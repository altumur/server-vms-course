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

from w2cplatform.sealing import PREFIX, Sealed, Sealer, is_sealed, new_key_file, open_row, seal_items
from vms.archive import ArchiveResource
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
    srv = serve(con, ArchiveResource(box.spool, box.archive), port=0, wall=box.wall)
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
