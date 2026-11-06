# Handwritten #fn primitives (ADR-0120, item 2(a)); the generator embeds this file into each module.
# Each prim_<fn> receives arguments already checked against its #fn types; an exception is a CEL error.
# Missing primitives such as allowed are external callbacks supplied by the caller in fns.
import ipaddress
import math


def prim_key_ok(k):
    """N1 row.key: nonempty, no leading slash or '..' segment, at most1024 UTF-8 bytes."""
    return k != "" and not k.startswith("/") and ".." not in k.split("/") and len(k.encode("utf-8")) <= 1024


def prim_weight(items):
    """N1: sum UTF-8 byte lengths of all item names/values; non-strings error."""
    total = 0
    for name, value in items.items():
        if type(name) is not str or type(value) is not str:
            raise TypeError("weight: items is not an object of strings")
        total += len(name.encode("utf-8")) + len(value.encode("utf-8"))
    return total


def prim_finite(x):
    """Check binary64 finiteness;1e400 is not finite."""
    return math.isfinite(x)


def prim_loopback(addr):
    """Check loopback host:port per ADR-0125 addendum 2, item 4:127/8, ::1 or localhost. Match Go SplitHostPort/ParseIP: bracketed IPv6, mapped IPv4 treated as IPv4, zones excluded. Invalid host:port errors."""
    if addr.startswith("["):
        end = addr.find("]")
        if end < 0 or not addr[end + 1:].startswith(":") or ":" in addr[end + 2:]:
            raise ValueError("loopback: not host:port")
        host = addr[1:end]
    else:
        host, sep, port = addr.rpartition(":")
        if not sep or ":" in host:
            raise ValueError("loopback: not host:port")
    if host.lower() == "localhost":
        return True
    if "%" in host:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_loopback if ip.version == 4 else ip == ipaddress.IPv6Address("::1")
