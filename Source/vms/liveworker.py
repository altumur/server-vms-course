"""The live gateway — the second subsystem's worker. A gateway is a worker in
the platform's sense (a slot claimed by CAS, an assignment read from the
store, a heartbeat with capacity and headroom, count = N by demand) whose
unit is a camera's live FAN-OUT: one subscription to the worker's RTP tee,
N browsers behind it over WebRTC. Capacity is counted in viewers.

    live/streams/<cam>      the unit — created by its first viewer (`POST /live/streams` at the platform's console, a
                            `view` of the camera), deleted by the gateway a grace period after the last one leaves
                            (demand-created placement)
    live/workers/<g>        the assignment, written by the live controller (the platform's SpecController
                            run from live.subsystem.yaml)
    live/<g>/heartbeat      capacity, headroom (viewers it could still take), url, per-stream status

    POST   /whep/<cam>            WHEP, from the page itself with the door token `GET /live/where/<cam>` gave: an SDP
                                  offer in, 201 + the SDP answer out, Location: /whep/session/<id>
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
from w2cplatform.console import Deadlined, SendMixin, door_server, heartbeats, holder_of, read_body
from w2cplatform.worker import Worker
from w2cplatform.spec import SpecController
from w2cplatform.variables import Variables

from .config import LIVE_SPEC
from w2cplatform.rows import PARSE_ERRORS

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
        # "" while the stream is one a browser can play, otherwise the sentence the page shows beside
        # it. Filled from the caps the peer's parser negotiated, so it is empty until something flowed.
        self.codec: str = ""

    def to_status(self) -> dict:
        st = {"id": self.cam, "phase": "live" if self.peers else "idle", "sessions": len(self.peers),
              "server": self.server, "source": self.url, "epoch": self.epoch}
        if self.codec:
            st["codec"] = self.codec
        return st


class LiveWorker(Worker):
    """`name` is a slot (`g-1`); `url` is where a page offers WHEP (the door `GET /live/where/<cam>` hands out);
    `capacity` is viewers."""

    def __init__(self, name: str | None, vars_: Variables, objects, ctl: SpecController | None = None, url: str = "",
                 capacity: int | None = None, clock=time.monotonic, wall=time.time, server: str | None = None,
                 peer_factory=None, env: dict | None = None, resource_root: str | None = None):
        env = dict(os.environ if env is None else env)
        super().__init__(LIVE, None, vars_, objects, clock=clock, wall=wall, resource_root=resource_root, env=env)
        self._said_loopback: set = set()            # cameras whose fan-out we were told is on another server's loopback
        self.server = runtime.server(env, server)   # before the claim: a process on a decommissioned server gets no slot
        self.claim_at_start(name, env)   # a spare: an offer
        self.ctl = ctl                                              # the live SpecController with the gateway's token: deletes its own idle units
        self.url = url or env.get("GATEWAY_URL", "")
        self.owners: dict[str, str | None] = {}         # who opened each session (the door token's name): its own to hang up
        self.capacity = capacity if capacity is not None else int(env.get("CAPACITY", "100"))
        self.labels = runtime.labels(env)
        self.peer_factory = peer_factory or FakePeer
        self.upstreams: dict[str, Upstream] = {}
        self.sessions: dict[str, tuple[str, object]] = {}          # session id -> (cam, peer)
        self.session_at: dict[str, float] = {}                     # session id -> when it was offered
        self.answering = 0                                          # offers being answered: seats held, not yet sessions
        self.resets = 0                                             # subscriptions reopened because the camera moved or the source died
        self.swept = 0                                              # sessions closed because their viewer was gone
        self.subscriptions = 0                                      # how many times an RTP source was opened — the test's number
        self.refused: dict[str, str] = {}                           # cameras whose epoch could not be taken -> why (the heartbeat's `refused`)
        self.waiting: dict[str, str] = {}                           # cameras assigned here whose stream nobody serves -> why (the heartbeat's `waiting`)
        self.waiting_since: dict[str, float] = {}                   # …and since when, by this gateway's wall clock
        self.lock = threading.Lock()

    # -- where a camera's RTP is: the VMS heartbeat, never a call to the worker ----------------------
    def rtp_source(self, cam: str):
        """`(server, live_url, epoch)` of the worker holding the camera — its RTSP fan-out, on any server."""
        found = holder_of(self.objects, "vms/", cam, self.wall(), phase="running", field="live_url", eyes=self.eyes)   # fresh by change (the 13th pass)
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
        from w2cplatform.rows import number                 # a word for the epoch in one holder's status: that camera's, not the pass's (the seventh pass)
        return server, st["live_url"], number(f"vms/status/{cam}#epoch", st.get("epoch", 0), int, 0)

    # -- the reconcile pass: make the subscriptions equal the assignment -------------------------------
    # The store is read BEFORE the lock and written AFTER it; under the lock only `upstreams` and `sessions`
    # change. It used to hold the lock across every heartbeat read, the epochs and the row deletes, and `offer`
    # waits for the same lock: a store that answered slowly held every viewer at the door for as long as it took
    # (the review's second pass, minor).
    def reconcile_once(self, now: float | None = None) -> list[str]:
        now = self.wall() if now is None else now
        a = self.assignment()
        wanted = set(a.units)
        sources = {cam: self.rtp_source(cam) for cam in wanted}  # where every wanted camera is NOW: new ones, and the recheck of the old
        with self.lock:
            fresh = wanted - set(self.upstreams)
            idle = [cam for cam, up in self.upstreams.items() if not up.peers and up.idle_since is not None]
        for cam in fresh:
            if sources[cam] is not None and cam not in self.epochs:
                # One camera's epoch is that camera's trouble (the review's fifth pass): a garbled `live/epoch/<cam>` raised
                # out of the pass, and no camera after it was subscribed, none taken away was dropped — every pass.
                try:
                    self.take_epoch(cam)                            # one gateway per fan-out, fenced like any unit
                    self.refused.pop(cam, None)
                except Exception as e:                              # noqa: BLE001
                    self.refused[cam] = f"its epoch could not be taken: {e}"
                    log.error("%s: camera %s not subscribed: its epoch could not be taken: %s", self.name, cam, e)
        for cam in [c for c in self.refused if c not in wanted]:
            del self.refused[cam]                                   # not ours any more: nothing to say about it
        unsourced = self._wait_for(now, wanted, sources)
        rows = {}
        for cam in (idle if self.ctl is not None else ()):
            try:
                rows[cam] = self.ctl.unit(cam)
                self.row_parsed(cam)
            except PARSE_ERRORS as e:    # its row does not parse (`row_garbled`): nobody can say
                self.row_garbled(cam, e)                      # its grace has run out, and the fan-out is kept
        dropped, deleted = [], []
        with self.lock:
            for cam in wanted - set(self.upstreams):
                src = sources.get(cam)
                if src is None or cam not in self.epochs:
                    continue                                        # the camera is not recording anywhere: wait, say so in the heartbeat
                self.upstreams[cam] = Upstream(cam, *src); self.subscriptions += 1
                self.upstreams[cam].idle_since = now
            for cam in set(self.upstreams) - wanted:                # taken away (rebalanced, deleted): drop viewers, close the source
                self._drop(cam, release=False); dropped.append(cam)
            self._recheck(now, sources)
            self._sweep(now)
            # the grace period: an idle fan-out is deleted by the gateway itself — demand-created, demand-deleted
            for cam, up in list(self.upstreams.items()):
                row = rows.get(cam)
                if not up.peers and up.idle_since is not None and row is not None and now - up.idle_since >= int(row.get("grace", 30)):
                    deleted.append(cam)
        for cam in dropped:
            self.release(cam)
        for cam in deleted:
            self.ctl.delete(cam)                                    # the controller's next pass takes the placement back
        for cam in unsourced:
            try:
                self.ctl.delete(cam)
            except Exception as e:                                  # noqa: BLE001 — the store: the next pass
                log.warning("%s: stream %s, served by nobody, was not deleted: %s", self.name, cam, e)
                continue
            log.info("%s: a stream nobody serves aged out: %s (%s)", self.name, cam, self.waiting.get(cam, ""))
            self.waiting.pop(cam, None); self.waiting_since.pop(cam, None)
        return sorted(self.upstreams)

    # A STREAM NOBODY SERVES (ADR-0057, window 2; the product's `waitFor`): a camera assigned here that no worker says it
    # running — there is no such camera, or nobody records it, or its fan-out is on another server's loopback. The console
    # writes such a row: `ref` asks a row only for `must_match`, and nothing undeclared binds (ADR-0012). The gateway does
    # not serve it, says why in its heartbeat (`waiting: {cam: why}`), and once it has waited the row's `grace` — by this
    # gateway's wall clock from the pass that first saw it so — deletes it as it deletes an idle fan-out; the next viewer
    # makes a fresh row. A camera that comes up meanwhile is subscribed and forgotten here.
    def _wait_for(self, now: float, wanted: set, sources: dict) -> list[str]:
        out = []
        for cam in sorted(wanted):
            if cam in self.upstreams or sources.get(cam) is not None:
                continue
            self.waiting[cam] = self._why_no_source(cam)
            since = self.waiting_since.setdefault(cam, now)
            if self.ctl is None:
                continue
            try:
                row = self.ctl.unit(cam)
            except PARSE_ERRORS:
                continue                                            # its row does not parse: nobody can say its grace
            if row is not None and now - since >= int(row.get("grace", 30)):
                out.append(cam)
        for cam in [c for c in self.waiting if c not in wanted or c in self.upstreams or sources.get(c) is not None]:
            self.waiting.pop(cam, None); self.waiting_since.pop(cam, None)
        return out

    # Why a camera assigned here has no stream to fan out, in words a page shows.
    def _why_no_source(self, cam: str) -> str:
        if cam in self._said_loopback:
            return f"camera {cam} is served on another server's loopback: not reachable from {self.server}"
        try:
            from .config import SPEC
            row, _ = self.vars.get(SPEC.sub.config(SPEC.rows, cam))
        except (OSError, *PARSE_ERRORS):
            row = {}
        if not row or row.get("deleted") == "true":
            return f"no camera {cam}"
        return f"camera {cam} is recorded nowhere: no worker says it running"

    # A stream row NOBODY holds — a viewer asked for labels no gateway carries, or no gateway is left — is not this
    # gateway's to delete: it never held it. Its controller deletes it after `placement.unplaced.delete_after` (30 s,
    # `live.subsystem.yaml`; ADR-0067) — a cluster with no gateway at all kept such a row and its alarm for ever while
    # the sweep was here. The gateway deletes only the rows it held whose viewers' `grace` ran out (above).

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
    def _recheck(self, now: float, sources: dict | None = None) -> None:
        for cam, up in list(self.upstreams.items()):
            src = sources[cam] if sources is not None and cam in sources else self.rtp_source(cam)
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

    def _drop(self, cam: str, release: bool = True) -> None:
        up = self.upstreams.pop(cam)
        for sid, (c, peer) in list(self.sessions.items()):
            if c == cam:
                peer.close(); del self.sessions[sid]; self.session_at.pop(sid, None)
        if getattr(up, "pipeline", None) is not None:              # the real media path (gstvms.webrtc): close the source
            up.pipeline.close()
        if release:
            self.release(cam)                                       # the pass does this after its lock: a store write

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
        for sid in [s for s in self.owners if s not in self.sessions]:
            self.owners.pop(sid, None)                  # swept or hung up: nobody's to hang up any more
        self.heartbeat([up.to_status() for up in self.upstreams.values()], server=self.server, instance=self.instance,
                       # `url`: the page's door too (the platform's word: `/live/where/<cam>` hands it out with a token)
                       labels=",".join(self.labels), url=self.url, capacity=self.capacity, headroom=self.headroom(),
                       sessions=len(self.sessions), subscriptions=self.subscriptions, conflicts=self.conflicts(),
                       swept=self.swept, resets=self.resets, **({"refused": dict(self.refused)} if self.refused else {}),
                       **({"waiting": dict(self.waiting)} if self.waiting else {}))

    def metrics_text(self) -> str:
        return (f"# TYPE live_sessions gauge\nlive_sessions {len(self.sessions)}\n"
                f"# TYPE live_streams_up gauge\nlive_streams_up {len(self.upstreams)}\n"
                f"# TYPE live_headroom gauge\nlive_headroom {self.headroom()}\n")

    # The platform's keeper of this gateway's page door (`w2cplatform/door.py`): the console's token, checked here.
    def door_keeper(self):
        from w2cplatform.door import DoorKeeper
        if getattr(self, "_door_keeper", None) is None:
            self._door_keeper = DoorKeeper(self.name, self.wall, self.vars)   # the ring: the store's `door/keys`
        return self._door_keeper

    # -- the WHEP server -------------------------------------------------------------------------------
    def handler(self):
        gw = self

        class H(SendMixin, Deadlined, BaseHTTPRequestHandler):
            # A socket that says nothing is let go, as at the console (the review's fourth pass): an offer is one
            # request and one answer, and a client that sends half of it must not hold a gateway thread for ever.
            # …and its request line and headers have a deadline, whole (`Deadlined`; the sixth pass).
            timeout = float(os.environ.get("CONSOLE_TIMEOUT", 30.0))
            MAX_OFFER = 256 << 10                       # an SDP offer is kilobytes: the most this door reads of a body

            def log_message(self, *a): pass

            def do_OPTIONS(self):
                gw.door_keeper().preflight(self)

            def do_POST(self):
                self._extra_headers = gw.door_keeper().headers(self)      # a page of a console's origin reads the answer
                if not self.path.startswith("/whep/"):
                    return self._send(404, {"error": "no such path"})
                cam = self.path[len("/whep/"):].split("?")[0]
                who = self._admitted(cam)
                if who is None:
                    self.close_connection = True         # refused before the body: it is not read
                    return
                # The offer, bounded (the sixth pass: "every place a body is read"): it was `Content-Length` bytes,
                # whatever that said, in the memory of the process every viewer's stream goes through.
                if not read_body(self, self.MAX_OFFER):
                    return
                try:
                    sdp = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
                except UnicodeDecodeError:               # no text: 400, not a dropped connection (the eleventh review's sweep)
                    return self._send(400, {"error": "an offer is an SDP, as text (UTF-8)"})
                try:
                    sid, answer = gw.offer(cam, sdp)
                except KeyError:
                    return self._send(404, {"error": f"stream {cam} is not on this gateway"})
                except OverflowError:
                    return self._send(503, {"error": "this gateway is full"})
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
                # WHO WATCHED, LIVE (feedback CL), said where the stream is given now — the gateway (the console said it
                # while it proxied the offer): who (the name the console gave the token to), which camera, the session,
                # from where. And the session is that viewer's alone to hang up (the review's third pass).
                gw.owners[sid] = who.get("sub")
                gw.journal.say("live.view", user=who.get("sub") or "anybody", target=cam, session=sid, gateway=gw.name,
                               addr=str(self.client_address[0]))
                data = answer.encode()
                self.send_response(201); self.send_header("Content-Type", "application/sdp")
                for k, v in gw.door_keeper().headers(self):
                    self.send_header(k, v)
                self.send_header("Location", f"/whep/session/{sid}"); self.send_header("Content-Length", str(len(data)))
                self.end_headers(); self.wfile.write(data)

            # THE PAGE COMES HERE ITSELF (the boundary's step 6, the owner's decision 1: the console proxied the offer and
            # the hang-up, `LiveFront`). It comes with the door token the console gave with the stream's place (`GET
            # /live/where/<cam>`) — the console asked `view` on the camera then — for THIS gateway and this stream
            # (`w2cplatform/door.py`): checked here by the cluster's public key (`door/keys` in the store); none, the door is open and
            # says so. The token is needed to OPEN — an offer, a hang-up; a stream that is up lives by its session.
            def _admitted(self, cam):
                return gw.door_keeper().admit(self, "whep", f"live/{cam}")

            def do_DELETE(self):
                self._extra_headers = gw.door_keeper().headers(self)
                if not self.path.startswith("/whep/session/"):
                    return self._send(404, {"error": "no such path"})
                sid = self.path[len("/whep/session/"):]
                held = gw.sessions.get(sid)
                if held is None:
                    return self._send(404, {"closed": False})
                who = self._admitted(held[0])                       # to hang up: a token for that session's stream…
                if who is None:
                    return
                owner = gw.owners.get(sid)
                if owner and who.get("sub") != owner:               # …given to the viewer who opened it
                    return self._send(403, {"error": "not your session",
                                            "detail": f"{who.get('sub')} may hang up only the sessions it opened"})
                ok = gw.hangup(sid)
                if ok:
                    gw.owners.pop(sid, None)
                    gw.journal.say("live.view.ended", user=who.get("sub") or "anybody", session=sid, gateway=gw.name,
                                   addr=str(self.client_address[0]))
                self._send(200 if ok else 404, {"closed": ok})

            def do_GET(self):
                if self.path == "/metrics":
                    return self._send(200, gw.metrics_text(), raw=True)
                if self.path == "/sessions":
                    return self._send(200, {cam: up.to_status() for cam, up in gw.upstreams.items()})
                self._send(404, {"error": "no such path"})

        return H

    # Bounded like every door (`w2cplatform.console.door_server`; the review's sixth pass): so many connections at
    # once and so many to one address — a page's, which brings its viewer's offer here itself.
    def serve(self, host: str = "127.0.0.1", port: int = 8082) -> ThreadingHTTPServer:
        srv = door_server((host, port), self.handler())
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        if not self.url:
            self.url = f"http://{host}:{srv.server_address[1]}"
        return srv

    # The loop is the platform's (`Worker.run`: the pass, the lease step, the heartbeat, each in a try of its own, the
    # stand-in for a step that hangs, an orderly stop); what it stops is its fan-outs.
    def stop_unit(self, unit) -> None:
        self._drop(unit)

    def stop_all_units(self) -> None:
        for unit in list(self.upstreams):
            self._drop(unit)
