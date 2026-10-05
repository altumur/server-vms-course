"""A body that is no JSON is the same refusal at every door of the platform (the architect with «Паритет», 2026-10-06;
product 5223aba): each reads its body through `canonical.parse_json`, and a body that is not UTF-8, holds a lone
surrogate (JSON's `\\ud800` escape lets one through) or a number past a float64 is 400 with the shared table's `fault`
(`not_json`, `not_number`) beside that door's own words. Here the console's doors and the store's (its write and its
membership); the domain's console, its signer and its token door in `tests/domain/test_body_fault_doors.py`.

And `null` in a field of type `json` (the architect, 2026-10-06, reversed the same day): at the top of a field it is no
field — the default applies, as for a field of any other type and a request's field; inside a document it is a value
(`{"a": null}` is stored as `{"a":null}`)."""
from __future__ import annotations

import os
import tempfile

# The three bodies of the shared table that `json.loads` reads and JSON does not: bytes that are no UTF-8, a lone
# surrogate, a number no float64 holds — and the word each is refused with.
BAD = [(b'{"a": "\xff"}', "not_json"), (b'{"a": "\\ud800"}', "not_json"), (b'{"a": 1e400}', "not_number")]


def _counters(**field):
    """A subsystem whose unit rows are `counters`, named by `name`, with a field `doc: {type: json, …field}`."""
    from tests.conftest import Served
    from w2cplatform import catalog
    from w2cplatform.console import SpecConsole
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.spec import SpecController, SubsystemSpec
    from w2cplatform.variables import FileVariables
    spec = SubsystemSpec.from_dict({
        "name": "ctr", "unit": {"rows": "counters", "id": "name", "fields": {
            "name": {"type": "string"}, "doc": {"type": "json", **field}}},
        "placement": {"capacity": {"from": "capacity", "default": 4}}})
    catalog.register(spec)
    root = tempfile.mkdtemp(prefix="bodyfault-")
    vars_ = FileVariables(os.path.join(root, "config"))
    ctl = SpecController(spec, vars_, FsObjectStore(os.path.join(root, "objects")), wall=lambda: 1_757_500_000.0)
    return vars_, Served(SpecConsole(ctl, wall=lambda: 1_757_500_000.0))


def test_the_consoles_doors_refuse_a_body_that_is_no_json_with_its_fault():
    """`POST /counters`, `PUT /counters/<id>`, `PUT /policy`: 400 with `fault`, the door's own `detail` and `error` kept,
    nothing written; a body that is JSON and no object is 400 with no `fault` (it read: it is the wrong shape)."""
    vars_, served = _counters()
    wrong = []
    with served as call:
        assert call("POST", "/counters", {"name": "c0"})[0] == 201
        for i, (raw, fault) in enumerate(BAD):
            for method, path in (("POST", "/counters"), ("PUT", "/counters/c0"), ("PUT", "/policy")):
                st, out = call(method, path, raw=raw.replace(b'"a"', b'"name": "c9", "a"'), key=f"k{i}{method}{path.replace('/', '-')}")
                if st != 400 or not isinstance(out, dict) or out.get("fault") != fault or not out.get("detail") \
                        or not out.get("error"):
                    wrong.append(f"{method} {path} {raw!r}: {st} {out}")
        st, out = call("POST", "/counters", raw=b"[1]", key="list")
        assert st == 400 and "fault" not in out, out
    assert not wrong, "\n".join(wrong)
    assert vars_.get("ctr/counters/c9")[0] is None and vars_.get("ctr/counters/c0")[0]["name"] == "c0"


def test_the_idempotency_digest_reads_the_body_as_the_door_does():
    """`IdempotencyKeys._said`: what `parse_json` refuses is "not JSON" — `1e400` was read as `inf` and digested as a body."""
    from w2cplatform.console import IdempotencyKeys
    for raw, _ in BAD:
        assert IdempotencyKeys._said(raw) == b"not JSON", raw
    assert IdempotencyKeys._said(b'{"b": 1, "a": 12345678901234567890}') == b'{"a": 12345678901234567890, "b": 1}'


def test_the_stores_write_door_and_its_membership_door_refuse_a_body_that_is_no_json_with_its_fault():
    """`POST /v1/write` (`storemachine.answer`, the daemon's and a stand's) and `POST /v1/join` / `/v1/leave` (the daemon's):
    400 `badrequest` with `fault`; nothing is submitted. Nested past what JSON reads is `not_json`, never a 500."""
    from w2cplatform.configstore import StoreDaemon
    from w2cplatform.storemachine import ADMIN, Rights, answer

    def submit(cmd):
        raise AssertionError(f"submitted: {cmd}")
    deep = b"[" * 100_000 + b"]" * 100_000
    for raw, fault in BAD + [(deep, "not_json")]:
        code, said = answer("POST", "/v1/write", raw, ADMIN, Rights(), submit)
        assert (code, said.get("kind"), said.get("fault")) == (400, "badrequest", fault), (raw[:20], code, said)
    dm = StoreDaemon(object(), node_id="solo")
    for path in ("/v1/join", "/v1/leave"):
        for raw, fault in BAD + [(deep, "not_json")]:
            code, said = dm.serve("POST", path, raw, ADMIN, 1.0)
            assert (code, said.get("kind"), said.get("fault")) == (400, "badrequest", fault), (path, raw[:20], code, said)
        code, said = dm.serve("POST", path, b'{"id": "bad name"}', ADMIN, 1.0)
        assert code == 400 and "fault" not in said, said            # read, and wrong: the door's words alone


def test_null_at_the_top_of_a_json_field_is_no_field_and_null_inside_a_document_is_a_value():
    """`POST /counters {"name": …, "doc": <body>}` and the row as stored: `null` is no `doc` (the default applies — none
    declared: no field, never the text `null`; one declared: the default's text), absent the same; `{"a": null}`, `{}`,
    `[]`, `0` are the document, canonical. A string is JSON text (`Field.to_item`): `"s"` is no JSON, 400 `not_json`."""
    vars_, served = _counters()
    cases = [("null", None), ("absent", None), ('{"a": null}', '{"a":null}'), ("{}", "{}"), ("[]", "[]"), ("0", "0"),
             ('[null, {"z": null}]', '[null,{"z":null}]')]
    wrong = []
    with served as call:
        for i, (body, stored) in enumerate(cases):
            raw = f'{{"name": "c{i}"}}' if body == "absent" else f'{{"name": "c{i}", "doc": {body}}}'
            st, out = call("POST", "/counters", raw=raw.encode())
            row = vars_.get(f"ctr/counters/c{i}")[0]
            if st != 201 or row is None or row.get("doc") != stored or (stored is None and "doc" in row):
                wrong.append(f"{body}: {st} {out}, stored {row}, not {stored!r}")
            elif stored is None and out.get("doc") is not None:
                wrong.append(f"{body}: the reply says doc {out.get('doc')!r}")
        st, out = call("POST", "/counters", raw=b'{"name": "s", "doc": "s"}')
        assert st == 400 and out.get("fault") == "not_json" and vars_.get("ctr/counters/s")[0] is None, (st, out)
    assert not wrong, "\n".join(wrong)
    vars_, served = _counters(default='{"n": 1}')     # JSON text: a map under `default` is keys the loader refuses
    with served as call:
        for i, body in enumerate(("null", "absent")):
            raw = f'{{"name": "d{i}"}}' if body == "absent" else f'{{"name": "d{i}", "doc": {body}}}'
            assert call("POST", "/counters", raw=raw.encode())[0] == 201
            row = vars_.get(f"ctr/counters/d{i}")[0]
            assert row.get("doc") == '{"n":1}', (body, row)              # the default applies: its text, as for absent
