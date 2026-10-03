"""What a pass READS, counted (the scaling pass after the eighth review).

A controller pass and the console's loops re-read whole prefixes of the store on a short period. Nothing breaks
when they read too much — the pass just takes longer, and every number about delays built on "a pass every five
seconds" stops being true (`_notes-ru/three-cameras/10-limits-and-scale.md`). So the reads are COUNTED here, on
a thousand rows, through a proxy over the store (`Reads`), and the number is pinned as a ceiling — not as an exact
count, which would break on every honest change — and the result of the pass is compared with the same pass
made without the per-pass reads (`one_pass`), on the same store.

The cluster is built straight into an in-memory store (`cluster`): N cameras, each with its recording on the
recorder of its camera's server, every one placed and at home, every worker heartbeating — the idle pass, which
is the pass that runs every five seconds for ever.
"""
from __future__ import annotations

import json
from contextlib import contextmanager

from w2cplatform.contract import Slot
from w2cplatform.memvariables import MemVariables

NOW = 1_757_500_000.0


class MemObjects:
    """An object store in a dict: a thousand heartbeats and rows without a disk."""
    def __init__(self): self.d = {}
    def put(self, key, data): self.d[key] = bytes(data)
    def get(self, key): return self.d.get(key)
    def list(self, prefix): return sorted(k for k in self.d if k.startswith(prefix))
    def delete(self, key): return self.d.pop(key, None) is not None


class Reads:
    """A store, counting what it is asked to read: `get` and `list` — the two calls a Nomad Variables or an S3
    read costs one request each (the product's `testbox.Reads`)."""
    def __init__(self, inner): self.inner, self.gets, self.lists = inner, 0, 0

    def get(self, key):
        self.gets += 1
        return self.inner.get(key)

    def list(self, prefix, *a, **kw):
        self.lists += 1
        return self.inner.list(prefix, *a, **kw)

    def __getattr__(self, name): return getattr(self.inner, name)

    @property
    def n(self) -> int: return self.gets + self.lists

    def zero(self): self.gets = self.lists = 0


def _heartbeat(objects, sub: str, worker: str, status: list, **extra) -> None:
    objects.put(f"{sub}/heartbeats/{worker}", json.dumps({"worker": worker, "ts": NOW, "status": status, **extra}).encode())


def _place(vars_, sub: str, uid: str, worker: str) -> None:
    vars_.put(f"{sub}/placement/{uid}", {"worker": worker, "reason": "placed by the builder", "at": NOW, "rev": 1})


def cluster(n: int = 1000, workers: int = 20, servers: int = 4, recording: bool = True):
    """`(vars, objects)`: n cameras on `workers` workers over `servers` servers, each server with a resource and —
    with `recording` — one recorder on its own volume holding the recordings of that server's cameras. Placed, at
    home, heartbeating: a pass over it should change nothing."""
    from vms.config import REC_SPEC, SPEC
    vars_, objects = MemVariables(), MemObjects()
    for s in range(servers):
        objects.put(f"platform/resources/srv-{s}/heartbeat",
                    json.dumps({"server": f"srv-{s}", "ts": NOW, "url": f"http://srv-{s}:8090", "mirrors": {}}).encode())
    names = [f"w-{k + 1}" for k in range(workers)]
    server_of = {w: f"srv-{k % servers}" for k, w in enumerate(names)}
    units: dict[str, list[str]] = {w: [] for w in names}
    status: dict[str, list] = {w: [] for w in names}
    for i in range(1, n + 1):
        w = names[i % workers]
        row = SPEC.new_row(i, {"name": f"cam{i}", "source": f"driverpack://file/cam{i}.mp4"})
        vars_.put(SPEC.sub.config(SPEC.rows, str(i)), SPEC.items(row))
        _place(vars_, "vms", str(i), w)
        units[w].append(str(i))
        status[w].append({"id": str(i), "phase": "running", "epoch": 1})
    cap = 2 * n // workers + 1
    for w in names:
        vars_.put(f"vms/workers/{w}", {"units": ",".join(sorted(units[w])), "rev": 1})
        vars_.put(f"vms/slots/{w}", Slot(w, f"inst-{w}", NOW + 30, False, 1).to_items())
        _heartbeat(objects, "vms", w, status[w], server=server_of[w], capacity=cap, headroom=cap - len(units[w]), labels="")
    if recording:
        rec_units: dict[str, list[str]] = {}
        rec_status: dict[str, list] = {}
        for i in range(1, n + 1):
            s = int(server_of[names[i % workers]][4:])
            r = f"r-{s + 1}"
            row = REC_SPEC.new_row(str(i), {"name": str(i), "cam": str(i), "home": f"vol-{s}"})
            vars_.put(REC_SPEC.sub.config(REC_SPEC.rows, str(i)), REC_SPEC.items(row))
            _place(vars_, "rec", str(i), r)
            rec_units.setdefault(r, []).append(str(i))
            rec_status.setdefault(r, []).append({"id": str(i), "cam": str(i), "phase": "running", "epoch": 1})
        for s in range(servers):
            r = f"r-{s + 1}"
            vars_.put(f"rec/workers/{r}", {"units": ",".join(sorted(rec_units.get(r, []))), "rev": 1})
            vars_.put(f"rec/slots/{r}", Slot(r, f"inst-{r}", NOW + 30, False, 1).to_items())
            _heartbeat(objects, "rec", r, rec_status.get(r, []), server=f"srv-{s}", volume=f"vol-{s}",
                       capacity=n, headroom=n, labels="")
    return vars_, objects


def wall():
    return NOW


def console_store(n: int = 1000, jobs_workers: int = 4, spans: int = 10):
    """`cluster(n)` plus what the console's loops walk: a detector per camera, n scan jobs (a third finished), n
    backfills a person asked for in `rec/requests/`, and the heartbeats that say what was closed and hit."""
    from vms.config import DET_SPEC, DETJOB_SPEC
    vars_, objects = cluster(n)
    for i in range(1, n + 1):
        name = f"{i}-motion"
        vars_.put(DET_SPEC.sub.config(DET_SPEC.rows, name),
                  DET_SPEC.items(DET_SPEC.new_row(name, {"name": name, "cam": str(i), "kind": "motion"})))
        vars_.put(f"rec/requests/{i}-{int(NOW) - 7200}-{int(NOW) - 3600}",
                  {"unit": str(i), "cam": str(i), "from": str(NOW - 7200), "to": str(NOW - 3600), "at": str(NOW - 60),
                   "by": "op"})
    status: dict[str, list] = {}
    for i in range(1, n + 1):
        jid, w = f"{i}-motion-{int(NOW) - 600}-{int(NOW) - 300}", f"j-{i % jobs_workers + 1}"
        done = i % 3 == 0
        row = DETJOB_SPEC.new_row(jid, {"name": jid, "cam": str(i), "rec": str(i), "kind": "motion", "from": NOW - 600,
                                        "to": NOW - 300, **({"state": "done", "ended": NOW - 3600} if done else {})})
        vars_.put(DETJOB_SPEC.sub.config(DETJOB_SPEC.rows, jid), DETJOB_SPEC.items(row))
        if not done:
            _place(vars_, "detjob", jid, w)
            status.setdefault(w, []).append({"id": jid, "phase": "running", "rec": str(i), "cam": str(i),
                                             "from": NOW - 600, "to": NOW - 300})
    for k in range(jobs_workers):
        _heartbeat(objects, "detjob", f"j-{k + 1}", status.get(f"j-{k + 1}", []), server=f"srv-{k % 4}", capacity=n,
                   labels="gpu")
    for key in objects.list("rec/heartbeats/"):              # what the recorders closed: footage arrived from a device
        hb = json.loads(objects.get(key))
        hb["closed"] = ",".join(f"{s['id']}|{NOW - 900:.0f}|{NOW - 840:.0f}" for s in hb["status"][:spans])
        objects.put(key, json.dumps(hb).encode())
    _heartbeat(objects, "survey", "s-1", [], server="srv-0",
               hits=",".join(f"{i}|{NOW - 500:.0f}|{NOW - 480:.0f}" for i in range(1, spans + 1)))
    return vars_, objects


def file_requests(vars_, turn: int, k: int = 10) -> None:
    """What automation files between two turns of the console's request loop: k recordings and k scans asked for."""
    for j in range(k):
        cam = str(turn * k + j + 1)
        vars_.put(f"rec/requests/f{turn}-{j}-0", {"unit": cam, "cam": cam, "action": "record", "minutes": "10",
                                                  "at": str(NOW), "by": "auto/x", "valid_until": str(NOW + 30)})
        vars_.put(f"det/requests/f{turn}-{j}-1", {"cam": cam, "kind": "motion", "action": "scan", "at": str(NOW),
                                                  "by": "auto/x", "valid_until": str(NOW + 30)})


# -- the old and the new on one scenario -------------------------------------------------------------------------------

@contextmanager
def without_pass_reads():
    """The same code with `one_pass` doing nothing: every read goes to the store, as before the scaling pass."""
    import sys
    contract, spec = sys.modules["w2cplatform.contract"], sys.modules["w2cplatform.spec"]   # the modules in use: an
    # `import a.b` reads the package's attribute, which a test that re-imports modules may have left pointing elsewhere

    @contextmanager
    def nothing(*_):
        yield
    saved = contract.one_pass, spec.one_pass
    contract.one_pass = spec.one_pass = nothing
    try:
        yield
    finally:
        contract.one_pass, spec.one_pass = saved


def rows(vars_) -> dict:
    """Every row of the store, without the indexes: what a pass decided."""
    return {k: vars_.get(k)[0] for k in vars_.list("")}


def objects_but_the_report(objects) -> dict:
    return {k: v for k, v in objects.d.items() if not k.endswith("/controller/pass")}


def _vms(vars_, objects):
    from vms.controller import VmsController
    return VmsController(vars_, objects, wall=wall)


def _rec(vars_, objects):
    from vms.config import REC_SPEC
    from w2cplatform.spec import SpecController
    return SpecController(REC_SPEC, vars_, objects, wall=wall)


def _loop_pass(ctl) -> None:
    """One turn of the controller's loop: the pass and the snapshot, in one pass of reads (`_controller_loop`)."""
    with ctl.one_pass():
        ctl.pass_once(1)
        ctl.publish_snapshot()


# -- the controller ----------------------------------------------------------------------------------------------------

def test_an_idle_controller_pass_over_a_thousand_cameras_reads_each_row_once():
    """The idle pass at N = 1000 cameras on 20 workers, four servers, a recording per camera. Before: 41 157 reads for
    `pass_once` and 23 002 more for the snapshot (the snapshot re-read every heartbeat per camera, `ensure_home` every
    recorder's) — 64 159 every five seconds. Now each row, placement and heartbeat once: ~2 N for the pass, and the
    snapshot in the same pass reads nothing again. The recordings' controller likewise: 25 164 before. And an idle pass
    still changes no row."""
    n = 1000
    for make, label in ((_vms, "vms"), (_rec, "rec")):
        vars_, objects = cluster(n)
        before = rows(vars_)
        v, o = Reads(vars_), Reads(objects)
        ctl = make(v, o)
        v.zero(), o.zero()
        with ctl.one_pass():
            rep = ctl.pass_once(1)
            pass_reads = v.n + o.n
            ctl.publish_snapshot()
        snap_reads = v.n + o.n - pass_reads
        assert rep["ok"], rep
        assert pass_reads <= 2 * n + 150, (label, pass_reads)
        assert snap_reads <= 60, (label, snap_reads)
        assert rows(vars_) == before, label                  # idle: nothing placed, moved or brought home
        v.zero(), o.zero()
        ctl.publish_snapshot()                               # alone, as a console may ask for it: once per key too
        assert v.n + o.n <= 2 * n + 60, (label, v.n + o.n)


def _busy(vars_) -> None:
    """A pass with work in it: twenty cameras lost their placement, ten new ones, one deleted, a slot released (scale-in),
    one camera on the wrong server (its recording is elsewhere)."""
    from vms.config import SPEC
    for i in range(1, 21):
        vars_.delete(f"vms/placement/{i}")
    for w in vars_.list("vms/workers/"):
        it = vars_.get(w)[0]
        vars_.put(w, {**it, "units": ",".join(u for u in it["units"].split(",") if not (u.isdigit() and int(u) <= 20))})
    for i in range(201, 211):
        vars_.put(SPEC.sub.config(SPEC.rows, str(i)),
                  SPEC.items(SPEC.new_row(i, {"name": f"cam{i}", "source": f"driverpack://file/cam{i}.mp4"})))
    it = vars_.get("vms/cameras/30")[0]
    vars_.put("vms/cameras/30", {**it, "deleted": "true"})
    s = vars_.get("vms/slots/w-3")[0]
    vars_.put("vms/slots/w-3", {**s, "released": "true"})
    p = vars_.get("vms/placement/41")[0]                     # 41 is on w-2 (srv-1); put it on w-4 (srv-3)
    vars_.put("vms/placement/41", {**p, "worker": "w-4"})
    for w, add in (("vms/workers/w-2", False), ("vms/workers/w-4", True)):
        it = vars_.get(w)[0]
        units = [u for u in it["units"].split(",") if u != "41"] + (["41"] if add else [])
        vars_.put(w, {**it, "units": ",".join(sorted(units))})


def test_a_busy_pass_decides_exactly_what_the_pass_that_read_everything_again_decided():
    """The same busy scenario (`_busy`) on two identical stores: one pass with its reads kept for the pass, one with
    every read going to the store as before. The rows they leave — placements, assignments — and the snapshot they
    publish are the same; the first reads a fraction of what the second does."""
    counts, results = [], []
    for kept in (True, False):
        vars_, objects = cluster(200, 8, 4)
        _busy(vars_)
        v, o = Reads(vars_), Reads(objects)
        ctl = _vms(v, o)
        v.zero(), o.zero()
        if kept:
            _loop_pass(ctl)
        else:
            with without_pass_reads():
                _loop_pass(ctl)
        counts.append(v.n + o.n)
        results.append((rows(vars_), objects_but_the_report(objects)))
    assert results[0][0] == results[1][0]
    assert results[0][1] == results[1][1]
    placed = {k for k, it in results[0][0].items() if k.startswith("vms/placement/") and it.get("worker")}
    assert {f"vms/placement/{i}" for i in (*range(1, 21), *range(201, 211))} - {"vms/placement/30"} <= placed
    assert "vms/placement/30" not in placed                 # the deleted one is unplaced
    assert not results[0][0]["vms/workers/w-3"]["units"]    # the released slot was emptied
    assert results[0][0]["vms/placement/41"]["worker"] != "w-4"   # and 41 came home
    assert counts[0] * 5 < counts[1], counts


def test_a_pass_reads_back_what_it_wrote_and_a_lost_cas_asks_the_store_again():
    """Inside `one_pass` a key is read once — and a write forgets it, so the pass reads back its own write; a write by
    somebody else is not seen until a CAS on that key loses, and then `Controller.write` reads the store, not the copy.
    The doors' threads read the store while a pass runs on the loop's."""
    import threading
    from w2cplatform.memvariables import MemVariables as Mem
    vars_, objects = Mem(), MemObjects()
    vars_.put("vms/placement/1", {"worker": "w-1", "reason": "r", "at": NOW, "rev": 1})
    v = Reads(vars_)
    ctl = _vms(v, objects)
    other = Mem(vars_._s)                                    # another controller instance on the same store
    with ctl.one_pass():
        v.zero()
        assert ctl.placement(1).worker == "w-1" and ctl.placement(1).worker == "w-1"
        assert v.gets == 1                                   # once
        other.put("vms/placement/1", {"worker": "w-2", "reason": "r", "at": NOW, "rev": 2})
        assert ctl.placement(1).worker == "w-1"              # the pass's copy: at most a pass old
        seen = []
        t = threading.Thread(target=lambda: seen.append(ctl.vars.get("vms/placement/1")[0]["worker"]))
        t.start(), t.join()
        assert seen == ["w-2"]                               # another thread reads the store
        new = ctl.write("vms/placement/1", lambda it: {**it, "reason": "moved", "rev": int(it["rev"]) + 1})
        assert new["worker"] == "w-2" and new["rev"] == 3    # the CAS lost on the copy, the retry read the store
        assert ctl.placement(1).reason == "moved"            # …and the pass reads back its own write
    assert ctl.vars is v                                     # the pass ended: the store itself again


# -- the console's loops -----------------------------------------------------------------------------------------------

def _console(vars_, objects):
    from vms.config import DET_SPEC, DETJOB_SPEC, SURVEY_SPEC
    from w2cplatform.spec import SpecController
    return {"rec": _rec(vars_, objects), "det": SpecController(DET_SPEC, vars_, objects, wall=wall),
            "job": SpecController(DETJOB_SPEC, vars_, objects, wall=wall),
            "survey": SpecController(SURVEY_SPEC, vars_, objects, wall=wall), "vms": _vms(vars_, objects)}


def _old_requests_turn(c, now):
    from vms import jobs
    with without_pass_reads():
        jobs.record_on_request(c["rec"], now), jobs.expire_recordings(c["rec"], now)
        jobs.detect_on_request(c["det"], c["job"], c["rec"], now), jobs.expire(c["det"], now)


def test_the_request_loop_reads_a_thousand_backfills_once_and_not_every_two_seconds():
    """`_requests_turn` at a thousand recordings, detectors and standing backfills. Before: 3 034 reads every two
    seconds with nothing asked (every backfill row, every recording, every detector, for their `until`), 33 269 with ten
    recordings and ten scans asked (each request read the detectors, the recordings and the jobs again). Now: the
    listings alone between whole reads, which come every `Remembered.REREAD` seconds; the prefixes once a turn when
    something is asked. And what the turns write is what the old turns wrote, on the same scenario."""
    from vms import __main__ as m
    from vms.jobs import Remembered
    n = 1000
    vars_, objects = console_store(n)
    v = Reads(vars_)
    c, mem = _console(v, objects), Remembered()
    m._requests_turn(c["rec"], c["det"], c["job"], mem, now=NOW)     # the first turn reads everything whole
    v.zero()
    m._requests_turn(c["rec"], c["det"], c["job"], mem, now=NOW + 2)
    assert v.n <= 10, v.n                                    # nothing asked: two listings
    file_requests(vars_, 0)
    v.zero()
    m._requests_turn(c["rec"], c["det"], c["job"], mem, now=NOW + 4)
    assert v.n <= 3 * n + 300, v.n                           # asked: each family once, not once per request
    v.zero()
    m._requests_turn(c["rec"], c["det"], c["job"], mem, now=NOW + Remembered.REREAD + 1)
    assert 2 * n < v.n <= 3 * n + 300, v.n                   # the whole read, on its period

    stores = []
    for new in (True, False):
        vars_, objects = console_store(300)
        c, mem = _console(vars_, objects), Remembered()
        for t in range(3):
            file_requests(vars_, t)
            now = NOW + 2 * t
            m._requests_turn(c["rec"], c["det"], c["job"], mem, now=now) if new else _old_requests_turn(c, now)
        stores.append(rows(vars_))
    assert stores[0] == stores[1]
    assert sum(1 for k in stores[0] if k.startswith("rec/recordings/") and k.endswith("-auto")) == 30
    assert not [k for k in stores[0] if k.startswith(("det/requests/", "rec/requests/f"))]


def test_the_reaper_reads_each_job_detector_and_recording_once_a_turn():
    """`_reap_turn` at a thousand jobs, detectors, recordings and backfills, ten spans closed and ten hits. Before:
    54 918 reads a turn (every detector again per closed span, every recording per hit, every job twice). Now each
    key once, and the turn leaves the rows the old one left."""
    from vms import __main__ as m
    from vms import jobs
    n = 1000
    vars_, objects = console_store(n)
    v, o = Reads(vars_), Reads(objects)
    c = _console(v, o)
    v.zero(), o.zero()
    m._reap_turn([c["job"]], [c["rec"], c["vms"]], c["rec"], c["det"], c["survey"], now=NOW)
    assert v.n + o.n <= 6 * n + 100, (v.n, o.n)

    stores = []
    for new in (True, False):
        vars_, objects = console_store(300)
        c = _console(vars_, objects)
        if new:
            m._reap_turn([c["job"]], [c["rec"], c["vms"]], c["rec"], c["det"], c["survey"], now=NOW)
        else:
            with without_pass_reads():
                jobs.reap(c["job"]), jobs.forget_finished(c["job"], NOW), jobs.ask_for_footage(c["job"], c["rec"])
                jobs.scan_what_arrived(c["rec"], c["det"], c["job"]), jobs.keep_what_fired(c["survey"], c["rec"])
                jobs.clear_requests(c["rec"]), jobs.clear_requests(c["vms"])
        stores.append(rows(vars_))
    assert stores[0] == stores[1]
    assert sum(1 for k in stores[0] if k.startswith("detjob/jobs/") and f"-{int(NOW) - 900}-" in k) == 40   # four recorders, ten spans each
    assert sum(1 for k in stores[0] if k.startswith("rec/requests/") and f"-{int(NOW) - 500}-" in k) == 10  # the hits, kept


class _Refusing:
    """A store that will not take a recording's row: not a refusal — the store's own failure (a row over its ceiling,
    a store away)."""
    def __init__(self, inner): self.inner, self.tries = inner, 0

    def put(self, path, items, cas=None):
        if path.startswith("rec/recordings/"):
            self.tries += 1
            raise OSError("the store did not answer")
        return self.inner.put(path, items, cas=cas)

    def __getattr__(self, name): return getattr(self.inner, name)


def test_a_request_the_store_failed_is_tried_again_after_a_doubling_pause_not_every_turn():
    """A `record` the store would not take stays — it is not an answer — and was tried again on every two-second turn:
    fifteen times in its thirty seconds, and for ever when it carried no `valid_until`. Now after 2, 4, 8, 16 … seconds,
    up to `Remembered.RETRY_MAX`; and it is still tried, and still performed once the store takes it."""
    from vms import __main__ as m
    from vms.jobs import Remembered
    vars_, objects = cluster(10, 2, 2)
    store = _Refusing(vars_)
    c, mem = _console(store, objects), Remembered()
    vars_.put("rec/requests/f-1-0", {"unit": "3", "cam": "3", "action": "record", "minutes": "10", "at": str(NOW),
                                     "by": "auto/x"})                       # no `valid_until`: nothing ends it but an answer
    for t in range(0, 600, 2):
        m._requests_turn(c["rec"], c["det"], c["job"], mem, now=NOW + t)
    assert 5 <= store.tries <= 10, store.tries                 # 0, 2, 6, 14, 30, 62, 126, 254, 510 — not 300 tries
    c["rec"].vars = vars_                                    # the store takes it again
    m._requests_turn(c["rec"], c["det"], c["job"], mem, now=NOW + 900)
    assert vars_.get("rec/recordings/3-auto")[0] and not vars_.get("rec/requests/f-1-0")[0]


def test_an_end_is_kept_on_time_and_one_moved_by_another_console_is_read_before_anything_is_ended():
    """`expire` with the loop's memory reads the rows whole every `REREAD` seconds and, between, only the rows whose end
    has come. A recording this console started on request ends on its minute; one whose end another console moved later
    is read before it is ended, and is not; one another console gave an end is ended within `REREAD`."""
    from vms import jobs
    from vms.jobs import Remembered
    vars_, objects = cluster(10, 2, 2)
    c, mem = _console(vars_, objects), Remembered()
    rec = c["rec"]
    vars_.put("rec/requests/f-1-0", {"unit": "3", "cam": "3", "action": "record", "minutes": "0.25", "at": str(NOW),
                                     "by": "auto/x", "valid_until": str(NOW + 30)})
    vars_.put("rec/requests/f-2-0", {"unit": "4", "cam": "4", "action": "record", "minutes": "0.25", "at": str(NOW),
                                     "by": "auto/x", "valid_until": str(NOW + 30)})
    jobs.record_on_request(rec, NOW, mem)
    assert jobs.expire(rec, NOW, mem) == 0
    rec.update("4-auto", {"until": NOW + 3600})              # another console: a scenario asked for camera 4 again
    rec.update("5", {"until": NOW + 5})                      # another console ends recording 5 in five seconds
    v = Reads(vars_)
    rec.vars = v
    assert jobs.expire(rec, NOW + 10, mem) == 0              # 5's end is not known here yet; nothing read
    assert v.n == 0
    assert jobs.expire(rec, NOW + 16, mem) == 1              # 3-auto ends on time; 4-auto is read, and stays
    assert v.n <= 6, v.n                                     # the two rows due, and the delete's own CAS
    assert rec.unit("3-auto") is None and rec.unit("4-auto") is not None
    assert jobs.expire(rec, NOW + Remembered.REREAD + 1, mem) == 1   # the whole read: 5 is ended
    assert rec.unit("5") is None


def _waiting(vars_, objects, sub: str, k: int) -> None:
    """The first k units lose their placement and every worker of `sub` is full: they wait, and every pass tries them."""
    for i in range(1, k + 1):
        vars_.delete(f"{sub}/placement/{i}")
    for w in vars_.list(f"{sub}/workers/"):
        it = vars_.get(w)[0]
        vars_.put(w, {**it, "units": ",".join(u for u in it["units"].split(",") if u and int(u) > k)})
    for key in objects.list(f"{sub}/heartbeats/"):
        hb = json.loads(objects.get(key))
        hb["capacity"] = 1
        objects.put(key, json.dumps(hb).encode())


def test_units_waiting_for_room_cost_a_pass_what_placed_ones_cost():
    """A unit with no room tries every pass, and its filters asked about every other unit: `group_by` (the cameras of one
    device, `worker_with_group`) and `spread_by` (two copies apart, `servers_taken`) each read every row and its placement
    again per waiting unit, and what each candidate worker said was a walk of every heartbeat per question. Before: 500
    cameras waiting of 600 — 671 887 reads and ten seconds a pass; 200 recordings of 1000 waiting under a `spread_by` —
    857 964 reads and six seconds. Now the rows by group, the placements and what each worker said are the pass's: a
    waiting unit costs what a placed one does."""
    import dataclasses
    from vms.config import REC_SPEC
    from w2cplatform.spec import SpecController
    vars_, objects = cluster(600, 12, 3, recording=False)
    _waiting(vars_, objects, "vms", 500)
    v, o = Reads(vars_), Reads(objects)
    ctl = _vms(v, o)
    v.zero(), o.zero()
    _loop_pass(ctl)
    assert v.n + o.n <= 2 * 600 + 100, v.n + o.n
    assert ctl.pass_report()["unplaced"] == 500

    vars_, objects = cluster(1000, 20, 4)
    _waiting(vars_, objects, "rec", 200)
    v, o = Reads(vars_), Reads(objects)
    ctl = SpecController(dataclasses.replace(REC_SPEC, spread_by="cam"), v, o, wall=wall)
    v.zero(), o.zero()
    _loop_pass(ctl)
    assert v.n + o.n <= 2 * 1000 + 100, v.n + o.n
