"""One unit's garbled epoch row is that unit's trouble, in every worker (the review's fifth pass, a major).

The fourth pass mended the detector and the survey: `take_epoch` on a row `<sub>/epoch/<unit>` that does not
parse raised a `ValueError` out of the pass, and every unit after that one was not looked at. The same class
stood in the holder, the recorder, the scan, the evaluator and the gateway: the review wrote `vms/epoch/4` by
hand, and three passes in a row raised — camera 5 never started, camera 1, taken away, never stopped; the scan's
job did not move and the heartbeat did not say why. Now each of them refuses THAT unit, says why in its status
(the gateway in its heartbeat's `refused`) and in the log, and serves the rest.
"""
import json

from w2cplatform.contract import Heartbeat
from vms.config import LIVE_SPEC
from vms.worker import FakeActuator, VmsWorker
from tests.vmsconftest import Box, recorder

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
    from tests.vmsconftest import four_workers
    box = Box()
    gw = four_workers(box)[3]
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


# -- commands: a request is a row too, and one row's trouble is that row's (the review's sixth pass) ---------------

def _two_doors(box):
    """Two devices held with no stream (`live: on-demand`): no epoch until the first command to each."""
    from tests.test_group_by import _ctl, _holder, _worker
    ctl, con = _ctl(box)
    doors = [con.create_camera({"name": f"door {i}", "source": f"driverpack://acme/10.0.0.9{i}/ch/1", "live": "on-demand"})["id"]
             for i in (1, 2)]
    _worker(box, "w-1", "srv-a"); ctl.ensure_placed()
    w = _holder(box, relays=2); w.reconcile_once()
    return con, doors, w


def _ask(box, con, rid, unit, **fields):
    from vms.config import SPEC
    con.vars.put(SPEC.sub.request_key(rid), {"unit": str(unit), "action": "output", "port": "1",
                                             "valid_until": str(box.wall() + 30), **fields})


def test_a_command_to_a_unit_whose_epoch_is_garbled_is_refused_alone_and_the_other_devices_are_commanded():
    """П-M11's remainder. A unit held without a lease takes its epoch before its first command (`requests`), and that
    `take_epoch` stood outside any `try`: with `vms/epoch/1` garbled, the `ValueError` went out of `requests` and of
    every `pump_once` after it — the review ran it for 600 s, the request's whole life — and the command to door 2,
    behind it in the pass, never reached its device. Now the refusal is that command's: answered, counted, said in
    the unit's status, and the pass goes on to the next request."""
    box = Box()
    con, (one, two), w = _two_doors(box)
    box.vars.put(f"vms/epoch/{one}", GARBLED)
    _ask(box, con, "a-1", one)
    _ask(box, con, "b-2", two)
    for _ in range(3):                                                 # every pump, not once
        w.pump_once()
    assert w.devices["acme/10.0.0.92"].did == [("output", 1, "pulse", 0)], "the command behind the garbled one never reached its device"
    assert w.devices["acme/10.0.0.91"].did == [] and str(one) not in w.leases
    assert w.fetched == ["a-1", "b-2"]                                 # both answered: the console clears the rows
    assert (w.commands["performed"], w.commands["refused"]) == (1, 1)
    st = {s["id"]: s for s in w.status()}
    assert "epoch could not be taken" in st[one]["why"] and "why" not in st[two]
    w.heartbeat_once()
    hb = Heartbeat.from_bytes(box.objects.get("vms/heartbeats/w-1"))
    assert hb.extra["command_counts"]["refused"] == 1 and hb.extra["fetched"] == "a-1,b-2"
    box.vars.put(f"vms/epoch/{one}", {"epoch": "3"})                    # mended by hand: the next command is performed
    _ask(box, con, "c-1", one)
    w.pump_once()
    assert w.devices["acme/10.0.0.91"].did == [("output", 1, "pulse", 0)] and w.epochs[str(one)] == 4
    assert "why" not in {s["id"]: s for s in w.status()}[one]


def test_a_command_whose_deadline_does_not_parse_is_refused_alone():
    """The sibling the review did not name, a few lines above: `valid_until` was read with a bare `float`. A row with
    a word there raised out of every pump for ever — it never reached the check that expires it — and no command
    behind it was performed."""
    box = Box()
    con, (one, two), w = _two_doors(box)
    _ask(box, con, "a-1", one, valid_until="soon")
    _ask(box, con, "b-2", two)
    for _ in range(2):
        w.pump_once()
    assert w.devices["acme/10.0.0.92"].did == [("output", 1, "pulse", 0)] and w.devices["acme/10.0.0.91"].did == []
    assert w.fetched == ["a-1", "b-2"] and (w.commands["performed"], w.commands["refused"]) == (1, 1)


def test_a_command_whose_mark_is_nested_past_jsons_depth_is_that_commands_and_the_others_are_performed():
    """The eleventh review, a major — a run: `mark_of` caught `ValueError` and the mark `[[[[…` raised `RecursionError`
    out of `requests()` at every look: commands a, b, c and six more in six minutes, `performed=0`, and those past their
    deadline not closed. A mark that does not parse is still a mark — another instance may have begun it, so it is not
    performed again — and it is that command's: the next is performed in the same look."""
    box = Box()
    con, (one, two), w = _two_doors(box)
    box.objects.put("vms/commands/a-1", b"[" * 100_000)
    _ask(box, con, "a-1", one)
    _ask(box, con, "b-2", two)
    for _ in range(2):
        w.pump_once()
    assert w.devices["acme/10.0.0.92"].did == [("output", 1, "pulse", 0)], "the command behind the deep mark never reached its device"
    assert w.devices["acme/10.0.0.91"].did == [] and set(w.fetched) == {"a-1", "b-2"}


def test_a_command_argument_longer_than_a_word_is_that_commands_refusal_and_never_reaches_the_driver():
    """The product's cross-check of the eleventh review: a command's argument had no size — `state` went to the driver
    as the row held it, as long as the row's ceiling let it be. One longer than `ARG_MAX` is that command's refusal,
    its value not repeated in the answer; the next command is performed."""
    box = Box()
    con, (one, two), w = _two_doors(box)
    _ask(box, con, "a-1", one, state="x" * 5000)
    _ask(box, con, "b-2", two)
    for _ in range(2):
        w.pump_once()
    assert w.devices["acme/10.0.0.91"].did == [] and w.devices["acme/10.0.0.92"].did == [("output", 1, "pulse", 0)]
    assert (w.commands["performed"], w.commands["refused"]) == (1, 1)
    st = {s["id"]: s for s in w.status()}
    assert "x" * 100 not in json.dumps(st)


def test_the_recorder_refuses_one_request_whose_range_does_not_parse_and_serves_the_next():
    """The same class in `RecWorker.requests`, which takes no epoch but reads `from` and `to` bare: a request row
    with a word there raised out of the backfill thread's `requests` on every pass, and no request behind it — any
    recording's — was ever fetched. It is answered (the console clears the row) and said in the log."""
    from tests.test_backfill_bounds import NOW, _ours, _recorder
    from vms.config import REC_SPEC
    act = FakeActuator()
    box, r, con_rec = _recorder(act)
    _ours(box, r, 1, ((NOW - 3600, NOW - 2400),))
    con_rec.vars.put(REC_SPEC.sub.request_key("1-a"), {"unit": "1", "cam": "1", "from": "yesterday", "to": str(NOW - 29700), "at": str(NOW), "by": "anna"})
    con_rec.vars.put(REC_SPEC.sub.request_key("1-b"), {"unit": "1", "cam": "1", "from": str(NOW - 30000), "to": str(NOW - 29700), "at": str(NOW), "by": "anna"})
    done = {d["request"]: d for d in r.requests(now=NOW)}
    assert "not a range" in done["1-a"]["error"] and "error" not in done["1-b"]
    assert r.fetched == ["1-a", "1-b"] and len(act.fetched) >= 1
