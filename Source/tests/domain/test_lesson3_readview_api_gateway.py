"""Lesson 3 — the camera list from the workers' heartbeats; staleness shown;
one cause per dead server; the API refuses placement at both levels and is
idempotent; the gateway fans out and the worker sees one viewer."""
import json
import urllib.request
from w2cplatform.domain.api import ApiError, ConsoleAPI
from w2cplatform.domain.console import Console
from w2cplatform.domain.federation import DomainDirectory
from vms.domainpart.gateway import Forbidden, Gateway, LiveTee, WorkerLiveEndpoint
from w2cplatform.domain.readview import ReadView
from tests.domain.conftest import Clock, Running, heartbeat, make_domain, snapshot


def _four_workers(wall):
    fed, links = make_domain({"north": (), "south": ()}, "north")
    n, s = fed.clusters["north"], fed.clusters["south"]
    for cl, w, srv, cams in (("north", "w-0", "srv-1", range(1, 51)), ("north", "w-1", "srv-1", range(51, 101)),
                             ("north", "w-2", "srv-2", range(101, 151)), ("south", "w-0", "srv-9", range(151, 201))):
        heartbeat(fed.clusters[cl], w, list(cams), ts=wall(), server=srv)
    return fed, links


def test_two_hundred_cameras_from_heartbeats_nobody_called():
    wall = Clock(10_000.0); fed, links = _four_workers(lambda: wall() - 3)
    view = ReadView(fed, lost_after=45, wall=wall)
    view.refresh()
    page = view.list(page=1, size=50)
    assert page["total"] == 200 and len(page["rows"]) == 50 and page["complete"]
    assert page["rows"][0]["as_of"] == "as of 3 s ago" and page["rows"][0]["worker_state"] == "live"
    assert view.list(q="cam175")["rows"][0]["cluster"] == "south" and view.list(q="cam175")["rows"][0]["worker"] == "w-0"
    assert view.list(cluster="south")["total"] == 50
    assert view.causes() == []


def test_the_list_from_a_real_cluster():
    """М11's controller and workers running; the domain's view is exactly their heartbeats."""
    fed, _ = make_domain({"north": (), "south": ()}, "north"); wall = Clock(10_000.0)
    n = Running(fed.clusters["north"], wall, workers=(("w-0", "srv-1"), ("w-1", "srv-2")), capacity=2)
    n.create(1, 2, 3)
    view = ReadView(fed, wall=wall); view.refresh()
    rows = view.list(size=10)["rows"]
    assert [r["phase"] for r in rows] == ["running"] * 3 and {r["server"] for r in rows} == {"srv-1", "srv-2"}
    assert {r["worker"] for r in rows} == {"w-0", "w-1"} and rows[0]["observed_revision"] == rows[0]["revision"] == 1


def test_a_camera_nobody_is_running_is_in_the_list_and_says_so():
    """The defect this closes: the list came only from heartbeats, so a camera that
    NOTHING is running was not in it at all. An operator could add a camera, watch
    the cluster fail to place it — no capacity, no worker with the right labels —
    and find nothing in the domain. Not an error, not a greyed row: absence, which
    is the most confusing shape a fault can take.

    A heartbeat is an observation; the snapshot is the configuration. The list now
    carries both and keeps them apart — the same pair М10A's console shows inside
    one cluster as `rows` beside `configured`."""
    fed, _ = make_domain({"north": ()}, "north")
    wall = Clock()
    # two cameras the cluster knows about: one held by a worker, one nobody could place
    snapshot(fed.clusters["north"], {7: ("w-0", "srv-1"), 9: ("", "?")}, ts=wall())
    heartbeat(fed.clusters["north"], "w-0", [7], ts=wall())
    view = ReadView(fed, wall=wall)
    view.refresh()

    rows = {r["ref"] or str(r["unit"]): r for r in view.list()["rows"]}
    assert set(rows) == {"7", "9"}, "the camera nobody runs is missing from the list"
    assert rows["7"]["worker_state"] == "live" and rows["7"]["phase"] == "running"
    assert rows["9"]["worker_state"] == "configured" and rows["9"]["worker"] == ""
    assert "no worker reports it" in rows["9"]["as_of"]
    assert view.list()["total"] == 2


def test_a_camera_is_not_listed_twice_when_both_sources_have_it():
    """The observation wins, because it says more. The two sources name a camera
    differently — the worker's status entry and the cluster's snapshot row — so the
    key is the one the DOMAIN uses, `ref`, and not the cluster's own number, of
    which every cluster has its own."""
    fed, _ = make_domain({"north": (), "south": ()}, "north")
    wall = Clock()
    snapshot(fed.clusters["north"], {7: ("w-0", "srv-1")}, ts=wall())
    heartbeat(fed.clusters["north"], "w-0", [7], ts=wall())
    snapshot(fed.clusters["south"], {7: ("w-0", "srv-9")}, ts=wall())   # a different camera 7
    heartbeat(fed.clusters["south"], "w-0", [7], ts=wall())
    view = ReadView(fed, wall=wall)
    view.refresh()

    rows = view.list()["rows"]
    assert len(rows) == 2, [r["cluster"] for r in rows]
    assert {r["cluster"] for r in rows} == {"north", "south"}
    assert all(r["worker_state"] == "live" for r in rows), "an observed camera came back as configured too"


def test_a_cluster_that_stopped_publishing_is_a_different_silence_from_a_silent_worker():
    """Two silences, and an operator does different things about them.

    A silent WORKER means its cameras are not running: `causes()` reports it. A stale
    SNAPSHOT means the cluster is running perfectly well and the domain's picture of
    it has stopped moving — nothing is broken where the operator would look.

    `ages()` has computed this since Lesson 1 and nothing outside a test ever called
    it, so the one number that says "this cluster's controller stopped publishing"
    was computable and never computed. Now the list carries it."""
    fed, _ = make_domain({"north": (), "south": ()}, "north")
    wall = Clock()
    snapshot(fed.clusters["north"], {1: ("w-0", "srv-1")}, ts=wall())
    snapshot(fed.clusters["south"], {2: ("w-0", "srv-9")}, ts=wall())
    heartbeat(fed.clusters["north"], "w-0", [1], ts=wall())
    heartbeat(fed.clusters["south"], "w-0", [2], ts=wall())
    view = ReadView(fed, wall=wall)
    view.refresh()
    assert view.list()["rpo"] == {"north": 0.0, "south": 0.0}

    # north's controller stops publishing; its worker keeps reporting, so nothing else notices
    wall.advance(120)
    heartbeat(fed.clusters["north"], "w-0", [1], ts=wall())
    heartbeat(fed.clusters["south"], "w-0", [2], ts=wall())
    snapshot(fed.clusters["south"], {2: ("w-0", "srv-9")}, ts=wall())
    view.refresh()

    assert view.list()["rpo"] == {"north": 120.0, "south": 0.0}
    assert view.causes() == [], "a stale snapshot is not a silent worker, and must not be reported as one"
    assert all(r["worker_state"] == "live" for r in view.list()["rows"]), "the cameras are fine, and the list says so"


def test_kill_a_server_one_cause_displayed():
    wall = Clock(10_000.0); fed, links = _four_workers(wall)
    view = ReadView(fed, lost_after=45, wall=wall)
    view.refresh()
    wall.advance(100)                                                       # srv-1 died: w-0 and w-1 go silent together
    heartbeat(fed.clusters["north"], "w-2", list(range(101, 151)), ts=wall(), server="srv-2")
    heartbeat(fed.clusters["south"], "w-0", list(range(151, 201)), ts=wall(), server="srv-9")
    view.refresh()
    causes = view.causes()
    assert len(causes) == 1 and causes[0].scope == "server" and causes[0].name == "north/srv-1"
    assert causes[0].workers == ["w-0", "w-1"] and causes[0].units == 100
    assert causes[0].sentence().startswith("server silent: north/srv-1 for 100 s")
    rows = view.list(size=200)["rows"]
    stale = [r for r in rows if r["worker_state"] == "stale"]
    assert len(stale) == 100 and "last known state" in stale[0]["as_of"]   # still listed, greyed, with their age


def test_unreachable_cluster_keeps_last_known_rows_and_says_so():
    wall = Clock(10_000.0); fed, links = _four_workers(wall)
    view = ReadView(fed, lost_after=45, wall=wall)
    view.refresh()
    links["south"].up = False
    wall.advance(30)
    view.refresh()
    page = view.list(cluster="south", size=100)
    assert page["total"] == 50 and page["clusters"]["south"] == "unreachable" and not page["complete"]
    assert page["rows"][0]["worker_state"] == "unreachable"
    assert view.causes()[0].scope == "cluster" and view.causes()[0].units == 50


class FakeClusterConsole:
    def __init__(self): self.edits = []; self.creates = []
    def update_unit(self, camera, fields, subject):
        self.edits.append((camera, fields, subject)); return {"revision": len(self.edits) + 1}
    def create_unit(self, fields, subject):
        self.creates.append(fields); return {"id": len(self.creates), "worker": "w-0"}


def test_api_refuses_placement_at_both_levels_and_is_idempotent():
    fed, _ = make_domain({"north": (), "south": ()}, "north")
    snapshot(fed.clusters["south"], {7: ("w-0", "srv-9")}, ts=0)
    consoles = {"south": FakeClusterConsole()}
    api = ConsoleAPI(DomainDirectory(fed), consoles.__getitem__)
    r1 = api.update_unit(7, {"name": "gate"}, idempotency_key="k1")
    r2 = api.update_unit(7, {"name": "gate"}, idempotency_key="k1")            # the same PUT, not a second edit
    assert r1 is r2 and len(consoles["south"].edits) == 1 and r1["cluster"] == "south" and r1["worker"] == "w-0" and not r1["authenticated"]
    for bad in ({"worker": "w-1"}, {"cluster": "north"}, {"server": "srv-1"}, {"placement": {}}, {"phase": "running"}, {"epoch": 9}):
        try:
            api.update_unit(7, bad, idempotency_key="k2"); raise AssertionError("must refuse")
        except ApiError as e:
            assert e.status == 400 and "may not set" in e.detail
    try:
        api.update_unit(99, {"name": "x"}, idempotency_key="k3"); raise AssertionError("must 404")
    except ApiError as e:
        assert e.status == 404
    c = api.create_unit({"name": "new", "source": "driverpack://file/n.mp4", "ref": "12"}, cluster="south", idempotency_key="k4")
    assert c["cluster"] == "south" and c["result"]["worker"] == "w-0"              # the cluster chose the worker; the domain forwarded


def test_api_says_503_not_404_when_a_cluster_is_unreachable():
    fed, links = make_domain({"north": (), "south": ()}, "north")
    snapshot(fed.clusters["south"], {7: ("w-0", "srv-9")}, ts=0)
    links["south"].up = False
    api = ConsoleAPI(DomainDirectory(fed), lambda n: FakeClusterConsole())
    try:
        api.update_unit(7, {"name": "x"}, idempotency_key="k"); raise AssertionError()
    except ApiError as e:
        assert e.status == 503 and "unreachable" in e.detail


def test_gateway_fans_out_and_the_worker_sees_one_viewer():
    tees = {7: LiveTee(7)}
    def authorise(token, camera):
        if token != "alice-token": raise Forbidden(token)
        return "alice"
    ep = WorkerLiveEndpoint("w-0", tees, authorise)
    gw = Gateway("gw-1", where=lambda c: "w-0", endpoint=lambda n: ep)
    viewers = [gw.watch(7, "alice-token", f"browser-{i}", maxsize=5) for i in range(50)]
    assert tees[7].viewers == 1 and gw.viewers(7) == 50                  # ONE subscription on the worker, fifty out
    try:
        gw.watch(7, "bad-token", "browser-x"); raise AssertionError("the cluster's authoriser decides")
    except Forbidden:
        pass
    for f in range(100):
        tees[7].push(f"frame-{f}")                                       # the worker's push never blocks
    assert gw.pump() == 30 and tees[7].subscribers["gw-1"].dropped == 70  # upstream leaky queue (30) leaked
    assert all(len(v.q) == 5 and v.dropped == 25 for v in viewers)       # every slow viewer leaked its own
    for i in range(50):
        gw.leave(7, f"browser-{i}")
    assert tees[7].viewers == 0 and gw.viewers(7) == 0


def test_gateway_follows_a_failover():
    eps = {"w-0": WorkerLiveEndpoint("w-0", {7: LiveTee(7)}, lambda t, c: "alice"),
           "w-1": WorkerLiveEndpoint("w-1", {7: LiveTee(7)}, lambda t, c: "alice")}
    home = {"cam": "w-0"}
    gw = Gateway("gw", where=lambda c: home["cam"], endpoint=eps.__getitem__)
    gw.watch(7, "t", "b1")
    home["cam"] = "w-1"                                                   # the controller moved it; the directory says so
    assert gw.reconnect(7, "t") == "w-1" and eps["w-1"].tees[7].viewers == 1 and gw.viewers(7) == 1


def test_console_over_http():
    fed, _ = make_domain({"north": (), "south": ()}, "north")
    snapshot(fed.clusters["south"], {7: ("w-0", "srv-9")}, ts=1000.0)
    heartbeat(fed.clusters["south"], "w-0", [7], ts=1000.0, server="srv-9")
    view = ReadView(fed, wall=lambda: 1002.0)
    api = ConsoleAPI(DomainDirectory(fed), lambda n: FakeClusterConsole())
    con = Console(DomainDirectory(fed), view, api, refresh_interval=0.05)
    srv = con.serve(port=0)
    port = srv.server_address[1]
    try:
        import time; time.sleep(0.2)
        body = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/vms/cameras"))
        assert body["total"] == 1 and body["rows"][0]["as_of"] == "as of 2 s ago"
        w = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/where/7"))
        assert w["cluster"] == "south" and w["worker"] == "w-0" and w["complete"]
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/vms/cameras/7", data=b'{"name":"x"}', method="PUT",
                                     headers={"Idempotency-Key": "abc"})
        assert json.load(urllib.request.urlopen(req))["cluster"] == "south"
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/vms/cameras/7", data=b'{"worker":"w-1"}', method="PUT",
                                     headers={"Idempotency-Key": "def"})
        try:
            urllib.request.urlopen(req); raise AssertionError()
        except urllib.error.HTTPError as e:
            assert e.code == 400
    finally:
        con.stop(srv)


def test_the_domains_console_is_a_door_like_the_others_bounded_and_with_a_ceiling_on_a_body():
    """М10's sixth review, its sweep of every HTTP door: this one was a thread for every connection, with no deadline
    on a request, and it read a body to whatever `Content-Length` said before it looked at the caller's token. It is
    served by the platform's bounded server now (`ConsoleServer`: so many connections, so many to one address), reads
    its request line and headers under a deadline (`Deadlined`), and a body past `MAX_BODY` is 413 with nothing read."""
    import socket
    import time
    from w2cplatform.console import ConsoleServer
    fed, _ = make_domain({"north": (), "south": ()}, "north")
    api = ConsoleAPI(DomainDirectory(fed), lambda n: FakeClusterConsole())
    con = Console(DomainDirectory(fed), ReadView(fed, wall=lambda: 1002.0), api, refresh_interval=0.05)
    srv = con.serve(port=0)
    port = srv.server_address[1]

    def raw(data: bytes) -> tuple[bytes, float]:
        s = socket.create_connection(("127.0.0.1", port)); s.settimeout(5)
        began = time.monotonic(); s.sendall(data); out = b""
        try:
            while True:
                got = s.recv(65536)
                if not got:
                    break
                out += got
        except socket.timeout:
            pass
        s.close()
        return out, time.monotonic() - began
    try:
        assert isinstance(srv, ConsoleServer) and srv.bounds.per_address < srv.bounds.limit
        reply, took = raw(b"PUT /api/vms/cameras/7 HTTP/1.1\r\nHost: x\r\nIdempotency-Key: k\r\nContent-Length: 104857600\r\n\r\n")
        assert reply.startswith(b"HTTP/1.0 413") and took < 2.0          # a hundred megabytes declared: not read, not waited for
        reply, took = raw(b"PUT /api/vms/cameras/7 HTTP/1.1\r\nHost: x\r\nIdempotency-Key: k\r\nContent-Length: lots\r\n\r\n")
        assert reply.startswith(b"HTTP/1.0 400")
        held = [socket.create_connection(("127.0.0.1", port)) for _ in range(srv.bounds.per_address)]
        for s in held:
            s.sendall(b"GET /api")                                       # half a request line each: this address's share
        time.sleep(0.2)
        reply, took = raw(b"GET /healthz HTTP/1.1\r\nHost: x\r\n\r\n")
        assert reply.startswith(b"HTTP/1.0 503") and took < 1.0          # the next from it: 503 on the spot, no thread
        for s in held:
            s.close()
    finally:
        con.stop(srv)


def test_the_domains_console_has_the_consoles_reserve_and_a_listed_monitor_is_answered_whoever_floods():
    """М10's seventh review, major: the domain's console (and the signer) had `Bounds(64, 16)` with no reserve and no
    lane for the box — four addresses took every connection. Its bounds are the console's now: `CONSOLE_PER_ADDRESS`
    an address, and once the common connections are all gone `/healthz` is still answered on the reserve, and to an
    address named in `CONSOLE_MONITORS` on its own lane; anything else from the network is 503."""
    import os
    import socket
    import time
    from w2cplatform import console as wc
    was = os.environ.get("CONSOLE_MONITORS")
    os.environ["CONSOLE_MONITORS"] = "192.0.2.100"
    fed, _ = make_domain({"north": (), "south": ()}, "north")
    api = ConsoleAPI(DomainDirectory(fed), lambda n: FakeClusterConsole())
    con = Console(DomainDirectory(fed), ReadView(fed, wall=lambda: 1002.0), api, refresh_interval=0.05)
    srv = con.serve(port=0)
    port, who, held = srv.server_address[1], {}, []
    srv.peer_of = lambda request, ca: (who.get(ca[1], str(ca[0])), False)

    def conn(addr: str) -> socket.socket:
        s = socket.socket(); s.bind(("127.0.0.1", 0)); who[s.getsockname()[1]] = addr
        s.connect(("127.0.0.1", port))
        return s

    def ask(addr: str, path: str) -> bytes:
        s = conn(addr); s.settimeout(5); s.sendall(f"GET {path} HTTP/1.1\r\nHost: x\r\n\r\n".encode()); out = b""
        try:
            while True:
                got = s.recv(65536)
                if not got:
                    break
                out += got
        except socket.timeout:
            pass
        s.close()
        return out
    try:
        assert srv.bounds.per_address == wc.CONSOLE_PER_ADDRESS and srv.bounds.reserve == wc.CONSOLE_RESERVE
        for i in range(srv.bounds.limit // srv.bounds.per_address):     # every common connection, an address's share each
            for _ in range(srv.bounds.per_address):
                s = conn(f"203.0.113.{i}"); s.sendall(b"GET /api"); held.append(s)
        for _ in range(50):
            if srv.bounds.used["common"] == srv.bounds.limit:
                break
            time.sleep(0.02)
        assert srv.bounds.used["common"] == srv.bounds.limit
        assert ask("192.0.2.7", "/healthz").startswith(b"HTTP/1.0 200")             # the reserve
        busy = ask("192.0.2.7", "/api/vms/cameras")
        assert busy.startswith(b"HTTP/1.0 503") and b"/healthz" in busy               # nothing else on it
        assert ask("192.0.2.100", "/healthz").startswith(b"HTTP/1.0 200")           # a listed monitor: its own lane
    finally:
        for s in held:
            s.close()
        con.stop(srv)
        if was is None:
            os.environ.pop("CONSOLE_MONITORS", None)
        else:
            os.environ["CONSOLE_MONITORS"] = was


def _units() -> dict:
    """The domain's units (`deploy/domain/systemd`), each parsed as the cluster's tests parse theirs."""
    import os
    from tests.cluster.test_recorder_job import unit
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "deploy", "domain",
                        "systemd")
    return {n[:-len(".service")]: unit(os.path.join(here, n)) for n in os.listdir(here) if n.endswith(".service")}


def _env_lines(path: str) -> dict:
    """`NAME=value` lines of an env example, the commented ones too (`#NAME=value`: what the site uncomments)."""
    import re
    out = {}
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^#?([A-Z][A-Z0-9_]*)=(\S+)", line)
        if m:
            out.setdefault(m.group(1), m.group(2))
    return out


def test_what_the_doors_open_in_code_the_units_turn_on_and_a_monitor_is_an_address_not_a_network():
    """М10's eighth review, minor: the domain's console and the signer had the reserve, the box's own door and the
    monitors' lane in code, and their deploy set none of it. Their units name the unix sockets — each in the unit's
    own runtime directory, 0700 — and the monitors (the box's loopback; the site adds its scrapers' addresses, never a
    network). The tokens' socket is in a directory made at boot, setgid to the books' worker's group: the socket takes
    that group, and the worker opens it and nothing else of the box does."""
    import os
    u = _units()
    console, signer = u["w2c-domain-console"], u["w2c-domain"]
    assert console["env"]["DOMAIN_CONSOLE_UNIX"] == "/run/w2c-domain-console/console.sock"
    assert console["RuntimeDirectory"] == ["w2c-domain-console"] and console["RuntimeDirectoryMode"] == ["0700"]
    assert signer["env"]["SIGNER_UNIX"] == "/run/w2c-domain/signer.sock"
    assert signer["RuntimeDirectory"] == ["w2c-domain"] and signer["RuntimeDirectoryMode"] == ["0700"]
    for door in (console, signer):
        assert door["env"]["CONSOLE_MONITORS"].split(",")[0] == "127.0.0.1"
        assert "/" not in door["env"]["CONSOLE_MONITORS"]                       # an address, not a network
    assert signer["env"]["SIGNER_TOKENS_UNIX"] == u["vms-domainpart"]["env"]["SIGNER_TOKENS_UNIX"] == "/run/w2c-signer/tokens.sock"
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    tmpfiles = open(os.path.join(here, "deploy", "domain", "systemd", "w2c-domain.tmpfiles")).read()
    assert "d /run/w2c-signer 2750 w2c vms-vmsdomain -" in tmpfiles
    assert "vms-vmsdomain" in u["vms-domainpart"]["SupplementaryGroups"][0].split()
    assert "vms-vmsdomain" not in signer["SupplementaryGroups"][0].split()       # the directory gives the group, not the signer


def test_every_domain_unit_runs_a_verb_of_the_runner_by_its_roles_socket():
    """The domain's units in the cluster's form (no orchestrator): each runs `w2c-run.sh <verb>`, names its role's socket
    and joins that role's group first (the rights file's), loads the ring as a credential, and lists no
    `EnvironmentFile=` — the site's lines are `w2c.env`'s, read under what the unit says. And the runner turns each verb
    into the module it names (a `python3` that prints what it was given). No Nomad file is left in `deploy/domain`."""
    import json
    import os
    import subprocess
    import tempfile
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    groups = {r: g["group"] for r, g in
              json.load(open(os.path.join(here, "deploy", "cluster", "configstore-rights.json")))["roles"].items()}
    want = {"w2c-domain": ("domain", "signer", "w2c", "-m w2cplatform.domain.signer_service"),
            "w2c-domain-console": ("domain", "domainconsole", "w2c", "-m w2cplatform.domain.console"),
            "w2c-domainagent": ("domainagent", "domainagent", "w2c", "-m w2cplatform.domain.agent"),
            "vms-domainpart": ("vmsdomain", "vms domainpart", "vms", "-m vms domainpart")}
    u = _units()
    assert sorted(u) == sorted(want)
    d = tempfile.mkdtemp(prefix="run-")
    py = os.path.join(d, "python3")
    with open(py, "w") as f:
        f.write("#!/bin/sh\necho \"$@\"\n")
    os.chmod(py, 0o755)
    os.symlink(here, os.path.join(d, "Source"))
    for name, (role, verb, user, module) in want.items():
        s = u[name]
        assert s["env"]["PLATFORM_STORE"] == f"configstore:///run/configstore/{role}.sock", name
        assert s["SupplementaryGroups"][0].split()[0] == groups[role], name
        assert s["User"] == [user] and s["ExecStart"] == [f"/opt/w2c/bin/w2c-run.sh {verb}"], name
        assert s["env"]["SECRETS_KEY"] == "%d/platform.key" and s["LoadCredential"], name
        assert "EnvironmentFile" not in s, f"{name}: a file would override what the unit says"
        env = {"PATH": os.environ["PATH"], "W2C_ENV": os.devnull, "VMS_ENV": os.devnull, "PYTHON": py, "W2C_HOME": d}
        out = subprocess.run(["sh", os.path.join(here, "deploy", "cluster", "w2c-run.sh"), *verb.split()], env=env,
                             capture_output=True, text=True, check=True).stdout.splitlines()
        assert out[0] == module, (name, out)
    left = os.listdir(os.path.join(here, "deploy", "domain"))
    assert not [n for n in left if n.endswith((".hcl", ".hcl.md")) or "nomad" in n], left


def test_the_domains_units_name_stores_that_open():
    """The twelfth review, major 22: the domain's deploy named its stores by a backend that is gone, and `open_vars`
    refused it before anything started. The units' lines, with the site's (`domain.env.example`, the platform's
    `OBJECTS`), now build the federation (`runtime.federation_from_env`) for the console and for the VMS's books — a
    bare name in `CLUSTERS` is this server's own cluster, opened by EACH unit's own socket — and open the agent's
    store; a member's agent carries through the domain's door and reads no store of the holder's."""
    import os
    import tempfile
    from w2cplatform.domain.runtime import federation_from_env
    from w2cplatform.variables import open_vars
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    site = _env_lines(os.path.join(here, "deploy", "domain", "systemd", "domain.env.example"))
    platform = _env_lines(os.path.join(here, "deploy", "cluster", "systemd", "w2c.env.example"))
    objects = tempfile.mkdtemp(prefix="objects-")
    u = _units()
    for name in ("w2c-domain-console", "vms-domainpart"):
        env = {"CLUSTERS": site["CLUSTERS"], "DOMAIN_HOLDER": site["DOMAIN_HOLDER"],
               "PLATFORM_STORE": u[name]["env"]["PLATFORM_STORE"],
               "OBJECTS": platform["OBJECTS"].replace("/data/platform/objects", objects)}
        saved = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            fed = federation_from_env()
        finally:
            for k, v in saved.items():
                os.environ.pop(k) if v is None else os.environ.__setitem__(k, v)
        assert sorted(fed.clusters) == ["north", "south"] and fed.domain_holder.name == "north", name
    assert open_vars(u["w2c-domainagent"]["env"]["PLATFORM_STORE"]) is not None
    member = open(os.path.join(here, "deploy", "domain", "systemd", "domain.env.example")).read()
    assert "\nDOMAIN_URL=https://" in member                                   # a member carries through the domain's door
    assert "\nDOMAIN_CONFIG_URL=" not in member                                 # …only the holder's own agent reads a store


def test_the_signer_opens_its_store_through_its_roles_socket_under_the_clusters_rights():
    """The thirteenth review, major 11: the signer opens `configstore:///run/configstore/domain.sock`, and no rights file
    named a role `domain` — so no daemon opened that socket, its first `get` was `StoreUnavailable` and the job went
    round its restarts. The test above only made the handle (`open_vars` is lazy), so it said nothing of it. Here a real
    daemon with М11's committed rights file, its sockets in a directory of the test's: the signer's own store URL (its
    default, and its unit's line; the books' worker's from its unit) is a socket the daemon opened, and the signer's first start runs
    through it — its keys made and kept, the key set published, a person created, logged in and the people published,
    a book written — and a second start reads the same keys. The agent's socket reads the key set but not the keys."""
    import inspect
    import os
    import re
    import shutil
    import tempfile
    import pytest
    from w2cplatform.domain import signer_service
    from w2cplatform.domain.agent import KEYS_PATH, DomainPublisher
    from w2cplatform.domain.identity import IdentityStore
    from w2cplatform.trust.signer import Signer
    from w2cplatform.configstore import LocalBackend, StoreDaemon
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.storemachine import Rights
    from w2cplatform.variables import Forbidden, open_vars
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    rights = Rights.load(os.path.join(here, "deploy", "cluster", "configstore-rights.json"))
    own = re.search(r'"(configstore:///run/configstore/\w+\.sock)"', inspect.getsource(signer_service.main)).group(1)
    units = _units()
    assert units["w2c-domain"]["env"]["PLATFORM_STORE"] == own                           # the unit says the signer's default
    books = units["vms-domainpart"]["env"]["PLATFORM_STORE"]
    assert books == "configstore:///run/configstore/vmsdomain.sock"                     # the books: the VMS worker's role
    d = tempfile.mkdtemp(prefix="cs")                                  # a socket's path is short: the run's root is
    daemon = StoreDaemon(LocalBackend("north", 1000), node_id="north", sockets=d, rights=rights)
    try:
        assert os.path.exists(own.replace("configstore://", "").replace("/run/configstore", d)), sorted(os.listdir(d))
        vars_ = open_vars(own.replace("/run/configstore", d))
        assert vars_.get("domain/signer")[0] is None                                       # answered: nothing there yet
        signer = Signer("acme", vars_)                                                     # its keys made, and kept
        DomainPublisher(vars_).publish_keys(signer.tokens.keyset())
        ids = IdentityStore(signer, vars_, FsObjectStore(os.path.join(d, "objects")), publish_floor=0)
        ids.create_local("ann", "a long enough password", ["admin"])
        assert ids.login("ann", "a long enough password") and ids.publish(force=True)
        open_vars(books.replace("/run/configstore", d)).put("domain/vms/sources/north", {"book": "{}"})
        assert Signer("acme", vars_).tokens.keyset().to_items() == signer.tokens.keyset().to_items()
        agent = open_vars(f"configstore://{d}/domainagent.sock")
        assert agent.get(KEYS_PATH)[0] is not None
        with pytest.raises(Forbidden):
            agent.get("domain/signer")
    finally:
        daemon.stop()
        shutil.rmtree(d, ignore_errors=True)


def test_the_domain_holder_console_draws_the_domain_from_one_object_and_says_when_it_is_old():
    """One tree for the site (feedback X). The domain leaves its view as one object in the domain holder's own
    object store on every pass; that cluster's console serves it at /domain and asks no member anything. A
    cluster that does not hold the domain has no such object, and says it does not know the others. An old view
    is served with its age and `silent`, never as if it were current."""
    from w2cplatform.console import domain_view
    wall = Clock(10_000.0); fed, links = _four_workers(wall)
    north, south = fed.clusters["north"], fed.clusters["south"]
    view = ReadView(fed, lost_after=45, wall=wall)
    view.refresh(); view.publish(north.objects, {"vms/crossings": {"SN7": "north"}})

    st, d = domain_view(north.objects, wall())
    assert st == 200 and d["complete"] and not d["silent"] and d["age"] == 0
    assert d["members"]["south"]["state"] == "ok" and len(d["units"]) == 200 and d["tables"] == {"vms/crossings": {"SN7": "north"}}
    assert {c["cluster"] for c in d["units"] if c["worker"] == "w-0"} == {"north", "south"}
    assert domain_view(south.objects, wall())[0] == 404      # not the domain's holder: it knows only itself

    links["south"].up = False; wall.advance(30); view.refresh(); view.publish(north.objects)
    st, d = domain_view(north.objects, wall())
    assert not d["complete"] and d["members"]["south"]["state"] == "unreachable"
    assert any(c.startswith("cluster unreachable: south") or "south" in c for c in d["causes"])

    wall.advance(120)                                         # the domain's pass stopped
    st, d = domain_view(north.objects, wall())
    assert d["silent"] and d["age"] == 120


def test_one_torn_object_of_one_cluster_freezes_neither_the_view_nor_the_directory():
    """М10's seventh review, part 2, reproduced: a snapshot shard or a heartbeat that does not parse raised
    `JSONDecodeError` out of the read view's pass — every cluster's time froze, `/api/cameras` and
    `DomainDirectory.where` failed — and the console's loop swallowed it with `except Exception: pass`. The torn object
    is that object's: skipped and counted once (`federation.MEMBER_OBJECTS`); a shard nobody can read makes its
    cluster's copy as old as can be; the cluster's other workers, and the other cluster, are read; a status entry whose
    numbers are words is that entry's; and a step of the console's loop that raises is said in the log, once."""
    import logging
    from w2cplatform.domain.federation import MEMBER_OBJECTS
    wall = Clock(10_000.0); fed, links = _four_workers(wall)
    north, south = fed.clusters["north"], fed.clusters["south"]
    snapshot(south, {151: ("w-0", "srv-9")}, ts=wall())
    snapshot(north, {7: ("w-0", "srv-1")}, ts=wall())
    north.objects.put("vms/snapshot/w-9", b'{"ts": 9999, "cameras": [')             # half a write
    north.objects.put("vms/heartbeats/w-1", b'{"worker": "w-1", "ts": ')
    south.objects.put("vms/heartbeats/w-5", json.dumps({"worker": "w-5", "ts": wall(), "server": "srv-9",
                                                        "status": [{"id": "x", "revision": "two"}]}).encode())
    before = MEMBER_OBJECTS.counts.get("north", 0)
    view = ReadView(fed, lost_after=45, wall=wall)
    for _ in range(2):
        wall.advance(5); view.refresh()
    page = view.list(size=500)
    assert page["complete"] and view.passes == 2
    assert {r["worker"] for r in page["rows"] if r["cluster"] == "north"} == {"w-0", "w-2"}       # the torn one alone is gone
    assert view.list(cluster="south")["total"] == 50                                             # the entry of words: that entry's
    assert MEMBER_OBJECTS.counts.get("north", 0) == before + 2                                   # once each, not once per pass
    d = DomainDirectory(fed, wall=wall)
    assert d.where("151").cluster == "south" and d.ages()["north"] == wall()                     # the copy says it is broken

    console, ran, said = Console(d, view, None), [], []

    class Catch(logging.Handler):
        def emit(self, record):
            said.append(record.getMessage())
    h = Catch(); logging.getLogger("domain.console").addHandler(h)
    try:
        for _ in range(2):
            console._steps(("a broken step", lambda: json.loads("{")), ("the next step", lambda: ran.append(1)))
    finally:
        logging.getLogger("domain.console").removeHandler(h)
    assert ran == [1, 1] and len([m for m in said if "a broken step failed" in m]) == 1 and console.refresh_failures == 2
