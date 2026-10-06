"""One table of how a body value is written into its row, for the course and the product (`testdata/requests_body.tsv`;
the architect with «Паритет», 2026-10-05/06, ADR 0012): a string as it is, `true`/`false`, a whole number in integer
digits, any other in its shortest decimal, `null` no field at all, a list or a map — and any value of a `json` field — in
the one canonical form of a JSON value in a row (`w2cplatform/canonical.py`, the product's `CanonicalJSON`). The door
wrote `str(v)` — `True`, `None`, `5.0` — and a holder in Go read another value than one in Python. The table is
«Паритет»'s, a copy of the product's byte for byte, in the shared columns `field, body, stored, fault`: `field` is
`request` (the field `v` of a request row, its family's schema `v: {maxLength: 32}`) or `json` (the field `doc` of type
`json` of a table `counters`); `stored` is the row's text, `<absent>` — no field, `<empty>` — the empty string; `fault`
is a word of `fault.tsv`, empty when taken."""
from __future__ import annotations

import json
import os

from tests.productdir import SOURCE, product_file

TABLE = os.path.join(SOURCE, "tests", "testdata", "requests_body.tsv")
ABSENT, EMPTY = "<absent>", "<empty>"
FIELDS = ("request", "json")


def _rows():
    """(line, field, body, stored, fault) of every row; `stored` with `<empty>` read as the empty string."""
    with open(TABLE, encoding="utf-8", newline="") as f:
        for i, line in enumerate(f.read().split("\n"), 1):
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            assert len(cols) == 4 and cols[0] in FIELDS, f"line {i}: a row is field, body, stored, fault: {line!r}"
            field, body, stored, fault = cols
            assert bool(fault) != bool(stored), f"line {i}: a row is stored or refused, one of the two: {line!r}"
            yield i, field, body, "" if stored == EMPTY else stored, fault


def _family():
    """The table's stand: a family of deadlines whose schema says of `v` only `maxLength: 32` (the VMS's arguments say
    as much), one unit; and a table `counters` whose field `doc` is of type `json`."""
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
        "tables": {"counters": {"key": "{name}", "fields": {"name": {"type": "string", "required": True},
                                                            "doc": {"type": "json"}}}},
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
    """Each row is filed through the door — the body's bytes as the table writes them, so `5.0` arrives as `5.0`: a
    `request` row as `v` of `POST /requests`, a `json` row as `doc` of `POST /counters` — and the row's field is read
    back from the store: `stored` is its text, `<absent>` no field; a `fault` is a 400 saying that word, nothing
    written. A `json` row taken is filed a second time with the value the door reads back (`GET /counters/<name>`, as
    a client writes it again): the row is the same, byte for byte."""
    vars_, served = _family()
    wrong, n = [], {"request": 0, "json": 0}
    with served as call:
        for i, field, body, stored, fault in _rows():
            n[field] += 1
            if field == "request":
                key, path, raw = f"jar/requests/r{i}", "/requests", f'{{"unit": "jar/a", "v": {body}}}'
                name = "v"
            else:
                key, path, raw = f"jar/counters/c{i}", "/counters", f'{{"name": "c{i}", "doc": {body}}}'
                name = "doc"
            st, out = call("POST", path, raw=raw.encode(), key=f"r{i}")
            row = vars_.get(key)[0]
            if fault:
                if st != 400 or (out or {}).get("fault") != fault or row is not None:
                    wrong.append(f"line {i}: {field} {body} is not refused {fault}: {st} {out}")
                continue
            if st not in (201, 202) or row is None:
                wrong.append(f"line {i}: {field} {body} is refused: {st} {out}")
                continue
            if (stored == ABSENT) != (name not in row) or (stored != ABSENT and row[name] != stored):
                wrong.append(f"line {i}: {field} {body}\n    stored {row.get(name, ABSENT)!r}\n    the table: {stored!r}")
                continue
            if field == "json":
                st, back = call("GET", f"/counters/c{i}")
                again = {"name": f"c{i}b", **({"doc": back["doc"]} if "doc" in back else {})} if st == 200 else None
                st2, out2 = call("POST", "/counters", raw=json.dumps(again, ensure_ascii=False).encode(), key=f"r{i}b") \
                    if again is not None else (st, back)
                twice = vars_.get(f"jar/counters/c{i}b")[0]
                if st2 != 201 or twice is None or twice.get(name, ABSENT) != row.get(name, ABSENT):
                    wrong.append(f"line {i}: {body} read back and filed again is "
                                 f"{(twice or {}).get(name, ABSENT)!r} ({st2} {out2}), first {row.get(name, ABSENT)!r}")
    assert not wrong, f"{len(wrong)} rows of {os.path.basename(TABLE)} go another way:\n  " + "\n  ".join(wrong)
    assert n["request"] >= 20 and n["json"] >= 10, f"the table is too short: {n}"


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
    assert canonical_json(parse_json(raw)) == ('{"a":"<&>","b":1,"c":[1.5,1000,12345678901234567890,0.0000001,0],'
                                               '"d":" ","e":"\\b\\f\\n\\u0001","f":{"y":true,"z":null}}')
    assert [number_text(x) for x in (5.0, 1000.0, 1e-7, 1.5, 1e22, -0.0, 10 ** 30)] == \
        ["5", "1000", "0.0000001", "1.5", "10000000000000000000000", "0", str(10 ** 30)]
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


def test_a_json_field_is_written_in_the_canonical_form_of_its_value_and_a_string_is_a_document_that_is_a_string():
    """A field of type `json` (`Field.take`, `Field.to_item`): the value is taken as it is given and written in the one
    canonical form — sorted keys, `1.5` for `1.50`, a big integer in its digits — and read back with them. A string is a
    document that is a string, never JSON text read again (the architect with «Паритет», 2026-10-06, (б)): `"s"` is
    written `"s"`, taken again as read it is the same row; reading a text box is the page's work before it sends."""
    import tempfile

    from w2cplatform.objects import FsObjectStore
    from w2cplatform.spec import Field, Refused, SpecController, SubsystemSpec
    from w2cplatform.variables import FileVariables
    f = Field("rule", "json")
    assert f.to_item({"b": 12345678901234567890, "a": "<"}) == '{"a":"<","b":12345678901234567890}'
    assert f.to_item({"b": 1.5, "a": [1]}) == '{"a":[1],"b":1.5}'
    assert f.to_item("s") == '"s"' and f.to_item('"s"') == '"\\"s\\""' and f.take("{oops") == "{oops"
    assert f.parse('{"n": 12345678901234567890}') == {"n": 12345678901234567890}     # a stored item: its text, read
    spec = SubsystemSpec.from_dict({"name": "deck", "unit": {"rows": "decks", "id": "name", "fields": {
        "name": {"type": "string"}, "rule": {"type": "json"}}}, "placement": {"capacity": {"from": "capacity", "default": 4}}})
    root = tempfile.mkdtemp(prefix="jsonfield-")
    vars_ = FileVariables(os.path.join(root, "config"))
    ctl = SpecController(spec, vars_, FsObjectStore(os.path.join(root, "objects")), wall=lambda: 1_757_500_000.0)
    ctl.create({"name": "a", "rule": {"when": [{"in": 2.0}], "at": 1e-7}})
    assert vars_.get("deck/decks/a")[0]["rule"] == '{"at":0.0000001,"when":[{"in":2}]}'
    for n, text in enumerate(("not json", '"s"', "{oops")):                    # strings: documents, written as such
        made = ctl.create({"name": f"s{n}", "rule": text})
        assert vars_.get(f"deck/decks/s{n}")[0]["rule"] == json.dumps(text, ensure_ascii=False)
        ctl.create({"name": f"t{n}", "rule": made["rule"]})                    # taken again as read: one row
        assert vars_.get(f"deck/decks/t{n}")[0]["rule"] == vars_.get(f"deck/decks/s{n}")[0]["rule"]
    for bad in (float("nan"), {"a": float("inf")}):                            # no JSON value: refused, not stored
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


def test_a_refused_body_value_says_its_kind_as_the_shared_table_names_it():
    """`fault` — the table's word for a refusal (the architect with «Паритет», 2026-10-06): `not_json` (`NaN`, a cut
    text, a lone surrogate — JSON's `\\ud800` escape lets one through, and it is no character), `not_number` (`1e400`),
    `too_long` (past `maxLength` as written). A lone surrogate is refused at the body, not let through to the store."""
    vars_, served = _family()
    cases = [("NaN", "not_json"), ('"\\ud800"', "not_json"), ('{"x": "a\\udfffb"}', "not_json"),
             ("1e400", "not_number"), ('{"x": 1e400}', "not_number"), ('"' + "a" * 33 + '"', "too_long")]
    wrong = []
    with served as call:
        for i, (raw, fault) in enumerate(cases):
            st, out = call("POST", "/requests", raw=f'{{"unit": "jar/a", "v": {raw}}}'.encode(), key=f"f{i}")
            if st != 400 or (out or {}).get("fault") != fault or vars_.get(f"jar/requests/f{i}")[0] is not None:
                wrong.append(f"{raw}: {st} {out}, the table says {fault}")
    assert not wrong, "\n".join(wrong)
