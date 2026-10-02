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
# in: the current bucket of each unit of the watched subsystems, in the newest epoch, in the subsystem's tree and
# its alarms' (and the bucket before, for the first seconds after a boundary). A file that grew is read from
# where it stood, and the kinds of the new lines are what waiters are matched against. Nobody waiting: no thread,
# no stat. Lines written into OLD buckets — an archive scan's, a card survey's — are not watched: the reader's
# own pass is still there, and it is the safety net for everything this does not see.
#
# **The bounds.** `WAITERS_MAX` requests held at once; one more is answered `full` at once, and its sender falls
# back to its pass. `WAIT_MAX` seconds per request. A waiter whose client went away is dropped within a second.
# `WAKE_GAP` between the beginnings of two passes of a reader, whatever is answered.
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
import select
import socket
import threading
import time
import urllib.parse
import urllib.request

from .events import EPOCH_DIR, alarm_tree, bucket_start, _stamp

log = logging.getLogger(__name__)

WAKE_GAP = 0.25               # an early pass begins no sooner than this after the previous pass began: 4 a second at most
WATCH_TICK = 0.1              # how often the door looks at the files, while somebody waits
WAIT_MAX = 30.0               # the longest a request is held; a reader asks again
WAITERS_MAX = 16              # requests held at once by one resource; one more is answered `full`
RESCAN = 1.0                  # how often the watcher lists directories for a unit or an epoch that appeared
LINGER = 2.0                  # how long the sizes are remembered after the last waiter left
PREVIOUS_FOR = 5.0            # how long after a bucket's boundary the bucket before it is still looked at
BACKOFF = 2.0                 # what a reader waits after a resource failed or said `full`, before asking again


def enabled(env) -> bool:
    """`LONG_POLL=0` (or `off`, `false`, `no`) switches the long poll off: no request is held, the loop looks
    every pass and no sooner."""
    return str(env.get("LONG_POLL", "1")).strip().lower() not in ("0", "off", "false", "no")


# -- the loop's side: the wait between passes ---------------------------------------------------------------
class Wake:
    """The wait a loop sleeps in between passes: `stop.wait(poll)`, with one more way to end — `set()`."""

    def __init__(self, gap: float = WAKE_GAP, clock=time.monotonic):
        self.gap, self.clock = gap, clock
        self.event = threading.Event()
        self.early = 0                               # passes begun early, since the process started
        self._began = clock()                        # when the pass that runs now began
        self._watched: set[int] = set()

    def set(self) -> None:
        self.event.set()

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
    """A resource's held requests. `wait(wants, timeout)` returns when a line of a wanted `(subsystem, kind)`
    is appended under one of `roots`, or at the timeout."""

    def __init__(self, roots, bucket_seconds: int = 600, wall=time.time, tick: float = WATCH_TICK,
                 waiters_max: int = WAITERS_MAX, clock=time.monotonic):
        self.roots, self.bucket_seconds, self.wall, self.tick = list(roots), bucket_seconds, wall, tick
        self.waiters_max, self.clock = waiters_max, clock
        self.seq = 0                                 # grows with every change noticed
        self.last: dict[tuple[str, str], int] = {}   # (subsystem, kind) -> the `seq` of its last change
        self.stats = 0                               # files stat-ed, since the process started: what a tick costs
        self.held = self.full = 0                    # requests held; requests refused for want of room
        self._lock = threading.Lock()
        self._waiters: list[dict] = []
        self._thread: threading.Thread | None = None
        self._closed = False
        self._sizes: dict[str, int] = {}             # candidate file -> bytes of it already looked at
        self._based: set[str] = set()                # subsystems whose files have a baseline in `_sizes`
        self._recent: dict[str, float] = {}          # subsystem -> when somebody last wanted it, by `clock`
        self._dirs: list[tuple[str, str]] = []       # (subsystem, newest epoch directory of a unit), as last listed
        self._listed: tuple[float, frozenset] | None = None
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

    # `gone()` — whether the client that asked is still there; asked once a second while the request is held.
    def wait(self, wants, timeout: float, since: int | None = None, gone=None) -> dict:
        wants = frozenset((str(s), str(k)) for s, k in wants)
        timeout = max(0.0, min(float(timeout), WAIT_MAX))
        me = {"wants": wants, "event": threading.Event(), "changed": False}
        with self._lock:
            if self._closed:
                return {"changed": False, "closed": True, "seq": self.seq}
            if since is not None and since <= self.seq and any(self.last.get(p, 0) > since for p in wants):
                return {"changed": True, "seq": self.seq}        # it changed between this reader's two waits
            if len(self._waiters) >= self.waiters_max:
                self.full += 1
                return {"changed": False, "full": True, "seq": self.seq}
            self._waiters.append(me)
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
                if not self._waiters:
                    self._idle_since = self.clock()
        return {"changed": me["changed"], "seq": me.get("seq", self.seq), **({"closed": True} if self._closed else {})}

    # The one thread, for as long as somebody waits.
    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._waiters or self._closed:
                    self._thread = None
                    return
                wanted = frozenset(p for w in self._waiters for p in w["wants"])
            try:
                self._tick(wanted)
            except Exception:                        # noqa: BLE001 — one bad look is a late answer, not a dead watcher
                log.exception("the watch over the events failed; looking again")
            time.sleep(self.tick)

    # One look. The candidates are computed, not found: the bucket of `now` has one name, so a file that is not
    # there yet is a stat that fails, and the first line written into it is growth from zero.
    def _tick(self, wanted: frozenset) -> None:
        now_c, now = self.clock(), self.wall()
        if self._idle_since is not None:
            idle = now_c - self._idle_since
            if idle > LINGER:                        # nobody waited for a while: what grew meanwhile is not news
                self._sizes, self._based, self._listed, self._recent = {}, set(), None, {}
            else:                                    # nobody looked meanwhile: "wanted a moment ago" did not age
                self._recent = {s: t + idle for s, t in self._recent.items()}
            self._idle_since = None
        # A subsystem is looked at while somebody wants it — and for `LINGER` after: its reader was answered and is
        # asking again, and what is written in between must be noticed for it (`last`, `since`), not start afresh.
        for s, _ in wanted:
            self._recent[s] = now_c
        self._recent = {s: t for s, t in self._recent.items() if now_c - t <= LINGER}
        subs = frozenset(self._recent)
        if self._listed is None or now_c - self._listed[0] >= RESCAN or self._listed[1] != subs:
            self._dirs, self._listed = self._list(subs), (now_c, subs)
        start = bucket_start(now, self.bucket_seconds)
        names = [_stamp(start) + ".events.jsonl"]
        if now - start < PREVIOUS_FOR:
            names.append(_stamp(start - self.bucket_seconds) + ".events.jsonl")
        sizes, seen = {}, set()
        for sub, d in self._dirs:
            for name in names:
                p = os.path.join(d, name)
                self.stats += 1
                try:
                    size = os.stat(p).st_size
                except OSError:
                    size = 0
                old = size if sub not in self._based else self._sizes.get(p, 0)   # a subsystem first looked at: from here
                if size > old:
                    kinds, old = self._kinds(p, old, size)
                    seen.update((sub, k) for k in kinds)
                sizes[p] = min(old, size)
        self._sizes, self._based = sizes, set(subs)  # a subsystem not looked at this time starts from a baseline when it returns
        if seen:
            with self._lock:
                self.seq += 1
                for pair in seen:
                    self.last[pair] = self.seq
                for w in self._waiters:
                    if w["wants"] & seen and not w["changed"]:
                        w["changed"], w["seq"] = True, self.seq      # the number it asks again with: what came after THIS
                        w["event"].set()

    # The newest epoch directory of every unit of `subs`, in each subsystem's tree and its alarms'. A line of an
    # older epoch is a fenced writer's, and no reader acts on it.
    def _list(self, subs: frozenset) -> list[tuple[str, str]]:
        out = []
        for root in self.roots:
            for sub in sorted(subs):
                for tree in (sub, alarm_tree(sub)):
                    base = os.path.join(root, tree)
                    try:
                        units = os.listdir(base)
                    except OSError:
                        continue
                    for unit in units:
                        try:
                            epochs = [int(m.group(1)) for m in map(EPOCH_DIR.match, os.listdir(os.path.join(base, unit))) if m]
                        except OSError:
                            continue
                        if epochs:
                            out.append((sub, os.path.join(base, unit, f"e{max(epochs)}")))
        return out

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
            except (ValueError, AttributeError):
                continue                             # a torn line: skipped, as every reader of a bucket skips it
        return kinds, old + whole


def client_gone(conn) -> bool:
    """Whether the other end of a held request closed its connection: readable, and nothing to read."""
    try:
        readable, _, _ = select.select([conn], [], [], 0)
        return bool(readable) and conn.recv(1, socket.MSG_PEEK) == b""
    except (OSError, ValueError):
        return True


def parse_wants(text: str) -> list[tuple[str, str]]:
    """`vms/io.input,det/motion` -> pairs. What does not look like `<subsystem>/<kind>` is dropped."""
    out = []
    for part in (text or "").split(","):
        sub, sep, kind = part.strip().partition("/")
        if sep and sub and kind:
            out.append((sub, kind))
    return out


# -- the reader's side: one held request per resource --------------------------------------------------------
class LongPoll:
    """Keeps one request held at each resource for what `wants()` says, and calls `wake.set()` when one is
    answered `changed`. `resources()` is `{server: url}` — the resources the reader asks anyway."""

    def __init__(self, wake: Wake, resources, wants, timeout: float = WAIT_MAX, backoff: float = BACKOFF, fetch=None):
        self.wake, self.resources, self.wants = wake, resources, wants
        self.timeout, self.backoff = timeout, backoff
        self.fetch = fetch or self._http
        self.waits = self.woken = self.errors = 0    # requests opened, answered `changed`, failed or refused
        self._urls: dict[str, str] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._stop = threading.Event()

    def _http(self, url: str, wants: list, timeout: float, since: int | None) -> dict:
        q = {"want": ",".join(f"{s}/{k}" for s, k in wants), "timeout": f"{timeout:g}", **({"since": since} if since is not None else {})}
        with urllib.request.urlopen(f"{url}/events/wait?{urllib.parse.urlencode(q)}", timeout=timeout + 5.0) as r:
            return json.loads(r.read())

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
            except Exception as e:                   # noqa: BLE001 — the resource is away, or does not know the route
                self.errors += 1
                log.debug("%s did not hold a wait (%s); the pass looks, as it did", server, e)
                self._stop.wait(self.backoff)
                continue
            since = rep.get("seq", since)
            if rep.get("changed"):
                self.woken += 1
                if not self._stop.is_set():
                    self.wake.set()
            elif rep.get("full") or rep.get("closed"):
                self.errors += 1                     # no room, or the door is shutting: back to the pass for a while
                self._stop.wait(self.backoff)

    def close(self) -> None:
        self._stop.set()                             # a thread inside a held request ends when the request does
