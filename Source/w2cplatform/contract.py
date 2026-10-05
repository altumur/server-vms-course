"""The subsystem contract — what the platform knows about any subsystem,
and it is all of this:

    a config prefix        <name>/*                      writable by the controller only
    assignment rows        <name>/workers/<worker>       what each worker should run
    a heartbeat object     <name>/heartbeats/<worker>    {ts, status: [...]} — the worker's own report
    an epoch prefix        <name>/epoch/<unit>           fencing tokens the workers take by CAS
    an event log           <resource>/<name>/<unit>/e<epoch>/<start>Z.events.jsonl   (w2cplatform.events)
                                                         what a worker observed about a unit it holds the epoch for;
                                                         on its server's resource, under the subsystem's prefix
    a slot prefix          <name>/slots/<worker>         identity by claim: a worker's name is a slot it
                                                         holds by CAS and renews; a replacement process
                                                         takes the lapsed slot and inherits its assignment

Who decides how many workers there are: not the controller. The service
manager runs them (`systemctl start <name>worker@…` on a box, a unit per role on
every server of a cluster), and a host's spares script starts a spare where the
controller offers a slot (`<sub>_workers_needed`, `offer_spares`). The platform's
part is to give interchangeable processes stable names — the slots — so that
assignments survive a restart. A slot is released on an orderly stop; the
controller then redistributes what the slot held. A slot that merely lapses (a
crash) is left alone: the service manager brings the process back, and it claims
the same slot.

`Controller` and `Worker` are the two base classes. The platform never
imports anything from a subsystem; the other subsystems prove the
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
# `epoch.py` and `longpoll.py` (a loop's early pass) and nothing else. `spec.SpecController` extends `Controller`; each
# subsystem's worker extends `Worker`. The file's own docstring settles who
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
# - The tests enforce the boundary: `tests/test_boundary.py` asserts no import from a subsystem and none of a
#   subsystem's words in this file, and runs the platform on a test subsystem alone through the same
#   `Controller`/`Worker`.
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
# `w-1`), and a grant is written before any process runs — a rights file is static text — so "may write its own
# heartbeat and nothing else" could not be written down: the narrowest expressible grant was the whole subsystem,
# which also covers the snapshot shards М12 reads and the blobs the workers trust.
#
# Moving the worker to the LAST segment makes it expressible. Three sibling directories under the
# subsystem, one writer each: `heartbeats/` the workers, `snapshot/` the controller, `blobs/` the console.
# A prefix that cannot be bounded by a grant is a layout problem, not a missing feature of the rights.
HEARTBEATS = "heartbeats"
REQUESTS = "requests"      # `<name>/requests/<id>`: bounded work an operator asked for, written by the console
CONTROLLER_PASS = "controller/pass"   # `<name>/controller/pass`: the controller's report on its last pass (`SpecController.pass_once`)
CONTENDERS = "contenders"  # `<name>/contenders/<slot>/<box>`: a process that wants a name another instance holds (`Worker._contend`)
USED = "used"              # `<name>/used/<place>`: a place this subsystem's workers have opened, and where (`Subsystem.used_key`)
COMMANDS = "commands"      # `<name>/commands/<id>`: a worker's mark before it performs a request, create-only (`Worker._mark`)


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


def contenders(objects, sub: "Subsystem", now: float, eyes: "Eyes | None" = None) -> dict[str, list[dict]]:
    """The fresh marks of a subsystem, by name, ordered by box: the processes that want a name another instance holds
    and asked within `CONTENDER_FRESH` of now — of the reader's clock where it has `eyes`: the mark CHANGED within it (the
    product's r29-writers2; `at` is the claimant's clock, and a claimant an hour ahead that stopped asking was a conflict
    for an hour). A mark that does not read is skipped; a store that does not answer, none."""
    out: dict[str, list[dict]] = {}
    try:
        keys = objects.list(sub.contenders_prefix())
    except OSError:
        return out
    for key in keys:
        row = _read_contender(objects, key)
        if row is not None and (eyes.fresh(key, row["at"], CONTENDER_FRESH) if eyes is not None
                                else now - row["at"] <= CONTENDER_FRESH):
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
# writes is that clock's, and is read for what a page shows — `until` an hour ahead held a dead server's units for an
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
            # …by the token every reader of a heartbeat gives the same eyes (`Heartbeat.token`, `(ts, crc)`): a bare `ts`
            # here and `(ts, crc)` in `/servers` under one key read as a change at every turn — a dead worker "fresh"
            # for as long as a page asked both (found beside the product's r29-writers2)
            import zlib
            live = (eyes.fresh(key, (d["ts"], zlib.crc32(raw)), lost_after, d["ts"], sub) if eyes is not None
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
# `ensure_reach`, `redistribute`, `ensure_home` (a new unit not placed, a dead worker's units not moved); a `5` among
# strings raised in every `sorted`. A worker's or a resource's `worker` and `server` are non-empty strings, or the
# heartbeat does not parse: that heartbeat's trouble, skipped and counted like any other.
NAMES = ("worker", "server")


def _named(hb) -> None:
    said = {"worker": hb.worker, **hb.extra} if isinstance(hb, Heartbeat) else hb if isinstance(hb, dict) else {}
    for field in NAMES:
        if field in said and not (isinstance(said[field], str) and said[field]):
            raise TypeError(f"`{field}` is a name, not {said[field]!r:.40}")


# …AND THE NAME IT SAYS IS THE NAME OF ITS KEY (the product's r30, defect A). Readers key a heartbeat by the name in its
# body (`hb.worker`, a resource's `server`) and judge it fresh by the key of that name: a file under `w-1`'s key whose
# body said `w-2` kept `w-2` alive while `w-2` was dead, and `w-1`'s name was never given back. A heartbeat whose body
# names another than its key — a foreign file copied in, a process that wrote under a name it does not hold — is not a
# heartbeat of either: skipped and counted as garbled.
def _owner_said(key: str, hb) -> None:
    if isinstance(hb, Heartbeat) and f"/{HEARTBEATS}/" in key:
        owner = key.partition(f"/{HEARTBEATS}/")[2]
        if hb.worker != owner:
            raise ValueError(f"the body names {hb.worker!r:.40}, the key {owner!r}")
    elif isinstance(hb, dict) and key.endswith("/heartbeat") and "server" in hb:
        owner = key[: -len("/heartbeat")].rsplit("/", 1)[-1]
        if hb["server"] != owner:
            raise ValueError(f"the body names {hb['server']!r:.40}, the key {owner!r}")


# …AND WHAT ITS SPEC SAYS IS A STRING IS ONE (`heartbeat.strings`, the product's key): the field a subsystem places by
# (`place_by`) is the place a worker is counted in, and `5` there was a place nobody could name. A worker's heartbeat
# whose field its subsystem's spec says is a string, and is not, is garbled like one that does not parse. A subsystem
# this process loaded no spec of says nothing here (`catalog.heartbeat_strings`).
def _strings_said(key: str, hb) -> None:
    if not (isinstance(hb, Heartbeat) and f"/{HEARTBEATS}/" in key):
        return
    from .catalog import heartbeat_strings
    for field_ in heartbeat_strings(key.partition(f"/{HEARTBEATS}/")[0]):
        if field_ in hb.extra and not isinstance(hb.extra[field_], str):
            raise TypeError(f"`{field_}` is a string by its spec (heartbeat.strings), not {hb.extra[field_]!r:.40}")


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
        _owner_said(key, hb)
        _strings_said(key, hb)
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
# slot's `until`, a worker's `ts`. A server whose clock ran 6…30 s ahead or 50 s behind had a live worker's units
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
# - `name` — the prefix (`a`, `b`, `testsub`).
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
    # where data grew in a single object: a store may declare a ceiling (`limits.py`; the capped store the
    # tests declare is 64 KiB), and 600 units — the cluster's own design maximum — did not fit under it. Sharded by
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

    # `<name>/requests/<id>` — bounded work somebody asked the holder of a unit to do, outside its ordinary pass: filed
    # by the console for an operator (`POST /<name>/requests`, the spec's `requests:`), by another subsystem's worker
    # (its spec's `worker: {requests: […]}`), or by the resource for bytes it needs freed (`free-…`, `requests.free`).
    #
    # The shape the blob sweep's row already has, generalised: one of those writes it, the holder's look reads
    # it (`Worker.requests`), and the platform never looks inside. It exists because the alternative — a POST that answers 202
    # and stores nothing — is a lie that survives right up until somebody checks whether the thing happened.
    # What a request MEANS is the subsystem's: one subsystem reads a range to fetch, another could
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
    # places, in M10B — and a worker may only take one of those, one at a time, exclusively.
    #
    # Two rows and not one because they answer different questions and lapse for different reasons: the
    # slot says which process of the deployment this is (the scheduler's business), the hold says which
    # place it writes into (the operator's). A process can lose the second and keep the first — it
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

    # `[<name>/epoch/*, <name>/slots/*, <name>/holds/*]` — what every worker writes: epochs, its slot and the
    # place it took; never configuration. The place is the worker's to take precisely because taking it
    # is a claim about this process, not a decision about the system. A spec's worker role adds what its spec
    # declares — rows of its own tables it found a thing to be (`worker.writes`), request rows it files for another
    # subsystem (`worker.requests`): `SubsystemSpec.acl_worker_role`.
    def acl_worker(self) -> list[str]:
        return [f"{self.name}/epoch/*", f"{self.name}/slots/*", f"{self.name}/holds/*"]

    # -- the object store's half of the same question ------------------------------------------------
    # Variables have had an ACL since Lesson 1; the OBJECT STORE never did. On one box that was invisible
    # — `FsObjectStore` has no writer and no prefixes — and on a cluster the objects a spec names rows are rows
    # of the store, granted by the same rights file as every other row.
    #
    # So the three grants are DERIVED here, from the same spec the Variables ACLs come from, and the cluster's
    # rights file is generated from them (`w2cplatform/cluster/rights.py`). One source, and a test that says so
    # (`tests/test_boundary.py`'s derivation on testsub; `tests/cluster/test_policies.py` for the file).
    #
    # Each is one directory with one writer, which is what the key layout was rearranged to allow:
    #
    # …and the marks before a request is performed (`<name>/commands/*`, `Worker._mark`): the platform's family, named by
    # the platform's worker — it was granted only where a spec repeated it under `objects.rows`, and a worker of any
    # other subsystem that serves requests could not write its mark on a cluster.
    def acl_objects_worker(self) -> list[str]:
        """The workers write their own heartbeats, their claims to a name another instance holds, the places they
        opened, and their marks before they perform a request."""
        return [f"{self.name}/{HEARTBEATS}/*", f"{self.name}/{CONTENDERS}/*", f"{self.name}/{USED}/*",
                f"{self.name}/{COMMANDS}/*"]

    def command_key(self, rid: str) -> str:
        return f"{self.name}/{COMMANDS}/{rid}"

    # …and the report on its pass (the review's ninth pass, major): `pass_once` writes `<name>/controller/pass`, the one
    # object `/metrics` reads `<name>_units_unplaced` and the last pass from, and this list — and the policy checked
    # against it — granted only the shards: on a cluster with an ACL the report was a 403 every five seconds and the
    # metrics stayed -1 and 0. `tests/cluster/test_policies.py` checks the rights against what the stand's processes
    # WRITE now.
    def acl_objects_controller(self) -> list[str]:
        """The controller publishes the snapshot shards — the only thing that leaves the cluster — and its pass report."""
        return [f"{self.name}/snapshot/*", f"{self.name}/{CONTROLLER_PASS}"]

    def acl_objects_console(self) -> list[str]:
        """The console stores the bytes of a `blob` field, beside the row that names them."""
        return [f"{self.name}/{BLOBS}/*"]


# THE CONTROLLER'S LIMIT, AS IT SAID IT (the product's alignment of the owner's decision on hung workers). A spare asks
# whether a lapsed slot's worker is hung before it takes the name (`Worker._hung`), and the console says so on `/servers`
# (`Mount._judged`) — each through `Controller.slot_fate`, with `HUNG_MOVE_AFTER` as compiled in, while the controller
# read its own from its environment: told an hour, it held a hung worker's units back and a spare took the name — and
# the units — at fifteen minutes, a second writer; told a minute, it moved them and the spare still waited. The
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
#   (`assignment_rev` in a subsystem's heartbeat).
# What a worker that files requests for OTHER subsystems may write, and nothing else.
#
# Every ACL so far has been about one prefix: a subsystem writes inside its own name. A subsystem of scenarios
# is the first thing that must reach across, because a scenario's whole job is to ask somebody else to act — and
# the narrowness is the point. Not `a/*`, which would let it edit another subsystem's units; not `a/requests/*` by
# accident of a wildcard, but by a grant that names the targets out loud in the process's token:
#
#     open_vars(url, writer="xworker", acl={"xworker": X.acl_worker() + requests_acl("a", "b")})
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
#   model: `{id, phase, epoch, …}` in a subsystem); `extra` — every other top-level key (`server`, `labels`,
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
    # units waited for ever. The holder writes it into every renewal of its name (`Worker.server`), and the controller
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
# beside the slot's). Read bare, one garbled hold among the candidates raised out of every claim: a worker took no
# place at all, and the console's list of places failed whole. The row is that place's trouble: no candidate until
# it is mended, counted (`HOLDS_GARBLED`, `holds_garbled` in the heartbeat and on `/metrics`), logged once.
HOLDS = Table("hold", "skipped — nobody takes that place until it is mended")
HOLDS_GARBLED = HOLDS.counts                      # subsystem -> hold rows that did not parse, this process


def read_hold(key: str, place: str, items) -> "Slot | None":
    """A place's row parsed, or None — skipped, counted, and logged once."""
    return HOLDS.read(key, lambda: Slot.from_items(place, _items(items)))


# -- one pass, one read of each key (the scaling pass after the eighth review) ----------------------------------------
# A controller's pass asks a dozen questions per unit — its row, its placement, which server a worker is on, whether
# that server's resource answers, who is leaving — and every question was a read of the store, asked again for the
# next unit. A thousand units on twenty workers cost one idle pass some 64 000 reads (`tests/test_read_budget.py`
# counts them): the snapshot alone read every heartbeat again for every unit, and `ensure_home` every worker's.
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
# so two instances are harmless — this is the property `spec.SpecController` and a subsystem's controller inherit,
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
    # followed subsystem's heartbeats under the same `(prefix, "")` as a DICT — in one pass shared by a following
    # subsystem's controller (`near: a`) and `a`'s own, the list read here was that dict, and `hb.ts` an `AttributeError`.
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
    # A worker's units move when its slot has lapsed AND its server's resource is silent — two
    # independent silences, about a minute and a half of nobody doing the work. A planned stop is not a silence:
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
    # they cannot know: whether a process that says nothing is dead or hung. A hung one went on writing beside the
    # worker its units were given to — two holders of units 1 and 3 — and a request refused as "alive" stood, and
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
    #            nobody can judge left its units written by nobody for ever, and an alarm was all (the owner's middle
    #            way for `hung`, applied to the doubt: a hung process is KNOWN to run and moves at the limit, so one
    #            that MAY run moves there too). `wait` keeps its old rule: it is what an older resource or a worker
    #            that never registered got before the resource said anything (the owner, 3 Oct: "old resource without
    #            fields → old behaviour")
    #
    # WHAT THE STORE REMEMBERS (the review's twelfth pass, blocker 5; the owner's decision of 4 Oct). A controller started
    # after a server died had read nothing of it: in М11 the worker's heartbeat and the resource's are files on that very
    # server, and "never said which server" held its units for ever. Two facts now live in the store, which outlives
    # any server: the server a slot's holder runs on (`Slot.server`, in every renewal) and when each resource last said
    # it is there (`at` on its door row, every `ALIVE_EVERY`; `resource_state`). A fresh controller reads both: the slot
    # lapsed past the margin, no heartbeat to read, the resource's row older than `SLOT_LOST_AFTER` — two silences, and
    # the units move. A slot left in `wait` or `unsure` with units on it is counted and said (`unjudged`).
    #
    # WHOSE CLOCK (the review's thirteenth pass, blocker 4; the owner's decision of 4 Oct). Every "still there?" here is
    # asked of what THIS controller has seen change, by its own clock (`Eyes`): the slot alive for a term (`SLOT_TERM`)
    # from when it saw the row renewed — not until the `until` its holder's clock wrote; the worker heard when its
    # heartbeat changed within `SLOT_LOST_AFTER`; the resource by its heartbeat and its door row the same way
    # (`resource_state`). A clock ahead holds nothing (`until` an hour on held a dead server's units for an hour — the
    # twelfth pass, major 17) and a clock behind takes nothing away (one 50 s behind had a live worker's units moved at
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
    # to look, before its units get a second writer; and short enough that a process hung for good leaves no hole for
    # ever. Its stand-in has already held the slot `STAND_IN_FOR` (five minutes) when the hang was in one step.
    # `HUNG_MOVE_AFTER` in the controller's environment (a subsystem's controller loop) — and said in its pass report, by
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
    # behind was "silent" while it beat, and a live worker's units went. Now they are tokens: changed within
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
            self.journal.say("clock.skew", ALARM, sub=self.sub.name, writer=key, skew=off[key],
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
    # hung worker. The log only, unless the process is given a resource tree (a subsystem's controller loop gives it one).
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
            self.journal.say("server.decommissioned", sub=self.sub.name, server=server, by=str(row.get("by", "") or "?"),
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
    # `/metrics` (the review's twelfth pass, blocker 5: a server's units waited on `wait` with no sign anywhere but a
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
                self.journal.say("worker.released_by_controller", sub=self.sub.name, worker=worker, server=server, why=why)
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
            self.journal.say("worker.unjudged", ALARM, sub=self.sub.name, worker=w, why=unjudged[w])
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
            self.journal.say("worker.unsure_moved", ALARM, sub=self.sub.name, worker=w, after=self.hung_move_after,
                             why=moved[w])
        gone.clear(); gone.update(moved)
        return new

    # A hung worker is an alarm, said once an episode — the pass looks every 5 s — and so is its move past
    # `hung_move_after`; "not hung any more" goes to the log. Returns the workers moved in THIS episode first.
    def _said_hung(self, hung: dict, moved: list) -> list:
        said, gone = self.__dict__.setdefault("_hung", set()), self.__dict__.setdefault("_hung_moved", set())
        for w in sorted(set(hung) - said):
            log.error("%s: %s", self.sub.name, hung[w])
            self.journal.say("worker.hung", ALARM, sub=self.sub.name, worker=w, why=hung[w])
        for w in sorted(said - set(hung) - set(moved)):
            log.warning("%s: %s is not hung any more", self.sub.name, w)
        new = sorted(set(moved) - gone)
        for w in new:
            log.error("%s: %s hung for longer than %g s: its units move anyway", self.sub.name, w, self.hung_move_after)
            self.journal.say("worker.hung_moved", ALARM, sub=self.sub.name, worker=w, after=self.hung_move_after)
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
        marks = contenders(self.objects, self.sub, now, self.eyes)
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
                self.journal.say("worker.name_conflict", ALARM, sub=self.sub.name, worker=name, holder=m.get("holder"),
                                 holder_box=holder_box, contender=m.get("instance"), contender_box=box,
                                 contender_hostname=m.get("hostname"), contender_server=m.get("server"),
                                 since=m["since"])
        before.clear(); before.update(said)
        return len(marks)

    # The places a worker's process holds (`<name>/holds/<place>`, `by` its slot): what freeing its slot leaves held —
    # a local disk is held through a silence on purpose, and one that went with its server is the administrator's to withdraw.
    def holds_of(self, worker: str) -> list[str]:
        return self.holds_by().get(worker, [])

    # `{place: holder instance}` for the places whose hold is live — by what this process saw change on its clock (`Eyes`,
    # `SLOT_TERM`; the thirteenth pass), not by the holder's `until` — what a metric counts as taken (`metrics.py`).
    def live_holds(self) -> dict[str, str]:
        prefix, out = self.sub.name + "/holds/", {}
        for path in self.vars.list(prefix):
            h = read_hold(path, path[len(prefix):], stored(self.vars, path, HOLDS)[0])
            if h is None or h.released or not h.holder:
                continue
            if self.eyes.age(path, (h.holder, h.until, h.gen)) <= SLOT_TERM:
                out[path[len(prefix):]] = h.holder
        return out

    # The workers of `live` that hold no place (their place field said empty: a spare) and whose instance holds none
    # either — taking is not opening, and a process that took a place is no spare whatever its heartbeat says yet.
    def placeless_live(self, live: dict) -> list[str]:
        holding = set(self.live_holds().values())
        return sorted(w for w, hb in live.items()
                      if self.place_of(w) == "" and str(hb.extra.get("instance", "")) not in holding)

    def holds_by(self) -> dict[str, list[str]]:
        prefix, out = self.sub.name + "/holds/", {}
        for path in self.vars.list(prefix):
            h = read_hold(path, path[len(prefix):], stored(self.vars, path, HOLDS)[0])
            if h is not None and not h.released and h.holder and h.by:
                out.setdefault(h.by, []).append(path[len(prefix):])
        return {w: sorted(p) for w, p in out.items()}
