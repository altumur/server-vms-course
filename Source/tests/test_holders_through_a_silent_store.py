"""The VMS's holders and recorders through a store that stops answering (feedback BC, BK) — what each does with the
platform's answers (`tests/test_store_outage.py` proves those on testsub):

    a pipeline that fell over       comes back under the epoch the holder already holds (`VmsWorker._actuate`): the
                                    platform gives no new epoch on an assignment not read, and the held lease still
                                    allows data
    recording unconfirmed           the holder's ceiling is its spec's (`lease.unconfirmed_max`), its status and its
                                    metrics say how long a camera has recorded past its lease
    a relay is not data             a command waits for the store's word; a camera never started has no epoch to record under
    a recorder's place              its own disk stays, a network archive is let go; a fallen pipeline restarts on the
                                    source read last
"""
from vms.worker import FakeActuator, VmsWorker
from tests.test_lesson4_worker import _box_with_cameras
from tests.test_store_outage import Flaky, OneRead, _silence


def _worker(n=2, env=None):
    box, ctl = _box_with_cameras(n)
    ctl.assign("w-1", [str(i) for i in range(1, n + 1)])
    store, act = Flaky(box.vars), FakeActuator()
    w = VmsWorker("w-1", store, box.objects, act, clock=box.clock, wall=box.wall, resource_root=box.resource_root, env=env)
    w.claim_slot(prefer="w-1")
    w.reconcile_once()
    assert act.running == set(range(1, n + 1))
    return box, ctl, store, act, w


def test_a_pipeline_that_fell_while_the_store_is_away_comes_back_under_the_epoch_it_holds():
    """Sixteen seconds without the store: the cameras record under the same epochs, nothing is fenced, the pass
    goes on with the assignment read last — and a pipeline that fell over meanwhile is noticed."""
    box, ctl, store, act, w = _worker()
    store.down = True
    box.clock.advance(16); box.wall.advance(16)
    assert w.reconcile_once() == []                                   # nothing stopped: the last assignment stands
    assert w.lease_pass() == [] and w.writing_allowed               # the slot: not confirmed, and still mine
    assert act.running == {1, 2} and act.epochs == {1: 1, 2: 1} and w.store_errors == 2
    act.dead.append(1)                                                # a pipeline falls over while the store is away
    w.pump_once()                                                     # noticed: the pump is local (the requests are not, and wait)
    box.clock.advance(5); box.wall.advance(5)
    assert w.reconcile_once() == [("start", 1)]                       # it comes back under the epoch this worker holds:
    assert act.running == {1, 2} and act.epochs == {1: 1, 2: 1}       # the same writer — nobody could be given another number
    store.down = False
    assert w.lease_pass() == [] and w.reconcile_once() == [] and act.epochs == {1: 1, 2: 1}


def test_a_holder_says_in_its_status_and_metrics_how_long_it_has_recorded_unconfirmed():
    """A lease that ran out while the store was SILENT is not a lease somebody took. The cameras record on under
    the epochs they have — a frame under an old epoch harms nothing: the epoch is in the path, and a second writer
    would cost a duplicate, where stopping costs a hole. On one box there is nobody to protect them from: the
    store is a directory on the same disk, away for everybody at once."""
    box, ctl, store, act, w = _worker()
    assert w.unconfirmed_max is None                                  # one box, nothing said: no ceiling
    store.down = True
    assert _silence(box, w, 600) == [] and act.running == {1, 2} and act.epochs == {1: 1, 2: 1}
    assert not w.may_act("1") and w.may_write("1")                 # the strict question says no; the data one says yes
    st = {s["id"]: s for s in w.status()}
    assert st[1]["lease"] == "unconfirmed" and 570 <= st[1]["unconfirmed_s"] <= 580
    w.objects = box.objects; w.heartbeat_once()
    from w2cplatform.console import SpecConsole
    text = SpecConsole(ctl, wall=box.wall).metrics_text()
    assert 'vms_worker_unconfirmed{worker="w-1"} 2' in text

    store.down = False
    assert w.lease_pass() == [] and act.running == {1, 2} and act.epochs == {1: 1, 2: 1}   # confirmed: no stop, no seam
    assert w.may_act("1") and "lease" not in w.status()[0] and w.unconfirmed() == {}


def test_the_holders_unconfirmed_max_is_its_specs_and_off_stops_data_at_the_leases_end():
    """How long a holder records on past a lease the silent store did not confirm is its spec's (`lease:
    {unconfirmed_max}`; the architect, 5 Oct — the environment's `UNCONFIRMED_MAX` is gone): the VMS's is `forever`
    (footage carries its epoch: a second writer is a duplicate), `<seconds>` records on up to that long past the
    lease's end, and `off` — the platform's default — stops the camera when the lease is not confirmed in time."""
    from vms import worker as vw
    from tests.conftest import in_catalogue
    assert vw.SPEC.unconfirmed_max is None and _worker()[4].unconfirmed_max is None
    for said in (60, "off"):
        with in_catalogue(_spec_with(said)):                         # the spec its worker runs by: the catalogue's
            box, ctl, store, act, w = _worker()
            store.down = True
            if said == 60:
                assert w.unconfirmed_max == 60.0
                assert _silence(box, w, 80) == [] and act.running == {1, 2}   # 25 s of lease + 55 s unconfirmed
                assert sorted(_silence(box, w, 16)) == ["1", "2"] and act.running == set() and w.writing_allowed
            else:
                assert w.unconfirmed_max == 0.0
                assert _silence(box, w, 24) == [] and sorted(_silence(box, w, 8)) == ["1", "2"]


def _spec_with(unconfirmed_max):
    """The VMS's spec, its `lease.unconfirmed_max` said otherwise."""
    import os

    import yaml
    from tests.productdir import SOURCE
    from w2cplatform.spec import SubsystemSpec
    with open(os.path.join(SOURCE, "vms", "vms.subsystem.yaml"), encoding="utf-8") as f:
        d = yaml.safe_load(f)
    return SubsystemSpec.from_dict({**d, "lease": {"unconfirmed_max": unconfirmed_max}})


def test_a_camera_never_started_waits_and_an_action_waits_for_the_stores_word():
    """Data goes on; two things do not. A camera this worker has not started has no epoch to record under — it
    waits. And a command is not data: a relay pulsed by a worker that may have been replaced is pulsed twice."""
    from vms.config import SPEC
    from tests.vmsconftest import Box
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
    assert w.may_write(str(door)) and str(late) not in w.epochs      # no epoch for it: it waits
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
    serve is let go when its hold has gone unconfirmed for its TTL — two writers in one archive is damage — because
    the spec says so next to the place (`placement.places.lease: strict`): a spec that does not keeps it too."""
    import os

    import yaml
    from vms import volumes
    from vms.recworker import RecWorker
    from w2cplatform.spec import SubsystemSpec
    from tests.productdir import SOURCE
    from tests.vmsconftest import Box
    from tests.test_volumes import _recorder
    with open(os.path.join(SOURCE, "vms", "rec.subsystem.yaml"), encoding="utf-8") as f:
        d = yaml.safe_load(f)
    places = {k: v for k, v in d["placement"]["places"].items() if k != "lease"}
    from tests.conftest import in_catalogue
    from vms.config import REC_SPEC
    loose = SubsystemSpec.from_dict({**d, "placement": {**d["placement"], "places": places}})
    for kind, stays, spec in (("local", True, REC_SPEC), ("network", False, REC_SPEC), ("network", True, loose)):
        box = Box()
        row = {"name": "vol", "kind": kind, "url": os.path.join(box.root, "vol"), "quota_bytes": 10 ** 9}
        volumes.write(box.vars, {**row, "server": "srv-a"} if kind == "local" else row)
        with in_catalogue(spec):                                     # the spec the recorder runs by: the catalogue's
            r = _recorder(box, "r-1", "srv-a")
        assert r.lease_pass() == [] and r.hold == "vol" and r.volume == "vol"
        r.vars = Flaky(box.vars); r.vars.down = True
        box.clock.advance(8); box.wall.advance(8)
        r.lease_pass()
        assert r.hold == "vol" and r.volume == "vol" and r.store_errors >= 1      # one error: nothing is let go
        for _ in range(8):
            box.clock.advance(8); box.wall.advance(8); r.lease_pass()
        assert (r.hold == "vol") is stays and (r.volume == "vol") is stays, (kind, spec.places)


def test_a_recorder_whose_store_is_away_restarts_a_fallen_pipeline_on_the_source_it_read_last():
    """The review's second pass, blocker 4. The recorder's pass began by reading the camera's holder — from the
    object store, which on a cluster is the same store — and the OSError ended the pass: no restart of a pipeline
    that fell over, no watch on the writer, for as long as the store was away. The store that does not answer
    says nothing: the source read last stands, and the other parts of the pass run."""
    from vms.config import live_shm
    from vms.recworker import RecWorker
    from tests.vmsconftest import REC_ACL, TEST_BLOCK, TEST_QUOTA, TEST_READ, obsd_session
    from tests.test_lesson5_recorder import _box
    box, ctl, con, rec_con, rec_ctl, w = _box()
    vars_, objects = Flaky(box.vars.as_writer("recworker-r-1", REC_ACL)), Flaky(box.objects)
    act = FakeActuator()
    r = RecWorker("r-1", vars_, objects, act, clock=box.clock, wall=box.wall, server="srv-1", resource_root=box.resource_root,
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


def _moved_away(n=2):
    """w-1 holds cameras 1 and 2 on a store that can refuse one read. Camera 1 goes to w-2, which starts it under
    epoch 2; w-1's lease step finds the newer epoch and lets camera 1 go."""
    box, ctl = _box_with_cameras(n)
    ctl.assign("w-1", [str(i) for i in range(1, n + 1)])
    store, act = OneRead(box.vars), FakeActuator()
    w = VmsWorker("w-1", store, box.objects, act, clock=box.clock, wall=box.wall, resource_root=box.resource_root)
    w.claim_slot(prefer="w-1")
    assert len(w.reconcile_once()) == n
    act2 = FakeActuator()
    w2 = VmsWorker("w-2", box.vars, box.objects, act2, clock=box.clock, wall=box.wall, resource_root=box.resource_root)
    w2.claim_slot(prefer="w-2")
    ctl.assign("w-1", [str(i) for i in range(2, n + 1)]); ctl.assign("w-2", ["1"])
    assert w2.reconcile_once() == [("start", 1)] and act2.epochs == {1: 2}
    assert w.lease_pass() == ["1"] and 1 not in act.running
    return box, store, act, w, act2, w2


def test_a_fallen_pipeline_of_a_camera_still_held_comes_back_under_its_epoch_when_the_assignment_read_failed():
    """The other side of the rule: what this worker HOLDS is not taken from anyone by restarting it. Camera 2's
    pipeline falls over in a pass whose assignment read failed: it comes back under the epoch it holds (feedback BK),
    not a new one, and not never."""
    box, store, act, w, act2, w2 = _moved_away()
    store.refused = {"vms/workers/w-1"}
    act.dead.append(2); w.pump_once()
    box.clock.advance(5); box.wall.advance(5)                         # inside camera 2's lease
    assert ("start", 2) in w.reconcile_once() and act.epochs[2] == 1 and act.running == {2}
    assert int(box.vars.get("vms/epoch/2")[0]["epoch"]) == 1
