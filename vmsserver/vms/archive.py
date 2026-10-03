"""The archive is ObjectStorage: a volume in `obsd`, and the recorder's names for what is in it."""
# ================================================================================================
# # archive.py — one volume, as the recorder and its readers see it
#
# Footage is not files. It is ObjectStorage — the product's engine — behind the host's daemon `obsd`
# (`w2cplatform/obsd.py`), and what a volume holds is STREAMS of samples, cut by the engine into sequences
# that open on a key frame, packed into blocks of a size fixed when the volume was formatted. This module is
# the course's vocabulary over that, and nothing more:
#
#   a stream       `<recording>/e<epoch>` — the epoch is part of the NAME, the only metadata a stream has.
#                  What a fenced writer wrote and what the survivor wrote are two streams of one volume, and
#                  the timeline tells them apart by name. Footage fetched into a gap is `<recording>/e<epoch>/
#                  backfill`: where it came from is in the name too — there is no manifest line to carry it.
#                  A keep's copy in an incidents volume is `<recording>/e0`: nobody's lease, so wherever the live
#                  footage still exists its own epoch owns those minutes (`RecWorker.keep_pass`)
#   a span         what the index says one stream holds, `(unit, epoch, start, end, bytes, source)` — read
#                  from the engine every time, never kept beside it
#   visibility     a reader sees only CLOSED blocks, and only those closed when it mounted. So every question
#                  is asked of a fresh reader, and what was written a minute ago may not be an answer yet: the
#                  recorder plans by what it can SEE (`RecWorker.gaps`), and a writer is closed and opened again
#                  (`Archive.seal`) when the minutes just written have to be readable now
#   the ring       a volume is formatted at its quota and overwrites its oldest blocks when full. Nothing is
#                  deleted by age: `retention_days` is a CEILING on what the doors show (`visible_from`), and
#                  how deep the archive really is, is read off the index (`depth_days`)
#
# Events are not here. They stay what they were — buckets of lines on the resource's tree, `vms/<cam>/` and
# `rec/<name>/` (`event_log`, the platform's `EventLog`) — a file tree the platform retains, mirrors and
# indexes, on the server of whoever wrote them.
# ================================================================================================
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit, unquote

from w2cplatform.events import EventLog
from w2cplatform.obsd import Closed, ObsdError, Sample, Session, SessionLost, Unavailable, archive_ms, unix_s
from w2cplatform.rows import PARSE_ERRORS, Table, finite

SUB = "rec"          # the recorder's subsystem: its streams in the volume, its event buckets on the resource
EVENTS_SUB = "vms"   # the worker's tree: the camera's event buckets
STITCH = 2.0         # seconds: two spans closer than this are one run — the seam between two sequences is no gap
# How a volume is formatted, unless its row says otherwise: the block, and the read size the engine cuts
# sequences by. A block must hold a sequence — the read size plus up to one group of pictures — or a long group
# is cut where the block is full and the rest is refused until the next key frame (the product's incident,
# feedback Y): block ≥ read + 3 MB.
BLOCK, READ = 8 << 20, 1 << 20
log = logging.getLogger("vms.archive")
NEVER, FOREVER = 0, 1 << 62           # the archive's milliseconds: before anything, after everything
# HOW LONG WRITTEN STAYS INVISIBLE (feedback CP). A reader sees only blocks written to the volume, and a block is
# written when it is full — or, since the engine's patch 04, when the writer's queue is not empty and
# `blockFlushPeriodSec` has passed. A sequence reaches that queue when it is finished: by `FINISH_MEDIA`, or by the
# engine on a key frame once it is open longer than `sequenceFlushPeriodMs`. So a thin stream — 7 KB/s against a
# 4 MB block — is visible after sequence flush + block flush, about fifteen seconds with the product's numbers,
# and not after the ten minutes the block takes to fill. The engine's own default for the block is a minute, and
# before the patch its timer never fired at all. The product sets both through `WRITER_CONFIGURE`; so does this.
SEQUENCE_FLUSH_MS, BLOCK_FLUSH_S = 10_000, 5
TIMELINE_WINDOW = 5 * 86400 * 1000    # how much of a stream one timeline question covers (`Archive._timeline`)


def event_log(root: str, cam, epoch: int, bucket_seconds: int = 600) -> EventLog:
    """The camera's event log on this resource: what the worker holding the
    camera's epoch writes into, recording or not — `vms/<cam>/`, not `rec/`."""
    return EventLog(root, EVENTS_SUB, str(cam), epoch, bucket_seconds)


def stream_name(unit, epoch: int, backfill: bool = False) -> str:
    return f"{unit}/e{int(epoch)}" + ("/backfill" if backfill else "")


def parse_stream(name: str) -> tuple[str, int, str] | None:
    """`(unit, epoch, source)` — `live` or `backfill` — or None for a stream that is not a recording's."""
    parts = name.split("/")
    if len(parts) not in (2, 3) or not parts[0] or not parts[1].startswith("e") or not parts[1][1:].isdigit():
        return None
    if len(parts) == 3 and parts[2] != "backfill":
        return None
    return parts[0], int(parts[1][1:]), "backfill" if len(parts) == 3 else "live"


# Where a volume is, as `obsd` opens it: PARAMETERS, never a URI with a key in it — a URI is printed, logged,
# published in heartbeats; the key travels separately (`access_secret`, sealed in the store, opened only by the
# process that mounts the volume: М10A Lesson 18).
def volume_params(url: str, secret: str = "", access_key: str = "") -> dict:
    if "://" not in url:
        return {"schema": "file", "path": url}           # a local volume's row names its directory
    u = urlsplit(url)
    if u.scheme == "file":
        return {"schema": "file", "path": unquote(u.path)}
    if u.scheme.startswith("s3"):
        parts = [p for p in u.path.split("/") if p]
        if len(parts) < 2:
            raise ValueError(f"{url}: an s3 volume is s3://<host>/<region>/<bucket>[/<path>]")
        return {"schema": u.scheme, "host": u.hostname or "", **({"port": str(u.port)} if u.port else {}),
                "region": parts[0], "bucket": parts[1], "path": "/".join(parts[2:]),
                "access_key": access_key, "secret_key": secret}   # the key's id from the row's `access_key`, never the url
    raise ValueError(f"{url}: not an archive this course opens (file://, s3://)")


@dataclass(frozen=True)
class Span:
    unit: str             # the recording — `7`, or `7-cloud`: the operator's name
    epoch: int
    start: float          # unix seconds
    end: float
    bytes: int
    source: str = "live"  # `live` (written from the fan-out) or `backfill` (fetched into a gap — Lesson 16)

    @property
    def stream(self) -> str:
        return stream_name(self.unit, self.epoch, self.source == "backfill")


# `want` minus every range in `have`. The one subtraction two things use: the console draws device coverage
# only where ours does not cover it (Lesson 15), and the recorder fetches only what it does not have (Lesson
# 16). One rule, two uses — they cannot drift apart.
def subtract(want: tuple[float, float], have: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = [want]
    for a, b in sorted(have):
        nxt = []
        for x, y in out:
            if b <= x or a >= y:
                nxt.append((x, y)); continue
            if a > x:
                nxt.append((x, min(a, y)))
            if b < y:
                nxt.append((max(b, x), y))
        out = nxt
    return [(a, b) for a, b in out if b > a]


def overlaps(have: list[tuple[float, float]], span: tuple[float, float]) -> bool:
    return any(a < span[1] and span[0] < b for a, b in have)


def stitch(spans, gap: float = STITCH) -> list[tuple[float, float]]:
    """Runs of `(start, end)`, adjacent ones merged: the seam between two sequences is not a hole."""
    runs: list[list[float]] = []
    for a, b in sorted((float(a), float(b)) for a, b in spans):
        if runs and a <= runs[-1][1] + gap:
            runs[-1][1] = max(runs[-1][1], b)
        else:
            runs.append([a, b])
    return [(a, b) for a, b in runs]


# Every stretch of `[t0, t1)` the spans cover, each given to the HIGHEST EPOCH there. Two epochs overlap
# whenever a writer was fenced with footage in flight; read both and those minutes come twice, drop every
# older epoch and the minutes only it held disappear. So the unit of the decision is the stretch:
# `[(span, lo, hi)]`, in time order.
def authoritative(spans: list[Span], t0: float, t1: float) -> list[tuple[Span, float, float]]:
    edges = sorted({t0, t1} | {s.start for s in spans} | {s.end for s in spans})
    edges = [e for e in edges if t0 <= e <= t1]
    out: list[list] = []
    for lo, hi in zip(edges, edges[1:]):
        if hi <= lo:
            continue
        covering = [s for s in spans if s.start <= lo and s.end >= hi]
        if not covering:
            continue
        best = max(covering, key=lambda s: (s.epoch, s.source == "live"))
        if out and out[-1][0] == best and out[-1][2] == lo:
            out[-1][2] = hi
        else:
            out.append([best, lo, hi])
    return [(s, a, b) for s, a, b in out]


# A CEILING THAT DOES NOT READ HIDES, IT DOES NOT FALL BACK (the product team's sibling of the review's ninth pass).
# `float(...)` of the row: a word raised out of the door and out of the backfill's plan, `nan` made a ceiling no time is
# under or over, `inf` showed everything, `-1` hid a day ahead. Only a finite number not below nought is days; not said
# at all is thirty, as before. Anything else is not a default — "nobody sees more than a week" is the promise some
# installations care about, and thirty days would break it: the door shows nothing older than now and the backfill
# plans nothing (the footage stays in the ring, untouched), counted once until it is mended (`ceilings_garbled`) and
# logged with the recording's name.
CEILINGS = Table("ceiling", "nothing of that recording is shown, and nothing fetched for it, until it is mended",
                 "recording's retention_days")


def visible_from(row: dict | None, now: float) -> float:
    """`retention_days` is a ceiling on what the doors show — the ring decides what is still THERE."""
    raw = (row or {}).get("retention_days")
    if not raw or str(raw).strip() in ("", "None"):
        return now - 30 * 86400
    key = f"rec/recordings/{(row or {}).get('id', '?')}#retention_days"
    try:
        days = finite(raw)
        if days < 0:
            raise ValueError(f"{raw!r} is not a number of days")
    except PARSE_ERRORS as e:
        CEILINGS.garbled(key, e)
        return now
    CEILINGS.parsed(key)
    return now - days * 86400


class ArchiveError(Exception):
    """A volume that will not open or take writes, by KIND — the recorder answers each differently:

    wrong   only a person changes it: a path that is not a volume, no permission, a bucket that refuses the key.
            The volume is handed back
    away    a timeout, a network that is down, the daemon itself gone. Kept: it is back in a minute, and handing
            it back would reshuffle every recording on it for a link that returns. `SESSION_LOST` is away too —
            and more: every handle is dead, and the volume is mounted again (`Archive.lost`)
    busy    another writer holds it on this host (`ALREADY_LOCKED`) — a recorder of the same volume that has
            not let go yet, or one whose grace the daemon is still waiting out

    `away` and `busy` have NO deadline for a disk of this server, on purpose (the review's fifth pass, its third
    question): nobody else can write there, and handing it back for a daemon that is restarted in a minute reshuffles
    every recording on it. So the recorder keeps it, and while this host's engine stays broken its recordings are
    written nowhere. That is the cost, and it is said, not hidden: `archive_failure` and `archive_away_since` in the
    heartbeat show the operator since when, and the operator decides.

    A volume ANY box may serve has one (the review's sixth pass): while this host's engine answers nothing, the hold is
    renewed for `RecWorker.ENGINE_SILENT_FOR` and no longer — then the volume is let go, for a box whose engine does
    answer (`RecWorker.volume_pass`). And `busy` under this recorder's own hold — another host's writer that does not
    let go — lasts `RecWorker.BUSY_FOR` and no longer (the seventh pass): let go, with an alarm."""

    def __init__(self, kind: str, detail: str, name: str = ""):
        self.kind, self.detail, self.name = kind, detail, name    # `name`: the engine's status, or UNAVAILABLE
        super().__init__(f"{kind}: {detail}")


class Fenced(Unavailable):
    """A sample NOT sent: the volume is one any box may serve, and the hold this recorder writes it under has not been
    confirmed within its write window (`Archive.fence`). Not the engine lost — nothing was asked of it — and not a
    refusal by the engine: the recorder's own check before sending (the review's fifth pass, blocker 1; what it is and
    is not — `Archive._fenced`)."""

    def __init__(self, op: str, why: str):
        super().__init__(op, why)
        self.name = "FENCED"


WRONG = {"PERMISSION_DENIED", "NOT_A_VOLUME", "UNSUPPORTED_FORMAT", "READ_ONLY", "PATH_NOT_EMPTY",
         "INVALID_ARGUMENT", "PROTECTED_VOLUME", "INVALID_CIPHER_KEY"}


def classify(e: Exception) -> ArchiveError:
    if isinstance(e, ArchiveError):
        return e
    if isinstance(e, Unavailable):
        return ArchiveError("away", f"obsd is not answering: {e.detail}", e.name)
    if isinstance(e, ObsdError):
        if e.name == "ALREADY_LOCKED":
            return ArchiveError("busy", str(e), e.name)
        return ArchiveError("wrong" if e.name in WRONG else "away", str(e), e.name)
    if isinstance(e, ValueError):
        return ArchiveError("wrong", str(e))
    return ArchiveError("away", str(e))


class Archive:
    """One volume through the host's `obsd`. `owner` is what the daemon remembers a writer by — the recorder
    passes `rec:<volume>`, which the platform's hold makes unique — and what gets a vanished writer back.

    `confirm`: asked right before every `VOLUME_MOUNT_RW`, and a mount it refuses does not happen — the recorder's
    hold on a volume any box may serve, confirmed at that moment and not a pass ago (`RecWorker._confirm_hold`).

    `fence`: asked before every sample and every finish, and a False sends nothing (`Fenced`) — the same hold, its
    confirmation young enough to write under (`RecWorker._may_write_volume`; the review's fifth pass, blocker 1). A
    check before sending, not the fence: that is the engine's (`_fenced`).

    `on_unclean`: given, a mount the engine refuses as `VOLUME_UNCLEAN` is RECOVERED — `confirm` asked once more first,
    so never without a hold confirmed this second — told `(result, detail)`, and mounted again. Not given, it is the
    refusal it always was.

    `share`: for a volume that does not exist yet and has no `quota`, how big to format it — given what the daemon
    says of the disk it will be on (`space_where`)."""

    def __init__(self, url: str, name: str = "", quota: int = 0, owner: str = "", session: Session | None = None,
                 wall=time.time, secret: str = "", block: int = BLOCK, read: int = READ, access_key: str = "",
                 sequence_flush_ms: int = SEQUENCE_FLUSH_MS, block_flush_s: int = BLOCK_FLUSH_S,
                 confirm=None, lock_refresh: int = 0, share=None, fence=None, on_unclean=None):
        self.url, self.name, self.quota, self.owner = url, name or url, int(quota), owner
        self.share = share                         # no quota and no volume yet: its size from the disk (`space_where`)
        self.session = session or Session(client="vms-archive")
        self.wall, self.secret, self.block, self.read, self.access_key = wall, secret, block, read, access_key
        self.sequence_flush_ms, self.block_flush_s = int(sequence_flush_ms), int(block_flush_s)
        self.confirm, self.lock_refresh = confirm, int(lock_refresh)
        self.fence, self.on_unclean = fence, on_unclean
        self.volume = None
        self.writer = None
        self._opening = threading.Lock()
        self.formatted = False                     # this open formatted the volume: it was new
        self.reattached = False                    # the daemon handed back a writer a vanished process left
        self.lost = False                          # a handle of this volume answered SESSION_LOST: mount it again
        # A writer that may be alive in the session with no handle here: a `VOLUME_MOUNT_RW` sent and not answered,
        # a `WRITER_CLOSE` that did not come back. Whoever owns the session leaves it behind (`close` says False).
        self.orphan = False
        self.lock_lost = False                     # the engine refused a sample: the volume's lock is another writer's
        # What this writer TOOK of each stream since it was mounted: `{stream: [first begin, last end]}`, archive ms.
        # Taken is not written — a sequence waits in the writer's queue, a block is open — and a writer given up
        # writes nothing more: what of this no reader sees then is footage lost, and is counted (`unwritten`).
        # `_recent`: per stream, when each of its last frames was taken — what bounds the loss when nobody can look.
        self.taken: dict[str, list[int]] = {}
        self._recent: dict[str, deque] = {}
        self._taken_at = 0.0                       # when the engine last took a frame of any stream (monotonic)
        self.dropped: dict[str, tuple[float, float]] = {}   # …the loss, after `abandon`: `{stream: (from, to)}`, unix seconds

    def _open_volume(self):
        with self._opening:                        # the door, the backfill and the pass may all ask first
            if self.volume is None:
                self.volume = self.session.open_volume(params=volume_params(self.url, self.secret, self.access_key))
            return self.volume

    # Every handle this volume has is dead once ONE of them answers `UNKNOWN_HANDLE` (`SessionLost`): the daemon
    # restarted, or the session outlived its linger. Said here, on whichever thread found it; the recorder's pass
    # reads `lost` and mounts the volume again (the review's third pass, blocker 4).
    def _classified(self, e: Exception) -> ArchiveError:
        if isinstance(e, SessionLost):
            self.lost = True
        return classify(e)

    # THE MOUNT WHOSE ANSWER WAS LOST (the review's fifth pass, blocker 2). `VOLUME_MOUNT_RW` is not sent twice, and
    # one sent into a silence — the daemon frozen right at it — was `away` and nothing more: the writer the daemon made
    # when it woke stayed ATTACHED to this session, which the readers and the pass kept alive, and every mount after
    # it answered `ALREADY_LOCKED` until the recorder was restarted. It is an orphan now (`orphan`), and the session
    # is left behind like one whose close did not come back (`RecWorker._close_store`): a successor under the same
    # owner gets that writer back at once.
    #
    # AN UNCLEAN VOLUME UNDER A CONFIRMED HOLD IS RECOVERED (the review's fifth pass, blocker 1, and its second
    # question). `VOLUME_UNCLEAN` was `away` for ever, and said by nobody: nothing called `VOLUME_RECOVER`. Now the
    # recorder that holds the volume recovers it — `confirm` asked again right before, so a recorder whose hold is not
    # confirmed this second recovers nothing — says so (`on_unclean`), and mounts. Recovery that fails is `wrong`:
    # only a person changes that.
    def _mount_rw(self, vol):
        if self.confirm is not None:
            self.confirm()                         # raises ArchiveError: this volume is not ours to write this second
        try:
            return vol.mount_rw(self.owner)
        except Unavailable as e:
            self.orphan = self.orphan or e.sent
            raise
        except ObsdError as e:
            if e.name != "VOLUME_UNCLEAN" or self.on_unclean is None:
                raise
            unclean = e.detail
        if self.confirm is not None:
            self.confirm()
        result = vol.recover()
        self.on_unclean(result, unclean)
        if result == 2:
            raise ArchiveError("wrong", f"{self.name} was not cleanly unmounted and its recovery failed: {unclean}",
                               "VOLUME_UNCLEAN")
        try:
            return vol.mount_rw(self.owner)
        except Unavailable as e:
            self.orphan = self.orphan or e.sent
            raise

    # Opening is the only honest test: a row can name a path that does not exist, a mount that is gone or a
    # bucket nobody can reach. A volume that is not there yet is FORMATTED — at its quota, which is the size of
    # the ring — and then mounted for writing under `owner`. A volume that IS there keeps its size, and `quota`
    # becomes that size, read from the volume (the review's third pass): the number a recorder computed at its
    # start is a guess for a volume it has yet to format, never news about one that exists.
    def open(self, write: bool = True) -> "Archive":
        try:
            vol = self._open_volume()
            if not vol.exists():
                if not self.quota and self.share is not None:
                    self.quota = self.share(self.space_where())
                if not self.quota:
                    raise ArchiveError("wrong", f"{self.name}: no volume there and no quota to format one with")
                vol.format(self.quota, max_block=self.block, optimal_read=self.read, label=self.name,
                           lock_refresh=self.lock_refresh)
                self.formatted = True
            else:
                self.quota = self.size() or self.quota
            if write and self.writer is None:
                self.writer = self._mount_rw(vol)
                self.reattached = self.writer.reattached
                self._configure()
        except (ObsdError, ValueError) as e:
            raise self._classified(e) from None
        return self

    # THE DISK A NEW VOLUME WILL BE ON, AS THE DAEMON SEES IT (the review's fourth pass). A volume of nobody's
    # declaring was formatted at a share of the disk the RECORDER measured — in its container, where `/data/volume`
    # is not mounted at all: the share of the container's root, a system SSD, not of the 8 TB data disk the daemon
    # writes to, and that size stood from then on as the volume's own. The daemon opens the path, so the daemon is
    # asked (`VOLUME_SPACE`): of the volume's directory, or — not there yet — of the nearest one above it that is.
    # `{available, capacity, free}`, zeros when there is nothing to measure (a bucket; a daemon that cannot see it).
    def space_where(self) -> dict:
        p = volume_params(self.url, self.secret, self.access_key)
        if p.get("schema") != "file":
            return {"available": 0, "capacity": 0, "free": 0}
        path = p["path"].rstrip("/") or "/"
        while True:
            v = self.session.open_volume(params={"schema": "file", "path": path})
            try:
                got = v.space()
            finally:
                try:
                    v.close()
                except ObsdError:
                    pass
            if int(got.get("capacity") or 0) or path in ("/", ""):
                return got
            path = path.rsplit("/", 1)[0] or "/"

    def size(self) -> int:
        """The ring's size as the volume holds it — `maxVolumeSize`, what it was formatted or last resized to."""
        with self.reading() as r:
            return int((r.info().get("info") or {}).get("maxVolumeSize") or 0)

    # The writer's settings, before its first sample: how a sequence is cut by time and how long a block may wait
    # (`SEQUENCE_FLUSH_MS`, `BLOCK_FLUSH_S`), and how a volume this recorder formats is cut. A writer picked up again
    # (`reattached`) keeps the settings it had; the engine says so, and that is not a failure to open.
    def _configure(self) -> None:
        settings = {k: v for k, v in (("maxBlockSize", self.block), ("optimalReadSize", self.read),
                                      ("sequenceFlushPeriodMs", self.sequence_flush_ms),
                                      ("blockFlushPeriodSec", self.block_flush_s)) if v}
        try:
            self.writer.configure(**settings)
        except ObsdError as e:
            log.warning("%s: the writer keeps its own settings (%s)", self.name, e.name)

    def put(self, unit, epoch: int, sample: Sample, backfill: bool = False) -> str:
        """One sample into the recording's stream: `OK`, or `SEQUENCE_LOST` (taken — an earlier sequence was
        lost). Raises `ObsdError` for a sample NOT taken — the caller skips to the next key frame — and
        `Unavailable` when this volume is not open for writing any more (closed, or the engine went away)."""
        w = self.writer
        if w is None:
            raise Unavailable("PUT_MEDIA", f"{self.name} is not open for writing")
        self._fenced("PUT_MEDIA")
        name = stream_name(unit, epoch, backfill)
        try:
            status = w.put(name, sample)
            self._took(name, sample)
            return status
        except SessionLost:
            self.lost = True
            raise
        except Closed:
            self._closed_under(w)
            raise
        except ObsdError as e:
            # The engine's own fence (its patch 07): the volume's lock is another writer's, found at its path before a
            # block was written. Not the engine lost — a remount would only find the other writer's lock — but the
            # place lost: nothing more is sent, and the recorder gives the volume up (`RecWorker.volume_pass`).
            if e.name == "WRITER_STOPPED" and "lock lost" in e.detail:
                self.lock_lost = True
            raise

    def finish(self, unit, epoch: int, backfill: bool = False) -> bool:
        w = self.writer
        if w is None:
            return False
        self._fenced("FINISH_MEDIA")
        try:
            return w.finish(stream_name(unit, epoch, backfill))
        except SessionLost:
            self.lost = True
            raise
        except Closed:
            self._closed_under(w)
            raise

    # EVERY SAMPLE INTO A VOLUME ANY BOX MAY SERVE IS FENCED (the review's fifth pass, blocker 1). The hold was checked
    # before `VOLUME_MOUNT_RW` and never again: a box frozen whole — recorder and daemon — woke with its writer
    # mounted, and its pipelines put thirty frames into a ring another box had taken meanwhile, all `OK`. The hold's
    # confirmation is asked on every sample now, the way a lease is (`Lease.may_write`): too old, and nothing is sent.
    #
    # A CHECK BEFORE SENDING, NOT A TOKEN (the review's sixth pass). Nothing travels with the sample that the engine
    # could refuse it by: a process frozen between this check and the send puts that one sample into a volume another
    # box has mounted meanwhile, and it is taken — reproduced: one frame `OK`. The fence of a volume is the ENGINE's,
    # and the course requires an engine that has one (ObjectStorage's patch 07): it checks the volume's lock at its
    # path before every block, status and removal, stops a writer whose lock is another's (`WRITER_STOPPED`, "volume
    # lock lost" — `lock_lost` here) and never removes a lock that is not its own. So that one frame is refused with
    # its block. What this check adds is time: nothing is SENT from ten seconds before anybody else may take the hold
    # (`RecWorker._may_write_volume`), instead of from the engine's next block.
    def _fenced(self, op: str) -> None:
        if self.lock_lost:
            raise Fenced(op, f"{self.name}: the engine says the volume's lock is another writer's: nothing sent")
        if self.fence is not None and not self.fence():
            raise Fenced(op, f"{self.name}: the hold this recorder writes it under is not confirmed: nothing sent")

    def abandon(self, timeout: float | None = None) -> bool:
        """The writer given up WITHOUT writing anything more (`Writer.abandon`: the engine's `WRITER_ABANDON`) and the
        volume let go: True when that is done — or the daemon no longer knows the writer. False when the daemon did
        not answer: the writer may be alive in the session, and whoever owns the session leaves it behind.

        What the writer had taken and not written is lost with it, and `dropped` says how much (the review's sixth
        pass; `unwritten`). Counted after the writer is given up: the giving up does not wait for a count."""
        w, self.writer = self.writer, None
        answered = True
        if w is not None:
            try:
                w.abandon(timeout)
            except (SessionLost, Closed):
                pass                               # not the daemon's any more: nothing to give up
            except Unavailable:
                answered = False
        self.dropped = self.unwritten(look=answered) if w is not None else {}
        if self.volume is not None and answered:
            try:
                self.volume.close()
            except ObsdError:
                pass
        self.volume = None
        return answered

    # One frame the engine took: the stream's span since the mount, and when — kept for as long as the frame may be
    # unwritten: a sequence is cut after `sequence_flush_ms`, its block written `block_flush_s` later (`_configure`).
    def _took(self, name: str, sample: Sample) -> None:
        span = self.taken.setdefault(name, [sample.begin, sample.end])
        span[0], span[1] = min(span[0], sample.begin), max(span[1], sample.end)
        now = self._taken_at = time.monotonic()
        recent = self._recent.setdefault(name, deque())
        recent.append((now, sample.begin))
        while now - recent[0][0] > self._flush_window():
            recent.popleft()

    def _flush_window(self) -> float:              # seconds a taken frame may stay unwritten in a working engine, with room
        return (self.sequence_flush_ms or 10_000) / 1000 + (self.block_flush_s or 60) + 5

    def unwritten(self, look: bool = True) -> dict[str, tuple[float, float]]:
        """Of what this writer took, what is not on the volume: `{stream: (from, to)}`, unix seconds. `look`: ask a
        reader — from the end of what it sees of the stream to the last frame taken, exactly. Without looking (the
        daemon does not answer) it is a bound: the frames taken within the engine's flush periods of the last one it
        took — the daemon was answering then, and whatever was older had been written."""
        taken = {name: tuple(span) for name, span in list(self.taken.items())}
        seen: dict[str, int] | None = None
        if look and taken:
            try:
                with self.reading() as r:
                    seen = {}
                    for name in taken:
                        last = r.find(name, FOREVER, backwards=True)
                        seen[name] = last.end if last is not None else NEVER
            except ArchiveError:
                seen = None                        # the volume does not answer after all: the bound
        out = {}
        for name, (first, last) in taken.items():
            if seen is not None:
                start = max(first, seen[name])
            else:
                recent = [b for at, b in list(self._recent.get(name, ())) if at >= self._taken_at - self._flush_window()]
                start = min(recent) if recent else last
            if last > start:
                out[name] = (unix_s(start), unix_s(last))
        return out

    # `Closed` on the writer this store still uses — not one a seal has already replaced — is a writer that is gone:
    # its close went out and the store kept the handle (the review's fifth pass). Counted as the engine lost, so the
    # pass mounts again; before, every sample after it was `Closed`, `lost` never set, for as long as the process ran.
    def _closed_under(self, w) -> None:
        if self.writer is w:
            self.writer = None
            self.lost = True

    def resize(self, quota: int) -> None:
        """A new quota is a new size of the ring, at once and without stopping: shrinking frees the oldest. A write
        into the volume like any other: under the same fence (the review's seventh pass, the sweep of writing paths)."""
        if self.writer is not None and quota and quota != self.quota:
            self._fenced("WRITER_RESIZE")
            self.writer.resize(quota)
        self.quota = quota or self.quota

    # A SEAL THAT FAILS LEAVES NO DEAD WRITER (the review's fifth pass). A close that timed out left `writer` set to the
    # handle it had just closed: every sample after it was `Closed`, `lost` stayed False, and the incidents volume took
    # nothing until a restart — and five minutes later its keep was a false alarm. Now the writer is forgotten before
    # its close goes out, whatever comes back: a close or a mount that did not come back leaves an `orphan` — the session
    # is left behind on the pass's `close`, and a successor picks the writer up — and the engine lost is `lost`.
    # Either way the next pass sees no writer and mounts again.
    def seal(self) -> None:
        """Close the writer and take it again: its last block is closed, and what was written is readable. What
        a recorder does when the minutes it just wrote must be an answer now — a copied range, a stop."""
        if self.writer is None:
            return
        self._fenced("WRITER_CLOSE")               # a close is the writer's last write: under the same fence
        w, self.writer = self.writer, None
        self.taken, self._recent = {}, {}          # the close is the flush: what was taken is written
        try:
            w.close()
        except SessionLost:
            self.lost = True
            raise
        except Unavailable:
            self.orphan = True                     # closed or not, nobody knows: the session is left behind
            raise
        except Closed:
            self.lost = True
            raise
        except ObsdError:
            pass                                   # refused: the handle is gone either way; a new writer is mounted
        try:
            self.writer = self._mount_rw(self._open_volume())
        except SessionLost:
            self.lost = True
            raise
        self._configure()

    def close(self, timeout: float | None = None) -> bool:
        """The writer closed — after its flush — and the volume let go. In that order: closing is what makes the
        last minutes readable, and a volume released first would be somebody else's with a writer still in it.

        True when the writer is let go: closed, or a writer the daemon no longer knows. False when it may still be
        ALIVE in the session — its close was refused in a silence, or did not come back within `timeout` — and
        then whoever owns the session must leave it behind (`Session.abandon`), or every mount of this volume is
        `ALREADY_LOCKED` for as long as the session lives (the review's fourth pass, blocker 1). False as well for an
        `orphan` — a mount or a seal whose answer did not come back (the review's fifth pass, blocker 2).

        And once the writer's close did not come back, the volume's close is not sent at all (the review's fifth pass,
        Т-M1): the session goes with it, and on the thread that renews the leases it was one more call's wait."""
        let_go = not self.orphan
        if self.writer is not None:
            try:
                self.writer.close(timeout)
            except SessionLost:
                pass                               # the daemon lost it: gone, nothing to let go of
            except Unavailable:
                let_go = False
            except ObsdError:
                pass
        if self.volume is not None and let_go:
            try:
                self.volume.close()
            except ObsdError:
                pass
        self.writer = self.volume = None
        return let_go

    # -- reading: a reader of its own for every question --------------------------------------------------
    # A reader sees what was closed when it mounted, so every question mounts one — and CLOSES it when the question
    # is answered, its own and nobody else's. There used to be one, `self._reader`, which each question closed and
    # replaced: the door, the backfill, the keeps and the pass read the volume at once, and every one of them closed
    # the reader another was in the middle of — `UNKNOWN_HANDLE` in an export, a keep's copy that never completed
    # (the review's third pass, blocker 5). And whatever the engine answers inside is an `ArchiveError` by kind, so
    # a door that catches those catches everything the volume can say.
    @contextmanager
    def reading(self):
        try:
            r = self._open_volume().mount_ro()
        except (ObsdError, ValueError) as e:
            raise self._classified(e) from None
        try:
            yield r
        except ObsdError as e:
            raise self._classified(e) from None
        finally:
            try:
                r.close()
            except ObsdError:
                pass

    def units(self) -> list[str]:
        with self.reading() as r:
            names = {p[0] for p in (parse_stream(s) for s in r.streams()) if p}
        from w2cplatform.doors import numeric                # not `isdigit` + `int`: a recording `7²` (the ninth pass)
        return sorted(names, key=lambda d: (0, n, "") if (n := numeric(d)) is not None else (1, 0, d))

    def spans(self, unit=None, t0: float | None = None, t1: float | None = None, reader=None) -> list[Span]:
        """What the index holds — of one recording, or of all — as spans, in time order. One question, one
        reader: `reader` is the one the caller already mounted, if it is asking more than this."""
        if reader is None:
            with self.reading() as r:
                return self.spans(unit, t0, t1, reader=r)
        r = reader
        lo = archive_ms(t0) if t0 is not None else NEVER
        hi = archive_ms(t1) if t1 is not None else FOREVER
        out = []
        for name in r.streams():
            p = parse_stream(name)
            if p is None or (unit is not None and p[0] != str(unit)):
                continue
            for iv in self._timeline(r, name, lo, hi):
                out.append(Span(p[0], p[1], unix_s(iv["start"]), unix_s(iv["end"]), int(iv.get("size", 0)), p[2]))
        return sorted(out, key=lambda s: (s.start, s.epoch))

    # A stream's timeline, asked IN WINDOWS. An engine before patch 05 answered `INTERNAL_ERROR` to a timeline over
    # six days of footage or more: it reads the index an hour at a time and handed every read to the volume's
    # pool at once, whose queue holds 128 — five days fit, six did not, and what the cache already held decided
    # the rest (the engine's session found and fixed it: the reads go in portions now). The windows stay as
    # insurance against an older daemon: a recording a month deep is asked five days at a time, cut to what the
    # stream holds — its first and last sequence — and a window refused anyway is asked again in halves, down to
    # an hour. Intervals that touch across a cut are put back together.
    def _timeline(self, r, name: str, lo: int, hi: int) -> list[dict]:
        first, last = r.find(name, lo), r.find(name, hi, backwards=True)
        if first is None or last is None:
            return []
        lo, hi = max(lo, min(first.start, hi)), min(hi, max(last.end, lo))
        out: list[dict] = []

        def ask(a: int, b: int) -> None:
            try:
                got = r.timeline(name, a, b)
            except ObsdError as e:
                if e.name != "INTERNAL_ERROR" or b - a <= 3600_000:
                    raise
                ask(a, (a + b) // 2); ask((a + b) // 2, b)
                return
            for iv in got:
                if out and iv["start"] <= out[-1]["end"]:
                    if iv["end"] > out[-1]["end"]:
                        out[-1] = {**out[-1], "end": iv["end"], "size": out[-1].get("size", 0) + iv.get("size", 0)}
                    continue
                out.append(dict(iv))

        t = lo
        while t < hi:
            ask(t, min(t + TIMELINE_WINDOW, hi))
            t += TIMELINE_WINDOW
        return out

    def timeline(self, unit, t0: float, t1: float, current_epoch: int | None = None) -> list[dict]:
        """Spans overlapping `[t0, t1)`, each marked `fenced` when its epoch is older than the current one — how
        the page shows a zombie's footage, kept and told apart."""
        return [{"start": s.start, "end": s.end, "epoch": s.epoch, "source": s.source, "bytes": s.bytes,
                 "fenced": current_epoch is not None and s.epoch < current_epoch}
                for s in self.spans(unit, t0, t1) if s.end > t0 and s.start < t1]

    def coverage(self, unit, gap: float = STITCH) -> list[tuple[float, float]]:
        return stitch(((s.start, s.end) for s in self.spans(unit)), gap)

    def depth_days(self, unit, now: float) -> float:
        cov = self.coverage(unit)
        return max(0.0, (now - cov[0][0]) / 86400) if cov else 0.0

    def samples(self, unit, t0: float, t1: float) -> list[Sample]:
        """The frames of `[t0, t1)`, each stretch from the epoch that owns it, each starting on the key frame AT
        OR BEFORE its first moment — what an export, a scan or a copy into another volume takes. A stretch that
        opens at 10:05 is inside a group of pictures that opened at 10:04:58, and without that key frame nothing
        of 10:05 decodes: the lead-in comes along, and whoever asked clips it (`Scan.accepts`). All of it, in a
        list: for a short range. A long one is `stream`ed."""
        return list(self.stream(unit, t0, t1))

    # The same frames, one SEQUENCE at a time (the review's third pass, blocker 6). A day of one camera is tens of
    # gigabytes, and the door built it into one string and the keep copied it out of one list: what is held now is
    # a sequence — a block at most — and whatever group of pictures is waiting for the moment the range begins.
    # The reader is held for as long as the frames are being taken, and closed when they are, or when whoever was
    # taking them stops.
    def stream(self, unit, t0: float, t1: float):
        with self.reading() as r:
            for span, lo, hi in authoritative(self.spans(unit, t0, t1, reader=r), t0, t1):
                a, b = archive_ms(lo), archive_ms(hi)
                lead: list[Sample] = []                  # since the last key frame, until the stretch's first moment
                started = False
                for e in r.sequences(span.stream, a, b):
                    for smp in r.read(e):
                        if smp.begin >= b:
                            break
                        if started:
                            yield smp
                            continue
                        if smp.key:
                            lead = []
                        lead.append(smp)
                        if smp.end > a:                  # the first moment: from the key frame at or before it
                            started = True
                            k = next((i for i, x in enumerate(lead) if x.key), None)
                            yield from (lead[k:] if k is not None else [])
                            if k is None:                # no key frame at or before: the stretch opens on its next one
                                started = False
                            lead = []
                    else:
                        continue
                    break

    def status(self) -> dict:
        """The ring: `usedSize`, `availableSize`, `totalWritten`, `firstBlockId`, `numBlocks`. A first block
        past nought is a ring that has closed: it has begun to overwrite."""
        with self.reading() as r:
            return dict(r.status())
