"""Fakes: a Variables raft in memory, an object store on disk, servers with
archive directories, a clock. No Nomad, no MinIO, no GStreamer — and one real
obsd for the whole run, М10's (`vmsserver/tests/conftest.py`): every server's
volume is a directory of its own on it, as every host's would be on its own."""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cluster  # noqa: E402,F401  — puts М10's vmsserver on sys.path

from cluster.objectstore import FsObjectStore  # noqa: E402
from cluster.variables import FakeVariables  # noqa: E402
from cluster.recworker import ClusterRecorder  # noqa: E402
from cluster.worker import ClusterWorker  # noqa: E402
from vms.worker import FakeActuator  # noqa: E402


def _vms_conftest():
    """М10's test helpers — the daemon, a session, footage — loaded by path: both suites are a package `tests`."""
    import importlib.util
    import vms
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(vms.__file__))), "tests", "conftest.py")
    spec = importlib.util.spec_from_file_location("vmsserver_conftest", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VMS_TESTS = _vms_conftest()
obsd_session, footage, store, door = VMS_TESTS.obsd_session, VMS_TESTS.footage, VMS_TESTS.store, VMS_TESTS.door
TEST_QUOTA, TEST_BLOCK, TEST_READ = VMS_TESTS.TEST_QUOTA, VMS_TESTS.TEST_BLOCK, VMS_TESTS.TEST_READ


class Clock:
    def __init__(self, t=1000.0): self.t = t
    def __call__(self): return self.t
    def advance(self, s): self.t += s


class Server:
    """A box in the cluster: a name, labels, the resource's tree on its disks (`archive`, which is also what the
    resource job is built over: `resource`) — and its own volume under it, which its recorder formats."""
    def __init__(self, root: str, name: str, labels: str = "", wall=None):
        self.name, self.labels = name, labels
        self.archive = os.path.join(root, name, "archive")
        os.makedirs(self.archive, exist_ok=True)
        self.resource = self.archive
        self.volume = f"file://{self.archive}/volume"


class Cluster:
    """Three servers, one raft, one object store — and a clock the tests own."""
    def __init__(self, servers=(("srv-a", "vlan:cctv-a"), ("srv-b", "vlan:cctv-a,vlan:cctv-b"), ("srv-c", "vlan:cctv-b"))):
        self.root = tempfile.mkdtemp(prefix="clustervms-")
        self.vars = FakeVariables()
        self.objects = FsObjectStore(os.path.join(self.root, "objects"))
        self.clock, self.wall = Clock(), Clock(1_757_500_000.0)
        self.servers = {n: Server(self.root, n, l, self.wall) for n, l in servers}
        self.allocs = 0

    def env(self, index: int, server: str, alloc: str | None = None) -> dict:
        """What a RUNTIME puts in an allocation's environment — the neutral names of
        `w2cplatform.runtime`, which the jobspec fills from Nomad's own. The loop never
        sees a vendor's name; the file that already knows the orchestrator does the mapping."""
        self.allocs += 1
        return {"SLOT_INDEX": str(index), "SERVER_NAME": server,
                "LABELS": self.servers[server].labels,
                "INSTANCE_ID": alloc or f"alloc-{self.allocs:04d}"}

    def worker(self, index: int, server: str, capacity: int = 50, actuator=None, alloc=None) -> ClusterWorker:
        w = ClusterWorker(self.vars.as_writer(f"vmsworker", ["vms/epoch/*", "vms/slots/*"]), self.objects,
                          actuator or FakeActuator(), env=self.env(index, server, alloc),
                          clock=self.clock, wall=self.wall, capacity=capacity)
        return w

    def recorder(self, index: int, server: str, capacity: int = 50, actuator=None, alloc=None) -> ClusterRecorder:
        """A recorder allocation on `server`: its events on THAT server's resource, its footage in that server's
        own volume, through the (one, test) daemon."""
        return ClusterRecorder(self.vars.as_writer("recworker", ["rec/epoch/*", "rec/slots/*", "rec/holds/*"]), self.objects,
                               actuator or FakeActuator(), env=self.env(index, server, alloc), **self.rec_kw(server, index),
                               clock=self.clock, wall=self.wall, capacity=capacity)

    def rec_kw(self, server: str, index: int) -> dict:
        return {"archive_root": self.servers[server].archive, "obsd": obsd_session(f"rec-{server}-{index}"),
                "default_quota": TEST_QUOTA, "block": TEST_BLOCK, "read": TEST_READ}


def world():
    return FakeVariables(), FsObjectStore(tempfile.mkdtemp(prefix="restore-"))


