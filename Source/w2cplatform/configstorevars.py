"""configstore:// — the replicated config store, as a process opens it: plain HTTP over the unix socket of the daemon
on its own server (`configstore.py`). Standard library only; a process that opens it never imports a raft library."""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # configstorevars.py — the handle
#
# **Role.** `open_vars("configstore:///run/configstore/<unit>.sock")` — `PLATFORM_STORE` in the unit's environment
# (`variables.store_url`) — gives a `ConfigstoreVariables`, and no subsystem can tell it from `file://`: the same
# five calls, the same `(None, 0)`, the same `Conflict` (the seam, М10A lesson 3). Who is leader is the daemon's
# business; the handle talks to the socket of its own server and to nothing else.
#
# The socket IS the identity: the daemon opens one per role (`/run/configstore/<role>.sock`, its group
# `configstore.socket_group`) and checks the role's rights before anything is forwarded (`storemachine.Rights`). `as_writer` stays as a second,
# client-side check, as in `FileVariables` — a process that opened the wrong socket learns it here first.
#
# ## The wire, mapped back to the contract
#   index ""  ↔ 0 (absent)          cas=0 → ""  (create-only)       cas=None → null (no CAS)
#   409 → `Conflict`   403 → `Forbidden`   400 → `ValueError` (not a key, as `safe_path` says it)
#   413 toolarge → `TooLarge` (a row over `storemachine.MAX_VALUE`)
#   503 unavailable → `StoreUnavailable`   503 ambiguous → `StoreAmbiguous`
# Both store errors are `OSError`s, which every caller already reads as "the store did not answer" — a worker keeps
# what it holds and tries again (feedback BC) — and never as "no". `StoreAmbiguous` says more: a write that may
# have landed. A caller that cares re-reads before writing again; one that does not, reads it as the plain kind.
#
# ## A daemon killed mid-answer is not an answer
# Found by the prototype's measurement at the fifteenth leader kill: headers sent, the body never — and
# `http.client.IncompleteRead` is an `HTTPException`, not an `OSError`; it flew out of `renew_slot` and killed the
# worker's thread. A cut body, a body that does not parse, a connection closed before any answer: unavailable,
# and for a write ambiguous, since it was sent. Never `ValueError`, which a caller reads as "not a key".
#
# ## A refused connection is tried again, within D
# A daemon restarting (systemd brings it back in a second or two) has no socket, or a socket nobody accepts on:
# `FileNotFoundError`, `ConnectionRefusedError`. Nothing was sent, so trying again is safe for a write too — for up
# to `REFUSED_WAIT` (D = 5 s), and a daemon restart stops costing every worker on the server its lease step
# (the notes on the raft prototype, "what to change", point 2). Past D it is unavailable like any silence.
#
# ## The operation id
# Made here (`id` in the write): the daemon retries a write inside its wait with the same id, and the machine answers
# a repeat with its first answer (`storemachine.StoreMachine`) — a CAS that would otherwise conflict with its own
# first copy and fence the worker.
#
# ONE ID PER OPERATION, NOT PER CALL (the review's twelfth pass, minor). A caller that got `StoreAmbiguous` and asked
# for the same write again — the lease loop does — made a new id, so a first copy that had landed meanwhile was not
# recognised: the CAS conflicted with it. A write whose outcome this handle does not know keeps its id
# (`_unknown`, by the write's whole content: op, key, items, cas); the same write asked again is sent with it, and is
# answered once. A definite answer — the index, `Conflict`, `Forbidden`, a bad key — forgets it. A different write
# to the same key is another operation, with an id of its own.
#
# …AND A LATER WRITE TO THE KEY ENDS IT (the review's thirteenth pass, major 4). The id was kept by content until a
# definite answer to THAT content, so `put on` (ambiguous: it landed), `put off` (OK), `put on` again went with the
# first `on`'s id and was answered from the machine's memory — «OK», and the row stayed `off`. The same with delete,
# put, delete and with create-only. A repeat is a repeat only of the LAST write asked of its key: one remembered
# write per key (`_Unknown`), replaced by any other write to that key and forgotten by any definite answer to one.
# Asked again after another write, the old content is a new operation, with a new id, and is applied. The machine
# holds the same line from its side: an id that comes back with another write is refused, not answered
# (`storemachine._fingerprint`).
#
# ## A row has the store's ceiling
# `storemachine.MAX_VALUE` is declared as this handle's `max_bytes` (a URL may declare less), so an oversized row is
# `TooLarge` here as on any store that has a ceiling (`limits.py`) — and the daemon's 413 is the same exception.
#
# ## Deadline
# `timeout` is what one call may take, the daemon's own retries included. The daemon is told a little less in
# `X-Deadline`, so its 503 with a reason arrives before our socket gives up.
# ================================================================================================
from __future__ import annotations

import collections
import http.client
import json
import random
import threading
import time
import urllib.parse
import uuid

from .limits import TooLarge, check
from .storemachine import MAX_VALUE                 # the machine and the API, no raft and no socket
from .variables import (KEY_BYTES, STORE_SCHEME, Conflict, Forbidden, KeyTooLong, items_bytes, refuse_delete,
                        register_scheme, safe_path)

REFUSED_WAIT = 5.0         # D: how long a refused connection to this server's daemon is tried again
REFUSED_STEP = 0.1         # …about this often, give or take half
UNKNOWN_KEPT = 64          # writes of unknown outcome whose ids a handle keeps for their repeat


class StoreUnavailable(OSError):
    """The store did not answer: no leader within the wait, the daemon gone, an answer cut off. Not a refusal."""


class StoreAmbiguous(StoreUnavailable):
    """A write was sent and its outcome is unknown: it may yet be applied. Read before writing it again."""


# -- the transport ------------------------------------------------------------------------------------
# One request over the unix socket. `socket.AF_UNIX` is asked for here, inside the call: it is not there on every
# platform, and the platform must still import where it is not (`test_portability`).
class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float):
        super().__init__("configstore", timeout=timeout)
        self.unix_path = path

    def connect(self):
        import socket
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        try:
            s.connect(self.unix_path)
        except BaseException:
            s.close()
            raise
        self.sock = s


class _NotConnected(Exception):
    """Refused before anything was sent: safe to try again."""


def unix_transport(path: str):
    def call(method: str, target: str, raw: bytes | None, headers: dict, timeout: float) -> tuple[int, bytes]:
        conn = _UnixConnection(path, timeout)
        try:
            try:
                conn.connect()
            except (FileNotFoundError, ConnectionRefusedError) as e:
                raise _NotConnected(f"{type(e).__name__}: {path}") from None
            conn.request(method, target, body=raw, headers=headers)
            r = conn.getresponse()
            return r.status, r.read()
        finally:
            conn.close()
    return call


# The writes of unknown outcome a handle remembers: the last write asked of a key, when its outcome is unknown — one
# per key, the newest `UNKNOWN_KEPT` keys; shared by a handle's `as_writer` copies, which a process's threads use at
# once. `what` is the write's whole content; its id is handed out again only for the same content.
class _Unknown:
    def __init__(self):
        self.ids: collections.OrderedDict[str, tuple[str, str]] = collections.OrderedDict()   # key → (what, id)
        self.lock = threading.Lock()

    def get(self, key: str, what: str) -> str | None:
        with self.lock:
            kept = self.ids.get(key)
            return kept[1] if kept and kept[0] == what else None

    def keep(self, key: str, what: str, op_id: str) -> None:
        with self.lock:
            self.ids[key] = (what, op_id)
            self.ids.move_to_end(key)
            while len(self.ids) > UNKNOWN_KEPT:
                self.ids.popitem(last=False)

    def forget(self, key: str) -> None:
        with self.lock:
            self.ids.pop(key, None)


class ConfigstoreVariables:
    """The handle. `path` is this server's daemon socket for the role; `transport` replaces the socket in a stand
    (`storemachine.local_transport`)."""

    def __init__(self, path: str, writer: str | None = None, acl: dict[str, list[str]] | None = None,
                 max_bytes: int = MAX_VALUE, timeout: float = 5.0, transport=None, unknown=None):
        self.path = path
        self.writer, self.acl = writer, dict(acl or {})
        # The daemon's ceiling, or less when the URL declares less, like `memory://` (twelfth pass).
        self.max_bytes = min(max_bytes, MAX_VALUE) if max_bytes else MAX_VALUE
        self.timeout = timeout
        self.transport = transport or unix_transport(path)
        self._unknown = _Unknown() if unknown is None else unknown     # write → its id; see the notes

    def as_writer(self, writer: str, allowed: list[str]) -> "ConfigstoreVariables":
        return ConfigstoreVariables(self.path, writer, {**self.acl, writer: allowed}, self.max_bytes, self.timeout,
                                    self.transport, self._unknown)

    # A write, with the id of the same write whose outcome is unknown — the last one asked of its key — or a new one.
    def _write(self, body: dict) -> dict:
        key, what = body["key"], json.dumps(body, sort_keys=True)
        op_id = self._unknown.get(key, what) or uuid.uuid4().hex
        try:
            got = self._call("POST", "/v1/write", {**body, "id": op_id})
        except StoreUnavailable:
            self._unknown.keep(key, what, op_id)   # "not done" this time; an earlier copy may still land
            raise
        except BaseException:
            self._unknown.forget(key)
            raise
        self._unknown.forget(key)
        return got

    def _refuse(self, path: str) -> None:
        from .rights import refusal                  # the platform's one evaluator: `!` denials first (`rights.py`)
        why = refusal(self.writer, self.acl, path)
        if why:
            raise Forbidden(why)

    # The same longest key `FileVariables` takes, refused the same way: a box's rows and a cluster's are one set.
    @staticmethod
    def _too_long(path: str) -> int:
        n = len(safe_path(path).replace("%", "%25").replace("/", "%2F").encode())
        return n if n > KEY_BYTES else 0

    def _call(self, method: str, target: str, body: dict | None = None) -> dict:
        write = body is not None
        raw = None if body is None else json.dumps(body).encode()
        headers = {"Content-Type": "application/json", "X-Deadline": f"{max(0.1, self.timeout - 0.5):.3f}"}
        start = time.monotonic()
        while True:
            try:
                code, got = self.transport(method, target, raw, headers, self.timeout)
                break
            except _NotConnected as e:
                if time.monotonic() - start >= min(REFUSED_WAIT, self.timeout):
                    raise StoreUnavailable(f"the store's daemon is not there: {e}") from None
                # …each caller at its own moment: every process of the server lost the daemon at once, and in step
                # they reached its new socket at once (the product's cross-check, its pusher's 2 s exactly).
                time.sleep(REFUSED_STEP * random.uniform(0.5, 1.5))
            except (OSError, http.client.HTTPException) as e:
                kind = StoreAmbiguous if write else StoreUnavailable
                raise kind(f"the store did not answer: {type(e).__name__}: {e}") from None
        try:
            said = json.loads(got or b"{}")
            if not isinstance(said, dict):
                raise ValueError("not an object")
        except ValueError:
            kind = StoreAmbiguous if write and code == 200 else StoreUnavailable
            raise kind(f"the store's answer did not parse: {code} {got[:40]!r}") from None
        if code == 200:
            return said
        error = str(said.get("error", ""))
        if code == 409:
            raise Conflict(error or "conflict")
        if code == 403:
            raise Forbidden(error or "forbidden")
        if code == 400:
            raise ValueError(error or "not a key")
        if code == 413 and said.get("kind") == "toolarge":
            raise TooLarge(str((body or {}).get("key", "")), int(said.get("size") or 0),
                           int(said.get("limit") or MAX_VALUE))
        if code == 503 and said.get("kind") == "unavailable":
            raise StoreUnavailable(f"the store did not answer: {error}")
        if code == 503 and said.get("kind") == "ambiguous":
            raise StoreAmbiguous(f"the write's outcome is unknown: {error}")
        kind = StoreAmbiguous if write else StoreUnavailable
        raise kind(f"the store did not answer: {code} {said.get('kind', '')} {error}".strip())

    def get(self, path: str) -> tuple[dict | None, int]:
        if self._too_long(path):
            return None, 0                        # nothing could have been written under it
        got = self._call("GET", "/v1/get?" + urllib.parse.urlencode({"key": path}))
        index = got.get("index")
        return got.get("items"), (0 if index in ("", None) else index)

    def put(self, path: str, items: dict, cas=None):
        safe_path(path)
        self._refuse(path)
        check(path, items_bytes(items), self.max_bytes)
        n = self._too_long(path)
        if n:
            raise KeyTooLong(path, n)
        body = {"op": "put", "key": path, "items": {str(k): str(v) for k, v in items.items()},
                "cas": "" if cas == 0 and not isinstance(cas, bool) else cas}
        return self._write(body)["index"]

    def delete(self, path: str, cas=None) -> None:
        safe_path(path)
        refuse_delete(path, self.writer, self.acl)
        if self._too_long(path):
            return
        self._write({"op": "delete", "key": path, "cas": "" if cas == 0 and not isinstance(cas, bool) else cas})

    def list(self, prefix: str) -> list[str]:
        return sorted(self._call("GET", "/v1/list?" + urllib.parse.urlencode({"prefix": prefix}))["keys"])

    def status(self) -> dict:
        return self._call("GET", "/v1/status")


# `configstore:///run/configstore/<role>.sock[?max_bytes=n&timeout=s]` — this server's daemon, by the role's socket.
def _open(url: str, writer: str | None = None, acl: dict[str, list[str]] | None = None) -> ConfigstoreVariables:
    rest = url[len(STORE_SCHEME) + len("://"):]
    where, _, query = rest.partition("?")
    opts = dict(urllib.parse.parse_qsl(query))
    if not where.startswith("/"):
        raise ValueError(f"{STORE_SCHEME}:// names this server's daemon socket: "
                         f"{STORE_SCHEME}:///run/configstore/<role>.sock")
    return ConfigstoreVariables(where, writer, acl, int(opts.get("max_bytes") or MAX_VALUE),
                                float(opts.get("timeout", 5.0)))


register_scheme(STORE_SCHEME, _open)
