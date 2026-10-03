"""What a server reaches, from the console — and a camera its server no longer reaches moves (feedback DQ).

A server's labels came from the node alone: `LABELS`, filled from `meta.labels` in the Nomad client's `client.hcl`, read by
a worker when it starts. Changing them was a file on the machine and a restart; and a label decided only the NEXT
placement — a camera stayed on a server that had stopped reaching its VLAN, and nothing said so.

Now a server may have a row, `<sub>/servers/<server> {labels}`, written by the console (`PUT`/`DELETE
/servers/<server>/labels`, admin on the whole cluster). Where it exists, placement reads it; where it does not, the node's
labels answer. And a pass step, `ensure_reach`, moves a placed unit whose server no longer passes the constraint — or
unplaces it with the reason when nothing live does — at most ten a pass.
"""
import json
import urllib.error

from w2cplatform.contract import Heartbeat
from w2cplatform.spec import REACH_BUDGET, Refused
from vms.config import SPEC
from vms.controller import VmsController
from tests.conftest import Box
from tests.test_console_gate import Tokens, _audit, _call, _console


def _resource(box, server: str) -> None:
    """The server's resource heartbeat: every server of a cluster has one, and it makes the server known to every
    subsystem (`servers_known`)."""
    import json
    box.objects.put(f"platform/resources/{server}/heartbeat",
                    json.dumps({"server": server, "ts": box.wall(), "url": f"http://{server}", "units": {}}).encode())


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
    _resource(box, "srv-a")                                                        # known to the recorders too
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


def _stale_node_site(box, n: int):
    """srv-a's node still says `vlan:b` (a stale `client.hcl`), its row says `vlan:a` — the correction DQ is for; srv-b
    reaches `vlan:a` by its node. `n` cameras needing `vlan:a`, all placed on srv-a."""
    ctl = _site(box, srv_a="vlan:b", srv_b="vlan:a")
    ctl.set_server_labels("srv-a", ["vlan:a"])
    ctl.set_server_labels("srv-b", [])
    cams = [_camera(ctl, k) for k in range(1, n + 1)]
    ctl.ensure_placed()
    ctl.clear_server_labels("srv-b")
    assert all(ctl.where(c) == "w-1" for c in cams)
    return ctl, cams


def test_a_torn_server_row_after_a_controller_restart_moves_nothing_and_takes_no_new_labelled_unit():
    """The review's tenth pass, major — a run: the row says `vlan:a` over a stale node's `vlan:b`. The row torn and the
    controller restarted, there was no last read to keep, the node's `vlan:b` answered, and `ensure_reach` took 12
    cameras of 12 off srv-a in two passes, "srv-a no longer reaches vlan:a" — untrue. A server whose row is there and
    did not read is not known: nothing moves off it, and a unit that needs a label is not placed there. The same for a
    row with no `labels` at all (the product team's sibling: it is not "reaches nothing"). `/servers` says so."""
    from w2cplatform.spec import SERVER_LABELS
    box = Box()
    ctl, cams = _stale_node_site(box, 12)
    for torn in ({"labels": "vlan:a,vlan b"}, {"note": "half a write"}):
        box.vars.put("vms/servers/srv-a", torn)
        fresh = VmsController(box.vars, box.objects, capacity=50, wall=box.wall)     # the controller restarted
        for _ in range(2):
            assert fresh.pass_once()["reach_moves"] == 0
        assert all(fresh.where(c) == "w-1" for c in cams) and "vms/servers/srv-a" in SERVER_LABELS.bad
        assert fresh.labels_of("w-1") == set() and fresh.labels_unread("srv-a")
    new = _camera(fresh, 99)
    fresh.pass_once()
    assert fresh.where(new) == "w-2"                                  # not onto the server nobody can say the reach of
    con_ctl, rec, m, srv, base = _console(box)
    try:
        assert _call(base, "GET", "/servers")[1]["servers"]["srv-a"].get("labels_unread") is True
    finally:
        srv.shutdown()
    box.vars.put("vms/servers/srv-a", {"labels": "vlan:a"})            # mended: read again, nothing to move
    assert fresh.pass_once()["reach_moves"] == 0 and not fresh.labels_unread("srv-a")


def test_a_listing_that_leaves_a_servers_row_out_moves_nothing():
    """The same finding's second run: one listing without the row, for one pass, was "no row" — the node's labels,
    5 cameras of 5 moved, and they did not come back. Each server's row is read by its key now (the servers of the
    workers, the ones read before), so a listing that misses one costs nothing — in a controller that has read it
    before and in one that has just started."""
    box = Box()
    ctl, cams = _stale_node_site(box, 5)
    real = box.vars.list
    box.vars.list = lambda prefix: [k for k in real(prefix) if k != "vms/servers/srv-a"]
    try:
        assert ctl.pass_once()["reach_moves"] == 0
        fresh = VmsController(box.vars, box.objects, capacity=50, wall=box.wall)
        assert fresh.pass_once()["reach_moves"] == 0 and fresh.labels_of("w-1") == {"vlan:a"}
    finally:
        box.vars.list = real
    assert all(ctl.where(c) == "w-1" for c in cams)


def test_one_row_that_cannot_be_read_is_that_servers_alone():
    """The product team's sibling: one row whose read fails stopped the reading of every server's labels (the whole read
    was one `try`). That server is unread; the others are read, and srv-b's edit moves what it should."""
    box = Box()
    ctl = _site(box, srv_a="vlan:a", srv_b="vlan:a", srv_c="vlan:a")
    ctl.set_server_labels("srv-c", [])
    cam = _camera(ctl, 1)
    ctl.set_server_labels("srv-a", [])
    ctl.ensure_placed()
    assert ctl.where(cam) == "w-2"
    ctl.clear_server_labels("srv-a")
    real = box.vars.get
    box.vars.get = lambda key: (_ for _ in ()).throw(OSError("one key")) if key == "vms/servers/srv-c" else real(key)
    try:
        ctl.set_server_labels("srv-b", ["vlan:z"])
        rep = ctl.pass_once()
        assert rep["reach_moves"] == 1 and ctl.where(cam) == "w-1"
        assert ctl.labels_unread("srv-c") and ctl.labels_of("w-3") == set()
        assert rep["servers_labels_unread"] == 1          # …said where a number is read, not only on the page (the eleventh)
    finally:
        box.vars.get = real
    import urllib.request
    con_ctl, rec, m, srv, base = _console(box)
    try:
        with urllib.request.urlopen(base + "/metrics") as r:
            page = r.read().decode()
        assert "vms_servers_labels_unread 1" in page and "vms_units_waiting_for_reach 0" in page
    finally:
        srv.shutdown()


def test_the_channels_of_one_device_move_together_or_not_at_all():
    """The review's tenth pass, minor, and its question: an administrator of one camera of a four-channel recorder
    changed its `labels`, and `ensure_reach` took that channel alone to another holder — two sessions to one recorder,
    for good. The group moves whole, in one pass, to a worker that takes it all. With none, the eleventh review's
    rule: the group stays where it is, whole — giving the channel's place back split the recorder too, once it was
    placed again beside nobody — said once, counted (`reach_waiting`), and moved as soon as a worker takes it."""
    box = Box()
    ctl = _site(box, srv_a="vlan:a", srv_b="vlan:a,vlan:c")
    ctl.set_server_labels("srv-b", [])
    nvr = [ctl.create_camera({"source": f"driverpack://acme/10.0.0.50/ch/{c}", "labels": "vlan:a"})["id"] for c in range(1, 5)]
    ctl.ensure_placed()
    ctl.clear_server_labels("srv-b")
    assert {ctl.where(c) for c in nvr} == {"w-1"}
    ctl.update(nvr[1], {"labels": "vlan:a,vlan:c"})
    rep = ctl.pass_once()
    assert rep["reach_moves"] == 4 and {ctl.where(c) for c in nvr} == {"w-2"}, [ctl.where(c) for c in nvr]
    assert ctl.placement(nvr[0]).reason.startswith(f"with {nvr[1]}, one device: srv-a no longer reaches vlan:c")
    ctl.update(nvr[2], {"labels": "vlan:d"})                             # nobody reaches vlan:d
    rep = ctl.pass_once()
    assert (rep["reach_moves"], rep["reach_waiting"]) == (0, 4) and {ctl.where(c) for c in nvr} == {"w-2"}
    _beat(box, "w-3", "srv-c", "vlan:a,vlan:c,vlan:d")                  # a server that reaches all four comes
    rep = ctl.pass_once()
    assert (rep["reach_moves"], rep["reach_waiting"]) == (4, 0) and {ctl.where(c) for c in nvr} == {"w-3"}


def test_a_group_goes_whole_to_a_worker_with_room_for_it_when_the_near_one_has_too_little():
    """The eleventh review, a major — a run: a four-channel recorder, srv-b (two places, its recorder beside it) and
    srv-c (fifty) both reach the label. `ensure_reach` asked `_pick` for ONE worker — the near one — found it too small
    and gave all four places back "nothing live reaches it"; the next placement put two on srv-b and two nowhere, for
    good. Now the group goes whole to a worker that reaches it and has room for all of it, inside the pass's budget;
    and the first placement of a group (`place`) does the same — the product's cross-check found that path too."""
    from vms.config import REC_SPEC
    box = Box()
    ctl = _site(box, srv_a="vlan:a")
    nvr = [ctl.create_camera({"source": f"driverpack://acme/10.0.0.50/ch/{c}", "labels": "vlan:a"})["id"] for c in range(1, 5)]
    ctl.ensure_placed()
    assert {ctl.where(c) for c in nvr} == {"w-1"}
    _beat(box, "w-2", "srv-b", "vlan:a", capacity=2)
    _beat(box, "w-3", "srv-c", "vlan:a", capacity=50)
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-1"),                  # the recorder of channel 1 runs on srv-b: near
                    Heartbeat("r-1", box.wall(), [{"id": f"{nvr[0]}-rec", "cam": str(nvr[0]), "phase": "running"}],
                              {"server": "srv-b"}).to_bytes())
    ctl.set_server_labels("srv-a", [])
    rep = ctl.pass_once()
    assert rep["reach_moves"] == 4 and {ctl.where(c) for c in nvr} == {"w-3"}, [ctl.where(c) for c in nvr]
    assert "nothing live reaches it" not in json.dumps([ctl.placement(c).reason for c in nvr])
    # …and four new channels of another recorder, followed by a recorder on srv-b: placed whole on srv-c, not 2 + 0
    more = [ctl.create_camera({"source": f"driverpack://acme/10.0.0.60/ch/{c}", "labels": "vlan:a"})["id"] for c in range(1, 5)]
    box.objects.put(REC_SPEC.sub.heartbeat_key("r-1"),
                    Heartbeat("r-1", box.wall(), [{"id": f"{more[0]}-rec", "cam": str(more[0]), "phase": "running"}],
                              {"server": "srv-b"}).to_bytes())
    ctl.ensure_placed()
    assert {ctl.where(c) for c in more} == {"w-3"}, [ctl.where(c) for c in more]


def test_a_group_is_moved_inside_the_budget_and_one_bigger_than_the_budget_waits_and_says_so():
    """The eleventh review's remark, made a rule by the product's cross-check: a group moved past `REACH_BUDGET` when it
    was the pass's first move — 32 channels with a budget of 10 were 32 epochs and seams in one pass. A group now fits
    in what is left of the pass's budget or waits for the next pass; one bigger than the budget stays whole where it
    is, counted (`reach_waiting`), and the log says to raise the budget or move it by hand."""
    box = Box()
    ctl = _site(box, srv_a="vlan:a", srv_b="vlan:a")
    ctl.set_server_labels("srv-b", [])
    big = [ctl.create_camera({"source": f"driverpack://acme/10.0.0.50/ch/{c}", "labels": "vlan:a"})["id"] for c in range(1, 13)]
    small = [ctl.create_camera({"source": f"driverpack://acme/10.0.0.70/ch/{c}", "labels": "vlan:a"})["id"] for c in range(1, 4)]
    ctl.ensure_placed()
    ctl.clear_server_labels("srv-b")
    assert {ctl.where(c) for c in big + small} == {"w-1"}
    ctl.set_server_labels("srv-a", [])
    moves = ctl.ensure_reach(budget=REACH_BUDGET)
    assert REACH_BUDGET < len(big) and len(moves) <= REACH_BUDGET
    assert {ctl.where(c) for c in big} == {"w-1"} and ctl.last_reach_waiting == len(big)
    assert {ctl.where(c) for c in small} == {"w-2"}
    moves = ctl.ensure_reach(budget=2)                                  # three channels, two moves: not this pass
    assert moves == [] and {ctl.where(c) for c in big} == {"w-1"}


def test_one_alphabet_for_labels_and_a_stored_label_outside_it_does_not_move_its_camera():
    """The review's tenth pass, major: a camera's labels were any words, a server's row only `LABEL_WORD`. Cameras with
    `склад`, `zone 1`, `-x` were placed by the node's labels, and once the administrator gave the server a row they
    were taken off it, and no server's row could ever take them. A label outside the one alphabet is refused when a
    camera is created or given it (400 at the console); one stored before stays as it is — editable, and not moved for
    a label no row can say, counted once (`UNIT_LABELS`)."""
    from w2cplatform.spec import UNIT_LABELS
    box = Box()
    ctl = _site(box, srv_a="склад,vlan:a")
    for bad in ("склад", "zone 1", "-x"):
        try:
            _camera(ctl, 1, bad)
        except Refused as e:
            assert "a label is letters" in str(e)
        else:
            raise AssertionError(bad)
    con_ctl, rec, m, srv, base = _console(box)
    try:
        assert _call(base, "POST", "/cameras", {"source": "driverpack://file/9.mp4", "labels": ["склад"]})[0] == 400
    finally:
        srv.shutdown()
    box.vars.put("vms/cameras/7", {"id": "7", "name": "old", "source": "driverpack://file/7.mp4", "labels": "склад",
                                   "revision": "1"})                    # as an older build let it in
    ctl.ensure_placed()
    assert ctl.where(7) == "w-1"
    ctl.set_server_labels("srv-a", ["vlan:a"])
    assert ctl.pass_once()["reach_moves"] == 0 and ctl.where(7) == "w-1"
    assert "vms/cameras/7#labels" in UNIT_LABELS.bad
    assert ctl.update(7, {"name": "renamed", "labels": "склад"})["name"] == "renamed"   # its own label: an edit stands
    try:
        ctl.update(7, {"labels": "склад,zone 1"})
    except Refused:
        pass
    else:
        raise AssertionError("a new label outside the alphabet was taken")


def test_the_labels_route_answers_a_bad_body_a_bad_label_and_an_unknown_server_with_words():
    """The review's tenth pass, minors, and the product team's sibling: a body that is not JSON dropped the connection;
    `[null]`, `[true]`, `[1]` were labels; `*`, `srv%2Fa`, a newline, a typo were rows nobody reads (200); a name of 300
    characters answered 503 with the store's local path in it. Each is a 400 in words now, and a store that does not
    take the write says so without its own words."""
    import urllib.request
    box = Box()
    _site(box, srv_a="vlan:a")
    con_ctl, rec, m, srv, base = _console(box)
    try:
        req = urllib.request.Request(base + "/servers/srv-a/labels", data=b"{not json", method="PUT",
                                     headers={"Content-Type": "application/json", "Idempotency-Key": "k-raw"})
        try:
            urllib.request.urlopen(req)
            raise AssertionError("taken")
        except urllib.error.HTTPError as e:
            assert e.code == 400 and "not JSON" in json.loads(e.read())["detail"]
        for labels in ([None], [True], [1], ["vlan:a", 2]):
            assert _call(base, "PUT", "/servers/srv-a/labels", {"labels": labels})[0] == 400, labels
        for name in ("*", "srv%252Fa", "srv%0Aa", "x" * 300, "srv-x"):
            code, body = _call(base, "PUT", f"/servers/{name}/labels", {"labels": []})
            assert code == 400 and box.archive not in json.dumps(body), (name[:20], code, body)
        assert "no server srv-x is known here" in _call(base, "PUT", "/servers/srv-x/labels", {"labels": []})[1]["detail"]
        assert not [k for k in box.vars.list("vms/servers/")]
        real = con_ctl.vars.put                                       # the console's own view of the store

        def refuses(key, *a, **k):
            if key.startswith("vms/servers/"):
                raise OSError(f"[Errno 28] No space left on device: '{box.archive}/store/{key}'")
            return real(key, *a, **k)
        con_ctl.vars.put = refuses
        try:
            code, body = _call(base, "PUT", "/servers/srv-a/labels", {"labels": ["vlan:a"]})
            assert code == 503 and box.archive not in json.dumps(body), body
        finally:
            con_ctl.vars.put = real
    finally:
        srv.shutdown()


def test_moves_for_reach_are_counted_since_the_store_was_new_and_said_in_the_log():
    """The review's tenth pass, minor: `units_moved_for_reach` was the last pass's number — a scrape every 15 s saw a
    third of the moves — and a move was a line nowhere. The pass report carries a counter (`reach_moves_total`,
    `…_units_moved_for_reach_total` on `/metrics`) and each move is a warning in the controller's log."""
    import logging
    import urllib.request
    box = Box()
    ctl = _site(box, srv_a="vlan:a", srv_b="vlan:a")
    ctl.set_server_labels("srv-b", [])
    cams = [_camera(ctl, n) for n in range(1, 13)]
    ctl.ensure_placed()
    ctl.clear_server_labels("srv-b")
    ctl.set_server_labels("srv-a", [])
    said = []

    class Catch(logging.Handler):
        def emit(self, record):
            said.append(record.getMessage())
    catch = Catch(level=logging.WARNING)
    logging.getLogger("w2cplatform.spec").addHandler(catch)
    try:
        assert [ctl.pass_once()["reach_moves"] for _ in range(3)] == [REACH_BUDGET, 2, 0]
    finally:
        logging.getLogger("w2cplatform.spec").removeHandler(catch)
    assert ctl.pass_report()["reach_moves_total"] == 12 and len(cams) == 12
    assert len([m for m in said if "moved from w-1 to w-2: srv-a no longer reaches vlan:a" in m]) == 12, said
    con_ctl, rec, m, srv, base = _console(box)
    try:
        with urllib.request.urlopen(base + "/metrics") as r:
            assert "vms_units_moved_for_reach_total 12" in r.read().decode()
    finally:
        srv.shutdown()
