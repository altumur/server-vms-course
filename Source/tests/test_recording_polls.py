"""C4 polls: home publication, unique current-holder reads, and fenced worker writes."""
import json
from types import SimpleNamespace

from tests.vmsconftest import Box
from vms.recording_books import Unconfirmed
from vms.recording_polls import POLLS_PATH, confirmed, observation, polls
from w2cplatform.contract import Eyes, Heartbeat
from w2cplatform.domain.bookmerge import collect
from w2cplatform.spec import BookMerge


def holder(box, own="relay", name="holder"):
    box.vars.put("domain/member", {"cluster": own})
    box.vars.put("domain/holder", {"doc": json.dumps({"holder": name, "term": 1})})


def topology(box, *, via=None, centre="centre", key="domain/member-topology", rev=1):
    box.vars.put(key, {"doc": json.dumps({"rev": rev, "centre": centre, "star": [], "via": via or {}})})


def row(*entries, missing=(), ref="serial"):
    return {"": json.dumps({"missing": list(missing)}), ref: json.dumps({
        "entries": list(entries), "missing": list(missing)})}


def camera(ref="serial", name="camera", *, to=("relay", "centre"), **over):
    return {"member": name, "item": "cam-1/"+ref, "value": {
        "ref": ref, "to": list(to), "polls": True, "live_url": "", "server": name,
        "as_of": 1000.0, **over}}


def address(home="relay", *, to=("camera",), **over):
    return {"member": home, "item": "r-1/serial", "value": {
        "ref": "serial", "to": list(to), "urls": ["http://relay/ingest"], **over}}


def heartbeat(box, name="r-1", url="http://relay/ingest", **over):
    value = {"worker": name, "ts": box.wall(), "status": [], "ingest": url, **over}
    box.objects.put("rec/heartbeats/"+name, json.dumps(value).encode())


def fixture(own="relay"):
    box = Box()
    holder(box, own)
    topology(box, via={"camera": "relay"})
    box.vars.put("domain/cam/sources", row(camera()))
    worker = SimpleNamespace(name="r-1", vars=box.vars, objects=box.objects,
                             ingest_url="http://relay/ingest", eyes=Eyes(box.clock, box.wall))
    heartbeat(box)
    return box, worker


def refused(call):
    try:
        call()
    except Unconfirmed:
        return
    raise AssertionError("an incomplete or foreign poll home was accepted")


def test_unassigned_polling_camera_gets_only_its_home_ingest_and_no_book_token():
    box, worker = fixture()
    got = polls(worker, [])
    assert json.loads(got["serial"]) == {
        "ref": "serial", "to": ["camera"], "urls": ["http://relay/ingest"]}
    rule = BookMerge("rec/polls/", "ref", "unique", "to")
    merged = collect(rule, {"relay": {"rec/polls/r-1": got}, "camera": {}, "stranger": {}},
                     ["relay", "camera", "stranger"])
    assert set(merged.rows["stranger"]) == {""}
    box.vars.put(POLLS_PATH, merged.rows["camera"])
    holder(box, "camera")
    fact = observation(box.vars, "camera", "serial")
    assert fact.member == "relay" and set(fact.value) == {"ref", "to", "urls"}
    assert "token" not in json.dumps(merged.rows)


def test_home_follows_via_then_centre_then_holder_and_cannot_reuse_old_home_fact():
    box, worker = fixture()
    assert polls(worker, [])
    box.vars.put(POLLS_PATH, row(address()))
    holder(box, "camera")
    assert observation(box.vars, "camera", "serial").member == "relay"
    topology(box, centre="centre")
    refused(lambda: observation(box.vars, "camera", "serial"))
    box.vars.put(POLLS_PATH, row(address("centre")))
    assert observation(box.vars, "camera", "serial").member == "centre"
    holder(box, "relay")
    assert polls(worker, []) == {}                                    # prior home stops publishing without a restart
    holder(box, "centre")
    assert polls(worker, [])                                          # new home already has the credential-free source
    holder(box, "camera")
    topology(box, centre=None)
    refused(lambda: observation(box.vars, "camera", "serial"))
    box.vars.put(POLLS_PATH, row(address("holder")))
    assert observation(box.vars, "camera", "serial").member == "holder"
    for own, expected in (("relay", False), ("centre", False), ("holder", True)):
        holder(box, own)
        if own == "holder":
            topology(box, centre=None, key="domain/topology")
            box.vars.put("domain/cam/sources/holder", row(camera(to=("holder",))))
        else:
            box.vars.put("domain/cam/sources", row(camera(to=(own,))))
        assert bool(polls(worker, [])) is expected


def test_publisher_excludes_recorded_nonpolling_missing_conflicting_and_unaddressed_sources():
    box, worker = fixture()
    box.vars.put("domain/placed/rec/serial", {"cluster": "main", "origin": "camera", "copies": "[]",
        "reason": "operator", "at": "1000", "rev": "1"})
    assert polls(worker, []) == {}                                    # C2/C3b recording transport keeps its own path
    box.vars.as_writer("domainagent", ["domain/*"]).delete("domain/placed/rec/serial")
    cases = [row(camera(polls=False)), row(camera(polls=1)), row(camera(to=("centre",))),
             row(camera(), missing=("camera",)), row(camera(), camera(name="other")),
             row(camera(live_url=7)), {"serial": json.dumps(camera()["value"])},
             {"": json.dumps({"missing": []}), "serial": "{"}]
    for value in cases:
        box.vars.put("domain/cam/sources", value)
        assert polls(worker, []) == {}
    value = row(camera())
    value["broken"] = "{"
    box.vars.put("domain/cam/sources", value)
    assert set(polls(worker, [])) == {"serial"}                          # malformed neighbour cannot suppress a good camera
    box.vars.put("domain/placed/rec/serial", {"cluster": "main", "rev": "bad"})
    assert polls(worker, []) == {}                                    # malformed placement cannot be mistaken for no assignment


def test_publisher_elects_smallest_fresh_recorder_and_sorts_distinct_ingests():
    box, worker = fixture()
    heartbeat(box, "r-1", "http://relay/z")
    heartbeat(box, "r-2", "http://relay/a", ts=box.wall()+100000)
    heartbeat(box, "r-3", "http://relay/a")
    heartbeat(box, "a-misnamed", "http://rogue", worker="a-rogue")
    heartbeat(box, "a-torn", "http://rogue", status=["bad"])
    heartbeat(box, "a-bad-address", ["http://rogue"])
    box.objects.put("rec/heartbeats/a-garbage", b"{")
    assert json.loads(polls(worker, [])["serial"])["urls"] == ["http://relay/a", "http://relay/z"]
    worker.name = "r-2"
    assert polls(worker, []) == {}
    worker.name = "r-1"
    box.wall.advance(-500000)
    assert polls(worker, [])                                          # sender wall cannot expire a live observation
    box.clock.advance(46)
    heartbeat(box, "r-2", "http://relay/a")
    assert polls(worker, []) == {}
    worker.name = "r-2"
    assert json.loads(polls(worker, [])["serial"])["urls"] == ["http://relay/a"]
    heartbeat(box, "r-1", "http://relay/z")
    assert polls(worker, []) == {}


def test_publisher_reads_current_holder_sources_and_topology_instead_of_stale_copies():
    box, worker = fixture("holder")
    topology(box, key="domain/topology", centre=None)
    box.vars.put("domain/cam/sources/holder", row(camera(to=("holder",))))
    box.vars.put("domain/cam/sources", row(camera(polls=False)))
    assert polls(worker, [])                                          # actual holder has no carried copy
    box.vars.as_writer("domain", ["domain/*"]).delete("domain/cam/sources/holder")
    assert polls(worker, []) == {}                                    # stale copy never replaces absent current result
    box.vars.put("domain/cam/sources/holder", row(camera(to=("holder",))))
    box.vars.put("domain/topology", {"doc": "{"})
    assert polls(worker, []) == {}


def test_reader_uses_current_holder_result_and_refuses_old_copy_after_holder_move():
    box, _ = fixture()
    holder(box, "camera", "camera")
    topology(box, centre="relay", key="domain/topology")
    topology(box, centre="rogue")                                    # stale member topology must not select rogue
    box.vars.put(POLLS_PATH, row(address("rogue")))
    box.vars.put(POLLS_PATH+"/camera", row(address()))
    assert observation(box.vars, "camera", "serial").member == "relay"
    box.vars.as_writer("domain", ["domain/*"]).delete(POLLS_PATH+"/camera")
    refused(lambda: observation(box.vars, "camera", "serial"))
    holder(box, "camera", "new-holder")
    topology(box, via={"camera": "relay"})
    box.vars.put(POLLS_PATH, row(address()))
    assert observation(box.vars, "camera", "serial").member == "relay"


def test_reader_refuses_missing_conflicting_foreign_flat_and_secret_bearing_observations():
    cases = [row(address(), missing=("relay",)), row(address(), address("other")), row(address("other")),
             row(address(to=("camera", "other"))), row(address(urls=[])), row(address(urls=[7])),
             row(address(token_secret="must-never-be-read")), row(address(until=10000)),
             {"serial": json.dumps({"urls": ["http://legacy"], "token_secret": "must-never-be-read"})},
             {"": json.dumps({"missing": []}), "serial": "{"}]
    for value in cases:
        refused(lambda: confirmed(value, "camera", "serial", "relay"))
    missing = {"": json.dumps({"missing": []})}
    refused(lambda: confirmed(missing, "camera", "serial", "relay"))
    box, _ = fixture("camera")
    box.vars.put(POLLS_PATH, row(address()))
    for key, value in (("domain/member-topology", {"doc": "{"}),
                       ("domain/member-topology", {"doc": json.dumps({"rev": 0, "centre": "relay"})})):
        box.vars.put(key, value)
        refused(lambda: observation(box.vars, "camera", "serial"))
    box.vars.put("domain/holder", {"doc": "{"})
    refused(lambda: observation(box.vars, "camera", "serial"))


def test_worker_pulses_before_building_poll_input_and_slot_guard_rejects_replaced_writer():
    from vms.config import REC_SPEC
    from w2cplatform.variables import GuardFailed
    from w2cplatform.worker import Worker
    box, _ = fixture()
    box.objects.delete("rec/heartbeats/r-1")
    worker = Worker(REC_SPEC.sub, None, box.vars, box.objects, wall=box.wall, clock=box.clock,
                    spec=REC_SPEC, resource_root=box.resource_root, env={})
    worker.claim_slot("r-1")
    worker.ingest_url = "http://relay/ingest"
    assert polls(worker, []) == {}
    worker.heartbeat([], ingest=worker.ingest_url)
    value = polls(worker, [])
    assert value
    worker.put_under_slot("rec/polls/r-1", value)
    successor = Worker(REC_SPEC.sub, None, box.vars, box.objects, wall=box.wall, clock=box.clock,
                       spec=REC_SPEC, resource_root=box.resource_root, env={})
    successor.claim_slot("r-1")
    try:
        worker.put_under_slot("rec/polls/r-1", {"serial": "late"})
    except GuardFailed:
        pass
    else:
        raise AssertionError("replaced recorder published a poll address")
    assert box.vars.get("rec/polls/r-1")[0] != {"serial": "late"}
