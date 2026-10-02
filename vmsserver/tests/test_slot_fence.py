"""A slot given up and no other taken: the instance is nobody until it has one (the review's fifth pass, blocker 3).

`keep_slot` reads a slot row naming another instance, lets its units go and claims a free slot. When that claim
failed — the store blinked, every candidate was taken under it — the worker was left with no slot and its OLD
name: `renew_slot` with no slot said "still me", the stand-in renewed for it, the next pass read the other
instance's assignment, took new epochs on its units with `may_write` true, and the heartbeat under that name was
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
        # the store answers again: the next lease step claims a free slot, and the instance is somebody
        assert _keep(w, lambda: None) == [], kind
        assert w.name != was and w.renew_slot() is True and w.may_stand_in() is True, kind
        w.take_epoch("v")
        assert "v" in w.epochs and w.may_write("v"), kind


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
