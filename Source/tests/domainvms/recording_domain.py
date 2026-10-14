"""C2 scenario fixture: ordinary publishers, signed reports and the generic holder pass.

Nothing here rebuilds a book from heartbeat fields. A scenario supplies worker
rows/status explicitly, as it supplies sensor frames or a network outage.
"""
import json
import math
from types import SimpleNamespace
from weakref import WeakKeyDictionary

from tests.reporting import sync
from vms.config import SPEC, REC_SPEC
from vms.recording_publication import primaries, publish
from w2cplatform.contract import Slot
from w2cplatform.domain import bookruntime, declared, placement
from w2cplatform.domain.federation import Unreachable
from w2cplatform.domain.carry import CarryClient, HolderDoor
from w2cplatform.domain.memberbook import read as member_book
from w2cplatform.domain.uplink import report
from w2cplatform.trust.memberkey import MemberKey
from w2cplatform.trust.tokens import DeclaredIssuer
from w2cplatform.worker import Worker

_doors = WeakKeyDictionary()


def role_requests(vars_):
    return _doors.get(vars_)


def camera_pusher(serial, flash, dial, **kw):
    from vms.domainpart.ingest import CameraPusher
    kw.setdefault("token_requests", role_requests(flash))
    return CameraPusher(serial, flash, dial, **kw)


class RecordingDomain:
    def __init__(self, inputs, signer, *, agents=(), devices=()):
        self.inputs, self.signer = inputs, signer
        self.wall = inputs.wall
        self.holder_cluster = inputs.view.fed.domain_holder
        self.vars = self.holder_cluster.vars
        self.objects = self.holder_cluster.objects
        from w2cplatform.trust.documents import sign
        if self.vars.get("domain/holder")[0] is None:
            self.vars.put("domain/holder", {"doc": json.dumps(sign({"term": 1,
                "holder": self.holder_cluster.name, "at": self.wall()}, signer.tokens))})
        self.agents, self.devices = list(agents), list(devices)
        self.publishers = {}
        self.report_at = {}
        self.keys = {}
        self.door = HolderDoor(self.vars, self.objects, sealer=getattr(inputs.vars, "sealer", None), wall=self.wall,
            token_issuer=DeclaredIssuer(signer.tokens, declared.token_kinds()))
        self.holder = SimpleNamespace(vars=self.vars, objects=self.objects,
            wall=self.wall, view=inputs.view, term=None, signer=signer, sealer=getattr(inputs.vars, "sealer", None))
        stores = {a.cluster: a.cluster_vars for a in self.agents}
        for name, cluster in inputs.view.fed.clusters.items():
            stores.setdefault(name, cluster.vars)
        self.stores = stores
        roster = {}
        for name, vars_ in stores.items():
            local_agent = next((a for a in self.agents if a.cluster == name), None)
            key = (local_agent.key if local_agent and local_agent.key is not None else
                   MemberKey.load_or_make(vars_, local_agent.sealer if local_agent else None))
            self.keys[name] = key
            roster[name] = {"key": key.pub, "seal": key.seal_pub}
            vars_.put("domain/member", {"cluster": name})
            client = CarryClient(self.door, name, key, self.wall)
            _doors[vars_] = SimpleNamespace(request=lambda kind, ref, c=client:
                c.request_token("cam", kind, ref, "camworker"))
        self.vars.put("domain/members", {"doc": json.dumps({"rev": 1, "members": roster})})
        if inputs.centre and self.vars.get("domain/topology")[0] is None:
            self.vars.put("domain/topology", {"doc": json.dumps({"rev": 1, "centre": inputs.centre,
                "star": sorted(inputs.star), "via": {}})})
        for agent in self.agents:
            agent.key = self.keys[agent.cluster]
            if agent.domain_objects is None and not hasattr(agent.domain_vars, "publish"):
                agent.domain_objects = self.objects
            if agent.published is None:
                agent.published = inputs.view.fed.clusters[agent.cluster].objects
            if not agent.published.list("cam/snapshot/"):
                agent.published.put("cam/snapshot/fixture", json.dumps({"cluster": agent.cluster,
                    "ts": self.wall(), "cameras": []}).encode())

    def add_agent(self, agent, device=None):
        self.agents.append(agent)
        self.stores[agent.cluster] = agent.cluster_vars
        key = MemberKey.load_or_make(agent.cluster_vars, agent.sealer)
        self.keys[agent.cluster] = key
        agent.key = key
        agent.cluster_vars.put("domain/member", {"cluster": agent.cluster})
        roster = json.loads(self.vars.get("domain/members")[0]["doc"])
        roster["rev"] += 1
        roster["members"][agent.cluster] = {"key": key.pub, "seal": key.seal_pub}
        self.vars.put("domain/members", {"doc": json.dumps(roster)})
        client = CarryClient(self.door, agent.cluster, key, self.wall)
        _doors[agent.cluster_vars] = SimpleNamespace(request=lambda kind, ref:
            client.request_token("cam", kind, ref, "camworker"))
        if device is not None:
            self.devices.append(device)

    def assign(self, ref, cluster, *, origin=None, copies=()):
        origin = origin or next(d.name for d in self.devices if d.serial == ref)
        value = placement.assign(self.vars, "rec", ref,
            {"cluster": cluster, "origin": origin, "copies": list(copies)}, self.wall)
        for agent in self.agents:
            try:
                sync(agent)
            except Unreachable:
                pass
        return value

    def observe(self, name, rows, status, *, worker="fixture-rec", ingest=None,
                peer=None, kind="local"):
        """Publish an explicit scenario observation through the ordinary recorder publisher."""
        vars_ = self.stores[name]
        key = (name, worker)
        publisher = self.publishers.get(key)
        if publisher is None:
            publisher = Worker(REC_SPEC.sub, None, vars_, self.objects,
                wall=self.wall, clock=self.wall, spec=REC_SPEC)
            publisher.SUB = REC_SPEC.sub
            publisher.claim_slot(worker)
            self.publishers[key] = publisher
        publisher.renew_slot()
        publisher.rows, publisher.volume = rows, "fixture-" + worker
        vars_.put("rec/volumes/" + publisher.volume, {"kind": kind})
        publisher.ingest_url, publisher.archive_url = ingest, peer
        source = member_book(vars_, "domain/cam/sources", name)
        publisher._look = lambda: SimpleNamespace(sources=lambda: source)
        publish(publisher, "primaries", primaries(publisher, status))

    def collect(self):
        for publisher in self.publishers.values():
            try:
                publisher.renew_slot()
            except Unreachable:
                pass
        for device in self.devices:
            device.publish()
        for agent in self.agents:
            try:
                sync(agent)
            except Unreachable:
                pass
        # The holder is also a contributing member; an empty camera snapshot is a
        # complete local publication on a recorder-only cluster.
        for name, cluster in self.inputs.view.fed.clusters.items():
            if name not in self.stores or any(a.cluster == name for a in self.agents):
                continue
            cluster.objects.put("cam/snapshot/fixture", json.dumps({"cluster": name,
                "ts": self.wall(), "cameras": []}).encode())
            sent = max(self.wall(), math.nextafter(self.report_at.get(name, float("-inf")), math.inf))
            self.report_at[name] = sent
            report(name, self.stores[name], cluster.objects, self.objects, sent, key=self.keys[name])
        got = {}
        for spec, book in ((SPEC, "sources"), (REC_SPEC, "primaries")):
            got[book] = bookruntime.collect(self.holder, spec, book)
        for agent in self.agents:
            try:
                sync(agent)
            except Unreachable:
                pass
        return got
