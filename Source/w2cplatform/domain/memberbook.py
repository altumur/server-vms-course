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


def aggregate(vars_, key):
    """Union recipient rows at the holder, deduplicating by immutable observation origin.

    Conflicting observations or a torn envelope cannot become a plausible display.
    A recipient's absent row adds no facts; missing markers remain conservative.
    """
    from .booknames import _parse
    from w2cplatform.trust.jcs import jcs
    missing, values = set(), {}
    for path in vars_.list(key + "/"):
        if "/" in path[len(key) + 1:]:
            continue
        items, _ = vars_.get(path)
        if not isinstance(items, dict) or "" not in items:
            raise ValueError("collected book has no marker")
        marker = _parse(items[""])
        if not isinstance(marker, dict) or set(marker) != {"missing"}:
            raise ValueError("invalid collected book marker")
        absent = marker["missing"]
        if not isinstance(absent, list) or any(not isinstance(n, str) or not n for n in absent):
            raise ValueError("invalid collected book missing members")
        missing.update(absent)
        for item, raw in items.items():
            if item == "":
                continue
            envelope = _parse(raw)
            if not isinstance(envelope, dict) or set(envelope) != {"entries", "missing"}                     or envelope["missing"] != absent or not isinstance(envelope["entries"], list):
                raise ValueError("inconsistent collected book envelope")
            bucket = values.setdefault(item, {})
            local = set()
            for entry in envelope["entries"]:
                if not isinstance(entry, dict) or set(entry) != {"member", "item", "value"}                         or any(not isinstance(entry[f], str) or not entry[f] for f in ("member", "item"))                         or not isinstance(entry["value"], dict):
                    raise ValueError("invalid collected book origin")
                origin = entry["member"], entry["item"]
                if origin in local or origin in bucket and jcs(bucket[origin]) != jcs(entry):
                    raise ValueError("conflicting collected book origin")
                local.add(origin)
                bucket[origin] = entry
    marker = {"missing": sorted(missing)}
    out = {"": json.dumps(marker)}
    out.update({item: json.dumps({"entries": [bucket[k] for k in sorted(bucket)], **marker})
                for item, bucket in sorted(values.items())})
    return out
