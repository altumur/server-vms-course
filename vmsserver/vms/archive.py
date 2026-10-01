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

import time
from dataclasses import dataclass
from urllib.parse import urlsplit, unquote

from w2cplatform.events import EventLog
from w2cplatform.obsd import ObsdError, Sample, Session, Unavailable, archive_ms, unix_s

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


def visible_from(row: dict | None, now: float) -> float:
    """`retention_days` is a ceiling on what the doors show — the ring decides what is still THERE."""
    days = float((row or {}).get("retention_days") or 30)
    return now - days * 86400


class ArchiveError(Exception):
    """A volume that will not open or take writes, by KIND — the recorder answers each differently:

    wrong   only a person changes it: a path that is not a volume, no permission, a bucket that refuses the key.
            The volume is handed back
    away    a timeout, a network that is down, the daemon itself gone. Kept: it is back in a minute, and handing
            it back would reshuffle every recording on it for a link that returns
    busy    another writer holds it on this host (`ALREADY_LOCKED`) — a recorder of the same volume that has
            not let go yet, or one whose grace the daemon is still waiting out"""

    def __init__(self, kind: str, detail: str, name: str = ""):
        self.kind, self.detail, self.name = kind, detail, name    # `name`: the engine's status, or UNAVAILABLE
        super().__init__(f"{kind}: {detail}")


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
    passes `rec:<volume>`, which the platform's hold makes unique — and what gets a vanished writer back."""

    def __init__(self, url: str, name: str = "", quota: int = 0, owner: str = "", session: Session | None = None,
                 wall=time.time, secret: str = "", block: int = BLOCK, read: int = READ, access_key: str = "",
                 sequence_flush_ms: int = SEQUENCE_FLUSH_MS, block_flush_s: int = BLOCK_FLUSH_S):
        self.url, self.name, self.quota, self.owner = url, name or url, int(quota), owner
        self.session = session or Session(client="vms-archive")
        self.wall, self.secret, self.block, self.read, self.access_key = wall, secret, block, read, access_key
        self.sequence_flush_ms, self.block_flush_s = int(sequence_flush_ms), int(block_flush_s)
        self.volume = None
        self.writer = None
        self._reader = None
        self.formatted = False                     # this open formatted the volume: it was new
        self.reattached = False                    # the daemon handed back a writer a vanished process left

    def _open_volume(self):
        if self.volume is None:
            self.volume = self.session.open_volume(params=volume_params(self.url, self.secret, self.access_key))
        return self.volume

    # Opening is the only honest test: a row can name a path that does not exist, a mount that is gone or a
    # bucket nobody can reach. A volume that is not there yet is FORMATTED — at its quota, which is the size of
    # the ring — and then mounted for writing under `owner`.
    def open(self, write: bool = True) -> "Archive":
        try:
            vol = self._open_volume()
            if not vol.exists():
                if not self.quota:
                    raise ArchiveError("wrong", f"{self.name}: no volume there and no quota to format one with")
                vol.format(self.quota, max_block=self.block, optimal_read=self.read, label=self.name)
                self.formatted = True
            if write and self.writer is None:
                self.writer = vol.mount_rw(self.owner)
                self.reattached = self.writer.reattached
                self._configure()
        except (ObsdError, ValueError) as e:
            raise classify(e) from None
        return self

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
        if self.writer is None:
            raise Unavailable("PUT_MEDIA", f"{self.name} is not open for writing")
        return self.writer.put(stream_name(unit, epoch, backfill), sample)

    def finish(self, unit, epoch: int, backfill: bool = False) -> bool:
        return self.writer.finish(stream_name(unit, epoch, backfill)) if self.writer is not None else False

    def resize(self, quota: int) -> None:
        """A new quota is a new size of the ring, at once and without stopping: shrinking frees the oldest."""
        if self.writer is not None and quota and quota != self.quota:
            self.writer.resize(quota)
        self.quota = quota or self.quota

    def seal(self) -> None:
        """Close the writer and take it again: its last block is closed, and what was written is readable. What
        a recorder does when the minutes it just wrote must be an answer now — a copied range, a stop."""
        if self.writer is not None:
            self.writer.close()
            self.writer = self._open_volume().mount_rw(self.owner)
            self._configure()

    def close(self) -> None:
        """The writer closed — after its flush — and the volume let go. In that order: closing is what makes the
        last minutes readable, and a volume released first would be somebody else's with a writer still in it."""
        for h in (self._reader, self.writer, self.volume):
            if h is not None:
                try:
                    h.close()
                except ObsdError:
                    pass
        self._reader = self.writer = self.volume = None

    # -- reading: a fresh reader for every question -----------------------------------------------------
    def reader(self):
        if self._reader is not None:
            try:
                self._reader.close()
            except ObsdError:
                pass
        try:
            self._reader = self._open_volume().mount_ro()
        except ObsdError as e:
            raise classify(e) from None
        return self._reader

    def units(self) -> list[str]:
        names = {p[0] for p in (parse_stream(s) for s in self.reader().streams()) if p}
        return sorted(names, key=lambda d: (0, int(d), "") if d.isdigit() else (1, 0, d))

    def spans(self, unit=None, t0: float | None = None, t1: float | None = None, reader=None) -> list[Span]:
        """What the index holds — of one recording, or of all — as spans, in time order. One question, one
        reader: `reader` is the one the caller already mounted, if it is asking more than this."""
        r = reader or self.reader()
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
        of 10:05 decodes: the lead-in comes along, and whoever asked clips it (`Scan.accepts`)."""
        r = self.reader()
        out: list[Sample] = []
        for span, lo, hi in authoritative(self.spans(unit, t0, t1, reader=r), t0, t1):
            a, b = archive_ms(lo), archive_ms(hi)
            seq = [s for e in r.sequences(span.stream, a, b) for s in r.read(e) if s.begin < b]
            first = next((i for i, s in enumerate(seq) if s.end > a), len(seq))
            key = next((i for i in range(min(first, len(seq) - 1), -1, -1) if seq[i].key), None)
            if key is None:                              # no key frame at or before: the stretch opens on its next one
                key = next((i for i in range(first, len(seq)) if seq[i].key), len(seq))
            out += seq[key:]
        return out

    def status(self) -> dict:
        """The ring: `usedSize`, `availableSize`, `totalWritten`, `firstBlockId`, `numBlocks`. A first block
        past nought is a ring that has closed: it has begun to overwrite."""
        return dict(self.reader().status())
