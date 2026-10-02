"""The console as data — the other half of spec.py. A subsystem's YAML
already says what its units are, which fields the operator owns and what
leaves the cluster; that is everything a console needs to list, edit and
show them. So the console is one class, run from the same spec:

    GET  /                       the page (console.html): the unit list, the edit form built from the spec's fields,
                                 and — when the subsystem registered media routes — a timeline and a player
    GET  /spec                   what the page reads first: name, rows, id rule, fields, media, metric names
    GET  /<rows>                 {rows: the read model from every worker's heartbeat, configured: the units}
    GET  /where/<id>             the stored placement (why) and the assignments' answer (where, one scan)
    GET  /resources              the platform's resources: usage, units, live | silent
    GET  /unplaceable            units nothing live can serve, with the labels that say why
    GET  /servers                every server as placement sees it: its archive (the label), its resource (the fact), its workers, placeable or why not
    GET  /domain                 the domain's view, if THIS cluster hosts the domain (М12 Lesson 3): members, completeness,
                                 units by cluster, with its age; 404 anywhere else — a cluster does not know the others
    GET/PUT /policy              the administrator's knobs — servers: shared | distinct — one row, <sub>/policy, the console's to write
    GET  /events?from&to&unit&kind&subsystem   the resources' event indexes, merged (MergedIndex), fenced by every subsystem's epochs
    GET  /metrics                <name>_workers_live · <name>_worker_headroom{worker,server} · <name>_worker_load ·
                                 <name>_epoch_conflicts · <name>_failover_seconds{kind="worst"} · <name>_resources_live ·
                                 <name>_<running> (units in phase "running"; the spec names the gauge)
    POST /<rows>  (Idempotency-Key)   the row only — the controller places it on its next pass; the key is a Variable
                                 (<sub>/idem/<key>), so the retry is answered the same by whichever console gets it
    PUT  /<rows>/<id>            the operator's fields; a new revision; refused where the controller refuses
    DELETE /<rows>/<id>          the row is marked; the controller's pass takes its placement back
    POST /marks  (Idempotency-Key)    an operator's observation {unit|cam, note}: the CONSOLE's event, into
                                 console/<instance>/… on this server's resource — never a worker's bucket

What a subsystem adds is registered, not subclassed: `extra(handler, method,
path, query) -> reply | None` gets every request the routes above do not
claim (the VMS: /timeline and /export); a reply is `(status, dict)`,
`(status, bytes)`, `(status, bytes, headers)` or `()` when the extra wrote
it itself. The console holds the subsystem's
SpecController with the console's token — the operator's rows, never
placement — so a write it should not make is a 403 from the store, not a
rule in this file.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # console.py — the console as data: SpecConsole over the same spec, with idempotent writes and the
# subsystem's registered extra routes
#
# **Role in the module.** Lesson 6, the other half of `spec.py`. A subsystem's YAML already says what its
# units are, which fields the operator owns and what leaves the cluster; that is everything a console needs
# to list, edit and show them, so the console is one class run from the same spec. It serves `console.html`,
# `/spec` (what the page reads first), the rows with the read model, `/where`, `/resources`, `/unplaceable`,
# `/events` (if a `MergedIndex` — anything with `query(t0, t1, cam, kind, subsystem, unit, current_epochs)` — is behind it), `/metrics`, and the writes — POST/PUT/DELETE on the rows and
# POST `/marks` — with idempotency keys stored in Variables so a retry answered by another console instance
# is the same request. What a subsystem adds is registered, not subclassed: `extra(handler, method, path,
# query)` gets every request the built-in routes do not claim (the VMS: `/timeline` and `/export`). The
# console holds the subsystem's `SpecController` with the *console's* token (the operator's rows, never
# placement), so a write it should not make is a 403 from the store, not a rule in this file.
# `vms/console.py` builds it via `make_console`; the deploy unit `console.container` runs it as its own
# process.
#
# ## Module-level names
# - `PAGE` — absolute path of `console.html` beside this file; served at `/`.
#
# ### `__init__(self, ctl, marks_root=None, index=None, worst_failover=0.0, wall=None, extra=None,
# media=False, lost_after=45.0)` `ctl` is the subsystem's `SpecController` holding the console's token;
# `marks_root` is this server's resource root — if given, `self.marks` is an `EventLog(marks_root,
# "console", <hostname:pid>, epoch 1)` (the console's own log; one writer, so epoch 1 forever); `index` is
# an optional `MergedIndex` (anything with `query(...)`); `worst_failover` is a number exported on `/metrics`; `extra` is the subsystem's
# route function; `media` tells the page it may draw a timeline and play. `seen` is the `IdempotencyKeys`
# over `<sub>/idem/`. `_scan` caches the assignment directory; `scans` counts cache refreshes.
#
# ## Notes
# - `test_the_console_over_http` walks the whole surface: POST twice with one key is one camera; the
#   console's controller cannot `place` (`Forbidden`); PUT `{"worker": "w-9"}` is 400; `/cameras` rows show
#   `phase running` and `server srv-1`; `/where/1` agrees with the directory; `/spec` says `rows cameras,
#   media true`; `/metrics` contains `vms_cameras_running 1`; `/marks` writes to `console/<instance>/e1/`;
#   the page mentions `/spec`, `/timeline/`, `<video>` and never the word camera outside its comment;
#   `/timeline/1` and an `/export` of it come from the VMS extra, through a recorder's door; PUT `{"enabled": false}` bumps
#   revision to 2; DELETE marks the row and the placement waits for `unplace_deleted`.
# - Idempotency covers POST always, PUT optionally, DELETE never; the page sends a fresh key with every
#   request (including DELETE, where it is ignored).
# - `/events` relies on a `MergedIndex` behind the console — every live resource's own event index, merged; without one it is an honest 503,
#   and the page tolerates that.
# - What a request may cost before anybody knows who sent it (the review's fifth pass): the caller is proved from the
#   headers (`Gate.caller`) before a byte of the body is read; the body is read once, under `MAX_BODY` (`MAX_BLOB`
#   for a blob's bytes) and a deadline (`read_body`); the request's line and headers arrive whole within
#   `CONSOLE_TIMEOUT` (`DeadlineReader`); and `CONSOLE_CONNECTIONS` are served at once, the next answered 503
#   (`ConsoleServer`). A row that reaches a camera through another field says so (`cams_of`), and a write to it asks
#   for the route's capability on every such camera, before and after (`admit_cams`).
# - …and what the sixth pass found left of it. WHOSE the connections are (`Bounds`): one address holds a share of
#   them (`CONSOLE_PER_ADDRESS`), the door in has a reserve (`CONSOLE_RESERVE`, `RESERVE_ROUTES`), the monitors named
#   in `CONSOLE_MONITORS` a lane of their own (`MONITOR_ROUTES`; the seventh pass), and the caller on the box —
#   through the unix socket `CONSOLE_UNIX` (`UnixConsoleServer`) — a lane of its own; the
#   request line and headers have `CONSOLE_HEADER_TIMEOUT`, not the socket's timeout (`Deadlined`). RIGHTS BEFORE THE
#   BODY (`dispatch`): everything the path decides is asked first, the body read after, and only a blob route of the
#   spec reads up to `MAX_BLOB`, `BLOBS_AT_ONCE` at a time (`blob_route`). A CHANGE that reaches other units says so
#   (`moved_cams`, beside `cams_of`). And the same server, deadline and bounded body are every door's, not the
#   console's alone: `door_server`, `Deadlined`, `read_body`, and for what a door streams `Paced` and `start_stream`.
# ================================================================================================
from __future__ import annotations

import io
import json
import logging
import os
import socket
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .doors import MAX_LIMIT, byte_range

from .secrets import mask_secrets
from .contract import (GARBLED, HEARTBEATS, SCHEMA, SKEW_MAX, SKEW_MIN, Assignment, DrainRefused, Heartbeat, SchemaTooNew, builds,
                       is_live, parse_heartbeat, schema_version)
from .epoch import current_epoch
from .rows import counts as garbled_by_table, number
from .eventdatabase import refence
from .events import ALARM, EventLog


# The default flow one operator is expected to read, in events a minute. Past it a timeline of separate
# lines is not information any more: a storm makes every alarm look like the last one, and the operator
# stops reading — which is the failure the whole event path was built to avoid, arriving through the
# front door instead of through a lost write.
#
# Sixty is one a second, and it is a starting number rather than a discovery: the point of having it at
# all is that SOMETHING happens when it is crossed. A norm with nothing acting on it is a comment.
PER_MINUTE = 60.0
CONSOLE_TIMEOUT = 30.0        # seconds a console's socket waits on a client that sends or reads nothing (`CONSOLE_TIMEOUT`)
                              # — and the most a request's line and headers may take, whole (`Mount.handler`)
CONSOLE_CONNECTIONS = 64      # connections one console serves at once (`CONSOLE_CONNECTIONS`): past it, 503 at once
MAX_BODY = 1 << 20            # the largest body a request may declare (`CONSOLE_MAX_BODY`): rows, marks, commands are JSON
MAX_BLOB = 32 << 20           # …except the bytes of a blob field (`CONSOLE_MAX_BLOB`): a mask, not a film
BLOBS_AT_ONCE = 2             # …of which so many are read at a time (`BLOBS_AT_ONCE`): each is `MAX_BLOB` of memory
SESSION_BODY = 16 << 10       # the body of `/session`, which anybody may send: a token, or a name and a password
BODY_RATE = 64 << 10          # bytes a second a body is given on top of `CONSOLE_TIMEOUT` to arrive in, whole
_blobs: list = []


def blobs_slots() -> threading.BoundedSemaphore:
    """The process's bound on blobs being read at once — every mount's, since they share the memory."""
    if not _blobs:
        _blobs.append(threading.BoundedSemaphore(max(1, int(os.environ.get("BLOBS_AT_ONCE", BLOBS_AT_ONCE)))))
    return _blobs[0]
from .access import (COOKIE, GLASS_COOKIE, OPEN_ROUTES, UNIX_PEER, Denied, Gate, caller_addr, is_local, session_cookie,
                     token_of)
from .journal import Journal
from .resource import resources_seen
from .limits import TooLarge
from .spec import Refused, SpecController
from .variables import Conflict, Forbidden

log = logging.getLogger(__name__)

PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "console.html")


# The page's Content-Security-Policy: the one script the browser may run is the page's own, named by its
# hash, and nothing else — not a `<script>` an event's note smuggled into the list, not an `onclick=` in a
# camera's name. The page escapes what it draws (`esc`/`h` in `console.html`); this is the second wall, for
# the place the escaping missed. The script is inline, so `'self'` would refuse it: the hash is the policy.
def page_csp(path: str = PAGE) -> str:
    import base64, hashlib, re
    page = open(path, encoding="utf-8").read()
    scripts = [m.group(1) for m in re.finditer(r"<script>(.*?)</script>", page, re.S)]
    hashes = " ".join("'sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode() + "'" for s in scripts)
    return f"script-src {hashes}; object-src 'none'; base-uri 'none'"


# A file, whole or by `Range` — what a `<video>` element asks for. Parses `bytes=a-b`, replies 206 with
# `Content-Range` and `Accept-Ranges` when a range was asked, 200 otherwise. Used by the VMS's
# page itself; a subsystem with files of its own to serve would call it the same way. `headers`: more of
# them, in front of the file.
def send_file(handler, path: str, content_type: str, headers=()) -> dict:
    """A file, whole or by Range — what a <video> element asks for. Returns what LEFT: `status`, `bytes`, and
    whether it was the whole file (`whole`, with `data` to take a digest of)."""
    size = os.path.getsize(path)
    rng = handler.headers.get("Range")
    span = byte_range(rng, size)                             # cut to the file (`doors`)
    if span is None:
        handler.send_response(416); handler.send_header("Content-Range", f"bytes */{size}")
        handler.send_header("Content-Length", "0"); handler.end_headers()
        return {"status": 416, "bytes": 0, "whole": False}
    start, end = span
    with open(path, "rb") as f:
        f.seek(start); data = f.read(end - start + 1)
    handler.send_response(206 if rng else 200); handler.send_header("Content-Type", content_type)
    for k, v in headers:
        handler.send_header(k, v)
    handler.send_header("Accept-Ranges", "bytes"); handler.send_header("Content-Length", str(len(data)))
    if rng:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    handler.end_headers(); handler.wfile.write(data)
    return {"status": 206 if rng else 200, "bytes": len(data), "whole": start == 0 and end == size - 1, "data": data}


# The domain's view, as the domain left it in THIS cluster's object store on its last pass (М12 Lesson 3,
# feedback X). The operator of the most common site — small members and one server room, the domain in the
# room's cluster — wants one tree, not the room in one console and everything else in another. The cluster console
# does not ask any member anything: it reads what the domain already gathered, the way a recorder reads the
# source book instead of the member's own cluster. A cluster that does not host the domain has no such object and
# says so — it does not know the others. And the view's age is part of the answer: older than `lost_after`, the
# page says "the domain is silent" rather than showing a short list as if it were current (Lesson 1's rule,
# applied to the console itself). Read only: edits go through the domain, the door of Lesson 3.
DOMAIN_VIEW = "domain/view"


def domain_view(objects, now: float, lost_after: float = 45.0) -> tuple[int, dict]:
    raw = objects.get(DOMAIN_VIEW)
    if not raw:
        return 404, {"error": "no domain view here: this cluster does not host the domain, and it does not know "
                              "the others — ask the domain holder's console"}
    d = json.loads(raw)
    age = max(0.0, now - float(d.get("ts", 0)))
    return 200, {**d, "age": round(age, 1), "silent": age > lost_after}


# Every worker's last heartbeat under `prefix`, whatever its age — the read model's and `/metrics`' source.
# Same scan as `Controller.workers_seen` without the age filter.
def heartbeats(objects, sub: str) -> dict[str, Heartbeat]:
    """Every worker's last heartbeat, WHATEVER ITS AGE — the read model's source.

    `sub` is the subsystem's name (`"vms"`, or `"vms/"` — both spellings the callers
    already use). Where its heartbeats LIVE is this function's business and not its
    callers': before they lived under `<name>/heartbeats/`, every caller listed
    `<name>/` and filtered by a suffix, and the filter was not the point — it was
    the price of a key layout that mixed them in with everything else.

    The read model wants the stale ones: it shows them muted, as "last known state".
    Anyone asking *who can I talk to right now* wants `holders()` below instead — a
    catalogue with the health filter inside it, so that no caller has to remember it.
    Four of them forgot."""
    out = {}
    for key in objects.list(sub.rstrip("/") + "/" + HEARTBEATS + "/"):
        raw = objects.get(key)
        hb = parse_heartbeat(key, raw) if raw else None    # one that does not parse is skipped and counted (the review's second pass, M6)
        if hb is not None:
            out[hb.worker] = hb
    return out


# -- the catalogue: who is reachable, and who holds what ----------------------------------------------
# `heartbeats` answers "what did each of them last say", which is what a screen wants. This answers "who
# can I talk to", which is what a subscriber wants — and the difference is one comparison that every
# caller was making differently or not at all (the recorder, the gateway and the detector leant on a dead
# worker's last `phase: running`; the console's playback route checked nothing).
#
# It is the `?passing=true` of a service catalogue, and it is here rather than in each caller for the
# reason Consul put it in the query: a filter that callers apply by hand is a filter callers forget.
def holders(objects, prefix: str, now: float, lost_after: float = 45.0) -> dict[str, Heartbeat]:
    """The heartbeats fresh enough to act on."""
    return {w: hb for w, hb in heartbeats(objects, prefix).items() if is_live(prefix.rstrip("/"), hb.ts, now, lost_after)}


# `(worker, its heartbeat, the unit's status entry)` for the process holding `unit` right now, or None.
# `phase` narrows it further when the caller needs the unit to be doing something and not merely held:
# a recorder subscribes to a fan-out only in `running`, while a playback door answers in `held` too.
def holder_of(objects, prefix: str, unit, now: float, lost_after: float = 45.0,
              phase: str | None = None, field: str | None = None):
    for w, hb in sorted(holders(objects, prefix, now, lost_after).items()):
        for st in hb.status:
            if str(st.get("id")) != str(unit):
                continue
            if phase is not None and st.get("phase") != phase:
                continue
            if field is not None and not st.get(field):
                continue
            return w, hb, st
    return None


# The id in `/<family>/<id>`: the second segment, whatever follows it. The ONE reading of a path's id — the gate's
# (`SpecConsole.route_id`) and every route's, the platform's and a subsystem's (`vms/console.py`) — so the unit
# checked and the unit acted on cannot be two segments of one path (the review's third pass, blocker 1).
def path_id(path: str) -> str:
    segs = path.split("/")
    return segs[2] if len(segs) >= 3 else ""


# A LABEL VALUE ON `/metrics` IS TEXT SOMEBODY ELSE WROTE (the review's eighth pass, part 4). A worker's name, a server's,
# a recording's, a keep's id, a table's, a kind of failure — each went into `{label="…"}` as it stood, and a recording
# named `7"x`, or with a newline in it, made a line the text format cannot read: Prometheus refuses the whole scrape
# for one such line, and every alert of the subsystem goes with it. New names with `"`, `|` or a newline are refused
# where they are created; the ones already stored are written here as the format says — `\` as `\\`, `"` as `\"`, a
# newline as `\n` — by this one function, in every metrics function of the platform and the VMS.
def label(value) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


# WHERE IT LISTENS, SAID (the review's third pass, minor: the unit binds `0.0.0.0` over plain HTTP, and the module's
# notes speak of loopback). The deploy unit keeps `0.0.0.0` — on one box the page is opened from the operator's own
# machine, and the course ships no TLS proxy to stand in front — so the console says so at every start, in the one
# place an administrator reads: beyond loopback, a token, a session cookie and the emergency password cross the
# network as they are. `CONSOLE_HOST=127.0.0.1` behind a TLS proxy (named in `TRUSTED_PROXY`) is the quiet setup.
LOOPBACK = ("127.0.0.1", "::1", "localhost")


def say_where(host: str) -> None:
    if host not in LOOPBACK:
        log.warning("the console listens on %s, beyond loopback, over plain HTTP: tokens, session cookies and the "
                    "emergency password cross the network as they are — put a TLS proxy in front and listen on "
                    "127.0.0.1 (CONSOLE_HOST), the proxy named in TRUSTED_PROXY", host or "every interface")


class NoSuchRoute(Exception):
    """A path with more after its id than its route takes: 404, before the gate is asked."""


# A REQUEST HAS A DEADLINE, NOT ONLY ITS READS (the review's fifth pass, major). `timeout` on the socket bounds one
# read: a client that sent a byte of its headers every second and a half, under a timeout of two, held its thread
# for as long as it liked — and three hundred of them were three hundred threads, all before the gate. The handler's
# reads go through this: each one is given what is left of the request's deadline (`deadline()`), at most the
# socket's own timeout, and past the deadline the read is a `TimeoutError` — which `BaseHTTPRequestHandler` answers
# by closing the connection. Only READS: what the console writes back (an export) is the socket timeout's, and the
# export's own rule (`vms/console.py`).
#
# …AND A BODY HAS A FLOOR ON ITS PACE, NOT ONLY A DEADLINE (the review's eighth pass; a run). The deadline of a body was
# proportional to the length it DECLARED: 64 MiB was given 1054 s, and a sender of a byte every few seconds held its
# connection that long — 32 of them an address's share of the resource's door, two addresses all of it. So past a
# grace a body arrives at `rate` on average or its read is late (`pace`): by `grace + got / rate` seconds after it
# began, `got` bytes are in. A body that comes at the rate the deadline always assumed is not touched — the deadline
# was this floor's last point; a trickle is let go at the grace, not at the end of what it declared.
class DeadlineReader(io.RawIOBase):
    def __init__(self, sock, deadline, op_timeout: float):
        self.sock, self.deadline, self.op = sock, deadline, op_timeout
        self.got, self.floor = 0, None                   # bytes received; (since, grace, rate, got then) while a body is read

    def readable(self) -> bool:
        return True

    def pace(self, grace: float, rate: float) -> None:
        self.floor = (time.monotonic(), float(grace), float(rate), self.got)

    def readinto(self, b) -> int:
        now = time.monotonic()
        left = self.deadline() - now
        if self.floor is not None:
            since, grace, rate, base = self.floor
            left = min(left, since + grace + (self.got - base) / rate - now)
        if left <= 0:
            raise TimeoutError("the request did not arrive whole within its deadline" if self.floor is None else
                               f"the body came slower than the {self.floor[2]:.0f} bytes a second a body is given")
        self.sock.settimeout(min(self.op, left))
        try:
            n = self.sock.recv_into(b)
            self.got += n
            return n
        finally:
            self.sock.settimeout(self.op)


# …AND A DOOR SERVES SO MANY AT ONCE. `ThreadingHTTPServer` made a thread for every connection, with no bound:
# `CONSOLE_CONNECTIONS` of them are served, and the next is answered 503 with `Retry-After` on the spot — a line
# written into its socket by the accepting thread, which waits on it for a second at most and reads none of it (and
# leaves its closing to `linger`). Exports are connections too: they hold a slot of their own (`EXPORTS_AT_ONCE`) inside this bound.
#
# ONE BOUND FOR EVERYBODY, TAKEN BEFORE ANYBODY IS KNOWN, SHUT THE DOOR TO EVERYBODY (the review's sixth pass, major;
# reproduced by a run: 64 connections with no token, reconnecting, and 99.3 % of all requests were 503 — the right
# emergency password from the box and Prometheus among them). A connection is counted when it is accepted, and at
# that moment all a door knows of it is the address. So the bound is cut by what IS known then (`Bounds`):
#
#   an address    holds at most `CONSOLE_PER_ADDRESS` of the common slots — one address cannot take them all, with a
#                 token or without. An IPv6 caller is its /64. A peer named in `TRUSTED_PROXY` is not counted: its
#                 connections are everybody's, and a limit per caller is then the proxy's to keep
#   the reserve   `CONSOLE_RESERVE` more connections, at most `RESERVE_PER_ADDRESS` to an address. Such a connection
#                 has `RESERVE_HEADERS` seconds for its request line and headers, and is answered only on the routes
#                 the door in needs (`RESERVE_ROUTES`); anything else on it is 503 (when it is taken, and monitoring's
#                 own lane: the seventh pass, below)
#   the box       `CONSOLE_BOX_RESERVE` more, for the caller ON THE BOX — a connection that came through the console's
#                 unix socket (`UnixConsoleServer`), which nobody on the network can open — answered on every route:
#                 the operator who came in by the emergency entry has work to do
#
# and every connection's request line and headers arrive within `CONSOLE_HEADER_TIMEOUT`, not `CONSOLE_TIMEOUT`: what
# a caller nobody knows yet may hold is a slot for five seconds.
#
# FOUR ADDRESSES SHUT IT, RESERVE AND ALL (the review's seventh pass, major; reproduced by a run). Sixteen common
# connections to an address and two of the reserve: four addresses sending half a line and reconnecting held all 64
# common connections and all 8 of the reserve, and an honest address had not one 200 — `/metrics`, `/healthz`,
# `/session`, `/cameras`. "Addresses in their dozens", the sixth pass's answer said; it was four. So:
#
#   a smaller share   `CONSOLE_PER_ADDRESS` is 8 — a page's parallel requests, not a quarter of the door
#   the reserve       is taken only when the COMMON slots are all gone — an address past its own share while others
#                     are free has its share, and is refused — and holds one connection of an address
#                     (`RESERVE_PER_ADDRESS`); it is 16 (`CONSOLE_RESERVE`), and answers the door in and `/healthz`
#                     (`RESERVE_ROUTES`). Not `/metrics`: a scrape is a monitor's, and a monitor is known in advance
#   the monitors      addresses named in `CONSOLE_MONITORS` (addresses or networks, comma-separated) have a lane of
#                     their own past the common slots — `CONSOLE_MONITOR_RESERVE` connections, answered on
#                     `MONITOR_ROUTES` only — which nobody else can take: Prometheus is answered whoever floods
#
# The honest numbers, at the defaults (64 common, 8 an address, a reserve of 16 at 1 an address): up to 7 addresses
# flooding leave the common slots open — every caller is served as usual; from 8 to 15 the common slots are gone, and
# an honest address still gets the door in and `/healthz` on the reserve, one connection at a time, and nothing else;
# from 16 the reserve is gone too, and over TCP only the listed monitors are answered (`/metrics`, `/healthz`) — and
# the box, through its unix socket, on every route. A door cannot tell the honest from the many before it has read a
# request; what it can do is make "many" a number that is written down.
#
# THE MONITORS' LANE HAS A SHARE PER ADDRESS TOO (the review's eighth pass, major; a run): М11's job listed
# `10.0.0.0/8`, and eight addresses of the cluster's network sending half a line took the common slots, the reserve and
# all four places of the lane — Prometheus had 503 in 15 of 15 and the autoscaler went blind. An address holds
# `MONITOR_PER_ADDRESS` of the lane (a scraper and a health check on one box), so it takes as many listed addresses as
# the lane has places halved to fill it; and a listed address is trusted — the list is the addresses that scrape, not
# the network they live in (the jobs say which: М11's `console.nomad.hcl`, М12's).
BUSY = (b"HTTP/1.0 503 Service Unavailable\r\nContent-Type: application/json\r\nRetry-After: 1\r\nConnection: close\r\n"
        b"Content-Length: %d\r\n\r\n%s")
CONSOLE_PER_ADDRESS = 8       # of `CONSOLE_CONNECTIONS`, how many one address holds at once (`CONSOLE_PER_ADDRESS`)
CONSOLE_RESERVE = 16          # connections kept for the door in and `/healthz` once the common ones are gone (`CONSOLE_RESERVE`)
RESERVE_PER_ADDRESS = 1       # …of which one address holds this many
CONSOLE_MONITOR_RESERVE = 4   # …and for the addresses in `CONSOLE_MONITORS`, theirs alone (`CONSOLE_MONITOR_RESERVE`)
MONITOR_PER_ADDRESS = 2       # …of which one address holds this many: a scraper and a health check on one box
CONSOLE_BOX_RESERVE = 4       # …and for the caller on the box, through the unix socket (`CONSOLE_BOX_RESERVE`)
CONSOLE_HEADER_TIMEOUT = 5.0  # seconds a request's line and headers may take, whole (`CONSOLE_HEADER_TIMEOUT`)
RESERVE_HEADERS = 2.0         # …on a connection of the reserve or the monitors' lane
RESERVE_ROUTES = ("/session", "/healthz")
MONITOR_ROUTES = ("/metrics", "/healthz")


# What a limit by address counts as one caller: the address — an IPv6 one cut to its /64, which is what one
# subscriber is given and can walk through at will.
def addr_key(addr: str) -> str:
    import ipaddress
    try:
        ip = ipaddress.ip_address(str(addr).split("%", 1)[0])
    except ValueError:
        return str(addr)
    ip = getattr(ip, "ipv4_mapped", None) or ip
    return str(ip) if ip.version == 4 else str(ipaddress.ip_network((ip, 64), strict=False))


# The addresses named in `CONSOLE_MONITORS` (or `env`): `"10.0.0.5, 10.1.0.0/24"` — an address, or a network. What is
# not one is said once and left out: a typo there is a monitor that is not answered, not a door that does not start.
def monitors_from(env: str = "CONSOLE_MONITORS") -> tuple:
    import ipaddress
    out = []
    for raw in (os.environ.get(env) or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(ipaddress.ip_network(raw, strict=False))
        except ValueError:
            log.error("%s names %r, which is not an address or a network: left out", env, raw)
    return tuple(out)


class Bounds:
    """How many connections a door serves at once, and whose: the common slots with a share per address, the reserve,
    the monitors' lane, the box's own. Shared by a door's TCP server and its unix one. `take` answers the lane a new
    connection is served on — `common`, `reserve`, `monitor`, `box` — or None when it is refused; `give` returns it."""

    def __init__(self, limit: int | None = None, per_address: int | None = None, reserve: int | None = None,
                 box: int | None = None, monitor: int | None = None, monitors: tuple | None = None):
        env = lambda name, default: int(os.environ.get(name, default))
        self.limit = max(1, env("CONSOLE_CONNECTIONS", CONSOLE_CONNECTIONS) if limit is None else int(limit))
        self.per_address = max(1, env("CONSOLE_PER_ADDRESS", CONSOLE_PER_ADDRESS) if per_address is None else int(per_address))
        self.reserve = max(0, env("CONSOLE_RESERVE", CONSOLE_RESERVE) if reserve is None else int(reserve))
        self.box = max(0, env("CONSOLE_BOX_RESERVE", CONSOLE_BOX_RESERVE) if box is None else int(box))
        self.monitor = max(0, env("CONSOLE_MONITOR_RESERVE", CONSOLE_MONITOR_RESERVE) if monitor is None else int(monitor))
        self.monitors = monitors_from() if monitors is None else tuple(monitors)
        self.lock = threading.Lock()
        self.used = {"common": 0, "reserve": 0, "monitor": 0, "box": 0}
        self.by_addr: dict[tuple, int] = {}              # (lane, address) -> connections it holds there
        self.refused = 0

    def is_monitor(self, addr: str) -> bool:
        import ipaddress
        if not self.monitors:
            return False
        try:
            ip = ipaddress.ip_address(str(addr).split("%", 1)[0])
        except ValueError:
            return False
        ip = getattr(ip, "ipv4_mapped", None) or ip
        return any(ip.version == n.version and ip in n for n in self.monitors)

    def take(self, addr: str, local: bool = False) -> str | None:
        from .access import trusted_proxies
        key, free = addr_key(addr), local or addr in trusted_proxies()
        with self.lock:
            full = self.used["common"] >= self.limit
            if not full and (free or self.by_addr.get(("common", key), 0) < self.per_address):
                lane = "common"
            elif local:
                lane = "box" if self.used["box"] < self.box else None
            elif self.used["monitor"] < self.monitor and self.is_monitor(addr) \
                    and self.by_addr.get(("monitor", key), 0) < MONITOR_PER_ADDRESS:
                lane = "monitor"                         # a listed monitor: past the common slots, its own lane
            elif full and self.used["reserve"] < self.reserve \
                    and self.by_addr.get(("reserve", key), 0) < RESERVE_PER_ADDRESS:
                lane = "reserve"                         # only once the common slots are ALL gone (the seventh pass)
            else:
                lane = None
            if lane is None:
                self.refused += 1
                return None
            self.used[lane] += 1
            self.by_addr[(lane, key)] = self.by_addr.get((lane, key), 0) + 1
            return lane

    def give(self, addr: str, lane: str) -> None:
        key = addr_key(addr)
        with self.lock:
            self.used[lane] -= 1
            left = self.by_addr.get((lane, key), 1) - 1
            if left > 0:
                self.by_addr[(lane, key)] = left
            else:
                self.by_addr.pop((lane, key), None)


# A REFUSAL THE CLIENT CAN READ (the review's seventh pass, minor; six runs of six on macOS). The 503 was written and
# the socket closed with the client's request still unread in it — and a socket closed with unread bytes is reset,
# not finished: the kernel sends RST, and on macOS the client's next read was `ECONNRESET` instead of the 503 and its
# `Retry-After` waiting in its buffer. The same on a handler's own refusals that leave a body unread (413, the
# reserve's 503). So a connection is closed in two steps: `SHUT_WR` (our answer is finished, a FIN after it), then
# what the client still sends is read and dropped until it closes too, or `LINGER` seconds pass — by one thread for
# the whole door (`linger`), not by the thread that accepts: a flood of refusals must not slow the accepting of the
# next. Each is read up to `LINGER_BYTES`. A connection whose request was read whole is closed at once: there is
# nothing to reset it with.
#
# …AND A FLOOD OF REFUSALS DOES NOT TAKE THE WAITING ROOM (the review's eighth pass, minor; a run): the flood went on
# sending after its 503s, the 256 places of the queue were all its own, and every refusal after that was closed at once
# — reset, for the honest client too (`ConnectionResetError` in 30–35 of 48 at sixteen addresses). So an address holds
# at most `LINGER_PER_ADDRESS` of `LINGER_MAX` places — sixteen flooding addresses hold 64 — and a refusal past them is
# not dropped bare either: what has arrived of it is read and dropped there and then (`_drain_close`), and closed — a
# FIN when nothing was left unread, so the 503 stays readable; abortively (`SO_LINGER` 0) only for a client still
# sending past `LINGER_BYTES`, which a close would reset anyway — and then the kernel holds nothing of it. What a place
# costs is a socket and a dictionary entry: what arrives is read and dropped, never kept.
LINGER = 1.0
LINGER_MAX = 512
LINGER_PER_ADDRESS = 4
LINGER_BYTES = 1 << 20


class _Linger:
    def __init__(self):
        self.lock = threading.Lock()
        self.socks: dict = {}                            # socket -> (deadline, bytes read from it, its address)
        self.by_addr: dict[str, int] = {}                # address -> sockets of it waiting here
        self.thread = None

    def add(self, sock, addr: str = "") -> None:
        try:
            sock.shutdown(socket.SHUT_WR)
            sock.setblocking(False)
        except OSError:
            return _close(sock)
        key = addr_key(addr) if addr else ""
        with self.lock:
            room = len(self.socks) < LINGER_MAX and self.by_addr.get(key, 0) < LINGER_PER_ADDRESS
            if room:
                self.socks[sock] = (time.monotonic() + LINGER, 0, key)
                self.by_addr[key] = self.by_addr.get(key, 0) + 1
                if self.thread is None:
                    self.thread = threading.Thread(target=self._run, daemon=True, name="door-linger")
                    self.thread.start()
        if not room:
            _drain_close(sock)

    # Every socket read (non-blocking — no `select`, which fails past descriptor 1024) every 50 ms until it is done.
    def _run(self) -> None:
        while True:
            with self.lock:
                if not self.socks:
                    self.thread = None
                    return
                socks = list(self.socks.items())
            now, done, over = time.monotonic(), [], []
            for s, (deadline, read, key) in socks:
                try:
                    while read < LINGER_BYTES:
                        got = s.recv(65536)
                        if not got:
                            break
                        read += len(got)
                    else:
                        got = b"over"
                except BlockingIOError:
                    got = b"more"
                except OSError:
                    got = b""
                if not got or got == b"over" or now >= deadline:
                    done.append(s)                       # the client finished too, or had its time
                    if got == b"over":
                        over.append(s)
                else:
                    with self.lock:
                        self.socks[s] = (deadline, read, key)
            with self.lock:
                for s in done:
                    held = self.socks.pop(s, None)
                    if held is not None:
                        left = self.by_addr.get(held[2], 1) - 1
                        if left > 0:
                            self.by_addr[held[2]] = left
                        else:
                            self.by_addr.pop(held[2], None)
            for s in done:
                if s in over:
                    _abort(s)
                _close(s)
            time.sleep(0.05)


# A refusal with no place to wait in: what has arrived is read and dropped now, and the socket closed — a FIN when
# nothing is left unread; at once, abortively, when the client is still sending past `LINGER_BYTES`.
def _drain_close(sock) -> None:
    read = 0
    try:
        while read < LINGER_BYTES:
            got = sock.recv(65536)
            if not got:
                break
            read += len(got)
        else:
            _abort(sock)
    except OSError:                                      # BlockingIOError: drained, nothing more yet
        pass
    _close(sock)


def _abort(sock) -> None:
    import struct
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    except OSError:
        pass


def _close(sock) -> None:
    try:
        sock.close()
    except OSError:
        pass


linger = _Linger()


# Whether a socket has bytes waiting that nobody read: what a close would answer with a reset.
def _unread(sock) -> bool:
    try:
        sock.setblocking(False)
        try:
            return bool(sock.recv(1, socket.MSG_PEEK))
        finally:
            sock.setblocking(True)
    except BlockingIOError:
        return False
    except OSError:
        return False


# The two halves every bounded door has: its server takes a lane for each connection or answers 503 (`Bounded`), and
# its handler reads under a deadline and knows the lane it is served on (`Deadlined`). The console is one such door;
# the holder's, the recorder's and the gateway's are the others (the review's sixth pass, major: the protections were
# the console's alone, and three hundred slow connections to the holder's door were three hundred threads in the
# process holding every camera of its server).
class Bounded:
    daemon_threads = True
    bounds: Bounds

    @property
    def refused(self) -> int:
        return self.bounds.refused

    def peer_of(self, request, client_address) -> tuple[str, bool]:
        """`(address, on the box)` of a connection. A test names its own."""
        addr = str(client_address[0]) if client_address else UNIX_PEER
        return addr, addr.startswith(UNIX_PEER)

    def process_request(self, request, client_address):
        addr, local = self.peer_of(request, client_address)
        lane = self.bounds.take(addr, local)
        if lane is None:
            body = json.dumps({"error": "busy", "detail": "this door serves as many connections as it serves at once, "
                                                          "and so many to one address (CONSOLE_CONNECTIONS, "
                                                          "CONSOLE_PER_ADDRESS) — retry"}).encode()
            try:
                request.settimeout(1.0)
                request.sendall(BUSY % (len(body), body))
            except OSError:
                _close(request)
                return
            linger.add(request, addr)                    # its request unread: finished, not reset
            return
        self.lanes[request] = (addr, lane)
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._give(request)
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._give(request)

    def _give(self, request) -> None:
        held = self.lanes.pop(request, None)
        if held is not None:
            self.bounds.give(*held)

    # A handler that answered without reading all it was sent (a 413, the reserve's 503): finished, not reset.
    def shutdown_request(self, request):
        if _unread(request):
            linger.add(request, (self.lanes.get(request) or ("",))[0])
            return
        super().shutdown_request(request)

    # A client that went away, or was let go at its deadline, is not a fault of the door's: `socketserver` prints a
    # traceback for every exception out of a handler, and a flood would write the log full of them.
    def handle_error(self, request, client_address):
        import sys
        e = sys.exc_info()[1]
        if isinstance(e, OSError):
            log.debug("a connection from %s ended: %s", client_address, e)
            return
        super().handle_error(request, client_address)


class ConsoleServer(Bounded, ThreadingHTTPServer):
    def __init__(self, addr, handler, limit: int | None = None, bounds: Bounds | None = None):
        self.bounds, self.lanes = bounds or Bounds(limit), {}
        self.unix = None                                 # the box's own door beside this one, when there is one
        super().__init__(addr, handler)

    def shutdown(self):
        super().shutdown()
        if self.unix is not None:
            self.unix.shutdown(); self.unix.server_close()


# THE BOX'S OWN DOOR: A UNIX SOCKET (the review's sixth pass, minor). "On the box" was a TCP peer of 127.0.0.1 — and
# behind a proxy on the same machine that is every caller there is (or, the proxy named in `TRUSTED_PROXY`, nobody),
# while any process on the box could spend the lane. A unix socket is a file: who may open it is its directory's
# mode (0700) and its own (0660) — root, as the console's unit runs — a proxy does not come through it, and the
# kernel says who did (`peer_cred`: pid, uid, gid, where it can). `curl --unix-socket <path> http://console/…` on the
# box, or `ssh -L 8080:<path> box` and a browser. Shares the TCP door's bounds (`Bounds`): the box's lane is here.
def peer_cred(sock) -> tuple[int, int, int] | None:
    import struct
    opt = getattr(socket, "SO_PEERCRED", None)
    if opt is None:
        return None                                      # not a kernel that says (macOS): the file's mode is all there is
    try:
        return struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, opt, struct.calcsize("3i")))
    except OSError:
        return None


class UnixConsoleServer(Bounded, socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    def __init__(self, path: str, handler, bounds: Bounds):
        self.bounds, self.lanes = bounds, {}
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, mode=0o700)
        try:
            os.unlink(path)                              # the last console's: a socket file outlives its process
        except FileNotFoundError:
            pass
        was = os.umask(0o117)                            # 0660 from the moment it exists, not after a chmod
        try:
            super().__init__(path, handler)
        finally:
            os.umask(was)

    def get_request(self):
        sock, _ = self.socket.accept()
        cred = peer_cred(sock)
        return sock, (UNIX_PEER + (f":uid={cred[1]}" if cred else ""), 0)

    def server_close(self):
        super().server_close()
        try:
            os.unlink(self.server_address)
        except OSError:
            pass


# A console's doors, opened: the TCP one, and — when `CONSOLE_UNIX` names a path — the box's own beside it, under the
# same bounds. A unix socket that cannot be made is said and gone without: a console with no lane for the box is a
# console; one that does not start is not. The domain's console and its signer open theirs here too (the review's
# seventh pass: they had no reserve and no lane for the box), each with the variable that names its socket (`unix_env`).
def open_doors(host: str, port: int, handler, unix_env: str = "CONSOLE_UNIX", say: bool = True) -> ConsoleServer:
    if say:
        say_where(host)
    srv = ConsoleServer((host, port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    path = os.environ.get(unix_env) or ""
    if path:
        try:
            srv.unix = UnixConsoleServer(path, handler, srv.bounds)
            threading.Thread(target=srv.unix.serve_forever, daemon=True).start()
            log.info("the box's own door is %s: the emergency entry's own turns and connections are there", path)
        except OSError as e:
            log.error("the box's own door %s could not be opened (%s): this console has no lane for the caller on the "
                      "box — the emergency entry competes with the network", path, e)
    else:
        log.info("no door of the box's own (%s is not set): the emergency entry has the network's turns only", unix_env)
    return srv


# The handler's half: reads under the request's deadline, and knows its lane. `header_timeout`: what the request line
# and headers get, whole; a connection of the reserve gets `RESERVE_HEADERS`. A door mixes it in before
# `BaseHTTPRequestHandler`.
class Deadlined:
    timeout = CONSOLE_TIMEOUT
    header_timeout: float | None = None
    lane = "common"

    def setup(self):
        super().setup()
        held = getattr(self.server, "lanes", {}).get(self.request)
        self.lane = held[1] if held else "common"
        op = float(self.timeout or CONSOLE_TIMEOUT)
        headers = float(os.environ.get("CONSOLE_HEADER_TIMEOUT", CONSOLE_HEADER_TIMEOUT)) if self.header_timeout is None \
            else float(self.header_timeout)
        self._headers = min(op, headers, RESERVE_HEADERS if self.lane in ("reserve", "monitor") else headers)
        self.deadline = time.monotonic() + self._headers
        self.rfile = io.BufferedReader(DeadlineReader(self.connection, lambda: self.deadline, op))

    def handle_one_request(self):
        self.deadline = time.monotonic() + self._headers   # each request of a connection that is kept: its own headers' time
        reader = getattr(self.rfile, "raw", None)
        if isinstance(reader, DeadlineReader):
            reader.floor = None                          # …and no body's floor from the request before
        super().handle_one_request()

    # Past the headers the request is its handler's: each operation has the socket's own timeout, and a body is given
    # a deadline of its own by whoever reads it (`SpecConsole.read_body`).
    def parse_request(self):
        ok = super().parse_request()
        self.deadline = time.monotonic() + 365 * 86400.0
        return ok

    def busy_unless(self, routes: tuple, path: str, monitor: tuple = MONITOR_ROUTES) -> bool:
        """True (and 503 sent) when this connection is one of the reserve (or the monitors' lane) and `path` is not
        what that lane is for: `routes` (`monitor`)."""
        allowed = routes if self.lane == "reserve" else monitor if self.lane == "monitor" else None
        if allowed is None or path in allowed:
            return False
        body = json.dumps({"error": "busy", "detail": "this door is full; what it still answers is " + ", ".join(allowed)}).encode()
        self.close_connection = True
        self.send_response(503); self.send_header("Content-Type", "application/json")
        self.send_header("Retry-After", "1"); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
        return True


# A door BETWEEN PROCESSES — the holder's, a recorder's, the gateway's — bounded the same way, with numbers of its own:
# its callers are the cluster's processes (a console asks every recorder's door for a timeline; a recorder copies
# from another's), so one address is given half the door, and there is no reserve and no lane for the box: nothing a
# person logs in at. The environment's `CONSOLE_*` are the console's and are not read here.
DOOR_CONNECTIONS = 64
DOOR_PER_ADDRESS = 32


def door_server(addr, handler, limit: int = DOOR_CONNECTIONS, per_address: int = DOOR_PER_ADDRESS) -> ConsoleServer:
    return ConsoleServer(addr, handler, bounds=Bounds(limit, per_address, reserve=0, box=0, monitor=0, monitors=()))


# WHAT A DOOR STREAMS, IT WRITES IN PIECES, TO A CLIENT THAT TAKES THEM (the review's sixth pass, major). The holder's
# door wrote a minute of a device's footage in one `sendall`, and a socket's timeout is the whole of a `sendall`: a
# camera of 100 kB/s read by a viewer at 150 kB/s — faster than it was recorded — was cut after 36 s, six megabytes
# not sent inside thirty seconds. So a stream is written `STREAM_PIECE` at a time, each piece under the socket's
# timeout; and the bound on a client that hardly reads is a floor on its pace, as an export's is (`EXPORT_MIN_RATE`):
# `STREAM_MIN_RATE` on average over the time this door spent WRITING to it — not waiting for its source, which may be
# a device playing a card back at the speed it was recorded — counted once that time is past `STREAM_GRACE`. To an
# HTTP/1.1 client the pieces are chunks, and the last chunk (`end`) is written only when the stream is whole: a reply
# that ends without it is an error to the client (`http.client.IncompleteRead`), not a shorter answer.
STREAM_PIECE = 128 << 10
STREAM_MIN_RATE = 64 << 10
STREAM_GRACE = 30.0


class Paced:
    def __init__(self, handler, chunked: bool, floor: float = STREAM_MIN_RATE, grace: float = STREAM_GRACE,
                 piece: int = STREAM_PIECE, clock=time.monotonic):
        self.h, self.chunked, self.floor, self.grace, self.piece, self.clock = handler, chunked, floor, grace, piece, clock
        self.sent, self.writing = 0, 0.0

    def write(self, data) -> None:
        view = memoryview(data)
        for off in range(0, len(view), self.piece):
            if self.writing > self.grace and self.sent < self.floor * self.writing:
                raise TimeoutError(f"the client took {self.sent} bytes in {self.writing:.0f} s of writing, slower than "
                                   f"the {self.floor:.0f} bytes a second a stream is given")
            part = view[off:off + self.piece]
            began = self.clock()
            try:
                self.h.wfile.write(b"%x\r\n%b\r\n" % (len(part), part) if self.chunked else part)
            finally:
                self.writing += self.clock() - began
            self.sent += len(part)

    def end(self) -> None:
        if self.chunked:
            self.h.wfile.write(b"0\r\n\r\n")


# The headers of a stream, and whether it goes in chunks: to a client that speaks HTTP/1.1, chunks; to an HTTP/1.0
# one, the bytes until the connection closes — it has no other framing.
def start_stream(handler, status: int, ctype: str, headers=()) -> bool:
    chunked = getattr(handler, "request_version", "") == "HTTP/1.1"
    if chunked:
        handler.protocol_version = "HTTP/1.1"
    handler.send_response(status); handler.send_header("Content-Type", ctype)
    for k, v in headers:
        handler.send_header(k, v)
    if chunked:
        handler.send_header("Transfer-Encoding", "chunked")
    handler.send_header("Connection", "close")
    handler.end_headers()
    handler.close_connection = True
    return chunked


# The reader's half: whether an answer has a framing that tells whole from cut — chunks, or a length that IS one.
# `http.client` says so itself: `chunked` only for `Transfer-Encoding: chunked` alone, `length` only for a
# `Content-Length` that is a number and not below zero. Asking whether the header is THERE (the review's eighth pass,
# minor) took `Content-Length: ten`, `-1` and `Transfer-Encoding: gzip, chunked` for framed, and an answer cut by the
# connection's close for a whole one. Asked before the body is read: `length` counts down as it is.
def framed(r) -> bool:
    return bool(getattr(r, "chunked", False)) or getattr(r, "length", None) is not None


class ClaimLost(Exception):
    """The idempotency claim this console held was taken over by another: it must not write under it (409)."""


# A retried POST must be the same POST whichever console answers it, so the key lives in the store, not in a
# process: `<sub>/idem/<key>` is claimed by a create-only CAS before the write and filled with the reply
# after it. A second instance that sees the claim waits for the reply and serves it; it never repeats the
# write. Keys older than `ttl` are pruned on the way past, at most once a minute.
# What every stdlib handler in the course needs: a JSON (or raw text) reply with the two headers, and the
# JSON body of a request. Mixed into the console's handler and the gateway's.
class SendMixin:
    def _send(self, status, body, raw=False):
        data = body.encode() if raw else json.dumps(body).encode()
        self.send_response(status); self.send_header("Content-Type", "text/plain" if raw else "application/json")
        for k, v in getattr(self, "_extra_headers", ()):                 # a cookie, set by `SpecConsole.session`
            self.send_header(k, v)
        self._extra_headers = ()
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")


def body_deadline(h, n: int) -> None:
    """Give a body of `n` bytes its deadline, whole: the handler's `timeout` and a second for every `BODY_RATE` bytes —
    and, read through a `DeadlineReader`, a floor on its pace past that grace (`pace`). Every door that reads a body
    past its headers sets it — `read_body`, and a door that streams one to a file (the resource's `PUT /mirror`)."""
    if hasattr(h, "deadline"):
        grace = float(getattr(h, "timeout", None) or CONSOLE_TIMEOUT)
        h.deadline = time.monotonic() + grace + max(0, n) / BODY_RATE
        reader = getattr(getattr(h, "rfile", None), "raw", None)
        if isinstance(reader, DeadlineReader):
            reader.pace(grace, BODY_RATE)                # …and a floor on its pace past the grace (the eighth pass)


# A request's body, read once and bounded — the one place a door of this code base reads one (the review's sixth pass:
# "every place a body is read"; the gateway's offer and the domain's doors read `Content-Length` bytes, whatever it
# said). `h` is a handler with `_send` (`SendMixin`). `Content-Length` past `limit` is 413 and nothing is read; not a
# number, 400; what is read is read under a deadline of its own — the handler's `timeout` and a second for every
# `BODY_RATE` bytes (`Deadlined`) — and put back as memory, so whoever answers reads it as if nobody had. True: go on;
# False: refused, and the reply sent.
def read_body(h, limit: int) -> bool:
    raw = (h.headers.get("Content-Length") or "").strip()
    if not raw or raw == "0":
        return True
    try:
        n = int(raw)
        if n < 0:
            raise ValueError(raw)
    except ValueError:
        h.close_connection = True
        h._send(400, {"detail": f"Content-Length is a number of bytes, not {raw!r}", "error": "bad length"})
        return False
    if n > limit:
        h.close_connection = True                        # not drained: the rest of it is not read at all
        h._send(413, {"detail": f"a body of {n} bytes; this door takes at most {limit} here", "error": "too large"})
        return False
    body_deadline(h, n)
    try:
        data = h.rfile.read(n)
    except (TimeoutError, OSError) as e:
        h.close_connection = True
        try:
            h._send(408, {"detail": f"the body did not arrive whole in time: {e}", "error": "timeout"})
        except OSError:
            pass
        return False
    if len(data) < n:
        h.close_connection = True
        h._send(400, {"detail": f"the body ended after {len(data)} of {n} bytes", "error": "short body"})
        return False
    h.rfile = io.BytesIO(data)
    return True


class IdempotencyKeys:
    """A retried POST must be the same POST whichever console answers it, so
    the key lives in the store, not in a process: `<sub>/idem/<key>` is
    claimed by a create-only CAS before the write and filled with the reply
    after it. A second instance that sees the claim waits for the reply and
    serves it; it never repeats the write. Keys older than `ttl` are pruned
    on the way past, at most once a minute."""

    # `prefix` is `<sub>/idem/`; `wall` stamps `at`; `clock` rate-limits pruning and ages a pending claim;
    # `sleep` is the wait between polls (injected for tests).
    def __init__(self, vars_, prefix: str, wall, ttl: float = 86400.0, clock=time.monotonic, sleep=time.sleep):
        self.vars, self.prefix, self.wall, self.ttl, self.clock, self.sleep = vars_, prefix, wall, ttl, clock, sleep
        self._pruned = -1e9
        self._seen: dict[str, tuple[int, float]] = {}    # pending claim -> (its revision, when THIS process first saw it)
        self._mine: dict[str, dict] = {}                 # the claims this process holds: whose, and of what body
        self._reserved: dict[str, str] = {}              # claims taken over -> the id the first attempt reserved
        self._rev: dict[str, int] = {}                   # the claims this process holds -> the revision it wrote last

    # Refuses an empty key, one containing `/` or `..`, or longer than 200 chars (`Refused`: must be one
    # path segment) and returns `prefix + key`.
    def _path(self, key: str) -> str:
        if not key or "/" in key or ".." in key or len(key) > 200:
            raise Refused("Idempotency-Key must be one path segment")
        return self.prefix + key

    # Whose request, and of what: `sub` and the sha256 of the body go into the claim, so a replay is answered
    # only to the same caller with the same body.
    @staticmethod
    def _tag(sub, body) -> dict:
        import hashlib
        out = {}
        if sub is not None:
            out["sub"] = str(sub)
        if body is not None:
            out["sha256"] = hashlib.sha256(body if isinstance(body, bytes) else str(body).encode()).hexdigest()
        return out

    # A key is a name for ONE request by ONE caller. Replayed by somebody else, or with another body, it used to be
    # answered with the first caller's reply — a stranger got anna's 201, and anna's own second mark under a reused
    # key was silently not written (the review's second pass, minor). A claim that carries no tag — written before
    # tags, or by a test — matches anybody, as it did.
    @staticmethod
    def _mismatch(items: dict, tag: dict):
        for k in ("sub", "sha256"):
            if k in items and k in tag and items[k] != tag[k]:
                return 422, {"detail": "this Idempotency-Key names another request: a key is one caller's, for one body",
                             "error": "key reused"}
        return None

    # Try `put({state: pending, at, sub, sha256}, cas=0)`: success means ours to answer — return `None` (the
    # caller does the write, then `store`). On `Conflict`, another instance holds it: poll up to 40 × 50 ms; if the
    # row vanished (pruned or the claimant crashed mid-flight) claim again; if `state == done` return `(status,
    # body)`; after the polls, `409 in flight`. `test_a_retry_that_lands_on_another_console_is_one_camera`
    # covers all of it: the second console returns the first's 201 body; a key with a pending claim makes
    # console A wait and then serve B's reply without creating a camera; a key `a/b` is 400.
    def claim(self, key: str, sub=None, body=None):
        """None: ours to answer — do the write, then store(). Else the reply to serve."""
        path, tag = self._path(key), self._tag(sub, body)
        try:
            self._rev[path] = self.vars.put(path, {"state": "pending", "at": self.wall(), **tag}, cas=0)   # create-only: the first claimant wins
            self._mine[path] = tag
            self.prune()
            return None
        except Conflict:
            pass
        for _ in range(40):                                              # another instance holds it: its reply, when it lands
            items, idx = self.vars.get(path)
            if items is None:
                self._seen.pop(path, None)
                return self.claim(key, sub, body)                        # pruned or crashed mid-flight: claim again
            wrong = self._mismatch(items, tag)
            if wrong is not None:
                return wrong                                             # somebody else's key, or another body under it: not this reply
            if items.get("state") == "done":
                self._seen.pop(path, None)
                return int(items["status"]), json.loads(items["body"])
            # A claim that has stood still for `PENDING_TTL` is nobody's: its console crashed between the claim
            # and the reply, or its write raised. It used to stand for the key's whole day, answering every
            # correct retry with 409 (the platform review; feedback BG). The next request takes it over, by
            # CAS, and does the work.
            #
            # "Stood still" is judged by THIS process's monotonic clock from the moment it first saw this
            # revision of the claim — never by the `at` another console wrote with its own wall clock (the
            # review's second pass, major): a console a minute behind its neighbour read every fresh claim as
            # stale, took it over and created the second camera. A claim re-made by somebody else is a new
            # revision, and the count starts again.
            first = self._seen.get(path)
            if first is None or first[0] != idx:
                first = self._seen[path] = (idx, self.clock())
            if self.clock() - first[1] >= self.PENDING_TTL:
                kept = {"id": items["id"]} if "id" in items else {}       # the id the first attempt reserved: ours to create under
                try:
                    self._rev[path] = self.vars.put(path, {"state": "pending", "at": self.wall(), **tag, **kept}, cas=idx)
                    self._seen.pop(path, None)
                    self._mine[path] = tag
                    if kept:
                        self._reserved[path] = kept["id"]
                    return None
                except Conflict:
                    continue
            self.sleep(0.05)
        if len(self._seen) > 1000:                                       # claims nobody came back for: forgotten past the TTL
            cutoff = self.clock() - self.PENDING_TTL
            self._seen = {p: v for p, v in self._seen.items() if v[1] > cutoff}
        return 409, {"detail": "the same request is in flight on another console", "error": "in flight"}

    PENDING_TTL = 30.0

    # The id a create is about to use, written into the claim BEFORE the row (`SpecController.create(reserve=)`).
    # A console that dies between the two leaves a claim that names the unit: whoever takes the claim over
    # creates under that id, or finds it created and answers with it — one camera either way (the product's
    # `Reserve`, feedback CS). Without it a lost reply and a write never made were the same claim, and the
    # retry made the second camera.
    #
    # By CAS on the revision this process wrote — like `store` and `release` (the review's third pass, major). A
    # take-over is a new revision; the console it was taken from may only be asleep, and when it wakes its write
    # must lose. Without the CAS it did not: A stood still for thirty seconds, B took the claim and created unit
    # 8, A woke and created unit 9 under the same key. Now A's `reserve` is a `ClaimLost` — 409, and no row.
    def reserve(self, key: str, uid) -> None:
        path = self._path(key)
        try:
            self._rev[path] = self.vars.put(path, {"state": "pending", "at": self.wall(), **self._mine.get(path, {}), "id": str(uid)},
                                            cas=self._rev.get(path, 0))
        except Conflict:
            self._lose(path)
            raise ClaimLost(f"the claim on {key} was taken over by another console: this one does not write") from None

    def reserved(self, key: str):
        """The id reserved by the attempt this process took the claim over from, if it got that far; else None."""
        return self._reserved.pop(self._path(key), None)

    def _lose(self, path: str) -> None:
        self._mine.pop(path, None); self._reserved.pop(path, None); self._rev.pop(path, None)

    # Overwrite the row with `{state: done, status, body: json, at}` plus the claim's tag — by CAS on the claim this
    # process holds (create-only when it holds none). Lost: `ClaimLost`, and the claim is the other console's.
    #
    # A 5xx is NOT remembered: "the store is away" is not an answer to the request, and kept under the key it was
    # the answer to every retry for a day. The claim is let go instead, and the retry does the work.
    def store(self, key: str, resp: tuple[int, dict]) -> None:
        if int(resp[0]) >= 500:
            return self.release(key)
        path = self._path(key)
        tag, rev = self._mine.get(path, {}), self._rev.get(path, 0)
        try:
            self.vars.put(path, {"state": "done", "status": resp[0], "body": json.dumps(resp[1]), "at": self.wall(), **tag}, cas=rev)
        except Conflict:
            raise ClaimLost(f"the claim on {key} was taken over by another console before the reply was kept") from None
        finally:
            self._lose(path)

    def release(self, key: str) -> None:
        """Let a claim go: the write it stood for did not happen. Only the claim this process holds — one taken
        over meanwhile is the other console's, and stays."""
        path = self._path(key)
        rev = self._rev.get(path)
        self._lose(path)
        if rev is None:
            return
        try:
            self.vars.delete(path, cas=rev)
        except Exception:                                                # noqa: BLE001 — taken over, or it ages out in `PENDING_TTL`
            pass

    # At most once per 60 s of monotonic time: delete every key under the prefix whose `at` is older than
    # `ttl`, by CAS (a conflict skips it). The test advances a day and sees 2 pruned, then 0, then a re-used
    # key create a new camera — a forgotten key is a new request, by design.
    def prune(self) -> int:
        if self.clock() - self._pruned < 60:
            return 0
        self._pruned = self.clock(); n = 0; now = self.wall()
        for path in self.vars.list(self.prefix):
            items, idx = self.vars.get(path)
            # `at` through `rows.number` (the review's seventh pass): a word there raised out of the loop — the rows after
            # it never pruned — and out of the POST that ran the prune, which got no reply. Its age not known, the row
            # is kept: counted, and the others are pruned.
            at = number(f"{path}#at", items.get("at", 0), float, None) if items else None
            if at is not None and now - at > self.ttl:
                try:
                    self.vars.delete(path, cas=idx); n += 1
                except Conflict:
                    pass
        return n


# One console for every subsystem.
class SpecConsole:
    """One console for every subsystem. `ctl` is the subsystem's SpecController
    holding the console's token; `media` says the page may draw a timeline and
    play (the subsystem's `extra` serves /timeline and a media route)."""

    def __init__(self, ctl: SpecController, marks_root: str | None = None, index=None, worst_failover: float = 0.0,
                 wall=None, extra=None, media: bool = False, lost_after: float = 45.0, metrics_extra=None,
                 per_minute: float = 0.0):
        self.ctl, self.spec, self.index = ctl, ctl.spec, index
        self.worst_failover, self.wall, self.extra, self.media, self.lost_after = worst_failover, wall or ctl.wall, extra, media, lost_after
        self.instance = f"{socket.gethostname()}:{os.getpid()}"
        self.marks_root = marks_root
        # The second seam of the same shape as `extra`. A subsystem may have a number nobody else has —
        # `rec` knows how many archives are declared and how many nobody is writing into — and `/metrics`
        # is where a scaling policy can see it. Called with no arguments, returns Prometheus lines; the
        # platform never learns what it counted.
        self.metrics_extra = metrics_extra
        # How many events a minute one operator is expected to read. Past it the timeline stops showing
        # lines and starts showing counts — see `timeline`. The number belongs to the CONSOLE and not to a
        # subsystem's policy, because the screen merges every subsystem and the attention it competes for
        # is one person's; and it is a number rather than a constant because a control room with four
        # screens and a guard with a phone are not the same reader.
        self.per_minute = float(os.environ.get("EVENTS_PER_MINUTE", per_minute) or PER_MINUTE)
        self.marks = EventLog(marks_root, "console", self.instance, 1) if marks_root else None   # the console's own log: one writer, so epoch 1
        self.journal = Journal(marks_root, "console", self.wall)   # what was done through this console, and by whom (`journal.py`)
        self.gate = Gate(ctl.vars, self.wall, lambda: self.journal)   # who is calling, and may they (`access.py`)
        self.seen = IdempotencyKeys(ctl.vars, f"{self.spec.name}/idem/", self.wall)   # in the store: any instance answers a retry
        self.epoch_policy: dict[str, str] = {self.spec.name: self.spec.older_epochs}   # replaced by the Mount's shared one
        self.clock = time.monotonic                      # ages the caches below; a test sets its own
        self._scan: tuple[float, dict] = (-1e9, {})
        self.scans = 0
        self._epochs: tuple[float, dict] = (-1e9, {})
        self.epoch_scans = 0

    # The operator's view of a window, which is NOT the index's view of it.
    #
    # `per_minute` is the norm; past it the screen stops showing lines and starts showing counts. This is
    # the half without which the number is a comment in a file: a norm nobody acts on changes nothing, and
    # the thing it is supposed to prevent — a storm turning alarms into wallpaper until the operator stops
    # reading — happens exactly the same with the number written down.
    #
    # It lives HERE and not in the index, and the line is worth naming: the index answers processes, and a
    # process reads a thousand lines as easily as ten. The evaluator (М10B, Lesson 25) asks the same merge
    # and must keep getting every line, because a scenario missing its event is the failure this whole
    # path exists to avoid. Only the reader who tires gets counts instead.
    #
    # An aggregate is `(subsystem, unit, kind, class)` with a count and the bounds it spans — the same
    # three numbers a suppressed window reports (Lesson 12), because it is the same question asked one
    # layer up: what happened, how many times, between when and when. Alarms keep their own groups rather
    # than being folded in with the noise, so a screen in aggregate mode still puts them first.
    def timeline(self, rep: dict, t0: float, t1: float) -> dict:
        events = rep.get("events", [])
        minutes = max((min(t1, self.wall()) - t0) / 60.0, 1 / 60.0)
        rate = len(events) / minutes
        out = {**rep, "rate_per_minute": round(rate, 1), "per_minute": self.per_minute, "aggregated": False}
        if rate <= self.per_minute or not events:
            return out
        groups: dict[tuple, dict] = {}
        for e in events:
            k = (e.get("subsystem"), str(e.get("unit")), e.get("kind"), e.get("class"))
            g = groups.get(k)
            if g is None:
                groups[k] = {"subsystem": k[0], "unit": k[1], "kind": k[2], "class": k[3],
                             "count": 1, "since": e["t"], "until": e["t"]}
            else:
                g["count"] += 1
                g["since"], g["until"] = min(g["since"], e["t"]), max(g["until"], e["t"])
        ordered = sorted(groups.values(), key=lambda g: (g["class"] != ALARM, -g["count"], g["since"]))
        return {**out, "aggregated": True, "events": [], "groups": ordered}

    # -- what the page reads first ------------------------------------------------------------
    # `/spec`'s body: `{name, rows, id, media, fields: [{name, type, default, required}], metrics: {prefix,
    # running}}` — the page's only knowledge of the subsystem.
    def describe(self) -> dict:
        s = self.spec
        return {"name": s.name, "rows": s.rows, "id": s.id, "media": self.media,
                "fields": [{"name": f.name, "type": f.type, "default": f.default_value(), "required": f.required,
                            **({"inherit": f.inherit, "merge": f.merge} if f.inherits else {})} for f in s.fields.values()],
                "metrics": {"prefix": s.name, "running": s.running_gauge}}

    # -- the directory: where is unit N, in one scan of the assignments ---------------------------
    # `{worker: units}` from one scan of the assignments, cached for 5 s of monotonic time.
    def directory(self) -> dict[str, list[str]]:
        now = time.monotonic()
        if now - self._scan[0] >= 5.0:
            self._scan = (now, {w: a.units for w, a in self.ctl.assignments().items()}); self.scans += 1
        return self._scan[1]

    # -- every subsystem's epochs, for the timeline's fence --------------------------------------
    # `{(subsystem, unit): epoch}` from every `<sub>/epoch/<unit>` row — the one scan of the WHOLE store the
    # console makes, and it made it on every `GET /events`: a thousand cameras, a page polling every three
    # seconds, ten operators — thousands of reads a second to the store, the leases' CAS queueing behind
    # them (the review's second pass, major). Cached for `EPOCH_CACHE` seconds of monotonic time, like the
    # directory: an epoch that changed inside the window shows as current for those seconds and fenced on
    # the next refresh, which is the lag the timeline already has from the resources' side.
    EPOCH_CACHE = 3.0

    #
    # One row that does not parse is skipped, not the whole answer: it was a `ValueError` out of the handler and the
    # page got no reply at all (the review's third pass, minor) — its unit's events then stand as their resource
    # marked them, as in `epochs_of`. A store that does not answer leaves the last map in place and says so
    # (`epochs_stale`, and `epochs: "cached"` in the reply): fenced by what was known a moment ago beats no timeline.
    epochs_stale = False

    def epochs(self) -> dict:
        now = self.clock()
        if now - self._epochs[0] >= self.EPOCH_CACHE:
            vars_ = self.ctl.vars
            try:
                paths = [p for p in vars_.list("") if "/epoch/" in p]
                out = {}
                for p in paths:
                    try:
                        out[(p.split("/")[0], p.rsplit("/", 1)[1])] = current_epoch(vars_, p)
                    except (ValueError, KeyError, TypeError):
                        log.warning("%s: epoch row %s does not parse: its events are not fenced", self.spec.name, p)
            except OSError as e:
                log.warning("%s: the store did not answer the epochs (%s): the timeline is fenced by the last ones read", self.spec.name, e)
                self.epochs_stale = True
                return self._epochs[1]
            self._epochs, self.epochs_stale = (now, out), False
            self.epoch_scans += 1
        return self._epochs[1]

    # The epochs of the units IN an answer — a camera's, or one unit's: a handful of rows read by name, no scan,
    # and read now, so a fence that fell a moment ago shows. `pairs` is `{(subsystem, unit)}`.
    def epochs_of(self, pairs) -> dict:
        out = {}
        for sub, unit in pairs:
            try:
                e = current_epoch(self.ctl.vars, f"{sub}/epoch/{unit}")
            except (ValueError, KeyError, TypeError, OSError):
                continue                                 # no epoch row, a torn one, or no store: the events stand as their resource marked them
            if e:
                out[(sub, unit)] = e
        return out

    # Every worker whose assignment lists the unit, joined with `+` — a reassignment window shows as both.
    # Compared against the placement row in `/where`.
    def where(self, uid) -> str | None:
        hits = sorted(w for w, units in self.directory().items() if str(uid) in units)
        return "+".join(hits) if hits else None                       # a reassignment window shows as both

    # -- metrics ------------------------------------------------------------------------------
    # Prometheus text, all prefixed with the subsystem name: `<p>_workers_live`;
    # `<p>_worker_headroom{worker,server}` per live worker and the total `<p>_headroom` (what the autoscaler
    # sums); `<p>_worker_load{worker}` = `1 − headroom/capacity` per live worker (assigned/capacity: what a
    # target-value policy scales on); `<p>_epoch_conflicts{worker}` counter from every heartbeat;
    # `<p>_failover_seconds{kind="worst"}`; `<p>_resources_live`; and `<p>_<running_gauge>` — the count of
    # status entries in phase `running` on live workers (`vms_cameras_running`). The page reads two of
    # these for its status line.
    # The servers this subsystem runs on, as the placement sees them: every server a worker heartbeats from
    # or a resource heartbeats from — the archive root its workers say they record into (on a cluster the
    # value of Nomad's `meta.archive`, the label the scheduler placed by), the state of its resource (`live`,
    # `silent`, `unknown`), its workers with load and capacity, and whether the controller would place
    # there now, with the reason when it would not.
    # What one subsystem can say about a machine that is about to stop: how many of ITS units are still
    # assigned there, whether anything it holds would be stranded by the stop, and — for a subsystem whose
    # workers keep something unwritten — how deep that is. The Mount composes these into one answer,
    # because an upgrade is a question about a server and a server carries several subsystems.
    #
    # `safe` is the whole point of the route: an upgrade script polls a CONDITION instead of sleeping and
    # hoping. Nothing here decides anything; it reports.
    def drain_state(self, server: str = "") -> dict:
        ctl, now = self.ctl, self.wall()
        server = server or ctl.draining()
        if not server:
            return {"draining": "", "subsystem": ctl.spec.name}
        here = [w for w in heartbeats(ctl.objects, ctl.sub.name + "/") if ctl.server_of(w) == server]
        units = sum(len(ctl.assignment(w).units) for w in here)
        strand = ctl.would_strand(server)
        # Nothing waits on this machine to be moved somewhere: what a worker wrote is wherever it wrote it — a
        # recorder's footage in its volume, closed when the writer was closed. No units left is the whole answer.
        return {"draining": server, "subsystem": ctl.spec.name, "workers": sorted(here),
                "units": units, "would_strand": strand, "safe": units == 0}

    def servers(self) -> dict:
        ctl, now = self.ctl, self.wall()
        out: dict[str, dict] = {}
        for w, hb in heartbeats(ctl.objects, ctl.sub.name + "/").items():
            s = out.setdefault(hb.extra.get("server", "?"), {"archive": None, "resource": "unknown", "workers": []})
            if hb.extra.get("archive"):
                s["archive"] = hb.extra["archive"]
            s["workers"].append({"worker": w, "load": ctl.load(w), "capacity": ctl.capacity_of(w), "labels": hb.extra.get("labels", ""),
                                 # WHERE this worker is, in whatever the spec counts places in (`place_by`): the server
                                 # for almost everyone, the volume for the recorder. The page needs it to offer the
                                 # archives that exist when a recording is created — `home` names one of these.
                                 "place": ctl.place_of(w),
                                 "state": "live" if is_live(ctl.sub.name, hb.ts, now, self.lost_after) else "stale", "idle_by_policy": False})
        for w in ctl.idle_by_policy(list(heartbeats(ctl.objects, ctl.sub.name + "/"))):    # servers: distinct — one worker per server carries units
            for s in out.values():
                for row in s["workers"]:
                    if row["worker"] == w:
                        row["idle_by_policy"] = True
        for server in resources_seen(ctl.objects):
            out.setdefault(server, {"archive": None, "resource": "unknown", "workers": []})
        drains = ctl.draining()
        for server, s in out.items():
            s["draining"] = server == drains
            s["resource"] = ctl.resource_state(server, self.lost_after)
            s["requires_resource"] = ctl.spec.requires == "resource"
            s["placeable"] = not (s["requires_resource"] and s["resource"] == "silent") and not s["draining"]
            s["why"] = (f"server {server} draining" if s["draining"] else
                        f"resource on {server} silent" if not s["placeable"] else None)
            s["workers"].sort(key=lambda x: x["worker"])
        return {"policy": ctl.policy(), "servers": dict(sorted(out.items()))}

    # EVERY NUMBER OF A HEARTBEAT OR OF THE PASS REPORT HERE IS READ THROUGH `n`, `rn` OR `r` (the review's seventh
    # pass, part 2): read bare — `int(headroom)`, `float(space.full)`, `float(ts)` — one word in one field raised, and
    # the whole page of the subsystem's metrics was gone, every alert with it. `SpecController._number` had closed it
    # for placement; the page had not. A field that is a word (or `nan`, `inf`) is read as not said — 0, or -1 for an
    # age — counted once per object and field (`rows.number`), and the rest of the page stands.
    def metrics_text(self) -> str:
        p = self.spec.name
        hbs = heartbeats(self.ctl.objects, p + "/"); now = self.wall()
        live = {w: hb for w, hb in hbs.items() if is_live(p, hb.ts, now, self.lost_after)}
        res = resources_seen(self.ctl.objects)
        hk = self.ctl.sub.heartbeat_key
        failover = self.ctl.failover_seconds()

        def n(w: str, field: str, kind=float, default=0):                # a worker's field
            return number(f"{hk(w)}#{field}", hbs[w].extra.get(field), kind, default)

        def rn(server: str, field: str, value, kind=float):               # a resource's field
            return number(f"platform/resources/{server}/heartbeat#{field}", value, kind)
        lines = [f"# TYPE {p}_workers_live gauge", f"{p}_workers_live {len(live)}",
                 f"# TYPE {p}_worker_headroom gauge",
                 *[f'{p}_worker_headroom{{worker="{label(w)}",server="{label(hb.extra.get("server", "?"))}"}} {n(w, self.spec.headroom_from, int)}' for w, hb in live.items()],
                 f"{p}_headroom {sum(n(w, self.spec.headroom_from, int) for w in live)}",
                 f"# TYPE {p}_worker_load gauge",              # assigned / capacity: what a target-value policy scales on
                 # …over the workers that ARE a place. A worker holding no place (`place_of` empty) is a
                 # spare: it carries nothing and reports zero capacity, which this formula would read as
                 # fully loaded — and a target-value policy would then scale out for ever, one spare
                 # demanding the next. A spare is counted below instead, as what it is.
                 *[f'{p}_worker_load{{worker="{label(w)}"}} {1 - n(w, self.spec.headroom_from, int) / max(1, n(w, self.spec.capacity_from, int, 1)):.3f}'
                   for w in live if self.ctl.place_of(w) != ""],
                 f"# TYPE {p}_spare_workers gauge",            # running, holding no place, ready to take one
                 f'{p}_spare_workers {sum(1 for w in live if self.ctl.place_of(w) == "")}',
                 f"# TYPE {p}_epoch_conflicts counter",
                 *[f'{p}_epoch_conflicts{{worker="{label(w)}"}} {n(w, "conflicts", int)}' for w in hbs],
                 # MEASURED, NOT ONLY SAID (the review's eighth pass, found by the coordinator): `worst` was the number the
                 # console was built with — on a cluster nothing, 0.0 after any failover. Each worker's last failover
                 # is measured from what its instances wrote (`SpecController.failover_seconds`: the start of this
                 # instance less the last heartbeat of the one before), said per worker as `last`, and `worst` is the
                 # largest of those and of the number the console was given (a drill's datasheet figure).
                 f"# TYPE {p}_failover_seconds gauge",
                 f'{p}_failover_seconds{{kind="worst"}} {max([self.worst_failover, *failover.values()])}',
                 *[f'{p}_failover_seconds{{kind="last",worker="{label(w)}"}} {s}' for w, s in sorted(failover.items())],
                 f"# TYPE {p}_resources_live gauge", f"{p}_resources_live {sum(1 for hb in res.values() if is_live('platform', float(hb['ts']), now, self.lost_after))}",
                 # What the readers of heartbeats skipped and measured (the review's second pass, M6, M9): objects that did
                 # not parse, since this process started; and the furthest a heartbeat's clock has been AHEAD of this
                 # one's — at `FUTURE_TOLERANCE` such a worker stops counting as live.
                 f"# TYPE {p}_heartbeats_garbled counter", f"{p}_heartbeats_garbled {GARBLED.get(p, 0)}",
                 f"# TYPE {p}_resource_heartbeats_garbled counter", f"{p}_resource_heartbeats_garbled {GARBLED.get('platform', 0)}",
                 f"# TYPE {p}_heartbeat_skew_seconds_max gauge", f"{p}_heartbeat_skew_seconds_max {round(SKEW_MAX.get(p, 0.0), 1)}",
                 f"# TYPE {p}_heartbeat_skew_seconds_min gauge", f"{p}_heartbeat_skew_seconds_min {round(SKEW_MIN.get(p, 0.0), 1)}",
                 f"# TYPE {p}_{self.spec.running_gauge} gauge",
                 f"{p}_{self.spec.running_gauge} {sum(1 for hb in live.values() for s in hb.status if s.get('phase') == 'running')}"]
        # How far behind the copy the layer above reads is. The controller publishes every pass and has no
        # port; this is read from the store, so a failing publish shows up here as a number that climbs,
        # rather than only as a log line on a host nobody is looking at. `-1` distinguishes "never
        # published" from "published a moment ago" — a gauge that is 0 for both would hide a cluster whose
        # controller has never once succeeded.
        age = self.ctl.snapshot_age(now)
        lines += [f"# TYPE {p}_snapshot_age_seconds gauge",
                  f"{p}_snapshot_age_seconds {-1 if age is None else round(age, 1)}"]
        # Each server's disk, from its resource's heartbeat: how full, and how many bytes the watermark was asked
        # to free and could not (feedback BM). The second is the state nothing mends by itself — everything on
        # the floor, or nothing of the subsystems' on that disk at all — and it used to be a line in a log.
        lines += [f"# TYPE {p}_resource_full gauge",
                  *[f'{p}_resource_full{{server="{label(s)}"}} {round(rn(s, "space.full", (hb.get("space") if isinstance(hb.get("space"), dict) else {}).get("full")), 3)}'
                    for s, hb in sorted(res.items())],
                  f"# TYPE {p}_resource_short_bytes gauge",
                  *[f'{p}_resource_short_bytes{{server="{label(s)}"}} {rn(s, "short", hb.get("short"), int)}' for s, hb in sorted(res.items())]]
        # The requests each resource holds for the readers of its events (`/events/wait`, `longpoll.Watch.counts`): held
        # now, and since it started — held, refused for want of room, replaced by their own client's next. `full`
        # climbing is an evaluator back on its two-second pass, and nothing else would say so (the review's seventh pass).
        waits = {s: hb["waits"] for s, hb in sorted(res.items()) if isinstance(hb.get("waits"), dict)}
        lines += [f"# TYPE {p}_resource_waits gauge",
                  *[f'{p}_resource_waits{{server="{label(s)}"}} {rn(s, "waits.waiting", w.get("waiting"), int)}' for s, w in waits.items()]]
        for key in ("held", "full", "replaced"):
            lines += [f"# TYPE {p}_resource_waits_{key}_total counter",
                      *[f'{p}_resource_waits_{key}_total{{server="{label(s)}"}} {rn(s, "waits." + key, w.get(key), int)}' for s, w in waits.items()]]
        # What each resource could not read and could not copy (the review's eighth pass): the rows of its tables that do
        # not parse, by table, and whether its watermark acts on a row that does not (`rows_garbled`, `space_garbled` —
        # in the heartbeat only, a minor); the mirror's buckets a peer did not take and those too big for any; the
        # restore's buckets still with peers and its failures. `restore_left` not falling is a replaced disk whose events
        # have not come back; `mirror_too_big` is a bucket copied nowhere.
        said = lambda hb, key: hb.get(key) if isinstance(hb.get(key), dict) else {}
        lines += [f"# TYPE {p}_resource_rows_garbled counter",
                  *[f'{p}_resource_rows_garbled{{server="{label(s)}",table="{label(t)}"}} {rn(s, "rows_garbled." + str(t), c, int)}'
                    for s, hb in sorted(res.items()) for t, c in sorted(said(hb, "rows_garbled").items(), key=lambda x: str(x[0]))],
                  f"# TYPE {p}_resource_space_garbled gauge",
                  *[f'{p}_resource_space_garbled{{server="{label(s)}"}} {1 if hb.get("space_garbled") else 0}' for s, hb in sorted(res.items())],
                  f"# TYPE {p}_resource_restore_left gauge",
                  *[f'{p}_resource_restore_left{{server="{label(s)}"}} {rn(s, "restore.left", said(hb, "restore").get("left"), int)}' for s, hb in sorted(res.items())],
                  f"# TYPE {p}_resource_restore_failures_total counter",
                  *[f'{p}_resource_restore_failures_total{{server="{label(s)}"}} {rn(s, "restore.failed", said(hb, "restore").get("failed"), int)}' for s, hb in sorted(res.items())],
                  f"# TYPE {p}_resource_mirror_failures_total counter",
                  *[f'{p}_resource_mirror_failures_total{{server="{label(s)}"}} {rn(s, "mirror.failed", said(hb, "mirror").get("failed"), int)}' for s, hb in sorted(res.items())],
                  f"# TYPE {p}_resource_mirror_too_big_total counter",
                  *[f'{p}_resource_mirror_too_big_total{{server="{label(s)}"}} {rn(s, "mirror.too_big", said(hb, "mirror").get("too_big"), int)}' for s, hb in sorted(res.items())]]
        # The controller's pass, from the report it leaves in the store (`SpecController.pass_once`): the
        # controller has no port, and a pass that fails, a unit with nowhere to go and an assignment the rows
        # contradicted used to be numbers nowhere. `-1`: no pass yet, or none that succeeded.
        rep = self.ctl.pass_report() or {}
        rk = f"{p}/controller/pass"
        r = lambda field, kind=float: number(f"{rk}#{field}", rep.get(field), kind)
        ago = lambda field: -1 if (t := number(f"{rk}#{field}", rep.get(field), float, None)) is None else round(now - t, 1)
        lines += [f"# TYPE {p}_reconcile_last_pass_age_seconds gauge",
                  f"{p}_reconcile_last_pass_age_seconds {ago('ts')}",
                  f"# TYPE {p}_reconcile_last_success_age_seconds gauge",
                  f"{p}_reconcile_last_success_age_seconds {ago('last_success')}",
                  f"# TYPE {p}_reconcile_pass_seconds gauge", f"{p}_reconcile_pass_seconds {r('seconds')}",
                  f"# TYPE {p}_reconcile_failures counter", f"{p}_reconcile_failures {r('failures', int)}",
                  f"# TYPE {p}_units_unplaced gauge", f"{p}_units_unplaced {r('unplaced', int)}",
                  f"# TYPE {p}_units_diverged gauge", f"{p}_units_diverged {r('diverged', int)}",
                  f"# TYPE {p}_rows_garbled gauge", f"{p}_rows_garbled {r('garbled', int)}",     # rows that do not parse: units nobody serves (the review's second pass, M7)
                  # What a worker says about itself and placement does not read — a person can, now: fenced
                  # (alive, holding nothing), and how often the store did not answer it.
                  f"# TYPE {p}_worker_fenced gauge",
                  *[f'{p}_worker_fenced{{worker="{label(w)}"}} {1 if str(hb.extra.get("fenced")).lower() == "true" else 0}' for w, hb in hbs.items()],
                  f"# TYPE {p}_worker_store_errors counter",
                  *[f'{p}_worker_store_errors{{worker="{label(w)}"}} {n(w, "store_errors", int)}' for w in hbs],
                  # Units a worker is recording past their lease's end, the store silent (feedback BK): data goes
                  # on, actions wait. Not zero for long is a store that is away, seen from the workers' side.
                  f"# TYPE {p}_worker_unconfirmed gauge",
                  *[f'{p}_worker_unconfirmed{{worker="{label(w)}"}} {n(w, "unconfirmed", int)}' for w in hbs],
                  f"# TYPE {p}_worker_pass_failures counter",
                  *[f'{p}_worker_pass_failures{{worker="{label(w)}"}} {n(w, "pass_failures", int)}' for w in hbs],
                  # Slot rows this worker could not read while looking for one (`contract.read_slot`; the review's
                  # sixth pass): each is a name nobody can take or be seen holding — capacity lost without a word.
                  f"# TYPE {p}_worker_slots_garbled counter",
                  *[f'{p}_worker_slots_garbled{{worker="{label(w)}"}} {n(w, "slots_garbled", int)}' for w in hbs]]
        # …and the rows of the other tables a worker could not read, by table (`rows.Table`; the review's seventh
        # pass, a minor: `holds_garbled` was in the heartbeat and not here) — `holds_garbled`, a place nobody can take;
        # `assignments_garbled`; a recorder's `volumes_garbled`, `keeps_garbled`. Rows, each once until it parses
        # again — not reads.
        tables = garbled_by_table()
        for name in sorted(tables):
            field = f"{name}s_garbled"
            if field != "slots_garbled":                                  # above, under the name it always had
                lines += [f"# TYPE {p}_worker_{field} counter",
                          *[f'{p}_worker_{field}{{worker="{label(w)}"}} {n(w, field, int)}' for w in hbs]]
        # …and this console's own: the rows of this subsystem IT could not read (the requests it files, the keeps it
        # shows, the fields of heartbeats read as not said just above), by table.
        lines += [f"# TYPE {p}_console_rows_garbled counter",
                  *[f'{p}_console_rows_garbled{{table="{label(name)}"}} {tables[name].get(p, 0)}' for name in sorted(tables)]]
        # The sweep's backlog, for subsystems that have blobs to collect. Two cheap reads — a prefix
        # listing and one row — deliberately NOT `blobs_referenced()`, which walks every unit's row: a
        # gauge scraped every fifteen seconds must not cost a full scan of the configuration.
        if any(f.type == "blob" for f in self.spec.fields.values()):
            from .spec import _sweep_list
            marked = _sweep_list(self.ctl.vars.get(self.ctl.sub.sweep_key())[0])[0]   # a list nobody can read is none
            lines += [f"# TYPE {p}_blobs_total gauge",
                      f"{p}_blobs_total {len(self.ctl.objects.list(self.ctl.sub.blobs_prefix()))}",
                      f"# TYPE {p}_blobs_marked gauge",
                      f"{p}_blobs_marked {len(marked)}"]
        if self.metrics_extra is not None:
            lines += list(self.metrics_extra())                # the subsystem's own numbers, in its own words
        return "\n".join(lines) + "\n"

    # -- writes ---------------------------------------------------------------------------------
    # `ctl.create(body)` → 201 with the row plus `worker: None` (placed by the controller's next pass, never
    # by the console); `Refused` → 400 `{detail, error}`. Under `key`, the new id goes into the claim first,
    # and a claim taken over creates under the id it names (`IdempotencyKeys.reserve`).
    #
    # WHO MADE IT AND WHO CHANGED IT (the review's third pass, minor): the journal knew who deleted a unit and not
    # who created or edited it. `unit.created` and `unit.changed` — with the NAMES of the fields, never their values
    # (a password is one of them) — are written after the write, because a unit that exists is its own evidence
    # that it was made, and an edit that failed changed nothing. `unit.deleted` is the other way round (`delete`).
    def create(self, body: dict, key: str | None = None, user: str = "operator") -> tuple[int, dict]:
        try:
            r = self.ctl.create(body, uid=self.seen.reserved(key) if key else None,
                                reserve=(lambda uid: self.seen.reserve(key, uid)) if key else None)
            self.journal.say("unit.created", of=self.spec.name, target=str(r.get("id")), user=user,
                             fields=",".join(sorted(str(k) for k in body)))
            # Masked, like every other way out. This reply is ALSO what `IdempotencyKeys` stores to answer a
            # retry, so an unmasked one puts a second copy of the secret in the config store under a key
            # nobody thinks to look at — which is exactly how this was got wrong the first time.
            return 201, {**mask_secrets([r])[0], "worker": None}      # placed by the controller's next pass, never by the console
        except Refused as e:
            return 400, {"detail": str(e), "error": str(e)}
        except TooLarge as e:
            return 413, {"detail": str(e), "error": str(e)}
        except ClaimLost as e:                                        # taken over while this console stood still: the
            return 409, {"detail": str(e), "error": "taken over"}     # other one answers the key, and nothing was written
        except Conflict as e:
            if key is None:
                raise
            # Reserved, then stood still: the console that took the claim over created under the reserved id first,
            # and this row's create-only write lost to it. One unit, and it is the other console's answer.
            return 409, {"detail": f"the request was taken over by another console, which created it ({e})", "error": "taken over"}

    # `ctl.update` → 200 with the row; `Refused` → 400; `TooLarge` → 413; `KeyError` → 404.
    #
    # A row's `cam` is fixed at its creation (`SpecController.update`, the review's fourth pass): the gate checked the
    # grant on the camera the row names now, and a PUT that changed it moved the unit past that check.
    def update(self, uid, body: dict, user: str = "operator") -> tuple[int, dict]:
        try:
            row = self.ctl.update(uid, body)
            self.journal.say("unit.changed", of=self.spec.name, target=str(uid), user=user,
                             fields=",".join(sorted(str(k) for k in body)), revision=row.get("revision"))
            return 200, mask_secrets([row])[0]
        except Refused as e:
            return 400, {"detail": str(e), "error": str(e)}
        # 413, and to the person who typed it. The store's ceiling used to be a number in a document and a
        # surprise in production; now the edit that does not fit is refused at the console, with the size
        # and the limit in the sentence, before anything is written.
        except TooLarge as e:
            return 413, {"detail": str(e), "error": str(e)}
        except KeyError:
            return 404, {"detail": "no such unit", "error": "no such unit"}

    # `PUT /<rows>/<id>/<field>` with the bytes as the body: the one route that takes something other than
    # JSON, because the thing it takes is not JSON. The bytes go to the object store first and the row gets
    # the digest — which bumps `revision`, which is what makes the worker pick the new lump up. Nothing
    # here is a new mechanism; the digest is what lets the old one see a change.
    def put_blob(self, uid, field: str, data: bytes, user: str = "operator") -> tuple[int, dict]:
        f = self.spec.fields.get(field)
        if f is None or f.type != "blob":
            return 404, {"detail": f"{field} is not a blob field", "error": "no such blob field"}
        if self.ctl.unit(uid) is None:
            return 404, {"detail": "no such unit", "error": "no such unit"}
        try:
            d = self.ctl.put_blob(data)                       # 1. the object
            row = self.ctl.update(uid, {field: d})            # 2. the row that names it
        except Refused as e:
            return 400, {"detail": str(e), "error": str(e)}
        except TooLarge as e:
            # The blob is bigger than the STORE will hold — which is the one case where changing the store
            # is the answer, because a blob is exactly the class of data an object store exists for.
            return 413, {"detail": f"{e} — a blob is what an object store is for: OBJECTS=s3+https://… "
                                   f"holds this, variables:// does not", "error": str(e)}
        self.journal.say("unit.changed", of=self.spec.name, target=str(uid), user=user, fields=field,
                         revision=row.get("revision"), digest=d)
        return 200, {**mask_secrets([row])[0], field: d, "bytes": len(data)}

    # 404 if the unit is absent; else `ctl.delete(uid)` and 200 `{deleted: uid}`.
    #
    # …and WHO. A deleted unit leaves a tombstone and a revision; neither is a name (feedback BN).
    #
    # Said BEFORE the delete (the review's second and third passes): after it, a console that died between the two
    # left a unit gone and no line — and a deleted unit, unlike a created one, is not there to be its own evidence.
    # Before, the worst is a line for a delete that then failed, and that is followed by `unit.delete.failed`.
    def delete(self, uid, user: str = "operator") -> tuple[int, dict]:
        if self.ctl.unit(uid) is None:
            return 404, {"detail": "no such unit", "error": "no such unit"}
        # `of` and `target`, not `subsystem` and `unit`: those two are the LINE's own — who wrote it — and a field
        # of the same name would answer for it in every reader.
        self.journal.say("unit.deleted", of=self.spec.name, target=str(uid), user=user)
        try:
            self.ctl.delete(uid)
        except Exception as e:
            self.journal.say("unit.delete.failed", of=self.spec.name, target=str(uid), user=user, error=str(e))
            raise
        return 200, {"deleted": uid}

    # An operator's observation. 503 if there is no resource on this server; 400 unless the body names `cam`
    # or `unit`. Appends `{kind: mark, user, note, cam|unit}` at `wall()` to the console's own bucket —
    # `cam` is stored as an int because it is the field the index joins on — and returns 201 `{subsystem:
    # "console", unit: <instance>, bucket: <relative path>}`. It is the console's event, into
    # `console/<instance>/e1/…` on this server's resource, never a worker's bucket.
    def mark(self, body: dict, user: str) -> tuple[int, dict]:
        if self.marks is None:
            return 503, {"detail": "no resource on this server to write marks into", "error": "no resource on this server to write marks into"}
        if "cam" not in body and "unit" not in body:
            return 400, {"detail": "a mark names a unit", "error": "a mark names a unit"}
        fields = {"user": user, "note": str(body.get("note", ""))}
        if "cam" in body:
            fields["cam"] = int(body["cam"])                          # the field the index joins on
        else:
            fields["unit"] = str(body["unit"])
        path = self.marks.append(self.wall(), "mark", **fields)
        return 201, {"subsystem": "console", "unit": self.instance, "bucket": os.path.relpath(path, self.marks_root)}

    # -- the handler ----------------------------------------------------------------------------
    # Builds and returns the request handler class bound to this console.
    #
    # #### `class H(BaseHTTPRequestHandler)` (nested)
    # - `log_message` — silenced.
    # - `_send(status, body, raw=False)` — JSON (or raw text) with `Content-Type` and `Content-Length`.
    # - `_body()` — the JSON request body, `{}` if empty.
    # - `_uid()` — the id segment (`path_id`: the one after the family, the one the gate checked) through `spec.parse_id`.
    # - `_extra(method, path, q) -> bool` — call the subsystem's `extra`; `None` means not ours (return
    #   False). `()` means the extra wrote the reply itself (`send_file`). `(status, dict|list)` is sent as
    #   JSON; `(status, bytes)` raw; `(status, bytes, headers)` raw with headers.
    # - `do_GET` — routes, in order:
    #   - `GET /` or `/index.html` — `console.html`.
    #   - `GET /spec` — `describe()`.
    #         - `GET /<rows>` — `{rows: ctl.read_model(lost_after), configured: ctl.units()}`: the
    #       heartbeats' view over the configured rows.
    #         - `GET /where/<id>` — `{worker, reason}` from the stored placement (404 with nulls if
    #       unplaced), plus `directory` (the assignments' answer) and `scans`.
    #   - `GET /resources` — every resource heartbeat with `state: live | silent` by `lost_after`.
    #   - `GET /servers` — `servers()`: per server, `archive` (what its workers record into — Nomad's `meta.archive`
    #     on a cluster), `resource` (`live | silent | unknown`), `workers`, `placeable` and `why`.
    #   - `GET /unplaceable` — `ctl.unplaceable()`.
    #         - `GET /events?from&to&cam|unit&kind&subsystem&limit&keep&class` — 503 if no index; else
    #       `current_epochs` from every `<sub>/epoch/*` row (`epochs`, cached `EPOCH_CACHE` seconds) and
    #       `index.query`; with `cam` or `unit`, the query runs unfenced and the answer is fenced by the epochs of
    #       the units in it (`epochs_of`, `refence`), read by name. A numeric `unit` is
    #       treated as `cam`; a non-numeric one is passed as `unit`. `keep` is "newest" (default) or
    #       "oldest", 400 if it is neither; the reply carries `truncated` when the window did not fit.
    #   - `GET /metrics` — `metrics_text()` as `text/plain`.
    #   - otherwise `_extra("GET", …)`; then 404 `{detail, error}`.
    # - `_idem() -> key | None` — for POST: 400 if `Idempotency-Key` is missing or malformed; if `claim`
    #   returns a prior reply, send it and return `None`; else return the key.
    # - `do_POST`:
    #     - `POST /<rows>` (Idempotency-Key required) — `create(body)`; the reply is stored under the key
    #     and sent.
    #         - `POST /marks` (Idempotency-Key required; `X-User` header, default `operator`) — `mark(body,
    #       user)`; stored and sent.
    #   - any other path — `_extra("POST", …)` or 404.
    # - `do_PUT`:
    #         - `PUT /<rows>/<id>` — `update(uid, body)`; `Idempotency-Key` is optional here: if present the
    #       same claim/store dance applies. Any other path is 404.
    # - `do_DELETE`:
    #         - `DELETE /<rows>/<id>` — `delete(uid)`; no idempotency key (a second delete is 404, "gone is
    #       gone"). Any other path is 404.
    def handler(self):
        """The request handler class for this console alone — a Mount with no other subsystems."""
        return Mount(self).handler()

    # -- one request, already stripped of any mount prefix: the routes above -----------------------------
    # THE ID A PATH NAMES — one reading, for the gate and for the route (the review's third pass, blocker 1). The
    # gate read `segs[2]` and the routes the LAST segment: `DELETE /<rows>/1/2` was checked on unit 1 and
    # deleted unit 2, `GET /export/1/2` was checked on 1 and served 2. Now a family that takes an id takes
    # exactly one — `/<family>/<id>` — and anything after it is 404 before the gate is asked, except the one
    # route with a third segment, `PUT /<rows>/<id>/<blob>`. Every route reads its id through `path_id`, the same
    # function the gate reads it through.
    #
    # The families: the rows, `UNIT_ROUTES` (the id IS a unit: `/where`, and a subsystem's — `/timeline`,
    # `/export`, `/whep`) and `ID_ROUTES` (an id that is not a unit: a keep, a volume). `NO_UNIT`: paths inside a
    # unit family that name something else — a live session is not a unit.
    ID_ROUTES: tuple = ()
    NO_UNIT: tuple = ()

    def route_id(self, method: str, path: str) -> tuple[str | None, str | None]:
        """`(family, id)` when the path is `/<family>/<id>` of a family that takes one, else `(None, None)`.
        `NoSuchRoute` for a path with more after the id."""
        if self.NO_UNIT and path.startswith(self.NO_UNIT):
            return None, None
        segs = path.split("/")
        if len(segs) < 3 or segs[1] not in (self.spec.rows, *self.UNIT_ROUTES, *self.ID_ROUTES):
            return None, None
        if len(segs) > 3 and not (method == "PUT" and segs[1] == self.spec.rows and len(segs) == 4 and segs[3]):
            raise NoSuchRoute(f"{path}: one id after /{segs[1]}/, and nothing after it")
        return segs[1], path_id(path) or None

    def _uid(self, path):
        return self.spec.parse_id(path_id(path))

    # What a gated caller may LOOK at: `(unit, labels) -> bool`, or None when this console is open. A list is
    # not a route that names a unit, so the gate lets in anybody with any grant — and the list then shows them
    # only what their grants cover. `"*"` asks about no unit in particular: only a grant on the whole cluster
    # answers yes.
    def _visible(self, h):
        try:
            access = self.gate.access()
        except Denied:
            return lambda unit, labels: False
        if access is None:
            return None
        try:
            payload = self.gate.payload(h.headers, access)
        except Denied:
            return lambda unit, labels: False
        return lambda unit, labels: access.may(payload, "view", unit, labels)

    # What a route needs: `(capability, unit, labels)`.
    #
    #   view    every GET, and whatever a subsystem says changes nothing though it is a POST (`VIEW_POSTS` —
    #           the VMS: asking for a live stream)
    #   edit    acting through the system without changing what it IS — a mark, a command to a device, a
    #           backfill, a keep
    #   admin   everything else that writes: units, volumes, policy, drain
    #
    # The unit is named when the path names one; a grant may be for one unit, for units with given labels, or
    # for the whole cluster, and a route that names no unit needs the last (to act) or any grant at all (to look).
    # A recording is its camera's: the grant is on the camera.
    #
    # The three lists are the platform's own routes; a subsystem adds its own to the console it builds
    # (`vms/console.py`), because only it knows that a backfill acts and a volume configures.
    EDIT_ROUTES: tuple = ("/marks", "/requests")
    UNIT_ROUTES: tuple = ("where",)
    VIEW_POSTS: tuple = ()

    # The unit an ACTION names in its body (`unit`, or `cam`): a mark, a command and a keep are about one unit,
    # and an operator granted that unit must be able to make them. The body is read here and put back, so
    # whoever answers the request reads it again as if nobody had.
    #
    # A GET names its unit in the query the same way (`?cam=`, `?unit=`): the device's own footage, the events
    # of one camera. A route that names no unit anywhere is answered to any grant — a list, and the list is cut
    # to what the caller may see; a route that names one in the query is about that unit (the review's second
    # pass, blocker 1: `/segment?cam=7` was "any grant", and the footage of camera 7 went to the guard of camera 3).
    # A body that names two units — `unit` one thing, `cam` another — is refused: the gate would check one and
    # the action would go to the other (the same review, major).
    def _named(self, h, method: str, path: str, q: dict | None = None) -> str | None:
        if method == "GET":
            q = q or {}
            if "unit" in q and "cam" in q and str(q["unit"]) != str(q["cam"]):
                raise Denied(400, "the query names two units: `unit` and `cam` must be the same one, or name one")
            named = q.get("unit", q.get("cam"))
            return str(named) if named not in (None, "") else None
        if method not in ("POST", "PUT") or not path.startswith(self.EDIT_ROUTES):
            return None
        raw = h.rfile.read(int(h.headers.get("Content-Length", 0) or 0))
        h.rfile = io.BytesIO(raw)
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            return None
        if not isinstance(body, dict):
            return None
        if "unit" in body and "cam" in body and str(body["unit"]) != str(body["cam"]):
            raise Denied(400, "the body names two units: `unit` and `cam` must be the same one, or name one")
        named = body.get("unit", body.get("cam"))
        return str(named) if named not in (None, "") else None

    def needs(self, method: str, path: str, named: str | None = None) -> tuple[str, str | None, list]:
        cap = "view" if method == "GET" or (self.VIEW_POSTS and path.startswith(self.VIEW_POSTS)) else \
              "edit" if path.startswith(self.EDIT_ROUTES) else "admin"
        family, pid = self.route_id(method, path)
        in_path = bool(pid) and family in (self.spec.rows, *self.UNIT_ROUTES)
        uid = pid if in_path else named
        if uid is None:
            return cap, None, []
        try:
            row = self.ctl.unit(self.spec.parse_id(uid))
        except (ValueError, KeyError):
            row = None
        if not in_path and row is not None and "cam" in row:
            row = None                                   # a body names the unit the action is ABOUT, not one of this console's rows
        unit = str((row or {}).get("cam") or uid)
        return cap, unit, self._labels(unit, row)

    # The labels a grant is matched against are the labels of the unit the grant is ON. A console whose rows are
    # ABOUT another subsystem's units (a recording is its camera's) says whose they are: `labels_of`, set by
    # whoever builds it. Without it, the row's own.
    labels_of = None

    def _labels(self, unit: str, row: dict | None) -> list:
        if self.labels_of is not None and (row is None or "cam" in row):
            try:
                return list(self.labels_of(unit) or [])
            except Exception:                            # noqa: BLE001 — not found, or the store is away: no labels, so no label grant matches
                return []
        return list((row or {}).get("labels") or [])

    def _extra(self, h, method, path, q):
        # What a subsystem's own routes need to filter a LIST the way this console filters its rows (the product,
        # feedback CG): `h.sees(unit, labels)`, None when the console is open, and `h.labels_for(unit)`.
        h.sees, h.labels_for = self._visible(h), (lambda unit: self._labels(str(unit), None))
        r = self.extra(h, method, path, q) if self.extra else None
        if r is None:
            return False
        if r == ():                                                  # the extra wrote the reply itself (send_file)
            return True
        if len(r) == 2 and isinstance(r[1], (dict, list)):
            h._send(*r)
        elif len(r) == 2:
            h.send_response(r[0]); h.send_header("Content-Length", str(len(r[1]))); h.end_headers(); h.wfile.write(r[1])
        else:
            status, data, headers = r
            h.send_response(status); h.send_header("Content-Length", str(len(data)))
            for k, v in headers: h.send_header(k, v)
            h.end_headers(); h.wfile.write(data)
        return True

    # The claim names the caller (`X-User` — the name the gate proved, where there is a gate) and the body, so a
    # replay by anybody else, or of anything else, is 422 and not the first caller's reply. The body is read here
    # and put back, as `_named` does.
    def _idem(self, h, required: bool = True):
        key = h.headers.get("Idempotency-Key")
        if not key:
            if required:
                h._send(400, {"detail": "Idempotency-Key header is required", "error": "Idempotency-Key required"})
            return None
        raw = h.rfile.read(int(h.headers.get("Content-Length", 0) or 0))
        h.rfile = io.BytesIO(raw)
        try:
            prior = self.seen.claim(key, h.headers.get("X-User", "operator"), raw)
        except Refused as e:
            h._send(400, {"detail": str(e), "error": str(e)}); return None
        except OSError as e:                                             # the store, not the request: a client told 400 does not retry
            h._send(503, {"detail": f"the store did not answer: {e}", "error": "store unavailable"}); return None
        if prior is not None:
            h._send(*prior); return None
        return key

    # The reply, remembered under the key — and sent whether or not it could be remembered. The write HAPPENED:
    # a store that did not take the reply is a log line, not a 503 that sends the client back to make a second
    # camera (the review's second pass, major). The claim stays pending; a retry inside `PENDING_TTL` waits on
    # it, and past it takes it over — the one window left, and it needs the store to fail twice.
    def _remember(self, key: str | None, resp: tuple) -> None:
        if not key:
            return
        try:
            self.seen.store(key, resp)
        except OSError as e:
            log.warning("%s: the reply to %s was sent but not remembered under its key: %s", self.spec.name, key, e)
        except ClaimLost as e:
            # The write happened, and then the claim was taken over: the console that took it finds the unit under
            # the id reserved in the claim and answers with it — the same unit. This reply is still the truth.
            log.warning("%s: %s", self.spec.name, e)

    # A write that RAISED under a claimed key: the claim is let go — nothing was written that the key could
    # answer for — and the reply says whose fault it was. The store: 503, which a client retries. Anything
    # else: 500. It used to leave the claim pending and the handler to fall over, and the correct retry got
    # 409 "in flight" until the key aged out a day later (feedback BG).
    def _failed(self, key: str | None, e: Exception) -> tuple[int, dict]:
        if key:
            self.seen.release(key)
        if isinstance(e, OSError):
            return 503, {"detail": f"the store did not answer: {e}", "error": "store unavailable"}
        log.error("%s: a write failed: %s", self.spec.name, e)
        return 500, {"detail": str(e), "error": "the write failed"}

    # THE DOOR IN: `/session`. The gate asks for a token; this is how a person's BROWSER comes to carry one.
    #
    #   GET     is this console gated, who am I here, and where does one log in (`LOGIN_URL` — the domain's
    #           signer; a console issues no tokens and keeps no passwords, М12 Lesson 4)
    #   POST    `{token}` — checked exactly as the gate would check it, and set as a cookie the page's script
    #           cannot read (`access.session_cookie`), for as long as the token lives
    #   DELETE  the cookie goes
    #
    # The password never comes here. The page sends it to the domain's login door and brings back only the
    # token: N consoles that never see a password are N places it cannot be taken from.
    def session(self, h, method: str) -> None:
        try:
            access = self.gate.access()
        except Denied as e:
            return h._send(e.status, {"detail": e.why, "error": "denied"})
        login = os.environ.get("LOGIN_URL") or None
        if method == "DELETE":
            self.gate.close_glass(h.headers)
            h._extra_headers = (("Set-Cookie", session_cookie("", 0)), ("Set-Cookie", session_cookie("", 0).replace(COOKIE, GLASS_COOKIE, 1)))
            return h._send(200, {"gated": access is not None, "user": None})
        if access is None:
            return h._send(200, {"gated": False, "user": h.headers.get("X-User", "operator"), "login": None})
        secure = (h.headers.get("X-Forwarded-Proto", "") == "https")
        body = h._body() if method == "POST" else {}
        if method == "POST" and isinstance(body.get("glass"), dict):
            # The emergency entry (`Gate.open_glass`): who, why and the one local password. What comes back is
            # a session in this process's memory, carried by a cookie of its own.
            g = body["glass"]
            peer = str(getattr(h, "client_address", ("?",))[0])
            try:
                sid, payload = self.gate.open_glass(str(g.get("who", "")), str(g.get("why", "")), str(g.get("password", "")),
                                                    addr=caller_addr(h.headers, peer), local=is_local(peer))
            except Denied as e:
                if e.retry_after is not None:                            # the emergency door's pace: when the next turn is
                    h._extra_headers = (("Retry-After", str(max(1, int(e.retry_after + 0.999)))),)
                return h._send(e.status, {"detail": e.why, "error": "denied",
                                          **({"retry_after": round(e.retry_after, 1)} if e.retry_after is not None else {})})
            h._extra_headers = (("Set-Cookie", session_cookie(sid, float(payload.get("exp", 0)) - self.wall(), secure).replace(COOKIE, GLASS_COOKIE, 1)),)
            return h._send(200, {"gated": True, "user": f"break-glass({payload.get('who')})", "until": payload.get("exp"), "login": login})
        token = (body.get("token") if method == "POST" else token_of(h.headers)) or ""
        try:
            payload = access.who(token) if token else (self.gate.payload(h.headers, access) if method == "GET" else None)
        except Denied as e:
            if method == "POST":
                return h._send(e.status, {"detail": e.why, "error": "denied"})
            payload = None                               # a cookie that has expired: not logged in, and not an error
        if payload is None:
            return h._send(200 if method == "GET" else 400, {"gated": True, "user": None, "login": login})
        if method == "POST":
            h._extra_headers = (("Set-Cookie", session_cookie(token, float(payload.get("exp", 0)) - self.wall(), secure)),)
        user = f"break-glass({payload.get('who')})" if payload.get("via") == "break-glass" else payload.get("sub")
        return h._send(200, {"gated": True, "user": user, "until": payload.get("exp"), "login": login})

    # THE BODY, READ ONCE, BOUNDED, AFTER THE CALLER IS KNOWN (the review's fifth pass, major). `Content-Length` is
    # checked before a byte is read: past `MAX_BODY` (a blob's bytes: `MAX_BLOB`) it is 413, and the connection is
    # closed rather than drained; a length that is not a number is 400. What is read is read here, under a deadline
    # of its own — `CONSOLE_TIMEOUT` and a second for every `BODY_RATE` bytes — and put back as memory, so `_named`,
    # `_idem` and every route read it as if nobody had. A body that does not arrive in time is 408. True: read, go
    # on; False: refused, and the reply sent. The reading itself is `read_body` below the class: every door's.
    def read_body(self, h, limit: int) -> bool:
        return read_body(h, limit)

    # THE CAMERAS A ROW NAMES, THROUGH ANY FIELD (the review's fifth pass, major). `cam` was made fixed, and the gate
    # checks the camera in it — but a row can name a camera through other fields: a scan's `rec` is a recording, and
    # its footage is that recording's camera's; a scenario's `when` and `then` name the cameras it watches and acts
    # on. `PUT /detjob/jobs/1-motion-1 {"rec": "2"}` with `admin` on camera 1 pointed a scan at camera 2's archive,
    # and a scenario edited under a grant that matched its PLACEMENT labels sent commands to camera 12. A subsystem
    # whose rows do that says so: `cams_of(row) -> {camera, …}`, every camera the row reaches, `"*"` for "any camera"
    # (a trigger with no unit) — which only a grant on the whole cluster covers. A write to such a row is admitted
    # only when the caller holds the route's capability on every camera of the row as it IS and as it WILL BE: the
    # old value, so a row cannot be taken from a camera one may not touch; the new one, so it cannot be pointed at
    # one. A row that names no camera of its own (`cam`) — a scenario — IS its cameras: an edit or a delete of it is
    # asked of them alone, and its own labels, which say where its evaluator runs, grant nothing on it
    # (`is_its_units`). Creating one still asks for a grant on the whole cluster, as every create here does.
    cams_of = None
    # …AND THE CAMERAS A CHANGE REACHES (the review's sixth pass, major). `cams_of` reads one row; some edits are about
    # two: a camera whose `source` moves to another channel of its recorder shows that channel's picture under this
    # camera's name, to this camera's viewers and into its archive — `PUT /cameras/1 {"source": "…/ch/2"}` with
    # `admin` on camera 1 was 200. `moved_cams(old, new) -> {camera, …}`: every camera the CHANGE touches beyond the
    # row itself — for the VMS, every camera of the device it leaves and of the device it moves to, when the device or
    # the channel changes (`vms/console.py`, `source_cams`). Empty for an edit that moves nothing: renaming a camera
    # asks for nothing more than it did.
    moved_cams = None
    # …AND THE CAMERAS AN ACTION REACHES (the review's seventh pass, major). A route whose unit is in the body
    # (`/requests`) was asked about that unit alone — and a command goes to a DEVICE: `edit` on camera 1 of a
    # sixteen-channel recorder pulsed its relays and turned it to a preset, the lock of camera 2's zone among them.
    # `body_cams(path, body) -> {camera, …}`: every camera the action in the body reaches beyond the unit it names — for
    # the VMS, every camera of the device, unless the device binds the port or the preset to a channel (`vms/console.py`,
    # `command_cams`). Asked after the body, for the route's capability, as the unit is.
    body_cams = None

    def _row_written(self, method: str, path: str):
        """`(old row or None, True)` for a write to one of this console's rows — `(None, False)` for anything else."""
        if (self.cams_of is None and self.moved_cams is None) or method not in ("POST", "PUT", "DELETE"):
            return None, False
        rows_path = "/" + self.spec.rows
        if (path != rows_path and not path.startswith(rows_path + "/")) or len(path.split("/")) > 3:
            return None, False                           # not a row; or a blob's bytes: no field that names a unit
        pid = path_id(path)
        try:
            return (self.ctl.unit(self.spec.parse_id(pid)) if pid else None), True
        except (ValueError, KeyError):
            return None, True

    def is_its_units(self, method: str, path: str) -> bool:
        if self.cams_of is None:
            return False
        old, written = self._row_written(method, path)
        return written and method in ("PUT", "DELETE") and old is not None and "cam" not in old

    # In two steps, because the body is read between them (`dispatch`): `body=False` asks about the row as it IS —
    # what the path alone decides — and `body=True` about the row as it WILL BE, and what the change reaches. `asked`
    # is what this request has been admitted on already, `{(capability, unit)}`: nothing is asked — or written into
    # the journal — twice.
    def admit_cams(self, h, method: str, path: str, asked: set | None = None, body: bool = True) -> None:
        old, written = self._row_written(method, path)
        if not written:
            return
        asked = set() if asked is None else asked
        whole = body or method == "DELETE"               # a delete has no body: the first step is all of it
        new = None
        if body and method != "DELETE":
            try:
                sent = json.loads(h.rfile.getvalue() or b"{}") if isinstance(h.rfile, io.BytesIO) else {}
            except ValueError:
                sent = {}
            new = {**(old or {}), **sent} if isinstance(sent, dict) else old
        cams = set()
        if self.cams_of is not None:
            for row in (old, new):
                if row is not None:
                    try:
                        cams |= {str(c) for c in (self.cams_of(row) or ())}
                    except Exception:                    # noqa: BLE001 — a row nobody can read the units of is anybody's
                        cams.add("*")
        if self.moved_cams is not None and body and old is not None and new is not None:
            try:
                cams |= {str(c) for c in (self.moved_cams(old, new) or ())}
            except Exception:                            # noqa: BLE001 — nobody can say what it reaches: the cluster's grant
                cams.add("*")
        if not cams and whole and self.cams_of is not None:
            cams = {"*"}                                 # a row that names no unit at all is anybody's: the cluster's grant
        cap = self.needs(method, path)[0]
        for cam in sorted(cams):
            unit = None if cam == "*" else cam
            if (cap, unit) in asked:
                continue
            self.gate.admit(h.headers, cap, unit, [] if cam == "*" else self._labels(cam, None))
            asked.add((cap, unit))

    def admit_body_cams(self, h, path: str, cap: str, asked: set) -> None:
        try:
            sent = json.loads(h.rfile.getvalue() or b"{}") if isinstance(h.rfile, io.BytesIO) else {}
            cams = {str(c) for c in (self.body_cams(path, sent) or ())}
        except Exception:                                # noqa: BLE001 — nobody can say what it reaches: the cluster's grant
            cams = {"*"}
        for cam in sorted(cams):
            unit = None if cam == "*" else cam
            if (cap, unit) in asked:
                continue
            self.gate.admit(h.headers, cap, unit, [] if cam == "*" else self._labels(cam, None))
            asked.add((cap, unit))

    # `PUT /<rows>/<id>/<field>`: the bytes of a blob. Reached only by a caller already admitted on the unit (`dispatch`).
    # What is not a blob field of this spec, or names no unit, is 404 without its body; `BLOBS_AT_ONCE` of them are
    # read at a time across the process — each is `MAX_BLOB` of memory while it is read and stored — and the next is
    # 503 with `Retry-After`, as an export past its bound is.
    def blob_route(self, h, path: str) -> None:
        field = path.split("/")[3]
        f = self.spec.fields.get(field)
        if f is None or f.type != "blob":
            h.close_connection = True
            return h._send(404, {"detail": f"{field} is not a blob field", "error": "no such blob field"})
        try:
            known = self.ctl.unit(self._uid(path)) is not None
        except (ValueError, KeyError):
            known = False
        if not known:
            h.close_connection = True
            return h._send(404, {"detail": "no such unit", "error": "no such unit"})
        if not blobs_slots().acquire(blocking=False):
            h.close_connection = True
            h._extra_headers = (("Retry-After", "1"),)
            return h._send(503, {"detail": "this console takes so many blobs at once (BLOBS_AT_ONCE) — retry", "error": "busy"})
        try:
            if not self.read_body(h, int(os.environ.get("CONSOLE_MAX_BLOB", MAX_BLOB))):
                return
            n = int(h.headers.get("Content-Length", 0) or 0)
            return h._send(*self.put_blob(self._uid(path), field, h.rfile.read(n), h.headers.get("X-User", "operator")))
        finally:
            blobs_slots().release()

    def dispatch(self, h, method: str, path: str, q: dict) -> None:
        """Answer one request for this subsystem. `path` is the route (`/<rows>`, `/where/7`), the mount
        prefix already removed; `h` is the handler (its `_send`, `_body`, `headers`, `rfile`)."""
        con, ctl, spec = self, self.ctl, self.spec
        rows_path = "/" + spec.rows
        if path == "/session":                           # the door in: anybody's, so its body is a token or a password
            if not self.read_body(h, SESSION_BODY):
                return
            return self.session(h, method)
        try:
            self.route_id(method, path)                  # `/<rows>/1/2`: no such route — said before the gate reads an id
        except NoSuchRoute as e:
            return h._send(404, {"detail": str(e), "error": "no such path"})
        # WHO, THEN WHAT THE PATH DECIDES, THEN THE BODY (the review's sixth pass, major). The caller was proved before
        # the body, and what they MAY do was asked after it: a token with no grant at all sent 32 MiB to
        # `PUT /<rows>/1/mask`, eight at a time, and the console held 331 MiB before it said 403 — in М11 four such
        # requests were its memory limit. Everything the path alone decides is asked first: the capability, the unit
        # the path names, the cameras the row reaches as it is. Only a route whose unit is IN the body (`EDIT_ROUTES`:
        # a mark, a command, a keep) waits for it — and is first asked for any grant at all, so a stranger's body is
        # not read. After the body: that unit, and the row as it will be.
        in_body = method in ("POST", "PUT") and path.startswith(self.EDIT_ROUTES)
        asked: set = set()
        if path not in OPEN_ROUTES:                     # the gate: open while this cluster has no key set, shut when it cannot check
            try:
                self.gate.caller(h.headers)              # who is calling: from the headers, before a byte of the body
                if in_body:
                    self.gate.admit(h.headers, "view")   # any grant here at all
                    asked.add(("view", None))
                elif not self.is_its_units(method, path):
                    need = self.needs(method, path, self._named(h, method, path, q))
                    self.gate.admit(h.headers, *need)
                    asked.add(need[:2])
                self.admit_cams(h, method, path, asked, body=False)
            except Denied as e:
                h.close_connection = True                # refused before the body: what follows the headers is not read
                return h._send(e.status, {"detail": e.why, "error": "denied"})
        # A blob's bytes are the one body larger than `MAX_BODY`, and only where the spec has a blob to put them
        # (`blob_route`): `PUT /<rows>/<id>/<a blob field>`, by somebody admitted on that unit.
        if method == "PUT" and path.startswith(rows_path + "/") and len(path.split("/")) == 4:
            return self.blob_route(h, path)
        if not self.read_body(h, int(os.environ.get("CONSOLE_MAX_BODY", MAX_BODY))):
            return
        if path not in OPEN_ROUTES:
            try:
                if in_body:
                    need = self.needs(method, path, self._named(h, method, path, q))
                    if need[:2] not in asked:
                        self.gate.admit(h.headers, *need)
                        asked.add(need[:2])
                    if self.body_cams is not None:
                        self.admit_body_cams(h, path, need[0], asked)
                self.admit_cams(h, method, path, asked)
            except Denied as e:
                return h._send(e.status, {"detail": e.why, "error": "denied"})
        if method == "GET":
            if path in ("/", "/index.html"):
                return send_file(h, PAGE, "text/html; charset=utf-8", headers=(("Content-Security-Policy", page_csp()),))
            if path == "/healthz":                      # alive: what the reserve and the monitors' lane answer besides
                return h._send(200, {"ok": True})        # (it was named there, and was a 404: the seventh pass's sweep)
            if path == "/spec":
                return h._send(200, con.describe())
            if path == rows_path:
                rows, configured = ctl.read_model(con.lost_after), mask_secrets(ctl.units())
                sees = self._visible(h)
                if sees is not None:                     # gated: the list is what THIS caller may look at, not the cluster's
                    ok = {str(r["id"]) for r in ctl.units() if sees(str(r.get("cam") or r["id"]), self._labels(str(r.get("cam") or r["id"]), r))}
                    rows = [r for r in rows if str(r.get("id")) in ok]
                    configured = [r for r in configured if str(r.get("id")) in ok]
                return h._send(200, {"rows": rows, "configured": configured})
            if path.startswith("/where/"):
                uid = self._uid(path); pl = ctl.placement(uid)
                return h._send(200 if pl else 404, {"worker": pl.worker if pl else None, "reason": pl.reason if pl else None,
                                                    "directory": con.where(uid), "scans": con.scans})
            if path == "/resources":
                now = con.wall()
                return h._send(200, {s: {**hb, "state": "live" if is_live("platform", float(hb["ts"]), now, con.lost_after) else "silent"}
                                     for s, hb in resources_seen(ctl.objects).items()})
            if path == "/servers":
                return h._send(200, con.servers())
            if path == "/domain":
                return h._send(*domain_view(ctl.objects, con.wall(), con.lost_after))
            if path == "/policy":
                return h._send(200, {**ctl.policy(), "choices": ctl.POLICY_CHOICES})
            if path == "/unplaceable":
                return h._send(200, ctl.unplaceable())
            if path == "/events":
                if con.index is None:
                    return h._send(503, {"error": "no event index behind this console"})
                cam = q.get("cam") or (q.get("unit") if (q.get("unit") or "").isdigit() else None)
                # Every subsystem's epochs, from the cache — the timeline shows them all. A camera's or one unit's
                # timeline reads only the epochs of the units in ITS answer, after the query, and fences again.
                narrow = bool(cam or q.get("unit"))
                cur = {} if narrow else con.epochs()
                try:                                          # the operator's timeline: `limit` is theirs to set, and
                                                              # `keep` says which end of a busy hour they get
                    t0, t1 = float(q.get("from", 0)), float(q.get("to", 1e12))
                    rep = con.index.query(t0, t1,
                                          int(cam) if cam else None, q.get("kind"), q.get("subsystem"),
                                          q.get("unit") if not cam else None, cur,
                                          limit=min(int(q.get("limit", 1000)), MAX_LIMIT),
                                          epoch_policy=con.epoch_policy, keep=q.get("keep", "newest"),
                                          cls=q.get("class"), by=q.get("by", "t"))
                    if narrow:
                        refence(rep["events"], con.epochs_of({(e["subsystem"], e["unit"]) for e in rep["events"]}), con.epoch_policy)
                    sees = self._visible(h)
                    if sees is not None:                 # …and so are the events: a unit's, to whoever may view that unit;
                        known: dict = {}                 # what names no unit — the journal — to whoever may view the whole cluster

                        def may_see(e):
                            unit = "*" if e.get("cam") is None else str(e["cam"])
                            if unit not in known:
                                row = None if unit == "*" else ctl.unit(spec.parse_id(unit)) if spec.rows and "cam" not in (spec.fields or {}) else None
                                known[unit] = sees(unit, list((row or {}).get("labels") or []))
                            return known[unit]
                        rep = {**rep, "events": [e for e in rep["events"] if may_see(e)]}
                    if not narrow and con.epochs_stale:
                        rep = {**rep, "epochs": "cached"}         # fenced by the epochs read before the store went quiet
                    return h._send(200, con.timeline(rep, t0, t1))
                except ValueError as e:
                    return h._send(400, {"error": str(e)})
            if path == "/metrics":
                return h._send(200, con.metrics_text(), raw=True)
            if self._extra(h, "GET", path, q):
                return
            return h._send(404, {"detail": "no such route", "error": "no such path"})
        if method == "POST":
            if path not in (rows_path, "/marks"):
                if self._extra(h, "POST", path, q):
                    return
                return h._send(404, {"detail": "no such route", "error": "no such path"})
            key = self._idem(h)
            if key is None:
                return
            try:
                if path == "/marks":
                    resp = con.mark(h._body(), h.headers.get("X-User", "operator"))
                else:
                    resp = con.create(h._body(), key, h.headers.get("X-User", "operator"))
            except Exception as e:                                       # noqa: BLE001
                return h._send(*self._failed(key, e))
            self._remember(key, resp); return h._send(*resp)
        if method == "PUT":
            if path == "/policy":                                        # the administrator's knobs: one row, no idempotency needed (a PUT is)
                try:
                    body = h._body()
                    out = ctl.set_policy(body)
                except (Refused, Forbidden) as e:
                    return h._send(400 if isinstance(e, Refused) else 403, {"detail": str(e), "error": str(e)})
                # A knob that moves every unit of the subsystem is a line with a name and the new values in it (the
                # review's third pass, minor): the policy's values are choices, not secrets.
                con.journal.say("policy.changed", of=spec.name, user=h.headers.get("X-User", "operator"),
                                policy=json.dumps(body, sort_keys=True))
                return h._send(200, out)
            if not path.startswith(rows_path + "/"):
                if self._extra(h, "PUT", path, q):
                    return
                return h._send(404, {"detail": "no such route", "error": "no such path"})
            key = self._idem(h, required=False)                         # optional here: a PUT is its own retry
            if key is None and h.headers.get("Idempotency-Key"):
                return                                                   # a prior reply, a refused key or 503: already sent
            try:
                resp = con.update(self._uid(path), h._body(), h.headers.get("X-User", "operator"))
            except Exception as e:                                       # noqa: BLE001
                return h._send(*self._failed(key, e))
            self._remember(key, resp)
            return h._send(*resp)
        if method == "DELETE":
            if not path.startswith(rows_path + "/"):
                if self._extra(h, "DELETE", path, q):
                    return
                return h._send(404, {"detail": "no such route", "error": "no such path"})
            try:
                return h._send(*con.delete(self._uid(path), h.headers.get("X-User", "operator")))
            except Exception as e:                                       # noqa: BLE001 — said in the journal already
                return h._send(*self._failed(None, e))
        h._send(405, {"detail": "method", "error": "method"})

    # Starts the server in a daemon thread and returns it (tests use `port=0` and read `server_address`).
    def serve(self, host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
        return open_doors(host, port, self.handler())


class Mount:
    """One console process, several subsystems. The root console answers at `/`
    (the page, `/<rows>`, its extras); every other subsystem is a path: `/live/spec`,
    `/det/units`, `/det/where/7-motion` — the same SpecConsole class, its routes
    under its name, its own token-scoped controller. A person opens one page;
    the machines (the autoscaler, М12's read model) find every subsystem on one
    port; a new subsystem is a YAML, a worker, and a path."""

    def __init__(self, root: SpecConsole, mounts: dict[str, SpecConsole] | None = None):
        self.root, self.mounts = root, dict(mounts or {})
        # One dict, SHARED by reference with every console here: `/events` merges across subsystems, so the
        # console answering the request has to know what an older epoch means in a subsystem it does not
        # own. A subsystem nobody mounted keeps the default, which is the old behaviour.
        self.epoch_policy: dict[str, str] = {}
        for c in (self.root, *self.mounts.values()):
            self._adopt(c)

    def _adopt(self, console: SpecConsole) -> None:
        self.epoch_policy[console.spec.name] = console.spec.older_epochs
        console.epoch_policy = self.epoch_policy

    def mount(self, name: str, console: SpecConsole) -> "Mount":
        self.mounts[name] = console
        self._adopt(console)
        return self

    def resolve(self, path: str) -> tuple[SpecConsole, str]:
        head = path.split("/", 2)
        if len(head) >= 2 and head[1] in self.mounts:
            return self.mounts[head[1]], "/" + (head[2] if len(head) > 2 else "")
        return self.root, path

    def describe(self) -> dict:
        return {"root": self.root.spec.name, "mounts": {n: c.describe() for n, c in self.mounts.items()}}

    # `GET /schema` — what layout the store is in, what every live process understands, and whether the
    # version can be raised; `PUT /schema?version=2` — raise it, once every machine is new.
    #
    # The two halves of an upgrade read side by side here: `/drain` is about one machine at a time,
    # `/schema` is about the moment all of them are done. Raising early is the mistake the guard exists
    # for — it would lock out whatever was not upgraded, which is exactly what a rolling upgrade is
    # trying to avoid.
    def schema_route(self, method: str, q: dict, user: str = "operator") -> tuple:
        ctl = self.root.ctl
        now = ctl.wall()
        if method == "PUT":
            try:
                was = schema_version(ctl.vars)
            except Exception:                            # noqa: BLE001 — what it was is for the journal; set_schema decides
                was = None
            try:
                ctl.set_schema(int(q.get("version", 0)))
            except SchemaTooNew as e:
                return 409, {"error": str(e), "detail": str(e)}
            except ValueError:
                return 400, {"error": "a version is a number", "detail": "a version is a number"}
            except Forbidden as e:                       # the console's token, not the caller: the store said no
                return 403, {"error": str(e), "detail": f"{e} — this console's token does not reach platform/schema"}
            # Irreversible — every older build is locked out from here — so it is a line with a name in it.
            self.root.journal.say("schema.raised", version=int(q.get("version", 0)), was=was, user=user)
        elif method != "GET":
            return 404, {}
        running = builds(ctl.objects, now)
        live = {n: b for n, b in running.items() if b["live"]}
        return 200, {"version": schema_version(ctl.vars), "understood": SCHEMA,
                     "builds": sorted({b["build"] for b in live.values()}),
                     "can_raise_to": min([b["schema"] for b in live.values()], default=SCHEMA),
                     "processes": dict(sorted(running.items()))}

    # `GET /drain` — is it safe to stop the machine yet; `POST /drain?server=srv-a` — say it is going to
    # stop; `DELETE /drain` — it is back. The only route on the Mount itself rather than on a subsystem,
    # because a server carries several and the answer is `safe` only when every one of them says so.
    #
    # An upgrade script is then three lines and no `sleep`: POST, poll until `safe`, stop the machine. And
    # after the reboot, DELETE — and `ensure_home` refills it one unit a pass, which is why the script
    # should wait for the work to come back before draining the NEXT machine. Otherwise ten servers'
    # worth of units drift onto whichever two were upgraded last.
    def drain_route(self, method: str, q: dict, user: str = "operator") -> tuple:
        consoles = [self.root, *self.mounts.values()]
        ctl = self.root.ctl
        if method == "POST":
            server = q.get("server", "")
            if not server:
                return 400, {"error": "a drain names a server", "detail": "a drain names a server"}
            try:
                ctl.drain(server)
            except DrainRefused as e:
                return 409, {"error": str(e), "detail": str(e)}
            self.root.journal.say("drain.started", server=server, user=user)   # every unit leaves a server: who said so
        elif method == "DELETE":
            was = ctl.draining()
            ctl.undrain()
            self.root.journal.say("drain.ended", server=was, user=user)
        elif method != "GET":
            return 404, {}
        parts = [c.drain_state() for c in consoles]
        server = ctl.draining()
        if not server:
            return 200, {"draining": "", "safe": True, "subsystems": {p["subsystem"]: p for p in parts}}
        return 200, {"draining": server,
                     "safe": all(p.get("safe") for p in parts),
                     "would_strand": {p["subsystem"]: p["would_strand"] for p in parts if p.get("would_strand")},
                     "subsystems": {p["subsystem"]: p for p in parts}}

    # THE MOUNT'S OWN ROUTES ASK THE GATE TOO (the review's third pass, blocker 2). `/drain`, `/schema` and `/mounts`
    # were answered here, before `dispatch` and its gate: `POST /drain?server=srv-1` with no token took every
    # recording off a server, and the irreversible `PUT /schema` was as open. There are no exceptions for rights:
    # the root console's gate, `admin` to change (a drain moves every unit of a server; a schema locks out every
    # older build) and `view` to read — `/mounts` too. It says what this process fronts and each subsystem's
    # `/spec`, which is gated; it is the same knowledge, and the page reads it after its login like `/spec`. An
    # upgrade script polls `GET /drain` with a token, as anything else that talks to a gated console does.
    # Returns the name to act under, or None when it has already answered.
    MOUNT_ROUTES = ("/mounts", "/drain", "/schema")

    def admit(self, h, method: str) -> str | None:
        try:
            return self.root.gate.admit(h.headers, "view" if method == "GET" else "admin")
        except Denied as e:
            h._send(e.status, {"detail": e.why, "error": "denied"})
            return None

    def handler(self):
        mnt = self

        class H(SendMixin, Deadlined, BaseHTTPRequestHandler):
            # A SOCKET THAT SAYS NOTHING IS LET GO (the review's fourth pass, major). The console's connections had no
            # timeout at all: a client that sent half a request line, or asked for an export and read nothing, held its
            # thread — and an export's slot — until the console restarted. `timeout` is the socket's, for every read
            # and write: the request line and headers (slowloris) as much as an export's body.
            timeout = float(os.environ.get("CONSOLE_TIMEOUT", CONSOLE_TIMEOUT))

            # …and the request's line and headers have `CONSOLE_HEADER_TIMEOUT` to arrive in WHOLE (`Deadlined`,
            # `DeadlineReader`); its body is given a deadline of its own when it is read (`SpecConsole.read_body`).
            def log_message(self, *a): pass

            def _route(self, method):
                u = urlsplit(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
                # A connection of the reserve is for the door in and for monitoring, whichever subsystem's (`Bounds`).
                if self.busy_unless(RESERVE_ROUTES, mnt.resolve(u.path)[1]):
                    return
                if u.path in mnt.MOUNT_ROUTES:
                    user = mnt.admit(self, method)
                    if user is None:
                        return                                           # refused, and said so
                    if u.path == "/mounts":
                        return self._send(200, mnt.describe())
                    if u.path == "/drain":
                        return self._send(*mnt.drain_route(method, q, user))
                    return self._send(*mnt.schema_route(method, q, user))
                con, path = mnt.resolve(u.path)
                con.dispatch(self, method, path, q)

            def do_GET(self): self._route("GET")
            def do_POST(self): self._route("POST")
            def do_PUT(self): self._route("PUT")
            def do_DELETE(self): self._route("DELETE")

        return H

    def serve(self, host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
        return open_doors(host, port, self.handler())
