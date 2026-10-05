"""What the domain keeps in its cluster's store, key by key — `GET /domain/keys`, for the domain's page (the product's
`keysview.go`, its shape).

`GET /domain` is the domain's VIEW: one document it composes each pass for people to read (`console.DOMAIN_VIEW`).
Underneath it are the records it is made from — the list of members, the edits waiting for their cluster, the rows the
specs declare (books and kept rows, under `domain/<sub>/`) — each under its own key of the domain cluster's store, and
next to them, under the same prefix of the object store, what the members published to the domain. This is that list
as the stores hold it right now. Which key means what is the page's business (`domain.keys` of the specs, the module's
own families); the list is the store's, so a key the page has no words for still shows.

Read only, and secrets masked: a field whose name says it is one, a value sealed under any name (the domain's keys and
hashes), and a login in an address.

    {"vars": [{key, items, index}], "objects": [{key, size, age?, body}], "error"?}
"""
from __future__ import annotations

import json

from w2cplatform.rows import PARSE_ERRORS

PREFIX = "domain/"
MASK = "***"


def _value(field: str, v):
    from w2cplatform.sealing import is_sealed
    from w2cplatform.secrets import hide_in_url, is_secret_field
    if is_secret_field(field) or (isinstance(v, str) and is_sealed(v)):
        return MASK
    return hide_in_url(v) if isinstance(v, str) else v


def _masked(x):
    from w2cplatform.secrets import hide_in_url, is_secret_field
    if isinstance(x, dict):
        return {k: MASK if is_secret_field(k) else _masked(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_masked(v) for v in x]
    return hide_in_url(x) if isinstance(x, str) else x


def keys(vars_, objects, now: float) -> dict:
    """Every key under `domain/` in this cluster's stores. A store that cannot list says so in `error`, and whatever
    the other holds still comes back."""
    from w2cplatform.variables import Forbidden
    out, errors = {"vars": [], "objects": []}, []
    try:
        for k in sorted(vars_.list(PREFIX)):
            try:
                items, idx = vars_.get(k)
            except Forbidden:
                # a row this process's role may not read — the signer's keys, read by the domain's console (ADR-0032):
                # named, and nothing of it shown
                out["vars"].append({"key": k, "items": None, "withheld": "not this process's to read"})
                continue
            out["vars"].append({"key": k, "items": {f: _value(f, v) for f, v in (items or {}).items()},
                                "index": str(idx)})
    except Exception as e:                                       # noqa: BLE001 — said, and the objects still listed
        errors.append(f"variables: {e}")
    try:
        names = sorted(objects.list(PREFIX)) if objects is not None else []
    except Exception as e:                                       # noqa: BLE001
        errors.append(f"objects: {e}")
        names = []
    for k in names:
        raw = objects.get(k)
        if not raw:
            continue
        o = {"key": k, "size": len(raw)}
        try:
            body = json.loads(raw)
        except PARSE_ERRORS:
            o["body"] = raw[:512].decode("utf-8", "replace")
            out["objects"].append(o)
            continue
        o["body"] = _masked(body)
        try:
            ts = float(body.get("ts", 0)) if isinstance(body, dict) else 0.0
        except PARSE_ERRORS:
            ts = 0.0
        if ts > 0:
            o["age"] = round(now - ts, 1)
        out["objects"].append(o)
    if errors:
        out["error"] = "; ".join(errors)
    return out
