"""What a server reaches, from the console — and a camera its server no longer reaches moves (feedback DQ).

A server's labels came from the node alone: `LABELS`, filled from `meta.labels` in the Nomad client's `client.hcl`, read by
a worker when it starts. Changing them was a file on the machine and a restart; and a label decided only the NEXT
placement — a camera stayed on a server that had stopped reaching its VLAN, and nothing said so.

Now a server may have a row, `<sub>/servers/<server> {labels}`, written by the console (`PUT`/`DELETE
/servers/<server>/labels`, admin on the whole cluster). Where it exists, placement reads it; where it does not, the node's
labels answer. And a pass step, `ensure_reach`, moves a placed unit whose server no longer passes the constraint — or
unplaces it with the reason when nothing live does — at most ten a pass.
"""
from w2cplatform.contract import Heartbeat
from w2cplatform.spec import REACH_BUDGET, Refused
from vms.config import SPEC
from vms.controller import VmsController
from tests.conftest import Box
from tests.test_console_gate import Tokens, _audit, _call, _console


def _beat(box, worker: str, server: str, labels: str, capacity: int = 50) -> None:
    box.objects.put(SPEC.sub.heartbeat_key(worker),
                    Heartbeat(worker, box.wall(), [], {"server": server, "capacity": capacity, "headroom": capacity,
                                                       "labels": labels}).to_bytes())


def _site(box, capacity: int = 50, **servers) -> VmsController:
    """A controller and one worker per server — `srv_a="vlan:a"` is `w-1` on `srv-a`, reaching `vlan:a`."""
    for k, (server, labels) in enumerate(servers.items(), 1):
        _beat(box, f"w-{k}", server.replace("_", "-"), labels, capacity)
    return VmsController(box.vars, box.objects, capacity=capacity, wall=box.wall)


def _camera(ctl, n: int, labels: str = "vlan:a") -> int:
    return ctl.create_camera({"source": f"driverpack://file/{n}.mp4", "labels": labels})["id"]


def test_labels_from_the_console_override_the_nodes_and_deleting_returns_to_the_nodes():
    """The row is the server's labels where it exists — even empty, "this machine reaches nothing" — and placement reads
    it on the next pass with no worker restarted; `DELETE` takes the row away and the node's labels answer again.
    `GET /servers` says both and which one placement reads; each write is a journal line with its author."""
    box = Box()
    ctl = _site(box, srv_a="vlan:a", srv_b="")
    con_ctl, rec, m, srv, base = _console(box)
    try:
        st, out = _call(base, "GET", "/servers")
        assert st == 200 and out["servers"]["srv-b"]["labels_source"] == "node"
        assert out["servers"]["srv-a"]["labels"] == ["vlan:a"] and out["servers"]["srv-a"]["labels_node"] == ["vlan:a"]
        assert ctl.labels_of("w-2") == set()

        st, out = _call(base, "PUT", "/servers/srv-b/labels", {"labels": ["vlan:b", "vlan:a", "vlan:a"]}, user="anna")
        assert st == 200 and out["labels"] == ["vlan:a", "vlan:b"] and out["labels_source"] == "console"
        assert box.vars.get("vms/servers/srv-b")[0] == {"labels": "vlan:a,vlan:b"}
        assert ctl.labels_of("w-2") == {"vlan:a", "vlan:b"}                       # the console's, over the node's ""
        s = _call(base, "GET", "/servers")[1]["servers"]["srv-b"]
        assert (s["labels"], s["labels_node"], s["labels_source"]) == (["vlan:a", "vlan:b"], [], "console")

        assert _call(base, "PUT", "/servers/srv-a/labels", {"labels": []}, user="anna")[0] == 200
        assert ctl.labels_of("w-1") == set()                                       # an empty row reaches nothing

        st, out = _call(base, "DELETE", "/servers/srv-b/labels", user="boris")
        assert st == 200 and out["labels_source"] == "node"
        assert ctl.labels_of("w-2") == set() and ctl.labels_source("srv-b") == "node"
        assert _call(base, "DELETE", "/servers/srv-b/labels", user="boris")[0] == 200   # gone is gone: no second line

        assert _call(base, "PUT", "/servers/srv-a/labels", {"labels": ["vlan a"]})[0] == 400       # not a label
        assert _call(base, "PUT", "/servers/srv-a/labels", {"labels": "vlan:a"})[0] == 400         # not a list
        assert _call(base, "PUT", "/servers/srv,a/labels", {"labels": []})[0] == 400              # not a server's name
        assert [k for k in _audit(box) if k[0].startswith("server.")] == [
            ("server.labels.set", "anna"), ("server.labels.set", "anna"), ("server.labels.cleared", "boris")]
    finally:
        srv.shutdown()


def test_a_camera_on_a_server_that_lost_its_label_moves_to_one_that_has_it_within_one_pass():
    """Camera 1 needs `vlan:a`, placed on srv-a. The administrator says srv-a reaches only `vlan:b` now. The next pass
    moves it to srv-b, which reaches `vlan:a`, with the reason naming what srv-a lost — no worker restarted."""
    box = Box()
    ctl = _site(box, srv_a="vlan:a", srv_b="vlan:a,vlan:b")
    cam = _camera(ctl, 1)
    ctl.set_server_labels("srv-b", [])                                             # placed on srv-a: srv-b reaches nothing yet
    ctl.ensure_placed()
    assert ctl.where(cam) == "w-1"
    ctl.clear_server_labels("srv-b")
    ctl.set_server_labels("srv-a", ["vlan:b"])
    rep = ctl.pass_once()
    assert rep["ok"] and rep["reach_moves"] == 1, rep
    assert ctl.where(cam) == "w-2" and ctl.assignment("w-1").units == [] and ctl.assignment("w-2").units == [str(cam)]
    assert ctl.placement(cam).reason.startswith("srv-a no longer reaches vlan:a; most free capacity"), ctl.placement(cam).reason
    assert ctl.pass_once()["reach_moves"] == 0 and ctl.where(cam) == "w-2"        # and it stays: nothing to move back to


def test_a_camera_no_live_server_reaches_is_unplaced_with_the_reason():
    """The same edit with no other server reaching `vlan:a`: the camera gives its place back — the row says nowhere and
    why, its worker drops it — and `/unplaceable` and `/where` say why in plain words. The next pass places it again as
    soon as a server reaches it (here: the row goes, the node's labels answer)."""
    box = Box()
    ctl = _site(box, srv_a="vlan:a", srv_b="vlan:b")
    cam = _camera(ctl, 1)
    ctl.ensure_placed()
    assert ctl.where(cam) == "w-1"
    ctl.set_server_labels("srv-a", ["vlan:c"])
    assert ctl.pass_once()["reach_moves"] == 1
    assert ctl.where(cam) is None and ctl.assignment("w-1").units == []
    why = "srv-a no longer reaches vlan:a; nothing live reaches it"
    assert ctl.unplaceable() == [{"id": cam, "labels": ["vlan:a"], "workers_live": 2, "why": why}]
    con_ctl, rec, m, srv, base = _console(box)
    try:
        assert _call(base, "GET", f"/where/{cam}")[1]["reason"] == why
    finally:
        srv.shutdown()
    ctl.clear_server_labels("srv-a")
    ctl.pass_once()
    assert ctl.where(cam) == "w-1" and ctl.unplaceable() == []


def test_at_most_ten_units_move_in_one_pass():
    """Twenty-five cameras on srv-a, which stops reaching their VLAN: ten move each pass (every move is a new epoch and a
    seam in the recording), the pass report counts them, and the third pass finishes."""
    box = Box()
    ctl = _site(box, srv_a="vlan:a", srv_b="vlan:a")
    ctl.set_server_labels("srv-b", [])
    cams = [_camera(ctl, n) for n in range(1, 26)]
    ctl.ensure_placed()
    assert all(ctl.where(c) == "w-1" for c in cams)
    ctl.clear_server_labels("srv-b")
    ctl.set_server_labels("srv-a", [])
    assert ctl.pass_once()["reach_moves"] == REACH_BUDGET
    con_ctl, rec, m, srv, base = _console(box)
    try:
        import urllib.request
        with urllib.request.urlopen(base + "/metrics") as r:
            assert f"vms_units_moved_for_reach {REACH_BUDGET}" in r.read().decode()     # the pass report, on /metrics
    finally:
        srv.shutdown()
    assert [ctl.pass_once()["reach_moves"] for _ in range(3)] == [REACH_BUDGET, 5, 0]
    assert all(ctl.where(c) == "w-2" for c in cams)


def test_a_store_that_does_not_answer_moves_nothing():
    """The servers' rows were read once — srv-a reaches `vlan:a` by the console's word, over a node that says nothing.
    Then the store stops answering for them: the pass keeps the labels last read, and camera 1 stays where it is
    (falling back to the node's empty labels would have unplaced it). A controller that has never read them moves
    nothing at all; the placement step still places by what it can read."""
    box = Box()
    ctl = _site(box, srv_a="", srv_b="")
    ctl.set_server_labels("srv-a", ["vlan:a"])
    cam = _camera(ctl, 1)
    ctl.pass_once()
    assert ctl.where(cam) == "w-1"

    real_list = box.vars.list

    def silent(prefix):
        if prefix.startswith("vms/servers/"):
            raise OSError("the store did not answer")
        return real_list(prefix)
    box.vars.list = silent
    try:
        rep = ctl.pass_once()
        assert rep["reach_moves"] == 0 and ctl.where(cam) == "w-1", rep
        assert ctl.labels_of("w-1") == {"vlan:a"}                                 # the last read
        fresh = VmsController(box.vars, box.objects, capacity=50, wall=box.wall)
        assert fresh.server_labels() is None
        assert fresh.ensure_reach() == [] and fresh.pass_once()["reach_moves"] == 0
        assert ctl.where(cam) == "w-1"
    finally:
        box.vars.list = real_list
    ctl.clear_server_labels("srv-a")                                               # answered again: the node's "" — it moves
    assert ctl.pass_once()["reach_moves"] == 1 and ctl.where(cam) is None


def test_a_servers_row_that_does_not_parse_keeps_what_was_last_read_of_it():
    """A row written by hand with a word that is not a label: that server keeps the labels last read of it (else its
    node's), counted once — and nothing moves for it."""
    from w2cplatform.spec import SERVER_LABELS
    box = Box()
    ctl = _site(box, srv_a="")
    ctl.set_server_labels("srv-a", ["vlan:a"])
    cam = _camera(ctl, 1)
    ctl.pass_once()
    box.vars.put("vms/servers/srv-a", {"labels": "vlan:a,vlan b"})
    assert ctl.pass_once()["reach_moves"] == 0 and ctl.where(cam) == "w-1"
    assert "vms/servers/srv-a" in SERVER_LABELS.bad
    box.vars.put("vms/servers/srv-a", {"labels": "vlan:a"})
    ctl.pass_once()
    assert "vms/servers/srv-a" not in SERVER_LABELS.bad


def test_only_an_admin_of_the_whole_cluster_writes_a_servers_labels():
    """A server's labels decide where every camera may go: `admin` on the cluster, not on one camera, not on a label,
    not `view`. Looking — `GET /servers`, and what an edit would move — is any grant."""
    box = Box()
    _site(box, srv_a="vlan:a")
    access = Tokens({"admin": [("admin", None, ())], "cam-admin": [("admin", "1", ())],
                     "guard": [("admin", None, ("vlan:a",))], "viewer": [("view", None, ())]})
    ctl, rec, m, srv, base = _console(box, access)
    try:
        for who in ("cam-admin", "guard", "viewer"):
            assert _call(base, "PUT", "/servers/srv-a/labels", {"labels": []}, token=who)[0] == 403, who
            assert _call(base, "DELETE", "/servers/srv-a/labels", token=who)[0] == 403, who
            assert _call(base, "PUT", "/rec/servers/srv-a/labels", {"labels": []}, token=who)[0] == 403, who
        assert _call(base, "GET", "/servers", token="viewer")[0] == 200
        assert _call(base, "GET", "/servers/srv-a/labels?labels=vlan:b", token="viewer")[0] == 200
        assert box.vars.get("vms/servers/srv-a")[0] is None
        assert _call(base, "PUT", "/servers/srv-a/labels", {"labels": []}, token="admin")[0] == 200
        assert _call(base, "PUT", "/rec/servers/srv-a/labels", {"labels": []}, token="admin")[0] == 200
        assert box.vars.get("rec/servers/srv-a")[0] == {"labels": ""}            # the recorder's own row, its own prefix
    finally:
        srv.shutdown()


def test_the_page_is_told_which_cameras_an_edit_will_move():
    """`GET /servers/<server>/labels?labels=…` — what would move if the server reached that — before anything is written,
    and the `PUT` says the same of what it wrote. The page warns with it."""
    box = Box()
    ctl = _site(box, srv_a="vlan:a,vlan:b", srv_b="vlan:a,vlan:b")
    ctl.set_server_labels("srv-b", [])
    a, b = _camera(ctl, 1, "vlan:a"), _camera(ctl, 2, "vlan:b")
    ctl.ensure_placed()
    con_ctl, rec, m, srv, base = _console(box)
    try:
        st, out = _call(base, "GET", "/servers/srv-a/labels?labels=vlan:b")
        assert st == 200 and out["would_move"] == [a] and out["labels_source"] == "node"
        assert _call(base, "GET", "/servers/srv-a/labels?labels=")[1]["would_move"] == [a, b]
        assert _call(base, "GET", "/servers/srv-a/labels?labels=vlan%20b")[0] == 400
        st, out = _call(base, "PUT", "/servers/srv-a/labels", {"labels": ["vlan:a"]})
        assert out["will_move"] == [b]
        assert ctl.where(a) == "w-1" and ctl.where(b) == "w-1"                    # nothing moved yet: the pass does
    finally:
        srv.shutdown()


def test_a_server_name_that_is_no_name_is_refused():
    box = Box()
    ctl = _site(box, srv_a="")
    for bad in ("", "a/b", "..", "a,b", 'a"b'):
        try:
            ctl.set_server_labels(bad, [])
        except Refused:
            continue
        raise AssertionError(bad)
