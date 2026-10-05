"""A slot given up and no other taken: the instance is nobody until it has one (the review's fifth pass, blocker 3).

`keep_slot` reads a slot row naming another instance, lets its units go and claims a free slot. When that claim
failed — the store blinked, every candidate was taken under it — the worker was left with no slot and its OLD
name: `renew_slot` with no slot said "still me", the stand-in renewed for it, the next pass read the other
instance's assignment, took new epochs on its units with `may_act` true, and the heartbeat under that name was
written over the legitimate one. Two processes took the same detectors in turn, until a restart.

Now, while there is no slot, the instance is fenced: `renew_slot` says no, the stand-in does not stand in, no epoch
is taken, the assignment it reads is empty, no heartbeat goes out under the name, and every lease step tries the
claim again — as `VmsWorker.rejoin` does for a fenced holder.
"""
from w2cplatform.contract import Heartbeat, Slot
from tests.conftest import Box


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


def _keep(w, let_go):
    """The lease step as the loops run it: in a `try` of its own, so whatever it raises the loop goes on. The
    evaluator's is its `lease_pass` (it has nothing running to let go of); the others call `keep_slot`."""
    try:
        return w.lease_pass() if type(w).__name__ == "AutoWorker" else w.keep_slot(let_go)
    except Exception:                                                  # noqa: BLE001
        return None


def _every_kind(box):
    from tests.test_stand_in import _all_workers
    return [w for w in _all_workers(box) if type(w).__name__ != "VmsWorker"]   # the holder fences and rejoins on its own


def test_a_worker_whose_slot_was_taken_and_whose_claim_failed_takes_nothing_and_says_nothing_under_that_name():
    """Every worker that keeps its slot by `keep_slot` — the detector, the scan, the survey, the gateway, the
    evaluator. The slot is taken by another instance, the claim of a free one fails on a store that blinks: the
    units it had are let go, no epoch is taken, the assignment of the name it gave up is not read, the stand-in
    renews nothing, and the other instance's heartbeat stands."""
    box = Box()
    for w in _every_kind(box):
        kind = type(w).__name__
        w.take_epoch("u")
        was = _taken(box, w)
        box.vars.put(w.sub.assignment(was), {"units": "u,v", "rev": 5})   # the other instance's assignment
        let_go = []
        with _Blink(w.vars):
            lost = _keep(w, lambda: let_go.append(1))
            assert (let_go or kind == "AutoWorker") and "u" not in w.epochs and not w.leases, kind   # its units let go, epochs given up
            assert lost in (["u"], None), kind
            assert w.renew_slot() is False, f"{kind}: no slot, and renew_slot said 'still me'"
            assert w.may_stand_in() is False, f"{kind}: the stand-in would renew for an instance with no slot"
            assert w.assignment().units == [], f"{kind}: it reads the assignment of a name it gave up"
            epoch_row = box.vars.get(w.sub.epoch_key("v"))[0]
            try:
                w.take_epoch("v")
                raise AssertionError(f"{kind}: an epoch was taken with no slot")
            except RuntimeError as e:                                  # `NoSlot`: nobody takes nothing
                assert type(e).__name__ == "NoSlot", f"{kind}: {e!r}"

            assert box.vars.get(w.sub.epoch_key("v"))[0] == epoch_row, kind      # and nothing was written for it
            w.heartbeat_once()
            hb = box.objects.get(w.sub.heartbeat_key(was))
            assert b"somebody-else" in hb, f"{kind}: its heartbeat went out over the other instance's"
            assert _keep(w, lambda: None) == [] and w.renew_slot() is False, kind   # tried again, still nobody
        # the store answers again — and the other instance holds the name live: still nobody, and no other number taken
        # (its name is the one it was started under: the owner's decision of 4 Oct, `test_names.py`)
        assert _keep(w, lambda: None) == [] and w.renew_slot() is False and w.slot is None, kind
        _let_go(box, w, was)                                           # the other instance stops in order
        assert _keep(w, lambda: None) == [], kind
        assert w.name == was and w.renew_slot() is True and w.may_stand_in() is True, kind
        assert w.assignment().units == ["u", "v"], kind                # its own name's list, read again — as its next pass does
        w.take_epoch("v")
        assert "v" in w.epochs and w.may_act("v"), kind


def test_the_detector_and_the_gateway_with_no_slot_run_nothing_of_the_name_they_gave_up():
    """Reproduced as the review did, on the two it ran: a detector `d-1` and a gateway `g-1` whose slot another
    instance took while the store blinked. Their next pass, with the other instance's assignment naming a camera
    that is held and live, starts nothing: no model, no subscription, no epoch."""
    from tests.test_pass_failures import _workers
    box = Box()
    det, _, _, gw = _workers(box)
    box.vars.put("det/units/7-motion", {"id": "7-motion", "name": "7-motion", "cam": "7", "kind": "motion", "enabled": "true"})
    det.rtp_source = lambda cam: ("srv-1", "rtsp://srv-1/7")
    gw.rtp_source = lambda cam: ("srv-1", "rtsp://srv-1/7", 1)
    for w, unit in ((det, "7-motion"), (gw, "7")):
        was = _taken(box, w)
        box.vars.put(w.sub.assignment(was), {"units": unit, "rev": 3})
        with _Blink(w.vars):
            _keep(w, lambda: None)
            w.reconcile_once()
            assert w.epochs == {} and box.vars.get(w.sub.epoch_key(unit))[0] in (None, {}), type(w).__name__
        assert det.running == {} and gw.upstreams == {}


def test_the_stand_in_does_not_renew_for_an_instance_with_no_slot():
    """The stand-in's look, by hand, under a step that has hung long enough to be stood in for: with no slot it
    renews nothing — no lease, no row."""
    box = Box()
    from tests.test_pass_failures import _workers
    det = _workers(box)[0]
    det.take_epoch("u")
    _taken(box, det)
    with _Blink(det.vars):
        _keep(det, lambda: None)
        with det.guarded("pass"):
            box.clock.advance(20); box.wall.advance(20)
            assert det.stand_in_once() is False and det.stand_in_renewals == 0


# -- the holder and the recorder: `fence` and `rejoin`, the same rule (the review's sixth pass) ------------------

def _holders(box):
    """The three that fence and rejoin on their own path instead of `keep_slot`: the holder, the recorder, and the
    camera's own recorder, which inherits the recorder's."""
    import tempfile
    from tests.vmsconftest import REC_ACL, recorder
    from tests.test_stand_in import _holder
    from vms.card import CamRing, CardActuator, CardRecorder
    ring = CamRing(clock=box.wall)
    return [_holder(box), recorder(box, "r-1", "srv-1"),
            CardRecorder("r-9", box.vars.as_writer("recworker-r-9", REC_ACL), box.objects, ring,
                         CardActuator(ring, threaded=False), clock=box.clock, wall=box.wall, server="cam-9",
                         resource_root=tempfile.mkdtemp(prefix="cam-"), env={})]


def _one_turn():
    from tests.test_pass_failures import _OnePass
    return _OnePass()


def _nobody(box, w, was, kind):
    """What an instance with no name does: nothing under the name it gave up."""
    w.heartbeat_once()
    assert b"somebody-else" in box.objects.get(w.sub.heartbeat_key(was)), f"{kind}: its heartbeat went out over the other instance's"
    assert w.renew_slot() is False and w.may_stand_in() is False, kind
    assert w.assignment().units == [], f"{kind}: it reads the assignment of a name it gave up"
    w.reconcile_once()
    assert w.rows == [] and w.devices == {} and w.epochs == {}, f"{kind}: it took up the other instance's units"
    try:
        w.take_epoch("u")
        raise AssertionError(f"{kind}: an epoch was taken with no slot")
    except RuntimeError as e:
        assert type(e).__name__ == "NoSlot", f"{kind}: {e!r}"


def test_a_fenced_holder_or_recorder_whose_rejoin_failed_says_nothing_under_the_name_another_instance_holds():
    """The review's sixth pass: the class of the fifth's blocker 3, on the holder's own path. `VmsWorker.rejoin` dropped
    its slot and claimed a free one; when the claim failed — the store blinked (the `OSError` went out of `rejoin`), or
    every candidate was taken under it — the instance was left with no slot and its OLD name, and `renew_slot` with
    no slot says "still me": its heartbeat (`fenced: true`) was written over the legitimate one, pass after pass.
    And between the fence and the first `rejoin` it said the same over the name another instance already held.

    Now the fence at the slot makes it nobody (`seeking`), `rejoin` goes through `_seek_slot`, and until a slot is
    claimed nothing is said, read or taken under the name. The holder, the recorder and the camera's recorder."""
    box = Box()
    for w in _holders(box):
        kind = type(w).__name__
        w.heartbeat_once()
        was = _taken(box, w)
        box.vars.put(w.sub.assignment(was), {"units": "1,2", "rev": 5})      # the other instance's assignment
        w.lease_pass()
        assert not w.writing_allowed and "held by another instance" in w.fenced_reason, kind
        _nobody(box, w, was, kind)                                          # fenced, before any `rejoin`: already nobody
        with _Blink(w.vars):                                                # the store blinks on the claim
            assert w.rejoin() is None and not w.writing_allowed, kind
            _nobody(box, w, was, kind)
            w.run(poll=0, stop=_one_turn())                                 # a turn of the real loop, and its orderly stop
            assert b"somebody-else" in box.objects.get(w.sub.heartbeat_key(was)), kind
            row = Slot.from_items(was, box.vars.get(w.sub.slot_key(was))[0])
            assert row.holder == "somebody-else" and not row.released, f"{kind}: it released the other instance's slot"
        real = w._claim_slot                                                # …or every candidate is taken under it
        w._claim_slot = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("could not claim a slot in 50 tries"))
        assert w.rejoin() is None and not w.writing_allowed, kind
        _nobody(box, w, was, kind)
        w._claim_slot = real
        assert w.rejoin() is None and not w.writing_allowed, kind         # the store answers, the other holds it live:
        _nobody(box, w, was, kind)                                          # its own name only (the owner's decision of 4 Oct)
        _let_go(box, w, was)                                                # the other instance stops in order
        name = w.rejoin()                                                   # somebody again — under its own name
        assert name == was and w.name == name and w.writing_allowed and w.seeking is None, kind
        assert w.renew_slot() is True and w.assignment().units == ["1", "2"], kind   # the name's assignment with it
        w.heartbeat_once()
        assert w.instance.encode() in box.objects.get(w.sub.heartbeat_key(name)), kind


def test_a_holder_fenced_for_the_schema_stops_speaking_when_another_instance_takes_its_name():
    """The sibling the review did not name. A store raised past the build fences the holder with its slot IN HAND:
    the name is still its own, and its heartbeat says `fenced` under it. But it renews nothing, the row lapses, and
    a new build takes the name — while the old one never read the row again (`renew_slot` raises on the schema
    before it gets there) and went on heartbeating over the new holder's. A fenced instance reads its row at every
    lease step now, and is nobody from the step that finds another holder there."""
    from w2cplatform.contract import SCHEMA, Controller, Subsystem
    for i in range(3):
        box = Box()
        w = _holders(box)[i]
        kind = type(w).__name__
        assert w.lease_pass() == []
        Controller(Subsystem("vms"), box.vars, box.objects, wall=box.wall).set_schema(SCHEMA + 1)
        w.lease_pass()
        assert not w.writing_allowed and f"schema {SCHEMA + 1}" in w.fenced_reason and w.seeking is None, kind
        w.heartbeat_once()                                                  # the name is still its own: it says so
        assert Heartbeat.from_bytes(box.objects.get(w.sub.heartbeat_key(w.name))).extra["fenced"] is True, kind
        was = _taken(box, w)                                                # the row lapsed and a new build took the name
        w.lease_pass()
        assert w.seeking == was, f"{kind}: fenced for the schema, it did not notice its name was taken"
        w.heartbeat_once()
        assert b"somebody-else" in box.objects.get(w.sub.heartbeat_key(was)), f"{kind}: its heartbeat went out over the new holder's"


def test_a_worker_on_a_store_raised_past_its_build_is_nobody_once_another_instance_takes_its_name():
    """The same sibling in the five that keep their slot by `keep_slot`. There the renewal's refusal goes out of the
    lease step, every step — nothing is renewed, the row lapses — and the heartbeat, in a `try` of its own, went on
    under the name after a new build had taken it. From the step that reads another holder in the row the instance
    is nobody: its units let go, nothing said under the name, and no other slot claimed on a store past its build."""
    from w2cplatform.contract import SCHEMA, Controller, Subsystem
    box = Box()
    workers = _every_kind(box)
    Controller(Subsystem("vms"), box.vars, box.objects, wall=box.wall).set_schema(SCHEMA + 1)
    for w in workers:
        kind = type(w).__name__
        w.take_epoch("u")
        let_go = []
        assert _keep(w, lambda: let_go.append(1)) is None and w.seeking is None, kind   # refused, and the name still its own
        w.heartbeat_once()
        assert box.objects.get(w.sub.heartbeat_key(w.name)) is not None, kind
        was = _taken(box, w)
        _keep(w, lambda: let_go.append(1))
        assert w.seeking == was and "u" not in w.epochs and not w.leases, f"{kind}: it did not notice its name was taken"
        assert let_go or kind == "AutoWorker", kind
        w.heartbeat_once()
        assert b"somebody-else" in box.objects.get(w.sub.heartbeat_key(was)), f"{kind}: its heartbeat went out over the new holder's"
        assert _keep(w, lambda: None) == [] and w.seeking == was and w.slot is None, f"{kind}: a slot claimed on a store past its build"


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
    name. The five that keep their slot by `keep_slot`, and the holder's `rejoin`."""
    from tests.test_stand_in import _holder
    box = Box()
    for w in _every_kind(box) + [_holder(box)]:
        kind, sub = type(w).__name__, w.sub.name
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
        if kind == "VmsWorker":
            w.lease_pass()
            assert w.rejoin() == f"{prefix}-8", f"{kind}: {w.name}, seeking {w.seeking}"
        else:
            assert _keep(w, lambda: None) is not None, f"{kind}: the claim raised over another worker's garbled row"
        assert w.seeking is None and w.name == f"{prefix}-8" and w.renew_slot() is True, f"{kind}: {w.name}, seeking {w.seeking}"
        assert box.vars.get(w.sub.slot_key(f"{prefix}-7"))[0] == GARBLED_SLOT, kind     # left for a person to mend
        assert garbled.get(sub, 0) > before, kind
        w.heartbeat_once()
        hb = Heartbeat.from_bytes(box.objects.get(w.sub.heartbeat_key(w.name)))
        assert hb.extra["slots_garbled"] == garbled[sub], kind
        assert b"somebody-else" in box.objects.get(w.sub.heartbeat_key(was)), kind
    _forget_garbled()


def test_a_garbled_slot_row_stops_neither_placement_nor_the_worker_it_names():
    """The siblings of the same row. The controller reads every slot to know who is leaving (`slots()`, under
    `_pool`): one garbled row raised out of every unit's placement — nothing was placed in the whole subsystem. A
    worker whose OWN row is garbled raised out of every renewal: no lease renewed after it, no heartbeat — dead of
    one field; it is read as the row it last wrote, and the renewal writes it whole again by CAS. And a process the
    runtime gave a name whose row is garbled takes it, as it takes any row under that name — from a holder of another
    box, or of a name that says no box, once the controller gives it (the review's thirteenth pass, blocker 3)."""
    from w2cplatform.contract import HUNG_MOVE_AFTER, NameOnAnotherBox
    from tests.test_lesson4_worker import _box_with_cameras
    from tests.test_stand_in import _holder
    box, ctl = _box_with_cameras(2)
    w = _holder(box)
    w.heartbeat_once()
    box.vars.put("vms/slots/w-9", GARBLED_SLOT)
    ctl.look()
    assert set(ctl.slots()) == {"w-1"} and ctl.released_slots() == []
    assert [p.worker for p in ctl.ensure_placed()] == ["w-1", "w-1"], "one garbled slot row stopped every placement"

    w.reconcile_once()
    box.vars.put("vms/slots/w-1", GARBLED_SLOT)                         # its own row, now
    assert w.lease_pass() == [] and w.writing_allowed and w.seeking is None
    row = Slot.from_items("w-1", box.vars.get("vms/slots/w-1")[0])      # parses again: the renewal wrote it whole
    assert row.holder == w.instance and not row.released and row.until > box.wall()
    assert w.may_act("1") and w.renew_slot() is True

    try:                                                                # "somebody": whose box, the row does not say
        _holder(box, name="w-9", instance="other:9")
        raise AssertionError("a garbled row of a holder nobody judged was taken")
    except NameOnAnotherBox:
        pass
    box.wall.advance(HUNG_MOVE_AFTER + 1)                               # nobody to say whether it runs: `wait`, to the limit
    assert "w-9" in ctl.publish_names()["names_given"]
    w9 = _holder(box, name="w-9", instance="other:9")                   # the runtime named it: taken, and whole again
    assert Slot.from_items("w-9", box.vars.get("vms/slots/w-9")[0]).holder == "other:9" and w9.renew_slot() is True
    _forget_garbled()
