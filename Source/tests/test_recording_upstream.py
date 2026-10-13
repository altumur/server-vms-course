"""C3/C3b: ordinary centre publisher, star audience and independently scoped readers."""
import json

from tests.vmsconftest import Box, recorder
from tests.test_recording_publication import fact, placement, primary_row, source_row
from vms.recording_upstream import observation
from w2cplatform.domain.bookmerge import collect
from vms.config import REC_SPEC


def test_centre_publishes_to_recording_cluster_only_and_one_live_recorder_is_the_publisher():
    box = Box()
    placement(box, "centre", primary="relay")
    box.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 1, "centre": "centre", "star": [], "via": {}})})
    first, second = recorder(box, "r-1"), recorder(box, "r-2")
    first.host_ingest("centre", "http://centre/a"); second.host_ingest("centre", "http://centre/b")
    first.heartbeat_once(); second.heartbeat_once(); first.heartbeat_once()
    row = box.vars.get("rec/upstream/r-1")[0]
    value = json.loads(row["serial"])
    assert value == {"ref": "serial", "to": ["relay"], "urls": ["http://centre/a", "http://centre/b"]}
    assert box.vars.get("rec/upstream/r-2")[0] == {}
    reports = {"centre": {"rec/upstream/r-1": row}, "relay": {}, "camera": {}, "reserve1": {}}
    got = collect(REC_SPEC.domain.merged["upstream"], reports, list(reports))
    assert "serial" in got.rows["relay"] and set(got.rows["camera"]) == {""} and set(got.rows["reserve1"]) == {""}
    box.vars.put("domain/rec/upstream", got.rows["relay"])
    box.vars.put("domain/member", {"cluster": "relay"})
    assert observation(box.vars, "relay", "serial")[0].member == "centre"


def test_star_primary_announces_centre_ingest_and_receiver_member_without_becoming_a_copy():
    box = Box()
    placement(box, "main")
    source_row(box, push=True)
    box.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 1, "centre": "centre", "star": ["main"], "via": {}})})
    value = {"ref": "serial", "to": ["main"], "urls": ["http://centre/ingest"]}
    box.vars.put("domain/rec/upstream", {"": json.dumps({"missing": []}), "serial": json.dumps({
        "entries": [{"member": "centre", "item": "r-1/serial", "value": value}], "missing": []})})
    rec = recorder(box)
    rec.rows = [{"id": "recording", "cam": "ref:serial", "enabled": True, "revision": 1}]
    rec.ingest_url = "http://main/ingest"
    rec.heartbeat_once()
    got = json.loads(box.vars.get("rec/primaries/r-1")[0]["recording"])
    assert got["ingest"] == ["http://centre/ingest"] and got["ingest_cluster"] == "centre" and got["push"] is True
    assert got["role"] == "primary" and "centre" not in got["to"]


def test_centre_derives_a_receiver_without_receiving_the_camera_source_or_credentials():
    box = Box()
    placement(box, "centre", primary="relay", copies=())
    box.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 1, "centre": "centre", "star": [], "via": {}})})
    rec = recorder(box)
    assert box.vars.get("domain/cam/sources")[0] is None
    assert rec.source("ref:serial") == ("centre", "ingest://centre/serial")
    box.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 2, "centre": "other", "star": [], "via": {}})})
    assert rec.source("ref:serial") is None
