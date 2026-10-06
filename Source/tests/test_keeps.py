"""What somebody said to keep: `rec/keeps/<id>` (the platform review, blocker 10; feedback BH).

Footage is in volumes, and a volume is a ring: ten minutes of one camera that are evidence go with the rest when
their turn comes. A keep is a row — a camera, an interval, a note, who set it — and the recorder holding an
INCIDENTS volume copies what it names into that volume, out of whichever recorder's door has it. The copy outlives
the recording's own ring; what was copied is an event with its sha256; and kept footage the incidents ring itself
took is an alarm. Retention skips the camera's event buckets a keep overlaps.
"""
import io
import json
import os
import tempfile
import urllib.error
import urllib.request

from w2cplatform.eventdatabase import EventIndex
from w2cplatform.spec import SpecController
from vms import keeps, volumes
from vms.archive import event_log
from vms.config import REC_SPEC
from vms.worker import fake_samples
from tests.vmsconftest import TEST_QUOTA, Box, door, footage, recorder, store

DAY = 86400.0


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
    return [e for e in EventIndex(box.resource_root, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="rec")["events"]
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
        got = json.loads(urllib.request.urlopen(f"{k.archive_url}/spans/7?from=0").read())
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
    from w2cplatform.resource import platform_resource
    box = Box()
    res = platform_resource(box.resource_root, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    t0 = box.wall() - 5 * DAY
    log = event_log(box.resource_root, 7, 3)
    log.append(t0 + 10, "alarm", zone="gate"); log.append(t0 + 3000, "motion")     # two buckets, fifty minutes apart
    event_log(box.resource_root, 8, 1).append(t0 + 10, "motion")
    keeps.write(box.vars, {"cam": "7", "from": t0, "to": t0 + 60}, ["7"], "anna", box.wall())
    box.vars.put("vms/retention/7", {"days": 0}); box.vars.put("vms/retention/8", {"days": 0})

    assert res.retain() == 2                                           # camera 8's, and camera 7's outside the keep
    left = buckets_under(box.resource_root, "vms", "7", 600)
    assert len(left) == 1 and left[0].start <= t0 + 10 < left[0].end and buckets_under(box.resource_root, "vms", "8", 600) == []


def test_a_keep_holds_every_subsystems_events_about_its_camera():
    """The review's fourth pass (B10 of the first review). Only the `vms` and `rec` trees were held: the detector's
    alarm at the gate, a scan's hits, a survey's, the scenario that fired — inside the keep, and deleted by their own
    days. Each unit's ROW says which camera it is about: a detector, a watch and a scan by `cam` (a deleted row too) —
    their specs' `about`, read by the platform since the boundary's step 6 (`holds:`). A unit whose camera cannot be
    told is held by any keep; another camera's units go; and a scenario is about nobody — its triggers name cameras,
    and nothing a spec declares reads them — so no keep holds it."""
    import json as _json
    from w2cplatform.events import ALARM, EventLog, subsystems_under
    from w2cplatform.resource import platform_resource
    box = Box()
    res = platform_resource(box.resource_root, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
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
        EventLog(box.resource_root, sub, unit, 1).append(t0 + 10, "seen", ALARM)            # the alarms' tree…
        EventLog(box.resource_root, sub, unit, 1).append(t0 + 10, "stats")                  # …and the observations'
        box.vars.put(f"{sub}/retention/{unit}", {"days": 0}); box.vars.put(f"{sub}/alarms_retention/{unit}", {"days": 0})
    keeps.write(box.vars, {"cam": "7", "from": t0, "to": t0 + 60}, ["7"], "anna", box.wall())

    res.retain()
    left = {(sub, u) for sub, us in subsystems_under(box.resource_root).items() for u in us if sub != "audit"   # the pass's own journal
            if any(f.endswith(".events.jsonl") for _, _, fs in __import__("os").walk(f"{box.resource_root}/{sub}/{u}") for f in fs)}
    held = {("det", "7-motion"), ("detjob", "7-lpr-1"), ("survey", "7-lpr"), ("rec", "7-cloud"), ("det", "orphan")}
    assert left == held | {(s + ".alarms", u) for s, u in held}                 # camera 8's, in both trees, are gone


def test_the_console_sets_a_keep_lists_it_and_lifts_it():
    """The spec's table (`tables.keeps`), served by the platform's console since the boundary's step 6 (it was the VMS's
    route, `rec_routes`): set by its camera and interval — the same interval again is the same row, written again —
    stamped with who and when, listed, lifted; refused in words what is no keep; and with no incidents volume declared
    a keep is ONLY a mark, counted on `/metrics` (the review's second pass, B10)."""
    from w2cplatform.console import SpecConsole
    from w2cplatform.metrics import text as spec_metrics
    from tests.conftest import Served
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    assert "rec/keeps/*" in REC_SPEC.acl_console()
    rec.create({"name": "7", "cam": "7"}); rec.create({"name": "7-cloud", "cam": "7"}); rec.create({"name": "9", "cam": "9"})
    t = box.wall()
    body = {"cam": "7", "from": t - 900, "to": t - 300, "note": "the gate, 14:10"}
    with Served(SpecConsole(rec, wall=box.wall)) as call:
        status, made = call("POST", "/keeps", body, headers={"X-User": "anna"})
        name = f"7-{int(t - 900)}-{int(t - 300)}"
        assert status == 201 and made["row"]["name"] == name
        assert (made["row"]["by"], float(made["row"]["at"])) == ("anna", t)
        assert "rec_keeps_unprotected 1" in spec_metrics(rec)
        volumes.write(box.vars, {"name": "evidence", "kind": "incidents", "server": "srv-1", "admits": False,
                                 "url": tempfile.mkdtemp(prefix="evidence-"), "quota_bytes": TEST_QUOTA})
        status, again = call("POST", "/keeps", body, headers={"X-User": "boris"})   # the same interval: the same row
        assert status == 201 and again["row"]["by"] == "boris" and "rec_keeps_unprotected 0" in spec_metrics(rec)
        status, view = call("GET", "/keeps")
        assert status == 200 and [k["name"] for k in view["keeps"]] == [name]

        for bad in ({"from": 1, "to": 2}, {"cam": "7", "from": "yesterday", "to": t}, {"cam": "../7", "from": 1, "to": 2},
                    {"cam": "7", "from": 1, "to": 2, "forever": True}, {"cam": "7", "from": 1, "to": 2, "note": "x" * 501},
                    {"cam": "7", "from": 0, "to": 2}):
            assert call("POST", "/keeps", bad)[0] == 400, bad

        assert call("DELETE", "/keeps/nope")[0] == 404
        assert call("DELETE", "/keeps/" + name)[0] == 200
        assert call("GET", "/keeps")[1]["keeps"] == []


def test_a_garbled_keep_is_shown_as_it_holds():
    """The review's eighth pass, part 4: a keep whose row does not parse holds its camera as far as its interval reads,
    and `GET /keeps` did not list it — a hold nobody could see or lift. The platform's list says every row, `garbled`
    where the store cannot read it; one whose bounds are words is listed as written, and the resources hold its camera
    as far as it reads (`holds.py`). (Who waits for a volume — a recorder's `volume_wait` — is its heartbeat's: the
    console's view of it went with the VMS's route, at the boundary's step 6.)"""
    from w2cplatform.console import SpecConsole
    from tests.conftest import Served
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    t = box.wall()
    box.vars.put("rec/keeps/7-bad", {"cam": "7", "from": "yesterday", "to": str(t), "note": "", "by": "anna"})
    _keep(box, "9", t - 900, t - 300)
    with Served(SpecConsole(rec, wall=box.wall)) as call:
        status, view = call("GET", "/keeps")
    by = {k["name"]: k for k in view["keeps"]}
    assert status == 200 and set(by) == {"7-bad", f"9-{int(t - 900)}-{int(t - 300)}"}
    assert by["7-bad"]["from"] == "yesterday" and by["7-bad"]["cam"] == "7"   # as written: whose, and what it says
    assert json.dumps(view)                                              # no `Infinity` in the answer


def test_a_keep_that_stays_garbled_for_an_hour_is_an_alarm_once_per_episode_and_again_once_a_day():
    """The review's eighth pass, part 4: a keep whose row does not parse holds its camera as far as its interval reads,
    and only the console's list said so. The incidents recorder carries since when it is garbled (`garbled_since`) and,
    past `KEEP_GARBLED_AFTER`, says `archive.keep.garbled` — once, again a day later while it lasts; a keep that parses
    again ends the episode, and its next garbling is a new one."""
    box, k = _site(source=False)
    t = box.wall()
    bad = {"cam": "7", "from": "yesterday", "to": str(t), "note": "", "by": "anna", "recordings": '["7"]'}
    box.vars.put("rec/keeps/7-bad", bad)
    state = k.keep_pass()
    assert state["7-bad"]["garbled"] is True and state["7-bad"]["garbled_since"] == t
    assert k.heartbeat_extra()["keeps"]["7-bad"]["garbled_since"] == t
    box.wall.advance(k.KEEP_GARBLED_AFTER - 60)
    k.keep_pass()
    assert _events(box, "archive.keep.garbled") == []                  # not yet an hour: a hand edit has its chance
    box.wall.advance(60)
    k.keep_pass()
    [alarm] = _events(box, "archive.keep.garbled")
    assert alarm["keep"] == "7-bad" and alarm["cam"] == "7" and alarm["class"] == "alarm" and alarm["since"] == t
    box.wall.advance(k.KEEP_EVERY)
    k.keep_pass()
    assert len(_events(box, "archive.keep.garbled")) == 1              # said once, not every pass
    box.wall.advance(k.SHALLOW_AGAIN)
    k.keep_pass()
    assert len(_events(box, "archive.keep.garbled")) == 2              # again a day later, while it lasts

    box.vars.put("rec/keeps/7-bad", {**bad, "from": str(t - 600)})    # mended: the episode is over
    assert "garbled" not in k.keep_pass()["7-bad"]
    box.vars.put("rec/keeps/7-bad", bad)                               # garbled again: a new hour from now
    again = box.wall()
    assert k.keep_pass()["7-bad"]["garbled_since"] == again
    box.wall.advance(k.KEEP_GARBLED_AFTER)
    k.keep_pass()
    assert [a["since"] for a in _events(box, "archive.keep.garbled")][-1] == again


def test_the_list_of_keeps_is_what_the_caller_may_see():
    """Feedback CG: a keep says which camera, which minutes and why. Lifting or checking one asked by its camera;
    the LIST did not, and showed every keep to whoever could see one camera. The platform's list of a table whose rows
    say whose they are (`rights.unit_of`) is what the caller may see — by a grant on the camera, or by its labels."""
    from tests.test_console_gate import Tokens, _call, _console
    box = Box()
    access = Tokens({"boris": [("view", "vms/1", ())], "vera": [("view", None, ("hall",))], "admin": [("admin", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    try:
        for cam, labels in (("1", []), ("3", ["hall"])):
            ctl.create_camera({"source": f"driverpack://file/{cam}.mp4", "labels": labels})
        box.vars.put("vms/cameras/3", {**box.vars.get("vms/cameras/2")[0], "id": "3"})
        for cam in ("1", "3", "ref:SN-A"):
            keeps.write(box.vars, {"cam": cam, "from": 100.0, "to": 200.0}, [], "anna", box.wall())
        cams = lambda who: sorted(k["cam"] for k in _call(base, "GET", "/rec/keeps", token=who)[1]["keeps"])   # noqa: E731
        assert cams("boris") == ["1"] and cams("vera") == ["3"] and cams("admin") == ["1", "3", "ref:SN-A"]
    finally:
        srv.shutdown()


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
    shutil.rmtree(os.path.join(box.resource_root, "rec"))                    # the event tree's retention took the copied events

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


# -- a keep's seal, checked at the door of the recorder that holds its copy (ADR-0015, ADR-0057 point 3) --------------

def _post(url, token=None):
    req = urllib.request.Request(url, data=b"", method="POST",
                                 headers={"Authorization": f"Bearer {token}"} if token else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _get(url, user="anna"):
    req = urllib.request.Request(url, headers={"X-User": user})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _sealed_site(spec=None):
    """`_site`, recording 7 of camera 7 copied for a keep into `evidence` — and a console over rec (`spec`: rec's, or one
    a test built) with the cluster's door key, `r-keep` serving its door and saying where (`url`, `volume`). Returns
    `(box, k, kp, base, keys, closers)`."""
    from vms.config import SPEC
    from vms.console import make_console
    from vms.controller import VmsController
    from tests.conftest import door_keys
    box, k = _site()
    t = box.wall()
    footage(box.src, "7", 1, t - 3600, t, step=10)
    box.vars.put("rec/recordings/7", {"name": "7", "cam": "7"})
    kp = _keep(box, "7", t - 1800, t - 1200)
    k.keep_pass()
    spec = spec or REC_SPEC
    with door_keys(box.vars) as keys:
        ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
        rec = SpecController(spec, box.vars.as_writer("console", spec.acl_console()), box.objects, wall=box.wall)
        m = make_console(ctl, box.resource_root, box.wall, mounts={"rec": rec})
    door_srv = k.serve_archive()
    k.heartbeat_once()
    srv = m.serve("127.0.0.1", 0)
    return box, k, kp, f"http://127.0.0.1:{srv.server_address[1]}", keys, (srv, door_srv, box.src_door)


def _verified_lines(k):
    from w2cplatform.events import buckets_under, read_bucket
    return [e for b in buckets_under(k.resource_root, "audit", f"door-{k.name}", 600)
            for e in read_bucket(os.path.join(k.resource_root, b.path)) if e.get("kind") == "archive.keep.verified"]


def test_a_keeps_seal_is_checked_at_the_door_of_the_recorder_that_holds_its_copy():
    """The page asks the console where the incidents volume is held, for recording 7 (`GET /rec/where/volumes/evidence
    ?unit=rec/7`): the door of `r-keep`, a token for its routes — `keeps` among them, rec's spec says so — and `POST
    <door>/keeps/<keep>/verify?recording=7` reads the copy now and compares it with its seal, the sha256 of
    `archive.keep.copied`. The console has no such route; the answer is a line `archive.keep.verified` with who asked."""
    box, k, kp, base, keys, closers = _sealed_site()
    try:
        st, p = _get(f"{base}/rec/where/volumes/evidence?unit=rec/7")
        assert st == 200 and p["worker"] == "r-keep" and p["door"]["url"] == k.archive_url, p
        assert "keeps" in p["door"]["routes"], p
        [copied] = _events(box, "archive.keep.copied")
        st, got = _post(f"{k.archive_url}/keeps/{kp.id}/verify?recording=7", p["door"]["token"])
        assert st == 200, got
        assert got["keep"] == kp.id and got["ok"] is True and got["integrity"] == "ok", got
        row = got["recordings"]["7"]
        assert row["result"] == "ok" and row["sealed"] == row["now"] == copied["sha256"] and row["samples"] > 0, row
        [line] = _verified_lines(k)
        assert line["keep"] == kp.id and line["ok"] is True and line["user"] == "anna" and line["integrity"] == "ok"
        for path in (f"/keeps/{kp.id}/verify", f"/rec/keeps/{kp.id}/verify"):
            assert _post(base + path)[0] in (404, 405), path              # not the console's: the door's
    finally:
        for s in closers:
            s.shutdown()


def test_a_copy_that_no_longer_hashes_to_its_seal_is_broken():
    """Frames another epoch wrote into the kept minutes of the incidents volume: the copy reads otherwise now, and the
    answer says `damaged` and `broken: …` — and so does a recorder that has only the durable event to go by."""
    box, k, kp, base, keys, closers = _sealed_site()
    try:
        t = kp.until
        token = keys.signer.issue("anna", "rec/7", "r-keep", REC_SPEC.door_routes, box.wall())[0]
        footage(k.store, "7", 5, t - 300, t - 200)                     # the volume no longer holds what was sealed
        st, got = _post(f"{k.archive_url}/keeps/{kp.id}/verify?recording=7", token)
        assert st == 200 and got["ok"] is False, got
        assert got["integrity"] == "broken: 7: the copy does not hash to its seal", got
        row = got["recordings"]["7"]
        assert row["result"] == "damaged" and row["sealed"] and row["sealed"] != row["now"], row
        k.keep_state = {}                                              # the seal from the event, not from memory
        assert k.verify_keep(kp.id, "7")[1]["recordings"]["7"]["sealed"] == row["sealed"]
    finally:
        for s in closers:
            s.shutdown()


def test_the_door_lets_in_a_keeps_check_only_with_a_token_for_that_recording_and_the_keeps_route():
    """A token that does not carry `keeps` (a spec built here without it in `door.routes`: the console hands out what the
    spec says), one for another recording, none — refused by the keeper, 401 and the reason; GET is not the check (405);
    and a door whose spec does not name `keeps` has no such route at all."""
    from w2cplatform.spec import SubsystemSpec
    from vms.footage import keeps_route
    with open(os.path.join(os.path.dirname(keeps.__file__), "rec.subsystem.yaml")) as f:
        text = f.read()
    assert text.count("door: {routes: [timeline, segment, keeps]}") == 1
    path = os.path.join(tempfile.mkdtemp(prefix="spec-"), "rec.subsystem.yaml")
    with open(path, "w") as f:
        f.write(text.replace("door: {routes: [timeline, segment, keeps]}", "door: {routes: [timeline, segment]}"))
    without = SubsystemSpec.load(path)
    assert without.door_routes == ("timeline", "segment")
    box, k, kp, base, keys, closers = _sealed_site(without)
    try:
        st, p = _get(f"{base}/rec/where/volumes/evidence?unit=rec/7")
        assert st == 200 and p["door"]["routes"] == ["timeline", "segment"], p
        url = f"{k.archive_url}/keeps/{kp.id}/verify"
        st, got = _post(url + "?recording=7", p["door"]["token"])
        assert st == 401 and got["reason"] == "route", got                # its token does not open `keeps`
        token = keys.signer.issue("anna", "rec/7", "r-keep", REC_SPEC.door_routes, box.wall())[0]
        st, got = _post(url + "?recording=8", token)
        assert st == 401 and got["reason"] == "unit", got                 # one recording's token
        st, got = _post(url, token)
        assert st == 401 and got["reason"] == "unit", got                 # …and the request names it
        st, got = _post(url + "?recording=7")
        assert st == 401 and got["reason"] == "token", got
        try:
            urllib.request.urlopen(urllib.request.Request(url + "?recording=7", headers={"Authorization": f"Bearer {token}"}))
            raise AssertionError("GET is not a keep's check")
        except urllib.error.HTTPError as e:
            assert e.code == 405 and json.loads(e.read())["error"] == "method"
        assert _post(url + "?recording=7", token)[0] == 200
        route = keeps_route(None, lambda *a: (200, {}), without.door_routes)
        assert route(None, "POST", f"/keeps/{kp.id}/verify", {"recording": "7"}) is None   # not a route of that door
    finally:
        for s in closers:
            s.shutdown()


def test_a_keep_cannot_be_verified_where_no_incident_archive_is_served_nor_when_its_interval_is_garbled():
    """503 `cannot verify` from a recorder holding no volume, and from one holding an ordinary volume — that one says
    whom to ask; 503 with the store's fault when the keeps cannot be read; 409 for a keep whose interval does not parse
    (nothing of it was copied, nothing sealed); 404 for no such keep and for a recording the keep does not hold."""
    box, k = _site()
    t = box.wall()
    footage(box.src, "7", 1, t - 3600, t, step=10)
    kp = _keep(box, "7", t - 1800, t - 1200)
    k.keep_pass()
    try:
        idle = recorder(box, "r-idle", "srv-9", acl=False)
        st, got = idle.verify_keep(kp.id, "7")
        assert st == 503 and got == {"error": "cannot verify", "detail": "this recorder serves no incident archive",
                                     "integrity": "unknown: this recorder serves no incident archive"}, got
        volumes.write(box.vars, {"name": "disks-2", "kind": "local", "server": "srv-2",
                                 "url": tempfile.mkdtemp(prefix="disks-2-"), "quota_bytes": TEST_QUOTA})
        plain = recorder(box, "r-2", "srv-2", acl=False)
        plain.lease_pass()
        assert plain.volume == "disks-2" and not plain.incidents
        st, got = plain.verify_keep(kp.id, "7")
        assert st == 503 and got["error"] == "cannot verify" and "ask the holder of the incidents volume" in got["detail"]
        assert got["integrity"] == "unknown: no incident archive is served here"

        box.vars.put("rec/keeps/7-bad", {"cam": "7", "from": "yesterday", "to": str(t), "by": "anna", "recordings": '["7"]'})
        st, got = k.verify_keep("7-bad", "7")
        assert st == 409 and got["error"] == "cannot verify a keep whose interval is garbled" and got["detail"], got
        assert k.verify_keep("7-none", "7")[0] == 404
        st, got = k.verify_keep(kp.id, "9")
        assert st == 404 and got["error"] == "no such recording in the keep", got

        class Away:
            def __init__(self, inner): self.inner = inner
            def get(self, key): return self.inner.get(key)
            def list(self, prefix):
                if prefix == "rec/keeps/":
                    raise PermissionError(13, "the store does not answer")
                return self.inner.list(prefix)
        was, k.vars = k.vars, Away(box.vars)
        try:
            st, got = k.verify_keep(kp.id, "7")
        finally:
            k.vars = was
        assert st == 503 and got == {"error": "cannot verify", "detail": "the store did not answer (PermissionError)"}, got
    finally:
        box.src_door.shutdown()


def test_a_recording_never_copied_is_pending_and_the_keep_unknown():
    """Nothing contradicts the seal and something is not known yet: a recording of the keep's camera with nothing copied
    is `pending`, not sealed yet, and the keep's integrity `unknown`, `ok` false — never `ok` for what was not compared."""
    box, k = _site(source=False)
    t = box.wall()
    kp = _keep(box, "7", t - 1800, t - 1200)
    st, got = k.verify_keep(kp.id)
    assert st == 200 and got["ok"] is False and got["integrity"] == "unknown: 7: not sealed yet", got
    assert got["recordings"]["7"] == {"sealed": "", "now": "", "samples": 0, "result": "pending"}
