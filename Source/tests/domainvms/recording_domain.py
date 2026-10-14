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
from w2cplatform.domain.uplink import report, _CopyObjects
from w2cplatform.trust.memberkey import MemberKey
from w2cplatform.trust.tokens import DeclaredIssuer
from w2cplatform.worker import Worker

_doors = WeakKeyDictionary()


def role_requests(vars_, role=None):
    door = _doors.get(vars_)
    if role is None or door is None:
        return door
    return SimpleNamespace(request=lambda kind, ref, by=None: door.request(kind, ref, by, role))


def bind_requests(vars_, client):
    # The camera keeps the same local role door when its agent follows a new
    # holder. Existing pushers must see that road rather than a captured old one.
    door = _doors.setdefault(vars_, SimpleNamespace())
    door.request = lambda kind, ref, by=None, role=None: client.request_token(
        "rec" if kind == "upstream" else "cam", kind, ref,
        role or ("recworker" if kind == "upstream" else "camworker"), by)


def camera_pusher(serial, flash, dial, **kw):
    from vms.ingest import CameraPusher
    kw.setdefault("token_requests", role_requests(flash))
    return CameraPusher(serial, flash, dial, **kw)


class RecordingDomain:
    def __init__(self, inputs, signer, *, agents=(), devices=(), recorders=(), domain_objects=None):
        self.inputs, self.signer = inputs, signer
        self.wall = inputs.wall
        agents, devices = list(agents), list(devices)
        self.holder_cluster = inputs.view.fed.domain_holder
        self.vars = next((d.flash for d in devices if d.name == self.holder_cluster.name), self.holder_cluster.vars)
        self.objects = self.holder_cluster.objects if domain_objects is None else domain_objects
        from w2cplatform.trust.documents import sign
        if self.vars.get("domain/holder")[0] is None:
            self.vars.put("domain/holder", {"doc": json.dumps(sign({"term": 1,
                "holder": self.holder_cluster.name, "at": self.wall()}, signer.tokens))})
        self.agents, self.devices = list(agents), list(devices)
        self.recorders = []
        self.publishers = {}
        self.auto_workers = {}
        self.report_at = {}
        self.keys = {}
        self.door = HolderDoor(self.vars, self.objects, sealer=getattr(inputs.vars, "sealer", None), wall=self.wall,
            token_issuer=DeclaredIssuer(signer.tokens, declared.token_kinds()))
        self.holder = SimpleNamespace(vars=self.vars, objects=self.objects,
            wall=self.wall, view=inputs.view, term=None, signer=signer, sealer=getattr(inputs.vars, "sealer", None))
        stores = {d.name: d.flash for d in self.devices}
        stores.update({a.cluster: a.cluster_vars for a in self.agents})
        for name, cluster in inputs.view.fed.clusters.items():
            if not isinstance(cluster.objects, _CopyObjects):
                stores.setdefault(name, cluster.vars)
        self.stores = stores
        admitted = self.vars.get("domain/members")[0]
        previous = json.loads(admitted["doc"]) if admitted else {"rev": 0, "members": {}}
        roster = dict(previous["members"])
        for name, vars_ in stores.items():
            local_agent = next((a for a in self.agents if a.cluster == name), None)
            key = (local_agent.key if local_agent and local_agent.key is not None else
                   MemberKey.load_or_make(vars_, local_agent.sealer if local_agent else None))
            self.keys[name] = key
            roster[name] = {"key": key.pub, "seal": key.seal_pub}
            vars_.put("domain/member", {"cluster": name})
            client = CarryClient(self.door, name, key, self.wall)
            bind_requests(vars_, client)
        self.vars.put("domain/members", {"doc": json.dumps({"rev": previous["rev"] + 1, "members": roster})})
        if (inputs.centre or any(c.via for c in inputs.view.fed.clusters.values())) and self.vars.get("domain/topology")[0] is None:
            self.vars.put("domain/topology", {"doc": json.dumps({"rev": 1, "centre": inputs.centre,
                "star": sorted(inputs.star), "via": {n: c.via for n, c in inputs.view.fed.clusters.items() if c.via}})})
        for agent in self.agents:
            agent.key = self.keys[agent.cluster]
            if agent.cluster_objects is None:
                agent.cluster_objects = next((d.disk for d in self.devices if d.name == agent.cluster),
                    inputs.view.fed.clusters[agent.cluster].objects)
            if not hasattr(agent.domain_vars, "answer_for"):
                agent.domain_vars = CarryClient(self.door, agent.cluster, agent.key, self.wall)
            if agent.domain_objects is None and not hasattr(agent.domain_vars, "publish"):
                agent.domain_objects = self.objects
            if agent.published is None:
                agent.published = inputs.view.fed.clusters[agent.cluster].objects
            if not agent.published.list("cam/snapshot/"):
                agent.published.put("cam/snapshot/fixture", json.dumps({"cluster": agent.cluster,
                    "ts": self.wall(), "cameras": []}).encode())
        for recorder in recorders:
            self.add_recorder(recorder)

    def add_recorder(self, recorder):
        """An ordinary ingest recorder publishes polls only while it owns its slot."""
        if recorder.slot is None:
            recorder.claim_slot(recorder.name)
        if recorder not in self.recorders:
            self.recorders.append(recorder)

    def add_agent(self, agent, device=None):
        self.agents.append(agent)
        if agent.cluster_objects is None:
            agent.cluster_objects = device.disk if device is not None else self.inputs.view.fed.clusters[agent.cluster].objects
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
        if not hasattr(agent.domain_vars, "answer_for"):
            agent.domain_vars = client
        bind_requests(agent.cluster_vars, client)
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
        self._reports()
        got = {}
        for spec, book in ((SPEC, "sources"), (REC_SPEC, "primaries"), (REC_SPEC, "upstream")):
            got[book] = bookruntime.collect(self.holder, spec, book)
        for agent in self.agents:
            try:
                sync(agent)
            except Unreachable:
                pass
        # Sources arrive through the preceding accepted report and generic book
        # collection. A home then pulses and publishes rec/polls under its slot;
        # the next signed report, not this fixture, supplies the fourth book.
        for recorder in self.recorders:
            recorder.renew_slot()
            recorder.heartbeat_once()
        self._reports()
        got["polls"] = bookruntime.collect(self.holder, REC_SPEC, "polls")
        # Scenarios travel as signed settings; the ordinary auto worker of each
        # path node publishes its own observations under its slot. A camera path
        # node publishes through its embedded publisher in DeviceCluster.publish.
        from vms.autoworker import AutoWorker
        camera_members = {d.name for d in self.devices}
        for name, cluster in self.inputs.view.fed.clusters.items():
            if name not in self.stores or name in camera_members or isinstance(cluster.objects, _CopyObjects):
                continue
            worker = self.auto_workers.get(name)
            if worker is None:
                worker = AutoWorker('a-fixture', self.stores[name], cluster.objects,
                    wall=self.wall, clock=self.wall, env={}, token_requests=role_requests(self.stores[name], 'autoworker'))
                worker.claim_slot(worker.name)
                self.auto_workers[name] = worker
            try:
                worker.renew_slot()
                worker.heartbeat_once()
            except Unreachable:
                pass  # this local process cannot reach its cluster store either
        self._reports()
        # The fixture runs the holder for every declared book, including names.
        for spec in declared.specs():
            for book in spec.domain.merged:
                if book not in got:
                    got[book] = bookruntime.collect(self.holder, spec, book)
        for agent in self.agents:
            try:
                sync(agent)
            except Unreachable:
                pass
        return got

    def _reports(self):
        for agent in self.agents:
            try:
                sync(agent)
            except Unreachable:
                pass
        # The holder is also a contributing member; an empty camera snapshot is a
        # complete local publication on a recorder-only cluster.
        for name, cluster in self.inputs.view.fed.clusters.items():
            if name not in self.stores or isinstance(cluster.objects, _CopyObjects) or any(a.cluster == name for a in self.agents):
                continue
            cluster.objects.put("cam/snapshot/fixture", json.dumps({"cluster": name,
                "ts": self.wall(), "cameras": []}).encode())
            sent = max(self.wall(), math.nextafter(self.report_at.get(name, float("-inf")), math.inf))
            self.report_at[name] = sent
            report(name, self.stores[name], cluster.objects, self.objects, sent, key=self.keys[name])
