"""Visibility — who can see what, and who reaches the domain through whom.

Two kinds of fact, set in two places. What a cluster CAN observe — the networks it sees — it says itself, in
its own store, through its agent (`federation.REACHES`); the domain reads it like any published object, and
placement (Lesson 1) uses it. What nobody can observe — the network's policy:
which member reaches the domain only through a relay, which relays are a star, where the centre is — the
operator sets in ONE record of the domain (`domain/topology`), edited by CAS and checked when written, and
every pass reads it from there.
"""

from tests.reporting import sync as report_sync
import json
import urllib.error
import urllib.request

from w2cplatform.cluster.variables import Conflict, FakeVariables

from w2cplatform.domain.agent import DomainAgent, DomainPublisher
from w2cplatform.domain.api import ApiError, ConsoleAPI
from w2cplatform.domain.relay import Relay
from w2cplatform.domain.console import Console
from tests.domain.conftest import EmbeddedMember
from w2cplatform.domain.federation import DomainDirectory, Federation
from w2cplatform.domain.placement import UnitSite, ClusterPlacer
from w2cplatform.domain.readview import ReadView
from w2cplatform.trust.signer import Signer
from w2cplatform.domain.topology import Topology
from w2cplatform.domain.uplink import member_copy
from tests.domain.conftest import Clock, make_cluster


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
        report_sync(a)
    admit(fed)
    placer = ClusterPlacer(fed, sub="cam", clock=wall)
    assert placer.place(UnitSite(1, "vlan:b")).cluster == "south"
    seen["south"] = ["vlan:b", "vlan:c"]
    assert agents[1].say_reaches() and not agents[1].say_reaches()   # written when it changes, and only then
    assert placer.place(UnitSite(2, "vlan:c")).cluster == "south"

    cam = EmbeddedMember("SN8001", FakeVariables(), wall=wall)
    cam.boot()
    fed.add(member_copy(cam.name, north.objects, wall=wall))
    report_sync(DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects,
                published=cam.local_objects(), reaches=lambda: ["vlan:cctv-a"]))
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




def test_the_operator_edits_the_topology_in_the_domain_console():
    """PUT /domain/topology, with the revision the operator was looking at; only an admin of the domain holder;
    a refusal says why. GET shows it."""
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    fed.add(north); fed.add(east)
    view = ReadView(fed, wall=lambda: 1000.0)
    api = ConsoleAPI(DomainDirectory(fed), verifier=lambda token: token)
    con = Console(DomainDirectory(fed), view, api, refresh_interval=0.05, topology=Topology(north.vars),
                  admin=lambda subject: subject == "anna")
    srv = con.serve(port=0)
    base = f"http://127.0.0.1:{srv.server_address[1]}/domain/topology"

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
    """AM, 1. Whoever reaches the domain holder reaches the domain: "through the domain holder" says nothing,
    and it has no agent to relay. It goes through nobody either."""
    topo = Topology(FakeVariables())
    known = {"north", "east", "cam-SN1"}
    for bad, why in ((lambda d: d.update(via={"cam-SN1": "north"}), "the domain's holder: whoever reaches it"),
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
    from w2cplatform.domain.relay import bundle
    wall = Clock()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    cam = EmbeddedMember("SN8003", FakeVariables(), wall=wall)
    cam.boot()
    direct = DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects, published=cam.local_objects())
    report_sync(direct)                                                      # it reaches the domain after all
    fed = Federation(); fed.add(north)
    fed.add(member_copy(cam.name, north.objects, wall=wall, via="east"))
    view = ReadView(fed, wall=wall); view.refresh()
    assert [r["ref"] for r in view.list()["rows"] if r["cluster"] == cam.name] == ["SN8003"]

    wall.advance(30)
    relay = DomainAgent("east", north.vars, east.vars, now=wall, domain_objects=north.objects, bundle_store=east.objects,
                        relay_members=[cam.name])
    report_sync(relay)                                                       # east keeps what the domain answers for it
    through = Relay(relay, east.objects)                               # now it reports through east, and renames itself
    cam.local_console().update_unit(1, {"name": "through-east"}, None)
    report_sync(DomainAgent(cam.name, through.vars, cam.flash, now=wall, domain_objects=through.objects,
                published=cam.local_objects()))
    bundle("east", [cam.name], east.objects, north.objects, received_at=wall())
    view.refresh()
    assert [r["name"] for r in view.list()["rows"] if r["cluster"] == cam.name] == ["through-east"]


def test_books_behind_a_relay_are_as_old_as_the_relay_says_on_the_cameras_own_clock():
    """AM, 3. The relay says how long ago it last reached the domain — an age, on its own clock — on every pass,
    the failed ones included. The camera sets its mark to its OWN clock minus that age: two clocks are never
    compared, and a camera whose clock runs five minutes ahead still judges its books by their true age."""
    from w2cplatform.domain.relay import say_seen
    relay_clock, cam_clock = Clock(10_000.0), Clock(10_300.0)       # the camera runs five minutes ahead
    from tests.domain.conftest import Ram
    relay_vars, relay_objects = FakeVariables(), Ram()
    agent = DomainAgent("cam-SN8004", Relay(None, relay_objects).vars, FakeVariables(), now=cam_clock)
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
    from w2cplatform.domain import agent as agent_module
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


def test_a_lower_member_timestamp_is_refused_even_after_a_change_of_road():
    """ADR-0074: a relay cannot replace an accepted report with a lower sent_at."""
    from w2cplatform.domain.relay import bundle
    wall = Clock()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    cam = EmbeddedMember("SN8005", FakeVariables(), wall=wall)
    cam.boot()
    report_sync(DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects, published=cam.local_objects()))
    fed = Federation(); fed.add(north)
    fed.add(member_copy(cam.name, north.objects, wall=wall, via="east"))
    view = ReadView(fed, wall=wall); view.refresh()                    # the domain has seen the direct report
    behind = lambda: wall() - 1000                                     # the camera's clock, a thousand seconds back
    cam.local_console().update_unit(1, {"name": "clock-stepped-back"}, None)
    relay = DomainAgent("east", north.vars, east.vars, now=wall, domain_objects=north.objects, bundle_store=east.objects,
                        relay_members=[cam.name])
    report_sync(relay)
    through = Relay(relay, east.objects)
    relay_agent = DomainAgent(cam.name, through.vars, cam.flash, now=behind, domain_objects=through.objects,
                              published=cam.local_objects())
    for _ in range(4):                                                 # a minute of passes through east
        wall.advance(15)
        report_sync(relay_agent); bundle("east", [cam.name], east.objects, north.objects, received_at=wall())
        view.refresh()
    rows = [r for r in view.list()["rows"] if r["cluster"] == cam.name]
    assert [r["name"] for r in rows] != ["clock-stepped-back"]         # the live road, not the frozen one
    assert not view.list()["complete"]                                     # and it is not silent








def admit(fed):
    from w2cplatform.domain.members import Members
    members = Members(fed.domain_holder.vars, configured=lambda: list(fed.clusters), domain=fed.domain_holder.name)
    members.settle()
    members.list_holder(fed.domain_holder.name, None, None)
