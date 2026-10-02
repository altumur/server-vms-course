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


def _site(quota: int = TEST_QUOTA, source: bool = True, held: dict | None = None):
    """A recording's volume behind its recorder's door, and a recorder holding the incidents volume `evidence`.
    `held`: `{recording: since}` the source's recorder writes into its volume (the door's `held_since`)."""
    box = Box()
    if source:
        box.src = store("disks")
        box.src_door = door(box, box.src, "r-disks", "srv-1", held=held)
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
    _keep(box, "7", t - 1800, t - 1200, recordings=["7", "7-cloud"])   # `7` has nothing anywhere…
    state = k.keep_pass()
    assert k.store.units() == ["7-cloud", "7-new"]                     # and nothing of camera 8
    [entry] = state.values()
    # …and no door that HOLDS `7` is there to say so: a door of other recordings answering "nothing of it here" is
    # true of every door but the right one (the sixth pass). Short, by all of it, until a door that holds it speaks.
    assert entry["copied"] == 1200 and entry["missing"] == 600


def test_a_second_recording_of_the_camera_that_holds_a_minute_of_the_keep_is_not_short_of_the_rest():
    """The review's fifth pass, a major. Every recording of the keep's camera was counted over the keep's whole
    interval: camera 7 recorded for an hour as `7` and for a minute as `7-ev`, a ten-minute keep copied whole — and
    `7-ev` was nine minutes short for ever, `archive.keep.uncopied` and `rec_keep_missing_seconds` with it. Short is
    only what a source's door shows and the incidents volume does not hold — the rest of `7-ev`'s interval its own
    recorder, writing it there for two hours, has nothing of (`held_since`; the seventh pass)."""
    held = {}
    box, k = _site(held=held)
    t = box.wall()
    held["7-ev"] = t - 7200
    box.vars.put("rec/recordings/7-ev", {"id": "7-ev", "name": "7-ev", "cam": "7"})
    footage(box.src, "7", 1, t - 3600, t, step=10, seal=False)
    footage(box.src, "7-ev", 1, t - 1500, t - 1440, step=10, seal=False)      # one minute, inside the keep
    box.src.seal()
    kp = _keep(box, "7", t - 1800, t - 1200)                           # names `7`; `7-ev` is found by its row
    state = k.keep_pass()
    assert state[kp.id]["copied"] == 660 and state[kp.id]["missing"] == 0
    for _ in range(6):                                                 # past KEEP_UNCOPIED_AFTER
        box.wall.advance(k.KEEP_EVERY); box.src_door.announce()
        k.keep_pass()
    assert _events(box, "archive.keep.uncopied") == []
    assert k.keep_state[kp.id]["missing"] == 0 and k.heartbeat_extra()["keep_missing"] == {}


def test_a_door_that_does_not_hold_the_recording_does_not_say_its_source_has_none():
    """The review's sixth pass, a major. The recording's own door was unreachable and another camera's door answered
    "nothing of `7` here" — true of every door but the right one — and that was taken for the source: `copied 0,
    missing 0`, no alarm, and the recording's ring went on towards the kept minutes. Only a door that holds the
    recording — its recorder's heartbeat names it, or it shows footage of it in the keep's interval — says what the
    source does not have."""
    box, k = _site()                                                   # `r-disks` answers, and holds camera 8 only
    t = box.wall()
    footage(box.src, "8", 1, t - 3600, t, step=10)
    far = store("far")
    footage(far, "7", 1, t - 3600, t, step=10)
    held = [{"id": "7", "phase": "running"}]
    down = door(box, far, "r-far", "srv-1", status=held)               # the recorder of `7`: alive, its door not answering
    down.shutdown(); down.server_close()
    kp = _keep(box, "7", t - 1800, t - 1200)
    state = k.keep_pass()
    assert state[kp.id]["copied"] == 0 and state[kp.id]["missing"] == 600, state
    for _ in range(5):                                                 # past KEEP_UNCOPIED_AFTER: said, not swallowed
        box.wall.advance(k.KEEP_EVERY); box.src_door.announce(); down.announce()
        k.keep_pass()
    [alarm] = _events(box, "archive.keep.uncopied")
    assert alarm["keep"] == kp.id and alarm["seconds"] == 600
    back = door(box, far, "r-far", "srv-1", status=held)               # its door answers again: copied, and whole
    try:
        box.src_door.announce()
        state = k.keep_pass()
        assert state[kp.id]["copied"] == 600 and state[kp.id]["missing"] == 0
    finally:
        back.shutdown()


def test_the_recordings_own_recorder_saying_it_has_nothing_is_believed_and_remembered():
    """The other side of the same rule, and the fifth pass's class kept closed: `7-ev` records on events and has
    nothing in the keep's interval. Its own recorder's door says so — it has written `7-ev` into its volume since
    before the keep's interval (`held_since`, the seventh pass) — and the keep is not short of it; nor after the
    recording is deleted and no recorder writes it any more: what a door that held it said is remembered."""
    box = Box()
    src = store("disks")
    names = [{"id": "7", "phase": "running"}, {"id": "7-ev", "phase": "running"}]
    held = {}
    srv = door(box, src, "r-disks", "srv-1", status=names, held=held)
    volumes.write(box.vars, {"name": "evidence", "kind": "incidents", "server": "srv-1",
                             "url": tempfile.mkdtemp(prefix="evidence-"), "quota_bytes": TEST_QUOTA})
    k = recorder(box, "r-keep", "srv-1", acl=False)
    k.lease_pass()
    try:
        t = box.wall()
        held["7-ev"] = t - 7200                                        # written here for two hours, under its epoch
        box.vars.put("rec/recordings/7-ev", {"id": "7-ev", "name": "7-ev", "cam": "7"})
        footage(src, "7", 1, t - 3600, t, step=10)                     # `7-ev` has no footage at all
        kp = _keep(box, "7", t - 1800, t - 1200, recordings=["7", "7-ev"])
        state = k.keep_pass()
        assert state[kp.id]["copied"] == 600 and state[kp.id]["missing"] == 0
        srv.shutdown()
        srv = door(box, src, "r-disks", "srv-1", status=names[:1])     # `7-ev` deleted: nobody's heartbeat names it now
        box.vars.put("rec/recordings/7-ev", {"id": "7-ev", "name": "7-ev", "cam": "7", "deleted": "true"})
        for _ in range(6):
            box.wall.advance(k.KEEP_EVERY); srv.announce()
            state = k.keep_pass()
        assert state[kp.id]["missing"] == 0 and _events(box, "archive.keep.uncopied") == []
    finally:
        srv.shutdown()


def test_a_recording_that_moved_is_not_said_to_be_missing_from_its_source_by_its_new_holder():
    """The review's seventh pass, a major. The kept minutes of `7` are on `v1`, and `v1`'s door is down; `7` is held
    now by `r-v2`, which has written it into `v2` only since afterwards. `r-v2` truthfully has none of the kept
    minutes — and was believed as "the source has none": `copied 0, missing 0`, no alarm, exactly when the keep
    mattered most. A door speaks only for what its volume could hold — each epoch it shows, first to last moment, and
    the holder from when it took its epoch: the keep is short, said, and then an alarm; copied whole once `v1`'s door
    answers. And inside what the holder DID hold, a hole is believed: nobody has it."""
    box, k = _site(source=False)
    t = box.wall()
    v1, v2 = store("v1"), store("v2")
    footage(v1, "7", 1, t - 3600, t - 900, step=10)                    # epoch 1, in v1
    footage(v2, "7", 2, t - 600, t - 450, step=10, seal=False)         # epoch 2, in v2 since t-600 — with a hole:
    footage(v2, "7", 2, t - 350, t, step=10)                           # the camera dark for 100 s
    down = door(box, v1, "r-v1", "srv-1")
    down.shutdown(); down.server_close()
    now = door(box, v2, "r-v2", "srv-1", status=[{"id": "7", "phase": "running"}], held={"7": t - 600})
    try:
        kept = _keep(box, "7", t - 1800, t - 1200)                     # on v1 only
        dark = _keep(box, "7", t - 500, t - 300)                       # in v2's time, over the hole
        state = k.keep_pass()
        assert state[kept.id]["copied"] == 0 and state[kept.id]["missing"] == 600, state
        assert state[dark.id]["copied"] == 100 and state[dark.id]["missing"] == 0, state   # the hole: nobody has it
        for _ in range(5):                                             # past KEEP_UNCOPIED_AFTER: said, not swallowed
            box.wall.advance(k.KEEP_EVERY); now.announce(); down.announce()
            k.keep_pass()
        [alarm] = _events(box, "archive.keep.uncopied")
        assert alarm["keep"] == kept.id and alarm["seconds"] == 600
        back = door(box, v1, "r-v1", "srv-1")                          # v1's door answers again
        try:
            now.announce()
            state = k.keep_pass()
            assert state[kept.id]["copied"] == 600 and state[kept.id]["missing"] == 0
        finally:
            back.shutdown()
    finally:
        now.shutdown()


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


def test_a_keep_holds_every_subsystems_events_about_its_camera():
    """The review's fourth pass (B10 of the first review). Only the `vms` and `rec` trees were held: the detector's
    alarm at the gate, a scan's hits, a survey's, the scenario that fired — inside the keep, and deleted by their own
    days. Each unit's ROW says which camera it is about: a detector, a watch and a scan by `cam` (a deleted row too),
    a scenario by the units its triggers and actions name. A unit whose camera cannot be told is held by any keep;
    another camera's units go."""
    import json as _json
    from w2cplatform.events import ALARM, EventLog, subsystems_under
    from vms.resource import vms_resource
    box = Box()
    res = vms_resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    t0 = box.wall() - 5 * DAY
    box.vars.put("det/units/7-motion", {"name": "7-motion", "cam": "7", "kind": "motion", "deleted": "true"})  # deleted: {days: 0}
    box.vars.put("det/units/8-motion", {"name": "8-motion", "cam": "8", "kind": "motion"})
    box.vars.put("detjob/jobs/7-lpr-1", {"name": "7-lpr-1", "cam": "7", "rec": "7", "kind": "lpr", "from": t0, "to": t0 + 60})
    box.vars.put("survey/watches/7-lpr", {"name": "7-lpr", "cam": "7", "kind": "lpr"})
    box.vars.put("rec/recordings/7-cloud", {"name": "7-cloud", "cam": "7"})        # made after the keep: not in its names
    box.vars.put("auto/scenarios/gate", {"name": "gate", "when": _json.dumps([{"sub": "det", "kind": "motion", "unit": "7-motion"}]),
                                         "then": _json.dumps([{"sub": "vms", "action": "output", "unit": "12", "port": 1}])})
    box.vars.put("auto/scenarios/yard", {"name": "yard", "when": _json.dumps([{"sub": "vms", "kind": "motion", "unit": "8"}]),
                                         "then": _json.dumps([{"sub": "rec", "action": "record", "cam": "8", "minutes": 1}])})
    box.vars.put("auto/scenarios/anywhere", {"name": "anywhere", "when": _json.dumps([{"sub": "vms", "kind": "silent"}]),
                                             "then": "[]"})                    # any camera: cannot be told
    units = [("det", "7-motion"), ("det", "8-motion"), ("detjob", "7-lpr-1"), ("survey", "7-lpr"), ("rec", "7-cloud"),
             ("auto", "gate"), ("auto", "yard"), ("auto", "anywhere"), ("det", "orphan")]
    for sub, unit in units:
        EventLog(box.archive, sub, unit, 1).append(t0 + 10, "seen", ALARM)            # the alarms' tree…
        EventLog(box.archive, sub, unit, 1).append(t0 + 10, "stats")                  # …and the observations'
        box.vars.put(f"{sub}/retention/{unit}", {"days": 0}); box.vars.put(f"{sub}/alarms_retention/{unit}", {"days": 0})
    keeps.write(box.vars, {"cam": "7", "from": t0, "to": t0 + 60}, ["7"], "anna", box.wall())

    res.retain()
    left = {(sub, u) for sub, us in subsystems_under(box.archive).items() for u in us if sub != "audit"   # the pass's own journal
            if any(f.endswith(".events.jsonl") for _, _, fs in __import__("os").walk(f"{box.archive}/{sub}/{u}") for f in fs)}
    held = {("det", "7-motion"), ("detjob", "7-lpr-1"), ("survey", "7-lpr"), ("rec", "7-cloud"), ("auto", "gate"),
            ("auto", "anywhere"), ("det", "orphan")}
    assert left == held | {(s + ".alarms", u) for s, u in held}                 # camera 8's, in both trees, are gone


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


def test_a_garbled_keep_is_shown_as_it_holds_and_a_recorder_waiting_for_its_volume_is_on_the_volumes_page():
    """The review's eighth pass. Part 4: a keep whose row does not parse holds its camera as far as its interval reads,
    and `GET /keeps` did not list it — a hold nobody could see or lift. It is listed now, `garbled`, with the interval
    it holds and since when this console has seen it so. Part 2: a recorder pinned to a volume whose hold is another's
    says why only in its heartbeat (`volume_wait`); the volumes page names it, on the volume it waits for."""
    from w2cplatform.contract import Heartbeat
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    route = rec_routes(rec)
    t = box.wall()
    box.vars.put("rec/keeps/7-bad", {"cam": "7", "from": "yesterday", "to": str(t), "note": "", "by": "anna", "recordings": '["7"]'})
    _keep(box, "9", t - 900, t - 300)
    status, view = route(None, "GET", "/keeps", {})
    by = {k["id"]: k for k in view["keeps"]}
    assert status == 200 and set(by) == {"7-bad", f"9-{int(t - 900)}-{int(t - 300)}"}
    bad = by["7-bad"]
    assert bad["garbled"] is True and bad["from"] == 0.0 and bad["to"] == t and bad["garbled_since"] == t
    assert json.dumps(view)                                              # no `Infinity` in the answer
    volumes.write(box.vars, {"name": "net", "kind": "network", "url": "s3://bucket/net", "quota_bytes": TEST_QUOTA})
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-9"), Heartbeat("r-9", t, [], {
        "server": "srv-9", "volume": "", "volume_wait": "net is being written by r-2: this recorder is pinned to it"}).to_bytes())
    status, page = route(None, "GET", "/volumes", {})
    net = next(v for v in page["volumes"] if v["name"] == "net")
    assert net["waiting"] == ["r-9"] and page["waiting"][0]["recorder"] == "r-9"


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


def test_a_restarted_recorder_starts_from_what_the_incidents_volume_holds_for_every_recording_of_a_keep():
    """The review's fourth pass, Т-m9. A recorder started again restored what each keep held from the
    `archive.keep.copied` events — written when the copy was made, outside the keep's interval, gone with the event
    tree's retention — and looked for them only under the names the keep wrote down and its own rows, which an
    incidents recorder has none of. A recording of the camera found by its row was restored as nothing, and its loss
    was never an alarm. The incidents volume's own `<recording>/e0` is what a recorder starts from now."""
    import os
    import shutil
    box, k = _site(quota=16 << 20)
    t = box.wall()
    box.vars.put("rec/recordings/7-x", {"id": "7-x", "name": "7-x", "cam": "7"})
    for smp in fake_samples(t - 1200, t, step=10, size=256 << 10):
        box.src.put("7-x", 1, smp)
    box.src.finish("7-x", 1); box.src.seal()
    first = _keep(box, "7", t - 1200, t - 900, recordings=[])          # names nothing: `7-x` is found by its row
    k.keep_pass()
    assert k.keep_held[(first.id, "7-x")] == 300
    k.after_stop()
    shutil.rmtree(os.path.join(box.archive, "rec"))                    # the event tree's retention took the copied events

    again = recorder(box, "r-keep", "srv-1", acl=False)
    again.lease_pass()
    assert again.volume == "evidence" and again.keep_held == {}
    _keep(box, "7", t - 800, t - 500, recordings=[]); _keep(box, "7", t - 400, t - 100, recordings=[])
    again.keep_pass()                                                  # restored from the volume, then its own copies…
    box.src_door.shutdown()
    state = again.keep_pass()                                          # …push the first keep out of the ring
    lost = [a for a in _events(box, "archive.keep.lost") if a["keep"] == first.id]
    assert lost and lost[0]["recording"] == "7-x" and state[first.id]["missing"] > 0


def test_a_keep_no_door_from_here_can_fill_is_counted_and_then_an_alarm():
    """The review's fourth pass. The recording's door on ANOTHER server's loopback was asked every pass and refused,
    `copied` stayed empty, and nothing said so: no metric, no alarm, while the recording's own ring reached the kept
    minutes. A door on another server's loopback is not asked; how much a keep is short and since when is in the
    heartbeat and on the recorder's `/metrics`; past `KEEP_UNCOPIED_AFTER` it is `archive.keep.uncopied`, once."""
    box, k = _site(source=False)
    t = box.wall()
    src = store("far")
    footage(src, "7", 1, t - 3600, t, step=10)
    far = door(box, src, "r-far", "srv-2")                             # announced as 127.0.0.1 by a recorder of srv-2
    try:
        kp = _keep(box, "7", t - 1800, t - 1200)
        state = k.keep_pass()
        assert state[kp.id]["copied"] == 0 and state[kp.id]["missing"] == 600   # not asked: not reachable from srv-1
        assert state[kp.id]["missing_since"] == t and f'rec_keep_missing_seconds{{keep="{kp.id}"}} 600' in k.metrics_text()
        assert _events(box, "archive.keep.uncopied") == []
        for _ in range(5):
            box.wall.advance(k.KEEP_EVERY); far.announce()
            k.keep_pass()
        [alarm] = _events(box, "archive.keep.uncopied")
        assert alarm["keep"] == kp.id and alarm["class"] == "alarm" and alarm["seconds"] == 600 and alarm["since"] == t
        box.wall.advance(k.KEEP_EVERY); far.announce()
        k.keep_pass()
        assert len(_events(box, "archive.keep.uncopied")) == 1          # said once, not every pass
        hb = k.heartbeat_extra()
        assert hb["keeps"][kp.id]["missing_since"] == t and hb["keep_missing"] == {kp.id: 600}
    finally:
        far.shutdown()


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
