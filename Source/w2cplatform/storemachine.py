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
# An id is answered from memory only for the SAME write — op, key, items, cas (`_fingerprint`): an id that comes back
# with another write is refused, never answered with a first answer that was not its own (the review's thirteenth
# pass, major 4: the handle sent a new write under an old id and was told «OK» for a write it never made; the handle
# is mended too, `configstorevars._Unknown`).
#
# ## What a caller names is bounded too (the review's thirteenth pass, major 2)
# `MAX_VALUE` bounded the items and nothing else: a delete whose `id` was 3 MiB was taken — the journal grew by
# 3.2 MB on every member, and the machine kept the id among its 50 000 — and a `cas` of 3 MiB went into the log and
# came back in the 409's text. Every request is a command of the log, reads too, so what a caller names is bounded
# at the door before anything is submitted, and again by the machine (a function of the command alone): an `id` is
# `OP_ID` — up to 64 letters, digits, `-` and `_` (the handle's are 32 hex digits); a `cas` is null, a number, or a
# short word of the same alphabet (`CAS_WORD`: the platform's `TORN` is one); a key is a key (`check_key`, its
# length asked before its text, so a refusal never quotes a long one); a list's prefix longer than any key matches
# nothing and is answered so without a command. No refusal quotes what the caller sent but a key.
#
# ## A row has a ceiling: `MAX_VALUE` (the review's twelfth pass, major 2)
# A row of 32 MiB was taken and went into the raft log — every member holds it in memory, writes it to its journal
# and sends it to a follower that lags, and while one entry that size crosses the network the leader's heartbeats
# wait behind it. A row is a couple of hundred bytes; what makes one big is a field that belongs in an object. So a
# row's items weigh at most `MAX_VALUE` bytes, counted as every store counts them (`variables.items_bytes`: keys and
# values, as bytes — Nomad's measure of a Variable, `limits.py`): refused at the door (413 `toolarge`, before
# anything is submitted) and again by the machine, whose refusal is a function of the command alone, so every member
# refuses the same. 512 KiB is Consul's ceiling for a value on the same `hashicorp/raft` the product runs
# (`kv_max_value_size`), for the same reason; it is a thousand times a row, and eight times Nomad's 64 KiB that the
# platform was built under — no row the code writes comes near it. `FileVariables` has no ceiling of its own, so a
# box's rows are measured at the import (`configstore.import_rows`), all of them before the first write.
#
# ## The rights file — who may do what, by the socket the caller came through
# `/etc/w2c/configstore-rights.json` (generated from the spec by `python3 -m cluster rights`, М11), in the product's
# format (its configstore round 2):
#     {"roles": {"testsubworker": {"group": "testsub-worker", "read": ["testsub/*"],
#                                  "write": ["testsub/epoch/*", "testsub/slots/*"], "delete": []}, …}}
# A trailing `*` is a prefix, anything else one key; a pattern that starts with `!` DENIES, and the denials are asked
# before the grants (`"read": ["domain/*", "!domain/break_glass"]`). The daemon opens a socket per role, owned by the
# role's `group` (`configstore.socket_group`; a role without one: `w2c-<role>`), so
# a role is WHICH socket a process could open (its unit's `SupplementaryGroups=`), and `Rights.allows` is asked
# before anything is forwarded or applied. `admin` is the root-only socket and may do everything but two things
# nobody does: delete an epoch row, or delete `domain/*` — which only the domain's own roles do (`DOMAIN_ROLES`:
# `domain`, `domainagent`). `list` answers only the keys the role may read; `get` of a key it may not read is 403.
#
# `configstore` (`PEER`) — another daemon on the `-api` door — is not a role of the file and has NO grant on a row
# (the review's twelfth pass, major 3: it had every right, so one daemon's certificate deleted slots, wrote the
# schema and changed the group). What daemons need from each other is the group: `/v1/status`, and `/v1/join` /
# `/v1/leave` of the calling daemon's own server (`configstore.StoreDaemon.serve`). No daemon speaks for a process
# either: the mark a forwarding daemon put on a request to be answered as its caller's role was any role a daemon's
# certificate wanted, and nobody forwards in the course — it is gone (the review's thirteenth pass, major 1). The
# file may name neither `admin` nor `configstore`: a socket of either name would be that door.
#
# ## The API — the product's, rendered here so the stand and the daemon say the same
#   GET  /v1/get?key=K          → {items, index}           index "" = absent
#   GET  /v1/list?prefix=P      → {keys: {key: index}}
#   POST /v1/write {op: "put"|"delete", key, items, cas, id} → {index}     cas null = none, "" = create-only
#   faults {kind, error}: 409 conflict (+ index now), 403 forbidden, 400 badkey / badrequest, 413 toolarge,
#                         503 unavailable (not done), 503 ambiguous (outcome unknown; repeat only with the same id)
# `answer` is the whole of it; the daemon adds `/v1/join`, `/v1/leave`, `/v1/status`, which are about raft.
# ================================================================================================
from __future__ import annotations

import collections
import hashlib
import json
import re
import urllib.parse

from .variables import KEY_BYTES, epoch_row, items_bytes, safe_path

OP_MEMORY = 50_000         # write answers remembered by id; a retry comes within seconds, this is hours of writes
OP_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")         # a write's operation id (the handle's: 32 hex digits)
CAS_WORD = re.compile(r"^[A-Za-z0-9_-]{0,32}$")      # a `cas` that is a string: "" (create-only), digits, a word
CAS_MAX = 1 << 63                                    # a `cas` that is a number: a version, which is a log index
MAX_VALUE = 512 << 10      # what a row's items may weigh (`items_bytes`): see the notes above
ADMIN = "admin"            # the root-only socket's role
PEER = "configstore"       # another daemon, on the mutually authenticated `-api` door
# The roles that may delete `domain/*` (the product's names): the domain's own processes on its store, and its agent in
# a member cluster's (М12, `domain/agent.py`). Nobody else — `admin` included.
DOMAIN_ROLES = frozenset({"domain", "domainagent"})


class Unavailable(Exception):
    """No leader took the command within the wait: NOT done (a write), or not answered (a read)."""


class Ambiguous(Unavailable):
    """A write reached a leader that went before answering: it may yet be applied. Repeat only with the same id."""


# -- keys ---------------------------------------------------------------------------------------------
# A key is what `safe_path` lets through, and no longer than `FileVariables` can name a file: a store a box's rows
# were imported into, and one a cluster's rows could be exported back from, must take the same keys.
def check_key(key) -> str:
    if not isinstance(key, str):
        raise ValueError(f"not a key: a {type(key).__name__}")
    if len(key.replace("%", "%25").replace("/", "%2F").encode()) > KEY_BYTES:
        raise ValueError(f"not a key: longer than {KEY_BYTES} bytes as a file's name")
    safe_path(key)                                # after the length: its refusal quotes the key
    return key


# What a write names besides its key and items, bounded (the notes: "What a caller names is bounded too"). Raises
# `ValueError` naming the field, never quoting it.
def check_write(cmd: dict) -> None:
    op_id = cmd.get("id")
    if op_id is not None and not (isinstance(op_id, str) and OP_ID.match(op_id)):
        raise ValueError("a write's id is up to 64 letters, digits, - and _")
    cas = cmd.get("cas")
    if cas is None or isinstance(cas, bool):
        return
    if isinstance(cas, int) and -CAS_MAX < cas < CAS_MAX:
        return
    if isinstance(cas, str) and CAS_WORD.match(cas):
        return
    raise ValueError('a write\'s cas is null, a version, "" (create-only) or a word of up to 32 letters and digits')


# The write an operation id stands for: what a repeat must be to be answered from memory. A function of the command
# alone, so every member keeps the same.
def _fingerprint(cmd: dict) -> str:
    what = json.dumps([cmd.get("op"), cmd.get("key"), cmd.get("items") if cmd.get("op") == "put" else None,
                       cmd.get("cas")], sort_keys=True, default=str)
    return hashlib.sha256(what.encode()).hexdigest()


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
        self.done: collections.OrderedDict[str, tuple[str, dict]] = collections.OrderedDict()   # id → (write, answer)
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
        try:
            check_key(cmd.get("key"))
            check_write(cmd)
        except ValueError as e:
            return {"error": str(e)}              # the door refuses it first; a command in the log must not raise
        key, op_id = cmd["key"], cmd.get("id")
        fingerprint = _fingerprint(cmd) if op_id else ""
        if op_id and op_id in self.done:
            was, res = self.done[op_id]
            if was != fingerprint:
                return {"error": "this operation id was another write's: a new write takes a new id"}
            return dict(res)
        current = self.rows.get(key, (None, 0))[1]
        cas = _cas(cmd.get("cas"))
        if cas is not None and cas != current:
            res = {"conflict": True, "index": current}
        elif cmd["op"] == "put" and items_bytes(cmd.get("items") or {}) > MAX_VALUE:
            res = {"toolarge": items_bytes(cmd["items"])}      # the door refuses it first; the log must agree anyway
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
            self.done[op_id] = (fingerprint, dict(res))
            while len(self.done) > OP_MEMORY:
                self.done.popitem(last=False)
        return res


# -- rights -------------------------------------------------------------------------------------------
ACTIONS = ("read", "write", "delete")
_ROLE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")          # a socket's file name: `<role>.sock`
_GROUP = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")        # a group's name, as `groupadd` takes it


def _hit(pattern: str, key: str) -> bool:
    return key == pattern or (pattern.endswith("*") and key.startswith(pattern[:-1]))


# A pattern: a key, or a prefix with one trailing `*`; with a leading `!` it denies what it names.
def _pattern(p) -> bool:
    if not isinstance(p, str):
        return False
    body = p[1:] if p.startswith("!") else p
    return bool(body) and "!" not in body and "*" not in body[:-1]


class Rights:
    """The rights file, read and checked. `allows(role, action, key)` is the one question; `groups` says whose each
    role's socket is (the role's `group`, where the file says one)."""

    def __init__(self, roles: dict[str, dict] | None = None):
        self.roles = {r: {a: list(g.get(a, [])) for a in ACTIONS} for r, g in (roles or {}).items()}
        self.groups = {r: str(g["group"]) for r, g in (roles or {}).items() if g.get("group")}

    @classmethod
    def parse(cls, doc) -> "Rights":
        """The file's JSON, refused whole when any part of it is not what the format says — a rights file that is
        half read grants what nobody wrote."""
        if not isinstance(doc, dict) or set(doc) - {"roles", "comment"} or not isinstance(doc.get("roles"), dict):
            raise ValueError('a rights file is {"roles": {"<role>": {"group": "...", "read": [...], "write": [...], '
                             '"delete": [...]}}}')
        roles = {}
        for role, grants in doc["roles"].items():
            if not isinstance(role, str) or not _ROLE.match(role) or role in (ADMIN, PEER):
                raise ValueError(f"not a role name: {role!r} (lower case, digits, - and _; {ADMIN!r} and {PEER!r} are "
                                 f"the store's own)")
            if not isinstance(grants, dict) or set(grants) - set(ACTIONS) - {"group"}:
                raise ValueError(f"{role}: a role says its socket's group, and read, write and delete, each a list of "
                                 f"keys or prefixes")
            if "group" in grants and (not isinstance(grants["group"], str) or not _GROUP.match(grants["group"])):
                raise ValueError(f"{role}.group: a group's name, as groupadd takes it")
            for action in ACTIONS:
                pats = grants.get(action, [])
                if not isinstance(pats, list) or not all(_pattern(p) for p in pats):
                    raise ValueError(f"{role}.{action}: a list of keys, a trailing * for a prefix, a leading ! to deny")
            roles[role] = grants
        return cls(roles)

    @classmethod
    def load(cls, path: str) -> "Rights":
        with open(path, encoding="utf-8") as f:
            return cls.parse(json.load(f))

    def doc(self) -> dict:
        """What is held, in the file's own form — what `/v1/rights` and `configstore rights` show."""
        return {"roles": {r: {**({"group": self.groups[r]} if r in self.groups else {}), **g}
                          for r, g in self.roles.items()}}

    def allows(self, role: str, action: str, key: str) -> bool:
        if action == "delete" and (epoch_row(key) or (key.startswith("domain/") and role not in DOMAIN_ROLES)):
            return False                          # nobody, `admin` included (`variables.refuse_delete`)
        if role == ADMIN:
            return True                           # `PEER` is no role of the file: no grant on any row (twelfth pass)
        pats = self.roles.get(role, {}).get(action, [])
        if any(_hit(p[1:], key) for p in pats if p.startswith("!")):
            return False                          # a denial wins over every grant, wherever it stands in the list
        return any(_hit(p, key) for p in pats if not p.startswith("!"))


# -- the API ------------------------------------------------------------------------------------------
def fault(code: int, kind: str, error: str, **more) -> tuple[int, dict]:
    return code, {"kind": kind, "error": error, **more}


def too_large(key: str, size: int) -> tuple[int, dict]:
    return fault(413, "toolarge", f"{key}: a row of {size} bytes; a row here weighs at most {MAX_VALUE}",
                 size=size, limit=MAX_VALUE)


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
            if len(prefix.encode()) > KEY_BYTES:
                return 200, {"keys": {}}          # longer than any key: nothing to match, nothing to ask the log
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
            try:
                check_write(body)
            except ValueError as e:
                return fault(400, "badrequest", str(e))
            action = "write" if body["op"] == "put" else "delete"
            if not rights.allows(role, action, key):
                return fault(403, "forbidden", f"{role} may not {action} {key}")
            cmd = {"op": body["op"], "key": key, "cas": body.get("cas")}
            if body["op"] == "put":
                items = body.get("items")
                if not isinstance(items, dict) or not all(isinstance(k, str) for k in items):
                    return fault(400, "badrequest", "items are a map of strings")
                cmd["items"] = {k: str(v) for k, v in items.items()}
                size = items_bytes(cmd["items"])
                if size > MAX_VALUE:
                    return too_large(key, size)
            if body.get("id"):
                cmd["id"] = body["id"]
            got = submit(cmd)
            if "error" in got:
                return fault(400, "badkey", got["error"])
            if "toolarge" in got:
                return too_large(key, got["toolarge"])
            if got.get("conflict"):
                # The version now, not the one the write named: what the caller sent is not said back to it.
                return fault(409, "conflict", f"{key}: the version is {got['index'] or 'absent'}, not the one the "
                                              f"write named", index=got["index"] or "")
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
