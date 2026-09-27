"""Lesson 17 — a chain: site, office, centre.

Cameras nobody can dial, recorded by an office nobody above can dial, watched from a centre everybody can
reach. Each level dials the level above: the camera its office (media) and the centre (books, reports); the
office the centre. The want travels down, the stream up. The star: an office that cannot be pushed to takes
its cameras' streams from the centre. The relay: a camera that can reach only its office reaches the domain
through it both ways — the office relays down what the domain left for it and carries its report up in one
summary object.
"""
import json

from cluster.variables import FakeVariables

from domain.agent import ClusterTrust, DomainAgent, DomainPublisher
from domain.chain import Forwarder, bundle, publish_upstream
from domain.crossing import Crossings
from domain.device import DeviceCluster, Ram
from domain.federation import Federation, Unreachable
from domain.gateway import Gateway
from domain.ingest import LINGER, CameraPusher, Ingest, IngestLiveEndpoint, audience
from domain.readview import ReadView
from domain.signer import Signer
from domain.uplink import member_copy
from tests.conftest import Clock, make_cluster

SERIAL = "SN7001"
OFFICE_URLS = ["srt://ingest.east.office:9000"]
CENTRE_URLS = ["srt://ingest.centre.example:9000"]


def _chain(wall, star=frozenset()):
    from vms.config import REC_SPEC
    from w2cplatform.spec import SpecController
    fed = Federation()
    north, _ = make_cluster("north", domain=True)                     # the centre: hosts the domain, has an ingest
    east, _ = make_cluster("east")                                     # the office: records the site's cameras
    fed.add(north); fed.add(east)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    centre = Ingest("north", CENTRE_URLS, keys=lambda: ClusterTrust(north.vars).keyset(), wall=wall)
    centre.announce(north.objects)
    office_agent = DomainAgent("east", north.vars, east.vars, now=wall)
    office_agent.sync()
    office = Ingest("east", OFFICE_URLS, keys=lambda: ClusterTrust(east.vars).keyset(), wall=wall)
    office.announce(east.objects)
    SpecController(REC_SPEC, east.vars, east.objects, wall=wall).create({"name": SERIAL, "cam": f"ref:{SERIAL}"})

    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, pushes=True)
    cam.boot(); cam.door_open = False                                  # nobody dials the camera
    fed.add(member_copy(cam.name, north.objects, wall=wall))
    cam_agent = DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects, published=cam.local_objects())
    cam_agent.sync()
    view = ReadView(fed, wall=wall); view.refresh()
    crossings = Crossings(north.vars, view, wall, issuer=signer.tokens, centre="north", star=star)
    crossings.record(SERIAL, on="east")

    dialled = []

    def dial_from(who, reachable):
        def dial(url):
            dialled.append((who, url))
            if url in OFFICE_URLS and "office" in reachable:
                return office
            if url in CENTRE_URLS:
                return centre
            raise Unreachable(f"{url} did not answer {who}")
        return dial

    pusher = CameraPusher(SERIAL, cam.flash, dial_from("camera", {"office"} if not star else set()), clock=wall)
    fwd = Forwarder("east", office, east.vars, dial_from("office", set()),
                    archive=lambda ref, t0, t1: [("east-archive", ref, t0, t1)], needs=lambda ref: True)

    def domain_pass():
        view.refresh(); crossings.publish(); crossings.publish_primaries()
        publish_upstream(crossings, "north", star=star)
        cam_agent.sync(); office_agent.sync()

    domain_pass.crossings = crossings
    domain_pass()
    return north, east, centre, office, pusher, fwd, dialled, domain_pass


def test_a_viewer_in_the_centre_the_want_travels_down_and_the_stream_up():
    wall = Clock()
    north, east, centre, office, pusher, fwd, dialled, _ = _chain(wall)
    gw = Gateway("gw-centre", where=lambda c: audience("north"), endpoint=lambda w: IngestLiveEndpoint(centre, lambda t, c: "anna"))
    vq = gw.watch(SERIAL, "anna-token", "anna")                        # the centre wants it
    assert pusher.pass_once(["f0"])["pushed"] == 0                     # not yet: the office has not heard
    fwd.pass_once()                                                    # the office hears, and wants it from the camera
    assert pusher.pass_once(["f1", "f2"])["pushed"] == 2
    fwd.pass_once()                                                    # up it goes
    gw.pump()
    assert vq.drain() == ["f1", "f2"]

    gw.leave(SERIAL, "anna"); wall.advance(LINGER + 1)
    fwd.pass_once()                                                    # the centre no longer wants it: nor does the office
    wall.advance(LINGER + 1)
    assert pusher.pass_once(["f3"])["pushed"] == 0
    assert {u for who, u in dialled if who == "camera"} == set(OFFICE_URLS)       # the camera dialled its office only


def test_the_centres_copy_is_fed_by_the_office_and_the_camera_serves_one_session():
    """An important camera kept in the centre too (a backup recording on the centre's volume, М10B Lesson 26).
    The camera still serves one session — to its office; the centre receives from the office."""
    wall = Clock()
    north, east, centre, office, pusher, fwd, dialled, _ = _chain(wall)
    centre.want(SERIAL, "recorder:centre")
    rq = centre.subscribe(SERIAL, "recorder:centre")
    fwd.pass_once(); pusher.pass_once(["a", "b", "c"]); fwd.pass_once()
    assert rq.drain() == ["a", "b", "c"]
    assert len(office.tees[(SERIAL, "live")].subscribers) == 1         # one subscriber of the camera's stream: the forwarder


def test_the_office_archive_asked_for_by_the_centre_is_uploaded_by_the_office():
    wall = Clock()
    north, east, centre, office, pusher, fwd, dialled, _ = _chain(wall)
    rid = centre.request_range(SERIAL, 5000.0, 5600.0)
    fwd.pass_once()
    assert centre.landed(SERIAL) == [(5000.0, 5600.0)]
    assert centre.answer(SERIAL, rid) == [("east-archive", SERIAL, 5000.0, 5600.0)]   # out of the office's archive


def test_the_star_the_camera_pushes_to_the_centre_and_the_office_pulls_its_cameras_from_there():
    """An office behind a mobile operator, or a cloud cluster that takes no inbound: nobody can push to it.
    The camera's book names the centre; the office, wanting the stream for its recorder, pulls it — calling
    in. Nobody dials the camera, nobody dials the office."""
    wall = Clock()
    north, east, centre, office, pusher, fwd, dialled, _ = _chain(wall, star={"east"})
    assert pusher.entry()["ingest"]["urls"] == CENTRE_URLS
    rq = office.subscribe(SERIAL, "recorder:east")
    fwd.pass_once()                                                    # the office wants it: pulling is wanting at the centre
    assert pusher.pass_once(["s1", "s2"])["pushed"] == 2               # the camera pushes to the centre
    fwd.pass_once()                                                    # the office pulls them down
    assert rq.drain() == ["s1", "s2"]
    assert {(w, u) for w, u in dialled} <= {("camera", u) for u in CENTRE_URLS} | {("office", u) for u in CENTRE_URLS}


def _site_of(n_offices, per_office, wall):
    north, _ = make_cluster("north", domain=True)
    store = _Counting(Ram())
    offices, fed = {}, Federation()
    fed.add(north)
    for o in range(n_offices):
        office_store = Ram()
        cams = []
        for i in range(per_office):
            d = DeviceCluster(f"SN{o:02d}{i:03d}", FakeVariables(), wall=wall)
            d.boot()
            cams.append((d, DomainAgent(d.name, north.vars, d.flash, now=wall, domain_objects=office_store, published=d.local_objects())))
            fed.add(member_copy(d.name, store, wall=wall, via=f"office-{o}"))
        offices[f"office-{o}"] = (office_store, cams)
    return north, store, offices, fed


class _Counting:
    def __init__(self, inner): self.inner, self.puts, self.largest = inner, 0, 0
    def put(self, k, v): self.puts += 1; self.largest = max(self.largest, len(v)); return self.inner.put(k, v)
    def get(self, k): return self.inner.get(k)
    def list(self, p): return self.inner.list(p)
    def delete(self, k): return self.inner.delete(k)


def test_the_summary_report_one_object_per_office_and_the_price_of_it():
    """Cameras that can reach only their office report to it, and the office folds their reports into one
    object in the centre. The price: when an office goes quiet, its cameras go quiet with it — they have no
    other road, and the centre cannot tell the office from its sites. The side effect: three hundred cameras
    in ten offices are ten writes per round instead of eight hundred."""
    wall = Clock()
    north, store, offices, fed = _site_of(10, 30, wall)

    def round_(skip=()):
        for name, (office_store, cams) in offices.items():
            for d, a in cams:
                d.publish(); a.sync()
            if name not in skip:
                bundle(name, [d.name for d, _ in cams], office_store, store)

    round_()
    view = ReadView(fed, wall=wall); view.refresh()
    assert view.list(size=400)["total"] == 300 and view.list()["complete"]
    wall.advance(10); store.puts = 0
    round_()
    assert store.puts == 10                                             # one per office per round
    assert store.largest < 64 * 1024                                    # a bundle fits a Variable: ~30 cameras an office
    view.refresh()                                                      # the domain sees this round's reports

    wall.advance(60); round_(skip=("office-3",))
    view.refresh()
    page = view.list(size=400)
    silent = {n for n, s in page["clusters"].items() if s == "unreachable"}
    assert silent == {d.name for d, _ in offices["office-3"][1]}        # its thirty cameras, all at once


def test_a_camera_that_sees_only_its_office_reaches_the_domain_through_it_both_ways():
    """The summary report's reason: the camera can reach its office and nothing else. The office is its road
    to the domain in both directions — the office's agent relays down everything the domain leaves for the
    camera, the camera reports into the office, and the office carries the report up in its bundle. Grants,
    a kept edit and its outcome, the book with the stream token, the list in the centre: all through the office.
    And how current the camera's books are is when the OFFICE last reached the domain."""
    from vms.config import REC_SPEC
    from vms.recworker import DOMAIN_SEEN
    from w2cplatform.spec import SpecController
    from domain.api import ConsoleAPI
    from domain.chain import Relay
    from domain.federation import DomainDirectory
    from domain.grants import Grant
    from domain.pending import PendingEdits

    wall = Clock()
    fed = Federation()
    north, north_link = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    fed.add(north); fed.add(east)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, pushes=True)
    cam.boot(); cam.door_open = False
    fed.add(member_copy(cam.name, north.objects, wall=wall, via="east"))
    office_agent = DomainAgent("east", north.vars, east.vars, now=wall, domain_objects=north.objects,
                               bundle_store=east.objects, bundle_members=[cam.name], relay_members=[cam.name])
    through = Relay(east.vars, east.objects)                           # all the camera can reach
    cam_agent = DomainAgent(cam.name, through.vars, cam.flash, now=wall, console=cam.local_console(), current=cam.current,
                            domain_objects=through.objects, published=cam.local_objects(), seen_store=cam.local_objects())
    office = Ingest("east", OFFICE_URLS, keys=lambda: ClusterTrust(east.vars).keyset(), wall=wall)
    office.announce(east.objects)
    SpecController(REC_SPEC, east.vars, east.objects, wall=wall).create({"name": SERIAL, "cam": f"ref:{SERIAL}"})

    def passes():
        office_agent.sync(); cam_agent.sync(); office_agent.sync()

    passes()
    view = ReadView(fed, wall=wall); view.refresh()
    assert [r["ref"] for r in view.list()["rows"] if r["cluster"] == cam.name] == [SERIAL]   # up: the bundle

    DomainPublisher(north.vars).publish_grants(cam.name, [Grant("anna", "edit", None, wall() + 3600)])
    passes()
    assert [g.subject for g in ClusterTrust(cam.flash).grants()] == ["anna"]                   # down: the relay

    pending = PendingEdits(north.vars, wall)

    def no_door(name):
        raise Unreachable(f"{name} is reached only through its office")

    api = ConsoleAPI(DomainDirectory(fed, wall=wall), no_door, verifier=lambda t: t, pending=pending, last_known=view.last_known)
    assert api.update_camera(SERIAL, {"name": "yard"}, idempotency_key="k1", token="anna")["pending"]
    passes()
    assert cam.row()["name"] == "yard"                                 # carried down by the office, applied by the camera
    view.refresh(); pending.collect(fed)
    assert pending.of(cam.name) == {}                                  # the outcome came up in the bundle

    crossings = Crossings(north.vars, view, wall, issuer=signer.tokens)
    crossings.record(SERIAL, on="east"); crossings.publish_primaries()
    passes()
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: office if url in OFFICE_URLS else (_ for _ in ()).throw(Unreachable(url)))
    office.want(SERIAL, "recorder:east")
    assert pusher.pass_once(["f"])["pushed"] == 1                      # the stream token came down the same road

    last = wall()
    north_link.up = False                                              # the office loses the centre
    for _ in range(4):
        wall.advance(20); office_agent.sync(); cam_agent.sync()        # the camera still reaches its office
    assert json.loads(cam.ram.get(DOMAIN_SEEN))["ts"] == last          # …and knows its books are as old as the office's


def test_an_ask_from_a_camera_at_another_site_goes_by_the_centre_and_the_office_carries_it_down():
    """The gate camera is at another site: it reaches the centre, not the east office. Its book names two roads
    to the yard camera — the office that records it, then the centre the office forwards it to. The office's
    ingest does not answer, so the ask is left at the centre; the office's forwarder, polling the centre, carries
    it down to the camera's poll, and the outcome back up."""
    from domain.ingest import Asker, publish_asks
    wall = Clock()
    north, east, centre, office, pusher, fwd, dialled, domain_pass = _chain(wall)
    gate = DeviceCluster("SN7002", FakeVariables(), wall=wall, pushes=True)
    gate.boot(); gate.door_open = False
    done = []
    pusher.perform = lambda action: done.append(action) or "performed"
    # the gate camera is a member like the yard camera: its report makes it known to the domain's view
    crossings = domain_pass.crossings
    crossings.view.fed.add(member_copy(gate.name, north.objects, wall=wall))
    gate_agent = DomainAgent(gate.name, north.vars, gate.flash, now=wall, domain_objects=north.objects,
                             published=gate.local_objects())
    gate_agent.sync()
    crossings.view.refresh()
    publish_asks(crossings, [{"trigger": "SN7002", "target": SERIAL}])
    gate_agent.sync()

    def gate_dial(url):
        if url in CENTRE_URLS:
            return centre
        raise Unreachable(f"{url} did not answer the gate camera")

    asker = Asker("SN7002", gate.flash, gate_dial, clock=wall)
    assert [r["urls"] for r in asker.book()[SERIAL]] == [OFFICE_URLS, CENTRE_URLS]
    ing, aid = asker.ask(SERIAL, {"preset": 3}, within=10)
    assert ing is centre and centre.ask_outcome(SERIAL, aid) is None
    fwd.pass_once()                                                    # down to the office's ingest
    assert pusher.pass_once([])["asks"] == [({"preset": 3}, "performed")] and done == [{"preset": 3}]
    fwd.pass_once()                                                    # the outcome, up
    assert centre.ask_outcome(SERIAL, aid) == "performed"
    assert done == [{"preset": 3}]                                     # carried twice, done once
