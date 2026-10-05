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

from w2cplatform.sealing import PREFIX, Sealed, Sealer, is_sealed, kid_of, new_key_file, open_row, seal_items, seal_stored
from w2cplatform.spec import Refused
from vms.config import SPEC
from vms.console import serve
from vms.controller import VmsController
from vms.worker import FakeActuator, VmsWorker
from tests.conftest import Box


def _key(*kids):
    path = os.path.join(tempfile.mkdtemp(prefix="key-"), "platform.key")
    new_key_file(path, kids[0])
    # its owner and its group, the clients of the secrets (`w2c-secrets`, the owner's decision of 4 October) — whatever
    # the umask; the group is the directory's
    assert oct(os.stat(path).st_mode & 0o777) == "0o640"
    assert os.stat(path).st_gid == os.stat(os.path.dirname(path)).st_gid
    for kid in kids[1:]:                                              # rotation: a new line ON TOP
        lines = open(path).read()
        new_key_file(path + ".new", kid)
        open(path, "w").write(open(path + ".new").read() + lines)
    return path


def test_a_value_is_sealed_with_the_current_key_and_opens_by_the_kid_it_names():
    old = _key("k1")
    s1 = Sealer.from_file(old)
    row = "vms/cameras/1"
    sealed = s1.seal("cred_secret", "hunter2", row)
    assert sealed.startswith(PREFIX + "k1:") and "hunter2" not in sealed and s1.seal("cred_secret", sealed, row) == sealed   # never twice
    assert s1.open("cred_secret", sealed, row) == "hunter2" and s1.open("cred_secret", "plain", row) == "plain"         # a row from before the key
    for bad, why in ((lambda: s1.open("access_secret", sealed, row), "another field"),
                     (lambda: s1.open("cred_secret", sealed[:-4] + "AAAA", row), "altered")):
        try:
            bad(); raise AssertionError(f"opened although {why}")
        except Sealed:
            pass

    both = _key("k1", "k2")                                           # k2 on top: current; k1 still opens
    s2 = Sealer.from_file(both)
    assert s2.current == "k2" and s2.seal("cred_secret", "x", row).startswith(PREFIX + "k2:")
    try:
        s2.open("cred_secret", sealed, row); raise AssertionError("a key the ring does not hold opened a value")
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
    w = VmsWorker("w-1", box.vars, box.objects, act, clock=box.clock, wall=box.wall, resource_root=box.archive, env={"SECRETS_KEY": key})
    w.reconcile_once()
    assert act.last["cred_secret"] == secret                          # the pipeline gets the password…
    assert is_sealed(next(r for r in w.rows if r["id"] == 1)["cred_secret"])                 # …the worker's rows keep it sealed

    said = []
    h = logging.Handler(); h.emit = lambda r: said.append(r.getMessage())
    logging.getLogger("vmsworker").addHandler(h)
    try:
        box2_act = Recording()
        nokey = VmsWorker("w-1", box.vars, box.objects, box2_act, clock=box.clock, wall=box.wall, resource_root=box.archive, env={})
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
        assert seal_items(None, {"cred_secret": "x", "name": "gate"}, "vms/cameras/1") == {"cred_secret": "x", "name": "gate"}
        seal_items(None, {"cred_secret": "y"}, "vms/cameras/2")
        assert sum("stored in the CLEAR" in m for m in said) == 1
        assert open_row(None, {"cred_secret": "plain"}, "vms/cameras/1") == {"cred_secret": "plain"}
        try:
            open_row(None, {"cred_secret": PREFIX + "k1:a:b"}, "vms/cameras/1"); raise AssertionError("opened without a key")
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
    """…and the platform's root is not a store (the owner's layout, 4 October): `/etc/w2c/secrets` is a link into
    `/data/platform/etc`, under `PLATFORM_DIR` and beside its stores, never in one of them (`platform_stores`)."""
    from w2cplatform.sealing import platform_stores
    store = tempfile.mkdtemp(prefix="platform-")
    try:
        new_key_file(os.path.join(store, "secrets.key"), store=store)
        raise AssertionError("a key beside the rows it protects protects nothing")
    except ValueError as e:
        assert "inside the store" in str(e)
    stores = platform_stores({"PLATFORM_DIR": store})
    assert stores == [os.path.join(store, d) for d in ("config", "objects", "configstore")]
    for inside in stores:
        os.makedirs(inside, exist_ok=True)
        try:
            new_key_file(os.path.join(inside, "platform.key"), store=stores)
            raise AssertionError(f"a key in {inside} is copied with every copy of it")
        except ValueError as e:
            assert "inside the store" in str(e)
    os.makedirs(os.path.join(store, "etc", "secrets"))
    new_key_file(os.path.join(store, "etc", "secrets", "platform.key"), store=stores)   # the layout's place for it
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
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, resource_root=box.archive, env={})
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


def test_a_secret_sent_back_as_its_mask_is_refused_and_the_one_kept_stays():
    """The thirteenth round (the product's guard): every reply shows a secret as `***` (`mask_secrets`), and a page that
    put the mask into the field on an edit and saved stored `***` as the camera's password — the camera stopped and
    nothing said why. The mask is refused at the door, in words, on a create, an edit and a volume's key; the secret
    kept stays as it was; a field left out keeps it."""
    from vms import volumes
    from w2cplatform.secrets import SECRET_MASK
    key = _key("k1")
    box = Box()
    con = _console_with_key(box, key)
    con.create_camera({"name": "a", "source": "driverpack://file/a.mp4", "cred_secret": "Hunter2"})
    kept = box.vars.get("vms/cameras/1")[0]["cred_secret"]
    for write in (lambda: con.update(1, {"cred_secret": SECRET_MASK}),
                  lambda: con.create_camera({"name": "b", "source": "driverpack://file/b.mp4", "cred_secret": SECRET_MASK}),
                  lambda: volumes.write(box.vars, {"name": "s3", "kind": "network", "url": "s3://archive.example/b",
                                                   "access_secret": SECRET_MASK, "quota_bytes": 10 ** 12})):
        try:
            write()
            raise AssertionError("a secret's mask was taken as the secret")
        except Refused as e:
            assert "sent as its mask" in str(e) and "leave the field out" in str(e), str(e)
    assert box.vars.get("vms/cameras/1")[0]["cred_secret"] == kept and box.vars.get("rec/volumes/s3")[0] is None
    con.update(1, {"name": "a, renamed"})                                    # the field left out: the secret stays
    assert box.vars.get("vms/cameras/1")[0]["cred_secret"] == kept


def _refused(write, *words):
    try:
        write()
    except Refused as e:
        assert all(w in str(e) for w in words), str(e)
        return str(e)
    raise AssertionError(f"taken: {words}")


def test_every_mask_a_page_draws_is_refused_and_a_password_with_stars_in_it_is_not():
    """The product's rule (the thirteenth round): `***` is what this console's replies show; a page or a client of its
    own draws `•••`, `●●●` or `＊＊＊` — or more of one of them. Each is refused in a camera's `cred_secret` on a create
    and an edit and in a volume's `access_secret`; a password that has stars in it is a password."""
    from vms import volumes
    from w2cplatform.spec import is_mask
    box = Box()
    con = _console_with_key(box, _key("k1"))
    con.create_camera({"name": "a", "source": "driverpack://file/a.mp4", "cred_secret": "Hunter2"})
    kept = box.vars.get("vms/cameras/1")[0]["cred_secret"]
    masks = ("***", "•••", "●●●", "＊＊＊", "******", "••••••••", " *** ")
    for m in masks:
        assert is_mask(m), m
        _refused(lambda: con.update(1, {"cred_secret": m}), "sent as its mask", "leave the field out")
        _refused(lambda: con.create_camera({"name": "b", "source": "driverpack://file/b.mp4", "cred_secret": m}),
                 "sent as its mask")
        _refused(lambda: volumes.write(box.vars, {"name": "s3", "kind": "network", "url": "s3://archive.example/b",
                                                  "access_secret": m, "quota_bytes": 10 ** 12}), "sent as its mask")
    assert box.vars.get("vms/cameras/1")[0]["cred_secret"] == kept and box.vars.get("rec/volumes/s3")[0] is None
    for word in ("a***", "**", "*•*", "pass●●●word"):
        assert not is_mask(word), word
    con.update(1, {"cred_secret": "a***"})
    assert box.vars.get("vms/cameras/1")[0]["cred_secret"] != kept


def test_a_secret_sent_empty_on_an_edit_keeps_the_stored_one_and_an_address_changed_without_one_is_refused():
    """The product's rule (the thirteenth round), one YAML key in both: `cred_secret: {bound_to: [source]}`. A page whose
    password field was typed in and cleared sends `""` (or null) — that kept nothing and wiped the camera's password; it
    keeps the stored one now. The address changed on an edit and no new password came: the stored one would go to
    whatever host the new address names — refused, in words that do not repeat the address. A new password with the new
    address is taken; a camera that had none has nothing to carry."""
    key = _key("k1")
    sealer = Sealer.from_file(key)
    box = Box()
    con = _console_with_key(box, key)
    con.create_camera({"name": "a", "source": "driverpack://file/a.mp4", "cred_secret": "Hunter2"})
    opened = lambda: sealer.open("cred_secret", box.vars.get("vms/cameras/1")[0]["cred_secret"], "vms/cameras/1")
    for empty in ("", None):
        con.update(1, {"name": "a", "source": "driverpack://file/a.mp4", "cred_secret": empty})   # the whole form, the same address
        assert opened() == "Hunter2", empty
    rev = box.vars.get("vms/cameras/1")[0]["revision"]
    for sent in ({}, {"cred_secret": ""}, {"cred_secret": None}):
        why = _refused(lambda: con.update(1, {"source": "driverpack://file/elsewhere.mp4", **sent}),
                       "cred_secret", "source", "no new cred_secret came", "send the one for the new address")
        assert "elsewhere" not in why
    assert box.vars.get("vms/cameras/1")[0]["revision"] == rev and opened() == "Hunter2"     # nothing written
    con.update(1, {"source": "driverpack://file/elsewhere.mp4", "cred_secret": "Hunter3"})
    assert opened() == "Hunter3"
    con.create_camera({"name": "b", "source": "driverpack://file/b.mp4"})                    # no password: nothing to carry
    con.update(2, {"source": "driverpack://file/b2.mp4"})
    assert box.vars.get("vms/cameras/2")[0]["source"] == "driverpack://file/b2.mp4"


def test_a_volumes_key_not_sent_is_kept_and_a_new_address_needs_a_new_one():
    """The same rule for a volume (`volumes.BOUND_TO`: `access_secret` to its `url`). A write over a declared volume is
    the whole declaration — and the key left out (or sent empty, or null) wiped the archive's key. It is kept now, as
    stored; a mask is refused; another url without a new key is refused; another url with one takes it. A volume
    turned into a card is another address too, and refused the same way (the platform's table since the boundary's
    step 6: it dropped the key, by a rule of the subsystem's own); declared again as a card, it has no key."""
    from vms import volumes
    key = _key("k1")
    sealer = Sealer.from_file(key)
    box = Box()
    vol = {"name": "s3", "kind": "network", "url": "s3://archive.example/bucket", "quota_bytes": 10 ** 12}
    volumes.write(box.vars, {**vol, "access_key": "AKIA", "access_secret": "xyz"}, sealer=sealer)
    opened = lambda: sealer.open("access_secret", box.vars.get("rec/volumes/s3")[0]["access_secret"], volumes.key("s3"))
    for sent in ({}, {"access_secret": ""}, {"access_secret": None}):
        volumes.write(box.vars, {**vol, "access_key": "AKIA", "quota_bytes": 2 * 10 ** 12, **sent}, sealer=sealer)
        assert opened() == "xyz" and box.vars.get("rec/volumes/s3")[0]["quota_bytes"] == str(2 * 10 ** 12), sent
    _refused(lambda: volumes.write(box.vars, {**vol, "access_secret": "***"}, sealer=sealer), "sent as its mask")
    for sent in ({}, {"access_secret": ""}):
        why = _refused(lambda: volumes.write(box.vars, {**vol, "url": "s3://other.example/bucket", **sent}, sealer=sealer),
                       "access_secret", "url", "send the one for the new address")
        assert "other.example" not in why
    assert box.vars.get("rec/volumes/s3")[0]["url"] == vol["url"] and opened() == "xyz"
    volumes.write(box.vars, {**vol, "url": "s3://other.example/bucket", "access_secret": "abc"}, sealer=sealer)
    assert opened() == "abc"
    card = {"name": "s3", "kind": "edge", "cam": "1", "server": "cam-1", "url": "/mnt/card", "quota_bytes": 10 ** 9}
    _refused(lambda: volumes.write(box.vars, card, sealer=sealer), "send the one for the new address")
    box.vars.delete(volumes.key("s3"))
    volumes.write(box.vars, card, sealer=sealer)
    assert not box.vars.get("rec/volumes/s3")[0].get("access_secret")


def test_bound_to_is_read_at_load_and_a_name_it_does_not_know_is_refused():
    """`bound_to` is parsed with the spec: the shipped camera's password is bound to its source; a name the unit has
    not, the secret itself, another secret, a field that is no secret, a value that is no name — refused at load."""
    from w2cplatform.spec import SubsystemSpec
    assert SPEC.fields["cred_secret"].bound_to == ("source",)

    def spec(fields):
        return SubsystemSpec.from_dict({"name": "t", "unit": {"id": "numeric", "rows": "units", "fields": fields},
                                        "placement": {"capacity": {"from": "capacity", "default": 4}}})
    assert spec({"url": {"type": "url"}, "x_secret": {"bound_to": "url"}}).fields["x_secret"].bound_to == ("url",)
    for bad, words in (({"x_secret": {"bound_to": ["url"]}}, "names no field"),
                       ({"x_secret": {"bound_to": ["x_secret"]}}, "names no field"),
                       ({"y_secret": {}, "x_secret": {"bound_to": ["y_secret"]}}, "names no field"),
                       ({"url": {"type": "url"}, "name": {"bound_to": ["url"]}}, "is no `*_secret`"),
                       ({"url": {"type": "url"}, "x_secret": {"bound_to": [1]}}, "a field name or a list"),
                       ({"url": {"type": "url"}, "x_secret": {"bound_to": []}}, "a field name or a list")):
        try:
            spec(bad)
            raise AssertionError(f"loaded: {bad}")
        except ValueError as e:
            assert words in str(e), (bad, str(e))


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
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, resource_root=box.archive, env={"SECRETS_KEY": key})
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
    sealed before that opens by the field alone ONLY for `seal_stored`, which seals it again, to its row — a holder
    asking for it is refused, or it would open in any row (the review's third pass, Н-M1's remainder)."""
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
    # sealed before the row was bound in: opens by the field alone only to be re-sealed, at the console's start
    old = sealer.seal("cred_secret", "Legacy", "")
    assert not sealer.bound("cred_secret", old, "vms/cameras/3") and sealer.open("cred_secret", old, "vms/cameras/3", fallback=True) == "Legacy"
    try:
        sealer.open("cred_secret", old, "vms/cameras/3")
        raise AssertionError("a value bound to no row opened in a holder")
    except Sealed:
        pass
    con.create_camera({"name": "c", "source": "driverpack://file/c.mp4", "cred_secret": "Legacy"})
    items3, idx3 = box.vars.get("vms/cameras/3")
    box.vars.put("vms/cameras/3", {**items3, "cred_secret": old}, cas=idx3)
    assert seal_stored(sealer, box.vars, ["vms/cameras/"]) == 1
    now = box.vars.get("vms/cameras/3")[0]["cred_secret"]
    assert now != old and sealer.bound("cred_secret", now, "vms/cameras/3") and sealer.open("cred_secret", now, "vms/cameras/3") == "Legacy"
    assert seal_stored(sealer, box.vars, ["vms/cameras/"]) == 0                                 # nothing left to do


def test_a_rotated_key_reseals_what_the_old_one_sealed_so_the_old_line_can_go():
    """The review's question 5. A new key on top of the file sealed only what was written after it; what was
    sealed before stayed under the old kid for ever, and the old line could never be removed. The console's start
    re-seals those under the current key — the revision standing still — once the holders have restarted with the
    new file; then `secrets status` is the log line, and the old line goes."""
    box = Box()
    k1 = _key("k1")
    con = _console_with_key(box, k1)
    con.create_camera({"name": "gate", "source": "driverpack://file/gate.mp4", "cred_secret": "Hunter2"})
    before, _ = box.vars.get("vms/cameras/1")
    assert kid_of(before["cred_secret"]) == "k1"
    k12 = _key("k1", "k2")                                             # the rotation: k2 on top, k1 still in the file
    lines = open(k12).read().splitlines()
    open(k12, "w").write("\n".join([lines[0], open(k1).read().strip()]) + "\n")   # the SAME k1 as before, under the new k2
    sealer = Sealer.from_file(k12)
    assert sealer.current == "k2" and sealer.open("cred_secret", before["cred_secret"], "vms/cameras/1") == "Hunter2"
    assert seal_stored(sealer, box.vars, ["vms/cameras/"]) == 1
    after, _ = box.vars.get("vms/cameras/1")
    assert kid_of(after["cred_secret"]) == "k2" and after["revision"] == before["revision"]
    assert sealer.open("cred_secret", after["cred_secret"], "vms/cameras/1") == "Hunter2"
    assert seal_stored(sealer, box.vars, ["vms/cameras/"]) == 0                       # once
    only_k2 = Sealer.from_file(_key("k2"))                                            # a file without the old line…
    try:
        only_k2.open("cred_secret", before["cred_secret"], "vms/cameras/1"); raise AssertionError("k1 opened without its key")
    except Sealed:
        pass
