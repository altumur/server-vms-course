"""A server cluster of the camera–office–centre stand: the cluster stand's `Cluster` (`tests/cluster/conftest.py`) of
ONE server named as the cluster, on the stand's one wall clock, its store's index from a base of its own — so that in a
trace of six stores no two writes share a number — and its temporary tree where the scenario says."""
from __future__ import annotations

import os

from tests.cluster.conftest import Cluster, Server, Store
from w2cplatform.storemachine import ADMIN


class StandCluster(Cluster):
    def __init__(self, name: str, labels: str, log, index_base: int, clock, wall, root: str):
        os.makedirs(root, exist_ok=True)
        self.name, self.root = name, root
        self.store = Store(log=log, index_base=index_base)
        self.clock, self.wall = clock, wall
        self.servers = {name: Server(root, name, labels)}
        self.pids = index_base + 100                       # instance names `<server>:<pid>:…`, apart per cluster
        self.vars = self.store.door(ADMIN)                 # the tests' own hand: root's socket — never traced
        for n in self.servers:
            self._resource(n)
        self.objects = self.objects_on(name, self.vars)

    @property
    def server(self):
        return self.servers[self.name]
