"""A secret is SEALED in the store and opened only by the process that uses it."""
# ================================================================================================
# # sealing.py — the cluster's key, and `*_secret` fields at rest
#
# `secrets.py` keeps a secret off every screen and out of every copy that leaves the cluster. What it could not
# do, and said so: the ROW held the password in the clear, and whoever could read `<sub>/<rows>/*` — or copied
# the store's directory, or a backup of it — read every camera's password (the product's authentication note,
# section 3.6; the order agreed with it, feedback BP).
#
# THE KEY IS NOT IN THE STORE. That is the whole design, and everything else follows from it. A key kept beside
# the rows it protects protects nothing: a copy of the store is a copy of both. So the key is a FILE, given only
# to the processes that write a secret or use one:
#
#   the console     writes rows: it SEALS every `*_secret` value on the way in (`SpecController`)
#   the holder      opens the device: it OPENS the password at the last moment, for the pipeline (`VmsWorker`)
#
# and to nobody else — the controller, the resource, automation, the domain's agent and every backup read the
# row and get ciphertext. On a box the file is mounted into those two units only; in a cluster it is a Nomad
# variable the two jobs' policies may read, rendered into the same file by the job's template. One interface,
# `SECRETS_KEY=<path>`, both places.
#
#   file      lines `<kid> <64 hex digits>`; the FIRST is the current key. Rotating is adding a line on top:
#             new writes are sealed with it, and every older one still opens by the kid it names
#   value     `enc:v1:<kid>:<nonce>:<ciphertext>` — AES-256-GCM, the field's name as associated data, so a
#             sealed password pasted into another field does not open
#
# NO KEY IS STILL A MODE, AND IT SAYS SO. Without `SECRETS_KEY` a secret is written as it always was, and the
# console's log says, once, that secrets are stored in the clear. A value that IS sealed and a process with no
# key, or without the kid it names, is an error at the one place it matters — the camera does not start, and
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

PREFIX = "enc:v1:"
log = logging.getLogger("w2cplatform.sealing")


class Sealed(Exception):
    """A sealed value this process cannot open: no key, an unknown kid, or a value that was tampered with."""


def is_sealed(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


class Sealer:
    def __init__(self, keys: dict[str, bytes], current: str):
        if current not in keys or any(len(k) != 32 for k in keys.values()):
            raise ValueError("a key ring names its current key, and every key is 32 bytes")
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM     # only where there is a key to use it with
        self._aead = {kid: AESGCM(k) for kid, k in keys.items()}
        self.current = current

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

    def seal(self, field: str, value: str) -> str:
        if not value or is_sealed(value):
            return value
        nonce = _secrets.token_bytes(12)
        ct = self._aead[self.current].encrypt(nonce, value.encode(), field.encode())
        b = lambda x: base64.urlsafe_b64encode(x).decode().rstrip("=")
        return f"{PREFIX}{self.current}:{b(nonce)}:{b(ct)}"

    def open(self, field: str, value: str) -> str:
        if not is_sealed(value):
            return value
        kid, nonce, ct = value[len(PREFIX):].split(":")
        if kid not in self._aead:
            raise Sealed(f"{field} is sealed with key {kid!r}, which this process does not hold")
        d = lambda x: base64.urlsafe_b64decode(x + "=" * (-len(x) % 4))
        try:
            return self._aead[kid].decrypt(d(nonce), d(ct), field.encode()).decode()
        except Exception:                                # noqa: BLE001 — InvalidTag: tampered, or another field's
            raise Sealed(f"{field} does not open with key {kid!r}: altered, or copied from another field") from None


# The two operations the platform performs, with or without a key.
_said_clear = False


def seal_items(sealer: Sealer | None, items: dict) -> dict:
    """The row as it goes into the store: every `*_secret` value sealed — when there is a key."""
    global _said_clear
    if sealer is None:
        if not _said_clear and any(is_secret_field(k) and v for k, v in items.items()):
            _said_clear = True
            log.warning("secrets are stored in the CLEAR: this process has no SECRETS_KEY, and whoever reads or copies "
                        "the store reads every device password")
        return items
    return {k: (sealer.seal(k, str(v)) if is_secret_field(k) and v else v) for k, v in items.items()}


def open_row(sealer: Sealer | None, row: dict) -> dict:
    """The row as the process that USES a secret needs it. A sealed value and no key raise `Sealed`."""
    out = dict(row)
    for k, v in row.items():
        if is_secret_field(k) and is_sealed(v):
            if sealer is None:
                raise Sealed(f"{k} is sealed and this process has no key (SECRETS_KEY)")
            out[k] = sealer.open(k, v)
    return out


# Rows written BEFORE the key existed (feedback CD). `seal_items` seals a row the next time it is written, and a
# camera nobody touches is never written again: its password would lie in the clear for years beside rows that
# are sealed. So the console, starting with a key, seals what is stored — the value only, in place, by CAS: the
# revision does not move, because nothing the row MEANS has changed, and a revision that moved would restart
# every pipeline for a password it already has. `prefixes`: the rows of every subsystem this console writes.
def seal_stored(sealer: "Sealer | None", vars_, prefixes) -> int:
    if sealer is None:
        return 0
    sealed = 0
    for prefix in prefixes:
        for key in vars_.list(prefix):
            items, idx = vars_.get(key)
            if not items or items.get("deleted") == "true":
                continue
            todo = {k: v for k, v in items.items() if is_secret_field(k) and v and not is_sealed(v)}
            if not todo:
                continue
            try:
                vars_.put(key, {**items, **{k: sealer.seal(k, str(v)) for k, v in todo.items()}}, cas=idx)
                sealed += 1
            except Exception as e:                       # noqa: BLE001 — a row written meanwhile: sealed by its own write
                log.info("%s changed while being sealed (%s): its own write sealed it", key, e)
    if sealed:
        log.warning("sealed the device secrets of %d row(s) written before this console had a key", sealed)
    return sealed


def new_key_file(path: str, kid: str = "k1", store: str | None = None) -> None:
    """A key ring with one key, readable by its owner only. Rotation: add a line ON TOP, by hand or by script.
    Never inside the store (`store`, the platform's directory): a key beside the rows it protects protects nothing,
    and every backup of the store would carry both. Never over an existing file (`O_EXCL`): a key lost is every
    password sealed with it."""
    if store:
        real, root = os.path.realpath(path), os.path.realpath(store)
        if real == root or real.startswith(root.rstrip(os.sep) + os.sep):
            raise ValueError(f"{path} is inside the store ({store}): put the key where the store and its backups are not")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"{kid} {_secrets.token_bytes(32).hex()}\n")


if __name__ == "__main__":                              # python3 -m w2cplatform.sealing new /data/secrets/vms.key
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "new":
        new_key_file(sys.argv[2], store=os.environ.get("PLATFORM_DIR", "/data/platform"))
        print(f"a key ring with one key: {sys.argv[2]} (mode 0600) — mount it into the console and the holders only")
    else:
        print("usage: python3 -m w2cplatform.sealing new <path>")
