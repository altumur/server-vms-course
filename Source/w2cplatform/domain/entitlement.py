"""Lesson 5 — entitlement, from the domain's side.

The vendor issues it (М14 Lesson 3); the domain CACHES it and degrades on a
grace period, exactly like placement and identity. The licence lives in
the domain holder's store, arrives through the same update server as
bundles, and is verified against a key shipped in the product. What
degrades: work-but-don't-add-units. Nothing that already works stops
because a licence server is unreachable — not for a month, not ever.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from w2cplatform.variables import Variables

GRACE = 30 * 86400.0      # the number the datasheet states


class LicenceError(Exception):
    pass


@dataclass
class Licence:
    domain: str
    units: int
    features: list[str]
    valid_until: float
    issued: float

    @classmethod
    def verify(cls, blob: bytes, vendor_public: bytes) -> "Licence":
        body, sig = blob.rsplit(b".", 1)
        try:
            Ed25519PublicKey.from_public_bytes(vendor_public).verify(bytes.fromhex(sig.decode()), body)
        except (InvalidSignature, ValueError):
            raise LicenceError("licence signature does not verify against the product's vendor key")
        d = json.loads(body)
        return cls(d["domain"], int(d["units"]), list(d["features"]), float(d["valid_until"]), float(d["issued"]))


class EntitlementCache:
    def __init__(self, domain: str, vars_: Variables, vendor_public: bytes, now=time.time):
        self.domain, self.vars, self.vendor_public, self.now = domain, vars_, vendor_public, now

    def install(self, blob: bytes) -> Licence:
        lic = Licence.verify(blob, self.vendor_public)
        if lic.domain != self.domain:
            raise LicenceError(f"licence names domain {lic.domain!r}, this is {self.domain!r}")
        _, idx = self.vars.get("domain/licence")
        self.vars.put("domain/licence", {"blob": blob.decode()}, cas=idx)
        return lic

    def current(self) -> Licence | None:
        items, _ = self.vars.get("domain/licence")
        return Licence.verify(items["blob"].encode(), self.vendor_public) if items else None

    def status(self) -> str:
        """valid | grace | degraded | none. Work is allowed in all four."""
        lic = self.current()
        if lic is None:
            return "none"
        now = self.now()
        if now <= lic.valid_until:
            return "valid"
        if now <= lic.valid_until + GRACE:
            return "grace"
        return "degraded"

    def may_add_unit(self, current_count: int) -> tuple[bool, str]:
        lic = self.current()
        st = self.status()
        if st in ("none", "degraded"):
            return False, f"entitlement {st}: work continues, adding units does not"
        if current_count >= lic.units:
            return False, f"licensed for {lic.units} units, {current_count} configured"
        return True, f"{st}: {lic.units - current_count} unit(s) left"

    @staticmethod
    def work_allowed() -> bool:
        return True       # by construction. There is no code path that returns False.
