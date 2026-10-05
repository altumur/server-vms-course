"""The scaling pass — what a recorder's pass and the placement's `near` cost in store reads, at a thousand recordings.

A question about ONE recording — who else records its camera, which backup holds it, who holds the camera, is the
primary written — was answered by walking every recording's row and every heartbeat, once per recording: the square of
the recordings a pass. Measured on this module's site before the change, at a thousand recordings and five hundred
`when: offline` backups: a backfill pass read the store 3 032 003 times (112 s), the backups' gate 755 500 times (30 s),
the heartbeat of the recorder of the thousand 24 000 times; `home_for` over a thousand cameras beside twenty recorders,
25 500 times. Now each pass takes ONE look (`vms.recworker.Look`; `SpecController.near_index`) and answers from maps.
These tests count every `get` and `list` of both stores and pin the ceilings — and that the count grows with the
recordings, not with their square: twice the recordings, at most twice the reads.
"""
from __future__ import annotations

import types

from tests.vmsconftest import Box
from vms import volumes
from vms.config import REC_SPEC, SPEC
from vms.worker import FakeActuator
from w2cplatform.contract import Heartbeat
from w2cplatform.variables import open_vars


class Counting:
    """A store whose reads are counted: every `get`, every `list` — what the product's `testbox.Reads` counts."""

    def __init__(self, inner, fail: str | None = None):
        self._inner, self.reads, self.fail = inner, 0, fail

    def get(self, *a, **kw):
        self.reads += 1
        return self._inner.get(*a, **kw)

    def list(self, prefix, *a, **kw):
        self.reads += 1
        if self.fail and prefix.startswith(self.fail):
            raise OSError("the store did not answer")
        return self._inner.list(prefix, *a, **kw)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _Volume:
    """The volume open, as far as a pass asks it — what is counted here is the STORE, not the engine."""
    writer, lost, name, quota = object(), False, "disks", 1 << 30

    def coverage(self, unit, stitch=2.0):
        return [(0.0, 1.0)]                              # nothing visible to plan from: every recording's sources are asked

    def status(self):
        return {"totalWritten": 0}

    def put(self, *a, **kw):
        return "OK"

    def finish(self, *a, **kw):
        return None


def _site(n: int, per_worker: int = 50):
    """`n` cameras held by VMS workers of fifty, each recorded on `disks` (`r-1`) — and half of them twice, by a
    `when: offline` backup on `copy` (`r-2`)."""
    box = Box()
    box.vars = open_vars("memory://")
    now = box.wall()
    volumes.write(box.vars, {"name": "disks", "kind": "local", "server": "srv-a", "url": "/tmp/disks", "quota_bytes": 64 << 20})
    volumes.write(box.vars, {"name": "copy", "kind": "backup", "server": "srv-b", "url": "/tmp/copy", "quota_bytes": 64 << 20})
    for i in range(1, n + 1):
        box.vars.put(f"rec/recordings/{i}", {"id": str(i), "name": str(i), "cam": str(i), "home": "disks", "enabled": "true"})
    for i in range(1, n // 2 + 1):
        box.vars.put(f"rec/recordings/{i}-copy", {"id": f"{i}-copy", "name": f"{i}-copy", "cam": str(i), "home": "copy",
                                                  "when": "offline", "enabled": "true"})
    for w in range(0, n, per_worker):
        name = f"w-{w // per_worker + 1}"
        st = [{"id": str(i), "phase": "running", "live_url": f"rtsp://srv-1:8554/{i}", "playback_url": f"http://srv-1/{i}",
               "coverage": {"from": now - 7200, "to": now}} for i in range(w + 1, min(n, w + per_worker) + 1)]
        box.objects.put(SPEC.sub.heartbeat_key(name), Heartbeat(name, now, st, {"server": "srv-1"}).to_bytes())
    box.vars.put("rec/workers/r-1", {"units": ",".join(str(i) for i in range(1, n + 1)), "rev": "1"})
    box.vars.put("rec/workers/r-2", {"units": ",".join(f"{i}-copy" for i in range(1, n // 2 + 1)), "rev": "1"})
    return box


def _recorder(box, name: str, server: str, fail: str | None = None):
    from vms.recworker import RecWorker
    vars_, objects = Counting(box.vars), Counting(box.objects, fail)
    r = RecWorker(name, vars_, objects, FakeActuator(), clock=box.clock, wall=box.wall, server=server,
                  resource_root=box.archive, obsd=types.SimpleNamespace(), env={})
    r.store = _Volume()
    return r, vars_, objects


def _reads_per_pass(n: int) -> dict:
    box = _site(n)
    (r1, v1, o1), (r2, v2, o2) = _recorder(box, "r-1", "srv-a"), _recorder(box, "r-2", "srv-b")
    for r in (r1, r2):
        r.reconcile_once()
        r.heartbeat_once()
    assert len(r1.reconciler.actual) == n and len(r2.reconciler.actual) == n // 2
    out = {}
    for label, v, o, step in (("pass", v1, o1, r1.reconcile_once), ("heartbeat", v1, o1, r1.heartbeat_once),
                              ("backfill", v1, o1, lambda: r1.backfill(budget=1, force=True)),
                              ("backups' pass", v2, o2, r2.reconcile_once), ("gate", v2, o2, r2.gate_pass),
                              ("backups' heartbeat", v2, o2, r2.heartbeat_once)):
        v.reads = o.reads = 0
        step()
        out[label] = v.reads + o.reads
    return out


def test_a_recorders_pass_reads_each_recording_once_not_once_per_recording():
    """At a thousand recordings and five hundred backups, each part of a recorder's pass reads the store about once
    per row it has to know (measured: 1022, 24, 1531, 2030, 1508, 24) — under two reads a recording, where the walks
    per recording read 3 032 003 for one backfill pass. And twice the recordings is at most twice the reads: the cost
    is linear in the recordings, not their square (which would be four times)."""
    half, full = _reads_per_pass(500), _reads_per_pass(1000)
    ceiling = {"pass": 1100, "heartbeat": 50, "backfill": 1600, "backups' pass": 2100, "gate": 1600, "backups' heartbeat": 50}
    for part, limit in ceiling.items():
        assert full[part] <= limit, (part, full[part], limit)
        assert full[part] <= 2 * half[part] + 10, (part, half[part], full[part])


def test_a_pass_reads_the_rows_and_heartbeats_once_and_the_next_pass_reads_them_again():
    """One look a pass: within the pass every recording's question is answered from it — the rows listed once, the
    recorders' heartbeats once, the holders' once — and what it read is not kept past the pass: a camera that moved to
    another holder between two passes is re-subscribed on the second, as it always was."""
    box = _site(100)
    r, vars_, objects = _recorder(box, "r-1", "srv-a")
    lists = []
    real_vars, real_objects = vars_.list, objects.list
    vars_.list = lambda prefix, *a, **kw: lists.append(prefix) or real_vars(prefix, *a, **kw)
    objects.list = lambda prefix, *a, **kw: lists.append(prefix) or real_objects(prefix, *a, **kw)
    r.reconcile_once()
    r.backfill(budget=1, force=True)
    assert lists.count("rec/recordings/") == 1 and lists.count("vms/heartbeats/") == 2      # the pass, then the backfill
    assert lists.count("rec/heartbeats/") == 1                                               # backfill's backup sources
    assert r.sources["7"] == "rtsp://srv-1:8554/7"
    with r.looking():                                        # a pass that lasts: read again after a heartbeat's period
        r.source("7"), r.source("8")
        box.clock.advance(r._look().FRESH)
        r.source("7")
    assert lists.count("vms/heartbeats/") == 4
    now = box.wall()
    box.objects.put(SPEC.sub.heartbeat_key("w-1"), Heartbeat("w-1", now, [
        {"id": str(i), "phase": "running", "live_url": f"rtsp://srv-9:8554/{i}"} for i in range(1, 51)], {"server": "srv-9"}).to_bytes())
    assert "7" in r.resubscribe()                                                            # the next look sees the move
    box.clock.advance(60)                                                                    # past the reconciler's backoff
    box.objects.put(SPEC.sub.heartbeat_key("w-1"), Heartbeat("w-1", now + 60, [             # …the holder beating on: fresh
        {"id": str(i), "phase": "running", "live_url": f"rtsp://srv-9:8554/{i}"} for i in range(1, 51)], {"server": "srv-9"}).to_bytes())
    r.reconcile_once()
    assert r.sources["7"] == "rtsp://srv-9:8554/7"


def test_a_store_that_does_not_answer_is_asked_once_a_pass_and_every_recording_keeps_its_last_source():
    """The look remembers the store's silence for the pass too. The holders' heartbeats unreadable: every running
    recording's question — has its camera moved — is answered by the source it read last (the review's second pass,
    blocker 4), each counted in `store_errors` as before, and the store is asked ONCE for the pass, not once for each of
    a hundred recordings."""
    box = _site(100)
    r, _, objects = _recorder(box, "r-1", "srv-a")
    r.reconcile_once()
    before = dict(r.sources)
    objects.fail, errors, lists = "vms/heartbeats/", r.store_errors, []
    real = objects.list
    objects.list = lambda prefix, *a, **kw: lists.append(prefix) or real(prefix, *a, **kw)
    assert r.reconcile_once() == [] and r.sources == before                                 # nothing stopped, nothing moved
    assert lists.count("vms/heartbeats/") == 1 and r.store_errors - errors == 100


def _placement_site(n: int, recorders: int):
    box = Box()
    box.vars = open_vars("memory://")
    now = box.wall()
    volumes.write(box.vars, {"name": "copy", "kind": "backup", "server": "srv-b", "url": "/tmp/copy", "quota_bytes": 64 << 20})
    per: list[list[dict]] = [[] for _ in range(recorders)]
    for i in range(1, n + 1):
        box.vars.put(f"vms/cameras/{i}", {"id": str(i), "name": f"c{i}", "source": f"driverpack://file/{i}", "enabled": "true"})
        box.vars.put(f"rec/recordings/{i}", {"id": str(i), "name": str(i), "cam": str(i), "home": "disks"})
        per[i % recorders].append({"id": str(i), "cam": str(i), "phase": "running"})
        if i % 2:
            box.vars.put(f"rec/recordings/{i}-copy", {"id": f"{i}-copy", "name": f"{i}-copy", "cam": str(i), "home": "copy"})
            per[(i + 1) % recorders].append({"id": f"{i}-copy", "cam": str(i), "phase": "running"})
    for k, st in enumerate(per):
        box.objects.put(REC_SPEC.sub.heartbeat_key(f"r-{k}"), Heartbeat(f"r-{k}", now, st, {"server": f"srv-{k}"}).to_bytes())
    return box


def _near_reads(n: int) -> tuple[int, dict, dict]:
    from vms.controller import VmsController
    box = _placement_site(n, recorders=n // 50)
    vars_, objects = Counting(box.vars), Counting(box.objects)
    ctl = VmsController(vars_, objects, wall=box.wall)
    rows = ctl.units()
    alone = {str(r["id"]): ctl.holder_near(r["id"]) for r in rows[:40]}
    vars_.reads = objects.reads = 0
    near = ctl.near_index()
    homes = {str(r["id"]): ctl.home_for(r, near) for r in rows}
    held = {str(r["id"]): ctl.holder_near(r["id"], near) for r in rows[:40]}
    assert held == alone                                     # one look or a look each: the same worker, the same server
    return vars_.reads + objects.reads, homes, held


def test_where_a_thousand_cameras_belong_is_found_in_one_look_at_the_recorders():
    """`ensure_home` asks `home_for` of every camera, `_pick` asks `holder_near` of every camera it places. Each read
    every recorder's heartbeat and ranked every tie from the store: 25 500 reads for a thousand cameras beside twenty
    recorders. From one look (`near_index`), handed in: the recorders' heartbeats once, which volumes are backups once,
    and each tied recording's row once — 1023 measured, under the ceiling of 1100; twice the cameras, at most twice the
    reads. The camera follows its BACKUP recording, as `rank_near_recording` says, and the answers are the ones each
    camera asked alone gets."""
    half, _, _ = _near_reads(500)
    full, homes, held = _near_reads(1000)
    assert full <= 1100 and full <= 2 * half + 10, (half, full)
    assert homes["1"] == "srv-2" and homes["2"] == "srv-2"   # 1 beside `1-copy` on r-2; 2 has one recording, on r-2
    assert held["1"] == ("r-2", "srv-2")


def test_a_holder_whose_clock_runs_behind_stays_the_recordings_source_while_it_beats():
    """The review's thirteenth pass, blocker 4's sibling on the data path: a recorder found the holder of its camera by
    the holder's `ts` against its own clock, so a holder whose server's clock ran 50 s behind was "not live" while it
    held the camera and served its fan-out — no source, the recording waiting for nobody. Now the recorder asks whether
    the holder's heartbeat CHANGED within 45 s of its own clock (`RecWorker.eyes`): a holder 100 s behind is the source
    while it beats, and once it stops it is not, a silence's length later by the recorder's clock."""
    box = _site(1)
    now = box.wall()

    def beat(ts):
        box.objects.put(SPEC.sub.heartbeat_key("w-1"), Heartbeat("w-1", ts, [
            {"id": "1", "phase": "running", "live_url": "rtsp://srv-1:8554/1"}], {"server": "srv-1"}).to_bytes())
    beat(now - 100)                                                          # its clock: a hundred seconds behind
    r, _, _ = _recorder(box, "r-1", "srv-a")
    r.reconcile_once()
    assert r.sources.get("1") == "rtsp://srv-1:8554/1"
    for k in range(1, 4):                                                    # it beats on, every ten seconds
        box.clock.advance(10); box.wall.advance(10); beat(now - 100 + 10 * k)
        assert r.source("1") == ("srv-1", "rtsp://srv-1:8554/1"), k
    box.clock.advance(46); box.wall.advance(46)                              # and stops
    r.last_holder.pop("1", None)                                             # (the store's word on who holds it aside)
    assert r.source("1") is None
