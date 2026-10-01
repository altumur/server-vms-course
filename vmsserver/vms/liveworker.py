"""The live gateway — the second subsystem's worker. A gateway is a worker in
the platform's sense (a slot claimed by CAS, an assignment read from the
store, a heartbeat with capacity and headroom, count = N by demand) whose
unit is a camera's live FAN-OUT: one subscription to the worker's RTP tee,
N browsers behind it over WebRTC. Capacity is counted in viewers.

    live/streams/<cam>      the unit — created by the console on the first viewer, deleted by the gateway
                            a grace period after the last one leaves (demand-created placement)
    live/workers/<g>        the assignment, written by the live controller (the platform's SpecController
                            run from live.subsystem.yaml)
    live/<g>/heartbeat      capacity, headroom (viewers it could still take), url, per-stream status

    POST   /whep/<cam>            WHEP: an SDP offer in, 201 + the SDP answer out, Location: /whep/session/<id>
    DELETE /whep/session/<id>     the viewer hangs up
    GET    /metrics               live_sessions, live_streams_up, live_headroom

Rules it keeps: it subscribes to a camera ONCE whatever the viewer count;
it finds the worker's fan-out URL from the VMS heartbeat, never by calling a
worker; a viewer never reaches a worker; it holds nothing a restart cannot
rediscover. The media path is a `Peer` — `FakePeer` here (signalling only),
`gstvms.webrtc.GstPeer` on a box (webrtcbin: ICE, DTLS-SRTP, RTP).
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from w2cplatform import runtime
from w2cplatform.access import Denied, Gate
from w2cplatform.console import SendMixin, heartbeats, holder_of
from w2cplatform.contract import Worker
from w2cplatform.spec import SpecController
from w2cplatform.variables import Variables

from .config import LIVE_SPEC

LIVE = LIVE_SPEC.sub
log = logging.getLogger("vms.liveworker")


# One WebRTC peer for one viewer. `answer(offer) -> sdp`; `close()`. The fake answers any offer with a minimal
# recvonly-compatible SDP so signalling can be tested end to end; the real one is `gstvms.webrtc.GstPeer`.
class FakePeer:
    def __init__(self, upstream):
        self.upstream, self.closed = upstream, False
        self.connected, self.lost = True, False           # a test says otherwise: never connected, or gone

    def state(self) -> str:
        """`connecting`, `connected` or `gone` — what `GstPeer.state` reads off webrtcbin."""
        return "gone" if self.closed or self.lost else ("connected" if self.connected else "connecting")

    def answer(self, offer: str) -> str:
        if "m=video" not in offer:
            raise ValueError("the offer has no video section")
        return ("v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=fingerprint:sha-256 FA:KE\r\n"
                "m=video 9 UDP/TLS/RTP/SAVPF 96\r\na=sendonly\r\na=rtpmap:96 H264/90000\r\n")

    def close(self) -> None:
        self.closed = True


# One camera's subscription: the RTP source (server, port) it listens to and the peers fanned out from it.
class Upstream:
    def __init__(self, cam: str, server: str, url: str, epoch: int):
        self.cam, self.server, self.url, self.epoch = cam, server, url, epoch
        self.peers: dict[str, object] = {}
        self.idle_since: float | None = None      # wall time the last viewer left; None while watched
        # "" while the stream is one a browser can play, otherwise the sentence the console shows beside
        # it. Filled from the caps the peer's parser negotiated, so it is empty until something flowed.
        self.codec: str = ""

    def to_status(self) -> dict:
        st = {"id": self.cam, "phase": "live" if self.peers else "idle", "sessions": len(self.peers),
              "server": self.server, "source": self.url, "epoch": self.epoch}
        if self.codec:
            st["codec"] = self.codec
        return st


class LiveWorker(Worker):
    """`name` is a slot (`g-1`); `url` is where the console proxies WHEP to; `capacity` is viewers."""

    SLOT_PREFIX = "g"                            # a slot it has to make is `g-<n>`, like the ones it is given

    def __init__(self, name: str | None, vars_: Variables, objects, ctl: SpecController | None = None, url: str = "",
                 capacity: int | None = None, clock=time.monotonic, wall=time.time, server: str | None = None,
                 peer_factory=None, env: dict | None = None):
        env = dict(os.environ if env is None else env)
        super().__init__(LIVE, None, vars_, objects, clock=clock, wall=wall)
        self.gate = Gate(self.vars, self.wall)      # who may be given a stream here (`handler`)
        self._said_loopback: set = set()            # cameras whose fan-out we were told is on another server's loopback
        self.claim_slot(prefer=name if name is not None else runtime.slot(env, "GATEWAY_NAME", "g"))
        self.ctl = ctl                                              # the live SpecController with the gateway's token: deletes its own idle units
        self.url = url or env.get("GATEWAY_URL", "")
        self.capacity = capacity if capacity is not None else int(env.get("CAPACITY", "100"))
        self.server = runtime.server(env, server)
        self.labels = runtime.labels(env)
        self.peer_factory = peer_factory or FakePeer
        self.upstreams: dict[str, Upstream] = {}
        self.sessions: dict[str, tuple[str, object]] = {}          # session id -> (cam, peer)
        self.session_at: dict[str, float] = {}                     # session id -> when it was offered
        self.answering = 0                                          # offers being answered: seats held, not yet sessions
        self.resets = 0                                             # subscriptions reopened because the camera moved or the source died
        self.swept = 0                                              # sessions closed because their viewer was gone
        self.subscriptions = 0                                      # how many times an RTP source was opened — the test's number
        self.lock = threading.Lock()

    # -- where a camera's RTP is: the VMS heartbeat, never a call to the worker ----------------------
    def rtp_source(self, cam: str):
        """`(server, live_url, epoch)` of the worker holding the camera — its RTSP fan-out, on any server."""
        found = holder_of(self.objects, "vms/", cam, self.wall(), phase="running", field="live_url")
        if found is None:
            return None
        _, hb, st = found
        from .config import local_only
        server = hb.extra.get("server", "?")
        if local_only(st["live_url"], server, self.server):
            # The fan-out is on loopback on ANOTHER server: announced truthfully, not for us. Said once per
            # camera, and the stream opens as soon as that server announces an address that is reachable.
            if cam not in self._said_loopback:
                self._said_loopback.add(cam)
                log.warning("%s: camera %s is served on loopback on %s — not reachable from %s (RTSP_HOST there)",
                            self.name, cam, server, self.server)
            return None
        self._said_loopback.discard(cam)
        return server, st["live_url"], int(st.get("epoch", 0))

    # -- the reconcile pass: make the subscriptions equal the assignment -------------------------------
    def reconcile_once(self, now: float | None = None) -> list[str]:
        now = self.wall() if now is None else now
        a = self.assignment()
        wanted = set(a.units)
        with self.lock:
            for cam in wanted - set(self.upstreams):
                src = self.rtp_source(cam)
                if src is None:
                    continue                                        # the camera is not recording anywhere: wait, say so in the heartbeat
                if cam not in self.epochs:
                    self.take_epoch(cam)                            # one gateway per fan-out, fenced like any unit
                self.upstreams[cam] = Upstream(cam, *src); self.subscriptions += 1
                self.upstreams[cam].idle_since = now
            for cam in set(self.upstreams) - wanted:                # taken away (rebalanced, deleted): drop viewers, close the source
                self._drop(cam)
            self._recheck(now)
            self._sweep(now)
            # the grace period: an idle fan-out is deleted by the gateway itself — demand-created, demand-deleted
            for cam, up in list(self.upstreams.items()):
                if not up.peers and up.idle_since is not None and self.ctl is not None:
                    row = self.ctl.unit(cam)
                    if row is not None and now - up.idle_since >= int(row.get("grace", 30)):
                        self.ctl.delete(cam)                        # the controller's next pass takes the placement back
        return sorted(self.upstreams)

    # A session ends with DELETE — when the viewer says so. A tab closed, a laptop lid shut, an offer whose
    # connection never came up say nothing, and their sessions stayed: the fan-out was never idle, so the unit
    # was never deleted, and the gateway filled to `capacity` with nobody watching and answered 503 "full" to
    # everybody after (the product's gateway, feedback BC). So every pass asks each peer: gone, or still
    # connecting `CONNECT_SECONDS` after its offer — closed, as if it had hung up.
    CONNECT_SECONDS = 30.0

    # Where the camera is was read ONCE, when the subscription was made. The camera moved to another worker, or
    # its worker restarted the pipeline under a new epoch: the source this gateway had opened died quietly, the
    # status went on saying `live` with the old address, and the viewers had a black picture — new ones too,
    # joining the same dead source (the platform review; the product's gateway, feedback BF). Every pass
    # compares `(url, epoch)` with what the holder's heartbeat says NOW, and asks the source whether it is
    # alive. Moved, or dead: the viewers are hung up on — their page connects again by itself — and the
    # subscription takes the new address; the first viewer back opens the source where the camera is.
    def _recheck(self, now: float) -> None:
        for cam, up in list(self.upstreams.items()):
            src = self.rtp_source(cam)
            alive = getattr(getattr(up, "pipeline", None), "alive", None)
            dead = callable(alive) and not alive()
            if src is None or ((src[1], src[2]) == (up.url, up.epoch) and not dead):
                continue                                            # nothing known against it: leave it be
            why = "the source stopped" if (src[1], src[2]) == (up.url, up.epoch) else "the camera is served elsewhere now"
            for sid, (c, _) in list(self.sessions.items()):
                if c == cam:
                    self._close(sid, now)
            if getattr(up, "pipeline", None) is not None:
                up.pipeline.close()
            fresh = Upstream(cam, *src)
            fresh.idle_since, fresh.reset = now, why
            self.upstreams[cam] = fresh
            self.resets += 1
            log.warning("%s: stream %s reopened: %s (%s, epoch %s)", self.name, cam, why, src[1], src[2])

    def _sweep(self, now: float) -> None:
        for sid, (cam, peer) in list(self.sessions.items()):
            state = peer.state() if callable(getattr(peer, "state", None)) else "connected"
            if state == "gone" or (state == "connecting" and now - self.session_at.get(sid, now) >= self.CONNECT_SECONDS):
                self._close(sid, now)
                self.swept += 1

    def _close(self, sid: str, now: float) -> None:
        cam, peer = self.sessions.pop(sid)
        self.session_at.pop(sid, None)
        peer.close()
        up = self.upstreams.get(cam)
        if up is not None:
            up.peers.pop(sid, None)
            if not up.peers:
                up.idle_since = now

    def _drop(self, cam: str) -> None:
        up = self.upstreams.pop(cam)
        for sid, (c, peer) in list(self.sessions.items()):
            if c == cam:
                peer.close(); del self.sessions[sid]; self.session_at.pop(sid, None)
        if getattr(up, "pipeline", None) is not None:              # the real media path (gstvms.webrtc): close the source
            up.pipeline.close()
        self.release(cam)

    # -- WHEP ----------------------------------------------------------------------------------------
    def offer(self, cam: str, sdp: str) -> tuple[str, str]:
        """A viewer's offer: refuse if the camera is not this gateway's or the gateway is full; else a session."""
        # The answer is prepared OUTSIDE the gateway's lock (feedback BE): it waits for every ICE candidate, up to
        # five seconds, and the same lock is taken by the pass — the leases, the heartbeat — and by every other
        # viewer. The seat is taken before the answer, so a burst of offers cannot overfill the gateway; and
        # after it the subscription is looked at again — the pass may have dropped or reopened it meanwhile.
        with self.lock:
            up = self.upstreams.get(str(cam))
            if up is None:
                raise KeyError(cam)
            if len(self.sessions) + self.answering >= self.capacity:
                raise OverflowError("full")
            self.answering += 1
            peer = self.peer_factory(up)
        try:
            answer = peer.answer(sdp)
        except Exception:
            with self.lock:
                self.answering -= 1
            peer.close()                                            # an offer that failed leaves no branch on the tee
            raise
        with self.lock:
            self.answering -= 1
            if self.upstreams.get(str(cam)) is not up:
                peer.close()                                        # answered into a subscription that is gone
                raise KeyError(cam)
            # The profile is known only once something has flowed, so the FIRST viewer may well arrive
            # before it is: ask after the answer, and ask every time.
            note = getattr(peer, "codec_note", None)
            if callable(note):
                up.codec = note() or up.codec
            sid = uuid.uuid4().hex
            up.peers[sid] = peer; up.idle_since = None
            self.sessions[sid] = (str(cam), peer)
            self.session_at[sid] = self.wall()
            return sid, answer

    def hangup(self, sid: str) -> bool:
        with self.lock:
            if sid not in self.sessions:
                return False
            self._close(sid, self.wall())
            return True

    # -- what it reports -----------------------------------------------------------------------------
    def headroom(self) -> int:
        return max(0, self.capacity - len(self.sessions) - self.answering)

    def heartbeat_once(self) -> None:
        self.heartbeat([up.to_status() for up in self.upstreams.values()], server=self.server, instance=self.instance,
                       labels=",".join(self.labels), url=self.url, capacity=self.capacity, headroom=self.headroom(),
                       sessions=len(self.sessions), subscriptions=self.subscriptions, conflicts=self.conflicts(),
                       swept=self.swept, resets=self.resets)

    def metrics_text(self) -> str:
        return (f"# TYPE live_sessions gauge\nlive_sessions {len(self.sessions)}\n"
                f"# TYPE live_streams_up gauge\nlive_streams_up {len(self.upstreams)}\n"
                f"# TYPE live_headroom gauge\nlive_headroom {self.headroom()}\n")

    # The labels of the camera a stream is of, for a grant given on labels. Read from the row, as text: a
    # gateway holds fan-outs, not cameras, and has no parsed rows of them.
    def labels_of(self, cam) -> list:
        try:
            items, _ = self.vars.get(f"vms/cameras/{cam}")
        except OSError:
            return []
        return [l for l in str((items or {}).get("labels", "")).split(",") if l]

    # -- the WHEP server -------------------------------------------------------------------------------
    def handler(self):
        gw = self

        class H(SendMixin, BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def do_POST(self):
                if not self.path.startswith("/whep/"):
                    return self._send(404, {"error": "no such path"})
                cam = self.path[len("/whep/"):].split("?")[0]
                if not self._admitted(cam):
                    return
                sdp = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
                try:
                    sid, answer = gw.offer(cam, sdp)
                except KeyError:
                    return self._send(404, {"error": f"stream {cam} is not on this gateway"})
                except OverflowError:
                    return self._send(503, {"error": "this gateway is full"})
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
                data = answer.encode()
                self.send_response(201); self.send_header("Content-Type", "application/sdp")
                self.send_header("Location", f"/whep/session/{sid}"); self.send_header("Content-Length", str(len(data)))
                self.end_headers(); self.wfile.write(data)

            # THE GATEWAY ASKS TOO (the order agreed with the product, feedback BP). The console checks a
            # viewer's token — and then calls this door, which anybody on the network it listens on could
            # call instead. Until processes prove themselves to each other (mutual TLS: not in this course's
            # code), the one check that can stand here is the VIEWER's own: the console passes the token on,
            # and the gateway checks it against the same cluster store, by the same gate
            # (`w2cplatform/access.py`) — `view` on this camera. No key set in the store: open, as the
            # console is. A key set and nothing to check with: shut.
            def _admitted(self, cam) -> bool:
                try:
                    gw.gate.admit(self.headers, "view", cam, gw.labels_of(cam) if cam is not None else [])
                    return True
                except Denied as e:
                    self._send(e.status, {"error": "denied", "detail": e.why})
                    return False

            def do_DELETE(self):
                if not self.path.startswith("/whep/session/"):
                    return self._send(404, {"error": "no such path"})
                if not self._admitted(None):                        # to hang up: anybody this cluster knows
                    return
                ok = gw.hangup(self.path[len("/whep/session/"):])
                self._send(200 if ok else 404, {"closed": ok})

            def do_GET(self):
                if self.path == "/metrics":
                    return self._send(200, gw.metrics_text(), raw=True)
                if self.path == "/sessions":
                    return self._send(200, {cam: up.to_status() for cam, up in gw.upstreams.items()})
                self._send(404, {"error": "no such path"})

        return H

    def serve(self, host: str = "127.0.0.1", port: int = 8082) -> ThreadingHTTPServer:
        srv = ThreadingHTTPServer((host, port), self.handler())
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        if not self.url:
            self.url = f"http://{host}:{srv.server_address[1]}"
        return srv

    def run(self, poll: float = 2.0, stop=None) -> None:
        """One box: the loop as a process. Nomad or systemd restarts it."""
        stop = stop or threading.Event()
        while not stop.is_set():
            try:
                self.reconcile_once()
            except Exception:                            # noqa: BLE001 — one bad pass, not a silent worker
                log.exception("gateway pass failed")
            try:                                         # its own try, like the heartbeat's: the renewal used to be the last line of the pass, so a pass that raised half-way also let the leases run out (M19 of the review)
                self.renew_leases()
            except Exception:                            # noqa: BLE001
                log.exception("gateway lease renewal failed")
            try:                                         # in a try of its own: the heartbeat says the worker is alive even when its pass is not (the review's second pass)
                self.heartbeat_once()
            except Exception:                            # noqa: BLE001
                log.exception("gateway heartbeat failed")
            stop.wait(poll)
        for cam in list(self.upstreams):
            self._drop(cam)
        self.release_slot()
