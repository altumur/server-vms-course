"""A writer that lost its volume's lock — the engine's patch 07, and what the recorder's client makes of it.

The course's fifth review, blocker 1: a network volume under two hosts, host A frozen past the engine lock's stale
age, host B takes the volume. Before patch 07 the engine noticed nothing — A's woken writer flushed beside B's and its
close removed B's lock file. With it the engine checks the lock at its path before every block and status, stops a
writer whose lock is another's (`WRITER_STOPPED`, "volume lock lost"), and takes `WRITER_ABANDON`: the writer given up
writing nothing. These tests need that daemon, and are skipped with one that does not have it.
"""
import os
import signal
import tempfile
import time

import pytest

from tests.conftest import TEST_BLOCK, TEST_READ, Box, ObsdDaemon, footage


def _abandons(socket_path: str) -> bool:
    """Does this daemon take `WRITER_ABANDON` — the engine's patch 07?"""
    from w2cplatform.obsd import Session
    s = Session(socket_path, client="probe")
    try:
        vol = s.open_volume(params={"schema": "file", "path": tempfile.mkdtemp(prefix="probe-")})
        vol.format(16 << 20, max_block=1 << 20, optimal_read=256 << 10)
        return vol.mount_rw("probe").abandon()
    finally:
        s.bye()


pytestmark = pytest.mark.skipif(not _abandons(ObsdDaemon.get().socket),
                                reason="this obsd has no WRITER_ABANDON: the engine's patch 07")


def test_a_writer_whose_lock_another_writer_took_is_stopped_by_the_engine_and_given_up_writing_nothing():
    """Two daemons over one directory, no holds: A's daemon frozen past the lock's stale age, B mounts; woken, A's
    writer finds the lock B's before its next block and stops — `WRITER_STOPPED`, "volume lock lost". That is the place
    lost, not the engine: the archive says `lock_lost`, sends nothing more, and gives the writer up with
    `WRITER_ABANDON`; B's volume stays clean and keeps what B wrote."""
    from w2cplatform.obsd import ObsdError, Session
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
        b.seal()                                                       # clean: nothing of A's landed
        assert b.writer is not None and b.coverage("9") == [(t - 20, t)]
    finally:
        da.stop(); db.stop()
