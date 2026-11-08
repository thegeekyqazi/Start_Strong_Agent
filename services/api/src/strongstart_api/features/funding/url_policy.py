"""Public-capture destination policy (SEC-03, partial; B1-DISC-001 s6; OWASP SSRF guidance).

What this enforces at the application layer:
- http/https only, no URL credentials, ports 80/443 only, IDNA-valid hostnames;
- no IP-literal tricks (decimal/octal/hex integer hosts), no localhost/.local/.internal;
- every resolved address (and any IP literal) must be globally routable: loopback,
  private, link-local (incl. cloud metadata 169.254.169.254), CGNAT, multicast,
  reserved, unspecified and IPv4-mapped/NAT64 forms of those are rejected;
- provider-reported final URLs are re-checked with the same policy.

Residual limit (recorded, not hidden): when a third-party capture provider fetches the
page, this check cannot observe which addresses the provider actually contacted or how
it followed redirects/DNS, and a one-time resolution here does not prevent DNS
rebinding. That needs connection-time egress controls, which this slice does not have.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

Resolver = Callable[[str], Iterable[str]]

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_PORTS = {"http": 80, "https": 443}
MAX_URL_LENGTH = 2048
BLOCKED_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".lan",
    ".home",
    ".corp",
    ".intranet",
    ".arpa",
)
BLOCKED_HOSTS = frozenset({"localhost", "metadata", "metadata.google.internal"})
_NUMERIC_HOST = re.compile(r"^(0x[0-9a-f]+|[0-9]+)(\.(0x[0-9a-f]+|[0-9]+)){0,3}$", re.I)
_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_EXTRA_BLOCKED_NETS = (
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT
    ipaddress.ip_network("64:ff9b::/96"),  # NAT64 (embeds IPv4)
    ipaddress.ip_network("192.0.0.0/24"),
)


class UnsafeDestinationError(ValueError):
    """URL rejected by the destination policy. ``reason`` is safe to show staff."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class CheckedUrl:
    url: str
    scheme: str
    host: str
    addresses: tuple[str, ...]


def system_resolver(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return sorted({str(info[4][0]) for info in infos})


def _address_is_public(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.ipv4_mapped is not None:
            return _address_is_public(addr.ipv4_mapped)
        if addr.sixtofour is not None or addr.teredo is not None:
            return False
    if any(addr in net for net in _EXTRA_BLOCKED_NETS if net.version == addr.version):
        return False
    return addr.is_global and not (
        addr.is_multicast or addr.is_reserved or addr.is_loopback or addr.is_link_local
    )


def _split(url: str) -> SplitResult:
    if len(url) > MAX_URL_LENGTH:
        raise UnsafeDestinationError("URL is too long")
    if any(ord(ch) < 0x21 or ch in "\\\x7f" for ch in url):
        raise UnsafeDestinationError("URL contains whitespace, control or backslash characters")
    try:
        parts = urlsplit(url)
        _ = parts.port  # raises ValueError on malformed ports
    except ValueError:
        raise UnsafeDestinationError("URL could not be parsed") from None
    return parts


def _validated_host(parts: SplitResult) -> str:
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeDestinationError("only http and https URLs can be captured")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise UnsafeDestinationError("URLs containing credentials are not allowed")
    raw_host = parts.hostname
    if not raw_host:
        raise UnsafeDestinationError("URL has no host")
    port = parts.port
    if port is not None and port != ALLOWED_PORTS[parts.scheme.lower()]:
        raise UnsafeDestinationError("only default ports (80/443) are allowed")
    host = raw_host.rstrip(".").lower()
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not _address_is_public(literal):
            raise UnsafeDestinationError("destination address is not public")
        return host
    if _NUMERIC_HOST.match(host):
        raise UnsafeDestinationError("numeric/encoded IP host forms are not allowed")
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError:
        raise UnsafeDestinationError("hostname is not valid IDNA") from None
    labels = ascii_host.split(".")
    if len(labels) < 2 or not all(_LABEL.match(label) for label in labels):
        raise UnsafeDestinationError("hostname is not a valid public DNS name")
    if ascii_host in BLOCKED_HOSTS or ascii_host.endswith(BLOCKED_HOST_SUFFIXES):
        raise UnsafeDestinationError("local/internal hostnames are not allowed")
    return ascii_host


def check_syntax(url: str) -> tuple[SplitResult, str]:
    parts = _split(url)
    return parts, _validated_host(parts)


def check_public_url(url: str, resolver: Resolver | None) -> CheckedUrl:
    """Validate ``url``; ``resolver=None`` skips DNS (only for registered fixture URLs)."""
    parts, host = check_syntax(url)
    try:
        ipaddress.ip_address(host)
        is_literal = True
    except ValueError:
        is_literal = False
    if is_literal:
        addresses: tuple[str, ...] = (host,)  # already checked public in check_syntax
    elif resolver is None:
        addresses = ()
    else:
        try:
            addresses = tuple(resolver(host))
        except OSError:
            raise UnsafeDestinationError("hostname did not resolve") from None
        if not addresses:
            raise UnsafeDestinationError("hostname did not resolve")
        for item in addresses:
            try:
                addr = ipaddress.ip_address(item.split("%", 1)[0])
            except ValueError:
                raise UnsafeDestinationError("resolver returned an invalid address") from None
            if not _address_is_public(addr):
                raise UnsafeDestinationError("hostname resolves to a non-public address")
    return CheckedUrl(url=url, scheme=parts.scheme.lower(), host=host, addresses=addresses)
