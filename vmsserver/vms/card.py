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
# (every recording's queue and spill together), and two pieces of `PIECE_BYTES` in flight — and nothing in the camera's
# process holds frames outside those three: not this file, and not the camera's pusher (М12 `CameraPusher`, given the
# ring, keeps no frame of its own — the seventh review). One frame more is in hand where a record is written or read.
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
# - `CamLine(clock, steady, boot=…)` — the camera's line of time: `place(begin, end)`, `now()`, `skew()`; `note()` and
#   `restore(note, newest)` — kept on the card, taken back by the next process; `moves` — what of it was relabelled.
# - `CamRing(window, max_bytes, clock, steady)` — `add(sample)`, `subscribe(fn)`, `set_keep(keep, spill, who)`,
#   `after(t_ms)`, `piece(t_ms, max_bytes)`, `reach()`, `now()`, `skew()`, `status(now)`; `on_move(fn)`, `moves()`,
#   `note()`, `restore(note, newest)` — its line's.
# - `CardBuffer.read_note(name)`, `write_note(name, data)` — a small file beside the segments (what the server has,
#   `delivered.json`; the camera's line, `LINE_NOTE`).
# - `CardBuffer(path, budget)` — `append(stream, sample)`, `finish(stream)`, `coverage(recording)`, `pieces(recording,
#   t0, t1, max_bytes)`, `range(recording, t0, t1)`, `newest()`, `relabel(lo, hi, delta)`, `stats()`, `err`, `close()`.
#   Raises `CardError` (an `OSError`): `NeedKey`, `Backwards`, `NoRecording`, a read cut short.
# - `CardActuator(ring, card)` — the recorder's actuator: `(verb, cam)`, `keep(cid, on)`, `pump()`, `drain()`, `stats(cid)`;
#   `card` — attached, it restores the ring's line from the card; `note_line()` — the line kept on the card.
# - `CardRecorder(name, vars_, objects, ring, ...)` — a `RecWorker` whose volume is the card; `answer_range`.
# - `declare_card(vars_, server, path, budget, cam=…)` — the card as the camera's own cluster declares it (`kind: edge`,
#   `cam`: whose card it is — only that camera's recordings are homed on it).
# ================================================================================================
from __future__ import annotations

import collections
import contextlib
import dataclasses
import json
import logging
import os
import threading
import time

from w2cplatform.obsd import SMPL, Sample, archive_ms, unix_s
from w2cplatform.rows import PARSE_ERRORS, finite, number

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
#     the pusher        nothing of its own          М12's `CameraPusher(ring=…)` reads THIS ring: what it sent and may
#                                                   not have been written, a break, the frames before an event are the
#                                                   ring's frames, and the pusher keeps only where the stream stands. Of
#                                                   the card it holds one piece at a time — the "pieces" row: a range's
#                                                   piece not acknowledged is sent again before anything else is read
#                                                   off the card, and a read left open between passes holds no piece
#
# THE PUSHER'S ROW IS NEW (the seventh review: "the pusher keeps frames outside the budget, and counts them in seconds").
# It kept `tail` and `ring` lists of its own — the same frames the ring holds, half a minute each: 14.8 MiB at
# 4 Mbit/s, 29.6 at 8, some 70 MiB in a camera that says 40. They are gone, and the whole camera is measured: the
# ring, the card's writer and queue, the card and the pusher through a break of a minute and its continuation at
# 10 Mbit/s, under `tracemalloc`: a peak of 33.7 MiB (М12 Lesson 16, `test_lesson16_card.py`, the whole camera's test).
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
RING_AHEAD = 10.0                        # a frame later than the one before AND the camera's clock by more: no capture time (`_timed`)
CLOCK_JUMP = 0.1                         # the camera's clock moved this much more than its steady clock between two looks: a step (`CamLine`)
CARD_BUDGET = 1 << 30                    # the card's budget when the declaration names none
SEGMENT_BYTES = 16 << 20                 # a segment closes at the first key frame past this…
SEGMENT_SPAN = 300.0                     # …or past five minutes of footage
SYNC_EVERY = 5.0                         # how often what is written is forced onto the card
STALL_AFTER = 10.0                       # a write to the card that has not returned for this long: the card is stalled…
STALL_FLOOR = 1 << 20                    # …and a second more for every MiB it moves: the slowest a healthy card writes


class CardError(OSError):
    """The card refused, or could not give back, what it was asked for."""


class NeedKey(CardError):
    """A delta frame with no segment of its stream open: it could not be read without the key frame before it."""


class Backwards(CardError):
    """A sample older than the last one of its stream: a stream only goes forward, across its segments too."""


class NoRecording(CardError):
    """The card holds nothing under the name it was asked for — or was asked for no name, and holds several."""


class Stalled(CardError):
    """The card's I/O in progress has not returned for `CardBuffer.stall_after`: the card does not answer, and nothing
    else is put behind that I/O."""


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


# -- the camera's line of time ---------------------------------------------------------------------------------------
# ONE LINE OF TIME FOR EVERY READER OF THE CAMERA'S FRAMES (the ninth review, blocker). A frame carries the time it was
# captured, on the camera's clock — and that clock steps: NTP after a boot with a fast RTC, a hand that sets it. Every
# reader of the frames stands on a frame's time: the pusher's `sent` and cursor, the card's writer's `last`, the card's
# own "a stream only goes forward"; and the ingest puts every frame on the cluster's clock by ONE offset, the cluster's
# clock minus the camera's as the camera states it (М12 `Ingest._check`). The clock stepped back thirty seconds, the
# frames after it were "not newer" than where each reader stood, and each passed them over: thirty seconds on the card
# nowhere and at the recorder nowhere (reproduced: −5 s lost 5.0 s, −30 s lost 30.0). So the camera keeps a line that
# only goes forward, puts every frame on it once, before anybody reads it, and states its clock on it (`now`).
#
# …AND A STEP FORWARD IS TAKEN UP AS A STEP BACK IS (the tenth review, blocker). A clock that stepped forward J was left
# to the frames: they followed it, the line had a gap of J "as a pause has", and the camera stated its clock J later —
# the ingest's offset moved by J. Live frames landed where they were captured; nothing else did. A break across the step:
# the recorder's `have`, moved onto the camera's clock by the NEW offset, stood J past what the recorder had, and the
# camera went on from there — a break of 30 s and a step of +30 at its end, 30.2 s on no copy and nothing counted. And
# backfill's ranges, moved by the new offset, read the card J late: a hole asked for at [20, 50] was answered with what
# was captured at [20 + J, 50 + J], laid into the archive at [20, 50] — the wrong pictures at the wrong time, and the
# hole itself never asked for. Every one of them needs ONE offset for the whole line, so the line must not jump.
#
# A step forward is told from a pause by the camera's STEADY clock (`steady`: `time.monotonic` on a camera, which no hand
# and no NTP step moves). Between two looks (`look`: every frame, every time the camera's time is asked) the camera's
# clock moves as the steady one does; when it moved further by more than `CLOCK_JUMP`, the clock stepped — forward or
# back — and the step is DUE: the line takes it up from the first frame captured on the stepped clock (`_carries`) —
# the frame whose distance from the one before is the frames' interval plus the step; the frames still on their way,
# captured before the step, lie where they lay. A pause moves both clocks alike, and the line has the gap it should.
# A step back is taken up the same way, and — without a steady clock, or when the frames show it first — by the frames'
# own order, as the ninth review left it: a frame not later than the one before. The steps are counted both ways
# (`back`, `forward`, and by how much), logged, and said.
#
# A frame LATER than both the frame before it and the camera's own clock by more than `RING_AHEAD` has no capture time
# at all (the ninth review's sibling: one frame of t = 1e300 at the ingest silenced the camera for good): on the line it
# would leave every frame after it "not newer". It is kept — it is the camera's own frame, and the group after it needs
# it — right after the frame before, and counted (`ahead`); the line does not move for it, and the clock did not step.
#
# THE LINE OUTLIVES THE CAMERA'S PROCESS (the eleventh review, blocker 1). It lived in memory: a step of J was taken up,
# the card was written on the line — and a process started again began a line of its own, equal to the raw clock. The
# ingest saw its offset move by J, and backfill's ranges, moved by the new offset, read the card J away from the hole
# (probe `pr1_restart_line`: J = +30 — the frames of 50–80 s laid at 20–50; J = −30 — those of 0–20 s at 30–50). So the
# line is kept on the card, a note beside the segments (`LINE_NOTE`), written by the card's writer whenever the line
# moves — before the first frame on the moved line — and every `NOTE_EVERY` (`CardActuator.note_line`): where the line
# stood (`line`), on which camera clock (`raw`) and steady clock (`steady`), in which boot (`boot`). The next process takes
# it back before its frames go anywhere (`restore`, when the card is attached). In the same boot — the steady clock is one
# for every process of a boot — the line goes on from where it stood by the steady clock, whatever the camera's clock did
# meanwhile; a clock that disagrees with it stepped while no process watched, and that step is counted as any other. In a
# new boot nothing measures the time between: the line goes on by the camera's clock through the conversion the note
# kept (`line − raw`), and never back over what the card holds — a clock behind it stepped back, counted, and the frames
# go on right after the card's newest.
#
# A CLOCK NOT YET SET DOES NOT ANCHOR THE LINE (the eleventh review, blocker 2, a regression of the tenth's step forward).
# A camera without an RTC battery boots in 1970, and NTP sets its clock seconds later — a step forward of fifty-six years,
# which the line took up like any other: the line stayed in 1970 for the life of the process, a reboot began it in 1970
# again, the two boots overlapped on the card, and the first boot's hole was never asked for where the card held it
# (probe `pr6_rtcless`: 0 frames of 305; of a hole after the reboot, 5 of 10 frames the first boot's, 300 s off). A step
# forward of more than `CLOCK_UNSET` out of a clock before `CLOCK_FLOOR` is the clock being SET, not stepping: the line is
# RE-ANCHORED on the set clock — through the conversion the card's note kept (`anchor`), or none — and everything placed
# while the clock was unset (from `since`) is relabelled by the same amount: the ring's frames, the card's writer's queue
# and place and the segments it wrote (`CardBuffer.relabel`), the pusher's place (`CameraPusher._follow`). A reboot whose
# clock is unset again (behind the card's newest by more than `CLOCK_UNSET`) goes on right after the card's newest until
# the clock is set — so two boots never overlap on the card, and with a conversion the card kept the second lands where
# it was captured. A clock set BEHIND what the line holds cannot be followed back: the line stays where it is (`sets`).
# A camera whose clock is never set goes on from boot to boot right after the card's newest — boots apart on the card,
# the time a reboot took unknown to it; the ingest sees that as its offset moving, and counts it (`clock_steps`).
#
# A CAMERA DOES NOT SLEEP (the owner's decision on the eleventh review): the steady clock is the monotonic one, and a sleep
# would look like the camera's clock stepping forward by its length — taken up on the line and counted (`forward`).
CLOCK_UNSET = 365 * 86400.0              # a step forward of more than a year…
CLOCK_FLOOR = 1.5e9                      # …out of a clock that read before mid-2017: the clock was SET (`CamLine`)
LINE_NOTE = "line.json"                  # the line, kept on the card beside the segments (`CardActuator.note_line`)


def boot_id() -> str | None:
    """This boot's id where the system says it (Linux), or None: then two boots are told apart by the steady clock alone
    — one that went back began again."""
    try:
        with open("/proc/sys/kernel/random/boot_id") as f:
            return f.read().strip() or None
    except OSError:
        return None


class CamLine:
    """The camera's line of time. `place(begin, end)` — where a frame captured then (on the camera's clock) lies on it;
    `now()` — the camera's clock on it. `unit`: what one second is in the frames' times (ms on the ring — the archive's
    `at` — or seconds in the model pusher's own memory). `steady`: the camera's steady clock, in seconds; None — steps
    forward are not told from pauses (a clock of a test's own that gives no steady one), steps back by the frames only.
    `boot`: () -> this boot's id, or None. `note()` and `restore(note, newest)` — the line kept on the card, and taken back."""

    def __init__(self, clock, steady=None, unit: int = 1000, at=archive_ms, boot=None):
        self.clock, self.steady, self.unit, self.at, self.boot = clock, steady, unit, at, boot
        self.shift = 0                   # what the line adds to the camera's capture times
        self.due = 0                     # …and what it is to add, from the first frame captured on the stepped clock
        self.prev: tuple | None = None   # (begin, end) of the frame placed last, on the line
        self.gap = unit / 1000           # the frames' interval, as last seen (a millisecond to a second)
        self._seen: tuple | None = None  # (the camera's clock, the steady clock) at the last look
        self.back = self.back_by = 0     # steps back taken up, and by how much (units)
        self.forward = self.forward_by = 0
        self.ahead = 0                   # frames with no capture time, kept right after the frame before
        self.floor = at(CLOCK_FLOOR)
        self.origin = None               # the line where this process began: all it placed is past it
        self.since = None                # …where the camera's clock was found unset: relabelled when it is set
        self.anchor = 0                  # the conversion (line − clock) the line takes when the clock is set
        self.sets = self.unset = 0       # clocks set, and found unset again by a reboot
        self.moves: list[tuple] = []     # (lo, hi, delta): what of the line was relabelled, for whoever holds its times
        self.on_move: list = []          # fn(lo, hi, delta), called where the move is made (the ring's lock)
        self.version = 0                 # moves with every change of the conversion: the card's note is written again
        self.tied = False                # the line is the card's: restored from its note, or written into it
        self._quiet = False              # the step due is a clock being set: not a step of the clock to count

    def look(self):
        """The camera's clock, in units — and a step it took since the last look, against the steady clock, made due."""
        raw = self.at(self.clock())
        if self.origin is None:
            self.origin = raw + self.shift
            if raw < self.floor:
                self.since = self.origin             # a clock not set yet (or a test's own: nothing happens unless it is set)
        if self.steady is not None:
            st = self.steady()
            if self._seen is not None:
                jump = (raw - self._seen[0]) - (st - self._seen[1]) * self.unit
                if jump > CLOCK_UNSET * self.unit and self._seen[0] < self.floor:
                    self._set(raw, jump)
                elif abs(jump) > CLOCK_JUMP * self.unit:
                    self.due -= jump
                    self.version += 1
            self._seen = (raw, st)
        return raw

    def _boot(self):
        try:
            return self.boot() if self.boot is not None else None
        except Exception:                            # noqa: BLE001 — no id: told apart by the steady clock
            return None

    def _move(self, lo, hi, delta) -> tuple:
        """Everything on the line in `[lo, hi]` moves by `delta` — this line's own place, and every holder of its times
        (`on_move`, and later `moves`)."""
        self.shift += delta
        if self.prev is not None and lo <= self.prev[0] <= hi:
            self.prev = (self.prev[0] + delta, self.prev[1] + delta)
        if self.origin is not None and lo <= self.origin <= hi:
            self.origin += delta
        mv = (lo, hi, delta)
        self.moves.append(mv)
        self.version += 1
        for fn in list(self.on_move):
            fn(*mv)
        return mv

    def _set(self, raw, jump) -> None:
        """The camera's clock was SET: the line re-anchored on it, and what was placed since it was unset relabelled."""
        before = raw - jump + self.shift + self.due              # the line now, had the clock not moved
        delta = raw + self.anchor - before
        lo = self.since if self.since is not None else self.origin
        self.sets += 1
        self.due -= jump                                         # the frames captured on the set clock: on the anchor…
        self._quiet, self.since = True, None
        self.version += 1
        if delta * 1000 >= self.unit:                            # (later: nothing placed can overtake what was)
            self._move(lo, before, delta)                        # …and those before it, relabelled to meet them
            log.warning("the camera's clock was set: its line goes on the set clock, and the %.0f s placed before it are "
                        "relabelled by %.3f s — on the card too", (before - lo) / self.unit, delta / self.unit)
        elif delta < -CLOCK_JUMP * self.unit:
            log.warning("the camera's clock was set %.1f s behind what its line holds: the line goes on where it is, ahead "
                        "of the set clock by that much", -delta / self.unit)

    def note(self) -> dict:
        """The line as the card keeps it (`LINE_NOTE`)."""
        raw = self.look()
        return {"line": raw + self.shift + self.due, "raw": raw, "unit": self.unit, "boot": self._boot(),
                "steady": self.steady() if self.steady is not None else None, "since": self.since, "anchor": self.anchor}

    def restore(self, note: dict | None, newest=None) -> tuple | None:
        """The line of the camera's process before this one (`note`, as `note()` wrote it on the card; None: none, or
        none that reads) and the card's newest frame (`newest`, units; None: it holds none): the line goes on from there
        (above). Returns the move it made of what this process had placed already, or None."""
        raw = self.look()
        now = raw + self.shift + self.due
        st = self.steady() if self.steady is not None else None
        target, step, floor, since, anchor = now, 0, newest, self.since, self.anchor
        if note is not None:
            n_line, n_raw = note["line"], note["raw"]
            n_st, n_boot, boot = note.get("steady"), note.get("boot"), self._boot()
            if st is not None and n_st is not None and st >= n_st and (boot is None or n_boot is None or boot == n_boot):
                target = n_line + (st - n_st) * self.unit                # the same boot: by the steady clock
                step = (raw - n_raw) - (st - n_st) * self.unit           # …what the clock did while no process watched
                since, anchor = note.get("since"), note.get("anchor") or 0
            else:                                                        # a new boot: by the conversion it kept
                target = raw + (n_line - n_raw)
                floor = n_line if newest is None else max(newest, n_line)
                anchor = (n_line - n_raw) if n_raw >= self.floor else (note.get("anchor") or 0)
                since = None
        if floor is not None and target <= floor:
            if floor - target > CLOCK_UNSET * self.unit and raw < self.floor:
                self.unset += 1                                          # the clock unset again: after the card's newest,
                log.warning("the camera's clock is not set (the card's newest is %.0f days later than it): its frames go on "
                            "right after the card's newest until it is set", (floor - target) / self.unit / 86400)
                target = since = floor + self.gap                        # until it is set
            else:
                step = min(step, target - floor - self.gap)              # behind what the card holds: stepped back
                target = floor + self.gap
        if abs(step) > CLOCK_JUMP * self.unit:
            self._said(-step, target)
        delta, mv = target - now, None
        if abs(delta) * 100 >= self.unit:
            mv = self._move(self.origin if self.origin is not None else now, now, delta)
        self.since, self.anchor, self.tied = since, anchor, True
        self.version += 1
        return mv

    def now(self):
        """The camera's clock on the line, in units: what the camera states beside its frames."""
        return self.look() + self.shift + self.due

    def skew(self) -> float:
        """What the line adds to the camera's clock, in seconds."""
        return (self.shift + self.due) / self.unit

    def _after(self, prev: tuple):
        return prev[1] if prev[1] > prev[0] else prev[0] + self.gap

    def _carries(self, b, now) -> bool:
        """Whether the frame at `b` (on the line as it stands) was captured on the stepped clock: it carries the step
        that is due. With a frame before it, by the distance from that frame — the frames' interval and the step — and
        without one by the clock: captured just now on it. The frames on their way, captured before the step, do not."""
        d = self.due
        off = self.gap - (b - self.prev[0]) if self.prev is not None else now - b
        return (off - d / 2) * d > 0

    def _said(self, d, b) -> None:
        if d > 0:
            self.back, self.back_by = self.back + 1, self.back_by + d
        else:
            self.forward, self.forward_by = self.forward + 1, self.forward_by - d
        if abs(d) >= self.unit:
            log.warning("the camera's clock stepped %s %.1f s: its frames go on right after the last one, on its own line "
                        "of time, and nothing of them is lost", "back" if d > 0 else "forward", abs(d) / self.unit)

    def place(self, b, e) -> tuple:
        """Where a frame captured at `[b, e)` on the camera's clock lies on the line."""
        raw = self.look()
        b, e = b + self.shift, e + self.shift
        prev, now = self.prev, raw + self.shift + self.due
        if self.due and self._carries(b, now):                       # the first frame of the stepped clock
            d, self.due = self.due, 0
            self.shift += d
            self.version += 1
            b, e = b + d, e + d
            if self._quiet:
                self._quiet = False                                  # a clock set (`_set`): counted there, not a step
            else:
                self._said(d, b)
            if prev is not None and b <= prev[0]:                    # the clock's measure and the frame's differ by the
                b, e = self._after(prev), self._after(prev) + max(0, e - b)   # frame's travel: right after the one before
        elif prev is not None and b <= prev[0]:                      # back, by the frames' own order
            step = self._after(prev) - b
            self.shift += step
            self.version += 1
            b, e = b + step, e + step
            if self.due > 0:
                self.due = 0                                         # the step the clock was seen to take: this one
            self._said(step, b)
        elif b > max(prev[1] if prev is not None else now, now) + RING_AHEAD * self.unit:
            to = self._after(prev) if prev is not None else now
            self.ahead += 1
            if self.ahead == 1 or self.ahead % 1000 == 0:
                log.warning("a frame came stamped %.0f s later than the camera's clock (%d such so far): kept, at the time "
                            "of the frame before it", (b - to) / self.unit, self.ahead)
            b, e = to, to + max(0, e - b)
        elif prev is not None:
            self.gap = min(self.unit, max(self.unit / 1000, b - prev[0]))
        self.prev = (b, e)
        return b, e


# -- the camera's frames in memory (the product's camfeed) -------------------------------------------------------
class CamRing:
    """The last `window` seconds of the camera's frames, from a key frame, in at most `max_bytes`. Every reader of
    frames reads this one ring — the pusher and the card's writer — so the camera holds each frame in memory once."""

    def __init__(self, window: float = RING_SECONDS, max_bytes: int = RING_BYTES, clock=time.time, steady=None):
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
        # The ring's own line of time (`CamLine`), in archive ms: every frame is put on it here, once. Its steady clock
        # tells a step forward from a pause: the camera's monotonic clock with the camera's real one; a test that gives
        # a clock of its own gives the steady one beside it, or none.
        # (A real camera's boot is told by its id with the real clocks; a test's clocks are told apart by themselves.)
        real = steady is None and clock is time.time
        self.line = CamLine(clock, time.monotonic if real else steady, boot=boot_id if real else None)
        self.line.on_move.append(self._relabel)
        self._movers: dict[int, object] = {}                 # fn(lo, hi, delta) of whoever holds the line's times

    # The line itself is `CamLine`'s (above); the ring is where every frame is put on it — under the ring's lock, before
    # any subscriber or reader sees it.
    def _timed(self, s: Sample) -> Sample:
        b, e = self.line.place(s.begin, s.end)
        b, e = int(round(b)), int(round(e))
        return s if (b, e) == (s.begin, s.end) else dataclasses.replace(s, begin=b, end=e)

    # THE LINE RE-ANCHORED (`CamLine.restore`, `_set`; the eleventh review): under the ring's lock, where the move is made,
    # the frames it holds in `[lo, hi]` move with it, and whoever holds the line's times is told (`on_move`: the card's
    # writer — it must not wait). The pusher reads `moves()` on its next pass.
    def _relabel(self, lo, hi, delta) -> None:
        d = int(round(delta))
        self._frames = [dataclasses.replace(f, begin=f.begin + d, end=f.end + d) if lo <= f.begin <= hi else f
                        for f in self._frames]
        for fn in list(self._movers.values()):
            fn(lo, hi, d)

    def on_move(self, fn):
        """`fn(lo, hi, delta)` (archive ms) whenever the line moves what it placed; returns the call that stops it."""
        with self._lock:
            sid, self._next = self._next, self._next + 1
            self._movers[sid] = fn

        def cancel():
            with self._lock:
                self._movers.pop(sid, None)
        return cancel

    def moves(self) -> list[tuple]:
        """Every move of the line so far: `(lo, hi, delta)` in archive ms."""
        with self._lock:
            return list(self.line.moves)

    def note(self) -> dict:
        """The ring's line, as the card keeps it (`CamLine.note`)."""
        with self._lock:
            return self.line.note()

    def restore(self, note: dict | None, newest: int | None) -> tuple | None:
        """The line of the camera's process before this one, off the card (`CamLine.restore`): what the ring holds
        already moves with it."""
        with self._lock:
            return self.line.restore(note, newest)

    def skew(self) -> float:
        """What the ring's line adds to the camera's clock, in seconds — the steps it has taken up, back and forward.
        Whoever states the camera's time beside the ring's frames states it on this line (`now`)."""
        with self._lock:
            return self.line.skew()

    def now(self) -> float:
        """The camera's clock on the ring's line, in unix seconds: what the camera's pusher states to the ingest."""
        with self._lock:
            return unix_s(self.line.now())

    clock_back = property(lambda self: self.line.back)           # steps back taken up…
    clock_back_ms = property(lambda self: int(round(self.line.back_by)))
    clock_forward = property(lambda self: self.line.forward)     # …and forward (the tenth review)
    clock_forward_ms = property(lambda self: int(round(self.line.forward_by)))
    ahead = property(lambda self: self.line.ahead)               # frames with no capture time

    # An empty ring takes only a key frame: nothing before it can be decoded. Room is made by letting go of the oldest
    # WHOLE group of pictures — a group cut in the middle is a group nobody can play — and a kept ring hands what it
    # lets go of to `spill` instead of dropping it. Every subscriber gets the sample as it came, under the lock: a
    # subscriber must not wait for anything (the card's writer only queues).
    def add(self, s: Sample) -> None:
        with self._lock:
            self.added += 1
            self.last_frame_at = self.clock()
            s = self._timed(s)
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
    #
    # `joined`: the reader knows the frame at `t_ms` is followed with nothing missing although the ring does not hold it
    # — the camera's pusher, whose continuation of a break read up to here off the card (М12 Lesson 16).
    def piece(self, t_ms: int, max_bytes: int, upto: int | None = None, caught_up=None,
              joined: bool = False) -> tuple[list[Sample], bool]:
        """`(frames, whole)`: the next frames past `t_ms`, at most `max_bytes` of them (one frame at least), none
        that begins after `upto`; `whole` — they follow the frame at `t_ms` with nothing missing between."""
        with self._lock:
            fs = self._frames
            i = next((k for k, f in enumerate(fs) if f.begin > t_ms), len(fs))
            whole = t_ms == 0 or joined or (i > 0 and fs[i - 1].begin == t_ms)
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

    def oldest(self) -> int:
        """When the oldest frame held began (archive ms); 0 when the ring is empty."""
        with self._lock:
            return self._frames[0].begin if self._frames else 0

    def last_key(self) -> int:
        """When the newest KEY frame held began (archive ms): where a reader that fell behind starts again; 0: none."""
        with self._lock:
            return next((f.begin for f in reversed(self._frames) if f.key), 0)

    def weight(self, t_ms: int) -> int:
        """The bytes of what the ring holds past `t_ms` (archive ms): what a reader at `t_ms` still has to send."""
        with self._lock:
            return sum(len(f.body) for f in self._frames if f.begin > t_ms)

    # HOW FAR BACK THE RING REACHES (the review's sixth pass). The window is sixty seconds and the ceiling is bytes:
    # at 6 Mbit/s the ring holds forty-four seconds, at 8 thirty-three (32 MiB at 750 000 and 1 000 000 bytes a
    # second; the seventh review caught "thirty-three at 6" here and in Lesson 26), and the card's gate went on saying
    # sixty — "recording from 60 s ago" over a ring that began after the break did. What the ring CAN hold of this
    # camera's stream is its ceiling at the bitrate it is being given: measured over what it holds now, once that is
    # `MEASURE_SPAN` of stream (a key frame alone would measure as a hundred megabits), and never more than the window.
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
            if self.clock_back:                          # the camera's clock stepped back, and the ring took it up (`CamLine`)
                out.update(clock_back=self.clock_back, clock_back_s=round(self.clock_back_ms / 1000.0, 3))
            if self.clock_forward:                       # …or forward (the tenth review)
                out.update(clock_forward=self.clock_forward, clock_forward_s=round(self.clock_forward_ms / 1000.0, 3))
            if self.ahead:
                out["frames_ahead"] = self.ahead
            if self.line.sets or self.line.unset:        # the clock set, found unset by a reboot (the eleventh review)
                out.update(clock_set=self.line.sets, clock_unset=self.line.unset)
            if self.last_frame_at is not None:
                out["last_frame_age_s"] = round(now - self.last_frame_at, 3)
            return out


# -- the card: segment files with a byte budget (the product's cardbuf) --------------------------------------------
#
#     <path>/<recording>/e<epoch>/<begin>.smpl     sample records back to back, as they travel (`Sample.encode`);
#                                                  <begin> is the first sample's archive time, in ms
#     …/<begin>@<delta>.smpl                       a segment RELABELLED (`relabel`): every record in it is `delta` ms
#                                                  later than it says — the camera's line was re-anchored after it was
#                                                  written (`CamLine`, a clock set); a record appended to it says its
#                                                  time less `delta`, so the one number holds for the whole file
#
# A segment opens on a key frame and is only ever appended to. One that a power loss cut is read up to its last whole
# record and cut there when the card opens; nothing else needs repair, because nothing else is written.
class _Segment:
    __slots__ = ("stream", "path", "first", "last", "last_begin", "bytes", "delta")

    def __init__(self, stream: str, path: str):
        self.stream, self.path = stream, path
        self.first = self.last = self.last_begin = 0         # archive ms: the first sample's begin, the last's end
        self.bytes = 0
        self.delta = 0                                       # what its records' times lack (`CardBuffer.relabel`)


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

    # TWO LOCKS: WHAT IS ON THE CARD, AND THE CARD'S I/O (the seventh review). One lock held across `write` and `fsync`
    # was taken by every reader too — the heartbeat's `stats`, the coverage, a range's answer — and a write that hung
    # for forty seconds held all of them: the camera's recorder stopped beating, went "lost" after 45 s with no reason
    # given, and its card said `recording` the whole time. Now the I/O — a write, an open, a close, a delete — is one at
    # a time under `_io`, and what the card holds (its segments and bytes) under `_lock`, held for moments and never
    # across I/O: a reader never waits for the card. And the I/O is WATCHED: `stalled_for` is how long the I/O in
    # progress has not returned, readable without any lock; past `stall_after` the card is STALLED — said in the
    # heartbeat (`CardRecorder.heartbeat_extra`), and nothing more waits for it: an append, a range read, a close raise
    # `Stalled` at once, and a `finish` is left for the next I/O that gets the card.
    def __init__(self, path: str, budget: int = CARD_BUDGET, segment_bytes: int = SEGMENT_BYTES,
                 segment_span: float = SEGMENT_SPAN, sync_every: float = SYNC_EVERY, clock=time.monotonic,
                 stall_after: float = STALL_AFTER):
        self.path = path[len("file://"):] if path.startswith("file://") else path
        self.budget = int(budget) or CARD_BUDGET
        self.segment_bytes, self.segment_span, self.sync_every, self.clock = segment_bytes, segment_span, sync_every, clock
        self.stall_after = float(stall_after)
        self._lock = threading.Lock()                        # what is on the card: never held across I/O
        self._iolock = threading.Lock()                      # the card's I/O, one at a time
        self._busy_since: float | None = None                # when the I/O in progress began (`clock`); None: none
        self._busy_bytes = 0                                 # …and the bytes it moves (`stall_limit`)
        self._finish_due: set[str] = set()                   # streams to close at the next I/O: asked while stalled
        self.segs: list[_Segment] = []                       # oldest first
        self.bytes = 0
        # The segment being written, of each STREAM that is: `stream -> [segment, file, when it was last synced, bytes
        # written since]`.
        self.open: dict[str, list] = {}
        self._f = None                                       # the file `_write` writes into: the appending stream's
        self.err: OSError | None = None                      # the last write error: the card is failing
        self.appended = 0                                    # samples written since it opened: a card that works
        self.evicted_owed = self.evicted_owed_ms = 0         # what the budget let go of that the server had not got (`owed`)
        self.evicted_unknown_ms = 0                          # …and let go of with nobody to say whether it had (`owed` unset)
        os.makedirs(self.path, exist_ok=True)
        self._scan()

    def stalled_for(self) -> float:
        """How long the card's I/O in progress has not returned, in seconds; 0 when none is in progress."""
        since = self._busy_since
        return 0.0 if since is None else max(0.0, self.clock() - since)

    # A SLOW CARD IS NOT A STALLED ONE (the eighth review, a minor: one write that took 1.5 × `stall_after` was the
    # card stalled). What the I/O in progress may take grows with what it moves: `stall_after`, and its bytes — the
    # record, and what a forced write puts on the card since the last (`_busy_bytes`) — at `STALL_FLOOR`, the slowest a
    # healthy card writes. Five seconds of an 8 Mbit/s stream forced at once is five seconds more, not a stall.
    def stall_limit(self) -> float:
        return self.stall_after + self._busy_bytes / STALL_FLOOR

    def stalled(self) -> bool:
        return self.stalled_for() >= self.stall_limit()

    @contextlib.contextmanager
    def _io(self):
        """The card's I/O, one at a time — refused at once while the card is stalled, and refused after what the I/O
        ahead may take (`stall_limit`) of waiting for it: nothing waits for a card that does not answer."""
        if self.stalled() or not self._iolock.acquire(timeout=self.stall_limit()):
            raise Stalled(f"the card has not finished a write for {self.stalled_for():.0f} s")
        self._busy_since, self._busy_bytes = self.clock(), 0
        try:
            yield
        finally:
            self._busy_since, self._busy_bytes = None, 0
            self._iolock.release()

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
        _, _, delta = os.path.basename(path)[:-len(".smpl")].partition("@")
        try:
            seg.delta = int(delta) if delta else 0
        except ValueError:
            seg.delta = 0
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
        seg.first, seg.last, seg.last_begin = seg.first + seg.delta, seg.last + seg.delta, seg.last_begin + seg.delta
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
        with self._io():
            if stream in self._finish_due:
                self._finish_due.discard(stream)
                self._close_locked(stream)
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
            data = (dataclasses.replace(s, begin=s.begin - cur.delta, end=s.end - cur.delta) if cur.delta else s).encode()
            held = self.open[stream]
            due = self.clock() - held[2] >= self.sync_every
            self._busy_bytes = len(data) + (held[3] if due else 0)      # what this I/O moves (`stall_limit`)
            try:
                self._f = held[1]
                self._write(data)
                held[3] += len(data)
                if due:
                    os.fsync(self._f.fileno())
                    held[2], held[3] = self.clock(), 0
            except OSError as e:
                self.err = e
                raise
            with self._lock:
                cur.last, cur.last_begin, cur.bytes = s.end, s.begin, cur.bytes + len(data)
                if not cur.first:
                    cur.first = s.begin
                self.bytes += len(data)
            self.err = None
            self.appended += 1
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
        self.open[stream] = [seg, open(path, "ab"), self.clock(), 0]
        with self._lock:
            self.segs.append(seg)
        return seg

    def finish(self, stream: str) -> None:
        """Close the stream's open segment: its next sample opens a new one, on a key frame. On a card that does not
        answer it is left for the next I/O that gets the card — its next sample of the stream opens a new segment
        all the same — and whoever asked does not wait."""
        try:
            with self._io():
                self._close_locked(stream)
        except Stalled:
            self._finish_due.add(stream)

    # A SEGMENT LEFT OPEN ACROSS A HOLD (the eighth review: a hold in the middle of a group of pictures closed the
    # segment, and the release that followed could open the next one only on a key frame — the rest of the group, on
    # the card nowhere and counted nowhere, while the ring still held it). A recording put on hold leaves its segment
    # open, forced onto the card (`sync`); released, it goes on in it from the frame after its last, mid-group, when
    # that frame follows (`follows`), and closes it with a hole when it does not (`CardActuator._catch_up`).
    def sync(self, stream: str) -> None:
        """What the stream's open segment holds, forced onto the card; the segment stays open. Nothing on a stalled card."""
        with self._io():
            held = self.open.get(stream)
            if held is not None and stream not in self._finish_due:
                self._busy_bytes = held[3]
                held[1].flush()
                os.fsync(held[1].fileno())
                held[2], held[3] = self.clock(), 0

    def follows(self, stream: str, begin: int) -> bool:
        """Whether the stream's segment is open and ends with the sample that began at `begin`: the next sample may be a
        delta frame of the same group."""
        with self._lock:
            held = self.open.get(stream)
            return (held is not None and stream not in self._finish_due and held[0].bytes > 0
                    and held[0].last_begin == begin)

    def close(self) -> None:
        """Every open segment closed. `Stalled` on a card that does not answer: the files stay with the I/O that hung."""
        with self._io():
            failed = None
            for stream in list(self.open):
                try:
                    self._close_locked(stream)
                except OSError as e:                         # every segment is closed, whatever one of them said
                    failed = e
            if failed is not None:
                raise failed

    # Under `_io`: the file is the I/O's, the segment list is `_lock`'s.
    def _close_locked(self, stream: str) -> None:
        cur, f, *_ = self.open.pop(stream, (None, None))
        if f is self._f:
            self._f = None
        if f is not None:
            try:
                f.flush()
                os.fsync(f.fileno())
            finally:
                f.close()
        if cur is not None and cur.bytes == 0:                # opened and never written
            self._drop(cur)
            try:
                os.remove(cur.path)
            except OSError:
                pass

    # The budget: the oldest closed segments go while the card is over it. An open one never does. Under `_io`; a
    # segment leaves the list before its file goes, so a reader lists only what is still there (or finds it gone, and
    # takes it for that: `_range_of`).
    #
    # …BUT WHAT THE SERVER HAS NOT GOT GOES LAST (the ninth review, major). A stream that lags opens the card, and the
    # card writes the whole stream — what the uplink then carried as well as what the pusher skipped — and its budget
    # let go of the oldest first: 400 s at 0.75 of an 8 Mbit/s stream, 345 MiB written, a budget of 200, and 61 of the
    # 121 seconds the stream skipped were gone before the night's backfill — on no copy, and no counter moved. The
    # camera's pusher says what it skipped and backfill has not yet taken (`owed()`: unix seconds on the card's own line,
    # `CameraPusher.owed_spans`), and the card lets go of the oldest segment that holds none of it; only when every
    # closed segment holds some, of the oldest — and what of the owed it held is counted (`evicted_owed`,
    # `evicted_owed_ms`), logged, and said by the recorder as footage lost (`CardRecorder.stream_pass`).
    #
    # NOBODY TO ASK IS NOT "NOTHING OWED" (the tenth review, major): with no pusher wired to say it, the budget went oldest
    # first as before — and silently. Now `owed` unset, or answering None, is UNKNOWN: the oldest still goes first, and
    # what it held is counted as let go of unknowing (`evicted_unknown_ms`) — said by the recorder of a camera whose stream
    # is said (`CardRecorder._stream`), where that is a wiring left half done.
    owed = None                                              # () -> [(t0, t1)] | None, set by whoever runs the card and the pusher

    def _owed_ms(self) -> list[tuple[int, int]] | None:
        if self.owed is None:
            return None
        try:
            spans = self.owed()
            if spans is None:
                return None
            return [(archive_ms(a), archive_ms(b) if b != float("inf") else 1 << 62) for a, b in spans]
        except Exception as e:                               # noqa: BLE001 — the pusher's trouble is not the card's write
            log.warning("card: what the stream skipped could not be read (%s): the budget goes oldest first", e)
            return None

    @staticmethod
    def _holds(seg: _Segment, owed: list[tuple[int, int]]) -> int:
        """How much of `owed` the segment holds, in ms."""
        return sum(max(0, min(seg.last, b) - max(seg.first, a)) for a, b in owed)

    def _retain(self) -> None:
        with self._lock:
            if self.bytes <= self.budget:
                return
        owed = self._owed_ms()                               # (outside the card's lock: it is the pusher's list)
        unknown, owed = owed is None, owed or []
        while True:
            with self._lock:
                if self.bytes <= self.budget:
                    return
                writing = {id(held[0]) for held in self.open.values()}
                closed = [seg for seg in self.segs if id(seg) not in writing]
                if not closed:
                    return
                old = next((seg for seg in closed if not self._holds(seg, owed)), closed[0])
                lost = self._holds(old, owed)
                self._drop_locked(old)
                if unknown:
                    self.evicted_unknown_ms += max(0, old.last - old.first)
                if lost:
                    self.evicted_owed += 1
                    self.evicted_owed_ms += lost
            if lost:
                log.warning("card: full, and every segment on it holds footage the server has not got: %.1f s of it let "
                            "go of before backfill took it (a larger card, a lower bitrate or a faster uplink)",
                            lost / 1000.0)
            try:
                os.remove(old.path)
            except FileNotFoundError:
                pass
            try:
                os.rmdir(os.path.dirname(old.path))          # the epoch's directory, if that was its last segment
            except OSError:
                pass

    def _drop(self, seg: _Segment) -> None:
        with self._lock:
            self._drop_locked(seg)

    def _drop_locked(self, seg: _Segment) -> None:
        if seg in self.segs:
            self.segs.remove(seg)
            self.bytes -= seg.bytes

    # A NOTE BESIDE THE SEGMENTS (the tenth review, major): what the camera knows the server has (`CameraPusher.delivery`)
    # was in the camera's memory only, and a camera whose process started again let go first, uncounted, of what the
    # server had never got. It is kept on the card, as a small file beside the recordings — never a segment, never in
    # the budget's way — written whole and put in place in one rename, so a power loss leaves the last whole note or the
    # one before. Through the card's I/O: a card that does not answer is not waited for.
    def read_note(self, name: str) -> bytes | None:
        """The note `name` the card keeps, or None."""
        try:
            with open(os.path.join(self.path, name), "rb") as f:
                return f.read()
        except FileNotFoundError:
            return None
        except OSError as e:
            raise CardError(f"reading the note {name}: {e}") from None

    def write_note(self, name: str, data: bytes) -> None:
        """The note `name`, written whole. `Stalled` on a card that does not answer."""
        with self._io():
            path = os.path.join(self.path, name)
            self._busy_bytes = len(data)
            with open(path + ".new", "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(path + ".new", path)

    def coverage(self, recording: str) -> list[tuple[float, float]]:
        """What the card holds of `recording` (every epoch), in unix seconds: one span per segment, in order."""
        with self._lock:
            return [(unix_s(s.first), unix_s(s.last)) for s in self.segs
                    if s.stream.startswith(f"{recording}/") and s.bytes > 0]

    def newest(self) -> int | None:
        """Where the newest sample the card holds BEGAN (archive ms), any recording's; None when it holds none."""
        with self._lock:
            return max((s.last_begin for s in self.segs if s.bytes > 0), default=None)

    # THE CARD RELABELLED (the eleventh review, blocker 2): the camera's line was re-anchored — its clock, unset when these
    # were written, was set (`CamLine._set`) — and what the card wrote on the old line moves with it. Not rewritten: each
    # segment wholly in `[lo, hi]` is renamed to say what its records lack (`<begin>@<delta>.smpl`) — one rename, so a power
    # loss leaves it relabelled or not — and every reader adds it. An open segment stays open: what is appended to it says
    # its time less the same `delta`.
    def relabel(self, lo: int, hi: int, delta: int) -> int:
        """Every segment whose samples all began in `[lo, hi]` (archive ms), relabelled by `delta` ms. Returns how many."""
        n = 0
        with self._io():
            with self._lock:
                segs = [s for s in self.segs if s.bytes > 0 and lo <= s.first and s.last_begin <= hi]
            for seg in segs:
                new = os.path.join(os.path.dirname(seg.path), f"{seg.first - seg.delta}@{seg.delta + delta}.smpl")
                os.replace(seg.path, new)
                with self._lock:
                    seg.path, seg.delta = new, seg.delta + delta
                    seg.first, seg.last, seg.last_begin = seg.first + delta, seg.last + delta, seg.last_begin + delta
                n += 1
        return n

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
    # now is not read, and a segment shorter than that is an error. (Every record is flushed as it is written —
    # `_write` — so the reader takes no part in the card's I/O: it used to flush the open files under the one lock, and
    # waited for a write that hung, with the heartbeat behind it; the seventh review.) A card that is STALLED is not
    # read at all: a read of a card that does not finish a write would hang the camera's pusher with it.
    def pieces(self, recording: str | None, t0: float, t1: float, max_bytes: int = PIECE_BYTES):
        if self.stalled():
            raise Stalled(f"the card has not finished a write for {self.stalled_for():.0f} s: it is not read")
        lo, hi = archive_ms(t0), archive_ms(t1)
        held = self.recordings()
        if recording is None:
            if len(held) != 1:
                raise NoRecording(f"the request names no recording, and the card holds {', '.join(held) or 'none'}")
            recording = held[0]
        if str(recording) not in held:
            raise NoRecording(f"no recording {recording} on this card (it holds {', '.join(held) or 'none'})")
        with self._lock:
            parts = [(s.path, s.bytes, s.delta) for s in self.segs
                     if s.stream.startswith(f"{recording}/") and s.bytes > 0 and s.first < hi and s.last > lo]
        return self._pieces_of(parts, lo, hi, max(1, int(max_bytes)))

    # A piece handed over is not kept here (the seventh review): the camera's pusher keeps a read of the card open from
    # one pass to the next, and a generator suspended at `yield out` held the piece it had just given — a piece more in
    # memory for every read left open. The piece is yielded out of a box, and the suspended reader holds one frame.
    def _pieces_of(self, parts: list, lo: int, hi: int, max_bytes: int):
        box, size = [[]], 0
        for path, written, delta in parts:
            for smp in self._range_of(path, written, lo, hi, delta):
                if box[0] and size + len(smp.body) > max_bytes:
                    box.append([])
                    size = 0
                    yield box.pop(0)
                box[0].append(smp)
                size += len(smp.body)
        if box[0]:
            yield box.pop(0)

    def range(self, recording: str | None, t0: float, t1: float) -> list[Sample]:
        """`pieces`, joined: the whole range as ONE list — for a reader with a server's memory, and the tests. A
        camera answers with the pieces."""
        return [smp for piece in self.pieces(recording, t0, t1) for smp in piece]

    @staticmethod
    def _range_of(path: str, size: int, lo: int, hi: int, delta: int = 0):
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
                if delta:
                    smp = dataclasses.replace(smp, begin=smp.begin + delta, end=smp.end + delta)
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
        self.moved: list[tuple] = []                     # the line's moves since it started (`CardActuator._moved`)
        self.lock = threading.Lock()
        self.wake = threading.Condition(self.lock)
        self.stopped = False
        self.untap = None
        self.thread: threading.Thread | None = None


class CardActuator:
    """Writes the card's recordings from the camera's ring. `threaded`: a writer thread per recording (a camera);
    off, the tests write with `drain()` when they choose — the card that has not caught up yet is a test, too."""

    NOTE_EVERY = 30.0                    # the line's note is written at least this often (`note_line`)

    def __init__(self, ring: CamRing, card: CardBuffer | None = None, threaded: bool = True,
                 queue_bytes: int = QUEUE_BYTES, piece_bytes: int = PIECE_BYTES):
        self.ring, self.threaded, self._card = ring, threaded, None
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
        # The camera's line on the card (`CamLine`; the eleventh review): the note of it, when last written and at which
        # version of the line, and the moves of the line the card has yet to be relabelled by.
        self._nlock = threading.Lock()
        self._noted: tuple = (None, float("-inf"))
        self._note_error = ""
        self._card_due: list[tuple] = []
        ring.on_move(self._moved)
        self.card = card

    # THE CARD IS WHERE THE CAMERA'S LINE IS KEPT (the eleventh review, blockers 1 and 2; `CamLine`). The card is attached
    # here — at the start, or by the recorder when it opens (`CardRecorder.volume_pass`) — and the ring's line goes on
    # from the line the card's note kept, before the card is written: in one boot by the steady clock, in the next through
    # the conversion the note kept, and never back over the card's newest frame. A card attached again in the same process
    # (it failed, and was opened again) is on this line already.
    @property
    def card(self) -> CardBuffer | None:
        return self._card

    @card.setter
    def card(self, card: CardBuffer | None) -> None:
        self._card = card
        if card is not None and not self.ring.line.tied:
            self._restore_line(card)

    def _restore_line(self, card: CardBuffer) -> None:
        note = None
        try:
            raw = card.read_note(LINE_NOTE)
            if raw:
                d = json.loads(raw)
                if not isinstance(d, dict) or finite(d["unit"]) != self.ring.line.unit:
                    raise ValueError("not a line of this camera's units")
                opt = lambda k: None if d.get(k) is None else finite(d[k])
                note = {"line": finite(d["line"]), "raw": finite(d["raw"]), "steady": opt("steady"),
                        "since": opt("since"), "anchor": opt("anchor") or 0,
                        "boot": d.get("boot") if isinstance(d.get("boot"), str) else None}
        except (CardError, *PARSE_ERRORS) as e:
            log.warning("card: its note of the camera's line of time does not read (%s): the line goes on after what the "
                        "card holds", e)
        mv = self.ring.restore(note, card.newest())
        self._card_due.clear()                           # nothing of this process's line is on this card yet
        if mv is not None:
            log.info("card: the camera's line goes on from the card's (%s): moved %.3f s", "its note" if note else
                     "its newest frame", mv[2] / 1000.0)
        self.note_line(force=True)

    # Under the ring's lock, where the line moved (`CamRing._relabel`): what the writers hold on the line moves with it —
    # what waits in their queues, where each stands, what a stopped one left — and the card itself is relabelled by the
    # next writer that gets to it, before it writes (`note_line`). It must not wait: no I/O here.
    def _moved(self, lo, hi, d: int) -> None:
        def mv(s):
            return dataclasses.replace(s, begin=s.begin + d, end=s.end + d) if s is not _CUT and lo <= s.begin <= hi else s
        with self._lock:
            recs = list(self.recs.values())
            self.carried = {cid: ((c[0] + d) if lo <= c[0] <= hi else c[0], *c[1:]) for cid, c in self.carried.items()}
        for r in recs:
            with r.lock:
                r.live, r.spill = collections.deque(map(mv, r.live)), collections.deque(map(mv, r.spill))
                if r.last and lo <= r.last <= hi:
                    r.last += d
                r.moved.append((lo, hi, d))
        self._card_due.append((lo, hi, d))

    # THE LINE'S NOTE ON THE CARD (`LINE_NOTE`): written before the first frame on a line that moved goes to the card — a
    # step taken up, the clock set, the line restored — and every `NOTE_EVERY` besides, so the note is never far from the
    # line the card's frames are on; and the card relabelled first by what the line moved. Through the card's I/O: a card
    # that does not answer is not waited for, and the note is tried again at the next frame.
    def note_line(self, force: bool = False) -> bool:
        card = self._card
        if card is None:
            return False
        with self._nlock:
            while self._card_due:
                lo, hi, d = self._card_due[0]
                try:
                    n = card.relabel(int(lo // 1), -int(-hi // 1), d)
                except OSError as e:
                    log.warning("card: relabelling what it wrote before the camera's clock was set: %s — tried again", e)
                    return False
                self._card_due.pop(0)
                log.info("card: %d segment(s) relabelled by %.0f s: the camera's clock was set", n, d / 1000.0)
            v, now = self.ring.line.version, card.clock()
            if not force and v == self._noted[0] and now - self._noted[1] < self.NOTE_EVERY:
                return False
            try:
                card.write_note(LINE_NOTE, json.dumps(self.ring.note()).encode())
            except OSError as e:
                if str(e) != self._note_error:
                    log.warning("card: the camera's line of time could not be kept on the card (%s): tried again", e)
                self._note_error = str(e)
                return False
            self._noted, self._note_error, self.ring.line.tied = (v, now), "", True
            return True

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
    # A restart under the SAME epoch — the gate putting a released recording on hold again — leaves the segment open
    # (the eighth review): the next writer goes on in it from the frame after `last`, in the middle of a group of
    # pictures, as long as the ring still holds that frame. Under a new epoch the stop closes the segment, a segment
    # opens on a key frame, and what a restart costs is the rest of the group it stopped in — counted
    # (`samples_dropped`).
    def __call__(self, verb: str, cam: dict) -> bool:
        cid = str(cam["id"])
        self.calls.append((verb, cid))
        if verb in ("start", "restart"):
            if self.card is None:
                return False                             # no card open: nothing to write into, the reconciler retries
            stream = f"{cid}/e{int(cam.get('epoch', 0))}"
            with self._lock:
                old = self.recs.get(cid)
            self._stop(cid, close=old is None or old.stream != stream)
            r = _Rec(cid, stream, bool(cam.get("hold")))
            r.last, r.written, r.dropped, r.lost_ms = self.carried.get(cid, (0, 0, 0, 0))
            newest = self.ring.newest()
            if newest and r.last > newest:
                r.last = 0
            r.need_key = not (r.last and self.card.follows(stream, r.last))
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
        self.note_line()
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
                seen = len(r.moved)
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
                self._write(r, s, seen)

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
        with r.lock:
            seen = len(r.moved)
        at = r.last
        piece, whole = self.ring.piece(at, self.piece_bytes, upto=upto, caught_up=done)
        with r.lock:
            if len(r.moved) > seen:
                return True                              # the line moved under the piece: taken again, moved (`_moved`)
            spilled = [self._took(r.spill) for _ in range(len(r.spill))]
        for s in spilled:
            self._write(r, s, seen)
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
    #
    # A frame taken from the queue before the line moved and written after (`seen`: the moves it had been through) is
    # moved here, as the queue's were (`_moved`); one of a piece of the ring is passed over by `last`, and the ring gives
    # it again, moved. The card's note of the line is written before the frame, when the line moved (`note_line`).
    def _write(self, r: _Rec, s, seen: int | None = None) -> None:
        if seen is not None and s is not _CUT and len(r.moved) > seen:
            with r.lock:
                for lo, hi, d in r.moved[seen:]:
                    if lo <= s.begin <= hi:
                        s = dataclasses.replace(s, begin=s.begin + d, end=s.end + d)
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
            if r.resumed or r.release_due:
                r.dropped += 1                           # …the rest of the group it was stopped in: not on the card
            return
        self.note_line()
        try:
            self.card.append(r.stream, s)
        except NeedKey:
            r.last, r.need_key = s.begin, True
            return
        except Backwards:
            r.last = s.begin
            return
        except Stalled as e:                             # not a refusal: the card does not answer (the seventh review) —
            r.last_error, r.need_key, r.failed = str(e), True, True      # dead all the same, back from `last` later
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
            # Released, it goes on in the segment it left open when that segment ends with `last` (`CardBuffer.follows`);
            # put on hold, what was queued before still goes into it.
            if not hold:
                r.need_key = self.card is None or not (r.last and self.card.follows(r.stream, r.last))
            r.wake.notify()
        if hold and self.card is not None:
            try:
                self.card.sync(r.stream)                 # on hold the segment stays open (`CardBuffer.sync`)
            except OSError as e:
                log.warning("card: forcing %s onto the card: %s", r.stream, e)
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
    def _stop(self, cid: str, close: bool = True) -> None:
        with self._lock:
            r = self.recs.pop(cid, None)
        if r is None:
            return
        if r.untap is not None:
            r.untap()
        with r.lock:
            r.stopped = True
            r.wake.notify()
        if r.thread is not None:                         # a writer stuck in a card that does not answer is not waited for
            r.thread.join(timeout=0.0 if self.card is not None and self.card.stalled() else 5.0)
        self._flush(r)
        upto, seen = self.ring.newest(), len(r.moved)
        while (r.keep or not r.hold) and not r.failed:
            for lo, hi, d in r.moved[seen:]:             # (the line moved meanwhile: its newest frame with it)
                upto = upto + d if lo <= upto <= hi else upto
            seen = len(r.moved)
            if not self._catch_up(r, upto):
                break
        if r.keep:
            self._unkeep(r)
        self._flush(r)                                   # what a kept ring spilled while this was going on
        self.carried[cid] = (r.last, r.written, r.dropped, r.lost_ms)
        if self.card is not None:
            try:
                if close or r.failed:
                    self.card.finish(r.stream)
                else:
                    self.card.sync(r.stream)             # restarted under the same epoch: the next writer goes on in it
            except OSError as e:
                log.warning("card: closing %s: %s", r.stream, e)

    # Everything queued, written — the spill, then live — and its bytes given back to the queue's budget, written or not.
    def _flush(self, r: _Rec) -> None:
        with r.lock:
            queued, seen = [self._took(q) for q in (r.spill, r.live) for _ in range(len(q))], len(r.moved)
        for s in queued:
            self._write(r, s, seen)

    def pump(self) -> tuple[list, list]:
        """(dead, posted): a recording the card refused a write of is dead, and stopped here; the recorder starts it
        again after its backoff (`VmsWorker.pump_once`), from the last frame the card took."""
        self.note_line()
        with self._lock:
            dead = [(cid, r.last_error) for cid, r in self.recs.items() if r.failed]
        for cid, why in dead:
            log.warning("card: %s: the card did not take a write (%s) — the recording is restarted", cid, why)
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
    PREBUFFER_AGAIN = 86400.0            # `card.prebuffer.short` is raised when it begins, and once a day while it lasts
    STALL_ALARM = 3.0                    # a stall is the alarm `card.failing` when it lasts this many `stall_after`
    WELL_FOR = 600.0                     # an alarm's episode is over when what raised it has not been seen for this long

    def __init__(self, name, vars_, objects, ring: CamRing, actuator: CardActuator | None = None, **kw):
        kw.pop("obsd", None)
        self.ring = ring
        super().__init__(name, vars_, objects, actuator or CardActuator(ring), obsd=NO_ENGINE, **kw)
        self.card: CardBuffer | None = None
        # `card_fault`: what the card did — "would not open", "refused a write" — and `card_error`, the error it gave.
        self.card_fault, self.card_error, self.card_tries, self.card_since = "would not open", "", 0, self.wall()
        self.card_failures = 0                               # times the card was closed for refusing a write
        self.card_cam = ""                                   # the camera whose card this is (the held volume's `cam`)
        self.not_ours: dict[str, str] = {}                   # recordings placed here that are another camera's -> why not recorded
        self._card_retry_at = float("-inf")
        self._coverage: dict[str, tuple[float, list]] = {}
        self.prebuffer_short: dict[str, float] = {}          # recording -> when `card.prebuffer.short` was last raised
        self._short_now: dict[str, float] = {}               # recording -> what the ring should reach, while it does not
        self._short_seen: dict[str, float] = {}              # recording -> when the ring was last seen short
        self.card_refusal = ""                               # what the card refused, until a write lands on it again
        self.failing_said: float | None = None               # when `card.failing` was last raised; None: the card is well
        self.uplink_said: float | None = None                # when `camera.uplink.short` was last raised; None: no episode
        self.uplink_seen = 0.0                               # …and when the stream was last seen lagging
        self.lost_said: float | None = None                  # when `camera.footage.lost` was last raised; None: no episode
        self.lost_seen, self.lost_grew = 0.0, 0.0            # …the seconds it had counted, and when they last grew
        self._evicted_before = 0                             # ms the cards closed before this one let go of unsent
        self._unknown_before = 0                             # …and let go of with nobody to say (`evicted_unknown_ms`)
        self._owed_unknown_said = False                      # the half wiring, logged (`_stream`)
        self._noted_at = float("-inf")                       # when the note of what the server has was last written
        self._slow_said = False                              # a stall too short for the alarm, logged (`failing_pass`)

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
    # 33; the primary's death is noticed after 45; and the log said "recording from 60 s ago" all the same. The start
    # of the break — the one thing the ring is kept for — was on the card at no ordinary bitrate above four megabits,
    # and nothing said so. Now it is said: in the recording's status (`prebuffer_s`, `prebuffer_short`), in the log,
    # and as the alarm `card.prebuffer.short`, when it begins and once a day while it lasts. The cure is the
    # camera's: a lower bitrate, or more memory for the ring (`memory_split`).
    #
    # ONE EPISODE, NOT ONE A DIP (the eighth review's sibling, from the product: no hysteresis). What the ring reaches is
    # measured on what it holds, and a stream whose bitrate moves around the line went short, long, short again — and
    # every turn was a new alarm. The status says what is true now (`_short_now`); the alarm's episode ends only when the
    # ring has reached far enough for `WELL_FOR`.
    def prebuffer_pass(self, now: float | None = None) -> dict:
        from w2cplatform.events import ALARM, EventLog
        now, reach, short = self.wall() if now is None else now, self.ring.reach(), {}
        for row in self.rows:
            uid = str(row["id"])
            if not self._offline_backup(row) or uid not in {str(u) for u in self.reconciler.actual}:
                self.prebuffer_short.pop(uid, None)
                self._short_now.pop(uid, None)
                continue
            need = self.detection(row)
            if reach >= need:
                self._short_now.pop(uid, None)
                if now - self._short_seen.get(uid, -1e18) >= self.WELL_FOR:
                    self.prebuffer_short.pop(uid, None)          # long enough: the episode is over
                continue
            short[uid] = self._short_now[uid] = need
            self._short_seen[uid] = now
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

    # A CARD THAT FAILS IS AN ALARM, NOT ONLY A FIELD (the seventh review: under a card gone read-only "there is no event
    # of the card's failure"). `card.failing` goes into the journal of every recording on the card when the trouble
    # begins — a write refused, a write that has not returned — and once a day while it lasts, through the closing,
    # the opening again and the next refusal: one episode, until a write lands on the card again.
    def failing_pass(self, now: float | None = None) -> str:
        from w2cplatform.events import ALARM, EventLog
        now = self.wall() if now is None else now
        state, error = self._card_said()
        bad = state in ("stalled", "failing") or (state == "recording" and bool(error)) or (
            state == "unavailable" and self.card_fault == "refused a write")
        if not bad:
            self.failing_said = None
            self._slow_said = False
            return ""
        # A STALL IS AN ALARM WHEN IT LASTS (the eighth review, a minor: one write of 1.5 × `stall_after` on a slow, healthy
        # card was the alarm, and every such write a new one). What a write may take grows with its bytes now
        # (`CardBuffer.stall_limit`), and a stall shorter than `STALL_ALARM` of those is said in the heartbeat (`stalled`,
        # `writer: stuck`) and once in the log — a warning; one that lasts is the alarm.
        card = self.card
        if state == "stalled" and self.failing_said is None and card is not None and \
                card.stalled_for() < self.STALL_ALARM * card.stall_limit():
            if not self._slow_said:
                self._slow_said = True
                log.warning("%s: a write to the card has not returned for %.0f s: the card is slow or failing — what it "
                            "does not take now is taken out of the ring when it answers", self.name, card.stalled_for())
            return error
        if self.failing_said is not None and now - self.failing_said < self.PREBUFFER_AGAIN:
            return error
        said = 0
        for row in self.rows:
            uid = str(row["id"])
            if uid in self.epochs:
                EventLog(self.archive_root, REC.name, uid, self.epochs[uid]).append(
                    now, "card.failing", cls=ALARM, cam=row.get("cam"), state=state, error=error)
                said += 1
        if said:
            self.failing_said = now
            log.warning("%s: the card %s (%s): what the camera records goes no further than its memory until the card "
                        "is fixed or replaced", self.name, error, state)
        return error

    # WHAT THE STREAM DID NOT CARRY IS SAID (the eighth review: the pusher's `continued` — `cut_s`, `left_s`, `failed_s` —
    # reached neither a heartbeat, nor a metric, nor an alarm). The camera's pusher runs beside this recorder (М12
    # `CameraPusher`), and whoever runs both hands its word here (`stream_said`, as `stream_says`): it goes into the
    # heartbeat as `stream` — the console's `rec_stream_*` — and a stream that LAGS, the uplink not carrying it, is the
    # alarm `camera.uplink.short`: when it begins, once a day while it lasts, and one episode until the stream has not
    # lagged for `WELL_FOR` — a lagging stream cut to the live edge stops lagging for a minute or two and lags
    # again, and every such turn was not a new alarm.
    stream_said = None                                   # () -> dict, the pusher's `said()`; set by whoever runs both
    # () -> [(t0, t1)]: what the card holds that the server has not got (the pusher's `owed_spans`), set by whoever runs
    # both — the card's budget lets go of it last (`CardBuffer.owed`; the ninth review).
    stream_owed = None
    # () -> dict and (dict) -> None: what the pusher knows the server has (`CameraPusher.delivery`), kept on the card in
    # a note beside its segments every `NOTE_EVERY` and when the card closes, and handed to the pusher of the camera's
    # next process when the card opens (`CameraPusher.remember`; the tenth review: a camera started again let go first,
    # uncounted, of what the server had never got — "what was on the card before this process began is nobody's to say").
    stream_delivery = None
    stream_remember = None
    NOTE = "delivered.json"
    NOTE_EVERY = 30.0
    # ALL OF THEM ARE SET IN ONE CALL (the tenth review, major: "without the hooks the card is FIFO again" — nothing in the
    # course set them but the tests). The camera's process ties its pusher to this recorder with М12's `tie` (or builds
    # the pusher with `camera_process`); a recorder whose stream is said and whose owed is not — a wiring left half done
    # by hand — says so in its heartbeat (`stream.owed: unknown`), logs it once, and counts what its card let go of
    # with nobody to say whether the server had it (`evicted_unknown_s`).

    def _owed(self) -> list | None:
        return list(self.stream_owed()) if self.stream_owed is not None else None

    def evicted_s(self) -> float:
        """Seconds the card's budget let go of before the server had them — every card this recorder opened."""
        card = self.card
        return round((self._evicted_before + (card.evicted_owed_ms if card is not None else 0)) / 1000.0, 1)

    def _stream(self) -> dict | None:
        if self.stream_said is None:
            return None
        try:
            said = self.stream_said()
            said = dict(said) if isinstance(said, dict) else None
        except Exception as e:                           # noqa: BLE001 — the pusher's trouble is not the heartbeat's end
            return {"error": f"{type(e).__name__}: {e}"}
        if said is not None and self.evicted_s():
            said["evicted_s"] = self.evicted_s()         # (the console's `rec_stream_skipped_seconds_total{why="evicted"}`)
        if said is not None and self.stream_owed is None:
            said["owed"] = "unknown"                     # half wired: the card cannot tell what the server has
            unknown = (self._unknown_before + (self.card.evicted_unknown_ms if self.card is not None else 0)) / 1000.0
            if unknown:
                said["evicted_unknown_s"] = round(unknown, 1)
            if not self._owed_unknown_said:
                self._owed_unknown_said = True
                log.warning("%s: the camera's stream is said here and what the server has not got is not: the card lets go "
                            "of its oldest first, whether the server has it or not (tie the pusher to this recorder in one "
                            "call)", self.name)
        return said

    # FOOTAGE ON NO COPY IS AN ALARM (the ninth review, a minor: "what was cut is not seen outside in full" — `failed_s`,
    # the seconds the stream could not carry and the card did not give, was a field and a metric, and no alarm). Two
    # things put footage on no copy, and both are counted where they happen: the card could not give what the stream
    # needed (`failed_s`: a hole on the card, a card that would not read, a card that holds less than memory lacks), and
    # the card's budget let go of what the server had not got (`evicted_s`, `CardBuffer.owed`). When their sum grows, it
    # is the alarm `camera.footage.lost` — once an episode: when it begins, once a day while it lasts, and over when
    # nothing more was lost for `WELL_FOR`.
    def footage_pass(self, now: float | None = None) -> float:
        from w2cplatform.events import ALARM, EventLog
        now = self.wall() if now is None else now
        said = self._stream() or {}
        # The pusher's numbers through `rows.number` (the review's tenth pass): `float` took `nan` for seconds, and
        # `lost_seen` became `nan` for good — `lost <= nan` is never true, so every pass after it was footage lost
        # again; and 400 digits raised `OverflowError` past `(TypeError, ValueError)`, out of `gate_pass` before
        # `note_pass`. A word in one of them is read as nothing lost, counted once a spell (`fields_garbled`).
        failed = number(f"{REC.name}/{self.name}/stream#failed_s", said.get("failed_s") or None, default=0.0)
        evicted = number(f"{REC.name}/{self.name}/stream#evicted_s", said.get("evicted_s") or None, default=0.0)
        lost = failed + evicted
        if lost <= self.lost_seen + 0.05:
            if self.lost_said is not None and now - self.lost_grew >= self.WELL_FOR:
                self.lost_said = None                    # nothing more lost for long enough: the episode is over
            return 0.0
        grew, self.lost_seen, self.lost_grew = lost - self.lost_seen, lost, now
        if self.lost_said is not None and now - self.lost_said < self.PREBUFFER_AGAIN:
            return grew
        told = 0
        for row in self.rows:
            uid = str(row["id"])
            if uid in self.epochs:
                EventLog(self.archive_root, REC.name, uid, self.epochs[uid]).append(
                    now, "camera.footage.lost", cls=ALARM, cam=row.get("cam"), lost_s=round(grew, 1), failed_s=failed,
                    evicted_s=evicted, why=said.get("failed_why", ""))
                told += 1
        if told:
            self.lost_said = now
            log.warning("%s: %.1f s of the camera's footage reached neither the server nor stayed on the card (%s) — "
                        "they are on no copy: a larger card, a lower bitrate or a faster uplink", self.name, grew,
                        said.get("failed_why") or "the card's budget let go of them before the server had them")
        return grew

    def stream_pass(self, now: float | None = None) -> bool:
        """Whether the camera's uplink does not carry its stream — and the alarm, once an episode."""
        from w2cplatform.events import ALARM, EventLog
        now = self.wall() if now is None else now
        said = self._stream() or {}
        if not said.get("lagging"):
            if self.uplink_said is not None and now - self.uplink_seen >= self.WELL_FOR:
                self.uplink_said = None                  # well long enough: the episode is over
            return False
        self.uplink_seen = now
        if self.uplink_said is not None and now - self.uplink_said < self.PREBUFFER_AGAIN:
            return True
        told = 0
        for row in self.rows:
            uid = str(row["id"])
            if uid in self.epochs:
                EventLog(self.archive_root, REC.name, uid, self.epochs[uid]).append(
                    now, "camera.uplink.short", cls=ALARM, cam=row.get("cam"), behind_s=said.get("behind_s"),
                    cut_s=said.get("cut_s"), failed_s=said.get("failed_s"))
                told += 1
        if told:
            self.uplink_said = now
            log.warning("%s: the camera's uplink does not carry its stream (%s s behind): the server gets it late, the "
                        "card records it, and what the stream skips is copied off the card later — a lower bitrate or a "
                        "faster uplink", self.name, said.get("behind_s"))
        return True

    def gate_pass(self, now: float | None = None) -> list[tuple[str, str]]:
        done = super().gate_pass(now)
        self.prebuffer_pass(now)
        self.failing_pass(now)
        self.stream_pass(now)
        self.footage_pass(now)
        self.note_pass()
        return done

    # What the server has, kept on the card (`stream_delivery`, above) — every `NOTE_EVERY`, by this process's clock, and
    # when the card closes. What the server took in the last of those seconds before a crash is taken for owed by the next
    # process, never for had: kept longer, not let go of unknowing.
    def note_pass(self, force: bool = False) -> bool:
        card, said = self.card, self.stream_delivery
        if card is None or said is None or (not force and self.clock() - self._noted_at < self.NOTE_EVERY):
            return False
        try:
            card.write_note(self.NOTE, json.dumps(said()).encode())
        except Exception as e:                           # noqa: BLE001 — the note is not worth a pass of the gate
            log.warning("%s: what the server has could not be kept on the card (%s): tried again next pass", self.name, e)
            return False
        self._noted_at = self.clock()
        return True

    def remember_card(self) -> bool:
        """The note the card kept, handed to the pusher (`stream_remember`) — when the card opens, and when the pusher
        is tied to a recorder whose card is open already."""
        card, told = self.card, self.stream_remember
        if card is None or told is None:
            return False
        try:
            raw = card.read_note(self.NOTE)
            if raw:
                told(json.loads(raw))
        except Exception as e:                           # noqa: BLE001 — a torn note is one the card did not keep
            log.warning("%s: the card's note of what the server has does not read (%s): what the card holds from before "
                        "this process is taken for owed from where this process began", self.name, e)
            return False
        return bool(raw)

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
    #
    # A volume row that does not parse — this card's or anybody's — is skipped by the one reader of rows, counted and
    # named (`volumes.declared`; the review's seventh pass, blocker 1: it raised out of here and out of the lease step).
    # This card's own row garbled is not the card taken away: it is kept by the row read last (`_card_last`).
    def volume_pass(self) -> str:
        unread: set = set()
        rows = {v.name: v for v in volumes.declared(self.vars, unread)
                if v.kind == "edge" and v.enabled and v.server == self.server}
        last = getattr(self, "_card_last", None)
        if self.hold in unread and last is not None and last.name == self.hold:
            rows[self.hold] = last
        held = self.hold
        if held is not None and (held not in rows or not self.renew_hold()):
            self.leave_volume(f"card {held} is not this camera's any more")
        if self.hold is None:
            if not rows or self.claim_hold(sorted(rows)) is None:
                self.volume, self.capacity = "", 0
                self.volume_error = "" if rows else "no card is declared for this camera"
                return self.volume
        vol = self._card_last = rows[self.hold]
        self.card_cam = vol.cam
        self._card_failing(vol)
        if self.card is None and self.clock() >= self._card_retry_at:
            self.card_tries += 1
            try:
                self.card = CardBuffer(vol.url, budget=vol.quota_bytes)
                self.card.owed = self._owed                  # what the server has not got goes last (the ninth review)
                self.actuator.card = self.card
                self.remember_card()                         # …and what it had before this process (the tenth review)
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
            if self.card.appended:
                self.card_refusal = ""                       # a write landed: what it refused is over
            _, error = self._card_said()
            self.capacity, self.volume_error = self.full_capacity, f"the card {error}" if error else ""
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
        self.card_refusal = str(err)
        self._card_retry_at = self.clock() + self.CARD_RETRY

    def _close_store(self, quiet: bool = False, wait: float | None = None) -> None:
        if self.card is not None:
            self.note_pass(force=True)
            self._evicted_before += self.card.evicted_owed_ms
            self._unknown_before += self.card.evicted_unknown_ms
            try:
                self.card.close()
            except OSError as e:
                if not quiet:
                    log.warning("%s: closing the card: %s", self.name, e)
        self.card = None
        self.actuator.card = None

    # What the card holds of a recording — read every `COVERAGE_EVERY`, not every heartbeat: the segments are a list in
    # memory, but a camera's heartbeat goes out every two seconds and the card changes in minutes.
    #
    # ON THE CAMERA'S CLOCK, NOT THE RING'S LINE (the ninth review's blocker, its sibling here). The card is written on the
    # ring's line of time (`CamRing._timed`), which runs ahead of the camera's clock by every step back it took up; the
    # server plans its backfill by laying what the card holds beside its own coverage, on the cluster's clock. Said on
    # the line, a step back of J would put every span J late, and each gap's first J seconds would never be asked for.
    # So the spans are said on the camera's clock — the line less its `skew`. (The ranges themselves need nothing: the
    # ingest moves them by the offset of the camera's clock as the pusher states it, on the same line.)
    def our_coverage(self, unit) -> list[tuple[float, float]]:
        if self.card is None:
            return []
        at, spans = self._coverage.get(str(unit), (float("-inf"), []))
        if self.clock() - at >= self.COVERAGE_EVERY:
            skew = self.ring.skew()
            spans = [(a - skew, b - skew) for a, b in stitch(self.card.coverage(str(unit)), self.stitch)]
            self._coverage[str(unit)] = (self.clock(), spans)
        return spans

    def status_extra(self, cam: dict) -> dict:
        out = super().status_extra(cam)
        out["via"] = "ring"
        out.update(self.actuator.stats(cam["id"]))
        if self.card is None and self.card_error and cam["id"] not in self.reconciler.actual:
            out["why"] = f"the card {self.card_fault}: {self.card_error}"
        if str(cam["id"]) in self.not_ours:
            out["why"] = self.not_ours[str(cam["id"])]
        if self._offline_backup(cam):
            out["prebuffer_s"] = round(self.ring.reach(), 1)
            if str(cam["id"]) in self._short_now:
                out["prebuffer_short"] = self.detection(cam)   # …and a break is noticed only after this many seconds
        return out

    # WHAT THE CARD IS DOING, IN ONE PLACE (the seventh review), read live by the heartbeat and by the volume pass:
    #
    #     stalled      a write has not returned for `CardBuffer.stall_after` — the card does not answer. It used to
    #                  hold the heartbeat with it, and the card said `recording` while nothing reached it
    #     failing      its last write was refused, and it is still open (the next pass closes it)
    #     unavailable  closed: it would not open, or it refused a write — with what it did
    #     recording    open and taking writes — or opened again after refusing, and nothing has landed on it since:
    #                  that is said too, so a card gone read-only is an error all along and not one that blinks
    #
    # `volume_error` was set by the volume pass alone, so it was empty while the card was `failing` and again between
    # its opening anew and its next refusal: `rec_volume_error` went 1, 0, 1 every thirty seconds under a read-only
    # card, and an alert with `for:` never fired.
    def _card_said(self) -> tuple[str, str]:
        """`(state, error)`: what the card is doing, and what it did, in words for the operator ("" when well)."""
        card = self.card
        if card is None:
            if not self.card_error:
                return "opening", ""
            return "unavailable", (self.card_error if self.card_fault == "would not open"
                                   else f"{self.card_fault}: {self.card_error}")
        stalled = card.stalled_for()
        if card.stalled():
            return "stalled", (f"does not answer: a write to it has not returned for {stalled:.0f} s, and nothing more "
                               f"is recorded on it until it does — check or replace the card")
        if card.err is not None:
            return "failing", f"refused a write: {card.err}"
        if self.card_refusal and not card.appended:
            return "recording", f"refused a write: {self.card_refusal}; opened again, nothing written to it since"
        return "recording", ""

    # What a camera's recorder says: its place, the card, and the camera's frames. None of the engine's fields — no
    # `archive` (nothing for a console to offer to declare), no quota of a ring, no door — and no writer watch but
    # one: a STALLED card is `writer: stuck`, what waits for it and for how long, so the console's `rec_writer` and its
    # volume page say it as they say a server's writer that stopped landing (the seventh review). Nothing here waits
    # for the card: its counters are read under its own lock, which no I/O holds (`CardBuffer._io`).
    def heartbeat_extra(self) -> dict:
        state, error = self._card_said()
        card = {"state": state, "tries": self.card_tries, "since": self.card_since}
        if self.card is not None:
            segs, size, budget = self.card.stats()
            card.update(segments=segs, bytes=size, budget=budget)
        if self.evicted_s():
            card["evicted_s"] = self.evicted_s()             # let go of before the server had it (`CardBuffer.owed`)
        if error:
            card["error"] = error
        if getattr(self.actuator, "failures", 0):
            card["failures"] = self.actuator.failures        # writes the card refused, since this process started
        stuck = {}
        if state == "stalled":
            card["stalled_s"] = round(self.card.stalled_for(), 1)
            stuck = {"writer": {"state": "stuck", "outstanding": getattr(self.actuator, "queued", 0),
                                "still": card["stalled_s"]}}
        # `archive` empty: a worker's is its events tree, and under `rec/` the console reads it as the box's own volume
        # and offers to declare it (`volumes.suggest`) — a camera has no volume of the engine to offer.
        stream = self._stream()                              # the pusher's word on the stream (`stream_said`)
        return {**VmsWorker.heartbeat_extra(self), "archive": "", "volume": self.volume,
                "volume_error": self.volume_error if self.card is None else f"the card {error}" if error else "",
                "card": card,
                "feed": self.ring.status(self.wall()), **stuck, **({"stream": stream} if stream is not None else {})}

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
