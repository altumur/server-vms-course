"""Загрузчик подмножества YAML 1.2 для генераторов tools/normgen (только стандартная библиотека Python).

Подмножество — то, чем пишутся OpenAPI уроков: блочные отображения и последовательности (в том числе последовательность
на отступе ключа), потоковые `{…}` и `[…]` (в том числе пара `k: v` элементом потоковой последовательности и потоковый
узел на нескольких строках), скаляры простые, в одинарных и двойных кавычках, блочные `|`, `>` с `-`/`+`, простой
скаляр на нескольких строках, комментарии `#`. Простые скаляры — по схеме core YAML 1.2 (null, bool, int, float).
Якоря, ссылки, теги, директивы, несколько документов, ключи-узлы, повтор ключа — отказ YamlError с номером строки.
Сверка с PyYAML на файлах курса — tools/normgen/test_gen_door.py.
"""
import re


class YamlError(Exception):
    pass


_INT = re.compile(r"[-+]?[0-9]+")
_OCT = re.compile(r"0o[0-7]+")
_HEX = re.compile(r"0x[0-9a-fA-F]+")
_FLOAT = re.compile(r"[-+]?(\.[0-9]+|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?")
_FLOW_END = ",[]{}"


def plain_value(text):
    """Простой скаляр → значение по схеме core YAML 1.2."""
    if text in ("null", "Null", "NULL", "~", ""):
        return None
    if text in ("true", "True", "TRUE"):
        return True
    if text in ("false", "False", "FALSE"):
        return False
    if _INT.fullmatch(text):
        return int(text)
    if _OCT.fullmatch(text):
        return int(text[2:], 8)
    if _HEX.fullmatch(text):
        return int(text[2:], 16)
    if _FLOAT.fullmatch(text):
        return float(text)
    if text in (".inf", ".Inf", ".INF", "+.inf", "+.Inf", "+.INF"):
        return float("inf")
    if text in ("-.inf", "-.Inf", "-.INF"):
        return float("-inf")
    if text in (".nan", ".NaN", ".NAN"):
        return float("nan")
    return text


_ESC = {"0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r",
        "e": "\x1b", " ": " ", '"': '"', "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0", "L": " ",
        "P": " "}


def _double(s, i, where):
    """s[i] == '"' → (строка, индекс после закрывающей кавычки)."""
    out, i = [], i + 1
    while i < len(s):
        c = s[i]
        if c == '"':
            return "".join(out), i + 1
        if c == "\\":
            if i + 1 >= len(s):
                break
            e = s[i + 1]
            if e in _ESC:
                out.append(_ESC[e])
                i += 2
                continue
            n = {"x": 2, "u": 4, "U": 8}.get(e)
            if n and re.fullmatch(r"[0-9a-fA-F]{%d}" % n, s[i + 2:i + 2 + n]):
                out.append(chr(int(s[i + 2:i + 2 + n], 16)))
                i += 2 + n
                continue
            raise YamlError(f"{where}: bad escape \\{e}")
        out.append(c)
        i += 1
    raise YamlError(f"{where}: unterminated double-quoted scalar")


def _single(s, i, where):
    out, i = [], i + 1
    while i < len(s):
        c = s[i]
        if c == "'":
            if s[i + 1:i + 2] == "'":
                out.append("'")
                i += 2
                continue
            return "".join(out), i + 1
        out.append(c)
        i += 1
    raise YamlError(f"{where}: unterminated single-quoted scalar")


def _check_plain(text, where):
    if not text:
        return
    if text[0] in "&*!|>%@`" or text.startswith("? ") or text == "?":
        raise YamlError(f"{where}: unsupported YAML construct {text[:20]!r}")


class _Flow:
    """Потоковый узел на одной логической строке."""

    def __init__(self, s, where):
        self.s, self.i, self.where = s, 0, where

    def ws(self):
        while self.i < len(self.s) and self.s[self.i] in " \t\n":
            self.i += 1

    def node(self):
        self.ws()
        if self.i >= len(self.s):
            raise YamlError(f"{self.where}: unexpected end of flow node")
        c = self.s[self.i]
        if c == "{":
            return self.mapping()
        if c == "[":
            return self.sequence()
        if c == '"':
            v, self.i = _double(self.s, self.i, self.where)
            return v
        if c == "'":
            v, self.i = _single(self.s, self.i, self.where)
            return v
        start = self.i
        while self.i < len(self.s):
            c = self.s[self.i]
            if c in _FLOW_END:
                break
            if c == ":" and (self.i + 1 >= len(self.s) or self.s[self.i + 1] in " \t\n" + _FLOW_END):
                break
            if c == "#" and self.i > start and self.s[self.i - 1] in " \t":
                raise YamlError(f"{self.where}: comment inside a flow node")
            self.i += 1
        text = " ".join(self.s[start:self.i].split())
        _check_plain(text, self.where)
        return plain_value(text)

    def colon(self):
        self.ws()
        if self.s[self.i:self.i + 1] == ":":
            self.i += 1
            return True
        return False

    def mapping(self):
        self.i += 1
        out = {}
        while True:
            self.ws()
            if self.s[self.i:self.i + 1] == "}":
                self.i += 1
                return out
            key = self.node()
            if isinstance(key, (dict, list)):
                raise YamlError(f"{self.where}: a collection as a key")
            value = None
            if self.colon():
                self.ws()
                if self.s[self.i:self.i + 1] not in (",", "}"):
                    value = self.node()
            if key in out:
                raise YamlError(f"{self.where}: repeated key {key!r}")
            out[key] = value
            self.ws()
            c = self.s[self.i:self.i + 1]
            if c == ",":
                self.i += 1
            elif c != "}":
                raise YamlError(f"{self.where}: expected , or }} in a flow mapping")

    def sequence(self):
        self.i += 1
        out = []
        while True:
            self.ws()
            if self.s[self.i:self.i + 1] == "]":
                self.i += 1
                return out
            item = self.node()
            if self.colon():                     # [k: v] — пара одним отображением
                self.ws()
                value = None if self.s[self.i:self.i + 1] in (",", "]") else self.node()
                if isinstance(item, (dict, list)):
                    raise YamlError(f"{self.where}: a collection as a key")
                item = {item: value}
            out.append(item)
            self.ws()
            c = self.s[self.i:self.i + 1]
            if c == ",":
                self.i += 1
            elif c != "]":
                raise YamlError(f"{self.where}: expected , or ] in a flow sequence")


def _strip_comment(text):
    """Комментарий ` #…` вне кавычек и потоковых узлов строки; → (текст без комментария, баланс скобок)."""
    q, depth, i = None, 0, 0
    while i < len(text):
        c = text[i]
        if q:
            if q == '"' and c == "\\":
                i += 2
                continue
            if c == q:
                if q == "'" and text[i + 1:i + 2] == "'":
                    i += 2
                    continue
                q = None
        elif c in "\"'" and (i == 0 or text[i - 1] in " \t[{,:-"):
            q = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        elif c == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i].rstrip(), depth
        i += 1
    return text.rstrip(), depth


class _Line:
    __slots__ = ("no", "indent", "text", "raw")

    def __init__(self, no, indent, text, raw):
        self.no, self.indent, self.text, self.raw = no, indent, text, raw


def _key_split(text, where):
    """'ключ: остаток' → (ключ, остаток) или None, если строка — не пара отображения."""
    if text[:1] in "\"'":
        v, j = (_double if text[0] == '"' else _single)(text, 0, where)
        rest = text[j:].lstrip(" ")
        if rest == ":" or rest.startswith(": "):
            return v, rest[1:].strip()
        return None
    if text[:1] in "[{":
        return None
    m = re.match(r"(.*?):( |$)", text)
    if not m:
        return None
    key = m[1].strip()
    _check_plain(key, where)
    if key == "":
        raise YamlError(f"{where}: empty key")
    return plain_value(key), text[m.end():].strip()


class _Block:
    def __init__(self, text, name):
        self.name = name
        self.lines = []
        raw_lines = text.split("\n")
        for no, raw in enumerate(raw_lines, 1):
            if "\t" in raw[:len(raw) - len(raw.lstrip())]:
                raise YamlError(f"{name}:{no}: tab in indentation")
            self.lines.append(_Line(no, len(raw) - len(raw.lstrip(" ")), raw.strip(" "), raw))
        self.i = 0
        self.anchors = {}                     # якоря &имя значений отображений (P/10); алиас *имя — то же значение
        for ln in self.lines:
            if ln.indent == 0 and (ln.text.startswith("---") or ln.text.startswith("...") or ln.text.startswith("%")):
                raise YamlError(f"{name}:{ln.no}: directives and document markers are not in the subset")

    def where(self, ln):
        return f"{self.name}:{ln.no}"

    def skip(self):
        while self.i < len(self.lines):
            t = self.lines[self.i].text
            if t == "" or t.startswith("#"):
                self.i += 1
            else:
                return self.lines[self.i]
        return None

    def parse(self):
        ln = self.skip()
        if ln is None:
            return None
        node = self.block(ln.indent)
        rest = self.skip()
        if rest is not None:
            raise YamlError(f"{self.where(rest)}: unexpected content (indentation)")
        return node

    def block(self, indent):
        ln = self.skip()
        if ln.text == "-" or ln.text.startswith("- "):
            return self.sequence(indent)
        return self.mapping(indent)

    def sequence(self, indent):
        out = []
        while True:
            ln = self.skip()
            if ln is None or ln.indent < indent:
                return out
            if ln.indent > indent:
                raise YamlError(f"{self.where(ln)}: bad indentation in a sequence")
            if not (ln.text == "-" or ln.text.startswith("- ")):
                return out
            body = ln.text[1:].lstrip(" ")
            if body == "" or body.startswith("#"):
                self.i += 1
                nxt = self.skip()
                if nxt is None or nxt.indent <= indent:
                    out.append(None)
                else:
                    out.append(self.block(nxt.indent))
                continue
            col = ln.indent + (len(ln.text) - len(body))
            # Содержимое после «- » — строка на отступе col: тот же разбор блока.
            self.lines[self.i] = _Line(ln.no, col, body, ln.raw)
            if _key_split(_strip_comment(body)[0], self.where(ln)) is not None or body == "-" or \
                    body.startswith("- "):
                out.append(self.block(col))
            else:
                out.append(self.scalar_rest(body, ln, indent))
        return out

    def mapping(self, indent):
        out = {}
        while True:
            ln = self.skip()
            if ln is None or ln.indent < indent:
                return out
            if ln.indent > indent:
                raise YamlError(f"{self.where(ln)}: bad indentation in a mapping")
            if ln.text == "-" or ln.text.startswith("- "):
                return out
            text, _ = _strip_comment(ln.text)
            kv = _key_split(text, self.where(ln))
            if kv is None:
                raise YamlError(f"{self.where(ln)}: expected 'key: value'")
            key, rest = kv
            anchor = None
            if rest.startswith("&"):                 # «ключ: &имя» (блок ниже) или «ключ: &имя скаляр»
                m = re.fullmatch(r"&([A-Za-z0-9_-]+)(?: +(.*))?", _strip_comment(rest)[0])
                if not m:
                    raise YamlError(f"{self.where(ln)}: anchor {rest[:20]!r} is not in the subset")
                anchor, rest = m[1], (m[2] or "")
                if anchor in self.anchors:
                    raise YamlError(f"{self.where(ln)}: anchor &{anchor} repeats")
            if isinstance(key, float) or key is None or isinstance(key, bool):
                raise YamlError(f"{self.where(ln)}: key {key!r} of an unsupported type")
            if key in out:
                raise YamlError(f"{self.where(ln)}: repeated key {key!r}")
            if rest == "":
                self.i += 1
                nxt = self.skip()
                if nxt is None or nxt.indent < indent or (nxt.indent == indent and not (
                        nxt.text == "-" or nxt.text.startswith("- "))):
                    out[key] = None
                else:
                    out[key] = self.block(nxt.indent)
            else:
                out[key] = self.scalar_rest(rest, ln, indent)
            if anchor is not None:
                self.anchors[anchor] = out[key]
        return out

    def scalar_rest(self, rest, ln, indent):
        """Значение после «ключ: » или «- » в строке ln (отступ родителя indent); съедает строки значения."""
        where = self.where(ln)
        text, depth = _strip_comment(rest)
        if text[:1] == "*":                          # алиас — значение якоря целиком
            m = re.fullmatch(r"\*([A-Za-z0-9_-]+)", text)
            if not m or m[1] not in self.anchors:
                raise YamlError(f"{where}: alias {text[:20]!r} — no such anchor before it")
            self.i += 1
            return self.anchors[m[1]]
        if text[:1] in "|>":
            return self.block_scalar(text, ln, indent)
        if text[:1] in "[{":
            buf = [text]
            self.i += 1
            while depth > 0:
                if self.i >= len(self.lines):
                    raise YamlError(f"{where}: unterminated flow node")
                t, d = _strip_comment(self.lines[self.i].text)
                buf.append(t)
                depth += d
                self.i += 1
            flow = _Flow("\n".join(buf), where)
            value = flow.node()
            flow.ws()
            if flow.i != len(flow.s):
                raise YamlError(f"{where}: content after a flow node")
            return value
        if text[:1] in "\"'":
            scan = _double if text[0] == '"' else _single
            parts = [rest.rstrip(" ")]
            self.i += 1
            while True:                          # скаляр в кавычках на нескольких строках: свёртка строк YAML
                folded = parts[0]
                for k in range(1, len(parts)):
                    if parts[k] == "":
                        folded += "\n"
                    elif text[0] == '"' and folded.endswith("\\") and not folded.endswith("\\\\"):
                        folded = folded[:-1] + parts[k]
                    else:
                        folded += ("" if parts[k - 1] == "" else " ") + parts[k]
                try:
                    value, j = scan(folded, 0, where)
                    break
                except YamlError:
                    if self.i >= len(self.lines) or (self.lines[self.i].text and self.lines[self.i].indent <= indent):
                        raise
                    parts.append(self.lines[self.i].text.rstrip(" "))
                    self.i += 1
            tail, _ = _strip_comment(folded[j:])
            if tail.strip():
                raise YamlError(f"{where}: content after a quoted scalar")
            return value
        _check_plain(text, where)
        parts = [text]
        self.i += 1
        while self.i < len(self.lines):          # простой скаляр на нескольких строках
            nxt = self.lines[self.i]
            if nxt.text == "" or nxt.indent <= indent or nxt.text.startswith("#"):
                break
            t, _ = _strip_comment(nxt.text)
            if _key_split(t, self.where(nxt)) is not None:
                raise YamlError(f"{self.where(nxt)}: a mapping inside a plain scalar")
            parts.append(t)
            self.i += 1
        if len(parts) > 1:
            return " ".join(parts)
        return plain_value(text)

    def block_scalar(self, head, ln, indent):
        m = re.fullmatch(r"([|>])([-+]?)", head)
        if not m:
            raise YamlError(f"{self.where(ln)}: block scalar header {head!r} is not in the subset")
        style, chomp = m[1], m[2]
        self.i += 1
        body, col = [], None
        while self.i < len(self.lines):
            nxt = self.lines[self.i]
            if nxt.text == "":
                body.append("")
                self.i += 1
                continue
            if nxt.indent <= indent:
                break
            if col is None:
                col = nxt.indent
            if nxt.indent < col:
                break
            body.append(nxt.raw[col:])
            self.i += 1
        # пустые строки в конце принадлежат хвосту (chomping)
        tail = 0
        while body and body[-1] == "":
            body.pop()
            tail += 1
        if style == "|":
            text = "\n".join(body)
        else:
            text, prev = "", None
            for line in body:
                if prev is None:
                    text = line
                elif line == "":
                    text += "\n"
                elif prev == "" or line.startswith(" ") or (prev and prev.startswith(" ")):
                    text += ("" if prev == "" else "\n") + line
                else:
                    text += " " + line
                prev = line
        if not body:
            return ""
        if chomp == "-":
            return text
        if chomp == "+":
            return text + "\n" * (1 + tail)
        return text + "\n"


def load(text, name="yaml"):
    """Текст YAML подмножества → значение Python (dict, list, str, int, float, bool, None)."""
    if text.startswith("﻿"):
        text = text[1:]
    return _Block(text, name).parse()
