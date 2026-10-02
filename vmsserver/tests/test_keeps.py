"""What somebody said to keep: `rec/keeps/<id>` (the platform review, blocker 10; feedback BH).

Footage is in volumes, and a volume is a ring: ten minutes of one camera that are evidence go with the rest when
their turn comes. A keep is a row — a camera, an interval, a note, who set it — and the recorder holding an
INCIDENTS volume copies what it names into that volume, out of whichever recorder's door has it. The copy outlives
the recording's own ring; what was copied is an event with its sha256; and kept footage the incidents ring itself
took is an alarm. Retention skips the camera's event buckets a keep overlaps.
"""
import io
import json
import tempfile
import urllib.request

from w2cplatform.eventdatabase import EventIndex
from w2cplatform.spec import SpecController
from vms import keeps, volumes
from vms.archive import event_log
from vms.config import REC_SPEC
from vms.console import rec_routes
from vms.worker import fake_samples
from tests.conftest import TEST_QUOTA, Box, door, footage, recorder, store

DAY = 86400.0


class _Body:
    def __init__(self, payload: dict, user: str = ""):
        raw = json.dumps(payload).encode()
        self.headers, self.rfile = {"Content-Length": str(len(raw)), **({"X-User": user} if user else {})}, io.BytesIO(raw)


def _site(quota: int = TEST_QUOTA, source: bool = True):
    """A recording's volume behind its recorder's door, and a recorder holding the incidents volume `evidence`."""
    box = Box()
    if source:
        box.src = store("disks")
        box.src_door = door(box, box.src, "r-disks", "srv-1")
    volumes.write(box.vars, {"name": "evidence", "kind": "incidents", "server": "srv-1",
                             "url": tempfile.mkdtemp(prefix="evidence-"), "quota_bytes": quota})
    k = recorder(box, "r-keep", "srv-1", acl=False)
    k.lease_pass()
    assert k.volume == "evidence" and k.incidents and k.store is not None
    return box, k


def _keep(box, cam, since, until, recordings=None):
    return keeps.write(box.vars, {"cam": cam, "from": since, "to": until, "note": "the gate"},
                       recordings if recordings is not None else [cam], "anna", box.wall())


def _events(box, kind):
    return [e for e in EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="rec")["events"]
            if e["kind"] == kind]


def test_an_incidents_volume_is_a_place_for_evidence_and_never_one_to_record_into():
    box, k = _site(source=False)
    assert k.capacity == 0 and k.heartbeat_extra()["keeps"] == {}
    from vms.config import REC_SPEC as spec
    rec = SpecController(spec, box.vars, box.objects, wall=box.wall)
    k.heartbeat_once()
    rec.create({"name": "7", "cam": "7"})
    rec.ensure_placed()
    assert rec.placement("7") is None                                  # nothing is placed on it, whatever its headroom


def test_a_keep_is_copied_into_the_incidents_volume_and_outlives_the_recordings_ring():
    box, k = _site()
    t = box.wall()
    footage(box.src, "7", 1, t - 3600, t, step=10)
    kp = _keep(box, "7", t - 1800, t - 1200)
    state = k.keep_pass()
    assert state[kp.id]["copied"] == 600 and state[kp.id]["missing"] == 0
    assert [(s.stream, s.start, s.end) for s in k.store.spans("7")] == [("7/e0", t - 1800, t - 1200)]
    [ev] = _events(box, "archive.keep.copied")
    assert ev["keep"] == kp.id and ev["recording"] == "7" and ev["sha256"] == state[kp.id]["sha256"]["7"]
    assert k.heartbeat_extra()["keeps"][kp.id]["copied"] == 600

    assert k.keep_pass()[kp.id]["sha256"] == state[kp.id]["sha256"]    # nothing new to copy, the digest still said
    assert len(_events(box, "archive.keep.copied")) == 1

    box.src_door.shutdown()                                            # the recording's ring moved on — or its server is gone
    srv = k.serve_archive()
    try:
        got = json.loads(urllib.request.urlopen(f"{k.archive_url}/timeline/7?from=0").read())
        assert [(sp["start"], sp["end"], sp["epoch"]) for sp in got["spans"]] == [(t - 1800, t - 1200, 0)]
        frames = k.read_samples(k.archive_url, "7", t - 1800, t - 1200)
        assert frames and frames[0].key                                # and the frames are served, as any recording's
    finally:
        srv.shutdown()


def test_a_keep_holds_a_recording_whose_row_is_gone_and_one_made_after_it():
    """A volume knows footage by the recording's name; the row says whose it is. Delete the recording and nothing
    ties `7-cloud` to camera 7 — so the keep wrote the names down. A recording of the camera made AFTER the keep is
    matched by its row."""
    box, k = _site()
    t = box.wall()
    for rec in ("7-cloud", "7-new", "8"):
        footage(box.src, rec, 1, t - 3600, t, step=10, seal=False)
    box.src.seal()
    box.vars.put("rec/recordings/7-new", {"id": "7-new", "name": "7-new", "cam": "7"})
    box.vars.put("rec/recordings/8", {"id": "8", "name": "8", "cam": "8"})
    _keep(box, "7", t - 1800, t - 1200, recordings=["7", "7-cloud"])   # `7` has nothing anywhere: missing, said
    state = k.keep_pass()
    assert k.store.units() == ["7-cloud", "7-new"]                     # and nothing of camera 8
    [entry] = state.values()
    assert entry["copied"] == 1200 and entry["missing"] == 600


def test_kept_footage_the_incidents_ring_took_is_an_alarm():
    """A keep is not "never": the incidents volume is a ring too. Given more than it holds, the oldest kept
    footage goes — and that is `archive.keep.lost`, with how much, not a quiet cut."""
    box, k = _site(quota=16 << 20)
    t = box.wall()
    for smp in fake_samples(t - 1200, t, step=10, size=256 << 10):    # a quarter of a megabyte every ten seconds
        box.src.put("7", 1, smp)
    box.src.finish("7", 1); box.src.seal()
    first = _keep(box, "7", t - 1200, t - 900)                         # 7.5 MB
    k.keep_pass()
    assert k.keep_held[(first.id, "7")] == 300
    _keep(box, "7", t - 800, t - 500); _keep(box, "7", t - 400, t - 100)
    k.keep_pass()                                                      # 15 MB more into a ring of 16
    assert k.store.status()["firstBlockId"] > 0                        # the ring has closed
    box.src_door.shutdown()                                            # and the recording's own copy is gone too
    state = k.keep_pass()
    alarms = _events(box, "archive.keep.lost")
    assert first.id in {a["keep"] for a in alarms}                     # the oldest went first — and whatever followed it
    assert all(a["class"] == "alarm" and a["seconds"] > 0 for a in alarms)
    assert state[first.id]["missing"] > 0
    k.keep_pass()
    assert len(_events(box, "archive.keep.lost")) == len(alarms)       # said once: what is gone is not lost again


def test_not_being_able_to_read_the_keeps_is_not_there_are_none():
    box, k = _site()
    t = box.wall()
    footage(box.src, "7", 1, t - 3600, t, step=10)
    _keep(box, "7", t - 1800, t - 1200)

    class Away:
        def __init__(self, inner): self.inner = inner
        def get(self, key): return self.inner.get(key)
        def list(self, prefix):
            if prefix == "rec/keeps/":
                raise PermissionError(13, "the store does not answer")
            return self.inner.list(prefix)

    k.vars = Away(box.vars)
    try:
        k.keep_pass()
        raise AssertionError("a pass that could not read the keeps must not run as if there were none")
    except PermissionError:
        pass
    assert k.store.units() == [] and k.keep_state == {}


def test_deleting_the_camera_does_not_erase_the_events_somebody_marked():
    """`{days: 0}` is what a deleted unit's retention becomes: its buckets go on the next pass. The ones
    under a keep do not."""
    from w2cplatform.events import buckets_under
    from vms.resource import vms_resource
    box = Box()
    res = vms_resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
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
    # …and with no incidents volume declared it is ONLY a mark (the review's second pass, B10): said in the
    # answer, counted on `/metrics`, and 201 all the same — the mark is valid, nothing copies it yet.
    from vms.console import rec_metrics
    assert "no incidents volume" in made["warning"] and "rec_keeps_unprotected 1" in rec_metrics(rec)()
    volumes.write(box.vars, {"name": "evidence", "kind": "incidents", "server": "srv-1", "url": tempfile.mkdtemp(prefix="evidence-"),
                             "quota_bytes": TEST_QUOTA})
    status, again = route(_Body(body, user="boris"), "POST", "/keeps", {})        # the same interval: the same row
    assert status == 201 and "warning" not in again and "rec_keeps_unprotected 0" in rec_metrics(rec)()
    status, view = route(None, "GET", "/keeps", {})
    assert status == 200 and [k["id"] for k in view["keeps"]] == [made["keep"]["id"]]

    for bad in ({"from": 1, "to": 2}, {"cam": "7", "from": t, "to": t - 1}, {"cam": "7", "from": "yesterday", "to": t},
                {"cam": "../7", "from": 1, "to": 2}, {"cam": "7", "from": 1, "to": 2, "forever": True},
                {"cam": "7", "from": 1, "to": 2, "note": "x" * 501}):
        assert route(_Body(bad), "POST", "/keeps", {})[0] == 400, bad

    assert route(None, "DELETE", "/keeps/nope", {})[0] == 404
    assert route(None, "DELETE", "/keeps/" + made["keep"]["id"], {})[0] == 200
    assert route(None, "GET", "/keeps", {})[1]["keeps"] == []


def test_a_keep_written_before_its_fields_were_renamed_still_holds():
    """`since`/`until` became `from`/`to` (feedback BQ). A row written before that, read by the new names only,
    would hold nothing — an interval from 0 to 0 — and the footage would go by its days, silently. It is read by
    the old names when the new ones are absent (the product's question, feedback BV)."""
    box = Box()
    box.vars.put("rec/keeps/7-100-200", {"cam": "7", "since": "100.0", "until": "200.0", "note": "", "by": "anna", "at": "50", "recordings": '["7"]'})
    [k] = keeps.declared(box.vars)
    assert (k.since, k.until) == (100.0, 200.0) and keeps.spans_of([k], "7") == [(100.0, 200.0)]



def test_the_list_of_keeps_is_what_the_caller_may_see():
    """Feedback CG: a keep says which camera, which minutes and why. Lifting or checking one asked by its camera;
    the LIST did not, and showed every keep to whoever could see one camera."""
    from types import SimpleNamespace
    from w2cplatform.spec import SpecController
    from vms import keeps as K
    from vms.config import REC_SPEC
    from vms.console import rec_routes
    from tests.conftest import Box
    box = Box()
    rec = SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall)
    for cam in ("1", "3", "ref:SN-A"):
        K.write(box.vars, {"cam": cam, "from": 100.0, "to": 200.0}, [], "anna", box.wall())
    route = rec_routes(rec)
    labels = {"3": ["hall"]}
    boris = SimpleNamespace(headers={}, sees=lambda unit, lab: unit == "1", labels_for=lambda u: labels.get(u, []))
    vera = SimpleNamespace(headers={}, sees=lambda unit, lab: "hall" in lab, labels_for=lambda u: labels.get(u, []))
    open_ = SimpleNamespace(headers={}, sees=None, labels_for=lambda u: [])
    cams = lambda h: sorted(k["cam"] for k in route(h, "GET", "/keeps", {})[1]["keeps"])   # noqa: E731
    assert cams(boris) == ["1"] and cams(vera) == ["3"] and cams(open_) == ["1", "3", "ref:SN-A"]


def test_kept_footage_the_ring_took_while_the_recorder_was_restarting_is_still_an_alarm():
    """The review's third pass, a minor: what each keep held in the incidents volume was in memory only, so a recorder
    started again compared against nothing, and kept footage its ring took meanwhile was never `archive.keep.lost`.
    What was copied is a DURABLE event now, with how much of the keep the volume held, and a recorder starts from it."""
    box, k = _site(quota=16 << 20)
    t = box.wall()
    for smp in fake_samples(t - 1200, t, step=10, size=256 << 10):
        box.src.put("7", 1, smp)
    box.src.finish("7", 1); box.src.seal()
    first = _keep(box, "7", t - 1200, t - 900)
    k.keep_pass()
    [copied] = _events(box, "archive.keep.copied")
    assert copied["seconds"] == 300
    k.after_stop()                                                     # the recorder of the incidents volume goes away…

    again = recorder(box, "r-keep", "srv-1", acl=False)                # …and a new process takes the volume
    again.lease_pass()
    assert again.volume == "evidence" and again.keep_held == {}
    _keep(box, "7", t - 800, t - 500); _keep(box, "7", t - 400, t - 100)
    again.keep_pass()                                                  # its own copies push the first keep out of the ring
    box.src_door.shutdown()
    state = again.keep_pass()
    lost = [a for a in _events(box, "archive.keep.lost") if a["keep"] == first.id]
    assert lost and lost[0]["seconds"] > 0 and state[first.id]["missing"] > 0
