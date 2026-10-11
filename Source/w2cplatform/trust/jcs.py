"""The canonical form of what the platform signs — RFC 8785, the JSON Canonicalization Scheme, whole (ADR-0072).

One function, `jcs(v)`: the bytes a signature covers, on both sides of the wire — the course's and the product's
(`trust/jcs.go`), held to one table of vectors (`tests/testdata/canonical_json.tsv`, byte for byte the product's
`testdata/canonical_json.tsv`). A signed document (`documents.py`), a token's header and payload (`tokens.py`), a door
token's body (`door.py`), a voucher and a pledge's hello (`enroll.py`) are written by it and nothing else.

    objects   members sorted by the UTF-16 code units of their names — not by code points, as `sort_keys` sorts: a
              name outside the BMP sorts by its surrogates (U+1F600 before U+FB33); a name is a string, nothing else
    strings   UTF-8 as they are; escaped only `"`, `\\` and the control characters — `\\b \\f \\n \\r \\t` short, the
              rest `\\u00xx` — no HTML escaping, no `\\uXXXX` for what UTF-8 says; a lone surrogate has no form
    numbers   the IEEE double they are, in ES6's `Number.prototype.toString`: the shortest digits that read back as it,
              decimal from 1e-6 up to 1e21, exponent outside (`1.0` → `1`, `1e21` → `1e+21`, `1e-7` → `1e-7`,
              `-0` → `0`); an integer past a double is the double it rounds to; NaN and the infinities have no form
    no whitespace

It is not the one text of a store row (`w2cplatform/canonical.py`, `requests_body.tsv`): a row is written for a reader,
a signed thing for a verifier, and the two tables are two contracts. There is no old canon beside it (ADR-0003): a
document signed by `json.dumps(sort_keys=True)` with `<`, a float or a name outside the BMP does not verify.

What has no form raises `ValueError` (`NotCanonical`), a value that is no JSON value `TypeError`.
"""
from __future__ import annotations

import json
import math


class NotCanonical(ValueError):
    """A value RFC 8785 has no form for: NaN, an infinity, a number past a double, a string that is not UTF-8."""


def jcs(v) -> bytes:
    """The RFC 8785 form of a JSON value (`dict`, `list`/`tuple`, `str`, `int`, `float`, `bool`, `None`), UTF-8."""
    out: list[str] = []
    _write(v, out)
    text = "".join(out)
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError:
        raise NotCanonical("a string that is not UTF-8 (a lone surrogate)") from None


def _write(v, out: list) -> None:
    if v is None:
        out.append("null")
    elif v is True or v is False:
        out.append("true" if v else "false")
    elif isinstance(v, (int, float)):
        out.append(_number(v))
    elif isinstance(v, str):
        out.append(json.dumps(v, ensure_ascii=False))      # `"` `\` and the controls escaped, `\u00xx` lower case
    elif isinstance(v, dict):
        for k in v:
            if not isinstance(k, str):
                raise TypeError(f"a {type(k).__name__} is no name of a JSON object's member")
        out.append("{")
        for i, k in enumerate(sorted(v, key=_utf16)):
            out.append(("," if i else "") + json.dumps(k, ensure_ascii=False) + ":")
            _write(v[k], out)
        out.append("}")
    elif isinstance(v, (list, tuple)):
        out.append("[")
        for i, x in enumerate(v):
            if i:
                out.append(",")
            _write(x, out)
        out.append("]")
    else:
        raise TypeError(f"a {type(v).__name__} is no JSON value")


def _utf16(name: str) -> bytes:
    """The key members sort by: the name's UTF-16 code units — big-endian bytes compare as the units do."""
    return name.encode("utf-16-be", "surrogatepass")


def _number(x) -> str:
    try:
        f = float(x)                                         # an integer is the double it is (RFC 8785 §3.2.2.3)
    except OverflowError:
        raise NotCanonical(f"the number {x!r:.40} is past a double") from None
    if not math.isfinite(f):
        raise NotCanonical(f"{f!r} is no JSON number")
    if f == 0:
        return "0"                                           # -0 too
    sign = "-" if f < 0 else ""
    # `repr` is the shortest digits that read back as the double: d.ddd, d.ddde±x or ddd.d
    mant, _, exp = repr(abs(f)).partition("e")
    whole, _, frac = mant.partition(".")
    digits = (whole + frac).lstrip("0")
    point = len(whole) + int(exp or 0) - (len(whole + frac) - len(digits))   # the point after `point` digits
    digits = digits.rstrip("0")
    k, n = len(digits), point
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * -n + digits
    e = n - 1
    return sign + digits[:1] + ("." + digits[1:] if k > 1 else "") + "e" + ("+" if e >= 0 else "-") + str(abs(e))
