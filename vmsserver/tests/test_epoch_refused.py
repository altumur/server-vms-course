"""One unit's garbled epoch row is that unit's trouble, in every worker (the review's fifth pass, a major).

The fourth pass mended the detector and the survey: `take_epoch` on a row `<sub>/epoch/<unit>` that does not
parse raised a `ValueError` out of the pass, and every unit after that one was not looked at. The same class
stood in the holder, the recorder, the scan, the evaluator and the gateway: the review wrote `vms/epoch/4` by
hand, and three passes in a row raised — camera 5 never started, camera 1, taken away, never stopped; the scan's
job did not move and the heartbeat did not say why. Now each of them refuses THAT unit, says why in its status
(the gateway in its heartbeat's `refused`) and in the log, and serves the rest.
"""
from w2cplatform.contract import Heartbeat
from vms.config import LIVE_SPEC
from vms.worker import FakeActuator, VmsWorker
from tests.conftest import Box, recorder

GARBLED = {"epoch": "four"}                                            # a hand edit


def test_the_holder_refuses_one_camera_and_starts_and_stops_the_others():
    from tests.test_lesson4_worker import _box_with_cameras
    box, ctl = _box_with_cameras(4)
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1")
    ctl.assign("w-1", ["1", "2"])
    assert w.reconcile_once() == [("start", 1), ("start", 2)]
    box.vars.put("vms/epoch/3", GARBLED)
    ctl.assign("w-1", ["2", "3", "4"])                                 # 1 taken away, 3 garbled, 4 after it
    for _ in range(3):                                                 # every pass, not once
        acts = w.reconcile_once()
        box.clock.advance(70)                                          # past the reconciler's backoff
    assert "1" not in w.epochs and "4" in w.epochs and "3" not in w.epochs
    w.heartbeat_once()
    st = {s["id"]: s for s in ctl.workers_seen()["w-1"].status}
    assert st[3]["phase"] == "failed" and "epoch could not be taken" in st[3]["why"]
    assert st[4]["phase"] == "running" and st[2]["phase"] == "running"


def test_the_recorder_refuses_one_recording_and_starts_the_next():
    from tests.test_rec_volume import _site
    box, rec_con, rec_ctl = _site()
    r = recorder(box)
    r.heartbeat_once()
    rec_con.create({"name": "1", "cam": "1"})
    rec_con.create({"name": "1-b", "cam": "1"})
    box.vars.put("rec/epoch/1", GARBLED)
    rec_ctl.ensure_placed()
    r.lease_pass()
    acts = r.reconcile_once()
    assert ("failed", "1") in acts and ("start", "1-b") in acts, acts
    st = {s["id"]: s for s in r.status()}
    assert st["1"]["phase"] != "running" and "epoch could not be taken" in st["1"].get("why", "")


def test_the_scan_refuses_one_job_and_the_next_one_moves():
    from tests.test_detjob_worker import _footage, _site, _worker, m
    from w2cplatform.spec import SpecController
    from vms.config import DETJOB_SPEC
    box = _site(); _footage(box, "7", 1, 0, 10)
    ctl = SpecController(DETJOB_SPEC, box.vars, box.objects, wall=box.wall)
    for name in ("7-lpr-1", "7-lpr-2"):
        ctl.create({"name": name, "cam": "7", "rec": "7", "kind": "lpr", "from": m(0), "to": m(10)})
    box.vars.put(DETJOB_SPEC.sub.assignment("j-1"), {"units": "7-lpr-1,7-lpr-2", "rev": 1})
    box.vars.put("detjob/epoch/7-lpr-1", GARBLED)                       # the first in the pass
    w = _worker(box)
    w.reconcile_once(); w.heartbeat_once()
    st = w.status_by_unit
    assert st["7-lpr-1"]["phase"] == "failed" and "epoch could not be taken" in st["7-lpr-1"]["why"]
    assert st["7-lpr-2"]["phase"] in ("running", "done") and w.events_written > 0
    hb = {s["id"]: s for s in Heartbeat.from_bytes(box.objects.get(DETJOB_SPEC.sub.heartbeat_key("j-1"))).status}
    assert hb["7-lpr-1"]["phase"] == "failed"                          # in the heartbeat, where the console reads it


def test_the_evaluator_refuses_one_scenario_and_decides_the_next():
    from tests.test_autoworker import DOOR, _Log, _assigned, _scenario, _worker, ev
    box = Box()
    t = box.wall()
    log = _Log([ev(t - 20, "det", "7-motion", "motion"), ev(t - 5, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box, name="a-door")
    _scenario(box)                                                     # `door-on-badge`, after `a-door` in the pass
    ctl = _assigned(box, "a-door")
    ctl.assign("a-1", ["a-door", "door-on-badge"])
    box.vars.put("auto/epoch/a-door", GARBLED)
    w = _worker(box, log)
    assert w.reconcile_once() == ["door-on-badge"]
    st = w.status_by_unit["a-door"]
    assert st["phase"] == "failed" and "epoch could not be taken" in st["why"]
    assert DOOR["name"] in w.epochs


def test_the_gateway_refuses_one_camera_and_subscribes_the_next():
    from tests.test_pass_failures import _workers
    box = Box()
    gw = _workers(box)[3]
    gw.rtp_source = lambda cam: ("srv-1", f"rtsp://srv-1/{cam}", 1)
    box.vars.put(LIVE_SPEC.sub.assignment("g-1"), {"units": "7,8", "rev": 1})
    box.vars.put("live/epoch/7", GARBLED)
    for _ in range(2):
        gw.reconcile_once()
    assert set(gw.upstreams) == {"8"} and "7" not in gw.epochs
    gw.heartbeat_once()
    hb = Heartbeat.from_bytes(box.objects.get(LIVE_SPEC.sub.heartbeat_key("g-1")))
    assert "epoch could not be taken" in hb.extra["refused"]["7"] and [s["id"] for s in hb.status] == ["8"]
    box.vars.put("live/epoch/7", {"epoch": "3"})                        # mended by hand: the next pass takes it
    gw.reconcile_once(); gw.heartbeat_once()
    hb = Heartbeat.from_bytes(box.objects.get(LIVE_SPEC.sub.heartbeat_key("g-1")))
    assert set(gw.upstreams) == {"7", "8"} and "refused" not in hb.extra
