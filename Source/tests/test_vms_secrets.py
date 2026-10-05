"""The VMS's half of sealing (`test_sealing.py` holds the platform's): the holder opens a camera's sealed password at
the last moment, for the pipeline only (`vms/worker.py`); a password it cannot open — no key, a value that only looks
sealed — is that camera's status and nobody else's; the shipped specs bind each secret to the address it is the key to.
"""
import json
import logging
import os
import urllib.request

from w2cplatform.sealing import is_sealed
from w2cplatform.spec import Refused
from vms.config import REC_SPEC, SPEC
from vms.console import serve
from vms.controller import VmsController
from vms.worker import FakeActuator, VmsWorker
from tests.test_sealing import _key
from tests.vmsconftest import Box


def _console_with_key(box, key):
    os.environ["SECRETS_KEY"] = key
    try:
        return VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    finally:
        del os.environ["SECRETS_KEY"]


def test_the_store_holds_ciphertext_and_the_holder_opens_it_for_the_pipeline_only():
    secret = "Hunter2-sealed"
    key = _key("k1")
    box = Box()
    os.environ["SECRETS_KEY"] = key
    try:
        con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    finally:
        del os.environ["SECRETS_KEY"]
    srv = serve(con, box.resource_root, port=0, wall=box.wall)
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
    w = VmsWorker("w-1", box.vars, box.objects, act, clock=box.clock, wall=box.wall, resource_root=box.resource_root, env={"SECRETS_KEY": key})
    w.reconcile_once()
    assert act.last["cred_secret"] == secret                          # the pipeline gets the password…
    assert is_sealed(next(r for r in w.rows if r["id"] == 1)["cred_secret"])                 # …the worker's rows keep it sealed

    said = []
    h = logging.Handler(); h.emit = lambda r: said.append(r.getMessage())
    logging.getLogger("vmsworker").addHandler(h)
    try:
        box2_act = Recording()
        nokey = VmsWorker("w-1", box.vars, box.objects, box2_act, clock=box.clock, wall=box.wall, resource_root=box.resource_root, env={})
        box.wall.advance(46)
        nokey.claim_slot(prefer="w-1"); nokey.reconcile_once()
        assert not hasattr(box2_act, "last")                           # a sealed password and no key: not started…
        assert any("sealed and this process has no key" in m for m in said)                  # …and the reason names the key
    finally:
        logging.getLogger("vmsworker").removeHandler(h)


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
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, resource_root=box.resource_root, env={})
    w.reconcile_once()
    st = next(s for s in w.status() if s["id"] == 1)
    assert st["phase"] != "running" and "SECRETS_KEY" in st["why"]


def test_the_shipped_secrets_are_bound_to_their_addresses():
    """`bound_to` in the shipped specs: a camera's password is the key to its source, a volume's `access_secret` to its
    url — the platform's rule for an address changed without a new secret applies to both (`test_sealing.py`)."""
    assert SPEC.fields["cred_secret"].bound_to == ("source",)
    assert REC_SPEC.table_specs["volumes"].fields["access_secret"].bound_to == ("url",)


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
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, resource_root=box.resource_root, env={"SECRETS_KEY": key})
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
