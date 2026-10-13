"""Worker readers of approved envelopes; explicit placement, no flat book fallback."""
import itertools
import json
from vms import recording_books as books
from w2cplatform.domain.bookmerge import collect
from w2cplatform.spec import BookMerge


def fact(member, recording, **fields):
    return {"member": member, "item": "r1/" + recording,
            "value": {"ref": "cam", "recording": recording, "enabled": True, "running": True, "role": "primary", "to": ["camera", "main"], **fields}}


def row(entries, missing=()):
    return {"": json.dumps({"missing": list(missing)}),
            "cam": json.dumps({"entries": entries, "missing": list(missing)})}


def refused(fn):
    try:
        fn()
    except books.Unconfirmed as e:
        assert "synthetic-hidden-payload" not in str(e)
    else:
        raise AssertionError("unconfirmed book was accepted")


def test_primary_is_the_placed_recording_in_every_entry_order_with_two_reserves():
    entries = [fact("a-reserve", "b1", role="backup"), fact("z-main", "main", running=False), fact("b-reserve", "b2", role="backup")]
    for order in itertools.permutations(entries):
        items = row(list(order))
        chosen = books.primary(items, "cam", "z-main")
        assert chosen.member == "z-main" and chosen.value["running"] is False
        assert [(e.member, e.value["recording"]) for e in books.copies(items, "cam", ["b-reserve", "a-reserve"])] == [("a-reserve", "b1"), ("b-reserve", "b2")]
        assert books.primary(items, "cam", "absent-main") is None


def test_missing_primary_does_not_choose_a_running_reserve_and_absent_key_is_not_running():
    items = row([fact("main", "r"), fact("reserve", "b")], missing=["main"])
    assert books.primary(items, "cam", "main") is None
    assert books.primary(items, "cam", "reserve").value["running"] is True
    assert books.primary({"": items[""]}, "cam", "main") is None
    refused(lambda: books.primary(items, "cam", ""))


def test_source_requires_one_complete_observation_and_keeps_authenticated_origin():
    item = {"member": "camera", "item": "w1/c1", "value": {"ref": "cam", "to": ["main"], "live_url": "rtsp://camera/live", "server": "camera", "as_of": 10}}
    items = row([item])
    seen = books.source(items, "cam")
    assert (seen.member, seen.item, seen.value["live_url"]) == ("camera", "w1/c1", "rtsp://camera/live")
    assert items == row([item])
    refused(lambda: books.source(row([item], missing=["room"]), "cam"))
    refused(lambda: books.source(row([]), "cam"))
    refused(lambda: books.source(row([item, {**item, "member": "other"}]), "cam"))


def test_old_flat_books_torn_markers_and_malformed_values_are_refused_without_payloads():
    good = row([fact("main", "r")])
    cases = [{"cam": json.dumps({"recorded_by": "main", "recording": "r"})},
             {"": "not-json", "cam": good["cam"]}, {"cam": good["cam"]},
             {"": json.dumps({"missing": ["room"]}), "cam": good["cam"]}]
    for entry in [None, [], {"member": "main", "item": "r", "value": {}},
                  {**fact("main", "r"), "value": {"ref": "other"}},
                  {**fact("main", "r"), "member": ""}, {**fact("main", "r"), "item": ""}]:
        cases.append(row([entry]))
    cases.append(row([fact("main", "r"), fact("main", "r")]))
    cases.append({"": '{"missing":[],"missing":[]}', "cam": good["cam"]})
    cases.append({"": good[""], "cam": '{"entries":[],"missing":[],"hidden":"synthetic-hidden-payload","n":NaN}'})
    cases.append({"": good[""], "cam": '{"entries":[],"missing":[],"n":1e400}'})
    for items in cases:
        refused(lambda: books.read(items, "cam"))


def test_recorder_state_is_boolean_and_duplicate_recording_origins_do_not_pick_a_winner():
    for field in ("running", "enabled"):
        for bad in (None, 1, "true", [], {}):
            refused(lambda: books.primary(row([fact("main", "r", **{field: bad})]), "cam", "main"))
    a, b = fact("main", "r"), fact("main", "r")
    b["item"] = "another-writer/r"
    refused(lambda: books.primary(row([a, b]), "cam", "main"))


def test_collector_delivers_facts_before_a_stream_runs_and_a_stranger_gets_no_addresses():
    members = ["camera", "main", "reserve1", "reserve2", "stranger"]
    reports = {m: {} for m in members}
    for member, recording in (("main", "r"), ("reserve1", "b1"), ("reserve2", "b2")):
        value = fact(member, recording, running=False)["value"]
        value.update(to=members[:-1], push=True, ingest=["http://" + member + "/ingest"])
        reports[member] = {"rec/primaries/w1": {recording: json.dumps(value)}}
    rule = BookMerge(source="rec/primaries/", key="ref", pick="all", to="to")
    collected = collect(rule, reports, members)
    for member in members[:-1]:
        chosen = books.primary(collected.rows[member], "cam", "main")
        assert not chosen.value["running"] and "starting" not in chosen.value
        assert "token_secret" not in json.dumps(collected.rows[member])
    assert set(collected.rows["stranger"]) == {""}
    reports["main"] = {}
    assert books.primary(collect(rule, reports, members).rows["camera"], "cam", "main") is None


def test_primary_card_and_backup_on_one_member_are_not_order_based():
    entries = [fact("main", "card", role="card"), fact("main", "reserve", role="backup"), fact("main", "main")]
    for order in itertools.permutations(entries):
        assert books.primary(row(list(order)), "cam", "main").value["recording"] == "main"
        assert books.copies(row(list(order)), "cam", ["main"])[0].value["recording"] == "reserve"
    for role in (None, "unknown", 1):
        refused(lambda: books.primary(row([fact("main", "main", role=role)]), "cam", "main"))
    assert books.primary(row([fact("main", "reserve", role="backup")]), "cam", "main") is None
