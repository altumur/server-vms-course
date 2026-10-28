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


def check(pattern):
    """Причина, по которой `pattern` схемы вне переносимого подмножества (ADR-0092 п. 14), или None.

    Подмножество — то, что ECMA-262 в режиме `u` и RE2 читают одинаково: полное совпадение `^(?:…)$`; внутри — знаки,
    классы `[…]` и `[^…]` (без `[` внутри: у RE2 `[[:alpha:]]` — класс POSIX), экранирование только знаков синтаксиса
    (`-` — и в классе), `\\d`, `\\D`, `\\w`, `\\W` и `[\\s\\S]` (одиночный `\\s` у ECMA шире, чем у RE2), группы `(…)`,
    `(?:…)`, `|`, кванторы `* + ? {n} {n,} {n,m}` (и ленивые); без `.` (у ECMA точка не берёт `\\r`, U+2028/2029), без
    `^`, `$` внутри, без обратных ссылок, просмотра, имён групп и флагов."""
    if not (pattern.startswith("^(?:") and pattern.endswith(")$")):
        return "not anchored as ^(?:…)$ (full match)"
    p = pattern[1:-1]
    i, depth, atom = 0, 0, False
    while i < len(p):
        c = p[i]
        if c == "\\":
            e = p[i + 1:i + 2]
            if not e or not (e in SYNTAX or e in "dDwW"):
                return "escape \\%s at %d (only syntax characters, \\d, \\w and [\\s\\S])" % (e, i + 1)
            i, atom = i + 2, True
            continue
        if c == "[":
            if p.startswith("[\\s\\S]", i):
                i, atom = i + 6, True
                continue
            j = i + 1 + (p[i + 1:i + 2] == "^")
            if p[j:j + 1] == "]":
                return "empty or ]-first class at %d" % (i + 1)
            while j < len(p) and p[j] != "]":
                if p[j] == "[":
                    return "unescaped [ inside a class at %d" % (j + 1)
                if p[j] == "\\":
                    e = p[j + 1:j + 2]
                    if not e or not (e in SYNTAX or e in "-dDwW"):
                        return "escape \\%s in a class at %d" % (e, j + 1)
                    j += 2
                    continue
                j += 1
            if j >= len(p):
                return "unclosed class at %d" % (i + 1)
            i, atom = j + 1, True
            continue
        if c == "(":
            if p.startswith("(?", i) and not p.startswith("(?:", i):
                return "group (%s at %d: only (…) and (?:…)" % (p[i + 1:i + 3], i + 1)
            depth += 1
            i += 3 if p.startswith("(?:", i) else 1
            atom = False
            continue
        if c == ")":
            depth -= 1
            if depth < 0:
                return "unbalanced ) at %d" % (i + 1)
            i, atom = i + 1, True
            continue
        if c in "*+?":
            if not atom:
                return "quantifier %s without an atom at %d" % (c, i + 1)
            i += 1
            if p[i:i + 1] == "?":
                i += 1
            atom = False
            continue
        if c == "{":
            m = re.match(r"\{(0|[1-9][0-9]*)(,(0|[1-9][0-9]*)?)?\}", p[i:])
            if not m or not atom:
                return "{ at %d is not a quantifier {n}, {n,}, {n,m} after an atom (escape it)" % (i + 1)
            i += m.end()
            if p[i:i + 1] == "?":
                i += 1
            atom = False
            continue
        if c in "}]":
            return "unescaped %s at %d" % (c, i + 1)
        if c == ".":
            return "bare . at %d (write [\\s\\S] or a class)" % (i + 1)
        if c in "^$":
            return "anchor %s inside at %d" % (c, i + 1)
        if c == "|":
            i, atom = i + 1, False
            continue
        i, atom = i + 1, True
    if depth != 0:
        return "unbalanced ("
    try:
        re.compile(python_full(pattern))
    except re.error as exc:
        return "does not compile: %s" % exc
    return None
