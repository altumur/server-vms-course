"""The one-box console, standard library — the platform's SpecConsole run
from the VMS spec, plus the routes only a VMS has (the footage):

    GET  /timeline/<cam>?from&to          every recording of the camera, from every recorder's archive door,
                                          fenced epochs marked; the device's own where ours has nothing
    GET  /export/<cam>?rec&from&to        the frames of an interval as a fragmented MP4 — what the page plays

Footage is not on this box's disk to be served by path. It is in volumes of ObjectStorage, each written by the
recorder that holds it, and every recorder serves its own (`archive_routes`, `vms/recworker.py`): the console
asks them, the way it asks the resources for events. Everything else — the page, /spec, /cameras, /where,
/marks, /metrics, the POST/PUT/DELETE of a camera — is `w2cplatform.console.SpecConsole` reading
`vms.subsystem.yaml`; nothing here knows what a camera's fields are. Its own process (`python3 -m vms
console`), with its own token: the operator's rows — cameras, next_id, retention — and never placement.
"""
from __future__ import annotations

import os
from http.server import ThreadingHTTPServer

import json
import logging
import threading
import time
import urllib.error
import urllib.request

from w2cplatform.access import token_of
from w2cplatform.console import PAGE, ClaimLost, Mount, SpecConsole, heartbeats, holder_of, holders, path_id, send_file   # noqa: F401  (PAGE, send_file re-exported for М11)
from w2cplatform.contract import slot_number
from w2cplatform.eventdatabase import MergedIndex
from w2cplatform.spec import Refused, SpecController
from w2cplatform.variables import Conflict

from . import keeps, volumes

log = logging.getLogger("vms.console")
READ_NOTE_EVERY = 60.0        # the same piece of archive, by the same person: one `archive.read` a minute
from .archive import subtract
from .controller import VmsController

EXPORT_MAX = 3600.0           # the longest interval one export answers: the page asks for minutes, a person for an hour
EXPORTS_AT_ONCE = 2           # exports one console makes at a time (`EXPORTS_AT_ONCE` in its environment): each is held in memory
EXPORT_RETRY = 5.0            # the `Retry-After` of an export refused for that
EXPORT_PIECE = 60.0           # an export reads a stretch this much at a time: what one recording holds in memory
DOOR_TIMEOUT = 5.0            # a recorder's door that does not answer in this is named, not waited for
SESSIONS_KEPT = 10000         # live sessions remembered for their hang-up: past it, the oldest is forgotten


class LiveFront:
    """The console's side of live video: the WHEP door. `POST /whep/<cam>`
    creates the fan-out unit `live/streams/<cam>` if nobody is watching yet
    (the console's token may write the operator's rows of the subsystem it
    fronts), finds which gateway the live controller placed it on, and
    proxies the offer there. Nothing here touches a worker, and the console
    never carries media: the answer names the gateway, and the browser's
    RTP goes gateway → browser from then on."""

    def __init__(self, ctl: VmsController, live_ctl: SpecController):
        self.ctl, self.live = ctl, live_ctl

    # Every gateway's last heartbeat: url, capacity, headroom, per-stream status.
    #
    # Deliberately NOT `holders()`: this is the one lookup that wants the stale ones. A gateway that has
    # gone quiet still holds the placement, and proxying to its address gets `OSError` — which the caller
    # turns into "gateway g-2 is not answering — unavailable, not lost". Filter it out here and that
    # becomes "no gateway holds this stream yet", which is a different fact and a worse one: the operator
    # would be told the stream was never placed when in truth its gateway is down.
    def gateways(self) -> dict:
        return heartbeats(self.live.objects, "live/")

    # (gateway name, its URL) for a stream, or (None, None) while unplaced or while the gateway has not heartbeaten.
    def where(self, cam: str) -> tuple[str | None, str | None]:
        pl = self.live.placement(cam)
        if not pl:
            return None, None
        hb = self.gateways().get(pl.worker)
        return pl.worker, (hb.extra.get("url") if hb else None)

    # A viewer's offer. 404 for an unknown camera; the unit is created on the first viewer (a concurrent
    # viewer's "exists" is fine); 503 with retry_after while the live controller has not placed it or the
    # gateway has not heartbeaten; else the gateway's 201 + SDP answer, with Location rewritten to go back
    # through this console (`/whep/session/<id>?gateway=<g>`).
    #
    # The viewer's token goes with it: the gateway checks it too (`LiveWorker.handler`) — the console is not
    # the only one who can reach that door.
    def offer(self, cam: str, sdp: str, labels: list[str], token: str | None = None):
        if self.ctl.camera(cam) is None:
            return 404, {"error": f"no camera {cam}", "detail": f"no camera {cam}"}
        if self.live.unit(cam) is None:
            # The viewer chooses where the stream is served from (`?labels=`: Lesson 13, a stream for the gateway
            # with a public address) — from among the places that EXIST. A label no live gateway carries made a
            # row nothing could place, and every next viewer of the camera was told "retry" for ever (the review's
            # second pass, major). Refused by name, and no row.
            #
            # …by ONE gateway (the review's third pass, Н-M8 and its minor): placement puts a stream on a gateway whose
            # labels cover ALL of the stream's, and the check took the union over every gateway — `public` on g-1 and
            # `eu` on g-2 passed for `public,eu`, and the row was one nothing could place, as before.
            sets = [{l for l in str(hb.extra.get("labels", "")).split(",") if l}
                    for hb in holders(self.live.objects, "live/", self.ctl.wall()).values()]
            if labels and not any(set(labels) <= s for s in sets):
                carried = set().union(*sets) if sets else set()
                unknown = sorted(set(labels) - carried)
                return 400, {"error": (f"no gateway carries the label{'s' if len(unknown) > 1 else ''} {', '.join(unknown)}" if unknown
                                       else f"no one gateway carries all of {', '.join(sorted(labels))}"),
                             "detail": f"a stream is placed on a gateway whose labels cover its own; the gateways here carry: "
                                       f"{'; '.join(','.join(sorted(s)) or '(none)' for s in sets) or 'none'}"}
            try:
                self.live.create({"cam": str(cam), "labels": labels})
            except Refused as e:
                if "exists" not in str(e):
                    return 400, {"error": str(e), "detail": str(e)}
        g, url = self.where(cam)
        if not g or not url:
            return 503, {"error": "no gateway holds this stream yet — retry", "detail": "placed on the live controller's next pass", "retry_after": 2}
        req = urllib.request.Request(f"{url}/whep/{cam}", data=sdp.encode(), method="POST",
                                     headers={"Content-Type": "application/sdp", **({"Authorization": f"Bearer {token}"} if token else {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data, status, loc = r.read(), r.status, r.headers.get("Location", "")
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace").strip()
            if e.code == 404:
                # The gateway is placed and up, and does not know this fan-out yet. That is what a row
                # created a moment ago looks like from here: the controller placed it, and the gateway
                # subscribes on its NEXT pass, up to a couple of seconds away. It comes back as 503 and
                # not as the gateway's own 404 because the two mean the same thing to a browser — wait —
                # and only one of them is a code the page retries. Forwarded verbatim it makes the
                # operator who pressed Live once press it twice, which is the defect the retry exists to
                # prevent. The gateway's own word is kept in `detail`: a 404 "not here" and a 404 "not
                # yet" differ only to whoever is asking.
                return 503, {"error": f"the fan-out is not up on {g} yet — retry",
                             "detail": f"placed on {g}; it subscribes on its next pass", "retry_after": 2}
            return e.code, {"error": f"gateway {g} said {e.code}", "detail": body}
        except OSError:
            return 503, {"error": f"gateway {g} is not answering — unavailable, not lost", "detail": g}
        sid = loc.rsplit("/", 1)[-1]
        return status, data, [("Content-Type", "application/sdp"), ("Location", f"/whep/session/{sid}?gateway={g}")]

    # The viewer hangs up: DELETE proxied to the gateway named in the session URL.
    def hangup(self, sid: str, g: str, token: str | None = None):
        hb = self.gateways().get(g)
        if not hb or not hb.extra.get("url"):
            return 404, {"error": f"no gateway {g}"}
        req = urllib.request.Request(f"{hb.extra['url']}/whep/session/{sid}", method="DELETE",
                                     headers={"Authorization": f"Bearer {token}"} if token else {})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, {"error": f"gateway {g} said {e.code}"}
        except OSError:
            return 503, {"error": f"gateway {g} is not answering"}

    # `GET /whep/<cam>`: the stream row, which gateway, and that gateway's status line for it — what the page shows.
    def status(self, cam: str) -> dict:
        g, url = self.where(cam)
        hb = self.gateways().get(g) if g else None
        st = next((s for s in (hb.status if hb else []) if str(s.get("id")) == str(cam)), None)
        return {"cam": cam, "stream": self.live.unit(cam), "gateway": g, "url": url, "status": st}


# Builds the `extra(handler, method, path, q)` function `SpecConsole` calls for every request its built-in
# routes do not claim. Returns `None` ("not ours") for anything it does not know, and for the footage when the
# console has no media (`media=False`: a console that fronts no recorders). Otherwise:
#
# - `GET /timeline/<cam>?from&to` — every recording of the camera from every live recorder's archive door
#   (`recorder_doors`), each span with `recording`, `recorder`, `volume`, `fenced` and `media` (the export to
#   play it by); a door that did not answer makes the reply `{segments, unreachable, note}`.
# - `GET /export/<cam>?rec&from&to` — the frames of the interval as one fragmented MP4, the reply written by
#   this function itself (it returns `()`), and a line `archive.read` with the sha256 of what left.
# - `GET /segment?cam=` — the DEVICE's own footage, through its holder's playback door.
# The holder of a camera, resolved NOW — never written into a span when it was drawn. A camera that moved
# between the drawing and the click would make a stored worker name a 404; resolving at request time costs
# one heartbeat read and cannot go stale. The fourth consumer of the same move, after the recorder, the
# gateway and the detector.
def device_playback(objects, cam, now: float) -> str | None:
    found = holder_of(objects, "vms/", cam, now, field="playback_url")
    return None if found is None else found[2]["playback_url"]


# What the DEVICE has and we do not — drawn only where our own footage does not cover it. The same
# subtraction the recorder fetches by (Lesson 16): one rule, two uses, so the picture and the work cannot
# disagree. A span like this is the one that will disappear — our archive keeps thirty days, a card keeps
# three — which is why the page offers to pin it.
def device_spans(objects, cam, ours: list[dict], t0: float, t1: float, now: float) -> list[dict]:
    found = holder_of(objects, "vms/", cam, now, field="coverage")
    if found is None:
        return []
    cov = found[2]["coverage"]
    want = (max(float(cov["from"]), t0), min(float(cov["to"]), t1))
    if want[1] <= want[0]:
        return []
    have = [(s["start"], s["end"]) for s in ours]
    return [{"start": a, "end": b, "media": None, "epoch": 0, "source": "device",
             "fenced": False, "device": True} for a, b in subtract(want, have)]


# A camera's footage lives under the units that record it, and the archive is keyed by unit (Lesson 7).
# A camera has as many recordings as archives it is written to: one (named `7`, the camera) on a box whose
# only archive is its disks, two (`7` and `7-cloud`) once the footage also goes to a network archive. This
# is the one function that turns a camera into that list, and the timeline below merges what it returns —
# which is why the day the second recording appeared, nothing above this line changed.
def recordings_of(rec_ctl, cam) -> list[str]:
    if rec_ctl is None:
        return [str(cam)]                      # no rec controller mounted: the old assumption, said out loud
    units = [str(r["id"]) for r in rec_ctl.units() if str(r.get("cam", r["id"])) == str(cam)]
    return units or [str(cam)]                 # nothing declared: the camera's own name, so old footage still shows


# Every recorder that serves its archive, live: `[(name, url, heartbeat)]`. A recorder holds ONE volume and its
# door answers for it — a camera recorded into two volumes, or one whose recording moved, is answered by two.
def recorder_doors(objects, now: float, lost_after: float = 45.0) -> list:
    out = []
    for name, hb in sorted(heartbeats(objects, "rec/").items()):
        url = str(hb.extra.get("archive_url") or "")
        if url and now - hb.ts <= lost_after:
            out.append((name, url.rstrip("/"), hb))
    return out


# The volumes nobody serves right now: a recorder went silent holding one, and no live recorder holds it since —
# the server is down, its disk with it, or a network archive is waiting for a spare. Its footage is not LOST: it is
# in that volume, and it is unavailable until a recorder holds the volume again. `[{volume, server, since}]`, from
# the recorders' last heartbeats; the timeline names them instead of drawing a hole where they are (М11 lesson 6).
def unserved_volumes(objects, now: float, lost_after: float = 45.0) -> list[dict]:
    live, stale = set(), {}
    for name, hb in heartbeats(objects, "rec/").items():
        vol = str(hb.extra.get("volume") or "")
        if not vol:
            continue                               # a spare holds nothing
        if now - hb.ts <= lost_after:
            live.add(vol)
        elif vol not in stale or hb.ts > stale[vol]["since"]:
            stale[vol] = {"volume": vol, "server": str(hb.extra.get("server", "")), "recorder": name, "since": hb.ts}
    return [v for k, v in sorted(stale.items()) if k not in live]


def _rec_epoch(ctl, unit) -> int | None:
    from w2cplatform.epoch import current_epoch
    try:
        return current_epoch(ctl.vars, f"rec/epoch/{unit}") or None
    except OSError:
        return None                                # the store did not answer: the doors' own word stands


def _door(url: str, timeout: float):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def vms_routes(media: bool = True, live: LiveFront | None = None, ctl=None, rec_ctl=None):
    """What the VMS adds to the generic console: the footage — from every recorder's archive and from the
    device's own — and the WHEP door to the live gateways. Returns None when a route is not ours, so the
    console answers 404."""
    ctl = ctl if ctl is not None else (live.ctl if live is not None else None)
    con_wall = (ctl.wall if ctl is not None else time.time)   # the catalogue needs "now" to know who is reachable

    # WHO READ THE ARCHIVE (the platform review, blocker 1 — the part of it that needs no login; feedback BI).
    # Footage left through this door and nothing said so. Every piece served is an event `archive.read` in
    # the console's own bucket, and a line in the log: who, which piece, from what address. A player asks
    # for one file in dozens of byte ranges, so the same piece by the same person is said once a minute.
    #
    # "Who" is `X-User` — the name the caller gave, or the one the gate proved from a token and wrote over
    # the header (`w2cplatform/access.py`): in a domain the journal names who the token said.
    seen_reads: dict[tuple, float] = {}
    reads_lock = threading.Lock()
    # The live sessions this console handed out — `{session: (who, camera, gateway)}`, oldest first, at most
    # `SESSIONS_KEPT`: what a hang-up is checked against.
    sessions: dict[str, tuple] = {}
    sessions_lock = threading.Lock()

    # WHAT LEFT, NOT WHAT WAS ASKED (the product, feedback BU). The line used to be written before the piece
    # went, and said only that somebody asked. It is written after, and says what was sent: the status, the
    # bytes and — when the piece left WHOLE (200, or 206 from the first byte to the last) — the sha256 of those
    # bytes. Then "is this the file you gave out" is answered by the journal: whoever holds the file takes its
    # digest and compares. A player seeking inside a file is a part, and a part has no digest.
    #
    # Once a minute per (who, piece) as a part and once a minute as a whole: otherwise a download right after
    # watching would be swallowed by the watching.
    def note_read(handler, rel: str, sent: dict) -> None:
        import hashlib
        user = handler.headers.get("X-User", "operator")
        addr = (getattr(handler, "client_address", None) or ("",))[0]
        now, whole = con_wall(), bool(sent.get("whole"))
        with reads_lock:
            if now - seen_reads.get((user, rel, whole), -1e18) < READ_NOTE_EVERY:
                return
            if len(seen_reads) > 10000:
                for k in [k for k, t in seen_reads.items() if now - t >= READ_NOTE_EVERY]:
                    del seen_reads[k]
            seen_reads[(user, rel, whole)] = now
        parts = rel.split("/")
        digest = sent.get("sha256") or (hashlib.sha256(sent["data"]).hexdigest() if whole and "data" in sent else None)
        log.info("archive read: %s got %s (%s, %d bytes) from %s", user, rel, sent.get("status"), sent.get("bytes", 0), addr)
        journal = getattr(extra, "journal", None)         # the console's journal (`w2cplatform/journal.py`), set by `make_console`
        if journal is not None:
            journal.say("archive.read", user=user, media=rel, addr=addr, status=sent.get("status"), bytes=sent.get("bytes", 0),
                        **({"sha256": digest} if digest else {}), **({"recording": parts[1]} if len(parts) > 1 else {}),
                        **({"unreachable": sent["unreachable"]} if sent.get("unreachable") else {}))

    def extra(handler, method, path, q):
        if live is not None and path.startswith("/whep/"):
            # WHO WATCHED, LIVE (feedback CL). Reading the archive was a journal line; watching the camera now was
            # not, and that is one of the two things authentication exists for. A viewer admitted — the gateway
            # answered the offer — is `live.view`: who, which camera, the session, the gateway, from where; a viewer
            # who hung up is `live.view.ended`. One who left without a word is the gateway's grace (Lesson 13), and
            # has no line: the console never heard.
            journal = getattr(extra, "journal", None)
            who = handler.headers.get("X-User", "operator")
            addr = (getattr(handler, "client_address", None) or ("",))[0]
            if method == "POST" and not path.startswith("/whep/session/"):
                cam = path_id(path)
                sdp = handler.rfile.read(int(handler.headers.get("Content-Length", 0))).decode()
                r = live.offer(cam, sdp, [l for l in q.get("labels", "").split(",") if l], token_of(handler.headers))
                if r[0] == 201:
                    loc = dict(r[2]).get("Location", "")
                    sid, g = loc.rsplit("/", 1)[-1].split("?")[0], loc.rsplit("gateway=", 1)[-1]
                    with sessions_lock:
                        sessions[sid] = (who, cam, g)
                        while len(sessions) > SESSIONS_KEPT:
                            sessions.pop(next(iter(sessions)))           # the oldest: a viewer who left without a word
                    if journal is not None:
                        journal.say("live.view", user=who, target=cam, session=sid, gateway=g, addr=addr)
                return r
            if method == "DELETE" and path.startswith("/whep/session/"):
                # HANGING UP IS THE VIEWER'S OWN (the review's third pass, minor). The gate read `session` as the
                # camera, and a viewer granted one camera could not put the phone down. A session names no camera
                # (`NO_UNIT`): the gate asks for any grant, and the session is checked here — the id this console
                # handed out, to the caller it handed it to, on the gateway it named then, whatever `?gateway=` says.
                sid = path[len("/whep/session/"):]
                with sessions_lock:
                    held = sessions.get(sid)
                if getattr(handler, "sees", None) is not None:    # gated: the caller is a proven name
                    if held is None:
                        return 404, {"error": "no such session", "detail": "not a session this console handed out"}
                    if held[0] != who:
                        if journal is not None:
                            journal.say("access.denied", user=who, capability="hangup", target=held[1], session=sid)
                        return 403, {"error": "not your session", "detail": f"{who} may hang up only the sessions it opened"}
                g = held[2] if held is not None else q.get("gateway", "")
                r = live.hangup(sid, g, token_of(handler.headers))
                if r[0] in (200, 204):
                    with sessions_lock:
                        sessions.pop(sid, None)
                    if journal is not None:
                        journal.say("live.view.ended", user=who, session=sid, gateway=g, addr=addr)
                return r
            if method == "GET" and not path.startswith("/whep/session/"):
                return 200, live.status(path_id(path))                  # GET /whep/<cam>: the stream, its gateway, that gateway's word
            return None
        # A COMMAND to a device, filed as a row for whoever holds it — `POST /requests`. Not a call: the
        # console does not open devices, and the one process that has this device open is the worker that
        # holds it (М10B, lesson 4). It writes the row; the holder performs it on its next pass, says so
        # in its heartbeat, and the controller clears it.
        #
        # `valid_until` is the field that makes this safe to file and forget. Thirty seconds by default,
        # because the commands an operator sends are answers to something they are looking at: a door
        # opened a minute after the button is an incident, and a request that misses its moment must
        # expire rather than wait. Automation will set its own, from the scenario.
        if method == "POST" and path == "/requests" and ctl is not None:
            # A command is not idempotent by nature — the same door pulsed twice IS two pulses — so the request's
            # NAME has to make the retry the same request: the `Idempotency-Key` is the row's id unless the body
            # names one, and the row is written create-only; a second POST under the key finds the row and is
            # answered the same 202 (the platform review, M17; the review's second pass). Named by the clock it
            # was a new row every time, and a retried click opened the door again.
            key = handler.headers.get("Idempotency-Key")
            if not key:
                return 400, {"detail": "Idempotency-Key header is required: a command retried is the same command",
                             "error": "Idempotency-Key required"}
            raw = handler.rfile.read(int(handler.headers.get("Content-Length", 0)))
            # …and the row lives only until its holder has answered it: the controller clears it, and a retry ninety
            # seconds later found no row and filed the command again (the review's third pass, minor). So the key is
            # ALSO kept where the console keeps every key (`IdempotencyKeys`, `<sub>/idem/`, for a day) — the same
            # claim, the same reply to the same caller with the same body, whichever console the retry reaches.
            seen = getattr(extra, "seen", None)
            if seen is None:
                return file_request(handler, json.loads(raw or b"{}"), key)
            try:
                prior = seen.claim(key, handler.headers.get("X-User", "operator"), raw)
            except Refused as e:
                return 400, {"detail": str(e), "error": str(e)}
            except OSError as e:
                return 503, {"detail": f"the store did not answer: {e}", "error": "store unavailable"}
            if prior is not None:
                return prior
            try:
                reply = file_request(handler, json.loads(raw or b"{}"), key)
            except Exception:
                seen.release(key)
                raise
            if reply[0] != 202:
                seen.release(key)                                     # a refusal is not a command: the key is not spent on it
                return reply
            try:
                seen.store(key, reply)
            except (OSError, ClaimLost) as e:
                log.warning("the command under %s was filed, and not remembered under its key: %s", key, e)
            return reply
        if method == "POST" and path == "/backfill" and media:
            # This used to answer 202 and store nothing: the text below was true about what the recorder
            # WOULD do and false about anything having been asked. The request is a row now
            # (`rec/requests/<id>`), the recorder reads it, and the id is deterministic — a retried POST
            # for the same range is the same row, not a second fetch.
            if rec_ctl is None:
                return 503, {"detail": "no recorder subsystem behind this console", "error": "no rec"}
            body = json.loads(handler.rfile.read(int(handler.headers.get("Content-Length", 0))) or b"{}")
            cam, t0, t1 = str(body.get("cam", "")), float(body.get("from", 0)), float(body.get("to", 0))
            if not cam or t1 <= t0:
                return 400, {"detail": "a backfill wants a camera and a range", "error": "bad range"}
            # WHICH recording gets the missing footage: the one the operator named, or the camera's first.
            # A backfill writes into a unit's tree, and with several recordings of one camera there is no
            # "the" tree any more — the caller says, or takes the first and the answer says which it was.
            units = recordings_of(rec_ctl, cam)
            unit = str(body.get("rec") or "") or units[0]
            if unit not in units:
                return 400, {"detail": f"camera {cam} has no recording {unit}", "error": "no such recording"}
            rid = f"{unit}-{int(t0)}-{int(t1)}"
            rec_ctl.vars.put(rec_ctl.spec.sub.request_key(rid),
                             {"unit": str(unit), "cam": cam, "from": str(t0), "to": str(t1),
                              "at": str(con_wall()), "by": handler.headers.get("X-User", "operator")})
            return 202, {"queued": {"id": rid, "unit": str(unit), "cam": cam, "from": t0, "to": t1},
                         "detail": "the recorder fetches it on its next pass — outside the budget and the window, "
                                   "because a person asked for it"}
        if method != "GET" or not media:
            return None
        if (path == "/segment" or path == "/segment/") and ctl is not None:                 # the device's own footage, through its holder
            return segment(handler, q)
        # The camera is `path_id`'s — the segment the gate checked, never the last one (the review's third pass,
        # blocker 1: `/export/1/2` was checked on 1 and served 2; such a path is 404 now, before the gate).
        if path.startswith("/timeline/"):
            return timeline(path_id(path), q)
        if path.startswith("/export/"):
            return export(handler, path_id(path), q)
        return None

    # The command, as a row: `(202, {queued, detail})`, or the refusal.
    def file_request(handler, body: dict, key: str):
        unit, action = str(body.get("unit", "")), str(body.get("action", ""))
        if not unit or ctl.camera(unit) is None:
            return 404, {"detail": f"no unit {unit}", "error": "no such unit"}
        if action not in ("output", "preset"):
            return 400, {"detail": f"actions are output and preset, not {action!r}", "error": "unknown action"}
        now = con_wall()
        rid = str(body.get("id") or key)
        if "/" in rid or rid in (".", "..") or len(rid) > 200:
            return 400, {"detail": "a request id is a name, not a path", "error": "bad id"}
        until = float(body.get("valid_until") or now + 30)
        if until - now > 600:                                     # the holder refuses it (`VmsWorker.MAX_VALID`): say so at the door
            return 400, {"detail": "a command's `valid_until` is at most ten minutes away", "error": "too far"}
        row = {"unit": unit, "action": action, "at": str(now), "by": handler.headers.get("X-User", "operator"),
               "valid_until": str(until)}
        for f in ("port", "state", "pulse_ms", "n"):
            if body.get(f) is not None:
                row[f] = str(body[f])
        try:
            ctl.vars.put(ctl.spec.sub.request_key(rid), row, cas=0)
        except Conflict:
            row = ctl.vars.get(ctl.spec.sub.request_key(rid))[0] or row   # the same request, filed already: its row is the answer
        return 202, {"queued": {"id": rid, **row},
                     "detail": "the worker holding this device performs it on its next pass; "
                               "after valid_until it expires unperformed"}

    # `GET /segment?cam=` — the device's own footage, through its holder's playback door: the URL, and a line.
    def segment(handler, q: dict):
        url = device_playback(ctl.objects, q.get("cam"), con_wall())
        if url is None:
            return 503, {"detail": "nobody holds this camera right now", "error": "unheld"}
        # The door to the DEVICE's footage is handed out here, and the footage then goes holder → browser:
        # this console never sees the bytes, so what it can say is that it gave the door, to whom, for which
        # minutes (the review's third pass, Н-B1's remainder: it went with no line at all). One line per URL
        # handed out — a page asks once per click, not once per byte range.
        journal = getattr(extra, "journal", None)
        if journal is not None:
            journal.say("archive.read", user=handler.headers.get("X-User", "operator"), source="device",
                        target=str(q.get("cam")), addr=(getattr(handler, "client_address", None) or ("",))[0],
                        **{"from": q.get("from", 0), "to": q.get("to", 1e12)})
        return 200, {"playback": f"{url}?from={q.get('from', 0)}&to={q.get('to', 1e12)}"}

    # A camera's timeline: every recording of it, from every recorder's door — each holds one volume, and what a
    # recording wrote over its life may be in more than one. A door that does not answer is NAMED, not waited
    # for: a timeline with a hole the page explains beats one that never comes. So is a volume nobody serves now
    # (`unserved_volumes`): unavailable, not lost. Each span says whose it is and how to play it (`media`: the
    # export of that recording; the page adds the minutes).
    def timeline(cid: str, q: dict):
        t0, t1 = float(q.get("from", 0)), float(q.get("to", 1e12))
        ours, unreachable = [], []
        doors = recorder_doors(ctl.objects, con_wall()) if ctl is not None else []
        for unit in recordings_of(rec_ctl, cid):
            # Fenced against the RECORDING's epoch, which the store holds — a door knows only its own recorder's,
            # and the zombie's stream may be in another volume than the survivor's. A copy (`e0`, a keep's) is
            # nobody's writer and is never fenced.
            cur = _rec_epoch(ctl, unit)
            for name, url, hb in doors:
                try:
                    body = json.loads(_door(f"{url}/timeline/{unit}?from={t0}&to={min(t1, 1e11)}", DOOR_TIMEOUT))
                except (OSError, ValueError):
                    unreachable.append(name)
                    continue
                for sp in body.get("spans", []):
                    fenced = bool(sp.get("fenced")) or (cur is not None and 0 < int(sp.get("epoch", 0)) < cur)
                    ours.append({**sp, "fenced": fenced, "recording": unit, "recorder": name,
                                 "volume": hb.extra.get("volume", ""), "media": f"/export/{cid}?rec={unit}"})
        extra_ = device_spans(ctl.objects, cid, ours, t0, t1, con_wall()) if ctl is not None else []
        spans = sorted(ours + extra_, key=lambda d: (d["start"], d["epoch"]))
        gone = unserved_volumes(ctl.objects, con_wall()) if ctl is not None else []
        if unreachable or gone:
            notes = []
            if unreachable:
                notes.append("a recorder's archive door did not answer: its footage is missing from this picture")
            if gone:
                notes.append("footage in " + ", ".join(f"{g['volume']} (on {g['server']})" for g in gone) +
                             " is unavailable until a recorder holds it again — not lost")
            return 200, {"segments": spans, "unreachable": sorted(set(unreachable)), "unavailable": gone,
                         "note": "; ".join(notes)}
        return 200, spans

    # An interval as a fragmented MP4 (`fmp4.from_samples`): the frames from every door that holds them, each
    # moment taken once — the first door's — and then, as everything that leaves through this console, a line
    # `archive.read` with what was sent and its sha256: the answer to "is this the file you gave out".
    #
    # AT MOST `EXPORTS_AT_ONCE` OF THEM, AND EACH A STREAM (the review's third pass, major). An export held its
    # interval's samples and the MP4 made of them in memory — an hour of an 8 Mbit/s camera is some 3.6 GB, twice —
    # and nothing bounded how many ran at once: two or three from anybody with `view` took the console down, and the
    # requests' loop with it. Now an export reads a minute of each recording at a time and writes the MP4 as it is
    # made (`_export`), so one holds about a minute per recording; and past the bound the next is 503 with
    # `Retry-After`, which a client waits out — each export is also a minute of reading from a recorder's door.
    exporting = threading.BoundedSemaphore(max(1, int(os.environ.get("EXPORTS_AT_ONCE", EXPORTS_AT_ONCE))))

    def export(handler, cid: str, q: dict):
        if not exporting.acquire(blocking=False):
            return 503, json.dumps({"detail": "this console is making as many exports as it makes at once — retry",
                                    "error": "busy"}).encode(), [("Content-Type", "application/json"),
                                                                 ("Retry-After", str(int(EXPORT_RETRY)))]
        try:
            return _export(handler, cid, q)
        finally:
            exporting.release()

    def _export(handler, cid: str, q: dict):
        import hashlib
        import heapq
        import itertools
        import struct
        from . import fmp4
        try:
            t0, t1 = float(q.get("from", 0)), float(q.get("to", 0))
        except ValueError:
            return 400, {"detail": "from and to are unix seconds", "error": "bad range"}
        if t1 <= t0 or t1 - t0 > EXPORT_MAX:
            return 400, {"detail": f"an export is an interval of at most {EXPORT_MAX:.0f} s", "error": "bad range"}
        # Each moment from the EPOCH that owns it, across every door — a door applies `authoritative` to the
        # volume it holds, and a fenced writer's stream may be in another volume than the survivor's. So the doors'
        # timelines are asked first, the rule is run over all of them, and each stretch is read from the door that
        # holds its owner. A door that does not answer is named in the reply's headers: a piece with a hole the
        # caller can see.
        from w2cplatform.obsd import Sample, unix_s
        from .archive import Span, authoritative
        # `rec` picks ONE of this camera's recordings — never another camera's: the gate checked `view` on the
        # camera in the path, and a recording named in the query must be hers (the review's second pass, blocker 1).
        units = recordings_of(rec_ctl, cid)
        if q.get("rec"):
            units = [u for u in units if u == str(q["rec"])]
            if not units:
                return 404, {"detail": f"recording {q['rec']} is not a recording of camera {cid}", "error": "not hers"}
        doors = recorder_doors(ctl.objects, con_wall()) if ctl is not None else []
        unreachable: list[str] = []

        # THE FRAMES OF A STRETCH, A MINUTE AT A TIME (the review's third pass, major; the door streams since its
        # blocker 6). Every door's answer used to be decoded into one list and the MP4 made of all of it: an hour
        # of an 8 Mbit/s camera, twice over, in the console. A stretch is now read in pieces of `EXPORT_PIECE`,
        # cut at a key frame the way the recorder cuts what it lands (`RecWorker._pieces`): a piece ends where its
        # last group of pictures begins, and the next piece starts there. A door that fails half way ends its
        # stretch there and is named; what came before it has gone out already.
        def frames_of(name: str, url: str, unit: str, lo: float, hi: float):
            at = lo
            while at < hi:
                top = min(hi, at + EXPORT_PIECE)
                try:
                    got = sorted(Sample.decode_all(_door(f"{url}/samples/{unit}?from={at}&to={top}", 30.0)),
                                 key=lambda s: s.begin)
                except (OSError, ValueError, struct.error):
                    unreachable.append(name)
                    return
                nxt = top
                if top < hi:
                    cut = next((i for i in range(len(got) - 1, -1, -1) if got[i].key and unix_s(got[i].begin) > at), None)
                    if cut is not None:
                        nxt, got = unix_s(got[cut].begin), got[:cut]
                yield from got
                at = nxt

        streams = []
        for unit in units:
            spans, where = [], {}
            for name, url, _ in doors:
                try:
                    body = json.loads(_door(f"{url}/timeline/{unit}?from={t0}&to={t1}", DOOR_TIMEOUT))
                except (OSError, ValueError):
                    unreachable.append(name)
                    continue
                for sp in body.get("spans", []):
                    span = Span(unit, int(sp.get("epoch", 0)), float(sp["start"]), float(sp["end"]), int(sp.get("bytes", 0)),
                                str(sp.get("source", "live")))
                    spans.append(span)
                    where.setdefault(span, (name, url))
            stretches = sorted(authoritative(spans, t0, t1), key=lambda x: x[1])
            streams.append(itertools.chain.from_iterable(frames_of(*where[span], unit, lo, hi) for span, lo, hi in stretches))

        # The recordings of the camera merged by time — one piece per recording held at a time — and each moment
        # taken once, the first door's. The MP4 is written as it is made (`fmp4.Writer`, one fragment per group of
        # pictures): the headers go with the first key frame, because that is when "nothing recorded" (404) and "not
        # playable" (415) can no longer be the answer. So there is no `Content-Length`, the connection's end is the
        # file's end, and a door that fails after the first byte cannot be named in a header any more: it is in the
        # log and in the journal's line (`unreachable`), and the file has the hole.
        sent = {"bytes": 0, "sha": hashlib.sha256(), "head": False}

        class Out:
            def write(self, b: bytes) -> None:
                handler.wfile.write(b)
                sent["bytes"] += len(b); sent["sha"].update(b)

        writer, frag, end, broken, said = None, [], None, None, 0
        try:
            for smp in heapq.merge(*streams, key=lambda s: s.begin):
                if end is not None and smp.begin < end:
                    continue                             # this moment came from another door already
                if writer is None:
                    if not smp.key:
                        continue
                    try:
                        sps, pps = fmp4.param_sets(smp.body)
                        width, height = struct.unpack("<II", smp.sub[:8]) if len(smp.sub) >= 8 else (0, 0)
                        writer = fmp4.Writer(Out(), sps, pps, width, height)
                    except ValueError as e:
                        return 415, {"detail": str(e), "error": "not playable"}
                    handler.send_response(200)
                    handler.send_header("Content-Type", "video/mp4")
                    if unreachable:
                        handler.send_header("X-Archive-Unreachable", ",".join(sorted(set(unreachable))))
                    handler.send_header("Connection", "close")
                    handler.end_headers()
                    handler.close_connection = True
                    sent["head"], said = True, len(unreachable)
                if smp.key and frag:
                    writer.write_fragment(frag)
                    frag = []
                frag.append(fmp4.Sample(fmp4.to_avcc(smp.body), max(1, int(smp.end - smp.begin)), smp.key))
                end = smp.end
            if writer is None:
                return 404, {"detail": f"no footage of camera {cid} in that interval", "error": "nothing recorded"}
            writer.write_fragment(frag)
        except (OSError, ValueError) as e:              # the caller went away, or a frame would not convert
            if not sent["head"]:
                raise
            broken = str(e)
            log.warning("an export of camera %s stopped after %d bytes: %s", cid, sent["bytes"], e)
        late = sorted(set(unreachable[said:]))
        if late:
            log.warning("an export of camera %s has holes: %s did not answer after the first byte", cid, ",".join(late))
        note_read(handler, f"rec/{','.join(units)}/{t0:.0f}-{t1:.0f}",
                  {"status": 200, "bytes": sent["bytes"], "whole": broken is None,
                   **({"sha256": sent["sha"].hexdigest()} if broken is None else {}),
                   **({"unreachable": ",".join(late)} if late else {})})
        return ()
    return extra


# `SpecConsole(ctl, marks_root=archive_root, wall=wall, extra=vms_routes(media, …), media=media)`. With a
# resource root on this server: operator marks (`POST /marks`) go into the console's own event log under
# `console/<hostname:pid>/e1/` there. With media (the console fronts recorders): `/spec` reports `media: true`
# so the page draws a timeline and a player.
# What the `rec` mount adds to the generic console: the archives themselves. `GET /rec/volumes` is the
# operator's answer to "where can this footage go, and is anybody writing there"; the POST and the DELETE
# are the declaration. Three numbers ride along, and they are the point of the screen:
#
#   wanted  — declared archives that are enabled: how many recorder processes this cluster needs
#   serving — how many of them a live recorder is actually holding
#   spare   — processes running with no volume, ready to take the next one declared
#
# `spare: 0` with `serving < wanted` is the one state that needs a person: an archive was declared and
# there is no process free to serve it. The console says so; it does not start one. Starting processes is
# the scheduler's, here as everywhere — what the platform owes is the number, not the action.
# How many recorder processes are missing, and THE COMMAND that starts them — written out, for the
# operator to run. Not a button: a console with a token to its orchestrator would be a console that can
# start processes, which is the one thing this whole design keeps out of the platform (М10A, lesson 7).
# What it can do is stop making the operator translate. It knows how many are missing (an archive is
# declared and nobody, spare included, can take it), and it knows which orchestrator started IT —
# `NOMAD_ALLOC_ID` in its own environment — so it can write the line out in that orchestrator's words.
#
# The slot name for a box is the next free number: instances are named by the slot they claim
# (`recworker@r-3` claims `r-3`), so the command has to name one nobody holds.
def scale_hint(rec_ctl: SpecController, unserved: int, spare: int) -> dict:
    needed = max(0, unserved - spare)                   # a spare takes an archive on its next pass
    if not needed:
        return {"needed": 0, "how": None}
    if os.environ.get("NOMAD_ALLOC_ID"):
        live = len(rec_ctl.workers_seen())
        return {"needed": needed, "how": f"nomad job scale recworker {live + needed}"}
    taken = list(rec_ctl.slots())
    nxt = max([slot_number(n) for n in taken] + [0]) + 1
    prefix = (taken[0].rsplit("-", 1)[0] if taken and "-" in taken[0] else "r")
    return {"needed": needed,
            "how": " && ".join(f"systemctl start recworker@{prefix}-{nxt + i}" for i in range(needed))}


# The two numbers a scaling policy needs and nothing else has. `declared` is how many archives the
# operator says should be written into; `unserved` is how many of those nobody is holding — which, added
# to the recorders that are live, is the count this job must reach.
#
# Why here and not in the platform's `metrics_text`: it counts VOLUMES, and the platform has never heard
# of one. `metrics_extra` is the seam, the same shape as `extra` for routes.
# Running, and holding no archive. Two sources and not one, because the obvious single source is wrong
# in a window that lasts: a recorder names its volume in the heartbeat once it has TAKEN it, and taking
# is not opening — a bucket whose previous writer is still letting go can take the better part of a
# minute. A process counted spare in that window is a spare the operator is promised and the scaling
# policy will not ask to replace, and both numbers heal themselves, which is exactly when nobody notices.
#
# So a worker whose instance holds a volume is not spare, whatever its heartbeat says about where it is.
def spare_workers(rec_ctl: SpecController) -> list[str]:
    holding = {s.holder for s in volumes.holders(rec_ctl.vars, rec_ctl.spec.sub).values()
               if s.holder and not s.released}
    out = []
    for w, hb in rec_ctl.workers_seen().items():
        if rec_ctl.place_of(w) == "" and str(hb.extra.get("instance", "")) not in holding:
            out.append(w)
    return sorted(out)


def rec_metrics(rec_ctl: SpecController):
    def lines() -> list[str]:
        view = volumes.served(rec_ctl.vars, rec_ctl.spec.sub, rec_ctl.wall(), objects=rec_ctl.objects)
        unserved = view["wanted"] - view["serving"]
        spare = len(spare_workers(rec_ctl))
        return ["# TYPE rec_volumes_declared gauge",
                f"rec_volumes_declared {view['wanted']}",
                "# TYPE rec_volumes_unserved gauge",
                f"rec_volumes_unserved {unserved}",
                # The number a scaling policy must use, and the reason it is not `unserved` itself: an
                # archive nobody CAN take does not become takeable by starting processes. A local volume
                # declared for a server where the scheduler puts no recorder leaves `unserved` at one for
                # ever, and a policy reading that would ask for one more worker, then another, up to its
                # ceiling — every one of them a spare that cannot help. Subtracting the spares stops it
                # after the first: one free process proves the shortage is not a shortage of processes.
                "# TYPE rec_recorders_needed gauge",
                f"rec_recorders_needed {max(0, unserved - spare)}",
                # Keeps that nothing copies: marks set while no incidents volume is declared (the review's second
                # pass, B10). Not zero is evidence somebody asked for and the ring will take all the same.
                "# TYPE rec_keeps_unprotected gauge",
                f"rec_keeps_unprotected {0 if volumes.incidents(rec_ctl.vars) else len(keeps.declared(rec_ctl.vars))}",
                *_recorders(rec_ctl)]
    return lines


# What each recorder says about itself, from its heartbeat (feedback BG). A fenced recorder and a recorder with
# nothing assigned both showed "0 running"; a volume that would not open, a writer that stalled, an archive that
# went away were in the heartbeat and on the page, and there was nothing to put an alert on.
def _recorders(rec_ctl: SpecController) -> list[str]:
    hbs = sorted(heartbeats(rec_ctl.objects, rec_ctl.spec.sub.name).items())
    now = rec_ctl.wall()
    out = ["# TYPE rec_recordings gauge"]
    for w, hb in hbs:
        phases: dict[str, int] = {}
        for st in hb.status:
            phases[str(st.get("phase", "?"))] = phases.get(str(st.get("phase", "?")), 0) + 1
        out += [f'rec_recordings{{worker="{w}",phase="{ph}"}} {n}' for ph, n in sorted(phases.items())]
    out.append("# TYPE rec_volume_error gauge")
    out += [f'rec_volume_error{{worker="{w}"}} {1 if hb.extra.get("volume_error") else 0}' for w, hb in hbs]
    out.append("# TYPE rec_archive_away_seconds gauge")
    out += [f'rec_archive_away_seconds{{worker="{w}"}} '
            f'{round(now - float(hb.extra["archive_away_since"]), 1) if float(hb.extra.get("archive_away_since") or 0) else 0}'
            for w, hb in hbs]
    # Why the volume stopped taking samples, by kind: `away` (the daemon, a network — waited for) or `wrong` (a
    # person has to act — the volume is handed back). One line per recorder that has a failure, none otherwise.
    out.append("# TYPE rec_archive_failure gauge")
    out += [f'rec_archive_failure{{worker="{w}",kind="{hb.extra["archive_failure"]}"}} 1' for w, hb in hbs
            if hb.extra.get("archive_failure")]
    out.append("# TYPE rec_writer gauge")                          # 1 for the state the volume's writer is in
    out += [f'rec_writer{{worker="{w}",state="{(hb.extra.get("writer") or {}).get("state") or "ok"}"}} 1' for w, hb in hbs]
    # How long since each recording last took anything from its source (feedback BI; the review's
    # `rec_archive_gap_seconds`). `rec_recordings{phase="running"}` says the pipeline is up; this says it is
    # being FED. Counted from the moment the recorder says bytes last arrived — so a recorder that went silent
    # grows here too — and only for recorders whose actuator measures.
    out.append("# TYPE rec_last_frame_age_seconds gauge")
    out += [f'rec_last_frame_age_seconds{{unit="{st["id"]}"}} {round(max(0.0, now - float(st["last_frame_at"])), 1)}'
            for w, hb in hbs for st in hb.status if st.get("last_frame_at")]
    # What the engine refused of each recording's samples, by its answer (the review's third pass). The writer watch
    # counts the VOLUME, and one camera of thirty that was never written — its group of pictures larger than a block
    # — left it `ok`. A counter per recording and answer, from what the recorder's sinks were told.
    out.append("# TYPE rec_samples_refused_total counter")
    out += [f'rec_samples_refused_total{{unit="{st["id"]}",status="{k}"}} {n}' for w, hb in hbs for st in hb.status
            for k, n in sorted((st.get("samples_refused") or {}).items())]
    # How far back each recording goes, and whether its volume's ring has closed inside the floor it was promised
    # (`min_depth_days`; feedback BM).
    out.append("# TYPE rec_archive_depth_days gauge")
    out += [f'rec_archive_depth_days{{unit="{st["id"]}"}} {st["depth_days"]}' for w, hb in hbs for st in hb.status if "depth_days" in st]
    out.append("# TYPE rec_archive_shallow gauge")
    out += [f'rec_archive_shallow{{unit="{st["id"]}"}} {1 if st.get("shallow") else 0}' for w, hb in hbs for st in hb.status if "depth_days" in st]
    out.append("# TYPE rec_unconfirmed_seconds gauge")            # a recording going on under an epoch the store has not confirmed
    out += [f'rec_unconfirmed_seconds{{unit="{st["id"]}"}} {st["unconfirmed_s"]}'
            for w, hb in hbs for st in hb.status if st.get("lease") == "unconfirmed"]
    return out


# What the VMS adds to `/metrics`: the commands its holders performed, refused or let expire, summed over their
# heartbeats. `expired` over the total is the number that says a scenario's requests live shorter than the road
# from an event to the device.
def vms_metrics(ctl):
    def lines() -> list[str]:
        total = {"performed": 0, "refused": 0, "expired": 0, "unknown": 0}
        for hb in heartbeats(ctl.objects, ctl.spec.sub.name).values():
            for k, v in (hb.extra.get("command_counts") or {}).items():
                if k in total:
                    total[k] += int(v)
        # …and the requests of automation this console dropped as too old (`jobs.expired`): a scenario said
        # `fired` and nothing happened. Zero is the number this should stay at; climbing, it says the requests'
        # loop is late (the review's second pass).
        from . import jobs
        return (["# TYPE vms_commands_total counter"] + [f'vms_commands_total{{outcome="{k}"}} {v}' for k, v in total.items()]
                + ["# TYPE vms_requests_expired_total counter"]
                + [f'vms_requests_expired_total{{sub="{s}"}} {n}' for s, n in sorted(jobs.expired.items())])
    return lines


# What automation adds: each evaluator's last pass, from its heartbeat — how long it took, how many queries it
# made, how far its furthest cursor trails `now`, and the longest road from an event to a request it filed.
# Without these a slow pass and a held cursor are visible nowhere (the notes on the event log's load).
def auto_metrics(auto_ctl):
    def lines() -> list[str]:
        names = (("pass_seconds", "auto_pass_seconds"), ("queries", "auto_queries_per_pass"),
                 ("lag_seconds", "auto_cursor_lag_seconds"), ("latency_seconds", "auto_firing_latency_seconds"))
        out = []
        hbs = heartbeats(auto_ctl.objects, auto_ctl.spec.sub.name)
        for key, metric in names:
            out.append(f"# TYPE {metric} gauge")
            out += [f'{metric}{{worker="{w}"}} {hb.extra[key]}' for w, hb in sorted(hbs.items()) if key in hb.extra]
        # Counted since each evaluator started, so a scrape misses nothing that happened between two of them:
        # the road from an event to its request as a histogram, and the firings too late to file.
        from vms.autoworker import AutoWorker
        out.append("# TYPE auto_event_to_request_seconds histogram")
        for w, hb in sorted(hbs.items()):
            lat = hb.extra.get("latency")
            if not lat:
                continue
            for le, n in zip(AutoWorker.LATENCY_BUCKETS, lat["buckets"]):
                out.append(f'auto_event_to_request_seconds_bucket{{worker="{w}",le="{le:g}"}} {n}')
            out.append(f'auto_event_to_request_seconds_bucket{{worker="{w}",le="+Inf"}} {lat["count"]}')
            out.append(f'auto_event_to_request_seconds_sum{{worker="{w}"}} {round(lat["sum"], 3)}')
            out.append(f'auto_event_to_request_seconds_count{{worker="{w}"}} {lat["count"]}')
        out.append("# TYPE auto_fired_late_total counter")
        out += [f'auto_fired_late_total{{worker="{w}"}} {hb.extra["late"]}' for w, hb in sorted(hbs.items()) if "late" in hb.extra]
        out.append("# TYPE auto_firings_suppressed_total counter")     # refused by a scenario's own ceiling
        out += [f'auto_firings_suppressed_total{{worker="{w}"}} {hb.extra["suppressed"]}' for w, hb in sorted(hbs.items()) if "suppressed" in hb.extra]
        return out
    return lines


def rec_routes(rec_ctl: SpecController):
    # Who set a keep, lifted it, shrank a volume or withdrew one — into the journal (`w2cplatform/journal.py`).
    def said(kind: str, handler, **fields) -> None:
        journal = getattr(extra, "journal", None)
        if journal is not None:
            journal.say(kind, user=(getattr(handler, "headers", None) or {}).get("X-User", "operator"), **fields)

    def extra(handler, method, path, q):
        # What somebody said to keep (`vms/keeps.py`): a list, a POST, a DELETE. The row is all there is — the
        # recorder holding an incidents volume copies what it names on its own pass, and the resource leaves the
        # events it names in place.
        if method == "GET" and path in ("/keeps", "/keeps/"):
            # The list is what THIS caller may see (feedback CG): a keep says which camera, which minutes and why,
            # and lifting or checking one already asked by its camera — the list did not. A camera of another
            # cluster (`ref:…`) has no labels here, as at every gate.
            sees = getattr(handler, "sees", None)
            shown = keeps.declared(rec_ctl.vars)
            if sees is not None:
                shown = [k for k in shown if sees(str(k.cam), handler.labels_for(k.cam))]
            return 200, {"keeps": [k.shown() for k in shown]}
        if method == "POST" and path in ("/keeps", "/keeps/"):
            body = json.loads(handler.rfile.read(int(handler.headers.get("Content-Length", 0))) or b"{}")
            try:
                keeps.refuse(body)
                # The recordings of the camera as they are NOW, and the camera's own name: a recording
                # deleted before today left a tree called after the camera, and nothing else says whose it is.
                names = set(recordings_of(rec_ctl, body["cam"])) | {str(body["cam"])}
                k = keeps.write(rec_ctl.vars, body, sorted(names), handler.headers.get("X-User", "operator"), rec_ctl.wall())
            except Refused as e:
                return 400, {"detail": str(e), "error": "refused"}
            said("archive.keep.made", handler, keep=k.id, cam=k.cam, **{"from": k.since, "to": k.until})
            # The mark is valid without a place to copy into — so 201 — but then it is ONLY a mark (the review's
            # second pass, B10): no recorder's `keep_pass` copies anything, and the footage goes with its ring. Said
            # in the answer, and counted on `/metrics` (`rec_keeps_unprotected`) for as long as it is so.
            if not volumes.incidents(rec_ctl.vars):
                return 201, {"keep": k.shown(), "warning": "no incidents volume: the keep is a mark, nothing is copied "
                                                           "until one is declared"}
            return 201, {"keep": k.shown()}
        if method == "DELETE" and path.startswith("/keeps/"):
            id_ = path_id(path)
            if not any(k.id == id_ for k in keeps.declared(rec_ctl.vars)):
                return 404, {"detail": f"no keep {id_}", "error": "no such keep"}
            keeps.delete(rec_ctl.vars, id_)
            said("archive.keep.lifted", handler, keep=id_)
            return 200, {"deleted": id_, "detail": "the events are under their own retention again, from the resource's "
                                                   "next pass; the copy in the incidents volume stays until its ring "
                                                   "overwrites it"}
        if not path.startswith("/volumes"):
            return None
        if method == "GET" and path in ("/volumes", "/volumes/"):
            now = rec_ctl.wall()
            view = volumes.served(rec_ctl.vars, rec_ctl.spec.sub, now, objects=rec_ctl.objects)
            spare = spare_workers(rec_ctl)
            return 200, {**view, "spare": len(spare), "spares": sorted(spare),
                         # `live` so that whatever acts on `needed` does not have to ask the orchestrator
                         # how many recorders are running — the console already knows, from heartbeats,
                         # and one source for the pair means the two numbers cannot disagree.
                         "live": len(rec_ctl.workers_seen()),
                         **scale_hint(rec_ctl, view["wanted"] - view["serving"], len(spare)),
                         # …and what to offer somebody who has declared nothing yet: the disk each box
                         # already records into, sized to its partition. A proposal, not a row.
                         "suggested": volumes.suggest(rec_ctl.vars, rec_ctl.objects, rec_ctl.spec.sub, now)}
        if method == "POST" and path in ("/volumes", "/volumes/"):
            body = json.loads(handler.rfile.read(int(handler.headers.get("Content-Length", 0))) or b"{}")
            was = next((v for v in volumes.declared(rec_ctl.vars) if v.name == str(body.get("name", ""))), None)
            try:
                vol = volumes.write(rec_ctl.vars, body, sealer=rec_ctl.sealer)
            except Refused as e:
                return 400, {"detail": str(e), "error": "refused"}
            if was is not None and 0 < vol.quota_bytes < was.quota_bytes:     # "give this archive less": the ring shrinks, its oldest minutes go
                said("archive.volume.shrunk", handler, volume=vol.name, quota_bytes=vol.quota_bytes, was=was.quota_bytes)
            return 201, {"volume": {k: v for k, v in {**vol.to_items(), "name": vol.name}.items()
                                    if not k.endswith("_secret")}}
        if method == "DELETE" and path.startswith("/volumes/"):
            name = path_id(path)
            if not any(v.name == name for v in volumes.declared(rec_ctl.vars)):
                return 404, {"detail": f"no volume {name}", "error": "no such volume"}
            # The row goes; the recorder holding it finds out on its next pass, stops what it was writing
            # there and takes something else. The FOOTAGE is not touched — deleting the declaration is not
            # deleting the archive, and the two must not be one button.
            volumes.delete(rec_ctl.vars, name)
            said("archive.volume.withdrawn", handler, volume=name)
            return 200, {"deleted": name, "detail": "the recorder stops writing there on its next pass; "
                                                    "the footage already written is untouched"}
        return None
    return extra


# What the `auto` mount adds: the catalogue a scenario form is built from (М10B Lesson 25). One answer with
# both halves — what automation may ask for, and what each unit raises and can do, as its holder described
# it — so the page offers the kinds camera 12 actually raises and the presets camera 7 actually has, and an
# operator picks rather than types. The check at the door stays: a form is a convenience, `curl` is not.
def auto_routes(auto_ctl):
    def extra(handler, method, path, q):
        if method == "GET" and path in ("/catalog", "/catalog/") and getattr(auto_ctl, "catalog", None) is not None:
            return 200, auto_ctl.catalog.reply()
        return None
    return extra


def make_console(ctl: VmsController, archive_root: str | None, wall=None, live_ctl: SpecController | None = None,
                 mounts: dict[str, SpecController] | None = None, index=None, media: bool | None = None) -> Mount:
    """One console process for the box: the VMS at `/` (the page, /cameras, the media routes, the WHEP door),
    and every other subsystem the console fronts under its name — `/live/…`, `/det/…` — each a SpecConsole over
    that subsystem's spec with the console's token. `live_ctl` opens the WHEP door and is mounted at /live;
    `mounts` adds the rest by name."""
    live = LiveFront(ctl, live_ctl) if live_ctl is not None else None
    index = index or MergedIndex(ctl.objects, wall=wall or time.time)   # no database here: the resource process's, asked over HTTP
    rec_ctl = (mounts or {}).get("rec")                                  # the console fronts it anyway: the page's Record toggle
    media = archive_root is not None if media is None else media         # footage to show: the recorders' doors
    root = SpecConsole(ctl, marks_root=archive_root, wall=wall,
                       extra=vms_routes(media, live, ctl, rec_ctl), media=media, index=index,
                       metrics_extra=vms_metrics(ctl))
    root.extra.journal = root.journal    # where `archive.read` goes: the journal, `audit/console/…`
    root.extra.seen = root.seen          # where a command's Idempotency-Key is kept past its row (`POST /requests`)
    # What the VMS's routes need at the gate (`w2cplatform/access.py`): a backfill ACTS; a timeline and a live
    # stream name a camera; asking for a live stream is a POST that changes nothing — `view` on that camera,
    # which is the viewer's token on the live door.
    root.EDIT_ROUTES = SpecConsole.EDIT_ROUTES + ("/backfill",)
    root.UNIT_ROUTES = SpecConsole.UNIT_ROUTES + ("timeline", "export", "whep")
    root.NO_UNIT = ("/whep/session/",)                                   # a live session is not a camera: its route checks it
    root.VIEW_POSTS = ("/whep/",)
    m = Mount(root)
    if live_ctl is not None:
        m.mount("live", SpecConsole(live_ctl, wall=wall, index=index))
    for name, c in (mounts or {}).items():
        con = SpecConsole(c, wall=wall, index=index,                     # every mount answers /events from the same merge
                          extra=(rec_routes(c) if name == "rec" else          # …and `rec` answers for the archives too,
                                 auto_routes(c) if name == "auto" else None),  # `auto` for its catalogue
                          metrics_extra=(rec_metrics(c) if name == "rec" else
                                         auto_metrics(c) if name == "auto" else None))
        # ONE journal for the process: a mount has no resource root of its own, and "who deleted recording 7"
        # belongs beside "who deleted camera 7".
        con.journal = root.journal
        if name == "rec":
            con.EDIT_ROUTES = SpecConsole.EDIT_ROUTES + ("/keeps",)   # a keep is set by an operator; a volume by an administrator
            con.ID_ROUTES = ("keeps", "volumes")                       # one id each, and nothing after it
        if name in ("rec", "live", "det"):
            # A recording, a stream, a detector are ABOUT a camera, and a grant on labels is a grant on the
            # CAMERA's labels: read from the camera's row, not from the recording's own (which say where it runs).
            con.labels_of = lambda cam: (ctl.camera(cam) or {}).get("labels") or []
        if con.extra is not None:
            con.extra.journal = root.journal
        m.mount(name, con)
    return m


# `make_console(...).serve(host, port)`: the server in a daemon thread, returned so the caller can
# `shutdown()` it. `__main__.console` calls it with `$CONSOLE_HOST:$CONSOLE_PORT`; the tests with `port=0`.
def serve(ctl: VmsController, archive_root: str | None, host: str = "127.0.0.1", port: int = 8080, wall=None,
          live_ctl: SpecController | None = None, mounts: dict[str, SpecController] | None = None, index=None) -> ThreadingHTTPServer:
    return make_console(ctl, archive_root, wall, live_ctl, mounts, index).serve(host, port)
