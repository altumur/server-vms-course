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
