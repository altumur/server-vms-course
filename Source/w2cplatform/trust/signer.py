"""Lesson 4 and Lesson 7 — the domain signer: one job, two keys.

The CA and the token issuer are the same operational thing — a process that
holds keys and signs — so they are one service. Its keys live in a Nomad
Variable in the domain holder's raft (domain/signer): a SOFTWARE key on
purpose, because a TPM-sealed key pins the signer to one server and defeats
the failover it just gained. A software key is acceptable because
everything it signs is short-lived.

Certificates, split by job (Lesson 7):

    the domain root          years         a rotation drill         needs nothing outside
    service-to-service       hours–days    the signer               never
    member identity (LDevID) long          the signer, on enrollment and renewal

    maximum tolerable outage = certificate lifetime − renewal margin

Chain verification takes `now` and a skew tolerance, so the tests move time
instead of waiting, and so clock skew is a named failure rather than
"everything broke". Root rotation is an overlap window in a TRUST BUNDLE
(old root and new root both trusted until a stated retirement time), with
an optional cross-certificate for peers that have only the old root.
"""
from __future__ import annotations

import datetime as dt
import json
import secrets
import time
from dataclasses import dataclass

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.x509.oid import NameOID

from w2cplatform.rows import PARSE_ERRORS

from .tokens import ROOT_KID, KeySet, TokenIssuer

HOUR, DAY, YEAR = 3600.0, 86400.0, 365 * 86400.0

# Lesson 7's table, as numbers the product states. Change them here, not in a job file.
LIFETIMES = {
    "root": {"lifetime": 10 * YEAR, "margin": YEAR},
    "service": {"lifetime": 3 * DAY, "margin": DAY},         # tolerable outage: 2 days
    "ldevid": {"lifetime": 2 * YEAR, "margin": 90 * DAY},     # tolerable outage: ~21 months
}


def max_tolerable_outage(kind: str) -> float:
    """The number to state: lifetime − renewal margin. A product promising
    thirty days of autonomy cannot issue seven-day service certificates."""
    return LIFETIMES[kind]["lifetime"] - LIFETIMES[kind]["margin"]


def _utc(ts: float) -> dt.datetime:
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)


def _name(cn: str, org: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, org), x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _pem(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


def _key_bytes(k: Ed25519PrivateKey) -> bytes:
    return k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())


@dataclass
class Root:
    cert: x509.Certificate
    key: Ed25519PrivateKey
    retire_at: float = 0.0           # 0 = current

    @property
    def pem(self) -> bytes:
        return _pem(self.cert)


class VerifyError(Exception):
    pass


class TrustBundle:
    """What every server and service holds: the roots it accepts, each with
    a retirement time. Rotation = add the new root, retire the old on a date."""

    def __init__(self, roots: list[x509.Certificate] | None = None):
        self.roots: dict[str, tuple[x509.Certificate, float]] = {}
        for r in roots or []:
            self.add(r)

    def add(self, root: x509.Certificate, retire_at: float = 0.0) -> None:
        self.roots[root.subject.rfc4514_string()] = (root, retire_at)

    def retire(self, root: x509.Certificate, at: float) -> None:
        self.roots[root.subject.rfc4514_string()] = (root, at)

    def pems(self) -> bytes:
        return b"".join(_pem(r) for r, _ in self.roots.values())

    def verify(self, cert: x509.Certificate, now: float | None = None, skew: float = 300.0,
               cross: list[x509.Certificate] = (), chain: list[x509.Certificate] = (),
               revoked: set[str] = frozenset()) -> str:
        """Returns the issuing root's CN. `cross` are cross-certificates:
        a new root's public key signed by an old root, for peers that have
        not yet received the new root.

        `chain` (Lesson 15): the holder's issuing certificates, each signed
        by a root in the bundle. A leaf signed by one of them verifies through
        it — unless its serial is in `revoked`, the list the root signed with
        the key set when the holder that held it was stolen."""
        now = time.time() if now is None else now
        issuer = cert.issuer.rfc4514_string()
        for ca in chain:
            if ca.subject.rfc4514_string() != issuer:
                continue
            if str(ca.serial_number) in revoked:
                raise VerifyError(f"issued by {issuer}, whose certificate the domain's root revoked")
            root_cn = self.verify(ca, now=now, skew=skew, cross=cross)
            try:
                ca.public_key().verify(cert.signature, cert.tbs_certificate_bytes)
            except InvalidSignature:
                raise VerifyError("signature does not verify under the issuing certificate it names")
            self._within(cert, now, skew)
            return root_cn
        chain = list(self.roots.values()) + [(c, 0.0) for c in cross if c.subject.rfc4514_string() == issuer]
        for root, retire_at in chain:
            if root.subject.rfc4514_string() != issuer:
                continue
            if retire_at and now >= retire_at:
                raise VerifyError(f"issuer {issuer} was retired at {retire_at:.0f}")
            try:
                root.public_key().verify(cert.signature, cert.tbs_certificate_bytes)
            except InvalidSignature:
                raise VerifyError("signature does not verify under the root it names")
            self._within(cert, now, skew)
            return root.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        raise VerifyError(f"no trusted root named {issuer}")

    @staticmethod
    def _within(cert: x509.Certificate, now: float, skew: float) -> None:
        nvb, nva = cert.not_valid_before_utc.timestamp(), cert.not_valid_after_utc.timestamp()
        if now < nvb - skew:
            raise VerifyError(f"not yet valid: starts in {nvb - now:.0f}s — clock skew?")
        if now > nva + skew:
            raise VerifyError(f"expired {now - nva:.0f}s ago")


# Lesson 15 — the domain's ROOT, off the holder.
#
# Lessons 4 and 7 kept both of the signer's keys in the holder's raft, in software, and defended it: a key
# sealed in one server's TPM defeats the failover inside the cluster, and what it signs is short-lived. On a
# box of one that defence does not hold — there is no failover inside a box of one — and the box can be carried
# away: whoever has its flash has the domain. So the key that DECIDES who the domain is leaves the holder:
#
#     the root        in the recovery file the operator keeps, and nowhere online. It signs three things, all
#                     rare: the holder's issuing certificate, the key set members trust, and the holder record
#                     (who holds the domain, at which term). Every move of the domain needs the recovery file
#                     already (Lesson 15, step 3), so none of this asks for it more often than before.
#     the holder      an issuing certificate (LDevIDs, service certificates) and the token key — everything
#                     signed every minute. Stolen, they are revoked by the root: a new key set without the
#                     token key and with the issuing certificate's serial in `revoked_ca`.
#
# What a thief with a holder can no longer do: take the domain (a term is the root's to sign), or give the
# members a key set of his own (they pinned the root). What he can still do until the move: issue tokens and
# certificates under the keys he has. The move ends that — and is the same operation as any other move.
class DomainRoot:
    KID = ROOT_KID

    def __init__(self, domain: str, org: str = "customer", key: Ed25519PrivateKey | None = None,
                 cert: x509.Certificate | None = None, now=time.time):
        self.domain, self.org, self.now = domain, org, now
        self.key = key or Ed25519PrivateKey.generate()
        self.kid = self.KID                              # so `shared.sign(doc, root)` signs as the root
        self.cert = cert or self._self_signed()

    def _self_signed(self) -> x509.Certificate:
        cn, now = f"{self.domain} root", self.now()
        return (x509.CertificateBuilder().subject_name(_name(cn, self.org)).issuer_name(_name(cn, self.org))
                .public_key(self.key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(_utc(now - 60)).not_valid_after(_utc(now + LIFETIMES["root"]["lifetime"]))
                .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
                .sign(self.key, None))

    @property
    def public_bytes(self) -> bytes:
        return self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    def issuing(self, cn: str, public_key: Ed25519PublicKey, lifetime: float = LIFETIMES["root"]["lifetime"]) -> x509.Certificate:
        """The holder's issuing certificate: a CA under this root, allowed no CA beneath it."""
        now = self.now()
        return (x509.CertificateBuilder().subject_name(_name(cn, self.org)).issuer_name(self.cert.subject)
                .public_key(public_key).serial_number(x509.random_serial_number())
                .not_valid_before(_utc(now - 60)).not_valid_after(_utc(now + lifetime))
                .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                .sign(self.key, None))

    def key_set(self, ks: "KeySet", rev: int, revoked_ca=(), issuing=(), revoked_members=()) -> dict:
        """The key set members take, signed: the token keys, this root's public key, a revision that only
        grows, the holders' issuing certificates so far, and those no longer trusted. Items for `domain/keys`."""
        from .documents import sign
        doc = sign({"rev": int(rev), "keys": {k: v for k, v in ks.to_items().items() if k != f"key:{ROOT_KID}"},
                    "root": self.public_bytes.hex(), "revoked_ca": sorted(str(r) for r in revoked_ca),
                    "issuing": sorted(str(i) for i in issuing),
                    **({"revoked_members": sorted(str(k) for k in revoked_members)} if revoked_members else {})}, self)
        return {"doc": json.dumps(doc, sort_keys=True)}

    def recovery(self) -> bytes:
        """The recovery file: the root and nothing else. The holder's keys are not in it — they never leave
        the holder, and a move gives the new holder keys of its own."""
        return json.dumps({"domain": self.domain, "root_key": _key_bytes(self.key).hex(),
                           "root_cert": _pem(self.cert).decode()}).encode()

    @classmethod
    def restore(cls, domain: str, blob: bytes, now=time.time) -> "DomainRoot":
        d = json.loads(blob)
        return cls(domain, key=Ed25519PrivateKey.from_private_bytes(bytes.fromhex(d["root_key"])),
                   cert=x509.load_pem_x509_certificate(d["root_cert"].encode()), now=now)


def is_recovery_file(blob: bytes) -> bool:
    """A root's recovery file (Lesson 15), or the signer's backup of Lessons 4 and 7 (both keys)."""
    try:
        return "root_key" in json.loads(blob)
    except PARSE_ERRORS:                             # a number (`in` raises `TypeError`), `[` ten thousand deep (the ninth review's sweep)
        return False


class Signer:
    """The domain signer. `vars_` is the domain holder's Variables; the
    keys are loaded from domain/signer or created on first start (the cold
    start Lesson 1 walks: Nomad up → signer scheduled → certificates issued
    → workers heartbeat).

    Given a `root` (Lesson 15), what it creates is an issuing certificate
    under that root instead of a root of its own: `self.root` is then the
    issuing CA, and `self.chain` the certificate a verifier needs between a
    leaf and the root. The root's key is never written here."""

    def __init__(self, domain: str, vars_, org: str = "customer", now=time.time, root: DomainRoot | None = None):
        self.domain, self.org, self.now = domain, org, now
        items, _ = vars_.get("domain/signer")
        self.vars = vars_
        self.chain: list[x509.Certificate] = []
        # A row that is there and holds no keys, or keys that do not parse, is NOT "no keys" (the review's eighth pass;
        # the product found its signer taking a store it could not read for an empty one): new keys written over it
        # would orphan every member that holds the old ones. The signer refuses to start, and says what to do. Only an
        # absent row is a first start.
        if items is not None and "ca_key" not in items:
            raise RuntimeError(f"this cluster no longer holds the domain's keys ({items.get('forgotten', 'forgotten')})")
        if items is not None:
            try:
                key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(items["ca_key"]))
                self.root = Root(x509.load_pem_x509_certificate(items["ca_cert"].encode()), key)
                self.tokens = TokenIssuer(domain, Ed25519PrivateKey.from_private_bytes(bytes.fromhex(items["token_key"])), items["kid"])
                self.generation = int(items.get("gen", "1"))
            except PARSE_ERRORS as e:
                raise RuntimeError(f"the domain's keys in domain/signer do not parse ({e}): the signer does not start "
                                   f"rather than make new ones — restore the row from the holder's backup") from None
            if items.get("issued") == "true":
                self.chain = [self.root.cert]
        elif root is not None:
            self.generation = 1
            self._issue_from(root)
        else:
            self.generation = 1
            self.root = self._new_root(self.root_cn())
            self.tokens = TokenIssuer(domain)
            self._persist()
        self.serial = 0

    @classmethod
    def issued(cls, domain: str, vars_, root: DomainRoot, now=time.time) -> "Signer":
        """A signer with keys of its OWN under `root` — whatever this cluster held before. What a move gives
        the new holder: the old holder's keys are not in the recovery file, and must not be."""
        s = cls.__new__(cls)                             # `_persist` writes over whatever was there, by CAS
        s.domain, s.org, s.now, s.vars, s.chain, s.serial, s.generation = domain, root.org, now, vars_, [], 0, 1
        s._issue_from(root)
        return s

    def _issue_from(self, root: DomainRoot) -> None:
        key = Ed25519PrivateKey.generate()
        cert = root.issuing(f"{self.domain} issuing {secrets.token_hex(3)}", key.public_key())
        self.root, self.chain = Root(cert, key), [cert]
        self.tokens = TokenIssuer(self.domain)
        self._persist()

    def root_cn(self) -> str:
        # Each root generation has its own name: a trust bundle keys on the
        # subject, and two roots that share one name are one root to it.
        return f"{self.domain} root g{self.generation}"

    def _persist(self) -> None:
        _, idx = self.vars.get("domain/signer")
        self.vars.put("domain/signer", {"ca_key": _key_bytes(self.root.key).hex(), "ca_cert": self.root.pem.decode(),
                                        "token_key": _key_bytes(self.tokens.key).hex(), "kid": self.tokens.kid,
                                        "gen": self.generation, **({"issued": "true"} if self.chain else {})}, cas=idx)

    def _new_root(self, cn: str) -> Root:
        key = Ed25519PrivateKey.generate()
        now = self.now()
        cert = (x509.CertificateBuilder().subject_name(_name(cn, self.org)).issuer_name(_name(cn, self.org))
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(_utc(now - 60)).not_valid_after(_utc(now + LIFETIMES["root"]["lifetime"]))
                .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                .sign(key, None))
        return Root(cert, key)

    def issue(self, cn: str, kind: str, public_key: Ed25519PublicKey, lifetime: float | None = None) -> x509.Certificate:
        """A leaf. `cn` names the SERVER or the service, never a worker — a worker
        is an allocation named by a slot, and Nomad's workload identity is its token."""
        now = self.now()
        life = lifetime if lifetime is not None else LIFETIMES[kind]["lifetime"]
        self.serial += 1
        return (x509.CertificateBuilder().subject_name(_name(cn, self.org)).issuer_name(self.root.cert.subject)
                .public_key(public_key).serial_number(self.serial)
                .not_valid_before(_utc(now - 60)).not_valid_after(_utc(now + life))
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .sign(self.root.key, None))

    def needs_renewal(self, cert: x509.Certificate, kind: str) -> bool:
        return self.now() >= cert.not_valid_after_utc.timestamp() - LIFETIMES[kind]["margin"]

    def renew(self, cert: x509.Certificate, kind: str) -> x509.Certificate:
        """Same key, same name, a fresh window. Overlapping validity is what
        lets the holder reload without dropping a connection."""
        cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        return self.issue(cn, kind, cert.public_key())

    # -- Lesson 7: root rotation as a drill --------------------------------------
    def rotate_root(self, bundle: TrustBundle, overlap: float) -> tuple[Root, x509.Certificate]:
        """A new root; the old one stays trusted for `overlap` seconds; new
        leaves are signed by the new root from now. Returns the new root and
        a cross-certificate (new root's key, signed by the old root) for peers
        that only hold the old one."""
        old = self.root
        self.generation += 1
        new = self._new_root(self.root_cn())
        cross = (x509.CertificateBuilder().subject_name(new.cert.subject).issuer_name(old.cert.subject)
                 .public_key(new.key.public_key()).serial_number(x509.random_serial_number())
                 .not_valid_before(_utc(self.now() - 60)).not_valid_after(_utc(self.now() + overlap))
                 .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                 .sign(old.key, None))
        bundle.add(new.cert)
        bundle.retire(old.cert, self.now() + overlap)
        self.root = new
        self._persist()
        return new, cross

    def backup(self) -> bytes:
        """What goes beyond the domain holder (another cluster's object
        store, or offline). Losing this loses the domain's trust: every server
        re-enrolls.

        Not for a signer issued by a root (Lesson 15): its keys never leave
        the holder, and what the operator keeps is the root's recovery file."""
        if self.chain:
            raise RuntimeError("an issuing signer's keys stay on the holder; keep the root's recovery file instead")
        return json.dumps({"ca_key": _key_bytes(self.root.key).hex(), "ca_cert": self.root.pem.decode(),
                           "token_key": _key_bytes(self.tokens.key).hex(), "kid": self.tokens.kid,
                           "gen": self.generation}).encode()

    @classmethod
    def restore(cls, domain: str, vars_, backup: bytes, now=time.time) -> "Signer":
        d = json.loads(backup)
        _, idx = vars_.get("domain/signer")
        vars_.put("domain/signer", d, cas=idx)
        return cls(domain, vars_, now=now)
