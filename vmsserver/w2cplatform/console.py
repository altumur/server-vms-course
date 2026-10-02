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
# ================================================================================================
from __future__ import annotations

import io
import json
import logging
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .doors import MAX_LIMIT, byte_range

from .secrets import mask_secrets
from .contract import (GARBLED, HEARTBEATS, SCHEMA, SKEW_MAX, Assignment, DrainRefused, Heartbeat, SchemaTooNew, builds,
                       is_live, parse_heartbeat, schema_version)
from .epoch import current_epoch
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
from .access import COOKIE, GLASS_COOKIE, OPEN_ROUTES, Denied, Gate, caller_addr, session_cookie, token_of
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
            if items and now - float(items.get("at", 0)) > self.ttl:
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

    def metrics_text(self) -> str:
        p = self.spec.name
        hbs = heartbeats(self.ctl.objects, p + "/"); now = self.wall()
        live = {w: hb for w, hb in hbs.items() if is_live(p, hb.ts, now, self.lost_after)}
        res = resources_seen(self.ctl.objects)
        lines = [f"# TYPE {p}_workers_live gauge", f"{p}_workers_live {len(live)}",
                 f"# TYPE {p}_worker_headroom gauge",
                 *[f'{p}_worker_headroom{{worker="{w}",server="{hb.extra.get("server", "?")}"}} {hb.extra.get(self.spec.headroom_from, 0)}' for w, hb in live.items()],
                 f"{p}_headroom {sum(int(hb.extra.get(self.spec.headroom_from, 0)) for hb in live.values())}",
                 f"# TYPE {p}_worker_load gauge",              # assigned / capacity: what a target-value policy scales on
                 # …over the workers that ARE a place. A worker holding no place (`place_of` empty) is a
                 # spare: it carries nothing and reports zero capacity, which this formula would read as
                 # fully loaded — and a target-value policy would then scale out for ever, one spare
                 # demanding the next. A spare is counted below instead, as what it is.
                 *[f'{p}_worker_load{{worker="{w}"}} {1 - int(hb.extra.get(self.spec.headroom_from, 0)) / max(1, int(hb.extra.get(self.spec.capacity_from, 1))):.3f}'
                   for w, hb in live.items() if self.ctl.place_of(w) != ""],
                 f"# TYPE {p}_spare_workers gauge",            # running, holding no place, ready to take one
                 f'{p}_spare_workers {sum(1 for w in live if self.ctl.place_of(w) == "")}',
                 f"# TYPE {p}_epoch_conflicts counter",
                 *[f'{p}_epoch_conflicts{{worker="{w}"}} {hb.extra.get("conflicts", 0)}' for w, hb in hbs.items()],
                 f"# TYPE {p}_failover_seconds gauge", f'{p}_failover_seconds{{kind="worst"}} {self.worst_failover}',
                 f"# TYPE {p}_resources_live gauge", f"{p}_resources_live {sum(1 for hb in res.values() if is_live('platform', float(hb['ts']), now, self.lost_after))}",
                 # What the readers of heartbeats skipped and measured (the review's second pass, M6, M9): objects that did
                 # not parse, since this process started; and the furthest a heartbeat's clock has been AHEAD of this
                 # one's — at `FUTURE_TOLERANCE` such a worker stops counting as live.
                 f"# TYPE {p}_heartbeats_garbled counter", f"{p}_heartbeats_garbled {GARBLED.get(p, 0)}",
                 f"# TYPE {p}_resource_heartbeats_garbled counter", f"{p}_resource_heartbeats_garbled {GARBLED.get('platform', 0)}",
                 f"# TYPE {p}_heartbeat_skew_seconds_max gauge", f"{p}_heartbeat_skew_seconds_max {round(SKEW_MAX.get(p, 0.0), 1)}",
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
                  *[f'{p}_resource_full{{server="{s}"}} {round(float((hb.get("space") or {}).get("full", 0)), 3)}' for s, hb in sorted(res.items())],
                  f"# TYPE {p}_resource_short_bytes gauge",
                  *[f'{p}_resource_short_bytes{{server="{s}"}} {int(hb.get("short", 0) or 0)}' for s, hb in sorted(res.items())]]
        # The controller's pass, from the report it leaves in the store (`SpecController.pass_once`): the
        # controller has no port, and a pass that fails, a unit with nowhere to go and an assignment the rows
        # contradicted used to be numbers nowhere. `-1`: no pass yet, or none that succeeded.
        rep = self.ctl.pass_report() or {}
        ago = lambda t: -1 if t is None else round(now - float(t), 1)
        lines += [f"# TYPE {p}_reconcile_last_pass_age_seconds gauge",
                  f"{p}_reconcile_last_pass_age_seconds {ago(rep.get('ts'))}",
                  f"# TYPE {p}_reconcile_last_success_age_seconds gauge",
                  f"{p}_reconcile_last_success_age_seconds {ago(rep.get('last_success'))}",
                  f"# TYPE {p}_reconcile_pass_seconds gauge", f"{p}_reconcile_pass_seconds {rep.get('seconds', 0)}",
                  f"# TYPE {p}_reconcile_failures counter", f"{p}_reconcile_failures {rep.get('failures', 0)}",
                  f"# TYPE {p}_units_unplaced gauge", f"{p}_units_unplaced {rep.get('unplaced', 0)}",
                  f"# TYPE {p}_units_diverged gauge", f"{p}_units_diverged {rep.get('diverged', 0)}",
                  f"# TYPE {p}_rows_garbled gauge", f"{p}_rows_garbled {rep.get('garbled', 0)}",     # rows that do not parse: units nobody serves (the review's second pass, M7)
                  # What a worker says about itself and placement does not read — a person can, now: fenced
                  # (alive, holding nothing), and how often the store did not answer it.
                  f"# TYPE {p}_worker_fenced gauge",
                  *[f'{p}_worker_fenced{{worker="{w}"}} {1 if str(hb.extra.get("fenced")).lower() == "true" else 0}' for w, hb in hbs.items()],
                  f"# TYPE {p}_worker_store_errors counter",
                  *[f'{p}_worker_store_errors{{worker="{w}"}} {hb.extra.get("store_errors", 0)}' for w, hb in hbs.items()],
                  # Units a worker is recording past their lease's end, the store silent (feedback BK): data goes
                  # on, actions wait. Not zero for long is a store that is away, seen from the workers' side.
                  f"# TYPE {p}_worker_unconfirmed gauge",
                  *[f'{p}_worker_unconfirmed{{worker="{w}"}} {hb.extra.get("unconfirmed", 0)}' for w, hb in hbs.items()],
                  f"# TYPE {p}_worker_pass_failures counter",
                  *[f'{p}_worker_pass_failures{{worker="{w}"}} {hb.extra.get("pass_failures", 0)}' for w, hb in hbs.items()]]
        # The sweep's backlog, for subsystems that have blobs to collect. Two cheap reads — a prefix
        # listing and one row — deliberately NOT `blobs_referenced()`, which walks every unit's row: a
        # gauge scraped every fifteen seconds must not cost a full scan of the configuration.
        if any(f.type == "blob" for f in self.spec.fields.values()):
            import json
            marked = json.loads((self.ctl.vars.get(self.ctl.sub.sweep_key())[0] or {}).get("digests", "[]"))
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
            try:
                sid, payload = self.gate.open_glass(str(g.get("who", "")), str(g.get("why", "")), str(g.get("password", "")),
                                                    addr=caller_addr(h.headers, str(getattr(h, "client_address", ("?",))[0])))
            except Denied as e:
                return h._send(e.status, {"detail": e.why, "error": "denied"})
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

    def dispatch(self, h, method: str, path: str, q: dict) -> None:
        """Answer one request for this subsystem. `path` is the route (`/<rows>`, `/where/7`), the mount
        prefix already removed; `h` is the handler (its `_send`, `_body`, `headers`, `rfile`)."""
        con, ctl, spec = self, self.ctl, self.spec
        rows_path = "/" + spec.rows
        if path == "/session":
            return self.session(h, method)
        try:
            self.route_id(method, path)                  # `/<rows>/1/2`: no such route — said before the gate reads an id
        except NoSuchRoute as e:
            return h._send(404, {"detail": str(e), "error": "no such path"})
        if path not in OPEN_ROUTES:                     # the gate: open while this cluster has no key set, shut when it cannot check
            try:
                self.gate.admit(h.headers, *self.needs(method, path, self._named(h, method, path, q)))
            except Denied as e:
                return h._send(e.status, {"detail": e.why, "error": "denied"})
        if method == "GET":
            if path in ("/", "/index.html"):
                return send_file(h, PAGE, "text/html; charset=utf-8", headers=(("Content-Security-Policy", page_csp()),))
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
            rest = path[len(rows_path) + 1:]
            if "/" in rest:                                              # /<rows>/<id>/<field>: the bytes of a blob
                field = rest.partition("/")[2]
                n = int(h.headers.get("Content-Length", 0))
                return h._send(*con.put_blob(self._uid(path), field, h.rfile.read(n), h.headers.get("X-User", "operator")))
            key = self._idem(h, required=False)                          # optional here: a PUT is its own retry
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
        say_where(host)
        srv = ThreadingHTTPServer((host, port), self.handler())
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv


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

        class H(SendMixin, BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def _route(self, method):
                u = urlsplit(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
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
        say_where(host)
        srv = ThreadingHTTPServer((host, port), self.handler())
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv
