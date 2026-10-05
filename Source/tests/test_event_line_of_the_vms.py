"""The event line as the VMS writes it and acts on it (the platform review; feedback BL) — the VMS's half of
`test_event_line.py`, whose platform half (the line's name, the reader's `by`, the merge) is proved on testsub there.

A scenario fires on when things happened and is named after the event that completed it; a device that knows when
something happened says so and the line carries it; and only what one of OUR elements said on the bus is an
observation of the camera.
"""
import os

from w2cplatform.eventdatabase import EventIndex
from tests.vmsconftest import Box
from tests.test_autoworker import DOOR, _assigned, _Log, _scenario, _worker, ev


def test_a_scenario_counts_in_event_time_and_is_named_after_the_event():
    box = Box()
    t = box.wall()
    # Two badges in one millisecond are two firings: the name is the event's, not its time
    same = [ev(t - 10, "vms", 12, "io.input", port="1", value="closed", id="12-e1-abc-1"),
            ev(t - 10, "vms", 12, "io.input", port="1", value="closed", id="12-e1-abc-2")]
    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")
    w = _worker(box, _Log(same))
    w.reconcile_once()
    assert sorted(box.vars.list("vms/requests/")) == ["vms/requests/one-12-e1-abc-1-0", "vms/requests/one-12-e1-abc-2-0"]
    assert box.vars.get("vms/requests/one-12-e1-abc-1-0")[0]["valid_until"] == str(t - 10 + 30.0)


def test_within_is_between_when_two_things_happened_and_a_late_event_is_too_late_to_act_on():
    box = Box()
    t = box.wall()
    # Motion at t-200; the contact closed at t-190 — ten seconds later — and the device told us only now.
    # Written 190 s apart, they HAPPENED inside the window: the scenario fires. But the action was due thirty
    # seconds after the contact closed: nothing is filed, and the firing says how late it was.
    events = [ev(t - 200, "det", "7-motion", "motion", id="m-1"),
              ev(t - 5, "vms", 12, "io.input", port="1", value="closed", id="d-1", occurred=t - 190)]
    _scenario(box); _assigned(box, "door-on-badge")
    w = _worker(box, _Log(events))
    w.reconcile_once()
    assert box.vars.list("vms/requests/") == [] and w.late == 1 and w.filed == 0

    # …and written in time, it is filed with the deadline counted from when it happened
    box2 = Box(); t = box2.wall()
    events = [ev(t - 12, "det", "7-motion", "motion", id="m-1"),
              ev(t - 1, "vms", 12, "io.input", port="1", value="closed", id="d-1", occurred=t - 4)]
    _scenario(box2); _assigned(box2, "door-on-badge")
    w = _worker(box2, _Log(events))
    w.reconcile_once()
    assert box2.vars.get("vms/requests/door-on-badge-d-1-0")[0]["valid_until"] == str(t - 4 + 30.0)


def test_a_device_that_knows_when_it_happened_says_so_and_the_line_carries_it():
    """The review's second pass, M11. `occurred` existed in the line and nothing on the device's path filled it:
    `observe` stamped the bus-drain time and that was all. A path that reads the device's clock passes `occurred`
    in the fields and the line carries it, by the writer's `t`; a path that does not passes nothing and no second
    time is invented; a value that is not a time is dropped, not written and not raised."""
    from w2cplatform.events import read_bucket
    from vms.controller import VmsController
    from vms.worker import FakeActuator, VmsWorker
    box = Box()
    ctl = VmsController(box.vars, box.objects, wall=box.wall)
    ctl.create_camera({"source": "driverpack://file/1.mp4"}); ctl.assign("w-1", ["1"])
    act = FakeActuator()
    w = VmsWorker("w-1", box.vars, box.objects, act, clock=box.clock, wall=box.wall, resource_root=box.resource_root)
    w.reconcile_once()
    t = box.wall()
    act.post(1, "io.input", port="1", occurred=t - 50)                 # the device said when the contact closed
    act.post(1, "motion")                                              # a path that knows no better
    act.post(1, "io.input", port="2", occurred="yesterday")            # a device that says something that is not a time
    w.pump_once()
    p = w.observe(1, "probe")                                          # the bucket every line of this moment went to
    assert p and os.path.exists(p)
    lines = {e["kind"] + e.get("port", ""): e for e in read_bucket(p)}
    assert lines["io.input1"]["t"] == t and lines["io.input1"]["occurred"] == t - 50
    assert "occurred" not in lines["motion"] and "occurred" not in lines["io.input2"]
    assert EventIndex(box.resource_root, "srv-1", wall=box.wall).query(t - 60, t - 40, by="occurred")["events"][0]["kind"] == "io.input"


def test_only_what_our_own_element_said_is_an_observation():
    """The filter was a list of names to drop. On the product's box `rtpbin` posted `application/x-rtp-source-sdes`
    every few seconds and each became an event of the camera. The question is who posted it."""
    import os
    from gstvms.observes import observes
    assert observes("driverpacksrc", "motion")
    assert not observes("rtpbin", "application/x-rtp-source-sdes") and not observes("", "motion")
    assert not observes("splitmuxsink", "splitmuxsink-fragment-closed") and not observes("appsink", "eos")
    assert observes("acmemotion", "motion", extra=("acmemotion",))
    os.environ["EVENT_ELEMENTS"] = "acmemotion,acmeface"
    try:
        assert observes("acmeface", "face")
    finally:
        del os.environ["EVENT_ELEMENTS"]
