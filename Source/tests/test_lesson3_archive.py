"""Lesson 3 — the archive is a volume: streams named by recording and epoch, an index that answers by time, a ring
that keeps what fits, retention as a ceiling on what is shown — and events beside it, on the resource."""
import json
import os
from datetime import datetime, timezone

from vms.archive import parse_stream, stream_name, visible_from
from vms.recworker import archive_routes
from tests.vmsconftest import Box, footage, store


def utc(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()


def test_a_stream_is_named_by_its_recording_and_its_epoch():
    # The first part is the RECORDING, and it comes back as a string: the grammar never knew that a recording
    # tended to be named after a camera, and `7-backup` parses exactly the same way.
    assert stream_name("7", 5) == "7/e5" and parse_stream("7/e5") == ("7", 5, "live")
    assert parse_stream("7-backup/e5") == ("7-backup", 5, "live")
    assert stream_name("7", 5, backfill=True) == "7/e5/backfill" and parse_stream("7/e5/backfill") == ("7", 5, "backfill")
    for other in ("7", "7/5", "7/e5/x", "/e5", "7/e5/backfill/1"):
        assert parse_stream(other) is None, other                  # a stream that is not a recording's: not ours to read


def test_written_is_readable_once_its_block_is_closed():
    """The order a recorder lives by. A sample taken is not a sample readable: a reader sees closed blocks only,
    and a block closes when the next begins or the writer closes. A recorder that must answer NOW — a stop, a
    copied range — closes its writer and takes it again (`Archive.seal`)."""
    st = store()
    t = utc("2026-09-12T10:00:00")
    footage(st, "7", 3, t, t + 600, seal=False)
    assert st.coverage("7") == []                                  # written, in an open block
    st.seal()
    assert st.coverage("7") == [(t, t + 600)]


def test_the_timeline_marks_a_fenced_epoch_and_spans_two_volumes():
    """A recorder fenced with footage in flight goes on writing its own stream for a moment: `7/e3` beside the
    survivor's `7/e4`. Nothing is overwritten — two streams — and the timeline shows the zombie's minutes, kept
    and told apart. A second volume (another server's) holds later footage; the console merges the doors."""
    st = store()
    t = utc("2026-09-12T10:00:00")
    footage(st, "7", 3, t, t + 600, seal=False)
    footage(st, "7", 4, t + 600, t + 1200, seal=False)
    footage(st, "7", 3, t + 600, t + 900)                          # the zombie's, going on where e3 left off
    tl = st.timeline("7", t + 300, t + 1800, current_epoch=4)
    assert [(x["epoch"], x["start"] - t, x["end"] - t, x["fenced"]) for x in tl] == [(3, 0, 900, True), (4, 600, 1200, False)]
    other = store("other")
    footage(other, "7", 5, t + 1200, t + 1800)
    merged = sorted(st.timeline("7", 0, 1e12) + other.timeline("7", 0, 1e12), key=lambda x: (x["start"], x["epoch"]))
    assert [x["epoch"] for x in merged] == [3, 4, 5]


def test_retention_is_a_ceiling_on_what_is_shown_and_the_ring_decides_what_is_there():
    """Nothing deletes footage by days any more: the volume is a ring formatted at its quota, and it gives up its
    oldest minutes when it is full. `retention_days` says how far back the doors SHOW a recording — a promise
    about what is visible, not a job that runs at night."""
    st = store()
    now = utc("2026-10-20T00:00:00")
    for day in (1, 10, 19):
        start = utc(f"2026-10-{day:02d}T10:00:00")
        footage(st, "7", 3, start, start + 600, step=10, seal=False)
    st.seal()
    routes = archive_routes(lambda: st, lambda: now, visible_from=lambda unit: visible_from({"retention_days": "8"}, now))
    code, body, _ = routes("/spans/7?from=0")
    assert code == 200 and [s["start"] for s in json.loads(body)["spans"]] == [utc("2026-10-19T10:00:00")]
    assert len(st.spans("7")) == 3                                 # …and all three are still in the volume
    assert visible_from(None, now) == now - 30 * 86400             # no row: thirty days, not "for ever"


def test_events_are_buckets_on_the_resource_recording_or_not():
    """An event is an observation, written by the WORKER holding the camera's epoch, into the camera's bucket on
    the worker's server's resource — `vms/<cam>/e<epoch>/` — recording or not. Footage is the RECORDER's, in a
    volume, under its own epoch: `7/e<epoch>`. Two places, two writers, one camera: a camera that is watched and
    never recorded has buckets and no stream; the volume's index answers for media, the resource's event index
    for the buckets; each is kept by its own rule. No controller wrote any of it."""
    from vms.archive import event_log
    from w2cplatform.events import parse_bucket, read_bucket, subsystems_under
    from w2cplatform.eventdatabase import EventIndex
    from w2cplatform.resource import Resource
    box = Box()
    st = store()
    t0 = utc("2026-09-12T10:00:00")
    box.wall.t = t0 + 2000
    log = event_log(box.archive, 7, 3)                             # the worker holds epoch 3 for camera 7
    p = log.append(t0 + 12.5, "motion", zone="gate")               # not recorded: still an event
    assert parse_bucket(p, box.archive) == ("vms", "7", 3, t0) and read_bucket(p)[0]["zone"] == "gate"
    log.append(t0 + 40.0, "silent")                                # the event with no footage, by definition
    p2 = log.append(t0 + 700.0, "person", score=0.9)               # the next bucket: rolled by the clock
    assert subsystems_under(box.archive) == {"vms": ["7"]} and st.units() == []   # watched, not recorded
    db = EventIndex(box.archive, "box", wall=box.wall)
    assert [e["kind"] for e in db.query(t0, t0 + 1200, unit="vms/7")["events"]] == ["motion", "silent", "person"]
    # now a recorder records the camera under ITS epoch, into its volume: a span on the timeline, the events still the worker's
    footage(st, "7", 4, t0 + 600, t0 + 1200)
    assert st.units() == ["7"]
    assert [(x["epoch"], x["fenced"]) for x in st.timeline("7", t0, t0 + 1200, current_epoch=4)] == [(4, False)]
    assert subsystems_under(box.archive) == {"vms": ["7"]}         # the resource's tree holds no footage at all
    # bucket retention is the platform's, and footage is not on its tree for it to touch
    box.vars.put("vms/retention/7", {"days": 30})                  # what the VMS controller writes for a camera's events
    platform = Resource(box.archive, "box", "http://box", box.vars, box.objects, wall=lambda: t0 + 40 * 86400)
    platform.index = db
    assert platform.retain() == 2 and not os.path.exists(p) and not os.path.exists(p2)
    assert db.query(t0, t0 + 1200, unit="vms/7")["events"] == []
    assert st.coverage("7") == [(t0 + 600, t0 + 1200)]             # the footage, untouched: the ring decides for it
    assert box.vars.list("vms/events") == []
