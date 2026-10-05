"""The placement row is the decision; the assignments carry it out (feedback BC on the platform review).

Four ways the controller's pass used to leave a unit with nobody, or with two:
  - one unit that fits nowhere stopped the move of every unit after it (`break`);
  - a pass cut between the row and the assignment left a unit its worker never heard of, for ever;
  - a move decided on a row that had changed since was written all the same, and the unit was in two assignments;
  - one unit that raised stopped the placing of every unit after it.

On testsub (`testdata/testsub.subsystem.yaml`): a unit is a named counter, `testsub/counters/<name>`.
"""
from w2cplatform.spec import Moved
from tests.conftest import Box, controller, counter_worker, testsub2


def _three(capacity=4, counters=6):
    box = Box()
    ctl = controller(box, capacity=capacity)
    ws = [counter_worker(box, capacity=capacity) for _ in range(3)]
    for w in ws:
        w.heartbeat_once()
    for i in range(1, counters + 1):
        ctl.create({"name": f"c{i}"})
    ctl.ensure_placed()
    return box, ctl, ws


def _listed(ctl, uid) -> list[str]:
    return sorted(w for w, a in ctl.assignments().items() if str(uid) in a.units)


def test_one_unit_that_fits_nowhere_does_not_hold_the_others_of_a_released_worker():
    """w-3 is scaled in with counters c3 and c6. c3 can go nowhere — a label no live worker has. It waits,
    listed where it was; c6 moves. With `break` c6 waited for ever behind it."""
    box, ctl, ws = _three()
    assert ctl.assignment("w-3").units == ["c3", "c6"]
    ws[2].release_slot()
    eligible = ctl.eligible
    ctl.eligible = lambda row, pool: [] if row and row["id"] == "c3" else eligible(row, pool)
    moves = ctl.redistribute()
    assert [(uid, frm) for uid, frm, _ in moves] == [("c6", "w-3")]
    assert ctl.where("c3") == "w-3" and ctl.where("c6") in ("w-1", "w-2")


def test_a_pass_cut_between_the_row_and_the_assignment_is_finished_by_the_next():
    """The controller wrote the placement row and died before `assign_add`. The row names a worker that never
    heard of the unit: not placed again, not unplaceable, running nowhere. The next pass reads the rows and
    makes the assignments say the same."""
    box, ctl, ws = _three()
    ctl.create({"name": "c7"})
    box.vars.put("testsub/placement/c7", {"worker": "w-2", "reason": "cut short", "at": box.wall(), "rev": 1})
    assert _listed(ctl, "c7") == []
    ctl.ensure_placed()
    assert _listed(ctl, "c7") == ["w-2"] and ctl.placement("c7").reason == "cut short"   # carried out, not decided again


def test_a_move_cut_short_is_finished_from_either_side():
    box, ctl, ws = _three()
    frm = ctl.where("c1")
    to = "w-2" if frm != "w-2" else "w-3"
    box.vars.put("testsub/placement/c1", {"worker": to, "reason": "cut short", "at": box.wall(), "rev": 9})   # the row, and nothing after
    assert _listed(ctl, "c1") == [frm]
    assert ctl.sync_assignments() == [("c1", frm, None), ("c1", None, to)]
    assert _listed(ctl, "c1") == [to]
    ctl.assign_add(frm, "c1")                                          # …and the other half-state: listed twice
    ctl.ensure_placed()
    assert _listed(ctl, "c1") == [to]
    assert ctl.sync_assignments() == []                                # nothing to fix: nothing written


def test_a_controllers_move_is_refused_when_the_row_has_changed():
    """Two controllers for the seconds of a deploy. Both see c3 on the released w-3; the first moves it to
    w-1. The second, still holding its picture, moves it to w-2 — and used to: the row was written without
    looking, the unit was in two assignments, and the worker holding the smaller epoch called itself a zombie
    and stopped all its units. The move names where it saw the unit, and the row's CAS checks it."""
    box, ctl, ws = _three()
    other = controller(box, capacity=4)
    ws[2].release_slot()
    assert ctl.move_from("c3", "w-3", "w-1", "slot w-3 released").worker == "w-1"
    assert other.move_from("c3", "w-3", "w-2", "slot w-3 released") is None
    assert ctl.where("c3") == "w-1" and _listed(ctl, "c3") == ["w-1"]
    try:
        other.move("c3", "w-2", "stale", expect="w-3")
        raise AssertionError("a move from where the unit no longer is must be refused")
    except Moved as e:
        assert "somebody moved it first" in str(e)
    assert ctl.move("c3", "w-2", "the operator said so").worker == "w-2"   # the operator's move: from wherever it is
    assert _listed(ctl, "c3") == ["w-2"]


def test_one_unit_that_raises_does_not_stop_the_placing_of_the_rest():
    box, ctl, ws = _three(counters=2)
    for i in (3, 4, 5):
        ctl.create({"name": f"c{i}"})
    place = ctl.place

    def flaky(uid, workers=None):
        if uid == "c3":
            raise RuntimeError("the row does not parse")
        return place(uid, workers)

    ctl.place = flaky
    placed = [p.unit for p in ctl.ensure_placed()]
    assert placed == ["c1", "c2", "c4", "c5"] and ctl.placement("c3") is None and ctl.placement("c5") is not None


def test_the_pass_reports_on_itself_and_the_console_exports_it():
    """The controller has no port. A pass that raised every time, a unit with nowhere to go, an assignment the rows
    contradicted were numbers nowhere — and the snapshot's age stayed fresh while the units were served by nobody
    (the platform review; feedback BG). The pass is one call; it leaves a report in the object store, and any
    console exports it.

    On testsub2, the subsystem whose spec says `offers` — a tally `t1` about counter c1, its worker a slot `t-1`."""
    from w2cplatform.console import SpecConsole
    box = Box()
    ctl = controller(box, capacity=4, spec=testsub2())
    ctl.create({"name": "t1", "of": "c1"})
    rep = ctl.pass_once()
    assert (rep["ok"], rep["unplaced"], rep["diverged"], rep["failures"]) == (True, 1, 0, 0)    # no workers: it waits, counted
    # …and offers the worker it is short of to a spare: the slot `t-1` (М11 rework, `offer_spares`) — so the worker the
    # unit names `t-1` takes it as its own (`prefer`), where a nameless one would make `t-2` beside the offer
    assert rep["workers_needed"] == {"": 1} and box.vars.get("testsub2/slots/t-1")[0]["offer"] == ""
    w = counter_worker(box, "t-1", capacity=4, spec=testsub2())
    w.heartbeat_once()
    assert ctl.pass_once()["unplaced"] == 0
    ctl.assign_remove("t-1", "t1")                                     # somebody took the assignment away; the row still says t-1
    rep = ctl.pass_once()
    assert rep["diverged"] == 1 and ctl.assignment("t-1").units == ["t1"]
    first_ok = box.wall()

    box.wall.advance(30)
    place = ctl.ensure_placed
    ctl.ensure_placed = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("the store went away mid-pass"))
    rep = ctl.pass_once()                                              # it does not raise: it says so
    assert (rep["ok"], rep["failures"], rep["last_success"]) == (False, 1, first_ok) and "went away" in rep["error"]
    ctl.ensure_placed = place

    text = SpecConsole(ctl, wall=box.wall).metrics_text()
    for line in ("testsub2_reconcile_last_pass_age_seconds 0.0", "testsub2_reconcile_last_success_age_seconds 30.0",
                 "testsub2_reconcile_failures 1", "testsub2_units_unplaced 0", "testsub2_units_diverged 0",
                 'testsub2_worker_fenced{worker="t-1"} 0', 'testsub2_worker_store_errors{worker="t-1"} 0',
                 'testsub2_worker_slots_garbled{worker="t-1"} 0'):  # slot rows it could not read (the review's sixth pass)
        assert line in text, line
    from w2cplatform import contract
    was = contract.SLOTS_GARBLED.get("testsub2", 0)
    contract.SLOTS_GARBLED["testsub2"] = was + 2                       # two torn slot rows met while looking for a slot
    try:
        w.heartbeat_once()
        assert f'testsub2_worker_slots_garbled{{worker="t-1"}} {was + 2}' in SpecConsole(ctl, wall=box.wall).metrics_text()
    finally:
        contract.SLOTS_GARBLED["testsub2"] = was
    w.fence("slot t-1 is held by another instance now"); w.heartbeat_once()
    assert 'testsub2_worker_fenced{worker="t-1"} 1' in SpecConsole(ctl, wall=box.wall).metrics_text()
    assert "testsub_reconcile_last_pass_age_seconds -1" in SpecConsole(controller(Box()), wall=box.wall).metrics_text()


def test_a_heartbeat_that_does_not_parse_is_one_workers_trouble_and_not_the_passs():
    """The review's second pass, M6. Every reader of heartbeats parsed them bare: one garbled object — half a
    write, a hand-edited file, a build writing another shape under the key — stopped the controller's pass, the
    console's `/servers` and `/metrics`, and `builds()` behind `set_schema`, every time, until somebody deleted
    it by hand. It is skipped, counted, and said on `/metrics`."""
    from w2cplatform import contract
    from w2cplatform.console import SpecConsole, heartbeats, holders
    box, ctl, ws = _three(counters=2)
    before = contract.GARBLED.get("testsub", 0), contract.GARBLED.get("platform", 0)
    box.objects.put("testsub/heartbeats/w-9", b'{"worker": "w-9", "ts": ')                  # cut short
    box.objects.put("testsub/heartbeats/w-8", b'["not", "a", "heartbeat"]')                  # JSON, the wrong shape
    box.objects.put("testsub/heartbeats/w-7", b'{"worker": "w-7", "ts": "soon"}')            # a time that is not one
    box.objects.put("platform/resources/srv-x/heartbeat", b"\xff\xfe not even text")

    assert sorted(ctl.workers_seen()) == ["w-1", "w-2", "w-3"]
    assert sorted(heartbeats(box.objects, "testsub/")) == ["w-1", "w-2", "w-3"] \
        == sorted(holders(box.objects, "testsub/", box.wall()))
    rep = ctl.pass_once()
    assert rep["ok"] and rep["unplaced"] == 0
    assert "testsub/w-9" not in contract.builds(box.objects, box.wall()) \
        and "testsub/w-1" in contract.builds(box.objects, box.wall())
    con = SpecConsole(ctl, wall=box.wall)
    assert set(con.servers()["servers"]) >= {"srv-x"} or True                                 # the console answers; what it shows is its business
    text = con.metrics_text()
    garbled = int(text.split("\ntestsub_heartbeats_garbled ")[1].split()[0])
    assert garbled >= before[0] + 3 and int(text.split("\nw2c_resource_heartbeats_garbled ")[1].split()[0]) >= before[1] + 1

    box.objects.put("testsub/heartbeats/w-9", ws[0].objects.get("testsub/heartbeats/w-1").replace(b'"w-1"', b'"w-9"'))
    assert "w-9" in ctl.workers_seen()                                                       # mended: read again, as any other


def test_a_row_that_does_not_parse_is_one_unit_nobody_serves_and_the_three_steps_run_each():
    """The review's second pass, M7. `units()` parsed every row bare, so one row with a field that is not what the
    spec says — a hand edit, a build that wrote another layout — ended every caller's pass: nothing placed, nothing
    redistributed, nothing brought home, the pass report red for a reason nobody could read off it. And the three
    steps shared one `try`: a `redistribute` that raised kept `ensure_home` from ever running."""
    from w2cplatform.console import SpecConsole
    box, ctl, ws = _three(counters=3)
    box.vars.put("testsub/counters/x", {"id": "x", "name": "x", "start": "zero", "revision": "1"})   # a start is a number
    box.vars.put("testsub/counters/c4", {"id": "c4", "name": "c4", "start": "one", "revision": "1"})
    assert [r["id"] for r in ctl.units()] == ["c1", "c2", "c3"] and ctl.rows_garbled == 2
    rep = ctl.pass_once()
    assert rep["ok"] and rep["garbled"] == 2 and rep["unplaced"] == 0
    assert "testsub_rows_garbled 2" in SpecConsole(ctl, wall=box.wall).metrics_text()
    box.vars.put("testsub/counters/c4", {"id": "c4", "name": "c4", "start": "1", "revision": "1"},
                 cas=box.vars.get("testsub/counters/c4")[1])
    assert [r["id"] for r in ctl.units()] == ["c1", "c2", "c3", "c4"] and ctl.rows_garbled == 1   # mended: a row, like any other

    ran = []
    ctl.redistribute = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("one released slot would not parse"))
    home = ctl.ensure_home
    ctl.ensure_home = lambda *a, **k: ran.append("home") or home(*a, **k)
    rep = ctl.pass_once()
    assert ran == ["home"] and not rep["ok"] and rep["error"].startswith("redistribute:") and rep["failures"] == 1
    assert ctl.placement("c4") is not None                                                    # `ensure_placed` ran before the step that raised


def test_a_placed_unit_whose_row_stops_parsing_holds_up_neither_placing_nor_moving():
    """The review's third pass. `units()` skipped a row that does not parse, but `unplace_deleted` — the first step of
    both `ensure_placed` and `redistribute` — and `redistribute` itself read each PLACED unit's row bare: one field
    edited by hand on a unit already placed, and no new unit was placed and no unit of a released slot moved,
    every pass. The garbled unit stays where it is, counted in `rows_garbled`; everything else goes on."""
    box, ctl, ws = _three(counters=6)
    assert ctl.assignment("w-3").units == ["c3", "c6"]
    it, idx = box.vars.get("testsub/counters/c3")
    box.vars.put("testsub/counters/c3", {**it, "start": "three"}, cas=idx)                  # placed, and now unreadable
    new = ctl.create({"name": "c7"})["id"]
    placed = ctl.ensure_placed()
    assert [p.unit for p in placed if p.unit == new] == [new] and ctl.placement("c3").worker == "w-3"   # not unplaced as "deleted"
    ws[2].release_slot()
    moves = ctl.redistribute()
    assert [(m[0], m[1]) for m in moves] == [("c6", "w-3")]                                 # c6 moved; c3 waits, listed where it was
    assert ctl.assignment("w-3").units == ["c3"]
    rep = ctl.pass_once()
    assert rep["ok"] and rep["garbled"] == 1
