"""A unit nobody holds for `placement.unplaced.delete_after` is deleted by its spec's controller (ADR-0067): the key,
what the loader refuses, the controller's right — a delete and never a write — and its pass on testsub."""
from __future__ import annotations

import copy
import os

import yaml

from w2cplatform.rights import DELETE_ONLY, allowed, refusal
from w2cplatform.spec import SpecController, SubsystemSpec
from w2cplatform.variables import Forbidden
from tests.conftest import Box

TESTSUB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata", "testsub.subsystem.yaml")


def _raw() -> dict:
    with open(TESTSUB, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_the_key_is_whole_seconds_one_or_more_and_nothing_else_under_unplaced():
    """`placement.unplaced: {delete_after: <whole seconds ≥ 1>}` (the form «Платформа»'s): testsub says an hour, a
    spec without it deletes nothing; `0`, a fraction, a word, `true`, a negative, another key under `unplaced`, a bare
    number does not load — and nor does the key beside `unit.derived`: those rows are the console's to clean."""
    assert SubsystemSpec.load(TESTSUB).unplaced_delete_after == 3600
    d = _raw()
    del d["placement"]["unplaced"]
    assert SubsystemSpec.from_dict(d).unplaced_delete_after == 0
    for ok, n in ((1, 1), (60.0, 60)):
        d = _raw()
        d["placement"]["unplaced"] = {"delete_after": ok}
        assert SubsystemSpec.from_dict(d).unplaced_delete_after == n
    for bad in ({"delete_after": 0}, {"delete_after": 1.5}, {"delete_after": "30"}, {"delete_after": True},
                {"delete_after": -5}, {"delete_after": 30, "grace": 5}, {}, 30, None):
        d = _raw()
        d["placement"]["unplaced"] = bad
        try:
            SubsystemSpec.from_dict(d)
            raise AssertionError(f"placement.unplaced {bad!r} loaded")
        except ValueError as e:
            assert "placement.unplaced is {delete_after: <whole seconds, 1 or more>}" in str(e), e
    d = _raw()
    d["unit"]["derived"] = [{"row": "tallies/{id}", "items": {"of": "name"}}]   # a field of the row (review 15, major 1)
    try:
        SubsystemSpec.from_dict(d)
        raise AssertionError("delete_after beside unit.derived loaded")
    except ValueError as e:
        assert "placement.unplaced.delete_after with unit.derived" in str(e), e


def test_the_controller_may_delete_a_unit_row_with_the_key_and_never_write_one():
    """The right is the product's `p.DeleteOnly`: `delete:<sub>/<rows>/*` in the controller's ACL, only with the key. It
    gives the delete and not the write, in the one evaluator every store asks (`rights.allowed`)."""
    spec = SubsystemSpec.load(TESTSUB)
    acl = spec.acl_controller()
    assert f"{DELETE_ONLY}testsub/counters/*" in acl
    assert allowed(acl, "testsub/counters/7", "delete") and not allowed(acl, "testsub/counters/7")
    assert refusal("c", {"c": acl}, "testsub/counters/7") == "c may not write testsub/counters/7"
    d = _raw()
    del d["placement"]["unplaced"]
    assert not any(p.startswith(DELETE_ONLY) for p in SubsystemSpec.from_dict(d).acl_controller())


def test_a_unit_nobody_holds_that_long_is_deleted_by_its_controller_and_without_the_key_it_stands():
    """testsub's controller, its own ACL, no worker: a counter stands unheld; the controller counts from the first pass
    that saw it so (its own clock), and past an hour deletes the row — removed, by CAS — with a line
    `unit.unplaced_deleted {target, after_s}` and the pass's `unplaced_deleted_total`; the controller still writes no
    unit's row. A spec without the key: the row stands whatever its age. (A row placed before its time is kept:
    `test_lesson8_live.py::test_a_stream_nobody_places_does_not_stand_for_ever`.)"""
    box = Box()
    spec = SubsystemSpec.load(TESTSUB)
    console = SpecController(spec, box.vars.as_writer("console", spec.acl_console()), box.objects, wall=box.wall)
    ctl = SpecController(spec, box.vars.as_writer("testsubcontroller", spec.acl_controller()), box.objects, wall=box.wall)
    lines = []
    ctl.journal = type("J", (), {"say": lambda self, kind, cls="observation", **f: lines.append((kind, f))})()
    console.create({"name": "a"})
    console.create({"name": "b"})
    ids = sorted(r["id"] for r in console.units())
    rep = ctl.pass_once()
    assert rep["unplaced"] == 2 and rep["unplaced_deleted_total"] == 0
    box.wall.advance(3599)
    assert ctl.pass_once()["unplaced_deleted_total"] == 0 and len(console.units()) == 2
    box.wall.advance(1)
    rep = ctl.pass_once()
    assert rep["unplaced_deleted_total"] == 2 and console.units() == []
    assert all(box.vars.get(spec.sub.config(spec.rows, str(i)))[0] is None for i in ids)      # removed, not a tombstone
    assert sorted((k, f["target"], f["after_s"]) for k, f in lines) == \
        sorted(("unit.unplaced_deleted", str(i), 3600) for i in ids)
    try:                                                                                     # …and still never a write
        ctl.vars.put(spec.sub.config(spec.rows, "9"), {"name": "x"})
        raise AssertionError("the controller wrote a unit's row")
    except Forbidden:
        pass

    d = copy.deepcopy(_raw())
    del d["placement"]["unplaced"]
    plain = SubsystemSpec.from_dict(d)
    keeper = SpecController(plain, box.vars.as_writer("testsubcontroller", plain.acl_controller()), box.objects, wall=box.wall)
    console.create({"name": "c"})
    keeper.pass_once()
    box.wall.advance(10 ** 6)
    assert keeper.pass_once()["unplaced"] == 1 and len(console.units()) == 1                  # no key: it stands
