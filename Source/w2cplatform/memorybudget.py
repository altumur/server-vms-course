"""A worker's memory budget (ADR-0070, step 3; the product's `memorybudget.go`, 7e9fcdb).

    memory_budget(spec, env)   the budget `WORKER_MEMORY_MB` says, in MB — 0 when none is said — or `MemoryBudgetRefused`
                               when it does not read, or the spec's units at this worker's `CAPACITY` do not fit it
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # memorybudget.py — whether a worker's units fit the memory its role's declaration gives it
#
# **Role in the module.** ADR-0070, step 3: `CAPACITY` (how many units a worker carries) and the ceiling of spares on a
# host (`MAX_WORKERS`) were two numbers nothing compared — a server counted for fifty units, with four workers of
# fifty each, said two hundred, and no check stopped it. Now one formula ties them to the host's memory. The role's
# declaration on a host (`roles/<role>.env`: `CAPACITY`, `WORKER_MEMORY_MB`, `HOST_MEMORY_MB`) says what each worker of the
# role may take, and the spares pass derives how many fit (`deploy/w2c-spares.sh`: `HOST_MEMORY_MB / WORKER_MEMORY_MB`,
# rounded down). Here the worker's half: where the spec says what a unit and the process cost
# (`placement.capacity: {unit_mb, base_mb}`, the subsystem's word about itself), the worker's units must fit its budget —
# `CAPACITY · unit_mb + base_mb ≤ WORKER_MEMORY_MB` — or the process does not start (`Worker.__init__`): a host would
# place more units on it than its memory holds, and the kernel would end it at the worst moment.
#
# `CAPACITY` is compared here, never read as a capacity (ADR-0030 p. 6: the worker's heartbeat says its capacity); without
# it in the environment, the spec's `placement.capacity.default` is the number compared. Without `WORKER_MEMORY_MB` — a
# test, a tool — nothing is checked. The check is the platform's, by the spec's numbers and the environment's; no code of
# a subsystem is in it.
#
# What the product does and this does not: it also sets the Go runtime's soft memory limit to the budget
# (`debug.SetMemoryLimit`). Python has no soft limit — `RLIMIT_AS` is a hard one, of address space, which is not the
# same number — so the course only checks.
# ================================================================================================
from __future__ import annotations

import os

MEMORY_BUDGET_ENV = "WORKER_MEMORY_MB"      # a worker's budget, MB — its role's declaration
CAPACITY_ENV = "CAPACITY"                   # the units it carries — the same declaration


class MemoryBudgetRefused(ValueError):
    """A worker whose budget does not read, or whose units do not fit it: the process does not start."""


def memory_budget(spec, env=None) -> float:
    """The budget `env` says, in MB (0: none said — nothing limited, nothing checked), checked against the spec's units
    at this worker's capacity (the notes above)."""
    env = os.environ if env is None else env
    raw = str(env.get(MEMORY_BUDGET_ENV, "") or "")
    if not raw:
        return 0.0
    try:
        budget = float(raw)
    except ValueError:
        budget = float("nan")
    if not budget > 0 or budget == float("inf"):
        raise MemoryBudgetRefused(f"a worker's units do not fit its memory budget ({MEMORY_BUDGET_ENV}): "
                                  f"{MEMORY_BUDGET_ENV} is a number of MB above 0, not {raw!r}")
    unit_mb = float(getattr(spec, "capacity_unit_mb", 0.0) or 0.0)
    if spec is None or not unit_mb:
        return budget                            # the spec says no unit's cost: nothing to compare
    base_mb = float(getattr(spec, "capacity_base_mb", 0.0) or 0.0)
    capacity = spec.capacity_default
    said = str(env.get(CAPACITY_ENV, "") or "")
    if said:
        if not (said.isascii() and said.isdigit()):
            raise MemoryBudgetRefused(f"a worker's units do not fit its memory budget ({MEMORY_BUDGET_ENV}): "
                                      f"{CAPACITY_ENV} is a whole number of units, not {said!r}")
        capacity = int(said)
    need = capacity * unit_mb + base_mb
    if need > budget:
        raise MemoryBudgetRefused(
            f"a worker's units do not fit its memory budget ({MEMORY_BUDGET_ENV}): {spec.name}'s worker carries "
            f"{capacity} units ({CAPACITY_ENV}) at {unit_mb:g} MB each and {base_mb:g} MB of its own — {need:g} MB, and "
            f"{MEMORY_BUDGET_ENV} is {budget:g}: lower CAPACITY or raise WORKER_MEMORY_MB in the role's declaration")
    return budget
