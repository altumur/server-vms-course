"""A step that hangs, and who renews for it (feedback DD; the fourth review's open item).

The loop that does the work was the loop that renewed: a pass hung on the store, a pump, a recorder's call
into obsd, and nothing renewed the leases or the slot row — thirty seconds later the units went to a
neighbour, though the process was alive and about to come back. Now every step of a loop is `guarded`,
and a stand-in beside the loop renews the slot, the leases and the place for a step that has run too long —
by the loop's own rules, and for `STAND_IN_FOR` at most.

The clock is the box's: a step "hangs" by the test moving the monotonic and the wall clock while it is
inside `guarded`, and the stand-in's look is `stand_in_once()`, called by hand. The last two tests run the
real loops, with the real stand-in thread, to show every worker's `run` has one.
"""
import threading
import time

from vms.worker import FakeActuator, VmsWorker
from w2cplatform.contract import Heartbeat, Slot, Subsystem, Worker
from w2cplatform.epoch import Lease, next_epoch
from tests.conftest import Box


def _holder(box, name="w-1", **kw):
    return VmsWorker(name, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                     archive_root=box.archive, **kw)


def _tick(box, s):
    box.clock.advance(s); box.wall.advance(s)


def _slot_row(box, w, name=None):
    name = name or w.name
    return Slot.from_items(name, box.vars.get(w.sub.slot_key(name))[0])


def test_a_step_stuck_longer_than_half_the_lease_keeps_its_leases_and_its_slot_row():
    """The rule itself. A pass hung for a minute — twice the lease, past the slot's 45 s — and the camera's
    lease never stopped allowing writes, the slot row never lapsed, and the heartbeat says how often somebody
    stood in."""
    box = Box()
    w = _holder(box)
    w.take_epoch("1")
    w.renew_leases()
    with w.guarded("pass"):
        for _ in range(12):                                         # 12 × 5 s
            _tick(box, 5)
            w.stand_in_once()
            assert w.may_write("1"), f"the lease ran out under a hung step at {box.clock() - 1000:.0f} s"
            assert not _slot_row(box, w).lapsed(box.wall()), "the slot row lapsed under a hung step"
    assert w.stand_in_renewals >= 5
    w.heartbeat_once()
    hb = Heartbeat.from_bytes(box.objects.get(w.sub.heartbeat_key(w.name)))
    assert hb.extra.get("stand_in_renewals") == w.stand_in_renewals


def test_a_step_that_starts_late_in_the_lease_is_stood_in_for_before_the_lease_ends():
    """A holder renews every `(ttl − margin)/3`, so a step may start ten seconds into a lease. Judged from the
    step's start alone, the stand-in would first look at 12.5 s into the step — 22.5 s into a 25 s lease, and one
    slow look from the end. It judges from the loop's last renewal when that is earlier."""
    box = Box()
    w = _holder(box)
    w.take_epoch("1")
    w.renew_leases()
    _tick(box, 10)                                                 # the loop renewed ten seconds ago
    with w.guarded("pass"):
        _tick(box, 3)
        assert w.stand_in_once(), "13 s since the loop renewed, under a running step: the stand-in did not renew"
        assert w.leases["1"].seconds_left() == w.lease_ttl - w.lease_margin


def test_a_step_stuck_past_STAND_IN_FOR_lets_its_units_go():
    """A step hung for ever does not hold units for ever. Up to `STAND_IN_FOR` the stand-in renews; after it,
    nothing — the lease runs out, the slot row lapses, a spare takes the name, and when the step finally comes
    back the loop finds itself fenced at the slot."""
    box = Box()
    w = _holder(box)
    w.take_epoch("1")
    w.renew_leases()
    with w.guarded("pass"):
        start = box.clock()
        while box.clock() - start + 5 <= w.STAND_IN_FOR:
            _tick(box, 5)
            w.stand_in_once()
            assert w.may_write("1")
        held = w.stand_in_renewals
        for _ in range(12):                                         # another minute past STAND_IN_FOR
            _tick(box, 5)
            w.stand_in_once()
        assert w.stand_in_renewals == held, "the stand-in went on renewing past STAND_IN_FOR"
        assert not w.may_write("1"), "a step hung past STAND_IN_FOR still holds its camera"
        assert _slot_row(box, w).lapsed(box.wall()), "a step hung past STAND_IN_FOR still holds its slot"
        spare = _holder(box, name=None, instance="spare:1")         # a nameless process takes a lapsed slot first
        assert spare.name == "w-1"
    assert w.lease_pass() == ["1"]
    assert not w.recording_allowed and "held by another instance" in w.fenced_reason


def test_a_slot_row_another_instance_took_is_not_written_over_by_the_stand_in():
    """The slot only by CAS and only while it names this instance. Another process took the name while the step
    hung (the scheduler said it is the current `w-1`): the stand-in leaves its row exactly as it is, renews no
    lease of the zombie's, and stops standing in for that step."""
    box = Box()
    w = _holder(box)
    w.take_epoch("1")
    w.renew_leases()
    with w.guarded("pass"):
        _tick(box, 10)
        _holder(box, name="w-1", instance="other:1")                # takes w-1 by preference, from a live holder
        theirs = _slot_row(box, w)
        stamp = w.leases["1"].last_renewal
        _tick(box, 5)
        assert not w.stand_in_once()
        row = _slot_row(box, w)
        assert (row.holder, row.gen, row.until) == ("other:1", theirs.gen, theirs.until), "the stand-in wrote over another instance's slot"
        assert w.leases["1"].last_renewal == stamp, "the stand-in renewed a lease for an instance that is nobody"
        for _ in range(4):
            _tick(box, 5)
            assert not w.stand_in_once()
        assert not w.may_write("1")
    assert w.stand_in_renewals == 0


def test_a_fenced_worker_is_not_revived_by_the_stand_in():
    """Two fences, neither undone. An instance its subsystem fenced (here: the store's schema raised past it —
    the one fence that leaves the slot row naming it) gets no renewal of anything; a lease fenced by a newer
    epoch stays fenced through the stand-in's renewal, and the loop, when it comes back, gives that camera up."""
    box = Box()
    w = _holder(box)
    w.take_epoch("1")
    w.renew_leases()
    w.fence("the store's schema is 2; this build understands 1")
    until = _slot_row(box, w).until
    stamp = w.leases["1"].last_renewal
    with w.guarded("pass"):
        _tick(box, 15)
        assert not w.stand_in_once()
    assert _slot_row(box, w).until == until, "the stand-in renewed the slot row of a fenced instance"
    assert w.leases["1"].last_renewal == stamp

    box = Box()
    w = _holder(box)
    w.take_epoch("1")
    w.renew_leases()
    next_epoch(box.vars, w.sub.epoch_key("1"))                      # another worker started camera 1
    with w.guarded("pass"):
        _tick(box, 15)
        assert w.stand_in_once()                                   # the slot is still its own: renewed
        assert w.leases["1"].fenced and not w.may_write("1")
        _tick(box, 10)
        w.stand_in_once()
        assert w.leases["1"].fenced and not w.may_write("1"), "the stand-in revived a fenced lease"
    assert w.lease_pass() == ["1"]
    assert w.recording_allowed                                     # one camera given up, not the instance


def test_a_lease_the_loop_released_is_renewed_by_nobody():
    """The loop stopped the camera while the stand-in held its lease from before: the stand-in does not renew it,
    and a renewal already in flight when the lease is let go stamps nothing."""
    box = Box()
    w = _holder(box)
    w.take_epoch("1")
    lease = w.leases["1"]
    with w.guarded("pass"):
        _tick(box, 15)
        w.release("1")
        stamp = lease.last_renewal
        assert w.stand_in_once()                                   # the slot is renewed…
        assert lease.last_renewal == stamp                         # …the released lease is not
        assert not lease.renew()

    class _LetGoMidway:                                            # the loop releases while the stand-in asks the store
        def __init__(self, inner): self.inner = inner
        def get(self, key):
            out = self.inner.get(key)
            mid.release()
            return out
    box = Box()
    mid = Lease(None, "vms/epoch/1", next_epoch(box.vars, "vms/epoch/1")[0], clock=box.clock)
    mid.vars = _LetGoMidway(box.vars)
    _tick(box, 10)
    stamp = mid.last_renewal
    assert not mid.renew()
    assert mid.last_renewal == stamp, "a renewal in flight stamped a lease released under it"


def test_two_renewals_in_flight_never_move_a_lease_backwards():
    """The loop and the stand-in renew the same lease. The one that asked the store first may answer last; its
    stamp is the older one, and it must not overwrite the younger."""
    box = Box()
    key = "vms/epoch/1"
    epoch, _ = next_epoch(box.vars, key)
    lease = Lease(None, key, epoch, clock=box.clock)

    class _Slow:                                                   # while the first renewal waits, the second runs whole
        def __init__(self, inner): self.inner, self.first = inner, True
        def get(self, k):
            if self.first:
                self.first = False
                box.clock.advance(3)
                assert lease.renew()
            return self.inner.get(k)
    lease.vars = _Slow(box.vars)
    _tick(box, 10)
    asked_first = box.clock()
    assert lease.renew()
    assert lease.last_renewal == asked_first + 3, "the slower renewal stamped its older time over the newer one"


def test_the_stand_in_renews_the_place_only_while_it_is_this_instances():
    """The place (a recorder's volume) lapses as fast as the slot. Renewed for a hung step while the row names
    this instance; taken by another, it is neither written over nor let go of here — losing it is the loop's."""
    box = Box()
    sub = Subsystem("t")
    w = Worker(sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance="me:1")
    w.claim_slot(prefer="t-1")
    assert w.claim_hold(["vol"]) == "vol"
    with w.guarded("pass"):
        _tick(box, 30)
        assert w.stand_in_once()
        row = Slot.from_items("vol", box.vars.get(sub.hold_key("vol"))[0])
        assert row.holder == "me:1" and row.until == box.wall() + w.slot_ttl
        items, idx = box.vars.get(sub.hold_key("vol"))
        box.vars.put(sub.hold_key("vol"), Slot("vol", "other:1", box.wall() + 45, False, row.gen + 1).to_items(), cas=idx)
        _tick(box, 10)
        assert w.stand_in_once()
        assert Slot.from_items("vol", box.vars.get(sub.hold_key("vol"))[0]).holder == "other:1"
        assert w.hold == "vol"                                     # the loop's renew_hold finds out, not the stand-in


def test_a_normal_fast_loop_never_calls_the_stand_in():
    """Passes of a second each, renewing as the loop does: no step runs long enough, and the stand-in renews
    nothing — not even once."""
    box = Box()
    w = _holder(box)
    w.take_epoch("1")
    lease_every = max(1.0, (w.lease_ttl - w.lease_margin) / 3)
    last = -1e9
    for _ in range(100):
        with w.guarded("pass"):
            _tick(box, 1)
            assert not w.stand_in_once()
        if box.clock() - last >= lease_every:
            with w.guarded("lease"):
                w.lease_pass()
            last = box.clock()
        _tick(box, 1)                                              # the loop's wait between passes
    assert w.stand_in_renewals == 0


# -- every worker's `run` has a stand-in ----------------------------------------------------------------------

def _all_workers(box):
    from vms.autoworker import AutoWorker
    from tests.test_pass_failures import _workers
    from vms.config import AUTO_SPEC
    from w2cplatform.contract import requests_acl
    auto = AutoWorker("a-1", box.vars.as_writer("autoworker", AUTO_SPEC.sub.acl_worker() + requests_acl("vms", "rec")),
                      box.objects, clock=box.clock, wall=box.wall, server="srv-1", archive_root=box.archive, env={})
    return [_holder(box)] + _workers(box) + [auto]


def _wait_for(cond, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.005)
    return False


def test_every_workers_loop_has_a_stand_in_for_a_pass_that_hangs():
    """The real `run` of each worker — the holder (and so the recorder, which inherits it), the detector, the scan,
    the survey, the gateway, the evaluator — with the real stand-in thread looking every 10 ms. The pass hangs for
    thirty seconds of the box's clock, past the lease; inside it, the lease still allows writes."""
    box = Box()
    for w in _all_workers(box):
        w.STAND_IN_WAKE = 0.01
        w.take_epoch("u")
        w.renew_leases()
        stop, seen = threading.Event(), {}

        def hung(*a, w=w, **kw):
            if seen:
                stop.set(); return []
            _tick(box, 20)
            _wait_for(lambda: getattr(w, "stand_in_renewals", 0) >= 1)
            _tick(box, 10)                                         # thirty seconds since the last renewal by the loop
            _wait_for(lambda: getattr(w, "stand_in_renewals", 0) >= 2)
            seen["may_write"] = w.may_write("u")
            return []

        w.reconcile_once = hung
        t = threading.Thread(target=w.run, kwargs={"poll": 0.01, "stop": stop}, daemon=True)
        t.start(); t.join(10)
        assert not t.is_alive(), type(w).__name__
        assert seen.get("may_write"), f"{type(w).__name__}: the lease ran out under a hung pass — no stand-in in its loop"


def test_a_fast_run_starts_the_stand_in_and_it_renews_nothing():
    """The same loops, passing quickly: the stand-in is there and has nothing to do."""
    box = Box()
    for w in _all_workers(box):
        w.STAND_IN_WAKE = 0.01
        w.take_epoch("u")
        w.renew_leases()                                           # the box's clock moved on since it was made
        stop, passes = threading.Event(), []

        def quick(*a, w=w, **kw):
            _tick(box, 1)
            passes.append(1)
            if len(passes) >= 40:
                stop.set()
            time.sleep(0.005)                                      # long enough for the stand-in to look
            return []

        w.reconcile_once = quick
        w.run(poll=0, stop=stop)
        assert w.stand_in_renewals == 0, type(w).__name__


def test_every_loop_keeps_its_slot_row_and_a_name_another_instance_took_is_given_up():
    """Found beside the stand-in: the detector, scan, survey and gateway loops claimed their slot once and never
    renewed it, so the row lapsed after `slot_ttl` in ordinary work and anybody could take a live worker's name.
    Their lease step keeps the slot row now (`Worker.keep_slot`); a row that names another instance is a name given up —
    the units let go, their epochs released, a free slot claimed."""
    from tests.test_pass_failures import _workers
    box = Box()
    for w in _workers(box):
        name = w.name
        stop, passes = threading.Event(), []

        def pass_(*a, **kw):
            passes.append(1)
            _tick(box, 30)                                         # each pass is thirty seconds of the box's clock
            if len(passes) >= 3:
                stop.set()
            return []

        w.reconcile_once = pass_
        w.run(poll=0.0, stop=stop)                                 # ninety seconds: twice the slot's own ttl
        row = _slot_row(box, w, name)
        assert row.holder == w.instance and row.until > box.wall() - 30, type(w).__name__   # renewed by the loop, not lapsed
    box = Box()
    for w in _workers(box):
        w.take_epoch("u")
        was = w.name
        box.vars.put(w.sub.slot_key(was), Slot(was, "somebody-else", box.wall() + 45, False, 9).to_items())
        lost = w.keep_slot(lambda: None)
        assert lost == ["u"] and "u" not in w.epochs and w.name != was, type(w).__name__
