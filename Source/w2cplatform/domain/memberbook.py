"""Read this member's collected book at its current location (ADR-0074)."""
import json


def _holder(vars_):
    items, _ = vars_.get("domain/holder")
    if not items:
        return None
    try:
        record = json.loads(items["doc"])
        if not isinstance(record, dict) or not isinstance(record.get("holder"), str) \
                or not record["holder"] or type(record.get("term")) is not int or record["term"] <= 0:
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise ValueError("invalid holder record") from None
    return record["holder"]


def holds(vars_, member):
    holder = _holder(vars_)
    return holder is not None and holder == member


def read(vars_, key, member):
    """Holder reads its per-member result; every other member reads its carried copy.

    A copy left after a move cannot override a holder's current result. Absence of
    that result remains absence, including when an old copy exists.
    """
    return vars_.get(key + "/" + member if holds(vars_, member) else key)[0]


def members(vars_, member):
    """Read the holder's authoritative roster, or this member's verified copy."""
    from w2cplatform.canonical import parse_json
    from w2cplatform.rows import PARSE_ERRORS
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate roster field")
            out[key] = value
        return out
    try:
        if not isinstance(member, str) or not member:
            raise ValueError()
        holder = _holder(vars_)
        if holder is None:
            raise ValueError()
        key = "domain/members" if holder == member else "domain/member-list"
        items, _ = vars_.get(key)
        if items:
            json.loads(items["doc"], object_pairs_hook=unique)
        doc = parse_json(items["doc"]) if items else None
        if not isinstance(doc, dict) or type(doc.get("rev")) is not int or doc["rev"] <= 0 \
                or not isinstance(doc.get("members"), dict) \
                or any(not isinstance(n, str) or not n or "/" in n or any(ord(c) < 33 for c in n)
                       or not isinstance(v, dict) for n, v in doc["members"].items()):
            raise ValueError()
        return tuple(sorted(doc["members"]))
    except PARSE_ERRORS:
        raise ValueError("the domain has no complete roster") from None
