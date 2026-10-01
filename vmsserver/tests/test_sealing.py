"""A secret is sealed in the store and opened only by the process that uses it (the product's authentication note,
section 3.6; the order agreed with it, feedback BP).

`secrets.py` kept a password off every screen and out of every copy that leaves the cluster; the ROW held it in
the clear. The key is not in the store — a file given to the console (which seals) and the holder (which opens) —
so a copy of the store, a backup, the controller and the domain's agent read ciphertext.
"""
import json
import logging
import os
import tempfile
import urllib.request

from w2cplatform.sealing import PREFIX, Sealed, Sealer, is_sealed, new_key_file, open_row, seal_items, seal_stored
from w2cplatform.spec import Refused
from vms.config import SPEC
from vms.console import serve
from vms.controller import VmsController
from vms.worker import FakeActuator, VmsWorker
from tests.conftest import Box


def _key(*kids):
    path = os.path.join(tempfile.mkdtemp(prefix="key-"), "vms.key")
    new_key_file(path, kids[0])
    assert oct(os.stat(path).st_mode & 0o777) == "0o600"             # readable by its owner only
    for kid in kids[1:]:                                              # rotation: a new line ON TOP
        lines = open(path).read()
        new_key_file(path + ".new", kid)
        open(path, "w").write(open(path + ".new").read() + lines)
    return path


def test_a_value_is_sealed_with_the_current_key_and_opens_by_the_kid_it_names():
    old = _key("k1")
    s1 = Sealer.from_file(old)
    sealed = s1.seal("cred_secret", "hunter2")
    assert sealed.startswith(PREFIX + "k1:") and "hunter2" not in sealed and s1.seal("cred_secret", sealed) == sealed   # never twice
    assert s1.open("cred_secret", sealed) == "hunter2" and s1.open("cred_secret", "plain") == "plain"                 # a row from before the key
    for bad, why in ((lambda: s1.open("access_secret", sealed), "another field"),
                     (lambda: s1.open("cred_secret", sealed[:-4] + "AAAA"), "altered")):
        try:
            bad(); raise AssertionError(f"opened although {why}")
        except Sealed:
            pass

    both = _key("k1", "k2")                                           # k2 on top: current; k1 still opens
    s2 = Sealer.from_file(both)
    assert s2.current == "k2" and s2.seal("cred_secret", "x").startswith(PREFIX + "k2:")
    try:
        s2.open("cred_secret", sealed); raise AssertionError("a key the ring does not hold opened a value")
    except Sealed as e:
        assert "k1" in str(e)                                         # a different k1: the two rings share only a name


def test_the_store_holds_ciphertext_and_the_holder_opens_it_for_the_pipeline_only():
    secret = "Hunter2-sealed"
    key = _key("k1")
    box = Box()
    os.environ["SECRETS_KEY"] = key
    try:
        con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    finally:
        del os.environ["SECRETS_KEY"]
    srv = serve(con, box.archive, port=0, wall=box.wall)
    try:
        body = json.dumps({"name": "gate", "source": "driverpack://file/gate.mp4", "cred_username": "admin", "cred_secret": secret}).encode()
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/cameras", data=body, method="POST",
                                                      headers={"Idempotency-Key": "s1"})).read()
    finally:
        srv.shutdown()
    row, _ = box.vars.get("vms/cameras/1")
    assert is_sealed(row["cred_secret"]) and row["cred_username"] == "admin"
    for path in box.vars.list(""):                                    # the whole store: not one plaintext copy
        items, _ = box.vars.get(path)
        assert not any(secret in str(v) for v in (items or {}).values()), path
    con.update(1, {"name": "front gate"})                              # an edit of another field
    assert box.vars.get("vms/cameras/1")[0]["cred_secret"] == row["cred_secret"]            # sealed once, not twice

    ctl = VmsController(box.vars, box.objects, wall=box.wall)
    ctl.assign("w-1", ["1"])

    class Recording(FakeActuator):
        def __call__(self, verb, cam):
            self.last = dict(cam)
            return super().__call__(verb, cam)

    act = Recording()
    w = VmsWorker("w-1", box.vars, box.objects, act, clock=box.clock, wall=box.wall, archive_root=box.archive, env={"SECRETS_KEY": key})
    w.reconcile_once()
    assert act.last["cred_secret"] == secret                          # the pipeline gets the password…
    assert is_sealed(next(r for r in w.rows if r["id"] == 1)["cred_secret"])                 # …the worker's rows keep it sealed

    said = []
    h = logging.Handler(); h.emit = lambda r: said.append(r.getMessage())
    logging.getLogger("vmsworker").addHandler(h)
    try:
        box2_act = Recording()
        nokey = VmsWorker("w-1", box.vars, box.objects, box2_act, clock=box.clock, wall=box.wall, archive_root=box.archive, env={})
        box.wall.advance(46)
        nokey.claim_slot(prefer="w-1"); nokey.reconcile_once()
        assert not hasattr(box2_act, "last")                           # a sealed password and no key: not started…
        assert any("sealed and this process has no key" in m for m in said)                  # …and the reason names the key
    finally:
        logging.getLogger("vmsworker").removeHandler(h)


def test_without_a_key_secrets_are_written_as_before_and_that_is_said():
    g = seal_items.__globals__                                         # the module the code USES (other tests re-import it)
    said = []
    h = logging.Handler(); h.emit = lambda r: said.append(r.getMessage())
    logging.getLogger("w2cplatform.sealing").addHandler(h)
    was, g["_said_clear"] = g["_said_clear"], False
    try:
        assert seal_items(None, {"cred_secret": "x", "name": "gate"}) == {"cred_secret": "x", "name": "gate"}
        seal_items(None, {"cred_secret": "y"})
        assert sum("stored in the CLEAR" in m for m in said) == 1
        assert open_row(None, {"cred_secret": "plain"}) == {"cred_secret": "plain"}
        try:
            open_row(None, {"cred_secret": PREFIX + "k1:a:b"}); raise AssertionError("opened without a key")
        except Sealed:
            pass
    finally:
        g["_said_clear"] = was
        logging.getLogger("w2cplatform.sealing").removeHandler(h)


# -- feedback CD --------------------------------------------------------------------------------------------
def test_rows_written_before_the_key_are_sealed_when_the_console_starts_with_one():
    """A camera nobody edits is never written again: its password would lie in the clear for years. The console,
    starting with a key, seals what is stored — the value only, in place: the revision does not move, so no
    pipeline restarts for a password it already has."""
    from w2cplatform.sealing import seal_stored
    box = Box()
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)   # no key yet
    con.create_camera({"name": "gate", "source": "driverpack://file/gate.mp4", "cred_secret": "Hunter2"})
    before, _ = box.vars.get("vms/cameras/1")
    assert before["cred_secret"] == "Hunter2"
    sealer = Sealer.from_file(_key("k1"))
    assert seal_stored(sealer, box.vars, ["vms/cameras/"]) == 1
    after, _ = box.vars.get("vms/cameras/1")
    assert is_sealed(after["cred_secret"]) and sealer.open("cred_secret", after["cred_secret"], "vms/cameras/1") == "Hunter2"   # bound to its row
    assert after["revision"] == before["revision"]                    # nothing the row means has changed
    assert seal_stored(sealer, box.vars, ["vms/cameras/"]) == 0       # once
    assert seal_stored(None, box.vars, ["vms/cameras/"]) == 0         # and nothing without a key


def test_the_key_is_never_made_inside_the_store_nor_over_another():
    store = tempfile.mkdtemp(prefix="platform-")
    try:
        new_key_file(os.path.join(store, "secrets.key"), store=store)
        raise AssertionError("a key beside the rows it protects protects nothing")
    except ValueError as e:
        assert "inside the store" in str(e)
    path = _key("k1")
    try:
        new_key_file(path, store=store)
        raise AssertionError("a key lost is every password sealed with it")
    except FileExistsError:
        pass


def test_a_camera_whose_password_cannot_be_opened_says_why_in_its_status():
    key = _key("k1")
    box = Box()
    os.environ["SECRETS_KEY"] = key
    try:
        con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    finally:
        del os.environ["SECRETS_KEY"]
    con.create_camera({"name": "gate", "source": "driverpack://file/gate.mp4", "cred_secret": "Hunter2"})
    VmsController(box.vars, box.objects, wall=box.wall).assign("w-1", ["1"])
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, archive_root=box.archive, env={})
    w.reconcile_once()
    st = next(s for s in w.status() if s["id"] == 1)
    assert st["phase"] != "running" and "SECRETS_KEY" in st["why"]


def test_a_volumes_secret_goes_into_the_store_sealed():
    from vms import volumes
    box = Box()
    sealer = Sealer.from_file(_key("k1"))
    volumes.write(box.vars, {"name": "s3", "kind": "network", "url": "s3://archive.example/bucket", "access_secret": "AKIA:xyz",
                             "quota_bytes": 10 ** 12},
                  sealer=sealer)
    row, _ = box.vars.get("rec/volumes/s3")
    assert is_sealed(row["access_secret"]) and sealer.open("access_secret", row["access_secret"], volumes.key("s3")) == "AKIA:xyz"


def _console_with_key(box, key):
    os.environ["SECRETS_KEY"] = key
    try:
        return VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    finally:
        del os.environ["SECRETS_KEY"]


def test_a_value_that_only_looks_sealed_stops_its_own_camera_and_is_refused_at_the_door():
    """The review's second pass, blocker 3: `enc:v1:x` under one camera ended the holder's pass for every camera
    after it. It is that camera's status now — and the door takes no value that looks sealed: a secret arrives
    in the clear and is sealed by the console."""
    key = _key("k1")
    box = Box()
    con = _console_with_key(box, key)
    con.create_camera({"name": "a", "source": "driverpack://file/a.mp4", "cred_secret": "Hunter2"})
    con.create_camera({"name": "b", "source": "driverpack://file/b.mp4", "cred_secret": "Hunter3"})
    items, idx = box.vars.get("vms/cameras/1")
    box.vars.put("vms/cameras/1", {**items, "cred_secret": "enc:v1:x"}, cas=idx)             # a copy that lost its tail, past the console
    VmsController(box.vars, box.objects, wall=box.wall).assign("w-1", ["1", "2"])
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, archive_root=box.archive, env={"SECRETS_KEY": key})
    w.reconcile_once()
    st = {s["id"]: s for s in w.status()}
    assert st[1]["phase"] != "running" and "looks sealed" in st[1]["why"]
    assert st[2]["phase"] == "running"                                                        # the camera after it started
    for pasted in ("enc:v1:x", box.vars.get("vms/cameras/2")[0]["cred_secret"]):
        try:
            con.create_camera({"name": "c", "source": "driverpack://file/c.mp4", "cred_secret": pasted})
            raise AssertionError("a sealed value was taken at the door")
        except Refused as e:
            assert "not taken" in str(e)
    try:
        con.update(2, {"cred_secret": "enc:v1:k1:aaaa:bbbb"})
        raise AssertionError("a sealed value was taken at the door")
    except Refused:
        pass


def test_a_ciphertext_opens_only_in_the_row_it_was_sealed_for():
    """The review's second pass, major: with the field alone as associated data, camera 7's sealed password pasted
    into camera 8's row opened for whoever reads camera 8. The row's key is in the ciphertext now; what was
    sealed before that opens by the field alone, once, and `seal_stored` seals it again, to its row."""
    key = _key("k1")
    box = Box()
    con = _console_with_key(box, key)
    con.create_camera({"name": "a", "source": "driverpack://file/a.mp4", "cred_secret": "Hunter2"})
    con.create_camera({"name": "b", "source": "driverpack://file/b.mp4", "cred_secret": "Other"})
    row1 = box.vars.get("vms/cameras/1")[0]
    items2, idx2 = box.vars.get("vms/cameras/2")
    box.vars.put("vms/cameras/2", {**items2, "cred_secret": row1["cred_secret"]}, cas=idx2)   # pasted past the console
    sealer = Sealer.from_file(key)
    assert open_row(sealer, {"id": 1, **row1}, "vms/cameras/1")["cred_secret"] == "Hunter2"
    try:
        open_row(sealer, {"id": 2, **box.vars.get("vms/cameras/2")[0]}, "vms/cameras/2")
        raise AssertionError("another row's ciphertext opened")
    except Sealed as e:
        assert "another row" in str(e)
    # sealed before the row was bound in: opens once by the field alone, and the console's start re-seals it
    old = sealer.seal("cred_secret", "Legacy")
    assert sealer.open("cred_secret", old, "vms/cameras/3") == "Legacy" and not sealer.bound("cred_secret", old, "vms/cameras/3")
    con.create_camera({"name": "c", "source": "driverpack://file/c.mp4", "cred_secret": "Legacy"})
    items3, idx3 = box.vars.get("vms/cameras/3")
    box.vars.put("vms/cameras/3", {**items3, "cred_secret": old}, cas=idx3)
    assert seal_stored(sealer, box.vars, ["vms/cameras/"]) == 1
    now = box.vars.get("vms/cameras/3")[0]["cred_secret"]
    assert now != old and sealer.bound("cred_secret", now, "vms/cameras/3") and sealer.open("cred_secret", now, "vms/cameras/3") == "Legacy"
    assert seal_stored(sealer, box.vars, ["vms/cameras/"]) == 0                                 # nothing left to do
