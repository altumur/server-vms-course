"""A recording of a camera that pushes (М12B, урок 3; М12 Lesson 16) — the recorder's half of the ingest.

A camera nobody can dial pushes its stream to the ingest of the cluster that records it. Its recording there names it
`cam: ref:<serial>`, and the recorder finds its source where it finds any camera of another cluster — in this cluster's
copy of the source book (`RecWorker.source`, `crossing.resolve_in`) — which says `ingest://<cluster>/<ref>`. There is no
pipeline to build for such a source: nothing to open, nothing to dial. The recording SUBSCRIBES to the ingest its
recorder hosts (`RecWorker.host_ingest`) and writes what comes, through the same sink a pipeline writes through
(`RecSink`: this volume's writer, as the stream `<recording>/e<epoch>`). As the product's `recact/ingestrec.go`:

    the want      subscribing is wanting the stream for ever (`Ingest.want`): it is what makes the camera push. A recording
                  that stops lets go of both at once (`Ingest.unsubscribe`), and the camera stops when nobody else wants it
    who writes    still this recorder, under its epoch. A start is a new epoch and a new stream, as for any pipeline
    have          each frame the writer TOOK moves the recording's `written_through` (`RecWorker.note_written`), on this
                  cluster's clock. The heartbeat says it; the ingest reads it there (`written_from_heartbeats`) and tells
                  the camera `have` in every poll answer — after a break the camera continues from it, out of its ring
    key frames    a recording begins at a key frame, and after a frame the engine refused it skips to the next one
    nothing yet   a recording that has had not a frame `START_GRACE` after its start is said `waiting` with why
                  (`push_waiting`): "running" would tell the domain's book of primaries — and the camera's card — that the
                  camera is recorded. A `when: offline` standby is quiet while its primary takes the stream: not waiting
    dead          a recording that had frames and then nothing for `WATCHDOG` is dead, as a pipeline whose watchdog fired:
                  `pump` says so, and the recorder starts it again after its backoff, under a new epoch

The course has no goroutine per recording: what arrived is written on every pass the recorder makes — its reconcile, its
bus (`pump`) and its heartbeat (`RecWorker.take_pushed`), so the heartbeat never says less than was written.

The actuator underneath — a GStreamer one on a box, `FakeActuator` in the tests — keeps every other source, and every
verb this one has nothing to do with is its own (`__getattr__`).
"""
from __future__ import annotations

import dataclasses
import logging

from vms.obsd import ObsdError, Sample, unix_s

log = logging.getLogger("recworker")

INGEST_SCHEME = "ingest://"                 # a source that is pushed rather than pulled: `ingest://<cluster>/<ref>`


def ingest_ref(source) -> str | None:
    """The camera an `ingest://<cluster>/<ref>` source names; None for any other (the product's `vms.IngestRef`)."""
    s = str(source or "")
    if not s.startswith(INGEST_SCHEME):
        return None
    _, _, ref = s[len(INGEST_SCHEME):].partition("/")
    return ref or None


@dataclasses.dataclass
class _Pushed:
    cid: object
    ref: str
    who: str
    sink: object
    queue: object
    started: float
    when: str = ""
    last: float | None = None                   # when, on the recorder's clock, the writer last took a frame
    need_key: bool = True
    written: int = 0
    dropped: int = 0
    why: str = ""


class IngestRecordings:
    """The recorder's actuator with its recordings of cameras that push (`ingest://`). `inner`: the actuator for every
    other source; `rec`: the recorder (its ingest, its clock, `note_written`)."""

    START_GRACE = 20.0                          # the product's `ingestStartGrace`: a poll, and the first key frame
    WATCHDOG = 8.0                              # the product's `WatchdogMs`: no frame this long after frames — dead
    QUEUE = 1024                                # the product's channel: frames waiting for the writer

    def __init__(self, inner, rec):
        self.inner, self.rec = inner, rec
        self.pushed: dict[str, _Pushed] = {}
        self._dead: list = []

    def __getattr__(self, name):
        if name == "inner":
            raise AttributeError(name)
        return getattr(self.inner, name)

    def __call__(self, verb: str, cam: dict) -> bool:
        cid = cam["id"]
        if verb == "stop":
            return True if self._stop(cid, "stop") else self.inner(verb, cam)
        if verb in ("start", "restart"):
            ref = ingest_ref(cam.get("source"))
            if ref is not None:
                return self._start(cam, ref)
            self._stop(cid, "restart")                       # a pushed camera now pulled (the book changed its road)
        if verb == "release" and str(cid) in self.pushed:
            return False                                     # no ring held: what the camera brings is written as it comes
        return self.inner(verb, cam)

    def _start(self, cam: dict, ref: str) -> bool:
        ing = getattr(self.rec, "ingest", None)
        if ing is None:                                      # `enrich` says it before a start; a start here is a bug
            log.error("%s: recording %s: camera %s pushes to this cluster's ingest, and this recorder hosts none",
                      self.rec.name, cam["id"], ref)
            return False
        cid = cam["id"]
        self._stop(cid, "restart")
        who = f"recorder:{self.rec.name}/{cid}"              # one subscription per recording: `Ingest.taken` reads `recorder`
        ing.want(ref, who)
        q = ing.subscribe(ref, who, maxsize=self.QUEUE)
        self.pushed[str(cid)] = _Pushed(cid, ref, who, cam.get("sink"), q, self.rec.wall(), str(cam.get("when") or ""))
        log.info("%s: recording %s from the ingest (camera %s, stream %s/e%s)", self.rec.name, cid, ref, cid,
                 cam.get("epoch", 0))
        return True

    def _stop(self, cid, why: str) -> bool:
        p = self.pushed.pop(str(cid), None)
        if p is None:
            return False
        self._write(p, p.queue.drain())                      # what came before the stop is written first
        if p.sink is not None:
            p.sink.finish()                                  # the open sequence closed
        ing = getattr(self.rec, "ingest", None)
        if ing is not None:
            ing.unsubscribe(p.ref, p.who)
        log.info("%s: recording %s from the ingest stopped (%s): %d frames written", self.rec.name, cid, why, p.written)
        return True

    # -- the writer ---------------------------------------------------------------------------------------------------
    def take(self) -> int:
        """What arrived for every recording, written: frames taken this time."""
        n = 0
        for p in list(self.pushed.values()):
            n += self._write(p, p.queue.drain())
        return n

    def _write(self, p: _Pushed, frames: list) -> int:
        took = 0
        for f in frames:
            smp = f.get("sample") if isinstance(f, dict) else f
            if not isinstance(smp, Sample) or p.sink is None:
                p.dropped += 1                               # no record to write — a model frame of a test of the ingest
                continue
            if p.need_key and not smp.key:
                p.dropped += 1                               # a sequence begins at a key frame
                continue
            try:
                p.sink.put(smp)
            except ObsdError as e:
                p.need_key, p.why = True, f"the engine refused a frame: {e.name}"
                p.dropped += 1
                continue
            p.need_key, p.why = False, ""
            p.written += 1
            took += 1
            p.last = self.rec.wall()
            self.rec._offered_extra += len(smp.body)        # written by this process itself: offered too (the writer watch)
            t = float(f["t"]) if isinstance(f, dict) and "t" in f else unix_s(smp.begin)
            self.rec.note_written(p.cid, t)                  # on this cluster's clock: the camera's `have`
        return took

    # -- what each says -----------------------------------------------------------------------------------------------
    def waiting(self, cid) -> str | None:
        """Why a running recording of a pushed camera is not recording now — nothing since its start, past the grace —
        or None. A standby (`when: offline`) is quiet while its primary takes the stream: never waiting."""
        p = self.pushed.get(str(cid))
        if p is None or p.when == "offline" or p.last is not None:
            return None
        quiet = self.rec.wall() - p.started
        if quiet <= self.START_GRACE:
            return None
        return f"the camera has pushed nothing since the recording began, {quiet:.0f} s ago"

    def stats(self, cid) -> dict | None:
        p = self.pushed.get(str(cid))
        if p is None:
            return None
        out = {"via": "ingest", "samples_written": p.written, "samples_dropped": p.dropped}
        if p.why:
            out["last_error"] = p.why
        why = self.waiting(cid)
        if why:
            out.update(push_waiting=True, why=why)
        return out

    # -- the bus, and the loop's other verbs ---------------------------------------------------------------------------
    def pump(self):
        self.take()
        now = self.rec.wall()
        for key, p in list(self.pushed.items()):
            if p.when != "offline" and p.last is not None and now - p.last > self.WATCHDOG:
                log.warning("%s: recording %s: nothing from camera %s for %.0f s — the pushed stream stopped",
                            self.rec.name, p.cid, p.ref, now - p.last)
                self._stop(p.cid, "dead")
                self._dead.append(p.cid)
        dead, posted = self.inner.pump()
        mine, self._dead = self._dead, []
        return list(dead) + mine, posted

    def stop_all(self) -> None:
        for p in list(self.pushed.values()):
            self._stop(p.cid, "stop")
        self.inner.stop_all()

    def offered(self, cid):
        if str(cid) in self.pushed:
            return None                                      # counted as written (`_offered_extra`), not as a pipeline's
        fn = getattr(self.inner, "offered", None)
        return fn(cid) if fn is not None else None
