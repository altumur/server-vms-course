"""What was left of the platform review that needed no decision (feedback BI). Nine small things:

    the store    its lock has a limit; a delete is a write; an epoch is never deleted; a CAS waits before it tries again
    the policy   sweeps by the names of the files, not by reading them; the copies of other servers age too;
                 a store that did not answer is "I do not know" — not "the knob is off", and not "thirty days"
    a command    carries a deadline, a near one; and is performed at most once — under a lease, with a mark made once
    what is seen how long since each recording last took a frame; who read the archive
    whose clock  a heartbeat from the future is not live, and the skew is a number (the review's second pass)
"""
import io
import json
import os
import tempfile
import urllib.request

from w2cplatform import variables
from w2cplatform.contract import Heartbeat, Slot
from w2cplatform.epoch import next_epoch
from w2cplatform.events import EventLog, buckets_under
from w2cplatform.memvariables import MemVariables
from w2cplatform.resource import MIRROR_GRACE, MIRROR_KEY, SPACE_KEY, Resource, mirrored_buckets, resources_seen
from w2cplatform.spec import Refused, SpecController
from w2cplatform.variables import FileVariables, Forbidden, StoreBusy, cas_pause
from vms import keeps
from vms.config import REC_SPEC, SPEC
from tests.conftest import Served
from tests.vmsconftest import Box, door, footage, recorder, store
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
    # (what a keep holds is the spec's `holds:`, read by every resource itself — the boundary's step 6)
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
    box.vars.put(SPACE_KEY, {"enabled": "true", "high": "0.85", "low": "0.75"}, cas=0)
    flaky = Flaky(box.vars)

    # the watermark: never read -> "unknown", and nothing freed; read once -> the last settings stand
    res = Resource(box.resource_root, "srv-1", "http://srv-1", flaky, box.objects, wall=box.wall,
                   space_probe=lambda root: (1_000_000, 100_000))
    from vms.config import REC_SPEC                                    # it frees by a request row (`requests: {free}`)
    [vol] = list(res.volumes)
    asked = lambda: box.vars.get(res._free_key(REC_SPEC, vol))[0]
    flaky.down = True
    assert res.relieve()["space"] == "unknown" and asked() is None
    flaky.down = False
    assert res.relieve()["space"] == "over" and asked()["free"] == "150000"
    box.vars.delete(res._free_key(REC_SPEC, vol))
    flaky.down = True
    assert res.relieve()["space"] == "over"                             # on what it read last (the ask itself waits for the store)
    flaky.down = False
    assert res.relieve()["space"] == "over" and asked()["free"] == "150000"

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
        return len(json.loads(routes(f"/spans/{unit}?from=0")[1])["spans"])

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

    # the console says it at the door (the spec's `requests.most_valid`), and a scenario cannot ask for more either
    from vms.auto import MAX_VALID_FOR
    from vms.worker import VmsWorker
    from w2cplatform.console import SpecConsole
    with Served(SpecConsole(con, wall=box.wall)) as call:
        far = {"unit": f"vms/{door}", "action": "output", "port": 1, "valid_until": now + 601}
        assert call("POST", "/requests", far, key="far-1")[1]["error"] == "too far"
    assert MAX_VALID_FOR == VmsWorker.MAX_VALID == SPEC.requests["most_valid"]


def test_a_command_retried_is_one_command():
    """M17 of the platform review, left open in its second pass: `POST /requests` named the row by the clock, so a
    retried click — the page's, a proxy's — filed a second command and the door pulsed twice. The `Idempotency-Key`
    is required and is the row's name (unless the body names one); the row is written create-only, and the retry
    finds it and is answered the same 202. Without the key: 400, before anything is looked at. (The platform's route
    since the boundary's step 6, the spec's `requests:`.)"""
    from w2cplatform.console import SpecConsole
    box = Box(); con, door, w = _door(box)
    served = Served(SpecConsole(con, wall=box.wall))

    def post(key, **fields):
        return served("POST", "/requests", {"unit": f"vms/{door}", "action": "output", "port": 1, **fields}, key=key or False)

    assert post(None)[0] == 400 and post(None)[1]["error"] == "Idempotency-Key required"
    assert box.vars.list("vms/requests/") == []
    first = post("click-1")
    assert first[0] == 202 and first[1]["queued"]["id"] == "click-1"
    box.wall.advance(3)
    assert post("click-1") == first                                       # the same request: the row it filed, not a second one
    assert box.vars.list("vms/requests/") == [SPEC.sub.request_key("click-1")]
    assert post("click-2")[0] == 202 and len(box.vars.list("vms/requests/")) == 2   # another click is another command
    assert post("a/b")[0] == 400                                          # a key is a name, not a path (one segment)
    assert post("click-3", id="by-name")[1]["queued"]["id"] == "by-name"  # a body may still name its request
    served.close()
    assert [d["request"] for d in w.requests()] == ["by-name", "click-1", "click-2"] and w.commands["performed"] == 3


def test_a_command_another_instance_began_is_not_performed_again():
    """The answer to a request is said in the heartbeat, after the device was called. A worker that died in
    between left a request that looked untouched — and the next holder pulsed the door a second time. The mark
    is written before the call; a request carrying another instance's mark is answered `unknown`."""
    import threading
    box = Box(); con, door, w = _door(box)
    req = {"unit": str(door), "action": "output", "port": "2", "valid_until": str(box.wall() + 30)}
    con.vars.put(SPEC.sub.request_key("r1"), req)
    gate = threading.Event()                                              # the device takes its time to answer…
    dev = w.devices["acme/10.0.0.90"]
    slow, dev.output = dev.output, lambda *a, **k: (gate.wait(5), slow(*a, **k))[1]
    assert w.requests() == []                                             # …the call is in flight
    mark = json.loads(box.objects.get("vms/commands/r1"))
    assert mark["instance"] == w.instance and mark["unit"] == str(door)   # said before the device was called
    assert "outcome" not in mark                                          # and how it went is not known yet
    # …and the worker dies before the device answers: the row is still there, and another instance holds the device

    w2 = _holder(box, relays=2)
    w2.reconcile_once()
    assert w2.instance != w.instance
    done = w2.requests()
    assert [d["request"] for d in done] == ["r1"] and done[0]["error"].startswith("unknown: an earlier instance")
    assert w.instance in done[0]["error"] and w2.devices["acme/10.0.0.90"].did == []      # the door was not touched again
    assert w2.commands["unknown"] == 1 and "command.failed" in [k for _, _, k in w2.observed]
    gate.set()

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


def test_a_commands_key_outlives_its_row_and_a_holder_forgets_what_nobody_will_ask_again():
    """The review's third pass, minor. The key of `POST /requests` lived only as long as the row: the holder answered,
    the row was cleared, and a retry ninety seconds later filed the command again — a second pulse of the door. The
    key is kept where the console keeps every key, for a day: the retry is the first reply, and no row. And a holder's
    `fetched` grew by one id per command for the life of the process; it keeps an id while the row stands."""
    from vms.console import serve
    box = Box(); ctl, con = _ctl(box)
    door = con.create_camera({"name": "door", "source": "driverpack://acme/10.0.0.90/ch/1", "kind": "io"})["id"]
    srv = serve(con, None, port=0, wall=box.wall)

    def post(key, body, user="anna"):
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/requests", data=json.dumps(body).encode(),
                                     method="POST", headers={"Idempotency-Key": key, "X-User": user})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)
    import urllib.error
    try:
        pulse = {"unit": f"vms/{door}", "action": "output", "port": 1}
        first = post("open-1", pulse)
        assert first[0] == 202 and box.vars.list(SPEC.sub.requests_prefix()) == [SPEC.sub.request_key("open-1")]
        box.vars.delete(SPEC.sub.request_key("open-1"))                     # answered by the holder, cleared by the controller
        box.wall.advance(90)
        assert post("open-1", pulse) == first                               # the retry: the first reply…
        assert box.vars.list(SPEC.sub.requests_prefix()) == []              # …and no second command
        assert post("open-1", {**pulse, "port": 2})[0] == 422               # the same key for another command: refused
        assert post("open-2", {"unit": "vms/999", "action": "output"})[0] == 404
        assert post("open-2", pulse)[0] == 202                              # a refusal did not spend the key
    finally:
        srv.shutdown()

    w = _holder(box)
    w.fetched = ["gone-1", "open-2", "gone-2"]                               # answered; only open-2's row still stands
    w.requests()
    assert w.fetched == ["open-2"]


def test_a_command_for_a_camera_nobody_holds_is_ended_by_the_reaper_and_counted():
    """The product's cross-check (4 Oct): a command for a camera with no holder hung for ever. In the course too: a
    command is ended by its HOLDER at its deadline, and the console's sweep passed every row with an `action` by — a
    camera placed nowhere had its command standing for good, never answered, never counted. Filed through the door
    for an unplaced camera, the row stands while a holder could still come for it, and the reaper's turn ends it
    `COMMAND_REAP_AFTER` past its deadline, counted on `/metrics` with the requests that expired. Its siblings in the
    same sweep: a command whose deadline is not a time (ended once its filing is older than the longest a command may
    wait), one a holder answered whose answer never reached a heartbeat (cleared, not counted twice), a scenario's row
    with an action nobody serves, in another family; a `record` and a young backfill are not this pass's."""
    from vms import jobs
    from w2cplatform import requests
    from vms.__main__ import _reap_turn
    from w2cplatform.metrics import text as spec_metrics
    from w2cplatform.console import SpecConsole
    box = Box(); ctl, con = _ctl(box)
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    gate = con.create_camera({"name": "gate", "source": "driverpack://acme/10.0.0.93/ch/1"})["id"]
    assert ctl.placement(gate) is None                                    # no worker anywhere: nobody holds it
    with Served(SpecConsole(con, wall=box.wall)) as call:
        filed = call("POST", "/requests", {"unit": f"vms/{gate}", "action": "output", "port": 1}, key="open-gate")
    assert filed[0] == 202
    until = float(filed[1]["queued"]["valid_until"])
    now = box.wall()
    con.vars.put(SPEC.sub.request_key("no-deadline"), {"unit": str(gate), "action": "output", "port": "1",
                                                       "valid_until": "soon", "at": str(now)})
    con.vars.put(SPEC.sub.request_key("answered"), {"unit": str(gate), "action": "output", "port": "1",
                                                    "valid_until": str(now + 30)})
    box.objects.put("vms/commands/answered", json.dumps({"instance": "w-x", "outcome": "performed"}).encode())
    rec.vars.put(REC_SPEC.sub.request_key("snap-0"), {"unit": str(gate), "action": "snapshot", "at": str(now),
                                                      "valid_until": str(now + 30), "by": "auto/s-1"})
    rec.vars.put(REC_SPEC.sub.request_key("s-1"), {"action": "record", "cam": str(gate), "minutes": "10", "at": str(now)})
    rec.vars.put(REC_SPEC.sub.request_key("7-1-2"), {"unit": "7", "cam": "7", "from": "1", "to": "2", "at": str(now),
                                                     "action": "backfill"})

    def standing(c, spec):
        return sorted(k.rsplit("/", 1)[1] for k in c.vars.list(spec.sub.requests_prefix()))

    was = dict(requests.expired)
    box.wall.advance(until - now + requests.REAP_AFTER - 5)           # past its deadline: a holder's still, if one comes
    requests.turn([rec, con], sweep=True)
    assert standing(con, SPEC) == ["answered", "no-deadline", "open-gate"]
    box.wall.advance(10)                                                  # a minute past it: nobody will
    requests.turn([rec, con], sweep=True)
    assert standing(con, SPEC) == ["no-deadline"]                         # its filing is not ten minutes old yet
    assert standing(rec, REC_SPEC) == ["7-1-2", "s-1"]
    assert requests.expired.get("vms", 0) == was.get("vms", 0) + 1           # the answered one is not counted again
    assert requests.expired.get("rec", 0) == was.get("rec", 0) + 1
    box.wall.advance(requests.MOST_VALID)
    requests.turn([rec, con], sweep=True)
    assert standing(con, SPEC) == [] and requests.expired.get("vms", 0) == was.get("vms", 0) + 2
    text = "\n".join(requests.metrics_lines())                               # the request loops' process's own numbers
    assert f'w2c_requests_expired_total{{sub="vms"}} {requests.expired.get("vms", 0)}' in text, text


def test_a_command_its_holder_is_still_performing_is_not_reaped_and_one_whose_holder_went_is_not_known():
    """The review's thirteenth pass, minor: a holder's call into the device hung past the deadline and the minute, and
    the reaper ended the command "unperformed" while it was being performed. A mark with no outcome whose holder still
    holds the name it marked under is left to that holder; once the name is another instance's, the command is ended
    as NOT KNOWN — `w2c_requests_unknown_total`, not `w2c_requests_expired_total`."""
    from vms import jobs
    from w2cplatform import requests
    from vms.__main__ import _reap_turn
    from w2cplatform.metrics import text as spec_metrics
    box = Box(); ctl, con = _ctl(box)
    gate = con.create_camera({"name": "gate", "source": "driverpack://acme/10.0.0.94/ch/1"})["id"]
    now = box.wall()
    con.vars.put(SPEC.sub.request_key("slow"), {"unit": str(gate), "action": "output", "port": "1",
                                                "valid_until": str(now + 30)})
    box.vars.put("vms/slots/w-1", Slot("w-1", "box-a:1:aaaaaa", now + 45, False, 1).to_items())
    box.objects.put("vms/commands/slow", json.dumps({"instance": "box-a:1:aaaaaa", "slot": "w-1", "unit": str(gate),
                                                     "at": now}).encode())                 # begun: the call has not returned
    was, unknown = dict(requests.expired), dict(requests.unknown)
    box.wall.advance(30 + requests.REAP_AFTER + 5)
    requests.turn([con], sweep=True)
    assert box.vars.get(SPEC.sub.request_key("slow"))[0] is not None                     # its holder's to answer
    assert requests.expired.get("vms", 0) == was.get("vms", 0) and requests.unknown.get("vms", 0) == unknown.get("vms", 0)
    box.vars.put("vms/slots/w-1", Slot("w-1", "box-a:2:bbbbbb", box.wall() + 45, False, 2).to_items())   # it went
    requests.turn([con], sweep=True)
    assert box.vars.get(SPEC.sub.request_key("slow"))[0] is None
    assert requests.expired.get("vms", 0) == was.get("vms", 0) and requests.unknown.get("vms", 0) == unknown.get("vms", 0) + 1
    text = "\n".join(requests.metrics_lines())
    assert f'w2c_requests_unknown_total{{sub="vms"}} {requests.unknown.get("vms", 0)}' in text, text


def test_a_command_to_a_unit_held_without_a_lease_takes_its_epoch_first_and_the_mark_is_made_once():
    """The review's second pass (minor): a unit `live: on-demand` is held — its device on the line, nothing
    recorded — under no epoch and so under no lease; its commands went to the device with no fence at all, and the
    mark that says "I began it" was read, then written: two holders in the same second both read nothing and both
    pulsed the door. Now the unit takes its epoch before its first command, so a second holder fences the first;
    and the mark is created or refused by the store, never written over."""
    box = Box(); ctl, con = _ctl(box)
    door = con.create_camera({"name": "back door", "source": "driverpack://acme/10.0.0.91/ch/1", "live": "on-demand"})["id"]
    _worker(box, "w-1", "srv-a"); ctl.ensure_placed()
    w = _holder(box, relays=2); w.reconcile_once()
    assert {s["id"]: s["phase"] for s in w.status()}[door] == "held" and str(door) not in w.leases    # held, no epoch: the finding

    con.vars.put(SPEC.sub.request_key("d1"), {"unit": str(door), "action": "output", "port": "1", "valid_until": str(box.wall() + 30)})
    assert [d["request"] for d in w.requests()] == ["d1"] and w.devices["acme/10.0.0.91"].did == [("output", 1, "pulse", 0)]
    assert w.may_act(str(door)) and box.vars.get(f"vms/epoch/{door}")[0]["epoch"] == "1"            # under a lease from here on
    con.vars.delete(SPEC.sub.request_key("d1"))                                                        # the console clears what was answered

    # a second holder of the same device — the seconds of a double assignment: its command takes epoch 2, and the
    # first instance learns at its next renewal that the unit is not its to act on; its next command, if the
    # device is still assigned to it, takes epoch 3 and fences the second — every command under a lease the
    # store confirmed, as every stream is
    from vms.worker import FakeActuator, FakeDevice, VmsWorker
    w2 = VmsWorker("w-2", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-b", env={},
                   resource_root=box.resource_root, device_factory=lambda key: FakeDevice(key, channels=["1"], relays=2))
    ctl.assign_add("w-2", str(door)); w2.reconcile_once()                                              # the double assignment
    con.vars.put(SPEC.sub.request_key("d2"), {"unit": str(door), "action": "output", "port": "2", "valid_until": str(box.wall() + 30)})
    assert [d["request"] for d in w2.requests()] == ["d2"] and w2.may_act(str(door))
    assert str(door) in w.lease_pass() and not w.may_act(str(door)) and str(door) not in w.leases
    con.vars.delete(SPEC.sub.request_key("d2"))
    con.vars.put(SPEC.sub.request_key("d3"), {"unit": str(door), "action": "output", "port": "1", "valid_until": str(box.wall() + 30)})
    # "still assigned to it" is what a pass reads: let go by the lease step, the unit is not taken back on the rows read
    # before (a beat between passes; `test_a_camera_the_lease_step_let_go_is_not_taken_back_on_a_beat_…`)
    assert w.requests() == [] and box.vars.get(f"vms/epoch/{door}")[0]["epoch"] == "2"
    w.reconcile_once()                                                                                 # the double assignment still stands
    assert [d["request"] for d in w.requests()] == ["d3"] and box.vars.get(f"vms/epoch/{door}")[0]["epoch"] == "3"
    assert str(door) in w2.lease_pass() and not w2.may_act(str(door))

    # the mark: the store says who made it
    assert w2._mark("m1", str(door), box.wall()) and not w._mark("m1", str(door), box.wall())
    assert json.loads(box.objects.get("vms/commands/m1"))["instance"] == w2.instance                     # …and it was not written over

    # a store with no create-only (the review's third pass): reading the mark back after a last-writer-wins write is
    # no fence — A puts, A reads its own name, B puts, B reads its own — so the command is REFUSED, and says why
    class LastWriterWins:
        def __init__(self, real): self._r = real
        def __getattr__(self, n):
            if n == "put_new":
                raise AttributeError(n)
            return getattr(self._r, n)
    w.objects = LastWriterWins(box.objects)
    assert w._mark("m2", str(door), box.wall()) is None and box.objects.get("vms/commands/m2") is None
    con.vars.delete(SPEC.sub.request_key("d3"))
    con.vars.put(SPEC.sub.request_key("d4"), {"unit": str(door), "action": "output", "port": "2", "valid_until": str(box.wall() + 30)})
    did = list(w.devices["acme/10.0.0.91"].did)
    [answer] = [d for d in w.requests() if d["request"] == "d4"]
    assert "create-only" in answer["error"] and box.objects.get("vms/commands/d4") is None
    assert w.devices["acme/10.0.0.91"].did == did                                                      # the device was not called


# -- whose clock -------------------------------------------------------------------------------------------

def test_a_writers_clock_ahead_or_behind_neither_holds_nor_drops_it_and_the_skew_is_said():
    """The review's second pass, M9, and its thirteenth, blocker 4. Liveness was `now - hb.ts`, two machines' clocks with
    `FUTURE_TOLERANCE` between them: a worker a minute ahead stayed "live" a minute after it died, one 50 s behind was
    "dead" while it worked. Now a heartbeat is live while the judge sees it CHANGE (`Eyes`), whatever its `ts` says: a
    minute ahead or a hundred seconds behind, live while it beats and silent once it stands still `lost_after` by the
    judge's clock — on `workers_seen`, the console's state, `holders` and `/schema`'s `builds` alike. The writer's time
    is the skew, counted where a change is seen (`<sub>_heartbeat_skew_seconds_max`/`_min`) and said past `SKEW_ALARM`:
    `clock.skew`, once an episode per writer, in the pass report too (`clock_skew`)."""
    from w2cplatform import contract
    from w2cplatform.console import SpecConsole, holders
    from w2cplatform.events import ALARM
    from vms.controller import VmsController
    from tests.test_slot_fate import _Said
    box = Box()
    ctl = VmsController(box.vars, box.objects, wall=box.wall)
    ctl.journal = said = _Said()
    con = SpecConsole(ctl, wall=box.wall)
    skew = {"w-1": 0, "w-2": 3, "w-3": 60, "w-4": -100}

    def beat(*names):
        for name in names:
            box.objects.put(SPEC.sub.heartbeat_key(name), Heartbeat(name, box.wall() + skew[name], [],
                                                                    {"server": "srv-a", "capacity": 4, "headroom": 4}).to_bytes())
    beat(*skew)
    ctl.look()
    box.wall.advance(10); beat(*skew)                                          # all four beat
    now = box.wall()
    assert sorted(ctl.workers_seen()) == ["w-1", "w-2", "w-3", "w-4"]
    assert sorted(holders(box.objects, "vms/", now, eyes=ctl.eyes)) == ["w-1", "w-2", "w-3", "w-4"]
    assert all(b["live"] for n, b in contract.builds(box.objects, now, eyes=ctl.eyes).items() if n.startswith("vms/"))
    states = {w["worker"]: w["state"] for s in con.servers()["servers"].values() for w in s["workers"]}
    assert states == {"w-1": "live", "w-2": "live", "w-3": "live", "w-4": "live"}
    text = con.metrics_text()
    assert "vms_workers_live 4" in text
    assert contract.SKEW_MAX["vms"] >= 60 and contract.SKEW_MIN["vms"] <= -100
    rep = ctl.pass_once()
    assert set(rep["clock_skew"]) == {"vms/heartbeats/w-3", "vms/heartbeats/w-4"}, rep["clock_skew"]
    assert said.kinds().count(("clock.skew", ALARM)) == 2
    ctl.pass_once()
    assert said.kinds().count(("clock.skew", ALARM)) == 2                      # once an episode
    box.wall.advance(46); beat("w-1", "w-2")                                   # w-3 and w-4 stop
    assert sorted(ctl.workers_seen()) == ["w-1", "w-2"]                        # silent by this clock, whatever theirs said
    states = {w["worker"]: w["state"] for s in con.servers()["servers"].values() for w in s["workers"]}
    assert states == {"w-1": "live", "w-2": "live", "w-3": "stale", "w-4": "stale"}


def test_a_clock_running_behind_is_a_number_too():
    """The review's third pass (M9's remainder). `SKEW_MAX` saw only clocks running AHEAD; a clock behind makes a live
    worker look old, `lost_after` from "dead" sooner than it should be, and nothing said so. The oldest heartbeat
    still judged live is on `/metrics` as `<sub>_heartbeat_skew_seconds_min`; a dead worker's is not counted."""
    import re
    from w2cplatform import contract
    from w2cplatform.console import SpecConsole
    from vms.controller import VmsController
    now = 1_757_500_000.0                                   # the number, on a subsystem name nobody else's threads judge
    for ts in (now - 2, now - 31, now - 400):               # 31 s behind and live; 400 s: dead, not a clock
        contract.is_live("skew-test", ts, now, 45.0)
    contract.is_live("skew-test", now - 9000, now, 1e12)    # a LISTING, not a judgement of liveness: not counted
    assert contract.SKEW_MIN["skew-test"] == -31.0
    box = Box()                                             # …and on `/metrics`, beside the maximum — counted where a
    ctl = VmsController(box.vars, box.objects, wall=box.wall)   # CHANGE is seen (the thirteenth pass, blocker 4)
    box.objects.put(SPEC.sub.heartbeat_key("w-2"), Heartbeat("w-2", box.wall() - 31, [], {"server": "srv-a"}).to_bytes())
    assert "w-2" in ctl.workers_seen()
    box.wall.advance(5)
    box.objects.put(SPEC.sub.heartbeat_key("w-2"), Heartbeat("w-2", box.wall() - 31, [], {"server": "srv-a"}).to_bytes())
    assert "w-2" in ctl.workers_seen()
    m = re.search(r"\nvms_heartbeat_skew_seconds_min (-?[0-9.]+)\n", SpecConsole(ctl, wall=box.wall).metrics_text())
    assert m and float(m.group(1)) <= -31.0


# -- what is seen -----------------------------------------------------------------------------------------

def test_a_recording_that_is_running_and_fed_nothing_has_an_age_that_grows():
    from w2cplatform.metrics import text as spec_metrics
    from vms.worker import FakeActuator
    box = Box()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    act = FakeActuator()
    r = recorder(box, actuator=act, acl=False)
    r.reconciler.actual = {"7": {"revision": 1}}
    r.rows = [{"id": "7", "cam": "7", "name": "7", "enabled": True, "revision": 1}]
    t0 = box.wall()
    act.offered_bytes["7"] = 1000; r.writer_pass()
    assert r.status_extra(r.rows[0])["last_frame_at"] == t0                       # nothing taken yet: counted from the start
    box.wall.advance(5); act.offered_bytes["7"] = 9000; r._tally("7", "OK"); r.writer_pass()   # the writer TOOK a frame: the moment moves
    box.wall.advance(40); act.offered_bytes["7"] = 99000; r._tally("7", "SEQUENCE_TOO_LARGE"); r.writer_pass()
    assert r.status_extra(r.rows[0])["last_frame_at"] == t0 + 5                   # offered, refused: not a frame on the volume
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-1"), Heartbeat("r-1", box.wall(), [
        {"id": "7", "phase": "running", "last_frame_at": t0 + 5}, {"id": "8", "phase": "running"}], {"server": "srv-1"}).to_bytes())
    box.wall.advance(15)                                                         # …and the recorder goes silent too
    text = spec_metrics(rec)
    assert 'rec_last_frame_age_seconds{unit="7"} 55.0' in text and 'rec_last_frame_age_seconds{unit="8"}' not in text
    r.reconciler.actual = {}; r.writer_pass()
    assert r.fed == {}                                                           # stopped: nothing is said about it


def test_who_read_the_archive_is_an_event_and_once_a_minute():
    """Footage that leaves is said: who, which interval, and — the piece having left whole — its sha256 (feedback BI,
    BU). A whole file is said every time it leaves (the review's fourth pass, minor: the second file of the same minute
    need not be the first); a part — a player that moved on — once a minute. Said by the recorder whose door it leaves
    through (`audit/door-<recorder>`), with the name the door token was given to."""
    from tests.vmsconftest import page_door
    box = Box()
    st = store()
    start = box.wall() - 3600
    footage(st, "7", 3, start, start + 600)
    rec_door = door(box, st)
    srv = page_door(box)
    port = srv.server_address[1]

    def read(user, a, b):
        req = urllib.request.Request(f"http://127.0.0.1:{port}/segment/7/e3/{(start + a) * 1000:.0f}-{(start + b) * 1000:.0f}.mp4",
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
        return [(e["user"], e["media"], e["recording"], e.get("sha256"))   # in the journal: the door's (feedback BN)
                for b in buckets_under(box.resource_root, "audit", "door-r-page", 600)
                for e in map(json.loads, open(os.path.join(box.resource_root, b.path))) if e["kind"] == "archive.read"]

    try:
        import hashlib
        piece = f"rec/7/{start + 60:.0f}-{start + 120:.0f}"
        data = [read("anna", 60, 120) for _ in range(3)]                       # the same minute, three times
        digest = hashlib.sha256(data[0]).hexdigest()
        assert said(3) == [("anna", piece, "7", digest)] * 3                   # …three files left: three lines, and what each was
        read("boris", 60, 120)
        assert [x[0] for x in said(4)] == ["anna", "anna", "anna", "boris"]
    finally:
        srv.shutdown(); rec_door.shutdown()


def test_the_door_to_a_recordings_footage_is_said_when_it_is_handed_out():
    """The review's third pass (Н-B1's remainder, and its minor): the console handed out the holder's playback door, the
    footage then went holder → browser, and nothing said so. A recording's door — its recorder's, `url` in its
    heartbeat — is handed out with the recording's place (`/rec/where/<id>` → `door`) and the console never sees those
    bytes; it says what it gave — `door.issued`: who, which unit, which holder, which routes, until when — and the door
    says what was read. The camera's holder has no door to hand out (`vms` declares none)."""
    from tests.conftest import door_keys
    from w2cplatform.spec import SpecController
    from vms.console import serve
    from vms.controller import VmsController
    box = Box()
    with door_keys(box.vars):
        con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
        rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
        srv = serve(con, box.resource_root, port=0, wall=box.wall, mounts={"rec": rec})
    try:
        cam = con.create_camera({"source": "driverpack://file/7.mp4"})["id"]
        rec.create({"name": "7", "cam": str(cam)})
        box.objects.put(REC_SPEC.sub.heartbeat_key("r-1"),
                        Heartbeat("r-1", box.wall(), [{"id": "7", "phase": "running"}],
                                  {"server": "srv-1", "capacity": 4, "headroom": 4, "url": "http://h:1"}).to_bytes())
        box.vars.put("rec/placement/7", {"worker": "r-1", "reason": "its volume", "at": box.wall(), "rev": 1})   # the controller's word
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        assert SPEC.door_routes == () and REC_SPEC.door_routes == ("timeline", "segment")   # no door at a camera's holder
        with urllib.request.urlopen(urllib.request.Request(f"{base}/rec/where/7", headers={"X-User": "anna"})) as r:
            d = json.loads(r.read())["door"]
        assert d["url"] == "http://h:1" and d["routes"] == ["timeline", "segment"] and d["token"]
        lines = [e for b in buckets_under(box.resource_root, "audit", "console", 600)
                 for e in map(json.loads, open(os.path.join(box.resource_root, b.path))) if e["kind"] == "door.issued"]
        assert [(e["user"], e["target"], e["holder"], e["routes"], e["until"]) for e in lines] == [
            ("anna", "7", "r-1", "timeline,segment", round(d["expires"]))]
    finally:
        srv.shutdown()


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
        return [(s["start"], s["end"]) for s in json.loads(routes("/spans/7?from=0")[1])["spans"]]

    assert spans() == [(now - 8 * DAY, now)]                           # cut at the ceiling, not drawn from twelve days ago
    assert routes(f"/samples/7?from={now - 11 * DAY}&to={now - 10 * DAY}")[1] == b""
    keeps.write(box.vars, {"cam": "7", "from": now - 11 * DAY, "to": now - 10 * DAY}, ["7"], "anna", now)
    assert spans() == [(now - 11 * DAY, now - 10 * DAY), (now - 8 * DAY, now)]
    assert routes(f"/samples/7?from={now - 11 * DAY}&to={now - 10 * DAY}")[1] != b""


def test_a_read_starts_on_the_key_frame_before_the_moment_asked_for():
    """The moment asked for is inside a group of pictures that opened earlier. Without that key frame nothing of
    the moment decodes, so the read brings the lead-in, and whoever asked clips it (`Scan.accepts`)."""
    from vms.obsd import unix_s
    st = store()
    t = Box().wall()
    footage(st, "7", 1, t - 100, t, step=1)                            # a key frame every two seconds
    got = st.samples("7", t - 51, t - 40)
    assert got[0].key and unix_s(got[0].begin) == t - 52               # the group's key frame, a second before
    assert all(unix_s(s.begin) < t - 40 for s in got)


def test_a_shrink_is_requested_until_the_recorder_applies_it_and_an_uncopied_keep_is_a_number():
    """The review's fourth pass, two majors, the console's half. A smaller quota declared without `shrink_confirmed`
    left the ring as it was, while the page showed the new size and the journal said `shrunk`. The volume is the spec's
    table since the boundary's step 6: the journal says what the write changed and from what (`changed`, `was`), and
    the recorder holding the volume says the shrink pending — `quota_note` in its heartbeat, `rec_volume_shrink_pending`
    on `/metrics` — until the operator's second word. (The console's volumes view, which joined the two, went with the
    VMS's route.) And a keep the recorder could not copy is `rec_keep_missing_seconds{keep}` on `/metrics`, from the
    recorder's `keep_missing`."""
    from vms.console import serve
    from vms.controller import VmsController
    box = Box()
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    srv = serve(ctl, box.resource_root, port=0, wall=box.wall, mounts={"rec": rec})
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    T = 10 ** 12

    def call(method, path, body=None):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                     headers={"Content-Type": "application/json", "X-User": "anna"})
        with urllib.request.urlopen(req) as r:
            return r.read().decode() if path.endswith("metrics") else json.loads(r.read())
    try:
        vol = {"name": "big", "kind": "local", "url": "/data/big", "server": "srv-1", "quota_bytes": 8 * T}
        call("POST", "/rec/volumes", vol)
        said = lambda text: [x for x in text.splitlines() if x.startswith("rec_volume_shrink_pending")]   # noqa: E731
        assert said(call("GET", "/rec/metrics")) == []                                    # nobody holds it: nobody says
        out = call("POST", "/rec/volumes", {**vol, "quota_bytes": 4 * T})
        assert out["row"]["quota_bytes"] == 4 * T                                           # declared: the recorder applies it
        box.objects.put(REC_SPEC.sub.heartbeat_key("r-1"), Heartbeat("r-1", box.wall(), [], {
            "server": "srv-1", "volume": "big", "archive": "/data/big", "archive_quota": 8 * T,
            "quota_note": "big is 8000000000000 bytes and declared 4000000000000: not done until shrink_confirmed",
            "keep_missing": {"7-100-200": 100.0, "8-1-2": 0}}).to_bytes())
        call("POST", "/rec/volumes", {**vol, "quota_bytes": 2 * T, "shrink_confirmed": 2 * T})
        lines = [e for b in buckets_under(box.resource_root, "audit", "console", 600)
                 for e in map(json.loads, open(os.path.join(box.resource_root, b.path))) if e["kind"].startswith("archive.volume")]
        assert [(e.get("changed"), e.get("was")) for e in lines] == [
            (None, None), ("quota_bytes", {"quota_bytes": 8 * T}), ("quota_bytes,shrink_confirmed", {"quota_bytes": 4 * T, "shrink_confirmed": 0})]
        metrics = call("GET", "/rec/metrics")
        [pending] = said(metrics)
        assert pending.endswith(" 1"), metrics                                              # r-1 says it
        assert 'rec_keep_missing_seconds{keep="7-100-200"} 100.0' in metrics and 'keep="8-1-2"' not in metrics
    finally:
        srv.shutdown()
