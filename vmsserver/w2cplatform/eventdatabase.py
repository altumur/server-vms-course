"""eventdatabase — the event index. Part of the resource job: one per RESOURCE,
over that resource's own tree — its buckets, and the copies it holds of its
peers' closed buckets (`.mirror/<server>/`). Nothing per console, nothing
cluster-wide: a console with a question asks every live resource's
`GET /events` and merges the answers by time (`MergedIndex`), on one box and
on a cluster alike.

Events are observations: written by the worker that holds a unit's epoch,
into that unit's bucket on its server's resource (w2cplatform.events). And
the tree they are written into IS the index already: split by subsystem, unit
and epoch in its directories, by time in its file names, ordered by time
inside each file, addressable by arithmetic — `bucket_path(sub, unit, epoch,
start)`. So nothing is copied out of it. A query computes which files its
window can touch, looks at each (`os.stat`), reads what it has not read yet,
and keeps what it read in a bounded cache. There is no second copy to keep in
step with the first, no pass that re-reads the tree, no rebuild after a
restart and no "catching up": the index is ready when the process is, and an
event is visible the moment its line is in the file.

It knows which subsystems exist by the directories it finds; a new one answers
the moment it starts writing. It knows nothing about what an event means:
`cam` is a field an event may carry.

    EventIndex(root, server)      the resource job's; nothing to start and nothing to rebuild
    query(...)                    subsystem, unit, cam (a field an event may carry), kind, class, time window
    listing()                     what the tree holds, from its directories alone: units, buckets, mirrors
    forget(server, paths)         retention removed a bucket: drop it from the cache (the resource calls this)
    MergedIndex(objects)          what a console has instead: every live resource's /events, merged
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # eventdatabase.py — the event index: the tree of buckets read where it lies, and a cache of what was read
#
# **Role in the module.** Lesson 13 on the box, Lesson 7 of М11 on the cluster: the reader of `events.py`.
# Events are written by workers into per-unit buckets on their server's resource; `GET /events` is answered
# over them, per RESOURCE, not per cluster: the resource job runs an `EventIndex` over its own root (own
# buckets and the `.mirror/<server>/` copies it holds). A console asks every live resource and merges
# (`MergedIndex`).
#
# **Why not a database — it was one, and what it cost.** Until 28 September this was an in-memory SQLite
# table rebuilt from the tree on every start and "tailed" every three seconds. The tail was the price, and
# it was the whole tree: to learn which files had grown it opened and parsed EVERY bucket, a year of them at
# the default retention — about a million files for twenty cameras, every three seconds. The four indexes
# over the flat table rebuilt what flattening had destroyed: two of them copied the directory layout, one
# split two values, and "everything in this hour" was covered by none. One connection and one mutex
# serialised every reader behind every other and behind the tail; and a restarted resource answered short
# while it rebuilt, saying `catching up` to a merge that did not listen. (The notes on the event log's
# concurrency and load, 28 September.)
#
# **What changes nothing.** The answer: the same rows, the same `truncated` from one row past the limit,
# alarms kept ahead of observations when a window overflows, `keep`, fencing by epoch, a peer's copies
# answered under the owner's name. `MergedIndex` below is untouched.
#
# **Freshness is looked at, not assumed.** A bucket is named by the time of its EVENTS, not by the time
# they were written: a scan of an archive (`detjob`, М10B Lesson 21) and a survey of somebody else's
# (Lesson 23) write lines stamped hours ago into buckets whose time is long past. So "a closed bucket never
# changes" is not a rule this index may lean on. It asks the file instead — size and modification time —
# and only for the files a query's window can touch: one or two per unit for the minutes automation asks
# about, a day's worth for a timeline. A file that grew is read from where the last read stopped.
#
# ## Module-level names
# `NARROW` — the widest window, in buckets, whose file names are computed rather than listed.
# `CACHE_BYTES` — the cache's ceiling by default.
# ================================================================================================
from __future__ import annotations

import heapq
import json
import os
import socket
import threading
import time
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone

from .events import (ALARM, CLASSES, EPOCH_DIR, EVENTS, MAX_EVENT_LATENESS, OBSERVATION, alarm_tree, bucket_path,
                     bucket_start, subsystems_under, tree_owner, when)
from .resource import MIRROR_DIR, mirrored_servers, resources_seen
from .rows import PARSE_ERRORS, Table, answer, finite

# Up to a day of buckets, the candidate files are COMPUTED from the window — a name from a time, and a stat
# that says whether it is there. Wider than that, the epoch's directory is listed and its names filtered:
# a query from 0 to 10^12 must not compute a billion names.
NARROW = 144
CACHE_BYTES = 64 << 20


# One bucket as read: its size and modification time when read (what says "unchanged" next time), how far
# into the file the read got (a half-written last line is not consumed — the next read starts at it), and
# its lines, each reduced once to what a query compares: `(t, kind, class, cam or None, the other fields)`.
@dataclass(frozen=True)
class _Read:
    size: int
    mtime: int
    offset: int
    lines: tuple
    ident: tuple = ()        # (device, inode): the same FILE, not only the same name
    head: bytes = b""        # its first bytes, as read — an inode is reused the moment it is freed


class EventIndex:
    """The event index of ONE resource: its own buckets and the mirror copies it holds, read where they lie.
    Not a subsystem and not a database: nothing to place, nothing to start, nothing to rebuild. The resource
    job serves it as `GET /events`."""

    def __init__(self, root: str, server: str | None = None, wall=time.time, bucket_seconds: int = 600,
                 cache_bytes: int = CACHE_BYTES):
        self.root, self.wall, self.bucket_seconds, self.cache_bytes = root, wall, bucket_seconds, cache_bytes
        self.server = server or socket.gethostname()
        self.state = "live"                              # ready as soon as it exists: there is nothing to catch up on
        self.torn = 0                                    # half-written lines seen, and not yet completed
        # The cache: absolute path -> `_Read`, least recently used first. The lock guards the DICTIONARY and
        # nothing else — files are read outside it, and a `_Read` is never changed, only replaced — so two
        # readers wait for each other for the length of a dictionary operation, not of a query.
        self._cache: OrderedDict[str, _Read] = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()
        # Which camera a unit's lines have named (`cam` in the line: a detector `7-motion` names camera 7).
        # A unit whose lines named exactly one camera is skipped by a query for another without being read.
        self._cams: dict[tuple[str, str, str], set] = {}

    # -- the tree, as candidates ------------------------------------------------------------------------
    # The places that hold buckets: this resource's root under its own name, and each peer's copies under
    # the PEER's name — a query answers "srv-a's events" whichever resource holds them.
    def _bases(self) -> list[tuple[str, str]]:
        out = [(self.server, self.root)]
        for peer in mirrored_servers(self.root):
            out.append((peer, os.path.join(self.root, MIRROR_DIR, peer)))
        return out

    def _epochs(self, unit_path: str) -> list[int]:
        try:
            return sorted(int(m.group(1)) for d in os.listdir(unit_path) if (m := EPOCH_DIR.match(d)))
        except FileNotFoundError:
            return []

    # The bucket files a window [t0, t1) can hold lines of, per epoch: computed for a narrow window, listed
    # for a wide one. A bucket starting at `s` holds [s, s + bucket), so the first candidate starts at the
    # bucket of t0 and the last at the bucket of the last instant before t1.
    def _candidates(self, base: str, sub: str, unit: str, t0: float, t1: float):
        first, last = bucket_start(max(t0, 0.0), self.bucket_seconds), bucket_start(max(t1 - 1e-6, 0.0), self.bucket_seconds)
        unit_path = os.path.join(base, sub, unit)
        for epoch in self._epochs(unit_path):
            if (last - first) / self.bucket_seconds <= NARROW:
                s = first
                while s <= last:
                    yield epoch, bucket_path(base, sub, unit, epoch, s)
                    s += self.bucket_seconds
                continue
            edir = os.path.join(unit_path, f"e{epoch}")
            try:
                names = os.listdir(edir)
            except FileNotFoundError:
                continue
            for name in sorted(names):
                m = EVENTS.match(name)
                if not m:
                    continue
                start = datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).timestamp()
                if first <= start <= last:
                    yield epoch, os.path.join(edir, name)

    # -- one bucket, read or re-read ----------------------------------------------------------------------
    # The file is looked at, not remembered: unchanged size and time — the cached lines; grown — only the
    # part past the last read; shrunk or rewritten — read again from the start; gone — nothing, and out of
    # the cache.
    #
    # "Grown" means the SAME file grown (feedback AX). A bucket that retention removed and a late scan of the
    # archive wrote again under the same name is at least as long as the old one, and read on from the old
    # offset it would keep the old lines and start the new ones mid-line — one lost, and counted as torn. So
    # the file's identity is compared (device and inode), and its first bytes too: a freed inode is handed to
    # the next file created, often at once.
    def _lines(self, path: str) -> tuple:
        try:
            st = os.stat(path)
        except FileNotFoundError:
            self._drop(path)
            return ()
        ident = (st.st_dev, st.st_ino)
        with self._lock:
            have = self._cache.get(path)
            if have is not None and have.size == st.st_size and have.mtime == st.st_mtime_ns and have.ident == ident:
                self._cache.move_to_end(path)
                return have.lines
        with open(path, "rb") as f:
            same = have is not None and have.ident == ident and st.st_size >= have.size \
                and f.read(len(have.head)) == have.head
            start, kept, head = (have.offset, have.lines, have.head) if same else (0, (), None)
            f.seek(start)
            data = f.read()
        head = data[:256] if head is None else head       # past the first line's name: two files differ there, if nowhere else
        cut = data.rfind(b"\n") + 1                      # a half-written last line waits for its end
        lines = list(kept)
        for raw in data[:cut].splitlines():
            if not raw.strip():
                continue
            try:
                e = json.loads(raw)
            except ValueError:                           # a torn line in the middle: the writer died mid-append
                self.torn += 1
                continue
            lines.append((float(e["t"]), str(e["kind"]), str(e.get("class", OBSERVATION)), e.get("cam"),
                          {k: v for k, v in e.items() if k not in ("t", "kind", "cam", "class")}))
        read = _Read(st.st_size, st.st_mtime_ns, start + cut, tuple(lines), ident, head)
        with self._lock:
            old = self._cache.pop(path, None)
            self._bytes -= old.size if old is not None else 0
            self._cache[path] = read
            self._bytes += read.size
            while self._bytes > self.cache_bytes and len(self._cache) > 1:
                _, gone = self._cache.popitem(last=False)
                self._bytes -= gone.size
        return read.lines

    def _drop(self, path: str) -> None:
        with self._lock:
            old = self._cache.pop(path, None)
            if old is not None:
                self._bytes -= old.size

    # -- the one read ---------------------------------------------------------------------------------------
    def query(self, t0: float, t1: float, cam: int | None = None, kind: str | None = None,
              subsystem: str | None = None, unit: str | None = None,
              current_epochs: dict[tuple[str, str], int] | None = None, limit: int = 1000,
              epoch_policy: dict[str, str] | None = None, keep: str = "newest", cls: str | None = None,
              by: str = "t") -> dict:
        """`by` is WHICH TIME the window and the order are in: `t`, when a line was written — or `occurred`,
        when its event happened (where the writer knew; `t` where it did not). In event time the window's
        buckets are read and `MAX_EVENT_LATENESS` further on: a line written late lies in a later file.

        `current_epochs` is {(subsystem, unit): epoch} — fencing is per unit, and only the
        unit's own subsystem knows its current epoch; the index just compares.

        `epoch_policy` is {subsystem: "fenced" | "earlier-run"} — what an older epoch MEANS
        there. Same comparison, two meanings: a writer that lost the race, or a finished
        earlier run of work that ends. The index is told; it does not decide.

        `keep` is which END of an overflowing window survives `limit` — and it is the CALLER's
        to choose, because "a thousand of the five thousand" means nothing without it. The
        default is "newest": nearly everything asked of an event log is a form of "what just
        happened", and the reader that wants the other end — paging forward through an archive
        from a cursor — knows that about itself and says so.

        The answer is ascending by time whichever end was kept, and it carries `truncated`, so a
        decision taken on part of a window cannot look like one taken on all of it.

        `cls` narrows to one traffic class — "show me the alarms of this hour" — and an unknown one
        is refused rather than answered with nothing, because an empty list is what "no alarms
        happened" looks like too.

        And the class earns its existence HERE: when the window overflows, OBSERVATIONS ARE DROPPED
        BEFORE ALARMS. A limit is a budget for a screenful, and spending it on the thousand statistics
        lines that crowded out the one contact that opened is the failure the class was introduced to
        prevent.

        What it costs is what the window touches, not what the tree holds: the files named by the window,
        a stat each, and a read of whatever of them is not in the cache yet."""
        if keep not in ("newest", "oldest"):
            raise ValueError(f"keep is 'newest' or 'oldest', not {keep!r}")
        if cls is not None and cls not in CLASSES:
            raise ValueError(f"event class is one of {', '.join(CLASSES)}, not {cls!r}")
        if by not in ("t", "occurred"):
            raise ValueError(f"by is 't' (when written) or 'occurred' (when it happened), not {by!r}")
        read_to = t1 + MAX_EVENT_LATENESS if by == "occurred" else t1
        # What the answer can still carry, and no more (feedback BD): `limit + 1` rows of each class from the end
        # `keep` names, held in two small heaps while the window is read. The cache's ceiling bounds the FILES
        # held, not the answer — a window with no `from` used to gather every matching line of the tree before
        # cutting it to a thousand, and eight such queries at once were the resource's memory. The `+ 1` is what
        # keeps `truncated` a fact.
        cap, seq, seen = max(0, int(limit)) + 1, 0, 0
        kept = {True: [], False: []}                     # alarm? -> heap of (rank, row); the smallest rank leaves first
        for server, base in self._bases():
            subs = subsystems_under(base)
            # A subsystem's lines lie in two trees — its own and its alarms' (`events.alarm_tree`) — and are
            # answered under ONE name: where a line lies is not whose it is. Both are read whatever class was
            # asked for: a bucket written before alarms had a tree holds both.
            for tree in ([subsystem, alarm_tree(subsystem)] if subsystem is not None else sorted(subs)):
                sub = tree_owner(tree)[0]
                for u in sorted(subs.get(tree, [])):
                    if unit is not None and u != str(unit):
                        continue
                    if cam is not None and not self._may_be(server, tree, u, cam):
                        continue
                    for epoch, path in self._candidates(base, tree, u, t0, read_to):
                        lines = self._lines(path)
                        if lines:
                            self._learn(server, tree, u, lines)
                        rel = os.path.relpath(path, base)
                        for t, k, c, ecam, fields in lines:
                            at = float(fields.get("occurred", t)) if by == "occurred" else t
                            if not t0 <= at < t1 or (kind is not None and k != kind) or (cls is not None and c != cls):
                                continue
                            the_cam = ecam if ecam is not None else (int(u) if u.isdigit() else None)
                            if cam is not None and the_cam != cam:
                                continue
                            seq, seen = seq + 1, seen + 1
                            heap = kept[c == ALARM]
                            rank = (at, -seq) if keep == "newest" else (-at, -seq)
                            item = (rank, (c == ALARM, at, sub, u, the_cam, epoch, k, server, rel, c, fields, t))
                            if len(heap) < cap:
                                heapq.heappush(heap, item)
                            elif rank > heap[0][0]:
                                heapq.heapreplace(heap, item)
        # One row PAST the limit, so `truncated` is a fact and not a guess. Alarms first, then time — `keep`
        # decides which end of the OBSERVATIONS survives, never whether an alarm does.
        rows = [row for _, row in sorted(kept[True], reverse=True)] + [row for _, row in sorted(kept[False], reverse=True)]
        truncated = seen > limit
        rows = sorted(rows[:limit], key=lambda r: r[1])  # alarms came first for the CUT; the answer is by time
        out = []
        for _, _at, sub, u, c, ep, k, server, rel, rcls, fields, t in rows:
            cur = (current_epochs or {}).get((sub, u))
            older = cur is not None and ep < cur
            was = (epoch_policy or {}).get(sub, "fenced") if older else "current"
            out.append({"subsystem": sub, "unit": u, "cam": c, "epoch": ep, "t": t, "kind": k, "server": server,
                        "bucket": rel, "class": rcls, "epoch_is": was, "fenced": was == "fenced", **fields})
        return {"events": out, "state": self.state, "truncated": truncated}

    # A unit is skipped for camera `cam` only when everything read of it so far named one OTHER camera; a unit
    # never read, or one naming several, is read. A numeric unit is its own camera.
    def _may_be(self, server: str, sub: str, unit: str, cam: int) -> bool:
        if unit.isdigit() and not self._cams.get((server, sub, unit)):
            return int(unit) == cam
        seen = self._cams.get((server, sub, unit))
        return not seen or len(seen) > 1 or cam in seen

    def _learn(self, server: str, sub: str, unit: str, lines: tuple) -> None:
        cams = {ecam for _, _, _, ecam, _ in lines if ecam is not None}
        if cams:
            self._cams.setdefault((server, sub, unit), set()).update(cams)

    # What the tree holds, from its directories alone — no file opened. For a person, a heartbeat and a test:
    # the answer to "is anything here", which a rebuild's row count used to give.
    def listing(self) -> dict:
        units = buckets = 0
        mirrored = []
        for server, base in self._bases():
            if server != self.server:
                mirrored.append(server)
            for sub, us in subsystems_under(base).items():
                for u in us:
                    n = 0
                    for epoch in self._epochs(os.path.join(base, sub, u)):
                        try:
                            n += sum(1 for f in os.listdir(os.path.join(base, sub, u, f"e{epoch}")) if EVENTS.match(f))
                        except FileNotFoundError:
                            pass
                    units += 1 if n else 0                   # a recorder's tree is a unit with no events: not counted
                    buckets += n
        return {"units": units, "buckets": buckets, "mirrored": sorted(mirrored), "cached": len(self._cache)}

    # Retention removed buckets: out of the cache now rather than at the next stat. Correctness does not
    # depend on it — a query stats every file it reads, and a missing one answers nothing — but the memory
    # does.
    def forget(self, server: str, paths: list[str]) -> int:
        base = self.root if server == self.server else os.path.join(self.root, MIRROR_DIR, server)
        for p in paths:
            self._drop(os.path.join(base, p))
        return len(paths)


# The fence, decided again over events already read: `current_epochs` is `{(subsystem, unit): epoch}` and
# `epoch_policy` what an older epoch means. The merge calls it over the union; the console calls it over an
# answer whose epochs it read AFTER the query — the units in the answer are the only ones it needs.
def refence(events: list, current_epochs: dict | None, epoch_policy: dict | None) -> list:
    cur = current_epochs or {}
    for e in events:
        c = cur.get((e["subsystem"], e["unit"]))
        older = c is not None and e["epoch"] < c
        e["epoch_is"] = (epoch_policy or {}).get(e["subsystem"], "fenced") if older else "current"
        e["fenced"] = e["epoch_is"] == "fenced"
    return events


# A RESOURCE'S ANSWER IS ANOTHER PROCESS'S WORDS (the review's eighth pass, part 4, a sibling of the peers' doors). The
# merge read `rep.get`, `rep["events"]`, `e["server"]` bare, after the fan-out's `try`: one resource of another build
# answering a list, or one line without `t`, raised out of `query` — automation's pass and the console's `/events` for
# every reader, every time. An answer that is not `{events: [...]}` is that resource not answering (`None`: the window
# incomplete, said); a line the merge cannot order, dedupe or fence is passed by and counted (`PEER_EVENTS`), and the
# rest of that resource's answer stands.
def _event_line(e: dict) -> dict:
    finite(e["t"]); str(e["server"]); str(e["kind"]); str(e["unit"]); str(e["subsystem"]); int(e["epoch"])
    if "occurred" in e:
        finite(e["occurred"])
    if not e.get("id"):
        e["bucket"]                                       # what a copy without a name is told apart by
    return e


def _answer(server: str, rep) -> dict | None:
    if not isinstance(rep, dict) or not isinstance(rep.get("events", None), list):
        return None
    events = []
    for e in rep["events"]:
        if not isinstance(e, dict):
            PEER_EVENTS.garbled(f"platform/events/{server}", "a line that is not an object")
            continue
        try:
            events.append(_event_line(e))
        except PARSE_ERRORS as err:
            PEER_EVENTS.garbled(f"platform/events/{server}", err)
    return {**rep, "events": events}


PEER_EVENTS = Table("peer_event", "that line is left out of the merged window", "line a resource answered")


# What stands behind a console's `/events`: nothing of its own. `query` asks every LIVE resource's
# `GET /events` (each answers from the index over its own tree — own buckets and mirror copies), merges by
# time, dedupes a dead server's copies when two peers hold them, drops a copy when the owner is live (it
# answered for itself), fences by `current_epochs`, and names in `state` the servers nobody answered for:
# `live; srv-a unreachable` for a resource that is silent and unmirrored (or live but not answering),
# `live; srv-a from mirror` when a peer's copy stood in. The same shape `EventIndex.query` returns, so
# `SpecConsole` cannot tell the difference. `fetch(url, params) -> dict` is HTTP by default; tests pass a
# call into the resource's index.
class MergedIndex:
    """A console's view of the event indexes: every live resource's `/events`, merged by time."""

    # Which resources exist — a listing of `resources/` and a read of every heartbeat there — at most once every
    # `SEEN_FOR` seconds of `clock` (the product's DD). It was read on every query: every poll of every open page, a
    # List and a Get per resource each time. A heartbeat comes every few seconds anyway, and liveness is still judged
    # by `wall` against the heartbeat's own time; what the cache costs is a resource that appeared, seen up to two
    # seconds late. The resources themselves are asked on every query, as before.
    SEEN_FOR = 2.0

    def __init__(self, objects, fetch=None, wall=time.time, lost_after: float = 45.0, timeout: float = 3.0,
                 cooldown: float = 10.0, lanes: int = 8, clock=time.monotonic):
        self.objects, self.wall, self.lost_after, self.timeout = objects, wall, lost_after, timeout
        self.clock = clock
        self._seen: tuple[float, dict] | None = None     # (read at, by `clock`; the resources) — one tuple, swapped whole
        self.fetch = fetch or self._http
        self.state = "live"
        # A resource that did not answer is not asked again for `cooldown` seconds: it is named in the answer as
        # not answering, straight away. Without it a resource that hung — live by heartbeat for another 45 s —
        # cost the full timeout to EVERY query, and a pass of a hundred queries waited five minutes on one box.
        # The simplest circuit breaker there is, and enough: it opens on one failure and closes on its own.
        self.cooldown, self.lanes = cooldown, lanes
        # One merge serves the console's requests, and those come in on threads of their own; the lanes do not
        # touch this map, only the query that owns them does. Here each read and write of it is one dict
        # operation, whole under the GIL, and the worst two queries can do is ask a hung server once more. A port
        # without a GIL guards it — the product keeps it under a mutex (feedback AW); without one it is a race.
        self._quiet: dict[str, float] = {}               # server -> not asked again until

    def seen(self) -> dict[str, dict]:
        """`resources_seen`, read again only once the last read is `SEEN_FOR` seconds old. A store that does not
        answer raises, as before; nothing is cached for it."""
        now, last = self.clock(), self._seen
        if last is None or now - last[0] >= self.SEEN_FOR:
            last = self._seen = (now, resources_seen(self.objects))
        return last[1]

    def _http(self, url: str, params: dict) -> dict:
        with urllib.request.urlopen(f"{url}/events?{urllib.parse.urlencode(params)}", timeout=self.timeout) as r:
            return json.loads(answer(r))                        # up to a bound (`rows.answer`; the review's eighth pass)

    def _fan_out(self, servers: list[str], seen: dict, params: dict) -> dict:
        """{server: its answer, or None if it did not give one} — asked in parallel, `lanes` at a time."""
        def one(server):
            try:
                return _answer(server, self.fetch(seen[server]["url"], params))
            except Exception:                                   # noqa: BLE001 — any failure is "did not answer"
                return None
        if len(servers) <= 1:
            return {s: one(s) for s in servers}
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(self.lanes, len(servers))) as pool:
            return dict(zip(servers, pool.map(one, servers)))

    def query(self, t0: float, t1: float, cam=None, kind=None, subsystem=None, unit=None, current_epochs=None,
              limit: int = 1000, epoch_policy: dict[str, str] | None = None, keep: str = "newest",
              cls: str | None = None, by: str = "t") -> dict:
        """`by` as in `EventIndex.query`: asked of every resource, and the merge orders by the same time.

        `keep` as in `EventIndex.query`, and it has to be carried BOTH ways: the merge asks
        each resource for a window and then cuts the union to `limit` again, so a limit with no
        direction dropped the newest end twice — once per resource, once more over the merge.

        The overflow policy is carried both ways for the same reason: each resource kept its alarms
        ahead of its observations, and the merge must do it again over the union, or an alarm that
        survived on its own server is dropped when it meets a busier neighbour's window.

        `truncated` is true if ANY resource cut its answer or the merge cut theirs: the reader is
        told the window is partial, not which server made it partial.

        `complete` is the other half of "is this all of it", and a reader that DECIDES on a window —
        automation moving its cursor past it — needs it: an empty window and a window whose server did not
        answer look the same in `events`. `incomplete` names each server the window is missing, and why:
        live by heartbeat and did not answer; answered, but its own state is not `live` (`empty`,
        `catching up` — a restarted resource rebuilding); or silent, and it could have written inside the
        window — even when a peer answers with its copies, because a copy holds only CLOSED buckets and the
        open one is in none. A server silent since before the window cannot have written in it and does not
        make it incomplete: a box taken out of service must not hold every reader's window for ever.

        The check below is the SAME refusal the index makes, and it has to be here too rather
        than left to the resources: this method reads any failure from a resource as "unreachable"
        (live by heartbeat, not answering), so a caller's bad `keep` would come back as an empty
        window and an infrastructure fault that never happened."""
        if keep not in ("newest", "oldest"):
            raise ValueError(f"keep is 'newest' or 'oldest', not {keep!r}")
        if cls is not None and cls not in CLASSES:
            raise ValueError(f"event class is one of {', '.join(CLASSES)}, not {cls!r}")
        if by not in ("t", "occurred"):
            raise ValueError(f"by is 't' (when written) or 'occurred' (when it happened), not {by!r}")
        order = when if by == "occurred" else (lambda e: e["t"])
        now = self.wall(); seen = self.seen()
        live = {s for s, hb in seen.items() if now - float(hb["ts"]) <= self.lost_after}
        params = {k: v for k, v in (("from", t0), ("to", t1), ("cam", cam), ("kind", kind), ("subsystem", subsystem),
                                    ("unit", unit), ("limit", limit), ("keep", keep), ("class", cls),
                                    ("by", by if by != "t" else None)) if v is not None}
        events, unreachable, from_mirror, have = [], [], set(), set()
        incomplete: dict[str, str] = {}
        truncated = False
        # Every live resource is asked AT ONCE, not one after another: the answer takes as long as the slowest
        # resource, not as long as all of them together. The answers are then read in server order, so the merge
        # is the same whichever came back first.
        ask = [s for s in sorted(live) if self._quiet.get(s, 0.0) <= now]
        answers = self._fan_out(ask, seen, params)
        for server in sorted(live):
            if server not in ask:
                unreachable.append(server); incomplete[server] = "did not answer a moment ago"; continue
            rep = answers[server]
            if rep is None:                                     # live by heartbeat, not answering
                self._quiet[server] = now + self.cooldown
                unreachable.append(server); incomplete[server] = "did not answer"; continue
            self._quiet.pop(server, None)
            said = str(rep.get("state", "live"))
            if not said.startswith("live"):
                incomplete[server] = f"said {said}"             # its own word: rebuilding, or nothing yet
            truncated = truncated or bool(rep.get("truncated"))
            for e in rep["events"]:
                if e["server"] != server:                         # a copy this resource holds for a peer
                    if e["server"] in live:
                        continue                                  # the owner answers for itself
                    # A copy is known by the line's NAME. Without one — a line written before lines had names —
                    # by where and when it was written, which made two events of one kind in one instant one.
                    key = e.get("id") or (e["server"], e["bucket"], e["t"], e["kind"], e["unit"])
                    if key in have:
                        continue                                  # two peers hold the same copy
                    have.add(key); from_mirror.add(e["server"])
                events.append(e)
        for server in sorted(seen):
            if server not in live and server not in from_mirror:
                unreachable.append(server)                        # silent, and nobody holds its copies
            if server not in live and float(seen[server]["ts"]) + self.lost_after >= t0:
                incomplete[server] = ("silent; its closed buckets from a copy, its open one from nobody"
                                      if server in from_mirror else "silent")
        events.sort(key=order)
        if len(events) > limit:
            truncated = True
            alarms = [e for e in events if e.get("class") == ALARM]
            rest = [e for e in events if e.get("class") != ALARM]
            # Alarms first; what is left over is the observations' budget. A window holding more alarms
            # than the whole limit is cut like anything else — an unbounded answer is not a kindness to
            # anybody — but it is cut with the observations already gone, and `truncated` says so.
            alarms = alarms if len(alarms) <= limit else (alarms[-limit:] if keep == "newest" else alarms[:limit])
            room = max(0, limit - len(alarms))
            events = sorted(alarms + (rest[-room:] if keep == "newest" else rest[:room]), key=order)
        refence(events, current_epochs, epoch_policy)             # each resource fenced its own; re-decide over the merge
        unreachable = sorted(set(unreachable))
        self.state = "live" + (f"; {', '.join(unreachable)} unreachable" if unreachable else "") \
                            + (f"; {', '.join(sorted(from_mirror))} from mirror" if from_mirror else "")
        return {"events": events, "state": self.state, "truncated": truncated,
                "complete": not incomplete, "incomplete": incomplete}
