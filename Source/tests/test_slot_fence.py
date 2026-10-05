"""A slot given up and no other taken: the instance is nobody until it has one (the review's fifth pass, blocker 3).

`keep_slot` reads a slot row naming another instance, lets its units go and claims a free slot. When that claim
failed — the store blinked, every candidate was taken under it — the worker was left with no slot and its OLD
name: `renew_slot` with no slot said "still me", the stand-in renewed for it, the next pass read the other
instance's assignment, took new epochs on its units with `may_act` true, and the heartbeat under that name was
written over the legitimate one. Two processes took the same units in turn, until a restart.

Now, while there is no slot, the instance is fenced: `renew_slot` says no, the stand-in does not stand in, no epoch
is taken, the assignment it reads is empty, no heartbeat goes out under the name, and every lease step tries the
claim again — as `Worker.rejoin` does for a fenced instance. A test of the platform alone, on testsub: the worker is
testsub's (`CounterWorker`), by both paths — a loop's own lease step by `keep_slot`, and `Worker.run`'s by
`lease_pass`, `fence` and `rejoin`. That every kind of a subsystem's worker keeps to it is that subsystem's to show.
"""
from w2cplatform.contract import Heartbeat, Slot
from tests.conftest import Box, controller, counter_worker, testsub


def _worker(box, name="w-1", **kw):
    """testsub's worker, started under `name` by its unit."""
    return counter_worker(box, name, **kw)


def _taken(box, w):
    """Another instance takes this worker's slot — a restarted process given the same name by its scheduler."""
    was = w.name
    box.vars.put(w.sub.slot_key(was), Slot(was, "somebody-else", box.wall() + 45, False, 9).to_items())
    box.objects.put(w.sub.heartbeat_key(was), Heartbeat(was, box.wall(), [], {"instance": "somebody-else"}).to_bytes())
    return was


def _let_go(box, w, was):
    """The other instance stops in order: its slot released, the name free for the process it was taken from."""
    box.vars.put(w.sub.slot_key(was), Slot(was, "somebody-else", box.wall(), True, 9).to_items())


class _Blink:
    """The store does not answer for a slot listing (the claim's first read) while `down`."""
    def __init__(self, vars_):
        self.vars, self.real, self.down = vars_, vars_.list, True

    def __enter__(self):
        def listing(prefix, *a, **kw):
            if self.down and "/slots/" in prefix:
                raise OSError("the store did not answer")
            return self.real(prefix, *a, **kw)
        self.vars.list = listing
        return self

    def __exit__(self, *exc):
        self.vars.list = self.real


class _OnePass:
    """One turn of a worker's `run`: the first `is_set` lets the pass in, the second ends the loop."""
    def __init__(self): self.asked = 0
    def is_set(self): self.asked += 1; return self.asked > 1
    def wait(self, s): return None


def _keep(w, let_go):
    """The lease step of a loop that keeps its slot by `keep_slot`: in a `try` of its own, so whatever it raises the
    loop goes on."""
    try:
        return w.keep_slot(let_go)
    except Exception:                                                  # noqa: BLE001
        return None


def test_a_worker_whose_slot_was_taken_and_whose_claim_failed_takes_nothing_and_says_nothing_under_that_name():
    """A worker that keeps its slot by `keep_slot`. The slot is taken by another instance, the claim of a free one
    fails on a store that blinks: the units it had are let go, no epoch is taken, the assignment of the name it gave
    up is not read, the stand-in renews nothing, and the other instance's heartbeat stands."""
    box = Box()
    w = _worker(box)
    w.take_epoch("u")
    was = _taken(box, w)
    box.vars.put(w.sub.assignment(was), {"units": "u,v", "rev": 5})   # the other instance's assignment
    let_go = []
    with _Blink(w.vars):
        lost = _keep(w, lambda: let_go.append(1))
        assert let_go and "u" not in w.epochs and not w.leases        # its units let go, epochs given up
        assert lost == ["u"], lost
        assert w.renew_slot() is False, "no slot, and renew_slot said 'still me'"
        assert w.may_stand_in() is False, "the stand-in would renew for an instance with no slot"
        assert w.assignment().units == [], "it reads the assignment of a name it gave up"
        epoch_row = box.vars.get(w.sub.epoch_key("v"))[0]
        try:
            w.take_epoch("v")
            raise AssertionError("an epoch was taken with no slot")
        except RuntimeError as e:                                      # `NoSlot`: nobody takes nothing
            assert type(e).__name__ == "NoSlot", repr(e)

        assert box.vars.get(w.sub.epoch_key("v"))[0] == epoch_row      # and nothing was written for it
        w.heartbeat_once()
        hb = box.objects.get(w.sub.heartbeat_key(was))
        assert b"somebody-else" in hb, "its heartbeat went out over the other instance's"
        assert _keep(w, lambda: None) == [] and w.renew_slot() is False   # tried again, still nobody
    # the store answers again — and the other instance holds the name live: still nobody, and no other number taken
    # (its name is the one it was started under: the owner's decision of 4 Oct, `test_names.py`)
    assert _keep(w, lambda: None) == [] and w.renew_slot() is False and w.slot is None
    _let_go(box, w, was)                                               # the other instance stops in order
    assert _keep(w, lambda: None) == []
    assert w.name == was and w.renew_slot() is True and w.may_stand_in() is True
    assert w.assignment().units == ["u", "v"]                          # its own name's list, read again — as its next pass does
    w.take_epoch("v")
    assert "v" in w.epochs and w.may_act("v")


def test_a_worker_with_no_slot_runs_nothing_of_the_name_it_gave_up():
    """The review's reproduction, on testsub: a worker whose slot another instance took while the store blinked. Its
    next pass, with the other instance's assignment naming a counter that exists, starts nothing: no epoch, nothing
    running."""
    box = Box()
    w = _worker(box)
    box.vars.put(w.sub.config("counters", "c7"), {"name": "c7"})
    was = _taken(box, w)
    box.vars.put(w.sub.assignment(was), {"units": "c7", "rev": 3})
    with _Blink(w.vars):
        _keep(w, lambda: None)
        w.reconcile_once()
        assert w.epochs == {} and box.vars.get(w.sub.epoch_key("c7"))[0] in (None, {})
    assert w.running == {} and w.started == []


def test_the_stand_in_does_not_renew_for_an_instance_with_no_slot():
    """The stand-in's look, by hand, under a step that has hung long enough to be stood in for: with no slot it
    renews nothing — no lease, no row."""
    box = Box()
    w = _worker(box)
    w.take_epoch("u")
    _taken(box, w)
    with _Blink(w.vars):
        _keep(w, lambda: None)
        with w.guarded("pass"):
            box.clock.advance(20); box.wall.advance(20)
            assert w.stand_in_once() is False and w.stand_in_renewals == 0


# -- `fence` and `rejoin`, the same rule (the review's sixth pass) -------------------------------------------------

def _nobody(box, w, was):
    """What an instance with no name does: nothing under the name it gave up."""
    w.heartbeat_once()
    assert b"somebody-else" in box.objects.get(w.sub.heartbeat_key(was)), "its heartbeat went out over the other instance's"
    assert w.renew_slot() is False and w.may_stand_in() is False
    assert w.assignment().units == [], "it reads the assignment of a name it gave up"
    w.reconcile_once()
    assert w.rows == {} and w.running == {} and w.epochs == {}, "it took up the other instance's units"
    try:
        w.take_epoch("c1")
        raise AssertionError("an epoch was taken with no slot")
    except RuntimeError as e:
        assert type(e).__name__ == "NoSlot", repr(e)


def test_a_fenced_worker_whose_rejoin_failed_says_nothing_under_the_name_another_instance_holds():
    """The review's sixth pass: the class of the fifth's blocker 3, on the path of a worker that fences and rejoins
    (`Worker.lease_pass`, `rejoin`). `rejoin` dropped its slot and claimed a free one; when the claim failed — the store
    blinked (the `OSError` went out of `rejoin`), or every candidate was taken under it — the instance was left with no
    slot and its OLD name, and `renew_slot` with no slot says "still me": its heartbeat (`fenced: true`) was written
    over the legitimate one, pass after pass. And between the fence and the first `rejoin` it said the same over the
    name another instance already held.

    Now the fence at the slot makes it nobody (`seeking`), `rejoin` goes through `_seek_slot`, and until a slot is
    claimed nothing is said, read or taken under the name."""
    box = Box()
    for name in ("c1", "c2"):
        box.vars.put(testsub().sub.config("counters", name), {"name": name})
    w = _worker(box)
    w.heartbeat_once()
    was = _taken(box, w)
    box.vars.put(w.sub.assignment(was), {"units": "c1,c2", "rev": 5})  # the other instance's assignment
    w.lease_pass()
    assert not w.writing_allowed and "held by another instance" in w.fenced_reason
    _nobody(box, w, was)                                                # fenced, before any `rejoin`: already nobody
    with _Blink(w.vars):                                                # the store blinks on the claim
        assert w.rejoin() is None and not w.writing_allowed
        _nobody(box, w, was)
        w.run(poll=0, stop=_OnePass())                                  # a turn of the real loop, and its orderly stop
        assert b"somebody-else" in box.objects.get(w.sub.heartbeat_key(was))
        row = Slot.from_items(was, box.vars.get(w.sub.slot_key(was))[0])
        assert row.holder == "somebody-else" and not row.released, "it released the other instance's slot"
    real = w._claim_slot                                                # …or every candidate is taken under it
    w._claim_slot = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("could not claim a slot in 50 tries"))
    assert w.rejoin() is None and not w.writing_allowed
    _nobody(box, w, was)
    w._claim_slot = real
    assert w.rejoin() is None and not w.writing_allowed                 # the store answers, the other holds it live:
    _nobody(box, w, was)                                                # its own name only (the owner's decision of 4 Oct)
    _let_go(box, w, was)                                                # the other instance stops in order
    name = w.rejoin()                                                   # somebody again — under its own name
    assert name == was and w.name == name and w.writing_allowed and w.seeking is None
    assert w.renew_slot() is True and w.assignment().units == ["c1", "c2"]   # the name's assignment with it
    w.heartbeat_once()
    assert w.instance.encode() in box.objects.get(w.sub.heartbeat_key(name))


def test_a_holder_fenced_for_the_schema_stops_speaking_when_another_instance_takes_its_name():
    """The sibling the review did not name. A store raised past the build fences the holder with its slot IN HAND:
    the name is still its own, and its heartbeat says `fenced` under it. But it renews nothing, the row lapses, and
    a new build takes the name — while the old one never read the row again (`renew_slot` raises on the schema
    before it gets there) and went on heartbeating over the new holder's. A fenced instance reads its row at every
    lease step now, and is nobody from the step that finds another holder there."""
    from w2cplatform.contract import SCHEMA, Controller
    box = Box()
    w = _worker(box)
    assert w.lease_pass() == []
    Controller(testsub().sub, box.vars, box.objects, wall=box.wall).set_schema(SCHEMA + 1)
    w.lease_pass()
    assert not w.writing_allowed and f"schema {SCHEMA + 1}" in w.fenced_reason and w.seeking is None
    w.heartbeat_once()                                                  # the name is still its own: it says so
    assert Heartbeat.from_bytes(box.objects.get(w.sub.heartbeat_key(w.name))).extra["fenced"] is True
    was = _taken(box, w)                                                # the row lapsed and a new build took the name
    w.lease_pass()
    assert w.seeking == was, "fenced for the schema, it did not notice its name was taken"
    w.heartbeat_once()
    assert b"somebody-else" in box.objects.get(w.sub.heartbeat_key(was)), "its heartbeat went out over the new holder's"


def test_a_worker_on_a_store_raised_past_its_build_is_nobody_once_another_instance_takes_its_name():
    """The same sibling in a loop that keeps its slot by `keep_slot`. There the renewal's refusal goes out of the
    lease step, every step — nothing is renewed, the row lapses — and the heartbeat, in a `try` of its own, went on
    under the name after a new build had taken it. From the step that reads another holder in the row the instance
    is nobody: its units let go, nothing said under the name, and no other slot claimed on a store past its build."""
    from w2cplatform.contract import SCHEMA, Controller
    box = Box()
    w = _worker(box)
    Controller(testsub().sub, box.vars, box.objects, wall=box.wall).set_schema(SCHEMA + 1)
    w.take_epoch("u")
    let_go = []
    assert _keep(w, lambda: let_go.append(1)) is None and w.seeking is None   # refused, and the name still its own
    w.heartbeat_once()
    assert box.objects.get(w.sub.heartbeat_key(w.name)) is not None
    was = _taken(box, w)
    _keep(w, lambda: let_go.append(1))
    assert w.seeking == was and "u" not in w.epochs and not w.leases, "it did not notice its name was taken"
    assert let_go
    w.heartbeat_once()
    assert b"somebody-else" in box.objects.get(w.sub.heartbeat_key(was)), "its heartbeat went out over the new holder's"
    assert _keep(w, lambda: None) == [] and w.seeking == was and w.slot is None, "a slot claimed on a store past its build"


# -- a slot row that does not parse is one row's trouble (the review's sixth pass, a minor) -----------------------

GARBLED_SLOT = {"holder": "somebody", "until": "soon", "released": "false", "gen": "1"}     # a hand edit


def _forget_garbled():
    """The counts of rows that did not parse are the PROCESS's, and every heartbeat written after carries them: a test
    that garbles a row clears them on its way out, or the heartbeats of every later test say `slots_garbled`."""
    import sys
    sys.modules["w2cplatform.rows"].forget()                           # the module in use, whatever was imported since: every table


def test_one_garbled_slot_row_does_not_leave_a_seeker_nobody_and_is_counted():
    """Every claim lists `<sub>/slots/` and parsed every row bare: one row with a word for a number — ANOTHER
    worker's — raised out of the claim, and an instance that had given its name up stayed nobody for ever, its
    capacity gone with nothing said (the `ValueError` was the loop's to log, every lease step). The row is skipped
    as a candidate now, counted in the heartbeat (`slots_garbled`) and logged once; a slot made new never takes its
    name. Both paths: a loop's `keep_slot`, and `rejoin` after the fence."""
    for path in ("keep_slot", "rejoin"):
        _forget_garbled()                  # the count is the process's, by row: each path from none, as a process of its own
        box = Box()
        w = _worker(box)
        sub = w.sub.name
        prefix = w.name.rsplit("-", 1)[0]
        # The counter of the module the workers RUN on, found through the method that reads it and not by an import:
        # `test_portability` rebuilds `sys.modules`, and after it `from w2cplatform import contract` is another module
        # object than the one these classes were made from.
        garbled = type(w).heartbeat.__globals__["SLOTS"].counts      # `SLOTS_GARBLED`, the table the worker reads by
        before = garbled.get(sub, 0)
        w.given = None                     # a process that took whatever was free: it walks the slots (one started under
                                           # a name asks for that name alone, `test_names.py`)
        box.vars.put(w.sub.slot_key(f"{prefix}-7"), GARBLED_SLOT)
        was = _taken(box, w)
        if path == "rejoin":
            w.lease_pass()
            assert w.rejoin() == f"{prefix}-8", f"{path}: {w.name}, seeking {w.seeking}"
        else:
            assert _keep(w, lambda: None) is not None, f"{path}: the claim raised over another worker's garbled row"
        assert w.seeking is None and w.name == f"{prefix}-8" and w.renew_slot() is True, f"{path}: {w.name}, seeking {w.seeking}"
        assert box.vars.get(w.sub.slot_key(f"{prefix}-7"))[0] == GARBLED_SLOT, path     # left for a person to mend
        assert garbled.get(sub, 0) > before, path
        w.heartbeat_once()
        hb = Heartbeat.from_bytes(box.objects.get(w.sub.heartbeat_key(w.name)))
        assert hb.extra["slots_garbled"] == garbled[sub], path
        assert b"somebody-else" in box.objects.get(w.sub.heartbeat_key(was)), path
    _forget_garbled()


def test_a_garbled_slot_row_stops_neither_placement_nor_the_worker_it_names():
    """The siblings of the same row. The controller reads every slot to know who is leaving (`slots()`, under
    `_pool`): one garbled row raised out of every unit's placement — nothing was placed in the whole subsystem. A
    worker whose OWN row is garbled raised out of every renewal: no lease renewed after it, no heartbeat — dead of
    one field; it is read as the row it last wrote, and the renewal writes it whole again by CAS. And a process the
    runtime gave a name whose row is garbled takes it, as it takes any row under that name — from a holder of another
    box, or of a name that says no box, once the controller gives it (the review's thirteenth pass, blocker 3)."""
    from w2cplatform.contract import HUNG_MOVE_AFTER, NameOnAnotherBox
    box = Box()
    ctl = controller(box, capacity=50)
    for i in (1, 2):
        ctl.create({"name": f"c{i}"})
    w = _worker(box)
    w.heartbeat_once()
    box.vars.put(w.sub.slot_key("w-9"), GARBLED_SLOT)
    ctl.look()
    assert set(ctl.slots()) == {"w-1"} and ctl.released_slots() == []
    assert [p.worker for p in ctl.ensure_placed()] == ["w-1", "w-1"], "one garbled slot row stopped every placement"

    w.reconcile_once()
    box.vars.put(w.sub.slot_key("w-1"), GARBLED_SLOT)                   # its own row, now
    assert w.lease_pass() == [] and w.writing_allowed and w.seeking is None
    row = Slot.from_items("w-1", box.vars.get(w.sub.slot_key("w-1"))[0])   # parses again: the renewal wrote it whole
    assert row.holder == w.instance and not row.released and row.until > box.wall()
    assert w.may_act("c1") and w.renew_slot() is True

    try:                                                                # "somebody": whose box, the row does not say
        _worker(box, name="w-9", instance="other:9")
        raise AssertionError("a garbled row of a holder nobody judged was taken")
    except NameOnAnotherBox:
        pass
    box.wall.advance(HUNG_MOVE_AFTER + 1)                               # nobody to say whether it runs: `wait`, to the limit
    assert "w-9" in ctl.publish_names()["names_given"]
    w9 = _worker(box, name="w-9", instance="other:9")                   # the runtime named it: taken, and whole again
    assert Slot.from_items("w-9", box.vars.get(w.sub.slot_key("w-9"))[0]).holder == "other:9" and w9.renew_slot() is True
    _forget_garbled()
