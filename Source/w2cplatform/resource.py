"""The resource — a platform job, one per server, pinned there for as long
as the server exists. It knows the shape of what every subsystem leaves on
a server's disks and nothing about what it means:

    <root>/<subsystem>/<unit>/e<epoch>/...          each subsystem's tree: its buckets, and whatever else it
                                                    keeps beside them (a scan's progress, say — its own)
    <root>/.mirror/<server>/<subsystem>/<unit>/...  copies of another server's closed buckets (the knob)

    platform/resources/<server>/heartbeat   {server, ts, url, usage, space: {total, free}, units: {sub: [unit]}, mirrors: {server: n}}
    platform/mirror                         the knob: {enabled, copies}
    platform/space                          the knob: {enabled, high, low, min_days} — the disk's watermark
    <sub>/retention, <sub>/retention/<unit> {days}: each subsystem's policy for its buckets, written by ITS controller

    GET  <url>/buckets/<sub>/<unit>    closed buckets, from the files
    GET  <url>/events/<path>           one bucket (also .mirror/<server>/<path>)
    GET  <url>/mirrored/<server>       which of <server>'s buckets this server holds copies of
    GET  <url>/events?from&to&kind&subsystem&unit       this resource's EventIndex: its buckets and its copies
    GET  <url>/events/wait?want=<sub>/<kind>[/<unit>],…&timeout&since&client   HELD until a line of a wanted kind (of
                                       that unit) is appended here, or the timeout: `{changed, seq, touched}` — a hint to
                                       look, never the events; one held request per `client` (`longpoll.py`)
    PUT  <url>/mirror/<server>/<path>  another resource leaves a copy of one of ITS closed buckets here

    platform/doors/<server>                 {url, since}: where this server's resource answers — a row in the store,
                                            said at start and whenever the address changes (`say_door`)
    GET    <url>/v1/objects?prefix=&scope=local|cluster   the objects this server holds, or every server's (the doors):
                                       `{server, objects: {key: {written, server, size}}, missing: [server]}`
    GET    <url>/v1/objects/<key>?scope=local|cluster     one object; the freshest copy by `written` (headers
                                       `X-Written`, `X-Server`; `X-Missing` names the doors that did not answer)
    PUT    <url>/v1/objects/<sub>/blobs/sha256-…          a peer leaves a copy of a blob here, verified before stored
    DELETE <url>/v1/objects/<sub>/blobs/sha256-…?scope=   a blob let go here, or on every server (the sweep); blobs only

The policy pass runs on a timer: retain each subsystem's buckets by its
policy; relieve the disk if it is over the high mark — the resource measures
and says how many bytes to free, each subsystem decides what to give up;
mirror closed buckets to the next live resource(s) after this one
in sorted order — nobody assigns peers, the rule is the assignment; copy
this server's blobs to the same peers (`mirror_blobs`); and any
subsystem-specific pass a subsystem registered (the VMS registers none: its
footage is in volumes of ObjectStorage, not on this tree). `restore` is the reverse of mirror, run by
the owner at start: a server back with an empty disk pulls its buckets
home. No controller is involved in any of it.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # resource.py — the resource as a platform job: heartbeat, buckets over HTTP, retention by each
# subsystem's
# row, mirror to a peer, restore
#
# **Role in the module.** Lesson 3. One resource per server, pinned there for as long as the server exists.
# It knows the shape of what every subsystem leaves on the server's disks —
# `<root>/<subsystem>/<unit>/e<epoch>/...` — and nothing about what it means; a subsystem may keep files of its
# own beside its buckets (a scan's progress) and the resource neither reads nor names them. Footage is not
# here at all: the VMS writes it into volumes of ObjectStorage, through the host's daemon. It writes its own heartbeat
# object (`platform/resources/<server>/heartbeat`), serves buckets over HTTP, and runs a policy pass on a
# timer: bucket retention by each subsystem's own `<sub>/retention[/<unit>]` row — less what a spec's `holds` keeps
# (`holds.py`) — then the watermark, which asks the subsystems whose spec says `requests: {free: true}` to free bytes by
# a request row, then the mirror. No subsystem's code is called here (the boundary's step 6: it was `register`, a hook
# with a pass of its own and a `free`, and `kept`, set by a subsystem's builder of the resource). Mirroring is a knob (`platform/mirror`), and peers are chosen by a rule — the next `copies`
# live resources after mine in sorted order — so nobody assigns them. `restore` is the reverse, run by the
# owner at start. No controller is involved in any of it. `eventdatabase.EventIndex` is the index the job
# runs over this tree (`Resource.index`), served as `GET /events` and told by `retain` what it removed;
# `console.py` reads `resources_seen`.
#
# ## Module-level names
# - `MIRROR_DIR = ".mirror"` — under a resource root, `.mirror/<server>/<sub>/<unit>/e<epoch>/…` holds
#   copies of another server's closed buckets. Hidden so `subsystems_under` never counts it as this server's
#   data.
# - `MIRROR_KEY = "platform/mirror"` — the Variable `{enabled, copies}`.
# - `RESOURCES = "platform/resources"` — the object-store prefix for resource heartbeats.
# - `DOORS = "platform/doors"` — the store rows `platform/doors/<server> {url, since}`: where each resource answers for
#   its server's objects (`say_door`, `doors`); `/v1/objects?scope=cluster` asks every door it names.
#
# ### `__init__(self, root, server, url, vars_, objects, bucket_seconds=600, wall=time.time, peers=None,
# lost_after=45.0)` `root` is the tree (created), `server` the name that goes into heartbeats and peer
# selection, `url` how others reach this resource's HTTP. `lost_after` is how old a
# peer's heartbeat may be to count as live.
#
# ## Notes
# - The heartbeat's `units` and `mirrors` are derived from the tree on every call — the resource keeps no
#   state a restart could lose.
# - `retain` and `mirror` both walk the tree each pass; on one box that is cheap, and it keeps the job
#   stateless.
# - The console's `/resources` route is `resources_seen` with a `live | silent` label by `lost_after`;
#   `/metrics` counts `w2c_resources_live` the same way.
# ================================================================================================
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import threading
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager, suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .doors import MAX_LIMIT, safe_rel, safe_segment

log = logging.getLogger(__name__)

from .contract import ALIVE_EVERY, BUILD, PRESENCE, SCHEMA, Eyes, check_schema, judge_clock, parse_heartbeat
from .rows import PARSE_ERRORS, Table, answer, counts as garbled_by_table, finite, number
from .events import CONSOLE, Bucket, bucket_names_under, buckets_under, parse_bucket, subsystems_under, tree_owner
from .longpoll import WAIT_MAX, Watch, client_gone, parse_wants

MIRROR_GRACE = 3600.0     # a copy outlives its original by this: two servers, two clocks
MIRROR_DIR = ".mirror"
DOOR_TIMEOUT = 30.0          # seconds the door's socket waits on a peer that sends or reads nothing
PIECE = 1 << 16               # what the mirror's client reads at a time (`PeerClient.get_into`)
MIRROR_MAX = 64 << 20        # the largest bucket one `PUT /mirror/…` takes: ten minutes of events, a storm included
PEER_FAILS = 3               # buckets in a row a peer did not take or give before it is left for this pass (`mirror`, `restore`)
RESTORE_RETRY = 10.0         # a restore that left buckets with peers is tried again after this — doubling each time…
RESTORE_RETRY_MAX = 600.0    # …up to this
EVENTS_INFLIGHT = 8         # `/events` answered at once by one resource; past it, 503 with Retry-After
MIRROR_KEY = "platform/mirror"
SPACE_KEY = "platform/space"
RESOURCES = "platform/resources"

# THE OBJECTS OF A CLUSTER ARE FILES ON EVERY SERVER (the owner's decision of 3 October: the cluster without an
# orchestrator). Each process writes its objects into its own server's directory; this door answers what is here
# (`scope=local`) and what every server holds (`scope=cluster`, the union, the freshest copy of a key by `written`).
# Who the other servers are is a row each resource writes in the store — `platform/doors/<server> {url, since}` —
# because the heartbeats that would say it are objects themselves, behind these very doors.
DOORS = "platform/doors"
DOORS_FRESH = 10.0           # seconds the doors read from the store are used before they are read again
OBJECT_MAX = 64 << 20        # the largest object one `/v1/objects` read or blob `PUT` moves: a blob is a mask or a model
OBJECTS_TIMEOUT = 2.0        # what a peer has to answer a read of the cluster's objects; its silence is named, not waited out
PEER_REST = 10.0             # a peer that did not answer is not asked again for this long — named `missing` meanwhile
SCOPES = ("local", "cluster")
_BLOB_KEY = re.compile(r"^(?:[^/]+/)+blobs/sha256-[0-9a-f]{64}$")


# A blob's key: `<sub>/blobs/sha256-<hex>` — the one kind of object a peer may put here, or a sweep delete: immutable,
# named by its bytes, so any copy that hashes to its name is the object (`blobs.py`).
def is_blob_key(key: str) -> bool:
    return isinstance(key, str) and safe_rel(key) and bool(_BLOB_KEY.match(key))


# The store of THIS server's files: a cluster store's `local`, or the store itself (a box's `FsObjectStore`).
def local_store(objects):
    return getattr(objects, "local", objects)


# `(written, size)` of one object here, or `None`. A store of files says its mtime (`FsObjectStore.stat`); one that
# cannot (a shared store in a test) says the length and `0` for when — nobody's copy is fresher than another's there.
def _stat(store, key: str) -> tuple[float, int] | None:
    stat = getattr(store, "stat", None)
    if stat is not None:
        return stat(key)
    data = store.get(key)
    return None if data is None else (0.0, len(data))


# A prefix of keys, as a request names it: `""`, or segments that are each one name with the last possibly empty
# (`vms/heartbeats/`) or a name's beginning (`vms/heartbeats/w-`). Nothing absolute, no `..`.
def _safe_prefix(prefix: str) -> bool:
    if prefix == "":
        return True
    parts = prefix.split("/")
    return not prefix.startswith("/") and all(safe_segment(p) for p in parts[:-1]) \
        and (parts[-1] == "" or safe_segment(parts[-1]))


DOOR_ROWS = Table("door", "that server's objects are not asked for until it is mended", "row of a door")
PEER_OBJECTS = Table("peer_object", "that object of the peer is left out of the cluster's listing", "entry of a peer's objects")


# The disk under `root`, not the tree on it: `f_bavail` and not `f_bfree`, because reserved blocks are not
# ours to spend. A test cannot fill a disk, so the probe is a seam — `Resource(space_probe=...)`.
def disk_space(root: str) -> tuple[int, int]:
    """(total, free) bytes of the filesystem `root` is on."""
    # `shutil.disk_usage` and not `os.statvfs`, which does not exist on Windows. This is the happy case of
    # a portability problem: the standard library already had the seam, and it keeps the meaning we want on
    # both sides — POSIX `free` is `f_bavail * f_frsize`, exactly the line this replaced, and Windows
    # `free` is GetDiskFreeSpaceExW's "available to the caller", which is the same idea (what is ours to
    # spend) rather than the volume's own free space. The Go port has to write both by hand
    # (`w2cplatform/space_unix.go`, `space_windows.go`); here it is one call.
    u = shutil.disk_usage(root)
    return u.total, u.free


# Parses the JSON line `Bucket.line()` produced (types coerced back). Used by `PeerClient`.
def bucket_from_line(line: str) -> Bucket:
    d = json.loads(line)
    return Bucket(d["subsystem"], str(d["unit"]), int(d["epoch"]), float(d["start"]), float(d["end"]), d["path"], int(d["events"]))


# A bucket's path as a peer names it, before anything is written by it (`restore`): segments that are each one name —
# no `..`, nothing absolute — ending in `.events.jsonl`, the rule the door's own `/events/<path>` keeps.
def _bucket_path(path) -> bool:
    return isinstance(path, str) and safe_rel(path) and path.endswith(".events.jsonl")


class _TooBig(Exception):
    """A bucket over `MIRROR_MAX`: no peer takes it (`mirror`)."""


# Reads the watermark. `high` and `low` are USED fractions of the disk: over `high` the resource starts
# freeing and stops at `low`, and the gap between them is the whole point — one mark alone gives a saw, a
# file freed and a file written, for ever. Choose the gap in HOURS OF INGEST, not in percent: fifty cameras
# at four megabit write about 2.2 TB a day, and ten percent of a 20 TB disk is less than one of them.
# `min_days` is the floor no unit is cut below; when everything is on the floor the answer is a shortfall,
# said out loud, and not a quiet cut into yesterday.
#
# ON UNLESS SOMEBODY TURNED IT OFF (the platform review, "what happens when the disk fills is chosen by the
# code"; feedback BM). It used to be off until a row said `enabled: true` — and an installation where nobody
# had written that row met a full disk with no policy at all: the recorder's writes failed, the store and the
# event log on the same partition failed with them, and nothing had been decided by anyone. With no row the
# watermark now runs on its defaults; `enabled: false` is the decision not to have one, and it is a decision
# somebody makes.
#
# `WATERMARK_DEFAULT=off` is for tests, said by the environment like `STORE_VOLATILE`: a suite runs on a
# developer's disk, which is as full as it happens to be, and must not start cutting its fixtures for that.
#
# A ROW THAT DOES NOT PARSE IS NOT "OFF" EITHER (the review's seventh pass, part 2). `high: "85%"` raised out of here,
# and `relieve` failed on every pass — a disk at 98 % freed nothing, with the knob read last in hand and unused. Each
# number is read alone now: one that does not parse — or is `nan`, `inf`, a mark under no disk (`finite`) — is the
# one in `last` (what the caller read last), else the default, and the row is counted once until it parses again
# through the one reader of rows (`SPACE`), logged once. `enabled` is a word compared with a word: it always reads.
# The fields taken from elsewhere come back in `garbled`, for the caller to say (`Resource.relieve`, `space_garbled`
# in the resource's heartbeat).
SPACE = Table("space", "each number that does not parse is the one read last, or the default, until it is mended")


def space_defaults() -> dict:
    return {"enabled": os.environ.get("WATERMARK_DEFAULT", "on") != "off", "high": 0.85, "low": 0.75, "min_days": 3.0}


def space_settings(vars_, last: dict | None = None) -> dict:
    """The watermark's settings; with `garbled: [field, …]` when a number of the row does not parse."""
    items, _ = vars_.get(SPACE_KEY)
    d = items or {}
    dflt = space_defaults()
    out = {"enabled": d.get("enabled") == "true" if "enabled" in d else dflt["enabled"]}
    garbled, errors = [], []
    for f in ("high", "low", "min_days"):
        try:
            out[f] = finite(d.get(f, dflt[f]))
        except (ValueError, TypeError) as e:
            out[f] = (last or dflt).get(f, dflt[f])
            garbled.append(f); errors.append(f"{f}: {e}")
    if garbled:
        SPACE.garbled(SPACE_KEY, "; ".join(errors))
        out["garbled"] = garbled
    else:
        SPACE.parsed(SPACE_KEY)
    return out


# Reads the knob: `enabled` is true only if the row exists and says `"true"`; `copies` defaults to 1. A `copies` that
# does not parse is ONE copy (the seventh pass, beside the watermark): it raised out of the mirror on every pass, and
# a mirror the operator turned on copied nothing — the row is counted (`MIRROR`) and logged once; one copy is the
# least the switch that IS readable asked for.
MIRROR = Table("mirror", "mirrored to one peer, until it is mended")


def mirror_settings(vars_) -> dict:
    items, _ = vars_.get(MIRROR_KEY)
    return {"enabled": bool(items) and items.get("enabled") == "true",
            "copies": MIRROR.read(MIRROR_KEY, lambda: int(finite((items or {}).get("copies", 1))), 1)}


# The unit's days if its subsystem set `<sub>/retention/<unit>`, else the subsystem's `<sub>/retention`,
# else a year. For the VMS the per-unit row is the derived row `vms/retention/<id>` written by
# `SpecController._derived` from `events_retention_days`; on delete it becomes `{days: 0}` so the buckets go
# on the next pass. Each subsystem's controller owns its row; the resource only reads.
#
# THE ALARMS' TREE HAS DAYS OF ITS OWN (feedback BO). `<sub>.alarms/<unit>` is kept by
# `<sub>/alarms_retention/<unit>`, else `<sub>/alarms_retention`, else THREE YEARS — and three years is what
# a subsystem that says nothing gets, which is every one that raises an alarm and has no row for it: the
# recorder's `archive.shallow`, say. That row has no `on_delete`: deleting a unit ends its observations at the
# next pass, and not the record of what happened at it.
ALARM_DAYS = 1095.0

# A row of days that does not read as days (the product team's sibling of the review's ninth pass): `float("nan")` is
# a number, and `nan` days passed no comparison — nothing swept, nothing said; `-1` swept every bucket of the unit, the
# current one too; `inf` is no number of days any controller writes. Only a finite number, not below nought, is days;
# anything else raises, and `Resource._days` keeps that unit's buckets — counted here, once until it is mended, and
# named in the heartbeat (`retention_garbled`). `0` stays what it is: the days of a deleted unit.
RETENTION = Table("retention", "its buckets are kept, not swept, until it is mended", "row of days")


def _days_of(raw) -> float:
    days = finite(raw)
    if days < 0:
        raise ValueError(f"{raw!r} is not a number of days")
    return days


def retention_days(vars_, subsystem: str, unit: str, default: float = 365.0) -> float:
    """The unit's days if its subsystem set them, else the subsystem's, else a year. A row that says nothing —
    a unit whose field is left to inherit (М12 Lesson 12) — is not zero days: it is the next link. A row whose
    days are not a finite number not below nought RAISES: not knowing a unit's days is not any number of them."""
    subsystem, alarms = tree_owner(subsystem)
    if subsystem == "audit":                         # who deleted it and who read it: kept as long as alarms are (`journal.py`)
        default = ALARM_DAYS
    family, default = ("alarms_retention", ALARM_DAYS) if alarms else ("retention", default)
    for path in (f"{subsystem}/{family}/{unit}", f"{subsystem}/{family}"):
        items, _ = vars_.get(path)
        if items and str(items.get("days", "")).strip() not in ("", "None"):
            return _days_of(items["days"])
    return default


# What the console's own buckets must outlive: the longest-kept unit on this resource.
#
# An operator's record REFERS to events — a mark names a unit, and an acknowledgement (when there is one)
# names the alarm it answers. The reference is one-way and the asymmetry matters: a record that outlives
# what it refers to is harmless clutter, while an event that outlives the record ABOUT it silently goes
# back to looking unanswered. Sweeping the console's bucket on its own clock would do exactly that, and it
# would do it a year later, to the one class of line somebody is going to be asked about.
#
# So the console's days are a floor, not a setting: whatever anybody keeps longest, its records keep too.
# It costs nothing — an operator writes a handful of lines a day against a worker's thousands — and it is
# the one rule that has to exist BEFORE the records do, because getting it wrong is invisible until the
# day the record is missing.
def console_floor(days_of: dict[tuple[str, str], float]) -> float:
    """The longest retention among everything that is not the console's own."""
    others = [d for (sub, _), d in days_of.items() if tree_owner(sub)[0] != CONSOLE]
    return max(others) if others else 0.0


# The rule that replaces a map: sort the other live servers, take those after mine then wrap around, and
# keep the first `copies`. `test_the_resource_is_a_platform_job…`: with `srv-a, srv-b, srv-c`, `srv-a`'s
# peer is `srv-b` and `srv-c`'s is `srv-a`.
def peers_of(server: str, live: list[str], copies: int) -> list[str]:
    """The rule that replaces a map: the next `copies` live resources after mine, in sorted order."""
    others = sorted(s for s in live if s != server)
    if not others:
        return []
    after = [s for s in others if s > server] + [s for s in others if s < server]
    return after[:copies]


# Every resource heartbeat under `platform/resources/`, keyed by `server`, whatever its age. Callers filter
# by `ts`.
# THE WORKERS OF THIS SERVER (the owner's decision, 3 Oct, on the review's eleventh pass): `(workers, running)`, each
# `{subsystem: [name]}` — the product's fields. Each worker registers here (`Worker.present`): it holds a lock on
# `<root>/.workers/<instance>.lock` for as long as its process lives, and says beside it what it is called (`.json`).
# WORKERS: every registration this server has — the slots placed on it. RUNNING: those whose lock cannot be taken — a
# process that still lives, hung or not.
# A registration whose process ended stays placed (the server's supervisor brings it back under its name) until a newer
# registration here says the same name, or until it has said nothing for `PRESENCE_KEPT` (the worker touches its lock
# at every heartbeat) — then it is removed: the server does not run it any more. A `.json` that does not read is a
# process whose name is not known yet: under `?`, so it is taken for nobody's.
#
# …AND WHAT CANNOT BE READ IS NOT "NOT HERE" (the review's twelfth pass, blocker 3). A directory that does not list (no
# rights, EIO, the volume not mounted where the workers write), a lock that does not open (EMFILE), a LIVE lock whose
# `.json` is absent, torn or names no subsystem — each was read as an empty list, or as a lock under `?`: the worker "not
# listed" by a resource that answers, its slot released, its cameras given to a second holder while its process still
# wrote them. Now the resource says what it could not read: a directory that does not list says no lists at all
# (`presence_error`, `workers`/`running` absent — "not said", which `slot_fate` takes for `wait`); a live lock whose
# owner it cannot read, or a lock it cannot open, is counted (`presence_unread`), and then no worker of this server is
# judged by being absent from the lists (`Controller.said_on`). A `.json` that reads, with `name: ""`, is a process that
# is nobody — a spare waiting, a process fenced off its name — and writes nothing: not a doubt. And whose locks are held
# is said by the lock's own name too (`running_instances`, `presence_name(instance)`): the controller matches it against
# the instance a slot names as its holder, so a live holder is "running" whatever its `.json` says (`slot_fate`).
PRESENCE_KEPT = 86400.0
PRESENCE_FIELDS = ("workers", "running", "running_instances", "presence_unread", "presence_error")   # what `presence_here` says, all of it


def presence_here(root: str | None, now: float | None = None) -> dict:
    """`{"workers": {sub: [name]}, "running": {sub: [name]}}`, with `presence_unread: n` when n live registrations (or
    locks that do not open) could not be read — or `{"presence_error": why}` alone when the directory does not list."""
    import fcntl
    now = time.time() if now is None else now
    if not root:
        return {"workers": {}, "running": {}, "running_instances": []}
    d = os.path.join(root, PRESENCE)
    try:
        names = sorted(os.listdir(d))
    except OSError as e:                                      # missing too: a worker that registered here made it
        return {"presence_error": f"{d} does not list: {e.strerror or e}"}
    seen, unread, held = [], 0, []                            # seen: (sub, name, alive, touched, lock path)
    for n in names:
        if not n.endswith(".lock"):
            continue
        lock = os.path.join(d, n)
        try:
            with open(lock, "rb") as f:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    alive = False
                    fcntl.flock(f, fcntl.LOCK_UN)
                except OSError:                               # held: the process lives
                    alive = True
            touched = os.path.getmtime(lock)
            if alive:
                held.append(n[:-len(".lock")])
        except FileNotFoundError:
            continue                                          # removed between the listing and the look: gone
        except OSError:
            unread += 1                                       # a lock that does not open may be held: not known
            continue
        try:
            with open(lock[:-len(".lock")] + ".json") as j:
                said = json.load(j)
            sub, name = said["sub"], said["name"]
            if not isinstance(sub, str) or not sub or not isinstance(name, str):
                raise TypeError("sub or name is not a name")
        except (OSError, *PARSE_ERRORS):
            sub, name = "?", n[:-len(".lock")]
            if alive:
                unread += 1                                   # a live process whose name cannot be read
        seen.append((sub, name, alive, touched, lock))
    placed: dict[str, set] = {}
    alive_: dict[str, set] = {}
    for sub, name, alive, touched, lock in seen:
        newer = any(o[:2] == (sub, name) and (o[2] or o[3] > touched) for o in seen if o[4] != lock)
        if not alive and (newer or now - touched > PRESENCE_KEPT):
            for path in (lock[:-len(".lock")] + ".json", lock):
                with suppress(OSError):
                    os.remove(path)
            continue
        if name and sub != "?":
            placed.setdefault(sub, set()).add(name)
            if alive:
                alive_.setdefault(sub, set()).add(name)
    out = {"workers": {k: sorted(v) for k, v in placed.items()}, "running": {k: sorted(v) for k, v in alive_.items()},
           "running_instances": sorted(held)}
    if unread:
        out["presence_unread"] = unread
    return out


def workers_here(root: str | None, now: float | None = None) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """`(workers, running)` as `presence_here` reads them — empty where it could not read (a bench's view)."""
    said = presence_here(root, now)
    return said.get("workers", {}), said.get("running", {})


# The key of a server's resource heartbeat, and what its tree measures as that heartbeat says it — what a subsystem reads
# of a resource, through these and not by the layout of the store (the boundary's step 5: a subsystem spelt
# `platform/resources/<server>/heartbeat#space.total` itself). `space_total(seen, server)`: bytes, 0 when not said —
# a number that does not parse is read as not said (`rows.number`), never as an error out of the caller's page.
def heartbeat_key(server: str) -> str:
    return f"{RESOURCES}/{server}/heartbeat"


def space_total(seen: dict, server: str) -> int:
    from .rows import number
    space = (seen.get(server) or {}).get("space")
    return number(f"{heartbeat_key(server)}#space.total", (space if isinstance(space, dict) else {}).get("total"), int, 0)


def resources_seen(objects) -> dict[str, dict]:
    def parse(raw: bytes) -> dict:                             # one that does not parse is skipped and counted (the review's second pass, M6)
        hb = dict(json.loads(raw))
        hb["server"], finite(hb["ts"])                         # what every reader of this dict asks of it — `server` a name
        # (`ts` a finite number: `Infinity` was a resource live for ever, `NaN` one silent — and a silent resource MOVES
        # a recorder's units; the review's eleventh pass, the sibling of the slot's `until`)
        # (`parse_heartbeat` checks it: `["srv-x"]` was the key of `out` below, and `/metrics`, `restore` and the mirror
        # raised on it — the review's tenth pass)
        # …and what the mirror asks of it (the review's seventh pass): `url` to send to and take back from, `mirrors` a
        # map — read bare, a heartbeat without them raised out of `mirror` for every peer, and out of `restore`, which
        # runs at the start with nothing around it.
        if not isinstance(hb.get("url", ""), str) or not isinstance(hb.get("mirrors", {}), dict):
            raise TypeError("url or mirrors is not what a resource heartbeat says")
        return hb

    out = {}
    for key in objects.list(RESOURCES + "/"):
        if key.endswith("/heartbeat"):
            raw = objects.get(key)
            hb = parse_heartbeat(key, raw, parse) if raw else None
            if hb is not None:
                out[hb["server"]] = hb
    return out


# The server names present under `<root>/.mirror/`.
def mirrored_servers(root: str) -> list[str]:
    try:
        return sorted(d for d in os.listdir(os.path.join(root, MIRROR_DIR)) if os.path.isdir(os.path.join(root, MIRROR_DIR, d)))
    except FileNotFoundError:
        return []


# Copies this resource holds of `server`'s buckets, parsed relative to `.mirror/<server>` so `path` is the
# original path on `server`. Line counts are taken from the copy.
def mirrored_buckets(root: str, server: str, bucket_seconds: int = 600) -> list[Bucket]:
    """Copies this resource holds of <server>'s buckets; `path` is the ORIGINAL path on <server>."""
    base = os.path.join(root, MIRROR_DIR, server)
    out = []
    for d, _, files in os.walk(base):
        for f in files:
            p = os.path.join(d, f)
            parsed = parse_bucket(p, base)
            if parsed:
                sub, unit, epoch, start = parsed
                with open(p) as fh:
                    n = sum(1 for l in fh if l.strip())
                out.append(Bucket(sub, unit, epoch, start, start + bucket_seconds, os.path.relpath(p, base), n))
    return sorted(out, key=lambda b: (b.start, b.epoch))


# How many copies, from the names alone — what the heartbeat says every ten seconds. `mirrored_buckets` opens
# every copy to count its lines; the heartbeat wants a number of files.
def mirrored_count(root: str, server: str) -> int:
    base = os.path.join(root, MIRROR_DIR, server)
    return sum(1 for d, _, files in os.walk(base) for f in files if parse_bucket(os.path.join(d, f), base))


# What a peer answered that does not parse: a line of its listing, a bucket's path that is not a bucket's.
LISTING_MAX = 64 << 20       # the longest `/mirrored/<server>` read: some 300 000 buckets


def _ok(r, what: str) -> None:
    if r.status != 200:
        raise IOError(f"{what}: {r.status}, not a 200")


# A peer's answer read whole, or an `IOError` (the review's ninth pass, a minor, and its siblings): only an answer with a
# frame — chunks, or a length that is a number (`console.framed`) — can be told whole from cut, and one with a length
# must bring all of it (`http.client` returns what came when the connection closes early, and says nothing). The
# listing matters most: a listing cut short is a peer that holds less, and `restore` takes a peer that gave all it
# listed for one that gave everything (`_restored_from`).
def _whole(r, what: str, limit: int) -> bytes:
    import http.client
    from .console import framed
    if not framed(r):
        raise IOError(f"{what}: the answer has neither chunks nor a length — whether it is whole cannot be told")
    want = r.length                                           # asked before the body: `length` counts down as it is read
    try:
        data = answer(r, limit)
    except http.client.HTTPException as e:
        raise IOError(f"{what}: the answer was cut short ({e!r})") from None
    if want is not None and len(data) != want:
        raise IOError(f"{what}: {len(data)} of {want} bytes")
    return data


PEER_LINES = Table("peer_line", "that bucket is not copied either way until the peer says it whole", "line of a peer's listing")


class Listing(list):
    """A peer's listing of the buckets it holds, and how many of its lines were not read (`skipped`)."""
    skipped = 0


# How one resource talks to another: HTTP. Tests substitute an in-process client with the same three methods
# over directories.
class PeerClient:
    """How one resource talks to another: HTTP; tests substitute an in-process client."""
    def __init__(self, timeout: float = 5.0): self.timeout = timeout

    # `GET <url>/mirrored/<server>` — which of `server`'s buckets the peer already holds.
    # A line that does not parse is that bucket's trouble (the review's eighth pass, part 4): skipped and counted
    # (`PEER_LINES`), and the rest of the listing stands — read bare, one line took every copy of the peer with it.
    # Read up to `LISTING_MAX` (a year of one server's buckets is some ten megabytes), and only a 200 is a listing —
    # whole (`_whole`; the ninth pass): a listing cut short is not a peer that holds less.
    #
    # …and how many it skipped is said with it (`Listing.skipped`; the review's tenth pass, minor): `restore` took a
    # listing with lines left out for everything the peer had, and never asked that peer again.
    def mirrored(self, url: str, server: str) -> list[Bucket]:
        with urllib.request.urlopen(f"{url}/mirrored/{server}", timeout=self.timeout) as r:
            _ok(r, f"GET mirrored/{server}")
            lines = [l for l in _whole(r, f"GET mirrored/{server}", LISTING_MAX).decode(errors="replace").splitlines() if l.strip()]
        key = f"platform/mirrored/{server}@{url}#"
        out = Listing(b for i, l in enumerate(lines) if (b := PEER_LINES.read(f"{key}{i}", lambda l=l: bucket_from_line(l))) is not None)
        out.skipped = len(lines) - len(out)
        return out

    # `PUT <url>/mirror/<server>/<path>` with the bucket's bytes; anything but 200/201/204 raises `IOError`.
    def put(self, url: str, server: str, path: str, data: bytes) -> None:
        req = urllib.request.Request(f"{url}/mirror/{server}/{path}", data=data, method="PUT")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status not in (200, 201, 204):
                raise IOError(f"PUT mirror {path}: {r.status}")

    # `PUT <url>/<path>` with arbitrary bytes and headers — the door a subsystem's own PUT route goes
    # through. The platform does not know what is being sent; it knows how to send it.
    def put_raw(self, url: str, path: str, data: bytes, headers: dict | None = None) -> int:
        req = urllib.request.Request(f"{url}/{path.lstrip('/')}", data=data, method="PUT", headers=headers or {})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status not in (200, 201, 204):
                raise IOError(f"PUT {path}: {r.status}")
            return r.status

    # `GET <url>/<path>` with arbitrary bytes back — the reading half of the same door.
    def get_raw(self, url: str, path: str) -> bytes:
        with urllib.request.urlopen(f"{url}/{path.lstrip('/')}", timeout=self.timeout) as r:
            _ok(r, f"GET {path}")
            return _whole(r, f"GET {path}", MIRROR_MAX)

    # `GET <url>/events/.mirror/<server>/<path>` — pull a copy back (restore).
    def get(self, url: str, server: str, path: str) -> bytes:
        with urllib.request.urlopen(f"{url}/events/{MIRROR_DIR}/{server}/{path}", timeout=self.timeout) as r:
            _ok(r, f"GET mirror {path}")
            return _whole(r, f"GET mirror {path}", MIRROR_MAX)

    # A BUCKET IS NEVER HELD WHOLE ON EITHER SIDE OF THE MIRROR (the review's seventh pass, beside "the resource sends a
    # bucket whole"). The door sends a bucket in pieces and takes a copy in pieces now; the resource's own client read a
    # bucket into memory to send it (`mirror`) and a copy into memory to write it back (`restore`) — sixty megabytes of
    # a storm, held whole, once per bucket. These two do it a piece at a time: `put_file` hands the open file to the
    # connection with its length (`http.client` sends a file in blocks), and `get_into` writes the reply to a file a
    # piece at a time and checks the length the peer said — a reply that ends short is an error, never a smaller bucket.
    # `mirror` and `restore` use them when the client has them; a client a test substitutes may have only `put`/`get`.
    def put_file(self, url: str, server: str, path: str, f, size: int) -> None:
        req = urllib.request.Request(f"{url}/mirror/{server}/{path}", data=f, method="PUT",
                                     headers={"Content-Length": str(size)})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status not in (200, 201, 204):
                raise IOError(f"PUT mirror {path}: {r.status}")

    # Only a 200 is a bucket, and no bucket is bigger than a peer takes (`MIRROR_MAX`): what a door says on 204, 206 or
    # past the bound is not written as one (the review's eighth pass, the product team's sibling — there, a 503's body
    # was stored as a bucket for good; here `urlopen` raised for 4xx/5xx already, and a 2xx that is not 200 did not).
    #
    # …AND ONLY A FRAMED ANSWER IS A WHOLE ONE (the review's ninth pass, a minor). An answer without a length and without
    # chunks — a proxy that took the framing off — ends where the connection ends, and a peer's door that died half way
    # gave a shorter bucket, written as the bucket for good; `Content-Length: ten` raised a bare `ValueError` after the
    # body was written. `framed` (the console's door reader asks the same) refuses both before a byte is read: the length
    # is `http.client`'s own, a number or nothing; chunks cut short raise in the read — both an `IOError`, the bucket
    # asked for again.
    def get_into(self, url: str, server: str, path: str, dest) -> int:
        import http.client
        from .console import framed
        try:
            with urllib.request.urlopen(f"{url}/events/{MIRROR_DIR}/{server}/{path}", timeout=self.timeout) as r:
                _ok(r, f"GET mirror {path}")
                if not framed(r):
                    raise IOError(f"GET mirror {path}: the answer has neither chunks nor a length — whether it is whole "
                                  f"cannot be told")
                want, got = r.length, 0                       # asked before the body: `length` counts down as it is read
                while True:
                    part = r.read(PIECE)
                    if not part:
                        break
                    got += len(part)
                    if got > MIRROR_MAX:
                        raise IOError(f"GET mirror {path}: over {MIRROR_MAX} bytes, larger than any bucket")
                    dest.write(part)
        except http.client.HTTPException as e:
            raise IOError(f"GET mirror {path}: the answer was cut short ({e!r})") from None
        if want is not None and got != want:
            raise IOError(f"GET mirror {path}: {got} of {want} bytes")
        return got

    # -- another server's objects (`/v1/objects`, always `scope=local`: a peer answers for itself, never for others) --
    # `GET <url>/v1/objects?prefix=…` — `{key: {written, server, size}}` of what that server holds. Only a 200 is a
    # listing, whole (`_whole`), and only a map is one.
    def objects(self, url: str, prefix: str, timeout: float | None = None) -> dict:
        q = urllib.parse.urlencode({"prefix": prefix, "scope": "local"})
        with urllib.request.urlopen(f"{url}/v1/objects?{q}", timeout=timeout or self.timeout) as r:
            _ok(r, "GET /v1/objects")
            d = json.loads(_whole(r, "GET /v1/objects", LISTING_MAX))
        objs = d.get("objects") if isinstance(d, dict) else None
        if not isinstance(objs, dict):
            raise IOError(f"GET /v1/objects at {url}: the answer is not a listing of objects")
        return objs

    # `GET <url>/v1/objects/<key>` — `(bytes, written, server)`, or `None` when that server has no such object.
    def object(self, url: str, key: str, timeout: float | None = None) -> tuple[bytes, float, str] | None:
        import urllib.error
        try:
            with urllib.request.urlopen(f"{url}/v1/objects/{urllib.parse.quote(key)}?scope=local",
                                        timeout=timeout or self.timeout) as r:
                _ok(r, f"GET {key}")
                data = _whole(r, f"GET {key}", OBJECT_MAX)
                return data, finite(r.headers.get("X-Written", "")), str(r.headers.get("X-Server", ""))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    # `PUT <url>/v1/objects/<sub>/blobs/sha256-…` — a copy of one of this server's blobs; the peer hashes it before it
    # keeps it. Anything but 204 is an `IOError` (a refusal raises from `urlopen` already).
    def put_blob(self, url: str, key: str, data: bytes) -> None:
        req = urllib.request.Request(f"{url}/v1/objects/{urllib.parse.quote(key)}", data=data, method="PUT",
                                     headers={"Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status != 204:
                raise IOError(f"PUT {key}: {r.status}, not a 204")

    # `DELETE <url>/v1/objects/<key>?scope=local` — the peer lets its copy of a blob go; `True` if it had one.
    def delete_object(self, url: str, key: str, timeout: float | None = None) -> bool:
        req = urllib.request.Request(f"{url}/v1/objects/{urllib.parse.quote(key)}?scope=local", method="DELETE")
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
            _ok(r, f"DELETE {key}")
            d = json.loads(_whole(r, f"DELETE {key}", LISTING_MAX))
        return isinstance(d, dict) and isinstance(d.get("deleted"), dict) and any(d["deleted"].values())


# A callable of the pass is called with what it takes of the optional words, and nothing it does not: `progressed`
# (the pass's pulse: a step that works for minutes says it is moving, or the pulse calls it stuck — the review's fourth
# pass). Asked by the signature and not by trying: a `TypeError` raised INSIDE one used to be read as "it does not take
# the word", and it was run a second time.
def _call_hook(fn, *args, **optional):
    import inspect
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return fn(*args)
    if any(p.kind is p.VAR_KEYWORD for p in params.values()):
        return fn(*args, **optional)
    return fn(*args, **{k: v for k, v in optional.items() if k in params})


# THE RESOURCE OF A SERVER, AS THE PLATFORM BUILDS IT (`python3 -m w2cplatform resource`, `host.resource`): the job over
# its tree with the event index attached, and what is kept read from the loaded specs (`holds`). Nothing of a subsystem's
# is installed on it (the boundary's step 6: it was a subsystem's builder of the resource, which set what it keeps).
def platform_resource(root: str, server: str, url: str, vars_, objects, wall=None, peers=None,
                      bucket_seconds: int = 600, **kw) -> "Resource":
    from .eventdatabase import EventIndex
    wall = wall or time.time
    r = Resource(root, server, url, vars_, objects, bucket_seconds, wall, peers, **kw)
    r.index = EventIndex(root, server, wall, bucket_seconds)
    return r


# What the loaded specs' `holds:` keep, for one pass (`holds.kept` over the catalogue: the specs this process loaded, or
# the directory `SPEC_DIR` names).
def kept_by_specs(vars_, progressed=None):
    from . import catalog, holds
    return holds.kept(vars_, catalog.specs(), progressed)


# THE OBJECT DOOR SAYS WHAT WENT WRONG, NOT WHERE (the review's thirteenth pass, minors; the product's cross-check (c)).
# A copy this server holds that cannot be read (EACCES, EIO) raised past the door and dropped the connection; a copy it
# could not keep (ENOSPC) was "the body did not arrive in time" with the file's absolute path in it. Each is a 503 now,
# in words — the error's own words, never a path on this server's disk.
class ObjectUnreadable(Exception):
    """This server's copy of an object is there and cannot be read: `str()` is the reason, without a path."""


class ObjectUnkept(Exception):
    """A copy sent here could not be kept on this server's disk: `str()` is the reason, without a path."""


def _why(e: OSError) -> str:
    """An `OSError` in words — its `strerror`, never the file it names."""
    return e.strerror or type(e).__name__


def _summed(spaces: list[dict]) -> dict:
    """Disks summed, as `Resource.space()` sums its volumes."""
    total = sum(int(sp.get("total", 0)) for sp in spaces)
    free = sum(int(sp.get("free", 0)) for sp in spaces)
    return {"total": total, "free": free, "used": total - free, "full": (total - free) / total if total else 0.0}


def _merged(units: list[dict]) -> dict[str, list[str]]:
    """What is on each volume, as one (`Resource.units`)."""
    out: dict[str, list[str]] = {}
    for per in units:
        for sub, names in per.items():
            out.setdefault(sub, []).extend(u for u in names if u not in out.get(sub, []))
    return {k: sorted(v) for k, v in out.items()}


def _counted(mirrors: list[dict]) -> dict[str, int]:
    """Copies of each server, over every volume."""
    out: dict[str, int] = {}
    for per in mirrors:
        for server, n in per.items():
            out[server] = out.get(server, 0) + n
    return out


class Resource:
    """One server's resource: its tree, its heartbeat, its policy pass."""

    def __init__(self, root: str | None, server: str, url: str, vars_, objects, bucket_seconds: int = 600,
                 wall=time.time, peers: PeerClient | None = None, lost_after: float = 45.0, space_probe=None,
                 volumes: dict[str, str] | None = None, quotas: dict[str, int] | None = None, clock=time.monotonic):
        # A server's disks, named. One volume is the common case and stays the whole of `root`; several are
        # what a box with more than one disk actually has, and they are the resource's INTERNAL structure:
        # the resource is still one per server, because reachability is a property of a server and a volume
        # has no address. What a volume does have is its own bottom — which is why the watermark, the only
        # thing here that ever measured a disk, becomes a loop over them.
        self.volumes = dict(volumes) if volumes else {"default": root}
        if not self.volumes or any(not v for v in self.volumes.values()):
            raise ValueError("a resource needs at least one volume with a path")
        # A CEILING per volume, in bytes, and zero means "the disk is the ceiling". Two things need it and
        # neither is exotic. A network archive has no disk to ask — `shutil.disk_usage` on a mount point
        # answers about the machine, not the bucket. And two volumes on ONE partition — which is how an
        # operator splits a disk between a long-retention archive and a short one — would otherwise both
        # read the same free space and both believe they own it.
        #
        # A quota is a ceiling, not a reservation: a volume gets the SMALLER of what its quota leaves and
        # what the disk actually has. Nothing is set aside, and a disk filled by somebody else is still
        # full, whatever the quota says.
        self.quotas = {k: int(v) for k, v in (quotas or {}).items() if int(v) > 0}
        self.root = next(iter(self.volumes.values()))          # the first: what single-volume callers still mean
        self.server, self.url, self.vars, self.objects = server, url, vars_, objects
        self.bucket_seconds, self.wall, self.peers, self.lost_after = bucket_seconds, wall, peers or PeerClient(), lost_after
        check_schema(vars_)                                  # a build older than the store does not run at all
        self.space_probe = space_probe or disk_space         # a test cannot fill a disk
        self.last_usage: int | None = None                   # the tree walk's answer, refreshed by `pass_`
        self._volume_usage: dict[str, int] = {}              # …and per volume, for the ones with a quota
        self.usage_at = 0.0                                  # …and when it was taken: a stale number must say so
        self.clock = clock                                   # monotonic: what the pass's pulse measures by (a test passes its own)
        # Which peers are there, by what this resource saw change on its own clock (`Eyes`; the review's thirteenth pass,
        # blocker 4): a peer whose clock ran behind was left out of the mirror and the restore. A test that drives only
        # the wall drives this too.
        self.eyes = Eyes(clock if clock is not time.monotonic else judge_clock(wall), wall)
        self._progress_at = clock()                          # when the running pass last got somewhere (`pass_`'s pulse)
        self._pass_started: float | None = None              # …and when it began, while one runs (`beat`)
        self._stuck_said = False
        self._beating: threading.Thread | None = None        # the beat's own thread, once started (`start_beat`)
        self._beat_at: float | None = None                   # by `clock`, when a heartbeat or a beat last went out
        # The looks at the disks with a deadline (`_probe`): the one running per name, the last answers, and since when
        # each that has not answered has been waited for.
        self._probe_lock = threading.Lock()
        self._probes: dict[str, tuple] = {}
        self._looked: dict[str, object] = {}
        self._stuck: dict[str, float] = {}
        self.index = None                          # an eventdatabase.EventIndex over this tree, if the job runs one: served as GET /events
        # What the last pass could NOT free, in bytes, by volume. Over the mark and nothing left to give up is
        # the one state the watermark cannot mend, and it used to be a number in a log line: said in the
        # heartbeat, it is a metric on any console (`w2c_resource_short_bytes`) and somebody's alert.
        from .journal import Journal
        self.journal = Journal(self.root, "resource", wall)     # what the policy removed (`journal.py`)
        self.short: dict[str, int] = {}
        self.mirror_removed = 0                    # copies of other servers' buckets this resource has let go by age
        # What `mirror` and `restore` could not do, said in the heartbeat and on `/metrics` (the review's eighth pass): a
        # peer that did not answer, a bucket a peer did not take or give, one too big for the door — counted since start,
        # and the restore's buckets still with peers, with when it is tried again (`restore_due`).
        self.mirror_failed = self.mirror_too_big = self.restore_failed = 0
        # Buckets past their days `retain` could not remove, since start (`_removed`): one that will not go does not stop
        # the rest; and whether the last pass met one, for "said once a spell".
        self.retain_failed, self._retain_failing, self._retain_failed_pass = 0, False, False
        self.mirror_peers_failed: list[str] = []   # the peers the last `mirror` could not copy to, or not all
        self._too_big: set[str] = set()            # buckets no peer takes (over `MIRROR_MAX`, or refused 413): not sent again
        self.restore_left: int | None = None       # buckets known to be with peers and not back; None: no restore yet
        self.restore_peers_failed: list[str] = []  # the peers the last `restore` could not list, or not take all from
        self._restore_tries = 0
        self._restore_next = 0.0                   # by `clock`: when `restore_due` says to try again
        self._restore_ok = False                   # a restore ran through once with a live peer, or with nobody to ask (`restore`)
        self._restored_from: set[str] = set()      # the peers that listed their copies of this server and gave them all back
        self.retention_garbled: list[str] = []     # `<sub>/<unit>` whose days the last `retain` could not read: kept, not swept
        self._space_knob: dict | None = None       # the watermark's settings as last READ — what a pass uses when the store does not answer
        self.space_garbled = ""                    # what the watermark acts on while its row does not parse (`relieve`), for the heartbeat
        # `(progressed) -> (subsystem, unit, start, end) -> bool`: the buckets `retain` must leave — what the loaded specs'
        # `holds` say (`holds.py`), read once a pass. A test may give its own.
        self.kept = lambda progressed=None: kept_by_specs(self.vars, progressed)
        # How many `/events` it answers AT ONCE. The server starts a thread per request and never says no, so
        # without a limit a burst of readers is a queue with no end: every answer later, memory growing, and a
        # reader that times out cannot tell "slow" from "gone". Past the limit the answer is 503 with
        # `Retry-After` — a refusal the merge reads as "did not answer", which makes the window incomplete and
        # holds automation's cursor rather than losing what this resource holds (М10B Lesson 25).
        self.events_slots = threading.BoundedSemaphore(EVENTS_INFLIGHT)
        # The requests this resource HOLDS for readers of its events (`GET /events/wait`, `longpoll.Watch`): answered
        # when a line of a kind the reader watches is appended to a current bucket here. Its own bound, apart from
        # the slots above — a held request does nothing for thirty seconds, and must neither take a query's slot nor
        # be without a ceiling of its own. It costs nothing until somebody waits: no thread, no stat.
        self.watch = Watch(self.volumes.values(), bucket_seconds, wall)
        # The cluster's objects (`/v1/objects`): the address this process said in `platform/doors/<server>`, the doors
        # as last read, the peers left alone for a while after they did not answer, and the blobs a peer did not take.
        self._door_said = ""
        self._door_refused = False                 # said once in the log while the store refuses the row
        self._door_since = ""                      # `since` as the row says it, kept through the refreshes of `at`
        self._alive_at: float | None = None        # by `wall`, when `at` was last written (`say_door`)
        self._doors: tuple[float, dict] | None = None
        self._peer_rest: dict[str, float] = {}     # server -> by `clock`, until when it is not asked (`_fan_out`)
        self._peers_silent: set[str] = set()       # the peers that did not answer when last asked: logged once a spell
        self.blobs_failed = 0
        self.blob_peers_failed: list[str] = []
        for path in self.volumes.values():
            os.makedirs(path, exist_ok=True)

    # -- the volumes ---------------------------------------------------------------------
    # Which volume holds a unit is not written down anywhere: the unit's directory IS the answer, exactly
    # as `subsystems_under` already derives what is on this resource at all. A map would be a second truth
    # about the disks, and it would drift.
    def volume_of(self, sub: str, unit: str) -> str | None:
        for name, path in self.volumes.items():
            if os.path.isdir(os.path.join(path, sub, str(unit))):
                return name
        return None

    # Where a unit that is not here yet should go: the emptiest volume. Called when something writes for
    # the first time; after that `volume_of` answers, and a unit does not move between disks — that would
    # be copying terabytes as a side effect of a pass.
    def place_volume(self) -> str:
        best, most = next(iter(self.volumes)), -1
        for name, path in self.volumes.items():
            _, free = self.space_probe(path)
            if free > most:
                best, most = name, free
        return best

    # The absolute path of something named relative to a volume: the volume that has it, else the emptiest.
    def path_of(self, rel: str, volume: str | None = None) -> str:
        if volume is not None:
            return os.path.join(self.volumes[volume], rel)
        for path in self.volumes.values():
            full = os.path.join(path, rel)
            if os.path.exists(full):
                return full
        return os.path.join(self.volumes[self.place_volume()], rel)

    # -- what is here -------------------------------------------------------------------
    # `subsystems_under(root)` — what is here, from the directories.
    def units(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for path in self.volumes.values():
            for sub, units in subsystems_under(path).items():
                out.setdefault(sub, []).extend(u for u in units if u not in out.get(sub, []))
        return {k: sorted(v) for k, v in out.items()}

    # Every bucket of every unit whose `end <= now`. Only these are mirrored.
    #
    # By NAME, and a mark of progress per bucket (the review's fifth pass, Т-M13's remainder). The mirror needs a
    # bucket's path and its end, both in the name; `buckets_under` opened every file to count its lines, so the walk
    # read a year of archive every pass — and marked progress once per UNIT: 5000 buckets of 300 lines took 3.2 s
    # against a pulse limit of 2, and the resource looked silent while it walked. `events` is 0 here: nobody reads it.
    def closed_buckets(self) -> list[Bucket]:
        out = []
        for sub, units in self.units().items():
            for unit in units:
                self._progressed()
                for path in self.volumes.values():
                    out += [b for b in bucket_names_under(path, sub, unit, self.bucket_seconds, self._progressed)
                            if b.end <= self.wall()]
        return out

    # Total bytes under `root` — every file, not only the ones some subsystem accounts for. A walk, and
    # therefore NOT something to do on a timer: a year of event buckets for a few hundred units is a great many
    # files, and walking them touches every inode in the tree. Measured
    # once per policy pass (`pass_`), published from the cache with the time it was taken (`usage_at`).
    # What decides anything is `space()` — one `statvfs`, cheap enough for every heartbeat.
    #
    # A file that goes between the listing and the `stat` — a `.tmp` renamed into place, a bucket the retention
    # removed — is not there to count, and is not the end of the walk (the review's third pass): one vanished file
    # used to take the whole policy pass with it.
    #
    # A mark of progress per FILE (the review's sixth pass): it was one per directory, and every bucket of an epoch
    # is in one directory — a year of one camera is fifty thousand `stat`s between two marks, and on a cold disk the
    # pulse called a walk that moved the whole time "stuck".
    def usage(self, volume: str | None = None) -> int:
        roots = [self.volumes[volume]] if volume is not None else list(self.volumes.values())
        total = 0
        for root in roots:
            for d, _, files in os.walk(root):
                self._progressed()
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(d, f))
                    except FileNotFoundError:
                        continue
                    finally:
                        self._progressed()
        return total

    # The pass is getting somewhere: what the pulse measures its limit by (`pass_`). Cheap — a clock read.
    def _progressed(self) -> None:
        self._progress_at = self.clock()

    # The cached number, measured now if it never was: the first heartbeat of a process pays for it once.
    def usage_cached(self) -> int:
        if self.last_usage is None:
            self.last_usage, self.usage_at = self.usage(), self.wall()
        return self.last_usage

    # The same, per volume, and only for the volumes that have a quota — the rest never ask. Cached beside
    # the whole-tree number and refreshed by `pass_`: a walk per volume per watermark check would be the
    # one place in this file where measuring costs more than what it decides.
    def usage_of(self, volume: str) -> int:
        cached = self._volume_usage.get(volume)
        if cached is None:
            cached = self.usage(volume)
            self._volume_usage[volume] = cached
        return cached

    # (total, free) of the disk, and how full it is. `free` is what a peer reads before sending anything
    # here: a copy onto a disk that is itself tight only moves the problem.
    def space(self, volume: str | None = None) -> dict:
        """One volume's disk, or every volume summed when none is named. The sum
        is what a fleet view wants; what DECIDES anything is a single volume —
        a box 50% full across two disks with one of them at 98% is full."""
        names = [volume] if volume is not None else list(self.volumes)
        total = free = 0
        for n in names:
            t, f = self.space_probe(self.volumes[n])
            q = self.quotas.get(n, 0)
            if q:
                left = max(0, q - self.usage_of(n))           # what the CEILING leaves
                t = min(t, q) if t else q                     # `t == 0`: no disk behind this path (a bucket)
                f = min(f, left) if t else left               # …and then the quota is the only truth there is
            total += t; free += f
        return {"total": total, "free": free, "used": total - free,
                "full": (total - free) / total if total else 0.0}

    # Every volume by name, which is what the console shows and what `relieve` walks.
    def spaces(self) -> dict[str, dict]:
        return {name: self.space(name) for name in self.volumes}

    # Writes `{server, ts, url, usage, usage_at, space, units, mirrors: {server: n copies}}` to
    # `platform/resources/<server>/heartbeat` and returns it. `units` is how the index discovers subsystems;
    # `mirrors` is how `restore` and the index find who holds copies.
    #
    # EVERY LOOK AT A VOLUME WITH A DEADLINE (the review's thirteenth pass, blocker 5; the product's cross-check (a)): the
    # `statfs`, the directory listings and the presence look ran bare on the heartbeat's thread, and one volume that
    # stopped answering — an NFS server gone, a dying disk — held the heartbeat for good: the resource silent in 45 s,
    # and the live workers' cameras carried off a server whose processes all ran. Each volume is looked at in a probe of
    # its own (`_probe`, `PROBE_DEADLINE`); one that does not answer in time is said (`volumes_stuck`, with how long) and
    # its last numbers stand; the presence look that does not answer is `presence_error` — "cannot tell", never "gone".
    def heartbeat(self) -> dict:
        looks = {name: self._volume_look(name) for name in self.volumes}
        usage = self._probe("usage", self.usage_cached, self.last_usage or 0)
        hb = {"server": self.server, "ts": self.wall(), "url": self.url,
              "schema": SCHEMA, "build": BUILD,                      # what this build understands, and what it is
              "usage": usage, "usage_at": self.usage_at,
              "space": _summed([lk["space"] for lk in looks.values()]),
              "volumes": {name: lk["space"] for name, lk in looks.items()},
              "units": _merged([lk["units"] for lk in looks.values()]),
              # The workers placed on this server and those whose process runs, by subsystem (`workers_here`): what
              # tells a hung worker from a dead one (`Controller.slot_fate`; the owner's decision on the review's eleventh
              # pass). The files' own clock, not `wall`: what is compared is a file's age
              # …and what it could not read of them, said and not taken for "not here" (`presence_here`; the twelfth pass)
              **self._presence(),
              **({"volumes_stuck": stuck} if (stuck := self.stuck()) else {}),
              "short": sum(self.short.values()),                     # bytes the last pass was asked to free and could not
              "waits": self.watch.counts(),                          # the requests it holds (`/events/wait`): now, and refused
              # The watermark's row, when it does not parse: what the pass acts on instead (`relieve`; the review's
              # seventh pass) — and the rows of any table this process could not read, by table (`rows.Table`): the
              # keeps a hook reads, the knobs. Absent when there are none.
              **({"space_garbled": self.space_garbled} if self.space_garbled else {}),
              **({"rows_garbled": garbled} if (garbled := {name: sum(c.values()) for name, c in garbled_by_table().items()
                                                           if sum(c.values())}) else {}),
              # …and while it has not run through once with somebody to ask (`done`; the review's ninth pass)
              **({"restore": self.restore_said()} if self.restore_left or self.restore_failed or not self._restore_ok else {}),
              # The units whose days the last `retain` could not read, by name: kept, not swept (sibling A of the ninth pass)
              **({"retention_garbled": self.retention_garbled} if self.retention_garbled else {}),
              # …and the buckets past their days it could not remove, since start (`_removed`; the thirteenth pass)
              **({"retain_failed": self.retain_failed} if self.retain_failed else {}),
              **({"mirror": {"failed": self.mirror_failed, "too_big": self.mirror_too_big,
                             "peers_failed": self.mirror_peers_failed}}
                 if self.mirror_failed or self.mirror_too_big else {}),
              # …and the blobs' copies the same way (`mirror_blobs`): what peers did not take, since start
              **({"blobs": {"failed": self.blobs_failed, "peers_failed": self.blob_peers_failed}}
                 if self.blobs_failed else {}),
              "mirrors": _counted([lk["mirrors"] for lk in looks.values()])}
        self.objects.put(f"{RESOURCES}/{self.server}/heartbeat", json.dumps(hb).encode())
        self._last_heartbeat, self._beat_at = hb, self.clock()
        self.say_door()
        return hb

    # One volume as the heartbeat says it — its disk, what is on it, the copies it holds of other servers — looked at in a
    # probe of its own, with a deadline: one that does not answer is that volume's, and its last look stands.
    def _volume_look(self, name: str) -> dict:
        path = self.volumes[name]

        def look() -> dict:
            return {"space": self.space(name), "units": subsystems_under(path),
                    "mirrors": {s: mirrored_count(path, s) for s in mirrored_servers(path)}}
        return self._probe(f"volume:{name}", look, {"space": {"total": 0, "free": 0, "used": 0, "full": 0.0},
                                                    "units": {}, "mirrors": {}})

    # Who is registered here and whose process runs (`presence_here`), with a deadline: a tree that does not answer is
    # "cannot read the registrations" — which nobody takes for a worker's end (`Controller.presence_doubt`).
    def _presence(self) -> dict:
        said = self._probe("presence", lambda: presence_here(self.root), None)
        if said is None or "presence" in self._stuck:
            return {"presence_error": f"{self.root} did not answer in {self.PROBE_DEADLINE:g} s"}
        return said

    # A look at a disk, with a deadline (blocker 5's half (a)). `fn` runs on a thread of its own and is waited for
    # `PROBE_DEADLINE`; in time, its answer is the answer and is kept. Not in time, the last answer kept (or `default`)
    # stands, and the probe is said stuck since it began (`stuck`): ONE thread per probe stays in it — a probe still
    # running is waited on again, never started twice, so a volume that hangs for a day costs one thread, not one per
    # heartbeat. What `fn` raises is raised here, as it was without the probe.
    PROBE_DEADLINE = 5.0

    def _probe(self, name: str, fn, default):
        with self._probe_lock:
            run = self._probes.get(name)                   # one still running is waited on again, not doubled
            if run is None:
                box: dict = {}

                def go(box=box):
                    try:
                        box["v"] = fn()
                    except BaseException as e:                 # noqa: BLE001 — handed to the caller below
                        box["e"] = e
                run = (threading.Thread(target=go, daemon=True, name=f"{self.server}-{name}"), box, self.clock())
                self._probes[name] = run
                run[0].start()
        thread, box, began = run
        thread.join(self.PROBE_DEADLINE)
        if box:
            with self._probe_lock:
                if self._probes.get(name) is run:
                    del self._probes[name]
                if name in self._stuck:
                    log.warning("%s: %s answers again", self.server, name)
                self._stuck.pop(name, None)
            if "e" in box:
                raise box["e"]
            self._looked[name] = box["v"]
            return box["v"]
        with self._probe_lock:
            if name not in self._stuck:
                log.error("%s: %s did not answer in %g s: its last look stands, and the heartbeat goes on without it — "
                          "the disk behind it does not answer", self.server, name, self.PROBE_DEADLINE)
            self._stuck[name] = began
        return self._looked.get(name, default)

    # The probes that have not answered: `{name: seconds}` since each began.
    def stuck(self) -> dict[str, float]:
        now = self.clock()
        return {n: round(now - t, 1) for n, t in sorted(self._stuck.items())}

    # -- the cluster's objects ------------------------------------------------------------
    # `platform/doors/<server> {url, since, at}` — where this resource answers, for the other resources that read every
    # server's objects (`doors`). Said by the first heartbeat of the process, and again whenever the address differs
    # from what the row says: one read at start. `since` is when this address was first said. A store that refuses the
    # row (a grant missing) or does not answer is not the heartbeat's trouble: said once in the log, asked again by the
    # next heartbeat; meanwhile the other servers do not find this one's objects.
    #
    # …AND `at`, AGAIN EVERY `ALIVE_EVERY` (the review's twelfth pass, blocker 5 and major 9): that this resource is
    # there, said in the store — which outlives a server, and which every controller reaches when it cannot reach this
    # server's door. A controller that cannot read this resource's heartbeat fresh asks it (`Controller.resource_state`):
    # fresh, the server is there and only its door is not — nothing moves; stale, the server is silent — and a controller
    # started after it went sees that too. One write per `ALIVE_EVERY` per server; the pulse of a long pass says it too.
    def say_door(self) -> bool:
        if not self.url:
            return False
        now = self.wall()                                    # the row's own clock: what a reader compares `at` with
        if self._door_said == self.url and self._alive_at is not None and 0 <= now - self._alive_at < ALIVE_EVERY:
            return False
        key = f"{DOORS}/{self.server}"
        try:
            if self._door_said != self.url:
                items, _ = self.vars.get(key)
                same = bool(items) and items.get("url") == self.url
                self._door_since = str(items.get("since")) if same and items.get("since") else str(self.wall())
            self.vars.put(key, {"url": self.url, "since": self._door_since, "at": str(now)})
        except Exception as e:                               # noqa: BLE001 — the door unsaid is not the heartbeat unsent
            if not self._door_refused:
                self._door_refused = True
                log.error("%s: could not say where this resource answers (%s: %s): the other servers do not find its "
                          "objects until it is said — asked again with every heartbeat", self.server, key, e)
            return False
        self._door_said, self._door_refused, self._alive_at = self.url, False, now
        return True

    # What the pulse of a long step says beside the heartbeat it sends again (`_pulsing`).
    def say_alive(self) -> None:
        self.say_door()

    # THE BEAT: that this resource is here, and who runs on it, on a thread of its own (the review's thirteenth pass,
    # blocker 5). The heartbeat, the door's `at` and the presence look were said from the thread of the pass, so a pass
    # that hung took them with it: at `PULSE_LIMIT` the pulse stopped, the resource was "silent", and a hung worker
    # holding its lock was moved — a second writer — at 250 s, long before `HUNG_MOVE_AFTER` (`p8c_pulse_stops`). Now
    # the beat runs beside the loop whatever the loop does: the last full heartbeat again, the presence looked at anew
    # (with its deadline), the time moved on, and the door's `at`. A pass that has not moved for `PULSE_LIMIT` ×
    # `lost_after` is said (`pass_stuck`, on `/metrics`) and logged once — the resource is there, its pass is not, and
    # that is a fault of the server to look at, not a silence that moves cameras.
    def beat(self) -> bool:
        last = getattr(self, "_last_heartbeat", None)
        if last is None:
            return False                                      # nothing said yet: the first heartbeat is the loop's
        beat = {k: v for k, v in last.items() if k not in PRESENCE_FIELDS + ("pass_seconds", "pass_stuck", "volumes_stuck")}
        beat.update(self._presence(), ts=self.wall())
        if self.stuck():
            beat["volumes_stuck"] = self.stuck()
        started = self._pass_started
        if started is not None:
            now = self.clock()
            still = now - self._progress_at
            beat["pass_seconds"] = round(now - started, 1)
            if still > self.PULSE_LIMIT * self.lost_after:
                beat["pass_stuck"] = round(still, 1)
                if not self._stuck_said:
                    self._stuck_said = True
                    log.error("%s: the pass has made no progress for %.0f s — longer than %d × lost_after: the resource "
                              "beats on (its workers are judged by what runs, not by its pass), and says pass_stuck",
                              self.server, still, self.PULSE_LIMIT)
        self.objects.put(f"{RESOURCES}/{self.server}/heartbeat", json.dumps(beat).encode())
        self._beat_at = self.clock()
        self.say_alive()
        return True

    # The beat's thread: `beat` every `PULSE_SECONDS` — unless the loop's own heartbeat went out meanwhile — until `stop`
    # is set. A beat that fails is one beat (the review's third pass), and the thread goes on. Started once a process
    # (`host.run_resource`, on a box and on a cluster); a test drives `beat` itself.
    def start_beat(self, stop: threading.Event | None = None) -> threading.Thread:
        stop = stop or threading.Event()

        def run():
            while not stop.wait(self.PULSE_SECONDS):
                if self._beat_at is not None and self.clock() - self._beat_at < self.PULSE_SECONDS * 0.9:
                    continue                                  # the loop's heartbeat just went: nothing to add
                try:
                    self.beat()
                except Exception:                             # noqa: BLE001 — one beat lost, not the beat
                    log.warning("%s: a beat did not go out", self.server, exc_info=True)
        self._beating = threading.Thread(target=run, daemon=True, name=f"{self.server}-beat")
        self._beating.start()
        return self._beating

    # `{server: url}` of every OTHER resource that said its door, read from the store at most every `DOORS_FRESH`
    # seconds. A row that is not a door (`url` not an http address, a server that is not a name) is left out and
    # counted once (`DOOR_ROWS`): that server's objects are missing from the cluster's answers, the others' are not.
    def doors(self) -> dict[str, str]:
        now = self.clock()
        if self._doors is not None and now - self._doors[0] < DOORS_FRESH:
            return self._doors[1]
        out = {}
        for path in self.vars.list(DOORS + "/"):
            server = path[len(DOORS) + 1:]
            if server == self.server:
                continue
            items, _ = self.vars.get(path)

            def url(items=items, server=server) -> str:
                u = (items or {}).get("url")
                if not safe_segment(server) or not isinstance(u, str) or not u.startswith(("http://", "https://")):
                    raise ValueError(f"not a door: {items!r}")
                return u.rstrip("/")
            u = DOOR_ROWS.read(path, url)
            if u:
                out[server] = u
        self._doors = (now, out)
        return out

    # `call(url)` on every other door AT ONCE, each within `OBJECTS_TIMEOUT`: `({server: answer}, [missing])`. A peer
    # that does not answer — down, refused, a body that does not parse — is MISSING, named to the caller, and not asked
    # again for `PEER_REST` seconds (named meanwhile): a server gone costs one timeout per spell, not one per read. Its
    # silence is logged when it starts and when it ends, not on every read.
    def _fan_out(self, call, servers: dict[str, str] | None = None) -> tuple[dict, list[str]]:
        doors = self.doors() if servers is None else servers
        now, results, missing = self.clock(), {}, []
        asked = {s: u for s, u in doors.items() if self._peer_rest.get(s, 0.0) <= now}
        missing += [s for s in doors if s not in asked]

        def one(s, u):
            try:
                results[s] = (True, call(u))
            except Exception as e:                           # noqa: BLE001 — that peer's trouble, not the answer's
                results[s] = (False, e)
        threads = [threading.Thread(target=one, args=(s, u), daemon=True) for s, u in asked.items()]
        for t in threads:
            t.start()
        deadline = time.monotonic() + 2 * OBJECTS_TIMEOUT + 1.0
        for t in threads:
            t.join(max(0.0, deadline - time.monotonic()))
        out = {}
        for s in asked:
            ok, value = results.get(s, (False, TimeoutError(f"no answer in {2 * OBJECTS_TIMEOUT + 1.0:.0f} s")))
            if ok:
                out[s] = value
                if s in self._peers_silent:
                    self._peers_silent.discard(s)
                    log.warning("%s: %s answers for its objects again", self.server, s)
                continue
            missing.append(s)
            self._peer_rest[s] = self.clock() + PEER_REST
            if s not in self._peers_silent:
                self._peers_silent.add(s)
                log.warning("%s: %s did not answer for its objects (%s): left out of the cluster's answers, asked again "
                            "in %.0f s", self.server, s, value, PEER_REST)
        return out, sorted(missing)

    # What this server holds under `prefix` — `{key: {written, server, size}}` — or, `scope=cluster`, every server's:
    # the union, and for a key on several servers the copy written last (`written`; a blob's copies are one object).
    # Returns `(objects, missing)`: the doors that did not answer, named. A peer's entry that is not one (a `written`
    # that is not a finite number) is left out and counted once (`PEER_OBJECTS`).
    def objects_listing(self, prefix: str, scope: str = "local") -> tuple[dict, list[str]]:
        local = local_store(self.objects)
        out = {}
        for key in local.list(prefix):
            st = _stat(local, key)
            if st is not None:
                out[key] = {"written": st[0], "server": self.server, "size": st[1]}
        if scope != "cluster":
            return out, []
        answers, missing = self._fan_out(lambda u: self.peers.objects(u, prefix, OBJECTS_TIMEOUT))
        for server, objs in sorted(answers.items()):
            for key, e in objs.items():
                def entry(e=e, server=server) -> dict:
                    return {"written": finite(e["written"]), "server": server, "size": int(finite(e.get("size", 0)))}
                got = PEER_OBJECTS.read(f"platform/objects/{server}#{key}", entry)
                if got is None or not isinstance(key, str) or not key.startswith(prefix):
                    continue
                if key not in out or got["written"] > out[key]["written"]:
                    out[key] = got
        return out, missing

    # One object: `((bytes, written, server) | None, missing)`. Here, `scope=local`; `scope=cluster` — the freshest copy
    # among every server's, by `written`. A BLOB is one object wherever it is, so it is taken from the first copy that
    # hashes to its name — this server's first, then each peer's in turn — and a copy that does not is refused,
    # logged, and the next one asked (`blobs.verify`; the reader checks again).
    def object_read(self, key: str, scope: str = "local") -> tuple[tuple[bytes, float, str] | None, list[str]]:
        from .blobs import BlobMismatch, verify
        # A key that names a directory, or an in-flight `put`'s temporary file, is no object (the review's twelfth pass,
        # minor): the directory's read raised past the door and dropped the connection, and `<key>.….tmp` was served as an
        # object though no listing names it (`FsObjectStore.list` passes such files by). Both: 404, here and anywhere.
        if key.endswith(".tmp"):
            return None, []
        local = local_store(self.objects)
        mine, unread = None, ""
        try:
            st = _stat(local, key)
            data = local.get(key) if st is not None else None
        except (IsADirectoryError, NotADirectoryError):
            data = None
        except OSError as e:                                 # there, and not readable: not "nobody has it" (the 13th pass)
            log.error("%s: its copy of %s cannot be read: %s", self.server, key, e)
            data, unread = None, _why(e)
        if data is not None:
            mine = (data, st[0], self.server)
        if scope != "cluster":
            if unread:
                raise ObjectUnreadable(f"this server's copy of {key} cannot be read ({unread})")
            return mine, []
        blob = is_blob_key(key)
        digest_ = key.rsplit("/", 1)[1] if blob else ""
        if blob and mine is not None:
            try:
                verify(digest_, mine[0])
                return mine, []
            except BlobMismatch as e:
                log.error("%s: this server's copy of %s is not the blob (%s): asked of the others", self.server, key, e)
                mine = None
        if blob:                                             # one copy is enough: the peers in turn, not all at once
            missing = []
            for server, url in sorted(self.doors().items()):
                got, gone = self._fan_out(lambda u: self.peers.object(u, key, OBJECTS_TIMEOUT), {server: url})
                missing += gone
                copy = got.get(server)
                if copy is None:
                    continue
                try:
                    verify(digest_, copy[0])
                except BlobMismatch as e:
                    log.error("%s: %s's copy of %s is not the blob (%s): refused, asked of the next", self.server,
                              server, key, e)
                    continue
                return (copy[0], copy[1], server), missing
            if unread:
                raise ObjectUnreadable(f"this server's copy of {key} cannot be read ({unread}), and no other server gave one")
            return None, missing
        got, missing = self._fan_out(lambda u: self.peers.object(u, key, OBJECTS_TIMEOUT))
        best = mine
        for server, copy in sorted(got.items()):
            if copy is not None and (best is None or copy[1] > best[1]):
                best = (copy[0], copy[1], server)
        if best is None and unread:
            raise ObjectUnreadable(f"this server's copy of {key} cannot be read ({unread}), and no other server gave one")
        return best, missing

    # A blob let go: here, and `scope=cluster` on every other server that answers (the sweep, `SpecController.sweep_blobs`
    # through `ClusterObjectStore.delete`). `({server: had it}, missing)` — a server that did not answer keeps its copy,
    # and the next sweep finds it again in the cluster's listing: an orphan, swept then.
    def object_delete(self, key: str, scope: str = "local") -> tuple[dict[str, bool], list[str]]:
        if not is_blob_key(key):
            raise ValueError(f"{key}: only a blob is deleted through this door")
        deleted = {self.server: bool(local_store(self.objects).delete(key))}
        if scope != "cluster":
            return deleted, []
        got, missing = self._fan_out(lambda u: self.peers.delete_object(u, key, OBJECTS_TIMEOUT))
        deleted.update({s: bool(v) for s, v in got.items()})
        return deleted, missing

    # A peer's copy of a blob, from a request's body: `n` bytes into a file beside the object, HASHED AS THEY COME, and
    # kept only if they hash to the key's digest — a copy that does not is refused and leaves nothing (`BlobMismatch`):
    # a peer's disk that rotted, or a door that cut the body, does not become this server's blob. A body that ends short
    # is an `EOFError`; a late one raises what the door's deadline raises.
    def take_blob(self, key: str, rfile, n: int) -> None:
        from .blobs import BlobMismatch
        from .events import durable_dir, durably, new_temp
        if not is_blob_key(key):
            raise ValueError(f"{key}: only a blob is put here")
        local = local_store(self.objects)
        p = getattr(local, "_p", None)
        if p is None:
            raise ValueError("this server's objects are not files: nothing to put a copy into")
        dest = p(key)

        def kept(step, *a):                                  # this disk's own trouble: said as such (the 13th pass)
            try:
                return step(*a)
            except OSError as e:
                log.error("%s: a copy of %s could not be kept: %s", self.server, key, e)
                raise ObjectUnkept(f"this server could not keep the copy of {key} ({_why(e)})") from None
        kept(os.makedirs, os.path.dirname(dest), 0o777, True)
        fd, tmp = kept(new_temp, os.path.dirname(dest), os.path.basename(dest) + ".")   # the store's group reads it (`new_temp`)
        try:
            h, left = hashlib.sha256(), n
            with os.fdopen(fd, "wb") as f:
                while left > 0:
                    part = rfile.read(min(left, PIECE))
                    if not part:
                        raise EOFError(f"{key}: the body ended {left} bytes short of {n}")
                    h.update(part); kept(f.write, part); left -= len(part)
                actual = f"sha256-{h.hexdigest()}"
                if actual != key.rsplit("/", 1)[1]:
                    raise BlobMismatch(f"{key}: the bytes sent hash to {actual} — not stored")
                kept(f.flush); kept(durably, f)
            kept(os.replace, tmp, dest)
            kept(durable_dir, os.path.dirname(dest))
        finally:
            with suppress(FileNotFoundError):
                os.remove(tmp)

    # THE BLOBS GO TO THE PEERS THE BUCKETS GO TO (the owner's decision of 3 October). A blob is the one object that
    # must not be lost — a mask, a model: the row names its digest, and nothing writes it again — while every other
    # object is written again within a pass. So each blob this server holds is copied to the next `copies` live
    # resources on the ring the events mirror uses (`peers_of`, `platform/mirror {copies}`), each peer asked first what
    # it holds. NOT behind the knob's `enabled`: the knob is about buckets, and a blob on one disk is a unit that does
    # not start when that disk goes. A store that is not files on this server (Variables, S3, a test's shared store)
    # has one copy for everybody — nothing to mirror. The same rules as `mirror`: a peer that does not list is left
    # for this pass, `PEER_FAILS` refusals in a row too; what was not copied goes on a later pass — the peer's listing
    # still lacks it. Returns `{mirrored, peers[, peers_failed]}`.
    def mirror_blobs(self) -> dict:
        local = local_store(self.objects)
        if not callable(getattr(local, "stat", None)):
            return {"mirrored": 0, "peers": []}
        blobs = [k for k in local.list("") if is_blob_key(k)]
        put_blob = getattr(self.peers, "put_blob", None)
        if not blobs or put_blob is None:
            return {"mirrored": 0, "peers": []}
        live = {s: hb for s, hb in self.live_resources().items() if hb.get("url")}
        peers = peers_of(self.server, list(live), mirror_settings(self.vars)["copies"])
        n, failed = 0, []
        for peer in peers:
            url = live[peer]["url"]
            try:
                have = set()
                for prefix in sorted({k.rsplit("/", 1)[0] + "/" for k in blobs}):
                    have |= set(self.peers.objects(url, prefix))
            except Exception as e:                           # noqa: BLE001
                self.blobs_failed += 1
                failed.append(peer)
                log.warning("%s: %s did not say which blobs it holds (%s): none copied to it this pass", self.server, peer, e)
                continue
            self._progressed()
            fails = 0
            for key in blobs:
                if key in have:
                    continue
                if fails >= PEER_FAILS:
                    break
                data = local.get(key)
                if data is None:
                    continue                                 # swept between the walk and here
                try:
                    put_blob(url, key, data)
                except Exception as e:                       # noqa: BLE001
                    fails += 1
                    self.blobs_failed += 1
                    log.warning("%s: %s did not take %s (%s)", self.server, peer, key, e)
                    if fails == PEER_FAILS:
                        failed.append(peer)
                    continue
                fails = 0
                n += 1
                self._progressed()
        self.blob_peers_failed = failed
        return {"mirrored": n, "peers": peers, **({"peers_failed": failed} if failed else {})}

    # `resources_seen` filtered to heartbeats that changed within `lost_after` of this resource's clock (`Eyes`).
    def live_resources(self) -> dict[str, dict]:
        return {s: hb for s, hb in resources_seen(self.objects).items() if self._live(s, hb)}

    def _live(self, server: str, hb: dict) -> bool:
        key = f"{RESOURCES}/{server}/heartbeat"
        return self.eyes.fresh(key, hb.get("ts"), self.lost_after, hb.get("ts"), "platform")

    # -- the policy pass ------------------------------------------------------------------
    # For each subsystem and unit, delete bucket files whose `end` is older than `retention_days` — files
    # only; a subsystem that indexes its buckets in a file of its own drops the lines in its own hook. The
    # resource's own index forgets each removed path. Returns the count. The test sets `other/retention {days: 1}`, advances three days and sees exactly the
    # `other` bucket go.
    def retain(self) -> int:
        """Each subsystem's buckets by its own days. Files only: a subsystem that
        indexes its buckets in a file of its own drops the lines in its own pass."""
        removed = []
        # What each unit keeps, decided before anything is swept, because the console's floor is read off
        # the others (`console_floor`).
        #
        # A ROW OF DAYS THAT DOES NOT PARSE IS THAT UNIT'S (the sixth pass, the follow-up). Every unit's days are read
        # in this one loop, and one row with a word for `days` raised out of it: nothing of anybody's was swept, every
        # pass. Not knowing a unit's days is not "zero days" — that unit is left alone this pass (`inf`), named in
        # `retention_garbled` and in the log, and the others are swept by theirs.
        days_of, garbled = {}, []
        for sub, units in self.units().items():
            for unit in units:
                days_of[(sub, unit)] = self._days(sub, unit, garbled)
                self._progressed()                                      # a row read per unit: each is a step
        floor = console_floor({k: d for k, d in days_of.items() if d != float("inf")})
        # What somebody said to keep (feedback BH). The resource does not know what a keep is: the specs say which rows
        # HOLD a unit for a stretch (`holds:`), and `self.kept` — called once a pass — reads them and returns
        # `(subsystem, unit, start, end) -> bool`. It matters most for `{days: 0}`, which is what a deleted unit's
        # retention becomes: without this, deleting the unit erased the very events somebody had marked. If it raises,
        # the pass fails and nothing is swept: not knowing what is kept is not "nothing is". It reads the store row by
        # row, so it is handed `progressed` (the review's sixth pass).
        kept = _call_hook(self.kept, progressed=self._progressed) if self.kept is not None else None
        self._progressed()
        self._retain_failed_pass = False
        swept: dict[tuple[str, str], tuple] = {}
        for sub, units in self.units().items():
            for unit in units:
                self._progressed()
                days = max(days_of[(sub, unit)], floor) if tree_owner(sub)[0] == CONSOLE else days_of[(sub, unit)]
                for path in self.volumes.values():
                    # by NAME: no file is opened to be swept; and a mark per bucket, not per unit (the review's fifth pass)
                    # …and a mark per REMOVAL (the sixth): the names are all marked while the list is built, and then
                    # the files go one after another — a year past its days is fifty thousand unlinks, and the pulse
                    # saw none of them.
                    for b in bucket_names_under(path, sub, unit, self.bucket_seconds, self._progressed):
                        if b.end < self.wall() - days * 86400:
                            if kept is not None and kept(sub, unit, b.start, b.end):
                                continue                                # somebody said to keep it: past its days, and here
                            if not self._removed(os.path.join(path, b.path)):
                                continue                                # that bucket's, said and counted: the rest go on
                            removed.append(b.path)
                            self._progressed()
                            n, a, z = swept.get((sub, unit), (0, b.start, b.end))
                            swept[(sub, unit)] = (n + 1, min(a, b.start), max(z, b.end))
        # What the pass removed, per unit, in the journal: whose buckets, how many, of what period, by what
        # days. It used to be one number in a log line (feedback BN).
        for (sub, unit), (n, a, z) in sorted(swept.items()):
            self.journal.say("events.removed", sub=sub, target=unit, buckets=n, since=a, until=z,
                             days=max(days_of[(sub, unit)], floor) if tree_owner(sub)[0] == CONSOLE else days_of[(sub, unit)])
            self._progressed()                                          # a line written to the medium per unit
        # THE COPIES AGE TOO (the review, "mirror copies are never deleted"). `.mirror/<server>/…` is in no
        # walk above — `units()` skips hidden directories, on purpose: a copy is not this server's data — so
        # with the mirror on it only ever grew. A copy is kept by the days of ITS unit, as the original is,
        # and a keep holds it the same way. `MIRROR_GRACE` later than the original, because the two servers
        # have two clocks: a copy swept a moment before its original would be sent again on the owner's next
        # pass, and swept again.
        for path in self.volumes.values():
            for server in mirrored_servers(path):
                base = os.path.join(path, MIRROR_DIR, server)
                for sub, units in subsystems_under(base).items():
                    for unit in units:
                        days = self._days(sub, unit, garbled)
                        days = max(days, floor) if tree_owner(sub)[0] == CONSOLE else days
                        self._progressed()
                        for b in bucket_names_under(base, sub, unit, self.bucket_seconds, self._progressed):
                            if b.end < self.wall() - days * 86400 - MIRROR_GRACE \
                                    and not (kept is not None and kept(sub, unit, b.start, b.end)):
                                if self._removed(os.path.join(base, b.path)):
                                    self.mirror_removed += 1
                                self._progressed()
        if removed and self.index is not None:
            self.index.forget(self.server, removed)                     # out of its cache with the file
        self.retention_garbled = sorted(set(garbled))
        if self._retain_failing and not self._retain_failed_pass:
            self._retain_failing = False
            log.warning("%s: every bucket past its days is removed again", self.server)
        return len(removed)

    # ONE BUCKET THIS RESOURCE CANNOT REMOVE IS THAT BUCKET'S (the review's thirteenth pass, major 13's other half). The
    # unlink ran bare: a directory a writer made 2755 under another group (no umask under Nomad), one EACCES, and the
    # `PermissionError` ended `retain` whole — no bucket of any unit swept after it, every pass, and the disk grew without
    # bound. A bucket that will not go is counted (`retain_failed`, in the heartbeat and on `/metrics`), logged once a
    # spell, and the walk goes on; one already gone is gone.
    def _removed(self, path: str) -> bool:
        try:
            os.remove(path)
        except FileNotFoundError:
            return True
        except OSError as e:
            self.retain_failed += 1
            if not self._retain_failing:
                self._retain_failing = True
                log.error("%s: a bucket past its days could not be removed (%s): it stays, the others are swept — "
                          "counted (retain_failed), said once until a pass removes everything it should",
                          self.server, e.strerror or e)
            self._retain_failed_pass = True
            return False
        return True

    # One unit's days, or `inf` — kept, not swept — when its row does not parse (`retain`).
    # Whatever a parse raises (`PARSE_ERRORS`: a row that is a JSON list has no `.get`), not only a word; a store that
    # does not answer is not the row's trouble and raises out of the pass. Counted and logged once until it parses again
    # (`RETENTION`; it was a warning every pass, and a count nowhere).
    def _days(self, sub: str, unit: str, garbled: list) -> float:
        key = f"{sub}/retention/{unit}"
        try:
            days = retention_days(self.vars, sub, unit)
        except PARSE_ERRORS as e:
            RETENTION.garbled(key, f"{e}; on {self.server}")
            garbled.append(f"{sub}/{unit}")
            return float("inf")
        RETENTION.parsed(key)
        return days

    # The knob. If disabled, `{enabled: False, mirrored: 0, peers: []}`. Otherwise, for each peer from
    # `peers_of`, ask what it already holds and `put` every closed bucket it lacks — any subsystem's,
    # exactly once each, by the server that owns it. Returns `{enabled, mirrored, peers}`. The test shows
    # two buckets mirrored the first pass and zero the second.
    #
    # ONE PEER, ONE BUCKET IS ITS OWN TROUBLE (the review's eighth pass, part 4). The whole mirror was one `try` (the
    # pass's part): a peer whose door refused its listing raised out of the loop and the next peer was given nothing; a
    # bucket bigger than `MIRROR_MAX` was 413 on every pass, and no bucket after it was copied to anybody, ever. Now a
    # peer that does not answer its listing is skipped for this pass; a bucket over `MIRROR_MAX` is not sent at all and
    # one refused 413 is not sent again — both counted (`too_big`); any other refusal of a bucket is counted and the next
    # bucket goes, and `PEER_FAILS` refusals in a row leave that peer for this pass (its door is down: a year of buckets
    # is not a year of timeouts). What was not copied is copied on a later pass — the peer's listing still lacks it: the
    # pass is the mirror's repeat. The counts and the peers are in the heartbeat (`mirror`) and on `/metrics`.
    def mirror(self) -> dict:
        """The knob. Every CLOSED bucket on this server — any subsystem — is
        copied to the next live resource(s) after it, exactly once each (the
        peer says what it already holds), by the server that owns it."""
        knob = mirror_settings(self.vars)
        if not knob["enabled"]:
            return {"enabled": False, "mirrored": 0, "peers": []}
        live = {s: hb for s, hb in self.live_resources().items() if hb.get("url")}   # a peer that says no address takes nothing
        peers = peers_of(self.server, list(live), knob["copies"])
        n, closed, failed = 0, None, []
        for peer in peers:
            url = live[peer]["url"]
            try:
                have = {b.path for b in self.peers.mirrored(url, self.server)}
            except Exception as e:                           # noqa: BLE001 — that peer's trouble, not the next one's
                self.mirror_failed += 1
                failed.append(peer)
                log.warning("%s: %s did not say what it holds (%s): nothing copied to it this pass", self.server, peer, e)
                continue
            self._progressed()
            if closed is None:
                closed = self.closed_buckets()               # the walk once a pass, not once per peer
            fails = 0
            for b in closed:
                if b.path in have or b.path in self._too_big:
                    continue
                if fails >= PEER_FAILS:
                    break                                    # its door is down: the rest on a later pass
                try:
                    with open(self.path_of(b.path), "rb") as f:
                        size = os.fstat(f.fileno()).st_size
                        if size > MIRROR_MAX:
                            raise _TooBig(f"{size} bytes, over the {MIRROR_MAX} a peer takes")
                        put_file = getattr(self.peers, "put_file", None)     # in pieces, never the bucket whole (the seventh pass)
                        if put_file is not None:
                            put_file(url, self.server, b.path, f, size)
                        else:
                            self.peers.put(url, self.server, b.path, f.read())
                except FileNotFoundError:
                    continue                                 # swept between the walk and here: nothing to copy
                except Exception as e:                       # noqa: BLE001
                    if isinstance(e, _TooBig) or getattr(e, "code", None) == 413:
                        self._too_big.add(b.path)
                        self.mirror_too_big += 1
                        log.error("%s: %s is too big to mirror (%s): it is copied nowhere — the buckets after it are",
                                  self.server, b.path, e)
                        continue
                    fails += 1
                    self.mirror_failed += 1
                    log.warning("%s: %s did not take %s (%s)", self.server, peer, b.path, e)
                    if fails == PEER_FAILS:
                        failed.append(peer)
                        log.warning("%s: %s refused %d buckets in a row: the rest go to it on a later pass",
                                    self.server, peer, PEER_FAILS)
                    continue
                fails = 0
                n += 1
                # Each copy the peer took is progress (the review's fourth pass): the FIRST mirroring of a server
                # sends a year of buckets, and without a mark per bucket a mirror that moved the whole time was
                # "stuck" to the pulse after four `lost_after` — the resource silent, its recordings moved.
                self._progressed()
        self.mirror_peers_failed = failed
        return {"enabled": True, "mirrored": n, "peers": peers, **({"peers_failed": failed} if failed else {})}

    # The reverse, run by the owner: for every live peer whose heartbeat lists me under `mirrors`, pull each
    # of my buckets it holds that I do not have (tmp + rename). Returns `{pulled, …}`. In the test,
    # `srv-a` with a wiped disk pulls 2 buckets; the open bucket that was never mirrored is the RPO.
    #
    # UNDER THE SAME PULSE AS THE PASS (the review's seventh pass, M4). It runs before the loop's first heartbeat after
    # the first, on the same thread: a disk replaced and two thousand buckets pulled at 50 ms each were 100 s without a
    # heartbeat — the resource silent to the index (the window incomplete, automation's cursor held) and to the
    # console, while its door answered. It beats as `pass_` does (`_pulsing`), with a mark per bucket pulled — and per
    # listing and per bucket already here — so a pull that moves keeps the pulse, and one that hangs on a peer stops it.
    #
    # ONE PEER, ONE BUCKET IS ITS OWN TROUBLE, AND WHAT IS LEFT IS ASKED FOR AGAIN (the review's eighth pass, part 4). It
    # ran once, at the start, in one `try`: a peer whose door refused gave back 0 buckets of 20, a cut on the fourth gave
    # back 3 — and nothing asked again, while the copies aged on the peers and were swept there. Now a peer that does not
    # list is skipped and the next one asked; a bucket that does not come is counted and the next one pulled, and
    # `PEER_FAILS` in a row leave that peer for this try; a path a peer lists that is not a bucket's (`..`, not
    # `.events.jsonl`) is never written — counted, skipped. What is known to be with peers and not back (`left`), and a
    # peer that did not list at all, make the restore due again (`restore_due`): after `RESTORE_RETRY` seconds, doubling
    # to `RESTORE_RETRY_MAX`, from the resource's loop, until nothing is left. Its state is in the heartbeat (`restore`)
    # and on `/metrics`. Returns `left`, `failed` and `peers_failed` beside `pulled` when there are any.
    #
    # NOT DONE UNTIL IT RAN THROUGH ONCE WITH SOMEBODY TO ASK (the review's ninth pass, major). Due again was only "left
    # something with a peer it reached": a restore that raised whole (the store away at the start, with a new disk) or
    # found no live peer (the server up before its peers after a power cut) left nothing known, and was never asked
    # again — 0 of 20 buckets back in 20 minutes, `restore_left` 0, while the copies aged on the peers. Now the restore is
    # due (`restore_due`, with its doubling pause) until one try ran through without an error and either saw a live peer
    # or found no other resource that ever said a heartbeat (one server alone: nobody can hold its copies); a try that
    # raises is due again after its pause. And a peer that comes up LATER with copies of this server it has not given —
    # down at the restore, while another peer was up — is asked when it is seen (`restore_due` looks every
    # `RESTORE_RETRY_MAX`); a peer that gave everything (`_restored_from`) is not asked again: what it holds of this
    # server since came from this server.
    def restore(self) -> dict:
        """The reverse, run by the owner: pull my buckets from whoever holds copies."""
        with self._pulsing():
            try:
                return self._restore()
            except Exception:
                wait = self._restore_later()
                log.warning("%s: restore did not run through: tried again in %.0f s", self.server, wait)
                raise

    def _restore(self) -> dict:
        pulled, left, failed, peers_failed = 0, 0, 0, []
        seen = resources_seen(self.objects)
        live = {s: hb for s, hb in seen.items() if s != self.server and self._live(s, hb)}
        for peer, hb in live.items():
            if peer in self._restored_from or not self._holds_mine(peer, hb):
                continue
            try:
                listed = self.peers.mirrored(hb["url"], self.server)
            except Exception as e:                           # noqa: BLE001 — that peer's trouble, not the next one's
                failed += 1
                peers_failed.append(peer)
                log.warning("%s: %s did not list the copies it holds of this server (%s): asked again later",
                            self.server, peer, e)
                continue
            self._progressed()
            # A line of the listing that was not read, and a path that is not a bucket's, are buckets the peer has and
            # did not give: counted in `left` (the review's tenth pass, minor) — the peer is not "gave everything" and is
            # asked again, and `restore_left` says what is still with it. A peer of another build is then asked every
            # `RESTORE_RETRY_MAX`, and the number that does not fall is what says so.
            fails, left_before = 0, left
            left += int(getattr(listed, "skipped", 0) or 0)
            for path in sorted(str(b.path) for b in listed):
                self._progressed()
                if not _bucket_path(path):
                    PEER_LINES.garbled(f"platform/restore/{peer}#{path}", "not a bucket's path")
                    left += 1
                    continue                                 # never written: it could name a place outside the tree
                dest = self.path_of(path)              # back onto the volume that held it, or the emptiest
                if os.path.exists(dest):
                    continue
                if fails >= PEER_FAILS:
                    left += 1
                    continue                                 # this peer is left for this try: counted, asked again
                try:
                    self._pull(hb["url"], path, dest)
                except Exception as e:                       # noqa: BLE001
                    fails += 1
                    failed += 1
                    left += 1
                    log.warning("%s: %s did not give back %s (%s): asked again later", self.server, peer, path, e)
                    if fails == PEER_FAILS:
                        peers_failed.append(peer)
                    continue
                fails = 0
                pulled += 1
                self._progressed()
            if left == left_before:
                self._restored_from.add(peer)                # all it listed is here: not asked again
        self.restore_failed += failed
        self.restore_left, self.restore_peers_failed = left, peers_failed
        if not left and not peers_failed and (live or not any(s != self.server for s in seen)):
            self._restore_ok = True
        if left or peers_failed:
            wait = self._restore_later()
            log.warning("%s: restore left %d buckets with peers%s: tried again in %.0f s", self.server, left,
                        f" ({', '.join(peers_failed)} did not answer whole)" if peers_failed else "", wait)
        elif not self._restore_ok:
            wait = self._restore_later()
            log.warning("%s: no other resource is live to give back what it holds of this server: asked again in "
                        "%.0f s", self.server, wait)
        else:
            self._restore_tries, self._restore_next = 0, self.clock() + RESTORE_RETRY_MAX   # the next look for a late peer
        return {"pulled": pulled,
                **({"left": left, "failed": failed} if left or failed else {}),
                **({"peers_failed": peers_failed} if peers_failed else {})}

    # A live peer that says it holds copies of this server, at an address.
    def _holds_mine(self, peer: str, hb: dict) -> bool:
        return peer != self.server and self.server in hb.get("mirrors", {}) and bool(hb.get("url"))

    # The pause before the next try: `RESTORE_RETRY`, doubling to `RESTORE_RETRY_MAX`. The exponent is capped (the review's
    # ninth pass, a minor): `2 ** 1024` is past a float, and the `OverflowError` came before the pause was set — from the
    # 1025th try on, a restore every turn of the loop, with a trace each time.
    def _restore_later(self) -> float:
        wait = min(RESTORE_RETRY_MAX, RESTORE_RETRY * 2 ** min(self._restore_tries, 10))
        self._restore_tries += 1
        self._restore_next = self.clock() + wait
        return wait

    # One bucket back from a peer, into `dest` through a `.tmp`: half a copy is no copy. The `.tmp` is removed whatever
    # failed — and a `.tmp` that was never made (the open itself failed) does not hide the reason behind its own
    # `FileNotFoundError` (the review's eighth pass, a minor).
    def _pull(self, url: str, path: str, dest: str) -> None:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        get_into = getattr(self.peers, "get_into", None)      # in pieces, never the bucket whole (the seventh pass)
        try:
            with open(dest + ".tmp", "wb") as f:
                if get_into is not None:
                    get_into(url, self.server, path, f)
                else:
                    f.write(self.peers.get(url, self.server, path))
        except BaseException:
            with suppress(FileNotFoundError):
                os.remove(dest + ".tmp")
            raise
        os.replace(dest + ".tmp", dest)

    # Whether the restore is to be tried again now, its pause (`RESTORE_RETRY`, doubling) over: it never ran through with
    # somebody to ask, it left buckets with peers, or a peer did not list — or, done, a live peer holds copies of this
    # server and has not given them (looked for every `RESTORE_RETRY_MAX`: one listing of the heartbeats). The resource's
    # loop asks this every turn (`host.run_resource`).
    def restore_due(self) -> bool:
        if self.clock() < self._restore_next:
            return False
        if not self._restore_ok or self.restore_left or self.restore_peers_failed:
            return True
        self._restore_next = self.clock() + RESTORE_RETRY_MAX     # the next look, whatever this one finds or raises
        return any(peer not in self._restored_from and self._holds_mine(peer, hb)
                   for peer, hb in self.live_resources().items())

    # The restore's state as the heartbeat says it: buckets still with peers, failures since start, the peers that did
    # not answer whole, whether it ran through once (`done`), and how long until it is tried again. While it has not,
    # `left` is -1 — not known: no peer was asked (it said 0 — the review's ninth pass).
    def restore_said(self) -> dict:
        pending = bool(self.restore_left or self.restore_peers_failed) or not self._restore_ok
        left = self.restore_left or (0 if self._restore_ok else -1)
        return {"left": left, "failed": self.restore_failed, "peers_failed": self.restore_peers_failed,
                "done": self._restore_ok,
                **({"next_in": round(max(0.0, self._restore_next - self.clock()), 1)} if pending else {})}

    # -- the watermark -------------------------------------------------------------------
    # Retention by days is a PROMISE to the operator; this is what happens when the promise cannot be kept.
    # The resource measures — the disk, not the tree — and says how many bytes to free; each subsystem
    # decides what to give up, because only it knows what its files mean. Nothing here knows what a camera
    # is, and nothing here deletes a subsystem's file.
    #
    # Over `high`, free down to `low`. The resource does not free a subsystem's bytes and does not call its code: it ASKS,
    # by a request row of the subsystem's own family — `<sub>/requests/free-<server>-<volume> {free, volume, server, at}`,
    # for each subsystem whose spec says `requests: {free: true}` — and the subsystem's worker on this server decides
    # what to give up and says what it gave in its heartbeat (`freed: {<volume>: bytes}`), read on the next pass (the
    # boundary's step 6: it was a hook of the subsystem's, `free`, run on this thread). Slowness resolves itself: the row
    # stands while the volume is over and is written again each pass; a volume back under its mark has its rows taken
    # away. With nobody declared to answer — the VMS's footage is in rings that never outgrow their quota — what is short
    # is said as a shortfall, and nothing is cut.
    def relieve(self) -> dict:
        """Over the high mark, ask each subsystem that frees to free bytes down to the low one.

        Per VOLUME, and that is the whole difference from the single-disk case:
        space does not average. A box that is 50% full across two disks, one of
        them at 98%, is a box that stops recording — and freeing bytes on the
        empty one closes nothing, because the unit that cannot write is on the
        full one. So the loop is over volumes, and the volume goes into the request:
        only the subsystem knows which of its files are where, but only the
        resource knows which disk is short.
        """
        # THE STORE NOT ANSWERING IS NOT "THE KNOB IS OFF" (feedback BI). The settings are one row; a pass that
        # could not read it used to stop here with an exception — and a full disk stayed full for as long as
        # the store was away, which is exactly when nobody is looking. The resource keeps what it last read
        # and acts on that. With nothing ever read it says `unknown` and frees nothing: it does not guess.
        try:
            knob = space_settings(self.vars, self._space_knob)
        except OSError as e:
            if self._space_knob is None:
                return {"space": "unknown", "error": str(e)}
            knob = self._space_knob
        else:
            # A number of the row that does not parse is the store ANSWERING with something that is not a setting —
            # unlike its silence, there is no reason to wait: that number as read last, else its default, and the
            # heartbeat says which (the review's seventh pass).
            bad = knob.pop("garbled", [])
            self.space_garbled = (f"{SPACE_KEY} does not parse ({', '.join(bad)}): acting on "
                                  f"{'the settings read last' if self._space_knob else 'the defaults'} for "
                                  f"{'it' if len(bad) == 1 else 'them'}") if bad else ""
            self._space_knob = knob
        if not knob["enabled"]:
            self.short = {}
            return {"space": "off"}
        from . import catalog
        frees = [s for s in catalog.specs() if s.requests_free]
        out, worst, over = {}, 0.0, []
        for name in self.volumes:
            self._progressed()                               # a volume measured is a step (the review's fourth pass)
            sp = self.space(name)
            worst = max(worst, sp["full"])
            if not sp["total"] or sp["used"] <= sp["total"] * knob["high"]:
                for spec in frees:
                    self._unask(spec, name)                  # under the mark: nothing asked of anybody
                continue
            need, freed = int(sp["used"] - sp["total"] * knob["low"]), 0
            for spec in frees:
                said = self._freed(spec, name)               # what its workers here say they gave, since the last ask
                self._progressed()                           # …and so is each subsystem's answer
                freed += said
                out.update({f"{spec.name}.freed": said} if len(self.volumes) == 1 else {f"{spec.name}.{name}.freed": said})
                if freed < need:
                    self._ask(spec, name, need - freed)
            over.append({"volume": name, "full": round(sp["full"], 3), "need": need, "freed": freed,
                         "short": max(0, need - freed)})
        self.short = {v["volume"]: v["short"] for v in over if v["short"]}
        if not over:
            return {"space": "ok", "full": round(worst, 3)}
        first = over[0]                                      # single-volume callers read these three at the top level
        return {"space": "over", "full": first["full"], "need": first["need"], "freed": first["freed"],
                "short": first["short"], "volumes": over, **out}

    # The request row of a subsystem for one of this server's volumes: written while it is over its mark (one row, its
    # bytes as of this pass), taken away when it is not. A store that does not take it is this pass's trouble only.
    def _free_key(self, spec, volume: str) -> str:
        return spec.sub.request_key(f"free-{self.server}-{volume}")

    def _ask(self, spec, volume: str, need: int) -> None:
        try:
            self.vars.put(self._free_key(spec, volume), {"free": str(int(need)), "volume": volume, "server": self.server,
                                                         "at": str(self.wall())})
        except OSError as e:
            log.warning("%s: %s was not asked to free %d bytes on %s: %s", self.server, spec.name, need, volume, e)

    def _unask(self, spec, volume: str) -> None:
        try:
            if self.vars.get(self._free_key(spec, volume))[0] is not None:
                self.vars.delete(self._free_key(spec, volume))
        except OSError:
            pass                                             # asked again or taken away on the next pass

    # What the subsystem's live workers on this server say they freed on the volume (`freed: {<volume>: bytes}` in
    # their heartbeats) — a word there is 0, counted (`rows.number`).
    def _freed(self, spec, volume: str) -> int:
        from .console import heard_live, heartbeats
        total = 0
        for w, hb in heartbeats(self.objects, spec.name + "/").items():
            if str(hb.extra.get("server", "")) != self.server or not heard_live(spec.name, w, hb, self.wall(), self.lost_after, self.eyes):
                continue
            freed = hb.extra.get("freed")
            if isinstance(freed, dict):
                total += int(number(f"{spec.sub.heartbeat_key(w)}#freed.{volume}", freed.get(volume), float, 0))
        return total

    # The timer's body, in order: `retain`, then `relieve` — the promise first, the watermark only for what the promise
    # left behind — then `mirror`; results flattened into one dict (`removed`, `space`, `enabled`, `mirrored`, `peers`).
    #
    # THE PASS CARRIES ITS OWN PULSE (feedback BE). It runs on the thread that heartbeats, and it reads every
    # bucket it keeps: on a year of archive it takes longer than `lost_after`, the resource is called silent,
    # and `redistribute` moves the recordings off a server that is perfectly well. A second thread calling
    # `heartbeat()` would race the pass for the very state a heartbeat reads — the usage it caches, the volumes
    # — so what is sent while the pass runs is the LAST heartbeat again, with the time moved on: bytes already
    # published, and nothing the pass is changing.
    PULSE_SECONDS = 10.0
    # …and not for ever (the review's second pass): a pass stuck on a disk that never answers was `live` with frozen
    # numbers for as long as it hung — so four `lost_after` WITHOUT PROGRESS stopped the pulse, and the resource was
    # silent. That took the presence with it (the review's thirteenth pass, blocker 5): a hung worker on a server whose
    # pass hung was moved at 250 s, two writers. Now the pulse goes on and says the pass is stuck (`pass_stuck`, with how
    # long since it last moved); the presence it sends is looked at anew, with its deadline (`beat`). Frozen numbers are
    # said for what they are, and what runs on the server is still told.
    #
    # Three things the first version got wrong (the review's third pass). The pulse died on its first error — one
    # store write that failed, an exception out of the thread, and a five-minute pass on a store that blinked was a
    # silent resource whose recordings `redistribute` moved off a sound server: each beat is in a `try` of its own
    # now. It measured by the WALL clock, which NTP steps: by a monotonic one (`clock`). And it counted TOTAL time,
    # which a year of archive legitimately takes: "stuck" is no progress — the walk, the retention and each part say
    # they moved (`_progressed`).
    #
    # …and every part says it, not only the walk and the retention (the review's fourth pass): the mirror marks
    # each bucket a peer took, `relieve` each volume and each subsystem's answer, and `kept` is handed `progressed` to
    # call as it goes.
    PULSE_LIMIT = 4

    # The pulse itself, around whatever long step runs on the heartbeat's thread: `pass_`, and `restore` (the seventh
    # pass). Where the beat runs on its own thread (`start_beat`) it is the pulse, and this only marks the step; else
    # a thread beats while the step runs.
    @contextmanager
    def _pulsing(self):
        done = threading.Event()
        self._pass_started, self._stuck_said = self.clock(), False
        self._progressed()

        def pulse():
            while not done.wait(self.PULSE_SECONDS):
                try:
                    self.beat()
                except Exception:                             # noqa: BLE001 — one beat lost, not the pulse
                    log.warning("%s: a pulse of the pass did not go out", self.server, exc_info=True)

        if self._beating is None or not self._beating.is_alive():
            threading.Thread(target=pulse, daemon=True).start()
        try:
            yield
        finally:
            done.set()
            self._pass_started = None

    def pass_(self) -> dict:
        with self._pulsing():
            return self._pass()

    def _pass(self) -> dict:
        # Each part in a `try` of its own (the review's second pass): the promise (`retain`) reads the rows of
        # what is kept, and a store that does not answer used to take the watermark and the mirror with it.
        # What a part could not do is named in `errors`; the next pass tries again. Whatever it raises — not only
        # `OSError` (the review's third pass): a part's bug is that part's, and the walk below is a part too.
        out, errors = {}, []
        def part(name, fn, into=None):
            self._progressed()
            try:
                r = fn()
                out.update(r if into is None else {into: r})
            except Exception as e:                          # noqa: BLE001
                errors.append(f"{name}: {e}")
                log.warning("%s: %s skipped this pass: %s", self.server, name, e)
            self._progressed()

        def measure():                                       # the one walk of the pass, not one per heartbeat
            usage = self.usage()
            self._volume_usage = {n: self.usage(n) for n in self.quotas}   # …and the same for the volumes with a ceiling
            self.last_usage, self.usage_at = usage, self.wall()
            return usage
        part("retain", self.retain, "removed")
        part("usage", measure, "usage")
        part("relieve", self.relieve)
        part("mirror", self.mirror)
        part("blobs", self.mirror_blobs, "blobs")
        if errors:
            out["errors"] = errors
        return out


# The resource over HTTP, in a daemon thread. `extra(path, headers) -> (status, bytes[, headers]) | None`
# lets a subsystem add its own reads (the VMS adds none: its footage is behind the recorders' doors).
#
# #### `class H(BaseHTTPRequestHandler)` (nested)
# - `log_message` — silenced.
# - `_raw(status, body, headers=())` — send a status, `Content-Length`, optional headers and the bytes.
# - `do_GET`:
#   - `GET /buckets/<sub>/<unit>` — `buckets_under` for that unit, one `Bucket.line()` per line, 200.
#   - `GET /mirrored/<server>` — `mirrored_buckets` for that server, same format.
#   - `GET /events?from&to&kind&subsystem&unit&limit&keep&class` — `resource.index.query(...)` as JSON (`unit` is
#     `<sub>/<id>`; a bare id is 400)
#     (`{events, state, truncated}`, unfenced: the console fences); `keep` is "newest" (default) or
#     "oldest" — which end of an overflowing window survives; 400 if it is neither; 503 if the job
#     runs no index.
#         - `GET /events/<path>` — the raw bytes of one bucket; `path` may begin with `.mirror/<server>/`.
#       404 if it contains `..`, does not end in `.events.jsonl`, or is not a file.
#   - anything else — `extra(path, headers)` if given and it answers; otherwise 404.
# - `do_PUT`:
#         - `PUT /mirror/<server>/<path>` — another resource leaves a copy of one of its closed buckets. 400
#       if `..`, empty server, or not `.events.jsonl`; writes to `.mirror/<server>/<path>` via tmp + rename
#       (a copy appears whole or not at all); 204. Any other PUT is 404.
# - `/v1/objects` (the cluster's objects, `objects_listing` / `object_read` / `take_blob` / `object_delete`):
#   - `GET /v1/objects?prefix=&scope=local|cluster` — `{server, objects: {key: {written, server, size}}[, missing]}`.
#   - `GET /v1/objects/<key>?scope=…` — the bytes, `X-Written`, `X-Server` (and `X-Missing`); 404 when nobody has it.
#   - `PUT /v1/objects/<sub>/blobs/sha256-…` — a peer's copy of a blob, hashed before it is kept: 204; 400 when the
#     bytes are not the blob; 405 for anything that is not a blob; 413 past `OBJECT_MAX`.
#   - `DELETE /v1/objects/<sub>/blobs/sha256-…?scope=…` — `{deleted: {server: bool}[, missing]}`; 405 if not a blob.
#   - a scope, key, prefix or length that does not say what it means: 400 with the reason in words.
def serve(resource: Resource, host: str = "0.0.0.0", port: int = 8090, extra=None, extra_put=None) -> ThreadingHTTPServer:
    """The resource over HTTP. `extra(path) -> (status, bytes) | None` lets a
    subsystem add its own reads, and `extra_put(path, headers, rfile)` its
    own writes."""
    # Bounded like every door (the review's sixth pass: the protections were the console's alone): so many connections
    # at once and so many to one address, the next answered 503 on the spot (`door_server`); the request line and
    # headers under a deadline (`Deadlined`). The requests this door HOLDS (`/events/wait`, `WAITERS_MAX`) and the
    # queries it answers at once (`EVENTS_INFLIGHT`) fit inside one address's share with room to spare — they are
    # one server's evaluators and its console. Imported here: `console.py` reads this module for `resources_seen`.
    from .console import STREAM_PIECE, Deadlined, Paced, body_deadline, door_server
    root = resource.root

    class H(Deadlined, BaseHTTPRequestHandler):
        timeout = DOOR_TIMEOUT                            # a socket that sends or reads nothing for this long is let go

        def log_message(self, *a): pass

        def _raw(self, status, body, headers=()):
            self.send_response(status); self.send_header("Content-Length", str(len(body)))
            for k, v in headers: self.send_header(k, v)
            self.end_headers(); self.wfile.write(body)

        # -- the cluster's objects (`/v1/objects`) -------------------------------------------------------------------
        # A request that does not say what it means is answered 400 with the reason in words, never a stack trace and
        # never a guess: a scope that is neither `local` nor `cluster`, a key or a prefix that is not one (`..`, a
        # leading `/`), a length that is not a number.
        def _json(self, status, body, headers=()):
            return self._raw(status, json.dumps(body).encode(), [("Content-Type", "application/json"), *headers])

        def _v1(self):
            """`(key | None, scope, prefix)` of a `/v1/objects` request, or `None` when it was answered (400) here."""
            path, _, query = self.path.partition("?")
            q = {k: v[0] for k, v in urllib.parse.parse_qs(query, keep_blank_values=True).items()}
            scope = q.get("scope", "local")
            if scope not in SCOPES:
                self._json(400, {"error": f"scope is 'local' (this server's objects) or 'cluster' (every server's), "
                                          f"not {scope!r}"})
                return None
            if path == "/v1/objects":
                prefix = q.get("prefix", "")
                if not _safe_prefix(prefix):
                    self._json(400, {"error": f"prefix {prefix!r} is not the beginning of a key: names separated by "
                                              f"'/', nothing absolute, no '..'"})
                    return None
                return None, scope, prefix
            key = urllib.parse.unquote(path[len("/v1/objects/"):])
            if not safe_rel(key):
                self._json(400, {"error": f"{key!r} is not a key: names separated by '/', nothing absolute, no '..'"})
                return None
            return key, scope, ""

        def _objects_get(self):
            asked = self._v1()
            if asked is None:
                return None
            key, scope, prefix = asked
            if key is None:
                objs, missing = resource.objects_listing(prefix, scope)
                return self._json(200, {"server": resource.server, "objects": objs,
                                        **({"missing": missing} if scope == "cluster" else {})})
            try:
                got, missing = resource.object_read(key, scope)
            except ObjectUnreadable as e:                    # there and not readable: 503 in words, not a dropped line
                return self._json(503, {"error": str(e)})
            gone = [("X-Missing", ",".join(missing))] if missing else []
            if got is None:
                return self._json(404, {"error": f"no object {key} on {'any server that answered' if scope == 'cluster' else resource.server}",
                                        **({"missing": missing} if missing else {})}, gone)
            data, written, server = got
            return self._raw(200, data, [("Content-Type", "application/octet-stream"), ("X-Written", repr(float(written))),
                                         ("X-Server", server), *gone])

        def do_DELETE(self):
            if not (self.path.startswith("/v1/objects/")):
                return self._raw(404, b"")
            asked = self._v1()
            if asked is None:
                return None
            key, scope, _ = asked
            if not is_blob_key(key):
                return self._json(405, {"error": f"{key} is not a blob: only a blob (<sub>/blobs/sha256-…) is deleted "
                                                 f"through this door — every other object is written again by its writer"})
            deleted, missing = resource.object_delete(key, scope)
            return self._json(200, {"deleted": deleted, **({"missing": missing} if missing else {})})

        def _objects_put(self):
            asked = self._v1()
            if asked is None:
                return None
            key, _, _ = asked
            if key is None or not is_blob_key(key):
                return self._json(405, {"error": f"{key} is not a blob: a peer puts only a blob (<sub>/blobs/sha256-…) "
                                                 f"here — every other object is written by its own writer on its own server"})
            raw = self.headers.get("Content-Length")
            try:
                n = int(raw)
            except (TypeError, ValueError):
                self.close_connection = True
                return self._json(400, {"error": f"Content-Length {raw!r} is not a number of bytes"})
            if n < 0 or n > OBJECT_MAX:
                self.close_connection = True
                return self._json(413, {"error": f"{n} bytes: a copy of a blob here is at most {OBJECT_MAX}"})
            from .blobs import BlobMismatch
            body_deadline(self, n)
            try:
                resource.take_blob(key, self.rfile, n)
            except BlobMismatch as e:
                return self._json(400, {"error": f"{e}: the copy is refused, this server keeps what it had"})
            except EOFError as e:
                self.close_connection = True
                return self._json(400, {"error": str(e)})
            except ObjectUnkept as e:                        # this server's disk, not the sender's body: 503, no path
                self.close_connection = True
                return self._json(503, {"error": str(e)})
            except (TimeoutError, OSError) as e:
                self.close_connection = True
                return self._json(408, {"error": f"the body did not arrive in time ({_why(e)})"})
            return self._raw(204, b"")

        def do_GET(self):
            if self.path == "/v1/objects" or self.path.startswith(("/v1/objects?", "/v1/objects/")):
                return self._objects_get()
            if self.path.startswith("/buckets/"):
                _, _, sub, unit = (self.path.split("/", 3) + [""])[:4]
                if not (safe_segment(sub) and safe_segment(unit)):     # a name, not a way out of the tree (`doors`)
                    return self._raw(404, b"")
                return self._raw(200, "".join(b.line() + "\n" for b in buckets_under(root, sub, unit, resource.bucket_seconds)).encode())
            if self.path.startswith("/mirrored/"):
                if not safe_segment(self.path[len("/mirrored/"):]):
                    return self._raw(404, b"")
                return self._raw(200, "".join(b.line() + "\n" for b in mirrored_buckets(root, self.path[len("/mirrored/"):], resource.bucket_seconds)).encode())
            if self.path == "/events" or self.path.startswith("/events?"):
                if resource.index is None:
                    return self._raw(503, b'{"error": "this resource runs no event index"}', [("Content-Type", "application/json")])
                if not resource.events_slots.acquire(blocking=False):
                    return self._raw(503, json.dumps({"error": f"busy: {EVENTS_INFLIGHT} queries already being answered"}).encode(),
                                     [("Content-Type", "application/json"), ("Retry-After", "1")])
                try:
                    q = {k: v[0] for k, v in urllib.parse.parse_qs(self.path.partition("?")[2]).items()}
                    try:
                        rep = resource.index.query(float(q.get("from", 0)), float(q.get("to", 1e12)),
                                                   q.get("kind"), q.get("subsystem"), q.get("unit"),
                                                   limit=min(int(q.get("limit", 1000)), MAX_LIMIT), keep=q.get("keep", "newest"),
                                                   cls=q.get("class"), by=q.get("by", "t"))
                    except ValueError as e:                       # an unknown `keep` is refused, not read as the other end
                        return self._raw(400, json.dumps({"error": str(e)}).encode(), [("Content-Type", "application/json")])
                    return self._raw(200, json.dumps(rep).encode(), [("Content-Type", "application/json")])
                finally:
                    resource.events_slots.release()
            # THE LONG POLL (`longpoll.py`): a reader of this resource's events asks to be told when a line of a kind
            # it watches is written, and this request is held until one is — or `timeout` seconds, capped. The answer
            # is `{changed, seq}` and nothing of the events: the reader makes its ordinary query next, through the
            # route above. Asked nothing more than `/events` is: the same door, no new opening.
            #
            # Not under `events_slots`: a held request is not a query being answered, and sixteen of them
            # (`WAITERS_MAX`) must not shut the door to the queries they exist to speed up. One more than that is
            # answered at once, `full`, and its sender goes back to its pass. The door's deadline (`Deadlined`) is on
            # the request line and the headers only; past them a request is its handler's, so a hold trips nothing —
            # and a client that hung up is noticed within a second (`client_gone`), not at the timeout.
            if self.path == "/events/wait" or self.path.startswith("/events/wait?"):
                q = {k: v[0] for k, v in urllib.parse.parse_qs(self.path.partition("?")[2]).items()}
                try:
                    timeout = float(q.get("timeout", WAIT_MAX))
                    since = int(q["since"]) if q.get("since") not in (None, "") else None
                    wants = parse_wants(q.get("want", ""))       # nothing, not a name, too many: 400 (the review's seventh pass)
                except ValueError as e:
                    return self._raw(400, json.dumps({"error": str(e)}).encode(), [("Content-Type", "application/json")])
                rep = resource.watch.wait(wants, timeout, since, gone=lambda: client_gone(self.connection),
                                          client=q.get("client") or None)   # one held request per evaluator
                try:
                    return self._raw(200, json.dumps(rep).encode(), [("Content-Type", "application/json")])
                except OSError:
                    return None                                   # the client went while it was held: nobody to answer
            if self.path.startswith("/events/"):
                rel = self.path[len("/events/"):]; p = os.path.join(root, rel)
                if not safe_rel(rel) or not rel.endswith(".events.jsonl") or not os.path.isfile(p):
                    return self._raw(404, b"")
                return self._bucket(p)
            if extra is not None:
                r = extra(self.path, self.headers)
                if r is not None:
                    return self._raw(*r)
            self._raw(404, b"")

        # A BUCKET GOES OUT IN PIECES (the review's seventh pass, major; reproduced by a run). It was `f.read()` into one
        # reply: eight readers of a 60 MB bucket that did not read held 400 MB in the resource, and a peer slower than
        # 2 MB/s never got one at all — the socket's timeout is the whole of a `sendall`, and `restore` of that bucket
        # failed on every retry. Its length is said (`Content-Length`: a reply that ends short is an error to the
        # reader, not a smaller bucket) and the bytes go `STREAM_PIECE` at a time, each under the socket's timeout, to a
        # reader that keeps `STREAM_MIN_RATE` on average (`Paced`) — what the holder's and the recorders' doors do.
        def _bucket(self, p):
            try:
                f = open(p, "rb")
            except OSError:
                return self._raw(404, b"")
            with f:
                left = os.fstat(f.fileno()).st_size
                self.send_response(200); self.send_header("Content-Length", str(left)); self.end_headers()
                out = Paced(self, chunked=False)
                try:
                    while left > 0:
                        part = f.read(min(left, STREAM_PIECE))
                        if not part:
                            break                             # shorter than it was: the reader sees the length unmet
                        out.write(part); left -= len(part)
                except (OSError, TimeoutError) as e:
                    log.debug("%s: a bucket's reader fell behind or went: %s", resource.server, e)
                if left:
                    self.close_connection = True

        # A body's deadline, whole (the review's seventh pass, major; reproduced by a run): past the headers a request
        # was its handler's, and `PUT /mirror` read its body under nothing but the socket's timeout on each read — 32
        # connections declaring 60 MB and sending a byte every twenty seconds held an address's share for ever, two
        # addresses the whole door: `/events`, `/events/wait` and the mirror were 503. Now the body has the door's
        # `timeout` and a second for every `BODY_RATE` bytes (`body_deadline`, `read_body`'s rule), here and for a
        # subsystem's own writes (`extra_put`); one that does not arrive in time is 408 and leaves no copy.
        #
        # …and a floor on its pace past the door's `timeout` (the review's eighth pass): the deadline was proportional to
        # the length declared, so 64 MiB held its connection 1054 s for a byte every few seconds. Now `got` bytes are in
        # by `timeout + got / BODY_RATE` seconds or the body is late — `DeadlineReader.pace`, which `body_deadline` sets
        # for every door that reads a body. A trickle is let go at the grace; a copy at the rate the deadline assumed is
        # not touched. What a holder of the door's share must now SEND is `BODY_RATE` a connection.
        def do_PUT(self):
            if self.path.startswith("/v1/objects/"):
                return self._objects_put()
            try:
                n = int(self.headers.get("Content-Length", 0))
            except ValueError:
                return self._raw(400, b"")
            if not self.path.startswith("/mirror/"):
                if extra_put is not None:
                    body_deadline(self, n)
                    try:
                        r = extra_put(self.path, self.headers, self.rfile)
                    except TimeoutError:
                        self.close_connection = True
                        return self._raw(408, b"")
                    if r is not None:
                        return self._raw(*r)
                return self._raw(404, b"")
            rel = self.path[len("/mirror/"):]
            server, _, path = rel.partition("/")
            if not safe_segment(server) or not safe_rel(path) or not path.endswith(".events.jsonl"):
                return self._raw(400, b"")
            # A bucket's copy, bounded and never held whole (the review's sixth pass, "every place a body is read"): it
            # was `Content-Length` bytes read into memory, whatever that said, by a door that asks nobody. Past
            # `MIRROR_MAX` it is 413 and nothing is read; within it the bytes go to the file a piece at a time; a
            # body that ends early leaves no copy.
            if n < 0 or n > MIRROR_MAX:
                self.close_connection = True
                return self._raw(413, b"")
            dest = os.path.join(root, MIRROR_DIR, server, path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            left, late = n, False
            body_deadline(self, n)
            with open(dest + ".tmp", "wb") as f:
                try:
                    while left > 0:
                        part = self.rfile.read(min(left, 1 << 16))
                        if not part:
                            break
                        f.write(part); left -= len(part)
                except (TimeoutError, OSError):
                    late = True
            if left:
                os.remove(dest + ".tmp")
                self.close_connection = True
                return self._raw(408 if late else 400, b"")
            os.replace(dest + ".tmp", dest)                     # a copy appears whole or not at all
            self._raw(204, b"")

    srv = door_server((host, port), H)
    # A door that shuts lets go of the requests it holds: each is answered now (`closed`), so no reader waits out
    # its timeout on a resource that has stopped, and no thread of this server outlives it by thirty seconds.
    resource.watch.open()
    shut = srv.shutdown

    def shutdown() -> None:
        resource.watch.close()
        shut()

    srv.shutdown = shutdown
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
