"""One garbled row of the store, one garbled number of a heartbeat — and the loop that must outlive both (the review's
seventh pass).

The sixth pass closed the class "one row that does not parse" for the rows the platform's controller and worker read.
The seventh found it again in the rows it had not walked — the volumes, the keeps, the requests, `platform/space`,
`<sub>/next_id`, the numbers of heartbeats on `/metrics` and in the console's loops — and found the worst of them could
silence every recorder of a cluster, because a recorder's lease step and its heartbeat stood in ONE `try`. So two
things are proved here: each table is read through the one reader of rows (`w2cplatform.rows`) — the row skipped,
counted once by its key, named — and every loop that renews and heartbeats does the two in tries of their own.
"""
import json
import threading
import time

from w2cplatform.contract import Heartbeat
from w2cplatform.spec import SpecController
from vms import keeps, volumes
from vms.config import REC_SPEC
from tests.conftest import Box
from tests.test_slot_fence import _forget_garbled


def _prometheus(text: str) -> None:
    """Every sample line of a scrape ends in a number — one line that does not, and Prometheus refuses the scrape."""
    for line in text.splitlines():
        if line and not line.startswith("#"):
            float(line.rsplit(" ", 1)[1])


# -- the volumes (part 2, blocker 1) -----------------------------------------------------------------------------------

def test_one_garbled_volume_row_stops_no_recorder_and_is_named_on_the_volumes_page():
    """`quota_bytes: "1e12"` in ONE volume's row — another server's — raised out of `volumes.declared`, under every
    recorder's lease step: reproduced, the step raised on every pass and (with the heartbeat in the same `try`) no
    recorder heartbeat for 150 s. The row is skipped where volumes are listed and counted ONCE however often it is
    read; the recorder takes its own disk; the volumes page names the row and what to do; `/metrics` is whole."""
    from tests.test_volumes import _disk, _recorder
    from vms.console import rec_metrics
    box = Box()
    _disk(box, "a-good")
    box.vars.put(volumes.key("s3-main"), {"kind": "network", "url": "s3://vms/site", "quota_bytes": "1e12",
                                         "enabled": "true"})
    r = _recorder(box, "r-1", "srv-a")
    for _ in range(3):                                                  # every pass, not once
        assert r.lease_pass() == [], "the lease step raised over another volume's row"
    assert r.hold == "a-good" and r.store is not None and not r.volume_error
    r.heartbeat_once()
    hb = Heartbeat.from_bytes(box.objects.get(REC_SPEC.sub.heartbeat_key("r-1")))
    assert hb.extra["volumes_garbled"] == 1, hb.extra                  # one row, read three times: ONE row
    view = volumes.served(box.vars, REC_SPEC.sub, box.wall(), objects=box.objects)
    rows = {v["name"]: v for v in view["volumes"]}
    assert rows["a-good"]["served_by"] and rows["s3-main"]["garbled"] and "does not parse" in rows["s3-main"]["why"]
    assert view["wanted"] == 2 and view["serving"] == 1
    rec_ctl = SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall)
    text = "\n".join(rec_metrics(rec_ctl)())
    assert "rec_volumes_declared 2" in text and "rec_volumes_unserved 1" in text
    # …and the console does not write such a row: the door refuses it in words (it raised a bare `ValueError`)
    from w2cplatform.spec import Refused
    for bad in ({"quota_bytes": "1e12"}, {"quota_bytes": 1 << 30, "shrink_confirmed": "yes"}):
        try:
            volumes.write(box.vars, {"name": "s3-2", "kind": "network", "url": "s3://vms/two", **bad})
            raise AssertionError(f"written: {bad}")
        except Refused as e:
            assert "whole number of bytes" in str(e)
    _forget_garbled()


def test_a_recorder_keeps_writing_into_its_volume_when_that_volumes_row_stops_parsing():
    """Read as "withdrawn", the recorder's OWN volume garbled under it would be let go and its recordings stopped — for
    one field. It is kept by the row it read last; the row named on the page, the recorder still serving it."""
    from tests.test_volumes import _disk, _recorder
    box = Box()
    _disk(box, "a-good")
    r = _recorder(box, "r-1", "srv-a")
    r.lease_pass()
    st = r.store
    assert r.hold == "a-good" and st is not None
    row, idx = box.vars.get(volumes.key("a-good"))
    box.vars.put(volumes.key("a-good"), {**row, "quota_bytes": "64M"}, cas=idx)
    for _ in range(2):
        r.lease_pass()
    assert r.hold == "a-good" and r.store is st and r.volume == "a-good"
    rows = {v["name"]: v for v in volumes.served(box.vars, REC_SPEC.sub, box.wall(), objects=box.objects)["volumes"]}
    assert rows["a-good"]["served_by"] and "still holds it" in rows["a-good"]["why"]
    # …and not without a word for ever (the eighth pass, a minor): past `ROW_UNREAD_AFTER` an alarm, once a day
    from w2cplatform.eventdatabase import EventIndex
    unreadable = lambda: [e for e in EventIndex(box.archive, "srv-a", wall=box.wall).query(0, box.wall() + 1, subsystem="rec")["events"]
                          if e["kind"] == "archive.volume.unreadable"]
    assert unreadable() == []
    for _ in range(3):
        box.wall.advance(r.ROW_UNREAD_AFTER / 2); box.clock.advance(r.ROW_UNREAD_AFTER / 2)
        r.lease_pass()
    [alarm] = unreadable()
    assert alarm["class"] == "alarm" and alarm["volume"] == "a-good" and alarm["seconds"] >= r.ROW_UNREAD_AFTER
    _forget_garbled()


def test_a_card_whose_row_stops_parsing_stays_the_cameras_card():
    """The camera's own recorder reads the volumes too (`CardRecorder.volume_pass`): the same reader, and its card
    kept by the row read last."""
    from tests.test_camera_card import _camera
    box, rec, ring, act, rec_ctl = _camera()
    assert rec.hold == "card" and rec.card is not None
    row, idx = box.vars.get(volumes.key("card"))
    box.vars.put(volumes.key("card"), {**row, "quota_bytes": "lots"}, cas=idx)
    assert rec.lease_pass() == [] and rec.hold == "card" and rec.card is not None and not rec.volume_error
    _forget_garbled()


def test_a_recording_is_not_homed_on_a_volume_whose_row_does_not_parse():
    """Read as "no volume", a card whose row was garbled let any camera's recording be homed on it. It is a refusal."""
    from w2cplatform.spec import Refused
    box = Box()
    box.vars.put(volumes.key("card2"), {"kind": "edge", "url": "/card", "server": "cam-2", "cam": "2", "quota_bytes": "x"})
    ctl = SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall)
    try:
        ctl.create({"name": "1-b", "cam": "1", "home": "card2"})
        raise AssertionError("homed on a volume nobody can read")
    except Refused as e:
        assert "does not parse" in str(e)
    _forget_garbled()


# -- the loops: the lease step and the heartbeat apart (part 2, blocker 1; part 1, M1) ---------------------------------

def test_every_loop_heartbeats_when_its_lease_step_raises():
    """The holder's loop (the recorder's and the card's, which inherit it) and the evaluator's had the lease step and the
    heartbeat in ONE `try`: whatever the step raised, the heartbeat after it never went, and the controller called a
    sound process dead at 45 s. Each loop of each kind is run for real with a lease step that raises; a heartbeat goes
    out after it, on the same turn of the loop. The detector, scan, survey and gateway loops had them apart already —
    run here so that stays so."""
    from tests.test_stand_in import _all_workers
    box = Box()
    for w in _all_workers(box):
        kind = type(w).__name__
        stop, said, raised = threading.Event(), [], []

        def boom(*a, **kw):
            raised.append(1)
            box.clock.advance(11); box.wall.advance(11)                # the holder heartbeats every 10 s of its clock
            raise ValueError("a row that does not parse")

        def heartbeat(*a, **kw):
            if raised and not stop.is_set():
                said.append(1)
                stop.set()

        w.lease_pass = w.renew_leases = boom
        w.heartbeat_once = heartbeat
        w.reconcile_once = lambda *a, **kw: box.clock.advance(30) or []   # past any loop's lease interval
        if hasattr(w, "pump_once"):
            w.pump_once = lambda *a, **kw: None
        t = threading.Thread(target=w.run, kwargs={"poll": 0.01, "stop": stop}, daemon=True)
        t.start(); t.join(3)
        stop.set(); t.join(3)
        assert raised and said, f"{kind}: the lease step raised and no heartbeat followed it"


# -- the requests (part 1, M2 and M3) ------------------------------------------------------------------------------

def _rec_console(box):
    return SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)


def test_one_garbled_request_row_is_refused_alone_and_the_recordings_are_started_and_ended():
    """Reproduced: `a-bad` with `valid_until: "soon"` before `b-good` — `record_on_request` raised on every turn for
    seventy-five minutes, nothing was recorded on request and no finished recording was ended (the two shared a
    `try`). The garbled request is refused — counted once, cleared — and the next one is started; a deadline of `nan`
    or `inf` is refused the same way, never "no deadline"."""
    from vms import jobs
    box = Box()
    rec = _rec_console(box)
    now = box.wall()
    rec.create({"name": "9-auto", "cam": "9", "until": now - 1})       # a recording on request whose end has passed
    for rid, until in (("a-bad", "soon"), ("a-nan", "nan"), ("a-inf", "inf")):
        box.vars.put(f"rec/requests/{rid}", {"action": "record", "cam": "7", "minutes": "10", "valid_until": until})
    box.vars.put("rec/requests/b-good", {"action": "record", "cam": "8", "minutes": "10", "valid_until": str(now + 30)})
    _forget_garbled()
    assert jobs.record_on_request(rec, now) == 1
    assert rec.unit("8-auto") is not None and rec.unit("7-auto") is None
    assert box.vars.list("rec/requests/") == []                         # refused or performed: nothing left standing
    assert jobs.REQUESTS.counts.get("rec", 0) == 3
    assert jobs.expire_recordings(rec, now) == 1 and rec.unit("9-auto") is None
    _forget_garbled()


def test_a_detector_request_whose_numbers_are_words_is_refused_and_not_tried_for_ever():
    """The sibling in `detect_on_request`: its `valid_until` read bare stopped the family; a `minutes` that is a word
    fell into "not an answer — stays, and is tried again", every two seconds for ever. Both are refused now, counted,
    and the request behind them is turned into work."""
    from vms import jobs
    from tests.test_det_requests import _ask, _site
    box = Box(); det, job, rec = _site(box)
    _ask(box, "a-bad", action="detect", cam="7", kind="lpr", minutes=10, valid_until="soon")
    _ask(box, "a-words", action="detect", cam="7", kind="motion", minutes="ten")
    _ask(box, "b-good", action="detect", cam="7", kind="lpr", minutes=10)
    assert jobs.detect_on_request(det, job, rec, box.wall()) == 1 and det.unit("7-lpr-auto") is not None
    assert box.vars.list("det/requests/") == []
    _forget_garbled()


def test_the_console_loop_ends_timed_recordings_when_starting_them_fails():
    """The console's requests loop called `record_on_request` and `expire_recordings` in one `try`: whatever the first
    raised, the second never ran. They are tried apart."""
    import vms.__main__ as main
    from vms import jobs
    box = Box()
    rec = _rec_console(box)
    rec.create({"name": "9-auto", "cam": "9", "until": box.wall() - 1})
    real = jobs.record_on_request
    jobs.record_on_request = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("the store went away"))
    ended = []
    real_expire = jobs.expire_recordings
    jobs.expire_recordings = lambda ctl, now: ended.append(real_expire(ctl, box.wall()) or 1) or 1
    t = threading.Thread(target=main._requests_loop, kwargs={"rec_ctl": rec, "every": 0.01}, daemon=True)
    try:
        t.start()
        end = time.monotonic() + 3
        while not ended and time.monotonic() < end:
            time.sleep(0.01)
    finally:
        main.stop.set(); t.join(3); main.stop.clear()
        jobs.record_on_request, jobs.expire_recordings = real, real_expire
    assert ended and rec.unit("9-auto") is None


def test_a_command_whose_deadline_is_nan_or_inf_is_refused_by_the_holder_and_at_the_console():
    """`float("nan")` passed the holder's three checks — every comparison with it is false — and a holder that came up
    three hours later performed the command; the console filed JSON `NaN` as it came. Both refuse it now."""
    from tests.test_epoch_refused import _ask, _two_doors
    from tests.test_group_by import _Body, _ctl
    from vms.console import vms_routes
    box = Box()
    con, (one, two), w = _two_doors(box)
    _ask(box, con, "a-nan", one, valid_until="nan")
    _ask(box, con, "a-inf", one, valid_until="inf")
    box.wall.advance(3 * 3600); box.clock.advance(3 * 3600)             # three hours later
    w.pump_once()
    assert w.devices["acme/10.0.0.91"].did == [] and w.commands["refused"] == 2 and w.commands["performed"] == 0
    box2 = Box(); ctl, con2 = _ctl(box2)
    door = con2.create_camera({"name": "door", "source": "driverpack://acme/10.0.0.90/ch/1", "kind": "io"})["id"]
    route = vms_routes(None, None, con2, None)
    for i, bad in enumerate(("NaN", "Infinity", '"soon"')):
        payload = f'{{"unit": {door}, "action": "output", "port": 1, "valid_until": {bad}}}'.encode()
        st, body = route(_Body(payload, key=f"k{i}"), "POST", "/requests", {})
        assert st == 400 and body["error"] == "bad deadline", (bad, st, body)
    assert box2.vars.list("vms/requests/") == []


# -- the resource: restore under the pulse (part 1, M4), the watermark, the keeps ---------------------------------------

def test_restore_beats_under_the_same_pulse_as_the_pass():
    """Reproduced: a replaced disk, 2000 buckets pulled at 50 ms each — 100 s without a heartbeat, the resource silent to
    the index and the console while its door answered. `restore` beats as `pass_` does, a mark per bucket pulled."""
    from w2cplatform.events import Bucket
    from w2cplatform.resource import Resource, resources_seen
    box = Box()
    seen = []

    class Peer:
        def mirrored(self, url, server):
            return [Bucket("vms", "7", 1, i * 600.0, (i + 1) * 600.0, f"vms/7/1/{i}.events.jsonl", 1) for i in range(6)]

        def get(self, url, server, path):
            box.wall.advance(30); box.clock.advance(30)                # 6 × 30 s: well past `lost_after`
            time.sleep(0.06)
            seen.append(resources_seen(box.objects)["srv-1"]["ts"] == box.wall())
            return b'{"ts": 1}\n'

    res = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, clock=box.clock, peers=Peer())
    res.PULSE_SECONDS = 0.02
    box.objects.put("platform/resources/srv-2/heartbeat", json.dumps(
        {"server": "srv-2", "ts": box.wall(), "url": "http://srv-2", "mirrors": {"srv-1": 6}}).encode())
    res.heartbeat()
    assert res.restore()["pulled"] == 6
    assert seen[1:] and all(seen[1:]), seen                             # fresh while it pulled (the first may beat the pulse)


def test_a_garbled_watermark_row_acts_on_the_settings_read_last_and_says_so():
    """`high: "85%"` raised out of `relieve` on every pass: a disk at 98 % freed nothing, with the settings read last in
    hand. They are used — or, never read, the defaults — and the heartbeat says which."""
    from w2cplatform.resource import SPACE_KEY, Resource
    box = Box()
    asked = []

    class Frees:
        def pass_(self, now):
            return {}

        def free(self, need, now, min_days, volume=None):
            asked.append(need)
            return {"freed": need}

    def full(path):
        return 100, 2                                                   # 98 % used
    res = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, space_probe=full)
    res.register("vms", Frees())
    box.vars.put(SPACE_KEY, {"enabled": "true", "high": "0.9", "low": "0.5"})
    assert res.relieve()["space"] == "over" and asked == [48]
    box.vars.put(SPACE_KEY, {"enabled": "true", "high": "85%", "low": "0.5"})
    out = res.relieve()
    assert out["space"] == "over" and asked == [48, 48] and "(high)" in res.heartbeat()["space_garbled"]
    assert "settings read last" in res.space_garbled
    fresh = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, space_probe=full)
    fresh.register("vms", Frees())
    assert fresh.relieve()["space"] == "over" and asked[-1] == 48 and "the defaults" in fresh.space_garbled   # the row's `low` stands
    box.vars.put(SPACE_KEY, {"enabled": "true", "high": "0.9", "low": "0.5"})
    fresh.relieve()
    assert "space_garbled" not in fresh.heartbeat()                    # mended: said no more
    _forget_garbled()


def test_a_mirror_whose_copies_do_not_parse_mirrors_to_one_peer():
    """The sibling of the watermark: `copies: "two"` raised out of `mirror` on every pass, and a mirror switched on
    copied nothing."""
    from w2cplatform.resource import MIRROR_KEY, mirror_settings
    box = Box()
    box.vars.put(MIRROR_KEY, {"enabled": "true", "copies": "two"})
    assert mirror_settings(box.vars) == {"enabled": True, "copies": 1}
    _forget_garbled()


def test_one_garbled_keep_holds_its_camera_whole_and_the_others_are_swept():
    """Reproduced: `since: "yesterday"` in camera 9's keep — three passes of `retain` in errors, and cameras 7 and 8 kept
    twenty of twenty old buckets: the disk fills. Not knowing which minutes are kept is "all of camera 9's"; the rest are
    swept by their days, the row is counted once and nothing is copied for it."""
    from w2cplatform.events import EventLog, bucket_names_under
    from vms.resource import vms_resource
    box = Box()
    res = vms_resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    old = box.wall() - 40 * 86400
    for cam in ("7", "8", "9"):
        EventLog(box.archive, "vms", cam, 1).append(old, "motion")
        box.vars.put(f"vms/retention/{cam}", {"days": "30"})
    box.vars.put(keeps.key("9-1-2"), {"cam": "9", "from": "yesterday", "to": "today"})
    for _ in range(2):
        res.retain()
    assert bucket_names_under(box.archive, "vms", "7", 600) == [] and bucket_names_under(box.archive, "vms", "8", 600) == []
    assert len(bucket_names_under(box.archive, "vms", "9", 600)) == 1
    assert keeps.KEEPS.counts.get("rec") == 1 and keeps.declared(box.vars) == []
    assert "rows_garbled" in res.heartbeat()
    _forget_garbled()


# -- `/metrics` (part 2) ---------------------------------------------------------------------------------------------

def test_one_word_in_one_heartbeat_field_does_not_take_the_metrics_page():
    """`headroom: "some"`, `ts: "then"` in the pass report, `space.full: "n/a"` at a resource, half a sweep list: each
    raised out of `metrics_text` and the subsystem's whole page was gone, every alert with it. And the VMS's own
    numbers — a recorder's `archive_away_since`, a holder's `command_counts`, a histogram, an evaluator's gauges. Each
    is read as not said, and every line of the page is a number Prometheus takes."""
    from vms.config import AUTO_SPEC, DET_SPEC, SPEC
    from vms.console import auto_metrics, rec_metrics, vms_metrics
    from w2cplatform.console import SpecConsole
    from tests.test_lesson4_worker import _box_with_cameras
    box, ctl = _box_with_cameras(2)
    t = box.wall()
    box.objects.put("vms/heartbeats/w-2", Heartbeat("w-2", t, [], {
        "server": "srv-b", "capacity": "many", "headroom": "some", "conflicts": "few", "store_errors": "x",
        "pass_failures": "y", "unconfirmed": "z", "slots_garbled": "w", "holds_garbled": "v",
        "command_counts": {"performed": "many"}, "command_road": {"buckets": ["x"], "count": 1, "sum": 1, "skewed": "s"},
        "command_wait": "nonsense"}).to_bytes())
    box.objects.put("platform/resources/srv-b/heartbeat", json.dumps(
        {"server": "srv-b", "ts": t, "url": "http://srv-b", "space": {"full": "n/a"}, "short": "lots"}).encode())
    box.objects.put("vms/controller/pass", json.dumps({"ts": "then", "last_success": "never", "failures": "many",
                                                       "unplaced": "?", "seconds": "slow"}).encode())
    text = SpecConsole(ctl, wall=box.wall).metrics_text()
    _prometheus(text)
    assert "vms_reconcile_last_pass_age_seconds -1" in text and 'vms_resource_full{server="srv-b"} 0' in text
    assert 'vms_worker_holds_garbled{worker="w-2"} 0' in text                # the holds, on the page (a minor)
    _prometheus("\n".join(vms_metrics(ctl)()))

    det = SpecController(DET_SPEC, box.vars, box.objects, wall=box.wall)
    box.vars.put(DET_SPEC.sub.sweep_key(), {"at": "then", "digests": '["sha256-'})
    _prometheus(SpecConsole(det, wall=box.wall).metrics_text())

    rec = SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall)
    box.objects.put("rec/heartbeats/r-9", Heartbeat("r-9", t, [
        {"id": "1", "phase": "running", "last_frame_at": "x", "depth_days": "deep", "samples_refused": {"BAD": "many"},
         "lease": "unconfirmed", "unconfirmed_s": "long"}], {
        "server": "srv-b", "archive_away_since": "then", "keep_missing": {"k-1": "lots"}}).to_bytes())
    _prometheus("\n".join(rec_metrics(rec)()))

    auto = SpecController(AUTO_SPEC, box.vars, box.objects, wall=box.wall)
    box.objects.put("auto/heartbeats/a-1", Heartbeat("a-1", t, [], {
        "pass_seconds": "slow", "late": "lots", "waits": "w", "latency": {"buckets": [1], "count": "c", "sum": 0}}).to_bytes())
    _prometheus("\n".join(auto_metrics(auto)()))
    assert SPEC.name == "vms"
    _forget_garbled()


# -- the console's loops over heartbeats (part 2) ---------------------------------------------------------------------

def test_one_word_in_a_recorders_closed_spans_stops_no_scan_and_no_keep():
    """`closed: "7|then|now"` in one recorder's heartbeat raised out of `scan_what_arrived` — no scan over arrived
    footage for any recorder — and the same shape in a survey's `hits` out of `keep_what_fired`. That span is passed
    by, counted; the others are turned into work."""
    from vms import jobs
    from vms.config import DET_SPEC, DETJOB_SPEC, SURVEY_SPEC
    box = Box()
    t = box.wall()
    rec = _rec_console(box)
    det = SpecController(DET_SPEC, box.vars.as_writer("console", DET_SPEC.acl_console()), box.objects, wall=box.wall)
    job = SpecController(DETJOB_SPEC, box.vars.as_writer("console", DETJOB_SPEC.acl_console()), box.objects, wall=box.wall)
    survey = SpecController(SURVEY_SPEC, box.vars, box.objects, wall=box.wall)
    rec.create({"name": "7", "cam": "7"}); rec.create({"name": "8", "cam": "8"})
    det.create({"name": "8-lpr", "cam": "8", "kind": "lpr"})
    box.objects.put("rec/heartbeats/r-1", Heartbeat("r-1", t, [], {"closed": "7|then|now"}).to_bytes())
    box.objects.put("rec/heartbeats/r-2", Heartbeat("r-2", t, [], {"closed": f"8|{t - 600}|{t - 300}"}).to_bytes())
    assert jobs.scan_what_arrived(rec, det, job) == 1
    box.objects.put("survey/heartbeats/s-1", Heartbeat("s-1", t, [], {"hits": f"7|soon|later,8|{t - 600}|{t - 300}"}).to_bytes())
    assert jobs.keep_what_fired(survey, rec) == 1
    _forget_garbled()


# -- `<sub>/next_id` (part 2, a minor) ---------------------------------------------------------------------------------

def test_a_garbled_id_counter_gives_the_next_number_past_the_largest_id():
    """`n: "seven"` raised out of every create: not one camera could be added until the row was mended by hand. The next
    number is one past the largest id there is — the deleted ones included — and the row is written whole."""
    from tests.test_lesson4_worker import _box_with_cameras
    box, ctl = _box_with_cameras(3)
    ctl.delete_camera(3)
    box.vars.put("vms/next_id", {"n": "seven"})
    new = ctl.create_camera({"name": "cam4", "source": "driverpack://file/cam4.mp4"})["id"]
    assert new == 4 and box.vars.get("vms/next_id")[0] == {"n": "4"}
    assert ctl.create_camera({"name": "cam5", "source": "driverpack://file/cam5.mp4"})["id"] == 5
    _forget_garbled()


# -- the walk over every reader (the siblings the review did not name) -------------------------------------------------

def test_a_name_in_an_assignment_that_is_no_units_id_stops_no_move():
    """`read_assignment` reads the list of names as it stands, and `redistribute` took every name for an id: `seven` in
    the row of a slot on a draining server raised out of the whole step, and no unit of any leaving slot moved."""
    from w2cplatform.contract import DRAIN_KEY
    from tests.test_garbled_rows import _placed
    box, ctl = _placed(3)
    on1 = [u for u in ctl.assignment("w-1").units]
    assert on1
    box.vars.put("vms/workers/w-1", {"units": ",".join(on1 + ["seven"]), "rev": "3"})
    box.vars.put(DRAIN_KEY, {"server": "srv-a"})
    ctl.redistribute()
    assert all(ctl.where(int(u)) == "w-2" for u in on1)
    _forget_garbled()


def test_a_status_entry_that_is_not_an_object_or_names_no_unit_stops_no_reader():
    """A heartbeat whose status holds a word, or an entry with no `id`: the first parsed and raised `AttributeError` in
    every reader that asks an entry `.get`; the second raised `KeyError` out of `read_model` — under the console's list,
    the job reaper and the asks for footage — and out of the recorders' metrics. The first heartbeat is skipped where
    heartbeats are read; the entry with no id says nothing about a unit."""
    from vms import jobs
    from vms.config import DETJOB_SPEC
    from vms.console import rec_metrics
    box = Box()
    t = box.wall()
    job = SpecController(DETJOB_SPEC, box.vars, box.objects, wall=box.wall)
    box.objects.put("detjob/heartbeats/j-1", Heartbeat("j-1", t, ["running"], {}).to_bytes())
    box.objects.put("detjob/heartbeats/j-2", Heartbeat("j-2", t, [{"phase": "done"}], {}).to_bytes())
    assert job.read_model() == [] and "j-1" not in job.workers_seen()
    assert jobs.reap(job) == {"done": 0, "failed": 0} and jobs.ask_for_footage(job, _rec_console(box)) == 0
    rec = SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall)
    box.objects.put("rec/heartbeats/r-9", Heartbeat("r-9", t, [{"phase": "running", "last_frame_at": t, "depth_days": 1}],
                                                    {"writer": "stuck"}).to_bytes())
    _prometheus("\n".join(rec_metrics(rec)()))
    _forget_garbled()


def test_a_sweep_list_entry_that_is_no_digest_stops_no_reclaiming():
    """`<sub>/sweep` holding a name that is no digest: `blob_key` raised on it at every sweep, and the list was never
    cleared — nothing of the subsystem was reclaimed again. Only digests are swept."""
    from vms.config import DET_SPEC
    box = Box()
    ctl = SpecController(DET_SPEC, box.vars, box.objects, wall=box.wall)
    ctl.create({"name": "7-linecross", "cam": "7", "kind": "linecross"})
    ctl.update("7-linecross", {"mask": ctl.put_blob(b"a" * 900)})
    ctl.update("7-linecross", {"mask": ctl.put_blob(b"b" * 900)})                    # the first is an orphan now
    assert ctl.sweep_blobs()["marked"] == 1
    items, idx = box.vars.get(DET_SPEC.sub.sweep_key())
    marked = json.loads(items["digests"])
    box.vars.put(DET_SPEC.sub.sweep_key(), {**items, "digests": json.dumps(marked + ["../not-a-digest", 5])}, cas=idx)
    box.wall.advance(30 * 86400)
    assert ctl.sweep_blobs() == {"marked": 0, "deleted": 1, "waiting": 0}


def test_a_book_of_primaries_nobody_can_read_makes_the_backup_record():
    """`carried_primary` parsed the book's entry and the agent's mark bare, inside `enrich` — inside the reconciler's
    loop: every start after that backup, every stop, the gate and the writer's pass were skipped. A book nobody can read
    is a book nobody can vouch for, and then the backup records, as for one that is old."""
    from tests.conftest import recorder
    from vms.recworker import DOMAIN_SEEN, PRIMARIES
    box = Box()
    r = recorder(box)
    box.objects.put(DOMAIN_SEEN, json.dumps({"ts": box.wall()}).encode())
    box.vars.put(PRIMARIES, {"SN1": '{"should": tru'})
    assert r.carried_primary({"id": "1-b", "cam": "ref:SN1"}, box.wall()) is True
    box.vars.put(PRIMARIES, {"SN1": json.dumps({"should": True, "written": True})})
    box.objects.put(DOMAIN_SEEN, b'{"ts": "now"}')
    assert r.carried_primary({"id": "1-b", "cam": "ref:SN1"}, box.wall()) is True
    box.objects.put(DOMAIN_SEEN, json.dumps({"ts": box.wall()}).encode())
    assert r.carried_primary({"id": "1-b", "cam": "ref:SN1"}, box.wall()) is False   # mended: read as it says
    _forget_garbled()


def test_a_devices_counts_and_a_holders_coverage_that_are_words_are_that_devices_and_that_cameras():
    """The siblings in the other workers, each a loop over many units: a device row's `relays: "many"` raised out of the
    evaluator's whole pass and the scenario catalogue (`parse_device_row`); a holder's coverage with a word in it out
    of the scan's and the survey's pass over every job; a scan job of a camera of another cluster (`cam: ref:…`) out
    of the scan's pass at its first event (`int(row["cam"])`). Each is read as not said, and the pass goes on."""
    import vms.detjobworker as dj
    import vms.surveyworker as sv
    from vms.config import parse_device_row
    assert parse_device_row({"relays": "many", "presets": "3"})["relays"] == 0
    assert parse_device_row({"relays": "many", "presets": "3"})["presets"] == 3
    assert dj._cam("ref:SN1") == "ref:SN1" and dj._cam("7") == 7
    st = {"id": "7", "coverage": {"from": "then", "to": 100.0}, "index_url": "http://w-1/index", "playback_url": "http://w-1/p"}
    found = ("w-1", Heartbeat("w-1", 0.0, [st], {}), st)
    real = dj.holder_of, sv.holder_of
    dj.holder_of = sv.holder_of = lambda *a, **kw: found
    try:
        assert dj.DetJobWorker.device_has(type("W", (), {"objects": None, "wall": lambda self: 0.0})(), "7", 0, 50) is False
        assert sv.SurveyWorker.device(type("W", (), {"objects": None, "wall": lambda self: 0.0})(), "7") is None
    finally:
        dj.holder_of, sv.holder_of = real
    _forget_garbled()


def test_a_resource_comes_up_over_a_peer_whose_heartbeat_names_no_address():
    """`restore` runs at the start with nothing around it, and read a peer's `url` bare: a peer's heartbeat without one
    ended the resource process at every start. Such a peer takes nothing and gives nothing back; the start goes on."""
    from w2cplatform.resource import Resource
    box = Box()
    res = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    box.objects.put("platform/resources/srv-2/heartbeat", json.dumps(
        {"server": "srv-2", "ts": box.wall(), "mirrors": {"srv-1": 3}}).encode())
    box.vars.put("platform/mirror", {"enabled": "true", "copies": "1"})
    res.heartbeat()
    assert res.restore() == {"pulled": 0} and res.mirror()["mirrored"] == 0


# -- the eighth pass: the peers' doors, the repeats, the labels -------------------------------------------------------

def _prometheus_strict(text: str) -> None:
    """Every line of a scrape as the text format reads it: a comment, or `name{label="value",…} number`, each label
    value with `\\`, `"` and the newline escaped. One line that is not, and Prometheus refuses the scrape whole."""
    import re
    sample = re.compile(r'^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[a-zA-Z_][a-zA-Z0-9_]*="(?:[^"\\\n]|\\[\\"n])*"'
                        r'(,[a-zA-Z_][a-zA-Z0-9_]*="(?:[^"\\\n]|\\[\\"n])*")*\})? \S+$')
    for line in text.splitlines():
        if line and not line.startswith("#"):
            assert sample.match(line), f"a line Prometheus refuses: {line!r}"
            float(line.rsplit(" ", 1)[1])


def test_a_name_with_a_quote_or_a_newline_is_escaped_on_every_metrics_page():
    """Reproduced (part 4): a recording named `7"x` — or with a newline in it — made `rec_last_frame_age_seconds{unit="7"x"}`,
    a line the text format cannot read, and Prometheus refused the whole `rec` scrape: every alert of the recorders gone.
    Every label value of every metrics function goes through one escaping (`w2cplatform.console.label`): the platform's
    page (workers, servers, tables), the recorders', the holders', the evaluators', and a recorder's own."""
    from vms.config import AUTO_SPEC
    from vms.console import auto_metrics, rec_metrics, vms_metrics
    from w2cplatform.console import SpecConsole, label
    from tests.test_lesson4_worker import _box_with_cameras
    assert label('7"x\\y\nz') == '7\\"x\\\\y\\nz'
    box, ctl = _box_with_cameras(1)
    t = box.wall()
    bad = '7"x\nnew'
    box.objects.put(f"vms/heartbeats/{bad}", Heartbeat(bad, t, [], {"server": 's"1\n', "headroom": 1, "capacity": 2,
                                                                     "command_counts": {"performed": 1},
                                                                     "command_road": {"auto": {"buckets": [1], "count": 1, "sum": 0.1}}}).to_bytes())
    box.objects.put('platform/resources/s"1/heartbeat', json.dumps(
        {"server": 's"1\n', "ts": t, "url": "http://s1", "space": {"full": 0.5}, "rows_garbled": {'ke"ep\n': 2}}).encode())
    _prometheus_strict(SpecConsole(ctl, wall=box.wall).metrics_text())
    _prometheus_strict("\n".join(vms_metrics(ctl)()))
    rec = SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall)
    box.objects.put(f"rec/heartbeats/{bad}", Heartbeat(bad, t, [
        {"id": bad, "phase": 'run"ning', "last_frame_at": t - 5, "depth_days": 1, "samples_refused": {'B"AD\n': 2},
         "lease": "unconfirmed", "unconfirmed_s": 3}], {
        "server": "srv-b", "archive_failure": 'aw"ay', "writer": {"state": 's"t'}, "keep_missing": {bad: 5},
        "volume_wait": "net is being written by r-1"}).to_bytes())
    text = "\n".join(rec_metrics(rec)())
    _prometheus_strict(text)
    assert 'rec_last_frame_age_seconds{unit="7\\"x\\nnew"} 5.0' in text and 'rec_volume_wait{worker="7\\"x\\nnew"} 1' in text
    auto = SpecController(AUTO_SPEC, box.vars, box.objects, wall=box.wall)
    box.objects.put(f"auto/heartbeats/{bad}", Heartbeat(bad, t, [], {"pass_seconds": 1, "late": 0, "wants_folded": 70}).to_bytes())
    text = "\n".join(auto_metrics(auto)())
    _prometheus_strict(text)
    assert 'auto_wants_folded{worker="7\\"x\\nnew"} 70' in text
    r = type("R", (), {"keep_state": {bad: {"missing": 5}}, "reconciler": type("C", (), {"actual": {}})(), "backfilled": 0,
                       "dropped_seconds": 0.0, "volume_wait": ""})()
    from vms.recworker import RecWorker
    _prometheus_strict(RecWorker.metrics_text(r))
    _forget_garbled()


class _Peer:
    """A peer resource, in process: what it lists of `srv-1`'s buckets, and what it gives back — `bad` paths it does not
    (it raises), `dead` when its listing itself fails."""
    def __init__(self, paths, bad=(), dead=False):
        self.paths, self.bad, self.dead, self.asked = list(paths), set(bad), dead, []

    def mirrored(self, url, server):
        from w2cplatform.events import Bucket
        if self.dead:
            raise OSError(f"{url}: 503 Service Unavailable")
        return [Bucket("vms", "7", 1, 0.0, 600.0, p, 1) for p in self.paths]

    def get(self, url, server, path):
        self.asked.append(path)
        if path in self.bad:
            raise OSError(f"{url}: the connection was reset at {path}")
        return b'{"t": 1, "kind": "motion"}\n'


def test_a_restore_takes_what_every_peer_gives_and_asks_again_for_what_did_not_come():
    """Reproduced (part 4): a peer with a live heartbeat whose door refused gave back 0 of 20 buckets, a cut on the fourth
    gave back 3, and `restore` ran once, at the start, in one `try` — nothing asked again while the copies aged on the
    peers. Now one peer and one bucket are their own trouble: of 20 with one that does not come, 19 are back; a peer
    whose listing fails does not cost the other peer's; what is left is said in the heartbeat and on `/metrics` and is
    due again after its pause (`restore_due`, doubling); a path a peer names outside the tree is never written."""
    import os
    from w2cplatform.console import SpecConsole
    from w2cplatform.resource import RESTORE_RETRY, Resource
    from tests.test_lesson4_worker import _box_with_cameras
    box, ctl = _box_with_cameras(1)
    paths = [f"vms/7/e1/{i:02d}.events.jsonl" for i in range(20)]
    good, dead = _Peer(paths + ["../../escape.events.jsonl"], bad={paths[3]}), _Peer(["vms/8/e1/0.events.jsonl"], dead=True)

    class Peers:
        def mirrored(self, url, server):
            return (good if url == "http://srv-2" else dead).mirrored(url, server)

        def get(self, url, server, path):
            return (good if url == "http://srv-2" else dead).get(url, server, path)

    res = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, clock=box.clock, peers=Peers())
    for peer in ("srv-0", "srv-2"):                                    # srv-0 sorts first: its refusal must not end the loop
        box.objects.put(f"platform/resources/{peer}/heartbeat", json.dumps(
            {"server": peer, "ts": box.wall(), "url": f"http://{peer}", "mirrors": {"srv-1": 20}}).encode())
    res.heartbeat()
    got = res.restore()
    assert got["pulled"] == 19 and got["left"] == 1 and got["peers_failed"] == ["srv-0"], got
    assert not os.path.exists(os.path.join(box.root, "escape.events.jsonl"))       # a path out of the tree: never written
    assert not res.restore_due()                                                     # its pause first
    hb = res.heartbeat()
    assert hb["restore"]["left"] == 1 and hb["restore"]["peers_failed"] == ["srv-0"] and hb["restore"]["failed"] == 2
    text = SpecConsole(ctl, wall=box.wall).metrics_text()
    assert 'vms_resource_restore_left{server="srv-1"} 1' in text and 'vms_resource_restore_failures_total{server="srv-1"} 2' in text
    good.bad.clear(); dead.dead = False
    dead.paths = []                                                  # healed: it lists, and holds nothing more of srv-1
    box.clock.advance(RESTORE_RETRY)
    assert res.restore_due()
    again = res.restore()
    assert again["pulled"] == 1 and "left" not in again and not res.restore_due(), again
    assert good.asked.count(paths[3]) == 2 and good.asked.count(paths[0]) == 1      # the one asked again, the others not
    assert "restore" in res.heartbeat()                                             # its failures since start stay counted
    _forget_garbled()


def test_a_mirror_copies_to_every_peer_past_one_that_refuses_and_past_a_bucket_too_big_for_any():
    """Reproduced (part 4): the mirror was one `try` — a peer whose door refused its listing raised out of the loop and the
    next peer got nothing; a bucket over `MIRROR_MAX` was 413 on every pass and no bucket after it was copied to anybody.
    Now the refusing peer is skipped and counted, the bucket too big is sent to nobody and counted once, the buckets after
    it go; both on the heartbeat and `/metrics`. A 413 from a peer is the same: not sent again."""
    from w2cplatform import resource as R
    from w2cplatform.console import SpecConsole
    from w2cplatform.events import EventLog
    from tests.test_lesson4_worker import _box_with_cameras
    box, ctl = _box_with_cameras(1)
    t = box.wall()
    for i in range(4):
        log = EventLog(box.archive, "vms", "7", 1)
        for n in range(1 + (200 if i == 1 else 0)):                   # the second bucket is the big one
            log.append(t - 86400 + i * 600 + n * 0.01, "motion", note="x" * 50)
    sent: dict = {"srv-2": [], "srv-3": []}

    class Peers:
        def mirrored(self, url, server):
            if url == "http://srv-2":
                raise OSError("http://srv-2: 503 Service Unavailable")
            return []

        def put(self, url, server, path, data):
            if len(data) > 4096 and url == "http://srv-3" and refuse_413[0]:
                import urllib.error
                raise urllib.error.HTTPError(url, 413, "Payload Too Large", {}, None)
            sent[url[len("http://"):]].append(path)

    refuse_413 = [False]
    box.vars.put(R.MIRROR_KEY, {"enabled": "true", "copies": "2"})
    res = R.Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, clock=box.clock, peers=Peers())
    for peer in ("srv-2", "srv-3"):
        box.objects.put(f"platform/resources/{peer}/heartbeat", json.dumps(
            {"server": peer, "ts": box.wall(), "url": f"http://{peer}"}).encode())
    real = R.MIRROR_MAX
    R.MIRROR_MAX = 8192
    try:
        out = res.mirror()
    finally:
        R.MIRROR_MAX = real
    assert out["mirrored"] == 3 and out["peers_failed"] == ["srv-2"] and len(sent["srv-3"]) == 3, (out, sent)
    assert res.mirror_too_big == 1 and res.mirror_failed == 1
    hb = res.heartbeat()
    assert hb["mirror"] == {"failed": 1, "too_big": 1, "peers_failed": ["srv-2"]}
    text = SpecConsole(ctl, wall=box.wall).metrics_text()
    assert 'vms_resource_mirror_too_big_total{server="srv-1"} 1' in text and 'vms_resource_mirror_failures_total{server="srv-1"} 1' in text
    # …and a peer that refuses 413 under the bound: counted, and the bucket is not sent to it again
    res2 = R.Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, clock=box.clock, peers=Peers())
    refuse_413[0] = True
    sent["srv-3"].clear()
    assert res2.mirror()["mirrored"] == 3 and res2.mirror_too_big == 1
    sent["srv-3"].clear()
    res2.mirror()
    assert len(sent["srv-3"]) == 3 and res2.mirror_too_big == 1           # the listing is empty: the rest again, the big one not


def test_the_peer_client_writes_only_a_whole_200_as_a_bucket_and_skips_a_garbled_line_of_a_listing():
    """The product team's siblings: a 2xx that is not a 200 was written as a bucket (a 503 is an `HTTPError` here already);
    one garbled line of a peer's `/mirrored` took the whole listing; an answer was read with no bound. Each is the
    line's or the answer's trouble now."""
    import io
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from w2cplatform.events import Bucket
    from w2cplatform.resource import PeerClient

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/mirrored/"):
                good = Bucket("vms", "7", 1, 0.0, 600.0, "vms/7/e1/a.events.jsonl", 1).line()
                body = (good + "\n" + '{"subsystem": "vms", "unit": 7, "epoch": "one"}\n' + good.replace("/a.", "/b.") + "\n").encode()
                self.send_response(200)
            else:
                body = b"partial"
                self.send_response(206)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        listed = PeerClient().mirrored(url, "srv-1")
        assert [b.path for b in listed] == ["vms/7/e1/a.events.jsonl", "vms/7/e1/b.events.jsonl"]
        for call in (lambda: PeerClient().get_into(url, "srv-1", "vms/7/e1/a.events.jsonl", io.BytesIO()),
                     lambda: PeerClient().get(url, "srv-1", "vms/7/e1/a.events.jsonl")):
            try:
                call()
                raise AssertionError("a 206 was taken for a bucket")
            except IOError as e:
                assert "206" in str(e)
    finally:
        srv.shutdown()
    from w2cplatform.rows import answer
    try:
        answer(io.BytesIO(b"x" * 11), 10)
        raise AssertionError("an answer past its bound was read")
    except ValueError:
        pass
    _forget_garbled()


def _canned(box, name: str, body, status: list | None = None, volume: str = "v-canned"):
    """A recorder's archive door that answers `body` (JSON) to every request, announced by a live heartbeat — another
    build's door, or a proxy in front of one. Returns the server; shut it down when done."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    raw = json.dumps(body).encode()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    box.objects.put(REC_SPEC.sub.heartbeat_key(name), Heartbeat(name, box.wall(), status or [], {
        "server": "srv-1", "archive_url": f"http://127.0.0.1:{srv.server_address[1]}", "volume": volume}).to_bytes())
    return srv


def test_a_door_that_answers_a_span_another_build_writes_costs_that_span_and_not_the_scan():
    """Reproduced (part 4): a door of another build answering `{"epoch": "e3"}` raised `int(sp["epoch"])` out of
    `recording_read`, outside the door's `try` — the scan worker moved no job (no `try` per job), and the good door's
    span beside it was lost too. The span is passed by and counted, the good spans stand, the door is named in
    `garbled` and the read is partial — the job waits rather than ending `done` without those minutes; an answer that is
    not an object is the door not answering; the scan's own progress file with a torn last line is read past it."""
    from vms.scan import DOOR_SPANS, ScanLog, plan, recording_read
    from tests.conftest import door, footage, store
    box = Box()
    t = box.wall()
    st = store("v-good")
    footage(st, "7", 1, t - 600, t - 300, step=10)
    good = door(box, st, "r-good")
    odd = _canned(box, "r-odd", {"spans": [{"epoch": "e3", "start": t - 200, "end": t - 100},
                                           {"epoch": 3, "start": t - 100, "end": t - 50, "bytes": 10}]})
    lists = _canned(box, "r-list", [{"epoch": 1}])
    try:
        got = recording_read(box.objects, "7", t - 3600, t, t)
        assert sorted((s.epoch, s.start, s.end) for s in got.spans) == [(1, t - 600, t - 300), (3, t - 100, t - 50)], got.spans
        assert got.garbled == ["r-odd"] and got.silent == ["r-list"] and got.partial
        assert DOOR_SPANS.counts.get("rec") == 1
    finally:
        good.shutdown(); odd.shutdown(); lists.shutdown()
    log = ScanLog(box.archive, "job-1")
    for s in plan(got.spans, t - 3600, t):
        log.append(s, events=1, at=t)
    with open(log.path, "a") as f:
        f.write('{"kind": "scan", "from": 17')                       # the half line a crash leaves
    assert len(log.read()) == 2 and log.events() == 2
    _forget_garbled()


def test_a_door_that_answers_a_span_another_build_writes_stops_no_keep_from_being_copied_or_checked():
    """The sibling the review named in `keep_pass`: `_speaks_for` read `int(sp["epoch"])` outside the door's `try`, and one
    such door stopped the copying and the checking of every keep — `archive.keep.lost` never raised. The span is passed
    by; the door shows and speaks for less, and what it would have covered stays short — the side a keep errs on."""
    from tests.test_keeps import _keep, _site
    box, k = _site()
    t = box.wall()
    from tests.conftest import footage
    footage(box.src, "7", 1, t - 1200, t - 600, step=10)
    odd = _canned(box, "r-odd", {"spans": [{"epoch": "e3", "start": t - 3000, "end": t - 2500}]})
    try:
        kp = _keep(box, "7", t - 1100, t - 700)
        late = _keep(box, "7", t - 2900, t - 2600)                    # only the odd door "has" it, in a span nobody can read
        state = k.keep_pass()
        assert state[kp.id]["copied"] == 400 and state[kp.id]["missing"] == 0, state
        assert state[late.id]["copied"] == 0 and state[late.id]["missing"] == 300, state
    finally:
        odd.shutdown(); box.src_door.shutdown()
    _forget_garbled()


def test_a_doors_held_since_is_laid_on_this_recorders_clock_by_the_doors_own_now():
    """Part 2, a minor: `held_since` is the door's wall clock. A new holder 1200 s behind said it held the recording 1200 s
    before it did and spoke for minutes it never had — the shortfall halved. The door says its `now` beside it, and the
    age `now - held_since` is laid on this recorder's clock; a door of an older build without `now` is taken as it is."""
    from tests.test_keeps import _site
    box, k = _site(source=False)
    t = box.wall()
    lagging = _canned(box, "r-lag", {"spans": [], "held_since": t - 1200 - 600, "now": t - 1200})
    older = _canned(box, "r-old", {"spans": [], "held_since": t - 600})
    try:
        url = lambda n: Heartbeat.from_bytes(box.objects.get(REC_SPEC.sub.heartbeat_key(n))).extra["archive_url"]
        _, held = k._door_timeline(url("r-lag"), "7", t - 3600, t)
        assert t - 601 <= held <= t - 599, held - t                    # it took the epoch 600 s ago, by anybody's clock
        assert k._door_timeline(url("r-old"), "7", t - 3600, t)[1] == t - 600
    finally:
        lagging.shutdown(); older.shutdown()
    from tests.conftest import door, store
    st = store("v-now")
    srv = door(box, st, "r-now", held={"7": t - 60})
    try:
        import urllib.request
        with urllib.request.urlopen(f"{url('r-now')}/timeline/7?from=0&to={t}") as r:
            body = json.loads(r.read())
        assert body["held_since"] == t - 60 and body["now"] == box.wall()   # the door says the clock it is on
    finally:
        srv.shutdown()


def test_a_garbled_keep_holds_its_camera_as_far_as_it_reads_and_nothing_of_the_units_of_no_camera():
    """Reproduced (part 4): any field that did not parse — even `at`, when the keep was set — made the keep its camera
    whole, from 0 to infinity, and every unit of no one camera (a scenario on any camera) whole too: 10 buckets removed
    where a sound keep let 37 go. Now `at` is metadata, read as not said; a bound that parses is kept and the lost one is
    open on its side; such a keep holds its camera's buckets and nothing of the units of no camera — those are held by
    the keeps that read."""
    from w2cplatform.events import EventLog, bucket_names_under
    from vms.resource import vms_resource
    box = Box()
    res = vms_resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    now = box.wall()
    day = lambda d: now - d * 86400
    for d in (40, 35, 32):
        for cam in ("7", "8"):
            EventLog(box.archive, "vms", cam, 1).append(day(d), "motion")
        EventLog(box.archive, "auto", "any-door", 1).append(day(d), "fired")
    for unit in ("vms/retention/7", "vms/retention/8", "auto/retention/any-door"):
        box.vars.put(unit, {"days": "30"})
    box.vars.put("auto/scenarios/any-door", {"name": "any-door", "when": json.dumps([{"sub": "vms", "kind": "io.input"}]),
                                             "then": "[]"})
    box.vars.put(keeps.key("7-a"), {"cam": "7", "from": str(day(36)), "to": str(day(34)), "at": "yesterday"})   # sound but for `at`
    box.vars.put(keeps.key("8-b"), {"cam": "8", "from": str(day(33)), "to": "later"})                          # its end lost
    res.retain()
    left = lambda sub, unit: sorted(round((now - b.start) / 86400) for b in bucket_names_under(box.archive, sub, unit, 600))
    assert left("vms", "7") == [35]                                    # its interval, and no more
    assert left("vms", "8") == [32]                                    # from its start on: 40 and 35 go
    assert left("auto", "any-door") == [35]                            # held by the keep that reads, not by the open one
    garbled: list = []
    keeps.declared(box.vars, garbled)
    [k8] = garbled
    assert k8.since == day(33) and k8.until == float("inf") and k8.garbled
    assert keeps.KEEPS.counts.get("rec") == 1 and [k.id for k in keeps.declared(box.vars)] == ["7-a"]
    _forget_garbled()


def test_one_resource_answering_another_shape_costs_its_window_and_not_the_merge():
    """The sibling of the peers' doors in the merge of `/events`: `rep.get`, `rep["events"]`, `e["server"]` were read
    after the fan-out's `try`, and one resource answering a list — or a line without `t` — raised out of `query` for
    automation and every console. That resource is "did not answer"; a line it cannot order is passed by, counted."""
    from w2cplatform.eventdatabase import MergedIndex, PEER_EVENTS
    box = Box()
    t = box.wall()
    for s in ("srv-a", "srv-b", "srv-c"):
        box.objects.put(f"platform/resources/{s}/heartbeat", json.dumps({"server": s, "ts": t, "url": f"http://{s}"}).encode())
    line = {"t": t - 5, "server": "srv-c", "kind": "motion", "unit": "7", "subsystem": "vms", "epoch": 1, "id": "c-1"}
    answers = {"http://srv-a": [1, 2], "http://srv-b": {"events": [{"t": "then", "server": "srv-b"}, {**line, "server": "srv-b", "id": "b-1"}]},
               "http://srv-c": {"events": [line], "state": "live"}}
    got = MergedIndex(box.objects, fetch=lambda url, params: answers[url], wall=box.wall).query(t - 60, t)
    assert [e["id"] for e in got["events"]] == ["b-1", "c-1"] and got["incomplete"] == {"srv-a": "did not answer"}, got
    assert PEER_EVENTS.counts.get("platform") == 1
    _forget_garbled()


# -- the ninth pass: restore, a torn unit row, the peer client's framing ---------------------------------------------

def _peer_heartbeat(box, peer: str, ts: float, held: int) -> None:
    box.objects.put(f"platform/resources/{peer}/heartbeat", json.dumps(
        {"server": peer, "ts": ts, "url": f"http://{peer}", "mirrors": {"srv-1": held}}).encode())


def test_a_restore_that_met_no_live_peer_or_raised_whole_is_asked_again_and_a_late_peer_is_asked():
    """Reproduced (the review's ninth pass, major): the server up before its peers after a power cut — `restore` found no
    live peer, left nothing known, and `restore_due` was never true: 0 of 20 buckets back, `restore_left` 0. And the store
    away at the start: `restore` raised whole, the same. Now it is due, with its doubling pause, until one try ran through
    with a live peer; while it has not, `left` is -1 (not known) and `done` false in the heartbeat and on `/metrics`. A
    peer that comes up after the restore was done, with copies the first peer did not have, is asked when it is seen —
    and the peer that gave everything is not asked again."""
    from w2cplatform.console import SpecConsole
    from w2cplatform.resource import RESTORE_RETRY, RESTORE_RETRY_MAX, Resource
    from tests.test_lesson4_worker import _box_with_cameras
    box, ctl = _box_with_cameras(1)
    paths = [f"vms/7/e1/{i:02d}.events.jsonl" for i in range(20)]
    east, west = _Peer(paths[:10]), _Peer(paths[10:])
    peers = {"http://srv-2": east, "http://srv-3": west}

    class Peers:
        def mirrored(self, url, server):
            return peers[url].mirrored(url, server)

        def get(self, url, server, path):
            return peers[url].get(url, server, path)

    res = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, clock=box.clock, peers=Peers())
    for peer in ("srv-2", "srv-3"):                                     # the power cut: both said a heartbeat an hour ago
        _peer_heartbeat(box, peer, box.wall() - 3600, 10)
    res.heartbeat()
    assert res.restore() == {"pulled": 0}
    hb = res.heartbeat()
    assert hb["restore"]["done"] is False and hb["restore"]["left"] == -1, hb["restore"]
    assert 'vms_resource_restore_left{server="srv-1"} -1' in SpecConsole(ctl, wall=box.wall).metrics_text()
    assert not res.restore_due()
    box.clock.advance(RESTORE_RETRY)
    assert res.restore_due() and res.restore() == {"pulled": 0}         # still nobody: asked, and the pause doubles
    box.clock.advance(RESTORE_RETRY)
    assert not res.restore_due()
    box.clock.advance(RESTORE_RETRY)
    assert res.restore_due()
    _peer_heartbeat(box, "srv-2", box.wall(), 10)                       # east is up; west still is not
    assert res.restore()["pulled"] == 10
    assert not res.restore_due() and "restore" not in res.heartbeat()   # done: nothing failed, nothing left
    _peer_heartbeat(box, "srv-3", box.wall(), 10)                       # west comes up later, with the other ten
    box.clock.advance(RESTORE_RETRY_MAX)
    _peer_heartbeat(box, "srv-2", box.wall(), 10)
    _peer_heartbeat(box, "srv-3", box.wall(), 10)
    assert res.restore_due()
    assert res.restore()["pulled"] == 10
    assert all(east.asked.count(p) == 1 for p in paths[:10]) and len(east.asked) == 10   # east was not asked again
    assert sum(1 for _ in __import__("os").scandir(f"{box.archive}/vms/7/e1")) == 20
    box.clock.advance(RESTORE_RETRY_MAX)
    _peer_heartbeat(box, "srv-2", box.wall(), 10)
    _peer_heartbeat(box, "srv-3", box.wall(), 10)
    assert not res.restore_due()                                         # both gave everything: nobody to ask

    # The store away at the start, with a new disk: the restore raises whole — and is due again after its pause.
    box2, _ = _box_with_cameras(1)

    class Away:
        def __init__(self, objects):
            self.objects, self.away = objects, True

        def list(self, prefix):
            if self.away:
                raise OSError("the store does not answer")
            return self.objects.list(prefix)

        def get(self, key):
            return self.objects.get(key)

        def put(self, key, data):
            return self.objects.put(key, data)

    store = Away(box2.objects)
    res2 = Resource(box2.archive, "srv-1", "http://srv-1", box2.vars, store, wall=box2.wall, clock=box2.clock, peers=Peers())
    east.asked.clear()
    try:
        res2.restore()
        raise AssertionError("a store that does not answer was read as nobody to ask")
    except OSError:
        pass
    assert not res2.restore_due()
    box2.clock.advance(RESTORE_RETRY)
    assert res2.restore_due()
    store.away = False
    _peer_heartbeat(box2, "srv-2", box2.wall(), 10)
    assert res2.restore()["pulled"] == 10 and not res2.restore_due()
    _forget_garbled()


def test_one_server_alone_is_restored_once_and_not_asked_again_for_ever():
    """The other side of the same rule: a server no other resource ever said a heartbeat beside has nobody to hold its
    copies — its restore is done at the first try, not due every ten minutes for the life of the box."""
    from w2cplatform.resource import RESTORE_RETRY_MAX, Resource
    box = Box()
    res = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, clock=box.clock)
    res.heartbeat()
    assert res.restore() == {"pulled": 0} and "restore" not in res.heartbeat()
    box.clock.advance(RESTORE_RETRY_MAX)
    assert not res.restore_due()


def test_the_restores_pause_does_not_overflow_after_a_thousand_tries():
    """The review's ninth pass, minor: `RESTORE_RETRY * 2 ** tries` is past a float at 1024 tries, and the
    `OverflowError` came before the pause was set — from then on a restore every ten seconds with a trace. The exponent
    is capped: the pause stays `RESTORE_RETRY_MAX`."""
    from w2cplatform.resource import RESTORE_RETRY_MAX, Resource
    box = Box()

    class Dead:
        def mirrored(self, url, server):
            raise OSError("503")

    res = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, clock=box.clock, peers=Dead())
    _peer_heartbeat(box, "srv-2", box.wall(), 3)
    res._restore_tries = 2000
    assert res.restore()["peers_failed"] == ["srv-2"]
    assert res.restore_said()["next_in"] == RESTORE_RETRY_MAX and not res.restore_due()
    _forget_garbled()


def test_one_torn_unit_row_stops_no_retain_and_its_unit_is_held_by_every_keep_that_reads():
    """Reproduced (the review's ninth pass, major): a row that is not JSON in `det/units/55`, `auto/scenarios/s1` or
    `rec/recordings/r9` raised out of `kept_buckets` — `removed=None` and every unit of the server kept, every pass, and
    `rows_garbled` did not count it. Now each row is read alone: the others are swept by their days, the torn row is
    counted once (`unit_rows_garbled`), and its unit is a unit of no one camera — held where a keep that reads holds,
    and swept outside it."""
    import os
    from w2cplatform.events import EventLog, bucket_names_under
    from vms.resource import UNIT_ROWS, vms_resource
    box = Box()
    res = vms_resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    old = box.wall() - 40 * 86400
    for sub, unit in (("vms", "7"), ("vms", "8"), ("det", "55"), ("auto", "s1"), ("rec", "r9")):
        EventLog(box.archive, sub, unit, 1).append(old, "motion")                     # inside the keep below
        EventLog(box.archive, sub, unit, 1).append(old - 86400, "motion")             # a day before it: nobody's keep
        box.vars.put(f"{sub}/retention/{unit}", {"days": "30"})
    box.vars.put(keeps.key(f"7-{int(old) - 60}-{int(old) + 60}"), {"cam": "7", "from": old - 60, "to": old + 60})
    for path in ("det/units/55", "auto/scenarios/s1", "rec/recordings/r9"):
        box.vars.put(path, {"name": "x"})
        with open(box.vars._file(path), "w") as f:
            f.write('{"items": {"cam": "7", ')                                            # torn mid-write
    for _ in range(2):
        out = res.pass_()
        assert "errors" not in out, out
    assert bucket_names_under(box.archive, "vms", "8", 600) == []                      # swept by its days
    assert len(bucket_names_under(box.archive, "vms", "7", 600)) == 1                  # the kept minutes, and only them
    for sub, unit in (("det", "55"), ("auto", "s1"), ("rec", "r9")):
        left = bucket_names_under(box.archive, sub, unit, 600)
        assert len(left) == 1 and left[0].start <= old < left[0].end, (sub, unit, left)   # held as ANY, the rest swept
    assert UNIT_ROWS.counts == {"det": 1, "auto": 1, "rec": 1}, UNIT_ROWS.counts      # once each, not once per read
    assert res.heartbeat()["rows_garbled"]["unit_row"] == 3
    os.remove(box.vars._file("det/units/55"))
    _forget_garbled()


def test_the_peer_client_takes_no_answer_without_a_frame_and_no_length_that_is_not_a_number():
    """The review's ninth pass, minor: an answer with neither a length nor chunks ends where the connection ends — a
    peer's door that died half way gave a shorter bucket, written for good; `Content-Length: ten` raised a bare
    `ValueError` after the body was written. Both are an `IOError` now, and nothing is kept of them; a framed answer
    that is whole is still a bucket. The sibling the review did not name: a peer's listing was read the same way — and
    `restore` now takes a peer that gave all it listed for done."""
    import io
    import socket
    import threading
    from w2cplatform.events import Bucket
    from w2cplatform.resource import PeerClient

    answers = {"/events/.mirror/srv-1/vms/7/e1/close.events.jsonl": b"HTTP/1.0 200 OK\r\n\r\n{\"t\": 1}\n",
               "/events/.mirror/srv-1/vms/7/e1/ten.events.jsonl": b"HTTP/1.1 200 OK\r\nContent-Length: ten\r\nConnection: close\r\n\r\n{\"t\": 1}\n",
               "/events/.mirror/srv-1/vms/7/e1/whole.events.jsonl": b"HTTP/1.1 200 OK\r\nContent-Length: 9\r\nConnection: close\r\n\r\n{\"t\": 1}\n",
               "/mirrored/srv-1": b"HTTP/1.0 200 OK\r\n\r\n" + Bucket("vms", "7", 1, 0.0, 600.0, "vms/7/e1/a.events.jsonl", 1).line().encode() + b"\n"}
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)

    def serve():
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            with c:
                path = c.recv(65536).split(b" ")[1].decode()
                c.sendall(answers[path])

    threading.Thread(target=serve, daemon=True).start()
    url = f"http://127.0.0.1:{srv.getsockname()[1]}"
    try:
        for name in ("close", "ten"):
            dest = io.BytesIO()
            try:
                PeerClient().get_into(url, "srv-1", f"vms/7/e1/{name}.events.jsonl", dest)
                raise AssertionError(f"{name}: an answer whose end cannot be told was taken for a bucket")
            except IOError as e:
                assert "neither chunks nor a length" in str(e), (name, e)
            assert dest.getvalue() == b"", name                                        # not a byte of it written
        dest = io.BytesIO()
        assert PeerClient().get_into(url, "srv-1", "vms/7/e1/whole.events.jsonl", dest) == 9
        assert dest.getvalue() == b'{"t": 1}\n'
        try:                                         # …and a listing: one cut short is not a peer that holds less (`_whole`)
            PeerClient().mirrored(url, "srv-1")
            raise AssertionError("a listing whose end cannot be told was taken whole")
        except IOError as e:
            assert "neither chunks nor a length" in str(e), e
    finally:
        srv.close()


def test_a_line_whose_values_only_convert_is_merged_as_converted_and_stops_no_timeline():
    """The `/events` sweep (the scaling pass after the eighth review): a line was checked to convert and kept as it came,
    so `"t": "1700000000"` beside numbers raised `TypeError` from the merge's sort — no reply to any timeline — and a list
    for `unit` or `id` raised in the sets that fence and dedupe. The line is merged as the types it was checked to be."""
    from w2cplatform.eventdatabase import MergedIndex
    box = Box()
    t = box.wall()
    for s in ("srv-a", "srv-b"):
        box.objects.put(f"platform/resources/{s}/heartbeat", json.dumps({"server": s, "ts": t, "url": f"http://{s}"}).encode())
    ours = {"t": t - 5, "server": "srv-a", "kind": "motion", "unit": "7", "subsystem": "vms", "epoch": 1, "id": "a-1"}
    odd = {"t": str(t - 9), "server": "srv-b", "kind": "motion", "unit": ["7"], "subsystem": "vms", "epoch": "2",
           "id": ["b", 1]}
    copy = {"t": str(t - 7), "server": "srv-c", "kind": "motion", "unit": "7", "subsystem": "vms", "epoch": 1, "bucket": [1]}
    answers = {"http://srv-a": {"events": [ours]}, "http://srv-b": {"events": [odd, copy]}}
    got = MergedIndex(box.objects, fetch=lambda url, params: answers[url], wall=box.wall).query(
        t - 60, t, current_epochs={("vms", "7"): 1})
    assert [e["t"] for e in got["events"]] == [t - 9, t - 7, t - 5], got
    assert got["events"][0]["epoch"] == 2 and got["events"][0]["id"] == "['b', 1]" and not got["events"][0]["fenced"]
    _forget_garbled()
