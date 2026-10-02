"""A tail of the volumes (the product's box, feedback BR).

    a recorder that stops gives its volume back — after its last write into it: whoever writes there next
        does not wait out a hold nobody is using, and finds no writer left in the volume
    …and, found on the way: the recorder PROCESS's token could not take a volume at all
"""
import inspect
import os
import threading

from w2cplatform.contract import Slot
from vms import volumes
from vms.config import REC_SPEC
from tests.conftest import Box, footage, recorder


def test_a_recorder_that_stops_gives_its_volume_back_after_its_last_write_into_it():
    box = Box()
    vol = os.path.join(box.root, "vol")
    volumes.write(box.vars, {"name": "vol", "kind": "local", "url": vol, "server": "srv-a", "quota_bytes": 64 << 20})
    a = recorder(box, "r-1", "srv-a", acl=False)
    assert a.volume_pass() == "vol"
    t = box.wall()
    footage(a.store, "7", 1, t - 600, t, seal=False)                   # written, its block still open

    order = []
    close, release = a._close_store, a.release_hold
    a._close_store = lambda *x, **k: (order.append("close"), close(*x, **k))[1]
    a.release_hold = lambda: (order.append("release"), release())[1]
    stop = threading.Event(); stop.set()
    a.run(stop=stop)                                                   # an orderly stop: SIGTERM, a rolling update

    assert order[-2:] == ["close", "release"]                          # the last write, THEN the place
    assert Slot.from_items("vol", box.vars.get("rec/holds/vol")[0]).released
    b = recorder(box, "r-2", "srv-a", acl=False)
    assert b.volume_pass() == "vol"                                    # at once — it used to wait out the hold's forty-five seconds
    assert not b.store.reattached                                      # a clean mount: no writer left in the volume
    assert b.our_coverage("7") == [(t - 600, t)]                       # and what the last write put there is readable

    # a crash says nothing, and the hold lapses by itself, as before
    c = recorder(box, "r-3", "srv-a", acl=False)
    assert c.volume_pass() == ""                                       # held by r-2, which is alive
    box.wall.advance(46)
    box.clock.advance(c.slot_ttl + c.HOLD_SKEW)                        # …by c's own clock: the row stood still a term (Т-M5)
    assert c.volume_pass() == "vol"


def test_the_recorder_process_holds_a_token_that_can_take_a_volume():
    """`python -m vms recorder` opened the store with a list written by hand before a recorder took volumes —
    epochs and its slot, and not its hold. On a box with a declared volume it was refused its own place."""
    import vms.__main__ as main
    src = inspect.getsource(main.recorder)
    assert 'acl={"recworker": REC_SPEC.sub.acl_worker()}' in src and '"rec/holds/*"' not in src     # derived, not listed by hand
    assert "rec/holds/*" in REC_SPEC.sub.acl_worker()
    box = Box()
    volumes.write(box.vars, {"name": "vol", "kind": "local", "url": os.path.join(box.root, "vol"), "server": "srv-a", "quota_bytes": 64 << 20})
    r = recorder(box, "r-1", "srv-a", acl=REC_SPEC.sub.acl_worker())
    assert r.volume_pass() == "vol"
