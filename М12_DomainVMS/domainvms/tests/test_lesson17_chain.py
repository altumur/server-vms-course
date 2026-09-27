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
    publish_asks(crossings, [{"trigger": "SN7002", "target": SERIAL, "actions": [{"preset": 3}]}])
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


def test_a_camera_that_sees_only_its_office_and_that_nobody_records_polls_its_office():
    """One site, one office: the gate camera and a PTZ camera kept for live view, both reaching only the east
    office, neither recorded. A scenario ties them. The book of polls must send the PTZ camera to its OFFICE's
    ingest — the centre's, or the domain's cluster's, is exactly what it cannot reach, and a scenario inside one
    site would never act. The gate camera's book of asks names the same office; the ask goes there and back."""
    from domain.books import Books
    from domain.chain import Relay
    from domain.ingest import Asker
    from domain.scenario import Scenarios
    from domain.shared import SharedSettings, SharedView

    wall = Clock()
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    fed.add(north); fed.add(east)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    centre = Ingest("north", CENTRE_URLS, keys=lambda: ClusterTrust(north.vars).keyset(), wall=wall)
    centre.announce(north.objects)                                     # there IS an ingest up there: the wrong one
    through = Relay(east.vars, east.objects)                           # all a camera of this site can reach
    cams, agents = {}, []
    for n in ("SN7002", "SN7003"):                                     # the gate, the PTZ
        d = DeviceCluster(n, FakeVariables(), wall=wall, pushes=True)
        d.boot(); d.door_open = False
        fed.add(member_copy(d.name, north.objects, wall=wall, via="east"))
        agents.append(DomainAgent(d.name, through.vars, d.flash, now=wall, domain_objects=through.objects,
                                  cluster_objects=d.disk, published=d.local_objects(), seen_store=d.local_objects()))
        cams[n] = d
    members = [d.name for d in cams.values()]
    office_agent = DomainAgent("east", north.vars, east.vars, now=wall, domain_objects=north.objects,
                               bundle_store=east.objects, bundle_members=members, relay_members=members)
    office_agent.sync()
    office = Ingest("east", OFFICE_URLS, keys=lambda: ClusterTrust(east.vars).keyset(), wall=wall)
    office.announce(east.objects)
    SharedSettings(north.vars, north.objects, signer.tokens, wall=wall).edit(lambda s: s.update(scenarios=[
        {"when": {"camera": "SN7002", "kind": "vehicle"}, "then": {"camera": "SN7003", "action": "preset", "arg": 3}}]),
        base_rev=0, by="anna")
    books = Books(Crossings(north.vars, ReadView(fed, wall=wall), wall, issuer=signer.tokens), north.objects)

    def domain_pass():
        for d in cams.values():
            d.publish()
        for a in agents:
            a.sync()                                                   # reports into the office
        office_agent.sync()                                            # up in the bundle, and down the relay
        books.pass_once()
        office_agent.sync()                                            # the new books relayed down
        for a in agents:
            a.sync()

    domain_pass(); domain_pass()

    def site_dial(url):
        if url in OFFICE_URLS:
            return office
        raise Unreachable(f"{url} is beyond the site's network")

    done = []
    ptz = CameraPusher("SN7003", cams["SN7003"].flash, site_dial, clock=wall,
                       perform=lambda action: done.append(action) or "performed")
    e = ptz.entry()
    assert e["polls_only"] and e["cluster"] == "east" and e["ingest"]["urls"] == OFFICE_URLS
    assert "asks only" in ptz.pass_once([])["state"]                   # it reached its poll

    asker = Asker("SN7002", cams["SN7002"].flash, site_dial, clock=wall)
    assert [r["cluster"] for r in asker.book()["SN7003"]] == ["east"]
    left = Scenarios("SN7002", SharedView(cams["SN7002"].flash, cams["SN7002"].disk, wall), asker).on_event("vehicle")
    assert [x["state"] for x in left] == ["asked"] and left[0]["ingest"] is office
    assert ptz.pass_once([])["asks"] == [({"action": "preset", "arg": 3}, "performed")]
    assert asker.outcome("SN7003", left[0]["ask"], left[0]["deadline"]) == "performed"


# -- a scenario between two offices: the road up through one's own office, by event -------------------------
EAST_URLS = OFFICE_URLS
WEST_URLS = ["srt://ingest.west.office:9000"]
GATE7, PTZ7, YARD7 = "SN7102", "SN7103", "SN7104"    # the gate and a PTZ at an east site; the yard at a west site


def _two_offices(wall):
    from domain.books import Books
    from domain.chain import Relay
    from domain.ingest import Asker
    from domain.scenario import Scenarios
    from domain.shared import SharedSettings, SharedView

    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    west, _ = make_cluster("west")
    for c in (north, east, west):
        fed.add(c)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    ing = {"north": Ingest("north", CENTRE_URLS, keys=lambda: ClusterTrust(north.vars).keyset(), wall=wall),
           "east": Ingest("east", EAST_URLS, keys=lambda: ClusterTrust(east.vars).keyset(), wall=wall),
           "west": Ingest("west", WEST_URLS, keys=lambda: ClusterTrust(west.vars).keyset(), wall=wall)}
    for name, c in (("north", north), ("east", east), ("west", west)):
        ing[name].announce(c.objects)
    cams, agents, offices = {}, [], []
    for office, serials in (("east", (GATE7, PTZ7)), ("west", (YARD7,))):
        store = east if office == "east" else west
        through = Relay(store.vars, store.objects)                     # all a camera of that site reaches
        members = []
        for n in serials:
            d = DeviceCluster(n, FakeVariables(), wall=wall, pushes=True)
            d.boot(); d.door_open = False
            fed.add(member_copy(d.name, north.objects, wall=wall, via=office))
            agents.append(DomainAgent(d.name, through.vars, d.flash, now=wall, domain_objects=through.objects,
                                      cluster_objects=d.disk, published=d.local_objects(), seen_store=d.local_objects()))
            cams[n] = d
            members.append(d.name)
        offices.append(DomainAgent(office, north.vars, store.vars, now=wall, domain_objects=north.objects,
                                   bundle_store=store.objects, bundle_members=members, relay_members=members))
    for o in offices:
        o.sync()
    SharedSettings(north.vars, north.objects, signer.tokens, wall=wall).edit(lambda s: s.update(scenarios=[
        {"when": {"camera": GATE7, "kind": "vehicle"}, "then": {"camera": YARD7, "action": "preset", "arg": 3}},
        {"when": {"camera": GATE7, "kind": "vehicle"}, "then": {"camera": PTZ7, "action": "preset", "arg": 1}}]),
        base_rev=0, by="anna")
    books = Books(Crossings(north.vars, ReadView(fed, wall=wall), wall, issuer=signer.tokens, centre="north"), north.objects)

    def domain_pass():
        for d in cams.values():
            d.publish()
        for a in agents:
            a.sync()
        for o in offices:
            o.sync()
        books.pass_once()
        for o in offices:
            o.sync()
        for a in agents:
            a.sync()

    domain_pass(); domain_pass()
    centre_up = {"on": True}

    def reach(urls, owner):
        def dial(url):
            if url in urls and (owner != "office" or centre_up["on"]):
                return next(i for i in ing.values() if url in i.urls)
            raise Unreachable(f"{url} does not answer {owner}")
        return dial

    fwd = {"east": Forwarder("east", ing["east"], east.vars, reach(CENTRE_URLS, "office")),
           "west": Forwarder("west", ing["west"], west.vars, reach(CENTRE_URLS, "office"))}
    done = {PTZ7: [], YARD7: []}
    ptz = CameraPusher(PTZ7, cams[PTZ7].flash, reach(EAST_URLS, "site"), clock=wall,
                       perform=lambda a: done[PTZ7].append(a) or "performed")
    yard = CameraPusher(YARD7, cams[YARD7].flash, reach(WEST_URLS, "site"), clock=wall,
                        perform=lambda a: done[YARD7].append(a) or "performed")
    gate = Scenarios(GATE7, SharedView(cams[GATE7].flash, cams[GATE7].disk, wall),
                     Asker(GATE7, cams[GATE7].flash, reach(EAST_URLS, "site"), clock=wall))
    return ing, fwd, ptz, yard, gate, done, centre_up


def test_an_ask_to_another_office_goes_up_through_ones_own_and_an_ask_inside_the_office_does_not():
    """The gate camera sees only the east office. The PTZ camera is in the same office: its book names the east
    ingest directly, and the ask never leaves the site. The yard camera is behind the west office: the book
    names the east ingest again, marked UP; the east forwarder takes it to the centre with the office's own
    token for that pair, the west forwarder carries it down, and the outcome comes back hop by hop."""
    wall = Clock()
    ing, fwd, ptz, yard, gate, done, _ = _two_offices(wall)
    book = gate.asker.book()
    assert [(r["cluster"], r.get("up")) for r in book[PTZ7]] == [("east", None)]      # inside: direct
    assert [(r["cluster"], r.get("up")) for r in book[YARD7]] == [("east", "north")]  # across: up through its own
    assert list(fwd["east"].asks_book()) == [f"{YARD7}|{GATE7}"]                     # the office may carry that pair
    assert YARD7 in fwd["west"].book()                                 # the centre has a road down to the yard

    left = {x["target"]: x for x in gate.on_event("vehicle")}
    assert {t: (x["state"], x["ingest"]) for t, x in left.items()} == {PTZ7: ("asked", ing["east"]), YARD7: ("asked", ing["east"])}
    assert ptz.pass_once([])["asks"] == [({"action": "preset", "arg": 1}, "performed")]
    assert PTZ7 not in ing["north"].cams                               # the centre never heard of the PTZ's ask

    assert fwd["east"].woken.is_set()                                  # the ask woke the east forwarder
    assert list(fwd["east"].lift().values()) == ["up"]
    fwd["west"].pass_once()                                            # the centre answers west's poll: down it goes
    assert yard.pass_once([])["asks"] == [({"action": "preset", "arg": 3}, "performed")]
    assert fwd["west"].woken.is_set()                                  # the yard's answer woke the west forwarder
    fwd["west"].lift()                                                 # …which answers the centre
    assert list(fwd["east"].lift().values()) == ["performed"]          # …and east takes the outcome back down
    x = left[YARD7]
    assert gate.asker.outcome(YARD7, x["ask"], x["deadline"]) == "performed"
    assert done == {PTZ7: [{"action": "preset", "arg": 1}], YARD7: [{"action": "preset", "arg": 3}]}


def test_an_ask_going_up_dies_at_its_deadline_on_the_way_and_is_not_kept():
    """The east office has lost the centre. The ask waits at the office — tried again on every event — and when
    its deadline passes it dies there: the gate camera reads "expired", and the centre never saw it."""
    wall = Clock()
    ing, fwd, ptz, yard, gate, done, centre_up = _two_offices(wall)
    centre_up["on"] = False
    x = next(x for x in gate.on_event("vehicle") if x["target"] == YARD7)
    assert list(fwd["east"].lift().values()) == ["the centre did not answer"]
    wall.advance(31)
    centre_up["on"] = True
    fwd["east"].lift()
    assert gate.asker.outcome(YARD7, x["ask"], x["deadline"]) == "expired"
    assert YARD7 not in ing["north"].cams and done[YARD7] == []


def test_by_event_the_whole_road_takes_milliseconds_while_every_timer_is_a_second():
    """Both forwarders as processes, the yard camera in its own long poll, every fallback timer one second. The
    gate camera sees a vehicle; the ask goes east → centre → west → yard, the answer yard → west → centre → east,
    each hop woken by the one before — done in far less than one timer."""
    import threading
    import time as _t
    wall = Clock()
    ing, fwd, ptz, yard, gate, done, _ = _two_offices(wall)
    stop = threading.Event()
    threads = fwd["east"].serve(stop, period=1.0) + fwd["west"].serve(stop, period=1.0)

    def camera():
        while not stop.is_set():
            yard.pass_once([], wait=1.0)
    cam = threading.Thread(target=camera, daemon=True)
    cam.start()
    _t.sleep(0.2)                                                      # everyone settles into a held poll
    try:
        t0 = _t.monotonic()
        x = next(x for x in gate.on_event("vehicle") if x["target"] == YARD7)
        out = None
        while out is None and _t.monotonic() - t0 < 3.0:
            out = gate.asker.outcome(YARD7, x["ask"], x["deadline"])
            _t.sleep(0.005)
        took = _t.monotonic() - t0
    finally:
        stop.set()
        for t in threads + [cam]:
            t.join(timeout=2.0)
    assert out == "performed" and done[YARD7] == [{"action": "preset", "arg": 3}]
    assert took < 0.5, f"took {took:.3f} s: something waited for a timer"
