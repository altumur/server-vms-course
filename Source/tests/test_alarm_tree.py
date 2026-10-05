"""An alarm lies in a tree of its own and is kept by days of its own (the platform review; feedback BO).

One bucket used to hold both classes, and a bucket is deleted whole: a year of a unit's statistics kept for one
alarm, or the alarm gone with the statistics. Alarms are written apart — `<subsystem>.alarms/<unit>/…` —
by the writer; the index reads both trees and answers under the subsystem's name; deleting a unit ends its
observations and not the record of what happened at it.
"""
import json
import os

from w2cplatform.eventdatabase import EventIndex
from w2cplatform.events import ALARM, EventLog, buckets_under, subsystems_under
from w2cplatform.resource import ALARM_DAYS, Resource, retention_days
from tests.conftest import Box, console_ctl, in_catalogue, testsub2

DAY = 86400.0


def test_the_writer_picks_the_tree_and_the_index_answers_under_one_name():
    box = Box()
    t = box.wall() - 100
    log = EventLog(box.tree, "testsub", "c7", 3)
    po = log.append(t, "stats", n=1)
    pa = log.append(t + 1, "lane.jam", ALARM, lane="1")
    assert os.path.relpath(po, box.tree).startswith("testsub/c7/e3/") and os.path.relpath(pa, box.tree).startswith("testsub.alarms/c7/e3/")
    assert subsystems_under(box.tree) == {"testsub": ["c7"], "testsub.alarms": ["c7"]}    # one more directory, to whatever walks the tree

    # a bucket written BEFORE alarms had a tree holds both classes, in the first one — and is read as it was
    old = po.replace(os.path.basename(po), "20200101T000000Z.events.jsonl")
    with open(old, "w") as f:
        f.write(json.dumps({"t": 1577836805.0, "kind": "lane.jam", "class": "alarm", "lane": "2"}) + "\n")

    db = EventIndex(box.tree, "srv-1", wall=box.wall)
    rows = db.query(0, box.wall(), subsystem="testsub")["events"]
    assert [(r["subsystem"], r["kind"], r["class"]) for r in rows] == [
        ("testsub", "lane.jam", "alarm"), ("testsub", "stats", "observation"), ("testsub", "lane.jam", "alarm")]
    assert rows[2]["bucket"].startswith("testsub.alarms/")               # where it lies is said; whose it is, is `testsub`
    alarms = db.query(0, box.wall(), subsystem="testsub", cls="alarm")["events"]
    assert [r["lane"] for r in alarms] == ["2", "1"]                     # from the old mixed bucket, and from the new tree
    assert [r["kind"] for r in db.query(0, box.wall(), unit=rows[0]["unit"], cls="observation")["events"]] == ["stats"]   # its unit, `<sub>/<id>`
    assert {r["subsystem"] for r in db.query(0, box.wall())["events"]} == {"testsub"}   # …and with no subsystem named, too
    assert db.query(t - 1, t + 5, current_epochs={("testsub", "c7"): 4})["events"][1]["fenced"] is True   # one epoch for both trees


def test_the_alarms_have_days_of_their_own_and_three_years_when_nobody_said():
    box = Box()
    con = console_ctl(box, testsub2())
    a = con.create({"name": "t1", "of": "c1"})["id"]
    b = con.create({"name": "t2", "of": "c2", "keep_days": 30, "alarm_days": 400})["id"]
    assert (retention_days(box.vars, "testsub2", a), retention_days(box.vars, "testsub2.alarms", a)) == (365.0, 1095.0) and ALARM_DAYS == 1095
    assert (retention_days(box.vars, "testsub2", b), retention_days(box.vars, "testsub2.alarms", b)) == (30.0, 400.0)
    assert box.vars.get(f"testsub2/alarms_retention/{b}")[0] == {"days": "400"}
    assert retention_days(box.vars, "testsub.alarms", "c7") == 1095.0    # a subsystem with no row for it: `ALARM_DAYS`
    box.vars.put("testsub/alarms_retention", {"days": 730})
    assert retention_days(box.vars, "testsub.alarms", "c7") == 730.0 and retention_days(box.vars, "testsub", "c7") == 365.0


def test_deleting_a_unit_ends_its_observations_and_not_the_record_of_what_happened():
    box = Box()
    con = console_ctl(box, testsub2())
    unit = con.create({"name": "t1", "of": "c1", "alarm_days": 400})["id"]
    t = box.wall() - 2 * DAY
    log = EventLog(box.tree, "testsub2", str(unit), 1)
    log.append(t, "stats", n=1)
    log.append(t, "lane.jam", ALARM, lane="1")
    res = Resource(box.tree, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    assert res.retain() == 0

    con.delete(unit)
    assert box.vars.get(f"testsub2/retention/{unit}")[0] == {"days": "0"}     # its observations: gone at the next pass — though
                                                                              # its days were INHERITED and it had no row of its own
    assert box.vars.get(f"testsub2/alarms_retention/{unit}")[0] == {"days": "400"}   # its alarms: the row is left alone
    assert res.retain() == 1
    assert buckets_under(box.tree, "testsub2", str(unit), 600) == [] and len(buckets_under(box.tree, "testsub2.alarms", str(unit), 600)) == 1
    rows = EventIndex(box.tree, "srv-1", wall=box.wall).query(0, box.wall(), subsystem="testsub2")["events"]
    assert [(r["kind"], r["class"]) for r in rows] == [("lane.jam", "alarm")]

    box.wall.advance(399 * DAY)
    assert res.retain() == 1 and buckets_under(box.tree, "testsub2.alarms", str(unit), 600) == []   # …and by their own days, they go


def test_a_keep_holds_the_alarms_tree_as_it_holds_the_other():
    """A hold (testsub2's `holds:`, a row of its `marks` naming a counter) keeps the counter's alarms past their days,
    as it keeps its observations."""
    from w2cplatform.resource import platform_resource
    from w2cplatform.tables import write_row
    box = Box()
    t = box.wall() - 5 * DAY
    EventLog(box.tree, "testsub", "c7", 1).append(t + 10, "lane.jam", ALARM, lane="1")
    EventLog(box.tree, "testsub", "c8", 1).append(t + 10, "lane.jam", ALARM, lane="1")
    for unit in ("c7", "c8"):
        box.vars.put(f"testsub/alarms_retention/{unit}", {"days": 1})
    write_row(testsub2(), "marks", box.vars, {"of": "c7", "from": t, "to": t + 60}, "anna", box.wall())
    res = platform_resource(box.tree, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    with in_catalogue(testsub2()):                                     # the resource reads the holds testsub2 declares
        assert res.retain() == 1
    assert len(buckets_under(box.tree, "testsub.alarms", "c7", 600)) == 1 and buckets_under(box.tree, "testsub.alarms", "c8", 600) == []
