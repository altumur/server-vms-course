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
from w2cplatform.console import (PAGE, ClaimLost, Mount, SpecConsole, framed, heartbeats, holder_of, holders, label,  # noqa: F401
                                 path_id, send_file)   # (PAGE, send_file re-exported for М11)
from w2cplatform.contract import HEARTBEATS, slot_number
from w2cplatform.rows import FIELDS, PARSE_ERRORS, finite, number
from w2cplatform.eventdatabase import MergedIndex
from w2cplatform.spec import Refused, SpecController
from w2cplatform.variables import Conflict

from . import keeps, volumes

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
                sets = [set(self.live.labels_of(w)) for w in holders(self.live.objects, "live/", self.ctl.wall())]
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
# - `GET /segment?cam=` — the DEVICE's own footage, through its holder's playback door (`segment`).


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


def device_spans(objects, cam, ours: list[dict], t0: float, t1: float, now: float) -> list[dict]:
    cov = coverage_of(holder_of(objects, "vms/", cam, now, field="coverage"))
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
        items, _ = rec_ctl.vars.get(rec_ctl._row_key(rec_ctl.spec.parse_id(str(cam))))
    except (OSError, *PARSE_ERRORS):                 # a row nested past JSON's depth too (the tenth round)
        return False
    return not items or str(items.get("cam", cam)) == str(cam)


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
            # A body that is no JSON object is the sender's 400 before any key is claimed (the review's tenth round: not
            # JSON, nested past its depth, a list — the handler fell over and the caller had no reply at all).
            try:
                body = json.loads(raw or b"{}")
                if not isinstance(body, dict):
                    raise TypeError(f"a command is a JSON object, not {type(body).__name__}")
            except PARSE_ERRORS as e:
                return 400, {"detail": f"a command is {{unit, action, …}} as a JSON object ({type(e).__name__})",
                             "error": "bad body"}
            # …and the row lives only until its holder has answered it: the controller clears it, and a retry ninety
            # seconds later found no row and filed the command again (the review's third pass, minor). So the key is
            # ALSO kept where the console keeps every key (`IdempotencyKeys`, `<sub>/idem/`, for a day) — the same
            # claim, the same reply to the same caller with the same body, whichever console the retry reaches.
            seen = getattr(extra, "seen", None)
            if seen is None:
                return file_request(handler, body, key)
            try:
                prior = seen.claim(key, handler.headers.get("X-User", "operator"), raw)
            except Refused as e:
                return 400, {"detail": str(e), "error": str(e)}
            except OSError as e:
                return 503, {"detail": f"the store did not answer: {e}", "error": "store unavailable"}
            if prior is not None:
                return prior
            try:
                reply = file_request(handler, body, key)
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
            # A RANGE IS TWO NUMBERS (the review's fifth pass, minor): `NaN` passed every comparison below — `t1 <= t0`
            # is false for it — and then broke `int()` with no reply at all. Finite, both ends, or 400.
            try:
                body = json.loads(handler.rfile.read(int(handler.headers.get("Content-Length", 0))) or b"{}")
                if any(isinstance(body.get(k), bool) for k in ("from", "to")):
                    raise TypeError("true and false are not seconds")   # `float(False)` is 0.0: 1970, not an answer
                cam, t0, t1 = str(body.get("cam", "")), float(body.get("from", 0)), float(body.get("to", 0))
            except PARSE_ERRORS:                             # a body nested past JSON's depth too: 400, not no reply (the tenth round)
                return 400, {"detail": "a backfill is {cam, from, to}: a camera and two unix seconds", "error": "bad range"}
            if not cam or not (math.isfinite(t0) and math.isfinite(t1)) or t1 <= t0:
                return 400, {"detail": "a backfill wants a camera and a range of finite unix seconds", "error": "bad range"}
            # A RANGE A PERSON CAN MEAN (the review's fourth pass, Т-B6's remainder). The recorder fetches in pieces and
            # a pass takes at most `RANGE_CAP` of a range, but the row took thirty-one years, and the recorder read a
            # device's card from its first second until it was done. A backfill is a hole somebody saw on a timeline:
            # a day at most, and a longer hole is several asks, each of which says what it costs.
            if t1 - t0 > BACKFILL_MAX:
                return 400, {"detail": f"a backfill is a range of at most {BACKFILL_MAX:.0f} s (a day): ask for a longer "
                                       f"hole a day at a time", "error": "range too long"}
            # WHICH recording gets the missing footage: the one the operator named, or the camera's first.
            # A backfill writes into a unit's tree, and with several recordings of one camera there is no
            # "the" tree any more — the caller says, or takes the first and the answer says which it was.
            units = recordings_of(rec_ctl, cam)
            if not units:
                return 404, {"detail": f"camera {cam} has no recording, and the tree named after it is another camera's",
                             "error": "no such recording"}
            unit = str(body.get("rec") or "") or units[0]
            if unit not in units:
                return 400, {"detail": f"camera {cam} has no recording {unit}", "error": "no such recording"}
            # AN ASK SOMEBODY CAN ANSWER (the review's sixth pass, minor). A range of milliseconds, or one that has not
            # happened yet, was a row no recorder could ever fetch — and it held one of its person's places for good.
            now = con_wall()
            if t1 - t0 < BACKFILL_MIN:
                return 400, {"detail": f"a backfill is at least {BACKFILL_MIN:.0f} s of footage", "error": "range too short"}
            if t1 > now + BACKFILL_AHEAD:
                return 400, {"detail": f"a backfill is a hole in what HAS been recorded: this range ends "
                                       f"{t1 - now:.0f} s from now", "error": "range in the future"}
            # …AND NOT BEFORE ANYTHING COULD BE THERE (the review's seventh pass, minor: `{"from": 0, "to": 600}` — 1970 —
            # was a row, and held one of its person's seven places for a day). A range wholly older than what the
            # recording shows (its `retention_days`: the doors would never show what was fetched) or than what the
            # device holds (the coverage its holder announces, when it does) is refused: no recorder could answer it.
            from .archive import visible_from
            try:
                floor, why = visible_from(rec_ctl.unit(unit), now), "the recording shows"
            except PARSE_ERRORS:
                floor, why = now - BACKFILL_MAX * 30, "a recording shows"
            cov = coverage_of(holder_of(ctl.objects, "vms/", cam, now, field="coverage") if ctl is not None else None)
            if cov is not None and cov[0] > floor:
                floor, why = cov[0], "the device holds"
            if t1 <= floor:
                return 400, {"detail": f"this range ends before anything {why} (from {floor:.0f}): no recorder could "
                                       f"fetch it", "error": "range too old"}
            who = handler.headers.get("X-User", "operator")
            # …AND SO MANY OF THEM (the fifth pass's minor): each ask is a day at most, and nothing bounded how many — a
            # day a row, a thousand rows, and the recorder reading a card for a thousand days. One person's asks that
            # the recorders have not answered yet are at most `BACKFILLS_OPEN` — a week of days; the next is 429 until
            # some are fetched (the recorder answers, the console clears the row) or have stood for `jobs.BACKFILL_TTL`.
            #
            # COUNTED BY CAS, NOT BY LOOKING (the sixth pass, minor; a run: forty POSTs at once left fifteen rows). The
            # bound was a count of rows read before the write, and forty requests in flight all counted the same six.
            # A person's open asks are now ONE row — `rec/requests/asks-<sha256 of the person, 16 hex>`, the list of their ids — changed by
            # CAS: a request adds its id only on the revision it read, and the one that loses reads again. The list
            # never holds an eighth. An id stays in it while its request's row stands (the console clears a row the
            # recorder fetched; `jobs.clear_requests` ends one that stood for `BACKFILL_TTL`) — and for
            # `ASK_SETTLE` after it was added, row or no row: the list is written before the request is. The same
            # range again is the same id, and is not counted twice. No worker reads the list as a request: it names
            # no unit and no action.
            rid = f"{unit}-{int(t0)}-{int(t1)}"
            ledger = rec_ctl.spec.sub.request_key("asks-" + hashlib.sha256(who.encode()).hexdigest()[:16])
            for _ in range(50):
                it, idx = rec_ctl.vars.get(ledger)
                try:
                    held = [(str(r), float(at)) for r, at in json.loads((it or {}).get("asks", "[]"))]
                except PARSE_ERRORS:
                    held = []
                held = [(r, at) for r, at in held if now - at <= BACKFILL_TTL
                        and (now - at < ASK_SETTLE or rec_ctl.vars.get(rec_ctl.spec.sub.request_key(r))[0])]
                if rid not in [r for r, _ in held]:
                    if len(held) >= BACKFILLS_OPEN:
                        return 429, {"detail": f"{who} has {len(held)} backfills the recorders have not fetched yet, as "
                                               f"many as one person asks at once — wait for some to be fetched",
                                     "error": "too many"}
                    held.append((rid, now))
                try:
                    rec_ctl.vars.put(ledger, {"asks": json.dumps(held), "by": who, "at": str(now)}, cas=idx)
                    break
                except Conflict:
                    continue                                  # another request of this person's got there first: read again
            else:
                return 503, {"detail": "this person's list of asks would not settle — retry", "error": "busy"}
            rec_ctl.vars.put(rec_ctl.spec.sub.request_key(rid),
                             {"unit": str(unit), "cam": cam, "from": str(t0), "to": str(t1),
                              "at": str(now), "by": who})
            # Who asked for a device's minutes to be fetched into the archive: a line, as a keep and a read are.
            journal = getattr(extra, "journal", None)
            if journal is not None:
                journal.say("archive.backfill.asked", user=who, target=cam, recording=str(unit), request=rid,
                            **{"from": t0, "to": t1})
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
        # …and the rule a unit's name keeps (the eighth pass's sibling: `doors.unnamable` — no `"`, `|`, control
        # characters): a request's id goes into the holder's log lines and its heartbeat whole.
        from w2cplatform.doors import unnamable
        if unnamable(rid):
            return 400, {"detail": f"a request id may not hold {', '.join(repr(c) for c in unnamable(rid))}",
                         "error": "bad id"}
        # A deadline is a finite number of seconds (the review's seventh pass, M3): JSON's `NaN` and `Infinity` reached
        # the row as `nan`/`inf`, and a holder performed such a command hours late. A word is refused here as well.
        try:
            until = finite(body.get("valid_until") or now + 30)
        except (TypeError, ValueError):
            return 400, {"detail": f"`valid_until` is a time in seconds, not {body.get('valid_until')!r}", "error": "bad deadline"}
        if until - now > 600:                                     # the holder refuses it (`VmsWorker.MAX_VALID`): say so at the door
            return 400, {"detail": "a command's `valid_until` is at most ten minutes away", "error": "too far"}
        row = {"unit": unit, "action": action, "at": str(now), "by": handler.headers.get("X-User", "operator"),
               "valid_until": str(until)}
        # The device the rights were asked on (`command_cams`): the holder performs the command only on that device
        # (`VmsWorker.requests`) — a camera moved onto a recorder in the ten minutes a command may wait is not the
        # camera the person had the right to command (the review's eighth pass).
        from .config import device_of
        src = str((ctl.camera(unit) or {}).get("source") or "")
        if src:
            row["device"] = device_of(src)
        for f in ("port", "state", "pulse_ms", "n"):
            if body.get(f) is not None:
                row[f] = str(body[f])
        try:
            ctl.vars.put(ctl.spec.sub.request_key(rid), row, cas=0)
        except Conflict:
            row = ctl.vars.get(ctl.spec.sub.request_key(rid))[0] or row   # the same request, filed already: its row is the answer
        return 202, {"queued": {"id": rid, **row},
                     "detail": "the worker holding this device performs it at its next look at the requests; "
                               "after valid_until it expires unperformed"}

    # `GET /segment?cam=` — the device's own footage, through its holder's playback door: the URL, and a line.
    def segment(handler, q: dict):
        from . import playback as pb
        cam, raw0, raw1 = str(q.get("cam") or ""), q.get("from", 0), q.get("to", 1e12)
        try:
            t0, t1 = pb.times(raw0, raw1)
        except (TypeError, ValueError):
            return 400, {"detail": "from and to are unix seconds, and to is after from", "error": "bad range"}
        # The holder, resolved NOW — never written into a span when it was drawn: a camera that moved between the
        # drawing and the click would make a stored worker name a 404; one heartbeat read cannot go stale.
        found = holder_of(ctl.objects, "vms/", cam, con_wall(), field="playback_url")
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
        doors = recorder_doors(ctl.objects, con_wall()) if ctl is not None else []
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


# EVERY NUMBER A HEARTBEAT CARRIES ONTO THIS PAGE GOES THROUGH `_n` (the review's seventh pass, part 2): read bare —
# `int(v)`, `float(archive_away_since)`, `round(h["sum"])` — one word in one field of one recorder raised, and the
# subsystem's whole `/metrics` was gone, every alert with it; printed bare, a word made a line Prometheus refuses, and
# a scrape with one such line is refused whole. A field that is a word, `nan` or `inf` is read as not said — 0, or the
# line is left out — counted once per heartbeat and field (`rows.number`, `<sub>_console_rows_garbled{table="field"}`).
def _n(sub: str, w: str, field: str, value, kind=float, default=0):
    return number(f"{sub}/{HEARTBEATS}/{w}#{field}", value, kind, default)


# One worker's histogram from its heartbeat — `{buckets: [...], count, sum}` — as Prometheus lines, or none at all when
# any part of it is not numbers: half a histogram is a wrong one.
def _histogram(metric: str, sub: str, w: str, field: str, h, les) -> list[str]:
    try:
        counts = [int(finite(b)) for b in h["buckets"]]
        count, total = int(finite(h["count"])), finite(h["sum"])
    except PARSE_ERRORS as e:
        FIELDS.garbled(f"{sub}/{HEARTBEATS}/{w}#{field}", e)
        return []
    FIELDS.parsed(f"{sub}/{HEARTBEATS}/{w}#{field}")
    return ([f'{metric}_bucket{{worker="{label(w)}",le="{le:g}"}} {n}' for le, n in zip(les, counts)]
            + [f'{metric}_bucket{{worker="{label(w)}",le="+Inf"}} {count}', f'{metric}_sum{{worker="{label(w)}"}} {round(total, 3)}',
               f'{metric}_count{{worker="{label(w)}"}} {count}'])


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
                *_keep_missing(rec_ctl),
                *_recorders(rec_ctl)]
    return lines


# The seconds of each keep that are not in the incidents volume yet, as the recorder copying keeps says (`keep_missing`
# in its heartbeat: `{keep: seconds}`) — the review's fourth pass, major: a keep whose source door nobody could reach
# was copied as nothing, pass after pass, while `rec_keeps_unprotected` said 0 and the ring came for the minutes. The
# largest any live recorder reports, per keep; none while every keep is whole.
def _keep_missing(rec_ctl: SpecController, lost_after: float = 45.0) -> list[str]:
    now, worst, sub = rec_ctl.wall(), {}, rec_ctl.spec.sub.name
    for w, hb in heartbeats(rec_ctl.objects, sub).items():
        if now - hb.ts > lost_after:
            continue
        missing = hb.extra.get("keep_missing") or {}
        if isinstance(missing, str):
            try:
                missing = json.loads(missing)
            except PARSE_ERRORS:                         # `RecursionError` too (the ninth pass's sweep of `door_timeline`)
                missing = {}
        for keep, s in (missing.items() if isinstance(missing, dict) else ()):
            worst[str(keep)] = max(worst.get(str(keep), 0.0), _n(sub, w, f"keep_missing.{keep}", s))
    return ["# TYPE rec_keep_missing_seconds gauge"] + [f'rec_keep_missing_seconds{{keep="{label(k)}"}} {round(s, 1)}'
                                                          for k, s in sorted(worst.items()) if s > 0]


# What each recorder says about itself, from its heartbeat (feedback BG). A fenced recorder and a recorder with
# nothing assigned both showed "0 running"; a volume that would not open, a writer that stalled, an archive that
# went away were in the heartbeat and on the page, and there was nothing to put an alert on.
def _recorders(rec_ctl: SpecController) -> list[str]:
    sub = rec_ctl.spec.sub.name
    hbs = sorted(heartbeats(rec_ctl.objects, sub).items())
    # A status entry that names no recording says nothing about one (the review's seventh pass): `st["id"]` raised out
    # of the whole page on it. And `writer` is read as a map only when it is one.
    status = {w: [st for st in hb.status if "id" in st] for w, hb in hbs}
    writer = {w: hb.extra.get("writer") if isinstance(hb.extra.get("writer"), dict) else {} for w, hb in hbs}
    now = rec_ctl.wall()
    out = ["# TYPE rec_recordings gauge"]
    for w, hb in hbs:
        phases: dict[str, int] = {}
        for st in status[w]:
            phases[str(st.get("phase", "?"))] = phases.get(str(st.get("phase", "?")), 0) + 1
        out += [f'rec_recordings{{worker="{label(w)}",phase="{label(ph)}"}} {n}' for ph, n in sorted(phases.items())]
    out.append("# TYPE rec_volume_error gauge")
    out += [f'rec_volume_error{{worker="{label(w)}"}} {1 if hb.extra.get("volume_error") else 0}' for w, hb in hbs]
    # A recorder pinned to a volume another recorder holds writes nothing and says why only in its heartbeat
    # (`volume_wait`): `volume_error` is empty, its capacity nought. 1 while it waits (the review's eighth pass, a minor).
    out.append("# TYPE rec_volume_wait gauge")
    out += [f'rec_volume_wait{{worker="{label(w)}"}} {1 if hb.extra.get("volume_wait") else 0}' for w, hb in hbs]
    out.append("# TYPE rec_archive_away_seconds gauge")
    away = {w: _n(sub, w, "archive_away_since", hb.extra.get("archive_away_since") or None) for w, hb in hbs}
    out += [f'rec_archive_away_seconds{{worker="{label(w)}"}} {round(now - away[w], 1) if away[w] else 0}' for w, hb in hbs]
    # Why the volume stopped taking samples, by kind: `away` (the daemon, a network — waited for) or `wrong` (a
    # person has to act — the volume is handed back). One line per recorder that has a failure, none otherwise.
    out.append("# TYPE rec_archive_failure gauge")
    out += [f'rec_archive_failure{{worker="{label(w)}",kind="{label(hb.extra["archive_failure"])}"}} 1' for w, hb in hbs
            if hb.extra.get("archive_failure")]
    out.append("# TYPE rec_writer gauge")                          # 1 for the state the volume's writer is in
    out += [f'rec_writer{{worker="{label(w)}",state="{label(writer[w].get("state") or "ok")}"}} 1' for w, hb in hbs]
    # How long since each recording last took anything from its source (feedback BI; the review's
    # `rec_archive_gap_seconds`). `rec_recordings{phase="running"}` says the pipeline is up; this says it is
    # being FED. Counted from the moment the recorder says bytes last arrived — so a recorder that went silent
    # grows here too — and only for recorders whose actuator measures.
    out.append("# TYPE rec_last_frame_age_seconds gauge")
    out += [f'rec_last_frame_age_seconds{{unit="{label(st["id"])}"}} {round(max(0.0, now - at), 1)}'
            for w, hb in hbs for st in status[w] if st.get("last_frame_at")
            if (at := _n(sub, w, str(st.get("id")) + ".last_frame_at", st["last_frame_at"], float, None)) is not None]
    # What the engine refused of each recording's samples, by its answer (the review's third pass). The writer watch
    # counts the VOLUME, and one camera of thirty that was never written — its group of pictures larger than a block
    # — left it `ok`. A counter per recording and answer, from what the recorder's sinks were told.
    out.append("# TYPE rec_samples_refused_total counter")
    out += [f'rec_samples_refused_total{{unit="{label(st["id"])}",status="{label(k)}"}} {_n(sub, w, str(st.get("id")) + ".samples_refused." + str(k), n, int)}'
            for w, hb in hbs for st in status[w]
            for k, n in sorted((st.get("samples_refused") if isinstance(st.get("samples_refused"), dict) else {}).items())]
    # How far back each recording goes, and whether its volume's ring has closed inside the floor it was promised
    # (`min_depth_days`; feedback BM).
    out.append("# TYPE rec_archive_depth_days gauge")
    out += [f'rec_archive_depth_days{{unit="{label(st["id"])}"}} {_n(sub, w, str(st.get("id")) + ".depth_days", st["depth_days"])}'
            for w, hb in hbs for st in status[w] if "depth_days" in st]
    out.append("# TYPE rec_archive_shallow gauge")
    out += [f'rec_archive_shallow{{unit="{label(st["id"])}"}} {1 if st.get("shallow") else 0}' for w, hb in hbs for st in status[w] if "depth_days" in st]
    out.append("# TYPE rec_unconfirmed_seconds gauge")            # a recording going on under an epoch the store has not confirmed
    out += [f'rec_unconfirmed_seconds{{unit="{label(st["id"])}"}} {_n(sub, w, str(st.get("id")) + ".unconfirmed_s", st.get("unconfirmed_s"))}'
            for w, hb in hbs for st in status[w] if st.get("lease") == "unconfirmed"]
    # A camera's stream, as its pusher says it in the camera recorder's heartbeat (`stream`, `vms/card.py`; the eighth
    # review): how far behind the live edge, whether the uplink carries it, and the seconds the stream did not carry —
    # `cut` to the live edge, `left` to backfill after a break, `failed` where the card could not give them; and
    # `evicted`, let go of by the card's budget before the server had them (the ninth review).
    streams = {w: hb.extra["stream"] for w, hb in hbs if isinstance(hb.extra.get("stream"), dict)}
    out.append("# TYPE rec_stream_behind_seconds gauge")
    out += [f'rec_stream_behind_seconds{{worker="{label(w)}"}} {_n(sub, w, "stream.behind_s", s.get("behind_s"))}' for w, s in streams.items()]
    out.append("# TYPE rec_stream_lagging gauge")
    out += [f'rec_stream_lagging{{worker="{label(w)}"}} {1 if s.get("lagging") is True else 0}' for w, s in streams.items()]
    out.append("# TYPE rec_stream_skipped_seconds_total counter")
    out += [f'rec_stream_skipped_seconds_total{{worker="{label(w)}",why="{why}"}} {_n(sub, w, f"stream.{why}_s", s.get(f"{why}_s"))}'
            for w, s in streams.items() for why in ("cut", "left", "failed", "evicted")]
    return out


# What the VMS adds to `/metrics`: the commands its holders performed, refused or let expire, summed over their
# heartbeats. `expired` over the total is the number that says a scenario's requests live shorter than the road
# from an event to the device.
def vms_metrics(ctl):
    def lines() -> list[str]:
        total = {"performed": 0, "refused": 0, "expired": 0, "unknown": 0}
        sub = ctl.spec.sub.name
        hbs = heartbeats(ctl.objects, sub)
        for w, hb in hbs.items():
            counts = hb.extra.get("command_counts")
            for k, v in (counts.items() if isinstance(counts, dict) else ()):
                if k in total:
                    total[k] += _n(sub, w, f"command_counts.{k}", v, int)
        # The road to the device, where it ends (`VmsWorker._measure`), per holder, since it started (the review's seventh
        # pass, minor: what each number is measured FROM). `vms_event_to_device_seconds` from the event's moment to the
        # call, and `vms_request_to_device_seconds` from the row's filing to the call — two clocks each, by who asked
        # (`by`: `auto` for a scenario, `operator` for a person), with the times the clocks visibly disagreed in
        # `…_skewed_total{direction="ahead|behind"}`; and `vms_request_seen_to_device_seconds` from the holder's first
        # sight of the row to the call, by its clock alone. A heartbeat of an older build (one histogram, `skewed`) is
        # read as automation's. Every number through `_histogram` and `_n`: a word in one holder's histogram is that
        # holder's, never the page's (the seventh pass, the metrics of a console).
        from .worker import VmsWorker

        def by_who(h) -> dict:
            if not isinstance(h, dict):
                return {}
            if "buckets" in h:
                return {"auto": h}
            return {b: x for b, x in sorted(h.items()) if isinstance(x, dict) and x.get("buckets")}

        def histogram(metric: str, labels: str, h: dict, w: str = "", field: str = "") -> list[str]:
            try:                                          # half a histogram is a wrong one: all of it, or none
                counts = [int(finite(n)) for n in h["buckets"]]
                count, total = int(finite(h["count"])), finite(h["sum"])
            except PARSE_ERRORS as e:
                FIELDS.garbled(f"{sub}/{HEARTBEATS}/{w}#{field}", e)
                return []
            out = [f'{metric}_bucket{{{labels},le="{le:g}"}} {n}' for le, n in zip(VmsWorker.ROAD_BUCKETS, counts)]
            return out + [f'{metric}_bucket{{{labels},le="+Inf"}} {count}', f'{metric}_sum{{{labels}}} {round(total, 3)}',
                          f'{metric}_count{{{labels}}} {count}']

        road: list[str] = []
        for metric, key in (("vms_event_to_device", "command_road"), ("vms_request_to_device", "command_request")):
            road.append(f"# TYPE {metric}_seconds histogram")
            skew: list[str] = []
            for w, hb in sorted(hbs.items()):
                for by, h in by_who(hb.extra.get(key)).items():
                    if not _n(sub, w, f"{key}.{by}.count", h.get("count"), int) and \
                            not any(_n(sub, w, f"{key}.{by}.{k}", h.get(k), int) for k in ("ahead", "behind", "skewed")):
                        continue
                    road += histogram(f"{metric}_seconds", f'worker="{label(w)}",by="{label(by)}"', h, w, f"{key}.{by}")
                    ahead = _n(sub, w, f"{key}.{by}.ahead", h.get("ahead"), int) + _n(sub, w, f"{key}.{by}.skewed", h.get("skewed"), int)   # `skewed`: an older build's word for ahead
                    skew += [f'{metric}_skewed_total{{worker="{label(w)}",by="{label(by)}",direction="ahead"}} {ahead}',
                             f'{metric}_skewed_total{{worker="{label(w)}",by="{label(by)}",direction="behind"}} {_n(sub, w, f"{key}.{by}.behind", h.get("behind"), int)}']
            road += [f"# TYPE {metric}_skewed_total counter"] + skew
        road.append("# TYPE vms_request_seen_to_device_seconds histogram")
        for w, hb in sorted(hbs.items()):
            h = hb.extra.get("command_wait")
            if isinstance(h, dict) and _n(sub, w, "command_wait.count", h.get("count"), int):
                road += histogram("vms_request_seen_to_device_seconds", f'worker="{label(w)}"', h, w, "command_wait")
        # …and the requests of automation this console dropped as too old (`jobs.expired`): a scenario said
        # `fired` and nothing happened. Zero is the number this should stay at; climbing, it says the requests'
        # loop is late (the review's second pass).
        from . import jobs
        return (["# TYPE vms_commands_total counter"] + [f'vms_commands_total{{outcome="{label(k)}"}} {v}' for k, v in total.items()]
                + ["# TYPE vms_requests_expired_total counter"]
                + [f'vms_requests_expired_total{{sub="{label(s)}"}} {n}' for s, n in sorted(jobs.expired.items())]
                + road + beat_lines(sub, hbs))
    return lines


# What a holder's beat waits on, per holder, from its heartbeat (the review's eighth pass, minor: none of it was on
# `/metrics`): devices whose last call did not answer inside `PERFORM_GRACE` — a look does not wait for them —
# calls into devices not back yet, and the answers said again after a restart instead of performed twice
# (`VmsWorker._answered_before`). A holder says each only when it is not zero: a line for every holder, 0 when unsaid.
def beat_lines(sub: str, hbs: dict) -> list[str]:
    out = []
    for metric, field, kind in (("vms_devices_slow", "devices_slow", "gauge"),
                                ("vms_commands_in_flight", "commands_in_flight", "gauge"),
                                ("vms_device_identity_coincidences", "identity_coincidences", "gauge"),   # the ninth pass
                                ("vms_devices_opening", "devices_opening", "gauge"),                       # the tenth pass
                                ("vms_device_identity_changes_total", "identity_changes", "counter"),      # …and its sibling
                                ("vms_commands_reanswered_total", "commands_reanswered", "counter")):
        out.append(f"# TYPE {metric} {kind}")
        out += [f'{metric}{{worker="{label(w)}"}} {_n(sub, w, field, hb.extra.get(field) or 0, int)}' for w, hb in sorted(hbs.items())]
    return out


# What automation adds: each evaluator's last pass, from its heartbeat — how long it took, how many queries it
# made, how far its furthest cursor trails `now`, and the longest road from an event to a request it filed.
# Without these a slow pass and a held cursor are visible nowhere (the notes on the event log's load).
def auto_metrics(auto_ctl):
    def lines() -> list[str]:
        names = (("pass_seconds", "auto_pass_seconds"), ("queries", "auto_queries_per_pass"),
                 ("lag_seconds", "auto_cursor_lag_seconds"), ("latency_seconds", "auto_firing_latency_seconds"))
        out = []
        sub = auto_ctl.spec.sub.name
        hbs = heartbeats(auto_ctl.objects, sub)
        said = lambda w, hb, key: _n(sub, w, key, hb.extra[key])             # a word in one field is not the page's end
        for key, metric in names:
            out.append(f"# TYPE {metric} gauge")
            out += [f'{metric}{{worker="{label(w)}"}} {said(w, hb, key)}' for w, hb in sorted(hbs.items()) if key in hb.extra]
        # Counted since each evaluator started, so a scrape misses nothing that happened between two of them:
        # the road from an event to its request as a histogram, and the firings too late to file.
        from vms.autoworker import AutoWorker
        out.append("# TYPE auto_event_to_request_seconds histogram")
        for w, hb in sorted(hbs.items()):
            if hb.extra.get("latency"):
                out += _histogram("auto_event_to_request_seconds", sub, w, "latency", hb.extra["latency"], AutoWorker.LATENCY_BUCKETS)
        out.append("# TYPE auto_fired_late_total counter")
        out += [f'auto_fired_late_total{{worker="{label(w)}"}} {said(w, hb, "late")}' for w, hb in sorted(hbs.items()) if "late" in hb.extra]
        out.append("# TYPE auto_firings_suppressed_total counter")     # refused by a scenario's own ceiling
        out += [f'auto_firings_suppressed_total{{worker="{label(w)}"}} {said(w, hb, "suppressed")}' for w, hb in sorted(hbs.items()) if "suppressed" in hb.extra]
        # The long poll of the resources (`AutoWorker.long_poll_stats`), per evaluator, since it started: requests it
        # opened, those answered "a watched event was written", passes begun early for them, and requests that
        # failed or were refused. A wait that fails breaks nothing — the pass still comes — so these are where it
        # is seen: `auto_wait_errors_total` growing is the road back at two seconds.
        for key, metric in (("waits", "auto_waits_total"), ("woken", "auto_woken_total"),
                            ("early_passes", "auto_early_passes_total"), ("wait_errors", "auto_wait_errors_total")):
            out.append(f"# TYPE {metric} counter")
            out += [f'{metric}{{worker="{label(w)}"}} {said(w, hb, key)}' for w, hb in sorted(hbs.items()) if key in hb.extra]
        # The triggers an evaluator watches folded to their kinds because there are more than one request may name
        # (`AutoWorker.wants`, `longpoll.WANTS_MAX`; the review's eighth pass): the long poll goes on, and every unit of
        # those kinds wakes it. 0 when nothing is folded.
        out.append("# TYPE auto_wants_folded gauge")
        out += [f'auto_wants_folded{{worker="{label(w)}"}} {said(w, hb, "wants_folded")}' for w, hb in sorted(hbs.items())
                if "wants_folded" in hb.extra]
        return out
    return lines


# What the recorder holding a volume says about it, beside what was declared (the review's fourth pass, major): the
# size the ring HAS (`size_bytes`) and a declared shrink it has not applied (`shrink_pending`, and its `quota_note`).
# The row is the operator's wish; the heartbeat is the ring. A smaller quota declared without `shrink_confirmed` used
# to show as the new size on the page while the ring stayed as it was, and both rings filled the disk.
#
# The size: `volume_quota` when the recorder says it (the held volume's own size, read from the engine), else
# `archive_quota` when the held volume IS the box's own (`archive`, whose size that field has always been). A volume
# no live recorder holds has no `size_bytes`: nobody can say.
def as_held(rec_ctl: SpecController, vol: dict, now: float, lost_after: float = 45.0) -> dict:
    for w, hb in heartbeats(rec_ctl.objects, rec_ctl.spec.sub.name).items():
        x = hb.extra
        if str(x.get("volume") or "") != vol["name"] or now - hb.ts > lost_after:
            continue
        # A camera's card (`kind: edge`) is no ring of the engine: its recorder says what the card holds against its
        # budget, and whether it opened at all (`vms/card.py`). Nothing to shrink, no size the engine formatted.
        if isinstance(x.get("card"), dict):
            return {"card": {k: x["card"][k] for k in ("state", "segments", "bytes", "budget", "error") if k in x["card"]}}
        size = x.get("volume_quota") or (x.get("archive_quota") if x.get("archive") and x.get("archive") == vol.get("url") else None)
        note = str(x.get("quota_note") or "")
        size = _n(rec_ctl.spec.sub.name, w, "volume_quota", size, int, None)   # a word in a heartbeat is not a size
        return {**({"size_bytes": size} if size else {}),
                "shrink_pending": bool(x.get("shrink_pending") or note), **({"quota_note": note} if note else {})}
    return {}


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
            # …and a keep whose row does not parse is SHOWN, as it holds (the review's eighth pass, part 4): hidden, the
            # camera it holds as far as its interval reads was held by something nobody could see or lift. Its line says
            # so — `garbled`, the interval it holds — and since when this console has seen it so (`garbled_since`).
            sees = getattr(handler, "sees", None)
            garbled: list = []
            shown = keeps.declared(rec_ctl.vars, garbled) + garbled
            if sees is not None:
                shown = [k for k in shown if sees(str(k.cam), handler.labels_for(k.cam))]
            first = extra.__dict__.setdefault("garbled_seen", {})
            now = rec_ctl.wall()
            for k in garbled:
                first.setdefault(k.id, now)
            for gone in set(first) - {k.id for k in garbled}:
                first.pop(gone, None)
            return 200, {"keeps": [{**k.shown(), **({"garbled": True, "garbled_since": first[k.id],
                                                     "to": k.until if k.until != float("inf") else None} if k.garbled else {})}
                                   for k in shown]}
        if method == "POST" and path in ("/keeps", "/keeps/"):
            body = json.loads(handler.rfile.read(int(handler.headers.get("Content-Length", 0))) or b"{}")
            try:
                keeps.refuse(body)
                # A keep is copied into the incidents volume piece by piece, and nothing bounded what it named: a keep
                # of thirty-one years asked for the whole archive (the review's fourth pass, Т-B6's remainder).
                if float(body["to"]) - float(body["from"]) > KEEP_MAX:
                    raise Refused(f"a keep holds at most {KEEP_MAX / 86400:.0f} days: a longer stretch is several keeps")
                # The recordings of the camera as they are NOW, and the camera's own name: a recording
                # deleted before today left a tree called after the camera, and nothing else says whose it is —
                # unless a recording of that name says it was ANOTHER camera's (`own_name_is_hers`).
                names = set(recordings_of(rec_ctl, body["cam"])) | ({str(body["cam"])} if own_name_is_hers(rec_ctl, body["cam"]) else set())
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
            if not rec_ctl.vars.get(keeps.key(id_))[0]:     # a row that does not parse is a keep too: it can be lifted (the seventh pass)
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
            view = {**view, "volumes": [{**v, **as_held(rec_ctl, v, now)} for v in view["volumes"]]}
            # A recorder pinned to a volume whose hold is another's writes nothing and says why (`volume_wait`): only its
            # heartbeat said so, and on this page it was a spare with no capacity (the review's eighth pass, part 2,
            # minor). Its line, and on the volume it waits for.
            waiting = [{"recorder": w, "why": str(hb.extra["volume_wait"])}
                       for w, hb in sorted(heartbeats(rec_ctl.objects, rec_ctl.spec.sub.name).items())
                       if hb.extra.get("volume_wait") and now - hb.ts <= 45.0]
            view["volumes"] = [{**v, **({"waiting": [x["recorder"] for x in waiting if x["why"].startswith(f"{v['name']} ")]}
                                        if any(x["why"].startswith(f"{v['name']} ") for x in waiting) else {})}
                               for v in view["volumes"]]
            return 200, {**view, "spare": len(spare), "spares": sorted(spare), **({"waiting": waiting} if waiting else {}),
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
            out = {"volume": {k: v for k, v in {**vol.to_items(), "name": vol.name}.items() if not k.endswith("_secret")}}
            # "Give this archive less": REQUESTED, not done (the review's fourth pass, major). The recorder shrinks a ring
            # only when the row also says `shrink_confirmed` equal to the new size — shrinking erases its oldest minutes —
            # and the journal said `shrunk` the moment the row was written: the page showed 4 TB, the journal "shrunk",
            # and the ring stayed 8 TB. The console's line is the request, with whether it was confirmed; the size the
            # ring HAS is the recorder's to say (its heartbeat, shown with the volume), and its line when it applied it.
            if was is not None and 0 < vol.quota_bytes < was.quota_bytes:
                confirmed = vol.shrink_confirmed == vol.quota_bytes
                said("archive.volume.shrink_requested", handler, volume=vol.name, quota_bytes=vol.quota_bytes,
                     was=was.quota_bytes, confirmed=confirmed)
                if not confirmed:
                    out["warning"] = (f"{vol.name} keeps its size: shrinking erases the oldest footage, so the recorder "
                                      f"applies it only when the row says shrink_confirmed: {vol.quota_bytes}")
            return 201, out
        if method == "DELETE" and path.startswith("/volumes/"):
            name = path_id(path)
            unread: set = set()                        # a row that does not parse is a declaration too: the page says to delete it
            if not any(v.name == name for v in volumes.declared(rec_ctl.vars, unread)) and name not in unread:
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


# The cameras a scan job reaches: the one it names, and the one whose recording it reads (`jobs.recording_cam`).
def job_cams(vars_):
    from .jobs import recording_cam

    def cams(row: dict) -> set:
        out = {str(row.get("cam") or "")}
        if row.get("rec"):
            out.add(recording_cam(vars_, str(row["rec"])))
        return out - {""}
    return cams


# The camera behind a VOLUME, when it has one: an edge volume is the card in a camera (`volumes.Volume.cam`). `"*"`
# for a card that does not say whose it is — a row from before cards named their camera: only a grant on the whole
# cluster covers it. None for every other kind of volume: a disk or a bucket is the cluster's, no camera's.
def volume_cam(vars_, name: str) -> str | None:
    try:
        vol = volumes.volume_named(vars_, str(name)) if name else None
    except volumes.Unreadable:
        return "*"                                     # a row nobody can read may be a card: only the whole cluster's grant covers it (the seventh pass)
    if vol is None or vol.kind != "edge":
        return None
    return vol.cam or "*"


# The cameras a RECORDING reaches (the review's sixth pass, major): the one it records, and — homed on a camera's
# card — the camera whose card that is. `PUT /rec/recordings/1-b {"home": "card2"}` with `admin` on camera 1 was 200,
# and camera 2's card then wrote camera 2's frames into camera 1's recording, out of its own budget. Rights on the
# camera recorded are not rights on the card: the gate asks for the route's capability on both, before and after the
# edit (`SpecConsole.admit_cams`). That a card holds only its own camera's recordings is the controller's rule, for
# whoever writes the row (`volumes.refuse_recording`).
def recording_cams(vars_):
    def cams(row: dict) -> set:
        return {str(row.get("cam") or ""), volume_cam(vars_, str(row.get("home") or "")) or ""} - {""}
    return cams


# The cameras a change of `source` reaches (the same review, major): every camera of the device the row leaves and of
# the device it moves to, when the device or the channel changes. The credentials are the device's, so
# `PUT /cameras/1 {"source": "…/ch/2"}` under `admin` on camera 1 made the holder open channel 2 as camera 1 — its
# viewers and its archive got camera 2's picture. Moving a camera about a device is an act on the device: `admin` on
# every camera it carries. An edit that leaves the source where it is asks for nothing more.
#
# …and `ref`, the name the domain knows the camera by (М12): changed, the camera is another camera to the layer above
# — its book of primaries, the edits it kept — which is nobody's to decide with rights on one camera: `"*"`, the
# cluster's grant.
#
# …ONE DEVICE BY ITS ONE SPELLING, AND BY ITS OWN WORD (the review's eighth pass, major; a run): `…/10.0.0.50:80/ch/2`,
# `…/ACME/…`, `…/10.0.0.50./…` were other devices than `…/10.0.0.50/…`, and the move asked about nobody else's camera.
# Devices are compared by `device_of` (one spelling) and, where a holder has opened them, by what the device says it
# is (`config.one_device`) — a DNS name and its address are then one device too.
#
# …AND THE SCENARIOS THAT COMMAND THE CAMERA (the same pass, minor). A scenario's `output` on a camera that was its
# device's only channel was checked against that camera alone; moved onto a recorder's channel, the same scenario
# pulsed the RECORDER's relay — a port chosen by somebody with no right on the recorder. Rights are asked when a row is
# written, and a scenario is not rewritten when the camera under it moves. So the move asks for them: whoever moves a
# camera to another device answers for every scenario that commands it — `admin` on each camera such a scenario
# reaches (`scenario_cams`), the cluster's grant for one that watches any camera. `scenarios`: the scenarios' rows and
# their reach, when the console fronts `auto`.
#
# …AND A DEVICE NOBODY HAS OPENED IS THE CLUSTER'S (the owner's decision on the review's ninth pass; a run: in the
# course's build there is no device factory, no holder ever learns what a device is, and `admin` on camera 3 moved it
# onto `nvr50.local/ch/2` — the recorder another camera holds as `10.0.0.50` — and pulsed its relay, 202). A move to a
# device whose identity no holder has written (`Devices.known`) asks for the cluster's grant, `"*"`, whatever the
# spelling: a DNS name, `010.000.000.050`, full-width digits are all keys nobody can say the device of. Once a holder
# has opened it, the move asks for every camera of that device, as before. Whether the source moved is asked by the KEY
# (`source_key` without identities): two clones with one serial number are two devices (the same decision), and a
# camera moved from one to the other has moved.
#
# …AND KNOWN IS HELD NOW (the review's tenth pass, major; a run): a device row stays when its device goes, and a stale
# `nvr50.local` row of a replaced recorder made the name "known" — `admin` on camera 3 moved it onto the new recorder
# the name led to. Known is a row whose device a live holder holds and has heard describe itself now (`Devices.known`);
# a key that does not parse into a device at all (`device_of` gives the text back) has no row and is the cluster's too.
def source_cams(ctl, scenarios=None):
    from .config import device_of, one_device

    def cams(old: dict, new: dict) -> set:
        out = set()
        if str(old.get("ref") or "") != str(new.get("ref") or ""):
            out.add("*")
        a, b = str(old.get("source") or ""), str(new.get("source") or "")
        if a == b:
            return out                                   # the source as it was: nothing moved, nothing to look up
        if volumes.source_key(a) != volumes.source_key(b):
            same = one_device(ctl.vars, ctl.objects, ctl.wall)       # known: held by a live holder now (the tenth pass)
            devices = {same(device_of(s)) for s in (a, b) if s}
            out |= {str(r["id"]) for r in ctl.cameras() if r.get("source") and same(device_of(str(r["source"]))) in devices}
            if device_of(a) != device_of(b):
                if b and not same.known(device_of(b)):
                    out.add("*")                         # nobody can say which device that is: the cluster's grant
                if scenarios is not None:
                    rows, reach = scenarios
                    for row in rows():
                        if str(old.get("id")) in commanded(row):
                            out |= reach(row)
        return out
    return cams


# The cameras a scenario COMMANDS — `output`, `preset` on a camera (`then`, `sub: vms`).
def commanded(row: dict) -> set:
    then = row.get("then")
    try:
        then = json.loads(then or "[]") if isinstance(then, (str, bytes)) else then
    except PARSE_ERRORS:
        return {"*"}
    if not isinstance(then, (list, type(None))):
        return {"*"}                                     # nobody can say what it commands: the cluster's grant
    return {str(a.get("unit")) for a in (then or []) if isinstance(a, dict) and str(a.get("sub", "")) == "vms"
            and str(a.get("action", "")) in ("output", "preset") and a.get("unit")}


# THE CAMERAS A COMMAND TO A DEVICE REACHES (the review's seventh pass, major; a run: a guard with `edit` on camera 1 of
# a sixteen-channel recorder sent `output` to ports 1–4 and `preset 5` — 202, and the device did all of it, the lock of
# camera 2's zone among them). A command is filed for a camera (`unit`), and its holder performs it on the DEVICE
# (`VmsWorker.perform`: `dev.output(port, …)`, `dev.preset(n)` — no channel in either). Nothing a device says of itself
# binds a relay or a preset to a channel: `capabilities()` is `rays`, `relays`, `ptz`, `presets` — counts, the
# device's (`config.describe`, the row `vms/devices/<device>`). So a relay or a preset is every camera's of the device:
# `edit` on each of them, as a change of `source` is `admin` on each (`source_cams`). A camera that is its device's
# only channel — a camera with a card, a file — asks for nothing more than it did. The way out, when a site needs a
# guard to press one relay of a recorder: a binding in the device's description (`relay → channel`, `preset →
# channel`) which this function would read, and which no driver here gives yet.
#
# The device is the one `source_cams` compares by (the eighth pass): one spelling, and the device's own word once a
# holder has opened it — the recorder under `nvr50.local` and under `10.0.0.50` is one recorder.
def device_cams(ctl, cam) -> set:
    from .config import device_of, one_device
    row = ctl.camera(cam)
    src = str((row or {}).get("source") or "")
    if not src:
        return {str(cam)}
    same = one_device(ctl.vars)
    dev = same(device_of(src))
    return {str(cam)} | {str(r["id"]) for r in ctl.cameras() if r.get("source") and same(device_of(str(r["source"]))) == dev}


def command_cams(ctl):
    def cams(path: str, body) -> set:
        if path != "/requests" or not isinstance(body, dict) or str(body.get("action", "")) not in ("output", "preset"):
            return set()                                 # not a command to a device (`file_request` refuses the rest)
        unit = str(body.get("unit") or "")
        return device_cams(ctl, unit) if unit and ctl.camera(unit) is not None else set()
    return cams


# WHICH CAMERAS A SCENARIO IS (the review's fifth pass, its question about `auto`). A scenario's labels are placement
# labels — where its evaluator runs — and say nothing about whose it is; a grant matching them is not a grant on the
# cameras it acts on. A scenario is the cameras it watches and the cameras it acts on: every `unit` of a trigger (a
# camera; a detector's, a recording's, a stream's camera through its row) and every camera of an action (`unit` of a
# command, `cam` of a recording or a scan, and a scan's recording's camera). A trigger with no unit watches every
# camera of its subsystem, and a unit nothing can say the camera of is anybody's: `"*"`, which only a grant on the
# whole cluster covers. And the camera whose CARD a `record` writes to (`archive`, which becomes the recording's
# `home`; the review's sixth pass): the same reach as an operator's `home`, through a scenario. And a command to a
# device — `vms.output`, `vms.preset` — every camera of that device (`device_cams`; the seventh pass): the same reach
# as an operator's `POST /requests`, through a scenario. `ctl`: the cameras' controller, which knows the devices.
def scenario_cams(vars_, mounts: dict, ctl=None):
    from .jobs import recording_cam

    def listed(v) -> list:
        if isinstance(v, (str, bytes)):
            v = json.loads(v or "[]")
        return [e for e in (v or []) if isinstance(e, dict)]

    def cam_of(sub: str, unit: str) -> str:
        if sub in ("vms", "live"):
            return unit                                  # a camera, and a stream is named by its camera
        if sub == "rec":
            return recording_cam(vars_, unit)
        other = mounts.get(sub)
        row = other.unit(unit) if other is not None and "cam" in other.spec.fields else None
        return str(row["cam"]) if row and row.get("cam") else "*"

    def cams(row: dict) -> set:
        out = set()
        for t in listed(row.get("when")):
            unit = str(t.get("unit") or "")
            out.add(cam_of(str(t.get("sub", "")), unit) if unit else "*")
        for a in listed(row.get("then")):
            out.add(str((a.get("unit") if str(a.get("sub", "")) == "vms" else a.get("cam")) or "*"))
            if ctl is not None and str(a.get("sub", "")) == "vms" and str(a.get("action", "")) in ("output", "preset") \
                    and a.get("unit") and ctl.camera(str(a["unit"])) is not None:
                out |= device_cams(ctl, str(a["unit"]))
            if a.get("rec"):
                out.add(recording_cam(vars_, str(a["rec"])))
            if a.get("archive") and volume_cam(vars_, str(a["archive"])):
                out.add(volume_cam(vars_, str(a["archive"])))
        return out
    return cams


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
    m = Mount(root)
    if live_ctl is not None:
        m.mount("live", SpecConsole(live_ctl, wall=wall, index=index))
    for name, c in (mounts or {}).items():
        m.mount(name, SpecConsole(c, wall=wall, index=index,             # every mount answers /events from the same merge
                                  extra=(rec_routes(c) if name == "rec" else          # …and `rec` answers for the archives too,
                                         auto_routes(c) if name == "auto" else None),  # `auto` for its catalogue
                                  metrics_extra=(rec_metrics(c) if name == "rec" else
                                                 auto_metrics(c) if name == "auto" else None)))
    return wire_vms(m, ctl, index)


# WHAT THE VMS'S ROUTES NEED OF THE CONSOLE THAT SERVES THEM — in one place, for every console that does (the review's
# sixth pass, found while sweeping "every door"). All of this was written inside `make_console`, and М11's console is
# built by a function of its own (`cluster/console.py`), which had none of it: `/timeline/<cam>` and `/export/<cam>`
# were not routes that name a unit there, so the gate asked for any grant at all — a viewer of camera 1 was given
# camera 2's timeline and its footage; a recording's labels were its own placement labels; and nothing that left
# through that console was written into the journal. A console built anywhere is wired here, or it is not the VMS's.
def wire_vms(m: Mount, ctl, index=None) -> Mount:
    root = m.root
    cam_labels = lambda cam: (ctl.camera(cam) or {}).get("labels") or []
    if root.extra is not None:
        root.extra.journal = root.journal    # where `archive.read` goes: the journal, `audit/console/…`
        root.extra.seen = root.seen          # where a command's Idempotency-Key is kept past its row (`POST /requests`)
        root.extra.index = index or root.index   # where a live session another console handed out is found (`live.view`)
    # What the VMS's routes need at the gate (`w2cplatform/access.py`): a backfill ACTS; a timeline and a live
    # stream name a camera; asking for a live stream is a POST that changes nothing — `view` on that camera,
    # which is the viewer's token on the live door.
    root.EDIT_ROUTES = SpecConsole.EDIT_ROUTES + ("/backfill",)
    root.UNIT_ROUTES = SpecConsole.UNIT_ROUTES + ("timeline", "export", "whep")
    root.NO_UNIT = ("/whep/session/",)                                   # a live session is not a camera: its route checks it
    root.VIEW_POSTS = ("/whep/",)
    # A camera's `source` moved to another channel or device reaches every camera of both devices (`source_cams`);
    # their labels are read from their own rows, as a mount reads a camera's.
    # …and, moved to another device, every camera of every scenario that commands it (the eighth pass).
    controllers = {name: con.ctl for name, con in m.mounts.items()}
    auto = controllers.get("auto")
    root.moved_cams = source_cams(ctl, (auto.units, scenario_cams(auto.vars, controllers, ctl)) if auto is not None else None)
    # …and a command to a device reaches every camera of the device (`command_cams`).
    root.body_cams = command_cams(ctl)
    root.labels_of = cam_labels
    for name, con in m.mounts.items():
        c = con.ctl
        # ONE journal for the process: a mount has no resource root of its own, and "who deleted recording 7"
        # belongs beside "who deleted camera 7".
        con.journal = root.journal
        if name == "rec":
            con.EDIT_ROUTES = SpecConsole.EDIT_ROUTES + ("/keeps",)   # a keep is set by an operator; a volume by an administrator
            con.ID_ROUTES = ("keeps", "volumes")                       # one id each, and nothing after it
        if "cam" in c.spec.fields:
            # A recording, a stream, a detector are ABOUT a camera, and a grant on labels is a grant on the
            # CAMERA's labels: read from the camera's row, not from the recording's own (which say where it runs).
            # Every subsystem whose rows name a camera — a scan job and a survey too (the review's fourth pass), and
            # a live stream, whose own labels say which gateway serves it (the sixth): by the field, not by a list
            # of names that the next subsystem is missing from.
            con.labels_of = cam_labels
        # …and the rows that reach a camera through ANOTHER field (the review's fifth pass, major): a scan through its
        # recording, a scenario through its triggers and actions. The gate checks every camera such a row names,
        # before and after the write (`SpecConsole.admit_cams`).
        if name == "rec":
            con.cams_of = recording_cams(c.vars)                       # …and a recording through the card it is homed on
        if name == "detjob":
            con.cams_of = job_cams(c.vars)
        if name == "auto":
            con.cams_of = scenario_cams(c.vars, controllers, ctl)
            con.labels_of = cam_labels
        if con.extra is not None:
            con.extra.journal = root.journal
    return m


# `make_console(...).serve(host, port)`: the server in a daemon thread, returned so the caller can
# `shutdown()` it. `__main__.console` calls it with `$CONSOLE_HOST:$CONSOLE_PORT`; the tests with `port=0`.
def serve(ctl: VmsController, archive_root: str | None, host: str = "127.0.0.1", port: int = 8080, wall=None,
          live_ctl: SpecController | None = None, mounts: dict[str, SpecController] | None = None, index=None) -> ThreadingHTTPServer:
    return make_console(ctl, archive_root, wall, live_ctl, mounts, index).serve(host, port)
