"""URL validation – guards against SSRF attacks.

Before fetching any user-supplied URL we verify:
1. The scheme is http or https.
2. The resolved host is not a private/loopback/link-local/multicast address.

This prevents attackers from using BugLens AI as a proxy to reach internal
services (AWS metadata endpoints, localhost services, RFC-1918 ranges, etc.).
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class URLValidationError(ValueError):
    """Raised when a user-supplied URL fails the safety checks."""


_BLOCKED_SCHEMES = frozenset({"file", "ftp", "gopher", "data", "jar"})
_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "ip6-localhost",
        "ip6-loopback",
        "broadcasthost",
        "0.0.0.0",
    }
)


def _is_private_ip(hostname: str) -> bool:
    """Return True if *hostname* resolves to a non-public IP address."""
    try:
        addr_info = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        # Cannot resolve – treat as safe (the fetch itself will fail later)
        return False

    for _, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return True
        except ValueError:
            continue

    return False


def validate_url(url: str) -> str:
    """Raise URLValidationError if *url* should not be fetched.

    Returns the original *url* unchanged so callers can use the return value
    as a sanitised reference, making the validation explicit in data flow.

    Intended to be called before every outbound HTTP request that originates
    from user input.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise URLValidationError(
            f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed."
        )

    hostname = parsed.hostname
    if not hostname:
        raise URLValidationError("URL must include a valid hostname.")

    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise URLValidationError(f"Requests to '{hostname}' are not permitted.")

    if _is_private_ip(hostname):
        raise URLValidationError(
            f"Requests to private/internal hosts are not permitted (resolved host: {hostname})."
        )

    return url