"""autoworker — the seventh subsystem's worker: the one that READS.

Every worker before it observed the world and wrote down what it saw. This one
reads what they wrote, decides that a scenario fired, and asks somebody else to
act — by filing a request, never by touching a device.

    AUTO_NAME / SLOT_INDEX     -> the slot to claim: a-<index>
    SERVER_NAME (or hostname)  -> `server` in the heartbeat
    RESOURCE_ROOT              -> where its own events and its cursor live

Three things carry the whole design, and each one is a decision that could have
gone the other way:

  1. NO STATE MACHINE. "A and B within thirty seconds" is not "saw A, waiting
     for B" — it is a question asked of the last thirty seconds of the log,
     re-asked every pass. There is nothing to keep, nothing to restore and
     nothing to get wrong after a crash.
  2. A CURSOR, not a queue. `Frontier` — the platform's reader's number (`w2cplatform/events.py`), the same file
     — says how far this scenario has been considered. It is the only thing
     written down.
  3. A DETERMINISTIC REQUEST ID. Delivery is at-least-once by construction, so
     a firing computed twice must be the same row: `<scenario>-<millisecond of
     the event that completed it>`. Written twice is written once; performed
     once by the holder.
"""
from __future__ import annotations

import logging
import math
import os
import time

from w2cplatform import runtime
from w2cplatform.doors import unit_ref
from w2cplatform.worker import Worker
from w2cplatform.eventdatabase import MergedIndex
from w2cplatform.events import EventLog
from w2cplatform.variables import Variables

from .auto import Catalog, fires, refusal
from .config import AUTO_SPEC
from w2cplatform.events import Frontier
from w2cplatform.rows import PARSE_ERRORS

log = logging.getLogger("autoworker")
AUTO = AUTO_SPEC.sub


# What the catalog reads, read once per ordinary pass (the review's seventh pass, the sweep beside M8). `Catalog.check`
# runs per scenario, and a trigger that names no camera lists and reads EVERY camera — so ten such scenarios were ten
# listings of the cameras and ten reads of each, every pass. Within one pass the answer cannot be more than a pass
# old anyway; it is asked of the store once, and the store's word is not kept past the pass.
class _OnePass:
    def __init__(self, vars_):
        self.vars, self._got, self._listed = vars_, {}, {}

    def get(self, key):
        if key not in self._got:
            self._got[key] = self.vars.get(key)
        return self._got[key]

    def list(self, prefix, *a, **kw):
        if prefix not in self._listed:
            self._listed[prefix] = self.vars.list(prefix, *a, **kw)
        return self._listed[prefix]


class AutoWorker(Worker):
    """`name` is a slot (`a-1`); `index` is the merged event log — the console's
    own reader, because a scenario watches what the console shows."""

    # How far back a scenario looks when it has never run, and the most it re-reads after being down. Not
    # "everything since the beginning": a scenario started this morning must not fire on yesterday's door.
    COLD_START = 300.0
    # Firings filed in one pass, per scenario. A sensor that bounced two hundred times while this worker
    # was restarting is not two hundred doors — it is a bounce, and the rate ceiling below says so; this
    # one keeps a single pass bounded whatever the log holds.
    PER_PASS = 4
    # The road from an event to the request filed for it, counted since this process started, in these buckets
    # (seconds) — a histogram, because the longest road of the LAST pass says nothing about a slow one between
    # two scrapes (feedback AY): the pass after it filed nothing and said 0.
    LATENCY_BUCKETS = (1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 300.0)
    # How long a firing id is remembered after it is filed. Long enough that the same event, still inside
    # somebody's window, is not filed twice; short enough to be a handful of strings.
    REMEMBER = 900.0
    # How far BEHIND `now` the cursor is allowed to stop, and the reason there is a distance at all: the
    # merge is not a stream this process reads. A line's `t` is its WRITER's clock at the moment it wrote, and
    # the line is in an answer only later: after it reached the file, by a clock that may run behind this
    # one's, from a peer's copy when its own server is silent. A cursor set to `now`
    # is already past it, and `t <= since` then skips it FOR EVER — no refusal, no log line, just a
    # scenario that does not fire, which is the most expensive silence in this subsystem.
    #
    # The asymmetry decides the number: re-reading a stretch costs a comparison (the firing ids are
    # deterministic and the ones just filed are still remembered), running ahead costs a firing. Five
    # seconds was chosen against the three-second tail a resource read its files by until 28 September; the
    # index stats the files on every query now, and the distance stays for the clocks.
    SETTLE = 5.0
    # Rows per (subsystem, kind) query. The index now keeps the NEWEST end of an overflowing window and
    # says `truncated` when it had to cut, so this is a budget rather than a trap — but a scenario still
    # wants its window whole, and one query per kind is what keeps it that way.
    PER_KIND = 500

    spec = AUTO_SPEC                  # its spec: the platform executes every key of it (`slot`, `lease`, …)

    def __init__(self, name: str | None, vars_: Variables, objects, index=None, capacity: int | None = None,
                 clock=time.monotonic, wall=time.time, server: str | None = None,
                 resource_root: str | None = None, env: dict | None = None, catalog: Catalog | None = None):
        env = dict(os.environ if env is None else env)
        super().__init__(AUTO, None, vars_, objects, clock=clock, wall=wall, resource_root=resource_root, env=env)
        self.claim_at_start(name, env)   # a spare: an offer
        self.capacity = capacity if capacity is not None else int(env.get("CAPACITY", "50"))
        self.server = runtime.server(env, server)
        self.labels = runtime.labels(env)
        # The same reader the console uses, for the same reason: a scenario watches what an operator would
        # see on the timeline. One merge, one definition of "the events of the last minute".
        self.index = index or MergedIndex(objects, wall=wall)
        # What the units say and do — the same check the console made when the scenario was written, made
        # again every pass, because the answer can change after it: a camera replaced by one without a
        # telemetry, a detector deleted, a device finally held and describing itself for the first time.
        self.catalog = catalog if catalog is not None else Catalog(vars_)
        self.fired: dict[str, float] = {}            # firing id -> when it was filed (the replay guard)
        self.holes: dict[str, dict] = {}             # scenario -> what its last window was missing
        self.gave_up: dict[str, dict] = {}           # scenario -> the servers it stopped waiting for
        self.held_from: dict[str, float] = {}        # scenario -> when (by the clock) its window first came back incomplete
        self.said_without: set[str] = set()          # scenarios that said `decided_without` for the gap they are in
        self.cut: dict[str, list] = {}               # scenario -> the kinds whose answer did not fit its window
        self.late_by_unit: dict[str, int] = {}       # scenario -> firings its last pass did not file (late)
        self.suppressed_by_unit: dict[str, int] = {} # scenario -> firings its last pass refused: over its ceiling
        self.suppressed = 0                          # …and all of them, since this process started
        self.pass_failures = 0                       # passes that raised
        # One pass's answers, per (subsystem, kind): asked ONCE for every scenario watching that kind, over the
        # longest window any of them needs (`reconcile_once`). And what the pass cost — said in the heartbeat,
        # because a slow pass is otherwise visible nowhere: its seconds, its queries, how far the furthest
        # cursor trails `now`, and the longest road from an event to the request it filed.
        self._asked: dict[tuple[str, str, str], dict] = {}
        self._needed: dict[tuple[str, str, str], float] = {}
        self._watched: set[tuple[str, str, str]] = set()   # (subsystem, kind, unit) of every trigger held: what `wants` says
        self.wants_folded = 0                         # triples folded to their kinds for the long poll (`wants`), 0: none
        self._keys_of: dict[str, set] = {}            # scenario -> its triggers' keys (last full pass): what an answer touches
        self._fit: dict[str, tuple] = {}              # scenario -> (misfit, unchecked), as of the last full pass
        self._pass_reads = None
        self.pass_stats = {"pass_seconds": 0.0, "queries": 0, "lag_seconds": 0.0, "latency_seconds": 0.0}
        self.latency = {"buckets": [0] * len(self.LATENCY_BUCKETS), "sum": 0.0, "count": 0}
        self.late = 0                                 # firings not filed: their request was expired before it left
        self.recent: dict[str, list[float]] = {}     # scenario -> firing times inside the last minute
        self.filed = 0
        self.status_by_unit: dict[str, dict] = {}

    # -- the rows ---------------------------------------------------------------------------------
    def scenario(self, unit: str) -> dict | None:
        it, _ = self.vars.get(AUTO.config(AUTO_SPEC.rows, str(unit)))
        return AUTO_SPEC.row(it) if it and it.get("deleted") != "true" else None

    # -- the pass ---------------------------------------------------------------------------------
    # One pass over the scenarios this worker was assigned. Everything else in this file is called from
    # here, and the order is the argument: take the epoch (one evaluator per scenario, fenced like any
    # writer), read the window, decide, file, then move the cursor — never before the filing, or a crash
    # between the two would lose the firing instead of repeating it.
    #
    # AN EARLY PASS IS FOR WHAT WAS TOUCHED (the review's seventh pass, M8). `only` is what the resources' answers said
    # changed — `(subsystem, kind, unit)` (`LongPoll.take_touched`) — and the pass evaluates the scenarios a trigger of
    # which it touches, and reads no other scenario's row: an `io.input` on camera 777 twenty times a second was twenty
    # full passes over every scenario, a query each, for a scenario on camera 1 that nothing had happened to. `None` is
    # the ordinary pass, over all of them; the loop makes one at least every `poll` whatever the answers (`run`).
    def reconcile_once(self, now: float | None = None, only: set | None = None) -> list[str]:
        now = self.wall() if now is None else now
        started = self.clock()
        acted: list[str] = []
        units = sorted(self.assignment().units)
        # A SCENARIO THAT WENT AWAY IS LET GO (the product's cross-check, after the twelfth review). Its epoch and lease
        # stayed: renewed for a scenario another evaluator decided, and when it came back the pass decided under the
        # epoch of its first stay — `running` — though the other evaluator had taken the next one meanwhile, until a
        # lease step found it fenced. Gone from the assignment read now, it is released here, as the detector, the
        # scan, the survey and the gateway release theirs; back, it is taken under a new epoch.
        for gone in [u for u in self.epochs if u not in units]:
            self.release(gone)
            for said in (self.status_by_unit, self.holes, self.held_from, self.gave_up, self.cut, self._fit):
                said.pop(gone, None)
            self.said_without.discard(gone)
        if only is not None:
            units = [u for u in units if any(self._touches(k, t) for k in self._keys_of.get(u, ()) for t in only)]
        rows = {}
        for u in units:
            try:
                rows[u] = self.scenario(u)
                self.row_parsed(u)
            except PARSE_ERRORS as e:    # its row does not parse: this scenario's trouble (`row_garbled`) — `RecursionError` too (the tenth pass)
                rows[u] = None
                self.status_by_unit[u] = {"id": u, "phase": "failed", "why": self.row_garbled(u, e)}
        self._plan(rows, now, partial=only is not None)
        self.pass_stats.update(queries=0, lag_seconds=0.0, latency_seconds=0.0)
        self.pass_refused = False
        self._pass_reads = None                      # the catalog's reads of this pass (`_OnePass`), made on first use
        for unit in units:
            row = rows[unit]
            if row is None:
                continue
            if not row["enabled"]:
                self.status_by_unit[unit] = {"id": unit, "phase": "pending", "why": "disabled"}
                continue
            if unit not in self.epochs:
                # Its epoch is this scenario's trouble (the review's fifth pass): a garbled `auto/epoch/<unit>` raised out
                # of the pass, and no scenario after it was decided — every pass, and nowhere said.
                try:
                    self.take_epoch(unit)            # its own events — "this scenario fired" — need one writer
                except Exception as e:               # noqa: BLE001
                    self.status_by_unit[unit] = {"id": unit, "phase": "failed", "why": f"its epoch could not be taken: {e}"}
                    log.error("%s: %s not evaluated: its epoch could not be taken: %s", self.name, unit, e)
                    continue
            if not self.may_act(unit):             # the lease says another instance has it: decide nothing…
                # …and say so. The status of the last pass this instance made would otherwise stay, and say
                # `holding` for a window this instance no longer asks for (feedback AV). What it was waiting
                # for goes too: taken back later, it starts waiting afresh, not five minutes into a wait.
                self.status_by_unit[unit] = {"id": unit, "phase": "waiting", "why": "its lease is not this instance's"}
                self.holes.pop(unit, None)
                self.held_from.pop(unit, None)
                self.said_without.discard(unit)
                continue
            # WHAT ONLY THIS EVALUATOR CAN SAY OF A SCENARIO (the boundary's step 6, the owner's decision 3): the shape is
            # the spec's JSON Schema, checked at the door; that two triggers need `within`, and that what it asks of a
            # device the device can do (`auto.refusal`, `Catalog.check`), is judged here — on the ordinary pass, and an
            # early one says what that found (the check reads the catalog: every camera, for a trigger that names none).
            # Such a scenario is REFUSED — not fired, `refused` with why in the heartbeat — where it was refused at the
            # door by a controller of the VMS's own. What the catalog cannot check yet stays `unchecked`, and runs.
            if only is None or unit not in self._fit:
                real = getattr(self.catalog, "vars", None)
                if real is not None:
                    self._pass_reads = self._pass_reads or _OnePass(real)
                    self.catalog.vars = self._pass_reads
                try:
                    misfit, unsure = self.catalog.check(row)
                    self._fit[unit] = (refusal(row) + misfit, unsure)
                finally:
                    if real is not None:
                        self.catalog.vars = real
            misfit, unsure = self._fit[unit]
            if misfit:
                self.status_by_unit[unit] = {"id": unit, "phase": "refused", "why": "; ".join(misfit), "unfit": misfit,
                                             **({"unchecked": unsure} if unsure else {})}
                self.holes.pop(unit, None)
                continue
            try:
                n = self.evaluate(row, now)
            except Exception as e:                   # noqa: BLE001 — a resource that stopped answering mid-pass
                self.status_by_unit[unit] = {"id": unit, "phase": "waiting", "why": str(e)}
                log.warning("%s: %s not evaluated: %s", self.name, unit, e)
                continue
            holes = self.holes.get(unit) or {}
            self.pass_refused = self.pass_refused or any(str(why).startswith("did not answer") for why in holes.values())
            self.status_by_unit[unit] = {"id": unit, "phase": "running", "fired": n,
                                         **({"holding": holes} if holes else {}),
                                         **({"cut": self.cut[unit]} if self.cut.get(unit) else {}),
                                         **({"late": self.late_by_unit[unit]} if self.late_by_unit.get(unit) else {}),
                                         **({"suppressed": self.suppressed_by_unit[unit]} if self.suppressed_by_unit.get(unit) else {}),
                                         **({"decided_without": self.gave_up.pop(unit)} if unit in self.gave_up else {}),
                                         **({"unchecked": unsure} if unsure else {})}
            if n:
                acted.append(unit)
        self.pass_stats["pass_seconds"] = round(self.clock() - started, 3)
        return acted

    # Where each scenario's window begins — the cursor, bounded by `COLD_START`, less the scenario's own
    # `within` — so a pass can ask each (subsystem, kind, unit) ONCE, from the earliest start any scenario
    # watching it needs, instead of once per scenario (the notes on the event log's load: "the product, not
    # the sum").
    #
    # The UNIT is in the key, and that was measured (`tests/load_events.py`): asked across all units, one kind
    # on twenty cameras writing a line every ten seconds filled the 500-row window, and the loud cameras cut
    # the quiet one a scenario was watching. A trigger that names its unit gets a query for that unit — one
    # no other camera can crowd, and for the index the cheapest there is: it opens that unit's files and no
    # others. Scenarios on the same unit and kind still share it; a trigger naming no unit shares the kind's.
    def _since(self, row: dict, now: float) -> float:
        since = Frontier(self.resource_root, AUTO.name, str(row["id"])).read()
        return now - self.COLD_START if since is None else max(since, now - self.COLD_START)

    # An early pass (`partial`) plans for the scenarios it evaluates and leaves what is watched as the last ordinary
    # pass found it: the scenarios it did not read are still held, and still watched.
    def _plan(self, rows: dict, now: float, partial: bool = False) -> None:
        self._asked, self._needed = {}, {}
        watched: set[tuple[str, str, str]] = set()
        keys_of: dict[str, set] = {}
        for unit, row in rows.items():
            if row is None or not row["enabled"]:
                continue
            t0 = self._since(row, now) - float(row.get("within") or 0)
            keys_of[unit] = set(self._keys(row))
            for key in keys_of[unit]:
                self._needed[key] = min(self._needed.get(key, t0), t0)
                watched.add(key)
        if not partial:
            self._watched, self._keys_of = watched, keys_of
            self._fit = {u: f for u, f in self._fit.items() if u in keys_of}

    # Whether a line of `seen = (subsystem, kind, unit)` is one a trigger keyed `key` may fire on: the same kind, and
    # the unit it names — or any unit, for a trigger that names none.
    @staticmethod
    def _touches(key: tuple, seen: tuple) -> bool:
        return key[0] == seen[0] and key[1] == seen[1] and (not key[2] or key[2] == seen[2])

    # What this evaluator asks the resources to tell it about (`Worker.wants`, `w2cplatform/longpoll.py`): the
    # `(subsystem, kind, unit)` of every trigger of every scenario it holds, as of its last pass. A line of such a
    # kind, appended on a resource for that unit, answers the request this evaluator holds there, and the next pass
    # begins now; a line of another kind or another unit answers nobody. A trigger that names no unit is `""`: any
    # unit's line of its kind answers it. When the scenarios change, the next request carries the new list.
    #
    # THE UNIT IS IN THE WANT (the review's seventh pass, M8). It was not — "the list stays a handful" — and a site
    # with one busy camera kept every evaluator in four passes a second, each a query per kind to every resource: eight
    # times the queries of the ordinary pass, up against `EVENTS_INFLIGHT`, whose refusals hold the cursors.
    #
    # …AND FOLDED TO ITS KINDS PAST `WANTS_MAX` (the review's eighth pass, part 3): more triples than one request may name
    # were refused at every request, and the long poll was off for good with 65 scenarios. Folded (`longpoll.fold`), the
    # request is held for those kinds on any unit; how many triples were folded is in the heartbeat (`wants_folded`) and
    # on `/metrics` (`auto_wants_folded`).
    def wants(self) -> list[tuple[str, str, str]]:
        from w2cplatform.longpoll import WANTS_MAX, fold
        out, folded = fold(self._watched)
        if folded != self.wants_folded:
            if folded:
                log.warning("%s: its triggers watch %d (subsystem, kind, unit), more than the %d one request names: %s",
                            self.name, folded, WANTS_MAX,
                            f"folded to {len(out)} kinds on any unit" if out else "more kinds than that too — no wait is "
                            "held, the pass looks every poll")
            self.wants_folded = folded
        return out

    # The resources this evaluator's index asks — the same list, read the same way (`MergedIndex.seen`, cached
    # there): those live by their heartbeats, each with the address its `/events` is asked at. The long poll is
    # held at that address and no other. An index that keeps no such list (a test's) has nowhere to hold one.
    def _resources(self) -> dict[str, str]:
        seen, live = getattr(self.index, "seen", None), getattr(self.index, "live", None)
        if seen is None or live is None:
            return {}
        got = seen()
        return {s: str(got[s].get("url") or "") for s in live(got)}      # live as the index judges it (r29-writers2)

    # Called by the process before `run`: ask the resources to say when an event a scenario watches is written,
    # instead of finding it at the end of a two-second wait. `LONG_POLL=0`: not asked, the loop as it was.
    def watch_events(self, env: dict | None = None):
        return self.poll_events(self._resources, env)

    @staticmethod
    def _keys(row: dict) -> list[tuple[str, str, str]]:
        return sorted({(str(t.get("sub", "")), str(t.get("kind", "")), str(t.get("unit") or "")) for t in row["when"]})

    def _ask(self, sub: str, kind: str, unit: str, t0: float, t1: float) -> dict:
        key = (sub, kind, unit)
        have = self._asked.get(key)
        if have is None or have["t0"] > t0 or have["t1"] < t1:
            start = min(t0, self._needed.get(key, t0))
            # A trigger names its unit inside its subsystem; the index takes a unit as the platform names one.
            rep = self.index.query(max(0.0, start), t1, subsystem=sub, kind=kind, unit=unit_ref(sub, unit) if unit else None,
                                   limit=self.PER_KIND)
            self.pass_stats["queries"] += 1
            have = self._asked[key] = {"t0": start, "t1": t1, "rep": rep}
        return have["rep"]

    # One scenario against the log. Returns how many firings were filed.
    def evaluate(self, row: dict, now: float) -> int:
        unit = str(row["id"])
        front = Frontier(self.resource_root, AUTO.name, unit)
        since = front.read()
        held = self.held_from.get(unit)
        if held is not None and now - held > self.COLD_START and self.holes.get(unit) and unit not in self.said_without:
            self.gave_up[unit] = self.holes[unit]    # held as long as it may: decided without them from here
            self.said_without.add(unit)              # said once for this gap, not once a pass
            log.warning("%s: %s waited %.0fs for %s; deciding without them", self.name, unit, now - held,
                        ", ".join(sorted(self.holes[unit])))
        since = now - self.COLD_START if since is None else max(since, now - self.COLD_START)
        window = float(row.get("within") or 0)
        # Read back far enough to answer the question, not far enough to answer it twice: the window is
        # how much history a firing may span, and `since` is how much of it is new.
        events, holes = self.window(row, since - window, now)
        self.pass_stats["lag_seconds"] = max(self.pass_stats["lag_seconds"], round(now - since, 3))
        # Two ways a firing is not filed on this pass, and they are not the same thing (feedback BG; the review
        # called both "lost without a trace", and both were):
        #
        #   more than PER_PASS    a QUEUE, not a refusal. The cursor stops just before the first firing not
        #                         filed, and the next pass files it. It used to move on, and the firing was gone
        #   over the ceiling      a refusal, by design — and counted: each is marked decided, so a pass over the
        #                         same window does not count it again; the worker says how many (`suppressed`),
        #                         and the scenario's own log gets ONE line with the number and the span
        fired, late, queued_at, refused = 0, 0, None, []
        for fid, at, written in self.firings(row, events, since):
            if fid in self.fired:
                continue                             # already filed, or refused; the id is the same either way
            if fired >= self.PER_PASS:
                queued_at = written                  # the cursor is in written time
                break
            if not self.allowed(row, now):
                self.fired[fid] = now
                refused.append(at)
                continue
            late += not self.file(row, fid, at)
            fired += 1
        if refused:
            self.suppressed += len(refused)
            log.warning("%s: %s is over its ceiling of %s/min — %d firing(s) not filed", self.name, unit,
                        row["rate_per_minute"], len(refused))
            if unit in self.epochs:
                EventLog(self.resource_root, AUTO.name, unit, self.epochs[unit]).append(   # written now; about then
                    now, "suppressed", occurred=max(refused), scenario=unit, count=len(refused),
                    since=min(refused), until=max(refused))
        self.late_by_unit[unit], self.suppressed_by_unit[unit] = late, len(refused)
        self.forget(now)
        # The cursor moves only past a window that was WHOLE. A server that did not answer, a resource that
        # was rebuilding after a restart, a silent one answered by its peer's copies (which never hold the
        # open bucket): each makes the window short, and moving past it would lose, for ever, whatever that
        # server holds — the most expensive silence there is, exactly as for an event not yet in the merge.
        # So the cursor stays and the same window is asked again next pass; what fired from its known part is
        # filed already and is not filed twice (`fired`, the deterministic id).
        #
        # Not for ever: `since` never trails `now` by more than `COLD_START`, so a server that does not come
        # back holds a scenario for five minutes at most — and then the scenario SAYS it decided without it.
        #
        # Five minutes counted by the clock, from the pass that first found the window incomplete — not from
        # where that window began (feedback AV). A scenario with no cursor yet starts its window
        # `COLD_START` back already, and counted from there it "gave up" on the very next pass, two seconds
        # into the wait. The cursor stands still meanwhile, so the window starts losing its old edge about
        # `COLD_START` after this moment: that is the honest point to say so.
        self.holes[unit] = holes
        if holes:
            self.held_from.setdefault(unit, now)
        else:
            self.held_from.pop(unit, None)
            self.said_without.discard(unit)
            to = max(since, now - self.SETTLE)        # …and never further than the log has caught up to
            if queued_at is not None:                 # …nor past a firing still waiting its turn
                to = max(since, min(to, math.nextafter(queued_at, -math.inf)))
            front.set(to)
        return fired

    # The events to decide on — ONE QUERY PER KIND THE SCENARIO WATCHES, and that is not an optimisation.
    #
    # A single "everything in the last five minutes" overflows on a busy box: three cameras writing a
    # statistics line every few seconds fill a thousand rows in a five-minute window. The index used to
    # answer such a window `ORDER BY t LIMIT n` and drop the NEWEST end — the end a scenario cares about —
    # with no refusal and no log line, so the language got blamed. It keeps the newest end now, but that
    # only changes WHICH events are lost: a scenario asking a broad window on a loud box would still be
    # deciding on part of one.
    #
    # The trigger already names the subsystem and the kind. Letting the query name them too means the
    # window holds only what this scenario is looking at, and there are at most `MAX_TRIGGERS` of them.
    #
    # And when a window still comes back cut, SAY SO: a decision taken on truncated data must not look
    # like a decision taken on all of it.
    #
    # And what the window is MISSING (`holes`: server -> why), from the merge's `complete` — a window a server
    # did not answer for is not a window with nothing in it.
    def window(self, row: dict, t0: float, t1: float) -> tuple[list[dict], dict[str, str]]:
        out, full, holes = [], [], {}
        for sub, kind, u in self._keys(row):
            rep = self._ask(sub, kind, u, t0, t1)                 # asked once this pass, for every scenario on this unit and kind
            holes.update(rep.get("incomplete") or {})
            rows = rep.get("events", [])
            evs = [e for e in rows if t0 <= float(e.get("t", 0)) < t1 and not e.get("fenced")]
            # Cut FOR THIS SCENARIO only if the cut reached into its window. The shared answer spans the longest
            # window any scenario needs and keeps its newest end; a scenario looking at the last minute of an
            # hour-long answer lost nothing when the hour's first minutes were dropped.
            oldest = float(rows[0]["t"]) if rows else t1
            if rep.get("truncated") and oldest > t0:              # the index's own answer, not a guess from the count:
                full.append(f"{sub}.{kind}" + (f"@{u}" if u else ""))   # fencing drops rows AFTER the cut, so a window that
                                                                  # WAS cut can still come back short of the limit
            out += evs
        self.cut[str(row["id"])] = full
        if full:
            log.warning("%s: %s — the window came back full for %s; a firing may have been cut off its "
                        "oldest end", self.name, row["id"], ", ".join(full))
        out.sort(key=lambda e: float(e.get("t", 0)))
        return out, holes

    # Which firings this scenario has, newest first — `(id, when)`.
    #
    # The completing event decides. For one trigger that is every matching event; for several it is an
    # event that matches one of them and has a partner for each of the others inside the window ending at
    # it. Asking it this way is what removes the state machine: the same question, asked of the same log,
    # gives the same answer on every pass, whoever is asking and however many times they have restarted.
    #
    # TWO TIMES, AND EACH HAS ITS USE (feedback BL). The CURSOR walks what has been written, so it compares `t`.
    # What the scenario MEANS is in event time: "within N seconds" is between when two things happened, and an
    # action is valid from when its cause happened — `occurred`, where the writer knew it. An event a device
    # delivered ten minutes late gives a request whose deadline has already passed, and that is right: the
    # door is not opened for somebody who left ten minutes ago.
    #
    # And the firing is named after the completing event's `id`, not its time in milliseconds: two badges read
    # in one millisecond are two firings. `(id, when it happened, when it was written)`.
    def firings(self, row: dict, events: list[dict], since: float) -> list[tuple[str, float, float]]:
        triggers, window = list(row["when"]), float(row.get("within") or 0)
        at = lambda e: float(e.get("occurred", e.get("t", 0)))
        out: list[tuple[str, float, float]] = []
        for e in events:
            t = float(e.get("t", 0))
            if t <= since:
                continue                             # considered on an earlier pass
            if not any(fires(tr, e) for tr in triggers):
                continue
            if len(triggers) > 1:
                done = [tr for tr in triggers if fires(tr, e)]
                waiting = [tr for tr in triggers if tr not in done]
                if not all(any(fires(tr, o) and at(e) - window <= at(o) <= at(e) for o in events)
                           for tr in waiting):
                    continue                         # not all of them, not inside the window: not yet
            name = str(e["id"]) if e.get("id") else str(int(t * 1000))   # a line written before lines had names
            out.append((f"{row['id']}-{name}", at(e), t))
        return out

    # The ceiling, per scenario, per minute. In memory on purpose: it is a guard against a sensor that
    # bounces, and a bounce does not survive a restart — while a number in the store would be one more
    # write on the path of the thing that must stay fast.
    def allowed(self, row: dict, now: float) -> bool:
        unit, cap = str(row["id"]), int(row.get("rate_per_minute") or 0)
        recent = [t for t in self.recent.get(unit, []) if now - t < 60.0]
        self.recent[unit] = recent
        return not cap or len(recent) < cap

    # File what the scenario asks for: one row per action, in the TARGET subsystem's request family.
    #
    # `valid_until` is the event's moment plus `valid_for` — thirty seconds by default, the same the console
    # uses for an operator's own command, and for the same reason: an action that arrives after its moment is
    # not a late action, it is a wrong one. It used to be the scenario's `within`, which is another thing: how
    # far apart two triggers may be. A scenario with `within: 5` then got requests that lived five seconds,
    # while the road from the event to the holder took up to four with nothing loaded — this evaluator's pass
    # and the holder's, two seconds each; the index has had no tail to wait for since 28 September, it stats the
    # files on every query — and a request that met a slow pass on its way expired unperformed on an idle box.
    # Since 2 October 2026 neither wait is two seconds on a sound box (this pass begins when the resource says
    # the event was written; the holder looks at its requests four times a second), and both still CAN be: the
    # two-second pass is what is left when a wait is refused or a beat is switched off, and thirty seconds must
    # outlive that too.
    # Returns whether the requests were filed. A firing whose requests would be expired before they leave — a
    # cold start looks five minutes back, and `valid_for` is thirty seconds — is not filed (feedback AY): the
    # holder would only count it `expired`, and `expired` is the number that says the ROAD grew longer. It is
    # still a firing: the scenario's event says so, with how late, and the worker counts it apart (`late`).
    def file(self, row: dict, fid: str, at: float) -> bool:
        unit = str(row["id"])
        valid_until = at + (float(row.get("valid_for") or 0) or 30.0)
        if valid_until <= self.wall():
            self.fired[fid] = self.wall()
            self.late += 1
            if unit in self.epochs:
                EventLog(self.resource_root, AUTO.name, unit, self.epochs[unit]).append(
                    self.wall(), "fired", occurred=at, scenario=unit, actions=0, late=round(self.wall() - at, 3))
            return False
        for i, action in enumerate(row["then"]):
            sub, name = str(action.get("sub", "")), str(action.get("action", ""))
            rid = f"{fid}-{i}"
            fields = {k: str(v) for k, v in action.items() if k not in ("sub", "action")}
            if name == "record":                     # the recorder's own words for "record this from now"
                fields = {"unit": fields.get("cam", ""), **fields}
            # `filed`: when this row was written, by this clock — what the holder measures the request's own road from
            # (`vms_request_to_device_seconds`, the review's seventh pass); `at` stays the event's moment.
            self.vars.put(f"{sub}/requests/{rid}",
                          {**fields, "action": name, "at": str(at), "by": f"auto/{unit}", "valid_until": str(valid_until),
                           "filed": str(self.wall())})
            self.filed += 1
        self.fired[fid] = self.wall()
        self.recent.setdefault(unit, []).append(at)
        road = self.wall() - at
        self.pass_stats["latency_seconds"] = max(self.pass_stats["latency_seconds"], round(road, 3))
        self.latency["sum"] += road
        self.latency["count"] += 1
        for i, le in enumerate(self.LATENCY_BUCKETS):
            if road <= le:
                self.latency["buckets"][i] += 1
        # …and the scenario's own event, in its own bucket: what an operator sees on the timeline when
        # they ask why the door opened at 14:02. WRITTEN now (`t`), ABOUT the moment its cause happened
        # (`occurred`) — feedback BL. It used to be filed under the cause's time, which after a cold start or
        # a held cursor is minutes back: a line appended to a bucket that had closed, and that a neighbour
        # mirroring this server had already copied without it.
        if unit in self.epochs:
            EventLog(self.resource_root, AUTO.name, unit, self.epochs[unit]).append(
                self.wall(), "fired", occurred=at, scenario=unit, actions=len(row["then"]))
        return True

    def forget(self, now: float) -> None:
        self.fired = {k: t for k, t in self.fired.items() if now - t < self.REMEMBER}

    # -- what this worker publishes -----------------------------------------------------------------
    def status(self) -> list[dict]:
        return [self.status_by_unit[u] for u in sorted(self.status_by_unit) if u in set(self.assignment().units)]

    def headroom(self) -> int:
        return max(0, self.capacity - len(self.assignment().units))

    # Beside the platform's own fields (`Worker.platform_fields`): what it filed, late and over its ceiling, the road's
    # latency, its passes and the long poll.
    def heartbeat_fields(self) -> dict:
        return {"filed": self.filed, "late": self.late, "suppressed": self.suppressed, "latency": self.latency,
                "pass_failures": self.pass_failures, **self.pass_stats, **self.long_poll_stats()}

    # The long poll, counted since this process started — and nothing at all when it is off: requests it opened at
    # the resources (`waits`), those answered "changed" (`woken`), passes begun early for them (`early_passes`),
    # and requests that failed or were refused (`wait_errors`). `waits` growing with `woken` at 0 is a quiet box;
    # `wait_errors` growing is a resource that does not hold the wait — and the road is the two-second pass again.
    def long_poll_stats(self) -> dict:
        lp = self.long_poll
        return {} if lp is None else {"waits": lp.waits, "woken": lp.woken, "early_passes": self.wake.early,
                                      "wait_errors": lp.errors, "wake_gap": round(self.wake.gap, 3),   # the gap as paced now
                                      "wants_folded": self.wants_folded}

    def pump_once(self) -> None:
        return None                                   # nothing to drain: this worker runs no pipelines

    # The loop is the platform's (`Worker.run`): the pass, the lease step from its start and at once after one the store
    # did not answer, the heartbeat, each in a try of its own, the stand-in for a step that hangs, an orderly stop. This
    # worker had none — `python -m vms autoworker` called `run` and fell over — and then a copy of it.
    #
    # The period is not a habit copied from the neighbours. It is one link of the road from an event to an
    # action — this period, then the holder's own pass — and it multiplies the load:
    # every pass asks every scenario's window. Two seconds is the same as the holder's pass, so neither
    # dominates; `PASS_SECONDS` changes it, and the latency it costs is the operator's to accept. The heartbeat goes
    # out once per `poll`, as it always did.
    #
    # Since 2 October 2026 the period is the road's CEILING and not its length. The evaluator holds a request at
    # every resource it asks (`watch_events`, `w2cplatform/longpoll.py`), answered when a line of a kind its
    # scenarios watch is appended there, and the platform's wait ends at that answer — never sooner than `WAKE_GAP`
    # after the last pass began. The answer decides nothing: the pass is this same pass — the same window, cursor,
    # `SETTLE` and firing ids — over the scenarios the answer touched (`early_pass`); the ordinary pass over all of
    # them still comes every `poll`, and the gap widens with a long pass and with a resource that refused
    # (`pass_refused`, `Wake.pace`).
    def run(self, poll: float | None = None, stop=None) -> None:
        poll = float(os.environ.get("PASS_SECONDS", "2")) if poll is None else poll
        self.HEARTBEAT_EVERY = poll
        super().run(poll, stop)

    def early_pass(self, touched: set) -> None:
        self.reconcile_once(only=touched)

    # Staying itself: the platform's rules (`Worker.lease_pass`'s) — a store that did not answer is not "no"; a lost
    # lease is one scenario's, its epoch given up and a new one taken by the next pass — by the platform's `keep_slot`:
    # a slot held by another instance means this one is nobody, and it takes a free slot and starts from nothing, with
    # nothing running to stop (what it decided is filed).
    def lease_pass(self) -> list[str]:
        gone = self.keep_slot(lambda: None)
        lost = self.renew_leases()
        for unit in lost:
            self.release(unit)                        # the next pass takes a new epoch for it, if it is still mine
        return gone + lost
