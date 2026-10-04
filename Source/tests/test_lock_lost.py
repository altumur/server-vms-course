"""A writer that lost its volume's lock — the engine's patch 07, and what the recorder's client makes of it.

The course's fifth review, blocker 1: a network volume under two hosts, host A frozen past the engine lock's stale
age, host B takes the volume. Before patch 07 the engine noticed nothing — A's woken writer flushed beside B's and its
close removed B's lock file. With it the engine checks the lock at its path before every block and status, stops a
writer whose lock is another's (`WRITER_STOPPED`, "volume lock lost"), and takes `WRITER_ABANDON`: the writer given up
writing nothing. That engine is the only one the course supports: the suite's daemon is refused without it
(`tests/conftest.py`), and a recorder takes no network volume on a daemon that lacks it (the last test here).
"""
import os
import signal
import tempfile
import time

from tests.conftest import TEST_BLOCK, TEST_READ, Box, ObsdDaemon, footage, recorder


def test_a_writer_whose_lock_another_writer_took_is_stopped_by_the_engine_and_given_up_writing_nothing():
    """Two daemons over one directory, no holds: A's daemon frozen past the lock's stale age, B mounts; woken, A's
    writer finds the lock B's before its next block and stops — `WRITER_STOPPED`, "volume lock lost". That is the place
    lost, not the engine: the archive says `lock_lost`, sends nothing more, and gives the writer up with
    `WRITER_ABANDON`; B's volume stays clean and keeps what B wrote."""
    from vms.obsd import ObsdError, Session
    from vms.archive import Archive, Fenced
    from vms.worker import fake_samples
    da, db = ObsdDaemon.fresh(), ObsdDaemon.fresh()
    try:
        url = "file://" + tempfile.mkdtemp(prefix="net-")
        a = Archive(url, "net", 64 << 20, "rec:net", Session(da.socket, client="a", timeout=2), block=TEST_BLOCK,
                    read=TEST_READ, lock_refresh=2).open()
        t = Box().wall()
        footage(a, "1", 1, t - 60, t - 30, seal=False)
        os.kill(da.proc.pid, signal.SIGSTOP)
        try:
            time.sleep(4)
            b = Archive(url, "net", 64 << 20, "rec:net", Session(db.socket, client="b", timeout=2), block=TEST_BLOCK,
                        read=TEST_READ, lock_refresh=2)
            deadline = time.monotonic() + 15
            while b.writer is None:
                try:
                    b.open()
                except Exception:                                      # noqa: BLE001 — busy until A's lock is stale
                    assert time.monotonic() < deadline
                    time.sleep(0.5)
            footage(b, "9", 1, t - 20, t, seal=False)
        finally:
            os.kill(da.proc.pid, signal.SIGCONT)
        said = []
        for smp in fake_samples(t - 30, t, step=0.2, size=256 << 10):  # enough for a block: the engine checks before one
            try:
                said.append(a.put("1", 1, smp))
            except Fenced:
                said.append("FENCED")
            except ObsdError as e:
                said.append(e.name)
            time.sleep(0.01)
        assert "WRITER_STOPPED" in said and a.lock_lost, said
        stopped = said.index("WRITER_STOPPED")
        assert said[stopped + 1:] == ["FENCED"] * (len(said) - stopped - 1)   # nothing more sent
        assert a.abandon() and a.writer is None
        # what A's writer had taken and never wrote is said, not lost in silence (the sixth pass): the thirty seconds
        # it took before the freeze, and whatever it took after waking before the engine stopped it
        assert list(a.dropped) == ["1/e1"] and a.dropped["1/e1"][0] == t - 60 and a.dropped["1/e1"][1] >= t - 30
        b.seal()                                                       # clean: nothing of A's landed
        assert b.writer is not None and b.coverage("9") == [(t - 20, t)]
    finally:
        da.stop(); db.stop()


def test_a_daemon_that_knows_the_operation_says_so_once_and_one_that_does_not_is_not_taken_for_one():
    """The probe the recorder's one guard rests on (`Session.abandons`): `WRITER_ABANDON` for a handle that is
    nobody's. This daemon answers that it does not know the handle — and that is not the session lost; a daemon without
    the operation answers `UNKNOWN_OP`. Asked once per daemon."""
    from vms.obsd import CODE, ObsdError, Session
    s = Session(ObsdDaemon.get().socket, client="probe")
    asked, real = [], s.call

    def call(op, *a, **kw):
        asked.append(op)
        return real(op, *a, **kw)
    s.call = call
    assert s.abandons() and s.abandons() and asked == ["WRITER_ABANDON"]
    assert s.lost == 0 and s.generation == 0                           # nothing was lost by asking

    old = Session(ObsdDaemon.get().socket, client="probe-old")

    def unknown(op, *a, **kw):
        raise ObsdError(CODE["UNKNOWN_OP"], op, "operation 36")
    old.call = unknown
    assert old.abandons() is False
    s.bye()


def test_a_recorder_takes_no_network_volume_on_an_obsd_that_cannot_give_one_up():
    """The review's sixth pass, blocker 1, and the decision it asked for. A daemon without `WRITER_ABANDON` got the
    volume anyway, with a stopgap — the writer "parked" when its hold was lost — that made the volume busy for ever for
    the box that took it. Such a daemon is not given a volume any box may serve at all: the recorder does not claim it,
    mounts nothing, and says why in words an operator can act on — in its heartbeat and on the volumes page — while a
    recorder whose daemon can takes it. Its own disk is not affected."""
    from vms import volumes
    from vms.config import REC_SPEC
    from vms.obsd import Session
    box = Box()
    net = tempfile.mkdtemp(prefix="net-")
    volumes.write(box.vars, {"name": "net", "kind": "network", "url": net, "quota_bytes": 64 << 20})
    r = recorder(box, "r-1", "srv-a", acl=False)
    r.session.abandons = lambda: False                                 # an obsd older than the engine this course requires
    r.lease_pass(); r.heartbeat_once()
    assert r.hold is None and box.vars.get("rec/holds/net")[0] is None  # not claimed
    assert not any(net in w["key"] for w in Session(ObsdDaemon.get().socket, client="peek").stats()["writers"])
    assert r.volume == "srv-a" and r.store is not None and r.volume_error == ""    # its own disk: as before
    why = r.heartbeat_extra()["refused"]["net"]
    assert "obsd on srv-a is too old to write net safely" in why and "Update obsd on srv-a" in why
    assert "patch" not in why and "ABANDON" not in why                 # an operator's words, not the build's
    [row] = volumes.served(box.vars, REC_SPEC.sub, box.wall(), objects=box.objects)["volumes"]
    assert row["served_by"] is None and "r-1 does not take it" in row["why"] and "too old" in row["why"]

    other = recorder(box, "r-2", "srv-b", acl=False)                   # a box whose obsd can: it takes the volume
    other.lease_pass(); other.heartbeat_once()
    assert other.hold == "net" and other.store is not None and other.store.writer is not None
    [row] = volumes.served(box.vars, REC_SPEC.sub, box.wall(), objects=box.objects)["volumes"]
    assert row["served_by"] and row["why"] is None

    # the neighbours of the same rule: a volume PINNED to such a recorder is refused the same way, mounted by nobody,
    # claimed by nobody — and the recorder says what it waits for (the seventh pass: a pinned network volume takes the hold)
    pinned = recorder(Box(), "r-1", "srv-c", acl=False, env={"VOLUME": "net2"})
    volumes.write(pinned.vars, {"name": "net2", "kind": "network", "url": tempfile.mkdtemp(prefix="net2-"),
                                "quota_bytes": 64 << 20})
    pinned.session.abandons = lambda: False
    pinned.lease_pass()
    assert pinned.store is None and pinned.capacity == 0 and pinned.hold is None and pinned.volume == ""
    assert "too old to write net2 safely" in pinned.heartbeat_extra()["volume_wait"]
    # …and one already held, on a daemon replaced by an older build, is let go — for a box that can serve it
    other.session.abandons = lambda: False
    other.lease_pass()
    assert other.hold is None and other.volume == "srv-b" and "net" in other.heartbeat_extra()["refused"]
    from w2cplatform.contract import Slot
    assert Slot.from_items("net", box.vars.get("rec/holds/net")[0]).released
