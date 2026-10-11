"""A worker's memory budget (ADR-0070, step 3; the product's `memorybudget_internal_test.go` and `SpecFromMap`): the spec
says what a unit and the process cost (`placement.capacity: {unit_mb, base_mb}`, together or neither, numbers of MB above
0), the role's declaration what a worker may take (`WORKER_MEMORY_MB`) and how many units it carries (`CAPACITY`) — and a
worker whose units do not fit does not start. A test of the platform alone, on specs made up here."""
from __future__ import annotations

import dataclasses

from w2cplatform.contract import Subsystem
from w2cplatform.memorybudget import MemoryBudgetRefused, memory_budget
from w2cplatform.memvariables import MemVariables
from w2cplatform.spec import SubsystemSpec
from w2cplatform.worker import Worker


def _spec(**capacity) -> SubsystemSpec:
    return SubsystemSpec.from_dict({"name": "probe", "unit": {"rows": "items", "id": "name",
                                                              "fields": {"name": {"type": "string", "required": True}}},
                                    "placement": {"capacity": {"from": "capacity", "default": 4, **capacity}}})


def _refused(make, words: str) -> None:
    try:
        make()
    except ValueError as e:
        assert words in str(e), (words, str(e))
        return
    raise AssertionError(f"went through, and should not have: {words}")


def test_unit_mb_and_base_mb_are_said_together_as_numbers_of_mb_above_zero_or_not_at_all():
    """The loader (the product's words): one of the pair alone is refused, naming the one not said; each is a number
    of MB above 0 — a word, `true`, 0, a negative refused; a whole number or a fraction read. Neither: the spec loads
    as before, its costs 0 — nothing to check."""
    spec = _spec(unit_mb=30, base_mb=12.5)
    assert (spec.capacity_unit_mb, spec.capacity_base_mb) == (30.0, 12.5)
    assert (_spec().capacity_unit_mb, _spec().capacity_base_mb) == (0.0, 0.0)
    _refused(lambda: _spec(unit_mb=30), "spec probe: placement.capacity.base_mb is not said: unit_mb (what one unit "
                                        "costs a worker) and base_mb (what the process costs with none) are said "
                                        "together, in MB, or neither")
    _refused(lambda: _spec(base_mb=30), "placement.capacity.unit_mb is not said")
    for bad in (0, -1, "lots", True, None):
        _refused(lambda bad=bad: _spec(unit_mb=bad, base_mb=10), "placement.capacity.unit_mb is a number of MB above 0, not")
        _refused(lambda bad=bad: _spec(unit_mb=10, base_mb=bad), "placement.capacity.base_mb is a number of MB above 0, not")
    _refused(lambda: _spec(unit_mb=1, base_mb=1, gpu_mb=1), "placement.capacity is {from: <heartbeat field>")


def test_a_worker_whose_units_do_not_fit_its_budget_is_refused_and_one_without_a_budget_is_not_checked():
    """`CAPACITY · unit_mb + base_mb ≤ WORKER_MEMORY_MB`: 4 · 30 + 20 = 140 fits 140 and not 139; `CAPACITY` from the
    declaration wins over the spec's default (10 · 30 + 20 = 320); a budget that is no number above 0, or a `CAPACITY`
    that is no whole number, refused. No `WORKER_MEMORY_MB`: nothing checked; a spec that says no cost: the budget
    read, nothing compared."""
    spec = _spec(unit_mb=30, base_mb=20)
    assert memory_budget(spec, {}) == 0
    assert memory_budget(spec, {"WORKER_MEMORY_MB": "140"}) == 140
    _refused(lambda: memory_budget(spec, {"WORKER_MEMORY_MB": "139"}),
             "probe's worker carries 4 units (CAPACITY) at 30 MB each and 20 MB of its own — 140 MB, and WORKER_MEMORY_MB "
             "is 139: lower CAPACITY or raise WORKER_MEMORY_MB in the role's declaration")
    assert memory_budget(spec, {"WORKER_MEMORY_MB": "320", "CAPACITY": "10"}) == 320
    _refused(lambda: memory_budget(spec, {"WORKER_MEMORY_MB": "319", "CAPACITY": "10"}), "320 MB")
    for raw in ("0", "-5", "lots", "nan", "inf"):
        _refused(lambda raw=raw: memory_budget(spec, {"WORKER_MEMORY_MB": raw}), "WORKER_MEMORY_MB is a number of MB above 0")
    _refused(lambda: memory_budget(spec, {"WORKER_MEMORY_MB": "500", "CAPACITY": "2.5"}), "CAPACITY is a whole number")
    assert memory_budget(_spec(), {"WORKER_MEMORY_MB": "1", "CAPACITY": "1000"}) == 1


def test_the_base_worker_does_not_start_when_its_units_do_not_fit():
    """The check is the base worker's (the product's `NewWorker`): a worker of a subsystem whose spec says its costs,
    with a declaration whose budget its units overrun, does not start — before it claims anything of the store."""
    spec = dataclasses.replace(_spec(unit_mb=30, base_mb=20), name="probe")
    vars_ = MemVariables()
    _refused(lambda: Worker(Subsystem("probe"), None, vars_, None, spec=spec,
                            env={"WORKER_MEMORY_MB": "100", "CAPACITY": "4"}), "do not fit its memory budget")
    assert isinstance(MemoryBudgetRefused("x"), ValueError)
    assert vars_.list("") == []                                       # nothing written: it never got that far
