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
#                    the oldest segments deleted when it is spent; a range reader that hands a range over in PIECES
#                    of at most `PIECE_BYTES` and says an error out loud
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
# **The camera's memory is ONE budget, in bytes** (`MEMORY_BUDGET`, 40 MiB; the review's sixth pass). The ring, what
# waits for the card, and a piece of the card on its way to the server are all the same frames, and all of them are
# held by this one process: counted in frames, or not at all, the ring's 32 MiB came with 38 MiB of spilled groups
# and a 29 MiB answer to one range on top. `memory_split` cuts the budget three ways — `RING_BYTES`, `QUEUE_BYTES`
# (every recording's queue and spill together), and two pieces of `PIECE_BYTES` in flight — and nothing here holds
# frames outside those three.
#
# **The write path never waits for the card.** Frames reach the card off the ring's lock: the ring hands each to a
# bounded queue (`QUEUE_BYTES` for the whole card, `QUEUE_LEN` frames a recording), and the card is written from the
# queue. A card slower than the stream — a cheap card, a card wearing out — fills the queue, and then frames for the
# CARD are dropped up to the next key frame, counted (`samples_dropped`); the ring, the pusher and the firmware never
# slow down for it. A write the card refuses kills the recording (`pump`), the recorder closes the card and opens it
# again (`CardRecorder.volume_pass`), and the recording comes back where it stopped: from the last frame the card
# took, out of the ring. A card full is not an error: its oldest segments go.
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
# - `memory_split(budget)` — `(ring, queue, piece)`; `MEMORY_BUDGET`, `RING_BYTES`, `QUEUE_BYTES`, `PIECE_BYTES`.
# - `CamRing(window, max_bytes)` — `add(sample)`, `subscribe(fn)`, `set_keep(keep, spill, who)`, `after(t_ms)`,
#   `piece(t_ms, max_bytes)`, `reach()`, `status(now)`.
# - `CardBuffer(path, budget)` — `append(stream, sample)`, `finish(stream)`, `coverage(recording)`, `pieces(recording,
#   t0, t1, max_bytes)`, `range(recording, t0, t1)`, `stats()`, `err`, `close()`. Raises `CardError` (an `OSError`):
#   `NeedKey`, `Backwards`, `NoRecording`, a read cut short.
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
from .recworker import REC, RecWorker
from .worker import VmsWorker

log = logging.getLogger("card")

# THE CAMERA'S MEMORY (the review's sixth pass: "what is the camera's memory budget, and how is it split?"). The
# product's camera is a 32-bit SoC that leaves this process some 32 MB for its data, and every frame the process
# holds is in one of three places — so the three are cut out of ONE number, in bytes:
#
#     the ring          `RING_BYTES`       32 MiB   the last `RING_SECONDS`, as far as the bytes go: 60 s at 4 Mbit/s,
#                                                   44 s at 6, 33 s at 8. `CamRing.reach` says which, and the recorder
#                                                   raises an alarm when that is less than a break takes to be noticed
#     the card's queue  `QUEUE_BYTES`       6 MiB   every recording's frames on their way to the card and what a kept
#                                                   ring spilled, together: twelve seconds at 4 Mbit/s
#     pieces            2 × `PIECE_BYTES`   2 MiB   one piece the card's writer took out of the ring, and one piece of
#                                                   the card read for the server (a range's answer, a break continued)
#
# Until then only the ring had a ceiling in bytes: the queue was 512 frames, the spill 2048, and a range was answered
# as one list — 31.5 MiB of ring, 38.2 MiB spilled and 28.6 MiB of one answer at 4 Mbit/s. The ring is the product's:
# 32 MiB, sixty seconds (feedback CT, DE — to be confirmed by measuring on a camera; the owner chose the product's ring
# over a smaller one that would have kept the whole process inside 32). The queue and the pieces come ON TOP of it, in
# bytes, where the product counts its queue and spill in frames: 40 MiB in all, every byte of it counted. A camera
# measured to have less or more hands `memory_split` another budget, and the three shares move together.
RING_SECONDS = 60.0                      # the ring's WINDOW — the product's sixty seconds; what it holds is `reach()`
MEMORY_BUDGET = 40 << 20


def memory_split(budget: int = MEMORY_BUDGET) -> tuple[int, int, int]:
    """`(ring, queue, piece)` in bytes, out of one budget: three twentieths wait for the card, two pieces of a
    fortieth each are in flight, and the ring has the rest — four fifths: 32 MiB of 40, the product's ring."""
    queue, piece = budget * 3 // 20, budget // 40
    return budget - queue - 2 * piece, queue, piece


RING_BYTES, QUEUE_BYTES, PIECE_BYTES = memory_split()
QUEUE_LEN = 512                          # …and never more FRAMES than this waiting, per recording (the product's number)
SPILL_LEN = QUEUE_LEN * 4                # what a kept ring hands over past its ceiling: groups of pictures, in bursts
MEASURE_SPAN = 5.0                       # the ring's bitrate is measured over at least this much of it
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


class NoRecording(CardError):
    """The card holds nothing under the name it was asked for — or was asked for no name, and holds several."""


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
        # Who keeps the ring, and where each wants what it lets go of (`set_keep`). KEPT is "somebody does": a flag
        # for the whole ring was one recording's to clear for every other (the review's sixth pass).
        self._keepers: dict[str, object] = {}
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
        for spill in list(self._keepers.values()):
            if spill is not None:
                spill(group)
        del self._frames[:k]
        self.bytes -= sum(len(f.body) for f in group)

    # The oldest group goes while the rest still covers the window. A KEPT ring keeps everything: a break the server
    # has not taken is in it, and only the byte ceiling may make it let go — to the card.
    def _trim_window(self) -> None:
        window_ms = self.window * 1000.0
        while not self._keepers and window_ms > 0 and len(self._frames) > 1:
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

    def set_keep(self, keep: bool, spill=None, who: str = "") -> None:
        """`who` keeps the ring, or keeps it no longer. Kept — by anybody — nothing is let go by the window; past
        the byte ceiling the oldest groups go to the `spill(frames)` of everyone keeping, under the ring's lock — it
        must not wait. Ordinary again when the LAST keeper lets go: it shrinks to its window on the next sample."""
        with self._lock:
            if keep:
                self._keepers[str(who)] = spill
            else:
                self._keepers.pop(str(who), None)

    @property
    def kept(self) -> bool:
        return bool(self._keepers)

    def after(self, t_ms: int = 0) -> list[Sample]:
        """What the ring holds past `t_ms` (archive ms), from the first key frame after it — from its oldest key
        frame when it does not reach back that far; 0: all of it. ALL of it, as one list: for a reader that sends it
        on at once. The card's writer, which holds what it took while the card writes, takes `piece`."""
        with self._lock:
            for i, f in enumerate(self._frames):
                if (t_ms == 0 or f.begin > t_ms) and f.key:
                    return list(self._frames[i:])
            return []

    # The ring in PIECES (the review's sixth pass): what a reader takes out of the ring it HOLDS — in this process
    # the same frames, in the product copies of them out of the ring's arena — while the ring goes on and lets go of
    # them. One snapshot of a full ring is a second ring in memory for as long as the card takes to write it.
    #
    # A piece goes on from the frame the reader had last (`t_ms` is that frame's begin, and the ring still holds it):
    # in the middle of a group of pictures, if that is where the last piece ended. When the ring no longer holds that
    # frame, the piece starts at the next key frame and says so (`whole` False): what lay between is gone.
    # `caught_up()` is called under the ring's lock when there is nothing past `t_ms` at all — whoever subscribed is
    # told every frame from that moment, so a reader that takes pieces first and its subscription after loses none.
    def piece(self, t_ms: int, max_bytes: int, upto: int | None = None, caught_up=None) -> tuple[list[Sample], bool]:
        """`(frames, whole)`: the next frames past `t_ms`, at most `max_bytes` of them (one frame at least), none
        that begins after `upto`; `whole` — they follow the frame at `t_ms` with nothing missing between."""
        with self._lock:
            fs = self._frames
            i = next((k for k, f in enumerate(fs) if f.begin > t_ms), len(fs))
            whole = t_ms == 0 or (i > 0 and fs[i - 1].begin == t_ms)
            if not whole or t_ms == 0:
                i = next((k for k in range(i, len(fs)) if fs[k].key), len(fs))
            out, size = [], 0
            while i < len(fs) and (upto is None or fs[i].begin <= upto) and (not out or size + len(fs[i].body) <= max_bytes):
                out.append(fs[i])
                size += len(fs[i].body)
                i += 1
            if not out and caught_up is not None:
                caught_up()
            return out, whole

    def newest(self) -> int:
        """When the newest frame held began (archive ms); 0 when the ring is empty."""
        with self._lock:
            return self._frames[-1].begin if self._frames else 0

    # HOW FAR BACK THE RING REACHES (the review's sixth pass). The window is sixty seconds and the ceiling is bytes:
    # at 6 Mbit/s the ring holds thirty-three seconds, and the card's gate went on saying sixty — "recording from 60 s
    # ago" over a ring that began after the break did. What the ring CAN hold of this camera's stream is its ceiling
    # at the bitrate it is being given: measured over what it holds now, once that is `MEASURE_SPAN` of stream (a
    # key frame alone would measure as a hundred megabits), and never more than the window.
    def reach(self) -> float:
        """Seconds of this camera's stream the ring holds when it is full: the window, or less — its bytes at the
        bitrate of what it holds now."""
        with self._lock:
            if not self._frames or not self.bytes:
                return self.window
            span = (self._frames[-1].end - self._frames[0].begin) / 1000.0
            if span < min(MEASURE_SPAN, self.window):
                return self.window
            by_bytes = span * self.max_bytes / self.bytes
            return min(self.window, by_bytes) if self.window > 0 else by_bytes

    def status(self, now: float | None = None) -> dict:
        """What the camera's worker says about its frames: arriving or not, how long since the last, and the ring."""
        now = self.clock() if now is None else now
        reach = self.reach()
        with self._lock:
            span = (self._frames[-1].end - self._frames[0].begin) / 1000.0 if self._frames else 0.0
            out = {"frames_connected": self.connected, "ring_samples": len(self._frames), "ring_bytes": self.bytes,
                   "ring_span_s": round(span, 3), "ring_window_s": self.window, "ring_max_bytes": self.max_bytes,
                   "ring_reach_s": round(reach, 1)}
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
        # The segment being written, of each STREAM that is: `stream -> [segment, file, when it was last synced]`.
        self.open: dict[str, list] = {}
        self._f = None                                       # the file `_write` writes into: the appending stream's
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

    # One sample of `stream`. A new segment opens on a key frame — when none is open for the stream, or when the open
    # one is full; a delta frame with no segment open for its stream is refused.
    #
    # ONE OPEN SEGMENT A STREAM, NOT ONE A CARD (the review's sixth pass: two recordings on one card). The card had a
    # single open segment, as the product's `cardbuf` has: a sample of another stream closed it, and the first stream's
    # next delta frame was refused for want of a key frame. Two recordings that keep the same break and are released
    # together write at once — and each lost every group of pictures the other wrote a frame in. The price of a
    # second open segment is a file descriptor and a write buffer per recording that is writing.
    def append(self, stream: str, s: Sample) -> None:
        with self._lock:
            cur = self.open[stream][0] if stream in self.open else None
            if cur is not None and cur.bytes > 0 and s.begin <= cur.last_begin:
                raise Backwards(f"{stream}: {s.begin} is not after {cur.last_begin}")
            if cur is None or (s.key and self._full(cur, s)):
                if not s.key:
                    raise NeedKey(f"{stream}: a stream opens on a key frame")
                try:
                    cur = self._open(stream, s.begin)
                except OSError as e:
                    self.err = e
                    raise
            data, held = s.encode(), self.open[stream]
            try:
                self._f = held[1]
                self._write(data)
                if self.clock() - held[2] >= self.sync_every:
                    os.fsync(self._f.fileno())
                    held[2] = self.clock()
            except OSError as e:
                self.err = e
                raise
            cur.last, cur.last_begin, cur.bytes = s.end, s.begin, cur.bytes + len(data)
            if not cur.first:
                cur.first = s.begin
            self.bytes += len(data)
            self.err = None
            self._retain()

    # The one place bytes reach the card — a test replaces it to have the card fail.
    def _write(self, data: bytes) -> None:
        self._f.write(data)
        self._f.flush()

    def _full(self, cur: _Segment, s: Sample) -> bool:
        return cur.bytes >= self.segment_bytes or s.begin - cur.first >= self.segment_span * 1000

    def _open(self, stream: str, begin: int) -> _Segment:
        self._close_locked(stream)
        d = os.path.join(self.path, *stream.split("/"))
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{begin}.smpl")
        seg = _Segment(stream, path)
        self.open[stream] = [seg, open(path, "ab"), self.clock()]
        self.segs.append(seg)
        return seg

    def finish(self, stream: str) -> None:
        """Close the stream's open segment: its next sample opens a new one, on a key frame."""
        with self._lock:
            self._close_locked(stream)

    def close(self) -> None:
        with self._lock:
            failed = None
            for stream in list(self.open):
                try:
                    self._close_locked(stream)
                except OSError as e:                         # every segment is closed, whatever one of them said
                    failed = e
            if failed is not None:
                raise failed

    def _close_locked(self, stream: str) -> None:
        cur, f, _ = self.open.pop(stream, (None, None, 0.0))
        if f is self._f:
            self._f = None
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

    # The budget: the oldest closed segments go while the card is over it. An open one never does.
    def _retain(self) -> None:
        while self.bytes > self.budget:
            writing = {id(held[0]) for held in self.open.values()}
            old = next((seg for seg in self.segs if id(seg) not in writing), None)
            if old is None:
                return
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

    def recordings(self) -> list[str]:
        """The names of the recordings the card holds anything of."""
        with self._lock:
            return sorted({s.stream.rsplit("/", 1)[0] for s in self.segs if s.bytes > 0})

    # Every sample of `recording` that begins in `[t0, t1)` (unix seconds), in time order, each segment's from its
    # first key frame in the range on — handed over in PIECES of at most `max_bytes` (a frame larger than that goes
    # alone), read off the card as each is asked for. Nothing is held but the piece: ten minutes at 4 Mbit/s were
    # 272 MiB in one list, read into a camera that has 32 (the review's sixth pass, blocker 3). A piece may end in the
    # middle of a group of pictures; the pieces of one read go on in order, to one reader.
    #
    # WHICH recording is said by whoever asks (the review's sixth pass): the card holds as many as the camera has
    # rows homed on it, and a reader wired to one of them answered a request for another with nothing — "not on the
    # card", for good. A name the card holds nothing of is `NoRecording`, an error like any other here; no name is the
    # card's ONE recording, and an error when it holds several.
    #
    # An error is RAISED, never taken for the end: a camera answering a server's request for a range must not answer
    # with part of it as if it were all — the server would take the rest for "the card has none" and never ask
    # again. The end of a segment is the size the card wrote when the range began, so the record being written right
    # now is not read, and a segment shorter than that is an error.
    def pieces(self, recording: str | None, t0: float, t1: float, max_bytes: int = PIECE_BYTES):
        lo, hi = archive_ms(t0), archive_ms(t1)
        held = self.recordings()
        if recording is None:
            if len(held) != 1:
                raise NoRecording(f"the request names no recording, and the card holds {', '.join(held) or 'none'}")
            recording = held[0]
        if str(recording) not in held:
            raise NoRecording(f"no recording {recording} on this card (it holds {', '.join(held) or 'none'})")
        with self._lock:
            for held in self.open.values():
                held[1].flush()
            parts = [(s.path, s.bytes) for s in self.segs
                     if s.stream.startswith(f"{recording}/") and s.bytes > 0 and s.first < hi and s.last > lo]
        return self._pieces_of(parts, lo, hi, max(1, int(max_bytes)))

    def _pieces_of(self, parts: list, lo: int, hi: int, max_bytes: int):
        out, size = [], 0
        for path, written in parts:
            for smp in self._range_of(path, written, lo, hi):
                if out and size + len(smp.body) > max_bytes:
                    yield out
                    out, size = [], 0
                out.append(smp)
                size += len(smp.body)
        if out:
            yield out

    def range(self, recording: str | None, t0: float, t1: float) -> list[Sample]:
        """`pieces`, joined: the whole range as ONE list — for a reader with a server's memory, and the tests. A
        camera answers with the pieces."""
        return [smp for piece in self.pieces(recording, t0, t1) for smp in piece]

    @staticmethod
    def _range_of(path: str, size: int, lo: int, hi: int):
        try:
            f = open(path, "rb")
        except FileNotFoundError:
            return                                           # the budget took it after it was listed: no longer held
        except OSError as e:
            raise CardError(f"reading {path}: {e}") from None
        read, started = 0, False
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
                yield smp

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
        # The writer owes the card the RING: what it holds past `last`, a piece at a time, before anything live — after
        # a release, and after a restart of a recording that was writing. While it does, nothing is queued for it:
        # those frames are in the ring, and it takes them from there (`CardActuator._catch_up`).
        self.release_due = False
        self.resumed = False                             # …after a restart: what it skips up to its first key frame is lost
        self.fresh = False                               # …after a release: its first piece begins where the ring does — no loss
        self.unkeep_due = False                          # asked to let the ring go while it owed the card the ring
        self.cutting = False                             # the queue overflowed: frames dropped up to the next key frame
        # How far the writer has got: the begin (archive ms) of the last sample it DEALT WITH — on the card, or passed
        # over on the way to a key frame. What the card refused is not dealt with: the recording goes on from there.
        self.last = 0
        self.need_key = True
        self.written = self.dropped = self.lost_ms = 0
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

    def __init__(self, ring: CamRing, card: CardBuffer | None = None, threaded: bool = True,
                 queue_bytes: int = QUEUE_BYTES, piece_bytes: int = PIECE_BYTES):
        self.ring, self.card, self.threaded = ring, card, threaded
        self.recs: dict[str, _Rec] = {}
        self._lock = threading.Lock()
        self.calls: list[tuple[str, str]] = []
        # What waits for the card, in BYTES, every recording's queue and spill together (`QUEUE_BYTES` of the
        # camera's one budget): counted as it is queued, given back as the writer takes it.
        self.queue_bytes, self.piece_bytes, self.queued = int(queue_bytes), int(piece_bytes), 0
        self._qlock = threading.Lock()
        self.failures = 0                                # writes the card refused, since this process started
        # What a recording's writer knew when it stopped — `(last, written, dropped, lost_ms)` — for the one started after it.
        self.carried: dict[str, tuple[int, int, int, int]] = {}

    # A recording that records only without its primary starts ON HOLD; any other writes from its first key frame.
    # `release` takes it off hold; going back on hold is a restart under the same epoch (the gate's `_actuate`).
    #
    # WHERE IT STOPPED IS WHERE IT GOES ON (the review's sixth pass). A recording started again knew nothing of the
    # one before it: `last` was nought. So a primary that flapped — released, held again, released within the ring's
    # sixty seconds — had the same interval written to the card twice, in two segments; and a recording the card
    # refused a write of came back at the next live key frame, the seconds between the refusal and the restart on
    # the card nowhere while the ring still held them. `last` is carried — under the same epoch and under a new one:
    # the card's coverage is the recording's, whatever the epoch — and a recording that was WRITING goes on from it
    # out of the ring. A `last` ahead of the ring's newest frame is a clock that stepped back: forgotten.
    #
    # What a restart still costs is the rest of the group of pictures it stopped in: the stop closed the segment, and
    # a segment opens on a key frame. Those frames — less than a group — are counted (`samples_dropped`).
    def __call__(self, verb: str, cam: dict) -> bool:
        cid = str(cam["id"])
        self.calls.append((verb, cid))
        if verb in ("start", "restart"):
            if self.card is None:
                return False                             # no card open: nothing to write into, the reconciler retries
            self._stop(cid)
            r = _Rec(cid, f"{cid}/e{int(cam.get('epoch', 0))}", bool(cam.get("hold")))
            r.last, r.written, r.dropped, r.lost_ms = self.carried.get(cid, (0, 0, 0, 0))
            newest = self.ring.newest()
            if newest and r.last > newest:
                r.last = 0
            r.release_due = r.resumed = bool(r.last) and not r.hold
            r.untap = self.ring.subscribe(lambda s, r=r: self._offer(r, s))
            if r.release_due:
                self._owe(r)
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

    # Room in the card's queue for `size` bytes more — the whole card's queue, in bytes (`QUEUE_BYTES`): 512 frames of
    # a 4 Mbit/s stream were ten megabytes, of an 8 Mbit/s one twenty, and the spill four times that.
    def _room(self, size: int) -> bool:
        with self._qlock:
            if self.queued + size > self.queue_bytes:
                return False
            self.queued += size
            return True

    def _took(self, q: collections.deque):
        s = q.popleft()
        if s is not _CUT:
            with self._qlock:
                self.queued -= len(s.body)
        return s

    # Under the ring's lock: queue it or count it, never wait. On hold nothing is owed to the card — the ring is the
    # pre-record; and nothing is queued while the writer is taking the ring itself, or after the card refused a
    # write: those frames are in the ring, where the writer finds them. A full queue — its frames, or the card's bytes
    # — drops this frame and every frame after it up to the next key frame, so the card has a clean cut and never
    # half a group of pictures; the cut is marked, and the writer closes the segment there.
    def _offer(self, r: _Rec, s: Sample) -> None:
        with r.lock:
            if r.hold or r.stopped or r.release_due or r.failed:
                return
            if r.cutting and not s.key:
                r.dropped += 1
                return
            room = QUEUE_LEN - len(r.live)
            if room < (2 if r.cutting else 1) or not self._room(len(s.body)):
                r.dropped += 1
                r.cutting = True
                return
            if r.cutting:
                r.live.append(_CUT)
                r.cutting = False
            r.live.append(s)
            r.wake.notify()

    # What a kept ring let go of past its ceiling: whole groups of pictures, the oldest of a break and its only copy.
    # Out of the same bytes as the queue; a group there is no room for is lost to the card, counted, and marked.
    def _spilled(self, r: _Rec, frames: list) -> None:
        with r.lock:
            if len(r.spill) + len(frames) > SPILL_LEN or not self._room(sum(len(f.body) for f in frames)):
                r.dropped += len(frames)
                if not r.spill or r.spill[-1] is not _CUT:
                    r.spill.append(_CUT)
            else:
                r.spill.extend(frames)
            r.wake.notify()

    def _run(self, r: _Rec) -> None:
        while True:
            with r.lock:
                while not r.stopped and (r.failed or self.card is None or not (r.live or r.spill or r.release_due)):
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

    # The writer: first what a kept ring spilled (the oldest of a break), then — while it owes the card the ring —
    # what the ring holds that the card has not had, then live. A frame that came both ways is written once (`_write`).
    def _drain(self, r: _Rec) -> None:
        while True:
            with r.lock:
                if r.failed or r.stopped or self.card is None:
                    return                               # refused a write, or stopping: what is left is `_stop`'s to write
                if r.spill:
                    s = self._took(r.spill)
                elif r.release_due:
                    s = None
                elif r.live:
                    s = self._took(r.live)
                else:
                    return
            if s is None:
                self._catch_up(r)
            else:
                self._write(r, s)

    # THE RING, A PIECE AT A TIME (the review's sixth pass). One piece of at most `PIECE_BYTES` is taken and written,
    # then the next — never the whole ring as one list, which the writer held while the ring went on behind it. What
    # the ring spilled is older than the piece, and is written before it: a kept ring lets go of nothing any other
    # way, so the piece follows what was spilled with no seam. A piece that follows neither the last frame dealt with
    # nor a spill is a hole — the ring, not kept, let go of what lay between before the card got to it: a card slower
    # than the stream, or one that was away longer than the ring reaches. It is closed as a hole (`_CUT`: a hole on the
    # card is a hole in its coverage) and its length is counted (`seconds_lost`).
    #
    # WHEN THE RING IS DONE, under the ring's lock (`caught_up`): from that moment every frame is queued, so none falls
    # between the last piece and the first queued frame. And only THEN is the ring let go, if somebody asked (`keep`)
    # while it was still owed: let go at the release, the next frame trimmed the ring to its window before the writer
    # had taken any of it — a break of a hundred seconds, kept whole in memory, reached the card as its last sixty.
    #
    # Returns whether it got anywhere: False when the ring has nothing more, and when the card took nothing of the
    # piece (it refused, or is closed) — asked again from the same place, it would be the same piece for ever.
    def _catch_up(self, r: _Rec, upto: int | None = None) -> bool:
        def done():
            with r.lock:
                r.release_due = False
        at = r.last
        piece, whole = self.ring.piece(at, self.piece_bytes, upto=upto, caught_up=done)
        with r.lock:
            spilled = [self._took(r.spill) for _ in range(len(r.spill))]
        for s in spilled:
            self._write(r, s)
        if not whole and r.last == at:
            if piece and at and not r.fresh:
                r.lost_ms += piece[0].begin - at
                if not r.need_key:
                    self._write(r, _CUT)
            r.need_key = True
        for s in piece:
            self._write(r, s)
        r.fresh = False
        if not piece:
            with r.lock:
                unkeep, r.unkeep_due = r.unkeep_due, False
            if unkeep:
                self._unkeep(r)
        return r.last > at

    # One sample onto the card, in order, from a key frame. A write the card refuses marks the recording dead for
    # `pump` — counted, and nothing more is offered to a card that is failing; a delta frame the card cannot open a
    # segment with waits for the next key frame.
    def _write(self, r: _Rec, s) -> None:
        if s is _CUT:
            r.need_key = True
            if self.card is not None:
                try:
                    self.card.finish(r.stream)           # a hole on the card is a hole in its coverage, not a seam
                except OSError as e:
                    self._refused(r, e)
            return
        if s.begin <= r.last or r.failed or self.card is None:
            return
        if r.need_key and not s.key:
            r.last = s.begin                             # passed over: it could not be read without its key frame
            if r.resumed:
                r.dropped += 1                           # …the rest of the group it was stopped in: not on the card
            return
        try:
            self.card.append(r.stream, s)
        except NeedKey:
            r.last, r.need_key = s.begin, True
            return
        except Backwards:
            r.last = s.begin
            return
        except OSError as e:
            self._refused(r, e)
            return
        r.last, r.need_key, r.last_error, r.resumed = s.begin, False, "", False
        r.written += 1

    def _refused(self, r: _Rec, e: OSError) -> None:
        r.last_error, r.need_key, r.failed = str(e), True, True
        self.failures += 1

    def hold(self, cid, hold: bool) -> bool:
        """On hold (True) or released (False). False when it is not running here, or already so."""
        with self._lock:
            r = self.recs.get(str(cid))
        if r is None:
            return False
        with r.lock:
            if r.hold == hold:
                return False
        if not hold:
            self._owe(r)
        with r.lock:
            r.hold = hold
            r.release_due = r.fresh = not hold
            r.need_key = True
            r.wake.notify()
        if hold and self.card is not None:
            self.card.finish(r.stream)
        log.info("card: %s %s", cid, "on hold: the ring is the pre-record" if hold else "released: the card writes")
        return True

    # THE RING IS KEPT BY A RECORDING, NOT FOR THE CARD (the review's sixth pass). `keep` was one flag on the ring, set
    # and cleared by whichever recording spoke last: two recordings on a card kept the same break, the second let go,
    # and the first lost ten seconds of it to the window. Each recording keeps under its own name (`CamRing.set_keep`,
    # `who`), is given what the ring lets go of, and the ring is ordinary again when the last of them lets go.
    #
    # And a recording that still owes the card the ring is not let go of at once: the gate releases and lets go in
    # the same pass, the writer takes the ring a moment later, and in between the next frame trimmed the ring to its
    # window. The request is remembered (`unkeep_due`) and done by the writer, when it has taken the ring (`_catch_up`).
    def keep(self, cid, keep: bool) -> bool:
        """Keep the ring for a recording (a break the camera may continue: memory first) or let it be ordinary."""
        with self._lock:
            r = self.recs.get(str(cid))
        if r is None:
            return False
        with r.lock:
            if keep:
                r.unkeep_due = False
            if r.keep == keep:
                return False
            if not keep and r.release_due:
                r.unkeep_due = True
                return True
            r.keep = keep
        if keep:
            self.ring.set_keep(True, lambda frames, r=r: self._spilled(r, frames), who=r.id)
            log.info("card: %s keeps the ring", cid)
        else:
            self._unkeep(r)
        return True

    # WHILE THE WRITER OWES THE CARD THE RING, THE RING IS KEPT FOR IT — whoever asked or did not. The frames that
    # arrive meanwhile are not queued (they are in the ring), so the ring must not let go of them by its window before
    # the writer gets there: a card slower than the stream would lose, uncounted, what the old snapshot at least held.
    # Kept, the ring lets go only past its bytes, and that goes to the spill — out of the queue's budget, and counted
    # when there is no room. Let go when the writer has caught up, unless the gate keeps the ring for a break.
    def _owe(self, r: _Rec) -> None:
        with r.lock:
            if r.keep:
                return
            r.keep = r.unkeep_due = True
        self.ring.set_keep(True, lambda frames, r=r: self._spilled(r, frames), who=r.id)

    def _unkeep(self, r: _Rec) -> None:
        r.keep = False
        self.ring.set_keep(False, who=r.id)
        log.info("card: %s lets the ring go by its window", r.id)

    # What only memory holds goes to the card before the recording stops: a KEPT ring is a break the server has not
    # taken (a restart in the middle of an outage must not lose it), and a writing recording's queue holds frames the
    # card has not had. A ring on hold and not kept is the pre-record: nothing of it is owed to the card. The queue
    # first — it is older than anything the ring is still owed for — then the ring, a piece at a time, up to the frame
    # that was its newest when the stop began. A recording the card refused a write of writes nothing here: the card
    # is failing, and the one started after it takes the ring from where this one stopped (`carried`).
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
        self._flush(r)
        upto = self.ring.newest()
        while (r.keep or not r.hold) and not r.failed and self._catch_up(r, upto):
            pass
        if r.keep:
            self._unkeep(r)
        self._flush(r)                                   # what a kept ring spilled while this was going on
        self.carried[cid] = (r.last, r.written, r.dropped, r.lost_ms)
        if self.card is not None:
            try:
                self.card.finish(r.stream)
            except OSError as e:
                log.warning("card: closing %s: %s", r.stream, e)

    # Everything queued, written — the spill, then live — and its bytes given back to the queue's budget, written or not.
    def _flush(self, r: _Rec) -> None:
        with r.lock:
            queued = [self._took(q) for q in (r.spill, r.live) for _ in range(len(q))]
        for s in queued:
            self._write(r, s)

    def pump(self) -> tuple[list, list]:
        """(dead, posted): a recording the card refused a write of is dead, and stopped here; the recorder starts it
        again after its backoff (`VmsWorker.pump_once`), from the last frame the card took."""
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
        if self.failures:
            out["card_failures"] = self.failures
        with self._lock:
            r = self.recs.get(str(cid))
        if r is None:
            return out
        out.update(hold=r.hold, keep=r.keep, samples_written=r.written, samples_dropped=r.dropped)
        if r.lost_ms:
            out["seconds_lost"] = round(r.lost_ms / 1000.0, 1)   # what the ring let go of before the card had it
        if r.last_error:
            out["last_error"] = r.last_error
        return out


# -- the platform's recorder over the card ---------------------------------------------------------------------------
def declare_card(vars_, server: str, path: str, budget: int = CARD_BUDGET, name: str = "card") -> volumes.Volume:
    """The card as the camera's own cluster declares it — `kind: edge`, `server` the camera — as the product's camera
    process does at its start: a place for placement and the gate, written by the card buffer, never by an engine."""
    return volumes.write(vars_, {"name": name, "kind": "edge", "server": server, "url": path, "quota_bytes": int(budget)})


class CardRecorder(RecWorker):
    """`RecWorker` on a camera: the same slot, leases, gate and heartbeat; its volume is the camera's card — a
    `CardBuffer` — and its pipelines are `CardActuator`'s, over the camera's one ring. No engine anywhere."""

    COVERAGE_EVERY = 10.0                # how often the card's coverage is read for the heartbeat: a card fills in minutes
    CARD_RETRY = 30.0                    # a card that would not open is tried again: often mounted after the process starts
    PREBUFFER_AGAIN = 86400.0            # `card.prebuffer.short` is raised when it begins, and once a day while it lasts

    def __init__(self, name, vars_, objects, ring: CamRing, actuator: CardActuator | None = None, **kw):
        kw.pop("obsd", None)
        self.ring = ring
        super().__init__(name, vars_, objects, actuator or CardActuator(ring), obsd=NO_ENGINE, **kw)
        self.card: CardBuffer | None = None
        # `card_fault`: what the card did — "would not open", "refused a write" — and `card_error`, the error it gave.
        self.card_fault, self.card_error, self.card_tries, self.card_since = "would not open", "", 0, self.wall()
        self.card_failures = 0                               # times the card was closed for refusing a write
        self._card_retry_at = float("-inf")
        self._coverage: dict[str, tuple[float, list]] = {}
        self.prebuffer_short: dict[str, float] = {}          # recording -> when `card.prebuffer.short` was last raised

    # THE PRE-RECORD IS WHAT THE RING HOLDS, NOT ITS WINDOW (the review's sixth pass: "30 or 60?"). Sixty seconds is the
    # ring's window, the product's and the server's `PREBUFFER`; what a camera's ring holds is that or its bytes,
    # whichever is less — 60 s at 4 Mbit/s, 44 at 6, 33 at 8 (`CamRing.reach`). Everything that counts on the
    # pre-record counts on THIS number: how long the gate may wait for a pushed stream to come back (`defer_for`), what
    # a standby says it holds, and whether it is enough (`prebuffer_pass`).
    @property
    def PREBUFFER(self) -> float:
        return self.ring.reach()

    def prebuffered(self, uid=None) -> float:
        """What the ring holds NOW, in seconds: what a release writes first, and what the log says of it."""
        return self.ring.status()["ring_span_s"]

    # How far back the ring must reach for a break to be on the card from its start: as late as the break is noticed,
    # and a key frame and a pass more. A camera whose stream says it (it pushes: М12's `edge_gate`) notices within
    # `DETECTION`, and the ring is kept from then on; one that learns from the book — its agent's, or the heartbeats
    # of its own cluster — notices only when the primary's last word has gone stale: `LOST_AFTER`.
    def detection(self, row: dict) -> float:
        by_stream = self.stream_says is not None and self.stream_says(row) is not None
        return (self.DETECTION if by_stream else self.LOST_AFTER) + self.DEFER_MARGIN

    # A RING SHORTER THAN THE DETECTION IS AN ALARM (the review's sixth pass). At 6 Mbit/s the ring held 44 s, at 8 —
    # 32; the primary's death is noticed after 45; and the log said "recording from 60 s ago" all the same. The start
    # of the break — the one thing the ring is kept for — was on the card at no ordinary bitrate above four megabits,
    # and nothing said so. Now it is said: in the recording's status (`prebuffer_s`, `prebuffer_short`), in the log,
    # and as the alarm `card.prebuffer.short`, when it begins and once a day while it lasts. The cure is the
    # camera's: a lower bitrate, or more memory for the ring (`memory_split`).
    def prebuffer_pass(self, now: float | None = None) -> dict:
        from w2cplatform.events import ALARM, EventLog
        now, reach, short = self.wall() if now is None else now, self.ring.reach(), {}
        for row in self.rows:
            uid = str(row["id"])
            if not self._offline_backup(row) or uid not in {str(u) for u in self.reconciler.actual}:
                self.prebuffer_short.pop(uid, None)
                continue
            need = self.detection(row)
            if reach >= need:
                self.prebuffer_short.pop(uid, None)
                continue
            short[uid] = need
            if now - self.prebuffer_short.get(uid, -1e18) < self.PREBUFFER_AGAIN or uid not in self.epochs:
                continue
            self.prebuffer_short[uid] = now
            st = self.ring.status(now)
            EventLog(self.archive_root, REC.name, uid, self.epochs[uid]).append(
                now, "card.prebuffer.short", cls=ALARM, cam=row.get("cam"), reach_s=round(reach, 1), need_s=need,
                ring_bytes=st["ring_max_bytes"], window_s=st["ring_window_s"])
            log.warning("%s: the ring holds %.0f s of %s and a break is noticed after %.0f: its start will not be on the "
                        "card (the ring is %d MiB — a lower bitrate, or more memory)", self.name, reach, uid, need,
                        st["ring_max_bytes"] >> 20)
        return short

    def gate_pass(self, now: float | None = None) -> list[tuple[str, str]]:
        done = super().gate_pass(now)
        self.prebuffer_pass(now)
        return done

    # The source is the camera's own ring — not a fan-out found in somebody's heartbeat: nothing to re-subscribe to.
    def source(self, cam):
        return self.server, "ring://camera"

    # Started only with a card open. A camera whose card would not open records nothing on it — and is a camera all
    # the same: the ring and the pusher do not need the card; a break longer than the ring is then lost.
    def enrich(self, cam: dict) -> dict | None:
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
        self._card_failing(vol)
        if self.card is None and self.clock() >= self._card_retry_at:
            self.card_tries += 1
            try:
                self.card = CardBuffer(vol.url, budget=vol.quota_bytes)
                self.actuator.card = self.card
                self.card_fault, self.card_error, self.card_since = "would not open", "", self.wall()
                # Its recordings waited for a card, not for a backoff: the ring holds the seconds since the card went
                # for only so long, and a start put off by what failed while there was no card would outlast it.
                for uid in list(self.reconciler.failures):
                    if uid not in self.reconciler.actual:
                        self.reconciler.failures.pop(uid, None)
                log.info("%s: the card %s is open; the card records", self.name, vol.url)
            except OSError as e:
                if str(e) != self.card_error or self.card_fault != "would not open":
                    log.warning("%s: the card %s would not open: %s; going on without it (the ring and the pusher work; "
                                "a break longer than the ring is lost), trying again every %.0f s",
                                self.name, vol.url, e, self.CARD_RETRY)
                    self.card_since = self.wall()
                self.card_fault, self.card_error = "would not open", str(e)
                self._card_retry_at = self.clock() + self.CARD_RETRY
        self.volume = self.hold
        if self.card is not None:
            self.capacity, self.volume_error = self.full_capacity, ""
        else:
            self.capacity, self.volume_error = 0, f"the card {self.card_fault}: {self.card_error}"
        return self.volume

    # A CARD THAT REFUSES WRITES IS NOT "RECORDING" (the review's sixth pass). A card gone read-only — the kernel does
    # it to a card that returned an error — refused every write, and nothing here knew: the recording was declared
    # dead and started again, seven times, on a card nobody had opened again, while the heartbeat said
    # `state: recording` and `volume_error` was empty. The card's own word (`CardBuffer.err`: the last write failed,
    # and none succeeded since) is read here, every pass. A failing card is CLOSED — said as `unavailable`, with what
    # it refused, in the heartbeat and in `volume_error`; the recorder's capacity is nought, so nothing is started
    # into it — and opened again after `CARD_RETRY`, the way a card that would not open is: opening reads it, so a
    # card that came back is found whole, and one that did not says why. Every recording on it is stopped — one that
    # has not been refused yet would go on handing frames to a card that is not there — and comes back from the last
    # frame the card took (`CardActuator.carried`), out of the ring, as far as the ring still reaches.
    def _card_failing(self, vol) -> None:
        err = self.card.err if self.card is not None else None
        if err is None:
            return
        self.card_failures += 1
        log.warning("%s: the card %s refused a write: %s; closing it, trying again in %.0f s (the ring and the pusher "
                    "work; what the ring lets go of meanwhile is lost to the card)", self.name, vol.url, err, self.CARD_RETRY)
        for uid in list(self.reconciler.actual):
            self.actuator("stop", {"id": uid})
            self.reconciler.lost(uid, self.now())
        self._close_store(quiet=True)
        self.card_fault, self.card_error, self.card_since = "refused a write", str(err), self.wall()
        self._card_retry_at = self.clock() + self.CARD_RETRY

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
            out["why"] = f"the card {self.card_fault}: {self.card_error}"
        if self._offline_backup(cam):
            out["prebuffer_s"] = round(self.ring.reach(), 1)
            if str(cam["id"]) in self.prebuffer_short:
                out["prebuffer_short"] = self.detection(cam)   # …and a break is noticed only after this many seconds
        return out

    # What a camera's recorder says: its place, the card, and the camera's frames. None of the engine's fields — no
    # `archive` (nothing for a console to offer to declare), no quota of a ring, no writer watch, no door. The card's
    # state is the card's own word: `failing` while its last write was refused and it is still open (until the next
    # pass closes it), `unavailable` with what it did — would not open, refused a write — while it is closed.
    def heartbeat_extra(self) -> dict:
        failing = self.card.err if self.card is not None else None
        card = {"state": "failing" if failing is not None else "recording" if self.card is not None else
                         "unavailable" if self.card_error else "opening",
                "tries": self.card_tries, "since": self.card_since}
        if self.card is not None:
            segs, size, budget = self.card.stats()
            card.update(segments=segs, bytes=size, budget=budget)
        if failing is not None:
            card["error"] = f"refused a write: {failing}"
        if self.card_error and self.card is None:
            card["error"] = self.card_error if self.card_fault == "would not open" else f"{self.card_fault}: {self.card_error}"
        if getattr(self.actuator, "failures", 0):
            card["failures"] = self.actuator.failures        # writes the card refused, since this process started
        # `archive` empty: a worker's is its events tree, and under `rec/` the console reads it as the box's own volume
        # and offers to declare it (`volumes.suggest`) — a camera has no volume of the engine to offer.
        return {**VmsWorker.heartbeat_extra(self), "archive": "", "volume": self.volume,
                "volume_error": self.volume_error, "card": card, "feed": self.ring.status(self.wall())}

    # The camera's answer to a request for a range of its card (М12 Lesson 16: the server puts the range in the answer
    # to the camera's poll, the camera uploads it). A card that is not open, or a read cut short, is an ERROR — the
    # server's copy fails and its backfill asks again later — never an empty answer, which would say "not on the card".
    #
    # THE ANSWER COMES IN PIECES, AND IT IS OF THE RECORDING THAT WAS ASKED FOR (the review's sixth pass). This is the
    # card's reader for the camera's pusher (`CameraPusher(card=recorder.answer_range)`): an iterator of lists of
    # `Sample`, each at most `max_bytes` — a minute at 4 Mbit/s was 28.6 MiB in one list. `recording` is the request's:
    # a name this camera has no recording of is an error (`NoRecording`), not an empty answer; a recording of this
    # camera the card holds nothing of YET is the one empty answer that is true; no name is this camera's one
    # recording on the card, and an error when it has several.
    def answer_range(self, recording: str | None, t0: float, t1: float, max_bytes: int = PIECE_BYTES):
        card = self.card
        if card is None:
            raise CardError(f"the card is not open{': ' + self.card_error if self.card_error else ''}")
        mine = sorted(str(r["id"]) for r in self.rows)
        if recording is None and len(mine) == 1:
            recording = mine[0]
        try:
            return card.pieces(None if recording is None else str(recording), t0, t1, max_bytes)
        except NoRecording:
            if recording is None or str(recording) not in mine:
                raise
            return iter(())
