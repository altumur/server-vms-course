"""Слой текста проверки формы манифеста (ADR-0085): байты → дерево JSON или отказ refused:text.

Парсер — ruamel.yaml (чистый Python, YAML 1.2); дерево строится из событий парсера, распознаватель простых
скаляров — свой, по таблице профиля §7 «Скаляры» (шапка 02-…schema.yaml). Правила, кроме стандарта YAML:
  E  знаки (encoding): BOM, C0 кроме TAB/LF/CR, DEL, C1, U+FFFE/FFFF, U+2028/2029, одиночный CR — в тексте
     и в значении после экранирований;
  R1 повтор ключа; R2 якорь/псевдоним; R3 ключ `<<`; R4 тег; R5 глубина > 64;
  K  простой ключ, который таблица скаляров Н1.1 читает не строкой; ключ-коллекция;
  S  короткий список «редкие конструкции» (профиль §8): TAB вне кавычек/блочного скаляра/комментария,
     поток или строка в кавычках на несколько строк, указатель отступа `|2`, ключ `? …`, директива `%`, `...`,
     второй документ;
  T  корень не отображение; N  сверх короткого списка (профиль §8), в том числе значение ключа на следующей
     строке не блочной коллекцией и простое слово с `?` в начале.
Не отказ: ключ любой длины (_Scanner), одиночный `-` значением блочного ключа — слово (RE_DASH_VALUE), одиночный
`-` с пробелом в потоке — слово (_quote_flow_dashes, свод Т16).
Числа: целое по модулю > 2^53−1 и не-конечное float — не отказ текста, а запись в numbers (класс value).
"""
import math
import re

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.scanner import Scanner, ScannerError

MAX_DEPTH = 64
MAX_INT = 2 ** 53 - 1

# Скаляры (профиль §7): порядок проверки — null, bool, int, float; иначе строка.
RE_NULL = re.compile(r"\A(?:null|Null|NULL|~|)\Z")
RE_BOOL = re.compile(r"\A(?:true|false)\Z", re.IGNORECASE)          # Н1.1 scalars: bool в любом регистре
RE_INT = re.compile(r"\A[-+]?[0-9]+\Z")
RE_FLOAT = re.compile(r"\A[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?\Z")
RE_INF = re.compile(r"\A[-+]?\.(?:inf|Inf|INF)\Z")
RE_NAN = re.compile(r"\A\.(?:nan|NaN|NAN)\Z")
RE_BAD_CHAR = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ufffe\uffff\u2028\u2029\ud800-\udfff]")


# Н1.1 string: одиночный `-` значением блочного ключа (`unit: -`) — слово; YAML читал бы его указателем списка.
# Такое значение до парсера берётся в кавычки: строка та же, строки и колонки ключа не сдвигаются.
RE_DASH_VALUE = re.compile(r"^( *(?:- +)*[^ #\"'{\[\]},?&*!|>%@`-][^#\"']*?: +)-( *| +#.*)$")


class _Scanner(Scanner):
    """Н1.1 keys: длину ключа текст не ограничивает — без предела 1024 знаков неявного ключа YAML 1.2."""

    def stale_possible_simple_keys(self):
        for level in list(self.possible_simple_keys):
            key = self.possible_simple_keys[level]
            if key.line != self.reader.line:
                if key.required:
                    raise ScannerError("while scanning a simple key", key.mark, "could not find expected ':'",
                                       self.reader.get_mark())
                del self.possible_simple_keys[level]


# Н1.1 string, свод Т16: одиночный `-` в потоке — слово и с пробелом после (`[ - , a ]`, `[a, - ]`, `{u: - }`); без
# пробела (`[-, a]`) YAML и так читает его словом. С пробелом сканер YAML даёт знак элемента блочного списка, а парсер
# отказывает. Такой знак — элемент списка (после `[` или `,`) или значение отображения (после `:`), за ним на той же
# строке только пробелы и `,`, `]` или `}` — до парсера берётся в кавычки; номера строк не сдвигаются.
_FLOW_DASH_BEFORE = {"[": ("FlowSequenceStartToken", "FlowEntryToken"), "{": ("ValueToken",)}
_FLOW_DASH_AFTER = ("FlowEntryToken", "FlowSequenceEndToken", "FlowMappingEndToken")


def _quote_flow_dashes(text):
    if not re.search(r"-[ ]+[,\]}]", text):
        return text
    y = YAML(typ="safe", pure=True)
    y.version = (1, 2)
    y.Scanner = _Scanner
    try:
        tokens = list(y.scan(text))
    except (YAMLError, ValueError):          # отказ скажет разбор
        return text
    lines = text.split("\n")
    flow, marks = [], []
    for i, t in enumerate(tokens):
        name = type(t).__name__
        if name in ("FlowSequenceStartToken", "FlowMappingStartToken"):
            flow.append("[" if name == "FlowSequenceStartToken" else "{")
        elif name in ("FlowSequenceEndToken", "FlowMappingEndToken"):
            if flow:
                flow.pop()
        elif name == "BlockEntryToken" and flow and 0 < i < len(tokens) - 1:
            prev, nxt = type(tokens[i - 1]).__name__, tokens[i + 1]
            a, b = t.start_mark, nxt.start_mark
            if (prev in _FLOW_DASH_BEFORE[flow[-1]] and type(nxt).__name__ in _FLOW_DASH_AFTER and a.line == b.line
                    and not lines[a.line][a.column + 1:b.column].strip(" ")):
                marks.append((a.line, a.column))
    for ln, col in reversed(marks):
        s = lines[ln]
        lines[ln] = s[:col] + '"-"' + s[col + 1:]
    return "\n".join(lines)


class TextRefused(Exception):
    """path — путь отказа текста, где он есть (повтор ключа, ключ не строкой, строка без ключа): Н4 «Диагностика»."""
    def __init__(self, rule, line, msg, path=None):
        super().__init__("%s line %s: %s" % (rule, line, msg))
        self.rule, self.line, self.msg, self.path = rule, line, msg, path


class NonFinite:
    """Число, которое слой текста прочёл, но которое не помещается в JSON: отказ value на шаге значений."""
    def __init__(self, text):
        self.text = text


def resolve_plain(s):
    if RE_NULL.match(s):
        return None
    if RE_BOOL.match(s):
        return s[0] in "tT"
    if RE_INT.match(s):
        if len(s.lstrip("+-").lstrip("0")) > 16:        # > 2^53−1 заведомо; int() Python падает после 4300 знаков (Н1.1)
            return NonFinite(s)
        return int(s)
    if RE_FLOAT.match(s):
        return float(s)
    if RE_INF.match(s) or RE_NAN.match(s):
        return NonFinite(s)
    return s


def _check_chars(text, base_line=None):
    m = RE_BAD_CHAR.search(text)
    if m:
        line = base_line if base_line is not None else text.count("\n", 0, m.start()) + 1
        raise TextRefused("E", line, "character U+%04X" % ord(m.group(0)))


def load_text(data):
    """bytes → (tree, numbers, empties) или TextRefused. numbers — пути чисел вне диапазона, empties — пути
    пустых значений (оба — класс value)."""
    return load_text_map(data)[:3]


def load_text_map(data):
    """То же и карта строк: {путь (кортеж ключей и индексов): строка ключа или элемента} (ADR-0087 доп. (3) Р4)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise TextRefused("E", data.count(b"\n", 0, e.start) + 1, "not UTF-8")
    if text.startswith("\ufeff"):
        raise TextRefused("E", 1, "BOM")
    _check_chars(text)
    i = text.find("\r")
    while i >= 0:
        if text[i + 1:i + 2] != "\n":
            raise TextRefused("E", text.count("\n", 0, i) + 1, "lone CR")
        i = text.find("\r", i + 1)
    text = text.replace("\r\n", "\n")
    text = "\n".join(RE_DASH_VALUE.sub(r'\1"-"\2', s) for s in text.split("\n"))
    text = _quote_flow_dashes(text)
    lines = text.split("\n")
    y = YAML(typ="safe", pure=True)
    y.version = (1, 2)
    y.Scanner = _Scanner
    try:
        events = list(y.parse(text))
    except ValueError as e:      # ruamel 0.19.1: «\UFFFFFFFF» роняет chr() мимо YAMLError
        raise TextRefused("Y", 0, "parser: %s" % e)
    except YAMLError as e:
        mark = getattr(e, "problem_mark", None) or getattr(e, "context_mark", None)
        raise TextRefused("Y", (mark.line + 1) if mark else 0, str(e).split("\n")[0])
    return _build(events, lines)


def _build(events, lines):
    linemap = {}
    numbers = []
    empties = []               # сказанный ключ без значения (класс value)
    quoted_spans = []          # (line0, col0, line1, col1) — где TAB допустим
    docs = 0
    stack = []                 # [container, path, pending_key, key_line]
    root = [None]

    def put(value, ev):
        if not stack:
            root[0] = value
            return
        top = stack[-1]
        c = top[0]
        base = [t[6] for t in stack[1:]]
        if isinstance(c, list):
            linemap[tuple(base + [len(c)])] = ev.start_mark.line + 1
            c.append(value)
            return
        if top[2] is _NOKEY:
            raise TextRefused("K", ev.start_mark.line + 1, "collection as key", base)
        k = top[2]
        top[2] = _NOKEY
        if k in c:
            raise TextRefused("R1", top[3], "duplicate key %r" % k, base + [k])
        linemap[tuple(base + [k])] = top[3]
        c[k] = value

    def path_of():
        p = [t[6] for t in stack[1:]]
        if stack:
            t = stack[-1]
            p.append(len(t[0]) if isinstance(t[0], list) else t[2])
        return p

    for ev in events:
        name = type(ev).__name__
        if name in ("StreamStartEvent", "StreamEndEvent"):
            continue
        line = ev.start_mark.line + 1
        if name == "DocumentStartEvent":
            docs += 1
            if docs > 1:
                raise TextRefused("S", line, "second document")
            if getattr(ev, "version", None) or getattr(ev, "tags", None):
                raise TextRefused("S", line, "directive")
            continue
        if name == "DocumentEndEvent":
            if getattr(ev, "explicit", False):
                raise TextRefused("S", line, "document end marker")
            continue
        if name == "AliasEvent":
            raise TextRefused("R2", line, "alias")
        if getattr(ev, "anchor", None):
            raise TextRefused("R2", line, "anchor")
        if getattr(ev, "tag", None) is not None:
            raise TextRefused("R4", line, "tag")
        is_key = bool(stack) and isinstance(stack[-1][0], dict) and stack[-1][2] is _NOKEY
        # Н1.1 blocks: значение блочного ключа на следующей строке — только блочное (отображение или список);
        # слово, кавычки или поток под ключом с пустым значением — строка, не отнесённая к ключу.
        empty = name == "ScalarEvent" and ev.value == "" and ev.style is None
        if (stack and isinstance(stack[-1][0], dict) and not stack[-1][4] and not is_key and not empty
                and (name == "ScalarEvent" or ev.flow_style) and line != stack[-1][3]):
            raise TextRefused("N", line, "value on the line after its key is not a block collection", path_of())
        # Н1.1 blocks: скаляр или поток строкой ниже голого «-» — отказ текста (как значение ниже ключа).
        if (stack and isinstance(stack[-1][0], list) and not stack[-1][4] and not empty
                and (name == "ScalarEvent" or getattr(ev, "flow_style", False))
                and not lines[ev.start_mark.line][:ev.start_mark.column].rstrip().endswith("-")):
            raise TextRefused("N", line, "item value on the line after its dash")
        if name in ("MappingStartEvent", "SequenceStartEvent"):
            if is_key:
                raise TextRefused("K", line, "collection as key", path_of()[:-1])
            if len(stack) + 1 > MAX_DEPTH:
                raise TextRefused("R5", line, "depth > %d" % MAX_DEPTH)
            c = {} if name == "MappingStartEvent" else []
            if not stack:
                if ev.flow_style or ev.start_mark.column != 0:
                    raise TextRefused("N", line, "root is not a block mapping at column 1")
            elif ev.flow_style and name == "MappingStartEvent" and lines[ev.start_mark.line][ev.start_mark.column:ev.start_mark.column + 1] != "{":
                raise TextRefused("N", line, "pair k: v inside a flow sequence")
            at = path_of()[-1:] or [None]
            put(c, ev)
            stack.append([c, None, _NOKEY, line, ev.flow_style, ev.start_mark.line, at[0], -1])
            continue
        if name in ("MappingEndEvent", "SequenceEndEvent"):
            _hash_after(lines, ev.end_mark)
            if stack[-1][4] and lines[ev.start_mark.line][:ev.start_mark.column].rstrip().endswith(","):
                raise TextRefused("N", line, "empty flow item (trailing comma)")
            top = stack.pop()
            if top[4] and ev.start_mark.line != top[5]:
                raise TextRefused("S", line, "flow collection on several lines")
            continue
        # ScalarEvent
        style = ev.style
        plain = ev.implicit[0] and style is None
        if style in ('"', "'", "|", ">"):
            quoted_spans.append((ev.start_mark.line, ev.start_mark.column, ev.end_mark.line, ev.end_mark.column))
            _check_chars(ev.value, line)
            if style in ('"', "'"):
                _hash_after(lines, ev.end_mark)
            if style in ('"', "'") and ev.end_mark.line != ev.start_mark.line:
                raise TextRefused("S", line, "quoted scalar on several lines")
            if style in ("|", ">"):
                hdr = lines[ev.start_mark.line][ev.start_mark.column:]
                if re.match(r"[|>][+-]?[1-9]|[|>][1-9]", hdr):
                    raise TextRefused("S", line, "block scalar indentation indicator")
        if plain and ev.value.startswith("?"):
            raise TextRefused("N", line, "plain scalar starting with '?'")
        # Н1.1 comment: `слово# c` — «#» после знака, а не пробела, перед пробелом — не комментарий, а строка без ключа.
        if plain and re.search(r"[^ \t]#[ \t]", ev.value):   # `a#b`, `C#` — слово (свод Т28)
            raise TextRefused("N", line, "'#' after a word is not a comment", path_of())
        if is_key:
            if not plain or ev.value != "<<":
                pass
            else:
                raise TextRefused("R3", line, "merge key <<")
            if plain and not isinstance(resolve_plain(ev.value), str):
                raise TextRefused("K", line, "key %r is not a string by the scalars table (Н1.1)" % ev.value,
                                  path_of()[:-1] + [ev.value])
            before = lines[ev.start_mark.line][:ev.start_mark.column].rstrip()
            if before.endswith("?") and (len(before) == 1 or before[-2] in " \t-[{,"):
                raise TextRefused("S", line, "complex key ? …")
            key = ev.value
            if stack[-1][4]:
                rest = lines[ev.end_mark.line][ev.end_mark.column:].lstrip(" ")
                # {k:} — the parser keeps ':' inside the plain key; Н1.1 reads it as key k with an empty value (Н12).
                if plain and key.endswith(":") and rest[:1] in ("}", ","):
                    key = key[:-1]
                elif not rest.startswith(":"):
                    raise TextRefused("N", line, "flow mapping key without ':'")
            stack[-1][2] = key
            stack[-1][3] = line
            stack[-1][7] = ev.start_mark.column
            continue
        if plain and ev.value != "" and stack and not stack[-1][4]:
            top = stack[-1]
            p = top[7] if isinstance(top[0], dict) else _indent(lines[ev.start_mark.line])
            try:
                _check_continuation(lines, ev.start_mark.line, p)
            except TextRefused as e:
                e.path = path_of()
                raise
        if plain:
            v = resolve_plain(ev.value)
            if ev.value == "":
                empties.append(path_of())
            if isinstance(v, NonFinite):
                numbers.append((path_of(), ev.value))
                v = None
            elif isinstance(v, int) and not isinstance(v, bool) and abs(v) > MAX_INT:
                numbers.append((path_of(), ev.value))
                v = None
            elif isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
                numbers.append((path_of(), ev.value))
                v = None
            elif isinstance(v, float) and v == 0.0 and re.search(r"[1-9]", re.split(r"[eE]", ev.value)[0]):
                numbers.append((path_of(), ev.value))   # потеря значимости (1e-400 → 0) — отказ value (Н1.1)
                v = None
        else:
            v = ev.value
        put(v, ev)
    _check_tabs(lines, quoted_spans)
    if not isinstance(root[0], dict):
        raise TextRefused("T", 1, "root is not a mapping")
    return root[0], numbers, empties, linemap


_NOKEY = object()


def _indent(s):
    return len(s) - len(s.lstrip(" "))


CONT_BAD_START = tuple("[{\"'&*!|>")


def _check_continuation(lines, l0, p):
    """Н1.1 blocks: строка продолжения простого слова (глубже ключа) с «: », «:» в конце или с начальным
    [, {, кавычкой, &, *, !, |, > — строка, не отнесённая ни к какому ключу. Строка-комментарий — не продолжение."""
    for ln in range(l0 + 1, len(lines)):
        s = lines[ln]
        if not s.strip():
            continue
        if _indent(s) <= p:
            return
        t = s.strip()
        if t.startswith("#"):
            continue
        if t.startswith(CONT_BAD_START) or ": " in t or t.endswith(":") or " #" in t or "\t#" in t:
            raise TextRefused("N", ln + 1, "continuation line of a plain word looks like a key or an indicator")


def _hash_after(lines, mark):
    if mark.line < len(lines) and lines[mark.line][mark.column:mark.column + 1] == "#":
        raise TextRefused("N", mark.line + 1, "'#' right after a quote or flow end is not a comment")


def _check_tabs(lines, spans):
    by_line = {}
    for l0, c0, l1, c1 in spans:
        for ln in range(l0, l1 + 1):
            a = c0 if ln == l0 else 0
            b = c1 if ln == l1 else 10 ** 9
            by_line.setdefault(ln, []).append((a, b))
    for ln, s in enumerate(lines):
        if "\t" not in s:
            continue
        sp = by_line.get(ln, [])
        inside = lambda col: any(a <= col < b for a, b in sp)  # noqa: E731
        comment_at = None
        for col, ch in enumerate(s):
            if ch == "#" and not inside(col) and (col == 0 or s[col - 1] in " \t"):
                comment_at = col
                break
        for col, ch in enumerate(s):
            if ch == "\t" and not inside(col) and (comment_at is None or col < comment_at):
                raise TextRefused("S", ln + 1, "TAB outside quotes, block scalar and comment")
