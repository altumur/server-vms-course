"""The scan worker — the fifth subsystem's worker, and the first whose work ENDS.

A unit is a job: one model over one interval of one recording. The worker does
not subscribe to anything. It plans the interval out of the recording's spans —
the volumes' index, asked of the recorders' archive doors (`vms/scan.py`) —
decodes each stretch in turn, writes what the model saw into the job's own bucket
on the resource, and appends a line to the job's progress for every stretch it
finishes:

    detjob/jobs/<job>          the job: cam, rec, kind, from, to, state — written by the console
    detjob/workers/<j>         the assignment, written by the detjob controller
    detjob/<j>/heartbeat       capacity, headroom, labels; per-job status: phase, done_through, events
    <archive>/detjob/<job>/e<epoch>/…events.jsonl   what the model saw
    <archive>/detjob/<job>/progress.jsonl           how far it got — durable, so a restart resumes

Three things separate it from `DetWorker`, and all three come from the work
having both ends. It runs a BUDGET of stretches per pass rather than a frame:
a job is hours of video and a pass that finished it would starve the heartbeat.
Its events are stamped with MEDIA time, not the clock. And it is the only worker
that can say `done` — which nothing in the placement vocabulary reads yet, so the
row stays placed until the console's reaper moves its state (Lesson 21).

The MODEL is the same object as the live detector's, and that is the point: it
takes a timestamp and answers what it saw. Nothing in it knows whether the frame
behind that timestamp came off a fan-out or off a disk.
"""
from __future__ import annotations

import logging
import os
import time

from w2cplatform import runtime
from w2cplatform.console import holder_of
from w2cplatform.contract import Worker
from w2cplatform.events import EventLog
from w2cplatform.variables import Variables

from .config import DETJOB_SPEC
from .detworker import FakeModel
from .scan import ScanLog, covered, covered_by, device_recordings, plan, recording_read, remaining, written_through

DETJOB = DETJOB_SPEC.sub
TERMINAL = ("done", "failed")
log = logging.getLogger("vms.detjobworker")


class DetJobWorker(Worker):
    """`name` is a slot (`j-1`); `models` maps a kind to a factory `(row) -> Model`,
    the same registry `DetWorker` uses."""

    # Stretches per reconcile pass. A scan is bounded work, and bounded work run to completion inside one
    # pass is a worker that stops heartbeating for an hour: its lease lapses, the controller calls it dead
    # and places the job somewhere else, and now two workers write the same job's events. The budget is
    # what keeps a long job and a live subsystem in the same process.
    STRETCHES_PER_PASS = 4
    STEP = 1.0                     # seconds of media between two looks; a real model decodes, this one counts

    SLOT_PREFIX = "j"                            # a slot it has to make is `j-<n>`, like the ones it is given

    # A job whose interval reaches past what is RECORDED follows the recording: the footage of its last
    # minutes is written while it runs. Done is when the footage has reached the end (`written_through`),
    # or — the recorder stopped, the camera went dark — when the end is older than this many LAGS: a reader sees a
    # block once it is written, and a block is written when it fills or `BLOCK_FLUSH_S` after its sequence was
    # finished, so the footage of `to` is at most one block's worth of time behind (`VISIBLE_LAG_SECONDS`: the block
    # size over the bitrate, for a stream that fills blocks faster than the flush period — the worst path from a
    # frame to an answer; feedback CP).
    FOLLOW_LAGS = 2

    def __init__(self, name: str | None, vars_: Variables, objects, models: dict | None = None,
                 capacity: int | None = None, clock=time.monotonic, wall=time.time, server: str | None = None,
                 archive_root: str | None = None, env: dict | None = None, step: float | None = None):
        env = dict(os.environ if env is None else env)
        super().__init__(DETJOB, None, vars_, objects, clock=clock, wall=wall)
        self.claim_slot(prefer=name if name is not None else runtime.slot(env, "DETJOB_NAME", "j"))
        self.models = models if models is not None else {"motion": FakeModel, "linecross": FakeModel, "lpr": FakeModel}
        self.capacity = capacity if capacity is not None else int(env.get("SCAN_CAPACITY", "2"))
        self.server = runtime.server(env, server)
        self.labels = runtime.labels(env, "gpu")
        self.archive_root = archive_root or env.get("ARCHIVE", "/data/archive")
        self.step = self.STEP if step is None else float(step)
        self.lag = float(env.get("VISIBLE_LAG_SECONDS", "600"))   # how far behind the visible footage runs: a block's worth
        self.running: dict[str, object] = {}                # job -> model, kept between passes
        self.status_by_unit: dict[str, dict] = {}
        self.events_written = 0

    def job_row(self, job: str) -> dict | None:
        it, _ = self.vars.get(DETJOB.config("jobs", job))
        return DETJOB_SPEC.row(it) if it and it.get("deleted") != "true" else None

    # Whether the camera's own device holds any of `[t0, t1)`. The summary in the HOLDER's heartbeat —
    # `from`, `to`, `fragments` — never an index: the device's own archive is behind its door, and this is all a heartbeat carries
    # (М10B Lesson 15). Enough to tell "nobody recorded this" from "somebody did, just not us".
    def device_has(self, cam, t0: float, t1: float) -> bool:
        found = holder_of(self.objects, "vms/", str(cam), self.wall(), field="coverage")
        if found is None or not found[2].get("coverage"):
            return False
        cov = found[2]["coverage"]
        if not (float(cov["to"]) > t0 and float(cov["from"]) < t1):
            return False                                  # outside what the device holds at all
        # Inside the summary is not the same as "there is footage there". A device recording on motion has
        # mostly nothing between its first and last minute, and a job told `fetching` about minutes that do
        # not exist waits for a fetch that will never bring anything. So the index is asked — and when the
        # driver cannot list, the summary stands, because refusing work that would succeed is the worse
        # of the two mistakes.
        url = found[2].get("index_url")
        if not url:
            return True
        try:
            return covered_by(device_recordings(url, t0, t1), t0, t1) > 0
        except Exception:                                 # noqa: BLE001 — the holder is there and not answering
            return True

    # -- one stretch, decoded from its key frame and reported only inside the window -----------------------
    #
    # `ts` starts BEFORE the stretch, not where it does: the group of pictures holding 10:05 opens on a key frame
    # at 10:04:5x, and there is no other way into it. So the model sees those seconds, and `accepts` is what keeps
    # what it saw there out of the answer. How far back: a reader starts on the key frame before `t0`
    # (`Archive.samples`); this model has no frames, and reaches back `KEY_REACH` — no further than the footage.
    KEY_REACH = 60.0

    def _stretch(self, model, sc):
        ts = max(sc.seg.start, sc.t0 - self.KEY_REACH)
        while ts < sc.t1:
            for kind, fields in model.observe(ts):
                if sc.accepts(ts):
                    yield ts, kind, fields
            ts += self.step

    # -- the pass: advance every assigned job by at most a budget of stretches -------------------------
    def reconcile_once(self, now: float | None = None) -> list[str]:
        now = self.wall() if now is None else now
        wanted = set(self.assignment().units)
        for job in sorted(wanted):
            row = self.job_row(job)
            if row is None:
                continue
            if row["kind"] not in self.models:
                self.status_by_unit[job] = self._status(job, row, "unsupported")
                continue
            if row["state"] in TERMINAL:                    # the reaper has read this and not yet unplaced it
                self.status_by_unit[job] = self._status(job, row, row["state"])
                continue

            # What was recorded: the recording's spans, from the archive doors of the recorders holding its volumes.
            # Nobody answering is not "nothing recorded": the job waits, and says why. And SOME doors answering is not
            # the whole recording (the review's third pass): what answered is scanned, but the job is not `done`
            # while a door was silent or a volume unread — it waits for them, and says which (`missing`).
            read = recording_read(self.objects, row["rec"], row["from"], max(row["to"], now) + self.lag, self.wall(),
                                  vars_=self.vars)
            log_ = ScanLog(self.archive_root, job)
            if not read.answered:
                self._stop(job)
                self.status_by_unit[job] = self._status(job, row, "waiting", log=log_,
                                                        why="no recorder's archive door answered: what was recorded is not known")
                continue
            seen = read.spans
            missing = ([f"recorder {w}'s door did not answer" for w in read.silent]
                       + [f"nobody serves volume {v}" for v in read.unread])
            scans = plan(seen, row["from"], row["to"])
            # FOLLOWING: the interval runs past what is recorded, and the end may yet be written. A scenario
            # asking for the minute after the alarm asks for footage that does not exist when it asks.
            following = (written_through(seen) < row["to"]
                         and now < row["to"] + self.FOLLOW_LAGS * self.lag)
            if not scans and following and not (row["from"] < now and self.device_has(row["cam"], row["from"], min(row["to"], now))):
                self._stop(job)
                self.status_by_unit[job] = self._status(job, row, "following", log=log_,
                                                        why="the interval reaches past what is recorded — following the recording to its end")
                continue
            if not scans and missing:
                self._stop(job)
                self.status_by_unit[job] = self._status(job, row, "waiting", log=log_,
                                                        why="nothing recorded in the volumes that answered — " + "; ".join(missing))
                continue
            if not scans:
                # Not "no events": no FOOTAGE, here. Two different silences, and which one it is decides
                # what happens next — so the worker says which.
                #
                # If the DEVICE has those minutes (a card, an NVR — М10B Lesson 15), this is not a dead end
                # but a step: the footage exists, it is simply not ours yet. Asking the scan to read it
                # over the device's playback door would be wrong twice — that door admits two sessions per
                # device and they belong to the operator watching and to the recorder saving — so the job
                # says `fetching`, the console asks the recorder for the range (Lesson 16), and the scan
                # runs afterwards over footage we own, unchanged.
                self._stop(job)
                if self.device_has(row["cam"], row["from"], row["to"]):
                    self.status_by_unit[job] = self._status(job, row, "fetching",
                                                            why="the device has these minutes and we do not — asking the recorder")
                else:
                    self.status_by_unit[job] = self._status(job, row, "waiting",
                                                            why="nothing recorded in that interval, in any volume")
                continue

            left = remaining(scans, log_)
            if not left and following:
                # Everything recorded so far is behind it; the rest is being written. The model stays loaded —
                # the next block is minutes away, not a new job — and the row says nothing new.
                self.status_by_unit[job] = self._status(job, row, "following", scans=scans, log=log_,
                                                        why="the interval reaches past what is recorded — following the recording to its end")
                continue
            if not left and missing:
                self._stop(job)
                self.status_by_unit[job] = self._status(job, row, "waiting", scans=scans, log=log_,
                                                        why="what answered is scanned; not done — " + "; ".join(missing))
                continue
            if not left:
                self._stop(job)
                self.status_by_unit[job] = self._status(job, row, "done", scans=scans, log=log_)
                continue

            if job not in self.epochs:
                self.take_epoch(job)                        # one writer of detjob/<job>/… at a time
            model = self.running.get(job)
            if model is None:
                model = self.running[job] = self.models[row["kind"]](row)
            if self.may_write(job):
                for sc in left[:self.STRETCHES_PER_PASS]:
                    n = 0
                    for ts, kind, fields in self._stretch(model, sc):
                        EventLog(self.archive_root, DETJOB.name, job, self.epochs[job]).append(
                            ts, kind, cam=int(row["cam"]), job=job, source="archive", **fields)
                        n += 1
                    log_.append(sc, n, self.wall())         # the line AFTER the events: a crash costs one re-scan
                    self.events_written += n
            caught_up = following and not remaining(scans, log_)   # this pass took it to the edge of what is written
            self.status_by_unit[job] = self._status(job, row, "following" if caught_up else "running", scans=scans, log=log_,
                                                    **({"why": "the interval reaches past what is recorded — following "
                                                               "the recording to its end"} if caught_up else {}))

        for job in list(self.running):
            if job not in wanted:
                self._stop(job); self.release(job)
        for job in list(self.status_by_unit):
            if job not in wanted:
                self.status_by_unit.pop(job, None)
        return sorted(self.running)

    # What the console and the controller read. `done_through` and `covered` are here and not computed by
    # a reader, because the log they come from is a file on THIS server's disk and nobody else can see it.
    def _status(self, job: str, row: dict, phase: str, why: str = "", scans=None, log=None) -> dict:
        st = {"id": job, "cam": row["cam"], "rec": row["rec"], "kind": row["kind"], "phase": phase,
              "from": row["from"], "to": row["to"]}
        if why:
            st["why"] = why
        if log is not None:
            st["done_through"] = log.done_through()
            st["events"] = log.events()
        if scans is not None:
            st["covered"] = covered(scans)                  # seconds of the interval that footage exists for
            st["asked"] = max(0.0, row["to"] - row["from"])
        return st

    def _stop(self, job: str) -> None:
        m = self.running.pop(job, None)
        if m is not None:
            m.close()

    def headroom(self) -> int:
        return max(0, self.capacity - len(self.running))

    def heartbeat_once(self) -> None:
        self.heartbeat(list(self.status_by_unit.values()), server=self.server, instance=self.instance,
                       labels=",".join(self.labels), capacity=self.capacity, headroom=self.headroom(),
                       conflicts=self.conflicts(), events=self.events_written)

    def run(self, poll: float = 2.0, stop=None) -> None:
        import threading
        stop = stop or threading.Event()
        while not stop.is_set():
            try:
                self.reconcile_once()
            except Exception:                            # noqa: BLE001 — one bad pass, not a silent worker
                log.exception("scan pass failed")
            try:                                         # its own try, like the heartbeat's: the renewal used to be the last line of the pass, so a pass that raised half-way also let the leases run out (M19 of the review)
                self.renew_leases()
            except Exception:                            # noqa: BLE001
                log.exception("scan lease renewal failed")
            try:                                         # in a try of its own: the heartbeat says the worker is alive even when its pass is not (the review's second pass)
                self.heartbeat_once()
            except Exception:                            # noqa: BLE001
                log.exception("scan heartbeat failed")
            stop.wait(poll)
        for job in list(self.running):
            self._stop(job)
        self.release_slot()
