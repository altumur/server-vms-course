"""Every kind of the VMS's worker lives by the platform's life cycle — the stand-in, the slot row, the fence, the lease
step, the journal — in the loop it runs: the holder (`VmsWorker`, and the recorders that inherit it), the detector, the
scan, the survey, the gateway and the evaluator (`AutoWorker`: the platform's loop, a lease step of its own).

The rules are the platform's and are proved there, on testsub (`test_stand_in.py`, `test_slot_fence.py`,
`test_names.py`, `test_lease_step.py`); what is proved here is that each of the VMS's workers keeps them — the ones the
platform's `Worker.run` drives — every one of them now — and the ones with a lease step of their own (the
evaluator's `lease_pass`, by `keep_slot`; the recorder's). These tests were in those modules, over the VMS's workers, before the
boundary's step 5 put the platform's tests on testsub.
"""
import threading
import time

from vms.worker import FakeActuator, VmsWorker
from w2cplatform.contract import Heartbeat, Slot
from w2cplatform.events import ALARM
from tests.vmsconftest import Box
from tests.test_stand_in import _slot_row, _tick, _wait_for
from tests.test_slot_fence import GARBLED_SLOT, _Blink, _forget_garbled, _let_go, _OnePass, _taken
from tests.test_lease_step import T_POLL, _Pausing, _Turns


def _holder(box, name="w-1", **kw):
    return VmsWorker(name, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                     resource_root=box.archive, **kw)


def _workers(box):
    """The four that keep their slot in the platform's loop beside the holder: the detector, the scan, the survey and
    the gateway."""
    from w2cplatform.spec import SpecController
    from vms.config import DETJOB_SPEC, LIVE_SPEC, SURVEY_SPEC
    from vms.detjobworker import DetJobWorker
    from vms.detworker import DetWorker
    from vms.liveworker import LiveWorker
    from vms.surveyworker import SurveyWorker
    common = dict(clock=box.clock, wall=box.wall, server="srv-1", env={"LABELS": "gpu"})
    live_vars = box.vars.as_writer("liveworker", ["live/epoch/*", "live/slots/*", "live/streams/*"])
    return [DetWorker("d-1", box.vars.as_writer("detworker", ["det/epoch/*", "det/slots/*"]), box.objects,
                      resource_root=box.archive, **common),
            DetJobWorker("j-1", box.vars.as_writer("detjobworker", DETJOB_SPEC.sub.acl_worker()), box.objects,
                         resource_root=box.archive, **common),
            SurveyWorker("s-1", box.vars.as_writer("surveyworker", SURVEY_SPEC.sub.acl_worker()), box.objects,
                         resource_root=box.archive, **common),
            LiveWorker("g-1", live_vars, box.objects, ctl=SpecController(LIVE_SPEC, live_vars, box.objects, wall=box.wall), **common)]


def _all_workers(box):
    from vms.autoworker import AutoWorker
    from vms.config import AUTO_SPEC
    from w2cplatform.contract import requests_acl
    auto = AutoWorker("a-1", box.vars.as_writer("autoworker", AUTO_SPEC.sub.acl_worker() + requests_acl("vms", "rec")),
                      box.objects, clock=box.clock, wall=box.wall, server="srv-1", resource_root=box.archive, env={})
    return [_holder(box)] + _workers(box) + [auto]


# -- every worker's `run` has a stand-in (from `test_stand_in.py`) ---------------------------------------------

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
            seen["may_act"] = w.may_act("u")
            return []

        w.reconcile_once = hung
        t = threading.Thread(target=w.run, kwargs={"poll": 0.01, "stop": stop}, daemon=True)
        t.start(); t.join(10)
        assert not t.is_alive(), type(w).__name__
        assert seen.get("may_act"), f"{type(w).__name__}: the lease ran out under a hung pass — no stand-in in its loop"


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
    Their loop is the platform's now, and its lease step keeps the slot row (`Worker.run` → `lease_pass`); and read by
    `Worker.keep_slot` — the platform's lease step for a loop of its own, the evaluator's — a row that names another
    instance is a name given up — the units let go, their epochs released — and, named by its unit, nothing else
    claimed: it waits for its own."""
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


# -- a slot given up and no other taken (from `test_slot_fence.py`) -------------------------------------------

def _keep(w, let_go):
    """A lease step in a `try` of its own, so whatever it raises the loop goes on. The evaluator's is its `lease_pass`
    (`keep_slot`, with nothing running to let go of); the others' loops fence and `rejoin` (`Worker.lease_pass`, the
    holders' tests below) — here they are given `keep_slot`, the same rules by the platform's other path."""
    try:
        return w.lease_pass() if type(w).__name__ == "AutoWorker" else w.keep_slot(let_go)
    except Exception:                                                  # noqa: BLE001
        return None


def _every_kind(box):
    return [w for w in _all_workers(box) if type(w).__name__ != "VmsWorker"]   # the holder fences and rejoins on its own


def test_every_kind_of_vms_worker_whose_slot_was_taken_and_whose_claim_failed_takes_nothing_and_says_nothing():
    """Every worker but the holders, by `keep_slot` — the detector, the scan, the survey, the gateway, the
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


def _holders(box):
    """The three proved here by the fence and `rejoin` (`lease_pass`): the holder, the recorder, and the camera's own
    recorder, which inherits the recorder's."""
    import tempfile
    from tests.vmsconftest import REC_ACL, recorder
    from vms.card import CamRing, CardActuator, CardRecorder
    ring = CamRing(clock=box.wall)
    return [_holder(box), recorder(box, "r-1", "srv-1"),
            CardRecorder("r-9", box.vars.as_writer("recworker-r-9", REC_ACL), box.objects, ring,
                         CardActuator(ring, threaded=False), clock=box.clock, wall=box.wall, server="cam-9",
                         resource_root=tempfile.mkdtemp(prefix="cam-"), env={})]


def _one_turn():
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


def test_the_vms_holder_and_recorders_fenced_for_the_schema_stop_speaking_when_another_instance_takes_the_name():
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


def test_every_kind_of_vms_worker_on_a_store_raised_past_its_build_is_nobody_once_another_instance_takes_its_name():
    """The same sibling in the five driven by `keep_slot`. There the renewal's refusal goes out of the
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


def test_one_garbled_slot_row_leaves_no_kind_of_vms_worker_nobody_and_is_counted():
    """Every claim lists `<sub>/slots/` and parsed every row bare: one row with a word for a number — ANOTHER
    worker's — raised out of the claim, and an instance that had given its name up stayed nobody for ever, its
    capacity gone with nothing said (the `ValueError` was the loop's to log, every lease step). The row is skipped
    as a candidate now, counted in the heartbeat (`slots_garbled`) and logged once; a slot made new never takes its
    name. The five by `keep_slot`, and the holder's `rejoin`."""
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


# -- one name, two processes (from `test_names.py`) ------------------------------------------------------------

def test_every_kind_of_worker_writes_its_journal_into_its_servers_events_archive():
    """The product's cross-check (4 Oct): its live gateway wrote `worker.name_taken` — the ALARM that says a process is
    nobody because another instance holds its name — into its own log and nowhere else. The course's gateway had the
    same gap: `LiveWorker` had no `resource_root`, so its journal (`Worker.journal`) was the log only, while its
    container mounts the archive for its registration. Every kind of worker, told the archive the way its entry point
    tells it (`RESOURCE_ROOT` in its environment), writes its journal there: the alarm into the alarms' tree, the line beside
    it into the audit family's."""
    import tempfile
    from w2cplatform.events import alarm_tree, buckets_under
    from vms.autoworker import AutoWorker
    from vms.detjobworker import DetJobWorker
    from vms.detworker import DetWorker
    from vms.liveworker import LiveWorker
    from vms.surveyworker import SurveyWorker
    box = Box()
    made = {"VmsWorker": lambda env: VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock,
                                               wall=box.wall, server="srv-a", env=env)}
    for cls in (LiveWorker, AutoWorker, DetWorker, DetJobWorker, SurveyWorker):
        made[cls.__name__] = lambda env, cls=cls: cls(None, box.vars, box.objects, clock=box.clock, wall=box.wall,
                                                      server="srv-a", env=env)
    for kind, make in made.items():
        root = tempfile.mkdtemp(prefix="events-")
        w = make({"RESOURCE_ROOT": root})
        role = f"{w.sub.name}worker"
        w.journal.say("worker.name_taken", ALARM, sub=w.sub.name, worker=w.name, holder="another")
        w.journal.say("worker.name_back", sub=w.sub.name, worker=w.name)
        said = buckets_under(root, "audit", role, 600) + buckets_under(root, alarm_tree("audit"), role, 600)
        assert sorted(b.subsystem for b in said) == sorted(["audit", alarm_tree("audit")]), (kind, root, said)


# -- the lease step (from `test_lease_step.py`) ----------------------------------------------------------------

def test_the_evaluators_loop_has_the_same_lease_step():
    """`AutoWorker.run` — the platform's loop since it stopped being a copy — keeps its leases the same way: a step
    whose renewals were not answered is followed by another at the next look, and the period runs from a step's start."""
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
