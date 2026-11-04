# Примитивы #fn таблиц проверок (ADR-0120 п. 2 (а)), написаны руками один раз; генератор вставляет файл в модуль.
# Имя примитива — prim_<имя #fn>. Аргументы уже проверены по типам объявления #fn; исключение — ошибка CEL.
# #fn без примитива здесь (allowed) — внешний обратный вызов: его передаёт вызывающий в fns.
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
