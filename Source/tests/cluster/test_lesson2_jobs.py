"""Lesson 2 — workers, resources and the controller as units on every server. The name from the unit
(`WORKER_NAME=w-%l-1`) and the labels from the server; a spare that takes an offer and stops; two processes with one
name; rights by the socket a process came through."""
from vms.controller import VmsController
from w2cplatform.cluster.variables import Forbidden
from tests.cluster.conftest import Cluster


def _cluster(n_cams=6, capacity=4):
    c = Cluster(); ctl = c.controller("srv-b", capacity=capacity)
    con = c.console()
    for i in range(n_cams):
        con.create_camera({"source": f"driverpack://file/{i}.mp4"})
    return c, ctl, con


def test_the_name_comes_from_the_unit_and_the_labels_from_the_server():
    c, ctl, _ = _cluster()
    a, b = c.worker("srv-a", capacity=4), c.worker("srv-b", capacity=4)
    assert (a.name, b.name) == ("w-srv-a-1", "w-srv-b-1")
    a.heartbeat_once(); b.heartbeat_once()
    hb = ctl.workers_seen()
    assert hb["w-srv-a-1"].extra["server"] == "srv-a" and hb["w-srv-a-1"].extra["labels"] == "vlan:cctv-a"
    assert hb["w-srv-b-1"].extra["labels"] == "vlan:cctv-a,vlan:cctv-b" and hb["w-srv-b-1"].extra["alloc"] == b.instance
    assert ctl.slots()["w-srv-b-1"].holder == b.instance == "srv-b:4102:001006"      # the claim names the process, host and pid


def test_a_spare_takes_an_offer_then_stops():
    """No orchestrator scales anything. The workers are full, a ninth camera waits: the controller's pass counts the
    shortage and writes an OFFER — an empty slot row with the label set it is for (`w-2`, the next free number);
    `w2c-spares.sh` on srv-c starts a spare for that set (`SPARE_FOR=`), it takes the offer by CAS and the camera lands
    on it. Stopped in order — SIGTERM, `release_slot` — its camera moves in one pass. The controller started no process
    and stopped none."""
    c, ctl, con = _cluster(n_cams=8)
    ws = [c.worker("srv-a", capacity=4), c.worker("srv-b", capacity=4)]
    for w in ws: w.heartbeat_once()
    ctl.pass_once(1)
    for w in ws: w.reconcile_once(); w.heartbeat_once()
    assert ctl.headroom() == 0 and sum(ctl.load(w.name) for w in ws) == 8
    con.create_camera({"source": "driverpack://file/9.mp4"})
    rep = ctl.pass_once(1)
    assert ctl.where(9) is None and rep["workers_needed"] == {"": 1} and rep["spare_offers"] == {"": 1}, rep
    assert ctl.slots()["w-2"].offered() and ctl.slots()["w-2"].holder == ""
    spare = c.worker("srv-c", capacity=4, spare_for="")
    assert spare.name == "w-2" and ctl.slots()["w-2"].holder == spare.instance and not ctl.slots()["w-2"].offered()
    spare.heartbeat_once()
    rep = ctl.pass_once(1)
    assert ctl.where(9) == "w-2" and "on srv-c" in ctl.placement(9).reason and rep["workers_needed"] == {"": 0}
    spare.reconcile_once(); spare.release_slot()                            # `systemctl stop vms-vmsworker-spare-1`
    con.delete_camera(1); con.delete_camera(2)                               # room to move into
    ctl.pass_once(1)
    assert ctl.where(9) in ("w-srv-a-1", "w-srv-b-1") and ctl.assignment("w-2").units == []


def test_two_processes_with_one_name_resolve_at_the_cas():
    """The unit restarted while the old process still lived — hung past its stop, or an operator's second copy by
    hand. The name is the unit's; the slot row is the proof. The second claim takes the name outright; the first is
    fenced at its next renewal."""
    c, ctl, _ = _cluster(2)
    a = c.worker("srv-a"); ctl.assign(a.name, ["1", "2"]); a.reconcile_once()
    b = c.worker("srv-a")                                                     # the same unit's name, a second process
    assert b.name == a.name == "w-srv-a-1" and b.instance != a.instance
    assert ctl.slots()["w-srv-a-1"].holder == b.instance and ctl.slots()["w-srv-a-1"].gen == 2
    assert a.lease_pass() and not a.writing_allowed and "slot w-srv-a-1" in a.fenced_reason
    assert b.reconcile_once() == [("start", 1), ("start", 2)] and b.lease_pass() == []


def test_rights_by_the_socket_a_process_came_through():
    """The worker's socket writes its epochs and its slot; the controller's, placement; the console's, the operator's
    rows — three sockets, three grants, one class (`VmsController` is both the console and the controller). The
    refusal is the daemon's, by the rights file: nothing in the code knows a list."""
    c, ctl, con = _cluster(1, capacity=50)
    w = c.worker("srv-a")
    try:
        w.vars.put("vms/cameras/1", {"name": "tampered"}); assert False
    except Forbidden:
        pass
    w.take_epoch("1"); con.update_camera(1, {"name": "ok"})
    assert ctl.camera(1)["name"] == "ok" and c.vars.get("vms/epoch/1")[0] == {"epoch": "1"}
    assert con.create_camera({"source": "driverpack://file/2.mp4"})["id"] == 2 and con.update_camera(2, {"name": "from the console"})["revision"] == 2
    w.heartbeat_once()
    try:
        con.place(2); assert False
    except Forbidden:
        pass
    try:
        ctl.update_camera(2, {"name": "from the controller"}); assert False
    except Forbidden:
        pass
    assert ctl.ensure_placed()[0].worker == "w-srv-a-1"                     # the controller placed what the console created
    assert isinstance(con, VmsController) and isinstance(ctl, VmsController)


def test_importing_the_clusters_entry_point_takes_none_of_the_runners_signals():
    """The review's sixth pass. The cluster's entry point installed its SIGTERM/SIGINT handler at import, as М10's entry
    point did: whatever process imported it — a test run — had its signals taken, and a signal sent to stop that run
    was swallowed (`Source/tests/test_pass_failures.py` says what that looked like). The handler is installed only
    when the module is run; this runner fails any module or test that takes its signals (`tests/cluster/run.py`)."""
    import inspect
    import signal
    import w2cplatform.cluster.__main__ as m
    for s in (signal.SIGTERM, signal.SIGINT):
        assert getattr(signal.getsignal(s), "__module__", None) != m.__name__, f"importing {m.__name__} took {s.name}"
    src = inspect.getsource(m)
    assert "signal.signal(" not in src.split('if __name__ == "__main__":')[0], "a handler installed at import"
    assert "signal.signal(" in src.split('if __name__ == "__main__":')[1]          # …and the process still stops on SIGTERM


def test_each_process_opens_its_roles_socket_and_its_objects_on_its_own_server():
    """`w2cplatform/cluster/__main__.py` opens nothing at import (a test imports it) and, when run, the store by its verb's
    role — `configstore:///run/configstore/<role>.sock` unless `PLATFORM_STORE` says otherwise — and the objects as
    `cluster://` on this server, whose create-only rows go through THAT store handle, not a second one opened from the
    environment (`host.stores`, what the box's processes open too). A subsystem's process opens the same two by the
    same variables, its unit naming its role's socket (`vms.__main__`)."""
    import tempfile
    import w2cplatform.cluster.__main__ as m
    from w2cplatform import host
    from w2cplatform.cluster.objectstore import ClusterObjectStore
    from w2cplatform.configstorevars import ConfigstoreVariables
    d = tempfile.mkdtemp(prefix="main-")
    env = m.cluster_env("vmscontroller", {"OBJECTS": f"cluster://{d}/objects?resource=http://127.0.0.1:8090"})
    vars_, objects = host.stores(env)
    assert isinstance(vars_, ConfigstoreVariables) and vars_.path == "/run/configstore/vmscontroller.sock"
    assert isinstance(objects, ClusterObjectStore) and objects.rows.vars is vars_ and objects.resource == "http://127.0.0.1:8090"
    vars_, _ = host.stores(m.cluster_env("console", {"PLATFORM_STORE": f"file://{d}/config", "OBJECTS": f"file://{d}/o"}))
    assert type(vars_).__name__ == "FileVariables"
    assert m.cluster_env("resource", {})["OBJECTS"] == m.OBJECTS == "cluster:///data/platform/objects?resource=http://127.0.0.1:8090"


def test_the_consoles_reaper_ends_a_command_nobody_performed_under_the_clusters_rights():
    """The thirteenth review, major 20 (`m11_console_turn`): the reaper (`vms/jobs.py`, `clear_requests`) reads a
    holder's mark (`vms/commands/<id>`, a create-only row of the store here) to tell a command its holder began from
    one nobody performed — and the console's rights did not grant that read: `Forbidden: console may not read
    objects/vms/commands/x1` on every turn, the command stood, `w2c_requests_expired_total` did not move, and the
    exception left the rows after it unlooked at. Through the console's own socket, under the committed rights: a
    command past its deadline that nobody held is ended and counted; one its holder answered (a mark with an outcome) is
    cleared and not counted; one its holder began (a mark, no outcome) stays its holder's while that holder holds its
    name, and once it went is ended as not known (`requests.unknown`; the thirteenth review, minor — the console reads the
    slot row for that, under its rights too)."""
    import json
    from vms import jobs
    from w2cplatform import requests
    c = Cluster(); c.resources_up()
    con, w = c.console(), c.worker("srv-a")
    late = c.wall() - requests.REAP_AFTER - 60
    for rid in ("x1", "x2", "x3"):
        con.vars.put(f"vms/requests/{rid}", {"action": "output", "unit": "1", "valid_until": late, "at": late - 30}, cas=0)
    assert w._mark("x1", "1", late - 20) and w._mark("x3", "1", late - 20)            # the holder's marks, by its socket
    w.objects.put("vms/commands/x3", json.dumps({"instance": w.instance, "outcome": "performed"}).encode())
    before, unknown = requests.expired.get("vms", 0), requests.unknown.get("vms", 0)
    requests.clear_requests(con)
    assert con.vars.list("vms/requests/") == ["vms/requests/x1"], con.vars.list("vms/requests/")
    assert requests.expired.get("vms", 0) - before == 1
    # …and each end is in its mark, written by the console's own socket (ADR-0054): nobody began x2 — `expired`, the
    # reaper's word, create-only; x3's answer is the holder's and stays as it was
    x2 = json.loads(con.objects.get("vms/commands/x2"))
    assert (x2["outcome"], x2["ended_by"], x2["unit"], x2["action"]) == ("expired", "reaper", "1", "output"), x2
    assert json.loads(con.objects.get("vms/commands/x3")) == {"instance": w.instance, "outcome": "performed"}
    w.release_slot()                                                                   # the holder went
    requests.clear_requests(con)
    assert con.vars.list("vms/requests/") == [], con.vars.list("vms/requests/")
    assert requests.expired.get("vms", 0) - before == 1 and requests.unknown.get("vms", 0) - unknown == 1
    x1 = json.loads(con.objects.get("vms/commands/x1"))                               # completed, its beginner kept
    assert (x1["outcome"], x1["instance"], x1["slot"]) == ("unknown", w.instance, w.name) and "ended_by" not in x1, x1
