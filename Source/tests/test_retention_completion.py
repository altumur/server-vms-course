"""A sweep keeps operator records with their material and accounts for every completed deletion."""
import os
from pathlib import Path

import pytest

from tests.conftest import Box
from w2cplatform import resource as resource_module
from w2cplatform.eventdatabase import EventIndex
from w2cplatform.events import ALARM, EventLog
from w2cplatform.resource import MIRROR_DIR, Resource
from w2cplatform.rows import forget

DAY = 86400.0


def _resource(days):
    forget()
    box = Box()
    for family in ("retention", "alarms_retention"):
        box.vars.put("testsub/" + family, {"days": days})
    res = Resource(box.resource_root, "srv-1", "http://srv-1", box.vars, box.objects,
                   wall=box.wall, clock=box.clock, specs=[])
    return box, res


def _mark(box, t):
    return Path(EventLog(box.resource_root, "console", "operator-1", 1).append(
        t, "mark", of="testsub/7", note="Checked"))


def _journal(box):
    return EventIndex(box.resource_root, "srv-1", wall=box.wall).query(
        0, box.wall() + 1, subsystem="audit")["events"]


def test_unknown_days_keep_records_until_the_policy_is_repaired():
    for days in ("broken", "0"):
        box, res = _resource(days)
        t = box.wall() - 1500 * DAY
        log = EventLog(box.resource_root, "testsub", "7", 1)
        material = [Path(log.append(t, "tick")), Path(log.append(t, "alarm", ALARM))]
        record = _mark(box, t)
        assert res.retain() == 0
        assert all(p.exists() for p in [*material, record])
        assert res.retention_garbled == ["testsub.alarms/7", "testsub/7"]
        for family in ("retention", "alarms_retention"):
            box.vars.put("testsub/" + family, {"days": 1})
        assert res.retain() == 3
        assert all(not p.exists() for p in [*material, record])
        assert res.retention_garbled == []


def test_records_outlive_material_found_only_on_a_second_volumes_mirror():
    for days in ("2200", "broken", "0"):
        box, res = _resource(days)
        second = os.path.join(box.root, "second")
        res.volumes["second"] = second
        copy = os.path.join(second, MIRROR_DIR, "peer-1")
        t = box.wall() - 1500 * DAY
        log = EventLog(copy, "testsub", "7", 1)
        material = [Path(log.append(t, "tick")), Path(log.append(t, "alarm", ALARM))]
        record = _mark(box, t)
        assert res.retain() == 0 and res.mirror_removed == 0
        assert all(p.exists() for p in [*material, record])


def test_local_records_also_cover_the_mirrors_extra_hour():
    box, res = _resource("365")
    t = box.wall() - 365 * DAY - 1800
    copy = os.path.join(box.resource_root, MIRROR_DIR, "peer-1")
    material = Path(EventLog(copy, "testsub", "7", 1).append(t, "tick"))
    record = _mark(box, t)
    assert res.retain() == 0 and res.mirror_removed == 0
    assert material.exists() and record.exists()
    box.wall.advance(7200)
    assert res.retain() == 1 and res.mirror_removed == 1
    assert not material.exists() and not record.exists()


def test_a_unit_created_during_inventory_waits_for_the_next_sweep():
    box, _ = _resource("1")
    t = box.wall() - 5 * DAY
    old = Path(EventLog(box.resource_root, "testsub", "7", 1).append(t, "tick"))
    new = []

    class Writer(Resource):
        calls = 0

        def units(self):
            inventory = super().units()
            self.calls += 1
            if self.calls == 1:
                new.append(Path(EventLog(self.root, "testsub", "8", 1).append(t, "tick")))
            return inventory

    res = Writer(box.resource_root, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, specs=[])
    res.index = EventIndex(box.resource_root, "srv-1", wall=box.wall)
    assert len(res.index.query(t - 1, box.wall())["events"]) == 1
    assert res.retain() == 1 and res.calls == 1
    assert not old.exists() and new[0].exists()
    assert not res.index._cache
    assert [(e["target"], e["buckets"]) for e in _journal(box)] == [("7", 1)]
    assert res.retain() == 1 and not new[0].exists()
    assert [(e["target"], e["buckets"]) for e in _journal(box)] == [("7", 1), ("8", 1)]


def _failed_walk(monkeypatch, mirror):
    box, res = _resource("1")
    t = box.wall() - 5 * DAY
    old = Path(EventLog(box.resource_root, "testsub", "7", 1).append(t, "tick"))
    later_tree = os.path.join(box.resource_root, MIRROR_DIR, "peer-1") if mirror else box.resource_root
    later = Path(EventLog(later_tree, "testsub", "8", 1).append(t, "tick"))
    res.index = EventIndex(box.resource_root, "srv-1", wall=box.wall)
    assert len(res.index.query(t - 1, box.wall())["events"]) == 2
    walk = resource_module.bucket_names_under

    def failing_walk(root, sub, unit, *args):
        if root == later_tree and unit == "8":
            raise OSError("later tree cannot be listed")
        return walk(root, sub, unit, *args)

    monkeypatch.setattr(resource_module, "bucket_names_under", failing_walk)
    with pytest.raises(OSError):
        res.retain()
    assert not old.exists() and later.exists()
    assert list(res.index._cache) == [str(later)]
    [entry] = _journal(box)
    assert (entry["kind"], entry["sub"], entry["target"], entry["buckets"], entry["days"]) == (
        "events.removed", "testsub", "7", 1, 1.0)
    assert entry["since"] <= t < entry["until"]


def test_a_later_original_walk_failure_preserves_the_journal_and_forgets_deleted_cache(monkeypatch):
    _failed_walk(monkeypatch, mirror=False)


def test_a_later_mirror_walk_failure_preserves_the_journal_and_forgets_deleted_cache(monkeypatch):
    _failed_walk(monkeypatch, mirror=True)


def test_failure_in_the_pulse_immediately_after_unlink_does_not_lose_the_deletion():
    box, _ = _resource("1")
    t = box.wall() - 5 * DAY
    old = Path(EventLog(box.resource_root, "testsub", "7", 1).append(t, "tick"))

    class FailedPulse(Resource):
        failed = False

        def _progressed(self):
            if not old.exists() and not self.failed:
                self.failed = True
                raise RuntimeError("pulse failed after unlink")
            super()._progressed()

    res = FailedPulse(box.resource_root, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, specs=[])
    res.index = EventIndex(box.resource_root, "srv-1", wall=box.wall)
    res.index.query(t - 1, box.wall())
    with pytest.raises(RuntimeError):
        res.retain()
    assert not old.exists() and not res.index._cache
    assert [(e["target"], e["buckets"]) for e in _journal(box)] == [("7", 1)]


def test_index_forgets_deleted_files_even_if_the_journal_call_raises(monkeypatch):
    box, res = _resource("1")
    t = box.wall() - 5 * DAY
    old = Path(EventLog(box.resource_root, "testsub", "7", 1).append(t, "tick"))
    res.index = EventIndex(box.resource_root, "srv-1", wall=box.wall)
    res.index.query(t - 1, box.wall())

    def failed_journal(*args, **kwargs):
        raise RuntimeError("journal call failed")

    monkeypatch.setattr(res.journal, "say", failed_journal)
    with pytest.raises(RuntimeError):
        res.retain()
    assert not old.exists() and not res.index._cache
