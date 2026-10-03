"""The event log — a platform piece. What the platform knows about events,
and it is all of this:

    a bucket    <resource>/<subsystem>/<unit>/e<epoch>/<start>Z.events.jsonl
                JSON lines {t, kind, ...}, for a span of `bucket_seconds` starting at <start>
    its writer  the worker that holds that unit's epoch — one writer per file, by construction
    its fence   the epoch in the path: a stale instance writes into its own bucket, marked afterwards
    its index   the resource's own over its tree (`eventdatabase.py`), and (М11) a cluster-wide cache over every resource

Nothing here knows what a unit is. The VMS's recording has footage — in a
volume of its own — and its bucket is here; a detector's unit is a model; a gateway's
unit is a fan-out. The word "event" means only: something a worker
observed at a time, about a unit it holds.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # events.py — the event log: JSON-lines buckets per unit per epoch on the resource, for any subsystem
#
# **Role in the module.** Lesson 3. An event here means only "something a worker observed at a time, about a
# unit it holds the epoch for". The platform fixes the shape and nothing else: a bucket is `<resource
# root>/<subsystem>/<unit>/e<epoch>/<start>Z.events.jsonl`, holding JSON lines `{t, kind, ...}` for a span
# of `bucket_seconds` starting at `<start>`; its writer is the worker holding that unit's epoch (one writer
# per file by construction); its fence is the epoch in the path (a stale instance writes into its own
# bucket, which is marked afterwards); its index is `eventdatabase.py` on each resource, over its own tree. `resource.py` walks these paths for retention
# and mirroring; `console.py` uses `EventLog` for operator marks under `console/<instance>/`; the VMS worker
# uses it per camera. Nothing here knows what a unit is.
#
# ## Module-level names
# - `EVENTS` — regex for a bucket filename: `YYYYMMDDTHHMMSSZ.events.jsonl`.
# - `EPOCH_DIR` — regex for the epoch directory: `e<digits>`.
#
# ## Notes
# - `test_lesson3_archive.py::test_events_are_buckets_on_the_resource_recording_or_not` and
#   `test_lesson4_worker.py::test_the_worker_observes_what_it_holds_recording_or_not` exercise the VMS's use
#   of this file: buckets are written whether or not media is recorded, closed buckets are counted onto the
#   timeline, and a fenced epoch's bucket is marked, not deleted.
# - A bucket is "closed" when `end <= now`; only closed buckets are mirrored and indexed
#   (`resource.Resource.closed_buckets`). The open one is the accepted loss on a disk failure.
# ================================================================================================
from __future__ import annotations

import itertools
import json
import os
import random
import re
import string

try:
    import fcntl                                  # Unix; `durably` falls back to `os.fsync` without it
except ImportError:                               # pragma: no cover - the course runs on Unix
    fcntl = None
from dataclasses import dataclass
from datetime import datetime, timezone

from .rows import PARSE_ERRORS

EVENTS =re.compile(r"^(\d{8}T\d{6}Z)\.events\.jsonl$")
EPOCH_DIR = re.compile(r"^e(\d+)$")


# Floors `t` to the start of its bucket span. Buckets roll by the clock, not by anything the subsystem does.
def bucket_start(t: float, bucket_seconds: int) -> float:
    return float(int(t // bucket_seconds) * bucket_seconds)


# UTC `%Y%m%dT%H%M%SZ` for a timestamp — the filename stem.
def _stamp(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# `<root>/<subsystem>/<unit>`.
def unit_dir(root: str, subsystem: str, unit: str) -> str:
    return os.path.join(root, subsystem, str(unit))


# `<root>/<subsystem>/<unit>/e<epoch>/<stamp>.events.jsonl`.
def bucket_path(root: str, subsystem: str, unit: str, epoch: int, start: float) -> str:
    return os.path.join(unit_dir(root, subsystem, unit), f"e{epoch}", _stamp(start) + ".events.jsonl")


# The inverse of `bucket_path`: relative to `root`, exactly four components, third matching `EPOCH_DIR`,
# fourth matching `EVENTS`; the start is parsed back to a UTC timestamp. Anything else (a scan's progress, a
# tmp file) is `None`, which is how the walkers below ignore whatever a subsystem keeps beside
# its buckets.
def parse_bucket(path: str, root: str) -> tuple[str, str, int, float] | None:
    """-> (subsystem, unit, epoch, start) for a bucket path under root, else None."""
    rel = os.path.relpath(path, root).split(os.sep)
    if len(rel) != 4 or not EPOCH_DIR.match(rel[2]):
        return None
    m = EVENTS.match(rel[3])
    if not m:
        return None
    start = datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).timestamp()
    return rel[0], rel[1], int(rel[2][1:]), start


# One bucket as the resource describes it over HTTP and the index stores it.
# - `subsystem`, `unit`, `epoch`, `start`, `end` (= start + bucket_seconds), `path` (relative to the
#   resource root), `events` (line count).
@dataclass(frozen=True)
class Bucket:
    subsystem: str
    unit: str
    epoch: int
    start: float
    end: float
    path: str            # relative to the resource root
    events: int

    # The bucket as one JSON line with `kind: "events"` — the wire form of `GET /buckets/<sub>/<unit>` and
    # `GET /mirrored/<server>`; `resource.bucket_from_line` parses it back.
    def line(self) -> str:
        return json.dumps({"kind": "events", "subsystem": self.subsystem, "unit": self.unit, "epoch": self.epoch,
                           "start": self.start, "end": self.end, "path": self.path, "events": self.events})


# ==================================================================================================
# Traffic classes — two, because two is the fewest that can carry different policy.
# ==================================================================================================
# An ALARM is a line whose loss is the loss of the thing the system exists for: a door forced, a contact
# opened, a stream gone. An OBSERVATION is everything else, and it is nearly every line.
#
# The class is a FIELD, declared and refused, and deliberately not a convention on `kind`. A convention
# refuses nothing: it reads whatever is written and quietly excludes a typo, and the exclusion shows up
# months later as an alarm nobody was shown. This is the same reason `keep` is refused rather than read
# leniently (Lesson 13) and a suppression rule is refused at load (above).
#
# Two is a decision, not a placeholder. A class earns its place by having a POLICY that differs, and
# today exactly one does: when a window overflows its limit, observations are dropped before alarms
# (`eventdatabase.query`). A third class with no policy of its own would be a word in a file.
#
# Which lines are alarms is NOT settled here, and not in a subsystem's spec either: the same `io.input` is
# an alarm on a door contact and noise on a technological sensor, and the difference is how the device was
# wired, not what the event type is. So the platform fixes the vocabulary and refuses anything outside it;
# the value comes from the unit's own configuration, one layer up.
ALARM = "alarm"
OBSERVATION = "observation"
CLASSES = (ALARM, OBSERVATION)

# WHERE AN ALARM LIES: a tree of its own, `<subsystem>.alarms/<unit>/e<epoch>/…`, beside `<subsystem>/<unit>/…`
# (the platform review, "a retention of its own for the class `alarm`"; agreed with the product, whose format
# this is too — feedback BO).
#
# An alarm and an observation used to share a bucket, and a bucket is deleted whole. So either a year of a
# driver's statistics was kept for the sake of one door alarm, or the alarm went with the statistics. Two ways
# out. Rewrite old buckets, dropping the observations — which breaks "a closed bucket is never written again",
# the rule mirroring, the index's cache and the check of copies all stand on. Or write alarms apart from the
# start. This is the second.
#
# The shape is the same and only the first directory differs, so everything that WALKS a resource's tree —
# buckets, the mirror, the doors — sees one more directory and knows nothing about classes. Two things know:
# the WRITER picks the tree by the line's class (`EventLog.append`), and the INDEX, asked for a subsystem,
# reads both and answers under the subsystem's own name — where a line lies is not whose it is.
#
# Buckets written before this hold both classes in the first tree and live out the days they had. The index
# reads them as it always did; nothing is moved.
ALARM_TREE = ".alarms"


def alarm_tree(subsystem: str) -> str:
    return subsystem + ALARM_TREE


# `(subsystem, is it the alarm tree)` for a first directory of a resource: `vms.alarms` is `vms`'s.
def tree_owner(name: str) -> tuple[str, bool]:
    return (name[:-len(ALARM_TREE)], True) if name.endswith(ALARM_TREE) else (name, False)


# The console's own subsystem name: its marks (and whatever else an operator records about the system)
# live in `console/<instance>/` beside every worker's buckets, written by the console process, epoch 1
# because there is one writer. `resource.retain` knows this name for one reason — see `console_floor`.
CONSOLE = "console"


# macOS' `fsync` returns as soon as the kernel has the bytes; only `F_FULLFSYNC` asks the drive to flush
# its own write cache. Measured on this course's machine: `append` as it stands runs at ~20,000 lines/s,
# adding `os.fsync` changes nothing worth measuring (~21,000/s — it is not reaching the platters), and
# `F_FULLFSYNC` costs 4.25 ms a line, which is 235 lines/s. That is the real price of durability, and it
# is ninety times what the free-looking call suggests.
#
# So the fallback is not a nicety: a build that used plain `fsync` here and believed itself durable would
# have bought a feeling. Linux's `fsync` does go to the device (barriers permitting) and needs no special
# call, which is why this is a try and not a platform check.
_F_FULLFSYNC = 51


def durably(f) -> None:
    """Flush one open file all the way to the medium, as far as the platform allows."""
    try:
        fcntl.fcntl(f.fileno(), _F_FULLFSYNC)
    except (AttributeError, OSError, ValueError, NameError):
        os.fsync(f.fileno())


# A file is not durable until the DIRECTORY ENTRY that names it is: fsync the file of a bucket created a
# moment ago and a power cut can leave the bytes on the disk with nothing pointing at them. It is the torn
# line one level up — the thing exists and does not — and it costs one more barrier, but only on the pass
# that creates the file, which is once per unit per ten minutes.
def durable_dir(path: str) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


# THE LINE, AS AGREED WITH THE PRODUCT (feedback BL; the platform review, "an event line with no second
# timestamp, no id and no version"). The file format is shared, so the names and what they mean are too:
#
#   t          when the line was WRITTEN, by the writer's clock. Always there, and its meaning has not changed.
#              It is what files a line: the bucket is chosen by `t`, a closed bucket is never written again —
#              and mirroring (closed buckets are copied), the index's cache and the retention pass all stand on
#              that. An event filed by when it HAPPENED would, arriving an hour late, have to be appended to a
#              file a neighbour has already copied; a month late, to one that was deleted
#   occurred   when the event HAPPENED, by the writer's clock, as far as the writer knows. Only when it knows
#              better than `t`: a device that reported late, a driver's callback a pass ago. A device's own
#              raw clock is not this — it is brought to the writer's clock first, or it is a field of the kind
#   id         the line's name: `<unit>-e<epoch>-<process>-<n>`. Given by the writer when it writes; the
#              device is not needed for it, and a device's own id, when it has one, is a field of the kind.
#              What tells a COPY from a TWIN: two events of one kind in one instant used to be one event to
#              the merge, which knew a line by (server, file, time, kind, unit)
#   v          the format's version — and NOT written. A line without `v` is version 1; a reader skips the
#              fields it does not know; `v` appears the day a line changes so that an old reader would read it
#              WRONGLY, and not before
#
# The process is in the id because several processes write under one epoch in one place: a console's marks
# and its journal of archive reads are all epoch 1.
_PROC = "".join(random.choice(string.ascii_lowercase) for _ in range(10))
_SEQ = itertools.count(1)


def new_event_id(unit: str, epoch: int) -> str:
    return f"{unit}-e{epoch}-{_PROC}-{next(_SEQ)}"


# How late a line may be written after what it is about and still be found by a query in EVENT time
# (`by=occurred`): the index reads the window's buckets and this much further on, because the late line lies
# in a later file. Later than this, a query by `t` still finds it — always.
MAX_EVENT_LATENESS = 3600.0


# When an event is, for a reader that asks in event time: `occurred` where the writer knew it, else `t`.
def when(e: dict) -> float:
    return float(e.get("occurred", e["t"]))


# What a worker holds per unit it has an epoch for: the writer side.
class EventLog:
    """What a worker holds per unit it has an epoch for. `append` writes one
    line, flushed, into the bucket for `t`; buckets roll by the clock, not by
    anything the subsystem does."""

    # Fixes the resource root, the subsystem prefix, the unit (stringified), the epoch this writer holds and
    # the bucket span (10 minutes by default).
    def __init__(self, root: str, subsystem: str, unit: str, epoch: int, bucket_seconds: int = 600):
        self.root, self.subsystem, self.unit, self.epoch, self.bucket_seconds = root, subsystem, str(unit), epoch, bucket_seconds
        self._synced: set[str] = set()            # bucket FILES whose directory entry this writer has made durable
        self._synced_dirs: set[str] = set()       # …and epoch directories whose own entry it has

    # The bucket file that time `t` falls in, for this epoch — in the alarms' tree for an alarm.
    def path_for(self, t: float, cls: str = OBSERVATION) -> str:
        tree = alarm_tree(self.subsystem) if cls == ALARM else self.subsystem
        return bucket_path(self.root, tree, self.unit, self.epoch, bucket_start(t, self.bucket_seconds))

    # Writes one JSON line `{t, kind, **fields}` to the bucket for `t`, creating directories, flushing after
    # the write; returns the path. Append-only, one process per file: the epoch in the path guarantees no
    # two live writers share a file.
    #
    # `cls` is the line's TRAFFIC CLASS, and it is a declared value rather than a convention on `kind`.
    # A convention — "kinds beginning with io. are alarms" — does not refuse anything: the first
    # `det.Motion` written where `det.motion` was meant falls out of its class in silence, and stays out
    # until somebody reads the file by hand. An unknown class is refused here instead, where the line is
    # written and the traceback names the writer.
    #
    # Only an alarm is written down. Absent means `observation`, which is what nearly every line is, and
    # a class on every line would be a word repeated a million times to say "nothing special".
    def append(self, t: float, kind: str, cls: str = OBSERVATION, durable: bool = False, **fields) -> str:
        if cls not in CLASSES:
            raise ValueError(f"event class is one of {', '.join(CLASSES)}, not {cls!r}")
        if "class" in fields:
            raise ValueError("`class` is the traffic class and travels as `cls=`, not as a field — two "
                             "spellings of one thing drift, and the drift is invisible in the file")
        if "occurred" in fields and (isinstance(fields["occurred"], bool) or not isinstance(fields["occurred"], (int, float))):
            raise ValueError(f"`occurred` is a time, in seconds, by the writer's clock — not {fields['occurred']!r}")
        if "v" in fields:
            raise ValueError("`v` is the format's version and is not written: a line without it is version 1")
        given = fields.pop("id", None)               # the writer names the line; a name it was handed is kept
        p = self.path_for(t, cls)                    # the class picks the tree: an alarm is kept by its own days
        os.makedirs(os.path.dirname(p), exist_ok=True)
        line = {"t": t, "kind": kind, **({} if cls == OBSERVATION else {"class": cls}),
                "id": str(given) if given else new_event_id(self.unit, self.epoch), **fields}
        # The second policy the class carries, and the one that costs something. An observation is
        # flushed and no more: it survives the process dying, not the power going, and that loss was
        # accepted on purpose (see `read_bucket` below — it is the same shape as the accepted loss for
        # footage). An ALARM is not the same trade. It is written down because losing it is losing the
        # thing the system is for, and a line that only reached the page cache is not written down.
        #
        # The cost is real and only alarms pay it: ~4 ms a line here against ~50 µs (`durably`). A box
        # where alarms arrive faster than a couple of hundred a second has a different problem, and
        # suppression above is what answers it.
        with open(p, "a") as f:
            f.write(json.dumps(line) + "\n"); f.flush()
            if cls == ALARM or durable:              # `durable`: the journal's lines — a deletion's "who" (the review's second pass)
                durably(f)
        # …and the directory entry that names the file, once per bucket FILE this writer has touched.
        #
        # Not "when the alarm created the file": an OBSERVATION may have created it a moment ago and paid
        # for no barrier at all, so the entry can still be only in the cache while the alarm's bytes are
        # on the platter — the bytes safe and nothing pointing at them. What decides is whether THIS
        # writer has made this file's entry durable yet, and a set of paths answers that without a stat.
        #
        # Per FILE, not per directory (the review's third pass): every bucket of an epoch lives in one `e<epoch>`
        # directory, so "once per directory" synced the first bucket's entry and none after it — ten minutes later
        # the next bucket's alarms were on the platter with nothing naming them. And the first time this writer
        # reaches an `e<epoch>` directory, its parent is synced too: a new epoch's directory is itself an entry.
        #
        # …and so is every directory above it, up to the tree's root (the review's fourth pass): the first alarm of a
        # new unit creates `<sub>.alarms/<unit>/e<epoch>/` at once, and syncing only `<unit>` left `<unit>`'s own
        # entry in `<sub>.alarms`, and that one's in the root, in the cache — after a power cut the file is on the
        # platter and the path to it is not. Once per directory per writer, as before: three barriers more on the
        # first alarm of a unit, and nothing after. Not only the directories THIS call created: an observation may
        # have made them a moment ago and paid for no barrier, which is the same argument as for the file above.
        if (cls == ALARM or durable) and p not in self._synced:
            d = os.path.dirname(p)
            durable_dir(d)
            if d not in self._synced_dirs:
                top, up = os.path.abspath(self.root), os.path.dirname(d)
                while True:
                    durable_dir(up)                  # the entry of the directory below `up` lives in `up`
                    if os.path.abspath(up) == top or os.path.dirname(up) == up:
                        break
                    up = os.path.dirname(up)
                self._synced_dirs.add(d)
            self._synced.add(p)
        return p


# All lines of one bucket parsed; a missing file is an empty list. A line that does not parse is SKIPPED,
# not fatal: an OBSERVATION is written and flushed and no more, so a crash or a power loss can leave the
# last line half-written, and losing the whole bucket for one torn line would lose ten minutes of
# observations where one record was actually damaged. The accepted loss is then the same shape as it is
# for footage — the open thing, not the day (М10B Lesson 6). `torn` counts them, so a resource whose
# buckets keep tearing says so instead of quietly returning less.
#
# An alarm is not in that trade: `append` takes it all the way to the medium, so a torn last line is an
# observation's, not an alarm's. That is the difference the class buys, and it is why the counter here
# stayed a counter instead of becoming an error.
torn = 0


def read_bucket(path: str) -> list[dict]:
    global torn
    out = []
    try:
        with open(path, errors="replace") as f:       # a byte that is no UTF-8 is that line's, not the bucket's
            for line in f:
                if not line.strip():
                    continue
                try:                                  # a half-written last line: the writer died mid-append — and one
                    e = json.loads(line)              # nested past JSON's depth, or not an object, is that line's too
                    if not isinstance(e, dict):       # (the eleventh review's sweep of `mark_of`)
                        raise TypeError("not an object")
                    out.append(e)
                except PARSE_ERRORS:
                    torn += 1
    except FileNotFoundError:
        return []
    return out


# Every bucket file for a unit, from the files alone — what repair and the resource's `/buckets` route read.
# Walks the unit directory, keeps what `parse_bucket` accepts, counts lines, sorts by `(start, epoch)`.
def buckets_under(root: str, subsystem: str, unit: str, bucket_seconds: int) -> list[Bucket]:
    """Every bucket file for a unit, from the files alone — what repair reads."""
    out = []
    base = unit_dir(root, subsystem, unit)
    for d, _, files in os.walk(base):
        for f in files:
            p = os.path.join(d, f)
            parsed = parse_bucket(p, root)
            if parsed:
                sub, u, epoch, start = parsed
                out.append(Bucket(sub, u, epoch, start, start + bucket_seconds, os.path.relpath(p, root), len(read_bucket(p))))
    return sorted(out, key=lambda b: (b.start, b.epoch))


# The same list from the NAMES alone: `events` is 0 and no file is opened.
#
# A bucket's path says everything a policy needs — whose it is, which epoch, when it starts — and its end is
# the start plus the bucket's length. `buckets_under` also opens every file to count its lines, which is what
# `/buckets` answers and what nothing that SWEEPS needs: the retention pass read a year of archive, every
# pass, to delete the files of one day (the platform review; feedback BI).
#
# `progressed`, if given, is called for every directory listed and every bucket named (the review's fifth pass,
# Т-M13's remainder): a year of one camera is fifty thousand buckets, and on a cold disk listing them is minutes —
# one mark per UNIT left the resource's pulse calling a walk that moved the whole time "stuck".
def bucket_names_under(root: str, subsystem: str, unit: str, bucket_seconds: int, progressed=None) -> list[Bucket]:
    out = []
    for d, _, files in os.walk(unit_dir(root, subsystem, unit)):
        if progressed is not None:
            progressed()
        for f in files:
            p = os.path.join(d, f)
            parsed = parse_bucket(p, root)
            if parsed:
                sub, u, epoch, start = parsed
                out.append(Bucket(sub, u, epoch, start, start + bucket_seconds, os.path.relpath(p, root), 0))
                if progressed is not None:
                    progressed()
    return sorted(out, key=lambda b: (b.start, b.epoch))


# `{subsystem: [unit, ...]}` present on a resource, from the directory tree — the index's and the resource
# heartbeat's discovery, with no registry. Hidden directories (`.mirror`) are skipped; a missing root is
# `{}`. The console test asserts that after one mark the archive root shows `{"console": [<instance>]}` and
# nothing under `vms/1/`, proving a mark is the console's bucket, not a worker's.
def subsystems_under(root: str) -> dict[str, list[str]]:
    """{subsystem: [unit, ...]} present on a resource — the index's discovery, no registry."""
    out: dict[str, list[str]] = {}
    try:
        subs = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)) and not d.startswith("."))
    except FileNotFoundError:
        return out
    for sub in subs:
        units = sorted(u for u in os.listdir(os.path.join(root, sub)) if os.path.isdir(os.path.join(root, sub, u)))
        out[sub] = units
    return out


# ==================================================================================================
# Suppression — the writer's work, because the writer is the only one who sees the stream before it
# becomes a file.
# ==================================================================================================
# A storm of events is NORMAL, not a fault: a contact bouncing, a link flapping, a sensor re-reporting
# for as long as the thing it watches keeps happening. Nothing downstream can undo one — an index reads
# what is written, a timeline draws what it reads, and every reader that tried to collapse repeats would
# do it its own way and disagree with the others. The one place a repeat can be recognised BEFORE it costs anything is the
# process holding the unit's epoch, one line before `append`.
#
# Two things make suppression honest rather than a quiet loss of data:
#
#   1. The FIRST line of a window is written immediately and unchanged. Whatever the repeats are
#      worth, the first occurrence is the observation, and delaying it to batch it would trade the
#      one property an alarm has for a smaller file.
#   2. What was dropped is SAID. When the window closes, a summary line carries `repeats`, `since`
#      and `until`, so a quiet log and a suppressed storm are different things on the timeline.
#      Without it suppression is indistinguishable from nothing having happened, which is the failure
#      this whole module is built to avoid (`state`, `truncated`, `unreachable` — Lesson 13).
@dataclass(frozen=True)
class Suppress:
    """One kind's rule. `window` in seconds; `by` are the fields that, with the kind, say two lines
    are THE SAME THING — `None` means every field the line carries.

    Every-field is the default because it cannot be wrong: two lines collapse only when they are
    identical, so a contact that opens and then closes (`value` differs) is never one event, and the
    same reading reported twice is never two. A subsystem narrows it when a field drifts for reasons
    that are not a new observation — a score, a temperature, a counter."""
    kind: str
    window: float
    by: tuple[str, ...] | None = None


class Suppressor:
    """Per (unit, kind, identity) counters, held by the writer for as long as it holds the unit.

    Not a platform decision about what deserves suppressing: it applies the rules its subsystem
    declared and nothing else. A kind with no rule passes through untouched, which is what every
    subsystem gets until it says otherwise."""

    def __init__(self, rules: dict[str, Suppress] | None = None):
        self.rules = dict(rules or {})
        self.open: dict[tuple, list] = {}          # key -> [since, until, repeats, kind, first fields]

    # The identity of one line: the unit, the kind, and the values of the fields that decide sameness.
    # `None` when this kind has no rule — the caller writes it and asks nothing further.
    def key(self, unit: str, kind: str, fields: dict):
        rule = self.rules.get(kind)
        if rule is None:
            return None
        names = sorted(fields) if rule.by is None else sorted(rule.by)
        return (str(unit), kind, tuple((n, fields.get(n)) for n in names))

    # What to write for one observation, in order: `(t, kind, fields)` triples.
    #
    # Either one line (the observation, when nothing is being suppressed), or none (a repeat inside
    # an open window), or two (the window closed: the summary of what it swallowed, then this line as
    # the first of the new window). The summary comes FIRST because it happened first — a log read by
    # time must not put the report of a storm after the line that ended it.
    def lines(self, t: float, unit: str, kind: str, fields: dict) -> list[tuple[float, str, dict]]:
        k = self.key(unit, kind, fields)
        if k is None:
            return [(t, kind, dict(fields))]
        rule, state = self.rules[kind], self.open.get(k)
        if state is not None and t - state[0] < rule.window:
            state[1], state[2] = t, state[2] + 1                  # inside the window: counted, not written
            return []
        out = []
        if state is not None and state[2]:
            out.append(self._summary(k))
        self.open[k] = [t, t, 0, kind, dict(fields)]
        out.append((t, kind, dict(fields)))
        return out

    # Windows that have closed since the last call, as summaries — the lines nobody would otherwise
    # write, because the storm stopped and no observation came to close the window. Called once a
    # pass: without it a burst that ends is a burst nobody ever counted.
    def flush(self, t: float) -> list[tuple[str, float, str, dict]]:
        out = []
        for k, state in sorted(self.open.items(), key=lambda kv: kv[1][0]):
            if t - state[0] >= self.rules[state[3]].window:
                if state[2]:
                    out.append((k[0], *self._summary(k)))         # the unit too: the caller writes per unit
                del self.open[k]
        return out

    # `repeats` is how many were swallowed, `since`/`until` the bounds they fell between — the three
    # numbers an incident is reconstructed from. The fields are the FIRST line's of that window: with
    # every-field identity they are all of them, and with a narrowed `by` they are one concrete
    # example of what repeated.
    def _summary(self, k) -> tuple[float, str, dict]:
        since, until, repeats, kind, fields = self.open[k]
        return (until, kind, {**fields, "repeats": repeats, "since": since, "until": until})
