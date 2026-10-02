"""The road from an event to a device, made short — by a hint the receiver pulls, and a look four times a second.

An event is written; the evaluator's pass finds it and files a request; the holder's pass finds the request
and calls the device. Two loops, two seconds each: two seconds on average, four at worst. Since 2 October 2026:

    event -> evaluator   the evaluator holds a request at the resource (`GET /events/wait`), answered when a line
                         of a kind its scenarios watch is appended; its pass begins then (`w2cplatform/longpoll.py`)
    request -> device    the holder looks at its request rows every quarter of a second between passes
                         (`COMMANDS_BEAT`, `VmsWorker.between`)

What these tests hold both to is the rule that makes them safe to add: nothing new decides anything. The answer
to a wait carries no event, and the pass after it is the ordinary pass; the look between passes is the ordinary
`requests`, with the lease, the deadline and the mark. So the road gets short when everything works, and nothing
at all changes when a wait fails, is refused, is switched off, or is answered a thousand times. The first tests
run the REAL loops in threads, over a resource asked over HTTP, with `poll` left at 2 s.
"""
import json
import os
import tempfile
import threading
import time
import types
import urllib.error
import urllib.request

from w2cplatform import longpoll
from w2cplatform.contract import Heartbeat, Subsystem, Worker, requests_acl
from w2cplatform.eventdatabase import MergedIndex
from w2cplatform.events import ALARM, EventLog
from vms.auto import AutoController
from vms.autoworker import AutoWorker
from vms.config import AUTO_SPEC, SPEC as VMS, WORKER_ACL
from vms.controller import VmsController
from vms.worker import COMMANDS_BEAT, FakeActuator, FakeDevice, VmsWorker, commands_beat
from tests.conftest import Box

ON, OFF = {}, {"LONG_POLL": "0", "COMMANDS_BEAT": "0"}     # what a process is started with: both on unless it says


def _until(cond, timeout: float = 10.0, what: str = "") -> None:
    deadline = time.monotonic() + timeout
    while not cond():
        assert time.monotonic() < deadline, f"waited {timeout:g} s for {what or 'a condition'}"
        time.sleep(0.005)


def _real_box() -> Box:
    """A box on the real clocks: the loops below wait real seconds, and a lease runs on the monotonic one."""
    box = Box()
    box.clock, box.wall = time.monotonic, time.time
    return box


def _resource(box, server: str = "srv-a"):
    """The resource of one server, over HTTP, heartbeating its address: `(resource, http server)`."""
    from vms.resource import vms_resource
    from w2cplatform.resource import serve
    res = vms_resource(box.archive, server, "", box.vars, box.objects, wall=box.wall)
    srv = serve(res, "127.0.0.1", 0)
    res.url = f"http://127.0.0.1:{srv.server_address[1]}"
    res.heartbeat()
    return res, srv


def _holder(box, **kw):
    """The holder of one device — one contact, two relays — with the token a worker gets, and its camera placed
    on it. Returns `(worker, camera id, device, the times the device was called)`."""
    con = VmsController(box.vars.as_writer("console", VMS.acl_console()), box.objects, wall=box.wall)
    cid = con.create_camera({"name": "door", "source": "driverpack://acme/10.0.0.90/ch/1"})["id"]
    box.objects.put(VMS.sub.heartbeat_key("w-1"), Heartbeat("w-1", box.wall(), [], {"server": "srv-a", "capacity": 50,
                                                                                    "headroom": 50}).to_bytes())
    if box.objects.get("platform/resources/srv-a/heartbeat") is None:
        box.objects.put("platform/resources/srv-a/heartbeat",
                        json.dumps({"server": "srv-a", "ts": box.wall(), "url": "http://srv-a", "units": {}}).encode())
    VmsController(box.vars.as_writer("vmscontroller", VMS.acl_controller()), box.objects, wall=box.wall).ensure_placed()
    dev = FakeDevice("acme/10.0.0.90", channels=["1"], rays=1, relays=2)
    called: list[float] = []
    real = dev.output
    dev.output = lambda *a, **k: (called.append(time.time()), real(*a, **k))[1]
    w = VmsWorker("w-1", box.vars.as_writer("vmsworker", WORKER_ACL), box.objects, FakeActuator(), clock=box.clock,
                  wall=box.wall, server="srv-a", env={}, archive_root=box.archive, device_factory=lambda key: dev, **kw)
    return w, cid, dev, called


def _evaluator(box, cid, index=None):
    """An evaluator holding one scenario: the contact of camera `cid` closes — its relay 2 is pulsed."""
    AutoController(box.vars.as_writer("console", AUTO_SPEC.acl_console()), box.objects, wall=box.wall).create(
        {"name": "door", "when": [{"sub": "vms", "kind": "io.input", "unit": str(cid)}], "within": 0,
         "then": [{"sub": "vms", "action": "output", "unit": str(cid), "port": 2, "pulse_ms": 500}], "rate_per_minute": 600})
    AutoController(box.vars.as_writer("autocontroller", AUTO_SPEC.acl_controller()), box.objects, wall=box.wall).assign("a-1", ["door"])
    return AutoWorker("a-1", box.vars.as_writer("autoworker", AUTO_SPEC.sub.acl_worker() + requests_acl("vms", "rec", "det")),
                      box.objects, index=index or MergedIndex(box.objects, wall=box.wall), clock=box.clock, wall=box.wall,
                      server="srv-a", archive_root=box.archive, env={})


def _site(env: dict, poll: float = 2.0):
    """One box, the real loops: a resource the evaluator's index asks over HTTP; the holder of a door device; an
    evaluator holding one scenario. Both loops run in threads with `poll` seconds between passes; `env` is what
    the two processes would have been started with. `fire()` posts the contact's event on the holder's bus and
    returns the road: from the moment the event was written to the moment the device was called."""
    box = _real_box()
    res, srv = _resource(box)
    holder, cid, dev, called = _holder(box)
    holder.reconcile_once()                                              # the device described: the scenario is checked against it
    # A line before the loops start: the watcher finds a unit's NEW epoch by listing directories once a second
    # (`longpoll.Watch`), so the first line a fresh epoch ever writes is noticed up to a second late — said in
    # lesson 25. The road measured here is the road of a camera that has been writing, as nearly all of them have.
    holder.observe(cid, "io.ready")
    evaluator = _evaluator(box, cid)
    evaluator.watch_events(env)                                          # what `__main__.autoworker` does before `run`
    stop = threading.Event()
    threads = [threading.Thread(target=holder.run, kwargs={"poll": poll, "stop": stop, "beat": commands_beat(env)}, daemon=True),
               threading.Thread(target=evaluator.run, kwargs={"poll": poll, "stop": stop}, daemon=True)]
    for t in threads:
        t.start()
    _until(lambda: str(cid) in holder.epochs and evaluator.status(), what="both loops to make their first pass")
    if evaluator.long_poll is not None:
        _until(lambda: res.watch.waiting() == 1, what="the evaluator's request to be held at the resource")
    seq = [0]

    def fire(timeout: float = 10.0) -> float:
        seq[0] += 1
        res.heartbeat()                                                  # the resource is alive for as long as the test runs
        before, seen = len(called), len(holder.observed)
        holder.actuator.post(cid, "io.input", port="1", value="closed", seq=seq[0])   # `seq`: another reading, not a repeat
        _until(lambda: len(called) > before, timeout, "the device to be called")
        written = next(t for c, t, kind in holder.observed[seen:] if kind == "io.input")
        return called[before] - written

    def close() -> None:
        stop.set()
        for t in threads:
            t.join(timeout=10)
        srv.shutdown()

    return types.SimpleNamespace(box=box, holder=holder, evaluator=evaluator, cid=cid, dev=dev, called=called,
                                 fire=fire, close=close, res=res, srv=srv, stop=stop)


# -- the road, end to end, with the real loops ------------------------------------------------------------------
def test_an_event_reaches_the_device_in_under_a_second_with_both_polls_left_at_two():
    """The holder writes the event; the resource answers the request the evaluator holds there; the evaluator's
    pass begins, and files the command; the holder's next look at its requests — a quarter of a second away at
    most — calls the device. `poll` is two seconds on both loops, and the device is called in a fraction of one.
    The holder says how long the road was in its heartbeat, the evaluator how it was woken."""
    site = _site(ON)
    try:
        road = site.fire()
        assert road < 1.0, f"the road took {road:.3f} s"
        _until(lambda: site.holder.commands["performed"] == 1, what="the command to be answered")
        assert site.dev.did == [("output", 2, "pulse", 500)]
        site.holder.heartbeat_once()
        hb = Heartbeat.from_bytes(site.box.objects.get(VMS.sub.heartbeat_key("w-1")))
        measured = hb.extra["command_road"]["auto"]                  # a scenario's request: automation's road
        assert measured["count"] == 1 and measured["sum"] < 1.0 and measured["ahead"] == measured["behind"] == 0
        assert measured["buckets"][VmsWorker.ROAD_BUCKETS.index(1.0)] == 1           # under a second, and the histogram shows it
        assert hb.extra["command_road"]["operator"]["count"] == 0
        filed = hb.extra["command_request"]["auto"]                  # from the row's filing: a part of the same road
        assert filed["count"] == 1 and filed["sum"] <= measured["sum"] + 0.01
        assert hb.extra["command_wait"]["count"] == 1 and hb.extra["command_wait"]["sum"] < 0.5
        site.evaluator.heartbeat_once()
        said = Heartbeat.from_bytes(site.box.objects.get(AUTO_SPEC.sub.heartbeat_key("a-1"))).extra
        assert said["woken"] >= 1 and said["early_passes"] >= 1 and said["waits"] >= 2 and said["wait_errors"] == 0
    finally:
        site.close()


def test_with_the_long_poll_and_the_beat_switched_off_the_event_takes_the_old_road_and_still_arrives():
    """`LONG_POLL=0` and `COMMANDS_BEAT=0` are the system as it was: no request is held at the resource, the
    holder looks at its requests on its pass only — and the event still reaches the device, by the two passes,
    in about the two seconds it always took. Nothing about either is in a heartbeat."""
    site = _site(OFF)
    try:
        assert site.evaluator.long_poll is None and site.evaluator.wake is None
        road = site.fire()
        assert 1.0 < road < 6.5, f"the old road is the evaluator's pass and then the holder's: {road:.3f} s"
        _until(lambda: site.holder.commands["performed"] == 1, what="the command to be answered")
        assert site.dev.did == [("output", 2, "pulse", 500)]
        assert site.res.watch.held == 0 and site.res.watch.stats == 0             # nobody asked the resource to watch
        site.evaluator.heartbeat_once()
        said = Heartbeat.from_bytes(site.box.objects.get(AUTO_SPEC.sub.heartbeat_key("a-1"))).extra
        assert not {"waits", "woken", "early_passes", "wait_errors"} & set(said)
    finally:
        site.close()


def test_a_resource_that_dies_mid_wait_leaves_the_evaluator_on_its_poll():
    """Nothing depends on the wait. The evaluator's request is held at a door that stops answering — here a door
    of its own beside the resource's, shut while the request is held: the request fails, is counted, and is asked
    again after a pause — and the event is found by the pass at the end of its two seconds, filed, and performed."""
    site = _site(ON)
    try:
        import socket as _socket
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        held = threading.Event()

        class Dying(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                held.set()
                self.connection.shutdown(_socket.SHUT_RDWR)          # the resource went, mid-answer

        dying = ThreadingHTTPServer(("127.0.0.1", 0), Dying)
        threading.Thread(target=dying.serve_forever, daemon=True).start()
        lp = site.evaluator.long_poll
        http = lp.fetch
        lp.fetch = lambda url, wants, timeout, since: http(f"http://127.0.0.1:{dying.server_address[1]}", wants, timeout, since)
        site.res.watch.close()                                       # the request held at the real door ends…
        _until(lambda: held.is_set(), what="the next request to go to the door that dies")   # …and the next one dies
        _until(lambda: lp.errors >= 1, what="the failed wait to be counted")
        early = site.evaluator.wake.early
        road = site.fire()
        assert 0.2 < road < 6.5, f"found by the evaluator's own pass: {road:.3f} s"
        assert site.evaluator.wake.early == early and site.dev.did == [("output", 2, "pulse", 500)]
        dying.shutdown()
    finally:
        site.close()


# -- the door's side: `GET /events/wait` --------------------------------------------------------------------------
def _ask(url: str, want: str, timeout: float, since=None, client_timeout: float = 40.0) -> dict:
    q = f"want={want}&timeout={timeout:g}" + (f"&since={since}" if since is not None else "")
    with urllib.request.urlopen(f"{url}/events/wait?{q}", timeout=client_timeout) as r:
        return json.loads(r.read())


def _asking(url: str, want: str, timeout: float, since=None):
    """A wait asked on a thread: `(thread, {"rep": the answer, "took": seconds})`."""
    out: dict = {}

    def ask():
        t0 = time.monotonic()
        try:
            out["rep"] = _ask(url, want, timeout, since)
        except Exception as e:                                       # noqa: BLE001
            out["error"] = e
        out["took"] = time.monotonic() - t0

    t = threading.Thread(target=ask, daemon=True)
    t.start()
    return t, out


def test_a_wait_with_nothing_happening_is_answered_unchanged_at_its_timeout():
    """A held request is answered `changed: false` when its `timeout` passes with nothing written — and a
    timeout longer than the door allows is cut to what it allows."""
    box = _real_box()
    res, srv = _resource(box)
    try:
        t0 = time.monotonic()
        rep = _ask(res.url, "vms/io.input", 0.5)
        assert rep["changed"] is False and "full" not in rep and 0.45 <= time.monotonic() - t0 < 1.5
        assert res.watch.waiting() == 0
        assert longpoll.WAIT_MAX == 30.0 and res.watch.wait([("vms", "io.input")], -5.0)["changed"] is False   # at once
    finally:
        srv.shutdown()


def test_a_line_of_a_wanted_kind_answers_the_wait_and_a_line_of_another_kind_does_not():
    """The wait names what it watches: `(subsystem, kind)` pairs. A line of another kind, or of that kind in
    another subsystem, leaves it held; a line of a wanted kind answers it within a tick or two — an observation
    or an alarm, which lies in a tree of its own. The answer says only that: the events are asked for as before."""
    box = _real_box()
    res, srv = _resource(box)
    try:
        log_ = EventLog(box.archive, "vms", "7", 1)
        log_.append(time.time(), "motion")                           # the unit exists before anybody waits
        t, out = _asking(res.url, "vms/io.input", 5.0)
        _until(lambda: res.watch.waiting() == 1, what="the request to be held")
        time.sleep(0.25)
        log_.append(time.time(), "motion")                           # the same unit, another kind
        EventLog(box.archive, "det", "7-io", 1).append(time.time(), "io.input")   # the kind, another subsystem
        time.sleep(0.5)
        assert t.is_alive() and "rep" not in out, "a line nobody asked about answered the wait"
        written = time.monotonic()
        log_.append(time.time(), "io.input", port="1", value="closed")
        t.join(timeout=3)
        assert out["rep"]["changed"] is True and time.monotonic() - written < 0.6
        assert set(out["rep"]) == {"changed", "seq", "touched"}      # a hint: nothing of the event is in it…
        assert out["rep"]["touched"] == ["vms/io.input/7"]           # …but which unit's kind it was (the seventh review)

        t, out = _asking(res.url, "vms/tamper,det/motion", 5.0, since=out["rep"]["seq"])
        _until(lambda: res.watch.waiting() == 1, what="the second request to be held")
        log_.append(time.time(), "tamper", ALARM)                    # an alarm: `vms.alarms/7/e1/…`
        t.join(timeout=3)
        assert out["rep"]["changed"] is True
    finally:
        srv.shutdown()


def test_a_line_written_between_two_waits_is_not_lost_between_them():
    """A reader that was answered asks again, and a line written in between would fall into the gap. The
    answer carries `seq`; the next request says `since`, and a wanted kind that changed after it is answered at
    once — also when nobody was waiting while it was written, for as long as the door remembers what it saw."""
    box = _real_box()
    res, srv = _resource(box)
    try:
        log_ = EventLog(box.archive, "vms", "7", 1)
        log_.append(time.time(), "motion")
        other_log = EventLog(box.archive, "det", "7-motion", 1)
        other_log.append(time.time(), "motion")
        t, out = _asking(res.url, "vms/io.input", 5.0)
        other, _ = _asking(res.url, "det/motion", 5.0)               # somebody else waits too, for another subsystem
        _until(lambda: res.watch.waiting() == 2)
        time.sleep(0.25)
        log_.append(time.time(), "io.input", n=1)
        t.join(timeout=3)
        seq = out["rep"]["seq"]
        log_.append(time.time(), "io.input", n=2)                    # written while the first reader is not waiting…
        time.sleep(0.4)                                              # …and looked at all the same: it was wanted a moment ago
        assert other.is_alive()
        t0 = time.monotonic()
        assert _ask(res.url, "vms/io.input", 5.0, since=seq)["changed"] is True and time.monotonic() - t0 < 0.3
        other_log.append(time.time(), "motion"); other.join(timeout=3)   # now nobody waits at all
        assert res.watch.waiting() == 0
        log_.append(time.time(), "io.input", n=3)
        time.sleep(0.3)                                              # inside `LINGER`: the sizes are remembered
        t0 = time.monotonic()
        assert _ask(res.url, "vms/io.input", 5.0, since=res.watch.seq)["changed"] is True and time.monotonic() - t0 < 0.6
    finally:
        srv.shutdown()


def test_the_seventeenth_waiter_is_answered_full_at_once_and_the_door_still_serves_events():
    """A held request must never be able to exhaust the door. `WAITERS_MAX` are held; one more is answered at
    once — `full`, and its sender falls back to its pass — and the queries the waits exist to speed up are
    answered as before: a wait takes none of their slots."""
    box = _real_box()
    res, srv = _resource(box)
    try:
        EventLog(box.archive, "vms", "7", 1).append(time.time(), "motion")
        assert longpoll.WAITERS_MAX == 16
        asked = [_asking(res.url, "vms/io.input", 8.0) for _ in range(16)]
        _until(lambda: res.watch.waiting() == 16, what="sixteen requests to be held")
        t0 = time.monotonic()
        rep = _ask(res.url, "vms/io.input", 8.0)
        assert rep["changed"] is False and rep["full"] is True and time.monotonic() - t0 < 0.5
        assert res.watch.full == 1 and res.watch.waiting() == 16
        with urllib.request.urlopen(f"{res.url}/events?from=0&to={time.time() + 1}&subsystem=vms", timeout=5) as r:
            assert [e["kind"] for e in json.loads(r.read())["events"]] == ["motion"]
        EventLog(box.archive, "vms", "7", 1).append(time.time(), "io.input")     # one line answers all sixteen
        for t, out in asked:
            t.join(timeout=3)
            assert out["rep"]["changed"] is True
        assert res.watch.waiting() == 0
    finally:
        srv.shutdown()


def test_with_nobody_waiting_the_watcher_looks_at_nothing():
    """The door notices a new line by looking at the files — and looks only while somebody waits. With a waiter:
    a stat per candidate file per tick. Without one: no thread, and not one stat, whatever is written."""
    box = _real_box()
    res, srv = _resource(box)
    try:
        for unit in ("1", "2", "3"):
            EventLog(box.archive, "vms", unit, 1).append(time.time(), "motion")
        assert res.watch.stats == 0 and res.watch._thread is None    # a resource nobody waits at
        _ask(res.url, "vms/io.input", 0.55)
        looked = res.watch.stats
        assert 3 <= looked <= 3 * 2 * 9, f"three units, a tick every 0.1 s for half a second: {looked} stats"
        _until(lambda: res.watch._thread is None, 1.0, "the watcher to stop with its last waiter")
        for unit in ("1", "2", "3"):
            EventLog(box.archive, "vms", unit, 1).append(time.time(), "io.input")
        time.sleep(0.5)
        assert res.watch.stats == looked and res.watch._thread is None
    finally:
        srv.shutdown()


def test_shutting_the_door_releases_the_waiters_and_a_client_that_left_is_dropped():
    """A resource that stops answers what it holds — `closed`, now — so no reader waits out its timeout on a
    door that is gone and no thread of the door outlives it. And a waiter whose client hung up is dropped
    within a second or so, not kept for the thirty it asked for."""
    import socket
    box = _real_box()
    res, srv = _resource(box)
    host, port = "127.0.0.1", srv.server_address[1]
    gone = socket.create_connection((host, port))
    gone.sendall(b"GET /events/wait?want=vms/io.input&timeout=30 HTTP/1.0\r\n\r\n")
    _until(lambda: res.watch.waiting() == 1, what="the request to be held")
    gone.close()                                                     # the client went away
    _until(lambda: res.watch.waiting() == 0, 3.0, "the waiter of a client that left to be dropped")

    asked = [_asking(res.url, "vms/io.input", 30.0) for _ in range(3)]
    _until(lambda: res.watch.waiting() == 3, what="three requests to be held")
    t0 = time.monotonic()
    srv.shutdown()
    for t, out in asked:
        t.join(timeout=3)
        assert out["rep"]["changed"] is False and out["rep"]["closed"] is True
    assert time.monotonic() - t0 < 3.0 and res.watch.waiting() == 0
    assert res.watch.wait([("vms", "io.input")], 5.0) == {"changed": False, "closed": True, "seq": res.watch.seq}


# -- the reader's side: the gap, and the lease step ---------------------------------------------------------------
def test_a_flood_of_changes_is_one_early_pass_per_gap_and_the_lease_step_stays_on_its_clock():
    """Events of a watched kind written a hundred times a second are four passes a second: an early pass begins
    no sooner than `WAKE_GAP` after the previous one began. And the steps that are by the clock stay by the
    clock: the leases are renewed every `lease_every` seconds — neither starved by passes nor once per early
    pass — and the heartbeat goes out once per `poll`, not once per early pass."""
    box = _real_box()
    res, srv = _resource(box)
    _holder(box)                                                     # the camera the scenario names exists
    evaluator = _evaluator(box, 1)
    evaluator.lease_ttl, evaluator.lease_margin = 6.0, 3.0           # the lease step every second
    evaluator.watch_events(ON)
    passes: list[float] = []
    leased: list[float] = []
    beats: list[float] = []
    reconcile_once, lease_pass, heartbeat_once = evaluator.reconcile_once, evaluator.lease_pass, evaluator.heartbeat_once
    evaluator.reconcile_once = lambda *a, **k: (passes.append(time.monotonic()), reconcile_once(*a, **k))[1]
    evaluator.lease_pass = lambda: (leased.append(time.monotonic()), lease_pass())[1]
    evaluator.heartbeat_once = lambda: (beats.append(time.monotonic()), heartbeat_once())[1]
    stop = threading.Event()
    thread = threading.Thread(target=evaluator.run, kwargs={"poll": 2.0, "stop": stop}, daemon=True)
    thread.start()
    try:
        _until(lambda: res.watch.waiting() == 1, what="the evaluator's request to be held")
        log_ = EventLog(box.archive, "vms", "1", 1)
        t0, n0, flooded = time.monotonic(), len(passes), 3.6
        while time.monotonic() - t0 < flooded:
            log_.append(time.time(), "io.input", port="1", value="closed")
            time.sleep(0.01)
        flood = [p for p in passes[n0:] if p - t0 <= flooded]
        took = time.monotonic() - t0
        assert 5 <= len(flood) <= took / longpoll.WAKE_GAP + 1, f"{len(flood)} passes in {took:.2f} s of flood"
        assert all(b - a >= longpoll.WAKE_GAP - 0.01 for a, b in zip(flood, flood[1:])), "two passes closer than the gap"
        gaps = [b - a for a, b in zip(leased, leased[1:])]
        assert len(leased) >= 2 and all(1.0 <= g <= 1.0 + 2 * longpoll.WAKE_GAP + 0.3 for g in gaps), f"lease steps {gaps}"
        said = [b for b in beats if t0 <= b <= t0 + flooded]
        assert 1 <= len(said) <= 3 and all(b - a >= 2.0 for a, b in zip(said, said[1:])), f"heartbeats in the flood: {said}"
        assert evaluator.may_write("door") and evaluator.long_poll.woken >= 5
    finally:
        stop.set(); thread.join(timeout=10); srv.shutdown()


def test_the_wait_is_the_poll_when_nothing_arrives_and_stop_ends_it_at_once():
    """`wait_next` is `stop.wait(poll)` with one more way to end. It returns at the poll when nothing arrives, at
    once when `stop` is set, early when the wake is set — but not sooner than the gap after the last pass began;
    and a worker that never asked for the long poll waits by `stop` alone, as every loop did."""
    box = Box()
    w = Worker(Subsystem("thing"), "t-1", box.vars, box.objects)
    stop = threading.Event()
    t0 = time.monotonic()
    assert w.wait_next(0.2, stop) is False and 0.19 <= time.monotonic() - t0 < 0.6      # no wake: `stop.wait(poll)`
    assert w.poll_events(lambda: {}, {"LONG_POLL": "0"}) is None and w.wake is None
    assert w.poll_events(lambda: {}, {}) is not None
    t0 = time.monotonic()
    assert w.wait_next(0.3, stop) is False and 0.29 <= time.monotonic() - t0 < 0.7      # nothing arrived
    w.wake.set()                                                                        # set while the "pass" runs
    t0 = time.monotonic()
    assert w.wait_next(5.0, stop) is True and longpoll.WAKE_GAP - 0.02 <= time.monotonic() - t0 < 1.0   # early, after the gap
    time.sleep(0.3)
    w.wake.set()
    t0 = time.monotonic()
    assert w.wait_next(5.0, stop) is True and time.monotonic() - t0 < 0.1               # the gap has passed: at once
    assert w.wake.early == 2
    threading.Timer(0.1, stop.set).start()
    t0 = time.monotonic()
    assert w.wait_next(5.0, stop) is False and time.monotonic() - t0 < 1.0              # stopped: not five seconds
    assert w.wake.early == 2


def test_a_resource_with_no_room_or_no_such_route_costs_a_pause_and_never_a_pass():
    """`full`, an error, a resource of a build that has no `/events/wait`: each is counted and followed by a
    pause before the next request — never a wake, and never anything raised into the loop. A resource that left
    the list is not asked again; one that joined it is asked from the next pass."""
    asked: list[tuple] = []
    answers = {"http://a": [{"changed": False, "full": True, "seq": 0}], "http://b": [OSError("refused")],
               "http://c": [{"changed": True, "seq": 4}, {"changed": False, "seq": 4}]}

    def fetch(url, wants, timeout, since):
        asked.append((url, tuple(wants), since))
        rep = answers[url].pop(0) if answers[url] else {"changed": False, "seq": 9}
        if isinstance(rep, Exception):
            raise rep
        if not rep.get("changed") and not rep.get("full"):
            time.sleep(0.05)
        return rep

    wake = longpoll.Wake()
    resources = {"a": "http://a", "b": "http://b"}
    lp = longpoll.LongPoll(wake, lambda: resources, lambda: [("vms", "io.input")], backoff=0.2, fetch=fetch)
    lp.sync()
    _until(lambda: lp.errors == 2, 2.0, "both refusals to be counted")
    assert not wake.event.is_set() and lp.woken == 0
    resources.pop("a"); resources["c"] = "http://c"
    lp.sync()
    _until(lambda: lp.woken == 1 and wake.event.is_set(), 2.0, "the answer of the resource that joined")
    _until(lambda: ("http://c", (("vms", "io.input"),), 4) in asked, 2.0, "the next request to carry `since`")
    time.sleep(0.5)
    assert [a for a in asked if a[0] == "http://a"] == [("http://a", (("vms", "io.input"),), None)]   # asked once, then gone
    lp.resources = lambda: (_ for _ in ()).throw(OSError("the store is away"))
    lp.sync()                                                        # never raises: the list as it was
    lp.close()


# -- the holder: a look every beat, and the row still decides -----------------------------------------------------
def _looping(beat: float = COMMANDS_BEAT, poll: float = 2.0, **kw):
    """A holder alone, its loop in a thread."""
    box = _real_box()
    holder, cid, dev, called = _holder(box, **kw)
    stop = threading.Event()
    thread = threading.Thread(target=holder.run, kwargs={"poll": poll, "stop": stop, "beat": beat}, daemon=True)
    thread.start()
    _until(lambda: str(cid) in holder.epochs and holder.passes >= 1 and holder.device_of_row(holder.rows[0]) is not None,
           what="the holder's first pass")

    def close() -> None:
        stop.set(); thread.join(timeout=10)

    def command(rid: str) -> float:
        now = time.time()
        box.vars.put(f"vms/requests/{rid}", {"unit": str(cid), "action": "output", "port": "2", "at": str(now),
                                             "by": "operator", "valid_until": str(now + 30)})
        return now

    return types.SimpleNamespace(box=box, holder=holder, cid=cid, dev=dev, called=called, close=close, command=command)


def test_a_command_is_performed_within_a_beat_and_only_on_the_pass_when_the_beat_is_off():
    """Between two passes the holder looks at its request rows every `COMMANDS_BEAT` — the same `requests`, with
    every rule it has. A command filed right after a pass is performed within a beat, not at the next pass two
    seconds on; with `COMMANDS_BEAT=0` it waits for the pass, as it always did. A beat is not a pass: the
    assignment is not read again, and the heartbeat and the lease step stay where they were."""
    assert commands_beat({}) == 0.25 and commands_beat({"COMMANDS_BEAT": "0"}) == 0.0 and commands_beat({"COMMANDS_BEAT": "0.5"}) == 0.5
    one = _looping()
    try:
        beats: list[float] = []
        leased: list[float] = []
        heartbeat_once, lease_pass = one.holder.heartbeat_once, one.holder.lease_pass
        one.holder.heartbeat_once = lambda: (beats.append(time.monotonic()), heartbeat_once())[1]
        one.holder.lease_pass = lambda: (leased.append(time.monotonic()), lease_pass())[1]
        passes = one.holder.passes
        filed = one.command("r1")
        _until(lambda: one.called, 1.0, "the command to be performed on a beat")
        assert one.called[0] - filed < 0.6 and one.holder.passes == passes           # no pass was made for it
        _until(lambda: one.holder.passes >= passes + 2, what="two more passes")
        assert beats == [] and len(leased) <= 1                                      # ten seconds, eight seconds: not yet
        assert one.holder.wait["count"] == 1 and one.holder.road["operator"]["sum"] < 0.6
    finally:
        one.close()

    off = _looping(beat=0.0)
    try:
        time.sleep(0.3)                                              # well inside the wait between two passes
        passes = off.holder.passes
        filed = off.command("r1")
        time.sleep(0.8)
        assert off.called == [] and off.holder.passes == passes     # nothing looks until the pass
        _until(lambda: off.called, 3.0, "the command to be performed on the pass")
        assert off.called[0] - filed > 0.8 and off.holder.passes == passes + 1
    finally:
        off.close()


def test_a_devices_event_is_a_line_within_a_beat_and_only_on_the_pass_when_the_beat_is_off():
    """What a device posts on its bus becomes an event when the holder drains the bus — and that was the pass: up
    to `poll` seconds before any scenario could see it, a part of the road no histogram measured, because the
    event's time is stamped when it is drained. Every beat drains the bus now (`drain_bus`, as the product does in
    its loop of commands); with `COMMANDS_BEAT=0` the event waits for the pass, as it always did."""
    for beat, within in ((COMMANDS_BEAT, 0.6), (0.0, None)):
        one = _looping(beat=beat)
        try:
            seen: list[float] = []
            observe = one.holder.observe
            one.holder.observe = lambda cid, kind, **f: (seen.append(time.monotonic()) if kind == "io.input" else None,
                                                         observe(cid, kind, **f))[1]
            time.sleep(0.3)                                          # well inside the wait between two passes
            passes = one.holder.passes
            posted = time.monotonic()
            one.holder.actuator.post(one.cid, "io.input", port="1", state="on")
            if within is not None:
                _until(lambda: seen, 1.0, "the event to be drained on a beat")
                assert seen[0] - posted < within and one.holder.passes == passes     # no pass was made for it
            else:
                time.sleep(0.8)
                assert seen == [] and one.holder.passes == passes                     # nothing drains until the pass
                _until(lambda: seen, 3.0, "the event to be drained on the pass")
        finally:
            one.close()


def test_a_fenced_holder_on_a_beat_does_not_act():
    """A look between passes does not make the request the holder's to perform. A holder whose lease on the unit
    is lost — another instance took the next epoch — looks at the row four times a second and leaves it for
    whoever holds the device now: the lease decides, on a beat as on a pass."""
    from w2cplatform.epoch import next_epoch
    one = _looping()
    try:
        holder, unit = one.holder, str(one.cid)
        assert holder.may_write(unit)
        looks: list[float] = []
        requests = holder.requests
        holder.requests = lambda *a, **k: (looks.append(time.monotonic()), requests(*a, **k))[1]
        next_epoch(one.box.vars, VMS.sub.epoch_key(unit))            # somebody else was given the device
        assert holder.leases[unit].renew() is False and not holder.may_write(unit)   # …and this holder knows it
        one.command("r1")
        _until(lambda: len(looks) >= 3, 1.5, "three looks at the requests")
        assert one.called == [] and one.dev.did == []
        assert holder.commands == {"performed": 0, "refused": 0, "expired": 0, "unknown": 0} and holder.fetched == []
        assert one.box.vars.get("vms/requests/r1")[0] is not None    # the row stands, for the holder that may
    finally:
        one.close()


def test_a_store_that_does_not_answer_on_a_beat_is_waited_out_and_said_once():
    """Four looks a second at a store that is away would be four warnings a second. A beat the store did not
    answer is counted and said once per outage; the beats go on, and the first one answered says so. The loop
    is not disturbed: its pass, lease step and heartbeat are in tries of their own."""
    import logging
    box = Box()
    holder, cid, dev, called = _holder(box)
    holder.reconcile_once()
    said: list[str] = []

    class Catch(logging.Handler):
        def emit(self, record): said.append(record.getMessage())

    handler = Catch()
    logging.getLogger("vmsworker").addHandler(handler)
    try:
        real = holder.vars.list
        away = {"on": True}
        holder.vars.list = lambda prefix: (_ for _ in ()).throw(OSError("the store is away")) if away["on"] else real(prefix)
        for _ in range(8):
            holder.beat_once()                                       # two seconds of beats
        assert holder.store_errors == 1 and len([m for m in said if "between passes" in m]) == 1
        away["on"] = False
        now = box.wall()
        box.vars.put("vms/requests/r1", {"unit": str(cid), "action": "output", "port": "2", "at": str(now),
                                         "by": "operator", "valid_until": str(now + 30)})
        holder.beat_once()
        assert dev.did == [("output", 2, "pulse", 0)] and holder.store_errors == 1
        assert [m for m in said if "between passes" in m][-1].endswith("the requests are read between passes again")
        away["on"] = True
        holder.beat_once(); holder.beat_once()
        assert holder.store_errors == 2                              # another outage: counted again, once
    finally:
        logging.getLogger("vmsworker").removeHandler(handler)


# -- the road, measured where it ends -------------------------------------------------------------------------
def test_the_holder_measures_the_road_by_two_clocks_and_its_own_link_by_one():
    """The whole road — the event's moment to the device call — compares two machines' clocks; so does the request's
    own road, from the row's filing (`filed`; an operator's row: its `at`) to the call; and the holder's own link is a
    third histogram, from its first sight of the row to the call, by its monotonic clock alone. The first two are
    split by who asked — `auto` for a scenario, `operator` for a person (the review's seventh pass) — and a clock
    skew is counted in both directions: AHEAD, a moment after ours, is a road of zero; BEHIND, a filing before our
    previous listing that did not have the row. After a restart the request's road is measured from its filing, not
    zero. All of it leaves in the heartbeat and is on the console's `/metrics`."""
    from vms.console import vms_metrics
    box = Box()
    holder, cid, dev, _called = _holder(box)
    holder.reconcile_once()
    now = box.wall()

    def put(rid, at, by="auto/door", filed=None):
        box.vars.put(f"vms/requests/{rid}", {"unit": str(cid), "action": "output", "port": "1", "at": str(at), "by": by,
                                             "valid_until": str(now + 30), **({"filed": str(filed)} if filed is not None else {})})

    holder.requests()                                                # a listing with nothing in it: "before" for what follows
    put("a", now - 0.2, filed=now - 0.1)                             # an event a fifth of a second ago, filed a tenth ago
    holder.requests()
    auto = holder.road["auto"]
    assert auto["count"] == 1 and round(auto["sum"], 3) == 0.2 and auto["ahead"] == 0
    assert auto["buckets"] == [0, 1, 1, 1, 1, 1, 1, 1, 1, 1]         # cumulative: 0.25 s and every bucket above it
    assert holder.request_road["auto"]["count"] == 1 and round(holder.request_road["auto"]["sum"], 3) == 0.1
    assert holder.wait["count"] == 1 and holder.wait["sum"] == 0.0   # seen and called in the same look
    put("b", now + 3.0, filed=now + 3.0)                             # the writer's clock is three seconds ahead
    holder.requests()
    assert auto["count"] == 2 and round(auto["sum"], 3) == 0.2 and auto["ahead"] == 1
    assert holder.request_road["auto"]["ahead"] == 1
    # the writer's clock is BEHIND: it says it filed the row ten seconds before our last listing, which did not have it
    box.wall.advance(1.0)
    put("late-clock", now - 30, filed=now - 10)
    holder.requests()
    assert holder.request_road["auto"]["behind"] == 1 and auto["behind"] == 0     # the event's road cannot tell
    # an operator's click: its own histograms, measured from its `at`, which is its filing
    put("click", box.wall() - 0.5, by="alice")
    holder.requests()
    assert holder.road["operator"]["count"] == 1 and holder.request_road["operator"]["count"] == 1
    assert auto["count"] == 3
    # the holder's own link: the device is busy when the row is first seen, and free a second and a half later
    put("c", box.wall() - 0.75, filed=box.wall() - 0.5)
    busy = {"rid": "x", "row": holder.rows[0], "it": {}, "at": box.clock(), "returned": threading.Event(), "answered": True}
    holder._performing[id(dev)] = busy
    holder.requests()
    assert holder.wait["count"] == 4                                 # not called: the device has a call in flight
    box.clock.advance(1.5); box.wall.advance(1.5)
    busy["returned"].set()
    holder.requests()
    assert holder.wait["count"] == 5 and holder.wait["sum"] == 1.5
    assert round(holder.request_road["auto"]["sum"], 3) == round(0.1 + 0 + 11.0 + 2.0, 3)

    holder.heartbeat_once()
    con = VmsController(box.vars.as_writer("console", VMS.acl_console()), box.objects, wall=box.wall)
    text = "\n".join(vms_metrics(con)())
    for line in ('vms_event_to_device_seconds_bucket{worker="w-1",by="auto",le="0.25"} 2',
                 'vms_event_to_device_seconds_count{worker="w-1",by="auto"} 4',
                 'vms_event_to_device_seconds_count{worker="w-1",by="operator"} 1',
                 'vms_event_to_device_skewed_total{worker="w-1",by="auto",direction="ahead"} 1',
                 'vms_request_to_device_skewed_total{worker="w-1",by="auto",direction="behind"} 1',
                 'vms_request_to_device_seconds_count{worker="w-1",by="auto"} 4',
                 'vms_request_seen_to_device_seconds_bucket{worker="w-1",le="1"} 4',
                 'vms_request_seen_to_device_seconds_sum{worker="w-1"} 1.5'):
        assert line in text, line

    # a holder started again: a standing row first seen at its call is not a road of zero — it was filed long ago
    holder.release_slot()                                            # an orderly stop; the next instance takes the name
    again = VmsWorker("w-1", box.vars.as_writer("vmsworker", WORKER_ACL), box.objects, FakeActuator(), clock=box.clock,
                      wall=box.wall, server="srv-a", env={}, archive_root=box.archive, device_factory=lambda key: dev)
    again.reconcile_once()
    put("d", box.wall() - 4.0, filed=box.wall() - 4.0)
    again.requests()
    assert again.wait["sum"] == 0.0 and round(again.request_road["auto"]["sum"], 3) == 4.0
    assert again.reanswered == 5 and again.commands["unknown"] == 0  # the five answered before are said again, quietly


def test_the_evaluator_asks_for_the_kinds_its_scenarios_watch_and_says_how_it_was_woken():
    """`wants` is the `(subsystem, kind)` of every trigger of every scenario the evaluator holds, as of its last
    pass — a scenario switched off watches nothing. The resources it holds a request at are the ones its index
    asks: live by their heartbeats, at the address `/events` is asked at. And how the long poll went is in its
    heartbeat and on the console's `/metrics` — where a wait that fails, and breaks nothing, is seen."""
    from tests.test_autoworker import _Log, _assigned, _scenario, _worker, ev
    from vms.console import auto_metrics
    box = Box()
    t = box.wall()
    log = _Log([ev(t - 20, "det", "7-motion", "motion"), ev(t - 5, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box); _assigned(box, "door-on-badge")
    w = _worker(box, log)
    assert w.wants() == [] and w._resources() == {}                  # before its first pass; and a fake index keeps no list
    assert w.reconcile_once() == ["door-on-badge"]
    assert w.wants() == [("det", "motion", "7-motion"), ("vms", "io.input", "12")]   # the unit is in the want (M8)
    con = AutoController(box.vars.as_writer("console", AUTO_SPEC.acl_console()), box.objects, wall=box.wall)
    w.heartbeat_once()
    assert "auto_waits_total{" not in "\n".join(auto_metrics(con)())                 # the long poll was not asked for

    w.index = MergedIndex(box.objects, fetch=lambda url, params: {"events": []}, wall=box.wall)
    for server, age in (("srv-a", 1), ("srv-b", 100)):               # one live resource, one silent
        box.objects.put(f"platform/resources/{server}/heartbeat",
                        json.dumps({"server": server, "ts": box.wall() - age, "url": f"http://{server}:8090"}).encode())
    assert w._resources() == {"srv-a": "http://srv-a:8090"}
    lp = w.watch_events({})
    lp.fetch = lambda url, wants, timeout, since: {"changed": False, "full": True, "seq": 0}
    lp.backoff = 30.0
    lp.sync()
    _until(lambda: lp.errors == 1, 2.0, "the refused wait to be counted")
    w.heartbeat_once()
    text = "\n".join(auto_metrics(con)())
    for line in ('auto_waits_total{worker="a-1"} 1', 'auto_woken_total{worker="a-1"} 0',
                 'auto_early_passes_total{worker="a-1"} 0', 'auto_wait_errors_total{worker="a-1"} 1'):
        assert line in text, line
    lp.close()
    con.update("door-on-badge", {"enabled": False})
    w.reconcile_once()
    assert w.wants() == []


# -- the cost of the fast path (the review's seventh pass, part 1: M5–M8 and the long poll's minors) ----------------------
def _counting(holder) -> list:
    """Every read of a request row the holder makes, by key."""
    reads: list[str] = []
    get = holder.vars.get
    holder.vars.get = lambda key: (reads.append(key) if "/requests/" in key else None, get(key))[1]
    return reads


def test_a_holder_reads_a_request_row_once_and_another_holders_rows_never_again():
    """M5. Every beat listed the requests of the whole cluster and READ every row — another holder's, one answered
    already — before asking whether it was its own: twenty holders over two hundred standing rows were 16 000 reads of
    the store a second, and 1000 rows were 30 ms of every beat. The unit a row names is remembered by its key now, and
    "answered" and "in flight" are asked before any read: a row is read once, when it appears."""
    box = Box()
    holder, cid, dev, _called = _holder(box)
    holder.reconcile_once()
    now = box.wall()
    for i in range(1000):                                            # a thousand rows of other holders' devices
        box.vars.put(f"vms/requests/other-{i:04d}", {"unit": "999", "action": "output", "port": "1",
                                                     "valid_until": str(now + 300)})
    box.vars.put("vms/requests/mine", {"unit": str(cid), "action": "output", "port": "1", "valid_until": str(now + 300)})
    reads = _counting(holder)
    holder.requests()
    assert len(reads) == 1001 and dev.did == [("output", 1, "pulse", 0)]     # each row once: they are new
    del reads[:]
    t0 = time.perf_counter()
    for _ in range(4):
        holder.requests()                                            # a second of beats
    after = (time.perf_counter() - t0) / 4
    assert reads == [] and len(dev.did) == 1                         # nothing read again, mine not performed again
    # what a beat cost before: every row read again
    t0 = time.perf_counter()
    for _ in range(4):
        holder._requests_read.clear()
        holder.requests()
    before = (time.perf_counter() - t0) / 4
    assert len(reads) == 4 * 1000 and after < before / 3, f"a beat over 1000 rows: {after * 1000:.1f} ms, was {before * 1000:.1f} ms"
    box.vars.put("vms/requests/new", {"unit": str(cid), "action": "output", "port": "2", "valid_until": str(now + 300)})
    del reads[:]
    holder.requests()
    assert reads == ["vms/requests/new"] and dev.did[-1] == ("output", 2, "pulse", 0)   # a new row: read, and performed


def _commands_at(box, holder, cid, con, rate: float, seconds: float, beat: float = 0.25, start: int = 0):
    """`rate` commands a second for `seconds`, by the box's clocks: the holder looks every `beat`, heartbeats every
    ten seconds (and renews its leases), the console clears every `CLEAR_EVERY` — as the processes do. Returns the standing rows after each
    beat, and the next request number."""
    from vms.jobs import CLEAR_EVERY, clear_requests
    standing, owed, n, t = [], 0.0, start, 0.0
    last_hb = last_clear = -1e9
    while t < seconds:
        owed += rate * beat
        while owed >= 1.0:
            owed -= 1.0
            n += 1
            box.vars.put(f"vms/requests/c-{n:05d}", {"unit": str(cid), "action": "output", "port": "1", "at": str(box.wall()),
                                                     "by": "auto/door", "valid_until": str(box.wall() + 30), "filed": str(box.wall())})
        holder.requests()
        if t - last_hb >= 10.0:
            holder.lease_pass(); holder.heartbeat_once(); last_hb = t   # the lease step, at least as often
        if t - last_clear >= CLEAR_EVERY:
            clear_requests(con, sweep=False); last_clear = t
        standing.append(len(box.vars.list("vms/requests/")))
        box.clock.advance(beat); box.wall.advance(beat); t += beat
    return standing, n


def test_at_three_commands_a_second_the_rows_stay_bounded_and_a_restart_declares_nothing_failed():
    """M6. The answers left in the heartbeat 32 at a time, every ten seconds, and the console cleared once every thirty:
    about one row a second, while the beat lets a holder answer sixteen. At three commands a second the standing rows
    went 45 → 174 and on; and a holder started again on 69 standing rows it had performed answered 53 `unknown` with a
    `command.failed` each — a scenario may fire on that — and 16 `expired`. Now every answer leaves, oldest first,
    under `FETCHED_BYTES`; the console clears every `CLEAR_EVERY` without reading a row; and a mark says how its call
    went, so the next instance of the slot says the answer again instead of calling it unknown. A minute at three a
    second, then the holder dies and is replaced: the rows stay bounded, and not one command is declared failed."""
    import inspect
    import vms.__main__ as m
    from vms.jobs import clear_requests
    assert "_clear_loop" in inspect.getsource(m.console) and "clear_requests(" in inspect.getsource(m._clear_loop)
    box = Box()
    holder, cid, dev, _called = _holder(box)
    holder.reconcile_once()
    con = VmsController(box.vars.as_writer("console", VMS.acl_console()), box.objects, wall=box.wall)
    standing, n = _commands_at(box, holder, cid, con, rate=3.0, seconds=60.0)
    assert n == 180 and len(dev.did) == 180 and holder.commands["performed"] == 180
    late = standing[len(standing) // 2:]                             # the second half of the minute: no growth
    assert max(late) <= 3 * (10 + 2) + 4, f"standing rows in the second half of the minute: {max(late)}"
    assert max(standing[-40:]) <= max(standing[40:80]) + 4, f"the rows grow: {standing[40:80]} … {standing[-40:]}"
    assert len(holder.fetched_said()) <= VmsWorker.FETCHED_BYTES
    # …the holder dies here, between two heartbeats, its last answers unsaid; its slot lapses and a new one takes it
    left = len(box.vars.list("vms/requests/"))
    assert left > 0
    box.clock.advance(46.0); box.wall.advance(46.0)                   # past `valid_until` too: performed is not expired
    again = VmsWorker("w-1", box.vars.as_writer("vmsworker", WORKER_ACL), box.objects, FakeActuator(), clock=box.clock,
                      wall=box.wall, server="srv-a", env={}, archive_root=box.archive, device_factory=lambda key: dev)
    assert again.name == "w-1" and again.instance != holder.instance
    again.reconcile_once()
    for _ in range(4):
        again.requests()
    assert again.commands == {"performed": 0, "refused": 0, "expired": 0, "unknown": 0}
    assert "command.failed" not in [k for _, _, k in again.observed] and len(dev.did) == 180    # nothing failed, nothing twice
    assert again.reanswered == left
    again.heartbeat_once()
    assert clear_requests(con, sweep=False) == left and box.vars.list("vms/requests/") == []
    # and the review's own split, read back from the mark: a call that never came back is still `unknown`
    box.objects.put("vms/commands/c-99999", json.dumps({"instance": "gone:1:abc", "slot": "w-1", "unit": str(cid)}).encode())
    box.vars.put("vms/requests/c-99999", {"unit": str(cid), "action": "output", "port": "1", "valid_until": str(box.wall() + 30)})
    again.requests()
    assert again.commands["unknown"] == 1                            # no answer in the mark: not known, said so


def test_a_hundred_hung_devices_of_two_hundred_delay_neither_a_fast_command_nor_the_lease():
    """M7. Each call into a device was waited for `PERFORM_GRACE` in turn, and `budget` counted only answers: 200
    devices commanded at once, 100 of them hung for 30 s, held the loop's thread 24.7 s — a fast command waited 7 s and
    the lease went 13.9 s unrenewed. Now a look waits for its calls together, a fifth of a second however many hang,
    within `REQUESTS_HOLD`; a call begun counts in the budget; a device that did not answer is not waited for again.
    The real loop, 200 devices, every one commanded at once and half of them hung: the lease step keeps its rhythm,
    and a fast command filed behind the whole burst is called within a look, a lease step and a beat — under a second
    and a half on this file store, whose create-only mark is most of a command's cost; it was seven."""
    box = _real_box()
    con = VmsController(box.vars.as_writer("console", VMS.acl_console()), box.objects, wall=box.wall)
    cams = [con.create_camera({"name": f"d{i}", "source": f"driverpack://acme/10.0.{i // 250}.{i % 250}/ch/1"})["id"]
            for i in range(VmsWorker.HUNG_DEVICES + 1)]                # the last one: the fast command's, not in the burst
    box.objects.put(VMS.sub.heartbeat_key("w-1"), Heartbeat("w-1", box.wall(), [], {"server": "srv-a", "capacity": 250,
                                                                                    "headroom": 250}).to_bytes())
    box.objects.put("platform/resources/srv-a/heartbeat",
                    json.dumps({"server": "srv-a", "ts": box.wall(), "url": "http://srv-a", "units": {}}).encode())
    VmsController(box.vars.as_writer("vmscontroller", VMS.acl_controller()), box.objects, wall=box.wall).ensure_placed()
    gate = threading.Event()
    hung = {f"acme/10.0.{i // 250}.{i % 250}" for i in range(0, VmsWorker.HUNG_DEVICES, 2)}
    called: dict[str, float] = {}

    def device(key):
        dev = FakeDevice(key, channels=["1"], rays=1, relays=2)
        real = dev.output

        def output(*a, **k):
            if key in hung:
                gate.wait(30)                                        # the network went with the session still held
            called[key] = time.monotonic()
            return real(*a, **k)
        dev.output = output
        return dev

    holder = VmsWorker("w-1", box.vars.as_writer("vmsworker", WORKER_ACL), box.objects, FakeActuator(), clock=box.clock,
                       wall=box.wall, server="srv-a", env={}, archive_root=box.archive, device_factory=device,
                       lease_ttl=6.0, lease_margin=3.0)                # the lease step every second
    leased: list[float] = []
    lease_pass = holder.lease_pass
    holder.lease_pass = lambda: (leased.append(time.monotonic()), lease_pass())[1]
    stop = threading.Event()
    thread = threading.Thread(target=holder.run, kwargs={"poll": 1.0, "stop": stop, "beat": COMMANDS_BEAT}, daemon=True)
    thread.start()
    try:
        _until(lambda: len(holder.epochs) == len(cams) and holder.passes >= 1, 60.0, "every camera started")
        now = time.time()
        for i, cid in enumerate(cams[:-1]):
            box.vars.put(f"vms/requests/burst-{i:03d}", {"unit": str(cid), "action": "output", "port": "1", "at": str(now),
                                                         "by": "auto/x", "valid_until": str(now + 30)})
        time.sleep(0.5)
        n = len(cams) - 1
        fast = f"acme/10.0.{n // 250}.{n % 250}"
        filed = time.monotonic()                                     # last in the order of keys: behind the whole burst
        box.vars.put("vms/requests/z-fast", {"unit": str(cams[-1]), "action": "output", "port": "2", "at": str(time.time()),
                                             "by": "operator", "valid_until": str(time.time() + 30)})
        _until(lambda: fast in called, 5.0, "the fast command to be performed")
        assert called[fast] - filed < 1.5, f"the fast command waited {called[fast] - filed:.2f} s"
        _until(lambda: len([k for k in called if k not in hung]) == len(cams) - len(hung), 10.0, "every free device called")
        mark = len(leased)
        time.sleep(4.0)
        gaps = [b - a for a, b in zip(leased[mark - 1:], leased[mark:])]
        assert len(gaps) >= 2 and max(gaps) <= 1.0 + 3 * VmsWorker.REQUESTS_HOLD + 0.5, f"lease steps {gaps}"
        slow = {id(d) for k, d in holder.devices.items() if k in hung}
        assert holder._slow and holder._slow <= slow                 # what is not waited for is what did not answer
        assert all(holder.may_write(str(c)) for c in cams)
    finally:
        gate.set()
        stop.set(); thread.join(timeout=20)


def test_an_evaluator_is_woken_by_the_units_it_watches_and_its_early_pass_reads_only_what_was_touched():
    """M8. The want named a kind and not a unit, so an `io.input` on camera 777 twenty times a second woke every
    evaluator with a scenario on ANY camera's contact, twenty early passes in six seconds, each over every scenario —
    on a site with one busy camera, eight times the queries of the ordinary pass, for ever. The unit is in the want now,
    the resource says which of the wanted units changed, and the early pass evaluates the scenarios those touch, and
    reads no other scenario's row; the ordinary pass over all of them still comes every `poll`."""
    box = _real_box()
    res, srv = _resource(box)
    holder, cid, _dev, _called = _holder(box)
    holder.reconcile_once()
    evaluator = _evaluator(box, cid)                                 # "door": camera `cid`'s contact
    gate = VmsController(box.vars.as_writer("console", VMS.acl_console()), box.objects, wall=box.wall).create_camera(
        {"name": "gate", "source": "driverpack://acme/10.0.0.91/ch/1"})["id"]
    assert str(gate) == "2"
    AutoController(box.vars.as_writer("console", AUTO_SPEC.acl_console()), box.objects, wall=box.wall).create(
        {"name": "other", "when": [{"sub": "vms", "kind": "io.input", "unit": "2"}], "within": 0,
         "then": [{"sub": "vms", "action": "output", "unit": str(cid), "port": 1, "pulse_ms": 100}], "rate_per_minute": 600})
    AutoController(box.vars.as_writer("autocontroller", AUTO_SPEC.acl_controller()), box.objects, wall=box.wall).assign(
        "a-1", ["door", "other"])
    passes: list[tuple] = []                                         # (what the pass was told was touched, what it evaluated)
    current: list = []
    evaluate, reconcile_once = evaluator.evaluate, evaluator.reconcile_once
    evaluator.evaluate = lambda row, now: (current.append(str(row["id"])), evaluate(row, now))[1]

    def counted(*a, **k):
        current.clear()
        try:
            return reconcile_once(*a, **k)
        finally:
            passes.append((k.get("only"), list(current)))
    evaluator.reconcile_once = counted
    for unit in ("777", "2", str(cid)):
        EventLog(box.archive, "vms", unit, 1).append(time.time(), "motion")   # the units exist before anybody waits
    evaluator.watch_events(ON)
    stop = threading.Event()
    thread = threading.Thread(target=evaluator.run, kwargs={"poll": 2.0, "stop": stop}, daemon=True)
    thread.start()
    try:
        _until(lambda: res.watch.waiting() == 1 and evaluator.wants(), what="the evaluator's request to be held")
        assert evaluator.wants() == sorted([("vms", "io.input", "2"), ("vms", "io.input", str(cid))])
        time.sleep(0.3)
        t0, n0 = time.monotonic(), len(passes)
        noisy = EventLog(box.archive, "vms", "777", 1)
        while time.monotonic() - t0 < 3.0:                           # camera 777's contact, twenty times a second
            noisy.append(time.time(), "io.input", port="1", value="closed")
            time.sleep(0.05)
        flood = passes[n0:]
        assert len(flood) <= 3 and evaluator.wake.early == 0, f"{len(flood)} passes, {evaluator.wake.early} early, in 3 s"
        n1 = len(passes)
        EventLog(box.archive, "vms", "2", 1).append(time.time(), "io.input", port="1", value="closed")
        early = lambda: [p for p in passes[n1:] if p[0] is not None and ("vms", "io.input", "2") in p[0]]
        _until(lambda: early(), 2.0, "an early pass for camera 2's contact")
        assert early()[0][1] == ["other"], f"the early pass evaluated {early()[0][1]}"   # and read no other scenario
        assert all(p[1] == ["door", "other"] for p in passes if p[0] is None and p[1])    # the ordinary pass: all of them
        assert evaluator.long_poll.woken >= 1
    finally:
        stop.set(); thread.join(timeout=10); srv.shutdown()


def test_the_gap_widens_with_a_long_pass_and_with_a_resource_that_refuses():
    """M8, the other half. The gap was a quarter of a second whatever happened: a pass that took a second was
    followed by the next early one at once, and a resource answering 503 was asked four times a second all the same.
    `Wake.pace` is told after every pass how long it took and whether a resource refused: the gap is at least twice
    the pass, doubles with every refused pass up to `WAKE_GAP_MAX`, and is back at the floor after a clean one. The
    evaluator says a resource refused when a window of the pass came back without a server that `did not answer`."""
    wake = longpoll.Wake()
    assert wake.pace(0.01, False) == longpoll.WAKE_GAP
    assert wake.pace(0.4, False) == 0.8                              # a long pass: early passes take half the loop at most
    assert [wake.pace(0.01, True) for _ in range(5)] == [0.25, 0.5, 1.0, 2.0, 2.0]   # refused: doubling, to the ceiling
    assert wake.pace(0.01, False) == longpoll.WAKE_GAP               # answered again: back to the floor
    from tests.test_autoworker import _Log, _assigned, _scenario, _worker, ev
    box = Box()
    t = box.wall()
    log_ = _Log([ev(t - 5, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box); _assigned(box, "door-on-badge")
    w = _worker(box, log_)
    query = log_.query
    log_.query = lambda *a, **k: {**query(*a, **k), "incomplete": {"srv-b": "did not answer"}, "complete": False}
    w.reconcile_once()
    assert w._refused is True
    log_.query = query
    w.reconcile_once()
    assert w._refused is False


def test_a_client_holds_one_wait_the_total_is_a_setting_and_the_counts_are_on_the_pulse_and_metrics():
    """`WAITERS_MAX` was one bound for the resource, with no share per client: the seventeenth evaluator got `full`
    nearly always and stayed on its two-second pass, silently. Now a client (the evaluator's instance, `client=`)
    holds ONE request — its next one ends the first, `replaced` — the total is `LONG_POLL_WAITERS`, and what was held,
    refused and replaced is in the resource's heartbeat and on `/metrics`. And a pause after a refusal is ±50 %, so the
    refused do not all ask again in the same instant."""
    from w2cplatform.console import SpecConsole
    box = _real_box()
    res, srv = _resource(box)
    res.watch.waiters_max = longpoll.waiters_from({"LONG_POLL_WAITERS": "3"})
    assert res.watch.waiters_max == 3 and longpoll.waiters_from({}) == longpoll.WAITERS_MAX == 2 * longpoll.EVALUATORS_EXPECTED
    try:
        EventLog(box.archive, "vms", "7", 1).append(time.time(), "motion")
        first, out1 = _asking(res.url, "vms/io.input&client=a-1", 8.0)
        _until(lambda: res.watch.waiting() == 1)
        again, out2 = _asking(res.url, "vms/io.input&client=a-1", 8.0)   # the same evaluator asks again
        first.join(timeout=3)
        assert out1["rep"]["replaced"] is True and out1["rep"]["changed"] is False
        _until(lambda: res.watch.waiting() == 1, what="one request of a-1, the newer")
        others = [_asking(res.url, f"vms/io.input&client=a-{i}", 8.0) for i in (2, 3)]
        _until(lambda: res.watch.waiting() == 3)
        assert _ask(res.url, "vms/io.input&client=a-4", 8.0)["full"] is True
        assert res.watch.counts() == {"waiting": 3, "held": 4, "full": 1, "replaced": 1, "max": 3}
        assert res.heartbeat()["waits"]["full"] == 1
        text = SpecConsole(VmsController(box.vars, box.objects, wall=box.wall), wall=box.wall).metrics_text()
        for line in ('vms_resource_waits{server="srv-a"} 3', 'vms_resource_waits_full_total{server="srv-a"} 1',
                     'vms_resource_waits_held_total{server="srv-a"} 4', 'vms_resource_waits_replaced_total{server="srv-a"} 1'):
            assert line in text, line
        EventLog(box.archive, "vms", "7", 1).append(time.time(), "io.input")
        for t, out in [(again, out2)] + others:
            t.join(timeout=3)
            assert out["rep"]["changed"] is True
    finally:
        srv.shutdown()
    pauses: list[float] = []
    lp = longpoll.LongPoll(longpoll.Wake(), lambda: {}, lambda: [], backoff=2.0)
    lp._stop.wait = lambda s: pauses.append(s)
    for _ in range(20):
        lp._pause()
    assert all(1.0 <= p <= 3.0 for p in pauses) and len(set(pauses)) > 1


def test_what_a_reader_asks_again_with_never_skips_a_change_and_a_refusal_does_not_move_it():
    """`seq` was read after the waiter left and outside the lock: a change the watcher noticed in between went into
    the number the reader asks again with, not into an answer — swallowed until its next ordinary pass. It is read
    under the lock now, with what the waiter was told. And `full` and `closed` moved `since` too: a change before a
    refusal was skipped for good."""
    watch = longpoll.Watch([tempfile.mkdtemp()], wall=time.time)

    class Lock:                                                      # the watcher takes the lock the instant the waiter leaves
        def __init__(self):
            self.real, self.armed = threading.Lock(), False

        def __enter__(self):
            self.real.acquire()

        def __exit__(self, *a):
            self.real.release()
            if self.armed == threading.get_ident():
                self.armed = False
                with self.real:
                    watch.seq += 1
                    watch.last[("vms", "io.input", "7")] = watch.seq
    watch._lock = Lock()
    calls = {"n": 0}

    def gone():
        calls["n"] += 1
        watch._lock.armed = threading.get_ident()                   # this thread's next release is the waiter leaving
        return True
    rep = watch.wait([("vms", "io.input", "7")], 5.0, gone=gone)
    assert rep["changed"] is False and watch.seq == rep["seq"] + 1
    assert watch.wait([("vms", "io.input", "7")], 0.0, since=rep["seq"])["changed"] is True      # not swallowed
    asked: list = []
    answers = [{"changed": True, "seq": 4, "touched": []}, {"changed": False, "full": True, "seq": 99},
               {"changed": False, "closed": True, "seq": 98}]

    def fetch(url, wants, timeout, since):
        asked.append(since)
        if answers:
            return answers.pop(0)
        time.sleep(0.05)
        return {"changed": False, "seq": 4}
    lp = longpoll.LongPoll(longpoll.Wake(), lambda: {"a": "http://a"}, lambda: [("vms", "io.input")], backoff=0.02, fetch=fetch)
    lp.sync()
    _until(lambda: len(asked) >= 4, 3.0, "four requests")
    lp.close()
    assert asked[:4] == [None, 4, 4, 4]


def test_a_want_is_refused_when_it_is_empty_not_a_name_or_too_many():
    """An empty `want` held a place for thirty seconds and answered nothing; `want=../../x/k` sent the watcher to list
    a directory outside the volumes; nothing bounded how many were named. Each is 400 now."""
    assert longpoll.parse_wants("vms/io.input,det/motion/7-motion") == [("det", "motion", "7-motion"), ("vms", "io.input", "")]
    for bad in ("", " , ", "../../x/k", "vms", "vms/", "vms/io.input/../x", ",".join(f"vms/k{i}" for i in range(65))):
        try:
            longpoll.parse_wants(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} was taken")
    box = _real_box()
    res, srv = _resource(box)
    try:
        for bad in ("", "..%2F..%2Fx%2Fk", ",".join(f"vms/k{i}" for i in range(65))):
            t0 = time.monotonic()
            try:
                _ask(res.url, bad, 5.0)
                raise AssertionError(f"{bad!r} was held")
            except urllib.error.HTTPError as e:
                assert e.code == 400 and time.monotonic() - t0 < 1.0
        assert res.watch.held == 0
    finally:
        srv.shutdown()


def test_the_watcher_looks_at_the_units_it_was_asked_about_and_lists_a_directory_again_when_it_changed():
    """The watcher's cost grew with every unit of the subsystem, not with what was asked: a thousand cameras were 7 %
    of a core with one waiter, five thousand 31 %. A want that names its units is looked at for those units alone; a
    directory is listed again when its mtime moved — and a unit's new epoch is still noticed."""
    box = _real_box()
    res, srv = _resource(box)
    try:
        for unit in range(1000):
            EventLog(box.archive, "vms", str(unit), 1).append(time.time(), "motion")
        listed: list[str] = []
        real = os.listdir
        os.listdir = lambda p: (listed.append(p), real(p))[1]
        try:
            _ask(res.url, "vms/io.input/7", 0.55)
        finally:
            os.listdir = real
        assert res.watch.stats <= 2 * 8, f"{res.watch.stats} stats for one camera in half a second"
        assert len(listed) <= 4, f"listed {len(listed)} directories for one camera"
        t, out = _asking(res.url, "vms/io.input/7", 5.0)
        _until(lambda: res.watch.waiting() == 1)
        time.sleep(0.3)
        EventLog(box.archive, "vms", "7", 2).append(time.time(), "io.input")      # camera 7 started again: epoch 2
        t.join(timeout=4)
        assert out["rep"]["changed"] is True and out["rep"]["touched"] == ["vms/io.input/7"]
    finally:
        srv.shutdown()


def test_a_held_request_on_a_descriptor_above_1024_is_still_watched_and_not_taken_for_gone():
    """`select.select` cannot take a descriptor at or above 1024: it raised `ValueError`, read as "the client went",
    and on a busy process every hold became a poll answered within a second. `client_gone` asks `selectors` now: an
    open client at descriptor 1500 is there, and gone when it hangs up."""
    import resource as rlimit
    import socket
    soft, hard = rlimit.getrlimit(rlimit.RLIMIT_NOFILE)
    if hard != rlimit.RLIM_INFINITY and hard < 1600:
        return                                                       # this machine cannot open a descriptor that high
    rlimit.setrlimit(rlimit.RLIMIT_NOFILE, (max(soft, 1600), hard))
    try:
        a, b = socket.socketpair()
        os.dup2(a.fileno(), 1500)
        high = socket.socket(fileno=1500)
        try:
            assert longpoll.client_gone(high) is False
            b.close()
            assert longpoll.client_gone(high) is True
        finally:
            high.close(); a.close()
    finally:
        rlimit.setrlimit(rlimit.RLIMIT_NOFILE, (soft, hard))


def test_an_ordinary_pass_reads_the_catalog_once_however_many_scenarios_name_no_camera():
    """The sweep beside M8. A scenario's fit is checked against the catalog on every pass, and a trigger that names no
    camera lists and reads every camera — once per such scenario, per pass. It is read once per ordinary pass now, and
    an early pass says what the last ordinary one found."""
    from tests.conftest import door_site
    from tests.test_autoworker import _Log, _worker
    box = Box()
    door_site(box)
    con = AutoController(box.vars.as_writer("console", AUTO_SPEC.acl_console()), box.objects, wall=box.wall)
    names = [f"any-{i}" for i in range(4)]
    for name in names:
        con.create({"name": name, "when": [{"sub": "vms", "kind": "io.input"}], "within": 0,
                    "then": [{"sub": "vms", "action": "output", "unit": "12", "port": 2, "pulse_ms": 500}]})
    AutoController(box.vars.as_writer("autocontroller", AUTO_SPEC.acl_controller()), box.objects, wall=box.wall).assign("a-1", names)
    w = _worker(box, _Log([]))
    listed: list[str] = []
    real = w.catalog.vars.list
    w.catalog.vars.list = lambda prefix, *a, **k: (listed.append(prefix), real(prefix, *a, **k))[1]
    w.reconcile_once()
    assert listed.count("vms/cameras/") == 1, listed                # four scenarios, one listing
    del listed[:]
    w.reconcile_once(only={("vms", "io.input", "12")})
    assert listed == [] and all(w.status_by_unit[n]["phase"] == "running" for n in names)


def test_seventy_scenarios_on_seventy_cameras_fold_to_their_kind_and_the_long_poll_holds():
    """The review's eighth pass, part 3, a regression of M8: more than `WANTS_MAX` triples were sent whole, every request
    was 400, and the evaluator's long poll was off for good — the road back at two seconds, seen only in
    `auto_wait_errors_total`. More than 64 scenarios on one evaluator are expected; past the bound the triples fold to
    their kinds on any unit: the request is held, a line of any camera answers it and says which camera it was (`touched`
    — the early pass still evaluates only what it touches), and the folding is on the pulse and on `/metrics`. And an
    answer of another shape costs that one wait, not the thread."""
    from vms.console import auto_metrics
    box = _real_box()
    res, srv = _resource(box)
    holder, cid, _dev, _called = _holder(box)
    evaluator = _evaluator(box, cid)
    evaluator._watched = {("vms", "io.input", str(i)) for i in range(1, 71)}   # what seventy scenarios' triggers watch
    for unit in ("42", "77"):
        EventLog(box.archive, "vms", unit, 1).append(time.time(), "motion")      # the units exist before anybody waits
    assert evaluator.wants() == [("vms", "io.input", "")] and evaluator.wants_folded == 70
    evaluator.watch_events(ON)
    try:
        evaluator.long_poll.sync()
        _until(lambda: res.watch.waiting() == 1, what="the folded request to be held")
        assert evaluator.long_poll.errors == 0
        EventLog(box.archive, "vms", "42", 1).append(time.time(), "io.input", port="1", value="closed")
        _until(lambda: evaluator.long_poll.woken >= 1, 3.0, "the folded request to be answered")
        assert ("vms", "io.input", "42") in evaluator.long_poll.take_touched()
        evaluator.heartbeat_once()
        hb = Heartbeat.from_bytes(box.objects.get(AUTO_SPEC.sub.heartbeat_key("a-1")))
        assert hb.extra["wants_folded"] == 70 and hb.extra["wait_errors"] == 0
        from w2cplatform.spec import SpecController
        text = "\n".join(auto_metrics(SpecController(AUTO_SPEC, box.vars, box.objects, wall=box.wall))())
        assert 'auto_wants_folded{worker="a-1"} 70' in text
    finally:
        evaluator.stop_polling(); srv.shutdown()
    assert longpoll.fold([("vms", f"k{i}", "1") for i in range(70)]) == ([], 70)  # more kinds than a request names: the pass
    calls = []
    lp = longpoll.LongPoll(longpoll.Wake(), lambda: {"srv-a": "http://srv-a"}, lambda: [("vms", "io.input", "")],
                           backoff=0.01, fetch=lambda *a: (calls.append(1), [1, 2])[1])
    lp.sync()
    _until(lambda: len(calls) >= 3, 3.0, "the thread to ask again after an answer of another shape")
    lp.close()
    assert lp.errors >= 2
