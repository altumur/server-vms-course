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
                 not a stream: the recorder asks for a minute, gets that minute or nothing (AD)
    the poll     answers at once the first time (a camera that has never polled has version -1), is held
                 while nothing changed, and wakes when a want runs out — a viewer's LINGER included (AF)
    one cluster  the book lists every ingest of the recording cluster; the camera pushes to the first that
                 answers, and the recorder may be on another server. Ingests of one cluster pass streams to
                 each other: a want at any of them is a want at all, and the one that has a subscriber but no
                 camera takes the stream from the one that has (`pump`) — the fan-out stays the cluster's (AG)

In the tests the "network" is a function from an address to an `Ingest`, called by the camera only: the
camera dials out, nobody dials in. The real ingest speaks SRT (the camera calls, the ingest listens; the
stream id names the camera) and the long poll is an HTTP request held for up to half a minute — Track 2.
"""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass, field

from .federation import Unreachable
from .gateway import Forbidden, LeakyQueue, LiveTee
from .tokens import TokenError, verify

INGEST = "rec/ingest"                  # the recording cluster's announcement: {"cluster", "urls", "ts"}
LINGER = 10.0                          # how long a stream nobody wants any more keeps being asked for


class Refused(Exception):
    """A push or a poll the ingest will not take: no token, the wrong camera, the wrong cluster, expired."""


def audience(cluster: str) -> str:
    return f"ingest:{cluster}"


def _is_ring(frame) -> bool:
    return isinstance(frame, dict) and bool(frame.get("ring"))


def _shift(frames: list, by: float) -> list:
    """Frames that carry a capture time (`t`, the camera's clock) moved onto the cluster's; others as they are."""
    if not by:
        return list(frames)
    return [dict(f, t=float(f["t"]) + by) if isinstance(f, dict) and "t" in f else f for f in frames]


@dataclass
class _Camera:
    wants: dict[str, float] = field(default_factory=dict)        # who wants the stream -> until when (inf: for ever)
    ranges: dict[str, tuple[float, float]] = field(default_factory=dict)   # requested uploads, by id, on the CLUSTER's clock
    answers: dict[str, list] = field(default_factory=dict)       # the camera's answer to each, by id
    landed: list[tuple[float, float]] = field(default_factory=list)
    pushed_at: float | None = None
    offset: float = 0.0                                          # the cluster's clock minus the camera's
    version: int = 0
    said: tuple | None = None                                    # what the last poll was told


class Ingest:
    """The recording cluster's receiver. `keys()` is the key set THIS cluster's agent carried (`ClusterTrust`).
    `peers()` are the other ingests of the same cluster (AG) — on a real cluster, found through its store."""

    def __init__(self, cluster: str, urls: list[str], keys, revoked=lambda: set(), wall=time.time,
                 name: str | None = None, peers=lambda: []):
        self.cluster, self.urls, self.keys, self.revoked, self.wall = cluster, list(urls), keys, revoked, wall
        self.name, self.peers = name or (urls[0] if urls else cluster), peers
        self.tees: dict[tuple[str, str], LiveTee] = {}
        self.cams: dict[str, _Camera] = {}

    def announce(self, objects) -> None:
        """Where cameras push to — in this cluster's own store, where the domain (or this cluster's report) reads it."""
        objects.put(INGEST, json.dumps({"cluster": self.cluster, "urls": self.urls, "ts": self.wall()}).encode())

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
            p = verify(token, ks, self.revoked(), now=self.wall())
        except TokenError as e:
            raise Refused(f"stream token refused: {e}")
        if p.get("aud") != audience(self.cluster) or str(p.get("ref")) != str(ref):
            raise Refused(f"stream token is for {p.get('ref')} at {p.get('aud')}, not {ref} at {audience(self.cluster)}")
        if camera_now is not None:                               # every request says what time the camera thinks it is
            self._cam(ref).offset = self.wall() - float(camera_now)
        return p

    def poll(self, token: str, ref: str, camera_now: float | None = None, version: int | None = None) -> dict:
        """The camera's long poll: whether to push now, and which ranges to upload — ranges on the CAMERA's
        clock. Wants and requests at any ingest of this cluster count (AG). `version`: what the camera last saw;
        the same version is a poll the real ingest would hold, and it is said so (`held`)."""
        self._check(token, ref, camera_now)
        now, cam = self.wall(), self._cam(ref)
        push, ranges = False, {}
        for ing in self._cluster():
            c = ing._cam(ref)
            c.wants = {w: u for w, u in c.wants.items() if u > now}       # a want that ran out wakes the poll (AF)
            push = push or bool(c.wants)
            ranges.update(c.ranges)
        said = (push, tuple(sorted(ranges.items())))
        if said != cam.said:
            cam.said, cam.version = said, cam.version + 1
        out = {"push": push, "version": cam.version,
               "ranges": {rid: (t0 - cam.offset, t1 - cam.offset) for rid, (t0, t1) in ranges.items()}}
        if version is not None and version == cam.version:
            out["held"] = True                                   # nothing changed: the real ingest holds the request
        return out

    def push(self, token: str, ref: str, frames: list, camera_now: float | None = None) -> int:
        self._check(token, ref, camera_now)
        return self._take(ref, _shift(frames, self._cam(ref).offset))

    def _take(self, ref: str, frames: list) -> int:
        live = self.tees.setdefault((str(ref), "live"), LiveTee(ref))
        edge = self.tees.setdefault((str(ref), "edge"), LiveTee(ref))
        for f in frames:
            live.push(f)                                         # recorders: everything, the ring first
            if not _is_ring(f):
                edge.push(f)                                     # viewers: the live edge only (AF)
        self._cam(ref).pushed_at = self.wall()
        return len(frames)

    def upload(self, token: str, ref: str, rid: str, samples: list, camera_now: float | None = None) -> None:
        """The camera's answer to a range request: samples with their own times, moved onto the cluster's clock,
        kept by the id of the request at whichever ingest of the cluster asked (AD). Never the live stream."""
        self._check(token, ref, camera_now)
        shifted = _shift(samples, self._cam(ref).offset)
        for ing in self._cluster():
            c = ing._cam(ref)
            if rid in c.ranges:
                c.answers[rid] = shifted
                c.landed.append(c.ranges.pop(rid))

    def answer(self, ref: str, rid: str) -> list | None:
        """The answer to one range request, or None — not yet, or never: the recorder's timeout decides."""
        return self._cam(ref).answers.get(rid)

    def pull(self, token: str, ref: str, who: str) -> list:
        """Lesson 17, the star: a cluster that nobody can dial either — an office behind a mobile operator's
        NAT, a cluster in a cloud that takes no inbound — takes the streams of ITS cameras from here, calling
        in. Each pull is wanting the stream for another `LINGER`; stop pulling, and the want runs out."""
        self._check(token, ref)
        self.want(ref, who, until=self.wall() + LINGER)
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
        self._cam(ref).wants[who] = until

    def release(self, ref: str, who: str) -> None:
        cam = self.cams.get(str(ref))
        if cam and who in cam.wants:
            cam.wants[who] = min(cam.wants[who], self.wall() + LINGER)   # a viewer who clicks back is not a restart

    def subscribe(self, ref: str, who: str, kind: str = "live", maxsize: int = 30, edge: bool = False) -> LeakyQueue:
        if not who.startswith("peer:"):                          # AG: be ready to take it from whichever peer gets it
            for peer in self._cluster()[1:]:
                peer.tees.setdefault((str(ref), "live"), LiveTee(ref)).subscribe(f"peer:{self.name}", maxsize)
        return self.tees.setdefault((str(ref), "edge" if edge else kind), LiveTee(ref)).subscribe(who, maxsize)

    def request_range(self, ref: str, t0: float, t1: float) -> str:
        """A range on this cluster's clock; the camera is told it on its own (AC)."""
        rid = secrets.token_hex(4)
        self._cam(ref).ranges[rid] = (t0, t1)
        return rid

    def pushing(self, ref: str, within: float = 5.0) -> bool:
        cam = self.cams.get(str(ref))
        return bool(cam and cam.pushed_at is not None and self.wall() - cam.pushed_at <= within)

    def landed(self, ref: str) -> list[tuple[float, float]]:
        cam = self.cams.get(str(ref))
        return list(cam.landed) if cam else []

    def pump(self) -> int:
        """AG: a stream this ingest has subscribers for and no camera pushing to it is taken from the peer
        that has — one subscription per camera per peer, like the gateway's to a worker."""
        moved = 0
        wanted = {ref for (ref, kind), tee in self.tees.items() if any(not w.startswith("peer:") for w in tee.subscribers)}
        for ref in wanted:
            if self.pushing(ref):
                continue                                         # the camera pushes here: nothing to take
            for peer in self._cluster()[1:]:
                q = peer.tees.get((ref, "live"))
                frames = q.subscribers[f"peer:{self.name}"].drain() if q and f"peer:{self.name}" in q.subscribers else []
                if frames:
                    moved += self._relay(ref, frames)
        return moved

    def _relay(self, ref: str, frames: list) -> int:
        """Frames taken from a peer: to this ingest's subscribers, without counting as a camera pushing HERE."""
        live = self.tees.setdefault((str(ref), "live"), LiveTee(ref))
        edge = self.tees.setdefault((str(ref), "edge"), LiveTee(ref))
        for f in frames:
            live.push(f)
            if not _is_ring(f):
                edge.push(f)
        return len(frames)


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
# time on the camera's clock (`t`); `card(t0, t1)` reads a range off the card, on that clock too. `clock` is
# the camera's own clock, stated in every request (AC). `ring_seconds`: the ring kept while nobody wants the
# stream, flushed first — marked — when somebody does (AC).
class CameraPusher:
    def __init__(self, serial: str, flash, dial, card=None, clock=None, ring_seconds: float = 0.0):
        self.serial, self.flash, self.dial, self.card = str(serial), flash, dial, card or (lambda t0, t1: [])
        self.clock, self.ring_seconds = clock or time.time, ring_seconds
        self.version, self.pushing, self.ring = -1, False, []          # -1: the first poll is answered at once (AF)
        self.state = "no book yet"

    def entry(self) -> dict | None:
        from .agent import PRIMARIES_PATH
        items, _ = self.flash.get(PRIMARIES_PATH)
        raw = (items or {}).get(self.serial)
        return json.loads(raw) if raw else None

    def _keep(self, frames: list) -> None:
        now = self.clock()
        self.ring = [f for f in self.ring + [f for f in frames if isinstance(f, dict) and "t" in f]
                     if float(f["t"]) >= now - self.ring_seconds]

    def pass_once(self, frames_now: list) -> dict:
        e = self.entry()
        if not e or not e.get("ingest"):
            self.state = "no book yet" if not e else "recorded in its own cluster: nothing to push"
            return {"state": self.state}
        token = e["ingest"]["token"]
        for url in e["ingest"]["urls"]:
            try:
                ing = self.dial(url)
                work = ing.poll(token, self.serial, camera_now=self.clock(), version=self.version)
                break
            except Unreachable:
                continue
        else:
            self.state = f"no ingest of {e['cluster']} answered"
            return {"state": self.state}
        self.version = work["version"]
        pushed = 0
        if work["push"]:
            batch = list(frames_now)
            if not self.pushing and self.ring:                         # the start: the ring first, marked
                batch = [dict(f, ring=True) for f in self.ring] + batch
                self.ring = []
            pushed = ing.push(token, self.serial, batch, camera_now=self.clock())
            self.pushing = True
        else:
            self.pushing = False
            if self.ring_seconds:
                self._keep(frames_now)
        uploaded = []
        for rid, (t0, t1) in work["ranges"].items():
            ing.upload(token, self.serial, rid, self.card(t0, t1), camera_now=self.clock())
            uploaded.append((t0, t1))
        self.state = f"pushing to {url}" if work["push"] else f"idle at {url}: nobody wants the stream"
        return {"state": self.state, "pushed": pushed, "uploaded": uploaded}
