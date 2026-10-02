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
        assert said(2) == [("anna", 200, len(body), digest)] * 2       # every whole file that left (the review's fourth pass)
        box.wall.advance(61); dsrv.announce()
        assert get(user="boris")[2] == body
        assert said(3)[-1] == ("boris", 200, len(body), digest)         # whoever holds the file takes its digest and compares
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
    class As:                                                        # a caller, by name: one person makes one export at a time
        def __init__(self, who): self.headers = {"X-User": who}
    try:
        busy = [threading.Thread(target=lambda i=i: out.append(route(As(f"u{i}"), "GET", "/export/7", {"from": t - 60, "to": t})[0]))
                for i in range(vc.EXPORTS_AT_ONCE)]
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


def _export_box(size=256):
    """A console that fronts `rec`, with recordings `7` and `7-cloud` of camera 7, both on one door."""
    from w2cplatform.spec import SpecController
    from vms.config import REC_SPEC
    from vms.worker import fake_samples
    box = Box()
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    rec.create({"name": "7", "cam": "7"}); rec.create({"name": "7-cloud", "cam": "7"})
    t = box.wall() - 3600
    st = store("a")
    for unit, (a, b) in (("7", (t, t + 300)), ("7-cloud", (t + 300, t + 600))):
        for smp in fake_samples(a, b, step=1, size=size):
            st.put(unit, 1, smp)
        st.finish(unit, 1)
    st.seal()
    return box, ctl, rec, st, t


def _journal(box):
    return [json.loads(line) for b in buckets_under(box.archive, "audit", "console", 600)
            for line in open(os.path.join(box.archive, b.path))]


def test_an_export_of_a_camera_with_two_recordings_and_no_rec_is_both_of_them():
    """The review's fourth pass, major: `GET /export/7` with recordings `7` and `7-cloud` and no `rec` broke the
    connection — the merge ran a generator that looked every recording's stretches up in the LAST recording's map
    (`KeyError`), and there was no reply and no line. Each recording's stream binds its own name and map now: the
    file is both recordings' minutes, merged by time, and the journal names both."""
    box, ctl, rec, st, t = _export_box()
    srv = serve(ctl, box.archive, port=0, wall=box.wall, mounts={"rec": rec})
    da = door(box, st, "r-a", "srv-a")
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        whole = urllib.request.urlopen(f"{base}/export/7?from={t}&to={t + 600}").read()
        first = urllib.request.urlopen(f"{base}/export/7?rec=7&from={t}&to={t + 600}").read()
        second = urllib.request.urlopen(f"{base}/export/7?rec=7-cloud&from={t}&to={t + 600}").read()
        assert whole[4:8] == b"ftyp" and len(whole) > max(len(first), len(second)) + 250 * 200   # both halves
        assert f"rec/7,7-cloud/{t:.0f}-{t + 600:.0f}" in [e.get("media") for e in _journal(box) if e["kind"] == "archive.read"]
    finally:
        da.shutdown(); srv.shutdown()


def test_a_client_that_reads_nothing_lets_its_export_go_and_one_person_holds_one_slot():
    """The review's fourth pass, major: two sockets that asked for an export and read nothing held both slots until
    the console restarted, and every other export was 503. The console's sockets have a timeout (`CONSOLE_TIMEOUT`):
    a client that reads nothing for that long is let go, and its slot with it. One person makes one export at a time
    (`EXPORTS_PER_USER`), and an export longer than `EXPORT_BUDGET` is cut off there, and says so in the journal.
    The timeout covers the request's own line and headers too: half a request line is let go the same way."""
    import socket
    import time
    import urllib.error
    box, ctl, rec, st, t = _export_box(size=32768)                   # some 20 MB: more than any socket's buffers hold
    was = {k: os.environ.get(k) for k in ("CONSOLE_TIMEOUT", "EXPORT_BUDGET")}
    os.environ["CONSOLE_TIMEOUT"] = "1"
    srv = serve(ctl, box.archive, port=0, wall=box.wall, mounts={"rec": rec})
    da = door(box, st, "r-a", "srv-a")
    port = srv.server_address[1]

    def silent(who):                                                 # asks, and never reads a byte of the answer
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        s.connect(("127.0.0.1", port))
        s.sendall(f"GET /export/7?from={t}&to={t + 600} HTTP/1.1\r\nHost: x\r\nX-User: {who}\r\n\r\n".encode())
        return s

    def export(who):
        req = urllib.request.Request(f"http://127.0.0.1:{port}/export/7?rec=7&from={t}&to={t + 60}", headers={"X-User": who})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
    held = []
    try:
        held = [silent("anna"), silent("boris")]
        time.sleep(0.3)                                              # both in flight, their buffers full
        assert export("carol")[0] == 503                             # every slot held by somebody who does not read
        half = socket.create_connection(("127.0.0.1", port))
        half.sendall(b"GET /cam")                                    # and half a request line
        for _ in range(100):                                         # …until the socket's timeout lets them go
            code, body = export("carol")
            if code == 200:
                break
            time.sleep(0.1)
        assert code == 200 and body[4:8] == b"ftyp"
        half.settimeout(5)
        assert half.recv(100) == b""                                 # closed by the console, not waited on for ever
        cut = {e["user"] for e in _journal(box) if e["kind"] == "archive.read" and "sha256" not in e}
        assert cut >= {"anna", "boris"}                              # cut off: no digest of a file that did not leave whole

        held = [silent("dave")]                                      # one person, one export at a time
        time.sleep(0.3)
        code, body = export("dave")
        assert code == 503 and b"dave is making 1 export" in body
        for s in held:
            s.close()
        held = []
        time.sleep(1.5)
        os.environ["EXPORT_BUDGET"] = "0"                            # …and an export past its budget stops there
        code, body = export("erin")
        assert code == 200 and len(body) < 10000
        mine = [e for e in _journal(box) if e.get("user") == "erin"]
        assert mine and "sha256" not in mine[-1] and "budget" in mine[-1].get("broken", "")
    finally:
        for s in held:
            s.close()
        for k, v in was.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        da.shutdown(); srv.shutdown()
