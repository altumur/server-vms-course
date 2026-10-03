"""The subsystem contract — what the platform knows about any subsystem,
and it is all of this:

    a config prefix        <name>/*                      writable by the controller only
    assignment rows        <name>/workers/<worker>       what each worker should run
    a heartbeat object     <name>/<worker>/heartbeat     {ts, status: [...]} — the worker's own report
    an epoch prefix        <name>/epoch/<unit>           fencing tokens the workers take by CAS
    an event log           <resource>/<name>/<unit>/e<epoch>/<start>Z.events.jsonl   (w2cplatform.events)
                                                         what a worker observed about a unit it holds the epoch for;
                                                         on its server's resource, under the subsystem's prefix
    a slot prefix          <name>/slots/<worker>         identity by claim: a worker's name is a slot it
                                                         holds by CAS and renews; a replacement process
                                                         takes the lapsed slot and inherits its assignment

Who decides how many workers there are: not the controller. The scheduler
runs `count` of them (Nomad, or `systemctl start vmsworker@w-N` on one box)
and an autoscaler moves `count` from a headroom metric the workers export.
The platform's part is to give `count` interchangeable processes stable
names — the slots — so that assignments survive a reschedule. A slot is
released on an orderly stop (scale-in); the controller then redistributes
what the slot held. A slot that merely lapses (a crash) is left alone: the
scheduler brings the process back, and it claims the same slot.

`Controller` and `Worker` are the two base classes. The platform never
imports anything from a subsystem; the live and det subsystems prove the
shape is generic by running a subsystem that counts seconds through it.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # contract.py — the subsystem contract: Subsystem, Assignment, Heartbeat, Slot, and the Controller and
# Worker base classes
#
# **Role in the module.** Lesson 1. This file is the whole of what the platform knows about any subsystem,
# and it is deliberately small: a config prefix `<name>/*` writable by the controller only; assignment rows
# `<name>/workers/<worker>`; a heartbeat object `<name>/<worker>/heartbeat`; an epoch prefix
# `<name>/epoch/<unit>` the workers take by CAS; an event log on the resource (`events.py`); and a slot
# prefix `<name>/slots/<worker>` — identity by claim. It depends on `variables.py`, `objects.py`,
# `epoch.py` and `longpoll.py` (a loop's early pass) and nothing else. `spec.SpecController` extends `Controller`; `vms.worker.VmsWorker` and the
# gateway (`vms/liveworker.py`) and the detector (`vms/detworker.py`) extend `Worker`. The file's own docstring settles who
# decides how many workers there are: not the controller. The scheduler runs `count` of them; the platform's
# part is to give those interchangeable processes stable names — the slots — so assignments survive a
# reschedule. A slot released on an orderly stop is redistributed by the controller; a slot that merely
# lapses is a crash, left alone for the scheduler.
#
# ## Module-level names
# None (dataclasses and classes only).
#
# ### `__init__(self, sub, name, vars_, objects, lease_ttl=30.0, lease_margin=5.0, clock=time.monotonic,
# wall=time.time, instance=None, slot_ttl=45.0)` `name` is the slot name, or `None` until `claim_slot()`.
# `instance` identifies the process (`hostname:pid:6hex` by default) and is what a slot row records as
# `holder`. Keeps two clocks: monotonic for leases, wall for slot expiry. `epochs` and `leases` are per-unit
# dicts, empty at start.
#
# ## Notes
# - The tests enforce the boundary: `test_the_platform_knows_nothing_about_video` asserts no import from
#   `vms/` and not the word "camera" in this file; `test_lesson8_live.py` and `test_lesson9_det.py` run two more subsystems through the
#   same `Controller`/`Worker`.
# - Ordering that matters: a worker claims its slot before reading its assignment (the name is the row key);
#   it takes an epoch before writing anything for a unit; it renews slot and leases on a shorter period than
#   `slot_ttl` / `lease_ttl − margin`.
# - `until` is wall-clock while leases are monotonic: slots are compared across processes and boxes, leases
#   only within one process.
# ================================================================================================
from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field

from .blobs import BLOBS, is_digest
from .epoch import Lease, next_epoch
from .objects import ObjectStore
from .rows import PARSE_ERRORS, Table, garbled_counts
from .longpoll import LongPoll, Wake, enabled as long_poll_enabled
from .variables import Conflict, Variables, cas_pause

log = logging.getLogger(__name__)

# What layout of the store this build understands. A rolling upgrade means old and new processes read and
# write the same rows for a while, so adding a field is free and changing what one MEANS is not: that is a
# new number here, and a step the operator takes once everything is new.
SCHEMA = 1
SCHEMA_KEY = "platform/schema"
BUILD = os.environ.get("BUILD", "dev")            # what a person reads on /schema; the machine reads SCHEMA

# The snapshot shard for units no worker holds. Reserved inside `<name>/snapshot/`, which is otherwise the
# worker name space — see `Subsystem.snapshot_key`.
UNPLACED = "unplaced"

# The object-store directory a subsystem's heartbeats live in: `<name>/heartbeats/<worker>`.
#
# It used to be `<name>/<worker>/heartbeat`, with the worker's name as the FIRST segment — and that one
# decision made the grant un-narrowable. A worker's name is claimed at run time (`claim_slot` hands out
# `w-1`), and a scheduler's ACL policy is static text, so "may write its own heartbeat and nothing else"
# could not be written down: the narrowest expressible grant was `objects/<name>/*`, the whole subsystem,
# which also covers the snapshot shards М12 reads and the blobs the workers trust.
#
# Moving the worker to the LAST segment makes it expressible. Three sibling directories under the
# subsystem, one writer each: `heartbeats/` the workers, `snapshot/` the controller, `blobs/` the console.
# A prefix that cannot be bounded by a policy is a layout problem, not a missing ACL feature.
HEARTBEATS = "heartbeats"
REQUESTS = "requests"      # `<name>/requests/<id>`: bounded work an operator asked for, written by the console
CONTROLLER_PASS = "controller/pass"   # `<name>/controller/pass`: the controller's report on its last pass (`SpecController.pass_once`)


# `<subsystem>/heartbeats/<worker>`, or the resource's `platform/resources/<server>/heartbeat`, which has
# a bounded prefix of its own and stays as it is.
def is_heartbeat_key(key: str) -> bool:
    return f"/{HEARTBEATS}/" in key or key.endswith("/heartbeat")


# What `builds()` calls the process behind such a key: `<subsystem>/<worker>`, or the resource's own path.
def heartbeat_owner(key: str) -> str:
    if f"/{HEARTBEATS}/" in key:
        sub, _, worker = key.partition(f"/{HEARTBEATS}/")
        return f"{sub}/{worker}"
    return key[: -len("/heartbeat")]


class SchemaTooNew(Exception):
    """This build does not understand the layout the store is already in."""


class NoSlot(RuntimeError):
    """This instance gave its slot up and has not claimed another yet: it is nobody, and takes nothing."""


# The store's layout version — absent means "whatever this build is", which is a fresh install.
def schema_version(vars_) -> int:
    items, _ = vars_.get(SCHEMA_KEY)
    return int((items or {}).get("version", SCHEMA))


# Called by every process that touches the store, at construction. A build older than the store refuses to
# run rather than read rows it will misunderstand — loudly, in a restart loop the operator can see, and not
# quietly with half the fields dropped on the next read-modify-write.
#
# Note which direction is checked. A NEWER process against an older store is fine and is the whole of a
# rolling upgrade: it understands the old layout. The version is raised afterwards, once, by the operator —
# never by the first new process to start, which would lock out every machine not yet upgraded and turn a
# rolling upgrade into an outage.
#
# A ROW THAT DOES NOT PARSE (the review's third pass). `platform/schema` is one row every process reads — at
# construction and at every slot renewal — and a hand edit that made `version` a word raised out of `renew_slot`
# in every process at once: no lease renewed, no heartbeat, the whole fleet fenced by one bad field. Two cases,
# decided apart. A process that already RAN against this store passes `last` — the version it read whole — and
# keeps it: the layout did not change under it because a field stopped parsing, and a raise that newer builds
# would get is a raise only a version that PARSES as newer earns. A process that never read it has nothing to
# keep, and refuses to start, loudly, as for a newer layout: it cannot name the layout it would be reading.
def check_schema(vars_, last: int | None = None) -> int:
    try:
        have = schema_version(vars_)
    except (ValueError, TypeError) as e:
        if last is None:
            raise SchemaTooNew(f"{SCHEMA_KEY} does not parse ({e}), and this process has never read it: it does not "
                               f"start on a layout it cannot name") from None
        log.warning("%s does not parse (%s); schema %d, as last read, stands", SCHEMA_KEY, e, last)
        return last
    if have > SCHEMA:
        raise SchemaTooNew(f"store is at schema {have}; this build understands {SCHEMA}")
    return have


# Every process that heartbeats, with the schema it understands and the build it is. The keys are
# `<subsystem>/heartbeats/<worker>` and `platform/resources/<server>/heartbeat`; nothing else matches, so
# one scan answers "what is running in this cluster" across subsystems.
def builds(objects, now: float, lost_after: float = 45.0) -> dict[str, dict]:
    def parse(raw: bytes) -> dict:                    # a worker's or a resource's: the three fields this reads, checked
        d = dict(json.loads(raw))
        return {"schema": int(d.get("schema", SCHEMA)), "build": d.get("build", "?"), "ts": float(d.get("ts", 0))}

    out = {}
    for key in objects.list(""):
        if not is_heartbeat_key(key):
            continue
        raw = objects.get(key)
        d = parse_heartbeat(key, raw, parse) if raw else None
        if d is not None:
            out[heartbeat_owner(key)] = {**d, "live": is_live(key.split("/", 1)[0], d["ts"], now, lost_after)}
    return out


# -- reading heartbeats: one that does not parse, and whose clock its time is (the review's second pass, M6, M9) --
# Every reader of a heartbeat object comes through these two.
#
# A heartbeat that does not parse — a build that wrote something else under the key, a bad disk — is ONE
# object's trouble: skipped and counted, never the end of the pass that read it. A controller's pass used to
# stop at it, every pass, until somebody deleted the file by hand. The count is on `/metrics` as
# `<sub>_heartbeats_garbled`; the log names the key, once per object until it parses again.
GARBLED: dict[str, int] = {}                      # subsystem -> heartbeat objects that did not parse, this process
_garbled_keys: set[str] = set()


def parse_heartbeat(key: str, raw: bytes, parse=None):
    """The object parsed, or None — skipped, counted, and logged once."""
    try:
        hb = (parse or Heartbeat.from_bytes)(raw)
        # …and its status is a list of OBJECTS (the review's seventh pass, the walk over every reader): an entry that
        # is a word parsed, and raised `AttributeError` in every reader that asks an entry `.get` — `holder_of`, the
        # read model, the running gauge — each a loop over every worker.
        if isinstance(hb, Heartbeat) and not all(isinstance(s, dict) for s in hb.status):
            raise TypeError("a status entry is not an object")
    except PARSE_ERRORS:                          # `OverflowError` (`ts: 10**400`) and `RecursionError` too (the ninth review's sweep)
        sub = key.split("/", 1)[0]
        GARBLED[sub] = GARBLED.get(sub, 0) + 1
        if key not in _garbled_keys:
            _garbled_keys.add(key)
            log.warning("%s: heartbeat does not parse; skipped", key)
        return None
    _garbled_keys.discard(key)
    return hb


# Liveness is `now - ts`, and the two numbers come from two machines' clocks. The skew is measured where it
# is judged — the largest `ts - now` seen per subsystem, on `/metrics` as `<sub>_heartbeat_skew_seconds_max`
# — and a `ts` from the FUTURE by more than the tolerance is not live: a worker whose clock ran ahead would
# stay "live" that long after it died. NTP keeps a cluster within fractions of a second; the tolerance is what
# a box without it still gets away with, and the metric is what says the tolerance is being approached.
FUTURE_TOLERANCE = 5.0
SKEW_MAX: dict[str, float] = {}
# …and the other direction (the review's third pass, M9). A clock running BEHIND makes a live process look old: its
# heartbeat is `lost_after` from "dead" sooner than it should be, and the maximum above never sees it — its skew is
# negative. What can be measured is the oldest heartbeat still judged LIVE, `ts - now` at its most negative: the
# heartbeat period plus the store's lag on a sound cluster (ten-odd seconds), creeping towards `-lost_after` when a
# clock falls behind. On `/metrics` as `<sub>_heartbeat_skew_seconds_min`. A dead process's heartbeat is not live
# and is not counted: the number is about clocks, not about who died — and neither is a caller whose window is no
# liveness at all (`workers_seen(max_age=1e12)`, which LISTS every worker ever seen): wider than `SKEW_MIN_WITHIN`.
SKEW_MIN: dict[str, float] = {}
SKEW_MIN_WITHIN = 300.0


def is_live(sub: str, ts: float, now: float, lost_after: float) -> bool:
    skew = ts - now
    if skew > SKEW_MAX.get(sub, 0.0):
        SKEW_MAX[sub] = skew
    live = -FUTURE_TOLERANCE <= now - ts <= lost_after
    if live and lost_after <= SKEW_MIN_WITHIN and skew < SKEW_MIN.get(sub, 0.0):
        SKEW_MIN[sub] = skew
    return live


# The one row that says which server is going away for a while. It is the platform's, not a subsystem's —
# a machine carries several — and it holds ONE name: a rolling upgrade is one server at a time.
DRAIN_KEY = "platform/drain"


class DrainRefused(Exception):
    """A second server asked to drain while one already is."""


# The server being drained, or "". Read on every placement pass by every subsystem, so it is one small
# row and not a directory: the answer must cost one `get`.
def draining(vars_) -> str:
    items, _ = vars_.get(DRAIN_KEY)
    return (items or {}).get("server", "")


# A name, and the key layout derived from it. Every path the platform touches for a subsystem is produced
# here, so the layout is in one place.
# - `name` — the prefix (`vms`, `live`, `det`).
@dataclass
class Subsystem:
    name: str

    # `<name>/<part>/<part>…` — the generic path builder used by `SpecController` for rows, `next_id`,
    # `placement/<id>`, derived rows and the snapshot key.
    def config(self, *parts: str) -> str:
        return "/".join((self.name,) + parts)

    # `<name>/workers/<worker>`.
    def assignment(self, worker: str) -> str:
        return f"{self.name}/workers/{worker}"

    # `<name>/heartbeats/<worker>` — an object-store key, not a Variable. The worker's name is the LAST
    # segment so that "the workers write here and nowhere else" is a prefix a policy can name; see
    # `HEARTBEATS` above for why the old spelling could not be bounded.
    def heartbeat_key(self, worker: str) -> str:
        return f"{self.name}/{HEARTBEATS}/{worker}"

    # `<name>/heartbeats/` — what a reader lists, and now the ONLY thing under it. The old layout mixed
    # heartbeats in with everything else under `<name>/`, so every reader carried a filter; the filter was
    # never the point, it was the price of the layout.
    def heartbeats_prefix(self) -> str:
        return f"{self.name}/{HEARTBEATS}/"

    # `<name>/snapshot/<worker>` — one object per worker, the same shape the heartbeat key already has.
    # The snapshot used to be ONE object for the whole cluster, and it was the only place in the platform
    # where data grew in a single object: an object store has a ceiling (Nomad Variables: 64 KiB on the
    # whole object), and 600 cameras — the cluster's own design maximum — did not fit under it. Sharded by
    # the worker that holds the unit, it grows the way the cluster grows: more units means more workers
    # means more objects, each the size of one worker's assignment.
    #
    # `unplaced` is the shard for units no worker holds, so no worker may be called that. The key space is
    # shared, and a reserved name needs a rule that reserves it — not a hope. (Nor can the unplaced rows go
    # in `<name>/snapshot` itself: a store backed by a filesystem cannot have both a file and a directory
    # under that one name.)
    def snapshot_key(self, worker: str | None) -> str:
        if worker == UNPLACED:
            raise ValueError(f"a worker may not be called {UNPLACED!r}: that key is the shard for the units "
                             f"no worker holds")
        return f"{self.name}/snapshot/{worker or UNPLACED}"

    # `<name>/sweep` — the blob sweep's own bookkeeping: what it decided to collect, and when it decided.
    # A Variable and not an object, because the decision needs CAS and the blobs do not.
    def sweep_key(self) -> str:
        return f"{self.name}/sweep"

    # `<name>/requests/<id>` — bounded work the OPERATOR asked a worker to do, outside its ordinary pass.
    #
    # The shape the blob sweep's row already has, generalised: the console writes it, a worker's pass reads
    # it, and the platform never looks inside. It exists because the alternative — a POST that answers 202
    # and stores nothing — is a lie that survives right up until somebody checks whether the thing happened.
    # What a request MEANS is the subsystem's: the recorder reads a range to fetch, another subsystem could
    # read something else entirely.
    def request_key(self, rid: str) -> str:
        return f"{self.name}/{REQUESTS}/{rid}"

    def requests_prefix(self) -> str:
        return f"{self.name}/{REQUESTS}/"

    # `<name>/blobs/` — what the sweep lists to find every blob.
    def blobs_prefix(self) -> str:
        return f"{self.name}/{BLOBS}/"

    # `<name>/snapshot/` — what a reader lists to find every shard.
    def snapshot_prefix(self) -> str:
        return f"{self.name}/snapshot/"

    # `<name>/blobs/sha256-<hex>` — the bytes of one `blob` field, named by what they are. Content
    # addressed, so this key is written once and never written again: the object store's
    # last-writer-wins has nothing to decide. See `blobs.py`.
    def blob_key(self, d: str) -> str:
        if not is_digest(d):
            raise ValueError(f"not a digest: {d!r} — a blob field holds `sha256-<hex>`, and the bytes go "
                             f"to the object store first")
        return f"{self.name}/{BLOBS}/{d}"

    # `<name>/epoch/<unit>`.
    def epoch_key(self, unit: str) -> str:
        return f"{self.name}/epoch/{unit}"

    # `<name>/slots/<worker>`.
    def slot_key(self, worker: str) -> str:
        return f"{self.name}/slots/{worker}"

    # `[<name>/*]` — the whole prefix. This is Lesson 1's coarse ACL; `SubsystemSpec.acl_controller` narrows
    # it in Lesson 6 once the console gets its own token.
    def acl_controller(self) -> list[str]:
        return [f"{self.name}/*"]

    # `<name>/holds/<place>` — a PLACE this worker took, as opposed to the slot above, which is WHO the
    # worker is. Same row (`Slot`), same CAS-with-a-lease rule, same fencing; what differs is where the
    # candidates come from. A slot's name a worker invents (`w-<max+1>`) because one process is as good as
    # another. A hold's name it cannot: the places are a list somebody else wrote down — the administrator's
    # volumes, in M10B — and a worker may only take one of those, one at a time, exclusively.
    #
    # Two rows and not one because they answer different questions and lapse for different reasons: the
    # slot says which process of the deployment this is (the scheduler's business), the hold says which
    # archive it writes into (the operator's). A process can lose the second and keep the first — it
    # becomes a spare — and that is a normal state, not a failure.
    def hold_key(self, place: str) -> str:
        return f"{self.name}/holds/{place}"

    # `[<name>/epoch/*, <name>/slots/*, <name>/holds/*]` — a worker writes only epochs, its slot and the
    # place it took; never configuration. The place is the worker's to take precisely because taking it
    # is a claim about this process, not a decision about the system.
    def acl_worker(self) -> list[str]:
        return [f"{self.name}/epoch/*", f"{self.name}/slots/*", f"{self.name}/holds/*"]

    # -- the object store's half of the same question ------------------------------------------------
    # Variables have had an ACL since Lesson 1; the OBJECT STORE never did. On one box that was invisible
    # — `FsObjectStore` has no writer and no prefixes — and on a cluster the ACL is real but lives in a
    # policy file a person maintains by hand, which drifted from the code twice in two commits.
    #
    # So the three grants are DERIVED here, from the same spec the Variables ACLs come from, and the
    # policy files are checked against them. One source, and a test that says so.
    #
    # Each is one directory with one writer, which is what the key layout was rearranged to allow:
    def acl_objects_worker(self) -> list[str]:
        """The workers write their own heartbeats and nothing else."""
        return [f"{self.name}/{HEARTBEATS}/*"]

    # …and the report on its pass (the review's ninth pass, major): `pass_once` writes `<name>/controller/pass`, the one
    # object `/metrics` reads `<name>_units_unplaced` and the last pass from, and this list — and the policy checked
    # against it — granted only the shards: on a cluster with an ACL the report was a 403 every five seconds and the
    # metrics stayed -1 and 0. `tests/test_policies.py` checks the policy against what the stand's processes WRITE now.
    def acl_objects_controller(self) -> list[str]:
        """The controller publishes the snapshot shards — the only thing that leaves the cluster — and its pass report."""
        return [f"{self.name}/snapshot/*", f"{self.name}/{CONTROLLER_PASS}"]

    def acl_objects_console(self) -> list[str]:
        """The console stores the bytes of a `blob` field, beside the row that names them."""
        return [f"{self.name}/{BLOBS}/*"]


# What one worker should run: the row at `<name>/workers/<worker>`.
# - `worker` — the slot name.
# - `units` — the subsystem's unit ids as strings; the platform does not know what they are.
# - `rev` — bumped on every change, so a worker can tell a new assignment from the one it already applied
#   (`assignment_rev` in the VMS heartbeat).
# What a worker that files requests for OTHER subsystems may write, and nothing else.
#
# Every ACL so far has been about one prefix: a subsystem writes inside its own name. Automation is the
# first thing that must reach across, because a scenario's whole job is to ask somebody else to act — and
# the narrowness is the point. Not `vms/*`, which would let it edit cameras; not `vms/requests/*` by
# accident of a wildcard, but by a grant that names the targets out loud in the process's token:
#
#     open_vars(url, writer="autoworker", acl={"autoworker": AUTO.acl_worker() + requests_acl("vms", "rec", "det")})
#
# `requests` is the right family to open because of what it already is: bounded work, addressed to a unit,
# performed by whoever holds it, cleared when done. A grant on it cannot change configuration, cannot
# place anything and cannot outlive the row it writes.
def requests_acl(*subs: str) -> list[str]:
    return [f"{s}/{REQUESTS}/*" for s in sorted(set(subs))]


@dataclass
class Assignment:
    worker: str
    units: list[str]                 # what the subsystem calls its units of work; the platform does not know
    rev: int = 0

    # `{"units": "1,2,3", "rev": n}` — the Variables row form (strings only).
    def to_items(self) -> dict:
        return {"units": ",".join(self.units), "rev": self.rev}

    # The inverse; a missing row is an empty assignment with `rev 0`. Empty strings in the list are dropped.
    @classmethod
    def from_items(cls, worker: str, items: dict | None) -> "Assignment":
        if not items:
            return cls(worker, [])
        return cls(worker, [u for u in items.get("units", "").split(",") if u], int(items.get("rev", 0)))


# A worker's own report, written as one JSON object.
# - `worker` — the name; `ts` — wall-clock time of the write; `status` — a list of per-unit dicts (the read
#   model: `{id, phase, epoch, …}` in the VMS); `extra` — every other top-level key (`server`, `labels`,
#   `capacity`, `headroom`, `conflicts`, `started`, `previous_hb`, …). The platform reads `extra` by name in
#   `SpecController` and the console's `/metrics`; it never defines the keys.
@dataclass
class Heartbeat:
    worker: str
    ts: float
    status: list[dict] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    # `{"worker", "ts", "status", **extra}` as JSON.
    def to_bytes(self) -> bytes:
        return json.dumps({"worker": self.worker, "ts": self.ts, "status": self.status, **self.extra}).encode()

    # The inverse; everything that is not `worker`/`ts`/`status` lands in `extra`.
    @classmethod
    def from_bytes(cls, raw: bytes) -> "Heartbeat":
        d = json.loads(raw)
        extra = {k: v for k, v in d.items() if k not in ("worker", "ts", "status")}
        return cls(d["worker"], float(d["ts"]), list(d.get("status", [])), extra)


# A worker's name as a row: who holds it, until when (wall clock), and whether the last holder let go on
# purpose. This is the mechanism behind identity by claim.
# - `name` — `w-1`; `holder` — the claiming process's `instance` string; `until` — wall-clock expiry of the
#   claim; `released` — True when the holder stopped on purpose (default True for a row that does not exist
#   yet); `gen` — a generation counter bumped on every claim.
@dataclass
class Slot:
    """A worker's name, as a row: who holds it, until when (wall clock), and
    whether the last holder let go of it on purpose."""
    name: str
    holder: str = ""
    until: float = 0.0
    released: bool = True
    gen: int = 0
    by: str = ""                     # a HOLD's row: the slot of the worker holding the place (`claim_hold`)

    # Row conversion; `released` is stored as `"true"`/`"false"`. A missing row is `Slot(name)` — released,
    # no holder.
    def to_items(self) -> dict:
        return {"holder": self.holder, "until": self.until, "released": "true" if self.released else "false", "gen": self.gen,
                **({"by": self.by} if self.by else {})}

    @classmethod
    def from_items(cls, name: str, items: dict | None) -> "Slot":
        if not items:
            return cls(name)
        return cls(name, items.get("holder", ""), float(items.get("until", 0)), items.get("released") == "true",
                   int(items.get("gen", 0)), str(items.get("by", "")))

    # Held, not released, and past `until`: the holder went silent — a crash.
    def lapsed(self, now: float) -> bool:
        return not self.released and self.holder != "" and now > self.until

    # Released, or never held, or past `until`. (A lapsed slot is claimable; a released one is too.)
    def claimable(self, now: float) -> bool:
        return self.released or self.holder == "" or now > self.until


# The integer after the last `-` in a slot name (`w-3` → 3), 0 if not numeric. Used to order free slots and
# to pick the next unused number.
def slot_number(name: str) -> int:
    tail = name.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


# A slot row that does not parse — a hand edit, half a write — is ONE row's trouble, as a heartbeat's is
# (`parse_heartbeat`; the review's sixth pass, a minor). Read bare, one such row among `<name>/slots/` raised out of
# every claim: an instance that had given its name up stayed nobody for ever, its capacity lost with nothing said,
# and the controller's `slots()` — what placement asks who is leaving — stopped every pass at it. The row is skipped
# where slots are listed, counted (`SLOTS_GARBLED`, in every worker's heartbeat as `slots_garbled`) and logged once
# until it parses again.
#
# Through the one reader of rows (`rows.Table`; the review's seventh pass): counted once per ROW until it parses again
# — it was once per read, so one torn row read every lease step grew the count for ever (the seventh pass, a minor).
SLOTS = Table("slot", "skipped — nobody claims it until it is mended")
SLOTS_GARBLED, _garbled_slots = SLOTS.counts, SLOTS.bad     # subsystem -> slot rows that did not parse, this process


def read_slot(key: str, name: str, items) -> "Slot | None":
    """The row parsed, or None — skipped, counted, and logged once."""
    return SLOTS.read(key, lambda: Slot.from_items(name, items))


# An assignment row is the same (the sixth pass, the follow-up) — and it has one number in it, `rev`. Read bare, a
# `rev` with a word in it raised out of `Controller.assignments()`, which is under everything the controller's pass
# does (the sync of assignments with their placement rows, every move, `/where`): one worker's row, and no unit of
# the subsystem was placed. And out of that worker's own pass, every pass.
#
# What the row DECIDES is `units` — a list of names, which cannot fail to parse — and it is read as it stands, with
# `rev 0`: counted (`ASSIGNMENTS_GARBLED`; in the pass report and in a worker's heartbeat as `assignments_garbled`)
# and logged once. The controller's next change to the row writes it whole; `rev` starts again, which costs nothing
# — it is published, never compared across writes.
ASSIGNMENTS = Table("assignment", "read for the units it names")
ASSIGNMENTS_GARBLED, _garbled_assignments = ASSIGNMENTS.counts, ASSIGNMENTS.bad


def read_assignment(key: str, worker: str, items) -> "Assignment":
    """The row parsed — or, when its `rev` does not parse, its units with `rev 0`: counted, and logged once."""
    return ASSIGNMENTS.read(key, lambda: Assignment.from_items(worker, items),
                            Assignment(worker, [u for u in str((items or {}).get("units", "")).split(",") if u]))


# The same for a PLACE's row, `<name>/holds/<place>` — the same row, read by the same people (the review's sixth pass,
# beside the slot's). Read bare, one garbled hold among the candidates raised out of every claim: a recorder took no
# volume at all, and the console's list of volumes failed whole. The row is that place's trouble: no candidate until
# it is mended, counted (`HOLDS_GARBLED`, `holds_garbled` in the heartbeat and on `/metrics`), logged once.
HOLDS = Table("hold", "skipped — nobody takes that place until it is mended")
HOLDS_GARBLED = HOLDS.counts                      # subsystem -> hold rows that did not parse, this process


def read_hold(key: str, place: str, items) -> "Slot | None":
    """A place's row parsed, or None — skipped, counted, and logged once."""
    return HOLDS.read(key, lambda: Slot.from_items(place, items))


# The only writer of `<name>/*`. It holds nothing: every method reads the store, decides, and writes by CAS,
# so two instances are harmless — this is the property `spec.SpecController` and the VMS controller inherit,
# and the reason the controller is never on the recovery path.
class Controller:
    """The only writer of <name>/*. Holds nothing: every method reads the
    store, decides, and writes by CAS. Two instances are harmless."""

    # Keeps the `Subsystem`, the two stores and a wall clock (tests inject a fake).
    def __init__(self, sub: Subsystem, vars_: Variables, objects: ObjectStore, wall=time.time):
        self.sub, self.vars, self.objects, self.wall = sub, vars_, objects, wall
        check_schema(vars_)                       # a build older than the store does not run at all

    # The one write primitive: read `(items, idx)`, call `mutate(dict(items or {}))`; if it returns `None`
    # nothing is written and the current items are returned; otherwise `put(cas=idx)`; on `Conflict` re-read
    # and repeat, up to `retries`, then `RuntimeError`. Every mutation in `SpecController` goes through
    # this, which is what makes "two controllers agree by CAS" true.
    def write(self, path: str, mutate, retries: int = 10) -> dict:
        """Read-modify-write by CAS: `mutate(items or {}) -> new items`.
        A conflict means another instance wrote; re-read and go again."""
        for attempt in range(retries):
            items, idx = self.vars.get(path)
            new = mutate(dict(items or {}))
            if new is None:
                return dict(items or {})
            try:
                self.vars.put(path, new, cas=idx)
                return new
            except Conflict:
                cas_pause(attempt)                   # a random pause, growing: tried again at once, the same writers meet again
                continue
        raise RuntimeError(f"{path}: {retries} conflicts")

    # Which workers exist: those whose heartbeat object under `<name>/` is at most `max_age` old. Never a
    # list the controller keeps — a fact it reads.
    # `test_controller_and_worker_bases_speak_only_the_contract`: after the wall clock advances 100 s a
    # silent worker is not a worker.
    def workers_seen(self, max_age: float = 45.0) -> dict[str, Heartbeat]:
        """Which workers exist: those that heartbeat recently. Never a list
        the controller keeps — a fact it reads."""
        out = {}
        now = self.wall()
        # One prefix, no filter: `<name>/heartbeats/` holds heartbeats and nothing else.
        for key in self.objects.list(self.sub.heartbeats_prefix()):
            raw = self.objects.get(key)
            hb = parse_heartbeat(key, raw) if raw else None
            if hb is not None and is_live(self.sub.name, hb.ts, now, max_age):
                out[hb.worker] = hb
        return out

    # Reads one worker's row. One whose `rev` does not parse is read for the units it names (`read_assignment`).
    def assignment(self, worker: str) -> Assignment:
        items, _ = self.vars.get(self.sub.assignment(worker))
        return self._assignment(worker, items)

    def _assignment(self, worker: str, items) -> Assignment:
        return read_assignment(self.sub.assignment(worker), worker, items)

    # Replaces the worker's assignment with the sorted, de-duplicated list and bumps `rev`.
    def assign(self, worker: str, units: list[str]) -> Assignment:
        def mutate(items):
            rev = self._assignment(worker, items).rev + 1
            return Assignment(worker, sorted(set(units), key=str), rev).to_items()
        return self._assignment(worker, self.write(self.sub.assignment(worker), mutate))

    # Read-modify-write adding one unit; returns `None` from the mutator (no write) if already present. Two
    # controllers adding different units to one worker at once both land.
    def assign_add(self, worker: str, unit: str) -> Assignment:
        """Read-modify-write: two controllers adding different units to one
        worker at once both land."""
        def mutate(items):
            a = self._assignment(worker, items)
            if unit in a.units:
                return None
            return Assignment(worker, sorted(set(a.units) | {unit}, key=str), a.rev + 1).to_items()
        return self._assignment(worker, self.write(self.sub.assignment(worker), mutate))

    # The mirror of `assign_add`.
    def assign_remove(self, worker: str, unit: str) -> Assignment:
        def mutate(items):
            a = self._assignment(worker, items)
            if unit not in a.units:
                return None
            return Assignment(worker, [u for u in a.units if u != unit], a.rev + 1).to_items()
        return self._assignment(worker, self.write(self.sub.assignment(worker), mutate))

    # Every row under `<name>/workers/`.
    def assignments(self) -> dict[str, Assignment]:
        out = {}
        for path in self.vars.list(self.sub.name + "/workers/"):
            worker = path.rsplit("/", 1)[1]
            out[worker] = self.assignment(worker)
        return out

    # -- slots: read them, never hand them out ------------------------------------
    # Every row under `<name>/slots/`, read only — the controller never hands slots out.
    def slots(self) -> dict[str, Slot]:
        out = {}
        for path in self.vars.list(self.sub.name + "/slots/"):
            name = path.rsplit("/", 1)[1]
            items, _ = self.vars.get(path)
            slot = read_slot(path, name, items)   # one that does not parse is not the end of the pass (`read_slot`)
            if slot is not None:
                out[name] = slot
        return out

    # Slots whose holder let go on purpose (scale-in, or `retire`) and that still have units assigned: what
    # a subsystem redistributes. A slot that merely lapsed is not here — that is a crash, and the scheduler
    # brings the process back under the same name. Sorted by slot number.
    def released_slots(self) -> list[str]:
        """Slots whose holder let go on purpose (scale-in, or `retire`) and
        that still have an assignment: what a subsystem redistributes. A slot
        that merely lapsed is NOT here — that is a crash, and the scheduler
        brings its process back under the same name."""
        return sorted((n for n, s in self.slots().items() if s.released and self.assignment(n).units),
                      key=slot_number)

    # -- draining a SERVER ---------------------------------------------------------------------------
    # `retire` is about one allocation; an upgrade is about a machine. One row says which server is going
    # away for a while, and every subsystem reads it through `_pool` and `redistribute` — nothing is told
    # anything, and no subsystem learns a new word.
    #
    # Why it is needed at all, when a stopped process is noticed anyway: being noticed is the SLOW path.
    # A recorder's units move when its slot has lapsed AND its server's resource is silent — two
    # independent silences, about a minute and a half of not recording. A planned stop is not a silence:
    # we know about it before it happens, and the work can leave first.
    #
    # One server at a time, and that is the whole of the mutual exclusion: the row holds ONE name, written
    # by CAS. Two operators, or a buggy script, cannot drain two machines at once by accident.
    def draining(self) -> str:
        """The server being drained right now, or ""."""
        return draining(self.vars)

    def drain(self, server: str) -> dict:
        """An operator's statement that a server is about to stop. Refused while
        another one is draining: a rolling upgrade is one machine at a time."""
        def mutate(items):
            have = (items or {}).get("server", "")
            if have and have != server:
                raise DrainRefused(f"{have} is already draining; one server at a time")
            return {"server": server, "at": str(self.wall())}
        return self.write(DRAIN_KEY, mutate)

    # The operator's one-way step, taken once every machine is new. Refused while anything LIVE says it
    # understands less — which is checkable, because every process publishes the number in its heartbeat.
    # That is the guard that makes the whole scheme safe: you cannot raise the store out from under a
    # machine you forgot to upgrade.
    def set_schema(self, version: int) -> dict:
        now = self.wall()
        behind = {n: b for n, b in builds(self.objects, now).items() if b["live"] and b["schema"] < version}
        if behind:
            raise SchemaTooNew(f"still running: {', '.join(sorted(behind))} — at schema "
                               f"{min(b['schema'] for b in behind.values())}")
        def mutate(items):
            have = int((items or {}).get("version", SCHEMA))
            if version < have:
                raise SchemaTooNew(f"schema does not go back: {have} -> {version}")
            return {"version": str(version), "at": str(now)}
        return self.write(SCHEMA_KEY, mutate)

    def undrain(self) -> dict:
        """The server is back. Its workers become placeable again, and `ensure_home`
        starts bringing back what its rows name — one unit a pass."""
        return self.write(DRAIN_KEY, lambda items: {"server": "", "at": str(self.wall())})

    # An operator's statement that a slot is gone for good: marks it `released` by CAS (no-op if already
    # released). The controller never decides this on its own from a silence.
    def retire(self, worker: str) -> Slot:
        """An operator's statement that a slot is gone for good (the process
        that held it will not return). Marks it released; the subsystem's
        redistribution takes it from there. The controller never decides this
        on its own from ONE silence — a subsystem that requires a resource may
        act on two, the slot's and its server's resource's (spec.gone_servers)."""
        key = self.sub.slot_key(worker)

        def mutate(items):
            s = read_slot(key, worker, items)
            if s is None:
                # A row that does not parse is the slot an operator most wants gone, and `retire` raised on it (the
                # sixth pass, the follow-up). Their word is written over it, whole: released, and nobody's.
                return Slot(worker, "", self.wall(), True, 0).to_items()
            if s.released:
                return None
            return Slot(worker, s.holder, s.until, True, s.gen).to_items()
        return Slot.from_items(worker, self.write(key, mutate))


# Runs its assignment and reports. Reads `<name>/workers/<me>` and the units it names; writes its heartbeat
# object and, when it starts a unit, that unit's epoch by CAS. Never writes configuration. A fresh worker
# rediscovers everything from the store. Subsystems subclass it and implement `reconcile_once`.
class Worker:
    """Runs its assignment and reports. Reads <name>/workers/<me> and the
    units it names; writes its heartbeat object and, when it starts a unit,
    that unit's epoch by CAS. Never writes configuration. A fresh worker
    rediscovers everything from the store."""

    def __init__(self, sub: Subsystem, name: str | None, vars_: Variables, objects: ObjectStore,
                 lease_ttl: float = 30.0, lease_margin: float = 5.0, clock=time.monotonic, wall=time.time,
                 instance: str | None = None, slot_ttl: float = 45.0):
        self.sub, self.vars, self.objects = sub, vars_, objects
        self.schema_seen = check_schema(vars_)    # a build older than the store does not run at all; kept for `renew_slot`
        self.clock, self.wall = clock, wall
        self.lease_ttl, self.lease_margin = lease_ttl, lease_margin
        # How long past a lease's end DATA may still be written while the store is silent (`Lease.may_record`).
        # 0: not at all — every subsystem's default. A subsystem whose units write data sets it: `None` is
        # "for as long as the silence lasts".
        self.unconfirmed_max: float | None = 0.0
        self.epochs: dict[str, int] = {}          # unit -> epoch this worker holds
        self.leases: dict[str, Lease] = {}
        self.instance = instance or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"   # the process; a name is a slot
        self.slot_ttl = slot_ttl
        self.slot: Slot | None = None
        self.name = name                          # None until claim_slot(); a fixed name is a slot claimed by that name
        # The name this instance gave up to another (`keep_slot`) while it has not claimed another: fenced till then.
        self.seeking: str | None = None
        self.hold: str | None = None              # the PLACE this worker took, if its subsystem has places to take
        # One renewal or claim of the hold at a time, from whichever thread (`renew_hold`); and when this process
        # first saw each place's row as it is now — the clock a stale hold is judged by (`claim_hold`).
        self._hold_lock = threading.RLock()
        self._hold_seen: dict[str, tuple[int, float]] = {}
        # The slot row is renewed from two threads now — the loop, and the stand-in while a step hangs — and one
        # claim, renewal or release of it happens at a time (feedback DD).
        self._slot_lock = threading.RLock()
        self._step: dict | None = None            # the loop's step in progress (`guarded`): name, start, the stand-in's notes
        self._step_lock = threading.Lock()
        self.stand_in_renewals = 0                # renewals the stand-in made for a hung step, since start: in the heartbeat
        self._loop_renewed = clock()              # when the loop last renewed its leases (`renew_leases`)
        self._stood_in_since: float | None = None # what `STAND_IN_FOR` is counted from, while steps are being stood in for
        # The long poll (`longpoll.py`): the wait this worker's loop sleeps in, and the requests it holds at the
        # resources. Neither exists until the process asks for them (`poll_events`) — a worker made without them
        # waits `stop.wait(poll)`, exactly as before.
        self.wake: Wake | None = None
        self.long_poll: LongPoll | None = None

    # -- identity by claim ----------------------------------------------------------
    # Become somebody. Lists the slot rows; with `prefer` (Nomad's `NOMAD_ALLOC_INDEX`, systemd's `%i`) the
    # candidate list is just that name and it is taken by CAS even from a holder that has not lapsed — the
    # scheduler is the authority on which process is the current one, and the old holder finds out on its
    # next `renew_slot`. Without `prefer`, candidates are: lapsed slots first (oldest `until` first — their
    # assignment is waiting), then free (released or never held) slots by number, then a fresh `w-<max+1>`.
    # For each candidate, re-read, skip if not claimable (only in the no-`prefer` case), and `put` a new
    # `Slot(cand, instance, now + slot_ttl, released=False, gen+1)` with `cas=idx`; a `Conflict` means
    # someone took it between read and write, move on. Sets `self.slot` and `self.name`.
    # `test_identity_by_claim_is_a_platform_piece`: two nameless workers get `w-1` and `w-2`; after `w-1`
    # lapses a third gets `w-1` back and its assignment with it; `prefer="w-7"` creates and takes `w-7`.
    SLOT_PREFIX = "w"                             # what a slot this worker has to MAKE is called: `<prefix>-<n>`

    def claim_slot(self, prefer: str | None = None, retries: int = 50) -> str:
        """Become somebody. With `prefer` (whatever `runtime.slot` made of
        SLOT_INDEX or a <ROLE>_NAME) take that slot, by CAS, even from a holder
        that has not lapsed — the runtime is the authority on which process is
        the current one,
        and the old holder finds out on its next renewal. Without it, take a
        lapsed slot — its assignment is waiting — before an unused number. Holding is renewed by `renew_slot`; losing it fences the
        instance. The controller never hands names out; a process takes one."""
        with self._slot_lock:
            return self._claim_slot(prefer, retries)

    def _claim_slot(self, prefer: str | None, retries: int) -> str:
        prefix = self.sub.name + "/slots/"
        now = self.wall()
        for attempt in range(retries):
            if attempt:
                cas_pause(attempt - 1)               # every candidate was taken under us: not the same race again at once
            names = [p[len(prefix):] for p in self.vars.list(prefix)]
            # A row that does not parse is no candidate (`read_slot`): skipped, and its number is still counted below,
            # so a slot made new never takes its name.
            known = {n: s for n in names if (s := read_slot(prefix + n, n, self.vars.get(prefix + n)[0])) is not None}
            if prefer is not None:
                order = [prefer]
            else:
                lapsed = sorted((n for n, s in known.items() if s.lapsed(now)), key=lambda n: known[n].until)
                free = sorted((n for n, s in known.items() if s.claimable(now) and not s.lapsed(now)), key=slot_number)
                # A NEW slot is named after the kind of worker taking it (`SLOT_PREFIX`: `r` a recorder, `g` a
                # gateway, `a` an evaluator — the letters a process given a name already had), not `w-` for
                # everybody: a recorder that had to make a slot looked like a camera worker in every list, every
                # heartbeat and every log line (the product's box, feedback BU). Slots that exist keep their
                # names; a lapsed or free one is still taken before a new one is made.
                nxt = f"{self.SLOT_PREFIX}-{max([slot_number(n) for n in names] + [0]) + 1}"
                order = lapsed + free + [nxt]
            for cand in order:
                items, idx = self.vars.get(prefix + cand)
                cur = read_slot(prefix + cand, cand, items)
                if cur is None:
                    if prefer is None:
                        continue                               # garbled since the listing: not a candidate
                    cur = Slot(cand)                           # the runtime named this slot: taken, and written whole again
                if prefer is None and not cur.claimable(now):
                    continue                                   # a preferred slot is taken regardless: the scheduler
                                                               # said this index is mine; the old holder fences on renewal
                new = Slot(cand, self.instance, now + self.slot_ttl, False, cur.gen + 1)
                try:
                    self.vars.put(prefix + cand, new.to_items(), cas=idx)
                except Conflict:
                    continue                                   # somebody took it between the read and the write
                self.slot, self.name = new, cand
                return cand
        raise RuntimeError(f"{self.instance}: could not claim a slot in {retries} tries")

    # Still me? Read the slot; if `holder` is another instance, return False — the instance is fenced as a
    # whole (the VMS worker stops recording on this). Otherwise extend `until` by CAS; a `Conflict` is also
    # False. A worker with no slot (fixed name without claim) returns True — but not one that gave its name up to
    # another instance and has not claimed another yet (`keep_slot`): that one is nobody, and False.
    def renew_slot(self) -> bool:
        """Still me? Read the slot; if another instance holds it now, the
        instance is fenced as a whole. Extends `until` by CAS otherwise."""
        with self._slot_lock:
            return self._renew_slot()

    # The row of this instance's name, read now. One that does not parse is not a row naming ANOTHER holder (the
    # review's sixth pass): read bare it raised out of every renewal — no lease renewed after it, no heartbeat, a
    # worker dead of one field. It is read as the row this instance last wrote, so the renewal writes it whole again,
    # by CAS: nobody else takes a row that does not parse (`_claim_slot` skips it), except a process the runtime gave
    # this very name — and then the row parses again, and names that one.
    def _own_slot(self) -> tuple[Slot, int]:
        key = self.sub.slot_key(self.name)
        items, idx = self.vars.get(key)
        cur = read_slot(key, self.name, items)
        if cur is None:
            cur = Slot(self.name, self.instance, 0.0, False, self.slot.gen if self.slot is not None else 0)
        return cur, idx

    # Whether the row of this instance's name names ANOTHER instance now — read, nothing renewed. For an instance
    # fenced with its slot in hand (a store raised past its build: `renew_slot` raises on the schema before it reads
    # the row): it renews nothing, the row lapses, another process takes the name — and what this one went on saying
    # under it was written over the other's (the review's sixth pass, beside the holder's `rejoin`). Nobody from the
    # look that finds another holder there. A store that does not answer says nothing.
    def name_taken(self) -> bool:
        with self._slot_lock:
            if self.slot is None:
                return self.seeking is not None
            try:
                cur, _ = self._own_slot()
            except OSError:
                return False
            if cur.holder == self.instance:
                return False
            self.seeking, self.slot = self.name, None
            return True

    # The name is not this instance's any more: nobody from this line (`seeking`), whatever is done next — until
    # `_seek_slot` claims another. Returns the name given up.
    def give_up_name(self) -> str:
        with self._slot_lock:
            if self.seeking is None:
                self.seeking = self.name
            self.slot = None
            return self.seeking

    def _renew_slot(self) -> bool:
        if self.slot is None:
            return self.seeking is None           # a fixed name never claimed is itself; a name given up is nobody's here
        # The store's schema, again (the review's second pass, m4). `set_schema` refuses while a LIVE build
        # understands less, and a build that checked at construction and has not heartbeaten yet is not live to
        # it: the version is raised under a process that passed its check a moment ago. So the check is repeated
        # where the slot is renewed, and the worker fences on it as it would on a slot held by somebody else.
        self.schema_seen = check_schema(self.vars, getattr(self, "schema_seen", None))   # a garbled row: what it ran with stands
        cur, idx = self._own_slot()
        if cur.holder != self.instance or cur.released:          # released: `retire` let go of it; a late renewal does not take it back
            return False
        new = Slot(self.name, self.instance, self.wall() + self.slot_ttl, False, cur.gen)
        try:
            self.vars.put(self.sub.slot_key(self.name), new.to_items(), cas=idx)
        except Conflict:
            return False
        self.slot = new
        return True

    # An orderly stop (SIGTERM from the scheduler: scale-in, or a drain). Writes the row with
    # `released=True` and `until=now`, if this instance still holds it; a `Conflict` is ignored. This flag
    # is what tells scale-in from a crash: a crash says nothing and the slot merely lapses.
    # -- the place, as opposed to the identity -------------------------------------
    # Take one of the places the administrator wrote down — `<name>/holds/<place>`, the same row and the
    # same rule as a slot, over candidates this worker did not invent. Returns the place taken, or None
    # when every candidate is held by somebody live, which is not an error: the process is a SPARE, it
    # carries nothing, and it tries again next pass. That is how a place declared in the console gets
    # served without anybody starting a process for it, and how a place that lapses is picked up by
    # whoever is free.
    #
    # Order matters and is the caller's: it passes candidates in the order it wants them taken (a
    # recorder puts its own server's disks before a network archive any box could serve). A `Conflict`
    # means somebody took this one between the read and the write — try the next candidate, and only
    # repeat the sweep if contention was the reason we ran out.
    #
    # THE PLACE FOLLOWS THE NAME (feedback CF). A recorder killed and started again by systemd is the same
    # worker: it takes its slot back at once, from a holder that has not lapsed (`claim_slot(prefer=…)` —
    # М10B Lesson 17: systemd is the authority on which process is the current `r-1`). Its volume did not
    # follow: the hold waited out its TTL — 45 s in which nothing on that volume was recorded, by the very
    # process that held it a moment ago. So a hold says WHOSE slot holds it (`by`), and the worker of that
    # slot takes it back at once, before any other candidate. The previous instance finds out at its next
    # `renew_hold` and stops writing there; what it wrote in between is fenced by the new epochs, as a slot's is.
    # Anybody else still waits for the TTL — the product's own lesson, from its archive daemon: a place
    # kept for its owner must be kept LONGER than the time the owner takes to come back.
    #
    # ONLY A PLACE THAT CANNOT BE WRITTEN FROM TWO HOSTS FOLLOWS THE NAME (the review's sixth pass, blocker 2). The
    # instance that took the name may be on another box, and the one it took it from frozen, not dead. Where the place
    # is a disk that is harmless — the two are on one host. Where any box may write it, taking it at once skipped the
    # one wait the previous holder's write window is measured against (`_hold_stale`), and two instances of one name
    # wrote one volume. The subsystem says which places follow, given who holds the place now (`hold_follows_name`:
    # the row's `holder`, `host:pid:rnd` — the seventh pass gave the same-host restart its place back); the rest wait
    # like anybody's.
    #
    # THE TTL BY THIS HOST'S CLOCK (the review's fourth pass, Т-M5). Anybody else took a hold when the wall clock HERE
    # passed the `until` the holder wrote by ITS wall clock: two machines five seconds apart, and a holder renewing
    # every pass looked lapsed to its neighbour — two writers in one ring, which on s3 the engine's lock does not
    # reliably stop. So a hold of somebody else's is stale when THIS process has watched its row stand still — the
    # same revision, never renewed — for the hold's whole term and `HOLD_SKEW` on top, by its own monotonic clock.
    # A holder that renews changes the row every pass, whatever its clock says; one that stopped leaves it standing.
    # The price: a process that first looks at a long-dead hold waits one term from that look. A released hold, or
    # one nobody holds, is free at once, as before.
    #
    # And no generation in the daemon's `owner` (`rec:<volume>`, `Archive`). The owner is how the next holder of the
    # volume on this host picks up the writer a vanished one left, detached — with a generation in it the successor
    # names another owner, and waits out the daemon's grace with nothing recorded, which is what the owner is there
    # to prevent (feedback CF). The fence is the hold, confirmed by CAS right before every `VOLUME_MOUNT_RW`
    # (`RecWorker._confirm_hold`); on one host the daemon itself keeps one writer per volume.
    HOLD_SKEW = 5.0

    def _hold_stale(self, cand: str, cur: "Slot", idx) -> bool:
        if cur.released or cur.holder in ("", self.instance):
            return True
        now = self.clock()
        seen = self._hold_seen.get(cand)
        if seen is None or seen[0] != idx:
            self._hold_seen[cand] = (idx, now)               # renewed since we last looked — or never looked: from now
            return False
        return now - seen[1] >= self.slot_ttl + self.HOLD_SKEW

    def claim_hold(self, candidates: list[str], retries: int = 20) -> str | None:
        """Take one place out of a list somebody else wrote. None when they are
        all taken — a spare, not a failure."""
        with self._hold_lock:
            return self._claim_hold(candidates, retries)

    def _claim_hold(self, candidates: list[str], retries: int) -> str | None:
        for attempt in range(retries):
            if attempt:
                cas_pause(attempt - 1)
            contended = False
            rows = {c: self.vars.get(self.sub.hold_key(c)) for c in candidates}
            # A row that does not parse is no candidate, and stops nobody from taking another (`read_hold`).
            held = {c: read_hold(self.sub.hold_key(c), c, rows[c][0]) for c in candidates}
            candidates = [c for c in candidates if held[c] is not None]
            # Only while the slot IS this instance's: the instance systemd replaced has the same name, and must not
            # take the place back from its successor on its way out. The slot is read only when a hold names it.
            mine = [c for c in candidates if self.name and held[c].by == self.name]
            slot = read_slot(self.sub.slot_key(self.name), self.name, self.vars.get(self.sub.slot_key(self.name))[0]) if mine else None
            named = slot is not None and slot.holder == self.instance      # (a slot row that does not parse proves nothing)
            mine = mine if named else []
            for cand in mine + [c for c in candidates if c not in mine]:
                key, now = self.sub.hold_key(cand), self.wall()
                idx, cur = rows[cand][1], held[cand]
                ours = named and cur.by == self.name and cur.holder != self.instance and self.hold_follows_name(cand, cur.holder)
                if not ours and not self._hold_stale(cand, cur, idx):
                    continue                                   # somebody live is writing there
                try:
                    self.vars.put(key, Slot(cand, self.instance, now + self.slot_ttl, False, cur.gen + 1, self.name or "").to_items(), cas=idx)
                except Conflict:
                    contended = True; continue
                self._hold_seen.pop(cand, None)
                self.hold = cand
                return cand
            if not contended:
                return None                                    # every place is held: a spare
        return None

    # Whether `place`, held under this worker's NAME by the instance `holder`, is taken back at once (`_claim_hold`).
    # Yes, unless the subsystem knows the place can be written from another host than the holder's
    # (`RecWorker.hold_follows_name`).
    def hold_follows_name(self, place: str, holder: str = "") -> bool:
        return True

    # Still mine? Same three lines as `renew_slot`, and the same meaning when it says no: another process
    # holds this place now, so this one must stop writing into it. Losing a hold is NOT losing the slot —
    # the process stays itself and becomes a spare.
    #
    # ONE AT A TIME, AND A LOST RACE IS READ AGAIN (the review's fourth pass, a minor). The recorder renews from two
    # threads — the pass, and a keep's `seal`, which confirms the hold before it mounts the writer again — and the
    # one that lost the CAS to the other took the conflict for the hold taken: let go of its own fresh hold, stopped
    # writing, and waited out the term to take it back. Renewals are serialised now, and a conflict is answered by
    # the row: still ours — somebody of ours renewed it a moment ago — is ours.
    def renew_hold(self) -> bool:
        with self._hold_lock:
            if self.hold is None:
                return True
            key = self.sub.hold_key(self.hold)
            cur, idx = self._own_hold()
            if cur.holder != self.instance:
                self.hold = None
                return False
            try:
                self.vars.put(key, Slot(self.hold, self.instance, self.wall() + self.slot_ttl, False, cur.gen, self.name or "").to_items(), cas=idx)
            except Conflict:
                again = read_hold(key, self.hold, self.vars.get(key)[0])
                if again is not None and again.holder == self.instance and not again.released:
                    return True
                self.hold = None
                return False
            return True

    # The row of the place this instance holds, read now. One that does not parse is not a row naming ANOTHER holder:
    # it is read as the row this instance last wrote — as its slot's is (`_own_slot`) — so a renewal or a release
    # writes it whole again, by CAS. Nobody else takes a hold row that does not parse (`_claim_hold` skips it).
    def _own_hold(self) -> tuple[Slot, int]:
        key = self.sub.hold_key(self.hold)
        items, idx = self.vars.get(key)
        cur = read_hold(key, self.hold, items)
        if cur is None:
            cur = Slot(self.hold, self.instance, 0.0, False, 0, self.name or "")
        return cur, idx

    # Let go on purpose: an orderly stop, or the administrator deleted the volume. `released` is what
    # tells that apart from a crash, and a released place is taken again at once instead of after a TTL.
    def release_hold(self) -> None:
        if self.hold is None:
            return
        cur, idx = self._own_hold()
        if cur.holder == self.instance:
            try:
                self.vars.put(self.sub.hold_key(self.hold), Slot(self.hold, self.instance, self.wall(), True, cur.gen, self.name or "").to_items(), cas=idx)
            except Conflict:
                pass
        self.hold = None

    def release_slot(self) -> None:
        """An orderly stop (SIGTERM from the scheduler: scale-in, or a drain).
        Says so in the row — `released` — which is what tells scale-in from a
        crash. A crash says nothing, and the slot merely lapses."""
        with self._slot_lock:
            if self.slot is None:
                return
            cur, idx = self._own_slot()
            if cur.holder == self.instance:
                try:
                    self.vars.put(self.sub.slot_key(self.name), Slot(self.name, self.instance, self.wall(), True, cur.gen).to_items(), cas=idx)
                except Conflict:
                    pass
            self.slot = None

    # Reads my row. One whose `rev` does not parse is read for the units it names (`read_assignment`): the pass is
    # a pass, and what the row decides is carried out.
    def assignment(self) -> Assignment:
        if self.seeking is not None:
            return Assignment(self.name, [])      # the row under that name is the other instance's now (`keep_slot`)
        key = self.sub.assignment(self.name)
        items, _ = self.vars.get(key)
        return read_assignment(key, self.name, items)

    # Called when the worker starts a unit: `next_epoch` on `<name>/epoch/<unit>`, record it in `epochs`,
    # and open a `Lease` on it. A second worker starting the same unit gets the next number, and the first
    # one's lease fences on renewal.
    def take_epoch(self, unit: str) -> int:
        """Called when the worker STARTS a unit: a new epoch, by CAS, and a
        lease on it. A second worker starting the same unit gets the next
        number, and the first one's lease will fence on renewal."""
        if self.seeking is not None:
            raise NoSlot(f"{self.instance} gave slot {self.seeking} up and holds no other: no epoch for {unit}")
        epoch, _ = next_epoch(self.vars, self.sub.epoch_key(unit))
        self.epochs[unit] = epoch
        self.leases[unit] = Lease(self.vars, self.sub.epoch_key(unit), epoch, self.lease_ttl, self.lease_margin, self.clock,
                                  self.unconfirmed_max)
        return epoch

    # Forget the unit's epoch and lease (the worker stopped it). The lease is marked let go as well: the stand-in may
    # hold it from before, and a lease the loop released is renewed by nobody.
    def release(self, unit: str) -> None:
        self.epochs.pop(unit, None)
        lease = self.leases.pop(unit, None)
        if lease is not None:
            lease.release()

    # Forget every unit — a worker that is nobody now and starts from nothing.
    def release_all(self) -> None:
        for unit in list(self.leases):
            self.release(unit)
        self.epochs.clear()

    # The unit's lease says so, and there is one.
    def may_write(self, unit: str) -> bool:
        lease = self.leases.get(unit)
        return lease is not None and lease.may_write()

    # The wider question, for data: also a lease that ran out while the store was silent (`Lease.may_record`).
    def may_record(self, unit: str) -> bool:
        lease = self.leases.get(unit)
        return lease is not None and lease.may_record()

    # Units recording past their lease's end, unconfirmed: `{unit: seconds}`.
    def unconfirmed(self) -> dict[str, float]:
        return {u: round(l.unconfirmed(), 1) for u, l in self.leases.items() if l.unconfirmed() > 0}

    # Renews every lease; returns the units whose lease was lost — fenced or expired — for the subsystem to
    # stop.
    # THE SLOT ROW, KEPT BY EVERY LOOP — not only the holder's and the evaluator's (found beside the stand-in, after
    # the fourth review). The detector, scan, survey and gateway workers claimed their slot once, at construction,
    # and never renewed it: the row lapsed after `slot_ttl` in ordinary work, and a spare or a restarted process
    # could take the name of a worker that was alive and holding units. `keep_slot` renews it on the loop's lease
    # step; a store that does not answer keeps the slot (not known is not "taken"); a row naming ANOTHER instance
    # means this one is a zombie on that name: it lets its units go (`let_go`, the worker's own stop), gives up
    # their epochs and claims a free slot.
    #
    # NOBODY UNTIL IT HAS ONE (the review's fifth pass, blocker 3). The claim that follows can fail — the store blinks,
    # every candidate is taken under it — and the worker was left with no slot and the OLD name: `renew_slot` with no
    # slot said "still me", the stand-in renewed for it, the next pass read the other instance's assignment and took
    # epochs on its units with `may_write` true, and its heartbeat went out over the legitimate one. Two processes took
    # the same detectors in turn, until a restart. Now a name given up is `seeking` until another is claimed, and
    # while it is the instance is fenced: `renew_slot` says no (so the stand-in renews nothing), `may_stand_in` says no,
    # `take_epoch` raises `NoSlot`, the assignment it reads is empty and no heartbeat goes out under the name. Every
    # lease step claims again, as `VmsWorker.rejoin` does for a fenced holder.
    #
    # …AND THE HOLDER TOO (the review's sixth pass). `VmsWorker` and the recorder do not come through here: they fence
    # the instance (`fence`) and take a free slot on a later pass (`rejoin`) — and that path kept the old name through
    # a claim that failed, the very thing closed here. It gives the name up by the same line now (`give_up_name`) and
    # claims by the same try (`_seek_slot`); what is fenced while `seeking` is one list, for every worker.
    def keep_slot(self, let_go) -> list[str]:
        if self.seeking is not None:
            self._seek_slot()
            return []
        try:
            mine = self.renew_slot()
        except OSError as e:
            log.warning("%s: the store did not answer for the slot (%s); still %s", self.name, e, self.name)
            return []
        except SchemaTooNew:
            # A store raised past this build: the renewal refuses before it reads the row, every step — and the row
            # lapses with the process alive and heartbeating. Once another instance has the name, this one is nobody
            # like any other whose slot was taken (`name_taken`); until then the refusal is the loop's to log, as before.
            if not self.name_taken():
                raise
            mine = False
        if mine:
            return []
        lost = list(self.epochs)
        self.give_up_name()                       # fenced from this line, whatever `let_go` does
        try:
            let_go()
        finally:
            self.release_all()
        self._seek_slot()
        return lost

    # One try at a free slot for an instance that gave its own up. True when it is somebody again. Whatever the claim
    # raised — the store did not answer, every candidate was taken under it, a token refused — the instance stays
    # nobody and tries again: `VmsWorker.rejoin` comes through here too (the review's sixth pass).
    def _seek_slot(self) -> bool:
        was = self.seeking
        try:
            self.schema_seen = check_schema(self.vars, getattr(self, "schema_seen", None))   # nobody to be on a store past this build
            self.claim_slot()
        except Exception as e:                    # noqa: BLE001
            log.warning("%s: gave slot %s up and no other could be claimed (%s): nobody, taking nothing; trying again "
                        "on the next step", self.instance, was, e)
            return False
        self.seeking = None
        log.warning("%s: gave slot %s up, its units let go; going on as %s", self.instance, was, self.name)
        return True

    def renew_leases(self) -> list[str]:
        """Returns the units whose lease was lost — fenced or expired."""
        self._loop_renewed = self.clock()         # what the stand-in measures a hung step's danger from
        return [u for u, l in self.leases.items() if not l.renew()]

    # -- the stand-in ----------------------------------------------------------------
    # THE LOOP THAT WORKS IS THE LOOP THAT RENEWS (feedback DD; the fourth review's open item). A step hung on a call
    # to the store or the engine — a pass, a pump, a recorder's call into obsd — stopped renewing too: after the
    # lease's TTL the worker's units went to a neighbour, though the process was alive and about to come back. So
    # every step of a loop marks its start and end (`guarded`), and beside the loop a thread (`start_stand_in`)
    # looks every `STAND_IN_WAKE` seconds: a step that has run longer than half of what a lease allows
    # (`stand_in_after`) gets its leases, its slot row and its place renewed for it — the slot and the place by CAS
    # and only while they still name this instance, by the same rules the loop renews them by.
    #
    #   only for a while      `STAND_IN_FOR`, from the loop's last renewal before the first step it stood in for — one
    #                         count for a run of hung steps, begun again only by a step that renewed and needed nobody
    #                         (`stand_in_once`). A step hung for ever must not hold units for ever: after that the
    #                         stand-in stops, the leases run out, and the units honestly go
    #   never a revival       a slot row another instance took, a lease fenced or let go, an instance its
    #                         subsystem fenced (`may_stand_in`): the stand-in renews none of them and decides
    #                         nothing — what a lost slot or lease MEANS is the loop's, when it comes back
    #   never in the way      the slot lock taken only if free: a loop renewing it right now needs no stand-in
    #
    # The product's `Worker.RunStandIn` is the same rule; there the stand-in renews leases and the slot row. Here it
    # renews the place (`hold`) as well — a recorder's network volume lapses as fast as its slot, and a recorder hung
    # in obsd is the case this was written for.
    STAND_IN_FOR = 300.0          # five minutes: long enough for a store or a daemon to come back, short of "for ever"
    STAND_IN_WAKE = 2.0           # how often the stand-in looks; far inside `stand_in_after`
    STAND_IN_AFTER = 0.5          # of the lease's write window (`ttl − margin`): 12.5 s of the default 25

    # How long the units may go un-renewed under a running step before the stand-in renews for it — counted from the
    # step's start or the loop's last renewal, whichever is EARLIER. From the step alone it was too late: a step may
    # start a whole renewal period after the loop renewed (a holder renews every `(ttl − margin)/3`), and half the
    # window after THAT, plus a look, is the window's end.
    def stand_in_after(self) -> float:
        return (self.lease_ttl - self.lease_margin) * self.STAND_IN_AFTER

    # Whether this instance may be stood in for at all. A subsystem that fences an instance says no once it has; and
    # an instance that gave its slot up and has no other is nobody to stand in for (`keep_slot`).
    def may_stand_in(self) -> bool:
        return self.seeking is None

    # Marks one step of the loop. Nested steps are one step: the outermost one's start is what the stand-in judges.
    @contextmanager
    def guarded(self, step: str):
        with self._step_lock:
            outer = self._step is None
            if outer:
                self._step = {"name": step, "at": self.clock(), "last": None, "said": False, "done": False}
        try:
            yield
        finally:
            if outer:
                with self._step_lock:
                    mark, self._step = self._step, None
                    # A step in which the loop renewed by itself and came back before anybody had to stand in: the loop
                    # works again, and the next hung step is counted from its own start (`stand_in_once`).
                    if mark and self._loop_renewed >= mark["at"] and self.clock() - mark["at"] <= self.stand_in_after():
                        self._stood_in_since = None
                if mark and mark["said"]:
                    log.warning("%s: step %s came back after %.0f s", self.name, step, self.clock() - mark["at"])

    # One look of the stand-in. Returns True when it renewed.
    def stand_in_once(self) -> bool:
        with self._step_lock:
            mark = self._step
        if mark is None or mark["done"]:
            return False
        now = self.clock()
        age = now - mark["at"]
        # STAND_IN_FOR is counted from the loop's own last renewal, not from this step's start (the review's fifth pass,
        # a minor): a loop that came back from one long step into another without renewing anything has made no
        # progress, and each new step gave it five more minutes.
        #
        # …AND NOT FROM A RENEWAL MADE INSIDE THE STEP THAT THEN HANGS (the review's sixth pass). The lease step renews
        # first and works after: hung there, it had renewed a moment ago by its own count, and every such step was given
        # five minutes more — six in a row held the units and the place for 1680 s (simulated). The five minutes run
        # from the renewal before the FIRST step that had to be stood in for (`_stood_in_since`), and start again only
        # after a step in which the loop renewed and needed nobody (`guarded`).
        quiet = now - min(mark["at"], self._loop_renewed)
        if quiet <= self.stand_in_after():
            return False
        since = self._stood_in_since if self._stood_in_since is not None else now - quiet
        if now - since > self.STAND_IN_FOR:
            mark["done"] = True
            log.error("%s: step %s has run %.0f s, and the loop has not renewed clear of a hung step for %.0f s; no "
                      "longer standing in for it (STAND_IN_FOR %g s): its units go", self.name, mark["name"], age,
                      now - since, self.STAND_IN_FOR)
            return False
        if not self.may_stand_in():
            return False
        if mark["last"] is not None and now - mark["last"] < max(1.0, (self.lease_ttl - self.lease_margin) / 3):
            return False                              # as often as the loop renews, not every look
        if not self._slot_lock.acquire(blocking=False):
            return False                              # the loop is renewing it this moment
        try:
            mine = self.renew_slot()
        except SchemaTooNew:
            mine = False                              # the loop fences on it when it comes back; nothing to hold
        except OSError:
            mine = True                               # silence is not "taken": the leases judge silence themselves
        finally:
            self._slot_lock.release()
        if not mine:
            mark["done"] = True
            log.error("%s: step %s has run %.0f s and slot %s is not this instance's now: not standing in",
                      self.name, mark["name"], age, self.name)
            return False
        for unit, lease in list(self.leases.items()):
            if self.leases.get(unit) is lease:        # not one the loop let go of meanwhile (and `released` closes the rest)
                lease.renew()
        self._stand_in_hold()
        mark["last"] = now
        self._stood_in_since = since
        self.stand_in_renewals += 1
        if not mark["said"]:
            mark["said"] = True
            log.warning("%s: step %s has run %.0f s; standing in for it — leases and slot renewed, for up to %g s",
                        self.name, mark["name"], age, self.STAND_IN_FOR)
        return True

    # The place, by CAS and only while the row names this instance; never let go of here — losing it is the loop's
    # to act on (`renew_hold` clears `hold`, and a recorder mounts by what `hold` says).
    #
    # And only while the subsystem says the step is worth holding the place for (`may_stand_in_hold`; the review's fifth
    # pass, a minor): a recorder's step stuck on a daemon that answers nothing writes nothing, and five minutes of a
    # network volume held for it were five minutes no box whose daemon answers could take it. A renewal it did make is
    # told (`note_hold_confirmed`), from before the store was asked — what a recorder fences its samples by.
    def _stand_in_hold(self) -> None:
        if self.hold is None or not self.may_stand_in_hold() or not self._hold_lock.acquire(blocking=False):
            return
        try:
            t0 = self.clock()
            key = self.sub.hold_key(self.hold)
            items, idx = self.vars.get(key)
            cur = read_hold(key, self.hold, items)        # one that does not parse is the loop's to mend, not the stand-in's
            if cur is not None and cur.holder == self.instance and not cur.released:
                self.vars.put(key, Slot(self.hold, self.instance, self.wall() + self.slot_ttl, False, cur.gen,
                                        self.name or "").to_items(), cas=idx)
                self.note_hold_confirmed(t0)
        except (OSError, Conflict):
            pass
        finally:
            self._hold_lock.release()

    # Whether the stand-in may renew the place for the step that hangs now. A subsystem whose place is written through
    # an engine says no while that engine is silent (`RecWorker.may_stand_in_hold`).
    def may_stand_in_hold(self) -> bool:
        return True

    # The place confirmed by the store at `at` (the clock, before it was asked). Nothing here; a recorder fences its
    # samples by it (`RecWorker.note_hold_confirmed`).
    def note_hold_confirmed(self, at: float) -> None:
        pass

    # Starts the stand-in beside a loop. Returns the event that ends it: the loop sets it when it ends. Its own
    # event, not the loop's `stop` — the stand-in must outlive nothing and wait on nothing the loop's caller owns.
    def start_stand_in(self) -> threading.Event:
        done = threading.Event()

        def look():
            while not done.wait(self.STAND_IN_WAKE):
                try:
                    self.stand_in_once()
                except Exception:                     # noqa: BLE001 — the stand-in must not die of one bad look
                    log.exception("%s: the stand-in failed; will look again", self.name)

        threading.Thread(target=look, name=f"{self.name}-stand-in", daemon=True).start()
        return done

    # -- the early pass: a hint, never a channel (`longpoll.py`) ------------------------------------------
    # A loop finds its work by looking, every `poll` seconds. A worker whose work begins with a line in the event
    # log may ask the resources to tell it when such a line is written — a request each resource HOLDS and answers
    # then (`GET /events/wait`). The answer says "look now" and nothing else: the pass that follows is the
    # ordinary pass, reading what it would have read at the end of its wait. An answer that never comes costs the
    # wait it would have saved; a flood of them is one early pass per `WAKE_GAP`.
    #
    #   wants()         what this worker watches: `(subsystem, kind, unit)`, a unit of "" for any. Its subsystem's to say
    #   poll_events()   the process asks for the long poll, before the loop: `resources()` is `{server: url}`,
    #                   the resources this worker asks anyway. `LONG_POLL=0`: nothing is asked, nothing changes
    #   wait_next()     the loop's wait between passes: `stop.wait(poll)`, cut short by an answer
    def wants(self) -> list[tuple[str, str]]:
        return []

    def poll_events(self, resources, env=None) -> LongPoll | None:
        if self.long_poll is None and long_poll_enabled(os.environ if env is None else env):
            self.wake = Wake()
            self.long_poll = LongPoll(self.wake, resources, self.wants, client=self.instance)   # one held request per instance
        return self.long_poll

    def wait_next(self, poll: float, stop) -> bool:
        """The loop's wait between passes. True when it was cut short — the pass that follows began early."""
        if self.wake is None:
            stop.wait(poll)
            return False
        if self.long_poll is not None:
            self.long_poll.sync()                 # a held request at every resource asked now: once a pass, never raises
        return self.wake.wait_next(poll, stop)

    # The loop ended: no request is asked again. One that is held ends by itself, at its answer.
    def stop_polling(self) -> None:
        if self.long_poll is not None:
            self.long_poll.close()

    # Sum of `conflicts` over all leases; goes into the heartbeat.
    def conflicts(self) -> int:
        return sum(l.conflicts for l in self.leases.values())

    # Writes `Heartbeat(name, wall(), status, extra)` to `<name>/<name>/heartbeat` in the object store. The
    # VMS passes `server`, `labels`, `capacity`, `headroom`, `conflicts`, `started`, `previous_hb`, etc. as
    # `extra`.
    def heartbeat(self, status: list[dict], **extra) -> None:
        # `schema` and `build` are on EVERY heartbeat, from here, so no subsystem has to remember them:
        # the first says what layout this process understands (what `set_schema` is checked against), the
        # second is for the person looking at a half-upgraded cluster.
        extra.setdefault("schema", SCHEMA)
        extra.setdefault("build", BUILD)
        if self.stand_in_renewals:
            extra.setdefault("stand_in_renewals", self.stand_in_renewals)     # a step hung, and somebody held its units
        # Rows of this subsystem this process could not read, by table (`rows.Table`): `slots_garbled` (`read_slot`),
        # `assignments_garbled` (its own assignment), `holds_garbled` (`read_hold`), and those of a subsystem's own
        # tables — a recorder's `volumes_garbled`, `keeps_garbled`.
        for name, n in garbled_counts(self.sub.name).items():
            extra.setdefault(name, n)
        if self.seeking is not None:
            return                                # the name is another instance's, and so is what is said under it (`keep_slot`)
        self.objects.put(self.sub.heartbeat_key(self.name),
                         Heartbeat(self.name, self.wall(), status, extra).to_bytes())

    # A UNIT'S OWN ROW THAT DOES NOT PARSE (the sixth pass, the follow-up). The controller has passed such a row by
    # since the second pass (`SpecController.units`); the workers read the rows of the units they were assigned in
    # one loop, bare, and a row garbled AFTER it was placed raised out of the pass: nothing after it started, nothing
    # taken away stopped, every pass. Every worker's loop catches it at its unit and comes here: said once per row
    # until it parses again, and the words for the unit's status. What the unit does meanwhile is the subsystem's —
    # what runs under the row read last keeps running (not knowing is not "no"), what never started does not start.
    def row_garbled(self, unit, e) -> str:
        said = self.__dict__.setdefault("_rows_garbled_said", set())
        if str(unit) not in said:
            said.add(str(unit))
            log.error("%s: the row of %s does not parse (%s); passed by until it does", self.name, unit, e)
        return f"its row does not parse: {e}"

    def row_parsed(self, unit) -> None:
        self.__dict__.get("_rows_garbled_said", set()).discard(str(unit))

    # what a subsystem implements
    # Abstract: what a subsystem implements (the VMS's is М9 Lesson 6's loop).
    def reconcile_once(self, now: float) -> list:
        raise NotImplementedError
