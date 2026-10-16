"""Fakes: N clusters, each a Variables raft and an object store, with a
switch to make one unreachable; the clusters' own controller and workers
(М11's, real) publishing what a cluster publishes; a clock."""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # Source/

from w2cplatform.cluster.objectstore import FsObjectStore  # noqa: E402
from w2cplatform.cluster.variables import FakeVariables, Conflict  # noqa: E402
from w2cplatform.epoch import next_epoch  # noqa: E402
from w2cplatform.domain.federation import Cluster, Federation, Unreachable  # noqa: E402


def _ensure_camera_spec():
    """Load published cam and its declared near neighbour (currently rec), required by ADR-0056.

    Only their YAML contracts enter the catalogue; no VMS implementation is imported.
    """
    from pathlib import Path
    from w2cplatform import catalog
    from w2cplatform.spec import SubsystemSpec
    directory = Path(__file__).parents[2] / "vms"
    loaded = {spec.name: spec for spec in catalog.specs()}
    camera = loaded.get("cam")
    if camera is None:
        camera = SubsystemSpec.load(str(directory / "cam.subsystem.yaml"))
    if camera.near not in ("", "none") and camera.near not in loaded:
        SubsystemSpec.load(str(directory / f"{camera.near}.subsystem.yaml"))
    return camera


class Clock:
    def __init__(self, t=1000.0): self.t = t
    def __call__(self): return self.t
    def advance(self, s): self.t += s


class Link:
    """One switch per cluster: when down, every read raises Unreachable."""
    def __init__(self): self.up = True


class LinkedVariables(FakeVariables):
    def __init__(self, link: Link):
        super().__init__(); self.link = link
    def _linked(self):
        if not self.link.up: raise Unreachable("region did not answer")
    def get(self, path): self._linked(); return super().get(path)
    def put(self, path, items, cas=None, *, guard=None): self._linked(); return super().put(path, items, cas, guard=guard)
    def delete(self, path, cas=None, *, guard=None): self._linked(); return super().delete(path, cas, guard=guard)
    def list(self, prefix): self._linked(); return super().list(prefix)
    def as_writer(self, writer, allowed=None):
        v = LinkedVariables.__new__(LinkedVariables); v.__dict__ = self.__dict__.copy(); v.writer = writer
        if allowed is not None: self.acl[writer] = list(allowed)
        return v


class LinkedObjects(FsObjectStore):
    def __init__(self, root, link: Link):
        super().__init__(root); self.link = link
    def _linked(self):
        if not self.link.up: raise Unreachable("region did not answer")
    def put(self, k, d): self._linked(); return super().put(k, d)
    def get(self, k): self._linked(); return super().get(k)
    def list(self, p): self._linked(); return super().list(p)


def make_cluster(name: str, reaches=(), domain: bool = False) -> tuple[Cluster, Link]:
    link = Link()
    c = Cluster(name, LinkedVariables(link), LinkedObjects(tempfile.mkdtemp(prefix=f"{name}-"), link),
                frozenset(reaches), domain)
    return c, link


def make_domain(spec: dict[str, tuple], domain_holder: str) -> tuple[Federation, dict[str, Link]]:
    """spec: {"north": ("vlan:a", "vlan:b"), ...}"""
    fed, links = Federation(), {}
    for name, reaches in spec.items():
        c, link = make_cluster(name, reaches, name == domain_holder)
        fed.add(c); links[name] = link
    return fed, links


class Running:
    """A generic testsub controller and worker, with no subsystem implementation involved."""
    def __init__(self, cluster: Cluster, wall: Clock, workers=(("w-0", "srv-1"),), capacity: int = 50):
        from w2cplatform.spec import SpecController
        from tests.conftest import CounterWorker, testsub
        from w2cplatform import catalog
        self.c, self.wall = cluster, wall
        self.spec = testsub()
        catalog.register(self.spec)
        self.ctl = SpecController(self.spec, cluster.vars, cluster.objects, wall=wall, cluster=cluster.name)
        self.workers = {}
        for name, server in workers:
            worker = CounterWorker(cluster.vars, cluster.objects, name=name, server=server, capacity=capacity,
                                   wall=wall, clock=wall)
            worker.heartbeat_once()
            self.workers[name] = worker

    def create(self, *refs, **fields):
        out = []
        for ref in refs:
            row = self.ctl.create({"name": str(ref), "start": 1, "labels": [], **fields})
            out.append(row["name"])
        self.tick()
        return out

    def tick(self):
        self.ctl.ensure_placed()
        for worker in self.workers.values():
            worker.reconcile_once()
            worker.heartbeat_once()
        self.ctl.publish_snapshot()


class DomainTestsub2:
    """Generic domain-member stand for the platform's second fixture subsystem.

    It uses only the platform's spec/controller and public snapshot format. Its tally can be named in generic
    domain/book tests without a VMS schema or implementation participating in the process.
    """
    def __init__(self, cluster: Cluster, wall: Clock):
        from tests.conftest import testsub2
        from w2cplatform import catalog
        from w2cplatform.spec import SpecController
        self.cluster, self.wall = cluster, wall
        self.spec = testsub2()
        catalog.register(self.spec)
        self.ctl = SpecController(self.spec, cluster.vars, cluster.objects, wall=wall, cluster=cluster.name)

    def create(self, name: str, of: str, **fields):
        return self.ctl.create({"name": name, "of": str(of), **fields})

    def publish(self):
        self.ctl.publish_snapshot()


class Flash:
    """A counting wrapper around the platform variables used by an embedded-member fixture."""
    def __init__(self, inner): self.inner, self.writes = inner, 0
    def get(self, path): return self.inner.get(path)
    def list(self, prefix): return self.inner.list(prefix)
    def put(self, path, items, cas=None, *, guard=None):
        out = self.inner.put(path, items, cas, guard=guard); self.writes += 1; return out
    def delete(self, path, cas=None, *, guard=None):
        out = self.inner.delete(path, cas, guard=guard); self.writes += 1; return out


class Ram:
    """Thread-safe volatile object store used by the embedded-member fixture."""
    def __init__(self): self._d = {}
    def put(self, key, data): self._d[key] = bytes(data)
    def get(self, key): return self._d.get(key)
    def list(self, prefix): return sorted(k for k in self._d if k.startswith(prefix))
    def delete(self, key): return self._d.pop(key, None) is not None


class _Door:
    def __init__(self, device, store_of): self.device, self.store_of = device, store_of
    def _open(self):
        if not self.device.door_open: raise Unreachable(f"{self.device.name} did not answer")
        return self.store_of()
    def get(self, *a): return self._open().get(*a)
    def put(self, *a, **kw): return self._open().put(*a, **kw)
    def list(self, *a): return self._open().list(*a)
    def delete(self, *a, **kw): return self._open().delete(*a, **kw)


class _Local:
    def __init__(self, device): self.device = device
    def get(self, key): return self.device.ram.get(key)
    def list(self, prefix): return self.device.ram.list(prefix)
    def put(self, key, data): return self.device.ram.put(key, data)


class _LocalConsole:
    def __init__(self, device): self.device = device
    def update_unit(self, unit, fields, subject=None): return self.device._update(unit, fields, subject)


class EmbeddedMember:
    """Generic, in-process one-unit platform member fixture for domain tests.

    It loads published cam and its declared near neighbour (currently rec) so that its console controller
    meets ADR-0056. It interprets camera rows and writes public snapshot and heartbeat shapes directly.
    It imports no VMS implementation; tests of the VMS worker and controller belong under tests/domainvms.
    """
    ROW, EPOCH = "cam/cameras/1", "cam/epoch/1"
    def __init__(self, serial, flash_vars, wall, name=None, reaches=(), address=None, disk=None, pushes=False, can=None):
        _ensure_camera_spec()
        self.serial = str(serial); self.name = name or f"cam-{self.serial}"
        self.flash, self.ram, self.wall = Flash(flash_vars), Ram(), wall
        self.disk = disk or Ram(); self.reaches = frozenset(reaches); self.address = address or f"{self.name}.local"
        self.epoch = self.boots = 0; self.door_open = False; self.pushes = pushes; self.can = can
        self.coverage = None; self.taken_by = set()
    def row(self):
        items, _ = self.flash.get(self.ROW)
        if not items: return {}
        from w2cplatform import catalog
        spec = catalog.spec("cam")
        return {k: v for k, v in spec.row(items).items() if k in items} if spec else dict(items)
    def boot(self, first_name=None):
        self.door_open = False; self.ram = Ram()
        self.epoch, _ = next_epoch(self.flash, self.EPOCH)
        if self.flash.get(self.ROW)[0] is None:
            self.flash.put(self.ROW, {"id": 1, "ref": self.serial, "name": first_name or self.serial, "revision": 1}, cas=0)
        self.boots += 1; self.publish(); self.door_open = True
        return self.epoch
    def power_off(self): self.door_open = False
    def publish(self):
        row = self.row(); now = self.wall(); rev = int(row.get("revision", 1))
        status = {"id": 1, "ref": self.serial, "name": row.get("name", ""), "enabled": True,
                  "phase": "running", "position": "converged", "revision": rev,
                  "observed_revision": rev, "epoch": self.epoch}
        hb = {"worker": self.serial, "ts": now, "server": self.serial, "instance": f"{self.name}-boot-{self.boots}",
              "capacity": 1, "headroom": 0, "status": [status], "polls": True, "taken_by": sorted(self.taken_by)}
        self.ram.put(f"cam/heartbeats/{self.serial}", json.dumps(hb).encode())
        self.ram.put(f"cam/snapshot/{self.serial}", json.dumps({"cluster": self.name, "worker": self.serial, "ts": now,
                    "cameras": [{**row, "worker": self.serial, "server": self.serial}]}).encode())
    def cluster(self, domain=False): return Cluster(self.name, _Door(self, lambda: self.flash), _Door(self, lambda: self.ram), self.reaches, domain)
    def local_objects(self): return _Local(self)
    def disk_door(self): return _Door(self, lambda: self.disk)
    def local_console(self): return _LocalConsole(self)
    def update_unit(self, unit, fields, subject=None):
        if not self.door_open: raise Unreachable(f"{self.name} did not answer")
        return self._update(unit, fields, subject)
    def _update(self, unit, fields, subject=None):
        if str(unit) not in ("1", self.serial): raise RuntimeError("unit not found")
        from w2cplatform.domain.api import refuse_addresses
        refuse_addresses(fields)
        for _ in range(10):
            items, idx = self.flash.get(self.ROW); row = dict(items or {}); row.update(fields)
            row["revision"] = int(row.get("revision", 1)) + 1
            try: self.flash.put(self.ROW, row, cas=idx); break
            except Conflict: continue
        else: raise RuntimeError("row changed repeatedly")
        self.publish(); return {"revision": row["revision"]}
    def current(self, ref): return (1, self.row()) if str(ref) == self.serial else None
    def rec_prefix(self): return f"rec/{self.serial}/e{self.epoch}/"


def member_name(serial): return f"cam-{serial}"

def snapshot(cluster: Cluster, cameras: dict[int, tuple[str, str]], ts: float) -> None:
    """A cluster's snapshot written by hand — ONE OBJECT PER WORKER, which is the
    shape М10's controller publishes: {camera: (worker, server)}."""
    _ensure_camera_spec()
    shards: dict[str, list] = {}
    for i, (c, (w, s)) in enumerate(cameras.items()):
        shards.setdefault(w or "unplaced", []).append(
            {"id": i + 1, "ref": str(c), "name": f"cam{c}", "worker": w or None, "server": s})
    for name, rows in shards.items():
        cluster.objects.put(f"cam/snapshot/{name}", json.dumps(
            {"cluster": cluster.name, "worker": rows[0]["worker"], "ts": ts, "cameras": rows}).encode())


def heartbeat(cluster: Cluster, worker: str, cams: list[int], ts: float, server: str = "srv-1", epoch: int = 1,
              revision: int = 1, observed: int | None = None, phase: str = "running") -> None:
    """What the generic domain test fixture publishes in the platform's heartbeat shape."""
    _ensure_camera_spec()
    cluster.objects.put(f"cam/heartbeats/{worker}", json.dumps({
        "worker": worker, "ts": ts, "server": server, "instance": f"{worker}-i", "capacity": 50, "headroom": 50 - len(cams),
        "status": [{"id": c, "name": f"cam{c}", "enabled": True, "phase": phase, "position": "converged",
                    "revision": revision, "observed_revision": revision if observed is None else observed, "epoch": epoch} for c in cams]}).encode())


class SharedDoor:
    """The shared settings as a person edits them (ADR-0032): through the signer's one operation, `PUT /api/shared`
    (`signer_service.edit_shared`), with a token of the domain for `who` — made an admin of the domain here — against
    the revision the document is at. No test writes the document past it. A refusal raises `ApiError`."""

    def __init__(self, vars_, objects, signer, wall, who: str = "anna"):
        self.vars, self.objects, self.signer, self.wall, self.who = vars_, objects, signer, wall, who

    def current(self):
        from w2cplatform.domain.shared import SharedSettings
        return SharedSettings(self.vars, self.objects, None).current()

    def put(self, shared: dict) -> int:
        """`{<sub>: {<field>: value | None}}` — the edit as the page sends it; the new revision."""
        from w2cplatform.domain.api import ApiError
        from w2cplatform.domain.grants import DOMAIN_GRANTS, Grant, domain_may, grants_from_items, set_domain_grants
        from w2cplatform.domain.signer_service import edit_shared
        from w2cplatform.trust.tokens import PERSON
        if not domain_may(self.vars, self.who, "admin", self.wall()):
            had = grants_from_items(self.vars.get(DOMAIN_GRANTS)[0])
            set_domain_grants(self.vars, [*had, Grant(self.who, "admin", None, 0.0)], self.wall())
        token = self.signer.tokens.issue(self.who, 900, now=self.wall(), kind=PERSON)
        st, out = edit_shared(self.vars, self.objects, self.signer.tokens, self.signer.tokens.keyset(), set(), token,
                              {"base_rev": int(self.current()[0]["rev"]), "shared": shared}, self.wall())
        if st != 200:
            raise ApiError(st, out["detail"])
        return out["rev"]

    # `auto`'s document there: the scenarios between cameras (`auto.subsystem.yaml`, `domain.shared`)
    def scenarios(self) -> list:
        held = ((self.current()[0].get("settings") or {}).get("shared") or {}).get("auto") or {}
        return list(held.get("scenarios") or [])

    def set_scenarios(self, scenarios: list) -> int:
        return self.put({"auto": {"scenarios": scenarios}})


def holder_agent(fed, devices, name: str, wall):
    """The holder's OWN agent on camera `name` (`agent.main` with `DOMAIN_CONFIG_URL`: it reads its own store) — following
    the holder by `CLUSTERS` like any member's agent: every cluster's `/api/held`, through that cluster's door here (one
    that is off does not answer), the greatest term that verifies, carried home as signed (`take_record`). That record is
    what the holder's `check` yields to (the product's `Term.Check`; «Архитектор» 2026-10-11, ADR-0066; the
    camera-office-centre scenario's N12). Replaced, it carries through the new holder's door, as any member."""
    from w2cplatform.domain.agent import DomainAgent, HolderFollower
    from w2cplatform.domain.term import held
    ask = {n: (lambda n=n: held(n, fed.clusters[n].vars)) for n in devices}

    def open_door(rec):
        return fed.clusters[rec["holder"]].vars, devices[rec["holder"]].disk_door()
    return DomainAgent(name, fed.clusters[name].vars, devices[name].flash, now=wall, follow=HolderFollower(ask),
                       open_door=open_door)
