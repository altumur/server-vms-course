"""The request family after the fifteenth review (`РЕВЬЮ-SERVERVMS-15.md`), each test a finding's scenario and the
probe that found it (`РЕВЬЮ-SERVERVMS-15/probes/`):

    major 2    the same `rid` filed again after its row was cleared is answered by its MARK, not performed again
               (ADR-0054): a mark stands until the request could no longer be performed — its deadline, or, with none,
               its end, plus the reaper's margin (`REAP_AFTER`, the family's `ttl` when longer); the family's door
               (`requests.file`) answers a spent id 200 `answered` with the mark's words, nothing written, no place
               counted; another request under it 409 `spent`; the VMS's jobs read the mark before they perform
               (rerun of the fourteenth's `p_r14_filings_course.py`, «refile after clear»)
    major 4    `jobs._ask_recorder` files by the family's rules, `requests.file_as` (the product's `p.FileAs`): the
               schema's keys (no `cam` in the body), the spec's stamps `[by, at, about]`, create-only, the spec's
               journal line, no person's ledger (`p4_jobs_filing.py`; ГРАНИЦА §3 row 3, ADR-0013, ADR-0012)
    minor 5    the resource's `free-<server>-<volume>` is not answered into `fetched`: the console's clearing leaves the
               resource's row, and `freeing` is said while it stands, no longer (`p3_free_request_fetched.py`; ADR-0059)
    minor 7    `requests.elsewhere` rows (`record`, `detect`, `scan`) end with their outcome in `<sub>/commands/<id>`,
               `ended_by: jobs`, before the row goes; a recorder's look sweeps them past their bound (ADR-0054)
"""
import json
import tempfile

from tests.conftest import Box, Served, controller, testsub2
from tests.test_holder_requests import _holder, _look
from w2cplatform import requests
from w2cplatform.canonical import canonical_json
from w2cplatform.console import SpecConsole
from w2cplatform.spec import SpecController


def _mark(box, sub, rid):
    raw = box.objects.get(f"{sub}/commands/{rid}")
    return json.loads(raw) if raw is not None else None


# -- major 2: how long a mark stands ----------------------------------------------------------------------------------
def test_a_mark_without_a_deadline_stands_its_end_plus_the_reapers_margin_and_one_with_one_its_deadline_plus_it():
    with_deadline = canonical_json({"valid_until": 2000.0, "at": 1000.0, "ended_at": 1500.0, "outcome": "performed"})
    assert requests.mark_kept_until(with_deadline, None) == 2000.0 + requests.REAP_AFTER
    assert requests.mark_kept_until(with_deadline, 3600) == 2000.0 + 3600
    # a family that ends its rows by `ttl` gives none: the mark went with its row, and the id was a fresh one at once
    no_deadline = canonical_json({"at": 1000.0, "ended_at": 1500.0, "outcome": "performed"})
    assert requests.mark_kept_until(no_deadline, 86400) == 1500.0 + 86400
    assert requests.mark_kept_until(canonical_json({"at": 1000.0}), None) == 1000.0 + requests.REAP_AFTER   # begun
    assert requests.mark_kept_until(b"{torn", 3600) is None                       # names nothing: with its row, as before
    assert requests.mark_kept_until(canonical_json({"outcome": "refused"}), 3600) is None


def test_a_holder_keeps_a_mark_without_a_deadline_past_its_row_until_its_end_plus_ttl():
    """The holder's sweep (`Worker.sweep_marks`) of a mark with no `valid_until`: it went the moment its row did."""
    box, spec = Box(), testsub2()
    w = _holder(box, spec, ["c1"])
    key = spec.sub.command_key("asked-1")
    box.objects.put(key, canonical_json({"instance": "x", "slot": "w-9", "unit": "c1", "outcome": "performed",
                                         "at": box.wall(), "ended_at": box.wall()}).encode())
    box.clock.advance(w.MARK_SWEEP + 1)
    assert w.sweep_marks() == 0 and box.objects.get(key) is not None             # its row is gone: the mark stays
    box.wall.advance(spec.requests["ttl"] + 1)
    box.clock.advance(w.MARK_SWEEP + 1)
    w._marks_kept.clear()
    assert w.sweep_marks() == 1 and box.objects.get(key) is None                 # past its end and `ttl`: swept


# -- major 2: the door answers a spent id by its mark -----------------------------------------------------------------
def test_the_same_request_at_the_door_after_its_row_was_cleared_is_answered_by_its_mark_not_performed_again():
    """`POST /requests` with a new Idempotency-Key, after the holder performed it and the console cleared the row: 200
    `answered` with the mark's outcome — nothing written, no place in the person's ledger, no second call. Another
    request under the spent id (another unit): 409 `spent`."""
    box, spec = Box(), testsub2()
    ctl = controller(box, spec=spec)
    for t in ("t1", "t2"):
        ctl.create({"name": t, "of": "c1"})
    w = _holder(box, spec, ["t1"])
    with Served(SpecConsole(ctl, wall=box.wall)) as call:
        a = call("POST", "/requests", {"unit": "testsub2/t1", "add": 2}, headers={"X-User": "anna"})
        assert a[0] == 202 and a[1]["queued"]["id"] == "t1-2", a
        assert [d.get("added") for d in _look(w, 1)] == [2] and len(w.calls) == 1
        w.heartbeat_once()
        requests.clear_requests(SpecController(spec, box.vars, box.objects, wall=box.wall), sweep=False)
        assert box.vars.get(spec.sub.request_key("t1-2"))[0] is None              # answered and cleared
        ledger = json.loads(box.vars.get(spec.sub.asked_key("anna"))[0]["asks"])
        box.wall.advance(spec.requests["settle"] + 1)
        b = call("POST", "/requests", {"unit": "testsub2/t1", "add": 2}, headers={"X-User": "anna"})
        assert b[0] == 200 and b[1]["answered"]["outcome"] == "performed" and b[1]["answered"]["id"] == "t1-2", b
        assert box.vars.get(spec.sub.request_key("t1-2"))[0] is None              # nothing written…
        assert json.loads(box.vars.get(spec.sub.asked_key("anna"))[0]["asks"]) == ledger   # …no place counted
        assert w.requests() == [] and len(w.calls) == 1                           # …and nothing performed again
        c = call("POST", "/requests", {"unit": "testsub2/t1", "add": 2}, headers={"X-User": "boris"})
        assert c[0] == 200 and c[1]["answered"]["outcome"] == "performed", c      # the same request, whoever asks it
    # another request under a spent id: a mark that says another unit
    box.objects.put(spec.sub.command_key("t2-5"), canonical_json(
        {"unit": "t1", "outcome": "refused", "at": box.wall(), "ended_at": box.wall(), "error": "no"}).encode())
    with Served(SpecConsole(ctl, wall=box.wall)) as call:
        d = call("POST", "/requests", {"unit": "testsub2/t2", "add": 5}, headers={"X-User": "anna"})
        assert d[0] == 409 and d[1]["error"] == "spent", d
    assert box.vars.get(spec.sub.request_key("t2-5"))[0] is None


def test_a_spent_id_whose_mark_the_store_does_not_hand_over_is_503_and_nothing_is_filed():
    box, spec = Box(), testsub2()
    ctl = controller(box, spec=spec)
    ctl.create({"name": "t1", "of": "c1"})

    class Away:
        def __init__(self, inner):
            self.inner = inner

        def get(self, key):
            if "/commands/" in key:
                raise OSError("the store is away")
            return self.inner.get(key)

        def __getattr__(self, name):
            return getattr(self.inner, name)

    away = SpecController(spec, box.vars, Away(box.objects), wall=box.wall)
    try:
        requests.file(away, {"unit": "testsub2/t1", "add": 1}, "anna")
        raise AssertionError("filed with its mark not read")
    except OSError:
        pass                                                                       # the door says 503 (`_failed`)
    assert box.vars.get(spec.sub.request_key("t1-1"))[0] is None


# -- major 2 and minor 7: the VMS's jobs ------------------------------------------------------------------------------
def _rec_console(box):
    from vms.config import REC_SPEC
    return SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)


def test_a_record_request_ends_in_its_mark_and_filed_again_after_its_row_went_is_not_performed_twice():
    """The fifteenth review, minor 7 and major 2: `record_on_request` deleted the row and wrote no outcome anywhere; the
    evaluator that moved filed the same id again and the recording was extended a second time. Now the outcome is in
    `rec/commands/<id>` (`ended_by: jobs`) before the row goes; `Worker.file_request` meets the mark (`False`, counted
    `again`), and a row that stands under the id all the same is answered by the mark — not performed."""
    from vms.config import AUTO_SPEC, REC_SPEC
    from vms.jobs import record_on_request
    box = Box()
    rec = _rec_console(box)
    now = box.wall()
    # the scenario evaluator's filing, as `AutoWorker` files it (its spec names `rec` in `worker.requests`)
    from w2cplatform.worker import Worker

    class Auto(Worker):
        def reconcile_once(self, now=None):
            return []
    auto = Auto(AUTO_SPEC.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, spec=AUTO_SPEC,
                resource_root=box.resource_root)
    auto.claim_slot("a-1")
    row = {"action": "record", "cam": "7", "minutes": 10, "valid_until": now + 30}
    assert auto.file_request("rec", "door-1-0", row, unit="door", at=now) is True
    assert record_on_request(rec, now) == 1 and rec.unit("7-auto")["until"] == now + 600
    assert box.vars.get(REC_SPEC.sub.request_key("door-1-0"))[0] is None          # the row went…
    m = _mark(box, "rec", "door-1-0")
    assert m["outcome"] == "performed" and m["ended_by"] == "jobs" and m["action"] == "record", m   # …its outcome stays
    assert m["valid_until"] == now + 30 and m["digest"]
    # the same id filed again, a minute later: the mark answers it
    box.wall.advance(60)
    assert auto.file_request("rec", "door-1-0", dict(row), unit="door", at=now) is False
    assert auto.filings["again"] == 1 and box.vars.get(REC_SPEC.sub.request_key("door-1-0"))[0] is None
    # a row under the spent id that stands all the same (put by hand): answered by the mark, the recording not extended
    box.vars.put(REC_SPEC.sub.request_key("door-1-0"), {"action": "record", "cam": "7", "minutes": "10",
                                                        "valid_until": str(box.wall() + 30)})
    assert record_on_request(rec, box.wall()) == 0 and rec.unit("7-auto")["until"] == now + 600
    assert box.vars.get(REC_SPEC.sub.request_key("door-1-0"))[0] is None


def test_a_refused_and_an_expired_record_end_in_their_marks_with_their_reasons():
    from vms.jobs import record_on_request
    box = Box()
    rec = _rec_console(box)
    now = box.wall()
    box.vars.put("rec/requests/late", {"action": "record", "cam": "7", "minutes": "10", "valid_until": str(now - 1)})
    box.vars.put("rec/requests/nothing", {"action": "record", "cam": "7", "minutes": "0", "valid_until": str(now + 30)})
    box.vars.put("rec/requests/word", {"action": "record", "cam": "7", "minutes": "ten", "valid_until": str(now + 30)})
    assert record_on_request(rec, now) == 0 and box.vars.list("rec/requests/") == []
    assert _mark(box, "rec", "late")["outcome"] == "expired"
    assert _mark(box, "rec", "nothing")["outcome"] == "refused" and "nothing" in _mark(box, "rec", "nothing")["error"]
    assert _mark(box, "rec", "word")["outcome"] == "refused" and "read" in _mark(box, "rec", "word")["error"]


def test_a_record_whose_mark_the_store_does_not_take_keeps_its_row_for_the_next_turn():
    from vms.jobs import record_on_request
    box = Box()
    real = box.objects.put_new
    box.objects.put_new = lambda *a, **kw: (_ for _ in ()).throw(OSError("the store is away"))
    rec = _rec_console(box)
    now = box.wall()
    box.vars.put("rec/requests/r-1", {"action": "record", "cam": "7", "minutes": "10", "valid_until": str(now + 30)})
    record_on_request(rec, now)
    assert box.vars.get("rec/requests/r-1")[0] is not None                        # no outcome anywhere: it stays
    box.objects.put_new = real
    record_on_request(rec, now + 1)
    assert box.vars.get("rec/requests/r-1")[0] is None and _mark(box, "rec", "r-1")["outcome"] == "performed"


def test_detect_and_scan_end_in_their_marks_and_a_spent_id_is_not_turned_into_work_again():
    from tests.test_det_requests import _ask, _site
    from vms.jobs import detect_on_request
    box = Box(); det, job, rec = _site(box)
    _ask(box, "f1-0", action="detect", cam="7", kind="lpr", minutes=10)
    _ask(box, "f1-1", action="scan", cam="7", kind="lpr", before=60, after=0, at=box.wall() - 600)
    _ask(box, "f1-2", action="dance", cam="7", kind="lpr")
    assert detect_on_request(det, job, rec, box.wall()) == 2
    assert [_mark(box, "det", r)["outcome"] for r in ("f1-0", "f1-1", "f1-2")] == ["performed", "performed", "refused"]
    assert all(_mark(box, "det", r)["ended_by"] == "jobs" for r in ("f1-0", "f1-1", "f1-2"))
    until = det.unit("7-lpr-auto")["until"]
    jobs_made = len(job.units())
    box.wall.advance(30)
    _ask(box, "f1-0", action="detect", cam="7", kind="lpr", minutes=10)           # the same id, filed again
    _ask(box, "f1-1", action="scan", cam="7", kind="lpr", before=60, after=0, at=box.wall() - 900)
    assert detect_on_request(det, job, rec, box.wall()) == 0
    assert det.unit("7-lpr-auto")["until"] == until and len(job.units()) == jobs_made
    assert box.vars.list("det/requests/") == []


def test_the_recorders_look_sweeps_the_marks_the_jobs_leave_once_past_their_bound():
    """`vms jobs` writes marks with the console's grant and never deletes one (ADR-0054); the recorder's look — its own
    `requests`, not the base's — sweeps them (`Worker.sweep_marks`) past the deadline and the family's `ttl`."""
    from tests.vmsconftest import recorder
    from vms.config import REC_SPEC
    from vms.jobs import record_on_request
    box = Box()
    rec = _rec_console(box)
    now = box.wall()
    box.vars.put("rec/requests/r-1", {"action": "record", "cam": "7", "minutes": "10", "valid_until": str(now + 30)})
    record_on_request(rec, now)
    r = recorder(box)
    r.requests(now=box.wall())
    assert _mark(box, "rec", "r-1") is not None                                   # within its bound: it stands
    box.wall.advance(30 + REC_SPEC.requests["ttl"] + 1)
    box.clock.advance(r.MARK_SWEEP + 1)
    r.requests(now=box.wall())
    assert _mark(box, "rec", "r-1") is None


# -- major 4: jobs file through the family's door ---------------------------------------------------------------------
def test_jobs_ask_the_recorder_by_the_familys_rules_schema_stamps_journal():
    """`p4_jobs_filing.py`: the row carried `cam` (the schema: «the request has no key 'cam' — it takes from, to,
    unit»), `[at, by]` where the spec stamps `[by, at, about]`, no journal line. Now `requests.file_as` — the product's
    `p.FileAs`: the family's rules, create-only, the journal line, and no person's ledger (a process files what a
    worker's report told it to)."""
    from vms import jobs
    from vms.config import REC_SPEC
    from w2cplatform.schema import check
    box = Box()
    rec = _rec_console(box)
    rec.create({"name": "7", "cam": "7"})
    said = []

    class Journal:
        def say(self, kind, cls=None, **fields):
            said.append((kind, fields))
    now = box.wall()
    assert jobs._ask_recorder(rec, "7", now - 600, now - 540, now, "detjob/7-lpr-1-2", journal=Journal()) is True
    key = REC_SPEC.sub.request_key(f"7-{int(now - 600)}-{int(now - 540)}")
    row = box.vars.get(key)[0]
    body = {k: v for k, v in row.items() if k not in REC_SPEC.requests["stamp"] and k != REC_SPEC.about_field}
    check(REC_SPEC.requests["schema"], {**body, "from": float(body["from"]), "to": float(body["to"])}, "the request")
    assert sorted(set(row) - set(body)) == ["at", "by", "cam"] and row["by"] == "detjob/7-lpr-1-2", row
    assert row["cam"] == "7" and "valid_until" not in row                          # `about`, and no deadline `rec` lacks
    assert said == [("archive.backfill.asked", {"user": "detjob/7-lpr-1-2", "target": "rec/7", "sub": "rec",
                                                "request": key.rsplit("/", 1)[1], "from": row["from"], "to": row["to"]})]
    assert box.vars.list(REC_SPEC.sub.asked_prefix()) == []                       # no person's ledger: a process
    # asked again on the next turn: the row stands — one row, not a queue, and no second line
    assert jobs._ask_recorder(rec, "7", now - 600, now - 540, now + 30, "detjob/7-lpr-1-2", journal=Journal()) is False
    assert len(said) == 1
    # a recording that is not there: refused by the door, said in the log whole (the fifteenth review's p4 on a2550ea6
    # read a line that did not format: a probe's stale call put a word where `%.0f` stood), nothing filed
    import logging

    class Lines(logging.Handler):
        def __init__(self):
            super().__init__()
            self.got = []

        def emit(self, record):
            self.got.append(record.getMessage())              # raises here, in the test, if the arguments do not fit
    lines = Lines()
    jobs.log.addHandler(lines)
    try:
        assert jobs._ask_recorder(rec, "9", now - 600, now - 540, now, "detjob/9-x", journal=Journal()) is False
    finally:
        jobs.log.removeHandler(lines)
    assert len(lines.got) == 1 and lines.got[0].startswith(
        f"rec: asking the recorder for 9 [{now - 600:.0f}, {now - 540:.0f}) for detjob/9-x was refused: "), lines.got
    assert box.vars.get(REC_SPEC.sub.request_key(f"9-{int(now - 600)}-{int(now - 540)}"))[0] is None


def test_a_process_filing_meets_a_spent_ids_mark_and_a_different_request_under_a_taken_id_is_a_conflict():
    """`file_as` (the product's `FileAs`) reads the mark before the row, as the door does (major 2): the same request
    answered under its id is `filed` False and nothing written; another request under a spent or a taken id raises
    `Conflict`; what the family's rules refuse raises `Refused`."""
    from vms.config import REC_SPEC
    from w2cplatform.spec import Refused
    from w2cplatform.variables import Conflict
    box = Box()
    rec = _rec_console(box)
    rec.create({"name": "7", "cam": "7"})
    rec.create({"name": "8", "cam": "8"})
    box.objects.put(REC_SPEC.sub.command_key("7-100-200"), canonical_json(
        {"unit": "7", "outcome": "performed", "at": box.wall(), "ended_at": box.wall()}).encode())
    assert requests.file_as(rec, {"unit": "rec/7", "from": 100, "to": 200}, "detjob/j") == ("7-100-200", None, False)
    assert box.vars.list(REC_SPEC.sub.requests_prefix()) == []
    box.objects.put(REC_SPEC.sub.command_key("8-100-200"), canonical_json(
        {"unit": "7", "outcome": "performed", "at": box.wall(), "ended_at": box.wall()}).encode())
    for body, err in (({"unit": "rec/8", "from": 100, "to": 200}, Conflict), ({"unit": "rec/7", "from": "x", "to": 1}, Refused),
                      ({"unit": "rec/7", "cam": "7", "from": 1, "to": 2}, Refused)):
        try:
            requests.file_as(rec, body, "detjob/j")
            raise AssertionError(f"filed: {body}")
        except err:
            pass
    rid, row, filed = requests.file_as(rec, {"unit": "rec/7", "from": 300, "to": 400, "lost": True}, "console")
    assert filed and row["lost"] == "true" and row["by"] == "console" and rid == "7-300-400", row
    box.wall.advance(5)
    assert requests.file_as(rec, {"unit": "rec/7", "from": 300, "to": 400, "lost": True}, "console")[2] is False
    try:
        requests.file_as(rec, {"unit": "rec/7", "from": 300, "to": 400}, "console")   # not the lost one: another request
        raise AssertionError("another request under a taken id was filed")
    except Conflict:
        pass


def test_the_jobs_process_says_its_filings_in_its_own_journal():
    import inspect
    import vms.__main__ as m
    src = inspect.getsource(m.jobs)
    assert 'rec_ctl.journal = Journal(runtime.events_said(os.environ), "jobs"' in src
    import vms.jobs as j
    assert "vars.put(" not in inspect.getsource(j._ask_recorder) and "file_as(" in inspect.getsource(j._ask_recorder)


# -- minor 5: the resource's ask to free bytes ------------------------------------------------------------------------
def test_the_resources_free_row_is_not_answered_into_fetched_and_freeing_is_said_while_it_stands():
    """`p3_free_request_fetched.py`: the recorder put `free-srv-1-vol` into `fetched`, the console's clearing deleted the
    resource's row two seconds later, and `freeing[vol] = 0` was said for good. ADR-0059: the holder neither performs
    nor marks it; the row is the resource's to write and to take away."""
    import time
    from vms.config import REC_SPEC
    from vms.domainpart.device import Ram
    from vms.recworker import RecWorker
    from w2cplatform.cluster.variables import FakeVariables
    vars_, objects = FakeVariables(), Ram()
    rec = RecWorker("r-1", vars_, objects, wall=time.time, server="srv-1", resource_root=tempfile.mkdtemp(prefix="r15-"))
    rec.volume = "vol"

    class FakeStore:                                    # the volume open: `archive_busy()` is False
        writer = object()
        quota, block_bytes, too_large, lost, lock_lost, name = 0, 0, 0, False, False, "vol"
    rec.store = FakeStore()
    key = REC_SPEC.sub.request_key("free-srv-1-vol")
    vars_.put(key, {"free": "1000000", "volume": "vol", "server": "srv-1", "at": str(time.time())})
    vars_.put(REC_SPEC.sub.request_key("free-srv-2-vol"), {"free": "5", "volume": "vol", "server": "srv-2",
                                                            "at": str(time.time())})
    assert rec.requests() == [] and rec.fetched == [] and rec.freeing == {"vol": 0}
    rec.heartbeat_once()
    assert requests.clear_requests(SpecController(REC_SPEC, vars_, objects), sweep=False) == 0
    assert vars_.get(key)[0] is not None                                           # the resource's row stands
    vars_.delete(key)                                                              # under its mark: the resource takes it away
    rec.requests()
    assert rec.freeing == {}                                                       # …and nothing is said of it any more
