"""Two small things from the product's box (feedback BU).

    a new slot is named after its kind   a recorder that had to make a slot was `w-3` in every list and log
    `archive.read` says what LEFT        and the sha256 of a piece that left whole — "is this the file you gave out"
"""
import hashlib
import json
import os
import urllib.request
from datetime import datetime, timezone

from w2cplatform.events import buckets_under
from vms.archive import ArchiveResource, segment_path
from vms.config import SPEC
from vms.console import serve
from vms.controller import VmsController
from vms.recworker import RecWorker
from vms.worker import FakeActuator, VmsWorker
from tests.conftest import Box


def test_a_slot_a_worker_has_to_make_is_named_after_its_kind():
    from vms.autoworker import AutoWorker
    from vms.liveworker import LiveWorker
    box = Box()
    rec = RecWorker(None, box.vars, box.objects, archive=ArchiveResource(box.spool, box.archive, wall=box.wall),
                    clock=box.clock, wall=box.wall, server="srv-a", env={})
    cam = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-a", env={})
    live = LiveWorker(None, box.vars, box.objects, clock=box.clock, wall=box.wall, server="srv-a", env={})
    auto = AutoWorker(None, box.vars, box.objects, clock=box.clock, wall=box.wall, server="srv-a", env={})
    assert (rec.name, cam.name, live.name, auto.name) == ("r-1", "w-1", "g-1", "a-1")
    again = RecWorker(None, box.vars, box.objects, archive=ArchiveResource(box.spool, box.archive, wall=box.wall),
                      clock=box.clock, wall=box.wall, server="srv-a", env={})
    assert again.name == "r-2"
    box.wall.advance(46)                                              # r-1 lapsed: taken before a new number is made
    third = RecWorker(None, box.vars, box.objects, archive=ArchiveResource(box.spool, box.archive, wall=box.wall),
                      clock=box.clock, wall=box.wall, server="srv-a", env={})
    assert third.name in ("r-1", "r-2")


def test_archive_read_says_what_left_and_the_digest_of_a_whole_piece():
    box = Box()
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    arch = ArchiveResource(box.spool, box.archive, wall=box.wall)
    p = segment_path(box.archive, "7", 3, datetime.fromtimestamp(box.wall() - 3600, timezone.utc))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    body = os.urandom(4000); open(p, "wb").write(body)
    rel = os.path.relpath(p, box.archive)
    srv = serve(ctl, arch, port=0, wall=box.wall)
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def get(rng=None, user="anna"):
        req = urllib.request.Request(f"{base}/segment/{rel}", headers={"X-User": user, **({"Range": rng} if rng else {})})
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()

    def said():
        return [(e["user"], e["status"], e["bytes"], e.get("sha256"))
                for b in buckets_under(box.archive, "audit", "console", 600)
                for e in map(json.loads, open(os.path.join(box.archive, b.path))) if e["kind"] == "archive.read"]

    try:
        assert get("bytes=1000-1999")[0] == 206                      # a player seeking: a part
        assert get()[1] == body                                        # a download, right after: a WHOLE, not swallowed by the part
        assert get("bytes=0-")[0] == 206                               # from the first byte to the last is whole too, and said once a minute
        digest = hashlib.sha256(body).hexdigest()
        assert said() == [("anna", 206, 1000, None), ("anna", 200, 4000, digest)]
        box.wall.advance(61)
        assert get("bytes=0-", user="boris")[0] == 206
        assert said()[-1] == ("boris", 206, 4000, digest)             # whoever holds the file takes its digest and compares
    finally:
        srv.shutdown()
