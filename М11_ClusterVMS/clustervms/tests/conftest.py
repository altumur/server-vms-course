"""The stand without an orchestrator: three servers, one store, a clock — no Nomad, no MinIO, no GStreamer, and one
real obsd for the whole run, М10's (`vmsserver/tests/conftest.py`): every server's volume is a directory of its own
on it, as every host's would be on its own.

THE STORE is the configstore's own state machine (`w2cplatform/storemachine.py`, `StoreMachine`) — one for the whole
stand, as the raft group is one for the whole cluster — behind a door per role: the daemon's API over that machine
in this process (`storemachine.local_transport`), with the rights of the committed rights file
(`deploy/configstore-rights.json`), opened by every process with the real handle (`ConfigstoreVariables`). A process
of the stand is refused exactly what its unit's socket would be refused on a server. The tests' own hand is the
root-only `admin` socket.

EACH SERVER has its own directory of objects and its resource — the platform's unit on every server, built when the
stand is, its door said in the store (`platform/doors/<server>`) — and a process's objects are `cluster://` on its
own server (`ClusterObjectStore`): its writes are files there, its reads go through the resource on its server,
which asks the others. The door is the resource's own code called in this process (`StandObjects._door`, `StandPeers`)
instead of HTTP: the same answers, no sockets. A server that is `down` answers nothing — neither its objects nor its
events — and what it last said is what a reader that heard it remembers.

A PROCESS is named the way its unit names it: `WORKER_NAME=w-%l-1` — `w-srv-a-1` on srv-a, `r-srv-a-1` for the
recorder; a spare has no name until it takes an offer. There are no allocations. It is built by the entry point's own
`make_worker`/`make_recorder` (`cluster/__main__.py`) and so REGISTERS with its server's resource as a unit's does
(`Worker.present`: a lock in that server's tree while the object lives) — `absent()` is its process ending.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cluster  # noqa: E402,F401  — puts М10's vmsserver on sys.path

from cluster.objectstore import ClusterObjectStore, ObjectsUnavailable  # noqa: E402
from cluster.recworker import ClusterRecorder  # noqa: E402
from cluster.worker import ClusterWorker  # noqa: E402
from vms.worker import FakeActuator  # noqa: E402
from w2cplatform.configstorevars import ConfigstoreVariables  # noqa: E402
from w2cplatform.storemachine import ADMIN, Rights, StoreMachine, local_transport  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RIGHTS = os.path.join(HERE, "deploy", "configstore-rights.json")
SOCKETS = "/run/configstore"
SERVERS = (("srv-a", "vlan:cctv-a"), ("srv-b", "vlan:cctv-a,vlan:cctv-b"), ("srv-c", "vlan:cctv-b"))


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


def host(url: str) -> str:
    return url.split("//", 1)[-1].split("/", 1)[0].split(":", 1)[0]


class Store:
    """The cluster's one store: the machine, the rights file, a door per role. A read takes no version here: on the
    daemon a read is a log entry too and the next write's version is higher by the reads between — nothing may count
    on versions being consecutive, and the stand keeps them so, so a trace reads easily."""

    def __init__(self, rights: str = RIGHTS, index_base: int = 1000, log=None):
        self.machine = StoreMachine(index_base)
        self.lock = threading.Lock()
        self.rights = Rights.load(rights)
        self.log = log

    def submit(self, cmd: dict) -> dict:
        with self.lock:
            if cmd.get("op") in ("get", "list"):
                return self.machine.apply(cmd, self.machine.applied)
            return self.machine.apply(cmd)

    def door(self, role: str, who: str | None = None) -> ConfigstoreVariables:
        """The handle a process of `role` opens: `configstore:///run/configstore/<role>.sock`, traced as `who`."""
        path = f"{SOCKETS}/{role}.sock"
        transport = local_transport(self.submit, self.rights, role)
        if self.log is not None and who:
            transport = self.log.transport(who, path, transport)
        return ConfigstoreVariables(path, transport=transport)


class Server:
    """A box in the cluster: a name, labels, the resource's tree on its disks (`archive` — `resource` is the same
    path, the one a resource is built over), its own objects, its own volume under the tree, which its recorder
    formats — and its resource process (`res`), whose door is `door`."""

    def __init__(self, root: str, name: str, labels: str = ""):
        self.name, self.labels = name, labels
        self.archive = os.path.join(root, name, "archive")
        os.makedirs(self.archive, exist_ok=True)
        self.resource = self.archive
        self.objects = os.path.join(root, name, "objects")
        self.volume = f"file://{self.archive}/volume"
        self.door = f"http://{name}:8090"
        self.down = False
        self.res = None


class StandPeers:
    """The resources' peer client (`w2cplatform.resource.PeerClient`) over the stand's servers instead of HTTP: the
    events mirror's three calls on the peer's directories, and the four of `/v1/objects` on the peer's own resource."""

    def __init__(self, cluster: "Cluster", bucket_seconds: int = 600):
        self.c, self.bucket = cluster, bucket_seconds

    def _srv(self, url: str) -> Server:
        srv = self.c.servers.get(host(url))
        if srv is None or srv.down:
            raise ConnectionError(f"{url} does not answer")
        return srv

    def mirrored(self, url, server):
        from w2cplatform.resource import mirrored_buckets
        return mirrored_buckets(self._srv(url).archive, server, self.bucket)

    def put(self, url, server, path, data):
        dest = os.path.join(self._srv(url).archive, ".mirror", server, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)

    def get(self, url, server, path):
        with open(os.path.join(self._srv(url).archive, ".mirror", server, path), "rb") as f:
            return f.read()

    def objects(self, url, prefix, timeout=None):
        return self._srv(url).res.objects_listing(prefix, "local")[0]

    def object(self, url, key, timeout=None):
        return self._srv(url).res.object_read(key, "local")[0]

    def put_blob(self, url, key, data):
        import io
        self._srv(url).res.take_blob(key, io.BytesIO(data), len(data))

    def delete_object(self, url, key, timeout=None):
        srv = self._srv(url)
        return bool(srv.res.object_delete(key, "local")[0].get(srv.name))


class StandObjects(ClusterObjectStore):
    """A process's `cluster://` objects on `server`: files in its directory, the rest through the resource on it —
    the resource's own code, called here instead of over HTTP; the create-only keys rows in the process's store."""

    def __init__(self, cluster: "Cluster", server: str, vars_, who: str = ""):
        srv = cluster.servers[server]
        super().__init__(srv.objects, srv.door, vars_, wall=cluster.wall, clock=cluster.clock, list_fresh=0)
        self.cluster, self.srv, self.who = cluster, srv, who

    def _log(self):
        log = self.cluster.store.log
        return log if log is not None and log.objects and self.who else None

    def _file(self, write, key, data):
        super()._file(write, key, data)
        log = self._log()
        if log is not None:
            from tests.trace import Call
            log.calls.append(Call(self.who, f"its own files on {self.srv.name}", "PUT", key, None, 0,
                                  None, kind="file"))

    def _door(self, method: str, path: str, query: dict) -> tuple[int, bytes, dict]:
        res = self.srv.res
        if res is None or self.srv.down:
            raise ObjectsUnavailable(f"the resource on {self.srv.name} does not answer")
        scope = query.get("scope", "local")
        if method == "GET" and path == "/v1/objects":
            objs, missing = res.objects_listing(query.get("prefix", ""), scope)
            said = {"server": self.srv.name, "objects": objs, **({"missing": missing} if missing else {})}
            status, body, headers, shown = 200, json.dumps(said).encode(), {}, said
        else:
            key = urllib.parse.unquote(path[len("/v1/objects/"):])
            if method == "GET":
                got, missing = res.object_read(key, scope)
                headers = {"X-Missing": ",".join(missing)} if missing else {}
                if got is None:
                    status, body, shown = 404, b"", (dict(headers) or None)
                else:
                    headers.update({"X-Written": repr(got[1]), "X-Server": got[2]})
                    status, body, shown = 200, got[0], {"bytes": len(got[0]), **headers}
            else:
                deleted, missing = res.object_delete(key, scope)
                said = {"deleted": deleted, **({"missing": missing} if missing else {})}
                status, body, headers, shown = 200, json.dumps(said).encode(), {}, said
        log = self._log()
        if log is not None:
            from tests.trace import Call
            log.calls.append(Call(self.who, f"the resource on {self.srv.name}, {self.srv.door}", method,
                                  f"{path}?{urllib.parse.urlencode(query)}", None, status, shown, kind="objects"))
        return status, body, headers


class Cluster:
    """Three servers, one store, a resource on each — and a clock the tests own."""

    def __init__(self, servers=SERVERS, log=None):
        self.root = tempfile.mkdtemp(prefix="clustervms-")
        self.store = Store(log=log)
        self.clock, self.wall = Clock(), Clock(1_757_500_000.0)
        self.servers = {n: Server(self.root, n, l) for n, l in servers}
        self.pids = 4100
        self.vars = self.store.door(ADMIN)                    # the tests' own hand: root's socket
        for name in self.servers:
            self._resource(name)
        self.objects = self.objects_on("srv-a" if "srv-a" in self.servers else next(iter(self.servers)), self.vars)

    # -- the resource unit on every server ---------------------------------------------------------------------------
    def _resource(self, name: str):
        """`w2c-resource` on `name`: its own socket, its server's objects, its peers the stand's — and its door said
        in the store, as its first heartbeat would say it (the heartbeat itself is `resources_up`'s: a resource that
        never heartbeat is "unknown", which is not "silent")."""
        from cluster.resource import cluster_resource
        srv = self.servers[name]
        v = self.store.door("resource", f"resource on {name}")
        srv.res = cluster_resource(srv.resource, name, srv.door, v, self.objects_on(name, v, f"resource on {name}"),
                                   wall=self.wall, peers=StandPeers(self))
        srv.res.clock = self.clock                                      # its doors and its peers' rests by the stand's clock
        srv.res.space_probe = lambda path: (4 * 10**12, 3 * 10**12)     # a 4 TB disk, 1 TB used — the same on every run
        srv.res.say_door()
        return srv.res

    def resources_up(self, peers=None) -> dict:
        """Each server's resource heartbeating — what makes a server a place footage can go (lesson 6)."""
        self.resources = {}
        for name, srv in self.servers.items():
            if peers is not None:
                srv.res.peers = peers
            srv.res.heartbeat()
            self.resources[name] = srv.res
        return self.resources

    def objects_on(self, server: str, vars_, who: str = "") -> StandObjects:
        return StandObjects(self, server, vars_, who)

    def door(self, role: str, who: str | None = None) -> ConfigstoreVariables:
        return self.store.door(role, who)

    # -- the processes -----------------------------------------------------------------------------------------------
    def env(self, server: str, name: str | None = None, **more) -> dict:
        """What a unit puts in its process's environment: the neutral names of `w2cplatform.runtime` — the name from
        the unit (`WORKER_NAME=w-%l-1`), the server and its labels from `/etc/w2c/w2c.env` — and this incarnation,
        host and pid. A spare has `SPARE_FOR` and no name."""
        self.pids += 1
        env = {"SERVER_NAME": server, "LABELS": self.servers[server].labels, "INSTANCE_ID": f"{server}:{self.pids}",
               "ARCHIVE": self.servers[server].resource}          # `w2c.env`: the platform's events archive here
        if name is not None:
            env["WORKER_NAME"] = name
        env.update({k: str(v) for k, v in more.items()})
        return env

    def worker(self, server: str, capacity: int = 50, actuator=None, name: str | None = None, spare_for=None,
               instance: str | None = None, **kw) -> ClusterWorker:
        """`vms-vmsworker` on `server` — `w-<server>-1`, or a spare for `spare_for` (`vms-vmsworker-spare-<n>`)."""
        name = None if spare_for is not None else (name or f"w-{server}-1")
        env = self.env(server, name, **({"SPARE_FOR": spare_for} if spare_for is not None else {}))
        if instance:
            env["INSTANCE_ID"] = instance
        who = f"vmsworker {name or 'spare'} on {server}"
        v = self.door("vmsworker", who)
        from cluster.__main__ import make_worker
        return make_worker(v, self.objects_on(server, v, who), actuator or FakeActuator(), env=env,
                           clock=self.clock, wall=self.wall, capacity=capacity, **kw)

    def recorder(self, server: str, capacity: int = 50, actuator=None, name: str | None = None,
                 **kw) -> ClusterRecorder:
        """`vms-recworker` on `server` — `r-<server>-1`: its events on THAT server's resource, its footage in that
        server's own volume, through the (one, test) daemon."""
        name = name or f"r-{server}-1"
        who = f"recworker {name} on {server}"
        v = self.door("recworker", who)
        from cluster.__main__ import make_recorder
        return make_recorder(v, self.objects_on(server, v, who), actuator or FakeActuator(),
                             env=self.env(server, name), **self.rec_kw(server, name),
                             clock=self.clock, wall=self.wall, capacity=capacity, **kw)

    def rec_kw(self, server: str, name: str) -> dict:
        return {"archive_root": self.servers[server].archive, "obsd": obsd_session(f"rec-{name}-{self.pids}"),
                "default_quota": TEST_QUOTA, "block": TEST_BLOCK, "read": TEST_READ}

    def controller(self, server: str = "srv-a", who: str | None = None, role: str = "vmscontroller", **kw):
        """`vms-vmscontroller` on `server` (a unit on every server, safe at two)."""
        from cluster.controller import ClusterController
        who = who or f"{role} on {server}"
        v = self.door(role, who)
        return ClusterController(v, self.objects_on(server, v, who), wall=self.wall, **kw)

    def console(self, server: str = "srv-a", who: str | None = None, **kw):
        """`vms-console` on `server`: the operator's rows and nothing else."""
        return self.controller(server, who or f"console on {server}", role="console", **kw)
