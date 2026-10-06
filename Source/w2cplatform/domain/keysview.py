"""What the domain keeps in its cluster's store, key by key — `GET /domain/keys`, for the domain's page (the product's
`keysview.go`, its shape).

`GET /domain` is the domain's VIEW: one document it composes each pass for people to read (`console.DOMAIN_VIEW`).
Underneath it are the records it is made from — the list of members, the edits waiting for their cluster, the rows the
specs declare (books and kept rows, under `domain/<sub>/`) — each under its own key of the domain cluster's store, and
next to them, under the same prefix of the object store, what the members published to the domain. This is that list
as the stores hold it right now. Which key means what is the page's business (`domain.keys` of the specs, the module's
own families); the list is the store's, so a key the page has no words for still shows.

IDENTIFIERS AND PUBLIC HALVES, NOTHING ELSE («Архитектор», 2026-10-06). A row is shown by its key, its index and the
NAMES of its fields; an object by its key, its size and its age. No value, no body. Masking by name was not enough: a
book row (`domain/<sub>/<book>/<member>`) holds a field whose value is a document, and the token inside it,
`token_secret`, came out whole; an object's body the same way. What the platform cannot read the meaning of it does
not show — the content of a book comes through its own route to come (`GET /domain/<sub>/books/<book>`, the fields its
spec declares to show; a separate ADR), never through this list.

The one exception is the trust the domain publishes on purpose: the key set (`domain/keys` — the token keys, the
root's public key, the signed document carrying them and the issuing certificates), the root a member pinned
(`domain/root`), a member's own public keys (`domain/member-key` — its `seed_secret` never), and a cluster's identity
certificate (`domain/ldevid/<cluster>`). Those fields, named in `PUBLIC` below, come with their values (`public`) —
and even there a value sealed, or a document carrying a field named a secret or a sealed value, is not shown. A row
this process's role may not read (the signer's keys, ADR-0032) is named and `withheld`.

    {"vars": [{key, index, fields, public?} | {key, withheld}], "objects": [{key, size, age?}], "error"?}
"""
from __future__ import annotations

import json

from w2cplatform.rows import PARSE_ERRORS

PREFIX = "domain/"

# The rows holding public halves, and which of their fields are: `(key, or a prefix ending in "/"; fields)`. Exact
# names, not a pattern — a field added to one of these rows later stays a name until it is put here.
PUBLIC = (
    ("domain/keys", lambda f: f in ("current", "doc") or f.startswith(("key:", "retire:"))),   # `KeySet.to_items`, `DomainRoot.key_set`
    ("domain/root", lambda f: f == "pub"),                                                      # `agent.ROOT_PATH`
    ("domain/member-key", lambda f: f in ("pub", "seal_pub")),                                  # `memberkey.ROW`
    ("domain/ldevid/", lambda f: f in ("cert", "chain")),                                       # `agent.LDEVID_PATH`
)


def _public_field(key: str, field: str) -> bool:
    return any((key.startswith(k) if k.endswith("/") else key == k) and ok(field) for k, ok in PUBLIC)


def _carries_secret(x) -> bool:
    """Whether a value, or the document in it, holds a sealed value or a field named a secret — anywhere."""
    from w2cplatform.sealing import is_sealed
    from w2cplatform.secrets import is_secret_field
    if isinstance(x, dict):
        return any(is_secret_field(str(k)) or _carries_secret(v) for k, v in x.items())
    if isinstance(x, list):
        return any(_carries_secret(v) for v in x)
    if isinstance(x, str):
        if is_sealed(x):
            return True
        t = x.strip()
        if t[:1] in ("{", "["):
            try:
                return _carries_secret(json.loads(t))
            except PARSE_ERRORS:
                return False
    return False


def _row(key: str, items: dict | None, idx) -> dict:
    items = items or {}
    out = {"key": key, "index": str(idx), "fields": sorted(items)}
    public = {f: v for f, v in items.items() if _public_field(key, f) and isinstance(v, str) and not _carries_secret(v)}
    if public:
        out["public"] = public
    return out


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
                out["vars"].append({"key": k, "withheld": "not this process's to read"})
                continue
            out["vars"].append(_row(k, items, idx))
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
        try:                                                     # read for its `ts` only: the body is not shown
            body = json.loads(raw)
            ts = float(body.get("ts", 0)) if isinstance(body, dict) else 0.0
        except PARSE_ERRORS:
            ts = 0.0
        if ts > 0:
            o["age"] = round(now - ts, 1)
        out["objects"].append(o)
    if errors:
        out["error"] = "; ".join(errors)
    return out
