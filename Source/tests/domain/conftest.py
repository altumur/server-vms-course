"""Fakes: N clusters, each a Variables raft and an object store, with a
switch to make one unreachable; the clusters' own controller and workers
(М11's, real) publishing what a cluster publishes; a clock."""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # Source/

from vms.controller import VmsController  # noqa: E402
from w2cplatform.cluster.objectstore import FsObjectStore  # noqa: E402
from w2cplatform.cluster.variables import FakeVariables  # noqa: E402
from vms.worker import VmsWorker  # noqa: E402
from w2cplatform.domain.federation import Cluster, Federation, Unreachable  # noqa: E402
from vms.worker import FakeActuator  # noqa: E402


class Clock:
    def __init__(self, t=1000.0): self.t = t
    def __call__(self): return self.t
    def advance(self, s): self.t += s


def real_card(t0: float, t1: float, recording: str = "1-card", step: float = 1.0, size: int = 256, card=None):
    """A REAL card — `vms.card.CardBuffer`, the camera's buffer of segment files, no engine — holding `[t0, t1)` of
    `recording`: a frame every `step` seconds of `size` bytes, a key frame every two seconds. Its reader for a pusher
    is `card.pieces` (the sixth review: the tests of the card ran on fakes that returned what no card returns)."""
    from vms.card import CardBuffer
    from vms.worker import fake_samples
    card = card or CardBuffer(tempfile.mkdtemp(prefix="card-"))
    for s in fake_samples(t0, t1, step=step, gop=2.0, size=size):
        card.append(f"{recording}/e1", s)
    return card


class Link:
    """One switch per cluster: when down, every read raises Unreachable."""
    def __init__(self): self.up = True


class LinkedVariables(FakeVariables):
    def __init__(self, link: Link):
        super().__init__(); self.link = link
    def _linked(self):
        if not self.link.up: raise Unreachable("region did not answer")
    def get(self, path): self._linked(); return super().get(path)
    def put(self, path, items, cas=None): self._linked(); return super().put(path, items, cas)
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
    """A cluster with М11's real controller and workers running on it: what
    the domain sees is exactly what they publish — the snapshot and the
    heartbeats — and nothing else."""

    def __init__(self, cluster: Cluster, wall: Clock, workers=(("w-0", "srv-1"),), capacity: int = 50):
        self.c, self.wall = cluster, wall
        self.ctl = VmsController(cluster.vars, cluster.objects, capacity=capacity, wall=wall, cluster=cluster.name)
        self.workers: dict[str, VmsWorker] = {}
        self.alloc = 0
        for name, server in workers:
            self.add_worker(name, server, capacity)

    def add_worker(self, name: str, server: str, capacity: int = 50) -> VmsWorker:
        self.alloc += 1
        env = {"SLOT_INDEX": name.split("-")[1], "SERVER_NAME": server, "INSTANCE_ID": f"{self.c.name}-alloc-{self.alloc}",
               "LABELS": ",".join(sorted(self.c.reaches))}
        w = VmsWorker(None, self.c.vars, self.c.objects, FakeActuator(), env=env, clock=self.wall, wall=self.wall, capacity=capacity)
        w.heartbeat_once()
        self.workers[name] = w
        return w

    def create(self, *refs, **fields) -> list[int]:
        """Cameras the domain forwarded (by ref); the cluster's controller places them
        on its workers; then everybody heartbeats and the snapshot goes out."""
        ids = []
        for ref in refs:
            r = self.ctl.create_camera({"name": f"cam{ref}", "source": f"driverpack://file/{ref}.mp4", "ref": str(ref), **fields})
            ids.append(r["id"])
        self.ctl.ensure_placed()
        self.tick()
        return ids

    def tick(self) -> None:
        for w in self.workers.values():
            w.reconcile_once(); w.heartbeat_once()
        self.ctl.publish_snapshot()


def snapshot(cluster: Cluster, cameras: dict[int, tuple[str, str]], ts: float) -> None:
    """A cluster's snapshot written by hand — ONE OBJECT PER WORKER, which is the
    shape М10's controller publishes: {camera: (worker, server)}."""
    shards: dict[str, list] = {}
    for i, (c, (w, s)) in enumerate(cameras.items()):
        shards.setdefault(w or "unplaced", []).append(
            {"id": i + 1, "ref": str(c), "name": f"cam{c}", "worker": w or None, "server": s})
    for name, rows in shards.items():
        cluster.objects.put(f"vms/snapshot/{name}", json.dumps(
            {"cluster": cluster.name, "worker": rows[0]["worker"], "ts": ts, "cameras": rows}).encode())


def heartbeat(cluster: Cluster, worker: str, cams: list[int], ts: float, server: str = "srv-1", epoch: int = 1,
              revision: int = 1, observed: int | None = None, phase: str = "running") -> None:
    """What М10's worker writes: its status per camera."""
    cluster.objects.put(f"vms/heartbeats/{worker}", json.dumps({
        "worker": worker, "ts": ts, "server": server, "instance": f"{worker}-i", "capacity": 50, "headroom": 50 - len(cams),
        "status": [{"id": c, "name": f"cam{c}", "enabled": True, "phase": phase, "position": "converged",
                    "revision": revision, "observed_revision": revision if observed is None else observed, "epoch": epoch} for c in cams]}).encode())
