"""The replicated store's state machine and its API, with no raft in it: what `configstore` applies on every member of
the group, and what a test stand applies in one process — the same code, so the two cannot disagree."""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # storemachine.py — `FileVariables`' semantics as a function of the log, the rights file, and the API
#
# **Role.** The cluster without an orchestrator keeps its rows in our own store, replicated by raft over the
# servers (`configstore.py`, the daemon). Consensus is the library's; WHAT is agreed on is this file. It imports no
# raft library and opens no socket, so the daemon applies it under `pysyncobj`, a test stand applies it under a
# lock, and `test_storemachine.py` holds it to the contract without either.
#
# ## The machine — `FileVariables`, to the letter
# One row per key, a map of strings. A row's version is the log index of the command that last wrote it, plus the
# group's `base` (below); absent is `(None, 0)`; `put` with `cas` passes only if the version has not moved, `cas=0`
# (on the wire `""`) is create-only; `delete` takes a `cas` too and burns an index, as every command does; `list` by
# prefix. A log index is never reused, so a version remembered from before a restart, a leader change or a dump
# still conflicts. Every answer is a copy: what the machine keeps is never handed out.
#
# The machine decides from the command and its own state only — never a clock, never a random number — because
# every member applies the same log and must arrive at the same rows.
#
# ## The base: a box that becomes a cluster
# A box keeps `file://` (its counter started at 1000 and has moved since). The day it becomes a cluster its rows are
# imported once into a fresh group (`configstore import`), and a process may still hold a version it read from the
# file. The group was started with `-index-base N`, N at least the file's counter: every version it hands out is
# `N + log index`, above every version the file ever handed out, so a remembered old version matches no new row —
# the CAS conflicts, the caller re-reads. `base` is the group's first command, accepted only while it holds no rows.
#
# ## A retried write is applied once
# During an election a write can fail with "leader changed" AFTER the old leader appended it — it may yet commit.
# Retried as a new write, a CAS conflicts with its own first copy, and a slot renewal that comes back `Conflict`
# FENCES the worker (`Worker._renew_slot`). So a write carries an operation id (`id`, made by the handle once per
# call), and the machine answers a repeat of an id it has seen with the first answer — the client sessions of the
# Raft dissertation, § 6.3. The memory is the last `OP_MEMORY` ids, in log order, so every member forgets the same.
#
# ## The rights file — who may do what, by the socket the caller came through
# `/etc/w2c/configstore-rights.json` (generated from the spec by `python3 -m cluster rights`, М11):
#     {"roles": {"vmsworker": {"read": ["vms/*"], "write": ["vms/epoch/*", "vms/slots/*"], "delete": []}, …}}
# A trailing `*` is a prefix, anything else one key. The daemon opens a socket per role, so a role is WHICH socket
# a process could open (its unit's group), and `Rights.allows` is asked before anything is forwarded or applied.
# `admin` is the root-only socket and may do everything but two things nobody does (`variables.refuse_delete`):
# delete an epoch row, or delete `domain/*` unless it is the domain's agent. `list` answers only the keys the role
# may read; `get` of a key it may not read is 403.
#
# ## The API — the product's, rendered here so the stand and the daemon say the same
#   GET  /v1/get?key=K          → {items, index}           index "" = absent
#   GET  /v1/list?prefix=P      → {keys: {key: index}}
#   POST /v1/write {op: "put"|"delete", key, items, cas, id} → {index}     cas null = none, "" = create-only
#   faults {kind, error}: 409 conflict (+ index now), 403 forbidden, 400 badkey / badrequest,
#                         503 unavailable (not done), 503 ambiguous (outcome unknown; repeat only with the same id)
# `answer` is the whole of it; the daemon adds `/v1/join`, `/v1/leave`, `/v1/status`, which are about raft.
# ================================================================================================
from __future__ import annotations

import collections
import json
import re
import urllib.parse

from .variables import DOMAIN_WRITER, KEY_BYTES, epoch_row, safe_path

OP_MEMORY = 50_000         # write answers remembered by id; a retry comes within seconds, this is hours of writes
ADMIN = "admin"            # the root-only socket's role
PEER = "configstore"       # another daemon, on the mutually authenticated `-api` door


class Unavailable(Exception):
    """No leader took the command within the wait: NOT done (a write), or not answered (a read)."""


class Ambiguous(Unavailable):
    """A write reached a leader that went before answering: it may yet be applied. Repeat only with the same id."""


# -- keys ---------------------------------------------------------------------------------------------
# A key is what `safe_path` lets through, and no longer than `FileVariables` can name a file: a store a box's rows
# were imported into, and one a cluster's rows could be exported back from, must take the same keys.
def check_key(key) -> str:
    if not isinstance(key, str):
        raise ValueError(f"not a key: {key!r}")
    safe_path(key)
    if len(key.replace("%", "%25").replace("/", "%2F").encode()) > KEY_BYTES:
        raise ValueError(f"not a key: longer than {KEY_BYTES} bytes as a file's name")
    return key


# A version as a write compares it. `None`: no CAS. `""` or 0: the key must be absent. A number (or its digits):
# that version. Anything else — the platform's `TORN`, a version from another store — names no version this
# store ever handed out, and conflicts.
def _cas(cas):
    if cas is None:
        return None
    if isinstance(cas, bool):
        return object()
    if cas == "" or cas == 0:
        return 0
    if isinstance(cas, int):
        return cas
    if isinstance(cas, str) and cas.isdigit():
        return int(cas)
    return object()


class StoreMachine:
    """The replicated state. `apply(cmd, index)` with the log index of the command; without one (a stand, a test)
    the machine counts its own."""

    def __init__(self, index_base: int = 0):
        self.rows: dict[str, tuple[dict, int]] = {}
        self.done: collections.OrderedDict[str, dict] = collections.OrderedDict()
        self.base = int(index_base)
        self.members: dict[str, dict] = {}        # id → {raft, api}: who is in the group, by the daemons' own word
        self.applied = 0                          # the log index of the last command applied
        self.wrote = False                        # a row was ever written: the base is fixed from then on

    def version(self, index: int) -> int:
        return self.base + index

    def apply(self, cmd: dict, index: int | None = None) -> dict:
        index = self.applied + 1 if index is None else int(index)
        self.applied = index
        op = cmd.get("op")
        if op in ("put", "delete"):
            return self._write(cmd, index)
        if op == "get":
            e = self.rows.get(cmd.get("key"))
            return {"items": dict(e[0]), "index": e[1]} if e else {"items": None, "index": 0}
        if op == "list":
            prefix = str(cmd.get("prefix") or "")
            return {"keys": {k: e[1] for k, e in sorted(self.rows.items()) if k.startswith(prefix)}}
        if op == "base":
            if self.wrote and int(cmd.get("base", 0)) != self.base:
                return {"refused": f"the group holds rows: its base stays {self.base}", "base": self.base}
            self.base = int(cmd.get("base", 0))
            return {"base": self.base}
        if op == "member":
            self.members[str(cmd["id"])] = {"raft": str(cmd.get("raft", "")), "api": str(cmd.get("api", ""))}
            return {"members": self.members_copy()}
        if op == "unmember":
            self.members.pop(str(cmd.get("id")), None)
            return {"members": self.members_copy()}
        return {"error": f"no such command: {op!r}"}

    def members_copy(self) -> dict:
        return {k: dict(v) for k, v in self.members.items()}

    def _write(self, cmd: dict, index: int) -> dict:
        op_id = cmd.get("id")
        if op_id and op_id in self.done:
            return dict(self.done[op_id])
        key = cmd.get("key")
        try:
            check_key(key)
        except ValueError as e:
            return {"error": str(e)}              # the door refuses it first; a command in the log must not raise
        current = self.rows.get(key, (None, 0))[1]
        cas = _cas(cmd.get("cas"))
        if cas is not None and cas != current:
            res = {"conflict": True, "index": current}
        elif cmd["op"] == "put":
            items = cmd.get("items") or {}
            self.rows[key] = ({str(k): str(v) for k, v in items.items()}, self.version(index))
            self.wrote = True
            res = {"index": self.version(index)}
        else:
            self.rows.pop(key, None)
            self.wrote = True
            res = {"index": self.version(index)}
        if op_id:
            self.done[op_id] = dict(res)
            while len(self.done) > OP_MEMORY:
                self.done.popitem(last=False)
        return res


# -- rights -------------------------------------------------------------------------------------------
ACTIONS = ("read", "write", "delete")
_ROLE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")          # a socket's file name: `<role>.sock`


class Rights:
    """The rights file, read and checked. `allows(role, action, key)` is the one question."""

    def __init__(self, roles: dict[str, dict[str, list[str]]] | None = None):
        self.roles = {r: {a: list(g.get(a, [])) for a in ACTIONS} for r, g in (roles or {}).items()}

    @classmethod
    def parse(cls, doc) -> "Rights":
        """The file's JSON, refused whole when any part of it is not what the format says — a rights file that is
        half read grants what nobody wrote."""
        if not isinstance(doc, dict) or set(doc) - {"roles", "comment"} or not isinstance(doc.get("roles"), dict):
            raise ValueError('a rights file is {"roles": {"<role>": {"read": [...], "write": [...], "delete": [...]}}}')
        roles = {}
        for role, grants in doc["roles"].items():
            if not isinstance(role, str) or not _ROLE.match(role) or role == ADMIN:
                raise ValueError(f"not a role name: {role!r} (lower case, digits, - and _; {ADMIN!r} is the store's own)")
            if not isinstance(grants, dict) or set(grants) - set(ACTIONS):
                raise ValueError(f"{role}: grants are read, write and delete, each a list of keys or prefixes")
            for action, pats in grants.items():
                if not isinstance(pats, list) or not all(isinstance(p, str) and p and "*" not in p[:-1] for p in pats):
                    raise ValueError(f"{role}.{action}: a list of keys, a trailing * for a prefix")
            roles[role] = grants
        return cls(roles)

    @classmethod
    def load(cls, path: str) -> "Rights":
        with open(path, encoding="utf-8") as f:
            return cls.parse(json.load(f))

    def allows(self, role: str, action: str, key: str) -> bool:
        if action == "delete" and (epoch_row(key) or (key.startswith("domain/") and role != DOMAIN_WRITER)):
            return False                          # nobody, `admin` included (`variables.refuse_delete`)
        if role in (ADMIN, PEER):
            return True
        pats = self.roles.get(role, {}).get(action, [])
        return any(key == p or (p.endswith("*") and key.startswith(p[:-1])) for p in pats)


# -- the API ------------------------------------------------------------------------------------------
def fault(code: int, kind: str, error: str, **more) -> tuple[int, dict]:
    return code, {"kind": kind, "error": error, **more}


def answer(method: str, target: str, raw: bytes, role: str, rights: Rights, submit) -> tuple[int, dict]:
    """One request of the data API, as `role`: rights first, then the command through `submit(cmd)` — the log on a
    daemon, the machine itself on a stand. Returns (status, body). Never raises for what a caller sent."""
    u = urllib.parse.urlsplit(target)
    q = dict(urllib.parse.parse_qsl(u.query, keep_blank_values=True))
    try:
        if method == "GET" and u.path == "/v1/get":
            key = check_key(q.get("key", ""))
            if not rights.allows(role, "read", key):
                return fault(403, "forbidden", f"{role} may not read {key}")
            got = submit({"op": "get", "key": key})
            return 200, {"items": got["items"], "index": got["index"] or ""}
        if method == "GET" and u.path == "/v1/list":
            prefix = q.get("prefix", "")
            got = submit({"op": "list", "prefix": prefix})
            return 200, {"keys": {k: v for k, v in got["keys"].items() if rights.allows(role, "read", k)}}
        if method == "POST" and u.path == "/v1/write":
            try:
                body = json.loads(raw or b"{}")
            except ValueError:
                return fault(400, "badrequest", "the body is not JSON")
            if not isinstance(body, dict) or body.get("op") not in ("put", "delete"):
                return fault(400, "badrequest", 'a write is {"op": "put"|"delete", "key", "items", "cas", "id"}')
            key = check_key(body.get("key", ""))
            action = "write" if body["op"] == "put" else "delete"
            if not rights.allows(role, action, key):
                return fault(403, "forbidden", f"{role} may not {action} {key}")
            cmd = {"op": body["op"], "key": key, "cas": body.get("cas")}
            if body["op"] == "put":
                items = body.get("items")
                if not isinstance(items, dict) or not all(isinstance(k, str) for k in items):
                    return fault(400, "badrequest", "items are a map of strings")
                cmd["items"] = {k: str(v) for k, v in items.items()}
            if body.get("id"):
                cmd["id"] = str(body["id"])
            got = submit(cmd)
            if "error" in got:
                return fault(400, "badkey", got["error"])
            if got.get("conflict"):
                return fault(409, "conflict", f"{key}: cas={body.get('cas')!r} but the version is {got['index'] or 'absent'}",
                             index=got["index"] or "")
            return 200, {"index": got["index"]}
        return fault(404, "badrequest", f"no such route: {method} {u.path}")
    except ValueError as e:
        return fault(400, "badkey", str(e))
    except Ambiguous as e:
        return fault(503, "ambiguous", str(e) or "the write's outcome is unknown: read before writing again")
    except Unavailable as e:
        return fault(503, "unavailable", str(e) or "no leader answered: not done")


def local_transport(submit, rights: Rights, role: str):
    """A transport for `configstorevars.ConfigstoreVariables` that answers in this process — a stand's door for `role`
    over one machine, with no socket in between: the handle, the API and the machine are the daemon's own code."""
    def call(method: str, target: str, raw: bytes | None, headers: dict, timeout: float) -> tuple[int, bytes]:
        code, body = answer(method, target, raw or b"", role, rights, submit)
        return code, json.dumps(body).encode()
    return call
