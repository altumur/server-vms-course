"""What happens when the disk fills — decided, and seen (the platform review; feedback BM).

    the watermark is on     unless somebody turned it off: a full disk with no policy is the recorder, the store
                            and the event log on that partition all failing at once, with nothing decided
    a shortfall is a number over the mark and nothing left to give up — in the resource's heartbeat and on any
                            console's `/metrics`, not in a log line
    a recording has a floor `min_depth_days`: when the watermark cuts inside it, the recorder raises an alarm
"""
import os
from datetime import datetime, timezone

from w2cplatform.console import SpecConsole
from w2cplatform.eventdatabase import EventIndex
from w2cplatform.resource import SPACE_KEY, Resource, space_settings
from vms.archive import ArchivePolicy, ArchiveResource, Manifest, Segment, segment_path
from vms.console import _recorders
from vms.controller import VmsController
from tests.conftest import Box
from tests.test_volumes import _recorder

DAY = 86400.0


def _segments(box, unit="7", days=10, size=1000):
    arch = ArchiveResource(box.spool, box.archive, wall=box.wall)
    for d in range(days, 0, -1):
        start = box.wall() - d * DAY
        p = segment_path(box.archive, unit, 1, datetime.fromtimestamp(start, timezone.utc))
        os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(b"x" * size)
        Manifest(box.archive, unit).append(Segment(unit, 1, start, start + 600, os.path.relpath(p, box.archive), size))
    return arch


def test_the_watermark_is_on_until_somebody_turns_it_off():
    box = Box()
    was = os.environ.pop("WATERMARK_DEFAULT", None)                    # the suite says `off`; an installation says nothing
    try:
        assert space_settings(box.vars) == {"enabled": True, "high": 0.85, "low": 0.75, "min_days": 3.0}
        box.vars.put(SPACE_KEY, {"high": "0.9"})                       # a row that tunes it does not switch it off
        assert space_settings(box.vars)["enabled"] is True and space_settings(box.vars)["high"] == 0.9
        box.vars.put(SPACE_KEY, {"enabled": "false"})                  # the decision not to have one: somebody's
        assert space_settings(box.vars)["enabled"] is False
        os.environ["WATERMARK_DEFAULT"] = "off"
        assert space_settings(Box().vars)["enabled"] is False          # a test suite, on whatever disk it runs on
        box.vars.put(SPACE_KEY, {"enabled": "true"})
        assert space_settings(box.vars)["enabled"] is True             # …and a row still says what it says
    finally:
        os.environ.pop("WATERMARK_DEFAULT", None)
        if was is not None:
            os.environ["WATERMARK_DEFAULT"] = was


def test_what_could_not_be_freed_is_a_number_anybody_can_read():
    """Over the mark, and everything already on the floor. The pass said so in its report, which went to a log.
    It is in the resource's heartbeat now, and a console exports it for every server."""
    box = Box()
    box.vars.put(SPACE_KEY, {"enabled": "true", "high": "0.85", "low": "0.75", "min_days": "3"})
    arch = _segments(box, days=5)                                      # two segments above the floor: 2000 bytes to give
    res = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall,
                   space_probe=lambda root: (1_000_000, 100_000))      # 90 % full: 150 000 to free
    res.register("rec", ArchivePolicy(arch, box.vars))
    assert res.heartbeat()["short"] == 0
    rep = res.relieve()
    assert (rep["freed"], rep["short"]) == (2000, 148_000) and res.heartbeat()["short"] == 148_000
    ctl = VmsController(box.vars, box.objects, wall=box.wall)
    text = SpecConsole(ctl, wall=box.wall).metrics_text()
    assert 'vms_resource_short_bytes{server="srv-1"} 148000' in text and 'vms_resource_full{server="srv-1"} 0.9' in text

    res.space_probe = lambda root: (1_000_000, 500_000)                # somebody added a disk
    assert res.relieve()["space"] == "ok" and res.heartbeat()["short"] == 0
    assert 'vms_resource_short_bytes{server="srv-1"} 0' in SpecConsole(ctl, wall=box.wall).metrics_text()


def test_a_recording_cut_inside_its_floor_raises_an_alarm_and_a_young_one_does_not():
    """`retention_days` is a ceiling. `min_depth_days` is what the recording was promised to HOLD — and the
    watermark, which has one floor for the whole disk, cuts below it. The recorder does not stop that; it says
    so: depth in the status, and the alarm `archive.shallow` when footage inside the floor was deleted."""
    box = Box()
    arch = _segments(box, "7", days=10); _segments(box, "8", days=2)
    r = _recorder(box, "r-1", "srv-a")
    r.rows = [{"id": "7", "cam": "7", "name": "7", "enabled": True, "revision": 1, "min_depth_days": 7.0},
              {"id": "8", "cam": "8", "name": "8", "enabled": True, "revision": 1, "min_depth_days": 7.0}]
    r.epochs = {"7": 4, "8": 2}

    def alarms():
        return [(e["unit"], e["kind"], e["class"], e["depth_days"], e["min_depth_days"])
                for e in EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="rec")["events"]]

    assert r.depth_pass() == {"7": 10.0, "8": 2.0} and alarms() == []   # 8 is young: shallow because it is young
    assert r.status_extra(r.rows[0])["depth_days"] == 10.0 and "shallow" not in r.status_extra(r.rows[1])

    ArchivePolicy(arch, box.vars).free(5000, box.wall(), min_days=3)     # the disk's floor is three days: 10…6 days old go
    box.clock.advance(61)
    assert r.depth_pass()["7"] == 5.0
    assert alarms() == [("7", "archive.shallow", "alarm", 5.0, 7.0)]
    assert r.status_extra(r.rows[0])["shallow"] is True

    box.clock.advance(61); r.depth_pass()
    assert len(alarms()) == 1                                           # not every minute
    box.clock.advance(61); box.wall.advance(DAY + 1); r.depth_pass()
    assert len(alarms()) == 2                                           # once a day while it lasts
    box.clock.advance(61); box.wall.advance(2 * DAY); r.depth_pass()     # what was cut would be past the floor by now
    assert "shallow" not in r.status_extra(r.rows[0]) and len(alarms()) == 2

    from w2cplatform.contract import Heartbeat
    from w2cplatform.spec import SpecController
    from vms.config import REC_SPEC
    rec = SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall)
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-1"), Heartbeat("r-1", box.wall(), [
        {"id": "7", "phase": "running", "depth_days": 5.0, "shallow": True},
        {"id": "8", "phase": "running", "depth_days": 2.0}], {"server": "srv-a"}).to_bytes())
    text = "\n".join(_recorders(rec))
    for line in ('rec_archive_depth_days{unit="7"} 5.0', 'rec_archive_shallow{unit="7"} 1', 'rec_archive_shallow{unit="8"} 0'):
        assert line in text, line
    assert rec.create({"name": "9", "cam": "9", "min_depth_days": 14})["min_depth_days"] == 14.0     # a field of the row
