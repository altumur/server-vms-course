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


def test_an_export_takes_each_moment_from_the_epoch_that_owns_it_whichever_door_holds_it():
    """A fenced writer's stream and the survivor's may be in two volumes. Each door applies the rule to its own
    volume only, so the console asks every door's timeline, runs `authoritative` over all of them, and reads each
    stretch from the door of its owner — not from whichever door happens to sort first."""
    import urllib.request
    from vms.console import serve
    from vms.controller import VmsController
    from vms.worker import fake_samples
    from vms.config import SPEC
    from tests.conftest import door, footage, store
    box = Box()
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    t = box.wall() - 3600
    old, new = store("a"), store("b")
    footage(old, "7", 1, t, t + 600, step=10)                          # the zombie's e1, in volume a
    for smp in fake_samples(t + 300, t + 600, step=10, size=4096):    # the survivor's e2, in volume b — bigger frames
        new.put("7", 2, smp)
    new.finish("7", 2); new.seal()
    srv = serve(ctl, box.archive, port=0, wall=box.wall)
    url = f"http://127.0.0.1:{srv.server_address[1]}/export/7?rec=7&from={t}&to={t + 600}"
    da = door(box, old, "r-a", "srv-a")
    try:
        only_old = len(urllib.request.urlopen(url).read())
        db = door(box, new, "r-b", "srv-b")
        try:
            both = urllib.request.urlopen(url)
            assert both.headers.get("X-Archive-Unreachable") is None
            assert len(both.read()) > only_old + 25 * 3000              # minutes 5–10 from e2, though r-a sorts first
        finally:
            db.shutdown()
    finally:
        da.shutdown(); srv.shutdown()


def test_an_export_is_read_a_minute_at_a_time_and_written_as_it_is_made():
    """The review's third pass, major: an export decoded every door's whole answer into one list and made the MP4 of
    all of it — an hour of a camera, twice, in the console's memory. It reads each stretch in pieces of
    `EXPORT_PIECE`, cut at a key frame, and writes fragments as they come: the same file, byte for byte, as the one
    made in one piece, its sha256 in the journal; asked of the door ten times instead of once."""
    from vms import console as vc
    box = Box()
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    t = box.wall() - 3600
    st = store("a")
    footage(st, "7", 1, t, t + 600, step=1)
    srv = serve(ctl, box.archive, port=0, wall=box.wall)
    da = door(box, st, "r-a", "srv-a")
    asked = []
    real = vc._door
    vc._door = lambda url, timeout: (asked.append(url), real(url, timeout))[1]
    url = f"http://127.0.0.1:{srv.server_address[1]}/export/7?rec=7&from={t}&to={t + 600}"
    try:
        piece = vc.EXPORT_PIECE
        vc.EXPORT_PIECE = 1e9
        try:
            whole = urllib.request.urlopen(url).read()
        finally:
            vc.EXPORT_PIECE = piece
        assert sum("/samples/" in u for u in asked) == 1
        asked.clear()
        r = urllib.request.urlopen(url)
        streamed = r.read()
        assert r.headers.get("Content-Length") is None and r.headers["Content-Type"] == "video/mp4"   # written as it is made
        assert streamed == whole and len(streamed) > 600 * 200                                       # the same file
        assert sum("/samples/" in u for u in asked) >= 10                                            # a minute at a time
        digests = [json.loads(line).get("sha256") for b in buckets_under(box.archive, "audit", "console", 600)
                   for line in open(os.path.join(box.archive, b.path)) if json.loads(line)["kind"] == "archive.read"]
        assert hashlib.sha256(streamed).hexdigest() in digests
    finally:
        vc._door = real; da.shutdown(); srv.shutdown()


def test_exports_held_in_memory_at_once_are_bounded_and_the_next_one_is_told_when_to_come_back():
    """The review's third pass, major: an export holds its interval in memory, an hour of a camera is gigabytes, and
    nothing bounded how many ran at once — two or three from anybody with `view` took the console down. Past
    `EXPORTS_AT_ONCE` the next is 503 with `Retry-After`; when one finishes, the next is served."""
    import threading
    from w2cplatform.contract import Heartbeat
    from vms import console as vc
    from vms.config import REC_SPEC
    box = Box()
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-1"),
                    Heartbeat("r-1", box.wall(), [], {"archive_url": "http://door.invalid", "volume": "a"}).to_bytes())
    held, entered = threading.Event(), threading.Semaphore(0)

    def slow_door(url, timeout):                                     # a door that takes its time: the export stays in flight
        entered.release(); held.wait(10)
        raise OSError("not answering")
    door_, vc._door = vc._door, slow_door
    route = vc.vms_routes(True, None, ctl, None)
    t = box.wall()
    out = []
    try:
        busy = [threading.Thread(target=lambda: out.append(route(None, "GET", "/export/7", {"from": t - 60, "to": t})[0]))
                for _ in range(vc.EXPORTS_AT_ONCE)]
        [b.start() for b in busy]
        for _ in busy:
            assert entered.acquire(timeout=5)                         # both in flight
        status, body, headers = route(None, "GET", "/export/7", {"from": t - 60, "to": t})
        assert status == 503 and json.loads(body)["error"] == "busy" and ("Retry-After", "5") in headers
        held.set(); [b.join(5) for b in busy]
        assert out == [404] * vc.EXPORTS_AT_ONCE                     # nothing recorded there: the door did not answer
        assert route(None, "GET", "/export/7", {"from": t - 60, "to": t})[0] == 404   # a place again
    finally:
        vc._door = door_; held.set()
