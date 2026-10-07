"""Stream clients — the accounts of RTSP outward (the product's `vms/streamclients.go`; ADR-0031, the addendum of
2026-10-07: the course carries them as the product does).

A video wall, another VMS, an analytics server: a DEVICE, not a person — it is given a password once and keeps it, and
it speaks RTSP with Digest, not tokens. So it is an account of its own kind, kept by the holder beside the people, with
grants like a person's: the cameras it may play are the cameras it may view.

    domain/vms/stream-clients/<name>   the holder's: {doc: {name, disabled, at, by}, password_secret}
    domain/vms/stream-accounts         a cluster's: {accounts_secret: {name: password}} — the clients that have a grant
                                       there, carried home by its agent (the book `stream-accounts/<cluster>` the VMS's
                                       worker on the domain writes at the holder, `domainpart/streamclients.py`); the
                                       holder reads its own records

Who reads them is the spec's (ADR-0024): the VMS's worker on the domain keeps the clients (`secrets.readers`), the
domain's processes carry the book, the live gateway reads both (`live.subsystem.yaml`, `secrets.reads`). The names are
the spec's too: the family is `domain.kept` (`stream-clients/`), its rows are subjects of the grants beside the people
(`domain.names`: a person and a client never share a name, a client is granted at most `view` — the platform refuses
either on every write of the holder's store, `w2cplatform.domain.declared`), and the book is `domain.books`. A spec that
declares none of it carries nothing: no client is made, no book is written, and the gateway's RTSP door stays shut.

Both secrets are sealed with the ring of the process that writes them (`SECRETS_KEY`; `w2cplatform.sealing`): the
holder's worker seals the password and the book, the platform seals the book again to the member's key on the way and
with the member's ring at home, and the gateway that takes the accounts opens them.

The password is the system's — long and random — and kept as it is: Digest proves it with an MD5 the server computes
from it, so what the server keeps is as good as the password whatever form it takes. That is why it is random (nothing
to guess from its hash), and why a cluster is carried only the clients it has granted.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass

from w2cplatform.rows import PARSE_ERRORS

from .config import SPEC

# The names, as the product's spec spells them (`vms.subsystem.yaml`: `domain.kept`, `domain.books`).
CLIENTS_FAMILY = "stream-clients/"
ACCOUNTS_BOOK = "stream-accounts"
STREAM_CLIENTS_PREFIX = SPEC.domain_prefix + CLIENTS_FAMILY
STREAM_ACCOUNTS_KEY = SPEC.domain_prefix + ACCOUNTS_BOOK
PASSWORD = "password_secret"
ACCOUNTS = "accounts_secret"


def _vms_spec():
    """The VMS's spec as this process holds it NOW — the catalogue's (`w2cplatform.domain.declared`), so a spec loaded or
    changed later is what the next call reads."""
    from w2cplatform.domain.declared import spec
    return spec(SPEC.name)


def clients_declared() -> bool:
    """The VMS's spec keeps the family of stream clients at the holder (`domain.kept: [stream-clients/]`)."""
    s = _vms_spec()
    return s is not None and CLIENTS_FAMILY in s.domain.kept


def book_declared() -> bool:
    """The VMS's spec declares the book of the accounts a cluster is granted (`domain.books: {stream-accounts: {}}`)."""
    s = _vms_spec()
    return s is not None and ACCOUNTS_BOOK in s.domain.books


def reads_declared(spec) -> bool:
    """`spec` (a process's own: the live gateway's) says it reads the clients and the accounts (`secrets.reads`)."""
    reads = set(getattr(spec, "secret_reads", ()) or ())
    return {STREAM_CLIENTS_PREFIX, STREAM_ACCOUNTS_KEY} <= reads


@dataclass
class StreamClient:
    """One RTSP account, without its password."""
    name: str
    disabled: bool = False
    at: float = 0.0
    by: str = ""

    def to_doc(self) -> dict:
        """As the product writes it: `name` always, the rest only when said (`omitempty`)."""
        out: dict = {"name": self.name}
        if self.disabled:
            out["disabled"] = True
        if self.at:
            out["at"] = self.at
        if self.by:
            out["by"] = self.by
        return out

    @classmethod
    def from_doc(cls, doc) -> "StreamClient | None":
        if not isinstance(doc, dict) or not isinstance(doc.get("name"), str) or not doc["name"]:
            return None
        at = doc.get("at", 0)
        return cls(doc["name"], doc.get("disabled") is True, float(at) if isinstance(at, (int, float)) else 0.0,
                   str(doc.get("by") or ""))


def new_stream_password() -> str:
    """A password the system makes: 32 characters, nothing to guess."""
    return base64.urlsafe_b64encode(os.urandom(24)).decode().rstrip("=")


def _opened(row: str, field: str, items: dict, sealer) -> str:
    """`items[field]` opened with `sealer`; "" when it is not there or does not open here (the product's
    `trust.Opened`): a password this process cannot read is no password, never the ciphertext."""
    from w2cplatform.sealing import Sealed, open_row
    try:
        return str(open_row(sealer, {field: items.get(field, "")}, row).get(field) or "")
    except (Sealed, ValueError):
        return ""


def read_stream_client(vars_, name: str, sealer=None) -> tuple[StreamClient | None, str]:
    """One client and its password; `(None, "")` when there is none of that name (or its record does not read)."""
    row = STREAM_CLIENTS_PREFIX + name
    items, _ = vars_.get(row)
    if not items or not items.get("doc"):
        return None, ""
    try:
        c = StreamClient.from_doc(json.loads(items["doc"]))
    except PARSE_ERRORS:
        return None, ""
    if c is None:
        return None, ""
    return c, _opened(row, PASSWORD, items, sealer)


def stream_clients(vars_, sealer=None) -> list[StreamClient]:
    """Every client, by name."""
    out = []
    for k in vars_.list(STREAM_CLIENTS_PREFIX):
        name = k[len(STREAM_CLIENTS_PREFIX):]
        if not name or "/" in name:
            continue
        c, _ = read_stream_client(vars_, name, sealer)
        if c is not None:
            out.append(c)
    return sorted(out, key=lambda c: c.name)


def accounts_for(vars_, cluster: str, sealer=None) -> dict[str, str]:
    """What the holder hands a cluster: name → password of every client, not disabled, that a line of the cluster's
    grants names."""
    from w2cplatform.domain.agent import GRANTS_PATH
    from w2cplatform.domain.grants import grants_from_items
    path = f"{GRANTS_PATH}/{cluster}"
    named = {g.subject for g in grants_from_items(vars_.get(path)[0], path)}
    out = {}
    for c in stream_clients(vars_, sealer):
        if c.name in named and not c.disabled:
            _, password = read_stream_client(vars_, c.name, sealer)
            if password:
                out[c.name] = password
    return out


def holds(vars_) -> bool:
    """This store holds the domain's keys (the signer's row, `trust.signer.SIGNER_ROW`, with its issuing key — sealed,
    never opened here). A store that will not let this process read the row: not the holder."""
    from w2cplatform.trust.signer import SIGNER_ROW
    try:
        items, _ = vars_.get(SIGNER_ROW)
    except Exception:                                    # noqa: BLE001 — refused by the rights: not ours, so not held
        return False
    return bool(items) and "issuing_key_secret" in items


def stream_accounts(vars_, cluster: str, sealer=None) -> dict[str, str]:
    """The accounts a cluster's RTSP door takes: on the holder, which nobody carries anything to, its own records — not
    what was carried when it was a member; elsewhere what its agent carried; with nothing carried, the records (none in
    a member's store, so nothing). Nothing at all in a domain not installed: nobody plays."""
    if holds(vars_):
        return accounts_for(vars_, cluster, sealer)
    items, _ = vars_.get(STREAM_ACCOUNTS_KEY)
    if items and items.get(ACCOUNTS):
        raw = _opened(STREAM_ACCOUNTS_KEY, ACCOUNTS, items, sealer)
        try:
            got = json.loads(raw) if raw else {}
        except PARSE_ERRORS:
            got = {}
        return {str(k): str(v) for k, v in got.items() if isinstance(v, str) and v} if isinstance(got, dict) else {}
    return accounts_for(vars_, cluster, sealer)
