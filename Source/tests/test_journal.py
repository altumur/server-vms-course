"""What was done to the system, and by whom: the `audit` family in the event log (the platform review; feedback BN).

A deleted unit left a tombstone and no name. The retention pass said one number in a log. And a worker that had
lost its place kept the units assigned to it, kept by nobody.
"""
import json
import urllib.request

from w2cplatform.contract import Heartbeat
from w2cplatform.eventdatabase import EventIndex
from w2cplatform.events import EventLog
from w2cplatform.host import spec_console
from w2cplatform.resource import Resource, retention_days
from w2cplatform.tables import write_row
from tests.conftest import Box, console_ctl, controller, testsub2

DAY = 86400.0


def _audit(box, role="console"):
    rows = EventIndex(box.resource_root, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit", unit=f"audit/{role}")["events"]
    return [{k: v for k, v in r.items() if k not in ("id", "t", "server", "bucket", "epoch", "epoch_is", "fenced", "class", "subsystem", "unit")} for r in rows]


def test_who_deleted_it_who_held_it_and_who_took_the_shelf_away():
    box = Box()
    ctl = console_ctl(box)
    mounted = console_ctl(box, testsub2())
    counter = ctl.create({"name": "c1"})["id"]
    mounted.create({"name": "t1", "of": "c1"})
    srv = spec_console({"testsub": ctl, "testsub2": mounted}, "testsub", box.resource_root, wall=box.wall).serve("127.0.0.1", 0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(method, path, body=None, user="anna"):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                     method=method, headers={"X-User": user, "Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.load(r)

    try:
        t = box.wall()
        notch = call("POST", "/testsub2/notches", {"of": "t1", "from": t - 900, "to": t - 300})["row"]["name"]
        call("DELETE", f"/testsub2/notches/{notch}", user="boris")
        shelf = {"name": "cold", "zone": "a", "server": "srv-a"}
        call("POST", "/testsub2/shelves", shelf)
        call("POST", "/testsub2/shelves", {**shelf, "zone": "b"}, user="boris")            # "move this shelf"
        call("DELETE", "/testsub2/shelves/cold")
        call("DELETE", "/testsub2/tallies/t1", user="boris")                               # through a MOUNT: the same journal
        call("DELETE", f"/counters/{counter}")
    finally:
        srv.shutdown()
    said = _audit(box)
    cut, cleared = (mounted.spec.table_specs["notches"].journal[k] for k in ("written", "deleted"))   # the spec's words
    put, gone = (mounted.spec.table_specs["shelves"].journal[k] for k in ("written", "deleted"))
    assert [(e["kind"], e["user"]) for e in said] == [
        (cut, "anna"), (cleared, "boris"), (put, "anna"), (put, "boris"), (gone, "anna"),
        ("unit.deleted", "boris"), ("unit.deleted", "anna")]
    # what a write changed, and from what — the spec's table, written by the platform since the boundary's step 6
    assert said[3]["changed"] == "zone" and said[3]["was"] == {"zone": "a"}
    assert "changed" not in said[2]                                                  # a new row: nothing was
    gone = [e for e in _raw(box) if e["kind"] == "unit.deleted"]
    assert [(e["subsystem"], e["unit"]) for e in gone] == [("audit", "audit/console")] * 2       # whose line it is…
    assert [(e["sub"], e["target"]) for e in gone] == [("testsub2", "t1"), ("testsub", str(counter))]   # …and what it is about


def _raw(box):
    return EventIndex(box.resource_root, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit")["events"]


def test_the_retention_pass_says_whose_buckets_it_removed_and_the_journal_outlives_them():
    box = Box()
    t = box.wall() - 3 * DAY
    EventLog(box.resource_root, "testsub", "c7", 1).append(t, "tick"); EventLog(box.resource_root, "testsub", "c7", 1).append(t + 700, "tick")
    EventLog(box.resource_root, "testsub", "c8", 1).append(t, "tick")
    box.vars.put("testsub/retention/c7", {"days": 1})
    res = Resource(box.resource_root, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    assert res.retain() == 2
    [line] = _audit(box, "resource")
    assert (line["kind"], line["buckets"], line["days"]) == ("events.removed", 2, 1.0) and line["since"] <= t < line["until"]
    assert retention_days(box.vars, "audit", "resource") == 1095.0       # kept as long as alarms are
    box.wall.advance(400 * DAY)
    res.retain()                                                         # counter c8's year is over; the journal's is not
    assert [e["buckets"] for e in _audit(box, "resource")] == [2, 1]


def test_a_worker_that_holds_no_place_gives_its_units_up():
    """Two workers restarted and the other took the place (testsub2's `place_by: shelf`). The first is alive, holds
    its slot, and cannot do its work — and the units assigned to it stayed there, kept by nobody, because placement
    only moves what a released slot or a gone server left. It says `shelf: ""` itself; the pass moves them."""
    box = Box()
    spec = testsub2()
    write_row(spec, "shelves", box.vars, {"name": "shelf-a", "server": "srv-a"}, "anna", box.wall())
    ctl = controller(box, spec=spec)

    def beat(name, shelf, capacity):
        box.objects.put(spec.sub.heartbeat_key(name), Heartbeat(name, box.wall(), [], {
            "server": "srv-a", "shelf": shelf, "capacity": capacity, "headroom": capacity}).to_bytes())

    box.objects.put("platform/resources/srv-a/heartbeat",
                    json.dumps({"server": "srv-a", "ts": box.wall(), "url": "http://srv-a", "units": {},
                                "space": {"total": 10 ** 9, "free": 10 ** 9}}).encode())
    beat("t-1", "shelf-a", 50); beat("t-2", "", 0)
    ctl.create({"name": "t7", "of": "c7"}); ctl.ensure_placed()
    assert ctl.where("t7") == "t-1" and ctl.redistribute() == []
    beat("t-1", "", 0); beat("t-2", "shelf-a", 50)                       # both restarted; the other took the shelf
    moves = ctl.redistribute()
    assert moves == [("t7", "t-1", "t-2")] and ctl.where("t7") == "t-2"
    assert "t-1 holds no shelf now" in ctl.placement("t7").reason
    assert ctl.redistribute() == []
