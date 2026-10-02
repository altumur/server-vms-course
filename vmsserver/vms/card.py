"""The camera's card, and the camera's frames in memory — with no archive engine on the camera.

A camera that runs this platform records a backup of itself on its card (`when: offline`, Lesson 26). Until now
the course wrote that card the way a server writes a disk: a volume of ObjectStorage, opened through `obsd`, by a
`RecWorker`. The product does not, and its reason is the camera (feedback CB, CT, CV, DG and the product's design
note on attaching the firmware, §12, §14): Linux on the camera sees some 32 MB, its flash 8 MB, and the engine is a
4.5 MB library, `libstdc++` and 20–25 MB of memory for a writer and a reader. So the card is a BUFFER — what the
camera keeps until the recording server has it — and not an archive of its own. The server never sees its format:
a range of it travels as sample records in the answer to a request (М12 Lesson 16). One archive format stays where
it is needed, on the server. An engine on a camera is a future, optional variant — a NAS or a mini-disk, a `local`
or `network` volume like a server's — and is not built here.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # card.py — one ring in memory, a card of plain files, and the recorder that writes the one into the other
#
# **Role in the module.** Four pieces, each the product's own (`vmsworker/camfeed`, `cardbuf`, `cardact`, and the
# platform's recorder over them in `cmd/vmscam`):
#
#     CamRing        the camera's frames in MEMORY: one ring of the last `RING_SECONDS`, never more than
#                    `RING_BYTES`, always beginning at a key frame and letting go of whole groups of pictures.
#                    Everything that needs frames reads it: the pusher (М12), and the card's writer. The camera
#                    with no card pushes all the same, and keeps in memory what its budget allows
#     CardBuffer     the CARD: per stream, segment files of sample records, only ever appended to; a byte budget,
#                    the oldest segments deleted when it is spent; a range reader that says an error out loud
#     CardActuator   the recorder's actuator on the camera: a recording on the card is written from the ring into
#                    the card. On HOLD it writes nothing — the ring is the pre-record; KEPT, the ring lets go of
#                    nothing by its window and what it must let go of past its byte ceiling goes to the card
#     CardRecorder   the platform's recorder over the two: `RecWorker`'s gate (`when: offline`, `primary_needs_cover`,
#                    memory first, the book of primaries) unchanged, its volume layer replaced by the card
#
# **Why a buffer and not an engine.** What the engine gives a server — one format for every reader, blocks and an
# index, wear and recovery discipline, a timeline over months — a camera's card does not need: it holds hours or
# days, it is read by ONE reader (the server asking for a range), and its format is nobody's business but the
# camera's. What it needs is to cost nothing: one write buffer, no index file (the segments' names and their first
# and last samples are the index, read when the card opens), and a write path that never makes the camera wait.
#
# **The write path never waits for the card.** Frames reach the card off the ring's lock: the ring hands each to a
# bounded queue (`QUEUE_LEN`, about twenty seconds at 25 fps), and the card is written from the queue. A card slower
# than the stream — a cheap card, a card wearing out — fills the queue, and then frames for the CARD are dropped up to
# the next key frame, counted (`samples_dropped`); the ring, the pusher and the firmware never slow down for it. A
# write the card refuses kills the recording (`pump`), and the recorder starts it again after its backoff, like any
# pipeline that died. A card full is not an error: its oldest segments go.
#
# **The card as the backup `when: offline`.** The gate is Lesson 26's, word for word — what the stream says first,
# then the book of primaries, then the cluster. What changes is what "hold" and "release" mean here: on hold the ring
# is the pre-record and the card is untouched; a break the camera can continue is KEPT in the ring (memory first,
# feedback CB) for `defer_for`; released, the card gets what the kept ring spilled, then what the ring still holds,
# then every frame live.
#
# **What it does NOT do.** No obsd, no `Session` — `CardRecorder` is built with `NO_ENGINE`, which refuses every
# call, so a path that still reached for the engine fails loudly in the tests instead of quietly on a camera. No
# archive door: the card is read by asking the camera (`answer_range`, the camera's answer to a range request — М12
# Lesson 16, the ingest), never by a door on the camera that nobody can reach.
#
# ## Public API
# - `CamRing(window, max_bytes)` — `add(sample)`, `subscribe(fn)`, `set_keep(keep, spill)`, `after(t_ms)`, `status(now)`.
# - `CardBuffer(path, budget)` — `append(stream, sample)`, `finish(stream)`, `coverage(recording)`, `range(recording,
#   t0, t1)`, `stats()`, `err`, `close()`. Raises `CardError` (an `OSError`): `NeedKey`, `Backwards`, a read cut short.
# - `CardActuator(ring, card)` — the recorder's actuator: `(verb, cam)`, `keep(cid, on)`, `pump()`, `drain()`, `stats(cid)`.
# - `CardRecorder(name, vars_, objects, ring, ...)` — a `RecWorker` whose volume is the card; `answer_range`.
# - `declare_card(vars_, server, path, budget)` — the card as the camera's own cluster declares it (`kind: edge`).
# ================================================================================================
from __future__ import annotations

import collections
import logging
import os
import threading
import time

from w2cplatform.obsd import SMPL, Sample, archive_ms, unix_s

from . import volumes
from .archive import stitch
from .recworker import RecWorker
from .worker import VmsWorker

log = logging.getLogger("card")

# The ring's size (feedback CT, DE: the product's camera, 60 s and 32 MiB). Sixty seconds because the ring is the
# card's pre-record too: a break the camera does not see itself is noticed only after `LOST_AFTER`, and a primary
# just placed gets `START_GRACE` on top. 32 MiB is sixty seconds at 4 Mbit/s, kept outside the Go heap in the
# product; the owner's decision is to confirm it by measuring on a camera, and to go to 16 MiB if memory is short.
RING_SECONDS = 60.0
RING_BYTES = 32 << 20
QUEUE_LEN = 512                          # frames waiting for the card, per recording: about twenty seconds at 25 fps
SPILL_LEN = QUEUE_LEN * 4                # what a kept ring hands over past its ceiling: groups of pictures, in bursts
CARD_BUDGET = 1 << 30                    # the card's budget when the declaration names none
SEGMENT_BYTES = 16 << 20                 # a segment closes at the first key frame past this…
SEGMENT_SPAN = 300.0                     # …or past five minutes of footage
SYNC_EVERY = 5.0                         # how often what is written is forced onto the card


class CardError(OSError):
    """The card refused, or could not give back, what it was asked for."""


class NeedKey(CardError):
    """A delta frame with no segment of its stream open: it could not be read without the key frame before it."""


class Backwards(CardError):
    """A sample older than the last one of its stream: a stream only goes forward, across its segments too."""


# A camera has no archive engine (the product's §12): a recorder built with this one fails loudly if anything in it
# still reaches for a daemon. `timeout` is read by the volume layer's waits and is the only thing it answers.
class _NoEngine:
    timeout = 10.0

    def __getattr__(self, name):
        raise RuntimeError(f"a camera has no archive engine: its card is a CardBuffer, not an obsd volume ({name})")


NO_ENGINE = _NoEngine()


def _group_end(frames, start: int = 0) -> int:
    """The index of the next key frame after `start` — where the group of pictures that begins there ends."""
    for i in range(start + 1, len(frames)):
        if frames[i].key:
            return i
    return len(frames)


# -- the camera's frames in memory (the product's camfeed) -------------------------------------------------------
class CamRing:
    """The last `window` seconds of the camera's frames, from a key frame, in at most `max_bytes`. Every reader of
    frames reads this one ring — the pusher and the card's writer — so the camera holds each frame in memory once."""

    def __init__(self, window: float = RING_SECONDS, max_bytes: int = RING_BYTES, clock=time.time):
        self.window, self.max_bytes, self.clock = float(window), int(max_bytes), clock
        self._lock = threading.Lock()
        self._frames: list[Sample] = []
        self.bytes = 0
        self.added = 0                                   # samples it was given in all
        self._subs: dict[int, object] = {}
        self._next = 0
        self._keep, self._spill = False, None
        # Whether the camera's frames are arriving: set by whoever reads them (the firmware's frame socket on a
        # camera, `camfeed.Source` in the product). The worker says both in its heartbeat; here, `status`.
        self.connected = False
        self.last_frame_at: float | None = None

    # An empty ring takes only a key frame: nothing before it can be decoded. Room is made by letting go of the oldest
    # WHOLE group of pictures — a group cut in the middle is a group nobody can play — and a kept ring hands what it
    # lets go of to `spill` instead of dropping it. Every subscriber gets the sample as it came, under the lock: a
    # subscriber must not wait for anything (the card's writer only queues).
    def add(self, s: Sample) -> None:
        with self._lock:
            self.added += 1
            self.last_frame_at = self.clock()
            if self._frames or s.key:
                size = len(s.body)
                if size > self.max_bytes:
                    while self._frames:
                        self._drop_group()                  # larger than the ring: it starts over at the next key frame
                else:
                    while self._frames and self.bytes + size > self.max_bytes:
                        self._drop_group()
                    if self._frames or s.key:
                        self._frames.append(s)
                        self.bytes += size
                        self._trim_window()
            for fn in list(self._subs.values()):
                fn(s)

    def _drop_group(self) -> None:
        k = _group_end(self._frames)
        group = self._frames[:k]
        if self._keep and self._spill is not None:
            self._spill(group)
        del self._frames[:k]
        self.bytes -= sum(len(f.body) for f in group)

    # The oldest group goes while the rest still covers the window. A KEPT ring keeps everything: a break the server
    # has not taken is in it, and only the byte ceiling may make it let go — to the card.
    def _trim_window(self) -> None:
        window_ms = self.window * 1000.0
        while not self._keep and window_ms > 0 and len(self._frames) > 1:
            k = _group_end(self._frames)
            if k >= len(self._frames):
                return
            if self._frames[-1].end - self._frames[k].begin < window_ms:
                return
            self._drop_group()

    def subscribe(self, fn):
        """`fn(sample)` for every sample from now on; returns the call that stops it."""
        with self._lock:
            sid, self._next = self._next, self._next + 1
            self._subs[sid] = fn

        def cancel():
            with self._lock:
                self._subs.pop(sid, None)
        return cancel

    def set_keep(self, keep: bool, spill=None) -> None:
        """Kept: nothing let go by the window; past the byte ceiling the oldest groups go to `spill(frames)`,
        under the ring's lock — it must not wait. Ordinary again: it shrinks to its window on the next sample."""
        with self._lock:
            self._keep, self._spill = bool(keep), spill if keep else None

    def after(self, t_ms: int = 0) -> list[Sample]:
        """What the ring holds past `t_ms` (archive ms), from the first key frame after it — from its oldest key
        frame when it does not reach back that far; 0: all of it."""
        with self._lock:
            for i, f in enumerate(self._frames):
                if (t_ms == 0 or f.begin > t_ms) and f.key:
                    return list(self._frames[i:])
            return []

    def status(self, now: float | None = None) -> dict:
        """What the camera's worker says about its frames: arriving or not, how long since the last, and the ring."""
        now = self.clock() if now is None else now
        with self._lock:
            span = (self._frames[-1].end - self._frames[0].begin) / 1000.0 if self._frames else 0.0
            out = {"frames_connected": self.connected, "ring_samples": len(self._frames), "ring_bytes": self.bytes,
                   "ring_span_s": round(span, 3), "ring_window_s": self.window, "ring_max_bytes": self.max_bytes}
            if self.last_frame_at is not None:
                out["last_frame_age_s"] = round(now - self.last_frame_at, 3)
            return out


# -- the card: segment files with a byte budget (the product's cardbuf) --------------------------------------------
#
#     <path>/<recording>/e<epoch>/<begin>.smpl     sample records back to back, as they travel (`Sample.encode`);
#                                                  <begin> is the first sample's archive time, in ms
#
# A segment opens on a key frame and is only ever appended to. One that a power loss cut is read up to its last whole
# record and cut there when the card opens; nothing else needs repair, because nothing else is written.
class _Segment:
    __slots__ = ("stream", "path", "first", "last", "last_begin", "bytes")

    def __init__(self, stream: str, path: str):
        self.stream, self.path = stream, path
        self.first = self.last = self.last_begin = 0         # archive ms: the first sample's begin, the last's end
        self.bytes = 0


def _read_record(f):
    """One sample record from `f`, or None at the end or at a record cut short."""
    head = f.read(SMPL.size)
    if len(head) < SMPL.size:
        return None, len(head)
    magic, major, subtype, flags, begin, end, sl, bl = SMPL.unpack(head)
    if magic != b"SMPL":
        return None, len(head)
    rest = f.read(sl + bl)
    if len(rest) < sl + bl:
        return None, len(head) + len(rest)
    return Sample(major, subtype, flags, begin, end, rest[:sl], rest[sl:]), SMPL.size + sl + bl


class CardBuffer:
    """One card. `budget` is its size in bytes: when it is spent, the oldest segments go, whatever recording they
    belong to. Opening it reads what is on it; a card that cannot be opened raises `OSError` here and nowhere else."""

    def __init__(self, path: str, budget: int = CARD_BUDGET, segment_bytes: int = SEGMENT_BYTES,
                 segment_span: float = SEGMENT_SPAN, sync_every: float = SYNC_EVERY, clock=time.monotonic):
        self.path = path[len("file://"):] if path.startswith("file://") else path
        self.budget = int(budget) or CARD_BUDGET
        self.segment_bytes, self.segment_span, self.sync_every, self.clock = segment_bytes, segment_span, sync_every, clock
        self._lock = threading.Lock()
        self.segs: list[_Segment] = []                       # oldest first
        self.bytes = 0
        self.cur: _Segment | None = None
        self._f = None
        self._synced = 0.0
        self.err: OSError | None = None                      # the last write error: the card is failing
        os.makedirs(self.path, exist_ok=True)
        self._scan()

    def _scan(self) -> None:
        for root, _, files in os.walk(self.path):
            for name in files:
                if not name.endswith(".smpl"):
                    continue
                seg = self._read_segment(os.path.relpath(root, self.path).replace(os.sep, "/"), os.path.join(root, name))
                if seg is None:
                    os.remove(os.path.join(root, name))      # nothing whole in it
                    continue
                self.segs.append(seg)
                self.bytes += seg.bytes
        self.segs.sort(key=lambda s: s.first)

    @staticmethod
    def _read_segment(stream: str, path: str) -> _Segment | None:
        seg, whole = _Segment(stream, path), 0
        with open(path, "r+b") as f:
            while True:
                smp, n = _read_record(f)
                if smp is None:
                    break                                    # the end, or a record a power loss cut: all before it is whole
                if whole == 0:
                    seg.first = smp.begin
                seg.last, seg.last_begin, whole = smp.end, smp.begin, whole + n
            if whole == 0:
                return None
            f.truncate(whole)
        seg.bytes = whole
        return seg

    # One sample of `stream`. A new segment opens on a key frame — when none is open for the stream, when the open one
    # is full, or when another stream is being written; a delta frame with no segment open for its stream is refused.
    def append(self, stream: str, s: Sample) -> None:
        with self._lock:
            cur = self.cur
            if cur is not None and cur.stream == stream and cur.bytes > 0 and s.begin <= cur.last_begin:
                raise Backwards(f"{stream}: {s.begin} is not after {cur.last_begin}")
            if cur is None or cur.stream != stream or (s.key and self._full(s)):
                if not s.key:
                    raise NeedKey(f"{stream}: a stream opens on a key frame")
                try:
                    self._open(stream, s.begin)
                except OSError as e:
                    self.err = e
                    raise
            data = s.encode()
            try:
                self._write(data)
                if self.clock() - self._synced >= self.sync_every:
                    os.fsync(self._f.fileno())
                    self._synced = self.clock()
            except OSError as e:
                self.err = e
                raise
            self.cur.last, self.cur.last_begin, self.cur.bytes = s.end, s.begin, self.cur.bytes + len(data)
            if not self.cur.first:
                self.cur.first = s.begin
            self.bytes += len(data)
            self.err = None
            self._retain()

    # The one place bytes reach the card — a test replaces it to have the card fail.
    def _write(self, data: bytes) -> None:
        self._f.write(data)
        self._f.flush()

    def _full(self, s: Sample) -> bool:
        return self.cur.bytes >= self.segment_bytes or s.begin - self.cur.first >= self.segment_span * 1000

    def _open(self, stream: str, begin: int) -> None:
        self._close_locked()
        d = os.path.join(self.path, *stream.split("/"))
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{begin}.smpl")
        self._f = open(path, "ab")
        self.cur = _Segment(stream, path)
        self.segs.append(self.cur)
        self._synced = self.clock()

    def finish(self, stream: str) -> None:
        """Close the stream's open segment: its next sample opens a new one, on a key frame."""
        with self._lock:
            if self.cur is not None and self.cur.stream == stream:
                self._close_locked()

    def close(self) -> None:
        with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        f, cur, self._f, self.cur = self._f, self.cur, None, None
        if f is not None:
            try:
                f.flush()
                os.fsync(f.fileno())
            finally:
                f.close()
        if cur is not None and cur.bytes == 0:                # opened and never written
            try:
                os.remove(cur.path)
            except OSError:
                pass
            self._drop(cur)

    # The budget: the oldest closed segments go while the card is over it. The open one never does.
    def _retain(self) -> None:
        while self.bytes > self.budget and self.segs and self.segs[0] is not self.cur:
            old = self.segs[0]
            try:
                os.remove(old.path)
            except FileNotFoundError:
                pass
            self._drop(old)
            try:
                os.rmdir(os.path.dirname(old.path))          # the epoch's directory, if that was its last segment
            except OSError:
                pass

    def _drop(self, seg: _Segment) -> None:
        if seg in self.segs:
            self.segs.remove(seg)
            self.bytes -= seg.bytes

    def coverage(self, recording: str) -> list[tuple[float, float]]:
        """What the card holds of `recording` (every epoch), in unix seconds: one span per segment, in order."""
        with self._lock:
            return [(unix_s(s.first), unix_s(s.last)) for s in self.segs
                    if s.stream.startswith(f"{recording}/") and s.bytes > 0]

    # Every sample of `recording` that begins in `[t0, t1)` (unix seconds), in time order, each segment's from its
    # first key frame in the range on.
    #
    # An error is RAISED, never taken for the end: a camera answering a server's request for a range must not answer
    # with part of it as if it were all — the server would take the rest for "the card has none" and never ask
    # again. The end of a segment is the size the card wrote when the range began, so the record being written right
    # now is not read, and a segment shorter than that is an error.
    def range(self, recording: str, t0: float, t1: float) -> list[Sample]:
        lo, hi = archive_ms(t0), archive_ms(t1)
        with self._lock:
            if self._f is not None:
                self._f.flush()
            parts = [(s.path, s.bytes) for s in self.segs
                     if s.stream.startswith(f"{recording}/") and s.bytes > 0 and s.first < hi and s.last > lo]
        out: list[Sample] = []
        for path, size in parts:
            out += self._range_of(path, size, lo, hi)
        return out

    @staticmethod
    def _range_of(path: str, size: int, lo: int, hi: int) -> list[Sample]:
        try:
            f = open(path, "rb")
        except FileNotFoundError:
            return []                                        # the budget took it after it was listed: no longer held
        except OSError as e:
            raise CardError(f"reading {path}: {e}") from None
        out, read, started = [], 0, False
        with f:
            while read < size:
                try:
                    smp, n = _read_record(f)
                except OSError as e:
                    raise CardError(f"reading {path}: {e}") from None
                if smp is None or read + n > size:
                    raise CardError(f"reading {path}: {read} of {size} bytes — the segment is shorter than written")
                read += n
                if smp.begin >= hi:
                    break
                if smp.begin < lo or (not started and not smp.key):
                    continue
                started = True
                out.append(smp)
        return out

    def stats(self) -> tuple[int, int, int]:
        """(segments, bytes, budget)."""
        with self._lock:
            return len(self.segs), self.bytes, self.budget


# -- the recorder's actuator on the camera (the product's cardact) -------------------------------------------------
_CUT = object()                                          # in a queue: frames were dropped before what follows


class _Rec:
    def __init__(self, cid, stream: str, hold: bool):
        self.id, self.stream, self.hold, self.keep = cid, stream, hold, False
        self.live: collections.deque = collections.deque()
        self.spill: collections.deque = collections.deque()
        self.release_due = False                         # released: the spill, then the ring, then live — on the writer
        self.cutting = False                             # the queue overflowed: frames dropped up to the next key frame
        self.last = 0                                    # begin (archive ms) of the last sample on the card
        self.need_key = True
        self.written = self.dropped = 0
        self.last_error = ""
        self.failed = False                              # the card refused a write: dead, restarted after a backoff
        self.lock = threading.Lock()
        self.wake = threading.Condition(self.lock)
        self.stopped = False
        self.untap = None
        self.thread: threading.Thread | None = None


class CardActuator:
    """Writes the card's recordings from the camera's ring. `threaded`: a writer thread per recording (a camera);
    off, the tests write with `drain()` when they choose — the card that has not caught up yet is a test, too."""

    def __init__(self, ring: CamRing, card: CardBuffer | None = None, threaded: bool = True):
        self.ring, self.card, self.threaded = ring, card, threaded
        self.recs: dict[str, _Rec] = {}
        self._lock = threading.Lock()
        self.calls: list[tuple[str, str]] = []

    # A recording that records only without its primary starts ON HOLD; any other writes from its first key frame.
    # `release` takes it off hold; going back on hold is a restart under the same epoch (the gate's `_actuate`).
    def __call__(self, verb: str, cam: dict) -> bool:
        cid = str(cam["id"])
        self.calls.append((verb, cid))
        if verb in ("start", "restart"):
            if self.card is None:
                return False                             # no card open: nothing to write into, the reconciler retries
            self._stop(cid)
            r = _Rec(cid, f"{cid}/e{int(cam.get('epoch', 0))}", bool(cam.get("hold")))
            r.untap = self.ring.subscribe(lambda s, r=r: self._offer(r, s))
            with self._lock:
                self.recs[cid] = r
            if self.threaded:
                r.thread = threading.Thread(target=self._run, args=(r,), name=f"card-{cid}", daemon=True)
                r.thread.start()
            log.info("card: recording %s into %s%s", cid, r.stream, " on hold" if r.hold else "")
            return True
        if verb == "stop":
            self._stop(cid)
            return True
        if verb == "release":
            return self.hold(cid, False)
        return False

    # Under the ring's lock: queue it or count it, never wait. On hold nothing is owed to the card — the ring is the
    # pre-record. A full queue drops this frame and every frame after it up to the next key frame, so the card
    # has a clean cut and never half a group of pictures; the cut is marked, and the writer closes the segment there.
    def _offer(self, r: _Rec, s: Sample) -> None:
        with r.lock:
            if r.hold or r.stopped:
                return
            if r.cutting and not s.key:
                r.dropped += 1
                return
            room = QUEUE_LEN - len(r.live)
            if room < (2 if r.cutting else 1):
                r.dropped += 1
                r.cutting = True
                return
            if r.cutting:
                r.live.append(_CUT)
                r.cutting = False
            r.live.append(s)
            r.wake.notify()

    def _spilled(self, r: _Rec, frames: list) -> None:
        with r.lock:
            if len(r.spill) + len(frames) > SPILL_LEN:
                r.dropped += len(frames)
                r.spill.append(_CUT)
            else:
                r.spill.extend(frames)
            r.wake.notify()

    def _run(self, r: _Rec) -> None:
        while True:
            with r.lock:
                while not (r.live or r.spill or r.release_due or r.stopped):
                    r.wake.wait(1.0)
                if r.stopped:
                    return
            self._drain(r)

    def drain(self, cid=None) -> None:
        """Write what is queued — every recording's, or one's. A camera's writer threads do this on their own."""
        with self._lock:
            recs = list(self.recs.values()) if cid is None else [r for k, r in self.recs.items() if k == str(cid)]
        for r in recs:
            self._drain(r)

    # The writer: first what a kept ring spilled (the oldest of a break), then — once released — what the ring still
    # holds that the card has not had, then live. A frame that came both ways is written once (`_write`).
    def _drain(self, r: _Rec) -> None:
        while True:
            with r.lock:
                if r.spill:
                    s = r.spill.popleft()
                elif r.release_due:
                    r.release_due = False
                    s = None
                elif r.live:
                    s = r.live.popleft()
                else:
                    return
            if s is None:
                for x in self.ring.after(r.last):
                    self._write(r, x)
            else:
                self._write(r, s)

    # One sample onto the card, in order, from a key frame. A write the card refuses marks the recording dead for
    # `pump`; a delta frame the card cannot open a segment with waits for the next key frame.
    def _write(self, r: _Rec, s) -> None:
        if s is _CUT:
            r.need_key = True
            if self.card is not None:
                self.card.finish(r.stream)               # a hole on the card is a hole in its coverage, not a seam
            return
        if s.begin <= r.last or (r.need_key and not s.key) or self.card is None:
            return
        try:
            self.card.append(r.stream, s)
        except NeedKey:
            r.need_key = True
            return
        except Backwards:
            return
        except OSError as e:
            r.last_error, r.need_key, r.failed = str(e), True, True
            return
        r.last, r.need_key, r.last_error = s.begin, False, ""
        r.written += 1

    def hold(self, cid, hold: bool) -> bool:
        """On hold (True) or released (False). False when it is not running here, or already so."""
        with self._lock:
            r = self.recs.get(str(cid))
        if r is None:
            return False
        with r.lock:
            if r.hold == hold:
                return False
            r.hold = hold
            r.release_due = not hold
            r.need_key = True
            r.wake.notify()
        if hold and self.card is not None:
            self.card.finish(r.stream)
        log.info("card: %s %s", cid, "on hold: the ring is the pre-record" if hold else "released: the card writes")
        return True

    def keep(self, cid, keep: bool) -> bool:
        """Keep the ring for a recording (a break the camera may continue: memory first) or let it be ordinary."""
        with self._lock:
            r = self.recs.get(str(cid))
        if r is None or r.keep == keep:
            return False
        r.keep = keep
        self.ring.set_keep(keep, (lambda frames, r=r: self._spilled(r, frames)) if keep else None)
        log.info("card: %s %s", cid, "keeps the ring" if keep else "lets the ring go by its window")
        return True

    # What only memory holds goes to the card before the recording stops: a KEPT ring is a break the server has not
    # taken (a restart in the middle of an outage must not lose it), and a writing recording's queue holds frames the
    # card has not had. A ring on hold and not kept is the pre-record: nothing of it is owed to the card.
    def _stop(self, cid: str) -> None:
        with self._lock:
            r = self.recs.pop(cid, None)
        if r is None:
            return
        if r.untap is not None:
            r.untap()
        with r.lock:
            r.stopped = True
            r.wake.notify()
        if r.thread is not None:
            r.thread.join(timeout=5.0)
        while r.spill:
            self._write(r, r.spill.popleft())
        if r.keep or not r.hold:
            # The queue's frames are in the ring too, unless the ring let them go already: those first, then the ring
            # — written in time order, so a released ring not drained yet is not skipped by newer live frames.
            ring = self.ring.after(r.last)
            first = ring[0].begin if ring else float("inf")
            for s in [s for s in r.live if s is _CUT or s.begin < first] + ring:
                self._write(r, s)
        r.live.clear()
        if r.keep:
            self.ring.set_keep(False)
        if self.card is not None:
            try:
                self.card.finish(r.stream)
            except OSError as e:
                log.warning("card: closing %s: %s", r.stream, e)

    def pump(self) -> tuple[list, list]:
        """(dead, posted): a recording the card refused a write of is dead, and stopped here; the recorder starts it
        again after its backoff (`VmsWorker.pump_once`)."""
        with self._lock:
            dead = [(cid, r.last_error) for cid, r in self.recs.items() if r.failed]
        for cid, why in dead:
            log.warning("card: %s: the card refused a write (%s) — the recording is restarted", cid, why)
            self._stop(cid)
        return [cid for cid, _ in dead], []

    def offered(self, cid):
        return None                                      # not measured: the card's write path has no engine to compare with

    def stop_all(self) -> None:
        for cid in list(self.recs):
            self._stop(cid)

    def stats(self, cid) -> dict:
        """The recording's state on the card, as its recorder's heartbeat says it."""
        out = {}
        if self.card is not None:
            segs, size, budget = self.card.stats()
            out = {"card_segments": segs, "card_bytes": size, "card_budget": budget}
        with self._lock:
            r = self.recs.get(str(cid))
        if r is None:
            return out
        out.update(hold=r.hold, keep=r.keep, samples_written=r.written, samples_dropped=r.dropped)
        if r.last_error:
            out["last_error"] = r.last_error
        return out


# -- the platform's recorder over the card ---------------------------------------------------------------------------
def declare_card(vars_, server: str, path: str, budget: int = CARD_BUDGET, name: str = "card", cam: str = "") -> volumes.Volume:
    """The card as the camera's own cluster declares it — `kind: edge`, `server` the camera's box, `cam` the camera's
    id among the cluster's cameras (an edge volume says whose card it is: `volumes.refuse`) — as the product's camera
    process does at its start: a place for placement and the gate, written by the card buffer, never by an engine."""
    return volumes.write(vars_, {"name": name, "kind": "edge", "server": server, "url": path, "quota_bytes": int(budget),
                                 "cam": str(cam)})


class CardRecorder(RecWorker):
    """`RecWorker` on a camera: the same slot, leases, gate and heartbeat; its volume is the camera's card — a
    `CardBuffer` — and its pipelines are `CardActuator`'s, over the camera's one ring. No engine anywhere."""

    COVERAGE_EVERY = 10.0                # how often the card's coverage is read for the heartbeat: a card fills in minutes
    CARD_RETRY = 30.0                    # a card that would not open is tried again: often mounted after the process starts

    def __init__(self, name, vars_, objects, ring: CamRing, actuator: CardActuator | None = None, **kw):
        kw.pop("obsd", None)
        self.ring = ring
        super().__init__(name, vars_, objects, actuator or CardActuator(ring), obsd=NO_ENGINE, **kw)
        self.PREBUFFER = ring.window                         # the ring IS the pre-record: its window, not a server's number
        self.card: CardBuffer | None = None
        self.card_error, self.card_tries, self.card_since = "", 0, self.wall()
        self.card_cam = ""                                   # the camera whose card this is (the held volume's `cam`)
        self.not_ours: dict[str, str] = {}                   # recordings placed here that are another camera's -> why not recorded
        self._card_retry_at = float("-inf")
        self._coverage: dict[str, tuple[float, list]] = {}

    # The source is the camera's own ring — not a fan-out found in somebody's heartbeat: nothing to re-subscribe to.
    def source(self, cam):
        return self.server, "ring://camera"

    # Started only with a card open. A camera whose card would not open records nothing on it — and is a camera all
    # the same: the ring and the pusher do not need the card; a break longer than the ring is then lost.
    #
    # …and only a recording of THIS camera (the review's sixth pass, major). The card's recorder writes its own ring
    # into whatever recording it is given: a recording of camera 1 homed on camera 2's card (`PUT … {"home":
    # "card2"}`) was camera 2's frames under camera 1's name, out of camera 2's budget. The row is refused at the
    # door now (`volumes.refuse_recording`); one that got here all the same — written before the rule, or past it —
    # is not recorded, and its status says why.
    def enrich(self, cam: dict) -> dict | None:
        mine = self.card_cam
        if mine and str(cam.get("cam") or "") != mine:
            self.waiting.add(cam["id"])
            self.not_ours[str(cam["id"])] = (f"this is the card in camera {mine}, and the recording is camera "
                                             f"{cam.get('cam')}'s: a card records its own camera")
            return None
        self.not_ours.pop(str(cam["id"]), None)
        if self.card is None:
            self.waiting.add(cam["id"])
            return None
        self.waiting.discard(cam["id"])
        self.sources[cam["id"]] = "ring://camera"
        out = dict(cam, source="ring://camera", source_server=self.server, via="ring")
        if self._offline_backup(cam):
            hold = not self.primary_needs_cover(cam)
            self.holding[str(cam["id"])] = hold
            out.update(hold=hold, ring_seconds=self.PREBUFFER, now=self.wall())
        return out

    # The card is a place like any other — a hold on `rec/volumes/<card>`, by CAS, so the console sees who serves it
    # — but only THIS camera's card, and opening it is a directory, not a daemon. A card that will not open costs the
    # recorder its capacity (not a place to put a recording), is said in `volume_error`, and is tried again every
    # `CARD_RETRY`: a card is often mounted after the camera's process starts, or put in later.
    def volume_pass(self) -> str:
        rows = {v.name: v for v in volumes.declared(self.vars)
                if v.kind == "edge" and v.enabled and v.server == self.server}
        held = self.hold
        if held is not None and (held not in rows or not self.renew_hold()):
            self.leave_volume(f"card {held} is not this camera's any more")
        if self.hold is None:
            if not rows or self.claim_hold(sorted(rows)) is None:
                self.volume, self.capacity = "", 0
                self.volume_error = "" if rows else "no card is declared for this camera"
                return self.volume
        vol = rows[self.hold]
        self.card_cam = vol.cam
        if self.card is None and self.clock() >= self._card_retry_at:
            self.card_tries += 1
            try:
                self.card = CardBuffer(vol.url, budget=vol.quota_bytes)
                self.actuator.card = self.card
                self.card_error, self.card_since = "", self.wall()
                log.info("%s: the card %s is open; the card records", self.name, vol.url)
            except OSError as e:
                if str(e) != self.card_error:
                    log.warning("%s: the card %s would not open: %s; going on without it (the ring and the pusher work; "
                                "a break longer than the ring is lost), trying again every %.0f s",
                                self.name, vol.url, e, self.CARD_RETRY)
                    self.card_since = self.wall()
                self.card_error, self._card_retry_at = str(e), self.clock() + self.CARD_RETRY
        self.volume = self.hold
        if self.card is not None:
            self.capacity, self.volume_error = self.full_capacity, ""
        else:
            self.capacity, self.volume_error = 0, f"the card would not open: {self.card_error}"
        return self.volume

    def _close_store(self, quiet: bool = False, wait: float | None = None) -> None:
        if self.card is not None:
            try:
                self.card.close()
            except OSError as e:
                if not quiet:
                    log.warning("%s: closing the card: %s", self.name, e)
        self.card = None
        self.actuator.card = None

    # What the card holds of a recording — read every `COVERAGE_EVERY`, not every heartbeat: the segments are a list in
    # memory, but a camera's heartbeat goes out every two seconds and the card changes in minutes.
    def our_coverage(self, unit) -> list[tuple[float, float]]:
        if self.card is None:
            return []
        at, spans = self._coverage.get(str(unit), (float("-inf"), []))
        if self.clock() - at >= self.COVERAGE_EVERY:
            spans = stitch(self.card.coverage(str(unit)), self.stitch)
            self._coverage[str(unit)] = (self.clock(), spans)
        return spans

    def status_extra(self, cam: dict) -> dict:
        out = super().status_extra(cam)
        out["via"] = "ring"
        out.update(self.actuator.stats(cam["id"]))
        if self.card is None and self.card_error and cam["id"] not in self.reconciler.actual:
            out["why"] = f"the card would not open: {self.card_error}"
        if str(cam["id"]) in self.not_ours:
            out["why"] = self.not_ours[str(cam["id"])]
        return out

    # What a camera's recorder says: its place, the card, and the camera's frames. None of the engine's fields — no
    # `archive` (nothing for a console to offer to declare), no quota of a ring, no writer watch, no door.
    def heartbeat_extra(self) -> dict:
        card = {"state": "recording" if self.card is not None else "unavailable" if self.card_error else "opening",
                "tries": self.card_tries, "since": self.card_since}
        if self.card is not None:
            segs, size, budget = self.card.stats()
            card.update(segments=segs, bytes=size, budget=budget)
        if self.card_error and self.card is None:
            card["error"] = self.card_error
        # `archive` empty: a worker's is its events tree, and under `rec/` the console reads it as the box's own volume
        # and offers to declare it (`volumes.suggest`) — a camera has no volume of the engine to offer.
        return {**VmsWorker.heartbeat_extra(self), "archive": "", "volume": self.volume,
                "volume_error": self.volume_error, "card": card, "feed": self.ring.status(self.wall())}

    # The camera's answer to a request for a range of its card (М12 Lesson 16: the server puts the range in the answer
    # to the camera's poll, the camera uploads it). A card that is not open, or a read cut short, is an ERROR — the
    # server's copy fails and its backfill asks again later — never an empty answer, which would say "not on the card".
    def answer_range(self, recording: str, t0: float, t1: float) -> list[Sample]:
        card = self.card
        if card is None:
            raise CardError(f"the card is not open{': ' + self.card_error if self.card_error else ''}")
        return card.range(str(recording), t0, t1)
