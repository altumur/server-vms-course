"""ADR-0074: book inputs encrypted to the domain, bound to their original identity.

The receive seed uses the existing MemberKey X25519 derivation/envelope only; it
never signs or grants an identity. Relays and the accepted report store keep the
encrypted bytes. Only the holder opens them while collecting a declared book.
"""
from __future__ import annotations

import json

from w2cplatform.secrets import is_secret_field
from w2cplatform.trust.memberkey import MemberKey, NotMine, seal_to
from w2cplatform.trust.tokens import jcs

ROW = "domain/book-seal"


class Unavailable(ValueError):
    """A receive key or contribution cannot be used. Never includes payload text."""


def load(vars_, sealer=None, *, create=False):
    from w2cplatform.sealing import seal_items
    items, idx = vars_.get(ROW)
    if items is None and create:
        key = MemberKey.new()
        vars_.put(ROW, seal_items(sealer, {"seed_secret": key.seed.hex()}, ROW), cas=idx)
        return key
    return decode(items, sealer)


def decode(items, sealer=None):
    from w2cplatform.sealing import Sealed, open_row
    try:
        if not isinstance(items, dict) or set(items) != {"seed_secret"}:
            raise ValueError("invalid receive key row")
        value = open_row(sealer, items, ROW)["seed_secret"]
        if not isinstance(value, str) or len(value) != 64 or value.lower() != value:
            raise ValueError("invalid seed")
        return MemberKey(bytes.fromhex(value))
    except Sealed:
        raise
    except (ValueError, TypeError, KeyError):
        raise Unavailable("the domain book receive key is absent or unreadable") from None


def replace(vars_, sealer=None):
    from w2cplatform.sealing import seal_items
    key = MemberKey.new()
    _, idx = vars_.get(ROW)
    vars_.put(ROW, seal_items(sealer, {"seed_secret": key.seed.hex()}, ROW), cas=idx)
    return key


def context(member, source, item):
    return jcs([member, source, item]).decode("utf-8")


def _deep(value, fn):
    if isinstance(value, dict):
        out = {}
        for field, part in value.items():
            if is_secret_field(field):
                if not isinstance(part, str):
                    raise Unavailable("a book secret is not text")
                out[field] = fn(field, part)
            else:
                out[field] = _deep(part, fn)
        return out
    if isinstance(value, list):
        return [_deep(part, fn) for part in value]
    return value


def _row(items, fn):
    from .bookmerge import _constant, _json, _object
    try:
        if not isinstance(items, dict):
            raise ValueError("invalid source row")
        out = {}
        for item, raw in items.items():
            if not isinstance(item, str) or not item or not isinstance(raw, str):
                raise ValueError("invalid source item")
            doc = json.loads(raw, object_pairs_hook=_object, parse_constant=_constant)
            if not isinstance(doc, dict):
                raise ValueError("invalid contribution")
            out[item] = _json(_deep(doc, lambda field, value: fn(item, field, value)))
        return out
    except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError, NotMine):
        raise Unavailable("a book contribution cannot be opened or sealed") from None


def verified_key(vars_, now):
    """Reverify the carried root signature; an unsigned set or answer field is no key."""
    from .agent import KEYS_PATH, ClusterTrust
    from w2cplatform.trust.documents import verify
    from w2cplatform.trust.tokens import KeySet, ROOT_KID
    try:
        root = ClusterTrust(vars_).root()
        items, _ = vars_.get(KEYS_PATH)
        doc = json.loads(items["doc"])
        if root is None or doc.get("root") != root.hex() or doc.get("kid") != ROOT_KID:
            raise ValueError("no trusted root")
        verify(doc, KeySet(current="", keys={ROOT_KID: root}), now)
        return KeySet.from_items(items).book_seal
    except Exception:
        raise Unavailable("no verified domain book receive key") from None


def outgoing(member, source, items, vars_, sealer, now):
    public = None
    def one(item, field, value):
        nonlocal public
        from w2cplatform.sealing import is_sealed
        if public is None:
            public = verified_key(vars_, now)
        if is_sealed(value):
            if sealer is None:
                raise Unavailable("the member has no ring to open its book secret")
            try:
                value = sealer.open(field, value, f"{source}#{item}")
            except Exception:
                raise Unavailable("the member cannot open its book secret") from None
        return seal_to(public, field, value, context(member, source, item))
    return _row(items, one)


def incoming(member, source, items, key):
    return _row(items, lambda item, field, value: key.open(field, value, context(member, source, item)))


def at_rest(items, sealer, dest):
    """Results always bind secrets to the final recipient row and result item."""
    def one(item, field, value):
        if sealer is None:
            raise Unavailable("the holder has no ring to seal a book result")
        return sealer.seal(field, value, f"{dest}#{item}", force=True)
    # The empty item is metadata, not a contribution.
    return {"": items[""], **_row({k: v for k, v in items.items() if k}, one)}
