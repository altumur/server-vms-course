"""Lesson 4 — a token signed by the domain signer; clusters hold the public
key, never a password hash.

    Alice -> signer: short-lived signed token (sub: alice, exp, jti)
    the cluster's console: verify signature (public key, OFFLINE), check expiry, check the
            revocation list it holds, then look up ITS OWN grants for "alice"

The token names the subject and nothing else. Rights are not in it (the
Authorization row): a token that carried rights would be a lookup that
expired with the domain.

Format: base64url(header).base64url(payload).base64url(Ed25519 signature)
— the JWS shape with one algorithm and no library, so a console verifies it
with forty lines and a public key. Keys are a SET (kid -> public key) so
rotation overlaps: a token signed by the previous key verifies until that
key's retirement time passes.
"""
from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from w2cplatform.rows import Table

# The rows of trust a cluster holds — the key set, the root it pinned, the revocation list — as the domain's agent
# carried them (the review's seventh pass left "the trust readers" open). One that does not parse is counted here once
# (`trust_row`) and logged once; what not reading it means is the reader's (`agent.ClusterTrust`): a door that cannot
# check a token says so with a 503 — never "nothing to check".
TRUST_ROWS = Table("trust_row", "a door that reads it answers 503 until the domain's agent writes it again", "trust row")


class TokenError(Exception):
    pass


class Expired(TokenError):
    pass


class Revoked(TokenError):
    pass


class UnknownKey(TokenError):
    pass


class BadSignature(TokenError):
    pass


class WrongKind(TokenError):
    pass


# WHAT A TOKEN IS FOR (the product, feedback CE). One key signs a person's token, a camera's stream token, the token
# a camera asks another with, and a relay's token to the centre. Read by signature alone, any of them is "a token
# for `sub`": a stream token off a camera's flash would pass a console's gate as the user `cam-SN5001`, a relay's
# as the user `south` — and whoever has grants under such a name has them. So every token says what it is for
# (`kind`), and every door accepts its own:
#
#   person   a console, the domain's door, the live gateway             (`identity`, `BreakGlass`)
#   stream   an ingest: poll, push, upload, take a stream               (`Crossings`, the relay's upstream book)
#   ask      an ingest's door for asks between cameras                  (the book of asks)
#
# A token issued before the claim existed says it by its shape: `ask` names a target, `aud` names an ingest, and a
# person's token has neither.
KINDS = ("person", "stream", "ask")


def kind_of(payload: dict) -> str:
    k = payload.get("kind")
    if k:
        return str(k)
    if "ask" in payload:
        return "ask"
    return "stream" if "aud" in payload else "person"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


ROOT_KID = "root"      # Lesson 15: the domain's root, kept OFF the holder, signs the key set and the holder record


@dataclass
class KeySet:
    """What every cluster and agent holds: current kid, and every public key
    still trusted with the time after which each is retired (0 = never).

    Since Lesson 15 it may come signed by the domain's root: then it also
    holds the root's public key (kid `root`), a revision that only grows, and
    the serials of the holder's issuing certificates that are no longer
    trusted (`revoked_ca`). Parsed here; VERIFIED by the agent that carries
    it (`DomainAgent._carry_keys`), against the root the member pinned."""
    current: str
    keys: dict[str, bytes] = field(default_factory=dict)       # kid -> raw 32-byte public key
    retire_at: dict[str, float] = field(default_factory=dict)  # kid -> wall time; missing = current/never
    rev: int = 0
    revoked_ca: set[str] = field(default_factory=set)
    issuing: set[str] = field(default_factory=set)             # serials of the holders' issuing certificates so far
    # Member keys revoked by a theft (feedback CK): the stolen holder's own. In the key set and not only in the
    # list of members, because the list travels in backups and an older backup does not know of the theft; the
    # key set every member holds, signed by the root, only goes forward.
    revoked_members: set[str] = field(default_factory=set)

    @property
    def root(self) -> bytes | None:
        return self.keys.get(ROOT_KID)

    def to_items(self) -> dict:
        items = {"current": self.current}
        for kid, pub in self.keys.items():
            items[f"key:{kid}"] = pub.hex()
            if kid in self.retire_at:
                items[f"retire:{kid}"] = str(self.retire_at[kid])
        return items

    @classmethod
    def from_items(cls, items: dict) -> "KeySet":
        if "doc" in items:                                      # signed by the root (Lesson 15)
            d = json.loads(items["doc"])
            ks = cls.from_items(d["keys"])
            ks.keys[ROOT_KID] = bytes.fromhex(d["root"])
            ks.rev, ks.revoked_ca, ks.issuing = int(d["rev"]), set(d.get("revoked_ca", [])), set(d.get("issuing", []))
            ks.revoked_members = set(d.get("revoked_members", []))
            return ks
        ks = cls(current=items["current"])
        for k, v in items.items():
            if k.startswith("key:"):
                ks.keys[k[4:]] = bytes.fromhex(v)
            elif k.startswith("retire:"):
                ks.retire_at[k[7:]] = float(v)
        return ks

    def usable(self, kid: str, now: float) -> bool:
        return kid in self.keys and (kid not in self.retire_at or now < self.retire_at[kid])


def kid_of(token: str) -> str | None:
    """The key a token names, read without verifying — for a book deciding whether to issue it again: a
    token the CURRENT key did not sign is re-issued whatever its half-life says (Lesson 15, step 9: after a
    move the holder's key is new, and after a theft the old one is no longer trusted anywhere)."""
    try:
        return json.loads(_unb64(token.split(".")[0])).get("kid")
    except (ValueError, IndexError, AttributeError):
        return None


class TokenIssuer:
    """Half of the domain signer. Holds the private key; issues short tokens."""

    def __init__(self, domain: str, private_key: Ed25519PrivateKey | None = None, kid: str | None = None):
        self.domain = domain
        self.key = private_key or Ed25519PrivateKey.generate()
        self.kid = kid or secrets.token_hex(4)
        self.previous: list[tuple[str, bytes, float]] = []    # (kid, public, retire_at) still in the set

    @property
    def public_bytes(self) -> bytes:
        from cryptography.hazmat.primitives import serialization
        return self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    def keyset(self) -> KeySet:
        ks = KeySet(current=self.kid, keys={self.kid: self.public_bytes})
        for kid, pub, until in self.previous:
            ks.keys[kid] = pub
            ks.retire_at[kid] = until
        return ks

    def issue(self, subject: str, lifetime: float, now: float | None = None, **claims) -> str:
        now = time.time() if now is None else now
        header = {"alg": "EdDSA", "kid": self.kid}
        payload = {"iss": self.domain, "sub": subject, "iat": now, "exp": now + lifetime,
                   "jti": secrets.token_hex(8), **claims}
        signing = _b64(json.dumps(header, sort_keys=True).encode()) + "." + _b64(json.dumps(payload, sort_keys=True).encode())
        return signing + "." + _b64(self.key.sign(signing.encode()))

    def rotate(self, overlap: float, now: float | None = None) -> str:
        """A new signing key; the old public key stays in the set for
        `overlap` seconds so tokens it signed run to their expiry. Returns
        the new kid."""
        now = time.time() if now is None else now
        self.previous.append((self.kid, self.public_bytes, now + overlap))
        self.key, self.kid = Ed25519PrivateKey.generate(), secrets.token_hex(4)
        self.previous = [(k, p, u) for k, p, u in self.previous if u > now]
        return self.kid


def verify(token: str, keys: KeySet, revoked: set[str] = frozenset(), now: float | None = None,
           skew: float = 60.0, kind: str | None = None) -> dict:
    """Offline. Returns the payload (the subject is payload["sub"]). `kind`: what this door accepts (`KINDS`);
    a token for something else is refused however good its signature."""
    now = time.time() if now is None else now
    try:
        h, p, s = token.split(".")
        header, payload = json.loads(_unb64(h)), json.loads(_unb64(p))
    except (ValueError, json.JSONDecodeError):
        raise BadSignature("not a token")
    kid = header.get("kid", "")
    if not keys.usable(kid, now):
        raise UnknownKey(f"kid {kid!r} is not in the trusted set (or retired)")
    try:
        Ed25519PublicKey.from_public_bytes(keys.keys[kid]).verify(_unb64(s), f"{h}.{p}".encode())
    except InvalidSignature:
        raise BadSignature("signature does not verify")
    if now > payload["exp"] + skew:
        raise Expired(f"expired {now - payload['exp']:.0f}s ago")
    if now < payload["iat"] - skew:
        raise BadSignature(f"issued {payload['iat'] - now:.0f}s in the future — clock skew")
    if payload["jti"] in revoked:
        raise Revoked(payload["jti"])
    if kind is not None and kind_of(payload) != kind:
        raise WrongKind(f"a {kind_of(payload)} token, not a {kind} token: this door takes {kind} tokens only")
    return payload


class RevocationList:
    """Small, rare, consistent: raft's shape. Entries carry the token's own
    expiry so the list prunes itself — revocation is a lifetime problem."""

    def __init__(self):
        self.entries: dict[str, float] = {}       # jti -> exp

    def revoke(self, payload: dict) -> None:
        self.entries[payload["jti"]] = float(payload["exp"])

    def prune(self, now: float) -> None:
        self.entries = {j: e for j, e in self.entries.items() if e > now}

    def to_items(self) -> dict:
        return {"jtis": ",".join(f"{j}:{e}" for j, e in sorted(self.entries.items()))}

    # Entry by entry (the review's seventh pass: the signer did not start on one torn entry, and a cluster's every
    # request raised). An entry whose expiry is not a number — or that has no expiry at all, half of it written — still
    # names a token that was revoked: it stays revoked, with no end (`inf`), counted once. A row that is not an object
    # of a string raises: whoever reads it decides what not knowing the revocations means.
    @classmethod
    def from_items(cls, items: dict | None, where: str = "domain/revoked") -> "RevocationList":
        import math
        rl = cls()
        if items is not None and not (isinstance(items, dict) and isinstance(items.get("jtis", ""), str)):
            raise TypeError("the revocation list is not an object holding a string")
        torn = False
        for part in (items or {}).get("jtis", "").split(","):
            j, _, e = part.rpartition(":") if ":" in part else (part, "", "")
            if not j:
                continue
            try:
                exp = float(e)
                if math.isnan(exp):
                    raise ValueError("nan")
            except ValueError:
                exp, torn = math.inf, True
            rl.entries[j] = exp
        if torn:
            TRUST_ROWS.garbled(where, ValueError("an entry's expiry is not a number: kept revoked, with no end"))
        else:
            TRUST_ROWS.parsed(where)
        return rl

    @property
    def jtis(self) -> set[str]:
        return set(self.entries)
