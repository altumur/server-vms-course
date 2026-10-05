"""Lesson 5 — the controller on every server: placement under label constraints,
the directory in one scan, two controllers agreeing, the snapshot that
leaves the cluster, and the console over real HTTP."""
import json
from w2cplatform import requests
import threading
import urllib.request
from vms.controller import VmsController
from w2cplatform.host import spec_console
from w2cplatform.cluster.directory import Directory
from tests.cluster.conftest import Cluster

A, B, C = "w-srv-a-1", "w-srv-b-1", "w-srv-c-1"      # one worker's unit on each server: `WORKER_NAME=w-%l-1`


def _three_workers(c, ctl):
    ws = {f"w-{s}-1": c.worker(s) for s in ("srv-a", "srv-b", "srv-c")}
    for w in ws.values(): w.heartbeat_once()
    return ws


def test_placement_under_label_constraints():
    c = Cluster(); ctl = VmsController(c.vars, c.objects, capacity=10, wall=c.wall)
    _three_workers(c, ctl)
    a = ctl.create_camera({"source": "driverpack://file/a.mp4", "labels": ["vlan:cctv-a"]})
    b = ctl.create_camera({"source": "driverpack://file/b.mp4", "labels": ["vlan:cctv-b"]})
    ab = ctl.create_camera({"source": "driverpack://file/ab.mp4", "labels": ["vlan:cctv-a", "vlan:cctv-b"]})
    x = ctl.create_camera({"source": "driverpack://file/x.mp4", "labels": ["vlan:cctv-x"]})
    ctl.ensure_placed()
    assert ctl.where(a["id"]) in (A, B) and ctl.where(b["id"]) in (B, C) and ctl.where(ab["id"]) == B
    assert "reaching vlan:cctv-a,vlan:cctv-b" in ctl.placement(ab["id"]).reason and "on srv-b" in ctl.placement(ab["id"]).reason
    assert ctl.where(x["id"]) is None and ctl.unplaceable() == [{"id": x["id"], "labels": ["vlan:cctv-x"], "workers_live": 3}]


def test_adding_a_worker_moves_nothing_even_with_constraints():
    c = Cluster(); ctl = VmsController(c.vars, c.objects, capacity=2, wall=c.wall)
    c.worker("srv-a", capacity=2).heartbeat_once()
    for i in range(3):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4", "labels": ["vlan:cctv-a"]})
    ctl.ensure_placed(); before = {i: ctl.where(i) for i in (1, 2, 3)}
    assert before == {1: A, 2: A, 3: None}
    c.worker("srv-b", capacity=2).heartbeat_once(); ctl.ensure_placed()
    assert {i: ctl.where(i) for i in (1, 2)} == {1: A, 2: A} and ctl.where(3) == B


def test_where_is_camera_7_in_one_scan():
    c = Cluster(); ctl = VmsController(c.vars, c.objects, wall=c.wall)
    _three_workers(c, ctl)
    for i in range(9):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4"})
    ctl.ensure_placed()
    d = Directory(c.vars, "vms", ttl=5.0, clock=c.clock)
    assert d.where(7) == ctl.where(7) and d.scans == 1
    for i in range(1, 10):
        assert d.where(i) == ctl.where(i)
    assert d.scans == 1                                                    # nine answers, one scan
    assert sorted(sum((d.holdings(w) for w in (A, B, C)), []), key=int) == [str(i) for i in range(1, 10)]


def test_the_directory_reads_past_an_assignment_row_whose_rev_does_not_parse():
    """The review's sixth pass, the follow-up. The directory is one scan of every `vms/workers/*`, each row parsed
    bare: one worker's `rev` with a word in it — a hand edit — and "where is camera 7" had no answer for ANY camera.
    The row is read for the units it names (`w2cplatform.contract.read_assignment`), as the controller reads it."""
    c = Cluster(); ctl = VmsController(c.vars, c.objects, wall=c.wall)
    _three_workers(c, ctl)
    for i in range(9):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4"})
    ctl.ensure_placed()
    w = ctl.where(7)
    c.vars.put(f"vms/workers/{w}", {"units": ",".join(ctl.assignment(w).units), "rev": "seven"})
    d = Directory(c.vars, "vms", ttl=5.0, clock=c.clock)
    assert [d.where(i) for i in range(1, 10)] == [ctl.where(i) for i in range(1, 10)] and d.where(7) == w
    assert ctl.pass_once()["ok"]                                             # and the controller's pass is a pass
    import sys                                                               # the count is the process's, and every heartbeat
    m = sys.modules["w2cplatform.contract"]                                  # and pass report after would carry it — into the
    m.ASSIGNMENTS_GARBLED.clear(); m._garbled_assignments.clear()            # traces `test_stand.py` compares


def test_two_controllers_agree_under_constraints():
    c = Cluster()
    _three_workers(c, VmsController(c.vars, c.objects, wall=c.wall))
    a = VmsController(c.vars, c.objects, capacity=100, wall=c.wall)
    b = VmsController(c.vars, c.objects, capacity=100, wall=c.wall)
    for i in range(40):
        a.create_camera({"source": f"driverpack://file/{i}.mp4", "labels": ["vlan:cctv-b"] if i % 2 else []})
    ts = [threading.Thread(target=x.ensure_placed) for x in (a, b, a, b)]
    [t.start() for t in ts]; [t.join() for t in ts]
    where = {i: a.where(i) for i in range(1, 41)}
    assert all(where.values())
    units = sum((a.assignment(w).units for w in (A, B, C)), [])
    assert sorted(int(u) for u in units) == list(range(1, 41))             # each camera in exactly one assignment
    assert all(where[i] != A for i in range(2, 41, 2))                     # cctv-b cameras never on srv-a


def test_the_clusters_controller_loops_write_the_pass_report_its_metrics_read():
    """The review's eighth pass, found by the coordinator: `vms_units_unplaced` and `vms_reconcile_pass_seconds` are read
    from the report `pass_once` writes, and the cluster's controller loops called the placement steps one by one and
    never wrote it — on a cluster the gauges said 0 and -1 whatever was unplaced. A pass of either loop is the box's
    pass now — the platform's, which both loops run (`host.placement_pass`, `host.controller_loop`): the report, then
    the snapshot, the recordings' included."""
    from w2cplatform import host
    from w2cplatform.console import SpecConsole
    from w2cplatform.spec import SpecController
    from vms.config import REC_SPEC
    c = Cluster(); ctl = VmsController(c.vars, c.objects, capacity=2, wall=c.wall)
    c.worker("srv-a", capacity=2).heartbeat_once()
    for i in range(3):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4"})
    text = SpecConsole(ctl, wall=c.wall).metrics_text()
    assert "vms_reconcile_last_pass_age_seconds -1" in text and "vms_units_unplaced 0" in text   # no report: what it said
    host.placement_pass(ctl, "placement")
    text = SpecConsole(ctl, wall=c.wall).metrics_text()
    assert "vms_units_unplaced 1" in text and "vms_reconcile_last_pass_age_seconds 0" in text, text
    assert "vms_reconcile_last_success_age_seconds 0" in text and "vms_reconcile_pass_seconds " in text
    assert "vms_snapshot_age_seconds -1" not in text
    rec = SpecController(REC_SPEC, c.vars, c.objects, wall=c.wall)
    rec.create({"name": "1", "cam": "1"})
    host.placement_pass(rec, "rec placement")
    text = SpecConsole(rec, wall=c.wall).metrics_text()
    assert "rec_units_unplaced 1" in text and "rec_reconcile_last_pass_age_seconds 0" in text, text
    assert "rec_snapshot_age_seconds -1" not in text                               # the recordings' snapshot, as on a box


def test_a_worker_runs_where_a_resource_answers_and_leaves_when_it_stops():
    """Who guarantees a worker runs where the archive is: the units on a server — its resource and its worker are
    installed together. This is the live fact behind that: the spec says `requires: resource`, so a worker whose
    server's resource has gone silent is not placed on, its cameras are moved to servers whose resource answers, and
    the reason says so. A resource never seen is not a fact and passes."""
    c = Cluster(); ctl = VmsController(c.vars, c.objects, capacity=10, wall=c.wall)
    ws = _three_workers(c, ctl)
    rs = c.resources_up()
    a = ctl.create_camera({"source": "driverpack://file/a.mp4", "labels": ["vlan:cctv-a"]})["id"]   # srv-a or srv-b
    b = ctl.create_camera({"source": "driverpack://file/b.mp4", "labels": ["vlan:cctv-a"]})["id"]
    for pl in ctl.ensure_placed():
        assert pl.reason.endswith(", whose resource is live")                                     # the label, and the fact behind it
    # srv-a's disks die: its resource job stops heartbeating; its worker does not — it has nowhere to write
    c.wall.advance(60)
    for w in ws.values(): w.heartbeat_once()
    rs["srv-b"].heartbeat(); rs["srv-c"].heartbeat()
    assert ctl.resource_state("srv-a") == "silent" and ctl.without_resource([A, B, C]) == [A]
    on_a = [u for u in ctl.assignment(A).units]
    moves = ctl.redistribute()
    assert sorted(m[1] for m in moves) == [A] * len(on_a) and all(m[2] == B for m in moves)   # off srv-a, onto srv-b (cctv-a reaches it; srv-c cannot)
    assert ctl.assignment(A).units == [] and ctl.placement(a).reason.startswith("resource on srv-a silent; ")
    assert ctl.placement(a).reason.endswith("; on srv-b")
    # the console shows the label beside the fact: whether each server's resource answers
    sv = spec_console({"vms": ctl}, "vms").root.servers()["servers"]
    assert sv["srv-a"]["resource"] == "silent" and sv["srv-a"]["placeable"] is False and sv["srv-a"]["why"] == "resource on srv-a silent"
    assert sv["srv-b"]["resource"] == "live" and sv["srv-b"]["placeable"] is True and [w["worker"] for w in sv["srv-b"]["workers"]] == [B]
    assert "archive" not in sv["srv-a"]          # what a server holds of a subsystem's tables is its spec's `servers.show` (step 6)
    x = ctl.create_camera({"source": "driverpack://file/x.mp4", "labels": ["vlan:cctv-a"]})["id"]
    assert ctl.place(x).worker == B                                                                # never w-srv-a-1 while srv-a's resource is silent
    assert ctl.unplaceable() == []                                                                 # srv-b reaches cctv-a too; nothing waits
    # the resource comes back: srv-a is a place to record again; nothing moves back (adding a worker moves nothing)
    rs["srv-a"].heartbeat()
    assert ctl.resource_state("srv-a") == "live" and ctl.redistribute() == [] and ctl.assignment(B).units == sorted(map(str, [a, b, x]), key=int)
    # the box has no resource heartbeat before its resource process starts: unknown is not silent
    assert ctl.resource_state("srv-z") == "unknown"


def test_the_snapshot_is_the_only_thing_that_leaves_the_cluster():
    c = Cluster(); ctl = VmsController(c.vars, c.objects, wall=c.wall, cluster="north")
    ws = _three_workers(c, ctl)
    for i in range(3):
        ctl.create_camera({"source": f"driverpack://file/{i}.mp4", "name": "gate" if i == 0 else f"cam{i}"})
    ctl.ensure_placed()
    ctl.publish_snapshot()
    # ONE OBJECT PER WORKER, the shape the heartbeats already have. Three cameras spread over three
    # workers is three objects — a cluster that grows publishes MORE of them, never a bigger one. That is
    # the whole difference from the single object this used to be, which grew with the cluster under a
    # store that caps an object at 64 KiB.
    keys = c.objects.list("vms/snapshot/")
    assert keys == ["vms/snapshot/" + w for w in sorted(ws)]
    held = [json.loads(c.objects.get(k)) for k in keys]
    rows = [r for sh in held for r in sh["cameras"]]
    assert len(rows) == 3                                                  # every camera, once
    gate = next(r for r in rows if r["name"] == "gate")
    assert gate["server"] in ("srv-a", "srv-b", "srv-c")
    # each shard says whose it is, and every row in it agrees
    assert all(all(r["worker"] == sh["worker"] for r in sh["cameras"]) for sh in held)
    assert all(sh["cluster"] == "north" for sh in held)
    assert all(sh["ts"] == c.wall() for sh in held)                        # a copy, with an age — the domain's RPO is this


def test_the_console_over_http():
    c = Cluster(); ctl = VmsController(c.vars, c.objects, wall=c.wall)
    ws = _three_workers(c, ctl)
    from w2cplatform.spec import SpecController
    from vms.config import REC_SPEC
    rec_con = SpecController(REC_SPEC, c.vars.as_writer("console", REC_SPEC.acl_console()), c.objects, wall=c.wall)   # the console's door to recordings
    srv = spec_console({"vms": ctl, "rec": rec_con}, "vms", c.servers["srv-a"].archive, worst_failover=48.0).serve("127.0.0.1", 0)
    port = srv.server_address[1]
    base = f"http://127.0.0.1:{port}"
    def call(method, path, body=None, headers=None):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req) as r: return r.status, r.read().decode()
        except urllib.error.HTTPError as e: return e.code, e.read().decode()
    st, out = call("POST", "/cameras", {"source": "driverpack://file/1.mp4", "labels": ["vlan:cctv-b"]}, {"Idempotency-Key": "k1"})
    assert st == 201 and json.loads(out)["worker"] is None                    # the console wrote the row; placement is the controller's
    # the SAME request again — the same body under the same key: one camera (a different body under it is 422, the key is one caller's for one body)
    assert call("POST", "/cameras", {"source": "driverpack://file/1.mp4", "labels": ["vlan:cctv-b"]}, {"Idempotency-Key": "k1"})[0] == 201 and len(ctl.cameras()) == 1
    assert call("POST", "/cameras", {"source": "driverpack://file/1.mp4"}, {"Idempotency-Key": "k1"})[0] == 422
    assert call("PUT", "/cameras/1", {"worker": A})[0] == 400
    placed = ctl.ensure_placed()[0].worker; assert placed in (B, C)       # the controller's pass, under the label
    ws[placed].reconcile_once(); ws[placed].heartbeat_once()
    st, out = call("GET", "/where/1"); d = json.loads(out)
    assert st == 200 and d["worker"] == d["directory"] and "on srv-" in d["reason"]
    st, out = call("GET", "/metrics")
    assert 'vms_failover_seconds{kind="worst"} 48.0' in out and "vms_workers_live 3" in out and "vms_cameras_running 1" in out
    st, out = call("GET", "/resources"); assert st == 200 and json.loads(out) == {}
    # the administrator's knob: one row, the console's to write, the controller's to read on its next pass
    st, out = call("GET", "/policy"); assert st == 200 and json.loads(out)["servers"] == "shared"
    assert call("PUT", "/policy", {"servers": "distinct"})[0] == 200 and ctl.policy() == {"servers": "distinct"}
    assert call("PUT", "/policy", {"servers": "everywhere"})[0] == 400 and ctl.policy() == {"servers": "distinct"}
    st, out = call("GET", "/servers"); assert json.loads(out)["policy"] == {"servers": "distinct"}
    call("PUT", "/policy", {"servers": "shared"})
    # the recorder at /rec/…: the page's Record toggle writes a recording row; placement is the rec controller's, not the console's
    st, out = call("GET", "/mounts"); assert json.loads(out) == {"root": "vms", "mounts": {"rec": json.loads(call("GET", "/rec/spec")[1])}}
    st, out = call("POST", "/rec/recordings", {"name": "1", "cam": "1", "retention_days": 7}, {"Idempotency-Key": "r1"}); assert st == 201 and json.loads(out)["worker"] is None
    assert c.vars.get("rec/recordings/1")[0]["retention_days"] == "7" and json.loads(call("GET", "/rec/policy")[1])["servers"] == "distinct"   # the recorder's own knob
    assert call("PUT", "/rec/recordings/1", {"worker": "r-srv-a-1"})[0] == 400
    assert call("DELETE", "/rec/recordings/1")[0] in (200, 204)
    st, out = call("GET", "/unplaceable"); assert json.loads(out) == []
    # srv-a's resource job, over real HTTP: the platform's routes and the event index over ITS tree
    from w2cplatform.resource import serve as serve_resource
    from w2cplatform.resource import platform_resource
    from tests.cluster.test_lesson3_resources import _recorder_with_footage
    t = c.wall()
    rec_a = _recorder_with_footage(c, "srv-a", "1", 1, ((t - 600, t),))                      # and srv-a's recorder, serving its volume
    res = platform_resource(c.servers["srv-a"].resource, "srv-a", "http://127.0.0.1:0", c.vars, c.objects, wall=c.wall)
    rsrv = serve_resource(res, "127.0.0.1", 0); res.url = f"http://127.0.0.1:{rsrv.server_address[1]}"; res.heartbeat()
    # an operator's mark: the console's own bucket on srv-a's resource; the console has no index — it asks srv-a's, by HTTP, and finds the `cam` field
    st, out = call("POST", "/marks", {"unit": "vms/1", "note": "check the gate"}, {"Idempotency-Key": "m1", "X-User": "murat"})
    m = json.loads(out); assert st == 201 and m["bucket"].startswith(f"console/{m['unit']}/e1/")
    st, out = call("GET", "/events?unit=vms/1"); ev = json.loads(out)
    assert st == 200 and [(e["subsystem"], e["kind"], e["user"], e["server"]) for e in ev["events"]] == [("console", "mark", "murat", "srv-a")] and ev["state"] == "live"
    # the page, and playback across the cluster: footage in srv-a's volume, at its recorder's door — the console hands
    # the door out with the recording's place and carries none of it (the boundary's step 6)
    assert "<video" in call("GET", "/")[1]
    page = rec_a.archive_url + "/door"
    tl = json.loads(urllib.request.urlopen(f"{page}/timeline/1").read())
    assert [(s["recorder"], s["volume"]) for s in tl] == [(rec_a.name, "srv-a")]
    with urllib.request.urlopen(f"{page}/{tl[0]['media']}?from={t - 120}&to={t - 60}") as r:
        assert r.status == 200 and r.headers["Content-Type"] == "video/mp4" and r.read()[4:8] == b"ftyp"   # read to its end: the last chunk comes when its slot is free again
    try:
        urllib.request.urlopen(f"{page}/export/1?from={t - 3000}&to={t - 2000}"); raise AssertionError("a file of nothing")
    except urllib.error.HTTPError as e:
        assert e.code == 404                                                       # nothing recorded there
    assert call("PUT", "/cameras/1", {"enabled": False})[0] == 200 and ctl.camera(1)["enabled"] is False
    assert call("DELETE", "/cameras/1")[0] == 200 and ctl.cameras() == [] and call("DELETE", "/cameras/1")[0] == 404
    assert ctl.unplace_deleted() == [1] and ctl.assignment(placed).units == []   # the controller takes the placement back
    rsrv.shutdown(); rec_a.after_stop()
    srv.shutdown()


def test_the_clusters_console_asks_about_the_camera_a_route_names_exactly_as_the_boxes_does():
    """М10's sixth review, found while sweeping every door: this module's console is built by a function of its own
    (a `make_console` of the cluster's own), which wired nothing of what М10's does — `/timeline/<cam>` and `/export/<cam>`
    were not routes that name a camera, so in a cluster that asks who is calling a viewer of camera 1 was given camera
    2's timeline and footage for any grant at all; a backfill was an administrator's, not an operator's; the
    recorder's mount served neither the archives nor the number its scaling check asks for. One function wires a
    console, whoever builds it (`host.spec_console`) — and since the boundary's step 6 the footage is a
    holder's door, handed out with the unit's place to whoever may view it: `/where/<cam>`, `/rec/where/<recording>`."""
    from w2cplatform.access import Denied
    from w2cplatform.spec import SpecController
    from vms.config import REC_SPEC

    class Tokens:                                                     # an `Access` with no cryptography: a token is a name
        grants = {"viewer": [("view", "vms/1")], "guard": [("edit", "vms/1")], "admin": [("admin", None)]}   # units: <sub>/<id>

        def who(self, token):
            if token not in self.grants:
                raise Denied(401, "nobody's token")
            return {"sub": token}

        def may(self, payload, capability, unit, labels):
            rank = {"view": 0, "edit": 1, "admin": 2}
            mine = self.grants[payload["sub"]]
            if unit is None and capability == "view":
                return bool(mine)
            return any(rank[c] >= rank[capability] and u in (unit, None) for c, u in mine)

    c = Cluster(); ctl = VmsController(c.vars, c.objects, wall=c.wall)
    rec = SpecController(REC_SPEC, c.vars, c.objects, wall=c.wall)
    m = spec_console({"vms": ctl, "rec": rec}, "vms")
    for con in (m.root, *m.mounts.values()):
        con.gate.impl = Tokens()
    srv = m.serve("127.0.0.1", 0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(method, path, token, body=None, key=[0]):
        key[0] += 1
        req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                     headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"k{key[0]}",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r: return r.status, r.read().decode()
        except urllib.error.HTTPError as e: return e.code, e.read().decode()
    try:
        for i in (1, 2):
            assert call("POST", "/cameras", "admin", {"source": f"driverpack://file/{i}.mp4"})[0] == 201
            assert call("POST", "/rec/recordings", "admin", {"name": str(i), "cam": str(i)})[0] == 201
        t = c.wall()
        assert call("GET", "/rec/where/1", "viewer")[0] in (200, 404)                  # her camera's recording: its door
        assert call("GET", "/rec/where/2", "viewer")[0] == 403                          # it was 200: any grant at all
        assert call("GET", "/where/2", "viewer")[0] == 403                              # …and the device's own with it
        ask = lambda rec: {"unit": f"rec/{rec}", "from": t - 120, "to": t - 60}          # noqa: E731 — a backfill (step 6)
        assert call("POST", "/rec/requests", "viewer", ask(1))[0] == 403                # to act, `edit`
        assert call("POST", "/rec/requests", "guard", ask(1))[0] == 202                 # …on her camera
        assert call("POST", "/rec/requests", "guard", ask(2))[0] == 403
        assert call("PUT", "/rec/recordings/2", "guard", {"retention_days": 1})[0] == 403
        assert call("GET", "/rec/volumes", "admin")[0] == 200                           # the archives, as on a box
        assert "rec_recorders_needed" in call("GET", "/rec/metrics", "admin")[1]        # what `w2c-spares.sh` reads for recorders
        assert m.mounts["rec"].journal is m.root.journal and m.mounts["rec"].spec.about_sub == "vms"   # a recording is about its camera
    finally:
        srv.shutdown()



def test_the_vms_jobs_keep_a_requests_until_on_a_cluster_as_on_a_box():
    """The twelfth review, on the author's answer ("REREAD … any console"): in М11 nothing ran the loop that turns a
    request into work and ends it at its `until` — a recording asked for ten minutes went on, and nobody in the cluster
    kept the end. The cluster's console ran the box's turns in its own process until the boundary's step 7; the console
    is the platform's now, and the turns are the VMS's own process on every server (`python3 -m vms jobs`,
    `vms-jobs.service`), through the console's socket and its rights: a scenario's "record camera 1 for ten minutes"
    becomes a recording with an end, the request goes, and the recording ends when its end has come."""
    import vms.__main__ as m
    from vms.config import REC_SPEC
    from vms.jobs import Remembered
    from w2cplatform.spec import SpecController
    c = Cluster(); c.resources_up()
    con = c.console("srv-a")
    rec = SpecController(REC_SPEC, con.vars, con.objects, wall=c.wall)
    con.create_camera({"source": "driverpack://file/1.mp4"})
    now = c.wall()
    c.vars.put("rec/requests/f1-0", {"action": "record", "cam": "1", "minutes": "10", "valid_until": str(now + 30)})
    mem = Remembered()
    m._requests_turn(rec, None, None, mem, now=now)
    requests.turn([rec, con], sweep=True)
    assert rec.unit("1-auto")["until"] == now + 600 and c.vars.get("rec/requests/f1-0")[0] is None
    m._requests_turn(rec, None, None, mem, now=now + 300)
    assert "1-auto" in [str(u["id"]) for u in rec.units()]                  # not yet
    m._requests_turn(rec, None, None, mem, now=now + 601)
    assert "1-auto" not in [str(u["id"]) for u in rec.units()]              # its end came: ended
