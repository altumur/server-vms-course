"""The footage a page reads, served by the holder of what it is of — never by the console (the boundary's step 6).

    GET /door/timeline/<recording>?from&to   on the recorder that holds the recording (`RecWorker.serve_archive`)
    GET /door/export/<recording>?from&to     the same door: an interval as a fragmented MP4

These were the console's routes (`vms/console.py`, `vms_routes`: `/timeline/<cam>`, `/export/<cam>?rec=`) and are the
spec's `door: {routes: [timeline, export]}` now: the console says where the door is and lets in (`GET
/rec/where/<recording>` → `door: {url, token, expires, routes}`, `w2cplatform/door.py`), and the bytes go holder →
browser. What a door reads is what the console read: every recorder's archive door between processes (`/timeline/`,
`/samples/`; `archive_routes` in `vms/recworker.py`) — a recording's minutes may be in more than one volume. The
device's own archive is its holder's door (`VmsWorker.playback_handler`: `/door/timeline/<cam>`, `/door/segment/<cam>`).
"""
from __future__ import annotations

import hashlib
import http.client
import json
import logging
import os
import struct
import threading
import time
import urllib.request

from w2cplatform.console import framed, heard_live, heartbeats
from w2cplatform.contract import HEARTBEATS
from w2cplatform.doors import safe_segment
from w2cplatform.rows import FIELDS, PARSE_ERRORS, finite

log = logging.getLogger("vms.footage")
READ_NOTE_EVERY = 60.0        # the same piece of archive, by the same person: one `archive.read` a minute
READ_NOTE_BYTES = 1 << 20     # …while what left of it is less than this: a larger part is a line every time
EXPORT_MAX = 3600.0           # the longest interval one export answers: the page asks for minutes, a person for an hour
SEGMENT_MAX = 3600.0          # …and one piece of a DEVICE's footage (`/door/segment/<cam>`), after it is cut to the coverage
EXPORTS_AT_ONCE = 2           # exports one door makes at a time (`EXPORTS_AT_ONCE` in its environment): each holds a minute
EXPORT_RETRY = 5.0            # the `Retry-After` of an export refused for that
EXPORTS_PER_USER = 1          # of those, how many one caller makes at once (`EXPORTS_PER_USER`): one person cannot take them all
EXPORT_MIN_RATE = 64 << 10    # bytes a second an export's client must take on average (`EXPORT_MIN_RATE`): slower, it is cut
EXPORT_GRACE = 60.0           # …counted after this many seconds of it (`EXPORT_GRACE`): a door's first answers, a slow start
EXPORT_PIECE = 60.0           # an export reads a stretch this much at a time: what one recording holds in memory
DOOR_TIMEOUT = 5.0            # a recorder's door that does not answer in this is named, not waited for


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
def _rec_epoch(vars_, unit) -> int | None:
    from w2cplatform.epoch import current_epoch
    try:
        return current_epoch(vars_, f"rec/epoch/{unit}") or None
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


# THE ROUTES A RECORDING'S HOLDER OPENS TO A PAGE (the boundary's step 6, the owner's decision 1: the bytes do not go
# through the console). They were the console's (`vms_routes`: `/timeline/<cam>`, `/export/<cam>?rec=`); a page goes to
# the recorder that holds the recording now, with the door token the console gave it at `GET /rec/where/<recording>`
# (`w2cplatform/door.py`), and the routes are the spec's `door: {routes: [timeline, export]}`:
#
#   GET /door/timeline/<recording>?from&to   the recording's spans from EVERY recorder's archive door (each holds one
#                                            volume, and what a recording wrote over its life may be in more than
#                                            one), fenced epochs marked; a door that did not answer named
#   GET /door/export/<recording>?from&to     the frames of an interval as a fragmented MP4, each moment from the
#                                            epoch that owns it whichever door holds it
#
# What they read is what the console read: the doors between recorders (`/timeline/`, `/samples/` — a door between
# processes, until mutual TLS). Who read what is this recorder's journal (`audit/door-<recorder>`), with the name the
# token was given to. `keeper` — the platform's `DoorKeeper` — admits each request; `None` admits everybody (a test's).
def footage_routes(objects, vars_, wall, journal=None, keeper=None, eyes=None):
    seen_reads: dict[tuple, float] = {}
    reads_lock = threading.Lock()

    # WHO READ THE ARCHIVE (the platform review, blocker 1; feedback BI, BU). Every piece that left is a line
    # `archive.read`: who, which piece, from what address, the status, the bytes and — when the piece left WHOLE — the
    # sha256 of those bytes: "is this the file you gave out" is answered by the journal. A part — a player that moved
    # on — once a minute per (who, piece); a WHOLE file always (the review's fourth pass), and a broken download that
    # carried real footage too (the fifth pass): under `READ_NOTE_BYTES` a part is folded into the minute's line.
    # "Who" is the name the console gave the door token to (`sub`) — the gate proved it there.
    def note_read(handler, who: str, rel: str, sent: dict) -> None:
        addr = (getattr(handler, "client_address", None) or ("",))[0]
        now, whole = wall(), bool(sent.get("whole"))
        each = whole or int(sent.get("bytes", 0) or 0) >= READ_NOTE_BYTES
        with reads_lock:
            if not each and now - seen_reads.get((who, rel), -1e18) < READ_NOTE_EVERY:
                return
            if len(seen_reads) > 10000:
                for k in [k for k, t in seen_reads.items() if now - t >= READ_NOTE_EVERY]:
                    del seen_reads[k]
            if not each:
                seen_reads[(who, rel)] = now
        parts = rel.split("/")
        digest = sent.get("sha256") or (hashlib.sha256(sent["data"]).hexdigest() if whole and "data" in sent else None)
        log.info("archive read: %s got %s (%s, %d bytes) from %s", who, rel, sent.get("status"), sent.get("bytes", 0), addr)
        if journal is not None:
            journal.say("archive.read", user=who, media=rel, addr=addr, status=sent.get("status"), bytes=sent.get("bytes", 0),
                        **({"sha256": digest} if digest else {}), **({"recording": parts[1]} if len(parts) > 1 else {}),
                        **({"unreachable": sent["unreachable"]} if sent.get("unreachable") else {}),
                        **({"broken": sent["broken"]} if sent.get("broken") else {}))

    def routes(handler, method: str, path: str, q: dict):
        """`(status, body[, headers])` or `()` (answered), or None — not a route of this door."""
        segs = path.split("/")                           # "", "door", <route>, <recording>
        if len(segs) != 4 or segs[1] != "door" or segs[2] not in ("timeline", "export") or not safe_segment(segs[3]):
            return None
        if method != "GET":
            return 405, {"detail": "this door is read-only", "error": "method"}
        route, unit = segs[2], segs[3]
        if keeper is not None:
            admitted = keeper.admit(handler, route, f"rec/{unit}")
            if admitted is None:
                return ()                                # refused, and said so
            who = str(admitted.get("sub") or "anybody")
        else:
            who = "anybody"
        if route == "timeline":
            return timeline(unit, q)
        return export(handler, who, unit, q)

    # A recording's timeline: from every recorder's door, a door that does not answer NAMED, not waited for; a volume
    # nobody serves now (`unserved_volumes`) said — unavailable, not lost. Each span says whose it is and how to play
    # it (`media`: the export of that recording, a route of this door; the page adds the minutes and its token).
    def timeline(unit: str, q: dict):
        try:                                             # a word, `nan`: 400 — it was no reply at all (the tenth round)
            t0, t1 = finite(q.get("from", 0)), finite(q.get("to", 1e12))
        except ValueError:
            return 400, {"detail": "from and to are unix seconds", "error": "bad range"}
        ours, unreachable = [], []
        # Fenced against the RECORDING's epoch, which the store holds — a door knows only its own recorder's, and the
        # zombie's stream may be in another volume than the survivor's. A copy (`e0`, a keep's) is never fenced.
        cur = _rec_epoch(vars_, unit)
        for name, url, hb in recorder_doors(objects, wall(), eyes=eyes):
            try:
                got, said_whole = door_timeline(name, url, unit, t0, min(t1, 1e11))
            except (OSError, ValueError):
                unreachable.append(name)
                continue
            if not said_whole:
                unreachable.append(name)                 # spans it said that do not parse: its picture is not whole
            for sp in got:
                fenced = bool(sp.get("fenced")) or (cur is not None and 0 < sp["epoch"] < cur)
                ours.append({**sp, "fenced": fenced, "recording": unit, "recorder": name,
                             "volume": hb.extra.get("volume", ""), "media": f"export/{unit}"})
        spans = sorted(ours, key=lambda d: (d["start"], d["epoch"]))
        gone = unserved_volumes(objects, wall(), eyes=eyes)
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

    # AT MOST `EXPORTS_AT_ONCE` OF THEM, AND EACH A STREAM (the review's third pass, major) — on each holder now, as
    # they were on the console: an export reads a minute of the recording at a time and writes the MP4 as it is made,
    # and past the bound the next is 503 with `Retry-After`. NOBODY HOLDS THEM ALL, NOR FOR EVER (the fourth pass):
    # the connection's timeout, the export's pace (`EXPORT_MIN_RATE`, counted after `EXPORT_GRACE`: the fifth pass —
    # the client's pace, not a clock) and the person's share (`EXPORTS_PER_USER`). A cut is SEEN: to an HTTP/1.1
    # client the file goes in chunks, and the last chunk is written only when the file is whole.
    exporting = threading.BoundedSemaphore(max(1, int(os.environ.get("EXPORTS_AT_ONCE", EXPORTS_AT_ONCE))))
    per_user: dict[str, int] = {}
    per_user_lock = threading.Lock()

    def busy(why: str):
        return 503, json.dumps({"detail": why, "error": "busy"}).encode(), [("Content-Type", "application/json"),
                                                                            ("Retry-After", str(int(EXPORT_RETRY)))]

    def export(handler, who: str, unit: str, q: dict):
        mine = max(1, int(os.environ.get("EXPORTS_PER_USER", EXPORTS_PER_USER)))
        with per_user_lock:
            if per_user.get(who, 0) >= mine:
                return busy(f"{who} is making {per_user[who]} export(s) already, as many as one person makes at once — retry")
            per_user[who] = per_user.get(who, 0) + 1
        whole = []                                       # the last chunk, held back until the slots are free again
        try:
            if not exporting.acquire(blocking=False):
                return busy("this door is making as many exports as it makes at once — retry")
            try:
                return _export(handler, who, unit, q, whole)
            finally:
                exporting.release()
        finally:
            with per_user_lock:
                per_user[who] -= 1
                if not per_user[who]:
                    del per_user[who]
            # The file is whole, its line is in the journal and its slots are given back: only now is the client told.
            for b in whole:
                try:
                    handler.wfile.write(b)
                except OSError:
                    pass

    def _export(handler, who: str, unit: str, q: dict, whole: list | None = None):
        import heapq
        from . import fmp4
        try:                                             # `nan` passed both checks below as `float` (the tenth round)
            t0, t1 = finite(q.get("from", 0)), finite(q.get("to", 0))
        except ValueError:
            return 400, {"detail": "from and to are unix seconds", "error": "bad range"}
        if t1 <= t0 or t1 - t0 > EXPORT_MAX:
            return 400, {"detail": f"an export is an interval of at most {EXPORT_MAX:.0f} s", "error": "bad range"}
        # Each moment from the EPOCH that owns it, across every door — a door applies `authoritative` to the volume it
        # holds, and a fenced writer's stream may be in another volume than the survivor's. So the doors' timelines are
        # asked first, the rule is run over all of them, and each stretch is read from the door that holds its owner.
        from vms.obsd import Sample, unix_s
        from .archive import Span, authoritative
        doors = recorder_doors(objects, wall(), eyes=eyes)
        unreachable: list[str] = []
        sent = {"bytes": 0, "sha": hashlib.sha256(), "head": False}

        # THE FRAMES OF A STRETCH, A MINUTE AT A TIME (the review's third pass, major), cut at a key frame the way the
        # recorder cuts what it lands. A DOOR THAT FAILS AFTER THE FIRST BYTE BREAKS THE EXPORT (the sixth pass): the
        # reply ends WITHOUT its last chunk, and the line is `broken`; before the first byte a door that does not
        # answer is a header (`X-Archive-Unreachable`) and a file that is whole for what it says it is.
        def frames_of(name: str, url: str, lo: float, hi: float):
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

        spans, where = [], {}
        for name, url, _ in doors:
            try:
                got, said_whole = door_timeline(name, url, unit, t0, t1)
            except (OSError, ValueError):
                unreachable.append(name)
                continue
            if not said_whole:
                unreachable.append(name)                 # a span it said that does not parse: named, as a silent door
            for sp in got:
                span = Span(unit, sp["epoch"], sp["start"], sp["end"], sp["bytes"], sp["source"])
                spans.append(span)
                where.setdefault(span, (name, url))
        stretches = sorted(authoritative(spans, t0, t1), key=lambda x: x[1])

        def stream():
            for span, lo, hi in stretches:
                yield from frames_of(*where[span], lo, hi)

        chunked = getattr(handler, "request_version", "") == "HTTP/1.1"
        cors = keeper.headers(handler) if keeper is not None else []

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
            for smp in heapq.merge(stream(), key=lambda s: s.begin):
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
                    for k, v in cors:
                        handler.send_header(k, v)
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
                return 404, {"detail": f"no footage of recording {unit} in that interval", "error": "nothing recorded"}
            writer.write_fragment(frag)
            if chunked:
                if whole is None:
                    handler.wfile.write(b"0\r\n\r\n")
                else:
                    whole.append(b"0\r\n\r\n")
        except (OSError, *FRAME_ERRORS) as e:           # the caller went away, or a frame would not convert
            if not sent["head"]:
                raise
            broken = str(e)
            log.warning("an export of recording %s stopped after %d bytes: %s", unit, sent["bytes"], e)
        late = sorted(set(unreachable[said:]))
        if late:
            log.warning("an export of recording %s was cut: %s did not answer after the first byte", unit, ",".join(late))
        note_read(handler, who, f"rec/{unit}/{t0:.0f}-{t1:.0f}",
                  {"status": 200, "bytes": sent["bytes"], "whole": broken is None,
                   **({"sha256": sent["sha"].hexdigest()} if broken is None else {"broken": broken}),
                   **({"unreachable": ",".join(late)} if late else {})})
        return ()

    routes.note_read = note_read
    return routes


# A route's answer onto the wire, for a door that is not the console (`SendMixin` has no headers of its own): JSON,
# or bytes with their headers; `()` was answered by the route; the door's CORS headers on every answer.
def answer(handler, got, cors=()) -> None:
    if got == ():
        return
    status, body, *rest = got
    headers = list(rest[0]) if rest else []
    if not isinstance(body, bytes):
        body = json.dumps(body).encode()
        headers = [("Content-Type", "application/json")] + headers
    handler.send_response(status)
    for k, v in list(cors) + headers:
        handler.send_header(k, v)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)
