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
# An id is answered from memory only for the SAME write — op, key, items, cas, guard (`_fingerprint`): an id that comes back
# with another write is refused, never answered with a first answer that was not its own (the review's thirteenth
# pass, major 4: the handle sent a new write under an old id and was told «OK» for a write it never made; the handle
# is mended too, `configstorevars._Unknown`).
#
# ## What a caller names is bounded too (the review's thirteenth pass, major 2)
# `MAX_VALUE` bounded the items and nothing else: a delete whose `id` was 3 MiB was taken — the journal grew by
# 3.2 MB on every member, and the machine kept the id among its 50 000 — and a `cas` of 3 MiB went into the log and
# came back in the 409's text. Every request is a command of the log, reads too, so what a caller names is bounded
# at the door before anything is submitted, and again by the machine (a function of the command alone). The
# HTTP contract is strict: lowercase hex id, decimal version strings (or empty/create-only and null/no CAS).
# Internal commands retain numeric log indexes; the door never accepts those numeric JSON versions. A key is a key (`check_key`, its
# length asked before its text, so a refusal never quotes a long one); a list's prefix longer than any key matches
# nothing and is answered so without a command. No refusal quotes what the caller sent but a key.
#
# ## A row has a ceiling: `MAX_VALUE` (the review's twelfth pass, major 2)
# A row of 32 MiB was taken and went into the raft log — every member holds it in memory, writes it to its journal
# and sends it to a follower that lags, and while one entry that size crosses the network the leader's heartbeats
# wait behind it. A row is a couple of hundred bytes; what makes one big is a field that belongs in an object. So a
# row's items weigh at most `MAX_VALUE` bytes, counted as every store counts them (`variables.items_bytes`: keys and
# values, as bytes, `limits.py`): refused at the door (413 `toolarge`, before
# anything is submitted) and again by the machine, whose refusal is a function of the command alone, so every member
# refuses the same. 512 KiB is Consul's ceiling for a value on the same `hashicorp/raft` the product runs
# (`kv_max_value_size`), for the same reason; it is a thousand times a row, and eight times the 64 KiB the capped
# stores of the tests declare — no row the code writes comes near it. `FileVariables` has no ceiling of its own, so a
# box's rows are measured at the import (`configstore.import_rows`), all of them before the first write.
#
# ## The rights file — who may do what, by the socket the caller came through
# `/etc/w2c/configstore-rights.json` (generated from the specs by `python3 -m w2cplatform.cluster rights`), in the product's
# format (its configstore round 2):
#     {"roles": {"testsubworker": {"group": "testsub-worker", "read": ["testsub/*"],
#                                  "write": ["testsub/epoch/*", "testsub/slots/*"], "delete": []}, …}}
# A trailing `*` is a prefix, anything else one key; a pattern that starts with `!` DENIES, and the denials are asked
# before the grants (`"read": ["domain/*", "!domain/break-glass/*"]`). The daemon opens a socket per role, owned by the
# role's `group` (`configstore.socket_group`; a role without one: `w2c-<role>`), so
# a role is WHICH socket a process could open (its unit's `SupplementaryGroups=`), and `Rights.allows` is asked
# before anything is forwarded or applied. `admin` is the root-only socket and may do everything but two things
# nobody does: delete an epoch row, or delete `domain/*` — which only the domain's own roles do (`DOMAIN_ROLES`:
# `domain`, `domainagent`; a subsystem's worker on the domain in its own prefix, `rights.may_delete_domain`). `list`
# names every key under the prefix to every role — names, nothing of a value; `get` of a key it may not read is 403
# (ADR-0021's addition of 2026-10-10, the product's rule: "`list` without `read`", as on Nomad — a role is a process of
# this box, ADR-0034, and a row's name is no secret to it; what people see is the console's, by its own rights).
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

from .epoch import EPOCH_FLOOR_AT, EPOCH_FLOOR_FIELD, EPOCH_FLOOR_KEY
from .rights import DOMAIN_ROLES, allowed, may_delete_domain, valid as _pattern   # noqa: F401  DOMAIN_ROLES: named here for the daemon
from .variables import epoch_row, items_bytes, safe_path, guard_check

OP_MEMORY = 50_000         # write answers remembered by id; a retry comes within seconds, this is hours of writes
OP_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")         # a write's operation id (the handle's: 32 hex digits)
CAS_WORD = re.compile(r"^[A-Za-z0-9_-]{0,32}$")      # a `cas` that is a string: "" (create-only), digits, a word
CAS_MAX = 1 << 63                                    # a `cas` that is a number: a version, which is a log index
MAX_KEY_BYTES = 1024       # raw UTF-8 key bytes; only File may refuse an encoded filename earlier
MAX_VALUE = 512 << 10      # what a row's items may weigh (`items_bytes`): see the notes above
MAX_JSON_DEPTH = 64        # containers, root included; М10/1 implementation choice 9
ADMIN = "admin"            # the root-only socket's role
PEER = "configstore"       # another daemon, on the mutually authenticated `-api` door
# A door without a vote (ADR-0070 step 5; `configstoredoor.py`), on a voter's `-api` door with a door's certificate: its
# own requests are asked as this role — its row of the doors, `DOORS_PREFIX<id>`, and nothing else; its processes'
# requests as the role of the socket they came in on.
DOOR = "configstore-door"
DOORS_PREFIX = "platform/doors/configstore/"
# The roles that may delete `domain/*`, and how a pattern is asked: the platform's one evaluator (`rights.py`), which the
# in-process ACL of a box's `file://` and `memory://` stores asks too.


class Unavailable(Exception):
    """No leader took the command within the wait: NOT done (a write), or not answered (a read)."""


class Ambiguous(Unavailable):
    """A write reached a leader that went before answering: it may yet be applied. Repeat only with the same id."""


class BadRequest(ValueError):
    """The request's form, before key rules or any store operation (М10/1 Н2.1)."""


def query_value(query: str, name: str, *, required: bool = False) -> bytes:
    """WHATWG urlencoded bytes; only the parameter this operation reads must be unique."""
    values = []
    for pair in query.encode("utf-8", "surrogateescape").split(b"&"):
        key, _, value = pair.partition(b"=")
        if urllib.parse.unquote_to_bytes(key.replace(b"+", b" ")) == name.encode("ascii"):
            values.append(urllib.parse.unquote_to_bytes(value.replace(b"+", b" ")))
    if len(values) > 1 or (required and not values):
        raise BadRequest(f"{name} must occur exactly once" if required else f"{name} must not repeat")
    return values[0] if values else b""


def parse_command(raw: bytes) -> dict:
    """Storage JSON syntax, with field-specific Unicode checks left to validation.

    Extra fields may contain huge numbers or lone surrogates; they are never interpreted. The general
    canonical parser's Unicode/float checks belong to typed documents, not this command's ignored fields.
    """
    def object_(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise BadRequest("a JSON object repeats a field name")
            result[key] = value
        return result

    def integer(text):
        # Only the operator's floor uses a number; every other read field is a string/object. Unread numbers
        # retain a non-string marker, without the interpreter's digit limit or a floating-point range limit.
        return int(text) if len(text) <= 20 else object()

    def constant(_):
        raise BadRequest("NaN and Infinity are not JSON")

    try:
        body = json.loads(raw.decode("utf-8"), object_pairs_hook=object_, parse_int=integer,
                          parse_float=lambda _: object(), parse_constant=constant)
        pending = [(body, 0)]
        while pending:
            value, depth = pending.pop()
            if isinstance(value, (dict, list)):
                depth += 1
                if depth > MAX_JSON_DEPTH:
                    raise BadRequest(f"JSON is nested past {MAX_JSON_DEPTH} containers")
                pending.extend((v, depth) for v in (value.values() if isinstance(value, dict) else value))
        return body
    except (ValueError, RecursionError):
        raise BadRequest("the body is not JSON within this door's parsing bounds") from None


# -- keys ---------------------------------------------------------------------------------------------
# The common door/memory key bound is raw UTF-8. FileVariables additionally checks its encoded filename.
def check_key(key) -> str:
    if not isinstance(key, str):
        raise ValueError(f"not a key: a {type(key).__name__}")
    if len(key.encode()) > MAX_KEY_BYTES:
        raise ValueError(f"not a key: longer than {MAX_KEY_BYTES} bytes")
    safe_path(key)                                # after the length: its refusal quotes the key
    return key


# What a write names besides its key and items, bounded (the notes: "What a caller names is bounded too"). Raises
# `ValueError` naming the field, never quoting it. The door adds the strict wire grammar before submission.
def check_write(cmd: dict) -> None:
    if "guard" in cmd and cmd["guard"] is None:
        raise ValueError("guard is {key, index}, never null")
    op_id = cmd.get("id")
    if op_id is not None and not (isinstance(op_id, str) and OP_ID.match(op_id)):
        raise ValueError("a write's id is up to 64 letters, digits, - and _")
    guard_check(cmd.get("guard"))
    if cmd.get("guard") is not None:
        check_key(cmd["guard"]["key"])
        check_write({"cas": cmd["guard"]["index"]})
    cas = cmd.get("cas")
    if cas is None or isinstance(cas, bool):
        return
    if isinstance(cas, int) and -CAS_MAX < cas < CAS_MAX:
        return
    if isinstance(cas, str) and CAS_WORD.match(cas):
        return
    raise ValueError('a write\'s cas is null, a version, "" (create-only) or a word of up to 32 letters and digits')


def wire_version(value):
    return isinstance(value, str) and (value == "" or re.fullmatch(r"[1-9][0-9]{0,19}", value) is not None)


def wire_index(value):
    return str(value) if value else ""


def wire_command(body) -> dict:
    """Validate in Н2.1 order and discard unread fields before fingerprinting or replication.

    BadRequest is form; ValueError from check_key is badkey. No store, clock or rights are consulted.
    """
    if not isinstance(body, dict) or body.get("op") not in ("put", "delete"):
        raise BadRequest("a write is an object with op put or delete")
    if not isinstance(body.get("key"), str):
        raise BadRequest("key is a required string")
    key = check_key(body["key"])
    cmd = {"op": body["op"], "key": key, "cas": body.get("cas")}
    if body["op"] == "put":
        items = body.get("items")
        if not isinstance(items, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in items.items()):
            raise BadRequest("items are a map of strings")
        try:
            items_bytes(items)
        except UnicodeError:
            raise BadRequest("items must contain UTF-8 text") from None
        cmd["items"] = dict(items)
    if cmd["cas"] is not None and not wire_version(cmd["cas"]):
        raise BadRequest("cas is null, empty, or a decimal version string")
    if "guard" in body:
        guard = body["guard"]
        if (not isinstance(guard, dict) or set(guard) != {"key", "index"}
                or not isinstance(guard["key"], str) or not guard["key"] or not wire_version(guard["index"])):
            raise BadRequest("guard is {key, index}, index a decimal version string")
        check_key(guard["key"])
        cmd["guard"] = dict(guard)
    if "id" in body:
        if not isinstance(body["id"], str) or not re.fullmatch(r"[0-9a-f]{1,64}", body["id"]):
            raise BadRequest("id is 1 to 64 lowercase hex digits")
        cmd["id"] = body["id"]
    return cmd


# The write an operation id stands for: what a repeat must be to be answered from memory. A function of the command
# alone, so every member keeps the same.
def _fingerprint(cmd: dict) -> str:
    what = json.dumps([cmd.get("op"), cmd.get("key"), cmd.get("items") if cmd.get("op") == "put" else None,
                       cmd.get("cas"), cmd.get("guard")], sort_keys=True, default=str)
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
        if op == "floor":
            # the floor under every epoch, raised and never lowered, with the hour its generation was set
            # (`answer`: the operator's alone; ADR-0070)
            have = self.rows.get(EPOCH_FLOOR_KEY, ({}, 0))[0].get(EPOCH_FLOOR_FIELD, "0")
            floor = int(cmd.get("floor", 0) or 0)
            if floor > (int(have) if have.isascii() and have.isdigit() else 0):
                items = {EPOCH_FLOOR_FIELD: str(floor)}
                if cmd.get(EPOCH_FLOOR_AT) is not None:
                    items[EPOCH_FLOOR_AT] = str(int(cmd[EPOCH_FLOOR_AT]))
                self.rows[EPOCH_FLOOR_KEY] = (items, self.version(index))
            self.wrote = True
            return {"index": self.version(index)}
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
            return {**res, "again": True}
        current = self.rows.get(key, (None, 0))[1]
        cas = _cas(cmd.get("cas"))
        guard = cmd.get("guard")
        guarded = self.rows.get(guard["key"], (None, 0))[1] if guard is not None else None
        if guard is not None and _cas(guard["index"]) != guarded:
            res = {"error": "guard", "key": guard["key"], "index": guarded}
        elif cas is not None and cas != current:
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
            if not isinstance(role, str) or not _ROLE.match(role) or role in (ADMIN, PEER, DOOR):
                raise ValueError(f"not a role name: {role!r} (lower case, digits, - and _; {ADMIN!r}, {PEER!r} and "
                                 f"{DOOR!r} are the store's own)")
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
        if action == "delete" and (epoch_row(key) or (key.startswith("domain/") and not may_delete_domain(role, key))):
            return False                          # nobody, `admin` included (`variables.refuse_delete`)
        if action != "read" and key == EPOCH_FLOOR_KEY:
            return False                          # the floor under every epoch is `configstore recover`'s alone (ADR-0070)
        if role == ADMIN:
            return True                           # `PEER` is no role of the file: no grant on any row (twelfth pass)
        return allowed(self.roles.get(role, {}).get(action, []), key)   # a denial first, wherever it stands


# -- the API ------------------------------------------------------------------------------------------
def fault(code: int, kind: str, error: str, **more) -> tuple[int, dict]:
    return code, {"kind": kind, "error": error, **more}


def too_large(key: str, size: int) -> tuple[int, dict]:
    return fault(413, "toolarge", f"{key}: a row of {size} bytes; a row here weighs at most {MAX_VALUE}",
                 key=key, size=size, limit=MAX_VALUE)


def answer(method: str, target: str, raw: bytes, role: str, rights: Rights, submit) -> tuple[int, dict]:
    """One request of the data API, as `role`: rights first, then the command through `submit(cmd)` — the log on a
    daemon, the machine itself on a stand. Returns (status, body). Never raises for what a caller sent."""
    path, _, query = target.partition("?")
    try:
        if method == "GET" and path == "/v1/get":
            key = check_key(query_value(query, "key", required=True).decode("utf-8"))
            if not rights.allows(role, "read", key):
                return fault(403, "forbidden", f"{role} may not read {key}")
            got = submit({"op": "get", "key": key})
            return 200, {"items": got["items"], "index": wire_index(got["index"])}
        if method == "GET" and path == "/v1/list":
            prefix = query_value(query, "prefix")
            if len(prefix) > MAX_KEY_BYTES:
                return 200, {"keys": {}}          # longer than any key: nothing to match, nothing to ask the log
            try:
                text_prefix = prefix.decode("utf-8")
            except UnicodeError:
                text_prefix = ""                  # a byte prefix may stop inside a character
            got = submit({"op": "list", "prefix": text_prefix})
            return 200, {"keys": {key: wire_index(index) for key, index in got["keys"].items()
                                  if key.encode("utf-8").startswith(prefix)}}
        if method == "POST" and path == "/v1/write":
            body = parse_command(raw)
            if isinstance(body, dict) and body.get("op") == "floor":
                # THE FLOOR UNDER EVERY EPOCH, RAISED (ADR-0070; the external review of 2026-10-11; the product's
                # `OpFloor`): the operator's alone — root's `admin.sock`, a restore before its first row — never a
                # role's; raised, never lowered. No `put` or `delete` of the row goes through any door (`Rights.allows`).
                floor, at = body.get("floor"), body.get(EPOCH_FLOOR_AT, "")
                if role != ADMIN or isinstance(floor, bool) or not isinstance(floor, int) or not 0 < floor < CAS_MAX:
                    return fault(403, "forbidden", "the floor under every epoch is raised by the operator alone "
                                                   "(admin.sock: a restore), to a number above 0")
                if at != "" and (isinstance(at, bool) or not isinstance(at, int) or not 0 <= at < CAS_MAX):
                    return fault(400, "badrequest", f"{EPOCH_FLOOR_AT} is the hour since 2026-01-01 UTC the floor is "
                                                    f"raised at, a whole number, or nothing")
                got = submit({"op": "floor", "floor": floor, **({EPOCH_FLOOR_AT: at} if at != "" else {})})
                return 200, {"index": wire_index(got["index"]), **({"again": True} if got.get("again") else {})}
            cmd = wire_command(body)
            key = cmd["key"]
            if body["op"] == "put":
                size = items_bytes(cmd["items"])
                if size > MAX_VALUE:
                    return too_large(key, size)
            action = "write" if body["op"] == "put" else "delete"
            if not rights.allows(role, action, key):
                return fault(403, "forbidden", f"{role} may not {action} {key}")
            if body.get("guard") is not None and not rights.allows(role, "read", body["guard"]["key"]):
                return fault(403, "forbidden", f"{role} may not read {body['guard']['key']}")
            if body.get("id"):
                cmd["id"] = body["id"]
            got = submit(cmd)
            if got.get("error") == "guard":
                return fault(412, "guard", "guard", key=got["key"], index=wire_index(got["index"]))
            if "error" in got:
                return fault(400, "badrequest", got["error"])
            if "toolarge" in got:
                return too_large(key, got["toolarge"])
            if got.get("conflict"):
                # The version now, not the one the write named: what the caller sent is not said back to it.
                return fault(409, "conflict", f"{key}: the version is {got['index'] or 'absent'}, not the one the "
                                              f"write named", index=wire_index(got["index"]))
            return 200, {"index": wire_index(got["index"]), **({"again": True} if got.get("again") else {})}
        return fault(404, "badrequest", f"no such route: {method} {path}")
    except BadRequest as e:
        return fault(400, "badrequest", str(e))
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
