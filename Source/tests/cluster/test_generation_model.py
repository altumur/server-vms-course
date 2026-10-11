"""The model of sequences (ADR-0070's addition of 2026-10-11, «Архитектор», on «Сборка»'s finding): every way a state is
put into a group — `recover` of a member's own directory, `restore` of a backup into a fresh group — in orders a seeded
random walk picks, with backups taken and old ones put in again, and the CLOCK stepped back, held to one invariant: NO
EPOCH IS ISSUED TWICE, across every group of the lineage. The generation of an input is `max(by the content + 1, the
clock)`, the clock whole hours of UTC since 2026-01-01 (`epoch.generation_hours`); here the clock is said by the walk —
an hour later for every operation — so the model is the same on every run. A clock stepped back below the hour of the
generation in the state put in is refused (the operator's `-force` is not walked: with it the operator answers for the
repeat); set right, the walk goes on.

Without the clock (the floor by the content alone) the walk finds the repeat the finding was: a backup restored after the
group it was taken of went through a recover — `test_the_content_alone_repeats_a_generation_which_the_clock_does_not`.

Real raft (`pysyncobj`), groups of one on this machine's loopback, in this process; skipped without the library."""
from __future__ import annotations

import os
import random
import shutil
import socket
import tempfile

import pytest

from w2cplatform import configstore
from w2cplatform.configstore import StoreDaemon, have_library
from w2cplatform.epoch import EPOCH_FLOOR_AT, EPOCH_FLOOR_KEY, hours_of, next_epoch
from w2cplatform.variables import open_vars

pytestmark = pytest.mark.skipif(not have_library(), reason="the raft library is not installed: pip install pysyncobj")

UNITS = ("model/epoch/1", "model/epoch/2")


def _port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class One:
    """A group of one: its directory, its raft address, its daemon with `admin.sock`."""

    def __init__(self, root: str, n: int, index_base: int = 0):
        self.name, self.data, self.sockets = f"g{n}", os.path.join(root, f"d{n}"), os.path.join(root, f"s{n}")
        self.raft = f"127.0.0.1:{_port()}"
        self.daemon = None
        self.start(bootstrap=True, index_base=index_base)

    def start(self, bootstrap: bool = False, index_base: int = 0) -> None:
        b = configstore.start_member(self.name, self.data, self.raft, group_size=1, bootstrap=bootstrap, tls_dir=None,
                                     tuning="lan", index_base=index_base)
        self.daemon = StoreDaemon(b, node_id=self.name, sockets=self.sockets)

    def vars(self):
        return open_vars(f"configstore://{self.sockets}/admin.sock?timeout=5")

    def stop(self) -> None:
        if self.daemon is not None:
            self.daemon.stop()
            self.daemon = None


def _generation_at(rows) -> int | None:
    for key, items in rows:
        if key == EPOCH_FLOOR_KEY and items.get(EPOCH_FLOOR_AT):
            return hours_of(items[EPOCH_FLOOR_AT])
    return None


def _walk(seed: int, steps: int, clock_of=lambda hours: hours) -> list[str]:
    """The walk; `clock_of(hours)` is the hours an input is told (the clock's form: the hours themselves; the content
    alone: 0). The repeats it found, as words."""
    rnd = random.Random(seed)
    root = tempfile.mkdtemp(prefix="model-")
    groups, issued, repeats, backups = [], {u: set() for u in UNITS}, [], []
    hours = 5000                                     # the walk's clock: hours since 2026-01-01
    try:
        cur = One(root, 0)
        groups.append(cur)
        for _step in range(steps):
            hours += 1                               # an hour later for every operation
            op = rnd.choice(("issue", "issue", "backup", "recover", "restore", "clock_back"))
            if op == "issue":
                for _ in range(rnd.randint(1, 3)):
                    u = rnd.choice(UNITS)
                    e = next_epoch(cur.vars(), u)[0]
                    if e in issued[u]:
                        repeats.append(f"{u} {e}")
                    issued[u].add(e)
            elif op == "backup":
                backups.append(configstore.backup_rows(cur.vars()))
            elif op == "recover":
                cur.stop()
                configstore.recover(cur.name, cur.data, {cur.name: cur.raft}, hours=clock_of(hours))
                cur.start()
            elif op == "restore" and backups:
                backup = rnd.choice(backups)
                fresh = One(root, len(groups), index_base=int(backup["highest"]))
                groups.append(fresh)
                configstore.restore_rows(backup, fresh.vars(), hours=clock_of(hours))
                cur.stop()
                cur = fresh
            elif op == "clock_back":
                back = hours - rnd.randint(1, 48)
                at = _generation_at((k, items) for k, items in [(EPOCH_FLOOR_KEY, cur.vars().get(EPOCH_FLOOR_KEY)[0] or {})])
                cur.stop()
                try:
                    configstore.recover(cur.name, cur.data, {cur.name: cur.raft}, hours=clock_of(back))
                    refused = False
                except ValueError as e:
                    refused = "the clock reads before the hour the state's floor was raised at" in str(e)
                    assert refused, e
                # refused exactly when the clock is before the hour of the state's generation
                assert refused == (at is not None and clock_of(back) < at), (seed, back, at, refused)
                cur.start()                          # the operator sets the clock right; the walk goes on
        return repeats
    finally:
        for g in groups:
            g.stop()
        shutil.rmtree(root, ignore_errors=True)


def test_recover_restore_and_a_clock_stepped_back_in_any_order_never_issue_an_epoch_twice():
    """Three seeded walks of twelve operations each: issue, backup, recover, restore of any backup taken so far, the clock
    stepped back. No epoch of a unit is issued twice; a clock behind the generation in the state is refused, and only
    then."""
    for seed in range(3):
        assert _walk(seed, 12) == [], seed


def test_the_content_alone_repeats_a_generation_which_the_clock_does_not():
    """The finding, kept: the floor by the content alone (the clock told 0) — a backup taken, a recover, epochs issued in
    the recover's generation, the backup restored — issues an epoch of that generation again. The clock's form, on the
    same steps, does not."""
    def steps(clock_of) -> list[int]:
        root = tempfile.mkdtemp(prefix="model-")
        a = b = None
        try:
            a = One(root, 0)
            u = UNITS[0]
            out = [next_epoch(a.vars(), u)[0]]
            backup = configstore.backup_rows(a.vars())
            a.stop()
            configstore.recover(a.name, a.data, {a.name: a.raft}, hours=clock_of(5001))
            a.start()
            out.append(next_epoch(a.vars(), u)[0])
            a.stop()
            b = One(root, 1, index_base=int(backup["highest"]))
            configstore.restore_rows(backup, b.vars(), hours=clock_of(5002))
            out.append(next_epoch(b.vars(), u)[0])
            return out
        finally:
            for g in (a, b):
                if g is not None:
                    g.stop()
            shutil.rmtree(root, ignore_errors=True)
    content = steps(lambda hours: 0)
    assert content == [1, (1 << 32) + 1, (1 << 32) + 1], content          # the repeat the finding was
    clock = steps(lambda hours: hours)
    assert clock == [1, (5001 << 32) + 1, (5002 << 32) + 1], clock
