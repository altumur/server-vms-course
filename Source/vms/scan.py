"""Reading an INTERVAL of the archive, and remembering how far you got.

    what was recorded      the recording's spans, from the archive doors of the recorders that hold its
                           volumes (`recording_spans`) — the index of ObjectStorage, read fresh
    <resource>/detjob/<job>/progress.jsonl     what a scan has processed: one line per stretch

The live detector never needed this. It reads a fan-out with no beginning and no end, and "where am I" is
"now". A scan over recorded footage has both ends, so it needs the two things the live path never asked for:
which stretches of the recording cover `[from, to)`, and which of them are already behind it.

The first answer comes out of the volumes' index and nothing else — not the recording's row, not who holds
it now: footage from last March is in whatever volume was written then, and who won the race for those
minutes is in the stream names, not in a heartbeat.

The progress file is a scan's own, on the resource's tree where its events are: append-only, rebuildable
from what it describes, and a crash between the work and the line costs a re-scan of one stretch rather
than a wrong answer.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from w2cplatform.events import unit_dir
from w2cplatform.rows import PARSE_ERRORS, Table, answer, finite

from .archive import Span, authoritative

SUB = "detjob"          # the scan's own tree, beside `rec/` and `vms/` on the same resource
SURVEY = "survey"       # the standing survey's own tree, beside it
PROGRESS = "progress.jsonl"


# -- the OTHER archive: what a device holds, span by span -------------------------------------------
#
# The summary in the holder's heartbeat (`from`, `to`, `fragments`) answers "is there anything there at
# all". It cannot answer "is there anything at 10:05", and for a device recording on motion the difference
# is most of the day: between its first and its last minute there is mostly nothing.
#
# `None` means the driver cannot list — not that the device holds nothing. A caller that folds the two
# together promises a scan minutes that do not exist, or refuses one that does.
def device_recordings(url: str, t0: float, t1: float, timeout: float = 10.0) -> list[tuple[float, float]] | None:
    import json as _json
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(f"{url}?from={t0}&to={t1}", timeout=timeout) as r:
            body = _json.loads(answer(r) or b"{}")
    except urllib.error.HTTPError as e:
        if e.code == 501:
            return None                                  # this driver cannot list; the summary is all there is
        raise
    except PARSE_ERRORS:
        return None                                      # an answer that does not parse lists nothing: the summary stands
    # Each span alone (the review's eighth pass): one that does not parse is that span's — counted, and the others
    # stand; `float(sp["from"])` bare took the whole listing, and with it the job's or the survey's step.
    out = []
    for sp in (body.get("spans", []) if isinstance(body, dict) and isinstance(body.get("spans", []), list) else []):
        got = DOOR_SPANS.read(f"vms/recordings@{url}", lambda sp=sp: (finite(sp["from"]), finite(sp["to"])))
        if got is not None:
            out.append(got)
    return out


# The seconds of `[t0, t1)` a device actually holds. `spans` is what `device_recordings` returned, and the
# `None` case is the caller's to decide: here it means "we cannot tell", and the honest fallback is the
# summary — optimistic, which is right, because being wrong the other way refuses work that would succeed.
def covered_by(spans: list[tuple[float, float]] | None, t0: float, t1: float) -> float:
    if spans is None:
        return max(0.0, t1 - t0)
    return sum(max(0.0, min(b, t1) - max(a, t0)) for a, b in spans)


# One stretch of one span: the footage, and the part of it this scan asked for.
@dataclass(frozen=True)
class Scan:
    seg: Span
    t0: float             # unix seconds; the stretch, not the span — they differ at both ends
    t1: float

    @property
    def seconds(self) -> float:
        return max(0.0, self.t1 - self.t0)

    # Identity in the log. The STREAM and the stretch, not the stream alone: one stream can come back in two
    # stretches when a newer epoch owns the minutes between them, and a log keyed by stream alone would call the
    # second stretch done when only the first was.
    def key(self) -> str:
        return f"{self.seg.stream}@{self.t0:.3f}-{self.t1:.3f}"

    # Whether an event the model reports at `ts` belongs to this scan. Decoding starts at a KEY FRAME — the
    # sequence that holds 10:05 may open at 10:04 — so the frames before `t0` are seen, and what they produce is
    # not what was asked for. Without this the answer to "what happened between 10:05 and 10:12" quietly
    # contains 10:04.
    def accepts(self, ts: float) -> bool:
        return self.t0 <= ts < self.t1


# Every stretch of `[t0, t1)` that footage covers, each given to the HIGHEST EPOCH that covers it
# (`archive.authoritative`). Two epochs overlap whenever a recorder was fenced with footage in flight: the
# zombie's stream and the survivor's describe the same minutes. Read both and those minutes are scanned twice,
# so the operator gets every car counted twice; drop every older epoch and the minutes BEFORE the takeover —
# which only the older epoch ever held — disappear from the answer. So the unit of the decision is the stretch.
def plan(spans: list[Span], t0: float, t1: float) -> list[Scan]:
    return [Scan(s, a, b) for s, a, b in authoritative(list(spans), float(t0), float(t1))]


# How far this recording's VISIBLE footage reaches: the end of its last span, 0 when there is none. What a scan
# whose interval runs into the future reads to know whether the footage has caught up with its end.
def written_through(spans: list[Span]) -> float:
    return max((s.end for s in spans), default=0.0)


# What was recorded of `unit` in `[t0, t1)`, as the volumes' index has it: asked of the archive door of every
# live recorder (`/spans/<unit>`), since each serves the one volume it holds and a recording's life may have
# been written into several. `None` when no door answered at all — "nobody could say" is not "nothing recorded".
def recording_spans(objects, unit, t0: float, t1: float, now: float, timeout: float = 5.0, eyes=None) -> list[Span] | None:
    seen = recording_read(objects, unit, t0, t1, now, timeout=timeout, eyes=eyes)
    return seen.spans if seen.answered else None


# …and what the answer is MISSING (the review's third pass). One door answering is not the whole recording: the
# recording moved from volume A to B, A's door did not answer, and the scan planned B's half, scanned it, and
# called the job `done` — the other half never scanned, for good. So the read says which doors were asked and did
# not answer (`silent`, by recorder) and which declared volumes no answering door serves (`unread`: nobody holds
# them now, or their holder is silent), and a scan that is missing anything is not finished (`DetJobWorker`).
# A volume the administrator DISABLED is nobody's (`volumes.servable`), and waiting for it would be waiting for a
# decision to change: it is not counted.
#
# Not every declared volume — the volumes THIS recording was in (the review's fourth pass). "Declared and nobody's
# door read it" made one volume without a recorder — a disk declared for a box not yet racked — hold every scan of
# the cluster in `waiting` for good. What the store knows about where a recording lived is the recorders' heartbeats:
# each names its volume and the recordings it holds, and the last one of a recorder that went silent says what was
# on its volume when it did. So `unread` is the timeline's rule (`unserved_volumes`: a volume whose last recorder is
# silent and that no live recorder holds) narrowed to the volumes whose last recorder named this recording. A
# volume that held it once and something else when its recorder died is not seen by this — the scan's deadline is
# what bounds that (`DetJobWorker.WAIT_MAX`), and the answer says what it did not read.
@dataclass
class Read:
    spans: list[Span]
    answered: bool                 # at least one door answered
    silent: list[str]              # recorders whose door was asked and did not answer
    unread: list[str]              # volumes that held this recording and nobody serves now
    garbled: list = field(default_factory=list)   # recorders whose door answered spans that do not parse (`door_spans`)

    @property
    def partial(self) -> bool:
        return bool(self.silent or self.unread or self.garbled)


# A SPAN A DOOR ANSWERED IS READ ALONE (the review's eighth pass, part 4). `int(sp["epoch"])` stood outside the door's
# `try`: a door of another build or a proxy answering `{"epoch": "e3"}` raised out of the read, the scan worker moved no
# job at all (it is called with no `try` per job), and the span of the good door beside it was lost too. Now an answer
# that is not `{spans: [...]}` is that door not answering (`silent`), and a span that does not parse is that span's:
# skipped, counted once per door and recording (`DOOR_SPANS`), and the door named in `garbled` — the read is partial,
# so the scan does not end `done` without the minutes it could not read. The keeps' copier reads its doors through the
# same parser (`RecWorker._door_timeline`).
DOOR_SPANS = Table("door_span", "that stretch is passed by until the door says it whole", "span a door answered")


def door_spans(key: str, body) -> tuple[list[dict], bool]:
    """The spans of a door's `/timeline` answer, each read alone — `([{start, end, epoch, bytes, source, …}], whole)`;
    `ValueError` when the answer is not `{spans: [...]}` at all."""
    if not isinstance(body, dict) or not isinstance(body.get("spans", []), list):
        raise ValueError("a timeline is {spans: [...]}")
    out, whole = [], True
    for sp in body.get("spans", []):
        try:
            out.append({**sp, "epoch": int(finite(sp.get("epoch") or 0)), "start": finite(sp["start"]),
                        "end": finite(sp["end"]), "bytes": int(finite(sp.get("bytes") or 0)),
                        "source": str(sp.get("source", "live"))})
        except PARSE_ERRORS as e:
            DOOR_SPANS.garbled(key, e)
            whole = False
    if whole:
        DOOR_SPANS.parsed(key)
    return out, whole


#
# Which doors are live by what the scan worker saw change (`eyes`, its `Eyes`; the product's r29-writers2): `is_live` was
# the recorder's clock against the worker's, and a recorder behind by 100 s was a door nobody asked — its minutes were
# "unread", the scan waited, then ended without them. Without eyes, `is_live` still.
def recording_read(objects, unit, t0: float, t1: float, now: float, vars_=None, timeout: float = 5.0, eyes=None) -> Read:
    import json as _json
    import urllib.request
    from w2cplatform.console import heard_live, heartbeats
    out, answered, silent, read, garbled = set(), False, [], set(), []
    every = heartbeats(objects, "rec/")
    for w, hb in sorted(every.items()):
        url = str(hb.extra.get("url") or "")
        if not url or not heard_live("rec", w, hb, now, 45.0, eyes):   # whose clock: the reader's (M9, r29-writers2)
            continue
        try:
            with urllib.request.urlopen(f"{url.rstrip('/')}/spans/{unit}?from={t0}&to={t1}", timeout=timeout) as r:
                spans, whole = door_spans(f"rec/doors/{w}#{unit}", _json.loads(answer(r)))
        except (OSError, *PARSE_ERRORS):
            silent.append(w)
            continue
        answered = True
        if not whole:
            garbled.append(w)
        if hb.extra.get("volume") and whole:
            read.add(str(hb.extra["volume"]))            # a volume read in part is not read: it stays `unread` if nobody else
        for sp in spans:
            out.add(Span(str(unit), sp["epoch"], sp["start"], sp["end"], sp["bytes"], sp["source"]))
    unread = []
    if vars_ is not None:
        from . import volumes
        from .footage import unserved_volumes          # the timeline's rule, read and not copied
        off = {v.name for v in volumes.declared(vars_) if not v.enabled}

        def held_it(recorder: str) -> bool:
            hb = every.get(recorder)
            return hb is not None and any(str(st.get("id")) == str(unit) for st in hb.status if isinstance(st, dict))
        unread = [g["volume"] for g in unserved_volumes(objects, now, eyes=eyes)
                  if g["volume"] not in read and g["volume"] not in off and held_it(g["recorder"])]
    return Read(sorted(out, key=lambda s: (s.start, s.epoch)), answered, silent, unread, garbled)


# Seconds of `[t0, t1)` the plan actually covers. The operator asked for an hour; if forty minutes were
# recorded, a finished scan that found nothing has to be able to say WHICH — "nothing happened" and
# "nothing was recorded" are different answers and only one of them is about the footage.
def covered(scans: list[Scan]) -> float:
    return sum(s.seconds for s in scans)


PROGRESS_LINES = Table("progress_line", "the stretch it names is scanned again", "line of a scan's progress")


def _progress_line(d) -> dict:
    return {**d, "from": finite(d["from"]), "to": finite(d["to"]), "events": int(finite(d.get("events") or 0))}


class ScanLog:
    """What a scan has already processed: `<resource>/detjob/<job>/progress.jsonl`,
    one line per stretch, appended AFTER the stretch is scanned and its events are
    written. Durable, so a worker restarting on this server resumes instead of
    starting again; and on the resource rather than in a row, because a worker's
    ACL is `[<name>/epoch/*, <name>/slots/*]` — it may not write configuration."""

    def __init__(self, resource_root: str, job):
        self.path = os.path.join(unit_dir(resource_root, SUB, str(job)), PROGRESS)

    def append(self, scan: Scan, events: int, at: float) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps({"kind": "scan", "key": scan.key(), "stream": scan.seg.stream, "epoch": scan.seg.epoch,
                                "from": scan.t0, "to": scan.t1, "events": int(events), "at": float(at)}) + "\n")

    # A line that does not parse — the half line a crash between the write and its end leaves — is that line's (the
    # review's eighth pass, a sibling of the doors' spans): read whole, it raised out of every pass of the job for good.
    # Passed by and counted (`PROGRESS_LINES`): the stretch it named is scanned again, which costs a re-scan of one
    # stretch, as the file's own rule says.
    def read(self) -> list[dict]:
        try:
            with open(self.path) as f:
                lines = [l for l in f if l.strip()]
        except FileNotFoundError:
            return []
        out = []
        for i, l in enumerate(lines):
            d = PROGRESS_LINES.read(f"{SUB}/progress/{self.path}#{i}", lambda l=l: _progress_line(json.loads(l)))
            if d is not None:
                out.append(d)
        return out

    # For the operator's progress, and for nothing else. It is the far end of the furthest stretch
    # recorded, which is NOT a point everything before is finished at: resuming from it would skip a
    # stretch that failed while a later one succeeded. `remaining` is the authoritative answer.
    def done_through(self) -> float:
        return max((float(d["to"]) for d in self.read()), default=0.0)

    def events(self) -> int:
        return sum(int(d.get("events", 0)) for d in self.read())

    # Since when this scan has been waiting for what it could not read, and — once its deadline passed — what it ended
    # without (the review's fourth pass). Durable beside the progress, for the same reason: a worker restarted on this
    # server does not start the deadline again. `{since, partial?}`; gone once nothing is missing.
    def _waiting_path(self) -> str:
        return os.path.join(os.path.dirname(self.path), "waiting.json")

    def waiting(self) -> dict | None:
        try:
            with open(self._waiting_path()) as f:
                d = json.load(f)
            return {"since": finite(d["since"]), **({"partial": list(d["partial"])} if d.get("partial") else {})}
        except (FileNotFoundError, *PARSE_ERRORS):       # `since` past a float, a file nested past JSON's depth (the tenth round)
            return None

    def wait(self, now: float, partial: list | None = None) -> dict:
        d = self.waiting() or {"since": float(now)}
        if partial:
            d["partial"] = list(partial)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self._waiting_path() + ".tmp"
        with open(tmp, "w") as f:
            json.dump(d, f)
        os.replace(tmp, self._waiting_path())
        return d

    def not_waiting(self) -> None:
        try:
            os.remove(self._waiting_path())
        except FileNotFoundError:
            pass


# Moments into stretches: what to keep when the reason for keeping it is that a model fired.
#
# An event is an instant and footage is an interval, so something has to turn one into the other, and the
# three numbers are all decisions rather than tuning. `pre` and `post` are what makes the clip watchable —
# a car crossing the line at 10:04:31 is useless as a one-second file and obvious as a twenty-second one.
# `join` is what keeps a busy minute from becoming three hundred two-second clips: hits closer together
# than that are one stretch, and the gap between them is cheaper to keep than to cut out.
#
# `watched` clips the result to what was actually looked at — padding runs off the end of a span otherwise,
# and asks for minutes the device never recorded.
def hit_spans(times: list[float], watched: list[tuple[float, float]],
              pre: float, post: float, join: float) -> list[tuple[float, float]]:
    if not times:
        return []
    raw = sorted((t - pre, t + post) for t in times)
    merged: list[list[float]] = []
    for a, b in raw:
        if merged and a - merged[-1][1] <= join:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    out = []
    for a, b in merged:
        for wa, wb in watched:
            lo, hi = max(a, wa), min(b, wb)
            if hi > lo:
                out.append((lo, hi))
    return sorted(out)


class Frontier:
    """How far a standing survey has watched: one number, durable, beside its events.

    The same argument as `ScanLog` and the same place for the same reason — a worker
    may not write configuration — but a different shape, because the work is different.
    A scan has a plan and ticks stretches off it; a survey has no end, and what it
    keeps is a moving edge."""

    # `sub` because the sixth subsystem keeps the same shape of number for the same reason: how far it has
    # READ. The survey's watched-through and the evaluator's considered-through are one idea, and one idea
    # gets one file format — the default keeps every survey written before this call site unchanged.
    def __init__(self, resource_root: str, unit, sub: str = SURVEY):
        self.path = os.path.join(unit_dir(resource_root, sub, str(unit)), "frontier.json")

    def read(self) -> float | None:
        try:
            with open(self.path) as f:
                return finite(json.load(f)["watched_through"])
        # …or a file that does not read as a frontier — a list (`TypeError`), a number past a float, nested past JSON's
        # depth (the review's tenth round): it raised out of the survey's and the evaluator's pass, every pass.
        except (FileNotFoundError, *PARSE_ERRORS):
            return None                                  # never started, or the file was lost: the row decides where to begin

    # Written after the events of that stretch, and atomically: a crash between the work and the number
    # costs a re-watch, a half-written number would cost the frontier itself.
    def set(self, t: float) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"watched_through": float(t)}, f)
        os.replace(tmp, self.path)


# The plan minus what the log says is behind us — what a restarted worker picks up, and what a follower scans
# next. By TIME, not by key: the index draws a stream's sequences that touch as ONE span, so the span a follower
# scanned up to 10:05 is, a block later, a span to 10:10 — a different stretch with a different key, and matching
# keys would scan its first five minutes again and count every car in them twice.
#
# And by time over the whole RECORDING, not per stream (the review's third pass). An epoch takeover moves the
# minutes of the overlap from the old stream to the new one once the new one is visible: per stream, minutes
# already scanned under `7/e1` were scanned again under `7/e2`, every car in them counted twice. The minutes are
# the camera's whichever writer won them; scanned once is the point.
def remaining(scans: list[Scan], log: ScanLog) -> list[Scan]:
    from .archive import parse_stream, subtract
    done: dict[str, list[tuple[float, float]]] = {}
    for d in log.read():
        parsed = parse_stream(str(d.get("stream", "")))
        done.setdefault(parsed[0] if parsed else str(d.get("stream", "")), []).append((float(d["from"]), float(d["to"])))
    return [Scan(s.seg, a, b) for s in scans for a, b in subtract((s.t0, s.t1), done.get(str(s.seg.unit), []))
            if b - a > 1e-6]
