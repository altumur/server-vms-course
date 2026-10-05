"""A member's own key: who the member is to its holder's door, and what a secret is sealed to on the way to it.

One seed, kept on the member and nowhere else (`domain/member-key`, its `seed_secret` sealed with the member's own key
ring), gives two keys:

    sign      Ed25519 — the member signs its ask for what it carries (`carry.py`); the holder checks the signature
              against the key the member was admitted with (`domain/members`, `key`), never a key the ask brings along
    seal      X25519, derived from the same seed — the holder seals each secret it hands the member to this key
              (`seal_to`): an ephemeral key, ECDH, HKDF, AES-GCM with the field and its row bound in. Only the member
              opens it (`MemberKey.open`). The X25519 public key travels in the signed ask, so nobody between can put
              their own in its place

What the holder hands a member over plain HTTP is then no secret to whoever listens — the course goes further than the
product here, which sends them open until its mTLS round (DOMAIN-PLATFORM.md, the owner's Q1).
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SEALED_TO = "x25519:v1:"                # `x25519:v1:<ephemeral public hex>:<nonce hex>:<ciphertext b64>`
ROW = "domain/member-key"               # in the member's own store: {seed_secret, pub, seal_pub}


def _raw(pub) -> bytes:
    return pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _kdf(shared: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(shared)


def _aad(field: str, ctx: str) -> bytes:
    return f"{ctx}:{field}".encode()


def is_sealed_to(value) -> bool:
    return isinstance(value, str) and value.startswith(SEALED_TO)


def seal_to(seal_pub_hex: str, field: str, value: str, ctx: str) -> str:
    """`value` sealed to the member whose X25519 public key is `seal_pub_hex`; bound to the field and its row."""
    eph = X25519PrivateKey.generate()
    key = _kdf(eph.exchange(X25519PublicKey.from_public_bytes(bytes.fromhex(seal_pub_hex))), b"w2c member seal")
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, value.encode(), _aad(field, ctx))
    return f"{SEALED_TO}{_raw(eph.public_key()).hex()}:{nonce.hex()}:{base64.b64encode(ct).decode()}"


class NotMine(Exception):
    """A value sealed to another member's key, or to another row or field — or not sealed at all where it must be."""


class MemberKey:
    def __init__(self, seed: bytes):
        if len(seed) != 32:
            raise ValueError("a member key's seed is 32 bytes")
        self.seed = seed
        self.signing = Ed25519PrivateKey.from_private_bytes(seed)
        self.sealing = X25519PrivateKey.from_private_bytes(_kdf(seed, b"w2c member x25519"))

    @classmethod
    def new(cls) -> "MemberKey":
        return cls(os.urandom(32))

    @property
    def pub(self) -> str:
        return _raw(self.signing.public_key()).hex()

    @property
    def seal_pub(self) -> str:
        return _raw(self.sealing.public_key()).hex()

    def sign(self, message: bytes) -> str:
        return self.signing.sign(message).hex()

    def open(self, field: str, value: str, ctx: str) -> str:
        if not is_sealed_to(value):
            raise NotMine(f"{ctx}:{field} was not sealed to this member")
        try:
            eph, nonce, ct = value[len(SEALED_TO):].split(":")
            key = _kdf(self.sealing.exchange(X25519PublicKey.from_public_bytes(bytes.fromhex(eph))), b"w2c member seal")
            return AESGCM(key).decrypt(bytes.fromhex(nonce), base64.b64decode(ct), _aad(field, ctx)).decode()
        except Exception as e:                            # noqa: BLE001 — a wrong key, row or field, or garbage: not ours
            raise NotMine(f"{ctx}:{field} does not open with this member's key ({type(e).__name__})") from None

    # Kept in the member's own store, the seed sealed with the member's key ring (`sealing.Sealer`): a copy of the store
    # is no copy of the member's identity. With no ring it is written in the clear, and the platform says so once.
    def save(self, vars_, sealer=None) -> None:
        from w2cplatform.sealing import seal_items
        _, idx = vars_.get(ROW)
        vars_.put(ROW, seal_items(sealer, {"seed_secret": self.seed.hex(), "pub": self.pub, "seal_pub": self.seal_pub},
                                  ROW), cas=idx)

    @classmethod
    def load(cls, vars_, sealer=None) -> "MemberKey | None":
        from w2cplatform.sealing import open_row
        items, _ = vars_.get(ROW)
        if not items or not items.get("seed_secret"):
            return None
        return cls(bytes.fromhex(open_row(sealer, items, ROW)["seed_secret"]))

    @classmethod
    def load_or_make(cls, vars_, sealer=None) -> "MemberKey":
        key = cls.load(vars_, sealer)
        if key is None:
            key = cls.new()
            key.save(vars_, sealer)
        return key


def verify(pub_hex: str, message: bytes, sig_hex: str) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex)).verify(bytes.fromhex(sig_hex), message)
        return True
    except Exception:                                    # noqa: BLE001 — any garbage is "does not verify"
        return False
