"""Conservative URL normalization, deduplication and query building (B1-DISC-001 s4).

Normalization only: lowercase scheme/host, drop default port, drop fragment and a
configured list of known tracking parameters. Path, case of path, trailing slashes and
all other query parameters (including cycle/stream/year parameters) are preserved, so
distinct rounds are never merged because titles or funder names look alike.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from strongstart_contracts.discovery import SearchProfile

TRACKING_PARAMS = frozenset(
    {"gclid", "fbclid", "msclkid", "dclid", "mc_cid", "mc_eid", "_hsenc", "_hsmi", "igshid"}
)
TRACKING_PREFIXES = ("utm_",)
DEFAULT_PORTS = {"http": 80, "https": 443}
BASE_QUERY_TERMS = ("grant", "funding")
MAX_QUERY_CHARS = 300


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").rstrip(".").lower()
    port = parts.port
    netloc = host if port is None or DEFAULT_PORTS.get(scheme) == port else f"{host}:{port}"
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith(TRACKING_PREFIXES)
    ]
    return urlunsplit((scheme, netloc, parts.path or "/", urlencode(kept, doseq=True), ""))


def stable_hash(*parts: str, length: int = 24) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:length]


def build_query(profile: SearchProfile, allowed_fields: Sequence[str]) -> tuple[str, list[str]]:
    """Build the provider query from the *profile only* (no ports, no private data).

    Returns (query_text, fields_used). Only fields in the server allowlist are used.
    """
    pieces: list[str] = []
    used: list[str] = []
    if "interests" in allowed_fields:
        pieces.extend(profile.interests)
        used.append("interests")
    if "program_context" in allowed_fields and profile.program_context:
        pieces.append(profile.program_context)
        used.append("program_context")
    if "geography" in allowed_fields and profile.geography:
        pieces.append(profile.geography)
        used.append("geography")
    query = " ".join([*pieces, *BASE_QUERY_TERMS])
    query = re.sub(r"\s+", " ", query).strip()
    if len(query) > MAX_QUERY_CHARS:
        raise ValueError(f"query exceeds {MAX_QUERY_CHARS} characters")
    return query, used


def matched_terms(profile: SearchProfile, *texts: str) -> list[str]:
    haystack = " ".join(texts).lower()
    terms = [*profile.interests, profile.program_context or "", profile.geography or ""]
    found: list[str] = []
    for term in terms:
        t = term.strip().lower()
        if t and re.search(rf"(?<!\w){re.escape(t)}(?!\w)", haystack) and term not in found:
            found.append(term)
    return found
