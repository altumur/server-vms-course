"""The console as data — the other half of spec.py. A subsystem's YAML
already says what its units are, which fields the operator owns and what
leaves the cluster; that is everything a console needs to list, edit and
show them. So the console is one class, run from the same spec:

    GET  /                       the page, at the console's root alone: the root subsystem's own (`<sub>.shell.html`
                                 beside its spec), else the platform's (console.html) — the console module and its
                                 mount, which shows any spec; a mounted subsystem serves none (404)
    GET  /platform/console.js[?v=1], /platform/console.css   the console module every page is built from, and its look;
                                 open (it draws the login); another version is 404
    GET/POST/DELETE /session, POST /session/break-glass   the door in (`session`): {open, login_url, user?, until?, via?}
    GET  /spec                   what the page reads first: name, rows, id rule, fields, door, metric names
    GET  /<rows>                 {rows: the read model from every worker's heartbeat, configured: the units}
    GET  /where/<id>             the stored placement (why, its worker and server) and the assignments' answer (where, one
                                 scan), and the holder's door for the spec's `door: {routes}`
    GET  /where/<table>/<place>?unit=<sub>/<id>   who holds a place of the spec's `placement.places` now, and its door
                                 for that unit — or 404 and `X-Unreachable: <place>@<server>` when nobody does
    GET  /resources              the platform's resources: usage, units, live | silent
    GET  /unplaceable            units nothing live can serve, with the labels that say why
    GET  /servers                every server as placement sees it: its labels, its resource (the fact, its address, its disk),
                                 its workers (each with the heartbeat fields its spec's `servers.status` names), placeable
                                 or why not, its decommission
    GET  /domain                 the domain's view, if THIS cluster hosts the domain (М12 Lesson 3): members, completeness,
                                 units by cluster, with its age; 404 anywhere else — a cluster does not know the others
    GET  /domain/shared/<sub>[?unit=<id>]   the fields a spec shares with the domain (`domain.shared`), resolved from
                                 this cluster's verified copy of the shared document: value and where it came from, the
                                 groups the domain offers for the field the page groups by; nothing undeclared
    GET  /domain/keys            every key under `domain/` in this cluster's stores, secrets masked (`domain.keysview`)
    GET  /domain/<sub>/books/<book>   the fields a spec shows of a book (`domain.books.<book>.show`), of every entry of
                                 this cluster's own copy — `{<item>: {<field>: value}}`; an item to whoever may view the
                                 unit whose `domain.ref` is its key, every item to a view of the whole cluster; 404 for a
                                 book not shown (`SpecConsole.book_route`; ADR-0010, the addition of 2026-10-06)
    …    /domain/<any other>     handed to the domain holder's door at the same path, unrewritten (`Mount.domain_forward`:
                                 the view's `url`), with the person's token and the edit's Idempotency-Key
    GET/PUT /policy             the administrator's knobs — servers: shared | distinct — one row, <sub>/policy, the console's to write
    GET/PUT/DELETE /servers/<server>/labels   on the Mount, as /drain: what a server reaches, the administrator's word over
                                 its node's (platform/servers/<server>, one a server; ADR-0026) — `would_move`/`will_move`
                                 are `<sub>/<id>` of every subsystem here, those the caller may see
    GET  /events?from&to&unit&kind&subsystem   the resources' event indexes, merged (MergedIndex), fenced by every subsystem's epochs
    GET  /metrics                <name>_workers_live · <name>_worker_headroom{worker,server} · <name>_worker_load ·
                                 <name>_epoch_conflicts · <name>_failover_seconds{kind="worst"} ·
                                 <name>_<running> (units in phase "running"; the spec names the gauge); and the
                                 platform's own, once per console process: w2c_resources_live · w2c_resource_*
    POST /<rows>  (Idempotency-Key)   the row only — the controller places it on its next pass; the key is a Variable
                                 (<sub>/idem/<key>), so the retry is answered the same by whichever console gets it
    PUT  /<rows>/<id>            the operator's fields; a new revision; refused where the controller refuses
    DELETE /<rows>/<id>          the row is marked; the controller's pass takes its placement back
    POST /marks  (Idempotency-Key)    an operator's observation {unit: <sub>/<id>, note}: the CONSOLE's event, into
                                 console/<instance>/… on this server's resource — never a worker's bucket
    POST/DELETE /servers/<server>/decommission  {why} — on the Mount, as /drain: "this machine is gone for good"
                                 (platform/decommission/<server>): 409 while the server answers; the controllers release
                                 its slots and move their units; DELETE withdraws it, or brings the machine back

A subsystem adds no routes: what it serves beyond its rows is declared in its spec — `tables:`, `requests:` —
and what its holders serve a page themselves is `door:`, handed out with the unit's place at `/where` (the
boundary's step 6: it was `extra(handler, method, path, query)`, a subsystem's function every request fell to). The
console holds the subsystem's
SpecController with the console's token — the operator's rows, never
placement — so a write it should not make is a 403 from the store, not a
rule in this file.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # console.py — the console as data: SpecConsole over the same spec, with idempotent writes and the
# spec's declared tables, requests and doors
#
# **Role in the module.** Lesson 6, the other half of `spec.py`. A subsystem's YAML already says what its
# units are, which fields the operator owns and what leaves the cluster; that is everything a console needs
# to list, edit and show them, so the console is one class run from the same spec. It serves the page (`page_of`), the
# console module (`/platform/console.js`),
# `/spec` (what the page reads first), the rows with the read model, `/where`, `/resources`, `/unplaceable`,
# `/events` (if a `MergedIndex` — anything with `query(t0, t1, kind, subsystem, unit, current_epochs)` — is behind it), `/metrics`, and the writes — POST/PUT/DELETE on the rows and
# POST `/marks` — with idempotency keys stored in Variables so a retry answered by another console instance
# is the same request. A subsystem adds no routes of its own: its tables and requests are its spec's, and the bytes
# its holders serve go holder → browser through the door `/where` hands out (`door.py`; the boundary's step 6). The
# console holds the subsystem's `SpecController` with the *console's* token (the operator's rows, never
# placement), so a write it should not make is a 403 from the store, not a rule in this file.
# `vms/console.py` builds it via `make_console`; the deploy unit `w2c-console.container` runs it as its own
# process.
#
# ## Module-level names
# - `PAGE` — absolute path of `console.html` beside this file: the platform's own page, the console module and its mount
#   and nothing else; served at `/` for a root subsystem with no page of its own. `SHELL` — a subsystem's own page,
#   `<sub>.shell.html` beside its spec (`page_of`); `MODULE`, `MODULE_CSS`, `MODULE_VERSION` — the console module every page is
#   built from, served at `/platform/console.js` and `/platform/console.css` (`send_module`).
#
# ### `__init__(self, ctl, marks_root=None, index=None, worst_failover=0.0, wall=None,
# lost_after=45.0)` `ctl` is the subsystem's `SpecController` holding the console's token;
# `marks_root` is this server's resource root — if given, `self.marks` is an `EventLog(marks_root,
# "console", <hostname:pid>, epoch 1)` (the console's own log; one writer, so epoch 1 forever); `index` is
# an optional `MergedIndex` (anything with `query(...)`); `worst_failover` is a number exported on `/metrics`.
# What a holder serves a page is the spec's `door:`, which `/spec` says. `seen` is the `IdempotencyKeys`
# over `<sub>/idem/`. `_scan` caches the assignment directory; `scans` counts cache refreshes.
#
# ## Notes
# - `test_the_console_over_http` walks the whole surface: POST twice with one key is one camera; the
#   console's controller cannot `place` (`Forbidden`); PUT `{"worker": "w-9"}` is 400; `/cameras` rows show
#   `phase running` and `server srv-1`; `/where/1` agrees with the directory; `/spec` says `rows cameras`; `/metrics` contains `vms_cameras_running 1`; `/marks` writes to `console/<instance>/e1/`;
#   a subsystem's own page reads `/spec` and the holders' doors;
#   what the holders serve is read at the doors `/where` hands out, never here; PUT `{"enabled": false}` bumps
#   revision to 2; DELETE marks the row and the placement waits for `unplace_deleted`.
# - Idempotency covers POST always, PUT optionally, DELETE never; the page sends a fresh key with every
#   request (including DELETE, where it is ignored).
# - `/events` relies on a `MergedIndex` behind the console — every live resource's own event index, merged; without one it is an honest 503,
#   and the page tolerates that.
# - What a request may cost before anybody knows who sent it (the review's fifth pass): the caller is proved from the
#   headers (`Gate.caller`) before a byte of the body is read; the body is read once, under `MAX_BODY` (`MAX_BLOB`
#   for a blob's bytes) and a deadline (`read_body`); the request's line and headers arrive whole within
#   `CONSOLE_TIMEOUT` (`DeadlineReader`); and `CONSOLE_CONNECTIONS` are served at once, the next answered 503
#   (`ConsoleServer`). Whose a row is the spec says (`about`, `rights.unit_of`), and a write to it asks for the
#   route's capability on that unit, before and after (`admit_rows`; the boundary's step 2).
# - …and what the sixth pass found left of it. WHOSE the connections are (`Bounds`): one address holds a share of
#   them (`CONSOLE_PER_ADDRESS`), the door in has a reserve (`CONSOLE_RESERVE`, `RESERVE_ROUTES`), the monitors named
#   in `CONSOLE_MONITORS` a lane of their own (`MONITOR_ROUTES`; the seventh pass), and the caller on the box —
#   through the unix socket `CONSOLE_UNIX` (`UnixConsoleServer`) — a lane of its own; the
#   request line and headers have `CONSOLE_HEADER_TIMEOUT`, not the socket's timeout (`Deadlined`). RIGHTS BEFORE THE
#   BODY (`dispatch`): everything the path decides is asked first, the body read after, and only a blob route of the
#   spec reads up to `MAX_BLOB`, `BLOBS_AT_ONCE` at a time (`blob_route`). A CHANGE that reaches other units says so
#   (the spec's `rights.reach`, `rights.names`). And the same server, deadline and bounded body are every door's, not the
#   console's alone: `door_server`, `Deadlined`, `read_body`, and for what a door streams `Paced` and `start_stream`.
# ================================================================================================
from __future__ import annotations

import io
import json
import logging
import os
import re
import socket
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .doors import MAX_LIMIT, byte_range, parse_ref, ref_fault

from .secrets import hide_in_reply, is_secret_field, mask_secrets
from .contract import (GARBLED, HEARTBEATS, SCHEMA, SCHEMA_KEY, SKEW_MAX, SKEW_MIN, Assignment, DrainRefused, Heartbeat,
                       DecommissionRefused, SchemaTooNew, builds, contenders, is_live, label_set, name_conflict,
                       parse_heartbeat, read_slot, schema_version)
from .epoch import current_epoch
from .canonical import canonical_json, field_text, number_text, parse_json
from .rows import FIELDS, PARSE_ERRORS, Table, counts as garbled_by_table, finite, number
from .eventdatabase import refence, unit_id
from .events import ALARM, CONSOLE_MARKS, OF, EventLog


# The default flow one operator is expected to read, in events a minute. Past it a timeline of separate
# lines is not information any more: a storm makes every alarm look like the last one, and the operator
# stops reading — which is the failure the whole event path was built to avoid, arriving through the
# front door instead of through a lost write.
#
# Sixty is one a second, and it is a starting number rather than a discovery: the point of having it at
# all is that SOMETHING happens when it is crossed. A norm with nothing acting on it is a comment.
PER_MINUTE = 60.0
LEDGER = "asks-"              # `<sub>/requests/asks-<sha256 of the person, 16 hex>`: one person's open requests (`_file_request`)
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
from .access import (COOKIE, GLASS_COOKIE, MODULE_ROUTES, OPEN_ROUTES, UNIX_PEER, Denied, Gate, caller_addr, is_local, may_on,
                     session_cookie, token_of)
from .journal import AUDIT, Journal
from .resource import resources_seen
from .limits import TooLarge
from .spec import GARBLED_ROW, LABEL_WORD, Exists, Refused, SpecController, server_name

# A unit's row the timeline's gate reads for its labels (`SpecConsole.dispatch`, `/events`): one that does not parse is
# that unit's events withheld from a grant by label, and nobody else's timeline (the scaling pass after the eighth review).
UNIT_LABELS = Table("unit", "its events are shown only to a grant that needs no labels: the unit's own, or the whole "
                    "cluster's", "unit's row, read for its labels")
from .variables import Conflict, Forbidden

log = logging.getLogger(__name__)

PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "console.html")
MODULE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "console.js")
MODULE_CSS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "console.css")
MODULE_VERSION = "1"                   # the contract's version (КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md §3): `?v=` names it
SHELL = "{}.shell.html"


# THE PAGE AT `/` (the boundary's step 3; КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md §1): a subsystem's own page when it has one —
# `<sub>.shell.html` beside `<sub>.subsystem.yaml`, the page that mounts the platform's console module and adds what is
# its own — else the platform's page, the module and its mount and nothing else, which shows any spec. A spec built in
# code (`from_dict`) has no file, so no page of its own. Only the console's root serves it (`SpecConsole.serves_page`).
def page_of(spec) -> str:
    from . import catalog
    f = catalog.file_of(spec.name)
    own = os.path.join(os.path.dirname(f), SHELL.format(spec.name)) if f else None
    return own if own and os.path.isfile(own) else PAGE


# `GET /platform/console.js` and `/platform/console.css`: the module and its look, open — the module draws the login.
# `?v=` asks for a version; another than this platform's is 404, saying which one it serves (no older one is kept: the
# owner's rule, while the system runs on one machine).
def send_module(h, path: str, q: dict) -> None:
    if q.get("v") not in (None, MODULE_VERSION):
        return h._send(404, {"detail": f"no console module of version {q['v'][:20]}; this platform serves {MODULE_VERSION}",
                             "error": "no such version"})
    raw = open(MODULE if path.endswith(".js") else MODULE_CSS, "rb").read()
    h.send_response(200)
    h.send_header("Content-Type", "text/javascript; charset=utf-8" if path.endswith(".js") else "text/css; charset=utf-8")
    h.send_header("Content-Length", str(len(raw)))
    h.end_headers()
    h.wfile.write(raw)


# The page's Content-Security-Policy: the scripts the browser may run are the page's own, each inline one named by
# its hash, and — for a page that loads the console module (`<script src="/platform/…">`) — this origin's files; nothing
# else — not a `<script>` an event's note smuggled into the list, not an `onclick=` in a unit's name. The page and the
# module escape what they draw; this is the second wall, for the place the escaping missed.
def page_csp(path: str = PAGE) -> str:
    import base64, hashlib, re
    page = open(path, encoding="utf-8").read()
    scripts = [m.group(1) for m in re.finditer(r"<script>(.*?)</script>", page, re.S)]
    hashes = " ".join("'sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode() + "'" for s in scripts)
    own = "'self' " if re.search(r"<script src=\"/", page) else ""
    return f"script-src {own}{hashes}; object-src 'none'; base-uri 'none'"


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


# `/domain/<sub>/books/<book>` of a spec on the domain: `(spec, book)`, else None — what this console answers itself, any
# method (a write is 405 here, never handed to the holder), before the route goes to the domain's door. The product's
# `ConsoleDoor.Handle`: `books/` after a known subsystem's name, whatever follows it.
def book_path(path: str):
    from .domain import declared
    parts = path[len("/domain/"):].split("/", 1) if path.startswith("/domain/") else []
    if len(parts) < 2 or not parts[1].startswith("books/"):
        return None
    s = declared.spec(parts[0])
    return (s, parts[1][len("books/"):]) if s is not None else None


# What a book's entry that is no JSON object is: counted (`books_garbled` on the metrics page, as every table of rows) and
# logged once, its bytes never (an entry carries tokens).
BOOK_ENTRIES = Table("book", "left out of what the page is shown", "entry of a book")   # `books_garbled`


# A JSON number as it is (`5` stays `5`, `0.5` stays `0.5`): `true` is no number and neither is the word `"5"` — a
# `TypeError` for both, a `ValueError` for `nan` and `inf` (`finite`).
# The value at a `servers.status` field in a heartbeat's extra — a field, or a path through its maps by its dots:
# `(said, value)`; a key not there, or a value on the way that is no map, is not said.
def _status_path(extra: dict, field: str) -> tuple[bool, object]:
    cur = extra
    for seg in field.split("."):
        if not isinstance(cur, dict) or seg not in cur:
            return False, None
        cur = cur[seg]
    return True, cur


def _json_number(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TypeError(f"{v!r:.40} is not a number")
    finite(v)
    return v


# `GET /spec`: a spec as the page reads it — of the spec alone, so the domain holder's door, which runs no controller,
# says the same of every spec it loaded (`/mounts` there, the contract's §10a).
def describe(s) -> dict:
    return {"name": s.name, "rows": s.rows, "id": s.id,
            "fields": [{"name": f.name, "type": f.type, "default": f.default_value(), "required": f.required,
                        **({"inherit": f.inherit, "merge": f.merge} if f.inherits else {}),
                        **({"fixed": True} if f.fixed else {}),
                        **({"bound_to": list(f.bound_to)} if f.bound_to else {}),   # a secret asked anew when they change
                        **({"enum": list(f.enum)} if f.enum else {})} for f in s.fields.values()],
            **({"about": {"sub": s.about_sub, "field": s.about_field}} if s.about_sub else {}),
            # the page's words and what it shows under a server, as the spec wrote them; the gauges it reads on
            # `/metrics` by name (the boundary's step 6; the product's keys)
            **({"display": s.display} if s.display else {}),
            **({"servers": {**({"show": s.servers_show} if s.servers_show else {}),
                            **({"status": s.servers_status} if s.servers_status else {})}}
               if s.servers_show or s.servers_status else {}),
            **({"door": {"routes": list(s.door_routes)}} if s.door_routes else {}),
            **({"places": {"table": s.places["table"]}} if s.places else {}),   # `/where/<table>/<place>`
            # its part of the domain, as the page reads it (the contract, §10a): the key families (`domain.keys`; their
            # words are `display.keys`), the shared fields, the fields the holder lets into an edit, the view's fields
            **({"domain": {"keys": [{"id": f["id"], "keys": list(f["keys"]), **({"prefix": f["prefix"]} if f["prefix"] else {})}
                                    for f in s.domain.keys], "shared": list(s.domain.shared),
                           "edit": list(s.domain.edit), "view": list(s.domain.view)}}
               if s.domain else {}),
            "running_gauge": f"{s.name}_{s.running_gauge}" if s.running_gauge else None,
            "workers_gauge": f"{s.name}_workers_live",
            "metrics": {"prefix": s.name, "running": s.running_gauge or None}}


def domain_view(objects, now: float, lost_after: float = 45.0) -> tuple[int, dict]:
    raw = objects.get(DOMAIN_VIEW)
    if not raw:
        return 404, {"error": "no domain view here: this cluster does not host the domain, and it does not know "
                              "the others — ask the domain holder's console"}
    # A view that does not read is not a 500 (the review's tenth round: `domain/view` torn, or a list, raised out of the
    # route): the domain's view is not known here, said so — and a `ts` that is no finite time (`Infinity` made the view
    # current for ever) is the same.
    try:
        d = json.loads(raw)
        if not isinstance(d, dict):
            raise TypeError(f"the view is a map, not {type(d).__name__}")
        age = max(0.0, now - finite(d.get("ts", 0)))
    except PARSE_ERRORS as e:
        log.warning("%s does not parse (%s): the domain's view is not shown", DOMAIN_VIEW, e)
        return 503, {"error": "the domain's view in this cluster's store cannot be read: what the domain knows is not "
                              "shown until its next pass writes it again", "detail": f"{DOMAIN_VIEW}: {type(e).__name__}"}
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
#
# …FRESH BY THE ASKER'S EYES WHERE IT HAS THEM (the review's thirteenth pass, blocker 4): `eyes` — the asker's `Eyes`, a
# long-lived judge — say whether a heartbeat CHANGED within `lost_after` of its own clock; without them, the writer's
# `ts` against `now`, as before (a one-off look that has watched nothing change).
def holders(objects, prefix: str, now: float, lost_after: float = 45.0, eyes=None) -> dict[str, Heartbeat]:
    """The heartbeats fresh enough to act on."""
    sub = prefix.rstrip("/")
    return {w: hb for w, hb in heartbeats(objects, prefix).items() if heard_live(sub, w, hb, now, lost_after, eyes)}


# One heartbeat, by the same rule — for a reader that walks every heartbeat and wants the silent ones too (the product's
# r29-writers2: a subsystem's readers judged by the writer's `ts` against their own `now`, so a dead process whose clock
# ran ahead stayed fresh, and one behind lost what it held).
def heard_live(sub: str, w: str, hb: Heartbeat, now: float, lost_after: float = 45.0, eyes=None) -> bool:
    if eyes is not None:
        return eyes.fresh(f"{sub}/heartbeats/{w}", hb.token, lost_after, hb.ts, sub)
    return is_live(sub, hb.ts, now, lost_after)


# `(worker, its heartbeat, the unit's status entry)` for the process holding `unit` right now, or None.
# `phase` narrows it further when the caller needs the unit to be doing something and not merely held:
# a recorder subscribes to a fan-out only in `running`, while a playback door answers in `held` too.
def holder_of(objects, prefix: str, unit, now: float, lost_after: float = 45.0,
              phase: str | None = None, field: str | None = None, eyes=None):
    found = []
    for w, hb in sorted(holders(objects, prefix, now, lost_after, eyes).items()):
        for st in hb.status:
            if str(st.get("id")) != str(unit):
                continue
            if phase is not None and st.get("phase") != phase:
                continue
            if field is not None and not st.get(field):
                continue
            found.append((w, hb, st))
    return newest(found)


# The kind of a refusal, for a 400's body: `{"fault": <word>}` when the refusal says one (`AddressRefused`: `bad_url`;
# the closed dictionary is `canonical.FAULTS`), nothing otherwise — the reason is always the body's `detail`.
def _epoch(st) -> int:
    try:
        return int(st.get("epoch") or 0)
    except (TypeError, ValueError, OverflowError):
        return 0


def newest(found: list):
    """Of the workers that say they hold one unit, the one under the highest epoch — the writer the fence admits; in
    name order among equals. A judge that first looks after a server died sees the dead holder's last heartbeat as new
    for a while (it judges by what it saw change, the thirteenth review); its epoch is the older one."""
    best = None
    for f in found:
        if best is None or _epoch(f[2]) > _epoch(best[2]):
            best = f
    return best


# AN ERROR IN WORDS, WITHOUT A PATH (the review's thirteenth pass, minor; the product's cross-check (c)): a 500's and a
# 503's `detail` was `str(e)` — "[Errno 13] Permission denied: '/data/platform/vars/vms/cameras/7'", the layout of the
# server's disk for anybody who can make a write fail. An `OSError` says its `strerror`; anything else has every
# absolute path in its text replaced. The full error goes to the log, where the operator reads it.
_ABSOLUTE = re.compile(r"(?<![\w.:/])/(?:[^\s'\"/:,;)]+/)+[^\s'\"/:,;)]*")


def no_paths(e) -> str:
    """`e` for a reply: an `OSError`'s own words, any other's text with its absolute paths cut out."""
    if isinstance(e, OSError) and e.strerror:
        return e.strerror
    return _ABSOLUTE.sub("<path>", str(e))


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
#
# …AND PAST THE HEADERS THERE IS ALWAYS ONE (the review's twelfth pass, major 8). The headers' deadline gave way to one
# a year off (`Deadlined.parse_request`), and only a handler that called `body_deadline` got a floor: one that read its
# client without it waited a byte at a time for as long as the client trickled. `lazy`: past the headers, the first read
# that finds no floor sets one — the handler's timeout for a grace and `BODY_RATE` after it — whoever reads.
class DeadlineReader(io.RawIOBase):
    def __init__(self, sock, deadline, op_timeout: float):
        self.sock, self.deadline, self.op = sock, deadline, op_timeout
        self.got, self.floor = 0, None                   # bytes received; (since, grace, rate, got then) while a body is read
        self.lazy = False                                # past the headers: a read with no floor sets a body's (`readinto`)

    def readable(self) -> bool:
        return True

    def pace(self, grace: float, rate: float) -> None:
        self.floor = (time.monotonic(), float(grace), float(rate), self.got)

    def readinto(self, b) -> int:
        if self.floor is None and self.lazy:
            self.pace(self.op, BODY_RATE)
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
RESERVE_ROUTES = ("/session", "/session/break-glass", "/healthz")
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
            # An address's share binds once the room is half taken: below that a client that retries fast, or a page's
            # parallel requests, wait as they did; above it nobody adds past `LINGER_PER_ADDRESS`, so the half left is
            # the other addresses'.
            room = len(self.socks) < LINGER_MAX and (self.by_addr.get(key, 0) < LINGER_PER_ADDRESS
                                                     or len(self.socks) < LINGER_MAX // 2)
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

    # The kernel's queue of connections not yet accepted holds as many as the door serves, every lane counted (asked
    # by `listen` in the server's `__init__`, so `bounds` is set first): `socketserver`'s own is 5, and a burst past it
    # was refused by the kernel (a unix socket, on macOS) or its SYN dropped (TCP, a second's retry) — never counted,
    # never answered 503 (the store's role sockets showed it: `configstore._Bounded`).
    @property
    def request_queue_size(self) -> int:
        b = self.bounds
        return b.limit + b.reserve + b.monitor + b.box

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
            reader.floor, reader.lazy = None, False      # …and no body's floor from the request before
        super().handle_one_request()

    # Past the headers the request is its handler's: each operation has the socket's own timeout, and a body is given
    # a deadline of its own by whoever reads it (`SpecConsole.read_body`) — or, read without one, a body's floor from its
    # first read (`DeadlineReader.lazy`; the review's twelfth pass: it was a year). What the handler waits for that is
    # not its client — a device, a peer — no deadline here can end: each door bounds those waits itself (the holder's
    # reads of a device: `VmsWorker._door_read`).
    def parse_request(self):
        ok = super().parse_request()
        self.deadline = float("inf")
        reader = getattr(self.rfile, "raw", None)
        if isinstance(reader, DeadlineReader):
            reader.lazy = True
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
        return parse_json(self.rfile.read(n) or b"{}")   # its digits exactly; `NaN`, `1e400`, a lone surrogate refused


# A REQUEST'S BODY IS A JSON OBJECT, OR A REFUSAL (the review's tenth round, the routes that failed whole). A body that
# is not JSON, is nested past what JSON reads, or is a list went into the route as it was: `POST /<rows>` and `PUT
# /<rows>/<id>` answered 500 "the write failed", `PUT /policy` and the VMS's `POST /requests` no reply at all.
# `Refused` — 400 to whoever sent it, and nothing written.
def object_body(h) -> dict:
    try:
        # A subsystem's route is handed a length and a stream (`headers`, `rfile`), not always this console's handler.
        reader = getattr(h, "_body", None)
        body = reader() if reader is not None else parse_json(h.rfile.read(int(h.headers.get("Content-Length", 0) or 0)) or b"{}")
    except PARSE_ERRORS as e:
        r = Refused(f"the body is not JSON that can be read ({type(e).__name__})")
        r.fault = getattr(e, "fault", "not_json")        # the shared table's word (`canonical.Fault`)
        raise r from None
    if not isinstance(body, dict):
        raise Refused(f"the body is a JSON object, not {type(body).__name__}")
    return body


# The shared table's word for a body that does not read (`object_body`'s `Refused`, a `canonical.Fault`), beside the
# door's own words: `{"fault": "not_json" | "not_number"}`, and nothing for a refusal of anything else (the architect,
# 2026-10-06: every door of the platform answers such a body 400 with `fault`).
def refused_status(e) -> int:
    """400 for a request wrong by the spec; 409 for one refused by the rows standing (`spec.Mismatched`, ADR 0031)."""
    return getattr(e, "status", 400)


def fault_of(e) -> dict:
    f = getattr(e, "fault", "")
    return {"fault": f} if f else {}


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
    # A BODY SENT IN CHUNKS IS NOT AN EMPTY BODY (the product's cross-check of the eleventh review). No door here reads
    # `Transfer-Encoding: chunked`, and with no `Content-Length` its body was read as none: `{}` to the route — a PUT
    # that changed nothing and answered 200, a POST that wrote defaults — and the chunks left on the connection were
    # read as the next request. 400 in words, and the connection closed: what follows the headers is not read.
    if (h.headers.get("Transfer-Encoding") or "").strip():
        h.close_connection = True
        h._send(400, {"detail": "this door takes a body sent whole, with a Content-Length — not in chunks "
                                "(Transfer-Encoding)", "error": "no length"})
        return False
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
    # `sleep` is the wait between polls (injected for tests); `sealer` is the cluster's key ring, when this process
    # holds one (`sealing.py`) — the key the body's digest is made with.
    def __init__(self, vars_, prefix: str, wall, ttl: float = 86400.0, clock=time.monotonic, sleep=time.sleep,
                 sealer=None):
        self.vars, self.prefix, self.wall, self.ttl, self.clock, self.sleep = vars_, prefix, wall, ttl, clock, sleep
        self.sealer = sealer
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

    # Whose request, and of what: `sub` and a digest of the body go into the claim, so a replay is answered only to
    # the same caller with the same body.
    #
    # NEVER A BARE HASH OF A BODY THAT CARRIES A SECRET (the thirteenth review, major 7; a run). It was the body's
    # sha256, kept a day under `<sub>/idem/`: the camera's row held `cred_secret` sealed, and `admin123` and
    # `qwerty2024` came back from the claims by hashing a dictionary of seven words into the body around them —
    # whoever reads the store had the password the key ring was there to keep from him. Now:
    #   a key ring   `mac`: HMAC of the body under a key derived from the ring's (`Sealer.mac`), which the store never
    #                holds; every console of the cluster holds the same ring, so any of them answers the retry
    #   none         `digest`: the sha256 of the body as a page would say it — every `*_secret` masked, every address
    #                hidden (`mask_secrets`) —: nothing in it a dictionary could find (and without a key the row holds
    #                the password in the clear anyway, which the console says once, at the first secret it writes)
    # …and with a ring, the `digest` beside the `mac` (the product's r28-secrets2): a kid removed from the ring within the
    # claim's day left every console unable to make the claim's `mac`, and a correct retry was 422 "key reused". The
    # digest is asked only then — the kid gone —, and says no secret: two bodies that differ only in a `*_secret` are one
    # body to it, as they are to a console without a key.
    def _tag(self, sub, body) -> dict:
        import hashlib
        out = {}
        if sub is not None:
            out["sub"] = str(sub)
        if body is not None:
            raw = body if isinstance(body, bytes) else str(body).encode()
            if self.sealer is not None:
                out["mac"] = self.sealer.mac("idem", raw)
            out["digest"] = hashlib.sha256(self._said(raw)).hexdigest()
        return out

    @staticmethod
    def _said(raw: bytes) -> bytes:
        try:
            body = parse_json(raw or b"{}")              # as the door reads it: `1e400`, a lone surrogate are no JSON
        except PARSE_ERRORS:
            return b"not JSON"                           # refused by whoever reads it; what it held is not kept
        return json.dumps(mask_secrets([{"": body}])[0][""], sort_keys=True).encode()

    # A key is a name for ONE request by ONE caller. Replayed by somebody else, or with another body, it used to be
    # answered with the first caller's reply — a stranger got anna's 201, and anna's own second mark under a reused
    # key was silently not written (the review's second pass, minor). A claim that carries no tag — written before
    # tags, or by a test — matches anybody, as it did.
    #
    # A `mac` made under another kid of the ring (a console a rotation ahead or behind) is asked again under that kid;
    # one this console cannot make — the kid is not in its ring, removed since — is judged by the `digest` beside it, and
    # without one is another body: refused, not answered.
    def _mismatch(self, items: dict, tag: dict, body=None):
        for k in ("sub", "mac", "digest"):
            if k in items and k in tag and items[k] != tag[k]:
                if k == "mac" and self.sealer is not None and body is not None:
                    raw = body if isinstance(body, bytes) else str(body).encode()
                    again = self.sealer.mac("idem", raw, str(items[k]).split(":", 1)[0])
                    if again == items[k] or (again is None and "digest" in items):
                        continue
                return 422, {"detail": "this Idempotency-Key names another request: a key is one caller's, for one body",
                             "error": "key reused"}
        return None

    # Try `put({state: pending, at, sub, mac or digest}, cas=0)`: success means ours to answer — return `None` (the
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
            wrong = self._mismatch(items, tag, body)
            if wrong is not None:
                return wrong                                             # somebody else's key, or another body under it: not this reply
            if items.get("state") == "done":
                self._seen.pop(path, None)
                return int(items["status"]), parse_json(items["body"])
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
    #
    # The copy says every address in the reply as a page does (`hide_in_reply`; the twelfth review, major 16): a refusal
    # that quoted a password — `urlsplit`'s words for a port — was kept here for a day, under a key nobody looks at. The
    # replies that leave are masked where they are made; this is the copy's own floor.
    def store(self, key: str, resp: tuple[int, dict]) -> None:
        if int(resp[0]) >= 500:
            return self.release(key)
        path = self._path(key)
        tag, rev = self._mine.get(path, {}), self._rev.get(path, 0)
        try:
            self.vars.put(path, {"state": "done", "status": resp[0], "body": canonical_json(hide_in_reply(resp[1])), "at": self.wall(),
                                 **tag}, cas=rev)
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
# A row's `labels` as a list of words — none for no row, and none for a value that is not a list.
def _labels(row: dict | None) -> list:
    v = (row or {}).get("labels") or []
    return [str(x) for x in v] if isinstance(v, (list, tuple)) else []


class SpecConsole:
    """One console for every subsystem. `ctl` is the subsystem's SpecController
    holding the console's token."""

    def __init__(self, ctl: SpecController, marks_root: str | None = None, index=None, worst_failover: float = 0.0,
                 wall=None, lost_after: float = 45.0, per_minute: float = 0.0):
        self.ctl, self.spec, self.index = ctl, ctl.spec, index
        self.worst_failover, self.wall, self.lost_after = worst_failover, wall or ctl.wall, lost_after
        self.instance = f"{socket.gethostname()}:{os.getpid()}"
        self.marks_root = marks_root
        # Whether this console's `/metrics` carries the platform's own lines (`platform_metrics`): a console alone
        # does; in a `Mount` only the root does (`Mount._adopt`), so a scrape of every page says each fact once.
        self.says_platform = True
        # …and whether it serves a page at `/` (`page_of`): a console alone does; in a `Mount` only the root, for its
        # root subsystem — a mounted one's units are shown by the module on the root's page (КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md §1).
        self.serves_page = True
        # How many events a minute one operator is expected to read. Past it the timeline stops showing
        # lines and starts showing counts — see `timeline`. The number belongs to the CONSOLE and not to a
        # subsystem's policy, because the screen merges every subsystem and the attention it competes for
        # is one person's; and it is a number rather than a constant because a control room with four
        # screens and a guard with a phone are not the same reader.
        self.per_minute = float(os.environ.get("EVENTS_PER_MINUTE", per_minute) or PER_MINUTE)
        self.marks = EventLog(marks_root, CONSOLE_MARKS, self.instance, 1) if marks_root else None   # the console's own log: one writer, so epoch 1
        self.journal = Journal(marks_root, "console", self.wall)   # what was done through this console, and by whom (`journal.py`)
        from .door import Signer
        # signs the holders' door tokens with the key in the store (`door/signer`, sealed with the cluster's key ring);
        # None without a ring to seal one with: the doors' open mode
        self.door_signer = Signer.for_console(ctl.vars, getattr(ctl, "sealer", None))
        self.gate = Gate(ctl.vars, self.wall, lambda: self.journal)   # who is calling, and may they (`access.py`)
        self.seen = IdempotencyKeys(ctl.vars, f"{self.spec.name}/idem/", self.wall,   # in the store: any instance answers a retry
                                    sealer=getattr(ctl, "sealer", None))                 # its digests under the cluster's key
        self.epoch_policy: dict[str, str] = {self.spec.name: self.spec.older_epochs}   # replaced by the Mount's shared one
        self.ledgers_garbled: set[str] = set()           # people's request ledgers this console found unreadable (`_file_request`)
        self.clock = time.monotonic                      # ages the caches below; a test sets its own
        self._scan: tuple[float, dict] = (-1e9, {})
        self.scans = 0
        self._epochs: tuple[float, dict] = (-1e9, {})
        self.epoch_scans = 0
        # The subsystems this console's process serves, by name — what a reference `<sub>/<id>` is looked up in: its
        # row, what it is about (`about`), the labels a grant is matched against. Alone, this console; in a `Mount`,
        # one dict shared by every console of it (`Mount._adopt`).
        self.units: dict[str, "SpecConsole"] = {self.spec.name: self}

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
    # `/spec`'s body: `{name, rows, id, fields: [{name, type, default, required}], door?, places?, metrics: {prefix,
    # running}}` — the page's only knowledge of the subsystem. What a holder serves a page is `door: {routes}`; the
    # table whose rows a place's holder is asked by, `places: {table}` (`/where/<table>/<place>`).
    def shared_route(self, sub: str, q: dict) -> tuple[int, dict]:
        """`GET /domain/shared/<sub>`: what the domain holds for a subsystem's shared fields, resolved by the platform
        (`domain/shared.py`: `inherit` and `merge` applied) from the copy this cluster's agent took and verified — for a
        unit of this console's own subsystem with `?unit=<id>`."""
        from w2cplatform.domain import declared
        from w2cplatform.domain.shared import SharedView, door
        s = declared.spec(sub)
        if s is None or not s.domain.shared:
            return 404, {"error": "no such shared settings", "detail": f"{sub!r} shares no field with the domain"}
        row = None
        if q.get("unit"):
            if sub != self.spec.name:
                return 400, {"error": "not this console's", "detail": f"a unit of {sub} is resolved by its own console"}
            row = next((r for r in self.ctl.units() if str(r.get("id")) == str(q["unit"])), None)
            if row is None:
                return 404, {"error": "no such unit", "detail": f"{sub} has no unit {q['unit']!r}"}
        return 200, door(s, SharedView(self.ctl.vars, self.ctl.objects, self.wall).document(), row)

    # A BOOK SHOWN (ADR-0010, the addition of 2026-10-06; ADR-0061): of each entry of this cluster's own copy of the book
    # (`domain/<sub>/<book>`, which the agent carried home), the fields the spec's `show` names, and nothing else — the
    # rest of an entry (the roads, and the tokens on them) is in the same JSON and stays in this process; so does a
    # `*_secret` item, and an entry that is no JSON object. WHO SEES AN ITEM («Архитектор» 2026-10-06): an item whose key
    # is the `domain.ref` of a unit of this cluster, whoever may `view` that unit; a view of the whole cluster, every item;
    # an item no unit here is keyed by, only that view. The operator of one unit sees where it is kept, wherever
    # that is. The gate before this asked for any grant at all (`needs`: a GET naming no unit): nobody with no view gets
    # here — 403. A member answers its own book and no other: what another member's book says is that cluster's to tell,
    # through `/domain/at/…`. The product's `ConsoleDoor.book`, word for word.
    def book_route(self, h, method: str, s, book: str) -> tuple[int, dict]:
        if method != "GET":
            return 405, {"error": f"GET /domain/{s.name}/books/<book>"}
        show = s.domain.show.get(book)
        if not show:
            detail = f"{s.name} declares no book {book}"
            if book in s.domain.books:
                detail = f"{s.name}'s book {book} is carried and not shown: its spec names no field of it to show"
            return 404, {"error": "no such book shown", "detail": detail}
        key = f"{s.domain_prefix}{book}"
        sees = self._visible(h)
        every = sees is None or sees("*", [])
        try:
            items, _ = self.ctl.vars.get(key)
            units = {} if every else self.units_by_ref(s)
        except OSError as e:
            return 503, {"error": "the store did not answer", "detail": no_paths(e)}
        out = {}
        for item, raw in sorted((items or {}).items()):
            if is_secret_field(item):
                continue
            if not every and (item not in units or not sees(*units[item])):
                continue
            try:
                entry = json.loads(raw)
                if not isinstance(entry, dict):
                    raise TypeError(f"not a JSON object ({len(str(raw))} bytes)")
            except PARSE_ERRORS as e:                    # what it holds is not said: an entry carries tokens
                BOOK_ENTRIES.garbled(f"{key}#{item}", e if isinstance(e, TypeError) else type(e).__name__)
                continue
            BOOK_ENTRIES.parsed(f"{key}#{item}")
            out[item] = {f: entry[f] for f in show if f in entry}
        return 200, out

    # This cluster's units of `s` by their `domain.ref` (`id`: the id itself), each as a grant is asked about it
    # (`target_of_row`: its labels, the unit it is about) — for a book whose items are keyed by the ref. A subsystem this
    # process does not serve has none here: its items are a view of the whole cluster's.
    def units_by_ref(self, s) -> dict:
        con = self.units.get(s.name)
        if con is None or not s.domain.ref:
            return {}
        out = {}
        for row in con.ctl.units():
            ref = row.get("id") if s.domain.ref == "id" else row.get(s.domain.ref)
            if ref not in (None, ""):
                out[str(ref)] = self.target_of_row(con, row, con.spec.ref(row["id"]))
        return out

    def describe(self) -> dict:
        return describe(self.spec)

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
                    except PARSE_ERRORS:                 # `epoch: Infinity` too (`int(inf)`; the tenth round's sweep)
                        log.warning("%s: epoch row %s does not parse: its events are not fenced", self.spec.name, p)
            except OSError as e:
                log.warning("%s: the store did not answer the epochs (%s): the timeline is fenced by the last ones read", self.spec.name, e)
                self.epochs_stale = True
                return self._epochs[1]
            self._epochs, self.epochs_stale = (now, out), False
            self.epoch_scans += 1
        return self._epochs[1]

    # The epochs of the units IN an answer — a camera's, or one unit's: a handful of rows read by name, no scan,
    # and read now, so a fence that fell a moment ago shows. `pairs` is `{(subsystem, unit)}`. `refused`, when given,
    # collects the subsystems whose epoch rows this console may not read (its rights in the store).
    def epochs_of(self, pairs, refused: set | None = None) -> dict:
        out = {}
        for sub, unit in pairs:
            try:
                e = current_epoch(self.ctl.vars, f"{sub}/epoch/{unit}")
            except (*PARSE_ERRORS, OSError):
                continue                                 # no epoch row, a torn one, or no store: the events stand as their resource marked them
            except Exception:                            # noqa: BLE001 — the store's refusal (М11's rights): not its to read
                if refused is not None:
                    refused.add(sub)
                continue
            if e:
                out[(sub, unit)] = e
        return out

    # THE HOLDER'S DOOR, HANDED OUT WITH THE UNIT'S PLACE (the boundary's step 6, the owner's decision 1: the bytes do not
    # go through the console). For a spec that declares `door: {routes}`, `/where/<id>` says `door: {url, token, expires,
    # routes}` — the door the holder announces in its heartbeat (`url`, the product's word), and a token for those routes,
    # this unit, this holder, `door.TTL` seconds, signed by the cluster's door key (`door/signer` in the store; with no key
    # ring to seal one, the door's open mode, `token: null`). The gate asked `view` on the unit before this line: that is the grant the token carries. THE holder is the
    # worker the unit is placed on, live, saying in its heartbeat that it holds the unit — not any heartbeat that
    # still lists it (a dead holder's last word, read for the first time, looks new). Nobody holding it so, or a holder
    # that announces no door: `door: null`, and the page asks again. Each token handed out is a
    # line `door.issued` — who, which unit, which holder, until when: what the console can say of bytes it never sees.
    def door_of(self, h, uid) -> dict:
        routes = self.spec.door_routes
        if not routes:
            return {}
        pl = self.ctl.placement(uid)
        hb = holders(self.ctl.objects, f"{self.spec.name}/", self.wall(), self.lost_after, self.ctl.eyes).get(pl.worker) if pl else None
        holds = hb is not None and any(str(st.get("id")) == str(uid) for st in hb.status)
        url = str(hb.extra.get("url") or "").rstrip("/") if holds else ""
        if not url:
            return {"door": None}
        return {"door": self.door_at(h, uid, pl.worker, url)}

    # The door of `holder` at `url`, opened for unit `uid`: a token for the spec's routes, this unit, this holder — or
    # none, in the open mode. Every token handed out is a line `door.issued`.
    def door_at(self, h, uid, holder: str, url: str, **said) -> dict:
        routes = self.spec.door_routes
        if self.door_signer is None:
            return {"url": url, "token": None, "expires": None, "routes": list(routes)}
        user, unit = h.headers.get("X-User", "operator"), self.spec.ref(uid)
        token, exp = self.door_signer.issue(user, unit, holder, routes, self.wall())
        self.journal.say("door.issued", sub=self.spec.name, target=str(uid), user=user, holder=holder,
                         routes=",".join(routes), until=round(exp), **said)
        return {"url": url, "token": token, "expires": exp, "routes": list(routes)}

    # WHERE A PLACE IS HELD — `GET /where/<table>/<place>?unit=<sub>/<id>` (the architect's decision after step 7: the
    # console has no byte routes of its own, and what a unit left in a place another worker holds now is read at THAT
    # worker's door). The table is the spec's table of places (`placement.places`), the place one of its rows that says
    # `where`; its holder is the live worker whose heartbeat names the place in the spec's `place_by` field — the one the
    # place's live hold names, where a hold says so — and announces a door (`url`). The answer is `/where/<id>`'s: the
    # worker and `door: {url, token, expires, routes}`, the token for the spec's routes, THAT holder and the unit named
    # in `?unit=` (the gate asked `view` on it before this line, as on `/where/<id>`). No unit named: the holder, and no
    # door — a token is always one unit's. Nobody holding the place: 404, `door: null`, and the place as
    # `<place>@<server>` (its row's `server_field`) in `unreachable` and in the header `X-Unreachable` — what a page
    # names as missing from its picture.
    def where_place(self, h, place: str, q: dict) -> tuple:
        from .metrics import matches
        t = self.spec.places
        try:
            row = self.ctl.table_rows(t["table"]).get(place)
        except OSError:
            return 503, {"detail": "the store did not answer", "error": "store unavailable"}
        if row is None or not matches(row, t["where"]):
            return 404, {"worker": None, "place": place, "door": None, "detail": f"{place!r} is not a place of "
                         f"{self.spec.name} (a row of {t['table']} that says {t['where'] or 'anything'})",
                         "error": "no such place"}
        server = str(row.get(t["server_field"]) or "") if t["server_field"] else ""
        uid = None
        if q.get("unit"):
            got = parse_ref(q["unit"])
            if got is None or got[0] != self.spec.name:
                return 400, {"detail": f"a door of {self.spec.name} opens for a unit of {self.spec.name}, "
                                       f"not {q['unit'][:80]!r}", "error": "not this console's"}
            try:
                uid = self._uid(f"/where/{got[1]}")
            except Refused as e:
                return 400, {"detail": str(e), "error": "not an id"}
        found = self.place_holder(place)
        if found is None:
            gone = f"{place}@{server}"
            h._extra_headers = (("X-Unreachable", gone),)
            return 404, {"worker": None, "place": place, "server": server, "door": None, "unreachable": gone,
                         "reason": f"nobody holds {place} now: what is there is unavailable until a worker takes it"}
        worker, url = found
        door = self.door_at(h, uid, worker, url, place=place) if uid is not None and self.spec.door_routes else None
        return 200, {"worker": worker, "place": place, "server": server, "door": door}

    # `(worker, door url)` of the live worker holding `place` now, or None. Several heartbeats naming one place — a
    # holder that died and its successor, both fresh to this console for a moment — are told apart by the place's live
    # hold (`<sub>/holds/<place>`: its holder instance); with no hold to ask, the first by name.
    def place_holder(self, place: str):
        try:
            held = self.ctl.live_holds().get(place)
        except OSError:
            held = None
        found = []
        for w, hb in sorted(holders(self.ctl.objects, f"{self.spec.name}/", self.wall(), self.lost_after,
                                    self.ctl.eyes).items()):
            url = str(hb.extra.get("url") or "").rstrip("/")
            inst = str(hb.extra.get("instance") or "")
            if str(hb.extra.get(self.spec.place_by, "")) != place or not url or (held and inst and inst != held):
                continue
            found.append((w, url))
        return found[0] if found else None

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
    # `<p>_failover_seconds{kind="worst"}`; and `<p>_<running_gauge>` — the count of status entries in phase
    # `running` on live workers (`vms_cameras_running`). The page reads two of these for its status line. The
    # RESOURCES are the platform's, not a subsystem's: `w2c_resources_live` and `w2c_resource_*` (`platform_metrics`),
    # said once per console process — by the root of a `Mount`, or by a console alone — and not once per subsystem
    # under its prefix (the course's decision on the platform's names: `vms_resources_live`, `rec_resources_live`, …
    # were one fact said as many times as there were subsystems mounted).
    # The servers this subsystem runs on, as the placement sees them: every server a worker heartbeats from
    # or a resource heartbeats from — the state of its resource (`live`, `silent`, `unreachable` — it writes to the
    # store but its heartbeat cannot be read here — or `unknown`), its workers with load and capacity, and whether the controller would place
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
        hbs = heartbeats(ctl.objects, ctl.sub.name + "/")
        here = [w for w in hbs if ctl.server_of(w) == server]
        units = sum(len(ctl.assignment(w).units) for w in here)
        strand = ctl.would_strand(server)
        # No units left is not the whole answer: a worker may hold writes it has not made durable yet — a buffer on
        # this machine's disk — and they go with the machine. Every worker says how many in its heartbeat
        # (`pending_writes`, `Worker.pending_writes`); one that does not say, or says a word, is not known to be done.
        pending, unsaid = 0, []
        for w in here:
            n = number(f"{ctl.sub.heartbeat_key(w)}#pending_writes", hbs[w].extra.get("pending_writes"), int, None)
            if n is None:
                unsaid.append(w)
            else:
                pending += n
        return {"draining": server, "subsystem": ctl.spec.name, "workers": sorted(here), "units": units,
                "pending_writes": pending, **({"pending_unsaid": sorted(unsaid)} if unsaid else {}),
                "would_strand": strand, "safe": units == 0 and pending == 0 and not unsaid}

    # One look at the store for the whole answer (`contract.one_pass`, on this door's thread): each server's
    # `decommission_refusal` and each worker's `slot_fate` ask the heartbeats and the resources, and outside a pass every
    # asking was a listing of them all.
    def servers(self) -> dict:
        with self.ctl.one_pass():
            return self._servers()

    def _servers(self) -> dict:
        ctl, now = self.ctl, self.wall()
        out: dict[str, dict] = {}
        for w, hb in heartbeats(ctl.objects, ctl.sub.name + "/").items():
            # (No `archive` here any more: what a server holds of a subsystem's tables is the spec's `servers.show`, which
            # the page reads with `/spec` — the boundary's step 6; it was one subsystem's heartbeat field, read here.)
            s = out.setdefault(hb.extra.get("server", "?"), {"resource": "unknown", "workers": []})
            s["workers"].append({"worker": w, "load": ctl.load(w), "capacity": ctl.capacity_of(w), "labels": hb.extra.get("labels", ""),
                                 # WHERE this worker is, in whatever the spec counts places in (`place_by`): the server
                                 # unless the spec names a field of the heartbeat. The page needs it to offer the
                                 # places that exist when a unit is created — a `home` field names one of these.
                                 "place": ctl.place_of(w),
                                 # …by what this console saw change, on its clock (the review's thirteenth pass)
                                 "state": "live" if ctl.eyes.fresh(ctl.sub.heartbeat_key(w), hb.token, self.lost_after, hb.ts,
                                                                   ctl.sub.name) else "stale", "idle_by_policy": False,
                                 # …and what the spec's `servers.status` names of its heartbeat, as it is written there
                                 **({"status": self._status_of(w, hb)} if ctl.spec.servers_status else {})})
        for w in ctl.idle_by_policy(list(heartbeats(ctl.objects, ctl.sub.name + "/"))):    # servers: distinct — one worker per server carries units
            for s in out.values():
                for row in s["workers"]:
                    if row["worker"] == w:
                        row["idle_by_policy"] = True
        # A worker that stopped renewing, as the controller judges it (`Controller.slot_fate` — the one rule): `hung`, and
        # since when, is a FAULT the page names — its process runs on a server that answers, and nothing is moved off it;
        # its slot's `until`, null for a row that does not parse (`slot_garbled`); the places each holds.
        held = ctl.holds_by()
        # …and whether another process wants its name (the owner's decision of 4 Oct; the product's field): who holds it,
        # and who else asks, from which box, since when — `name_conflict`, null when nobody does.
        contended = contenders(ctl.objects, ctl.sub, now, ctl.eyes)
        for s in out.values():
            for row in s["workers"]:
                self._judged(row, held)
                cs, holder = contended.get(row["worker"]), row.pop("_holder", "")
                row["name_conflict"] = name_conflict(holder or cs[0].get("holder") or "", cs, now) if cs else None
        for server in resources_seen(ctl.objects):
            out.setdefault(server, {"resource": "unknown", "workers": []})
        # What the server reaches (feedback DQ): the node's word (its workers' heartbeats), the administrator's when there
        # is a row, and which of the two placement reads — both shown, so a node and an administrator who disagree are
        # seen to. A server with a row and no worker is listed too: the row is still the administrator's word on it.
        rows = ctl.server_labels() or {}
        for server in rows:
            out.setdefault(server, {"resource": "unknown", "workers": []})
        drains, asked, marks = ctl.draining(), ctl.decommission_requests(), ctl.decommission_marks()
        for server in {*asked, *marks}:
            out.setdefault(server, {"resource": "unknown", "workers": []})
        res, held = ctl._resources(), ctl.holds_by()
        for server, s in out.items():
            node = sorted({l for row in s["workers"] for l in str(row["labels"]).split(",") if l})
            s["labels_node"] = node
            # …as placement reads it (`server_labels_of`): "unknown" — its row is there and did not read (the tenth pass),
            # or this console has never read the rows (ADR-0026's addition) — is the product's word, which the module
            # shows; the labels are then what its row last said, or none
            said, s["labels_source"] = ctl.server_labels_of(server)
            s["labels"] = node if s["labels_source"] == "node" else sorted(said or ())
            s["draining"] = server == drains
            s["resource"] = ctl.resource_state(server, self.lost_after)
            s["resource_heard_at"] = float(res[server]["ts"]) if server in res else None
            # …and what the resource says of itself: its address, and the disk under it (`space: {total, free}`, bytes)
            s["resource_url"] = str(res[server].get("url") or "") if server in res else ""
            sp = res[server].get("space") if server in res else None
            s["space"] = ({"total": number(f"{server}#space.total", sp.get("total"), int, 0),
                           "free": number(f"{server}#space.free", sp.get("free"), int, 0)} if isinstance(sp, dict) else None)
            # The operator's decommission (`platform/decommission/<server>`) and what this subsystem's controller did
            # about it (`<sub>/decommissioned/<server>`); whether it may be asked now, and why not — the sign that the
            # server answers — or the warning that its resource was never heard; and the places its workers held, which
            # a decommission does not give back (`lost`). The product's fields.
            s["decommission"] = {k: str(asked[server].get(k, "")) for k in ("by", "at", "why")} if server in asked else None
            s["decommissioned"] = ({k: str(marks[server].get(k, "")) for k in ("asked_at", "at", "slots", "units", "holds")}
                                   if server in marks else None)
            try:
                refusal, warning = ctl.decommission_refusal(server)
                refusal = ctl.not_watched_yet(refusal)       # a console just started says so (the thirteenth pass)
            except (*PARSE_ERRORS, OSError) as e:        # a row that does not read: that server's answer, not the page's end
                refusal, warning = f"could not be told: {e}", None
            s["decommission_refusal"], s["decommission_warning"] = refusal, warning
            s["decommissionable"] = refusal is None and server not in asked
            s["lost"] = ([{"place": p, "worker": row["worker"]} for row in s["workers"] for p in held.get(row["worker"], [])]
                         if server in asked else [])
            s["requires_resource"] = ctl.spec.requires == "resource"
            s["placeable"] = (not (s["requires_resource"] and s["resource"] == "silent") and not s["draining"]
                              and server not in asked)
            s["why"] = (f"server {server} decommissioned" if server in asked else
                        f"server {server} draining" if s["draining"] else
                        f"resource on {server} silent" if not s["placeable"] else None)
            s["workers"].sort(key=lambda x: x["worker"])
        # The titles of the workers' `status` once, as the spec wrote them (`servers.status`): the page sums each field over
        # a server's workers and titles it — the platform shows what the heartbeats say and adds nothing up.
        return {"policy": ctl.policy(), "servers": dict(sorted(out.items())),
                **({"status": ctl.spec.servers_status} if ctl.spec.servers_status else {})}

    # A worker's heartbeat fields the spec's `servers.status` names, AS THE HEARTBEAT CARRIES THEM: a string of
    # `heartbeat.strings` (one that is not a string never got here — the heartbeat was garbled, `parse_heartbeat`), any
    # other a JSON number — a word there (`"5"` too), `true`, a list or an object is counted as a garbled field (the
    # rows' count, `FIELDS`, as `number` counts it) and left out. A path (`writer.state`) goes into the heartbeat's maps
    # by its dots (`_status_path`), and its leaf is a string or a number — a map's leaf says what it is, no
    # `heartbeat.strings` names it —, or it is counted and left out the same way (ADR 0057, «Архитектор» 2026-10-06; the
    # reading of `metrics[].from`, the product's `statusOf`). A field the heartbeat does not carry — or a map on the way
    # that is not there — is absent, not null: "nothing said" is not "said nothing".
    def _status_of(self, w: str, hb) -> dict:
        spec, out = self.ctl.spec, {}
        for e in spec.servers_status:
            f = e["field"]
            said, v = _status_path(hb.extra, f)
            if not said:
                continue
            leaf = "." in f and isinstance(v, str)
            if f in spec.heartbeat_strings or FIELDS.read(f"{self.ctl.sub.heartbeat_key(w)}#{f}",
                                                           lambda: v if leaf else _json_number(v), None) is not None:
                out[f] = v
        return out

    def _judged(self, row: dict, held: dict) -> None:
        w, ctl = row["worker"], self.ctl
        row.update(holds=held.get(w, []), hung=False, hung_since=None, slot_garbled=False, slot_until=None)
        try:
            key = ctl.sub.slot_key(w)
            from .contract import SLOTS, stored
            items, rev = stored(ctl.vars, key, SLOTS)    # one the store cannot read: garbled, as one that does not parse
            if not items:
                return                                   # a name no process claimed (one given in the unit file): no slot to judge
            slot = read_slot(key, w, items)
            row["slot_garbled"], row["slot_until"] = slot is None, (slot.until if slot is not None else None)
            row["_holder"] = slot.holder if slot is not None else ""      # whose the name is, for `name_conflict`
            if slot is not None and slot.released:
                row["released"] = True
                return
            # The controller's verdict at the revision read — the judge that has watched the rows change (the review's
            # thirteenth pass, blocker 4); else this console's own eyes, by the controller's limit (`slot_fate`)
            from .contract import published_hung_limit, published_names
            said = (published_names(ctl.objects, ctl.sub, "fates") or {}).get(w)
            if isinstance(said, dict) and str(said.get("rev")) == str(rev) and isinstance(said.get("fate"), str):
                fate, why, since = said["fate"], str(said.get("why", "")), number(f"{key}#since", said.get("since"), float, None)
            else:
                fate, _, why = ctl.slot_fate(w, slot, hung_after=published_hung_limit(ctl.objects, ctl.sub))
                since = ctl.eyes.wall_of(ctl.hung_since(w, slot)) if fate == "hung" else None
            if fate == "hung":                           # since when, on a wall clock, for the page
                row.update(hung=True, hung_since=since, hung_why=why)
        except (*PARSE_ERRORS, OSError):
            return                                       # a name that is no key, a store that did not answer: that row says nothing of it

    # EVERY NUMBER OF A HEARTBEAT OR OF THE PASS REPORT HERE IS READ THROUGH `n`, `rn` OR `r` (the review's seventh
    # pass, part 2): read bare — `int(headroom)`, `float(space.full)`, `float(ts)` — one word in one field raised, and
    # the whole page of the subsystem's metrics was gone, every alert with it. `SpecController._number` had closed it
    # for placement; the page had not. A field that is a word (or `nan`, `inf`) is read as not said — 0, or -1 for an
    # age — counted once per object and field (`rows.number`), and the rest of the page stands.
    def metrics_text(self) -> str:
        p = self.spec.name
        hbs = heartbeats(self.ctl.objects, p + "/"); now = self.wall()
        live = {w: hb for w, hb in hbs.items()            # by what this console saw change (the thirteenth pass)
                if self.ctl.eyes.fresh(self.ctl.sub.heartbeat_key(w), hb.token, self.lost_after, hb.ts, p)}
        hk = self.ctl.sub.heartbeat_key
        failover = self.ctl.failover_seconds()

        def n(w: str, field: str, kind=float, default=0):                # a worker's field
            return number(f"{hk(w)}#{field}", hbs[w].extra.get(field), kind, default)
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
                 # `worst` is the largest this process measured, not the largest of the last ones; a failover measured
                 # on no one clock is not a number here but a count (`SpecController.failover_seconds`, the ninth review).
                 f"# TYPE {p}_failover_seconds gauge",
                 f'{p}_failover_seconds{{kind="worst"}} {max([self.worst_failover, getattr(self.ctl, "failover_worst", 0.0), *failover.values()])}',
                 *[f'{p}_failover_seconds{{kind="last",worker="{label(w)}"}} {s}' for w, s in sorted(failover.items())],
                 f"# TYPE {p}_failovers_unmeasured gauge", f"{p}_failovers_unmeasured {getattr(self.ctl, 'failovers_unmeasured', 0)}",
                 # What the readers of heartbeats skipped and measured (the review's second pass, M6, M9): objects that did
                 # not parse, since this process started; and the furthest a heartbeat's clock has been AHEAD of this
                 # one's — at `FUTURE_TOLERANCE` such a worker stops counting as live.
                 f"# TYPE {p}_heartbeats_garbled counter", f"{p}_heartbeats_garbled {GARBLED.get(p, 0)}",
                 f"# TYPE {p}_heartbeat_skew_seconds_max gauge", f"{p}_heartbeat_skew_seconds_max {round(SKEW_MAX.get(p, 0.0), 1)}",
                 f"# TYPE {p}_heartbeat_skew_seconds_min gauge", f"{p}_heartbeat_skew_seconds_min {round(SKEW_MIN.get(p, 0.0), 1)}"]
        # How far behind the copy the layer above reads is. The controller publishes every pass and has no
        # port; this is read from the store, so a failing publish shows up here as a number that climbs,
        # rather than only as a log line on a host nobody is looking at. `-1` distinguishes "never
        # published" from "published a moment ago" — a gauge that is 0 for both would hide a cluster whose
        # controller has never once succeeded.
        age = self.ctl.snapshot_age(now)
        lines += [f"# TYPE {p}_snapshot_age_seconds gauge",
                  f"{p}_snapshot_age_seconds {-1 if age is None else round(age, 1)}"]
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
                  # units the last pass moved or unplaced because their server no longer reaches them (feedback DQ)
                  f"# TYPE {p}_units_moved_for_reach gauge", f"{p}_units_moved_for_reach {r('reach_moves', int)}",
                  # …and as a counter (the review's tenth pass): the last pass's number is seen only by a scrape that
                  # falls on it
                  f"# TYPE {p}_units_moved_for_reach_total counter",
                  f"{p}_units_moved_for_reach_total {r('reach_moves_total', int)}",
                  # The controller's releases and the operator's decommissions (the owner's decision on the review's
                  # eleventh pass; the product's names): decommissions carried out, slots released (a worker its server
                  # lists nowhere, every slot of a decommissioned server), requests whose server still answers, and
                  # workers whose process runs and that neither renew nor speak — a fault, `worker.hung`
                  f"# TYPE {p}_servers_decommissioned_total counter",
                  f"{p}_servers_decommissioned_total {r('servers_decommissioned_total', int)}",
                  f"# TYPE {p}_slots_released_total counter", f"{p}_slots_released_total {r('slots_released_total', int)}",
                  f"# TYPE {p}_decommission_requests_standing gauge",
                  f"{p}_decommission_requests_standing {r('decommission_requests_standing', int)}",
                  f"# TYPE {p}_workers_hung gauge",
                  f"{p}_workers_hung {len(rep.get('workers_hung')) if isinstance(rep.get('workers_hung'), list) else 0}",
                  # slots nobody can judge (`wait`, `unsure`) with units on them, and those units: written by nobody until
                  # judged — and live workers whose name is not beside their lock (the review's twelfth pass, blockers 5, 3)
                  f"# TYPE {p}_workers_hung_moved_total counter",
                  f"{p}_workers_hung_moved_total {r('workers_hung_moved_total', int)}",
                  # …and those nobody could judge (`unsure`), moved past the same limit
                  f"# TYPE {p}_workers_unsure_moved_total counter",
                  f"{p}_workers_unsure_moved_total {r('workers_unsure_moved_total', int)}",
                  f"# TYPE {p}_workers_unjudged gauge",
                  f"{p}_workers_unjudged {len(rep.get('workers_unjudged')) if isinstance(rep.get('workers_unjudged'), list) else 0}",
                  f"# TYPE {p}_units_unjudged gauge", f"{p}_units_unjudged {r('units_unjudged', int)}",
                  f"# TYPE {p}_workers_presence_unsaid gauge",
                  f"{p}_workers_presence_unsaid {len(rep.get('workers_presence_unsaid')) if isinstance(rep.get('workers_presence_unsaid'), list) else 0}",
                  # names a live instance holds and another process asks for — of another box, or left nobody on its own
                  # (the owner's decision of 4 Oct; the product's name): `worker.name_conflict`, `/servers`' `name_conflict`
                  f"# TYPE {p}_name_conflicts gauge", f"{p}_name_conflicts {r('name_conflicts', int)}",
                  # units of groups left whole on a server that no longer reaches them, and servers whose labels row did
                  # not read on the pass's last read (the eleventh review: each was a log line or a page only)
                  f"# TYPE {p}_units_waiting_for_reach gauge", f"{p}_units_waiting_for_reach {r('reach_waiting', int)}",
                  # …and the moves a pass may make for reach (`REACH_BUDGET`): in the pass report, and here beside the
                  # units it holds back (the review's thirteenth pass, «Вопросы» 2)
                  f"# TYPE {p}_reach_budget gauge", f"{p}_reach_budget {r('reach_budget', int)}",
                  # …and units left on a worker that is leaving, a group no live worker takes whole among them (the
                  # review's twelfth pass, blocker 7)
                  f"# TYPE {p}_units_left_on_leaving gauge", f"{p}_units_left_on_leaving {r('units_left_on_leaving', int)}",
                  f"# TYPE {p}_servers_labels_unread gauge", f"{p}_servers_labels_unread {r('servers_labels_unread', int)}",
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
        # …and the same counters as this process counted them for this subsystem, by table (`rows.Table`): what its
        # readers in this process could not read — the rows of the tables it serves, a subsystem's own tables it reads.
        lines += [f"# TYPE {p}_console_rows_garbled counter",
                  *[f'{p}_console_rows_garbled{{table="{label(name)}"}} {tables[name].get(p, 0)}' for name in sorted(tables)]]
        # …and the people's request ledgers this console found unreadable, now (`_file_request`): each a person who
        # files nothing until an administrator deletes the row.
        if "per_person" in self.spec.requests:
            lines += [f"# TYPE {p}_requests_ledger_garbled gauge", f"{p}_requests_ledger_garbled {len(self.ledgers_garbled)}"]
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
        places = self.places_needed(live) if self.spec.places else None
        spares = self.spares_lines(rep, now, hbs, places or 0) if self.spec.offers else []
        lines += spares or (self.places_lines(places) if places is not None else [])   # one `workers_needed` series
        from . import metrics
        lines += metrics.lines(self.spec, self.ctl, hbs, live, now)   # the subsystem's own numbers, as its spec declares them
        if self.says_platform:
            lines += self.platform_metrics(now)                # the platform's, once per console process
        return "\n".join(lines) + "\n"

    # THE PLATFORM'S OWN NUMBERS: the resources, under the platform's name `w2c` — one resource per server, whatever
    # subsystems write into it, so one set of lines per console process and not one per subsystem (`metrics_text`).
    # Every number of a heartbeat through `rn`, as above (the review's seventh pass).
    PLATFORM = "w2c"

    def platform_metrics(self, now: float) -> list[str]:
        p, res = self.PLATFORM, resources_seen(self.ctl.objects)

        def rn(server: str, field: str, value, kind=float):               # a resource's field
            return number(f"platform/resources/{server}/heartbeat#{field}", value, kind)
        lines = [f"# TYPE {p}_resources_live gauge",
                 f"{p}_resources_live {sum(1 for s in res if self.ctl.resource_state(s, self.lost_after) == 'live')}",
                 # resource heartbeats that did not parse, since this process started (the review's second pass, M6)
                 f"# TYPE {p}_resource_heartbeats_garbled counter", f"{p}_resource_heartbeats_garbled {GARBLED.get('platform', 0)}"]
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
                  # …a pass that has not moved past the pulse's limit, and the volumes a look did not answer in time
                  # (the review's thirteenth pass, blocker 5): the resource beats on — these say what it cannot do
                  f"# TYPE {p}_resource_pass_stuck_seconds gauge",
                  *[f'{p}_resource_pass_stuck_seconds{{server="{label(s)}"}} {rn(s, "pass_stuck", hb.get("pass_stuck", 0), float)}' for s, hb in sorted(res.items())],
                  f"# TYPE {p}_resource_volumes_stuck gauge",
                  *[f'{p}_resource_volumes_stuck{{server="{label(s)}"}} {len(hb["volumes_stuck"]) if isinstance(hb.get("volumes_stuck"), dict) else 0}' for s, hb in sorted(res.items())],
                  # …and the buckets past their days `retain` could not remove (the review's thirteenth pass, major 13)
                  f"# TYPE {p}_resource_retain_failures_total counter",
                  *[f'{p}_resource_retain_failures_total{{server="{label(s)}"}} {rn(s, "retain_failed", hb.get("retain_failed", 0), int)}' for s, hb in sorted(res.items())],
                  f"# TYPE {p}_resource_mirror_too_big_total counter",
                  *[f'{p}_resource_mirror_too_big_total{{server="{label(s)}"}} {rn(s, "mirror.too_big", said(hb, "mirror").get("too_big"), int)}' for s, hb in sorted(res.items())]]
        # …and the request rows this process's housekeeping ended unanswered (`requests.py`): expired, or not known
        from . import requests
        return lines + requests.metrics_lines()

    # WHAT A HOST'S SPARES SCRIPT READS (the М11 rework; the product's names): `<p>_workers_needed{labels}` — the empty
    # set's row always — `<p>_units_short{labels}`, `<p>_spare_offers{labels}` from the controller's pass report
    # (`SpecController.offer_spares`), and `<p>_server_labels{server,labels,source}`: what each server reaches, the
    # console's row (`source="console"`), its workers' word (`"node"`), or not known (`"unknown"`: its row did not read,
    # or this console has never read the rows — what its row last said, or none). On `/metrics`, which asks no token — and ONLY
    # while the pass is at most `SPARES_FRESH` old: a script reading the number of a controller that stopped would start
    # processes for a shortage that may be long gone. A stale pass: none of the four, and `w2c-spares.sh` starts nothing.
    SPARES_FRESH = 60.0

    # …and for a subsystem placed by its rows (`placement.places`): `<p>_workers_needed{labels=""}` — the places that say
    # `where` and that no live hold names, less the live workers that hold no place. Read here, on every scrape, from the
    # store and the heartbeats this console reads anyway: no offer is written (a spare takes a free place by itself).
    #
    # ONE SERIES, WHATEVER SAYS IT (a spec with both `offers` and `places`): the spares' empty set and the free places were
    # each `<p>_workers_needed{labels=""}` with a TYPE line of its own — two TYPE lines and a duplicate series, and
    # Prometheus refuses the whole scrape. The places' number is added to the empty set's row of the spares' lines, and
    # said alone only when those are not said (a stale pass, or no `offers`).
    def places_needed(self, live: dict) -> int:
        from .metrics import matches
        t = self.spec.places
        held = self.ctl.live_holds()
        free = [n for n, it in self.ctl.table_rows(t["table"]).items() if matches(it, t["where"]) and n not in held]
        return max(0, len(free) - len(self.ctl.placeless_live(live)))

    def places_lines(self, needed: int) -> list[str]:
        p = self.spec.name
        return [f"# TYPE {p}_workers_needed gauge", f'{p}_workers_needed{{labels=""}} {needed}']

    def spares_lines(self, rep: dict, now: float, hbs: dict, places_needed: int = 0) -> list[str]:
        p, rk = self.spec.name, f"{self.spec.name}/controller/pass"
        ts = number(f"{rk}#ts", rep.get("ts"), float, None)
        if ts is None or now - ts > self.SPARES_FRESH:
            return []
        lines = []
        # …and `<p>_spares_withheld{labels}` 1 for a set short with no server a spare could carry its units on (the
        # twelfth round's «Вопросы»): no offer, and the reason in the pass report
        withheld = rep.get("spares_withheld") if isinstance(rep.get("spares_withheld"), dict) else {}
        rep = {**rep, "spares_withheld_n": {k: 1 for k in withheld}}
        for field, metric in (("workers_needed", "workers_needed"), ("units_short", "units_short"),
                              ("spare_offers", "spare_offers"), ("spares_withheld_n", "spares_withheld")):
            said = rep.get(field) if isinstance(rep.get(field), dict) else {}
            sets = {"": 0, **{str(k): v for k, v in said.items()}} if field == "workers_needed" else said
            extra = {"": places_needed} if field == "workers_needed" else {}      # the free places, on the empty set's row
            lines += [f"# TYPE {p}_{metric} gauge",
                      *[f'{p}_{metric}{{labels="{label(s)}"}} {number(f"{rk}#{field}.{s}", v, int, 0) + extra.get(s, 0)}'
                        for s, v in sorted(sets.items(), key=lambda x: str(x[0]))]]
        node: dict[str, set] = {}
        for w, hb in hbs.items():
            if isinstance(hb.extra.get("server"), str):
                node.setdefault(hb.extra["server"], set()).update(l for l in str(hb.extra.get("labels", "")).split(",") if l)
        lines.append(f"# TYPE {p}_server_labels gauge")
        for server in sorted(self.ctl.servers_known()):
            said, by = self.ctl.server_labels_of(server)          # `unknown`: what its row last said, or none
            said = node.get(server, ()) if by == "node" else (said or ())
            lines.append(f'{p}_server_labels{{server="{label(server)}",labels="{label(label_set(said))}",source="{by}"}} 1')
        return lines

    # -- writes ---------------------------------------------------------------------------------
    # `ctl.create(body)` → 201 with the row plus `worker: None` (placed by the controller's next pass, never
    # by the console); `Exists` — the id is a unit's already — → 409 `{detail, error: "exists"}`, the product's answer,
    # which a page reads as "there already" (`startLive`); `Refused` → 400 `{detail, error}`. Under `key`, the new id
    # goes into the claim first, and a claim taken over creates under the id it names (`IdempotencyKeys.reserve`).
    #
    # WHO MADE IT AND WHO CHANGED IT (the review's third pass, minor): the journal knew who deleted a unit and not
    # who created or edited it. `unit.created` and `unit.changed` — with the NAMES of the fields, never their values
    # (a password is one of them) — are written after the write, because a unit that exists is its own evidence
    # that it was made, and an edit that failed changed nothing. `unit.deleted` is the other way round (`delete`).
    def create(self, body: dict, key: str | None = None, user: str = "operator") -> tuple[int, dict]:
        try:
            r = self.ctl.create(body, uid=self.seen.reserved(key) if key else None,
                                reserve=(lambda uid: self.seen.reserve(key, uid)) if key else None)
            self.journal.say("unit.created", sub=self.spec.name, target=str(r.get("id")), user=user,
                             fields=",".join(sorted(str(k) for k in body)))
            # Masked, like every other way out. This reply is ALSO what `IdempotencyKeys` stores to answer a
            # retry, so an unmasked one puts a second copy of the secret in the config store under a key
            # nobody thinks to look at — which is exactly how this was got wrong the first time.
            return 201, {**mask_secrets([r])[0], "worker": None}      # placed by the controller's next pass, never by the console
        except Exists as e:
            return 409, {"detail": str(e), "error": "exists"}
        except Refused as e:
            return refused_status(e), {"detail": str(e), "error": str(e), **fault_of(e)}
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
    # A `fixed` field is set at the row's creation (`SpecController.update`, the review's fourth pass): the gate checks
    # the grant on the unit the row is about now, and a PUT that changed it would move the row past that check.
    def update(self, uid, body: dict, user: str = "operator") -> tuple[int, dict]:
        try:
            row = self.ctl.update(uid, body)
            self.journal.say("unit.changed", sub=self.spec.name, target=str(uid), user=user,
                             fields=",".join(sorted(str(k) for k in body)), revision=row.get("revision"))
            return 200, mask_secrets([row])[0]
        except Refused as e:
            return refused_status(e), {"detail": str(e), "error": str(e), **fault_of(e)}
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
            return refused_status(e), {"detail": str(e), "error": str(e), **fault_of(e)}
        except TooLarge as e:
            # The blob is bigger than the STORE will hold — which is the one case where changing the store
            # is the answer, because a blob is exactly the class of data an object store exists for. The cluster's
            # objects are files on each server (`OBJECTS=cluster://…`, `w2cplatform/cluster/objectstore.py`) with no ceiling; a
            # store that declares one (`max_bytes`: an object store built with one, or one over a capped row store —
            # `VariablesObjectStore` takes the ceiling of the store under it) is what refused this.
            return 413, {"detail": f"{e} — a blob is what an object store is for: this one declares a ceiling; the "
                                   f"cluster's file objects (OBJECTS=cluster://…) have none", "error": str(e)}
        self.journal.say("unit.changed", sub=self.spec.name, target=str(uid), user=user, fields=field,
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
        # `sub` and `target`, not `subsystem` and `unit`: those two are the LINE's own — who wrote it — and a field
        # of the same name would answer for it in every reader (`journal.py`).
        self.journal.say("unit.deleted", sub=self.spec.name, target=str(uid), user=user)
        try:
            self.ctl.delete(uid)
        except Exception as e:
            self.journal.say("unit.delete.failed", sub=self.spec.name, target=str(uid), user=user, error=str(e))
            raise
        return 200, {"deleted": uid}

    # An operator's observation. 503 if there is no resource on this server; 400 unless the body names the unit it is
    # about, `<sub>/<id>` — a bare id is whose? Appends `{kind: mark, user, note, of: <sub>/<id>}` at `wall()` to the
    # console's own bucket — `of`, the index's second column, so a query for that unit finds the mark (the boundary's
    # step 2: the mark named a number in a field of one subsystem's, and the index joined on that field) — and
    # returns 201 `{subsystem: "console", unit: <instance>, bucket: <relative path>}`. It is the console's event, into
    # `console/<instance>/e1/…` on this server's resource, never a worker's bucket.
    def mark(self, body: dict, user: str) -> tuple[int, dict]:
        if self.marks is None:
            return 503, {"detail": "no resource on this server to write marks into", "error": "no resource on this server to write marks into"}
        why = ref_fault(body.get("unit")) if "unit" in body else "a mark names the unit it is about, <sub>/<id>"
        if why:
            return 400, {"detail": why, "error": "a mark names a unit"}
        path = self.marks.append(self.wall(), "mark", user=user, note=str(body.get("note", "")), **{OF: str(body["unit"])})
        return 201, {"subsystem": "console", "unit": self.instance, "bucket": os.path.relpath(path, self.marks_root)}

    # -- the handler ----------------------------------------------------------------------------
    # Builds and returns the request handler class bound to this console.
    #
    # #### `class H(BaseHTTPRequestHandler)` (nested)
    # - `log_message` — silenced.
    # - `_send(status, body, raw=False)` — JSON (or raw text) with `Content-Type` and `Content-Length`.
    # - `_body()` — the JSON request body, `{}` if empty.
    # - `_uid()` — the id segment (`path_id`: the one after the family, the one the gate checked) through `spec.parse_id`.
    # - `do_GET` — routes, in order:
    #   - `GET /` or `/index.html` — the page (`page_of`), with its CSP, at the root alone (`serves_page`); `/platform/console.js|css` — the module (`send_module`).
    #   - `GET /spec` — `describe()`.
    #         - `GET /<rows>` — `{rows: ctl.read_model(lost_after), configured: ctl.units()}`: the
    #       heartbeats' view over the configured rows.
    #         - `GET /where/<id>` — `{worker, reason}` from the stored placement (404 with nulls if
    #       unplaced), plus `directory` (the assignments' answer) and `scans`.
    #         - `GET /where/<table>/<place>?unit=` — `where_place`: the place's holder and its door for that unit; 404
    #       `X-Unreachable: <place>@<server>` when nobody holds it.
    #   - `GET /resources` — every resource heartbeat with `state: live | silent` by `lost_after`.
    #   - `GET /servers` — `servers()`: per server, `resource` (`live | silent | unreachable | unknown`), `workers`,
    #     `placeable` and `why` (what of a subsystem's tables a server holds is the spec's `servers.show`, read with `/spec`);
    #     each worker's `status` — the fields of its heartbeat the spec's `servers.status` names, as written — and
    #     those declarations once, `status: [{field, title}]`, beside `policy`.
    #   - `GET /unplaceable` — `ctl.unplaceable()`.
    #         - `GET /events?from&to&unit&kind&subsystem&limit&keep&class` — 503 if no index; else
    #       `current_epochs` from every `<sub>/epoch/*` row (`epochs`, cached `EPOCH_CACHE` seconds) and
    #       `index.query`; with `unit` (`<sub>/<id>`: its own lines and those of every unit about it; a bare id is
    #       400), the query runs unfenced and the answer is fenced by the epochs of the units in it (`epochs_of`,
    #       `refence`), read by name. `keep` is "newest" (default) or "oldest", 400 if it is neither; the reply
    #       carries `truncated` when the window did not fit.
    #   - `GET /metrics` — `metrics_text()` as `text/plain`.
    #   - otherwise a declared table or request (`_declared`); then 404 `{detail, error}`.
    # - `_idem() -> key | None` — for POST: 400 if `Idempotency-Key` is missing or malformed; if `claim`
    #   returns a prior reply, send it and return `None`; else return the key.
    # - `do_POST`:
    #     - `POST /<rows>` (Idempotency-Key required) — `create(body)`; the reply is stored under the key
    #     and sent.
    #         - `POST /marks` (Idempotency-Key required; `X-User` header, default `operator`) — `mark(body,
    #       user)`; stored and sent.
    #   - any other path — a declared table or request (`_declared`), or 404.
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
    # The families: the rows, `UNIT_ROUTES` (the id IS a unit: `/where`) and `ID_ROUTES` (an id that is not a unit),
    # and the spec's tables (a row's name).
    ID_ROUTES: tuple = ()

    def route_id(self, method: str, path: str) -> tuple[str | None, str | None]:
        """`(family, id)` when the path is `/<family>/<id>` of a family that takes one, else `(None, None)`.
        `NoSuchRoute` for a path with more after the id."""
        segs = path.split("/")
        if self.place_path(method, path):
            return None, None                            # a place names no unit: the unit it is asked for is `?unit=`
        if len(segs) < 3 or segs[1] not in (self.spec.rows, *self.UNIT_ROUTES, *self.ID_ROUTES, *self.spec.table_specs):
            return None, None
        if len(segs) > 3 and not (method == "PUT" and segs[1] == self.spec.rows and len(segs) == 4 and segs[3]):
            raise NoSuchRoute(f"{path}: one id after /{segs[1]}/, and nothing after it")
        return segs[1], path_id(path) or None

    # `GET /where/<table>/<place>` — the one route with a table's row after `/where/`: the spec's table of places
    # (`placement.places.table`) and one name in it. Anything else after `/where/<x>/` stays no route.
    def place_path(self, method: str, path: str) -> bool:
        segs = path.split("/")
        return (method == "GET" and len(segs) == 4 and segs[1] == "where" and bool(self.spec.places)
                and segs[2] == self.spec.places["table"] and bool(segs[3]))

    # …and an id that is no id of this subsystem — `/where/None`, `/cameras/x` where ids are numbers — is the sender's, a
    # 400 in words (the coordinator's find in the twelfth round): `parse_id` raised `ValueError` out of `dispatch`, and
    # `GET /where/None` dropped the connection; `PUT`/`DELETE /cameras/x` answered 500 "the write failed".
    def _uid(self, path):
        raw = path_id(path)
        try:
            uid = self.spec.parse_id(raw)
        except ValueError:
            raise Refused(f"{raw[:80]!r} is not an id of {self.spec.name}: its ids are "
                          f"{'whole numbers' if self.spec.numeric else 'names'}") from None
        # …and a name is ONE segment of a key (the review's thirteenth pass, minor): `..` passed as a name, and the store
        # refused the key it made — `PUT` and `DELETE` on `/rec/recordings/..`, `/detjob/jobs/..`, `/auto/scenarios/..`
        # answered 500 "the write failed". Not an id: 400, as a word is where the ids are numbers.
        from .doors import safe_segment
        if not self.spec.numeric and not safe_segment(str(uid)):
            raise Refused(f"{raw[:80]!r} is not an id of {self.spec.name}: a name is one segment, not '.', '..' or a "
                          f"path")
        return uid

    # What a gated caller may LOOK at: `(unit, labels) -> bool`, or None when this console is open. A list is
    # not a route that names a unit, so the gate lets in anybody with any grant — and the list then shows them
    # only what their grants cover. `"*"` asks about no unit in particular: only a grant on the whole cluster
    # answers yes.
    def _visible(self, h):
        try:
            access = self.gate.access()
        except Denied:
            return lambda unit, labels, of=None: False
        if access is None:
            return None
        try:
            payload = self.gate.payload(h.headers, access)
        except Denied:
            return lambda unit, labels, of=None: False
        return lambda unit, labels, of=None: may_on(access, payload, "view", unit, labels, of)

    # Whether a gated caller holds a grant given on LABELS (`Access.by_labels`, when the access can say): what `/events`
    # asks before it names the units whose labels it could not read. An access that cannot say is taken as no.
    def _by_labels(self, h) -> bool:
        try:
            access = self.gate.access()
            if access is None:
                return False
            payload = self.gate.payload(h.headers, access)
        except Denied:
            return False
        ask = getattr(access, "by_labels", None)
        return bool(ask(payload, "view")) if ask is not None else False

    # What a route needs: `(capability, unit, labels, of)` — what `Gate.admit` takes.
    #
    #   view    every GET, and a write the spec says changes nothing (`rights.routes.view` — asking for a stream)
    #   edit    acting through the system without changing what it IS — a mark, a command to a device, a
    #           backfill, a keep
    #   admin   everything else that writes: units, volumes, policy, drain, a server decommissioned
    #
    # The unit is named when the path names one; a grant may be for one unit, for units with given labels, or
    # for the whole cluster, and a route that names no unit needs the last (to act) or any grant at all (to look).
    # A unit ABOUT another (its spec's `about`) is asked with what it is about: a grant on either is enough, and the
    # labels are the about-unit's (`target`).
    #
    # The lists are the platform's own routes; what a subsystem's families need beyond them its spec says, because
    # only it knows that a backfill acts and a volume configures (`rights.routes`), and that its rows are the whole
    # cluster's business — a write to one needs the cluster's grant, whatever the row names (`rights.cluster_rows`).
    EDIT_ROUTES: tuple = ("/marks", "/requests")
    UNIT_ROUTES: tuple = ("where",)

    # The unit an ACTION names in its body (`unit`, `<sub>/<id>`): a mark, a command and a keep are about one unit,
    # and an operator granted that unit must be able to make them. The body is read here and put back, so whoever
    # answers the request reads it again as if nobody had.
    #
    # A GET names its unit in the query the same way (`?unit=<sub>/<id>`): the events of one unit, a subsystem's route
    # about one. A route that names no unit anywhere is answered to any grant — a list, and the list is cut to what the
    # caller may see; a route that names one in the query is about that unit (the review's second pass, blocker 1: a
    # route that named its unit in the query was "any grant", and one unit's footage went to the guard of another). A
    # name that is no reference — a bare id — is 400 here, asked of nobody: whose `7` would the gate check?
    def _named(self, h, method: str, path: str, q: dict | None = None) -> str | None:
        if method == "GET":
            named = (q or {}).get("unit")
        else:
            if method not in ("POST", "PUT") or not path.startswith(self.EDIT_ROUTES):
                return None
            body = self._sent(h)
            named = body.get("unit") if isinstance(body, dict) else None
        if named in (None, ""):
            return None
        why = ref_fault(named)
        if why:
            raise Denied(400, why)
        return str(named)

    # The body as sent, read and put back — `{}` for none, None for one that is no JSON.
    @staticmethod
    def _sent(h):
        if isinstance(h.rfile, io.BytesIO):
            raw = h.rfile.getvalue()
        else:
            raw = h.rfile.read(int(h.headers.get("Content-Length", 0) or 0))
            h.rfile = io.BytesIO(raw)
        try:
            return parse_json(raw or b"{}")              # as the route reads it (`canonical.parse_json`)
        except PARSE_ERRORS:                             # nested past what JSON reads too: no reply at all (the tenth round)
            return None

    def needs(self, method: str, path: str, named: str | None = None) -> tuple[str, str | None, list, str | None]:
        head = path.strip("/").split("/")[0]
        # `rights.routes`: a family's writes that need less than admin. Of the unit rows, the CREATE alone — asking for a
        # stream is a viewer's; changing what a row is stays the administrator's
        caps = self.spec.route_caps if head != self.spec.rows or method == "POST" else {}
        ledger = method == "DELETE" and path.startswith(f"/requests/{LEDGER}")   # a person's ledger: the administrator's
        cap = "view" if method == "GET" \
            or head in caps.get("view", ()) else \
              "edit" if (path.startswith(self.EDIT_ROUTES) and not ledger) or head in caps.get("edit", ()) else "admin"
        family, pid = self.route_id(method, path)
        if pid and family in (self.spec.rows, *self.UNIT_ROUTES):
            if self.spec.cluster_rows and family == self.spec.rows and method != "GET":
                return cap, None, [], None
            return (cap, *self.target_in(self, pid))
        if named is None:
            return cap, None, [], None
        return (cap, *self.target(named))

    # WHAT A UNIT IS, AS A GRANT IS ASKED ABOUT IT: `(ref, labels, of)`, read through the catalogue (`units`) — its row,
    # what the row says it is about (`about`), and the labels a `labels:` grant reads: the about-unit's when there is one
    # (a recording's own labels say where it runs, not whose it is), else its own. A unit of a subsystem this console
    # does not serve is asked as it is named, with no labels: only a grant on it, or the cluster's, takes it in.
    def target(self, ref: str) -> tuple[str, list, str | None]:
        got = parse_ref(ref)
        con = self.units.get(got[0]) if got is not None else None
        if con is None:
            return ref, [], None
        return self.target_in(con, got[1])

    def target_in(self, con: "SpecConsole", pid) -> tuple[str, list, str | None]:
        return self.target_of_row(con, con.row_of(pid), con.spec.ref(pid))

    def target_of_row(self, con: "SpecConsole", row: dict | None, ref: str) -> tuple[str, list, str | None]:
        of = con.spec.of_row(row) or None
        return ref, (self.labels_of(of) if of else _labels(row)), of

    # The labels of the unit a reference names, through the catalogue; none when its row is not here.
    def labels_of(self, ref: str) -> list:
        got = parse_ref(ref)
        con = self.units.get(got[0]) if got is not None else None
        return _labels(con.row_of(got[1])) if con is not None else []

    # This console's row of `pid`, as stored — None when it is absent, deleted, no id of this subsystem, or does not
    # parse (a row nobody can read names nothing: the unit's own grant and the cluster's still answer for it).
    def row_of(self, pid) -> dict | None:
        try:
            return self.ctl.unit(self.spec.parse_id(pid))
        except (ValueError, OSError, *PARSE_ERRORS):   # a store that did not answer for it: no row, so no label grant
            return None

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
            h._send(503, {"detail": f"the store did not answer: {no_paths(e)}", "error": "store unavailable"}); return None
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
        if isinstance(e, Refused):                       # a body that is no object (`object_body`): the sender's, 400
            return refused_status(e), {"detail": str(e), "error": str(e), **fault_of(e)}
        if isinstance(e, OSError):
            log.warning("%s: a write was not taken by the store: %s", self.spec.name, e)
            return 503, {"detail": f"the store did not answer: {no_paths(e)}", "error": "store unavailable"}
        log.error("%s: a write failed: %s", self.spec.name, e)
        return 500, {"detail": no_paths(e), "error": "the write failed"}

    # THE DOOR IN: `/session`. The gate asks for a token; this is how a person's BROWSER comes to carry one. The shapes
    # are the product's (`w2cplatform/access.go`, `Gate.session`), which the platform's console module reads (the
    # boundary's step 3):
    #
    #   GET     `{open, login_url, user?, until?, via?}` — whether this console asks at all (`open`: it does not), who
    #           the caller is here, and the login door (`LOGIN_URL` is the domain's signer, its door `/api/login`; a console
    #           issues no tokens and keeps no passwords, М12 Lesson 4)
    #   POST    `{token}` — checked exactly as the gate would check it, and set as a cookie the page's script cannot
    #           read (`access.session_cookie`), for as long as the token lives: `{user, until}`
    #   DELETE  the cookie goes, and an emergency session with it: `{out: true}`
    #   POST /session/break-glass `{who, why, password}` — the emergency entry (`Gate.open_glass`): a session in this
    #           process's memory, carried by a cookie of its own: `{user, until}`
    #
    # The password never comes here. The page sends it to the domain's login door and brings back only the token: N
    # consoles that never see a password are N places it cannot be taken from. An open console has nothing to log in
    # to, nor to break into: 400.
    def session(self, h, method: str, path: str = "/session") -> None:
        try:
            access = self.gate.access()
        except Denied as e:
            return h._send(e.status, {"detail": e.why, "error": "denied"})
        signer = os.environ.get("LOGIN_URL") or ""
        login = signer.rstrip("/") + "/api/login" if signer else None
        if method == "DELETE" and path == "/session":
            self.gate.close_glass(h.headers)
            h._extra_headers = (("Set-Cookie", session_cookie("", 0)), ("Set-Cookie", session_cookie("", 0).replace(COOKIE, GLASS_COOKIE, 1)))
            return h._send(200, {"out": True})
        if (method, path) not in (("GET", "/session"), ("POST", "/session"), ("POST", "/session/break-glass")):
            return h._send(404, {"detail": "GET, POST or DELETE /session; POST /session/break-glass", "error": "no such path"})
        if access is None:
            if method == "GET":
                return h._send(200, {"open": True, "login_url": login})
            return h._send(400, {"detail": "this console is open: there is nothing to log in to, nor to break into",
                                 "error": "open"})
        secure = (h.headers.get("X-Forwarded-Proto", "") == "https")
        # The door in is anybody's, so its body is whatever anybody sends (the review's ninth pass, minor: a body that
        # is a list, a token that is not a string, brackets past the parser's depth were 500): an object holding a
        # string token, or the emergency entry's three strings — else 400, and nothing is asked of the gate.
        from .rows import PARSE_ERRORS
        unread = {}                                      # the shared table's word, when the body does not read
        try:
            body = h._body() if method == "POST" else {}
        except OSError:
            body = None
        except PARSE_ERRORS as e:
            body, unread = None, {"fault": getattr(e, "fault", "") or "not_json"}
        if path == "/session/break-glass":
            if not isinstance(body, dict) or not all(isinstance(body.get(k, ""), str) for k in ("who", "why", "password")):
                return h._send(400, {"detail": "the emergency entry takes {\"who\", \"why\", \"password\"}, strings",
                                     "error": "not a session request", **unread})
            peer = str(getattr(h, "client_address", ("?",))[0])
            try:
                sid, payload = self.gate.open_glass(body.get("who", ""), body.get("why", ""), body.get("password", ""),
                                                    addr=caller_addr(h.headers, peer), local=is_local(peer))
            except Denied as e:
                if e.retry_after is not None:                            # the emergency door's pace: when the next turn is
                    h._extra_headers = (("Retry-After", str(max(1, int(e.retry_after + 0.999)))),)
                return h._send(e.status, {"detail": e.why, "error": "denied",
                                          **({"retry_after": round(e.retry_after, 1)} if e.retry_after is not None else {})})
            h._extra_headers = (("Set-Cookie", session_cookie(sid, float(payload.get("exp", 0)) - self.wall(), secure).replace(COOKIE, GLASS_COOKIE, 1)),)
            return h._send(200, {"user": f"break-glass({payload.get('who')})", "until": payload.get("exp")})
        if not isinstance(body, dict) or not isinstance(body.get("token", ""), (str, type(None))):
            return h._send(400, {"detail": "the door in takes {\"token\": \"…\"}; the emergency entry is POST "
                                           "/session/break-glass", "error": "not a session request", **unread})
        token = (body.get("token") if method == "POST" else token_of(h.headers)) or ""
        try:
            payload = access.who(token) if token else (self.gate.payload(h.headers, access) if method == "GET" else None)
        except Denied as e:
            if method == "POST":
                return h._send(e.status, {"detail": e.why, "error": "denied"})
            payload = None                               # a cookie that has expired: not logged in, and not an error
        if payload is None:
            if method == "GET":
                return h._send(200, {"open": False, "login_url": login})
            return h._send(400, {"detail": "the door in takes {\"token\": \"…\"}", "error": "not a session request"})
        user = f"break-glass({payload.get('who')})" if payload.get("via") == "break-glass" else payload.get("sub")
        if method == "POST":
            h._extra_headers = (("Set-Cookie", session_cookie(token, float(payload.get("exp", 0)) - self.wall(), secure)),)
            return h._send(200, {"user": user, "until": payload.get("exp")})
        return h._send(200, {"open": False, "login_url": login, "user": user, "until": payload.get("exp"),
                             "via": str(payload.get("via") or "")})

    # THE BODY, READ ONCE, BOUNDED, AFTER THE CALLER IS KNOWN (the review's fifth pass, major). `Content-Length` is
    # checked before a byte is read: past `MAX_BODY` (a blob's bytes: `MAX_BLOB`) it is 413, and the connection is
    # closed rather than drained; a length that is not a number is 400. What is read is read here, under a deadline
    # of its own — `CONSOLE_TIMEOUT` and a second for every `BODY_RATE` bytes — and put back as memory, so `_named`,
    # `_idem` and every route read it as if nobody had. A body that does not arrive in time is 408. True: read, go
    # on; False: refused, and the reply sent. The reading itself is `read_body` below the class: every door's.
    def read_body(self, h, limit: int) -> bool:
        return read_body(h, limit)

    # WHOSE ROWS A WRITE TOUCHES (the review's fifth pass, major; the boundary's step 2). The gate checks the unit a path
    # names — and a write can reach units through the rows it writes. The platform reads two of those from the spec:
    #
    #   about         a row of this subsystem is about the unit its `about.field` names, and that field is `fixed`:
    #                 the row as it is and as it will be are about the same unit, asked with it (`needs`, `target`)
    #   unit_of       a row of one of its tables is its unit's (`rights.unit_of`): whoever writes it needs on that unit
    #                 what the route needs — on both, when a write moves it from one to another (`_table_targets`)
    #
    # And what a CHANGE of a row, or a request, reaches beyond the unit itself — the spec's `rights.reach` and
    # `rights.names` (`reach_of_change`, `reach_of_request`; the boundary's step 6: it was the subsystem's code set on
    # this console, `moved_units` and `body_units`). `"*"` is "any unit", which only a grant on the whole cluster covers.

    # `(table, id or None)` for a write to a row of one of this subsystem's tables that `rights.unit_of` says whose —
    # `(None, None)` for anything else.
    def _table_row(self, method: str, path: str) -> tuple[str | None, str | None]:
        if method not in ("POST", "PUT", "DELETE"):
            return None, None
        segs = path.split("/")
        if len(segs) < 2 or segs[1] not in self.spec.unit_of or len(segs) > 3:
            return None, None
        return segs[1], (segs[2] if len(segs) == 3 and segs[2] else None)

    # The units a write to such a row touches: the row as stored (the path names one) and the row as sent (`sent`, the
    # body, once it is read).
    def _table_targets(self, method: str, path: str, sent=None) -> set:
        table, rid = self._table_row(method, path)
        if table is None:
            return set()
        from .doors import safe_segment
        rows = []
        if rid and safe_segment(rid):
            try:
                rows.append(self.ctl.vars.get(self.spec.sub.config(table, rid))[0])
            except OSError:
                rows.append({self.spec.unit_of[table]: "*"})   # the store did not say whose: the cluster's grant
        if isinstance(sent, dict) and method != "DELETE":
            rows.append(sent)
        out = set()
        for row in rows:
            v = (row or {}).get(self.spec.unit_of[table])
            if v == "*":
                out.add("*")
                continue
            ref, _known = self.spec.table_unit(table, row)
            if ref:
                out.add(ref)
        return out

    # `(old row or None, True)` for a write to one of this console's rows — `(None, False)` for anything else.
    def _row_written(self, method: str, path: str):
        if method not in ("POST", "PUT", "DELETE"):
            return None, False
        rows_path = "/" + self.spec.rows
        if (path != rows_path and not path.startswith(rows_path + "/")) or len(path.split("/")) > 3:
            return None, False                           # not a row; or a blob's bytes: no field that names a unit
        pid = path_id(path)
        return (self.row_of(pid) if pid else None), True

    # In two steps, because the body is read between them (`dispatch`): `body=False` asks about what the path alone
    # decides — a table's row as stored — and `body=True` about the row as it WILL BE, and what the change reaches.
    # `asked` is what this request has been admitted on already, `{(capability, unit)}`: nothing is asked — or written
    # into the journal — twice.
    def admit_rows(self, h, method: str, path: str, asked: set | None = None, body: bool = True) -> None:
        if method not in ("POST", "PUT", "DELETE"):
            return                                       # a read writes no row: what a list shows is cut where it is made
        asked = set() if asked is None else asked
        sent = self._sent(h) if body and method != "DELETE" else None
        refs = self._table_targets(method, path, sent if body else None)
        # a unit row a viewer or an operator may create (`rights.routes` names the rows): asked on the unit it is ABOUT,
        # as the body names it — or the cluster's, when it names none. The gate before the body asked any grant at all.
        if body and method == "POST" and path.rstrip("/") == "/" + self.spec.rows and isinstance(sent, dict) \
                and any(self.spec.rows in v for v in self.spec.route_caps.values()):
            refs.add(self.spec.of_row(sent) or "*")
        # What the row reaches as it will be: an edit from the row as stored, a CREATE — `POST /<rows>`, or a `PUT` of a
        # row that is not there — from no row at all (`old = {}`: a move from "no group" into the group it names, the
        # same question as an edit's `will != was`). The sixth review closed it for an edit only, and a create put a
        # unit on a host where other people's units stand past them («Платформа», «Архитектор» 2026-10-06).
        if body and self.spec.reach and isinstance(sent, dict):
            old, written = self._row_written(method, path)
            if written and method in ("POST", "PUT"):
                try:
                    refs |= self.reach_of_change(old or {}, {**(old or {}), **sent})
                except Exception:                        # noqa: BLE001 — nobody can say what it reaches: the cluster's grant
                    refs.add("*")
        self._admit_each(h, self.needs(method, path)[0], refs, asked)

    def _admit_each(self, h, cap: str, refs: set, asked: set) -> None:
        for ref in sorted(refs):
            unit, labels, of = ("*", [], None) if ref == "*" else self.target(ref)
            if (cap, unit) in asked:
                continue
            self.gate.admit(h.headers, cap, unit, labels, of)
            asked.add((cap, unit))

    # -- what the spec declares, served (the boundary's step 6) --------------------------------------------------------
    # A subsystem's tables and its requests were its own routes on this console (`extra`, a hook gone at step 6); they are its spec's declarations now (`tables:`, `requests:`), and this console serves
    # them. True: the request was one of them, and its reply is sent.
    def _declared(self, h, method: str, path: str, q: dict) -> bool:
        segs = path.strip("/").split("/")
        if segs and segs[0] in self.spec.table_specs and len(segs) <= 2:
            self._table_route(h, method, segs[0], segs[1] if len(segs) == 2 and segs[1] else None)
            return True
        if path.rstrip("/") == "/requests" and method == "POST" and self.spec.requests:
            self._request_route(h)
            return True
        if method == "DELETE" and len(segs) == 2 and segs[0] == "requests" and segs[1].startswith(LEDGER) \
                and "per_person" in self.spec.requests:
            h._send(*self._delete_ledger(segs[1], h.headers.get("X-User", "operator")))
            return True
        return False

    # `/<table>[/<name>]` (`tables.py`): the list as this caller may see it, one row, a row written whole, a row deleted.
    def _table_route(self, h, method: str, table: str, name: str | None) -> None:
        ctl, user = self.ctl, h.headers.get("X-User", "operator")
        t = self.spec.table_specs[table]
        if method == "GET":
            rows = ctl.table_rows_shown(table)
            sees = self._visible(h)
            if sees is not None and table in self.spec.unit_of:   # gated: the rows whose unit this caller may see
                keep = []
                for r in rows:
                    ref, _ = self.spec.table_unit(table, r)
                    if r.get("garbled") or not ref or sees(*self.target(ref)):
                        keep.append(r)
                rows = keep
            # The table of places (`placement.places.table`): who holds each, now. A hold is of a place only
            # (`<sub>/holds/<row>`); the `affinity` table without `places` has no holder to say (ADR 0056).
            if table == self.spec.places.get("table"):
                held = ctl.live_holds()
                rows = [{**r, "held_by": held.get(r["name"])} for r in rows]
            if name is not None:
                one = next((r for r in rows if r["name"] == name), None)
                return h._send(200 if one else 404, one or {"detail": f"no {table} row {name}", "error": "no such row"})
            return h._send(200, {table: rows})
        if method == "POST" and name is None:
            try:
                body, said = object_body(h), {}
                rid, items = ctl.write_table_row(table, body, user, said)
            except Refused as e:
                return h._send(refused_status(e), {"detail": str(e), "error": "refused", **fault_of(e)})
            except TooLarge as e:
                return h._send(413, {"detail": str(e), "error": str(e)})
            except Forbidden as e:
                return h._send(403, {"detail": str(e), "error": str(e)})
            except (Conflict, OSError) as e:
                log.warning("%s: a row of %s was not written: %s", self.spec.name, table, e)
                return h._send(503, {"detail": "the store did not take it: try again", "error": "store unavailable"})
            from .tables import shown
            changed = {"changed": ",".join(said["changed"]), "was": said["was"]} if said else {}
            self.journal.say(t.journal.get("written", f"{table}.written"), sub=self.spec.name, target=rid, user=user,
                             table=table, fields=",".join(sorted(str(k) for k in body)), **changed)
            return h._send(201, {"row": {**shown(items, t.fields), "name": rid}})
        if method == "DELETE" and name is not None:
            try:
                gone = ctl.delete_table_row(table, name)
            except (Forbidden, OSError) as e:
                return h._send(503 if isinstance(e, OSError) else 403, {"detail": str(e), "error": "not deleted"})
            if not gone:
                return h._send(404, {"detail": f"no {table} row {name}", "error": "no such row"})
            self.journal.say(t.journal.get("deleted", f"{table}.deleted"), sub=self.spec.name, target=name, user=user,
                             table=table)
            return h._send(200, {"deleted": name})
        return h._send(405, {"detail": f"/{table} takes GET, POST and DELETE of one row", "error": "method"})

    # `POST /requests` (`requests:` in the spec): a request filed as a row of this subsystem's family, for whoever holds
    # its unit to perform and answer in its heartbeat. A request is not idempotent by nature — the same relay pulsed
    # twice IS two pulses — so its NAME makes a retry the same request: the spec's `key` (a template of its fields), the
    # body's `id`, or the `Idempotency-Key`, written create-only; and the key is kept where every key is (`_idem`), so a
    # retry after the row was answered and cleared is answered the same. What only the holder can judge — that a range
    # is longer than it fetches, that an argument is past what its unit has — is the holder's, said in its heartbeat.
    def _request_route(self, h) -> None:
        key = self._idem(h)
        if key is None:
            return
        try:
            resp = self._file_request(h, key)
        except Exception as e:                                       # noqa: BLE001
            return h._send(*self._failed(key, e))
        if resp[0] == 202:
            self._remember(key, resp)
        else:
            self.seen.release(key)                                  # a refusal is not a request: the key is not spent
        return h._send(*resp)

    def _file_request(self, h, key: str) -> tuple:
        import hashlib
        ctl, spec, req = self.ctl, self.spec, self.spec.requests
        user, now = h.headers.get("X-User", "operator"), self.wall()
        try:
            body = object_body(h)
        except Refused as e:
            return 400, {"detail": str(e), "error": "bad body", **fault_of(e)}
        if "schema" in req:
            from .schema import Invalid, check
            try:
                check(req["schema"], body, "the request")
            except Invalid as e:                         # past `maxLength`: the shared table's `too_long`
                return 400, {"detail": str(e), "error": "refused", **({"fault": "too_long"} if e.keyword == "maxLength" else {})}
            except RecursionError:
                return 400, {"detail": "the request is nested past what is read", "error": "refused"}
        ref = str(body.get("unit", ""))
        got = parse_ref(ref)
        if got is None or got[0] != spec.name:
            return 400, {"detail": f"a request names its unit as {spec.name}/<id>, not {ref[:80]!r}", "error": "bad unit"}
        try:
            row = ctl.unit(spec.parse_id(got[1]))
        except (ValueError, *PARSE_ERRORS):
            row = None
        if row is None:
            return 404, {"detail": f"no unit {ref}", "error": "no such unit"}
        uid = str(row["id"])
        if "key" in req:
            from .tables import KEY_TEMPLATE

            def filled(m) -> str:                          # a field's text in the name is its text in the row
                v = {**body, "unit": uid}[m.group(1)]
                if v is None:
                    raise KeyError(m.group(1))             # `null` is no value: the name is not filled in
                if not m.group(2):
                    return field_text(v)
                # `:int` — an integer in exactly its digits (through a float, 12345678901234567890 was …7168)
                return str(v) if isinstance(v, int) and not isinstance(v, bool) else str(int(float(v)))
            try:
                rid = KEY_TEMPLATE.sub(filled, req["key"])
            except (KeyError, *PARSE_ERRORS, OverflowError):
                return 400, {"detail": f"a request is named {req['key']}, and the body does not fill it in", "error": "bad id"}
        else:
            rid = str(body.get("id") or key)
        from .doors import unnamable
        if "/" in rid or rid in (".", "..") or len(rid) > 200 or unnamable(rid):
            return 400, {"detail": "a request's id is a name, not a path, and holds no quote, bar or control character",
                         "error": "bad id"}
        # A ROW'S VALUE IS ITS JSON TEXT, ONE FORM FOR THE COURSE AND THE PRODUCT (the architect, 2026-10-05, ADR 0012;
        # «Паритет»'s `testdata/requests_body.tsv`): a string as it is, `true`/`false`, a whole number as its digits, any
        # other the shortest decimal — `str()` wrote Python's `True` and `5.0`, and a holder in Go read another value
        # than the one in Python. `null` is no value: the field is absent, not the word `None`. The text is what the
        # schema's `maxLength` bounds — a number's too, as the holder reads it (`port: 1e40` is 41 characters).
        try:
            out = {k: t for k, v in body.items() if k not in ("unit", "id", "valid_until")
                   and (t := field_text(v)) is not None}
        except PARSE_ERRORS:                                # `NaN`, `Infinity`: Python reads them, JSON has none
            return 400, {"detail": "a request's values are JSON, and NaN and the infinities are not", "error": "bad body",
                         "fault": "not_json"}
        props = (req["schema"].get("properties") or {}) if isinstance(req.get("schema"), dict) else {}
        for k, t in out.items():
            most = props[k].get("maxLength") if isinstance(props.get(k), dict) else None
            if isinstance(most, int) and len(t) > most:
                return 400, {"detail": f"the request's {k} is at most {most} characters as written, not {len(t)}",
                             "error": "refused", "fault": "too_long"}
        out.update(unit=uid)
        if "valid_for" in req:
            # A deadline is a finite number of seconds (the review's seventh pass, M3): JSON's `NaN` and `Infinity`
            # reached the row as `nan`/`inf`, and a holder performed such a request hours late. How far one may be is
            # declared (`most_valid`, required with `valid_for`): no bound is assumed, neither 600 nor none (ADR 0012).
            try:
                until = finite(body.get("valid_until") or now + req["valid_for"])
            except (TypeError, ValueError):
                return 400, {"detail": f"`valid_until` is a time in seconds, not {body.get('valid_until')!r}", "error": "bad deadline"}
            if until - now > req["most_valid"]:
                return 400, {"detail": f"a request's `valid_until` is at most {req['most_valid']:.0f} s away", "error": "too far"}
            out["valid_until"] = number_text(until)
        stamp = set(req.get("stamp") or ())
        if "by" in stamp:
            out["by"] = user
        if "at" in stamp:
            out["at"] = number_text(now)
        if "group" in stamp and spec.group_by:               # what the rights were asked on: the holder performs it there only
            out["group"] = ctl.group_value(row)
        if "about" in stamp and spec.about_field and row.get(spec.about_field) not in (None, ""):
            out[spec.about_field] = str(row[spec.about_field])
        if "per_person" in req:
            # ONE PERSON'S OPEN REQUESTS, COUNTED BY CAS, NOT BY LOOKING (the review's sixth pass, minor; a run: forty
            # POSTs at once left fifteen rows). A person's open requests are ONE row — `<sub>/requests/asks-<sha256 of
            # the person, 16 hex>`, the list of their ids — changed by CAS; an id stays in it while its row stands, and
            # for `settle` seconds after it was added, row or no row (the list is written before the request is), and
            # never past the spec's `ttl` (`0`: no limit). The same request again is the same id, and is not counted twice.
            #
            # A LEDGER THAT DOES NOT READ STOPS THAT PERSON, AND SAYS SO (the architect's decision after step 7). It was read
            # as an empty list and written over by CAS: the person's limit silently reset, nothing counted. Now it is 429
            # «учёт не читается» to that person and nobody else, `<sub>_requests_ledger_garbled` on `/metrics`, the journal
            # once per row (not per request); an administrator deletes the row (`DELETE /<sub>/requests/asks-…`), and
            # the ledger starts anew.
            name = LEDGER + hashlib.sha256(user.encode()).hexdigest()[:16]
            ledger = spec.sub.request_key(name)
            settle, ttl = req.get("settle", 60.0), req["ttl"]   # the loader requires it with `per_person`; 0: no limit
            for _ in range(50):
                try:
                    it, idx = ctl.vars.get(ledger)
                    held = [(str(r), finite(at)) for r, at in parse_json((it or {}).get("asks", "[]"))]
                except PARSE_ERRORS as e:                 # `Garbled` too: a row the store holds and cannot read
                    return self._ledger_garbled(name, user, e)
                self._ledger_read(name)
                held = [(r, at) for r, at in held if (not ttl or now - at <= ttl)
                        and (now - at < settle or ctl.vars.get(spec.sub.request_key(r))[0])]
                if rid not in [r for r, _ in held]:
                    if len(held) >= req["per_person"]:
                        return 429, {"detail": f"{user} has {len(held)} requests nobody has answered yet, as many as one "
                                               f"person files at once — wait for some to be answered", "error": "too many"}
                    held.append((rid, now))
                try:
                    ctl.vars.put(ledger, {"asks": canonical_json(held), "by": user, "at": number_text(now)}, cas=idx)
                    break
                except Conflict:
                    continue                                  # another request of this person's got there first
            else:
                return 503, {"detail": "this person's list of requests would not settle — retry", "error": "busy"}
        try:
            ctl.vars.put(spec.sub.request_key(rid), out, cas=0)
        except Conflict:
            out = ctl.vars.get(spec.sub.request_key(rid))[0] or out   # the same request, filed already: its row is the answer
        if req.get("journal"):
            self.journal.say(str(req["journal"]), user=user, target=ref, request=rid,
                             **{k: v for k, v in out.items() if k in ("from", "to", "action")})
        return 202, {"queued": {"id": rid, **out},
                     "detail": "whoever holds the unit answers it on its next look at the requests, in its heartbeat"
                               + ("; after valid_until it expires unperformed" if "valid_for" in req else "")}

    # A person's ledger that does not read: 429 to that person, said in the journal once per row — again only after it
    # read once more, or was deleted.
    def _ledger_garbled(self, name: str, user: str, e: Exception) -> tuple:
        if name not in self.ledgers_garbled:
            self.ledgers_garbled.add(name)
            log.error("%s: the request ledger %s of %s does not read (%s): that person files nothing until an administrator "
                      "deletes it (DELETE /%s/requests/%s)", self.spec.name, name, user, e, self.spec.name, name)
            self.journal.say("request.ledger_garbled", ALARM, sub=self.spec.name, target=name, user=user, error=str(e)[:200])
        return 429, {"detail": f"учёт не читается: the list of {user}'s open requests ({self.spec.name}/requests/{name}) "
                               f"does not read, and nothing is filed for {user} until an administrator deletes it",
                     "error": "учёт не читается"}

    def _ledger_read(self, name: str) -> None:
        self.ledgers_garbled.discard(name)

    # `DELETE /requests/asks-<…>` — an administrator removes a person's ledger (one that does not read, as a rule): the
    # person's next request starts it anew. Only a ledger: a request row is its holder's to answer and the console's to
    # clear (`requests.py`).
    def _delete_ledger(self, name: str, user: str) -> tuple:
        key = self.spec.sub.request_key(name)
        try:
            there = bool(self.ctl.vars.get(key)[0])
        except PARSE_ERRORS:
            there = True                                  # garbled is there: the row is what is deleted
        if not there:
            self._ledger_read(name)
            return 404, {"detail": f"no ledger {name}", "error": "no such ledger"}
        self.ctl.vars.delete(key)
        self._ledger_read(name)
        self.journal.say("request.ledger_deleted", sub=self.spec.name, target=name, user=user)
        return 200, {"deleted": name}

    # -- what a change reaches (`rights.reach`, `rights.names`; the boundary's step 6) ---------------------------------
    # It was the subsystem's code, set on this console by its wiring (`moved_units`, `body_units`). A change of a field
    # `reach.group` names reaches every OTHER unit of the group the unit leaves and of the group it joins — one
    # connection is one group (`placement.group_by`), and moving a unit within a group shows that unit another's input;
    # a group no other unit is in yet is nobody's to open but the cluster's (`"*"`: a name nobody can say whose it is, a
    # host nobody holds); and moved to another group, every unit named by a row that names it (`rights.names` of any
    # subsystem served here — a scenario that commands it answers for every unit it reaches). A change of a field
    # `reach.cluster` names is the cluster's. A request whose action `reach.requests` names reaches every unit of its
    # unit's group: what it does is done to the one connection.
    #
    # A CREATE is `old = {}` (`admit_rows`): a move from no group into the one the row names — it reaches every unit of
    # that group (none is the new one: it is not there yet), and a group of nobody's is `"*"`, as a move into it is; a
    # `reach.cluster` field it is created with is the cluster's (a row created with a value there, ADR 0057). What the
    # spec's `default` puts in a field nobody sent is what the row will have, and is asked as if it was sent. No row
    # names a unit that does not exist yet: a create asks no `rights.names`.
    def reach_of_change(self, old: dict, new: dict) -> set:
        ctl, reach, out = self.ctl, self.spec.reach, set()
        created = not old
        if created:
            new = {**{f: self.spec.fields[f].default for f in (*reach.get("group", ()), *reach.get("cluster", ()))
                      if self.spec.fields[f].default is not None}, **new}
        norm = lambda v: ",".join(sorted(str(x) for x in v)) if isinstance(v, (list, tuple)) else str(v or "")
        if any(norm(old.get(f)) != norm(new.get(f)) for f in reach.get("cluster", ()) if f in new):
            out.add("*")
        if not any(f in new and norm(old.get(f)) != norm(new.get(f)) for f in reach.get("group", ())):
            return out
        g_old, g_new, me = ctl.group_value(old), ctl.group_value(new), None if created else str(old.get("id"))
        members = lambda g: {self.spec.ref(u["id"]) for u in ctl.units() if g and str(u["id"]) != me and ctl.group_value(u) == g}
        out |= members(g_old) | members(g_new)
        if g_new != g_old:
            if g_new and not members(g_new):
                out.add("*")
            if not created:
                out |= self.named_with(self.spec.ref(me))
        return out

    def reach_of_request(self, path: str, body) -> set:
        acts = self.spec.reach.get("requests", ())
        if path.rstrip("/") != "/requests" or not isinstance(body, dict) or str(body.get("action", "")) not in acts:
            return set()
        got = parse_ref(str(body.get("unit", "")))
        row = self.row_of(got[1]) if got is not None and got[0] == self.spec.name else None
        if row is None:
            return set()
        g = self.ctl.group_value(row)
        return {self.spec.ref(row["id"])} | ({self.spec.ref(u["id"]) for u in self.ctl.units() if self.ctl.group_value(u) == g}
                                              if g else set())

    # Every unit named — `rights.names` — by a row of a subsystem served here that names `ref`: what a row naming the
    # unit answers for when the unit moves. A row nobody can read names anybody: `"*"`.
    def named_with(self, ref: str) -> set:
        out = set()
        for con in self.units.values():
            if not con.spec.names:
                continue
            for row in con.ctl.units():
                named = names_in(con.spec, row)
                if ref in named or "*" in named:
                    out |= named
        return out

    def _sent_reach(self, h, path: str) -> set:
        try:
            return self.reach_of_request(path, self._sent(h))
        except Exception:                                # noqa: BLE001 — nobody can say what it reaches: the cluster's grant
            return {"*"}

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
        except PARSE_ERRORS:
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
        if path in ("/session", "/session/break-glass"):  # the door in: anybody's, so its body is a token or a password
            if not self.read_body(h, SESSION_BODY):
                return
            return self.session(h, method, path)
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
        # …and a write to a row of a table whose rows say whose they are (`rights.unit_of`): its unit is in the body too
        in_body = method in ("POST", "PUT") and (path.startswith(self.EDIT_ROUTES)
                                                 or path.strip("/").split("/")[0] in self.spec.unit_of)
        asked: set = set()
        if path not in OPEN_ROUTES:                     # the gate: open while this cluster has no key set, shut when it cannot check
            try:
                self.gate.caller(h.headers)              # who is calling: from the headers, before a byte of the body
                if in_body:
                    self.gate.admit(h.headers, "view")   # any grant here at all
                    asked.add(("view", None))
                else:
                    need = self.needs(method, path, self._named(h, method, path, q))
                    # A table's row that names whose it is (`rights.unit_of`) is that unit's: a request that names no unit
                    # of its own and writes such a row is about that row's unit, and about nothing wider.
                    if not (need[1] is None and self._table_targets(method, path)):
                        self.gate.admit(h.headers, *need)
                        asked.add(need[:2])
                self.admit_rows(h, method, path, asked, body=False)
            except Denied as e:
                h.close_connection = True                # refused before the body: what follows the headers is not read
                return h._send(e.status, {"detail": e.why, "error": "denied"})
        # A blob's bytes are the one body larger than `MAX_BODY`, and only where the spec has a blob to put them
        # (`blob_route`): `PUT /<rows>/<id>/<a blob field>`, by somebody admitted on that unit.
        if method == "PUT" and path.startswith(rows_path + "/") and len(path.split("/")) == 4:
            return self.blob_route(h, path)
        if not self.read_body(h, int(os.environ.get("CONSOLE_MAX_BODY", MAX_BODY))):
            return
        if in_body and path not in OPEN_ROUTES:
            # A body that does not read names no unit: it is the sender's 400 with the shared table's `fault` (the
            # architect, 2026-10-06), not a grant on the whole cluster asked of a caller who sent `NaN` or `1e400`.
            try:
                parse_json(h.rfile.getvalue() or b"{}")  # `read_body` put it back as memory: read, and still there
            except PARSE_ERRORS as e:
                return h._send(400, {"detail": f"the body is not JSON that can be read ({type(e).__name__})",
                                     "error": "bad body", "fault": getattr(e, "fault", "") or "not_json"})
        if path not in OPEN_ROUTES:
            try:
                if in_body:
                    need = self.needs(method, path, self._named(h, method, path, q))
                    if need[:2] not in asked and not (need[1] is None and self._table_targets(method, path, self._sent(h))):
                        self.gate.admit(h.headers, *need)
                        asked.add(need[:2])
                    if self.spec.reach.get("requests"):
                        self._admit_each(h, need[0], self._sent_reach(h, path), asked)
                self.admit_rows(h, method, path, asked)
            except Denied as e:
                return h._send(e.status, {"detail": e.why, "error": "denied"})
        book = book_path(path)
        if book is not None:                             # a book shown: any method, answered here (`book_route`)
            return h._send(*con.book_route(h, method, *book))
        if method == "GET":
            if path in ("/", "/index.html"):
                if not self.serves_page:
                    return h._send(404, {"detail": f"{spec.name} is mounted: the page is the console root's",
                                         "error": "not found"})
                page = page_of(spec)
                return send_file(h, page, "text/html; charset=utf-8", headers=(("Content-Security-Policy", page_csp(page)),))
            if path in MODULE_ROUTES:
                return send_module(h, path, q)
            if path == "/healthz":                      # alive: what the reserve and the monitors' lane answer besides
                return h._send(200, {"ok": True})        # (it was named there, and was a 404: the seventh pass's sweep)
            if path == "/spec":
                return h._send(200, con.describe())
            if path == rows_path:
                rows, configured = ctl.read_model(con.lost_after), mask_secrets(ctl.units())
                sees = self._visible(h)
                if sees is not None:                     # gated: the list is what THIS caller may look at, not the cluster's
                    ok = {str(r["id"]) for r in ctl.units() if sees(*self.target_of_row(self, r, spec.ref(r["id"])))}
                    rows = [r for r in rows if str(r.get("id")) in ok]
                    configured = [r for r in configured if str(r.get("id")) in ok]
                return h._send(200, {"rows": rows, "configured": configured})
            if self.place_path(method, path):
                return h._send(*con.where_place(h, path.split("/")[3], q))
            if path.startswith("/where/"):
                try:
                    uid = self._uid(path)
                except Refused as e:
                    return h._send(400, {"detail": str(e), "error": "not an id"})
                pl = ctl.placement(uid)
                return h._send(200 if pl else 404, {"worker": pl.worker if pl else None,
                                                    "server": ctl.server_of(pl.worker) if pl else None,
                                                    "reason": pl.reason if pl else ctl.unplaced_reason(uid),   # nowhere, and why (DQ)
                                                    "directory": con.where(uid), "scans": con.scans,
                                                    **con.door_of(h, uid)})
            if path == "/resources":
                now = con.wall()
                return h._send(200, {s: {**hb, "state": "live" if ctl.resource_state(s, con.lost_after) == "live" else "silent"}
                                     for s, hb in resources_seen(ctl.objects).items()})
            if path == "/servers":
                return h._send(200, con.servers())
            if path == "/domain":
                return h._send(*domain_view(ctl.objects, con.wall(), con.lost_after))
            if path == "/domain/keys":                       # every `domain/` key in this cluster's stores, masked
                from .domain.keysview import keys
                return h._send(200, keys(ctl.vars, ctl.objects, con.wall()))
            if path.startswith("/domain/shared/"):
                return h._send(*con.shared_route(path[len("/domain/shared/"):], q))
            if path == "/policy":
                return h._send(200, {**ctl.policy(), "choices": ctl.POLICY_CHOICES})
            if path == "/unplaceable":
                return h._send(200, ctl.unplaceable())
            if path == "/events":
                if con.index is None:
                    return h._send(503, {"error": "no event index behind this console"})
                # `unit` is `<sub>/<id>` — its own lines and those of every unit about it (the index's `of`); a bare id
                # is 400 (`check_query`). Every subsystem's epochs, from the cache — the timeline shows them all. One
                # unit's timeline reads only the epochs of the units in ITS answer, after the query, and fences again.
                unit = q.get("unit") or None
                narrow = unit is not None
                cur = {} if narrow else con.epochs()
                try:                                          # the operator's timeline: `limit` is theirs to set, and
                                                              # `keep` says which end of a busy hour they get
                    t0, t1 = float(q.get("from", 0)), float(q.get("to", 1e12))
                    rep = con.index.query(t0, t1, q.get("kind"), q.get("subsystem"), unit, cur,
                                          limit=min(int(q.get("limit", 1000)), MAX_LIMIT),
                                          epoch_policy=con.epoch_policy, keep=q.get("keep", "newest"),
                                          cls=q.get("class"), by=q.get("by", "t"))
                    if narrow:
                        refence(rep["events"], con.epochs_of({(e["subsystem"], unit_id(e)) for e in rep["events"]}), con.epoch_policy)
                    else:
                        # …AND A SUBSYSTEM THE SCAN DID NOT SEE IS ASKED BY NAME (the twelfth round's «Вопросы» 6, found
                        # by runs): the scan lists the empty prefix, and a store that answers only what the console may
                        # read (М11's rights) leaves out every subsystem outside them — `live/`, `det/` — and their
                        # events stood "current" whatever their epoch. The units of such a subsystem in THIS answer are
                        # read by name; a subsystem whose rows the console may not read at all is said (`epochs_unread`),
                        # its events as their resource marked them. The journal and the console's marks are written
                        # by one writer under epoch 1 and have no epoch rows: not asked.
                        seen_subs, refused = {s for s, _ in cur} | {AUDIT, CONSOLE_MARKS}, set()
                        other = [e for e in rep["events"] if e.get("subsystem") not in seen_subs]
                        if other:
                            refence(other, con.epochs_of({(e["subsystem"], unit_id(e)) for e in other}, refused),
                                    con.epoch_policy)
                        if refused:
                            rep = {**rep, "epochs_unread": sorted(refused)}
                    sees = self._visible(h)
                    if sees is not None:                 # …and so are the events: a unit's, to whoever may view that unit;
                        known: dict = {}                 # what names no unit — the journal — to whoever may view the whole cluster
                        unread: dict[str, str] = {}      # unit -> why its labels could not be read
                        withheld: dict[str, int] = {}    # …and how many of its events this caller was not shown for it

                        # ONE UNIT'S ROW IS ONE UNIT'S EVENTS (the scaling pass after the eighth review). The labels a
                        # grant may name were read with `ctl.unit` bare: one row that does not parse was a `ValueError`
                        # and a 400 for the whole timeline of everybody the gate checks (a `KeyError`, no reply at all).
                        # The row is read through `rows.Table` now (`UNIT_LABELS`: counted once, logged once, on
                        # `/metrics`); its unit is judged with no labels — the unit's own grant and the whole cluster's
                        # still see its events, a grant by label cannot, since what the row says is not known — and what
                        # was left out for that reason is said in the answer (`withheld`), by unit. A unit of a subsystem
                        # this console does not serve names no row here: judged with no labels, nothing withheld. A store
                        # that does not answer for the row is that unit's too, said the same way.
                        #
                        # Whose a line is: its own unit's, and the unit it is about (`of`) — a grant on either sees it,
                        # with the about-unit's labels when there is one (the boundary's step 2; the product's `MayOn`).
                        def labels_of(ref: str) -> list:
                            got = parse_ref(ref)
                            c = self.units.get(got[0]) if got is not None else None
                            if c is None or not c.spec.rows:
                                return []
                            try:
                                uid = c.spec.parse_id(got[1])
                            except ValueError:
                                return []
                            try:
                                row = UNIT_LABELS.read(c.ctl.row_key(uid), lambda: c.ctl.unit(uid), GARBLED_ROW)
                            except OSError as err:
                                unread[ref] = f"the store did not answer for its row ({err})"
                                return []
                            if row is GARBLED_ROW:
                                unread[ref] = "its row does not parse"
                                return []
                            return _labels(row)

                        def may_see(e):
                            ref, of = str(e.get("unit", "")), (e.get(OF) or None)
                            whose = of or ref               # the unit whose labels a grant is matched against
                            if (ref, of) not in known:
                                known[(ref, of)] = bool(sees(ref, labels_of(whose), of))
                            if not known[(ref, of)] and whose in unread:
                                withheld[whose] = withheld.get(whose, 0) + 1
                            return known[(ref, of)]
                        rep = {**rep, "events": [e for e in rep["events"] if may_see(e)]}
                        # …said only to a caller who holds a grant BY LABEL (the review's tenth pass, minor): what is
                        # withheld is what such a grant might have covered. A grant on one unit never covered another
                        # unit, and naming it — its id, how many events it had — told a guard of camera 2 about camera 3.
                        if withheld and not self._by_labels(h):
                            withheld = {}
                        if withheld:
                            rep["withheld"] = [{"unit": u, "events": n, "why": f"{unread[u]}: what labels it carries is "
                                                f"not known, and a grant by label cannot be checked against it"}
                                               for u, n in sorted(withheld.items())]
                    if not narrow and con.epochs_stale:
                        rep = {**rep, "epochs": "cached"}         # fenced by the epochs read before the store went quiet
                    return h._send(200, con.timeline(rep, t0, t1))
                except ValueError as e:
                    return h._send(400, {"error": str(e)})
            if path == "/metrics":
                return h._send(200, con.metrics_text(), raw=True)
            if self._declared(h, "GET", path, q):
                return
            return h._send(404, {"detail": "no such route", "error": "no such path"})
        if method == "POST":
            if path not in (rows_path, "/marks"):
                if self._declared(h, "POST", path, q):
                    return
                return h._send(404, {"detail": "no such route", "error": "no such path"})
            key = self._idem(h)
            if key is None:
                return
            try:
                if path == "/marks":
                    resp = con.mark(object_body(h), h.headers.get("X-User", "operator"))
                else:
                    resp = con.create(object_body(h), key, h.headers.get("X-User", "operator"))
            except Exception as e:                                       # noqa: BLE001
                return h._send(*self._failed(key, e))
            self._remember(key, resp); return h._send(*resp)
        if method == "PUT":
            if path == "/policy":                                        # the administrator's knobs: one row, no idempotency needed (a PUT is)
                try:
                    body = object_body(h)
                    out = ctl.set_policy(body)
                except (Refused, Forbidden) as e:
                    return h._send(400 if isinstance(e, Refused) else 403, {"detail": str(e), "error": str(e), **fault_of(e)})
                # A knob that moves every unit of the subsystem is a line with a name and the new values in it (the
                # review's third pass, minor): the policy's values are choices, not secrets.
                con.journal.say("policy.changed", sub=spec.name, user=h.headers.get("X-User", "operator"),
                                policy=json.dumps(body, sort_keys=True))
                return h._send(200, out)
            if not path.startswith(rows_path + "/"):
                if self._declared(h, "PUT", path, q):
                    return
                return h._send(404, {"detail": "no such route", "error": "no such path"})
            key = self._idem(h, required=False)                         # optional here: a PUT is its own retry
            if key is None and h.headers.get("Idempotency-Key"):
                return                                                   # a prior reply, a refused key or 503: already sent
            try:
                resp = con.update(self._uid(path), object_body(h), h.headers.get("X-User", "operator"))
            except Exception as e:                                       # noqa: BLE001
                return h._send(*self._failed(key, e))
            self._remember(key, resp)
            return h._send(*resp)
        if method == "DELETE":
            if not path.startswith(rows_path + "/"):
                if self._declared(h, "DELETE", path, q):
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


# The units a row names inside its json fields, as its spec's `rights.names` says (`{field, unit, sub | of}`): `<sub>/<id>`
# each — the subsystem from the entry's own key (`sub`) or said once (`of`). An entry of a field that names nothing by any
# of the declarations — a trigger on any unit — names anybody: `"*"`; and so does a field nobody can read.
def names_in(spec, row: dict) -> set:
    out: set = set()
    by_field: dict = {}
    for e in spec.names:
        by_field.setdefault(e["field"], []).append(e)
    for fld, entries in by_field.items():
        v = row.get(fld)
        try:
            v = json.loads(v) if isinstance(v, (str, bytes)) else v
        except PARSE_ERRORS:
            return {"*"}
        if v is None:
            continue
        if not isinstance(v, list):
            return {"*"}
        for x in v:
            if not isinstance(x, dict):
                continue
            found = set()
            for e in entries:
                u = x.get(e["unit"])
                if u not in (None, ""):
                    found.add(f"{x.get(e['sub']) if 'sub' in e else e['of']}/{u}")
            out |= found or {"*"}
    return out


class Mount:
    """One console process, several subsystems. The root console answers at `/`
    (the page, `/<rows>`, its tables); every other subsystem is a path: `/<sub>/spec`,
    `/<sub>/<rows>`, `/<sub>/where/<id>` — the same SpecConsole class, its routes
    under its name, its own token-scoped controller. A person opens one page;
    the machines (a host's spares script, М12's read model) find every subsystem
    on one port; a new subsystem is a YAML, a worker, and a path."""

    def __init__(self, root: SpecConsole, mounts: dict[str, SpecConsole] | None = None):
        self.root, self.mounts = root, dict(mounts or {})
        # One dict, SHARED by reference with every console here: `/events` merges across subsystems, so the
        # console answering the request has to know what an older epoch means in a subsystem it does not
        # own. A subsystem nobody mounted keeps the default, which is the old behaviour.
        self.epoch_policy: dict[str, str] = {}
        # …and one catalogue, the same way: a reference `<sub>/<id>` names a unit of whichever subsystem this process
        # serves, and the gate of any of its consoles reads that unit's row, what it is about and its labels.
        self.units: dict[str, SpecConsole] = {}
        for c in (self.root, *self.mounts.values()):
            self._adopt(c)

    def _adopt(self, console: SpecConsole) -> None:
        self.epoch_policy[console.spec.name] = console.spec.older_epochs
        console.epoch_policy = self.epoch_policy
        self.units[console.spec.name] = console
        console.units = self.units
        console.says_platform = console is self.root         # the platform's lines once per process: the root's page
        console.serves_page = console is self.root           # one page per process, the root's: `/<sub>/` is none

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
        running = builds(ctl.objects, now, eyes=ctl.eyes)  # live by what this console saw change (the thirteenth pass)
        live = {n: b for n, b in running.items() if b["live"]}
        # One process or one row that does not read is not the route's end (the review's tenth round): `platform/schema`
        # garbled is `version: null`, said; a live process whose schema is not known (`builds`) keeps `can_raise_to`
        # where the store is — raising past a process nobody can read is the lock-out the guard is for.
        try:
            version = schema_version(ctl.vars)
        except PARSE_ERRORS as e:
            version = None
            log.warning("%s does not parse (%s): /schema says so", SCHEMA_KEY, e)
        known = [b["schema"] for b in live.values() if b["schema"] is not None]
        can = min(known, default=SCHEMA) if len(known) == len(live) else (version or SCHEMA)
        return 200, {"version": version, "understood": SCHEMA,
                     "builds": sorted({b["build"] for b in live.values()}),
                     "can_raise_to": can,
                     **({"schema_unknown": sorted(n for n, b in live.items() if b["schema"] is None)} if len(known) < len(live) else {}),
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

    # THE OPERATOR'S DOOR TO A SERVER'S END: `POST /servers/<server>/decommission {"why": "…"}`, `DELETE` to withdraw it or
    # to bring the machine back. On the Mount, as `/drain`: a machine carries every subsystem, and whether it still answers
    # is asked of each (the product's door).
    #
    # The operator operates SERVERS, not workers (the owner's decision, 3 Oct, on the review's eleventh pass). There was
    # a door to retire a worker, and it asked the operator whether a silent process is dead or hung — which they cannot
    # know, and which made two holders of the same cameras. What they do know is a machine: they took it out and switched
    # it off. So the door is about the machine, and the platform checks what it can: the server answers by any of three
    # signs (`Controller.decommission_refusal` — its resource heard, a worker of it heard, a slot of it renewed) — 409, the
    # sign in words, nothing written. A server whose resource was never heard passes, with a warning. Written otherwise
    # (`platform/decommission/<server>`, the console's alone): each controller carries it out on its next pass
    # (`apply_decommissions`) — every slot of the server released, its units moved, a mark of what was done — and nothing
    # is placed on that server, nor a slot given to a process on it, until `DELETE`. A drain says the machine comes back;
    # this, that it does not. `admin` on the whole cluster; a server nobody here has heard of: 404; a body that is not a
    # JSON object: 400. A journal line each way (`server.decommission_requested`, `server.decommission_withdrawn`).
    def decommission_route(self, h, method: str, path: str, user: str = "operator") -> tuple:
        consoles = [self.root, *self.mounts.values()]
        ctl = self.root.ctl
        server = path[len("/servers/"):-len("/decommission")]
        try:
            server_name(server)
            if method == "DELETE":
                was = ctl.withdraw_decommission(server)
                if was is not None:
                    self.root.journal.say("server.decommission_withdrawn", server=server, user=user)
                return 200, {"server": server, "decommission": None, "withdrawn": was is not None,
                             "note": "its workers are placed on, and given slots, again from the controllers' next pass"
                                     if was is not None else f"{server} was not decommissioned"}
            body = object_body(h)
            if server not in self.servers_known():
                return 404, {"detail": f"no server called {server} is known here", "error": "no such server"}
            refusal = warning = None
            for c in consoles:
                r, w = c.ctl.decommission_refusal(server)
                refusal, warning = refusal or c.ctl.not_watched_yet(r), warning or w
            if refusal:
                log.warning("server %s was not decommissioned (asked by %s): %s", server, user, refusal)
                # …and in the journal, beside the decommissions that were made (the review's twelfth pass, minor)
                self.root.journal.say("server.decommission_refused", server=server, user=user, why=refusal)
                return 409, {"detail": refusal, "error": "server answers"}
            row = ctl.decommission(server, user, str(body.get("why") or ""))
        except Refused as e:
            return 400, {"detail": str(e), "error": "refused", **fault_of(e)}
        except DecommissionRefused as e:                 # it began to answer between the look and the write
            return 409, {"detail": str(e), "error": "server answers"}
        except Forbidden as e:                           # the console's token, not the caller: the store said no
            return 403, {"detail": str(e), "error": str(e)}
        except OSError as e:
            log.warning("server %r was not decommissioned: %s", server[:80], e)
            return 503, {"detail": "the store did not take it: try again; the console's log says why",
                         "error": "store unavailable"}
        self.root.journal.say("server.decommission_requested", server=server, user=user, why=row["why"])
        parts = {}
        for c in consoles:
            here = c.ctl.workers_on(server)
            held = c.ctl.holds_by()
            parts[c.spec.name] = {"workers": here,
                                  "units": sorted({str(u) for w in here for u in c.ctl.assignment(w).units}),
                                  "holds": sorted({p for w in here for p in held.get(w, [])})}
        holds = sorted({p for part in parts.values() for p in part["holds"]})
        return 202, {"server": server, "state": "requested", "subsystems": parts,
                     **({"warning": warning} if warning else {}),
                     "note": "each controller releases its slots on this server on its next pass and moves their units "
                             "to the servers that are here" +
                             (f"; what they held stays held — {', '.join(holds)}: withdraw a volume that went with its "
                              f"server" if holds else "")}

    # The servers anybody here has announced: a worker of any subsystem, a resource, a row of labels (each controller's
    # `servers_known`), and a decommission asked. What a write about a server is checked against.
    def servers_known(self) -> set[str]:
        return {s for c in (self.root, *self.mounts.values()) for s in c.ctl.servers_known()} \
            | set(self.root.ctl.decommission_requests())

    # WHAT A SERVER REACHES, FROM THE CONSOLE (feedback DQ; ADR-0026 and its addition): `/servers/<server>/labels`.
    # On the Mount, as `/drain` and a decommission, not on a subsystem: the row is ONE a server
    # (`platform/servers/<server>`), and what a server reaches decides where every subsystem's units may go. It was each
    # subsystem's route and row (`/<sub>/servers/<s>/labels`, `<sub>/servers/<s>`): gone, no alias (ADR-0003).
    #
    #   GET     ?labels=a,b — what it reaches now and from where (`server_labels_of`: console | node | unknown), and
    #           which units would move if it reached `a,b` (`would_move`; no `labels`: back to its node's) — the page
    #           asks before it writes, and warns
    #   PUT     {"labels": ["vlan:cctv-a", …]} — the administrator's labels; [] reaches nothing. A server nobody here has
    #           announced (`servers_known`, of every subsystem), a name that is not a host's, a body that is not JSON, a
    #           label that is not a string: 400, in words (the review's tenth pass)
    #   DELETE  back to the node's (`LABELS` in the server's environment)
    #
    # `admin` on the whole cluster to write, any grant to look (`admit`): a path that names no unit. `would_move` and
    # `will_move` are one list of `<sub>/<id>` across every spec here, cut to what the caller may `view` (the product's
    # `Mount.wouldMove`). Each write is a journal line with the name and the labels (`server.labels.set`,
    # `server.labels.cleared`); the controllers move what they decide on their next pass (`ensure_reach`).
    def labels_route(self, h, method: str, path: str, user: str = "operator") -> tuple:
        ctl = self.root.ctl
        server = path[len("/servers/"):-len("/labels")]
        try:
            server_name(server)
            if method == "GET":
                # `?labels=` (blank) reaches nothing; no `labels` at all is back to its node's — `q` drops a blank value
                want = parse_qs(urlsplit(h.path).query, keep_blank_values=True).get("labels", [None])[0]
                labels = None if want is None else [l for l in want.split(",") if l]
                if labels is not None and any(not LABEL_WORD.fullmatch(l) for l in labels):
                    raise Refused(f"a label is letters, digits and _ . : - (up to 64): {want!r}")
                said, by = ctl.server_labels_of(server)
                return 200, {"server": server, "labels": sorted(said) if said is not None else None,
                             "labels_source": by, "would_move": self.would_move(h, server, labels)}
            if method == "PUT":
                # Through `object_body` (the eleventh review, a minor): `ValueError` alone let a body nested past what
                # JSON reads (`RecursionError`) through, and the connection dropped with no answer.
                body = object_body(h)
                # …and `labels` alone (ADR 0012, strict; the product's `len(body) != 1`): a key beside it — `label`
                # misspelt, a `server` the path already names — was taken silently and meant nothing
                stray = sorted(k for k in body if k != "labels")
                if stray:
                    raise Refused(f'the labels are {{"labels": ["vlan:cctv-a", …]}}, each a string; [] for none — '
                                  f'and nothing else: not {stray[0]!r}')
                labels = ctl.set_server_labels(server, body.get("labels"), self.servers_known())
                self.root.journal.say("server.labels.set", server=server, labels=",".join(labels), user=user)
                return 200, {"server": server, "labels": labels, "labels_source": "console",
                             "will_move": self.would_move(h, server, labels)}
            if method != "DELETE":
                return 405, {"detail": "GET, PUT or DELETE", "error": "method not allowed"}
            if ctl.clear_server_labels(server):
                self.root.journal.say("server.labels.cleared", server=server, user=user)
            return 200, {"server": server, "labels_source": "node", "will_move": self.would_move(h, server, None)}
        except Refused as e:
            return 400, {"detail": str(e), "error": "refused", **fault_of(e)}
        except Forbidden as e:                           # the console's token, not the caller: the store said no
            return 403, {"detail": str(e), "error": str(e)}
        except OSError as e:
            # Not the store's own words to the caller (the review's tenth pass, minor): a name of 300 characters answered
            # with the local path of the store's file. They go to this console's log.
            log.warning("the labels of server %r were not written: %s", server[:80], e)
            return 503, {"detail": "the store did not take it: try again; the console's log says why",
                         "error": "store unavailable"}

    # What would move if `server` reached `labels` (None: its node's), in every subsystem here — each unit as
    # `<sub>/<id>`, and only those the caller may look at (`_visible`, `target_in`: a guard granted `vlan:a` is not told
    # the ids of the units on `vlan:b`).
    def would_move(self, h, server: str, labels) -> list[str]:
        sees = self.root._visible(h)
        out = []
        for c in (self.root, *self.mounts.values()):
            for uid in c.ctl.would_move(server, labels):
                target = self.root.target_in(c, uid)
                if sees is None or sees(*target):
                    out.append(target[0])
        return out

    # THE MOUNT'S OWN ROUTES ASK THE GATE TOO (the review's third pass, blocker 2). `/drain`, `/schema` and `/mounts`
    # were answered here, before `dispatch` and its gate: `POST /drain?server=srv-1` with no token took every
    # recording off a server, and the irreversible `PUT /schema` was as open. There are no exceptions for rights:
    # the root console's gate, `admin` to change (a drain moves every unit of a server; a schema locks out every
    # older build) and `view` to read — `/mounts` too. It says what this process fronts and each subsystem's
    # `/spec`, which is gated; it is the same knowledge, and the page reads it after its login like `/spec`. An
    # upgrade script polls `GET /drain` with a token, as anything else that talks to a gated console does.
    # Returns the name to act under, or None when it has already answered.
    MOUNT_ROUTES = ("/mounts", "/drain", "/schema")

    # THE DOMAIN'S ROUTES, HANDED ON AS THEY ARE (the contract of the console module, §10a: one set of paths,
    # literally). `/domain/X` the console does not answer itself — its view, its keys, a spec's shared fields — goes to
    # the domain holder's door at `/domain/X`, the path unrewritten: the address is the view's `url`, which only the
    # cluster the domain runs in holds (`domain_view`); elsewhere 404, said so. The person's token, the edit's
    # `Idempotency-Key` and `X-Operator: console` go with it, and the answer comes back as it came: the domain decides.
    # THE DOMAIN'S DOORS OF THIS CLUSTER, TO PROCESSES (contract §10a; «Архитектор» 2026-10-06; `domain.term`). Asked no
    # person's token — processes call them, each with its own proof:
    #   GET  /api/held      `{cluster, holder, term, keys, backup: {term, rev}}`: the holder's record and the key set this
    #                       cluster holds, as signed, and which backup copy is kept here, by term and rev — public, proving
    #                       itself: what a member's agent follows the holder by (`domain.agent.HolderFollower`), what a
    #                       move reads the largest term and the keys by, and what the page shows on a server's overview
    #                       (contract §2). Never the backup's content
    #   GET  /api/backup    the backup copy kept here, to a member that signs its ask (`domain.term.backup_answer`)
    #   POST /api/prepare, /api/take   a planned handover, handed to THIS box's signer (`SIGNER_URL`) as it came — the
    #                       signer checks the outgoing holder's signature and grant itself; no signer here: 404, said
    def held(self) -> dict:
        from .domain.term import held
        return held(self.root.ctl.cluster, self.root.ctl.vars)

    def backup(self, h) -> tuple[int, dict]:
        from .domain.term import backup_answer
        return backup_answer(self.root.ctl.cluster, self.root.ctl.vars, self.root.ctl.objects,
                             h.headers.get("X-W2C-Member"), h.headers.get("X-W2C-Time", "nan"),
                             h.headers.get("X-W2C-Signature"), self.root.wall())

    def to_signer(self, h, path: str) -> None:
        import urllib.error
        import urllib.request
        signer = os.environ.get("SIGNER_URL", "")
        if not signer:
            return h._send(404, {"error": "no signer here", "detail": f"{self.root.ctl.cluster} runs no signer of the "
                                                                      f"domain (SIGNER_URL): the domain cannot be handed here"})
        if not read_body(h, 1 << 16):
            return
        body = h.rfile.read(int(h.headers.get("Content-Length") or 0))
        headers = {"Content-Type": "application/json",
                   **{k: h.headers[k] for k in ("X-W2C-Time", "X-W2C-Signature") if h.headers.get(k)}}
        req = urllib.request.Request(signer.rstrip("/") + path, data=body or b"{}", headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=90.0 if path == "/api/take" else 10.0) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        except (OSError, ValueError) as e:
            return h._send(502, {"error": "the signer did not answer", "detail": str(e)})
        try:
            answer = json.loads(raw or b"{}")
        except PARSE_ERRORS:
            answer = {"detail": raw[:512].decode("utf-8", "replace")}
        h._send(status, answer)

    @staticmethod
    def domain_local(method: str, path: str) -> bool:
        return (method == "GET" and (path in ("/domain", "/domain/keys") or path.startswith("/domain/shared/"))) \
            or book_path(path) is not None                # a book of this cluster's own copy (`book_route`), any method

    def domain_forward(self, h, method: str, path: str, query: str) -> None:
        import urllib.error
        import urllib.request

        from .access import token_of
        st, view = domain_view(self.root.ctl.objects, self.root.wall(), self.root.lost_after)
        url = str(view.get("url") or "") if st == 200 else ""
        if not url:
            return h._send(404, {"error": "no domain here", "detail": "this cluster is not the domain's, or the "
                                                                       "domain has not run: its door is not known"})
        body = b""
        if method in ("POST", "PUT", "DELETE"):
            if not read_body(h, 1 << 16):
                return
            body = h.rfile.read(int(h.headers.get("Content-Length") or 0))
        headers = {"Content-Type": "application/json", "X-Operator": "console"}
        token = token_of(h.headers)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if h.headers.get("Idempotency-Key"):
            headers["Idempotency-Key"] = h.headers["Idempotency-Key"]
        req = urllib.request.Request(url.rstrip("/") + path + (f"?{query}" if query else ""), data=body or None,
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=90.0 if path == "/domain/handover" else 5.0) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        except (OSError, ValueError) as e:
            return h._send(502, {"error": "the domain did not answer", "detail": str(e)})
        try:
            answer = json.loads(raw or b"{}")
        except PARSE_ERRORS:
            answer = {"detail": raw[:512].decode("utf-8", "replace")}
        h._send(status, answer)

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
                if method in ("POST", "DELETE") and u.path.startswith("/servers/") and \
                        u.path.endswith("/decommission") and u.path.count("/") == 3:
                    user = mnt.admit(self, method)               # `admin`: every unit of a server moves
                    if user is None:
                        return
                    # …its body read as every other door's is (`read_body`; the review's twelfth pass, minor): read
                    # bare, `Content-Length: -1` held the thread 30 s and answered 503 "the store did not take it", and
                    # 20 MB was read whole
                    if method == "POST" and not read_body(self, int(os.environ.get("CONSOLE_MAX_BODY", MAX_BODY))):
                        return
                    return self._send(*mnt.decommission_route(self, method, u.path, user))
                # What a server reaches (ADR-0026's addition): on the Mount too — `admin` on the cluster to write, any
                # grant to look; its body read as every other door's is (`read_body`)
                if method in ("GET", "PUT", "DELETE") and u.path.startswith("/servers/") and \
                        u.path.endswith("/labels") and u.path.count("/") == 3:
                    user = mnt.admit(self, method)
                    if user is None:
                        return
                    if method == "PUT" and not read_body(self, int(os.environ.get("CONSOLE_MAX_BODY", MAX_BODY))):
                        return
                    return self._send(*mnt.labels_route(self, method, u.path, user))
                if u.path in mnt.MOUNT_ROUTES:
                    user = mnt.admit(self, method)
                    if user is None:
                        return                                           # refused, and said so
                    if u.path == "/mounts":
                        return self._send(200, mnt.describe())
                    if u.path == "/drain":
                        return self._send(*mnt.drain_route(method, q, user))
                    return self._send(*mnt.schema_route(method, q, user))
                if u.path == "/api/held" and method == "GET":
                    return self._send(200, mnt.held())                  # a process door: the record proves itself
                if u.path == "/api/backup" and method == "GET":
                    return self._send(*mnt.backup(self))                # …a member's signature, checked here
                if u.path in ("/api/prepare", "/api/take") and method == "POST":
                    return mnt.to_signer(self, u.path)                  # …the outgoing holder's, checked by the signer
                if u.path.startswith("/domain/") and not mnt.domain_local(method, u.path):
                    if mnt.admit(self, "GET") is None:                   # who is calling; the domain decides the rest
                        return
                    return mnt.domain_forward(self, method, u.path, u.query)
                con, path = mnt.resolve(u.path)
                con.dispatch(self, method, path, q)

            # WHAT THE STORE CANNOT HOLD IS SAID, ON EVERY ROUTE (the eleventh review, a minor): a key longer than the
            # store can name a file (`variables.KeyTooLong`) — a keep, a volume, a server's labels under a name of
            # 100 000 characters — raised past the routes that knew only `TooLarge` of a row's size, and the connection
            # dropped with no answer. The store's own limit, in its words, to whoever asked: 413. Raised before a
            # write, so nothing of the reply was sent.
            def _answered(self, method):
                try:
                    self._route(method)
                except TooLarge as e:
                    self._send(413, {"detail": str(e), "error": "too large for the store"})

            def do_GET(self): self._answered("GET")
            def do_POST(self): self._answered("POST")
            def do_PUT(self): self._answered("PUT")
            def do_DELETE(self): self._answered("DELETE")

        return H

    def serve(self, host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
        return open_doors(host, port, self.handler())
