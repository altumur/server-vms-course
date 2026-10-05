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
from w2cplatform.worker import Worker
from w2cplatform.events import EventLog
from w2cplatform.variables import Variables

from .config import DETJOB_SPEC
from .detworker import FakeModel
from .scan import ScanLog, covered, covered_by, device_recordings, plan, recording_read, remaining, written_through
from w2cplatform.rows import PARSE_ERRORS

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

    SLOT_PREFIX = DETJOB_SPEC.slot_prefix                          # a slot it has to make is `j-<n>`, like the ones it is given

    # A job whose interval reaches past what is RECORDED follows the recording: the footage of its last
    # minutes is written while it runs. Done is when the footage has reached the end (`written_through`),
    # or — the recorder stopped, the camera went dark — when the end is older than this many LAGS: a reader sees a
    # block once it is written, and a block is written when it fills or `BLOCK_FLUSH_S` after its sequence was
    # finished, so the footage of `to` is at most one block's worth of time behind (`VISIBLE_LAG_SECONDS`: the block
    # size over the bitrate, for a stream that fills blocks faster than the flush period — the worst path from a
    # frame to an answer; feedback CP).
    FOLLOW_LAGS = 2

    # How long a scan WAITS for a silent door or a volume nobody serves before it ends without them (the review's
    # fourth pass). It used to wait for ever: one volume whose server never came back, and every scan of that recording
    # was `waiting` for good. Past this the job is `done` with `partial` naming what it did not read — said in its
    # status and, because the status goes with the placement, as a line `scan.partial` in the job's own events.
    WAIT_MAX = 3600.0

    def __init__(self, name: str | None, vars_: Variables, objects, models: dict | None = None,
                 capacity: int | None = None, clock=time.monotonic, wall=time.time, server: str | None = None,
                 resource_root: str | None = None, env: dict | None = None, step: float | None = None):
        env = dict(os.environ if env is None else env)
        super().__init__(DETJOB, None, vars_, objects, clock=clock, wall=wall)
        self.claim_slot(prefer=name if name is not None else runtime.slot(env, DETJOB_SPEC.slot_name_env, DETJOB_SPEC.slot_prefix))
        self.models = models if models is not None else {"motion": FakeModel, "linecross": FakeModel, "lpr": FakeModel}
        self.capacity = capacity if capacity is not None else int(env.get("SCAN_CAPACITY", "2"))
        self.server = runtime.server(env, server)
        self.labels = runtime.labels(env, "gpu")
        self.resource_root = runtime.events_root(env, resource_root)
        self.step = self.STEP if step is None else float(step)
        self.lag = float(env.get("VISIBLE_LAG_SECONDS", "600"))   # how far behind the visible footage runs: a block's worth
        self.wait_max = float(env.get("SCAN_WAIT_SECONDS", self.WAIT_MAX))
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
        found = holder_of(self.objects, "vms/", str(cam), self.wall(), field="coverage", eyes=self.eyes)   # fresh by change (the 13th pass)
        if found is None or not found[2].get("coverage"):
            return False
        cov = found[2]["coverage"] if isinstance(found[2]["coverage"], dict) else {}
        from w2cplatform.rows import number               # what one holder says it holds, through the one reader (the seventh pass)
        start, end = number(f"vms/status/{cam}#coverage.from", cov.get("from"), float, None), \
            number(f"vms/status/{cam}#coverage.to", cov.get("to"), float, None)
        if start is None or end is None or not (end > t0 and start < t1):
            return False                                  # outside what the device holds at all — or not said
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
            try:
                row = self.job_row(job)
                self.row_parsed(job)
            except PARSE_ERRORS as e:    # its row does not parse: this job's trouble (`row_garbled`)
                self.status_by_unit[job] = {"id": job, "phase": "failed", "why": self.row_garbled(job, e)}
                continue
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
                                  vars_=self.vars, eyes=self.eyes)   # the doors live by change (r29-writers2)
            log_ = ScanLog(self.resource_root, job)
            if not read.answered:
                self._stop(job)
                self.status_by_unit[job] = self._status(job, row, "waiting", log=log_,
                                                        why="no recorder's archive door answered: what was recorded is not known")
                continue
            seen = read.spans
            missing = ([f"recorder {w}'s door did not answer" for w in read.silent]
                       + [f"nobody serves volume {v}" for v in read.unread]
                       + [f"recorder {w}'s door answered stretches that cannot be read" for w in read.garbled])
            if not missing:
                log_.not_waiting()                          # the deadline is for one stretch of waiting, not for the job's life
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
                self.status_by_unit[job] = self._wait_or_end(job, row, log_, missing,
                                                             "nothing recorded in the volumes that answered — ")
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
                self.status_by_unit[job] = self._wait_or_end(job, row, log_, missing, "what answered is scanned; not done — ",
                                                             scans=scans)
                continue
            if not left:
                self._stop(job)
                self.status_by_unit[job] = self._status(job, row, "done", scans=scans, log=log_)
                continue

            model = self.running.get(job)
            if model is None and len(self.running) >= self.capacity:
                # The budget is of MODELS, not of jobs (the review's fourth pass): a job that waits holds none, so this
                # worker may carry more jobs than models (`heartbeat_once`) — and when the waiting ones can all run at
                # once, the ones past the budget queue here until a model is free.
                self.status_by_unit[job] = self._status(job, row, "queued", scans=scans, log=log_,
                                                        why=f"this worker's {self.capacity} scan(s) are all decoding: next when one ends")
                continue
            # Its epoch is this job's own trouble (the review's fifth pass; det and survey were mended in the fourth): a
            # garbled `detjob/epoch/<job>` raised out of the pass, and no job after this one moved — nor said why.
            if job not in self.epochs:
                why = self._take_epoch(job)                 # one writer of detjob/<job>/… at a time
                if why:
                    self._stop(job)
                    self.status_by_unit[job] = self._status(job, row, "failed", why=why, scans=scans, log=log_)
                    continue
            if model is None:
                model = self.running[job] = self.models[row["kind"]](row)
            if self.may_act(job):
                for sc in left[:self.STRETCHES_PER_PASS]:
                    n = 0
                    for ts, kind, fields in self._stretch(model, sc):
                        EventLog(self.resource_root, DETJOB.name, job, self.epochs[job], of=DETJOB_SPEC.of_row(row)).append(
                            ts, kind, cam=_cam(row["cam"]), job=job, source="archive", **fields)
                        n += 1
                    log_.append(sc, n, self.wall())         # the line AFTER the events: a crash costs one re-scan
                    self.events_written += n
            caught_up = following and not remaining(scans, log_)   # this pass took it to the edge of what is written
            self.status_by_unit[job] = self._status(job, row, "following" if caught_up else "running", scans=scans, log=log_,
                                                    **({"why": "the interval reaches past what is recorded — following "
                                                               "the recording to its end"} if caught_up else {}))

        for job in set(self.running) | set(self.epochs):   # an epoch with no model too: a finished job, or a partial one's line
            if job not in wanted:
                self._stop(job); self.release(job)
        for job in list(self.status_by_unit):
            if job not in wanted:
                self.status_by_unit.pop(job, None)
        return sorted(self.running)

    # Waiting for what is missing — until `wait_max` after it began, then `done` with `partial`. The line `scan.partial`
    # is written once, at the interval's start in media time (where `/events?unit=vms/<cam>` finds the scan's answer), and the
    # end is remembered beside the progress, so the next pass before the reaper does not write it again.
    def _wait_or_end(self, job: str, row: dict, log_: ScanLog, missing: list[str], why: str, scans=None) -> dict:
        waited = log_.waiting() or log_.wait(self.wall())
        partial = waited.get("partial")
        if partial is None and self.wall() - waited["since"] >= self.wait_max:
            why_not = self._take_epoch(job) if job not in self.epochs else ""
            if why_not:
                return self._status(job, row, "failed", scans=scans, log=log_, why=why_not)
            if not self.may_act(job):
                return self._status(job, row, "waiting", scans=scans, log=log_, why=why + "; ".join(missing))
            EventLog(self.resource_root, DETJOB.name, job, self.epochs[job], of=DETJOB_SPEC.of_row(row)).append(
                float(row["from"]), "scan.partial", cam=_cam(row["cam"]), job=job, source="archive", missing=list(missing),
                waited=round(self.wall() - waited["since"]))
            partial = log_.wait(self.wall(), partial=missing)["partial"]
            log.warning("scan %s: done without %s — waited %.0f s", job, "; ".join(missing), self.wall() - waited["since"])
        if partial is not None:
            return self._status(job, row, "done", scans=scans, log=log_, partial=partial,
                                why=f"done without what it waited {self.wait_max:.0f} s for — " + "; ".join(partial))
        left = self.wait_max - (self.wall() - waited["since"])
        return self._status(job, row, "waiting", scans=scans, log=log_,
                            why=why + "; ".join(missing) + f" (ends without them in {max(0.0, left):.0f} s)")

    # `take_epoch`, as one job's trouble: "" when it holds one, else why not — said in the job's status and the log.
    def _take_epoch(self, job: str) -> str:
        try:
            self.take_epoch(job)
        except Exception as e:                              # noqa: BLE001 — a garbled row, a store that did not answer
            log.error("scan %s: its epoch was not taken: %s", job, e)
            return f"its epoch could not be taken: {e}"
        return ""

    # What the console and the controller read. `done_through` and `covered` are here and not computed by
    # a reader, because the log they come from is a file on THIS server's disk and nobody else can see it.
    def _status(self, job: str, row: dict, phase: str, why: str = "", scans=None, log=None, partial=None) -> dict:
        st = {"id": job, "cam": row["cam"], "rec": row["rec"], "kind": row["kind"], "phase": phase,
              "from": row["from"], "to": row["to"]}
        if why:
            st["why"] = why
        if partial:
            st["partial"] = list(partial)
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

    # `capacity` is the jobs this worker will HOLD: its budget of models, plus every job it holds that has none — one that
    # waits, follows with nothing to decode, or queues (the review's fourth pass). The controller places by `capacity −
    # assigned`, so it sees exactly the models that are free; two jobs waiting for a volume that never comes back used
    # to fill a GPU worker of two, and every new scan was unplaceable behind them.
    def heartbeat_once(self) -> None:
        idle = sum(1 for job in self.status_by_unit if job not in self.running)
        self.heartbeat(list(self.status_by_unit.values()), server=self.server, instance=self.instance,
                       labels=",".join(self.labels), capacity=self.capacity + idle, headroom=self.headroom(),
                       conflicts=self.conflicts(), events=self.events_written)

    # The loop is the platform's (`Worker.run`: the pass, the lease step, the heartbeat, each in a try of its own, the
    # stand-in for a step that hangs, an orderly stop); what it stops is its scans.
    def stop_unit(self, unit) -> None:
        self._stop(unit)

    def stop_all_units(self) -> None:
        for unit in list(self.running):
            self._stop(unit)


# The camera an event carries: its number when it is one, else as written — `ref:<serial>`, a camera of another cluster
# (the review's seventh pass: `int(row["cam"])` raised on it, out of the job's pass, and every job after it waited).
def _cam(cam):
    from w2cplatform.doors import numeric                    # not `isdigit` + `int`: `7²` raised the same way (the ninth pass)
    n = numeric(cam)
    return str(cam) if n is None else n
