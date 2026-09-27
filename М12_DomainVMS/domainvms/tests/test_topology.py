"""Visibility — who can see what, and who reaches the domain through whom.

Two kinds of fact, set in two places. What a cluster CAN observe — the networks it sees — it says itself, in
its own store, through its agent (`federation.REACHES`); the domain reads it like any published object, and
placement (Lesson 1) and the mirror plan (Lesson 14) use it. What nobody can observe — the network's policy:
which member reaches the domain only through a relay, which relays are a star, where the centre is — the
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
    """The operator's record: the centre, the star relays, who reaches the domain through whom. Two editors are
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
                     (lambda d: d.update(star=["north"]), "cannot be a star relay"),
                     (lambda d: d["via"].update({"east": "west"}), "one relay between a member and the domain")):
        try:
            topo.edit(bad, base_rev=1, known=known)
            raise AssertionError(why)
        except ApiError as e:
            assert e.status == 409 and why in e.detail
    assert topo.read()["rev"] == 1 and topo.relayed_by("east") == ["cam-SN1"]


CENTRE_URLS, RELAY_URLS = ["srt://ingest.north:9000"], ["srt://ingest.east:9000"]


def test_the_passes_follow_the_topology_without_a_restart():
    """A camera reported to the domain directly. The site is re-wired: from now on it reaches only the east
    relay. The operator says so in the topology — once — and the next passes follow: the domain reads the
    camera from east's bundle, east relays down what the domain leaves for it, the books take the centre from
    the topology, and the camera, which nobody records, polls east. No job's environment changed."""
    wall = Clock()
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    fed.add(north); fed.add(east)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    for name, c, urls in (("north", north, CENTRE_URLS), ("east", east, RELAY_URLS)):
        Ingest(name, urls, keys=lambda c=c: ClusterTrust(c.vars).keyset(), wall=wall).announce(c.objects)
    cam = DeviceCluster("SN8002", FakeVariables(), wall=wall, pushes=True)
    cam.boot(); cam.door_open = False
    fed.add(member_copy(cam.name, north.objects, wall=wall))          # configured: it reports directly
    topo = Topology(north.vars)
    relay = DomainAgent("east", north.vars, east.vars, now=wall, domain_objects=north.objects, bundle_store=east.objects,
                         relay_members=lambda: topo.relayed_by("east"), bundle_members=lambda: topo.relayed_by("east"))
    through = Relay(east.vars, east.objects)
    cam_agent = DomainAgent(cam.name, through.vars, cam.flash, now=wall, domain_objects=through.objects,
                            published=cam.local_objects(), seen_store=cam.local_objects())
    books = Books(Crossings(north.vars, ReadView(fed, wall=wall), wall, issuer=signer.tokens, topology=topo), north.objects)

    topo.edit(lambda d: d.update(centre="north", via={cam.name: "east"}), base_rev=0, known=set(fed.clusters))
    relay.sync()                                                      # east relays for the camera: the topology says so
    cam_agent.sync(); relay.sync()                                    # the camera reports into east; east bundles it up
    out = books.pass_once()
    assert out["moved"] == [cam.name] and fed.clusters[cam.name].via == "east"
    assert books.crossings.centre == "north"                           # from the topology, not from an argument
    assert [r["ref"] for r in books.crossings.view.list()["rows"] if r["cluster"] == cam.name] == ["SN8002"]
    relay.sync(); cam_agent.sync()                                    # the books, relayed down
    pusher = CameraPusher("SN8002", cam.flash, lambda url: None, clock=wall)
    assert pusher.entry()["cluster"] == "east" and pusher.entry()["ingest"]["urls"] == RELAY_URLS
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


# -- feedback AM ----------------------------------------------------------------------------------------------
def test_nobody_goes_through_the_domains_own_cluster_and_it_goes_through_nobody():
    """AM, 1. Whoever reaches the domain cluster reaches the domain: "through the domain cluster" says nothing,
    and it has no agent to relay. It goes through nobody either."""
    topo = Topology(FakeVariables())
    known = {"north", "east", "cam-SN1"}
    for bad, why in ((lambda d: d.update(via={"cam-SN1": "north"}), "the domain's own cluster: whoever reaches it"),
                     (lambda d: d.update(via={"north": "east"}), "goes through nobody")):
        try:
            topo.edit(bad, base_rev=0, known=known, domain="north")
            raise AssertionError(why)
        except ApiError as e:
            assert e.status == 409 and why in e.detail
    assert topo.edit(lambda d: d.update(centre="north", via={"cam-SN1": "east"}), base_rev=0, known=known, domain="north") == 1


def test_a_member_placed_behind_a_relay_is_read_by_whichever_road_is_newer():
    """AM, 2. The topology describes a road; it does not forbid another. A camera placed behind east that still
    reports straight to the domain is not made silent — the domain reads the newer of its own report and east's
    bundle, by the camera's own report number."""
    from domain.chain import bundle
    wall = Clock()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    cam = DeviceCluster("SN8003", FakeVariables(), wall=wall)
    cam.boot()
    direct = DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects, published=cam.local_objects())
    direct.sync()                                                      # it reaches the domain after all
    fed = Federation(); fed.add(north)
    fed.add(member_copy(cam.name, north.objects, wall=wall, via="east"))
    view = ReadView(fed, wall=wall); view.refresh()
    assert [r["ref"] for r in view.list()["rows"] if r["cluster"] == cam.name] == ["SN8003"]

    wall.advance(30)
    through = Relay(east.vars, east.objects)                           # now it reports through east, and renames itself
    cam.local_console().update_camera(1, {"name": "through-east"}, None)
    DomainAgent(cam.name, through.vars, cam.flash, now=wall, domain_objects=through.objects,
                published=cam.local_objects()).sync()
    bundle("east", [cam.name], east.objects, north.objects)
    view.refresh()
    assert [r["name"] for r in view.list()["rows"] if r["cluster"] == cam.name] == ["through-east"]


def test_books_behind_a_relay_are_as_old_as_the_relay_says_on_the_cameras_own_clock():
    """AM, 3. The relay says how long ago it last reached the domain — an age, on its own clock — on every pass,
    the failed ones included. The camera sets its mark to its OWN clock minus that age: two clocks are never
    compared, and a camera whose clock runs five minutes ahead still judges its books by their true age."""
    from domain.chain import say_seen
    relay_clock, cam_clock = Clock(10_000.0), Clock(10_300.0)       # the camera runs five minutes ahead
    relay_vars, relay_objects = FakeVariables(), __import__("domain.device", fromlist=["Ram"]).Ram()
    agent = DomainAgent("cam-SN8004", Relay(relay_vars, relay_objects).vars, FakeVariables(), now=cam_clock)
    last = relay_clock()
    say_seen(relay_objects, last, relay_clock())                     # the relay reached the domain just now
    assert agent._relay_mark() == cam_clock()
    for _ in range(4):
        relay_clock.advance(30); cam_clock.advance(30)
        say_seen(relay_objects, last, relay_clock())                 # it has lost the domain: the age grows
        mark = agent._relay_mark()
    assert cam_clock() - mark == relay_clock() - last == 120.0        # the true age, on the camera's clock


def test_the_sites_names_are_the_source_and_interfaces_only_a_fallback_without_tunnels():
    """AM, 5. On the product's box a VPN put the same /32 into every cluster's networks. REACHES — the site's own
    names — is the source; the interfaces are a fallback, without host routes and tunnel or container links."""
    import os
    import subprocess
    from domain import agent as agent_module
    fake = json.dumps([
        {"ifname": "lo", "addr_info": [{"local": "127.0.0.1", "prefixlen": 8}]},
        {"ifname": "eth0", "addr_info": [{"local": "10.1.0.5", "prefixlen": 24}]},
        {"ifname": "utun3", "addr_info": [{"local": "100.64.0.7", "prefixlen": 32}]},
        {"ifname": "docker0", "addr_info": [{"local": "172.17.0.1", "prefixlen": 16}]},
        {"ifname": "eth1", "addr_info": [{"local": "192.168.9.2", "prefixlen": 32}]}])
    run, env = subprocess.run, os.environ.pop("REACHES", None)
    subprocess.run = lambda *a, **kw: type("R", (), {"stdout": fake})()
    try:
        assert agent_module.local_networks() == ["net:10.1.0.0/24"]
        os.environ["REACHES"] = "vlan:cctv-a,vlan:cctv-b"
        assert agent_module.local_networks() == ["vlan:cctv-a", "vlan:cctv-b"]
    finally:
        subprocess.run = run
        os.environ.pop("REACHES", None)
        if env is not None:
            os.environ["REACHES"] = env
