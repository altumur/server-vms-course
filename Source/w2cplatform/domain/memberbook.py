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
    """The holder displays every recipient row; the collection pass owns membership.

    First observation of an origin wins, unreadable keys are skipped. This door
    neither adjudicates collection conflicts nor writes while serving a GET.
    """
    from .booknames import _parse
    from w2cplatform.rows import PARSE_ERRORS
    missing, values = set(), {}
    for path in sorted(vars_.list(key + '/')):
        if '/' in path[len(key) + 1:]:
            continue
        try:
            items, _ = vars_.get(path)
            if not isinstance(items, dict):
                continue
        except PARSE_ERRORS:
            continue
        for item, raw in sorted(items.items()):
            try:
                envelope = _parse(raw)
                if not isinstance(envelope, dict):
                    raise ValueError('invalid book object')
                absent = envelope.get('missing')
                if not isinstance(absent, list) or any(not isinstance(n, str) or not n for n in absent):
                    raise ValueError('invalid missing members')
                if item == '':
                    if set(envelope) != {'missing'}:
                        raise ValueError('invalid book marker')
                    missing.update(absent)
                    continue
                if set(envelope) != {'entries', 'missing'} or not isinstance(envelope['entries'], list):
                    raise ValueError('invalid book envelope')
                entries = envelope['entries']
                for entry in entries:
                    if (not isinstance(entry, dict) or set(entry) != {'member', 'item', 'value'} or
                            any(not isinstance(entry[f], str) or not entry[f] for f in ('member', 'item')) or
                            not isinstance(entry['value'], dict)):
                        raise ValueError('invalid book origin')
            except PARSE_ERRORS:
                continue
            missing.update(absent)
            bucket = values.setdefault(item, {})
            for entry in entries:
                bucket.setdefault((entry['member'], entry['item']), entry)
    marker = {'missing': sorted(missing)}
    out = {'': json.dumps(marker)}
    out.update({item: json.dumps({'entries': [bucket[k] for k in sorted(bucket)], **marker})
                for item, bucket in sorted(values.items())})
    return out
