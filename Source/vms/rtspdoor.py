"""The gateway's RTSP door — RTSP outward (the product's `liveproc/rtsp.go`; ADR-0031, the addendum of 2026-10-07).

A video wall, another VMS, an analytics server takes a camera as `rtsp://<gateway>/<cam>`, proving who it is with a
stream client's account (`vms/streamclients.py`): Digest, and Basic too inside TLS. It plays the cameras its grants let
it view — the same grants, the same scopes and labels, the same lapse as a person's — and nothing else.

The door is the gateway's, not the workers': the workers' fan-outs stay where they are, a camera that moves to another
worker keeps its address here, and there is one door to guard. A mount re-pays the worker's stream as it is, without
decoding; N clients of one camera are one session at the worker, and none while nobody plays.

THE SERVER IS PLUGGABLE, as the WebRTC peer is (`liveworker.FakePeer`): what the door decides is here, and what speaks
RTSP is an object with five calls —

    accounts({name: password})    who may log in at all: the accounts this cluster was carried
    publish(cam, source)          a mount for the camera, over the worker's stream at `source`
    unpublish(cam)                no mount: a new client gets a 404
    roles(cam, [name…])           who may play that mount
    plays() -> [Play]             the sessions playing now: id, user, mount, ip, agent

— `FakeRTSPServer` below in the tests, a server with Digest on a box. The course ships no such server: on a box where
`LIVE_RTSP_LISTEN` is set and none is given, the door says so and stays shut. Off unless `LIVE_RTSP_LISTEN` is set, and
shut while the gateway's spec does not say it reads the accounts (`live.subsystem.yaml`, `secrets.reads`; ADR-0024).

Each pass (`sync`, then `watch`):

    sync    the server's accounts (`streamclients.stream_accounts`: what the agent carried, or the holder's own records),
            a mount for every camera a worker of this cluster holds (where its stream is now: `source(cam)`), and on
            each mount the accounts whose grants let them `view` that camera — one reading of the grants for the whole
            pass, so a grant revoked is honoured on the next one
    watch   who began playing and who stopped since the last pass: `live.rtsp.play`, `live.rtsp.ended` in the gateway's
            journal — who, which camera, the session, from where (the course's journal fields: `target`, `addr`)
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

from .config import SPEC, cam_ref, row
from . import streamclients as sc

log = logging.getLogger("vms.rtspdoor")


@dataclass
class Play:
    """One session playing a mount: who logged in, which mount, from where, with what."""
    id: str
    user: str
    mount: str
    ip: str = ""
    agent: str = ""


@dataclass
class FakeRTSPServer:
    """The RTSP server as the door drives it, in memory: what it was told, and a client's `play` checked against it —
    an account with its password, on a mount whose roles name it."""
    accounts_: dict = field(default_factory=dict)
    mounts: dict = field(default_factory=dict)                 # cam -> source
    roles_: dict = field(default_factory=dict)                 # cam -> [name…]
    playing: dict = field(default_factory=dict)                # id -> Play
    published: int = 0

    def accounts(self, accounts: dict) -> None:
        self.accounts_ = dict(accounts)

    def publish(self, cam: str, source: str) -> None:
        self.mounts[cam], self.roles_[cam] = source, []
        self.published += 1

    def unpublish(self, cam: str) -> None:
        self.mounts.pop(cam, None)
        self.roles_.pop(cam, None)
        for sid in [s for s, p in self.playing.items() if p.mount == cam]:
            del self.playing[sid]

    def roles(self, cam: str, names: list) -> None:
        if cam not in self.mounts:
            raise KeyError(cam)
        self.roles_[cam] = list(names)

    def plays(self) -> list:
        return list(self.playing.values())

    # -- a client, as a test plays one ---------------------------------------------------------------------------------
    def play(self, user: str, password: str, cam: str, ip: str = "10.0.0.9", agent: str = "wall/1") -> str:
        """A session id, or `PermissionError` (401: no such account or a wrong password; 403: not on this mount's roles)
        or `KeyError` (404: no such mount)."""
        if self.accounts_.get(user) != password or not password:
            raise PermissionError(401)
        if cam not in self.mounts:
            raise KeyError(cam)
        if user not in self.roles_.get(cam, []):
            raise PermissionError(403)
        sid = uuid.uuid4().hex
        self.playing[sid] = Play(sid, user, cam, ip, agent)
        return sid

    def stop(self, sid: str) -> None:
        self.playing.pop(sid, None)


class RTSPDoor:
    """`server`: the RTSP server (above); `source(cam) -> url | None`: where the camera's stream is now (the gateway's
    `rtp_source`); `vars_`: this cluster's store; `cluster`: its name (the holder hands its own accounts by it);
    `journal`: the gateway's, or a callable that gives it; `gateway`: its name, or a callable; `sealer`: its ring — the
    carried accounts lie sealed with it."""

    def __init__(self, server, source, vars_, cluster: str, journal=None, sealer=None, wall=time.time,
                 gateway: str = ""):
        self.server, self.source, self.vars, self.cluster = server, source, vars_, cluster
        self.journal, self.sealer, self.wall, self.gateway = journal, sealer, wall, gateway
        self.mounted: dict[str, str] = {}          # cam -> the source it is published with
        self.given: dict[str, str] = {}            # cam -> who may play it, as last handed to the server
        self.playing: dict[str, tuple[Play, float]] = {}    # session id -> who plays what, since when

    def sync(self) -> None:
        """Makes the door what the store says: the accounts carried, a mount for every camera a worker of this cluster
        holds, and on each mount the accounts its grants let view it."""
        accounts = sc.stream_accounts(self.vars, self.cluster, self.sealer)
        self.server.accounts(accounts)
        names = sorted(accounts)
        grants = self._grants()                    # once a sync, as a gate's memo lives for one request
        seen = set()
        prefix = SPEC.sub.config(SPEC.rows, "")
        for path in self.vars.list(prefix):
            cam = path[len(prefix):]
            if not cam or "/" in cam:
                continue
            src = self.source(cam)
            if not src:
                continue
            seen.add(cam)
            if self.mounted.get(cam) != src:
                if cam in self.mounted:
                    self.server.unpublish(cam)     # the camera moved: a new client gets the new road
                try:
                    self.server.publish(cam, src)
                except Exception as e:             # noqa: BLE001 — that mount's trouble: the others are made
                    log.warning("RTSP mount %s: %s", cam, e)
                    self.mounted.pop(cam, None)
                    continue
                self.mounted[cam], self.given[cam] = src, "\x00"     # roles go on below, on a mount that has none yet
            may = self.who_may(grants, cam, names)
            joined = "\n".join(may)
            if self.given.get(cam) != joined:
                try:
                    self.server.roles(cam, may)
                    self.given[cam] = joined
                except Exception as e:             # noqa: BLE001 — tried again on the next pass
                    log.warning("RTSP roles of %s: %s", cam, e)
        for cam in [c for c in self.mounted if c not in seen]:
            self.server.unpublish(cam)             # no worker holds it now: a new client gets a 404
            del self.mounted[cam]
            self.given.pop(cam, None)

    def _grants(self):
        """This cluster's grants, read once (`domain/grants`, carried by its agent), as a cluster's console reads them."""
        from w2cplatform.domain.agent import ClusterTrust
        from w2cplatform.domain.grants import ClusterGrants
        g = ClusterGrants(self.cluster, now=self.wall)
        g.renew_from_domain(ClusterTrust(self.vars).grants())
        return g

    def who_may(self, grants, cam: str, names: list) -> list:
        """The accounts among `names` whose grants let them `view` the camera — a grant of `view` or above, on the
        cluster, on the camera, or on labels the camera carries."""
        from w2cplatform.access import RANK
        items, _ = self.vars.get(SPEC.sub.config(SPEC.rows, cam))
        try:
            labels = [str(x) for x in (row(items or {}).get("labels") or [])]
        except Exception:                          # noqa: BLE001 — a row that does not read carries no labels
            labels = []
        now, ref = self.wall(), cam_ref(cam)
        caps = [c for c, r in RANK.items() if r >= RANK["view"]]
        return [n for n in names if any(grants.may(n, c, ref, now, labels=labels) for c in caps)]

    def watch(self) -> None:
        """Writes down the plays that began and ended since the last pass."""
        now, seen = self.wall(), set()
        for pl in self.server.plays():
            if not pl.id:
                continue
            seen.add(pl.id)
            if pl.id not in self.playing:
                self.playing[pl.id] = (pl, now)
                self._say("live.rtsp.play", user=pl.user, target=pl.mount, session=pl.id, addr=pl.ip, agent=pl.agent)
        for sid in [s for s in self.playing if s not in seen]:
            pl, since = self.playing.pop(sid)
            self._say("live.rtsp.ended", user=pl.user, target=pl.mount, session=sid, addr=pl.ip,
                      seconds=int(now - since))

    def _say(self, kind: str, **fields) -> None:
        log.info("audit: %s %s", kind, fields)
        journal = self.journal() if callable(self.journal) else self.journal
        gateway = self.gateway() if callable(self.gateway) else self.gateway
        if journal is not None:
            journal.say(kind, gateway=gateway or "", **fields)

    def pass_once(self) -> None:
        self.sync()
        self.watch()


def open_rtsp(env: dict, server=None, spec=None):
    """The server the door drives, or None: the door is not asked for (`LIVE_RTSP_LISTEN` unset), or the gateway's spec
    does not say it reads the accounts (`secrets.reads`), or there is no server to drive — each said once, here."""
    listen = env.get("LIVE_RTSP_LISTEN", "")
    if not listen:
        return None
    if spec is None:
        from w2cplatform import catalog
        from .config import LIVE_SPEC
        try:
            spec = catalog.spec(LIVE_SPEC.name)
        except ValueError:
            spec = LIVE_SPEC
    if not sc.reads_declared(spec):
        log.warning("LIVE_RTSP_LISTEN=%s, and %s.subsystem.yaml does not say its gateway reads %s and %s "
                    "(secrets.reads): the RTSP door stays shut", listen, spec.name, sc.STREAM_CLIENTS_PREFIX,
                    sc.STREAM_ACCOUNTS_KEY)
        return None
    if server is None:
        log.warning("LIVE_RTSP_LISTEN=%s, and this gateway has no RTSP server to open it with: the door stays shut",
                    listen)
        return None
    if not env.get("LIVE_RTSP_CERT") and listen.rsplit(":", 1)[0] not in ("127.0.0.1", "localhost", "::1", "[::1]"):
        log.warning("the RTSP door has no TLS certificate: passwords are proved by Digest, but the video goes in the "
                    "clear — keep it to a network you trust, or set LIVE_RTSP_CERT and LIVE_RTSP_KEY (listen %s)", listen)
    return server
