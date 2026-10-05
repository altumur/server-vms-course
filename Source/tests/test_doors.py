"""The doors: what a request may name, and how much it may ask for (`w2cplatform/doors.py`).

Every route that turns a URL or a header into a place on a disk goes through one check, and every file sent
by `Range` is cut to the file. Found by the platform review of 29 September and by the product on its own doors
(feedback BC, BD): an absolute path after `/segment/` read any file of the box; `/buckets` and `/mirrored` had
no check at all; a `Range` of a hundred gigabytes was one allocation.
"""
import os
import urllib.error
import urllib.request

from w2cplatform.doors import byte_range, safe_rel, safe_segment
from w2cplatform.resource import serve as serve_resource
from vms.console import serve
from vms.controller import VmsController
from vms.config import SPEC
from w2cplatform.resource import platform_resource
from tests.conftest import Box, door, footage, store


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
    res = platform_resource(box.archive, "srv-1", "", box.vars, box.objects, wall=box.wall)
    srv = serve_resource(res, "127.0.0.1", 0)
    return f"http://127.0.0.1:{srv.server_address[1]}", srv


def test_a_name_is_one_segment_and_a_path_is_relative():
    assert safe_segment("7") and safe_segment("7-backup") and safe_segment("srv-1")
    for bad in ("", ".", "..", "a/b", "a\\b", "a\0b"):
        assert not safe_segment(bad), bad
    assert safe_rel("vms/7/e1/x.events.jsonl")
    for bad in ("", "/etc/hosts", "vms/../x", "../x", "vms//x", "vms/./x", "vms/7/"):
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
    """The file a door must never give: the box's own configuration, outside the resource's root."""
    box = Box()
    url, srv = _resource(box)
    try:
        secret = os.path.join(box.root, "secret.events.jsonl")
        with open(secret, "w") as f:
            f.write('{"t": 1, "kind": "cred"}\n')
        assert _get(f"{url}/events/{secret}")[0] == 404
        assert _get(f"{url}/events/vms/7/../../../secret.events.jsonl")[0] == 404
        assert _get(f"{url}/mirrored/../..")[0] == 404                 # no check at all, before
        assert _get(f"{url}/buckets/vms/../..")[0] == 404
        assert _get(f"{url}/buckets/vms")[0] == 404                    # and a short path is a 404, not a crash
        assert _get(f"{url}/segment/{secret}")[0] == 404               # and footage is not a resource's any more
        assert _put(f"{url}/mirror/../x.events.jsonl", b"{}", {}) == 400
        assert _put(f"{url}/mirror/srv-2/../../x.events.jsonl", b"{}", {}) == 400
    finally:
        srv.shutdown()


def test_a_recorders_archive_door_names_a_recording_and_nothing_else():
    """`/timeline/<unit>` and `/samples/<unit>` take ONE name — a recording's — and the volume is asked about it;
    nothing in the path reaches a disk."""
    box = Box()
    st = store()
    footage(st, "7", 1, box.wall() - 60, box.wall())
    d = door(box, st)
    try:
        assert _get(f"{d.url}/timeline/7")[0] == 200
        assert _get(f"{d.url}/timeline/..")[0] == 404
        assert _get(f"{d.url}/samples/a/b")[0] == 404
        assert _get(f"{d.url}/samples/7?from=x")[0] == 400
        assert _get(f"{d.url}/manifest/7")[0] == 404
    finally:
        d.shutdown()


def test_the_consoles_export_asks_for_an_interval_and_never_a_path():
    box = Box()
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    srv = serve(ctl, box.archive, "127.0.0.1", 0)
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        secret = os.path.join(box.root, "secret.txt")
        with open(secret, "w") as f:
            f.write("cred")
        assert _get(f"{url}/segment/{secret}")[0] == 404              # no file is served by path any more
        assert _get(f"{url}/export/7?from=100&to=50")[0] == 400       # an interval, ends in order
        assert _get(f"{url}/export/7?from=0&to=99999999")[0] == 400   # and of a bounded length: an hour
        assert _get(f"{url}/export/7?from=100&to=160")[0] == 404      # nothing recorded there: said, not an empty file
    finally:
        srv.shutdown()
