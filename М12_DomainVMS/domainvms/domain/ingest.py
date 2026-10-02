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
                 size takes, and the ingest forgets an answer the moment it has handed it over (the sixth review)
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
                 The camera starts its next push at the first keyframe after `have` — off its card, then out
                 of the ring it kept through the break — and nothing the recorder has goes twice; the
                 ingest drops what is not newer than `have`. Backfill is for minutes and hours (it plans
                 nothing fresher than its settle); a break of seconds is the stream's own business
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
import secrets
import threading
import time
from dataclasses import dataclass, field

from vms.card import PIECE_BYTES       # what one piece of a camera's card may weigh: a share of the camera's memory
from w2cplatform.obsd import unix_s

from .federation import Unreachable
from .gateway import Forbidden, LeakyQueue, LiveTee
from .tokens import TokenError, kid_of, verify

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
        waits for this range: False tells the camera to stop reading its card for a recorder that has given up."""
        self._check(token, ref, camera_now)
        shifted, now, wanted = _shift(samples, self._cam(ref).offset), self.wall(), False
        for ing in self._cluster():
            c = ing._cam(ref)
            if rid not in c.ranges:
                continue
            n, have, _ = c.parts.pop(rid, (0, [], 0.0))
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

    def pull(self, token: str, ref: str, who: str) -> list:
        """Lesson 17, the star: a cluster that nobody can dial either — a relay behind a mobile operator's
        NAT, a cluster in a cloud that takes no inbound — takes the streams of ITS cameras from here, calling
        in. Each pull is wanting the stream for another `LINGER`; stop pulling, and the want runs out."""
        self._check(token, ref)
        self.want(ref, who, until=self.wall() + self.linger)
        return self.subscribe(ref, who).drain()

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
# too, a piece at a time (below). `clock` is
# the camera's own clock, stated in every request (AC). `ring_seconds`: the ring kept while nobody wants the
# stream, flushed first — marked — when somebody does (AC). `hold_seconds`: how much of a BREAK it keeps in
# memory — while it was pushing and lost its road — to continue the stream from when the road comes back (CB).
# It has to reach as far back as the card's gate waits before it writes (`RecWorker.defer_for` plus how late the
# break is noticed — `RecWorker.CONTINUE_REACH`, 30 s; the card's own ring holds what its bytes hold of the stream,
# `CardRecorder.PREBUFFER`, and the gate waits no longer than the shorter of the two): a break that ends
# while the card still waits is in memory
# ONLY, and a shorter hold here would lose its beginning. Longer breaks: the card wrote them, from before
# the break, and the continuation reads them off it — a piece at a time (`_continue`).
#
# THE CARD IS OPTIONAL, AND IT IS NOT AN ARCHIVE (the product's camera; feedback CB, DG, DH). On a camera the card is
# the camera's buffer of plain files, written from the camera's one ring with no engine (`vms/card.py`); `card` here
# is its range reader — `CardRecorder.answer_range`. The pusher does not need it: a camera
# with no card — none put in, or one that would not open — pushes and continues breaks from memory all the same, and
# answers a range with RANGE FAILED (`upload(failed=...)`), as it does when the card could not read one: the server
# asks again later. Answered empty, the server would remember the range as "not on the card" and never ask again.
#
# THE CARD'S READER (the sixth review): `card(recording, t0, t1, max_bytes)` gives the range as an ITERATOR OF PIECES
# — lists of `Sample`, each at most `max_bytes` — read off the card as each is asked for; `recording` is the one the
# request names (None: the camera's one), and one the card does not hold is an error. Nothing of the card is in
# this process but the piece in hand: a camera has some 32 MB for everything (`vms.card.MEMORY_BUDGET`), and a
# reader that returned the range as one list put ten minutes at 4 Mbit/s — 272 MiB — into it, to continue one break.
class CameraPusher:
    def __init__(self, serial: str, flash, dial, card=None, clock=None, ring_seconds: float = 0.0, perform=None,
                 hold_seconds: float = 30.0, recording: str | None = None):
        """`perform(action) -> outcome` carries out an ask from another camera (a preset, a relay) and says
        what happened: "performed", or "refused: <why>". `recording`: this camera's recording on its card — what a
        break is continued from (None: the card's one)."""
        self.serial, self.flash, self.dial, self.card, self.recording = str(serial), flash, dial, card, recording
        self.failed_ranges: list[tuple[float, float, str]] = []        # ranges answered "could not read", and why
        self.perform = perform or (lambda action: "refused: this camera performs no actions")
        self.clock, self.ring_seconds = clock or time.time, ring_seconds
        self.versions: dict[str, int] = {}                             # per road; -1 first: answered at once (AF)
        self.pushing, self.ring, self.road = None, [], None            # the road it pushes on, if any
        self.uncovered: bool | None = None                             # the primary does not take the stream
        self.state = "no book yet"
        # A BREAK (CB): the road was lost while pushing. `broken_at` — the capture time of the last frame pushed;
        # while it is set, the ring keeps what the break held, `hold_seconds` of it, not the event ring's window.
        self.hold_seconds, self.broken_at, self.last_pushed = hold_seconds, None, None
        # What it SENT in the last `hold_seconds`, while pushing: sent is not written — a recorder's queue may have
        # dropped some of it — so at a break this becomes the start of what is kept, and `have` decides.
        self.tail: list = []
        self.resumed = 0                                               # frames sent again after breaks, for the tests and a metric

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

    def _keep(self, frames: list) -> None:
        now = self.clock()
        window = self.hold_seconds if self.broken_at is not None else self.ring_seconds
        self.ring = [f for f in self.ring + [f for f in frames if isinstance(f, dict) and "t" in f]
                     if float(f["t"]) >= now - window]

    # The continuation of a broken push (CB): everything after `have` — the recorder's own word, on this camera's
    # clock — that the camera still holds, from the first keyframe: off the card up to where the ring begins,
    # then the ring. Without `have` (an ingest that cannot say) it is the ring, as at an event's start.
    #
    # THE CARD'S PART GOES OUT AS IT IS READ (the sixth review, blocker 3). It was read whole into one list — ten
    # minutes of a break at 4 Mbit/s, 272 MiB in a camera with 32 — and then all of it was thrown away: the card's
    # reader gives `Sample`, and this kept only dicts. So the camera went down with its ring, the break it was
    # keeping and its live stream, to send nothing. Now a piece of at most `PIECE_BYTES` is read, turned into push
    # frames (`wire`) and pushed, and only then is the next one read: what the camera holds of its card is one piece.
    # Returns how many frames went out, and the ring's part — which goes with the pass's own frames, as before.
    #
    # The ring follows the card's part in the middle of a group of pictures only when the card's part reached it —
    # its last frame ends where the ring begins. A card that could not be read, that holds less, or no card at all
    # leaves a hole before the ring, and after a hole the stream starts on a keyframe; what is missing is backfill's.
    def _continue(self, ing, token: str, have) -> tuple[int, list]:
        ring = list(self.ring)
        if have is None:
            return 0, ring
        have = float(have)
        ring = [f for f in ring if float(f["t"]) > have]
        first = float(ring[0]["t"]) if ring else self.clock()
        sent, reached = 0, have
        if have < first:
            try:
                for piece in self._read_card(self.recording, have, first, PIECE_BYTES):
                    out = [wire(s, ring=True) for s in piece if unix_s(s.begin) > have]
                    while out and not sent and not out[0]["key"]:
                        out.pop(0)                                     # a continuation starts on a keyframe, never mid-GOP
                    if out:
                        ing.push(token, self.serial, out, camera_now=self.clock())
                        sent, reached = sent + len(out), unix_s(piece[-1].end)
                    piece = out = None                                 # let go BEFORE the next is read: one piece, not two
            except OSError:
                reached = have                                         # no card, or it could not read: memory only —
                                                                       # what is missing is backfill's, asked again
        if not sent or reached < first - 0.002:
            while ring and not ring[0].get("key", True):
                ring.pop(0)
        return sent, ring

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

    def _serve(self, ing, token: str, work: dict, frames_now: list, key: str) -> tuple[int, list, list]:
        pushed = 0
        if work["push"]:
            batch = list(frames_now)
            if self.broken_at is not None:                             # a break ends here: continue, don't restart
                sent, more = self._continue(ing, token, work.get("have"))   # the card's part is pushed as it is read
                self.resumed += sent + len(more)
                pushed += sent
                batch = [dict(f, ring=True) for f in more] + batch
                self.ring, self.broken_at = [], None
            elif self.pushing != key and self.ring:                    # a start, here: the ring first, marked
                batch = [dict(f, ring=True) for f in self.ring] + batch
                self.ring = []
            pushed += ing.push(token, self.serial, batch, camera_now=self.clock())
            self.pushing = key
            timed = [f for f in batch if isinstance(f, dict) and "t" in f]
            if timed:
                self.last_pushed = max(float(f["t"]) for f in timed)
                floor = self.clock() - self.hold_seconds
                self.tail = [f for f in self.tail + [{k: v for k, v in f.items() if k != "ring"} for f in timed]
                             if float(f["t"]) >= floor]
        uploaded = []
        for rid, r in work["ranges"].items():
            t0, t1 = r["from"], r["to"]
            if self._upload(ing, token, rid, r):
                uploaded.append((t0, t1))
        performed = []
        for aid, a in work.get("asks", {}).items():
            outcome = "expired" if a["deadline"] <= self.clock() else self.perform(a["action"])   # too late: not done
            ing.answer_ask(token, self.serial, aid, outcome)
            performed.append((a["action"], outcome))
        return pushed, uploaded, performed

    # One range of the card, answered (the sixth review). The request names the recording and the size of a piece; the
    # card is read a piece at a time and each piece is uploaded before the next is read — `more` on every one of
    # them, and an upload with nothing in it and no `more` to say the answer is whole. A minute at 4 Mbit/s was read
    # into one list of 28.6 MiB; it is thirty pieces of a megabyte now, one of them in memory. The ingest says, with
    # every piece, whether anybody still waits: a recorder that gave up is not read the rest of the card for.
    # An error of the card at ANY piece is said (`failed`), never answered as "that was all".
    def _upload(self, ing, token: str, rid: str, r: dict) -> bool:
        t0, t1 = r["from"], r["to"]
        piece = min(int(r.get("piece") or PIECE_BYTES), PIECE_BYTES)
        recording = r.get("recording") or self.recording
        seq = 0
        try:
            for samples in self._read_card(recording, t0, t1, piece):
                if not ing.upload(token, self.serial, rid, samples, camera_now=self.clock(), more=True, seq=seq):
                    return False                                       # nobody waits for it any more
                seq, samples = seq + 1, None                           # let go BEFORE the next is read: one piece, not two
        except OSError as e:                                           # the card's error is said, never answered as empty
            ing.upload(token, self.serial, rid, [], camera_now=self.clock(), failed=str(e))
            self.failed_ranges.append((t0, t1, str(e)))
            return False
        ing.upload(token, self.serial, rid, [], camera_now=self.clock(), seq=seq)
        return True

    def pass_once(self, frames_now: list, wait: float = 0.0) -> dict:
        """One pass. `wait`: how long the poll may be held when nothing changed — the camera's long poll.

        Two roads when the camera has a backup on another server (М11 lesson 1): the PRIMARY's ingest, and
        the backup's. One stream, never two — the camera pushes to the backup when, and only when, the primary
        does not take it: no ingest of the primary answers, or the book says the primary should be written and
        is not (and is not merely starting). Frames nobody takes stay in the ring, so the road it switches to
        gets them first."""
        e = self.entry()
        if not e or not e.get("ingest"):
            self.state = "no book yet" if not e else "recorded in its own cluster: nothing to push"
            return {"state": self.state}
        backup = e.get("backup")
        ing, work, url = self._poll(e["ingest"], "primary", 0.0 if backup else wait)
        pushed, uploaded, performed, road = 0, [], [], None
        takes = primary_takes(e, ing is not None, work)
        # What the card (edge) goes by, decided HERE and now: the primary does not take the stream — its ingest
        # did not answer, or said the recording is uncovered, or (with no word from it) the book says so.
        self.uncovered = not takes if ing is None or "uncovered" in (work or {}) or backup else None
        if ing is not None:
            p, u, a = self._serve(ing, e["ingest"]["token"], work if takes else {**work, "push": False},
                                  frames_now, "primary")
            pushed, uploaded, performed = p, u, a
            if takes:
                road = ("primary", url, work["push"])
        if road is None and backup:
            bing, bwork, burl = self._poll(backup["ingest"], "backup", wait)
            if bing is not None:
                p, u, a = self._serve(bing, backup["ingest"]["token"], bwork, frames_now, "backup")
                pushed, uploaded, performed = pushed + p, uploaded + u, performed + a
                road = ("backup", burl, bwork["push"])
        if road is None and self.pushing is not None and self.broken_at is None:
            self.broken_at = self.last_pushed if self.last_pushed is not None else self.clock()   # it broke while pushing (CB)
            self.ring = list(self.tail)                                # what was sent and may not have been written
        if road is not None and not road[2]:
            self.broken_at, self.tail = None, []                       # back, and nobody wants it now: nothing to continue
        if road is None or not road[2]:
            self.pushing = None
            if self.ring_seconds or self.broken_at is not None:
                self._keep(frames_now)                                 # nobody takes it now: keep it for who will
        if road is None:
            self.state = f"no ingest of {e['cluster']} answered" + (" nor of its backup" if backup else "")
            return {"state": self.state, "pushed": 0, "uploaded": uploaded, "asks": performed}
        which, where, pushing = road
        self.road = which
        self.state = (f"pushing to {where}" + (" — the backup: the primary does not take the stream" if which == "backup" else "")
                      if pushing else
                      f"polling {where}: nobody records it, asks only" if e.get("polls_only") else
                      f"idle at {where}: nobody wants the stream")
        return {"state": self.state, "pushed": pushed, "uploaded": uploaded, "asks": performed, "road": which}


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
