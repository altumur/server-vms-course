"""autoworker — the seventh subsystem's worker: the one that READS.

Every worker before it observed the world and wrote down what it saw. This one
reads what they wrote, decides that a scenario fired, and asks somebody else to
act — by filing a request, never by touching a device.

    AUTO_NAME / SLOT_INDEX     -> the slot to claim: a-<index>
    SERVER_NAME (or hostname)  -> `server` in the heartbeat
    ARCHIVE                    -> where its own events and its cursor live

Three things carry the whole design, and each one is a decision that could have
gone the other way:

  1. NO STATE MACHINE. "A and B within thirty seconds" is not "saw A, waiting
     for B" — it is a question asked of the last thirty seconds of the log,
     re-asked every pass. There is nothing to keep, nothing to restore and
     nothing to get wrong after a crash.
  2. A CURSOR, not a queue. `Frontier` — the survey's own number, the same file
     — says how far this scenario has been considered. It is the only thing
     written down.
  3. A DETERMINISTIC REQUEST ID. Delivery is at-least-once by construction, so
     a firing computed twice must be the same row: `<scenario>-<millisecond of
     the event that completed it>`. Written twice is written once; performed
     once by the holder.
"""
from __future__ import annotations

import logging
import os
import time

from w2cplatform import runtime
from w2cplatform.contract import Worker
from w2cplatform.eventdatabase import MergedIndex
from w2cplatform.events import EventLog
from w2cplatform.variables import Variables

from .auto import Catalog, fires
from .config import AUTO_SPEC
from .scan import Frontier

log = logging.getLogger("autoworker")
AUTO = AUTO_SPEC.sub


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
    # How long a firing id is remembered after it is filed. Long enough that the same event, still inside
    # somebody's window, is not filed twice; short enough to be a handful of strings.
    REMEMBER = 900.0
    # How far BEHIND `now` the cursor is allowed to stop, and the reason there is a distance at all: the
    # merge is not a stream this process reads. A resource tails its files on a timer and the console
    # merges over HTTP, so an event written at T becomes visible some seconds later. A cursor set to `now`
    # is already past it, and `t <= since` then skips it FOR EVER — no refusal, no log line, just a
    # scenario that does not fire, which is the most expensive silence in this subsystem.
    #
    # The asymmetry decides the number: re-reading a stretch costs a comparison (the firing ids are
    # deterministic and the ones just filed are still remembered), running ahead costs a firing. Five
    # seconds is comfortably more than the tail period.
    SETTLE = 5.0
    # Rows per (subsystem, kind) query. The index now keeps the NEWEST end of an overflowing window and
    # says `truncated` when it had to cut, so this is a budget rather than a trap — but a scenario still
    # wants its window whole, and one query per kind is what keeps it that way.
    PER_KIND = 500

    def __init__(self, name: str | None, vars_: Variables, objects, index=None, capacity: int | None = None,
                 clock=time.monotonic, wall=time.time, server: str | None = None,
                 archive_root: str | None = None, env: dict | None = None, catalog: Catalog | None = None):
        env = dict(os.environ if env is None else env)
        super().__init__(AUTO, None, vars_, objects, clock=clock, wall=wall)
        self.claim_slot(prefer=name if name is not None else runtime.slot(env, "AUTO_NAME", "a"))
        self.capacity = capacity if capacity is not None else int(env.get("CAPACITY", "50"))
        self.server = runtime.server(env, server)
        self.labels = runtime.labels(env)
        self.archive_root = archive_root or env.get("ARCHIVE", "/data/archive")
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
        # One pass's answers, per (subsystem, kind): asked ONCE for every scenario watching that kind, over the
        # longest window any of them needs (`reconcile_once`). And what the pass cost — said in the heartbeat,
        # because a slow pass is otherwise visible nowhere: its seconds, its queries, how far the furthest
        # cursor trails `now`, and the longest road from an event to the request it filed.
        self._asked: dict[tuple[str, str, str], dict] = {}
        self._needed: dict[tuple[str, str, str], float] = {}
        self.pass_stats = {"pass_seconds": 0.0, "queries": 0, "lag_seconds": 0.0, "latency_seconds": 0.0}
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
    def reconcile_once(self, now: float | None = None) -> list[str]:
        now = self.wall() if now is None else now
        started = self.clock()
        acted: list[str] = []
        units = sorted(self.assignment().units)
        rows = {u: self.scenario(u) for u in units}
        self._plan(rows, now)
        self.pass_stats.update(queries=0, lag_seconds=0.0, latency_seconds=0.0)
        for unit in units:
            row = rows[unit]
            if row is None:
                continue
            if not row["enabled"]:
                self.status_by_unit[unit] = {"id": unit, "phase": "pending", "why": "disabled"}
                continue
            if unit not in self.epochs:
                self.take_epoch(unit)                # its own events — "this scenario fired" — need one writer
            if not self.may_write(unit):             # the lease says another instance has it: decide nothing…
                # …and say so. The status of the last pass this instance made would otherwise stay, and say
                # `holding` for a window this instance no longer asks for (feedback AV). What it was waiting
                # for goes too: taken back later, it starts waiting afresh, not five minutes into a wait.
                self.status_by_unit[unit] = {"id": unit, "phase": "waiting", "why": "its lease is not this instance's"}
                self.holes.pop(unit, None)
                self.held_from.pop(unit, None)
                self.said_without.discard(unit)
                continue
            try:
                n = self.evaluate(row, now)
            except Exception as e:                   # noqa: BLE001 — a resource that stopped answering mid-pass
                self.status_by_unit[unit] = {"id": unit, "phase": "waiting", "why": str(e)}
                log.warning("%s: %s not evaluated: %s", self.name, unit, e)
                continue
            # A scenario that no longer fits still runs: its trigger may be fine and its other actions too,
            # and the one that cannot be done is refused by the holder, on the unit, where it is seen. What
            # changes is that the scenario SAYS so, on every pass — never a scenario silently half-working.
            misfit, unsure = self.catalog.check(row)
            holes = self.holes.get(unit) or {}
            self.status_by_unit[unit] = {"id": unit, "phase": "running", "fired": n,
                                         **({"holding": holes} if holes else {}),
                                         **({"cut": self.cut[unit]} if self.cut.get(unit) else {}),
                                         **({"decided_without": self.gave_up.pop(unit)} if unit in self.gave_up else {}),
                                         **({"unfit": misfit} if misfit else {}),
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
        since = Frontier(self.archive_root, str(row["id"]), AUTO.name).read()
        return now - self.COLD_START if since is None else max(since, now - self.COLD_START)

    def _plan(self, rows: dict, now: float) -> None:
        self._asked, self._needed = {}, {}
        for row in rows.values():
            if row is None or not row["enabled"]:
                continue
            t0 = self._since(row, now) - float(row.get("within") or 0)
            for key in self._keys(row):
                self._needed[key] = min(self._needed.get(key, t0), t0)

    @staticmethod
    def _keys(row: dict) -> list[tuple[str, str, str]]:
        return sorted({(str(t.get("sub", "")), str(t.get("kind", "")), str(t.get("unit") or "")) for t in row["when"]})

    def _ask(self, sub: str, kind: str, unit: str, t0: float, t1: float) -> dict:
        key = (sub, kind, unit)
        have = self._asked.get(key)
        if have is None or have["t0"] > t0 or have["t1"] < t1:
            start = min(t0, self._needed.get(key, t0))
            rep = self.index.query(max(0.0, start), t1, subsystem=sub, kind=kind, unit=unit or None, limit=self.PER_KIND)
            self.pass_stats["queries"] += 1
            have = self._asked[key] = {"t0": start, "t1": t1, "rep": rep}
        return have["rep"]

    # One scenario against the log. Returns how many firings were filed.
    def evaluate(self, row: dict, now: float) -> int:
        unit = str(row["id"])
        front = Frontier(self.archive_root, unit, AUTO.name)
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
        fired = 0
        for fid, at in self.firings(row, events, since):
            if fired >= self.PER_PASS:
                break
            if fid in self.fired:
                continue                             # already filed; the id is the same either way
            if not self.allowed(row, now):
                log.warning("%s: %s is over its ceiling of %s/min — not firing", self.name, unit, row["rate_per_minute"])
                break
            self.file(row, fid, at)
            fired += 1
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
            front.set(max(since, now - self.SETTLE))  # …and never further than the log has caught up to
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
    def firings(self, row: dict, events: list[dict], since: float) -> list[tuple[str, float]]:
        triggers, window = list(row["when"]), float(row.get("within") or 0)
        out: list[tuple[str, float]] = []
        for e in events:
            t = float(e.get("t", 0))
            if t <= since:
                continue                             # considered on an earlier pass
            if not any(fires(tr, e) for tr in triggers):
                continue
            if len(triggers) > 1:
                done = [tr for tr in triggers if fires(tr, e)]
                waiting = [tr for tr in triggers if tr not in done]
                if not all(any(fires(tr, o) and t - window <= float(o.get("t", 0)) <= t for o in events)
                           for tr in waiting):
                    continue                         # not all of them, not inside the window: not yet
            out.append((f"{row['id']}-{int(t * 1000)}", t))
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
    # while the road from the event to the holder takes up to seven with nothing loaded — the tail, the pass,
    # the holder's pass — and they expired unperformed on an idle box.
    def file(self, row: dict, fid: str, at: float) -> None:
        unit = str(row["id"])
        for i, action in enumerate(row["then"]):
            sub, name = str(action.get("sub", "")), str(action.get("action", ""))
            rid = f"{fid}-{i}"
            fields = {k: str(v) for k, v in action.items() if k not in ("sub", "action")}
            if name == "record":                     # the recorder's own words for "record this from now"
                fields = {"unit": fields.get("cam", ""), **fields}
            self.vars.put(f"{sub}/requests/{rid}",
                          {**fields, "action": name, "at": str(at), "by": f"auto/{unit}",
                           "valid_until": str(at + (float(row.get("valid_for") or 0) or 30.0))})
            self.filed += 1
        self.fired[fid] = self.wall()
        self.recent.setdefault(unit, []).append(at)
        self.pass_stats["latency_seconds"] = max(self.pass_stats["latency_seconds"], round(self.wall() - at, 3))
        # …and the scenario's own event, in its own bucket: what an operator sees on the timeline when
        # they ask why the door opened at 14:02.
        if unit in self.epochs:
            EventLog(self.archive_root, AUTO.name, unit, self.epochs[unit]).append(
                at, "fired", scenario=unit, actions=len(row["then"]))

    def forget(self, now: float) -> None:
        self.fired = {k: t for k, t in self.fired.items() if now - t < self.REMEMBER}

    # -- what this worker publishes -----------------------------------------------------------------
    def status(self) -> list[dict]:
        return [self.status_by_unit[u] for u in sorted(self.status_by_unit) if u in set(self.assignment().units)]

    def headroom(self) -> int:
        return max(0, self.capacity - len(self.assignment().units))

    def heartbeat_once(self) -> None:
        self.heartbeat(self.status(), server=self.server, instance=self.instance,
                       labels=",".join(self.labels), capacity=self.capacity, headroom=self.headroom(),
                       filed=self.filed, **self.pass_stats)

    def pump_once(self) -> None:
        return None                                   # nothing to drain: this worker runs no pipelines

    # The loop — which this worker did not have: `python -m vms autoworker` called `run` and fell over, and no
    # test noticed, because every test drives `reconcile_once` by hand (feedback on the event log's load).
    #
    # The period is not a habit copied from the neighbours. It is one link of the road from an event to an
    # action — the resource's tail, `SETTLE`, this period, the holder's own pass — and it multiplies the load:
    # every pass asks every scenario's window. Two seconds is the same as the holder's pass, so neither
    # dominates; `PASS_SECONDS` changes it, and the latency it costs is the operator's to accept.
    def run(self, poll: float | None = None, stop=None) -> None:
        import threading
        poll = float(os.environ.get("PASS_SECONDS", "2")) if poll is None else poll
        stop = stop or threading.Event()
        while not stop.is_set():
            try:
                self.reconcile_once(); self.heartbeat_once()
            except Exception:                         # noqa: BLE001 — one bad pass is a late decision, not a dead evaluator
                log.exception("%s: pass failed", self.name)
            stop.wait(poll)
        self.release_slot()
