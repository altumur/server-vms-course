"""ADR-0074 guard crosses a non-voting door and is decided by the raft group."""
import json
import shutil
import signal
import tempfile

from tests.cluster.test_door import _door, _vars, _rights
from tests.cluster.test_drills import _group
from tests.test_guard import _race
from w2cplatform.configstorevars import StoreUnavailable


def test_guard_is_atomic_through_a_nonvoting_door_and_no_quorum_never_writes():
    root=tempfile.mkdtemp(prefix='guard-door-')
    ds, door=[], None
    try:
        ds=_group(root,_rights(root))
        door=_door(root,[ds[0].adv])
        v=_vars(door,timeout=2)
        _race(v,'testsub2')
        slot='testsub2/slots/w-1'
        index=v.get(slot)[1]
        for d in ds:
            d.stop(signal.SIGKILL)
        try:
            v.put('testsub2/slots/contribution',{'n':'late'},guard={'key':slot,'index':index})
        except StoreUnavailable:
            pass
        else:
            raise AssertionError('a door without voters acknowledged a write')
    finally:
        if door is not None:
            door.stop()
        for d in ds:
            d.stop(signal.SIGKILL)
        shutil.rmtree(root,ignore_errors=True)
