# Примитивы #fn таблиц проверок (ADR-0120 п. 2 (а)), написаны руками один раз; генератор вставляет файл в модуль.
# Имя примитива — prim_<имя #fn>. Аргументы уже проверены по типам объявления #fn; исключение — ошибка CEL.
# #fn без примитива здесь (allowed) — внешний обратный вызов: его передаёт вызывающий в fns.
import ipaddress
import math


def prim_key_ok(k):
    """Н1 row.key: не пуст, не начинается с /, нет сегмента .., не длиннее 1024 байт UTF-8."""
    return k != "" and not k.startswith("/") and ".." not in k.split("/") and len(k.encode("utf-8")) <= 1024


def prim_weight(items):
    """Н1: сумма длин в байтах UTF-8 всех имён и значений items; не строка — ошибка."""
    total = 0
    for name, value in items.items():
        if type(name) is not str or type(value) is not str:
            raise TypeError("weight: items is not an object of strings")
        total += len(name.encode("utf-8")) + len(value.encode("utf-8"))
    return total


def prim_finite(x):
    """Конечно в binary64 (1e400 — нет)."""
    return math.isfinite(x)


def prim_loopback(addr):
    """Хост адреса host:port на петле: 127.0.0.0/8, ::1 или localhost (ADR-0125 доп. (2) п. 4); как net.SplitHostPort
    и net.ParseIP Go: IPv6 — в скобках, IPv4 в форме ::ffff:a.b.c.d — как IPv4, зона — не петля; не host:port — ошибка."""
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
