"""longpoll — a hint the receiver PULLS: "a line you watch was written; look now".

A worker that reads the event log finds new lines by looking: a pass every two
seconds. The log is files under a resource, and the resource has a door. So the
reader asks that door to HOLD a request until a line of a kind it watches is
appended, and to answer then — or at a timeout, with nothing. The answer
carries no event and decides nothing: the reader runs its ordinary pass, now
instead of at the end of its wait, and reads what it would have read anyway.

    lost, refused, timed out    the pass happens at the end of the wait, as it always did
    answered a thousand times   one early pass per `WAKE_GAP`, no more
    switched off                `LONG_POLL=0`: no request is held, the loop as it was

    Watch      the door's side: who waits for what, and one thread that notices what was appended
    LongPoll   the reader's side: one held request per resource, and what each answer does
    Wake       the loop's wait between passes, cut short by an answer — never sooner than the gap
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # longpoll.py — the long poll of a resource's events: `Watch`, `LongPoll`, `Wake`
#
# **Why pulled, over a door that exists.** The reader already asks this door for `/events`: the same address
# from the same heartbeat, the same rights, the same path through whatever stands between two servers. A hint
# PUSHED to the reader would need a door on every reader — a port per process, announced, reachable from every
# writer — and a writer that cannot reach it learns nothing. A request the reader opens itself goes where its
# queries already go, and a wait that failed is an error the reader sees and counts.
#
# **How the door notices.** Nothing tells the resource that a line was written: writers append to files and say
# nothing to anybody. So while somebody waits — and only then — one thread stats the files a new line can land
# in: the current bucket of each unit somebody named — of every unit of a subsystem, for a want that names none —
# in the newest epoch, in the subsystem's tree and its alarms' (and the bucket before, for the first seconds after
# a boundary). A file that grew is read from where it stood, and the kinds of the new lines, with the unit whose
# file it is, are what waiters are matched against. Nobody waiting: no thread,
# no stat. Lines written into OLD buckets — an archive scan's, a card survey's — are not watched: the reader's
# own pass is still there, and it is the safety net for everything this does not see.
#
# **The bounds.** One request held per CLIENT — an evaluator's instance, `client=` — and a second one from it ends
# the first (`replaced`); `WAITERS_MAX` held at once in all (`LONG_POLL_WAITERS`), one more is answered `full` at
# once and its sender falls back to its pass. `WAIT_MAX` seconds per request. A waiter whose client went away is
# dropped within a second. `WAKE_GAP` between the beginnings of two passes of a reader, whatever is answered — wider
# when the passes are long or the resources refuse (`Wake.pace`). What was held, refused and replaced is in the
# resource's heartbeat and on `/metrics` (`Watch.counts`).
#
# **The unit is in the want** (the review's seventh pass, M8). `vms/io.input/12` is camera 12's contacts and nobody
# else's; `vms/io.input` is any camera's. A request for named units is answered only for them, and the watcher looks
# at their directories alone — a thousand cameras on the resource cost what the units asked about cost, not a stat
# per camera per tick. The answer says which of the wanted units changed (`touched`), and the reader's early pass
# evaluates the scenarios those touch and no others.
#
# **Between two waits.** A reader that was answered asks again, and a line written in between would fall into
# the gap. Two things close it: the answer carries `seq`, a number that grows with every change noticed, and the
# next request says `since=<seq>` — a wanted kind that changed after it is answered at once; and when the last
# waiter leaves, the sizes the watcher knew are kept for `LINGER` seconds, so a line appended while nobody waited
# is noticed by the first look after somebody does.
# ================================================================================================
from __future__ import annotations

import json
import logging
import os
import random
import selectors
import socket
import threading
import time
import urllib.parse
import urllib.request

from .doors import safe_segment
from .rows import PARSE_ERRORS, answer
from .events import EPOCH_DIR, alarm_tree, bucket_start, _stamp

log = logging.getLogger(__name__)

WAKE_GAP = 0.25               # an early pass begins no sooner than this after the previous pass began: 4 a second at most
WAKE_GAP_MAX = 2.0            # …and the gap, widened for long passes and refusals (`Wake.pace`), is never wider than this
PASS_SHARE = 2.0              # the gap is at least this many times the last pass: early passes take half the loop at most
WATCH_TICK = 0.1              # how often the door looks at the files, while somebody waits
WAIT_MAX = 30.0               # the longest a request is held; a reader asks again
# Requests held at once by one resource, in all; one more is answered `full`. Each client holds ONE (a second from the
# same `client` replaces its first), so this is a number of evaluators: up to eight are expected per resource (the
# design number of 2 October 2026), and the default is twice that. `LONG_POLL_WAITERS` changes it.
EVALUATORS_EXPECTED = 8
WAITERS_MAX = 2 * EVALUATORS_EXPECTED
WANTS_MAX = 64                # `(subsystem, kind, unit)` one request may name; more is 400 — a reader folds past it (`fold`)
RESCAN = 1.0                  # how often the watcher looks for a unit or an epoch that appeared (by the directories' mtime)
LINGER = 2.0                  # how long the sizes are remembered after the last waiter left
PREVIOUS_FOR = 5.0            # how long after a bucket's boundary the bucket before it is still looked at
BACKOFF = 2.0                 # what a reader waits after a resource failed or said `full`, before asking again — ±50 %
MTIME_SLACK = 2.0             # a directory changed this recently is listed again whatever its mtime says: a coarse clock


def waiters_from(env) -> int:
    """`LONG_POLL_WAITERS`: requests one resource holds at once, in all. `WAITERS_MAX` unless the environment says."""
    raw = str(env.get("LONG_POLL_WAITERS", "") or "").strip()
    return max(1, int(raw)) if raw else WAITERS_MAX


def wanted(pairs) -> frozenset:
    """`(subsystem, kind)` or `(subsystem, kind, unit)` -> triples; a unit of `""` is any unit of that kind."""
    return frozenset((str(p[0]), str(p[1]), str(p[2]) if len(p) > 2 and p[2] else "") for p in pairs)


# MORE THAN ONE REQUEST MAY NAME IS FOLDED, NOT REFUSED FOR GOOD (the review's eighth pass, part 3: a regression of the
# seventh's M8). An evaluator with 65 scenarios on 65 cameras sent 65 triples, every request was 400, and its long poll
# was off for good — the road from an event to a request back at two seconds, seen only in `auto_wait_errors_total`.
# More than `WANTS_MAX` scenarios on one evaluator are expected (the coordinator's decision of 2 October). Past the
# bound the triples are folded to their `(subsystem, kind)` with any unit: the request is held, any unit of those kinds
# answers it, and the answer's `touched` still names the units that changed — so the early pass still evaluates only
# the scenarios they touch. What folding costs is the watcher's look at every unit of the kind, and an early pass for a
# camera nobody watches. `(wants, folded)`: `folded` is how many triples were folded, 0 when none. More kinds than the
# bound — no request can hold them — is `([], n)`: the reader's pass, every `poll`, is all there is then.
def fold(wants) -> tuple[list, int]:
    wants = sorted(set(wants))
    if len(wants) <= WANTS_MAX:
        return wants, 0
    kinds = sorted({(w[0], w[1], "") for w in wants})
    return (kinds if len(kinds) <= WANTS_MAX else []), len(wants)


def matches(wants: frozenset, seen: tuple) -> bool:
    """Whether a line of `(subsystem, kind, unit)` answers `wants`: that unit named, or any unit of the kind."""
    return seen in wants or (seen[0], seen[1], "") in wants


def enabled(env) -> bool:
    """`LONG_POLL=0` (or `off`, `false`, `no`) switches the long poll off: no request is held, the loop looks
    every pass and no sooner."""
    return str(env.get("LONG_POLL", "1")).strip().lower() not in ("0", "off", "false", "no")


# -- the loop's side: the wait between passes ---------------------------------------------------------------
class Wake:
    """The wait a loop sleeps in between passes: `stop.wait(poll)`, with one more way to end — `set()`."""

    def __init__(self, gap: float = WAKE_GAP, clock=time.monotonic, gap_max: float = WAKE_GAP_MAX):
        self.base, self.gap, self.gap_max, self.clock = gap, gap, max(gap, gap_max), clock
        self.backoff = 0.0                           # the part of the gap the refusals added (`pace`)
        self.event = threading.Event()
        self.early = 0                               # passes begun early, since the process started
        self._began = clock()                        # when the pass that runs now began
        self._watched: set[int] = set()

    def set(self) -> None:
        self.event.set()

    # THE GAP FOLLOWS THE LOAD (the review's seventh pass, M8). It was `WAKE_GAP` whatever happened: a pass that took
    # a second was followed by the next early one a quarter of a second later, and a resource answering 503 to the
    # queries (`EVENTS_INFLIGHT`) was asked four times a second all the same — the holes kept the cursors where they
    # were, and the early passes made more holes. Told after every pass how long it took and whether a resource
    # refused it, the gap is now at least `PASS_SHARE` times the pass (early passes take half the loop at most), and
    # doubles with every pass a resource refused, back to the floor at the first one nobody refused; never wider than
    # `gap_max`, which is the ordinary pass.
    def pace(self, seconds: float, refused: bool) -> float:
        self.backoff = min(self.gap_max, max(self.base, 2 * self.backoff)) if refused else 0.0
        self.gap = min(self.gap_max, max(self.base, PASS_SHARE * max(0.0, float(seconds)), self.backoff))
        return self.gap

    # Returns when `poll` has passed, when `stop` is set, or when `set()` was called — but an early return never
    # comes sooner than `gap` after the previous pass BEGAN, so a flood of answers is one early pass per gap.
    # True when the wait was cut short.
    #
    # The event is cleared before the pass begins, never after: an answer that arrives while the pass runs is for
    # a line the pass may already have missed, and it stays set for the next wait.
    def wait_next(self, poll: float, stop) -> bool:
        self._watch(stop)
        woken = self.event.wait(poll)
        if stop.is_set():
            return False
        if woken:
            rest = self._began + self.gap - self.clock()
            if rest > 0 and stop.wait(rest):
                return False
            self.event.clear()
            self.early += 1
        self._began = self.clock()
        return woken

    # `stop` ends the wait at once, as it ends `stop.wait(poll)`: a thread that waits for it and sets our event.
    def _watch(self, stop) -> None:
        if id(stop) in self._watched:
            return
        self._watched.add(id(stop))

        def watch():
            stop.wait()
            self.event.set()

        threading.Thread(target=watch, name="wake-stop", daemon=True).start()


# -- the door's side: who waits, and what was appended -----------------------------------------------------
class Watch:
    """A resource's held requests. `wait(wants, timeout)` returns when a line of a wanted `(subsystem, kind, unit)`
    is appended under one of `roots`, or at the timeout."""

    def __init__(self, roots, bucket_seconds: int = 600, wall=time.time, tick: float = WATCH_TICK,
                 waiters_max: int | None = None, clock=time.monotonic, env=None):
        self.roots, self.bucket_seconds, self.wall, self.tick = list(roots), bucket_seconds, wall, tick
        self.waiters_max = waiters_max if waiters_max is not None else waiters_from(os.environ if env is None else env)
        self.clock = clock
        self.seq = 0                                 # grows with every change noticed
        self.last: dict[tuple[str, str, str], int] = {}   # (subsystem, kind, unit) -> the `seq` of its last change
        self.stats = 0                               # files stat-ed, since the process started: what a tick costs
        self.held = self.full = self.replaced = 0    # requests held; refused for want of room; ended by their client's next
        self._lock = threading.Lock()
        self._waiters: list[dict] = []
        self._by_client: dict[str, dict] = {}        # client -> the one request it holds here
        self._thread: threading.Thread | None = None
        self._closed = False
        self._sizes: dict[str, int] = {}             # candidate file -> bytes of it already looked at
        self._based: set[tuple[str, str]] = set()    # (subsystem, unit) whose files have a baseline in `_sizes`
        self._recent: dict[tuple[str, str], float] = {}   # (subsystem, unit or "") -> when somebody last wanted it, by `clock`
        self._dirs: list[tuple[str, str, str]] = []  # (subsystem, unit, newest epoch directory of it), as last listed
        self._listed: tuple[float, frozenset] | None = None
        self._dircache: dict[str, tuple[int, float, object]] = {}   # directory -> (mtime_ns, when listed, what it gave)
        self._idle_since: float | None = None        # when the last waiter left

    def open(self) -> None:
        with self._lock:
            self._closed = False

    # The door shuts: every held request is answered now, and none is held after.
    def close(self) -> None:
        with self._lock:
            self._closed = True
            for w in self._waiters:
                w["event"].set()

    def waiting(self) -> int:
        return len(self._waiters)

    # What the resource says about its waits in its heartbeat, and the console on `/metrics`: held now, and since the
    # process started — held, refused `full`, and replaced by their own client's next request.
    def counts(self) -> dict:
        with self._lock:
            return {"waiting": len(self._waiters), "held": self.held, "full": self.full, "replaced": self.replaced,
                    "max": self.waiters_max}

    # `gone()` — whether the client that asked is still there; asked once a second while the request is held.
    # `client` — who asks (an evaluator's instance): it holds one request here, and a second ends the first.
    #
    # THE NUMBER IS READ UNDER THE LOCK (the review's seventh pass, minor). `seq` was read after the waiter had left
    # and outside the lock: a change the watcher noticed in between went into the number this reader asks again
    # with, and not into an answer — the hint was swallowed until the reader's next ordinary pass. Now what this
    # waiter was told and the number it is told to ask again with come from one moment.
    def wait(self, wants, timeout: float, since: int | None = None, gone=None, client: str | None = None) -> dict:
        wants = wanted(wants)
        timeout = max(0.0, min(float(timeout), WAIT_MAX))
        client = str(client or "")
        me = {"wants": wants, "event": threading.Event(), "changed": False, "touched": set(), "client": client}
        with self._lock:
            if self._closed:
                return {"changed": False, "closed": True, "seq": self.seq}
            if since is not None and since <= self.seq:
                touched = [t for t, n in self.last.items() if n > since and matches(wants, t)]
                if touched:                                       # it changed between this reader's two waits
                    return {"changed": True, "seq": self.seq, "touched": sorted("/".join(t) for t in touched)}
            old = self._by_client.get(client) if client else None
            if old is not None:                               # its previous request — a client holds one, the newest
                old["replaced"] = True
                old["event"].set()
                self.replaced += 1
            elif len(self._waiters) >= self.waiters_max:
                self.full += 1
                return {"changed": False, "full": True, "seq": self.seq}
            self._waiters.append(me)
            if client:
                self._by_client[client] = me
            self.held += 1
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name="events-watch", daemon=True)
                self._thread.start()
        try:
            end = self.clock() + timeout
            while not me["event"].wait(max(0.0, min(1.0, end - self.clock()))):
                if self.clock() >= end or (gone is not None and gone()):
                    break
        finally:
            with self._lock:
                self._waiters.remove(me)
                if client and self._by_client.get(client) is me:
                    del self._by_client[client]
                if not self._waiters:
                    self._idle_since = self.clock()
                rep = {"changed": me["changed"], "seq": me["seq"] if me["changed"] else self.seq}
                if me["changed"]:
                    rep["touched"] = sorted("/".join(t) for t in me["touched"])
                if self._closed:
                    rep["closed"] = True
                if me.get("replaced"):
                    rep["replaced"] = True
        return rep

    # The one thread, for as long as somebody waits.
    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._waiters or self._closed:
                    self._thread = None
                    return
                wanted_now = frozenset(p for w in self._waiters for p in w["wants"])
            try:
                self._tick(wanted_now)
            except Exception:                        # noqa: BLE001 — one bad look is a late answer, not a dead watcher
                log.exception("the watch over the events failed; looking again")
            time.sleep(self.tick)

    # One look. The candidates are computed, not found: the bucket of `now` has one name, so a file that is not
    # there yet is a stat that fails, and the first line written into it is growth from zero.
    def _tick(self, wanted_now: frozenset) -> None:
        now_c, now = self.clock(), self.wall()
        if self._idle_since is not None:
            idle = now_c - self._idle_since
            if idle > LINGER:                        # nobody waited for a while: what grew meanwhile is not news
                self._sizes, self._based, self._listed, self._recent = {}, set(), None, {}
            else:                                    # nobody looked meanwhile: "wanted a moment ago" did not age
                self._recent = {s: t + idle for s, t in self._recent.items()}
            self._idle_since = None
        # A unit is looked at while somebody wants it — and for `LINGER` after: its reader was answered and is asking
        # again, and what is written in between must be noticed for it (`last`, `since`), not start afresh. A want
        # with no unit is every unit of that subsystem (`""`).
        for s, _, u in wanted_now:
            self._recent[(s, u)] = now_c
        self._recent = {k: t for k, t in self._recent.items() if now_c - t <= LINGER}
        looked = frozenset(self._recent)
        if self._listed is None or now_c - self._listed[0] >= RESCAN or self._listed[1] != looked:
            self._dirs, self._listed = self._list(looked), (now_c, looked)
        start = bucket_start(now, self.bucket_seconds)
        names = [_stamp(start) + ".events.jsonl"]
        if now - start < PREVIOUS_FOR:
            names.append(_stamp(start - self.bucket_seconds) + ".events.jsonl")
        sizes, seen, based = {}, set(), set()
        for sub, unit, d in self._dirs:
            first = (sub, unit) not in self._based   # a unit first looked at: from here
            based.add((sub, unit))
            for name in names:
                p = os.path.join(d, name)
                self.stats += 1
                try:
                    size = os.stat(p).st_size
                except OSError:
                    size = 0
                old = size if first else self._sizes.get(p, 0)
                if size > old:
                    kinds, old = self._kinds(p, old, size)
                    seen.update((sub, k, unit) for k in kinds)
                sizes[p] = min(old, size)
        self._sizes, self._based = sizes, based      # a unit not looked at this time starts from a baseline when it returns
        if seen:
            with self._lock:
                self.seq += 1
                for t in seen:
                    self.last[t] = self.seq
                for w in self._waiters:
                    touched = {t for t in seen if matches(w["wants"], t)}
                    if not touched:
                        continue
                    w["touched"] |= touched
                    if not w["changed"]:
                        w["changed"], w["seq"] = True, self.seq      # the number it asks again with: what came after THIS
                        w["event"].set()

    # The newest epoch directory of each unit looked at, in each subsystem's tree and its alarms'. A line of an older
    # epoch is a fenced writer's, and no reader acts on it.
    #
    # WHAT IS LISTED IS WHAT IS WANTED (the review's seventh pass, minor). Every unit of every watched subsystem was
    # listed every second and its files stat-ed every tick — a thousand cameras were 7 % of a core with ONE waiter, for
    # one camera's contact. Now a want that names its units lists those units' directories and no others; only a want
    # with no unit lists the subsystem. And a directory is listed again only when its mtime moved (an epoch or a unit
    # appeared) — or changed within `MTIME_SLACK`, for a file system whose clock is coarser than two creations.
    def _list(self, looked: frozenset) -> list[tuple[str, str, str]]:
        named: dict[str, set[str] | None] = {}
        for sub, unit in looked:
            if not safe_segment(sub) or (unit and not safe_segment(unit)):
                continue                             # never a path: `parse_wants` refuses these at the door already
            if not unit:
                named[sub] = None                    # every unit of it
            elif named.get(sub, set()) is not None:
                named.setdefault(sub, set()).add(unit)
        out, used = [], set()
        for root in self.roots:
            for sub in sorted(named):
                for tree in (sub, alarm_tree(sub)):
                    base = os.path.join(root, tree)
                    units = named[sub]
                    if units is None:
                        units = self._listed_dir(base, used, lambda names: list(names))
                        if units is None:
                            continue
                    for unit in sorted(units):
                        d = os.path.join(base, unit)
                        newest = self._listed_dir(d, used, lambda names: max(
                            (int(m.group(1)) for m in map(EPOCH_DIR.match, names) if m), default=None))
                        if newest is not None:
                            out.append((sub, unit, os.path.join(d, f"e{newest}")))
        self._dircache = {k: v for k, v in self._dircache.items() if k in used}
        return out

    # What `make(os.listdir(path))` gave, listed again only when the directory's mtime moved. None: not there.
    def _listed_dir(self, path: str, used: set, make):
        try:
            mtime = os.stat(path).st_mtime_ns
        except OSError:
            return None
        used.add(path)
        now = time.time()                            # the file system's clock, which is what an mtime is in
        have = self._dircache.get(path)
        if have is not None and have[0] == mtime and now - mtime / 1e9 > MTIME_SLACK:
            return have[2]
        try:
            got = make(os.listdir(path))
        except OSError:
            return None
        self._dircache[path] = (mtime, now, got)
        return got

    # The kinds of the lines in `[old, size)` of a file, and how far whole lines went: a line half written is
    # left for the next look.
    @staticmethod
    def _kinds(path: str, old: int, size: int) -> tuple[set, int]:
        kinds: set[str] = set()
        try:
            with open(path, "rb") as f:
                f.seek(old)
                data = f.read(size - old)
        except OSError:
            return kinds, old
        whole = data.rfind(b"\n") + 1
        for line in data[:whole].splitlines():
            try:
                kinds.add(str(json.loads(line).get("kind", "")))
            except PARSE_ERRORS:
                continue                             # a torn line: skipped, as every reader of a bucket skips it
        return kinds, old + whole


# Whether the other end of a held request closed its connection: readable, and nothing to read.
#
# Through `selectors`, not `select.select` (the review's seventh pass, minor): `select` cannot take a descriptor at or
# above 1024 and raises `ValueError`, which was read as "the client went" — on a busy process every hold became a
# poll answered within a second. A descriptor this cannot watch is now "not known", and the hold ends at its timeout.
def client_gone(conn) -> bool:
    try:
        with selectors.DefaultSelector() as sel:
            sel.register(conn, selectors.EVENT_READ)
            readable = bool(sel.select(0))
    except ValueError:
        return False                                 # not a descriptor this can watch: not known, so not gone
    except OSError:
        return True
    if not readable:
        return False
    try:
        return conn.recv(1, socket.MSG_PEEK) == b""
    except (BlockingIOError, InterruptedError):
        return False
    except OSError:
        return True


# `vms/io.input,det/motion/7-motion` -> `[("vms", "io.input", ""), ("det", "motion", "7-motion")]`: a unit of `""` is
# any unit of the kind.
#
# REFUSED, NOT GUESSED (the review's seventh pass, minor). What did not look like a want was dropped: an empty `want`
# held a place for thirty seconds and answered nothing, `want=../../x/k` sent the watcher to list a directory outside
# the volumes, and nothing bounded how many were named. Now each is a `ValueError` the door answers 400: nothing
# wanted; a subsystem or a unit that is not one name (`safe_segment` — the subsystem and the unit are path segments
# under the volume); more than `WANTS_MAX`.
def parse_wants(text: str) -> list[tuple[str, str, str]]:
    out = []
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        sub, kind, unit = (part.split("/", 2) + ["", ""])[:3]
        if not safe_segment(sub) or not kind or (unit and not safe_segment(unit)):
            raise ValueError(f"a want is <subsystem>/<kind> or <subsystem>/<kind>/<unit>, each one name: not {part!r}")
        out.append((sub, kind, unit))
    if not out:
        raise ValueError("nothing is wanted: `want` names at least one <subsystem>/<kind>")
    if len(out) > WANTS_MAX:
        raise ValueError(f"{len(out)} wants; one request names at most {WANTS_MAX}")
    return sorted(set(out))


# -- the reader's side: one held request per resource --------------------------------------------------------
class LongPoll:
    """Keeps one request held at each resource for what `wants()` says, and calls `wake.set()` when one is
    answered `changed`. `resources()` is `{server: url}` — the resources the reader asks anyway; `client` is who
    asks (the worker's instance), so that a resource holds one request of it and not one per retry."""

    def __init__(self, wake: Wake, resources, wants, timeout: float = WAIT_MAX, backoff: float = BACKOFF, fetch=None,
                 client: str = ""):
        self.wake, self.resources, self.wants = wake, resources, wants
        self.timeout, self.backoff, self.client = timeout, backoff, str(client or "")
        self.fetch = fetch or self._http
        self.waits = self.woken = self.errors = 0    # requests opened, answered `changed`, failed or refused
        self._urls: dict[str, str] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._touched: set | None = set()            # what the answers since the last pass said changed; None: not said

    def _http(self, url: str, wants: list, timeout: float, since: int | None) -> dict:
        q = {"want": ",".join("/".join(str(x) for x in w if x != "") for w in wants), "timeout": f"{timeout:g}",
             **({"since": since} if since is not None else {}), **({"client": self.client} if self.client else {})}
        with urllib.request.urlopen(f"{url}/events/wait?{urllib.parse.urlencode(q)}", timeout=timeout + 5.0) as r:
            return json.loads(answer(r))                 # up to a bound (`rows.answer`; the review's eighth pass)

    # What the answers since the last call said changed — `(subsystem, kind, unit)` — and forgotten: the pass that
    # follows evaluates what these touch. None when an answer said `changed` without saying what (a resource of an
    # older build): everything, then.
    def take_touched(self) -> set | None:
        with self._lock:
            out, self._touched = self._touched, set()
        return out

    def _say_touched(self, rep: dict) -> None:
        with self._lock:
            if "touched" not in rep:
                self._touched = None
            elif self._touched is not None:
                for t in rep.get("touched") or []:
                    sub, kind, unit = (str(t).split("/", 2) + ["", ""])[:3]
                    self._touched.add((sub, kind, unit))

    # Called by the loop once a pass: a thread for every resource that has none. A resource that left the list has
    # its thread end by itself, at the end of the request it holds. Never raises: a list that could not be read is
    # the list as it was.
    def sync(self) -> None:
        try:
            self._urls = {s: u for s, u in dict(self.resources()).items() if u}
        except Exception as e:                       # noqa: BLE001
            log.debug("the resources could not be listed for the long poll (%s); as before", e)
            return
        for server in self._urls:
            t = self._threads.get(server)
            if t is None or not t.is_alive():
                t = self._threads[server] = threading.Thread(target=self._run, args=(server,), name=f"long-poll-{server}", daemon=True)
                t.start()

    # A pause after a failure or a refusal, ±50 %: sixteen evaluators refused together do not all ask again in the
    # same instant, and one of them finds the place another has just left (the review's seventh pass, minor).
    def _pause(self) -> None:
        self._stop.wait(self.backoff * random.uniform(0.5, 1.5))

    def _run(self, server: str) -> None:
        since = None
        while not self._stop.is_set():
            url, wants = self._urls.get(server), sorted(self.wants())
            if url is None:
                return                               # not a resource this reader asks any more
            if not wants:
                self._stop.wait(self.backoff)        # nothing watched: nothing to wait for
                continue
            self.waits += 1
            try:
                rep = self.fetch(url, wants, self.timeout, since)
                if not isinstance(rep, dict):            # an answer of another shape is a wait that failed, not the thread's end
                    raise ValueError(f"the answer is a {type(rep).__name__}, not an object")
            except Exception as e:                   # noqa: BLE001 — the resource is away, or does not know the route
                self.errors += 1
                log.debug("%s did not hold a wait (%s); the pass looks, as it did", server, e)
                self._pause()
                continue
            if rep.get("full") or rep.get("closed"):
                # No room, or the door is shutting: back to the pass for a while — and `since` stays where it was. The
                # number such an answer carries says nothing about what this reader was told (the review's seventh
                # pass, minor): moved to it, a change made before it and never answered was skipped for good.
                self.errors += 1
                self._pause()
                continue
            since = rep.get("seq", since)
            if rep.get("changed"):
                self.woken += 1
                self._say_touched(rep)
                if not self._stop.is_set():
                    self.wake.set()

    def close(self) -> None:
        self._stop.set()                             # a thread inside a held request ends when the request does
