"""C2: ordinary workers publish facts and read assigned observations, no remote writes."""
import itertools
import json

from tests.vmsconftest import Box, cam, recorder
from vms import recording_books as books
from vms import recording_publication as publication
from vms.config import REC_SPEC, SPEC
from vms.worker import VmsWorker
from w2cplatform.domain.bookmerge import collect
from w2cplatform.variables import GuardFailed


def placement(box, own, *, primary="main", origin="camera", copies=("reserve1", "reserve2"), rev=1):
    box.vars.put("domain/member", {"cluster": own})
    box.vars.put("domain/placed/rec/serial", {"cluster": primary, "origin": origin, "copies": json.dumps(list(copies)),
                                             "reason": "operator", "at": str(box.wall()), "rev": str(rev)})


def source_row(box, *, push=False, address="rtsp://camera/live", missing=()):
    value = {"ref": "serial", "to": ["main", "reserve1", "reserve2"], "live_url": address,
             "server": "camera", "as_of": box.wall(), **({"push": True} if push else {})}
    row = {"": json.dumps({"missing": list(missing)}),
           "serial": json.dumps({"entries": [{"member": "camera", "item": "w1/1", "value": value}], "missing": list(missing)})}
    box.vars.put("domain/cam/sources", row)
    return row


def primary_row(box, entries, missing=()):
    row = {"": json.dumps({"missing": list(missing)}),
           "serial": json.dumps({"entries": entries, "missing": list(missing)})}
    box.vars.put("domain/rec/primaries", row)
    return row


def fact(member, recording, role="primary", **fields):
    return {"member": member, "item": "r1/" + recording,
            "value": {"ref": "serial", "recording": recording, "role": role, "enabled": True,
                      "running": True, "to": ["camera", "main", "reserve1", "reserve2"], **fields}}


def test_camera_heartbeat_publishes_only_its_origin_and_replaced_writer_is_fenced():
    box = Box()
    placement(box, "camera")
    worker = VmsWorker("w-1", box.vars, box.objects, clock=box.clock, wall=box.wall, env={})
    worker.rows = [cam(1, ref="serial"), cam(2, ref="not-placed")]
    worker.heartbeat_once()
    path = "cam/sources/w-1"
    rows = box.vars.get(path)[0]
    value = json.loads(rows["1"])
    assert set(rows) == {"1"} and set(value) == {"ref", "to", "live_url", "server", "as_of"}
    assert value["to"] == ["main", "reserve1", "reserve2"]
    reports = {"camera": {path: rows}, "main": {}, "reserve1": {}, "reserve2": {}, "stranger": {}}
    got = collect(SPEC.domain.merged["sources"], reports, list(reports))
    assert books.source(got.rows["main"], "serial").member == "camera"
    assert set(got.rows["stranger"]) == {""}
    successor = VmsWorker("w-1", box.vars, box.objects, clock=box.clock, wall=box.wall, env={})
    assert box.vars.get(path)[0] is None
    assert publication.publish(worker, "sources", rows) is False
    assert box.vars.get(path)[0] is None
    placement(box, "stranger")
    successor.rows = worker.rows
    successor.heartbeat_once()
    assert box.vars.get(path)[0] == {}


def test_recorder_heartbeat_publishes_enabled_and_running_false_without_tokens_or_nulls():
    box = Box()
    placement(box, "main")
    source_row(box, push=True)
    rec = recorder(box)
    rec.rows = [{"id": "recording", "cam": "ref:serial", "enabled": False, "revision": 1}]
    rec.ingest_url, rec.archive_url = "http://main/ingest", "http://main/archive"
    rec.heartbeat_once()
    rows = box.vars.get("rec/primaries/r-1")[0]
    value = json.loads(rows["recording"])
    assert value["role"] == "primary" and value["enabled"] is False and value["running"] is False
    assert value["ingest"] == ["http://main/ingest"] and value["push"] is True
    assert value["to"] == ["camera", "main", "reserve1", "reserve2"]
    assert value["peer_url"] == "http://main/archive"
    assert not ({"token", "token_secret", "until", "starting", "urls"} & value.keys())
    assert all(v is not None for v in value.values())
    rec.writing_allowed = False
    rec.heartbeat_once()  # a fenced worker still pulses; the control row remains unchanged
    assert box.vars.get("rec/primaries/r-1")[0] == rows


def test_recorder_failure_memory_is_local_and_resets_on_source_or_assignment_change():
    box = Box()
    placement(box, "main")
    source_row(box)
    rec = recorder(box)
    rec.ingest_url = "http://main/ingest"
    rec.rows = [{"id": "recording", "cam": "ref:serial", "enabled": True, "revision": 1}]
    status = [{"id": "recording", "phase": "failed", "source_unreachable": True}]
    assert json.loads(publication.primaries(rec, status)["recording"])["push"] is True
    assert json.loads(publication.primaries(rec, [{"id": "recording", "phase": "pending"}])["recording"])["push"] is True
    assert not box.vars.list("domain/cam/roads")
    placement(box, "main", rev=2)
    rec._look()._got.clear()
    assert "push" not in json.loads(publication.primaries(rec, [{"id": "recording", "phase": "pending"}])["recording"])
    assert rec._source_of_ref("ref:serial")[1] == "rtsp://camera/live"
    placement(box, "stranger")
    rec._look()._got.clear()
    assert rec._source_of_ref("ref:serial") is None


def test_recorder_primary_selection_grace_and_backfill_use_the_whole_assigned_book():
    box = Box()
    placement(box, "camera")
    rec = recorder(box)
    rec.card_range = lambda *_: []
    box.objects.put("domain/seen", json.dumps({"ts": box.wall()}).encode())
    row = {"id": "card", "cam": "ref:serial"}
    coverage = {"from": 1, "to": 2, "fragments": 1}
    entries = [fact("main", "primary", running=False, peer_url="http://main/archive", coverage=coverage),
               fact("reserve1", "b1", "backup", coverage=coverage, peer_url="http://r1/archive"),
               fact("reserve2", "b2", "backup", coverage=coverage, peer_url="http://r2/archive"),
               fact("stranger", "extra", "backup", coverage=coverage, peer_url="http://stranger/archive")]
    for order in itertools.permutations(entries[:3]):
        primary_row(box, list(order) + entries[3:])
        rec._look()._got.clear()
        assert rec.carried_word(row, box.wall())[0] is True
        peers = rec.domain_archive_sources(row)
        assert {p["recorder"] for p in peers} == {"main", "reserve1", "reserve2"}
    primary_row(box, entries[1:])
    rec._look()._got.clear()
    # Losing the report cannot interrupt the reserve that already covers.
    assert rec.carried_word(row, box.wall())[0] is True
    # A new assignment starts a fresh grace instead of inheriting that decision.
    placement(box, "camera", rev=2)
    rec._look()._got.clear()
    assert rec.carried_word(row, box.wall())[0] is False
    box.wall.advance(rec.START_GRACE)
    assert rec.carried_word(row, box.wall())[0] is True
    primary_row(box, [fact("main", "primary", enabled=False)])
    rec._look()._got.clear()
    assert rec.carried_word(row, box.wall())[0] is False


def test_pull_camera_that_polls_gets_an_ingest_address_without_requesting_push():
    box = Box()
    placement(box, "main")
    rows = source_row(box)
    value = json.loads(rows["serial"])
    value["entries"][0]["value"]["polls"] = True
    rows["serial"] = json.dumps(value)
    box.vars.put("domain/cam/sources", rows)
    rec = recorder(box)
    rec.rows = [{"id": "recording", "cam": "ref:serial", "enabled": True, "revision": 1}]
    rec.ingest_url = "http://main/ingest"
    rec.heartbeat_once()
    fact = json.loads(box.vars.get("rec/primaries/r-1")[0]["recording"])
    assert fact["ingest"] == ["http://main/ingest"] and "push" not in fact


def test_centre_derives_a_receiver_without_receiving_the_camera_source_or_credentials():
    box = Box()
    placement(box, "centre", primary="relay", copies=())
    box.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 1, "centre": "centre", "star": [], "via": {}})})
    rec = recorder(box)
    assert box.vars.get("domain/cam/sources")[0] is None
    assert rec.source("ref:serial") == ("centre", "ingest://centre/serial")
    box.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 2, "centre": "other", "star": [], "via": {}})})
    assert rec.source("ref:serial") is None


def test_primary_book_carries_applied_recording_settings_not_pending_edits():
    box = Box()
    placement(box, "main")
    source_row(box)
    rec = recorder(box)
    rec.rows = [{"id": "recording", "cam": "ref:serial", "enabled": True,
                 "retention_days": 17, "when": "offline", "home": "volume-applied"}]
    box.vars.put("domain/pending/main", {"unapplied": json.dumps({"retention_days": 90})})
    status = [{"id": "recording", "phase": "running",
               "coverage": {"from": 10, "to": 20, "fragments": 2}}]
    value = json.loads(publication.primaries(rec, status)["recording"])
    assert value["retention_days"] == 17
    assert value["when"] == "offline" and value["home"] == "volume-applied"
    assert value["coverage"] == {"from": 10, "to": 20, "fragments": 2}
    assert value["role"] == "primary" and value["running"] is True
    for field, bad in (("retention_days", True), ("retention_days", 0),
                       ("retention_days", 1.5), ("when", "unknown"), ("home", {})):
        try:
            books.recording_value({**value, field: bad})
        except books.Unconfirmed:
            pass
        else:
            raise AssertionError(field)
