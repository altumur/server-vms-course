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

import contextlib
import json
import logging
import os
import re
import socket
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field

from . import runtime
from .blobs import BLOBS, is_digest
from .epoch import Lease, next_epoch
from .objects import ObjectStore
from .doors import LIST_SEPARATOR, numeric
from .events import ALARM
from .journal import Journal
from .rows import PARSE_ERRORS, Table, finite, garbled_counts, number
from .longpoll import LongPoll, Wake, enabled as long_poll_enabled
from .variables import TORN, Conflict, Garbled, Variables, cas_pause

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
CONTENDERS = "contenders"  # `<name>/contenders/<slot>/<box>`: a process that wants a name another instance holds (`Worker._contend`)
USED = "used"              # `<name>/used/<place>`: a place this subsystem's workers have opened, and where (`Subsystem.used_key`)


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


class NoOffer(NoSlot):
    """A spare found no offer of its label set to take (`Worker.claim_slot(spare_for=)`): it waits, holding nothing."""


class NotReadThisPass(RuntimeError):
    """The unit is not in the assignment this worker read last, or that read did not answer: no new epoch for it."""


# `Worker.assigned_now` before the first read: a worker driven by hand (the platform's lessons take an epoch on a unit
# they name) has no list to be held to. Every subsystem's pass reads its assignment before it takes anything.
NEVER_READ = object()


# -- one name, two processes (the owner's decision of 4 Oct; the product's r24-names, `names.go`) ---------------------
#
# A process started under a name — its unit's `WORKER_NAME`, a `<ROLE>_NAME`, `SLOT_INDEX` (`Worker.given`) — IS that
# name, and is left without it two ways:
#
#   on its own box   the unit started it again while it still lived, and the new process took the name at its start
#                    (the restart after kill -9: the unit is the authority on which process is the current one). The old
#                    one used to rejoin under whatever was free (`w-2`) — a second worker on the server that its unit
#                    knew nothing about. Now it is NOBODY (`Worker._seek_slot`): it holds nothing, says
#                    `worker.name_taken` once an episode, and on each lease step asks for its own name again — taken
#                    only when free or lapsed, never from a live holder (two live processes of one name on one box
#                    would take it from each other for ever), never another number. Got back: `worker.name_back`.
#   on another box   a live process holds it — two machines installed with one hostname compute one `w-%l-1`. It is not
#                    taken (`NameOnAnotherBox`): the process refuses with words, exits, and its unit restarts it.
#
# Either way it leaves its mark, `<sub>/contenders/<name>/<box>` (`Worker._contend`): who wants the name, from which box,
# who holds it, since when — written over at each refusal and on each pass of a nobody, never accumulated; a mark not
# written for `CONTENDER_FRESH` is a claimant that stopped asking. `/servers` shows the fresh ones on the holder's row
# (`name_conflict`), the controller says a claimant of ANOTHER box once an episode — `worker.name_conflict`, an alarm
# (`Controller.say_name_conflicts`) — and `<p>_name_conflicts` counts the names with any fresh mark. A process that took
# whatever was free rejoins as before.
CONTENDER_FRESH = 300.0        # how long a mark is read after it was last written
CONTEND_EVERY = 10.0           # how often a nobody writes its mark again: its pulse, while the heartbeat is the holder's
REFUSED, NAMELESS = "refused", "nameless"    # a claimant that exits and is restarted; one that runs holding nothing


class NameOnAnotherBox(RuntimeError):
    """The name this process was started under is held by a live process of ANOTHER box (`Worker._may_take_by_name`).
    Its text is the whole message the process exits with."""

    def __init__(self, slot: str, holder: str, box: str, hostname: str, here: str, name_env: str = "",
                 held: bool = False):
        self.slot, self.holder, self.box, self.hostname, self.here = slot, holder, box, hostname, here
        names = "WORKER_NAME" + (f" (or {name_env})" if name_env and name_env != "WORKER_NAME" else "")
        # A holder whose name says no box (an `INSTANCE_ID`), and one that stopped renewing but is not judged gone (the
        # review's thirteenth pass, blocker 3): the same refusal, in its own words.
        where = f"on another machine (box {box}, instance {holder})" if box else \
            f"by instance {holder}, whose name does not say which machine it runs on"
        state = ("stopped renewing it, and its controller has not judged it gone: its process may still run and write "
                 "(hung, or cut off from the store) — the name is taken once the controller gives it, or once its "
                 "process is known to be dead" if held else "is live")
        super().__init__(
            f"{slot} is held {where}, which {state}. Two machines given one name usually share the hostname "
            f"{hostname!r} (the units name their processes from it, w-%l-1): give this machine another hostname, or "
            f"set {names} in its unit to a name no other machine uses. This machine (box {here}) leaves the name "
            f"alone: taking it would make two processes of one name")


class _NameTaken(Exception):
    """The name asked for again is held by a live instance — or a lapsed one whose process runs, hung — and is not taken
    from it (`Worker._claim_slot(steal=False)`)."""

    def __init__(self, slot: str, holder: str, until: float):
        super().__init__(f"slot {slot} is held by {holder or '?'}: a live holder keeps its name")
        self.slot, self.holder, self.until = slot, holder, until


def _read_contender(objects, key: str) -> dict | None:
    try:
        row = json.loads(objects.get(key) or b"null")
    except (*PARSE_ERRORS, OSError):
        return None
    if not isinstance(row, dict) or not str(row.get("name") or ""):
        return None
    try:
        row["at"], row["since"] = finite(row.get("at")), finite(row.get("since"))
    except PARSE_ERRORS:
        return None
    return row


def contenders(objects, sub: "Subsystem", now: float) -> dict[str, list[dict]]:
    """The fresh marks of a subsystem, by name, ordered by box: the processes that want a name another instance holds
    and asked within `CONTENDER_FRESH` of now. A mark that does not read is skipped; a store that does not answer, none."""
    out: dict[str, list[dict]] = {}
    try:
        keys = objects.list(sub.contenders_prefix())
    except OSError:
        return out
    for key in keys:
        row = _read_contender(objects, key)
        if row is not None and now - row["at"] <= CONTENDER_FRESH:
            out.setdefault(str(row["name"]), []).append(row)
    for rows in out.values():
        rows.sort(key=lambda r: str(r.get("box", "")))
    return out


def name_conflict(holder: str, rows: list[dict], now: float) -> dict:
    """What `/servers` says of a name contended for: who holds it, and who else wants it, from where, since when."""
    from . import runtime
    return {"holder": holder, "holder_box": runtime.box_of(holder) or "",
            "contenders": [{"state": r.get("state"), "box": r.get("box"), "hostname": r.get("hostname"),
                            "server": r.get("server"), "instance": r.get("instance"), "holder_seen": r.get("holder"),
                            "since": r["since"], "for_s": round(max(0.0, now - r["since"])), "at": r["at"]}
                           for r in rows]}


# Where a worker registers with its server's resource (`Worker.present`, `resource.workers_here`): a directory in
# the resource's tree — a dot, so the tree's walks do not take it for a subsystem — one lock file per process.
PRESENCE = ".workers"


def presence_name(instance: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(instance))[:200]


# How long a slot stays "alive" past its `until`, and a worker past its last heartbeat: the platform's usual "lost"
# (`Controller.slot_fate`). The slot outlives the lease (45 s against `ttl − margin` = 25); this is the margin on top.
SLOT_LOST_AFTER = 45.0

# How long a hung worker — or one nobody can judge (`unsure`) — keeps its units past its slot's `until` before they move
# anyway (`Controller.hung_move_after`).
HUNG_MOVE_AFTER = 900.0
# The fates of a lapsed slot whose units move now (`Controller.slot_fate`) — what `leaving` and `gone_servers` read.
MOVED_FATES = ("move", "hung_moved", "unsure_moved")

# A slot's term as its judge counts it: from when it saw the row renewed (`Controller.slot_fate`; the review's thirteenth
# pass, blocker 4). A renewal dates its slot one term ahead by its holder's clock (`slot_ttl`, 45 s); the `until` it
# writes is that clock's, and is read for what a page shows — `until` an hour ahead held a dead server's cameras for an
# hour (the twelfth pass, major 17), one 50 s behind gave a live worker's away.
SLOT_TERM = 45.0
# The fates under which a lapsed slot's NAME may be taken by another process (`Worker._held`): its units move with it
# (`MOVED_FATES`), or its server does not run it any more (`release`) — and `wait`, past `hung_move_after`
# (`Controller.name_given`).
NAME_FATES = MOVED_FATES + ("release",)

# How often a resource writes, in the store, that it is there (`Resource.say_door`, `at` on its door row): the second
# opinion on its silence (`Controller.resource_state`), read where its heartbeat cannot be read fresh.
ALIVE_EVERY = 15.0

# How long an offer a spare took counts as a worker on its way while that worker has not been heard
# (`SpecController.offer_spares`): the product's 90 s — a start, its first pass and its first heartbeat, with room.
OFFER_GRACE = 90.0


def label_set(labels) -> str:
    """A set of labels as one string, the way offers and `SPARE_FOR` say it: sorted, comma-joined, "" the empty set.
    Takes the comma-joined string or any iterable of labels."""
    items = labels.split(",") if isinstance(labels, str) else labels
    return ",".join(sorted({str(l).strip() for l in items if str(l).strip()}))


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
    except PARSE_ERRORS as e:                     # `version: Infinity` too: `int(inf)` is an `OverflowError` (the tenth round's sweep)
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
#
# A schema that does not read is NOT KNOWN, and not a heartbeat skipped (the review's tenth round, `/schema`): `1e999`
# (`int(inf)`) skipped the process, and a process `/schema` does not list is not behind any version — the one raise
# that locks a live process out. It is listed with `schema: null`, `can_raise_to` stays where the store is, and
# `set_schema` refuses while it runs. A `build` that is not a string (a list: unhashable, and `/schema` sorts a set of
# them) is `"?"`, as an absent one is.
def builds(objects, now: float, lost_after: float = 45.0, eyes: "Eyes | None" = None) -> dict[str, dict]:
    def parse(raw: bytes) -> dict:                    # a worker's or a resource's: the three fields this reads, checked
        d = dict(json.loads(raw))
        try:
            schema = int(d.get("schema", SCHEMA))
        except PARSE_ERRORS:
            schema = None
        build = d.get("build", "?")
        return {"schema": schema, "build": build if isinstance(build, str) else "?", "ts": float(d.get("ts", 0))}

    out = {}
    for key in objects.list(""):
        if not is_heartbeat_key(key):
            continue
        raw = objects.get(key)
        d = parse_heartbeat(key, raw, parse) if raw else None
        if d is not None:
            # Live by the judge's eyes where it has them — changed within `lost_after` of its clock (the review's
            # thirteenth pass, blocker 4): `set_schema` refused nothing while a live build's clock ran 50 s behind
            sub = key.split("/", 1)[0]
            live = (eyes.fresh(key, d["ts"], lost_after, d["ts"], sub) if eyes is not None
                    else is_live(sub, d["ts"], now, lost_after))
            out[heartbeat_owner(key)] = {**d, "live": live}
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


#
# …AND WHAT IT IS CALLED BY IS A NAME (the review's tenth pass, major). `worker` and `server` went on as they stood: a
# heartbeat saying `"server": ["srv-x"]` parsed, and every reader that keys or sorts by it raised — `/servers`,
# `/unplaceable`, `/drain`, `/metrics` of the console, a resource's `restore` and mirror, and the controller's
# `ensure_reach`, `redistribute`, `ensure_home` (a new unit not placed, a dead recorder's units not moved); a `5` among
# strings raised in every `sorted`. A worker's or a resource's `worker` and `server` are non-empty strings, or the
# heartbeat does not parse: that heartbeat's trouble, skipped and counted like any other.
NAMES = ("worker", "server")


def _named(hb) -> None:
    said = {"worker": hb.worker, **hb.extra} if isinstance(hb, Heartbeat) else hb if isinstance(hb, dict) else {}
    for field in NAMES:
        if field in said and not (isinstance(said[field], str) and said[field]):
            raise TypeError(f"`{field}` is a name, not {said[field]!r:.40}")


def parse_heartbeat(key: str, raw: bytes, parse=None):
    """The object parsed, or None — skipped, counted, and logged once."""
    try:
        hb = (parse or Heartbeat.from_bytes)(raw)
        # …and its status is a list of OBJECTS (the review's seventh pass, the walk over every reader): an entry that
        # is a word parsed, and raised `AttributeError` in every reader that asks an entry `.get` — `holder_of`, the
        # read model, the running gauge — each a loop over every worker.
        if isinstance(hb, Heartbeat) and not all(isinstance(s, dict) for s in hb.status):
            raise TypeError("a status entry is not an object")
        _named(hb)
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


# -- FRESHNESS BY CHANGE, ON THE JUDGE'S CLOCK (the review's thirteenth pass, blocker 4; the owner's decision of 4 Oct) --
# `is_live` compares two machines' clocks, and `FUTURE_TOLERANCE` is all the slack it has. Every "is it still there?"
# that moves something, gives a name away or lets a server go was asked so: a resource's `ts`, its door row's `at`, a
# slot's `until`, a worker's `ts`. A server whose clock ran 6…30 s ahead or 50 s behind had a live worker's cameras
# carried off at 10 s, a hung one's given a second writer at 10 s instead of 900, and a live server ahead by 30 s was
# decommissioned (`n3`, `n4`, `n6`, `n7`, reproduced by runs). The judge now asks whether what it reads has CHANGED, and
# how long it has stood still by ITS OWN clock: a heartbeat's `ts` and a door row's `at` are tokens that change with
# every write — never times — and a slot's term runs from when the judge saw it renewed. A thing the judge has never
# seen before is taken as just changed: a controller started a minute ago waits a window out before it calls anything
# silent, rather than believe a writer's clock. The writer's time is read for two things only: the skew, when a new
# token is first seen (`SKEW_MAX`/`SKEW_MIN` on `/metrics`, `clock.skew` in the journal past `SKEW_ALARM`), and what a
# page shows. Every server should still run NTP; nothing here depends on it.
#
# Judged by a monotonic clock in a process (a wall clock stepped by NTP would age everything at once); a test that
# drives its own wall drives this too (`judge_clock`).
SKEW_ALARM = (FUTURE_TOLERANCE, 15.0)    # ahead, behind: past either a writer's clock is said (`Controller.say_skews`)


def judge_clock(wall):
    """The clock freshness is measured by: monotonic, unless the caller drives its own wall (a test)."""
    return time.monotonic if wall is time.time else wall


class Eyes:
    """When this judge first saw each thing as it is now, by its own clock."""

    def __init__(self, clock, wall=time.time):
        self.clock, self.wall = clock, wall
        self.born = clock()                       # what it has watched since: a judge started a minute ago saw a minute
        self._seen: dict[str, tuple[object, float]] = {}
        self._lock = threading.Lock()
        # The writer's clock against this one, as last seen when a token changed: `{key: ts − wall}`. A new token is
        # read up to a beat and a pass after it was written, so the number is a little behind; ahead is ahead.
        self.skews: dict[str, float] = {}

    def since(self, key: str, token, ts=None, sub: str | None = None) -> float:
        """When `key` was first seen holding `token`, by this judge's clock. `ts` — the writer's time — and `sub`: for
        the skew only, counted where the token is new."""
        now = self.clock()
        with self._lock:
            prev = self._seen.get(key)
            if prev is not None and prev[0] == token:
                return prev[1]
            self._seen[key] = (token, now)
        # …and only a CHANGE seen tells of the writer's clock: the first sight of a key may be a token written an hour
        # ago by a process long dead, and its `ts` says nothing of any clock.
        if prev is not None and ts is not None and sub is not None:
            with contextlib.suppress(TypeError, ValueError, OverflowError):
                skew = float(ts) - self.wall()
                if skew == skew:                                  # a NaN says nothing of a clock
                    self.skews[key] = skew
                    if skew > SKEW_MAX.get(sub, 0.0):
                        SKEW_MAX[sub] = skew
                    if skew < SKEW_MIN.get(sub, 0.0):
                        SKEW_MIN[sub] = skew
        return now

    def age(self, key: str, token, ts=None, sub: str | None = None) -> float:
        """How long `key` has stood still at `token`, by this judge's clock."""
        return max(0.0, self.clock() - self.since(key, token, ts, sub))

    def fresh(self, key: str, token, within: float, ts=None, sub: str | None = None) -> bool:
        """`key` changed within `within` seconds of this judge's clock."""
        return self.age(key, token, ts, sub) <= within

    def wall_of(self, t: float) -> float:
        """A moment of this judge's clock as its wall clock reads it — for a page."""
        return self.wall() - (self.clock() - t)

    def watched(self) -> float:
        """How long this judge has been watching."""
        return max(0.0, self.clock() - self.born)


# The one row that says which server is going away for a while. It is the platform's, not a subsystem's —
# a machine carries several — and it holds ONE name: a rolling upgrade is one server at a time.
DRAIN_KEY = "platform/drain"

# `platform/decommission/<server>`: the operator's word that a machine is gone for good (`Controller.decommission`).
# A directory, not one row like the drain: machines are decommissioned one by one and stay so.
DECOMMISSION = "platform/decommission/"


class DecommissionRefused(Exception):
    """A server decommissioned while it still answers — its resource, a worker on it, or a slot renewed there."""


class ServerDecommissioned(RuntimeError):
    """A process on a decommissioned server asked for a slot: refused, by name, until the operator brings it back."""


# Every server decommissioned: `{server: {by, at, why}}`.
def decommissioned(vars_) -> dict[str, dict]:
    out = {}
    for path in vars_.list(DECOMMISSION):
        items, _ = stored(vars_, path, DECOMMISSIONS)
        if items:                                       # one the store cannot read is a decommission still: the operator's
            out[path[len(DECOMMISSION):]] = {"unread": str(items.error)} if isinstance(items, Unread) else dict(items)
    return out


class DrainRefused(Exception):
    """A second server asked to drain while one already is."""


# The server being drained, or "". Read on every placement pass by every subsystem, so it is one small
# row and not a directory: the answer must cost one `get`.
def draining(vars_) -> str:
    return DRAINS.read(DRAIN_KEY, lambda: str((vars_.get(DRAIN_KEY)[0] or {}).get("server", "")), "")


# A ROW THE STORE CANNOT READ, WHERE A ROUTE OR A PASS READS IT (the eleventh review, a minor). `Variables.get` raises
# `Garbled` for a row it holds and cannot read — the course's file store: a torn file, items that are not a map — and
# read bare, one such row took `/servers`, `/unplaceable`, `/drain` and `/where` down whole, and every
# controller pass with them: the drain, a slot, a hold, a worker's assignment, a placement, a decommission. Those are
# read through `stored` (or inside their table's read, as the drain): the row's error in its items' place (`Unread`),
# which each of them reads as that row not parsing — counted in its table, logged once — and the rest go on. A write
# replaces such a row whole (`Controller.write`, under `TORN`). A row read bare anywhere else still raises: a
# `ValueError`, that row's (`rows.PARSE_ERRORS`).
class Unread:
    """The items of a row the store holds and cannot read: its error. True, as a row that is there."""

    def __init__(self, error: Exception):
        self.error = error


def stored(vars_, key: str, table: Table) -> tuple:
    """`vars_.get(key)` — or `(Unread, TORN)` for a row the store cannot read: counted in `table`, logged once."""
    try:
        return vars_.get(key)
    except Garbled as e:
        table.garbled(key, e)
        return Unread(e), TORN


def _items(items):
    """The items to parse — or, for a row the store could not read, its error raised where the row is parsed."""
    if isinstance(items, Unread):
        raise items.error
    return items


DRAINS = Table("drain", "read as no server draining, until it is written again (POST or DELETE /drain)")
DECOMMISSIONS = Table("decommission", "read as a decommission still, until it is written again or withdrawn")


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

    # `<name>/decommissioned/<server> {asked_at, at, slots, units, holds}` — the controller's mark that a server's
    # decommission (`platform/decommission/<server>`, the console's) was carried out in this subsystem: which slots it
    # released, which units moved, which places stay held (`Controller.apply_decommissions`).
    def decommissioned_key(self, server: str) -> str:
        return f"{self.name}/decommissioned/{server}"

    # `<name>/servers/<server>` — what a SERVER reaches, as the administrator says it from the console (`{labels}`;
    # feedback DQ). Where there is none, the labels its workers report (the node's `LABELS`) answer, as they always did.
    def server_key(self, server: str) -> str:
        return f"{self.name}/servers/{server}"

    def servers_prefix(self) -> str:
        return f"{self.name}/servers/"

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

    # `<name>/contenders/<slot>/<box>` — a process that wants a name another instance holds, and from which box (the
    # owner's decision of 4 Oct, the product's r24-names; `Worker._contend`): what `/servers` shows as `name_conflict`
    # and the controller says as `worker.name_conflict`. An OBJECT, like a heartbeat: the claimant's own word, written
    # over at each refusal and each pass of a nobody, never a decision anybody else waits on.
    def contender_key(self, slot: str, box: str) -> str:
        return f"{self.name}/{CONTENDERS}/{slot}/{str(box).replace('/', '-')}"

    def contenders_prefix(self) -> str:
        return f"{self.name}/{CONTENDERS}/"

    # `<name>/used/<place>` — a place this subsystem's workers have OPENED, and at which address `{url, at, by,
    # instance, server}`: what "already in use" means when the place is not there any more (`RecWorker._may_format`;
    # the owner's decision of 4 Oct). An object, written once per address by whoever opened it first.
    def used_key(self, place: str) -> str:
        return f"{self.name}/{USED}/{place}"

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
        """The workers write their own heartbeats, their claims to a name another instance holds, and the places
        they opened."""
        return [f"{self.name}/{HEARTBEATS}/*", f"{self.name}/{CONTENDERS}/*", f"{self.name}/{USED}/*"]

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


# THE CONTROLLER'S LIMIT, AS IT SAID IT (the product's alignment of the owner's decision on hung workers). A spare asks
# whether a lapsed slot's worker is hung before it takes the name (`Worker._hung`), and the console says so on `/servers`
# (`Mount._judged`) — each through `Controller.slot_fate`, with `HUNG_MOVE_AFTER` as compiled in, while the controller
# read its own from its environment: told an hour, it held a hung worker's cameras back and a spare took the name — and
# the cameras — at fifteen minutes, a second writer; told a minute, it moved them and the spare still waited. The
# controller says its limit in its pass report (`<sub>/controller/pass`, `hung_move_after` — the one object it writes
# beside the shards, `acl_objects_controller`; anyone of the subsystem reads it), and the others judge by that: one limit,
# one rule, one verdict. No report yet, or a word in it: the default, as the controller's own.
def published_hung_limit(objects, sub: "Subsystem") -> float:
    """How long a hung worker keeps its units, as the controller of `sub` said it in its last pass report."""
    key = f"{sub.name}/{CONTROLLER_PASS}"
    try:
        raw = objects.get(key)
        rep = json.loads(raw) if raw else {}
    except (*PARSE_ERRORS, OSError):
        rep = {}
    said = rep.get("hung_move_after") if isinstance(rep, dict) else None
    return number(f"{key}#hung_move_after", said, float, HUNG_MOVE_AFTER)


# …AND ITS VERDICT ON THE NAMES (the review's thirteenth pass, blocker 4): the slots whose name another process may take
# now, each by the revision of the row the controller judged (`Controller.names_given`). The controller has watched the
# rows change for as long as it has run; a process looking for a name has just started, has seen nothing change, and
# would have to believe the holder's clock to call its slot lapsed. A name is taken only where this says so, at the very
# revision read — a holder that renewed since is a revision past it. No report, a store that does not answer, a field
# that does not read: no name is given (`Worker._held`).
def published_names(objects, sub: "Subsystem", field: str = "names_given") -> dict | None:
    """`{worker: rev}` as the controller of `sub` said it in its last pass report — None when it cannot be read.
    `field="fates"`: its verdict on every slot that stopped renewing (`Controller.fates_said`)."""
    key = f"{sub.name}/{CONTROLLER_PASS}"
    try:
        raw = objects.get(key)
        rep = json.loads(raw) if raw else {}
    except (*PARSE_ERRORS, OSError):
        return None
    said = rep.get(field) if isinstance(rep, dict) else None
    return said if isinstance(said, dict) else None


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
    #
    # A NAME WITH THE SEPARATOR IN IT IS NOT WRITTEN INTO THE LIST (the review's ninth pass, the product team's sibling B).
    # Joined, `1,9` read back as `1` and `9`: its worker started `9` — another unit, or nothing — and never `1,9`, and no
    # reader can tell the two apart afterwards. `create` refuses such a name now (`doors.unnamable`, `unit`); a unit
    # stored under one before is left out of every assignment — unplaced, not split — counted and named once
    # (`UNLISTED`), and logged. So whatever reads `units` back reads only whole names.
    def to_items(self, key: str = "") -> dict:
        for u in self.units:
            if LIST_SEPARATOR in str(u):
                UNLISTED.garbled(f"{key or self.worker}#{u}", f"{LIST_SEPARATOR!r} in its name")
        return {"units": LIST_SEPARATOR.join(u for u in self.units if LIST_SEPARATOR not in str(u)), "rev": self.rev}

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

    # The inverse; everything that is not `worker`/`ts`/`status` lands in `extra` — and a checksum of the bytes read,
    # for whoever judges by change (`token`).
    @classmethod
    def from_bytes(cls, raw: bytes) -> "Heartbeat":
        import zlib
        d = json.loads(raw)
        extra = {k: v for k, v in d.items() if k not in ("worker", "ts", "status")}
        hb = cls(d["worker"], float(d["ts"]), list(d.get("status", [])), extra)
        hb.crc = zlib.crc32(raw)
        return hb

    # What a judge compares to tell that a heartbeat CHANGED (`Eyes`; the review's thirteenth pass, blocker 4): its `ts`
    # and its bytes — a heartbeat written again under the same `ts` (a clock that did not move) is still a new one.
    @property
    def token(self) -> tuple:
        return self.ts, self.__dict__.get("crc")


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
    # AN OFFER (`SpecController.offer_spares`): a slot row nobody holds, written by the controller for a worker it is
    # short of — `offer` the label set a spare must be for (`SPARE_FOR`; "" the empty set), None: not an offer.
    # `offered_at` when it was written; `taken_at` when a spare took it (`Worker._claim_offer`). A taken offer keeps
    # the three through its renewals: the controller counts it as a worker on its way until that worker is heard,
    # for `OFFER_GRACE`.
    offer: str | None = None
    offered_at: float = 0.0
    taken_at: float = 0.0
    # THE SERVER ITS HOLDER RUNS ON, in the store (the review's twelfth pass, blocker 5; the owner's decision of 4 Oct).
    # Where a worker runs was said in its heartbeat alone — an object, and in М11 a file on that very server: with the
    # server gone, a controller started after it had nothing to read, "never said which server", and the server's
    # cameras waited for ever. The holder writes it into every renewal of its name (`Worker.server`), and the controller
    # reads it where the heartbeat is gone (`slot_fate`). "" — not said (a worker of no server, an older build).
    server: str = ""

    # Row conversion; `released` is stored as `"true"`/`"false"`. A missing row is `Slot(name)` — released,
    # no holder.
    def to_items(self) -> dict:
        return {"holder": self.holder, "until": self.until, "released": "true" if self.released else "false", "gen": self.gen,
                **({"by": self.by} if self.by else {}),
                **({"offer": self.offer, "offered_at": self.offered_at, "taken_at": self.taken_at}
                   if self.offer is not None else {}),
                **({"server": self.server} if self.server else {})}

    @classmethod
    def from_items(cls, name: str, items: dict | None) -> "Slot":
        if not items:
            return cls(name)
        # `until` through `finite` (the review's eleventh pass): `"Infinity"` read as a lease that never ends, and
        # `int(until - now)` in the words about it raised `OverflowError` past the `ValueError` its callers caught —
        # `/servers` answered nothing and the controller's pass stopped at its first step. Not finite: the row does not
        # parse, and is that slot's trouble alone.
        offer = str(items["offer"]) if "offer" in items else None
        return cls(name, items.get("holder", ""), finite(items.get("until", 0)), items.get("released") == "true",
                   int(items.get("gen", 0)), str(items.get("by", "")), offer,
                   finite(items.get("offered_at", 0)) if offer is not None else 0.0,
                   finite(items.get("taken_at", 0)) if offer is not None else 0.0, str(items.get("server", "") or ""))

    # An offer nobody has taken yet: what only a spare of its label set may take.
    def offered(self) -> bool:
        return self.offer is not None and self.holder == "" and not self.released

    # Held, not released, and past `until`: the holder went silent — a crash.
    def lapsed(self, now: float) -> bool:
        return not self.released and self.holder != "" and now > self.until

    # Released, or never held, or past `until`. (A lapsed slot is claimable; a released one is too.) Never an offer
    # nobody has taken: that is a spare's (`Worker._claim_offer`), and an ordinary process makes a slot of its own.
    def claimable(self, now: float) -> bool:
        return not self.offered() and (self.released or self.holder == "" or now > self.until)


# The integer after the last `-` in a slot name (`w-3` → 3), 0 if not numeric. Used to order free slots and
# to pick the next unused number.
def slot_number(name: str) -> int:
    tail = name.rsplit("-", 1)[-1]
    n = numeric(tail)                                   # not `isdigit` + `int`: `w-²` raised (the ninth pass's sibling)
    return 0 if n is None else n


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
    return SLOTS.read(key, lambda: Slot.from_items(name, _items(items)))


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
# A unit whose name holds the list's separator: written into no assignment (`Assignment.to_items`; the ninth pass).
UNLISTED = Table("unlisted", "it is assigned to nobody — the list would split it; create it again under a name without "
                             "a comma", "unit in an assignment")


def read_assignment(key: str, worker: str, items) -> "Assignment":
    """The row parsed — or, when its `rev` does not parse, its units with `rev 0`: counted, and logged once."""
    if isinstance(items, Unread):                       # a row the store cannot read names no unit anyone can tell
        return ASSIGNMENTS.read(key, lambda: _items(items), Assignment(worker, []))
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
    return HOLDS.read(key, lambda: Slot.from_items(place, _items(items)))


# -- one pass, one read of each key (the scaling pass after the eighth review) ----------------------------------------
# A controller's pass asks a dozen questions per unit — its row, its placement, which server a worker is on, whether
# that server's resource answers, who is leaving — and every question was a read of the store, asked again for the
# next unit. A thousand cameras on twenty workers cost one idle pass some 64 000 reads (`tests/test_read_budget.py`
# counts them): the snapshot alone read every heartbeat again for every camera, and `ensure_home` every recorder's.
# Within one pass an answer cannot be more than a pass old anyway; so inside `one_pass` the store is asked ONCE per key
# and per listing, and the answer is kept until the pass ends — never longer: nothing survives between passes, and
# the process can still be killed anywhere.
#
# Writes go to the store as they did, and a write FORGETS what it touched — the key, and every listing it could be in —
# so the pass reads back what it wrote, not what it had read before. A write that fails forgets too: a CAS that lost
# is retried by `Controller.write` against the store, not against the copy that lost.
class _PassStore:
    """One store's reads for one pass: each `get` and `list` asked once; a write forgets what it touched."""

    def __init__(self, real):
        self.real, self._got, self._listed, self._memo = real, {}, {}, {}

    def get(self, key):
        if key not in self._got:
            self._got[key] = self.real.get(key)
        got = self._got[key]
        if isinstance(got, tuple) and got and isinstance(got[0], dict):
            return dict(got[0]), got[1]               # Variables' items are a copy, as the store's own are
        return got

    def list(self, prefix, *a, **kw):
        if a or kw:
            return self.real.list(prefix, *a, **kw)
        if prefix not in self._listed:
            self._listed[prefix] = list(self.real.list(prefix))
        return list(self._listed[prefix])

    # What a pass derives from one prefix — every heartbeat under it parsed, the rows grouped by a field — kept like a
    # read, and forgotten like one: by a write to anything under the prefix.
    def memo(self, prefix: str, read, name: str = ""):
        if (prefix, name) not in self._memo:
            self._memo[(prefix, name)] = read()
        return self._memo[(prefix, name)]

    def _forget(self, key: str) -> None:
        self._got.pop(key, None)
        for p in [p for p in self._listed if key.startswith(p)]:
            del self._listed[p]
        for p in [p for p in self._memo if key.startswith(p[0])]:
            del self._memo[p]

    def _wrote(self, call, key, *a, **kw):
        try:
            return call(key, *a, **kw)
        finally:
            self._forget(key)

    def put(self, key, *a, **kw):
        return self._wrote(self.real.put, key, *a, **kw)

    def delete(self, key, *a, **kw):
        return self._wrote(self.real.delete, key, *a, **kw)

    def put_durable(self, key, data):
        return self._wrote(getattr(self.real, "put_durable", self.real.put), key, data)

    def put_new(self, key, data):
        return self._wrote(self.real.put_new, key, data)

    def __getattr__(self, name):
        return getattr(self.real, name)


@contextmanager
def one_pass(*ctls):
    """Inside: each controller reads each key of its stores once, and sees what it writes. Controllers over the same store
    share its reads (the console's loops write through one and read through another). Only on the calling thread — the
    console's doors read through the same controller from theirs, and see the store. A pass inside a pass is the outer one."""
    stores: dict[int, _PassStore] = {}
    opened = []
    for c in ctls:
        if c._reads() is not None:
            continue
        v, o = c.__dict__["_vars"], c.__dict__["_objects"]
        c._pass_local.reads = (stores.setdefault(id(v), _PassStore(v)), stores.setdefault(id(o), _PassStore(o)))
        opened.append(c)
    try:
        yield
    finally:
        for c in opened:
            c._pass_local.reads = None


# The only writer of `<name>/*`. It holds nothing: every method reads the store, decides, and writes by CAS,
# so two instances are harmless — this is the property `spec.SpecController` and the VMS controller inherit,
# and the reason the controller is never on the recovery path.
class Controller:
    """The only writer of <name>/*. Holds nothing: every method reads the
    store, decides, and writes by CAS. Two instances are harmless."""

    # Keeps the `Subsystem`, the two stores and a wall clock (tests inject a fake).
    def __init__(self, sub: Subsystem, vars_: Variables, objects: ObjectStore, wall=time.time):
        self._pass_local = threading.local()
        self.sub, self.vars, self.objects, self.wall = sub, vars_, objects, wall
        # What this controller has seen change, and when, by its own clock (`Eyes`; the review's thirteenth pass,
        # blocker 4): how long a heartbeat, a slot or a resource's row has stood still — never a writer's timestamp.
        self.eyes = Eyes(judge_clock(wall), wall)
        check_schema(vars_)                       # a build older than the store does not run at all

    # The stores — or, inside `one_pass` on this thread, the pass's reads of them. Assigning sets the store itself.
    def _reads(self):
        local = self.__dict__.get("_pass_local")
        return getattr(local, "reads", None) if local is not None else None

    @property
    def vars(self):
        r = self._reads()
        return r[0] if r is not None else self.__dict__["_vars"]

    @vars.setter
    def vars(self, v):
        self.__dict__["_vars"] = v

    @property
    def objects(self):
        r = self._reads()
        return r[1] if r is not None else self.__dict__["_objects"]

    @objects.setter
    def objects(self, o):
        self.__dict__["_objects"] = o

    def one_pass(self):
        return one_pass(self)

    # A prefix's heartbeats, parsed — once per pass inside one (`_PassStore.memo`), on every call outside. `rows`: what is
    # derived from rows under the prefix rather than from objects (`SpecController._rows_by`).
    def _per_pass(self, prefix: str, read, name: str = "", rows: bool = False):
        store = self.vars if rows else self.objects
        return store.memo(prefix, read, name) if isinstance(store, _PassStore) else read()

    # The one write primitive: read `(items, idx)`, call `mutate(dict(items or {}))`; if it returns `None`
    # nothing is written and the current items are returned; otherwise `put(cas=idx)`; on `Conflict` re-read
    # and repeat, up to `retries`, then `RuntimeError`. Every mutation in `SpecController` goes through
    # this, which is what makes "two controllers agree by CAS" true.
    def write(self, path: str, mutate, retries: int = 10) -> dict:
        """Read-modify-write by CAS: `mutate(items or {}) -> new items`.
        A conflict means another instance wrote; re-read and go again."""
        for attempt in range(retries):
            try:
                items, idx = self.vars.get(path)
            except Garbled as e:                     # a row the store cannot read is written whole: from nothing, under TORN
                items, idx = None, e.index
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
        for hb in self._heartbeats():
            # …by whether its heartbeat CHANGED within `max_age` of this controller's clock (`Eyes`; the thirteenth pass,
            # blocker 4): a worker whose clock runs behind is not taken for gone, nor one ahead for alive
            if self.eyes.fresh(self.sub.heartbeat_key(hb.worker), hb.token, max_age, hb.ts, self.sub.name):
                out[hb.worker] = hb
        return out

    # Every heartbeat under the prefix, parsed, whatever its age — read once per pass (`_per_pass`): `capacity_of`,
    # `server_of`, `place_of` ask it per unit and per candidate, and each asking was a listing and a read of every one.
    #
    # Its own name in the pass's memo (the review's tenth pass, minor): it was `(prefix, "")`, and `near_index` keeps the
    # followed subsystem's heartbeats under the same `(prefix, "")` as a DICT — in one pass shared by a recorder's
    # controller (`near: vms`) and the VMS's, the list read here was that dict, and `hb.ts` an `AttributeError`.
    def _heartbeats(self) -> list[Heartbeat]:
        def read():
            out = []
            # One prefix, no filter: `<name>/heartbeats/` holds heartbeats and nothing else.
            for key in self.objects.list(self.sub.heartbeats_prefix()):
                raw = self.objects.get(key)
                hb = parse_heartbeat(key, raw) if raw else None
                if hb is not None:
                    out.append(hb)
            return out
        return self._per_pass(self.sub.heartbeats_prefix(), read, "heartbeats")

    # Reads one worker's row. One whose `rev` does not parse is read for the units it names (`read_assignment`).
    def assignment(self, worker: str) -> Assignment:
        items, _ = stored(self.vars, self.sub.assignment(worker), ASSIGNMENTS)
        return self._assignment(worker, items)

    def _assignment(self, worker: str, items) -> Assignment:
        return read_assignment(self.sub.assignment(worker), worker, items)

    # Replaces the worker's assignment with the sorted, de-duplicated list and bumps `rev`.
    def assign(self, worker: str, units: list[str]) -> Assignment:
        def mutate(items):
            rev = self._assignment(worker, items).rev + 1
            return Assignment(worker, sorted(set(units), key=str), rev).to_items(self.sub.assignment(worker))
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
            if LIST_SEPARATOR in str(unit):                 # never into the list (`Assignment.to_items`): no write either
                UNLISTED.garbled(f"{self.sub.assignment(worker)}#{unit}", f"{LIST_SEPARATOR!r} in its name")
                return None
            return Assignment(worker, sorted(set(a.units) | {unit}, key=str), a.rev + 1).to_items(self.sub.assignment(worker))
        return self._assignment(worker, self.write(self.sub.assignment(worker), mutate))

    # The mirror of `assign_add`.
    def assign_remove(self, worker: str, unit: str) -> Assignment:
        def mutate(items):
            a = self._assignment(worker, items)
            if unit not in a.units:
                return None
            return Assignment(worker, [u for u in a.units if u != unit], a.rev + 1).to_items(self.sub.assignment(worker))
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
            items, _ = stored(self.vars, path, SLOTS)
            slot = read_slot(path, name, items)   # one that does not parse is not the end of the pass (`read_slot`)
            if slot is not None:
                out[name] = slot
        return out

    # Slots whose holder let go on purpose (scale-in), or that the controller released (`free_slot`), and that still
    # have units assigned: what a subsystem redistributes. A slot that merely lapsed is not here — that is a crash, and
    # the scheduler brings the process back under the same name. Sorted by slot number.
    def released_slots(self) -> list[str]:
        """Slots whose holder let go on purpose (scale-in), or freed, and
        that still have an assignment: what a subsystem redistributes. A slot
        that merely lapsed is NOT here — that is a crash, and the scheduler
        brings its process back under the same name."""
        return sorted((n for n, s in self.slots().items() if s.released and self.assignment(n).units),
                      key=slot_number)

    # -- draining a SERVER ---------------------------------------------------------------------------
    # A slot is about one allocation; an upgrade is about a machine. One row says which server is going
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
        behind = {n: b for n, b in builds(self.objects, now, eyes=self.eyes).items()
                  if b["live"] and (b["schema"] is None or b["schema"] < version)}   # not known: behind any (`builds`)
        if behind:
            known = [b["schema"] for b in behind.values() if b["schema"] is not None]
            raise SchemaTooNew(f"still running: {', '.join(sorted(behind))} — at schema "
                               f"{min(known) if known else 'not known'}")
        def mutate(items):
            try:
                have = int((items or {}).get("version", SCHEMA))
            except PARSE_ERRORS:                  # what it is now cannot be read: not raised past (the tenth round)
                raise SchemaTooNew(f"{SCHEMA_KEY} does not parse: whether {version} is forward cannot be told — "
                                   f"mend the row first") from None
            if version < have:
                raise SchemaTooNew(f"schema does not go back: {have} -> {version}")
            return {"version": str(version), "at": str(now)}
        return self.write(SCHEMA_KEY, mutate)

    def undrain(self) -> dict:
        """The server is back. Its workers become placeable again, and `ensure_home`
        starts bringing back what its rows name — one unit a pass."""
        return self.write(DRAIN_KEY, lambda items: {"server": "", "at": str(self.wall())})

    # -- a slot that stopped renewing: what happens to it, decided in one place ----------------------------------
    # THE OPERATOR OPERATES SERVERS, NOT WORKERS (the owner's decision, 3 Oct, on the review's eleventh pass). There was
    # a door to retire a WORKER from the console (`POST /workers/<w>/retire`), and it asked the operator the one thing
    # they cannot know: whether a process that says nothing is dead or hung. A hung one went on recording beside the
    # worker its cameras were given to — two holders of cameras 1 and 3 — and a request refused as "alive" stood, and
    # retired the same process at its next silence an hour and a half later. That door is gone. What becomes of a slot
    # that stopped renewing is decided by the controller from facts, by ONE rule (`slot_fate`), which three things read:
    # the move off a dead worker (`gone_servers` → `redistribute`), releasing a slot (`release_unlisted`), and a
    # decommission (`decommission_refusal`, `apply_decommissions`). Releasing marks the slot released (`free_slot`):
    # `redistribute` moves what it lists, and a process under it learns at its next renewal that the name is not its own.
    def free_slot(self, worker: str) -> bool:
        """Mark the slot released by CAS — unless its row shows life again: renewed since it lapsed, or released
        already. A row that does not parse is written whole: released, and nobody's. True when this call freed it."""
        key, done = self.sub.slot_key(worker), [False]

        def mutate(items):
            s, now = read_slot(key, worker, items), self.wall()
            done[0] = False
            if s is None:
                if not items:
                    return None                       # no row at all: nothing to free
                # A row that does not parse is the slot most wanted gone, and was a dead end (the sixth pass, the
                # follow-up): written over, whole — released, nobody's.
                done[0] = True
                said = items if isinstance(items, dict) else {}
                return Slot(worker, "", now, True, 0, server=str(said.get("server") or "")).to_items()
            if s.released or now <= s.until + SLOT_LOST_AFTER:
                return None                           # released already, or renewed since it was judged
            done[0] = True
            # …the row whole, its `server` with it (the review's thirteenth pass, «Вопросы» 1): rebuilt without it, a
            # freed slot no longer said where its holder ran — what a fresh controller reads where the heartbeat is gone
            return Slot(worker, s.holder, s.until, True, s.gen, server=s.server).to_items()
        self.write(key, mutate)
        return done[0]

    # WHAT BECOMES OF A SLOT — THE ONE RULE (the review's eleventh pass, blocker 3; the owner's decision, 3 Oct). "Is it
    # dead?" was asked in three places by three rules: the console's retire by the slot's `until` and the worker's
    # heartbeat, the move off a gone server by the slot and the server's resource, nothing else by anything. Now here,
    # once. First, is anything under the slot still alive:
    #
    #   alive    the slot's `until` is ahead (it renews), or passed less than `SLOT_LOST_AFTER` ago (the slot outlives
    #            the lease — 45 s against `ttl − margin` = 25 — and the store's lag is on top), or the worker was heard
    #            from within `SLOT_LOST_AFTER` (a heartbeat dated ahead of this clock too). Nothing happens — except
    #            that a slot past its `until` whose server's resource answers and says the process is dead moves at
    #            once, without the margin and whatever its last heartbeat (`_dead_on`; the owner, 3 Oct: failover
    #            shortened by the resource — a slot's 45 s, where it was 45 + 45)
    #
    # Then, the resource on the server the worker last said it ran on says two things in its heartbeat: which workers are
    # placed there (`workers` — registered with it, `Worker.present`) and whose processes are alive (`running` — still
    # holding the lock). A field missing is "not said"; an empty list is a list. The four cases, in the owner's words:
    #
    #   hung        the resource answers and names the process running: it neither renews nor speaks, and it may be
    #               writing. NOT moved — a second writer is what a move would make — and an alarm (`worker.hung`, once an
    #               episode: the journal, `/servers`, `<sub>_workers_hung`). Until `hung_move_after` past the slot's
    #               `until`: then `hung_moved`, moved anyway, with an alarm (`worker.hung_moved`) — so a hung process gets
    #               no second writer early, and there is no hole for ever either
    #   move        the process is dead (in `workers`, not in `running`), or the resource is silent too: the units move,
    #               the slot stays — the server's supervisor brings the process back under its name, with nothing to do
    #   release     the resource answers and does not list the worker at all: that server does not run it any more — the
    #               slot is released (`release_unlisted`), and the units move. A slot row that does not parse is not
    #               released — `move`: the units go, the row stays as it is (the product's DZ)
    #   wait     a resource without those fields (an older build), a worker that never registered (`present` not in its
    #            heartbeat), no resource on its server, or no server known: what it was before — a silent resource
    #            where the spec requires one moves (`_moves_off_silent`), anything else waits
    #   unsure   (the review's twelfth pass) the resource is there but what it says cannot be taken for the whole truth:
    #            it could not read every registration (`presence_unread`, `presence_error` — blocker 3), the worker
    #            could not write its name beside its lock (`presence_unsaid`), or the resource writes to the store but
    #            its heartbeat cannot be read fresh (`resource_state` "unreachable" — a door this process cannot reach is
    #            not a silent server, major 9). Nothing moves, as `wait` — and, unlike `wait`, the name is not given to
    #            a nameless process either (`Worker._held`). Until `hung_move_after` past the slot's `until`, as `hung`:
    #            then `unsure_moved`, moved anyway, with an alarm (`worker.unsure_moved`) and the name given — a worker
    #            nobody can judge left its cameras written by nobody for ever, and an alarm was all (the owner's middle
    #            way for `hung`, applied to the doubt: a hung process is KNOWN to run and moves at the limit, so one
    #            that MAY run moves there too). `wait` keeps its old rule: it is what an older resource or a worker
    #            that never registered got before the resource said anything (the owner, 3 Oct: "old resource without
    #            fields → old behaviour")
    #
    # WHAT THE STORE REMEMBERS (the review's twelfth pass, blocker 5; the owner's decision of 4 Oct). A controller started
    # after a server died had read nothing of it: in М11 the worker's heartbeat and the resource's are files on that very
    # server, and "never said which server" held its cameras for ever. Two facts now live in the store, which outlives
    # any server: the server a slot's holder runs on (`Slot.server`, in every renewal) and when each resource last said
    # it is there (`at` on its door row, every `ALIVE_EVERY`; `resource_state`). A fresh controller reads both: the slot
    # lapsed past the margin, no heartbeat to read, the resource's row older than `SLOT_LOST_AFTER` — two silences, and
    # the units move. A slot left in `wait` or `unsure` with units on it is counted and said (`unjudged`).
    #
    # WHOSE CLOCK (the review's thirteenth pass, blocker 4; the owner's decision of 4 Oct). Every "still there?" here is
    # asked of what THIS controller has seen change, by its own clock (`Eyes`): the slot alive for a term (`SLOT_TERM`)
    # from when it saw the row renewed — not until the `until` its holder's clock wrote; the worker heard when its
    # heartbeat changed within `SLOT_LOST_AFTER`; the resource by its heartbeat and its door row the same way
    # (`resource_state`). A clock ahead holds nothing (`until` an hour on held a dead server's cameras for an hour — the
    # twelfth pass, major 17) and a clock behind takes nothing away (one 50 s behind had a live worker's cameras moved at
    # 10 s). The writers' times are counted as a skew where a change is first seen, and said (`say_skews`).
    #
    # A SLOT ROW THAT DOES NOT PARSE (`slot` None; the product's DZ) is not a dead worker: no lease to read, so it is
    # "not known", and moves only on two words — its worker's heartbeat silent past `SLOT_LOST_AFTER`, AND its server's
    # resource saying there is no such process (placed and not running, or not listed) or silent itself. Neither the
    # shortened move nor a release is made on it.
    #
    # Whatever the owner decides next changes this function, and every caller follows. What none of it covers: a worker
    # cut off from the store together with its whole server records on to its lease's end plus `UNCONFIRMED_MAX`
    # (М11: 90 s) — data under a stale epoch, the duplicate feedback BK chose over a hole.
    def slot_fate(self, worker: str, slot: "Slot | None", hung_after: float | None = None) -> tuple[str, str, str]:
        """`(fate, server, why)`: fate "alive", "hung", "hung_moved", "move", "release", "wait", "unsure" or
        "unsure_moved" (see above); `slot` None: a row that does not parse — no lease to read, the heartbeat and the
        server decide. `hung_after`: the controller's limit as it published it, for whoever judges in another process
        (`published_hung_limit`)."""
        now = self.eyes.clock()                       # this controller's clock: what everything below is measured by
        limit = self.hung_move_after if hung_after is None else hung_after
        stored_server = slot.server if slot is not None else ""
        until = self._slot_end(worker, slot) if slot is not None else None
        if until is not None and until > now:
            return "alive", "", f"{worker} holds its name for another {int(until - now) + 1} s"
        hb = self._heard(worker)                      # read once: the shortened move asks where it ran, the rest below
        dead = self._dead_on(worker, hb, slot.holder) if slot is not None else None
        if dead:
            return "move", dead, (f"{worker}'s process on {dead} is not running: moved when its slot ran out, its "
                                  f"server's resource saying so")
        if until is not None and now <= until + SLOT_LOST_AFTER:
            return "alive", "", (f"{worker} stopped renewing its name {int(now - until)} s ago; what it started "
                                 f"may still be writing for {int(until + SLOT_LOST_AFTER - now) + 1} s more")
        heard = self._heard_ago(worker, hb)
        if heard is not None and heard <= SLOT_LOST_AFTER:
            return "alive", "", f"{worker} was heard from {int(heard)} s ago"
        server = hb.extra.get("server") if hb is not None else None
        if (not isinstance(server, str) or not server) and stored_server:
            server = stored_server                    # its heartbeat gone (with its server): where its slot says it ran
        if not isinstance(server, str) or not server:
            return "wait", "", f"{worker} never said which server it runs on"
        state, said = self.resource_state(server, SLOT_LOST_AFTER), self.said_on(server)
        present = hb is not None and hb.extra.get("present") is True

        def unsure(cause: str) -> tuple[str, str, str]:   # …for up to the hung limit, then moved anyway (see above)
            since = self.hung_since(worker, slot)
            if now - since > limit:
                return "unsure_moved", server, (f"{cause}, for {int(now - since)} s past its slot's end, longer than "
                                                f"{int(limit)} s: its units move anyway")
            return "unsure", server, f"{cause}: its units stay, for up to {int(limit)} s"
        if state == "unreachable":
            return unsure(f"{worker} is silent; the resource on {server} still writes to the store, but its heartbeat "
                          f"cannot be read here — whether the process runs cannot be told")
        if state == "silent" and (hb is None or said is None or not present):
            if hb is None or self._moves_off_silent():   # two silences, judged from the store where nothing else is left
                return "move", server, f"server {server} gone: slot {worker} lapsed and its resource silent"
        if hb is not None and hb.extra.get("presence_unsaid") and state != "silent":
            return unsure(f"{worker} is silent, and could not write its name beside its lock on {server}: what the "
                          f"resource there says of it cannot be taken for its end")
        if state == "unknown" or said is None or not present:
            doubt = self.presence_doubt(server) if state == "live" and present else ""
            if doubt:
                return unsure(f"{worker} is silent; the resource on {server} {doubt} — whether its process runs "
                              f"cannot be told")
            return "wait", server, (f"{worker} is silent; whether its process runs on {server} cannot be told — "
                                    f"left to the process and its supervisor")
        placed, running = said
        if state == "silent":
            return "move", server, f"server {server} gone: slot {worker} lapsed and its resource silent"
        if worker in running or (slot is not None and self.holder_runs(server, slot.holder)):
            since = self.hung_since(worker, slot)
            if now - since > limit:
                return "hung_moved", server, (f"{worker} has been hung on {server} for {int(now - since)} s, longer than "
                                              f"{int(limit)} s: its units move anyway")
            return "hung", server, (f"{worker} neither renews its name nor heartbeats, but its process runs on {server}: "
                                    f"hung, or cut off from the store — its units stay, so they get no second writer, for "
                                    f"up to {int(limit)} s; look at {server}")
        doubt = self.presence_doubt(server)
        if doubt:                                     # not listed, or not running — by a list with holes in it (blocker 3)
            return unsure(f"{worker} is silent; the resource on {server} {doubt} — whether its process runs cannot be "
                          f"told")
        if worker in placed:
            return "move", server, f"{worker}'s process on {server} is not running"
        if slot is None:                              # a row nobody can read is not written over as released (DZ)
            return "move", server, (f"{server} does not run {worker} any more and its slot row does not parse: its "
                                    f"units move, the row is left as it is")
        return "release", server, f"{server} does not run {worker} any more: its resource answers and lists it nowhere"

    # FAILOVER SHORTENED BY THE RESOURCE (the owner's decision, 3 Oct). The margin past a slot's `until`
    # (`SLOT_LOST_AFTER`) is there for a process that may still be writing: it stopped renewing, and nobody can say
    # whether it lives. When its server's resource answers and says the process is NOT running — registered there
    # (`workers`), its lock let go (not in `running`) — somebody can: a dead process writes nothing, and its units
    # move the moment its slot runs out, not 45 s after. The server the worker last said it runs on, when all of that
    # is said; else None, and the slot is judged as before. A silent resource shortens nothing: then nobody can say.
    def _dead_on(self, worker: str, hb, holder: str = "") -> str | None:
        server = hb.extra.get("server") if hb is not None else None
        if not isinstance(server, str) or not server or hb.extra.get("present") is not True:
            return None
        if self.resource_state(server, SLOT_LOST_AFTER) != "live" or hb.extra.get("presence_unsaid") \
                or self.presence_doubt(server):
            return None                               # a list with holes in it says nobody is dead (blocker 3)
        said = self.said_on(server)
        if self.holder_runs(server, holder):
            return None                               # the slot's own holder still holds its lock: not dead, whatever the name
        return server if said is not None and worker in said[0] and worker not in said[1] else None

    # The end of a slot's term as this controller counts it: `SLOT_TERM` past when it first saw the row as it is now —
    # renewed, or claimed (`Eyes`; the thirteenth pass, blocker 4). By this controller's clock (`eyes.clock`).
    def _slot_end(self, worker: str, slot: "Slot") -> float:
        token = (slot.holder, slot.until, slot.gen, slot.released)
        return self.eyes.since(self.sub.slot_key(worker), token) + SLOT_TERM

    # How long ago this controller saw the worker's heartbeat change, or None when there is none to read.
    def _heard_ago(self, worker: str, hb) -> float | None:
        if hb is None:
            return None
        key = self.sub.heartbeat_key(worker)
        ts = number(f"{key}#ts", hb.ts, float, None)
        return None if ts is None else self.eyes.age(key, hb.token, ts, self.sub.name)

    # Since when a hung worker has been hung — or an unsure one not judged: its slot's end as this controller counts it
    # (`_slot_end`) — or, for a row that does not parse, since its heartbeat stood still. By this controller's clock
    # (`eyes.clock`; a page shows it through `eyes.wall_of`).
    def hung_since(self, worker: str, slot: "Slot | None") -> float:
        if slot is not None:
            return self._slot_end(worker, slot)
        hb = self._heard(worker)
        heard = self._heard_ago(worker, hb)
        if heard is not None:
            return self.eyes.clock() - heard
        # No heartbeat: since this controller first called it hung — so the limit still comes, counted from a restart
        # of the controller at the latest.
        return self.__dict__.setdefault("_hung_first", {}).setdefault(worker, self.eyes.clock())

    # How long a hung worker's units stay with it, past its slot's `until`, before they move anyway (`slot_fate`): fifteen
    # minutes, as the product's `HUNG_MOVE_AFTER` — time for the server's supervisor to see a process that has stopped
    # answering and restart it (systemd's `WatchdogSec`, launchd's `KeepAlive`), or for the person paged by `worker.hung`
    # to look, before its cameras get a second writer; and short enough that a process hung for good leaves no hole for
    # ever. Its stand-in has already held the slot `STAND_IN_FOR` (five minutes) when the hang was in one step.
    # `HUNG_MOVE_AFTER` in the controller's environment (`vms/__main__._controller_loop`) — and said in its pass report, by
    # which every other process judges (`published_hung_limit`).
    hung_move_after = HUNG_MOVE_AFTER

    # Where the resource cannot say who runs where (an older build, a worker that never registered), whether a lapsed slot
    # on a server whose resource is silent too moves — two silences from one server, a fact about the server. The base
    # controller moves nothing on its own; `SpecController` moves when its spec requires a resource.
    def _moves_off_silent(self) -> bool:
        return False

    # The worker's own heartbeat, whatever its age, or None — one key read, not the listing (`/servers` asks per worker).
    def _heard(self, worker: str):
        key = self.sub.heartbeat_key(worker)
        raw = self.objects.get(key)
        return parse_heartbeat(key, raw) if raw else None

    # The state of the resource on a server, from `platform/resources/<server>/heartbeat`: `"live"` (younger than
    # `lost_after`), `"silent"` (older), `"unknown"` (never heartbeaten — a box before its resource process starts, a
    # bench). Here rather than in `SpecController` since `slot_fate` asks it.
    #
    # …AND A SECOND OPINION FROM THE STORE (the review's twelfth pass, blocker 5 and major 9). Where the heartbeat is not
    # fresh, the resource's own row is asked — `at` on `platform/doors/<server>`, written every `ALIVE_EVERY`
    # (`Resource.say_door`): fresh, the resource is there and only its heartbeat cannot be read here (a door this
    # process cannot reach, a lagging copy) — `"unreachable"`, which moves nothing; stale too, or the heartbeat stale with
    # no row, `"silent"`; neither ever heard, `"unknown"`. A controller started after the server died finds the row, and
    # sees the silence the controller before it heard.
    #
    # …EACH BY WHETHER IT CHANGED, ON THIS CONTROLLER'S CLOCK (the review's thirteenth pass, blocker 4): the heartbeat's
    # `ts` and the row's `at` are the resource's clock, and were compared with this one — a resource 6 s ahead or 50 s
    # behind was "silent" while it beat, and a live worker's cameras went. Now they are tokens: changed within
    # `lost_after`, the resource is there. The row is looked at every time, so a silence is timed from its last change.
    def resource_state(self, server: str, lost_after: float = 45.0) -> str:
        from .resource import RESOURCES
        hb = self._resources().get(server)
        at = self._said_alive(server)
        door = self._door_age(server, at) if at is not None else None     # looked at whatever the heartbeat says
        if hb is not None and self.eyes.fresh(f"{RESOURCES}/{server}/heartbeat", hb["ts"], lost_after, hb["ts"],
                                              "platform"):
            return "live"
        if door is not None and door <= lost_after:
            return "unreachable"
        # A heartbeat that is there and does not parse (`ts: NaN`) is a resource known, and not live: "silent" — it was
        # "unknown", and `wait` for ever (the review's twelfth pass, minor). Its door row, when fresh, said otherwise above.
        if hb is None and at is None and f"platform/resources/{server}/heartbeat" not in _garbled_keys:
            return "unknown"
        return "silent"

    # When the resource on `server` last said in the store that it is there (`at` on its door row), or None. Read with
    # every look at the server, fresh heartbeat or not — once a pass for each: a silence is timed from the row's last
    # change (`resource_state`; the thirteenth pass).
    def _said_alive(self, server: str) -> float | None:
        from .resource import DOORS
        key = f"{DOORS}/{server}"

        def read():
            try:
                items, _ = self.vars.get(key)
            except (Garbled, *PARSE_ERRORS):
                return None
            at = (items or {}).get("at") if isinstance(items, dict) else None
            return None if at is None else number(f"{key}#at", at, float, None)
        return self._per_pass(key, read, "alive", rows=True)

    # How long the resource's row has said the same `at`, by this controller's clock.
    def _door_age(self, server: str, at: float) -> float:
        from .resource import DOORS
        return self.eyes.age(f"{DOORS}/{server}", at, at, "platform")

    # What the resource on `server` says of THIS subsystem's workers (`workers`, `running` in its heartbeat, from the
    # processes registered with it — `resource.workers_here`): `(workers, running)`, or None when it does not say.
    def said_on(self, server: str) -> tuple[set[str], set[str]] | None:
        hb = self._resources().get(server, {})
        out = []
        for field in ("workers", "running"):
            said = hb.get(field)
            names = said.get(self.sub.name, []) if isinstance(said, dict) else None
            if not isinstance(names, list):
                return None
            out.append({str(n) for n in names})
        return out[0] | out[1], out[1]

    # Whether the process a slot names as its holder still holds its lock on `server` — by the lock's own name
    # (`running_instances`), not by what it wrote beside it: a `.json` absent, torn or naming nobody is no proof of an
    # end (the review's twelfth pass, blocker 3). False where the resource does not say.
    def holder_runs(self, server: str, holder: str) -> bool:
        said = self._resources().get(server, {}).get("running_instances")
        return bool(holder) and isinstance(said, list) and presence_name(holder) in {str(n) for n in said}

    # What the resource on `server` says it could NOT read of the workers registered with it (`resource.presence_here`;
    # the review's twelfth pass, blocker 3), in words — or "" when its lists are whole. With a hole in them, a worker
    # absent from them is not a worker that is not there: nobody is judged dead or gone by them (`slot_fate` "unsure").
    def presence_doubt(self, server: str) -> str:
        hb = self._resources().get(server, {})
        err, unread = hb.get("presence_error"), hb.get("presence_unread")
        if err:
            return f"cannot read the registrations of its workers ({str(err)[:200]})"
        if unread:
            return f"cannot read {unread} of the registrations of its workers"
        return ""

    def _resources(self) -> dict:
        from .resource import RESOURCES, resources_seen            # the platform's own reader of the resource heartbeats
        return self._per_pass(RESOURCES + "/", lambda: resources_seen(self.objects))   # asked per worker, read once a pass

    # Every slot that stopped renewing, and what becomes of it: `{worker: (fate, server, why)}` for every slot that is
    # held and not released — a row that does not parse too, judged on its heartbeat and its server. Read once a pass.
    def fates(self) -> dict[str, tuple[str, str, str]]:
        return {w: j[:3] for w, j in self._judged_slots().items()}

    # A WRITER'S CLOCK OFF THIS ONE IS SAID, AND MOVES NOTHING (the review's thirteenth pass, blocker 4; the owner's decision
    # of 4 Oct). Nothing here is judged by a writer's time any more (`Eyes`); what it is still good for is to say that a
    # server's clock is wrong — the person who reads `/metrics` and the journal mends NTP. Past `SKEW_ALARM` (ahead by
    # `FUTURE_TOLERANCE`, behind by fifteen seconds: a change is first seen up to a beat and a pass after it was written,
    # so "behind" carries that much on top), `clock.skew` once an episode per writer; `{writer: seconds}` is returned
    # for the pass report (`clock_skew`).
    def say_skews(self) -> dict[str, float]:
        ahead, behind = SKEW_ALARM
        off = {k: round(v, 1) for k, v in sorted(self.eyes.skews.items()) if v > ahead or v < -behind}
        said = self.__dict__.setdefault("_skew_said", set())
        for key in sorted(set(off) - said):
            way = f"{off[key]:+.0f} s — ahead of" if off[key] > 0 else f"{off[key]:+.0f} s — behind"
            log.error("%s: the clock that writes %s is %s this controller's: nothing is judged by it, but whatever "
                      "reads its times reads them wrong — mend NTP on that server", self.sub.name, key, way)
            self.journal.say("clock.skew", ALARM, of=self.sub.name, writer=key, skew=off[key],
                             why=(f"the clock that writes {key} is {way} this controller's; nothing moves for it "
                                  f"(freshness is judged by change), but its times are wrong where they are shown — "
                                  f"mend NTP on that server"))
        said.clear(); said.update(off)
        return off

    # A refusal from a judge that has not watched a silence's length yet, said so (the review's thirteenth pass, blocker
    # 4): it takes what it has never seen as just changed, so a console started a moment ago says "heard 0 s ago" of a
    # server that went an hour ago — true of what it saw, and the operator needs to know to ask again.
    def not_watched_yet(self, refusal: str | None) -> str | None:
        watched = self.eyes.watched()
        if refusal is None or watched >= SLOT_LOST_AFTER:
            return refusal
        return (f"{refusal} (this process started watching {int(watched)} s ago, and a silence is told once nothing has "
                f"changed for {int(SLOT_LOST_AFTER)} s by its own clock — ask again in {int(SLOT_LOST_AFTER - watched) + 1} s)")

    # EVERYTHING IT JUDGES BY, LOOKED AT NOW (the review's thirteenth pass, blocker 4): every heartbeat, every slot, and
    # the resource and door row of every server it knows of — so its eyes (`Eyes`) see what changed since the last look,
    # and a silence is timed from the last change and not from the first time this controller happened to ask. The pass
    # looks first (`SpecController.pass_once`); a test or a page that judges between passes calls it as the pass would.
    def look(self) -> None:
        with one_pass(self):
            seen = self.workers_seen(max_age=1e12)
            servers = set(self._resources())
            servers |= {hb.extra["server"] for hb in seen.values() if isinstance(hb.extra.get("server"), str)}
            servers |= {s.server for s in self.slots().values() if s.server}
            for server in sorted(servers):
                self.resource_state(server)
            self._judged_slots()

    # …and the slots whose NAME another process may take now, by the revision of the row so judged: `{worker: rev}`.
    # A name goes with its units: given where they move (`NAME_FATES`) — and under `wait` past `hung_move_after` from the
    # slot's end, as `unsure` gives it (the owner's decision of 4 Oct: `wait` keeps the name, as `unsure` does, until the
    # limit). Said in the pass report (`names_given`), and a process looking for a name takes only one said there AT
    # THE REVISION it reads (`Worker._held`): the controller watches the rows change all the time, a process that has just
    # started has seen nothing change yet (the review's thirteenth pass, blocker 4).
    def names_given(self) -> dict[str, object]:
        return {w: j[3] for w, j in self._judged_slots().items() if j[4]}

    # …and every slot that stopped renewing, as this controller judged it: `{worker: {fate, why, rev, since}}` — `since`
    # on its wall, for a page (`Mount._judged` shows the controller's verdict at the revision it reads, rather than one of
    # its own eyes that have watched nothing yet).
    def fates_said(self) -> dict[str, dict]:
        out = {}
        for w, (fate, server, why, rev, _, slot) in self._judged_slots().items():
            if fate == "alive":
                continue
            out[w] = {"fate": fate, "server": server, "why": why, "rev": rev,
                      "since": round(self.eyes.wall_of(self.hung_since(w, slot)), 3)}
        return out

    # …said where every process of the subsystem reads it (`published_names`): `SpecController.pass_once` writes it in its
    # report; a controller with no pass of its own (the platform's lessons) says it with this, its limit beside it.
    def publish_names(self) -> dict:
        rep = {"ts": self.wall(), "hung_move_after": self.hung_move_after, "names_given": self.names_given(),
               "fates": self.fates_said()}
        self.objects.put(f"{self.sub.name}/{CONTROLLER_PASS}", json.dumps(rep).encode())
        return rep

    def _judged_slots(self) -> dict[str, tuple]:
        def read():
            out = {}
            prefix = self.sub.name + "/slots/"
            limit = self.hung_move_after
            for path in sorted(self.vars.list(prefix)):
                worker = path[len(prefix):]
                items, rev = stored(self.vars, path, SLOTS)
                s = read_slot(path, worker, items)
                if s is not None and (s.released or not s.holder):
                    continue
                fate, server, why = self.slot_fate(worker, s)
                if not server:                         # where it ran, for a decommission: the last heartbeat's word
                    hb = self._heard(worker)
                    said = hb.extra.get("server") if hb is not None else None
                    server = said if isinstance(said, str) else ""
                gives = fate in NAME_FATES or (fate == "wait" and self.eyes.clock() - self.hung_since(worker, s) > limit)
                out[worker] = (fate, server, why, rev, gives, s)
            return out
        return self._per_pass(self.sub.name + "/slots/", read, "fates", rows=True)

    # -- decommissioning a SERVER: the operator's word that a machine is gone for good -----------------------------
    # The sibling of `drain`: a drain says the machine will come back, this that it will not. One row per server,
    # `platform/decommission/<server> {by, at, why}`, the platform's (a machine carries every subsystem), written only by
    # the console and read by every controller. Refused while the server ANSWERS, by any of three signs
    # (`decommission_refusal`): "take it out and switch it off" is the operator's to do and the platform's to see. Once
    # the server is silent, each controller carries it out in its subsystem (`apply_decommissions`): every slot on the
    # server released, its units moved, and a mark `<sub>/decommissioned/<server>` saying what was done. No worker on that
    # server is placed on (`_pool`), nor given a slot (`Worker._claim_slot`), until the row is deleted.
    def decommission_requests(self) -> dict[str, dict]:
        """`{server: {by, at, why}}` — every server the operator decommissioned (`platform/decommission/*`)."""
        return self._per_pass(DECOMMISSION, lambda: decommissioned(self.vars), "decommission", rows=True)

    def decommission_marks(self) -> dict[str, dict]:
        """`{server: {asked_at, at, slots, units, holds}}` — the decommissions carried out in this subsystem."""
        def read():
            prefix, out = self.sub.decommissioned_key(""), {}
            for path in self.vars.list(prefix):
                items, _ = stored(self.vars, path, DECOMMISSIONS)
                if items:
                    out[path[len(prefix):]] = {"unread": str(items.error)} if isinstance(items, Unread) else dict(items)
            return out
        return self._per_pass(self.sub.decommissioned_key(""), read, "marks", rows=True)

    # The workers whose last heartbeat, whatever its age, names `server` — what runs, or ran, there.
    def workers_on(self, server: str) -> list[str]:
        return sorted(hb.worker for hb in self._heartbeats() if hb.extra.get("server") == server)

    # WHETHER THE SERVER ANSWERS — any of three signs, each enough (the product's rule): its resource heard within
    # `SLOT_LOST_AFTER`; a worker of that server heard within it; a worker of that server whose slot is renewed, or was
    # less than `SLOT_LOST_AFTER` ago — without the last two, a live process undoes the release at its next renewal, or
    # writes on under it. The last two are `slot_fate`'s "alive", asked of it: the course waits out the margin on the
    # third sign as every slot judgement here does; the product asks only that the slot is not being renewed. `(refusal, warning)`: the refusal names
    # the sign, in words; the warning is for a server whose resource was never heard — it passes, on the operator's word.
    def decommission_refusal(self, server: str) -> tuple[str | None, str | None]:
        from .resource import RESOURCES
        hb = self._resources().get(server)
        state = self.resource_state(server, SLOT_LOST_AFTER)
        # …how long ago, by what this controller saw change (the review's thirteenth pass, blocker 4): a live server whose
        # clock ran 30 s ahead was decommissioned — its resource's `ts` read as "not live" by this clock
        if hb is not None and state == "live":
            ago = self.eyes.age(f"{RESOURCES}/{server}/heartbeat", hb["ts"])
            return (f"{server} answers: its resource was heard {int(ago)} s ago — take the server out of service and "
                    f"switch it off first"), None
        if state == "unreachable":                    # its heartbeat cannot be read here, but it writes to the store
            at = self._said_alive(server)
            ago = self._door_age(server, at) if at is not None else 0.0
            return (f"{server} answers: its resource said it is there {int(ago)} s ago — take the server out of service "
                    f"and switch it off first"), None
        for w in self.workers_on(server):
            key = self.sub.slot_key(w)
            items = stored(self.vars, key, SLOTS)[0]
            slot = read_slot(key, w, items)
            if not items or (slot is not None and (slot.released or not slot.holder)):
                continue                              # no slot, or one let go: nothing of it can write
            fate, _, why = self.slot_fate(w, slot)    # signs 2 and 3 are `slot_fate`'s "alive": the one rule
            if fate == "alive":
                return f"{server} answers: {why} — stop it and switch the server off first", None
        warning = (f"the resource on {server} was never heard: whether the machine is off cannot be told — decommissioned "
                   f"on the operator's word") if state == "unknown" else None
        return None, warning

    def decommission(self, server: str, by: str, why: str = "") -> dict:
        refusal, warning = self.decommission_refusal(server)
        refusal = self.not_watched_yet(refusal)
        if refusal:
            raise DecommissionRefused(refusal)
        row = {"by": str(by), "at": str(self.wall()), "why": str(why or "")[:500]}
        self.vars.put(DECOMMISSION + server, row)
        return {**row, **({"warning": warning} if warning else {})}

    def withdraw_decommission(self, server: str) -> dict | None:
        """The operator's undo — a request withdrawn, or a server brought back. The row as it was, or None."""
        items, idx = stored(self.vars, DECOMMISSION + server, DECOMMISSIONS)
        if not items:
            return None
        self.vars.delete(DECOMMISSION + server, cas=idx)    # one the store cannot read, too: under TORN
        return {"unread": str(items.error)} if isinstance(items, Unread) else dict(items)

    # The controller's lines in the journal (`journal.py`): a decommission carried out, a slot it released and why, a
    # hung worker. The log only, unless the process is given a resource tree (`vms/__main__._controller_loop`: `ARCHIVE`).
    @property
    def journal(self) -> Journal:
        j = self.__dict__.get("_journal")
        if j is None:
            j = self.__dict__["_journal"] = Journal(None, "controller", self.wall)
        return j

    @journal.setter
    def journal(self, j: Journal) -> None:
        self.__dict__["_journal"] = j

    # The first step of the pass (`SpecController._pass_once`): each request not carried out yet in this subsystem, once
    # its server is silent by all three signs — every slot of the server's workers released (`free_slot`, by CAS), the
    # mark written (`<sub>/decommissioned/<server> {asked_at, at, slots, units, holds}`), the journal told
    # (`server.decommissioned`). A request whose server still answers stands, the sign in `standing`. A mark whose
    # request is gone — the server brought back — goes too: it is this controller's row. `{"decommissioned": [server],
    # "released": [worker], "standing": {server: why}}`.
    def apply_decommissions(self) -> dict:
        done, released, standing = [], [], {}
        asked, marks = self.decommission_requests(), self.decommission_marks()
        for server, row in sorted(asked.items()):
            mark = marks.get(server)
            if mark is not None and str(mark.get("asked_at", "")) == str(row.get("at", "")):
                continue                              # carried out already, for this very request
            refusal, _ = self.decommission_refusal(server)
            if refusal:
                standing[server] = refusal
                continue
            here = self.workers_on(server)
            units = sorted({str(u) for w in here for u in self.assignment(w).units}, key=lambda u: (numeric(u) is None, numeric(u) or 0, u))
            held = self.holds_by()
            holds = sorted({p for w in here for p in held.get(w, [])})
            freed = [w for w in here if self.free_slot(w)]
            self.vars.put(self.sub.decommissioned_key(server),
                          {"asked_at": str(row.get("at", "")), "at": str(self.wall()), "slots": LIST_SEPARATOR.join(freed),
                           "units": LIST_SEPARATOR.join(units), "holds": LIST_SEPARATOR.join(holds)})
            log.warning("%s: server %s decommissioned (by %s): slots %s released, units %s move%s", self.sub.name, server,
                        row.get("by", "?"), ", ".join(freed) or "none", ", ".join(units) or "none",
                        f"; still held: {', '.join(holds)}" if holds else "")
            self.journal.say("server.decommissioned", of=self.sub.name, server=server, by=str(row.get("by", "") or "?"),
                             slots=LIST_SEPARATOR.join(freed), units=LIST_SEPARATOR.join(units),
                             holds=LIST_SEPARATOR.join(holds))
            done.append(server)
            released += freed
        for server in sorted(set(marks) - set(asked)):
            try:
                self.vars.delete(self.sub.decommissioned_key(server))
            except Conflict:
                pass
        return {"decommissioned": done, "released": released, "standing": standing}

    # The second step: every slot whose fate is `release` (`slot_fate`: its server answers and does not list it) released
    # by CAS, with `worker.released_by_controller` in the journal; a hung worker an alarm once an episode (`worker.hung`),
    # one moved past `hung_move_after` another (`worker.hung_moved`). `{"released": {worker: why}, "hung": {worker: why},
    # "hung_moved": [worker]}` — `hung_moved` the workers moved in this episode first. An unsure one past the same limit
    # likewise (`worker.unsure_moved`, `unsure_moved`; the owner's middle way, applied to the doubt).
    #
    # …and the slots left where nobody can judge them (`wait`, `unsure`) while units are assigned to them: `unjudged`
    # `{worker: why}`, an alarm once an episode (`worker.unjudged`), `<sub>_workers_unjudged` and `_units_unjudged` on
    # `/metrics` (the review's twelfth pass, blocker 5: a server's cameras waited on `wait` with no sign anywhere but a
    # line of a lesson). `units_unjudged` — how many units wait so.
    def release_unlisted(self) -> dict:
        released, hung, moved, unjudged, units, doubted = {}, {}, [], {}, 0, {}
        for worker, (fate, server, why) in self.fates().items():
            if fate == "hung":
                hung[worker] = why
            elif fate == "hung_moved":
                moved.append(worker)
            elif fate == "unsure_moved":
                doubted[worker] = why
            elif fate == "release" and self.free_slot(worker):
                released[worker] = why
                log.warning("%s: slot %s released: %s", self.sub.name, worker, why)
                self.journal.say("worker.released_by_controller", of=self.sub.name, worker=worker, server=server, why=why)
            elif fate in ("wait", "unsure") and (n := len(self.assignment(worker).units)):
                unjudged[worker], units = why, units + n
        self._said_unjudged(unjudged)
        return {"released": released, "hung": hung, "hung_moved": self._said_hung(hung, moved), "unjudged": unjudged,
                "units_unjudged": units, "unsure_moved": self._said_unsure_moved(doubted)}

    # A slot nobody can judge, with units on it, is an alarm once an episode; "judged again" goes to the log.
    def _said_unjudged(self, unjudged: dict) -> None:
        said = self.__dict__.setdefault("_unjudged", set())
        for w in sorted(set(unjudged) - said):
            log.error("%s: %s — its units are written by nobody until it is judged, or the operator decommissions its "
                      "server", self.sub.name, unjudged[w])
            self.journal.say("worker.unjudged", ALARM, of=self.sub.name, worker=w, why=unjudged[w])
        for w in sorted(said - set(unjudged)):
            log.warning("%s: %s can be judged again", self.sub.name, w)
        said.clear(); said.update(unjudged)

    # An unsure worker moved past `hung_move_after` is an alarm once an episode, as a hung one (`_said_hung`). Returns the
    # workers moved in THIS episode first.
    def _said_unsure_moved(self, moved: dict) -> list:
        gone = self.__dict__.setdefault("_unsure_moved", set())
        new = sorted(set(moved) - gone)
        for w in new:
            log.error("%s: %s", self.sub.name, moved[w])
            self.journal.say("worker.unsure_moved", ALARM, of=self.sub.name, worker=w, after=self.hung_move_after,
                             why=moved[w])
        gone.clear(); gone.update(moved)
        return new

    # A hung worker is an alarm, said once an episode — the pass looks every 5 s — and so is its move past
    # `hung_move_after`; "not hung any more" goes to the log. Returns the workers moved in THIS episode first.
    def _said_hung(self, hung: dict, moved: list) -> list:
        said, gone = self.__dict__.setdefault("_hung", set()), self.__dict__.setdefault("_hung_moved", set())
        for w in sorted(set(hung) - said):
            log.error("%s: %s", self.sub.name, hung[w])
            self.journal.say("worker.hung", ALARM, of=self.sub.name, worker=w, why=hung[w])
        for w in sorted(said - set(hung) - set(moved)):
            log.warning("%s: %s is not hung any more", self.sub.name, w)
        new = sorted(set(moved) - gone)
        for w in new:
            log.error("%s: %s hung for longer than %g s: its units move anyway", self.sub.name, w, self.hung_move_after)
            self.journal.say("worker.hung_moved", ALARM, of=self.sub.name, worker=w, after=self.hung_move_after)
        said.clear(); said.update(hung)
        gone.clear(); gone.update(moved)
        return new

    # TWO BOXES GIVEN ONE NAME, SAID (the owner's decision of 4 Oct; the product's `sayNameConflicts`). Once an episode —
    # a claimant's box and the time its episode began — that a process of ANOTHER box wants a name this subsystem's
    # instance holds: `worker.name_conflict`, an alarm, and the log. A nobody of the holder's own box has said it in its
    # own journal (`worker.name_taken`). Returns the number of names with any fresh mark — the pass report's
    # `name_conflicts`, `<p>_name_conflicts` on `/metrics`.
    def say_name_conflicts(self) -> int:
        now = self.wall()
        marks = contenders(self.objects, self.sub, now)
        said, before = {}, self.__dict__.setdefault("_names_said", {})
        for name in sorted(marks):
            for m in marks[name]:
                box, holder_box = str(m.get("box") or ""), str(m.get("holder_box") or "")
                if m.get("state") != REFUSED and (not holder_box or box == holder_box):
                    continue                              # a nobody of the holder's own box: its own journal said it
                k = f"{name}/{box}"
                said[k] = m["since"]
                if before.get(k) == m["since"]:
                    continue
                log.error("%s: %s is held by %s (box %s), and a process of box %s (%s, server %s) asks for it too, for "
                          "%.0f s: two machines are given one name", self.sub.name, name, m.get("holder") or "?",
                          holder_box or "not said", box, m.get("hostname") or "?", m.get("server") or "?",
                          now - m["since"])
                self.journal.say("worker.name_conflict", ALARM, of=self.sub.name, worker=name, holder=m.get("holder"),
                                 holder_box=holder_box, contender=m.get("instance"), contender_box=box,
                                 contender_hostname=m.get("hostname"), contender_server=m.get("server"),
                                 since=m["since"])
        before.clear(); before.update(said)
        return len(marks)

    # The places a worker's process holds (`<name>/holds/<place>`, `by` its slot): what freeing its slot leaves held —
    # a local disk is held through a silence on purpose, and one that went with its server is the administrator's to withdraw.
    def holds_of(self, worker: str) -> list[str]:
        return self.holds_by().get(worker, [])

    def holds_by(self) -> dict[str, list[str]]:
        prefix, out = self.sub.name + "/holds/", {}
        for path in self.vars.list(prefix):
            h = read_hold(path, path[len(prefix):], stored(self.vars, path, HOLDS)[0])
            if h is not None and not h.released and h.holder and h.by:
                out.setdefault(h.by, []).append(path[len(prefix):])
        return {w: sorted(p) for w, p in out.items()}


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
        # The process; a name is a slot. Its box in it (`runtime.box`: `BOX_ID`, the machine's id, the hostname) — what
        # a live holder's name may be taken by at a start is read from (`_may_take_by_name`).
        self.instance = instance or f"{runtime.box(os.environ)}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        self.slot_ttl = slot_ttl
        self.slot: Slot | None = None
        self.name = name                          # None until claim_slot(); a fixed name is a slot claimed by that name
        # The name this instance gave up to another (`keep_slot`) while it has not claimed another: fenced till then.
        self.seeking: str | None = None
        # The name this process was STARTED under (`claim_slot(prefer=…)`: its unit's `WORKER_NAME`, a `<ROLE>_NAME`,
        # `SLOT_INDEX`), or None — it took whatever was free. Given, it is that name and no other: fenced off it, it asks
        # for it again and takes nothing else (`_seek_slot`; the owner's decision of 4 Oct).
        self.given: str | None = None
        # The episode this process spends without its given name — `{name, holder, holder_box, since}` — or None while
        # it is somebody (`_name_taken_by`), and when it last wrote its mark (`_contend`, by the clock).
        self.nameless: dict | None = None
        self._contend_at = -1e18
        # The label set this process is a SPARE for (`SPARE_FOR`, `claim_at_start`), or None: it takes an offer of that
        # set and nothing else, then and every time it has to claim again.
        self.spare_for: str | None = None
        # Renewals — of the slot, a lease, a place — the store did not answer, since start: a lease step that added
        # one is followed by another at the loop's next look, not a period later (`VmsWorker.run`, the raft
        # prototype's finding).
        self.unanswered = 0
        self.hold: str | None = None              # the PLACE this worker took, if its subsystem has places to take
        # One renewal or claim of the hold at a time, from whichever thread (`renew_hold`); and when this process
        # first saw each place's row as it is now — the clock a stale hold is judged by (`claim_hold`).
        self._hold_lock = threading.RLock()
        self._hold_seen: dict[str, tuple[int, float]] = {}
        self._slot_seen: dict[str, tuple[int, float]] = {}   # …and each garbled slot row's (`_garbled_stale`)
        # What this process has seen change, and when, by its own clock (`Eyes`; the review's thirteenth pass, blocker 4):
        # whose heartbeat is fresh enough to read a camera from — a holder, a recorder — by change, not by its writer's `ts`
        self.eyes = Eyes(clock, wall)
        self._presence = None                     # the lock this process holds on its server (`present`)
        self._presence_unsaid: str | None = None  # why its name could not be written beside the lock, while it cannot
        # The slot row is renewed from two threads now — the loop, and the stand-in while a step hangs — and one
        # claim, renewal or release of it happens at a time (feedback DD).
        self._slot_lock = threading.RLock()
        self._step: dict | None = None            # the loop's step in progress (`guarded`): name, start, the stand-in's notes
        self._step_lock = threading.Lock()
        self.stand_in_renewals = 0                # renewals the stand-in made for a hung step, since start: in the heartbeat
        self._loop_renewed = clock()              # when the loop last renewed its leases (`renew_leases`)
        self._stood_in_since: float | None = None # what `STAND_IN_FOR` is counted from, while steps are being stood in for
        # The loop's last heartbeat as it wrote it — `(status, extra, ts)` — and when any heartbeat last went (the clock):
        # what the stand-in re-dates for a hung step (`_stand_in_heartbeat`). One write at a time, from either thread.
        self._last_heartbeat: tuple | None = None
        self._heartbeat_at: float | None = None
        self._heartbeat_lock = threading.Lock()
        # The long poll (`longpoll.py`): the wait this worker's loop sleeps in, and the requests it holds at the
        # resources. Neither exists until the process asks for them (`poll_events`) — a worker made without them
        # waits `stop.wait(poll)`, exactly as before.
        self.wake: Wake | None = None
        self.long_poll: LongPoll | None = None
        # The units of the assignment as the last read of it answered, or None when that read did not answer
        # (`assignment`, `take_epoch`); `NEVER_READ` until it is first read.
        self.assigned_now: frozenset[str] | None | object = NEVER_READ

    # -- identity by claim ----------------------------------------------------------
    # Become somebody. Lists the slot rows; with `prefer` (the unit's `WORKER_NAME`, `SLOT_INDEX`) the
    # candidate list is just that name and it is taken by CAS even from a holder that has not lapsed — the
    # supervisor is the authority on which process is the current one, and the old holder finds out on its
    # next `renew_slot` — at a START only, and only from a holder of this box (`_may_take_by_name`); fenced off it,
    # a process so named asks for that name alone, free or lapsed (`_seek_slot`). Without `prefer`, candidates are: lapsed slots first (oldest `until` first — their
    # assignment is waiting), then free (released or never held) slots by number, then a fresh `w-<max+1>`.
    # For each candidate, re-read, skip if not claimable (only in the no-`prefer` case), and `put` a new
    # `Slot(cand, instance, now + slot_ttl, released=False, gen+1)` with `cas=idx`; a `Conflict` means
    # someone took it between read and write, move on. Sets `self.slot` and `self.name`.
    # `test_identity_by_claim_is_a_platform_piece`: two nameless workers get `w-1` and `w-2`; after `w-1`
    # lapses a third gets `w-1` back and its assignment with it; `prefer="w-7"` creates and takes `w-7`.
    SLOT_PREFIX = "w"                             # what a slot this worker has to MAKE is called: `<prefix>-<n>`
    server: str | None = None                     # the server it runs on, when its subsystem says (`_claim_slot` asks it)

    # Whether a held slot's name stays its holder's — the controller's verdict, at the revision this process reads
    # (`published_names`): the rule stays in one place, and so does the judge.
    #
    # It was asked through a controller built here, over this worker's stores (the twelfth pass) — and by the controller's
    # limit, not this process's default (the product's alignment: one limit, one rule, one verdict). Not before the units
    # would move (the twelfth pass, blocker 2): `alive`, `hung` and `unsure` keep the name; `move`, `hung_moved`,
    # `unsure_moved` and `release` give it with the units.
    #
    # …AND `wait` KEEPS IT, as `unsure` does, until the controller's limit (the review's thirteenth pass, blocker 2; the
    # owner's decision of 4 Oct). `wait` gave it "as before the resource said anything": a worker whose `present()` failed
    # (EACCES, ENOSPC on the events tree) and went on working is `wait` — its cameras held back by the controller, and a
    # spare took the name and the cameras with it at +100 s, two writers (`n9_unregistered_hung_name`).
    #
    # …AND BY THE CONTROLLER'S EYES, NOT THIS PROCESS'S (the thirteenth pass, blocker 4). A controller built here at the
    # moment of the claim has seen nothing change: to call a slot lapsed it had to believe the holder's `until`, a clock
    # of another machine — one 50 s behind gave a live holder's name away. The controller that has watched the rows says
    # in its pass report which names are given, at which revision (`Controller.names_given`): taken only there, and only
    # if the row is still that revision. No report, no word on this name, a store that raises: the name stays.
    def _held(self, name: str, rev) -> bool:
        try:
            given = published_names(self.objects, self.sub)
        except Exception as e:                    # noqa: BLE001 — whatever it is, nobody can say the holder is gone
            log.warning("%s: whether %s's holder is gone cannot be told (%s): its name is left alone", self.instance,
                        name, e)
            return True
        return given is None or name not in given or str(given[name]) != str(rev)

    # Whether `holder` ran on THIS box, by both names (`runtime.box_of`). A name that says no box is not this box's: whose
    # machine it is cannot be read from it (the review's thirteenth pass, blocker 3 — an `INSTANCE_ID` took always).
    def _on_this_box(self, holder: str) -> bool:
        here, there = runtime.box_of(self.instance), runtime.box_of(holder)
        return here is not None and there is not None and here == there

    # A garbled slot row is stale when this process has watched it stand still — the same revision — for the slot's term
    # and `HOLD_SKEW`, by its own monotonic clock (`_hold_stale`'s rule, for the row nobody can read).
    def _garbled_stale(self, cand: str, idx) -> bool:
        seen, now = self._slot_seen.get(cand), self.clock()
        if seen is None or seen[0] != idx:
            self._slot_seen[cand] = (idx, now)
            return False
        return now - seen[1] >= self.slot_ttl + self.HOLD_SKEW

    def claim_slot(self, prefer: str | None = None, retries: int = 50, spare_for: str | None = None) -> str:
        """Become somebody. With `prefer` (whatever `runtime.slot` made of
        SLOT_INDEX or a <ROLE>_NAME) take that slot, by CAS, even from a holder
        that has not lapsed — the runtime is the authority on which process is
        the current one — unless that holder runs on another box (`NameOnAnotherBox`),
        and the old holder finds out on its next renewal; that name is then this
        process's for good (`given`: fenced off it, it asks for it again and for
        nothing else, `_seek_slot`). Without it, take a
        lapsed slot — its assignment is waiting — before an unused number. Holding is renewed by `renew_slot`; losing it fences the
        instance. The controller never hands names out; a process takes one.
        A SPARE (`spare_for`, or `self.spare_for` once said) takes only an offer of that label set, and `NoOffer` when
        there is none: no name, however it was started (`_claim_offer`)."""
        with self._slot_lock:
            if spare_for is not None:
                self.spare_for = label_set(spare_for)
            if self.spare_for is not None:
                return self._claim_offer(retries)
            if prefer is not None:
                self.given = prefer                   # named by its unit: that name and no other (`_seek_slot`)
            return self._claim_slot(prefer, retries)

    # What a process does at its start: claim, as `claim_slot` — or, started as a spare (`SPARE_FOR` in `env`), take an
    # offer of its set, and with none be nobody (`seeking`): no slot, no heartbeat, nothing assigned, nothing taken.
    # Every lease step looks for an offer again (`_seek_slot`). Returns the name, or None while it waits.
    def claim_at_start(self, prefer: str | None, env: dict) -> str | None:
        from . import runtime
        spare = runtime.spare_for(env)
        if spare is None:
            return self.claim_slot(prefer=prefer)
        try:
            return self.claim_slot(spare_for=spare)
        except NoOffer as e:
            self.seeking = ""                         # nobody: no name was ever this instance's
            log.info("%s: %s; waiting, holding nothing", self.instance, e)
            return None

    # A spare with no offer taken yet — nobody, waiting (`claim_at_start`).
    def waiting_for_offer(self) -> bool:
        return self.spare_for is not None and self.slot is None and self.seeking is not None

    # THE SPARE'S CLAIM: an offer of its set, nothing else (the product's c62e236). The offers are listed, the lowest
    # number first, and the first still an untaken offer of `spare_for` when re-read is written as this instance's, by
    # CAS on the revision read — `offer` and `offered_at` kept, `taken_at` now. Two spares that read one offer: one
    # write lands, the other conflicts, looks again and finds none — `NoOffer`, and it waits.
    def _claim_offer(self, retries: int) -> str:
        if self.server and stored(self.vars, DECOMMISSION + self.server, DECOMMISSIONS)[0]:
            raise ServerDecommissioned(f"server {self.server} is decommissioned: no slot for a process on it until the "
                                       f"operator brings it back (DELETE /servers/{self.server}/decommission)")
        prefix = self.sub.name + "/slots/"
        for attempt in range(retries):
            if attempt:
                cas_pause(attempt - 1)
            offers = []
            for path in self.vars.list(prefix):
                name = path[len(prefix):]
                items, idx = stored(self.vars, path, SLOTS)
                s = read_slot(path, name, items)
                if s is not None and s.offered() and label_set(s.offer) == self.spare_for:
                    offers.append((slot_number(name), name, s, idx))
            if not offers:
                break
            for _, cand, cur, idx in sorted(offers, key=lambda o: (o[0], o[1])):
                now = self.wall()
                new = Slot(cand, self.instance, now + self.slot_ttl, False, cur.gen + 1, "", cur.offer, cur.offered_at, now,
                           self.server or "")
                try:
                    self.vars.put(prefix + cand, new.to_items(), cas=idx)
                except Conflict:
                    continue                                   # another spare took it between the read and the write
                self.slot, self.name = new, cand
                log.warning("%s: a spare for labels '%s' took offer %s", self.instance, self.spare_for, cand)
                return cand
        raise NoOffer(f"a spare for labels '{self.spare_for}', and no offer of them to take")

    # `steal`: whether `prefer` is taken from a live holder. At a process's start, yes — the unit says which process is
    # the current one — unless that holder runs on ANOTHER box (`_may_take_by_name`). When a process named by its unit
    # and fenced off its name asks for it again (`_seek_slot`), no: a live holder keeps it, and the answer is `_NameTaken`.
    def _claim_slot(self, prefer: str | None, retries: int, steal: bool = True) -> str:
        # A process on a decommissioned server is given no name (the product's rule): its slot would be released again on
        # the next pass, and whatever it took would move. Said by name, until the operator brings the server back.
        if self.server and stored(self.vars, DECOMMISSION + self.server, DECOMMISSIONS)[0]:
            raise ServerDecommissioned(f"server {self.server} is decommissioned: no slot for a process on it until the "
                                       f"operator brings it back (DELETE /servers/{self.server}/decommission)")
        prefix = self.sub.name + "/slots/"
        now = self.wall()
        for attempt in range(retries):
            if attempt:
                cas_pause(attempt - 1)               # every candidate was taken under us: not the same race again at once
            names = [p[len(prefix):] for p in self.vars.list(prefix)]
            # A row that does not parse is no candidate (`read_slot`): skipped, and its number is still counted below,
            # so a slot made new never takes its name — until THIS process has watched it stand still, the same
            # revision, for a slot's whole term and `HOLD_SKEW` on top (`_garbled_stale`; the product's cross-check of
            # the eleventh pass): read bare it was nobody's for ever, and the units assigned to its name with it. A
            # holder that renews writes its row whole every step (`_own_slot`), so a row that stands still that long has
            # nobody behind it.
            # Each through `stored` (the review's twelfth pass, major 19): one torn slot file raised `Garbled` out of the
            # bare read — no process of the subsystem started, by name or without, for as long as the file stayed torn.
            # A row the store cannot read is a garbled row like any other: no candidate until it stands still a term.
            rows = {n: stored(self.vars, prefix + n, SLOTS) for n in names}
            known = {n: s for n in names if (s := read_slot(prefix + n, n, rows[n][0])) is not None}
            if prefer is not None:
                order = [prefer]
            else:
                # …but not the name of a worker whose units the controller would not move yet (`Controller.slot_fate`,
                # the one rule; `_held`): hung, within the margin, or not known — a spare taking its name would take its
                # units with it, the second holder the controller refuses to make by a move. Which names those are is
                # the controller's word at the revision read (the thirteenth pass, blocker 4), not this process's reading
                # of a holder's `until`: a held row is a candidate where the controller gives its name, and only there.
                lapsed = sorted((n for n, s in known.items() if self._given(n, s, rows[n][1])),
                                key=lambda n: known[n].until)
                free = sorted((n for n, s in known.items() if self._free(s)), key=slot_number)
                # …and a garbled row stood still for a term, the same way (the review's twelfth pass, major 4): it stands
                # still when its holder is hung, too, and was taken past `slot_fate` with the hung worker's units.
                free += sorted((n for n in names if n not in known and rows[n][0] and self._garbled_stale(n, rows[n][1])
                                and not self._held(n, rows[n][1])), key=slot_number)
                # A NEW slot is named after the kind of worker taking it (`SLOT_PREFIX`: `r` a recorder, `g` a
                # gateway, `a` an evaluator — the letters a process given a name already had), not `w-` for
                # everybody: a recorder that had to make a slot looked like a camera worker in every list, every
                # heartbeat and every log line (the product's box, feedback BU). Slots that exist keep their
                # names; a lapsed or free one is still taken before a new one is made.
                nxt = f"{self.SLOT_PREFIX}-{max([slot_number(n) for n in names] + [0]) + 1}"
                order = lapsed + free + [nxt]
            for cand in order:
                items, idx = stored(self.vars, prefix + cand, SLOTS)
                cur = read_slot(prefix + cand, cand, items)
                if cur is None:
                    if prefer is None and not (items and self._garbled_stale(cand, idx) and not self._held(cand, idx)):
                        continue                               # garbled, and not watched standing still for a term — or held
                    said = items if isinstance(items, dict) else {}
                    holder = str(said.get("holder") or "")    # whose it is, when that much of the row still reads
                    if not steal and items and (not self._garbled_stale(cand, idx) or self._held(cand, idx)):
                        raise _NameTaken(cand, holder, 0.0)    # whose it is cannot be read: asked again, taken once it stands still
                    if steal and items and holder != self.instance and not self._on_this_box(holder) \
                            and self._held(cand, idx):
                        # …and at a start, by the same rule as a row that reads (the review's thirteenth pass, blocker 3):
                        # a torn row of a holder on another box, or of a name that says none, is taken where the
                        # controller gives the name, and not before
                        refused = self._may_take_by_name(cand, holder, held=True)
                        self._contend(cand, holder, REFUSED)
                        raise refused
                    # The runtime named this slot, or nobody has touched its garbled row for a term: taken, written whole
                    # again — under the generation the row still says, if it says one, so a generation is not handed out
                    # twice through a torn row.
                    cur = Slot(cand, gen=numeric(str(said.get("gen", ""))) or 0)
                if prefer is None and not (self._free(cur) or self._given(cand, cur, idx)):
                    continue                                   # a preferred slot is taken regardless: the scheduler
                                                               # said this index is mine; the old holder fences on renewal
                if prefer is not None and cur.holder and cur.holder != self.instance and not cur.released:
                    if not steal and self._held(cand, idx):
                        raise _NameTaken(cand, cur.holder, cur.until)   # live, or lapsed with its process hung: its holder's
                    # AT A START (the owner's decision of 4 Oct; the review's thirteenth pass, blocker 3): from a holder
                    # of THIS box, always — the unit is the authority on which process is the current one. From any other
                    # holder — another box, or a name that says no box — only where the controller gives the name (`_held`):
                    # the slot's lapse was read by `until` alone, and a process named on box B took a hung worker's name
                    # and its cameras from box A at +50…+600 s, two writers (`n5_named_takes_hung`).
                    if steal and not self._on_this_box(cur.holder) and self._held(cand, idx):
                        refused = self._may_take_by_name(cand, cur.holder, held=cur.claimable(now))
                        self._contend(cand, cur.holder, REFUSED)   # seen on /servers, not only in this box's log
                        raise refused
                new = Slot(cand, self.instance, now + self.slot_ttl, False, cur.gen + 1, server=self.server or "")
                try:
                    self.vars.put(prefix + cand, new.to_items(), cas=idx)
                except Conflict:
                    continue                                   # somebody took it between the read and the write
                self._slot_seen.pop(cand, None)
                self.slot, self.name = new, cand
                if prefer is not None:
                    self._uncontend(cand)                      # this box asks for the name no more: it has it
                return cand
        raise RuntimeError(f"{self.instance}: could not claim a slot in {retries} tries")

    # MAY A LIVE HOLDER'S NAME BE TAKEN AT A START (the owner's decision of 4 Oct; the product's `mayTakeByName`). Taking
    # a named slot from a live holder is how a unit restarted after kill -9 gets its name back without waiting out the
    # previous instance's slot. But the unit that says so is THIS box's, and the units name their processes from the
    # short hostname (`w-%l-1`): two machines with one hostname computed one name, and each restart of one took the
    # other's — fenced it — and the other's restart took it back, a ping-pong only the two boxes' own logs saw. So the
    # take stands only where its reason does: the holder ran on this box; or the holder's name says no box, or this
    # instance's does not (an `INSTANCE_ID`, an allocation's id: a scheduler names them and moves an index between nodes
    # — there the scheduler stays the authority). A live holder on another box is left alone: the refusal, in words.
    #
    # …AND A NAME THAT SAYS NO BOX IS NOT THIS BOX'S (the review's thirteenth pass, blocker 3; the product closed the same):
    # "the scheduler stays the authority" let an `INSTANCE_ID` take a live holder's name always — whichever node it ran
    # on. Now a holder is replaced by name only from its own box; any other holder keeps its name until the controller
    # gives it (`Worker._held`) — a scheduler that moved an index waits out the old holder's slot, which a dead node's
    # holder gives in a slot's term. `held`: the holder stopped renewing, but the controller has not given the name.
    def _may_take_by_name(self, slot: str, holder: str, held: bool = False) -> "NameOnAnotherBox | None":
        if self._on_this_box(holder):
            return None
        here, there = runtime.box_of(self.instance), runtime.box_of(holder)
        return NameOnAnotherBox(slot, holder, there or "", socket.gethostname(), here or runtime.box(os.environ),
                                getattr(self, "NAME_ENV", ""), held)

    # A slot nobody holds: released, or never held — not an offer, which is a spare's (`_claim_offer`).
    @staticmethod
    def _free(s: "Slot") -> bool:
        return not s.offered() and (s.released or not s.holder)

    # A held slot whose name the controller gives, at the revision read (`_held`).
    def _given(self, name: str, s: "Slot", rev) -> bool:
        return bool(s.holder) and not s.released and not self._held(name, rev)

    # The box this instance runs on, as its name says it — this machine's when its name says none.
    def _box(self) -> str:
        return runtime.box_of(self.instance) or runtime.box(os.environ)

    # This process's mark on a name another instance holds (`<sub>/contenders/<name>/<box>`): written over, never added
    # to. The episode's start is kept from a fresh mark of the same state — a refused process is a new process at each
    # restart, and its episode is its first refusal. A store that does not take it: this box's log says it, as before.
    def _contend(self, name: str, holder: str, state: str) -> None:
        if self.objects is None:
            return
        now, key = self.wall(), self.sub.contender_key(name, self._box())
        since = now
        if state == NAMELESS and self.nameless is not None:
            since = self.nameless["since"]
        else:
            prev = _read_contender(self.objects, key)
            if prev is not None and prev.get("state") == state and now - prev["at"] <= CONTENDER_FRESH:
                since = prev["since"]
        row = {"name": name, "state": state, "box": self._box(), "hostname": socket.gethostname(),
               "server": self.server or "", "instance": self.instance, "holder": holder,
               "holder_box": runtime.box_of(holder) or "", "since": since, "at": now}
        try:
            self.objects.put(key, json.dumps(row).encode())
        except Exception as e:                            # noqa: BLE001 — the claim is said; a mark nobody took is a log line
            log.warning("%s: its claim to %s/%s was not written down (%s): only this log says it", self.instance,
                        self.sub.name, name, e)

    # …removed once this box holds the name.
    def _uncontend(self, name: str) -> None:
        if self.objects is None:
            return
        try:
            key = self.sub.contender_key(name, self._box())
            if self.objects.get(key):
                self.objects.delete(key)
        except Exception as e:                            # noqa: BLE001
            log.warning("%s: its old claim to %s/%s stays (%s): read as stale in %g s", self.instance, self.sub.name,
                        name, e, CONTENDER_FRESH)

    # The worker's own lines in the journal (`journal.py`): `worker.name_taken`, `worker.name_back`. Into its server's
    # resource tree when it has one (`archive_root`), else the log only — as the controller's.
    @property
    def journal(self) -> Journal:
        j = self.__dict__.get("_journal")
        if j is None:
            j = self.__dict__["_journal"] = Journal(getattr(self, "archive_root", None), f"{self.sub.name}worker", self.wall)
        return j

    @journal.setter
    def journal(self, j: Journal) -> None:
        self.__dict__["_journal"] = j

    # NOBODY, WAITING FOR ITS OWN NAME: said once an episode — who holds the name, on which box — and the mark written
    # as its pulse while its heartbeat is the holder's.
    def _name_taken_by(self, e: "_NameTaken") -> None:
        now = self.wall()
        holder_box = runtime.box_of(e.holder) or ""
        if self.nameless is None:
            self.nameless = {"name": e.slot, "holder": e.holder, "holder_box": holder_box, "since": now}
            log.error("%s: its name %s/%s is held by %s (box %s) — another process started under the same name took it. "
                      "This one is nobody now: it holds nothing, and takes its name back when that is free; it takes no "
                      "other", self.instance, self.sub.name, e.slot, e.holder or "?", holder_box or "not said")
            self.journal.say("worker.name_taken", ALARM, of=self.sub.name, worker=e.slot, holder=e.holder,
                             holder_box=holder_box, holder_until=e.until, instance=self.instance, box=self._box(),
                             server=self.server or "", since=now)
            self._contend_at = -1e18
        self.nameless.update(holder=e.holder, holder_box=holder_box)
        if self.clock() - self._contend_at >= CONTEND_EVERY:
            self._contend(e.slot, e.holder, NAMELESS)
            self._contend_at = self.clock()

    # …and its name its own again.
    def _name_back(self) -> None:
        if self.nameless is None:
            return
        n, now = self.nameless, self.wall()
        self.nameless = None
        log.warning("%s: its name %s/%s is its own again, after %.0f s of being nobody", self.instance, self.sub.name,
                    n["name"], now - n["since"])
        self.journal.say("worker.name_back", of=self.sub.name, worker=n["name"], instance=self.instance, box=self._box(),
                         server=self.server or "", since=n["since"], nameless_s=round(now - n["since"]))

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
        items, idx = stored(self.vars, key, SLOTS)        # one the store cannot read, the same (major 19's sibling)
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
            self.assigned_now = None              # what it read was the list of the name given up (`take_epoch`)
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
        if cur.holder != self.instance or cur.released:          # released: the controller freed it (`free_slot`); a late renewal does not take it back
            return False
        # …an offer's three fields kept: until its worker is heard, the controller counts it as one on its way
        new = Slot(self.name, self.instance, self.wall() + self.slot_ttl, False, cur.gen, "", cur.offer, cur.offered_at,
                   cur.taken_at, self.server or "")
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
            rows = {c: stored(self.vars, self.sub.hold_key(c), HOLDS) for c in candidates}   # torn: no candidate (major 19's sibling)
            # A row that does not parse is no candidate, and stops nobody from taking another (`read_hold`).
            held = {c: read_hold(self.sub.hold_key(c), c, rows[c][0]) for c in candidates}
            candidates = [c for c in candidates if held[c] is not None]
            # Only while the slot IS this instance's: the instance systemd replaced has the same name, and must not
            # take the place back from its successor on its way out. The slot is read only when a hold names it.
            mine = [c for c in candidates if self.name and held[c].by == self.name]
            slot = read_slot(self.sub.slot_key(self.name), self.name, stored(self.vars, self.sub.slot_key(self.name), SLOTS)[0]) if mine else None
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
                again = read_hold(key, self.hold, stored(self.vars, key, HOLDS)[0])
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
        items, idx = stored(self.vars, key, HOLDS)
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
    #
    # What it answered is kept (`assigned_now`) for `take_epoch`; a read that did not answer clears it.
    def assignment(self) -> Assignment:
        if self.seeking is not None:
            return Assignment(self.name, [])      # the row under that name is the other instance's now (`keep_slot`)
        key = self.sub.assignment(self.name)
        try:
            items, _ = stored(self.vars, key, ASSIGNMENTS)  # one the store cannot read: no unit, counted (the eleventh review)
        except OSError:
            self.assigned_now = None
            raise
        a = read_assignment(key, self.name, items)
        self.assigned_now = frozenset(str(u) for u in a.units)
        return a

    # Called when the worker starts a unit: `next_epoch` on `<name>/epoch/<unit>`, record it in `epochs`,
    # and open a `Lease` on it. A second worker starting the same unit gets the next number, and the first
    # one's lease fences on renewal.
    def take_epoch(self, unit: str) -> int:
        """Called when the worker STARTS a unit: a new epoch, by CAS, and a
        lease on it. A second worker starting the same unit gets the next
        number, and the first one's lease will fence on renewal."""
        if self.seeking is not None:
            raise NoSlot(f"{self.instance} gave slot {self.seeking} up and holds no other: no epoch for {unit}")
        # …NOR FROM A STEP NOBODY STOOD IN FOR (the product's cross-check of the review's twelfth pass). A loop stuck in a
        # step past `STAND_IN_FOR` let its units go — and when the step came back it went on with the assignment it had
        # read before it hung: the next camera of the list was started, its epoch taken by CAS over the worker the units
        # had moved to meanwhile, which then fenced — a second writer made by a process that had been absent for minutes.
        # Nothing new is taken in such a step; the loop's next lease step and pass look again at what is its own.
        if self.step_abandoned():
            raise NoSlot(f"{self.name}: this step outlived its stand-in ({self.STAND_IN_FOR:g} s) and its units may be "
                         f"another's now: no epoch for {unit} until the loop has looked again")
        # …NOR ON AN ASSIGNMENT NOT READ NOW (the product's cross-check, after the twelfth review). The read of the
        # assignment failed — one 503 — and the pass went on with the list read before; a unit moved away meanwhile
        # was still on it, its lease had just been fenced, the reconciler started it again, and the epoch CAS, which
        # the store DID answer, fenced the worker the unit had moved to. A new epoch is taken only for a unit of the
        # assignment whose read answered last; what is not known to be this worker's is not taken from anybody. A
        # worker that holds the unit's epoch already goes on under it (`VmsWorker._actuate`, feedback BK).
        if self.assigned_now is not NEVER_READ and (self.assigned_now is None or str(unit) not in self.assigned_now):
            raise NotReadThisPass(
                f"{self.name}: {unit} is not in the assignment read last" if self.assigned_now is not None else
                f"{self.name}: its assignment did not answer, and {unit} may be another's now: no new epoch for it "
                f"until the assignment is read again")
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
            self.unanswered += 1
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
    #
    # …AND A PROCESS NAMED BY ITS UNIT ASKS FOR THAT NAME ONLY (the owner's decision of 4 Oct; the product's `RejoinSlot`).
    # It took whatever was free (`claim_slot()`), and a unit-named process fenced off its name became `w-2`: a second
    # worker on its server, given units by the controller, under no unit — and its unit's own process held the name
    # beside it. Now it takes its given name when that is free or lapsed (`steal=False`), and while another instance
    # holds it live it is nobody (`_name_taken_by`) — said once, its mark written, asked again every step.
    def _seek_slot(self) -> bool:
        was = self.seeking
        try:
            self.schema_seen = check_schema(self.vars, getattr(self, "schema_seen", None))   # nobody to be on a store past this build
            if self.given is not None and self.spare_for is None:
                with self._slot_lock:
                    self._claim_slot(self.given, 50, steal=False)
            else:
                self.claim_slot()
        except NoOffer:
            return False                          # a spare with no offer of its set: it waits, as it said at its start
        except _NameTaken as e:
            self._name_taken_by(e)
            return False
        except Exception as e:                    # noqa: BLE001
            log.warning("%s: gave slot %s up and no other could be claimed (%s): nobody, taking nothing; trying again "
                        "on the next step", self.instance, was, e)
            return False
        self.seeking = None
        self._name_back()
        if was:                                   # a spare that never had a name has said what it took (`_claim_offer`)
            log.warning("%s: gave slot %s up, its units let go; going on as %s", self.instance, was, self.name)
        return True

    def renew_leases(self) -> list[str]:
        """Returns the units whose lease was lost — fenced or expired."""
        self._loop_renewed = self.clock()         # what the stand-in measures a hung step's danger from
        lost = []
        for u, lease in list(self.leases.items()):
            errors = lease.store_errors
            if not lease.renew():
                lost.append(u)
            if lease.store_errors > errors:
                self.unanswered += 1              # the store did not answer this one (`unanswered`)
        return lost

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

    # Whether the loop's step in progress is one the stand-in stopped standing in for (`stand_in_once`: past
    # `STAND_IN_FOR`, or the slot found another's) — its units went, and what it read before it hung is not its own.
    def step_abandoned(self) -> bool:
        with self._step_lock:
            return bool(self._step and self._step.get("done"))

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
            self._stand_in_heartbeat(mark, age)       # between two renewals: the heartbeat, if it is due
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
        self._stand_in_heartbeat(mark, age)
        return True

    # …AND THE HEARTBEAT (the scaling pass after the eighth review). The stand-in renewed the leases and the slot and wrote
    # no heartbeat: 45 s into a hung step the controller and the recorders judged the holder dead — the recorders lost the
    # fan-out they record from, the controller moved its units — while the stand-in held its leases for five minutes. So
    # while it stands in, it writes one whenever the last is `STAND_IN_HEARTBEAT` old, and only after it has confirmed the
    # slot is this instance's in this step (`mark["last"]`).
    #
    # WHAT IT MAY SAY. Nothing it has not seen: it does not ask the subsystem for a status — that is the loop's state,
    # mid-step on the loop's thread, and computing it here would be a second writer of it — and it does not send an empty
    # one, which would tell every reader the units have no holder, the very failure this is for. It says the LOOP'S LAST
    # heartbeat again, as the loop wrote it, with a new `ts` and `stood_in`: the step that hangs, for how long, and
    # `as_of` — the `ts` of the heartbeat whose status this is. A reader that needs only "alive, and where the fan-out
    # is" has it; one that wants to know how fresh the status is reads `as_of`. A pipeline that died under the hung step
    # is in that status as running until the loop comes back — for at most `STAND_IN_FOR`, after which the stand-in
    # stops, the heartbeat goes stale too, and the units honestly go.
    STAND_IN_HEARTBEAT = 10.0     # the loop's heartbeat rhythm (`VmsWorker.run`)

    def _stand_in_heartbeat(self, mark: dict, age: float) -> bool:
        if self._last_heartbeat is None or self.seeking is not None or not self._heartbeat_lock.acquire(blocking=False):
            return False                              # nothing to say again, nobody to say it as, or the loop is writing
        try:
            if self._heartbeat_at is not None and self.clock() - self._heartbeat_at < self.STAND_IN_HEARTBEAT:
                return False
            status, extra, ts = self._last_heartbeat
            said = {**extra, "stand_in_renewals": self.stand_in_renewals,
                    "stood_in": {"step": mark["name"], "for": round(age, 1), "as_of": ts}}
            self.objects.put(self.sub.heartbeat_key(self.name), Heartbeat(self.name, self.wall(), status, said).to_bytes())
            self._heartbeat_at = self.clock()
        except OSError:
            return False                              # the store is what hangs: the leases judge that themselves
        finally:
            self._heartbeat_lock.release()
        if not mark.get("heartbeat_said"):
            mark["heartbeat_said"] = True
            log.warning("%s: step %s has run %.0f s; its last heartbeat (of %.0f s ago) said again for it", self.name,
                        mark["name"], age, self.wall() - ts)
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
            items, idx = stored(self.vars, key, HOLDS)
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
    #
    # -- registered with its server: the process lives (the owner's decision, 3 Oct, on the review's eleventh pass) ---
    # Whether a worker that neither renews nor speaks is dead or hung is a fact about its SERVER, and the server's
    # resource is there to see it. Each worker holds a lock on a file in the resource's tree for as long as its process
    # lives (`<root>/.workers/<instance>.lock`, `flock` — the kernel lets go when the process ends, however it ends) and
    # writes beside it what it is called (`.json`). The resource says in its heartbeat which workers it has (`workers`)
    # and whose locks are still held (`running`; `resource.workers_here`), and the controller reads both (`slot_fate`):
    # running, it is hung and keeps its units; there and not running, it is dead and its units move; not there at all,
    # the server does not run it and its slot is released. `present` in this worker's heartbeat says it registered, so one that
    # did not (an older build, a bench) is never taken for dead by not being listed. The lock is touched at every
    # heartbeat: how long a dead registration has said nothing is the file's own age.
    def present(self, root: str) -> bool:
        """Register with the resource whose tree is `root`. False (and said) when the tree cannot be written."""
        import fcntl
        d = os.path.join(root, PRESENCE)
        try:
            os.makedirs(d, exist_ok=True)
            f = open(os.path.join(d, presence_name(self.instance) + ".lock"), "a")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                f.close()
                raise
        except OSError as e:
            log.warning("%s: not registered with the resource in %s (%s): a silence of this worker will be taken for "
                        "a hang, never for its end", self.name or self.instance, root, e)
            return False
        self._presence = (f, d, None)
        self._say_present()
        return True

    # Let go of the lock — what the end of the process does by itself, and all it does: the registration stays, and
    # says the server runs this worker, whose process is not alive. A test ends a worker this way.
    def absent(self) -> None:
        if self._presence is not None:
            f, self._presence = self._presence[0], None
            f.close()

    # What it is called, beside its lock: written again when that changes (a name claimed, or given up — "" then: the
    # name is another instance's). Atomically, so the resource never reads half of it.
    def _say_present(self) -> None:
        f, d, said = self._presence
        with contextlib.suppress(OSError):
            os.utime(f.name)                      # it still lives: what `PRESENCE_KEPT` is counted from once it does not
        name = "" if self.seeking is not None else (self.name or "")
        if said == name:
            return
        path = os.path.join(d, presence_name(self.instance) + ".json")
        try:
            with open(path + ".tmp", "w") as out:
                json.dump({"sub": self.sub.name, "name": name, "pid": os.getpid()}, out)
            os.replace(path + ".tmp", path)
        except OSError as e:
            # …SAID, NOT ONLY LOGGED (the review's twelfth pass, blocker 3): ENOSPC on the archive's volume left the
            # `.json` absent or naming nobody while the lock was held — and a resource that answers read the worker as
            # "not listed", its slot released under a process that still wrote. Now the heartbeat says so
            # (`presence_unsaid`, which `slot_fate` takes for "unsure": its name and units stay up to the hung limit,
            # and `/metrics` counts it), the log says it once an episode, and every heartbeat tries again (`said` is not
            # moved on).
            if not getattr(self, "_presence_unsaid", None):
                log.error("%s: what it is called could not be written beside its lock (%s): until it is, its silence is "
                          "not taken for its end — tried again with every heartbeat", self.name or self.instance, e)
            self._presence_unsaid = f"{os.path.basename(path)}: {e.strerror or e}"
            return
        if getattr(self, "_presence_unsaid", None):
            log.warning("%s: what it is called is written beside its lock again", self.name or self.instance)
        self._presence_unsaid = None
        self._presence = (f, d, name)

    def heartbeat(self, status: list[dict], **extra) -> None:
        if self._presence is not None:
            self._say_present()
            extra.setdefault("present", True)     # registered with its server's resource (`present`)
            if getattr(self, "_presence_unsaid", None):
                extra.setdefault("presence_unsaid", self._presence_unsaid)   # …but its name is not beside its lock
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
        with self._heartbeat_lock:                # …and what a stand-in says again for a hung step (`_stand_in_heartbeat`)
            ts = self.wall()
            self.objects.put(self.sub.heartbeat_key(self.name), Heartbeat(self.name, ts, status, extra).to_bytes())
            self._last_heartbeat, self._heartbeat_at = (status, extra, ts), self.clock()

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
