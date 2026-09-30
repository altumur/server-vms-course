"""What somebody said to keep: `rec/keeps/<id>` (the platform review, blocker 10; feedback BH).

Retention by days deleted what was old and the watermark deleted what was in the way, and neither knew that
ten minutes of one camera were evidence. A keep is a row: a camera, an interval, a note, who set it. Retention
skips what it names — footage and events; the watermark takes it last, and says so when it does; and every
segment a policy removes is a line in the archive's deletions journal.
"""
import io
import json
import os
from datetime import datetime, timezone

from w2cplatform.spec import SpecController
from vms import keeps
from vms.archive import ArchivePolicy, ArchiveResource, Deletions, Manifest, Segment, event_log, segment_path
from vms.config import REC_SPEC
from vms.console import rec_routes
from tests.conftest import Box

DAY = 86400.0


class _Body:
    def __init__(self, payload: dict, user: str = ""):
        raw = json.dumps(payload).encode()
        self.headers, self.rfile = {"Content-Length": str(len(raw)), **({"X-User": user} if user else {})}, io.BytesIO(raw)


def _archive(box, units=("7",), days=10, size=1000):
    """One segment a day, `days` deep, for each unit: day 10 is the oldest, day 1 is yesterday."""
    arch = ArchiveResource(box.spool, box.archive, wall=box.wall)
    now = box.wall()
    for unit in units:
        for d in range(days, 0, -1):
            start = now - d * DAY
            p = segment_path(box.archive, unit, 1, datetime.fromtimestamp(start, timezone.utc))
            os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(b"x" * size)
            Manifest(box.archive, unit).append(Segment(unit, 1, start, start + 600, os.path.relpath(p, box.archive), size))
    return arch


def _ages(box, unit) -> list[int]:
    """How many days old each segment left in the manifest is."""
    return sorted(round((box.wall() - s.start) / DAY) for s in Manifest(box.archive, unit).read())


def _keep(box, cam, d_from, d_to, recordings=None):
    """Keep what is between `d_from` and `d_to` days old."""
    now = box.wall()
    return keeps.write(box.vars, {"cam": cam, "from": now - d_from * DAY - 1, "to": now - d_to * DAY + 601, "note": "the gate"},
                       recordings if recordings is not None else [cam], "anna", now)


def test_retention_by_days_leaves_what_a_keep_names_and_takes_it_when_the_keep_is_gone():
    box = Box()
    arch = _archive(box)
    box.vars.put("rec/recordings/7", {"name": "7", "cam": "7", "retention_days": 5})
    k = _keep(box, "7", 9, 8)                                          # the segments 9 and 8 days old
    policy = ArchivePolicy(arch, box.vars)
    rep = policy.pass_(box.wall())
    assert (rep["media_removed"], rep["media_kept"]) == (3, 2)         # 10, 7 and 6 days old go; 9 and 8 stay
    assert _ages(box, "7") == [1, 2, 3, 4, 5, 8, 9]
    gone = Deletions(box.archive).read("7")
    assert sorted(round((box.wall() - d["start"]) / DAY) for d in gone) == [6, 7, 10]
    assert {d["why"] for d in gone} == {"retention"} and all(d["days"] == 5 and d["bytes"] == 1000 for d in gone)
    assert policy.pass_(box.wall())["media_removed"] == 0              # and again: nothing, and nothing counted twice

    keeps.delete(box.vars, k.id)                                       # the keep is lifted: its days apply again
    assert policy.pass_(box.wall()) == {"added": 0, "dropped": 0, "media_removed": 2}
    assert _ages(box, "7") == [1, 2, 3, 4, 5]


def test_a_keep_holds_a_recording_whose_row_is_gone_and_one_made_after_it():
    """The archive knows footage by the recording's name; the row says whose it is. Delete the recording and
    nothing ties `7-cloud` to camera 7 — so the keep wrote the names down. A recording of the camera made
    AFTER the keep is matched by its row."""
    box = Box()
    arch = _archive(box, units=("7-cloud", "7-new", "8"))
    box.vars.put("rec/recordings/7-new", {"name": "7-new", "cam": "7", "retention_days": 5})
    box.vars.put("rec/recordings/8", {"name": "8", "cam": "8", "retention_days": 5})
    _keep(box, "7", 9, 8, recordings=["7", "7-cloud"])                 # `7-cloud` has no row: 30 days, all of it stays anyway
    box.wall.advance(30 * DAY)
    ArchivePolicy(arch, box.vars).pass_(box.wall())
    assert _ages(box, "7-cloud") == [38, 39] and _ages(box, "7-new") == [38, 39] and _ages(box, "8") == []


def test_the_watermark_takes_everything_else_first_and_then_the_ring_reaches_the_kept():
    """A keep is not "never". The disk is a ring: full, and nothing but kept footage above the floor, the
    oldest kept segment goes — counted, and in the journal under its own reason. A recorder that stops
    recording today to protect last month is what nobody chose."""
    box = Box()
    arch = _archive(box)
    _keep(box, "7", 10, 9)                                             # the two OLDEST segments
    policy = ArchivePolicy(arch, box.vars)

    rep = policy.free(3000, box.wall(), min_days=3)                    # three segments' worth
    assert rep == {"freed": 3000, "cut": 3}
    assert _ages(box, "7") == [1, 2, 3, 4, 5, 9, 10]                   # 8, 7, 6 went; the kept ones are older and still here

    rep = policy.free(3000, box.wall(), min_days=3)                    # …and more than the rest above the floor
    assert rep == {"freed": 3000, "cut": 3, "kept_cut": 1}             # 5 and 4, then the ring: the OLDEST kept
    assert _ages(box, "7") == [1, 2, 3, 9]
    assert [d["why"] for d in Deletions(box.archive).read()] == ["pressure"] * 5 + ["pressure-kept"]

    rep = policy.free(5000, box.wall(), min_days=3)                    # the last kept one, and then the floor
    assert rep["kept_cut"] == 1 and rep["shortfall"] == 4000 and _ages(box, "7") == [1, 2, 3]


def test_a_kept_segment_under_the_floor_is_as_safe_as_any_other():
    box = Box()
    arch = _archive(box, days=3)
    _keep(box, "7", 2, 2)
    rep = ArchivePolicy(arch, box.vars).free(10_000, box.wall(), min_days=3)
    assert rep == {"freed": 0, "cut": 0, "shortfall": 10_000} and _ages(box, "7") == [1, 2, 3]


def test_not_being_able_to_read_the_keeps_is_not_there_are_none():
    box = Box()
    arch = _archive(box)
    box.vars.put("rec/recordings/7", {"name": "7", "cam": "7", "retention_days": 5})
    _keep(box, "7", 9, 8)

    class Away:
        def __init__(self, inner): self.inner = inner
        def get(self, key): return self.inner.get(key)
        def list(self, prefix):
            if prefix == "rec/keeps/":
                raise PermissionError(13, "the store does not answer")
            return self.inner.list(prefix)

    policy = ArchivePolicy(arch, Away(box.vars))
    for act in (lambda: policy.pass_(box.wall()), lambda: policy.free(3000, box.wall(), min_days=3)):
        try:
            act()
            raise AssertionError("a policy that could not read the keeps must not run")
        except PermissionError:
            pass
    assert len(_ages(box, "7")) == 10 and Deletions(box.archive).read() == []


def test_deleting_the_camera_does_not_erase_the_events_somebody_marked():
    """`{days: 0}` is what a deleted unit's retention becomes: its buckets go on the next pass. The ones
    under a keep do not."""
    from w2cplatform.events import buckets_under
    from vms.resource import vms_resource
    box = Box()
    arch = ArchiveResource(box.spool, box.archive, wall=box.wall)
    res = vms_resource(arch, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    t0 = box.wall() - 5 * DAY
    log = event_log(box.archive, 7, 3)
    log.append(t0 + 10, "alarm", zone="gate"); log.append(t0 + 3000, "motion")     # two buckets, fifty minutes apart
    event_log(box.archive, 8, 1).append(t0 + 10, "motion")
    keeps.write(box.vars, {"cam": "7", "from": t0, "to": t0 + 60}, ["7"], "anna", box.wall())
    box.vars.put("vms/retention/7", {"days": 0}); box.vars.put("vms/retention/8", {"days": 0})

    assert res.retain() == 2                                           # camera 8's, and camera 7's outside the keep
    left = buckets_under(box.archive, "vms", "7", 600)
    assert len(left) == 1 and left[0].start <= t0 + 10 < left[0].end and buckets_under(box.archive, "vms", "8", 600) == []


def test_the_console_sets_a_keep_lists_it_and_lifts_it():
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    route = rec_routes(rec)
    assert "rec/keeps/*" in REC_SPEC.acl_console()
    rec.create({"name": "7", "cam": "7"}); rec.create({"name": "7-cloud", "cam": "7"}); rec.create({"name": "9", "cam": "9"})

    t = box.wall()
    body = {"cam": "7", "from": t - 900, "to": t - 300, "note": "the gate, 14:10"}
    status, made = route(_Body(body, user="anna"), "POST", "/keeps", {})
    assert status == 201 and made["keep"]["id"] == f"7-{int(t - 900)}-{int(t - 300)}"
    assert (made["keep"]["by"], made["keep"]["at"], made["keep"]["recordings"]) == ("anna", t, ["7", "7-cloud"])
    assert route(_Body(body, user="boris"), "POST", "/keeps", {})[0] == 201          # the same interval: the same row
    status, view = route(None, "GET", "/keeps", {})
    assert status == 200 and [k["id"] for k in view["keeps"]] == [made["keep"]["id"]]

    for bad in ({"from": 1, "to": 2}, {"cam": "7", "from": t, "to": t - 1}, {"cam": "7", "from": "yesterday", "to": t},
                {"cam": "../7", "from": 1, "to": 2}, {"cam": "7", "from": 1, "to": 2, "forever": True},
                {"cam": "7", "from": 1, "to": 2, "note": "x" * 501}):
        assert route(_Body(bad), "POST", "/keeps", {})[0] == 400, bad

    assert route(None, "DELETE", "/keeps/nope", {})[0] == 404
    assert route(None, "DELETE", "/keeps/" + made["keep"]["id"], {})[0] == 200
    assert route(None, "GET", "/keeps", {})[1]["keeps"] == []


def test_the_resource_says_what_its_policies_deleted_and_why():
    from vms.resource import vms_routes
    box = Box()
    arch = _archive(box, units=("7", "8"))
    box.vars.put("rec/recordings/7", {"name": "7", "cam": "7", "retention_days": 8})
    ArchivePolicy(arch, box.vars).pass_(box.wall())                    # 7: two segments past eight days; 8: thirty days, nothing
    door = vms_routes(arch, box.objects, "srv-1")
    status, raw, _ = door("/deletions", {})
    lines = json.loads(raw)["deletions"]
    assert status == 200 and [(d["unit"], d["why"]) for d in lines] == [("7", "retention")] * 2
    assert json.loads(door("/deletions?unit=8", {})[1])["deletions"] == []
    assert len(json.loads(door("/deletions?unit=7&limit=1", {})[1])["deletions"]) == 1
    assert door("/deletions?limit=many", {})[0] == 400
