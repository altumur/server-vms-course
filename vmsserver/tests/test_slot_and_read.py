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
    vc._door = lambda url, timeout, *limit: (asked.append(url), real(url, timeout, *limit))[1]
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

    def slow_door(url, timeout, *limit):                                     # a door that takes its time: the export stays in flight
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


def test_an_honest_slow_client_gets_the_whole_export_and_a_cut_one_is_seen_as_cut():
    """The review's fifth pass, major: an export was cut at a budget of 900 s of the clock, and went out as `200` with
    a file that simply ended — an hour of an 8 Mbit/s camera over a 10 Mbit/s VPN was always nineteen minutes, and
    nothing said so. The bound is the client's pace now (`EXPORT_MIN_RATE`, after `EXPORT_GRACE`): a client reading
    slowly but above it gets the file whole, however long that takes, ending with the last chunk; one below it is cut,
    and the reply ends WITHOUT the last chunk — what curl, a browser and `http.client` read as an error — and the
    journal says `broken` with no digest."""
    import socket
    import time
    box, ctl, rec, st, t = _export_box(size=8192)                    # some 2.5 MB for recording 7's five minutes
    was = {k: os.environ.get(k) for k in ("EXPORT_GRACE", "EXPORT_MIN_RATE")}
    os.environ["EXPORT_GRACE"], os.environ["EXPORT_MIN_RATE"] = "0.3", "500000"
    srv = serve(ctl, box.archive, port=0, wall=box.wall, mounts={"rec": rec})
    da = door(box, st, "r-a", "srv-a")
    port = srv.server_address[1]

    def fetch(who: str, rate: float):                                 # reads no faster than `rate` bytes a second
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8192)
        s.connect(("127.0.0.1", port))
        s.sendall(f"GET /export/7?rec=7&from={t}&to={t + 300} HTTP/1.1\r\nHost: x\r\nX-User: {who}\r\n\r\n".encode())
        data, began = b"", time.monotonic()
        s.settimeout(10)
        while True:
            got = s.recv(8192)
            if not got:
                break
            data += got
            ahead = len(data) / rate - (time.monotonic() - began)
            if ahead > 0:
                time.sleep(ahead)
        s.close()
        return data, time.monotonic() - began
    try:
        whole, took = fetch("fiona", 2_000_000)
        assert b"Transfer-Encoding: chunked" in whole and whole.endswith(b"\r\n0\r\n\r\n") and len(whole) > 2_000_000
        assert took > 1.0                                             # slow, and whole: no clock cut it
        assert [e.get("sha256") for e in _journal(box) if e.get("user") == "fiona"][-1]
        cut, _ = fetch("gleb", 100_000)
        assert b" 200 " in cut.split(b"\r\n", 1)[0] and not cut.endswith(b"0\r\n\r\n") and len(cut) < len(whole)
        mine = [e for e in _journal(box) if e.get("user") == "gleb"]
        assert mine and "sha256" not in mine[-1] and "EXPORT_MIN_RATE" in mine[-1].get("broken", "")
    finally:
        for k, v in was.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        da.shutdown(); srv.shutdown()


def test_every_download_cut_off_after_real_footage_is_a_line_of_its_own():
    """The review's fifth pass, Ч-m5's remainder: a whole export was always a line, and a broken one was folded into
    the minute's — two downloads of an interval, each cut after 3.6 MB, were one line. A part is folded only while it
    is a player's scrub, under `READ_NOTE_BYTES`; two cut downloads past it are two lines, each with its bytes."""
    import socket
    import time
    from vms import console as vc
    box, ctl, rec, st, t = _export_box(size=32768)                   # some 10 MB for recording 7's five minutes
    srv = serve(ctl, box.archive, port=0, wall=box.wall, mounts={"rec": rec})
    da = door(box, st, "r-a", "srv-a")
    port = srv.server_address[1]

    # The cut download's line is in the journal BEFORE its slots are given back — its barrier (`durably`) runs between —
    # so a player that asks again the moment it sees the line can meet its own slot still held, and is answered 503
    # "retry" (`EXPORTS_PER_USER`). Under the whole suite's disk load the barrier is slow enough for it: this helper read
    # the 503 as if it were the file, and spun on the closed socket. A player retries; so does this one, and a download
    # that ends before `n` bytes for any other reason fails here, never spins.
    def cut_after(n: int) -> None:
        for _ in range(200):
            s = socket.create_connection(("127.0.0.1", port))
            s.sendall(f"GET /export/7?rec=7&from={t}&to={t + 300} HTTP/1.1\r\nHost: x\r\nX-User: hana\r\n\r\n".encode())
            got, head = 0, b""
            while got < n:
                b = s.recv(65536)
                if not b or (not head and b.split(b"\r\n", 1)[0].endswith(b" 503 Service Unavailable")):
                    head = head or b
                    break
                head, got = head or b, got + len(b)
            s.close()                                                 # the player went away
            if got >= n:
                return
            assert b" 503 " in head.split(b"\r\n", 1)[0], (got, head[:80])   # ended early, and not for a busy slot
            time.sleep(0.05)
        raise AssertionError("the slot of the download before never came free")
    def lines(n: int) -> list:
        for _ in range(200):
            mine = [e for e in _journal(box) if e.get("user") == "hana"]
            if len(mine) >= n:
                break
            time.sleep(0.05)
        return mine
    try:
        cut_after(3 * vc.READ_NOTE_BYTES)
        assert len(lines(1)) == 1                                     # the first is over, its slot free again
        cut_after(3 * vc.READ_NOTE_BYTES)                             # the same interval, inside the same minute
        mine = lines(2)
        assert len(mine) == 2 and all("broken" in e and e["bytes"] >= vc.READ_NOTE_BYTES for e in mine)
    finally:
        da.shutdown(); srv.shutdown()


def test_a_client_that_reads_nothing_lets_its_export_go_and_one_person_holds_one_slot():
    """The review's fourth pass, major: two sockets that asked for an export and read nothing held both slots until
    the console restarted, and every other export was 503. The console's sockets have a timeout (`CONSOLE_TIMEOUT`):
    a client that reads nothing for that long is let go, and its slot with it. One person makes one export at a time
    (`EXPORTS_PER_USER`), and a client slower than `EXPORT_MIN_RATE` is cut off — the client sees the cut (no last
    chunk: `IncompleteRead`, the review's fifth pass) and the journal says so. The timeout covers the request's own
    line and headers too: half a request line is let go the same way."""
    import socket
    import time
    import urllib.error
    box, ctl, rec, st, t = _export_box(size=32768)                   # some 20 MB: more than any socket's buffers hold
    was = {k: os.environ.get(k) for k in ("CONSOLE_TIMEOUT", "EXPORT_GRACE", "EXPORT_MIN_RATE")}
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
        os.environ["EXPORT_GRACE"], os.environ["EXPORT_MIN_RATE"] = "0", "1e12"   # …and a client slower than the floor is cut
        import http.client
        req = urllib.request.Request(f"http://127.0.0.1:{port}/export/7?rec=7&from={t}&to={t + 60}", headers={"X-User": "erin"})
        with urllib.request.urlopen(req) as r:
            assert r.status == 200 and r.headers.get("Transfer-Encoding") == "chunked"
            try:
                r.read()
                raise AssertionError("a file cut short read as a whole one")
            except http.client.IncompleteRead as e:                  # the cut is SEEN: no last chunk (the fifth pass)
                assert len(e.partial) < 10000
        mine = [e for e in _journal(box) if e.get("user") == "erin"]
        assert mine and "sha256" not in mine[-1] and "EXPORT_MIN_RATE" in mine[-1].get("broken", "")
    finally:
        for s in held:
            s.close()
        for k, v in was.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        da.shutdown(); srv.shutdown()


def test_a_door_that_stops_answering_after_the_first_byte_breaks_the_export_and_the_journal_says_so():
    """The review's sixth pass, major — a run: an export of 9.85 MB whose recorder's door stopped after 1 MB was a `200`
    of 1.9 MB with a correct last chunk, and a sha256 in the journal as a whole file has. The door was named and its
    stretch ended — and the file went on to its end. A door that fails after the first byte is a BREAK now: the reply
    ends without its last chunk (`IncompleteRead` to the client), and the line is `broken`, names the door, and
    carries no digest."""
    import http.client
    import time
    from vms import console as vc
    box, ctl, rec, st, t = _export_box(size=8192)                    # five pieces of a minute for recording 7
    srv = serve(ctl, box.archive, port=0, wall=box.wall, mounts={"rec": rec})
    da = door(box, st, "r-a", "srv-a")
    real, asked = vc._door, []

    def gone_after_two(url, timeout, *limit):                                 # the timelines and two minutes of frames, then nothing
        if "/samples/" in url:
            asked.append(url)
            if len(asked) > 2:
                raise ConnectionRefusedError("the recorder's door is gone")
        return real(url, timeout, *limit)
    vc._door = gone_after_two
    try:
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=30)
        c.request("GET", f"/export/7?rec=7&from={t}&to={t + 300}", headers={"X-User": "ivan"})
        r = c.getresponse()
        assert r.status == 200 and r.getheader("Transfer-Encoding") == "chunked"
        try:
            r.read()
            raise AssertionError("an export its door walked away from read as a whole file")
        except http.client.IncompleteRead as e:
            assert 100_000 < len(e.partial) < 300 * 8192              # two minutes of five, and no last chunk
        for _ in range(100):
            mine = [e for e in _journal(box) if e.get("user") == "ivan"]
            if mine:
                break
            time.sleep(0.05)
        assert "sha256" not in mine[-1] and mine[-1]["unreachable"] == "r-a"
        assert "r-a" in mine[-1]["broken"] and "cut" in mine[-1]["broken"]
    finally:
        vc._door = real; da.shutdown(); srv.shutdown()


def test_a_recorders_door_cut_between_two_sequences_is_an_error_to_its_readers_never_a_shorter_range():
    """The same class one door down (the sixth pass: the export took a door that failed for a file that ended). A
    recorder's door streamed its frames with no framing but the connection's end, a SEQUENCE at a time: a volume that
    failed between two sequences left its reader whole records — a shorter range, taken for all the source holds, by
    the console's export and by a recorder copying from a backup alike. The door writes its last chunk only when the
    stream ended whole (`send_route`), and both readers take an answer without it for what it is."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from vms import console as vc
    from vms.recworker import RecWorker, send_route
    from vms.worker import fake_samples
    first = b"".join(s.encode() for s in fake_samples(1000.0, 1002.0))          # one whole sequence
    state = {"fail": True}

    def frames():
        yield first
        if state["fail"]:
            raise OSError("the volume went away")                     # between two sequences: every record so far is whole
        yield b"".join(s.encode() for s in fake_samples(1002.0, 1004.0))

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            send_route(self, (200, frames(), "application/octet-stream"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        for read in (lambda: RecWorker.read_samples(None, url, "7", 1000.0, 1004.0),      # a recorder copying from a backup
                     lambda: vc._door(f"{url}/samples/7?from=1000&to=1004", 5.0)):        # the console's export
            try:
                read()
                raise AssertionError("a stream cut between two sequences read as all there was")
            except OSError as e:
                assert "cut short" in str(e)
        state["fail"] = False
        assert len(RecWorker.read_samples(None, url, "7", 1000.0, 1004.0)) == 4            # whole: as before
    finally:
        srv.shutdown()


def test_an_answer_with_neither_chunks_nor_a_length_is_not_taken_for_a_whole_one():
    """The review's seventh pass, minor: `_door` took an answer that ended where its connection ended — no chunks, no
    `Content-Length` — as whole; such an answer cut half way (a door that spoke HTTP/1.0, a proxy that took the framing
    off) looked exactly like one that had nothing more. Both readers of a recorder's frames — the console's export and a
    recorder copying from a backup — refuse it; with a length, or in chunks, it is read as before. And a header is not
    a framing (the eighth pass, minor): `Content-Length: ten`, `-1`, `Transfer-Encoding: gzip, chunked` on an answer
    the connection's end cut were taken for whole — what is asked now is whether `http.client` reads a length or chunks
    out of them (`framed`)."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from vms import console as vc
    from vms.recworker import RecWorker
    from vms.worker import fake_samples
    frames = b"".join(s.encode() for s in fake_samples(1000.0, 1004.0))
    state = {"length": False, "header": None}

    class H(BaseHTTPRequestHandler):                                  # HTTP/1.0: the connection's end is the answer's end
        def log_message(self, *a):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            if state["length"]:
                self.send_header("Content-Length", str(len(frames)))
            if state["header"]:
                self.send_header(*state["header"])
            self.end_headers()
            self.wfile.write(frames[:len(frames) // 2] if state["header"] else frames)   # …and cut half way
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        for read in (lambda: vc._door(f"{url}/samples/7?from=1000&to=1004", 5.0),
                     lambda: RecWorker.read_samples(None, url, "7", 1000.0, 1004.0)):
            try:
                read()
                raise AssertionError("an answer with no framing read as whole")
            except OSError as e:
                assert "neither chunks nor a length" in str(e)
        for header in (("Content-Length", "ten"), ("Content-Length", "-1"), ("Transfer-Encoding", "gzip, chunked")):
            state["header"] = header
            for read in (lambda: vc._door(f"{url}/samples/7?from=1000&to=1004", 5.0),
                         lambda: RecWorker.read_samples(None, url, "7", 1000.0, 1004.0)):
                try:
                    read()
                    raise AssertionError(f"{header}: a cut answer read as whole")
                except OSError as e:
                    assert "neither chunks nor a length" in str(e), (header, e)
        state["header"] = None
        state["length"] = True
        assert vc._door(f"{url}/samples/7?from=1000&to=1004", 5.0) == frames
        assert len(RecWorker.read_samples(None, url, "7", 1000.0, 1004.0)) == 4
    finally:
        srv.shutdown()


def test_one_recordings_torn_epoch_row_does_not_take_the_cameras_timeline_away():
    """The review's sixth pass, minor: a `rec/epoch/<recording>` row that does not parse was a `ValueError` out of the
    timeline's handler — the page got no timeline of the camera at all, every other recording of it included. Read as
    `SpecConsole.epochs_of` reads it: that recording's spans stand as their door marked them, the others are fenced
    by their own rows."""
    box, ctl, rec, st, t = _export_box()
    srv = serve(ctl, box.archive, port=0, wall=box.wall, mounts={"rec": rec})
    da = door(box, st, "r-a", "srv-a")
    try:
        box.vars.put("rec/epoch/7", {"epoch": "not a number"})
        box.vars.put("rec/epoch/7-cloud", {"epoch": "2"})
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/timeline/7?from={t}&to={t + 600}") as r:
            spans = json.load(r)
        by = {s["recording"]: s for s in spans}
        assert set(by) == {"7", "7-cloud"}                            # both drawn
        assert by["7"]["fenced"] is False and by["7-cloud"]["fenced"] is True   # …the torn one by its door's word, the other by its row
    finally:
        da.shutdown(); srv.shutdown()


def test_a_span_a_door_answered_that_does_not_parse_costs_that_door_and_not_the_cameras_timeline_or_its_export():
    """The review's eighth pass, part 4, left to the console's routes: `/timeline` and `/export` read a recorder door's
    answer whole and each span bare — `int(sp["epoch"])` of a door of another build or a proxy (`{"epoch": "e3"}`)
    raised out of the route, and the good door's footage was lost with it. A door's timeline is read up to a bound
    (`rows.answer`) and span by span (`scan.door_spans`, `door_timeline`): a span that does not parse costs that span,
    and the door is named among those that did not answer; the good door's minutes are drawn and exported."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import sys
    rows = sys.modules["w2cplatform.rows"]                              # the module in use (`test_slot_fence` says why)
    from w2cplatform.contract import Heartbeat
    from vms.config import REC_SPEC
    box = Box()
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    st = store()
    t = box.wall()
    footage(st, "7", 3, t - 3600, t - 3000)
    dsrv = door(box, st)

    class Bad(BaseHTTPRequestHandler):                                # a door of another build: its epoch is a word
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = json.dumps({"spans": [{"epoch": "e3", "start": t - 3600, "end": t - 3000, "bytes": 10}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)
    bad = ThreadingHTTPServer(("127.0.0.1", 0), Bad)
    threading.Thread(target=bad.serve_forever, daemon=True).start()
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-bad"), Heartbeat("r-bad", box.wall(), [], {
        "server": "srv-9", "archive_url": f"http://127.0.0.1:{bad.server_address[1]}", "volume": "other"}).to_bytes())
    srv = serve(ctl, box.archive, port=0, wall=box.wall)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/timeline/7?from={t - 3600}&to={t - 3000}") as r:
            tl = json.loads(r.read())
        assert tl["unreachable"] == ["r-bad"] and tl["segments"] and all(s["recorder"] == "r-door" for s in tl["segments"])
        with urllib.request.urlopen(f"{base}/export/7?from={t - 3600}&to={t - 3300}") as r:
            assert r.status == 200 and r.read()[4:8] == b"ftyp" and r.headers.get("X-Archive-Unreachable") == "r-bad"
        was, rows.ANSWER_MAX = rows.ANSWER_MAX, 64                    # an answer past the bound: not read, that door silent
        try:
            with urllib.request.urlopen(f"{base}/timeline/7?from={t - 3600}&to={t - 3000}") as r:
                tl = json.loads(r.read())
        finally:
            rows.ANSWER_MAX = was
        assert set(tl["unreachable"]) == {"r-bad", "r-door"}
    finally:
        srv.shutdown(); dsrv.shutdown(); bad.shutdown()


def test_a_door_whose_timeline_is_brackets_past_the_parsers_depth_is_a_door_that_did_not_answer():
    """The review's ninth pass, minor — a run: a door that answered nested brackets (there 100 000 of them, 200 KB; how
    deep the parser goes depends on the stack it runs on) raised `RecursionError` out of `door_timeline`, which no caller
    catches — the camera's timeline and its export were 500, the good door's footage lost with them. Whatever the parser
    raises (`PARSE_ERRORS`) is the door not answering: named, and the other door's minutes drawn and exported."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from w2cplatform.contract import Heartbeat
    from vms.config import REC_SPEC
    box = Box()
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    st = store()
    t = box.wall()
    footage(st, "7", 3, t - 3600, t - 3000)
    dsrv = door(box, st)

    class Deep(BaseHTTPRequestHandler):                               # a door — or a proxy — answering brackets
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = b"[" * 1_000_000 + b"]" * 1_000_000      # how deep the parser goes is the stack's: past it here
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)
    deep = ThreadingHTTPServer(("127.0.0.1", 0), Deep)
    threading.Thread(target=deep.serve_forever, daemon=True).start()
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-deep"), Heartbeat("r-deep", box.wall(), [], {
        "server": "srv-9", "archive_url": f"http://127.0.0.1:{deep.server_address[1]}", "volume": "other"}).to_bytes())
    srv = serve(ctl, box.archive, port=0, wall=box.wall)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/timeline/7?from={t - 3600}&to={t - 3000}") as r:
            tl = json.loads(r.read())
        assert tl["unreachable"] == ["r-deep"] and tl["segments"] and all(s["recorder"] == "r-door" for s in tl["segments"])
        with urllib.request.urlopen(f"{base}/export/7?from={t - 3600}&to={t - 3300}") as r:
            assert r.status == 200 and r.read()[4:8] == b"ftyp" and r.headers.get("X-Archive-Unreachable") == "r-deep"
    finally:
        srv.shutdown(); dsrv.shutdown(); deep.shutdown()
