"""A secret is sealed in the store and opened only by the process that uses it (the product's authentication note,
section 3.6; the order agreed with it, feedback BP).

`secrets.py` kept a password off every screen and out of every copy that leaves the cluster; the ROW held it in
the clear. The key is not in the store — a file given to the console (which seals) and the holder (which opens) —
so a copy of the store, a backup, the controller and the domain's agent read ciphertext.

The platform's rules, on testsub2: a tally's `feed_secret` is the key to its `feed` (`bound_to`), and a shelf's
`feed_secret` the key to the shelf's `feed` — a table whose row holds a secret. How a subsystem's holder opens what was
sealed is the subsystem's own, and so are its tests.
"""
import logging
import os
import tempfile

from w2cplatform.sealing import PREFIX, Sealed, Sealer, is_sealed, kid_of, new_key_file, open_row, seal_items, seal_stored
from w2cplatform.spec import Refused
from tests.conftest import Box, Served, console_ctl, testsub2

TALLIES = "testsub2/tallies/"


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


def _console_with_key(box, key):
    """testsub2's console, started with the key ring `key` (`SECRETS_KEY`): it seals every `*_secret` on the way in."""
    os.environ["SECRETS_KEY"] = key
    try:
        return console_ctl(box, testsub2())
    finally:
        del os.environ["SECRETS_KEY"]


def _tally(name, **fields):
    """A tally about counter c1, read from a feed of its own (`feed` is unique)."""
    return {"name": name, "of": "c1", "feed": f"https://feed.example/{name}", **fields}


def _shelf(spec, vars_, body, sealer=None):
    from w2cplatform.tables import write_row
    return write_row(spec, "shelves", vars_, body, sealer=sealer)


def test_a_value_is_sealed_with_the_current_key_and_opens_by_the_kid_it_names():
    old = _key("k1")
    s1 = Sealer.from_file(old)
    row = TALLIES + "t1"
    sealed = s1.seal("feed_secret", "hunter2", row)
    assert sealed.startswith(PREFIX + "k1:") and "hunter2" not in sealed and s1.seal("feed_secret", sealed, row) == sealed   # never twice
    assert s1.open("feed_secret", sealed, row) == "hunter2" and s1.open("feed_secret", "plain", row) == "plain"         # a row from before the key
    for bad, why in ((lambda: s1.open("key_secret", sealed, row), "another field"),
                     (lambda: s1.open("feed_secret", sealed[:-4] + "AAAA", row), "altered")):
        try:
            bad(); raise AssertionError(f"opened although {why}")
        except Sealed:
            pass

    both = _key("k1", "k2")                                           # k2 on top: current; k1 still opens
    s2 = Sealer.from_file(both)
    assert s2.current == "k2" and s2.seal("feed_secret", "x", row).startswith(PREFIX + "k2:")
    try:
        s2.open("feed_secret", sealed, row); raise AssertionError("a key the ring does not hold opened a value")
    except Sealed as e:
        assert "k1" in str(e)                                         # a different k1: the two rings share only a name


def test_the_store_holds_ciphertext_and_an_edit_of_another_field_seals_nothing_again():
    """The console started with a key seals a secret on its way in, through its route as a page reaches it: the row
    holds ciphertext, the whole store not one plaintext copy, and an edit of another field leaves the ciphertext as it
    was — sealed once, not twice."""
    from w2cplatform.console import SpecConsole
    secret = "Hunter2-sealed"
    box = Box()
    con = _console_with_key(box, _key("k1"))
    with Served(SpecConsole(con, wall=box.wall)) as call:
        status, _ = call("POST", "/tallies", _tally("t1", feed_user="admin", feed_secret=secret), key="s1")
    assert status in (200, 201), status
    row, _ = box.vars.get(TALLIES + "t1")
    assert is_sealed(row["feed_secret"]) and row["feed_user"] == "admin"
    for path in box.vars.list(""):                                    # the whole store: not one plaintext copy
        items, _ = box.vars.get(path)
        assert not any(secret in str(v) for v in (items or {}).values()), path
    con.update("t1", {"mode": "loud"})                                # an edit of another field
    assert box.vars.get(TALLIES + "t1")[0]["feed_secret"] == row["feed_secret"]             # sealed once, not twice


def test_without_a_key_secrets_are_written_as_before_and_that_is_said():
    g = seal_items.__globals__                                         # the module the code USES (other tests re-import it)
    said = []
    h = logging.Handler(); h.emit = lambda r: said.append(r.getMessage())
    logging.getLogger("w2cplatform.sealing").addHandler(h)
    was, g["_said_clear"] = g["_said_clear"], False
    try:
        assert seal_items(None, {"feed_secret": "x", "name": "t1"}, TALLIES + "t1") == {"feed_secret": "x", "name": "t1"}
        seal_items(None, {"feed_secret": "y"}, TALLIES + "t2")
        assert sum("stored in the CLEAR" in m for m in said) == 1
        assert open_row(None, {"feed_secret": "plain"}, TALLIES + "t1") == {"feed_secret": "plain"}
        try:
            open_row(None, {"feed_secret": PREFIX + "k1:a:b"}, TALLIES + "t1"); raise AssertionError("opened without a key")
        except Sealed:
            pass
    finally:
        g["_said_clear"] = was
        logging.getLogger("w2cplatform.sealing").removeHandler(h)


# -- feedback CD --------------------------------------------------------------------------------------------
def test_rows_written_before_the_key_are_sealed_when_the_console_starts_with_one():
    """A unit nobody edits is never written again: its secret would lie in the clear for years. The console,
    starting with a key, seals what is stored — the value only, in place: the revision does not move, so no
    holder restarts for a secret it already has."""
    box = Box()
    con = console_ctl(box, testsub2())                                # no key yet
    con.create(_tally("a", feed_secret="Hunter2"))
    before, _ = box.vars.get(TALLIES + "a")
    assert before["feed_secret"] == "Hunter2"
    sealer = Sealer.from_file(_key("k1"))
    assert seal_stored(sealer, box.vars, [TALLIES]) == 1
    after, _ = box.vars.get(TALLIES + "a")
    assert is_sealed(after["feed_secret"]) and sealer.open("feed_secret", after["feed_secret"], TALLIES + "a") == "Hunter2"   # bound to its row
    assert after["revision"] == before["revision"]                    # nothing the row means has changed
    assert seal_stored(sealer, box.vars, [TALLIES]) == 0              # once
    assert seal_stored(None, box.vars, [TALLIES]) == 0                # and nothing without a key


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


def test_a_tables_secret_goes_into_the_store_sealed():
    spec = testsub2()
    box = Box()
    sealer = Sealer.from_file(_key("k1"))
    _shelf(spec, box.vars, {"name": "s1", "feed": "https://shelf.example/s1", "feed_secret": "AKIA:xyz"}, sealer=sealer)
    row, _ = box.vars.get("testsub2/shelves/s1")
    assert is_sealed(row["feed_secret"]) and sealer.open("feed_secret", row["feed_secret"], spec.sub.config("shelves", "s1")) == "AKIA:xyz"


def test_a_secret_sent_back_as_its_mask_is_refused_and_the_one_kept_stays():
    """The thirteenth round (the product's guard): every reply shows a secret as `***` (`mask_secrets`), and a page that
    put the mask into the field on an edit and saved stored `***` as the unit's secret — its holder could not use it,
    and nothing said why. The mask is refused at the door, in words, on a create, an edit and a table row's key; the
    secret kept stays as it was; a field left out keeps it."""
    from w2cplatform.secrets import SECRET_MASK
    spec = testsub2()
    box = Box()
    con = _console_with_key(box, _key("k1"))
    con.create(_tally("a", feed_secret="Hunter2"))
    kept = box.vars.get(TALLIES + "a")[0]["feed_secret"]
    for write in (lambda: con.update("a", {"feed_secret": SECRET_MASK}),
                  lambda: con.create(_tally("b", feed_secret=SECRET_MASK)),
                  lambda: _shelf(spec, box.vars, {"name": "s1", "feed": "https://shelf.example/s1", "feed_secret": SECRET_MASK})):
        try:
            write()
            raise AssertionError("a secret's mask was taken as the secret")
        except Refused as e:
            assert "sent as its mask" in str(e) and "leave the field out" in str(e), str(e)
    assert box.vars.get(TALLIES + "a")[0]["feed_secret"] == kept and box.vars.get("testsub2/shelves/s1")[0] is None
    con.update("a", {"mode": "loud"})                                        # the field left out: the secret stays
    assert box.vars.get(TALLIES + "a")[0]["feed_secret"] == kept


def _refused(write, *words):
    try:
        write()
    except Refused as e:
        assert all(w in str(e) for w in words), str(e)
        return str(e)
    raise AssertionError(f"taken: {words}")


def test_every_mask_a_page_draws_is_refused_and_a_password_with_stars_in_it_is_not():
    """The product's rule (the thirteenth round): `***` is what this console's replies show; a page or a client of its
    own draws `•••`, `●●●` or `＊＊＊` — or more of one of them. Each is refused in a tally's `feed_secret` on a create
    and an edit and in a table row's `feed_secret`; a password that has stars in it is a password."""
    from w2cplatform.spec import is_mask
    spec = testsub2()
    box = Box()
    con = _console_with_key(box, _key("k1"))
    con.create(_tally("a", feed_secret="Hunter2"))
    kept = box.vars.get(TALLIES + "a")[0]["feed_secret"]
    masks = ("***", "•••", "●●●", "＊＊＊", "******", "••••••••", " *** ")
    for m in masks:
        assert is_mask(m), m
        _refused(lambda: con.update("a", {"feed_secret": m}), "sent as its mask", "leave the field out")
        _refused(lambda: con.create(_tally("b", feed_secret=m)), "sent as its mask")
        _refused(lambda: _shelf(spec, box.vars, {"name": "s1", "feed": "https://shelf.example/s1", "feed_secret": m}),
                 "sent as its mask")
    assert box.vars.get(TALLIES + "a")[0]["feed_secret"] == kept and box.vars.get("testsub2/shelves/s1")[0] is None
    for word in ("a***", "**", "*•*", "pass●●●word"):
        assert not is_mask(word), word
    con.update("a", {"feed_secret": "a***"})
    assert box.vars.get(TALLIES + "a")[0]["feed_secret"] != kept


def test_a_secret_sent_empty_on_an_edit_keeps_the_stored_one_and_an_address_changed_without_one_is_refused():
    """The product's rule (the thirteenth round), one YAML key in both: `feed_secret: {bound_to: [feed]}`. A page whose
    secret field was typed in and cleared sends `""` (or null) — that kept nothing and wiped the unit's secret; it
    keeps the stored one now. The address changed on an edit and no new secret came: the stored one would go to
    whatever host the new address names — refused, in words that do not repeat the address. A new secret with the new
    address is taken; a unit that had none has nothing to carry."""
    key = _key("k1")
    sealer = Sealer.from_file(key)
    box = Box()
    con = _console_with_key(box, key)
    con.create(_tally("a", feed_secret="Hunter2"))
    opened = lambda: sealer.open("feed_secret", box.vars.get(TALLIES + "a")[0]["feed_secret"], TALLIES + "a")
    for empty in ("", None):
        con.update("a", _tally("a", feed_secret=empty))                # the whole form, the same address
        assert opened() == "Hunter2", empty
    rev = box.vars.get(TALLIES + "a")[0]["revision"]
    for sent in ({}, {"feed_secret": ""}, {"feed_secret": None}):
        why = _refused(lambda: con.update("a", {"feed": "https://elsewhere.example/a", **sent}),
                       "feed_secret", "feed", "no new feed_secret came", "send the one for the new address")
        assert "elsewhere" not in why
    assert box.vars.get(TALLIES + "a")[0]["revision"] == rev and opened() == "Hunter2"     # nothing written
    con.update("a", {"feed": "https://elsewhere.example/a", "feed_secret": "Hunter3"})
    assert opened() == "Hunter3"
    con.create(_tally("b"))                                                 # no secret: nothing to carry
    con.update("b", {"feed": "https://feed.example/b2"})
    assert box.vars.get(TALLIES + "b")[0]["feed"] == "https://feed.example/b2"


def test_a_tables_key_not_sent_is_kept_and_a_new_address_needs_a_new_one():
    """The same rule for a table's row (`feed_secret` bound to its `feed`). A write over a declared row is the whole
    declaration — and the key left out (or sent empty, or null) wiped the row's key. It is kept now, as stored; a mask
    is refused; another address without a new key is refused; another address with one takes it. The row declared again as
    another kind at another address is another address too, and refused the same way (the platform's table since the
    boundary's step 6); deleted and declared again, it has no key."""
    spec = testsub2()
    key = _key("k1")
    sealer = Sealer.from_file(key)
    box = Box()
    row_key = spec.sub.config("shelves", "s1")
    shelf = {"name": "s1", "feed": "https://shelf.example/s1", "zone": "z1"}
    _shelf(spec, box.vars, {**shelf, "feed_secret": "xyz"}, sealer=sealer)
    opened = lambda: sealer.open("feed_secret", box.vars.get(row_key)[0]["feed_secret"], row_key)
    for sent in ({}, {"feed_secret": ""}, {"feed_secret": None}):
        _shelf(spec, box.vars, {**shelf, "zone": "z2", **sent}, sealer=sealer)
        assert opened() == "xyz" and box.vars.get(row_key)[0]["zone"] == "z2", sent
    _refused(lambda: _shelf(spec, box.vars, {**shelf, "feed_secret": "***"}, sealer=sealer), "sent as its mask")
    for sent in ({}, {"feed_secret": ""}):
        why = _refused(lambda: _shelf(spec, box.vars, {**shelf, "feed": "https://other.example/s1", **sent}, sealer=sealer),
                       "feed_secret", "feed", "send the one for the new address")
        assert "other.example" not in why
    assert box.vars.get(row_key)[0]["feed"] == shelf["feed"] and opened() == "xyz"
    _shelf(spec, box.vars, {**shelf, "feed": "https://other.example/s1", "feed_secret": "abc"}, sealer=sealer)
    assert opened() == "abc"
    reserve = {"name": "s1", "kind": "reserve", "feed": "https://reserve.example/s1", "zone": "z9"}
    _refused(lambda: _shelf(spec, box.vars, reserve, sealer=sealer), "send the one for the new address")
    box.vars.delete(row_key)
    _shelf(spec, box.vars, reserve, sealer=sealer)
    assert not box.vars.get(row_key)[0].get("feed_secret")


def test_bound_to_is_read_at_load_and_a_name_it_does_not_know_is_refused():
    """`bound_to` is parsed with the spec: testsub2's `feed_secret` is bound to its feed; a name the unit has not, the
    secret itself, another secret, a field that is no secret, a value that is no name — refused at load."""
    from w2cplatform.spec import SubsystemSpec
    assert testsub2().fields["feed_secret"].bound_to == ("feed",)

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


def test_a_value_that_only_looks_sealed_does_not_open_and_is_refused_at_the_door():
    """The review's second pass, blocker 3: `enc:v1:x` under one unit ended the holder's pass for every unit after it.
    It does not open — a `Sealed` like any other, which a holder makes that unit's status — and the door takes no value
    that looks sealed: a secret arrives in the clear and is sealed by the console."""
    key = _key("k1")
    sealer = Sealer.from_file(key)
    box = Box()
    con = _console_with_key(box, key)
    con.create(_tally("a", feed_secret="Hunter2"))
    con.create(_tally("b", feed_secret="Hunter3"))
    for opening in (lambda: sealer.open("feed_secret", "enc:v1:x", TALLIES + "a"),
                    lambda: open_row(sealer, {"id": "a", "feed_secret": "enc:v1:x"}, TALLIES + "a")):
        try:
            opening()
            raise AssertionError("a value that only looks sealed opened")
        except Sealed as e:
            assert "looks sealed" in str(e)
    for pasted in ("enc:v1:x", box.vars.get(TALLIES + "b")[0]["feed_secret"]):
        try:
            con.create(_tally("c", feed_secret=pasted))
            raise AssertionError("a sealed value was taken at the door")
        except Refused as e:
            assert "not taken" in str(e)
    try:
        con.update("b", {"feed_secret": "enc:v1:k1:aaaa:bbbb"})
        raise AssertionError("a sealed value was taken at the door")
    except Refused:
        pass


def test_a_ciphertext_opens_only_in_the_row_it_was_sealed_for():
    """The review's second pass, major: with the field alone as associated data, unit 7's sealed secret pasted
    into unit 8's row opened for whoever reads unit 8. The row's key is in the ciphertext now; what was
    sealed before that opens by the field alone ONLY for `seal_stored`, which seals it again, to its row — a holder
    asking for it is refused, or it would open in any row (the review's third pass, Н-M1's remainder)."""
    key = _key("k1")
    box = Box()
    con = _console_with_key(box, key)
    con.create(_tally("a", feed_secret="Hunter2"))
    con.create(_tally("b", feed_secret="Other"))
    row1 = box.vars.get(TALLIES + "a")[0]
    items2, idx2 = box.vars.get(TALLIES + "b")
    box.vars.put(TALLIES + "b", {**items2, "feed_secret": row1["feed_secret"]}, cas=idx2)    # pasted past the console
    sealer = Sealer.from_file(key)
    assert open_row(sealer, {"id": "a", **row1}, TALLIES + "a")["feed_secret"] == "Hunter2"
    try:
        open_row(sealer, {"id": "b", **box.vars.get(TALLIES + "b")[0]}, TALLIES + "b")
        raise AssertionError("another row's ciphertext opened")
    except Sealed as e:
        assert "another row" in str(e)
    # sealed before the row was bound in: opens by the field alone only to be re-sealed, at the console's start
    old = sealer.seal("feed_secret", "Legacy", "")
    assert not sealer.bound("feed_secret", old, TALLIES + "c") and sealer.open("feed_secret", old, TALLIES + "c", fallback=True) == "Legacy"
    try:
        sealer.open("feed_secret", old, TALLIES + "c")
        raise AssertionError("a value bound to no row opened in a holder")
    except Sealed:
        pass
    con.create(_tally("c", feed_secret="Legacy"))
    items3, idx3 = box.vars.get(TALLIES + "c")
    box.vars.put(TALLIES + "c", {**items3, "feed_secret": old}, cas=idx3)
    assert seal_stored(sealer, box.vars, [TALLIES]) == 1
    now = box.vars.get(TALLIES + "c")[0]["feed_secret"]
    assert now != old and sealer.bound("feed_secret", now, TALLIES + "c") and sealer.open("feed_secret", now, TALLIES + "c") == "Legacy"
    assert seal_stored(sealer, box.vars, [TALLIES]) == 0                                       # nothing left to do


def test_a_rotated_key_reseals_what_the_old_one_sealed_so_the_old_line_can_go():
    """The review's question 5. A new key on top of the file sealed only what was written after it; what was
    sealed before stayed under the old kid for ever, and the old line could never be removed. The console's start
    re-seals those under the current key — the revision standing still — once the holders have restarted with the
    new file; then `secrets status` is the log line, and the old line goes."""
    box = Box()
    k1 = _key("k1")
    con = _console_with_key(box, k1)
    con.create(_tally("a", feed_secret="Hunter2"))
    before, _ = box.vars.get(TALLIES + "a")
    assert kid_of(before["feed_secret"]) == "k1"
    k12 = _key("k1", "k2")                                             # the rotation: k2 on top, k1 still in the file
    lines = open(k12).read().splitlines()
    open(k12, "w").write("\n".join([lines[0], open(k1).read().strip()]) + "\n")   # the SAME k1 as before, under the new k2
    sealer = Sealer.from_file(k12)
    assert sealer.current == "k2" and sealer.open("feed_secret", before["feed_secret"], TALLIES + "a") == "Hunter2"
    assert seal_stored(sealer, box.vars, [TALLIES]) == 1
    after, _ = box.vars.get(TALLIES + "a")
    assert kid_of(after["feed_secret"]) == "k2" and after["revision"] == before["revision"]
    assert sealer.open("feed_secret", after["feed_secret"], TALLIES + "a") == "Hunter2"
    assert seal_stored(sealer, box.vars, [TALLIES]) == 0                              # once
    only_k2 = Sealer.from_file(_key("k2"))                                            # a file without the old line…
    try:
        only_k2.open("feed_secret", before["feed_secret"], TALLIES + "a"); raise AssertionError("k1 opened without its key")
    except Sealed:
        pass


def test_a_secret_of_any_subsystem_is_in_one_row_of_the_store_and_in_no_reply():
    """The platform's rule on a spec that has nothing to do with the product (testsub2's `feed_secret`, bound to its
    address): a create's reply, its retry answered from the store (the Idempotency-Key copy), an update's reply and the
    listing hand back `***`; and after them the whole store holds the secret in ONE place — the unit's own row."""
    import json
    import urllib.request
    from w2cplatform.console import SpecConsole
    from w2cplatform.secrets import SECRET_MASK
    secret = "Hunter2-in-one-row-only"
    box = Box()
    ctl = console_ctl(box, testsub2())
    srv = SpecConsole(ctl, wall=box.wall).serve("127.0.0.1", 0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(method, path, body=None, key=None):
        req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Idempotency-Key": key} if key else {})
        return urllib.request.urlopen(req).read().decode()
    try:
        made = call("POST", "/tallies", {"name": "t1", "of": "c1", "feed": "https://feed.example/t1", "feed_user": "u",
                                         "feed_secret": secret}, key="k1")
        assert secret not in made and json.loads(made)["feed_secret"] == SECRET_MASK
        assert secret not in call("POST", "/tallies", {"name": "t1", "of": "c1", "feed": "https://feed.example/t1",
                                                       "feed_user": "u", "feed_secret": secret}, key="k1")   # the retry
        assert secret not in call("PUT", "/tallies/t1", {"feed_secret": secret + "-2"}, key="k2")
        assert secret not in call("GET", "/tallies")
    finally:
        srv.shutdown()
    assert ctl.unit("t1")["feed_secret"] == secret + "-2"
    for path in box.vars.list(""):
        items, _ = box.vars.get(path)
        for k, v in (items or {}).items():
            if secret in str(v):
                assert (path, k) == ("testsub2/tallies/t1", "feed_secret"), f"the secret is also stored at {path}[{k}]"
