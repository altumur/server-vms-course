"""VMS behavior formerly mixed into tests/domain; kept in the subsystem test suite."""
import json
from tests.domain.conftest import Clock, make_cluster
from tests.reporting import sync as report_sync
from w2cplatform.domain.agent import ClusterTrust, DomainAgent, DomainPublisher, KEYS_PATH, MEMBER_PATH
from w2cplatform.domain.alarms import DomainAlarms
from w2cplatform.domain.federation import Federation
from w2cplatform.domain.readview import ReadView
from w2cplatform.domain.uplink import member_copy
from w2cplatform.trust.signer import Signer
from tests.vmsconftest import ingest_recorder
from tests.domainvms.test_domain_confirmation_splits import _domain, _site
from vms.ingest import ASK_DEADLINE_MAX, MAX_LIVE_ASKS, OUTCOMES_KEPT, POLLED, Refused, audience
from vms.camera_actions import misfit
from vms.recording_books import primary, source
from vms.recording_sources import camera_taken, NotResolvable, resolve
from vms.gateway import Forbidden, Gateway, LiveTee, WorkerLiveEndpoint

NOW = 1_001_000.0

def test_an_ask_whose_deadline_or_camera_clock_is_not_a_number_is_refused_and_the_ceiling_holds():
    """A deadline of `nan` passed every check and failed every comparison: never counted against `MAX_LIVE_ASKS`,
    never expired — two thousand asks at a ceiling of sixteen. A deadline or a camera clock that is not a finite
    number is refused, so is a deadline further ahead than `ASK_DEADLINE_MAX` (the product: `within` had no bound),
    and the ceiling counts what is left."""
    wall = Clock(10_000.0)
    south, _ = make_cluster("south")
    signer = Signer("acme", south.vars, now=wall)
    DomainPublisher(south.vars).publish_keys(signer.tokens.keyset())
    ing = ingest_recorder("south", "srt://south:9000", wall, keys=lambda: ClusterTrust(south.vars).keyset()).ingest
    acts = [{"camera": "SN5", "action": "preset", "arg": i} for i in range(40)]
    token = signer.tokens.issue("cam-GATE", 3600, now=wall(), aud=["south"], ref="SN5", by="GATE", acts=acts, kind="ask")
    for deadline, camera_now in ((float("nan"), None), (float("inf"), None), ("soon", None),
                                 (wall() + ASK_DEADLINE_MAX + 60, None), (wall() + 10, float("nan"))):
        for i in range(3):
            try:
                ing.ask(token, "SN5", acts[i], deadline, camera_now=camera_now); raise AssertionError("must refuse")
            except Refused:
                pass
    assert sum(len(c.asks) for c in ing.cams.values()) == 0
    for i in range(MAX_LIVE_ASKS):
        ing.ask(token, "SN5", acts[i], wall() + 30)
    try:
        ing.ask(token, "SN5", acts[MAX_LIVE_ASKS], wall() + 30); raise AssertionError("the ceiling must hold")
    except Refused as e:
        assert "ceiling" in str(e)
    try:
        ing.poll(signer.tokens.issue("cam-SN5", 60, now=wall(), aud=audience("south"), ref="SN5", kind="stream"), "SN5",
                 camera_now=float("nan")); raise AssertionError("a camera clock of nan must be refused")
    except Refused:
        pass

def test_a_camera_whose_description_is_words_stops_no_book_and_reads_as_not_said():
    """`int(can.get("presets"))` on "five" and `can_a['events']` on a description that is not one raised out of the
    pass over the books — every camera's books with it. A description that is not one says nothing: the camera
    reads as one that has not said, and `misfit` reads a count that is a word as none."""
    from vms.camera_actions import misfit
    assert misfit("cam", {"ptz": True, "presets": "five"}, {"action": "preset", "arg": 3}) is None
    assert misfit("cam", {"relays": "two"}, {"action": "output", "arg": 1}) == "cam has no relays"

def test_invalid_input_does_not_publish_a_partial_report_and_working_flow_survives():
    from tests.domainvms.test_two_servers import SERIAL, _office
    from vms.recording_books import primary
    from w2cplatform.domain.reports import read
    wall = Clock()
    o = _office(wall)
    o.pusher.pass_once([{"t": wall(), "key": True}])
    before = read("srv-a", o.b.objects)
    o.a.vars.put("rec/primaries/r-a", {SERIAL: '{"ref":'})
    o.recording_domain.collect()
    after = read("srv-a", o.b.objects)
    assert after.raw == before.raw and after.mark == before.mark
    items = o.cam.flash.get("domain/rec/primaries")[0]
    assert primary(items, SERIAL, "srv-a").value["running"] is True
    assert "srv-a" in o.pusher.entry()["channels"]
    wall.advance(46)
    o.recording_domain.collect()
    assert primary(o.cam.flash.get("domain/rec/primaries")[0], SERIAL, "srv-a") is None
    assert "srv-a" in o.pusher.entry()["channels"]  # existing data flow is independent of a lost report

def test_a_camera_that_says_who_takes_its_stream_as_a_string_is_not_read_as_its_letters():
    """The sibling of the string of urls: `taken_by: "srv-b"` passed `list(...)` as letters, every letter is somebody
    else, and the standby `srv-b` read the camera as taken by another and never pulled. A list of names, or nothing
    known (None: change nothing)."""
    from vms.recording_sources import camera_taken

    class Door:
        def __init__(self, said):
            self.said = said

        def get(self, key):
            return json.dumps({"taken_by": self.said}).encode()
    assert camera_taken(Door("srv-b"), "SN1", "srv-b") is None
    assert camera_taken(Door(["srv-b"]), "SN1", "srv-b") is False and camera_taken(Door(["srv-a"]), "SN1", "srv-b") is True

def test_an_ask_whose_deadline_has_passed_is_refused_and_one_askers_outcomes_are_bounded_without_crowding_out_another():
    """The ninth review, a minor, run as its probe ran it: 20 000 asks with `deadline = now − 1` were taken — a deadline
    already past was never a live ask, so `MAX_LIVE_ASKS` never counted it — each became an "expired" outcome kept for
    `REMEMBER`, and every ask swept all of them: 27.5 s of the ingest's CPU. A deadline that has passed is refused now;
    an asker that lets its asks run out as fast as it may keeps at most `OUTCOMES_KEPT` outcomes at a camera, the
    oldest forgotten first; and another asker's outcome is not pushed out by it."""
    from vms.ingest import OUTCOMES_KEPT
    wall = Clock(10_000.0)
    south, _ = make_cluster("south")
    signer = Signer("acme", south.vars, now=wall)
    DomainPublisher(south.vars).publish_keys(signer.tokens.keyset())
    ing = ingest_recorder("south", "srt://south:9000", wall, keys=lambda: ClusterTrust(south.vars).keyset()).ingest
    acts = [{"camera": "SN5", "action": "preset", "arg": i} for i in range(MAX_LIVE_ASKS)]

    def token(by):
        return signer.tokens.issue(f"cam-{by}", 3600, now=wall(), aud=["south"], ref="SN5", by=by, acts=acts,
                                   kind="ask")
    flood, other = token("GATE"), token("YARD")
    for deadline in (wall() - 1, wall()):
        try:
            ing.ask(flood, "SN5", acts[0], deadline); raise AssertionError("a deadline that has passed must be refused")
        except Refused as e:
            assert "passed" in str(e)
    assert ing.cams.get("SN5") is None or not ing.cams["SN5"].asks
    kept = ing.ask(other, "SN5", acts[0], wall() + 1)                     # another asker's ask, expired like the rest
    for _ in range(40):                                                   # sixteen live asks at a time, run out, again
        for i in range(MAX_LIVE_ASKS):
            ing.ask(flood, "SN5", acts[i], wall() + 1)
        wall.advance(2)
    assert ing.ask_outcome("SN5", kept) == "expired"                      # not crowded out by 640 of GATE's
    outcomes = ing.cams["SN5"].outcomes
    assert sum(1 for v in outcomes.values() if v[2] == "GATE") == OUTCOMES_KEPT and len(outcomes) == OUTCOMES_KEPT + 1

def test_a_preset_or_a_port_in_digits_that_are_not_ascii_is_a_misfit_and_not_a_value_error():
    """The tenth pass's sweep of `isdigit` then `int` (М10B's `vms/auto.py` had it too): `"²".isdigit()` is true and
    `int("²")` raised out of `misfit` — out of the domain's check of the scenario being written. By `doors.numeric`."""
    from vms.camera_actions import misfit
    for arg in ("²", "١", "７"):
        assert misfit("cam", {"relays": 2}, {"action": "output", "arg": arg}) == f"cam has 2 relay(s), not port {arg}"
        assert misfit("cam", {"ptz": True, "presets": 4}, {"action": "preset", "arg": arg}) == f"cam has 4 preset(s), not {arg}"
    assert misfit("cam", {"relays": 2}, {"action": "output", "arg": "2"}) is None

def test_a_member_always_carries_a_mark_that_it_is_one_and_its_console_shuts_when_the_keys_go():
    """The review's fourth pass. The cluster's console tells "the keys were lost" from "there never were any" by the
    rows only the agent writes (`DOMAIN_MARKS`), and each of those was conditional: `domain/root` only with a
    root-signed key set, the grants and the rest only when the domain has some for this cluster. A member with an
    unsigned key set and no grants had none of them — its keys deleted, the console was open to anybody as `admin`.
    The agent writes `domain/member` on every pass that leaves a key set, again after it was lost."""
    import tempfile
    import urllib.error
    import urllib.request
    from w2cplatform.cluster.objectstore import FsObjectStore
    from w2cplatform.domain.agent import MEMBER_PATH
    from vms.console import make_console
    from vms.controller import VmsController
    from w2cplatform.access import DOMAIN_MARKS, has_mark
    clk = Clock(1000.0)
    fed, links, dc, signer = _domain(clk)
    south = fed.clusters["south"]
    DomainPublisher(dc.vars).publish_keys(signer.tokens.keyset())     # a key set, no grants for south, no root pinned
    agent = DomainAgent("south", dc.vars, south.vars, now=clk)
    assert report_sync(agent)
    assert MEMBER_PATH in DOMAIN_MARKS and south.vars.get(MEMBER_PATH)[0] == {"cluster": "south"}
    assert [p for p in DOMAIN_MARKS if has_mark(south.vars, p)] == [MEMBER_PATH]     # the only mark there is
    idx = south.vars.get(MEMBER_PATH)[1]
    report_sync(agent)
    assert south.vars.get(MEMBER_PATH)[1] == idx                                   # not rewritten every pass

    south.vars._items.pop(KEYS_PATH)                                               # the key set is lost: a rollback, past the store
    srv = make_console(VmsController(south.vars, FsObjectStore(tempfile.mkdtemp(prefix="m12-")), wall=clk), None, clk) \
        .serve("127.0.0.1", 0)
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/cameras")
            raise AssertionError("a member's console without its keys let a stranger in")
        except urllib.error.HTTPError as e:
            assert e.code == 503 and MEMBER_PATH in json.loads(e.read())["detail"]
    finally:
        srv.shutdown()
    south.vars._items.pop(MEMBER_PATH)
    assert report_sync(agent) and south.vars.get(MEMBER_PATH)[0] and south.vars.get(KEYS_PATH)[0]   # both back on the next pass

def test_a_camera_still_polling_its_ingest_is_alive_and_not_reporting():
    """Its agent stopped — a crash, an expired certificate — and the camera works. The ingest it polls says so
    (`rec/polled`): the poll is kept by the camera's pusher, not by its agent. The alarm is then "not
    reporting", with where and when it was last seen alive: the operator sends somebody to fix software, not
    to look for a broken camera."""
    wall = Clock(NOW)
    fed, north, devices, cards, agents, report, reported = _site(wall)
    DomainAlarms(fed, reported, wall).list(since=NOW - 60)
    wall.advance(120)
    report(skip=("cam-SN0",))                                            # its agent is gone; the camera is not
    north.objects.put(f"{POLLED}/srt___north_9000", json.dumps({"cluster": "north", "ts": wall(), "units": {"cam-SN0": 2.0}}).encode())
    out = DomainAlarms(fed, reported, wall).list(since=NOW - 60)
    alarm = [e for e in out["events"] if e["member"] == "cam-SN0"][0]
    assert (alarm["kind"], alarm["alive_at"], alarm["alive_via"]) == ("not_reporting", NOW + 118, "north")
    assert "alive, and not reporting to the domain" in out["sentence"]

def test_a_cluster_with_no_cameras_yet_reports_that_it_has_none():
    """Feedback AA, on the report. A server room nobody has given a camera yet runs its controller once and
    publishes an empty `unplaced` shard; its agent reports; the domain lists it as a member that answered
    with nothing — complete — and not as one that never reported."""
    from vms.controller import VmsController
    wall = Clock(NOW)
    north, _ = make_cluster("north", domain=True)
    south, _ = make_cluster("south")
    fed = Federation(); fed.add(north)
    fed.add(member_copy("south", north.objects, wall=wall))
    VmsController(south.vars, south.objects, wall=wall, cluster="south").publish_snapshot()
    agent = DomainAgent("south", north.vars, south.vars, now=wall, domain_objects=north.objects, published=south.objects)
    assert report_sync(agent) and agent.reported.startswith("reported")
    view = ReadView(fed, wall=wall); view.refresh()
    page = view.list()
    assert page["total"] == 0 and page["complete"] and page["clusters"]["south"] == "ok"

def test_gateway_fans_out_and_the_worker_sees_one_viewer():
    tees = {7: LiveTee(7)}
    def authorise(token, camera):
        if token != "alice-token": raise Forbidden(token)
        return "alice"
    ep = WorkerLiveEndpoint("w-0", tees, authorise)
    gw = Gateway("gw-1", where=lambda c: "w-0", endpoint=lambda n: ep)
    viewers = [gw.watch(7, "alice-token", f"browser-{i}", maxsize=5) for i in range(50)]
    assert tees[7].viewers == 1 and gw.viewers(7) == 50                  # ONE subscription on the worker, fifty out
    try:
        gw.watch(7, "bad-token", "browser-x"); raise AssertionError("the cluster's authoriser decides")
    except Forbidden:
        pass
    for f in range(100):
        tees[7].push(f"frame-{f}")                                       # the worker's push never blocks
    assert gw.pump() == 30 and tees[7].subscribers["gw-1"].dropped == 70  # upstream leaky queue (30) leaked
    assert all(len(v.q) == 5 and v.dropped == 25 for v in viewers)       # every slow viewer leaked its own
    for i in range(50):
        gw.leave(7, f"browser-{i}")
    assert tees[7].viewers == 0 and gw.viewers(7) == 0

def test_gateway_follows_a_failover():
    eps = {"w-0": WorkerLiveEndpoint("w-0", {7: LiveTee(7)}, lambda t, c: "alice"),
           "w-1": WorkerLiveEndpoint("w-1", {7: LiveTee(7)}, lambda t, c: "alice")}
    home = {"cam": "w-0"}
    gw = Gateway("gw", where=lambda c: home["cam"], endpoint=eps.__getitem__)
    gw.watch(7, "t", "b1")
    home["cam"] = "w-1"                                                   # the controller moved it; the directory says so
    assert gw.reconnect(7, "t") == "w-1" and eps["w-1"].tees[7].viewers == 1 and gw.viewers(7) == 1

def test_sources_do_not_infer_push_from_topology_or_network_reachability():
    from tests.domainvms.test_lesson13_crossing import _site, SERIAL
    from vms.recording_books import source
    wall = Clock()
    _, _, south, cam, books, _, _ = _site(wall)
    books.assign(SERIAL, "south"); books.collect()
    assert "push" not in source(south.vars.get("domain/cam/sources")[0], SERIAL).value
    cam.pushes = True
    books.collect()
    assert source(south.vars.get("domain/cam/sources")[0], SERIAL).value["push"] is True

def test_recorder_pull_failure_is_local_and_never_changes_the_origin_source():
    from tests.domainvms.test_lesson13_crossing import _site, SERIAL
    from vms.recording_books import source, primary
    wall = Clock()
    _, _, south, cam, books, _, _ = _site(wall)
    books.assign(SERIAL, "south"); books.collect()
    row = {"id": SERIAL, "cam": "ref:"+SERIAL, "enabled": True}
    books.observe("south", [row], [{"id": SERIAL, "phase": "pending", "source_unreachable": True}], ingest="http://south/ingest")
    books.collect()
    assert "push" not in source(south.vars.get("domain/cam/sources")[0], SERIAL).value
    assert primary(cam.flash.get("domain/rec/primaries")[0], SERIAL, "south").value["push"] is True
    books.observe("south", [row], [{"id": SERIAL, "phase": "running"}], ingest="http://south/ingest")
    books.collect()
    assert primary(cam.flash.get("domain/rec/primaries")[0], SERIAL, "south").value["push"] is True
    cam.address = "10.1.0.99"; books.collect()
    books.observe("south", [row], [{"id": SERIAL, "phase": "running"}], ingest="http://south/ingest")
    books.collect()
    assert "push" not in primary(cam.flash.get("domain/rec/primaries")[0], SERIAL, "south").value

def test_unconfirmed_source_does_not_start_a_stream_from_network_guesses():
    from tests.domainvms.test_lesson13_crossing import _site, SERIAL
    from vms.recording_sources import NotResolvable, resolve
    wall = Clock()
    _, _, south, cam, books, _, _ = _site(wall)
    books.assign(SERIAL, "south")
    try:
        resolve(south.vars, "ref:"+SERIAL, wall())
    except NotResolvable:
        pass
    else:
        raise AssertionError("an unconfirmed source was selected")
