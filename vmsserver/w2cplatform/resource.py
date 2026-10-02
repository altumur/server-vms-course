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
    GET  <url>/events?from&to&cam&kind&subsystem&unit   this resource's EventIndex: its buckets and its copies
    PUT  <url>/mirror/<server>/<path>  another resource leaves a copy of one of ITS closed buckets here

The policy pass runs on a timer: retain each subsystem's buckets by its
policy; relieve the disk if it is over the high mark — the resource measures
and says how many bytes to free, each subsystem decides what to give up;
mirror closed buckets to the next live resource(s) after this one
in sorted order — nobody assigns peers, the rule is the assignment; and any
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
# timer: each subsystem's registered hook first (a subsystem with files of its own registers its pass via
# `Resource.register`), then bucket retention by each subsystem's own `<sub>/retention[/<unit>]` row, then
# the mirror. Mirroring is a knob (`platform/mirror`), and peers are chosen by a rule — the next `copies`
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
#
# ### `__init__(self, root, server, url, vars_, objects, bucket_seconds=600, wall=time.time, peers=None,
# lost_after=45.0)` `root` is the tree (created), `server` the name that goes into heartbeats and peer
# selection, `url` how others reach this resource's HTTP. `hooks` starts empty. `lost_after` is how old a
# peer's heartbeat may be to count as live.
#
# ## Notes
# - The heartbeat's `units` and `mirrors` are derived from the tree on every call — the resource keeps no
#   state a restart could lose.
# - `retain` and `mirror` both walk the tree each pass; on one box that is cheap, and it keeps the job
#   stateless.
# - The console's `/resources` route is `resources_seen` with a `live | silent` label by `lost_after`;
#   `/metrics` counts `<sub>_resources_live` the same way.
# ================================================================================================
from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .doors import MAX_LIMIT, safe_rel, safe_segment

log = logging.getLogger(__name__)

from .contract import BUILD, SCHEMA, check_schema, is_live, parse_heartbeat
from .events import CONSOLE, Bucket, bucket_names_under, buckets_under, parse_bucket, subsystems_under, tree_owner

MIRROR_GRACE = 3600.0     # a copy outlives its original by this: two servers, two clocks
MIRROR_DIR = ".mirror"
EVENTS_INFLIGHT = 8          # `/events` answered at once by one resource; past it, 503 with Retry-After
MIRROR_KEY = "platform/mirror"
SPACE_KEY = "platform/space"
RESOURCES = "platform/resources"


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
def space_settings(vars_) -> dict:
    items, _ = vars_.get(SPACE_KEY)
    d = items or {}
    default_on = os.environ.get("WATERMARK_DEFAULT", "on") != "off"
    return {"enabled": d.get("enabled") == "true" if "enabled" in d else default_on,
            "high": float(d.get("high", 0.85)), "low": float(d.get("low", 0.75)),
            "min_days": float(d.get("min_days", 3))}


# Reads the knob: `enabled` is true only if the row exists and says `"true"`; `copies` defaults to 1.
def mirror_settings(vars_) -> dict:
    items, _ = vars_.get(MIRROR_KEY)
    return {"enabled": bool(items) and items.get("enabled") == "true", "copies": int((items or {}).get("copies", 1))}


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


def retention_days(vars_, subsystem: str, unit: str, default: float = 365.0) -> float:
    """The unit's days if its subsystem set them, else the subsystem's, else a year. A row that says nothing —
    a unit whose field is left to inherit (М12 Lesson 12) — is not zero days: it is the next link."""
    subsystem, alarms = tree_owner(subsystem)
    if subsystem == "audit":                         # who deleted it and who read it: kept as long as alarms are (`journal.py`)
        default = ALARM_DAYS
    family, default = ("alarms_retention", ALARM_DAYS) if alarms else ("retention", default)
    for path in (f"{subsystem}/{family}/{unit}", f"{subsystem}/{family}"):
        items, _ = vars_.get(path)
        if items and str(items.get("days", "")).strip() not in ("", "None"):
            return float(items["days"])
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
def resources_seen(objects) -> dict[str, dict]:
    def parse(raw: bytes) -> dict:                             # one that does not parse is skipped and counted (the review's second pass, M6)
        hb = dict(json.loads(raw))
        hb["server"], float(hb["ts"])                          # what every reader of this dict asks of it
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


# How one resource talks to another: HTTP. Tests substitute an in-process client with the same three methods
# over directories.
class PeerClient:
    """How one resource talks to another: HTTP; tests substitute an in-process client."""
    def __init__(self, timeout: float = 5.0): self.timeout = timeout

    # `GET <url>/mirrored/<server>` — which of `server`'s buckets the peer already holds.
    def mirrored(self, url: str, server: str) -> list[Bucket]:
        with urllib.request.urlopen(f"{url}/mirrored/{server}", timeout=self.timeout) as r:
            return [bucket_from_line(l) for l in r.read().decode().splitlines() if l.strip()]

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
            return r.read()

    # `GET <url>/events/.mirror/<server>/<path>` — pull a copy back (restore).
    def get(self, url: str, server: str, path: str) -> bytes:
        with urllib.request.urlopen(f"{url}/events/{MIRROR_DIR}/{server}/{path}", timeout=self.timeout) as r:
            return r.read()


# A subsystem's hook is called with what it takes of the optional words, and nothing it does not: `volume` (the
# disk that is short — older hooks do not take one) and `progressed` (the pass's pulse: a hook that works for
# minutes says it is moving, or the pulse calls it stuck — the review's fourth pass). Both are right to leave out:
# a subsystem whose files are all on one disk has nothing to choose, and a hook that returns in a second has
# nothing to say. Asked by the signature and not by trying: a `TypeError` raised INSIDE a hook used to be read
# as "it does not take a volume", and the hook was run a second time.
def _call_hook(fn, *args, **optional):
    import inspect
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return fn(*args)
    if any(p.kind is p.VAR_KEYWORD for p in params.values()):
        return fn(*args, **optional)
    return fn(*args, **{k: v for k, v in optional.items() if k in params})


def _ask_to_free(free, need: int, now: float, min_days: float, volume: str, progressed=None) -> dict:
    return _call_hook(free, need, now, min_days, volume=volume, progressed=progressed or (lambda: None))


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
        self._progress_at = clock()                          # when the running pass last got somewhere (`pass_`'s pulse)
        self.hooks: dict[str, object] = {}         # subsystem -> object with .pass_(now) -> dict: its own policy on ITS part of the tree
        self.index = None                          # an eventdatabase.EventIndex over this tree, if the job runs one: served as GET /events
        # What the last pass could NOT free, in bytes, by volume. Over the mark and nothing left to give up is
        # the one state the watermark cannot mend, and it used to be a number in a log line: said in the
        # heartbeat, it is a metric on any console (`<sub>_resource_short_bytes`) and somebody's alert.
        from .journal import Journal
        self.journal = Journal(self.root, "resource", wall)     # what the policy removed (`journal.py`)
        self.short: dict[str, int] = {}
        self.mirror_removed = 0                    # copies of other servers' buckets this resource has let go by age
        self._space_knob: dict | None = None       # the watermark's settings as last READ — what a pass uses when the store does not answer
        self.kept = None                           # `() -> (subsystem, unit, start, end) -> bool`: buckets `retain` must leave, if anybody says so
        # How many `/events` it answers AT ONCE. The server starts a thread per request and never says no, so
        # without a limit a burst of readers is a queue with no end: every answer later, memory growing, and a
        # reader that times out cannot tell "slow" from "gone". Past the limit the answer is 503 with
        # `Retry-After` — a refusal the merge reads as "did not answer", which makes the window incomplete and
        # holds automation's cursor rather than losing what this resource holds (М10B Lesson 25).
        self.events_slots = threading.BoundedSemaphore(EVENTS_INFLIGHT)
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

    # A subsystem installs an object with `pass_(now) -> dict` for its own part of the tree — the same "code
    # under a name" door `spec.register_constraint` opens. A hook that may run long takes `progressed` too —
    # `pass_(now, progressed)`, `free(…, progressed=…)` — and calls it as it goes (`_call_hook`).
    def register(self, subsystem: str, hook) -> None:
        self.hooks[subsystem] = hook

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
    def heartbeat(self) -> dict:
        hb = {"server": self.server, "ts": self.wall(), "url": self.url,
              "schema": SCHEMA, "build": BUILD,                      # what this build understands, and what it is
              "usage": self.usage_cached(), "usage_at": self.usage_at,
              "space": self.space(), "volumes": self.spaces(), "units": self.units(),
              "short": sum(self.short.values()),                     # bytes the last pass was asked to free and could not
              "mirrors": {s: sum(mirrored_count(r, s) for r in self.volumes.values())
                          for r in self.volumes.values() for s in mirrored_servers(r)}}
        self.objects.put(f"{RESOURCES}/{self.server}/heartbeat", json.dumps(hb).encode())
        self._last_heartbeat = hb
        return hb

    # `resources_seen` filtered to heartbeats younger than `lost_after`.
    def live_resources(self) -> dict[str, dict]:
        now = self.wall()
        return {s: hb for s, hb in resources_seen(self.objects).items() if is_live("platform", float(hb["ts"]), now, self.lost_after)}

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
        days_of = {}
        for sub, units in self.units().items():
            for unit in units:
                days_of[(sub, unit)] = retention_days(self.vars, sub, unit)
                self._progressed()                                      # a row read per unit: each is a step
        floor = console_floor(days_of)
        # What somebody said to keep (feedback BH). The resource does not know what a keep is: whoever built
        # it may set `self.kept` — called once a pass, it returns `(subsystem, unit, start, end) -> bool`.
        # It matters most for `{days: 0}`, which is what a deleted unit's retention becomes: without this,
        # deleting the unit erased the very events somebody had marked. If it raises, the pass fails and
        # nothing is swept: not knowing what is kept is not "nothing is". It reads the store row by row, so it is
        # handed `progressed` like a subsystem's pass, if it takes one (the review's sixth pass).
        kept = _call_hook(self.kept, progressed=self._progressed) if self.kept is not None else None
        self._progressed()
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
                            os.remove(os.path.join(path, b.path)); removed.append(b.path)
                            self._progressed()
                            n, a, z = swept.get((sub, unit), (0, b.start, b.end))
                            swept[(sub, unit)] = (n + 1, min(a, b.start), max(z, b.end))
        # What the pass removed, per unit, in the journal: whose buckets, how many, of what period, by what
        # days. It used to be one number in a log line (feedback BN).
        for (sub, unit), (n, a, z) in sorted(swept.items()):
            self.journal.say("events.removed", of=sub, target=unit, buckets=n, since=a, until=z,
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
                        days = retention_days(self.vars, sub, unit)
                        days = max(days, floor) if tree_owner(sub)[0] == CONSOLE else days
                        self._progressed()
                        for b in bucket_names_under(base, sub, unit, self.bucket_seconds, self._progressed):
                            if b.end < self.wall() - days * 86400 - MIRROR_GRACE \
                                    and not (kept is not None and kept(sub, unit, b.start, b.end)):
                                os.remove(os.path.join(base, b.path)); self.mirror_removed += 1
                                self._progressed()
        if removed and self.index is not None:
            self.index.forget(self.server, removed)                     # out of its cache with the file
        return len(removed)

    # The knob. If disabled, `{enabled: False, mirrored: 0, peers: []}`. Otherwise, for each peer from
    # `peers_of`, ask what it already holds and `put` every closed bucket it lacks — any subsystem's,
    # exactly once each, by the server that owns it. Returns `{enabled, mirrored, peers}`. The test shows
    # two buckets mirrored the first pass and zero the second.
    def mirror(self) -> dict:
        """The knob. Every CLOSED bucket on this server — any subsystem — is
        copied to the next live resource(s) after it, exactly once each (the
        peer says what it already holds), by the server that owns it."""
        knob = mirror_settings(self.vars)
        if not knob["enabled"]:
            return {"enabled": False, "mirrored": 0, "peers": []}
        live = self.live_resources()
        peers = peers_of(self.server, list(live), knob["copies"])
        n, closed = 0, None
        for peer in peers:
            have = {b.path for b in self.peers.mirrored(live[peer]["url"], self.server)}
            self._progressed()
            if closed is None:
                closed = self.closed_buckets()               # the walk once a pass, not once per peer
            for b in closed:
                if b.path in have:
                    continue
                with open(self.path_of(b.path), "rb") as f:
                    self.peers.put(live[peer]["url"], self.server, b.path, f.read())
                n += 1
                # Each copy the peer took is progress (the review's fourth pass): the FIRST mirroring of a server
                # sends a year of buckets, and without a mark per bucket a mirror that moved the whole time was
                # "stuck" to the pulse after four `lost_after` — the resource silent, its recordings moved.
                self._progressed()
        return {"enabled": True, "mirrored": n, "peers": peers}

    # The reverse, run by the owner: for every live peer whose heartbeat lists me under `mirrors`, pull each
    # of my buckets it holds that I do not have (tmp + rename), then, if anything came back, run every
    # registered hook once so the subsystem re-indexes. Returns `{pulled, <sub>.<key>: …}`. In the test,
    # `srv-a` with a wiped disk pulls 2 buckets; the open bucket that was never mirrored is the RPO.
    def restore(self) -> dict:
        """The reverse, run by the owner: pull my buckets from whoever holds
        copies, then let each subsystem's hook re-index what came back."""
        pulled = 0
        for peer, hb in self.live_resources().items():
            if peer == self.server or self.server not in hb.get("mirrors", {}):
                continue
            for path in sorted(b.path for b in self.peers.mirrored(hb["url"], self.server)):
                dest = self.path_of(path)          # back onto the volume that held it, or the emptiest
                if os.path.exists(dest):
                    continue
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest + ".tmp", "wb") as f:
                    f.write(self.peers.get(hb["url"], self.server, path))
                os.replace(dest + ".tmp", dest); pulled += 1
        hooks = {sub: _call_hook(h.pass_, self.wall(), progressed=self._progressed)
                 for sub, h in self.hooks.items()} if pulled else {}
        return {"pulled": pulled, **{f"{s}.{k}": v for s, r in hooks.items() for k, v in r.items()}}

    # -- the watermark -------------------------------------------------------------------
    # Retention by days is a PROMISE to the operator; this is what happens when the promise cannot be kept.
    # The resource measures — the disk, not the tree — and says how many bytes to free; each subsystem
    # decides what to give up, because only it knows what its files mean. Nothing here knows what a camera
    # is, and nothing here deletes a subsystem's file.
    #
    # Over `high`, free down to `low`. Slowness resolves itself: a hook that can only start something (a move
    # to another disk, say) returns what it managed and is asked again on the next pass — which is why there is
    # no third, "critical" mark and no separate schedule. With nothing registered to answer — the VMS's footage
    # is in rings that never outgrow their quota — what is short is said as a shortfall, and nothing is cut.
    def relieve(self) -> dict:
        """Over the high mark, ask each subsystem to free bytes down to the low one.

        Per VOLUME, and that is the whole difference from the single-disk case:
        space does not average. A box that is 50% full across two disks, one of
        them at 98%, is a box that stops recording — and freeing bytes on the
        empty one closes nothing, because the unit that cannot write is on the
        full one. So the loop is over volumes, and the volume goes to the hook:
        only the subsystem knows which of its files are where, but only the
        resource knows which disk is short.
        """
        # THE STORE NOT ANSWERING IS NOT "THE KNOB IS OFF" (feedback BI). The settings are one row; a pass that
        # could not read it used to stop here with an exception — and a full disk stayed full for as long as
        # the store was away, which is exactly when nobody is looking. The resource keeps what it last read
        # and acts on that. With nothing ever read it says `unknown` and frees nothing: it does not guess.
        try:
            knob = self._space_knob = space_settings(self.vars)
        except OSError as e:
            if self._space_knob is None:
                return {"space": "unknown", "error": str(e)}
            knob = self._space_knob
        if not knob["enabled"]:
            self.short = {}
            return {"space": "off"}
        out, worst, over = {}, 0.0, []
        for name in self.volumes:
            self._progressed()                               # a volume measured is a step (the review's fourth pass)
            sp = self.space(name)
            worst = max(worst, sp["full"])
            if not sp["total"] or sp["used"] <= sp["total"] * knob["high"]:
                continue
            need, freed = int(sp["used"] - sp["total"] * knob["low"]), 0
            for sub, h in self.hooks.items():
                free = getattr(h, "free", None)
                if free is None:
                    continue                                 # a subsystem that keeps only buckets: `retain` is its whole policy
                rep = _ask_to_free(free, need - freed, self.wall(), knob["min_days"], name, self._progressed)
                self._progressed()                           # …and so is each subsystem's answer
                freed += int(rep.get("freed", 0))
                out.update({f"{sub}.{k}": v for k, v in rep.items()} if len(self.volumes) == 1
                           else {f"{sub}.{name}.{k}": v for k, v in rep.items()})
                if freed >= need:
                    break
            over.append({"volume": name, "full": round(sp["full"], 3), "need": need, "freed": freed,
                         "short": max(0, need - freed)})
        self.short = {v["volume"]: v["short"] for v in over if v["short"]}
        if not over:
            return {"space": "ok", "full": round(worst, 3)}
        first = over[0]                                      # single-volume callers read these three at the top level
        return {"space": "over", "full": first["full"], "need": first["need"], "freed": first["freed"],
                "short": first["short"], "volumes": over, **out}

    # The timer's body, in order: each subsystem's hook (it may index or drop lines), then `retain`, then
    # `relieve` — the promise first, the watermark only for what the promise left behind — then `mirror`;
    # results flattened into one dict (`<sub>.<key>`, `removed`, `space`, `enabled`, `mirrored`, `peers`).
    #
    # THE PASS CARRIES ITS OWN PULSE (feedback BE). It runs on the thread that heartbeats, and it reads every
    # bucket it keeps: on a year of archive it takes longer than `lost_after`, the resource is called silent,
    # and `redistribute` moves the recordings off a server that is perfectly well. A second thread calling
    # `heartbeat()` would race the pass for the very state a heartbeat reads — the usage it caches, the volumes
    # — so what is sent while the pass runs is the LAST heartbeat again, with the time moved on: bytes already
    # published, and nothing the pass is changing.
    PULSE_SECONDS = 10.0
    # …and not for ever (the review's second pass): a pass stuck on a disk that never answers would be `live`
    # with frozen numbers for as long as it hung. Four `lost_after` WITHOUT PROGRESS and the pulse stops; the pass
    # is then what it is — silent — and the heartbeat says how long it has been running while it still beats.
    #
    # Three things the first version got wrong (the review's third pass). The pulse died on its first error — one
    # store write that failed, an exception out of the thread, and a five-minute pass on a store that blinked was a
    # silent resource whose recordings `redistribute` moved off a sound server: each beat is in a `try` of its own
    # now. It measured by the WALL clock, which NTP steps: by a monotonic one (`clock`). And it stopped at four `lost_after`
    # of TOTAL time, which a year of archive legitimately takes: it stops at four `lost_after` with no progress —
    # the walk, the retention and each part say they moved (`_progressed`) — which is what "stuck" means.
    #
    # …and every part says it, not only the walk and the retention (the review's fourth pass): the mirror marks
    # each bucket a peer took, `relieve` each volume and each subsystem's answer, and a subsystem's hook is handed
    # `progressed` to call as it goes. A part that moves the whole time keeps the pulse; one that hangs — a peer
    # that takes nothing, a disk that does not answer — stops it, as before.
    PULSE_LIMIT = 4

    def pass_(self) -> dict:
        done = threading.Event()
        started = self.clock()
        self._progressed()

        def pulse():
            while not done.wait(self.PULSE_SECONDS):
                try:
                    now = self.clock()
                    running, still = now - started, now - self._progress_at
                    if still > self.PULSE_LIMIT * self.lost_after:
                        log.error("%s: the pass has made no progress for %.0f s — longer than %d × lost_after: the pulse "
                                  "stops, and this resource is reported silent until the pass ends", self.server, still,
                                  self.PULSE_LIMIT)
                        return
                    last = getattr(self, "_last_heartbeat", None)
                    if last is not None:
                        self.objects.put(f"{RESOURCES}/{self.server}/heartbeat",
                                         json.dumps({**last, "ts": self.wall(), "pass_seconds": round(running, 1)}).encode())
                except Exception:                             # noqa: BLE001 — one beat lost, not the pulse
                    log.warning("%s: a pulse of the pass did not go out", self.server, exc_info=True)

        threading.Thread(target=pulse, daemon=True).start()
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
        try:
            for sub, h in self.hooks.items():                    # a subsystem's own pass first: it may index or drop lines
                part(sub, lambda h=h, sub=sub: {f"{sub}.{k}": v for k, v in
                                                _call_hook(h.pass_, self.wall(), progressed=self._progressed).items()})
            part("retain", self.retain, "removed")
            part("usage", measure, "usage")
            part("relieve", self.relieve)
            part("mirror", self.mirror)
            if errors:
                out["errors"] = errors
            return out
        finally:
            done.set()


# The resource over HTTP, in a daemon thread. `extra(path, headers) -> (status, bytes[, headers]) | None`
# lets a subsystem add its own reads (the VMS adds none: its footage is behind the recorders' doors).
#
# #### `class H(BaseHTTPRequestHandler)` (nested)
# - `log_message` — silenced.
# - `_raw(status, body, headers=())` — send a status, `Content-Length`, optional headers and the bytes.
# - `do_GET`:
#   - `GET /buckets/<sub>/<unit>` — `buckets_under` for that unit, one `Bucket.line()` per line, 200.
#   - `GET /mirrored/<server>` — `mirrored_buckets` for that server, same format.
#   - `GET /events?from&to&cam&kind&subsystem&unit&limit&keep&class` — `resource.index.query(...)` as JSON
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
def serve(resource: Resource, host: str = "0.0.0.0", port: int = 8090, extra=None, extra_put=None) -> ThreadingHTTPServer:
    """The resource over HTTP. `extra(path) -> (status, bytes) | None` lets a
    subsystem add its own reads, and `extra_put(path, headers, rfile)` its
    own writes."""
    root = resource.root

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def _raw(self, status, body, headers=()):
            self.send_response(status); self.send_header("Content-Length", str(len(body)))
            for k, v in headers: self.send_header(k, v)
            self.end_headers(); self.wfile.write(body)

        def do_GET(self):
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
                                                   int(q["cam"]) if q.get("cam") else None, q.get("kind"), q.get("subsystem"), q.get("unit"),
                                                   limit=min(int(q.get("limit", 1000)), MAX_LIMIT), keep=q.get("keep", "newest"),
                                                   cls=q.get("class"), by=q.get("by", "t"))
                    except ValueError as e:                       # an unknown `keep` is refused, not read as the other end
                        return self._raw(400, json.dumps({"error": str(e)}).encode(), [("Content-Type", "application/json")])
                    return self._raw(200, json.dumps(rep).encode(), [("Content-Type", "application/json")])
                finally:
                    resource.events_slots.release()
            if self.path.startswith("/events/"):
                rel = self.path[len("/events/"):]; p = os.path.join(root, rel)
                if not safe_rel(rel) or not rel.endswith(".events.jsonl") or not os.path.isfile(p):
                    return self._raw(404, b"")
                with open(p, "rb") as f: return self._raw(200, f.read())
            if extra is not None:
                r = extra(self.path, self.headers)
                if r is not None:
                    return self._raw(*r)
            self._raw(404, b"")

        def do_PUT(self):
            if not self.path.startswith("/mirror/"):
                if extra_put is not None:
                    r = extra_put(self.path, self.headers, self.rfile)
                    if r is not None:
                        return self._raw(*r)
                return self._raw(404, b"")
            rel = self.path[len("/mirror/"):]
            server, _, path = rel.partition("/")
            if not safe_segment(server) or not safe_rel(path) or not path.endswith(".events.jsonl"):
                return self._raw(400, b"")
            dest = os.path.join(root, MIRROR_DIR, server, path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            n = int(self.headers.get("Content-Length", 0))
            with open(dest + ".tmp", "wb") as f:
                f.write(self.rfile.read(n))
            os.replace(dest + ".tmp", dest)                     # a copy appears whole or not at all
            self._raw(204, b"")

    srv = ThreadingHTTPServer((host, port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
