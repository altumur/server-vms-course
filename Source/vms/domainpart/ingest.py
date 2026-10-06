"""Lesson 16 — a camera nobody can reach.

Lesson 10 made every connection between a member and the DOMAIN the member's (`uplink.py`). The media are
next. A server room's recorder pulled the camera's stream from its door (Lesson 13), and the live gateway
did the same (Lesson 3). A camera behind a NAT, on a cellular link, or recorded by a cluster in another
building or a rented region (Lesson 8) has no door anybody can open. So the camera pushes — and it pushes
recording and live the same way, because they are the same stream.

    the ingest   a job of the RECORDING cluster, on every server like the console, with a stable address it
                 announces in its cluster (`rec/ingest`). It takes streams the cameras push, keyed by the
                 domain's name for the camera, and hands each to whoever in its cluster wants it: the
                 recorder, to write; the gateway, to show. The fan-out that lived on the camera's worker
                 (М10B Lesson 9) moves off the camera, into the cluster that consumes it
    where        the camera learns where to push from its book of primaries (Lesson 13, point V): the domain
                 adds the recording cluster's ingest addresses and a STREAM TOKEN. The token is the domain
                 signer's, like every token in this module (Lesson 4): audience the ingest of that cluster,
                 for that camera, with an expiry. The ingest checks it with the key set its own agent
                 carried — no secret is shared, and none is invented. The domain re-issues it only past its
                 half-life, so the book on the camera's flash changes a few times a day, not every pass
    when         the camera keeps ONE long poll open to the ingest — "is there work for me?" — and pushes
                 while anybody wants the stream: a recorder holding an always-recording (it wants it for
                 ever, so the camera pushes for ever), a recorder inside an event's window, a viewer. The
                 same poll asks for RANGES off the card: backfill, and playback of what only the card holds,
                 turn into uploads the camera makes on request — "the recorder asks, the camera pushes"
    who writes   still the recorder, under its epoch (М10B). Nothing here changes who writes or what fences:
                 a camera pushes to the ingest the book names; a zombie recorder simply receives nothing

Every connection is still the camera's: the agent's pass (books down, report up — seconds to half a minute),
the long poll (work — about a second), the push (media — continuous). The camera's own page stays, for the
operator on site; it is not the way live video reaches anybody else.

What the product found running it on a box (feedback AC–AG), all of it here:

    clocks       a frame carries the time it was CAPTURED, on the camera's clock — MPEG-TS over SRT has no
                 wall time of its own. The ingest moves it onto the cluster's clock by the difference the
                 camera states in its requests — held, not measured anew each time (`OFFSET_HOLD`; the camera's
                 clock is on a line steps do not move, `vms.card.CamLine`) — and moves a range request back
                 onto the camera's. Stamped by
                 arrival instead, the seam with backfill is off by the clock difference, and a ring flushed at
                 an event's start collapses into one instant (AC)
    the ring     lives on the CAMERA: while nobody wants the stream it keeps the last seconds, and the first
                 push after "push now" starts with them, marked — the start of an event is not lost to the
                 time the want took to arrive (AC). A viewer gets the live edge, never the ring (AF)
    ranges       a range off the card is the ANSWER to a request, by its id — samples with their own times —
                 not a stream: the recorder asks for a minute, gets that minute or nothing (AD). The card is the
                 camera's buffer, not an archive engine's volume (`vms/card.py`; the product's camera has no
                 obsd): a camera with no card, or a card that could not read the range, answers RANGE FAILED —
                 the copy fails and is asked again later, never taken for "not on the card" (feedback DG, DH).
                 The request NAMES the recording on the card; the answer comes up in PIECES of bytes the camera
                 can hold (`vms.card.PIECE_BYTES`), the recorder waits for each piece as long as a piece of that
                 size takes, and the ingest forgets an answer the moment it has handed it over (the sixth review).
                 The camera sends a piece's worth a pass, beside its stream, and a piece it had no answer for goes
                 again under its own number — the ingest takes the repeat as a repeat (the seventh review)
    frames       two forms, each for its road, and ONE place that turns the one into the other. The card's frame
                 is a sample record (`vms.obsd.Sample`: archive ms, the key flag, the body) — as it lies
                 on the card and as it travels in a range's answer, never re-made. The PUSH's frame, in this
                 module, is a dict with `t` (when it was captured, the camera's clock) and `key`. A break
                 continued off the card puts card frames into the push, and the PUSHER makes them push frames
                 (`wire`): it is the only one that holds both. The record rides inside (`sample`), untouched
    the poll     answers at once the first time (a camera that has never polled has version -1), is held
                 while nothing changed, and wakes when a want runs out — a viewer's LINGER included (AF), timed
                 to the lapse itself, since nobody touches anything then (AH)
    one cluster  the book lists every ingest of the recording cluster; the camera pushes to the first that
                 answers, and the recorder may be on another server. Ingests of one cluster pass streams to
                 each other: a want at any of them is a want at all, and the one the camera pushes to pushes on
                 to a peer that has a subscriber (`PeerLink`) — a stream, cut clean to a keyframe when the peer
                 falls behind, never a viewer's leaky queue: a recorder is behind it (AG, AJ)
    a break      a camera that was PUSHING and lost its road continues the stream when the road comes back,
                 instead of leaving the break to the card and to backfill (feedback CB). Every poll answer
                 carries `have`: how far this cluster's recorder WROTE the camera — on the camera's clock,
                 from the recorder's own word in its heartbeat (`written_through`), not from what this
                 ingest received: frames a recorder's queue dropped must be sent again, and a camera that
                 comes back to ANOTHER ingest of the cluster, or to one that restarted, must still be told.
                 The camera starts its next push at the first keyframe after `have` — out of its memory (the
                 camera's ring), off its card for what memory no longer holds — and nothing the recorder has
                 goes twice; the ingest drops what is not newer than `have`. Backfill is for minutes and hours
                 (it plans nothing fresher than its settle); a break of seconds is the stream's own business —
                 and only seconds: the stream reaches back `hold_seconds`, goes ahead of the live edge a piece a
                 pass, and leaves what is older to backfill, saying how much (the seventh review)
    asks         a scenario between cameras — "vehicle at the gate: yard camera to preset 3" (Lesson 12) — is
                 worth something NOW. Neither camera can be reached; both keep a long poll open. So the camera
                 whose event fired leaves the ask at the ingest of the cluster that records the target — the
                 domain put that address, and a token to ask, in its book (`domain/asks`) — and the target gets
                 it in the answer to its poll, which the new ask wakes: about a second, not an agent's pass.
                 An ask carries a deadline and dies at it, answered "expired": unlike an edit it is never kept

In the tests the "network" is a function from an address to an `Ingest`, called by the camera only: the
camera dials out, nobody dials in. The real ingest speaks SRT (the camera calls, the ingest listens; the
stream id names the camera) and the long poll is an HTTP request held for up to half a minute — Track 2.
"""
from __future__ import annotations

import collections
import dataclasses
import json
import logging
import secrets
import threading
import time
from dataclasses import dataclass, field

from vms.card import PIECE_BYTES       # what one piece of a camera's card may weigh: a share of the camera's memory
from vms.card import RING_BYTES        # …and the camera's ring: what a pusher with no camera ring keeps at most
from vms.card import CamLine           # …and the camera's line of time, which steps of its clock do not move
from vms.card import RING_AHEAD        # …and how much later than the camera's clock its frame may lie on its line
from vms.obsd import archive_ms, unix_s

from w2cplatform.rows import FIELDS, PARSE_ERRORS, Table, finite

from w2cplatform.domain.federation import Unreachable, published
from .gateway import Forbidden, LeakyQueue, LiveTee
from w2cplatform.trust.tokens import TokenError, kid_of, verify

log = logging.getLogger("ingest")

INGEST = "rec/ingest"                  # the recording cluster's announcement: {"cluster", "urls", "ts"}
# `/<ingest>`: when each member last polled here, as ages — {"cluster", "ingest", "ts", "units": {<member>: seconds}};
# the rec spec's witness (`domain.witness`)
POLLED = "rec/polled"
FORWARDED = "rec/forwarded"            # `/<forwarder>`: what a relay's forwarder dropped, per camera (`chain.Forwarder.publish`)
LINGER = 10.0                          # how long a stream nobody wants any more keeps being asked for
# Asks (step 8). An outcome is kept this long for the asker to read — the product's automation remembers
# what it fired for as long (autoworker REMEMBER) — and then forgotten: an ingest's memory is not a log.
REMEMBER = 900.0
PEER_BUFFER = 50                       # frames one ingest holds for a peer that is not keeping up: two seconds (AJ)
MAX_LIVE_ASKS = 16                     # live asks one asking camera may hold at one ingest: a ceiling, not a queue
# How far ahead an ask's deadline may be, from when it arrives (the review's eighth pass; the product found `within`
# had no upper bound): an ask is "do it now", and the product's commands live up to 600 s (`valid_until`). One kept
# for a year was one more live ask for a year, against the ceiling above.
ASK_DEADLINE_MAX = 600.0
# What became of one asker's asks, kept per target camera (the ninth review, a minor: a deadline already past was taken —
# never counted as live, expired at the next touch — and its outcome kept for `REMEMBER`: 20 000 of them, and every ask
# swept them all, 27.5 s of the ingest's CPU). A deadline that has passed is refused now, and of each asker's outcomes at
# a camera the last `OUTCOMES_KEPT` are kept — the oldest forgotten first, as a reader past `REMEMBER` finds it gone.
OUTCOMES_KEPT = 4 * MAX_LIVE_ASKS
ANSWER_GRACE = 5.0                     # past the deadline by this, an ask nobody knows of is lost, not late
# A RANGE IS WAITED FOR A PIECE AT A TIME (the sixth review). The recorder waited one fixed number for the whole
# answer, whatever it weighed: a camera that answered in 1.2 s to a wait of 1 failed four requests out of four, and
# read its card four times for it. The answer comes in pieces of at most `PIECE_BYTES`, so the wait is for the NEXT
# piece, and it is what a piece of that size takes: the camera's poll coming round and the card being read
# (`POLL_ROUND`), and the piece itself over the slowest uplink a range is served on at all (`UPLINK_FLOOR`, the pace
# the console's export holds a download to). A megabyte: 21 s. A camera that keeps sending is waited for; one that
# sent nothing for that long has failed the range.
POLL_ROUND = 5.0
UPLINK_FLOOR = 64 << 10                # bytes a second
# What the ingest keeps of a range nobody came for (the sixth review: it kept every answer, for good — twenty requests,
# twenty answers and 19 MiB; a day of backfill took the ingest of every camera down). An answer is deleted when it is
# handed over; one nobody collected — its recorder gave up, or died — goes after `ANSWER_KEPT`; and of what landed,
# only the last `LANDED_KEPT` ranges are remembered.
ANSWER_KEPT = 60.0
LANDED_KEPT = 64
# A FRAME FROM THE FUTURE IS NOT A FRAME (the ninth review, major). A subscriber is given only what is newer than the last
# frame it was given (`_InOrder`), and one frame stamped `t = 1e300` — or `"1e400"` — was the last frame for ever: 250 of
# 250 frames after it dropped as repeats until the recorder subscribed anew, seen only in `repeats`. A camera's frame is
# moved onto this cluster's clock by the offset stated in the SAME request (`_check`), and it was captured before that
# request was sent: on this clock it cannot be later than now by more than the request's own travel. A frame a peer or
# this cluster's forwarder hands on is on a clock of the same cluster, or of the one above, set by NTP. So a frame later
# than this ingest's clock by more than `FRAME_AHEAD` — or whose time is not a finite number — is refused, counted per
# camera (`ahead`, under `lost`), logged once, and given to nobody: it never becomes anybody's last frame.
FRAME_AHEAD = 60.0
# THE CAMERA'S OFFSET IS HELD (the product's feedback DU, and the tenth review's blocker with it). It was measured anew on
# every request — `wall - camera_now`, a request's travel in it — so two requests a second apart put the camera's frames
# on this clock by offsets a few milliseconds apart: the first frame of a request landed a millisecond BEFORE the last
# frame written (the engine refuses it: INCONSISTENT_SEQUENCE_TIMESTAMP — the product lost lead-in frames 131–149 on a
# real obsd) or twelve after it (a hole). The camera keeps its clock on a line that steps do not move (`vms.card.CamLine`),
# so the offset does not move either, but for a request's travel: it is held, and moves only when a request says it is off
# by more than `OFFSET_HOLD` — the product's `OffsetHold`. DOWN whenever a request says so (the camera's clock further
# ahead: no request arrives before it was sent, so that is never travel); UP — the camera's clock further behind — only
# when it is more than `CLOCK_STEP` (no request travels that long) or every request for `OFFSET_RISE` said so: one request
# that took a second on a cellular uplink is not the camera's clock. Every move is counted (`clock_steps`) and logged:
# with the camera's line kept (on its card too), it is this cluster's own clock stepped, a first request that travelled
# long, or a clock that drifts with nobody setting it.
#
# …AND A MOVE DOWN IS TAKEN BY THE FRAMES, NOT AT ONCE (the eleventh review, major: "a move down at once sends the next
# frames to `repeats`"). Taken at once, the frames after it landed up to the move earlier than the frames before it, and
# every subscriber dropped them as not newer than its last: a camera clock 0.5 % fast lost 4 frames at every move — one
# every 50 s — and a first request that travelled T seconds (TLS, a cold uplink) lost T seconds of frames when a quick one
# followed. Now a move down of up to `CLOCK_STEP` is a TARGET the open stream slews to (`_slewed`): each frame newer than
# the newest one the camera pushed takes the offset down by at most `OFFSET_SLEW` of its distance from that one — the
# frames come half as far apart until the offset is there, never one behind another, never one lost. A move up leaves a
# gap and loses nothing, and a move of more than `CLOCK_STEP` either way is a step of somebody's clock, taken at once.
#
# …AND A REQUEST'S TRAVEL IS NEVER A STEP, HOWEVER LONG (the product's DZ, checked in the course and measured: one push
# that took 5.5 s on its way — a stalled uplink, a retransmission — was a move UP past `CLOCK_STEP`, taken at once; its
# frames landed 5.5 s late, the next quick request took the offset back down at once, and the next 5.5 s of frames were
# not newer than `have`: 54 of 1800 frames dropped with nothing counted, 2 `clock_steps`; 40 s on its way, 399). Travel
# only ever RAISES what a request says, and the camera's clock is on its line, which steps do not move: a rise is this
# cluster's own clock stepped forward, a camera clock that runs slow, or a camera with no RTC that rebooted with its
# clock unset (its line goes on right after the card's newest frame) — never the camera's step. So a rise up to
# `CLOCK_STEP` waits until every request for `OFFSET_RISE`, at least `RISE_REQUESTS` of them, said so — the least of
# them — and one request inside the hold withdraws it. A rise past `CLOCK_STEP` is taken at once but PROVISIONALLY (the
# product's rule; `provisional`): `RISE_REQUESTS` requests agreeing make it a step, firm and counted — a reboot of ten or
# sixty seconds puts its frames where they were captured, as before this pass — and the next request back on the old
# clock withdraws it by the frames, slewed (`_slewed`), uncounted: a push of 5.5–40 s puts its frames at most its travel
# late, for about twice its travel, and loses none (measured, the table in lesson 16). A move DOWN past
# `CLOCK_STEP` was still taken at once from an offset held firm (`_firm`: the requests of `OFFSET_RISE`, at least
# `RISE_REQUESTS`, agreed with it); from one not held firm — a first pass whose requests all travelled eight seconds put
# its frames eight seconds late, and the jump down from there dropped the next eight — it is slewed (`_slewed`), as a
# small one is; and since the twelfth review from a firm one too (below).
#
# …AND A PLATEAU OF TRAVEL IS NOT A STEP EITHER (the twelfth review, blocker 13, its probe `pz4_road SC=bloat`: every
# request of twenty seconds travelled eight — a full drop-tail buffer — so three requests agreed with the provisional
# rise, it became a step, and the first quick request after the plateau jumped the offset down at once: 79 frames to
# `repeats`, 59 for six seconds over a minute). Three requests that agree prove nothing when each of them travelled as
# long as the rise. So the camera says, with every request, how long its last request took there and back on its own
# line (`rtt`: a request's travel one way is never longer than its round trip), and the ingest counts a request for a
# rise only when the rise is longer than that round trip by more than the bound it is held to — `CLOCK_STEP` for a
# provisional rise, `OFFSET_HOLD` for a small one; a request its round trip explains neither confirms a rise nor
# withdraws it. A camera rebooted with its clock unset says a round trip of milliseconds and a rise of the reboot's
# length: a step, as before. And a move down past `CLOCK_STEP` is never a jump now, from a firm offset too: a target
# taken at once by the first frame that leaps with it (a clock set, `leap`), slewed by the frames otherwise. What stays:
# a camera that states no round trip (one of an older build) is held as before this pass.
#
# …AND A RANGE IS TOLD ONLY BY A FIRM OFFSET (the twelfth review, blocker 11). A range is told the camera on its own
# clock, by the offset it is first told by, and goes back by the same (`told_by`, below). That offset was whatever the
# held one was at the moment: a provisional rise (a slow poll carried the range: its frames read six or eight seconds
# away from the hole), the middle of a slew (a range told by 5.0 while the stream slewed from 10 to 0), or a long poll
# held at the ingest — every wake measured the offset again by the `camera_now` the poll was sent with, so the hold
# itself read as the request's travel (held 7 s: told by 5.0; 12 s: by 10.02). Now a range, `have` and an ask's
# deadline are told by the FIRM offset (`_told`): the target while the stream slews to it, none while a rise is
# provisional — a range waits then, untold, for the requests that decide it (`have` and a deadline go by the raised
# offset: earlier on the camera's clock, never later); a held poll's wake measures nothing; and a range told by an
# offset the requests after it showed to be one request's travel — a move down from an offset not held firm — fails,
# and backfill asks it again (`_untold`).
#
# …AND THE ROAD EXPLAINS ONLY WHAT ITS ROUND TRIP GREW BY, AND NEVER FOR GOOD (the thirteenth review, major 10, its probe
# `pq4_cluster_step_rtt`: this cluster's clock stepped 5.5 s, the camera's road a steady 0.6 s there and back — a rise of
# 5.5 that its round trip brought under `CLOCK_STEP` was neither a provisional rise nor a small one, and no request ever
# said anything else: 2125 frames 5.5 s early, nothing counted). Three such zones: a rise in (`CLOCK_STEP`, `CLOCK_STEP` +
# rtt], a small one in (`OFFSET_HOLD`, `OFFSET_HOLD` + rtt], and a provisional rise that requests agreed with only "as their
# round trip explains" — told nobody, for good. The offset held was measured over the same road, its travel in it: what
# can be travel in a rise is what the round trip GREW BY since the least the camera said (`rtt_least`; a plateau is a
# round trip grown by its whole length, a steady road grew by nothing). What the road leaves of a rise is the rise
# (`proven`): past `CLOCK_STEP` provisional at once; past `OFFSET_HOLD` a small rise, counted for `OFFSET_RISE` — the one
# past `CLOCK_STEP` that the road brings under it too; and a provisional rise agreed with by requests whose road leaves
# it under `CLOCK_STEP` is confirmed as a small one is, after `OFFSET_RISE`. A request agreeing with a provisional rise
# only as far as its round trip grew is a plateau the rise was: the rise is withdrawn then, not held to the plateau's end.
OFFSET_HOLD = 0.25
OFFSET_RISE = 30.0
RISE_REQUESTS = 3
CLOCK_STEP = 5.0
OFFSET_SLEW = 0.5
# A CAMERA'S OWN FRAME IS HELD TIGHTER (the tenth review, major). Held to `FRAME_AHEAD`, a frame of now+59 passed, became
# the recorder's last frame (`_InOrder`), and the next 59 s of the camera's frames were dropped as repeats. A camera's
# frame lies on its line of time no later than its clock by `RING_AHEAD` (`vms.card.CamLine` keeps one further ahead
# right after the frame before), and is put on this clock by the camera's held offset, which no request finds more than
# `OFFSET_HOLD` too high: later than now by more than both, it is refused. A frame a peer or this cluster's forwarder
# hands on is on another machine's clock: `FRAME_AHEAD` for it. And at every door the tee takes a frame further past a
# subscriber's last than `STREAM_JUMP` as the stream's only when the frame after it follows it (`_InOrder`): one frame
# of now+9 did what one of now+59 did, inside every bound.
CAMERA_AHEAD = RING_AHEAD + OFFSET_HOLD
STREAM_JUMP = 2.0


# ONE ENTRY OF A BOOK THAT DOES NOT PARSE IS THAT ENTRY'S TROUBLE (the eighth review's sibling, left here by the М12
# pass: the camera's books, the relay's carried books and this cluster's rec snapshots were read bare). A camera's entry
# in the book of primaries, a relay's entry of its upstream book or its book of asks, one shard of the rec snapshot: one
# that does not parse raised out of the camera's whole pass, the forwarder's, every poll at the ingest. Now it is skipped,
# counted once until it parses again (`BOOKS`), logged once — and the entry read last of it is kept where there is one:
# a camera does not stop pushing because its book was torn in the middle of a write.
BOOKS = Table("book_entry", "skipped — the rest of the book is read", "book entry")


def _an_object(v) -> dict:
    if not isinstance(v, dict):
        raise TypeError(f"not an object: {type(v).__name__}")
    return v


def _a_road(road) -> None:
    """A road of a book: its ingest's `urls` (a list of addresses) and a `token`."""
    if not isinstance(road, dict) or not isinstance(road.get("urls"), list) \
            or not all(isinstance(u, str) for u in road["urls"]) or not isinstance(road.get("token_secret"), str):
        raise TypeError("a road is its urls and its token")


def _a_primary(e) -> dict:
    """A camera's entry in the book of primaries: the cluster that records it (`recorded_by`), and — when it pushes —
    the road to its ingest, and the backup's when it has one."""
    if not isinstance(e, dict):
        raise TypeError(f"not an object: {type(e).__name__}")
    if e.get("ingest"):
        _a_road(e["ingest"])
    if e.get("backup"):
        if not isinstance(e["backup"], dict):
            raise TypeError("its backup is not an object")
        _a_road(e["backup"].get("ingest"))
    return e


def piece_wait(piece: int = PIECE_BYTES) -> float:
    """How long the next piece of a range is waited for: the poll's round, and `piece` bytes at the uplink's floor."""
    return POLL_ROUND + piece / UPLINK_FLOOR


class Refused(Exception):
    """A push or a poll the ingest will not take: no token, the wrong camera, the wrong cluster, expired."""


class RangeFailed(OSError):
    """The camera could not read a range it was asked for — its card is not open, a segment read short — or did not
    answer in time. An ERROR, not an answer about the card: the recorder's copy fails and backfill asks again later
    (the product's `X-Range-Failed`). An empty answer would say "not on the card" and never be asked again."""


def audience(cluster: str) -> str:
    return f"ingest:{cluster}"


def _is_ring(frame) -> bool:
    return isinstance(frame, dict) and bool(frame.get("ring"))


def _is_sample(frame) -> bool:
    return dataclasses.is_dataclass(frame) and hasattr(frame, "begin")


def _shift(frames: list, by: float) -> list:
    """Frames that carry a capture time (`t`, the camera's clock) moved onto the cluster's; others as they are.
    A sample record off a camera's card (`vms.obsd.Sample`, archive ms) is moved the same way — on its own,
    in a range's answer, and inside a push frame made of it (`wire`)."""
    if not by:
        return list(frames)
    ms = int(round(by * 1000))

    def moved(s):
        return dataclasses.replace(s, begin=s.begin + ms, end=s.end + ms)
    return [dict(f, t=float(f["t"]) + by, **({"sample": moved(f["sample"])} if _is_sample(f.get("sample")) else {}))
            if isinstance(f, dict) and "t" in f else
            moved(f) if _is_sample(f) else
            f for f in frames]


# THE ONE PLACE A CARD'S FRAME BECOMES A PUSH'S (the sixth review: "which is the card's contract for the pusher —
# `Sample` or `dict` — and who turns the one into the other?"). The card's is `Sample`, and a range's answer carries
# it as it is. The push's is a dict with `t` and `key`. They met in one place — a break continued off the card — and
# nobody turned anything: the continuation kept `isinstance(f, dict)`, the card gave `Sample`, and every frame read
# off the card was thrown away. The PUSHER turns it, here, because it alone holds both; the record itself goes along
# as `sample`, for the recorder to write as it is.
def wire(sample, **marks) -> dict:
    """A sample record off the card as a frame of the push: its capture time on the camera's clock, its key flag,
    and the record itself."""
    return {"t": unix_s(sample.begin), "key": bool(sample.key), "sample": sample, **marks}


@dataclass
class _Camera:
    wants: dict[str, float] = field(default_factory=dict)        # who wants the stream -> until when (inf: for ever)
    # Requested uploads, by id: `(t0, t1, recording)` — the CLUSTER's clock, and the recording on the card (None: the
    # camera's one). An answer on its way is `parts` — `(pieces so far, samples, when the last piece came)`; whole, it
    # is `answers`, with when it landed; `failed` is why the camera could not read it. All three go when the range is
    # handed over (`result`), and after `ANSWER_KEPT` if nobody came (`_forget`).
    ranges: dict[str, tuple] = field(default_factory=dict)
    told_by: dict[str, float] = field(default_factory=dict)      # …the offset each was first told the camera by (`upload`)
    parts: dict[str, tuple] = field(default_factory=dict)
    answers: dict[str, tuple] = field(default_factory=dict)
    failed: dict[str, tuple] = field(default_factory=dict)
    landed: list[tuple[float, float]] = field(default_factory=list)
    pushed_at: float | None = None
    offset: float = 0.0                                          # the cluster's clock minus the camera's, held (`OFFSET_HOLD`)
    told: bool = False                                           # …and the camera has stated its clock at least once
    rise: tuple | None = None                                    # …requests that put it higher: since when, the least, how many
    agreed: tuple = (0.0, 0)                                     # …requests that agreed with it: since when, how many (`_firm`)
    target: float | None = None                                  # …a lower offset the open stream slews to (`_slewed`)
    leap: bool = False                                           # …further down than `CLOCK_STEP`: a leap of the frames takes it
    provisional: float | None = None                             # …a rise past `CLOCK_STEP` taken at once: the offset before it
    slow: bool = False                                           # …and a request its road takes under `CLOCK_STEP` agreed
    rtt_least: float | None = None                               # the least round trip the camera said (`_offset`)
    newest: float | None = None                                  # the newest frame it pushed, on its own clock
    clock_steps: int = 0                                         # times the held offset moved
    asks: dict[str, dict] = field(default_factory=dict)          # asks for this camera: {id: {action, deadline, by}}
    outcomes: dict[str, tuple] = field(default_factory=dict)     # what became of each, when, and whose ask: (outcome, at, by)
    version: int = 0
    said: tuple | None = None                                    # what the last poll was told
    polled_at: float | None = None                               # when it last polled, on the cluster's clock
    polled_by: str | None = None                                 # …the member that did: its stream token's subject


class Ingest:
    """The recording cluster's receiver. `keys()` is the key set THIS cluster's agent carried (`ClusterTrust`).
    `peers()` are the other ingests of the same cluster (AG) — on a real cluster, found through its store."""

    def __init__(self, cluster: str, urls: list[str], keys, revoked=lambda: set(), wall=time.time,
                 name: str | None = None, peers=lambda: [], should=None, written=None):
        """`should(ref) -> bool | None`: whether THIS cluster should be recording the camera now — from its own
        rec rows (`should_from_snapshot`). Given it, every poll also says whether the recording is UNCOVERED:
        it should be written and no recorder here takes the stream. The camera needs no domain to know that its
        primary does not take its stream (М11 lesson 1)."""
        self.cluster, self.urls, self.keys, self.revoked, self.wall = cluster, list(urls), keys, revoked, wall
        self.name, self.peers, self.should = name or (urls[0] if urls else cluster), peers, should
        # `written(ref) -> float | None`: how far this cluster's recorder WROTE the camera, on the cluster's clock
        # (`written_from_heartbeats`) — the `have` every poll answer carries (feedback CB).
        self.written = written
        # …and how far the cluster ABOVE wrote it, as its ingest told this cluster's forwarder (`Forwarder`; the product's
        # DY): with a relay, the camera's `have` is the lesser of the two (`_have`), and its card holds until both have it.
        self.up_have: dict[str, float] = {}
        # A recorder that lets go of a camera — or dies — wakes nobody: nothing here changes. So a held poll that
        # has a word to say about coverage looks again at least this often (feedback AP: the product does 5 s).
        self.recheck = 5.0
        self.linger = LINGER
        self.links: dict[tuple[str, str], PeerLink] = {}          # (peer, camera) -> the stream this ingest pushes it (AJ)
        self.pulled: dict[tuple[str, str], tuple[int, list]] = {}  # (camera, puller) -> the last batch pulled, numbered
        # NUMBERS THAT OUTLIVE THIS PROCESS ARE NOT COMPARED WITH ITS OWN (the eighth review, blocker 2). A pull's batch is
        # numbered from nought in memory, and the relay says the number it last got: after the centre restarted, the
        # relay's "2" from before met the new count at 2, two answers after the restart lost on the way down — and frames
        # 3 and 4 were taken for delivered, and lost uncounted. A batch is numbered `(boot, n)` now: `boot` is this
        # process's, and a number from another boot never matches — the last batch goes again (`pull`). The poll's
        # `version` is the same kind of number, told to a camera that may come back to another ingest of its road, or to
        # this one restarted: it starts at a number of this boot's (`_v0`), so a version from elsewhere is not "nothing
        # changed" — it is an answer at once.
        self.boot = secrets.token_hex(4)
        self._v0 = secrets.randbelow(1 << 40)
        self.tees: dict[tuple[str, str], "_InOrder"] = {}
        self.cams: dict[str, _Camera] = {}
        self.ahead: dict[str, int] = {}                           # per camera: frames refused for a time from the future
        # Asks going UP (Lesson 17): left here by a camera that sees only this relay, for a camera elsewhere;
        # this relay's forwarder takes them to the centre. {id: {target, action, deadline, by, lifted}}
        self.up: dict[str, dict] = {}
        # Held polls, for real: whatever could change an answer bumps the generation and wakes every waiter;
        # listeners — this cluster's forwarder — are told too. That is what "by event" is made of.
        self._cond, self._gen, self._listeners = threading.Condition(), 0, []

    def listen(self, fn) -> None:
        """`fn()` is called whenever something here may have changed an answer: a want, a range, an ask, an
        outcome. The forwarder listens, so an ask going up leaves at once and an outcome coming back goes on."""
        self._listeners.append(fn)

    def _changed(self) -> None:
        for ing in self._cluster():
            with ing._cond:
                ing._gen += 1
                ing._cond.notify_all()
            for fn in list(ing._listeners):
                fn()

    def _wait(self, gen: int, until: float) -> bool:
        with self._cond:
            return self._cond.wait_for(lambda: self._gen != gen, timeout=max(0.0, until - time.monotonic()))

    def announce(self, objects) -> None:
        """Where cameras push to — in this cluster's own store, where the domain (or this cluster's report) reads it."""
        objects.put(INGEST, json.dumps({"cluster": self.cluster, "urls": self.urls, "ts": self.wall()}).encode())

    # When each camera last polled — the domain's witness that a camera is alive when its agent is not reporting
    # (Lesson 14): the poll is kept by the camera's pusher, another process than its agent. Ages, not times, so
    # the domain reads them against the object's own `ts` and a clock difference cancels out. Named by the MEMBER that
    # polled — its stream token's subject, the camera's home (the rec spec's `witness.member_field`): the domain
    # matches a silent member by its own name (ADR-0010), and a camera that is a member, `cam-SN0`, is no longer `SN0`.
    # One object per INGEST, not per cluster (feedback AZ): a cluster runs several (Lesson 16, step 7), each knows only
    # the cameras that poll it, and one shared object would be whichever wrote last.
    #
    # …and what this ingest did NOT hand on, per camera (the eighth review's sibling, from the product: a recorder's full
    # queue refused frames and nobody counted it). A subscriber's queue that overflowed drops its oldest frames
    # (`LeakyQueue.dropped`), a peer that fell behind is cut clean (`PeerLink.dropped`), and repeats are not handed on at
    # all (`_InOrder.repeats`): all three, when not nought, under `lost`.
    def publish_polled(self, objects) -> dict:
        now, cams = self.wall(), {}
        for c in list(self.cams.values()):
            if c.polled_at is not None and c.polled_by:
                age = round(now - c.polled_at, 3)
                cams[c.polled_by] = min(age, cams.get(c.polled_by, age))    # a member's freshest poll
        key = f"{POLLED}/" + "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in self.name)
        steps = {ref: c.clock_steps for ref, c in list(self.cams.items()) if c.clock_steps}
        objects.put(key, json.dumps({"cluster": self.cluster, "ingest": self.name, "ts": now, "units": cams,
                                     **({"lost": lost} if (lost := self.lost()) else {}),
                                     **({"clock_steps": steps} if steps else {})}).encode())
        return cams

    def lost(self) -> dict[str, dict]:
        """Per camera, what this ingest did not hand on: `{"dropped": {subscriber: n}, "peers": {peer: n}, "repeats": n}`,
        only what is not nought."""
        out: dict[str, dict] = {}
        for (ref, _kind), tee in list(self.tees.items()):
            for who, q in list(tee.subscribers.items()):
                if getattr(q, "dropped", 0):
                    out.setdefault(ref, {}).setdefault("dropped", {})[who] = q.dropped
            if getattr(tee, "repeats", 0):
                e = out.setdefault(ref, {})
                e["repeats"] = e.get("repeats", 0) + tee.repeats
            if getattr(tee, "ahead", 0):                         # one frame far past the stream, dropped (`_InOrder`)
                e = out.setdefault(ref, {})
                e["ahead"] = e.get("ahead", 0) + tee.ahead
        for (peer, ref), link in list(self.links.items()):
            if link.dropped:
                out.setdefault(ref, {}).setdefault("peers", {})[peer] = link.dropped
        for ref, n in list(self.ahead.items()):
            e = out.setdefault(ref, {})
            e["ahead"] = e.get("ahead", 0) + n
        return out

    def _cam(self, ref) -> _Camera:
        cam = self.cams.get(str(ref))
        if cam is None:
            cam = self.cams.setdefault(str(ref), _Camera(version=self._v0))   # versions of this boot's own (`boot`)
        return cam

    def _cluster(self) -> list["Ingest"]:
        return [self, *[p for p in self.peers() if p is not self]]

    # -- the camera's side of the conversation ----------------------------------------------------------
    def _check(self, token: str, ref: str, camera_now: float | None = None, rtt: float | None = None) -> dict:
        ks = self._keys()
        if ks is None:
            raise Refused(f"{self.cluster}: no key set yet — is this cluster's agent running?")
        try:
            p = verify(token, ks, self.revoked(), now=self.wall(), kind="stream")
        except TokenError as e:
            raise Refused(f"stream token refused: {e}")
        if p.get("aud") != audience(self.cluster) or str(p.get("ref")) != str(ref):
            raise Refused(f"stream token is for {p.get('ref')} at {p.get('aud')}, not {ref} at {audience(self.cluster)}")
        if camera_now is not None:                               # every request says what time the camera thinks it is
            self._offset(ref, self._cam(ref), self.wall(), self.wall() - _finite_clock(camera_now), _round_trip(rtt))
        return p

    def _offset(self, ref: str, cam: _Camera, now: float, offset: float, rtt: float | None = None) -> None:
        """The camera's offset, held: moved by what one request says only past `OFFSET_HOLD` — down by the frames (a
        target the stream slews to; past `CLOCK_STEP` a leap the frames take at once when they leap with it), up when
        every request for `OFFSET_RISE`, `RISE_REQUESTS` at least, said so — past `CLOCK_STEP` at once, provisionally,
        until the requests after it confirm or withdraw it (above, `OFFSET_HOLD`; DZ). A request whose round trip
        (`rtt`, the camera's word) explains its rise counts for none (the twelfth review). While it slews, the offset
        held is where it goes (`target`)."""
        held = cam.target if cam.target is not None else cam.offset
        if rtt is not None:
            cam.rtt_least = rtt if cam.rtt_least is None else min(cam.rtt_least, rtt)

        def proven(rise: float) -> float:                        # the least a rise can be: the road's travel taken out
            return rise if rtt is None else rise - max(0.0, rtt - cam.rtt_least)
        if not cam.told:
            cam.offset, cam.told, cam.agreed = offset, True, (now, 1)
        elif offset < held - OFFSET_HOLD and cam.provisional is not None:
            # Back on the old clock: the rise was a request's travel. Withdrawn — to the offset held before it, not this
            # request's own word (its travel in it would put the next frame a few milliseconds before the last) — by the
            # frames, slewed, nothing lost, or at once when no frame was put by it; neither is a step of anybody's clock,
            # and neither is counted.
            log.info("camera %s: a request travelled %.1f s; the offset it raised goes back", ref, held - offset)
            self._withdraw(cam, now)
        elif offset < held - OFFSET_HOLD:
            firm = self._firm(cam, now)
            if cam.newest is None:
                self._moved(ref, cam, offset)                    # no frame put by it yet: nothing to slew
            else:
                # Down by the frames, from a firm offset too (the twelfth review, blocker 13): past `CLOCK_STEP` it is a
                # leap the first frame that leaps with it takes at once (a clock set), and slewed otherwise — the end of
                # a plateau of travel that was taken for a step jumped down at once and sent its travel's worth of frames
                # to `repeats`.
                cam.clock_steps += 1
                log.info("camera %s: its clock is %.3f s further ahead of this cluster's than its frames are put by: the "
                         "stream takes the new difference over its next frames", ref, held - offset)
                cam.target, cam.rise, cam.leap = offset, None, offset < held - CLOCK_STEP
            if not firm:
                self._untold(ref, offset, now)                   # what it was held at was a request's travel
            cam.agreed = (now, 1)
        elif offset > held + CLOCK_STEP and proven(offset - held) > CLOCK_STEP:
            # A rise past `CLOCK_STEP`: taken at once, PROVISIONALLY (DZ, the product's rule): a camera that rebooted with
            # its clock unset goes on after the card's newest frame, its offset up by the reboot's length, and its frames
            # land where they were captured only by the new one. The requests after it say which it was: back on the old
            # clock withdraws it (above), `RISE_REQUESTS` agreeing make it a step, counted then. One whose road explains
            # it past `CLOCK_STEP` is a rise up to it (below; the twelfth and thirteenth reviews).
            if cam.provisional is None:
                cam.provisional = held
            cam.offset, cam.target, cam.leap, cam.newest, cam.rise = offset, None, False, None, None
            cam.agreed, cam.slow = (now, 1), False
        elif offset > held + OFFSET_HOLD:
            # A rise up to `CLOCK_STEP` — or past it, by no more than the road explains (the thirteenth review, major 10:
            # that one was nothing, for good): what the road leaves of it counts, past `OFFSET_HOLD`; a request whose road
            # explains it all — a plateau of travel — counts for none.
            if proven(offset - held) > OFFSET_HOLD:
                since, low, n = cam.rise or (now, offset, 0)
                cam.rise = (since, min(low, offset), n + 1)
                if now - since >= OFFSET_RISE and n + 1 >= RISE_REQUESTS:
                    self._moved(ref, cam, cam.rise[1])
                    cam.agreed = (since, n + 1)                  # every request of the window agreed with it: firm
        elif cam.provisional is not None and proven(cam.offset - cam.provisional) <= OFFSET_HOLD:
            # Agrees with a provisional rise only as far as its road grew: a plateau of travel the rise was (the
            # thirteenth review, a minor: held up while the plateau lasted, it put every frame of it as late — 654 frames
            # of a plateau of 6 s for a minute). Withdrawn, by the frames, as a request back on the old clock does.
            log.info("camera %s: its requests travel as long as the offset rose (%.1f s): the offset goes back", ref,
                     cam.offset - cam.provisional)
            self._withdraw(cam, now)
        else:
            cam.rise = None                                      # inside the hold: what was held stands
            cam.agreed = (cam.agreed[0], cam.agreed[1] + 1)
            if cam.provisional is not None and proven(cam.offset - cam.provisional) <= CLOCK_STEP:
                cam.slow = True                                  # …a rise its road takes under `CLOCK_STEP`: as a small one
            if cam.provisional is not None and cam.agreed[1] >= RISE_REQUESTS and \
                    (not cam.slow or now - cam.agreed[0] >= OFFSET_RISE):
                cam.clock_steps += 1                             # the requests after it agree: a step, not a request's travel
                log.warning("camera %s: its clock moved %.3f s against this cluster's (it rebooted with its clock unset, or "
                            "this cluster's clock stepped): its frames are put on this clock by the new difference",
                            ref, cam.provisional - cam.offset)
                cam.provisional, cam.slow = None, False
                cam.agreed = (float("-inf"), cam.agreed[1])     # firm: a step of a clock — the next one back is taken at once

    @staticmethod
    def _withdraw(cam: _Camera, now: float) -> None:
        """A provisional rise withdrawn: to the offset held before it — by the frames, slewed, or at once when no frame
        was put by it — uncounted."""
        if cam.newest is None:
            cam.offset, cam.target, cam.leap = cam.provisional, None, False
        else:
            cam.target, cam.leap = cam.provisional, False
        cam.provisional, cam.rise, cam.agreed, cam.slow = None, None, (now, 1), False

    @staticmethod
    def _firm(cam: _Camera, now: float) -> bool:
        """The offset held is the requests' word, not one request's travel: as many agreed with it, for as long, as a rise
        needs (`RISE_REQUESTS`, `OFFSET_RISE`)."""
        since, n = cam.agreed
        return n >= RISE_REQUESTS and now - since >= OFFSET_RISE

    @staticmethod
    def _told(cam: _Camera) -> float | None:
        """The offset a range is told the camera by (above, the twelfth review): the firm one — where the
        stream slews to while it slews — or None while a rise is provisional: nobody knows yet whether it was the camera's
        clock or one request's travel."""
        if cam.provisional is not None:
            return None
        return cam.target if cam.target is not None else cam.offset

    def _untold(self, ref: str, offset: float, now: float) -> None:
        """The offset held was one request's travel (a move down from an offset not held firm): a range told by it reads
        the card that far from the hole — failed, and asked again (the twelfth review)."""
        for ing in self._cluster():
            c = ing._cam(ref)
            for rid, by in list(c.told_by.items()):
                if rid in c.ranges and by > offset + OFFSET_HOLD:
                    c.ranges.pop(rid, None)
                    c.parts.pop(rid, None)
                    c.failed[rid] = (f"it was told the camera by its clock as a slow request had it ({by - offset:.1f} s "
                                     f"off): asked again", now)
                    log.info("camera %s: a range was told by an offset %.1f s off — one request's travel: failed, asked "
                             "again", ref, by - offset)
        self._changed()

    @staticmethod
    def _moved(ref: str, cam: _Camera, offset: float) -> None:
        cam.clock_steps += 1
        log.warning("camera %s: its clock moved %.3f s against this cluster's (this cluster's clock stepped, or its clock "
                    "drifts with nobody setting it): its frames from here on are put on this clock by the new difference",
                    ref, (cam.target if cam.target is not None else cam.offset) - offset)
        if cam.offset - CLOCK_STEP <= offset < cam.offset:
            cam.target, cam.rise, cam.leap = offset, None, False # below where the stream is put: slewed to, not jumped
        else:
            cam.offset, cam.rise, cam.target, cam.newest, cam.leap = offset, None, None, None, False
        cam.provisional = None

    @staticmethod
    def _slewed(cam: _Camera, frames: list, now: float) -> list:
        """The camera's frames on this cluster's clock — each by the offset as it slews down to its target, a frame at a
        time, no faster than `OFFSET_SLEW` of the frames' own distance (above). A target further down than `CLOCK_STEP`
        (`leap`, from an offset not yet held firm) is taken at once by the first frame that, put by it, still lies after
        the last frame put: the camera's clock was set and its frames leapt with it (a camera with no RTC set by NTP) —
        otherwise the frames came on as before, the offset was a first pass's travel, and they slew to it.

        …AND NOT INTO THE FUTURE (DZ: a withdrawn rise). A push that took forty seconds put its frames forty seconds late;
        the frames the camera captured meanwhile come after them, and slewed at half their distance they lay up to twenty
        seconds ahead of this ingest's clock — past `CAMERA_AHEAD`, refused at the door (773 of 2000). While the offset
        slews, a batch that would reach past `CAMERA_AHEAD` (`now`) is pressed evenly between the last frame put and that
        bound: closer together for a while, every one in order, none refused."""
        out, offs, slewing = [], [], cam.target is not None and cam.newest is not None
        last = cam.newest + cam.offset if slewing else None              # where the last frame was put
        for f in frames:
            t = _t(f)
            if t is not None:
                if cam.target is not None and cam.newest is not None and t > cam.newest:
                    if cam.leap and t + cam.target > cam.newest + cam.offset:
                        cam.offset = cam.target                  # nothing lands behind the last frame: taken at once
                    else:
                        cam.offset = max(cam.target, cam.offset - OFFSET_SLEW * (t - cam.newest))
                    if cam.offset <= cam.target:
                        cam.target, cam.leap = None, False
                cam.newest = t if cam.newest is None else max(cam.newest, t)
            offs.append(cam.offset)
        put = [(i, _t(f) + o) for i, (f, o) in enumerate(zip(frames, offs)) if _t(f) is not None]
        bound = now + CAMERA_AHEAD - OFFSET_HOLD
        if slewing and put and put[-1][1] > bound > last:
            k = (bound - last) / (put[-1][1] - last)
            for i, p in put:
                if p > last:
                    offs[i] = last + (p - last) * k - _t(frames[i])
            cam.offset = offs[put[-1][0]]
        for f, o in zip(frames, offs):
            out += _shift([f], o)
        return out

    def _keys(self):
        """`keys()` — and a key set in this cluster's store that does not parse is a refusal with the reason, as no key
        set is (the review's eighth pass: it raised out of every poll and push of every camera)."""
        from w2cplatform.domain.agent import Untrusted
        try:
            return self.keys()
        except Untrusted as e:
            raise Refused(f"{self.cluster}: {e}") from None

    def poll(self, token: str, ref: str, camera_now: float | None = None, version: int | None = None,
             wait: float = 0.0, rtt: float | None = None) -> dict:
        """The camera's long poll: whether to push now, and which ranges to upload — ranges on the CAMERA's
        clock. Wants and requests at any ingest of this cluster count (AG). `version`: what the camera last saw;
        the same version is a poll the ingest HOLDS — up to `wait` seconds, answered the moment anything changes
        — and, if nothing did, answers with `held`. `rtt`: how long the camera's last request took there and back.

        The camera's clock is measured as the poll ARRIVES, once: a wake of the held poll measures nothing (the twelfth
        review — every wake measured it again by the `camera_now` the poll was sent with, so the hold read as travel)."""
        until = time.monotonic() + wait
        while True:
            gen = self._gen
            out = self._poll_once(token, ref, camera_now, version, rtt)
            camera_now = rtt = None                              # …and a wake measures nothing
            if not out.get("held") or time.monotonic() >= until:
                return out
            lapse = self._next_lapse(ref)                        # AH: a want or an ask that runs out changes the answer
            if self.should is not None:
                lapse = self.recheck if lapse is None else min(lapse, self.recheck)
            self._wait(gen, until if lapse is None else min(until, time.monotonic() + lapse))

    def _next_lapse(self, ref: str) -> float | None:
        """Seconds until the next thing that changes this camera's answer by itself, with nobody touching
        anything: a want running out (a viewer's linger) or an ask's deadline. Nothing bumps a generation then,
        so the held poll must be timed to it (feedback AH)."""
        now, soon = self.wall(), []
        for ing in self._cluster():
            c = ing._cam(ref)
            soon += [u - now for u in list(c.wants.values()) if u != float("inf") and u > now]
            soon += [a["deadline"] - now for a in list(c.asks.values()) if a["deadline"] > now]
        return min(soon) if soon else None

    def _poll_once(self, token: str, ref: str, camera_now: float | None, version: int | None,
                   rtt: float | None = None) -> dict:
        p = self._check(token, ref, camera_now, rtt)
        now, cam = self.wall(), self._cam(ref)
        cam.polled_at, cam.polled_by = now, str(p.get("sub") or "") or None
        firm = self._told(cam)                                   # None: a rise is provisional — new ranges wait
        push, ranges, asks, told = False, {}, {}, {}
        for ing in self._cluster():
            ing._forget(now)
            c = ing._cam(ref)
            c.wants = {w: u for w, u in c.wants.items() if u > now}       # a want that ran out wakes the poll (AF)
            push = push or bool(c.wants)
            for rid, r in list(c.ranges.items()):
                by = c.told_by.get(rid)
                if by is None and firm is not None:
                    by = c.told_by[rid] = firm
                if by is not None:
                    ranges[rid], told[rid] = r, by
            _forget_outcomes(c, now)
            for aid, a in list(c.asks.items()):
                if a["deadline"] <= now:                                  # dies at its deadline, never kept
                    _settle(c, aid, "expired", a["by"], now)
                    del c.asks[aid]
                else:
                    asks[aid] = a
        sv = self.should(ref) if self.should is not None else None     # None: nothing to say — the book decides
        uncovered = None if sv is None else (bool(sv) and not self.taken(ref))
        said = (push, tuple(sorted(ranges.items())), tuple(sorted(asks)), uncovered)   # a new ask, a lost recorder: news
        if said != cam.said:
            cam.said, cam.version = said, cam.version + 1
        # A range is told with the recording it is of, and with the size of a piece the recorder waits for
        # (`piece_wait`): the camera sends its answer in pieces no larger (the product's `PollRange`, and two fields more).
        # It is told by the offset it was first told by (`told_by`), every time: the answer goes back by the same (`upload`)
        # — the firm offset (`_told`), and none while a rise is provisional: the range waits untold (the twelfth review).
        # An ask's deadline and `have` go by the firm offset too, and by the raised one while it is provisional: the
        # earlier on the camera's clock — an ask expires early sooner than it is performed late, and the camera takes the
        # recorder to have less, so it sends again what the tee drops and its card holds more, never less.
        said_by = cam.offset if firm is None else firm
        out = {"push": push, "version": cam.version,
               "ranges": {rid: {"from": t0 - told[rid], "to": t1 - told[rid], "recording": rec, "piece": PIECE_BYTES}
                          for rid, (t0, t1, rec) in ranges.items()},
               "asks": {aid: {"action": a["action"], "by": a["by"],
                              "deadline": a["deadline"] - said_by}
                        for aid, a in asks.items()}}
        if uncovered is not None:
            out["uncovered"] = uncovered
        have = self._have(ref)
        if have is not None:
            # Not part of `said`: it moves with every frame written, and a poll held for news must not wake for it.
            out["have"] = float(have) - said_by
        if version is not None and version == cam.version:
            out["held"] = True                                   # nothing changed: the real ingest holds the request
        return out

    def push(self, token: str, ref: str, frames: list, camera_now: float | None = None, rtt: float | None = None) -> int:
        self._check(token, ref, camera_now, rtt)
        frames = self._timely(ref, self._slewed(self._cam(ref), self._timely(ref, frames, future=False), self.wall()), CAMERA_AHEAD)
        have = self._have(ref)
        if have is not None:
            # What the recorder already wrote does not go to it twice (CB). `have` is conservative — a heartbeat
            # old — so this takes the bulk, and the tee the rest: no subscriber is given a frame not newer than the
            # last it was given (`_InOrder`; the eighth review).
            frames = [f for f in frames if not (isinstance(f, dict) and "t" in f and float(f["t"]) <= have)]
        return self._take(ref, frames)

    # WHAT THE CAMERA MAY TAKE FOR DELIVERED (the product's DY, checked in the course): how far this cluster's recorder
    # wrote it — and, where this cluster's forwarder carries the camera up to a centre that records it, no further than
    # the centre wrote it (`up_have`). The camera's card lets go only of what lies before it (`CameraPusher.owed_spans`).
    def _have(self, ref) -> float | None:
        have = self.written(ref) if self.written is not None else None
        up = self.up_have.get(str(ref))
        return have if up is None else up if have is None else min(have, up)

    def _timely(self, ref: str, frames: list, ahead: float | None = FRAME_AHEAD, future: bool = True) -> list:
        """The frames whose time is a finite number and — `future` — not later than this ingest's clock by more than
        `ahead` (a camera's own: `CAMERA_AHEAD`); the rest refused, counted (`ahead`), logged once per camera. A frame
        with no time passes."""
        limit, out = self.wall() + (ahead or 0.0), []
        for f in frames:
            if isinstance(f, dict) and "t" in f:
                try:
                    t = finite(f["t"])
                except PARSE_ERRORS:
                    t = None
                if t is None or (future and t > limit):
                    n = self.ahead[str(ref)] = self.ahead.get(str(ref), 0) + 1
                    if n == 1:
                        log.warning("camera %s: a frame stamped %r — %s: refused, and given to nobody", ref, f["t"],
                                    "no time at all" if t is None else f"{t - limit + (ahead or 0.0):.1f} s later than now")
                    continue
            out.append(f)
        return out

    def _tee(self, ref, kind: str) -> "_InOrder":
        """The camera's tee of `kind` here ("live": recorders, "edge": viewers), on this ingest's clock."""
        tee = self.tees.get((str(ref), kind))
        return tee if tee is not None else self.tees.setdefault((str(ref), kind), _InOrder(ref, self.wall))

    def _take(self, ref: str, frames: list) -> int:
        live, edge = self._tee(ref, "live"), self._tee(ref, "edge")
        for f in frames:
            live.push(f)                                         # recorders: everything, the ring first
            if not _is_ring(f):
                edge.push(f)                                     # viewers: the live edge only (AF)
        self._cam(ref).pushed_at = self.wall()
        # AG, AJ: a peer with a subscriber for this camera gets the stream PUSHED, as the camera pushes here —
        # not left in a viewer's leaky queue for someone to drain. A recorder is behind it.
        for peer in self._cluster()[1:]:
            if peer._has_subscribers(ref):
                self.links.setdefault((peer.name, str(ref)), PeerLink(peer, str(ref))).send(frames)
        return len(frames)

    def upload(self, token: str, ref: str, rid: str, samples: list, camera_now: float | None = None,
               failed: str | None = None, more: bool = False, seq: int = 0, rtt: float | None = None) -> bool:
        """The camera's answer to a range request: samples with their own times, moved onto the cluster's clock,
        kept by the id of the request at whichever ingest of the cluster asked (AD). Never the live stream.
        `failed`: the camera could not read the range — no samples, and why (the product's `X-Range-Failed`); the
        request is over and the recorder waiting for it fails at once, to ask again later.

        IN PIECES (the sixth review): `more` — this is a piece and more follow; `seq` — which piece, from nought. The
        answer is whole, and handed to the recorder, when a piece comes without `more`; a piece out of its turn fails
        the range — an answer with a piece missing would be taken for all the card has. Returns whether anybody still
        waits for this range: False tells the camera to stop reading its card for a recorder that has given up.

        A REPEAT OF THE PIECE TAKEN LAST IS A REPEAT (the seventh review): the answer to an upload can be lost on its way
        back as well as the upload itself, and the camera sends the piece again under the same number — `seq == n - 1`.
        It was failed as "out of its turn": one lost answer cost the whole range, and at 5 % of answers lost one range
        in ten landed. Now it is taken as what it is — nothing added, the range waits for piece `n` — and the camera
        hears that the range is still wanted.

        BACK BY THE OFFSET IT WAS TOLD BY (DZ's second half, a sibling the probe found on this path: no poll in the middle
        of an upload recreates anything here — 300 of 300 samples, the card read once, with polls between the pieces,
        inside each upload and from three threads — but the held offset that moved between two pieces moved the pieces
        after it: 10 of 300 samples landed past the range asked for and two seconds of it were missing). Each piece goes
        back onto this cluster's clock by the offset the request was first told by (`told_by`), so the answer lands in the
        range it answers, whatever the offset does meanwhile."""
        self._check(token, ref, camera_now, rtt)
        now, wanted = self.wall(), False
        for ing in self._cluster():
            c = ing._cam(ref)
            if rid not in c.ranges:
                continue
            shifted = _shift(samples, c.told_by.get(rid, self._cam(ref).offset))
            n, have, _ = c.parts.pop(rid, (0, [], 0.0))
            if failed is None and more and seq == n - 1:
                c.parts[rid] = (n, have, time.monotonic())             # a repeat: taken already, and the camera is alive
                wanted = True
                continue
            if failed is None and seq != n:
                failed = f"piece {seq} of the answer came where piece {n} was due"
            if failed is not None:
                c.failed[rid] = (str(failed), now)
                c.ranges.pop(rid)
            elif more:
                c.parts[rid] = (n + 1, have + shifted, time.monotonic())
                wanted = True
            else:
                c.answers[rid] = (have + shifted, now)
                t0, t1, _rec = c.ranges.pop(rid)
                c.landed = (c.landed + [(t0, t1)])[-LANDED_KEPT:]
                wanted = True
        self._changed()
        return wanted

    def _forget(self, now: float) -> None:
        """What nobody came for goes: an answer or a failure `ANSWER_KEPT` old, and a piece of an answer — or the offset
        it was told by — whose request is gone. Every poll and every request sweeps — as asks are swept (`_sweep`)."""
        for c in list(self.cams.values()):
            for kept in (c.answers, c.failed):
                for rid in [k for k, v in list(kept.items()) if now - v[1] >= ANSWER_KEPT]:
                    kept.pop(rid, None)
            for kept in (c.parts, c.told_by):
                for rid in [k for k in list(kept) if k not in c.ranges]:
                    kept.pop(rid, None)

    # -- asks between cameras ---------------------------------------------------------------------------------
    def ask(self, token: str, target: str, action: dict, deadline: float, camera_now: float | None = None) -> str:
        """A camera asks `target` to do `action` before `deadline` (the asker's clock). The token is the domain
        signer's, for this ingest, naming the target in its `ask` claim — issued because a scenario ties the
        asker's event to the target's action. Kept only until the deadline."""
        ks = self._keys()
        if ks is None:
            raise Refused(f"{self.cluster}: no key set yet")
        try:
            p = verify(token, ks, self.revoked(), now=self.wall(), kind="ask")
        except TokenError as e:
            raise Refused(f"ask token refused: {e}")
        if p.get("aud") != audience(self.cluster) or str(p.get("ask")) != str(target):
            raise Refused(f"ask token is for {p.get('ask')} at {p.get('aud')}, not {target} at {audience(self.cluster)}")
        # The token names the actions the scenarios allow — "preset 3", not "anything the yard camera does".
        # A camera whose token was minted for preset 3 cannot ask for preset 9, or for the relay.
        action = json.loads(json.dumps(action))
        if action not in (p.get("acts") or []):
            raise Refused(f"{p.get('by', p['sub'])} may ask {target} for {p.get('acts') or 'nothing'}, not {action}")
        now, by = self.wall(), p.get("by", p["sub"])
        # A DEADLINE IS A NUMBER (the review's eighth pass, major). `nan` passed every check and failed every comparison:
        # `nan > now` is false, so an ask of `nan` was never counted against `MAX_LIVE_ASKS` and never expired — two
        # thousand of them were taken at a ceiling of sixteen, and every poll of the target handed them all out. A
        # deadline or a camera clock that is not a finite number is refused, and so is a deadline further ahead than
        # `ASK_DEADLINE_MAX`.
        shift = 0.0 if camera_now is None else now - _finite_clock(camera_now)
        try:
            deadline = finite(deadline)
        except (TypeError, ValueError, OverflowError):    # 10**400 too (the review's ninth pass)
            raise Refused(f"an ask's deadline is a number of seconds, not {deadline!r}") from None
        if deadline + shift > now + ASK_DEADLINE_MAX:
            raise Refused(f"an ask's deadline is at most {ASK_DEADLINE_MAX:.0f} s ahead; this one is "
                          f"{deadline + shift - now:.0f} s ahead")
        if deadline + shift <= now:
            raise Refused(f"an ask's deadline has passed: it was {now - deadline - shift:.0f} s ago")
        for ing in self._cluster():
            ing._sweep(now)
        live = (sum(1 for c in list(self.cams.values()) for a in list(c.asks.values()) if a["by"] == by and a["deadline"] > now)
                + sum(1 for a in list(self.up.values()) if a["by"] == by and a["deadline"] > now))
        if p.get("up"):                                   # a road UP: not for a camera here — for this relay to carry
            for aid, a in list(self.up.items()):
                if a["by"] == by and a["target"] == str(target) and a["action"] == action and a["deadline"] > now:
                    return aid
            if live >= MAX_LIVE_ASKS:
                raise Refused(f"{by} holds {live} live asks at {self.cluster}: over the ceiling of {MAX_LIVE_ASKS}")
            aid = secrets.token_hex(4)
            self.up[aid] = {"target": str(target), "action": action, "deadline": float(deadline) + shift, "by": by,
                            "lifted": False}
            self._changed()                                # the forwarder hears it now, not on its next pass
            return aid
        # The same ask while one is alive IS that ask: twenty events from one gust of wind are one preset, not
        # twenty — the asker is told the id it already has.
        for ing in self._cluster():
            for aid, a in list(ing._cam(target).asks.items()):
                if a["by"] == by and a["action"] == action and a["deadline"] > now:
                    return aid
        if live >= MAX_LIVE_ASKS:
            raise Refused(f"{by} holds {live} live asks at {self.cluster}: over the ceiling of {MAX_LIVE_ASKS}")
        aid = secrets.token_hex(4)
        self._cam(target).asks[aid] = {"action": action, "deadline": float(deadline) + shift, "by": by}
        self._changed()                                    # wakes the target's held poll
        return aid

    def _sweep(self, now: float) -> None:
        """AI: an ask's deadline is a property of the ASK, not of its target's poll — a camera that is off, or
        was taken off the site for good, never polls again. Every touch of the ingest sweeps: dead asks become
        "expired" (the asker reads THAT, not "lost"), and outcomes older than REMEMBER are forgotten."""
        for c in list(self.cams.values()):
            for aid, a in list(c.asks.items()):
                if a["deadline"] <= now:
                    _settle(c, aid, "expired", a["by"], now)
                    c.asks.pop(aid, None)
            _forget_outcomes(c, now)

    # The forwarder's side of asks going up: take the new ones, put one back when the centre did not answer (it
    # is tried again until its deadline), and settle each with what the centre said became of it.
    def take_up(self) -> list[tuple[str, dict]]:
        now, out = self.wall(), []
        self._sweep(now)
        for aid, a in list(self.up.items()):
            if a["deadline"] <= now:
                self.settle_up(aid, "expired")             # died here, on the way up: never kept
            elif not a["lifted"]:
                a["lifted"] = True
                out.append((aid, dict(a)))
        return out

    def untake_up(self, aid: str) -> None:
        if aid in self.up:
            self.up[aid]["lifted"] = False

    def settle_up(self, aid: str, outcome: str) -> None:
        a = self.up.pop(aid, None)
        if a is not None:
            _settle(self._cam(a["target"]), aid, outcome, a["by"], self.wall())
            self._changed()

    def outcome_wait(self, target: str, aid: str, wait: float = 0.0) -> str | None:
        """`ask_outcome`, held up to `wait` seconds for the outcome to arrive — the call a relay holds at the
        centre for the asks it carried up, answered the moment the other relay answers."""
        until = time.monotonic() + wait
        while True:
            gen = self._gen
            out = self.ask_outcome(target, aid)
            if out is not None or time.monotonic() >= until:
                return out
            self._wait(gen, until)

    def answer_ask(self, token: str, ref: str, aid: str, outcome: str) -> None:
        """The target's answer: `performed`, or `refused` with its reason. At whichever ingest holds the ask."""
        self._check(token, ref)
        for ing in self._cluster():
            c = ing._cam(ref)
            if aid in c.asks:
                _settle(c, aid, outcome, c.asks.pop(aid)["by"], self.wall())
        self._changed()                                    # the forwarder that carried it down answers up at once

    def carry_ask(self, ref: str, aid: str, ask: dict) -> None:
        """An ask left at the level above, carried down by this cluster's forwarder (Lesson 17) — the forwarder
        is this cluster's own code, as trusted as a recorder's want. Kept under the same id, to answer it up."""
        c = self._cam(ref)
        if aid not in c.asks and aid not in c.outcomes:
            c.asks[aid] = {"action": dict(ask["action"]), "deadline": float(ask["deadline"]), "by": ask["by"]}
            self._changed()

    def ask_outcome(self, target: str, aid: str) -> str | None:
        now = self.wall()
        for ing in self._cluster():
            ing._sweep(now)
        for ing in self._cluster():
            out = ing._cam(target).outcomes.get(aid)
            if out is not None:
                return out[0]
        return None

    def answer(self, ref: str, rid: str) -> list | None:
        """The answer to one range request, or None — not yet, or never: the recorder's timeout decides. A LOOK: the
        answer stays until somebody takes it (`result`), or `ANSWER_KEPT` passes."""
        got = self._cam(ref).answers.get(rid)
        return None if got is None else got[0]

    def result(self, ref: str, rid: str) -> list | None:
        """The answer, TAKEN — handed over once, and forgotten here (the sixth review: every answer stayed in the
        ingest for good) — and a range the camera could not read raised as `RangeFailed`, never taken for an empty
        answer. None: not yet."""
        cam = self._cam(ref)
        why = cam.failed.pop(rid, None)
        if why is not None:
            raise RangeFailed(f"camera {ref} could not read the range: {why[0]}")
        got = cam.answers.pop(rid, None)
        return None if got is None else got[0]

    def fetch_range(self, ref: str, t0: float, t1: float, wait: float | None = None, recording: str | None = None) -> list:
        """The recorder's side, whole (the product's `Ingest.Request`): ask the camera for `[t0, t1)` of `recording`
        on its card — this cluster's clock — and wait for the upload. A camera that could not read it, or sent no
        piece of its answer for `wait` (unset: `piece_wait()`, what a piece takes), raises `RangeFailed`: the copy
        fails, and backfill asks again later. The wait is for the NEXT piece — each one that arrives starts it again
        — so a minute of a slow uplink is waited for as long as it keeps coming, and a camera that went quiet is given
        up after one piece's time. Whatever happens, nothing of the request stays here."""
        wait = piece_wait() if wait is None else wait
        rid = self.request_range(ref, t0, t1, recording)
        asked = time.monotonic()
        try:
            while True:
                gen = self._gen
                got = self.result(ref, rid)
                if got is not None:
                    return got
                came = [p[2] for ing in self._cluster() for p in [ing._cam(ref).parts.get(rid)] if p is not None]
                until = max([asked] + came) + wait
                if time.monotonic() >= until:
                    raise RangeFailed(f"camera {ref} did not answer a range: nothing of it came for {wait:.0f} s")
                self._wait(gen, until)
        finally:
            for ing in self._cluster():
                c = ing._cam(ref)
                for kept in (c.ranges, c.told_by, c.parts, c.answers, c.failed):
                    kept.pop(rid, None)

    def pull(self, token: str, ref: str, who: str, have: tuple | None = None) -> list:
        """Lesson 17, the star: a cluster that nobody can dial either — a relay behind a mobile operator's
        NAT, a cluster in a cloud that takes no inbound — takes the streams of ITS cameras from here, calling
        in. Each pull is wanting the stream for another `LINGER`; stop pulling, and the want runs out.

        A BATCH IS GONE FROM HERE ONLY WHEN THE PULLER HAS IT (the seventh review, the camera's rule one level up): the
        answer is numbered (`.seq`), and the puller says which number it last got (`have`). An answer lost on its way
        down — the drained frames gone with it — is handed over again, in front of what came since; as a stream,
        at most `PEER_BUFFER` frames of it, cut clean to a keyframe. `have` None: a puller that does not count.

        `have` is the batch's mark, `(boot, n)` (the eighth review): only this boot's own last number is "got"; one from
        before a restart of this ingest, or none yet, has the last batch again — after a restart there is none, and the
        stream starts over clean. A puller that restarted says no mark, and gets the last batch once more: a repeat, which
        the ingest it injects into drops (`_InOrder`). (A bare number — a puller of an older build — is no mark either: it
        gets repeats, never a lost batch.)"""
        self._check(token, ref)
        self.want(ref, who, until=self.wall() + self.linger)
        fresh = self.subscribe(ref, who).drain()
        if have is None:
            return fresh
        key = (str(ref), str(who))
        seq, last = self.pulled.get(key, (0, []))
        got = isinstance(have, (tuple, list)) and len(have) == 2 and tuple(have) == (self.boot, seq)
        frames = fresh if got else last + fresh
        if len(frames) > PEER_BUFFER:
            frames = frames[-PEER_BUFFER:]
            while frames and not _is_key(frames[0]):
                frames.pop(0)
        self.pulled[key] = (seq + 1, frames)
        return _Batch(frames, seq + 1, self.boot)

    def inject(self, ref: str, frames: list) -> int:
        """A stream arriving from this cluster's own forwarder or a peer ingest — already on this cluster's clock. Its
        frames are held to the same bound as a camera's (`_timely`): a relay is no less able to hand on a frame from the
        future than a camera to send one."""
        return self._take(ref, self._timely(ref, frames))

    def wanted(self, ref: str) -> bool:
        cam = self.cams.get(str(ref))
        return bool(cam and any(u > self.wall() for u in cam.wants.values()))

    # -- the cluster's side -----------------------------------------------------------------------------
    def want(self, ref: str, who: str, until: float = float("inf")) -> None:
        """Somebody in this cluster wants the stream: a recorder (for ever, or an event's window), a viewer."""
        new = self._cam(ref).wants.get(who) != until
        self._cam(ref).wants[who] = until
        if new:
            self._changed()

    def release(self, ref: str, who: str) -> None:
        cam = self.cams.get(str(ref))
        if cam and who in cam.wants:
            cam.wants[who] = min(cam.wants[who], self.wall() + self.linger)   # a viewer who clicks back is not a restart

    def subscribe(self, ref: str, who: str, kind: str = "live", maxsize: int = 30, edge: bool = False) -> LeakyQueue:
        return self._tee(ref, "edge" if edge else kind).subscribe(who, maxsize)

    def taken(self, ref: str) -> bool:
        """A recorder of this cluster takes the stream — subscribed to it, at any ingest of the cluster. A recorder
        subscribes as `recorder:<name>`; viewers and forwarders are not recorders."""
        return any(w.startswith("recorder") for ing in self._cluster()
                   for (r, kind), tee in list(ing.tees.items()) if r == str(ref) and kind == "live"
                   for w in list(tee.subscribers))

    def _has_subscribers(self, ref: str) -> bool:
        return any(tee.subscribers for (r, _kind), tee in list(self.tees.items()) if r == str(ref))

    def request_range(self, ref: str, t0: float, t1: float, recording: str | None = None) -> str:
        """A range on this cluster's clock; the camera is told it on its own (AC). `recording`: which recording ON
        THE CARD — the camera may hold several, and one it does not hold is answered RANGE FAILED, not empty (the
        sixth review). None: the camera's one recording."""
        self._forget(self.wall())
        rid = secrets.token_hex(4)
        self._cam(ref).ranges[rid] = (t0, t1, None if recording is None else str(recording))
        self._changed()
        return rid

    def pushing(self, ref: str, within: float = 5.0) -> bool:
        cam = self.cams.get(str(ref))
        return bool(cam and cam.pushed_at is not None and self.wall() - cam.pushed_at <= within)

    def landed(self, ref: str) -> list[tuple[float, float]]:
        cam = self.cams.get(str(ref))
        return list(cam.landed) if cam else []

    def _relay(self, ref: str, frames: list) -> int:
        """Frames taken from a peer: to this ingest's subscribers, without counting as a camera pushing HERE — and held
        to the bound of this ingest's clock, as every frame here is (`_timely`)."""
        frames = self._timely(ref, frames)
        live, edge = self._tee(ref, "live"), self._tee(ref, "edge")
        for f in frames:
            live.push(f)
            if not _is_ring(f):
                edge.push(f)
        return len(frames)


def _settle(c: _Camera, aid: str, outcome: str, by: str, now: float) -> None:
    """What became of ask `aid` of `by`, kept for its asker to read — and of `by`'s outcomes at this camera only the last
    `OUTCOMES_KEPT` (the ninth review)."""
    c.outcomes[aid] = (outcome, now, by)
    mine = [k for k, v in c.outcomes.items() if v[2:3] == (by,)]
    for k in mine[:-OUTCOMES_KEPT]:
        del c.outcomes[k]


def _forget_outcomes(c: _Camera, now: float) -> None:
    """Outcomes older than `REMEMBER` go — from the oldest, which is first: kept in the order they were settled, so a
    touch costs what it forgets and not every outcome kept (the ninth review: each ask rebuilt the whole dict)."""
    while c.outcomes:
        k = next(iter(c.outcomes))
        if now - c.outcomes[k][1] < REMEMBER:
            return
        del c.outcomes[k]


def _is_key(frame) -> bool:
    """A frame a decoder can start from. A frame that says nothing (the tests' plain values) counts as one."""
    return not isinstance(frame, dict) or bool(frame.get("key", True))


class _InOrder(LiveTee):
    """A camera's tee at the ingest whose every subscriber gets a frame only when it is newer than the last frame that
    subscriber was given — the recorder's writer's own rule, kept here so a repeat reaches nobody.

    A REPEATED PUSH ADDS NOTHING (the eighth review, major). The ingest dropped only what was not newer than `have` —
    the recorder's word, a heartbeat old — and the rest of the rule ("the writer takes nothing older than its last") was
    in the course's test writer alone; the engine answers an old sample `SEQUENCE_SAMPLE_TIME_INVALID`, and the recorder
    counts that as a loss. A push whose answer was lost, sent again as a break's continuation from a `have` five seconds
    old: 53 repeats out of order. Now each subscriber — a recorder, a viewer, the relay's forwarder; a peer ingest's
    subscribers at the peer, whose tees are these too — is given frames in order, by capture time on this cluster's
    clock (the order its writer keeps), and a repeat counts in `repeats`. A
    subscriber that comes anew — a recorder that restarted — has no last frame, and gets what the camera sends again
    after `have`, which is what it lost. A frame with no time (the tests' plain values) passes as it is.

    ONE FRAME DOES NOT MOVE THE STREAM AHEAD (the tenth review, major). A frame inside the bound of the door it came by
    but far past the stream — one of now+59 at a peer's door, of now+9 at the camera's — became the subscriber's last
    frame, and every frame of the next 59 s (or 9) was dropped as a repeat. So a frame further past the subscriber's last
    than `STREAM_JUMP` AND later than this ingest's clock by as much is HELD: the frame after it says whether the stream
    went there (it lies within `RING_AHEAD` past the held one: both are handed on) or not (the held frame was nobody's
    stream — dropped, counted in `ahead`).

    …ONLY A FRAME FROM THE FUTURE (the eleventh review, major, a regression: "a sparse stream is dropped nearly whole").
    Held for being far past the subscriber's last alone, a frame every 11, 15 or 60 s — a time-lapse, a snapshot camera,
    frames on an event — was held every time, and the frame after it, as far past it again, failed it: 1 of 40 reached the
    recorder (`ahead` 38) at every door. The frame that can silence a stream is one later than NOW — whatever the stream
    does, its next frame is not later than now — so that is the one held; a sparse stream, a break continued from where it
    reaches, a push begun again after a pause are all in the past, and pass at once. `wall`: this ingest's clock."""

    def __init__(self, camera, wall=None):
        super().__init__(camera)
        self.wall = wall or time.time
        self.last: dict[str, float] = {}
        self.held: dict[str, tuple] = {}                 # per subscriber: a frame far past its last, waiting for the next
        self.repeats = self.ahead = 0

    def unsubscribe(self, who: str) -> None:
        super().unsubscribe(who)
        self.last.pop(who, None)
        self.held.pop(who, None)

    def push(self, frame) -> None:
        self.frames += 1
        t = _t(frame)
        for who, q in list(self.subscribers.items()):
            if t is not None:
                last, held = self.last.get(who), self.held.get(who)
                if last is not None and t <= last:
                    self.repeats += 1
                    continue
                if held is not None:
                    del self.held[who]
                    if held[0] < t <= held[0] + RING_AHEAD:      # the stream went where the held frame was: both go
                        q.push(held[1])
                        last = self.last[who] = held[0]
                    else:                                        # it did not: the held frame was nobody's stream
                        self.ahead += 1
                if last is not None and t > last + STREAM_JUMP and t > self.wall() + STREAM_JUMP:
                    self.held[who] = (t, frame)                  # far past the stream, and ahead of now: does the next follow?
                    continue
                self.last[who] = t
            q.push(frame)


class _Batch(list):
    """The frames of one pull, and its mark — `(boot, seq)`, `have`: what the puller says it has, next time
    (`Ingest.pull`)."""

    def __init__(self, frames, seq: int, boot: str = ""):
        super().__init__(frames)
        self.seq, self.boot = seq, boot
        self.have = (boot, seq)


class PeerLink:
    """The stream one ingest pushes to a peer of its cluster for one camera (AJ). A recorder is behind it, so a
    frame lost in the middle of a GOP is worse than a gap: the recorder writes garbage, or nothing, until the
    next keyframe. So the link never leaks frame by frame. While the peer keeps up, every frame goes through; a
    peer that falls behind by more than `PEER_BUFFER` frames loses the WHOLE backlog, and the link waits for the
    next keyframe before sending again — a clean cut, counted (`dropped`), as the recorder counts
    `samples_dropped`. In one process delivery is a call; on a network, `paused` is backpressure."""

    def __init__(self, peer: "Ingest", ref: str, limit: int = 0):
        self.peer, self.ref, self.limit = peer, ref, limit or PEER_BUFFER
        self.buffer: list = []
        self.cutting, self.dropped, self.cuts, self.paused = False, 0, 0, False

    def send(self, frames: list) -> None:
        for f in frames:
            if self.cutting and not _is_key(f):
                self.dropped += 1
                continue
            self.cutting = False
            self.buffer.append(f)
            if len(self.buffer) > self.limit:
                self.dropped += len(self.buffer)
                self.buffer, self.cutting, self.cuts = [], True, self.cuts + 1
        if not self.paused and self.buffer:
            batch, self.buffer = self.buffer, []
            self.peer._relay(self.ref, batch)


class IngestLiveEndpoint:
    """The gateway's endpoint for a camera that pushes: the same `open`/`authorise`/`tees` as a worker's
    (Lesson 3), over the ingest. Opening it is a viewer WANTING the stream — the camera learns on its poll —
    and what the viewer gets is the live edge, not the ring (AF). On a real ingest this is an RTSP mount whose
    pipeline connects to the ingest's local socket at the first viewer: that connection IS the want, and its
    end is the leave, with the linger."""

    def __init__(self, ingest: Ingest, authorise):
        self.ingest, self.authorise = ingest, authorise
        self.worker = audience(ingest.cluster)
        self.tees = _Tees(ingest)

    def open(self, camera, token: str, who: str) -> LeakyQueue:
        self.authorise(token, camera)                    # the cluster's check, as at any endpoint; raises Forbidden
        self.ingest.want(camera, who)
        return self.ingest.subscribe(camera, who, edge=True)


class _Tees:
    def __init__(self, ingest: Ingest):
        self.ingest = ingest

    def __getitem__(self, camera):
        ingest = self.ingest

        class _Handle:
            @staticmethod
            def unsubscribe(who):
                ingest._tee(camera, "edge").unsubscribe(who)
                ingest.release(camera, who)
        return _Handle()


# -- the camera --------------------------------------------------------------------------------------------
# One pass of the camera's pusher, after its agent has carried the book home. `dial(url)` is the camera
# opening a connection OUT — it raises Unreachable when that address does not answer, and then the next one
# in the book is tried. `frames_now` is what the sensor produced since the last pass, each with its capture
# time on the camera's clock (`t`); `card(recording, t0, t1, max_bytes)` reads a range off the card, on that clock
# too, a piece at a time (below). `clock` is the camera's own clock, stated in every request (AC). `ring_seconds`:
# how much of what came before a push is sent first — marked — when somebody starts wanting the stream (AC).
# `hold_seconds`: how far back a BREAK is continued — the road was lost while pushing — when the road comes back (CB).
# It has to reach as far back as the card's gate waits before it writes (`RecWorker.defer_for` plus how late the
# break is noticed — `RecWorker.CONTINUE_REACH`, 30 s): a break that ends while the card still waits is in memory
# ONLY, and a shorter reach here would lose its beginning. A longer break: the card wrote it, from before its start,
# and BACKFILL takes it off the card (below, "how far a break is continued").
#
# THE PUSHER HOLDS NO FRAMES OF ITS OWN ON A CAMERA (the seventh review: "the pusher keeps frames outside the budget
# and counts them in seconds"). It kept two lists — `tail`, what it had sent in the last half-minute, and `ring`, the
# break — with the same frames the camera's ring (`vms.card.CamRing`) already held: 14.8 MiB each at 4 Mbit/s, 29.6 at
# 8, some 70 MiB in a camera whose budget says 40. Now its frames ARE the camera's ring: given it (`ring=`), the pusher
# keeps only WHERE the stream stands — `sent`, the capture time of the last frame an ingest took, and `cursor`, where
# the next piece begins — and reads the ring from there, a piece at a time (`_RingFrames`). What it sent and may not
# have been written, a break, the frames before an event: all of it is the ring's, under the ring's bytes. Of the card
# it holds one piece in flight, from the camera's budget (`vms.card.memory_split`, "pieces"). Without a camera's ring —
# the course's model frames, dicts with no bodies — it keeps one of its own, of the same bounds (`_OwnFrames`).
#
# A FRAME IS GONE FROM THE PUSHER'S STATE ONLY WHEN AN INGEST TOOK IT (the seventh review, blocker 3). The state of a
# break was reset BEFORE the push that continued it, and `Unreachable` — not an `OSError` — left the pass on the way
# out: a push that failed after a poll that answered lost the whole break, with `resumed` counting it as sent; and an
# ordinary push that failed lost its own frames, which were never added to what was kept. Now `sent`, `cursor` and the
# end of a break move after each push an ingest confirmed, and nowhere else; a push that fails leaves them where they
# were, and the break stands — the next road that answers gets everything from the last frame taken. The same rule for
# a range's pieces (`uploading`: a piece not acknowledged is sent again, as it was, under its own number) and for an
# ask (`_outcomes`: an action performed and not acknowledged is answered again, not performed again).
#
# THE CARD IS OPTIONAL, AND IT IS NOT AN ARCHIVE (the product's camera; feedback CB, DG, DH). On a camera the card is
# the camera's buffer of plain files, written from the camera's one ring with no engine (`vms/card.py`); `card` here
# is its range reader — `CardRecorder.answer_range`. The pusher does not need it: a camera with no card — none put in,
# or one that would not open — pushes and continues breaks from memory all the same, and answers a range with RANGE
# FAILED (`upload(failed=...)`), as it does when the card could not read one: the server asks again later. Answered
# empty, the server would remember the range as "not on the card" and never ask again.
#
# THE CARD'S READER (the sixth review): `card(recording, t0, t1, max_bytes)` gives the range as an ITERATOR OF PIECES
# — lists of `Sample`, each at most `max_bytes` — read off the card as each is asked for; `recording` is the one the
# request names (None: the camera's one), and one the card does not hold is an error. Nothing of the card is in
# this process but the piece in hand.
def _t(frame) -> float | None:
    """A push frame's capture time on the camera's clock; None for a frame that carries none (the tests' plain values)."""
    return float(frame["t"]) if isinstance(frame, dict) and "t" in frame else None


def _weight(frame) -> int:
    """The bytes a push frame holds: the record's body, off the card or the camera's ring, or a body of its own. The
    course's model frames have none, and weigh nothing."""
    if not isinstance(frame, dict):
        return 0
    body = getattr(frame.get("sample"), "body", None)
    if body is None:
        body = frame.get("body")
    return len(body) if isinstance(body, (bytes, bytearray, str)) else 0


def _key(frame) -> bool:
    return not isinstance(frame, dict) or bool(frame.get("key", True))


class _RingFrames:
    """The camera's own ring (`vms.card.CamRing`), as its pusher sees it: what the sensor put there, as push frames
    (`wire`), on the camera's clock. The pusher holds nothing of its own; the ring is fed by the sensor, not the pass."""

    def __init__(self, ring):
        self.ring = ring

    def add(self, frames: list) -> None:
        if frames:
            raise ValueError("a pusher over the camera's ring takes the frames from the ring, not from the pass")

    def oldest(self) -> float | None:
        ms = self.ring.oldest()
        return unix_s(ms) if ms else None

    def newest(self) -> float | None:
        ms = self.ring.newest()
        return unix_s(ms) if ms else None

    def last_key(self) -> float | None:
        ms = self.ring.last_key()
        return unix_s(ms) if ms else None

    def weight(self, after: float | None) -> int:
        return self.ring.weight(0 if after is None else archive_ms(after))

    def piece(self, after: float | None, max_bytes: int, joined: bool = False) -> tuple[list, bool]:
        frames, whole = self.ring.piece(0 if after is None else archive_ms(after), max_bytes, joined=joined)
        return [wire(s) for s in frames], whole and after is not None

    def reach(self) -> float:
        """Seconds of the stream memory holds when it is full: the ring's window, or less at a high bitrate."""
        return self.ring.reach()

    def skew(self) -> float:
        """What the ring's line of time adds to the camera's clock (`CamRing.skew`): the steps it took up."""
        return self.ring.skew()

    def now(self) -> float:
        """The camera's clock on the ring's line (`CamRing.now`)."""
        return self.ring.now()

    def steps(self) -> dict:
        r = self.ring
        return {"clock_back_s": round(r.clock_back_ms / 1000.0, 3), "clock_forward_s": round(r.clock_forward_ms / 1000.0, 3),
                "ahead": r.ahead, "clock_set": r.line.sets, "clock_unset": r.line.unset}

    def moves(self) -> list[tuple]:
        """The moves of the ring's line (`CamRing.moves`), in unix seconds: `(lo, hi, delta)` — the delta in whole ms, as
        the ring moved its frames by (`CamRing._relabel`; the twelfth review's sibling: moved by the line's fraction of a
        ms, the pusher's place no longer met the frame it stood on, and the next piece began at a key frame — the frames
        before it, four at a set of the clock, never sent)."""
        return [(unix_s(lo), unix_s(hi), int(round(d)) / 1000.0) for lo, hi, d in self.ring.moves()]

    def adrift(self) -> float | None:
        """Where the ring's line went on by a guess, its clock unset since a reboot (`CamRing.adrift`), or None."""
        ms = self.ring.adrift()
        return None if ms is None else unix_s(ms)

    def unplaced(self) -> list[tuple[float, float]]:
        """`[lo, hi)` of the line where frames of unset boots lie with no capture time (`CamRing.unplaced`), unix s."""
        return [(unix_s(lo), unix_s(hi)) for lo, hi in self.ring.unplaced()]


class _OwnFrames:
    """What a pusher given no camera ring keeps itself: the course's model frames (dicts with `t`), in the order they
    were captured, for `window` seconds and at most `max_bytes` — the bounds of the camera's ring. `clock` is the
    camera's own, `steady` its steady clock (`vms.card.CamLine`).

    ON ONE LINE OF TIME, as the camera's ring keeps it — the same `CamLine`, in seconds (the ninth review, blocker; the
    tenth's on a step forward). A frame not newer than the one before it was "stale" here, and not taken: a camera clock
    that stepped back thirty seconds lost the thirty seconds after it, counted only in a field nobody read. Now a step,
    back or forward, is taken up on the line — the frames after it follow the one before, a frame's interval later —
    and counted (`clock_back_s`, `clock_forward_s`). A frame later than both the one before it and the camera's clock by
    more than `RING_AHEAD` has no capture time: kept, right after the one before, counted (`ahead`)."""

    def __init__(self, window: float, max_bytes: int, clock, steady=None):
        self.window, self.max_bytes = float(window), int(max_bytes)
        self.frames: list[dict] = []
        self.bytes = 0
        self.line = CamLine(clock, steady, unit=1, at=float)
        self.line.on_move.append(self._relabel)

    def _relabel(self, lo, hi, d) -> None:
        """The line re-anchored (its clock set, `vms.card.CamLine`): the frames held on it move with it."""
        self.frames = [dict(f, t=_t(f) + d) if lo <= _t(f) <= hi else f for f in self.frames]

    def moves(self) -> list[tuple]:
        return list(self.line.moves)

    def adrift(self) -> float | None:
        return self.line.adrift

    def unplaced(self) -> list[tuple[float, float]]:
        return [(lo, hi) for lo, hi in self.line.unplaced]

    def skew(self) -> float:
        return self.line.skew()

    def now(self) -> float:
        return self.line.now()

    def steps(self) -> dict:
        ln = self.line
        return {"clock_back_s": round(ln.back_by, 3), "clock_forward_s": round(ln.forward_by, 3), "ahead": ln.ahead,
                "clock_set": ln.sets}

    def _timed(self, f: dict) -> dict:
        t = _t(f)
        b, _ = self.line.place(t, t)
        return f if b == t else dict(f, t=b)

    def add(self, frames: list) -> None:
        for f in frames:
            f = self._timed(f)
            self.frames.append(f)
            self.bytes += _weight(f)
        floor, drop = self.line.now() - self.window, 0
        while drop < len(self.frames) and (_t(self.frames[drop]) < floor or self.bytes > self.max_bytes):
            self.bytes -= _weight(self.frames[drop])
            drop += 1
        del self.frames[:drop]

    def oldest(self) -> float | None:
        return _t(self.frames[0]) if self.frames else None

    def newest(self) -> float | None:
        return _t(self.frames[-1]) if self.frames else None

    def last_key(self) -> float | None:
        return next((_t(f) for f in reversed(self.frames) if _key(f)), None)

    def weight(self, after: float | None) -> int:
        return sum(_weight(f) for f in self.frames if after is None or _t(f) > after)

    def reach(self) -> float:
        """Seconds it holds when full: the window, or less when its bytes run out first (as `CamRing.reach`)."""
        if len(self.frames) < 2 or not self.bytes:
            return self.window
        span = _t(self.frames[-1]) - _t(self.frames[0])
        return min(self.window, span * self.max_bytes / self.bytes) if span > 0 else self.window

    def piece(self, after: float | None, max_bytes: int, joined: bool = False) -> tuple[list, bool]:
        """`(frames, whole)`, as `CamRing.piece`: the frames past `after` (None: from the first frame held), at most
        `max_bytes` of them and one at least; `whole` — they follow the frame at `after` with nothing missing, because
        it is held or the reader says so (`joined`). Otherwise they start on a key frame."""
        fs, i = self.frames, 0
        if after is not None:
            i = next((k for k, f in enumerate(fs) if _t(f) > after), len(fs))
        whole = joined or (after is not None and i > 0 and _t(fs[i - 1]) == after)
        if not whole:
            while i < len(fs) and not _key(fs[i]):
                i += 1
        out, size = [], 0
        while i < len(fs) and (not out or size + _weight(fs[i]) <= max_bytes):
            out.append(fs[i])
            size += _weight(fs[i])
            i += 1
        return out, whole


_END = object()                                                        # a range's reader has nothing more


def _refused_read(why: str):
    """A range's reader that fails at its next piece — the range is answered RANGE FAILED, and asked again."""
    raise OSError(why)
    yield                                                              # noqa: unreachable — makes this a generator
_BEFORE = 0.001                        # a cursor just before a frame: the stream goes on from it, held or not, a keyframe first
_CARD_BACK = 10.0                      # a read of the card that goes on mid-group starts this far back: a keyframe is in it
# How late the card's gate acts on what the pusher says (`uncovered`): a pass of the gate and a key frame — the
# recorder's `DEFER_MARGIN`. The pusher says "lagging" this much before what it has not sent would leave memory.
GATE_NOTICE = 5.0
FAILED_KEPT = 64                       # ranges the camera could not read, remembered with why (`failed_ranges`)
DELIVERED_KEPT = 256                   # stretches an ingest took, remembered for the card's budget (`delivered`)
DELIVERED_SEAM = 0.25                  # two pieces this close are one stretch: a hole the stream skips is a group at least
# The uplink has room for a range's piece when this pass's push left the stream this close to its newest frame — a pass and
# a piece behind the live edge at most (`uplink_free`).
UPLINK_FREE = 2.0


# WHAT THE INGESTS AND THE FORWARDERS DID NOT HAND ON, ON `/metrics` (the eleventh review, a minor). An ingest's `lost` —
# a subscriber's queue that overflowed, a peer cut, repeats, frames far past the stream — and its `clock_steps` were in
# the object it leaves in its cluster's store (`publish_polled`) and nowhere a monitor reads; a relay's forwarder's
# `dropped` and `holes` were nowhere at all. Both leave an object now (`publish_polled`, `chain.Forwarder.publish`), and
# the domain's console, which reads every member's store already (`alarms.DomainAlarms.alive_at`), says them on its
# `/metrics` — one place for the whole domain, every line labelled with its cluster. Each object goes through the
# members' one reader (`published`): one that does not parse is counted and logged there, and the rest are said; a
# member that does not answer is left out of this scrape. Counters since that process began: a restart starts them
# again, as a Prometheus counter's reset.
def stream_metrics(fed) -> list[str]:
    from w2cplatform.console import label
    from w2cplatform.rows import number
    from w2cplatform.domain.federation import published
    lost, steps, dropped, holes = [], [], [], []
    for name, c in list(fed.clusters.items()):
        try:
            polled = [(k, c.objects.get(k)) for k in c.objects.list(POLLED + "/")]
            forwarded = [(k, c.objects.get(k)) for k in c.objects.list(FORWARDED + "/")]
        except Unreachable:
            continue
        for key, raw in polled:
            d = published(name, key, raw, lambda d: (dict(d.get("lost") or {}), dict(d.get("clock_steps") or {})))
            if d is None:
                continue
            at = f'cluster="{label(name)}",ingest="{label(d.get("ingest", key.rsplit("/", 1)[-1]))}"'
            for ref, e in sorted(dict(d.get("lost") or {}).items()):
                e = e if isinstance(e, dict) else {}

                def n(field, v, ref=ref):
                    return number(f"{name}/{key}#lost.{ref}.{field}", v, int)

                def total(field):                        # `dropped` by subscriber, `peers` by peer: summed
                    by = e.get(field)
                    return sum(n(field, v) for v in by.values()) if isinstance(by, dict) else n(field, by)
                by = {"dropped": total("dropped"), "peers": total("peers"), "repeats": n("repeats", e.get("repeats")),
                      "ahead": n("ahead", e.get("ahead"))}
                lost += [f'ingest_frames_lost_total{{{at},camera="{label(ref)}",why="{why}"}} {v}' for why, v in by.items()]
            steps += [f'ingest_clock_steps_total{{{at},camera="{label(ref)}"}} {number(f"{name}/{key}#clock_steps.{ref}", v, int)}'
                      for ref, v in sorted(dict(d.get("clock_steps") or {}).items())]
        for key, raw in forwarded:
            d = published(name, key, raw, lambda d: dict(d.get("cameras") or {}))
            if d is None:
                continue
            at = f'cluster="{label(name)}",forwarder="{label(d.get("forwarder", key.rsplit("/", 1)[-1]))}"'
            for ref, e in sorted(dict(d.get("cameras") or {}).items()):
                e = e if isinstance(e, dict) else {}
                n = lambda field: number(f"{name}/{key}#cameras.{ref}.{field}", e.get(field), int)   # noqa: E731
                dropped += [f'forwarder_frames_dropped_total{{{at},camera="{label(ref)}",where="held"}} {n("dropped")}',
                            f'forwarder_frames_dropped_total{{{at},camera="{label(ref)}",where="queue"}} {n("queue_dropped")}']
                holes.append(f'forwarder_holes_total{{{at},camera="{label(ref)}"}} {n("holes")}')
    return (["# TYPE ingest_frames_lost_total counter"] + lost + ["# TYPE ingest_clock_steps_total counter"] + steps
            + ["# TYPE forwarder_frames_dropped_total counter"] + dropped + ["# TYPE forwarder_holes_total counter"] + holes)


class CameraPusher:
    sealer = None                  # the ring its books' tokens are opened with: this process's (`keys.ring`) when None

    def __init__(self, serial: str, flash, dial, card=None, clock=None, ring_seconds: float = 0.0, perform=None,
                 hold_seconds: float = 30.0, recording: str | None = None, ring=None, steady=None):
        """`perform(action) -> outcome` carries out an ask from another camera (a preset, a relay) and says
        what happened: "performed", or "refused: <why>". `recording`: this camera's recording on its card — what a
        break is continued from (None: the card's one). `ring`: the camera's ring (`vms.card.CamRing`) — the frames
        it pushes, on its line of time; none, and it keeps the frames of the pass itself, on a line of its own over
        `clock` and `steady` — the camera's steady clock (`time.monotonic` with the real clock; a test's clock gives
        its own, or none)."""
        self.serial, self.flash, self.dial, self.card, self.recording = str(serial), flash, dial, card, recording
        # Ranges answered "could not read", and why: the last `FAILED_KEPT` of them, and how many in all (the thirteenth
        # review, a minor: a list of every one grew by ~144 a day per hole while a camera's clock stayed unset).
        self.failed_ranges: collections.deque = collections.deque(maxlen=FAILED_KEPT)
        self.ranges_failed = 0
        self.unplaced_left = 0                                         # frames with no capture time left out (`_placed`)
        self.perform = perform or (lambda action: "refused: this camera performs no actions")
        self.ring_seconds = ring_seconds
        self.versions: dict[str, int] = {}                             # per road; -1 first: answered at once (AF)
        self.pushing, self.road = None, None                           # the road it pushes on, if any
        self.uncovered: bool | None = None                             # the primary does not take the stream
        self.state = "no book yet"
        self.hold_seconds = hold_seconds
        base = clock or time.time
        steady = steady if steady is not None else (time.monotonic if base is time.time else None)
        self.frames = (_RingFrames(ring) if ring is not None else
                       _OwnFrames(max(hold_seconds, ring_seconds), RING_BYTES, base, steady))
        # THE CAMERA'S CLOCK ON THE FRAMES' LINE (the ninth review, blocker; the tenth's on a step forward). Its frames are
        # on a line that only goes forward and does not jump (`vms.card.CamLine`): a clock that stepped, back or forward,
        # is taken up there. Every time the pusher compares with a frame's — where the stream stands, how far behind it
        # is, what memory reaches — and every time it states to the ingest (`camera_now`, which the ingest's offset is
        # made of) is on that same line, so a step moves nothing anywhere: the recorder's `have`, a range of the card and
        # the frames of a break are all moved by the offset they were captured under, because it is the only one.
        self.clock = self.frames.now
        # WHERE THE STREAM STANDS — all the pusher keeps of it. `sent`: the capture time of the last frame an ingest
        # took. `cursor`: `(after, joined)`, where the next piece begins — past `after`, from a key frame unless the
        # frame at `after` is known to be followed with nothing missing. `live_from`: frames up to it are what came
        # before the push began (the event's ring, a break) — marked, for the recorder, never the viewer's live edge.
        # `broken_at`: the road was lost while pushing — `sent` then. `seen`: the newest frame when the last pass
        # ended: what is newer is this pass's own.
        self.sent: float | None = None
        self._sent_end: tuple[int, int] | None = None                  # its record's end (archive ms) and a slack (`_card_hole`)
        self.cursor: tuple[float | None, bool] | None = None
        self.live_from: float | None = None
        self.broken_at: float | None = None
        self.resuming = False                                          # the stream is continuing a break
        self._left = 0.0                                               # …and how much of it is older than it reaches
        self._hole_said = False                                        # the hole the next piece begins after is counted
        self.seen: float | None = self.frames.newest()
        self._card = None                                              # the continuation's read off the card, under way
        self.resumed = 0                                               # frames sent again after breaks, for the tests and a metric
        # What became of the breaks the stream could not continue whole, in seconds (`continued`): `failed` — the
        # card could not give its part (and how many times, and the last reason); `left` — older than `hold_seconds`,
        # left to backfill; `cut` — the uplink fell behind the stream by more than `lag_limit`, and the stream went on
        # from the live edge. Each is the recorder's backfill to close off the card, and none is silent.
        self.continued = {"failed": 0, "failed_s": 0.0, "failed_why": "", "left_s": 0.0, "cut_s": 0.0}
        self.lag_limit = 2 * hold_seconds
        self.lag, self._lag_at = False, 0.0                            # the uplink does not carry the stream (`_judge_lag`)
        self._peak = 0.0                                               # …how far behind this pass began
        self.catching = False                                          # the stream is behind because of a break
        self._entry: dict | None = None                                # its book's entry, as read last (`entry`)
        self.uploading: dict[str, dict] = {}                           # ranges being answered, piece by piece
        self._outcomes: dict[str, str] = {}                            # asks performed and not yet acknowledged
        # WHAT THE SERVER HAS, FOR THE CARD'S BUDGET (the ninth review, major). The card's budget let go of its oldest
        # first, and a card filled by a lagging stream — it writes all of it, what the uplink carried too — let go of
        # what the stream had skipped before anybody had asked for it. So the pusher remembers what an ingest TOOK
        # (`delivered`, `[from, to]` on the frames' line, which is the card's: both are written from one ring) and what
        # a range the camera uploaded gave the server (`_paid`), from `since` — what was on the card before this process
        # began is nobody's to say. The card asks what it holds that the server has not got (`owed_spans`: from `since`
        # on, all but what was delivered) and lets go of that last (`CardBuffer.owed`).
        self.delivered: list[list[float]] = []
        self.since = self.clock()
        # A card another camera wrote (its note names another serial): what it holds from before this process is not this
        # camera's footage — not offered as a range of it (`_read_card`). None: nothing on the card is in doubt.
        self.foreign_before: float | None = None
        # …and what TOOK is not what was WRITTEN (the product's DY, checked here): an ingest takes a push before its recorder
        # writes it — and a relay's ingest before the centre above it has it. So what the pusher counts delivered is capped
        # by the `have` of the road's last answer (the recorder's word — the lesser of the relay's and the centre's,
        # `Ingest._have`): the card holds what lies past it. An ingest that says no `have` leaves what it took delivered.
        self.have: float | None = None
        self._moved = len(self.frames.moves())                         # the line's moves this pusher has followed (`_follow`)
        # HOW LONG ITS LAST REQUEST TOOK, THERE AND BACK (the twelfth review, blocker 13): said with every request (`rtt`),
        # on the camera's line, which steps of its clock do not move. The ingest takes a rise its round trip explains for
        # travel, not for the camera's clock (`Ingest._offset`). A held poll is not measured: the hold is not travel.
        self.rtt: float | None = None
        # The ranges it was told, by road, and how many moves of its line it had followed when it was first told each.
        self._told: dict[str, tuple[str, int]] = {}

    # THE LINE MOVES, AND THE PUSHER'S PLACE WITH IT (the eleventh review, blockers 1 and 2): the camera's line goes on from
    # the card's when the card is attached (`vms.card.CamLine.restore`), and is re-anchored when an unset clock is set
    # (`CamLine._set`) — the ring's frames moved there, under its lock. Every time the pusher holds on the line — where the
    # stream stands, a break, what the server has — moves by the same amount, at the start of a pass (and before the card's
    # note is taken back): a cursor left on the old line would send the moved frames again, or skip them.
    def _follow(self) -> None:
        moves = self.frames.moves()
        for lo, hi, d in moves[self._moved:]:
            def mv(v, lo=lo, hi=hi, d=d):
                return v + d if v is not None and lo <= v <= hi else v
            self.sent, self.live_from, self.broken_at, self.seen, self.since, self.foreign_before = (
                mv(self.sent), mv(self.live_from), mv(self.broken_at), mv(self.seen), mv(self.since),
                mv(self.foreign_before))
            if self.cursor is not None:
                self.cursor = (mv(self.cursor[0]), self.cursor[1])
            if self._sent_end is not None and lo <= unix_s(self._sent_end[0]) <= hi:
                self._sent_end = (self._sent_end[0] + int(round(d * 1000)), self._sent_end[1])
            self.delivered = [[mv(a), mv(b)] for a, b in self.delivered]
            self._card = None                                          # a read of the card under way: begun again
            for u in self.uploading.values():                          # …and a range being answered: failed, asked again
                u["piece"], u["pieces"] = None, _refused_read("the camera's line of time moved while the range was read")
        self._moved = len(moves)

    # …AND A RANGE TOLD BEFORE THE LINE MOVED IS NOT READ ON THE MOVED ONE (the twelfth review, blocker 12's sibling): the
    # ingest goes on telling a range by the offset it was first told by (`told_by`), and that offset is of the line before
    # the move — the clock set, the frames before it relabelled. Read on the moved line, it brought what lay where the
    # range had been. A range being answered fails at the move (above); one told and not begun yet fails when it is
    # begun. And while the line is ADRIFT — a reboot with the clock unset put it right after the card's newest, by a
    # guess (`vms.card.CamLine.adrift`) — a range reaching before where it went adrift is not read either: before it lie
    # the frames of a boot whose offset the ingest no longer holds, and whichever offset told the range is wrong for one
    # of the two (blocker 12: the first boot's hole, asked between the boot and NTP, read 30 s away). Both fail — RANGE
    # FAILED, never an empty answer — and backfill asks again: after the clock is set the card is on one offset again.
    def _stale_range(self, rid: str, t0: float) -> str | None:
        """Why the range `rid` (from `t0`, on the line) is not read now, or None."""
        if self._told.get(rid, ("", self._moved))[1] < self._moved:
            return "the camera's line of time moved after the range was told: asked again by the line as it is"
        adrift = self.frames.adrift()
        if adrift is not None and t0 < adrift:
            return ("the camera's clock is not set since it booted: the range reaches into an earlier boot, asked again "
                    "once the clock is set")
        return None

    def _request(self, fn, *a, held: bool = False, **kw):
        """A request to an ingest: the camera's clock as it is sent (`camera_now`), and how long its last request took
        there and back (`rtt`) — measured now, unless the ingest may hold it (`held`). A look at the clock that finds it
        set moves the line, and the pusher follows the move at once (`_follow`): what the ingest answers is on the moved
        line."""
        sent = self.clock()
        self._follow()
        out = fn(*a, camera_now=sent, rtt=self.rtt, **kw)
        took = self.clock() - sent
        if not held:
            self.rtt = took if took >= 0 else None                     # a line moved under it: no measure
        return out

    def entry(self) -> dict | None:
        """The book of primaries — or, for a camera nobody records, the book of polls: an ingest to poll for
        asks, never told to push (step 8)."""
        from .keys import POLL_PATH, PRIMARIES_PATH, opened
        items = opened(self.flash.get(PRIMARIES_PATH)[0], PRIMARIES_PATH, self.sealer)
        raw = (items or {}).get(self.serial)
        if raw:
            e = BOOKS.read(f"{PRIMARIES_PATH}/{self.serial}", lambda: _a_primary(json.loads(raw)))
            if e is not None:
                self._entry = e
            return e if e is not None else self._entry           # torn: the entry read last (`BOOKS`)

        def polls(p) -> dict:
            road = {k: p[k] for k in ("urls", "token_secret", "until")}
            _a_road(road)
            return {"cluster": str(p["cluster"]), "polls_only": True, "ingest": road}
        items = opened(self.flash.get(POLL_PATH)[0], POLL_PATH, self.sealer)
        raw = (items or {}).get(self.serial)
        if not raw:
            return None
        e = BOOKS.read(f"{POLL_PATH}/{self.serial}", lambda: polls(json.loads(raw)))
        if e is not None:
            self._entry = e
        return e if e is not None else self._entry

    def behind(self) -> float:
        """How far the stream it pushes is behind the newest frame, in seconds: catching up after a break."""
        newest = self.frames.newest()
        if self.pushing is None or self.cursor is None or newest is None:
            return 0.0
        after = self.cursor[0]
        return 0.0 if after is not None and after >= newest else newest - (after if after is not None else newest)

    def busy(self) -> bool:
        """Work left over from the last pass — a break or a start no ingest has taken yet, a stream catching up, a
        range being answered, an outcome not yet taken: the poll is not held for it."""
        return (self.broken_at is not None or (self.pushing is None and self.cursor is not None) or self.behind() > 0
                or bool(self.uploading) or bool(self._outcomes))

    # HOW FAR A BREAK IS CONTINUED, AND HOW FAST (the seventh review: "the continuation goes whole inside one pass" —
    # ten minutes at 4 Mbit/s, 272 MiB over an uplink of 8 Mbit/s, about five minutes with no live stream at all, no
    # poll, no ask answered; and "what uplink does the camera assume for it?").
    #
    # THE UPLINK IS ASSUMED AT ONE AND A HALF TIMES THE STREAM'S OWN BITRATE. The stream to a recorder goes in order —
    # its writer takes nothing older than its last frame — so a continuation is not sent beside the live stream but
    # ahead of it, and the live edge waits behind it until the stream has caught up: at 1.5 × the bitrate a backlog of
    # B seconds is gone in 2B. So the continuation reaches back no further than `hold_seconds` (30 s: caught up in a
    # minute, the live edge never more than half a minute late) — the stream after a break begins at `have` or at
    # `now - hold_seconds`, whichever is later, and what is older the card wrote (its gate released it, `defer_for`)
    # and BACKFILL copies off it, a range at a time, between the polls. A break of ten minutes is thirty seconds of
    # the stream and nine and a half minutes of backfill; `continued["left_s"]` says how much was left.
    #
    # AND IT GOES A PIECE AT A TIME. A pass sends what came since the last pass and one piece (`PIECE_BYTES`) of the
    # backlog on top, two pieces at the most — never the whole backlog; off the card, a piece as the card gives it —
    # then answers ranges and asks, and the next pass polls at once and goes on: the stream gains as fast as the uplink
    # takes it, and no pass holds the poll, the asks and the ranges longer than two pieces take.
    # Below the assumed uplink it catches up slower; below the stream's own bitrate it cannot catch up at all, and when
    # it falls `lag_limit` (two `hold_seconds`) behind it goes on from the newest key frame, the seconds it skipped
    # counted (`continued["cut_s"]`) and logged — backfill's too. An uplink that does not carry the live stream is a
    # camera that cannot be recorded live, and that is said, not hidden in a queue.
    def _start(self, work: dict, now: float) -> None:
        """Where the stream begins this pass: after a break, at `have` (the recorder's word) or `hold_seconds` back;
        at a start, `ring_seconds` back and this pass's frames; going on, where it stands — or, fallen too far
        behind, at the newest key frame."""
        reach = now - self.hold_seconds
        if self.broken_at is not None:                                 # a break ends here: continue, don't restart
            have = work.get("have")
            after, joined = (reach, True) if have is None else (float(have), False)   # none: all it holds, as at a start
            if after < reach:                                          # older than the stream reaches: backfill's —
                self._left, after = reach - after, reach - _BEFORE     # the stream from the first keyframe at `reach`
                self._hole_said = True
            self.cursor, self.live_from, self.resuming, self._card = (after, joined), self.seen, True, None
            self.catching = True
        elif self.pushing is None:                                     # a start: the ring first, marked
            if self.cursor is None:                                    # (kept from a start no ingest took yet)
                self.cursor = (None if self.seen is None else min(now - self.ring_seconds, self.seen), True)
            self.live_from, self.resuming = self.seen, False
        elif self.cursor is not None and self.cursor[0] is not None and self.cursor[0] < now - self.lag_limit:
            k = self.frames.last_key()
            if k is not None and k > self.cursor[0]:
                self.continued["cut_s"] = round(self.continued["cut_s"] + k - self.cursor[0], 1)
                log.warning("camera %s: its stream fell %.0f s behind (the uplink does not carry it): going on from the "
                            "newest key frame; the %.0f s skipped are backfill's", self.serial, now - self.cursor[0],
                            k - self.cursor[0])
                self.cursor, self._card, self.resuming, self._hole_said = (k - _BEFORE, False), None, False, True
                self.catching = False

    # THE SECONDS THE STREAM SKIPS ARE ON THE CARD (the eighth review, blocker 1). Both logs above said "backfill's", and
    # nothing put them where backfill looks: a card `when: offline` writes only while the pusher says `uncovered`, and a
    # road that answers every poll is not uncovered however slow it is. Measured: an uplink of 0.75 × an 8 Mbit/s stream
    # for 400 s — 136 s cut, 126 s the recorder never got, and 0 s of them on the card; the state said "catching up after
    # a break" with no break at all.
    #
    # So a stream that falls behind further than memory can carry it is LAGGING (`_judge_lag`), and a lagging stream is
    # uncovered: the card's gate opens and writes, from what the ring holds. It is said before anything is lost: when the
    # stream is behind by what memory holds — `reach`, the ring's window or less at a high bitrate — or by `lag_limit`,
    # whichever is less, less the time the gate takes to act (`GATE_NOTICE`). From then on what memory lets go of unsent
    # is on the card, and the stream goes on off the card (`_next_piece`); what the cut to the live edge skips is on the
    # card too, and backfill takes it off there, as the logs say. A lagging stream is also NOT one the camera will
    # continue from memory (`can_continue`): the gate writes at once instead of waiting for it (`RecWorker.resumes`).
    # A break's catch-up stays the stream's own business: it reaches back `hold_seconds`, inside what memory holds at an
    # ordinary bitrate. Lagging lasts until the stream is back within half that bound, and `2 × GATE_NOTICE` at least —
    # a cut puts it at the live edge at once, and the gate must have seen it.
    def lag_open(self) -> float:
        """How far behind the stream may fall before it is lagging: what memory holds, or `lag_limit`, whichever is
        less, less `GATE_NOTICE`."""
        return max(0.0, min(self.frames.reach(), self.lag_limit) - GATE_NOTICE)

    def _judge_lag(self, now: float) -> bool:
        """Judged on the worst of the pass — how far behind it began (`_peak`), before its pieces went — and the end."""
        behind, bound = max(self._peak, self.behind()), self.lag_open()
        self._peak = 0.0
        if not self.lag and behind > bound:
            self.lag, self._lag_at, self.catching = True, now, False
            log.warning("camera %s: its stream is %.0f s behind and memory holds %.0f: the uplink does not carry the stream "
                        "— the card records it from here, and what the stream skips is backfilled off the card",
                        self.serial, behind, self.frames.reach())
        elif self.lag and behind <= bound / 2 and now - self._lag_at >= 2 * GATE_NOTICE:
            self.lag = False
            log.info("camera %s: its stream is %.0f s behind again: the uplink carries it", self.serial, behind)
        return self.lag

    def _paid(self, t0: float, t1: float) -> None:
        """The server has `[t0, t1)` now — an ingest took it in the stream, or a range of the card was uploaded whole:
        merged into what touches it; past `DELIVERED_KEPT` stretches the oldest is forgotten, and `since` moves past it
        (what is older is nobody's to say, as what was on the card before this process began)."""
        if t1 <= t0:
            return
        merged: list[list[float]] = []
        for a, b in sorted(self.delivered + [[float(t0), float(t1)]]):
            if merged and a <= merged[-1][1] + DELIVERED_SEAM:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        if len(merged) > DELIVERED_KEPT:
            self.since = max(self.since, merged[-DELIVERED_KEPT - 1][1])
            merged = merged[-DELIVERED_KEPT:]
        self.delivered = merged

    def owed_spans(self) -> list[tuple[float, float]]:
        """What the card holds that the server has not got, as far as this pusher knows — from `since` on, everything
        but what was delivered: what the stream skipped, what it has not sent yet, a break. On the frames' line, which
        is the card's — and none of it past the road's last `have` (above). The card lets go of it last (`CardBuffer.owed`)."""
        out, at = [], self.since
        cap = self.have if self.have is not None else float("inf")
        for a, b in self.delivered:
            if a >= cap:
                break
            if a > at:
                out.append((at, a))
            at = max(at, min(b, cap))
        return out + [(at, float("inf"))]

    # WHAT THE SERVER HAS OUTLIVES THE CAMERA'S PROCESS (the tenth review, major). `since` was where this process began,
    # and what the card held from before it was "nobody's to say" — so it went FIRST when the card was full, and it was
    # exactly what a lagging stream had skipped and backfill had not taken yet: a camera started again in the middle of
    # it — 153 s on no copy at a budget of 200 MiB, `evicted_owed` nought, no alarm. Now what this pusher knows the
    # server has is kept on the card, in a note beside the segments (`CardRecorder.stream_delivery`, written every
    # `CardRecorder.NOTE_EVERY`), and the pusher of the next process takes it back when the card opens (`remember`):
    # `since` goes back to the note's, the stretches it lists join this process's own. Between the note's last word and
    # this process's start everything is owed — kept longer than it might be, never let go of unknowing.
    #
    # NO NOTE IS NOT "NOTHING OWED", AND A NOTE IS ONE CAMERA'S (the eleventh review, a minor). With no note — none, torn,
    # or lost to a rename a power cut undid — what the card held from before `since` was let go of first and uncounted;
    # and a card moved from another camera handed its note, and its footage, to this one. What lies before `since` is
    # unknown now (`unknown_before`, the card's `CardBuffer.unknown`): let go of in the same order, and counted
    # (`evicted_unknown_s` in the recorder's heartbeat). The note names the camera that wrote it (`serial`): another
    # camera's note is not taken, and what the card holds from before this process is not offered as this camera's
    # (`foreign_before`, `_read_card`). A note without a serial is read as one this camera wrote.
    def delivery(self) -> dict:
        """What this pusher knows the server has, for the card's note: from `since` on, the stretches delivered."""
        self._follow()
        return {"serial": self.serial, "since": self.since, "delivered": [list(d) for d in self.delivered]}

    def unknown_before(self) -> float:
        """Where what this pusher knows of the server begins: the card's frames before it, nobody can say whether the
        server has (`CardBuffer.unknown`)."""
        self._follow()
        return self.since

    def remember(self, note) -> bool:
        """The card's note from the camera's process before this one (`delivery` as it wrote it): its `since` and the
        stretches it lists before this process began. A note that does not read is no note — logged; another camera's
        is not this camera's — logged, and the card's older footage is not offered as this camera's. A note of only a
        serial (`{"serial"}`: the card kept no note of what the server has, its line's note named whose card it is —
        `CardRecorder.remember_card`) says only that."""
        self._follow()
        try:
            if not isinstance(note, dict):
                raise TypeError("not an object")
            writer = note.get("serial")
            since = finite(note["since"]) if "since" in note or writer is None else None
            spans = [(finite(a), finite(b)) for a, b in note.get("delivered") or []]
        except PARSE_ERRORS as e:
            log.warning("camera %s: the card's note of what the server has does not read (%s): what the card holds from "
                        "before this process is counted as let go of unknowing when the card is full", self.serial, e)
            return False
        if writer is not None and str(writer) != self.serial:
            if self.foreign_before is None:
                self.foreign_before = self.since
            log.warning("camera %s: its card was written by another camera (%s): what it holds from before this process is "
                        "not offered as this camera's footage, and is counted as let go of unknowing when the card is full",
                        self.serial, str(writer)[:64])
            return False
        if since is None or since >= self.since:
            return False
        began, self.since = self.since, since
        for a, b in spans:
            if a < began:
                self._paid(a, min(b, began))
        log.info("camera %s: the card remembers what the server had from %.0f on: what it holds from before this process "
                 "is owed or delivered as it was", self.serial, since)
        return True

    def can_continue(self) -> bool:
        """Whether a break of this stream may be left to memory (`RecWorker.resumes`): not while it lags."""
        return not self.lag

    # `up`: an ingest takes the stream now — the last piece it was offered was taken, on the road it goes to (`pushing`,
    # set in `_took`, cleared when no road answers or nobody wants the stream). The console's `rec_stream_up` (the spec's
    # `stream_up`, «Архитектор» 2026-10-06): a camera polling, idle or broken off says 0.
    def said(self) -> dict:
        """What the camera's recorder says of the stream in its heartbeat (`CardRecorder.stream_said`): whether it goes,
        where, how far behind, whether the uplink carries it, and the seconds of it the stream did not carry
        (`continued`)."""
        c = dict(self.continued)
        steps = {k: v for k, v in self.frames.steps().items() if v}     # the camera's clock, taken up (`_timed`)
        return {"state": self.state, "up": self.pushing is not None, "road": self.road,
                "behind_s": round(self.behind(), 1), "lagging": self.lag,
                "cut_s": c["cut_s"], "left_s": c["left_s"], "failed_s": c["failed_s"], "failed": c["failed"],
                **({"failed_why": c["failed_why"]} if c["failed_why"] else {}), **steps}

    # The next piece from the cursor: off the card while the stream is behind what memory holds — after a break that
    # memory does not reach back to, and when memory let go of frames the uplink had not sent yet (a camera's ring at a
    # high bitrate holds less than the stream may lag) — read one piece at a time, kept open across passes; then out of
    # memory. The card's part joins memory in the middle of a group of pictures only when it reached it (its last frame
    # ends where memory begins); a card that could not be read, that holds less, or no card at all leaves a hole, and
    # after a hole the stream starts on a key frame. What is missing is backfill's — and said (`_card_failed`, `_hole`).
    #
    # `_card`: None — no read under way; a dict — a read, `upto` where memory began when it was opened; "done" — the
    # last read ended, and a new one is opened only if memory moves past the cursor again; "failed" — the card failed,
    # and is not asked again until the next break.
    def _next_piece(self, room: int = PIECE_BYTES) -> tuple[list, bool]:
        after, joined = self.cursor
        room = max(1, min(PIECE_BYTES, room))
        oldest = self.frames.oldest()
        while self._card != "failed" and after is not None and not joined and (oldest is None or after < oldest - 0.002):
            upto = oldest if oldest is not None else self.clock()
            try:
                if not isinstance(self._card, dict):
                    # A break's first read starts at `after` on a keyframe; any later one goes on from a keyframe a little
                    # before the last frame sent, and drops what was sent — the stream is contiguous there.
                    first = self.resuming and self._card is None
                    self._card = {"pieces": iter(self._read_card(self.recording, after if first else after - _CARD_BACK,
                                                                 upto, PIECE_BYTES)),
                                  "upto": upto, "started": not first, "end": after,
                                  # what the next frame must follow (`_follows`): the last frame sent — none for a
                                  # break's first read, which starts on a key frame
                                  "prev": None if first else self._sent_end, "skip": first}
                piece = next(self._card["pieces"], None)
            except OSError as e:
                self._card_failed(e, after, upto)
                break
            if piece is None:
                reached, oldest = self._card["end"], self.frames.oldest()
                if oldest is not None and reached >= oldest - 0.002:  # it reached memory: no hole between them
                    self._card = "done"
                    return self.frames.piece(after, room, joined=True)[0], False
                moved = self._card["started"] and oldest is not None and oldest > self._card["upto"] + 0.002
                self._card = "done"
                if moved:
                    continue                                           # memory moved on while the card was read: read on
                break
            out = self._follows([wire(s, ring=True) for s in piece if unix_s(s.begin) > after])
            if out:
                self._card["started"], self._card["end"] = True, unix_s(piece[-1].end)
                return out, True
        piece, whole = self.frames.piece(after, room, joined=joined)
        if piece and not whole and after is not None and not self._hole_said and _t(piece[0]) > after:
            self._hole(after, _t(piece[0]))
        self._hole_said = False
        return piece, False

    # A HOLE NOBODY PLANNED IS SAID TOO. The stream goes on past a hole from the next keyframe — and a hole is planned
    # where the stream begins after a break older than it reaches (`left_s`), where the card failed (`failed_s`) and
    # where the pusher cut to the live edge (`cut_s`). Two more come by themselves, and were silent: the card's part of a
    # break ended before memory begins (it holds less — it opened late, it was slow), and memory let go of frames the
    # uplink had not sent yet (a camera's ring at a high bitrate holds less than `lag_limit`). Counted, and logged.
    def _hole(self, t0: float, t1: float) -> None:
        gap = t1 - t0
        if self.resuming:
            self.continued["failed"] += 1
            self.continued["failed_s"] = round(self.continued["failed_s"] + gap, 1)
            self.continued["failed_why"] = "the card holds less of the break than memory lacks"
            log.warning("camera %s: the card's part of a break ends %.0f s before memory begins: not in the stream; "
                        "backfill asks the card for them later", self.serial, gap)
        else:
            self.continued["cut_s"] = round(self.continued["cut_s"] + gap, 1)
            log.warning("camera %s: its stream fell behind and memory let go of %.0f s before they were sent (the uplink "
                        "does not carry the stream); backfill asks the card for them later", self.serial, gap)

    # A HOLE ON THE CARD IS A HOLE IN THE STREAM (the eighth review's sibling: the product's live loop had no hole check,
    # and the server took the frames after a hole as if they followed). Every frame read off the card must begin where
    # the one before it ended — the last frame sent, for the first of a read that goes on (`_sent_end`), with half a
    # frame's length of slack; a record with no length is not checked. One that begins later is a hole the card has — a
    # queue it dropped, a hold that closed its segment — and the stream goes on from the next key frame, the seconds
    # said (`_card_hole`): nothing can fill them, the card is the last copy. A break's first read starts on a key frame.
    def _follows(self, out: list) -> list:
        c, kept = self._card, []
        for f in out:
            s, prev = f["sample"], c["prev"]
            if prev is not None and s.begin > prev[0] + prev[1]:
                self._card_hole(unix_s(s.begin) - unix_s(prev[0]))
                c["skip"] = True
            c["prev"] = (s.end, max(1, (s.end - s.begin) // 2)) if s.end > s.begin else None
            if c["skip"] and not f["key"]:
                continue                                               # never mid-GOP after a hole, or at a break's start
            c["skip"] = False
            kept.append(f)
        return kept

    def _card_hole(self, gap: float) -> None:
        self.continued["failed"] += 1
        self.continued["failed_s"] = round(self.continued["failed_s"] + gap, 1)
        self.continued["failed_why"] = "the card has a hole where the stream goes on"
        log.warning("camera %s: the card has a hole of %.1f s where the stream goes on off it: those seconds are on no "
                    "copy; the stream goes on from the next key frame", self.serial, gap)

    # THE CARD'S ERROR IS SAID (the seventh review: `except OSError: reached = have` swallowed it — two recordings on the
    # card and a pusher not told which, a break of ten minutes, nothing off the card, and neither a log line nor a
    # failed range). Logged, counted, and the seconds the card could not give are in the pusher's state.
    def _card_failed(self, e: OSError, after: float, upto: float) -> None:
        self._card, self._hole_said = "failed", True
        self.continued["failed"] += 1
        self.continued["failed_s"] = round(self.continued["failed_s"] + max(0.0, upto - after), 1)
        self.continued["failed_why"] = str(e)
        log.warning("camera %s: a break could not be continued off the card (%s): %.0f s of it are not in the stream; "
                    "backfill asks the card for them later", self.serial, e, upto - after)

    def _read_card(self, recording, t0: float, t1: float, max_bytes: int = PIECE_BYTES):
        if self.card is None:
            raise OSError("this camera has no card")
        if self.foreign_before is not None and t0 < self.foreign_before:
            if t1 <= self.foreign_before:
                raise OSError("the card was written by another camera before this one began: its footage of that time "
                              "is not this camera's")
            t0 = self.foreign_before                                   # only what this camera wrote on it
        pieces = self.card(recording, t0, t1, max_bytes)
        spans = [(lo, hi) for lo, hi in self.frames.unplaced() if lo <= t1 and hi > t0]
        return self._placed(pieces, spans) if spans else pieces

    # FRAMES WITH NO CAPTURE TIME ARE NOT ANSWERED (the thirteenth review, blocker 7). The frames of unset boots the set
    # clock could not place (`vms.card.CamLine.unplaced`) lie on the card where a guess put them — a boot's length or more
    # early — and read there they were another moment's pictures in the hole. A range leaves them out: what is left of
    # the answer is placed, and the frames left out are counted (`unplaced_left`) and logged.
    def _placed(self, pieces, spans):
        left = 0
        for piece in pieces:
            kept = [s for s in piece if not any(lo <= unix_s(s.begin) < hi for lo, hi in spans)]
            left += len(piece) - len(kept)
            if kept:
                yield kept
        if left:
            self.unplaced_left += left
            log.warning("camera %s: %d frames of a range were captured in a boot whose clock was never set: they have no "
                        "capture time, and are left out of the answer", self.serial, left)

    def _poll(self, road: dict, key: str, wait: float):
        """The first ingest of a road that answers, and what it said — or (None, None)."""
        for url in road["urls"]:
            try:
                ing = self.dial(url)
                work = self._request(ing.poll, road["token_secret"], self.serial, version=self.versions.get(key, -1), wait=wait,
                                     held=wait > 0)
                self.versions[key] = work["version"]
                told = work.get("ranges") or {}
                self._told = {rid: k for rid, k in self._told.items() if k[0] != key or rid in told}
                for rid in told:
                    self._told.setdefault(rid, (key, self._moved))
                return ing, work, url
            except Unreachable:
                continue
        return None, None, None

    # One road's work: a range piece the ingest did not acknowledge, first (one piece of the card in memory at a time,
    # never two); the stream; the ranges; the asks. The first `Unreachable` ends the road's work for this pass — and
    # changes nothing that was not confirmed.
    def _serve(self, ing, token: str, work: dict, loose: list, key: str) -> tuple[int, list, list, bool]:
        pushed, uploaded, performed = 0, [], []
        try:
            self.have = None if work.get("have") is None else finite(work["have"])
        except PARSE_ERRORS:
            self.have = None
        ok = self._resend(ing, token, work)
        if ok and work["push"]:
            pushed, ok = self._push(ing, token, work, loose, key)
        if ok:
            uploaded, ok = self._uploads(ing, token, work)
        if ok:
            performed, ok = self._answer(ing, token, work)
        return pushed, uploaded, performed, ok

    def _push(self, ing, token: str, work: dict, loose: list, key: str) -> tuple[int, bool]:
        now = self.clock()
        self._follow()                                                 # (below: a look may have moved the line)
        self._left = 0.0
        self._peak = self.behind()                                     # how far behind the pass begins (`_judge_lag`)
        self._start(work, now)
        self._peak = max(self._peak, self.behind())
        # This pass's own frames and a piece of the backlog on top — two pieces at the most: a pass that took long (an
        # uplink below the stream) is not followed by a longer one; the next pass does not hold its poll (`busy`).
        allowance = min(PIECE_BYTES + self.frames.weight(self.seen), 2 * PIECE_BYTES)
        pushed = sent_bytes = 0
        while sent_bytes < allowance:
            # The camera's clock is looked at BEFORE the piece is read, and the move it may make is followed before the
            # stream's place is used (the twelfth review's sibling, found with blocker 12): a look that finds the clock set
            # moves the line (`CamLine._set`). A piece read before it went with a `camera_now` on the moved line — four
            # frames on the old one at the new offset, ten seconds early; and `_start`, comparing the cursor on the old line
            # with the clock on the new, took the stream for fallen behind by the set and cut it to the newest key frame —
            # the frames before it never sent, counted as `cut_s`.
            self.clock()
            self._follow()
            piece, off_card = self._next_piece(allowance - sent_bytes)
            if not piece:
                break
            out = [f if off_card or self.live_from is None or _t(f) > self.live_from else dict(f, ring=True)
                   for f in piece]
            try:
                self._request(ing.push, token, self.serial, out)
            except Unreachable:
                return pushed, False                                   # nothing moves: the next road gets it all
            self._took(key, piece)
            pushed += len(out)
            sent_bytes += sum(_weight(f) for f in piece)
            if self.resuming:
                self.resumed += sum(1 for f in out if f.get("ring"))
                if self.live_from is None or self.sent > self.live_from:
                    self.resuming = False                              # the break is sent: what follows is live
        if loose and self.behind() <= 0:
            try:
                self._request(ing.push, token, self.serial, list(loose))
            except Unreachable:
                return pushed, False
            self._took(key, [])
            pushed += len(loose)
        return pushed, True

    def _took(self, key: str, piece: list) -> None:
        """An ingest TOOK this piece: only now does the stream's state move."""
        if self.broken_at is not None:
            self.continued["left_s"] = round(self.continued["left_s"] + self._left, 1)   # the break is over: what it left, said
            self.broken_at = None
        self.pushing = key
        if piece:
            s = piece[-1].get("sample") if isinstance(piece[-1], dict) else None
            self._paid(_t(piece[0]), unix_s(s.end) if _is_sample(s) and s.end > s.begin else _t(piece[-1]))   # (`owed_spans`)
            self.sent = _t(piece[-1])
            self.cursor = (self.sent, False)
            self._sent_end = (s.end, max(1, (s.end - s.begin) // 2)) if _is_sample(s) and s.end > s.begin else None

    def _resend(self, ing, token: str, work: dict) -> bool:
        for rid in [r for r in self.uploading if r not in work["ranges"]]:
            del self.uploading[rid]                                    # handed over, given up, or forgotten there
        for rid, u in list(self.uploading.items()):
            if u["piece"] is not None:
                return self._upload_piece(ing, token, rid, u)[1]
        return True

    # One range of the card, answered (the sixth review), A PIECE AT A TIME ACROSS PASSES (the seventh review). The
    # request names the recording and the size of a piece; the card is read a piece at a time and each piece is
    # uploaded before the next is read — `more` on every one of them, and an upload with nothing in it and no `more` to
    # say the answer is whole. A pass sends at most a piece's worth of answers (`PIECE_BYTES`) and goes on with the
    # range next pass, where it stopped: an answer of thirty megabytes is thirty passes that each poll and push too,
    # not thirty megabytes in one. The ingest says, with every piece, whether anybody still waits.
    #
    # A PIECE NOT ACKNOWLEDGED IS SENT AGAIN, AS IT IS, UNDER ITS OWN NUMBER (the seventh review: a lost answer to piece
    # 3 and the camera started again from piece 0 — the ingest failed the range; at 5 % lost answers one range in ten
    # landed). The ingest takes a repeat of the piece it took last as a repeat (`Ingest.upload`). An error of the card at
    # ANY piece is said (`failed`), never answered as "that was all".
    #
    # BACKFILL TAKES WHAT THE STREAM LEAVES OF THE UPLINK (the ninth review, a minor: in a model with one uplink for both,
    # the ranges' pieces went beside a stream that was falling behind — `cut_s` 183 → 363 s, the lag coming back as soon
    # as it had gone). A camera has one uplink, and the live stream is first: a range's piece goes only when this pass's
    # push left the stream at its live edge — less than `UPLINK_FREE` behind its newest frame — and never while it lags.
    # So backfill takes what is left over: on an uplink of 1.5 × the stream the stream stays a couple of seconds behind
    # and the ranges go in between; below the stream's bitrate they wait. The ingest waits for a range's next piece as
    # long as a piece takes, and the server's backfill does not ask a camera that says its stream lags at all
    # (`RecWorker.backfill`). What the stream skipped stays on the card meanwhile, the last thing it lets go of
    # (`owed_spans`).
    def uplink_free(self) -> bool:
        return not self.lag and (self.pushing is None or self.behind() < UPLINK_FREE)

    def _uploads(self, ing, token: str, work: dict) -> tuple[list, bool]:
        ranges = work["ranges"] if self.uplink_free() else {}
        done, budget = [], PIECE_BYTES
        for rid, r in ranges.items():
            if budget <= 0:
                break
            u = self.uploading.get(rid)
            if u is None:
                t0, t1 = r["from"], r["to"]
                piece = min(int(r.get("piece") or PIECE_BYTES), PIECE_BYTES)
                try:
                    stale = self._stale_range(rid, t0)
                    if stale is not None:
                        raise OSError(stale)
                    pieces = iter(self._read_card(r.get("recording") or self.recording, t0, t1, piece))
                except OSError as e:
                    if not self._range_failed(ing, token, rid, t0, t1, e):
                        return done, False
                    continue
                u = self.uploading[rid] = {"pieces": pieces, "seq": 0, "piece": None, "from": t0, "to": t1}
            while budget > 0 and rid in self.uploading:
                if u["piece"] is None:
                    try:
                        u["piece"] = next(u["pieces"], _END)
                    except OSError as e:                               # the card's error is said, never answered as empty
                        del self.uploading[rid]
                        if not self._range_failed(ing, token, rid, u["from"], u["to"], e):
                            return done, False
                        break
                size, final = (0 if u["piece"] is _END else sum(len(s.body) for s in u["piece"])), u["piece"] is _END
                landed, ok = self._upload_piece(ing, token, rid, u)
                if not ok:
                    return done, False
                budget -= size
                if landed:
                    done.append((u["from"], u["to"]))
                    self._paid(u["from"], u["to"])
                if final or landed:
                    break
        return done, True

    def _upload_piece(self, ing, token: str, rid: str, u: dict) -> tuple[bool, bool]:
        """`(landed, ok)`: the range's pending piece uploaded — or its end said. Not ok: not acknowledged, kept."""
        try:
            if u["piece"] is _END:
                self._request(ing.upload, token, self.serial, rid, [], seq=u["seq"])
            elif not self._request(ing.upload, token, self.serial, rid, u["piece"], more=True, seq=u["seq"]):
                self.uploading.pop(rid, None)                          # nobody waits for it any more
                return False, True
        except Unreachable:
            return False, False
        if u["piece"] is _END:
            self.uploading.pop(rid, None)
            return True, True
        u["seq"], u["piece"] = u["seq"] + 1, None                      # let go BEFORE the next is read: one piece, not two
        return False, True

    def _range_failed(self, ing, token: str, rid: str, t0: float, t1: float, e: OSError) -> bool:
        try:
            self._request(ing.upload, token, self.serial, rid, [], failed=str(e))
        except Unreachable:
            return False                                               # said again next pass: the range is still asked
        self.failed_ranges.append((t0, t1, str(e)))
        self.ranges_failed += 1
        return True

    def _answer(self, ing, token: str, work: dict) -> tuple[list, bool]:
        asks = work.get("asks", {})
        for aid in [a for a in self._outcomes if a not in asks]:
            del self._outcomes[aid]                                    # answered, or expired there
        performed = []
        for aid, a in asks.items():
            outcome = self._outcomes.get(aid)
            if outcome is None:                                        # performed ONCE, however often it is answered
                outcome = self._outcomes[aid] = ("expired" if a["deadline"] <= self.clock()   # too late: not done
                                                 else self.perform(a["action"]))
            try:
                ing.answer_ask(token, self.serial, aid, outcome)
            except Unreachable:
                return performed, False
            self._outcomes.pop(aid, None)
            performed.append((a["action"], outcome))
        return performed, True

    def pass_once(self, frames_now: list, wait: float = 0.0) -> dict:
        """One pass. `wait`: how long the poll may be held when nothing changed — the camera's long poll; never while
        the pass has work left over (`busy`).

        Two roads when the camera has a backup on another server (М11 lesson 1): the PRIMARY's ingest, and
        the backup's. One stream, never two — the camera pushes to the backup when, and only when, the primary
        does not take it: no ingest of the primary answers, or the book says the primary should be written and
        is not (and is not merely starting). The stream goes on, on whichever road, from the last frame an ingest
        took."""
        loose = [f for f in frames_now if _t(f) is None]                # frames with no time: this pass's, or nobody's
        self.frames.add([f for f in frames_now if _t(f) is not None])
        self._follow()
        try:
            return self._pass(loose, wait)
        finally:
            self.seen = self.frames.newest()

    def _pass(self, loose: list, wait: float) -> dict:
        e = self.entry()
        if not e or not e.get("ingest"):
            self.state = "no book yet" if not e else "recorded in its own cluster: nothing to push"
            return {"state": self.state}
        backup = e.get("backup")
        ing, work, url = self._poll(e["ingest"], "primary", 0.0 if backup or self.busy() else wait)
        pushed, uploaded, performed, road = 0, [], [], None
        takes = primary_takes(e, ing is not None, work)
        # What the card (edge) goes by, decided HERE and now: the primary does not take the stream — its ingest
        # did not answer, or said the recording is uncovered, or (with no word from it) the book says so.
        self.uncovered = not takes if ing is None or "uncovered" in (work or {}) or backup else None
        if ing is not None:
            p, u, a, ok = self._serve(ing, e["ingest"]["token_secret"], work if takes else {**work, "push": False}, loose,
                                      "primary")
            pushed, uploaded, performed = p, u, a
            if takes and ok:
                road = ("primary", url, work["push"])
        if road is None and backup:
            bing, bwork, burl = self._poll(backup["ingest"], "backup", 0.0 if self.busy() else wait)
            if bing is not None:
                p, u, a, ok = self._serve(bing, backup["ingest"]["token_secret"], bwork, loose, "backup")
                pushed, uploaded, performed = pushed + p, uploaded + u, performed + a
                if ok:
                    road = ("backup", burl, bwork["push"])
        if road is None:
            if self.pushing is not None and self.broken_at is None:
                self.broken_at = self.sent if self.sent is not None else self.clock()   # it broke while pushing (CB)
            self.pushing, self._card = None, None
        elif not road[2]:                                              # back, and nobody wants it now: nothing to continue
            self.broken_at, self.cursor, self.pushing, self._card, self.resuming = None, None, None, None, False
        behind = self.behind()
        if behind <= 0:
            self.catching = False
        if self._judge_lag(self.clock()):
            self.uncovered = True                                      # the card writes what the stream cannot carry
        said = {"continue": dict(self.continued), "behind": round(behind, 1), "lagging": self.lag}
        if road is None:
            at = e["cluster"] if e.get("polls_only") else e["recorded_by"]     # the book of polls, or of primaries
            self.state = f"no ingest of {at} answered" + (" nor of its backup" if backup else "")
            return {"state": self.state, "pushed": pushed, "uploaded": uploaded, "asks": performed, **said}
        which, where, pushing = road
        self.road = which
        lagging = (f" — {behind:.0f} s behind: the uplink does not carry the stream; the card records it" if self.lag else
                   f" — catching up after a break, {behind:.0f} s behind" if self.catching and behind >= 1.0 else
                   f" — {behind:.0f} s behind" if behind >= 1.0 else "")
        self.state = (f"pushing to {where}" + (" — the backup: the primary does not take the stream" if which == "backup" else "")
                      + lagging
                      if pushing else
                      f"polling {where}: nobody records it, asks only" if e.get("polls_only") else
                      f"idle at {where}: nobody wants the stream")
        return {"state": self.state, "pushed": pushed, "uploaded": uploaded, "asks": performed, "road": which, **said}


def live_road(entry: dict, dial) -> str | None:
    """Where a viewer of this camera opens its stream: the road the camera is pushing on — by the same rule the
    camera follows (`primary_takes`). "primary", "backup", or None when neither answers. A gateway on either
    server asks this and opens the matching ingest, so its want lands where the one stream goes."""
    def answers(road):
        for url in road["urls"]:
            try:
                dial(url)
                return True
            except Unreachable:
                continue
        return False
    if primary_takes(entry, answers(entry["ingest"])):                 # (the ingest's own word reaches the camera,
        return "primary"                                               # not the gateway: the book stands in for it)
    backup = entry.get("backup")
    return "backup" if backup and answers(backup["ingest"]) else None


def primary_takes(entry: dict, answered: bool, work: dict | None = None) -> bool:
    """Whether the camera's primary takes its stream. First what its ingest SAID — no answer, or "uncovered"
    (it should record and no recorder takes it): the primary's own word, fresh, and no domain in it. Only when
    the ingest says nothing about it, the book: it should be written and is not — a stop, not a start (feedback
    AB): a start has its grace."""
    if not answered:
        return False
    if work is not None and "uncovered" in work:
        return not work["uncovered"]
    return not (entry.get("should") and not entry.get("written") and not entry.get("starting") and entry.get("backup"))


# -- the standbys' gates: what the stream says (vms.recworker.RecWorker.stream_says) -------------------------
def should_from_snapshot(objects, wall=time.time, sources=None):
    """`should(ref)` for an ingest, from its own cluster's rec rows: a recording of `ref:<ref>`, enabled, its
    `until` not passed, and not itself a standby. `sources`: this cluster's Variables, where its agent keeps the
    source book — and then only a camera that PUSHES here (`ingest://`) is answered. Every member camera holds a
    poll (feedback AL), a camera this cluster's recorder pulls over RTSP too; no recorder subscribes to the ingest
    for it, and "uncovered" would be said of a camera that is being written — its card would record all the
    time, and with a backup it would push a second stream (feedback AP). Of those the ingest says nothing.

    Read past what does not parse (the eighth review's sibling): a source entry that does not is "not ours to say";
    a snapshot shard that does not is the shard read last; a row whose `until` is not a number is left out — each
    counted once (`BOOKS`). One of them raised out of every poll at this ingest."""
    shards: dict[str, list] = {}                             # shard -> its recordings, as read last

    def recordings(v) -> list:
        rows = v.get("recordings", [])
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise TypeError("its recordings are not a list of rows")
        return rows

    def should(ref) -> bool | None:
        if sources is not None:
            from .keys import SOURCES_PATH
            items, _ = sources.get(SOURCES_PATH)
            raw = (items or {}).get(str(ref))
            e = BOOKS.read(f"{SOURCES_PATH}/{ref}", lambda: _an_object(json.loads(raw)), {}) if raw else {}
            if not str(e.get("live_url", "")).startswith("ingest://"):
                return None                                  # pulled, or not ours to say: the book decides
        rows = []
        for key in objects.list("rec/snapshot/"):
            raw = objects.get(key)
            if raw:
                got = BOOKS.read(key, lambda: recordings(json.loads(raw)))
                if got is not None:
                    shards[key] = got
            rows += [(key, r) for r in shards.get(key, [])
                     if str(r.get("cam")) == f"ref:{ref}" and str(r.get("when") or "") != "offline"]
        now, said = wall(), []
        for key, r in rows:
            until = FIELDS.read(f"{key}#{r.get('id')}.until", lambda: finite(r.get("until") or 0))
            if until is not None:
                said.append(bool(r.get("enabled", True)) and (until == 0 or until > now))
        return any(said) if said else None
    return should


def written_from_heartbeats(objects, wall=time.time, fresh: float = 45.0):
    """`written(ref)` for an ingest, from its own cluster's recorders: the furthest `written_through` a fresh
    recorder heartbeat says for a recording of `ref:<ref>` — what the cluster's recorder has, whichever ingest
    the camera comes back to, and whatever restarted meanwhile (feedback CB). A `written_through` that is not a number
    is not said (`rows.number`, counted once): it raised out of every poll and push at this ingest (the eighth review's
    sibling)."""
    from w2cplatform.console import heard_live, heartbeats
    from w2cplatform.contract import Eyes, judge_clock
    from w2cplatform.rows import number
    # A recorder fresh by what this ingest saw CHANGE (`Eyes`; the product's r29-writers2): `now - hb.ts` was the
    # recorder's clock against the ingest's — a dead recorder an hour ahead said its `written_through` for that hour.
    eyes = Eyes(judge_clock(wall), wall)

    def written(ref) -> float | None:
        now, best = wall(), None
        for name, hb in heartbeats(objects, "rec/").items():
            if not heard_live("rec", name, hb, now, fresh, eyes):
                continue
            for st in hb.status:
                if str(st.get("cam")) == f"ref:{ref}" and st.get("written_through") is not None:
                    at = number(f"rec/heartbeats/{name}#{st.get('id')}.written_through", st["written_through"], float, None)
                    # …and not one from the future (the ninth review's sibling of the frame from the future): the ingest
                    # drops every frame not newer than `have`, and a `written_through` of 1e300 would drop them all.
                    if at is not None and at <= now + FRAME_AHEAD:
                        best = max(best or float("-inf"), at)
        return best
    return written


def backup_gate(ingest):
    """The backup on the second server, fed by a camera that pushes: the camera came HERE — it does so only when
    its primary does not take the stream — so write what arrives. Otherwise it cannot say: the book decides."""
    return lambda row: True if ingest.pushing(str(row["cam"])[4:] if str(row["cam"]).startswith("ref:") else row["cam"]) else None


def edge_gate(pusher):
    """The card in the camera: the camera itself knows whether its primary takes its stream — and whether its uplink
    carries it (`CameraPusher.lag`: a lagging stream is uncovered, the eighth review)."""
    return lambda row: pusher.uncovered


def edge_resumes(pusher):
    """`RecWorker.resumes` for the card in a camera that pushes: a break may be left to memory for a while — unless the
    stream lags, and then what it skips must be on the card at once."""
    return lambda row: pusher.can_continue()


# -- the camera's process: its pusher and its card's recorder, tied in one call -------------------------------------
# THE HOOKS ARE ONE CALL, AND IT IS THE CAMERA'S (the tenth review, major: "without `stream_said` and `stream_owed` the
# card is FIFO again" — nothing in the course set them outside the tests, and a firmware that set one and not the other
# had the card let go of its oldest first, silently). The camera's process builds its ring, its card's recorder
# (`vms.card.CardRecorder`) and its pusher, and ties them here: the card's gate goes by the stream (`edge_gate`,
# `edge_resumes`), the recorder's heartbeat says the stream (`said`), the card lets go last of what the server has not got
# (`owed_spans`) and keeps on itself what the server has (`delivery`, `remember`), and the pusher reads ranges and breaks
# off the card through the recorder (`answer_range`). A recorder left half wired by hand says so in its heartbeat.
def tie(pusher: CameraPusher, recorder) -> CameraPusher:
    """`pusher` and `recorder` (the camera's `CardRecorder`), told of each other: every hook, in one call."""
    recorder.stream_says, recorder.resumes = edge_gate(pusher), edge_resumes(pusher)
    recorder.stream_said, recorder.stream_owed = pusher.said, pusher.owed_spans
    recorder.stream_unknown = pusher.unknown_before                    # …and before what it knows (the eleventh review)
    recorder.stream_delivery, recorder.stream_remember = pusher.delivery, pusher.remember
    if getattr(recorder, "actuator", None) is not None:
        recorder.actuator.serial = pusher.serial                       # whose line the card keeps (the twelfth review),
        recorder.actuator.note_line(force=True)                        # …said on a card open already — and a line gone on
                                                                       # from another camera's note taken back (13th)
    if pusher.card is None:
        pusher.card = recorder.answer_range
    recorder.remember_card()                                           # a card open already: what it kept, now
    return pusher


def camera_process(serial: str, flash, dial, recorder, **kw) -> CameraPusher:
    """The camera's pusher over its card recorder's ring and card, tied to the recorder (`tie`): what a camera's process
    starts beside its recorder. `kw` — `CameraPusher`'s own (`ring_seconds`, `hold_seconds`, `perform`, `recording`)."""
    return tie(CameraPusher(serial, flash, dial, card=recorder.answer_range, ring=recorder.ring, **kw), recorder)


def card_range(ingest, ref_of, wait: float | None = None):
    """`RecWorker.card_range` for a recorder of this cluster: a range of a camera's card, read by ASKING the camera
    through this ingest — the range goes in the answer to its poll, the camera uploads it (the product's
    `POST <ingest>/<ref>/range/<id>`). No door on the camera, no engine on it. `ref_of(src)`: the domain's name of
    the camera the source's recording is of. A range the camera could not read raises `RangeFailed` (an `OSError`):
    the recorder's copy fails, and its backfill asks again later — after a backoff (`RecWorker._source_answered`).

    The request NAMES the source's recording (`src["recording"]`): the card may hold several, and unnamed, a request
    for `2-card` was answered out of `1-card` — nothing in the range, remembered as "not on the card", never asked
    again (the sixth review). `wait`: how long each PIECE of the answer is waited for; unset, what a piece takes
    (`piece_wait`)."""
    return lambda src, t0, t1: ingest.fetch_range(ref_of(src), t0, t1, wait, recording=src.get("recording"))


# -- the asking camera -------------------------------------------------------------------------------------
from .keys import ASKS_PATH          # in the asking camera's cluster: whom it may ask, by which roads  # noqa: E402


class Asker:
    """The camera whose event fired: it leaves the ask at an ingest its book names for the target, calling OUT.
    The book lists roads nearest first — the cluster that records the target, then the level above that the
    target's cluster forwards to (Lesson 17) — each with its own token; the first ingest that answers takes it."""
    sealer = None                  # the ring its book's tokens are opened with: this process's (`keys.ring`) when None

    def __init__(self, serial: str, flash, dial, clock=None):
        self.serial, self.flash, self.dial, self.clock = str(serial), flash, dial, clock or time.time

    # ONE TORN ENTRY OF THE BOOK IS THAT TARGET'S (vmsserver's eleventh review, the half of the `publish_asks` major that
    # sits on the camera): the book was read whole with bare `json.loads`, and one torn `domain/asks` entry the agent
    # carried home raised out of `book()` — no ask to any target. Each entry is read through `BOOKS`: one that does not
    # parse is the one read last of it (`_last`), or none, counted once; the other targets are asked as before.
    def book(self) -> dict[str, list[dict]]:
        from .keys import opened
        items = opened(self.flash.get(ASKS_PATH)[0], ASKS_PATH, self.sealer)
        last = self.__dict__.setdefault("_last", {})

        def roads(raw):
            out = _an_object(json.loads(raw))["roads"]
            if not isinstance(out, list):
                raise TypeError("the roads are a list")
            for r in out:
                _a_road(r)
            return out
        book = {}
        for ref, raw in (items or {}).items():
            got = BOOKS.read(f"{ASKS_PATH}/{self.serial}/{ref}", lambda raw=raw: roads(raw))
            if got is not None:
                last[ref] = got
            if ref in last:
                book[ref] = last[ref]
        return book

    def ask(self, target: str, action: dict, within: float) -> tuple[object, str] | None:
        """Returns (the ingest, the ask's id) — or None when no ingest answered. The outcome is read with
        `outcome`, by the roads again: the ingest that took it may be another process by then."""
        roads = self.book().get(str(target))
        if not roads:
            raise Refused(f"{self.serial} may not ask {target}: no scenario ties them")
        for road in roads:
            for url in road["urls"]:
                try:
                    ing = self.dial(url)
                    return ing, ing.ask(road["token_secret"], target, action, self.clock() + within, camera_now=self.clock())
                except Unreachable:
                    continue
        return None

    def outcome(self, target: str, aid: str, deadline: float) -> str | None:
        """What became of an ask: performed, refused, expired — None while it may still come. Asks live in the
        ingest's memory, so an ingest that restarted knows nothing of one; past the deadline and a grace, an ask
        no ingest knows of is LOST, and said so — never waited for."""
        for road in self.book().get(str(target), []):
            for url in road["urls"]:
                try:
                    out = self.dial(url).ask_outcome(target, aid)
                except Unreachable:
                    continue
                if out is not None:
                    return out
        if self.clock() > deadline + ANSWER_GRACE:
            return "unknown: no ingest knows this ask — it restarted, or the ask was lost on the way"
        return None


def _finite_clock(camera_now) -> float:
    """The time a camera says it is, as a number — `nan` would make its offset, and every range on its clock, `nan`
    (the product found `X-Camera-Clock: NaN` did): refused."""
    try:
        return finite(camera_now)
    except (TypeError, ValueError, OverflowError):
        raise Refused(f"the camera's clock is a number of seconds, not {camera_now!r}") from None


def _round_trip(rtt) -> float | None:
    """How long the camera's last request took there and back, as it says (`rtt`; the twelfth review) — or None: it does
    not say, or says something that is no time. Only ever an excuse for a rise, never a reason for a move: a garbled one is
    none."""
    try:
        v = finite(rtt) if rtt is not None else None
    except PARSE_ERRORS:
        return None
    return v if v is not None and v >= 0 else None


def _urls(v: dict) -> None:
    """An ingest's announcement: its `urls`, a list of strings."""
    if not isinstance(v.get("urls"), list) or not all(isinstance(u, str) for u in v["urls"]):
        raise TypeError("its urls are not a list of addresses")


# -- the domain's side: the book of asks -----------------------------------------------------------------------
# For every scenario "an event on camera A acts on camera B", A's cluster gets the roads to B: the ingest of the
# cluster that records B and, when that cluster forwards B up (Lesson 17), the ingest above — with a token to
# ask B at each, naming the actions the scenarios allow (`acts`). `scenarios`: [{"trigger": ref A, "target":
# ref B, "actions": [...]}], from the shared settings (Lesson 12, `scenario.pairs`). A target nobody records
# polls the poll home (`Crossings.polled_at`).
def publish_asks(crossings, scenarios: list[dict], lifetime: float = 86400.0) -> dict[str, dict]:
    from .chain import UPSTREAM_PATH
    now, books = crossings.wall(), {}

    # What another cluster's ingest announced is read through the members' one reader (the review's eighth pass): a
    # torn announcement raised out of the whole book of asks — every camera's right to ask stopped being re-issued.
    # One that does not parse keeps the road the book already holds for that cluster (`old`), as the book of
    # primaries does (`Crossings._ingest`); a cluster that is silent gives no road, as before.
    def urls_of(cluster, old: dict | None = None):
        c = crossings.view.fed.clusters.get(cluster)
        try:
            raw = c.objects.get(INGEST) if c is not None else None
        except Unreachable:
            raw = None
        if not raw:
            return None
        said = published(cluster, INGEST, raw, _urls)
        return said["urls"] if said is not None else (old or {}).get("urls")

    dc = getattr(crossings.view.fed, "domain_holder", None)
    top = crossings.centre or (dc.name if dc is not None else None)      # where every relay's forwarder goes

    def road(old: dict | None, cluster: str, urls: list, sub: str, a: str, b: str, acts: list, up: str | None = None):
        if old and old["urls"] == urls and old.get("acts") == acts and old.get("up") == up \
                and float(old["until"]) - now > lifetime / 2 and kid_of(old.get("token_secret", "")) == crossings.issuer.kid:
            return old
        claims = {"aud": audience(cluster), "ask": b, "by": a, "acts": acts, **({"up": up} if up else {})}
        return {"cluster": cluster, "urls": urls, "until": now + lifetime, "acts": acts, **({"up": up} if up else {}),
                "token_secret": crossings.issuer.issue("ask", sub, now=now, **claims)}

    # ONE ENTRY OF A BOOK THAT DOES NOT PARSE IS THAT ENTRY'S (vmsserver's eleventh review, a major; a run): the entries
    # of the book of asks and of the upstream book were read bare, and `upstream/east[SN7001] = "{"` — the very entry the
    # chain's test tears — raised out of the whole of this, for every scenario: no token re-issued anywhere. Each entry
    # is read through `BOOKS` now (counted once, logged once, under `<book>/<entry>`): a torn entry of the book of asks
    # is issued anew — the old road is not there to keep — and a torn entry of the upstream book is "not pushed up".
    def roads_of(key: str, raw) -> dict:
        def parse():
            out = {}
            for r in _an_object(json.loads(raw))["roads"]:
                _a_road(r)
                finite(r["until"])
                out[str(r["cluster"])] = r
            return out
        return BOOKS.read(key, parse, {}) if raw else {}

    def upstream_of(key: str, raw) -> dict:
        def parse():
            v = _an_object(json.loads(raw))
            if v.get("mode") == "push":
                _urls(v)                                     # a road up is its addresses
            return v
        return BOOKS.read(key, parse, {}) if raw else {}

    for sc in scenarios:
        a, b = str(sc["trigger"]), str(sc["target"])
        acts = sorted((json.loads(json.dumps(x)) for x in sc.get("actions", [])), key=lambda x: json.dumps(x, sort_keys=True))
        known_a, on = crossings.view.last_known(a), crossings.polled_at(b)
        if known_a is None or on is None or crossings.issuer is None:
            continue
        home = known_a[0]
        via = crossings.via_of(home)                         # Lesson 17: this camera reaches only that relay
        have, _ = crossings.vars.get(f"{ASKS_PATH}/{home}")
        old = roads_of(f"{ASKS_PATH}/{home}/{b}", (have or {}).get(b))
        up, _ = crossings.vars.get(f"{UPSTREAM_PATH}/{on}")
        above = upstream_of(f"{UPSTREAM_PATH}/{on}/{b}", (up or {}).get(b))
        if via and on != via:
            # The target is in another relay. The only road this camera has is its own relay, marked UP; the
            # relay gets a token of its own for exactly this pair, to take it to the top — which must have a
            # road down to the target: it polls the top, or its relay forwards it there.
            ohave, _ = crossings.vars.get(f"{ASKS_PATH}/{via}")
            oold = roads_of(f"{ASKS_PATH}/{via}/{b}|{a}", (ohave or {}).get(f"{b}|{a}"))
            mine, theirs = urls_of(via, old.get(via)), urls_of(top, oold.get(top))
            if not (on == top or above.get("mode") == "push") or mine is None or theirs is None:
                continue
            roads = [road(old.get(via), via, mine, home, a, b, acts, up=top)]
            books.setdefault(via, {})[f"{b}|{a}"] = json.dumps(
                {"roads": [road(oold.get(top), top, theirs, via, a, b, acts)]}, sort_keys=True)
        else:
            # Its own relay (the only one it reaches), or — for a camera that reaches the centre — the cluster
            # where the target polls, then the centre that cluster forwards it to.
            wanted = [(on, urls_of(on, old.get(on)))]
            if not via and above.get("mode") == "push" and crossings.centre:
                wanted.append((crossings.centre, above["urls"]))
            roads = [road(old.get(cluster), cluster, urls, home, a, b, acts) for cluster, urls in wanted if urls]
        if roads:
            books.setdefault(home, {})[b] = json.dumps({"roads": roads}, sort_keys=True)
    for home, book in books.items():
        path = f"{ASKS_PATH}/{home}"
        have, idx = crossings.vars.get(path)
        if have != book:
            crossings.vars.put(path, book, cas=idx)
    # A scenario taken out of the document takes the right with it: a book nobody's scenario fills any more is
    # emptied, and the agent carries the empty book home. (A token already carried runs to its expiry — a day;
    # revoke it by its jti for sooner, as any token.)
    for path in crossings.vars.list(f"{ASKS_PATH}/"):
        if path[len(ASKS_PATH) + 1:] not in books:
            have, idx = crossings.vars.get(path)
            if have:
                crossings.vars.put(path, {}, cas=idx)
    return books
