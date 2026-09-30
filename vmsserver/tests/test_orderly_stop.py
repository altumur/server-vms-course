"""Two tails of the keeps and the volumes (the product's box, feedback BR).

    a recorder that stops gives its volume back — after its last write into it: whoever writes there next
        does not wait out a hold nobody is using
    kept footage the ring took is an alarm, not a line in a log
    …and, found on the way: the recorder PROCESS's token could not take a volume at all
"""
import inspect
import os
import threading
from datetime import datetime, timezone

from w2cplatform.contract import Slot
from w2cplatform.eventdatabase import EventIndex
from w2cplatform.resource import SPACE_KEY
from vms import keeps, volumes
from vms.archive import ArchiveResource, Manifest, Segment, segment_path
from vms.config import REC_SPEC
from vms.recworker import RecWorker
from vms.resource import vms_resource
from tests.conftest import Box

DAY = 86400.0


def _recorder(box, name, vars_=None):
    return RecWorker(name, vars_ or box.vars, box.objects, archive=ArchiveResource(box.spool, box.archive, wall=box.wall),
                     clock=box.clock, wall=box.wall, server="srv-a", env={})


def test_a_recorder_that_stops_gives_its_volume_back_after_its_last_write_into_it():
    box = Box()
    vol = os.path.join(box.root, "vol")
    volumes.write(box.vars, {"name": "vol", "kind": "local", "url": vol, "server": "srv-a", "quota_bytes": 10 ** 9})
    a = _recorder(box, "r-1")
    assert a.volume_pass() == "vol"
    t = box.wall()
    seg = segment_path(a.archive.spool, "7", 1, datetime.fromtimestamp(t - 600, timezone.utc))   # closed, and still in the spool
    os.makedirs(os.path.dirname(seg), exist_ok=True); open(seg, "wb").write(b"footage"); os.utime(seg, (t - 600, t - 600))

    order = []
    promote, release = a.promote_closed, a.release_hold
    a.promote_closed = lambda *x, **k: (order.append("promote"), promote(*x, **k))[1]
    a.release_hold = lambda: (order.append("release"), release())[1]
    stop = threading.Event(); stop.set()
    a.run(stop=stop)                                                   # an orderly stop: SIGTERM, a rolling update

    assert order[-2:] == ["promote", "release"]                        # the last write, THEN the place
    assert os.path.isfile(os.path.join(vol, "rec", "7", "e1", os.path.basename(seg)))
    assert Slot.from_items("vol", box.vars.get("rec/holds/vol")[0]).released
    b = _recorder(box, "r-2")
    assert b.volume_pass() == "vol"                                    # at once — it used to wait out the hold's forty-five seconds

    # a crash says nothing, and the hold lapses by itself, as before
    c = _recorder(box, "r-3")
    assert c.volume_pass() == ""                                       # held by r-2, which is alive
    box.wall.advance(46)
    assert c.volume_pass() == "vol"


def test_kept_footage_the_ring_took_is_an_alarm():
    """It was a number in the pass's report, a warning in a log and a reason in the deletions journal: three
    places nobody is woken from. A keep is set so that footage lives until somebody comes for it."""
    box = Box()
    box.vars.put(SPACE_KEY, {"enabled": "true", "high": "0.85", "low": "0.75", "min_days": "3"})
    arch = ArchiveResource(box.spool, box.archive, wall=box.wall)
    now = box.wall()
    for d in range(10, 0, -1):
        start = now - d * DAY
        p = segment_path(box.archive, "7", 1, datetime.fromtimestamp(start, timezone.utc))
        os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(b"x" * 1000)
        Manifest(box.archive, "7").append(Segment("7", 1, start, start + 600, os.path.relpath(p, box.archive), 1000))
    keeps.write(box.vars, {"cam": "7", "from": now - 10 * DAY - 1, "to": now - 9 * DAY + 601}, ["7"], "anna", now)
    res = vms_resource(arch, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    policy = res.hooks["rec"]

    def alarms():
        return [e for e in EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit", cls="alarm")["events"]]

    rep = policy.free(5000, now, min_days=3)
    assert (rep["freed"], rep["cut"]) == (5000, 5) and "kept_cut" not in rep and alarms() == []   # everything else first: no alarm
    assert policy.free(2000, now, min_days=3)["kept_cut"] == 2
    [a] = alarms()
    assert (a["kind"], a["of"], a["target"], a["segments"], a["seconds"]) == ("archive.keep.lost", "rec", "7", 2, 1200.0)
    assert a["from"] == now - 10 * DAY and a["to"] == now - 9 * DAY + 600 and a["unit"] == "resource"


def test_the_recorder_process_holds_a_token_that_can_take_a_volume():
    """`python -m vms recorder` opened the store with a list written by hand before a recorder took volumes —
    epochs and its slot, and not its hold. On a box with a declared volume it was refused its own place."""
    import vms.__main__ as main
    src = inspect.getsource(main.recorder)
    assert 'acl={"recworker": REC_SPEC.sub.acl_worker()}' in src and '"rec/holds/*"' not in src     # derived, not listed by hand
    assert "rec/holds/*" in REC_SPEC.sub.acl_worker()
    box = Box()
    volumes.write(box.vars, {"name": "vol", "kind": "local", "url": os.path.join(box.root, "vol"), "server": "srv-a", "quota_bytes": 10 ** 9})
    r = _recorder(box, "r-1", box.vars.as_writer("recworker", REC_SPEC.sub.acl_worker()))
    assert r.volume_pass() == "vol"
