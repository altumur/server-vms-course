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
import json
from types import SimpleNamespace

from cluster.variables import FakeVariables

from domain.agent import DomainAgent, DomainPublisher
from domain.crossing import Crossings, plan_takeback, resolve
from domain.device import DeviceCluster
from domain.federation import Federation, Unreachable
from domain.gateway import Gateway
from domain.ingest import CameraPusher, Ingest, IngestLiveEndpoint, audience, live_road
from domain.readview import ReadView
from domain.signer import Signer
from domain.uplink import member_copy
from tests.conftest import Clock, make_cluster

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
    from domain.agent import ClusterTrust
    from domain.ingest import should_from_snapshot
    ing = {"srv-a": Ingest("srv-a", A_URLS, keys=lambda: ClusterTrust(a.vars).keyset(), wall=wall,
                           should=should_from_snapshot(a.objects, wall)),
           "srv-b": Ingest("srv-b", B_URLS, keys=lambda: ClusterTrust(b.vars).keyset(), wall=wall,
                           should=should_from_snapshot(b.objects, wall))}
    ing["srv-a"].announce(a.objects); ing["srv-b"].announce(b.objects)
    agents = {"srv-a": DomainAgent("srv-a", b.vars, a.vars, now=wall),
              "srv-b": DomainAgent("srv-b", b.vars, b.vars, now=wall, seen_store=b.objects)}
    for x in agents.values():
        x.sync()

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
    cam_agent.sync()
    view = ReadView(fed, wall=wall); view.refresh()
    crossings = Crossings(b.vars, view, wall, issuer=signer.tokens)
    crossings.record(SERIAL, on="srv-a")

    def recorders(a_running=True, backup_coverage=None):              # what each server's recorder says
        from w2cplatform.contract import Heartbeat, Subsystem
        rec_a.publish_snapshot()
        st = [{"id": SERIAL, "cam": f"ref:{SERIAL}", "enabled": True, "phase": "running" if a_running else "pending"}]
        a.objects.put(Subsystem("rec").heartbeat_key("r-a"), Heartbeat("r-a", wall(), st, {}).to_bytes())
        cov = backup_coverage or {"from": wall() - 60, "to": wall()}
        b.objects.put(Subsystem("rec").heartbeat_key("r-b"), Heartbeat("r-b", wall(), [
            {"id": f"{SERIAL}-copy", "cam": f"ref:{SERIAL}", "enabled": True, "phase": "running", "coverage": cov}],
            {"archive_url": "http://srv-b:9100/"}).to_bytes())

    def domain_pass(a_up=True, backup_coverage=None):
        cam.publish(); cam_agent.sync()
        if a_up:
            recorders(backup_coverage=backup_coverage)
            agents["srv-a"].sync()
        view.refresh(); crossings.publish(); crossings.publish_primaries()
        agents["srv-b"].sync(); cam_agent.sync()
        if a_up:
            agents["srv-a"].sync()

    down = set()

    def dial(url):
        for name, i in ing.items():
            if url in i.urls and name not in down:
                return i
        raise Unreachable(f"{url} did not answer")

    q = {n: (i.want(SERIAL, f"recorder:{n}"), i.subscribe(SERIAL, f"recorder:{n}", maxsize=1000))[1] for n, i in ing.items()}
    pusher = CameraPusher(SERIAL, cam.flash, dial, clock=wall, ring_seconds=30)
    domain_pass()
    return SimpleNamespace(fed=fed, a=a, b=b, a_link=a_link, ing=ing, q=q, cam=cam, pusher=pusher, crossings=crossings,
                           domain_pass=domain_pass, recorders=recorders, down=down, dial=dial, rec_a=rec_a)


def _covers(vars_, objects, row, now):
    """The standby's gate, as the recorder runs it (`vms.recworker.RecWorker.carried_primary`)."""
    from vms.recworker import RecWorker
    me = SimpleNamespace(vars=vars_, objects=objects, _not_written_since={}, CARRIED_LOST_AFTER=45.0, START_GRACE=20.0)
    return RecWorker.carried_primary(me, row, now)


EDGE = {"id": "card", "cam": f"ref:{SERIAL}", "home": "card", "when": "offline"}
BACKUP = {"id": f"{SERIAL}-copy", "cam": f"ref:{SERIAL}", "home": "copy", "when": "offline"}


def _frames(wall, n, start=0):
    return [{"t": wall() + i * 0.04, "n": start + i} for i in range(n)]


def test_while_a_writes_the_camera_sends_one_stream_to_a_and_neither_standby_records():
    wall = Clock()
    o = _office(wall)
    e = o.pusher.entry()
    assert e["backup"]["cluster"] == "srv-b" and e["backup"]["ingest"]["urls"] == B_URLS     # its second road
    assert o.pusher.pass_once(_frames(wall, 5))["road"] == "primary"
    assert len(o.q["srv-a"].drain()) == 5 and o.q["srv-b"].drain() == []                    # one stream, to A
    assert not _covers(o.cam.flash, o.cam.local_objects(), EDGE, wall())                     # the card holds
    assert not _covers(o.b.vars, o.b.objects, BACKUP, wall())                                # the backup holds


def test_a_dies_and_both_standbys_record_the_card_from_its_sensor_the_backup_from_the_one_stream():
    wall = Clock()
    o = _office(wall)
    o.pusher.pass_once(_frames(wall, 5)); o.q["srv-a"].drain()
    o.down.add("srv-a"); o.a_link.up = False                          # server A is gone
    wall.advance(5)
    o.domain_pass(a_up=False)                                         # the domain, on B, sees A silent
    out = o.pusher.pass_once(_frames(wall, 5, start=5))
    assert out["road"] == "backup" and [f["n"] for f in o.q["srv-b"].drain()] == [5, 6, 7, 8, 9]
    assert _covers(o.cam.flash, o.cam.local_objects(), EDGE, wall())  # the card records
    assert _covers(o.b.vars, o.b.objects, BACKUP, wall())             # and so does the backup
    assert "the backup" in o.pusher.state


def test_when_as_ingest_cannot_say_the_book_decides_that_a_whose_recorder_stopped_does_not_take_the_stream():
    """A's ingest answers but has no word on the recording (it cannot read its cluster's rows); A's recorder has
    stopped: the book says A should write and does not, and it is not a start. The camera goes to the backup on
    the book's word — "the primary does not take the stream" is about the recording, not about who answers."""
    wall = Clock()
    o = _office(wall)
    o.ing["srv-a"].should = None                                      # the ingest has no word of its own
    o.pusher.pass_once(_frames(wall, 3)); o.q["srv-a"].drain()
    wall.advance(5)
    o.domain_pass()
    o.recorders(a_running=False)                                      # named, and not running: a stop
    o.crossings.publish_primaries()
    o.cam.publish()                                                    # the book reaches the camera on its agent's pass
    DomainAgent(o.cam.name, o.b.vars, o.cam.flash, now=wall, domain_objects=o.b.objects,
                published=o.cam.local_objects(), seen_store=o.cam.local_objects()).sync()
    assert o.pusher.pass_once(_frames(wall, 3, start=3))["road"] == "backup"
    assert [f["n"] for f in o.q["srv-b"].drain()] == [3, 4, 5]


def test_a_back_takes_everything_home_from_the_backup_first_and_the_card_for_the_rest():
    """A was down for ten minutes. The camera switched its stream to B at once, but B's recording starts a few
    seconds into the outage (the switch, the gate) — those seconds are only on the card. A, back, gets the
    camera's stream again, and its plan takes the hole from the backup where the backup has it, and the rest
    from the card, asked NOW."""
    wall = Clock(100_000.0)
    o = _office(wall)
    t0 = wall()
    o.down.add("srv-a"); o.a_link.up = False
    wall.advance(600)
    o.domain_pass(a_up=False)
    o.pusher.pass_once(_frames(wall, 3)); o.q["srv-b"].drain()
    o.down.discard("srv-a"); o.a_link.up = True
    o.cam.coverage = {"from": t0 - 3600, "to": wall()}                # the card recorded the whole outage
    o.domain_pass(backup_coverage={"from": t0 + 5, "to": wall()})     # B holds it from its fifth second
    assert o.pusher.pass_once(_frames(wall, 3))["road"] == "primary"  # A takes the stream again
    assert o.q["srv-b"].drain() == []
    src = resolve(o.a.vars, f"ref:{SERIAL}", wall())
    assert [b["cluster"] for b in src.backups] == ["srv-b"] and src.backups[0]["url"] == "http://srv-b:9100"
    ours = [(t0 - 1800, t0), (wall() - 1, wall())]                    # A's own archive: the hole is the outage
    fetch, missing = plan_takeback(src, ours, wall(), keep_days=30, settle=0, ask_device=lambda: o.cam.coverage)
    assert fetch == [((t0, t0 + 5), "card"), ((t0 + 5, wall() - 1), "backup:srv-b")]
    assert missing == []


def test_a_viewer_opens_the_camera_where_its_one_stream_is_going():
    wall = Clock()
    o = _office(wall)
    e = o.pusher.entry()
    assert live_road(e, o.dial) == "primary"
    o.down.add("srv-a"); o.a_link.up = False
    wall.advance(5); o.domain_pass(a_up=False)
    e = o.pusher.entry()
    assert live_road(e, o.dial) == "backup"
    road = {"primary": audience("srv-a"), "backup": audience("srv-b")}
    eps = {audience(n): IngestLiveEndpoint(i, lambda t, c: "anna") for n, i in o.ing.items()}
    gw = Gateway("gw-b", where=lambda c: road[live_road(o.pusher.entry(), o.dial)], endpoint=lambda w: eps[w])
    vq = gw.watch(SERIAL, "anna-token", "anna")
    o.pusher.pass_once(_frames(wall, 4))
    gw.pump()
    assert len(vq.drain()) == 4                                        # from B's ingest: where the camera is



# -- failover without the domain: what the stream says -----------------------------------------------------------
def test_a_whose_recorder_let_go_is_left_at_once_on_its_own_ingests_word_no_domain_asked():
    """A's recorder stops taking the stream. The book still says "written" — no domain pass has run. A's ingest
    says it on the next poll: it should record the camera and no recorder takes it. The camera goes to B on
    that word, and both standbys know it from the stream: the card because its camera did not hand the stream
    on, the backup because the camera came to it."""
    from domain.ingest import backup_gate, edge_gate
    wall = Clock()
    o = _office(wall)
    o.pusher.pass_once(_frames(wall, 3)); o.q["srv-a"].drain()
    o.ing["srv-a"].tees[(SERIAL, "live")].unsubscribe("recorder:srv-a")          # A's recorder let go
    out = o.pusher.pass_once(_frames(wall, 3, start=3))
    assert out["road"] == "backup" and [f["n"] for f in o.q["srv-b"].drain()] == [3, 4, 5]
    assert json.loads(o.cam.flash.get("domain/primaries")[0][SERIAL])["written"] is True   # the book: behind
    assert edge_gate(o.pusher)(EDGE) is True and backup_gate(o.ing["srv-b"])(BACKUP) is True


def test_the_domain_dies_with_a_and_both_standbys_start_at_once_anyway():
    """Suppose the domain lived on A and died with it. No book will say "not written" until it goes stale — 45 s.
    Nothing waits for it: the camera cannot reach A's ingest and goes to B; the card and the backup start from
    what the stream says; the book, stale or not, is only the fallback."""
    from domain.ingest import backup_gate, edge_gate
    wall = Clock()
    o = _office(wall)
    o.pusher.pass_once(_frames(wall, 3)); o.q["srv-a"].drain()
    o.down.add("srv-a"); o.a_link.up = False                           # A is gone; no domain pass runs after
    wall.advance(2)
    assert o.pusher.pass_once(_frames(wall, 3, start=3))["road"] == "backup"
    assert not _covers(o.cam.flash, o.cam.local_objects(), EDGE, wall())          # the book still says written
    assert edge_gate(o.pusher)(EDGE) is True                                        # the stream says otherwise
    assert backup_gate(o.ing["srv-b"])(BACKUP) is True


def test_a_standby_that_pulls_opens_the_one_session_only_when_the_primary_stops_writing():
    """A camera the second server takes itself (RTSP). Cold, not on hold: while A's recorder says it writes, B
    holds no session — the camera serves one. A goes silent: B opens its session. A is back: B keeps it a minute,
    so the archives overlap, and closes it. A partition, both servers alive: B cannot see A and opens a second
    session — two recordings for a while, which Lesson 8 of М11 prefers to none."""
    from domain.crossing import ColdStandby
    wall = Clock()
    o = _office(wall)
    sessions = {"srv-a"}
    standby = ColdStandby(o.a.objects, SERIAL, lambda: sessions.add("srv-b"), lambda: sessions.discard("srv-b"), wall=wall)
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
