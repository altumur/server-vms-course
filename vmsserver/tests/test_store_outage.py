"""A worker and a store that stops answering — and what a lost lease means (feedback BC).

Three rules, each learned on the product's box with the store of one cluster taken away (`chmod 000`):

    not knowing is not "no"    a store that did not answer says nothing: the worker goes on with the assignment it
                               read last, and its slot is still its own. Only a slot row READ, with another holder
                               in it, says "no"
    a lease is one camera's    lost however it was lost, one pipeline stops and gives its epoch up; if the camera
                               is still this worker's it is started again under a new epoch. The instance is not
                               fenced, and its other cameras are not stopped
    a fence is not for ever    a fenced instance takes a free slot on its next pass and starts from nothing
"""
import threading

from w2cplatform.epoch import Lease, next_epoch
from vms.worker import FakeActuator, VmsWorker
from tests.test_lesson4_worker import _box_with_cameras


class Flaky:
    """A store, and a switch: down, every read and write is an OSError — what a directory with its mode taken
    away gives, or a cluster's API that does not answer."""

    def __init__(self, inner):
        self.inner, self.down = inner, False

    def __getattr__(self, name):
        attr = getattr(self.inner, name)
        if not callable(attr) or name not in ("get", "put", "delete", "list"):
            return attr

        def call(*a, **kw):
            if self.down:
                raise PermissionError(13, "the store does not answer")
            return attr(*a, **kw)
        return call


def _worker(n=2):
    box, ctl = _box_with_cameras(n)
    ctl.assign("w-1", [str(i) for i in range(1, n + 1)])
    store, act = Flaky(box.vars), FakeActuator()
    w = VmsWorker("w-1", store, box.objects, act, clock=box.clock, wall=box.wall, archive_root=box.archive)
    w.claim_slot(prefer="w-1")
    w.reconcile_once()
    assert act.running == set(range(1, n + 1))
    return box, ctl, store, act, w


def test_a_store_that_does_not_answer_is_not_an_empty_assignment():
    """Sixteen seconds without the store: the cameras record under the same epochs, nothing is fenced, the pass
    goes on with the assignment read last — and a pipeline that fell over meanwhile is noticed."""
    box, ctl, store, act, w = _worker()
    store.down = True
    box.clock.advance(16); box.wall.advance(16)
    assert w.reconcile_once() == []                                   # nothing stopped: the last assignment stands
    assert w.lease_pass() == [] and w.recording_allowed               # the slot: not confirmed, and still mine
    assert act.running == {1, 2} and act.epochs == {1: 1, 2: 1} and w.store_errors == 2
    act.dead.append(1)                                                # a pipeline falls over while the store is away
    w.pump_once()                                                     # noticed: the pump is local (the requests are not, and wait)
    box.clock.advance(5); box.wall.advance(5)
    assert w.reconcile_once() == [("failed", 1)]                      # a new writer needs a new epoch: a failed start, retried
    assert w.recording_allowed and act.running == {2}                 # …of one camera. The pass did not end at it
    store.down = False
    box.clock.advance(60); box.wall.advance(60)
    assert ("start", 1) in w.reconcile_once() and act.epochs[1] == 2


def test_a_lease_the_store_did_not_confirm_in_time_stops_that_camera_and_it_comes_back_under_a_new_epoch():
    """Thirty-six seconds: past `ttl - margin`. Nobody confirmed that these cameras are still this worker's, so
    they stop — each with the reason in the log — and the instance is NOT fenced. The store returns, and the
    reconciler starts them again under the next epoch."""
    box, ctl, store, act, w = _worker()
    store.down = True
    box.clock.advance(36); box.wall.advance(36)
    assert sorted(w.lease_pass()) == ["1", "2"]
    assert act.running == set() and w.epochs == {} and w.recording_allowed and w.fenced_reason is None
    store.down = False
    box.clock.advance(60); box.wall.advance(60)                       # past any backoff
    w.reconcile_once()
    assert act.running == {1, 2} and act.epochs == {1: 2, 2: 2}
    assert w.lease_pass() == []


def test_a_camera_in_two_assignments_costs_one_pipeline_not_fifty():
    """Camera 1 is listed on two workers for the seconds a controller takes to mend it. The other worker took the
    next epoch. This worker used to read that as "another instance of me holds it: I am a zombie" and stop every
    camera it had. Its slot was renewed a line before — there is no other instance of it."""
    box, ctl, store, act, w = _worker()
    next_epoch(box.vars, "vms/epoch/1")                               # somebody else started camera 1
    assert w.lease_pass() == ["1"]
    assert w.recording_allowed and act.running == {2} and "1" not in w.epochs
    assert w.conflicts() == 0 and w.lease_pass() == []                # camera 2 is untouched; nothing left to lose


def test_only_a_slot_row_naming_another_holder_fences_and_a_fence_is_not_for_ever():
    """The replacement took w-1. The old instance reads the slot row, finds another holder and fences — that is a
    "no". It used to stay so: alive, heartbeating `fenced: true`, recording nothing until somebody restarted it.
    On its next pass it takes a free slot and starts from nothing."""
    box, ctl, store, act, a = _worker(1)
    box.wall.advance(46)                                              # a long pause: the slot lapsed
    b = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall)
    assert b.name == "w-1"
    assert a.lease_pass() == ["1"] and not a.recording_allowed and "slot w-1" in a.fenced_reason
    assert a.rejoin() == "w-2" and a.recording_allowed and a.was_fenced and a.fenced_reason is None
    assert a.epochs == {} and a.rows == [] and a.reconciler.actual == {}
    ctl.assign("w-2", ["1"])
    assert a.reconcile_once() == [("start", 1)]                       # whatever ITS slot's assignment says, from nothing
    assert b.lease_pass() == []                                       # and the replacement never noticed


def test_a_lease_runs_from_before_the_read_not_from_after_it():
    """A holder paused for a minute between reading the epoch row and stamping the renewal woke up with a fresh
    lease it had in fact slept through."""
    box, ctl = _box_with_cameras(1)
    epoch, _ = next_epoch(box.vars, "vms/epoch/1")

    class Slow:
        def get(self, key):
            out = box.vars.get(key)
            box.clock.advance(60)                                     # the pause: a GC, a stalled disk
            return out

    lease = Lease(Slow(), "vms/epoch/1", epoch, 30.0, 5.0, box.clock)
    assert lease.renew() is True                                      # the row said "yours" — a minute ago
    assert lease.may_write() is False and lease.seconds_left() == 0


def test_the_pump_does_not_wait_for_the_pass_over_the_store():
    """What is local — the buses, the devices' events, the spool — is drained whether or not the pass succeeded.
    They shared one `try`, and a pass that raised skipped the pump, every pass."""
    box, ctl, store, act, w = _worker(1)
    pumps = []
    w.reconcile_once = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("the pass raised"))
    w.pump_once = lambda: pumps.append(1)

    class Twice:
        def __init__(self): self.n = 0
        def is_set(self): self.n += 1; return self.n > 2
        def wait(self, s): return None
        def set(self): pass

    w.run(poll=0, stop=Twice())
    assert len(pumps) == 2
