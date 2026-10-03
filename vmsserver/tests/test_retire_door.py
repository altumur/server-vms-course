"""The operator's door to `retire`: a worker whose process will never come back, retired from the console.

`Controller.retire` was "the operator's statement that a slot is gone for good" and no operator could make it: the
controller has no port, and the console may not write `slots/*`. Now the console writes a request,
`<sub>/retire/<worker> {gen, by, at, why}` (`POST /workers/<w>/retire`, admin on the whole cluster, a journal line),
and the controller acts on it at the top of its next pass (`Controller.apply_retires`). Two guards, each asked by
both: a live slot — its lease runs, or its worker was heard from within 45 s — is not retired; and the request names
the slot's generation, so a process that took the name since is not retired by it. A retire closes the NAME and
moves what it listed; it does not give back what the worker held.
"""
import json

from w2cplatform.contract import Heartbeat, Slot
from w2cplatform.spec import SpecController
from vms.config import REC_SPEC, SPEC
from vms.controller import VmsController
from vms.worker import FakeActuator, VmsWorker
from tests.conftest import Box
from tests.test_console_gate import Tokens, _audit, _call, _console
from tests.test_slot_fence import _forget_garbled


def _site(box, cameras: int = 4):
    """Two workers that claimed their names (`w-1`, `w-2`), the controller with ITS token, and cameras placed by a
    pass — half on each worker."""
    ctl = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, capacity=4, wall=box.wall)
    ws = [VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, capacity=4) for _ in range(2)]
    for w in ws:
        w.heartbeat_once()
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    for i in range(1, cameras + 1):
        con.create_camera({"source": f"driverpack://file/{i}.mp4"})
    ctl.pass_once()
    assert sorted(w.name for w in ws) == ["w-1", "w-2"] and ctl.assignment("w-1").units and ctl.assignment("w-2").units
    return ctl, ws


def _silence(box, ws, dead: str = "w-1", seconds: float = 100):
    """`dead` stops: no renewal, no heartbeat. The other renews and heartbeats on."""
    box.wall.advance(seconds)
    for w in ws:
        if w.name != dead:
            assert w.renew_slot()
            w.heartbeat_once()


def _beat(box, worker: str):
    """Something answers under the name again — a heartbeat, nothing claimed."""
    box.objects.put(SPEC.sub.heartbeat_key(worker),
                    Heartbeat(worker, box.wall(), [], {"server": "srv-1", "capacity": 4, "headroom": 4}).to_bytes())


def _worker_row(base, worker: str) -> dict:
    servers = _call(base, "GET", "/servers")[1]["servers"]
    return next(w for s in servers.values() for w in s["workers"] if w["worker"] == worker)


def test_a_dead_worker_is_retired_from_the_console_on_the_next_pass_and_its_name_gets_no_cameras():
    """Refused while alive, 404 for a name nobody took; once silent, the console writes a REQUEST (not the slot), the
    next pass retires the slot and moves its cameras to the worker that is here; a heartbeat under the name again
    is given nothing, and the process that held it, should it wake, cannot renew it."""
    box = Box()
    ctl, ws = _site(box)
    on_w1 = list(ctl.assignment("w-1").units)
    _, _, _, srv, base = _console(box)
    try:
        st, out = _call(base, "POST", "/workers/w-1/retire", {"why": "burnt"}, user="anna")
        assert st == 409 and out["error"] == "alive" and "alive" in out["detail"], out
        assert _call(base, "POST", "/workers/w-9/retire", {})[0] == 404
        assert _call(base, "POST", "/workers/w%2C1/retire", {})[0] in (400, 404)
        assert box.vars.get("vms/retire/w-1")[0] is None                           # a refusal writes nothing

        _silence(box, ws)
        ctl.pass_once()
        assert sorted(ctl.assignment("w-1").units) == sorted(on_w1)                  # a crash is the scheduler's: they wait
        row = _worker_row(base, "w-1")
        assert row["retirable"] and row["gen"] == "1" and row["retire_refusal"] is None, row
        st, out = _call(base, "POST", "/workers/w-1/retire", {"why": "server burnt", "gen": row["gen"]}, user="anna")
        assert st == 202 and out["state"] == "requested" and sorted(out["units"]) == sorted(on_w1), out
        req = box.vars.get("vms/retire/w-1")[0]
        assert (req["gen"], req["by"], req["why"]) == ("1", "anna", "server burnt"), req
        assert not Slot.from_items("w-1", box.vars.get("vms/slots/w-1")[0]).released     # the console wrote a request, not the slot
        assert _worker_row(base, "w-1")["retire"]["why"] == "server burnt"

        rep = ctl.pass_once()
        assert rep["ok"] and rep["retired"] == ["w-1"] and rep["retire_refused"] == 0, rep
        assert Slot.from_items("w-1", box.vars.get("vms/slots/w-1")[0]).released
        assert box.vars.get("vms/retire/w-1")[0] is None                           # done: the request is gone
        assert ctl.assignment("w-1").units == [] and all(ctl.where(int(c)) == "w-2" for c in on_w1)
        assert "slot w-1 released" in ctl.placement(int(on_w1[0])).reason

        _beat(box, "w-1")                                                          # something answers under the name again
        ctl.pass_once()
        assert ctl.assignment("w-1").units == []                                   # a retired name is no place for a camera
        assert not ws[0].renew_slot()                                              # the old process woke: the name is not its
        st, out = _call(base, "POST", "/workers/w-1/retire", {})
        assert st == 409 and out["error"] == "released", out
        assert ("worker.retire.requested", "anna") in _audit(box)
    finally:
        srv.shutdown()


def test_a_live_slot_is_refused_by_the_controller_when_the_console_was_bypassed():
    """A request written straight into the store, past the console's guard, about a worker that is alive: the pass
    retires nothing, counts it refused and writes why into the row. A worker heard from AFTER the console wrote is the
    same case — its lease lapsed, its heartbeat fresh: refused. Once it has been silent long enough, it is retired."""
    box = Box()
    ctl, ws = _site(box)
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    box.vars.as_writer("console", SPEC.acl_console()).put("vms/retire/w-1", {"gen": "1", "by": "script", "at": "0", "why": ""})
    rep = ctl.pass_once()
    assert rep["retired"] == [] and rep["retire_refused"] == 1, rep
    assert not Slot.from_items("w-1", box.vars.get("vms/slots/w-1")[0]).released
    assert "alive" in box.vars.get("vms/retire/w-1")[0]["refused"]

    _silence(box, ws)                                                              # w-1 dies…
    assert con.request_retire("w-1", "anna", "burnt")["gen"] == "1"                 # …the console asks, rightly
    _beat(box, "w-1")                                                              # …and before the pass it is heard again
    rep = ctl.pass_once()
    assert rep["retired"] == [] and not Slot.from_items("w-1", box.vars.get("vms/slots/w-1")[0]).released
    assert "alive" in box.vars.get("vms/retire/w-1")[0]["refused"]
    idx = box.vars.get("vms/retire/w-1")[1]
    ctl.pass_once()
    assert box.vars.get("vms/retire/w-1")[1] == idx                               # the same reason is not written every pass

    box.wall.advance(60); ws[1].renew_slot(); ws[1].heartbeat_once()              # silent for good now
    assert ctl.pass_once()["retired"] == ["w-1"]


def test_a_request_whose_generation_is_older_than_the_slots_is_refused():
    """The console asked about generation 1. Before the pass a new process took the name (generation 2) — and died in
    its turn. The old request does not retire it: refused, with why, and it stays refused. The console, given the
    generation the page showed, refuses the same thing before it writes."""
    box = Box()
    ctl, ws = _site(box)
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    _silence(box, ws)
    con.request_retire("w-1", "anna", "burnt")
    VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, capacity=4)   # claims the name
    assert Slot.from_items("w-1", box.vars.get("vms/slots/w-1")[0]).gen == 2
    _silence(box, ws)                                                              # the successor dies too
    for _ in range(2):
        rep = ctl.pass_once()
        assert rep["retired"] == [] and rep["retire_refused"] == 1, rep
    assert not Slot.from_items("w-1", box.vars.get("vms/slots/w-1")[0]).released
    assert "generation 1" in box.vars.get("vms/retire/w-1")[0]["refused"]

    _, _, _, srv, base = _console(box)
    try:
        st, out = _call(base, "POST", "/workers/w-1/retire", {"why": "burnt", "gen": "1"})
        assert st == 409 and out["error"] == "generation", out
        st, out = _call(base, "POST", "/workers/w-1/retire", {"why": "burnt", "gen": 2})
        assert st == 202 and out["gen"] == "2", out
    finally:
        srv.shutdown()
    assert ctl.pass_once()["retired"] == ["w-1"]                                   # asked about the right one: done


def test_retiring_a_worker_needs_admin_on_the_whole_cluster():
    """Every camera of the worker moves: a grant on one camera, a grant by label, a viewer — 403, nothing written. The
    recorder's console the same, under `/rec/`."""
    box = Box()
    ctl, ws = _site(box)
    _silence(box, ws)
    access = Tokens({"admin": [("admin", None, ())], "cam-admin": [("admin", "1", ())],
                     "guard": [("admin", None, ("vlan:a",))], "viewer": [("view", None, ())]})
    _, _, _, srv, base = _console(box, access)
    try:
        for who in ("cam-admin", "guard", "viewer"):
            assert _call(base, "POST", "/workers/w-1/retire", {"why": "x"}, token=who)[0] == 403, who
            assert _call(base, "POST", "/rec/workers/r-1/retire", {"why": "x"}, token=who)[0] == 403, who
        assert box.vars.get("vms/retire/w-1")[0] is None
        assert _call(base, "POST", "/workers/w-1/retire", {"why": "x"}, token="admin")[0] == 202
    finally:
        srv.shutdown()


def test_a_retire_request_survives_a_controller_restart():
    """The request is a row, not a call: written while the controller was down — or refused by one controller and
    then the process restarted — it is read by the next one, from the store."""
    box = Box()
    ctl, ws = _site(box)
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    box.wall.advance(10)
    box.vars.as_writer("console", SPEC.acl_console()).put("vms/retire/w-1", {"gen": "1", "by": "anna", "at": "0", "why": ""})
    assert ctl.pass_once()["retire_refused"] == 1                                 # alive yet: refused, kept
    del ctl                                                                       # the controller stops…
    _silence(box, ws)
    con.request_retire("w-1", "anna", "burnt")                                    # …the console asks again meanwhile
    fresh = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, capacity=4, wall=box.wall)
    assert fresh.pass_once()["retired"] == ["w-1"]                                # …and the next one reads it
    assert fresh.assignment("w-1").units == []


def test_a_retired_recorder_keeps_the_volume_it_held_and_the_answer_names_it():
    """A retire gives back no place: a recorder's local disk is held through a silence on purpose, and when the box
    burnt the disk went with it — the administrator withdraws the volume. The console's answer names it; the pass
    retires the slot and leaves the hold's row as it was."""
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("reccontroller", REC_SPEC.acl_controller()), box.objects, wall=box.wall)
    sub, now = REC_SPEC.sub, box.wall()
    box.vars.put(sub.slot_key("r-1"), Slot("r-1", "box-a:11:aa", now - 100, False, 3).to_items())
    box.vars.put(sub.hold_key("disk"), Slot("disk", "box-a:11:aa", now - 100, False, 1, "r-1").to_items())
    box.vars.put(sub.hold_key("nas"), Slot("nas", "box-b:12:bb", now + 30, False, 1, "r-2").to_items())
    hold_before = box.vars.get(sub.hold_key("disk"))
    _, _, _, srv, base = _console(box)
    try:
        st, out = _call(base, "POST", "/rec/workers/r-1/retire", {"why": "box burnt"}, user="anna")
        assert st == 202 and out["holds"] == ["disk"] and "disk" in out["note"], out
    finally:
        srv.shutdown()
    rep = rec.pass_once()
    assert rep["retired"] == ["r-1"], rep
    assert Slot.from_items("r-1", box.vars.get(sub.slot_key("r-1"))[0]).released
    assert box.vars.get(sub.hold_key("disk")) == hold_before                       # not given back: not even touched
    assert rec.holds_of("r-1") == ["disk"]


def test_a_slot_whose_row_does_not_parse_is_retired_through_the_door_too():
    """The slot an operator most wants gone is one whose row is garbled (`test_garbled_rows`). No lease can be read, so
    the heartbeat decides; the request names no generation, and the pass writes the row whole: released, nobody's."""
    box = Box()
    ctl, ws = _site(box)
    box.vars.put("vms/slots/w-9", {"holder": "somebody", "until": "soon", "released": "false", "gen": "1"})
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    assert con.request_retire("w-9", "anna", "garbled")["gen"] == ""
    assert ctl.pass_once()["retired"] == ["w-9"]
    s = Slot.from_items("w-9", box.vars.get("vms/slots/w-9")[0])
    assert s.released and s.holder == ""
    _forget_garbled()


def test_the_console_writes_the_request_and_never_the_slot():
    """One writer per family: the console's token covers `<sub>/retire/*` and no slot; the controller's covers both —
    it reads the request, deletes it when done, and writes why into one it refused."""
    for spec in (SPEC, REC_SPEC):
        con, ctl = spec.acl_console(), spec.acl_controller()
        assert f"{spec.name}/retire/*" in con and f"{spec.name}/slots/*" not in con
        assert f"{spec.name}/retire/*" in ctl and f"{spec.name}/slots/*" in ctl
    assert json.dumps(SPEC.sub.retire_key("w-1")) == '"vms/retire/w-1"'
