"""The doors: what a request may name, and how much it may ask for (`w2cplatform/doors.py`).

Every route that turns a URL or a header into a place on a disk goes through one check, and every file sent
by `Range` is cut to the file. Found by the platform review of 29 September and by the product on its own doors
(feedback BC, BD): an absolute path after `/segment/` read any file of the box; `/buckets` and `/mirrored` had
no check at all; a `Range` of a hundred gigabytes was one allocation.
"""
import json
import os
import urllib.error
import urllib.request

from w2cplatform.doors import byte_range, safe_rel, safe_segment
from w2cplatform.resource import serve as serve_resource
from vms.archive import SUB, ArchiveResource, Segment
from vms.console import serve
from vms.controller import VmsController
from vms.config import SPEC
from vms.resource import vms_resource, vms_routes, vms_writes
from tests.conftest import Box


def _get(url, headers=None):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=5) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def _put(url, body, headers):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method="PUT"), timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def _resource(box):
    archive = ArchiveResource(box.spool, box.archive, wall=box.wall)
    res = vms_resource(archive, "srv-1", "", box.vars, box.objects, wall=box.wall)
    srv = serve_resource(res, "127.0.0.1", 0, extra=vms_routes(archive), extra_put=vms_writes(archive))
    return archive, f"http://127.0.0.1:{srv.server_address[1]}", srv


def _segment(box, body=b"x" * 122):
    rel = f"{SUB}/7/e1/20260929T100000Z.mp4"
    p = os.path.join(box.archive, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(body)
    return rel


def test_a_name_is_one_segment_and_a_path_is_relative():
    assert safe_segment("7") and safe_segment("7-backup") and safe_segment("srv-1")
    for bad in ("", ".", "..", "a/b", "a\\b", "a\0b"):
        assert not safe_segment(bad), bad
    assert safe_rel("rec/7/e1/x.mp4")
    for bad in ("", "/etc/hosts", "rec/../x", "../x", "rec//x", "rec/./x", "rec/7/"):
        assert not safe_rel(bad), bad


def test_a_range_is_cut_to_the_file_and_never_the_clients_number():
    assert byte_range(None, 122) == (0, 121) and byte_range("bytes=0-", 122) == (0, 121)
    assert byte_range("bytes=0-99999999999", 122) == (0, 121)          # a hundred gigabytes asked: the file sent
    assert byte_range("bytes=10-19", 122) == (10, 19)
    assert byte_range("bytes=-10", 122) == (112, 121)                  # the LAST ten — it used to read as 0-10
    assert byte_range("bytes=50-40", 122) is None                      # a negative length was "read everything"
    assert byte_range("bytes=500-", 122) is None and byte_range("bytes=-0", 122) is None
    assert byte_range("pages=1-2", 122) == (0, 121)                    # not a byte range: the whole file


def test_the_resources_doors_name_nothing_outside_the_tree():
    """The file a door must never give: the box's own configuration, outside the archive's root."""
    box = Box()
    archive, url, srv = _resource(box)
    try:
        rel = _segment(box)
        secret = os.path.join(box.root, "secret.events.jsonl")
        with open(secret, "w") as f:
            f.write('{"t": 1, "kind": "cred"}\n')
        assert _get(f"{url}/segment/{rel}")[0] == 200
        assert _get(f"{url}/segment/{secret}")[0] == 404               # /segment//abs/path: absolute — it used to be read
        assert _get(f"{url}/segment/{SUB}/7/../../../secret.events.jsonl")[0] == 404
        assert _get(f"{url}/events/{secret}")[0] == 404
        assert _get(f"{url}/mirrored/../..")[0] == 404                 # no check at all, before
        assert _get(f"{url}/buckets/vms/../..")[0] == 404
        assert _get(f"{url}/buckets/vms")[0] == 404                    # and a short path is a 404, not a crash
        assert _get(f"{url}/manifest/..")[0] == 404
    finally:
        srv.shutdown()


def test_a_range_of_a_hundred_gigabytes_gets_the_file_and_an_impossible_one_gets_416():
    box = Box()
    archive, url, srv = _resource(box)
    try:
        rel = _segment(box, bytes(range(122)))
        status, body, headers = _get(f"{url}/segment/{rel}", {"Range": "bytes=0-99999999999"})
        assert status == 206 and len(body) == 122 and headers["Content-Range"] == "bytes 0-121/122"
        status, body, _ = _get(f"{url}/segment/{rel}", {"Range": "bytes=-10"})
        assert status == 206 and body == bytes(range(112, 122))
        status, _, headers = _get(f"{url}/segment/{rel}", {"Range": "bytes=50-40"})
        assert status == 416 and headers["Content-Range"] == "bytes */122"
    finally:
        srv.shutdown()


def test_a_segment_put_names_its_manifest_by_a_unit_not_by_a_path():
    """The line in `X-Segment` names the unit whose manifest it is appended to. `{"unit": "../../x"}` made
    directories and appended a manifest wherever it pointed."""
    box = Box()
    archive, url, srv = _resource(box)
    try:
        rel = f"{SUB}/7/e1/20260929T100500Z.mp4"
        good = Segment("7", 1, 100.0, 110.0, rel, 3)
        assert _put(f"{url}/segment/{rel}", b"abc", {"X-Segment": good.line()}) == 204
        bad = json.dumps({**json.loads(good.line()), "unit": "../../x"})
        assert _put(f"{url}/segment/{rel}", b"abc", {"X-Segment": bad}) == 400
        assert not os.path.exists(os.path.join(box.root, "x"))
        assert _put(f"{url}/segment//{rel}", b"abc", {"X-Segment": good.line()}) == 400
        assert _put(f"{url}/mirror/../x.events.jsonl", b"{}", {}) == 400
        assert _put(f"{url}/mirror/srv-2/../../x.events.jsonl", b"{}", {}) == 400
    finally:
        srv.shutdown()


def test_the_consoles_segment_door_is_the_same_door():
    box = Box()
    rel = _segment(box, bytes(range(122)))
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    srv = serve(ctl, ArchiveResource(box.spool, box.archive, wall=box.wall), "127.0.0.1", 0)
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        secret = os.path.join(box.root, "secret.txt")
        with open(secret, "w") as f:
            f.write("cred")
        assert _get(f"{url}/segment/{rel}")[0] == 200
        assert _get(f"{url}/segment/{secret}")[0] == 404
        status, body, _ = _get(f"{url}/segment/{rel}", {"Range": "bytes=0-99999999999"})
        assert status == 206 and len(body) == 122
        assert _get(f"{url}/segment/{rel}", {"Range": "bytes=50-40"})[0] == 416
    finally:
        srv.shutdown()
