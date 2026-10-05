"""The cluster's objects without Variables: files on every server, read through the resources (`cluster://`).

The owner's decision of 3 October: the cluster has no orchestrator, and its objects leave the replicated store —
every object has one writer and almost every one is written again within a pass, so each server keeps its own as
files and its resource answers for them (`/v1/objects`). `ClusterObjectStore` writes here and reads everywhere: the
freshest copy of a key by `written`, the union for a listing. What must be created ONCE across the cluster — a
worker's mark before a device command — is a row in the store; a blob is copied to the next peers on the events
mirror's ring and deleted by the sweep on every server that answers.

Three servers here, each with its own directory of objects and its own resource door on a real socket; one store
for all three (`FakeVariables`, the same contract as the daemon).
"""
import json
import os

from w2cplatform.cluster.objectstore import ClusterObjectStore, ObjectsUnavailable, open_store
from w2cplatform.cluster.variables import FakeVariables
from tests.cluster.conftest import Clock
from w2cplatform.blobs import digest
from w2cplatform.contract import Controller, Subsystem, Worker
from w2cplatform.resource import Resource, resources_seen, serve


class Three:
    """srv-a, srv-b, srv-c: a resource each, serving its server's objects; a `ClusterObjectStore` each over them."""

    def __init__(self, names=("srv-a", "srv-b", "srv-c")):
        import tempfile
        self.root = tempfile.mkdtemp(prefix="cluster-objects-")
        self.vars = FakeVariables()
        self.wall = Clock(1_757_500_000.0)
        self.res, self.store, self.srv = {}, {}, {}
        for name in names:
            store = ClusterObjectStore(os.path.join(self.root, name, "objects"), "", self.vars, wall=self.wall)
            res = Resource(os.path.join(self.root, name, "archive"), name, "", self.vars, store, wall=self.wall)
            srv = serve(res, "127.0.0.1", 0)
            res.url = store.resource = f"http://127.0.0.1:{srv.server_address[1]}"
            self.res[name], self.store[name], self.srv[name] = res, store, srv
        for res in self.res.values():
            res.heartbeat()                                         # its heartbeat a file here, its door a row

    def stop(self):
        for srv in self.srv.values():
            srv.shutdown()


def test_a_heartbeat_written_on_one_server_is_read_on_another():
    """A worker on srv-a puts its heartbeat — a file on srv-a, no store write — and the controller on srv-b sees it
    through srv-b's resource; the resources' own heartbeats are found the same way. No ceiling on the way."""
    c = Three()
    try:
        sub = Subsystem("vms")
        w = Worker(sub, "w-srv-a-1", c.vars, c.store["srv-a"], wall=c.wall)
        w.heartbeat([{"id": 7, "phase": "running"}], server="srv-a")
        assert os.path.exists(os.path.join(c.root, "srv-a", "objects", "vms", "heartbeats", "w-srv-a-1"))
        assert not [k for k in c.vars.list("objects/")]                     # not a row: a file
        ctl = Controller(sub, c.vars, c.store["srv-b"], wall=c.wall)
        assert ctl.workers_seen()["w-srv-a-1"].extra["server"] == "srv-a"
        assert sorted(resources_seen(c.store["srv-c"])) == ["srv-a", "srv-b", "srv-c"]
        assert all(s.max_bytes == 0 for s in c.store.values())
    finally:
        c.stop()


def test_the_copy_written_last_wins_wherever_it_is():
    """A key two servers hold — the controller moved from srv-a to srv-b, and srv-a's old shard is still on its disk:
    every reader, srv-a's included, gets the one written last, by `written` (the writer's clock)."""
    c = Three()
    try:
        c.store["srv-a"].put("vms/snapshot/w-1", b"from srv-a")
        c.wall.advance(30)
        c.store["srv-b"].put("vms/snapshot/w-1", b"from srv-b")
        for name in ("srv-a", "srv-b", "srv-c"):
            assert c.store[name].get("vms/snapshot/w-1") == b"from srv-b", name
        assert c.store["srv-c"].list("vms/snapshot/") == ["vms/snapshot/w-1"]
    finally:
        c.stop()


def test_a_server_gone_is_named_and_the_others_are_read():
    """srv-c's resource stops: a listing on srv-a is the union of srv-a and srv-b, and srv-c is NAMED (`missing`) —
    not an error that hides everybody's objects. The resource on THIS server silent is different: nothing can be
    read from here, and the store says so (`ObjectsUnavailable`) rather than answering a listing of nothing."""
    c = Three()
    try:
        for name in c.store:
            c.store[name].put(f"vms/heartbeats/w-{name}-1", b"{}")
        c.srv["srv-c"].shutdown(); c.srv["srv-c"].server_close()
        assert c.store["srv-a"].list("vms/heartbeats/") == ["vms/heartbeats/w-srv-a-1", "vms/heartbeats/w-srv-b-1"]
        assert c.store["srv-a"].missing == ["srv-c"]
        assert c.store["srv-a"].get("vms/heartbeats/w-srv-b-1") == b"{}"
        try:
            c.store["srv-c"].list("vms/")
            raise AssertionError("a silent door on this server was read as an empty cluster")
        except ObjectsUnavailable as e:
            assert "does not answer" in str(e)
    finally:
        c.srv["srv-a"].shutdown(); c.srv["srv-b"].shutdown()


def test_a_reader_that_heard_a_server_answers_with_what_it_said_last_while_it_is_missing():
    """Found by the module's stand (the power pull, the dead server's doors down): a server's objects are files on it,
    and with it gone its worker's last heartbeat and its resource's left every listing — a controller could not tell
    which server the worker ran on, nor that its resource was silent rather than unknown, and the dead server's units
    never moved. A reader keeps what it last listed and read of each server: while that server is MISSING its keys
    are in the listing and `get` answers their last bytes, ageing by their own `ts`. A reader that never heard it says
    nothing of it; a server that answers again answers for itself, and a key it answers without is let go."""
    c = Three()
    try:
        for name in c.store:
            c.store[name].put(f"vms/heartbeats/w-{name}-1", f'{{"ts": "{name}"}}'.encode())
        reader, late = c.store["srv-a"], ClusterObjectStore(os.path.join(c.root, "late"), c.store["srv-a"].resource,
                                                            c.vars, wall=c.wall, list_fresh=0)
        reader.list_fresh = 0
        assert reader.list("vms/heartbeats/") == [f"vms/heartbeats/w-{n}-1" for n in ("srv-a", "srv-b", "srv-c")]
        assert reader.get("vms/heartbeats/w-srv-c-1") == b'{"ts": "srv-c"}'
        c.srv["srv-c"].shutdown(); c.srv["srv-c"].server_close()
        assert reader.list("vms/heartbeats/") == [f"vms/heartbeats/w-{n}-1" for n in ("srv-a", "srv-b", "srv-c")]
        assert reader.missing == ["srv-c"] and reader.get("vms/heartbeats/w-srv-c-1") == b'{"ts": "srv-c"}'
        assert late.list("vms/heartbeats/") == ["vms/heartbeats/w-srv-a-1", "vms/heartbeats/w-srv-b-1"]   # never heard it
        assert late.get("vms/heartbeats/w-srv-c-1") is None
        c.store["srv-b"].local.delete("vms/heartbeats/w-srv-b-1")                  # an answering server, without the key
        assert reader.list("vms/heartbeats/") == ["vms/heartbeats/w-srv-a-1", "vms/heartbeats/w-srv-c-1"]
    finally:
        c.srv["srv-a"].shutdown(); c.srv["srv-b"].shutdown()


def test_a_blob_is_mirrored_and_a_corrupted_copy_is_refused_and_read_elsewhere():
    """The console on srv-a puts a mask; srv-a's resource pass copies it to the next live peer on the ring (srv-b),
    asked first what it holds — once. A copy that rotted on srv-a is refused on the read and the blob is taken from
    srv-b, on srv-a and on srv-c alike; a peer that sends bytes that are not the blob is refused before they land."""
    c = Three()
    try:
        mask = b"a mask " * 4000
        key = f"det/blobs/{digest(mask)}"
        c.store["srv-a"].put_durable(key, mask)
        assert c.res["srv-a"].pass_()["blobs"] == {"mirrored": 1, "peers": ["srv-b"]}
        assert c.res["srv-a"].mirror_blobs() == {"mirrored": 0, "peers": ["srv-b"]}         # it holds it: not again
        assert c.store["srv-b"].local.get(key) == mask and c.store["srv-c"].local.get(key) is None
        with open(os.path.join(c.root, "srv-a", "objects", key), "wb") as f:
            f.write(b"x" * len(mask))                                                         # the disk rotted
        assert c.store["srv-a"].get(key) == mask and c.store["srv-c"].get(key) == mask
        try:
            c.res["srv-a"].peers.put_blob(c.res["srv-c"].url, key, b"x" * len(mask))
            raise AssertionError("a copy that is not the blob was kept")
        except Exception as e:                                                                # noqa: BLE001
            assert getattr(e, "code", None) == 400
        assert c.store["srv-c"].local.get(key) is None
    finally:
        c.stop()


def test_a_shard_of_a_megabyte_is_an_object_like_any_other():
    """The 64 KiB went with the Variables: a mebibyte shard is written on srv-a and read whole on srv-c."""
    c = Three()
    try:
        big = json.dumps({"cameras": ["x" * 1000] * 1048}).encode()
        assert len(big) > 1 << 20
        c.store["srv-a"].put("vms/snapshot/w-1", big)
        assert c.store["srv-c"].get("vms/snapshot/w-1") == big
    finally:
        c.stop()


def test_a_command_mark_is_a_row_and_conflicts_across_the_cluster():
    """Two holders of one device on two servers both mark the command: create-only on two directories would be two
    winners. The mark is a row `objects/vms/commands/<id>` in the store, so the second `put_new` loses wherever it is,
    and every server lists and reads it. A create-only key the store does not route there is refused, in words."""
    c = Three()
    try:
        a, b = c.store["srv-a"], c.store["srv-b"]
        assert a.put_new("vms/commands/r1", json.dumps({"instance": "a"}).encode())
        assert not b.put_new("vms/commands/r1", json.dumps({"instance": "b"}).encode())
        assert c.vars.list("objects/") == ["objects/vms/commands/r1"]
        assert not os.path.exists(os.path.join(c.root, "srv-a", "objects", "vms", "commands"))
        assert json.loads(c.store["srv-c"].get("vms/commands/r1"))["instance"] == "a"
        assert "vms/commands/r1" in c.store["srv-c"].list("vms/")
        b.delete("vms/commands/r1")
        assert a.get("vms/commands/r1") is None
        try:
            a.put_new("vms/heartbeats/w-1", b"{}")
            raise AssertionError("a create-only write went to files")
        except ValueError as e:
            assert "objects.rows" in str(e)
    finally:
        c.stop()


def test_the_sweep_deletes_a_blob_on_every_server_that_answers():
    """`SpecController.sweep_blobs` on srv-a: the replaced mask was mirrored to srv-b; the sweep marks it from the
    cluster's listing and, a grace later, deletes it here and on the peers. The mask the row names stays everywhere."""
    from vms.config import DET_SPEC
    from w2cplatform.spec import SpecController
    c = Three()
    try:
        ctl = SpecController(DET_SPEC, c.vars, c.store["srv-a"], wall=c.wall)
        ctl.create({"name": "7-linecross", "cam": "7", "kind": "linecross"})
        old = ctl.put_blob(b"old mask")
        ctl.update("7-linecross", {"mask": old})
        new = ctl.put_blob(b"new mask")
        ctl.update("7-linecross", {"mask": new})
        c.res["srv-a"].mirror_blobs()
        assert c.store["srv-b"].local.get(f"det/blobs/{old}") == b"old mask"
        assert ctl.sweep_blobs()["marked"] == 1
        c.wall.advance(SpecController.SWEEP_GRACE + 1)
        assert ctl.sweep_blobs()["deleted"] == 1
        for name in ("srv-a", "srv-b"):
            assert c.store[name].local.get(f"det/blobs/{old}") is None, name
            assert c.store[name].local.get(f"det/blobs/{new}") == b"new mask", name
    finally:
        c.stop()


def test_open_store_reads_the_cluster_url():
    """`OBJECTS=cluster:///data/platform/objects?resource=http://127.0.0.1:8090` — the directory and the door."""
    import tempfile
    d = tempfile.mkdtemp(prefix="cluster-url-")
    s = open_store(f"cluster://{d}/objects?resource=http://10.0.0.7:8090", vars_=FakeVariables())
    assert isinstance(s, ClusterObjectStore) and s.local.root == f"{d}/objects" and s.resource == "http://10.0.0.7:8090"
    assert open_store(f"cluster://{d}/o2").resource == "http://127.0.0.1:8090"
