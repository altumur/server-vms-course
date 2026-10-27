"""Слой 1 В7 на Python (ADR-0092 п. 2): готовый парсер YAML 1.2 (ruamel.yaml 0.19.1, события) и тонкая проверка.

Тонкая проверка (п. 2–4; Н1.1 в части, которую решение не отменяет; 11 отклонений Н1.1 от YAML 1.2.2 сняты, п. 3):
- байты: UTF-8, без BOM первым знаком, без C0 (кроме TAB, LF, CR), DEL, C1, U+FFFE/FFFF, U+2028/2029, суррогатов;
  одиночный CR — отказ, CRLF → LF; те же знаки в значении после экранирования — отказ;
- TAB только в комментарии (п. 4): после `#`, начинающего комментарий (в начале строки или после пробела, вне кавычек);
- один документ — по байтам: `---` только первой непустой некомментарной строкой с колонки 1, `...` и `%` — отказ;
- корень — блочное отображение с колонки 1;
- отказ на якоре, псевдониме, `<<`, теге, повторе ключа, ключе-коллекции, глубине > 64, простом ключе, который таблица
  скаляров читает не строкой;
- Н1.1:95 — поток или строка в кавычках на несколько строк, указатель отступа (`|2`), сложный ключ `? …`; :46 — `...`, `%`;
- `{k:}` — отказ (п. 4);
- скаляры по стилю узла: простой — по `scalars.tsv` (первая совпавшая строка), в кавычках и блочный — строка; пустое
  простое значение — «сказанный ключ без значения» (empties); числа вне пределов таблицы и потеря значимости — numbers.
Выход — как у слоя текста эталона: (дерево, numbers, empties, строки ключей) или TextRefused(rule, line, msg, path).
"""
import math
import re
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

MAX_DEPTH = 64
SCALARS = Path(__file__).resolve().parents[4] / "Platform/02-installer/spec/02.1-installer.scalars.tsv"
BAD = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f￾￿  \ud800-\udfff]")


class TextRefused(Exception):
    def __init__(self, rule, line, msg, path=None):
        super().__init__("%s line %s: %s" % (rule, line, msg))
        self.rule, self.line, self.msg, self.path = rule, line, msg, path


class NonFinite:
    def __init__(self, text):
        self.text = text


def load_scalars(path=SCALARS):
    rows, limits = [], {}
    for line in Path(path).read_text(encoding="utf-8").split("\n"):
        if not line or line.startswith("#"):
            continue
        kind, pat, _ = line.split("\t")
        if kind == "kind":
            continue
        if kind == "limit":
            k, _, v = pat.partition("=")
            limits[k] = int(v) if k == "int_max" else float(v)
            continue
        rows.append((kind, re.compile(pat, re.S)))
    return rows, limits


ROWS, LIMITS = load_scalars()


def kind_of(s):
    return next(k for k, p in ROWS if p.fullmatch(s))


ESCAPES = set("0abt\tnvfre \"/\\N_LPxuU")


def scan_line(line):
    """Лексика строки для тонкой проверки: (колонка `#`, начинающего комментарий, или None; ошибка или None; колонки TAB
    экранирования `\\<TAB>` в двойных кавычках). Комментарий — `#` в начале строки или после пробела/TAB, вне кавычек.
    Ошибки (дефекты парсеров, yaml-test-suite): `#` вплотную после закрывающей кавычки или `]`/`}` (SU5Z); в двойных
    кавычках — экранирование вне YAML 1.2.2 (HRE5). `\\<TAB>` — экранирование YAML 1.2.2 и Н1.1, не литеральный TAB (п. 4
    запрещает байт TAB как знак текста; решение «Архитектора» по ревью Б, круг 2)."""
    q, prev, esc, tabs = None, " ", False, set()
    for i, c in enumerate(line):
        nxt = line[i + 1:i + 2]
        if q == '"':
            if esc:
                if c not in ESCAPES:
                    return None, "escape \\%s outside YAML 1.2.2" % c, tabs
                if c == "\t":
                    tabs.add(i)
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                q = None
                if nxt == "#":
                    return None, "comment without a space after a quoted scalar", tabs
        elif q == "'":
            if c == "'":
                if nxt == "'":
                    q = "''"
                else:
                    q = None
                    if nxt == "#":
                        return None, "comment without a space after a quoted scalar", tabs, tabs
        elif q == "''":
            q = "'"
        elif c in "\"'" and prev in " \t[{,:-?":
            q = c
        elif c in "]}" and nxt == "#":
            return None, "comment without a space after a flow collection", tabs
        elif c == "#" and prev in " \t":
            return i, None, tabs
        prev = c
    return None, None, tabs


def comment_start(line):
    return scan_line(line)[0]


def check_bytes(data):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise TextRefused("bytes", data.count(b"\n", 0, e.start) + 1, "not UTF-8")
    if text.startswith("\ufeff"):
        raise TextRefused("bytes", 1, "BOM")
    m = BAD.search(text)
    if m:
        raise TextRefused("bytes", text.count("\n", 0, m.start()) + 1, "character U+%04X" % ord(m.group(0)))
    i = text.find("\r")
    while i >= 0:
        if text[i + 1:i + 2] != "\n":
            raise TextRefused("bytes", text.count("\n", 0, i) + 1, "lone CR")
        i = text.find("\r", i + 1)
    text = text.replace("\r\n", "\n")
    if text and not text.endswith("\n"):
        text += "\n"                             # обход D16: последняя строка без LF — с LF (значение по YAML 1.2.2)
    lines = text.split("\n")
    content = False
    for no, ln in enumerate(lines, 1):
        c, err, esc_tabs = scan_line(ln)
        if err:
            raise TextRefused("lexis", no, err)
        for t, ch in enumerate(ln):
            if ch == "\t" and t not in esc_tabs and (c is None or t < c):
                raise TextRefused("tab", no, "TAB outside a comment (ADR-0092 п. 4)")
        if re.match(r"\.\.\.(\s|$)", ln):
            raise TextRefused("document", no, "`...` (Н1.1:46)")
        if ln.startswith("%"):
            raise TextRefused("document", no, "directive `%` (Н1.1:46)")
        if re.match(r"---(\s|$)", ln):
            if content:
                raise TextRefused("document", no, "second document or `---` after content")
            rest = ln[3:].strip()
            if rest and not rest.startswith("#"):
                raise TextRefused("document", no, "content on the `---` line")
            content = True
            continue
        if re.match(r"\s+---(\s|$)", ln):
            raise TextRefused("document", no, "`---` not at column 1")
        s = ln.strip()
        if s and not s.startswith("#"):
            content = True
    return text, lines


def block_leading_ok(lines, at):
    """Блочный скаляр с заголовком на строке at: начальные пустые строки тела не глубже первой строки содержимого."""
    base = len(lines[at]) - len(lines[at].lstrip(" "))
    lead = []
    for ln in lines[at + 1:]:
        if ln.strip() == "":
            lead.append(len(ln))
            continue
        ind = len(ln) - len(ln.lstrip(" "))
        if ind <= base:
            return not lead or max(lead) <= base
        return not lead or max(lead) <= ind
    return True


def load_text_map(data):
    text, lines = check_bytes(data)
    y = YAML(typ="safe", pure=True)
    y.version = (1, 2)
    try:
        events = list(y.parse(text))
    except YAMLError as e:
        mark = getattr(e, "problem_mark", None) or getattr(e, "context_mark", None)
        raise TextRefused("parser", (mark.line + 1) if mark else 0, str(e).split("\n")[0])
    except (ValueError, OverflowError) as e:         # ruamel 0.19.1: `\UFFFFFFFF` роняет chr() мимо YAMLError (D9)
        raise TextRefused("parser", 0, "parser: %s" % e)
    return Builder(events, lines).build()


class Builder:
    def __init__(self, events, lines):
        self.ev, self.i, self.lines = events, 0, lines
        self.numbers, self.empties, self.linemap = [], [], {}

    def next(self):
        e = self.ev[self.i]
        self.i += 1
        return e

    def peek(self):
        return self.ev[self.i]

    def build(self):
        name = lambda e: type(e).__name__   # noqa: E731
        assert name(self.next()) == "StreamStartEvent"
        e = self.next()
        if name(e) == "StreamEndEvent":
            raise TextRefused("root", 1, "empty file")
        e = self.peek()
        if name(e) != "MappingStartEvent" or e.flow_style or e.start_mark.column != 0:
            raise TextRefused("root", e.start_mark.line + 1, "the root is a block mapping from column 1")
        tree = self.node([], 1, None)
        if name(self.next()) != "DocumentEndEvent" or name(self.next()) != "StreamEndEvent":
            raise TextRefused("document", 0, "more than one document")
        return tree, self.numbers, self.empties, self.linemap

    def refuse(self, rule, e, msg, path=None):
        raise TextRefused(rule, e.start_mark.line + 1, msg, path)

    def common(self, e, path):
        if type(e).__name__ == "AliasEvent":
            self.refuse("alias", e, "alias `*`", path)
        if getattr(e, "anchor", None) is not None:
            self.refuse("anchor", e, "anchor `&`", path)
        if getattr(e, "tag", None) is not None:
            self.refuse("tag", e, "tag `!…`", path)

    def node(self, path, depth, key_event):
        e = self.next()
        self.common(e, path)
        n = type(e).__name__
        if n in ("MappingStartEvent", "SequenceStartEvent"):
            if depth > MAX_DEPTH:
                self.refuse("depth", e, "nesting deeper than 64", path)
            if e.flow_style:
                self.flow_one_line(e, path)
            if n == "MappingStartEvent":
                return self.mapping(e, path, depth)
            out = []
            while type(self.peek()).__name__ != "SequenceEndEvent":
                out.append(self.node(path + [len(out)], depth + 1, None))
            self.next()
            return out
        return self.scalar(e, path)

    def flow_one_line(self, start, path):
        """Н1.1:95 — поток на одной строке: конец потока на строке начала."""
        d, j = 0, self.i
        while True:
            x = self.ev[j]
            nm = type(x).__name__
            if nm in ("MappingStartEvent", "SequenceStartEvent"):
                d += 1
            elif nm in ("MappingEndEvent", "SequenceEndEvent"):
                if d == 0:
                    if x.end_mark.line != start.start_mark.line:
                        self.refuse("rare", start, "flow collection on several lines (Н1.1:95)", path)
                    return
                d -= 1
            j += 1

    def mapping(self, e, path, depth):
        out = {}
        while type(self.peek()).__name__ != "MappingEndEvent":
            k = self.next()
            kn = type(k).__name__
            self.common(k, path)
            if kn != "ScalarEvent":
                self.refuse("key", k, "a key is a collection", path)
            ln = self.lines[k.start_mark.line][:k.start_mark.column].rstrip()
            if ln.endswith("?") and (len(ln) == 1 or ln[-2] in " \t-[{,") or ln == "?":
                self.refuse("rare", k, "complex key `? …` (Н1.1:95)", path)
            if k.style is None:
                if k.value == "<<":
                    self.refuse("merge", k, "merge key `<<`", path)
                if kind_of(k.value) != "string":
                    self.refuse("key", k, "a plain key read as %s" % kind_of(k.value), path + [k.value])
            else:
                self.scalar_style(k, path)
                self.chars(k, path)
            key = k.value
            if key in out:
                self.refuse("duplicate", k, "key %r said twice" % key, path + [key])
            self.linemap[tuple(path + [key])] = k.start_mark.line + 1
            v = self.peek()
            if (e.flow_style and type(v).__name__ == "ScalarEvent" and v.style is None and v.value == ""
                    and v.start_mark.line == k.start_mark.line):
                self.refuse("flow", v, "`{k:}` — key without a value in a flow mapping (ADR-0092 п. 4)", path + [key])
            out[key] = self.node(path + [key], depth + 1, k)
        self.next()
        return out

    def scalar_style(self, e, path):
        if e.style in ('"', "'") and e.end_mark.line != e.start_mark.line:
            self.refuse("rare", e, "quoted string on several lines (Н1.1:95)", path)
        if e.style in ("|", ">"):
            if "\t" in e.value:                  # TAB в теле блочного скаляра — вне комментария (п. 4)
                self.refuse("tab", e, "TAB in a block scalar (ADR-0092 п. 4)", path)
            head = self.lines[e.start_mark.line][e.start_mark.column:]
            if re.match(r"[|>][-+]?[0-9]|[|>][0-9]", head):
                self.refuse("rare", e, "explicit indentation indicator (Н1.1:95)", path)
            if not re.match(r"[|>][-+]?(\s|$)", head):
                self.refuse("lexis", e, "block scalar header without a space before a comment (X4QW)", path)
            if not block_leading_ok(self.lines, e.start_mark.line):
                self.refuse("lexis", e, "leading empty line deeper than the first content line (S98Z)", path)

    def chars(self, e, path):
        m = BAD.search(e.value)
        if m:
            self.refuse("bytes", e, "character U+%04X in a value" % ord(m.group(0)), path)

    def scalar(self, e, path):
        self.chars(e, path)
        if e.style is not None:
            self.scalar_style(e, path)
            return e.value
        s = e.value
        if s == "":
            self.empties.append(path)
            return None
        k = kind_of(s)
        if k == "null":
            return None
        if k in ("true", "false"):
            return k == "true"
        if k == "int":
            if len(s.lstrip("+-").lstrip("0")) > 16 or abs(int(s)) > LIMITS["int_max"]:
                self.numbers.append((path, s))
                return NonFinite(s)
            return int(s)
        if k == "float":
            x = float(s)
            if (not math.isfinite(x) or abs(x) > LIMITS["float_max"]
                    or (x == 0 and re.search(r"[1-9]", s.split("e")[0].split("E")[0]))):
                self.numbers.append((path, s))
                return NonFinite(s)
            return x
        if k == "nonfinite":
            self.numbers.append((path, s))
            return NonFinite(s)
        return s
