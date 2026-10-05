"""A signed document: a JSON object with the key that signed it (`kid`) and the signature (`sig`) beside its fields.

What the domain publishes and a member must believe whoever handed it over — the key set the root signs, the holder
record, the shared settings, the holder's backup — is one of these. A copy is believed by its signature against the key
set the member holds, never by the road it came by.
"""
from __future__ import annotations

import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from w2cplatform.rows import PARSE_ERRORS

from .tokens import KeySet, _b64, _unb64


def _canonical(doc: dict) -> bytes:
    return json.dumps({k: v for k, v in doc.items() if k not in ("kid", "sig")}, sort_keys=True,
                      ensure_ascii=False, separators=(",", ":")).encode()


def sign(doc: dict, issuer) -> dict:
    """`issuer`: anything with a `kid` and an Ed25519 `key` — the token issuer, or the domain's root."""
    return {**doc, "kid": issuer.kid, "sig": _b64(issuer.key.sign(_canonical(doc)))}


class NotTaken(Exception):
    pass


def verify(doc: dict, keys: KeySet | None, now: float) -> dict:
    if keys is None:
        raise NotTaken("no key set yet — nothing to check a signature against")
    if not keys.usable(doc.get("kid", ""), now):
        raise NotTaken(f"signed by key {doc.get('kid')!r}, which this member does not trust")
    try:
        Ed25519PublicKey.from_public_bytes(keys.keys[doc["kid"]]).verify(_unb64(doc["sig"]), _canonical(doc))
    except (InvalidSignature, *PARSE_ERRORS):         # a `sig` that is not a string too (the ninth review's sweep)
        raise NotTaken("the signature does not verify")
    return doc
