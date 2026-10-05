"""The one text of a JSON value in a store row (the architect, 2026-10-05; the product's `CanonicalJSON`, checked byte for
byte against it by `testdata/requests_body.tsv`). Two writers of the same value wrote two rows — `json.dumps` with its
spaces, `str()` with Python's words (`True`, `None`, `5.0`), keys in the order a body happened to bring them — and a
reader in Go and one in Python disagreed on what a row said. Every JSON value a row holds is parsed and written here:

    canonical_json(v)  compact (`,` `:` and no space), keys sorted, UTF-8 as it is (no `\\u` escape of a letter; a
                       control character as `json.dumps` writes it, U+2028 and `<>&/` as they are); a number by
                       `number_text`, a key that is one as its text; `NaN` and the infinities raise `ValueError`
    number_text(x)     an integer as its digits, exactly (JSON carries `10**30` as it is; never through a float); a
                       whole-valued float as integer digits (`5.0` → `5`, `1e20` → `100000000000000000000`); any other
                       in the shortest decimal that reads back as the same float, no exponent (`1e-07` → `0.0000001`);
                       zero has no sign (`-0.0` and `-0` → `0`: equal values, one text — the architect, 2026-10-06)
    parse_json(text)   `json.loads`, refusing what is not JSON though Python reads it — `NotJson` (`NaN`, `Infinity`,
                       a lone surrogate), `NotNumber` (`1e999`); an integer exactly (`exact_int`)
    field_text(v)      a value as one field of a row: a string as it is (the schema tells a word from a number), the
                       rest `canonical_json` (`true`, `5`, `{"a":1}`); `None` is no text — the field is absent

What raises is `ValueError` (or `RecursionError` for a value nested past what is read): `rows.PARSE_ERRORS` holds both.
"""
from __future__ import annotations

import decimal
import json
import math

_CONTEXT = decimal.Context(prec=40)                 # a float's shortest repr is 17 digits at most: nothing is rounded


def number_text(x) -> str:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise TypeError(f"{x!r:.40} is not a number")
    if isinstance(x, int):
        return str(x)
    if not math.isfinite(x):
        raise ValueError(f"{x!r} is no JSON number")
    if x == 0:
        return "0"                                  # `-0.0` is `0`: equal values write one text
    return format(decimal.Decimal(repr(x)).normalize(_CONTEXT), "f")


def _write(v, out: list) -> None:
    if v is None:
        out.append("null")
    elif v is True or v is False:
        out.append("true" if v else "false")
    elif isinstance(v, (int, float)):
        out.append(number_text(v))
    elif isinstance(v, str):
        out.append(json.dumps(v, ensure_ascii=False))
    elif isinstance(v, dict):
        named = sorted(((_key(k), x) for k, x in v.items()), key=lambda p: p[0])   # `1` is "1", as `json.dumps` says
        out.append("{")
        for i, (k, x) in enumerate(named):
            out.append(("," if i else "") + json.dumps(k, ensure_ascii=False) + ":")
            _write(x, out)
        out.append("}")
    elif isinstance(v, (list, tuple)):
        out.append("[")
        for i, x in enumerate(v):
            if i:
                out.append(",")
            _write(x, out)
        out.append("]")
    else:
        raise TypeError(f"{type(v).__name__} is no JSON value")


def _key(k) -> str:
    if isinstance(k, str):
        return k
    if k is None or isinstance(k, (bool, int, float)):
        return canonical_json(k)
    raise TypeError(f"{type(k).__name__} is no JSON object's key")


def canonical_json(v) -> str:
    out: list[str] = []
    _write(v, out)
    return "".join(out)


# What a refusal is, by its kind — the words of the shared table (`requests_body.tsv`, column `fault`; the architect with
# «Паритет», 2026-10-06), the same on both sides: each a `ValueError`, so `rows.PARSE_ERRORS` holds them all.
class Fault(ValueError):
    fault = ""


class NotJson(Fault):
    fault = "not_json"          # not JSON at all: `NaN`, `Infinity`, a cut text, a lone surrogate


class NotNumber(Fault):
    fault = "not_number"        # a number JSON writes and no float holds: `1e400`


class TooLong(Fault):
    fault = "too_long"          # past the schema's `maxLength` of the written text, or `JSON_CEILING` in bytes


def _no_constant(name: str):
    raise NotJson(f"{name} is no JSON")


def exact_int(text: str):
    """An integer literal as its value, exactly — never through a float."""
    return int(text)


def _finite_float(text: str) -> float:
    f = float(text)
    if not math.isfinite(f):
        raise NotNumber(f"{text[:40]} is past what a JSON number holds here")
    return f


def _whole_text(v):
    """A string is Unicode text: `\\ud800` alone (JSON's escape lets one through) is no character, and no UTF-8."""
    if isinstance(v, str):
        if any("\ud800" <= c <= "\udfff" for c in v):
            raise NotJson("a lone surrogate is no character")
    elif isinstance(v, dict):
        for k, x in v.items():
            _whole_text(k)
            _whole_text(x)
    elif isinstance(v, list):
        for x in v:
            _whole_text(x)
    return v


def parse_json(text):
    try:
        if isinstance(text, (bytes, bytearray)):
            text = bytes(text).decode("utf-8")
        v = json.loads(text, parse_constant=_no_constant, parse_float=_finite_float, parse_int=exact_int)
    except Fault:
        raise
    except ValueError as e:                             # `JSONDecodeError`, `UnicodeDecodeError`
        raise NotJson(str(e)) from None
    return _whole_text(v)


def field_text(v) -> str | None:
    if v is None:
        return None
    return v if isinstance(v, str) else canonical_json(v)
