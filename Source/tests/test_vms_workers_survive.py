"""The VMS's workers survive what the platform's loop hands them: a pass that raises half-way, and the garbled
heartbeat a previous instance left under the slot. Moved from `test_pass_failures.py` and `test_placement_decides.py`
(the boundary's step 5): the platform's halves are there, on testsub; these are about every VMS worker kind and
about `VmsWorker`'s own constructor."""
import logging

from vms.controller import VmsController
from vms.worker import FakeActuator, VmsWorker
from tests.conftest import Box
from tests.test_pass_failures import _OnePass
from tests.vmsconftest import Box as VmsBox, four_workers


class _Log(logging.Handler):
    def __init__(self):
        super().__init__(); self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


def test_every_vms_worker_kind_renews_its_leases_when_a_pass_raises():
    """M19 of the review, the remainder. The heartbeat had been given a `try` of its own; `renew_leases()` was
    still the LAST line of `reconcile_once`, so the one exception that skipped the heartbeat also skipped the
    renewal — the worker was reported alive, held its units, and `may_act` ran out on all of them twenty-five
    seconds later. Every worker here: the four that renewed at the end of the pass (det, detjob, survey, live)."""
    box = VmsBox()
    for w in four_workers(box):
        w.take_epoch("u")
        box.clock.advance(10)                                       # the lease is ten seconds old; the renewal stamps it anew

        def boom(*a, **kw):
            raise RuntimeError("the store went away mid-pass")

        w.reconcile_once = boom
        rec = _Log(); logging.getLogger().addHandler(rec)
        try:
            w.run(poll=0, stop=_OnePass())
        finally:
            logging.getLogger().removeHandler(rec)
        assert any("pass failed" in ln for ln in rec.lines), (type(w).__name__, rec.lines)
        assert w.leases["u"].last_renewal == box.clock(), f"{type(w).__name__}: the pass raised and the lease was not renewed"
        assert w.may_act("u"), type(w).__name__
        hb = box.objects.get(w.sub.heartbeat_key(w.name))
        assert hb is not None, f"{type(w).__name__}: no heartbeat after a failed pass"


def test_a_worker_whose_slot_left_a_garbled_heartbeat_starts_all_the_same():
    """The review's third pass (M6's remainder). `VmsWorker.__init__` read the previous instance's heartbeat — to
    measure its own failover — bare: a garbled one raised out of the constructor, and the process restarted for
    ever over the very object its first heartbeat would have replaced. Unparsed, there is no failover to measure."""
    box = Box()
    box.objects.put("vms/heartbeats/w-1", b'{"worker": "w-1", "ts": ')                      # cut short
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-a")
    assert (w.previous_hb, w.previous_instance) == (0.0, "")
    w.heartbeat_once()
    assert "w-1" in VmsController(box.vars, box.objects, wall=box.wall).workers_seen()
