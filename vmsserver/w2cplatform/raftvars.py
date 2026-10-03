"""raft:// — the Variables contract replicated by raft. EXPERIMENTAL: a prototype for the owner's decision of
3 October (the cluster without an orchestrator: our own store replicated by raft in Nomad's place), not a backend
any process of the course is started with. What it measured is in the notes on the raft prototype."""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # raftvars.py — `FileVariables`' semantics on a raft group, and the daemon that holds the group
#
# **Role.** The note on the cluster without Nomad says: our own store, the same `Variables` contract with CAS,
# replicated over three servers by a real raft library — consensus is not something we write. This is that, as
# a prototype in Python: the library is `pysyncobj` (the only maintained pure-Python raft with dynamic
# membership and a journal; `pip install pysyncobj`). The product's choice is `hashicorp/raft`; what this file
# measures about the SHAPE (election pause against a lease, retries, joins) carries over, what it says about
# pysyncobj does not (see "what pysyncobj does not give" below).
#
# ## Two halves, two processes
# - `RaftVariables` — the handle a process opens: `open_vars("raft://127.0.0.1:8701")`. Plain HTTP to the
#   daemon on its own server, stdlib only: a process that opens the store never imports the raft library, and
#   `vms/` cannot tell it from `file://` (the lesson's seam, М10A lesson 3).
# - `RaftStore` — the daemon (`python -m w2cplatform.raftvars serve …`), one per server beside `obsd`: a raft
#   node, its journal and dump in a directory, an HTTP door for the processes of that server. A write or a read
#   for CAS that arrives at a follower is forwarded to the leader by the library itself.
#
# Why a daemon and not a raft node in every process: a server runs a console, controllers and workers, and a
# group of fifteen voters that changes every time a worker restarts is not a group. The note says the same.
#
# ## The state machine — `FileVariables`, to the letter
# One JSON-able row per key (`{key: str}`), the key's version is the raft index of the entry that last wrote
# it, absent is `(None, 0)`, `put` with `cas` passes only if the version has not moved, `cas=0` is create-only,
# `delete` takes a `cas` too and burns an index (every entry has one), `list` by prefix. The index is unique
# for the life of the group's log and never reused, so a CAS remembered from before a restart still conflicts.
#
# READS GO THROUGH THE LOG. `get` and `list` are replicated commands: the answer is what the state machine
# held at that entry, on the leader of that term — linearizable, at the price of one log entry per read.
# pysyncobj has no ReadIndex and no leader lease; this is the one linearizable read it allows. `reads=local`
# on the URL reads the daemon's own copy instead (a follower may be behind): for a reader that only displays.
# A lease renewal is a READ here (`Lease.renew` reads the epoch row), so it must not be local: a follower cut
# off from the group would go on confirming an epoch the others have already moved.
#
# ## A retried write is applied once
# During an election a command can fail with "leader changed" or "unknown outcome" AFTER the old leader
# appended it — it may yet commit. Retrying it blindly makes a CAS conflict with its own first copy: a slot
# renewal that comes back `Conflict` FENCES the worker (`Worker._renew_slot`). So every write carries an
# operation id from the handle, the daemon retries with the same id until its deadline, and the state machine
# remembers the last `OP_MEMORY` results by id and answers a repeat with the first answer (the client sessions of
# the Raft dissertation, § 6.3). `test_a_write_retried_after_its_first_copy_landed_is_applied_once`.
#
# ## What the daemon answers
#   200   done; a read's row or a write's index
#   409   `Conflict`: the version moved — the body says what it is now
#   400   not a key (`safe_path`), or a request the door does not understand
#   503   no leader answered within the deadline: NOT a refusal. The handle raises `RaftUnavailable`, an
#         `OSError`, which every caller already reads as "the store did not answer" (a worker keeps what it
#         holds and tries again; feedback BC). A write that timed out may still land: its outcome is unknown,
#         as with any store over a network
#
# ## One server, then three
# A box is a group of one (`serve` with no peers): it elects itself, and its store is the cluster's from day
# one, so there is no migration when the second and third servers come (the note, point 5). A new server is
# started with `--join <http of a member>`: it asks the member who is in the group, starts with them as
# partners, and asks the member to add it; the leader then sends it the log (or a dump). One member at a time,
# and each started BEFORE it is added — a group of one that adds a second voter which is not there yet has
# lost its majority.
#
# ## What pysyncobj does not give (and the product's library does)
# - the journal is a memory-mapped file with no fsync before an entry is acknowledged: it survives a killed
#   process, not a power cut of a majority. `FileVariables` has its barriers for exactly that (feedback BD)
# - peers speak pickle: an unauthenticated peer port is code execution. `password=` encrypts; mTLS is the plan
# - no pre-vote and no leader lease; a leader cut off from the others steps down only after
#   `leaderFallbackTimeout` (30 s by default) — harmless for correctness here, because reads go through the log
# ================================================================================================
from __future__ import annotations

import argparse
import collections
import http.client
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .limits import NO_CEILING, check
from .variables import Conflict, Forbidden, items_bytes, refuse_delete, register_scheme, safe_path


class RaftUnavailable(OSError):
    """No leader answered in time: the store did not answer — not a refusal, and not a confirmation."""


# -- the handle -------------------------------------------------------------------------------------
# What a process holds. `base` is the daemon's HTTP (`http://127.0.0.1:8701`); `writer` and `acl` mean what they
# mean in `FileVariables` and belong to the handle (memvariables, m3). The ACL is checked HERE, as the file
# store checks it in the process: until mTLS the daemon cannot know who calls (deferred by the owner).
class RaftVariables:
    def __init__(self, base: str, writer: str | None = None, acl: dict[str, list[str]] | None = None,
                 max_bytes: int = NO_CEILING, timeout: float = 5.0, reads: str = "leader"):
        self.base = base.rstrip("/")
        self.writer, self.acl = writer, dict(acl or {})
        self.max_bytes = max_bytes
        self.timeout = timeout                   # what one call may take, the daemon's own retries included
        self.reads = reads                       # "leader" (through the log) or "local" (this daemon's copy)

    def as_writer(self, writer: str, allowed: list[str]) -> "RaftVariables":
        return RaftVariables(self.base, writer, {**self.acl, writer: allowed}, self.max_bytes, self.timeout, self.reads)

    def _refuse(self, path: str) -> None:
        if self.writer is None or not self.acl:
            return
        allowed = self.acl.get(self.writer, [])
        if not any(path == p or (p.endswith("*") and path.startswith(p[:-1])) for p in allowed):
            raise Forbidden(f"{self.writer} may not write {path}")

    # One request to the daemon. The daemon gets a deadline a little shorter than ours, so a 503 with a reason
    # arrives before our socket gives up; a socket that gives up is the same answer without one.
    #
    # A DAEMON KILLED IN THE MIDDLE OF ITS ANSWER is not an answer either. It sent the headers and died before the
    # body: `http.client.IncompleteRead`, which is an `HTTPException` and NOT an `OSError` — it flew out of the
    # handle, out of `renew_slot`, and killed the measurement's worker thread at the fifteenth leader kill. A body
    # that does not parse is the same. Both are "the store did not answer" (`RaftUnavailable`), never `ValueError`,
    # which a caller reads as "not a key". `test_an_answer_cut_off_by_a_dying_daemon_is_not_an_answer`.
    def _call(self, method: str, route: str, query: dict | None = None, body: dict | None = None) -> dict:
        q = dict(query or {})
        q["deadline"] = f"{max(0.1, self.timeout - 0.5):.3f}"
        url = f"{self.base}{route}?{urllib.parse.urlencode(q)}"
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read()
        except urllib.error.HTTPError as e:
            try:
                said = json.loads(e.read() or b"{}")
            except (ValueError, OSError, http.client.HTTPException):
                said = {}
            if e.code == 409:
                raise Conflict(said.get("error", "conflict")) from None
            if e.code == 400:
                raise ValueError(said.get("error", "bad request")) from None
            raise RaftUnavailable(f"the store did not answer: {e.code} {said.get('error', '')}".strip()) from None
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            raise RaftUnavailable(f"the store did not answer: {type(e).__name__}: {e}") from None
        try:
            return json.loads(raw or b"{}")
        except ValueError:
            raise RaftUnavailable(f"the store's answer did not parse: {raw[:40]!r}") from None

    def get(self, path: str) -> tuple[dict | None, int]:
        safe_path(path)
        got = self._call("GET", "/v1/get", {"path": path, "reads": self.reads})
        return got["items"], int(got["index"])

    # The operation id is made HERE, once per call: the daemon's retries inside its deadline carry it, and the
    # state machine answers a repeat with the first answer instead of a conflict with itself.
    def put(self, path: str, items: dict, cas: int | None = None) -> int:
        safe_path(path)
        self._refuse(path)
        check(path, items_bytes(items), self.max_bytes)
        body = {"path": path, "items": {str(k): str(v) for k, v in items.items()}, "cas": cas, "op": uuid.uuid4().hex}
        return int(self._call("POST", "/v1/put", body=body)["index"])

    def delete(self, path: str, cas: int | None = None) -> None:
        safe_path(path)
        refuse_delete(path, self.writer, self.acl)
        self._call("POST", "/v1/delete", body={"path": path, "cas": cas, "op": uuid.uuid4().hex})

    def list(self, prefix: str) -> list[str]:
        return list(self._call("GET", "/v1/list", {"prefix": prefix, "reads": self.reads})["keys"])

    def status(self) -> dict:
        return self._call("GET", "/v1/status")


# `raft://<host>:<port>[?max_bytes=n&timeout=s&reads=local]` — the daemon on this server. The query says which
# store this is and how it is read, as `memory://`'s does.
def _open(url: str, writer: str | None = None, acl: dict[str, list[str]] | None = None) -> RaftVariables:
    rest = url[len("raft://"):]
    where, _, query = rest.partition("?")
    opts = dict(urllib.parse.parse_qsl(query))
    if not where:
        raise ValueError("raft:// needs the address of this server's store daemon: raft://127.0.0.1:8701")
    return RaftVariables("http://" + where.rstrip("/"), writer, acl, int(opts.get("max_bytes", NO_CEILING)),
                         float(opts.get("timeout", 5.0)), opts.get("reads", "leader"))


register_scheme("raft", _open)


# -- the daemon -------------------------------------------------------------------------------------
# The library is imported here and only here: a process that opens `raft://` never needs it, and `import
# w2cplatform.raftvars` works on a box where it is not installed (the portability test imports every module).
OP_MEMORY = 50_000         # results remembered by operation id; a retry comes within seconds, this is hours of writes

# Timings by name, for the daemon's command line and the measurements. `defaults` is the library's own
# (election 0.4–1.4 s, heartbeat 0.1 s); `fast` is what a LAN of three can afford; `slow` is a loaded box or a
# WAN — the shape Consul ships (five times its LAN timings).
TIMINGS = {
    "defaults": {},
    "fast": {"raftMinTimeout": 0.15, "raftMaxTimeout": 0.35, "appendEntriesPeriod": 0.03, "connectionTimeout": 1.0,
             "connectionRetryTime": 0.5},
    "slow": {"raftMinTimeout": 2.0, "raftMaxTimeout": 7.0, "appendEntriesPeriod": 0.5, "connectionTimeout": 10.0},
}

_BUILT: dict = {}


def _library():
    """pysyncobj and the state machine class, built on first use."""
    if _BUILT:
        return _BUILT
    from pysyncobj import FAIL_REASON, SyncObj, SyncObjConf, SyncObjConsumer, replicated

    class Rows(SyncObjConsumer):
        # Everything set after `super().__init__()` is the replicated state (and what a dump carries).
        def __init__(self):
            super().__init__()
            self.rows: dict[str, tuple[dict, int]] = {}
            self.done: collections.OrderedDict[str, tuple] = collections.OrderedDict()

        # The raft index of the entry being applied. The library counts what it has applied and moves the count
        # after an entry, so the one in hand is the next: the same number on every node, after a restart and after
        # a dump, because it is the log's.
        def _index(self) -> int:
            return self._syncObj.raftLastApplied + 1

        def _answered(self, op: str, res: tuple) -> tuple:
            self.done[op] = res
            while len(self.done) > OP_MEMORY:
                self.done.popitem(last=False)
            return res

        @replicated
        def write(self, op, path, items, cas):
            if op in self.done:
                return self.done[op]
            current = self.rows.get(path, (None, 0))[1]
            if cas is not None and cas != current:
                return self._answered(op, ("conflict", current))
            idx = self._index()
            self.rows[path] = (dict(items), idx)
            return self._answered(op, ("ok", idx))

        @replicated
        def remove(self, op, path, cas):
            if op in self.done:
                return self.done[op]
            current = self.rows.get(path, (None, 0))[1]
            if cas is not None and cas != current:
                return self._answered(op, ("conflict", current))
            self.rows.pop(path, None)
            return self._answered(op, ("ok", self._index()))

        # Reads are entries too (above): the answer is a copy, never the row the state machine keeps.
        @replicated
        def read(self, path):
            e = self.rows.get(path)
            return (dict(e[0]), e[1]) if e else (None, 0)

        @replicated
        def scan(self, prefix):
            return sorted(p for p in self.rows if p.startswith(prefix))

        def local(self, path):
            e = self.rows.get(path)
            return (dict(e[0]), e[1]) if e else (None, 0)

    _BUILT.update(FAIL_REASON=FAIL_REASON, SyncObj=SyncObj, SyncObjConf=SyncObjConf, Rows=Rows)
    return _BUILT


def have_library() -> bool:
    try:
        _library()
        return True
    except ImportError:
        return False


class RaftStore:
    """One raft node and its HTTP door. `self_addr` is the raft address (`host:port`), `partners` the other
    members' raft addresses ([] for a group of one), `data` the directory for the journal and the dump."""

    def __init__(self, self_addr: str, partners: list[str], data: str | None, http: tuple[str, int] = ("127.0.0.1", 0),
                 timing: str | dict = "defaults", deadline: float = 4.5):
        lib = _library()
        knobs = dict(TIMINGS[timing]) if isinstance(timing, str) else dict(timing)
        files = {}
        if data:
            os.makedirs(data, exist_ok=True)
            files = {"journalFile": os.path.join(data, "journal"), "fullDumpFile": os.path.join(data, "dump")}
        # `useFork=False`: the dump is written by the tick thread, not a forked child — a fork of a process with
        # an HTTP server's threads in it is what macOS refuses to promise anything about.
        # `appendEntriesUseBatch=False`: a command wakes the tick thread and goes out at once. Batched (the
        # library's default) it waits for the next tick on every hop — follower, leader, commit, back — and a
        # write through a follower took 150 ms on a laptop; a worker's lease step is a handful of them in a row.
        base = {"dynamicMembershipChange": True, "useFork": False, "appendEntriesUseBatch": False}
        conf = lib["SyncObjConf"](**{**base, **files, **knobs})
        self.fail = lib["FAIL_REASON"]
        self.rows = lib["Rows"]()
        self.raft = lib["SyncObj"](self_addr, list(partners), conf, consumers=[self.rows])
        self.self_addr = self_addr
        self.deadline = deadline
        self.http = ThreadingHTTPServer(http, _door(self))
        self.http.daemon_threads = True
        self.url = f"http://{self.http.server_address[0]}:{self.http.server_address[1]}"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    # A command, until it is applied or the deadline passes. Every failure the library reports during an
    # election is retried with the SAME arguments — the operation id among them, so a write that did land is
    # answered from memory, not applied again. A command still queued when the deadline passes may apply later.
    def apply(self, method, *args, deadline: float | None = None):
        end = time.monotonic() + (self.deadline if deadline is None else deadline)
        while True:
            left = end - time.monotonic()
            if left <= 0:
                raise RaftUnavailable(f"no leader answered within {self.deadline if deadline is None else deadline:g} s")
            done, box = threading.Event(), {}

            def cb(res, err, box=box, done=done):
                box["res"], box["err"] = res, err
                done.set()

            method(*args, callback=cb)
            if not done.wait(left):
                raise RaftUnavailable("no leader answered in time; the command may still be applied")
            if box["err"] == self.fail.SUCCESS:
                return box["res"]
            time.sleep(min(0.02, max(0.0, end - time.monotonic())))

    def members(self) -> list[str]:
        return sorted([self.self_addr] + [n.id for n in self.raft.otherNodes])

    def status(self) -> dict:
        s = self.raft.getStatus()
        leader = s.get("leader")
        return {"self": self.self_addr, "state": {0: "follower", 1: "candidate", 2: "leader"}.get(s["state"], s["state"]),
                "leader": leader.id if leader is not None else None, "members": self.members(),
                "term": s["raft_term"], "commit": s["commit_idx"], "applied": s["last_applied"],
                "leader_commit": s.get("leader_commit_idx"), "rows": len(self.rows.rows)}

    # Membership, one change at a time: the library refuses a second change while the first is uncommitted, and
    # that refusal is retried like an election's.
    def add(self, node: str, deadline: float = 20.0) -> None:
        self.apply(self.raft.addNodeToCluster, node, deadline=deadline)

    def remove(self, node: str, deadline: float = 20.0) -> None:
        self.apply(self.raft.removeNodeFromCluster, node, deadline=deadline)

    def stop(self) -> None:
        self.http.shutdown()
        self.http.server_close()
        self.raft.destroy_synchronous()


def _door(store: RaftStore):
    class Door(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):           # a request a second per worker is not a log line
            pass

        def _send(self, code: int, body: dict) -> None:
            raw = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _args(self) -> tuple[str, dict, dict]:
            u = urllib.parse.urlsplit(self.path)
            q = dict(urllib.parse.parse_qsl(u.query))
            body = {}
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                body = json.loads(self.rfile.read(n))
            return u.path, q, body

        def _serve(self, method: str) -> None:
            try:
                route, q, body = self._args()
                dl = min(store.deadline, float(q["deadline"])) if "deadline" in q else None
                if method == "GET" and route == "/v1/get":
                    path = safe_path(q.get("path", ""))
                    items, idx = (store.rows.local(path) if q.get("reads") == "local"
                                  else store.apply(store.rows.read, path, deadline=dl))
                    return self._send(200, {"items": items, "index": idx})
                if method == "GET" and route == "/v1/list":
                    prefix = q.get("prefix", "")
                    keys = (sorted(p for p in list(store.rows.rows) if p.startswith(prefix)) if q.get("reads") == "local"
                            else store.apply(store.rows.scan, prefix, deadline=dl))
                    return self._send(200, {"keys": keys})
                if method == "POST" and route in ("/v1/put", "/v1/delete"):
                    path = safe_path(body.get("path", ""))
                    op = str(body.get("op") or uuid.uuid4().hex)
                    if route == "/v1/put":
                        res = store.apply(store.rows.write, op, path, dict(body.get("items") or {}), body.get("cas"), deadline=dl)
                    else:
                        res = store.apply(store.rows.remove, op, path, body.get("cas"), deadline=dl)
                    if res[0] == "conflict":
                        return self._send(409, {"error": f"{path}: cas={body.get('cas')} but ModifyIndex={res[1]}", "index": res[1]})
                    return self._send(200, {"index": res[1]})
                if method == "GET" and route == "/v1/status":
                    return self._send(200, store.status())
                if method == "POST" and route in ("/v1/join", "/v1/leave"):
                    node = str(body.get("node", ""))
                    (store.add if route == "/v1/join" else store.remove)(node)
                    return self._send(200, store.status())
                return self._send(400, {"error": f"no such door: {method} {route}"})
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            except RaftUnavailable as e:
                return self._send(503, {"error": str(e)})
            except Exception as e:                       # noqa: BLE001 — a door answers, whatever went wrong behind it
                return self._send(500, {"error": f"{type(e).__name__}: {e}"})

        def do_GET(self):
            self._serve("GET")

        def do_POST(self):
            self._serve("POST")

    return Door


def _http_json(method: str, url: str, body: dict | None = None, timeout: float = 5.0) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


# A new member: ask a member who is in the group, start with them as partners, then ask to be added — in that
# order, so the group never counts a voter that is not running yet. Returns the running store.
def join(self_addr: str, seed_http: str, data: str | None, http: tuple[str, int] = ("127.0.0.1", 0),
         timing: str | dict = "defaults", deadline: float = 4.5, wait: float = 30.0) -> RaftStore:
    members = _http_json("GET", seed_http.rstrip("/") + "/v1/status")["members"]
    store = RaftStore(self_addr, [m for m in members if m != self_addr], data, http, timing, deadline)
    end = time.monotonic() + wait
    while True:
        try:
            _http_json("POST", seed_http.rstrip("/") + "/v1/join", {"node": self_addr}, timeout=25.0)
            return store
        except (urllib.error.URLError, OSError, http.client.HTTPException):     # a member dying mid-answer, too
            if time.monotonic() > end:
                store.stop()
                raise
            time.sleep(0.2)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m w2cplatform.raftvars", description="the raft:// store daemon (experimental)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--raft", required=True, help="this node's raft address, host:port")
    s.add_argument("--http", required=True, help="the door for this server's processes, host:port")
    s.add_argument("--data", required=True, help="journal and dump directory")
    s.add_argument("--peer", action="append", default=[], help="another member's raft address (a fixed group)")
    s.add_argument("--join", help="the http of a member: ask it to add this node")
    s.add_argument("--timing", default="defaults", choices=sorted(TIMINGS))
    s.add_argument("--deadline", type=float, default=4.5)
    a = ap.parse_args(argv)
    host, port = a.http.rsplit(":", 1)
    if a.join:
        store = join(a.raft, a.join, a.data, (host, int(port)), a.timing, a.deadline)
    else:
        store = RaftStore(a.raft, a.peer, a.data, (host, int(port)), a.timing, a.deadline)
    print(json.dumps({"serving": store.url, "raft": a.raft}), flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        store.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
