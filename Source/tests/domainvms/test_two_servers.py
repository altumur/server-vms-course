"""Two servers in an office — two clusters of one, no orchestrator (М11 lesson 1).

A third raft vote cannot stand anywhere, so the two servers are not one cluster: each is a cluster of one under
`systemd`, and the domain sits above them. Server A records the camera. What stands in for A when it does not
write is not a scheduler but two STANDBY recordings, both `when: offline` (М10B lesson 26):

    edge     the card in the camera — its own recorder, from its own sensor, no network between them
    backup   the second server's backup volume — fed over the network, and a camera that pushes sends its ONE
             stream there only when A does not take it

Both start from the same book of primaries; when A is back it takes everything home — from the backup first,
on the LAN, and from the card for the rest. A viewer opens the camera where its stream is going.
"""

from tests.reporting import sync as report_sync
from tests.domainvms.recording_domain import RecordingDomain, camera_pusher
import json
from types import SimpleNamespace

from w2cplatform.cluster.variables import FakeVariables

from w2cplatform.domain.agent import DomainAgent, DomainPublisher
from vms.domainpart.inputs import BookInputs
from vms.recording_sources import plan_takeback, resolve
from vms.camera_cluster import DeviceCluster
from w2cplatform.domain.federation import Federation, Unreachable
from vms.gateway import Gateway
from vms.ingest import CameraPusher, IngestLiveEndpoint, audience, live_road
from w2cplatform.domain.readview import ReadView
from w2cplatform.trust.signer import Signer
from w2cplatform.domain.uplink import member_copy
from tests.domain.conftest import Clock, make_cluster
from tests.vmsconftest import ingest_recorder

SERIAL = "SN6001"
A_URLS, B_URLS = ["srt://srv-a:9000"], ["srt://srv-b:9000"]


def _office(wall):
    from vms import volumes
    from vms.config import REC_SPEC
    from w2cplatform.spec import SpecController
    fed = Federation()
    b, _ = make_cluster("srv-b", domain=True)                         # the backup server; the domain lives here
    a, a_link = make_cluster("srv-a")                                  # the server that records the camera
    fed.add(a); fed.add(b)
    signer = Signer("acme", b.vars, now=wall)
    DomainPublisher(b.vars).publish_keys(signer.tokens.keyset())
    # Each server's ingest lives in a recorder of its own (`RecWorker.host_ingest`, ADR-0065's addition), which says where
    # in its heartbeat; whether its cluster should record the camera it reads from its own rows (`should_from_snapshot`)
    hosts = {"srv-a": ingest_recorder("srv-a", A_URLS[0], wall, a.vars, a.objects, name="r-ingest"),
             "srv-b": ingest_recorder("srv-b", B_URLS[0], wall, b.vars, b.objects, name="r-ingest")}
    ing = {n: r.ingest for n, r in hosts.items()}
    agents = {"srv-a": DomainAgent("srv-a", b.vars, a.vars, now=wall),
              "srv-b": DomainAgent("srv-b", b.vars, b.vars, now=wall, seen_store=b.objects)}
    for x in agents.values():
        report_sync(x)

    rec_a = SpecController(REC_SPEC, a.vars, a.objects, wall=wall)
    rec_a.create({"name": SERIAL, "cam": f"ref:{SERIAL}"})           # the primary, on A
    volumes.write(b.vars, {"name": "copy", "kind": "backup", "server": "srv-b", "url": "/data/copy", "quota_bytes": 10**12})
    rec_b = SpecController(REC_SPEC, b.vars, b.objects, wall=wall)
    rec_b.create({"name": f"{SERIAL}-copy", "cam": f"ref:{SERIAL}", "home": "copy", "when": "offline"})   # the backup, on B
    rec_b.publish_snapshot()

    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, pushes=True)
    cam.coverage = {"from": wall() - 3600, "to": wall()}              # the edge archive: the card
    cam.boot(); cam.door_open = False
    fed.add(member_copy(cam.name, b.objects, wall=wall))
    cam_agent = DomainAgent(cam.name, b.vars, cam.flash, now=wall, domain_objects=b.objects,
                            published=cam.local_objects(), seen_store=cam.local_objects())
    report_sync(cam_agent)
    view = ReadView(fed, wall=wall); view.refresh()
    crossings = BookInputs(b.vars, view, wall)
    recording_domain = RecordingDomain(crossings, signer, agents=[*agents.values(), cam_agent], devices=[cam])
    recording_domain.assign(SERIAL, "srv-a", copies=["srv-b"])
    recording_domain.collect()

    def recorders(a_running=True, backup_coverage=None):              # what each server's recorder says
        from w2cplatform.contract import Heartbeat, Subsystem
        rec_a.publish_snapshot()
        st = [{"id": SERIAL, "cam": f"ref:{SERIAL}", "enabled": True, "phase": "running" if a_running else "pending"}]
        a.objects.put(Subsystem("rec").heartbeat_key("r-a"), Heartbeat("r-a", wall(), st, {}).to_bytes())
        cov = backup_coverage or {"from": wall() - 60, "to": wall()}
        b.objects.put(Subsystem("rec").heartbeat_key("r-b"), Heartbeat("r-b", wall(), [
            {"id": f"{SERIAL}-copy", "cam": f"ref:{SERIAL}", "enabled": True, "phase": "running", "coverage": cov}],
            {"url": "http://srv-b:9100/"}).to_bytes())
        recording_domain.observe("srv-a", rec_a.units(), st, worker="r-a", ingest=A_URLS[0])
        recording_domain.observe("srv-b", rec_b.units(), [{"id": f"{SERIAL}-copy", "phase": "running",
            "coverage": {**cov, "fragments": cov.get("fragments", 1)}}], worker="r-b", kind="backup",
            ingest=B_URLS[0], peer="http://srv-b:9100/")
        recording_domain.observe(cam.name, [{"id": "card", "cam": "ref:"+SERIAL, "enabled": True}],
            [{"id": "card", "phase": "running", "coverage": {**cam.coverage, "fragments": 1}}], kind="edge")


    def domain_pass(a_up=True, backup_coverage=None):
        for n, r in hosts.items():
            if a_up or n != "srv-a":
                r.heartbeat_once()                                     # where each server's ingest is, said again
        cam.publish(); report_sync(cam_agent)
        if a_up:
            recorders(backup_coverage=backup_coverage)
            report_sync(agents["srv-a"])
        view.refresh(); recording_domain.collect()
        report_sync(agents["srv-b"]); report_sync(cam_agent)
        if a_up:
            report_sync(agents["srv-a"])

    down = set()

    def dial(url):
        for name, i in ing.items():
            if url in i.urls and name not in down:
                return i
        raise Unreachable(f"{url} did not answer")

    q = {n: (i.want(SERIAL, f"recorder:{n}"), i.subscribe(SERIAL, f"recorder:{n}", maxsize=1000))[1] for n, i in ing.items()}
    pusher = camera_pusher(SERIAL, cam.flash, dial, clock=wall, ring_seconds=30)
    domain_pass()
    return SimpleNamespace(fed=fed, a=a, b=b, a_link=a_link, ing=ing, q=q, cam=cam, pusher=pusher, crossings=crossings,
                           domain_pass=domain_pass, recorders=recorders, down=down, dial=dial, rec_a=rec_a, recording_domain=recording_domain)


from weakref import WeakKeyDictionary
_GATES = WeakKeyDictionary()


def _covers(vars_, objects, row, now):
    """The standby's gate, as the recorder runs it (`vms.recworker.RecWorker.carried_primary`)."""
    from vms.recworker import RecWorker
    me = _GATES.get(vars_)
    if me is None:
        me = SimpleNamespace(vars=vars_, objects=objects, _not_written_since={}, CARRIED_LOST_AFTER=45.0, START_GRACE=20.0)
        _GATES[vars_] = me
    return RecWorker.carried_primary(me, row, now)


EDGE = {"id": "card", "cam": f"ref:{SERIAL}", "home": "card", "when": "offline"}
BACKUP = {"id": f"{SERIAL}-copy", "cam": f"ref:{SERIAL}", "home": "copy", "when": "offline"}


def _frames(wall, n, start=0):
    """The sensor's frames `start` to `start + n`, twenty-five a second: their capture times go forward with their
    numbers — a pusher takes no frame that is not newer than the last it holds (М12 Lesson 16, the seventh review)."""
    return [{"t": wall() + (start + i) * 0.04, "n": start + i, "key": (start + i) % 25 == 0} for i in range(n)]


def test_each_assigned_receiver_has_its_own_channel_while_reserve_gates_hold():
    wall = Clock()
    o = _office(wall)
    e = o.pusher.entry()
    assert e["primary"] == "srv-a" and set(e["channels"]) == {"srv-a", "srv-b"}
    assert e["channels"]["srv-b"]["urls"] == B_URLS
    assert o.pusher.pass_once(_frames(wall, 5))["pushed"] == 10
    assert [f["n"] for f in o.q["srv-a"].drain()] == list(range(5))
    assert [f["n"] for f in o.q["srv-b"].drain()] == list(range(5))
    assert not _covers(o.cam.flash, o.cam.local_objects(), EDGE, wall())
    assert not _covers(o.b.vars, o.b.objects, BACKUP, wall())


def test_disabled_recording_is_observed_and_reassignment_withdraws_its_receiver():
    wall = Clock()
    o = _office(wall)
    row = {"id": SERIAL+"-copy", "cam": "ref:"+SERIAL, "enabled": False}
    o.recording_domain.observe("srv-b", [row], [{"id": row["id"], "phase": "pending"}],
        kind="backup", worker="r-b", ingest=B_URLS[0])
    o.recording_domain.collect()
    assert set(o.pusher.entry()["channels"]) == {"srv-a", "srv-b"}
    o.recording_domain.assign(SERIAL, "srv-a", copies=[])
    o.recording_domain.collect()
    assert set(o.pusher.entry()["channels"]) == {"srv-a"}


def test_page_projection_of_primary_and_backup_is_flat_and_has_no_transport_credentials():
    import tempfile
    from pathlib import Path
    from vms.config import REC_SPEC
    from w2cplatform.console import SpecConsole
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.spec import SpecController
    from w2cplatform.variables import FileVariables
    from w2cplatform.domain.memberbook import read
    wall = Clock()
    o = _office(wall)
    copy = read(o.b.vars, "domain/rec/primaries", "srv-b")
    root = Path(tempfile.mkdtemp(prefix="primaries-"))
    v = FileVariables(str(root/"config"), volatile=True)
    v.put("domain/rec/primaries", copy)
    con = SpecConsole(SpecController(REC_SPEC, v, FsObjectStore(str(root/"objects")), wall=wall), wall=wall)
    status, body = con.book_route(None, "GET", REC_SPEC, "primaries")
    assert status == 200
    got = body[SERIAL]
    assert got["missing"] == []
    assert {(e["member"], e["recording"], e["role"]) for e in got["entries"]} == {
        ("srv-a", SERIAL, "primary"), ("srv-b", SERIAL+"-copy", "backup"), (o.cam.name, "card", "card")}
    assert "token" not in json.dumps(body) and "srt://" not in json.dumps(body)


def test_both_reserves_follow_explicit_primary_stop_without_waiting_for_a_start():
    wall = Clock()
    o = _office(wall)
    o.recorders(a_running=False)
    o.recording_domain.collect()
    assert _covers(o.cam.flash, o.cam.local_objects(), EDGE, wall())
    assert _covers(o.b.vars, o.b.objects, BACKUP, wall())
    o.pusher.pass_once(_frames(wall, 5))
    assert len(o.q["srv-b"].drain()) == 5


def test_absent_primary_observation_has_grace_and_keeps_the_working_reserve_channel():
    wall = Clock()
    o = _office(wall)
    o.pusher.pass_once(_frames(wall, 3)); o.q["srv-b"].drain()
    o.down.add("srv-a"); o.a_link.up = False
    wall.advance(46)
    o.domain_pass(a_up=False)
    assert not _covers(o.b.vars, o.b.objects, BACKUP, wall())
    wall.advance(20)
    o.b.objects.put("domain/seen", json.dumps({"ts": wall()}).encode())
    assert _covers(o.b.vars, o.b.objects, BACKUP, wall())
    assert o.pusher.pass_once(_frames(wall, 3))["road"] == "backup"
    assert len(o.q["srv-b"].drain()) >= 3


def test_primary_takeback_uses_assigned_backup_then_card_for_the_remaining_holes():
    wall = Clock(100_000.0)
    o = _office(wall)
    t0 = wall()
    wall.advance(600)
    o.cam.coverage = {"from": t0 - 3600, "to": wall()}
    o.domain_pass(backup_coverage={"from": t0+5, "to": wall()})
    src = resolve(o.a.vars, "ref:"+SERIAL, wall())
    assert [b["cluster"] for b in src.backups] == ["srv-b"]
    ours = [(t0-1800, t0), (wall()-1, wall())]
    fetch, missing = plan_takeback(src, ours, wall(), 30, 0, lambda: o.cam.coverage)
    assert fetch == [((t0, t0+5), "card"), ((t0+5, wall()-1), "backup:srv-b")]
    assert missing == []


def test_viewer_chooses_an_available_assigned_member():
    wall = Clock()
    o = _office(wall)
    assert live_road(o.pusher.entry(), o.dial) == "srv-a"
    o.down.add("srv-a")
    assert live_road(o.pusher.entry(), o.dial) == "srv-b"
    eps = {audience(n): IngestLiveEndpoint(i, lambda t, c: "anna") for n, i in o.ing.items()}
    gw = Gateway("gw-b", where=lambda c: audience(live_road(o.pusher.entry(), o.dial)), endpoint=lambda w: eps[w])
    queue = gw.watch(SERIAL, "anna-token", "anna")
    o.pusher.pass_once(_frames(wall, 4)); gw.pump()
    assert len(queue.drain()) == 4


def test_receiver_unsubscription_does_not_change_assignment_or_other_channels():
    wall = Clock()
    o = _office(wall)
    o.pusher.pass_once(_frames(wall, 3)); o.q["srv-b"].drain()
    o.ing["srv-a"].tees[(SERIAL, "live")].unsubscribe("recorder:srv-a")
    o.pusher.pass_once(_frames(wall, 3, start=3))
    assert [f["n"] for f in o.q["srv-b"].drain()] == [3, 4, 5]
    assert not _covers(o.b.vars, o.b.objects, BACKUP, wall())


def test_a_standby_that_pulls_opens_the_one_session_only_when_the_primary_stops_writing():
    """A camera without the platform, which the second server takes itself (RTSP), watched through A's door. Cold, not on hold: while A's recorder says it writes, B
    holds no session — the camera serves one. A goes silent: B opens its session. A is back: B keeps it a minute,
    so the archives overlap, and closes it. A partition, both servers alive: B cannot see A and opens a second
    session — two recordings for a while, which Lesson 8 of М11 prefers to none."""
    from vms.recording_sources import ColdStandby, neighbour_writes
    wall = Clock()
    o = _office(wall)
    sessions = {"srv-a"}
    standby = ColdStandby(lambda: neighbour_writes(o.a.objects, SERIAL, wall()),
                          lambda: sessions.add("srv-b"), lambda: sessions.discard("srv-b"), wall=wall)
    o.recorders()
    assert standby.pass_once() == "cold: the primary writes" and sessions == {"srv-a"}
    o.a_link.up = False; sessions.discard("srv-a")                     # A is gone, and its session with it
    assert standby.pass_once().startswith("pulling") and sessions == {"srv-b"}
    o.a_link.up = True; sessions.add("srv-a"); o.recorders()           # A is back
    assert standby.pass_once() == "pulling: the overlap" and sessions == {"srv-a", "srv-b"}
    wall.advance(61); o.recorders()
    assert standby.pass_once() == "closed: the primary writes again" and sessions == {"srv-a"}
    o.a_link.up = False                                                # a partition: A writes, B cannot see it
    standby.pass_once()
    assert sessions == {"srv-a", "srv-b"}



def test_a_cold_standby_of_our_camera_asks_the_camera_and_a_partition_opens_no_second_session():
    """Our camera, door open, recorded by A pulling it. B asks the CAMERA who takes its stream — the same door B
    would pull from, nothing new to reach. A is gone: the camera says nobody takes it, B opens its session. A is
    back: a minute of overlap, then B closes. The servers lose sight of each other while A pulls: the camera
    still says A takes it, and B stays cold — one session."""
    from vms.recording_sources import ColdStandby, camera_taken
    wall = Clock()
    cam = DeviceCluster("SN6002", FakeVariables(), wall=wall)
    cam.boot()                                                         # its door open to the site
    door = cam.cluster().objects

    def take(who):
        cam.taken_by.add(who); cam.publish()

    def let_go(who):
        cam.taken_by.discard(who); cam.publish()

    take("srv-a")
    standby = ColdStandby(lambda: camera_taken(door, "SN6002", "srv-b"), lambda: take("srv-b"), lambda: let_go("srv-b"),
                          wall=wall)
    assert standby.pass_once() == "cold: the primary writes" and cam.taken_by == {"srv-a"}
    let_go("srv-a")                                                    # A is gone
    assert standby.pass_once().startswith("pulling") and cam.taken_by == {"srv-b"}
    take("srv-a")                                                      # A is back
    assert standby.pass_once() == "pulling: the overlap"
    wall.advance(61)
    assert standby.pass_once() == "closed: the primary writes again" and cam.taken_by == {"srv-a"}
    # the servers lose sight of each other: nothing changes for B, which never asked A
    assert standby.pass_once() == "cold: the primary writes" and cam.taken_by == {"srv-a"}
    cam.power_off()
    assert standby.pass_once() == "cold: cannot tell"                  # the camera does not answer: nothing to pull



def test_a_camera_that_a_pulls_is_not_called_uncovered_and_its_card_does_not_record():
    """Feedback AP — a defect of the course. The camera is pulled by A over RTSP (its door is open, it does not
    push); it still holds a poll, as every member camera does. No recorder subscribes to A's ingest for it — A's
    recorder pulls. Asked only "should A record it?", the ingest would call it uncovered: the card would record all
    the time and the camera would push a second stream to B. The ingest speaks only of a camera that pushes to it;
    of this one it says nothing, and the book — A writes it — decides."""
    from vms.ingest import edge_gate
    wall = Clock()
    o = _office(wall)
    o.cam.pushes = False; o.cam.door_open = True                       # pulled by A now
    o.ing["srv-a"].tees[(SERIAL, "live")].unsubscribe("recorder:srv-a")
    o.ing["srv-b"].tees[(SERIAL, "live")].unsubscribe("recorder:srv-b")
    o.domain_pass(); o.domain_pass()
    from vms.recording_books import source
    assert source(o.a.vars.get("domain/cam/sources")[0], SERIAL).value["live_url"].startswith("rtsp://")
    assert set(o.pusher.entry()["channels"]) == {"srv-a", "srv-b"}
    o.pusher.pass_once(_frames(wall, 3))
    assert edge_gate(o.pusher)(EDGE) is False


# -- the recorders themselves: placed, started from the book, written from the ingest (the scenario's O6) --------------
def _written_office(wall):
    """The office of `_office` with its RECORDERS doing the work the fixture above does by hand: on each server a
    recorder that hosts the ingest and writes (`ingest_recorder(volume=…)`), its recording placed on it by its cluster's
    controller, started from its cluster's copy of the source book (`ingest://<server>/<ref>`) and written from what the
    camera pushes (`vms.ingestrec`). Nobody subscribes to an ingest and nobody writes a heartbeat by hand: what the domain
    and the camera learn — `running`, `have` — the recorders said (М12B урок 3; «камера — офис — центр», O6)."""
    import tempfile
    from vms import volumes
    from vms.config import REC_SPEC
    from w2cplatform.spec import SpecController
    from tests.vmsconftest import TEST_QUOTA
    fed = Federation()
    b, _ = make_cluster("srv-b", domain=True)
    a, a_link = make_cluster("srv-a")
    fed.add(a); fed.add(b)
    signer = Signer("acme", b.vars, now=wall)
    DomainPublisher(b.vars).publish_keys(signer.tokens.keyset())
    agents = {"srv-a": DomainAgent("srv-a", b.vars, a.vars, now=wall),
              "srv-b": DomainAgent("srv-b", b.vars, b.vars, now=wall, seen_store=b.objects)}
    for x in agents.values():
        report_sync(x)                                                       # each server's key set: what its ingest checks with
    ctl = {"srv-a": SpecController(REC_SPEC, a.vars, a.objects, wall=wall, cluster="srv-a"),
           "srv-b": SpecController(REC_SPEC, b.vars, b.objects, wall=wall, cluster="srv-b")}
    ctl["srv-a"].create({"name": SERIAL, "cam": f"ref:{SERIAL}"})     # the primary, on A
    volumes.write(b.vars, {"name": "copy", "kind": "backup", "server": "r-srv-b", "quota_bytes": TEST_QUOTA,   # (the recorder's
                           "url": "file://" + tempfile.mkdtemp(prefix="copy-")})                         # server: its name)
    ctl["srv-b"].create({"name": f"{SERIAL}-copy", "cam": f"ref:{SERIAL}", "home": "copy", "when": "offline"})   # the backup, on B
    recs = {n: ingest_recorder(n, urls[0], wall, c.vars, c.objects, name=f"r-{n}", volume=tempfile.mkdtemp(prefix=f"{n}-"))
            for n, urls, c in (("srv-a", A_URLS, a), ("srv-b", B_URLS, b))}
    ing = {n: r.ingest for n, r in recs.items()}

    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, pushes=True)
    cam.boot(); cam.door_open = False
    fed.add(member_copy(cam.name, b.objects, wall=wall))
    cam_agent = DomainAgent(cam.name, b.vars, cam.flash, now=wall, domain_objects=b.objects,
                            published=cam.local_objects(), seen_store=cam.local_objects())
    report_sync(cam_agent)
    view = ReadView(fed, wall=wall); view.refresh()
    crossings = BookInputs(b.vars, view, wall)
    recording_domain = RecordingDomain(crossings, signer, agents=[*agents.values(), cam_agent], devices=[cam])
    recording_domain.assign(SERIAL, "srv-a", copies=["srv-b"])
    recording_domain.collect()
    down = set()

    def servers():                                                     # each server that is on: placement, its recorder's pass
        for n, r in recs.items():
            if n in down:
                continue
            ctl[n].ensure_placed(); ctl[n].publish_snapshot()
            r.lease_pass(); r.reconcile_once(); r.heartbeat_once()

    def books():
        cam.publish(); report_sync(cam_agent)
        if "srv-a" not in down:
            report_sync(agents["srv-a"])
        view.refresh(); recording_domain.collect()
        report_sync(agents["srv-b"]); report_sync(cam_agent)
        if "srv-a" not in down:
            report_sync(agents["srv-a"])                                     # A's source book, carried home

    def domain_pass():
        servers(); books()

    def dial(url):
        for name, i in ing.items():
            if url in i.urls and name not in down:
                return i
        raise Unreachable(f"{url} did not answer")

    pusher = camera_pusher(SERIAL, cam.flash, dial, clock=wall, ring_seconds=30)
    for c in ctl.values():
        c.publish_snapshot()                                           # what each records: the domain finds B's backup in it
    books()                                                            # the books home before the recorders' first pass:
    domain_pass()                                                      # a start that finds no source burns an epoch (the gate's)
    return SimpleNamespace(a=a, b=b, a_link=a_link, recs=recs, ing=ing, cam=cam, pusher=pusher, down=down,
                           domain_pass=domain_pass, servers=servers, recording_domain=recording_domain)


def _sensor(t0, n, start=0):
    """What the camera's sensor gives, as the pusher pushes it (`ingest.wire`): frames `start`… of twenty-five a second
    from `t0`, a key frame each second, each carrying its sample record — what a recorder writes."""
    from vms.ingest import wire
    from vms.obsd import archive_ms, video
    from vms.worker import FAKE_PPS, FAKE_SPS
    out = []
    for i in range(start, start + n):
        t, key = t0 + i * 0.04, i % 25 == 0
        body = (FAKE_SPS + FAKE_PPS + b"\x00\x00\x00\x01\x65" if key else b"\x00\x00\x00\x01\x41") + b"\x80" * 200
        out.append(dict(wire(video(archive_ms(t), archive_ms(t + 0.04), body, key, 1280, 720)), n=i))
    return out


def _status(rec, rid):
    rec.heartbeat_once()
    hb = json.loads(rec.objects.get(f"rec/heartbeats/{rec.name}"))
    return next(st for st in hb["status"] if str(st["id"]) == rid)


def test_the_recorder_takes_what_the_camera_pushes_writes_it_says_have_and_the_backup_writes_while_a_is_off():
    """The scenario «камера — офис — центр», finding O6: a recording `{name: SN…, cam: ref:SN…}` stood `waiting`, «camera
    held by nobody» — the recorder looked for the camera in its own cluster's heartbeats and never in the source book, and
    the tests subscribed to the ingest for it by hand. Now, as the product's recorder (`Source` over `ResolveRef`, its
    actuator's `startIngest`): A's recording is started from A's source book — `ingest://srv-a/<ref>` — and subscribes to
    the ingest A's recorder hosts, and that is what makes the camera push. What it pushes is written as `<ref>/e1`; the
    heartbeat says how far (`written_through`), the camera is told it as `have` in its next poll, and the book of primaries
    says `running`. A goes off: the camera takes its second road, to B, and B's backup — subscribed the same way, `when:
    offline`, never `waiting` for a camera that does not come — writes `<ref>-copy/e1`."""
    wall = Clock(1_760_000_000.0)
    o = _written_office(wall)
    ra, rb = o.recs["srv-a"], o.recs["srv-b"]
    st = _status(ra, SERIAL)
    assert (st["phase"], st["source"], st["via"]) == ("running", f"ingest://srv-a/{SERIAL}", "ingest"), st
    assert o.ing["srv-a"].wanted(SERIAL) and o.ing["srv-a"].taken(SERIAL)            # the recorder's want: the camera pushes
    assert _status(rb, f"{SERIAL}-copy")["phase"] == "running"                        # B's standby subscribed, and quiet
    t0 = wall()
    out = o.pusher.pass_once(_sensor(t0, 50))
    assert (out["road"], out["pushed"]) == ("primary", 50), out
    st = _status(ra, SERIAL)
    assert st["samples_written"] == 50 and abs(st["written_through"] - (t0 + 49 * 0.04)) < 0.01, st
    ra.store.seal()
    spans = ra.store.spans(SERIAL)
    assert [s.stream for s in spans] == [f"{SERIAL}/e1"] and abs(spans[0].start - t0) < 0.01, spans
    token = o.pusher.assigned.stream_token()
    assert abs(o.ing["srv-a"].poll(token, SERIAL, camera_now=wall())["have"] - (t0 + 49 * 0.04)) < 0.01   # the camera's `have`
    o.domain_pass()
    assert _primary(o).value["running"] is True                                        # the book of primaries: A writes it
    assert _primary(o).value["running"] is True
    assert rb.store.spans(f"{SERIAL}-copy") == []                                    # one stream, to A: the backup wrote nothing

    o.down.add("srv-a"); o.a_link.up = False                                          # A is off
    wall.advance(46)
    o.domain_pass()
    rb.primary_needs_cover(rb.rows[0])
    wall.advance(20)
    rb.take_pushed()
    second = wall()
    out = o.pusher.pass_once(_sensor(second, 50))
    assert out["road"] == "backup", out
    st = _status(rb, f"{SERIAL}-copy")
    assert st["phase"] == "running" and st["samples_written"] == 50, st
    assert abs(st["written_through"] - (second + 49 * 0.04)) < 0.01, st
    rb.store.seal()
    spans = rb.store.spans(f"{SERIAL}-copy")
    assert [s.stream for s in spans] == [f"{SERIAL}-copy/e1"] and abs(spans[0].start - second) < 0.01, spans


def test_a_recording_the_camera_brings_nothing_to_is_waiting_and_the_book_says_so_until_the_first_frame():
    """Subscribed, and nothing comes — the camera has nothing to push, or cannot reach this ingest. Past the start's grace
    the recording says `waiting`, with why (`push_waiting`, the product's `statusFix`), not `running`: the book of
    primaries would tell the camera's card that it is recorded. Its first frame makes it a recording again, under the
    same epoch — nothing was restarted for the wait."""
    wall = Clock(1_760_000_000.0)
    o = _written_office(wall)
    ra = o.recs["srv-a"]
    wall.advance(25)
    o.domain_pass()
    st = _status(ra, SERIAL)
    assert st["phase"] == "waiting" and st["push_waiting"] is True and "pushed nothing" in st["why"], st
    o.domain_pass()
    assert _primary(o).value["running"] is False
    o.pusher.pass_once(_sensor(wall(), 25))
    st = _status(ra, SERIAL)
    assert st["phase"] == "running" and st["samples_written"] == 25 and st["epoch"] == 1, st


def _primary(o):
    from vms.recording_books import primary
    return primary(o.cam.flash.get("domain/rec/primaries")[0], SERIAL, "srv-a")
