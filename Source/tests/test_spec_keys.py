"""What the platform used to know by name and reads from the specs now (the boundary's step 4, ГРАНИЦА-ПЛАТФОРМЫ-И-
ПОДСИСТЕМЫ.md §2.4; the keys agreed with the product): `placement.capacity.default`, `slot`, `objects.rows`, and a url
field's `schemes`, `credentials` and `secret_in`. A test of the platform alone: its specs are made up here and in
`testdata/testsub.subsystem.yaml`, and no subsystem's package is imported."""
from __future__ import annotations

import os
import tempfile

from w2cplatform import catalog, runtime
from w2cplatform.secrets import NO_RULES, SecretRules, address_refusal, hide_in_url, is_credential_param
from w2cplatform.spec import Refused, SubsystemSpec

TESTDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata")
CAP = {"capacity": {"from": "capacity", "default": 4}}


def _spec(**over):
    d = {"name": "probe", "unit": {"rows": "items", "id": "name", "fields": {"name": {"type": "string", "required": True}}},
         "placement": dict(CAP)}
    d.update(over)
    return SubsystemSpec.from_dict(d)


def _refused(make, words: str) -> None:
    try:
        make()
    except ValueError as e:
        assert words in str(e), (words, str(e))
        return
    raise AssertionError(f"loaded, and should not have: {words}")


def test_a_spec_says_what_a_worker_that_said_nothing_carries_and_one_that_does_not_say_it_does_not_load():
    """`placement.capacity: {from, default}` — the default is required (the product's decision): the number a silent
    worker is counted at is the subsystem's to say. Left out, or written the old way (`fallback`), the spec does not
    load, and the words say what to write."""
    spec = _spec(placement={"capacity": {"from": "room", "default": 7}})
    assert (spec.capacity_from, spec.capacity_default) == ("room", 7)
    _refused(lambda: _spec(placement={}), "placement.capacity is {from: <heartbeat field>, default:")
    _refused(lambda: _spec(placement={"capacity": {"from": "capacity", "fallback": 7}}), "the default is the subsystem's")
    _refused(lambda: _spec(placement={"capacity": {"default": "many"}}), "a whole number of units")
    assert SubsystemSpec.load(os.path.join(TESTDATA, "testsub.subsystem.yaml")).capacity_default == 4


def test_a_slot_is_named_by_the_spec_and_a_worker_started_under_its_variable_takes_that_name():
    """`slot: {prefix, name_env}` — what a slot a worker makes is called, and the variable naming the one it is started
    under; left out, `w` and `WORKER_NAME`. An offer of another prefix than the slots' is refused at load."""
    spec = _spec(slot={"prefix": "k", "name_env": "KEEPER_NAME"})
    assert (spec.slot_prefix, spec.slot_name_env) == ("k", "KEEPER_NAME")
    assert (_spec().slot_prefix, _spec().slot_name_env) == ("w", "WORKER_NAME")
    assert runtime.slot({"KEEPER_NAME": "k-3"}, spec.slot_name_env, spec.slot_prefix) == "k-3"
    assert runtime.slot({"SLOT_INDEX": "2"}, spec.slot_name_env, spec.slot_prefix) == "k-2"
    _refused(lambda: _spec(slot={"prefix": "K-9"}), "slot.prefix")
    _refused(lambda: _spec(slot={"name_env": "lower"}), "slot.name_env")
    _refused(lambda: _spec(slot={"prefix": "k"}, placement={**CAP, "offers": "w"}), "an offer nobody's name fits")


def test_the_objects_that_are_rows_are_the_loaded_specs_and_nothing_else():
    """`objects: {rows: [...]}` under the subsystem's name, from the specs this process loaded (`catalog.object_rows`):
    the platform's constant naming one subsystem's family is gone. A pattern that is no key is refused at load."""
    root = tempfile.mkdtemp(prefix="specs-")
    with open(os.path.join(root, "probe.subsystem.yaml"), "w") as f:
        f.write("name: probe\nunit: {rows: items, id: name, fields: {name: {type: string}}}\n"
                "placement: {capacity: {from: capacity, default: 2}}\nobjects: {rows: [marks/*, seen/*]}\n")
    catalog.load_dir(root)
    assert {"probe/marks/*", "probe/seen/*"} <= set(catalog.object_rows())
    assert catalog.spec("probe").object_rows == ("marks/*", "seen/*")
    _refused(lambda: _spec(objects={"rows": ["/marks"]}), "objects.rows takes key patterns")
    _refused(lambda: _spec(objects={"rows": ["ma*/x"]}), "a whole segment '*'")
    _refused(lambda: _spec(objects={"door": ["x/*"]}), "`objects:` is {rows:")
    _refused(lambda: catalog.load_dir(tempfile.mkdtemp(prefix="empty-")), "no <sub>.subsystem.yaml there")
    _refused(lambda: catalog.spec("nobody"), "no subsystem 'nobody'")


# A url field the way a subsystem says how its addresses carry a login.
TARGET = {"type": "url", "required": True, "schemes": ["https", "sftp"],
          "credentials": {"login": "account_name", "secret": "pass_secret"},
          "secret_in": [{"param": ["pwd", "token*", "*key"]},
                        {"regex": r"(?:^|/)~(?P<login>[^:/]+):(?P<secret>[^/]+)", "in": "path"},
                        {"nested": "via"}]}


def _target_spec(target=None):
    return _spec(unit={"rows": "items", "id": "name", "fields": {
        "name": {"type": "string", "required": True}, "target": target or TARGET,
        "account_name": {"type": "string"}, "pass_secret": {"type": "string", "bound_to": ["target"]}}})


def test_how_an_address_carries_a_login_is_the_specs_and_the_platform_keeps_no_list_of_its_own():
    """The forms a credential takes in an address — the names of its parameters, a login spelt in the path, a parameter
    holding another address — were lists in `secrets.py`. They are a url field's `secret_in` now: with no rules the
    platform refuses only what RFC 3986 says is a login (an `@`, a port that is no number); with the field's rules it
    refuses and hides what they find, and the refusal names the field's `credentials`, never the value."""
    for plain in ("https://h/x?pwd=Hunter2", "https://h/~me:Hunter2/x", "https://h/x?via=https%3A%2F%2Fh2%2F%3Fpwd%3DHunter2"):
        assert address_refusal(plain, NO_RULES) is None and hide_in_url(plain, NO_RULES) == plain
    assert address_refusal("https://me:Hunter2@h/x", NO_RULES) and address_refusal("https://h:Hunter2/x", NO_RULES)
    rules = _target_spec().fields["target"].rules
    assert is_credential_param("pwd", rules) and is_credential_param("token_bucket", rules)     # `token*`: a word begins it
    assert is_credential_param("apiKey", rules) and not is_credential_param("keyframe", rules)  # `*key`: the last word ends it
    assert "pwd" in address_refusal("https://h/x?pwd=Hunter2", rules)
    assert "a login and a password in its path" in address_refusal("https://h/~me:Hunter2/x", rules)
    assert "'via'" in address_refusal("https://h/x?via=https%3A%2F%2Fh2%2F%3Fpwd%3DHunter2", rules)
    for bad in ("https://h/x?pwd=Hunter2", "https://h/~me:Hunter2/x", "https://h/x?via=https%3A%2F%2Fh2%2F%3Fpwd%3DHunter2"):
        assert "Hunter2" not in hide_in_url(bad, rules), bad
    spec = _target_spec()
    for bad in ("https://h/x?pwd=Hunter2", "https://h/~me:Hunter2/x"):
        try:
            spec.refuse({"target": bad})
            raise AssertionError(f"taken: {bad}")
        except Refused as e:
            assert "account_name" in str(e) and "pass_secret" in str(e) and "Hunter2" not in str(e), str(e)
    try:
        spec.refuse({"target": "ftp://h/x"})
        raise AssertionError("a scheme the field does not take was taken")
    except Refused as e:
        assert "https, sftp" in str(e) and "'ftp'" in str(e), str(e)
    spec.refuse({"target": "https://h/x?channel=1"})                                     # an ordinary address stands


def test_a_url_fields_words_are_read_at_load_and_anything_else_is_refused():
    """`schemes`, `credentials`, `secret_in` belong to a url field; `credentials` names a string field and a `*_secret`
    one of the row; `secret_in` is a list of the three kinds, a regex names what it finds and where it reads."""
    _refused(lambda: _spec(unit={"rows": "i", "fields": {"n": {"type": "string", "schemes": ["https"]}}}),
             "belong to a url field")
    _refused(lambda: _target_spec({**TARGET, "credentials": {"login": "pass_secret"}}), "credentials.login")
    _refused(lambda: _target_spec({**TARGET, "credentials": {"secret": "account_name"}}), "credentials.secret")
    _refused(lambda: _target_spec({**TARGET, "schemes": ["HTTPS"]}), "`schemes` is a list of schemes")
    for bad, words in (({"param": "pwd"}, "`param` is a list of names"), ({"param": ["*pwd*"]}, "a name, `name*` or `*name`"),
                       ({"regex": "x(?P<secret>.)"}, "`in: path` or `in: query`"),
                       ({"regex": "x(.)", "in": "path"}, "names what it finds"),
                       ({"regex": "(", "in": "query"}, "no regular expression"),
                       ({"nested": []}, "`nested` names the pair"), ({"other": 1}, "param, regex or nested"),
                       ({"param": ["a"], "nested": "b"}, "an entry of `secret_in` is one of")):
        _refused(lambda bad=bad: SecretRules.parse([bad], "field t"), words)
    _refused(lambda: SecretRules.parse({"param": ["a"]}, "field t"), "`secret_in` is a list")
