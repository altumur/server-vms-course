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
                 camera states in every request, and moves a range request back onto the camera's. Stamped by
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
                 is a sample record (`w2cplatform.obsd.Sample`: archive ms, the key flag, the body) — as it lies
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

import dataclasses
import json
import logging
import secrets
import threading
import time
from dataclasses import dataclass, field

from vms.card import PIECE_BYTES       # what one piece of a camera's card may weigh: a share of the camera's memory
from vms.card import RING_BYTES        # …and the camera's ring: what a pusher with no camera ring keeps at most
from w2cplatform.obsd import archive_ms, unix_s

from .federation import Unreachable
from .gateway import Forbidden, LeakyQueue, LiveTee
from .tokens import TokenError, kid_of, verify

log = logging.getLogger("ingest")

INGEST = "rec/ingest"                  # the recording cluster's announcement: {"cluster", "urls", "ts"}
POLLED = "rec/polled"                  # `/<ingest>`: when each camera last polled here, as ages: {"cluster", "ingest", "ts", "cameras"}
LINGER = 10.0                          # how long a stream nobody wants any more keeps being asked for
# Asks (step 8). An outcome is kept this long for the asker to read — the product's automation remembers
# what it fired for as long (autoworker REMEMBER) — and then forgotten: an ingest's memory is not a log.
REMEMBER = 900.0
PEER_BUFFER = 50                       # frames one ingest holds for a peer that is not keeping up: two seconds (AJ)
MAX_LIVE_ASKS = 16                     # live asks one asking camera may hold at one ingest: a ceiling, not a queue
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
    A sample record off a camera's card (`w2cplatform.obsd.Sample`, archive ms) is moved the same way — on its own,
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
    parts: dict[str, tuple] = field(default_factory=dict)
    answers: dict[str, tuple] = field(default_factory=dict)
    failed: dict[str, tuple] = field(default_factory=dict)
    landed: list[tuple[float, float]] = field(default_factory=list)
    pushed_at: float | None = None
    offset: float = 0.0                                          # the cluster's clock minus the camera's
    asks: dict[str, dict] = field(default_factory=dict)          # asks for this camera: {id: {action, deadline, by}}
    outcomes: dict[str, tuple] = field(default_factory=dict)     # what became of each, and when: performed, refused, expired
    version: int = 0
    said: tuple | None = None                                    # what the last poll was told
    polled_at: float | None = None                               # when it last polled, on the cluster's clock


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
        # A recorder that lets go of a camera — or dies — wakes nobody: nothing here changes. So a held poll that
        # has a word to say about coverage looks again at least this often (feedback AP: the product does 5 s).
        self.recheck = 5.0
        self.linger = LINGER
        self.links: dict[tuple[str, str], PeerLink] = {}          # (peer, camera) -> the stream this ingest pushes it (AJ)
        self.pulled: dict[tuple[str, str], tuple[int, list]] = {}  # (camera, puller) -> the last batch pulled, numbered
        self.tees: dict[tuple[str, str], LiveTee] = {}
        self.cams: dict[str, _Camera] = {}
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
    # the domain reads them against the object's own `ts` and a clock difference cancels out.
    # One object per INGEST, not per cluster (feedback AZ): a cluster runs several (Lesson 16, step 7), each knows only
    # the cameras that poll it, and one shared object would be whichever wrote last.
    def publish_polled(self, objects) -> dict:
        now = self.wall()
        cams = {ref: round(now - c.polled_at, 3) for ref, c in self.cams.items() if c.polled_at is not None}
        key = f"{POLLED}/" + "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in self.name)
        objects.put(key, json.dumps({"cluster": self.cluster, "ingest": self.name, "ts": now, "cameras": cams}).encode())
        return cams

    def _cam(self, ref) -> _Camera:
        return self.cams.setdefault(str(ref), _Camera())

    def _cluster(self) -> list["Ingest"]:
        return [self, *[p for p in self.peers() if p is not self]]

    # -- the camera's side of the conversation ----------------------------------------------------------
    def _check(self, token: str, ref: str, camera_now: float | None = None) -> dict:
        ks = self.keys()
        if ks is None:
            raise Refused(f"{self.cluster}: no key set yet — is this cluster's agent running?")
        try:
            p = verify(token, ks, self.revoked(), now=self.wall(), kind="stream")
        except TokenError as e:
            raise Refused(f"stream token refused: {e}")
        if p.get("aud") != audience(self.cluster) or str(p.get("ref")) != str(ref):
            raise Refused(f"stream token is for {p.get('ref')} at {p.get('aud')}, not {ref} at {audience(self.cluster)}")
        if camera_now is not None:                               # every request says what time the camera thinks it is
            self._cam(ref).offset = self.wall() - float(camera_now)
        return p

    def poll(self, token: str, ref: str, camera_now: float | None = None, version: int | None = None,
             wait: float = 0.0) -> dict:
        """The camera's long poll: whether to push now, and which ranges to upload — ranges on the CAMERA's
        clock. Wants and requests at any ingest of this cluster count (AG). `version`: what the camera last saw;
        the same version is a poll the ingest HOLDS — up to `wait` seconds, answered the moment anything changes
        — and, if nothing did, answers with `held`."""
        until = time.monotonic() + wait
        while True:
            gen = self._gen
            out = self._poll_once(token, ref, camera_now, version)
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

    def _poll_once(self, token: str, ref: str, camera_now: float | None, version: int | None) -> dict:
        self._check(token, ref, camera_now)
        now, cam = self.wall(), self._cam(ref)
        cam.polled_at = now
        push, ranges, asks = False, {}, {}
        for ing in self._cluster():
            ing._forget(now)
            c = ing._cam(ref)
            c.wants = {w: u for w, u in c.wants.items() if u > now}       # a want that ran out wakes the poll (AF)
            push = push or bool(c.wants)
            ranges.update(c.ranges)
            c.outcomes = {k: v for k, v in c.outcomes.items() if now - v[1] < REMEMBER}
            for aid, a in list(c.asks.items()):
                if a["deadline"] <= now:                                  # dies at its deadline, never kept
                    c.outcomes[aid] = ("expired", now)
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
        out = {"push": push, "version": cam.version,
               "ranges": {rid: {"from": t0 - cam.offset, "to": t1 - cam.offset, "recording": rec, "piece": PIECE_BYTES}
                          for rid, (t0, t1, rec) in ranges.items()},
               "asks": {aid: {"action": a["action"], "by": a["by"], "deadline": a["deadline"] - cam.offset}
                        for aid, a in asks.items()}}
        if uncovered is not None:
            out["uncovered"] = uncovered
        have = self.written(ref) if self.written is not None else None
        if have is not None:
            # Not part of `said`: it moves with every frame written, and a poll held for news must not wake for it.
            out["have"] = float(have) - cam.offset
        if version is not None and version == cam.version:
            out["held"] = True                                   # nothing changed: the real ingest holds the request
        return out

    def push(self, token: str, ref: str, frames: list, camera_now: float | None = None) -> int:
        self._check(token, ref, camera_now)
        frames = _shift(frames, self._cam(ref).offset)
        have = self.written(ref) if self.written is not None else None
        if have is not None:
            # What the recorder already wrote does not go to it twice (CB). `have` is conservative — a heartbeat
            # old — so the writer still drops a frame not newer than its own last; this takes the bulk.
            frames = [f for f in frames if not (isinstance(f, dict) and "t" in f and float(f["t"]) <= have)]
        return self._take(ref, frames)

    def _take(self, ref: str, frames: list) -> int:
        live = self.tees.setdefault((str(ref), "live"), LiveTee(ref))
        edge = self.tees.setdefault((str(ref), "edge"), LiveTee(ref))
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
               failed: str | None = None, more: bool = False, seq: int = 0) -> bool:
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
        hears that the range is still wanted."""
        self._check(token, ref, camera_now)
        shifted, now, wanted = _shift(samples, self._cam(ref).offset), self.wall(), False
        for ing in self._cluster():
            c = ing._cam(ref)
            if rid not in c.ranges:
                continue
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
        """What nobody came for goes: an answer or a failure `ANSWER_KEPT` old, and a piece of an answer whose
        request is gone. Every poll and every request sweeps — as asks are swept (`_sweep`)."""
        for c in list(self.cams.values()):
            for kept in (c.answers, c.failed):
                for rid in [k for k, v in list(kept.items()) if now - v[1] >= ANSWER_KEPT]:
                    kept.pop(rid, None)
            for rid in [k for k in list(c.parts) if k not in c.ranges]:
                c.parts.pop(rid, None)

    # -- asks between cameras ---------------------------------------------------------------------------------
    def ask(self, token: str, target: str, action: dict, deadline: float, camera_now: float | None = None) -> str:
        """A camera asks `target` to do `action` before `deadline` (the asker's clock). The token is the domain
        signer's, for this ingest, naming the target in its `ask` claim — issued because a scenario ties the
        asker's event to the target's action. Kept only until the deadline."""
        ks = self.keys()
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
        for ing in self._cluster():
            ing._sweep(now)
        shift = 0.0 if camera_now is None else now - float(camera_now)
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
                    c.outcomes[aid] = ("expired", now)
                    c.asks.pop(aid, None)
            c.outcomes = {k: v for k, v in list(c.outcomes.items()) if now - v[1] < REMEMBER}

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
            self._cam(a["target"]).outcomes[aid] = (outcome, self.wall())
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
                del c.asks[aid]
                c.outcomes[aid] = (outcome, self.wall())
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
                for kept in (c.ranges, c.parts, c.answers, c.failed):
                    kept.pop(rid, None)

    def pull(self, token: str, ref: str, who: str, have: int | None = None) -> list:
        """Lesson 17, the star: a cluster that nobody can dial either — a relay behind a mobile operator's
        NAT, a cluster in a cloud that takes no inbound — takes the streams of ITS cameras from here, calling
        in. Each pull is wanting the stream for another `LINGER`; stop pulling, and the want runs out.

        A BATCH IS GONE FROM HERE ONLY WHEN THE PULLER HAS IT (the seventh review, the camera's rule one level up): the
        answer is numbered (`.seq`), and the puller says which number it last got (`have`). An answer lost on its way
        down — the drained frames gone with it — is handed over again, in front of what came since; as a stream,
        at most `PEER_BUFFER` frames of it, cut clean to a keyframe. `have` None: a puller that does not count."""
        self._check(token, ref)
        self.want(ref, who, until=self.wall() + self.linger)
        fresh = self.subscribe(ref, who).drain()
        if have is None:
            return fresh
        key = (str(ref), str(who))
        seq, last = self.pulled.get(key, (0, []))
        frames = fresh if int(have) == seq else last + fresh
        if len(frames) > PEER_BUFFER:
            frames = frames[-PEER_BUFFER:]
            while frames and not _is_key(frames[0]):
                frames.pop(0)
        self.pulled[key] = (seq + 1, frames)
        return _Batch(frames, seq + 1)

    def inject(self, ref: str, frames: list) -> int:
        """A stream arriving from this cluster's own forwarder or a peer ingest — already on this cluster's clock."""
        return self._take(ref, frames)

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
        return self.tees.setdefault((str(ref), "edge" if edge else kind), LiveTee(ref)).subscribe(who, maxsize)

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
        """Frames taken from a peer: to this ingest's subscribers, without counting as a camera pushing HERE."""
        live = self.tees.setdefault((str(ref), "live"), LiveTee(ref))
        edge = self.tees.setdefault((str(ref), "edge"), LiveTee(ref))
        for f in frames:
            live.push(f)
            if not _is_ring(f):
                edge.push(f)
        return len(frames)


def _is_key(frame) -> bool:
    """A frame a decoder can start from. A frame that says nothing (the tests' plain values) counts as one."""
    return not isinstance(frame, dict) or bool(frame.get("key", True))


class _Batch(list):
    """The frames of one pull, and its number (`seq`): what the puller says it has, next time (`Ingest.pull`)."""

    def __init__(self, frames, seq: int):
        super().__init__(frames)
        self.seq = seq


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
                ingest.tees.setdefault((str(camera), "edge"), LiveTee(camera)).unsubscribe(who)
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


class _OwnFrames:
    """What a pusher given no camera ring keeps itself: the course's model frames (dicts with `t`), in the order they
    were captured, for `window` seconds and at most `max_bytes` — the bounds of the camera's ring. A frame not newer
    than the newest held is not taken (`stale`): a capture clock goes forward."""

    def __init__(self, window: float, max_bytes: int, clock):
        self.window, self.max_bytes, self.clock = float(window), int(max_bytes), clock
        self.frames: list[dict] = []
        self.bytes = self.stale = 0

    def add(self, frames: list) -> None:
        for f in frames:
            if self.frames and _t(f) <= _t(self.frames[-1]):
                self.stale += 1
                continue
            self.frames.append(f)
            self.bytes += _weight(f)
        floor, drop = self.clock() - self.window, 0
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
_BEFORE = 0.001                        # a cursor just before a frame: the stream goes on from it, held or not, a keyframe first
_CARD_BACK = 10.0                      # a read of the card that goes on mid-group starts this far back: a keyframe is in it


class CameraPusher:
    def __init__(self, serial: str, flash, dial, card=None, clock=None, ring_seconds: float = 0.0, perform=None,
                 hold_seconds: float = 30.0, recording: str | None = None, ring=None):
        """`perform(action) -> outcome` carries out an ask from another camera (a preset, a relay) and says
        what happened: "performed", or "refused: <why>". `recording`: this camera's recording on its card — what a
        break is continued from (None: the card's one). `ring`: the camera's ring (`vms.card.CamRing`) — the frames
        it pushes; none, and it keeps the frames of the pass itself."""
        self.serial, self.flash, self.dial, self.card, self.recording = str(serial), flash, dial, card, recording
        self.failed_ranges: list[tuple[float, float, str]] = []        # ranges answered "could not read", and why
        self.perform = perform or (lambda action: "refused: this camera performs no actions")
        self.clock, self.ring_seconds = clock or time.time, ring_seconds
        self.versions: dict[str, int] = {}                             # per road; -1 first: answered at once (AF)
        self.pushing, self.road = None, None                           # the road it pushes on, if any
        self.uncovered: bool | None = None                             # the primary does not take the stream
        self.state = "no book yet"
        self.hold_seconds = hold_seconds
        self.frames = (_RingFrames(ring) if ring is not None else
                       _OwnFrames(max(hold_seconds, ring_seconds), RING_BYTES, self.clock))
        # WHERE THE STREAM STANDS — all the pusher keeps of it. `sent`: the capture time of the last frame an ingest
        # took. `cursor`: `(after, joined)`, where the next piece begins — past `after`, from a key frame unless the
        # frame at `after` is known to be followed with nothing missing. `live_from`: frames up to it are what came
        # before the push began (the event's ring, a break) — marked, for the recorder, never the viewer's live edge.
        # `broken_at`: the road was lost while pushing — `sent` then. `seen`: the newest frame when the last pass
        # ended: what is newer is this pass's own.
        self.sent: float | None = None
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
        self.uploading: dict[str, dict] = {}                           # ranges being answered, piece by piece
        self._outcomes: dict[str, str] = {}                            # asks performed and not yet acknowledged

    def entry(self) -> dict | None:
        """The book of primaries — or, for a camera nobody records, the book of polls: an ingest to poll for
        asks, never told to push (step 8)."""
        from .agent import POLL_PATH, PRIMARIES_PATH
        items, _ = self.flash.get(PRIMARIES_PATH)
        raw = (items or {}).get(self.serial)
        if raw:
            return json.loads(raw)
        items, _ = self.flash.get(POLL_PATH)
        raw = (items or {}).get(self.serial)
        if not raw:
            return None
        p = json.loads(raw)
        return {"cluster": p["cluster"], "polls_only": True,
                "ingest": {k: p[k] for k in ("urls", "token", "until")}}

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
                                  "upto": upto, "started": not first, "end": after}
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
            out = [wire(s, ring=True) for s in piece if unix_s(s.begin) > after]
            if not self._card["started"]:
                while out and not out[0]["key"]:
                    out.pop(0)                                         # a continuation starts on a keyframe, never mid-GOP
            if out:
                self._card["started"], self._card["end"] = True, unix_s(piece[-1].end)
                return out, True
        piece, whole = self.frames.piece(after, room, joined=joined)
        if piece and not whole and after is not None and not self._hole_said and _t(piece[0]) > after:
            self._hole(_t(piece[0]) - after)
        self._hole_said = False
        return piece, False

    # A HOLE NOBODY PLANNED IS SAID TOO. The stream goes on past a hole from the next keyframe — and a hole is planned
    # where the stream begins after a break older than it reaches (`left_s`), where the card failed (`failed_s`) and
    # where the pusher cut to the live edge (`cut_s`). Two more come by themselves, and were silent: the card's part of a
    # break ended before memory begins (it holds less — it opened late, it was slow), and memory let go of frames the
    # uplink had not sent yet (a camera's ring at a high bitrate holds less than `lag_limit`). Counted, and logged.
    def _hole(self, gap: float) -> None:
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
        return self.card(recording, t0, t1, max_bytes)

    def _poll(self, road: dict, key: str, wait: float):
        """The first ingest of a road that answers, and what it said — or (None, None)."""
        for url in road["urls"]:
            try:
                ing = self.dial(url)
                work = ing.poll(road["token"], self.serial, camera_now=self.clock(),
                                version=self.versions.get(key, -1), wait=wait)
                self.versions[key] = work["version"]
                return ing, work, url
            except Unreachable:
                continue
        return None, None, None

    # One road's work: a range piece the ingest did not acknowledge, first (one piece of the card in memory at a time,
    # never two); the stream; the ranges; the asks. The first `Unreachable` ends the road's work for this pass — and
    # changes nothing that was not confirmed.
    def _serve(self, ing, token: str, work: dict, loose: list, key: str) -> tuple[int, list, list, bool]:
        pushed, uploaded, performed = 0, [], []
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
        self._left = 0.0
        self._start(work, now)
        # This pass's own frames and a piece of the backlog on top — two pieces at the most: a pass that took long (an
        # uplink below the stream) is not followed by a longer one; the next pass does not hold its poll (`busy`).
        allowance = min(PIECE_BYTES + self.frames.weight(self.seen), 2 * PIECE_BYTES)
        pushed = sent_bytes = 0
        while sent_bytes < allowance:
            piece, off_card = self._next_piece(allowance - sent_bytes)
            if not piece:
                break
            out = [f if off_card or self.live_from is None or _t(f) > self.live_from else dict(f, ring=True)
                   for f in piece]
            try:
                ing.push(token, self.serial, out, camera_now=self.clock())
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
                ing.push(token, self.serial, list(loose), camera_now=self.clock())
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
            self.sent = _t(piece[-1])
            self.cursor = (self.sent, False)

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
    def _uploads(self, ing, token: str, work: dict) -> tuple[list, bool]:
        ranges = work["ranges"]
        done, budget = [], PIECE_BYTES
        for rid, r in ranges.items():
            if budget <= 0:
                break
            u = self.uploading.get(rid)
            if u is None:
                t0, t1 = r["from"], r["to"]
                piece = min(int(r.get("piece") or PIECE_BYTES), PIECE_BYTES)
                try:
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
                if final or landed:
                    break
        return done, True

    def _upload_piece(self, ing, token: str, rid: str, u: dict) -> tuple[bool, bool]:
        """`(landed, ok)`: the range's pending piece uploaded — or its end said. Not ok: not acknowledged, kept."""
        try:
            if u["piece"] is _END:
                ing.upload(token, self.serial, rid, [], camera_now=self.clock(), seq=u["seq"])
            elif not ing.upload(token, self.serial, rid, u["piece"], camera_now=self.clock(), more=True, seq=u["seq"]):
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
            ing.upload(token, self.serial, rid, [], camera_now=self.clock(), failed=str(e))
        except Unreachable:
            return False                                               # said again next pass: the range is still asked
        self.failed_ranges.append((t0, t1, str(e)))
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
            p, u, a, ok = self._serve(ing, e["ingest"]["token"], work if takes else {**work, "push": False}, loose,
                                      "primary")
            pushed, uploaded, performed = p, u, a
            if takes and ok:
                road = ("primary", url, work["push"])
        if road is None and backup:
            bing, bwork, burl = self._poll(backup["ingest"], "backup", 0.0 if self.busy() else wait)
            if bing is not None:
                p, u, a, ok = self._serve(bing, backup["ingest"]["token"], bwork, loose, "backup")
                pushed, uploaded, performed = pushed + p, uploaded + u, performed + a
                if ok:
                    road = ("backup", burl, bwork["push"])
        if road is None:
            if self.pushing is not None and self.broken_at is None:
                self.broken_at = self.sent if self.sent is not None else self.clock()   # it broke while pushing (CB)
            self.pushing, self._card = None, None
        elif not road[2]:                                              # back, and nobody wants it now: nothing to continue
            self.broken_at, self.cursor, self.pushing, self._card, self.resuming = None, None, None, None, False
        said = {"continue": dict(self.continued)}
        if road is None:
            self.state = f"no ingest of {e['cluster']} answered" + (" nor of its backup" if backup else "")
            return {"state": self.state, "pushed": pushed, "uploaded": uploaded, "asks": performed, **said}
        which, where, pushing = road
        self.road = which
        behind = self.behind()
        self.state = (f"pushing to {where}" + (" — the backup: the primary does not take the stream" if which == "backup" else "")
                      + (f" — catching up after a break, {behind:.0f} s behind" if behind >= 1.0 else "")
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
    time, and with a backup it would push a second stream (feedback AP). Of those the ingest says nothing."""
    def should(ref) -> bool | None:
        if sources is not None:
            from .agent import SOURCES_PATH
            items, _ = sources.get(SOURCES_PATH)
            e = json.loads((items or {}).get(str(ref), "{}"))
            if not str(e.get("live_url", "")).startswith("ingest://"):
                return None                                  # pulled, or not ours to say: the book decides
        rows = []
        for key in objects.list("rec/snapshot/"):
            raw = objects.get(key)
            rows += [r for r in (json.loads(raw).get("recordings", []) if raw else [])
                     if str(r.get("cam")) == f"ref:{ref}" and str(r.get("when") or "") != "offline"]
        if not rows:
            return None
        now = wall()
        return any(bool(r.get("enabled", True)) and (float(r.get("until") or 0) == 0 or float(r.get("until")) > now)
                   for r in rows)
    return should


def written_from_heartbeats(objects, wall=time.time, fresh: float = 45.0):
    """`written(ref)` for an ingest, from its own cluster's recorders: the furthest `written_through` a fresh
    recorder heartbeat says for a recording of `ref:<ref>` — what the cluster's recorder has, whichever ingest
    the camera comes back to, and whatever restarted meanwhile (feedback CB)."""
    from w2cplatform.console import heartbeats

    def written(ref) -> float | None:
        now, best = wall(), None
        for hb in heartbeats(objects, "rec/").values():
            if now - hb.ts > fresh:
                continue
            for st in hb.status:
                if str(st.get("cam")) == f"ref:{ref}" and st.get("written_through") is not None:
                    best = max(best or float("-inf"), float(st["written_through"]))
        return best
    return written


def backup_gate(ingest):
    """The backup on the second server, fed by a camera that pushes: the camera came HERE — it does so only when
    its primary does not take the stream — so write what arrives. Otherwise it cannot say: the book decides."""
    return lambda row: True if ingest.pushing(str(row["cam"])[4:] if str(row["cam"]).startswith("ref:") else row["cam"]) else None


def edge_gate(pusher):
    """The card in the camera: the camera itself knows whether its primary takes its stream."""
    return lambda row: pusher.uncovered


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
ASKS_PATH = "domain/asks"             # in the asking camera's cluster: whom it may ask, by which roads


class Asker:
    """The camera whose event fired: it leaves the ask at an ingest its book names for the target, calling OUT.
    The book lists roads nearest first — the cluster that records the target, then the level above that the
    target's cluster forwards to (Lesson 17) — each with its own token; the first ingest that answers takes it."""

    def __init__(self, serial: str, flash, dial, clock=None):
        self.serial, self.flash, self.dial, self.clock = str(serial), flash, dial, clock or time.time

    def book(self) -> dict[str, list[dict]]:
        items, _ = self.flash.get(ASKS_PATH)
        return {ref: json.loads(raw)["roads"] for ref, raw in (items or {}).items()}

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
                    return ing, ing.ask(road["token"], target, action, self.clock() + within, camera_now=self.clock())
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


# -- the domain's side: the book of asks -----------------------------------------------------------------------
# For every scenario "an event on camera A acts on camera B", A's cluster gets the roads to B: the ingest of the
# cluster that records B and, when that cluster forwards B up (Lesson 17), the ingest above — with a token to
# ask B at each, naming the actions the scenarios allow (`acts`). `scenarios`: [{"trigger": ref A, "target":
# ref B, "actions": [...]}], from the shared settings (Lesson 12, `scenario.pairs`). A target nobody records
# polls the poll home (`Crossings.polled_at`).
def publish_asks(crossings, scenarios: list[dict], lifetime: float = 86400.0) -> dict[str, dict]:
    from .chain import UPSTREAM_PATH
    now, books = crossings.wall(), {}

    def urls_of(cluster):
        c = crossings.view.fed.clusters.get(cluster)
        try:
            raw = c.objects.get(INGEST) if c is not None else None
        except Unreachable:
            raw = None
        return json.loads(raw)["urls"] if raw else None

    dc = getattr(crossings.view.fed, "domain_holder", None)
    top = crossings.centre or (dc.name if dc is not None else None)      # where every relay's forwarder goes

    def road(old: dict | None, cluster: str, urls: list, sub: str, a: str, b: str, acts: list, up: str | None = None):
        if old and old["urls"] == urls and old.get("acts") == acts and old.get("up") == up \
                and float(old["until"]) - now > lifetime / 2 and kid_of(old.get("token", "")) == crossings.issuer.kid:
            return old
        claims = {"aud": audience(cluster), "ask": b, "by": a, "acts": acts, "kind": "ask", **({"up": up} if up else {})}
        return {"cluster": cluster, "urls": urls, "until": now + lifetime, "acts": acts, **({"up": up} if up else {}),
                "token": crossings.issuer.issue(sub, lifetime, now=now, **claims)}

    for sc in scenarios:
        a, b = str(sc["trigger"]), str(sc["target"])
        acts = sorted((json.loads(json.dumps(x)) for x in sc.get("actions", [])), key=lambda x: json.dumps(x, sort_keys=True))
        known_a, on = crossings.view.last_known(a), crossings.polled_at(b)
        if known_a is None or on is None or crossings.issuer is None:
            continue
        home = known_a[0]
        via = crossings.via_of(home)                         # Lesson 17: this camera reaches only that relay
        have, _ = crossings.vars.get(f"{ASKS_PATH}/{home}")
        old = {r["cluster"]: r for r in json.loads((have or {}).get(b, '{"roads": []}'))["roads"]}
        up, _ = crossings.vars.get(f"{UPSTREAM_PATH}/{on}")
        above = json.loads((up or {}).get(b, "{}"))
        if via and on != via:
            # The target is in another relay. The only road this camera has is its own relay, marked UP; the
            # relay gets a token of its own for exactly this pair, to take it to the top — which must have a
            # road down to the target: it polls the top, or its relay forwards it there.
            if not (on == top or above.get("mode") == "push") or urls_of(via) is None or urls_of(top) is None:
                continue
            roads = [road(old.get(via), via, urls_of(via), home, a, b, acts, up=top)]
            ohave, _ = crossings.vars.get(f"{ASKS_PATH}/{via}")
            oold = {r["cluster"]: r for r in json.loads((ohave or {}).get(f"{b}|{a}", '{"roads": []}'))["roads"]}
            books.setdefault(via, {})[f"{b}|{a}"] = json.dumps(
                {"roads": [road(oold.get(top), top, urls_of(top), via, a, b, acts)]}, sort_keys=True)
        else:
            # Its own relay (the only one it reaches), or — for a camera that reaches the centre — the cluster
            # where the target polls, then the centre that cluster forwards it to.
            wanted = [(on, urls_of(on))]
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
