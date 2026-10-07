"""A secret is SEALED in the store and opened only by the process that uses it."""
# ================================================================================================
# # sealing.py — the cluster's key, and `*_secret` fields at rest
#
# `secrets.py` keeps a secret off every screen and out of every copy that leaves the cluster. What it could not
# do, and said so: the ROW held the password in the clear, and whoever could read `<sub>/<rows>/*` — or copied
# the store's directory, or a backup of it — read every unit's password (the product's authentication note,
# section 3.6; the order agreed with it, feedback BP).
#
# THE KEY IS NOT IN THE STORE. That is the whole design, and everything else follows from it. A key kept beside
# the rows it protects protects nothing: a copy of the store is a copy of both. So the key ring is a FILE, given only
# to the processes whose role writes a secret or opens one — the members of `w2c-secrets`, on a box and on every
# server of a cluster alike:
#
#   the console     writes rows: it SEALS every `*_secret` value on the way in (`SpecController`), and the door key
#                   it signs a page's tokens with (`door.py`, `door/signer`)
#   a worker        whose subsystem opens a thing with a secret: it OPENS the value at the last moment, for the use
#
# and to nobody else — a controller, the resource and every backup read the row and get ciphertext. Which units
# join the group is the deployment's (its unit files; the rights file, `configstore-rights.json`, grants ROWS, and the
# key is no row). One interface, `SECRETS_KEY=<path>`, both places.
#
#   file      lines `<kid> <64 hex digits>`; the FIRST is the current key. Rotating is adding a line on top:
#             new writes are sealed with it, and every older one still opens by the kid it names
#   value     `enc:v1:<kid>:<nonce>:<ciphertext>` — AES-256-GCM, the field's name AND the row's key as associated
#             data, so a sealed password pasted into another field, or into another unit's row, does not open
#
# NO KEY IS STILL A MODE, AND IT SAYS SO. Without `SECRETS_KEY` a secret is written as it always was, and the
# console's log says, once, that secrets are stored in the clear. A value that IS sealed and a process with no
# key, or without the kid it names, is an error at the one place it matters — the unit does not start, and
# the reason names the key — never a password silently read as the ciphertext.
#
# A value that is not sealed opens as itself: rows written before a key existed go on working, and the next
# write of the row seals them.
# ================================================================================================
from __future__ import annotations

import base64
import logging
import os
import secrets as _secrets

from .secrets import is_secret_field
from .variables import Conflict

PREFIX = "enc:v1:"
log = logging.getLogger("w2cplatform.sealing")


class Sealed(Exception):
    """A sealed value this process cannot open: no key, an unknown kid, or a value that was tampered with."""


def is_sealed(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def kid_of(value: str) -> str:
    """The key a sealed value names; '' when it is not sealed or not well formed."""
    parts = value[len(PREFIX):].split(":") if is_sealed(value) else []
    return parts[0] if len(parts) == 3 else ""


class Sealer:
    def __init__(self, keys: dict[str, bytes], current: str):
        if current not in keys or any(len(k) != 32 for k in keys.values()):
            raise ValueError("a key ring names its current key, and every key is 32 bytes")
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM     # only where there is a key to use it with
        self._aead = {kid: AESGCM(k) for kid, k in keys.items()}
        self._keys = dict(keys)
        self.current = current

    # A KEYED DIGEST, for a copy that is compared and never read back — the idempotency claim's "the same body?" (the
    # thirteenth review, major 7: an unsalted sha256 of a body that carries `cred_secret` gave the password back to a
    # dictionary of seven words, beside a row that held it sealed). HMAC-SHA256 under a key derived from the ring's
    # for this purpose alone, so no digest is ever made with the sealing key itself; `kid:hex`, and `kid` asks the
    # digest of a console a rotation ahead or behind by the key it was made with. None: this process lacks that kid.
    def mac(self, purpose: str, data: bytes, kid: str | None = None) -> str | None:
        import hashlib
        import hmac
        kid = kid or self.current
        if kid not in self._keys:
            return None
        sub = hmac.new(self._keys[kid], b"w2c-mac:" + purpose.encode(), hashlib.sha256).digest()
        return f"{kid}:{hmac.new(sub, data, hashlib.sha256).hexdigest()}"

    @classmethod
    def from_file(cls, path: str) -> "Sealer":
        keys, current = {}, None
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                kid, hexkey = line.split()
                keys[kid] = bytes.fromhex(hexkey)
                current = current or kid
        if current is None:
            raise ValueError(f"{path} holds no key")
        return cls(keys, current)

    @classmethod
    def from_env(cls, env=None) -> "Sealer | None":
        path = (os.environ if env is None else env).get("SECRETS_KEY", "")
        return cls.from_file(path) if path else None

    # The associated data binds the ciphertext to its place: the ROW (`<sub>/<rows>/<id>`, the store key) and the
    # field. Without the row, unit 7's sealed password pasted into unit 8's row opens for whoever reads 8 —
    # the holder does the opening, and does it for the row it was given (the review's second pass, a major).
    #
    # The row is NOT optional (the review's third pass, blocker 3). It was `ctx=""` by default, and the one caller
    # that forgot it — a worker opening a mounted store's `access_secret` — asked for a value bound to no row, which
    # the console had sealed to `<sub>/<rows>/<name>`: every such row's secret failed to open. Every seal and
    # every open names its row now, or does not run.
    #
    # Values sealed before the row was part of it open by the field alone — and ONLY where `seal_stored` re-seals
    # them (`fallback=True`). Anywhere else an old value was a value that opened in any row, the hole binding closed.
    @staticmethod
    def _aad(field: str, ctx: str) -> bytes:
        return f"{ctx}:{field}".encode() if ctx else field.encode()

    def seal(self, field: str, value: str, ctx: str) -> str:
        if not value or is_sealed(value):
            return value
        nonce = _secrets.token_bytes(12)
        ct = self._aead[self.current].encrypt(nonce, value.encode(), self._aad(field, ctx))
        b = lambda x: base64.urlsafe_b64encode(x).decode().rstrip("=")
        return f"{PREFIX}{self.current}:{b(nonce)}:{b(ct)}"

    def bound(self, field: str, value: str, ctx: str) -> bool:
        """Whether a sealed value opens with its row in the associated data — or only by the field, the old way."""
        try:
            self.open(field, value, ctx, fallback=False)
            return True
        except Sealed:
            return False

    def open(self, field: str, value: str, ctx: str, fallback: bool = False) -> str:
        if not is_sealed(value):
            return value
        # A value that only LOOKS sealed — `enc:v1:x`, a row somebody typed or a copy that lost its tail — is a
        # `Sealed` like any other: this unit's status, not the end of the pass for every unit after it
        # (the review's second pass, blocker 3).
        parts = value[len(PREFIX):].split(":")
        if len(parts) != 3 or not all(parts):
            raise Sealed(f"{field} looks sealed and is not: `{PREFIX}<kid>:<nonce>:<ciphertext>` has {len(parts)} parts")
        kid, nonce, ct = parts
        if kid not in self._aead:
            raise Sealed(f"{field} is sealed with key {kid!r}, which this process does not hold")
        d = lambda x: base64.urlsafe_b64decode(x + "=" * (-len(x) % 4))
        for aad in ([self._aad(field, ctx)] + ([field.encode()] if ctx and fallback else [])):
            try:
                return self._aead[kid].decrypt(d(nonce), d(ct), aad).decode()
            except Exception:                            # noqa: BLE001 — InvalidTag: tampered, or another row's or field's
                continue
        raise Sealed(f"{field} does not open with key {kid!r}: altered, or copied from another row or field")


# The two operations the platform performs, with or without a key.
_said_clear = False


def seal_items(sealer: Sealer | None, items: dict, ctx: str) -> dict:
    """The row as it goes into the store: every `*_secret` value sealed — when there is a key. `ctx`: the row's
    key in the store, bound into the ciphertext."""
    global _said_clear
    if sealer is None:
        if not _said_clear and any(is_secret_field(k) and v for k, v in items.items()):
            _said_clear = True
            log.warning("secrets are stored in the CLEAR: this process has no SECRETS_KEY, and whoever reads or copies "
                        "the store reads every secret in the clear")
        return items
    return {k: (sealer.seal(k, str(v), ctx) if is_secret_field(k) and v else v) for k, v in items.items()}


def open_row(sealer: Sealer | None, row: dict, ctx: str) -> dict:
    """The row as the process that USES a secret needs it. A sealed value and no key raise `Sealed`. `ctx`: the
    row's key in the store — the one the holder was given, not one the row names."""
    out = dict(row)
    for k, v in row.items():
        if is_secret_field(k) and is_sealed(v):
            if sealer is None:
                raise Sealed(f"{k} is sealed and this process has no key (SECRETS_KEY)")
            out[k] = sealer.open(k, v, ctx)
    return out


# Rows written BEFORE the key existed (feedback CD). `seal_items` seals a row the next time it is written, and a
# unit nobody touches is never written again: its password would lie in the clear for years beside rows that
# are sealed. So the console, starting with a key, seals what is stored — the value only, in place, by CAS: the
# revision does not move, because nothing the row MEANS has changed, and a revision that moved would restart
# every pipeline for a password it already has. `prefixes`: the rows of every subsystem this console writes.
def seal_stored(sealer: "Sealer | None", vars_, prefixes) -> int:
    if sealer is None:
        return 0
    sealed = skipped = 0
    for prefix in prefixes:
        for key in vars_.list(prefix):
            items, idx = vars_.get(key)
            if not items or items.get("deleted") == "true":
                continue
            # In the clear — or sealed before the row was bound into the ciphertext (opened by the field alone and
            # sealed again, to this row) — or sealed under an OLDER key: the rotation (the review's question 5). A
            # new key goes on top of the file and seals what is written from then on; what was sealed before stays
            # under the old kid for ever, and the old line could never leave the file. So the console, starting,
            # re-seals those under the current key, the revision standing still. Order matters, and is the
            # operator's: the holders restart first (they read the key file at start), THEN the console — a
            # holder that does not know the new key yet cannot open what the console re-sealed with it.
            todo = {k: v for k, v in items.items() if is_secret_field(k) and v and not is_sealed(v)}
            try:
                todo.update({k: sealer.open(k, v, key, fallback=True) for k, v in items.items()
                             if is_secret_field(k) and is_sealed(v) and (not sealer.bound(k, v, key) or kid_of(v) != sealer.current)})
            except Sealed as e:
                log.warning("%s: a sealed value this process cannot open is left as it is (%s)", key, e)
            if not todo:
                continue
            try:
                vars_.put(key, {**items, **{k: sealer.seal(k, str(v), key) for k, v in todo.items()}}, cas=idx)
                sealed += 1
            except Conflict as e:                        # a row written meanwhile: sealed by its own write
                log.info("%s changed while being sealed (%s): its own write sealed it", key, e)
            except Exception as e:                       # noqa: BLE001 — the store refused or did not answer: said, not hidden
                skipped += 1
                log.warning("%s was NOT sealed (%s)", key, e)
    if sealed:
        log.warning("sealed the secrets of %d row(s) written before this console had a key", sealed)
    if skipped:
        log.warning("%d row(s) with secrets in the clear could not be sealed: the store refused or did not answer", skipped)
    return sealed


def new_key_file(path: str, kid: str = "k1", store: str | list[str] | tuple[str, ...] | None = None) -> None:
    """A key ring with one key, readable by its owner and its group — the clients of the secrets, `w2c-secrets`
    (the owner's decision, 4 October): 0640, whatever the umask; the group is the directory's, which is setgid to it
    (`w2c.tmpfiles`). Rotation: add a line ON TOP, by hand or by script. Never inside a store (`store`, a directory
    or several): a key beside the rows it protects protects nothing, and every backup of the store would carry both.
    Never over an existing file (`O_EXCL`): a key lost is every password sealed with it."""
    for one in ([store] if isinstance(store, str) else store or []):
        real, root = os.path.realpath(path), os.path.realpath(one)
        if real == root or real.startswith(root.rstrip(os.sep) + os.sep):
            raise ValueError(f"{path} is inside the store ({one}): put the key where the store and its backups are not")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    os.fchmod(fd, 0o640)                                 # a umask of 0077 would leave the group out
    with os.fdopen(fd, "w") as f:
        f.write(f"{kid} {_secrets.token_bytes(32).hex()}\n")


# The STORES under the platform's root — its rows, its objects, the cluster's journal — and not the root itself: the
# root holds `etc/` too, where the key belongs (`/etc/w2c/secrets/platform.key` is a link into `/data/platform/etc`).
def platform_stores(env: dict) -> list[str]:
    from .runtime import platform_dir
    return [os.path.join(platform_dir(env), d) for d in ("config", "objects", "configstore")]


if __name__ == "__main__":                              # python3 -m w2cplatform.sealing new /etc/w2c/secrets/platform.key
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "new":
        new_key_file(sys.argv[2], store=platform_stores(os.environ))
        print(f"a key ring with one key: {sys.argv[2]} (mode 0640, the directory's group: w2c-secrets) — read by the "
              "console and the workers that read secrets, which join that group")
    else:
        print("usage: python3 -m w2cplatform.sealing new <path>")
