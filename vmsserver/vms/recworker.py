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

import logging
import os
import threading
import time

from w2cplatform.console import heartbeats, holder_of
from w2cplatform.contract import Subsystem
from w2cplatform.obsd import ObsdError, Sample, Session, Unavailable
from w2cplatform.objects import ObjectStore
from w2cplatform.variables import Variables

from . import volumes
from .archive import Archive, ArchiveError, classify, overlaps, stitch, subtract
from .config import rec_row
from .worker import FakeActuator, VmsWorker
from .writerwatch import WriterWatch

# What the domain's agent carries into THIS cluster about primaries recorded elsewhere (М12 Lesson 13), and
# where it says when it last reached the domain. Named here because the recorder is the reader; the agent writes.
PRIMARIES = "domain/primaries"
DOMAIN_SEEN = "domain/seen"

log = logging.getLogger("recworker")
REC = Subsystem("rec")


# What a recording's pipeline writes into: the volume's writer, under this recording's name and epoch. A
# sample the engine did not take raises, and the pipeline skips to the next key frame. A daemon that stopped
# answering is not an answer about the sample: the recorder is told, and remounts on its next pass (feedback CF).
class RecSink:
    def __init__(self, store: Archive, unit, epoch: int, on_lost=None, backfill: bool = False):
        self.store, self.unit, self.epoch, self.on_lost, self.backfill = store, str(unit), int(epoch), on_lost, backfill
        self.taken = self.refused = 0

    def put(self, sample: Sample) -> str:
        try:
            st = self.store.put(self.unit, self.epoch, sample, self.backfill)
            self.taken += 1
            return st
        except Unavailable:
            if self.on_lost is not None:
                self.on_lost()
            raise
        except ObsdError:
            self.refused += 1
            raise

    def finish(self) -> None:
        try:
            self.store.finish(self.unit, self.epoch, self.backfill)
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
    # How much of the past a held backup keeps in memory (Lesson 26). When the primary is found missing —
    # `START_GRACE` after it went quiet, plus a pass — the ring is written first, so the backup's footage
    # starts BEFORE the moment anybody noticed. Thirty seconds covers the grace, a pass and a keyframe.
    PREBUFFER = 30.0
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
    # How old the agent's last contact with the domain may be before the book of primaries it carried stops
    # counting (М12 Lesson 13). The same 45 s a heartbeat gets: past it, the backup cannot know whether the
    # primary in the other cluster is written, and records.
    CARRIED_LOST_AFTER = 45.0
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
        # WHICH VOLUME THIS RECORDER WRITES INTO — its place, in the sense `place_by: volume` means. Three
        # ways to be told, in this order:
        #
        # `$VOLUME` — PINNED. A disk is bolted to one machine, so the unit file that knows which disk this
        # instance mounts is the right place to say so, the way `$RECORDER_NAME` says which slot it is.
        # A pinned recorder takes no hold and gives none up.
        #
        # Nothing pinned and volumes DECLARED (`rec/volumes/*`) — the recorder takes one, by CAS, and is
        # that volume's recorder until it stops or lapses (`volume_pass`). This is what makes a network
        # archive created on the console get served without anybody starting a process for it.
        #
        # Nothing pinned and nothing declared — the SERVER's own volume, `file://$ARCHIVE/volume`, named after
        # the server: what every single-disk box meant before any of this existed — one place, `home: srv-a`
        # still true, `place_by: volume` behaving exactly like `place_by: server`.
        self.pinned = bool(env.get("VOLUME"))
        self.default_volume = str(self.server or "default")
        self.default_url = env.get("ARCHIVE_VOLUME") or f"file://{os.path.join(events_root, 'volume')}"
        q = default_quota if default_quota is not None else int(env.get("ARCHIVE_QUOTA_BYTES", "0") or 0)
        self.default_quota = q or self._share_of_free(events_root)
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
        self.refused: dict[str, tuple[float, str]] = {}   # volume -> (tried again after, why) — see REFUSED_FOR
        self._backfiller: threading.Thread | None = None
        # Is the WRITER writing (Lesson 10, feedback U): bytes offered to the sinks against what the volume
        # took — the ring's own count, `totalWritten`, from when this recorder opened it.
        self.writer = WriterWatch()
        self._written_at_open = 0
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
        self._hold_confirmed = self.clock()          # when `volume_pass` last ran to its end
        self.fed: dict = {}                         # recording -> (bytes offered, when that last grew): `last_frame_at`
        self.written_through: dict = {}             # recording -> capture time of the last frame its sink took (`note_written`)
        self._cover_since: dict = {}                # held backup -> when its primary was first found needing cover (CB)
        self.closed: list[str] = []                 # ranges fetched from a device: `<unit>|<from>|<to>`, for the console
        # What a clean fetch was asked for and did not get, per (recording, source) — the source does not
        # have it either (Lesson 16, the feedback's P). A summary in a heartbeat says where a card starts and
        # ends, never where its holes are; without this the same empty range is planned every pass, and each
        # plan opens one of the device's one or two sessions.
        self.nowhere: dict[tuple[str, str], list[tuple[float, float]]] = {}
        # What a source DELIVERED that our volume does not show yet (feedback AE): a reader sees a block only
        # once it is closed, so a range just copied shows minutes later. Until it does, the range is ours —
        # neither a hole to copy again nor, worse, something the source did not have.
        self.landing: dict[str, list[tuple[float, float]]] = {}
        self.archive_url = ""                       # this recorder's archive door, once served (Lesson 26)
        self._not_written_since: dict[str, float] = {}   # primary recording -> since when nobody writes it
        self.holding: dict[str, bool] = {}          # `when: offline` recording -> is its pipeline on hold now
        self._primary_back_since: dict[str, float] = {}  # released backup -> since when its primary is written again
        # KEEPS (feedback BH): a recorder holding an INCIDENTS volume copies into it what somebody said to keep
        # (`keep_pass`). What each keep holds there, as last seen, and what the last pass found.
        self.incidents = False                       # is the volume this recorder holds an incidents volume
        self.keep_held: dict[tuple[str, str], float] = {}   # (keep, recording) -> seconds of it in the volume
        self.keep_state: dict[str, dict] = {}        # keep -> {copied, missing, sha256}: for the heartbeat
        self._keeper: threading.Thread | None = None
        self._keep_at = -1e18
        self.waiting: set[str] = set()                                        # units with nobody holding their camera
        self.sources: dict[str, str] = {}                                     # what each running pipeline subscribed to

    # A volume nobody declared, on a disk nobody measured: four fifths of what is free under the resource,
    # leaving at least two gigabytes — the product's rule (feedback BM). Asked once, when it is first formatted;
    # a volume that exists keeps the size it has.
    @staticmethod
    def _share_of_free(root: str) -> int:
        try:
            import shutil
            os.makedirs(root, exist_ok=True)
            free = shutil.disk_usage(root).free
        except OSError:
            return 4 << 30
        return max(1 << 30, min(int(free * 0.8), free - (2 << 30)))

    # -- where a camera's stream is: the VMS heartbeat, never a call to the worker ------------------
    def source(self, cam) -> tuple[str, str] | None:
        """`(server, source)` of the worker holding the camera, from its heartbeat; None if nobody does.
        The source is the worker's shared-memory branch (`live_shm`, shm://…) when that worker is on
        THIS server — the same bytes with no RTSP hop, no fan-out process on the recording path — and
        its RTSP fan-out (`live_url`) otherwise."""
        found = holder_of(self.objects, "vms/", cam, self.wall(), phase="running", field="live_url")
        if found is None:
            return None
        _, hb, st = found
        server = hb.extra.get("server", "?")
        if server == self.server and st.get("live_shm"):
            return server, st["live_shm"]
        from .config import local_only
        if local_only(st["live_url"], server, self.server):
            # Announced truthfully and not for us: the fan-out is bound to loopback on ANOTHER server. Going to
            # that address would be knocking on our own machine. Said in the status, so the operator reads
            # "open RTSP_HOST on srv-b" instead of "camera held by nobody".
            self.behind_loopback[str(cam)] = server
            return None
        self.behind_loopback.pop(str(cam), None)
        return server, st["live_url"]

    # A recording's pipeline needs a source: `rtspsrc location=<live_url> ! archivesink` under this
    # recorder's epoch. No source (the camera is held by nobody yet) means "cannot start now": the
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
                   sink=RecSink(self.store, cam["id"], cam.get("epoch", 0), on_lost=self._lost_engine))
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
        if cam["id"] in self.fed:
            out["last_frame_at"] = self.fed[cam["id"]][1]
        if str(cam["id"]) in self.written_through:
            out["written_through"] = self.written_through[str(cam["id"])]
        if str(cam["id"]) in self.depths:
            out["depth_days"] = self.depths[str(cam["id"])]
            if str(cam["id"]) in self.shallow:
                out["shallow"] = True
        # A BACKUP recording says what it holds, the way Lesson 15's holder says what a card holds: a
        # summary, cheap to carry in every heartbeat. The primary plans from it, and what it copies is what the
        # backup's door hands over (Lesson 26).
        if volumes.is_backup(cam, self.vars):
            ours = self.our_coverage(cam["id"])
            if ours:
                out["coverage"] = {"from": ours[0][0], "to": ours[-1][1], "fragments": len(ours)}
        return out

    def status(self) -> list[dict]:
        out = super().status()
        for st in out:
            if st["phase"] != "running" and st["id"] in self.waiting and st["enabled"]:
                st["phase"] = "waiting"
            if st["phase"] == "running" and self.holding.get(str(st["id"])):
                st["phase"], st["why"] = "standby", f"the primary recording is being written; the last {self.PREBUFFER:.0f} s are held in memory"
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
        return str(row.get("when") or "") == "offline" and volumes.is_backup(row, self.vars)

    # One pass of the gate, after the reconciler's. A held backup whose primary now needs cover is RELEASED:
    # the ring is written first, then live. A released one whose primary has been back for `HOLD_AFTER` is
    # put on hold again — a restart under the same epoch, so its open sequence is finished, and the ring
    # starts filling afresh.
    def gate_pass(self, now: float | None = None) -> list[tuple[str, str]]:
        now = self.wall() if now is None else now
        done = []
        for row in self.rows:
            uid = str(row["id"])
            if not self._offline_backup(row) or uid not in {str(u) for u in self.reconciler.actual}:
                continue
            need = self.primary_needs_cover(row, now)
            if need:
                self._primary_back_since.pop(uid, None)
            if need and self.holding.get(uid) and self.resumes is not None and self.resumes(row):
                since = self._cover_since.setdefault(uid, now)
                if now - since < self.defer_for():
                    continue                                 # held in memory: the camera may yet continue the stream
            if not need and uid in self._cover_since:
                self._cover_since.pop(uid, None)            # back before the card had to write: nothing written (CB)
                done.append((uid, "back from memory"))
            if need and self.holding.get(uid):
                if self.actuator("release", {"id": row["id"], "now": now}):
                    self.holding[uid] = False
                    self._cover_since.pop(uid, None)
                    done.append((uid, "released"))
                    log.warning("%s: the primary of %s is not being written — recording from %.0f s ago",
                                self.name, uid, self.PREBUFFER)
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
        return max(0.0, self.PREBUFFER - self.DETECTION - self.DEFER_MARGIN)

    def primary_needs_cover(self, row: dict, now: float | None = None) -> bool:
        now = self.wall() if now is None else now
        said = self.stream_says(row) if self.stream_says is not None else None
        if said is not None:
            return bool(said)
        carried = self.carried_primary(row, now)
        if carried is not None:
            return carried
        names = volumes.backups(self.vars)
        running = {str(st.get("id")) for hb in heartbeats(self.objects, self.SUB.name + "/").values()
                   if now - hb.ts <= 45.0 for st in hb.status if st.get("phase") == "running"}
        need = False
        for key in self.vars.list(self.SUB.config(self.ROWS, "")):
            items, _ = self.vars.get(key)
            if not items or items.get("deleted") == "true":
                continue
            other = self.parse_row(items)
            if str(other["id"]) == str(row["id"]) or str(other["cam"]) != str(row["cam"]) or volumes.is_backup(other, names=names):
                continue
            until = float(other.get("until") or 0)
            should = bool(other.get("enabled")) and (until == 0 or until > now)
            if not should or str(other["id"]) in running:
                self._not_written_since.pop(str(other["id"]), None)
                continue
            since = self._not_written_since.setdefault(str(other["id"]), now)
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
        items, _ = self.vars.get(PRIMARIES)
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
        e = json.loads(items[ref])
        raw = self.objects.get(DOMAIN_SEEN)
        seen = float(json.loads(raw).get("ts", 0)) if raw else 0.0
        key = f"ref:{ref}"
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
    def resubscribe(self, now: float | None = None) -> list[int]:
        now = self.now() if now is None else now
        moved = []
        for cid in list(self.reconciler.actual):
            src = self.source(cid)
            if src is not None and self.sources.get(cid) not in (None, src[1]):
                self.actuator("stop", {"id": cid})
                self.reconciler.lost(cid, now)
                self.sources.pop(cid, None)
                moved.append(cid)
                log.info("%s: camera %s is held elsewhere now (%s): re-subscribing", self.name, cid, src[1])
        return moved

    def reconcile_once(self, now: float | None = None) -> list[tuple[str, int]]:
        self.resubscribe(now)
        out = super().reconcile_once(now)
        self.gate_pass()
        self.writer_pass()
        return out

    # -- is the writer writing (Lesson 10, feedback U) ------------------------------------------------------
    # Offered: what the actuator says its pipelines handed their sinks. Landed: what the volume's ring says it
    # took since this recorder opened it (`totalWritten`). Between the two is a queue and the engine's own
    # policy — a sequence it lost, a group of pictures it cut — and "taken" is not "on the volume" until this
    # says so. A recorder whose actuator does not measure says nothing — silence here
    # is "not measured", never "fine". When the watch says stuck or losing, the cure is to reopen the writer:
    # the pipelines are stopped and counted lost, and the reconciler starts them again, under a new epoch as
    # any restart. At most every ten minutes (`WriterWatch.reopen_every`); the heartbeat says the state
    # every pass regardless.
    def writer_pass(self, now: float | None = None) -> dict:
        wall = self.wall() if now is None else now
        measure = getattr(self.actuator, "offered", None)
        running = list(self.reconciler.actual)
        vals = [measure(c) for c in running] if measure else []
        # Per recording: when what it was offered last GREW. A pipeline that is up and fed nothing — a source
        # that stalled, a fan-out that stopped — is `running` for ever; this is the number that says otherwise.
        # A recording that has taken nothing yet is counted from when it was first seen running.
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
            landed = int(self.store.status().get("totalWritten", 0)) - self._written_at_open if self.store else 0
        except ArchiveError:
            return self.writer.state                 # a volume that does not answer measures nothing this pass
        state = self.writer.observe(sum(v or 0 for v in vals), landed, wall)
        if self.writer.reopen_due(wall):
            log.warning("%s: the writer is %s (%s) — reopening it", self.name, state["state"], state)
            for cid in running:
                self.actuator("stop", {"id": cid})
                self.reconciler.lost(cid, self.now())
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
                # Empty unless the volume this process holds will not open. Published because the alternative
                # is the failure that looks like health: a fresh hold, a green console and nothing being
                # written. Whatever reads it must not count that volume as served.
                "volume_error": self.volume_error,
                # Empty while the volume takes samples. Otherwise the reason it stopped, and since when.
                # Different from `volume_error` on purpose: a volume that went AWAY is still this recorder's
                # place, and it is not handed back for being away.
                "archive_error": self.archive_error,
                "archive_away_since": self.archive_away_since,
                "archive_failure": self.archive_failure,
                # Whether what the sinks were handed is reaching the volume (Lesson 10): ok, stuck or losing.
                # A fresh hold and a running row do not say it; only this does.
                "writer": self.writer.state,
                # Volumes this recorder handed back for refusing writes, and why — left alone until the time
                # given, so that a key somebody fixes is picked up without a restart.
                "refused": {n: why for n, (_, why) in self.refused.items()},
                "closed": ",".join(self.closed),
                # Lesson 26: the door this recorder serves its archive at, for a primary backfilling from it.
                **({"archive_url": self.archive_url} if self.archive_url else {}),
                # Lesson 16: what a clean fetch found nowhere — ours missing it, the source missing it too.
                # A number the operator wants on its own: "of what we lost, 519 s were not on the card either".
                "nowhere_seconds": int(sum(b - a for spans in self.nowhere.values() for a, b in spans)),
                # A recorder holding an incidents volume: what each keep holds there (`keep_pass`).
                **({"keeps": self.keep_state} if self.incidents else {})}

    # -- which archive this recorder writes into ------------------------------------------------------
    # Run once a pass, after the slot and the leases. Four outcomes, and the one that matters is the last.
    #
    # Pinned: nothing to decide. Nothing declared: the server's own name, as before volumes were rows.
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
        if self.pinned:
            if self.store is None or self.engine_lost:
                rows = {v.name: v for v in volumes.declared(self.vars)}
                vol = rows.get(self.volume) or volumes.Volume(self.volume, "local", self.default_url, self.server or "",
                                                              self.default_quota)
                self.volume_error = str(self._write_into(vol) or "")
                self._place_kind(vol)
            return self.volume
        rows = {v.name: v for v in volumes.declared(self.vars)}
        self._shared = {n for n, v in rows.items() if volumes.any_box(v)}   # remembered: asked when the store is silent
        free = volumes.servable(list(rows.values()), self.server)
        # A volume that refuses writes — WRONG, not away — is handed back: its recordings should go somewhere
        # that works. And it is left alone for REFUSED_FOR, or the next pass would take it straight back:
        # opening may succeed and the first write fail again.
        now = self.wall()
        if self.hold is not None and self.archive_failure == "wrong":
            why = self.archive_error
            self.refused[self.hold] = (now + self.REFUSED_FOR, why)
            logging.error("%s: %s refuses writes (%s) — handing it back", self.name, self.hold, why)
            self.leave_volume(f"volume {self.hold} refuses writes")
        self.refused = {n: v for n, v in self.refused.items() if v[0] > now}
        free = [n for n in free if n not in self.refused]
        held = self.hold
        if held is not None and (held not in free or not self.renew_hold()):
            self.leave_volume(f"volume {held} is not this recorder's any more")   # withdrawn, disabled, or taken from us
        if self.hold is None and not free:
            # Nothing declared anywhere: the box as it was before volumes were rows — one place, named after
            # the server, `file://$ARCHIVE/volume`. Note this is reached after letting go above, so withdrawing
            # the last volume does not leave a process quietly writing into it.
            err = self._write_into(volumes.Volume(self.default_volume, "local", self.default_url, self.server or "",
                                                  self.default_quota))
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
                        logging.error("%s: %s is the only archive it can reach and it will not open: %s",
                                      self.name, self.hold, self.volume_error)
                        return self.volume
                    self.volume, self.capacity = "", 0             # a spare is not a place to put a recording
                    return self.volume
            err = self._write_into(rows[self.hold])
            if err is None:
                self.volume, self.capacity, self.volume_error = self.hold, self.full_capacity, ""
                self._place_kind(rows[self.hold])
                return self.volume
            logging.warning("%s: %s will not open (%s) — looking for another", self.name, self.hold, err)
            skipped.add(self.hold)
            broken.append((self.hold, str(err)))
            self.volume_error = str(err)
            self.release_hold()                                    # so somebody who CAN write there may take it

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
        if self.store is not None and self.store.url == vol.url and self.store.writer is not None and not self.engine_lost:
            if vol.quota_bytes and vol.quota_bytes != self.store.quota:
                try:
                    self.store.resize(vol.quota_bytes)   # a new quota is a new size of the ring, without stopping
                except ObsdError as e:
                    log.warning("%s: could not resize %s to %d bytes: %s", self.name, vol.name, vol.quota_bytes, e)
            return None
        if self.store is not None:
            self._close_store(quiet=True)
        secret = self.sealer.open("access_secret", vol.access_secret) if vol.access_secret and self.sealer else vol.access_secret
        store = Archive(vol.url, vol.name, vol.quota_bytes or self.default_quota, f"rec:{vol.name}", self.session, self.wall,
                        secret=secret, **{k: v for k, v in (("block", self.block), ("read", self.read)) if v})
        try:
            store.open()
        except ArchiveError as e:
            if e.kind == "wrong":
                return e
            if not self.archive_error:
                self.archive_away_since = self.wall()
                log.warning("%s: %s is %s at open (%s) — keeping it and trying again", self.name, vol.name, e.kind, e.detail)
            self.archive_error, self.archive_failure = e.detail, "away"
            return None
        self.store, self.engine_lost = store, False
        try:
            self._written_at_open = int(store.status().get("totalWritten", 0))
        except ArchiveError:
            self._written_at_open = 0
        if self.archive_error:
            log.info("%s: %s answers again after %.0f s", self.name, vol.name, self.wall() - self.archive_away_since)
        self.archive_error, self.archive_failure, self.archive_away_since = "", "", 0.0
        log.info("%s: writing into %s (%s)%s%s", self.name, vol.name, vol.url, " — formatted" if store.formatted else "",
                 " — the writer a previous process left, picked up again" if store.reattached else "")
        return None

    # A sink found the daemon gone. Nothing is torn down here, on the pipeline's thread: the next pass closes
    # what is left of the store and opens it again (`volume_pass`) — at once, not after the writer watch's ten
    # minutes, because there is nothing to wait for: the engine is not there, a new session is (feedback CF).
    def _lost_engine(self) -> None:
        if not self.engine_lost:
            log.warning("%s: obsd stopped answering — remounting %s on the next pass", self.name, self.volume)
        self.engine_lost = True

    def _close_store(self, quiet: bool = False) -> None:
        if self.store is None:
            return
        try:
            self.store.close()
        except Exception as e:                           # noqa: BLE001 — closing a volume that went away says nothing new
            if not quiet:
                log.warning("%s: closing %s: %s", self.name, self.store.name, e)
        self.store = None

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
        # The writer is closed while the volume is still ours — its flush is what puts the last minutes on the
        # volume — and only then is the hold let go: released first, the next holder would mount a volume with
        # our writer still in it.
        self._close_store(quiet=True)
        try:
            self.release_hold()
        except OSError:                              # the store is silent: the hold lapses by itself
            self.hold = None
        self.volume, self.capacity, self.incidents = "", 0, False
        # What the archive's state said was about the volume we just left. The next one starts clean.
        self.archive_error, self.archive_failure, self.archive_away_since = "", "", 0.0
        self.keep_held, self.keep_state = {}, {}

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
        self._close_store()
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
        if self.store is None or self.clock() - self._depth_at < self.DEPTH_EVERY:
            return self.depths
        self._depth_at, now = self.clock(), self.wall() if now is None else now
        try:
            closed = int(self.store.status().get("firstBlockId", 0)) > 0
            depths = {str(r["id"]): round(self.store.depth_days(str(r["id"]), now), 2) for r in self.rows}
        except ArchiveError:                         # a volume that is away says nothing about depth
            return self.depths
        self.depths = depths
        for row in self.rows:
            unit, floor = str(row["id"]), float(row.get("min_depth_days") or 0)
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
    def lease_pass(self) -> list[str]:
        lost = super().lease_pass()
        if self.recording_allowed:                   # a fenced instance decides nothing about volumes
            try:
                self.volume_pass()
                self._hold_confirmed = self.clock()
            except OSError as e:
                self.store_errors += 1
                quiet = self.clock() - self._hold_confirmed
                if self.hold is not None and self.hold in self._shared and quiet >= self.slot_ttl - self.lease_margin:
                    self.leave_volume(f"the hold on network archive {self.hold} has not been confirmed for {quiet:.0f} s "
                                      f"(the store does not answer: {e})")
                else:
                    logging.warning("%s: the store did not answer for the volumes (%s); still writing into %s",
                                    self.name, e, self.volume or "nothing")
            self.depth_pass()
        return lost

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
        super().pump_once()                         # …which now includes `requests()`: the base serves the
                                                    # family for every subsystem, and this one overrides
                                                    # the method, not the call — asking twice a pass would
                                                    # spend the budget twice
        # Bounded, inside the window — it shares the device's uplink — and never while the volume is taking
        # nothing.
        if self.backfill_budget and not self.archive_busy():
            self.backfill_in_background()
        if self.incidents and not self.archive_busy():
            self.keeps_in_background()

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

    # What a source has and we do not, bounded at both ends. Not older than our own retention — otherwise
    # backfill and retention chase each other round the clock, for ever.
    #
    # Not newer than what we can SEE (the feedback's Q). A reader sees only closed blocks, and a block closes
    # when the next begins — minutes, at a low bitrate. Everything after the end of our visible coverage is
    # either being written this minute or written and not yet visible, and there is no need to tell the two
    # apart: neither is a gap. The visible end is the lag MEASURED; `settle` stays as the floor, and is all
    # there is for a recording with nothing visible.
    #
    # PLANNED backfill starts at our first visible second (the feedback's S). Before it the recording was not
    # running by design — created yesterday, or a recording on events — and filling it from the card would
    # turn a recording on events into a recording always, a night late. An operator's request is not
    # planned: a person asked for that hour, and may ask for any hour.
    #
    # And never what a clean fetch from THIS source already found nowhere.
    def gaps(self, unit, coverage: dict, now: float, planned: bool = True, source: str = "device") -> list[tuple[float, float]]:
        ours = self.our_coverage(unit)
        lo = max(float(coverage["from"]), now - self.keep_days * 86400)
        hi = min(float(coverage["to"]), now - self.settle, ours[-1][1] if ours else now)
        if planned:
            if not ours:
                return []
            lo = max(lo, ours[0][0])
        if hi <= lo:
            return []
        holes = subtract((lo, hi), ours)
        for gone in self.nowhere.get((str(unit), source), []):
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
        found = holder_of(self.objects, "vms/", cam, self.wall(), field="playback_url")
        if found is None or not found[2].get("coverage"):
            return None                       # no phase: a channel held only for its archive answers too
        from .config import local_only
        if local_only(found[2]["playback_url"], found[1].extra.get("server", "?"), self.server):
            return None                       # the holder's archive door is on ITS loopback: not a source from here
        return found[2]["playback_url"], found[2]["coverage"]

    # -- the backup archive: a recording of the same camera on a backup volume (Lesson 26) ----------------
    # Found the way everything here is found — in heartbeats: a recording of this camera, homed on a backup
    # volume, run by a recorder that is alive, says what it holds and serves its archive. `self` is never its
    # own source, and a backup fetches from nobody.
    def backup_sources(self, row: dict, now: float | None = None) -> list[dict]:
        now = self.wall() if now is None else now
        names = volumes.backups(self.vars)
        if not names or volumes.is_backup(row, names=names):
            return []
        recs = set()
        for key in self.vars.list(self.SUB.config(self.ROWS, "")):
            items, _ = self.vars.get(key)
            if items and items.get("deleted") != "true":
                other = self.parse_row(items)
                if str(other["id"]) != str(row["id"]) and str(other["cam"]) == str(row["cam"]) and volumes.is_backup(other, names=names):
                    recs.add(str(other["id"]))
        out, edge_homes, homes = [], volumes.edges(self.vars), {}
        for key in self.vars.list(self.SUB.config(self.ROWS, "")):
            items, _ = self.vars.get(key)
            if items:
                other = self.parse_row(items)
                homes[str(other["id"])] = str(other.get("home") or "")
        for name, hb in sorted(heartbeats(self.objects, self.SUB.name + "/").items()):
            url = hb.extra.get("archive_url", "")
            if not url or now - hb.ts > 45.0:
                continue
            from .config import local_only
            if local_only(url, hb.extra.get("server", "?"), self.server):
                continue                      # that recorder's archive door is on its own loopback: not reachable from here
            for st in hb.status:
                if str(st.get("id")) in recs and st.get("coverage"):
                    kind = "edge" if homes.get(str(st["id"])) in edge_homes else "backup"
                    out.append({"key": f"{kind}:{st['id']}", "kind": kind, "recording": str(st["id"]),
                                "recorder": name, "url": url.rstrip("/"), "coverage": st["coverage"]})
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
    def read_samples(self, url: str, unit: str, t0: float, t1: float) -> list[Sample]:
        import urllib.parse
        import urllib.request
        q = urllib.parse.urlencode({"from": t0, "to": t1})
        with urllib.request.urlopen(f"{url}/samples/{urllib.parse.quote(str(unit))}?{q}", timeout=30) as r:
            return Sample.decode_all(r.read())

    # How far back the doors show a recording: its row's `retention_days` (`visible_from`). A ceiling — the ring
    # decides what is still there; this decides what is SHOWN. A recording whose row is gone, or a row the store
    # did not give, shows thirty days: unread is not "for ever".
    def _visible_from(self, unit) -> float:
        from .archive import visible_from
        if self.incidents:
            return 0.0                                # everything in an incidents volume is there because somebody kept it
        try:
            items, _ = self.vars.get(self.SUB.config(self.ROWS, str(unit)))
        except OSError:
            items = None
        return visible_from(items if items and items.get("deleted") != "true" else None, self.wall())

    # This recorder's archive, served: `/timeline/<unit>` and `/samples/<unit>?from&to` over the volume THIS
    # process holds (`archive_routes`). A backup recorder serves it so a primary can copy from it; the console
    # reads every recorder's to draw a camera's timeline and play it; any recorder may.
    def serve_archive(self, host: str = "127.0.0.1", port: int = 0):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        routes = archive_routes(lambda: self.store, self.wall, lambda unit: self.epochs.get(str(unit)), self._visible_from)

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                got = routes(self.path)
                if got is None:
                    self.send_response(404); self.end_headers(); return
                status, body, ctype = got
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        srv = ThreadingHTTPServer((host, port), H)
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
    def requests(self, budget: int = 2, now: float | None = None) -> list[dict]:
        now = self.wall() if now is None else now
        if self.archive_busy():
            return []
        mine = {str(r["id"]) for r in self.rows}
        done: list[dict] = []
        for key in self.vars.list(REC.requests_prefix()):
            if len(done) >= budget:
                break
            it, _ = self.vars.get(key)
            if not it or str(it.get("unit", "")) not in mine:
                continue                                     # another recorder's recording: not ours to fetch
            # One family, two kinds of asking. A backfill names a RANGE and this worker fetches it; a
            # `record` names a DURATION and is not a worker's to serve at all — it becomes a row, and rows
            # are the console's. Skipping it here is what keeps the recorder from tripping over a request
            # that was never addressed to it (`it["from"]` would not be there).
            if str(it.get("action", "backfill")) != "backfill":
                continue
            unit, cam = str(it["unit"]), str(it.get("cam", it["unit"]))
            srcs = self.sources_of({"id": unit, "cam": cam, "home": next((r.get("home") for r in self.rows if str(r["id"]) == unit), "")})
            rid = key.rsplit("/", 1)[1]
            if not srcs:
                continue                                     # nobody holds the device and no backup answers; ask again next pass
            r = self.fetch_from(unit, cam, srcs[0], float(it["from"]), float(it["to"]))
            if r.get("skipped"):
                continue                                     # not fetched: reporting it would have the console
                                                             # delete a request nobody served
            self.fetched.append(rid)                         # the heartbeat says so; the console removes the row
            done.append({**r, "request": rid})
        return done

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
                self.backfill(self.backfill_budget)
            except Exception:                            # noqa: BLE001 — a thread has nobody to raise to
                logging.exception("%s: backfill failed", self.name)

        self._backfiller = threading.Thread(target=fetch, name=f"{self.name}-backfill", daemon=True)
        self._backfiller.start()
        self._backfiller.join(timeout=self.BACKFILL_WAIT)

    def backfill(self, budget: int = 1, now: float | None = None, force: bool = False) -> list[dict]:
        now = self.wall() if now is None else now
        if not (force or self.in_window(now)) or self.archive_busy():
            return []
        done: list[dict] = []
        names = volumes.backups(self.vars)
        for row in self.rows:
            if len(done) >= budget:
                break
            if volumes.is_backup(row, names=names):
                continue
            for src in self.sources_of(row):
                for (t0, t1) in self.gaps(row["id"], src["coverage"], now, source=src["key"])[:budget - len(done)]:
                    done.append(self.fetch_from(row["id"], row["cam"], src, t0, t1))
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
        try:
            samples = self.read_samples(src["url"], src["recording"], t0, t1)
        except OSError as e:
            return {"unit": unit, "cam": str(cam), "from": t0, "to": t1, "error": f"{src['recording']}: {e}"}
        self.actuator.range_error = ""
        return self._land(unit, cam, samples, t0, t1, src["key"])

    # One range from the device: its frames, landed as OURS — our epoch, our volume, the backfill stream.
    def fetch(self, unit, cam, url: str, t0: float, t1: float) -> dict:
        unit = str(unit)
        if not self.may_record(unit):
            return {"unit": unit, "cam": str(cam), "from": t0, "to": t1, "skipped": "no lease"}
        self.actuator.range_error = ""
        samples = self.actuator.record_range(unit, f"{url}?from={t0}&to={t1}", t0, t1)
        return self._land(unit, cam, samples, t0, t1, "device")

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
    def _land(self, unit: str, cam, samples: list[Sample], t0: float, t1: float, source: str) -> dict:
        from w2cplatform.obsd import unix_s
        have, kept, groups = self.our_coverage(unit), 0, []
        for smp in samples:
            if smp.key or not groups:
                groups.append([smp])
            else:
                groups[-1].append(smp)
        delivered = stitch([(unix_s(g[0].begin), unix_s(g[-1].end)) for g in groups], self.stitch)
        epoch = self.epochs.get(unit, 0)
        last = None                                      # where the sequence being written ends
        for g in groups:
            span = (unix_s(g[0].begin), unix_s(g[-1].end))
            if overlaps(have, span) or not g[0].key:
                continue                                 # live recording got there while we were fetching
            try:
                # A sequence is CONTINUOUS to the index: a hole inside one is drawn as footage. So what the source
                # did not have — or what was dropped above — ends the sequence, and the next group opens another.
                if last is not None and span[0] - last > self.stitch:
                    self.store.finish(unit, epoch, backfill=True)
                last = span[1]
                for smp in g:
                    self.store.put(unit, epoch, smp, backfill=True)
                kept += 1
            except Unavailable:
                self._lost_engine()
                break
            except ObsdError as e:                       # the engine refused the group: the next one opens on its key
                log.warning("%s: %s refused a fetched group at %.0f: %s", self.name, unit, span[0], e.name)
        if kept:
            self.store.finish(unit, epoch, backfill=True)
        self.backfilled += kept
        self.landing[unit] = stitch(self.landing.get(unit, []) + delivered, self.stitch)
        failed = getattr(self.actuator, "range_error", "")
        if not failed:
            missing = subtract((t0, t1), delivered)
            if missing:
                self.nowhere[(unit, source)] = sorted(self.nowhere.get((unit, source), []) + missing)
        if kept:
            # What arrived is now ordinary footage — and a hole in the DETECTIONS, because nothing was
            # watching this camera while nothing was recording it. The console turns each of these into a
            # scan (М10B Lesson 22), so the two holes close together. Reported here and not written
            # anywhere: a worker's token writes no configuration.
            self.closed = (self.closed + [f"{unit}|{t0:.0f}|{t1:.0f}"])[-self.CLOSED_REPORTED:]
        out = {"unit": unit, "cam": str(cam), "from": t0, "to": t1, "groups": kept, "source": source}
        if failed:
            out["error"] = failed
        return out

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
    #
    # A keep is still not "for ever": the incidents volume is a ring too. It is only one that nothing else writes
    # into, so it turns as slowly as keeps arrive.
    KEEP_EVERY = 60.0

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

    def keep_pass(self, now: float | None = None) -> dict:
        import hashlib
        from w2cplatform.events import ALARM, EventLog
        from . import keeps
        from .console import recorder_doors
        if not self.incidents or self.store is None:
            return {}
        now = self.wall() if now is None else now
        declared = keeps.declared(self.vars)             # a store that does not answer RAISES: unread is not "none"
        cams: dict[str, set] = {}
        for key in self.vars.list(self.SUB.config(self.ROWS, "")):
            items, _ = self.vars.get(key)
            if items and items.get("deleted") != "true":
                row = self.parse_row(items)
                cams.setdefault(str(row["cam"]), set()).add(str(row["id"]))
        doors = [(n, u) for n, u, _ in recorder_doors(self.objects, now) if n != self.name]
        state: dict[str, dict] = {}

        def inside(k, rec) -> float:                     # seconds of the keep this volume holds for `rec`
            return sum(min(b, k.until) - max(a, k.since) for a, b in self.store.coverage(rec) if b > k.since and a < k.until)

        for k in declared:
            got = missing = 0.0
            touched: list[str] = []
            for rec in sorted(set(k.recordings) | cams.get(k.cam, set())):
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
                for a, b in subtract((k.since, k.until), self.store.coverage(rec)):
                    for name, url in doors:
                        try:
                            samples = self.read_samples(url, rec, a, b)
                        except OSError:
                            continue                     # that door is down: another may have it, the next pass asks again
                        if samples and self._copy_in(rec, samples):
                            touched.append(rec)
                            break
                if rec in touched:
                    self.store.seal()                    # what was copied is readable now — and counted below
                self.keep_held[(k.id, rec)] = held = inside(k, rec)
                got += held
                missing += sum(b - a for a, b in subtract((k.since, k.until), self.store.coverage(rec)))
            entry = {"copied": round(got, 1), "missing": round(missing, 1)}
            for rec in sorted(set(touched)):
                frames = b"".join(s.encode() for s in self.store.samples(rec, k.since, k.until))
                digest = hashlib.sha256(frames).hexdigest()
                EventLog(self.archive_root, REC.name, rec, 0).append(
                    now, "archive.keep.copied", cam=k.cam, keep=k.id, recording=rec, bytes=len(frames),
                    sha256=digest, volume=self.volume)
                entry.setdefault("sha256", {})[rec] = digest
            if "sha256" not in entry and k.id in self.keep_state and "sha256" in self.keep_state[k.id]:
                entry["sha256"] = self.keep_state[k.id]["sha256"]
            state[k.id] = entry
        self.keep_held = {kr: v for kr, v in self.keep_held.items() if kr[0] in state}
        self.keep_state = state
        return state

    # Frames from another recorder's door into this volume, as `<recording>/e0`, one sequence per stretch — a hole
    # inside a sequence would be drawn as footage. What the door handed over starts on a key frame.
    def _copy_in(self, rec: str, samples: list) -> bool:
        from w2cplatform.obsd import unix_s
        last, kept = None, 0
        for smp in samples:
            if last is None and not smp.key:
                continue
            if last is not None and unix_s(smp.begin) - last > self.stitch:
                self.store.finish(rec, 0)
                if not smp.key:
                    last = None
                    continue
            try:
                self.store.put(rec, 0, smp)
                kept += 1
                last = unix_s(smp.end)
            except Unavailable:
                self._lost_engine()
                return False
            except ObsdError:
                last = None                              # refused: the next group opens on its key
        if kept:
            self.store.finish(rec, 0)
        return kept > 0

    def metrics_text(self) -> str:
        return (f"# TYPE rec_recordings_running gauge\nrec_recordings_running {len(self.reconciler.actual)}\n"
                f"# TYPE rec_groups_backfilled counter\nrec_groups_backfilled {self.backfilled}\n")


# A recorder's archive door, over the volume it holds: what a primary copies from a backup, and what the console
# draws and plays. Two reads, both from a FRESH reader — a reader sees what was closed when it mounted:
#
#   GET /timeline/<unit>?from&to   {"spans": [{start, end, epoch, source, bytes, fenced}], "current_epoch"}
#   GET /samples/<unit>?from&to    the frames, SMPL records one after another — each stretch from the epoch that
#                                  owns it, from a key frame (`Archive.samples`)
def archive_routes(store_of, wall, current_epoch=lambda unit: None, visible_from=lambda unit: 0.0):
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
            t0 = max(t0, visible_from(unit))                 # retention is a ceiling on what the door shows
            try:
                if prefix == "/timeline/":
                    cur = current_epoch(unit)
                    body = {"unit": unit, "spans": store.timeline(unit, t0, t1, cur), "current_epoch": cur}
                    return 200, json.dumps(body).encode(), "application/json"
                return 200, b"".join(smp.encode() for smp in store.samples(unit, t0, t1)), "application/octet-stream"
            except ArchiveError as e:
                return 503, json.dumps({"error": str(e)}).encode(), "application/json"
        return None
    return routes
