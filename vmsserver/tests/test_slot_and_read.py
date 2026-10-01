"""Two small things from the product's box (feedback BU).

    a new slot is named after its kind   a recorder that had to make a slot was `w-3` in every list and log
    `archive.read` says what LEFT        and the sha256 of a piece that left whole — "is this the file you gave out"
"""
import hashlib
import json
import os
import urllib.request

from w2cplatform.events import buckets_under
from vms.config import SPEC
from vms.console import serve
from vms.controller import VmsController
from vms.worker import FakeActuator, VmsWorker
from tests.conftest import Box, door, footage, recorder, store


def test_a_slot_a_worker_has_to_make_is_named_after_its_kind():
    from vms.autoworker import AutoWorker
    from vms.liveworker import LiveWorker
    box = Box()
    rec = recorder(box, None, "srv-a", acl=False)
    cam = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-a", env={})
    live = LiveWorker(None, box.vars, box.objects, clock=box.clock, wall=box.wall, server="srv-a", env={})
    auto = AutoWorker(None, box.vars, box.objects, clock=box.clock, wall=box.wall, server="srv-a", env={})
    assert (rec.name, cam.name, live.name, auto.name) == ("r-1", "w-1", "g-1", "a-1")
    again = recorder(box, None, "srv-a", acl=False)
    assert again.name == "r-2"
    box.wall.advance(46)                                              # r-1 lapsed: taken before a new number is made
    third = recorder(box, None, "srv-a", acl=False)
    assert third.name in ("r-1", "r-2")


def test_archive_read_says_what_left_and_the_digest_of_what_left():
    """An export is an interval turned into an MP4 (`/export/<cam>`), and the line `archive.read` is written
    AFTER it left, with the sha256 of the bytes — what whoever holds the file compares against. The same
    person asking for the same interval within a minute is one line; another person is another, with the same
    digest: the same frames make the same file."""
    box = Box()
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    st = store()
    t = box.wall()
    footage(st, "7", 3, t - 3600, t - 3000)
    dsrv = door(box, st)
    srv = serve(ctl, box.archive, port=0, wall=box.wall)
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def get(user="anna"):
        req = urllib.request.Request(f"{base}/export/7?from={t - 3600}&to={t - 3300}", headers={"X-User": user})
        with urllib.request.urlopen(req) as r:
            return r.status, r.headers.get("Content-Type"), r.read()

    def said(n=None):
        import time
        for _ in range(100):
            got = _said()
            if n is None or len(got) >= n:
                return got
            time.sleep(0.02)
        return got

    def _said():
        return [(e["user"], e["status"], e["bytes"], e.get("sha256"))
                for b in buckets_under(box.archive, "audit", "console", 600)
                for e in map(json.loads, open(os.path.join(box.archive, b.path))) if e["kind"] == "archive.read"]

    try:
        code, ctype, body = get()
        assert code == 200 and ctype == "video/mp4" and body[4:8] == b"ftyp"
        assert get()[2] == body                                        # the same frames: the same file
        digest = hashlib.sha256(body).hexdigest()
        assert said(1) == [("anna", 200, len(body), digest)]           # one line a minute, per person and piece
        box.wall.advance(61); dsrv.announce()
        assert get(user="boris")[2] == body
        assert said(2)[-1] == ("boris", 200, len(body), digest)         # whoever holds the file takes its digest and compares
    finally:
        srv.shutdown(); dsrv.shutdown()
