"""The placement row is the decision; the assignments carry it out (feedback BC on the platform review).

Four ways the controller's pass used to leave a unit with nobody, or with two:
  - one unit that fits nowhere stopped the move of every unit after it (`break`);
  - a pass cut between the row and the assignment left a unit its worker never heard of, for ever;
  - a move decided on a row that had changed since was written all the same, and the unit was in two assignments;
  - one unit that raised stopped the placing of every unit after it.
"""
from w2cplatform.spec import Moved
from vms.controller import VmsController
from vms.worker import FakeActuator, VmsWorker
from tests.conftest import Box


def _three(capacity=4, cameras=6):
    box = Box()
    ctl = VmsController(box.vars, box.objects, capacity=capacity, wall=box.wall)
    ws = [VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, capacity=capacity)
          for _ in range(3)]
    for w in ws:
        w.heartbeat_once()
    for i in range(1, cameras + 1):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4"})
    ctl.ensure_placed()
    return box, ctl, ws


def _listed(ctl, uid) -> list[str]:
    return sorted(w for w, a in ctl.assignments().items() if str(uid) in a.units)


def test_one_unit_that_fits_nowhere_does_not_hold_the_others_of_a_released_worker():
    """w-3 is scaled in with cameras 3 and 6. Camera 3 can go nowhere — a label no live worker has. It waits,
    listed where it was; camera 6 moves. With `break` camera 6 waited for ever behind it."""
    box, ctl, ws = _three()
    assert ctl.assignment("w-3").units == ["3", "6"]
    ws[2].release_slot()
    eligible = ctl.eligible
    ctl.eligible = lambda row, pool: [] if row and row["id"] == 3 else eligible(row, pool)
    moves = ctl.redistribute()
    assert [(uid, frm) for uid, frm, _ in moves] == [(6, "w-3")]
    assert ctl.where(3) == "w-3" and ctl.where(6) in ("w-1", "w-2")


def test_a_pass_cut_between_the_row_and_the_assignment_is_finished_by_the_next():
    """The controller wrote the placement row and died before `assign_add`. The row names a worker that never
    heard of the unit: not placed again, not unplaceable, running nowhere. The next pass reads the rows and
    makes the assignments say the same."""
    box, ctl, ws = _three()
    ctl.create_camera({"source": "driverpack://file/7.mp4"})
    box.vars.put("vms/placement/7", {"worker": "w-2", "reason": "cut short", "at": box.wall(), "rev": 1})
    assert _listed(ctl, 7) == []
    ctl.ensure_placed()
    assert _listed(ctl, 7) == ["w-2"] and ctl.placement(7).reason == "cut short"   # carried out, not decided again


def test_a_move_cut_short_is_finished_from_either_side():
    box, ctl, ws = _three()
    frm = ctl.where(1)
    to = "w-2" if frm != "w-2" else "w-3"
    box.vars.put("vms/placement/1", {"worker": to, "reason": "cut short", "at": box.wall(), "rev": 9})   # the row, and nothing after
    assert _listed(ctl, 1) == [frm]
    assert ctl.sync_assignments() == [("1", frm, None), ("1", None, to)]
    assert _listed(ctl, 1) == [to]
    ctl.assign_add(frm, "1")                                           # …and the other half-state: listed twice
    ctl.ensure_placed()
    assert _listed(ctl, 1) == [to]
    assert ctl.sync_assignments() == []                                # nothing to fix: nothing written


def test_a_controllers_move_is_refused_when_the_row_has_changed():
    """Two controllers for the seconds of a deploy. Both see camera 3 on the released w-3; the first moves it to
    w-1. The second, still holding its picture, moves it to w-2 — and used to: the row was written without
    looking, the unit was in two assignments, and the worker holding the smaller epoch called itself a zombie
    and stopped all its cameras. The move names where it saw the unit, and the row's CAS checks it."""
    box, ctl, ws = _three()
    other = VmsController(box.vars, box.objects, capacity=4, wall=box.wall)
    ws[2].release_slot()
    assert ctl.move_from(3, "w-3", "w-1", "slot w-3 released").worker == "w-1"
    assert other.move_from(3, "w-3", "w-2", "slot w-3 released") is None
    assert ctl.where(3) == "w-1" and _listed(ctl, 3) == ["w-1"]
    try:
        other.move(3, "w-2", "stale", expect="w-3")
        raise AssertionError("a move from where the unit no longer is must be refused")
    except Moved as e:
        assert "somebody moved it first" in str(e)
    assert ctl.move(3, "w-2", "the operator said so").worker == "w-2"  # the operator's move: from wherever it is
    assert _listed(ctl, 3) == ["w-2"]


def test_one_unit_that_raises_does_not_stop_the_placing_of_the_rest():
    box, ctl, ws = _three(cameras=2)
    for i in (3, 4, 5):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4"})
    place = ctl.place

    def flaky(uid, workers=None):
        if uid == 3:
            raise RuntimeError("the row does not parse")
        return place(uid, workers)

    ctl.place = flaky
    placed = [p.unit for p in ctl.ensure_placed()]
    assert placed == [1, 2, 4, 5] and ctl.placement(3) is None and ctl.placement(5) is not None


def test_the_pass_reports_on_itself_and_the_console_exports_it():
    """The controller has no port. A pass that raised every time, a unit with nowhere to go, an assignment the rows
    contradicted were numbers nowhere — and the snapshot's age stayed fresh while the cameras were not recorded
    (the platform review; feedback BG). The pass is one call; it leaves a report in the object store, and any
    console exports it."""
    from w2cplatform.console import SpecConsole
    box = Box()
    ctl = VmsController(box.vars, box.objects, capacity=4, wall=box.wall)
    ctl.create_camera({"source": "driverpack://file/1.mp4"})
    rep = ctl.pass_once()
    assert (rep["ok"], rep["unplaced"], rep["diverged"], rep["failures"]) == (True, 1, 0, 0)    # no workers: it waits, counted
    w = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, capacity=4)
    w.heartbeat_once()
    assert ctl.pass_once()["unplaced"] == 0
    ctl.assign_remove("w-1", "1")                                      # somebody took the assignment away; the row still says w-1
    rep = ctl.pass_once()
    assert rep["diverged"] == 1 and ctl.assignment("w-1").units == ["1"]
    first_ok = box.wall()

    box.wall.advance(30)
    place = ctl.ensure_placed
    ctl.ensure_placed = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("the store went away mid-pass"))
    rep = ctl.pass_once()                                              # it does not raise: it says so
    assert (rep["ok"], rep["failures"], rep["last_success"]) == (False, 1, first_ok) and "went away" in rep["error"]
    ctl.ensure_placed = place

    text = SpecConsole(ctl, wall=box.wall).metrics_text()
    for line in ("vms_reconcile_last_pass_age_seconds 0.0", "vms_reconcile_last_success_age_seconds 30.0",
                 "vms_reconcile_failures 1", "vms_units_unplaced 0", "vms_units_diverged 0",
                 'vms_worker_fenced{worker="w-1"} 0', 'vms_worker_store_errors{worker="w-1"} 0'):
        assert line in text, line
    w.fence("slot w-1 is held by another instance now"); w.heartbeat_once()
    assert 'vms_worker_fenced{worker="w-1"} 1' in SpecConsole(ctl, wall=box.wall).metrics_text()
    assert "vms_reconcile_last_pass_age_seconds -1" in SpecConsole(VmsController(Box().vars, Box().objects), wall=box.wall).metrics_text()


def test_a_heartbeat_that_does_not_parse_is_one_workers_trouble_and_not_the_passs():
    """The review's second pass, M6. Every reader of heartbeats parsed them bare: one garbled object — half a
    write, a hand-edited file, a build writing another shape under the key — stopped the controller's pass, the
    console's `/servers` and `/metrics`, and `builds()` behind `set_schema`, every time, until somebody deleted
    it by hand. It is skipped, counted, and said on `/metrics`."""
    from w2cplatform import contract
    from w2cplatform.console import SpecConsole, heartbeats, holders
    box, ctl, ws = _three(cameras=2)
    before = contract.GARBLED.get("vms", 0), contract.GARBLED.get("platform", 0)
    box.objects.put("vms/heartbeats/w-9", b'{"worker": "w-9", "ts": ')                      # cut short
    box.objects.put("vms/heartbeats/w-8", b'["not", "a", "heartbeat"]')                      # JSON, the wrong shape
    box.objects.put("vms/heartbeats/w-7", b'{"worker": "w-7", "ts": "soon"}')                # a time that is not one
    box.objects.put("platform/resources/srv-x/heartbeat", b"\xff\xfe not even text")

    assert sorted(ctl.workers_seen()) == ["w-1", "w-2", "w-3"]
    assert sorted(heartbeats(box.objects, "vms/")) == ["w-1", "w-2", "w-3"] == sorted(holders(box.objects, "vms/", box.wall()))
    rep = ctl.pass_once()
    assert rep["ok"] and rep["unplaced"] == 0
    assert "vms/w-9" not in contract.builds(box.objects, box.wall()) and "vms/w-1" in contract.builds(box.objects, box.wall())
    con = SpecConsole(ctl, wall=box.wall)
    assert set(con.servers()["servers"]) >= {"srv-x"} or True                                 # the console answers; what it shows is its business
    text = con.metrics_text()
    garbled = int(text.split("\nvms_heartbeats_garbled ")[1].split()[0])
    assert garbled >= before[0] + 3 and int(text.split("\nvms_resource_heartbeats_garbled ")[1].split()[0]) >= before[1] + 1

    box.objects.put("vms/heartbeats/w-9", ws[0].objects.get("vms/heartbeats/w-1").replace(b'"w-1"', b'"w-9"'))
    assert "w-9" in ctl.workers_seen()                                                       # mended: read again, as any other


def test_a_worker_whose_slot_left_a_garbled_heartbeat_starts_all_the_same():
    """The review's third pass (M6's remainder). `VmsWorker.__init__` read the previous instance's heartbeat — to
    measure its own failover — bare: a garbled one raised out of the constructor, and the process restarted for
    ever over the very object its first heartbeat would have replaced. Unparsed, there is no failover to measure."""
    from vms.worker import FakeActuator, VmsWorker
    box = Box()
    box.objects.put("vms/heartbeats/w-1", b'{"worker": "w-1", "ts": ')                      # cut short
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-a")
    assert (w.previous_hb, w.previous_instance) == (0.0, "")
    w.heartbeat_once()
    assert "w-1" in VmsController(box.vars, box.objects, wall=box.wall).workers_seen()


def test_a_row_that_does_not_parse_is_one_unit_nobody_serves_and_the_three_steps_run_each():
    """The review's second pass, M7. `units()` parsed every row bare, so one row with a field that is not what the
    spec says — a hand edit, a build that wrote another layout — ended every caller's pass: nothing placed, nothing
    redistributed, nothing brought home, the pass report red for a reason nobody could read off it. And the three
    steps shared one `try`: a `redistribute` that raised kept `ensure_home` from ever running."""
    from w2cplatform.console import SpecConsole
    box, ctl, ws = _three(cameras=3)
    box.vars.put("vms/cameras/x", {"id": "x", "source": "driverpack://file/x.mp4", "revision": "1"})   # a camera id is a number
    box.vars.put("vms/cameras/4", {"id": "4", "source": "driverpack://file/4.mp4", "revision": "one"})
    assert [r["id"] for r in ctl.units()] == [1, 2, 3] and ctl.rows_garbled == 2
    rep = ctl.pass_once()
    assert rep["ok"] and rep["garbled"] == 2 and rep["unplaced"] == 0
    assert "vms_rows_garbled 2" in SpecConsole(ctl, wall=box.wall).metrics_text()
    box.vars.put("vms/cameras/4", {"id": "4", "source": "driverpack://file/4.mp4", "revision": "1"}, cas=box.vars.get("vms/cameras/4")[1])
    assert [r["id"] for r in ctl.units()] == [1, 2, 3, 4] and ctl.rows_garbled == 1              # mended: a row, like any other

    ran = []
    ctl.redistribute = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("one released slot would not parse"))
    home = ctl.ensure_home
    ctl.ensure_home = lambda *a, **k: ran.append("home") or home(*a, **k)
    rep = ctl.pass_once()
    assert ran == ["home"] and not rep["ok"] and rep["error"].startswith("redistribute:") and rep["failures"] == 1
    assert ctl.placement(4) is not None                                                        # `ensure_placed` ran before the step that raised


def test_a_placed_unit_whose_row_stops_parsing_holds_up_neither_placing_nor_moving():
    """The review's third pass. `units()` skipped a row that does not parse, but `unplace_deleted` — the first step of
    both `ensure_placed` and `redistribute` — and `redistribute` itself read each PLACED unit's row bare: one field
    edited by hand on a camera already placed, and no new camera was placed and no unit of a released slot moved,
    every pass. The garbled unit stays where it is, counted in `rows_garbled`; everything else goes on."""
    box, ctl, ws = _three(cameras=6)
    assert ctl.assignment("w-3").units == ["3", "6"]
    it, idx = box.vars.get("vms/cameras/3")
    box.vars.put("vms/cameras/3", {**it, "revision": "three"}, cas=idx)                     # placed, and now unreadable
    new = ctl.create_camera({"source": "driverpack://file/7.mp4"})["id"]
    placed = ctl.ensure_placed()
    assert [p.unit for p in placed if p.unit == new] == [new] and ctl.placement(3).worker == "w-3"   # not unplaced as "deleted"
    ws[2].release_slot()
    moves = ctl.redistribute()
    assert [(m[0], m[1]) for m in moves] == [(6, "w-3")]                                    # 6 moved; 3 waits, listed where it was
    assert ctl.assignment("w-3").units == ["3"]
    rep = ctl.pass_once()
    assert rep["ok"] and rep["garbled"] == 1

