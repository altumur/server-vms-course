import os
"""What happens when the disk fills — decided, and seen (the platform review; feedback BM).

    the watermark is on     unless somebody turned it off: a full disk with no policy is the store and the event
                            log on that partition failing at once, with nothing decided
    a shortfall is a number over the mark and nothing left to give up — in the resource's heartbeat and on any
                            console's `/metrics`, not in a log line
    a recording has a floor `min_depth_days`: footage is in a RING, which gives up its oldest minutes when it is
                            full whatever was promised — when the ring has closed and a recording holds less than
                            its floor, the recorder raises an alarm
"""
from w2cplatform.console import SpecConsole
from w2cplatform.contract import Heartbeat
from w2cplatform.eventdatabase import EventIndex
from w2cplatform.resource import SPACE_KEY, Resource, space_settings
from w2cplatform.metrics import text as spec_metrics
from vms.controller import VmsController
from vms.worker import fake_samples
from tests.vmsconftest import Box, footage, recorder

DAY = 86400.0


def test_the_watermark_is_on_until_somebody_turns_it_off():
    box = Box()
    was = os.environ.pop("WATERMARK_DEFAULT", None)                    # the suite says `off`; an installation says nothing
    try:
        assert space_settings(box.vars) == {"enabled": True, "high": 0.85, "low": 0.75}
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


def _files():
    """A subsystem that keeps files on the resource's disk and can give some up — `requests: {free: true}`, made up here:
    the watermark is the platform's, for whatever a subsystem keeps on that disk, and a test of it needs no product."""
    from w2cplatform import catalog
    from w2cplatform.spec import SubsystemSpec
    spec = SubsystemSpec.from_dict({"name": "files", "unit": {"rows": "files", "id": "name", "fields": {"name": {"type": "string"}}},
                                    "placement": {"capacity": {"from": "capacity", "default": 4}}, "requests": {"free": True, "ttl": 0}})
    catalog.register(spec)
    return spec


def test_what_could_not_be_freed_is_a_number_anybody_can_read():
    """Over the mark, and everything already on the floor. The pass said so in its report, which went to a log.
    It is in the resource's heartbeat now, and a console exports it for every server."""
    box = Box()
    box.vars.put(SPACE_KEY, {"enabled": "true", "high": "0.85", "low": "0.75"})
    res = Resource(box.resource_root, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall,
                   space_probe=lambda root: (1_000_000, 100_000))      # 90 % full: 150 000 to free
    files = _files()
    [vol] = list(res.volumes)
    box.objects.put(files.sub.heartbeat_key("f-1"), Heartbeat("f-1", box.wall(), [], {"server": "srv-1",
                                                                                    "freeing": {vol: 2000}}).to_bytes())
    assert res.heartbeat()["short"] == 0
    rep = res.relieve()
    assert (rep["freeing"], rep["short"]) == (2000, 148_000) and res.heartbeat()["short"] == 148_000
    ctl = VmsController(box.vars, box.objects, wall=box.wall)
    text = SpecConsole(ctl, wall=box.wall).metrics_text()
    assert 'w2c_resource_short_bytes{server="srv-1"} 148000' in text and 'w2c_resource_full{server="srv-1"} 0.9' in text

    res.space_probe = lambda root: (1_000_000, 500_000)                # somebody added a disk
    assert res.relieve()["space"] == "ok" and res.heartbeat()["short"] == 0
    assert 'w2c_resource_short_bytes{server="srv-1"} 0' in SpecConsole(ctl, wall=box.wall).metrics_text()


def test_bytes_still_being_freed_are_not_asked_for_again_and_bytes_freed_are_not_counted_twice():
    """`freeing: {<volume>: bytes}` is what a worker's engine has deleted and the volume does not show yet (ADR 0059;
    it was `freed`, what was given «since the last ask», ADR 0003). Each pass asks for `used − total·low − freeing`:

        lag     an engine that frees asynchronously says 50 000 while `used` has not moved — 150 000 is asked, not 200 000
        no lag  the deletion shows in `used` and the worker says 0 — the need is what `used` says, nothing taken off twice
    """
    box = Box()
    box.vars.put(SPACE_KEY, {"enabled": "true", "high": "0.85", "low": "0.75"})
    disk = {"free": 50_000}                                            # 95 % full: 200 000 over the low mark
    res = Resource(box.resource_root, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall,
                   space_probe=lambda root: (1_000_000, disk["free"]))
    files = _files()
    [vol] = list(res.volumes)
    asked = lambda: box.vars.get(files.sub.request_key(f"free-srv-1-{vol}"))[0]
    say = lambda n: box.objects.put(files.sub.heartbeat_key("f-1"), Heartbeat("f-1", box.wall(), [], {
        "server": "srv-1", "freeing": {vol: n}}).to_bytes())

    say(50_000)                                                        # deleted, not yet visible on the volume
    rep = res.relieve()
    assert (rep["need"], rep["freeing"], asked()["free"]) == (150_000, 50_000, "150000")
    disk["free"] = 100_000                                             # the engine confirms: `used` drops by as much…
    say(0)                                                             # …and the worker stops saying it
    rep = res.relieve()
    assert (rep["need"], rep["freeing"], asked()["free"]) == (150_000, 0, "150000")   # the same, not 100 000

    disk["free"] = 120_000                                             # no lag: 20 000 more gone, and already in `used`
    rep = res.relieve()
    assert (rep["need"], rep["short"], asked()["free"]) == (130_000, 130_000, "130000")   # what `used` says, no less
    say(500_000)                                                       # a word over the need: not below zero
    rep = res.relieve()
    assert rep["space"] == "over" and rep["need"] == rep["short"] == 0 and asked() is None


def test_a_recording_cut_inside_its_floor_raises_an_alarm_and_a_young_ring_does_not():
    """`retention_days` is a ceiling. `min_depth_days` is what the recording was promised to HOLD — and the
    volume is a ring, formatted at its quota, that gives up its oldest minutes when it is full, whatever was
    promised. The recorder does not stop that; it says so: depth in the status, and the alarm `archive.shallow`
    when the ring has CLOSED — begun to overwrite — and a recording holds less than its floor. A ring that has
    not closed is shallow because it is young: nothing was overwritten, nothing is raised."""
    box = Box()
    r = recorder(box, "r-1", "srv-a")
    r.lease_pass()
    r.rows = [{"id": "7", "cam": "7", "name": "7", "enabled": True, "revision": 1, "min_depth_days": 7.0},
              {"id": "8", "cam": "8", "name": "8", "enabled": True, "revision": 1}]
    r.epochs = {"7": 4, "8": 2}
    now = box.wall()
    footage(r.store, "7", 4, now - 10 * DAY, now, step=3600, seal=False)
    footage(r.store, "8", 2, now - 2 * DAY, now, step=3600)

    def alarms():
        return [(e["unit"], e["kind"], e["class"], e["depth_days"], e["min_depth_days"])
                for e in EventIndex(box.resource_root, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="rec")["events"]]

    box.clock.advance(61)                                                # once a minute: `lease_pass` read it already
    assert r.depth_pass() == {"7": 10.0, "8": 2.0} and alarms() == []
    assert r.store.status()["firstBlockId"] == 0                         # the ring has not closed
    assert r.status_extra(r.rows[0])["depth_days"] == 10.0 and "shallow" not in r.status_extra(r.rows[0])

    # something else on the volume writes more than its quota: the ring closes over 7's and 8's days
    for smp in fake_samples(now - 3600, now, step=40, size=1 << 20):
        r.store.put("flood", 1, smp)
    r.store.finish("flood", 1); r.store.seal()
    box.clock.advance(61)
    assert r.store.status()["firstBlockId"] > 0
    assert r.depth_pass()["7"] < 7.0
    assert [a[:3] for a in alarms()] == [("rec/7", "archive.shallow", "alarm")]   # 8 was promised nothing
    assert r.status_extra(r.rows[0])["shallow"] is True and "shallow" not in r.status_extra(r.rows[1])

    box.clock.advance(61); r.depth_pass()
    assert len(alarms()) == 1                                           # not every minute
    box.clock.advance(61); box.wall.advance(DAY + 1); r.depth_pass()
    assert len(alarms()) == 2                                           # once a day while it lasts
    r.rows[0]["min_depth_days"] = 0.0                                   # the promise withdrawn — or a larger quota
    box.clock.advance(61); r.depth_pass()
    assert "shallow" not in r.status_extra(r.rows[0]) and len(alarms()) == 2

    from w2cplatform.contract import Heartbeat
    from w2cplatform.spec import SpecController
    from vms.config import REC_SPEC
    rec = SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall)
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-1"), Heartbeat("r-1", box.wall(), [
        {"id": "7", "phase": "running", "depth_days": 5.0, "shallow": True},
        {"id": "8", "phase": "running", "depth_days": 2.0}], {"server": "srv-a"}).to_bytes())
    text = spec_metrics(rec)
    for line in ('rec_archive_depth_days{unit="7"} 5', 'rec_archive_shallow{unit="7"} 1', 'rec_archive_shallow{unit="8"} 0'):
        assert line in text, line
    assert rec.create({"name": "9", "cam": "9", "min_depth_days": 14})["min_depth_days"] == 14.0     # a field of the row
