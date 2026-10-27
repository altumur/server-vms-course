"""Выражение диалекта (DIALECT § 4) → переносимое выражение `pattern` (ADR-0092 п. 14): ECMA-262 в режиме `u` в
пересечении с RE2, полное совпадение якорями `^(?:…)$`.

Механический перевод: `.` → `[\\s\\S]` (точка диалекта берёт и `\\n`, `re.S`); `\\x{HHHH}` → сам знак; экранирование
остаётся только у знаков синтаксиса ECMA-262 (в режиме `u` иное экранирование — ошибка), `]` `{` `}` вне класса —
экранированы. Немеханическое — дополнение `name_not_pattern` (ADR-0092 п. 12): таблица MANUAL, вписана руками,
проверена тестом на случайных строках против `re.fullmatch` эталона.
"""
import re

SYNTAX = set("^$\\.*+?()[]{}|/")
_HEX = re.compile(r"\\x\{([0-9A-Fa-f]{2,6})\}")


def _char(c, in_class):
    if c in SYNTAX or (in_class and c == "-"):
        return "\\" + c
    return c


def portable(p):
    """Тело выражения диалекта → тело переносимого выражения (без якорей)."""
    out, i, cls = [], 0, False
    while i < len(p):
        c = p[i]
        m = _HEX.match(p, i)
        if m:
            out.append(_char(chr(int(m.group(1), 16)), cls))
            i = m.end()
            continue
        if c == "\\":
            out.append(_char(p[i + 1], cls))
            i += 2
            continue
        if cls:
            if c == "]" and out[-1] in ("[", "[^"):
                out.append("\\]")               # `[]…]` диалекта: `]` первым — знак; у ECMA-262 `[]` — пустой класс
            else:
                cls = c != "]"
                out.append(c)
        elif c == "[":
            cls = True
            if p[i + 1:i + 2] == "^":
                out.append("[^")
                i += 2
                continue
            out.append("[")
        elif c == ".":
            out.append("[\\s\\S]")
        elif c == "]":
            out.append("\\]")
        else:
            out.append(c)
        i += 1
    return "".join(out)


def anchored(p):
    """Выражение диалекта → `pattern` схемы: полное совпадение."""
    return "^(?:%s)$" % portable(p)


# Дополнения `name_not_pattern` (ADR-0092 п. 12: немеханическое место, переведено вручную и помечено). Ключ —
# выражение диалекта, значение — тело переносимого выражения, совпадающего ровно со строками, которые ключ НЕ берёт
# целиком. Без просмотра вперёд (RE2): «не кончается на `_secret`» — короче семи знаков или один из семи последних
# знаков не тот; «не имя blob» — пусто, первый знак не тот, знак не тот на месте 2–65, длиннее 64.
MANUAL = {
    ".*_secret":
        "[\\s\\S]{0,6}|[\\s\\S]*(?:[^_][\\s\\S]{6}|_[^s][\\s\\S]{5}|_s[^e][\\s\\S]{4}|_se[^c][\\s\\S]{3}"
        "|_sec[^r][\\s\\S]{2}|_secr[^e][\\s\\S]|_secre[^t])",
    "[A-Za-z_][A-Za-z0-9_]{0,63}":
        "|[^A-Za-z_][\\s\\S]*|[A-Za-z_][A-Za-z0-9_]{0,63}[^A-Za-z0-9_][\\s\\S]*|[A-Za-z_][A-Za-z0-9_]{63}[\\s\\S]+",
}


class NotTranslatable(Exception):
    pass


def complement(p):
    """Тело выражения-дополнения к выражению диалекта p; нет в MANUAL — NotTranslatable (дописать руками)."""
    if p not in MANUAL:
        raise NotTranslatable("name_not_pattern %r: no manual complement (ADR-0092 п. 12)" % p)
    return MANUAL[p]


def python_full(pattern):
    """Слой 5 (полное совпадение у Python): `$` в конце якоря → `\\Z` (у `re` `$` совпадает и перед последним `\\n`)."""
    return pattern[:-1] + "\\Z" if pattern.endswith(")$") else pattern
