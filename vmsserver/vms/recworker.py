"""recworker — the fourth subsystem's worker: the only one placed on top of the archive.

A recorder is a worker in the platform's sense (a slot claimed by CAS —
`r-1` — an assignment read from the store, an epoch per unit, a heartbeat
with capacity and headroom) whose unit is ONE RECORDING of a camera,
`rec/recordings/<name>` — a camera written to two archives has two of them,
and the row's `cam` field says whose footage this one holds. It does not
hold the camera: it subscribes to the fan-out of whichever VMS worker does
(`live_url` in the VMS heartbeat, found the way a gateway finds it — never
by calling a worker, never a second connection to the camera) and writes
footage into the VOLUME it holds — a volume of ObjectStorage, through the
host's daemon `obsd` (`vms/archive.py`), as the stream `<name>/e<epoch>`.

The worker that holds the camera may be anywhere, `servers: shared`; the
recorder must be where its volume can be served — `requires: resource`,
one per volume — and when its server dies the controller moves its
recordings to a recorder that holds a volume. Footage from before the move
stays in the volume it was written to, under the old epoch; the console's
timeline merges the two.

    RECORDER_NAME / SLOT_INDEX     -> the slot to claim: r-<index>
    SERVER_NAME (or the hostname)  -> `server` in the heartbeat
    ARCHIVE                        -> this server's resource tree: where its EVENTS go (not its footage)
    OBSD_SOCKET                    -> the host's ObjectStorage daemon
    CAPACITY                       -> recordings this server's disks and NIC can take — its own number

Same class as the worker (`VmsWorker` over the `rec` rows): the same
reconciler, the same gate (an epoch per unit, a lease, the fence at the
slot), the same heartbeat. What differs is what the pipeline needs — a
source, not a camera — and a sink: the volume's one writer on this host.
"""
from __future__ import annotations

import contextlib
import logging
import os
import random
import socket
import threading
import time

from w2cplatform.console import framed, heartbeats
from w2cplatform.contract import Subsystem, is_live, read_hold
from w2cplatform.obsd import ObsdError, Sample, Session, Unavailable
from w2cplatform.sealing import Sealed, open_row
from w2cplatform.objects import ObjectStore
from w2cplatform.rows import FIELDS, PARSE_ERRORS, number
from w2cplatform.variables import Variables

from . import volumes
from .archive import Archive, ArchiveError, Fenced, classify, overlaps, stitch, subtract
from .config import rec_row
from .worker import FakeActuator, VmsWorker
from .writerwatch import WriterWatch


# The host in an instance's name, `host:pid:rnd` (`Worker.instance`'s default) — None for an instance named otherwise:
# an allocation's id says nothing about where it runs. What a network volume's hold follows the name by
# (`RecWorker.hold_follows_name`).
def host_of(instance: str) -> str | None:
    parts = str(instance or "").rsplit(":", 2)
    return parts[0] if len(parts) == 3 and parts[0] and parts[1].isdigit() else None


# …AND THE HOST IS THE BOX, NOT ITS NAME (the review's eighth pass, minor). It was `socket.gethostname()`: two boxes named
# alike — `localhost`, `fedora`, two clones of one VM — were "the same host", and the second instance took the first's
# network volume at once, its writer still mounted on the other box; the engine stopped the first (patch 07), with no
# wait to spare. The host part is `BOX_ID` when the runtime says it: systemd's machine id (`%m`, in the unit — a
# container's own hostname is not the box's: Quadlet's `Network=host` shares the network, not the UTS namespace),
# Nomad's node id (`${node.unique.id}`, in the job). Not said: the hostname, as before. And an allocation's id, which
# says no host, gets one only from `BOX_ID`: `<box>:<pid>:<alloc>` — still unique to the incarnation; without it the
# allocation's id alone, and the instance waits (the safe side).
def box_instance(env: dict, given: str | None = None) -> str:
    import uuid
    box, given = str(env.get("BOX_ID") or "").strip(), given or env.get("INSTANCE_ID") or ""
    if given:
        return f"{box}:{os.getpid()}:{given}" if box else given
    return f"{box or socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"


# What the domain's agent carries into THIS cluster about primaries recorded elsewhere (М12 Lesson 13), and
# where it says when it last reached the domain. Named here because the recorder is the reader; the agent writes.
PRIMARIES = "domain/primaries"
DOMAIN_SEEN = "domain/seen"

log = logging.getLogger("recworker")
REC = Subsystem("rec")


# ONE LOOK A PASS (the scaling pass). A question about ONE recording — who else records its camera, which backup holds
# it, who holds the camera, is the primary written — was answered by walking EVERYTHING: every recording's row (a list
# and a read each), every recorder's heartbeat, every VMS worker's. Asked once per recording, a pass cost the square of
# the recordings: measured at a thousand recordings and five hundred backups, one backfill pass read the store
# 3 032 003 times (112 s), one pass of the backups' gate 755 500 times (30 s), and the heartbeat of the recorder of the
# thousand 24 000 times — every holder's heartbeat, once per recording. Now a pass reads each of them ONCE, on first
# use, and answers every recording's question from maps — by camera, by recording, by holder: 1531, 1508 and 24 reads
# (`tests/test_recorder_reads.py`). What it read is the pass's: the next pass reads again, so nothing answered here is
# older than the pass that asks.
#
# A store that did not answer is the pass's too: each question raises what the one read raised — and is counted where
# it always was (`source` answers with `last_source`, the gate's part is skipped and counted) — and an outage is asked
# once, not once per recording.
class Look:
    """What one pass of a recorder read of the cluster, each part once: the recordings' rows, a subsystem's heartbeats,
    the standby volumes' names — and the maps a question about one recording is answered from."""

    # …and no older than a heartbeat's period, however long the pass: a backfill that spent minutes on one range asks the
    # next recording's sources of heartbeats read again, not of the ones read before the copy began.
    FRESH = 10.0

    def __init__(self, rec: "RecWorker"):
        self.rec, self._got, self._at = rec, {}, None

    def _once(self, part, read):
        now = getattr(self.rec, "clock", time.monotonic)()
        if self._at is None or now - self._at >= self.FRESH:
            self._got, self._at = {}, now
        if part not in self._got:
            try:
                self._got[part] = read()
            except OSError as e:
                self._got[part] = e
        got = self._got[part]
        if isinstance(got, OSError):
            raise got.with_traceback(None)
        return got

    # Every recording's row as stored, `[(name, items)]` — one list and one read each; parsed per use below.
    def _rows(self) -> list[tuple[str, dict]]:
        def read():
            out = []
            for key in self.rec.vars.list(self.rec.SUB.config(self.rec.ROWS, "")):
                items, _ = self.rec.vars.get(key)
                if items:
                    out.append((key.rsplit("/", 1)[1], items))
            return out
        return self._once("rows", read)

    # The rows parsed — and one that does not parse passed by (`Worker.row_garbled`; the sixth pass, the follow-up). The
    # deleted ones only when asked: a tombstone still says whose name it was and where its footage lives.
    def recordings(self, deleted: bool = False) -> list[dict]:
        def parse():
            out = []
            for name, items in self._rows():
                if not deleted and items.get("deleted") == "true":
                    continue
                try:
                    out.append(self.rec.parse_row(items))
                except (ValueError, KeyError, TypeError) as e:
                    self.rec.row_garbled(name, e)
            return out
        return self._once(("recordings", deleted), parse)

    def by_cam(self) -> dict[str, list[dict]]:
        """The recordings that stand, by camera: who else records the camera this recording is of."""
        def index():
            out: dict[str, list[dict]] = {}
            for r in self.recordings():
                out.setdefault(str(r["cam"]), []).append(r)
            return out
        return self._once("by_cam", index)

    def homes(self) -> dict[str, str]:
        """Each recording's volume, deleted ones too: the kind of a backup a heartbeat still names."""
        return self._once("homes", lambda: {str(r["id"]): str(r.get("home") or "") for r in self.recordings(deleted=True)})

    def backups(self) -> set[str]:
        return self._once("backups", lambda: volumes.backups(self.rec.vars))

    # The book of primaries the camera's agent carries home, and when it last reached the domain (`carried_primary`).
    def primaries(self) -> dict | None:
        return self._once("primaries", lambda: self.rec.vars.get(PRIMARIES)[0])

    def domain_seen(self) -> bytes | None:
        return self._once("domain_seen", lambda: self.rec.objects.get(DOMAIN_SEEN))

    def edges(self) -> set[str]:
        return self._once("edges", lambda: volumes.edges(self.rec.vars))

    def units(self, sub: str) -> dict[str, list[tuple[str, int, object, dict]]]:
        """Every status entry of a subsystem's heartbeats, by the unit it names: `[(worker, its place in that heartbeat,
        heartbeat, entry)]`, workers in name order — the order `holder_of` and the walks below went in. Whatever their
        age: liveness is the asker's, at its own `now`."""
        def index():
            out: dict[str, list] = {}
            for w, hb in sorted(heartbeats(self.rec.objects, sub + "/").items()):
                for i, st in enumerate(hb.status):
                    out.setdefault(str(st.get("id")), []).append((w, i, hb, st))
            return out
        return self._once(("units", sub), index)

    # `w2cplatform.console.holder_of` over the heartbeats read once: the first live worker, in name order, whose entry
    # for `unit` is in `phase` and has `field`.
    def holder(self, sub: str, unit, now: float, lost_after: float = 45.0, phase: str | None = None,
               field: str | None = None):
        for w, _, hb, st in self.units(sub).get(str(unit), ()):
            if not is_live(sub, hb.ts, now, lost_after):
                continue
            if phase is not None and st.get("phase") != phase:
                continue
            if field is not None and not st.get(field):
                continue
            return w, hb, st
        return None


# The passes that take one look: everything they ask is answered from it — and a pass inside a pass (`gate_pass` in
# `reconcile_once`) takes the outer one's.
def one_look(fn):
    import functools

    @functools.wraps(fn)
    def run(self, *a, **kw):
        with self.looking():
            return fn(self, *a, **kw)
    return run


# The look the pass of `rec` is taking on this thread — or, outside a pass, one of its own. `rec` needs only its two
# stores: М12's two-server tests run `carried_primary` over an object that has nothing else.
def look_of(rec) -> Look:
    return RecWorker._LOOKS.__dict__.get("by", {}).get(id(rec)) or Look(rec)


# What a recording's pipeline writes into: the volume's writer, under this recording's name and epoch. A
# sample the engine did not take raises, and the pipeline skips to the next key frame. A daemon that stopped
# answering is not an answer about the sample: the recorder is told, and remounts on its next pass (feedback CF).
#
# `store` is the recorder's CURRENT volume — a callable, asked on every sample — not the one open when the
# pipeline started. A remount replaces the `Archive`; a sink that kept the old one would write into a closed
# volume for as long as the pipeline ran, and nothing restarts a pipeline for a remount. Asked each time, the
# next key frame after a remount opens a sequence in the new writer, and the recording goes on.
#
# PER RECORDING, WHAT WAS LOST (the review's third pass). The writer watch counts the VOLUME: one camera of thirty
# whose group of pictures is larger than a block is refused every sample, never written at all, and the volume —
# landing what the other twenty-nine send — says `ok`. So the sink says what the engine answered for each of ITS
# samples to `tally(unit, status)`: `OK`, or why not — `SEQUENCE_TOO_LARGE`, `WRITER_STOPPED`, `UNAVAILABLE` (no
# volume, no daemon) — and `SEQUENCE_LOST`, taken but an earlier sequence of this stream lost. The recorder sums
# them per recording (`RecWorker._tally`): the status carries them, `/metrics` turns them into
# `rec_samples_refused_total{unit,status}`, and `last_frame_at` is the moment the writer last TOOK a frame.
class RecSink:
    def __init__(self, store, unit, epoch: int, on_lost=None, backfill: bool = False, on_wrong=None, tally=None):
        self.store_of = store if callable(store) else (lambda: store)
        self.unit, self.epoch, self.on_lost, self.backfill = str(unit), int(epoch), on_lost, backfill
        self.on_wrong = on_wrong                     # the volume refuses writes for good: told once per sample, acted on per pass
        self.tally = tally or (lambda unit, status: None)
        self.taken = self.refused = 0

    @property
    def store(self) -> Archive | None:
        return self.store_of()

    def put(self, sample: Sample) -> str:
        try:
            store = self.store_of()
            if store is None:
                raise Unavailable("PUT_MEDIA", "no volume open")
            st = store.put(self.unit, self.epoch, sample, self.backfill)
            self.taken += 1
            self.tally(self.unit, st)
            return st
        except Fenced as e:
            # The hold on a network volume unconfirmed (blocker 1, the fifth pass): nothing was sent and the engine is
            # not lost — the pass confirms the hold or lets the volume go, and a remount now would close the writer
            # onto a volume that may be somebody else's.
            self.refused += 1
            self.tally(self.unit, e.name)
            raise
        except Unavailable:
            self.tally(self.unit, "UNAVAILABLE")
            if self.on_lost is not None:
                self.on_lost()
            raise
        except ObsdError as e:
            self.refused += 1
            self.tally(self.unit, e.name)
            if e.name == "WRITER_STOPPED" and getattr(store, "lock_lost", False):
                pass                                 # the volume's lock is another writer's: the place lost, not the engine
            elif e.name == "WRITER_STOPPED" and self.on_lost is not None:
                self.on_lost()                       # the engine stopped this writer: a new one, on the next pass
            elif self.on_wrong is not None and classify(e).kind == "wrong":
                self.on_wrong(e)
            raise

    def finish(self) -> None:
        store = self.store_of()
        if store is None:
            return
        try:
            store.finish(self.unit, self.epoch, self.backfill)
        except ObsdError:
            pass


class RecWorker(VmsWorker):
    """A recorder: `VmsWorker` over `rec/recordings/*`, its pipelines fed by the
    worker's fan-out, writing into the volume it holds."""

    SUB = REC
    ROWS = "recordings"
    # How long a volume that refused writes is left alone before this recorder tries it again. Opening it
    # may well succeed — the directories are there — and the first write fail again, so without a pause a
    # recorder flaps between taking and dropping the same broken archive. Long enough not to flap, short
    # enough that a key somebody fixed is picked up without a restart.
    REFUSED_FOR = 600.0
    # How many closed ranges the heartbeat carries. A window and not a queue: the console acts on what it
    # sees, and a range that scrolled out was either acted on or is gone — which is why the console's
    # decision has to be idempotent on its own (it is: the job's id is the range).
    CLOSED_REPORTED = 32
    # How long a primary recording may be not written before a `when: offline` backup stands in for it
    # (Lesson 26). Every event-driven recording starts this way — a row appears, a pipeline takes a few
    # seconds — and waking the backup for each would make it record every event twice. The product's
    # number, from what a start takes on a real box.
    START_GRACE = 20.0
    # How long a released backup keeps writing after its primary is written again. The primary's first
    # minutes are not visible until their block closes, and "running" in a heartbeat comes before the first
    # frame on the volume; stopping the backup at that word would leave the seam between them to nobody. With a minute of
    # overlap the two archives overlap, and backfill finds the seam from both sides.
    HOLD_AFTER = 60.0
    # How old a recorder's heartbeat may be before what it said stops counting: the platform's `lost_after`.
    LOST_AFTER = 45.0
    # How much of the past a held backup keeps in memory (Lesson 26). When the primary is found missing the ring
    # is written first, so the backup's footage starts BEFORE the moment anybody noticed — and the ring must
    # reach back to the moment it stopped being written.
    #
    # THE PRIMARY'S SERVER DIES (the review's third pass). In one cluster, without М12's agent, nothing tells a
    # backup the stream broke: `stream_says` is a hook nothing in this package sets — `vms/__main__` does not,
    # only the domain's ingest does (М12, `domainvms/domain/ingest.py`) — so the book decides, and the book is
    # the primary's recorder's heartbeat. A server that loses power at T last heartbeated at most ten seconds
    # before, and that heartbeat stops counting at T + `LOST_AFTER` at the latest. Thirty seconds of ring, with
    # `START_GRACE` on top, began the backup's footage at T + 35.
    #
    # Two changes, and both are needed. A recorder that VANISHED — its last heartbeat said `running`, and it went
    # stale — gets no grace: the grace is for a recording that has not started yet, and this one was written
    # until its heartbeat stopped; the time it is "not written since" is that heartbeat's, not the moment we
    # noticed (`primary_needs_cover`). And the ring reaches past `LOST_AFTER`: that alone is longer than thirty
    # seconds. Sixty covers it, a pass and a keyframe — the product's number too. The price is memory: twice the
    # ring per held backup — at 4 Mbit/s 30 MB instead of 15, at 8 Mbit/s 60 MB; a recorder holding fifty
    # backups of 4-Mbit cameras holds 1.5 GB instead of 0.75. (Enlarging the ring instead of dropping the grace
    # would have needed 75 s — `LOST_AFTER`, the grace and a pass — for the same cover.)
    PREBUFFER = 60.0
    # MEMORY FIRST (feedback CB). A camera that pushes its own stream can CONTINUE it after a break: its ingest
    # says how far the recording got (`have`) and the camera sends the rest from memory (`CameraPusher`). For such
    # a stream the card need not start the moment the break is noticed — a ten-second Wi-Fi drop would write
    # the card and then be backfilled from it, every time, and wear the card out for breaks that ended before
    # anybody noticed them. So the release WAITS: the ring minus how late a break is noticed minus a margin.
    # A stream that comes back sooner leaves the card untouched; a longer break releases the ring, which still
    # reaches back past the break's start. Where nobody can continue the stream (a camera a server pulls over
    # RTSP), there is nothing to wait for, and the card writes at once, as before.
    DETECTION = 10.0                                 # how late a break is noticed: the pusher's poll, a pass
    DEFER_MARGIN = 5.0                               # a keyframe and a pass of the gate
    # How much of a break the CAMERA keeps to continue from (`CameraPusher.hold_seconds`, М12): the deferral is
    # bounded by it, not by our ring — a break that ends while the card still waits is in the camera's memory
    # ONLY, and a wait longer than that memory loses the break's beginning. It was the ring's length while both
    # were thirty seconds; the ring grew for a dead server, and the camera's memory did not.
    CONTINUE_REACH = 30.0
    # A break that ended before the card wrote leaves the ring KEPT this much longer (the product's `KeepGrace`): the
    # camera's pusher is still taking the break out of it (`_keep`).
    KEEP_GRACE = 10.0
    # How old the agent's last contact with the domain may be before the book of primaries it carried stops
    # counting (М12 Lesson 13). The same 45 s a heartbeat gets: past it, the backup cannot know whether the
    # primary in the other cluster is written, and records.
    CARRIED_LOST_AFTER = 45.0
    # A RANGE IS LANDED IN PIECES (the review's third pass, blocker 6). A fetched range was one request and one list:
    # a day of backfill from a backup is some forty gigabytes, in the memory of both recorders at once — both died
    # of it, the request stayed, and after the restart it all began again. Whatever is copied — a gap from a device
    # or a backup, a keep — is asked for about a minute at a time and landed before the next minute is asked for
    # (`_pieces`). And one pass takes at most `RANGE_CAP` of one range: an operator's request for a day is served
    # ten minutes a pass, the rest on the passes after (`requests`), the way a planned gap is (`backfill`).
    PIECE = 60.0
    RANGE_CAP = 600.0
    SLOT_PREFIX, NAME_ENV = "r", "RECORDER_NAME"
    parse_row = staticmethod(rec_row)

    def __init__(self, name: str | None, vars_: Variables, objects: ObjectStore, actuator=None,
                 lease_ttl: float = 30.0, lease_margin: float = 5.0, clock=time.monotonic, wall=time.time,
                 server: str | None = None, capacity: int | None = None, instance: str | None = None, slot_ttl: float = 45.0,
                 env: dict | None = None, archive_root: str | None = None, obsd: Session | None = None,
                 default_quota: int | None = None,
                 window: tuple[int, int] | None = None, keep_days: float = 30.0, settle: float = 900.0,
                 stitch: float = 2.0, block: int | None = None, read: int | None = None):
        env = dict(os.environ if env is None else env)
        events_root = archive_root or env.get("ARCHIVE", "/data/archive")
        instance = instance or box_instance(env)          # the box it runs on, by `BOX_ID` (`hold_follows_name`)
        super().__init__(name, vars_, objects, actuator or FakeActuator(), lease_ttl, lease_margin, clock, wall, server, capacity, instance,
                         slot_ttl, archive_root=events_root, env=env)
        # The host's ObjectStorage daemon, and this process's one session with it. Every volume this recorder
        # opens, every writer, every reader is a handle of THIS session — a token the daemon knows it by.
        #
        # Every call waits at most `OBSD_TIMEOUT` — ten seconds, a third of a lease. The calls a pass makes run on
        # the thread that renews the leases, and a daemon that took a request and went quiet would otherwise hold
        # that thread past the lease: the recorder fenced, every recording stopped, for one silent daemon. Silent
        # is `away` (`ArchiveError`): the volume is kept, the pass goes on, the next one asks again.
        self.session = obsd or Session(client=f"rec-{self.name}", timeout=float(env.get("OBSD_TIMEOUT", "10")))
        self.block, self.read = block, read           # how a volume this recorder formats is cut (`vms/archive.py`)
        # …and how often the engine refreshes a new volume's write lock (`lockRefreshSec`; 0: the engine's 30 s). After
        # a daemon that CRASHED, a volume it held stays locked until that lock is stale: `busy` for up to a minute.
        self.lock_refresh = int(env.get("ARCHIVE_LOCK_REFRESH_S", "0") or 0)
        # How soon written is visible (feedback CP): the writer's two flush periods, `WRITER_CONFIGURE`d at every open.
        from .archive import BLOCK_FLUSH_S, SEQUENCE_FLUSH_MS
        self.sequence_flush_ms = int(env.get("SEQUENCE_FLUSH_MS", SEQUENCE_FLUSH_MS))
        self.block_flush_s = int(env.get("BLOCK_FLUSH_S", BLOCK_FLUSH_S))
        # WHICH VOLUME THIS RECORDER WRITES INTO — its place, in the sense `place_by: volume` means. Three
        # ways to be told, in this order:
        #
        # `$VOLUME` — PINNED. A disk is bolted to one machine, so the unit file that knows which disk this
        # instance mounts is the right place to say so, the way `$RECORDER_NAME` says which slot it is.
        # A pinned DISK takes no hold: nobody else can write it. A pinned volume any box may serve takes the hold,
        # the fence and the wait an unpinned recorder does (the review's seventh pass, blocker 2): pinning says WHICH
        # volume this recorder writes, and never that nobody else may — a free recorder on another box saw it unheld,
        # took it and mounted it, and the pinned one's footage went on into a writer the engine had stopped.
        #
        # Nothing pinned and volumes DECLARED (`rec/volumes/*`) — the recorder takes one, by CAS, and is
        # that volume's recorder until it stops or lapses (`volume_pass`). This is what makes a network
        # archive created on the console get served without anybody starting a process for it.
        #
        # Nothing pinned and nothing declared — the SERVER's own volume, named after the server: what every
        # single-disk box meant before any of this existed — one place, `home: srv-a` still true, `place_by:
        # volume` behaving exactly like `place_by: server`. It lives BESIDE the resource's tree, not in it —
        # `/data/volume` next to `/data/archive`: inside, the resource's walks would take the ring for a
        # subsystem, count its blocks as the tree's usage and mirror nothing of it (`ARCHIVE_VOLUME` to put it
        # elsewhere).
        self.pinned = bool(env.get("VOLUME"))
        self.pin = str(env.get("VOLUME") or "")      # …its name, which `volume` is not while the hold is another's
        self.volume_wait = ""                        # pinned, and waiting for the hold: why (`_wait_for_pin`)
        self.default_volume = str(self.server or "default")
        beside = os.path.join(os.path.dirname(os.path.abspath(events_root)), "volume")
        self.default_url = env.get("ARCHIVE_VOLUME") or f"file://{beside}"
        # Its size when it is new: `ARCHIVE_QUOTA_BYTES`, or — 0 — a share of the disk it will be on, which the DAEMON
        # measures when it formats it (`_share_of_space`; the review's fourth pass: measured here, it was the
        # container's own disk, not the data disk `/data/volume` is on).
        self.default_quota = default_quota if default_quota is not None else int(env.get("ARCHIVE_QUOTA_BYTES", "0") or 0)
        self.volume = str(env.get("VOLUME") or self.default_volume)
        self.store: Archive | None = None            # the volume open for writing, if one is
        self.full_capacity = self.capacity           # what it reports while it has a place to record in
        self.volume_error = ""                       # why the volume it holds will not open, if it will not
        # Why the volume it DID open has stopped taking samples, and since when. Not `volume_error`: that one
        # means "will not open" and costs the volume its capacity; this one means "opened, then went away" —
        # the daemon stopped answering, the bucket's network is down — and the answer to it is to try again.
        self.archive_error, self.archive_away_since = "", 0.0
        self.archive_failure = ""                    # "away" or "wrong" while archive_error is set
        self.engine_lost = False                     # a sink found the daemon gone: remount on the next pass
        # What the last remount after a lost engine was, and how many there were: `archive_error` says the outage
        # while it lasts and clears when the volume is open again, and this is what is left to say afterwards.
        self.remounts, self.remounted = 0, {}
        self._lost_why, self._lost_at = "", 0.0      # why, and since when, the engine is lost (`_lost_engine`)
        self._taken_over = ""                        # …or the volume's lock was another writer's: said till, and at, the remount
        self._vol_last = None                        # the volume row last opened: what a silent store remounts by
        self._vol_unread = None                      # (since, alarm said at) while the held volume's row does not parse
        self._volume_garbled_said = ""               # the last row trouble the volume step logged (`lease_pass`), said once
        self.refused: dict[str, tuple[float, str]] = {}   # volume -> (tried again after, why) — see REFUSED_FOR
        self._backfiller: threading.Thread | None = None
        # Is the WRITER writing (Lesson 10, feedback U): bytes offered to the sinks against what the volume
        # took — the ring's own count, `totalWritten`, from when this recorder opened it.
        self.writer = WriterWatch()
        self._written_at_open = 0
        self._landed_before = 0                      # what landed under writers this recorder already closed: the count goes on
        self._landed = 0
        # Backfill (Lesson 16): the hours in local time it may run in (None: any), how far back it may
        # reach, how fresh it must NOT touch, and the seam tolerance that stops 144 seams a day from
        # looking like 144 gaps.
        self.window, self.keep_days, self.settle, self.stitch = window, keep_days, settle, stitch
        self.backfill_budget = 0                    # ranges per pass; 0 = only what an operator asks for
        self.backfilled = 0
        self.fetched: list[str] = []                # request ids this worker has fetched — the heartbeat carries them
        self.behind_loopback: dict = {}             # camera -> the server whose fan-out is bound to loopback, and is not ours
        self.depths: dict = {}                      # recording -> days of footage it has here (`depth_pass`)
        self.shallow: dict = {}                     # recording -> when its `archive.shallow` alarm was last raised
        self._depth_at = -1e18
        self._shared: set = set()                   # the declared volumes any box may serve, as last read
        self._hold_confirmed = self.clock()          # when the store last said the hold is ours (`renew_hold`, `claim_hold`)
        # Volumes any box may serve that THIS recorder does not take, and why: its host's engine cannot give a volume
        # up (`_engine_refuses`). In the heartbeat with `refused`, and on the volumes page (`volumes.served`).
        self.unservable: dict[str, str] = {}
        # Since when the host's engine has answered nothing under a volume any box may serve (`_hear_engine`, `_away`);
        # None while it answers. What the hold on such a volume is given up by (`ENGINE_SILENT_FOR`).
        self._engine_silent_since: float | None = None
        self.dropped_seconds = 0.0                   # footage writers given up had taken and not written (`_say_dropped`)
        self._own_lock_since = 0.0                   # since when mounts answer ALREADY_LOCKED under our own owner
        self._own_lock_left = False                  # …and a session was already left behind for it (`_own_lock`)
        self._lock_theirs = False                    # …and it is still there: another process's, not an orphan of ours
        self._busy_since = 0.0                       # since when the volume held has been `busy` at every mount (`BUSY_FOR`)
        self._requested: dict[str, float] = {}       # request id -> how far it has been served (`RANGE_CAP` a pass)
        self.default_size = 0                        # the box's own volume's real size, once it was opened
        self.quota_note = ""                         # a smaller quota declared and not applied: said, not done
        self.shrink_pending = 0                      # …the same, as data: the size declared and waiting for its second word
        self.resize_error = ""                       # the engine refused the new size: said, and asked again next pass
        self.fed: dict = {}                         # recording -> (bytes offered, when that last grew)
        self.running_since: dict = {}               # recording -> when this recorder first saw it running, this time
        # What the engine answered for each recording's samples (`RecSink.tally`): `{recording: {status: n}}` for
        # every answer but `OK`, and when the writer last TOOK one of its samples. Written on the pipelines'
        # streaming threads, read by the heartbeat: under a lock.
        self.samples_lost: dict[str, dict[str, int]] = {}
        self.taken_at: dict[str, float] = {}
        self._tally_lock = threading.Lock()
        self.written_through: dict = {}             # recording -> capture time of the last frame its sink took (`note_written`)
        self._epoch_at: dict[str, float] = {}       # recording -> when its epoch was taken, by the wall (`_held_since`)
        self._cover_since: dict = {}                # held backup -> when its primary was first found needing cover (CB)
        self._kept_until: dict = {}                 # held backup -> its ring stays kept until then: a break over without the card
        self._source_asks: dict[str, tuple[int, float]] = {}   # a source that failed a range -> (times in a row, not asked before)
        self.closed: list[str] = []                 # ranges fetched from a device or a backup: `<unit>|<from>|<to>`, for the console
        # What a clean fetch was asked for and did not get, per (recording, source) — the source does not
        # have it either (Lesson 16, the feedback's P). A summary in a heartbeat says where a card starts and
        # ends, never where its holes are; without this the same empty range is planned every pass, and each
        # plan opens one of the device's one or two sessions.
        self.nowhere: dict[tuple[str, str], list[tuple[float, float]]] = {}
        # What a source DELIVERED that our volume does not show yet (feedback AE): a reader sees a block only
        # once it is closed, so a range just copied shows minutes later. Until it does, the range is ours —
        # neither a hole to copy again nor, worse, something the source did not have.
        self.landing: dict[str, list[tuple[float, float]]] = {}
        # What the ENGINE refused of what a source delivered (`_land`): how many times each piece — (recording,
        # source, span rounded to the stitch tolerance) — and, after `REFUSED_TIMES`, the pieces given up per
        # (recording, source), planned no more, like `nowhere` (the review's fourth pass, an open item; the product's DD).
        self.refusals: dict[tuple[str, str, int, int], tuple[int, float, float]] = {}   # piece -> (times, its span)
        self.given_up: dict[tuple[str, str], list[tuple[float, float]]] = {}
        self.archive_url = ""                       # this recorder's archive door, once served (Lesson 26)
        self._rows_seen: dict[str, dict | None] = {}   # recording -> its row as last read, for the door (`_visible_from`)
        self._not_written_since: dict[str, float] = {}   # primary recording -> since when nobody writes it
        self.holding: dict[str, bool] = {}          # `when: offline` recording -> is its pipeline on hold now
        self._primary_back_since: dict[str, float] = {}  # released backup -> since when its primary is written again
        # KEEPS (feedback BH): a recorder holding an INCIDENTS volume copies into it what somebody said to keep
        # (`keep_pass`). What each keep holds there, as last seen, and what the last pass found.
        self.incidents = False                       # is the volume this recorder holds an incidents volume
        self.keep_held: dict[tuple[str, str], float] = {}   # (keep, recording) -> seconds of it in the volume
        self.keep_state: dict[str, dict] = {}        # keep -> {copied, missing, sha256}: for the heartbeat
        self._keeps_read = False                     # `keep_held` restored from the volume and its events (`keep_pass`)
        self._keep_short: dict[str, tuple] = {}      # keep -> (short since, last `archive.keep.uncopied`) — `_keep_uncopied`
        self._keep_garbled: dict[str, tuple] = {}    # keep -> (garbled since, last `archive.keep.garbled`) — `_keep_unreadable`
        self._keep_nowhere: dict[tuple[str, str], list] = {}   # (keep, recording) -> what a door that holds it said it has not
        self._keeper: threading.Thread | None = None
        self._keep_at = -1e18
        self.waiting: set[str] = set()                                        # units with nobody holding their camera
        self.sources: dict[str, str] = {}                                     # what each running pipeline subscribed to
        self._offered_seen: dict[str, int] = {}                               # per pipeline: the actuator's counter as last read
        self._offered_total = 0                                               # …summed by DELTAS, so a pipeline that stops takes nothing back
        self._offered_extra = 0                                               # what this process wrote into the writer itself: fetched ranges, keeps
        self.last_source: dict[str, tuple[str, str]] = {}                     # camera -> (server, source) read last: the answer while the store is away

    # A volume nobody declared, on a disk nobody measured: four fifths of what is free, leaving two gigabytes —
    # the product's rule (feedback BM) — and never so much that the disk ends above the watermark's low mark
    # (`space_settings`, 0.75 by default) once the ring is full. The disk is shared with the resource's events,
    # and a ring that filled it past the mark would leave the watermark short for good: nothing of the VMS's
    # answers `free` any more. At least a gigabyte, whatever the arithmetic says. Asked once, when it is first
    # formatted; a volume that exists keeps the size it has.
    #
    # Of the disk as the DAEMON sees it — `VOLUME_SPACE` of the volume's directory (`Archive.space_where`), not
    # `statvfs` here (the review's fourth pass): in the recorder's container the volume's directory is not mounted,
    # and what was measured was the container's root. Nothing to measure — a bucket, a daemon that cannot see the
    # path — is no size: the volume is not formatted, and its status says why.
    @staticmethod
    def _share_of_space(space: dict, low: float = 0.75) -> int:
        free, total = int(space.get("available") or 0), int(space.get("capacity") or 0)
        if not total:
            return 0
        used = total - int(space.get("free") or free)
        return max(1 << 30, min(int(free * 0.8), free - (2 << 30), int(total * low) - used))

    # -- where a camera's stream is: the VMS heartbeat, never a call to the worker ------------------
    def source(self, cam) -> tuple[str, str] | None:
        """`(server, source)` of the worker holding the camera, from its heartbeat; None if nobody does.
        The source is the worker's shared-memory branch (`live_shm`, shm://…) when that worker is on
        THIS server — the same bytes with no RTSP hop, no fan-out process on the recording path — and
        its RTSP fan-out (`live_url`) otherwise."""
        # The store that does not answer says nothing — not "nobody holds it". A recorder whose camera's pipeline
        # fell over during the outage restarts it on the source it read last (the review's second pass, blocker 4:
        # the camera's worker is still there; what is away is the book). A camera never read stays unstartable.
        try:
            found = self._look().holder("vms", cam, self.wall(), phase="running", field="live_url")
        except OSError as e:
            self.store_errors += 1
            last = self.last_source.get(str(cam))
            log.warning("%s: the store did not answer for camera %s's holder (%s): %s", self.name, cam, e,
                        f"its last source {last[1]} stands" if last else "and it was never read")
            return last
        if found is None:
            self.last_source.pop(str(cam), None)
            return None
        _, hb, st = found
        server = hb.extra.get("server", "?")
        if server == self.server and st.get("live_shm"):
            self.last_source[str(cam)] = (server, st["live_shm"])
            return server, st["live_shm"]
        from .config import local_only
        if local_only(st["live_url"], server, self.server):
            # Announced truthfully and not for us: the fan-out is bound to loopback on ANOTHER server. Going to
            # that address would be knocking on our own machine. Said in the status, so the operator reads
            # "open RTSP_HOST on srv-b" instead of "camera held by nobody".
            self.behind_loopback[str(cam)] = server
            return None
        self.behind_loopback.pop(str(cam), None)
        self.last_source[str(cam)] = (server, st["live_url"])
        return server, st["live_url"]

    # A recording's pipeline needs a source — `rtspsrc location=<live_url>`, or the worker's shared memory — and a
    # sink: this volume's writer, under this recorder's epoch. No source (the camera is held by nobody yet) means "cannot start now": the
    # reconciler backs off and retries, and the status says `waiting`.
    def enrich(self, cam: dict) -> dict | None:
        # Two identities, and this is the one method where both are used in three lines: `cam["cam"]` is
        # WHOSE fan-out to subscribe to, `cam["id"]` is WHICH recording is subscribing. They were the same
        # string while the spec said `id: cam`; they stopped being it, and nothing here changed.
        src = self.source(cam["cam"])
        if src is None:
            self.waiting.add(cam["id"])
            return None
        if self.store is None or self.store.writer is None:
            self.waiting.add(cam["id"])
            return None                                  # no volume open to write into: the reconciler retries
        self.waiting.discard(cam["id"])
        self.sources[cam["id"]] = src[1]
        # The sink: this volume's writer, as the stream `<recording>/e<epoch>`. The epoch is in the stream's
        # NAME — a fenced writer and its successor write two streams, and nothing is overwritten.
        out = dict(cam, source=src[1], source_server=src[0], via="shm" if src[1].startswith("shm://") else "rtsp",
                   sink=RecSink(lambda: self.store, cam["id"], cam.get("epoch", 0), on_lost=self._lost_engine,
                                on_wrong=self._volume_refuses, tally=self._tally))
        # A `when: offline` backup runs ON HOLD while its primary is written: the pipeline is up, subscribed,
        # and recording into a ring in memory, writing nothing (Lesson 26).
        if self._offline_backup(cam):
            hold = not self.primary_needs_cover(cam)
            self.holding[str(cam["id"])] = hold
            out.update(hold=hold, ring_seconds=self.PREBUFFER, now=self.wall())
        return out

    # A source this recorder cannot reach — the pipeline could not open the camera's stream (М12 lesson 16): said
    # in the heartbeat, per recording, so the domain can stop sending it to pull what it cannot reach and have
    # the camera push instead. The pipeline's own failure is the only witness; whoever runs it calls this.
    def note_source_unreachable(self, unit, reason: str | None) -> None:
        if not hasattr(self, "unreachable_sources"):
            self.unreachable_sources = {}
        if reason is None:
            self.unreachable_sources.pop(str(unit), None)
        else:
            self.unreachable_sources[str(unit)] = reason

    # How far the recording GOT (feedback CB): the capture time, on this cluster's clock, of the last frame the
    # sink took. Said in the heartbeat as `written_through`, and read by the ingest a camera pushes to — it is the
    # `have` a camera continues after, after a break. Written, not received: frames a recorder's queue dropped
    # are frames the camera must send again, and only the writer knows which those were. The pipeline's sink
    # calls this (a pad probe on a real box); the tests do.
    def note_written(self, unit, capture_t: float) -> None:
        self.written_through[str(unit)] = max(float(capture_t), self.written_through.get(str(unit), float("-inf")))

    # One answer of the engine about one of a recording's samples (`RecSink.tally`).
    def _tally(self, unit, status: str) -> None:
        with self._tally_lock:
            if status == "OK" or status == "SEQUENCE_LOST":
                self.taken_at[str(unit)] = self.wall()
            if status != "OK":
                lost = self.samples_lost.setdefault(str(unit), {})
                lost[status] = lost.get(status, 0) + 1

    # When the recording last got a frame onto the volume: the writer's last TAKE — not the last frame offered to
    # the sink, which a refusing engine leaves fresh for ever (the review's third pass). A recording that has
    # taken nothing since it started is counted from its start, so its age grows from there. None: nothing
    # measures this recording — no sink took anything and the actuator counts nothing.
    def last_frame_at(self, uid) -> float | None:
        key = str(uid)
        with self._tally_lock:
            taken = self.taken_at.get(key)
        since = self.running_since.get(uid, self.running_since.get(key))
        if since is None:
            return taken
        if taken is None:
            return since if uid in self.fed or key in self.fed else None
        return max(taken, since)

    def status_extra(self, cam: dict) -> dict:
        src = self.source(cam["cam"])
        out = {"cam": str(cam["cam"]), "source": src[1] if src else None, "via": (None if src is None else "shm" if src[1].startswith("shm://") else "rtsp")}
        if cam["id"] in self.waiting and cam["id"] not in self.reconciler.actual:
            out["why"] = "camera held by nobody"
            if str(cam["cam"]) in self.behind_loopback:
                out["why"] = (f"the camera's stream is served on loopback on {self.behind_loopback[str(cam['cam'])]}: "
                              f"not reachable from {self.server} (RTSP_HOST there)")
        why = getattr(self, "unreachable_sources", {}).get(str(cam["id"]))
        if why:
            out.update(source_unreachable=True, why=f"source unreachable: {why}")
        last = self.last_frame_at(cam["id"])
        if last is not None:
            out["last_frame_at"] = last
        with self._tally_lock:
            lost = dict(self.samples_lost.get(str(cam["id"]), {}))
        if lost:
            out["samples_refused"] = lost                # cumulative since this process started, per engine answer
        if str(cam["id"]) in self.written_through:
            out["written_through"] = self.written_through[str(cam["id"])]
        if str(cam["id"]) in self.depths:
            out["depth_days"] = self.depths[str(cam["id"])]
            if str(cam["id"]) in self.shallow:
                out["shallow"] = True
        # A BACKUP recording says what it holds, the way Lesson 15's holder says what a card holds: a
        # summary, cheap to carry in every heartbeat. The primary plans from it, and what it copies is what the
        # backup's door hands over (Lesson 26).
        if volumes.is_backup(cam, names=self._look().backups()):
            ours = self.our_coverage(cam["id"])
            if ours:
                out["coverage"] = {"from": ours[0][0], "to": ours[-1][1], "fragments": len(ours)}
        return out

    @one_look
    def status(self) -> list[dict]:
        out = super().status()
        for st in out:
            if st["phase"] != "running" and st["id"] in self.waiting and st["enabled"]:
                st["phase"] = "waiting"
            if st["phase"] == "running" and self.holding.get(str(st["id"])):
                st["phase"], st["why"] = "standby", (f"the primary recording is being written; the last "
                                                     f"{self.prebuffered(st['id']):.0f} s are held in memory")
                if str(st["id"]) in self._cover_since:
                    st["why"] = (f"the stream broke {self.wall() - self._cover_since[str(st['id'])]:.0f} s ago; held in "
                                 f"memory for {self.defer_for():.0f} s before the card writes — the camera may continue it")
        return out

    # STOPPED DURING A BREAK (feedback CB). A held ring inside its deferral is the ONLY copy of the break: the
    # stream has not come back and the card has not written. Stopped the old way — dropped — it is gone, which was
    # right for "the primary is written and we hold for nothing" and is wrong for "it broke and we are waiting".
    # So it is written first, then stopped.
    def _release_if_broken(self, uid) -> None:
        key = str(uid)
        if self.holding.get(key) and key in self._cover_since:
            if self.actuator("release", {"id": uid, "now": self.wall()}):
                log.warning("%s: %s stopped during a break — the ring held in memory is written to the card first",
                            self.name, key)
            self.holding[key] = False
            self._cover_since.pop(key, None)

    def _actuate(self, verb: str, cam: dict) -> bool:
        if verb == "stop":
            self._release_if_broken(cam["id"])
        return super()._actuate(verb, cam)

    # An orderly stop goes through `stop_all`, past `_actuate`: the rings held through a break are written first here
    # (the review's second pass) — the ring is the only copy of the break, and the restart would not have it.
    def before_stop_all(self) -> None:
        for uid in list(self.reconciler.actual):
            self._release_if_broken(uid)

    # -- a backup that records only for a primary that is down (Lesson 26) -----------------------------
    # `when: offline` on a backup recording: record only while the camera's PRIMARY recording should be
    # written and is not. "Should be" is the whole rule, and the feedback's point S is why: a primary that is
    # switched off, or an event recording whose event has ended, is nobody's failure — standing in for it
    # would turn a recording on events into a recording always, on the backup's disk and, for a card, over
    # the camera's uplink. What is covered is a failure, never a decision.
    #
    # The backup's pipeline does not wait to be started: it runs on hold, a ring of the last `PREBUFFER`
    # seconds in memory, and the gate below opens and closes it. Starting it only when the primary is found
    # missing would lose exactly the seconds before that — the grace, the pass, the pipeline's own start —
    # which are the seconds the failure happened in.
    def _offline_backup(self, row: dict) -> bool:
        return str(row.get("when") or "") == "offline" and volumes.is_backup(row, names=self._look().backups())

    # One pass of the gate, after the reconciler's. A held backup whose primary now needs cover is RELEASED:
    # the ring is written first, then live. A released one whose primary has been back for `HOLD_AFTER` is
    # put on hold again — a restart under the same epoch, so its open sequence is finished, and the ring
    # starts filling afresh.
    @one_look
    def gate_pass(self, now: float | None = None) -> list[tuple[str, str]]:
        now = self.wall() if now is None else now
        done = []
        running = {str(u) for u in self.reconciler.actual}       # once, not once per row (the scaling pass)
        for row in self.rows:
            uid = str(row["id"])
            if not self._offline_backup(row) or uid not in running:
                continue
            need = self.primary_needs_cover(row, now)
            if need:
                self._primary_back_since.pop(uid, None)
            # Deferred only when the STREAM reported the break: a break the book reports is reported `START_GRACE`
            # late, and the deferral on top of it would reach past the ring — the start of the break gone, which is
            # what the ring is for (the review's second pass).
            by_stream = self.stream_says is not None and self.stream_says(row) is True
            if need and by_stream and self.holding.get(uid) and self.resumes is not None and self.resumes(row):
                since = self._cover_since.setdefault(uid, now)
                if now - since < self.defer_for():
                    self._keep(uid, True)                    # the break stays in the ring, not let go by its window
                    self._kept_until.pop(uid, None)
                    continue                                 # held in memory: the camera may yet continue the stream
            if not need and uid in self._cover_since:
                self._cover_since.pop(uid, None)            # back before the card had to write: nothing written (CB)
                self._kept_until[uid] = now + self.KEEP_GRACE
                done.append((uid, "back from memory"))
            if uid in self._kept_until and now >= self._kept_until[uid]:
                self._kept_until.pop(uid, None)
                self._keep(uid, False)
            if need and self.holding.get(uid):
                held = self.prebuffered(uid)                 # what the ring holds as it is released: the log says THAT
                if self.actuator("release", {"id": row["id"], "now": now}):
                    self.holding[uid] = False
                    self._cover_since.pop(uid, None)
                    self._kept_until.pop(uid, None)
                    self._keep(uid, False)                   # released: what the kept ring held goes to the card first
                    done.append((uid, "released"))
                    log.warning("%s: the primary of %s is not being written — recording from %.0f s ago",
                                self.name, uid, held)
            elif not need and self.holding.get(uid) is False:
                back = self._primary_back_since.setdefault(uid, now)
                if now - back >= self.HOLD_AFTER and self._actuate("restart", row):
                    self._primary_back_since.pop(uid, None)
                    done.append((uid, "held"))
        return done

    # What the STREAM itself says, when it can say it — first, before any book (М11 lesson 1, two servers). A
    # standby whose stream comes only when the primary does not take it (a backup fed by a camera that pushes:
    # the camera came here) knows at once; so does the card of a camera that did not hand its stream to its
    # primary; so does a backup that watches the primary's recorder on the site's LAN. None: it cannot say —
    # decide by the book, as before. The domain is not on this path: it may be the thing that died.
    stream_says = None                                   # (row) -> bool | None, set by whoever runs this recorder
    # Whether the stream this backup stands in for can be CONTINUED from memory after a break (feedback CB): a
    # camera that pushes it, and says how far its ingest got. Set by whoever runs this recorder, like the above.
    resumes = None                                       # (row) -> bool

    def defer_for(self) -> float:
        return max(0.0, min(self.PREBUFFER, self.CONTINUE_REACH) - self.DETECTION - self.DEFER_MARGIN)

    # What a held backup holds in memory NOW, in seconds — what its status says, and what the log says a release
    # began from. A server's pipeline holds the ring it was started with; the camera's card says what its ring really
    # holds, which at an ordinary bitrate is less than its window (`CardRecorder.prebuffered`; the review's sixth pass).
    def prebuffered(self, uid=None) -> float:
        return self.PREBUFFER

    # A KEPT ring (feedback CB; the product's `Keeper`): while a break is held in memory the ring lets go of nothing by
    # its window, and what it must let go of past its byte ceiling goes to the card instead of being dropped. Only an
    # actuator that can keep is asked — the camera's card (`vms/card.py`, `CardActuator.keep`); a server's pipeline
    # holds its ring in a GStreamer queue and has no such mode. The ring is kept BY THIS RECORDING — two recordings on
    # one card keep and let go apart — and after a release the actuator lets the ring go when its writer has taken
    # it, not at the gate's word, which comes in the same pass as the release (the review's sixth pass).
    def _keep(self, uid, keep: bool) -> None:
        keeper = getattr(self.actuator, "keep", None)
        if keeper is not None:
            keeper(uid, keep)

    def primary_needs_cover(self, row: dict, now: float | None = None) -> bool:
        now = self.wall() if now is None else now
        said = self.stream_says(row) if self.stream_says is not None else None
        if said is not None:
            return bool(said)
        carried = self.carried_primary(row, now)
        if carried is not None:
            return carried
        look = self._look()
        names = look.backups()
        units = look.units(self.SUB.name)
        need = False
        # The camera's other recordings from the pass's map by camera, and what the recorders say of each from its map
        # by recording (the scaling pass): every row and every recorder's heartbeat were read again for each backup.
        for other in look.by_cam().get(str(row["cam"]), ()):
            if str(other["id"]) == str(row["id"]) or volumes.is_backup(other, names=names):
                continue
            # Running in a LIVE heartbeat (`is_live`: a clock from the future does not keep a dead recorder alive — the
            # review's second pass, M9), and — the third pass — running in one that went stale not long ago: a recorder
            # that VANISHED. Its recordings were written until its last heartbeat, so that is when "not written" began,
            # and the grace for a start does not apply; past the grace, the rule below covers it anyway.
            said = [hb.ts for _, _, hb, st in units.get(str(other["id"]), ()) if st.get("phase") == "running"]
            running = any(is_live(self.SUB.name, ts, now, self.LOST_AFTER) for ts in said)
            gone = [ts for ts in said if not is_live(self.SUB.name, ts, now, self.LOST_AFTER)
                    and now - ts <= self.LOST_AFTER + self.START_GRACE]
            until = float(other.get("until") or 0)
            should = bool(other.get("enabled")) and (until == 0 or until > now)
            if not should or running:
                self._not_written_since.pop(str(other["id"]), None)
                continue
            since = self._not_written_since.setdefault(str(other["id"]), min(now, max(gone) if gone else now))
            need = need or now - since >= self.START_GRACE
        return need

    # -- a primary in ANOTHER cluster (М12 Lesson 13) --------------------------------------------------------
    # The rule above looks for the primary in this cluster's rows and this cluster's heartbeats. A camera
    # that is a cluster of its own, recorded by a server room, has neither: its primary is a row of the
    # room's cluster, written by the room's recorder. Looking only here, the backup on its card found no
    # primary and never covered — not when the room was down either, which is the one moment it exists for.
    #
    # So the domain, which reads both clusters, writes a BOOK OF PRIMARIES for the camera's cluster, and the
    # camera's agent carries it home like the grants: per camera, by the domain's name for it (`ref`), who
    # records it, whether it SHOULD be written, whether it IS, and whether it is still STARTING (no recorder
    # of that cluster has named it yet — the only case that gets the grace). No timestamps in it, on purpose: a book that
    # changed on every pass of the domain would be rewritten on the camera's flash every few seconds. How
    # current the book is comes separately — the time the agent last reached the domain, an object in the
    # cluster's object store (RAM on a camera). A book the agent has not refreshed for `lost_after` is a book
    # nobody can vouch for, and then the backup records: it cannot know, and not knowing is a failure.
    def carried_primary(self, row: dict, now: float) -> bool | None:
        """None: the camera's primary is not in another cluster — decide as always. Else: whether to cover."""
        look = look_of(self)                                     # a recorder, or only its two stores (М12's gate)
        items = look.primaries()                                 # once a pass, not once a backup (the scaling pass)
        if not items:
            return None
        if str(row.get("cam", "")).startswith("ref:"):
            ref = str(row["cam"])[4:]                            # a camera of ANOTHER cluster, by the domain's name — a
        else:                                                    # backup kept here for another server's primary (М11 lesson 1)
            cam, _ = self.vars.get(f"vms/cameras/{row['cam']}")
            ref = str((cam or {}).get("ref") or "")
        if not ref or ref not in items:
            return None
        import json
        key = f"ref:{ref}"
        # An entry of the book, or the agent's mark, that does not parse is a book nobody can vouch for: the backup records
        # (the review's seventh pass). Read bare, it raised out of `enrich` — out of the reconciler's loop: every start
        # after this backup, every stop, the gate and the writer's pass were skipped.
        try:
            e = json.loads(items[ref])
            raw = look.domain_seen()
            seen = float(json.loads(raw).get("ts", 0)) if raw else 0.0
            if not isinstance(e, dict):
                raise TypeError("a book's entry is not an object")
        except PARSE_ERRORS as err:
            FIELDS.garbled(f"{PRIMARIES}#{ref}", err)
            self._not_written_since.pop(key, None)
            return True
        FIELDS.parsed(f"{PRIMARIES}#{ref}")
        if now - seen > self.CARRIED_LOST_AFTER:                 # the book is as old as the agent's last contact
            self._not_written_since.pop(key, None)
            return True
        if not e.get("should") or e.get("written"):
            self._not_written_since.pop(key, None)
            return False
        if not e.get("starting"):                                # it was written and stopped: cover at once (feedback AB)
            self._not_written_since.pop(key, None)
            return True
        since = self._not_written_since.setdefault(key, now)    # still starting: every event begins this way
        return now - since >= self.START_GRACE

    # -- the passes: the worker's, plus a re-subscription when the camera's holder moved -------------------
    # The camera's worker moved: the source is another server's fan-out now — or, if it moved HERE, the
    # shared-memory branch. The pipeline reading the old source is stopped and counted lost, so the
    # reconciler starts it again on the new one, under a new rec epoch (a start is a new writer).
    @one_look
    def resubscribe(self, now: float | None = None) -> list[int]:
        now = self.now() if now is None else now
        moved = []
        # Whose fan-out: the RECORDING's camera (`cam`), not the recording's own id — the two are the same string
        # only while the recording is named after its camera, and `7-cloud` moved with its camera too.
        cams = {str(r["id"]): str(r.get("cam") or r["id"]) for r in self.rows}
        for cid in list(self.reconciler.actual):
            src = self.source(cams.get(str(cid), cid))
            if src is not None and self.sources.get(cid) not in (None, src[1]):
                self._release_if_broken(cid)                      # the ring is the only copy of the break (CB): written before the stop
                self.actuator("stop", {"id": cid})
                self.reconciler.lost(cid, now)
                self.sources.pop(cid, None)
                moved.append(cid)
                log.info("%s: camera %s is held elsewhere now (%s): re-subscribing", self.name, cid, src[1])
        return moved

    # One pass, four parts, and the store away stops none of the others: a pipeline that fell over is restarted
    # on its last source, the offline backups are judged by the rows read last, the writer is watched. What a
    # part could not read it reports; it does not take the pass with it (the review's second pass, blocker 4).
    @one_look
    def reconcile_once(self, now: float | None = None) -> list[tuple[str, int]]:
        self.resubscribe(now)
        out = super().reconcile_once(now)
        for part in (self.gate_pass, self.writer_pass):
            try:
                part()
            except OSError as e:
                self.store_errors += 1
                log.warning("%s: %s skipped: the store did not answer (%s)", self.name, part.__name__, e)
        return out

    # -- is the writer writing (Lesson 10, feedback U) ------------------------------------------------------
    # Offered: what the actuator says its pipelines handed their sinks. Landed: what the volume's ring says it
    # took since this recorder opened it (`totalWritten`). Between the two is a queue and the engine's own
    # policy — a sequence it lost, a group of pictures it cut — and "taken" is not "on the volume" until this
    # says so. A recorder whose actuator does not measure says nothing — silence here
    # is "not measured", never "fine". When the watch says stuck or losing, the cure is to reopen the writer:
    # the pipelines are stopped and counted lost, and the reconciler starts them again, under a new epoch as
    # any restart — and the volume is closed and opened again on the next pass, a new writer under the same
    # owner, exactly as after a lost engine. At most every ten minutes (`WriterWatch.reopen_every`); the heartbeat
    # says the state every pass regardless.
    def writer_pass(self, now: float | None = None) -> dict:
        wall = self.wall() if now is None else now
        measure = getattr(self.actuator, "offered", None)
        running = list(self.reconciler.actual)
        vals = [measure(c) for c in running] if measure else []
        # Per recording: when what it was offered last GREW. A pipeline that is up and fed nothing — a source
        # that stalled, a fan-out that stopped — is `running` for ever; `last_frame_at` is the number that says
        # otherwise, and a recording that has taken nothing yet is counted from when it was first seen running.
        for c in running:
            self.running_since.setdefault(c, wall)
        for c in [c for c in self.running_since if c not in running]:
            del self.running_since[c]
        for c, v in zip(running, vals):
            if v is None:
                continue
            last = self.fed.get(c)
            if last is None or v > last[0]:
                self.fed[c] = (v, wall)
        for c in [c for c in self.fed if c not in running]:
            del self.fed[c]
        if not any(v is not None for v in vals):
            return self.writer.state
        try:
            if self.store:
                self._landed = int(self.store.status().get("totalWritten", 0)) - self._written_at_open
            landed = self._landed_before + self._landed
        except ArchiveError:
            if self.store is not None and self.store.lost:
                self._lost_engine()                  # the daemon no longer knows the session: remount, not wait
            return self.writer.state                 # a volume that does not answer measures nothing this pass
        # Offered is summed by DELTAS per pipeline, not as the sum of the running ones: a recording that stops took
        # its count out of the sum, `outstanding` went negative and `stuck` never came (the review's second pass).
        # And what this process wrote into the writer itself — fetched ranges, keeps — is offered too, else it
        # masks a stall for as long as it lands.
        for c, v in zip(running, vals):
            if v is None:
                continue
            seen = self._offered_seen.get(c)
            self._offered_total += v - seen if seen is not None and v >= seen else v
            self._offered_seen[c] = v
        state = self.writer.observe(self._offered_total + self._offered_extra, landed, wall)
        if self.writer.reopen_due(wall):
            log.warning("%s: the writer is %s (%s) — reopening it", self.name, state["state"], state)
            for cid in running:
                self._release_if_broken(cid)
                self.actuator("stop", {"id": cid})
                self.reconciler.lost(cid, self.now())
            self.engine_lost = True                  # …and the writer itself: closed and opened again on the next pass
            self._lost_why, self._lost_at = f"the writer was {state['state']}: reopened", wall
        return state

    # What this recorder adds to the heartbeat.
    def heartbeat_extra(self) -> dict:
        # `volume`: the archive this recorder writes into, and the place the policy counts in. A box with
        # three disks runs three recorders, and `servers: distinct` over `place_by: volume` puts one
        # recording's worth of work on each — which is what the operator meant by three disks.
        #
        # EMPTY means something different from absent, and both are said on purpose. Absent: a recorder
        # that was never told about volumes, read as one place named after its server. Empty: this process
        # is a SPARE — it is running, it has taken no volume, and it is not a place to record. It reports
        # zero capacity with it, so the two halves of the same statement cannot drift apart.
        #
        # `fetched`: the requests this recorder has closed. It cannot delete the rows — a worker writes no
        # configuration — so it says which ones are done and the console removes them.
        return {**super().heartbeat_extra(),         # `fetched`: the same answer every worker gives
                "volume": self.volume,
                # The box's own volume — where this recorder writes when nothing is declared. What the console
                # offers to declare, with the partition's size, the first time anybody looks (`volumes.suggest`).
                "archive": self.default_url,
                # …and its size: what the console offers to declare it at. The size it HAS once it was opened — read
                # from the volume — and only before that the share of the disk it would be formatted at (the review's
                # third pass: recomputed at every start, the number grew and shrank with the disk's free space, and an
                # operator who declared it shrank a volume of eight terabytes to the one gigabyte offered).
                "archive_quota": self.default_size or self.default_quota,
                **({"quota_note": self.quota_note} if self.quota_note else {}),
                # THE SIZE THE HELD VOLUME HAS, from the daemon, and a smaller one declared and waiting for its second word
                # (the review's fourth pass): the page showed the declared number as the size and the journal said
                # `shrunk`, while the ring stayed as it was — an operator who split a disk in two found both rings
                # full later. `volume_quota` is the ring; `shrink_pending` the declared size until it is applied, and
                # `resize_error` why the engine refused a new size (asked again every pass); the applied shrink is the
                # event `archive.volume.shrunk`.
                **({"volume_quota": self.store.quota} if self.store is not None else {}),
                **({"shrink_pending": self.shrink_pending} if self.shrink_pending else {}),
                **({"resize_error": self.resize_error} if self.resize_error else {}),
                # Empty unless the volume this process holds will not open. Published because the alternative
                # is the failure that looks like health: a fresh hold, a green console and nothing being
                # written. Whatever reads it must not count that volume as served.
                "volume_error": self.volume_error,
                # Pinned to a volume any box may serve whose hold is not this recorder's: what it waits for (`_wait_for_pin`).
                **({"volume_wait": self.volume_wait} if self.volume_wait else {}),
                # Empty while the volume takes samples. Otherwise the reason it stopped, and since when.
                # Different from `volume_error` on purpose: a volume that went AWAY is still this recorder's
                # place, and it is not handed back for being away.
                "archive_error": self.archive_error,
                "archive_away_since": self.archive_away_since,
                "archive_failure": self.archive_failure,
                # The engine lost and the volume mounted again (blocker 4): how many times, and the last — when, and why.
                **({"archive_remounts": self.remounts, "archive_remounted": self.remounted} if self.remounts else {}),
                # Seconds of footage that writers this recorder gave up had taken and not written (`_say_dropped`; each
                # is an alarm in its recording's journal too).
                **({"archive_dropped_seconds": round(self.dropped_seconds, 1)} if self.dropped_seconds else {}),
                # Whether what the sinks were handed is reaching the volume (Lesson 10): ok, stuck or losing.
                # A fresh hold and a running row do not say it; only this does.
                "writer": self.writer.state,
                # Volumes this recorder handed back for refusing writes, and why — left alone until the time
                # given, so that a key somebody fixes is picked up without a restart. And the ones it does not take at
                # all, for as long as the reason stands (`unservable`).
                "refused": {**{n: why for n, (_, why) in self.refused.items()}, **self.unservable},
                "closed": ",".join(self.closed),
                # Lesson 26: the door this recorder serves its archive at, for a primary backfilling from it.
                **({"archive_url": self.archive_url} if self.archive_url else {}),
                # Lesson 16: what a clean fetch found nowhere — ours missing it, the source missing it too.
                # A number the operator wants on its own: "of what we lost, 519 s were not on the card either".
                "nowhere_seconds": int(sum(b - a for spans in self.nowhere.values() for a, b in spans)),
                # …and what the source HAD and the engine refused `REFUSED_TIMES` times, given up (`_refused`): the
                # product's `backfill.refused_seconds`. Not "not on the card" — on it, and not something this volume takes.
                "backfill": {"refused_seconds": int(sum(b - a for spans in list(self.given_up.values()) for a, b in spans))},
                # A recorder holding an incidents volume: what each keep holds there (`keep_pass`).
                **({"keeps": self.keep_state} if self.incidents else {}),
                # …and what each keep is short of, alone: `{keep: seconds}` — the console's `rec_keep_missing_seconds`
                # (the review's fourth pass). Empty when every keep is whole.
                **({"keep_missing": {kid: e["missing"] for kid, e in self.keep_state.items() if e.get("missing")}}
                   if self.incidents else {})}

    # -- which archive this recorder writes into ------------------------------------------------------
    # Run once a pass, after the slot and the leases. Four outcomes, and the one that matters is the last.
    #
    # Pinned to a disk: nothing to decide. Pinned to a volume any box may serve: the same as unpinned, with that one
    # volume to take and nothing else — no spare's fallback to the box's own disk. Nothing declared: the server's own
    # name, as before volumes were rows.
    # Holding a volume that is still declared and still enabled: renew, keep recording.
    # Otherwise: let go of what is no longer ours and try to take a free one — and if every volume is
    # taken, become a SPARE. A spare is a normal, visible state: a process that is running, carrying
    # nothing, and waiting for a place. It is what makes the next network archive somebody creates on the
    # console get served in one pass instead of one deploy.
    #
    # Losing a hold is not the same as losing a slot. The slot says which process of the deployment this
    # is; the hold says which archive it writes into. A process can lose the second and keep the first,
    # and it then stops recording — the footage of those recordings belongs to whoever holds the volume
    # now — without fencing the instance, which would mean it could never take another.
    def volume_pass(self) -> str:
        self._check_lost()
        if self.store is not None and self.store.lock_lost:
            # The engine found the volume's lock another writer's: the place is lost whatever the hold row still says —
            # given up, its writer abandoned, what it had taken and not written counted (`_say_dropped`), and the volume
            # claimed again only by the rules. A pinned volume too (the review's seventh pass, blocker 2: its writer
            # stayed, stopped, and nothing said so). Said until a volume is open again — and, once it is, by
            # `archive_remounted`, as a lost engine is.
            name = self.store.name
            self.leave_volume(f"the engine says the lock of {name} is another writer's")
            self.archive_error = self._taken_over = (
                f"another writer took {name} while this recorder was writing it: the footage it had not yet written is "
                f"lost (counted in the recording's journal), and it writes {name} again only once it holds the volume "
                f"and the other writer has let it go")
            self.archive_failure, self.archive_away_since = "away", self.wall()
            self._lost_why, self._lost_at = f"another writer took {name}", self.wall()
        rows = None
        if self.pinned:
            # A pinned DISK: nothing to decide — opened if it is not open, and nobody else's. A pinned volume any box may
            # serve goes on below, the way an unpinned recorder takes one, with nothing else to take.
            last = self._vol_last if self.store is not None else None
            if last is not None and not self.engine_lost and not volumes.any_box(last) and self.hold is None:
                return self.volume
            rows = self._declared()
            vol = rows.get(self.pin) or self._own_volume(self.pin)
            if not volumes.any_box(vol) and not (last is not None and volumes.any_box(last)) and self.hold is None:
                self.volume, self.volume_wait = self.pin, ""
                if self.store is None or self.engine_lost:
                    self.volume_error = str(self._write_into(vol) or "")
                    self.capacity = 0 if self.volume_error else self.full_capacity    # will not open: not a place to put a recording
                    self._place_kind(vol)
                return self.volume
        if rows is None:
            rows = self._declared()
        self._shared = {n for n, v in rows.items() if volumes.any_box(v)}   # remembered: asked when the store is silent
        # A camera's card is not this recorder's to take: it is the camera's buffer, and only the camera's own recorder
        # (`vms/card.py`, `CardRecorder`) writes it — a recorder of the engine on the camera's box included.
        free = [n for n in volumes.servable(list(rows.values()), self.server) if rows[n].kind != "edge"]
        if self.pinned:
            free = [n for n in free if n == self.pin]   # pinning chooses which volume; the hold still decides whether
        # A volume that refuses writes — WRONG, not away — is handed back: its recordings should go somewhere
        # that works. And it is left alone for REFUSED_FOR, or the next pass would take it straight back:
        # opening may succeed and the first write fail again.
        now = self.wall()
        if self.hold is not None and self.archive_failure == "wrong":
            why = self.archive_error
            self.refused[self.hold] = (now + self.REFUSED_FOR, why)
            logging.error("%s: %s refuses writes (%s) — handing it back", self.name, self.hold, why)
            self.leave_volume(f"volume {self.hold} refuses writes")
        if self.hold is not None and self.hold in self._shared and self._busy_since \
                and self.clock() - self._busy_since >= self.BUSY_FOR:
            self._busy_too_long(now)
        answers = self._engine_pass(rows, free, now)   # the volumes any box may serve, and the engine they need
        self.refused = {n: v for n, v in self.refused.items() if v[0] > now}
        free = [n for n in free if n not in self.refused and n not in self.unservable]
        if self._engine_silent_since is not None:    # an engine that answers nothing takes no volume another box could
            free = [n for n in free if n == self.hold or n not in self._shared]
        held = self.hold
        if held is not None and (held not in free or not self.renew_hold()):
            # withdrawn, disabled, taken from us — or one this host's engine may not write
            self.leave_volume(self.unservable.get(held) or f"volume {held} is not this recorder's any more")
        if self.hold is not None and self.hold in self._shared and not answers:
            # Kept, and not mounted in this pass: the ping was this pass's one wait on a silent daemon (Т-M1).
            self._away(rows[self.hold], ArchiveError("away", "obsd is not answering: no answer to a ping", "UNAVAILABLE"))
            return self.volume
        if self.hold is None and not free and self.pinned:
            return self._wait_for_pin(rows)
        if self.hold is None and not free:
            # Nothing declared anywhere: the box as it was before volumes were rows — one place, named after
            # the server, beside `$ARCHIVE`. Note this is reached after letting go above, so withdrawing
            # the last volume does not leave a process quietly writing into it.
            err = self._write_into(self._own_volume(self.default_volume))
            self.volume, self.capacity, self.volume_error = self.default_volume, self.full_capacity, str(err or "")
            return self.volume
        # Take one, and then OPEN it — the step that was missing. Holding a volume and being unable to
        # write into it is the worst failure this subsystem has, because every number says it is fine:
        # the hold is fresh, the console counts it served, and no footage is being written. So the open
        # decides, and a volume that will not open is handed back — but only if there is somewhere else
        # to go. Letting go of the only archive this box can reach would stop it recording altogether,
        # which is a worse answer than recording into a broken one and saying so.
        skipped: set[str] = set()
        broken: list[tuple[str, str]] = []                         # what we handed back on the way, and why
        while True:
            if self.hold is None:
                candidates = [n for n in free if n not in skipped]
                taken = self.claim_hold(candidates) if candidates else None
                if taken is None:
                    # Nothing else to be had — every other declared archive has a live recorder, or there
                    # are none. If we handed a broken one back getting here, take it BACK rather than
                    # leave this box holding nothing: writing into an archive that will not open and
                    # saying so is bad, and not recording at all because of diagnostics is worse.
                    if broken and self.claim_hold([broken[0][0]]) is not None:
                        self.volume, self.capacity, self.volume_error = self.hold, 0, broken[0][1]
                        self.volume_wait = ""
                        logging.error("%s: %s is the only archive it can reach and it will not open: %s",
                                      self.name, self.hold, self.volume_error)
                        return self.volume
                    if self.pinned:
                        return self._wait_for_pin(rows)
                    self.volume, self.capacity = "", 0             # a spare is not a place to put a recording
                    return self.volume
            name = self.hold
            err = self._write_into(rows[name])
            if err is None:
                self.volume, self.capacity, self.volume_error = self.hold, self.full_capacity, ""
                self.volume_wait = ""
                self._place_kind(rows[self.hold])
                return self.volume
            if err.name == "HOLD_LOST":                            # taken from us between the renewal and the mount
                self.leave_volume(f"volume {name} is not this recorder's any more: {err.detail}")
                return self.volume
            logging.warning("%s: %s will not open (%s) — looking for another", self.name, self.hold, err)
            skipped.add(self.hold)
            broken.append((self.hold, str(err)))
            self.volume_error = str(err)
            self.release_hold()                                    # so somebody who CAN write there may take it

    # The declared volumes, `{name: Volume}`, read through `volumes.declared` — and a row that does not parse is NOT a
    # volume withdrawn (the review's seventh pass, part 2, blocker 1). Skipped, it would be: the held volume missing
    # from `free`, let go, its recordings stopped — for one field. The volume this recorder writes into is kept by the
    # row it read last (`_vol_last`, what it opened); any other garbled row is no candidate until it is mended, and is
    # counted and logged by the reader (`volumes.VOLUMES`, `volumes_garbled` in the heartbeat). A pinned recorder whose
    # row was never read whole has nothing to open by: `_own_volume` under that name would be the box's default
    # directory, which is not the volume — so the row's trouble is said and no place is taken.
    def _declared(self) -> dict:
        unread: set = set()
        rows = {v.name: v for v in volumes.declared(self.vars, unread)}
        mine = self.pin if self.pinned else self.hold
        last = self._vol_last
        if mine in unread and last is not None and last.name == mine:
            rows[mine] = last
            self._row_unread(mine)
        elif mine in unread and self.pinned:
            raise ValueError(f"the row of volume {mine} ({volumes.key(mine)}) does not parse, and this recorder never "
                             f"read it whole: it has nothing to open — mend the row")
        else:
            self._vol_unread = None
        return rows

    # KEPT BY THE ROW READ LAST — FOR HOW LONG (the review's eighth pass, part 4, a minor). The volume this recorder writes
    # stays as it was opened while its row does not parse — and a row garbled together with `enabled: false`, or a new
    # quota, was a recorder writing for hours into a volume its administrator had switched off, `rec_volume_error` 0, seen
    # only in `*_volumes_garbled`. Past `ROW_UNREAD_AFTER` it is an ALARM, `archive.volume.unreadable`, once a day while
    # it lasts: what it means for the recording and what to do, in words.
    ROW_UNREAD_AFTER = 600.0

    def _row_unread(self, name: str) -> None:
        from w2cplatform.events import ALARM, EventLog
        now = self.wall()
        since, said = self._vol_unread or (now, None)
        if now - since >= self.ROW_UNREAD_AFTER and (said is None or now - said >= self.SHALLOW_AGAIN):
            EventLog(self.archive_root, REC.name, name, 0).append(now, "archive.volume.unreadable", cls=ALARM, volume=name,
                                                                  since=since, seconds=round(now - since))
            log.error("%s: the settings of volume %s have not been readable for %.0f minutes: this recorder goes on writing it "
                      "as it was set when last read, and a change made since — switched off, a new size — does not reach "
                      "it. Correct the volume's settings on the volumes page, or delete and declare it again",
                      self.name, name, (now - since) / 60)
            said = now
        self._vol_unread = (since, said)

    # PINNED TO A VOLUME ANY BOX MAY SERVE, AND NOT HOLDING IT (the review's seventh pass, blocker 2). Another recorder
    # holds it — a free one that took it first, or the previous instance of this name on another host whose hold has
    # not stood still long enough (`_hold_stale`) — or it is disabled, refused, not servable by this host's engine.
    # This recorder writes nothing then: it holds no place (`volume` empty, capacity nought, like a spare) and says
    # what it waits for (`volume_wait`). It claims the volume again every pass, and takes it once it is free.
    def _wait_for_pin(self, rows: dict) -> str:
        name, vol = self.pin, rows.get(self.pin)
        why = self.refused.get(name, (0, ""))[1] or self.unservable.get(name, "")
        if not why and (vol is None or not vol.enabled):
            why = f"{name} is {'not declared' if vol is None else 'disabled by the administrator'}: nothing is recorded into it"
        if not why:
            try:
                key = self.sub.hold_key(name)
                cur = read_hold(key, name, self.vars.get(key)[0])
            except OSError:
                cur = None
            who = cur.by if cur is not None and cur.by else "another recorder"
            why = (f"{name} is being written by {who}: this recorder is pinned to it and starts writing it once {who} "
                   f"lets it go or stops")
        if why != self.volume_wait:
            log.warning("%s: pinned to %s and not writing it: %s", self.name, name, why)
        self.volume, self.capacity, self.volume_wait = "", 0, why
        return self.volume

    # BUSY, WITH A DEADLINE (the review's sixth pass, an item it left open, and its seventh). A volume any box may serve
    # that this recorder HOLDS and cannot mount, because another writer still has it: the engine's lock refreshed by a
    # daemon that is alive — a recorder there frozen with its writer mounted, or one that never let go. It ends when
    # that writer is given up (the frozen recorder wakes, is fenced and abandons it) or when its daemon closes it; a
    # recorder stuck for good holds it for good, and this one held the hold, recorded nothing, and said `busy` for ever.
    # Past `BUSY_FOR` the volume is let go and left alone for `REFUSED_FOR`, like one that refuses writes: an ALARM,
    # `archive.volume.busy`, words an operator can act on in the heartbeat's `refused` and on the volumes page — and
    # nothing done to the other host: its writer is the engine's business there. An unpinned recorder records into
    # another volume meanwhile, if one is free. A disk of this server is not let go for it: nobody else could take it.
    BUSY_FOR = 600.0

    def _busy_too_long(self, now: float) -> None:
        from w2cplatform.events import ALARM, EventLog
        name, quiet = self.hold, self.clock() - self._busy_since
        why = (f"{name} has been in use by another writer for {quiet / 60:.0f} minutes although this recorder holds it, so "
               f"nothing is being recorded into it. A recorder on another server may be stuck with {name} still open: "
               f"check obsd and the recorders on the other servers. This recorder lets {name} go and tries it again in "
               f"{self.REFUSED_FOR / 60:.0f} minutes")
        EventLog(self.archive_root, REC.name, name, 0).append(now, "archive.volume.busy", cls=ALARM, volume=name,
                                                              seconds=round(quiet), detail=self.archive_error)
        log.error("%s: %s", self.name, why)
        self.refused[name] = (now + self.REFUSED_FOR, why)
        self.leave_volume(why)

    # THE ENGINE UNDER A VOLUME ANY BOX MAY SERVE (the review's sixth pass, blockers 1 and 2, and П-m2). Two things are
    # asked of the host's daemon once a pass, and only when such a volume is declared.
    #
    # CAN IT GIVE A VOLUME UP (`_engine_refuses`)? If not, this recorder takes no such volume at all: not claimed, and
    # said — `unservable`, in the heartbeat's `refused` and on the volumes page — so that a box whose daemon can takes
    # it. The mode this replaces was the fifth pass's "parked" writer for a daemon without the operation: mounted, fed
    # nothing, closed later. It was not safe — a recorder paused past its hold's term while its daemon went on
    # refreshing the engine's lock woke, parked its writer, and the box that held the volume by then was `busy` for
    # ever (reproduced) — and it is gone.
    #
    # DOES IT ANSWER AT ALL (`_hear_engine`)? A recorder renewed its hold for as long as it ran, whatever its daemon
    # did: frozen for 320 s (reproduced), the hold was renewed throughout, nothing was written, and no box whose
    # daemon answers could take the volume. Now the hold is renewed through a silence for `ENGINE_SILENT_FOR` and no
    # longer — by the loop here, and never by the stand-in (`may_stand_in_hold`): past it the volume is let go, and
    # left alone for `REFUSED_FOR` like one that refuses writes. A disk of this server is not let go for a silent
    # daemon: nobody else could write it (`ArchiveError`).
    ENGINE_SILENT_FOR = 300.0                        # the stand-in's `STAND_IN_FOR`, for the same reason: a daemon comes back in less

    def _engine_pass(self, rows: dict, free: list[str], now: float) -> bool:
        """True when the daemon answered in this pass — or was not asked: no volume any box may serve is declared."""
        shared = [n for n in free if n in self._shared]
        was, self.unservable = self.unservable, {}
        if not shared:
            self._engine_silent_since = None
            return True
        answers = self._hear_engine()
        if answers:
            for n in shared:
                e = self._engine_refuses(rows[n])
                if e is not None and e.kind == "wrong":
                    self.unservable[n] = e.detail
                    if n not in was:
                        log.error("%s: %s is not taken: %s", self.name, n, e.detail)
        held = self.hold
        silent = 0.0 if self._engine_silent_since is None else self.clock() - self._engine_silent_since
        if held in shared and silent >= self.ENGINE_SILENT_FOR:
            why = (f"obsd on {self.server} has not answered for {silent:.0f} s, so nothing is being recorded into "
                   f"{held}: this recorder gives the volume up, and a server whose obsd answers takes it. Check obsd "
                   f"on {self.server}; this recorder tries {held} again in {self.REFUSED_FOR / 60:.0f} minutes")
            self.refused[held] = (now + self.REFUSED_FOR, why)
            log.error("%s: %s", self.name, why)
            self.leave_volume(why)
        return answers

    # One PING. No answer: silent since now, if it was not already — and a store that looked open is one the next pass
    # mounts again, as when a sink finds the daemon gone. An answer ends the silence only where nothing contradicts
    # it: no volume held, or one whose writer is mounted — a daemon that answers PING and no mount is still silent.
    def _hear_engine(self) -> bool:
        try:
            self.session.ping()
        except Unavailable as e:
            if self._engine_silent_since is None:
                self._engine_silent_since = self.clock()
                log.warning("%s: obsd does not answer (%s)", self.name, e.detail)
            if self.hold in self._shared and self.store is not None and not self.engine_lost:
                self._lost_engine()
            return False
        except ObsdError:
            pass                                     # an answer, whatever it says
        if self.hold is None or (self.store is not None and self.store.writer is not None and not self.engine_lost):
            self._engine_silent_since = None
        return True

    # A volume any box may serve needs an engine that can GIVE IT UP when another box takes it: `WRITER_ABANDON` — the
    # writer stopped with nothing more written, the engine's lock left alone unless it is still its own (ObjectStorage's
    # patch 07, which this course requires). A daemon without the operation closes a writer one way only: its flush,
    # the volume's status, the lock file removed by its PATH — onto a volume that is another box's by then. So such a
    # daemon is not given the volume at all. `wrong`, in words an operator can act on; `away` while the daemon does not
    # answer — not known is not "it can". None: no objection (a disk of this server needs no giving up).
    def _engine_refuses(self, vol) -> ArchiveError | None:
        if not volumes.any_box(vol):
            return None
        try:
            if self.session.abandons():
                return None
        except ObsdError as e:
            return classify(e)
        return ArchiveError("wrong", f"obsd on {self.server} is too old to write {vol.name} safely — a volume any server "
                                     f"may take: this obsd cannot give a volume up when another server takes it. Update "
                                     f"obsd on {self.server}; volumes on its own disks are not affected", "ENGINE_TOO_OLD")

    # The box's own volume, which nobody declared: no size of its own (`quota_bytes` 0) — `default_quota` formats it
    # if it is new, and a volume that exists keeps the size it has. Declared with a quota, it would be resized at
    # every start to whatever share of the disk was free that morning.
    def _own_volume(self, name: str):
        return volumes.Volume(name, "local", self.default_url, self.server or "", 0)

    # The engine lost, found by whoever touched a handle of the store (`Archive.lost`): the next open is a remount.
    def _check_lost(self) -> None:
        if self.store is not None and self.store.lost and not self.engine_lost:
            self._lost_engine()

    # WHEN THE HOLD WAS LAST CONFIRMED (the review's third pass). It was stamped when `volume_pass` ended — after the
    # renewal AND after whatever the pass did next, a remount that closes a writer and opens another included, which
    # can take a minute. A hold confirmed at the start of that minute and stamped at its end looked a minute younger
    # than it was. The stamp is the store's answer, now: at the renewal, and at the claim.
    #
    # And from BEFORE the store was asked, as a lease is (`Lease.renew`; the review's fifth pass): a renewal that took
    # ten seconds to come back confirmed the hold as it was when it was asked. Never backwards — the pass, a keep's
    # seal and the stand-in confirm it from three threads.
    def renew_hold(self) -> bool:
        t0 = self.clock()
        ok = super().renew_hold()
        if ok and self.hold is not None:
            self.note_hold_confirmed(t0)
        return ok

    def claim_hold(self, candidates: list[str], retries: int = 20) -> str | None:
        t0 = self.clock()
        got = super().claim_hold(candidates, retries)
        if got is not None:
            self._hold_confirmed = t0                # a new hold: its own clock, not the last one's
        return got

    def note_hold_confirmed(self, at: float) -> None:
        self._hold_confirmed = max(self._hold_confirmed, at)

    # A VOLUME ANY BOX MAY SERVE FOLLOWS THE NAME ONLY ON ITS HOLDER'S HOST (the review's sixth pass, blocker 2, and its
    # seventh). A disk does: the instance that took this recorder's name is on the same host, where the daemon keeps one
    # writer per volume. A network volume's next holder may be on ANOTHER host, and the instance it takes the name from
    # may be frozen, not dead, its writer mounted: two instances of `r-1` on two daemons, the first frozen — the second
    # took the hold at once, mounted thirteen seconds later, and the first woke with a hold confirmed thirteen seconds
    # ago, inside its write window: thirty frames `OK` beside the other's (reproduced). The window rests on a claimant
    # WAITING `slot_ttl + HOLD_SKEW`, so a claimant on another host waits it, the same name included.
    #
    # On the holder's own host it does not have to (the seventh pass: the sixth made every restart of a recorder wait
    # fifty seconds with nothing recorded — feedback CF undone). The row's `holder` is `host:pid:rnd`: the same host is
    # the same daemon, and that daemon lets one writer at a time hold the volume — the new instance's mount is
    # `ALREADY_LOCKED` while the old one's writer is attached, frozen or not, and picks it up (`reattached`) once it is
    # detached. An instance named otherwise — `NOMAD_ALLOC_ID`, `INSTANCE_ID` — says no host: it waits, the safe side,
    # unless the runtime said the box (`BOX_ID`, `box_instance`). The host is the box's id where one is said — two boxes
    # named alike are two hosts (the eighth pass).
    # A hold let go on purpose — its writer closed first (`leave_volume`, `after_stop`) — is taken at once by anybody.
    def hold_follows_name(self, place: str, holder: str = "") -> bool:
        if place not in self._shared:
            return True
        here = host_of(self.instance)
        return here is not None and here == host_of(holder)

    # BEFORE EVERY SAMPLE (the review's fifth pass, blocker 1): may this recorder write into `vol` this second?
    # A disk of this server always — nobody else can write there. A network volume any box may serve, pinned or not
    # (the review's seventh pass, blocker 2), only while the hold is this recorder's and was confirmed less than
    # `slot_ttl − lease_margin` ago: the recorder that takes it next waits `slot_ttl + HOLD_SKEW` of an unchanged row by its own clock (`_hold_stale`),
    # so writing stops ten seconds before anybody else may start. It is `Lease.may_write`, for the place — and like
    # it a check before sending: what fences the volume itself is the engine (`Archive._fenced`).
    def _may_write_volume(self, vol) -> bool:
        if vol is None or not volumes.any_box(vol):
            return True
        return self.hold == vol.name and self.clock() - self._hold_confirmed < self.slot_ttl - self.lease_margin

    # …and may its writer be CLOSED — the flush, the volume's status, the engine's lock released by its path? While the
    # hold is still this recorder's and nobody else may have taken it: a claimant waits `slot_ttl + HOLD_SKEW` of an
    # unchanged row. Wider than the fence by the margin and the skew — the ten seconds a close is given on the leases'
    # thread — and the engine's own lock, refreshed by a daemon that is not frozen, holds the claimant off until the
    # close has released it.
    def _may_close_volume(self, vol) -> bool:
        if vol is None or not volumes.any_box(vol):
            return True
        return self.hold == vol.name and self.clock() - self._hold_confirmed < self.slot_ttl + self.HOLD_SKEW

    # The stand-in renews the hold while a step hangs (`Worker._stand_in_hold`) — but not while the engine itself is
    # silent (the review's fifth pass, a minor): a step stuck on a daemon that answers nothing writes nothing either,
    # and a hold renewed for it only keeps the volume from a box whose daemon answers. Silent is what the PASS found
    # (`_engine_silent_since`), not only what this moment shows (the sixth pass): between two of a hung step's calls
    # the session is not "silent", and with no volume open nothing had said the engine lost — the stand-in renewed.
    def may_stand_in_hold(self) -> bool:
        return not (self.engine_lost or self.session.silent() or self._engine_silent_since is not None)

    # Asked right before every `VOLUME_MOUNT_RW` (`Archive.confirm`): is this volume still ours, this second? A
    # network volume any box may serve is ours only while the store says the hold is, and the engine's own lock on
    # it is a SECOND line, not the first: on s3 it is a lock object with a timestamp — taken without an atomic
    # check, compared across two machines' clocks, and overwritten unconditionally by a holder that wakes from a
    # freeze (the engine's owner, asked). Two writers in one ring is damage. So the hold is renewed here, at the
    # mount, and a mount the store does not confirm does not happen. A disk of this server is nobody else's, and a
    # store that does not answer does not stop its mount (`lease_pass`).
    #
    # A network volume this recorder does NOT hold is never mounted (the seventh pass): it was taken for "the box's own
    # volume, no hold to confirm", which a pinned recorder's volume, mounted without any hold, went through.
    def _confirm_hold(self, vol) -> None:
        if self.hold != vol.name:
            if volumes.any_box(vol):
                raise ArchiveError("wrong", f"{vol.name} is not held by this recorder: not mounted", "HOLD_LOST")
            return                                   # no hold to confirm: a pinned disk, or the box's own volume
        try:
            ok = self.renew_hold()
        except OSError as e:
            # The store is silent. The hold is still ours for as long as its term runs, and a mount takes at most a
            # call's timeout: a network volume is mounted only if the term outlasts that; a disk of this server, always.
            left = self.slot_ttl - self.lease_margin - (self.clock() - self._hold_confirmed)
            if volumes.any_box(vol) and left <= self.session.timeout:
                raise ArchiveError("away", f"the hold on {vol.name} could not be confirmed before mounting it: {e}",
                                   "HOLD_UNCONFIRMED") from None
            return
        if not ok:
            raise ArchiveError("wrong", f"{vol.name} is held by another recorder now: not mounted", "HOLD_LOST")

    # An INCIDENTS volume is a place for kept footage and never one to record into: the recorder holding it says
    # so with its capacity — nought, like a spare — and copies keeps instead (`keep_pass`).
    def _place_kind(self, vol) -> None:
        self.incidents = vol.kind == "incidents"
        if self.incidents:
            self.capacity = 0

    # Taking a volume means OPENING it through the host's daemon and becoming its writer. Returns None when it
    # is open and writable, or the reason it is not. Opening is the only honest test: a declaration can name a
    # path that does not exist, a mount that is gone or a bucket nobody can reach, and none of that is visible
    # in the row. A volume that does not exist yet is formatted at its quota — the size of its ring.
    #
    # A failure is answered by its KIND (`vms/archive.py`, `ArchiveError`). WRONG — not a volume, no permission —
    # is returned, and `volume_pass` hands the volume back: nobody can write there until a person fixes it. AWAY
    # — the daemon not answering, a network that is down — and BUSY — a writer the daemon still holds for
    # somebody — are not reasons to give the volume up: the recorder keeps it and tries again next pass. Handing
    # it back would reshuffle every recording on it for a link that is back in a minute.
    #
    # The writer is mounted under the owner `rec:<volume>`. A recorder killed and started again — or the next
    # recorder to hold the volume — names the same owner, and the daemon hands back the very writer the dead
    # process left (`reattached`): no lock waited out, nothing recovered (feedback CF).
    def _write_into(self, vol) -> ArchiveError | None:
        # A camera's card is the camera's buffer, written by its own recorder as plain segment files (`vms/card.py`;
        # the product's camera has no engine) — never mounted by the engine, here or anywhere.
        if vol.kind == "edge":
            return ArchiveError("wrong", f"{vol.name} is a camera's card: its camera's recorder writes it, the engine "
                                         f"never does (vms/card.py)", "NOT_AN_ENGINE_VOLUME")
        self._vol_last = vol
        if self.store is not None and self.store.url == vol.url and self.store.writer is not None and not self.engine_lost:
            self._apply_quota(vol)
            return None
        if self.store is not None:
            # On the leases' thread: one call's wait (Т-M1). And a close that did not come back left the session behind:
            # the volume is mounted again on the next pass, once the daemon has done — not here, a second call's wait
            # on a daemon that answers nothing (the review's fifth pass, Т-M1).
            if self._close_store(quiet=True, wait=self.session.timeout):
                return self._away(vol, ArchiveError("away", "the writer's close did not come back: mounted again on "
                                                            "the next pass", "UNAVAILABLE"))
        refuses = self._engine_refuses(vol)              # a volume any box may serve, and an engine that cannot give it up
        if refuses is not None:
            return refuses if refuses.kind == "wrong" else self._away(vol, refuses)
        # The volume's secret is sealed to ITS row, `rec/volumes/<name>` (the review's third pass, blocker 3): opened
        # without the row it never opened at all, and the recorder — with no key in its unit either — handed the
        # bucket the ciphertext. And a secret that does not open is THIS volume's failure, not the pass's: the volume
        # is not taken, its status says why, and the pass goes on to the next (`Sealed` used to fly out of `lease_pass`,
        # which catches only `OSError`: no heartbeat, and in 45 s the recorder was dead to its controller).
        try:
            secret = open_row(self.sealer, {"access_secret": vol.access_secret}, volumes.key(vol.name))["access_secret"]
        except Sealed as e:
            log.error("%s: %s: %s", self.name, vol.name, e)
            return ArchiveError("wrong", f"{vol.name}: {e}", "SEALED")
        store = Archive(vol.url, vol.name, vol.quota_bytes or self.default_quota, f"rec:{vol.name}", self.session, self.wall,
                        secret=secret, access_key=vol.access_key,
                        sequence_flush_ms=self.sequence_flush_ms, block_flush_s=self.block_flush_s,
                        confirm=lambda: self._confirm_hold(vol), share=self._share_of_space,
                        fence=lambda: self._may_write_volume(vol),
                        on_unclean=lambda result, detail: self._unclean(vol, result, detail),
                        **{k: v for k, v in (("block", self.block), ("read", self.read), ("lock_refresh", self.lock_refresh))
                           if v})
        store.row = vol                                  # what `_close_store` asks whether its writer may be closed by
        try:
            store.open()
        except ArchiveError as e:
            self._lock_theirs = False
            if store.orphan and store.session is self.session:
                self._leave_session(f"the mount of {vol.name} was not answered: the writer the daemon made is an orphan")
            elif self._own_lock(store, e):
                self._leave_session(f"{vol.name} is ALREADY_LOCKED by a writer of our own owner {store.owner} for "
                                    f"{self.OWN_LOCK_FOR:g} s: an orphan of this session")
            if e.name == "HOLD_LOST":
                return e
            # A DISK on this box that cannot be formatted or mounted — a file where the directory should be, a
            # path nobody may create — is not a link that comes back in a minute. The engine says it as an I/O or
            # a generic error, the same words a network volume uses for a network that is down, so the kind of
            # volume decides: on a box, wrong; at an address, away.
            if e.kind == "away" and e.name in ("IO_ERROR", "GENERIC_ERROR") and volumes.on_a_box(vol):
                e = ArchiveError("wrong", e.detail, e.name)
            if e.kind == "wrong":
                return e
            if self._lock_theirs:
                e = ArchiveError("busy", self._not_our_lock(vol), e.name)
            return self._away(vol, e)
        self._own_lock_since, self._own_lock_left, self._engine_silent_since, self._busy_since = 0.0, False, None, 0.0
        if self.engine_lost or self._taken_over:
            self.remounts += 1
            self.remounted = {"lost_at": self._lost_at or self.wall(), "at": self.wall(),
                              "why": self._lost_why or "the writer was reopened"}
            self._lost_why, self._lost_at = "", 0.0
            log.warning("%s: %s mounted again (%s)", self.name, vol.name, self.remounted["why"])
        self.store, self.engine_lost, self._taken_over = store, False, ""
        try:
            self._landed_before, self._landed = self._landed_before + self._landed, 0
            self._written_at_open = int(store.status().get("totalWritten", 0))
        except ArchiveError:
            self._written_at_open = 0
        if vol.url == self.default_url:
            self.default_size = store.quota          # the box's own volume: the size it HAS, for the console to offer
        self._apply_quota(vol)
        if self.archive_error:
            log.info("%s: %s answers again after %.0f s", self.name, vol.name, self.wall() - self.archive_away_since)
        self.archive_error, self.archive_failure, self.archive_away_since = "", "", 0.0
        log.info("%s: writing into %s (%s)%s%s", self.name, vol.name, vol.url, " — formatted" if store.formatted else "",
                 " — the writer a previous process left, picked up again" if store.reattached else "")
        return None

    # `away` or `busy` at open: the volume is kept, and said as what it is. A daemon that did not answer at all, under a
    # volume any box may serve, is the engine silent since now (`_engine_pass`).
    def _away(self, vol, e: ArchiveError) -> None:
        if not self.archive_error:
            self.archive_away_since = self.wall()
            log.warning("%s: %s is %s at open (%s) — keeping it and trying again", self.name, vol.name, e.kind, e.detail)
        self.archive_error, self.archive_failure = e.detail, e.kind
        if self._taken_over:                         # what happened before the wait is still the news (`volume_pass`)
            self.archive_error = f"{self._taken_over}. Now: {e.detail}"
        # `BUSY_FOR` counts UNBROKEN busy (the review's eighth pass, part 2): the mark was set by a `busy` and cleared only
        # by a mount or by leaving, so one `busy` pass — a predecessor's writer still closing — followed by ten minutes of
        # a network that is down (`away`, waited for without a deadline) let a volume that was merely unreachable go with
        # an alarm sending the operator to look for somebody else's recorder, and a pinned recorder wrote nothing for ten
        # minutes after the store came back. Any refusal that is not `busy` ends the count.
        self._busy_since = (self._busy_since or self.clock()) if e.kind == "busy" else 0.0
        if e.name == "UNAVAILABLE" and volumes.any_box(vol) and self._engine_silent_since is None:
            self._engine_silent_since = self.clock()
        return None

    # ALREADY_LOCKED UNDER OUR OWN OWNER, FOR LONGER THAN A SESSION LINGERS (the review's fifth pass, blocker 2). The
    # daemon names the owner of an attached writer in its refusal; a detached one of ours it would have handed back
    # (`reattached`), and one of a process that is gone after its linger. `rec:<volume>` attached to a session that
    # stays — this one: a mount whose answer was lost, whatever lost it — is an orphan nobody here holds a handle of.
    # Not at once: a predecessor on this host may be closing its writer this moment.
    #
    # THE OWNER IS A NAME, AND ANOTHER PROCESS MAY BEAR IT (the review's sixth pass, a minor). `rec:<volume>` is the
    # same for every recorder of the volume: a second instance of this recorder on the host, or one that lost the
    # hold and has not let go yet, holds a writer under it in a session of ITS own — and this recorder took that for
    # its orphan, every ten seconds: seven sessions left behind in forty (reproduced), each cutting its readers off.
    # The daemon does not say which session holds a writer, but it lists its sessions with their process ids (`STATS`):
    # while another process of this recorder's own client name is there, the lock is taken for its, and no session is
    # left. And whatever the list says, one session is left per lock, not one per ten seconds: an orphan of ours comes
    # back to the next mount (`reattached`); a lock still attached after that is not in a session of this process.
    OWN_LOCK_FOR = 10.0

    def _own_lock(self, store: Archive, e: ArchiveError) -> bool:
        if e.name != "ALREADY_LOCKED" or f"({store.owner})" not in e.detail or "detached" in e.detail \
                or store.session is not self.session:
            self._own_lock_since, self._own_lock_left = 0.0, False
            return False
        now = self.clock()
        self._own_lock_since = self._own_lock_since or now
        if now - self._own_lock_since < self.OWN_LOCK_FOR:
            return False
        if self._own_lock_left or self._same_name_elsewhere():
            self._lock_theirs = True                 # said as what it is (`_not_our_lock`); nothing of ours to shed
            return False
        self._own_lock_since, self._own_lock_left = now, True   # …and judged again a linger after the session is left
        return True

    # The daemon's sessions of this recorder's client name in ANOTHER process: `[{client, pid, …}]` (`STATS`).
    def _same_name_elsewhere(self) -> list[dict]:
        try:
            sessions = self.session.stats().get("sessions", [])
        except ObsdError:
            return []
        return [s for s in sessions if s.get("client") == self.session.client and int(s.get("pid") or 0) != self.session.pid]

    # What `archive_error` says of a lock under this recorder's owner that is not its own to shed: who else is there.
    def _not_our_lock(self, vol) -> str:
        try:
            others = sorted({f"{s.get('client')} (pid {s.get('pid')})" for s in self.session.stats().get("sessions", [])
                             if int(s.get("pid") or 0) != self.session.pid})
        except ObsdError:
            others = []
        return (f"{vol.name} is being written by another process on {self.server} under this recorder's owner name, so "
                f"this recorder cannot write it"
                + (f" — obsd's other clients: {', '.join(others)}" if others else "")
                + f". Two recorders of one volume on one server: stop the other one, or wait for it to let {vol.name} go")

    # This session left behind for the daemon to detach, and a new one in its place (`Session.successor`): the writer
    # nobody here holds is detached after its linger and handed to the next mount under the same owner.
    #
    # WHAT ELSE GOES WITH IT (the review's sixth pass). Its readers: the doors' questions in flight answer 503 and are
    # asked again of the new session. And no writer of ANOTHER volume: a recorder has one store, and it is closed, given
    # up or the very one being left by the time a session is (`_write_into`, `_close_store`) — the parked writers that
    # used to die with a left session are gone with parking. The writer that IS left the daemon closes after its grace,
    # unless the same owner mounts first: with the lock still its own that is the flush of what it had taken; with the
    # lock another writer's the engine writes nothing and leaves that lock alone (its patch 07).
    def _leave_session(self, why: str) -> None:
        log.warning("%s: %s — its session is left for the daemon to detach, and a new one picks the writer up",
                    self.name, why)
        self.session = self.session.successor()

    # `VOLUME_UNCLEAN`, recovered under a confirmed hold (`Archive._mount_rw`): an ALARM, because footage may be gone —
    # two writers in one ring, a crash in the middle of a block — and somebody is asked about it afterwards.
    def _unclean(self, vol, result: int, detail: str) -> None:
        from w2cplatform.events import ALARM, EventLog
        said = {0: "clean", 1: "recovered", 2: "failed"}.get(int(result), str(result))
        EventLog(self.archive_root, REC.name, vol.name, 0).append(
            self.wall(), "archive.volume.recovered", cls=ALARM, volume=vol.name, result=said, detail=detail)
        log.error("%s: %s was not cleanly unmounted (%s): recovered under this recorder's hold — %s", self.name,
                  vol.name, detail, said)

    # A NEW QUOTA IS A NEW SIZE OF THE RING — a larger one at once, a smaller one only when the row says so twice.
    # Shrinking a ring frees its oldest blocks: a quota typed one digit short, or a number the console offered from a
    # recorder's guess, erased terabytes of footage without a question (the review's third pass). So a quota below
    # the size the volume HAS is applied only when the row also carries `shrink_confirmed` equal to it — the
    # operator's second word — and otherwise it is said in the heartbeat (`quota_note`) and the ring keeps its size.
    #
    # And what happened is SAID (the review's fourth pass): the console journals the request (`archive.volume.
    # shrink_requested`), and only the recorder knows when the engine applied it — `archive.volume.shrunk`, with the
    # size before and after, under the volume's name in this recorder's events. A size the engine refused is
    # `resize_error` in the heartbeat until a pass gets it through.
    def _apply_quota(self, vol) -> None:
        self.quota_note, self.shrink_pending = "", 0
        st = self.store
        if st is None or not vol.quota_bytes or vol.quota_bytes == st.quota:
            self.resize_error = ""
            return
        if vol.quota_bytes < st.quota and vol.shrink_confirmed != vol.quota_bytes:
            self.quota_note = (f"{vol.name} is {st.quota} bytes and declared {vol.quota_bytes}: shrinking it erases the "
                               f"oldest footage, so it is not done until the row says `shrink_confirmed: {vol.quota_bytes}`")
            self.shrink_pending = vol.quota_bytes
            return
        was = st.quota
        try:
            st.resize(vol.quota_bytes)           # a new quota is a new size of the ring, without stopping
        except ObsdError as e:
            log.warning("%s: could not resize %s to %d bytes: %s", self.name, vol.name, vol.quota_bytes, e)
            self.resize_error = f"{vol.name}: {vol.quota_bytes} bytes refused: {e}"
            return
        self.resize_error = ""
        if vol.quota_bytes < was:
            from w2cplatform.events import EventLog
            EventLog(self.archive_root, REC.name, vol.name, 0).append(
                self.wall(), "archive.volume.shrunk", durable=True, volume=vol.name, was=was, quota_bytes=vol.quota_bytes)
            log.warning("%s: %s shrunk from %d to %d bytes: its oldest footage is given up first", self.name, vol.name,
                        was, vol.quota_bytes)
        if vol.url == self.default_url:
            self.default_size = st.quota

    # A sink found the daemon gone — or a handle of the store answered that the daemon no longer knows this session
    # (`SessionLost`: restarted, or the session outlived its linger; the review's third pass, blocker 4). Nothing is
    # torn down here, on the pipeline's thread: the next pass closes what is left of the store and opens it again
    # (`volume_pass`) — at once, not after the writer watch's ten minutes, because there is nothing to wait for: the
    # engine is not there, a new session is (feedback CF). And it is SAID: until the remount, `archive_error`; after
    # it, `archive_remounted`.
    def _lost_engine(self) -> None:
        if self.store is not None and not self.store.lost and not self._may_write_volume(getattr(self.store, "row", None)):
            return                                   # fenced, not lost (`Fenced`): the hold is the pass's to answer
        lost = self.store is not None and self.store.lost
        why = ("obsd no longer knows this recorder's session (restarted, or the session outlived its linger): every "
               "handle is dead" if lost else "obsd stopped answering")
        if not self.engine_lost:
            log.warning("%s: %s — remounting %s on the next pass", self.name, why, self.volume)
            self._lost_why, self._lost_at = why, self.wall()
            if not self.archive_error or lost:
                self.archive_error, self.archive_failure = why, "away"
                self.archive_away_since = self.archive_away_since or self.wall()
        self.engine_lost = True

    # The volume took the sample and REFUSED it for good — no permission, read-only, a key that no longer opens
    # it. Only a person changes that, so the volume is handed back on the next pass (`volume_pass`, REFUSED_FOR)
    # and its recordings go somewhere that works. Said here, on the pipeline's thread; acted on there.
    def _volume_refuses(self, e) -> None:
        if self.archive_failure != "wrong":
            log.error("%s: %s refuses writes: %s", self.name, self.volume, e)
            self.archive_error, self.archive_failure = str(e), "wrong"
            self.archive_away_since = self.archive_away_since or self.wall()

    # Closing the store, and what a close that did not happen leaves (the review's fourth pass, blocker 1). The daemon
    # went silent, the write connection answered `Unavailable` at once for its window, and the remount's
    # `WRITER_CLOSE` was refused before it reached the daemon: the store forgot the handle, the writer lived on in the
    # session the readers and the pass kept alive, and every mount after it was `ALREADY_LOCKED` until somebody
    # restarted the recorder. A writer whose close did not happen is left to the daemon now: the session is abandoned
    # and a new one takes its place (`Session.successor`) — the daemon detaches the writer after its linger, sequences
    # finished, and the next mount, under the same owner, picks it up (`reattached`). Busy until then, a pass or two.
    #
    # And the close waits `wait` (the review's fourth pass, Т-M1): on the thread that renews the leases a
    # `WRITER_CLOSE` waited the protocol's thirty seconds and more, past the twenty-five a lease leaves — a slow
    # flush fenced every recording. That thread waits one call's timeout; a flush longer than that goes on in the
    # daemon, the session is left behind as above, and the volume is mounted again once the daemon has done.
    #
    # A WRITER OF A NETWORK VOLUME WHOSE HOLD IS LOST IS NOT CLOSED: IT IS GIVEN UP (the review's fifth pass, blocker 1).
    # The close is the writer's last write — its flush, the volume's status — onto a volume another box may hold by
    # then: a box frozen whole woke, its pass found the hold gone and closed the writer, and the rightful holder's next
    # mount was `VOLUME_UNCLEAN`, pass after pass. So such a writer gets `WRITER_ABANDON` (`Archive.abandon`): nothing
    # more written — no queue, no status — and the engine's lock removed only if it is still its own.
    #
    # THE ENGINE IS WHAT MAKES THIS SAFE, AND THE COURSE REQUIRES THAT ENGINE (ObjectStorage with its patch 07; the
    # review's sixth pass). It checks the volume's lock at its path before every block, status and removal, stops a
    # writer whose lock is another's (`WRITER_STOPPED`, "volume lock lost" — `Archive.lock_lost`), and never removes a
    # lock that is not its own — whoever closes the writer: this recorder, the daemon at the end of a dead recorder's
    # grace, the supervisor stopping the daemon. A daemon without `WRITER_ABANDON` is not given such a volume at all
    # (`_engine_refuses`); the fifth pass's stopgap for it — the writer "parked", mounted and fed nothing — is gone:
    # it made the volume busy for ever for the box that held it by then (the sixth pass, blocker 1).
    #
    # WHAT THE WRITER HAD TAKEN AND NOT WRITTEN IS LOST, AND COUNTED (the sixth pass, a minor): frames answered `OK`
    # that were still in the writer's queue or its open block — an alarm in each recording's journal, seconds in the
    # heartbeat (`_say_dropped`). And a daemon that does not answer the giving up keeps the writer in a session this
    # recorder leaves: the engine's own check is then all that stands, which is what it is there for.
    #
    # `_leaving`: the volume is being left for good (`leave_volume`, `after_stop`), not mounted again. Then a close that
    # did not come back on a volume any box may serve is footage that MAY be lost: the next writer may be another box's,
    # and the engine will let this one write nothing once its lock is taken. Said as a bound, not as a fact.
    #
    # Returns True when the session was left behind.
    _leaving = False

    def _close_store(self, quiet: bool = False, wait: float | None = None) -> bool:
        if self.store is None:
            return False
        st, let_go = self.store, True
        if st.writer is not None and (st.lock_lost or not self._may_close_volume(getattr(st, "row", None))):
            self.store = None
            answered = st.abandon(wait)
            log.error("%s: volume %s may be another server's by now (%s): this recorder stops writing it and gives its "
                      "writer up without writing anything more%s", self.name, st.name,
                      "the engine found its lock taken" if st.lock_lost else "its hold was not confirmed in time",
                      "" if answered else " — obsd did not answer, so the writer is left for obsd to close")
            self._say_dropped(st, answered)
            if not answered and st.session is self.session:
                self._leave_session(f"the writer of {st.name} could not be given up (the daemon did not answer)")
                return True
            return False
        try:
            let_go = st.close(wait)
        except Exception as e:                           # noqa: BLE001 — closing a volume that went away says nothing new
            if not quiet:
                log.warning("%s: closing %s: %s", self.name, st.name, e)
        self.store = None
        row = getattr(st, "row", None)
        if not let_go and self._leaving and row is not None and volumes.any_box(row):
            st.dropped = st.unwritten(look=False)
            self._say_dropped(st, False)
        if not let_go and st.session is self.session:
            self._leave_session(f"the writer of {st.name} did not close (the daemon did not answer)")
            return True
        return False

    # What a writer given up had taken and not written (`Archive.dropped`), said per recording: an ALARM in its journal
    # — `archive.footage.dropped`, with the seconds and the stretch — and summed in the heartbeat
    # (`archive_dropped_seconds`). `known` False: the daemon did not answer, nobody could look at what the volume
    # shows, and the stretch is what the engine's flush periods leave unwritten at most — a bound, said as one
    # (`exact: false`).
    def _say_dropped(self, st: Archive, known: bool) -> None:
        from w2cplatform.events import ALARM, EventLog
        from .archive import parse_stream
        for name, (a, b) in sorted(st.dropped.items()):
            p = parse_stream(name)
            if p is None:
                continue
            self.dropped_seconds += b - a
            EventLog(self.archive_root, REC.name, p[0], p[1]).append(
                self.wall(), "archive.footage.dropped", cls=ALARM, volume=st.name, seconds=round(b - a, 1), since=a,
                until=b, exact=known)
            log.error("%s: %s%.0f s of recording %s are lost (%.0f–%.0f): the writer had taken them and not yet "
                      "written them when volume %s was given up. A backup recording or the camera's own archive may "
                      "still hold them — ask for a backfill of that stretch", self.name, "" if known else "up to ",
                      b - a, p[0], a, b, st.name)

    # Stop writing into a volume that is no longer ours — the administrator withdrew it, or the hold
    # lapsed and somebody else took it. Every recording of that archive is stopped and released, which is
    # the reassignment path of `lease_pass` and not the zombie one: the process keeps its slot, keeps
    # running, and may take another volume on the next pass.
    def leave_volume(self, why: str) -> None:
        logging.warning("%s: %s — stopping its recordings", self.name, why)
        for uid in list(self.reconciler.actual):
            self._release_if_broken(uid)
            self.actuator("stop", {"id": uid})
            self.reconciler.actual.pop(uid, None)
            self.release(str(uid))
        # A fetch in flight lands into the volume it STARTED on (`_land` checks) and finds it gone; it is given a
        # moment to finish its group rather than be cut in the middle of one.
        if self._backfiller is not None and self._backfiller.is_alive():
            self._backfiller.join(timeout=5.0)
        # The writer is closed while the volume is still ours — its flush is what puts the last minutes on the
        # volume — and only then is the hold let go: released first, the next holder would mount a volume with
        # our writer still in it. Waited one call's timeout, on the leases' thread (Т-M1): a flush longer than that
        # goes on in the daemon, and whoever mounts the volume next finds it busy until it is done — the daemon keeps
        # one writer per volume, and on another host the engine's own lock holds it. A network volume whose hold is
        # already lost is not closed at all: its writer is given up (`_close_store`; the review's fifth pass, blocker 1).
        self._leaving = True
        try:
            self._close_store(quiet=True, wait=self.session.timeout)
        finally:
            self._leaving = False
        try:
            self.release_hold()
        except OSError:                              # the store is silent: the hold lapses by itself
            self.hold = None
        self.volume, self.capacity, self.incidents = "", 0, False
        # What the archive's state said was about the volume we just left. The next one starts clean.
        self.archive_error, self.archive_failure, self.archive_away_since, self._busy_since = "", "", 0.0, 0.0
        self.keep_held, self.keep_state, self._keeps_read, self._keep_nowhere = {}, {}, False, {}

    # AN ORDERLY STOP GIVES THE VOLUME BACK — AFTER THE LAST WRITE INTO IT (the product's box, feedback BR).
    #
    # A recorder that stopped released its slot and not its hold: the volume stayed "held" until the hold
    # lapsed, and whoever was to write there next waited out `slot_ttl` — forty-five seconds of no recording
    # on every restart and every rolling update, for nothing: the process that held it had said goodbye.
    #
    # The ORDER is the point. A released place is taken at once, and whoever takes it mounts the volume for
    # writing. So the hold goes LAST: the pipelines are stopped, the last heartbeat said so, the slot is
    # released — and then the writer is closed, its flush putting the last minutes on the volume, and only then
    # is the hold let go. Released together with the slot, the next recorder would find our writer still there.
    #
    # A crash does none of this. The hold lapses by itself, and the daemon keeps the writer DETACHED for its
    # grace — longer than the hold takes to lapse — so whoever takes the volume next, under the same owner
    # `rec:<volume>`, picks the writer up whole (feedback CF).
    def after_stop(self) -> None:
        held = self.hold
        self._leaving = True
        try:
            self._close_store()
        finally:
            self._leaving = False
        if held is None:
            return
        try:
            self.release_hold()
            logging.info("%s: released %s on the way out", self.name, held)
        except OSError as e:                         # the store does not answer: the hold lapses by itself
            logging.warning("%s: could not release %s (%s); it lapses in %.0f s", self.name, held, e, self.slot_ttl)

    # HOW DEEP EACH RECORDING IS, AND WHETHER THAT IS LESS THAN IT WAS PROMISED (feedback BM).
    #
    # `retention_days` is a ceiling on what is shown. The row's `min_depth_days` is the floor — and nothing
    # enforces it: the volume is a ring, and a ring gives up its oldest minutes when it is full, whatever was
    # promised. So the recorder WATCHES. Once a minute it reads, per recording:
    #
    #   depth_days   from the index: how far back the footage goes. In the status and on `/metrics`
    #   shallow      the ring has CLOSED — it has begun to overwrite (`firstBlockId` past nought) — and the
    #                recording holds less than its floor. A young archive is shallow because it is young, and
    #                that is not this: nothing was overwritten yet
    #
    # The alarm `archive.shallow` is raised when it begins and once a day while it lasts — an alarm, because a
    # recording that holds four days of a promised thirty is the thing somebody is asked about afterwards. The
    # answer is a larger quota, or fewer recordings on the volume.
    DEPTH_EVERY, SHALLOW_AGAIN = 60.0, 86400.0

    def depth_pass(self, now: float | None = None) -> dict:
        from w2cplatform.events import ALARM, EventLog
        if self.store is None or self.engine_lost or self.clock() - self._depth_at < self.DEPTH_EVERY:
            return self.depths                       # (an engine found lost is not asked again on the leases' thread)
        self._depth_at, now = self.clock(), self.wall() if now is None else now
        try:
            closed = int(self.store.status().get("firstBlockId", 0)) > 0
            depths = {str(r["id"]): round(self.store.depth_days(str(r["id"]), now), 2) for r in self.rows}
        except ArchiveError:                         # a volume that is away says nothing about depth
            return self.depths
        self.depths = depths
        for row in self.rows:
            # `rows.number`: `nan` or `inf` days passed the row's `float` and raised `archive.shallow` every day for a
            # floor no depth meets (the ninth pass, sibling A's table) — read as not said, counted once and logged
            unit = str(row["id"])
            floor = number(f"rec/recordings/{unit}#min_depth_days", row.get("min_depth_days") or None, float, 0.0)
            if not floor or not closed or depths[unit] >= floor:
                self.shallow.pop(unit, None)
                continue
            if now - self.shallow.get(unit, -1e18) < self.SHALLOW_AGAIN or unit not in self.epochs:
                continue
            self.shallow[unit] = now
            EventLog(self.archive_root, REC.name, unit, self.epochs[unit]).append(
                now, "archive.shallow", cls=ALARM, cam=row.get("cam"), depth_days=depths[unit], min_depth_days=floor)
            logging.warning("%s: recording %s holds %.1f day(s) and was promised %.0f: the ring of %s has closed",
                            self.name, unit, depths[unit], floor, self.volume)
        return self.depths

    # THE PLACE, WHILE THE STORE IS SILENT (feedback BK). `volume_pass` reads the declared volumes and renews the
    # hold; a store that does not answer raises out of it, and nothing is let go for that — not reading the
    # list is not "nothing is declared", and not reading the hold is not "somebody else holds it".
    #
    # How long that lasts depends on whose the place is:
    #
    #   a disk of this server     stays this recorder's for as long as the silence lasts. Nobody else can write
    #                             to it: it is here
    #   a network archive         any box may serve it, and one that can reach the store will take the hold when
    #                             it lapses. Two writers in one archive is not a duplicate, it is damage — so
    #                             when the hold has gone `slot_ttl − margin` unconfirmed, it is let go, and its
    #                             recordings stop. The one case where silence still stops a recording
    #
    # From that moment the fence refuses every sample (`_may_write_volume`; the review's fifth pass, blocker 1), and the
    # writer is still closed — its flush is the last minutes — while nobody else may have taken the hold: until
    # `slot_ttl + HOLD_SKEW`, what a claimant waits (`_may_close_volume`). A pass that comes later than that — the box
    # was frozen — gives the writer up instead (`_close_store`).
    def lease_pass(self) -> list[str]:
        lost = super().lease_pass()
        if self.recording_allowed:                   # a fenced instance decides nothing about volumes
            try:
                self.volume_pass()
            except OSError as e:
                self.store_errors += 1
                quiet = self.clock() - self._hold_confirmed
                if self.hold is not None and self.hold in self._shared and quiet >= self.slot_ttl - self.lease_margin:
                    self.leave_volume(f"the hold on network archive {self.hold} has not been confirmed for {quiet:.0f} s "
                                      f"(the store does not answer: {e})")
                else:
                    logging.warning("%s: the store did not answer for the volumes (%s); still writing into %s",
                                    self.name, e, self.volume or "nothing")
                    self._remount_by_last()
            except PARSE_ERRORS as e:
                # A ROW THAT DOES NOT PARSE is the row's trouble, not the lease step's (the review's seventh pass, part
                # 2, blocker 1): it went out of here to the loop's one `try`, and the heartbeat after it never went.
                # The rows are read past such a row (`_declared`); whatever still raises one here — a row read on the
                # way, a pinned volume never read whole — leaves the recorder writing where it writes, said in
                # `volume_error` and once in the log, and the depth below is still measured.
                self.volume_error = f"a row of the store does not parse: {e}"
                if self._volume_garbled_said != str(e):
                    self._volume_garbled_said = str(e)
                    logging.error("%s: the volume step met a row that does not parse (%s); still writing into %s",
                                  self.name, e, self.volume or "nothing")
                self._remount_by_last()
            else:
                self._volume_garbled_said = ""
            self.depth_pass()
        return lost

    # THE ENGINE LOST WHILE THE STORE IS SILENT (the review's third pass). `volume_pass` begins by reading the declared
    # volumes; a store that does not answer raised out of it before anything was opened again — so a daemon that
    # restarted during the store's election left the recorder with no writer for the whole silence. The rows read
    # last say where this recorder writes; it mounts by them — a disk of this server at once, and a network volume
    # only while the term of its last confirmed hold outlasts what a mount can take (`_confirm_hold`); past that
    # another box may hold it, and the branch above lets it go.
    def _remount_by_last(self) -> None:
        self._check_lost()
        vol = self._vol_last
        if vol is None or not (self.store is None or self.engine_lost):
            return
        if vol.name not in (self.hold, self.default_volume) and (not self.pinned or volumes.any_box(vol)):
            return                                   # a network volume is mounted only under its hold, pinned or not
        err = self._write_into(vol)
        if err is not None:
            log.warning("%s: %s could not be mounted again by its last known row: %s", self.name, vol.name, err)

    # The volume is taking nothing: it said so (`archive_error`), or nothing is open. Backfill — planned or asked
    # for — waits then: there is nowhere to land what it would fetch.
    #
    # What it does NOT wait for is a full disk. The footage is in a ring formatted at its quota: it never grows
    # past it, and a range fetched now is written at the ring's head, the newest block, overwritten last. The
    # chase the watermark used to guard against — the resource freeing hours, backfill fetching the same hours
    # back — has nothing to chase.
    def archive_busy(self) -> bool:
        return bool(self.archive_error) or self.store is None or self.store.writer is None

    def pump_once(self) -> None:
        super().pump_once()
        # Bounded, inside the window — it shares the device's uplink — and never while the volume is taking
        # nothing. The operator's requests go the same way (`serve_requests`).
        if not self.archive_busy():
            self.backfill_in_background()
        if self.incidents and not self.archive_busy():
            self.keeps_in_background()

    # Not on the loop's thread: an operator's request is a range off the camera's card, minutes long, and it ran
    # where the leases are renewed and the heartbeat goes out (the review's first pass, B3). It is served on the
    # backfill thread, before the planned ranges — a person asked for that hour.
    def serve_requests(self) -> None:
        pass

    # -- backfill: closing our gaps from the device's own archive (Lesson 16) ---------------------------
    # The card exists because the camera kept recording while we could not, so replication is not "copy
    # everything" — it is the difference between two coverages. Desired: continuous. Actual: what the volume's
    # index shows, every stream of the recording — live and fetched, every epoch. The difference is the work.
    # Lesson 2's loop, over time instead of pipelines.
    def our_coverage(self, unit) -> list[tuple[float, float]]:
        if self.store is None:
            return []
        try:
            return self.store.coverage(str(unit), self.stitch)
        except ArchiveError:
            return []

    # What a source has and we do not, bounded at both ends. Not older than what the doors would SHOW — the
    # row's `retention_days` (`visible_from`) — nor than `keep_days`: a range fetched past the ceiling is a range
    # nobody will be shown.
    #
    # Not newer than what we can SEE (the feedback's Q). A reader sees only blocks written to the volume — when one
    # fills, or `BLOCK_FLUSH_S` after a sequence reached the writer's queue (feedback CP). Everything after the end of our visible coverage is
    # either being written this minute or written and not yet visible, and there is no need to tell the two
    # apart: neither is a gap. The visible end is the lag MEASURED; `settle` stays as the floor, and is all
    # there is for a recording with nothing visible.
    #
    # PLANNED backfill starts at our first visible second (the feedback's S). Before it the recording was not
    # running by design — created yesterday, or a recording on events — and filling it from the card would
    # turn a recording on events into a recording always, a night late. An operator's request is not
    # planned: a person asked for that hour, and may ask for any hour.
    #
    # And never what a clean fetch from THIS source already found nowhere, nor what the engine refused of it
    # `REFUSED_TIMES` times (`_refused`) — forgotten once older than anything planned, so neither list grows for ever.
    # This recorder's row of `unit`, from a map of the rows read last — made again when they are read again. The backfill
    # asked it per recording by walking the rows: the square of them, in Python, every pass (the scaling pass).
    def _row_of(self, unit) -> dict | None:
        rows, by_id = self.__dict__.get("_rows_by_id", (None, {}))
        if rows is not self.rows:
            by_id = {}
            for r in self.rows:
                by_id.setdefault(str(r["id"]), r)            # the first, as the walk found it
            self._rows_by_id = (self.rows, by_id)
        return by_id.get(str(unit))

    def gaps(self, unit, coverage: dict, now: float, planned: bool = True, source: str = "device") -> list[tuple[float, float]]:
        from .archive import visible_from
        ours = self.our_coverage(unit)
        row = self._row_of(unit)
        # What a source says it holds, through `rows.number` (the review's seventh pass): a word there raised out of the
        # backfill of every recording after this one. Not said, nothing to fetch from it.
        c = coverage if isinstance(coverage, dict) else {}
        start = number(f"rec/coverage/{source}/{unit}#from", c.get("from"), float, None)
        end = number(f"rec/coverage/{source}/{unit}#to", c.get("to"), float, None)
        if start is None or end is None:
            return []
        lo = max(start, now - self.keep_days * 86400, visible_from(row, now))
        hi = min(end, now - self.settle, ours[-1][1] if ours else now)
        if planned:
            if not ours:
                return []
            lo = max(lo, ours[0][0])
        if hi <= lo:
            return []
        holes = subtract((lo, hi), ours)
        for gone in self.nowhere.get((str(unit), source), []):
            holes = [h for hole in holes for h in subtract(hole, [gone])]
        if (str(unit), source) in self.given_up:
            kept = self.given_up[(str(unit), source)] = [sp for sp in self.given_up[(str(unit), source)]
                                                         if sp[1] > now - self.keep_days * 86400]
            for gone in kept:
                holes = [h for hole in holes for h in subtract(hole, [gone])]
        pending = [sp for sp in self.landing.get(str(unit), []) if subtract(sp, ours)]   # still not shown by the volume
        self.landing[str(unit)] = pending
        for sp in pending:
            holes = [h for hole in holes for h in subtract(hole, [sp])]
        return holes

    # Local time, and the one place in the course where that is right: "at night" is night where the camera
    # is, not where the server is. `(22, 6)` wraps midnight — without that branch it would never arrive.
    def in_window(self, now: float) -> bool:
        if not self.window:
            return True
        h = time.localtime(now).tm_hour
        a, b = self.window
        return a <= h < b if a < b else (h >= a or h < b)

    # `(cam, playback_url, coverage)` for a recording whose camera is held by a worker that serves the
    # device's own archive — found the way everything is found here: in the holder's heartbeat.
    def device_source(self, cam) -> tuple[str, dict] | None:
        found = self._look().holder("vms", cam, self.wall(), field="playback_url")
        if found is None or not found[2].get("coverage"):
            return None                       # no phase: a channel held only for its archive answers too
        from .config import local_only
        if local_only(found[2]["playback_url"], found[1].extra.get("server", "?"), self.server):
            return None                       # the holder's archive door is on ITS loopback: not a source from here
        from .playback import process_url     # the door asks a gated cluster's processes for this camera's capability
        return process_url(found), found[2]["coverage"]

    # -- the backup archive: a recording of the same camera on a backup volume (Lesson 26) ----------------
    # Found the way everything here is found — in heartbeats: a recording of this camera, homed on a backup
    # volume, run by a recorder that is alive, says what it holds and serves its archive. `self` is never its
    # own source, and a backup fetches from nobody.
    #
    # THE CARD IS ASKED, NOT OPENED (the product's camera; feedback CB, DG). A recording on a camera's card says what it
    # holds like any backup — `coverage` in its recorder's heartbeat, every ten seconds — and serves no door: the card is
    # the camera's buffer, not a volume of the engine, and a camera is a box nobody can dial. Its frames come as the
    # camera's ANSWER to a range: the range goes to the camera in the answer to its poll, the camera uploads it (М12
    # Lesson 16). `card_range(src, t0, t1)` is that request, set by whoever runs this recorder — the ingest; unset,
    # nobody here can ask the camera, and the card is not a source. A card that could not read the range raises
    # (`OSError`): the copy fails and is asked again on a later pass — never an empty answer taken for "not on the card".
    # `src["recording"]` is the recording ON THE CARD the range is of, and whoever asks the camera must say it: a card
    # holds as many recordings as its camera has rows homed on it (the review's sixth pass).
    #
    # ASKED AGAIN, BUT NOT AT ONCE (the review's sixth pass). A range that failed was asked again on the next pass, and
    # the pass after: a camera that answers a second later than it is waited for read its card four times for four
    # failures. A source that failed a range is not a source for a while — `SOURCE_BACKOFF`, doubling to
    # `SOURCE_BACKOFF_MAX`, with jitter, so a site's cameras that failed together are not asked together — and the pass
    # goes on to the recording's other sources and to other recordings meanwhile. One range landed forgets it. The
    # same for a backup recorder's door, the neighbour on this path: a door whose volume is away read the same minute
    # for every pass that asked it.
    card_range = None                                    # (src, t0, t1) -> [Sample], set by whoever runs this recorder
    SOURCE_BACKOFF, SOURCE_BACKOFF_MAX = 5.0, 600.0

    def _source_waits(self, key: str) -> bool:
        return self.clock() < self._source_asks.get(key, (0, float("-inf")))[1]

    def _source_answered(self, key: str, failed: bool) -> None:
        if not failed:
            self._source_asks.pop(key, None)
            return
        n = self._source_asks.get(key, (0, 0.0))[0] + 1
        delay = min(self.SOURCE_BACKOFF * 2 ** n, self.SOURCE_BACKOFF_MAX) * (0.5 + random.random() * 0.5)
        self._source_asks[key] = (n, self.clock() + delay)

    # The look this thread's pass is taking, per recorder (`Look`, `one_look`); outside a pass every question takes a
    # look of its own — one read of each part, as one question always cost.
    _LOOKS = threading.local()

    @contextlib.contextmanager
    def looking(self):
        looks = self._LOOKS.__dict__.setdefault("by", {})
        if id(self) in looks:
            yield looks[id(self)]
            return
        looks[id(self)] = look = Look(self)
        try:
            yield look
        finally:
            looks.pop(id(self), None)

    def _look(self) -> Look:
        return look_of(self)

    # Every recording's row, parsed — and one that does not parse passed by (`Worker.row_garbled`; the sixth pass, the
    # follow-up). The recorder walks ALL of them to answer a question about one — who else records this camera,
    # which backup holds it, what a keep names — and parsed each bare: one garbled row, and no backup's pipeline
    # started, no range was fetched and no keep was copied, for any recording. Read once a pass (`Look`).
    def _recordings(self, deleted: bool = False) -> list[dict]:
        return self._look().recordings(deleted)

    # Found in this pass's look (the scaling pass): the camera's other recordings from the map by camera, their
    # recorders' entries from the map by recording — a thousand recordings asked this once each, and each asking read
    # every row twice and every recorder's heartbeat.
    def backup_sources(self, row: dict, now: float | None = None) -> list[dict]:
        now = self.wall() if now is None else now
        look = self._look()
        names = look.backups()
        if not names or volumes.is_backup(row, names=names):
            return []
        recs = {str(o["id"]) for o in look.by_cam().get(str(row["cam"]), ())
                if str(o["id"]) != str(row["id"]) and volumes.is_backup(o, names=names)}
        out, edge_homes, homes = [], look.edges(), look.homes()
        from .config import local_only
        units = look.units(self.SUB.name)
        for name, _, hb, st in sorted((e for rid in recs for e in units.get(rid, ())), key=lambda e: e[:2]):
            if not is_live(self.SUB.name, hb.ts, now, self.LOST_AFTER):
                continue                      # silent, or a clock from the future (M9 of the review): not a source
            if not st.get("coverage"):
                continue
            url = hb.extra.get("archive_url", "")
            if url and local_only(url, hb.extra.get("server", "?"), self.server):
                url = ""                      # that recorder's archive door is on its own loopback: not reachable from here
            kind = "edge" if homes.get(str(st["id"])) in edge_homes else "backup"
            if (kind == "backup" and not url) or (kind == "edge" and self.card_range is None):
                continue                      # no door to a backup, nobody to ask the camera: not a source from here
            if self._source_waits(f"{kind}:{st['id']}"):
                continue                      # it failed a range just now: not asked again yet (`_source_answered`)
            out.append({"key": f"{kind}:{st['id']}", "kind": kind, "recording": str(st["id"]), "cam": str(row["cam"]),
                        "recorder": name, "url": url.rstrip("/") if kind == "backup" else "",
                        "coverage": st["coverage"]})
        return out

    # Where one recording's gaps can come from, in order: the device's own archive (Lesson 16), then every
    # backup recording of the same camera.
    def sources_of(self, row: dict) -> list[dict]:
        out = []
        dev = self.device_source(row["cam"])
        if dev is not None:
            out.append({"key": "device", "kind": "device", "url": dev[0], "coverage": dev[1]})
        return out + self.backup_sources(row)

    # The backup's FRAMES, through its recorder's door: the samples of a range as its volume holds them, with
    # the times they were recorded at — what goes into our own volume as they are. The plan came from the
    # summary in the heartbeat; what is copied is what the door hands over.
    # A PIECE of a range, not a range (`_pieces`): what is read here is held whole. The door streams its answer, and a
    # stream cut short — the door's volume went away half way — is an error, never a shorter range taken for what
    # the source holds: the door writes its last chunk only when the stream was whole (`send_route`), and an answer
    # without it is `IncompleteRead` here (the review's sixth pass: a cut between two sequences left whole records,
    # and nothing said they were not all).
    def read_samples(self, url: str, unit: str, t0: float, t1: float) -> list[Sample]:
        import http.client
        import struct
        import urllib.parse
        import urllib.request
        q = urllib.parse.urlencode({"from": t0, "to": t1})
        try:
            with urllib.request.urlopen(f"{url}/samples/{urllib.parse.quote(str(unit))}?{q}", timeout=30) as r:
                # an answer with neither chunks nor a length cannot be told whole from cut (the seventh pass, minor;
                # the console's `_door` refuses it the same way) — and a length that is not a number is none (`framed`,
                # the eighth pass)
                if not framed(r):
                    raise OSError(f"{url}: the frames of {unit} came with neither chunks nor a length — whole or cut "
                                  f"cannot be told")
                data = r.read()
        except http.client.HTTPException as e:
            raise OSError(f"{url}: the frames of {unit} came cut short ({e!r})") from None
        try:
            return Sample.decode_all(data)
        except (ValueError, struct.error) as e:
            raise OSError(f"{url}: the frames of {unit} came cut short ({e})") from None

    # A range, about a minute at a time (`PIECE`; the review's third pass, blocker 6). Each piece is read whole and
    # handed on before the next is asked for, and the cut between two pieces is at a KEY FRAME: a piece ends where its
    # last group of pictures begins, and the next piece starts there. A cut anywhere else would split a group — the
    # half after the cut has no key frame to open a sequence on, and the half before it would be fetched again as
    # the next piece's lead-in. `read(t0, t1)` is a source's frames of a range; yields `(from, to, frames)`.
    def _pieces(self, read, t0: float, t1: float):
        from w2cplatform.obsd import unix_s
        at = t0
        while at < t1:
            hi = min(t1, at + self.PIECE)
            got = read(at, hi)
            nxt = hi
            if hi < t1:
                cut = next((i for i in range(len(got) - 1, -1, -1) if got[i].key and unix_s(got[i].begin) > at), None)
                if cut is not None:
                    nxt, got = unix_s(got[cut].begin), got[:cut]
            yield at, nxt, got
            at = nxt

    # How far back the doors show a recording: its row's `retention_days` (`visible_from`). A ceiling — the ring
    # decides what is still there; this decides what is SHOWN, and for some installations it is the promise that
    # matters: "nobody sees more than a week". A recording whose row is gone shows thirty days.
    #
    # A row the store did not GIVE is not a row that is gone (feedback BI). Read as "gone" it would show a week's
    # recording for thirty days, or hide ninety days' recording past thirty, for as long as the store blinked. So
    # the door answers on what the row said last; thirty days only for a recording it has never read.
    def _visible_from(self, unit) -> float:
        from .archive import visible_from
        if self.incidents:
            return 0.0                                # everything in an incidents volume is there because somebody kept it
        try:
            items, _ = self.vars.get(self.SUB.config(self.ROWS, str(unit)))
            row = self._rows_seen[str(unit)] = items if items and items.get("deleted") != "true" else None
        except OSError:
            row = self._rows_seen.get(str(unit))
        return visible_from(row, self.wall())

    # The intervals of a recording somebody said to keep (`vms/keeps.py`): the door shows them whatever the ceiling,
    # because a keep is the operator's word that those minutes matter longer than the recording's days — and the
    # recorder copying keeps into an incidents volume reads them through this very door. Not readable is none:
    # the ceiling stands, which hides, and hiding is the side to err on.
    def _kept_of(self, unit) -> list[tuple[float, float]]:
        from . import keeps
        try:
            declared = keeps.declared(self.vars)
        except OSError:
            return []
        row = self._rows_seen.get(str(unit)) or {}
        return keeps.spans_of(declared, str(unit), str(row.get("cam", "")))

    # Since when this recorder writes `unit` into the volume it holds: when it took the recording's epoch (an epoch is
    # given up with the volume — `leave_volume` — so it never spans two). None when it does not write it (the review's
    # seventh pass: what a keep's copier lets this door say "nothing here" for).
    def take_epoch(self, unit: str) -> int:
        epoch = super().take_epoch(unit)
        self._epoch_at[str(unit)] = self.wall()
        return epoch

    def release(self, unit: str) -> None:
        super().release(unit)
        self._epoch_at.pop(str(unit), None)

    def _held_since(self, unit) -> float | None:
        if self.store is None or self.incidents or str(unit) not in self.epochs:
            return None
        return self._epoch_at.get(str(unit))

    # This recorder's archive, served: `/timeline/<unit>` and `/samples/<unit>?from&to` over the volume THIS
    # process holds (`archive_routes`). A backup recorder serves it so a primary can copy from it; the console
    # reads every recorder's to draw a camera's timeline and play it; any recorder may.
    #
    # Bounded like every door (the review's sixth pass: the protections were the console's alone): so many
    # connections at once and so many to one address, the next answered 503 (`door_server`); the request line and
    # headers under a deadline, a socket that says nothing let go (`Deadlined`). It asks nobody who they are — a door
    # between processes, until mutual TLS.
    def serve_archive(self, host: str = "127.0.0.1", port: int = 0):
        from http.server import BaseHTTPRequestHandler
        from w2cplatform.console import Deadlined, door_server
        routes = archive_routes(lambda: self.store, self.wall, lambda unit: self.epochs.get(str(unit)), self._visible_from,
                                self._kept_of, self._held_since)

        class H(Deadlined, BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                send_route(self, routes(self.path))

        srv = door_server((host, port), H)
        threading.Thread(target=srv.serve_forever, daemon=True, name="archive-door").start()
        from .config import announce_host
        self.archive_url = f"http://{announce_host(host, self.server)}:{srv.server_address[1]}"   # what it bound: loopback, or this server's name — never `0.0.0.0`
        return srv

    # -- what an operator asked for: `rec/requests/<id>`, written by the console ------------------------
    #
    # The ordinary pass is bounded by a budget and an hour because backfill competes with live for the
    # device's uplink. A range a PERSON asked for is different work: they are looking at that gap now, and
    # the night is not a useful answer. So these are fetched outside both — but not while the volume takes
    # nothing (`archive_busy`): the request waits, it is not refused.
    #
    # The request is not cleared here. A worker's token writes its slot and its epochs, never configuration
    # (М10A Lesson 10), so the recorder REPORTS what it fetched in its heartbeat and the console's reaper
    # removes the row — the same division as a scan that finishes (М10B Lesson 21).
    @one_look
    def requests(self, budget: int = 2, now: float | None = None) -> list[dict]:
        now = self.wall() if now is None else now
        if self.archive_busy():
            return []
        mine = {str(r["id"]) for r in self.rows}
        done: list[dict] = []
        keys = sorted(self.vars.list(REC.requests_prefix()))
        # A request answered is remembered while its ROW stands, and not after — the base worker's rule (`VmsWorker.
        # requests`), which this override did not keep: `fetched` grew by one id per request for the life of the
        # process, and a request whose row the console had not reaped yet was fetched again from its start (the
        # review's fourth pass, Т-m13). The same for how far each one got.
        present = {k.rsplit("/", 1)[1] for k in keys}
        self.fetched = [r for r in self.fetched if r in present]
        self._requested = {r: v for r, v in self._requested.items() if r in present}
        self._requests_read = {r: v for r, v in self._requests_read.items() if r in present}
        for key in keys:
            if len(done) >= budget:
                break
            # Answered, or another recorder's as its row said when it appeared: not read again (the holder's rule, the
            # review's seventh pass, M5 — every row of the family was read on every pass of every recorder).
            known = self._requests_read.get(key.rsplit("/", 1)[1])
            if key.rsplit("/", 1)[1] in self.fetched or (known is not None and known[0] not in mine):
                continue
            it, _ = self.vars.get(key)
            if it:
                self._requests_read[key.rsplit("/", 1)[1]] = (str(it.get("unit", "")), None)
            if not it or str(it.get("unit", "")) not in mine or key.rsplit("/", 1)[1] in self.fetched:
                continue                                     # another recorder's recording, or answered already
            # One family, two kinds of asking. A backfill names a RANGE and this worker fetches it; a
            # `record` names a DURATION and is not a worker's to serve at all — it becomes a row, and rows
            # are the console's. Skipping it here is what keeps the recorder from tripping over a request
            # that was never addressed to it (`it["from"]` would not be there).
            if str(it.get("action", "backfill")) != "backfill":
                continue
            unit, cam = str(it["unit"]), str(it.get("cam", it["unit"]))
            rid = key.rsplit("/", 1)[1]
            # Not past what we can see, while the recording is live: those minutes are in a block being written,
            # and fetching them would write them twice. A recording that is not running may be asked for anything.
            # …and a range that does not parse is THIS request's refusal (the review's sixth pass, the class of the
            # holder's commands): read bare, it raised out of `requests` on every pass, and no request behind it — any
            # recording's — was fetched. Answered, so the console clears the row.
            try:
                t0, t1 = float(it["from"]), float(it["to"])
            except (KeyError, TypeError, ValueError):
                log.error("%s: request %s refused: from=%r to=%r is not a range", self.name, rid, it.get("from"), it.get("to"))
                self.fetched.append(rid)
                done.append({"unit": unit, "cam": cam, "request": rid, "error": "`from` and `to` are not a range"})
                continue
            ours = self.our_coverage(unit)
            if unit in self.reconciler.actual:
                t1 = min(t1, ours[-1][1] if ours else now - self.settle)
            # `RANGE_CAP` of it a pass, from where the last pass stopped: a request for a day is not a day in one go
            # (blocker 6). Done — reported, and the console removes the row — when the last piece of it is.
            #
            # WHERE THE LAST PASS STOPPED survives a restart (the review's fourth pass, Т-B6): it was in memory only, and
            # a recorder started again read a day's request from its first minute — the hours it had landed fetched
            # once more, to be dropped group by group as ours already. What landed is in the volume, under this
            # recording's name: the request goes on from its first moment the volume does not show. Nothing is kept
            # beside the volume to say it, so nothing can say it wrongly; a stretch the source did not have is asked
            # for once more after a restart, and found not there again.
            t0 = max(t0, self._requested.get(rid, t0))
            if t1 <= t0:
                continue
            t0 = self._served_to(unit, ours, t0, t1)
            if t0 >= t1:                                     # the volume shows all that was left: nothing to fetch
                self._requested.pop(rid, None)
                self.fetched.append(rid)
                done.append({"unit": unit, "cam": cam, "from": float(it["from"]), "to": t1, "groups": 0, "request": rid})
                continue
            srcs = self.sources_of({"id": unit, "cam": cam, "home": (self._row_of(unit) or {}).get("home", "")})
            if not srcs:
                continue                                     # nobody holds the device and no backup answers; ask again next pass
            upto = min(t1, t0 + self.RANGE_CAP)
            # Each source in turn until one serves it. A source that FAILED says nothing about the range — the
            # request stays, for the next pass; reported as fetched, the console would delete what nobody served.
            r = {}
            for src in srcs:
                r = self.fetch_from(unit, cam, src, t0, upto)
                if not r.get("error"):
                    break
            if r.get("skipped") or r.get("error"):
                continue
            if upto < t1:
                self._requested[rid] = upto                  # the rest on the next pass
                done.append({**r, "request": rid, "partial": True})
                continue
            self._requested.pop(rid, None)
            self.fetched.append(rid)                         # the heartbeat says so; the console removes the row
            done.append({**r, "request": rid})
        return done

    # The first moment of `[t0, t1)` the volume does not show — `t1` when it shows all of it.
    def _served_to(self, unit: str, ours: list[tuple[float, float]], t0: float, t1: float) -> float:
        holes = subtract((t0, t1), stitch(ours + self.landing.get(unit, []), self.stitch))
        return holes[0][0] if holes else t1

    # Bounded work, on request — never in the ordinary pass, the way `rebalance(budget)` is bounded
    # (Lesson 13): backfill competes with live for the device's uplink, so it gets a ceiling and an hour.
    # Each of this recorder's recordings, from each of its sources in order — the device, then any backup —
    # and a backup recording from none: a backup fetches from nobody.
    # A fetch is a pipeline on the device's playback door, run to the end of the range: minutes, on a camera's
    # slow card — and it ran on the loop's thread, where the leases are renewed and the heartbeat goes out. A card
    # that took longer than the lease fenced the recorder and stopped the live recording of every camera it had,
    # to fetch an hour of one (the platform review; feedback BE). So it runs on a
    # thread of its own, one at a time, the pass waiting `BACKFILL_WAIT` for it and no longer.
    BACKFILL_WAIT = 0.5

    def backfill_in_background(self) -> None:
        if self._backfiller is not None and self._backfiller.is_alive():
            return                                       # one range at a time: the device has one uplink

        def fetch():
            try:
                self.requests()
            except OSError as e:                         # the requests are rows in the store: no store, none this pass
                self.store_errors += 1
                logging.warning("%s: the store did not answer for the requests (%s)", self.name, e)
            except Exception:                            # noqa: BLE001 — a thread has nobody to raise to
                logging.exception("%s: requests failed", self.name)
            try:
                if self.backfill_budget:
                    self.backfill(self.backfill_budget)
            except Exception:                            # noqa: BLE001
                logging.exception("%s: backfill failed", self.name)

        self._backfiller = threading.Thread(target=fetch, name=f"{self.name}-backfill", daemon=True)
        self._backfiller.start()
        self._backfiller.join(timeout=self.BACKFILL_WAIT)

    @one_look
    def backfill(self, budget: int = 1, now: float | None = None, force: bool = False) -> list[dict]:
        now = self.wall() if now is None else now
        if not (force or self.in_window(now)) or self.archive_busy():
            return []
        done: list[dict] = []
        names = self._look().backups()
        for row in self.rows:
            if len(done) >= budget:
                break
            if volumes.is_backup(row, names=names):
                continue
            for src in self.sources_of(row):
                for (t0, t1) in self.gaps(row["id"], src["coverage"], now, source=src["key"])[:budget - len(done)]:
                    # RANGE_CAP of a gap a pass: what is left of it is a gap on the next one
                    done.append(self.fetch_from(row["id"], row["cam"], src, t0, min(t1, t0 + self.RANGE_CAP)))
                if len(done) >= budget:
                    break
        return done

    # One range from one source. From the device: its playback door, as Lesson 16 wrote it — the actuator
    # hands back the frames. From a backup recording: its door's frames, with the times they were recorded at.
    # Either way what lands goes into OUR volume as ours, into the recording's backfill stream.
    def fetch_from(self, unit, cam, src: dict, t0: float, t1: float) -> dict:
        if src["kind"] == "device":
            return self.fetch(unit, cam, src["url"], t0, t1)
        unit = str(unit)
        if not self.may_record(unit):
            return {"unit": unit, "cam": str(cam), "from": t0, "to": t1, "skipped": "no lease"}

        def read(a, b):
            self.actuator.range_error = ""
            if src["kind"] == "edge":
                return self.card_range(src, a, b)        # the camera's answer to a range of its card
            return self.read_samples(src["url"], src["recording"], a, b)
        try:
            out = self._land_pieces(unit, cam, read, t0, t1, src["key"])
        except OSError as e:
            self._source_answered(src["key"], failed=True)
            return {"unit": unit, "cam": str(cam), "from": t0, "to": t1, "error": f"{src['recording']}: {e}"}
        self._source_answered(src["key"], failed=False)
        return out

    # One range from the device: its frames, landed as OURS — our epoch, our volume, the backfill stream.
    def fetch(self, unit, cam, url: str, t0: float, t1: float) -> dict:
        unit = str(unit)
        if not self.may_record(unit):
            return {"unit": unit, "cam": str(cam), "from": t0, "to": t1, "skipped": "no lease"}

        def read(a, b):
            self.actuator.range_error = ""
            return self.actuator.record_range(unit, f"{url}?from={a}&to={b}", a, b)
        return self._land_pieces(unit, cam, read, t0, t1, "device")

    # A range landed piece by piece, into the volume the fetch STARTED on (`_land`). A piece that failed, or was
    # skipped, ends the range there: what landed before it stays landed, and the rest is asked for again — a failed
    # piece says nothing about what the source holds after it. The range is reported to the console ONCE, whole.
    def _land_pieces(self, unit: str, cam, read, t0: float, t1: float, source: str) -> dict:
        store = self.store                               # the volume this fetch is FOR (`_land`)
        out = {"unit": unit, "cam": str(cam), "from": t0, "to": t1, "groups": 0, "source": source}
        for a, b, samples in self._pieces(read, t0, t1):
            r = self._land(unit, cam, samples, a, b, source, store, report=False)
            out["groups"] += r.get("groups", 0)
            if r.get("skipped") or r.get("error"):
                out.update({k: r[k] for k in ("skipped", "error") if k in r})
                break
        if out["groups"]:
            self.closed = (self.closed + [f"{unit}|{t0:.0f}|{t1:.0f}"])[-self.CLOSED_REPORTED:]
        return out

    # What a fetch brought, landed. The overlap is checked a second time here, by GROUP OF PICTURES — from one
    # key frame to the next — because live recording may have reached the same minutes while we were fetching;
    # a group that would land on top of what we already have is dropped rather than written. Then, if the fetch
    # was CLEAN, whatever of the range the source did not deliver is remembered as nowhere for this source —
    # never after a fetch that failed half way, which says nothing about what the source holds.
    #
    # What was NOT on the source is what it did not DELIVER — not what our volume does not show after the fetch
    # (feedback AE): a range just copied is invisible until its block closes, and was being remembered as "not
    # on the card either" and never planned again. Delivered is what came back: landed, or dropped because live
    # recording had it already. And what landed and is not visible yet is `landing` — ours, not a hole.
    #
    # Landed into the volume the fetch STARTED on, under the lease this recorder still holds — not into whatever is
    # open now (the review's second pass): a fetch takes minutes, and in minutes the volume may have been handed
    # back and another taken, or the lease let go. After a release `epochs.get(unit)` is None, not 0 — epoch nought
    # is a keep's copy, never a backfill's. And `landing` is what LANDED, plus what live recording had already: a
    # group the engine refused, or one that began without a key frame, stays a hole and is asked for again.
    #
    # NOT FOR EVER (the review's fourth pass, an open item; the product's DD). A group the engine refuses for what is
    # IN it — no key frame to open on, larger than a block — is refused every time, and the recorder fetched it off
    # the card every pass. Each refused piece is counted (`_refused`) and given up at the third; a piece that lands,
    # or that live recording reached, is forgotten. A refused group also CLOSES the sequence it would have continued:
    # left open, the next group went on in it, and the index drew the refused stretch as footage — no hole, no
    # second fetch, and a picture of nothing on the timeline. And a sequence the engine took and then lost (put
    # answers `SEQUENCE_LOST`: taken, an earlier one lost) is the one finished before this one opened — no longer
    # landed, and refused like the rest. One lost in an earlier fetch cannot be told from here; that is only said.
    REFUSED_TIMES = 3
    REFUSALS_KEPT = 256                              # pieces counted at once; the oldest forgotten first

    def _land(self, unit: str, cam, samples: list[Sample], t0: float, t1: float, source: str, store=None,
              report: bool = True) -> dict:
        from w2cplatform.obsd import unix_s
        store = self.store if store is None else store
        epoch = self.epochs.get(unit)
        if store is None or store is not self.store or epoch is None or not self.may_record(unit):
            log.warning("%s: a range of %s fetched for a volume or a lease this recorder no longer holds is dropped", self.name, unit)
            return {"unit": unit, "cam": str(cam), "from": t0, "to": t1, "skipped": "the volume or the lease changed during the fetch"}
        have = stitch(self.our_coverage(unit) + self.landing.get(unit, []), self.stitch)   # landing is ours: not twice
        kept, groups, ours = 0, [], []
        for smp in samples:
            if smp.key or not groups:
                groups.append([smp])
            else:
                groups[-1].append(smp)
        delivered = stitch([(unix_s(g[0].begin), unix_s(g[-1].end)) for g in groups], self.stitch)
        last = None                                      # where the sequence being written ends
        seq, before, refused = [], [], []                # the open sequence's groups, the previous one's; what was refused
        for g in groups:
            span = (unix_s(g[0].begin), unix_s(g[-1].end))
            if overlaps(have, span):
                ours.append(span)                        # live recording got there while we were fetching: ours already
                continue
            if not g[0].key:
                refused.append(span)
                continue                                 # no key frame to open on: a hole, asked for again
            try:
                # A sequence is CONTINUOUS to the index: a hole inside one is drawn as footage. So what the source
                # did not have — or what was dropped above — ends the sequence, and the next group opens another.
                if last is not None and span[0] - last > self.stitch:
                    store.finish(unit, epoch, backfill=True)
                    seq, before = [], seq
                last = span[1]
                for smp in g:
                    if store.put(unit, epoch, smp, backfill=True) == "SEQUENCE_LOST":
                        log.warning("%s: %s lost a fetched sequence before %.0f", self.name, unit, span[0])
                        ours = [sp for sp in ours if sp not in before]
                        kept, refused, before = kept - len(before), refused + before, []
                    self._offered_extra += len(smp.body)
                kept += 1
                ours.append(span)
                seq.append(span)
            except Unavailable:
                self._lost_engine()
                break
            except ObsdError as e:                       # the engine refused the group: the next one opens on its key
                log.warning("%s: %s refused a fetched group at %.0f: %s", self.name, unit, span[0], e.name)
                refused.append(span)
                last, seq, before = None, [], seq
                try:
                    store.finish(unit, epoch, backfill=True)
                except Unavailable:
                    self._lost_engine()
                    break
                except ObsdError:
                    pass                                 # nothing open to close
        if ours:
            self.refusals = {k: v for k, v in self.refusals.items() if k[0] != unit or not overlaps(ours, v[1:])}
        self._refused(unit, source, refused)
        if kept:
            # In the `try` too (the review's fourth pass): the engine gone between the last sample and this finish
            # raised out of `_land`, every request of the pass with it, and what had landed was not counted.
            try:
                store.finish(unit, epoch, backfill=True)
            except Unavailable:
                self._lost_engine()
            except ObsdError as e:
                log.warning("%s: the fetched range of %s was not finished: %s", self.name, unit, e.name)
        self.backfilled += kept
        self.landing[unit] = stitch(self.landing.get(unit, []) + ours, self.stitch)
        failed = getattr(self.actuator, "range_error", "")
        if not failed:
            missing = subtract((t0, t1), delivered)
            if missing:
                # touching pieces are one range: a hole fetched a minute at a time is remembered as the hole
                self.nowhere[(unit, source)] = stitch(self.nowhere.get((unit, source), []) + missing, 0.0)
        if kept and report:
            # What arrived is now ordinary footage — and a hole in the DETECTIONS, because nothing was
            # watching this camera while nothing was recording it. The console turns each of these into a
            # scan (М10B Lesson 22), so the two holes close together. Reported here and not written
            # anywhere: a worker's token writes no configuration. A range landed in pieces is reported once,
            # whole (`_land_pieces`).
            self.closed = (self.closed + [f"{unit}|{t0:.0f}|{t1:.0f}"])[-self.CLOSED_REPORTED:]
        out = {"unit": unit, "cam": str(cam), "from": t0, "to": t1, "groups": kept, "source": source}
        if failed:
            out["error"] = failed
        return out

    # One more refusal of each piece. A piece is known by its span ROUNDED to the stitch tolerance: the same group
    # fetched again comes back with the same frames, and a few milliseconds of a source's rounding are not another
    # piece. At `REFUSED_TIMES` it is given up for this source — logged, and remembered beside `nowhere`.
    def _refused(self, unit: str, source: str, spans: list[tuple[float, float]]) -> None:
        q = self.stitch or 1.0
        for a, b in spans:
            k = (unit, source, round(a / q), round(b / q))
            n = self.refusals.pop(k, (0,))[0] + 1         # popped and put back: the newest refusal is the last one forgotten
            if n < self.REFUSED_TIMES:
                self.refusals[k] = (n, a, b)
                continue
            self.given_up[(unit, source)] = stitch(self.given_up.get((unit, source), []) + [(a, b)], 0.0)
            log.error("%s: %s: %.0f–%.0f from %s refused by the engine %d times — given up", self.name, unit, a, b, source, n)
        while len(self.refusals) > self.REFUSALS_KEPT:
            del self.refusals[next(iter(self.refusals))]

    # -- keeps: a COPY in the incidents volume (feedback BH; the product's design) ---------------------------
    #
    # A volume is a ring, and a ring cannot spare a range: when its turn comes, kept footage is overwritten with
    # the rest. So the recorder holding an INCIDENTS volume copies every keep's minutes into it — out of whichever
    # recorder's door holds them, every recording of the keep's camera (`Keep.recordings` and any row naming the
    # camera now), as the stream `<recording>/e0`. Epoch nought: a copy is nobody's lease, and where the live
    # footage still exists its own epoch owns those minutes (`authoritative`); where the ring took it, the copy
    # is what is left. What one pass could not get — a door that is down, a recorder that moved — the next asks for
    # again: the keep stands until somebody lifts it.
    #
    #   archive.keep.copied   an event, when a pass copied something: the recording, the seconds, and the sha256
    #                         of the frames as the incidents volume now holds them — "is this what was kept"
    #   archive.keep.lost     an ALARM, when footage a keep held in the incidents volume is no longer there: its
    #                         own ring, full, took it. The answer is a larger quota, or an export
    #   archive.keep.uncopied an ALARM, when a keep has stayed short of what it names for `KEEP_UNCOPIED_AFTER`: no
    #                         door that answers from here has those minutes (the review's fourth pass). Said again
    #                         once a day while it lasts; the heartbeat says how much and since when, every pass
    #   archive.keep.garbled  an ALARM, when a keep's row has not parsed for `KEEP_GARBLED_AFTER`: its camera is held
    #                         as far as its interval reads and nothing of it is copied (`_keep_unreadable`). Said
    #                         again once a day while it lasts
    #
    # A keep is still not "for ever": the incidents volume is a ring too. It is only one that nothing else writes
    # into, so it turns as slowly as keeps arrive.
    KEEP_EVERY = 60.0
    KEEP_UNCOPIED_AFTER = 300.0                      # five passes: a door that blinked had its chance
    KEEP_GARBLED_AFTER = 3600.0                      # an hour: a row being mended by hand had its chance

    def keeps_in_background(self) -> None:
        if self._keeper is not None and self._keeper.is_alive():
            return
        if self.clock() - self._keep_at < self.KEEP_EVERY:
            return
        self._keep_at = self.clock()

        def run():
            try:
                self.keep_pass()
            except Exception:                            # noqa: BLE001 — a thread has nobody to raise to
                logging.exception("%s: copying keeps failed", self.name)

        self._keeper = threading.Thread(target=run, name=f"{self.name}-keeps", daemon=True)
        self._keeper.start()
        self._keeper.join(timeout=self.BACKFILL_WAIT)

    @one_look
    def keep_pass(self, now: float | None = None) -> dict:
        import hashlib
        from w2cplatform.events import ALARM, EventLog
        from . import keeps
        from .console import recorder_doors
        if not self.incidents or self.store is None:
            return {}
        now = self.wall() if now is None else now
        # A store that does not answer RAISES: unread is not "none". A keep whose row does not parse is skipped and
        # counted (`keeps.KEEPS`; the seventh pass) — it raised out of this pass, and no keep of anybody's was copied —
        # and what was copied of it is carried as it stands below, so its losses are still seen when it is mended.
        unread: list = []
        declared = keeps.declared(self.vars, unread)
        cams: dict[str, set] = {}
        for row in self._recordings():
            cams.setdefault(str(row["cam"]), set()).add(str(row["id"]))
        # Not a door on another server's loopback (the review's fourth pass): announced truthfully and not reachable from
        # here, it was asked every pass, refused, and the keep stayed uncopied with nothing to say why.
        from .config import local_only
        live = [(n, u, hb) for n, u, hb in recorder_doors(self.objects, now)
                if n != self.name and not local_only(u, str(hb.extra.get("server", "?")), self.server)]
        doors = [(n, u) for n, u, _ in live]
        state: dict[str, dict] = {}

        def inside(k, rec) -> float:                     # seconds of the keep this volume holds for `rec`
            return sum(min(b, k.until) - max(a, k.since) for a, b in self.store.coverage(rec) if b > k.since and a < k.until)

        def recordings_of(k) -> list[str]:               # what the keep names, and every recording of its camera now
            return sorted(set(k.recordings) | cams.get(k.cam, set()))

        if not self._keeps_read:
            self._keeps_read = True
            self.keep_held = {**self._keeps_held_before(declared, recordings_of, inside), **self.keep_held}
        for k in declared:
            got = missing = 0.0
            touched: list[str] = []
            for rec in recordings_of(k):
                # First what is GONE — before anything is copied, or a copy taken again from the recording's own
                # volume would hide that the incidents ring is too small to hold what it was given.
                now_in, before = inside(k, rec), self.keep_held.get((k.id, rec), 0.0)
                if now_in + 1.0 < before:
                    lost = round(before - now_in, 1)
                    EventLog(self.archive_root, REC.name, rec, 0).append(
                        now, "archive.keep.lost", cls=ALARM, cam=k.cam, keep=k.id, recording=rec, seconds=lost,
                        volume=self.volume)
                    logging.error("%s: %.0f s of keep %s (%s) are gone from %s: its ring took them",
                                  self.name, lost, k.id, rec, self.volume)
                gaps = subtract((k.since, k.until), self.store.coverage(rec))
                shown, speaks = self._doors_show(rec, k.since, k.until, doors) if gaps else ({}, [])
                for a, b in gaps:
                    for name, url in doors:
                        # Only what this door shows of the gap (the fifth pass): asked for the rest, it answered
                        # nothing, every minute, for ever.
                        have = [(max(a, x), min(b, y)) for x, y in shown.get(url, []) if min(b, y) > max(a, x)]
                        try:                             # in pieces (blocker 6): an hour's keep is not an hour in memory
                            copied = [self._copy_in(rec, smp) for lo, hi in have for _, _, smp in
                                      self._pieces(lambda x, y: self.read_samples(url, rec, x, y), lo, hi) if smp]
                        except OSError:
                            copied = []                  # that door is down: another may have it, the next pass asks again
                        if any(copied):
                            touched.append(rec)
                            break
                if rec in touched:
                    self.store.seal()                    # what was copied is readable now — and counted below
                self.keep_held[(k.id, rec)] = held = inside(k, rec)
                got += held
                missing += self._keep_short_of((k.id, rec), subtract((k.since, k.until), self.store.coverage(rec)), shown,
                                               speaks)
            entry = {"copied": round(got, 1), "missing": round(missing, 1)}
            self._keep_uncopied(k, entry, missing, now)
            for rec in sorted(set(touched)):
                h, size = hashlib.sha256(), 0
                for smp in self.store.stream(rec, k.since, k.until):     # the digest a sequence at a time, as the copy
                    raw = smp.encode()
                    h.update(raw)
                    size += len(raw)
                digest = h.hexdigest()
                # Durable, with how much of the keep the volume held: what `keep_held` is restored from when this
                # recorder starts again — in memory only, a restart forgot what had been copied, and the incidents
                # ring taking it afterwards raised no `archive.keep.lost` (the review's third pass, a minor).
                EventLog(self.archive_root, REC.name, rec, 0).append(
                    now, "archive.keep.copied", durable=True, cam=k.cam, keep=k.id, recording=rec, bytes=size,
                    sha256=digest, seconds=round(self.keep_held.get((k.id, rec), 0.0), 1), volume=self.volume)
                entry.setdefault("sha256", {})[rec] = digest
            if "sha256" not in entry and k.id in self.keep_state and "sha256" in self.keep_state[k.id]:
                entry["sha256"] = self.keep_state[k.id]["sha256"]
            state[k.id] = entry
        for k in unread:                                 # not read is not lifted: what it holds stays counted
            state[k.id] = {**self.keep_state.get(k.id, {}), "garbled": True}
            self._keep_unreadable(k, state[k.id], now)
        self.keep_held = {kr: v for kr, v in self.keep_held.items() if kr[0] in state}
        self._keep_nowhere = {kr: v for kr, v in self._keep_nowhere.items() if kr[0] in state}
        self._keep_short = {kid: v for kid, v in self._keep_short.items() if kid in state}
        # Parsed again, or lifted: that episode is over, and the next garbling is a new one.
        self._keep_garbled = {kid: v for kid, v in self._keep_garbled.items() if state.get(kid, {}).get("garbled")}
        self.keep_state = state
        return state

    # WHAT A KEEP IS SHORT OF is what a SOURCE has and this volume does not (the review's fifth pass). Every recording
    # of the keep's camera was counted over the keep's whole interval: a camera recorded for an hour as `7` and for a
    # minute as `7-ev`, a ten-minute keep copied whole — and `7-ev` was nine minutes short for ever, the alarm and
    # `rec_keep_missing_seconds` with it, its doors asked every minute. Now the doors that answer from here say what
    # they hold of the recording in the keep's interval (`_doors_show`), only that is copied, and only that, not here,
    # is short. A recording no door from here answers for at all is short by all it lacks, as before: nobody can say
    # it is not there.
    #
    # AND A DOOR SAYS "THE SOURCE HAS NONE" ONLY FOR WHAT ITS VOLUME COULD HOLD (the review's sixth pass, and its seventh).
    # Any door that answered was believed: the recording's own door unreachable, another camera's door answering
    # "nothing of it here" — true of every door but the right one — and the keep was `copied 0, missing 0`, no alarm,
    # while the recording's ring went on towards the kept minutes. The sixth pass believed the door of the recorder
    # that holds the recording NOW — and a recording that moved was the same failure again: the kept minutes on `v1`,
    # its door down, the recording held by `r-v2` on `v2` since afterwards — `r-v2` truthfully had none of them, and the
    # keep was whole by that (the seventh pass). A door speaks for the stretches its volume was the recording's place in
    # (`_speaks_for`): from the first to the last moment of each of the recording's epochs it shows — one epoch is one
    # writer in one volume, so a hole inside it is a hole — and, for the recorder that holds the recording now, from
    # when it took its epoch on (`held_since` in the door's timeline). What no answering door speaks for stays short: no
    # volume that answers could have held it, so nobody can say it is not there. What doors have said is remembered per
    # (keep, recording) (`_keep_nowhere`) — a recording deleted afterwards has nobody to say it again — and forgotten
    # where a door shows the footage after all.
    def _keep_short_of(self, key: tuple[str, str], short: list, shown: dict, speaks: list) -> float:
        everything = stitch([sp for spans in shown.values() for sp in spans], 0.0)
        gone = [p for g in self._keep_nowhere.get(key, []) for p in subtract(g, everything)]
        said = [(max(a, x), min(b, y)) for a, b in short for x, y in speaks if min(b, y) > max(a, x)]
        gone = stitch(gone + [p for want in said for p in subtract(want, everything)], 0.0)   # the source does not have these either
        self._keep_nowhere[key] = gone
        return sum(b - a for want in short for a, b in subtract(want, gone))

    # What each door that answers shows of a recording in `[since, until)` — `{url: [(start, end)]}`; a door that is down
    # is not in it, one that has nothing is, with nothing — and the stretches the answering doors speak for, together.
    def _doors_show(self, rec: str, since: float, until: float, doors: list) -> tuple[dict, list]:
        shown, speaks = {}, []
        for _, url in doors:
            try:
                spans, held = self._door_timeline(url, rec, since, until)
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue                                 # that door is down, or said nothing readable: nothing about what it has
            shown[url] = stitch([(sp["start"], sp["end"]) for sp in spans], 0.0)
            speaks += self._speaks_for(spans, held)
        return shown, stitch(speaks, 0.0)

    # The stretches one door's answer speaks for: each epoch's first to last moment of LIVE footage (a backfill lands
    # into its epoch's stream minutes the epoch never recorded; epoch nought is a keep's copy, nobody's writing), and
    # from `held` on — the recorder holds the recording under an epoch it took then, in the volume behind this door.
    @staticmethod
    def _speaks_for(spans: list[dict], held) -> list[tuple[float, float]]:
        runs: dict[int, tuple[float, float]] = {}
        for sp in spans:
            e = sp["epoch"]                              # read by `scan.door_spans`: an int
            if e <= 0 or sp.get("source", "live") != "live":
                continue
            a, b = runs.get(e, (sp["start"], sp["end"]))
            runs[e] = (min(a, sp["start"]), max(b, sp["end"]))
        return list(runs.values()) + ([(float(held), float("inf"))] if held is not None else [])

    # A door's timeline of one recording: `([{start, end, epoch, source, …}], held_since)`.
    #
    # Each span read alone, through the scan's parser (`scan.door_spans`; the review's eighth pass, part 4): `_speaks_for`
    # read `int(sp["epoch"])` outside the door's `try`, and one door answering `{"epoch": "e3"}` raised out of
    # `keep_pass` — no keep copied, none checked, `archive.keep.lost` never raised. A span that does not parse is passed
    # by and counted: this door then shows less and speaks for less, and what it would have covered stays short — the
    # side a keep must err on. An answer that is not `{spans: [...]}`, or larger than `rows.ANSWER_MAX`, is the door not
    # answering (`ValueError`, which `_doors_show` takes so).
    #
    # `held_since` IS THE DOOR'S CLOCK (the review's eighth pass, part 2, a minor): its recorder's wall when it took the
    # epoch, compared here with the keep's interval by this recorder's. A door 1200 s behind said it held the recording
    # 1200 s before it did, and spoke for minutes it never had — the shortfall halved (`missing 300` for 600). The door
    # says its own `now` beside it; `now - held_since` is an age neither clock skews, and it is laid on this recorder's
    # clock, read after the answer came — later than the door's moment, so the door speaks for less, never for more. A
    # door of an older build without `now` is taken as it stands.
    def _door_timeline(self, url: str, unit: str, t0: float, t1: float) -> tuple[list[dict], float | None]:
        import json
        import urllib.parse
        import urllib.request
        from w2cplatform.rows import answer, number
        from .scan import door_spans
        q = urllib.parse.urlencode({"from": t0, "to": t1})
        try:
            with urllib.request.urlopen(f"{url}/timeline/{urllib.parse.quote(str(unit))}?{q}", timeout=10) as r:
                body = json.loads(answer(r) or b"{}")
        except RecursionError as e:
            raise ValueError(f"{url}: a timeline nested too deep to read") from e
        spans, _ = door_spans(f"{REC.name}/doors/{url}#{unit}", body)
        held = number(f"{REC.name}/doors/{url}#held_since", body.get("held_since"), float, None)
        said_at = number(f"{REC.name}/doors/{url}#now", body.get("now"), float, None)
        if held is not None and said_at is not None:
            held = self.wall() - max(0.0, said_at - held)
        return spans, held

    # A KEEP THAT STAYS SHORT (the review's fourth pass). What a pass could not copy it asked for again on the next,
    # and said nowhere but in `missing`: the recording's door on another server's loopback, every pass `copied = []`,
    # the recording's own ring reaching the kept minutes — and `/metrics` said no keep was unprotected. Since when it
    # is short goes into the heartbeat (`missing_since`, beside `missing` — the console's `rec_keep_missing_seconds`),
    # and past `KEEP_UNCOPIED_AFTER` it is an alarm, once a day while it lasts.
    def _keep_uncopied(self, k, entry: dict, missing: float, now: float) -> None:
        from w2cplatform.events import ALARM, EventLog
        if missing <= 0:
            self._keep_short.pop(k.id, None)
            return
        since, said = self._keep_short.get(k.id, (now, None))
        entry["missing_since"] = since
        if now - since >= self.KEEP_UNCOPIED_AFTER and (said is None or now - said >= self.SHALLOW_AGAIN):
            unit = (sorted(k.recordings) or [str(k.cam)])[0]
            EventLog(self.archive_root, REC.name, unit, 0).append(
                now, "archive.keep.uncopied", cls=ALARM, cam=k.cam, keep=k.id, seconds=round(missing, 1),
                since=since, volume=self.volume)
            logging.error("%s: keep %s is %.0f s short of what it names, for %.0f s: no door that answers from here has "
                          "them", self.name, k.id, missing, now - since)
            said = now
        self._keep_short[k.id] = (since, said)

    # A KEEP THAT STAYS GARBLED (the review's eighth pass, part 4). A keep whose row does not parse holds its camera as
    # far as its interval reads — with a bound lost, from the start of time or to its end — and nothing of it is copied
    # (`keeps.as_far_as_read`). The console lists it (`garbled`, `garbled_since`), and nothing else said it: a row broken
    # by a hand edit held a camera's footage for good, and an operator who did not open the list never knew. Since when
    # this recorder has seen it so goes into the heartbeat (`garbled_since`), and past `KEEP_GARBLED_AFTER` it is an
    # alarm, once per keep and episode, again once a day while it lasts — as `_keep_uncopied`. Since when is this
    # recorder's sight of it: a recorder started again starts the hour again.
    def _keep_unreadable(self, k, entry: dict, now: float) -> None:
        from w2cplatform.events import ALARM, EventLog
        since, said = self._keep_garbled.get(k.id, (now, None))
        entry["garbled_since"] = since
        if now - since >= self.KEEP_GARBLED_AFTER and (said is None or now - said >= self.SHALLOW_AGAIN):
            unit = (sorted(k.recordings) or [str(k.cam)])[0]
            EventLog(self.archive_root, REC.name, unit, 0).append(
                now, "archive.keep.garbled", cls=ALARM, cam=k.cam, keep=k.id, since=since, volume=self.volume)
            logging.error("%s: keep %s of camera %s has not been readable for %.0f min: its camera's footage is held as "
                          "far as the keep can be read, and none of it is copied for safekeeping. Mend the keep or lift "
                          "it and set it again", self.name, k.id, k.cam, (now - since) / 60)
            said = now
        self._keep_garbled[k.id] = (since, said)

    # What this volume held of each keep when this recorder last said so: the last `archive.keep.copied` of each
    # (keep, recording), less the `archive.keep.lost` said after it — read from the events on this server, the
    # durable record of what was copied. What it held before is what a restarted recorder compares against, or the
    # ring taking kept footage during a restart would never be an alarm.
    #
    # AND WHAT THE VOLUME HOLDS NOW, whichever is more (the review's fourth pass, Т-m9). The events alone missed keeps:
    # an `archive.keep.copied` is written when the copy is made, outside the keep's interval, and goes with the event
    # tree's retention — and they were looked for under this recorder's own rows, which an incidents recorder has none
    # of, and the names the keep wrote down, not the recordings of its camera it was copied from. The incidents
    # volume's own `<recording>/e0` is the truth of what is there: a recorder starts from it for every recording of
    # every keep, and from an event that says MORE — the ring took some while nobody was looking — it raises the alarm.
    def _keeps_held_before(self, declared, recordings_of, inside) -> dict:
        from w2cplatform.events import alarm_tree, buckets_under, read_bucket, when
        ids = {k.id for k in declared}
        held: dict = {}
        for k in declared:
            for rec in recordings_of(k):
                if inside(k, rec) > 0:
                    held[(k.id, rec)] = inside(k, rec)
        lines = []
        for sub in (REC.name, alarm_tree(REC.name)):
            for unit in {r for k in declared for r in recordings_of(k)}:
                try:
                    for b in buckets_under(self.archive_root, sub, unit, 600):
                        lines += [e for e in read_bucket(os.path.join(self.archive_root, b.path))
                                  if e.get("keep") in ids and e.get("volume") == self.volume]
                except OSError:
                    continue
        said: dict = {}
        for e in sorted(lines, key=when):
            key = (str(e["keep"]), str(e.get("recording", "")))
            if e.get("kind") == "archive.keep.copied" and "seconds" in e:
                said[key] = float(e["seconds"])
            elif e.get("kind") == "archive.keep.lost" and key in said:
                said[key] = max(0.0, said[key] - float(e.get("seconds", 0)))
        for key, v in said.items():
            held[key] = max(held.get(key, 0.0), v)
        return held

    # Frames from another recorder's door into this volume, as `<recording>/e0`, one sequence per stretch — a hole
    # inside a sequence would be drawn as footage. What the door handed over starts on a key frame.
    def _copy_in(self, rec: str, samples: list) -> bool:
        from w2cplatform.obsd import unix_s
        last, kept = None, 0
        for smp in samples:
            if last is None and not smp.key:
                continue
            try:
                if last is not None and unix_s(smp.begin) - last > self.stitch:
                    self.store.finish(rec, 0)
                    if not smp.key:
                        last = None
                        continue
                self.store.put(rec, 0, smp)
                self._offered_extra += len(smp.body)
                kept += 1
                last = unix_s(smp.end)
            except Unavailable:
                self._lost_engine()
                return kept > 0                          # what went in before the engine went counts (the fourth pass)
            except ObsdError:
                # Refused: the next group opens on its key — in a sequence of its own (the review's fourth pass, an open
                # item). The one before is closed here; left open, the next group went on in it and the index drew the
                # refused stretch as footage.
                if last is not None:
                    try:
                        self.store.finish(rec, 0)
                    except Unavailable:
                        self._lost_engine()
                        return kept > 0
                    except ObsdError:
                        pass
                last = None
        if kept:
            try:
                self.store.finish(rec, 0)
            except Unavailable:
                self._lost_engine()
            except ObsdError:
                pass
        return kept > 0

    # A keep's id is a row's name, and a name stored before names were checked may hold a quote or a newline: written as
    # a label value by the one function that escapes it (`w2cplatform.console.label`; the review's eighth pass). And
    # whether this recorder waits for the volume it is pinned to (`volume_wait`), as the console's page says it.
    def metrics_text(self) -> str:
        from w2cplatform.console import label
        keeps = "".join(f'rec_keep_missing_seconds{{keep="{label(kid)}"}} {e.get("missing", 0)}\n'
                        for kid, e in sorted(self.keep_state.items()))
        return (f"# TYPE rec_recordings_running gauge\nrec_recordings_running {len(self.reconciler.actual)}\n"
                f"# TYPE rec_volume_wait gauge\nrec_volume_wait {1 if self.volume_wait else 0}\n"
                f"# TYPE rec_groups_backfilled counter\nrec_groups_backfilled {self.backfilled}\n"
                f"# TYPE rec_footage_dropped_seconds_total counter\nrec_footage_dropped_seconds_total {self.dropped_seconds:.1f}\n"
                + (f"# TYPE rec_keep_missing_seconds gauge\n{keeps}" if keeps else ""))


# A recorder's archive door, over the volume it holds: what a primary copies from a backup, and what the console
# draws and plays. Two reads, both from a FRESH reader — a reader sees what was closed when it mounted:
#
#   GET /timeline/<unit>?from&to   {"spans": [{start, end, epoch, source, bytes, fenced}], "current_epoch"}
#   GET /samples/<unit>?from&to    the frames, SMPL records one after another — each stretch from the epoch that
#                                  owns it, from a key frame (`Archive.stream`). STREAMED, a sequence at a time
#                                  (blocker 6: it built the whole range into one string — a day of a camera, in the
#                                  memory of the recorder serving it). No ceiling on the range: what is held is one
#                                  sequence whatever it is, the recorders ask in pieces (`RecWorker._pieces`), and the
#                                  console's export has a ceiling of its own (`EXPORT_MAX`)
#
# The frames' body is an ITERABLE of byte strings — or `b""` when there are none: whoever serves it writes each
# as it comes (`send_route`), and whoever wants them whole joins them (`frames_of`).
def frames_of(body) -> bytes:
    return body if isinstance(body, bytes) else b"".join(body)


# A route's answer, onto the wire. Bytes go with their length; an iterable of frames goes as it comes, with no
# length — and a volume that fails half way ends it early.
#
# AN ANSWER CUT SHORT SAYS SO (the review's sixth pass: the console's export took a door that failed for a file that
# ended). The stream had no framing: the connection's end was the answer's end, and the door writes a SEQUENCE at a
# time — so a volume that failed between two sequences left a reader with whole records and nothing to tell them
# from all there was: a shorter range, taken for what the source holds, by the console's export and by a recorder
# copying from a backup alike. To a client that speaks HTTP/1.1 — every reader here does — the frames go in chunks,
# and the last chunk is written only when the stream ended whole: a reply without it is an error to the reader
# (`http.client.IncompleteRead`; `RecWorker.read_samples`, the console's `_door`). In pieces, to a client that takes
# them (`w2cplatform.console.Paced`). An HTTP/1.0 client has only the end of the connection, as before.
def send_route(handler, got) -> None:
    from w2cplatform.console import Paced, start_stream
    if got is None:
        handler.send_response(404); handler.end_headers(); return
    status, body, ctype = got
    if isinstance(body, bytes):
        handler.send_response(status)
        handler.send_header("Content-Type", ctype)
        handler.send_header("Content-Length", str(len(body))); handler.end_headers(); handler.wfile.write(body)
        return
    out = Paced(handler, start_stream(handler, status, ctype))
    try:
        for chunk in body:
            out.write(chunk)
        out.end()
    except (ArchiveError, OSError) as e:
        log.warning("archive door: %s cut short: %s", handler.path, e)
    finally:
        close = getattr(body, "close", None)
        if close is not None:
            close()


def archive_routes(store_of, wall, current_epoch=lambda unit: None, visible_from=lambda unit: 0.0, kept=lambda unit: [],
                   held_since=lambda unit: None):
    import json
    from urllib.parse import parse_qs, urlsplit
    from w2cplatform.doors import safe_segment

    def routes(path: str):
        u = urlsplit(path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        for prefix in ("/timeline/", "/samples/"):
            if not u.path.startswith(prefix):
                continue
            unit = u.path[len(prefix):]
            if not safe_segment(unit):
                return 404, b"", "text/plain"
            store = store_of()
            if store is None:
                return 503, b'{"error": "no volume open here"}', "application/json"
            try:
                t0, t1 = float(q.get("from", 0)), float(q.get("to", wall() + 86400))
            except ValueError:
                return 400, b'{"error": "from and to are unix seconds"}', "application/json"
            # Retention is a ceiling on what the door shows: from `visible_from` on, and whatever a keep holds. A span
            # that began before the ceiling is CUT at it — drawn from its start, it would be footage the page shows
            # and the door then refuses to play.
            shown = stitch([(visible_from(unit), float("inf"))] + [tuple(k) for k in kept(unit)], 0.0)
            try:
                if prefix == "/timeline/":
                    cur = current_epoch(unit)
                    spans = []
                    for sp in store.timeline(unit, t0, t1, cur):
                        for a, b in shown:
                            lo, hi = max(sp["start"], a), min(sp["end"], b)
                            if hi > lo:
                                spans.append({**sp, "start": lo, "end": hi})
                    # …and since when this recorder writes the recording into this volume, if it does: what a keep's
                    # copier lets this door speak for beyond the footage it shows (`RecWorker._speaks_for`)
                    body = {"unit": unit, "spans": spans, "current_epoch": cur, "held_since": held_since(unit),
                            "now": wall()}             # the clock `held_since` is on, for a reader on another (`_door_timeline`)
                    return 200, json.dumps(body).encode(), "application/json"
                def frames():
                    for a, b in shown:
                        lo, hi = max(t0, a), min(t1, b)
                        if hi > lo:
                            for smp in store.stream(unit, lo, hi):
                                yield smp.encode()
                # The first frame is taken here: a volume that is away is a 503, said before the 200 goes out, and
                # nothing at all is an empty answer.
                body = frames()
                try:
                    first = next(body)
                except StopIteration:
                    return 200, b"", "application/octet-stream"

                def rest():
                    try:
                        yield first
                        yield from body
                    finally:
                        body.close()                     # the reader goes when the answer does, finished or not
                return 200, rest(), "application/octet-stream"
            except ArchiveError as e:
                return 503, json.dumps({"error": str(e)}).encode(), "application/json"
        return None
    return routes
