"""The reconcile helper the platform owes every worker that runs a set of pipelines (ADR 0033; the product's
`w2cplatform/reconcile.go`, one form with this file): what runs is made equal to what is wanted, with exponential
backoff and jitter on failure.

    Desired state is persisted. Actual state is derived.

`Worker.reconcile_once` stays the base worker's abstract step: only the worker knows what "running" means. A worker
whose units are long-running pipelines — started, restarted when their row moves, stopped when it goes — calls
`Reconciler.once` from its step with what it wants; a worker whose work is not a set of pipelines need not.

What it keeps is the contract (ARCHITECTURE §1.11): a report never moves the desired state (`>=` on the revision);
what runs is derived, in memory, and a fresh process starts from nothing; and a failed start waits a delay that
doubles up to a ceiling and is spread by JITTER, so that units that failed together do not retry together — a store,
a server or a network that came back is not met by every unit at the same instant. Tested on testsub and testsub2
(`tests/test_reconcile.py`).
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # reconcile.py — the platform's reconcile helper (ADR 0033): desired persisted, running derived, backoff with jitter
#
# **Role in the module.** A common helper of the platform, not a step of the life cycle and not a hook (ADR 0002):
# the worker calls it, and it calls nothing of the worker's but the two functions it was built with. It knows nothing
# about epochs, leases, slots or the store — the worker's `start` is where an epoch is taken and a lease checked.
#
# ## Module-level names
# - `Backoff(base, max, jitter)` — the delay of the n-th failure in a row: `min(max, base·2^(n−1))` times a uniform
#   factor in `[1−jitter, 1+jitter]`. `jitter ∈ (0, 1]`: zero is refused, because a delay without it is the same
#   delay for every unit that failed at one instant. `base > 0` and `max ≥ base`, refused otherwise (the product's
#   `Backoff.Check`). Defaults 1 s, 60 s, 0.5.
# - `Want(rev, body)` — one key's desired state: its revision, which is all the helper compares, and what the
#   worker's `start` needs, opaque here.
# - `Pass(started, stopped, restarted, waiting, failed)` — what one `once` did, key by key, in the order it did it.
#   The worker says it in its heartbeat if it wants to; the helper writes nothing.
# - `Position(state, lag, failures, retry_at)` — one wanted key as `status` says it: `converged | lagging | stalled`.
# - `Reconciler(start, stop, backoff, restart)` — `start(key, want) -> bool` (False: a failed start), `stop(key)`, and
#   optionally `restart(key, want) -> bool`: with it a key behind its revision is restarted in ONE call (a holder that
#   keeps its epoch and lease across an edit); without it a restart is `stop`, then `start`. Not fields: a backoff is
#   checked once, by its constructor, and nothing replaces it past that. Fields: `now` (the clock of the delays,
#   seconds, monotonic), `rand` (uniform in `[0, 1)`; a test hands its own), `stall_failures` (3).
#
# ## Notes
# - The loop never sleeps or schedules itself: "nothing supervises the loop, because the loop is the process" — the
#   worker's step calls `once` on its pass.
# - A restart through `restart` that fails leaves the key running at its old revision: the next try is a restart again,
#   after its delay. Without `restart` the stop has happened: a start that fails leaves the key not running, and the next
#   try is a start.
# - A count lives while its key is wanted: `once` drops the failures of every key absent from `desired` at the top of
#   the pass (the product's `Once` does the same), so a key that leaves and comes back starts at the base delay — a new
#   life, not the old one's backoff. A key still wanted keeps its count until `_settle` or `reset_backoff` takes it.
# - Four ways out of `running` past `once`, by why: `forget` — it died, not by command: a failure; `drop` — the worker
#   stopped it (a lease lost, a place no longer fit): no failure; `clear` — the worker is fenced or lost its slot:
#   nothing runs, the failures stay; `reset_backoff` — what the failures waited for is back (a place opened, a new
#   slot): they go, named or all.
# ================================================================================================
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Hashable

CONVERGED, LAGGING, STALLED = "converged", "lagging", "stalled"


# The delay of the n-th failure in a row. `jitter` spreads it over `[1−jitter, 1+jitter]` of the doubled base; zero is
# the constructor's refusal (and so is anything past 1, which would make a delay negative). So are a base that is not
# positive — every delay would be nothing, a failing unit retried on every pass — and a ceiling under the base, which
# leaves nothing to double (ADR 0033; the product's `Backoff.Check`, one rule).
@dataclass(frozen=True)
class Backoff:
    base: float = 1.0
    max: float = 60.0
    jitter: float = 0.5

    def __post_init__(self):
        if not self.base > 0:
            raise ValueError(f"backoff base must be positive, not {self.base!r}")
        if not self.max >= self.base:
            raise ValueError(f"backoff max ({self.max!r}) is under its base ({self.base!r})")
        if not 0 < self.jitter <= 1:
            raise ValueError(f"backoff jitter must be in (0, 1], not {self.jitter!r}: without it, units that failed "
                             f"together retry together")

    # `n` ≥ 1 failures in a row, `rand` uniform in [0, 1).
    def delay(self, n: int, rand: float) -> float:
        return min(self.max, self.base * 2 ** (n - 1)) * (1 - self.jitter + 2 * self.jitter * rand)


# One key's desired state: `rev` is compared with `>=` (a running key at this revision or past it is left alone);
# `body` is the worker's — the row its `start` builds the pipeline from.
@dataclass(frozen=True)
class Want:
    rev: int
    body: Any = None


# What one pass did. `waiting`: wanted, behind, and not tried because its delay has not passed.
@dataclass
class Pass:
    started: list = field(default_factory=list)
    stopped: list = field(default_factory=list)
    restarted: list = field(default_factory=list)
    waiting: list = field(default_factory=list)
    failed: list = field(default_factory=list)


# One wanted key: `lag` its desired revision less the running one (the whole revision for a key not running);
# `state` is never `converged` for a key not running, whatever its lag; `failures` in a row;
# `retry_at` when it may be tried again (`now`'s clock; 0 with no failure).
@dataclass(frozen=True)
class Position:
    state: str
    lag: int
    failures: int = 0
    retry_at: float = 0.0


# One loop over what a worker wants. State, all in memory and rebuilt from nothing on restart: `_running` (`{key:
# rev}` of what it believes runs — IN MEMORY ONLY: a persisted one is a cache that lies), `_up_since` (when each
# started), `_failures` (`{key: (n, retry_at)}`), `_wanted` (`{key: rev}` of the last pass, for `status`).
class Reconciler:
    def __init__(self, start: Callable[[Hashable, Want], bool], stop: Callable[[Hashable], Any],
                 backoff: Backoff | None = None, restart: Callable[[Hashable, Want], bool] | None = None):
        self._start, self._stop, self._restart = start, stop, restart
        self._backoff = backoff if backoff is not None else Backoff()
        self.now: Callable[[], float] = time.monotonic
        self.rand: Callable[[], float] = random.random
        self.stall_failures = 3
        self._running: dict = {}
        self._up_since: dict = {}
        self._failures: dict = {}
        self._wanted: dict = {}

    @property
    def backoff(self) -> Backoff:
        return self._backoff

    # One pass over `desired` (`{key: Want}`). First what runs and is not wanted is stopped — the stop loop walks what
    # is RUNNING, and what it frees is free before anything starts; then each running key at a lower revision is
    # restarted (`>=` leaves it); then each key not running is started — both in `desired`'s order. A key whose delay
    # has not passed is waiting, under either form of restart. A failure adds to the key's count; a success takes the
    # revision and starts the key's countdown again, and clears its count only once it has stayed up for `backoff.max`
    # AT what is wanted now — a pipeline that dies right after every start waits longer each time, and so does a
    # restart that keeps failing on a key that had held for hours before its row moved. The count of a key not in
    # `desired` goes at the top of the pass, before anything is stopped or started: one that comes back is a new life,
    # its first start at the base delay — the product's `Once`, one rule (ADR 0033). Only the count: a key that still
    # runs is the stop loop's, and a key still wanted keeps its count.
    def once(self, desired: dict) -> Pass:
        now, p = self.now(), Pass()
        self._wanted = {k: w.rev for k, w in desired.items()}
        self._settle(now)
        for key in [k for k in self._failures if k not in desired]:
            del self._failures[key]                   # nobody wants it now: its next start is a first one (ADR 0033)
        for key in list(self._running):
            if key not in desired:
                self._stop(key)
                self._running.pop(key, None)
                self._up_since.pop(key, None)
                p.stopped.append(key)
        behind = [k for k, w in desired.items() if k in self._running and self._running[k] < w.rev]
        fresh = [k for k in desired if k not in self._running]
        for key, done in [(k, p.restarted) for k in behind] + [(k, p.started) for k in fresh]:
            failed = self._failures.get(key)
            if failed is not None and now < failed[1]:
                p.waiting.append(key)
                continue
            if done is p.restarted and self._restart is None:
                self._stop(key)                       # no restart of its own: a restart is a stop, then a start
                self._running.pop(key, None)
                self._up_since.pop(key, None)
            call = self._restart if done is p.restarted and self._restart is not None else self._start
            if call(key, desired[key]):
                self._running[key] = desired[key].rev
                self._up_since[key] = now
                done.append(key)
            else:
                self._fail(key, now)
                p.failed.append(key)
        return p

    # What it believes runs, `{key: rev}`: a read-only view, live — asked per unit of a large set, it costs nothing; a
    # caller that keeps it across a pass copies it.
    def running(self) -> MappingProxyType:
        return MappingProxyType(self._running)

    # The key's pipeline died, not by this loop's command: not running, and a failure — its next start waits.
    def forget(self, key) -> None:
        self._running.pop(key, None)
        self._up_since.pop(key, None)
        self._fail(key, self.now())

    # The worker stopped it past the loop (its lease lost, its place no longer fit): not running, and no failure.
    def drop(self, key) -> None:
        self._running.pop(key, None)
        self._up_since.pop(key, None)

    # The worker is fenced, or lost its slot: its pipelines were stopped underneath the loop. Nothing runs; the
    # failures stay.
    def clear(self) -> None:
        self._running.clear()
        self._up_since.clear()

    # What the failures waited for is back (a place opened, a new slot): the named keys' failures go — every key's, with
    # none named.
    def reset_backoff(self, *keys) -> None:
        if not keys:
            self._failures.clear()
        for key in keys:
            self._failures.pop(key, None)

    # Each key of the last pass: `converged` when it runs at no lag — a key that runs nothing is never `converged`, not
    # even one wanted at revision 0 (a row without a revision); else `stalled` once its failures reach
    # `stall_failures`, else `lagging`.
    def status(self) -> dict:
        self._settle(self.now())
        out = {}
        for key, rev in self._wanted.items():
            lag = max(rev - self._running.get(key, 0), 0)
            n, retry_at = self._failures.get(key, (0, 0.0))
            state = (CONVERGED if key in self._running and lag == 0
                     else STALLED if n >= self.stall_failures else LAGGING)
            out[key] = Position(state, lag, n, retry_at)
        return out

    def _fail(self, key, now: float) -> None:
        n = self._failures.get(key, (0, 0.0))[0] + 1
        self._failures[key] = (n, now + self._backoff.delay(n, self.rand()))

    # A key up for `backoff.max` since its last start, AT its wanted revision, has earned its count back. One behind it
    # is not: what it held was the old revision, and the failures are its restart's — wiping them would retry a restart
    # that keeps failing on every pass, with no delay and never `stalled` (ADR 0033; review 14, major 7).
    def _settle(self, now: float) -> None:
        for key in [k for k in self._failures if k in self._up_since and k in self._wanted
                    and self._running[k] >= self._wanted[k] and now - self._up_since[k] >= self._backoff.max]:
            del self._failures[key]
