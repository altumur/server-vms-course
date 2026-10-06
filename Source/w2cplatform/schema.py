"""JSON Schema, the part a spec writes (the boundary's step 6, ГРАНИЦА-ПЛАТФОРМЫ-И-ПОДСИСТЕМЫ.md §4 and the owner's decision
3: «исполнимость проверяется JSON Schema из YAML»). What a field of a row, a row of a table or a request's body may be
is said in the subsystem's spec as a schema, and the platform checks it at the door — the words of the refusal are the
schema's, never a subsystem's code (it was a controller of one subsystem's own, for its rows).
What only the subsystem can know — that unit 7 cannot do what a row asks of it — is its worker's, said in its heartbeat.

The keywords (draft 2020-12, their meaning unchanged; anything else in a schema is refused at load, so a typo is not a
rule that silently holds nothing):

    type                 object, array, string, integer, number, boolean, null — or a list of them
    enum, const
    properties, required, additionalProperties (true, false or a schema), propertyNames, minProperties, maxProperties
    items (a schema), minItems, maxItems, uniqueItems
    minLength, maxLength, pattern (searched, as the standard says: anchor it to mean the whole; RE2 only, `re2_fault`)
    minimum, maximum, exclusiveMinimum, exclusiveMaximum, multipleOf
    allOf, anyOf, oneOf, not, if/then/else
    title, description, $comment   words for a reader, checked nothing

`check(schema, value, where)` raises `Invalid` with where it failed and what was wanted, in words.
"""
from __future__ import annotations

import math
import re

KEYWORDS = {"type", "enum", "const", "properties", "required", "additionalProperties", "propertyNames", "minProperties",
            "maxProperties", "items", "minItems", "maxItems", "uniqueItems", "minLength", "maxLength", "pattern", "minimum",
            "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "allOf", "anyOf", "oneOf", "not", "if",
            "then", "else", "title", "description", "$comment"}
TYPES = ("object", "array", "string", "integer", "number", "boolean", "null")
DEPTH = 32                                   # a schema nested past this is no schema anybody wrote by hand


class Invalid(ValueError):
    """What a value is not, and where in it; `keyword` — the schema's word that refused it (`maxLength`, …)."""

    def __init__(self, msg: str, keyword: str = ""):
        super().__init__(msg)
        self.keyword = keyword


def load(schema, what: str, depth: int = 0):
    """`schema` checked as a schema — every keyword known, every sub-schema a schema — or a `ValueError` naming `what`."""
    if depth > DEPTH:
        raise ValueError(f"{what}: a schema nested past {DEPTH} levels")
    if isinstance(schema, bool):
        return schema
    if not isinstance(schema, dict):
        raise ValueError(f"{what}: a schema is a map of keywords, not {schema!r}")
    unknown = sorted(set(schema) - KEYWORDS)
    if unknown:
        raise ValueError(f"{what}: {', '.join(unknown)} — not a keyword the platform reads ({', '.join(sorted(KEYWORDS))})")
    t = schema.get("type")
    for x in (t if isinstance(t, list) else [t] if t is not None else []):
        if x not in TYPES:
            raise ValueError(f"{what}: type {x!r} is none of {', '.join(TYPES)}")
    for k in ("properties",):
        if k in schema:
            if not isinstance(schema[k], dict):
                raise ValueError(f"{what}: `{k}` is a map of schemas")
            for n, sub in schema[k].items():
                load(sub, f"{what}.{n}", depth + 1)
    for k in ("additionalProperties", "propertyNames", "items", "not", "if", "then", "else"):
        if k in schema:
            load(schema[k], f"{what}/{k}", depth + 1)
    for k in ("allOf", "anyOf", "oneOf"):
        if k in schema:
            if not isinstance(schema[k], list) or not schema[k]:
                raise ValueError(f"{what}: `{k}` is a non-empty list of schemas")
            for i, sub in enumerate(schema[k]):
                load(sub, f"{what}/{k}[{i}]", depth + 1)
    if "required" in schema and not (isinstance(schema["required"], list) and all(isinstance(x, str) for x in schema["required"])):
        raise ValueError(f"{what}: `required` is a list of names")
    if "enum" in schema and not isinstance(schema["enum"], list):
        raise ValueError(f"{what}: `enum` is a list")
    if "pattern" in schema:
        try:
            re.compile(schema["pattern"])
        except (re.error, TypeError) as e:
            raise ValueError(f"{what}: pattern {schema['pattern']!r} is no regular expression ({e})") from None
        fault = re2_fault(schema["pattern"])
        if fault:
            raise ValueError(f"{what}: pattern {schema['pattern']!r} {fault}")
    for k in ("minLength", "maxLength", "minItems", "maxItems", "minProperties", "maxProperties"):
        if k in schema and (isinstance(schema[k], bool) or not isinstance(schema[k], int) or schema[k] < 0):
            raise ValueError(f"{what}: `{k}` is a whole number")
    for k in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"):
        if k in schema and (isinstance(schema[k], bool) or not isinstance(schema[k], (int, float))):
            raise ValueError(f"{what}: `{k}` is a number")
    return schema


# A REGULAR EXPRESSION OF A SPEC IS A SUBSET OF RE2 (the architect, 6 Oct). One spec for course and product (ADR 0019),
# and the product's loader is Go's `regexp` — RE2; Python's `re` reads more and says nothing. What Go will not compile
# or reads otherwise the course refuses at load (the strict loader, ADR 0012). Go does not compile: lookaround, a
# backreference (`\1`…`\9`, `\g<…>`, `(?P=name)`), an atomic group, a conditional, a possessive quantifier, `\Z` and `\G`,
# an inline flag but `i`, `m`, `s`, `U`, a comment `(?#…)`, `\u`/`\U`/`\N{…}`, an escaped non-ASCII character, `[\b]`, a
# one-digit octal in a class, a count past 1000. Go reads otherwise: `[:` in a class (a POSIX class), `{,n}` (characters).
# The scan walks the pattern as the parser does: `\x` is one escape, `[…]` one class, so `\(?=` and `[(?=]` stand.
_RE2_FLAGS = set("imsU")
_COUNT = re.compile(r"\{(\d*)(,?)(\d*)\}")
_RE2_GROUPS = (("(?<=", "a lookbehind"), ("(?<!", "a negative lookbehind"), ("(?=", "a lookahead"),
               ("(?!", "a negative lookahead"), ("(?P=", "a named backreference"), ("(?>", "an atomic group"),
               ("(?(", "a conditional"), ("(?#", "a comment"))


def re2_fault(p) -> str:
    """'' for a pattern Go's RE2 compiles as Python reads it, else the words of what in it does not: the construct and
    where it stands. Run after `re.compile` succeeded, so what Python refuses is Python's words."""
    if not isinstance(p, str):
        return ""
    n, i, klass = len(p), 0, False

    def no(what: str, at: int, text: str, apart: bool = False) -> str:
        how = "reads it otherwise than Python" if apart else "does not compile it"
        return (f"holds {what} `{text}` at {at}: Go's RE2 {how}, and what Go will not compile or reads otherwise the "
                f"course refuses at load — one spec for course and product (ADR 0019, 0012)")

    while i < n:
        c = p[i]
        if c == "\\" and i + 1 < n:
            e = p[i + 1]
            if e.isdigit() and e != "0":
                if len(p[i + 1:i + 4]) == 3 and all(ch in "01234567" for ch in p[i + 1:i + 4]):
                    i += 4                              # `\123`: an octal character to both
                    continue
                if not klass:
                    return no("a backreference", i, p[i:i + 2])
                if e in "1234567" and p[i + 2:i + 3] in tuple("01234567"):
                    i += 3                              # `[\12]`: two octal digits, a character to both
                    continue
                return no("a one-digit octal escape in a class", i, p[i:i + 2])
            if e == "g":
                return no("a backreference", i, p[i:p.find(">", i) + 1 or i + 2])
            if e in "ZG":
                return no("an anchor RE2 lacks (it has `\\z`)", i, p[i:i + 2])
            if e in "uUN":
                return no("an escape RE2 lacks (it writes `\\x{…}`)", i, p[i:i + 2])
            if klass and e == "b":
                return no("a backspace escape in a class", i, p[i:i + 2])
            if ord(e) > 127:
                return no("an escaped non-ASCII character", i, p[i:i + 2])
            i += 2
            continue
        if klass:
            if c == "]":
                klass = False
            elif c == "[" and p[i + 1:i + 2] == ":":
                return no("a POSIX class to Go, characters to Python", i, p[i:i + 2], apart=True)
            i += 1
            continue
        if c == "[":
            klass, i = True, i + 1
            if p[i:i + 1] == "^":
                i += 1
            if p[i:i + 1] == "]":
                i += 1                                  # `[]…]`: the first `]` is a character
            continue
        if c == "(" and p[i + 1:i + 2] == "?":
            for start, what in _RE2_GROUPS:
                if p.startswith(start, i):
                    return no(what, i, start)
            j = i + 2
            while j < n and (p[j].isalpha() or p[j] == "-"):
                j += 1
            flags = p[i + 2:j]
            if flags and p[j:j + 1] in (":", ")") and not flags.startswith("P"):
                stray = [f for f in flags if f != "-" and f not in _RE2_FLAGS]
                if stray:
                    return no("an inline flag RE2 lacks (it reads i, m, s, U)", i, p[i:j + 1])
            i += 2
            continue
        if c == "{":
            m = _COUNT.match(p, i)
            if m and (m.group(1) or m.group(2)):        # `{}` is two characters to both
                lo, comma, hi = m.groups()
                if not lo and comma:
                    return no("a count with no lower bound (Go reads the characters; write `{0,n}`)", i, m.group(),
                              apart=True)
                if any(x and int(x) > 1000 for x in (lo, hi)):
                    return no("a count past RE2's 1000", i, m.group())
                if p[m.end():m.end() + 1] == "+":
                    return no("a possessive quantifier", i, m.group() + "+")
                i = m.end()
                continue
        if c in "*+?" and p[i + 1:i + 2] == "+":
            return no("a possessive quantifier", i, p[i:i + 2])
        i += 1
    return ""


def _type_of(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        if not math.isfinite(v):
            return "non-finite"                            # `NaN`, `Infinity`: JSON has neither, Python's reader takes both
        return "integer" if v.is_integer() else "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, (list, tuple)):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def _is(t: str, v) -> bool:
    got = _type_of(v)
    return got == t or (t == "number" and got == "integer")


def _shown(v) -> str:
    s = repr(v)
    return s if len(s) <= 60 else s[:57] + "…"


def _same(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b if isinstance(a, bool) and isinstance(b, bool) else False
    return a == b


# What a `not` refuses, said by what it names: a key it may not have, a form it may not take, a value it may not be.
def _what_not(at: str, sub, v) -> str:
    if isinstance(sub, dict):
        if set(sub) == {"required"}:
            return f"{at} may not have {', '.join(repr(k) for k in sub['required'])}"
        if set(sub) == {"pattern"}:
            return f"{at} may not match {sub['pattern']!r}"
        if set(sub) <= {"const", "enum"}:
            return f"{at} may not be {_shown(v)}"
    return f"{at} is what it may not be"


def check(schema, v, where: str = "") -> None:
    """Raise `Invalid` when `v` does not fit `schema` — the first thing that does not, said with where."""
    at = where or "the value"
    if schema is True:
        return
    if schema is False:
        raise Invalid(f"{at}: nothing is allowed here")
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_is(x, v) for x in types):
            raise Invalid(f"{at} is {' or '.join(types)}, not {_type_of(v)} {_shown(v)}")
    if "const" in schema and not _same(v, schema["const"]):
        raise Invalid(f"{at} is {_shown(schema['const'])}, not {_shown(v)}")
    if "enum" in schema and not any(_same(v, e) for e in schema["enum"]):
        raise Invalid(f"{at} is one of {', '.join(_shown(e) for e in schema['enum'])}, not {_shown(v)}")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in schema and v < schema["minimum"]:
            raise Invalid(f"{at} is at least {schema['minimum']}, not {v}")
        if "maximum" in schema and v > schema["maximum"]:
            raise Invalid(f"{at} is at most {schema['maximum']}, not {v}")
        if "exclusiveMinimum" in schema and v <= schema["exclusiveMinimum"]:
            raise Invalid(f"{at} is more than {schema['exclusiveMinimum']}, not {v}")
        if "exclusiveMaximum" in schema and v >= schema["exclusiveMaximum"]:
            raise Invalid(f"{at} is less than {schema['exclusiveMaximum']}, not {v}")
        if "multipleOf" in schema and schema["multipleOf"] and not math.isclose(v / schema["multipleOf"], round(v / schema["multipleOf"])):
            raise Invalid(f"{at} is a multiple of {schema['multipleOf']}, not {v}")
    if isinstance(v, str):
        if "minLength" in schema and len(v) < schema["minLength"]:
            raise Invalid(f"{at} is at least {schema['minLength']} characters" if schema["minLength"] > 1 else f"{at} is not empty")
        if "maxLength" in schema and len(v) > schema["maxLength"]:
            raise Invalid(f"{at} is at most {schema['maxLength']} characters, not {len(v)}", "maxLength")
        if "pattern" in schema and not re.search(schema["pattern"], v):
            raise Invalid(f"{at} does not match {schema['pattern']!r}")
    if isinstance(v, (list, tuple)):
        if "minItems" in schema and len(v) < schema["minItems"]:
            raise Invalid(f"{at} has at least {schema['minItems']} entr{'y' if schema['minItems'] == 1 else 'ies'}, not {len(v)}")
        if "maxItems" in schema and len(v) > schema["maxItems"]:
            raise Invalid(f"{at} has at most {schema['maxItems']} entr{'y' if schema['maxItems'] == 1 else 'ies'}, not {len(v)}")
        if schema.get("uniqueItems") and len({repr(x) for x in v}) != len(v):
            raise Invalid(f"{at} has no entry twice")
        if "items" in schema:
            for i, x in enumerate(v):
                check(schema["items"], x, f"{at}[{i}]")
    if isinstance(v, dict):
        if "minProperties" in schema and len(v) < schema["minProperties"]:
            raise Invalid(f"{at} has at least {schema['minProperties']} key(s)")
        if "maxProperties" in schema and len(v) > schema["maxProperties"]:
            raise Invalid(f"{at} has at most {schema['maxProperties']} key(s)")
        for k in schema.get("required", ()):
            if k not in v:
                raise Invalid(f"{at} needs {k!r}")
        props = schema.get("properties", {})
        for k, x in v.items():
            if "propertyNames" in schema:
                check(schema["propertyNames"], k, f"{at}: the key {k!r}")
            if k in props:
                check(props[k], x, f"{at}.{k}")
            elif "additionalProperties" in schema:
                extra = schema["additionalProperties"]
                if extra is False:
                    raise Invalid(f"{at} has no key {k!r} — it takes {', '.join(sorted(props)) or 'none'}")
                check(extra, x, f"{at}.{k}")
    for sub in schema.get("allOf", ()):
        check(sub, v, where)
    if "anyOf" in schema:
        whys = []
        for sub in schema["anyOf"]:
            try:
                check(sub, v, where)
                break
            except Invalid as e:
                whys.append(str(e))
        else:
            raise Invalid(f"{at} fits none of what it may be: " + "; or ".join(dict.fromkeys(whys)))
    if "oneOf" in schema:
        fits = 0
        whys = []
        for sub in schema["oneOf"]:
            try:
                check(sub, v, where)
                fits += 1
            except Invalid as e:
                whys.append(str(e))
        if fits != 1:
            raise Invalid(f"{at} fits {'none' if not fits else 'more than one'} of what it may be"
                          + (": " + "; or ".join(dict.fromkeys(whys)) if not fits else ""))
    if "not" in schema:
        try:
            check(schema["not"], v, where)
        except Invalid:
            pass
        else:
            raise Invalid(_what_not(at, schema["not"], v))
    if "if" in schema:
        try:
            check(schema["if"], v, where)
            ok = True
        except Invalid:
            ok = False
        branch = schema.get("then" if ok else "else")
        if branch is not None:
            check(branch, v, where)
