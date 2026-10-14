"""Recording follows the platform's edited relay topology without restarting."""
from tests.reporting import sync as report_sync
from tests.domain.conftest import Clock, make_cluster
from tests.domainvms.recording_domain import RecordingInputs
from tests.vmsconftest import ingest_recorder
from vms.camera_cluster import DeviceCluster
from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.domain.agent import DomainAgent, DomainPublisher
from w2cplatform.domain.federation import Federation
from w2cplatform.domain.readview import ReadView
from w2cplatform.domain.relay import Relay
from w2cplatform.domain.topology import Topology, apply as follow_topology
from w2cplatform.domain.uplink import member_copy
from w2cplatform.trust.signer import Signer

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
    recorders = []
    for name, c, urls in (("north", north, CENTRE_URLS), ("east", east, RELAY_URLS)):
        recorders.append(ingest_recorder(name, urls[0], wall, c.vars, c.objects))
    cam = DeviceCluster("SN8002", FakeVariables(), wall=wall, pushes=True)
    cam.boot(); cam.door_open = False
    fed.add(member_copy(cam.name, north.objects, wall=wall))          # configured: it reports directly
    topo = Topology(north.vars)
    relay = DomainAgent("east", north.vars, east.vars, now=wall, domain_objects=north.objects, bundle_store=east.objects,
                         relay_members=lambda: topo.relayed_by("east"), bundle_members=lambda: topo.relayed_by("east"))
    through = Relay(relay, east.objects)
    cam_agent = DomainAgent(cam.name, through.vars, cam.flash, now=wall, domain_objects=through.objects,
                            published=cam.local_objects(), seen_store=cam.local_objects())
    inputs = RecordingInputs(north.vars, ReadView(fed, wall=wall), wall, topology=topo)
    from tests.domainvms.recording_domain import RecordingDomain, camera_pusher
    publication = RecordingDomain(inputs, signer,
        agents=[cam_agent, relay], devices=[cam], recorders=recorders)

    topo.edit(lambda d: d.update(centre="north", via={cam.name: "east"}), base_rev=0, known=set(fed.clusters))
    report_sync(relay)                                                      # east relays for the camera: the topology says so
    report_sync(cam_agent); report_sync(relay)                                    # the camera reports into east; east bundles it up
    moved = follow_topology(fed, topo, north.objects, wall=wall)
    inputs.view.refresh()
    assert moved == [cam.name] and fed.clusters[cam.name].via == "east"
    assert inputs.centre == "north"                           # from the topology, not from an argument
    assert [r["ref"] for r in inputs.view.list()["rows"] if r["cluster"] == cam.name] == ["SN8002"]
    for _ in range(2):
        publication.collect()
    report_sync(relay); report_sync(cam_agent)                                    # the books, relayed down
    pusher = camera_pusher("SN8002", cam.flash, lambda url: None, clock=wall)
    assert pusher.entry()["cluster"] == "east" and pusher.entry()["ingest"]["urls"] == RELAY_URLS
    assert follow_topology(fed, topo, north.objects, wall=wall) == []                            # followed once, not every pass

