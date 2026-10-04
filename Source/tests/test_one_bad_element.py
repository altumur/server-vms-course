"""One bad element is that element's: not a whole route of the console, not a whole loop (the review's tenth pass, and the
routes the ninth answer named as failing whole).

A heartbeat whose `server` is a list, a camera whose `source` does not parse, a holder whose coverage is a word, a body
that is not a JSON object, a bucket line nested past what JSON reads, a row with `Infinity` in an integer field: each
raised out of a route or a loop over many, and everybody else's answer went with it. Each is proved here on the route or
the loop it took down, with the others answering beside it.
"""
import json
import os
import types
import urllib.error
import urllib.request

from w2cplatform.contract import GARBLED, Heartbeat, builds
from vms.config import REC_SPEC
from tests.conftest import Box
from tests.test_slot_fence import _forget_garbled

DEEP = "[" * 1_000_000 + "]" * 1_000_000                            # nested past what `json.loads` reads: `RecursionError`
BODY_DEEP = "[" * 400_000                                             # …and as deep as a body under `MAX_BODY` goes


def _hand_edit(box, path: str, field: str, number: str = "1e999") -> None:
    """A row's file as a hand edit leaves it: `field` a JSON number, not the string every write stores — `1e999` reads
    back as `inf`, and `int(inf)` is an `OverflowError`."""
    p = box.vars._file(path)
    with open(p) as f:
        d = json.load(f)
    d["items"][field] = "__number__"
    with open(p, "w") as f:
        f.write(json.dumps(d).replace('"__number__"', number))


def _raw(base, method, path, data: bytes, key="k"):
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", "Idempotency-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


# -- routes of the console: /servers, /unplaceable, /drain, /metrics, /schema, /domain -------------------------------

def test_a_heartbeat_whose_server_or_worker_is_no_name_is_that_heartbeats_and_no_route_falls():
    """Reproduced (the tenth pass, major): `"server": ["srv-x"]` in a worker's heartbeat was a `TypeError` out of
    `/servers`, `/unplaceable` and `/drain`; in a resource's, out of `/metrics` too (`resources_seen` keyed by it) and of
    `restore` and the mirror; a `5` among names raised in every `sorted`; a `worker` that is a list, the same. Now a
    heartbeat whose `worker` or `server` is not a non-empty string does not parse: skipped and counted as that
    heartbeat's, and every route answers with the others."""
    from w2cplatform.console import Mount, SpecConsole
    from w2cplatform.resource import resources_seen
    from tests.test_lesson4_worker import _box_with_cameras
    box, ctl = _box_with_cameras(3)
    t = box.wall()
    box.objects.put("vms/heartbeats/w-1", Heartbeat("w-1", t, [], {"server": "srv-a", "capacity": 50}).to_bytes())
    box.objects.put("platform/resources/srv-a/heartbeat", json.dumps({"server": "srv-a", "ts": t, "url": "http://a"}).encode())
    bad = {"vms/heartbeats/w-2": {"worker": "w-2", "ts": t, "status": [], "server": ["srv-x"]},
           "vms/heartbeats/w-3": {"worker": "w-3", "ts": t, "status": [], "server": 5},
           "vms/heartbeats/w-4": {"worker": ["w-4"], "ts": t, "status": [], "server": "srv-b"},
           "vms/heartbeats/w-5": {"worker": "w-5", "ts": t, "status": [], "server": ""},
           "platform/resources/srv-x/heartbeat": {"server": ["srv-x"], "ts": t, "url": "http://x"},
           "platform/resources/srv-y/heartbeat": {"server": 7, "ts": t, "url": "http://y"}}
    for k, v in bad.items():
        box.objects.put(k, json.dumps(v).encode())
    GARBLED.clear()
    con = SpecConsole(ctl, wall=box.wall)
    m = Mount(con)
    assert list(con.servers()["servers"]) == ["srv-a"]
    assert ctl.unplaceable() == []                                     # placed on w-1 by the pass below, or eligible there
    text = con.metrics_text()
    assert "w2c_resources_live 1" in text and 'vms_worker_headroom{worker="w-1",server="srv-a"}' in text
    assert GARBLED["vms"] >= 4 and GARBLED["platform"] >= 2                # counted as heartbeats that do not parse
    assert list(resources_seen(box.objects)) == ["srv-a"]
    ctl.pass_once()
    assert all(ctl.placement(i).worker == "w-1" for i in (1, 2, 3))   # placement went on past them
    ctl.drain("srv-a")
    status, rep = m.drain_route("GET", {})
    assert status == 200 and rep["subsystems"]["vms"]["workers"] == ["w-1"]
    _forget_garbled()


def test_schema_lists_a_process_whose_schema_does_not_read_and_raises_past_nobody():
    """`/schema` with `schema: 1e999` in a heartbeat skipped that process — and a process `/schema` does not list is not
    behind any version: the one raise that locks a live process out. A `build` that is a list was a `TypeError` out of
    the route (a set of builds), and a garbled `platform/schema` row the same. Now the process is listed with
    `schema: null`, `can_raise_to` stays where the store is, a raise is refused while it runs, the build reads `?`, and
    a garbled row is `version: null`."""
    from w2cplatform.console import Mount, SpecConsole
    from w2cplatform.contract import SchemaTooNew
    from tests.test_lesson4_worker import _box_with_cameras
    box, ctl = _box_with_cameras(1)
    t = box.wall()
    box.objects.put("vms/heartbeats/w-1", b'{"worker": "w-1", "ts": %f, "status": [], "server": "srv-a", "schema": 1e999, '
                                          b'"build": ["x"]}' % t)
    m = Mount(SpecConsole(ctl, wall=box.wall))
    status, rep = m.schema_route("GET", {})
    assert status == 200 and rep["processes"]["vms/w-1"]["schema"] is None and rep["builds"] == ["?"], rep
    assert rep["can_raise_to"] == 1 and rep["schema_unknown"] == ["vms/w-1"]
    try:
        ctl.set_schema(2)
        raise AssertionError("raised past a process whose schema nobody can read")
    except SchemaTooNew as e:
        assert "vms/w-1" in str(e)
    assert builds(box.objects, t)["vms/w-1"]["live"]
    box.vars.put("platform/schema", {"version": "two"})
    status, rep = m.schema_route("GET", {})
    assert status == 200 and rep["version"] is None


def test_a_domain_view_that_does_not_read_is_said_and_not_a_500():
    """`domain/view` torn, or a list, raised out of `/domain`; `ts: Infinity` made the view current for ever. Each is
    a 503 that says the view cannot be read, or — a time that is no time — the same."""
    from w2cplatform.console import domain_view
    box = Box()
    for raw in (b'{"ts": ', b"[1]", b'{"ts": Infinity}', DEEP.encode()):
        box.objects.put("domain/view", raw)
        status, rep = domain_view(box.objects, box.wall())
        assert status == 503 and "cannot be read" in rep["error"], (raw[:20], status, rep)
    box.objects.put("domain/view", json.dumps({"ts": box.wall() - 100, "members": {}}).encode())
    assert domain_view(box.objects, box.wall())[1]["silent"] is True


def test_a_source_that_does_not_parse_costs_its_camera_not_drain_unplaceable_or_the_catalogue():
    """`rtsp://[::1/x` — "Invalid IPv6 URL" from `urlsplit` — in one camera's row raised out of `device_of`, and so out of
    every walk of the cameras that groups them by device: `/drain` (`would_strand`), `/unplaceable`, and the scenario
    catalogue's every camera (`/auto/catalog`). The source is its own device now, as any source that is not an address;
    a camera whose device row cannot be read is offered with `can: null` and says why."""
    from w2cplatform.console import Mount, SpecConsole
    from vms.auto import Catalog
    from vms.config import device_of
    from tests.test_lesson4_worker import _box_with_cameras
    box, ctl = _box_with_cameras(2)
    t = box.wall()
    box.objects.put("vms/heartbeats/w-1", Heartbeat("w-1", t, [], {"server": "srv-a", "capacity": 50}).to_bytes())
    box.vars.put("vms/cameras/9", {"id": "9", "name": "x", "source": "rtsp://[::1/x", "revision": "1"})
    assert device_of("rtsp://[::1/x") == "rtsp://[::1/x"
    m = Mount(SpecConsole(ctl, wall=box.wall))
    assert isinstance(ctl.unplaceable(), list)
    ctl.drain("srv-a")
    status, rep = m.drain_route("GET", {})
    assert status == 200 and "9" in rep["subsystems"]["vms"]["would_strand"], rep
    cams = Catalog(box.vars).reply()["vms"]
    assert set(cams) == {"1", "2", "9"} and cams["9"]["can"] is None


# -- the VMS's routes: coverage, request bodies, query strings --------------------------------------------------------

def test_a_holders_coverage_that_is_a_word_costs_its_spans_and_not_the_timeline_or_the_segment():
    """`float(cov["from"])` bare in three routes (the ninth answer's open list): one holder announcing `{"from": "x"}`
    was no reply at all for the camera's `/timeline`, and for its `/segment`. The coverage is read once
    (`coverage_of`): one that does not read is a holder that announces none — no device spans, a segment held to the
    ceiling alone — counted once as that holder's field."""
    from w2cplatform.rows import FIELDS
    from vms.console import vms_routes
    from tests.test_lesson4_worker import _box_with_cameras
    box, ctl = _box_with_cameras(1)
    t = box.wall()
    box.objects.put("vms/heartbeats/w-1", Heartbeat("w-1", t, [
        {"id": 1, "phase": "running", "coverage": {"from": "x", "to": "y"}, "playback_url": "http://w-1/play/1"}],
        {"server": "srv-a"}).to_bytes())
    extra = vms_routes(media=True, ctl=ctl)
    h = types.SimpleNamespace(headers={}, client_address=("10.0.0.1", 0))
    assert extra(h, "GET", "/timeline/1", {"from": str(t - 60), "to": str(t)}) == (200, [])
    status, rep = extra(h, "GET", "/segment", {"unit": "vms/1", "from": str(t - 60), "to": str(t)})
    assert status == 200 and rep["playback"].startswith("http://w-1/play/1?"), rep
    assert "vms/heartbeats/w-1#coverage" in FIELDS.bad
    assert extra(h, "GET", "/timeline/1", {"from": "yesterday"})[0] == 400       # a word in the query: 400, not no reply
    _forget_garbled()


def test_a_body_that_is_no_json_object_is_refused_on_every_write_route():
    """A body that is not JSON, nested past what JSON reads, or a list: `POST /cameras` and `PUT /cameras/1` answered 500
    "the write failed", `PUT /policy`, `POST /requests` and `POST /backfill` no reply at all (the handler fell over),
    and a mark naming `cam: "seven"` was 500. Each is a 400 now, and nothing is written."""
    from tests.test_console_gate import _console
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    try:
        assert _raw(base, "POST", "/cameras", json.dumps({"source": "driverpack://file/1.mp4"}).encode(), "k0") == 201
        n = 0
        for method, path in (("POST", "/cameras"), ("PUT", "/cameras/1"), ("PUT", "/policy"), ("POST", "/requests"),
                             ("POST", "/backfill"), ("POST", "/marks")):
            for data in (b"{not json", BODY_DEEP.encode(), b"[1, 2]"):
                n += 1
                assert _raw(base, method, path, data, f"k{n}") == 400, (method, path, data[:12])
        assert _raw(base, "POST", "/marks", json.dumps({"cam": "seven"}).encode(), "km") == 400
        assert [r["id"] for r in ctl.units()] == [1]
        assert _raw(base, "GET", "/export/1?from=nan&to=60", None) == 400
    finally:
        srv.shutdown()


def test_a_body_that_is_no_json_object_is_refused_on_keeps_volumes_and_server_labels_and_an_offer_that_is_no_text_too():
    """The eleventh review, a minor: `POST /rec/keeps` and `POST /rec/volumes` (a body not JSON, or nested past what
    JSON reads) and `PUT /servers/<s>/labels` (nested) dropped the connection with no answer — they read the body bare,
    beside the routes the tenth round had closed. Through `object_body` now: 400, in words, nothing written. The sibling
    of the same class: an offer of a live view that is no text (bytes that are not UTF-8), at the console and at the
    gateway, was the same dropped connection; 400 now."""
    from tests.test_console_gate import _console
    from tests.test_lesson8_live import OFFER, _box as _live_box, _gateway
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    try:
        n = 0
        for method, path in (("POST", "/rec/keeps"), ("POST", "/rec/volumes"), ("PUT", "/servers/srv-1/labels")):
            for data in (b"{not json", BODY_DEEP.encode(), b"[1, 2]"):
                n += 1
                assert _raw(base, method, path, data, f"k{n}") == 400, (method, path, data[:12])
        assert box.vars.list("rec/keeps/") == [] and box.vars.list("rec/volumes/") == []
    finally:
        srv.shutdown()
    box, ctl, live_ctl, w, srv, base = _live_box()
    try:
        g = _gateway(box, "g-1")
        assert _raw(base, "POST", "/whep/1", OFFER.encode()) == 503    # the first offer makes the stream: placed next
        live_ctl.ensure_placed(); g.reconcile_once(); g.heartbeat_once()
        bad = b"v=0\r\n\xff\xfe\xfa"
        assert _raw(base, "POST", "/whep/1", bad) == 400               # the console's
        assert _raw(g.url, "POST", "/whep/1", bad) == 400              # the gateway's own
        assert _raw(base, "POST", "/whep/1", OFFER.encode()) == 201 and len(g.sessions) == 1
    finally:
        srv.shutdown()


def _chunked(base: str, method: str, path: str, body: bytes) -> bytes:
    """`body` sent in one chunk, with `Transfer-Encoding: chunked` and no `Content-Length`: the reply's first line."""
    import socket
    from urllib.parse import urlsplit
    u = urlsplit(base)
    with socket.create_connection((u.hostname, u.port), timeout=5) as s:
        s.sendall(f"{method} {path} HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nIdempotency-Key: kc\r\n"
                  f"Transfer-Encoding: chunked\r\n\r\n".encode() + b"%x\r\n%b\r\n0\r\n\r\n" % (len(body), body))
        return s.recv(4096).split(b"\r\n", 1)[0]


def test_a_body_sent_in_chunks_is_refused_in_words_and_not_read_as_an_empty_one():
    """The product's cross-check of the eleventh review: no door here reads `Transfer-Encoding: chunked`, and with no
    `Content-Length` such a body was read as none — `{}` to the route: a PUT that changed nothing and answered 200, a
    POST that wrote defaults. `read_body` — every console's door, the domain's, the signing service's, the live
    gateway's — answers 400 in words and reads nothing more."""
    from tests.test_console_gate import _console
    box = Box()
    ctl, rec, m, srv, base = _console(box)
    try:
        assert _raw(base, "POST", "/cameras", json.dumps({"source": "driverpack://file/1.mp4"}).encode(), "k0") == 201
        for method, path in (("PUT", "/cameras/1"), ("POST", "/cameras"), ("POST", "/requests")):
            assert b" 400 " in _chunked(base, method, path, b'{"name": "x"}'), (method, path)
        assert [r["id"] for r in ctl.units()] == [1] and ctl.unit(1)["revision"] == 1
    finally:
        srv.shutdown()


# -- loops over many: the retain, the evaluator, the workers, the leases, the watch, the restore ----------------------

def test_a_scenario_nested_past_jsons_depth_stops_neither_the_retain_nor_the_evaluator():
    """Reproduced (the tenth pass, major): a scenario whose `when` is nested a hundred thousand deep raised
    `RecursionError` past `vms/resource.py`'s own tuple of exceptions — out of `kept_buckets`, and the whole server's
    `retain` swept nothing. And past the evaluator's (`AutoWorker.reconcile_once`): no scenario after it was decided.
    Through `PARSE_ERRORS` now: the scenario is a unit of no one camera to the retain, and `failed` to the evaluator."""
    from w2cplatform.events import EventLog, bucket_names_under
    from vms.resource import vms_resource
    from tests.test_autoworker import DOOR, _Log, _assigned, _scenario, _worker as _auto, ev
    box = Box()
    res = vms_resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    old = box.wall() - 40 * 86400
    EventLog(box.archive, "vms", "8", 1).append(old, "motion")
    box.vars.put("vms/retention/8", {"days": "30"})
    box.vars.put("auto/scenarios/s1", {"name": "s1", "when": DEEP, "then": "[]"})
    out = res.pass_()
    assert "errors" not in out and bucket_names_under(box.archive, "vms", "8", 600) == [], out

    t = box.wall()
    log = _Log([ev(t - 20, "det", "7-motion", "motion"), ev(t - 5, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box, name="a-door")
    _scenario(box)
    _assigned(box, "a-door").assign("a-1", ["a-door", "door-on-badge"])
    it, idx = box.vars.get("auto/scenarios/a-door")
    box.vars.put("auto/scenarios/a-door", {**it, "when": DEEP}, cas=idx)
    a = _auto(box, log)
    assert a.reconcile_once() == ["door-on-badge"] and DOOR["name"] in a.epochs
    assert a.status_by_unit["a-door"]["phase"] == "failed"
    _forget_garbled()


def test_infinity_in_a_rows_integer_stops_no_workers_pass_and_no_lease():
    """The siblings the review did not name: `revision: 1e999` (a JSON number a hand edit writes) is `int(inf)` — an
    `OverflowError`, past the `(ValueError, KeyError, TypeError)` of every worker's row reader: the scan's pass stopped
    at it. And `epoch: Infinity` raised out of `Lease.renew`, so out of `renew_leases` — every lease of the worker
    unrenewed for one row. Each is that row's now."""
    from w2cplatform.epoch import Lease
    from w2cplatform.spec import SpecController
    from vms.config import DETJOB_SPEC
    from tests.test_detjob_worker import _footage, _site, _worker as _scan, m
    box = _site(); _footage(box, "7", 1, 0, 10)
    ctl = SpecController(DETJOB_SPEC, box.vars, box.objects, wall=box.wall)
    for name in ("7-lpr-1", "7-lpr-2"):
        ctl.create({"name": name, "cam": "7", "rec": "7", "kind": "lpr", "from": m(0), "to": m(10)})
    box.vars.put(DETJOB_SPEC.sub.assignment("j-1"), {"units": "7-lpr-1,7-lpr-2", "rev": 1})
    _hand_edit(box, "detjob/jobs/7-lpr-1", "revision")
    w = _scan(box)
    w.reconcile_once()
    assert w.status_by_unit["7-lpr-1"]["phase"] == "failed"
    assert w.status_by_unit["7-lpr-2"]["phase"] in ("running", "done")

    box.vars.put("vms/epoch/1", {"epoch": "1"})
    box.vars.put("vms/epoch/2", {"epoch": "1"})
    _hand_edit(box, "vms/epoch/2", "epoch")
    good, bad = Lease(box.vars, "vms/epoch/1", 1, clock=box.clock), Lease(box.vars, "vms/epoch/2", 1, clock=box.clock)
    assert good.renew() is True and bad.renew() is False
    _forget_garbled()


def test_a_placement_row_counting_past_any_number_still_says_where_its_unit_is():
    """`rev: 1e999` in a placement row (a hand edit) was `int(inf)` past `_placement`'s `(ValueError, KeyError, TypeError)`:
    `placement()` raised under every step of the pass and every route that asks where a unit is. Read as a row whose
    `rev` does not parse — its worker stands, `rev 0` — and the next write of it counts from one."""
    from tests.test_lesson4_worker import _box_with_cameras
    box, ctl = _box_with_cameras(2)
    box.objects.put("vms/heartbeats/w-1", Heartbeat("w-1", box.wall(), [], {"server": "srv-a", "capacity": 50}).to_bytes())
    ctl.pass_once()
    _hand_edit(box, "vms/placement/1", "rev")
    pl = ctl.placement(1)
    assert pl.worker == "w-1" and pl.rev == 0
    ctl.pass_once()
    assert ctl.placement(2).worker == "w-1"
    _forget_garbled()


def test_a_bucket_line_nested_past_jsons_depth_does_not_stop_the_watch():
    """`json.loads` of one line nested a hundred thousand deep raised `RecursionError` past the watch's
    `(ValueError, AttributeError)`: the look raised, the sizes were not moved, and every look after it read the same
    line and raised again — the long poll dead for every unit, a trace a tick. The line is skipped like a torn one."""
    import tempfile
    from w2cplatform.longpoll import Watch
    p = os.path.join(tempfile.mkdtemp(), "x.events.jsonl")
    with open(p, "w") as f:
        f.write(DEEP + "\n" + json.dumps({"t": 1, "kind": "motion"}) + "\n")
    kinds, upto = Watch._kinds(p, 0, os.path.getsize(p))
    assert kinds == {"motion"} and upto == os.path.getsize(p)


def test_a_bucket_line_nested_past_jsons_depth_or_with_no_time_is_that_lines_for_every_reader_of_a_bucket():
    """The eleventh review's sweep of `mark_of` (`except ValueError` before `json.loads`): the two readers of a bucket's
    lines beside the watch — `read_bucket` (the resource's `/buckets`, repair, the recorder's look back) and the event
    database's line cache (`/events`) — let `RecursionError` out of the whole bucket, and the cache a line with no `t`
    or a word in it too; `read_bucket` handed a line that is a number to readers that take objects. Each is that line's,
    counted as torn, and the lines beside it are read."""
    import tempfile
    import w2cplatform.events as ev
    from w2cplatform.eventdatabase import EventIndex
    good = json.dumps({"t": 1000.0, "kind": "motion", "cam": 1})
    p = os.path.join(tempfile.mkdtemp(), "x.events.jsonl")
    with open(p, "wb") as f:
        f.write((DEEP + "\n7\n" + '{"t": "noon", "kind": "motion"}\n' + good + "\n").encode() + b"\xff\xfe\n")
    torn = ev.torn
    assert [e["kind"] for e in ev.read_bucket(p) if e.get("t") == 1000.0] == ["motion"] and ev.torn - torn == 3
    db = EventIndex(tempfile.mkdtemp())
    assert [ln[1] for ln in db._lines(p)] == ["motion"] and db.torn == 4


def test_a_frontier_or_a_waiting_file_that_does_not_read_is_not_there():
    """A survey's `frontier.json` that is a list (`TypeError`), a number past a float, or nested past JSON's depth raised
    out of `Frontier.read` — out of the survey's and the evaluator's pass, every pass; a scan's `waiting.json` the same.
    Each is a file that is not there: the row decides where to begin."""
    from vms.scan import Frontier, ScanLog
    box = Box()
    fr = Frontier(box.archive, "7-lpr")
    for raw in ("[1]", '{"watched_through": %s}' % ("9" * 400), DEEP, '{"watched_through": NaN}'):
        os.makedirs(os.path.dirname(fr.path), exist_ok=True)
        with open(fr.path, "w") as f:
            f.write(raw)
        assert fr.read() is None, raw[:20]
    log = ScanLog(box.archive, "7-lpr-1")
    os.makedirs(os.path.dirname(log._waiting_path()), exist_ok=True)
    for raw in ("[1]", '{"since": %s}' % ("9" * 400), DEEP):
        with open(log._waiting_path(), "w") as f:
            f.write(raw)
        assert log.waiting() is None, raw[:20]


def test_a_restore_whose_listing_skipped_lines_asks_that_peer_again():
    """The ninth pass's new minor: a peer of another build listed 20 lines of which 10 did not parse; the client skipped
    them, `restore` pulled the 10 it read — and marked the peer "gave everything": never asked again, 10 buckets gone.
    The listing says how many it skipped (`Listing.skipped`); they are counted in `left`, and the peer is asked again."""
    from w2cplatform.events import Bucket
    from w2cplatform.resource import RESTORE_RETRY, Listing, Resource
    box = Box()
    paths = [f"vms/7/e1/{i:02d}.events.jsonl" for i in range(10)]

    class Peers:
        skip = 10

        def mirrored(self, url, server):
            out = Listing(Bucket("vms", "7", 1, 0.0, 600.0, p, 1) for p in paths)
            out.skipped = self.skip
            return out

        def get(self, url, server, path):
            return b'{"t": 1, "kind": "motion"}\n'

    peers = Peers()
    res = Resource(box.archive, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, clock=box.clock, peers=peers)
    box.objects.put("platform/resources/srv-2/heartbeat", json.dumps(
        {"server": "srv-2", "ts": box.wall(), "url": "http://srv-2", "mirrors": {"srv-1": 20}}).encode())
    got = res.restore()
    assert got["pulled"] == 10 and got["left"] == 10, got
    assert res.heartbeat()["restore"]["left"] == 10
    box.clock.advance(RESTORE_RETRY)
    assert res.restore_due()                                           # not "gave everything": asked again
    peers.skip = 0
    again = res.restore()
    assert "left" not in again and not res.restore_due(), again


# -- the pass's memo, list values, the engine's answers ---------------------------------------------------------------

def test_two_controllers_in_one_pass_do_not_read_each_others_memo():
    """The tenth pass's minor: `Controller._heartbeats` kept its list under `(prefix, "")`, and `near_index` the followed
    subsystem's heartbeats as a dict under the same key — a survey's controller (`near: vms`) and the VMS's in one pass,
    and `workers_seen` walked the dict: `AttributeError`. And the index itself was one memo for every `near_of`: the VMS
    (`of: cam`) and a scan job (by id) both follow `rec`, and one got the other's index."""
    from w2cplatform.contract import one_pass
    from w2cplatform.spec import SpecController
    from vms.config import DETJOB_SPEC, SURVEY_SPEC
    from vms.controller import VmsController
    box = Box()
    t = box.wall()
    vms = VmsController(box.vars, box.objects, wall=box.wall)
    survey = SpecController(SURVEY_SPEC, box.vars, box.objects, wall=box.wall)
    job = SpecController(DETJOB_SPEC, box.vars, box.objects, wall=box.wall)
    box.objects.put("vms/heartbeats/w-1", Heartbeat("w-1", t, [{"id": 7, "phase": "running"}], {"server": "srv-a"}).to_bytes())
    box.objects.put("rec/heartbeats/r-1", Heartbeat("r-1", t, [{"id": "r9", "cam": "7", "phase": "running"}],
                                                     {"server": "srv-a"}).to_bytes())
    with one_pass(vms, survey, job):
        survey.near_index()
        assert list(vms.workers_seen()) == ["w-1"]
        assert set(vms.near_index().by) == {"7"} and set(job.near_index().by) == {"r9"}


def test_a_value_of_a_list_field_with_a_comma_is_refused_and_the_joined_string_is_taken():
    """The ninth answer's open item: a list field is stored joined by `,` and split on read by every reader, so
    `labels: ["zone 1,2"]` came back as two labels. Refused where it is written (create and update); a string is the
    joined form itself and is taken as it is."""
    from w2cplatform.spec import Refused, SpecController
    box = Box()
    rec = SpecController(REC_SPEC, box.vars, box.objects, wall=box.wall)
    for bad in ({"labels": ["zone 1,2"]}, {"labels": ["a", "b,c"]}):
        try:
            rec.create({"name": "r1", "cam": "7", **bad})
            raise AssertionError(f"took {bad}")
        except Refused as e:
            assert "','" in str(e)
    r = rec.create({"name": "r1", "cam": "7", "labels": "a,b"})
    assert rec.unit(r["id"])["labels"] == ["a", "b"]
    try:
        rec.update(r["id"], {"labels": ["x,y"]})
        raise AssertionError("an update took a comma")
    except Refused:
        pass


def test_an_engine_answer_this_build_cannot_read_is_a_wrong_volume_and_not_a_crash():
    """`int(reply["writer"])` of an answer with the field missing, `Infinity` for a handle: a bare `KeyError` or
    `OverflowError` out of `Archive.open` and `reading`, past their `(ObsdError, ValueError)` — the recorder's caller
    took it for a crash, not a volume it cannot use. They are `ArchiveError("wrong")` now, saying what was not read."""
    from vms.archive import ArchiveError, classify
    for e in (KeyError("writer"), OverflowError("cannot convert float infinity to integer"), TypeError("list")):
        got = classify(e)
        assert isinstance(got, ArchiveError) and got.kind == "wrong" and "cannot read" in str(got), (e, got)


# -- what the tenth round left beside its walks -----------------------------------------------------------------------
BIG = "1" + "0" * 400                                                 # a JSON integer no float holds: `OverflowError`


def test_a_moment_of_four_hundred_digits_in_a_request_is_that_requests_in_the_holder_and_the_recorder():
    """`float()` of an integer of 400 digits raises `OverflowError`, which `(TypeError, ValueError)` does not catch. A
    hand edit left one in a command's `at` and the holder's measure of the road raised out of `requests` — no command
    behind it performed; in a backfill's `from` the recorder's `requests` raised the same way. Read by `finite` now: the
    command is performed and its road not measured, the backfill is refused alone and the next one served."""
    from tests.test_long_poll import _holder
    box = Box()
    holder, cid, dev, called = _holder(box)
    holder.reconcile_once()
    now = box.wall()
    for rid in ("a", "b"):
        box.vars.put(f"vms/requests/{rid}", {"unit": str(cid), "action": "output", "port": "1", "at": str(now),
                                             "filed": str(now), "by": "auto/door", "valid_until": str(now + 30)})
    _hand_edit(box, "vms/requests/a", "at", BIG)
    _hand_edit(box, "vms/requests/a", "filed", BIG)
    holder.requests()
    assert holder.commands["performed"] == 2 and len(called) == 2
    assert holder.road["auto"]["count"] == 1 and holder.request_road["auto"]["count"] == 1   # "b" alone is measured

    from tests.test_backfill_bounds import NOW, _ours, _recorder
    from vms.worker import FakeActuator
    box, r, con_rec = _recorder(FakeActuator())
    _ours(box, r, 1, ((NOW - 3600, NOW - 2400),))
    for rid in ("1-a", "1-b"):
        con_rec.vars.put(REC_SPEC.sub.request_key(rid), {"unit": "1", "cam": "1", "from": str(NOW - 30000),
                                                         "to": str(NOW - 29700), "at": str(NOW), "by": "anna"})
    _hand_edit(box, REC_SPEC.sub.request_key("1-a"), "from", BIG)
    done = {d["request"]: d for d in r.requests(now=NOW)}
    assert "not a range" in done["1-a"]["error"] and "error" not in done["1-b"]


def test_a_line_a_device_posts_that_cannot_be_written_is_that_lines_and_the_bus_goes_on():
    """`drain_bus` handed every posted line to `observe` bare: a driver's `occurred` of 400 digits raised `OverflowError`
    past `float`'s `(TypeError, ValueError)`, a field `class` raised in `EventLog.append`, a value JSON cannot carry a
    `TypeError` — out of the loop, and the lines after it, of any camera, and the dead cameras' `lost` were gone. Now a
    moment that is no number is dropped and counted (`fields_garbled`), a line that cannot be written is dropped and
    counted (`events_refused`, `vms_device_events_refused_total`), and the rest of the bus is written."""
    from w2cplatform import rows
    from w2cplatform.console import heartbeats
    from w2cplatform.events import read_bucket
    from vms.console import beat_lines
    from vms.controller import VmsController
    from vms.worker import FakeActuator, VmsWorker
    box = Box()
    ctl = VmsController(box.vars, box.objects, wall=box.wall)
    for i in (1, 2):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4"})
    ctl.assign("w-1", ["1", "2"])
    act = FakeActuator()
    w = VmsWorker("w-1", box.vars, box.objects, act, clock=box.clock, wall=box.wall, archive_root=box.archive)
    w.reconcile_once()
    act.post(1, "io.input", port="1", occurred=int(BIG))              # a driver's integer of 400 digits
    act.post(1, "io.input", port="2", occurred=float("nan"))          # …and `nan`, which `float` took for a time
    act.post(1, "motion", **{"class": "alarm"})                        # a field `EventLog` refuses
    act.post(2, "motion", region={1, 2})                               # a value JSON cannot carry
    act.post(2, "io.input", port="3")                                  # …and the line after them all
    act.dead.append(1)
    w.drain_bus()
    assert w.events_refused == 2
    lines = {cid: read_bucket(w.observe(cid, "probe")) for cid in (1, 2)}
    one = {e["kind"] + e.get("port", ""): e for e in lines[1]}
    assert "occurred" not in one["io.input1"] and "occurred" not in one["io.input2"] and "silent" in one
    assert any(e["kind"] == "io.input" and e.get("port") == "3" for e in lines[2])
    assert rows.counts()["field"].get("vms") == 1                      # both moments: one spell of camera 1's `occurred`
    w.heartbeat_once()
    assert 'vms_device_events_refused_total{worker="w-1"} 2' in beat_lines("vms", heartbeats(box.objects, "vms/"))
    _forget_garbled()


def test_the_pushers_seconds_that_are_no_number_cost_the_card_neither_its_pass_nor_its_episode():
    """`footage_pass` read the pusher's `failed_s` by `float`: `nan` made `lost_seen` `nan` for good (`lost <= nan` is
    never true, so every pass after was footage lost again), and 400 digits raised out of `gate_pass` before `note_pass`.
    Through `rows.number` now: a value that is no number is read as nothing lost, counted, and the episode goes on."""
    from w2cplatform import rows
    from tests.test_camera_card import _alarms, _camera
    box, rec, ring, act, rec_ctl = _camera()
    said = {"state": "pushing", "lagging": False, "cut_s": 0.0, "left_s": 0.0, "failed_s": 0.0, "failed": 0}
    rec.stream_said = lambda: dict(said)
    for bad in (float("nan"), int(BIG), "ten", [1]):
        said["failed_s"] = bad
        rec.gate_pass()                                                # nothing raised, nothing said lost
        assert rec.lost_seen == 0.0 and _alarms(box, "camera.footage.lost") == []
    assert rows.counts()["field"].get("rec", 0) >= 1
    said["failed_s"] = 4.0
    rec.gate_pass()
    assert len(_alarms(box, "camera.footage.lost")) == 1 and rec.lost_seen == 4.0
    _forget_garbled()


def test_a_keep_line_whose_seconds_or_moment_is_no_number_is_that_lines():
    """`_keeps_held_before` read the event lines of what this volume held of each keep by `float` and sorted them by
    `events.when`: a line hand-edited to 400 digits of `seconds` or `t: "yesterday"` raised out of the keeps' pass, and
    no keep of the volume was looked at. That line is read as not said now, counted; the others are summed as before."""
    from w2cplatform import rows
    from w2cplatform.events import EventLog
    from vms.recworker import REC, RecWorker
    box = Box()
    t = box.wall()
    p = EventLog(box.archive, REC.name, "1", 1).path_for(t)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    good = {"t": t, "kind": "archive.keep.copied", "keep": "k1", "recording": "1", "volume": "v1", "seconds": 30.0, "id": "a"}
    with open(p, "w") as f:
        f.write(json.dumps(good) + "\n")
        f.write(json.dumps({**good, "seconds": "__big__", "id": "b"}).replace('"__big__"', BIG) + "\n")
        f.write(json.dumps({**good, "t": "yesterday", "seconds": 50.0, "id": "c"}) + "\n")
        f.write(json.dumps({**good, "kind": "archive.keep.lost", "t": t + 1, "seconds": 10.0, "id": "d"}) + "\n")
        f.write("5\n")                                                 # a line that is no object
    me = types.SimpleNamespace(archive_root=box.archive, volume="v1")
    held = RecWorker._keeps_held_before(me, [types.SimpleNamespace(id="k1")], lambda k: ["1"], lambda k, rec: 0.0)
    assert held == {("k1", "1"): 20.0}, held
    assert rows.counts()["field"].get(REC.name, 0) >= 1                 # both lines: one spell of recording 1's copies
    _forget_garbled()


def test_a_unit_whose_filters_raise_is_one_nothing_can_serve_and_the_others_are_judged():
    """`_unplaceable` and `_would_strand` called `eligible` bare for each unit, while the controller's steps stood past
    one unit already: a filter that raised on one row — a field that reads and does not compare, an `admit` that trips
    on it — took `/unplaceable` and `/drain` down for every unit. That unit is listed now as one nothing can serve (with
    why), counted once a walk (`unit_judged`), and the other units are judged."""
    from w2cplatform import rows
    from w2cplatform.console import Mount, SpecConsole
    from tests.test_lesson4_worker import _box_with_cameras
    box, ctl = _box_with_cameras(3)
    box.objects.put("vms/heartbeats/w-1", Heartbeat("w-1", box.wall(), [], {"server": "srv-a", "capacity": 50}).to_bytes())

    def taken(row):                                   # a filter that trips on one row (the platform's own, since `admit` is gone)
        if str(row["id"]) == "2":
            raise TypeError("'<' not supported between instances of 'str' and 'int'")
        return set()

    ctl.servers_taken = taken
    try:
        got = {str(u["id"]): u for u in ctl.unplaceable()}
        assert set(got) == {"2"} and "could not be checked" in got["2"]["why"], got
        ctl.pass_once()
        assert ctl.placement(1).worker == "w-1" and ctl.placement(3).worker == "w-1" and ctl.placement(2) is None
        assert ctl.would_strand("srv-b") == ["2"]                     # the others are not on it; "2" is on nobody
        ctl.drain("srv-a")
        status, rep = Mount(SpecConsole(ctl, wall=box.wall)).drain_route("GET", {})
        assert status == 200 and set(rep["subsystems"]["vms"]["would_strand"]) == {"1", "2", "3"}, rep
        assert rows.counts()["unit_judged"].get("vms") == 2, rows.counts()["unit_judged"]   # one spell in each walk
    finally:
        del ctl.servers_taken
        _forget_garbled()


def test_channel_of_reads_any_value_as_channel_key_and_device_of_do():
    """The devices group closed `channel_of` for a `[` with no `]`; `channel_key` and `device_of` read `str(source)`, and
    `channel_of` alone raised on a value that is not a string (`5`, `None`). Now the three read it as a string."""
    from vms.config import channel_key, channel_of, device_of
    for v in (5, None, ["a"], int(BIG), "rtsp://[::1/x", "driverpack://acme/h/ch/" + "9" * 5000):
        channel_of(v), channel_key(v), device_of(v)
    assert channel_of(5) is None and channel_key(None) == ""


def test_the_resources_are_said_once_per_console_under_the_platforms_name():
    """A resource is the PLATFORM's — one per server, whatever subsystems write into it — and every mounted console
    said its numbers again under its own prefix: `vms_resources_live`, `det_resources_live`, `detjob_…`, one fact as
    many times as there were subsystems (the course's decision on the platform's names). Now `w2c_resources_live` and
    `w2c_resource_*`, on the root's page of a `Mount` only — a console mounted later included — and on a console that
    serves alone; no subsystem's page carries a resource line under any prefix."""
    from w2cplatform.console import Mount, SpecConsole
    from w2cplatform.spec import SpecController
    from vms.config import DET_SPEC, DETJOB_SPEC, SPEC
    box = Box()
    t = box.wall()
    box.objects.put("platform/resources/srv-a/heartbeat", json.dumps(
        {"server": "srv-a", "ts": t, "url": "http://a", "space": {"full": 0.5}, "short": 0}).encode())
    con = lambda spec: SpecConsole(SpecController(spec, box.vars, box.objects, wall=box.wall), wall=box.wall)
    alone = con(SPEC).metrics_text()
    assert "w2c_resources_live 1" in alone and 'w2c_resource_full{server="srv-a"} 0.5' in alone
    root, jobs, det = con(SPEC), con(DETJOB_SPEC), con(DET_SPEC)
    m = Mount(root, {"detjob": jobs})
    m.mount("det", det)
    pages = {c.spec.name: c.metrics_text() for c in (root, jobs, det)}
    assert pages["vms"].count("\nw2c_resources_live 1\n") == 1 and 'w2c_resource_short_bytes{server="srv-a"} 0' in pages["vms"]
    for name, text in pages.items():
        assert "_resources_live" not in text.replace("w2c_resources_live", ""), name   # never under a subsystem's prefix
        assert f"{name}_resource_" not in text, name
        if name != "vms":
            assert "w2c_resource" not in text, name                                     # said once: by the root
