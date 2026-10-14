"""Read this member's collected book at its current location (ADR-0074)."""
import json


def holds(vars_, member):
    items, _ = vars_.get("domain/holder")
    if not items:
        return False
    try:
        record = json.loads(items["doc"])
        if not isinstance(record, dict) or not isinstance(record.get("holder"), str) \
                or not record["holder"] or type(record.get("term")) is not int or record["term"] <= 0:
            raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise ValueError("invalid holder record") from None
    return record["holder"] == member


def read(vars_, key, member):
    """Holder reads its per-member result; every other member reads its carried copy.

    A copy left after a move cannot override a holder's current result. Absence of
    that result remains absence, including when an old copy exists.
    """
    return vars_.get(key + "/" + member if holds(vars_, member) else key)[0]
