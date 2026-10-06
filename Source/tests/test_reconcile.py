"""The platform's reconcile helper (`w2cplatform/reconcile.py`, ADR 0033) on testsub and testsub2: what runs is made
equal to what is wanted, and a failure waits a delay that doubles up to a ceiling and is spread by jitter — units that
fail together do not retry together (ARCHITECTURE §1.11). testsub's worker (`conftest.CounterWorker`) reconciles its
counters through it; testsub2's here (`TallyWorker`) its tallies, with a restart of its own or without one.

Each check of the ADR's Confirmation is a test below, and each fails without the rule it names: the doubling and its
ceiling, the spread within `[1−J, 1+J]`, two keys with one history waiting apart, a count cleared only by a unit that
stayed up `max`, a waiting key not tried early, `jitter = 0` refused, the order «stops, restarts, starts», and `drop`,
`clear`, `reset_backoff` and `status` on testsub2.
"""
import random

from tests.conftest import Box, controller, counter_worker, testsub2
from w2cplatform.contract import Controller
from w2cplatform.reconcile import CONVERGED, LAGGING, STALLED, Backoff, Pass, Position, Reconciler, Want
from w2cplatform.worker import Worker


class TallyWorker(Worker):
    """testsub2's worker, as small as the helper lets it be: a tally it is assigned RUNS under an epoch from the start
    the helper asks for to the stop; `calls` says what the helper asked, in order; a tally in `failing` does not start.
    With `restart` an edit is one call that keeps the epoch; without it, a stop and a start under a new one."""

    def __init__(self, box, restart: bool = True, backoff: Backoff | None = None):
        spec = testsub2()
        super().__init__(spec.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance="box-a:1:t",
                         spec=spec)
        self.claim_slot("t-1")
        self.running, self.calls, self.failing = {}, [], set()
        self.reconciler = Reconciler(self._start, self._stop, backoff, restart=self._restart if restart else None)
        self.reconciler.now = box.clock

    def _start(self, unit, want) -> bool:
        self.calls.append(("start", unit))
        if unit in self.failing:
            return False
        self.running[unit] = self.take_epoch(unit)
        return True

    def _restart(self, unit, want) -> bool:
        self.calls.append(("restart", unit))
        return unit not in self.failing                  # the epoch it holds goes on

    def _stop(self, unit) -> None:
        self.calls.append(("stop", unit))
        self.running.pop(unit, None)
        self.release(unit)

    def reconcile_once(self, now=None) -> Pass:
        wants = {}
        for unit in self.assignment().units:
            items, _ = self.vars.get(self.sub.config("tallies", unit))
            if items:
                wants[unit] = Want(int(items.get("revision") or 0), items)
        return self.reconciler.once(wants)


def _tallies(box, names, revision=1):
    spec = testsub2()
    for n in names:
        box.vars.put(spec.sub.config("tallies", n), {"name": n, "of": "7", "revision": str(revision)})
    Controller(spec.sub, box.vars, box.objects, wall=box.wall).assign("t-1", list(names))


def _tick(box, s):
    box.clock.advance(s); box.wall.advance(s)


# -- the delay -------------------------------------------------------------------------------------------------------

def test_the_delay_doubles_with_each_failure_and_stops_at_the_ceiling():
    """The n-th failure in a row waits `min(max, base·2^(n−1))` at the middle of its spread: 1, 2, 4, … and then `max`
    for ever — not a delay that grows without a bound, nor one that never grows."""
    b = Backoff(1.0, 60.0, 0.5)
    assert [b.delay(n, 0.5) for n in range(1, 9)] == [1, 2, 4, 8, 16, 32, 60, 60]
    assert Backoff(0.5, 3.0, 0.5).delay(10, 0.5) == 3.0


def test_the_spread_stays_within_one_less_and_one_more_jitter():
    """A substituted `rand` at its two ends gives the two ends of the spread, `(1−J)` and `(1+J)` of the doubled base, and
    nothing outside them."""
    b = Backoff(2.0, 60.0, 0.25)
    assert b.delay(3, 0.0) == 8.0 * 0.75 and abs(b.delay(3, 0.999999) - 8.0 * 1.25) < 1e-4
    assert all(8.0 * 0.75 <= b.delay(3, random.random()) <= 8.0 * 1.25 for _ in range(1000))


def test_a_backoff_without_jitter_is_refused():
    """`jitter = 0` would give every unit that failed at one instant the same instant to retry: the constructor refuses it,
    and anything past 1 too."""
    for bad in (0, 0.0, -0.1, 1.5):
        try:
            Backoff(1.0, 60.0, bad)
        except ValueError as e:
            assert "jitter" in str(e)
        else:
            raise AssertionError(f"jitter {bad} was taken")
    Backoff(1.0, 60.0, 1.0)


def test_a_backoff_without_a_positive_base_or_with_a_ceiling_under_it_is_refused():
    """A base of zero or less makes every delay zero or less — a failing unit is retried on every pass, the very thing a
    backoff is for; a ceiling under the base makes the first delay the ceiling and doubling nothing (ADR 0033, review 14,
    minor 22; the product's `Backoff.Check` refuses both). The constructor refuses them, and a NaN in either."""
    for base, top, word in ((0, 60.0, "base"), (-1.0, 60.0, "base"), (float("nan"), 60.0, "base"),
                            (10.0, 1.0, "max"), (1.0, float("nan"), "max")):
        try:
            Backoff(base, top, 0.5)
        except ValueError as e:
            assert word in str(e), e
        else:
            raise AssertionError(f"backoff base {base}, max {top} was taken")
    Backoff(2.0, 2.0, 0.5)


# -- on testsub: the counters of `CounterWorker` ------------------------------------------------------------------------

def _counters(box, n=2, name="w-1"):
    ctl = controller(box)
    for i in range(1, n + 1):
        ctl.create({"name": f"c{i}"})
    ctl.assign(name, [f"c{i}" for i in range(1, n + 1)])
    return counter_worker(box, name)


def test_counters_that_failed_together_do_not_retry_together():
    """Two counters whose epochs the store would not give, in one pass — one history of failures — get two different
    instants to try again, by the real `rand`: at the earlier one the first is tried and the other still waits."""
    box = Box()
    w = _counters(box)
    take = w.take_epoch
    w.take_epoch = lambda unit: (_ for _ in ()).throw(OSError("the store does not answer"))
    w.reconcile_once()
    st = w.reconciler.status()
    assert st["c1"].failures == st["c2"].failures == 1 and st["c1"].retry_at != st["c2"].retry_at, st
    w.take_epoch = take
    first, second = sorted(["c1", "c2"], key=lambda u: st[u].retry_at)
    box.clock.t = (st[first].retry_at + st[second].retry_at) / 2
    w.reconcile_once()
    assert first in w.running and second not in w.running and w.started == [first]


def test_a_counter_that_keeps_failing_waits_longer_each_time_and_never_past_the_ceiling():
    """The delay of a counter that keeps failing grows by doubling and stops at the ceiling, spread each time."""
    box = Box()
    w = _counters(box, 1)
    w.take_epoch = lambda unit: (_ for _ in ()).throw(OSError("the store does not answer"))
    waits = []
    for n in range(1, 10):
        w.reconcile_once()
        st = w.reconciler.status()["c1"]
        assert st.failures == n
        waits.append(st.retry_at - box.clock())
        box.clock.t = st.retry_at
    assert all(0.5 * min(60, 2 ** (n - 1)) <= d <= 1.5 * min(60, 2 ** (n - 1)) for n, d in enumerate(waits, 1)), waits
    assert max(waits) <= 90 and waits[-1] >= 30


def test_a_waiting_counter_is_not_tried_before_its_time():
    """A counter in its wait is `waiting` and its start is not called, however many passes come before the instant."""
    box = Box()
    w = _counters(box, 1)
    tried = []
    w.take_epoch = lambda unit: (tried.append(unit), (_ for _ in ()).throw(OSError("no")))[1]
    w.reconcile_once()
    at = w.reconciler.status()["c1"].retry_at
    while box.clock() + 0.1 < at:
        _tick(box, 0.1)
        assert w.reconciler.once({"c1": Want(0, w.rows["c1"])}).waiting == ["c1"]
    assert tried == ["c1"]


# -- on testsub2: the tallies of `TallyWorker` --------------------------------------------------------------------------

def test_a_unit_that_dies_after_every_start_waits_longer_and_one_that_stays_up_earns_its_count_back():
    """A success clears the count only once the unit has stayed up `max`: a pipeline that dies right after each start is
    started again at a delay that keeps doubling, not at the base delay for ever; one that then stays up `max` dies to
    the base delay again."""
    box = Box()
    w = TallyWorker(box, backoff=Backoff(1.0, 8.0, 0.5))
    w.reconciler.rand = lambda: 0.5                      # the middle of the spread: the delays themselves
    _tallies(box, ["a"])
    waits = []
    for _ in range(5):
        assert w.reconcile_once().started == ["a"]
        w.reconciler.forget("a")                         # it died at once
        st = w.reconciler.status()["a"]
        waits.append(st.retry_at - box.clock())
        box.clock.t = st.retry_at
    assert waits == [1, 2, 4, 8, 8], waits
    assert w.reconcile_once().started == ["a"]
    _tick(box, 8.0)                                      # up for `max`
    w.reconcile_once()
    assert w.reconciler.status()["a"].failures == 0
    w.reconciler.forget("a")
    assert w.reconciler.status()["a"].retry_at - box.clock() == 1


def test_a_unit_that_held_past_max_and_then_fails_its_restart_counts_waits_longer_and_stalls():
    """A tally has run for an hour (longer than `max`), the operator edits its row, and the restart in place fails
    every time: each failure adds to the count, the delay doubles, and at `stall_failures` the unit is `stalled`. The
    hour it held earned back the failures BEFORE it, not the ones of the restart that keeps failing: a key behind its
    revision has not held anything (ADR 0033, review 14, major 7: the count was wiped on every pass, the restart retried
    on every pass, and `stalled` never came)."""
    box = Box()
    w = TallyWorker(box, backoff=Backoff(1.0, 60.0, 0.5))
    w.reconciler.rand = lambda: 0.5                      # the middle of the spread: the delays themselves
    _tallies(box, ["a"])
    assert w.reconcile_once().started == ["a"]
    _tick(box, 100.0)                                    # up longer than `max`
    w.failing.add("a")
    _tallies(box, ["a"], revision=2)
    seen = []
    for _ in range(3):
        p = w.reconcile_once()
        st = w.reconciler.status()["a"]
        assert p.failed == ["a"], p
        seen.append((st.failures, st.retry_at - box.clock(), st.state))
        _tick(box, 0.1)
        assert w.reconcile_once().waiting == ["a"]       # not tried again before its delay
        box.clock.t = st.retry_at
    assert seen == [(1, 1, LAGGING), (2, 2, LAGGING), (3, 4, STALLED)], seen
    assert w.calls.count(("restart", "a")) == 3, w.calls


def test_a_unit_that_does_not_run_is_never_converged_whatever_its_revision():
    """A row without a revision is wanted at 0; a key at 0 whose every start fails runs nothing and is not `converged`
    because nothing is behind 0 — it is `lagging`, then `stalled` (ADR 0033, review 14, minor 21)."""
    r = Reconciler(lambda k, w: False, lambda k: None, Backoff(1.0, 60.0, 0.5))
    t = [0.0]
    r.now = lambda: t[0]
    r.once({"z": Want(0)})
    assert r.status()["z"].state == LAGGING, r.status()
    for _ in range(4):
        t[0] += 100.0
        r.once({"z": Want(0)})
    assert r.status()["z"].state == STALLED and r.status()["z"].failures == 5, r.status()
    ok = Reconciler(lambda k, w: True, lambda k: None)
    ok.once({"z": Want(0)})
    assert ok.status()["z"] == Position(CONVERGED, 0, 0, 0.0)


def test_a_pass_stops_first_then_restarts_then_starts():
    """What is not wanted is stopped before anything starts — what it held is free for what comes — then each unit
    behind its revision is restarted, then each new one started: `a`, new, is wanted before `b`, edited, and still
    starts after it."""
    box = Box()
    w = TallyWorker(box)
    _tallies(box, ["b", "x"])
    w.reconcile_once()
    spec = testsub2()
    box.vars.put(spec.sub.config("tallies", "a"), {"name": "a", "of": "7", "revision": "1"})
    box.vars.put(spec.sub.config("tallies", "b"), {"name": "b", "of": "7", "revision": "2"})
    Controller(spec.sub, box.vars, box.objects, wall=box.wall).assign("t-1", ["a", "b"])
    w.calls.clear()
    p = w.reconcile_once()
    assert w.calls == [("stop", "x"), ("restart", "b"), ("start", "a")], w.calls
    assert (p.stopped, p.restarted, p.started) == (["x"], ["b"], ["a"])


def test_a_restart_of_its_own_is_one_call_and_keeps_the_epoch_and_without_one_it_is_a_stop_and_a_start():
    """With `restart`, a unit behind its revision is restarted in one call: the epoch it holds goes on, the new revision is
    taken. Without, the restart is a stop and a start — a new epoch. A restart that fails leaves the unit on its old
    revision, counted, `lagging` and then `stalled`; one in its wait is `waiting`, under both forms."""
    for own in (True, False):
        box = Box()
        w = TallyWorker(box, restart=own)
        _tallies(box, ["a"])
        w.reconcile_once()
        epoch = w.running["a"]
        _tallies(box, ["a"], revision=2)
        w.calls.clear()
        p = w.reconcile_once()
        assert p.restarted == ["a"] and w.reconciler.running()["a"] == 2
        assert w.calls == ([("restart", "a")] if own else [("stop", "a"), ("start", "a")]), (own, w.calls)
        assert (w.running["a"] == epoch) is own
        w.failing.add("a")
        _tallies(box, ["a"], revision=3)
        p = w.reconcile_once()
        st = w.reconciler.status()["a"]
        assert p.failed == ["a"] and st.state == LAGGING and st.failures == 1 and st.lag == (1 if own else 3)
        assert w.reconcile_once().waiting == ["a"]
        for _ in range(2):
            box.clock.t = w.reconciler.status()["a"].retry_at
            w.reconcile_once()
        assert w.reconciler.status()["a"].state == STALLED


def test_drop_clear_reset_backoff_and_status_on_tallies():
    """`drop`: the worker stopped it past the loop (a lease lost) — not running, no failure, started again on the next
    pass. `forget`: it died — a failure, it waits. `clear`: fenced — nothing runs, the failures stay. `reset_backoff`:
    what they waited for is back — the named ones go, or all. `status`: each wanted unit's state, lag, count and instant."""
    box = Box()
    w = TallyWorker(box)
    _tallies(box, ["a", "b", "c"])
    w.reconcile_once()
    assert {k: (p.state, p.lag, p.failures) for k, p in w.reconciler.status().items()} == {
        u: (CONVERGED, 0, 0) for u in "abc"}
    w.reconciler.drop("a")
    assert "a" not in w.reconciler.running() and w.reconciler.status()["a"].failures == 0
    assert w.reconcile_once().started == ["a"]                     # at once: no failure to wait out
    w.reconciler.forget("b")
    assert w.reconciler.status()["b"].failures == 1 and w.reconcile_once().waiting == ["b"]
    w.reconciler.clear()
    assert w.reconciler.running() == {} and w.reconciler.status()["b"].failures == 1
    assert w.reconciler.status()["a"] == Position(LAGGING, 1, 0, 0.0)
    w.reconciler.forget("c")
    w.reconciler.reset_backoff("b")
    assert w.reconciler.status()["b"].failures == 0 and w.reconciler.status()["c"].failures == 1
    p = w.reconcile_once()
    assert set(p.started) == {"a", "b"} and p.waiting == ["c"]
    w.reconciler.reset_backoff()
    assert w.reconcile_once().started == ["c"] and set(w.reconciler.running()) == {"a", "b", "c"}
