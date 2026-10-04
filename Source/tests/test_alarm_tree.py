"""An alarm lies in a tree of its own and is kept by days of its own (the platform review; feedback BO).

One bucket used to hold both classes, and a bucket is deleted whole: a year of a driver's statistics kept for one
door alarm, or the alarm gone with the statistics. Alarms are written apart — `<subsystem>.alarms/<unit>/…` —
by the writer; the index reads both trees and answers under the subsystem's name; deleting a camera ends its
observations and not the record of what happened at it.
"""
import json
import os

from w2cplatform.eventdatabase import EventIndex
from w2cplatform.events import ALARM, EventLog, buckets_under, subsystems_under
from w2cplatform.resource import ALARM_DAYS, Resource, retention_days
from vms.config import SPEC
from vms.controller import VmsController
from tests.conftest import Box

DAY = 86400.0


def test_the_writer_picks_the_tree_and_the_index_answers_under_one_name():
    box = Box()
    t = box.wall() - 100
    log = EventLog(box.archive, "vms", "7", 3)
    po = log.append(t, "stats", n=1)
    pa = log.append(t + 1, "io.input", ALARM, port="1")
    assert os.path.relpath(po, box.archive).startswith("vms/7/e3/") and os.path.relpath(pa, box.archive).startswith("vms.alarms/7/e3/")
    assert subsystems_under(box.archive) == {"vms": ["7"], "vms.alarms": ["7"]}    # one more directory, to whatever walks the tree

    # a bucket written BEFORE alarms had a tree holds both classes, in the first one — and is read as it was
    old = po.replace(os.path.basename(po), "20200101T000000Z.events.jsonl")
    with open(old, "w") as f:
        f.write(json.dumps({"t": 1577836805.0, "kind": "io.input", "class": "alarm", "port": "2"}) + "\n")

    db = EventIndex(box.archive, "srv-1", wall=box.wall)
    rows = db.query(0, box.wall(), subsystem="vms")["events"]
    assert [(r["subsystem"], r["kind"], r["class"]) for r in rows] == [
        ("vms", "io.input", "alarm"), ("vms", "stats", "observation"), ("vms", "io.input", "alarm")]
    assert rows[2]["bucket"].startswith("vms.alarms/")                   # where it lies is said; whose it is, is `vms`
    alarms = db.query(0, box.wall(), subsystem="vms", cls="alarm")["events"]
    assert [r["port"] for r in alarms] == ["2", "1"]                     # from the old mixed bucket, and from the new tree
    assert [r["kind"] for r in db.query(0, box.wall(), unit=rows[0]["unit"], cls="observation")["events"]] == ["stats"]   # its unit, `<sub>/<id>`
    assert {r["subsystem"] for r in db.query(0, box.wall())["events"]} == {"vms"}   # …and with no subsystem named, too
    assert db.query(t - 1, t + 5, current_epochs={("vms", "7"): 4})["events"][1]["fenced"] is True   # one epoch for both trees


def test_the_alarms_have_days_of_their_own_and_three_years_when_nobody_said():
    box = Box()
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    a = con.create_camera({"source": "driverpack://file/1.mp4"})["id"]
    b = con.create_camera({"source": "driverpack://file/2.mp4", "events_retention_days": 30, "alarms_retention_days": 400})["id"]
    assert (retention_days(box.vars, "vms", a), retention_days(box.vars, "vms.alarms", a)) == (365.0, 1095.0) and ALARM_DAYS == 1095
    assert (retention_days(box.vars, "vms", b), retention_days(box.vars, "vms.alarms", b)) == (30.0, 400.0)
    assert box.vars.get(f"vms/alarms_retention/{b}")[0] == {"days": "400"}
    assert retention_days(box.vars, "rec.alarms", "7") == 1095.0         # a subsystem with no row for it: `archive.shallow`
    box.vars.put("rec/alarms_retention", {"days": 730})
    assert retention_days(box.vars, "rec.alarms", "7") == 730.0 and retention_days(box.vars, "rec", "7") == 365.0


def test_deleting_a_camera_ends_its_observations_and_not_the_record_of_what_happened():
    box = Box()
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    cam = con.create_camera({"source": "driverpack://file/1.mp4", "alarms_retention_days": 400})["id"]
    t = box.wall() - 2 * DAY
    log = EventLog(box.archive, "vms", str(cam), 1)
    log.append(t, "stats", n=1)
    log.append(t, "io.input", ALARM, port="1")
    res = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    assert res.retain() == 0

    con.delete_camera(cam)
    assert box.vars.get(f"vms/retention/{cam}")[0] == {"days": "0"}       # its observations: gone at the next pass — though
                                                                          # its days were INHERITED and it had no row of its own
    assert box.vars.get(f"vms/alarms_retention/{cam}")[0] == {"days": "400"}   # its alarms: the row is left alone
    assert res.retain() == 1
    assert buckets_under(box.archive, "vms", str(cam), 600) == [] and len(buckets_under(box.archive, "vms.alarms", str(cam), 600)) == 1
    rows = EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall(), subsystem="vms")["events"]
    assert [(r["kind"], r["class"]) for r in rows] == [("io.input", "alarm")]

    box.wall.advance(399 * DAY)
    assert res.retain() == 1 and buckets_under(box.archive, "vms.alarms", str(cam), 600) == []   # …and by their own days, they go


def test_a_keep_holds_the_alarms_tree_as_it_holds_the_other():
    from vms import keeps
    from vms.resource import vms_resource
    box = Box()
    t = box.wall() - 5 * DAY
    EventLog(box.archive, "vms", "7", 1).append(t + 10, "io.input", ALARM, port="1")
    EventLog(box.archive, "vms", "8", 1).append(t + 10, "io.input", ALARM, port="1")
    for cam in ("7", "8"):
        box.vars.put(f"vms/alarms_retention/{cam}", {"days": 1})
    keeps.write(box.vars, {"cam": "7", "from": t, "to": t + 60}, ["7"], "anna", box.wall())
    res = vms_resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    assert res.retain() == 1
    assert len(buckets_under(box.archive, "vms.alarms", "7", 600)) == 1 and buckets_under(box.archive, "vms.alarms", "8", 600) == []
