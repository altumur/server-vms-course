"""A place under a strict lease (`placement.places.lease: strict`) is the PLATFORM's to let go, not a subsystem's (the
architect's rule: a key the loader reads and a subsystem executes is a hook in reverse). A place any box may write — its
row names no server — is written only inside its hold's write window (`Worker.may_write_place`) and let go by the base
worker's lease step once the hold has gone unconfirmed past it and the store does not confirm it then — silent, or
the row another worker's (`Worker._strict_place_pass`) — whatever the units'
`lease.unconfirmed_max` lets them write. On testsub2, whose units are kept on shelves and whose leases go on ten minutes
unconfirmed."""
import os

from w2cplatform.spec import SubsystemSpec
from w2cplatform.worker import Worker
from tests.conftest import Box

TESTSUB2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata", "testsub2.subsystem.yaml")


def _spec(lease: str):
    spec = SubsystemSpec.load(TESTSUB2)
    spec.places = {**spec.places, "lease": lease}
    return spec


def _shelf(box, spec, name, server):
    box.vars.put(spec.sub.config("shelves", name), {"name": name, "server": server, "enabled": True})


def _worker(box, spec):
    w = Worker(spec.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance="box-a:1:w", spec=spec)
    w.server = "srv-1"
    w.claim_slot(prefer="t-1")
    return w


def _tick(box, s):
    box.clock.advance(s); box.wall.advance(s)


class _Silent:
    """The store, not answering: every read and write raises `OSError`."""
    def __init__(self, real):
        self.real = real

    def __getattr__(self, name):
        def away(*a, **kw):
            raise OSError("the store is away")
        return away


def _silence(w, box, shelf):
    """Take `shelf`, then let the store go silent for the hold's write window: the lease step one second inside it and
    one second past it. Returns what the step found each time — (held, may write)."""
    assert w.claim_hold([shelf]) == shelf
    w.vars = _Silent(box.vars)
    seen = []
    for step in (w.slot_ttl - w.lease_margin - 1, 1):
        _tick(box, step)
        w.lease_pass()
        seen.append((w.hold, w.may_write_place(shelf)))
    w.vars = box.vars
    return seen


def test_a_place_any_box_may_write_under_a_strict_lease_is_let_go_by_the_platform_when_its_hold_goes_unconfirmed():
    """Strict, and the shelf's row names no server: written inside the window, refused and let go past it — though the
    spec lets a tally's count go on ten minutes past an unconfirmed lease. Let go, the hold row lapses by itself (the
    store did not hear a release) and the worker holds nothing."""
    box = Box()
    spec = _spec("strict")
    assert spec.unconfirmed_max == 600.0                                 # the units' ceiling: not the place's
    _shelf(box, spec, "net", "")
    w = _worker(box, spec)
    assert _silence(w, box, "net") == [("net", True), (None, False)]


def test_a_place_under_a_lease_that_is_not_strict_is_kept_through_the_silence():
    """The same shelf, the same silence, `lease` not said: the place stays the worker's and writable — the platform
    executes `strict` only where the spec says it."""
    box = Box()
    spec = _spec("")
    _shelf(box, spec, "net", "")
    w = _worker(box, spec)
    assert _silence(w, box, "net") == [("net", True), ("net", True)]


def test_a_place_whose_row_names_a_server_is_kept_under_a_strict_lease():
    """Strict is about a place ANY box may write. A shelf whose row names its server is that box's alone: nobody else
    can write there, so it is kept for as long as the silence lasts — as the row said when it was taken."""
    box = Box()
    spec = _spec("strict")
    _shelf(box, spec, "s1", "srv-1")
    w = _worker(box, spec)
    assert _silence(w, box, "s1") == [("s1", True), ("s1", True)]


def test_a_strict_place_confirmed_late_by_a_store_that_answers_is_kept_and_its_window_runs_from_the_confirmation():
    """A renewal confirms the hold from before the store was asked; the window runs from there, not from the take.
    Past it with the store answering — a pass that came late — the lease step asks once more: the row is still the one
    this worker wrote (nobody took it meanwhile), so the hold is confirmed and the fence opens again."""
    box = Box()
    spec = _spec("strict")
    _shelf(box, spec, "net", "")
    w = _worker(box, spec)
    assert w.claim_hold(["net"]) == "net"
    window = w.slot_ttl - w.lease_margin
    _tick(box, window - 1)
    assert w.renew_hold()
    _tick(box, window - 1)                                               # past the take's window, inside the renewal's
    assert w.may_write_place("net") and w.may_close_place("net")
    _tick(box, 1)
    assert not w.may_write_place("net") and w.may_close_place("net")    # the close has the margin and the skew more
    w.lease_pass()                                                       # late, and the store answers: confirmed
    assert w.hold == "net" and w.may_write_place("net")


def test_a_strict_place_another_worker_took_is_let_go_by_the_lease_step():
    """Past the window, and the row another worker's by then: the lease step's last ask is answered no, and the place
    is let go — the worker holds nothing and may write nothing there."""
    box = Box()
    spec = _spec("strict")
    _shelf(box, spec, "net", "")
    w = _worker(box, spec)
    assert w.claim_hold(["net"]) == "net"
    other = Worker(spec.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance="box-b:2:other",
                   spec=spec)
    other.server = "srv-2"
    other.claim_slot(prefer="t-2")
    assert other.claim_hold(["net"]) is None                             # looks: renewed a moment ago
    _tick(box, w.slot_ttl + w.HOLD_SKEW)
    assert other.claim_hold(["net"]) == "net"                            # the row stood still: taken
    w.lease_pass()
    assert w.hold is None and not w.may_write_place("net")
