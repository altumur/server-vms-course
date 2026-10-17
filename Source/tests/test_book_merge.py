"""ADR-0074 collection contract, using only testsub and testsub2; no subsystem runtime imports."""

from tests.frozen_data import frozen_testdata
import copy
import itertools
import json
from pathlib import Path

import yaml

from w2cplatform.spec import SubsystemSpec
from w2cplatform.domain.bookmerge import collect


def spec(sub="testsub", **overrides):
    raw = yaml.safe_load((frozen_testdata() / f"{sub}.subsystem.yaml").read_text())
    rule = {"from": f"{sub}/counts/", "key": "ref", "pick": "all", "to": "to"}
    rule.update(overrides)
    raw["domain"]["books"] = {"counts": rule}
    # This test installs a different book set; names attached to the removed
    # fixture books do not belong to this synthetic collection contract.
    raw["domain"].pop("names", None)
    return SubsystemSpec.from_dict(raw)


def rule(**kw):
    return spec(**kw).domain.merged["counts"]


def row(**overrides):
    value = {"ref": "r1", "to": "b", "n": 7}
    value.update(overrides)
    return json.dumps(value)


def report(value=None, writer="w1", sub="testsub"):
    return {f"{sub}/counts/{writer}": {"i1": row() if value is None else value}}


def test_loader_keeps_collection_rules_and_shown_fields_for_both_test_subsystems():
    for sub in ("testsub", "testsub2"):
        s = spec(sub, show=["n"])
        r = s.domain.merged["counts"]
        assert (r.source, r.key, r.pick, r.to) == (f"{sub}/counts/", "ref", "all", "to")
        assert s.domain.show["counts"] == ("n",)
        assert spec(sub, **{"from": f"{sub}/counts"}).domain.merged["counts"].source == f"{sub}/counts"


def test_loader_refuses_partial_rules_unknown_operators_and_foreign_or_unsafe_paths():
    base = yaml.safe_load((frozen_testdata() / 'testsub.subsystem.yaml').read_text())
    good = {"from": "testsub/counts/", "key": "ref", "pick": "unique", "to": "to"}
    invalid = [{k: v for k, v in good.items() if k != omitted} for omitted in good]
    for key, values in {
        "from": (None, True, [], "", "testsub/", "testsub//counts", "testsub/counts//", "testsub/../counts",
                 "testsub/./counts", "other/counts", "domain/testsub/counts", "https://host/row", "testsub/*"),
        "key": (None, True, [], "", "nested.ref", "token_secret", "ref\n"),
        "pick": (None, True, [], {}, "", "latest", "UNIQUE"),
        "to": (None, True, [], "", "nested.to", "token_secret"),
    }.items():
        invalid.extend({**good, key: value} for value in values)
    invalid.append({**good, "hook": "no"})
    for bad in invalid:
        raw = copy.deepcopy(base)
        raw["domain"]["books"] = {"counts": bad}
        try:
            SubsystemSpec.from_dict(raw)
        except ValueError as e:
            assert "domain.books.counts" in str(e)
        else:
            raise AssertionError(f"accepted invalid rule: {bad}")


def test_carried_books_stay_separate_from_collected_books():
    raw = yaml.safe_load((frozen_testdata() / 'testsub.subsystem.yaml').read_text())
    assert SubsystemSpec.from_dict(raw).domain.merged == {}
    raw["domain"]["books"] = ["counts"]
    assert SubsystemSpec.from_dict(raw).domain.merged == {}


def test_collection_is_order_independent_and_does_not_broadcast_payloads():
    reports = {"a": report(row(to=["b", "b"])), "b": report(row(n=8, to="a"), writer="w2"), "c": {}}
    original = copy.deepcopy(reports)
    expected = None
    for order in itertools.permutations(reports):
        result = collect(rule(), {m: reports[m] for m in order}, reversed(order))
        if expected is None:
            expected = result
        assert result == expected
    assert reports == original
    assert json.loads(expected.rows["b"]["r1"])["entries"] == [
        {"member": "a", "item": "w1/i1", "value": json.loads(row(to=["b", "b"]))}]
    assert json.loads(expected.rows["a"]["r1"])["entries"][0]["member"] == "b"
    assert expected.rows["c"] == {"": '{"missing":[]}'}


def test_missing_is_present_even_when_empty_and_lost_members_do_not_hold_the_book():
    reports = {"a": report(), "b": {}, "c": None}
    result = collect(rule(), reports, ["a", "b", "c"])
    assert json.loads(result.rows["b"]["r1"])["missing"] == ["c"]
    assert json.loads(result.rows["a"][""]) == {"missing": ["c"]}
    result = collect(rule(), reports, ["a", "b", "c"], lost=["c"])
    assert json.loads(result.rows["b"]["r1"])["missing"] == []
    assert collect(rule(), {"a": {}}, ["a"]).rows == {"a": {"": '{"missing":[]}'}}


def test_unknown_senders_are_ignored_and_unknown_destinations_are_not_partially_delivered():
    result = collect(rule(), {"outsider": report(), "a": report(row(to=["b", "outsider"])), "b": {}}, ["a", "b"])
    assert all(set(items) == {""} for items in result.rows.values())
    assert result.diagnostics == (("a", "w1/i1", "r1", "unknown recipient"),)


def test_unique_conflicts_are_global_even_with_disjoint_destinations():
    result = collect(rule(pick="unique"), {"a": report(), "b": report(row(to="a"))}, ["a", "b"])
    assert all(set(items) == {""} for items in result.rows.values())
    assert len(result.diagnostics) == 2
    assert all(d[2] == "r1" and d[3] == "conflicting key" for d in result.diagnostics)


def test_one_invalid_element_discards_the_members_whole_contribution_without_exposing_values():
    for broken in ('{', '[]', '{"ref":""}', row(ref=12), row(to=True),
                   '{"ref":"r1","ref":"r2","to":"b"}', row(n=float("nan")),
                   '{"ref":"r1","to":"b","n":1e999}', row(ref="\ud800")):
        source = report()
        source["testsub/counts/w1"]["i2"] = broken
        got = collect(rule(), {"a": source, "b": {}}, ["a", "b"])
        assert got.rows["b"] == {"": '{"missing":["a"]}'}
        assert got.diagnostics == (("a", "", "", "invalid input"),)


def test_repeated_unique_key_within_member_discards_other_keys_too():
    source = report()
    source["testsub/counts/w2"] = {"i2": row(), "i3": row(ref="r2")}
    got = collect(rule(pick="unique"), {"a": source, "b": {}}, ["a", "b"])
    assert got.rows["b"] == {"": '{"missing":["a"]}'}


def test_single_row_and_family_inputs_do_not_pick_up_neighbours():
    for sub in ("testsub", "testsub2"):
        s = spec(sub, **{"from": f"{sub}/counts"})
        data = {f"{sub}/counts": {"i1": row()}, f"{sub}/counts-extra": {"bad": "{"}}
        got = collect(s.domain.merged["counts"], {"a": data, "b": {}}, ["a", "b"])
        assert json.loads(got.rows["b"]["r1"])["entries"][0]["item"] == "i1"
        got = collect(spec(sub).domain.merged["counts"], {"a": report(sub=sub), "b": {}}, ["a", "b"])
        assert json.loads(got.rows["b"]["r1"])["entries"][0]["item"] == "w1/i1"


def test_withdrawal_and_repeated_snapshot_do_not_leave_old_entries():
    reports = {"a": report(), "b": {}}
    first = collect(rule(), reports, ["a", "b"])
    assert first == collect(rule(), reports, ["a", "b"])
    reports["a"] = {}
    assert collect(rule(), reports, ["a", "b"]).rows["b"] == {"": '{"missing":[]}'}
    # Admission is independent of a stale copy of the sender's report.
    assert collect(rule(), {"a": report(), "b": {}}, ["b"]).rows["b"] == {"": '{"missing":[]}'}


def test_direct_fields_are_used_without_subsystem_names_or_nested_key_interpretation():
    got = collect(rule(key="code", to="dest"), {"a": report(row(code="r2", dest="b")), "b": {}}, ["a", "b"])
    assert "r2" in got.rows["b"] and "r1" not in got.rows["b"]


def test_malformed_family_or_row_does_not_become_a_successful_empty_report():
    for bad in ({"testsub/counts/": {}}, {"testsub/counts/w/extra": {}},
                {"testsub/counts/w": None}, {"testsub/counts/w": {"": row()}},
                {"testsub/counts/w": {"x": {"ref": "r1"}}}):
        got = collect(rule(), {"a": bad, "b": {}}, ["a", "b"])
        assert got.rows["b"] == {"": '{"missing":["a"]}'}


def test_all_orders_writers_and_keeps_payloads_opaque_for_the_delivery_boundary():
    payload = row(member="forged", password_secret="sealed-test-value")
    source = report(payload, writer="w2")
    source.update(report(payload, writer="w1"))
    got = collect(rule(), {"a": source, "b": {}}, ["a", "b"])
    entries = json.loads(got.rows["b"]["r1"])["entries"]
    assert [e["item"] for e in entries] == ["w1/i1", "w2/i1"]
    assert all(e["member"] == "a" and e["value"] == json.loads(payload) for e in entries)
    assert "sealed-test-value" not in str(got.diagnostics) + str(got.rows["a"])
