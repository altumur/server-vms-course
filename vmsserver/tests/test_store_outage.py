"""A worker and a store that stops answering — and what a lost lease means (feedback BC).

Three rules, each learned on the product's box with the store of one cluster taken away (`chmod 000`):

    not knowing is not "no"    a store that did not answer says nothing: the worker goes on with the assignment it
                               read last, and its slot is still its own. Only a slot row READ, with another holder
                               in it, says "no"
    a lease is one camera's    lost however it was lost, one pipeline stops and gives its epoch up; if the camera
                               is still this worker's it is started again under a new epoch. The instance is not
                               fenced, and its other cameras are not stopped
    a fence is not for ever    a fenced instance takes a free slot on its next pass and starts from nothing
"""
import threading

from w2cplatform.epoch import Lease, next_epoch
from vms.worker import FakeActuator, VmsWorker
from tests.test_lesson4_worker import _box_with_cameras


class Flaky:
    """A store, and a switch: down, every read and write is an OSError — what a directory with its mode taken
    away gives, or a cluster's API that does not answer."""

    def __init__(self, inner):
        self.inner, self.down = inner, False

    def __getattr__(self, name):
        attr = getattr(self.inner, name)
        if not callable(attr) or name not in ("get", "put", "delete", "list"):
            return attr

        def call(*a, **kw):
            if self.down:
                raise PermissionError(13, "the store does not answer")
            return attr(*a, **kw)
        return call


def _worker(n=2, env=None):
    box, ctl = _box_with_cameras(n)
    ctl.assign("w-1", [str(i) for i in range(1, n + 1)])
    store, act = Flaky(box.vars), FakeActuator()
    w = VmsWorker("w-1", store, box.objects, act, clock=box.clock, wall=box.wall, archive_root=box.archive, env=env)
    w.claim_slot(prefer="w-1")
    w.reconcile_once()
    assert act.running == set(range(1, n + 1))
    return box, ctl, store, act, w


def test_a_store_that_does_not_answer_is_not_an_empty_assignment():
    """Sixteen seconds without the store: the cameras record under the same epochs, nothing is fenced, the pass
    goes on with the assignment read last — and a pipeline that fell over meanwhile is noticed."""
    box, ctl, store, act, w = _worker()
    store.down = True
    box.clock.advance(16); box.wall.advance(16)
    assert w.reconcile_once() == []                                   # nothing stopped: the last assignment stands
    assert w.lease_pass() == [] and w.recording_allowed               # the slot: not confirmed, and still mine
    assert act.running == {1, 2} and act.epochs == {1: 1, 2: 1} and w.store_errors == 2
    act.dead.append(1)                                                # a pipeline falls over while the store is away
    w.pump_once()                                                     # noticed: the pump is local (the requests are not, and wait)
    box.clock.advance(5); box.wall.advance(5)
    assert w.reconcile_once() == [("start", 1)]                       # it comes back under the epoch this worker holds:
    assert act.running == {1, 2} and act.epochs == {1: 1, 2: 1}       # the same writer — nobody could be given another number
    store.down = False
    assert w.lease_pass() == [] and w.reconcile_once() == [] and act.epochs == {1: 1, 2: 1}


def test_a_lease_that_ran_out_with_nobody_asking_stops_that_camera_and_it_comes_back_under_a_new_epoch():
    """Thirty-six seconds in which this worker asked nothing — a GC pause, a suspended VM — and then a store
    that does not answer. That is not silence (feedback BK): the lease ran out while nobody was asking, and
    somebody may have been given the cameras meanwhile. They stop — each with the reason in the log — and the
    instance is NOT fenced. The store returns, and the reconciler starts them again under the next epoch.
    Silence counts from a renewal that failed while the lease was still good; see the tests at the end."""
    box, ctl, store, act, w = _worker()
    store.down = True
    box.clock.advance(36); box.wall.advance(36)
    assert sorted(w.lease_pass()) == ["1", "2"]
    assert act.running == set() and w.epochs == {} and w.recording_allowed and w.fenced_reason is None
    store.down = False
    box.clock.advance(60); box.wall.advance(60)                       # past any backoff
    w.reconcile_once()
    assert act.running == {1, 2} and act.epochs == {1: 2, 2: 2}
    assert w.lease_pass() == []


def test_a_camera_in_two_assignments_costs_one_pipeline_not_fifty():
    """Camera 1 is listed on two workers for the seconds a controller takes to mend it. The other worker took the
    next epoch. This worker used to read that as "another instance of me holds it: I am a zombie" and stop every
    camera it had. Its slot was renewed a line before — there is no other instance of it."""
    box, ctl, store, act, w = _worker()
    next_epoch(box.vars, "vms/epoch/1")                               # somebody else started camera 1
    assert w.lease_pass() == ["1"]
    assert w.recording_allowed and act.running == {2} and "1" not in w.epochs
    assert w.conflicts() == 0 and w.lease_pass() == []                # camera 2 is untouched; nothing left to lose


def test_only_a_slot_row_naming_another_holder_fences_and_a_fence_is_not_for_ever():
    """The replacement took w-1. The old instance reads the slot row, finds another holder and fences — that is a
    "no". It used to stay so: alive, heartbeating `fenced: true`, recording nothing until somebody restarted it.
    On its next pass it takes a free slot and starts from nothing — a process that took whatever was free; one named by
    its unit takes its own name back only (`test_names.py`)."""
    box, ctl, store, act, a = _worker(1)
    a.given = None                                                    # not named by its unit: any free slot will do
    box.wall.advance(46)                                              # a long pause: the slot lapsed
    b = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall)
    assert b.name == "w-1"
    assert a.lease_pass() == ["1"] and not a.recording_allowed and "slot w-1" in a.fenced_reason
    assert a.rejoin() == "w-2" and a.recording_allowed and a.was_fenced and a.fenced_reason is None
    assert a.epochs == {} and a.rows == [] and a.reconciler.actual == {}
    ctl.assign("w-2", ["1"])
    assert a.reconcile_once() == [("start", 1)]                       # whatever ITS slot's assignment says, from nothing
    assert b.lease_pass() == []                                       # and the replacement never noticed


def test_a_lease_runs_from_before_the_read_not_from_after_it():
    """A holder paused for a minute between reading the epoch row and stamping the renewal woke up with a fresh
    lease it had in fact slept through."""
    box, ctl = _box_with_cameras(1)
    epoch, _ = next_epoch(box.vars, "vms/epoch/1")

    class Slow:
        def get(self, key):
            out = box.vars.get(key)
            box.clock.advance(60)                                     # the pause: a GC, a stalled disk
            return out

    lease = Lease(Slow(), "vms/epoch/1", epoch, 30.0, 5.0, box.clock)
    assert lease.renew() is True                                      # the row said "yours" — a minute ago
    assert lease.may_write() is False and lease.seconds_left() == 0


def test_the_pump_does_not_wait_for_the_pass_over_the_store():
    """What is local — the buses, the devices' events, the spool — is drained whether or not the pass succeeded.
    They shared one `try`, and a pass that raised skipped the pump, every pass."""
    box, ctl, store, act, w = _worker(1)
    pumps = []
    w.reconcile_once = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("the pass raised"))
    w.pump_once = lambda: pumps.append(1)

    class Twice:
        def __init__(self): self.n = 0
        def is_set(self): self.n += 1; return self.n > 2
        def wait(self, s): return None
        def set(self): pass

    w.run(poll=0, stop=Twice())
    assert len(pumps) == 2


# -- recording through a silent store (feedback BK) -------------------------------------------------------

def _silence(box, w, seconds, step=8):
    """The loop, for `seconds`: a lease pass and a reconcile every `step` — the store asked each time."""
    out = []
    for _ in range(int(seconds // step)):
        box.clock.advance(step); box.wall.advance(step)
        out += w.lease_pass()
        w.reconcile_once()
    return out


def test_ten_minutes_of_silence_stop_nothing_and_the_store_coming_back_stops_nothing_either():
    """A lease that ran out while the store was SILENT is not a lease somebody took. The cameras record on under
    the epochs they have — a frame under an old epoch harms nothing: the epoch is in the path, and a second writer
    would cost a duplicate, where stopping costs a hole. On one box there is nobody to protect them from: the
    store is a directory on the same disk, away for everybody at once."""
    box, ctl, store, act, w = _worker()
    assert w.unconfirmed_max is None                                  # one box, nothing said: no ceiling
    store.down = True
    assert _silence(box, w, 600) == [] and act.running == {1, 2} and act.epochs == {1: 1, 2: 1}
    assert not w.may_write("1") and w.may_record("1")                 # the strict question says no; the data one says yes
    st = {s["id"]: s for s in w.status()}
    assert st[1]["lease"] == "unconfirmed" and 570 <= st[1]["unconfirmed_s"] <= 580
    w.objects = box.objects; w.heartbeat_once()
    from w2cplatform.console import SpecConsole
    text = SpecConsole(ctl, wall=box.wall).metrics_text()
    assert 'vms_worker_unconfirmed{worker="w-1"} 2' in text

    store.down = False
    assert w.lease_pass() == [] and act.running == {1, 2} and act.epochs == {1: 1, 2: 1}   # confirmed: no stop, no seam
    assert w.may_write("1") and "lease" not in w.status()[0] and w.unconfirmed() == {}


def test_a_camera_given_to_somebody_else_during_the_silence_stops_at_the_stores_first_answer():
    box, ctl, store, act, w = _worker()
    store.down = True
    _silence(box, w, 120)
    next_epoch(box.vars, "vms/epoch/1")                               # another worker reached the store and started camera 1
    store.down = False
    assert w.lease_pass() == ["1"] and act.running == {2} and w.recording_allowed


def test_the_ceiling_and_off():
    """A cluster's store is on the network: a worker cut off from it may hold the camera's session while its
    successor cannot connect. `UNCONFIRMED_MAX` is how long past the lease's end it records on; `off` is the old
    behaviour — a lease not confirmed in time stops its camera."""
    box, ctl, store, act, w = _worker(env={"UNCONFIRMED_MAX": "60"})
    store.down = True
    assert _silence(box, w, 80) == [] and act.running == {1, 2}       # 25 s of lease + 55 s unconfirmed: under the ceiling
    assert sorted(_silence(box, w, 16)) == ["1", "2"] and act.running == set() and w.recording_allowed

    box, ctl, store, act, w = _worker(env={"UNCONFIRMED_MAX": "off"})
    store.down = True
    assert _silence(box, w, 24) == [] and sorted(_silence(box, w, 8)) == ["1", "2"]


def test_a_camera_never_started_waits_and_an_action_waits_for_the_stores_word():
    """Data goes on; two things do not. A camera this worker has not started has no epoch to record under — it
    waits. And a command is not data: a relay pulsed by a worker that may have been replaced is pulsed twice."""
    from vms.config import SPEC
    from tests.conftest import Box
    from tests.test_group_by import _ctl, _holder, _worker as _placed
    box = Box(); ctl, con = _ctl(box)
    door = con.create_camera({"name": "front door", "source": "driverpack://acme/10.0.0.90/ch/1"})["id"]
    _placed(box, "w-1", "srv-a"); ctl.ensure_placed()
    w = _holder(box, relays=2)
    store = Flaky(box.vars)
    w.vars = store
    w.reconcile_once()
    late = con.create_camera({"name": "late", "source": "driverpack://acme/10.0.0.91/ch/1"})["id"]
    ctl.ensure_placed(); w.refresh()                                  # assigned, and not yet started
    store.down = True
    _silence(box, w, 40)
    assert w.may_record(str(door)) and str(late) not in w.epochs      # no epoch for it: it waits
    assert late not in w.actuator.running

    store.down = False
    con.vars.put(SPEC.sub.request_key("r1"), {"unit": str(door), "action": "output", "port": "1",
                                              "valid_until": str(box.wall() + 60)})
    w.leases[str(door)].vars = Flaky(box.vars); w.leases[str(door)].vars.down = True      # the row is read; the lease is still unconfirmed
    assert w.requests() == [] and w.devices["acme/10.0.0.90"].did == []                  # not performed
    w.leases[str(door)].vars.down = False
    w.lease_pass()
    assert [d["request"] for d in w.requests()] == ["r1"]             # confirmed: it acts


def test_a_recorders_own_disk_stays_its_own_and_a_network_archive_is_let_go():
    """The place, while the store is silent. Not reading the list of volumes is not "nothing is declared", and
    not reading the hold is not "somebody else holds it": the recorder used to be one store error away from
    dropping its archive and every recording on it. A disk of this server stays. A network archive any box may
    serve is let go when its hold has gone unconfirmed for its TTL — two writers in one archive is damage."""
    import os
    from vms import volumes
    from tests.conftest import Box
    from tests.test_volumes import _recorder
    for kind, stays in (("local", True), ("network", False)):
        box = Box()
        row = {"name": "vol", "kind": kind, "url": os.path.join(box.root, "vol"), "quota_bytes": 10 ** 9}
        volumes.write(box.vars, {**row, "server": "srv-a"} if kind == "local" else row)
        r = _recorder(box, "r-1", "srv-a")
        assert r.lease_pass() == [] and r.hold == "vol" and r.volume == "vol"
        r.vars = Flaky(box.vars); r.vars.down = True
        box.clock.advance(8); box.wall.advance(8)
        r.lease_pass()
        assert r.hold == "vol" and r.volume == "vol" and r.store_errors >= 1      # one error: nothing is let go
        for _ in range(8):
            box.clock.advance(8); box.wall.advance(8); r.lease_pass()
        assert (r.hold == "vol") is stays and (r.volume == "vol") is stays, kind



def test_a_recorder_whose_store_is_away_restarts_a_fallen_pipeline_on_the_source_it_read_last():
    """The review's second pass, blocker 4. The recorder's pass began by reading the camera's holder — from the
    object store, which on a cluster is the same store — and the OSError ended the pass: no restart of a pipeline
    that fell over, no watch on the writer, for as long as the store was away. The store that does not answer
    says nothing: the source read last stands, and the other parts of the pass run."""
    from vms.config import live_shm
    from vms.recworker import RecWorker
    from tests.conftest import REC_ACL, TEST_BLOCK, TEST_QUOTA, TEST_READ, obsd_session
    from tests.test_lesson5_recorder import _box
    box, ctl, con, rec_con, rec_ctl, w = _box()
    vars_, objects = Flaky(box.vars.as_writer("recworker-r-1", REC_ACL)), Flaky(box.objects)
    act = FakeActuator()
    r = RecWorker("r-1", vars_, objects, act, clock=box.clock, wall=box.wall, server="srv-1", archive_root=box.archive,
                  block=TEST_BLOCK, read=TEST_READ, default_quota=TEST_QUOTA, obsd=obsd_session("rec-outage"),
                  env={"ARCHIVE_VOLUME": f"file://{box.root}/vol-srv-1"})
    r.lease_pass(); r.heartbeat_once()
    rec_con.create({"name": "1-main", "cam": "1"}); rec_ctl.ensure_placed()
    assert r.reconcile_once() == [("start", "1-main")] and act.started["1-main"]["source"] == live_shm(1)
    vars_.down = objects.down = True
    box.clock.advance(5); box.wall.advance(5)
    assert r.reconcile_once() == []                                   # the store away: nothing stopped, nothing fenced
    act.dead.append("1-main"); r.pump_once()                          # the pipeline falls over meanwhile
    box.clock.advance(5); box.wall.advance(5)
    assert r.reconcile_once() == [("start", "1-main")]                # restarted — on the source read last, under the held epoch
    assert act.started["1-main"]["source"] == live_shm(1) and act.started["1-main"]["epoch"] == 1 and r.store_errors > 0
    vars_.down = objects.down = False
    assert r.reconcile_once() == [] and act.running == {"1-main"}
