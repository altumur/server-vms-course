"""The domain's secrets with the VMS on it — the product's four checks (DOMAIN-PLATFORM.md, r23-seal): nothing open in
any store of three clusters; a member gets only its own; the relay gives a camera only its own; a member's agent neither
reads nor writes the signer's key. Two servers and a camera, as in `test_two_servers.py`, each with its own key ring:
the holder seals the books' stream tokens at rest, its door seals them to each member's key, each member keeps them
sealed with its own ring — and the camera still pushes, its token opened at the last moment."""
import json
import os
import re
import tempfile

from w2cplatform.cluster.variables import FakeVariables

from w2cplatform.domain.agent import ClusterTrust, DomainAgent, DomainPublisher
from w2cplatform.domain.carry import CarryClient, HolderDoor
from w2cplatform.domain.federation import Federation, Unreachable
from w2cplatform.domain.members import Members
from w2cplatform.domain.readview import ReadView
from w2cplatform.domain.uplink import member_copy
from w2cplatform.trust.memberkey import MemberKey
from w2cplatform.trust.signer import Signer
from vms.domainpart.crossing import Crossings
from vms.domainpart.device import DeviceCluster
from vms.domainpart.ingest import CameraPusher, Ingest
from vms.domainpart.keys import PRIMARIES_PATH, SOURCES_PATH
from tests.domain.conftest import Clock, make_cluster

SERIAL = "SN6101"
A_URLS, B_URLS = ["srt://srv-a:9000"], ["srt://srv-b:9000"]
JWS = re.compile(r"eyJ[\w-]+\.eyJ[\w-]+\.[\w-]+")


def ring():
    from w2cplatform.sealing import Sealer, new_key_file
    path = os.path.join(tempfile.mkdtemp(prefix="ring-"), "platform.key")
    new_key_file(path)
    return Sealer.from_file(path)


def _site(wall):
    """srv-b holds the domain and the backup; srv-a records the camera; the camera pushes. Every member is admitted
    with its key and carries through the holder's door; every cluster has its ring."""
    from vms.config import REC_SPEC
    from w2cplatform.spec import SpecController
    fed = Federation()
    b, _ = make_cluster("srv-b", domain=True)
    a, _ = make_cluster("srv-a")
    fed.add(a); fed.add(b)
    rings = {"srv-b": ring(), "srv-a": ring(), "cam": ring()}
    signer = Signer("acme", b.vars, now=wall, sealer=rings["srv-b"])
    DomainPublisher(b.vars).publish_keys(signer.tokens.keyset())
    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, pushes=True)
    keys = {"srv-a": MemberKey.new(), cam.name: MemberKey.new()}
    members = Members(b.vars, wall, domain="srv-b")
    for n, k in keys.items():
        members.add(n, "voucher", key=k.pub, seal=k.seal_pub)
    door = HolderDoor(b.vars, b.objects, rings["srv-b"], wall)
    ing = {"srv-a": Ingest("srv-a", A_URLS, keys=lambda: ClusterTrust(a.vars).keyset(), wall=wall),
           "srv-b": Ingest("srv-b", B_URLS, keys=lambda: ClusterTrust(b.vars).keyset(), wall=wall)}
    ing["srv-a"].announce(a.objects); ing["srv-b"].announce(b.objects)
    agents = {"srv-a": DomainAgent("srv-a", CarryClient(door, "srv-a", keys["srv-a"], wall), a.vars, now=wall,
                                   sealer=rings["srv-a"], key=keys["srv-a"]),
              "srv-b": DomainAgent("srv-b", b.vars, b.vars, now=wall, seen_store=b.objects, sealer=rings["srv-b"])}
    SpecController(REC_SPEC, a.vars, a.objects, wall=wall).create({"name": SERIAL, "cam": f"ref:{SERIAL}"})
    cam.boot(); cam.door_open = False
    fed.add(member_copy(cam.name, b.objects, wall=wall))
    cam_agent = DomainAgent(cam.name, CarryClient(door, cam.name, keys[cam.name], wall), cam.flash, now=wall,
                            domain_objects=b.objects, published=cam.local_objects(), seen_store=cam.local_objects(),
                            sealer=rings["cam"], key=keys[cam.name])
    view = ReadView(fed, wall=wall)
    crossings = Crossings(b.vars, view, wall, issuer=signer.tokens, sealer=rings["srv-b"])

    def domain_pass():
        cam.publish(); cam_agent.sync()
        for x in agents.values():
            x.sync()
        view.refresh(); crossings.record(SERIAL, on="srv-a") if not crossings.all() else None
        crossings.publish(); crossings.publish_primaries()
        for x in agents.values():
            x.sync()
        cam_agent.sync()

    def dial(url):
        for i in ing.values():
            if url in i.urls:
                return i
        raise Unreachable(f"{url} did not answer")
    q = ing["srv-a"].subscribe(SERIAL, "recorder:srv-a", maxsize=1000)
    ing["srv-a"].want(SERIAL, "recorder:srv-a")
    pusher = CameraPusher(SERIAL, cam.flash, dial, clock=wall, ring_seconds=30)
    pusher.sealer = rings["cam"]
    domain_pass(); domain_pass()
    return fed, a, b, cam, door, keys, rings, pusher, q, signer


def _rows(store) -> dict:
    return {k: store.get(k)[0] for k in store.list("")}


def test_nothing_is_open_in_any_store_of_three_clusters_and_the_camera_still_pushes():
    """Every `*_secret` in every row of the holder, the recording server and the camera — the signer's keys, the books'
    tokens, the member keys — lies sealed; no token is anywhere in the clear, in a row or an object. And the camera
    pushes: its stream token, opened with its own ring at the moment it calls, is one the recorder's ingest takes."""
    from tests.test_domain_secrets import sealed_everywhere
    wall = Clock(1000.0)
    fed, a, b, cam, door, keys, rings, pusher, q, signer = _site(wall)
    for name, store in (("srv-b", b.vars), ("srv-a", a.vars), ("camera", cam.flash)):
        rows = _rows(store)
        assert rows, name
        for key, items in rows.items():
            assert not sealed_everywhere(items), (name, key, sealed_everywhere(items))
            assert not JWS.search(json.dumps(items)), (name, key)
    for name, objects in (("srv-b", b.objects), ("srv-a", a.objects), ("camera", cam.ram)):
        for key in objects.list(""):
            assert not JWS.search((objects.get(key) or b"").decode("utf-8", "replace")), (name, key)
    assert b.vars.get(f"{PRIMARIES_PATH}/{cam.name}")[0] and cam.flash.get(PRIMARIES_PATH)[0]
    assert pusher.entry()["ingest"]["token_secret"].count(".") == 2
    for _ in range(3):
        wall.advance(1)
        pusher.pass_once([{"t": wall(), "key": True}])
    assert q.drain(), "the camera's stream did not reach its recorder"


def test_a_member_gets_only_its_own_rows_through_the_door():
    """The door answers the recording server with its own book of sources and the camera with its own book of primaries
    — neither sees the other's, and neither the signer's row nor another member's emergency hash."""
    wall = Clock(1000.0)
    fed, a, b, cam, door, keys, rings, pusher, q, signer = _site(wall)
    for me, other in (("srv-a", cam.name), (cam.name, "srv-a")):
        got = CarryClient(door, me, keys[me], wall)._ask()
        assert not [p for p in got["rows"] if p.endswith(f"/{other}")], me
        assert "domain/signer" not in got["rows"]
    assert a.vars.get(SOURCES_PATH)[0] and not a.vars.get(PRIMARIES_PATH)[0]
    assert cam.flash.get(PRIMARIES_PATH)[0] and "domain/signer" not in cam.flash.list("domain/")


def test_the_relay_gives_a_camera_only_its_own():
    """A camera behind the recording server, relayed: what the domain answered for it lies in the relay's memory, sealed
    to the camera; the relay's store holds none of it; the camera gets its own book, another member's ask is refused."""
    from w2cplatform.domain.carry import Refused, request_message
    from w2cplatform.domain.relay import Relay
    from w2cplatform.domain.topology import Topology
    wall = Clock(1000.0)
    fed, a, b, cam, door, keys, rings, pusher, q, signer = _site(wall)
    Topology(b.vars).edit(lambda d: d["via"].update({cam.name: "srv-a"}), 0, known=set(fed.clusters) | {cam.name},
                          domain="srv-b")
    relay = DomainAgent("srv-a", CarryClient(door, "srv-a", keys["srv-a"], wall), a.vars, now=wall, sealer=rings["srv-a"],
                        key=keys["srv-a"], relay_members=[cam.name], bundle_store=a.objects)
    assert relay.sync() and set(relay.relayed) == {cam.name}
    assert not a.vars.list("relay/")
    got = Relay(relay).vars.answer_for(cam.name, keys[cam.name])
    assert json.loads(got["rows"][f"{PRIMARIES_PATH}/{cam.name}"][SERIAL])["ingest"]["token_secret"].count(".") == 2
    try:
        Relay(relay).door.carry(cam.name, wall(), keys["srv-a"].seal_pub,
                                keys["srv-a"].sign(request_message(cam.name, wall(), keys["srv-a"].seal_pub)))
        raise AssertionError("the relay gave the camera's rows to another member")
    except Refused:
        pass


def test_a_members_agent_neither_reads_nor_writes_the_signers_key():
    """In the rights file the VMS's specs generate, the agent writes `domain/*` but not the signer's row (nor any row
    only the holder writes) and reads no signer row; on a box with `file://` the in-process ACL says the same."""
    from w2cplatform import catalog
    from w2cplatform.domain.rights import roles
    from w2cplatform.storemachine import Rights
    from w2cplatform.variables import FileVariables, Forbidden
    specs = catalog.load_dir(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "vms"))
    agent = roles(specs=specs)["domainagent"]
    r = Rights({"domainagent": agent})
    for action in ("read", "write", "delete"):
        assert not r.allows("domainagent", action, "domain/signer"), action
    for key in (f"{PRIMARIES_PATH}/cam-SN1", f"{SOURCES_PATH}/srv-a", "domain/vms/crossings", "domain/members"):
        assert not r.allows("domainagent", "write", key), key
    assert r.allows("domainagent", "write", PRIMARIES_PATH) and r.allows("domainagent", "write", "domain/member-key")
    box = FileVariables(tempfile.mkdtemp(prefix="acl-"), "domainagent", {"domainagent": agent["write"]}, volatile=True)
    try:
        box.put("domain/signer", {"issuing_key_secret": "x"})
        raise AssertionError("the box let the agent write the signer's key")
    except Forbidden:
        pass


def test_every_key_the_vms_writes_on_the_domain_falls_into_a_family_its_spec_declares():
    """The domain card's «keys» tab lists the VMS's rows by the families `vms.subsystem.yaml` declares (`domain.keys`,
    the product's `KEY_FAMILIES` mapped to `domain/vms/…`). Every `domain/vms/…` key a pass wrote — at the holder, in the
    recording member, in the camera — falls into one; so does every path the worker's code names (each book at the
    holder and carried home, each kept row, the worker's slot); and every family has its words."""
    from vms.config import SPEC
    from vms.domainpart import chain, crossing, ingest, keys, worker
    wall = Clock(1000.0)
    fed, a, b, cam, door, member_keys, rings, pusher, q, signer = _site(wall)
    written = [k for store in (b.vars, a.vars, cam.flash) for k in store.list(SPEC.domain_prefix)]
    assert written
    named = [getattr(m, n) for m in (keys, worker, crossing, chain, ingest) for n in dir(m)
             if (n.endswith("_PATH") or n in ("CROSSINGS", "ROADS", "SLOT")) and isinstance(getattr(m, n), str)
             and getattr(m, n).startswith(SPEC.domain_prefix)]
    named += [f"{SPEC.domain_prefix}{book}/srv-a" for book in SPEC.domain.books]
    assert keys.UPSTREAM_PATH in named and keys.ASKS_PATH in named and worker.SLOT in named
    stray = sorted({k for k in written + named if SPEC.domain.family_of(k) is None})
    assert not stray, f"keys in no declared family: {stray}"
    assert sorted(SPEC.display["keys"]) == sorted(f["id"] for f in SPEC.domain.keys)
