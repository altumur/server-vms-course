"""A worker and a store that stops answering — and what a lost lease means (feedback BC).

Three rules, each learned on the product's box with the store of one cluster taken away (`chmod 000`):

    not knowing is not "no"    a store that did not answer says nothing: the worker goes on with the assignment it
                               read last, and its slot is still its own. Only a slot row READ, with another holder
                               in it, says "no"
    a lease is one unit's      lost however it was lost, one unit's work stops and gives its epoch up; if the unit
                               is still this worker's it is started again under a new epoch. The instance is not
                               fenced, and its other units are not stopped
    a fence is not for ever    a fenced instance takes a free slot on its next pass and starts from nothing

On testsub (`testdata/testsub.subsystem.yaml`): a unit is a named counter, `c1`…; a worker is `CounterWorker`, and what
it runs is `running`. What a subsystem's own worker does with these answers — its pipelines, the place it writes in —
is that subsystem's tests' (`test_holders_through_a_silent_store.py`).
"""
from w2cplatform.contract import NotReadThisPass
from w2cplatform.epoch import Lease, current_epoch, next_epoch
from tests.conftest import Box, controller, counter_worker, testsub


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


def _box_with_counters(n=2):
    """A box and testsub's controller over the whole store, with counters `c1`…`c<n>`."""
    box = Box()
    ctl = controller(box)
    for i in range(1, n + 1):
        ctl.create({"name": f"c{i}"})
    return box, ctl


def _names(n, first=1):
    return [f"c{i}" for i in range(first, n + 1)]


def _worker(n=2, unconfirmed_max=None):
    """w-1 running `c1`…`c<n>` on a store with a switch. Its units write data, so a lease that runs out in silence
    goes on under its epoch up to `unconfirmed_max` past its end (`None`: for as long as the silence lasts; `0`: not
    at all) — the subsystem's knob, set before any epoch is taken."""
    box, ctl = _box_with_counters(n)
    ctl.assign("w-1", _names(n))
    store = Flaky(box.vars)
    w = counter_worker(box, "w-1", vars_=store)
    w.unconfirmed_max = unconfirmed_max
    w.reconcile_once()
    assert w.running == {u: 1 for u in _names(n)}
    return box, ctl, store, w


def test_a_store_that_does_not_answer_is_not_an_empty_assignment():
    """Sixteen seconds without the store: the counters run under the same epochs, nothing is fenced, the pass goes
    on with the assignment read last — and for a unit whose work fell over meanwhile the platform has the two answers
    a subsystem restarts it from: no NEW epoch on an assignment that did not answer, and the epoch it holds still
    good for data."""
    box, ctl, store, w = _worker()
    store.down = True
    box.clock.advance(16); box.wall.advance(16)
    assert w.reconcile_once() == ["c1", "c2"] and w.stopped == []    # nothing stopped: the last assignment stands
    assert w.lease_pass() == [] and w.writing_allowed               # the slot: not confirmed, and still mine
    assert w.running == {"c1": 1, "c2": 1} and w.epochs == {"c1": 1, "c2": 1} and w.store_errors == 2
    try:
        w.take_epoch("c1"); raise AssertionError("a new epoch on an assignment that did not answer")
    except NotReadThisPass:
        pass
    assert w.may_write("c1") and w.epochs == {"c1": 1, "c2": 1}     # the same writer — nobody could be given another number
    store.down = False
    assert w.lease_pass() == [] and w.reconcile_once() == ["c1", "c2"] and w.epochs == {"c1": 1, "c2": 1}
    assert current_epoch(box.vars, testsub().sub.epoch_key("c1")) == 1


def test_a_lease_that_ran_out_with_nobody_asking_stops_that_unit_and_it_comes_back_under_a_new_epoch():
    """Thirty-six seconds in which this worker asked nothing — a GC pause, a suspended VM — and then a store
    that does not answer. That is not silence (feedback BK): the lease ran out while nobody was asking, and
    somebody may have been given the units meanwhile. They stop — each with the reason in the log — and the
    instance is NOT fenced. The store returns, and the next pass starts them again under the next epoch.
    Silence counts from a renewal that failed while the lease was still good; see the tests at the end."""
    box, ctl, store, w = _worker()
    store.down = True
    box.clock.advance(36); box.wall.advance(36)
    assert sorted(w.lease_pass()) == ["c1", "c2"]
    assert w.running == {} and w.epochs == {} and w.writing_allowed and w.fenced_reason is None
    assert sorted(w.stopped) == ["c1", "c2"]
    store.down = False
    box.clock.advance(60); box.wall.advance(60)                       # past any backoff
    w.reconcile_once()
    assert w.running == {"c1": 2, "c2": 2}
    assert w.lease_pass() == []


def test_a_unit_in_two_assignments_costs_one_unit_not_fifty():
    """Counter c1 is listed on two workers for the seconds a controller takes to mend it. The other worker took the
    next epoch. This worker used to read that as "another instance of me holds it: I am a zombie" and stop every
    unit it had. Its slot was renewed a line before — there is no other instance of it."""
    box, ctl, store, w = _worker()
    next_epoch(box.vars, testsub().sub.epoch_key("c1"))               # somebody else started c1
    assert w.lease_pass() == ["c1"]
    assert w.writing_allowed and w.running == {"c2": 1} and "c1" not in w.epochs
    assert w.conflicts() == 0 and w.lease_pass() == []                # c2 is untouched; nothing left to lose


def test_only_a_slot_row_naming_another_holder_fences_and_a_fence_is_not_for_ever():
    """The replacement took w-1. The old instance reads the slot row, finds another holder and fences — that is a
    "no". It used to stay so: alive, heartbeating `fenced: true`, doing nothing until somebody restarted it.
    On its next pass it takes a free slot and starts from nothing — a process that took whatever was free; one named by
    its unit takes its own name back only (`test_names.py`)."""
    from w2cplatform.contract import HUNG_MOVE_AFTER
    box, ctl, store, a = _worker(1)
    a.given = None                                                    # not named by its unit: any free slot will do
    ctl.look()
    box.wall.advance(91 + HUNG_MOVE_AFTER)                            # a long pause: the slot lapsed, the margin out,
    assert "w-1" in ctl.publish_names()["names_given"]                # and the controller gives its name (the 13th pass)
    b = counter_worker(box, None)
    assert b.name == "w-1"
    assert a.lease_pass() == ["c1"] and not a.writing_allowed and "slot w-1" in a.fenced_reason
    assert a.rejoin() == "w-2" and a.writing_allowed and a.was_fenced and a.fenced_reason is None
    assert a.epochs == {} and a.rows == {} and a.running == {}
    ctl.assign("w-2", ["c1"])
    assert a.reconcile_once() == ["c1"] and a.running == {"c1": 2}    # whatever ITS slot's assignment says, from nothing
    assert b.lease_pass() == []                                       # and the replacement never noticed


def test_a_lease_runs_from_before_the_read_not_from_after_it():
    """A holder paused for a minute between reading the epoch row and stamping the renewal woke up with a fresh
    lease it had in fact slept through."""
    box, ctl = _box_with_counters(1)
    key = testsub().sub.epoch_key("c1")
    epoch, _ = next_epoch(box.vars, key)

    class Slow:
        def get(self, key):
            out = box.vars.get(key)
            box.clock.advance(60)                                     # the pause: a GC, a stalled disk
            return out

    lease = Lease(Slow(), key, epoch, 30.0, 5.0, box.clock)
    assert lease.renew() is True                                      # the row said "yours" — a minute ago
    assert lease.may_act() is False and lease.seconds_left() == 0


def test_the_pump_does_not_wait_for_the_pass_over_the_store():
    """The pump — what a subsystem drains beside the pass, and the requests — runs whether or not the pass
    succeeded. They shared one `try`, and a pass that raised skipped the pump, every pass."""
    box, ctl, store, w = _worker(1)
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


# -- working through a silent store (feedback BK) -------------------------------------------------------

def _silence(box, w, seconds, step=8):
    """The loop, for `seconds`: a lease pass and a reconcile every `step` — the store asked each time."""
    out = []
    for _ in range(int(seconds // step)):
        box.clock.advance(step); box.wall.advance(step)
        out += w.lease_pass()
        w.reconcile_once()
    return out


def test_ten_minutes_of_silence_stop_nothing_and_the_store_coming_back_stops_nothing_either():
    """A lease that ran out while the store was SILENT is not a lease somebody took. Units that write data go on
    under the epochs they have — a write under an old epoch harms nothing: the epoch is in the path, and a second
    writer would cost a duplicate, where stopping costs a hole. On one box there is nobody to protect them from: the
    store is a directory on the same disk, away for everybody at once. The subsystem says so: no ceiling."""
    box, ctl, store, w = _worker(unconfirmed_max=None)
    store.down = True
    assert _silence(box, w, 600) == [] and w.running == {"c1": 1, "c2": 1} and w.stopped == []
    assert not w.may_act("c1") and w.may_write("c1")               # the strict question says no; the data one says yes
    assert sorted(w.unconfirmed()) == ["c1", "c2"] and 570 <= w.unconfirmed()["c1"] <= 580

    store.down = False
    assert w.lease_pass() == [] and w.running == {"c1": 1, "c2": 1} and w.epochs == {"c1": 1, "c2": 1}   # confirmed: no stop, no seam
    assert w.may_act("c1") and w.unconfirmed() == {}


def test_a_unit_given_to_somebody_else_during_the_silence_stops_at_the_stores_first_answer():
    box, ctl, store, w = _worker()
    store.down = True
    _silence(box, w, 120)
    next_epoch(box.vars, testsub().sub.epoch_key("c1"))               # another worker reached the store and started c1
    store.down = False
    assert w.lease_pass() == ["c1"] and w.running == {"c2": 1} and w.writing_allowed


def test_the_ceiling_and_off():
    """A cluster's store is on the network: a worker cut off from it may hold a unit while its successor cannot
    connect. `unconfirmed_max` is how long past the lease's end it writes on; `0` is the old behaviour — a lease not
    confirmed in time stops its unit."""
    box, ctl, store, w = _worker(unconfirmed_max=60.0)
    store.down = True
    assert _silence(box, w, 80) == [] and w.running == {"c1": 1, "c2": 1}   # 25 s of lease + 55 s unconfirmed: under the ceiling
    assert sorted(_silence(box, w, 16)) == ["c1", "c2"] and w.running == {} and w.writing_allowed

    box, ctl, store, w = _worker(unconfirmed_max=0.0)
    store.down = True
    assert _silence(box, w, 24) == [] and sorted(_silence(box, w, 8)) == ["c1", "c2"]


def test_a_unit_never_started_waits_and_an_action_waits_for_the_stores_word():
    """Data goes on; two things do not. A unit this worker has not started has no epoch to write under — it
    waits. And a request is not data: an action taken by a worker that may have been replaced is taken twice."""
    box, ctl, store, w = _worker()
    ctl.create({"name": "c3"})
    ctl.assign("w-1", _names(3)); w.refresh()                         # assigned, and not yet started
    store.down = True
    _silence(box, w, 40)
    assert w.may_write("c1") and "c3" not in w.epochs                # no epoch for it: it waits
    assert "c3" not in w.running

    store.down = False
    box.vars.put(testsub().sub.request_key("r1"), {"unit": "c1", "add": "2", "valid_until": str(box.wall() + 60)})
    w.leases["c1"].vars = Flaky(box.vars); w.leases["c1"].vars.down = True     # the row is read; the lease is still unconfirmed
    assert w.requests() == [] and w.counts["c1"] == 0                 # not performed
    w.leases["c1"].vars.down = False
    w.lease_pass()
    assert [d["request"] for d in w.requests()] == ["r1"] and w.counts["c1"] == 2   # confirmed: it acts


class OneRead(Flaky):
    """…and a switch for single keys: a read of one of them is an OSError, every other call answers — a store or a
    door that answered 503 for that one read (the product's cross-check)."""

    def __init__(self, inner):
        super().__init__(inner)
        self.refused: set[str] = set()

    def get(self, key, *a, **kw):
        if key in self.refused:
            raise ConnectionError(f"503 for {key}")
        return self.inner.get(key, *a, **kw)


def _moved_away(n=2):
    """w-1 holds `c1`…`c<n>` on a store that can refuse one read. c1 goes to w-2, which starts it under epoch 2;
    w-1's lease step finds the newer epoch and lets c1 go."""
    box, ctl = _box_with_counters(n)
    ctl.assign("w-1", _names(n))
    store = OneRead(box.vars)
    w = counter_worker(box, "w-1", vars_=store)
    assert len(w.reconcile_once()) == n
    w2 = counter_worker(box, "w-2")
    ctl.assign("w-1", _names(n, 2)); ctl.assign("w-2", ["c1"])
    assert w2.reconcile_once() == ["c1"] and w2.running == {"c1": 2}
    assert w.lease_pass() == ["c1"] and "c1" not in w.running
    return box, store, w, w2


def test_a_worker_whose_assignment_read_failed_takes_no_new_epoch_on_the_assignment_it_read_before():
    """The product's cross-check (A): the old holder's read of its assignment failed — one 503 — and the pass went on
    with the assignment read before, which still named c1; the pass started it, and the epoch CAS, which the store did
    answer, gave it epoch 3 over the worker the unit had moved to. The new holder was fenced by one that had not read
    its assignment since. Rule: a new epoch only for a unit of the assignment read this pass."""
    box, store, w, w2 = _moved_away()
    store.refused = {testsub().sub.assignment("w-1")}
    box.clock.advance(60); box.wall.advance(60)                       # past any backoff
    assert w.reconcile_once() == ["c2"] and w.started.count("c1") == 1   # c1 is not started from the old list
    assert current_epoch(box.vars, testsub().sub.epoch_key("c1")) == 2
    assert w2.lease_pass() == [] and w2.running == {"c1": 2}         # …and its new holder is not fenced
    store.refused = set()
    box.clock.advance(60); box.wall.advance(60)
    assert w.reconcile_once() == ["c2"] and w.started.count("c1") == 1   # read again: c1 is not its own


def test_a_worker_whose_unit_row_read_failed_takes_no_epoch_for_a_unit_its_new_assignment_does_not_name():
    """The sibling the product did not name: the assignment answered — c1 is gone from it — but the read of c2's row
    did not, and the pass went on with the rows of the pass before, c1's among them. c1 is not the fresh assignment's:
    no epoch is taken for it."""
    box, store, w, w2 = _moved_away()
    store.refused = {testsub().sub.config(testsub().rows, "c2")}
    box.clock.advance(60); box.wall.advance(60)
    assert w.reconcile_once() == ["c2"] and w.started.count("c1") == 1
    assert current_epoch(box.vars, testsub().sub.epoch_key("c1")) == 2
    assert w2.lease_pass() == [] and w2.running == {"c1": 2}
