"""DISC-12: unsafe destinations rejected (SEC-03 application-layer predicates only)."""

from __future__ import annotations

import pytest

from strongstart_api.features.funding.url_policy import (
    UnsafeDestinationError,
    check_public_url,
)

PUBLIC = lambda host: ["93.184.215.14"]  # noqa: E731


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.org/x",
        "javascript:alert(1)",
        "gopher://example.org/",
        "https://user:pw@example.org/",
        "https://user@example.org/",
        "http://127.0.0.1/",
        "http://127.1/",
        "http://2130706433/",
        "http://0x7f000001/",
        "http://017700000001/",
        "http://0.0.0.0/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://100.64.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://[fe80::1]/",
        "http://[fd00::1]/",
        "http://localhost/",
        "http://app.localhost/",
        "http://printer.local/",
        "http://metadata.google.internal/",
        "https://example.org:8443/",
        "https://example.org:22/",
        "https://exa mple.org/",
        "https://example.org\\@evil/",
        "https:///nohost",
        "https://-bad-.example/",
        "https://singlelabel/",
    ],
)
def test_unsafe_urls_rejected(url: str) -> None:
    with pytest.raises(UnsafeDestinationError):
        check_public_url(url, PUBLIC)


@pytest.mark.parametrize(
    "resolved",
    [
        ["10.1.2.3"],
        ["93.184.215.14", "127.0.0.1"],
        ["169.254.169.254"],
        ["::1"],
        ["fd12::1"],
        ["::ffff:192.168.0.1"],
        [],
    ],
)
def test_hostnames_resolving_to_non_public_addresses_rejected(resolved: list[str]) -> None:
    with pytest.raises(UnsafeDestinationError):
        check_public_url("https://rebind.example.org/", lambda host: resolved)


def test_resolution_failure_rejected() -> None:
    def fail(host: str) -> list[str]:
        raise OSError("nxdomain")

    with pytest.raises(UnsafeDestinationError):
        check_public_url("https://nope.example.org/", fail)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.example.org/grants?cycle=2026",
        "http://example.org",
        "https://EXAMPLE.org:443/a",
        "https://8.8.8.8/",
        "https://bücher.example/",
    ],
)
def test_public_urls_allowed(url: str) -> None:
    checked = check_public_url(url, PUBLIC)
    assert checked.scheme in {"http", "https"}
