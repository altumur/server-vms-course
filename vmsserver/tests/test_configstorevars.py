"""`configstore://` — the handle (`w2cplatform/configstorevars.py`) and the daemon's doors (`w2cplatform/configstore.py`)
on real unix sockets and a real mutual-TLS door, with the state machine applied in the daemon's own process
(`LocalBackend`) instead of through raft. Needs no raft library, so it runs in every suite; what raft adds — a
group, joins, a leader killed — is `test_configstore.py`, where `pysyncobj` is installed.

Socket directories are short ones under /tmp: a unix socket's path is at most 104 bytes on macOS."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import socket
import socketserver
import ssl
import stat
import tempfile
import threading
import time
from contextlib import redirect_stdout

import pytest

from w2cplatform import configstore, tls
from w2cplatform.configstore import LocalBackend, StoreDaemon
from w2cplatform.configstorevars import StoreAmbiguous, StoreUnavailable
from w2cplatform.storemachine import Ambiguous, Rights, Unavailable
from w2cplatform.variables import Conflict, FileVariables, Forbidden, open_vars, store_url

HERE = os.path.dirname(os.path.abspath(__file__))
TLS = os.path.join(HERE, "tls")
RIGHTS = Rights.parse({"roles": {
    "vmsworker": {"read": ["vms/*"], "write": ["vms/epoch/*", "vms/slots/*"], "delete": ["vms/slots/*"]},
    "console": {"read": ["vms/*"], "write": ["vms/cameras/*"], "delete": ["vms/cameras/*"]},
}})


@contextlib.contextmanager
def refused(words: str):
    """A `ValueError` that says `words` — the operator reads the reason, so the reason is part of what is tested."""
    try:
        yield
    except ValueError as e:
        assert words in str(e), f"refused, but not for {words!r}: {e}"
        return
    raise AssertionError(f"not refused ({words})")


def short_dir() -> str:
    d = tempfile.mkdtemp(prefix="cs", dir="/tmp")
    assert len(os.path.join(d, "vmscontroller.sock")) < 104, d
    return d


def url(d: str, role: str = "admin", query: str = "") -> str:
    return f"configstore://{d}/{role}.sock" + (f"?{query}" if query else "")


class Daemon:
    """A daemon over the machine in this process: its sockets in a short directory, optionally its `-api` door."""

    def __init__(self, backend=None, api: bool = False, tls_dir: str = os.path.join(TLS, "srv-a"), d: str | None = None):
        self.dir = d or short_dir()
        self.backend = backend or LocalBackend("srv-a", 1000)
        self.d = StoreDaemon(self.backend, node_id="srv-a", sockets=self.dir, rights=RIGHTS,
                             api=("127.0.0.1", 0) if api else None, tls_dir=tls_dir if api else None)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.d.stop()
        shutil.rmtree(self.dir, ignore_errors=True)


def test_the_variables_contract_holds_on_configstore_through_a_daemon_socket():
    """Every clause of the contract suite against `configstore://<dir>/admin.sock`: the handle, HTTP over a unix
    socket, the daemon's door, the API and the machine — everything but raft, which `test_configstore.py` adds."""
    from tests import test_variables_contract as contract
    clauses = [(n, fn) for n, fn in vars(contract).items() if n.startswith("test_") and callable(fn)]
    assert len(clauses) >= 13, "the contract suite shrank"
    failed = []
    saved = os.environ.get("CONTRACT_URL")
    for name, fn in clauses:
        with Daemon() as dm:
            os.environ["CONTRACT_URL"] = url(dm.dir)
            try:
                fn()
            except Exception as e:                     # noqa: BLE001 — collected and reported by clause
                failed.append(f"{name}: {type(e).__name__}: {e}")
            finally:
                if saved is None:
                    os.environ.pop("CONTRACT_URL", None)
                else:
                    os.environ["CONTRACT_URL"] = saved
    assert not failed, "\n".join(failed)


def test_a_role_without_the_grant_is_refused_at_its_own_socket_before_anything_is_applied():
    """The socket is the identity: the worker's socket may write slots and epochs, not cameras. The 403 is the
    daemon's, before the command reaches the machine (on a raft member: before it is forwarded to the leader) — the
    machine's log index does not move. The handle's own `as_writer` check is a second one, not the one proved here:
    this handle has no writer at all."""
    with Daemon() as dm:
        w = open_vars(url(dm.dir, "vmsworker"))
        w.put("vms/slots/w-1", {"holder": "x"}, cas=0)
        applied = dm.backend.machine.applied
        with pytest.raises(Forbidden):
            w.put("vms/cameras/7", {"name": "gate"})
        with pytest.raises(Forbidden):
            w.delete("vms/cameras/7")
        with pytest.raises(Forbidden):
            open_vars(url(dm.dir, "console")).delete("vms/epoch/7")
        assert dm.backend.machine.applied == applied, "a refused request reached the log"
        assert open_vars(url(dm.dir)).get("vms/cameras/7") == (None, 0)


def test_each_role_has_its_own_socket_and_the_admin_socket_is_the_owners():
    """0660 for a role's socket (its group is the role's unit's: `socket_group`), 0600 for `admin.sock`; join and
    leave are refused on a role's socket, the rights are shown on the admin's only."""
    with Daemon() as dm:
        names = sorted(f for f in os.listdir(dm.dir) if f.endswith(".sock"))
        assert names == ["admin.sock", "console.sock", "vmsworker.sock"]
        mode = lambda f: stat.S_IMODE(os.stat(os.path.join(dm.dir, f)).st_mode)    # noqa: E731
        assert mode("admin.sock") == 0o600 and mode("vmsworker.sock") == 0o660
        assert configstore.socket_group("vmsworker") == "vms-vmsworker"
        assert configstore.socket_group("resource") == "w2c-resource"
        w = open_vars(url(dm.dir, "vmsworker"))
        with pytest.raises(Forbidden):
            w._call("POST", "/v1/join", {"id": "srv-x", "raft": "127.0.0.1:1"})
        with pytest.raises(Forbidden):
            w._call("GET", "/v1/rights")
        assert open_vars(url(dm.dir))._call("GET", "/v1/rights")["roles"]["vmsworker"]["write"] == \
            ["vms/epoch/*", "vms/slots/*"]


def test_a_refused_connection_is_tried_again_within_d():
    """A daemon restarting has no socket for a second or two. Nothing was sent, so the handle tries again — a write
    too — for up to D (`REFUSED_WAIT`, 5 s): the worker's lease step waits out the restart instead of losing a turn
    (the notes on the raft prototype, "what to change", point 2). Past its time it is `StoreUnavailable`."""
    d = short_dir()
    try:
        v = open_vars(url(d))
        holder = {}

        def start_late():
            time.sleep(1.0)
            holder["dm"] = Daemon(d=d)

        t = threading.Thread(target=start_late)
        t.start()
        t0 = time.monotonic()
        i = v.put("vms/epoch/7", {"epoch": 1}, cas=0)
        took = time.monotonic() - t0
        t.join()
        assert 0.9 <= took < 5.0, took
        assert v.get("vms/epoch/7") == ({"epoch": "1"}, i)
        holder["dm"].d.stop()
        quick = open_vars(url(d, query="timeout=1"))
        t0 = time.monotonic()
        with pytest.raises(StoreUnavailable):
            quick.get("vms/epoch/7")
        assert 0.9 <= time.monotonic() - t0 < 3.0
    finally:
        shutil.rmtree(d, ignore_errors=True)


class _Faulty(LocalBackend):
    def __init__(self, fault):
        super().__init__("srv-a", 1000)
        self.fault = fault

    def submit(self, cmd, deadline=None):
        if cmd["op"] in ("put", "delete"):
            raise self.fault
        return super().submit(cmd, deadline)


def test_not_done_and_outcome_unknown_reach_the_caller_as_their_own_kinds():
    """503 `unavailable` → `StoreUnavailable` (not done; repeat freely), 503 `ambiguous` → `StoreAmbiguous` (may yet
    land; read before writing again). Both are `OSError`s — "the store did not answer" to every caller in the
    platform, which keeps what it holds — and neither is ever `Conflict`, which would fence a worker."""
    with Daemon(_Faulty(Unavailable("no leader within 5 s"))) as dm:
        try:
            open_vars(url(dm.dir)).put("vms/epoch/7", {"epoch": 1})
            raise AssertionError("a write no leader took was answered")
        except StoreUnavailable as e:
            assert not isinstance(e, StoreAmbiguous), "a write that was not done was said to be maybe done"
    with Daemon(_Faulty(Ambiguous("the leader went"))) as dm:
        with pytest.raises(StoreAmbiguous):
            open_vars(url(dm.dir)).put("vms/epoch/7", {"epoch": 1})
    assert issubclass(StoreAmbiguous, StoreUnavailable) and issubclass(StoreUnavailable, OSError)


def test_an_answer_cut_off_by_a_dying_daemon_is_not_an_answer():
    """Found by the prototype's measurement at the fifteenth leader kill: the daemon sent its headers and died before
    the body, and `http.client.IncompleteRead` — an `HTTPException`, not an `OSError` — flew out of the handle and out
    of `renew_slot`. Whatever a daemon does while dying, the handle says «the store did not answer»: a cut-off body,
    a body that is not JSON, a connection closed before any answer. For a read `StoreUnavailable`; for a write,
    which was sent, `StoreAmbiguous`. Never `ValueError`, which reads as «not a key»."""
    d = short_dir()

    class Dying(socketserver.StreamRequestHandler):
        def handle(self):
            line = self.rfile.readline().decode()
            while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                pass
            if "cut" in line:
                self.wfile.write(b'HTTP/1.1 200 OK\r\nContent-Length: 27\r\n\r\n{"items"')
            elif "garbage" in line:
                self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\n<html")
            # else: not even a status line

    srv = socketserver.ThreadingUnixStreamServer(os.path.join(d, "admin.sock"), Dying)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        v = open_vars(url(d, query="timeout=2"))
        for key in ("vms/cut/1", "vms/garbage/1", "vms/silent/1"):
            with pytest.raises(StoreUnavailable):
                v.get(key)
        with pytest.raises(StoreUnavailable):
            v.list("vms/cut/")
        with pytest.raises(StoreAmbiguous):
            v.put("vms/silent/1", {"x": "1"})
    finally:
        srv.shutdown()
        srv.server_close()
        shutil.rmtree(d, ignore_errors=True)


# -- the -api door: mutual TLS ------------------------------------------------------------------------
def _dial(api_url: str, ctx: ssl.SSLContext, name: str, method: str, route: str, body: bytes = b"{}"):
    import http.client
    host, port = api_url.rsplit(":", 1)
    s = ctx.wrap_socket(socket.create_connection((host, int(port)), timeout=5), server_hostname=name)
    conn = http.client.HTTPConnection(host, int(port), timeout=5)
    conn.sock = s
    conn.request(method, route, body=body, headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    return r.status, json.loads(r.read() or b"{}")


def test_the_api_door_refuses_a_join_without_a_certificate_and_with_another_roles_certificate():
    """A daemon that accepts `POST /v1/join` from anybody hands the cluster's store to anybody. Without a client
    certificate the handshake itself fails; with a certificate of the installation's CA for another role (a
    recorder's, `urn:w2c:role:recworker`) the door answers 403 before it reads the request; a daemon's certificate
    (`configstore.<server>`, `urn:w2c:role:configstore`) gets through — here to a store that is no group, 503."""
    with Daemon(api=True) as dm:
        api = dm.d.api_url
        bare = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        bare.load_verify_locations(os.path.join(TLS, "ca.pem"))
        join = json.dumps({"id": "srv-x", "raft": "127.0.0.1:1", "api": ""}).encode()
        with pytest.raises((ssl.SSLError, ConnectionError, OSError)):
            _dial(api, bare, "srv-a", "POST", "/v1/join", join)
        code, said = _dial(api, tls.client_context(os.path.join(TLS, "srv-a"), "recworker"), "srv-a", "POST",
                           "/v1/join", join)
        assert (code, said["kind"]) == (403, "forbidden") and "recworker" in said["error"]
        code, said = _dial(api, tls.client_context(os.path.join(TLS, "srv-b")), "srv-a", "POST", "/v1/join", join)
        assert code == 503, said
        code, said = _dial(api, tls.client_context(os.path.join(TLS, "srv-b")), "srv-a", "GET", "/v1/status")
        assert code == 200 and said["id"] == "srv-a"


def test_a_daemon_dialling_another_checks_the_name_and_the_role_of_the_one_that_answers():
    """The client side of the same door: the answering certificate must be the CA's, carry the SAN DNS of the server
    dialled (`srv-b@host:port` dials srv-b), and be a store daemon's — a recorder's certificate for the right server
    is not the store."""
    with Daemon(api=True) as dm:
        assert configstore.peer_call(f"srv-a@{dm.d.api_url}", os.path.join(TLS, "srv-b"), "GET", "/v1/status")["id"] \
            == "srv-a"
        with pytest.raises(ssl.SSLCertVerificationError):
            configstore.peer_call(f"srv-c@{dm.d.api_url}", os.path.join(TLS, "srv-b"), "GET", "/v1/status")
    rogue_dir = short_dir()
    try:
        for f in ("ca.pem",):
            shutil.copy(os.path.join(TLS, "srv-a", f), rogue_dir)
        shutil.copy(os.path.join(TLS, "srv-a", "recworker.pem"), os.path.join(rogue_dir, "server.pem"))
        shutil.copy(os.path.join(TLS, "srv-a", "recworker.key"), os.path.join(rogue_dir, "server.key"))
        with Daemon(api=True, tls_dir=rogue_dir) as dm:
            with pytest.raises(PermissionError):
                configstore.peer_call(f"srv-a@{dm.d.api_url}", os.path.join(TLS, "srv-b"), "GET", "/v1/status")
    finally:
        shutil.rmtree(rogue_dir, ignore_errors=True)


def test_a_daemon_will_not_open_its_doors_unprotected():
    """The `-api` door is mutual TLS or nothing; a raft port off loopback without the secret is refused before the
    raft library is even asked."""
    with pytest.raises(ValueError):
        StoreDaemon(LocalBackend(), node_id="srv-a", api=("127.0.0.1", 0), tls_dir=None)
    with pytest.raises(ValueError):
        configstore.start_member("srv-a", short_dir(), "10.0.0.1:8301", bootstrap=True)


# -- a box becomes a cluster: the one-time import, backup and restore ------------------------------------
def _box() -> tuple[FileVariables, dict, int]:
    """A box's file store with rows at various versions: rewritten, deleted, created again."""
    box = FileVariables(tempfile.mkdtemp(), volatile=True)
    remembered = {}
    for n in range(5):
        remembered[f"vms/cameras/{n}"] = box.put(f"vms/cameras/{n}", {"name": f"cam {n}"}, cas=0)
    remembered["vms/epoch/1"] = box.put("vms/epoch/1", {"epoch": "7"}, cas=0)
    remembered["vms/cameras/2"] = box.put("vms/cameras/2", {"name": "renamed"}, cas=remembered["vms/cameras/2"])
    box.delete("vms/cameras/4", cas=remembered.pop("vms/cameras/4"))
    remembered["rec/recordings/1"] = box.put("rec/recordings/1", {"camera": "1", "days": "10"}, cas=0)
    counter = int(open(box.index_file).read())
    return box, remembered, counter


def test_a_box_imported_into_a_fresh_group_keeps_its_values_and_no_version_it_handed_out_matches():
    """`configstore import --from file://…`: the values arrive exactly as the box held them (epochs, generations and
    revisions live inside values); every new version is above the box's counter because the group was started with
    `-index-base` at least that counter — so a CAS with a version a process still remembers from the box conflicts
    instead of matching a different row; and the store goes on keeping the contract after the import."""
    box, remembered, counter = _box()
    with Daemon(LocalBackend("srv-a", index_base=counter)) as dm:
        admin = open_vars(url(dm.dir))
        got = configstore.import_rows("file://" + box.root, admin)
        assert got["rows"] == len(remembered) == 7 - 1
        for key in remembered:
            items, index = admin.get(key)
            assert items == box.get(key)[0], key
            assert index > counter, (key, index, counter)
        assert admin.get("vms/cameras/4") == (None, 0)
        for key, old in remembered.items():
            with pytest.raises(Conflict):
                admin.put(key, {"stale": "yes"}, cas=old)
        fresh = admin.put("vms/cameras/9", {"name": "new"}, cas=0)
        assert fresh > max(remembered.values()) and fresh > counter

        from tests import test_variables_contract as contract
        saved = os.environ.get("CONTRACT_URL")
        os.environ["CONTRACT_URL"] = url(dm.dir)
        failed = []
        try:
            for name, fn in vars(contract).items():
                if name.startswith("test_") and callable(fn):
                    try:
                        fn()
                    except Exception as e:             # noqa: BLE001
                        failed.append(f"{name}: {type(e).__name__}: {e}")
        finally:
            if saved is None:
                os.environ.pop("CONTRACT_URL", None)
            else:
                os.environ["CONTRACT_URL"] = saved
        assert not failed, "\n".join(failed)


def test_an_import_is_refused_whole_into_a_group_it_could_confuse():
    """Before the first write: a group whose base is below the box's counter (a remembered version could match a new
    row), a group that already holds rows, and a box with a row that does not read (dropped, it would read as
    absent — an absent epoch starts again from 1)."""
    box, _, counter = _box()
    with Daemon(LocalBackend("srv-a", index_base=counter - 1)) as dm:
        with refused("index-base"):
            configstore.import_rows("file://" + box.root, open_vars(url(dm.dir)))
        assert open_vars(url(dm.dir)).list("") == []
    with Daemon(LocalBackend("srv-a", index_base=counter)) as dm:
        open_vars(url(dm.dir)).put("vms/already", {"x": "1"})
        with refused("fresh"):
            configstore.import_rows("file://" + box.root, open_vars(url(dm.dir)))
    with open(box._file("vms/epoch/1"), "w") as f:
        f.write('{"items": {"epoch": "7"}, "ind')
    with Daemon(LocalBackend("srv-a", index_base=counter)) as dm:
        with refused("vms/epoch/1"):
            configstore.import_rows("file://" + box.root, open_vars(url(dm.dir)))
        assert open_vars(url(dm.dir)).list("") == []


def test_a_backup_restores_into_a_fresh_group_above_its_highest_version():
    """`configstore backup` / `restore`: every row and the highest version the group could have handed out; the
    restored group keeps the values and conflicts with every version from before."""
    with Daemon(LocalBackend("srv-a", 1000)) as a:
        h = open_vars(url(a.dir))
        old = {f"vms/cameras/{n}": h.put(f"vms/cameras/{n}", {"name": str(n)}, cas=0) for n in range(4)}
        out = io.StringIO()
        with redirect_stdout(out):
            configstore.main(["backup", "--socket", url(a.dir)])
        backup = json.loads(out.getvalue())
    assert backup["highest"] >= max(old.values())
    path = os.path.join(tempfile.mkdtemp(), "rows.json")
    with open(path, "w") as f:
        json.dump(backup, f)
    with Daemon(LocalBackend("srv-b", 10)) as low:
        with refused("index-base"):
            configstore.main(["restore", "--from", path, "--socket", url(low.dir)])
    with Daemon(LocalBackend("srv-b", backup["highest"])) as b:
        with redirect_stdout(io.StringIO()):
            configstore.main(["restore", "--from", path, "--socket", url(b.dir)])
        h = open_vars(url(b.dir))
        for key, index in old.items():
            assert h.get(key)[0] == {"name": key.rsplit("/", 1)[1]}
            with pytest.raises(Conflict):
                h.put(key, {"name": "stale"}, cas=index)


def test_the_operator_commands_speak_to_the_admin_socket():
    """`python3 -m w2cplatform.configstore status | rights [file]` — the product's `vmsctl configstore …`."""
    with Daemon() as dm:
        out = io.StringIO()
        with redirect_stdout(out):
            configstore.main(["status", "--socket", url(dm.dir)])
        assert json.loads(out.getvalue())["id"] == "srv-a"
        out = io.StringIO()
        with redirect_stdout(out):
            configstore.main(["rights", "--socket", url(dm.dir)])
        assert sorted(json.loads(out.getvalue())["roles"]) == ["console", "vmsworker"]


def test_a_process_reads_platform_store_first_and_config_url_by_its_old_name():
    """One function says which store a process opens (`variables.store_url`, product P7): the cluster's units set
    `PLATFORM_STORE`, a box's and the product's older ones `CONFIG_URL`."""
    both = {"PLATFORM_STORE": "configstore:///run/configstore/vmsworker.sock", "CONFIG_URL": "file:///data/c"}
    assert store_url(both) == both["PLATFORM_STORE"]
    assert store_url({"CONFIG_URL": "file:///data/c"}) == "file:///data/c"
    assert store_url({}, "file:///data/platform/config") == "file:///data/platform/config"
    assert store_url({"PLATFORM_STORE": "", "CONFIG_URL": "memory://x"}) == "memory://x"
    entry = os.path.join(os.path.dirname(HERE), "vms", "__main__.py")      # the process entry: the same function
    src = open(entry, encoding="utf-8").read()
    assert "store_url(os.environ" in src and 'os.environ.get("CONFIG_URL")' not in src
