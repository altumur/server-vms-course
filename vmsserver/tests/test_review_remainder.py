"""What was left of the platform review that needed no decision (feedback BI). Nine small things:

    the store    its lock has a limit; a delete is a write; an epoch is never deleted; a CAS waits before it tries again
    the policy   sweeps by the names of the files, not by reading them; the copies of other servers age too;
                 a store that did not answer is "I do not know" — not "the knob is off", and not "thirty days"
    a command    carries a deadline, a near one; and is performed at most once
    what is seen how long since each recording last took a frame; who read the archive
"""
import io
import json
import os
import tempfile
import urllib.request

from w2cplatform import variables
from w2cplatform.contract import Heartbeat
from w2cplatform.epoch import next_epoch
from w2cplatform.events import EventLog, buckets_under
from w2cplatform.memvariables import MemVariables
from w2cplatform.resource import MIRROR_GRACE, MIRROR_KEY, SPACE_KEY, Resource, mirrored_buckets, resources_seen
from w2cplatform.spec import Refused, SpecController
from w2cplatform.variables import FileVariables, Forbidden, StoreBusy, cas_pause
from vms import keeps
from vms.config import REC_SPEC, SPEC
from tests.conftest import Box, door, footage, recorder, store
from tests.test_group_by import _ctl, _holder, _worker
from tests.test_store_outage import Flaky

DAY = 86400.0


# -- the store -------------------------------------------------------------------------------------------

def test_a_store_whose_lock_is_held_says_busy_instead_of_waiting_for_ever():
    """`flock(LOCK_EX)` waited for as long as it took — and with it the loop that renews the leases. The lock is
    asked for, and after `LOCK_WAIT` the write raises `StoreBusy`: an `OSError`, which a worker already reads
    as "the store did not answer"."""
    import fcntl
    import time
    box = Box()
    box.vars.put("thing/u/a", {"n": 1})
    g = type(box.vars)._locked.__globals__                             # the module THIS store was built from (other tests re-import it)
    real, g["LOCK_WAIT"], StoreBusy = g["LOCK_WAIT"], 0.2, g["StoreBusy"]
    try:
        with open(box.vars.lock_file, "a+") as somebody:               # a backup tool, a stuck neighbour, a debugger
            fcntl.flock(somebody, fcntl.LOCK_EX)
            t0 = time.monotonic()
            for write in (lambda: box.vars.put("thing/u/a", {"n": 2}), lambda: box.vars.delete("thing/u/a")):
                try:
                    write()
                    raise AssertionError("a write went through a lock somebody else holds")
                except StoreBusy as e:
                    assert isinstance(e, OSError) and "held by another process" in str(e)
            assert 0.4 <= time.monotonic() - t0 < 3                    # it waited its limit, twice, and no longer
            assert box.vars.get("thing/u/a")[0] == {"n": "1"}          # a read needs no lock
        assert box.vars.put("thing/u/a", {"n": 2}) > 0                 # released: the next write goes through
    finally:
        g["LOCK_WAIT"] = real


def test_a_delete_is_a_write_and_an_epoch_is_never_deleted():
    """`delete` checked no ACL: a worker's token, which writes epochs and its slot, could remove a camera's row.
    And an epoch row is a counter — deleted, it starts again from 1 under names (`e1`) that footage and events
    already carry. The rule is one function, so the backends cannot disagree."""
    for store in (Box().vars, MemVariables()):
        store.put("vms/cameras/7", {"name": "gate"})
        store.put("vms/requests/r1", {"unit": "7"})
        worker = store.as_writer("vmsworker", SPEC.sub.acl_worker())
        console = store.as_writer("console", SPEC.acl_console())
        try:
            worker.delete("vms/cameras/7")
            raise AssertionError("a worker deleted a row it may not write")
        except Forbidden as e:
            assert "vmsworker may not delete vms/cameras/7" in str(e)
        assert store.get("vms/cameras/7")[0] is not None
        console.delete("vms/requests/r1")                              # its own family: as before
        assert store.get("vms/requests/r1")[0] is None

        assert next_epoch(worker, "vms/epoch/7")[0] == 1
        for handle in (worker, console, store):                        # its writer, another token, and no token at all
            try:
                handle.delete("vms/epoch/7")
                raise AssertionError("an epoch was deleted")
            except Forbidden as e:
                assert "a counter nobody deletes" in str(e)
        assert next_epoch(worker, "vms/epoch/7")[0] == 2               # …and the count goes on


def test_a_lost_cas_waits_a_random_moment_that_grows_and_stays_short():
    slept = []
    for attempt in (0, 3, 8, 50):
        t = cas_pause(attempt, sleep=slept.append)
        assert 0 <= t <= min(variables.CAS_PAUSE_MAX, 0.0005 * 2 ** min(attempt, 12)) and slept[-1] == t
    assert max(cas_pause(50, sleep=lambda t: None) for _ in range(200)) <= 0.1
    assert len({cas_pause(6, sleep=lambda t: None) for _ in range(20)}) > 1      # random: two losers do not wait the same

    # …and the loops use it: twenty writers on one counter all get a number, and no number twice
    import threading
    box = Box(); got = []
    ts = [threading.Thread(target=lambda: got.append(next_epoch(box.vars, "thing/epoch/u")[0])) for _ in range(20)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sorted(got) == list(range(1, 21))


# -- the policy pass --------------------------------------------------------------------------------------

def _two_resources(box):
    roots = {s: tempfile.mkdtemp(prefix=f"res-{s}-") for s in ("srv-a", "srv-b")}

    class Local:
        def mirrored(self, url, server): return mirrored_buckets(roots[url], server)
        def put(self, url, server, path, data):
            p = os.path.join(roots[url], ".mirror", server, path); os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").write(data)
        def get(self, url, server, path): return open(os.path.join(roots[url], ".mirror", server, path), "rb").read()

    return roots, {s: Resource(r, s, s, box.vars, box.objects, wall=box.wall, peers=Local()) for s, r in roots.items()}


def test_the_policy_sweeps_by_the_names_of_the_files_and_the_copies_age_too():
    """The retention pass opened every bucket it kept, to count lines it had no use for; the heartbeat did the
    same to every copy, every ten seconds. And `.mirror/` was in no walk at all: with the mirror on it only grew."""
    import builtins
    box = Box(); t = box.wall() - 7200
    roots, res = _two_resources(box)
    EventLog(roots["srv-a"], "vms", "7", 1).append(t + 5, "alarm")
    EventLog(roots["srv-a"], "vms", "8", 1).append(t + 5, "motion")
    EventLog(roots["srv-a"], "vms", "8", 1).append(t + 3000, "motion")
    for r in res.values(): r.heartbeat()
    box.vars.put(MIRROR_KEY, {"enabled": "true", "copies": "1"})
    assert res["srv-a"].pass_()["mirrored"] == 3

    opened, real = [], builtins.open
    builtins.open = lambda p, *a, **k: (opened.append(str(p)), real(p, *a, **k))[1]
    try:
        assert res["srv-b"].heartbeat()["mirrors"] == {"srv-a": 3}     # counted…
        assert res["srv-a"].retain() == 0 and res["srv-b"].retain() == 0
    finally:
        builtins.open = real
    assert [p for p in opened if p.endswith(".events.jsonl")] == []    # …and swept over, with no bucket opened

    box.vars.put("vms/retention/7", {"days": 1}); box.vars.put("vms/retention/8", {"days": 1})
    keeps.write(box.vars, {"cam": "8", "from": t, "to": t + 60}, ["8"], "anna", box.wall())
    res["srv-b"].kept = res["srv-a"].kept = __import__("vms.resource", fromlist=["kept_buckets"]).kept_buckets(box.vars)
    box.wall.advance(DAY - 5000)                                       # the two early buckets are past their day…
    assert res["srv-a"].retain() == 1                                  # the original of camera 7 goes; 8's is kept
    assert res["srv-b"].retain() == 0 and res["srv-b"].mirror_removed == 0   # …and the copy waits out the grace
    box.wall.advance(MIRROR_GRACE)
    res["srv-b"].retain()
    assert res["srv-b"].mirror_removed == 1                            # camera 7's copy, an hour after its original
    box.wall.advance(DAY)
    res["srv-b"].retain()
    assert res["srv-b"].mirror_removed == 2                            # camera 8's SECOND bucket, old now too
    left = [b.path for b in mirrored_buckets(roots["srv-b"], "srv-a")]
    assert len(left) == 1 and left[0].startswith("vms/8/")             # the copy under the keep is held like its original


def test_a_store_that_did_not_answer_is_not_a_knob_that_is_off_nor_thirty_days():
    box = Box()
    box.vars.put(SPACE_KEY, {"enabled": "true", "high": "0.85", "low": "0.75", "min_days": "3"}, cas=0)
    flaky = Flaky(box.vars)

    # the watermark: never read -> "unknown", and nothing freed; read once -> the last settings stand
    res = Resource(box.archive, "srv-1", "http://srv-1", flaky, box.objects, wall=box.wall,
                   space_probe=lambda root: (1_000_000, 100_000))
    asked = []
    res.register("rec", type("Hook", (), {"pass_": lambda s, now: {}, "free": lambda s, need, now, min_days, volume=None: (asked.append(need), {"freed": need})[1]})())
    flaky.down = True
    assert res.relieve()["space"] == "unknown" and asked == []
    flaky.down = False
    assert res.relieve()["space"] == "over" and asked == [150_000]
    flaky.down = True
    assert res.relieve()["space"] == "over" and asked == [150_000, 150_000]      # on what it read last

    # the recording's days: a row not READ is not a row that is absent. Forty days of footage of 7 and of 8; 7 is
    # shown for ninety, 8 has no row and is shown for thirty — and a store that blinks changes neither.
    r = recorder(box, acl=False)
    r.lease_pass()
    now = box.wall()
    for unit in ("7", "8"):
        footage(r.store, unit, 1, now - 40 * DAY, now - 40 * DAY + 600, step=10, seal=False)
    r.store.seal()
    box.vars.put("rec/recordings/7", {"id": "7", "name": "7", "cam": "7", "retention_days": 90})
    from vms.recworker import archive_routes
    routes = archive_routes(lambda: r.store, box.wall, visible_from=r._visible_from)

    def shown(unit):
        return len(json.loads(routes(f"/timeline/{unit}?from=0")[1])["spans"])

    assert (shown("7"), shown("8")) == (1, 0)

    class RowsAway:
        def __init__(self, inner): self.inner = inner
        def list(self, prefix): return self.inner.list(prefix)
        def get(self, key):
            if key.startswith("rec/recordings/"):
                raise PermissionError(13, "the store does not answer")
            return self.inner.get(key)

    r.vars = RowsAway(box.vars)
    assert shown("7") == 1                                             # ninety days still: not cut to thirty by a blink
    assert shown("8") == 0


# -- a command --------------------------------------------------------------------------------------------

def _door(box):
    ctl, con = _ctl(box)
    door = con.create_camera({"name": "front door", "source": "driverpack://acme/10.0.0.90/ch/1"})["id"]
    _worker(box, "w-1", "srv-a"); ctl.ensure_placed()
    w = _holder(box, relays=2)
    w.reconcile_once()
    return con, door, w


def test_a_command_carries_a_deadline_and_a_near_one():
    box = Box(); con, door, w = _door(box)
    now = box.wall()
    con.vars.put(SPEC.sub.request_key("a-none"), {"unit": str(door), "action": "output", "port": "1"})
    con.vars.put(SPEC.sub.request_key("b-far"), {"unit": str(door), "action": "output", "port": "1", "valid_until": str(now + 3600)})
    con.vars.put(SPEC.sub.request_key("c-fine"), {"unit": str(door), "action": "output", "port": "1", "valid_until": str(now + 600)})
    done = {d["request"]: d for d in w.requests()}
    assert "without one it would wait" in done["a-none"]["error"] and "more than 600 s away" in done["b-far"]["error"]
    assert done["c-fine"]["action"] == "output" and w.devices["acme/10.0.0.90"].did == [("output", 1, "pulse", 0)]
    assert w.commands == {"performed": 1, "refused": 2, "expired": 0, "unknown": 0}

    # the console says it at the door, and a scenario cannot ask for more either
    from vms.auto import MAX_VALID_FOR
    from vms.console import vms_routes
    from vms.worker import VmsWorker
    route = vms_routes(None, None, con)
    far = json.dumps({"unit": str(door), "action": "output", "port": 1, "valid_until": now + 601}).encode()
    body = type("H", (), {"headers": {"Content-Length": str(len(far))}, "rfile": io.BytesIO(far)})()
    assert route(body, "POST", "/requests", {})[0] == 400 and MAX_VALID_FOR == VmsWorker.MAX_VALID


def test_a_command_another_instance_began_is_not_performed_again():
    """The answer to a request is said in the heartbeat, after the device was called. A worker that died in
    between left a request that looked untouched — and the next holder pulsed the door a second time. The mark
    is written before the call; a request carrying another instance's mark is answered `unknown`."""
    box = Box(); con, door, w = _door(box)
    req = {"unit": str(door), "action": "output", "port": "2", "valid_until": str(box.wall() + 30)}
    con.vars.put(SPEC.sub.request_key("r1"), req)
    assert [d["request"] for d in w.requests()] == ["r1"]
    mark = json.loads(box.objects.get("vms/commands/r1"))
    assert mark["instance"] == w.instance and mark["unit"] == str(door)   # said before the device was called
    # …and the worker dies before its heartbeat: the row is still there, and another instance holds the device

    w2 = _holder(box, relays=2)
    w2.reconcile_once()
    assert w2.instance != w.instance
    done = w2.requests()
    assert [d["request"] for d in done] == ["r1"] and done[0]["error"].startswith("unknown: an earlier instance")
    assert w.instance in done[0]["error"] and w2.devices["acme/10.0.0.90"].did == []      # the door was not touched again
    assert w2.commands["unknown"] == 1 and "command.failed" in [k for _, _, k in w2.observed]

    # the request is cleared by the console; its mark goes on a later pass, and not before
    box.clock.advance(31)
    w2.requests(); assert box.objects.get("vms/commands/r1") is not None
    con.vars.delete(SPEC.sub.request_key("r1"))
    w2.requests(); assert box.objects.get("vms/commands/r1") is not None         # not yet: every thirty seconds
    box.clock.advance(31)
    w2.requests(); assert box.objects.get("vms/commands/r1") is None

    # a request that waits for its device carries no mark: nobody began it
    con.vars.put(SPEC.sub.request_key("r2"), req)
    w2.device_of_row = lambda row: None
    assert w2.requests() == [] and box.objects.get("vms/commands/r2") is None


# -- what is seen -----------------------------------------------------------------------------------------

def test_a_recording_that_is_running_and_fed_nothing_has_an_age_that_grows():
    from vms.console import _recorders
    from vms.worker import FakeActuator
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    act = FakeActuator()
    r = recorder(box, actuator=act, acl=False)
    r.reconciler.actual = {"7": {"revision": 1}}
    r.rows = [{"id": "7", "cam": "7", "name": "7", "enabled": True, "revision": 1}]
    t0 = box.wall()
    act.offered_bytes["7"] = 1000; r.writer_pass()
    box.wall.advance(5); act.offered_bytes["7"] = 9000; r.writer_pass()          # fed: the moment moves
    box.wall.advance(40); r.writer_pass()                                        # up, and fed nothing
    assert r.status_extra(r.rows[0])["last_frame_at"] == t0 + 5
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-1"), Heartbeat("r-1", box.wall(), [
        {"id": "7", "phase": "running", "last_frame_at": t0 + 5}, {"id": "8", "phase": "running"}], {"server": "srv-1"}).to_bytes())
    box.wall.advance(15)                                                         # …and the recorder goes silent too
    text = "\n".join(_recorders(rec))
    assert 'rec_last_frame_age_seconds{unit="7"} 55.0' in text and 'rec_last_frame_age_seconds{unit="8"}' not in text
    r.reconciler.actual = {}; r.writer_pass()
    assert r.fed == {}                                                           # stopped: nothing is said about it


def test_who_read_the_archive_is_an_event_and_once_a_minute():
    """Footage that leaves through the console is said: who, which interval, and — the piece having left whole
    — its sha256 (feedback BI, BU). The same piece by the same person is said once a minute."""
    from vms.console import serve
    from vms.controller import VmsController
    box = Box()
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    st = store()
    start = box.wall() - 3600
    footage(st, "7", 3, start, start + 600)
    rec_door = door(box, st)
    srv = serve(ctl, box.archive, port=0, wall=box.wall)
    port = srv.server_address[1]

    def read(user, a, b):
        req = urllib.request.Request(f"http://127.0.0.1:{port}/export/7?rec=7&from={start + a}&to={start + b}",
                                     headers={"X-User": user})
        with urllib.request.urlopen(req) as r:
            return r.read()

    def said(n=None):                                                    # written after the reply has gone: ask until it lands
        import time
        for _ in range(100):
            got = _said()
            if n is None or len(got) >= n:
                return got
            time.sleep(0.02)
        return got

    def _said():
        return [(e["user"], e["media"], e["recording"], e.get("sha256"))   # in the journal: `audit/console/…` (feedback BN)
                for b in buckets_under(box.archive, "audit", "console", 600)
                for e in map(json.loads, open(os.path.join(box.archive, b.path))) if e["kind"] == "archive.read"]

    try:
        import hashlib
        piece = f"rec/7/{start + 60:.0f}-{start + 120:.0f}"
        data = [read("anna", 60, 120) for _ in range(3)]                       # the same minute, three times
        digest = hashlib.sha256(data[0]).hexdigest()
        assert said(1) == [("anna", piece, "7", digest)]                       # …one line, and what it was
        read("boris", 60, 120)
        box.wall.advance(61); rec_door.announce()
        read("anna", 60, 120)                                                  # a minute later it is said again
        assert [x[0] for x in said(3)] == ["anna", "boris", "anna"]
    finally:
        srv.shutdown(); rec_door.shutdown()


def test_the_door_cuts_a_span_at_the_ceiling_and_shows_what_a_keep_holds_behind_it():
    """A span that began before the ceiling is cut at it — drawn from its start, it would be footage the page
    shows and the door then refuses to play. And a keep is the operator's word that some minutes matter longer
    than the recording's days: the door shows them past the ceiling — which is also how the recorder copying
    keeps into an incidents volume can read them."""
    from vms import keeps
    from vms.recworker import archive_routes
    box = Box()
    r = recorder(box, acl=False)
    r.lease_pass()
    now = box.wall()
    footage(r.store, "7", 1, now - 12 * DAY, now, step=600)             # twelve days, one span
    box.vars.put("rec/recordings/7", {"id": "7", "name": "7", "cam": "7", "retention_days": 8})
    routes = archive_routes(lambda: r.store, box.wall, visible_from=r._visible_from, kept=r._kept_of)

    def spans():
        return [(s["start"], s["end"]) for s in json.loads(routes("/timeline/7?from=0")[1])["spans"]]

    assert spans() == [(now - 8 * DAY, now)]                           # cut at the ceiling, not drawn from twelve days ago
    assert routes(f"/samples/7?from={now - 11 * DAY}&to={now - 10 * DAY}")[1] == b""
    keeps.write(box.vars, {"cam": "7", "from": now - 11 * DAY, "to": now - 10 * DAY}, ["7"], "anna", now)
    assert spans() == [(now - 11 * DAY, now - 10 * DAY), (now - 8 * DAY, now)]
    assert routes(f"/samples/7?from={now - 11 * DAY}&to={now - 10 * DAY}")[1] != b""


def test_a_read_starts_on_the_key_frame_before_the_moment_asked_for():
    """The moment asked for is inside a group of pictures that opened earlier. Without that key frame nothing of
    the moment decodes, so the read brings the lead-in, and whoever asked clips it (`Scan.accepts`)."""
    from w2cplatform.obsd import unix_s
    st = store()
    t = Box().wall()
    footage(st, "7", 1, t - 100, t, step=1)                            # a key frame every two seconds
    got = st.samples("7", t - 51, t - 40)
    assert got[0].key and unix_s(got[0].begin) == t - 52               # the group's key frame, a second before
    assert all(unix_s(s.begin) < t - 40 for s in got)
