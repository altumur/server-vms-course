"""configstore:// — the replicated config store, as a process opens it: plain HTTP over the unix socket of the daemon
on its own server (`configstore.py`). Standard library only; a process that opens it never imports a raft library."""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # configstorevars.py — the handle
#
# **Role.** `open_vars("configstore:///run/configstore/vmsworker.sock")` — `PLATFORM_STORE` in the unit's environment
# (`variables.store_url`) — gives a `ConfigstoreVariables`, and nothing in `vms/` can tell it from `file://`: the same
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
# Made here, once per call (`id` in the write): the daemon retries a write inside its wait with the same id, and the
# machine answers a repeat with its first answer (`storemachine.StoreMachine`) — a CAS that would otherwise conflict
# with its own first copy and fence the worker.
#
# ## Deadline
# `timeout` is what one call may take, the daemon's own retries included. The daemon is told a little less in
# `X-Deadline`, so its 503 with a reason arrives before our socket gives up.
# ================================================================================================
from __future__ import annotations

import http.client
import json
import time
import urllib.parse
import uuid

from .limits import NO_CEILING, check
from .variables import (KEY_BYTES, STORE_SCHEME, Conflict, Forbidden, KeyTooLong, items_bytes, refuse_delete,
                        register_scheme, safe_path)

REFUSED_WAIT = 5.0         # D: how long a refused connection to this server's daemon is tried again


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


class ConfigstoreVariables:
    """The handle. `path` is this server's daemon socket for the role; `transport` replaces the socket in a stand
    (`storemachine.local_transport`)."""

    def __init__(self, path: str, writer: str | None = None, acl: dict[str, list[str]] | None = None,
                 max_bytes: int = NO_CEILING, timeout: float = 5.0, transport=None):
        self.path = path
        self.writer, self.acl = writer, dict(acl or {})
        self.max_bytes = max_bytes                # declared on the URL, like `memory://`: the daemon has no ceiling
        self.timeout = timeout
        self.transport = transport or unix_transport(path)

    def as_writer(self, writer: str, allowed: list[str]) -> "ConfigstoreVariables":
        return ConfigstoreVariables(self.path, writer, {**self.acl, writer: allowed}, self.max_bytes, self.timeout,
                                    self.transport)

    def _refuse(self, path: str) -> None:
        if self.writer is None or not self.acl:
            return
        allowed = self.acl.get(self.writer, [])
        if not any(path == p or (p.endswith("*") and path.startswith(p[:-1])) for p in allowed):
            raise Forbidden(f"{self.writer} may not write {path}")

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
                time.sleep(0.1)
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
                "cas": "" if cas == 0 and not isinstance(cas, bool) else cas, "id": uuid.uuid4().hex}
        return self._call("POST", "/v1/write", body)["index"]

    def delete(self, path: str, cas=None) -> None:
        safe_path(path)
        refuse_delete(path, self.writer, self.acl)
        if self._too_long(path):
            return
        body = {"op": "delete", "key": path, "cas": "" if cas == 0 and not isinstance(cas, bool) else cas,
                "id": uuid.uuid4().hex}
        self._call("POST", "/v1/write", body)

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
    return ConfigstoreVariables(where, writer, acl, int(opts.get("max_bytes", NO_CEILING)),
                                float(opts.get("timeout", 5.0)))


register_scheme(STORE_SCHEME, _open)
