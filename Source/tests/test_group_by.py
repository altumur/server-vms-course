"""One connection per device, enforced where the decision is made.

A recorder with sixteen channels is sixteen rows. Every other rule in the
catalogue spreads them — most free capacity, labels, the policy — and each move
away from the first one opens another session to a box that licenses two. The
failure then arrives in the device's own words ("too many sessions", a channel
that will not start, a stream that drops when the fifth is added), an hour after
the placement that caused it and on another machine.

`group_by: device` is the mirror of `spread_by`: units sharing a value go on the
SAME worker, as a filter. These tests are about that, and about the three places
a naive version of it goes wrong — a dead holder, a group that outgrows its
worker, and a spec that asks for both at once.
"""
import io
import json

from w2cplatform.spec import SpecController, SubsystemSpec
from w2cplatform.contract import Heartbeat
from vms.config import SPEC
from vms.controller import VmsController
from w2cplatform.variables import Forbidden
from tests.conftest import Box


def _ctl(box):
    """The pair every test here needs: the controller places, the console creates —
    two tokens, as on a real box."""
    ctl = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    return ctl, con


def _worker(box, name, server, capacity=50, labels=""):
    box.objects.put(SPEC.sub.heartbeat_key(name),
                    Heartbeat(name, box.wall(), [], {"server": server, "capacity": capacity,
                                                     "headroom": capacity, "labels": labels}).to_bytes())
    box.objects.put(f"platform/resources/{server}/heartbeat",
                    json.dumps({"server": server, "ts": box.wall(), "url": f"http://{server}", "units": {}}).encode())


def _cam(con, name, source):
    return con.create_camera({"name": name, "source": source})


NVR = "driverpack://acme/10.0.0.50/ch/"          # one box, many channels
CAM = "driverpack://acme/10.0.0.77/ch/1"         # a camera of its own


def test_channels_of_one_device_go_to_one_worker():
    """The point. Two workers, both empty, both eligible: capacity alone would
    put one channel on each, and that is two sessions to one recorder."""
    box = Box(); ctl, con = _ctl(box)
    _worker(box, "w-1", "srv-a"); _worker(box, "w-2", "srv-b")

    a = _cam(con, "ch1", NVR + "1")["id"]
    b = _cam(con, "ch2", NVR + "2")["id"]
    other = _cam(con, "gate", CAM)["id"]
    ctl.ensure_placed()

    assert ctl.where(a) == ctl.where(b), "two channels of one recorder, two sessions"
    assert ctl.group_value(ctl.camera(a)) == "driverpack://acme/10.0.0.50" == ctl.group_value(ctl.camera(b))   # the spec's `cut_at: ch`
    assert ctl.where(other) != ctl.where(a)          # a different device is free to balance away

    # and a channel added later joins them rather than the emptier worker
    c = _cam(con, "ch3", NVR + "3")["id"]
    ctl.ensure_placed()
    assert ctl.where(c) == ctl.where(a)


def test_a_row_with_no_source_groups_with_nothing():
    """An empty group is no group. A row half-created — or a unit of a kind that
    has no device at all — must not be dragged towards somebody else's box."""
    box = Box(); ctl, con = _ctl(box)
    assert ctl.group_value({"id": 1, "source": ""}) == ""
    assert ctl.group_value({"id": 1}) == ""
    _worker(box, "w-1", "srv-a")
    assert ctl.eligible({"id": 1, "labels": []}, ["w-1"]) == ["w-1"]


def test_a_dead_holder_does_not_pin_the_group_to_itself():
    """The mistake that turns a safety rule into an outage. The worker holding
    the group goes silent; its units have to move. Reading its placement as "the
    group lives there" would make every one of them unplaceable at exactly the
    moment they need somewhere to go."""
    box = Box(); ctl, con = _ctl(box)
    _worker(box, "w-1", "srv-a"); _worker(box, "w-2", "srv-b")
    a = _cam(con, "ch1", NVR + "1")["id"]
    b = _cam(con, "ch2", NVR + "2")["id"]
    ctl.ensure_placed()
    home = ctl.where(a)
    assert ctl.where(b) == home

    box.wall.advance(120)                                  # that worker stops heartbeating
    survivor = "w-2" if home == "w-1" else "w-1"
    _worker(box, survivor, "srv-b" if survivor == "w-2" else "srv-a")

    pool = ctl._pool(None)
    assert pool == [survivor]                              # the dead one is out of the pool
    assert ctl.eligible(ctl.camera(a), pool) == [survivor]  # …so the group is free to re-form there
    assert ctl.eligible(ctl.camera(b), pool) == [survivor]
    assert ctl.unplaceable() == []                         # and nothing reads as "nowhere to go"


def test_a_group_that_outgrows_its_worker_is_unplaceable_and_says_which_device():
    """The cost of the rule, stated rather than hidden. The worker holding a
    device is not chosen for its room, so a group can outgrow it — and then the
    honest answer is "nowhere", because the alternative is the second session
    this whole thing exists to prevent. The operator raises capacity or moves
    the group; `/unplaceable` is where they find out."""
    box = Box(); ctl, con = _ctl(box)
    _worker(box, "w-1", "srv-a", capacity=2); _worker(box, "w-2", "srv-b", capacity=50)

    a = _cam(con, "ch1", NVR + "1")["id"]
    b = _cam(con, "ch2", NVR + "2")["id"]
    ctl.ensure_placed()
    ctl.move(a, "w-1", "the operator put this recorder here"); ctl.move(b, "w-1", "…and its second channel")
    assert ctl.where(a) == ctl.where(b) == "w-1"           # two of two: the small worker is full

    c = _cam(con, "ch3", NVR + "3")["id"]
    ctl.ensure_placed()
    assert ctl.placement(c) is None                        # w-2 has room, and using it would be a second session

    # And the state it is in is "waiting", not "unplaceable" — `unplaceable` means nobody may EVER take
    # it, and somebody may: the worker holding its device, once it has room. The difference matters to
    # the operator in one way, and it is worth knowing: this one will not be helped by another worker.
    assert ctl.eligible(ctl.camera(c), ctl._pool(None)) == ["w-1"]
    assert ctl.unplaceable() == []

    # …and the way out is room on the worker that holds the device, not another worker
    _worker(box, "w-1", "srv-a", capacity=3)
    ctl.ensure_placed()
    assert ctl.where(c) == "w-1"


def test_a_channel_whose_groups_worker_does_not_pass_its_filters_waits_and_is_not_placed_alone():
    """The eleventh review, a minor: the group's worker was looked for among the workers the filters LEFT, so a channel
    the device's worker did not pass — a label given to that channel, the server's row unread this pass — found no
    group and was placed alone on another worker: two sessions to one recorder. The group's worker is looked for in the
    whole pool now; such a channel waits, and `/unplaceable` says beside whom.

    …AND NOT FOR EVER (the review's thirteenth pass, major 17; `dq13_group` U): it waited for good, and no door moves a
    group by hand. A member the group's worker may not take is a reason to move the group whole: the pass moves ch1 and
    ch2 onto a worker every channel may go to, with room for all three, and ch3 follows them there."""
    box = Box(); ctl, con = _ctl(box)
    _worker(box, "w-1", "srv-a", labels="vlan:a"); _worker(box, "w-2", "srv-b", labels="vlan:a,vlan:c")
    a = con.create_camera({"name": "ch1", "source": NVR + "1", "labels": "vlan:a"})["id"]
    b = con.create_camera({"name": "ch2", "source": NVR + "2", "labels": "vlan:a"})["id"]
    ctl.ensure_placed()
    ctl.move(a, "w-1", "the operator put this recorder here"); ctl.move(b, "w-1", "…and its second channel")
    c = con.create_camera({"name": "ch3", "source": NVR + "3", "labels": "vlan:a,vlan:c"})["id"]
    ctl.ensure_placed()
    assert ctl.placement(c) is None, f"placed alone on {ctl.where(c)}: two sessions to one recorder"
    why = {u["id"]: u.get("why", "") for u in ctl.unplaceable()}
    assert "its source is held on w-1" in why[c], why
    ctl.pass_once()                                                          # the group moves whole…
    assert ctl.where(a) == ctl.where(b) == "w-2" and "which w-1 may not take" in ctl.placement(a).reason
    ctl.pass_once()                                                          # …and the new channel follows it
    assert ctl.where(c) == "w-2" and ctl.unplaceable() == []


def test_a_released_workers_group_goes_whole_to_a_worker_with_room_and_a_rebalance_moves_groups_whole():
    """The product's cross-check of the eleventh review: placement and redistribution, not only `ensure_reach`, must
    keep a device's channels together. `redistribute` moved a draining server's channels one by one onto `_pick`'s
    worker — the near one, with room for two of three, and the third then waited behind its full worker for good; and
    `rebalance` moved its first candidate alone — a channel away from its recorder's other channels. The first of a
    group now goes where the whole group has room, and a rebalance moves a group whole, inside its budget, or another
    unit."""
    from vms.config import REC_SPEC
    box = Box(); ctl, con = _ctl(box)
    _worker(box, "w-1", "srv-a")
    nvr = [_cam(con, f"ch{c}", NVR + str(c))["id"] for c in (1, 2, 3)]
    ctl.ensure_placed()
    _worker(box, "w-2", "srv-b", capacity=2); _worker(box, "w-3", "srv-c", capacity=50)
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-1"),                  # channel 1's recorder runs on srv-b: near
                    Heartbeat("r-1", box.wall(), [{"id": "rec-1", "cam": str(nvr[0]), "phase": "running"}],
                              {"server": "srv-b"}).to_bytes())
    VmsController(box.vars, box.objects, wall=box.wall).drain("srv-a")      # the operator's statement
    ctl.redistribute()
    assert [ctl.where(c) for c in nvr] == ["w-3"] * 3

    box2 = Box(); ctl2, con2 = _ctl(box2)
    _worker(box2, "w-1", "srv-a", capacity=10)
    group = [_cam(con2, f"ch{c}", NVR + str(c))["id"] for c in (1, 2, 3)]
    single = [_cam(con2, f"cam{c}", f"driverpack://acme/10.0.0.{80 + c}/ch/1")["id"] for c in (1, 2, 3)]
    ctl2.ensure_placed()
    _worker(box2, "w-2", "srv-b", capacity=10)
    moves = ctl2.rebalance(2, dead_band=0.1)
    assert [m[0] for m in moves] == single[:2] and {ctl2.where(c) for c in group} == {"w-1"}, moves
    moves = ctl2.rebalance(3, dead_band=0.0)                             # room in the budget for the whole group now
    assert {ctl2.where(c) for c in group} == {"w-2"} and len(moves) == 3, moves


def test_a_spec_that_asks_for_both_on_one_field_is_refused_at_load():
    """`group_by: cam` with `spread_by: cam` says "one worker" and "different
    servers" about the same pair of units. A spec that contradicts itself must
    not load — the alternative is a placement pass whose answer depends on the
    order two filters happen to run in."""
    d = {"name": "x", "unit": {"rows": "units", "id": "name",
                               "fields": {"name": {"type": "string", "required": True},
                                          "cam": {"type": "string"}}},
         "placement": {"capacity": {"from": "capacity", "default": 8},
                       "spread_by": "cam", "group_by": "cam"}}
    try:
        SubsystemSpec.from_dict(d)
        raise AssertionError("a spec that says both was accepted")
    except ValueError as e:
        assert "group_by" in str(e) and "spread_by" in str(e)

    d["placement"]["group_by"] = "kind"                    # different fields: not a contradiction
    assert SubsystemSpec.from_dict({**d, "unit": {**d["unit"], "fields": {**d["unit"]["fields"],
                                                                         "kind": {"type": "string"}}}}).group_by == "kind"


def test_a_device_with_no_picture_is_a_unit_like_any_other():
    """The row that made `kind` necessary: a door controller. It is an IP device
    integrated the same way, so it is held (one connection), placed, given an
    epoch and it writes events — everything a camera gets except the picture.

    And the whole of its special treatment is an ABSENCE: no fan-out published.
    Nothing else needs a branch, because everything else already asks the
    heartbeat rather than the row — the recorder looks for a holder with a
    `live_url` and does not find one."""
    from w2cplatform.console import holder_of
    from vms.worker import FakeActuator, VmsWorker
    from vms.config import SPEC as VMS_SPEC

    box = Box(); ctl, con = _ctl(box)
    cam = con.create_camera({"name": "lobby", "source": CAM})["id"]
    door = con.create_camera({"name": "front door", "source": "driverpack://acme/10.0.0.90/ch/1",
                              "kind": "io"})["id"]
    assert con.camera(cam)["kind"] == "video"              # the default keeps every older row meaning what it meant

    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall,
                  server="srv-a", env={}, archive_root=box.archive)
    _worker(box, "w-1", "srv-a")
    ctl.ensure_placed()
    w.reconcile_once(); w.heartbeat_once()

    st = {s["id"]: s for s in w.status()}
    assert st[cam]["live_url"] and "live_url" not in st[door]      # the absence, and it is the only difference
    assert st[door]["kind"] == "io" and st[door]["phase"] == "running"
    assert w.epochs[str(door)] >= 1                                 # held, fenced, its own epoch

    # a subscriber looking for something to watch finds the camera and not the door — no new check anywhere
    assert holder_of(box.objects, "vms/", cam, box.wall(), phase="running", field="live_url") is not None
    assert holder_of(box.objects, "vms/", door, box.wall(), phase="running", field="live_url") is None

    # …and it observes: an input change is an event in its own bucket, like any other event
    assert w.observe(door, "io.input", port=1, value="closed") is not None


class _Body:
    def __init__(self, payload: bytes, key: str = "k"):
        self.headers, self.rfile = {"Content-Length": str(len(payload)), "Idempotency-Key": key}, io.BytesIO(payload)   # a command is filed under a key (M17)


def _holder(box, server="srv-a", **devkw):
    """A worker with a real device open, so a command has something to reach."""
    from vms.worker import FakeActuator, FakeDevice, VmsWorker
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall,
                  server=server, env={}, archive_root=box.archive,
                  device_factory=lambda key: FakeDevice(key, channels=["1"], **devkw))
    return w


def test_a_command_is_a_row_performed_by_whoever_holds_the_device():
    """The other half of what a device is: until now a holder only observed.

    A relay pulse travels the connection that already exists, because there is
    only one — a second process opening the device to click a relay is the thing
    this subsystem is built not to do. So the command is a row, the holder
    performs it, and the row is cleared by the controller when the heartbeat
    says it was done."""
    from vms.jobs import clear_requests

    box = Box(); ctl, con = _ctl(box)
    door = con.create_camera({"name": "front door", "source": "driverpack://acme/10.0.0.90/ch/1",
                              "kind": "io"})["id"]
    _worker(box, "w-1", "srv-a"); ctl.ensure_placed()
    w = _holder(box, relays=2, ptz=True)
    w.reconcile_once()

    con.vars.put(SPEC.sub.request_key("r1"), {"unit": str(door), "action": "output", "port": "2",
                                              "state": "pulse", "pulse_ms": "500",
                                              "valid_until": str(box.wall() + 30)})
    done = w.requests()
    dev = w.devices["acme/10.0.0.90"]
    assert dev.did == [("output", 2, "pulse", 500)]        # it reached the device, on the open connection
    assert done[0]["request"] == "r1" and done[0]["action"] == "output"
    assert ("command" in [k for _, _, k in w.observed])    # …and what was done to a device is an event about it

    w.heartbeat_once()
    assert clear_requests(con) == 1                        # the worker says done; the CONSOLE removes the row —
    try:                                                   # a delete is a write, and the controller's token has no such grant
        ctl.vars.delete(SPEC.sub.request_key("r1"))
        raise AssertionError("the controller may not delete a request")
    except Forbidden:
        pass
    assert box.vars.list(SPEC.sub.requests_prefix()) == []

    # doing it again is not doing it twice: the row is gone, and the id is remembered while it is not
    assert w.requests() == [] and dev.did == [("output", 2, "pulse", 500)]


def test_a_device_that_does_not_come_back_from_a_command_does_not_hold_the_loop():
    """A command is a call into a driver, and the driver's call has no timeout of ours. A camera whose network went
    away with its session held kept `requests` — and the loop, the slot, the leases and the heartbeat of every
    camera of the worker — for as long as the vendor's SDK waited (the product's `Perform`, feedback BE). The call
    is made on a thread of its own: the pass waits 0.2 s for it; the camera next to it gets its command; no second
    call goes into the busy device; and after ten seconds the request is answered "the device did not answer"."""
    import threading
    import time
    box = Box(); ctl, con = _ctl(box)
    stuck = con.create_camera({"name": "stuck", "source": "driverpack://acme/10.0.0.90/ch/1"})["id"]
    fine = con.create_camera({"name": "fine", "source": "driverpack://acme/10.0.0.91/ch/1"})["id"]
    _worker(box, "w-1", "srv-a"); ctl.ensure_placed()
    w = _holder(box, ptz=True)
    w.reconcile_once()
    release, calls = threading.Event(), []
    dev = w.devices["acme/10.0.0.90"]
    dev.preset = lambda n: (calls.append(n), release.wait(30))         # the SDK call that does not return
    for rid, unit, n in (("r1", stuck, 1), ("r2", stuck, 2), ("r3", fine, 3)):
        con.vars.put(SPEC.sub.request_key(rid), {"unit": str(unit), "action": "preset", "n": str(n),
                                                 "valid_until": str(box.wall() + 60)})
    t0 = time.monotonic()
    done = w.requests()
    assert time.monotonic() - t0 < 2                                   # the pass did not wait for the device
    assert [d["request"] for d in done] == ["r3"] and w.devices["acme/10.0.0.91"].did == [("preset", 3, "", 0)]
    assert calls == [1]                                                # one call into the busy device, not two
    assert w.requests() == [] and calls == [1]
    box.clock.advance(11)                                              # PERFORM_TIMEOUT
    done = w.requests()
    assert done == [{"request": "r1", "unit": stuck, "error": "the device did not answer"}] and w.commands["refused"] == 1
    assert calls == [1]                                                # r2 still waits: the driver has not returned
    release.set()
    time.sleep(0.1)
    done = w.requests()                                                # the driver came back: the next in line goes
    assert [d["request"] for d in done] == ["r2"] and calls == [1, 2]
    assert w.commands == {"performed": 2, "refused": 1, "expired": 0, "unknown": 0}  # r1 is not counted twice for coming back late


def test_a_worker_that_may_no_longer_write_does_not_act_on_the_device():
    """The presence of a row was the whole check. A fenced instance, or one whose lease on the unit is lost, leaves
    the request for whoever holds the device now — a door is not opened by a worker that has been replaced."""
    box = Box(); ctl, con = _ctl(box)
    cam = con.create_camera({"name": "ptz", "source": "driverpack://acme/10.0.0.90/ch/1"})["id"]
    _worker(box, "w-1", "srv-a"); ctl.ensure_placed()
    w = _holder(box, ptz=True)
    w.reconcile_once()
    con.vars.put(SPEC.sub.request_key("r1"), {"unit": str(cam), "action": "preset", "n": "1",
                                              "valid_until": str(box.wall() + 60)})
    box.clock.advance(26)                                              # past ttl - margin: the lease is not confirmed
    assert w.requests() == [] and w.devices["acme/10.0.0.90"].did == []
    w.renew_leases()
    assert [d["request"] for d in w.requests()] == ["r1"]              # confirmed again: it acts


def test_a_command_that_missed_its_moment_expires_instead_of_firing():
    """The field a recording's request does not need. Footage fetched an hour
    late is still the footage; a door opened an hour late is an incident."""
    box = Box(); ctl, con = _ctl(box)
    door = con.create_camera({"name": "door", "source": "driverpack://acme/10.0.0.90/ch/1", "kind": "io"})["id"]
    _worker(box, "w-1", "srv-a"); ctl.ensure_placed()
    w = _holder(box, relays=1)
    w.reconcile_once()

    con.vars.put(SPEC.sub.request_key("late"), {"unit": str(door), "action": "output", "port": "1",
                                                "valid_until": str(box.wall() - 1)})
    done = w.requests()
    assert done == [{"request": "late", "unit": door, "expired": True}]
    assert w.devices["acme/10.0.0.90"].did == []           # never performed
    assert "late" in w.fetched                             # and cleared rather than retried for ever


def test_a_device_that_cannot_do_it_answers_and_is_not_asked_for_ever():
    """A refusal is an answer. An operator who asked a camera with no relays to
    open a door gets told, on the unit, and the row goes — the alternative is a
    request retried every pass until somebody notices the log."""
    box = Box(); ctl, con = _ctl(box)
    cam = con.create_camera({"name": "lobby", "source": "driverpack://acme/10.0.0.77/ch/1"})["id"]
    _worker(box, "w-1", "srv-a"); ctl.ensure_placed()
    w = _holder(box)                                       # no relays, no telemetry
    w.reconcile_once()

    con.vars.put(SPEC.sub.request_key("nope"), {"unit": str(cam), "action": "preset", "n": "3",
                                                "valid_until": str(box.wall() + 30)})
    done = w.requests()
    assert done[0]["request"] == "nope" and "telemetry" in done[0]["error"]
    assert ("command.failed" in [k for _, _, k in w.observed])
    assert "nope" in w.fetched


def test_the_console_files_a_command_and_refuses_the_ones_it_cannot():
    """The door an operator uses, and a `curl` away: `POST /requests`. The
    console does not open devices — it writes a row for the one process that
    has this device open."""
    from vms.console import vms_routes

    box = Box(); ctl, con = _ctl(box)
    door = con.create_camera({"name": "door", "source": "driverpack://acme/10.0.0.90/ch/1", "kind": "io"})["id"]
    route = vms_routes(None, None, con, None)

    status, body = route(_Body(json.dumps({"unit": f"vms/{door}", "action": "output", "port": 2,
                                           "state": "pulse", "pulse_ms": 500}).encode()),
                         "POST", "/requests", {})
    assert status == 202 and float(body["queued"]["valid_until"]) == box.wall() + 30   # thirty seconds by default
    assert box.vars.list(SPEC.sub.requests_prefix())

    for bad, why in (({"unit": "vms/999", "action": "output"}, "no such unit"),
                     ({"unit": f"vms/{door}", "action": "reboot"}, "unknown action"),
                     ({"unit": door, "action": "output"}, "bad unit")):            # a bare id: whose camera would it be?
        st, b = route(_Body(json.dumps(bad).encode(), key="bad"), "POST", "/requests", {})
        assert st in (400, 404) and b["error"] == why

    # an argument longer than a word: 400 at the door, the field named and not its value, no row written (the product's
    # cross-check of the eleventh review; the holder refuses such a row too, `VmsWorker.perform`)
    rows = len(box.vars.list(SPEC.sub.requests_prefix()))
    st, b = route(_Body(json.dumps({"unit": f"vms/{door}", "action": "output", "port": 1, "state": "x" * 5000}).encode(), key="long"),
                  "POST", "/requests", {})
    assert st == 400 and b["error"] == "too long" and "`state`" in b["detail"] and "xxxx" not in json.dumps(b)
    assert len(box.vars.list(SPEC.sub.requests_prefix())) == rows


def test_two_workers_on_one_box_open_their_own_doors():
    """The defect this exists for is not subtle once seen: a port in a TEMPLATE
    is a door only the first instance can open. `vmsworker@w-2` on the same box
    binds a taken socket, dies, and `Restart=always` raises it every two seconds
    until morning.

    Nothing ever needed the number: every subscriber reads the address out of
    the heartbeat. So the number may be zero, and what is published is what the
    OS gave."""
    from vms.config import port_of
    from vms.worker import FakeActuator, VmsWorker

    assert (port_of("auto", 8554), port_of("", 8554), port_of("9000", 8554)) == (0, 8554, 9000)

    box = Box(); ctl, con = _ctl(box)
    cam = con.create_camera({"name": "lobby", "source": CAM})["id"]
    _worker(box, "w-1", "srv-a"); ctl.ensure_placed()

    doors = []
    for name in ("w-1", "w-2"):
        w = VmsWorker(name, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall,
                      server="srv-a", archive_root=box.archive,
                      env={"PLAYBACK_PORT": "auto", "RTSP_PORT": "auto"})
        srv = w.serve_playback("127.0.0.1")               # both bind: neither was told a number
        doors.append((w, srv))
    (w1, s1), (w2, s2) = doors
    try:
        assert w1.playback_port and w2.playback_port and w1.playback_port != w2.playback_port
        assert w1.playback_port == s1.server_address[1]   # …and what it published is what it bound

        # the fan-out is the actuator's door, so the actuator is asked for its number rather than assumed
        w1.actuator.rtsp_port = 41111
        w1.reconcile_once()
        st = {x["id"]: x for x in w1.status()}
        assert st[cam]["live_url"] == f"rtsp://srv-a:41111/{cam}"
    finally:
        s1.shutdown(); s2.shutdown()

    # the default is untouched: a box with one worker publishes exactly what it always did
    plain = VmsWorker("w-3", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall,
                      server="srv-a", archive_root=box.archive, env={})
    assert (plain.rtsp_port, plain.playback_port) == (8554, 8083)


def test_two_clusters_of_one_on_one_bench_do_not_share_an_rtp_port():
    """A cluster of one camera (М12 Lesson 10) calls its camera 1, and so does
    every other. On a real camera each has its own loopback; on a bench where
    several such clusters share a machine, a constant base sends them all to
    20001 and a picture turns up in another cluster's window with no error. The
    base is the process's (`RTP_BASE`), so each cluster takes its own thousand."""
    from vms.worker import FakeActuator, VmsWorker, live_port

    assert (live_port(1), live_port(1, 21000), live_port("gate", 21000)) == (20001, 21001, 21000)

    ports = []
    for base in ("", "21000", "22000"):                # the default, then two more clusters of one
        box = Box()
        w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall,
                      server="srv-a", archive_root=box.archive, env={"RTP_BASE": base} if base else {})
        ports.append(w.enrich({"id": 1})["live_port"])
    assert ports == [20001, 21001, 22001]


def test_what_became_of_the_commands_is_counted_and_exported():
    """Performed, refused by the device, or arrived after its moment: each is counted in the holder's heartbeat,
    and the console sums them into `vms_commands_total`. A share of `expired` that grows is the road from an
    event to the holder getting longer than the requests live."""
    from w2cplatform.metrics import text as spec_metrics
    box = Box(); ctl, con = _ctl(box)
    door = con.create_camera({"name": "door", "source": "driverpack://acme/10.0.0.90/ch/1", "kind": "io"})["id"]
    _worker(box, "w-1", "srv-a"); ctl.ensure_placed()
    w = _holder(box, relays=1)
    w.reconcile_once()
    for rid, fields in (("ok", {"port": "1"}), ("bad", {"port": "9"}), ("late", {"port": "1", "valid_until": str(box.wall() - 1)})):
        con.vars.put(SPEC.sub.request_key(rid), {"unit": str(door), "action": "output",
                                                 "valid_until": str(box.wall() + 30), **fields})
    w.requests(); w.heartbeat_once()
    text = spec_metrics(ctl)
    assert 'vms_commands_total{outcome="performed"} 1' in text
    assert 'vms_commands_total{outcome="refused"} 1' in text and 'vms_commands_total{outcome="expired"} 1' in text
