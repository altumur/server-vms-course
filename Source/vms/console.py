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

import hashlib
import http.client
import json
import logging
import math
import struct
import threading
import time
import urllib.error
import urllib.request

from w2cplatform.access import token_of
from w2cplatform.console import (PAGE, ClaimLost, Mount, SpecConsole, framed, heard_live, heartbeats, holder_of, holders, label, no_paths,  # noqa: F401
                                 object_body, path_id, send_file)   # (PAGE, send_file re-exported for М11)
from w2cplatform.contract import HEARTBEATS, slot_number
from w2cplatform.rows import FIELDS, PARSE_ERRORS, finite, number
from w2cplatform.eventdatabase import MergedIndex
from w2cplatform.spec import Refused, SpecController
from w2cplatform.variables import Conflict

from . import keeps, volumes
from .config import cam_ref, camera_of_ref

log = logging.getLogger("vms.console")
READ_NOTE_EVERY = 60.0        # the same piece of archive, by the same person: one `archive.read` a minute
READ_NOTE_BYTES = 1 << 20     # …while what left of it is less than this: a larger part is a line every time
from .archive import subtract
from .controller import VmsController
from .jobs import BACKFILL_TTL

EXPORT_MAX = 3600.0           # the longest interval one export answers: the page asks for minutes, a person for an hour
SEGMENT_MAX = 3600.0          # …and one signed piece of a DEVICE's footage (`GET /segment`), after it is cut to the coverage
BACKFILL_MAX = 86400.0        # the longest range one `POST /backfill` asks for: a hole somebody saw, a day at most
BACKFILL_MIN = 1.0            # …and the shortest: the recorder fetches whole seconds, and less is an ask nobody can answer
BACKFILL_AHEAD = 60.0         # …and how far past this console's clock it may end: two clocks apart, not minutes to come
BACKFILLS_OPEN = 7            # …and how many of one person's asks may wait for a recorder at once: a week of days
ASK_SETTLE = 60.0             # an ask counts for this long after it was made, its row there or not (`POST /backfill`)
KEEP_MAX = 7 * 86400.0        # the longest interval one keep holds: an incident's week, not "the archive"
EXPORTS_AT_ONCE = 2           # exports one console makes at a time (`EXPORTS_AT_ONCE` in its environment): each is held in memory
EXPORT_RETRY = 5.0            # the `Retry-After` of an export refused for that
EXPORTS_PER_USER = 1          # of those, how many one caller makes at once (`EXPORTS_PER_USER`): one person cannot take them all
EXPORT_MIN_RATE = 64 << 10    # bytes a second an export's client must take on average (`EXPORT_MIN_RATE`): slower, it is cut
EXPORT_GRACE = 60.0           # …counted after this many seconds of it (`EXPORT_GRACE`): a door's first answers, a slow start
EXPORT_PIECE = 60.0           # an export reads a stretch this much at a time: what one recording holds in memory
DOOR_TIMEOUT = 5.0            # a recorder's door that does not answer in this is named, not waited for
SESSIONS_KEPT = 10000         # live sessions remembered for their hang-up: past it, the oldest is forgotten
SESSION_LOOKBACK = 86400.0    # …and how far back the journal is asked for one this process does not remember
SESSION_MISS_TTL = 60.0       # an id the journal did not know is not asked about again for this long
SESSION_MISSES = 10           # look-ups that ask the journal, one caller, a minute — whatever they find: past them, 429 without asking


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
        row = self.live.unit(cam)
        if row is not None and labels and not set(labels) <= set(row.get("labels") or []):
            # THE LABELS ARE THE STREAM'S, AND THE FIRST VIEWER SET THEM (the review's second pass, Н-M8; unchanged in the
            # third). There is one fan-out per camera, placed by its row's labels, and a second viewer's `?labels=` was
            # dropped without a word: the guard who asked for the stream with the public address got the one on the
            # private gateway the first viewer had wanted. Asked for labels the row does not carry, the answer is 409,
            # naming the row's: the stream that exists is served from a gateway covering those, and a viewer who needs
            # another one says so to whoever may change the row — a second fan-out of one camera is a second session
            # on the device, which is the device's to give (М10B Lesson 13), not a viewer's to take.
            have = sorted(row.get("labels") or [])
            return 409, {"error": f"the stream of camera {cam} is served by labels {','.join(have) or '(none)'}, not "
                                  f"{','.join(sorted(labels))}",
                         "detail": "one fan-out per camera, placed by its row's labels: ask without `labels` (or with a "
                                   "subset of the row's) to watch it, or change the row `live/streams/" + str(cam) + "`",
                         "labels": have}
        if row is None:
            # The viewer chooses where the stream is served from (`?labels=`: Lesson 13, a stream for the gateway
            # with a public address) — from among the places that EXIST. A label no live gateway carries made a
            # row nothing could place, and every next viewer of the camera was told "retry" for ever (the review's
            # second pass, major). Refused by name, and no row.
            #
            # …by ONE gateway (the review's third pass, Н-M8 and its minor): placement puts a stream on a gateway whose
            # labels cover ALL of the stream's, and the check took the union over every gateway — `public` on g-1 and
            # `eu` on g-2 passed for `public,eu`, and the row was one nothing could place, as before.
            # …and what a gateway carries is what PLACEMENT reads (feedback DQ): its server's row from the console when
            # there is one (`live/servers/<server>`), its heartbeat's otherwise — `labels_of`, not the heartbeat alone.
            with self.live.one_pass():                   # each gateway asked: the heartbeats and the rows read once
                sets = [set(self.live.labels_of(w)) for w in holders(self.live.objects, "live/", self.ctl.wall(),
                                                                     eyes=self.live.eyes)]   # fresh by change (13th)
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
        except PARSE_ERRORS:                             # an answer nobody can read (the ninth pass's sweep of `door_timeline`)
            return 502, {"error": f"gateway {g} answered something that is not JSON"}

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
# - `GET /segment?unit=vms/<id>` — the DEVICE's own footage, through its holder's playback door (`segment`).


# What the DEVICE has and we do not — drawn only where our own footage does not cover it. The same
# subtraction the recorder fetches by (Lesson 16): one rule, two uses, so the picture and the work cannot
# disagree. A span like this is the one that will disappear — our archive keeps thirty days, a card keeps
# three — which is why the page offers to pin it.
#
# THE COVERAGE A HOLDER ANNOUNCES IS READ ONCE, HERE (the review's tenth round): `float(cov["from"])` bare in three routes,
# and one holder's word where a number goes was the camera's whole `/timeline` (no reply), its `/segment` and a
# backfill's floor. `(from, to)`, or None — not said, or said in a form that does not read: counted once as that
# holder's field (`rows.FIELDS`), and the routes go on as for a holder that announces nothing.
# What a frame that will not become MP4 raises (`export`): a word of the codec, a size past a `>I`/`>H` field
# (`struct.error`), an empty unit (`IndexError`) — the frame's trouble: before the first byte a 415, after it a cut
# file said `broken`. It was `ValueError` alone, and `struct.error` went past the journal's line (the tenth round).
FRAME_ERRORS = (ValueError, struct.error, IndexError, OverflowError)


def coverage_of(found) -> tuple[float, float] | None:
    if found is None:
        return None
    cov = found[2].get("coverage")
    if not cov:
        return None
    key = f"vms/{HEARTBEATS}/{found[0]}#coverage"
    try:
        return finite(cov["from"]), finite(cov["to"])
    except PARSE_ERRORS as e:
        FIELDS.garbled(key, e)
        return None


def device_spans(objects, cam, ours: list[dict], t0: float, t1: float, now: float, eyes=None) -> list[dict]:
    cov = coverage_of(holder_of(objects, "vms/", cam, now, field="coverage", eyes=eyes))
    if cov is None:
        return []
    want = (max(cov[0], t0), min(cov[1], t1))
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
    return units or ([str(cam)] if own_name_is_hers(rec_ctl, cam) else [])   # nothing declared: the camera's own name, so old footage still shows


# Whether the tree named after the camera may be read as the camera's — the fallback above, and a keep's names.
# Only when no recording of that NAME says it is another camera's, alive or deleted (a tombstone keeps its `cam`):
# a recording called «1» that records camera 2 made `/timeline/1` and `/export/1` serve camera 2's frames to camera
# 1's viewers, journalled as camera 1, and `POST /backfill` for camera 1 wrote into camera 2's tree (the review's
# fourth pass, major). A store that does not answer is not "nobody's": the name is not taken.
def own_name_is_hers(rec_ctl, cam) -> bool:
    try:
        items, _ = rec_ctl.vars.get(rec_ctl.row_key(rec_ctl.spec.parse_id(str(cam))))
    except (OSError, *PARSE_ERRORS):                 # a row nested past JSON's depth too (the tenth round)
        return False
    return not items or str(items.get("cam", cam)) == str(cam)


# Every recorder that serves its archive, live: `[(name, url, heartbeat)]`. A recorder holds ONE volume and its
# door answers for it — a camera recorded into two volumes, or one whose recording moved, is answered by two.
#
# LIVE BY WHAT THE READER SAW CHANGE (the product's r29-writers2): `now - hb.ts` here, in `unserved_volumes`, the keeps'
# numbers, a volume's size and its waiting recorders — the recorder's clock against the reader's, with no bound ahead:
# a recorder dead an hour whose clock ran an hour ahead stayed a door, and one 100 s behind was a volume "unserved".
# `eyes` — the asker's long-lived `Eyes` — say whether the heartbeat changed within `lost_after` of the asker's clock
# (`heard_live`); without them, `is_live` (bounded both ways).
def recorder_doors(objects, now: float, lost_after: float = 45.0, eyes=None) -> list:
    out = []
    for name, hb in sorted(heartbeats(objects, "rec/").items()):
        url = str(hb.extra.get("archive_url") or "")
        if url and heard_live("rec", name, hb, now, lost_after, eyes):
            out.append((name, url.rstrip("/"), hb))
    return out


# The volumes nobody serves right now: a recorder went silent holding one, and no live recorder holds it since —
# the server is down, its disk with it, or a network archive is waiting for a spare. Its footage is not LOST: it is
# in that volume, and it is unavailable until a recorder holds the volume again. `[{volume, server, since}]`, from
# the recorders' last heartbeats; the timeline names them instead of drawing a hole where they are (М11 lesson 6).
def unserved_volumes(objects, now: float, lost_after: float = 45.0, eyes=None) -> list[dict]:
    live, stale = set(), {}
    for name, hb in heartbeats(objects, "rec/").items():
        vol = str(hb.extra.get("volume") or "")
        if not vol:
            continue                               # a spare holds nothing
        if heard_live("rec", name, hb, now, lost_after, eyes):
            live.add(vol)
        elif vol not in stale or hb.ts > stale[vol]["since"]:
            stale[vol] = {"volume": vol, "server": str(hb.extra.get("server", "")), "recorder": name, "since": hb.ts}
    return [v for k, v in sorted(stale.items()) if k not in live]


# A row that does not PARSE is not the timeline's end either (the review's sixth pass, minor): one torn
# `rec/epoch/<recording>` was a `ValueError` out of the handler, and the page got no timeline of the camera at all —
# every other recording of it with that one. Read as `SpecConsole.epochs_of` reads it: the doors' own word stands
# for that recording, and the row is named in the log.
def _rec_epoch(ctl, unit) -> int | None:
    from w2cplatform.epoch import current_epoch
    try:
        return current_epoch(ctl.vars, f"rec/epoch/{unit}") or None
    except OSError:
        return None                                # the store did not answer: the doors' own word stands
    except PARSE_ERRORS as e:                         # `epoch: Infinity` too (the tenth round)
        log.warning("rec/epoch/%s does not parse (%s): its spans are fenced by their doors' word alone", unit, e)
        return None


# A door's answer, whole — or an `OSError`. A recorder's door streams its frames in chunks and writes the last one only
# when the stream was whole (`recworker.send_route`): an answer that ends without it is `http.client.IncompleteRead`,
# which is not an `OSError` and would have gone past every `except` here as a door that answered.
#
# …AND AN ANSWER WITH NO FRAMING IS NOT TAKEN FOR A WHOLE ONE (the review's seventh pass, minor). Chunks or a length
# are what let a short answer be told from a whole one; an answer with neither — a door that spoke HTTP/1.0, or a
# proxy that took the framing off — ends where the connection ends, and a door that failed half way looked exactly
# like a door that had nothing more. Such an answer is refused here, as a cut one is: the export says the door did not
# answer, it does not write a shorter film.
#
# …AND READ UP TO A BOUND WHEN IT IS A LIST (the review's eighth pass, part 4, left to this group): a door's `/timeline`
# was read whole whatever its size, and each span parsed bare — `int(sp["epoch"])` of a door of another build or a proxy
# raised out of the camera's timeline and its export. `limit`: at most so many bytes (`rows.answer`, a `ValueError`
# past it — the door did not answer); the spans are read by `door_spans` below.
def _door(url: str, timeout: float, limit: int | None = None):
    from w2cplatform.rows import answer
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            if not framed(r):                            # …and a length that is a number (the eighth pass): `framed`
                raise ConnectionError(f"{url}: the door's answer has neither chunks nor a length — whether it is whole "
                                      f"cannot be told")
            return r.read() if limit is None else answer(r, limit)
    except http.client.HTTPException as e:
        raise ConnectionError(f"{url}: the door's answer was cut short ({e!r})") from None


# A recorder door's timeline of one recording, each span read alone (`scan.door_spans`): `(spans, whole)`, or an
# `OSError`/`ValueError` — the door did not answer. A span that does not parse costs that span, and `whole` is False:
# the reader names the door, it does not take the rest for all the door holds.
#
# …and an answer that does not parse is a door that did not answer, whatever the parser raised (`PARSE_ERRORS`; the
# review's ninth pass, a run): a door's 200 KB of nested brackets was a `RecursionError`, which no caller catches —
# the timeline and the export were 500 instead of naming the door.
def door_timeline(name: str, url: str, unit, t0: float, t1: float) -> tuple[list[dict], bool]:
    from w2cplatform.rows import ANSWER_MAX
    from .scan import door_spans
    raw = _door(f"{url}/timeline/{unit}?from={t0}&to={t1}", DOOR_TIMEOUT, ANSWER_MAX)
    try:
        return door_spans(f"rec/doors/{name}#{unit}", json.loads(raw))
    except PARSE_ERRORS as e:
        raise ValueError(f"{url}: the door's timeline does not parse ({type(e).__name__})") from None


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
    # A part — a player that moved on before the piece ended, the connection closed under it — once a minute per
    # (who, piece): a page scrubbing through a span makes dozens. A WHOLE file always (the review's fourth pass,
    # minor): the same interval exported twice in a minute was one line, and the second file need not be the first
    # — a door that answered this time, a block that closed meanwhile — so its digest is the one somebody will hold.
    #
    # …and a BROKEN download as well, once it carried footage worth the name (the review's fifth pass, Ч-m5's
    # remainder): two downloads of an interval, each cut off after 3.6 MB, were one line — the second copy of most of
    # those minutes left without a word. A part is folded into the minute's line only while it is a player's scrub,
    # under `READ_NOTE_BYTES`; past it, every one is a line of its own.
    def note_read(handler, rel: str, sent: dict) -> None:
        import hashlib
        user = handler.headers.get("X-User", "operator")
        addr = (getattr(handler, "client_address", None) or ("",))[0]
        now, whole = con_wall(), bool(sent.get("whole"))
        each = whole or int(sent.get("bytes", 0) or 0) >= READ_NOTE_BYTES
        with reads_lock:
            if not each and now - seen_reads.get((user, rel), -1e18) < READ_NOTE_EVERY:
                return
            if len(seen_reads) > 10000:
                for k in [k for k, t in seen_reads.items() if now - t >= READ_NOTE_EVERY]:
                    del seen_reads[k]
            if not each:
                seen_reads[(user, rel)] = now
        parts = rel.split("/")
        digest = sent.get("sha256") or (hashlib.sha256(sent["data"]).hexdigest() if whole and "data" in sent else None)
        log.info("archive read: %s got %s (%s, %d bytes) from %s", user, rel, sent.get("status"), sent.get("bytes", 0), addr)
        journal = getattr(extra, "journal", None)         # the console's journal (`w2cplatform/journal.py`), set by `make_console`
        if journal is not None:
            journal.say("archive.read", user=user, media=rel, addr=addr, status=sent.get("status"), bytes=sent.get("bytes", 0),
                        **({"sha256": digest} if digest else {}), **({"recording": parts[1]} if len(parts) > 1 else {}),
                        **({"unreachable": sent["unreachable"]} if sent.get("unreachable") else {}),
                        **({"broken": sent["broken"]} if sent.get("broken") else {}))

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
                try:
                    sdp = handler.rfile.read(int(handler.headers.get("Content-Length", 0))).decode()
                except UnicodeDecodeError:                # an offer that is no text: the sender's 400, not a dropped connection
                    return 400, {"detail": "an offer is an SDP, as text (UTF-8)", "error": "bad offer"}
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
                try:
                    held = session_of(sid, who)
                except LookupError as e:                         # the journal was not asked: not "no such session"
                    return 429, json.dumps({"error": "too many look-ups", "detail": f"{e}; retry in a minute"}).encode(), \
                        [("Content-Type", "application/json"), ("Retry-After", "60")]
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
        # (A command to a device, `POST /requests`, and a backfill a person asks for, `POST /backfill`, were routes of the
        # VMS's here: they are the specs' `requests:` since the boundary's step 6, served by the platform's console.)
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

    # `(who, camera, gateway)` of a live session this console — or ANOTHER console — handed out, or None.
    #
    # The table above is one process's memory: a hang-up through another replica of the console, or after a restart,
    # found nothing and was 404, and the session lived on until the gateway's sweep (the review's fourth pass, minor).
    # What every console already writes for every session it hands out is `live.view` — who, which camera, the
    # session, the gateway — durably, into the journal the event index merges across every server. So a session this
    # process does not remember is looked up there: the last `SESSION_LOOKBACK` of `live.view` lines. Not a row in the
    # store: the console's token writes the operator's rows, and a session per viewer is not one; not the gateway: it
    # holds the session, and not who opened it. A session older than the look-back, or written while the journal could
    # not be, is 404 as before — and its viewer's tab closing is the gateway's grace.
    #
    # WHAT A LOOK-UP COSTS, AND WHO PAYS (the review's fifth pass, minor). Any id asked the journals of every server for
    # a day, and past `MAX_LIMIT` views a day an old session was 404. Three things now. The day is read a window at a
    # time, newest first, until the session is found or the day is done — not one window cut at the limit. An id that
    # was not found is remembered as not found for `SESSION_MISS_TTL` (the same wrong id again asks nobody). And each
    # caller has `SESSION_MISSES` look-ups that find nothing a minute (`who`); past them their next unknown id is 404
    # without asking. What would make one look-up cheap — the index answering by `session` itself — is the index's
    # to grow: today it filters by kind and subsystem, and the rest is read here.
    #
    # EVERY LOOK-UP IS COUNTED, AND WHAT IT FOUND IS KEPT (the review's sixth pass, minor; reproduced by a run: thirty
    # DELETEs of somebody ELSE's old session were six hundred windows read). Only look-ups that found nothing were
    # remembered and counted — and a session that IS in the journal and is not the caller's was found, refused with
    # 403, and found again on the next request, the whole day read each time, with no bound. A session found is put
    # into the table above, where the next request finds it without the journal; and the caller's budget
    # (`SESSION_MISSES` a minute) is spent by every look-up that asks the journal, whatever it finds, before it asks.
    # Past the budget the answer is `LookupError` — the route says 429, not "no such session": it did not look.
    misses: dict[str, float] = {}
    asked_by: dict[str, list] = {}

    def session_of(sid: str, who: str | None = None):
        with sessions_lock:
            held = sessions.get(sid)
        if held is not None:
            return held
        index = getattr(extra, "index", None)
        if index is None or not sid:
            return None
        from w2cplatform.doors import MAX_LIMIT
        mono = time.monotonic()
        with sessions_lock:
            if mono - misses.get(sid, -1e18) < SESSION_MISS_TTL:
                return None
            mine = asked_by[who] = [t for t in asked_by.get(who, []) if mono - t < 60.0]
            if who is not None and len(mine) >= SESSION_MISSES:
                raise LookupError(f"{who} has asked the journal about {len(mine)} sessions this minute")
            mine.append(mono)                                        # counted before it asks, whatever it finds
            if len(asked_by) > SESSIONS_KEPT:
                asked_by.clear()
        now = con_wall()
        lo, hi = now - SESSION_LOOKBACK, now + 1
        try:
            while hi > lo:
                rep = index.query(lo, hi, kind="live.view", subsystem="audit", limit=MAX_LIMIT, keep="newest")
                events = rep.get("events", [])
                for e in events:
                    if str(e.get("session")) == sid:
                        held = str(e.get("user", "")), str(e.get("target", "")), str(e.get("gateway", ""))
                        with sessions_lock:
                            sessions[sid] = held                     # found once: not looked for again
                            while len(sessions) > SESSIONS_KEPT:
                                sessions.pop(next(iter(sessions)))
                        return held
                if not rep.get("truncated") or not events:
                    break
                older = min(float(e["t"]) for e in events)           # the older end of the day, the next window
                if older >= hi:
                    break
                hi = older
        except Exception as e:                                       # noqa: BLE001 — the journal is away: not found, said
            log.warning("a hang-up of %s could not ask the journal who opened it: %s", sid, e)
            return None
        with sessions_lock:
            misses[sid] = mono
            if len(misses) > SESSIONS_KEPT:
                for k in [k for k, t in misses.items() if mono - t >= SESSION_MISS_TTL] or list(misses)[:len(misses) // 2]:
                    misses.pop(k, None)
        return None

    # The command, as a row: `(202, {queued, detail})`, or the refusal.
    # `GET /segment?unit=vms/<id>` — the device's own footage, through its holder's playback door: the URL, and a line.
    # The camera is named as the platform names a unit (the boundary's step 2): that is what the gate asked about.
    def segment(handler, q: dict):
        from . import playback as pb
        cam, raw0, raw1 = camera_of_ref(q.get("unit")) or "", q.get("from", 0), q.get("to", 1e12)
        try:
            t0, t1 = pb.times(raw0, raw1)
        except (TypeError, ValueError):
            return 400, {"detail": "from and to are unix seconds, and to is after from", "error": "bad range"}
        # The holder, resolved NOW — never written into a span when it was drawn: a camera that moved between the
        # drawing and the click would make a stored worker name a 404; one heartbeat read cannot go stale.
        found = holder_of(ctl.objects, "vms/", cam, con_wall(), field="playback_url", eyes=ctl.eyes)   # by change (13th)
        if found is None:
            return 503, {"detail": "nobody holds this camera right now", "error": "unheld"}
        url, key = found[2]["playback_url"], found[1].extra.get("playback_key") or None
        # WHAT IS SIGNED IS WHAT THE DEVICE HAS, AND NO MORE THAN AN EXPORT (the review's fifth pass, major). Any
        # interval was signed — a day of a card, `0..1e12` — and the door read it whole into one buffer in the
        # holder, the process holding every camera of its server: a viewer with `view` on one camera could take it
        # down. The interval is cut to the coverage the holder announces (`coverage`, the summary in its heartbeat)
        # and then held to `SEGMENT_MAX`, as an export is to `EXPORT_MAX`: a longer one is 400, before anything is
        # signed. A holder that announces no coverage (an older build) is held to the ceiling alone.
        cov = coverage_of(found)                          # a word in it: held to the ceiling alone, as an older build
        lo, hi = float(t0), float(t1)
        if cov is not None:
            lo, hi = max(lo, cov[0]), min(hi, cov[1])
            if hi <= lo:
                return 404, {"detail": f"the device holds nothing of camera {cam} in that interval (it holds "
                                       f"{cov[0]:.0f}..{cov[1]:.0f})", "error": "nothing there"}
        if hi - lo > SEGMENT_MAX:
            return 400, {"detail": f"a piece of the device's footage is at most {SEGMENT_MAX:.0f} s; this one is "
                                   f"{hi - lo:.0f} s of what the device holds — ask for less", "error": "range too long"}
        if (lo, hi) != (float(t0), float(t1)):
            (t0, t1), raw0, raw1 = pb.times(lo, hi), lo, hi
        who = handler.headers.get("X-User", "operator")
        # The door to the DEVICE's footage is handed out here, and the footage then goes holder → browser:
        # this console never sees the bytes, so what it can say is that it gave the door, to whom, for which
        # minutes (the review's third pass, Н-B1's remainder: it went with no line at all). One line per URL
        # handed out — a page asks once per click, not once per byte range.
        #
        # …and the address is SIGNED (the review's fourth pass, blocker 4): this camera, these minutes, this viewer,
        # for `playback.TTL` seconds, with the door's own key from its heartbeat. The door checks it: the camera
        # edited, the minutes stretched or the address kept for tomorrow are 403 there. A holder that announced no
        # key is an older build, whose door asks nobody: its bare address, as before.
        journal = getattr(extra, "journal", None)
        until = con_wall() + pb.TTL
        if journal is not None:
            journal.say("archive.read", user=who, source="device", target=cam,
                        addr=(getattr(handler, "client_address", None) or ("",))[0],
                        **{"from": raw0, "to": raw1}, **({"until": round(until)} if key else {}))
        if key is None:
            return 200, {"playback": f"{url}?from={raw0}&to={raw1}"}
        return 200, {"playback": f"{url}?{pb.signed_query(key, cam, t0, t1, who, con_wall())}", "until": round(until)}

    # A camera's timeline: every recording of it, from every recorder's door — each holds one volume, and what a
    # recording wrote over its life may be in more than one. A door that does not answer is NAMED, not waited
    # for: a timeline with a hole the page explains beats one that never comes. So is a volume nobody serves now
    # (`unserved_volumes`): unavailable, not lost. Each span says whose it is and how to play it (`media`: the
    # export of that recording; the page adds the minutes).
    def timeline(cid: str, q: dict):
        try:                                             # a word, `nan`: 400 — it was no reply at all (the tenth round)
            t0, t1 = finite(q.get("from", 0)), finite(q.get("to", 1e12))
        except ValueError:
            return 400, {"detail": "from and to are unix seconds", "error": "bad range"}
        ours, unreachable = [], []
        doors = recorder_doors(ctl.objects, con_wall(), eyes=(rec_ctl or ctl).eyes) if ctl is not None else []
        for unit in recordings_of(rec_ctl, cid):
            # Fenced against the RECORDING's epoch, which the store holds — a door knows only its own recorder's,
            # and the zombie's stream may be in another volume than the survivor's. A copy (`e0`, a keep's) is
            # nobody's writer and is never fenced.
            cur = _rec_epoch(ctl, unit)
            for name, url, hb in doors:
                try:
                    got, said_whole = door_timeline(name, url, unit, t0, min(t1, 1e11))
                except (OSError, ValueError):
                    unreachable.append(name)
                    continue
                if not said_whole:
                    unreachable.append(name)             # spans it said that do not parse: its picture is not whole
                for sp in got:
                    fenced = bool(sp.get("fenced")) or (cur is not None and 0 < sp["epoch"] < cur)
                    ours.append({**sp, "fenced": fenced, "recording": unit, "recorder": name,
                                 "volume": hb.extra.get("volume", ""), "media": f"/export/{cid}?rec={unit}"})
        extra_ = device_spans(ctl.objects, cid, ours, t0, t1, con_wall(), ctl.eyes) if ctl is not None else []
        spans = sorted(ours + extra_, key=lambda d: (d["start"], d["epoch"]))
        gone = unserved_volumes(ctl.objects, con_wall(), eyes=(rec_ctl or ctl).eyes) if ctl is not None else []
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

    # An interval as a fragmented MP4, written as it is made (`fmp4.Writer`): the frames from every door that holds them, each
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
    # …AND NOBODY HOLDS THEM ALL, NOR FOR EVER (the review's fourth pass, major). Two sockets that asked for an export
    # and read nothing held both slots until the console restarted: every other export was 503, and `view` on one
    # camera was enough. Three bounds now: the connection's own (`CONSOLE_TIMEOUT` on every socket of the console —
    # a client that reads nothing for that long is let go), the export's (`EXPORT_MIN_RATE`: one that reads a byte
    # just inside each timeout is cut off, and says so), and the person's (`EXPORTS_PER_USER`: one caller cannot
    # take every slot).
    #
    # THE EXPORT'S BOUND IS ITS CLIENT'S PACE, NOT A CLOCK (the review's fifth pass, major). It was a budget: 900 s for
    # an interval of up to 3600 — an hour of an 8 Mbit/s camera is 3.6 GB, so the budget assumed a 32 Mbit/s channel
    # it never named, and an honest operator behind a 10 Mbit/s VPN got the first nineteen minutes of the hour as a
    # `200` and a file that ended, as if that were all. Now an export goes on for as long as its client takes, on
    # average, at least `EXPORT_MIN_RATE` (counted after `EXPORT_GRACE`): that hour takes the VPN some fifty minutes,
    # and arrives whole; a client reading a byte a minute is still cut, in a minute. And a cut is SEEN: to an HTTP/1.1
    # client the file goes in chunks, and the last chunk is written only when the file is whole — a reply that ends
    # without it is an error to curl, to a browser and to `http.client` (`IncompleteRead`), not a shorter film. An
    # HTTP/1.0 client has no such framing: the end of the connection is the end of the file, and only the journal's
    # `broken` tells the two apart.
    per_user: dict[str, int] = {}
    per_user_lock = threading.Lock()

    def busy(why: str):
        return 503, json.dumps({"detail": why, "error": "busy"}).encode(), [("Content-Type", "application/json"),
                                                                            ("Retry-After", str(int(EXPORT_RETRY)))]

    def export(handler, cid: str, q: dict):
        who = (getattr(handler, "headers", None) or {}).get("X-User", "operator")
        mine = max(1, int(os.environ.get("EXPORTS_PER_USER", EXPORTS_PER_USER)))
        with per_user_lock:
            if per_user.get(who, 0) >= mine:
                return busy(f"{who} is making {per_user[who]} export(s) already, as many as one person makes at once — retry")
            per_user[who] = per_user.get(who, 0) + 1
        whole = []                                       # the last chunk, held back until the slots are free again
        try:
            if not exporting.acquire(blocking=False):
                return busy("this console is making as many exports as it makes at once — retry")
            try:
                return _export(handler, cid, q, whole)
            finally:
                exporting.release()
        finally:
            with per_user_lock:
                per_user[who] -= 1
                if not per_user[who]:
                    del per_user[who]
            # The file is whole, its line is in the journal and its slots are given back: only now is the client told
            # it is done — a client that asks for the next export the moment this one ends finds its slot free.
            for b in whole:
                try:
                    handler.wfile.write(b)
                except OSError:
                    pass

    def _export(handler, cid: str, q: dict, whole: list | None = None):
        import hashlib
        import heapq
        import struct
        from . import fmp4
        try:                                             # `nan` passed both checks below as `float` (the tenth round)
            t0, t1 = finite(q.get("from", 0)), finite(q.get("to", 0))
        except ValueError:
            return 400, {"detail": "from and to are unix seconds", "error": "bad range"}
        if t1 <= t0 or t1 - t0 > EXPORT_MAX:
            return 400, {"detail": f"an export is an interval of at most {EXPORT_MAX:.0f} s", "error": "bad range"}
        # Each moment from the EPOCH that owns it, across every door — a door applies `authoritative` to the
        # volume it holds, and a fenced writer's stream may be in another volume than the survivor's. So the doors'
        # timelines are asked first, the rule is run over all of them, and each stretch is read from the door that
        # holds its owner. A door that does not answer is named in the reply's headers: a piece with a hole the
        # caller can see.
        from vms.obsd import Sample, unix_s
        from .archive import Span, authoritative
        # `rec` picks ONE of this camera's recordings — never another camera's: the gate checked `view` on the
        # camera in the path, and a recording named in the query must be hers (the review's second pass, blocker 1).
        units = recordings_of(rec_ctl, cid)
        if q.get("rec"):
            units = [u for u in units if u == str(q["rec"])]
            if not units:
                return 404, {"detail": f"recording {q['rec']} is not a recording of camera {cid}", "error": "not hers"}
        doors = recorder_doors(ctl.objects, con_wall(), eyes=(rec_ctl or ctl).eyes) if ctl is not None else []
        unreachable: list[str] = []

        # THE FRAMES OF A STRETCH, A MINUTE AT A TIME (the review's third pass, major; the door streams since its
        # blocker 6). Every door's answer used to be decoded into one list and the MP4 made of all of it: an hour
        # of an 8 Mbit/s camera, twice over, in the console. A stretch is now read in pieces of `EXPORT_PIECE`,
        # cut at a key frame the way the recorder cuts what it lands (`RecWorker._pieces`): a piece ends where its
        # last group of pictures begins, and the next piece starts there.
        #
        # A DOOR THAT FAILS AFTER THE FIRST BYTE BREAKS THE EXPORT (the review's sixth pass, major; reproduced by a
        # run). It ended its stretch and was named in the journal — and the file went on to its last chunk: an
        # export of 9.85 MB whose door stopped after 1 MB was a `200` of 1.9 MB that every client took for whole,
        # with a sha256 in the journal as a whole file has. A hole that could not be said in the headers is said the
        # only way left: the reply ends WITHOUT its last chunk, and the line is `broken`, with the door's name and no
        # digest. Before the first byte a door that does not answer is still a header (`X-Archive-Unreachable`) and
        # a file that is whole for what it says it is.
        def frames_of(name: str, url: str, unit: str, lo: float, hi: float):
            at = lo
            while at < hi:
                top = min(hi, at + EXPORT_PIECE)
                try:
                    got = sorted(Sample.decode_all(_door(f"{url}/samples/{unit}?from={at}&to={top}", 30.0)),
                                 key=lambda s: s.begin)
                except (OSError, ValueError, struct.error) as e:
                    unreachable.append(name)
                    if sent["head"]:
                        raise ConnectionError(f"the archive door of {name} stopped answering at {at:.0f} of "
                                              f"{unit} ({e}): the file is cut there") from None
                    return
                nxt = top
                if top < hi:
                    cut = next((i for i in range(len(got) - 1, -1, -1) if got[i].key and unix_s(got[i].begin) > at), None)
                    if cut is not None:
                        nxt, got = unix_s(got[cut].begin), got[:cut]
                yield from got
                at = nxt

        # One recording's frames, its stretches in order. A function, so that `unit` and `where` are THIS recording's:
        # the generator expression this was closed over the loop's variables, and was run by the merge after the loop
        # — every recording's stretches were looked up in the LAST recording's `where`, and an export of a camera with
        # two recordings and no `rec` ended in a `KeyError` with no reply and no line (the review's fourth pass, major).
        def stream_of(unit: str, where: dict, stretches: list):
            for span, lo, hi in stretches:
                yield from frames_of(*where[span], unit, lo, hi)

        streams = []
        for unit in units:
            spans, where = [], {}
            for name, url, _ in doors:
                try:
                    got, said_whole = door_timeline(name, url, unit, t0, t1)
                except (OSError, ValueError):
                    unreachable.append(name)
                    continue
                if not said_whole:
                    unreachable.append(name)             # a span it said that does not parse: named, as a silent door
                for sp in got:
                    span = Span(unit, sp["epoch"], sp["start"], sp["end"], sp["bytes"], sp["source"])
                    spans.append(span)
                    where.setdefault(span, (name, url))
            stretches = sorted(authoritative(spans, t0, t1), key=lambda x: x[1])
            streams.append(stream_of(unit, where, stretches))

        # The recordings of the camera merged by time — one piece per recording held at a time — and each moment
        # taken once, the first door's. The MP4 is written as it is made (`fmp4.Writer`, one fragment per group of
        # pictures): the headers go with the first key frame, because that is when "nothing recorded" (404) and "not
        # playable" (415) can no longer be the answer. So there is no `Content-Length`, the connection's end is the
        # file's end, and a door that fails after the first byte cannot be named in a header any more: the export
        # stops there, without its last chunk (`frames_of`), and the journal's line says `broken` and `unreachable`.
        sent = {"bytes": 0, "sha": hashlib.sha256(), "head": False}
        chunked = getattr(handler, "request_version", "") == "HTTP/1.1"

        class Out:
            def write(self, b: bytes) -> None:
                if not b:
                    return
                handler.wfile.write(b"%x\r\n%s\r\n" % (len(b), b) if chunked else b)
                sent["bytes"] += len(b); sent["sha"].update(b)

        writer, frag, end, broken, said = None, [], None, None, 0
        floor = float(os.environ.get("EXPORT_MIN_RATE", EXPORT_MIN_RATE))
        grace = float(os.environ.get("EXPORT_GRACE", EXPORT_GRACE))
        began = time.monotonic()
        try:
            for smp in heapq.merge(*streams, key=lambda s: s.begin):
                took = time.monotonic() - began
                if sent["head"] and took > grace and sent["bytes"] < floor * took:
                    raise TimeoutError(f"the client took {sent['bytes']} bytes in {took:.0f} s, slower than the "
                                       f"{floor:.0f} bytes a second an export is given (EXPORT_MIN_RATE)")
                if end is not None and smp.begin < end:
                    continue                             # this moment came from another door already
                if writer is None:
                    if not smp.key:
                        continue
                    try:
                        sps, pps = fmp4.param_sets(smp.body)
                        width, height = struct.unpack("<II", smp.sub[:8]) if len(smp.sub) >= 8 else (0, 0)
                        writer = fmp4.Writer(Out(), sps, pps, width, height)
                    except FRAME_ERRORS as e:            # a header past what MP4 holds: `struct.error` (the tenth round)
                        return 415, {"detail": str(e), "error": "not playable"}
                    if chunked:
                        handler.protocol_version = "HTTP/1.1"
                    handler.send_response(200)
                    handler.send_header("Content-Type", "video/mp4")
                    if unreachable:
                        handler.send_header("X-Archive-Unreachable", ",".join(sorted(set(unreachable))))
                    if chunked:
                        handler.send_header("Transfer-Encoding", "chunked")
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
            if chunked:
                # The file is whole: the one thing that says so — written by `export` once the line is in the
                # journal and the slots are free.
                if whole is None:
                    handler.wfile.write(b"0\r\n\r\n")
                else:
                    whole.append(b"0\r\n\r\n")
        except (OSError, *FRAME_ERRORS) as e:           # the caller went away, or a frame would not convert
            if not sent["head"]:
                raise
            broken = str(e)
            log.warning("an export of camera %s stopped after %d bytes: %s", cid, sent["bytes"], e)
        late = sorted(set(unreachable[said:]))
        if late:
            log.warning("an export of camera %s was cut: %s did not answer after the first byte", cid, ",".join(late))
        note_read(handler, f"rec/{','.join(units)}/{t0:.0f}-{t1:.0f}",
                  {"status": 200, "bytes": sent["bytes"], "whole": broken is None,
                   **({"sha256": sent["sha"].hexdigest()} if broken is None else {"broken": broken}),
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
#
# A cluster of М11 has no `recworker@` (the twelfth review, a minor): one recorder unit per server, `r-%l-1`, and the
# rest are spares its script starts from the role's template (`vms-recworker-spare@<n>`, as the role's unit) on a server
# that can take them — so the command is that script's, run on the server that has the disks. The console knows it is
# one by its store: a configstore's socket, where a box has files.
# (The subsystems' own numbers — `rec_metrics`, `vms_metrics`, `auto_metrics`, `beat_lines` — are declared in their
# specs since the boundary's step 6, `metrics:`, and the platform's console reads them: `w2cplatform/metrics.py`. The
# counters of the request loops are that loop's process's own: `jobs.metrics_lines`.)


# (The VMS's tables — `/rec/volumes`, `/rec/keeps` — and who may change what — a camera's device, a command's reach, a
# scenario's — were functions here the console called: `rec_routes`, `source_cams`, `command_cams`, `scenario_cams`.
# They are the specs' `tables:` and `rights:` since the boundary's step 6, served and asked by the platform's console.)


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
                       extra=vms_routes(media, live, ctl, rec_ctl), media=media, index=index)
    m = Mount(root)
    if live_ctl is not None:
        m.mount("live", SpecConsole(live_ctl, wall=wall, index=index))
    for name, c in (mounts or {}).items():
        m.mount(name, SpecConsole(c, wall=wall, index=index))          # every mount answers /events from the same merge
    return wire_vms(m, ctl, index)


# WHAT THE VMS'S ROUTES NEED OF THE CONSOLE THAT SERVES THEM — in one place, for every console that does (the review's
# sixth pass, found while sweeping "every door"). All of this was written inside `make_console`, and М11's console is
# built by a function of its own (`cluster/console.py`), which had none of it: `/timeline/<cam>` and `/export/<cam>`
# were not routes that name a unit there, so the gate asked for any grant at all — a viewer of camera 1 was given
# camera 2's timeline and its footage; a recording's labels were its own placement labels; and nothing that left
# through that console was written into the journal. A console built anywhere is wired here, or it is not the VMS's.
def wire_vms(m: Mount, ctl, index=None) -> Mount:
    root = m.root
    if root.extra is not None:
        root.extra.journal = root.journal    # where `archive.read` goes: the journal, `audit/console/…`
        root.extra.index = index or root.index   # where a live session another console handed out is found (`live.view`)
    # What the VMS's routes need at the gate (`w2cplatform/access.py`): a timeline and a live stream name a camera;
    # asking for a live stream is a POST that changes nothing — `view` on that camera, which is the viewer's token on
    # the live door.
    root.UNIT_ROUTES = SpecConsole.UNIT_ROUTES + ("timeline", "export", "whep")
    root.NO_UNIT = ("/whep/session/",)                                   # a live session is not a camera: its route checks it
    root.VIEW_POSTS = ("/whep/",)
    # (What a change of a camera reaches, what a command reaches, what a scenario is — the specs' `rights:` since the
    # boundary's step 6: `reach`, `names`, `cluster_rows`, read by the platform's console.)
    for name, con in m.mounts.items():
        # ONE journal for the process: a mount has no resource root of its own, and "who deleted recording 7"
        # belongs beside "who deleted camera 7".
        con.journal = root.journal
        if con.extra is not None:
            con.extra.journal = root.journal
    return m


# `make_console(...).serve(host, port)`: the server in a daemon thread, returned so the caller can
# `shutdown()` it. `__main__.console` calls it with `$CONSOLE_HOST:$CONSOLE_PORT`; the tests with `port=0`.
def serve(ctl: VmsController, archive_root: str | None, host: str = "127.0.0.1", port: int = 8080, wall=None,
          live_ctl: SpecController | None = None, mounts: dict[str, SpecController] | None = None, index=None) -> ThreadingHTTPServer:
    return make_console(ctl, archive_root, wall, live_ctl, mounts, index).serve(host, port)
