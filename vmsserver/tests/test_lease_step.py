"""The lease step of a worker's loop, and a store that pauses (the raft prototype's finding, `_notes-ru/raft-prototype.md`).

A worker renews its slot and its leases in one step every `T = (ttl − margin) / 3` seconds, looked at every `poll`. The
prototype measured a raft leader's death under thirty real workers and found the loop, not raft, to blame for the leases
that went past their window: the next step was counted from the END of the previous one, and a renewal the store did not
answer waited a whole period more. A step that waited out a pause of `P` seconds pushed the next one `P` later, and
without a confirmation went `≈ 2T + P` — past the 25 s window at a pause of ten seconds.

Now the next step is counted from the START of the previous one, and a step with a renewal the store did not answer is
followed by another at the next look: `≈ T + P + poll`. The store here is a fake that pauses like a store electing a
leader: a call made during the pause waits for its end if that comes within `D` (the call's term), and fails after `D`
otherwise. The clocks are fakes too; the loop is the real one (`VmsWorker.run`, `AutoWorker.run`), its work stubbed —
only the lease step talks to the store.
"""
import threading

from vms.worker import FakeActuator, VmsWorker
from tests.conftest import Box
from tests.test_lesson4_worker import _box_with_cameras

T_POLL = 2.0
D = 4.5                      # how long one call waits for a leader (the prototype's daemon)


class _Pausing:
    """`vars` that stop answering for `pause` seconds from `at`: a call begun in the pause waits for its end, if that
    comes within `D`, and is answered; otherwise it fails after `D` (`OSError`). Waiting moves both clocks."""

    def __init__(self, inner, box, at: float, pause: float):
        self.inner, self.box, self.at, self.pause = inner, box, at, pause

    def __getattr__(self, name):
        attr = getattr(self.inner, name)
        if name not in ("get", "put", "delete", "list"):
            return attr

        def call(*a, **kw):
            now, end = self.box.clock(), self.at + self.pause
            if self.at <= now < end:
                wait = min(D, end - now)
                self.box.clock.advance(wait); self.box.wall.advance(wait)
                if now + D < end:
                    raise ConnectionError("no leader")
            return attr(*a, **kw)
        return call


class _Turns:
    """A `stop` for `run`: `n` turns, each `wait(poll)` moving both clocks by `poll`."""

    def __init__(self, n: int, box: Box):
        self.n, self.box = n, box

    def is_set(self):
        return self.n <= 0

    def wait(self, poll):
        self.n -= 1
        self.box.clock.advance(poll); self.box.wall.advance(poll)
        return False

    def set(self):
        self.n = 0


def _worker(at: float, pause: float):
    box, ctl = _box_with_cameras(2)
    ctl.assign("w-1", ["1", "2"])
    store = _Pausing(box.vars, box, box.clock() + at, pause)
    w = VmsWorker("w-1", store, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, archive_root=box.archive)
    w.reconcile_once()
    assert sorted(w.leases) == ["1", "2"]
    for stub in ("reconcile_once", "pump_once", "heartbeat_once", "beat_once"):   # only the lease step talks to the store
        setattr(w, stub, lambda *a, **kw: None)
    w.start_stand_in = lambda: threading.Event()                                   # no thread: the clocks are fakes
    return box, w


def _gaps(box, w, step):
    """Run `step` and note, per lease, the longest stretch between two confirmations (`Lease.last_renewal`)."""
    last = {u: l.last_renewal for u, l in w.leases.items()}
    worst = {u: 0.0 for u in last}
    lease_pass = w.lease_pass

    def noted():
        out = lease_pass()
        for u, l in w.leases.items():
            if l.last_renewal != last[u]:
                worst[u] = max(worst[u], l.last_renewal - last[u])
                last[u] = l.last_renewal
        return out
    w.lease_pass = noted
    step()
    return max(worst.values())


def _old_loop(box, w, turns: int):
    """The loop's lease step as it was (`vms/worker.py` before the fix): `last_lease = self.clock()` AFTER the step, and
    nothing sooner after a step whose renewals the store did not answer."""
    every = max(1.0, (w.lease_ttl - w.lease_margin) / 3)
    last_lease = 0.0
    for _ in range(turns):
        if box.clock() - last_lease >= every:
            w.lease_pass()
            last_lease = box.clock()
        box.clock.advance(T_POLL); box.wall.advance(T_POLL)


def test_the_next_lease_step_counts_from_the_start_of_the_last_and_a_step_unanswered_is_tried_again_at_the_next_look():
    """The prototype's worst case: the pause begins as a lease step does, and lasts `P = 9.6 s` — longer than a call
    waits (`D = 4.5 s`), so the step's first calls fail. Before the fix the leases went `≈ 2T + P` without a
    confirmation — about 30 s, past the 25 s window (`may_write` false for seconds; the prototype measured 29.7). After
    it `≈ T + P + poll` — about 22 s, inside. The same pause, the same store, the same worker; only the loop differs."""
    window, P = 25.0, 9.6
    box, w = _worker(at=20.0, pause=P)               # steps at 0, 10, 20: the pause begins with the third
    before = _gaps(box, w, lambda: _old_loop(box, w, 40))
    box, w = _worker(at=20.0, pause=P)
    after = _gaps(box, w, lambda: w.run(poll=T_POLL, stop=_Turns(40, box)))
    T = 10.0                                         # 8.33 s, rounded up to the next look every 2 s
    print(f"worst unconfirmed with a {P} s pause: before {before:.1f} s, after {after:.1f} s (window {window:.0f})")
    assert before > window and abs(before - (2 * T + P)) <= T_POLL + 0.5, before
    assert after < window and after <= T + P + T_POLL + 0.5, after
    assert w.store_errors + sum(l.store_errors for l in w.leases.values()) > 0      # the pause was felt, and counted


def test_a_pause_a_call_waits_out_costs_the_pause_and_nothing_more():
    """`P ≤ D`: every call made in the pause waits for the new leader and is answered — no renewal unanswered, and the
    next step comes a period after the START of the late one, not a period after its end."""
    box, w = _worker(at=20.0, pause=3.5)
    after = _gaps(box, w, lambda: w.run(poll=T_POLL, stop=_Turns(40, box)))
    assert after <= 10.0 + 3.5 + 0.01, after
    assert w.store_errors == 0


def test_the_evaluators_loop_has_the_same_lease_step():
    """`AutoWorker.run` keeps its leases the same way: a step whose renewals were not answered is followed by another at
    the next look, and the period runs from a step's start."""
    from vms.autoworker import AutoWorker
    box = Box()
    store = _Pausing(box.vars, box, box.clock() + 1000.0, 0.0)
    w = AutoWorker("a-1", store, box.objects, clock=box.clock, wall=box.wall, env={})
    for stub in ("reconcile_once", "heartbeat_once"):
        setattr(w, stub, lambda *a, **kw: None)
    w.start_stand_in = lambda: threading.Event()
    steps, failing = [], [3]

    def lease_pass():
        steps.append(box.clock())
        if failing[0]:
            failing[0] -= 1
            w.unanswered += 1                         # a renewal the store did not answer
        box.clock.advance(1.5)                        # the step itself takes a while
        return []
    w.lease_pass = lease_pass
    w.run(poll=T_POLL, stop=_Turns(20, box))
    gaps = [round(b - a, 1) for a, b in zip(steps, steps[1:])]
    assert gaps[:3] == [3.5, 3.5, 3.5], gaps          # unanswered: again at the next look (the step's 1.5 s and a poll)
    # answered: the next a period after this one BEGAN — the first look past 8.33 s from it, 9.5 s; counted from its
    # end (the old loop) it was the first look past 8.33 s from 1.5 s later, 11.5 s
    assert gaps[3:] and all(g == 9.5 for g in gaps[3:]), gaps
