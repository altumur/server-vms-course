"""Deterministic YAML subset for as-built snapshots (stdlib only).

The writer emits one fixed form: block mappings with sorted keys, block
sequences, strings always as JSON double-quoted scalars, integers, booleans,
null, and `[]` / `{}` for empty collections. The reader accepts exactly that
form, so snapshots round-trip without a YAML library.
"""

import json

__all__ = ["dump", "load"]


def _scalar(v):
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    raise TypeError("unsupported scalar %r" % (v,))


def _emit(v, indent, out):
    pad = " " * indent
    if isinstance(v, dict):
        # The snapshot header comes first; every other key is sorted.
        for k in sorted(v, key=lambda k: (k != "header", k)):
            val = v[k]
            key = k if _plain_key(k) else json.dumps(k, ensure_ascii=False)
            if isinstance(val, (dict, list)) and val:
                out.append("%s%s:" % (pad, key))
                _emit(val, indent + 2, out)
            elif isinstance(val, dict):
                out.append("%s%s: {}" % (pad, key))
            elif isinstance(val, list):
                out.append("%s%s: []" % (pad, key))
            else:
                out.append("%s%s: %s" % (pad, key, _scalar(val)))
    elif isinstance(v, list):
        for item in v:
            if isinstance(item, dict) and item:
                sub = []
                _emit(item, indent + 2, sub)
                sub[0] = pad + "- " + sub[0][indent + 2:]
                out.extend(sub)
            elif isinstance(item, list) and item:
                raise TypeError("nested lists are not part of the subset")
            elif isinstance(item, (dict, list)):
                out.append("%s- %s" % (pad, "{}" if isinstance(item, dict) else "[]"))
            else:
                out.append("%s- %s" % (pad, _scalar(item)))
    else:
        raise TypeError("top level must be a mapping")


def _plain_key(k):
    return bool(k) and all(c.isalnum() or c in "_-." for c in k) and not k[0].isdigit()


def dump(doc):
    """Return the YAML text of doc (a dict); ends with a newline."""
    if not isinstance(doc, dict):
        raise TypeError("top level must be a mapping")
    out = []
    _emit(doc, 0, out)
    return "\n".join(out) + "\n"


def _parse_scalar(s):
    s = s.strip()
    if s == "null":
        return None
    if s == "true":
        return True
    if s == "false":
        return False
    if s == "[]":
        return []
    if s == "{}":
        return {}
    if s.startswith('"'):
        return json.loads(s)
    return int(s)


def _split_key(text):
    if text.startswith('"'):
        dec = json.JSONDecoder()
        key, end = dec.raw_decode(text)
        rest = text[end:]
        assert rest.startswith(":"), text
        return key, rest[1:].strip()
    key, _, rest = text.partition(":")
    return key, rest.strip()


def load(text):
    """Parse YAML text written by dump."""
    lines = [l for l in text.split("\n") if l.strip()]
    pos = 0

    def indent_of(l):
        return len(l) - len(l.lstrip(" "))

    def block(ind):
        nonlocal pos
        if lines[pos].lstrip().startswith("- ") or lines[pos].strip() == "-":
            return seq(ind)
        return mapping(ind)

    def mapping(ind, first=None):
        nonlocal pos
        d = {}
        while pos < len(lines):
            l = lines[pos]
            if first is None:
                if indent_of(l) != ind or l.lstrip().startswith("- "):
                    break
                body = l[ind:]
            else:
                body, first = first, None
            pos += 1
            key, rest = _split_key(body)
            if rest == "":
                d[key] = block(indent_of(lines[pos]))
            else:
                d[key] = _parse_scalar(rest)
        return d

    def seq(ind):
        nonlocal pos
        items = []
        while pos < len(lines):
            l = lines[pos]
            if indent_of(l) != ind or not l.lstrip().startswith("- "):
                break
            body = l[ind + 2:]
            if body.startswith('"') or body in ("null", "true", "false", "[]", "{}") or body.lstrip("-").isdigit():
                items.append(_parse_scalar(body))
                pos += 1
            else:
                items.append(mapping(ind + 2, first=body))
        return items

    return mapping(0)
