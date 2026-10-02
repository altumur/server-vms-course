"""The detector worker — the second subsystem's worker. A unit is one model on
one camera (`7-linecross`); the worker subscribes to the camera's RTSP fan-out
the way the gateway does (`live_url` from the VMS worker's heartbeat, never by
calling it), decodes, runs the model, and writes what the model saw into the
unit's bucket on the resource — `det/<unit>/e<epoch>/…events.jsonl`, under
the epoch it holds, so a stale instance's events are identifiable like a
stale writer's buckets. Capacity is streams a GPU can carry; labels say
where it may run. The model is a `Model` — `FakeModel` here (fires on a
schedule, so the events and their buckets can be tested), a decode-and-infer
pipeline on a box.

    det/units/<name>        the unit: cam, kind, params, enabled — written by the console with the operator's token
    det/workers/<d>         the assignment, written by the det controller (SpecController from det.subsystem.yaml)
    det/<d>/heartbeat       capacity, headroom, labels, url-less; per-unit status: phase, events written
"""
from __future__ import annotations

import logging
import os
import time

from w2cplatform import runtime
from w2cplatform.console import holder_of
from w2cplatform.contract import Worker
from w2cplatform.events import ALARM, OBSERVATION, EventLog, Suppressor
from w2cplatform.variables import Variables

from .config import DET_SPEC

DET = DET_SPEC.sub
log = logging.getLogger("vms.detworker")


# A model: `observe(now) -> [ (kind, fields) ]` per pass; `close()`. The fake fires one event every `every`th
# pass, with the pass number, so a test can count buckets and lines.
class FakeModel:
    def __init__(self, unit: dict, every: int = 3):
        self.unit, self.every, self.passes = unit, every, 0

    def observe(self, now: float) -> list[tuple[str, dict]]:
        self.passes += 1
        return [(self.unit["kind"], {"pass": self.passes, "cam": int(self.unit["cam"])})] if self.passes % self.every == 0 else []

    def close(self) -> None:
        pass


class DetWorker(Worker):
    """`name` is a slot (`d-1`); `models` maps a kind to a factory `(unit) -> Model`; unknown kinds are
    reported as `phase: unsupported` and run nothing."""

    SLOT_PREFIX = "d"                            # a slot it has to make is `d-<n>`, like the ones it is given

    def __init__(self, name: str | None, vars_: Variables, objects, models: dict | None = None, capacity: int | None = None,
                 clock=time.monotonic, wall=time.time, server: str | None = None, archive_root: str | None = None,
                 env: dict | None = None):
        env = dict(os.environ if env is None else env)
        super().__init__(DET, None, vars_, objects, clock=clock, wall=wall)
        self.claim_slot(prefer=name if name is not None else runtime.slot(env, "DET_NAME", "d"))
        self.models = models if models is not None else {"motion": FakeModel, "linecross": FakeModel, "lpr": FakeModel}
        self.capacity = capacity if capacity is not None else int(env.get("CAPACITY", "8"))
        self.server = runtime.server(env, server)
        self.labels = runtime.labels(env, "gpu")
        self.archive_root = archive_root or env.get("ARCHIVE", "/data/archive")   # this server's resource: where the buckets go
        self.running: dict[str, object] = {}                                     # unit -> model
        self.status_by_unit: dict[str, dict] = {}
        self.events_written = 0
        # What this subsystem declared about repeats (`events.suppress` in det.subsystem.yaml), held for as
        # long as this worker runs the model — the VMS worker's arrangement, for its reason: the model's
        # output is seen here before it is a file, and nowhere else (M12 of the review).
        self.suppressor = Suppressor(DET_SPEC.suppress)

    # -- where the camera's RTP is: the VMS heartbeat, never a call to the worker ---------------------
    def rtp_source(self, cam: str):
        """`(server, live_url)` of the worker holding the camera — its RTSP fan-out, on any server."""
        found = holder_of(self.objects, "vms/", cam, self.wall(), phase="running", field="live_url")
        if found is None:
            return None
        from .config import local_only
        server, url = found[1].extra.get("server", "?"), found[2]["live_url"]
        return None if local_only(url, server, self.server) else (server, url)   # loopback on another server: not for us

    def unit_row(self, unit: str) -> dict | None:
        it, _ = self.vars.get(DET.config("units", unit))
        return DET_SPEC.row(it) if it and it.get("deleted") != "true" else None

    # -- the reconcile pass: running models equal the assignment's enabled, reachable units ------------------
    def reconcile_once(self, now: float | None = None) -> list[str]:
        now = self.wall() if now is None else now
        wanted = set(self.assignment().units)
        for unit in wanted:
            row = self.unit_row(unit)
            if row is None:
                continue
            if not row["enabled"]:
                self._stop(unit); self.status_by_unit[unit] = {"id": unit, "cam": row["cam"], "kind": row["kind"], "phase": "pending"}; continue
            if row["kind"] not in self.models:
                self.status_by_unit[unit] = {"id": unit, "cam": row["cam"], "kind": row["kind"], "phase": "unsupported"}; continue
            src = self.rtp_source(row["cam"])
            if src is None:
                self._stop(unit); self.status_by_unit[unit] = {"id": unit, "cam": row["cam"], "kind": row["kind"], "phase": "waiting", "why": "camera held by nobody"}; continue
            if unit not in self.epochs:
                self.take_epoch(unit)                                           # one writer of det/<unit>/… at a time
            # THE MODEL IS THE UNIT'S OWN TROUBLE (the review's third pass, M19's remainder). Its factory — a weights
            # file missing, a mask that does not decode — and its `observe` raised out of the pass, and every unit
            # after this one in the loop was not looked at, every pass. Now the unit says `failed` and why, its model is
            # dropped so the next pass builds it afresh, and the others are served.
            try:
                if unit not in self.running:
                    self.running[unit] = self.models[row["kind"]](row)
                    self.status_by_unit[unit] = {"id": unit, "cam": row["cam"], "kind": row["kind"], "phase": "running", "events": 0, "server": src[0], "source": src[1]}
                if self.may_write(unit):
                    for kind, fields in self.running[unit].observe(now):       # what the model saw, into the unit's bucket under its epoch
                        # Suppression stands between the model and the file, last before the write, as in the
                        # VMS worker: everything above is about whether this worker may speak about this unit
                        # at all, and that does not change because the scene moved twice.
                        self._write(unit, row, self.suppressor.lines(now, unit, kind, fields))
            except Exception as e:                                              # noqa: BLE001
                log.exception("detector %s failed this pass", unit)
                self._stop(unit)
                self.status_by_unit[unit] = {"id": unit, "cam": row["cam"], "kind": row["kind"], "phase": "failed",
                                             "why": f"the model failed: {e}"}
        self._flush_suppressed(now)
        for unit in list(self.running):
            if unit not in wanted:
                self._stop(unit); self.status_by_unit.pop(unit, None); self.release(unit)
        for unit in list(self.status_by_unit):
            if unit not in wanted:
                self.status_by_unit.pop(unit, None)
        return sorted(self.running)

    # The traffic class of one line: `alarm` when this DETECTOR's row lists the kind among its alarms, else
    # `observation` (det.subsystem.yaml, `alarms`). The platform fixes the two words; which kinds are which is on
    # the row, because it is about what the operator set the model up for.
    @staticmethod
    def class_of(row: dict, kind: str) -> str:
        names = [str(n).strip() for n in (row.get("alarms") or []) if str(n).strip()]
        return ALARM if kind in names else OBSERVATION

    # Writes the lines the suppressor handed back — the observation, nothing, or the summary of a window that
    # just closed and then the observation — each under its class, into the unit's bucket under its epoch.
    def _write(self, unit: str, row: dict, lines) -> None:
        log_ = EventLog(self.archive_root, DET.name, unit, self.epochs[unit])
        for t, kind, fields in lines:
            log_.append(t, kind, self.class_of(row, kind), **fields)
            self.status_by_unit[unit]["events"] = self.status_by_unit[unit].get("events", 0) + 1; self.events_written += 1

    # Windows that closed with no observation left to carry the summary out: the scene went still. Once a pass,
    # as the VMS worker does — without it a storm that ENDS is a storm nobody counted. A unit whose epoch this
    # worker gave up drops its summary rather than writing it under an epoch that is not its own any more.
    def _flush_suppressed(self, now: float) -> None:
        for unit, t, kind, fields in self.suppressor.flush(now):
            row = self.unit_row(unit) if unit in self.epochs and unit in self.status_by_unit else None
            if row is not None and self.may_write(unit):
                self._write(unit, row, [(t, kind, fields)])

    def _stop(self, unit: str) -> None:
        m = self.running.pop(unit, None)
        if m is not None:
            m.close()

    def headroom(self) -> int:
        return max(0, self.capacity - len(self.running))

    def heartbeat_once(self) -> None:
        self.heartbeat(list(self.status_by_unit.values()), server=self.server, instance=self.instance, labels=",".join(self.labels),
                       capacity=self.capacity, headroom=self.headroom(), conflicts=self.conflicts(), events=self.events_written)

    def run(self, poll: float = 2.0, stop=None) -> None:
        import threading
        stop = stop or threading.Event()
        while not stop.is_set():
            try:
                self.reconcile_once()
            except Exception:                            # noqa: BLE001 — one bad pass, not a silent worker
                log.exception("detector pass failed")
            try:                                         # its own try, like the heartbeat's: the renewal used to be the last line of the pass, so a pass that raised half-way also let the leases run out (M19 of the review)
                self.renew_leases()
            except Exception:                            # noqa: BLE001
                log.exception("detector lease renewal failed")
            try:                                         # in a try of its own: the heartbeat says the worker is alive even when its pass is not (the review's second pass)
                self.heartbeat_once()
            except Exception:                            # noqa: BLE001
                log.exception("detector heartbeat failed")
            stop.wait(poll)
        for unit in list(self.running):
            self._stop(unit)
        self.release_slot()
