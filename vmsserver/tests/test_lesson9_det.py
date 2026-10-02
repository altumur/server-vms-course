"""Lesson 9 — detectors as the third subsystem, and one console for
all of them. A unit is one model on one camera, created from the camera's page
with the console's token, placed on a GPU-labelled worker by stream headroom;
its events are buckets under det/<unit>/e<epoch>/ on the resource, written
under the epoch the worker holds. The VMS console mounts `/det/…` and
`/live/…` — one process, one port, one page."""
import json
import os
import urllib.error
import urllib.request

from w2cplatform.events import read_bucket, subsystems_under
from w2cplatform.spec import SpecController
from w2cplatform.variables import Forbidden
from vms.config import DET_SPEC, LIVE_SPEC, SPEC
from vms.controller import VmsController
from vms.detworker import DetWorker, FakeModel
from vms.worker import FakeActuator, VmsWorker
from vms.console import serve
from tests.conftest import Box


def _box():
    box = Box()
    ctl = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    con_vars = box.vars.as_writer("console", SPEC.acl_console() + LIVE_SPEC.acl_console() + DET_SPEC.acl_console())
    con = VmsController(con_vars, box.objects, wall=box.wall)
    det_ctl = SpecController(DET_SPEC, box.vars.as_writer("detcontroller", DET_SPEC.acl_controller()), box.objects, wall=box.wall)
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1", archive_root=box.archive)
    w.heartbeat_once()
    con.create_camera({"name": "gate", "source": "driverpack://file/gate.mp4"}); ctl.ensure_placed()
    w.reconcile_once(); w.heartbeat_once()
    srv = serve(con, None, port=0, wall=box.wall, live_ctl=SpecController(LIVE_SPEC, con_vars, box.objects, wall=box.wall),
                mounts={"det": SpecController(DET_SPEC, con_vars, box.objects, wall=box.wall)})
    return box, ctl, det_ctl, w, srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _det(box, name, labels="gpu", capacity=8):
    d = DetWorker(name, box.vars.as_writer("detworker", ["det/epoch/*", "det/slots/*"]), box.objects, capacity=capacity,
                  clock=box.clock, wall=box.wall, server="srv-1", archive_root=box.archive, env={"LABELS": labels})
    d.heartbeat_once()
    return d


def call(base, method, path, body=None, headers=None):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def test_one_console_mounts_every_subsystem_it_fronts():
    box, ctl, det_ctl, w, srv, base = _box()
    try:
        assert call(base, "GET", "/spec")[1]["name"] == "vms" and call(base, "GET", "/live/spec")[1]["name"] == "live"
        assert call(base, "GET", "/det/spec")[1]["rows"] == "units"
        m = call(base, "GET", "/mounts")[1]
        assert m["root"] == "vms" and sorted(m["mounts"]) == ["det", "live"] and m["mounts"]["det"]["id"] == "name"
        assert call(base, "GET", "/det/units")[1] == {"rows": [], "configured": []}
        assert "det_workers_live 0" in urllib.request.urlopen(f"{base}/det/metrics").read().decode()
        assert call(base, "GET", "/det/nope")[0] == 404 and call(base, "GET", "/nope/spec")[0] == 404
    finally:
        srv.shutdown(); srv.server_close()


def test_a_model_on_a_camera_is_placed_on_a_gpu_worker_and_writes_its_own_buckets():
    box, ctl, det_ctl, w, srv, base = _box()
    try:
        cpu, gpu = _det(box, "d-1", labels=""), _det(box, "d-2", labels="gpu")
        # from the camera's page: the console's token writes det's rows; the name is the operator's for the pair
        unit = {"name": "1-linecross", "cam": "1", "kind": "linecross", "params": "line=10,20;30,40"}
        st, r = call(base, "POST", "/det/units", unit, {"Idempotency-Key": "k1"})
        assert st == 201 and r["id"] == "1-linecross" and r["labels"] == ["gpu"] and r["worker"] is None
        assert call(base, "POST", "/det/units", unit, {"Idempotency-Key": "k1"})[0] == 201   # the same POST: the same body under the same key
        assert call(base, "POST", "/det/units", {"name": "x", "cam": "1", "kind": "motion", "worker": "d-2"}, {"Idempotency-Key": "k2"})[0] == 400  # placement is not the operator's
        try:
            SpecController(DET_SPEC, box.vars.as_writer("console", DET_SPEC.acl_console()), box.objects, wall=box.wall).place("1-linecross")
            raise AssertionError("a console token never writes placement")
        except Forbidden:
            pass
        # the det controller's pass: only the GPU worker is eligible
        assert det_ctl.ensure_placed()[0].worker == "d-2" and "reaching gpu" in det_ctl.placement("1-linecross").reason
        assert call(base, "GET", "/det/where/1-linecross")[1]["worker"] == "d-2"
        # the worker runs the model against the camera's RTP (from the VMS heartbeat) and writes events under its epoch
        assert cpu.reconcile_once() == [] and gpu.reconcile_once() == ["1-linecross"]
        assert box.vars.get("det/epoch/1-linecross")[0] == {"epoch": "1"}
        for _ in range(5):
            box.wall.advance(2); gpu.reconcile_once()
        gpu.heartbeat_once()
        st = call(base, "GET", "/det/units")[1]["rows"][0]
        assert st["phase"] == "running" and st["events"] == 2 and st["source"] == "rtsp://srv-1:8554/1" and st["worker"] == "d-2"
        # its own prefix on the same resource — and a line crossed is an ALARM (det.subsystem.yaml, `alarms`), so the
        # tree is the alarms' one, with the alarms' days (M12 of the review: these used to be observations)
        assert subsystems_under(box.archive) == {"det.alarms": ["1-linecross"]}
        e1 = os.path.join(box.archive, "det.alarms", "1-linecross", "e1")
        lines = [l for b in sorted(os.listdir(e1)) for l in read_bucket(os.path.join(e1, b))]
        assert [(l["kind"], l["pass"], l["cam"], l["class"]) for l in lines] == [("linecross", 3, 1, "alarm"), ("linecross", 6, 1, "alarm")]
        assert det_ctl.unit("1-linecross")["alarms"] == ["linecross", "lpr"]            # the row says which kinds; the operator may change it
        assert "det_units_running 1" in urllib.request.urlopen(f"{base}/det/metrics").read().decode()
        # disable from the page: the model stops, the row says pending; enable again: a new run under the SAME epoch (same writer)
        assert call(base, "PUT", "/det/units/1-linecross", {"enabled": False})[0] == 200
        assert gpu.reconcile_once() == [] and gpu.status_by_unit["1-linecross"]["phase"] == "pending"
        call(base, "PUT", "/det/units/1-linecross", {"enabled": True}); gpu.reconcile_once()
        assert box.vars.get("det/epoch/1-linecross")[0] == {"epoch": "1"}
        # delete from the page: the controller takes the placement back, the worker stops and releases; the buckets stay
        assert call(base, "DELETE", "/det/units/1-linecross")[0] == 200 and det_ctl.unplace_deleted() == ["1-linecross"]
        assert gpu.reconcile_once() == [] and "1-linecross" not in gpu.epochs and os.path.isdir(e1)
    finally:
        srv.shutdown(); srv.server_close()


def test_a_camera_nobody_holds_leaves_the_model_waiting_not_failed():
    box, ctl, det_ctl, w, srv, base = _box()
    try:
        gpu = _det(box, "d-1")
        call(base, "POST", "/det/units", {"name": "1-motion", "cam": "1", "kind": "motion"}, {"Idempotency-Key": "k1"})
        det_ctl.ensure_placed(); assert gpu.reconcile_once() == ["1-motion"]
        w.actuator.dead.append(1); w.pump_once(); w.heartbeat_once()                    # the camera's pipeline died: its phase is no longer running
        assert gpu.reconcile_once() == [] and gpu.status_by_unit["1-motion"] == {"id": "1-motion", "cam": "1", "kind": "motion", "phase": "waiting", "why": "camera held by nobody"}
        assert det_ctl.where("1-motion") == "d-1"                                        # placement is untouched: the worker waits, nothing is moved
        # an unknown model kind is reported, not run
        call(base, "POST", "/det/units", {"name": "1-face", "cam": "1", "kind": "face"}, {"Idempotency-Key": "k2"})
        det_ctl.ensure_placed(); w.reconcile_once(); w.heartbeat_once(); gpu.reconcile_once()
        assert gpu.status_by_unit["1-face"]["phase"] == "unsupported" and gpu.headroom() == 8   # nothing runs while the camera is down
    finally:
        srv.shutdown(); srv.server_close()


def test_motion_is_an_observation_and_its_repeats_collapse_into_one_line_and_a_summary():
    """M12 of the review: every line a model produced went into the log as an observation, and a motion model
    re-reports for as long as the scene moves. The subsystem now declares its repeats (det.subsystem.yaml,
    `events.suppress`) and the worker applies them before the write, as the VMS worker does: the first line of
    a window goes in, the rest are counted, and the count is written when the window closes — even when the
    scene went still and no observation came to close it."""
    box, ctl, det_ctl, w, srv, base = _box()
    try:
        gpu = _det(box, "d-1")
        call(base, "POST", "/det/units", {"name": "1-motion", "cam": "1", "kind": "motion"}, {"Idempotency-Key": "k1"})
        gpu.models["motion"] = lambda unit: FakeModel(unit, every=1)                   # the scene moves on every pass
        det_ctl.ensure_placed(); gpu.reconcile_once()
        for _ in range(10):
            box.wall.advance(2); gpu.reconcile_once()                                  # eleven observations in twenty seconds
        e1 = os.path.join(box.archive, "det", "1-motion", "e1")
        lines = lambda: [l for b in sorted(os.listdir(e1)) for l in read_bucket(os.path.join(e1, b))]   # noqa: E731
        assert [l["kind"] for l in lines()] == ["motion"] and "class" not in lines()[0]   # one line, an observation
        assert gpu.status_by_unit["1-motion"]["events"] == 1
        gpu.models["motion"] = lambda unit: FakeModel(unit, every=10 ** 6)             # the scene goes still…
        gpu._stop("1-motion"); gpu.reconcile_once()
        box.wall.advance(31); w.heartbeat_once(); gpu.reconcile_once()                 # …and the window closes with nothing to carry the summary
        summary = lines()[-1]
        assert len(lines()) == 2 and summary["kind"] == "motion" and summary["repeats"] == 10
        assert summary["since"] == lines()[0]["t"] and summary["until"] == lines()[0]["t"] + 20
        assert not os.path.isdir(os.path.join(box.archive, "det.alarms"))             # motion is nobody's alarm
    finally:
        srv.shutdown(); srv.server_close()


def test_nothing_with_a_gpu_is_unplaceable_and_says_why():
    box, ctl, det_ctl, w, srv, base = _box()
    try:
        _det(box, "d-1", labels="")
        call(base, "POST", "/det/units", {"name": "1-lpr", "cam": "1", "kind": "lpr"}, {"Idempotency-Key": "k1"})
        assert det_ctl.ensure_placed() == []
        assert call(base, "GET", "/det/unplaceable")[1] == [{"id": "1-lpr", "labels": ["gpu"], "workers_live": 1}]
        _det(box, "d-2", labels="gpu,nvidia")
        assert det_ctl.ensure_placed()[0].worker == "d-2"                                # a GPU arrives: placed, nothing else moves
    finally:
        srv.shutdown(); srv.server_close()


def test_one_detectors_model_failing_is_that_detectors_trouble_and_not_the_passs():
    """The review's third pass (M19's remainder). The model's factory — a weights file missing, a mask that does not
    decode — and its `observe` raised out of the pass, and every detector after it in the loop was not looked at,
    every pass. The broken one says `failed` and why; the others run and write."""
    box, ctl, det_ctl, w, srv, base = _box()
    try:
        gpu = _det(box, "d-1")

        class Broken:
            def __init__(self, row):
                raise FileNotFoundError("lpr.weights")

        class Sees:
            def __init__(self, row): self.row = row
            def observe(self, now): return [("motion", {"area": 1})]
            def close(self): pass
        gpu.models = {"lpr": Broken, "motion": Sees}
        call(base, "POST", "/det/units", {"name": "1-lpr", "cam": "1", "kind": "lpr"}, {"Idempotency-Key": "k1"})
        call(base, "POST", "/det/units", {"name": "1-motion", "cam": "1", "kind": "motion"}, {"Idempotency-Key": "k2"})
        det_ctl.ensure_placed()
        assert gpu.reconcile_once() == ["1-motion"]
        assert gpu.status_by_unit["1-lpr"]["phase"] == "failed" and "lpr.weights" in gpu.status_by_unit["1-lpr"]["why"]
        assert gpu.status_by_unit["1-motion"]["phase"] == "running" and gpu.events_written >= 1
    finally:
        srv.shutdown(); srv.server_close()
