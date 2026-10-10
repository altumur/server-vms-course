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
from vms.archive import STITCH, event_log
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
    assert k.capacity == 0 and "keeps" not in k.heartbeat_extra()          # nothing to say of any keep: absent
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
    assert state[kp.id]["seconds"] == 600 and state[kp.id]["missing"] == 0
    assert [(s.stream, s.start, s.end) for s in k.store.spans("7")] == [("7/e0", t - 1800, t - 1200)]
    [ev] = _events(box, "archive.keep.copied")
    assert ev["keep"] == kp.id and ev["recording"] == "7" and ev["sha256"] == state[kp.id]["sha256"]["7"]
    assert k.heartbeat_extra()["keeps"][kp.id]["seconds"] == 600

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
    assert entry["seconds"] == 1200 and entry["missing"] == 600


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
    assert state[kp.id]["seconds"] == 660 and state[kp.id]["missing"] == 0
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
    assert state[kp.id]["seconds"] == 0 and state[kp.id]["missing"] == 600, state
    for _ in range(5):                                                 # past KEEP_UNCOPIED_AFTER: said, not swallowed
        box.wall.advance(k.KEEP_EVERY); box.src_door.announce(); down.announce()
        k.keep_pass()
    [alarm] = _events(box, "archive.keep.uncopied")
    assert alarm["keep"] == kp.id and alarm["seconds"] == 600
    back = door(box, far, "r-far", "srv-1", status=held)               # its door answers again: copied, and whole
    try:
        box.src_door.announce()
        state = k.keep_pass()
        assert state[kp.id]["seconds"] == 600 and state[kp.id]["missing"] == 0
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
        assert state[kp.id]["seconds"] == 600 and state[kp.id]["missing"] == 0
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
        assert state[kept.id]["seconds"] == 0 and state[kept.id]["missing"] == 600, state
        assert state[dark.id]["seconds"] == 100 and state[dark.id]["missing"] == 0, state   # the hole: nobody has it
        for _ in range(5):                                             # past KEEP_UNCOPIED_AFTER: said, not swallowed
            box.wall.advance(k.KEEP_EVERY); now.announce(); down.announce()
            k.keep_pass()
        [alarm] = _events(box, "archive.keep.uncopied")
        assert alarm["keep"] == kept.id and alarm["seconds"] == 600
        back = door(box, v1, "r-v1", "srv-1")                          # v1's door answers again
        try:
            now.announce()
            state = k.keep_pass()
            assert state[kept.id]["seconds"] == 600 and state[kept.id]["missing"] == 0
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


def _overfilled():
    """Three keeps of five minutes, a quarter of a megabyte every ten seconds, copied into an incidents ring of 16 MB:
    the third pushes the oldest kept footage out, and the recording's own door is gone, so nothing is copied back."""
    box, k = _site(quota=16 << 20)
    t = box.wall()
    for smp in fake_samples(t - 1200, t, step=10, size=256 << 10):
        box.src.put("7", 1, smp)
    box.src.finish("7", 1); box.src.seal()
    first = _keep(box, "7", t - 1200, t - 900)
    k.keep_pass()
    second, third = _keep(box, "7", t - 800, t - 500), _keep(box, "7", t - 400, t - 100)
    k.keep_pass()
    box.src_door.shutdown()
    k.keep_pass()
    return box, k, (first, second, third)


def test_kept_footage_the_incidents_ring_wrote_over_is_in_the_heartbeat_with_its_seconds_every_pass():
    """ADR-0064, its addition: the course's recorder says `incidents_lost {keep: seconds}` as the product does. The alarm
    `archive.keep.lost` is said once; what the volume took of a keep in force and holds no more is in the heartbeat for
    as long as it lasts — the most it ever held less what it holds now, in whole seconds — and gone with the keep."""
    box, k, (first, second, third) = _overfilled()
    assert k.store.status()["firstBlockId"] > 0
    held = {kp.id: k.keep_held[(kp.id, "7")] for kp in (first, second, third)}
    assert held[first.id] < 300                                        # the oldest went first
    hb = k.heartbeat_extra()
    want = {kp.id: round(300 - held[kp.id]) for kp in (first, second, third) if 300 - held[kp.id] >= k.LOSS_SLACK}
    assert first.id in want and hb["incidents_lost"] == want, (hb.get("incidents_lost"), held)
    assert all(type(s) is int for s in hb["incidents_lost"].values())
    k.keep_pass()                                                      # the alarm is not said again; the field still is
    assert k.heartbeat_extra()["incidents_lost"] == want
    keeps.delete(box.vars, first.id)                                   # lifted: not a keep in force, not lost
    k.keep_pass()
    assert first.id not in k.heartbeat_extra().get("incidents_lost", {})


def test_a_closed_incidents_ring_whose_oldest_footage_is_kept_says_that_keep_is_at_risk():
    """ADR-0064, its addition: `incidents_at_risk [keep]` — the ring has closed, and the oldest footage it holds of a
    recording lies in a keep still in force: the next block it writes over is kept. Footage of a keep that was lifted
    going first is what a ring is for: once the keep whose minutes are oldest is lifted, nothing is at risk."""
    box, k, kps = _overfilled()
    oldest = k.store.coverage("7")[0][0]
    under = [kp.id for kp in kps if kp.since - STITCH <= oldest <= kp.until]
    assert under and k.heartbeat_extra()["incidents_at_risk"] == sorted(under)
    for kid in under:
        keeps.delete(box.vars, kid)
    k.keep_pass()
    oldest = k.store.coverage("7")[0][0]
    assert not any(kp.since - STITCH <= oldest <= kp.until for kp in kps if kp.id not in under)
    assert "incidents_at_risk" not in k.heartbeat_extra()


def test_nothing_lost_and_nothing_at_risk_is_not_said():
    """A keep copied whole into a ring that has room: `keeps` says it, and neither `incidents_lost` nor
    `incidents_at_risk` is in the heartbeat — absent when empty, as the product leaves them out. A recorder that holds
    no incidents volume says neither, whatever."""
    box, k = _site()
    t = box.wall()
    footage(box.src, "7", 1, t - 3600, t, step=10)
    kp = _keep(box, "7", t - 1800, t - 1200)
    k.keep_pass()
    assert k.store.status()["firstBlockId"] == 0
    hb = k.heartbeat_extra()
    assert hb["keeps"][kp.id]["seconds"] == 600
    assert "incidents_lost" not in hb and "incidents_at_risk" not in hb
    plain = recorder(box, "r-disks-2", "srv-1", acl=False)
    assert "incidents_lost" not in plain.heartbeat_extra() and "incidents_at_risk" not in plain.heartbeat_extra()


def test_servers_shows_the_incidents_recorders_keeps_lost_and_at_risk_as_they_are():
    """rec's spec declares `keeps`, `incidents_lost` and `incidents_at_risk` under `servers.status` with `of: keeps`
    (ADR-0064): the incidents recorder's heartbeat goes onto its row of `GET /servers` as it is — a map of seconds by
    keep, a list of keeps — and the page matches the keys and the elements with the rows of `keeps`."""
    import urllib.request as ur
    from w2cplatform.console import SpecConsole
    box, k, _ = _overfilled()
    k.heartbeat_once()
    hb = k.heartbeat_extra()
    assert hb["incidents_lost"] and hb["incidents_at_risk"]
    declared = {e["field"]: e for e in REC_SPEC.servers_status}
    assert all(declared[f].get("of") == "keeps" for f in ("keeps", "incidents_lost", "incidents_at_risk")), declared
    # where the page reads it: `GET /rec/servers` of the VMS console that mounts rec — and rec's own console at its root
    from vms.console import make_console
    from vms.controller import VmsController
    rec = SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall)
    vms = make_console(VmsController(box.vars, box.objects, wall=box.wall), box.resource_root, box.wall,
                       mounts={"rec": rec}).serve("127.0.0.1", 0)
    own = SpecConsole(rec, wall=box.wall).serve("127.0.0.1", 0)
    try:
        for url in (f"http://127.0.0.1:{vms.server_address[1]}/rec/servers", f"http://127.0.0.1:{own.server_address[1]}/servers"):
            out = json.loads(ur.urlopen(ur.Request(url, headers={"X-User": "ann"}), timeout=10).read())
            [row] = [w["status"] for s in out["servers"].values() for w in s["workers"] if w["worker"] == "r-keep"]
            assert row["incidents_lost"] == hb["incidents_lost"] and row["incidents_at_risk"] == hb["incidents_at_risk"], url
            assert row["keeps"] == json.loads(json.dumps(hb["keeps"])), url
    finally:
        vms.shutdown(); own.shutdown()


def _source(box, quota: int = 64 << 20):
    """The recording's own recorder: `r-src` holding the local volume `disks` of srv-1, beside the incidents recorder."""
    volumes.write(box.vars, {"name": "disks", "kind": "local", "server": "srv-1", "url": tempfile.mkdtemp(prefix="disks-"),
                             "quota_bytes": quota})
    src = recorder(box, "r-src", "srv-1", acl=False)
    src.lease_pass()
    assert src.volume == "disks" and not src.incidents and src.store is not None
    return src


def test_the_recordings_recorder_says_its_side_of_a_keep_here_at_risk_pushing_pushed():
    """The product's keeper, its source half: the recorder of the recording's volume says, for each keep over footage
    it holds, `{recording, seconds, leaves_in_s, state}` — `here` far from going, `at risk` close to going with no
    incidents archive to copy it (and why), `pushing` while the incidents archive is served and does not show it all
    yet, `pushed` once it does. What it shows is asked at the incidents recorder's door, not guessed."""
    box, k = _site(source=False)
    src = _source(box)
    t = box.wall()
    footage(src.store, "7", 1, t - 30000, t, step=10)
    far = _keep(box, "7", t - 1800, t - 1200)                          # 28200 s from the ring's edge: past KEEP_MARGIN
    near = _keep(box, "7", t - 29000, t - 28800)                       # 1000 s from it: due
    side = src.keep_side_pass()
    assert side[far.id] == {"recording": "7", "seconds": 600, "leaves_in_s": 28200, "state": "here"}, side
    assert side[near.id] == {"recording": "7", "seconds": 200, "leaves_in_s": 1000, "state": "at risk",
                             "why": "no incident archive is served"}, side
    assert "keeps" not in k.heartbeat_extra() or far.id not in k.heartbeat_extra()["keeps"]

    copier = k.serve_archive()                                         # the incidents archive is served now…
    k.heartbeat_once()
    door_src = src.serve_archive()
    src.heartbeat_once()
    try:
        side = src.keep_side_pass()
        assert side[far.id]["state"] == side[near.id]["state"] == "pushing", side   # …and shows none of it yet
        k.keep_pass()                                                  # its recorder copies both from r-src's door
        side = src.keep_side_pass()
        assert side[far.id]["state"] == side[near.id]["state"] == "pushed", side
        hb = src.heartbeat_extra()
        assert hb["keeps"] == side and "incidents_lost" not in hb and "keep_missing" not in hb
        assert k.heartbeat_extra()["keeps"][far.id]["state"] == "kept"  # the holder's word beside it
    finally:
        copier.shutdown(); door_src.shutdown()


def test_kept_footage_the_recordings_ring_took_before_any_copy_is_lost_and_an_alarm():
    """`lost` on the recording's side: what of a keep this volume held and the incidents archive never showed is gone
    from the volume — its ring wrote over it first. Said in the heartbeat with `lost_seconds` and why while the keep
    stands, and an alarm `archive.keep.lost` once (the course's incidents recorder could not say it: no door has those
    minutes any more, so nothing is short)."""
    box, k = _site(source=False)
    src = _source(box, quota=16 << 20)
    t = box.wall()
    for smp in fake_samples(t - 1200, t - 900, step=10, size=256 << 10):
        src.store.put("7", 1, smp)
    src.store.finish("7", 1); src.store.seal()
    kp = _keep(box, "7", t - 1200, t - 900)
    side = src.keep_side_pass()
    assert side[kp.id]["state"] == "at risk"                           # at the ring's edge, and nobody to copy it
    held = side[kp.id]["seconds"]
    for smp in fake_samples(t - 900, t, step=10, size=256 << 10):     # 22 MB more into a ring of 16
        src.store.put("7", 1, smp)
    src.store.finish("7", 1); src.store.seal()
    assert not [s for s in src.store.coverage("7") if s[0] < t - 900]
    side = src.keep_side_pass()
    assert side[kp.id] == {"recording": "7", "state": "lost", "lost_seconds": held,
                           "why": "the ring wrote over it before the incident archive had a copy"}, side
    [alarm] = [e for e in _events(box, "archive.keep.lost") if e.get("volume") == "disks"]
    assert alarm["class"] == "alarm" and alarm["keep"] == kp.id and alarm["recording"] == "7" and alarm["seconds"] == held
    src.keep_side_pass()
    assert len([e for e in _events(box, "archive.keep.lost") if e.get("volume") == "disks"]) == 1   # once, not every pass
    keeps.delete(box.vars, kp.id)                                      # lifted: nothing to say of it
    assert kp.id not in src.keep_side_pass()


def test_a_garbled_keep_over_a_recording_this_volume_holds_is_said_garbled_on_its_side():
    box, k = _site(source=False)
    src = _source(box)
    t = box.wall()
    footage(src.store, "7", 1, t - 600, t, step=10)
    box.vars.put("rec/keeps/7-bad", {"cam": "7", "from": "yesterday", "to": str(t), "recordings": '["7"]'})
    box.vars.put("rec/keeps/9-bad", {"cam": "9", "from": "yesterday", "to": str(t), "recordings": '["9"]'})
    side = src.keep_side_pass()
    assert side == {"7-bad": {"state": "garbled", "why": "its row does not parse", "garbled_since": t}}, side   # not 9's
    box.wall.advance(60)
    assert src.keep_side_pass()["7-bad"]["garbled_since"] == t                # since when this recorder sees it so
    assert src.heartbeat_extra()["keeps"]["7-bad"]["state"] == "garbled"
    box.vars.put("rec/keeps/7-bad", {"cam": "7", "from": str(t - 600), "to": str(t), "recordings": '["7"]'})
    assert src.keep_side_pass()["7-bad"]["state"] != "garbled"                # mended: what it holds, said as such


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
    assert "state" not in state["7-bad"] and state["7-bad"]["garbled_since"] == t
    assert state["7-bad"]["why"] == "its row does not parse"
    assert "7-bad" not in k.heartbeat_extra().get("keeps", {})          # the holder has no word for it: the product's
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
    assert "garbled_since" not in k.keep_pass()["7-bad"]
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
        assert state[kp.id]["seconds"] == 0 and state[kp.id]["missing"] == 600   # not asked: not reachable from srv-1
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
        assert k.keep_state[kp.id]["missing_since"] == t and hb["keep_missing"] == {kp.id: 600}
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
    # …and in the heartbeat, from what the copy said it held before the restart (`incidents_lost`, ADR-0064)
    assert again.heartbeat_extra()["incidents_lost"][first.id] == round(300 - again.keep_held[(first.id, "7")])


# -- what an incidents volume took, written down by volume: `rec/taken/<volume>` (ADR-0057) ----------------------------

def _taken(box, volume="evidence"):
    return keeps.parse_taken(box.objects.get(keeps.taken_key(volume)))


def _on_another_box(box, name="r-keep"):
    """A recorder of this site whose resource's tree is another box's: the events the first one wrote are not in it."""
    here = box.resource_root
    box.resource_root = tempfile.mkdtemp(prefix="another-box-")
    try:
        return recorder(box, name, "srv-1", acl=False)
    finally:
        box.resource_root = here


def _events_in(box, root, kind):
    return [e for e in EventIndex(root, "srv-1", wall=box.wall).query(0, box.wall() + 1, subsystem="rec")["events"]
            if e["kind"] == kind]


def test_what_an_incidents_volume_took_outlives_its_recorder_and_its_box():
    """ADR-0057, the product's `rec/taken/<volume>` (TestWhatAnIncidentArchiveTookOutlivesItsProcess). The events that
    said what was copied are in the tree of the server that copied it: a recorder of the volume on another box started
    from what the ring still held, and kept footage the ring wrote over before it came was never `archive.keep.lost`.
    The record of what the volume took goes with the volume: the next holder, wherever it is, says the loss."""
    box, k = _site(quota=16 << 20)
    t = box.wall()
    for smp in fake_samples(t - 1200, t, step=10, size=256 << 10):
        box.src.put("7", 1, smp)
    box.src.finish("7", 1); box.src.seal()
    first = _keep(box, "7", t - 1200, t - 900)
    k.keep_pass()
    fmt = k.store.formatted_at()
    assert fmt and _taken(box) == ({"7": [(t - 1200, t - 900)]}, False, fmt)
    _keep(box, "7", t - 800, t - 500); _keep(box, "7", t - 400, t - 100)
    k.keep_pass()                                                      # its own copies push the first keep out of the ring…
    k.after_stop()                                                     # …and it goes before its next pass sees it
    box.src_door.shutdown()
    assert _taken(box)[0]["7"][0] == (t - 1200, t - 900)               # what it took, as it took it

    again = _on_another_box(box)                                       # the volume's next holder, on another box
    again.lease_pass()
    assert again.volume == "evidence" and again.resource_root != box.resource_root
    left = sum(min(b, t - 900) - max(a, t - 1200) for a, b in again.store.coverage("7") if b > t - 1200 and a < t - 900)
    assert 300 - left >= again.LOSS_SLACK                              # gone before it came: the ring holds no trace of it
    state = again.keep_pass()
    lost = [a for a in _events_in(box, again.resource_root, "archive.keep.lost") if a["keep"] == first.id]
    assert lost and lost[0]["recording"] == "7" and lost[0]["seconds"] == round(300 - left, 1)
    assert state[first.id]["missing"] > 0 and again.heartbeat_extra()["incidents_lost"][first.id] == round(300 - left)
    took, wrapped, formatted = _taken(box)
    assert wrapped and formatted == fmt                                # the ring came round, for whoever holds it next
    assert took["7"][0] == (t - 1200, t - 900)                         # a keep in force: what it took stays, lost or not
    again.keep_pass()
    assert len([a for a in _events_in(box, again.resource_root, "archive.keep.lost") if a["keep"] == first.id]) == 1


def test_the_record_of_what_was_taken_is_in_the_products_bytes():
    """One record, two writers on one site's history: the course writes what the product's `json.Marshal` of
    `takenRecord` writes — its field order, no spaces, a whole second without `.0` — and reads it back."""
    box, k = _site()
    t = box.wall()
    footage(box.src, "7", 1, t - 3600, t, step=10)
    _keep(box, "7", t - 1800, t - 1200)
    k.keep_pass()
    fmt = k.store.formatted_at()
    raw = box.objects.get(keeps.taken_key("evidence"))
    assert raw == f'{{"took":{{"7":[[{int(t - 1800)},{int(t - 1200)}]]}},"wrapped":false,"formatted":{fmt}}}'.encode()
    assert keeps.taken_bytes({"7": [(1000.5, 1095.0)]}, True, 7) == b'{"took":{"7":[[1000.5,1095]]},"wrapped":true,"formatted":7}'
    assert keeps.parse_taken(b'{"took":null,"wrapped":false,"formatted":7}') == ({}, False, 7)


def test_what_was_taken_is_written_down_as_large_as_what_is_kept():
    """Pruned on write by the keeps as they stand (the product's `pruneTook`, 0ae8365 — its record grew without bound):
    a span outside every keep goes, a recording no keep names goes, and a keep lifted takes its spans with it."""
    box, k = _site()
    t = box.wall()
    footage(box.src, "7", 1, t - 3600, t, step=10)
    first, second = _keep(box, "7", t - 1800, t - 1200), _keep(box, "7", t - 600, t - 300)
    k.keep_pass()
    fmt = k.store.formatted_at()
    assert _taken(box) == ({"7": [(t - 1800, t - 1200), (t - 600, t - 300)]}, False, fmt)
    k.taken["7"] = k.taken["7"] + [(t - 3000, t - 2900)]               # a span no keep covers…
    k.taken["8"] = [(0.0, 50000.0)]                                    # …and a recording no keep names
    k.keep_pass()
    assert _taken(box) == ({"7": [(t - 1800, t - 1200), (t - 600, t - 300)]}, False, fmt)
    keeps.delete(box.vars, first.id)
    k.keep_pass()
    assert _taken(box) == ({"7": [(t - 600, t - 300)]}, False, fmt)
    keeps.delete(box.vars, second.id)
    k.keep_pass()
    assert _taken(box) == ({}, False, fmt)


def test_a_keep_whose_interval_does_not_read_keeps_what_was_taken_whole():
    """Which footage a garbled keep means is not known (`keeps.as_far_as_read`): its recordings' spans are kept whole,
    as the product's `pruneTook` keeps a keep that is not `Bounded`."""
    box, k = _site()
    t = box.wall()
    footage(box.src, "7", 1, t - 3600, t, step=10)
    kp = _keep(box, "7", t - 1800, t - 1200)
    k.keep_pass()
    k.taken["7"] = k.taken["7"] + [(t - 3000, t - 2900)]
    items, _ = box.vars.get(keeps.key(kp.id))
    box.vars.put(keeps.key(kp.id), {**items, "from": "yesterday"})
    k.keep_pass()
    assert _taken(box)[0] == {"7": [(t - 3000, t - 2900), (t - 1800, t - 1200)]}


def test_keeps_that_cannot_be_read_prune_nothing_of_what_was_taken():
    """A store that does not answer is not "nothing is kept": what was taken is written down as it is."""
    box, k = _site()
    t = box.wall()
    footage(box.src, "7", 1, t - 3600, t, step=10)
    _keep(box, "7", t - 1800, t - 1200)
    k.keep_pass()
    k.taken["8"] = [(0.0, 50000.0)]

    class Away:
        def __init__(self, inner): self.inner = inner
        def get(self, key): return self.inner.get(key)
        def list(self, prefix):
            if prefix == "rec/keeps/":
                raise PermissionError(13, "the store does not answer")
            return self.inner.list(prefix)

    here, k.vars = k.vars, Away(box.vars)
    try:
        k._taken_write(lambda kp: sorted(kp.recordings))
    finally:
        k.vars = here
    assert _taken(box)[0] == {"7": [(t - 1800, t - 1200)], "8": [(0.0, 50000.0)]}


def test_a_record_of_another_format_of_the_volume_is_not_taken():
    """`took` and `wrapped` are of one format of the volume (`formatted`): a record of another, or of none said (an
    older build's, ADR-0003), is not this volume's — a disk replaced and declared again under the old name starts with
    nothing taken and a ring that has not come round."""
    for stale in (keeps.taken_bytes({"7": [(100.0, 400.0)]}, True, 1),
                  b'{"took":{"7":[[100,400]]},"wrapped":true}'):
        box = Box()
        box.src = store("disks")
        box.src_door = door(box, box.src, "r-disks", "srv-1")
        box.objects.put(keeps.taken_key("evidence"), stale)
        volumes.write(box.vars, {"name": "evidence", "kind": "incidents", "server": "srv-1",
                                 "url": tempfile.mkdtemp(prefix="evidence-"), "quota_bytes": TEST_QUOTA})
        k = recorder(box, "r-keep", "srv-1", acl=False)
        k.lease_pass()
        kp = _keep(box, "7", 50, 500, recordings=["7"])
        k.keep_pass()
        assert _events(box, "archive.keep.lost") == [] and kp.id not in k.heartbeat_extra().get("incidents_lost", {})
        assert "incidents_at_risk" not in k.heartbeat_extra()
        assert _taken(box) == ({}, False, k.store.formatted_at())     # written anew, of this format
        box.src_door.shutdown()


def test_a_volume_formatted_again_under_the_running_recorder_forgets_what_the_old_one_took():
    """The same name, another format, while the process holds it (the product's `loadTaken`, 0ae8365): `took`,
    `wrapped` and what each keep held of the old volume go."""
    box, k = _site()
    t = box.wall()
    footage(box.src, "7", 1, t - 3600, t, step=10)
    kp = _keep(box, "7", t - 1800, t - 1200)
    k.keep_pass()
    k.taken_wrapped = True
    assert k._taken_read() == {"7": [(t - 1800, t - 1200)]}            # the same format: read once, kept
    fmt = k.store.formatted_at()
    k.store.formatted_at = lambda: fmt + 60
    assert k._taken_read() == {} and not k.taken_wrapped and (kp.id, "7") not in k.keep_held
    assert k._taken_format == fmt + 60
    box.src_door.shutdown()


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
    """`_site`, recording 7 of camera 7 copied for a keep into `evidence` and SEALED by `r-keep`, the recorder of the
    incidents volume, in the same pass (`RecWorker._seal`) — and a console over rec (`spec`: rec's, or one a test built)
    with the cluster's door key, `r-keep` serving its door and saying where (`url`, `volume`). Returns
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
    assert keeps.read_seal(box.objects, kp.id) is not None
    srv = m.serve("127.0.0.1", 0)
    return box, k, kp, f"http://127.0.0.1:{srv.server_address[1]}", keys, (srv, door_srv, box.src_door)


def _audit(root, role, kind):
    from w2cplatform.events import buckets_under, read_bucket
    return [e for b in buckets_under(root, "audit", role, 600)
            for e in read_bucket(os.path.join(root, b.path)) if e.get("kind") == kind]


def _verified_lines(k):
    return _audit(k.resource_root, f"door-{k.name}", "archive.keep.verified")


def test_a_keeps_seal_is_checked_at_the_door_of_the_recorder_that_holds_its_copy():
    """The page asks the console where the incidents volume is held, for recording 7 (`GET /rec/where/volumes/evidence
    ?unit=rec/7`): the door of `r-keep`, a token for its routes — `keeps` among them, rec's spec says so — and `POST
    <door>/keeps/<keep>/verify?recording=7` reads the copy now and compares it with its seal — set once by `r-keep`,
    when the copy was whole, in rec's own record `rec/sealed/<keep>` and not in the keep's row (ADR-0057, дополнение
    п. 3: пишет рекордер тома incidents), an event `archive.keep.sealed`. The console has no such route; the answer is a line
    `archive.keep.verified` with who asked."""
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
        seal = keeps.read_seal(box.objects, kp.id)
        assert seal == keeps.Seal((("7", copied["sha256"]),), kp.since, kp.until, box.wall(), kp.made_at), seal   # its own record
        assert kp.made_at == box.wall() > 0                                          # …taken for the keep made then
        assert not {"sealed", "sealed_at"} & set(box.vars.get(keeps.key(kp.id))[0])                  # not the keep's row
        [line] = _events(box, "archive.keep.sealed")
        assert (line["keep"], line["recording"], line["sha256"], line["cam"]) == (kp.id, "7", copied["sha256"], "7")
        assert (line["from"], line["to"]) == (kp.since, kp.until)
        [line] = _verified_lines(k)
        assert line["keep"] == kp.id and line["ok"] is True and line["user"] == "anna" and line["integrity"] == "ok"
        # what the line is about (ADR-0069; the review's fifteenth pass, minor 6): the keep's row, and the camera it holds
        assert (line["sub"], line["table"], line["target"], line["of"]) == ("rec", "keeps", kp.id, f"vms/{kp.cam}"), line
        for path in (f"/keeps/{kp.id}/verify", f"/rec/keeps/{kp.id}/verify"):
            assert _post(base + path)[0] in (404, 405), path              # not the console's: the door's
    finally:
        for s in closers:
            s.shutdown()


def test_a_copy_that_no_longer_hashes_to_its_seal_is_broken():
    """Frames another epoch wrote into the kept minutes of the incidents volume: the copy reads otherwise now, and the
    answer says `damaged` and `broken: …`. The seal does not follow it: a recorder that says another digest of a whole
    copy, or one started again with nothing in memory, changes nothing in the seal — it is set once (ADR-0057,
    дополнение п. 3)."""
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
        k.keep_state = {}                                              # a recorder with nothing in memory reads the copy
        state = k.keep_pass()                                          # again — the damaged one — and seals nothing
        assert state[kp.id]["sha256"]["7"] == row["now"] and state[kp.id]["whole"] == ["7"]
        assert k.verify_keep(kp.id, "7")[1]["recordings"]["7"]["sealed"] == row["sealed"]
        assert len(_events(box, "archive.keep.sealed")) == 1
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
    whom to ask; 503 with the store's fault in the product's words, no path (`StoreFault`); 409 for a keep any part of
    whose interval does not parse — the start alone here (nothing of it was copied, nothing sealed; ADR-0057, addendum
    p. 3); 404 for no such keep and for a recording the keep does not hold."""
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
        assert st == 503 and got == {"error": "cannot verify", "detail": "[Errno 13] the store does not answer"}, got
        Away.list = lambda self, prefix: (_ for _ in ()).throw(
            PermissionError(13, "Permission denied", "/var/lib/w2c/vars/rec/keeps")) if prefix == "rec/keeps/" else []
        k.vars = Away(box.vars)
        try:
            st, got = k.verify_keep(kp.id, "7")
        finally:
            k.vars = was
        assert st == 503 and got["detail"] == "[Errno 13] Permission denied: '<store>'", got   # no path of this box
    finally:
        box.src_door.shutdown()


def test_a_recording_never_copied_is_pending_and_the_keep_unknown():
    """Nothing contradicts the seal and something is not known yet: a recording of the keep's camera with nothing copied
    is `pending`, not sealed yet, and the keep's integrity `unknown`, `ok` false — never `ok` for what was not compared."""
    box, k = _site(source=False)
    t = box.wall()
    kp = _keep(box, "7", t - 1800, t + 600)                            # the interval is not over: footage may still come
    st, got = k.verify_keep(kp.id)
    assert st == 200 and got["ok"] is False and got["integrity"] == "unknown: 7: not sealed yet", got
    assert got["recordings"]["7"] == {"sealed": "", "now": "", "samples": 0, "result": "pending"}
    over = _keep(box, "7", t - 1800, t - 1200)                         # over — and a live recorder says it holds it
    _says(box, "r-src", {over.id: {"recording": "7", "state": "here", "seconds": 600}})
    assert k.verify_keep(over.id)[1]["recordings"]["7"]["result"] == "pending"


def _says(box, worker, keeps_said):
    """A live recorder's heartbeat saying its side of keeps (`keeps`), as `keep_side_pass` writes it."""
    from w2cplatform.contract import Heartbeat
    box.objects.put(REC_SPEC.sub.heartbeat_key(worker),
                    Heartbeat(worker, box.wall(), [], {"server": "srv-1", "keeps": keeps_said}).to_bytes())


def test_a_recording_with_no_footage_in_an_interval_that_is_over_is_empty_not_pending():
    """The product's `empty` (ffc94a6): a recording not sealed, with no footage in the incidents volume, the interval
    over, and no live recorder saying it holds the recording's footage of the keep — nothing to seal, and nothing will
    come. The verify answers `result: empty` with why, apart from a failure (the keep `unknown`, no seal promised), and
    the holder's `keeps.<id>` says `state: kept` with `empty: [<recording>]`, so that nobody waits for its seal."""
    box, k = _site(source=False)
    t = box.wall()
    kp = _keep(box, "7", t - 1800, t - 1200)
    _says(box, "r-src", {kp.id: {"state": "garbled", "why": "x"}})    # a word that names no recording is not "I have it"
    st, got = k.verify_keep(kp.id)
    assert st == 200 and got["ok"] is False, got
    assert got["recordings"]["7"] == {"sealed": "", "result": "empty", "detail": "7 holds no footage in the interval"}
    assert got["integrity"] == "unknown: 7 holds no footage in the interval"
    state = k.keep_pass()
    assert state[kp.id]["state"] == "kept" and state[kp.id]["empty"] == ["7"] and state[kp.id]["seconds"] == 0
    assert k.heartbeat_extra()["keeps"][kp.id]["empty"] == ["7"]


def test_nobody_writes_a_seal_through_a_door():
    """The seal is rec's own record, not a table: the console serves no `/rec/sealed` (404, to read or to write), and a
    keep written through the table door with a `sealed` in it is refused — an operator cannot write a seal by
    construction (ADR-0057, дополнение п. 3)."""
    from w2cplatform.console import SpecConsole
    from tests.conftest import Served
    box = Box()
    t = box.wall()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    kp = _keep(box, "7", t - 1800, t - 1200)
    with Served(SpecConsole(rec, wall=box.wall)) as call:
        assert call("GET", f"/sealed/{kp.id}")[0] == 404
        assert call("POST", "/sealed", {"recordings": "7=" + "c" * 64, "from": kp.since, "to": kp.until})[0] == 404
        status, said = call("POST", "/keeps", {"cam": "7", "from": kp.since, "to": kp.until, "sealed": "7=" + "c" * 64})
        assert status == 400, (status, said)
        status, view = call("GET", "/keeps")
    assert status == 200 and all("sealed" not in r for r in view["keeps"]), view
    assert keeps.read_seal(box.objects, kp.id) is None


def test_a_keep_rewritten_over_other_minutes_is_not_sealed_until_the_next_pass_seals_it_anew():
    """A seal is bound to the interval it was taken over. The keep's row rewritten by hand to other minutes: the check
    says "not sealed yet" for it — the old seal is of other minutes — and once the recorder has copied the new interval
    whole, its next pass replaces the seal, by CAS, with one of the interval as it stands."""
    box, k, kp, base, keys, closers = _sealed_site()
    try:
        old = keeps.read_seal(box.objects, kp.id)
        row = box.vars.get(keeps.key(kp.id))[0]
        box.vars.put(keeps.key(kp.id), {**row, "from": str(kp.since + 300), "to": str(kp.until + 100)})
        st, got = k.verify_keep(kp.id, "7")
        assert st == 200 and got["integrity"] == "unknown: 7: not sealed yet", got
        assert got["recordings"]["7"]["result"] == "pending" and got["recordings"]["7"]["sealed"] == ""
        k.keep_pass()                                                  # the new minutes copied, whole — and sealed
        seal = keeps.read_seal(box.objects, kp.id)
        assert (seal.since, seal.until) == (kp.since + 300, kp.until + 100) and seal.recordings != old.recordings
        st, got = k.verify_keep(kp.id, "7")
        assert st == 200 and got["ok"] is True and got["integrity"] == "ok", got
    finally:
        for s in closers:
            s.shutdown()


def test_a_keeps_row_is_stamped_made_at_when_made_and_carries_it_through_every_write():
    """ADR-0057, addendum of 2026-10-07 (the form «Платформа»'s): `keeps.stamp: [by, at, made_at]`. `made_at` is the
    console's clock when the row is MADE — `at` is the last write's — and every write after it carries it as stored; a
    body that sends it is refused as an unknown field, as `at` and `by`; a row made before the stamp is not given one
    after the fact; and a keep lifted and made again under the same name has its own."""
    from w2cplatform.spec import Refused
    from w2cplatform.tables import parse
    assert REC_SPEC.table_specs["keeps"].stamp == ("by", "at", "made_at")
    box = Box()
    t = box.wall()
    kp = _keep(box, "7", t - 1800, t - 1200)
    assert kp.made_at == kp.at == t
    box.wall.advance(60)
    again = keeps.write(box.vars, {"cam": "7", "from": t - 1800, "to": t - 1200, "note": "the other gate"}, ["7"], "boris",
                        box.wall())
    assert (again.id, again.made_at, again.at, again.by) == (kp.id, t, t + 60, "boris")
    for word in ("made_at", "at", "by"):
        try:
            keeps.write(box.vars, {"cam": "7", "from": t - 1800, "to": t - 1200, word: 1.0}, ["7"], "mallory", box.wall())
            raise AssertionError(f"{word} in the body was taken")
        except Refused:
            pass
    assert keeps.declared(box.vars)[0].made_at == t                                    # nobody's body moved it
    keeps.delete(box.vars, kp.id)
    box.wall.advance(60)
    assert _keep(box, "7", t - 1800, t - 1200).made_at == t + 120                     # made again: its own
    box.vars.put("rec/keeps/8-1-2", {"cam": "8", "from": "1", "to": "2", "by": "anna", "at": "5"})   # made before the stamp
    old = keeps.write(box.vars, {"cam": "8", "from": 1, "to": 2, "note": "n"}, ["8"], "anna", box.wall())
    assert old.made_at == 0.0 and "made_at" not in box.vars.get(keeps.key("8-1-2"))[0]
    for stamp in (["made_at"], ["by", "made_at"], []):                                 # each word on its own
        parse("x", {"t": {"key": "n", "fields": {"n": {"type": "string"}}, "stamp": stamp}}, lambda t, f: f)
    try:
        parse("x", {"t": {"key": "n", "fields": {"n": {"type": "string"}}, "stamp": ["made"]}}, lambda t, f: f)
        raise AssertionError("a stamp word nobody declared was taken")
    except ValueError as e:
        assert "`made_at`" in str(e), e


def test_a_keep_lifted_and_made_again_is_not_sealed_by_the_old_seal_and_a_seal_of_no_keep_goes():
    """ADR-0057, addendum of 2026-10-07 (the product's GW note): the seal names the keep it was taken for by its row's
    `made_at`. The keep lifted and made again under the same name over the same minutes is a new keep: the old seal does
    not count for it — the check says "not sealed yet" — and the recorder of the incidents volume, before it seals, drops
    the seal no keep counts for (`keeps.drop_stale_seals`) and seals the new keep's copy anew. A seal whose keep is gone
    is dropped by that pass too; one whose keep row does not read is left."""
    box, k, kp, base, keys, closers = _sealed_site()
    try:
        old = keeps.read_seal(box.objects, kp.id)
        assert old.keep_made_at == kp.made_at and old.of(kp)
        keeps.delete(box.vars, kp.id)
        box.wall.advance(30)
        made = _keep(box, "7", kp.since, kp.until)
        assert made.id == kp.id and made.made_at == kp.made_at + 30
        assert old.of(made) == {}                                                     # the old seal is not this keep's
        st, got = k.verify_keep(made.id, "7")
        assert st == 200 and got["integrity"] == "unknown: 7: not sealed yet", got
        k.keep_pass()                                                                  # dropped, then sealed anew
        seal = keeps.read_seal(box.objects, made.id)
        assert seal.keep_made_at == made.made_at and seal.of(made) == {"7": old.recordings[0][1]}, seal
        st, got = k.verify_keep(made.id, "7")
        assert st == 200 and got["ok"] is True and got["integrity"] == "ok", got
        assert keeps.drop_stale_seals(box.vars, box.objects) == {}                    # it counts: it stays
        keeps.delete(box.vars, made.id)
        box.objects.put(keeps.seal_key("9-1-2"), old.to_bytes())                       # …a seal whose keep never was
        box.vars.put("rec/keeps/5-1-2", {"cam": "5", "from": "1", "to": "2"})
        box.objects.put(keeps.seal_key("5-1-2"), old.to_bytes())                       # …one whose keep is not of it
        k.keep_pass()
        for gone in (made.id, "9-1-2", "5-1-2"):
            assert keeps.read_seal(box.objects, gone) is None, gone
    finally:
        for s in closers:
            s.shutdown()


def test_the_recorder_seals_only_a_whole_copy_of_a_keep_that_reads_and_only_once():
    """`RecWorker._seal` (ADR-0057, дополнение п. 3: пишет рекордер тома incidents; the product's `SealKeeps`): a copy
    short of what no door from here can fill is not sealed; a keep whose interval does not read is never sealed; and a
    recording sealed once is not sealed again, whatever the recorder computes later. The family is a row of the store
    on a cluster — rec's `objects.rows` — which the recorder's role writes and the console only reads (the rights file,
    `tests/cluster/test_policies.py`)."""
    from w2cplatform.catalog import matches
    assert "sealed/*" in REC_SPEC.object_rows
    assert any(matches(f"rec/{p}", keeps.seal_key("7-1-2")) for p in REC_SPEC.object_rows)
    box, k = _site()
    t = box.wall()
    footage(box.src, "7", 1, t - 3600, t - 1500, step=10)
    whole = _keep(box, "7", t - 1800, t - 1600)
    box.vars.put("rec/keeps/7-bad", {"cam": "7", "from": "yesterday", "to": str(t), "by": "anna", "recordings": '["7"]'})
    state = k.keep_pass()
    seal = keeps.read_seal(box.objects, whole.id)
    assert state[whole.id]["whole"] == ["7"] and seal.of(whole) == {"7": state[whole.id]["sha256"]["7"]}
    assert keeps.read_seal(box.objects, "7-bad") is None                          # an interval that does not read
    box.src_door.shutdown()                                                       # no door from here answers now
    short = _keep(box, "7", t - 1700, t - 1400)                                   # half of it copied with the first
    state = k.keep_pass()
    assert state[short.id]["missing"] > 0 and "whole" not in state[short.id]
    assert keeps.read_seal(box.objects, short.id) is None                         # not whole: not sealed
    k._seal(whole, {"7": "f" * 64}, box.wall())                                   # a later digest of a sealed copy…
    assert keeps.read_seal(box.objects, whole.id) == seal                         # …changes nothing
    assert [e["keep"] for e in _events(box, "archive.keep.sealed")] == [whole.id]
