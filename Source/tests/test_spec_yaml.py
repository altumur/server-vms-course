"""How a spec's file is read (`w2cplatform/specyaml.py`; ADR-0012, ADR-0019; «Архитектор», 2026-10-06, after the
fourteenth review): YAML 1.2 core, a subset — one document, a mapping, no anchors, aliases, tags or duplicate keys, On/Off
words and not booleans, decimal integers within 2^53 — and every refusal a ValueError naming the file, where and the
line. A test of the platform alone: the specs are written here."""
from __future__ import annotations

import os
import tempfile

import yaml

from w2cplatform import specyaml
from w2cplatform.spec import SubsystemSpec

TESTDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata")
SPECS = [os.path.join(TESTDATA, f) for f in ("testsub.subsystem.yaml", "testsub2.subsystem.yaml")] + \
    [os.path.join(os.path.dirname(TESTDATA), "..", "vms", f) for f in
     ("vms.subsystem.yaml", "rec.subsystem.yaml", "live.subsystem.yaml", "det.subsystem.yaml", "detjob.subsystem.yaml",
      "survey.subsystem.yaml", "auto.subsystem.yaml")]

BASE = """name: probe
unit:
  rows: items
  id: name
  fields:
    name: {type: string, required: true}
    zone: {type: string}
placement:
  capacity: {from: capacity, default: 4}
  constraint: labels-subset
lease: {unconfirmed_max: off}
"""


def _write(text, name="probe.subsystem.yaml") -> str:
    path = os.path.join(tempfile.mkdtemp(), name)
    with open(path, "wb") as f:
        f.write(text if isinstance(text, bytes) else text.encode("utf-8"))
    return path


def _refused(text, *words) -> str:
    path = _write(text)
    try:
        SubsystemSpec.load(path)
    except ValueError as e:
        for w in (path, *words):
            assert w in str(e), (w, str(e))
        return str(e)
    raise AssertionError(f"loaded, and should not have: {words}")


def test_a_key_said_twice_is_refused_naming_the_key_and_its_line_not_the_last_kept():
    """The fourteenth review, major 9: `yaml.safe_load` kept the last of a key said twice and dropped the first with
    all under it — a second `lease:` appended to a spec turned `off` into `forever`, a second `placement:` hid a typo
    (`fallbak`) the closed key set would have refused. Now a duplicate at any level is refused: the key, the path of
    the mapping it stands in, and its line."""
    _refused(BASE + "lease: {unconfirmed_max: forever}\n", "the key 'lease' is said twice", "line 12")
    _refused(BASE.replace("placement:\n", "placement:\n  fallbak: 1\nplacement:\n", 1),
             "the key 'placement' is said twice", "line 10")
    _refused(BASE.replace("{unconfirmed_max: off}", "{unconfirmed_max: off, unconfirmed_max: forever}"),
             "lease (line 11)", "'unconfirmed_max' is said twice")
    _refused(BASE.replace("    zone: {type: string}\n", "    zone: {type: string}\n    zone: {type: int}\n"),
             "unit.fields (line 8)", "'zone' is said twice")
    _refused(BASE + "name: other\n", "'name' is said twice")
    # …and by the course's every loading path: a directory (`catalog.load_dir`) refuses the same file
    from w2cplatform import catalog
    d = os.path.dirname(_write(BASE + "lease: {unconfirmed_max: forever}\n"))
    try:
        catalog.load_dir(d)
    except ValueError as e:
        assert "said twice" in str(e)
    else:
        raise AssertionError("a directory loaded a spec with a key said twice")


def test_on_off_yes_no_are_words_true_false_are_booleans_and_an_integer_is_decimal_within_2_53():
    """YAML 1.2 core: only `true`/`false` (any of their three cases) are booleans; `On`, `off`, `Yes`, `no` are the
    words; `null`, `~` and nothing are null. An integer is decimal digits — `010` is ten, and `0x10`, `0o7`, `1_000`,
    `1:30` are words — within ±(2^53 − 1); a float is `1.5`, `1e308`, `.inf`."""
    got = specyaml.loads("a: On\nb: off\nc: Yes\nd: no\ne: true\nf: FALSE\ng: True\nh: ~\ni: null\nj:\nk: 010\n"
                         "l: 0x10\nm: 1_000\nn: 1:30\no: 0o7\np: 1e308\nq: .inf\nr: 1.5\ns: 2001-12-14\nt: -7\n"
                         "u: 9007199254740991\non: 1\n")
    assert got == {"a": "On", "b": "off", "c": "Yes", "d": "no", "e": True, "f": False, "g": True, "h": None,
                   "i": None, "j": None, "k": 10, "l": "0x10", "m": "1_000", "n": "1:30", "o": "0o7", "p": 1e308,
                   "q": float("inf"), "r": 1.5, "s": "2001-12-14", "t": -7, "u": 2 ** 53 - 1, "on": 1}, got
    assert specyaml.loads('a: "true"\nb: \'010\'\n') == {"a": "true", "b": "010"}       # quoted: words, always
    for big in ("9007199254740992", "-9007199254740992", "99999999999999999999999"):
        try:
            specyaml.loads(f"name: x\nn: {big}\n", "big.yaml")
        except ValueError as e:
            assert "big.yaml" in str(e) and "n (line 2)" in str(e) and "2^53" in str(e), str(e)
        else:
            raise AssertionError(big)


def test_anchors_aliases_merge_keys_tags_and_a_second_document_are_refused_with_where():
    """What the eye does not see is not in a spec: an anchor and an alias copy a block, `<<` merges one, a tag retypes
    a value; and a file is one document."""
    _refused(BASE.replace("    zone: {type: string}", "    zone: &z {type: string}\n    zona: *z"), "an anchor (&z)",
             "unit.fields.zone (line 7)")
    _refused(BASE.replace("  constraint: labels-subset", "  constraint: !!str labels-subset"), "a tag",
             "placement.constraint")
    _refused(BASE.replace("  constraint: labels-subset", "  constraint: ! labels-subset"), "a tag")
    _refused(BASE.replace("  constraint: labels-subset", "  <<: {constraint: labels-subset}"), "a merge key (<<)")
    _refused(BASE + "---\nname: second\n", "not a spec's YAML", "expected a single document")
    _refused(BASE + "---\n", "not a spec's YAML")


def test_a_file_that_is_not_a_spec_is_refused_as_a_value_error_naming_it_never_a_crash():
    """The fourteenth review, minor 25: garbage raised AttributeError, RecursionError, PyYAML's ParserError out of a
    load. Every one is a ValueError naming the file now — and so is a BOM, a NUL, a byte that is not UTF-8, a tab."""
    cases = [("- a\n- b\n", "a spec is a mapping of keys, not list"), ("", "not nothing"), ("just words\n", "not str"),
             (b"\xef\xbb\xbf" + BASE.encode(), "byte order mark"), (BASE.replace("items", "it\x00ems"), "a NUL"),
             (BASE.encode().replace(b"items", b"it\xffems"), "is not UTF-8"),
             (BASE.replace("  constraint:", "\tconstraint:"), "not a spec's YAML"),
             (BASE + "  stray: [1, 2\n", "not a spec's YAML"),
             (BASE.replace("    zone: {type: string}", "    zone: {type: string}\n       over: 1"), "not a spec's YAML"),
             (BASE + "deep: " + "{a: " * 5000 + "1" + "}" * 5000 + "\n", "nested deeper than 64 levels"),
             (BASE + "deep:\n" + "".join("  " * (i + 1) + "a:\n" for i in range(100)) + "  " * 101 + "b: 1\n",
              "nested deeper than 64 levels"),
             ("name: x\nplacement: [a]\nunit: {}\n", "not a spec"), ("name: x\nunit: 5\n", "not a spec"),
             ("{a: 1}: b\n", "a key is a word, not a dict")]
    for text, words in cases:
        _refused(text, words)


def test_every_spec_of_the_course_reads_the_same_by_the_spec_loader_as_by_yaml_but_the_word_off():
    """The real specs say nothing the subset refuses, and read as PyYAML read them — but `off`, which YAML 1.1 read as
    false and YAML 1.2 reads as the word it is (`lease.unconfirmed_max: off`). None nests past a dozen levels."""
    def depth(v):
        return 1 + max([depth(x) for x in (v.values() if isinstance(v, dict) else v)] or [0]) \
            if isinstance(v, (dict, list)) else 0
    for path in SPECS:
        mine = specyaml.load(path)
        with open(path, encoding="utf-8") as f:
            theirs = yaml.safe_load(f)
        if mine.get("lease", {}).get("unconfirmed_max") == "off":
            assert theirs["lease"]["unconfirmed_max"] is False
            theirs["lease"]["unconfirmed_max"] = "off"
        assert mine == theirs, path
        assert depth(mine) <= 16 < specyaml.MAX_DEPTH, path


def test_a_json_fields_default_or_inherit_is_any_json_value_and_another_types_is_still_walked():
    """The fourteenth review, minor 25: `{type: json, default: {a: 1}}` and `inherit: {…}` were refused as keys nobody
    reads (`unit.fields.*.default.a`). A `json` field's value is any JSON — a map or a list; another type's map is
    walked and refused as before."""
    doc = SubsystemSpec.from_dict({"name": "probe", "unit": {"rows": "items", "id": "name", "fields": {
        "name": {"type": "string", "required": True}, "doc": {"type": "json", "default": {"a": 1, "b": [1, {"c": 2}]}},
        "up": {"type": "json", "inherit": {"x": {"y": 1}}}}}, "placement": {"capacity": {"from": "capacity", "default": 4}}})
    assert doc.fields["doc"].default == {"a": 1, "b": [1, {"c": 2}]} and doc.fields["up"].inherit == {"x": {"y": 1}}
    _refused(BASE.replace("    zone: {type: string}", "    zone: {type: string, default: {a: 1}}"),
             "unit.fields.zone.default.a")
