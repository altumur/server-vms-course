"""The platform's worker: the life cycle every subsystem's worker shares (§3 row 7 of the boundary note; the product's
`p.Worker`).

A worker runs its assignment and reports. It claims a name (a slot, by CAS), takes an epoch per unit it starts and
holds a lease on it, renews both on a period shorter than they last, fences itself when another instance holds its
name and rejoins under a free one, registers with its server's resource, says what it holds in a heartbeat, and serves
the request rows of the units it holds — once each, at most once, its answer in the heartbeat. A subsystem's worker
subclasses `Worker` and implements its own work: `reconcile_once` (what runs equals what is assigned), `status` (what
the heartbeat says of each unit), and, for a subsystem whose units take requests, what one holder knows of them:
`held_rows` (what is open now), `request_target` (the key of what a request goes into) and `perform` (the call). Everything
else here — the fence and the epoch before a request's first act, the marks, the deadline, the `command` lines — runs
from the spec alone, and the platform's own tests run it on `testsub`.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import socket
import threading
import time
import uuid
from contextlib import contextmanager

from . import runtime
from .contract import (ASSIGNMENTS, Assignment, BUILD, CONTENDER_FRESH, CONTEND_EVERY, DECOMMISSION, DECOMMISSIONS, Eyes, HOLDS, Heartbeat, NAMELESS, NEVER_READ, NameOnAnotherBox, NoOffer, NoSlot, NotReadThisPass, PRESENCE, REFUSED, SCHEMA, SLOTS, SchemaTooNew, ServerDecommissioned, Slot, Subsystem, _NameTaken, _read_contender, check_schema, label_set, presence_name, published_names, read_assignment, read_hold, read_slot, slot_number, stored)
from .canonical import canonical_json
from .doors import numeric
from .epoch import Lease, next_epoch
from .events import ALARM, COMMAND, COMMAND_FAILED, OBSERVATION, OF
from .journal import Journal
from .longpoll import LongPoll, Wake, enabled as long_poll_enabled
from .objects import ObjectStore
from .rows import PARSE_ERRORS, garbled_counts
from .variables import Conflict, Variables, cas_pause

log = logging.getLogger(__name__)


# A worker whose subsystem has no spec in this process (`Worker.__init__`): it does not start.
class NoSpec(ValueError):
    pass


# Runs its assignment and reports. Reads `<name>/workers/<me>` and the units it names; writes its heartbeat
# object and, when it starts a unit, that unit's epoch by CAS. Never writes configuration. A fresh worker
# rediscovers everything from the store. Subsystems subclass it and implement `reconcile_once`; the loop is this
# class's (`run`), and so are the fields of the heartbeat the platform reads, the events' line (`observe`, through
# the spec's `events.suppress`) and the resource tree they go to (`resource_root`).
# What the heartbeat of a worker that names no server says (`server_unsaid`): one text, the product's too.
SERVER_UNSAID = "this worker names no server of its own: every place it holds is let go when its hold goes unconfirmed"


class Worker:
    """Runs its assignment and reports. Reads <name>/workers/<me> and the
    units it names; writes its heartbeat object and, when it starts a unit,
    that unit's epoch by CAS. Never writes configuration. A fresh worker
    rediscovers everything from the store."""

    def __init__(self, sub: Subsystem, name: str | None, vars_: Variables, objects: ObjectStore,
                 lease_ttl: float = 30.0, lease_margin: float = 5.0, clock=time.monotonic, wall=time.time,
                 instance: str | None = None, slot_ttl: float = 45.0, resource_root: str | None = None,
                 env: dict | None = None, spec=None):
        self.sub, self.vars, self.objects = sub, vars_, objects
        # THE SPEC, ALWAYS (the architect's rule after step 7: a platform key is executed by the platform, and the platform
        # has no path where the spec is absent). Every key of it a worker carries out — `lease`, `placement.places`,
        # `events.suppress`, `slot`, `about`, `requests` — is read here from the spec, and a worker without one ran on
        # defaults: a class that forgot to name its spec made `w-<n>`, renewed no strict place and stamped no `of`, and
        # nothing said so. The spec is the catalogue's, by the subsystem's name — the one the controller and the console
        # run by (`catalog.spec`); a test may hand its own. None of either: the worker does not start.
        self.spec = spec if spec is not None else self._catalogue_spec(sub, env)
        if self.spec.name != sub.name:
            raise ValueError(f"a worker of {sub.name} runs by {sub.name}'s spec, not {self.spec.name}'s")
        # This server's resource tree — where `observe` and the journal write (`runtime.events_root`: the caller's,
        # else `RESOURCE_ROOT`, else the platform's events root). Set here, before the claim, so no subsystem has to
        # remember it: one that forgot had `observe` write nothing, silently, and a journal opened on no tree.
        self.resource_root = runtime.events_root(os.environ if env is None else env, resource_root)
        self.schema_seen = check_schema(vars_)    # a build older than the store does not run at all; kept for `renew_slot`
        self.clock, self.wall = clock, wall
        self.started_wall = wall()                # this instance's start, by this box's wall clock: `started` in the heartbeat
        self.lease_ttl, self.lease_margin = lease_ttl, lease_margin
        # How long past a lease's end DATA may still be written while the store is silent (`Lease.may_write`): what
        # the subsystem's spec says (`lease: {unconfirmed_max}`) — 0, not at all, unless it says otherwise; `None` is
        # "for as long as the silence lasts". Never the environment: a weakening of the single writer is the spec's.
        self.unconfirmed_max: float | None = self.spec.unconfirmed_max
        self.epochs: dict[str, int] = {}          # unit -> epoch this worker holds
        # unit -> what it is about (`<about.sub>/<id>`, "" for nothing), read from its row when its epoch was taken
        # (`take_epoch`): the `of` of every line and mark written of it (`of`). None: the row did not read then.
        self.abouts: dict[str, str | None] = {}
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
        # one is followed by another at the loop's next look, not a period later (a subsystem worker's `run`, the raft
        # prototype's finding).
        self.unanswered = 0
        self.hold: str | None = None              # the PLACE this worker took, if its subsystem has places to take
        # One renewal or claim of the hold at a time, from whichever thread (`renew_hold`); and when this process
        # first saw each place's row as it is now — the clock a stale hold is judged by (`claim_hold`).
        self._hold_lock = threading.RLock()
        self._hold_seen: dict[str, tuple[int, float]] = {}
        self._slot_seen: dict[str, tuple[int, float]] = {}   # …and each garbled slot row's (`_garbled_stale`)
        # When the store last said the hold is this instance's, by the clock (`note_hold_confirmed`), and where each place
        # taken lies, as its row last read at the take or a renewal ("" — any box may write it; `_read_where`): what a
        # strict place is fenced by (`may_write_place`) and let go by (`_strict_place_pass`) while the store is silent.
        self._hold_confirmed = clock()
        self._place_where: dict[str, str] = {}
        # What this process has seen change, and when, by its own clock (`Eyes`; the review's thirteenth pass, blocker 4):
        # whose heartbeat is fresh enough to read a unit from — a holder, another subsystem's worker — by change, not by its writer's `ts`
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
        self._life()                              # the life cycle's own state: the fence, the epochs let go, the requests

    # The spec of `sub` in this process's catalogue (`catalog.spec`: what it loaded, else `SPEC_DIR`), or the refusal.
    @staticmethod
    def _catalogue_spec(sub: Subsystem, env: dict | None):
        from . import catalog
        try:
            return catalog.spec(sub.name, env)
        except ValueError as e:
            raise NoSpec(f"a worker of {sub.name} runs by its spec, and this process has none for it: {e}") from None

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
    server: str | None = None                     # the server it runs on, when its subsystem says (`_claim_slot` asks it)

    # What a slot this worker has to MAKE is called (`<prefix>-<n>`), and the variable its unit names the one it is
    # started under beside `WORKER_NAME`: the spec's `slot: {prefix, name_env}`, read here and nowhere else. Each
    # subsystem's class copied them (`SLOT_PREFIX`, `NAME_ENV`) and passed `runtime.slot` its own reading — a key the
    # loader read and a subsystem carried out, and a class that forgot made `w-<n>` whatever its spec said. A spec that
    # says no `slot` makes `w-<n>`, named in `WORKER_NAME`.
    @property
    def slot_prefix(self) -> str:
        return self.spec.slot_prefix

    @property
    def name_env(self) -> str:
        return self.spec.slot_name_env

    # The name the runtime gave this process (`runtime.slot`: its spec's variable, `WORKER_NAME`, `SLOT_INDEX`), or
    # None — "whichever is free, a lapsed one first".
    def given_name(self, env: dict) -> str | None:
        return runtime.slot(env, self.name_env, self.slot_prefix)

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
    # (EACCES, ENOSPC on the events tree) and went on working is `wait` — its units held back by the controller, and a
    # spare took the name and the units with it at +100 s, two writers (`n9_unregistered_hung_name`).
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
    # Every lease step looks for an offer again (`_seek_slot`). Returns the name, or None while it waits. `prefer` None:
    # the name the runtime gave it (`given_name`), if any.
    def claim_at_start(self, prefer: str | None, env: dict) -> str | None:
        spare = runtime.spare_for(env)
        if spare is None:
            return self.claim_slot(prefer=prefer if prefer is not None else self.given_name(env))
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
                # A NEW slot is named after the kind of worker taking it (`slot_prefix`: one letter per subsystem's
                # worker — the letters a process given a name already had), not `w-` for
                # everybody: a worker of one kind that had to make a slot looked like one of another in every list, every
                # heartbeat and every log line (the product's box, feedback BU). Slots that exist keep their
                # names; a lapsed or free one is still taken before a new one is made.
                nxt = f"{self.slot_prefix}-{max([slot_number(n) for n in names] + [0]) + 1}"
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
                    # and its units from box A at +50…+600 s, two writers (`n5_named_takes_hung`).
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
                                self.name_env, held)

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
            self.objects.put(key, canonical_json(row).encode())   # a row's one text (`canonical.py`)
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
    # resource tree when it has one (the root its subsystem gave it), else the log only — as the controller's.
    @property
    def journal(self) -> Journal:
        j = self.__dict__.get("_journal")
        if j is None:
            j = self.__dict__["_journal"] = Journal(self.resource_root, f"{self.sub.name}worker", self.wall)
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
            self.journal.say("worker.name_taken", ALARM, sub=self.sub.name, worker=e.slot, holder=e.holder,
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
        self.journal.say("worker.name_back", sub=self.sub.name, worker=n["name"], instance=self.instance, box=self._box(),
                         server=self.server or "", since=n["since"], nameless_s=round(now - n["since"]))

    # Still me? Read the slot; if `holder` is another instance, return False — the instance is fenced as a
    # whole (a subsystem's worker stops its work on this). Otherwise extend `until` by CAS; a `Conflict` is also
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
    # subsystem that writes to a disk puts its own server's disks before a network place any box could serve). A `Conflict`
    # means somebody took this one between the read and the write — try the next candidate, and only
    # repeat the sweep if contention was the reason we ran out.
    #
    # THE PLACE FOLLOWS THE NAME (feedback CF). A worker killed and started again by systemd is the same
    # worker: it takes its slot back at once, from a holder that has not lapsed (`claim_slot(prefer=…)` —
    # М10B Lesson 17: systemd is the authority on which process is the current `r-1`). Its place did not
    # follow: the hold waited out its TTL — 45 s in which nothing was written into that place, by the very
    # process that held it a moment ago. So a hold says WHOSE slot holds it (`by`), and the worker of that
    # slot takes it back at once, before any other candidate. The previous instance finds out at its next
    # `renew_hold` and stops writing there; what it wrote in between is fenced by the new epochs, as a slot's is.
    # Anybody else still waits for the TTL — the product's own lesson, from the daemon it writes through: a place
    # kept for its owner must be kept LONGER than the time the owner takes to come back.
    #
    # ONLY A PLACE THAT CANNOT BE WRITTEN FROM TWO HOSTS FOLLOWS THE NAME (the review's sixth pass, blocker 2). The
    # instance that took the name may be on another box, and the one it took it from frozen, not dead. Where the place
    # is a disk that is harmless — the two are on one host. Where any box may write it, taking it at once skipped the
    # one wait the previous holder's write window is measured against (`_hold_stale`), and two instances of one name
    # wrote one place. The subsystem says which places follow, given who holds the place now (`hold_follows_name`:
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
    # And no generation in the `owner` a subsystem names to its daemon (`<sub>:<place>`). The owner is how the next
    # holder of the place on this host picks up the writer a vanished one left, detached — with a generation in it the
    # successor names another owner, and waits out the daemon's grace with nothing written, which is what the owner is
    # there to prevent (feedback CF). The fence is the hold, confirmed by CAS right before every mount for writing
    # (by the subsystem's worker); on one host the daemon itself keeps one writer per place.
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
            t0 = self.clock()
            got = self._claim_hold(candidates, retries)
            if got is not None:
                self._hold_confirmed = t0                      # a new hold: its own clock, not the last one's
                # Remembered for the silence (`held_strictly`), from this take's row alone: a place whose row the take
                # could not read is strict (ADR 0029), whatever an earlier hold of it had read.
                self._place_where.pop(got, None)
                where = self._read_where(got)
                if where and not self.server:
                    log.warning("%s: took %s, a place of server %s, naming no server of its own: it is let go when its "
                                "hold goes unconfirmed, not kept through a silence (ADR 0029)", self.name, got, where)
            return got

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
    # A DEFAULT THAT WEAKENS A FENCE IS OFF UNTIL THE SPEC TURNS IT ON (the architect's rule after step 7): taking a place
    # back at once skips the one wait the previous holder's write window is measured against, so it is done only where
    # the spec says where the place is (`placement.places.server_field`) and the row says it:
    #   a place on one box (its row names its server)   from that box: this worker's server is the row's — its daemon
    #                                                   keeps one writer there
    #   a place ANY box may write (its row names none)  from the holder's own box: the row's `holder` is `host:pid:rnd`,
    #                                                   and the host is the box's id where the runtime says one
    #                                                   (`runtime.box_of`; an instance named otherwise says no host)
    #   a spec that names no `server_field`, a row that cannot be read now — where the place is is not known: it WAITS
    #                                                   like anybody's, until it is let go or its hold lapses
    # (It followed the name from any box when the spec said nothing: a default that let two instances of one name write
    # one place. Following from another box is no default; a spec that needed it would declare it.)
    def hold_follows_name(self, place: str, holder: str = "") -> bool:
        where = self._place_server(place)
        if where is None:
            return False
        if where:
            return bool(self.server) and self.server == where
        here = runtime.box_of(self.instance)
        return here is not None and here == runtime.box_of(holder)

    # The server the place's row names ("" — any box may write it), or None: the spec names no field for it, or the row
    # does not read now.
    def _place_server(self, place: str) -> str | None:
        places = self.spec.places
        if not places.get("server_field"):
            return None
        try:
            items, _ = self.vars.get(self.sub.config(places["table"], place))
        except (OSError, *PARSE_ERRORS):
            return None
        if not isinstance(items, dict):
            return None
        return str(items.get(places["server_field"]) or "")

    # Still mine? Same three lines as `renew_slot`, and the same meaning when it says no: another process
    # holds this place now, so this one must stop writing into it. Losing a hold is NOT losing the slot —
    # the process stays itself and becomes a spare.
    #
    # ONE AT A TIME, AND A LOST RACE IS READ AGAIN (the review's fourth pass, a minor). A subsystem's worker renews from two
    # threads — the pass, and a keep's `seal`, which confirms the hold before it mounts the writer again — and the
    # one that lost the CAS to the other took the conflict for the hold taken: let go of its own fresh hold, stopped
    # writing, and waited out the term to take it back. Renewals are serialised now, and a conflict is answered by
    # the row: still ours — somebody of ours renewed it a moment ago — is ours.
    #
    # A renewal confirms the hold as it was when the store was ASKED, as a lease's does (`Lease.renew`; the review's
    # fifth pass): one that took ten seconds to come back is ten seconds old (`note_hold_confirmed`).
    def renew_hold(self) -> bool:
        with self._hold_lock:
            if self.hold is None:
                return True
            t0 = self.clock()
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
                    self.note_hold_confirmed(t0)
                    self._read_where(self.hold)
                    return True
                self.hold = None
                return False
            self.note_hold_confirmed(t0)
            self._read_where(self.hold)
            return True

    # WHERE THE PLACE IS, READ AGAIN AT EVERY RENEWAL THAT SUCCEEDED (ADR 0029, More Information; the product's
    # `TestWhereAPlaceIsIsReadAgainAtEveryRenewal`). Read only at the take, a place the administrator gave to another
    # server mid-hold went on through silences as this server's; and one whose row the take could not read stayed strict
    # for good. The mark follows a row that was READ: one naming this worker's server makes the place its own, any other
    # takes that away; a read that fails changes nothing — it is no evidence either way, and weakens nothing.
    def _read_where(self, place: str) -> str | None:
        where = self._place_server(place)
        if where is not None:
            self._place_where[place] = where
        return where

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

    # A PLACE ANY BOX MAY WRITE, UNDER A STRICT LEASE (`placement.places.lease: strict`; the architect, 5 Oct: it is about
    # the place, not the unit). Two writers in one place is damage, not a duplicate, so whatever `lease.unconfirmed_max`
    # lets the units write, such a place is written only while its hold was confirmed less than `slot_ttl −
    # lease_margin` ago — the claimant that takes it next waits `slot_ttl + HOLD_SKEW` of an unchanged row
    # (`_hold_stale`) — and let go once it has not been. The platform's to carry out, not a subsystem's: a key the loader
    # reads and a subsystem executes is a promise the spec makes and the subsystem may forget (the architect's rule).
    #
    # A FENCE IS WEAKENED ONLY ON EVIDENCE THAT THE PLACE IS OURS (ADR 0012; the architect after the product's base worker,
    # ADR 0029). A place goes through a silence by the units' ceiling only where its row names THIS worker's server: that
    # server's daemon keeps one writer there. Every other place is strict — one any box may write, ANOTHER server's (its
    # row names it: someone else's place, never written into through a silence), one whose row could not be read, a spec
    # with no `server_field`, and every place of a worker that names no server of its own (`server_unsaid` says so in its
    # heartbeat). Read in the safe direction, as `hold_follows_name` reads the same row the other way. `row` is the
    # place's row as the caller holds it this second; without it, the row as it last read — at the take or at a renewal
    # (`_read_where`; a silent store answers nothing now).
    def held_strictly(self, place: str, row: dict | None = None) -> bool:
        places = self.spec.places
        if places.get("lease") != "strict":
            return False
        field = places.get("server_field")
        if not field or not self.server:
            return True
        where = str(row.get(field) or "") if row is not None else self._place_where.get(place, "")
        return where != self.server

    # May this worker write into `place` this second? A place not held strictly always — nobody else may write there.
    # One held strictly only while the hold is this worker's and inside its write window. A check before sending, as
    # `Lease.may_act` is: what fences the place itself is the place's own engine, if it has one.
    def may_write_place(self, place: str, row: dict | None = None) -> bool:
        if not self.held_strictly(place, row):
            return True
        return self.hold == place and self.clock() - self._hold_confirmed < self.slot_ttl - self.lease_margin

    # …and may what writes into it be CLOSED — its last writes flushed — while nobody else may have taken it? Wider than
    # the write window by the margin and the skew: a claimant waits `slot_ttl + HOLD_SKEW` of an unchanged row.
    def may_close_place(self, place: str, row: dict | None = None) -> bool:
        if not self.held_strictly(place, row):
            return True
        return self.hold == place and self.clock() - self._hold_confirmed < self.slot_ttl + self.HOLD_SKEW

    # The lease step's part (`lease_pass`): a place held strictly whose hold has gone unconfirmed past its write window
    # is asked for once more, and let go unless the store confirms it — the store silent, or the row another worker's.
    # Confirmed late is confirmed: by CAS on the row this worker wrote last, so nobody took it meanwhile (a claimant's
    # take would have changed it), and the fence opens again. A place not held strictly — its row names this worker's
    # server — stays this worker's through the silence by the units' ceiling (`lease.unconfirmed_max`, past the hold's
    # end; `forever`: for as long as the silence lasts). Nothing is held through a silence longer than the spec says:
    # past the ceiling it is asked for and let go the same way.
    def _strict_place_pass(self) -> None:
        place = self.hold
        if place is None:
            return
        quiet = self.clock() - self._hold_confirmed
        strict = self.held_strictly(place)
        if strict:
            if quiet < self.slot_ttl - self.lease_margin:
                return
        elif self.unconfirmed_max is None or quiet < self.slot_ttl + self.unconfirmed_max:
            return
        try:
            if self.renew_hold():
                return
            why = "another worker holds it now"
        except OSError as e:
            why = f"the store does not answer: {e}"
        self.leave_place(f"the hold on {place} has not been confirmed for {quiet:.0f} s, "
                         + ("and its lease is strict" if strict else "past the units' ceiling") + f" ({why})")

    # Stop writing into the place held, and let go of it: it is not this worker's any more. Here the hold alone (a silent
    # store lets it lapse by itself); a subsystem whose worker writes into its place closes that first, overriding this —
    # as a lost lease's work is stopped by `stop_unit`.
    def leave_place(self, why: str) -> None:
        log.warning("%s: %s — letting go of it", self.name, why)
        try:
            self.release_hold()
        except OSError:
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
    #
    # …AND WHAT THE LEASE STEP LET GO BEFORE IT IS FORGOTTEN BY IT (`lost_to_epoch`; the review's thirteenth pass, major 6,
    # where only one subsystem's refresh did it): a unit let go is not taken back between passes, and the read that
    # answered is what says whether it is still this worker's. Cleared at the read — not when the caller's pass ran
    # through — and only what was let go BEFORE the read: what the lease step lets go meanwhile stays.
    def assignment(self) -> Assignment:
        if self.seeking is not None:
            return Assignment(self.name, [])      # the row under that name is the other instance's now (`keep_slot`)
        key = self.sub.assignment(self.name)
        lost_before = set(self.lost_to_epoch)
        try:
            items, _ = stored(self.vars, key, ASSIGNMENTS)  # one the store cannot read: no unit, counted (the eleventh review)
        except OSError:
            self.assigned_now = None
            raise
        a = read_assignment(key, self.name, items)
        self.assigned_now = frozenset(str(u) for u in a.units)
        self.lost_to_epoch -= lost_before
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
        # read before it hung: the next unit of the list was started, its epoch taken by CAS over the worker the units
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
        # worker that holds the unit's epoch already goes on under it (a subsystem worker's actuation, feedback BK).
        if self.assigned_now is not NEVER_READ and (self.assigned_now is None or str(unit) not in self.assigned_now):
            raise NotReadThisPass(
                f"{self.name}: {unit} is not in the assignment read last" if self.assigned_now is not None else
                f"{self.name}: its assignment did not answer, and {unit} may be another's now: no new epoch for it "
                f"until the assignment is read again")
        # …NOR FOR A UNIT THE LEASE STEP LET GO SINCE THAT READ (`lost_to_epoch`; the review's thirteenth pass, major 6):
        # the step found a newer epoch — the unit's new holder took it — and the list read before still names the unit.
        # Whether it is still this worker's is the next read's to say. The rule was kept twice — by one subsystem's gate
        # and by the requests — and by no other caller; it is the epoch's now, whoever asks for one.
        if str(unit) in self.lost_to_epoch:
            raise NotReadThisPass(f"{self.name}: {unit} was let go to a newer epoch since the assignment was last read: "
                                  f"not taken back until it is read again")
        epoch, _ = next_epoch(self.vars, self.sub.epoch_key(unit))
        self.epochs[unit] = epoch
        self.leases[unit] = Lease(self.vars, self.sub.epoch_key(unit), epoch, self.lease_ttl, self.lease_margin, self.clock,
                                  self.unconfirmed_max)
        self.abouts[str(unit)] = self._read_about(str(unit))
        return epoch

    # WHAT A UNIT IS ABOUT — the `of` of every line and mark this worker writes of it (`<about.sub>/<id>`, the index's
    # second column), "" for a unit about nothing but itself. The PLATFORM's to say, from the spec's `about` and the unit's
    # row: it was each subsystem's, passed by hand at each line, and a line that forgot it (a refused request, written
    # through `observe`) was found by a query for its unit and by none for what the unit is about. `about.field` is
    # `fixed`, so what was read when the epoch was taken holds while the epoch does; a row that did not read then is read
    # again at the next line. A unit this worker holds no epoch for (a line under epoch 0) is read at its line.
    def of(self, unit) -> str:
        unit = str(unit)
        if not self.spec.about_sub:
            return ""
        got = self.abouts.get(unit)
        if got is None:
            got = self._read_about(unit)
            if got is not None and unit in self.epochs:
                self.abouts[unit] = got
        return got or ""

    # The unit's row, read now, for what it is about; None when it does not read (the store, a garbled row).
    def _read_about(self, unit: str) -> str | None:
        if not self.spec.about_sub:
            return ""
        try:
            items, _ = self.vars.get(self.sub.config(self.spec.rows, unit))
        except (OSError, *PARSE_ERRORS):
            return None
        if items is not None and not isinstance(items, dict):
            return None
        return self.spec.of_row(items)

    # Forget the unit's epoch and lease (the worker stopped it). The lease is marked let go as well: the stand-in may
    # hold it from before, and a lease the loop released is renewed by nobody.
    def release(self, unit: str) -> None:
        self.abouts.pop(str(unit), None)
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
    def may_act(self, unit: str) -> bool:
        lease = self.leases.get(unit)
        return lease is not None and lease.may_act()

    # The wider question, for data: also a lease that ran out while the store was silent (`Lease.may_write`).
    def may_write(self, unit: str) -> bool:
        lease = self.leases.get(unit)
        return lease is not None and lease.may_write()

    # Units written past their lease's end, unconfirmed: `{unit: seconds}`.
    def unconfirmed(self) -> dict[str, float]:
        return {u: round(l.unconfirmed(), 1) for u, l in self.leases.items() if l.unconfirmed() > 0}

    # Renews every lease; returns the units whose lease was lost — fenced or expired — for the subsystem to
    # stop.
    # THE SLOT ROW, KEPT BY EVERY LOOP — not only the two that renewed it already (found beside the stand-in, after
    # the fourth review). The other subsystems' workers claimed their slot once, at construction,
    # and never renewed it: the row lapsed after `slot_ttl` in ordinary work, and a spare or a restarted process
    # could take the name of a worker that was alive and holding units. `keep_slot` renews it on the loop's lease
    # step; a store that does not answer keeps the slot (not known is not "taken"); a row naming ANOTHER instance
    # means this one is a zombie on that name: it lets its units go (`let_go`, the worker's own stop), gives up
    # their epochs and claims a free slot.
    #
    # NOBODY UNTIL IT HAS ONE (the review's fifth pass, blocker 3). The claim that follows can fail — the store blinks,
    # every candidate is taken under it — and the worker was left with no slot and the OLD name: `renew_slot` with no
    # slot said "still me", the stand-in renewed for it, the next pass read the other instance's assignment and took
    # epochs on its units with `may_act` true, and its heartbeat went out over the legitimate one. Two processes took
    # the same units in turn, until a restart. Now a name given up is `seeking` until another is claimed, and
    # while it is the instance is fenced: `renew_slot` says no (so the stand-in renews nothing), `may_stand_in` says no,
    # `take_epoch` raises `NoSlot`, the assignment it reads is empty and no heartbeat goes out under the name. Every
    # lease step claims again, as a subsystem worker's `rejoin` does for a fenced holder.
    #
    # …AND THE HOLDER TOO (the review's sixth pass). Some subsystems' workers do not come through here: they fence
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
    # nobody and tries again: a subsystem worker's `rejoin` comes through here too (the review's sixth pass).
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
    # to the store or the engine — a pass, a pump, a worker's call into its daemon — stopped renewing too: after the
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
    # renews the place (`hold`) as well — a network place lapses as fast as its slot, and a worker hung
    # in its daemon is the case this was written for.
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
        return self.seeking is None and self.writing_allowed

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
    # no heartbeat: 45 s into a hung step the controller and the workers following it judged the holder dead — they lost the
    # fan-out they read from, the controller moved its units — while the stand-in held its leases for five minutes. So
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
    STAND_IN_HEARTBEAT = 10.0     # the loop's heartbeat rhythm (a subsystem worker's `run`)

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
    # to act on (`renew_hold` clears `hold`, and a worker mounts by what `hold` says).
    #
    # And only while the subsystem says the step is worth holding the place for (`may_stand_in_hold`; the review's fifth
    # pass, a minor): a worker's step stuck on a daemon that answers nothing writes nothing, and five minutes of a
    # network place held for it were five minutes no box whose daemon answers could take it. A renewal it did make is
    # told (`note_hold_confirmed`), from before the store was asked — what a worker fences its samples by.
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
    # an engine says no while that engine is silent (its worker overrides this).
    def may_stand_in_hold(self) -> bool:
        return True

    # The place confirmed by the store at `at` (the clock, before it was asked): what a strict place is fenced by
    # (`may_write_place`). Never backwards — the pass, a subsystem's own renewal and the stand-in confirm it from three
    # threads.
    def note_hold_confirmed(self, at: float) -> None:
        self._hold_confirmed = max(self._hold_confirmed, at)

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

    # Sum of `conflicts` over all leases, and those met under a name it lost (`rejoin`); goes into the heartbeat.
    def conflicts(self) -> int:
        return sum(l.conflicts for l in self.leases.values()) + self.conflicts_carried

    # Writes `Heartbeat(name, wall(), status, extra)` to `<name>/heartbeats/<worker>` in the object store. The loop's
    # heartbeat (`heartbeat_once`) passes the platform's fields (`platform_fields`: `server`, `labels`, `capacity`,
    # `headroom`, `conflicts`, `started`, `previous_*`, …) and the subsystem's (`heartbeat_fields`) as `extra`.
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
            # …SAID, NOT ONLY LOGGED (the review's twelfth pass, blocker 3): ENOSPC on the place it writes into left the
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
        # A worker that names no server of its own, of a subsystem whose places say their server: none of them is its
        # own, so every one is let go when its hold goes unconfirmed (`held_strictly`, ADR 0029). Said, for the person
        # reading the heartbeat; the platform decides nothing by it, and `/metrics` does not count it.
        if not self.server and self.spec.places.get("server_field"):
            extra.setdefault("server_unsaid", SERVER_UNSAID)
        # `schema` and `build` are on EVERY heartbeat, from here, so no subsystem has to remember them:
        # the first says what layout this process understands (what `set_schema` is checked against), the
        # second is for the person looking at a half-upgraded cluster.
        extra.setdefault("schema", SCHEMA)
        extra.setdefault("build", BUILD)
        # …and `pending_writes`: what a drain waits for besides the units (`SpecConsole.drain_state`, `safe`)
        extra.setdefault("pending_writes", self.pending_writes())
        if self.stand_in_renewals:
            extra.setdefault("stand_in_renewals", self.stand_in_renewals)     # a step hung, and somebody held its units
        # Rows of this subsystem this process could not read, by table (`rows.Table`): `slots_garbled` (`read_slot`),
        # `assignments_garbled` (its own assignment), `holds_garbled` (`read_hold`), and those of a subsystem's own
        # tables — `<table>_garbled` each.
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

    # WRITES THIS PROCESS HOLDS AND HAS NOT MADE DURABLE (§2.5 of the boundary note): a buffer on this machine's disk
    # that would go with the machine. A drain is `safe` only when every worker of the server says 0 here. 0 by
    # default: a worker that writes through to a store it does not hold has nothing pending; one with a buffer says
    # how deep it is.
    def pending_writes(self) -> int:
        return 0

    # what a subsystem implements
    # Abstract: what a subsystem implements. A worker whose units are a set of pipelines calls the platform's reconcile
    # helper from it (`reconcile.py`, ADR 0033: backoff with jitter, which the contract owes); one whose work is not
    # need not.
    # `now` is optional: the loop (`run`) calls it with none, a test may pass its own.
    def reconcile_once(self, now: float | None = None) -> list:
        raise NotImplementedError

    # ================================================================================================================
    # THE LIFE CYCLE EVERY SUBSYSTEM'S WORKER SHARES (§3 row 7 of the boundary note: it was one subsystem's holder,
    # inherited by the others or copied into their own loops). A subsystem implements its WORK and nothing of this:
    #
    #   reconcile_once()     one pass: what runs equals what is assigned (abstract, above)
    #   status()             what the heartbeat says of each unit
    #   heartbeat_fields()   …and of itself, beyond the platform's own fields (`heartbeat_once`)
    #   stop_unit(unit)      stop the local work of one unit whose lease was lost
    #   stop_all_units()     stop everything local: an orderly stop
    #   fence_units()        …and when the instance is fenced (default: `stop_all_units`)
    #   forget_units()       forget what it held when it rejoins under another name
    #   held_rows(), request_target(row), perform(target, row, it)   a subsystem whose units take requests (below)
    # ================================================================================================================
    LEASE_EVERY: float | None = None              # seconds between lease steps; None: a third of `ttl − margin`
    HEARTBEAT_EVERY = 10.0                        # seconds between heartbeats of the loop

    # THE LIFE CYCLE'S OWN STATE, made with the worker (`__init__`) and nowhere else: the fence, what the lease step let
    # go, the counters, the requests. Every rule that reads it — the fence and the epoch before a request's first act, a
    # line's and a stand-in's fence — is the base's, and a subsystem neither keeps a copy nor checks that it is there.
    def _life(self) -> None:
        self.writing_allowed = True               # the instance-wide fence: False while it is nobody (`fence`, `rejoin`)
        self.fenced_reason: str | None = None
        self.was_fenced: str | None = None        # why it was fenced last, once it has rejoined
        self.conflicts_carried = 0                # epoch conflicts it met as a zombie, under the name it lost (`rejoin`)
        self.store_errors = 0                     # passes and renewals the store did not answer
        self.pass_failures = 0                    # parts of the loop that raised, since the process started
        self.passes = 0
        self.lost_to_epoch: set[str] = set()      # units the lease step let go since the last assignment read (`take_epoch`)
        self.epoch_errors: dict[str, str] = {}    # unit -> why its epoch could not be taken (a garbled row)
        self.pass_refused = False                 # a resource did not answer this pass: early passes back off (`run`)
        self._requests_state()

    # -- staying itself: the slot, the leases, the fence -------------------------------------------------------
    # Renew the slot and every lease, and decide what a lost lease means. Three rules (feedback BC):
    #
    #   the slot says who I am    only a slot row READ, naming another holder, fences the instance. A store that
    #                             did not answer is not that row: "still me", counted (`store_errors`). The slot
    #                             is a name; the right to write is the leases', and they run out by themselves
    #   a lease is one unit's     lost however it was lost — the unit went to another worker, it is in two
    #                             assignments for the seconds a controller takes to mend that, or the store did
    #                             not confirm the lease in time — ONE unit's work stops and its epoch is given up.
    #                             If the unit is still mine the next pass starts it again, under a new epoch
    #   a fence is not for ever   `rejoin`, below
    #
    # And an exception (feedback BK): a lease that ran out while the store was SILENT is not lost. The work goes on
    # under the epoch it has — DATA, which a stale epoch cannot harm — and ACTIONS wait (`requests` asks the strict
    # `may_act`). When the store answers again: the same epoch, and nothing was stopped; another, and the unit stops
    # as it always did. `unconfirmed_max` is the ceiling, in seconds past the lease's end. A place held strictly has none:
    # it is let go once its hold has gone unconfirmed past its write window (`_strict_place_pass`).
    def lease_pass(self) -> list[str]:
        """Renew the slot and every lease. Another holder on my slot: the instance
        fences. A lost lease: that one unit stops and gives its epoch up."""
        if self.writing_allowed and self.waiting_for_offer():
            self._seek_slot()                         # a spare with no offer yet: nobody, holding nothing — not a fence
            return []
        try:
            mine = self.renew_slot()
        except OSError as e:
            self.unanswered += 1
            self.store_errors += 1
            log.warning("%s: the store did not answer for the slot (%s); still %s", self.name, e, self.name)
            mine = True
        except SchemaTooNew as e:
            # The store was raised past this build while it ran (the review's second pass, m4): the rows it would read
            # next are not what it thinks they are. Fenced, as a build older than the store does not start — and it
            # stays fenced (`rejoin` checks the same thing) until somebody restarts it new. Fenced with its slot in
            # hand, it renews nothing: the row lapses, another process takes the name, and from the lease step that
            # reads another holder there it is nobody (the review's sixth pass).
            self.schema_seen = None                   # what it read is not the store's layout any more (`rejoin`)
            self.fence(str(e))
            self.name_taken()
            return list(self.epochs)
        if not mine:
            # NOBODY FROM THIS LINE (the review's sixth pass), as `keep_slot` makes it: the name is the other
            # instance's, and so are its assignment and its heartbeat.
            self.give_up_name()
            self.fence(f"slot {self.name} is held by another instance now")
            return list(self.epochs)
        waiting = {u: l.epoch for u, l in self.leases.items() if l.unconfirmed() > 0}
        lost = self.renew_leases()
        for unit, epoch in waiting.items():
            lease = self.leases.get(unit)
            if unit not in lost and lease is not None and lease.silent_since is None:
                log.warning("%s: the store confirms epoch %d of %s again; nothing was stopped", self.name, epoch, unit)
        for unit in lost:
            lease = self.leases.get(unit)
            why = ("a newer epoch was issued for it" if lease is not None and lease.fenced
                   else f"unconfirmed for longer than its ceiling ({lease.unconfirmed_max:g} s)"
                   if lease is not None and lease.silent_since is not None and lease.unconfirmed_max
                   else "the store did not confirm the lease in time")
            log.warning("%s: %s stopped: %s", self.name, self.unit_word(unit), why)
            self.stop_unit(unit)
            self.release(unit)
            self.lost_to_epoch.add(unit)
        self._strict_place_pass()
        return lost

    # How a log line names a unit: `unit 7`; a subsystem says it in its own word.
    def unit_word(self, unit) -> str:
        return f"unit {unit}"

    # A fenced instance is nobody: on its next pass it takes a FREE slot and starts from nothing — no epochs, no rows,
    # whatever that slot's assignment says (the product's Go worker, feedback BC: a supervisor does not restart a
    # process that has not died). Returns the new name, or None while there is no slot to take.
    def rejoin(self) -> str | None:
        if self.writing_allowed:
            return self.name
        # A store raised past this build: nobody to rejoin as (the review's second pass, m4) — with the version it last
        # read whole (the review's fourth pass): a row that does not parse is "never read" to a bare check.
        try:
            self.schema_seen = check_schema(self.vars, getattr(self, "schema_seen", None))
        except SchemaTooNew:
            return None
        except OSError:
            return None                               # not known: a fenced instance can wait a pass
        was = self.name
        # What the epochs said of the zombie goes with it to its next name (the sixth pass, the follow-up).
        self.conflicts_carried += sum(l.conflicts for l in self.leases.values())
        self.release_all()
        self.forget_units()
        # The claim can fail; the name is given up first and the claim is `keep_slot`'s (`_seek_slot`): nobody until
        # it has a slot, and every pass tries again (the review's sixth pass; the fifth's blocker 3).
        self.give_up_name()
        if not self._seek_slot():
            return None
        name = self.name
        log.warning("%s: was fenced as %s (%s); rejoined as %s", self.instance, was, self.fenced_reason, name)
        self.writing_allowed, self.was_fenced, self.fenced_reason = True, self.fenced_reason, None
        return name

    # Once: log at error, `writing_allowed = False` and `fenced_reason`, and the local work stopped underneath the loop
    # (`fence_units`). Idempotent. After this the subsystem starts nothing and writes nothing; the heartbeat says
    # `fenced: true` while the name is still this instance's, and nothing at all once the name is another's.
    def fence(self, why: str) -> None:
        if not self.writing_allowed:
            return
        log.error("%s: FENCED (%s). Stopping every unit.", self.name, why)
        self.writing_allowed, self.fenced_reason = False, why
        self.fence_units()

    # The hooks of the subsystem's work (see the head of this part).
    def stop_unit(self, unit) -> None:
        pass

    def stop_all_units(self) -> None:
        for unit in list(self.epochs):
            self.stop_unit(unit)

    def fence_units(self) -> None:
        self.stop_all_units()

    def forget_units(self) -> None:
        pass

    def status(self) -> list[dict]:
        return []

    # What this worker can carry: the number its subsystem set (`capacity`), else its spec's `placement.capacity.default`.
    # It said 0 when its subsystem set none: the controller takes a said number as the worker's word (`capacity_of`), and
    # nothing was ever placed on it.
    def capacity_said(self) -> int | None:
        cap = getattr(self, "capacity", None)
        return self.spec.capacity_default if cap is None else cap

    def headroom(self) -> int:
        return max(0, int(self.capacity_said() or 0) - len(self.assignment().units))

    # The heartbeat: `status()` and the fields the platform reads by name — where it runs, what it can carry, whether
    # it is fenced, what it answered (`fetched`), when this instance started and what the instance before it under this
    # name last said (`previous_*`: what `SpecController.failover_seconds` measures) — and what the subsystem adds
    # (`heartbeat_fields`).
    def heartbeat_once(self) -> None:
        self.heartbeat(self.status(), **{**self.platform_fields(), **self.heartbeat_fields()})

    def platform_fields(self) -> dict:
        cap = self.capacity_said()
        return {"server": self.server, "instance": self.instance, "labels": ",".join(getattr(self, "labels", None) or []),
                **({"capacity": cap, "headroom": self.headroom()} if cap is not None else {}),
                "conflicts": self.conflicts(), "started": self.started_wall, **self.previous_said(),
                **({"fenced": True} if not self.writing_allowed else {}),
                **self.requests_fields()}

    # THE INSTANCE BEFORE THIS ONE UNDER ITS NAME: the heartbeat it left — its `ts`, its instance, its server — read once
    # per name this instance holds, before this instance's first heartbeat under it writes over it. What failover is
    # measured from (`SpecController.failover_seconds`, on one clock when the server is the same); it was one
    # subsystem's constructor, and every other subsystem's failover went unmeasured. A heartbeat that does not parse,
    # or cannot be read (a resource door restarting), is no failover to measure — said, and that is all it costs.
    def previous_said(self) -> dict:
        name = None if self.seeking is not None else self.name
        if not name:
            return {}
        seen = self.__dict__.get("_previous")
        if seen is None or seen[0] != name:
            prev = {"previous_hb": 0.0, "previous_instance": "", "previous_server": ""}
            try:
                raw = self.objects.get(self.sub.heartbeat_key(name)) if self.objects is not None else None
            except OSError as e:
                raw = None
                log.warning("%s: its previous heartbeat could not be read (%s): this start's failover is not measured",
                            name, e)
            if raw:
                from .contract import parse_heartbeat
                old = parse_heartbeat(self.sub.heartbeat_key(name), raw)
                if old is not None and old.extra.get("instance") != self.instance:   # its own: no instance before it
                    prev = {"previous_hb": old.ts, "previous_instance": str(old.extra.get("instance", "")),
                            "previous_server": str(old.extra.get("server", ""))}
            seen = self.__dict__["_previous"] = (name, prev)
        return dict(seen[1])

    @property
    def previous_hb(self) -> float:
        return float(self.previous_said().get("previous_hb", 0.0))

    @property
    def previous_instance(self) -> str:
        return str(self.previous_said().get("previous_instance", ""))

    @property
    def previous_server(self) -> str:
        return str(self.previous_said().get("previous_server", ""))

    def heartbeat_fields(self) -> dict:
        return {}

    # -- the loop --------------------------------------------------------------------------------------------------
    # The loop as a process. Every `poll` seconds: the pass (`reconcile_once`, after `rejoin` while fenced), the pump
    # (`pump_once`: the requests), the lease step every `LEASE_EVERY` (a third of `ttl − margin` by default, ≈8.3 s,
    # well inside the 25 s a lease allows — and at once after a step with a renewal the store did not answer), the
    # heartbeat every `HEARTBEAT_EVERY`; each step `guarded` (the stand-in renews for one that hangs, feedback DD) and in
    # a try of its own — a pass that failed is a pass to retry, and the process that ran it still holds its units and
    # says so (the review's seventh pass, part 2). The first heartbeat goes NOW. On `stop`: the subsystem's last words
    # (`before_stop_all`), its work stopped, a last heartbeat, the slot released — an orderly stop says so; a crash says
    # nothing, which is what lets the controller tell scale-in from a crash — and `after_stop`.
    #
    # THE NEXT LEASE STEP FROM THE START OF THIS ONE, AND AT ONCE AFTER ONE THE STORE DID NOT ANSWER (the raft
    # prototype's finding): `T + P + poll` without a confirmation, inside the window up to a pause of ~13 s.
    #
    # AN EARLY PASS (`longpoll.py`, for a worker that asked for it — `poll_events`): a wait cut short by a resource's
    # answer is followed by `early_pass(touched)` — what the answers said changed, `(subsystem, kind, unit)` — and the
    # ordinary pass over everything still comes at least every `poll`, woken or not. After every pass the wake is told
    # how long it took and whether a resource refused (`pass_refused`; `Wake.pace`): the long poll speeds the road up
    # and is never what loads the resources. The heartbeat stays by its clock: an early pass does not add one. (One
    # subsystem's worker had this loop as a copy of its own; there is one loop.)
    def run(self, poll: float = 2.0, stop=None, beat: float = 0.0) -> None:
        """One box: the loop as a process. systemd or launchd restarts it."""
        stop = stop or threading.Event()
        lease_every = self.LEASE_EVERY or max(1.0, (self.lease_ttl - self.lease_margin) / 3)
        stand_in = self.start_stand_in()
        with self.guarded("heartbeat"):
            self.heartbeat_once()
        last_lease, last_hb, again = 0.0, self.clock(), False
        last_full, woken, touched = -1e18, False, None
        while not stop.is_set():
            full = not woken or touched is None or self.clock() - last_full >= poll
            began = self.clock()
            try:
                with self.guarded("pass"):
                    if not self.writing_allowed:
                        self.rejoin()                      # a fence is not for ever: a free slot, from nothing
                    if full:
                        self.reconcile_once()
                    else:
                        self.early_pass(touched)
                if full:
                    last_full = began
            except Exception:                              # noqa: BLE001
                self.pass_failures += 1                    # …and counted: a loop that raises every pass is alive and says so
                log.exception("%s: pass failed; will retry", self.name)
            if self.wake is not None:                      # the next early pass no sooner than the load allows
                self.wake.pace(self.clock() - began, self.pass_refused)
            try:
                with self.guarded("pump"):
                    self.pump_once()
            except Exception:                              # noqa: BLE001
                self.pass_failures += 1
                log.exception("%s: pump failed; will retry", self.name)
            try:
                if again or self.clock() - last_lease >= lease_every:
                    unanswered, started = self.unanswered, self.clock()
                    with self.guarded("lease"):
                        self.lease_pass()
                    last_lease, again = started, self.unanswered > unanswered
            except Exception:                              # noqa: BLE001
                self.pass_failures += 1
                log.exception("%s: the lease step failed; will retry, and the heartbeat goes all the same", self.name)
            try:
                if self.clock() - last_hb >= self.HEARTBEAT_EVERY:
                    with self.guarded("heartbeat"):
                        self.heartbeat_once()
                    last_hb = self.clock()
            except Exception:                              # noqa: BLE001
                log.exception("%s: heartbeat failed; will retry", self.name)
            woken = self.between(poll, stop, beat)         # `stop.wait(poll)`, with a look at the requests every `beat`
            touched = self.long_poll.take_touched() if woken and self.long_poll is not None else None
        stand_in.set()
        self.stop_polling()                           # no request is held at a resource for a loop that ended
        self.before_stop_all()
        self.stop_all_units()
        self.heartbeat_once()
        self.release_slot()                           # an orderly stop says so; a crash says nothing
        self.after_stop()

    # A pass begun early, at a resource's answer: the ordinary pass unless the subsystem's worker can look at less —
    # `touched` is what the answers said changed.
    def early_pass(self, touched: set) -> None:
        self.reconcile_once()

    # What a pass does beside the reconcile: the summaries of suppressed repeats whose window closed, and the request
    # rows, when the subsystem's units take requests.
    #
    # A REQUEST LOOK THAT RAISES SOMETHING ELSE IS ONE LOOK'S TROUBLE (found on a cluster's request marks): a store that
    # refuses a write it does not take — a mark the cluster's object store will not create — raised `ValueError` past
    # the `OSError` here, out of the pump. Counted and said once a spell; the next look tries again.
    def pump_once(self) -> None:
        self.flush_suppressed()
        if not self.serves_requests():
            return
        try:
            self.serve_requests()
        except OSError as e:                          # the requests are rows in the store: no store, none this pass
            self.store_errors += 1
            log.warning("%s: the store did not answer for the requests (%s)", self.name, e)
            return
        except Exception as e:                        # noqa: BLE001 — not the store's silence: this look's, counted
            self.pass_failures += 1
            if not self.__dict__.get("_requests_failing"):
                self.__dict__["_requests_failing"] = True
                log.exception("%s: the look at the requests failed (%s); looking again every pass, saying so once",
                              self.name, e)
            return
        if self.__dict__.pop("_requests_failing", False):
            log.warning("%s: the requests are looked at again", self.name)

    # BETWEEN TWO PASSES (2 October 2026): the loop wakes every `beat` seconds inside the wait and looks at the request
    # rows (`beat_once`) — not a pass: the assignment is not read again, nothing is reconciled. The lease step and the
    # heartbeat stay once per turn, by the clock. By the real clock: `stop.wait` waits real seconds. And at the end of
    # every turn the supervisor is told the loop turns (`runtime.notify`, systemd's watchdog): a step that HANGS keeps
    # the loop from coming here, and after `WatchdogSec` systemd starts the unit again.
    # True when the wait was cut short by a resource's answer (`wait_next`): the pass that follows is an early one.
    def between(self, poll: float, stop, beat: float) -> bool:
        runtime.notify()
        if self.wake is not None:
            return self.wait_next(poll, stop)         # `stop.wait(poll)` — or sooner, when an event it watches was written
        if beat <= 0 or beat >= poll:
            stop.wait(poll)
            return False
        end = time.monotonic() + poll
        while not stop.wait(max(0.0, min(beat, end - time.monotonic()))):
            if end - time.monotonic() <= 0.001:
                return False                          # the pass is due, and it looks at the requests itself
            self.beat_once()
        return False

    # One look between passes. A store that does not answer is waited out as on a pass — and said ONCE per outage.
    def beat_once(self) -> None:
        try:
            with self.guarded("beat"):
                self.beat()
        except Exception as e:                        # noqa: BLE001 — a beat that raised is a beat to make again
            if not self._beat_failed:
                self._beat_failed = True
                if isinstance(e, OSError):
                    self.store_errors += 1
                    log.warning("%s: the store did not answer for the requests between passes (%s); "
                                "looking again every beat, saying so once", self.name, e)
                else:
                    self.pass_failures += 1
                    log.exception("%s: the look at the requests between passes failed; will retry", self.name)
            return
        if self._beat_failed:
            self._beat_failed = False
            log.warning("%s: the requests are read between passes again", self.name)

    def beat(self) -> None:
        if self.serves_requests():
            self.serve_requests()

    # What the subsystem does before its work is stopped on an ORDERLY stop, and lets go of after the slot.
    def before_stop_all(self) -> None:
        pass

    def after_stop(self) -> None:
        pass

    # ================================================================================================================
    # REQUESTS: `<sub>/requests/<id>`, performed by whoever holds the unit (§3 row 3; it was one subsystem's code).
    # The family the platform has for "bounded work somebody asked for", filed by the console (`POST /<sub>/requests`,
    # the spec's `requests:`) or by another subsystem's worker (`worker: {requests: […]}`); the worker holding the unit
    # performs it on its next look, says so in its heartbeat (`fetched`), and the row is cleared by the console
    # (`w2cplatform/requests.py`). Not a unit of its own: a request has no duration to hold, no epoch to fence, nothing
    # to reconcile — it happens and it is over.
    #
    # A REQUEST HAS A DEADLINE, AND IT IS NEAR (feedback BI). Without `valid_until` it is refused; with one more than
    # `most_valid` away (the spec's number, which the loader requires wherever `valid_for` is declared) it is refused
    # too; a family that declares none has no deadline to judge near, and refuses them all. One that arrives after its
    # moment is EXPIRED, reported as such and cleared — never performed, never silently dropped.
    #
    # NOTHING LONG WHERE THE LEASES ARE RENEWED (feedback BE). `perform` is a call into whatever the subsystem holds,
    # and such a call has no timeout of ours: it is made on a thread of its own — the loop waits `PERFORM_GRACE` for it,
    # after `PERFORM_TIMEOUT` the request is answered "did not answer" and cleared, and while a call into a target has
    # not returned no second call is made into it. A worker that may no longer act for the unit does not act on it:
    # a fenced instance, or one whose lease on the unit is lost, leaves the request for whoever holds the unit now.
    #
    # AT MOST ONCE (the platform review). Before the target is called the worker says it is about to — a MARK,
    # `<sub>/commands/<id>`, written CREATE-ONLY: of two holders in the same second the store says which made it, and
    # the other answers `unknown`. A request that carries another instance's mark is not performed: it is answered
    # `unknown: an earlier instance … began it`, and a person decides. The answer goes into the mark once it is known
    # (`_confirm`), so an instance started after this one says it again rather than `unknown`. Marks of requests that
    # no longer exist are cleared every `MARK_SWEEP` seconds, by whichever worker gets there. A unit held with no lease
    # takes one before its first request, so a second holder fences the first.
    #
    # THE SUBSYSTEM SAYS ONLY WHAT ONE HOLDER KNOWS (ADR 0013): what it holds open now (`held_rows`), the key of what a
    # request against a row goes into (`request_target`: compared, never called — one call at a time into each), the call
    # (`perform`), and, if it has words of its own, how it names a unit moved since the request was given
    # (`moved_refusal`) and what group a row is in (`request_group`, the spec's `group_by` by default). The rest is this
    # class's and no hook: the fence (`writing_allowed`), the epoch taken before the first act and its rules (`take_epoch`:
    # nothing taken for a unit not on the assignment read last, nor for one the lease step let go since), and the two
    # kinds every holder writes, `command` and `command.failed`, with the unit's `of` (`events.COMMAND`).
    #
    # LOOKED AT FOUR TIMES A SECOND (2 October 2026) — `beat` — with every rule above, each row read ONCE, when it first
    # appears (the review's seventh pass, M5). THE ROAD IS MEASURED HERE, where it ends (`_measure`): `wait` from this
    # worker's first sight of the row to the call (one clock); `road` from the request's `at` (two clocks) and `request`
    # from its filing (two clocks), each by who asked (`by`: a subsystem's worker, `<sub>/…`, or an operator). HUNG TARGETS DO NOT HOLD THE LOOP
    # (the review's seventh pass, M7): `REQUESTS_HOLD` bounds a look, `budget` counts calls begun, and a target whose
    # last call did not answer inside `PERFORM_GRACE` is not waited for at all.
    PERFORM_GRACE, PERFORM_TIMEOUT = 0.2, 10.0
    MARK_SWEEP = 30.0
    ROAD_BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 300.0)
    COMMANDS_SUSTAINED, COMMANDS_BURST = 2.0, 16    # requests a second per holder: the design numbers of 2 October 2026
    HUNG_TARGETS = 200                              # targets hung at once a holder keeps its leases through (the test's)
    COMMANDS_PER_LOOK = HUNG_TARGETS                # every target of such a holder, asked at once, called in one look
    REQUESTS_HOLD = 0.5                             # seconds one `requests` call may hold the loop's thread
    FETCHED_BYTES = 8192                            # the answered ids one heartbeat carries, oldest first
    FETCHED_COUNT = COMMANDS_BURST * 10             # …at most so many: the burst, for the ten seconds between two heartbeats
    SKEW_SLACK = 1.0                                # a filing this much before our previous listing: the writer's clock is behind
    MARKS_OWED_PER_LOOK = 16
    REQUEST_TARGET = "the target"                   # what a refusal calls what was called: the subsystem's word
    CANNOT_MARK = ("this object store cannot write a request's mark create-only (no `put_new`): two holders of the "
                   "unit could both perform it, so neither does")

    def _requests_state(self) -> None:
        self.fetched: list[str] = []                     # requests answered — performed, refused or expired — while their row stands
        self.commands = {"performed": 0, "refused": 0, "expired": 0, "unknown": 0}
        # …by who asked: `operator`, or the subsystem whose worker filed it (its `by` stamp, `<sub>/<unit>`), as first seen
        self.road = {"operator": self._histogram()}                                      # the event's moment -> the call
        self.request_road = {"operator": self._histogram()}                              # the row's filing -> the call
        self.wait = {"buckets": [0] * len(self.ROAD_BUCKETS), "sum": 0.0, "count": 0}
        self._first_seen: dict[str, float] = {}          # request -> when a look first saw its row, by the clock
        self._requests_read: dict[str, tuple] = {}       # request -> (the unit it names, its fields if ours): read once (M5)
        self._marks_looked: set[str] = set()             # requests whose mark was read at their first sight (`_confirm`)
        self._appeared: dict[str, float] = {}            # request -> the wall time of the last listing that did not have it
        self._listed: tuple[float, set] | None = None    # (when, which requests) of the previous listing
        self._slow: set = set()                          # targets (their keys) whose last call did not answer inside `PERFORM_GRACE`
        self._performing: dict = {}                      # target key -> the one call in flight into it
        self.reanswered = 0                              # requests answered before by this slot, said again (`_answered_before`)
        self._beat_failed = False                        # the look between passes is failing: said once (`beat_once`)
        self._marks_swept = -1e18                        # when the marks of requests that are gone were last cleared
        self._marks_owed: dict[str, bytes] = {}          # request -> its answered mark, not yet taken by the store (`_confirm`)

    # Whether this worker's units take requests: its spec declares `requests:`.
    def serves_requests(self) -> bool:
        return bool(self.spec.requests or self.spec.requests_free)

    def serve_requests(self) -> None:
        self.requests()

    # What the subsystem gives: the rows of the units this worker holds now (`{id: row}`); the KEY of what a request
    # against one goes into (`request_target`) — anything comparable, one call at a time into each key, the unit itself
    # unless the subsystem says otherwise; None: not open yet, asked again on the next look; the call itself (`perform`,
    # handed that key); and how a refusal names a unit moved since the request was given.
    def held_rows(self) -> dict[str, dict]:
        return {}

    def request_target(self, row: dict):
        return str(row["id"])

    def perform(self, target, row: dict, it: dict) -> dict:
        raise NotImplementedError

    def moved_refusal(self, unit: str) -> str:
        return (f"unit {unit} was moved to another group after this request was given: it was not performed — give it "
                f"again if it is still wanted")

    # The group a unit is in, as the platform reads it from the spec (`placement.group_by`): what a request's `group` was
    # stamped with when the console asked for its rights — performed only in the group it was filed for.
    def request_group(self, row: dict) -> str:
        if not self.spec.group_by:
            return ""
        return self.spec.group_of(row.get(self.spec.group_by))

    # AN EVENT ABOUT A UNIT, under the epoch this worker holds for it, into the unit's bucket on this server's resource:
    # the platform's line. `None` when no epoch is held for it (not this worker's to speak of), the instance is fenced,
    # or the line was a repeat the spec's `events.suppress` swallows. Nothing else is told — no store write, no controller.
    #
    #   `occurred`     when the thing happened by the SOURCE's clock, where the caller knows it: kept out of the
    #                  suppressor's identity (a repeat is the same thing whatever that clock said) and put on the line
    #                  written; through `rows.number` — `nan`, `inf` or 400 digits drop the moment alone, counted
    #   suppression    the LAST thing before the write: whether this worker may speak of the unit does not change because
    #                  the same thing happened twice. The suppressor hands back this line, nothing, or the summary of a
    #                  window that just closed and then this line; the answer is the path of the LAST one written
    #   the class      `class_of` — `observation` unless the subsystem's worker says which kinds are alarms
    #
    # The suppressor is the spec's (`events.suppress`), and it was one subsystem's worker's: the key was loaded and checked
    # for every spec and applied for one. Its counters live in this process alone — the only one that sees the line before
    # it is a file, and the only one holding the epoch that makes the file writable.
    BUCKET_SECONDS = 600

    def observe(self, unit, kind: str, **fields) -> str | None:
        from .events import refuse_own_of
        from .rows import number
        refuse_own_of(self.sub.name, str(unit), fields)   # at once: a line the suppressor swallows is refused as well
        epoch = self.epochs.get(str(unit))
        if epoch is None or not self.resource_root or not self.writing_allowed:
            return None
        t = self.wall()
        occurred = number(f"{self.sub.name}/{unit}#occurred", fields.pop("occurred", None), default=None)
        lines = self.suppressor.lines(t, str(unit), kind, fields)
        if lines and occurred is not None:            # the observation is the last line; a summary before it has its own times
            lt, lk, lf = lines[-1]
            lines[-1] = (lt, lk, {**lf, "occurred": occurred})
        return self._write_lines(unit, epoch, lines, self.class_of(unit, kind))

    # The spec's suppressor, made at its first use.
    @property
    def suppressor(self):
        from .events import Suppressor
        s = self.__dict__.get("_suppressor")
        if s is None:
            s = self.__dict__["_suppressor"] = Suppressor(self.spec.suppress)
        return s

    @suppressor.setter
    def suppressor(self, s) -> None:
        self.__dict__["_suppressor"] = s

    # The traffic class of one line: `observation`; a subsystem's worker that knows which of a unit's kinds are alarms
    # says so (the platform fixes the two words, `events.py`).
    def class_of(self, unit, kind: str) -> str:
        return OBSERVATION

    def _write_lines(self, unit, epoch: int, lines, cls: str) -> str | None:
        log_ = self.event_log(unit, epoch)
        path = None
        for t, kind, fields in lines:
            path = log_.append(t, kind, cls, **fields)
        return path

    # A LINE ABOUT A UNIT, WRITTEN AS SAID — not suppressed, not fenced here: what a subsystem's worker writes beside
    # `observe` (an alarm of its own judging, the lines a pass of its work produced), under the epoch it holds for the
    # unit, or under the one it names (`epoch`: 0 for what no epoch fences — a keep's line, a volume's). Into the unit's
    # bucket on this server's resource, as `observe`'s; None when no epoch is held for it and none is named.
    def write_event(self, unit, t: float, kind: str, cls: str = OBSERVATION, *, epoch: int | None = None,
                    durable: bool = False, **fields) -> str | None:
        epoch = self.epochs.get(str(unit)) if epoch is None else epoch
        if epoch is None or not self.resource_root:
            return None
        return self.event_log(unit, epoch).append(t, kind, cls, durable, **fields)

    # The writer of a unit's lines under `epoch`, every line of it stamped with what the unit is about (`of`; the
    # product's `Worker.EventLog`). The ONE place a log's `of` is set (`EventLog._of`): a line that says its own is
    # refused by the log itself (`events.refuse_own_of`), whoever opened it.
    def event_log(self, unit, epoch: int):
        from .events import EventLog
        log_ = EventLog(self.resource_root, self.sub.name, str(unit), epoch, getattr(self, "bucket_seconds", self.BUCKET_SECONDS))
        log_._of = self.of(unit)
        return log_

    # WINDOWS THAT CLOSED WITH NOBODY LEFT TO CLOSE THEM — the storm stopped, so no observation came to carry the summary
    # out. Once a pass (`pump_once`), and wherever a subsystem drains its lines: without it a burst that ENDS is a burst
    # nobody ever counted. A summary goes under the epoch its window was opened under; a unit let go since, or a fenced
    # instance, drops it — a predecessor's storm is not written into a successor's bucket.
    def flush_suppressed(self) -> int:
        if not self.writing_allowed or not self.resource_root:
            return 0
        written = 0
        for unit, t, kind, fields in self.suppressor.flush(self.wall()):
            epoch = self.epochs.get(str(unit))
            if epoch is None:
                continue
            self._write_lines(unit, epoch, [(t, kind, fields)], self.class_of(unit, kind))
            written += 1
        return written

    # The farthest a deadline may be: the spec's `requests.most_valid`, and nothing else; None when it declares none.
    def most_valid(self) -> float | None:
        got = (self.spec.requests or {}).get("most_valid")
        return None if got is None else float(got)

    @staticmethod
    def _histogram() -> dict:
        return {"buckets": [0] * len(Worker.ROAD_BUCKETS), "sum": 0.0, "count": 0, "ahead": 0, "behind": 0}

    def _measure(self, rid: str, it: dict) -> None:
        from .rows import finite

        def count(h: dict, seconds: float) -> None:
            h["sum"] += seconds
            h["count"] += 1
            for i, le in enumerate(self.ROAD_BUCKETS):
                if seconds <= le:
                    h["buckets"][i] += 1

        def two_clocks(h: dict, since, behind_of: float | None = None) -> None:
            # `finite`, not `float`: a moment of 400 digits raised `OverflowError` past a `(TypeError, ValueError)`
            try:
                at = finite(since)
            except (TypeError, ValueError):
                return                                   # a row that does not say when: not counted here
            seconds = self.wall() - at
            if seconds < 0:
                h["ahead"] += 1                          # the writer's clock is ahead of this one: said, not hidden
            elif behind_of is not None and at < behind_of - self.SKEW_SLACK:
                h["behind"] += 1                         # filed "before" a listing that did not have it: its clock is behind
            count(h, max(0.0, seconds))

        count(self.wait, max(0.0, self.clock() - self._first_seen.pop(rid, self.clock())))
        stamp = str(it.get("by", ""))
        by = stamp.split("/", 1)[0] if "/" in stamp else "operator"   # a worker of a subsystem filed it, or a person did
        two_clocks(self.road.setdefault(by, self._histogram()), it.get("at"))
        filed = it.get("filed") if it.get("filed") not in (None, "") else (it.get("at") if by == "operator" else None)
        two_clocks(self.request_road.setdefault(by, self._histogram()), filed, self._appeared.pop(rid, None))

    def command_key(self, rid: str) -> str:
        return self.sub.command_key(rid)

    def began_by(self, rid: str) -> str | None:
        """The instance that said it was about to perform this request, or None."""
        mark = self.mark_of(rid)
        return None if mark is None else (str(mark.get("instance", "")) or "?")

    def mark_of(self, rid: str) -> dict | None:
        """The mark of this request as it stands, or None. Raises if the store does not answer."""
        raw = self.objects.get(self.command_key(rid))
        if raw is None:
            return None
        try:
            mark = json.loads(raw)
        except PARSE_ERRORS:                             # a mark that does not parse is still a mark (the eleventh review)
            return {"instance": "?"}
        return mark if isinstance(mark, dict) else {"instance": "?"}

    def sweep_marks(self) -> int:
        if self.clock() - self._marks_swept < self.MARK_SWEEP:
            return 0
        self._marks_swept = self.clock()
        prefix = self.sub.command_key("")
        marks = self.objects.list(prefix)                # the marks FIRST: a mark is written after its request,
        if not marks:                                    # so a mark listed here whose row is gone below is over
            return 0
        rows = {k.rsplit("/", 1)[1] for k in self.vars.list(self.sub.requests_prefix())}
        gone = [k for k in marks if k.rsplit("/", 1)[1] not in rows]
        for k in gone:
            self.objects.delete(k)
        return len(gone)

    # EVERY ANSWER, OLDEST FIRST, UNDER A CEILING (the review's seventh and eighth passes): as many as fit in
    # `FETCHED_BYTES` and at most `FETCHED_COUNT`, each said by its digest when it is long (`requests.said_id`, which the
    # console's clearing matches the same way) — a cursor that is the list itself.
    def fetched_said(self) -> str:
        from .requests import said_id
        out, size = [], 0
        for rid in self.fetched[:self.FETCHED_COUNT]:
            said = said_id(rid)
            size += len(said) + 1
            if size > self.FETCHED_BYTES:
                break
            out.append(said)
        return ",".join(out)

    # WHAT THE FAMILY SAYS IN THE HEARTBEAT, every holder's (the product's names; a spec's `metrics:` reads them): what was
    # answered (`fetched`, which the console's clearing reads), the outcomes counted, the answers said again, the calls
    # not back yet, and the road to the call as histograms since the process started (`_measure`). Each only once there
    # is something to say.
    def requests_fields(self) -> dict:
        return {**({"fetched": self.fetched_said()} if self.fetched else {}),
                **({"command_counts": dict(self.commands)} if any(self.commands.values()) else {}),
                **({"commands_reanswered": self.reanswered} if self.reanswered else {}),
                **({"commands_in_flight": len(self._performing)} if self._performing else {}),
                **({"command_road": self.road, "command_request": self.request_road, "command_wait": self.wait}
                   if self.wait["count"] else {})}

    def requests(self, budget: int | None = None, now: float | None = None) -> list[dict]:
        from .rows import finite
        budget = self.COMMANDS_PER_LOOK if budget is None else budget
        now = self.wall() if now is None else now
        held_from = time.monotonic()                     # the waits below are real seconds: so is their bound
        mine = self.held_rows()
        done: list[dict] = self._performed()             # what calls already in flight have come to
        base, again, from_calls, begun = len(done), 0, 0, []   # what this look acted on: answers given, calls begun
        self.sweep_marks()
        listed_at = self.wall()
        keys = sorted(self.vars.list(self.sub.requests_prefix()))
        # An answered request is remembered for as long as its ROW stands — the heartbeat carries it until the console
        # clears the row — and not after (the review's third pass, minor).
        present = {k.rsplit("/", 1)[1] for k in keys}
        self.fetched = [r for r in self.fetched if r in present]
        self._first_seen = {r: t for r, t in self._first_seen.items() if r in present}
        self._requests_read = {r: v for r, v in self._requests_read.items() if r in present}
        self._marks_looked &= present
        if self._marks_owed:
            self._confirm_owed(present)                  # answers the store did not take the first time (`_confirm`)
        self._appeared = {r: t for r, t in self._appeared.items() if r in present}
        if self._listed is not None:
            for r in present - self._listed[1]:
                self._appeared.setdefault(r, self._listed[0])
        self._listed = (listed_at, present)
        answered = set(self.fetched)
        in_flight = {c["rid"] for c in self._performing.values()}
        self._slow &= {t for t in map(self.request_target, mine.values()) if t is not None}   # a target let go is not slow
        for key in keys:
            if len(done) - base - again - from_calls + len(begun) >= budget:
                break                                    # this look has acted on its share: the rest is the next look's
            if time.monotonic() - held_from >= self.REQUESTS_HOLD:
                break                                    # …or held the loop as long as one look may
            rid = key.rsplit("/", 1)[1]
            if rid in answered or rid in in_flight:
                continue                                 # one we have answered, or one in flight: not even read
            got = self._requests_read.get(rid)           # (the unit it names, its fields if the unit is ours)
            if got is None or (got[0] in mine and got[1] is None):
                it, _ = self.vars.get(key)
                if not it:
                    continue
                unit_of = str(it.get("unit", ""))
                if "/" in unit_of and unit_of.split("/", 1)[0] == self.sub.name:
                    unit_of = unit_of.split("/", 1)[1]   # `<sub>/<id>`, as a subsystem's worker may file it
                got = self._requests_read[rid] = (unit_of, it if unit_of in mine else None)
            row = mine.get(got[0])
            if row is None:
                continue                                 # another worker's unit: its row was read once, when it appeared
            it = got[1]
            self._first_seen.setdefault(rid, self.clock())   # what `wait` is measured from (`_measure`)
            unit = str(row["id"])
            if not self.writing_allowed or (unit in self.leases and not self.may_act(unit)):
                continue                                 # not mine to act on now: fenced, or the lease is lost
            # ANSWERED BEFORE, BY THIS NAME (the review's seventh pass, M6): a mark that says how the call went is that
            # call's answer, said again so the row is cleared, and nothing else. Looked at once per row, at its first
            # sight, before the deadline: performed is not expired.
            unmarked = False                             # read just now, and no mark: not read again before the call
            if rid not in self._marks_looked:
                mark = self.mark_of(rid)                 # raises if the store does not answer: not known is not "nobody"
                self._marks_looked.add(rid)
                unmarked = mark is None
                if mark is not None and mark.get("outcome"):
                    self._answered_before(rid, row, mark, done)
                    again += 1                           # a read, not a call: not of the budget
                    continue
            # ONE ROW'S TROUBLE IS THAT ROW'S (the review's sixth and seventh passes): a deadline that is not a finite
            # number — a word, `nan`, `inf` — is that request's refusal, answered like the others here.
            try:
                until = finite(it.get("valid_until", 0) or 0)
            except (TypeError, ValueError):
                self._refused(rid, row, it, f"`valid_until` is not a time: {it.get('valid_until')!r}", done)
                continue
            if not until:
                self._refused(rid, row, it, "a command carries a deadline (`valid_until`): without one it would wait "
                                            "for its target for ever", done)
                continue
            most = self.most_valid()
            if most is None:
                self._refused(rid, row, it, "this family declares no `requests.most_valid`: no deadline can be judged near",
                              done)
                continue
            if until - now > most:
                self._refused(rid, row, it, f"`valid_until` is more than {most:.0f} s away: that is not a command", done)
                continue
            if now > until:
                self.fetched.append(rid)                 # say so, so it is cleared rather than asked again
                done.append({"request": rid, "unit": row["id"], "expired": True})
                self.commands["expired"] += 1
                log.warning("%s: request %s expired unperformed (%.0fs late)", self.name, rid, now - until)
                continue
            # RIGHTS ARE THE GROUP'S THE REQUEST WAS FILED FOR (the review's eighth pass, minor): the console asked them on
            # every unit of the group (`rights.reach.requests`) and stamped the group (`group`); a unit moved meanwhile is
            # not the unit the person had the right to command. A row with no `group` is performed as before.
            filed_for = str(it.get("group") or "")
            if filed_for and filed_for != self.request_group(row):
                self._refused(rid, row, it, self.moved_refusal(unit), done)
                continue
            target = self.request_target(row)
            if target is None:
                continue                                 # what it goes into is not open yet: ask again next look
            if target in self._performing:
                # A call this look began into the same target, not yet back: waited for — inside its own `PERFORM_GRACE`
                # and the look's `REQUESTS_HOLD` — so that two requests to a target that answers at once go in one look; a
                # target that does not answer is not waited for twice.
                ahead = self._performing[target]
                if target not in self._slow and any(c is ahead for c, _ in begun):
                    left = min(ahead["t0"] + self.PERFORM_GRACE, held_from + self.REQUESTS_HOLD) - time.monotonic()
                    if left > 0:
                        ahead["returned"].wait(left)
                    if ahead["returned"].is_set():
                        got_back = self._performed()
                        from_calls += len(got_back)
                        done += got_back
                    elif time.monotonic() - ahead["t0"] >= self.PERFORM_GRACE:
                        self._slow.add(target)
                if target in self._performing:
                    continue                             # a call into this target has not returned: wait your turn
            if unit not in self.leases:
                try:
                    self.take_epoch(unit)                # a unit acted on is a unit fenced: its epoch, before the first request
                except OSError:
                    raise                                # the store did not answer: not known, for every request
                except NotReadThisPass:
                    # Not on the assignment read last, or LET GO SINCE IT WAS READ (`lost_to_epoch`): not taken back
                    # between passes. Whether the unit is still mine is the pass's to say; until then, whoever holds it acts.
                    continue
                except Exception as e:                   # noqa: BLE001 — a garbled epoch row, or no slot: this request's refusal
                    self.epoch_errors[unit] = str(e)
                    self._refused(rid, row, it, f"its unit's epoch could not be taken: {e}", done)
                    log.error("%s: request %s not performed: the epoch of %s could not be taken (%s)", self.name, rid, unit, e)
                    continue
                self.epoch_errors.pop(unit, None)
            if not self.may_act(unit):
                continue                                 # taken and lost already, or not confirmed: whoever holds it now acts
            mark = None if unmarked else self.mark_of(rid)   # raises if the store does not answer
            if mark is not None and mark.get("outcome"):
                self._answered_before(rid, row, mark, done)      # answered meanwhile — by another holder of the unit
                again += 1
                continue
            before = None if mark is None else (str(mark.get("instance", "")) or "?")
            made = self._mark(rid, unit, now) if before is None else False
            if made is None:
                self._refused(rid, row, it, self.CANNOT_MARK, done)
                continue
            if before is None and not made:
                before = self.began_by(rid) or "?"       # somebody made the mark between our read and our write
            if before is not None:
                why = f"unknown: an earlier instance ({before}) began it, and whether it was acted on is not known"
                self.fetched.append(rid)
                done.append({"request": rid, "unit": row["id"], "error": why})
                self.commands["unknown"] += 1
                self._command_line(row, it, "unknown", error=why)
                log.warning("%s: request %s not performed — %s", self.name, rid, why)
                continue
            call = {"rid": rid, "row": row, "it": it, "at": self.clock(), "returned": threading.Event(), "answered": False,
                    "t0": time.monotonic()}

            def run(call=call, target=target):
                t0 = time.monotonic()
                try:
                    call["out"] = self.perform(target, call["row"], call["it"])
                except Exception as e:                   # noqa: BLE001 — the target's word, whatever it is
                    call["error"] = str(e)
                call["took"] = time.monotonic() - t0
                call["returned"].set()

            self._performing[target] = call
            in_flight.add(rid)
            self._measure(rid, it)                       # the road ends here: the call
            threading.Thread(target=run, daemon=True).start()
            begun.append((call, target))
        # The calls this look began, waited for TOGETHER, `PERFORM_GRACE` at most and never past `REQUESTS_HOLD`; one that
        # outlasts a whole `PERFORM_GRACE` names its target slow, and its answer is collected by a later look.
        if begun:
            deadline = min(time.monotonic() + self.PERFORM_GRACE, held_from + self.REQUESTS_HOLD)
            for call, target_id in begun:
                if target_id not in self._slow and deadline > time.monotonic():
                    call["returned"].wait(max(0.0, deadline - time.monotonic()))
            for call, target_id in begun:
                if not call["returned"].is_set() and time.monotonic() - call["t0"] >= self.PERFORM_GRACE:
                    self._slow.add(target_id)
            done += self._performed()
        return done

    # A request this slot had answered before — its mark says how — answered again so the row is cleared: into
    # `fetched`, and nowhere else (no event, no outcome counted twice; `reanswered` in the heartbeat).
    def _answered_before(self, rid: str, row: dict, mark: dict, done: list) -> None:
        self.fetched.append(rid)
        self.reanswered += 1
        done.append({"request": rid, "unit": row["id"], "answered": str(mark.get("outcome")),
                     "by": str(mark.get("slot") or mark.get("instance") or "?")})
        log.info("%s: request %s was answered before (%s, by %s): said again, not performed", self.name, rid,
                 mark.get("outcome"), mark.get("slot") or mark.get("instance"))

    # The answer, written into the mark once the target has said it. A store that does not take the write: the mark is
    # OWED (`_marks_owed`) and written again at every look until it does, or the row is gone (the review's eighth pass).
    def _confirm(self, rid: str, row: dict, outcome: str, it: dict, late: bool = False) -> None:
        mark = canonical_json({"instance": self.instance, "slot": self.name, "unit": str(row["id"]),
                               **self._of_said(row["id"]), "outcome": outcome, "action": str(it.get("action", "")),
                               "at": self.wall(), **({"late": True} if late else {})}).encode()
        try:
            self.objects.put(self.command_key(rid), mark)
            self._marks_owed.pop(rid, None)
        except Exception as e:                           # noqa: BLE001
            self.store_errors += 1
            self._marks_owed[rid] = mark
            log.warning("%s: the answer to request %s could not be written into its mark (%s); written again at the next "
                        "look", self.name, rid, e)

    def _confirm_owed(self, present: set) -> int:
        self._marks_owed = {r: m for r, m in self._marks_owed.items() if r in present}   # a row gone: its mark is swept
        wrote = 0
        for rid, mark in list(self._marks_owed.items())[:self.MARKS_OWED_PER_LOOK]:
            try:
                self.objects.put(self.command_key(rid), mark)
            except Exception:                            # noqa: BLE001 — still not taking it: the next look
                self.store_errors += 1
                break
            del self._marks_owed[rid]
            wrote += 1
        return wrote

    # The mark, create-only (`put_new`): `True` when this instance made it, `False` when somebody else did; a store
    # WITHOUT create-only answers `None`, and the request is refused (the review's third pass) — "not performed, and a
    # person is told why" is better than "perhaps twice".
    def _mark(self, rid: str, unit: str, now: float) -> bool | None:
        put_new = getattr(self.objects, "put_new", None)
        if put_new is None:
            return None
        mark = canonical_json({"instance": self.instance, "slot": self.name, "unit": unit, **self._of_said(unit), "at": now})
        return bool(put_new(self.command_key(rid), mark.encode()))

    # …and a mark says it too, as a line does (`of`): what was done to a unit is about what the unit is about. Absent for a
    # unit about nothing but itself.
    def _of_said(self, unit) -> dict:
        of = self.of(unit)
        return {OF: of} if of else {}

    # What the calls in flight have come to: performed, refused, or — after `PERFORM_TIMEOUT` — not answered. A call
    # that timed out is answered ONCE and stays in flight until it returns: the target is busy for as long as it is.
    def _performed(self) -> list[dict]:
        done = []
        for key, call in list(self._performing.items()):
            rid, row, it = call["rid"], call["row"], call["it"]
            if call["returned"].is_set():
                del self._performing[key]
                if call.get("took", 0.0) <= self.PERFORM_GRACE:
                    self._slow.discard(key)              # it answered at once
                if call["answered"]:
                    # IT CAME BACK AFTER WE HAD SAID IT DID NOT ANSWER (the architect's decision; the product's
                    # `request-holder`): the request keeps that answer and its row is not touched, but the MARK says what
                    # was really done — so the next instance says it again rather than `unknown` — and `late`, which tells
                    # an execution past `PERFORM_TIMEOUT` (an incident) from an ordinary one.
                    outcome = "refused" if "error" in call else "performed"
                    self._confirm(rid, row, outcome, it, late=True)
                    self._command_line(row, it, outcome, reply=call.get("out"), error=call.get("error"), late=True)
                    log.warning("%s: request %s was %s by %s after it had been answered as not answering (%.1f s)",
                                self.name, rid, outcome, self.REQUEST_TARGET, call.get("took", 0.0))
                    continue
                if "error" in call:
                    self._refused(rid, row, it, call["error"], done)
                    self._confirm(rid, row, "refused", it)
                else:
                    self.fetched.append(rid)
                    done.append({"request": rid, "unit": row["id"], **call["out"]})
                    self.commands["performed"] += 1
                    self._confirm(rid, row, "performed", it)
                    self._command_line(row, it, "performed", reply=call["out"])   # what was done to a unit: an event of it
            elif not call["answered"] and self.clock() - call["at"] >= self.PERFORM_TIMEOUT:
                call["answered"] = True
                self._refused(rid, row, it, f"{self.REQUEST_TARGET} did not answer", done)
        return done

    # THE LINE OF WHAT WAS DONE, in the platform's fields — the ones the console module reads (its contract, §5):
    # `outcome` (performed | refused | unknown), `action`, `by` (who asked), `late` (the target answered after the request
    # had been answered "did not answer"), `error` for what was not done; the target's own answer whole under `reply`, so
    # nothing a target says can stand where a platform field does. `command` for what was performed, `command.failed` for
    # the rest; the unit's `of` is the log's (`event_log`).
    def _command_line(self, row: dict, it: dict, outcome: str, reply: dict | None = None, error: str | None = None,
                      late: bool = False) -> None:
        by = str(it.get("by") or "")
        self.observe(row["id"], COMMAND if outcome == "performed" else COMMAND_FAILED, outcome=outcome,
                     action=str(it.get("action", "")), **({"by": by} if by else {}), **({"late": True} if late else {}),
                     **({"error": error} if error else {}), **({"reply": reply} if reply is not None else {}))

    def _refused(self, rid: str, row: dict, it: dict, why: str, done: list) -> None:
        self.fetched.append(rid)                         # a refusal is an answer: do not ask for ever
        done.append({"request": rid, "unit": row["id"], "error": why})
        self.commands["refused"] += 1
        self._command_line(row, it, "refused", error=why)
