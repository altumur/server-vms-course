"""Lesson 17 — a chain: site, office, centre.

Cameras nobody can dial, recorded by an office nobody above can dial, watched from a centre everybody can
reach. Each level dials the level above: the camera its office (media) and the centre (books, reports); the
office the centre. The want travels down, the stream up. The star: an office that cannot be pushed to takes
its cameras' streams from the centre. The summary report: cameras report through their office, one object
for all of them in the centre.
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

    pusher = CameraPusher(SERIAL, cam.flash, dial_from("camera", {"office"} if not star else set()))
    fwd = Forwarder("east", office, east.vars, dial_from("office", set()),
                    archive=lambda ref, t0, t1: [("east-archive", ref, t0, t1)], needs=lambda ref: True)

    def domain_pass():
        view.refresh(); crossings.publish(); crossings.publish_primaries()
        publish_upstream(crossings, "north", star=star)
        cam_agent.sync(); office_agent.sync()

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
    bq = centre.subscribe(SERIAL, "recorder:centre", kind="backfill")
    centre.request_range(SERIAL, 5000.0, 5600.0)
    fwd.pass_once()
    assert centre.landed(SERIAL) == [(5000.0, 5600.0)]
    assert bq.drain() == [("east-archive", SERIAL, 5000.0, 5600.0)]    # out of the office's archive, not the camera's card


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
    """Cameras report to their office; the office folds their reports into one object in the centre. Three
    hundred cameras in ten offices are ten writes per round instead of eight hundred — and when an office
    goes quiet, its cameras go quiet with it: the centre cannot tell the office from its sites."""
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
