"""What the platform used to know by name and reads from the specs now (the boundary's step 4, ГРАНИЦА-ПЛАТФОРМЫ-И-
ПОДСИСТЕМЫ.md §2.4; the keys agreed with the product): `placement.capacity.default`, `slot`, `objects.rows`, and a url
field's `schemes`, `credentials` and `secret_in` — and that no other key loads. A test of the platform alone: its specs are made up here and in
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
    _refused(lambda: _spec(slot={"prefix": "k"}, placement={**CAP, "offers": "w"}), "placement.offers is true or false")
    assert _spec(slot={"prefix": "k"}, placement={**CAP, "offers": True}).offers is True     # offered as `k-<n>`


def test_the_base_worker_names_its_slot_by_its_spec_and_no_subsystem_class_copies_it():
    """`slot:` is executed by the platform (the architect's rule: a key the loader reads and a subsystem executes must
    not exist). A worker of a spec that says `slot: {prefix: k}` makes `k-<n>`, and started under the spec's variable
    takes that name; a spec that says no `slot` makes `w-<n>`. (Each subsystem's worker class copied the spec's into
    `SLOT_PREFIX` and `NAME_ENV`, and passed `runtime.slot` its own reading: a class that forgot made `w-<n>`.)"""
    from tests.conftest import Box
    from w2cplatform.worker import Worker
    spec = _spec(slot={"prefix": "k", "name_env": "KEEPER_NAME"})

    def started(box, spec, env):
        w = Worker(spec.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, spec=spec)
        w.claim_at_start(None, env)
        return w.name
    box = Box()
    assert started(box, spec, {}) == "k-1"                                  # made: the spec's prefix
    assert started(box, spec, {"KEEPER_NAME": "k-7"}) == "k-7"              # given in the spec's variable
    assert started(box, spec, {"SLOT_INDEX": "3"}) == "k-3"
    assert started(Box(), _spec(), {}) == "w-1"                             # no `slot`: `w`


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
    _refused(lambda: _spec(objects={"files": ["x/*"]}), "`objects:` is {rows:")
    _refused(lambda: catalog.load_dir(tempfile.mkdtemp(prefix="empty-")), "no <sub>.subsystem.yaml there")
    _refused(lambda: catalog.spec("nobody"), "no subsystem 'nobody'")


def test_a_heartbeat_field_its_spec_says_is_a_string_and_is_not_garbles_the_heartbeat():
    """`heartbeat: {strings: [...]}` (the product's key, the course implements it): the fields of a subsystem's
    heartbeats that are strings by contract and that something decides by. A worker's heartbeat holding one of them as
    anything but a string is garbled — skipped and counted (`<sub>_heartbeats_garbled`), as one that does not parse;
    absent is not garbled, and another subsystem's heartbeat is not this spec's business. The platform's own fields are
    not a spec's to name, and a field is named once."""
    from w2cplatform.contract import GARBLED, Heartbeat, parse_heartbeat
    root = tempfile.mkdtemp(prefix="specs-")
    with open(os.path.join(root, "beater.subsystem.yaml"), "w") as f:
        f.write("name: beater\nunit: {rows: items, id: name, fields: {name: {type: string}}}\n"
                "placement: {capacity: {from: capacity, default: 2}}\nheartbeat: {strings: [shelf, shelf_error]}\n")
    catalog.load_dir(root)
    assert catalog.spec("beater").heartbeat_strings == ("shelf", "shelf_error")
    key = "beater/heartbeats/w-1"
    beat = lambda **extra: Heartbeat("w-1", 1.0, [], extra).to_bytes()      # noqa: E731
    assert parse_heartbeat(key, beat(shelf="a", shelf_error="")).extra["shelf"] == "a"
    assert parse_heartbeat(key, beat()) is not None                         # not said: nobody is sent by it
    before = GARBLED.get("beater", 0)
    for bad in (beat(shelf=5), beat(shelf="a", shelf_error=None), beat(shelf=["a"])):
        assert parse_heartbeat(key, bad) is None
    assert GARBLED["beater"] == before + 3
    assert parse_heartbeat("nobody/heartbeats/w-1", beat(shelf=5)) is not None
    _refused(lambda: _spec(heartbeat={"strings": ["server"]}), "heartbeat.strings: 'server' is no field of its own")
    _refused(lambda: _spec(heartbeat={"strings": ["fetched"]}), "heartbeat.strings: 'fetched' is no field of its own")
    _refused(lambda: _spec(heartbeat={"strings": ["a", "a"]}), "or is said twice")
    _refused(lambda: _spec(heartbeat={"strings": "a"}), "`heartbeat:` is {strings:")


def test_who_reads_a_secret_row_is_what_the_specs_say_and_the_rights_are_held_to_it():
    """`secrets: {readers: {<row>: [<role>]}, reads: [<row>]}` (the product's key, the course checks it): the rights file
    is the grants the specs make, and the declaration is the promise they are held to (`cluster.rights.check_secrets`).
    testsub2's console alone reads its door's seed, as it says. Named with a role that does not read it — or kept under
    the subsystem's own name, where its controller and worker read every row — it is no file at all, the disagreement
    named; a role is one of the platform's. `reads` grants as well, as the product's key does (ADR-0024): the worker
    that names a row reads it — a prefix as its rows — and a row another spec keeps secret has that worker among its
    readers, the others still held to the declaration."""
    from w2cplatform.cluster.rights import roles
    from w2cplatform.rights import allowed
    two = _testsub2()
    roles([SubsystemSpec.from_dict(_testsub()), SubsystemSpec.from_dict(two)], "test")
    for secrets, row in (({"reads": ["domain/member-key"]}, "domain/member-key"),
                         ({"reads": ["domain/test/clients/"]}, "domain/test/clients/a"),
                         ({"readers": {"door/signer": ["console"]}, "reads": ["door/signer"]}, "door/signer")):
        got = roles([SubsystemSpec.from_dict(_testsub()), SubsystemSpec.from_dict({**two, "secrets": secrets})], "test")
        assert allowed(got["testsub2worker"]["read"], row), (secrets, got["testsub2worker"]["read"])
        assert not allowed(roles([SubsystemSpec.from_dict(_testsub()), SubsystemSpec.from_dict(two)],
                                 "test")["testsub2worker"]["read"], row), row    # …and not without it
    for secrets, words in (({"readers": {"door/signer": ["console", "worker"]}}, "the rights let console read it"),
                           ({"readers": {"testsub2/vault/": ["console"]}},
                            "testsub2/vault/: the specs name console as its readers, and the rights let console, "
                            "domain, domainconsole, testsub2controller, testsub2worker, testsubdomain read it")):
        _refused(lambda secrets=secrets: roles([SubsystemSpec.from_dict(_testsub()),
                                                SubsystemSpec.from_dict({**two, "secrets": secrets})], "test"), words)
    for bad, words in (({"readers": {"door/signer": ["operator"]}}, "is a list of roles"),
                       ({"readers": {"/door": ["console"]}}, "no key of the store"),
                       ({"reads": "door/signer"}, "`secrets:` is {readers:"), ({}, "`secrets:` is {readers:")):
        _refused(lambda bad=bad: SubsystemSpec.from_dict({**two, "secrets": bad}), words)


def test_how_long_data_goes_on_past_an_unconfirmed_lease_is_the_specs_and_typed():
    """`lease: {unconfirmed_max: forever | off | <seconds>}` (the architect, 5 Oct; it was `UNCONFIRMED_MAX` in a
    subsystem's environment): `forever` is no ceiling, `off` — the platform's default — none at all, a number that many
    seconds; the worker takes it from its spec (`Worker.unconfirmed_max`, and every lease it opens). Typed (the architect
    after the fourteenth review, 2026-10-06): a whole number of seconds above 0 or one of the two words — a word `"90"`,
    a zero, a negative, a flag, `false`/`no`/`OFF`, `90.5`, `1e308`, an empty `lease:` are refused at load with the
    path; `off` written bare is the word `off` (a spec is YAML 1.2, `specyaml.py`). And a place any box may write is let go
    unconfirmed when the spec says so next to it (`placement.places.lease: strict`), nothing else."""
    from tests.conftest import Box
    from w2cplatform import specyaml
    from w2cplatform.worker import Worker
    said = lambda v: _spec(lease={"unconfirmed_max": v}).unconfirmed_max     # noqa: E731
    assert (_spec().unconfirmed_max, said("forever"), said("off"), said(90)) == (0.0, None, 0.0, 90.0)
    bare = specyaml.loads("lease: {unconfirmed_max: off}")["lease"]          # the product's spelling: the word itself
    assert bare == {"unconfirmed_max": "off"} and _spec(lease=bare).unconfirmed_max == 0.0
    for bad in ({"unconfirmed_max": "90"}, {"unconfirmed_max": 0}, {"unconfirmed_max": -5}, {"unconfirmed_max": True},
                {"unconfirmed_max": False}, {"unconfirmed_max": "no"}, {"unconfirmed_max": "OFF"},
                {"unconfirmed_max": 90.5}, {"unconfirmed_max": 1e308}, {"unconfirmed_max": float("nan")},
                {"unconfirmed_max": "always"}, {}, {"unconfirmed_max": 90, "strict": True}, "forever", None):
        _refused(lambda bad=bad: _spec(lease=bad), "lease.unconfirmed_max is forever, off or a whole number of seconds")
    box = Box()
    for said, want in (("forever", None), (90, 90.0), ("off", 0.0)):
        spec = _spec(lease={"unconfirmed_max": said})
        w = Worker(spec.sub, "w-1", box.vars, box.objects, clock=box.clock, wall=box.wall, spec=spec)
        assert w.unconfirmed_max == want, (said, w.unconfirmed_max)
    assert SubsystemSpec.from_dict(_testsub2()).places["lease"] == "strict"
    two = _testsub2()
    two["placement"]["places"] = {**two["placement"]["places"], "lease": "loose"}
    _refused(lambda: SubsystemSpec.from_dict(two), "lease?: strict")


# A url field the way a subsystem says how its addresses carry a login.
TARGET = {"type": "url", "required": True, "schemes": {"https": {}, "sftp": {}},
          "credentials": {"login": "account_name", "secret": "pass_secret"},
          "secret_in": [{"param": ["pwd", "token*", "*key", "=auth", "user", "*name"], "login": ["user", "*name"]},
                        {"regex": r"(?:^|/)~(?P<login>[^:/]+):(?P<secret>[^/]+)", "in": "path"},
                        {"regex": r"^(?P<name>code)=(?P<secret>.+)$", "in": "fragment", "schemes": ["sftp"]},
                        {"nested": ["via"]}]}


def _target_spec(target=None):
    return _spec(unit={"rows": "items", "id": "name", "fields": {
        "name": {"type": "string", "required": True}, "target": target or TARGET,
        "account_name": {"type": "string"}, "pass_secret": {"type": "string", "bound_to": ["target"]}}})


def test_how_an_address_carries_a_login_is_the_specs_beside_the_platforms_few_common_names():
    """The forms a credential takes in an address — the names of its parameters, a login spelt in the path, a parameter
    holding another address — were lists in `secrets.py`. They are a url field's `secret_in` now, beside a few names
    every system spells a credential by (`COMMON_RULES`, the product's decision of 5 Oct: `pwd`, `token`, `key` as the
    last word, `=auth`, `=pin`…): with no rules the platform refuses what RFC 3986 says is a login (an `@`, a port that
    is no number) and those names; with the field's rules it refuses what they find and hides the passwords — a login is
    said as written, a userinfo's too (`me:***@`) —, and the refusal names the field of `credentials` for what it found
    (a password the secret's, a login alone the login's), never the value. A regex reads the part it names of an address
    of the schemes it names, its escapes undone; its `name` is what the refusal says."""
    for plain in ("https://h/~me:Hunter2/x", "https://h/x?via=https%3A%2F%2Fh2%2F%3Fpwd%3DHunter2",
                  "https://h/x?gpio_pin=4&hotkey=2&p=1"):
        assert address_refusal(plain, NO_RULES) is None and hide_in_url(plain, NO_RULES) == plain
    for common in ("pwd", "hot_key", "pin", "access_token", "auth"):
        assert hide_in_url(f"https://h/x?{common}=Hunter2", NO_RULES) == f"https://h/x?{common}=***", common
    assert hide_in_url("https://me:Hunter2@h/x", NO_RULES) == "https://me:***@h/x"
    assert address_refusal("https://me:Hunter2@h/x", NO_RULES) and address_refusal("https://h:Hunter2/x", NO_RULES)
    rules = _target_spec().fields["target"].rules
    assert is_credential_param("pwd", rules) and is_credential_param("token_bucket", rules)     # `token*`: a word begins it
    assert is_credential_param("apiKey", rules) and not is_credential_param("keyframe", rules)  # `*key`: the last word ends it
    assert is_credential_param("auth", rules) and not is_credential_param("enable_auth", rules)  # `=auth`: the whole name
    assert "pwd" in address_refusal("https://h/x?pwd=Hunter2", rules)
    assert "a login and a password in its path" in address_refusal("https://h/~me:Hunter2/x", rules)
    assert "'via'" in address_refusal("https://h/x?via=https%3A%2F%2Fh2%2F%3Fpwd%3DHunter2", rules)
    for bad in ("https://h/x?pwd=Hunter2", "https://h/~me:Hunter2/x", "https://h/x?via=https%3A%2F%2Fh2%2F%3Fpwd%3DHunter2"):
        assert "Hunter2" not in hide_in_url(bad, rules), bad
    spec = _target_spec()
    for bad, named, unnamed in (("https://h/x?pwd=Hunter2", "pass_secret", "account_name"),
                                ("https://h/~me:Hunter2/x", "account_name and the password or token in pass_secret", None),
                                ("https://h/x?user=me", "Put the login in account_name", "pass_secret"),
                                ("https://h/x?user=me&pwd=Hunter2", "account_name and the password or token in pass_secret",
                                 None)):
        try:
            spec.refuse({"target": bad})
            raise AssertionError(f"taken: {bad}")
        except Refused as e:
            assert named in str(e) and (unnamed is None or unnamed not in str(e)) and "Hunter2" not in str(e), str(e)
    # a login is refused and said; a regex's part, scheme and escapes; its `name` in the words
    assert "a login in its parameters (user)" in address_refusal("https://h/x?user=me", rules)
    assert hide_in_url("https://h/x?user=me&nick_name=you", rules) == "https://h/x?user=me&nick_name=you"
    assert hide_in_url("https://h/~me:Hunter2/x", rules) == "https://h/~me:***/x"
    assert hide_in_url("sftp://h/x#code=Hunter2", rules) == "sftp://h/x#code=***"
    assert "a password in its fragment (code)" in address_refusal("sftp://h/x#code=Hunter2", rules)
    assert address_refusal("https://h/x#code=Hunter2", rules) is None                     # not of its schemes
    assert hide_in_url("https://h/%7Eme%3AHunter2/x", rules) == "https://h/%7Eme%3A***/x"  # decoded, hidden as written
    assert "'via'" in address_refusal("https://h/x?via=ffmpeg:https%3A%2F%2Fme%3AHunter2%40h2%2F", rules)
    try:
        spec.refuse({"target": "ftp://h/x"})
        raise AssertionError("a scheme the field does not take was taken")
    except Refused as e:
        assert "https, sftp" in str(e) and "'ftp'" in str(e), str(e)
    spec.refuse({"target": "https://h/x?channel=1"})                                     # an ordinary address stands


def test_a_url_fields_words_are_read_at_load_and_anything_else_is_refused():
    """`schemes`, `credentials`, `secret_in` belong to a url field; `credentials` names a string field and a `*_secret`
    one of the row; `secret_in` is a list of the three kinds, a regex names what it finds and where it reads."""
    _refused(lambda: _spec(unit={"rows": "i", "fields": {"n": {"type": "string", "schemes": {"https": {}}}}}),
             "belong to a url field")
    _refused(lambda: _target_spec({**TARGET, "credentials": {"login": "pass_secret"}}), "credentials.login")
    _refused(lambda: _target_spec({**TARGET, "credentials": {"secret": "account_name"}}), "credentials.secret")
    _refused(lambda: _target_spec({**TARGET, "schemes": {"HTTPS": {}}}), "not a scheme in lower case")
    _refused(lambda: _target_spec({**TARGET, "schemes": ["https", "sftp"]}), "`schemes` is a map")   # the list it was (ADR 0003)
    _refused(lambda: _target_spec({**TARGET, "schemes": {"https": {"port": "none"}}}), "is not a word of the dictionary")
    for bad, words in (({"param": "pwd"}, "`param` is a list of names"),
                       ({"param": ["*pwd*"]}, "a name, `=name`, `name*` or `*name`"),
                       ({"param": ["=pwd*"]}, "a name, `=name`"),
                       ({"login": ["us"]}, "is param, regex or nested"),
                       ({"param": ["a"], "login": []}, "`login` is a list of names"),
                       ({"param": ["a"], "login": ["us er"]}, "in `login` is a name"),
                       ({"param": ["a"], "login": ["b"]}, "'b' in `login` is not in `param`"),
                       ({"regex": "x(?P<secret>.)"}, "`in:` path, query, authority, fragment"),
                       ({"regex": "x(?P<secret>.)", "in": "host"}, "`in:` path, query"),
                       ({"regex": "x(?P<secret>.)", "in": "path", "schemes": "https"}, "`schemes` is a list of schemes"),
                       ({"regex": "x(?P<secret>.)", "in": "path", "decoded": "yes"}, "`decoded` is true or false"),
                       ({"regex": "x(?P<secret>.)", "in": "path", "where": 1}, "an entry of `secret_in` is one of"),
                       ({"regex": "x(.)", "in": "path"}, "names what it finds"),
                       ({"regex": "x(?P<secret>.)(?P<other>.)", "in": "path"}, "no other"),
                       ({"regex": "(", "in": "query"}, "no regular expression"),
                       ({"nested": []}, "`nested` names the pairs"), ({"nested": "via"}, "`nested` names the pairs"),
                       ({"other": 1}, "param, regex or nested"),
                       ({"param": ["a"], "nested": ["b"]}, "an entry of `secret_in` is one of")):
        _refused(lambda bad=bad: SecretRules.parse([bad], "field t"), words)
    _refused(lambda: SecretRules.parse({"param": ["a"]}, "field t"), "`secret_in` is a list")


def test_a_key_the_platform_does_not_read_is_refused_at_any_level_and_named_where_it_stands():
    """The key sets are closed (the architect, 2026-10-05): a key nobody reads — a typo, another team's word — is a
    refusal at load naming it with its path, at the top, in a section, in a field, in an item of a list. Where the
    spec writes names (a field, an event kind) or words (`display.kinds`), anything stands."""
    plain = _testsub()
    for words, add in (("`heartbeat:` is {strings:", {"heartbeat": {"strings": ["jam"], "beats": 1}}),
                       ("`secrets:` is {readers:", {"secrets": {"writers": {"door/signer": ["console"]}}}),
                       ("`objects:` is {rows:", {"objects": {"rows": ["marks/*"], "files": ["x/*"]}})):
        _refused(lambda add=add: SubsystemSpec.from_dict({**plain, **add}), words)     # …by the section's own reader
    for where, add in (("placement.requries", {"placement": {**plain["placement"], "requries": "resource"}}),
                       ("console.gauge", {"console": {"gauge": "x"}}),
                       ("events.suppress.tick.windw", {"events": {"suppress": {"tick": {"window": 5, "windw": 6}}}}),
                       ("unit.fields.name.requird", {"unit": {**plain["unit"], "fields": {
                           **plain["unit"]["fields"], "name": {**plain["unit"]["fields"]["name"], "requird": True}}}}),
                       ("unit.derived.rows", {"unit": {**plain["unit"], "derived": [{"row": "r/{id}", "items": {},
                                                                                       "rows": 1}]}})):
        _refused(lambda add=add: SubsystemSpec.from_dict({**plain, **add}), f"`{where}`")
    from w2cplatform.speckeys import unknown
    assert unknown({**plain, "display": {"kinds": {"any.kind": "слово"}, "fields": {"x": "y"}},
                    "events": {"suppress": {"any-kind": {"window": 1}}}}) == []
    assert unknown({"metrics": [{"name": "m", "from": "status.phase", "agg": "count", "where": {"a": 1}, "colour": 2}]}) \
        == ["metrics.colour"]


def test_a_units_card_is_words_naming_its_fields():
    """`display` is closed by sections (the architect, 5 Oct): unit, units, units_count, section, general, fields,
    field_help, options, form, events, kinds, actions, keys, tree (its words the product's: group_title, no_group,
    pick_note…) — passed to the page. What a section holds is free words with ONE check at load: a word for a field names
    one — `fields`, `field_help` and `form[].fields` a field of the row (or `id`, a status column), or a field of the
    unit's status a block names (`form[].status`); `options` the values of a field's `enum`, a status field's values being
    the worker's and free. Anything else is refused with the path."""
    spec = SubsystemSpec.from_dict(_testsub2())
    assert spec.display["form"][0]["fields"] == ["name", "mode"] and spec.display["options"]["mode"]["loud"] == "громко"
    assert spec.display["options"]["lane"] == {"fast": "быстрая", "slow": "медленная"}      # a status field: free values
    assert (spec.display["units_count"], spec.display["tree"]["no_group"], spec.display["events"]) == ("счётов", "Без зоны", False)
    d2 = _testsub2()
    d2["display"]["options"].pop("lane")                 # the words for the status field, out of the way of a form replaced
    d2["display"]["field_help"].pop("lane", None)
    for bad, words in (({"fields": {"nothing": "x"}}, "display.fields is"), ({"options": {"name": {"a": "b"}}}, "display.options is"),
                       ({"options": {"mode": {"quiet": "тихо"}}}, "display.options is"),
                       ({"options": {"belt": {"a": "b"}}}, "display.options is"),           # no field, no status field
                       ({"field_help": {"nothing": "x"}}, "['nothing'] names no field"),
                       ({"fields": {"lane": 1}}, "display.fields is"),
                       ({"form": [{"title": "t", "fields": ["nothing"]}]}, "display.form is"),
                       ({"form": [{"title": "t", "fields": ["lane"]}]}, "display.form is"),   # a status field is read only
                       ({"form": [{"title": "t", "fields": ["name"], "tab": 1}]}, "display.form is"),
                       ({"form": [{"title": "t", "fields": [], "status": [{"field": "lane", "when": "x"}]}]}, "form[].status"),
                       ({"form": [{"title": "t", "fields": [], "status": "lane"}]}, "form[].status"),
                       ({"general": 1}, "display.general is a word"), ({"units_count": ["счётов"]}, "display.units_count"),
                       ({"section": 2}, "display.section is a word"), ({"events": "no"}, "display.events is true or false"),
                       ({"kinds": {"tally.tick": 1}}, "display.kinds"),
                       ({"tree": {"group_by": "zone", "no_group": ["x"]}}, "display.tree is"),
                       ({"tree": {"group_by": "zone", "erase": "x"}}, "display.tree is")):
        _refused(lambda bad=bad: SubsystemSpec.from_dict({**d2, "display": {**d2["display"], **bad}}), words)
    # the words of a unit's groups box the module reads (`groupsBox`: remove, not_in, add_to, no_others, new_group) are
    # the tree's too — the set is the module's dictionary (the loader's verdicts, «Архитектор» 2026-10-06)
    box = {"remove": "убрать", "not_in": "ни в одной зоне", "add_to": "в зону", "no_others": "других зон нет",
           "new_group": "новая зона"}
    took = SubsystemSpec.from_dict({**d2, "display": {**d2["display"], "tree": {**d2["display"]["tree"], **box}}})
    assert {k: took.display["tree"][k] for k in box} == box
    for stray in ("status", "colour"):                   # a section of no one's: the loader names it with its path
        _refused(lambda stray=stray: SubsystemSpec.from_dict({**d2, "display": {**d2["display"], stray: {}}}),
                 f"`display.{stray}`")


def test_every_grant_of_a_subsystem_is_derived_from_its_spec():
    """What each process of a subsystem may write — the console's rows, the controller's placement, the worker's claims,
    and the three directories of objects with one writer each — is derived from the spec (`acl_*`, `Subsystem.acl_*`),
    and the cluster's rights file is generated from the same lists (`w2cplatform/cluster/rights.py`). Here on testsub,
    exactly: a grant dropped from a list (the controller's pass report, say) is a test that fails, not a 403 on a
    cluster every five seconds (the review's ninth pass)."""
    spec = SubsystemSpec.from_dict(_testsub())
    assert spec.acl_console() == ["testsub/counters/*", "testsub/next_id", "testsub/idem/*", "testsub/policy",
                                  "testsub/sweep", "testsub/requests/*", "platform/servers/*", "platform/drain",
                                  "platform/decommission/*", "platform/schema"]
    assert spec.acl_controller() == ["testsub/workers/*", "testsub/placement/*", "testsub/slots/*",
                                     "testsub/decommissioned/*", "delete:testsub/counters/*"]   # the key (ADR-0067)
    assert spec.acl_worker_role() == spec.sub.acl_worker() == ["testsub/epoch/*", "testsub/slots/*", "testsub/holds/*"]
    assert spec.sub.acl_objects_worker() == ["testsub/heartbeats/*", "testsub/contenders/*", "testsub/used/*",
                                         "testsub/commands/*"]   # its marks before it performs a request
    assert spec.sub.acl_objects_controller() == ["testsub/snapshot/*", "testsub/controller/pass"]
    assert spec.sub.acl_objects_console() == ["testsub/blobs/*",
                                          "testsub/commands/*"]   # the reaper ends a request in its mark (ADR-0054)


def test_a_worker_writes_its_units_rows_or_its_declared_tables_and_any_other_family_does_not_load():
    """ADR 0012 («Архитектор» with «Паритет», 2026-10-06): `worker.writes` names the subsystem's own unit rows or one of
    its DECLARED tables — a family whose form the spec says (`{key, fields}`) and whose rows a write goes through
    (`tables.write_row`). The course took any family under `<sub>/`: `writes: [finds]` with no `finds` declared was
    a token writing rows of no form that nobody served. Now such a family is refused at load, named, and so is a table
    only NAMED (`tables: [x]`): named is not declared. testsub2 (`writes: [shelves]`, a declared table) loads."""
    shelf = {"tables": {"shelves": {"key": "name", "fields": {"name": {"type": "string", "required": True}}}}}
    assert _spec(worker={"writes": ["items"]}).acl_worker_role()[-1] == "probe/items/*"      # its units' rows
    assert _spec(worker={"writes": ["shelves"]}, **shelf).acl_worker_role()[-1] == "probe/shelves/*"
    _refused(lambda: _spec(worker={"writes": ["finds"]}),
             "worker.writes names finds — neither its units' rows (items) nor one of its declared tables (none)")
    _refused(lambda: _spec(worker={"writes": ["shelves", "finds"]}, **shelf),
             "worker.writes names finds — neither its units' rows (items) nor one of its declared tables (shelves)")
    _refused(lambda: _spec(worker={"writes": ["notes"]}, tables=["notes"]), "worker.writes names notes")
    two = SubsystemSpec.from_dict(_testsub2())
    assert two.worker_writes == ("shelves",) and "testsub2/shelves/*" in two.acl_worker_role()


def test_group_by_and_spread_by_name_a_field_of_the_row_in_every_form():
    """The fourteenth review, majors 5 and 11 (ADR-0012): `placement.group_by` in its string form was not checked
    against `fields:` — `group_by: sourcee` loaded, every unit's group was empty, and sixteen units of one group went
    to four workers; `spread_by` naming no field, or not a string, loaded and dropped the filter (`servers_taken`
    of none), a second copy on the same server. Both are refused with the fields named."""
    zone = {"name": {"type": "string", "required": True}, "zone": {"type": "string"}}
    spec = lambda **pl: _spec(unit={"rows": "items", "id": "name", "fields": zone}, placement={**CAP, **pl})  # noqa: E731
    assert (spec(group_by="zone").group_by, spec(spread_by="zone").spread_by) == ("zone", "zone")
    for bad in ("zonee", "", 5, None, ["zone"]):
        _refused(lambda bad=bad: spec(group_by=bad), "placement.group_by is a field of the row (name, zone)")
        _refused(lambda bad=bad: spec(spread_by=bad), "placement.spread_by is a field of the row (name, zone)")


def test_every_number_of_a_request_family_is_finite_and_a_count_is_whole():
    """The fourteenth review, minor 5 (ADR-0012): `ttl: .nan` loaded (`< 0` is false for NaN) — the filter then dropped
    every row, `per_person` limited nothing and the reaper ended nothing by age; `.inf` and `per_person: 2.5` loaded
    too. `ttl` and `settle` are finite seconds, 0 or more; `valid_for` and `most_valid` finite above 0; `per_person` a
    whole number above 0."""
    base = {"schema": {"type": "object", "properties": {"unit": {"type": "string"}}}, "valid_for": 30, "most_valid": 600,
            "per_person": 3, "settle": 0, "ttl": 0}
    got = _spec(requests=base).requests
    assert (got["valid_for"], got["most_valid"], got["per_person"], got["settle"], got["ttl"]) == (30, 600, 3, 0, 0)
    nan, inf = float("nan"), float("inf")
    for k, bads in (("ttl", (nan, inf, -1, "60", True)), ("settle", (nan, inf, -1, "1")),
                    ("valid_for", (nan, inf, 0, -1, "30")), ("most_valid", (nan, inf, 0, "600")),
                    ("per_person", (2.5, 0, -1, nan, inf, 3.0, "3", True))):
        for bad in bads:
            _refused(lambda k=k, bad=bad: _spec(requests={**base, k: bad}), f"requests.{k} is ")
    from w2cplatform import specyaml
    for text in ("ttl: .nan", "ttl: .inf", "per_person: 2.5"):         # the review's three, as a file writes them
        _refused(lambda text=text: _spec(requests={**base, **specyaml.loads(text)}), "requests.")


def test_a_request_key_names_fields_of_the_requests_schema_and_closes_its_braces_and_a_group_stamp_needs_a_group():
    """The fourteenth review, minor 26, the loader's side (ADR-0012): `requests.key` with a name the request's schema
    does not declare made every request a 400 «bad id»; `"x-{unit"` left a brace open; `stamp: [group]` without
    `placement.group_by` stamped nothing. Each is refused at load."""
    fields = {"name": {"type": "string", "required": True}, "zone": {"type": "string"}}
    req = {"schema": {"type": "object", "properties": {"unit": {"type": "string"}, "add": {"type": "integer"}}},
           "valid_for": 30, "most_valid": 600}
    spec = lambda pl=None, **r: _spec(unit={"rows": "items", "id": "name", "fields": fields},  # noqa: E731
                                      placement={**CAP, **(pl or {})}, requests={**req, **r})
    assert spec(key="{unit}-{add:int}").requests["key"] == "{unit}-{add:int}"
    assert spec({"group_by": "zone"}, stamp=["by", "group"]).requests["stamp"] == ["by", "group"]
    _refused(lambda: spec(key="{nosuch}"), "requests.key names nosuch, which requests.schema does not declare")
    for bad in ("x-{unit", "x-unit}", "{unit:float}", "", 5):
        _refused(lambda bad=bad: spec(key=bad), "every brace closed")
    _refused(lambda: spec(stamp=["group"]), "requests.stamp names `group`, and placement says no `group_by`")


def test_worker_requests_names_subsystems_of_the_catalogue_that_take_requests():
    """The fourteenth review, minor 9 (ADR-0012, ADR-0054): `worker.requests` was not checked against the catalogue —
    a typo (`recc`), the subsystem itself, a subsystem with no `requests:` all loaded, every filing returned True, no
    holder served the row and no reaper ended it. Asked where the catalogue is whole (`catalog.requests_known`): the end
    of `load_dir`, and a controller's start — as `near_known`."""
    import shutil
    from tests.conftest import Box, in_catalogue
    from w2cplatform.spec import SpecController
    one = SubsystemSpec.from_dict(_testsub())
    plain = _spec(name="plain")                                                 # a subsystem of no family
    for names, words in ((["recc"], "names 'recc', which is no subsystem this process loaded"),
                         (["probe"], "names 'probe', which is the spec itself"),
                         (["plain"], "names 'plain', which declares no `requests:`")):
        spec = _spec(worker={"requests": names})
        with in_catalogue(one, plain, spec):
            _refused(lambda spec=spec: catalog.requests_known(spec), words)
            box = Box()
            _refused(lambda spec=spec: SpecController(spec, box.vars, box.objects, wall=box.wall), words)
    with in_catalogue(one):
        catalog.requests_known(_spec(worker={"requests": ["testsub"]}))          # a family there: it files to it
    d, files = tempfile.mkdtemp(), dict(catalog._files)
    with open(os.path.join(d, "filer.subsystem.yaml"), "w", encoding="utf-8") as f:     # a filer to testsub…
        f.write("name: filer\nworker: {requests: [testsub]}\nunit: {rows: items, id: name, fields: {name: {type: string, "
                "required: true}}}\nplacement: {capacity: {from: capacity, default: 4}}\n")
    try:
        with in_catalogue():
            catalog._loaded.clear()
            _refused(lambda: catalog.load_dir(d), "worker.requests names 'testsub', which is no subsystem")
        shutil.copy(os.path.join(TESTDATA, "testsub.subsystem.yaml"), d)       # …and with testsub beside, loads
        with in_catalogue():
            catalog._loaded.clear()
            assert [s.name for s in catalog.load_dir(d)] == ["filer", "testsub"]
    finally:
        catalog._files.clear()
        catalog._files.update(files)


def _testsub() -> dict:
    from w2cplatform import specyaml
    return specyaml.load(os.path.join(TESTDATA, "testsub.subsystem.yaml"))


def _testsub2() -> dict:
    from w2cplatform import specyaml
    return specyaml.load(os.path.join(TESTDATA, "testsub2.subsystem.yaml"))
