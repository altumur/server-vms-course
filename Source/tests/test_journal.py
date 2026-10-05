"""What was done to the system, and by whom: the `audit` family in the event log (the platform review; feedback BN).

A deleted unit left a tombstone and no name. The retention pass said one number in a log. And a recorder that had
lost its volume kept the recordings assigned to it, recorded by nobody.
"""
import io
import json
import urllib.request

from w2cplatform.contract import Heartbeat
from w2cplatform.eventdatabase import EventIndex
from w2cplatform.events import EventLog
from w2cplatform.resource import Resource, retention_days
from w2cplatform.spec import SpecController
from vms import volumes
from vms.config import REC_SPEC, SPEC
from vms.console import serve
from vms.controller import VmsController
from tests.vmsconftest import Box

DAY = 86400.0


def _audit(box, role="console"):
    rows = EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit", unit=f"audit/{role}")["events"]
    return [{k: v for k, v in r.items() if k not in ("id", "t", "server", "bucket", "epoch", "epoch_is", "fenced", "cam", "class", "subsystem", "unit")} for r in rows]


def test_who_deleted_it_who_kept_it_and_who_took_the_volume_away():
    box = Box()
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    mounted = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    cam = ctl.create_camera({"source": "driverpack://file/1.mp4"})["id"]
    mounted.create({"name": "1", "cam": "1"})
    srv = serve(ctl, box.archive, port=0, wall=box.wall, mounts={"rec": mounted})
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(method, path, body=None, user="anna"):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                     method=method, headers={"X-User": user, "Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return json.load(r)

    try:
        t = box.wall()
        keep = call("POST", "/rec/keeps", {"cam": "1", "from": t - 900, "to": t - 300})["row"]["name"]
        call("DELETE", f"/rec/keeps/{keep}", user="boris")
        vol = {"name": "cold", "kind": "network", "url": "s3://vms/x", "quota_bytes": 10 ** 12}
        call("POST", "/rec/volumes", vol)
        call("POST", "/rec/volumes", {**vol, "quota_bytes": 10 ** 11}, user="boris")       # "give this archive less"
        call("DELETE", "/rec/volumes/cold")
        call("DELETE", "/rec/recordings/1", user="boris")                                   # through a MOUNT: the same journal
        call("DELETE", f"/cameras/{cam}")
    finally:
        srv.shutdown()
    said = _audit(box)
    put, gone = (mounted.spec.table_specs["volumes"].journal[k] for k in ("written", "deleted"))   # the spec's words
    assert [(e["kind"], e["user"]) for e in said] == [
        ("archive.keep.made", "anna"), ("archive.keep.lifted", "boris"), (put, "anna"), (put, "boris"), (gone, "anna"),
        ("unit.deleted", "boris"), ("unit.deleted", "anna")]
    # what a write changed, and from what — the spec's table, written by the platform since the boundary's step 6; a
    # smaller quota is applied by whoever holds the row, on the operator's second word (the review's fourth pass)
    assert said[3]["changed"] == "quota_bytes" and said[3]["was"] == {"quota_bytes": 10 ** 12}
    assert "changed" not in said[2]                                                  # a new row: nothing was
    gone = [e for e in _raw(box) if e["kind"] == "unit.deleted"]
    assert [(e["subsystem"], e["unit"]) for e in gone] == [("audit", "audit/console")] * 2       # whose line it is…
    assert [(e["sub"], e["target"]) for e in gone] == [("rec", "1"), ("vms", str(cam))]     # …and what it is about


def _raw(box):
    return EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="audit")["events"]


def test_the_retention_pass_says_whose_buckets_it_removed_and_the_journal_outlives_them():
    box = Box()
    t = box.wall() - 3 * DAY
    EventLog(box.archive, "vms", "7", 1).append(t, "motion"); EventLog(box.archive, "vms", "7", 1).append(t + 700, "motion")
    EventLog(box.archive, "vms", "8", 1).append(t, "motion")
    box.vars.put("vms/retention/7", {"days": 1})
    res = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    assert res.retain() == 2
    [line] = _audit(box, "resource")
    assert (line["kind"], line["buckets"], line["days"]) == ("events.removed", 2, 1.0) and line["since"] <= t < line["until"]
    assert retention_days(box.vars, "audit", "resource") == 1095.0       # kept as long as alarms are
    box.wall.advance(400 * DAY)
    res.retain()                                                         # camera 8's year is over; the journal's is not
    assert [e["buckets"] for e in _audit(box, "resource")] == [2, 1]


def test_a_recorder_that_holds_no_volume_gives_its_recordings_up():
    """Two recorders restarted and the other took the volume. The first is alive, holds its slot, and cannot write
    a byte — and the recordings assigned to it stayed there, recorded by nobody, because placement only moves
    what a released slot or a gone server left. It says `volume: ""` itself; the pass moves them."""
    box = Box()
    volumes.write(box.vars, {"name": "vol-a", "kind": "local", "url": box.archive, "server": "srv-a", "quota_bytes": 10 ** 9})
    ctl = SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall)

    def beat(name, volume, capacity):
        box.objects.put(REC_SPEC.sub.heartbeat_key(name), Heartbeat(name, box.wall(), [], {
            "server": "srv-a", "volume": volume, "capacity": capacity, "headroom": capacity}).to_bytes())

    box.objects.put("platform/resources/srv-a/heartbeat",
                    json.dumps({"server": "srv-a", "ts": box.wall(), "url": "http://srv-a", "units": {},
                                "space": {"total": 10 ** 9, "free": 10 ** 9}}).encode())
    beat("r-1", "vol-a", 50); beat("r-2", "", 0)
    ctl.create({"name": "7", "cam": "7"}); ctl.ensure_placed()
    assert ctl.where("7") == "r-1" and ctl.redistribute() == []
    beat("r-1", "", 0); beat("r-2", "vol-a", 50)                         # both restarted; the other took the volume
    moves = ctl.redistribute()
    assert moves == [("7", "r-1", "r-2")] and ctl.where("7") == "r-2"
    assert "r-1 holds no volume now" in ctl.placement("7").reason
    assert ctl.redistribute() == []
