"""Validate user-supplied targets without changing the supplied page URL."""
import ipaddress
import re
from urllib.parse import urlsplit


def validate_web_target(value: str) -> str:
    if any(ord(c) < 33 for c in value) or "\\" in value:
        raise ValueError("Website URLs cannot contain whitespace or backslashes")
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Use a full http:// or https:// application URL")
        if parsed.username or parsed.password:
            raise ValueError("Do not include credentials in a URL")
        _ = parsed.port  # Reject malformed or out-of-range ports.
        host = parsed.hostname.lower().rstrip(".")
        # Private/LAN targets need a separate explicit administrator allowlist.
        if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
            raise ValueError("Private-network targets are not enabled")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if not re.fullmatch(r"[a-z0-9.-]+", host) or "." not in host:
                raise ValueError("Use a public application hostname")
        else:
            if not address.is_global:
                raise ValueError("Private-network targets are not enabled")
    except (ValueError, TypeError) as exc:
        raise ValueError(str(exc)) from exc
    return value


def product_name(url: str) -> str:
    host = urlsplit(url).hostname or "Website"
    labels = host.removeprefix("www.").split(".")
    # This is a display hint, not a product-identity verification.
    return labels[0].replace("-", " ").capitalize()
