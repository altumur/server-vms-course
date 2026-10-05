"""`retire_when`: the word the first four subsystems never needed. A unit whose
work is over is not placed, gives back the budget it held, and stays that way.

On testsub2 (`testdata/testsub2.subsystem.yaml`): a tally is over when its row says
`state: done` or `state: failed`."""
from w2cplatform.console import Heartbeat
from w2cplatform.spec import SpecController, SubsystemSpec
from tests.conftest import Box, console_ctl, controller_ctl, testsub, testsub2

T2 = testsub2()


def _ctls(box):
    return console_ctl(box, spec=T2), controller_ctl(box, spec=T2)


def _worker(box, worker, server, *status, capacity=2):
    box.objects.put(T2.sub.heartbeat_key(worker),
                    Heartbeat(worker, box.wall(), list(status),
                              {"server": server, "capacity": capacity, "headroom": capacity, "labels": "gpu"}).to_bytes())


def _tally(con, name, **fields):
    con.create({"name": name, "of": "c7", **fields})
    return name


def test_finished_work_is_not_placed():
    box = Box(); con, adm = _ctls(box)
    _worker(box, "t-1", "srv-1")
    a, b = _tally(con, "a"), _tally(con, "b")
    con.update(b, {"state": "done"})
    adm.ensure_placed()
    assert adm.placement(a) is not None and adm.placement(b) is None


def test_finished_work_is_not_the_clusters_fault():
    """`/unplaceable` is the answer to "nothing here can serve this". A unit that is
    over is unplaced for a completely different reason, and telling the operator
    their cluster cannot run it sends them looking for a worker to add."""
    box = Box(); con, adm = _ctls(box)
    _worker(box, "t-1", "srv-1")                                        # on srv-1
    con.write_table_row("shelves", {"name": "s9", "kind": "reserve", "server": "srv-9"})   # a shelf bound to srv-9
    _tally(con, "a", shelf="s9")
    _tally(con, "b", shelf="s9")
    con.update("b", {"state": "done"})
    adm.ensure_placed()
    assert [u["id"] for u in adm.unplaceable()] == ["a"]                 # the one still waiting, and only it


def test_the_budget_a_finished_job_held_comes_back():
    """One worker, one slot. The second unit waits; the first finishes; the second
    runs. Without the un-placing half, a cluster's whole capacity ends up held by
    work that is over."""
    box = Box(); con, adm = _ctls(box)
    _worker(box, "t-1", "srv-1", capacity=1)
    a, b = _tally(con, "a"), _tally(con, "b")
    adm.ensure_placed()
    assert adm.placement(a) is not None and adm.placement(b) is None

    con.update(a, {"state": "done"})
    adm.ensure_placed()
    assert adm.placement(a) is None and adm.placement(b) is not None
    assert adm.placement(b).worker == "t-1"


def test_the_reason_says_which_end_it_came_to():
    box = Box(); con, adm = _ctls(box)
    _worker(box, "t-1", "srv-1")
    a = _tally(con, "a"); adm.ensure_placed()
    con.update(a, {"state": "failed"}); adm.ensure_placed()
    it, _ = adm.vars.get(T2.sub.config("placement", a))
    assert it["worker"] == "" and it["reason"] == "failed"     # "done" and "failed" are different news


def test_the_whole_cycle_does_not_start_finished_work_over():
    """The failure this design exists to avoid, walked end to end. The worker says
    done; the subsystem writes the row (its reaper, here the test); the controller
    takes the assignment back; the worker drops the unit and its next heartbeat does
    not mention it — and the evidence of `done` is gone from the heartbeats. The ROW
    is what keeps it finished."""
    box = Box(); con, adm = _ctls(box)
    _worker(box, "t-1", "srv-1")
    a = _tally(con, "a"); adm.ensure_placed()
    assert adm.placement(a).worker == "t-1"

    _worker(box, "t-1", "srv-1", {"id": a, "phase": "done"})                       # the worker finished it
    assert [st["phase"] for st in adm.read_model() if st["id"] == a] == ["done"]
    con.update(a, {"state": "done"})                                               # …and its subsystem says so in the row
    adm.ensure_placed()
    assert adm.placement(a) is None                                                # the assignment is back

    _worker(box, "t-1", "srv-1")                                                   # the worker dropped it: silence
    assert [st for st in adm.read_model() if st["id"] == a] == []                   # no heartbeat says done any more
    for _ in range(3):
        adm.ensure_placed()
    assert adm.placement(a) is None                                                # and it is still not running

    con.update(a, {"state": "open"})                                               # the operator asks again
    adm.ensure_placed()
    assert adm.placement(a) is not None                                            # the row decides, and only the row


def test_a_subsystem_that_never_ends_is_untouched():
    """A spec that does not say `retire_when` retires nothing, whatever its rows say: a
    counter whose row says `done` in a field of its own keeps its assignment and its line
    in the console's list. A unit that stays visible while doing nothing is a different
    thing from one that is over, and only the spec says which field means over."""
    spec = testsub()
    assert spec.retire_field == "" and spec.retire_values == ()
    box = Box()
    ctl = SpecController(spec, box.vars, box.objects, wall=box.wall)
    box.objects.put(spec.sub.heartbeat_key("w-1"),
                    Heartbeat("w-1", box.wall(), [], {"server": "srv-1", "capacity": 4, "headroom": 4}).to_bytes())
    ctl.create({"name": "gate"}); ctl.ensure_placed()
    uid = ctl.units()[0]["id"]
    ctl.update(uid, {"marks": ["done"], "start": 5}); ctl.ensure_placed()
    assert ctl.placement(uid) is not None and ctl.placement(uid).worker == "w-1"


def test_a_predicate_that_retires_nothing_is_refused_at_load():
    unit = {"rows": "u", "id": "name", "fields": {"name": {"type": "string"}, "state": {"type": "string"}}}
    for bad, want in (({"field": "phase", "in": ["done"]}, "names no field"),
                      ({"field": "state"}, "non-empty"),
                      ({"in": ["done"]}, "non-empty")):
        try:
            SubsystemSpec.from_dict({"name": "x", "unit": unit, "placement": {"retire_when": bad}})
            raise AssertionError(f"accepted retire_when: {bad}")
        except ValueError as e:
            assert want in str(e), str(e)
