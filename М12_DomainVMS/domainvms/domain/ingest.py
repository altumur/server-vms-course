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


@dataclass
class _Camera:
    wants: dict[str, float] = field(default_factory=dict)        # who wants the stream -> until when (inf: for ever)
    ranges: dict[str, tuple[float, float]] = field(default_factory=dict)   # requested uploads, by id
    landed: list[tuple[float, float]] = field(default_factory=list)
    pushed_at: float | None = None


class Ingest:
    """The recording cluster's receiver. `keys()` is the key set THIS cluster's agent carried (`ClusterTrust`)."""

    def __init__(self, cluster: str, urls: list[str], keys, revoked=lambda: set(), wall=time.time):
        self.cluster, self.urls, self.keys, self.revoked, self.wall = cluster, list(urls), keys, revoked, wall
        self.tees: dict[tuple[str, str], LiveTee] = {}
        self.cams: dict[str, _Camera] = {}

    def announce(self, objects) -> None:
        """Where cameras push to — in this cluster's own store, where the domain (or this cluster's report) reads it."""
        objects.put(INGEST, json.dumps({"cluster": self.cluster, "urls": self.urls, "ts": self.wall()}).encode())

    # -- the camera's side of the conversation ----------------------------------------------------------
    def _check(self, token: str, ref: str) -> dict:
        ks = self.keys()
        if ks is None:
            raise Refused(f"{self.cluster}: no key set yet — is this cluster's agent running?")
        try:
            p = verify(token, ks, self.revoked(), now=self.wall())
        except TokenError as e:
            raise Refused(f"stream token refused: {e}")
        if p.get("aud") != audience(self.cluster) or str(p.get("ref")) != str(ref):
            raise Refused(f"stream token is for {p.get('ref')} at {p.get('aud')}, not {ref} at {audience(self.cluster)}")
        return p

    def poll(self, token: str, ref: str) -> dict:
        """The camera's long poll: whether to push now, and which ranges to upload."""
        self._check(token, ref)
        now, cam = self.wall(), self.cams.setdefault(str(ref), _Camera())
        cam.wants = {w: u for w, u in cam.wants.items() if u > now}
        return {"push": bool(cam.wants), "ranges": dict(cam.ranges)}

    def push(self, token: str, ref: str, frames: list, kind: str = "live") -> int:
        self._check(token, ref)
        tee = self.tees.setdefault((str(ref), kind), LiveTee(ref))
        for f in frames:
            tee.push(f)
        self.cams.setdefault(str(ref), _Camera()).pushed_at = self.wall()
        return len(frames)

    def upload(self, token: str, ref: str, rid: str, span: tuple[float, float], frames: list) -> None:
        """A range off the card, as asked. Into the `backfill` stream, never the live one (М10B Lesson 26)."""
        self.push(token, ref, frames, kind="backfill")
        cam = self.cams[str(ref)]
        cam.ranges.pop(rid, None)
        cam.landed.append(tuple(span))

    # -- the cluster's side -----------------------------------------------------------------------------
    def want(self, ref: str, who: str, until: float = float("inf")) -> None:
        """Somebody in this cluster wants the stream: a recorder (for ever, or an event's window), a viewer."""
        self.cams.setdefault(str(ref), _Camera()).wants[who] = until

    def release(self, ref: str, who: str) -> None:
        cam = self.cams.get(str(ref))
        if cam and who in cam.wants:
            cam.wants[who] = min(cam.wants[who], self.wall() + LINGER)   # a viewer who clicks back is not a restart

    def subscribe(self, ref: str, who: str, kind: str = "live", maxsize: int = 30) -> LeakyQueue:
        return self.tees.setdefault((str(ref), kind), LiveTee(ref)).subscribe(who, maxsize)

    def request_range(self, ref: str, t0: float, t1: float) -> str:
        rid = secrets.token_hex(4)
        self.cams.setdefault(str(ref), _Camera()).ranges[rid] = (t0, t1)
        return rid

    def pushing(self, ref: str, within: float = 5.0) -> bool:
        cam = self.cams.get(str(ref))
        return bool(cam and cam.pushed_at is not None and self.wall() - cam.pushed_at <= within)

    def landed(self, ref: str) -> list[tuple[float, float]]:
        cam = self.cams.get(str(ref))
        return list(cam.landed) if cam else []


class IngestLiveEndpoint:
    """The gateway's endpoint for a camera that pushes: the same `open`/`authorise`/`tees` as a worker's
    (Lesson 3), over the ingest. Opening it is a viewer WANTING the stream — the camera learns on its poll."""

    def __init__(self, ingest: Ingest, authorise):
        self.ingest, self.authorise = ingest, authorise
        self.worker = audience(ingest.cluster)
        self.tees = _Tees(ingest)

    def open(self, camera, token: str, who: str) -> LeakyQueue:
        self.authorise(token, camera)                    # the cluster's check, as at any endpoint; raises Forbidden
        self.ingest.want(camera, who)
        return self.ingest.subscribe(camera, who)


class _Tees:
    def __init__(self, ingest: Ingest):
        self.ingest = ingest

    def __getitem__(self, camera):
        ingest = self.ingest

        class _Handle:
            @staticmethod
            def unsubscribe(who):
                ingest.tees.setdefault((str(camera), "live"), LiveTee(camera)).unsubscribe(who)
                ingest.release(camera, who)
        return _Handle()


# -- the camera --------------------------------------------------------------------------------------------
# One pass of the camera's pusher, after its agent has carried the book home. `dial(url)` is the camera
# opening a connection OUT — it raises Unreachable when that address does not answer, and then the next one
# in the book is tried. `frames_now` is what the sensor produced since the last pass; `card(t0, t1)` reads a
# range off the card. Returns what it did, for the camera's own page.
class CameraPusher:
    def __init__(self, serial: str, flash, dial, card=None):
        self.serial, self.flash, self.dial, self.card = str(serial), flash, dial, card or (lambda t0, t1: [])
        self.state = "no book yet"

    def entry(self) -> dict | None:
        from .agent import PRIMARIES_PATH
        items, _ = self.flash.get(PRIMARIES_PATH)
        raw = (items or {}).get(self.serial)
        return json.loads(raw) if raw else None

    def pass_once(self, frames_now: list) -> dict:
        e = self.entry()
        if not e or not e.get("ingest"):
            self.state = "no book yet" if not e else "recorded in its own cluster: nothing to push"
            return {"state": self.state}
        token = e["ingest"]["token"]
        for url in e["ingest"]["urls"]:
            try:
                ing = self.dial(url)
                work = ing.poll(token, self.serial)
                break
            except Unreachable:
                continue
        else:
            self.state = f"no ingest of {e['cluster']} answered"
            return {"state": self.state}
        pushed = ing.push(token, self.serial, frames_now) if work["push"] else 0
        uploaded = []
        for rid, (t0, t1) in work["ranges"].items():
            ing.upload(token, self.serial, rid, (t0, t1), self.card(t0, t1))
            uploaded.append((t0, t1))
        self.state = f"pushing to {url}" if work["push"] else f"idle at {url}: nobody wants the stream"
        return {"state": self.state, "pushed": pushed, "uploaded": uploaded}
