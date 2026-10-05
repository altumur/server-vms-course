"""An archive that stops answering — the host's `obsd` gone, or there and silent, for a minute or an hour.

The recorder writes through the daemon, and the daemon is a process of its own: it can be restarted, it can be
killed, it can take a request and say nothing. None of that may stop the recorder LIVING. A recorder that stops
renewing its leases loses its epochs, and one that stops heartbeating is reassigned by its controller — either
way every recording on it ends, and it ends because of the one component it was told to wait for.

So the rule is about the loop: staying alive — renewing leases, sending the heartbeat — never shares a fate with
doing the work, and no call the work makes may hold the loop longer than a lease.
"""
import os
import socket
import tempfile
import threading

from vms.obsd import Session
from vms.recworker import RecWorker
from tests.vmsconftest import Box, obsd_session, recorder


class _Passes:
    """A `stop` for `run()` that lets it make exactly `n` passes, moving both clocks `poll` seconds each
    time — so the loop's own timers (lease, heartbeat) fire as they would in a minute of real running,
    with no thread and no sleeping. `run` asks only `is_set()` and `wait(poll)` of it."""

    def __init__(self, n: int, box: Box):
        self.n, self.box = n, box

    def is_set(self) -> bool:
        return self.n <= 0

    def wait(self, poll: float) -> None:
        self.n -= 1
        self.box.clock.advance(poll)
        self.box.wall.advance(poll)


def _counted(r: RecWorker) -> dict:
    """Counters on the two things a living recorder must keep doing."""
    calls = {"heartbeat": 0, "lease": 0}
    heartbeat, lease = r.heartbeat_once, r.lease_pass

    def counted_heartbeat():
        calls["heartbeat"] += 1
        return heartbeat()

    def counted_lease():
        calls["lease"] += 1
        return lease()
    r.heartbeat_once, r.lease_pass = counted_heartbeat, counted_lease
    return calls


def _without_a_daemon(box: Box) -> tuple[RecWorker, dict]:
    """A recorder whose host has no obsd at all: nothing listens on its socket."""
    r = recorder(box, obsd=Session(os.path.join(tempfile.mkdtemp(), "obsd.sock"), client="rec-r-1", timeout=0.5))
    return r, _counted(r)


def test_a_daemon_that_is_not_there_does_not_stop_the_recorder():
    """A minute of the loop with no daemon throughout.

    Leases are renewed every `(ttl − margin) / 3` ≈ 8 s and the heartbeat goes every 10 s, so a minute
    holds several of each. Both must keep happening: the recorder is healthy, its place is its own, and
    only the engine it writes through is away."""
    box = Box()
    r, calls = _without_a_daemon(box)
    r.run(poll=2.0, stop=_Passes(30, box))                       # a minute, the daemon away the whole time

    assert calls["lease"] >= 5, f"leases renewed {calls['lease']} times in a minute: the work took the loop with it"
    assert calls["heartbeat"] >= 5, f"heartbeat sent {calls['heartbeat']} times in a minute: the controller will call it dead"

    # …and the outage is SAID, not just survived: a recorder quietly holding a volume it cannot write into looks,
    # from outside, exactly like one that is fine.
    hb = r.heartbeat_extra()
    assert "obsd is not answering" in hb["archive_error"] and hb["archive_away_since"] > 0
    assert hb["archive_failure"] == "away"
    assert hb["volume_error"] == "", "an engine that went away is not a volume that will not open — it is not handed back"
    assert hb["volume"] == "srv-1"                               # the place is kept


def test_when_the_daemon_answers_again_the_volume_opens_and_the_outage_is_over():
    """The other end of the outage. The start of it is kept while it lasts; when the daemon answers — restarted,
    or back from wherever it was — the next pass opens the volume, and `archive_error` clears because a volume
    actually opened."""
    box = Box()
    r, _ = _without_a_daemon(box)
    r.lease_pass()
    away_since = r.archive_away_since
    assert r.archive_error and away_since and r.store is None

    box.wall.advance(600)
    r.lease_pass()                                               # still away: the start of the outage is kept
    assert r.archive_away_since == away_since

    r.session = obsd_session("rec-r-1")                          # the daemon is back
    r.lease_pass()
    assert r.store is not None and r.store.writer is not None
    assert r.archive_error == "" and r.archive_away_since == 0.0 and r.archive_failure == ""


def test_no_failure_in_the_work_can_stop_the_recorder_living():
    """The structural half. `pump_once` is where a recorder reaches out — backfill fetches a range from a device
    or a backup and lands it — and any of it can fail during the very outage it was meant to ride out. Catching
    them one call site at a time is a list that is complete only until the next call site.

    So: STAYING ALIVE never shares a fate with DOING THE WORK. A pass that failed is logged and retried; the
    process that ran it is still the one holding its units, and saying so is not optional. The error here is
    deliberately not an `OSError`: this is the guarantee for whatever nobody anticipated."""
    box = Box()
    r = recorder(box)
    calls = _counted(r)

    def something_nobody_anticipated(*a, **k):
        raise RuntimeError("backfill fell over")
    r.backfill_budget, r.backfill = 1, something_nobody_anticipated

    r.run(poll=2.0, stop=_Passes(30, box))

    assert calls["lease"] >= 5, f"leases renewed {calls['lease']} times: a failure in the work stopped the recorder living"
    assert calls["heartbeat"] >= 5, f"heartbeat sent {calls['heartbeat']} times: the controller will call it dead"


# -- the worse failure: a daemon that does not fail, it does not ANSWER -------------------------------------
#
# A daemon wedged on a dead network volume takes the request and says nothing. There is no exception to catch,
# only a call that does not come back — and while it has not, the loop is not renewing anything. So every call
# waits at most the session's timeout, shorter than a lease, and a silence is `away`, not asked twice.

class _Silent:
    """A daemon that accepts every connection, reads what it is sent, and never answers."""

    def __init__(self):
        self.path = os.path.join(tempfile.mkdtemp(), "obsd.sock")
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(self.path); self.srv.listen(8)
        self.conns: list[socket.socket] = []
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            self.conns.append(c)

    def close(self):
        for c in self.conns:
            c.close()
        self.srv.close()


def test_a_daemon_that_says_nothing_does_not_stop_the_recorder_living():
    """A minute of the loop against a daemon that never answers. A loop that waited on it would renew nothing:
    the same thirty seconds to losing its epochs as no daemon at all, with nothing in the log to say why,
    because nothing failed."""
    box = Box()
    silent = _Silent()
    try:
        r = recorder(box, obsd=Session(silent.path, client="rec-r-1", timeout=0.05))
        calls = _counted(r)
        t = threading.Thread(target=r.run, kwargs={"poll": 2.0, "stop": _Passes(30, box)}, daemon=True)
        t.start(); t.join(timeout=20)
        assert not t.is_alive(), "a minute of the loop did not end: a call waited on the silent daemon"
    finally:
        silent.close()

    assert calls["lease"] >= 5, f"leases renewed {calls['lease']} times while the daemon said nothing"
    assert calls["heartbeat"] >= 5, f"heartbeat sent {calls['heartbeat']} times while the daemon said nothing"
    assert r.archive_failure == "away" and "no answer in" in r.archive_error, r.archive_error


def test_the_recorders_calls_wait_less_than_a_lease_and_only_a_close_waits_for_its_flush():
    """The number behind the test above, in production: a third of a lease, and `WRITER_CLOSE` — which the
    protocol lets take thirty seconds to flush — the one call allowed to wait longer."""
    box = Box()
    r = RecWorker("r-x", box.vars, box.objects, clock=box.clock, wall=box.wall, server="srv-1", resource_root=box.resource_root,
                  env={}, default_quota=1 << 26)
    assert r.session.timeout == 10.0 and r.session.timeout < r.lease_ttl - r.lease_margin
    assert r.session.long_timeout >= 30.0


def test_backfill_waits_while_the_volume_is_taking_nothing():
    """Backfill exists to bring MORE into the volume. While the volume is taking nothing — away, or not open —
    a fetched range has nowhere to land, and the fetch would be one more call on a silent engine."""
    box = Box()
    r, _ = _without_a_daemon(box)
    r.lease_pass()
    tried = []
    r.backfill_budget = 1
    r.backfill = lambda *a, **k: tried.append(1) or []

    r.pump_once()
    r.pump_once()
    assert tried == [], "backfill fetched for a volume that is taking nothing"


def test_a_fetch_from_a_slow_card_does_not_hold_the_pass():
    """A fetch is a pipeline on the device's playback door, run to the end of the range — minutes, on a slow card —
    and it ran on the loop's thread. A card slower than the lease fenced the recorder and stopped the live
    recording of every camera it had, to fetch an hour of one (the platform review, blocker 3; feedback BE). It
    runs on a thread of its own, one range at a time; the pass waits half a second for it and goes on."""
    import time
    box = Box()
    r = recorder(box)
    r.lease_pass()
    started, release = [], threading.Event()

    def slow_card(*a, **k):
        started.append(1)
        release.wait(30)
        return []

    r.backfill_budget, r.backfill = 1, slow_card
    t0 = time.monotonic()
    r.pump_once()
    r.pump_once()
    assert time.monotonic() - t0 < 5 and started == [1]              # two passes went by; ONE fetch is in flight
    release.set(); r._backfiller.join(5)
    r.pump_once()
    r._backfiller.join(5)
    assert started == [1, 1]                                          # it came back: the next range may go


# -- the review's third pass ---------------------------------------------------------------------------------------

def test_a_silent_daemon_costs_a_pass_one_wait_and_not_one_per_question():
    """One connection, one lock, no deadline: forty cameras' samples queued behind a silent daemon ten seconds each,
    the pass behind them. A connection that went silent fails at once for a timeout after — the pass's budget — so
    twenty questions of a daemon that answers none wait for one of them."""
    import time
    from vms.obsd import Unavailable
    silent = _Silent()
    try:
        s = Session(silent.path, client="t", timeout=0.3)
        t0 = time.monotonic()
        for _ in range(20):
            try:
                s.call("STATS")
                raise AssertionError("a silent daemon answered")
            except Unavailable:
                pass
        assert time.monotonic() - t0 < 1.5, "every question waited its own timeout"
    finally:
        silent.close()


def test_the_engine_lost_while_the_store_is_silent_is_mounted_again_by_the_last_rows():
    """The daemon restarted during the store's own election: `volume_pass` began by reading the declared volumes,
    raised, and opened nothing again — no writer for the whole silence. The recorder mounts by the rows it read
    last: a disk of its server at once; a network volume only while its hold is still in its term for longer than
    a mount can take — and not past that, when another box may have taken it."""
    from vms import volumes
    box = Box()
    volumes.write(box.vars, {"name": "disk-a", "kind": "local", "url": os.path.join(box.root, "disk-a"), "server": "srv-1",
                             "quota_bytes": 64 << 20})
    r = recorder(box, acl=False)
    r.lease_pass()
    assert r.volume == "disk-a" and r.store is not None
    first = r.store

    def silent(*a, **k):
        raise OSError(5, "the store does not answer")
    real_declared, real_renew = volumes.declared, r.renew_hold
    volumes.declared, r.renew_hold = silent, silent
    try:
        r._lost_engine()
        r.lease_pass()
        assert r.store is not None and r.store is not first and not r.engine_lost      # mounted again, by the last row
        assert r.volume == "disk-a" and r.remounts == 1
    finally:
        volumes.declared, r.renew_hold = real_declared, real_renew

    net = Box()
    volumes.write(net.vars, {"name": "net", "kind": "network", "url": tempfile.mkdtemp(prefix="net-"), "quota_bytes": 64 << 20})
    n = recorder(net, acl=False)
    n.lease_pass()
    assert n.volume == "net" and n.store is not None
    volumes.declared, n.renew_hold = silent, silent
    try:
        n._lost_engine()
        n.lease_pass()                                                  # the hold confirmed a moment ago: still ours
        assert n.store is not None and n.remounts == 1
        n._lost_engine()
        net.clock.advance(n.slot_ttl - n.lease_margin - 1)              # in its term — but not for as long as a mount takes
        n.lease_pass()
        assert n.store is None and "could not be confirmed" in n.archive_error
    finally:
        volumes.declared, n.renew_hold = real_declared, real_renew
