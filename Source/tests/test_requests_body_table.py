"""One table of how a request's body value is written into its row, for the course and the product
(`testdata/requests_body.tsv`; the architect with «Паритет», 2026-10-05, ADR 0012): a string as it is, `true`/`false`, a
whole number in integer digits, any other in its shortest decimal, `null` no field at all, a list or a map in the one
canonical form of a JSON value in a row (`w2cplatform/canonical.py`, the product's `CanonicalJSON`). The door wrote
`str(v)` — `True`, `None`, `5.0` — and a holder in Go read another value than one in Python. The table is «Паритет»'s:
when the product's committed main keeps it, the course's file is a copy, byte for byte; until then it is the course's
seed, in the same columns (`raw`, `written`, `note`)."""
from __future__ import annotations

import json
import os

from tests.productdir import SOURCE, product_file

TABLE = os.path.join(SOURCE, "tests", "testdata", "requests_body.tsv")
ABSENT, REFUSED = "(absent)", "(refused)"


def _rows():
    with open(TABLE, encoding="utf-8", newline="") as f:
        for i, line in enumerate(f.read().split("\n"), 1):
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            assert len(cols) == 3, f"line {i}: a row is raw, written, note: {line!r}"
            yield i, cols


def _family():
    """A family of deadlines whose schema says of `v` only `maxLength: 32` (the VMS's arguments say as much), one unit."""
    import tempfile

    from tests.conftest import Served
    from w2cplatform import catalog
    from w2cplatform.console import SpecConsole
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.spec import SpecController, SubsystemSpec
    from w2cplatform.variables import FileVariables
    spec = SubsystemSpec.from_dict({
        "name": "jar", "unit": {"rows": "jars", "id": "name", "fields": {"name": {"type": "string"}}},
        "placement": {"capacity": {"from": "capacity", "default": 4}},
        "requests": {"schema": {"type": "object", "required": ["unit"], "additionalProperties": False,
                                "properties": {"unit": {"type": "string"}, "v": {"maxLength": 32}}},
                     "valid_for": 30, "most_valid": 600}})
    catalog.register(spec)
    root = tempfile.mkdtemp(prefix="reqbody-")
    vars_ = FileVariables(os.path.join(root, "config"))
    ctl = SpecController(spec, vars_, FsObjectStore(os.path.join(root, "objects")), wall=lambda: 1_757_500_000.0)
    ctl.create({"name": "a"})
    return vars_, Served(SpecConsole(ctl, wall=lambda: 1_757_500_000.0))


def test_every_body_value_of_the_shared_table_is_written_into_the_row_as_the_table_says():
    """Each row is filed through the door — the body's bytes as `raw` says them, so `5.0` arrives as `5.0` — and the
    row's field is read back: `written` is its text; `(absent)` — no field; `(refused)` — 400, nothing written."""
    if not os.path.exists(TABLE):
        print("  no testdata/requests_body.tsv: nothing to read")
        return
    vars_, served = _family()
    wrong, n = [], 0
    with served as call:
        for i, (raw, written, _) in _rows():
            n += 1
            rid = f"r{i}"
            st, out = call("POST", "/requests", raw=f'{{"unit": "jar/a", "v": {raw}}}'.encode(), key=rid)
            row = vars_.get(f"jar/requests/{rid}")[0]
            if written == REFUSED:
                if st != 400 or row is not None:
                    wrong.append(f"line {i}: {raw} is not refused: {st} {out}")
                continue
            if st != 202 or row is None:
                wrong.append(f"line {i}: {raw} is refused: {st} {out}")
                continue
            got = row.get("v", ABSENT) if written == ABSENT else row.get("v")
            if (written == ABSENT and "v" in row) or (written != ABSENT and got != written):
                wrong.append(f"line {i}: {raw}\n    written {row.get('v', ABSENT)!r}\n    the table: {written!r}")
    assert not wrong, f"{len(wrong)} rows of {os.path.basename(TABLE)} go another way:\n  " + "\n  ".join(wrong)
    assert n >= 20, f"the table is too short: {n} rows"


def test_a_request_is_named_by_its_fields_text_and_an_int_of_its_key_in_exactly_its_digits():
    """The spec's `key` fills a field in as the row writes it (`{flag}` of `true` is `true`, not Python's `True`), and
    `{n:int}` in exactly the digits the body gave (through a float, 12345678901234567890 was …7168); a `null` fills
    nothing in — 400, as a field the body does not have."""
    import tempfile

    from tests.conftest import Served
    from w2cplatform import catalog
    from w2cplatform.console import SpecConsole
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.spec import SpecController, SubsystemSpec
    from w2cplatform.variables import FileVariables
    spec = SubsystemSpec.from_dict({
        "name": "urn", "unit": {"rows": "urns", "id": "name", "fields": {"name": {"type": "string"}}},
        "placement": {"capacity": {"from": "capacity", "default": 4}},
        "requests": {"key": "{unit}-{flag}-{n:int}", "valid_for": 30, "most_valid": 600}})
    catalog.register(spec)
    root = tempfile.mkdtemp(prefix="reqkey-")
    ctl = SpecController(spec, FileVariables(os.path.join(root, "config")), FsObjectStore(os.path.join(root, "objects")),
                         wall=lambda: 1_757_500_000.0)
    ctl.create({"name": "a"})
    with Served(SpecConsole(ctl, wall=lambda: 1_757_500_000.0)) as call:
        st, out = call("POST", "/requests", raw=b'{"unit": "urn/a", "flag": true, "n": 12345678901234567890}')
        assert st == 202 and out["queued"]["id"] == "a-true-12345678901234567890", out
        st, out = call("POST", "/requests", raw=b'{"unit": "urn/a", "flag": null, "n": 1}')
        assert (st, out["error"]) == (400, "bad id"), out


def test_the_shared_table_is_the_products_byte_for_byte_when_the_product_keeps_one():
    """When the product's committed `main` keeps the table (`testdata/requests_body.tsv`), the course's is a copy of it:
    the same bytes. Until then the course's own seed stands (`productdir.py`: a working tree is not the product's)."""
    theirs = product_file("testdata/requests_body.tsv")
    if theirs is None:
        print("  the product's main keeps no testdata/requests_body.tsv: the course's seed stands")
        return
    with open(TABLE, "rb") as b:
        assert theirs == b.read(), f"{TABLE} is not the product's testdata/requests_body.tsv byte for byte — copy it"


def test_a_json_value_in_a_row_has_one_text_compact_sorted_and_its_numbers_by_the_rule():
    """`canonical_json`: keys sorted, no space, UTF-8 as it is, `<&>/` and U+2028 unescaped, `\\b \\f` short; numbers
    — inside a map or a list too — whole in integer digits (an integer exactly, `-0` too), else the shortest decimal,
    never an exponent; `NaN` and the infinities are no JSON. The product's own case (`canonjson_test.go`), the same
    text from the same bytes."""
    from w2cplatform.canonical import canonical_json, field_text, number_text, parse_json
    raw = ('{"b": 1, "a": "<&>", "c": [1.50, 1e3, 12345678901234567890, 0.0000001, -0], '
           '"d": " ", "e": "\\b\\f\\n\\u0001", "f": {"z": null, "y": true}}')
    assert canonical_json(parse_json(raw)) == ('{"a":"<&>","b":1,"c":[1.5,1000,12345678901234567890,0.0000001,-0],'
                                               '"d":" ","e":"\\b\\f\\n\\u0001","f":{"y":true,"z":null}}')
    assert [number_text(x) for x in (5.0, 1000.0, 1e-7, 1.5, 1e22, -0.0, 10 ** 30)] == \
        ["5", "1000", "0.0000001", "1.5", "10000000000000000000000", "-0", str(10 ** 30)]
    assert canonical_json((1, "é/")) == '[1,"é/"]' and json.loads(canonical_json({"é": [0.1]})) == {"é": [0.1]}
    assert [field_text(v) for v in ("x", True, None, 2.0, {"b": 1, "a": 0})] == ["x", "true", None, "2", '{"a":0,"b":1}']
    for bad in ("NaN", "Infinity", "-Infinity", "1e999", "{", "[1,]"):
        try:
            parse_json(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad} read as JSON")
    assert canonical_json({2: "b", 10: "a", True: 0}) == '{"10":"a","2":"b","true":0}'   # keys are text, sorted as text
    for bad in (float("nan"), float("inf"), {(1,): 2}, {"s": {1, 2}}):
        try:
            canonical_json(bad)
        except (ValueError, TypeError):
            continue
        raise AssertionError(f"{bad!r} written as JSON")


def test_a_json_field_is_written_in_the_canonical_form_from_a_shape_or_from_text_and_text_not_json_is_refused():
    """A field of type `json` (`Field.to_item`, the write's check): the same value is the same row, given as a shape or
    as text — sorted keys, `1.5` for `1.50`, a big integer in its digits — and read back with them; a string that does
    not parse as JSON is refused, not stored as typed (the architect, 2026-10-05)."""
    import tempfile

    from w2cplatform.objects import FsObjectStore
    from w2cplatform.spec import Field, Refused, SpecController, SubsystemSpec
    from w2cplatform.variables import FileVariables
    f = Field("rule", "json")
    shaped = f.to_item({"b": 12345678901234567890, "a": "<"})
    assert shaped == '{"a":"<","b":12345678901234567890}' and f.to_item('{"b": 12345678901234567890, "a": "<"}') == shaped
    assert f.to_item('{"b": 1.50, "a": [ 1 ]}') == '{"a":[1],"b":1.5}'
    assert f.parse('{"n": 12345678901234567890}') == {"n": 12345678901234567890}
    spec = SubsystemSpec.from_dict({"name": "deck", "unit": {"rows": "decks", "id": "name", "fields": {
        "name": {"type": "string"}, "rule": {"type": "json"}}}, "placement": {"capacity": {"from": "capacity", "default": 4}}})
    root = tempfile.mkdtemp(prefix="jsonfield-")
    vars_ = FileVariables(os.path.join(root, "config"))
    ctl = SpecController(spec, vars_, FsObjectStore(os.path.join(root, "objects")), wall=lambda: 1_757_500_000.0)
    ctl.create({"name": "a", "rule": '{"when": [{"in": 2.0}], "at": 1e-7}'})
    assert vars_.get("deck/decks/a")[0]["rule"] == '{"at":0.0000001,"when":[{"in":2}]}'
    for bad in ("not json", "{'a': 1}", "NaN", '{"a": Infinity}'):
        try:
            ctl.create({"name": "b", "rule": bad})
        except Refused as e:
            assert "rule is not JSON" in str(e), e
            continue
        raise AssertionError(f"{bad!r} stored in a json field")
    assert vars_.get("deck/decks/b")[0] is None
    # THE CEILING IS THE BYTES OF THE TEXT STORED (`JSON_CEILING`, «Паритет», 2026-10-05): `{"s":"ж"×2000}` is 2007
    # characters and 4008 bytes — the course took it, the product refused it. 4000 bytes of canonical UTF-8 are taken,
    # 4001 refused; spaces the canonical text drops are not counted.
    from w2cplatform.spec import JSON_CEILING
    assert JSON_CEILING == 4000
    for n, (value, taken) in enumerate(((("ж" * 1996), True), ("a" + "ж" * 1996, False), ("ж" * 2000, False))):
        rule = {"s": value}
        assert len(json.dumps(rule, ensure_ascii=False, separators=(",", ":")).encode()) == (4000, 4001, 4008)[n]
        try:
            ctl.create({"name": f"c{n}", "rule": rule})
            assert taken, (n, "taken")
        except Refused as e:
            assert not taken and f"{(4000, 4001, 4008)[n]} bytes of JSON" in str(e), (n, e)
    ctl.create({"name": "spaced", "rule": '{"s":   ' + " " * 100 + '"' + "a" * 3992 + '"}'})   # 4100 typed, 4000 stored
    assert len(vars_.get("deck/decks/spaced")[0]["rule"]) == 4000
