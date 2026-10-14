"""ADR-0074 C3b: the star changes the transport receiver, never recording placement."""
import json
from types import SimpleNamespace

from tests.vmsconftest import Box
from tests.test_recording_publication import fact, placement, primary_row
from vms.ingest import CameraPusher, Ingest
from vms.recording_books import Unconfirmed, recording_value
from vms.recording_publication import primaries
from w2cplatform.trust.tokens import TokenIssuer


CENTRE_URLS = ["http://centre/a", "http://centre/b"]


def rejects(value):
    try:
        recording_value(value)
    except Unconfirmed:
        return
    raise AssertionError("an invalid ingest receiver was accepted")


def upstream_row(box, *, own="relay", member="centre", recipients=None, missing=(), conflict=False):
    value = {"ref": "serial", "to": [own] if recipients is None else recipients, "urls": CENTRE_URLS}
    entries = [{"member": member, "item": "r1/serial", "value": value}]
    if conflict:
        entries.append({"member": member, "item": "r2/serial", "value": value})
    row = {"": json.dumps({"missing": list(missing)}),
           "serial": json.dumps({"entries": entries, "missing": list(missing)})}
    box.vars.put("domain/rec/upstream", row)


def publisher(*, own="relay", primary="relay", backup=False, star=("relay",), push=False):
    box = Box()
    placement(box, own, primary=primary, copies=("backup",))
    box.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 1, "centre": "centre", "star": list(star), "via": {}})})
    source = {"ref": "serial", "to": [primary, "backup"], "live_url": "rtsp://camera/live",
              "server": "camera", "as_of": box.wall(), "polls": True, **({"push": True} if push else {})}
    sources = {"": json.dumps({"missing": []}), "serial": json.dumps({"missing": [], "entries": [
        {"member": "camera", "item": "w1/serial", "value": source}]})}
    volume = "backup-volume" if backup else None
    if volume:
        box.vars.put("rec/volumes/" + volume, {"kind": "backup"})
    worker = SimpleNamespace(vars=box.vars, rows=[{"id": "recording", "cam": "ref:serial", "enabled": True}],
                             volume=volume, wall=box.wall, ingest_url=f"http://{own}/ingest", archive_url="",
                             _look=lambda: SimpleNamespace(sources=lambda: sources))
    upstream_row(box, own=own)
    return box, worker


def published(worker):
    rows = primaries(worker, [{"id": "recording", "phase": "pending"}])
    return json.loads(rows["recording"]) if "recording" in rows else {}


def star_and_backup():
    return [fact("relay", "primary", ingest=CENTRE_URLS, ingest_cluster="centre", push=True, to=["camera", "relay", "backup"]),
            fact("backup", "backup", "backup", ingest=["http://backup/ingest"], push=True, to=["camera", "relay", "backup"])]


def test_recording_value_accepts_explicit_receiver_with_ingest_and_preserves_implicit_member():
    for role in ("primary", "backup"):
        value = fact("relay", "recording", role, ingest=CENTRE_URLS, ingest_cluster="centre", push=True)["value"]
        assert recording_value(value)["ingest_cluster"] == "centre"
        ordinary = {k: v for k, v in value.items() if k != "ingest_cluster"}
        assert recording_value(ordinary) == ordinary and "ingest_cluster" not in ordinary


def test_recording_value_rejects_empty_nonstring_or_addressless_explicit_receiver():
    base = fact("relay", "recording", ingest=CENTRE_URLS)["value"]
    for receiver in ("", None, 0, False, [], {}):
        rejects({**base, "ingest_cluster": receiver})
    rejects({k: v for k, v in {**base, "ingest_cluster": "centre"}.items() if k != "ingest"})
    rejects({**base, "ingest_cluster": "centre", "ingest": []})
    rejects({**base, "ingest_cluster": "centre", "ingest": "http://centre/ingest"})


def test_star_primary_publishes_confirmed_centre_addresses_without_moving_recording_or_copies():
    box, worker = publisher()
    assignment = box.vars.get("domain/placed/rec/serial")[0]
    value = published(worker)
    assert value["role"] == "primary" and value["recording"] == "recording"
    assert value["ingest"] == CENTRE_URLS and value["ingest_cluster"] == "centre" and value["push"] is True
    assert value["to"] == ["camera", "relay", "backup"] and "centre" not in value["to"]
    assert worker.ingest_url == "http://relay/ingest"
    assert box.vars.get("domain/placed/rec/serial")[0] == assignment
    assert not ({"token", "token_secret", "until"} & value.keys())


def test_star_primary_never_substitutes_its_unreachable_ingest_for_unconfirmed_upstream():
    for damage in ("wrong-origin", "wrong-recipient", "missing", "conflict", "torn"):
        box, worker = publisher()
        assignment = box.vars.get("domain/placed/rec/serial")[0]
        # Establish an observation first: a stale local cache must not publish a new wrong receiver later.
        published(worker)
        if damage == "wrong-origin":
            upstream_row(box, member="stranger")
        elif damage == "wrong-recipient":
            upstream_row(box, recipients=["backup"])
        elif damage == "missing":
            upstream_row(box, missing=["centre"])
        elif damage == "conflict":
            upstream_row(box, conflict=True)
        else:
            box.vars.put("domain/rec/upstream", {"serial": "{"})
        value = published(worker)
        assert not value.get("ingest") and not value.get("push") and "ingest_cluster" not in value, damage
        assert box.vars.get("domain/placed/rec/serial")[0] == assignment


def test_ordinary_primary_and_star_assignments_backup_keep_their_own_receiver():
    for own, primary, backup, star in (("main", "main", False, ()), ("backup", "relay", True, ("relay",))):
        box, worker = publisher(own=own, primary=primary, backup=backup, star=star, push=True)
        value = published(worker)
        assert value["role"] == ("backup" if backup else "primary")
        assert value["ingest"] == [f"http://{own}/ingest"] and value["push"] is True
        assert "ingest_cluster" not in value
        assignment = box.vars.get("domain/placed/rec/serial")[0]
        assert assignment["cluster"] == primary and json.loads(assignment["copies"]) == ["backup"]


def test_camera_reads_explicit_centre_from_primary_without_deriving_it_from_topology():
    box = Box()
    placement(box, "camera", primary="relay", copies=("backup",))
    # The observation alone identifies the transport receiver. The camera does not need a topology copy.
    assert box.vars.get("domain/member-topology")[0] is None
    primary_row(box, star_and_backup())
    pusher = CameraPusher("serial", box.vars, lambda url: None, clock=box.wall, steady=box.clock)
    entry = pusher.assigned.entry()
    assert entry["primary"] == "relay" and set(entry["channels"]) == {"relay", "backup"}
    assert entry["channels"]["relay"]["cluster"] == "centre"
    assert entry["channels"]["relay"]["urls"] == CENTRE_URLS
    assert entry["channels"]["backup"]["cluster"] == "backup"
    assert entry["channels"]["backup"]["urls"] == ["http://backup/ingest"]


def test_camera_pushes_to_explicit_centre_and_independent_backup_with_original_placement():
    box, issuer = Box(), TokenIssuer("site")
    placement(box, "camera", primary="relay", copies=("backup",))
    assignment = box.vars.get("domain/placed/rec/serial")[0]
    primary_row(box, star_and_backup())
    ingests, queues, calls = {}, {}, []
    for receiver, urls in (("centre", CENTRE_URLS), ("backup", ["http://backup/ingest"])):
        ing = Ingest(receiver, urls, issuer.keyset, wall=box.wall)
        ing.want("serial", "recorder:test")
        queues[receiver] = ing.subscribe("serial", "recorder:test", maxsize=10)
        for url in urls:
            ingests[url] = ing
    def request(kind, ref):
        calls.append((kind, ref))
        token = issuer.issue("camera", 86400, now=box.wall(), kind=kind, aud=["relay", "backup", "centre"], ref=ref)
        return {"request_id": "fixture", "token": token, "exp": box.wall()+86400}
    pusher = CameraPusher("serial", box.vars, lambda url: ingests[url], clock=box.wall, steady=box.clock,
                          token_requests=SimpleNamespace(request=request))
    for i in range(3):
        box.wall.advance(1)
        box.clock.advance(1)
        pusher.pass_once([{"t": box.wall(), "key": True, "n": i}])
    assert {name: [frame["n"] for frame in q.drain()] for name, q in queues.items()} == {"centre": [0, 1, 2], "backup": [0, 1, 2]}
    assert pusher.assigned.channels["relay"]._channel_entry["cluster"] == "centre"
    assert pusher.assigned.channels["backup"]._channel_entry["cluster"] == "backup"
    assert calls == [("stream", "serial")]
    assert box.vars.get("domain/placed/rec/serial")[0] == assignment
