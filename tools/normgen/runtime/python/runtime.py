# CEL subset runtime for gen_checks.py output (ADR-0120, item 2(a)).
# The generator embeds this whole file into each Python module; table code calls only these functions.
# CEL values are JSON-decoded Python dict, list, str, int, float, bool, None, plus CelType/CelError.
# A CEL error is a CelError value, not an exception, allowing false&&error=false and true||error=true.
# Semantics are checked against check_tables.py's cel-expr-python oracle.


class CelError:
    """CEL error value, corresponding to the oracle's error status."""
    __slots__ = ("msg",)

    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return f"CelError({self.msg!r})"


class CelType:
    """CEL type value: type() result and map, list, string, int, double, bool, null_type, type names."""
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


_TYPES = {name: CelType(name) for name in ("bool", "int", "double", "string", "list", "map", "null_type", "type")}


def _no(op, *args):
    return CelError(f"no matching overload: {op}({', '.join(_kind(a) for a in args)})")


def _kind(v):
    t = type(v)
    if t is bool:
        return "bool"
    if t is int:
        return "int"
    if t is float:
        return "double"
    if t is str:
        return "string"
    if t is list:
        return "list"
    if t is dict:
        return "map"
    if v is None:
        return "null_type"
    if t is CelType:
        return "type"
    if t is CelError:
        return "error"
    return "unknown"


def _is_num(v):
    t = type(v)
    return t is int or t is float


def _numcmp(a, b):
    """Return -1, 0, 1 or None for incomparable/NaN. Compare ints exactly; mixed int/double via double, like cel-cpp."""
    if type(a) is int and type(b) is int:
        return (a > b) - (a < b)
    x, y = float(a), float(b)
    if x < y:
        return -1
    if x > y:
        return 1
    if x == y:
        return 0
    return None


def _eqv(a, b):
    """Compare non-error values with CEL heterogeneous equality."""
    if _is_num(a) and _is_num(b):
        return _numcmp(a, b) == 0
    ka, kb = _kind(a), _kind(b)
    if ka != kb:
        return False
    if ka == "list":
        return len(a) == len(b) and all(_eqv(x, y) for x, y in zip(a, b))
    if ka == "map":
        return len(a) == len(b) and all(k in b and _eqv(v, b[k]) for k, v in a.items())
    if ka == "type":
        return a.name == b.name
    if ka == "null_type":
        return True
    return a == b


def _eq(a, b):
    if type(a) is CelError:
        return a
    if type(b) is CelError:
        return b
    return _eqv(a, b)


def _ne(a, b):
    r = _eq(a, b)
    return r if type(r) is CelError else not r


def _order(op, a, b):
    if type(a) is CelError:
        return a
    if type(b) is CelError:
        return b
    if _is_num(a) and _is_num(b):
        c = _numcmp(a, b)
    elif type(a) is str and type(b) is str or type(a) is bool and type(b) is bool:
        c = (a > b) - (a < b)
    else:
        return _no(op, a, b)
    if c is None:
        return False
    return {"<": c < 0, "<=": c <= 0, ">": c > 0, ">=": c >= 0}[op]


def _lt(a, b):
    return _order("<", a, b)


def _le(a, b):
    return _order("<=", a, b)


def _gt(a, b):
    return _order(">", a, b)


def _ge(a, b):
    return _order(">=", a, b)


def _in(x, c):
    if type(x) is CelError:
        return x
    if type(c) is CelError:
        return c
    if type(c) is list:
        return any(_eqv(x, el) for el in c)
    if type(c) is dict:
        # Map keys may be string, bool, int, double; JSON keys are strings, so other types miss. Other key types error.
        if type(x) is str:
            return x in c
        if type(x) in (bool, int, float):
            return False
        return _no("in", x, c)
    return _no("in", x, c)


def _not(v):
    if type(v) is bool:
        return not v
    if type(v) is CelError:
        return v
    return _no("!", v)


def _or(a, b):
    """Evaluate a||b when a is not true; true absorbs an error on either side."""
    if b is True:
        return True
    if a is False and b is False:
        return False
    if type(a) is CelError:
        return a
    if type(b) is CelError:
        return b
    return _no("||", a, b)


def _and(a, b):
    """Evaluate a&&b when a is not false; false absorbs an error on either side."""
    if b is False:
        return False
    if a is True and b is True:
        return True
    if type(a) is CelError:
        return a
    if type(b) is CelError:
        return b
    return _no("&&", a, b)


def _sel(v, field):
    if type(v) is dict:
        if field in v:
            return v[field]
        return CelError(f"no such key: {field}")
    if type(v) is CelError:
        return v
    return CelError(f"select .{field} on {_kind(v)}")


def _has(v, field):
    if type(v) is dict:
        return field in v
    if type(v) is CelError:
        return v
    return CelError(f"has(.{field}) on {_kind(v)}")


def _index(v, k):
    if type(v) is CelError:
        return v
    if type(k) is CelError:
        return k
    if type(v) is list:
        if type(k) is int:
            i = k
        elif type(k) is float and abs(k) < 2.0 ** 63 and k.is_integer():
            i = int(k)
        else:
            return CelError(f"index: expected integer, got {_kind(k)}")
        if 0 <= i < len(v):
            return v[i]
        return CelError(f"index {i} out of range {len(v)}")
    if type(v) is dict:
        if type(k) is str and k in v:
            return v[k]
        return CelError(f"no such key: {k!r}")
    return CelError(f"index on {_kind(v)}")


def _size(v):
    t = type(v)
    if t is str or t is list or t is dict:
        return len(v)
    if t is CelError:
        return v
    return _no("size", v)


def _string(v):
    t = type(v)
    if t is str:
        return v
    if t is bool:
        return "true" if v else "false"
    if t is int:
        return str(v)
    if t is float:
        return "%.17g" % v
    if t is CelError:
        return v
    return _no("string", v)


def _add(a, b):
    if type(a) is CelError:
        return a
    if type(b) is CelError:
        return b
    ta, tb = type(a), type(b)
    if ta is str and tb is str or ta is list and tb is list:
        return a + b
    if ta is int and tb is int:
        r = a + b
        if -2 ** 63 <= r < 2 ** 63:
            return r
        return CelError("integer overflow")
    if ta is float and tb is float:
        return a + b
    return _no("+", a, b)


def _type(v):
    if type(v) is CelError:
        return v
    return _TYPES.get(_kind(v), CelError("type of unknown value"))


def _starts(s, p):
    if type(s) is CelError:
        return s
    if type(p) is CelError:
        return p
    if type(s) is str and type(p) is str:
        return s.startswith(p)
    return _no("startsWith", s, p)


def _matches(s, rx):
    if type(s) is str:
        return rx.search(s) is not None
    if type(s) is CelError:
        return s
    return _no("matches", s)


def _list(*vals):
    for v in vals:
        if type(v) is CelError:
            return v
    return list(vals)


def _map(keys, *vals):
    for v in vals:
        if type(v) is CelError:
            return v
    return dict(zip(keys, vals))


def _range_err(r):
    return r if type(r) is CelError else _no("<iter_range>", r)


def _pred_err(err, b):
    """Remember the first exists error; a non-bool result is also an error."""
    if err is not None:
        return err
    return b if type(b) is CelError else _no("||", False, b)


def _status(v):
    if v is True:
        return "true"
    if v is False:
        return "false"
    return "error"
