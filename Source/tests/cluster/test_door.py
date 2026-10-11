"""A door without a vote (ADR-0070 step 5; `w2cplatform/configstoredoor.py`): a store daemon on a fourth server that holds
no raft, in front of a group of three on mutual TLS — the product's `doormode_test.go`, on the course's store. The voters
are processes (`python3 -m w2cplatform.configstore`, as `test_drills.py` runs them), the door is in this process with
short periods (its row every half second, the group asked every half second) — the product's test does the same; the
drill of the door through the voters' power loss runs it as a process (`test_drills.py`).

What it proves: the door passes its processes' reads and writes on as their role, and the group holds them; what the role
may not do is refused at the door, and again at the voter, which asks the same rights file — no header widens a role,
neither on the door's socket nor on a voter's `-api` door with the door's certificate; a door's certificate never joins,
never reads the rights, never asks as the admin, never under another door's name; a voter does not start on a door's
certificate, nor a door on a voter's; the door learns the group from one seed, follows a leave and a join, and keeps
writing when its seed is killed; it is counted in `configstore_doors` and in no voter's count; and with every voter gone
it answers 503 `unavailable` with the reason, inside the caller's wait, and writes again when they come back."""
from __future__ import annotations

import json
import os
import shutil
import signal
import tempfile
import time

import pytest

from tests.cluster.test_drills import TLS, Daemon, _back, _group, _leader, _metric, _wait
from w2cplatform import configstore
from w2cplatform.configstore import HEADER_DOOR, HEADER_ROLE, _PeerConnection, have_library
from w2cplatform.configstoredoor import DoorDaemon
from w2cplatform.configstorevars import StoreUnavailable, unix_transport
from w2cplatform.storemachine import Rights
from w2cplatform.variables import Forbidden, open_vars

pytestmark = pytest.mark.skipif(not have_library(), reason="the raft library is not installed: pip install pysyncobj")

DOOR_TLS = os.path.join(TLS, "srv-d")                # w2c-ca.sh issue srv-d configstore-door: no raft.secret in it
RIGHTS = {"roles": {
    "testsub2worker": {"read": ["testsub2/*", "platform/epoch_floor"], "write": ["testsub2/*"],
                       "delete": ["testsub2/slots/*"]},
    "testsubworker": {"read": ["testsub/*"], "write": ["testsub/*"]},
}}


def _rights(root: str) -> str:
    path = os.path.join(root, "rights.json")
    with open(path, "w") as f:
        json.dump(RIGHTS, f)
    return path


def _door(root: str, seeds: list[str]) -> DoorDaemon:
    return DoorDaemon("srv-d", seeds, sockets=os.path.join(root, "srv-d.s"), rights=Rights.parse(RIGHTS),
                      tls_dir=DOOR_TLS, beat=0.5, follow=0.5)


def _vars(door: DoorDaemon, role: str = "testsub2worker", timeout: float = 3.0):
    return open_vars(f"configstore://{door.sockets}/{role}.sock?timeout={timeout:g}")


def _door_metric(door: DoorDaemon, name: str) -> float | None:
    for line in door.metrics_text().splitlines():
        if line.startswith(name + " "):
            return float(line.split()[-1])
    return None


def _says(kind, words: str, fn) -> None:
    """`fn()` raises `kind` saying `words` (the suite runs without pytest too: its shim's `raises` takes no `match`)."""
    try:
        fn()
    except kind as e:
        assert words in str(e), e
        return
    raise AssertionError(f"{kind.__name__} not raised")


def _at_voter(voter: Daemon, tls_dir: str, method: str, route: str, headers: dict, body: dict | None = None) -> tuple[int, dict]:
    """One request to a voter's `-api` door with the certificate in `tls_dir`, saying what `headers` say."""
    conn = _PeerConnection(voter.adv, tls_dir, 10.0)
    try:
        conn.request(method, route, body=None if body is None else json.dumps(body).encode(),
                     headers={"Content-Type": "application/json", **headers})
        r = conn.getresponse()
        return r.status, json.loads(r.read() or b"{}")
    finally:
        conn.close()


def test_a_door_passes_its_processes_requests_on_as_their_role_and_no_header_widens_one():
    root = tempfile.mkdtemp(prefix="door-")
    ds, door = [], None
    try:
        rights = _rights(root)
        # a voter does not start on a door's certificate, and a door does not on a voter's
        _says(ValueError, "a door's: it never votes", lambda: configstore.start_member(
            "srv-d", os.path.join(root, "v"), "127.0.0.1:1", group_size=3, bootstrap=True, tls_dir=DOOR_TLS))
        for who, tls_dir, words in (("srv-a", os.path.join(TLS, "srv-a"), "is a voter's: a door holds a door's"),
                                    ("srv-x", DOOR_TLS, "-id is 'srv-x'"), ("srv-d", None, "mutual TLS only")):
            _says(ValueError, words, lambda who=who, tls_dir=tls_dir: DoorDaemon(
                who, ["srv-b@127.0.0.1:1"], sockets=os.path.join(root, "x.s"), rights=Rights.parse(RIGHTS),
                tls_dir=tls_dir))
        ds = _group(root, rights)
        a, b, c = ds
        door = _door(root, [a.adv])                                            # one seed: the group is asked of it
        worker = _vars(door)
        worker.put("testsub2/counters/1", {"name": "via the door"}, cas=0)
        assert a.vars().get("testsub2/counters/1")[0] == {"name": "via the door"}
        assert worker.get("testsub2/counters/1")[0] == {"name": "via the door"}
        assert worker.list("testsub2/") == ["testsub2/counters/1"]
        answered = _door_metric(door, 'configstore_door_forwards_total{outcome="answered"}')
        with pytest.raises(Forbidden):                                         # refused at the door: nothing passed on
            worker.put("testsub/counters/1", {"name": "not its own"})
        assert _door_metric(door, 'configstore_door_forwards_total{outcome="answered"}') == answered
        # a process on the door's socket says another role: refused, whatever it says
        code, raw = unix_transport(os.path.join(door.sockets, "testsub2worker.sock"))(
            "POST", "/v1/write", json.dumps({"op": "put", "key": "testsub/x", "items": {}}).encode(),
            {"Content-Type": "application/json", HEADER_ROLE: "testsubworker"}, 5.0)
        assert code == 403 and "says who it is" in json.loads(raw)["error"], raw
        # …and so on a voter's own socket
        code, raw = unix_transport(a.admin)("GET", "/v1/status", None, {HEADER_DOOR: "srv-d"}, 5.0)
        assert code == 403, raw
        # the door's certificate at a voter's -api: the voter asks the same rights file, as the role the door names
        door_says = {HEADER_DOOR: "srv-d", HEADER_ROLE: "testsub2worker"}
        code, said = _at_voter(b, DOOR_TLS, "POST", "/v1/write", door_says,
                               {"op": "put", "key": "testsub/widened", "items": {"x": "1"}})
        assert code == 403 and "may not write testsub/widened" in said["error"], said
        code, said = _at_voter(b, DOOR_TLS, "POST", "/v1/write", {HEADER_DOOR: "srv-d", HEADER_ROLE: "admin"},
                               {"op": "put", "key": "testsub2/x", "items": {}})
        assert code == 403 and "asks as the admin" in said["error"], said
        code, said = _at_voter(b, DOOR_TLS, "POST", "/v1/write", {HEADER_DOOR: "srv-e"},
                               {"op": "put", "key": "platform/doors/configstore/srv-e", "items": {}})
        assert code == 403 and "its own door certificate" in said["error"], said
        code, said = _at_voter(b, DOOR_TLS, "POST", "/v1/write", {HEADER_DOOR: "srv-d"},       # as the door: its row only
                               {"op": "put", "key": "testsub2/x", "items": {}})
        assert code == 403, said
        code, said = _at_voter(b, DOOR_TLS, "POST", "/v1/join", {HEADER_DOOR: "srv-d"},
                               {"id": "srv-d", "raft": "127.0.0.1:1"})
        assert code == 403 and "not a door's to ask" in said["error"], said
        code, said = _at_voter(b, DOOR_TLS, "GET", "/v1/rights", {HEADER_DOOR: "srv-d"})
        assert code == 403, said
        code, said = _at_voter(b, DOOR_TLS, "GET", "/v1/status", {})                           # names no door
        assert code == 403 and "names no door" in said["error"], said
        code, said = _at_voter(b, os.path.join(TLS, "srv-a"), "GET", "/v1/status", {HEADER_DOOR: "srv-d"})
        assert code == 403 and "its own door certificate" in said["error"], said                # a voter is no door
        # the group as the voters say it — three, from one seed; the door in no voter's count, and counted as a door
        _wait("the door to know the three voters", lambda: len(_vars(door).status()["voters"]) == 3)
        s = _vars(door).status()
        assert s["state"] == "door" and s["leader_id"] == _leader(ds).name, s
        _wait("the door to reach three voters", lambda: _door_metric(door, "configstore_door_voters_reachable") == 3)
        _wait("a voter to count the door", lambda: _metric(a.admin, "configstore_doors") == 1)
        assert _metric(c.admin, "configstore_raft_voters") == 3
        assert all(m["id"] != "srv-d" for m in a.status()["members"])
        # the operator asks the group at a voter's admin.sock, not at a door's
        admin = open_vars(f"configstore://{door.sockets}/admin.sock?timeout=3")
        assert admin.status()["id"] == "srv-d"
        _says(Forbidden, "is a door", lambda: admin.get("testsub2/counters/1"))
    finally:
        if door is not None:
            door.stop()
        for d in ds:
            d.stop(signal.SIGKILL)
        shutil.rmtree(root, ignore_errors=True)


def test_a_door_follows_the_group_answers_503_with_no_voter_left_and_writes_again_when_they_come_back():
    root = tempfile.mkdtemp(prefix="door-")
    ds, door = [], None
    try:
        ds = _group(root, _rights(root))
        a, b, c = ds
        door = _door(root, [a.adv])
        worker = _vars(door)
        _wait("the door to know the three voters", lambda: len(worker.status()["voters"]) == 3)
        # a leave and a join reach the door through the voters' status
        assert a.vars()._call("POST", "/v1/leave", {"id": "srv-c"})
        c.stop()
        _wait("the door to follow the leave", lambda: sorted(worker.status()["voters"]) == ["srv-a", "srv-b"])
        c.wipe()
        c.start("-join", a.adv)
        _wait("the door to follow the join", lambda: sorted(worker.status()["voters"]) == ["srv-a", "srv-b", "srv-c"])
        # its seed killed: it writes on through the others
        a.stop(signal.SIGKILL)
        _wait("a write through the door after its seed was killed",
              lambda: worker.put("testsub2/counters/2", {"name": "after"}) is not None)
        # every voter gone: 503 unavailable, said inside the caller's wait — never a hang
        for d in ds:
            d.stop(signal.SIGKILL)
        quick = _vars(door, timeout=3.0)
        t0 = time.monotonic()
        _says(StoreUnavailable, "reached none of the group's voters",
              lambda: quick.put("testsub2/counters/3", {"name": "nobody"}))
        assert time.monotonic() - t0 < 3.0
        _says(StoreUnavailable, "reached none of the group's voters", lambda: quick.get("testsub2/counters/2"))
        assert _door_metric(door, 'configstore_door_forwards_total{outcome="unavailable"}') >= 2
        _wait("the door to count no voter", lambda: _door_metric(door, "configstore_door_voters_reachable") == 0)
        # the voters back from their journals: the door writes again, with the list it kept
        for d in ds:
            d.spawn()
        _back(ds)
        _wait("a write through the door after the voters came back",
              lambda: worker.put("testsub2/counters/3", {"name": "back"}) is not None)
        assert b.vars().get("testsub2/counters/2")[0] == {"name": "after"}
        _wait("the door to count three voters again", lambda: _door_metric(door, "configstore_door_voters_reachable") == 3)
    finally:
        if door is not None:
            door.stop()
        for d in ds:
            d.stop(signal.SIGKILL)
        shutil.rmtree(root, ignore_errors=True)


def test_a_door_is_started_as_a_door_and_its_certificate_is_its_own_kind():
    """The command line says what a door is not (the product's refusal), and `w2c-ca.sh` issues a door's certificate
    alone, as `server.pem`, with no raft secret in its bundle."""
    import subprocess
    import sys
    from tests.cluster.test_drills import SOURCE
    root = tempfile.mkdtemp(prefix="door-")
    try:
        rights = _rights(root)
        base = [sys.executable, "-m", "w2cplatform.configstore", "-door", "-id", "srv-d", "-voters", "srv-a@127.0.0.1:1",
                "-sockets", os.path.join(root, "s"), "-rights", rights]
        out = subprocess.run(base + ["-tls", DOOR_TLS, "-raft", "127.0.0.1:1", "-group-size", "3"], cwd=SOURCE,
                             capture_output=True, text=True)
        assert out.returncode == 2 and "-door holds no raft and is no member" in out.stderr, out.stderr
        out = subprocess.run(base + ["-tls", os.path.join(TLS, "srv-a")], cwd=SOURCE, capture_output=True, text=True)
        assert out.returncode == 1 and "is a voter's: a door holds a door's" in out.stderr, out.stderr
        ca = os.path.join(root, "ca")
        env = {**os.environ, "W2C_CA_DIR": ca}
        script = os.path.join(SOURCE, "deploy", "w2c-ca.sh")
        assert subprocess.run(["sh", script, "init"], env=env, capture_output=True).returncode == 0
        out = subprocess.run(["sh", script, "issue", "srv-e", "configstore-door", "testsub2worker"], env=env,
                             capture_output=True, text=True)
        assert out.returncode != 0 and "a door's certificate carries one role" in out.stderr, out.stderr
        out = subprocess.run(["sh", script, "issue", "srv-e", "configstore-door"], env=env, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        kit = os.path.join(ca, "srv-e")
        assert sorted(os.listdir(kit)) == ["ca.pem", "crl.pem", "server.key", "server.pem"]
        from w2cplatform import tls
        assert tls.own_roles(kit) == {"configstore-door"} and tls.own_server(kit) == "srv-e"
    finally:
        shutil.rmtree(root, ignore_errors=True)
