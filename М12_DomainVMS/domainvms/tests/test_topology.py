"""Visibility — who can see what, and who reaches the domain through whom.

Two kinds of fact, set in two places. What a cluster CAN observe — the networks it sees — it says itself, in
its own store, through its agent (`federation.REACHES`); the domain reads it like any published object, and
placement (Lesson 1) and the mirror plan (Lesson 14) use it. What nobody can observe — the network's policy:
which member reaches the domain only through an office, which offices are a star, where the centre is — the
operator sets in ONE record of the domain (`domain/topology`), edited by CAS and checked when written, and
every pass reads it from there.
"""
import json
import urllib.error
import urllib.request

from cluster.variables import Conflict, FakeVariables

from domain.agent import ClusterTrust, DomainAgent, DomainPublisher
from domain.api import ApiError, ConsoleAPI
from domain.books import Books
from domain.chain import Relay
from domain.console import Console
from domain.crossing import Crossings
from domain.device import DeviceCluster
from domain.federation import DomainDirectory, Federation
from domain.ingest import CameraPusher, Ingest
from domain.placement import CameraSite, ClusterPlacer
from domain.readview import ReadView
from domain.signer import Signer
from domain.topology import Topology
from domain.uplink import member_copy
from tests.conftest import Clock, make_cluster


def test_a_cluster_says_what_it_reaches_and_placement_reads_it_there():
    """Nobody typed "south sees vlan:b" into the domain. South's agent says it, from what south observes, in
    south's own store; the domain places a vlan:b camera on south. South is re-cabled onto vlan:c: its agent
    says so on its next pass, and the next vlan:c camera goes there — the domain's configuration never changed.
    A camera says it the same way, in its report."""
    wall = Clock()
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    south, _ = make_cluster("south")
    fed.add(north); fed.add(south)
    seen = {"north": ["vlan:a"], "south": ["vlan:b"]}
    agents = [DomainAgent(c.name, north.vars, c.vars, now=wall, reaches=lambda n=c.name: seen[n], own_objects=c.objects)
              for c in (north, south)]
    for a in agents:
        a.sync()
    placer = ClusterPlacer(fed, clock=wall)
    assert placer.place(CameraSite(1, "vlan:b")).cluster == "south"
    seen["south"] = ["vlan:b", "vlan:c"]
    assert agents[1].say_reaches() and not agents[1].say_reaches()   # written when it changes, and only then
    assert placer.place(CameraSite(2, "vlan:c")).cluster == "south"

    cam = DeviceCluster("SN8001", FakeVariables(), wall=wall)
    cam.boot()
    fed.add(member_copy(cam.name, north.objects, wall=wall))
    DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects,
                published=cam.local_objects(), reaches=lambda: ["vlan:cctv-a"]).sync()
    assert fed.clusters[cam.name].networks() == frozenset({"vlan:cctv-a"})   # from its report


def test_the_topology_is_one_record_edited_by_cas_and_checked_when_written():
    """The operator's record: the centre, the star offices, who reaches the domain through whom. Two editors are
    told, not overwritten; a name that is not a cluster of the domain, or a topology that contradicts itself,
    is refused with the reason and nothing is written."""
    topo = Topology(FakeVariables())
    known = {"north", "east", "west", "cam-SN1"}
    assert topo.edit(lambda d: d.update(centre="north", via={"cam-SN1": "east"}), base_rev=0, known=known) == 1
    try:
        topo.edit(lambda d: d.update(star=["west"]), base_rev=0, known=known)
        raise AssertionError("an edit made against rev 0 must be told")
    except Conflict:
        pass
    for bad, why in ((lambda d: d["via"].update({"cam-SN2": "east"}), "cam-SN2 is not a cluster"),
                     (lambda d: d.update(star=["north"]), "cannot be a star office"),
                     (lambda d: d["via"].update({"east": "west"}), "one office between a member and the domain")):
        try:
            topo.edit(bad, base_rev=1, known=known)
            raise AssertionError(why)
        except ApiError as e:
            assert e.status == 409 and why in e.detail
    assert topo.read()["rev"] == 1 and topo.relayed_by("east") == ["cam-SN1"]


CENTRE_URLS, OFFICE_URLS = ["srt://ingest.north:9000"], ["srt://ingest.east:9000"]


def test_the_passes_follow_the_topology_without_a_restart():
    """A camera reported to the domain directly. The site is re-wired: from now on it reaches only the east
    office. The operator says so in the topology — once — and the next passes follow: the domain reads the
    camera from east's bundle, east relays down what the domain leaves for it, the books take the centre from
    the topology, and the camera, which nobody records, polls east. No job's environment changed."""
    wall = Clock()
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    fed.add(north); fed.add(east)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    for name, c, urls in (("north", north, CENTRE_URLS), ("east", east, OFFICE_URLS)):
        Ingest(name, urls, keys=lambda c=c: ClusterTrust(c.vars).keyset(), wall=wall).announce(c.objects)
    cam = DeviceCluster("SN8002", FakeVariables(), wall=wall, pushes=True)
    cam.boot(); cam.door_open = False
    fed.add(member_copy(cam.name, north.objects, wall=wall))          # configured: it reports directly
    topo = Topology(north.vars)
    office = DomainAgent("east", north.vars, east.vars, now=wall, domain_objects=north.objects, bundle_store=east.objects,
                         relay_members=lambda: topo.relayed_by("east"), bundle_members=lambda: topo.relayed_by("east"))
    through = Relay(east.vars, east.objects)
    cam_agent = DomainAgent(cam.name, through.vars, cam.flash, now=wall, domain_objects=through.objects,
                            published=cam.local_objects(), seen_store=cam.local_objects())
    books = Books(Crossings(north.vars, ReadView(fed, wall=wall), wall, issuer=signer.tokens, topology=topo), north.objects)

    topo.edit(lambda d: d.update(centre="north", via={cam.name: "east"}), base_rev=0, known=set(fed.clusters))
    office.sync()                                                      # east relays for the camera: the topology says so
    cam_agent.sync(); office.sync()                                    # the camera reports into east; east bundles it up
    out = books.pass_once()
    assert out["moved"] == [cam.name] and fed.clusters[cam.name].via == "east"
    assert books.crossings.centre == "north"                           # from the topology, not from an argument
    assert [r["ref"] for r in books.crossings.view.list()["rows"] if r["cluster"] == cam.name] == ["SN8002"]
    office.sync(); cam_agent.sync()                                    # the books, relayed down
    pusher = CameraPusher("SN8002", cam.flash, lambda url: None, clock=wall)
    assert pusher.entry()["cluster"] == "east" and pusher.entry()["ingest"]["urls"] == OFFICE_URLS
    assert books.pass_once()["moved"] == []                            # followed once, not every pass


def test_the_operator_edits_the_topology_in_the_domain_console():
    """PUT /api/topology, with the revision the operator was looking at; only an admin of the domain cluster;
    a refusal says why. GET shows it."""
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    fed.add(north); fed.add(east)
    view = ReadView(fed, wall=lambda: 1000.0)
    api = ConsoleAPI(DomainDirectory(fed), lambda n: None, verifier=lambda token: token)
    con = Console(DomainDirectory(fed), view, api, refresh_interval=0.05, topology=Topology(north.vars),
                  admin=lambda subject: subject == "anna")
    srv = con.serve(port=0)
    base = f"http://127.0.0.1:{srv.server_address[1]}/api/topology"

    def put(body, token):
        req = urllib.request.Request(base, data=json.dumps(body).encode(), method="PUT",
                                     headers={"Authorization": f"Bearer {token}"})
        try:
            return 200, json.load(urllib.request.urlopen(req))
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    try:
        assert put({"base_rev": 0, "centre": "north"}, "boris")[0] == 403
        code, body = put({"base_rev": 0, "centre": "north", "via": {"east": "west"}}, "anna")
        assert code == 409 and "west is not a cluster" in body["detail"]
        code, body = put({"base_rev": 0, "centre": "north"}, "anna")
        assert code == 200 and body["rev"] == 1
        assert put({"base_rev": 0, "star": ["east"]}, "anna")[0] == 409      # made against rev 0: told
        assert json.load(urllib.request.urlopen(base))["centre"] == "north"
    finally:
        con.stop(srv)
