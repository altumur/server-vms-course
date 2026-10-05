"""The resource answers for its server's objects (`/v1/objects`, `w2cplatform/resource.py`).

The cluster without an orchestrator keeps its objects as files on every server (the owner's decision of 3 October):
each process writes into its own server's directory, and the resource there serves them — this server's
(`scope=local`) or every server's (`scope=cluster`, the union, the freshest copy of a key by `written`). Who the
other servers are is the store row each resource writes, `platform/doors/<server> {url, since}`. A peer may leave a
copy of a BLOB here, hashed before it is kept; only a blob is ever deleted through the door.
"""
import errno
import json
import os
import urllib.error
import urllib.request

from w2cplatform.blobs import digest
from w2cplatform.objects import FsObjectStore
from w2cplatform.resource import DOORS, Resource, serve
from tests.conftest import Box


def _call(method, url, body=None):
    req = urllib.request.Request(url, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def _servers(box, names=("srv-a", "srv-b")):
    """Two (or more) servers of one cluster: one store, a directory of objects each, a resource each with its door."""
    out = {}
    for name in names:
        objects = FsObjectStore(os.path.join(box.root, name, "objects"))
        res = Resource(os.path.join(box.root, name, "tree"), name, "", box.vars, objects, wall=box.wall)
        srv = serve(res, "127.0.0.1", 0)
        res.url = f"http://127.0.0.1:{srv.server_address[1]}"
        res.heartbeat()                                   # …which says the door: `platform/doors/<server>`
        out[name] = (res, objects, srv)
    return out


def _stop(servers):
    for _, _, srv in servers.values():
        srv.shutdown()


def _at(objects, key, t):
    os.utime(os.path.join(objects.root, key), (t, t))


def test_each_resource_says_its_door_once_and_again_when_it_moves():
    """`platform/doors/<server>` is where the other servers find this one's objects: written by the first heartbeat
    with `{url, since}`, not again while the address stands, and again when it changes."""
    box = Box()
    s = _servers(box, ("srv-a",))
    try:
        res = s["srv-a"][0]
        items, idx = box.vars.get(f"{DOORS}/srv-a")
        assert items["url"] == res.url and float(items["since"]) == box.wall()
        res.heartbeat(); res.heartbeat()
        assert box.vars.get(f"{DOORS}/srv-a")[1] == idx                       # one write, not one per heartbeat
        res.url = "http://10.0.0.7:8090"
        res.heartbeat()
        assert box.vars.get(f"{DOORS}/srv-a")[0]["url"] == "http://10.0.0.7:8090"
    finally:
        _stop(s)


def test_local_is_this_servers_and_cluster_is_everyones_with_the_freshest_copy():
    """`scope=local` lists what this server holds; `scope=cluster` the union of every door, and a key on two servers
    is the copy written last — on either side of the door. The object comes with `X-Written` and `X-Server`."""
    box = Box()
    s = _servers(box)
    try:
        (a, oa, _), (b, ob, _) = s["srv-a"], s["srv-b"]
        oa.put("testsub/heartbeats/w-1", b'{"w": 1}')
        ob.put("testsub/heartbeats/w-2", b'{"w": 2}')
        oa.put("testsub/snapshot/w-1", b"old"); _at(oa, "testsub/snapshot/w-1", 1000.0)
        ob.put("testsub/snapshot/w-1", b"new"); _at(ob, "testsub/snapshot/w-1", 2000.0)    # the controller moved to srv-b
        st, body, _ = _call("GET", f"{a.url}/v1/objects?prefix=testsub/&scope=local")
        assert st == 200 and sorted(json.loads(body)["objects"]) == ["testsub/heartbeats/w-1", "testsub/snapshot/w-1"]
        st, body, _ = _call("GET", f"{a.url}/v1/objects?prefix=testsub/&scope=cluster")
        said = json.loads(body)
        assert st == 200 and said["server"] == "srv-a" and said["missing"] == []
        assert sorted(said["objects"]) == ["testsub/heartbeats/w-1", "testsub/heartbeats/w-2", "testsub/snapshot/w-1"]
        assert said["objects"]["testsub/snapshot/w-1"] == {"written": 2000.0, "server": "srv-b", "size": 3}
        st, body, headers = _call("GET", f"{a.url}/v1/objects/testsub/snapshot/w-1?scope=cluster")
        assert (st, body, headers["X-Server"], float(headers["X-Written"])) == (200, b"new", "srv-b", 2000.0)
        st, body, headers = _call("GET", f"{a.url}/v1/objects/testsub/snapshot/w-1?scope=local")
        assert (st, body, headers["X-Server"]) == (200, b"old", "srv-a")          # local is local, however old
        assert _call("GET", f"{a.url}/v1/objects/testsub/heartbeats/w-2?scope=local")[0] == 404
        assert _call("GET", f"{a.url}/v1/objects/testsub/heartbeats/w-2?scope=cluster")[1] == b'{"w": 2}'
        assert _call("GET", f"{a.url}/v1/objects/testsub/heartbeats/w-9?scope=cluster")[0] == 404
    finally:
        _stop(s)


def test_a_peers_copy_of_a_blob_is_hashed_before_it_is_kept():
    """`PUT /v1/objects/<sub>/blobs/sha256-…` from a peer: the bytes that hash to the name are kept (204); bytes that
    do not are refused with the reason, and leave nothing — not even over a good copy already here."""
    box = Box()
    s = _servers(box, ("srv-a",))
    try:
        a, oa, _ = s["srv-a"]
        mask = b"a mask" * 1000
        key = f"testsub2/blobs/{digest(mask)}"
        st, body, _ = _call("PUT", f"{a.url}/v1/objects/{key}", b"not the mask")
        assert st == 400 and "hash to" in json.loads(body)["error"] and oa.get(key) is None
        assert not [f for f in os.listdir(os.path.join(oa.root, "testsub2", "blobs")) if f.endswith(".tmp")]
        assert _call("PUT", f"{a.url}/v1/objects/{key}", mask)[0] == 204 and oa.get(key) == mask
        assert _call("PUT", f"{a.url}/v1/objects/{key}", b"x" * len(mask))[0] == 400
        assert oa.get(key) == mask                                                  # the good copy stays
    finally:
        _stop(s)


def test_only_a_blob_is_put_or_deleted_through_the_door_and_the_delete_reaches_every_server():
    """A heartbeat, a snapshot shard, a mark: each is written by its own writer on its own server, and the door
    neither takes nor deletes one (405, in words). A blob is deleted here, or on every server with `scope=cluster`
    — the sweep's delete."""
    box = Box()
    s = _servers(box)
    try:
        (a, oa, _), (b, ob, _) = s["srv-a"], s["srv-b"]
        oa.put("testsub/heartbeats/w-1", b"{}")
        for method in ("PUT", "DELETE"):
            st, body, _ = _call(method, f"{a.url}/v1/objects/testsub/heartbeats/w-1", b"{}" if method == "PUT" else None)
            assert st == 405 and "not a blob" in json.loads(body)["error"], (method, st, body)
        assert oa.get("testsub/heartbeats/w-1") == b"{}"
        key = f"testsub2/blobs/{digest(b'mask')}"
        oa.put(key, b"mask"); ob.put(key, b"mask")
        st, body, _ = _call("DELETE", f"{a.url}/v1/objects/{key}?scope=local")
        assert st == 200 and json.loads(body)["deleted"] == {"srv-a": True} and ob.get(key) == b"mask"
        oa.put(key, b"mask")
        st, body, _ = _call("DELETE", f"{a.url}/v1/objects/{key}?scope=cluster")
        assert st == 200 and json.loads(body)["deleted"] == {"srv-a": True, "srv-b": True}
        assert oa.get(key) is None and ob.get(key) is None
    finally:
        _stop(s)


def test_a_door_that_does_not_answer_is_named_and_the_rest_is_answered():
    """A server whose resource is gone is MISSING from the cluster's answer, by name (`missing`, `X-Missing`) —
    not an error that takes every other server's objects with it."""
    box = Box()
    s = _servers(box)
    try:
        (a, oa, _), (b, ob, srv_b) = s["srv-a"], s["srv-b"]
        oa.put("testsub/heartbeats/w-1", b"1"); ob.put("testsub/heartbeats/w-2", b"2")
        srv_b.shutdown(); srv_b.server_close()
        st, body, _ = _call("GET", f"{a.url}/v1/objects?prefix=testsub/&scope=cluster")
        said = json.loads(body)
        assert st == 200 and said["missing"] == ["srv-b"] and list(said["objects"]) == ["testsub/heartbeats/w-1"]
        st, body, headers = _call("GET", f"{a.url}/v1/objects/testsub/heartbeats/w-1?scope=cluster")
        assert (st, body, headers.get("X-Missing")) == (200, b"1", "srv-b")
    finally:
        s["srv-a"][2].shutdown()


def test_a_garbled_request_is_answered_in_words():
    """A scope that is neither, a prefix or a key that leaves the tree, a length that is not a number: 400 with the
    reason, never a stack trace and never a guess at what was meant."""
    box = Box()
    s = _servers(box, ("srv-a",))
    try:
        url = s["srv-a"][0].url
        for path, words in (("/v1/objects?prefix=testsub/&scope=everywhere", "scope is 'local'"),
                            ("/v1/objects?prefix=../etc/", "not the beginning of a key"),
                            ("/v1/objects?prefix=/etc", "not the beginning of a key"),
                            ("/v1/objects/testsub/../../etc/passwd", "is not a key")):
            st, body, _ = _call("GET", url + path)
            assert st == 400 and words in json.loads(body)["error"], (path, st, body)
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", s["srv-a"][2].server_address[1], timeout=5)
        c.putrequest("PUT", f"/v1/objects/testsub2/blobs/{digest(b'x')}")
        c.putheader("Content-Length", "ten")
        c.endheaders()
        r = c.getresponse()
        assert r.status == 400 and "is not a number of bytes" in json.loads(r.read())["error"]
    finally:
        _stop(s)


def test_a_key_that_names_a_directory_or_a_temporary_file_is_no_object():
    """The review's twelfth pass, minor: `GET /v1/objects/testsub` — a key that is a directory — dropped the connection, and
    an in-flight put's `….tmp` file was served as an object though no listing names it. Both are 404, on either scope."""
    box = Box()
    s = _servers(box)
    try:
        (a, oa, _), (b, ob, _) = s["srv-a"], s["srv-b"]
        oa.put("testsub/heartbeats/w-1", b'{"w": 1}')
        with open(os.path.join(oa.root, "testsub", "heartbeats", "w-1.x1.tmp"), "wb") as f:
            f.write(b"half")
        for scope in ("local", "cluster"):
            for key in ("testsub", "testsub/heartbeats", "testsub/heartbeats/w-1.x1.tmp"):
                st, _, _ = _call("GET", f"{a.url}/v1/objects/{key}?scope={scope}")
                assert st == 404, (key, scope, st)
            assert _call("GET", f"{a.url}/v1/objects/testsub/heartbeats/w-1?scope={scope}")[0] == 200
    finally:
        _stop(s)


def test_a_copy_that_cannot_be_read_or_kept_is_a_503_in_words_with_no_path():
    """The review's thirteenth pass, minors, and the product's cross-check (c): an object file this server holds and
    cannot read (mode 000) dropped the connection; a blob copy this server could not keep (no space) was 408 "the body
    did not arrive in time", the file's absolute path in it. Each is 503 now, the error's own words, no path of this
    server's disk — on either scope; a copy another server gives is still served."""
    import json as _json

    box = Box()
    s = _servers(box)
    try:
        (a, oa, _), (b, ob, _) = s["srv-a"], s["srv-b"]
        oa.put("testsub/heartbeats/w-1", b'{"w": 1}')
        path = os.path.join(oa.root, "testsub", "heartbeats", "w-1")
        os.chmod(path, 0)
        try:
            if os.access(path, os.R_OK):
                return                                    # run as root: nothing is unreadable to it
            for scope in ("local", "cluster"):
                st, body, _ = _call("GET", f"{a.url}/v1/objects/testsub/heartbeats/w-1?scope={scope}")
                assert st == 503 and b"cannot be read" in body and box.root.encode() not in body, (scope, st, body)
            ob.put("testsub/heartbeats/w-1", b'{"w": 2}')        # another server has a copy: the cluster answers with it
            st, body, _ = _call("GET", f"{a.url}/v1/objects/testsub/heartbeats/w-1?scope=cluster")
            assert st == 200 and body == b'{"w": 2}', (st, body)
        finally:
            os.chmod(path, 0o644)
        data = b"a mask"
        key = f"testsub/blobs/{digest(data)}"
        from w2cplatform import events
        real_new_temp = events.new_temp

        def full(d, prefix):
            raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC), os.path.join(d, prefix + "tmp"))
        events.new_temp = full
        try:
            st, body, _ = _call("PUT", f"{a.url}/v1/objects/{key}", data)
        finally:
            events.new_temp = real_new_temp
        assert st == 503 and os.strerror(errno.ENOSPC).encode() in body and box.root.encode() not in body, (st, body)
        assert _json.loads(body)["error"].startswith("this server could not keep the copy"), body
    finally:
        _stop(s)


def test_a_write_the_store_refuses_says_why_without_the_disks_layout():
    """The product's cross-check (c), at the console: a 503 or a 500 of a write said `str(e)` — "[Errno 13] Permission
    denied: '/data/platform/vars/…'", the layout of the server's disk for anybody who can make a write fail. The reply
    says the error's words; the path stays in the log."""
    from w2cplatform.console import no_paths
    assert no_paths(OSError(13, "Permission denied", "/data/platform/vars/testsub/counters/7")) == "Permission denied"
    assert no_paths(RuntimeError("could not open /data/platform/vars/testsub/counters/7: no")) == "could not open <path>: no"
    assert no_paths(ValueError("not a key: 'testsub2/tallies/..'")) == "not a key: 'testsub2/tallies/..'"
    assert no_paths(ValueError("http://srv-1:8090/v1/objects did not answer")) == "http://srv-1:8090/v1/objects did not answer"
