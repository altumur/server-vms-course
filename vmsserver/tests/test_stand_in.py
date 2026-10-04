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


def test_the_stand_in_does_not_hold_the_place_for_a_step_on_a_silent_engine_and_says_what_it_renewed():
    """The review's fifth pass, a minor. The stand-in renewed a recorder's network volume for five minutes while the
    step stood on a daemon that had already answered `Unavailable`: nothing was being written, and no box whose daemon
    answers could take the volume. A subsystem says whether the place is worth holding for the step
    (`may_stand_in_hold`), and a renewal the stand-in does make is told, from before the store was asked
    (`note_hold_confirmed`) — what a recorder fences every sample by."""
    box = Box()
    sub = Subsystem("t")
    w = Worker(sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance="me:1")
    w.claim_slot(prefer="t-1")
    assert w.claim_hold(["vol"]) == "vol"
    told, silent = [], [True]
    w.note_hold_confirmed = told.append
    w.may_stand_in_hold = lambda: not silent[0]
    with w.guarded("pass"):
        _tick(box, 30)
        before = Slot.from_items("vol", box.vars.get(sub.hold_key("vol"))[0]).until
        assert w.stand_in_once()                                   # the slot and the leases: still renewed
        assert Slot.from_items("vol", box.vars.get(sub.hold_key("vol"))[0]).until == before and told == []
        silent[0] = False
        _tick(box, 10)
        assert w.stand_in_once()
        assert Slot.from_items("vol", box.vars.get(sub.hold_key("vol"))[0]).until == box.wall() + w.slot_ttl
        assert told == [box.clock()]


def test_STAND_IN_FOR_counts_from_the_loops_last_renewal_and_a_new_step_does_not_start_it_again():
    """The review's fifth pass, a minor. Five minutes were counted from each step's start: a loop that came back from
    one hung step and went straight into another, renewing nothing in between, was given five minutes more each
    time. They are counted from the loop's own last renewal now."""
    box = Box()
    w = _holder(box)
    w.take_epoch("1")
    w.renew_leases()
    with w.guarded("pass"):
        while box.clock() - 1000 + 5 <= w.STAND_IN_FOR - 60:
            _tick(box, 5)
            w.stand_in_once()
    assert w.may_write("1")                                        # four minutes stood in for: the camera still held
    with w.guarded("pump"):                                        # the next step, and the loop renewed nothing between
        for _ in range(24):                                        # two more minutes
            _tick(box, 5)
            w.stand_in_once()
        assert not w.may_write("1"), "a second hung step was given five more minutes of somebody else's camera"


def test_STAND_IN_FOR_is_not_started_again_by_a_renewal_inside_the_step_that_then_hangs():
    """The review's sixth pass (П-m2). The lease step renews first and works after — and hung there, it had renewed a
    moment ago by its own count: every such step was given five minutes more, six in a row held a camera and a place
    for 1680 s. The five minutes run from before the FIRST step that had to be stood in for, and start again only after
    a step in which the loop renewed and needed nobody."""
    box = Box()
    w = _holder(box)
    w.claim_hold(["vol"])
    w.take_epoch("1")
    start, held_until = box.clock(), None
    for _ in range(6):                                             # six lease steps, each renewing and then hung 280 s
        with w.guarded("lease"):
            w.lease_pass()
            for _ in range(56):
                _tick(box, 5)
                w.stand_in_once()
                if held_until is None and not w.may_write("1"):
                    held_until = box.clock()
    assert held_until is not None, "a loop that hangs in every lease step held its camera for 1680 s"
    assert held_until - start <= w.STAND_IN_FOR + w.lease_ttl      # five minutes of standing in, and the lease's own term
    assert Slot.from_items("vol", box.vars.get(w.sub.hold_key("vol"))[0]).until < box.wall()   # …and its place lapsed too

    with w.guarded("lease"):                                       # the loop works again: a step that renews and returns
        w.lease_pass()
    w.take_epoch("1")
    with w.guarded("pass"):                                        # …and the next hung step is stood in for afresh
        _tick(box, 60)
        assert w.stand_in_once() and w.may_write("1")


def test_a_place_another_host_may_write_does_not_follow_the_name_and_a_released_one_is_taken_at_once():
    """The review's sixth pass, blocker 2, in the platform's terms. An instance that takes a worker's name takes its
    place back at once (feedback CF) — unless the subsystem says the place can be written from another host
    (`hold_follows_name`): then it waits like anybody, the row unchanged for `slot_ttl + HOLD_SKEW` by its own clock,
    because that wait is what the previous holder's write window is measured against. Released, it is free at once."""
    sub = Subsystem("t")

    def worker(box, instance):
        w = Worker(sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance=instance)
        w.hold_follows_name = lambda place, holder: place != "net"  # what a recorder says of a network volume held elsewhere
        w.claim_slot(prefer="t-1")
        return w
    box = Box()
    first = worker(box, "first:1")
    assert first.claim_hold(["disk"]) == "disk"
    again = worker(box, "again:1")                                 # the same name, another instance
    assert again.claim_hold(["disk"]) == "disk"                    # a place of one host: at once, as before

    box = Box()
    first = worker(box, "first:1")
    assert first.claim_hold(["net"]) == "net"
    again = worker(box, "again:1")
    assert again.claim_hold(["net"]) is None                       # may be written from another host: not at once
    _tick(box, again.slot_ttl + again.HOLD_SKEW - 1)
    assert again.claim_hold(["net"]) is None
    _tick(box, 1)
    assert again.claim_hold(["net"]) == "net"                      # the row stood still a term and the skew
    again.release_hold()
    third = worker(box, "third:1")
    assert third.claim_hold(["net"]) == "net"                      # let go on purpose: at once


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
    the units let go, their epochs released — and, named by its unit, nothing else claimed: it waits for its own."""
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
        # …and no other name taken: it was started under this one, and waits for it (the owner's decision of 4 Oct)
        assert lost == ["u"] and "u" not in w.epochs and w.slot is None and w.seeking == was, type(w).__name__
        assert sorted(p.rsplit("/", 1)[1] for p in box.vars.list(w.sub.name + "/slots/")) == [was], type(w).__name__


# -- the stand-in's heartbeat (the scaling pass after the eighth review) ---------------------------------------------

def _hb(box, w):
    return Heartbeat.from_bytes(box.objects.get(w.sub.heartbeat_key(w.name)))


def test_a_hung_step_does_not_make_the_holder_look_dead_and_the_heartbeat_says_whose_words_it_repeats():
    """The stand-in renewed the leases and the slot and wrote no heartbeat: 45 s into a hung step the controller and the
    recorders judged the holder dead while its leases were held for five minutes. Now, while it stands in, it says the
    loop's LAST heartbeat again — the same status, a new `ts`, `stood_in` with the step, how long, and `as_of` (the `ts`
    of the heartbeat whose status it is) — whenever the last one is `STAND_IN_HEARTBEAT` old; never anything it computed.
    A minute hung: no moment with a heartbeat older than `lost_after`. Back, the loop's own heartbeat says no `stood_in`."""
    box = Box()
    w = _holder(box)
    w.take_epoch("1")
    w.renew_leases()
    w.heartbeat_once()
    loop = _hb(box, w)
    oldest = 0.0
    with w.guarded("pass"):
        for _ in range(30):                                         # 30 × 2 s, a look of the stand-in each
            _tick(box, 2)
            w.stand_in_once()
            hb = _hb(box, w)
            oldest = max(oldest, box.wall() - hb.ts)
        assert hb.ts > loop.ts and hb.status == loop.status
        assert hb.extra["stood_in"]["step"] == "pass" and hb.extra["stood_in"]["as_of"] == loop.ts
        assert hb.extra["stood_in"]["for"] >= 50 and hb.extra["stand_in_renewals"] == w.stand_in_renewals
    # the first one goes with the stand-in's first renewal; after it, one every `STAND_IN_HEARTBEAT` and a look
    assert oldest <= max(w.stand_in_after() + w.STAND_IN_WAKE, w.STAND_IN_HEARTBEAT + w.STAND_IN_WAKE) < 45.0, oldest
    w.heartbeat_once()
    assert "stood_in" not in _hb(box, w).extra                     # the loop's own words again


def test_the_stand_in_says_no_heartbeat_over_a_fresh_one_nor_under_a_name_another_instance_took():
    """It writes only when the last heartbeat — the loop's or its own — is `STAND_IN_HEARTBEAT` old: a loop that wrote
    one a moment ago is not overwritten with an older status. And a slot another instance took ends its standing in
    before it says anything under that name."""
    box = Box()
    w = _holder(box)
    w.take_epoch("1")
    w.renew_leases()
    w.heartbeat_once()
    with w.guarded("heartbeat"):
        _tick(box, 14)
        w.heartbeat_once()                                          # the loop wrote one inside the step
        fresh = _hb(box, w)
        assert w.stand_in_once()                                    # it renews the leases…
        assert _hb(box, w) == fresh                                 # …and leaves the fresh heartbeat as it is
    box2 = Box()
    v = _holder(box2)
    v.take_epoch("1")
    v.renew_leases()
    v.heartbeat_once()
    before = _hb(box2, v)
    box2.vars.put(v.sub.slot_key(v.name), Slot(v.name, "somebody-else", box2.wall() + 45, False, 9).to_items())
    with v.guarded("pass"):
        for _ in range(10):
            _tick(box2, 5)
            v.stand_in_once()
    assert _hb(box2, v) == before                                   # nothing said under a name that is not its own


def test_every_workers_stand_in_says_its_last_heartbeat_again_for_a_pass_that_hangs():
    """The real `run` of each worker, with the real stand-in thread: a pass hung thirty seconds of the box's clock, and
    the heartbeat under the worker's name is re-dated inside it — `stood_in` names the pass."""
    box = Box()
    for w in _all_workers(box):
        w.STAND_IN_WAKE = 0.01
        w.take_epoch("u")
        w.renew_leases()
        stop, seen = threading.Event(), {}

        def said_again(w=w):
            raw = w.objects.get(w.sub.heartbeat_key(w.name))
            return raw is not None and "stood_in" in Heartbeat.from_bytes(raw).extra

        def hung(*a, w=w, **kw):
            if seen:
                stop.set(); return []
            _tick(box, 20)
            _wait_for(lambda: getattr(w, "stand_in_renewals", 0) >= 1)
            _tick(box, 10)
            _wait_for(said_again)
            seen["hb"] = Heartbeat.from_bytes(w.objects.get(w.sub.heartbeat_key(w.name)))
            return []

        w.reconcile_once = hung
        t = threading.Thread(target=w.run, kwargs={"poll": 0.01, "stop": stop}, daemon=True)
        t.start(); t.join(10)
        assert not t.is_alive(), type(w).__name__
        hb = seen.get("hb")
        assert hb is not None and hb.extra.get("stood_in", {}).get("step") == "pass", f"{type(w).__name__}: {hb and hb.extra}"
        assert box.wall() - hb.ts <= w.STAND_IN_HEARTBEAT, type(w).__name__
