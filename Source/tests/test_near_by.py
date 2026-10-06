"""Following a subsystem whose units are named differently: `by` and `of`.

testsub2's unit is a tally — `t7`, about counter `c7`; no holder of testsub's counters ever reports
that id. The bare `near: testsub` therefore matches nothing on it — an affinity that reads as
followed and is not. `by: of` says which value of MINE to look for. `of: name` says where in THEIR
status to look for it, for the day their entry's id is not the value I hold: an entry `c7-b` whose
`name` says `c7`, and nothing but that field says so. These tests are about both differences being
visible."""
import json

from w2cplatform import catalog
from w2cplatform.console import Heartbeat
from w2cplatform.spec import SpecController, SubsystemSpec
from tests.conftest import Box, testsub, testsub2

T2 = testsub2()                                                   # near: {sub: testsub, by: of, of: name}
catalog.register(testsub())                                       # …read by its spec: no controller without it (ADR 0056)


def _worker(box, spec, worker: str, server: str, capacity: int = 8, status=None):
    box.objects.put(spec.sub.heartbeat_key(worker),
                    Heartbeat(worker, box.wall(), status or [], {"server": server, "capacity": capacity,
                                                                 "headroom": capacity, "labels": "gpu"}).to_bytes())
    box.objects.put(f"platform/resources/{server}/heartbeat",
                    json.dumps({"server": server, "ts": box.wall(), "url": f"http://{server}", "units": {}}).encode())


def _holding(box, worker: str, server: str, *counters):
    """A worker of testsub whose heartbeat says it is running these counters, each entry carrying both
    identities: `id` is WHICH entry, `name` is WHOSE count. Write `"c7-b:c7"` when they differ, `"c7"`
    when they are one."""
    status = []
    for r in counters:
        uid, _, name = str(r).partition(":")
        status.append({"id": uid, "name": name or uid, "phase": "running"})
    _worker(box, testsub(), worker, server, status=status)


def test_the_tally_lands_beside_the_worker_holding_its_counter():
    box = Box()
    ctl = SpecController(T2, box.vars, box.objects, wall=box.wall)
    _worker(box, T2, "t-1", "srv-1")
    _worker(box, T2, "t-2", "srv-2")
    _holding(box, "w-2", "srv-2", "c7")                           # counter c7 is held on srv-2

    ctl.create({"name": "t7", "of": "c7"})
    ctl.ensure_placed()

    where = ctl.placement("t7")
    assert where is not None and ctl.server_of(where.worker) == "srv-2"
    assert "beside w-2" in where.reason                           # and it says so, in the operator's words


def short_unit():
    return {"rows": "units", "id": "name", "fields": {
        "name": {"type": "string", "required": True}, "of": {"type": "string", "required": True},
        "kind": {"type": "string", "required": True}}}


def test_the_short_form_would_follow_nothing_here():
    """The same cluster, the same holder, the only difference being `by`. The bare
    form looks for a holder reporting `t7` and no holder ever will."""
    box = Box()
    short = SubsystemSpec.from_dict({"name": "follow2", "unit": short_unit(),
                                     "placement": {"capacity": {"from": "capacity", "default": 8}, "near": "testsub"}})
    assert short.near == "testsub" and short.near_by == "id"

    ctl = SpecController(short, box.vars, box.objects, wall=box.wall)
    _worker(box, short, "t-1", "srv-1")
    _holding(box, "w-2", "srv-2", "c7")
    ctl.create({"name": "t7", "of": "c7", "kind": "plain"})
    assert ctl.holder_near("t7") is None                          # the holder is right there, and is not found

    full = SubsystemSpec.from_dict({"name": "follow3", "unit": short_unit(),
                                    "placement": {"capacity": {"from": "capacity", "default": 8},
                                                  "near": {"sub": "testsub", "by": "of"}}})
    ctl2 = SpecController(full, box.vars, box.objects, wall=box.wall)
    ctl2.create({"name": "t7", "of": "c7", "kind": "plain"})
    assert ctl2.holder_near("t7") == ("w-2", "srv-2")             # same cluster, one word of YAML


def test_no_holder_for_this_counter_is_a_fallback_not_a_refusal():
    """A counter nobody holds still gets a tally: the affinity is a preference,
    not a filter."""
    box = Box()
    ctl = SpecController(T2, box.vars, box.objects, wall=box.wall)
    _worker(box, T2, "t-1", "srv-1")
    ctl.create({"name": "t9", "of": "c9"})                        # nothing holds counter c9
    ctl.ensure_placed()
    assert ctl.placement("t9") is not None and ctl.placement("t9").worker == "t-1"


def test_a_unit_follows_the_unit_its_field_names_not_its_own_name():
    """`by` without `of`: my field's value is matched against THEIR id."""
    box = Box()
    spec = SubsystemSpec.from_dict({"name": "follow5", "unit": short_unit(),
                                    "placement": {"capacity": {"from": "capacity", "default": 2},
                                                  "near": {"sub": "testsub", "by": "of"}}})
    ctl = SpecController(spec, box.vars, box.objects, wall=box.wall)
    _worker(box, spec, "j-1", "srv-1", capacity=2)
    _worker(box, spec, "j-2", "srv-2", capacity=2)
    _holding(box, "w-2", "srv-2", "c7")

    ctl.create({"name": "c7-pass-1", "of": "c7", "kind": "plain"})
    ctl.ensure_placed()
    assert ctl.server_of(ctl.placement("c7-pass-1").worker) == "srv-2"   # where its counter is


def test_a_near_by_naming_no_field_is_refused_at_load():
    for bad in ({"sub": "testsub", "by": "counter"}, {"by": "of"}):
        try:
            SubsystemSpec.from_dict({"name": "x", "unit": short_unit(), "placement": {"near": bad}})
            raise AssertionError(f"accepted near: {bad}")
        except ValueError as e:
            assert "near" in str(e)


def test_the_affinity_survives_the_name_the_operator_chose():
    """The reason `of` exists. Counter c7's only entry is called `c7-b` — the id their worker gave it.
    Nothing in testsub2's row, and nothing in testsub2's controller, can know that string; the entry's
    `name` says it instead."""
    box = Box()
    ctl = SpecController(T2, box.vars, box.objects, wall=box.wall)
    _worker(box, T2, "t-1", "srv-1")
    _worker(box, T2, "t-2", "srv-2")
    _holding(box, "w-2", "srv-2", "c7-b:c7")                      # counter c7, under another id

    ctl.create({"name": "t7", "of": "c7"})
    ctl.ensure_placed()
    assert ctl.server_of(ctl.placement("t7").worker) == "srv-2"

    # and matching their id, as a spec without `of` does, would find nothing at all
    short = SubsystemSpec.from_dict({"name": "follow4", "unit": short_unit(),
                                     "placement": {"capacity": {"from": "capacity", "default": 8},
                                                   "near": {"sub": "testsub", "by": "of"}}})
    other = SpecController(short, box.vars, box.objects, wall=box.wall)
    other.create({"name": "t7", "of": "c7", "kind": "plain"})
    assert other.holder_near("t7") is None


def test_two_holders_of_one_counter_settle_the_tie_the_same_way_twice():
    """Two entries of one counter on two workers: the affinity has to pick one, and pick the
    same one next pass, or the follower walks between them forever. The smallest id wins."""
    box = Box()
    ctl = SpecController(T2, box.vars, box.objects, wall=box.wall)
    _worker(box, T2, "t-1", "srv-1")
    _worker(box, T2, "t-2", "srv-2")
    _holding(box, "w-1", "srv-1", "c7-b:c7")
    _holding(box, "w-2", "srv-2", "c7:c7")

    ctl.create({"name": "t7", "of": "c7"})
    assert ctl.holder_near("t7") == ("w-2", "srv-2")              # "c7" sorts before "c7-b"
    assert ctl.holder_near("t7") == ("w-2", "srv-2")
