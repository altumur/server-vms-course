"""C2: role requests, member audiences, independent channels and reserve writers."""
import json

from tests.vmsconftest import Box, recorder
from tests.test_recording_publication import fact, placement, primary_row, source_row
from vms.ingest import CameraPusher, Ingest, Refused
from vms.ingestrec import IngestRecordings, _Pushed
from vms.obsd import Sample
from w2cplatform.domain.placement import placed
from w2cplatform.trust.tokens import TokenIssuer


def refused(fn):
    try:
        fn()
    except Refused:
        return
    raise AssertionError("an unauthorized stream was accepted")


class Door:
    def __init__(self, issuer, box):
        self.issuer, self.box, self.calls = issuer, box, []

    def request(self, kind, ref):
        self.calls.append((kind, ref))
        assignment = placed(self.box.vars, "rec", ref)
        token = self.issuer.issue("camera", 86400, now=self.box.wall(), kind=kind,
                                  ref=ref, aud=[assignment["cluster"], *assignment["copies"]])
        return {"request_id": "local-test", "token": token, "exp": self.box.wall() + 86400}


def test_stream_receiver_accepts_only_member_list_reference_signature_and_current_token():
    box, issuer = Box(), TokenIssuer("site")
    ing = Ingest("main", ["http://main/ingest"], issuer.keyset, wall=box.wall)
    def token(**over):
        return issuer.issue("serial", 10, now=box.wall(), kind="stream", **{"aud": ["main", "reserve1"], "ref": "serial", **over})
    ing.poll(token(), "serial")
    for aud in ("ingest:main", "main", ["other"], ["main", "main"], ["main", 1]):
        refused(lambda: ing.poll(token(aud=aud), "serial"))
    refused(lambda: ing.poll(token(ref="other"), "serial"))
    old = token()
    box.wall.advance(100)
    refused(lambda: ing.poll(old, "serial"))
    rogue = TokenIssuer("site")
    refused(lambda: ing.poll(rogue.issue("serial", 100, now=box.wall(), kind="stream", aud=["main"], ref="serial"), "serial"))


def test_poll_only_route_answers_work_without_sending_frames_even_when_a_viewer_wants_them():
    box, issuer = Box(), TokenIssuer("site")
    placement(box, "camera", copies=())
    url = "http://main/ingest"
    ing = Ingest("main", [url], issuer.keyset, wall=box.wall)
    ing.want("serial", "viewer")
    queue = ing.subscribe("serial", "viewer", maxsize=10)
    primary_row(box, [fact("main", "recording", ingest=[url])])
    pusher = CameraPusher("serial", box.vars, lambda _: ing, clock=box.wall,
                          token_requests=Door(issuer, box))
    result = pusher.pass_once([{"t": box.wall(), "key": True, "n": 1}])
    assert result["pushed"] == 0 and queue.drain() == []
    assert pusher.assigned.channels["main"]._route["push"] is False


def test_pusher_uses_one_in_memory_token_and_distinct_cursors_for_primary_and_two_reserves():
    box, issuer = Box(), TokenIssuer("site")
    placement(box, "camera")
    ingests, queues = {}, {}
    entries = []
    for name, role in (("main", "primary"), ("reserve1", "backup"), ("reserve2", "backup")):
        url = f"http://{name}/ingest"
        ing = Ingest(name, [url], issuer.keyset, wall=box.wall)
        ing.want("serial", "viewer")
        queues[name] = ing.subscribe("serial", "viewer", maxsize=100)
        ingests[url] = ing
        entries.append(fact(name, name + "-recording", role, push=True, ingest=[url]))
    primary_row(box, entries)
    door = Door(issuer, box)
    pusher = CameraPusher("serial", box.vars, lambda url: ingests[url], clock=box.wall,
                          steady=box.clock, token_requests=door)
    for i in range(3):
        box.wall.advance(1); box.clock.advance(1)
        pusher.pass_once([{"t": box.wall(), "key": True, "n": i}])
    batches = {name: [frame["n"] for frame in queue.drain()] for name, queue in queues.items()}
    assert batches == {"main": [0, 1, 2], "reserve1": [0, 1, 2], "reserve2": [0, 1, 2]}
    assert door.calls == [("stream", "serial")]
    assert len({id(c) for c in pusher.assigned.channels.values()}) == 3
    assert len({id(c.frames) for c in pusher.assigned.channels.values()}) == 1
    assert "token_secret" not in json.dumps({k: box.vars.get(k)[0] for k in box.vars.list("")})
    # A missing report keeps an existing channel, and cannot create a new one.
    primary_row(box, entries[1:], missing=["main"])
    box.wall.advance(1); box.clock.advance(1)
    pusher.pass_once([{"t": box.wall(), "key": True, "n": 3}])
    assert [f["n"] for f in queues["main"].drain()] == [3]
    fresh = CameraPusher("serial", box.vars, lambda url: ingests[url], clock=box.wall,
                         steady=box.clock, token_requests=door)
    assert "main" not in fresh.entry()["channels"]
    # A member past its report grace has no observation and is not in missing;
    # that still cannot sever an already working channel.
    primary_row(box, entries[1:])
    box.wall.advance(1); box.clock.advance(1)
    pusher.pass_once([{"t": box.wall(), "key": True, "n": 35}])
    assert [f["n"] for f in queues["main"].drain()] == [35]
    # A changed assignment invalidates both cached credentials and the previous routes.
    placement(box, "camera", primary="reserve1", copies=("reserve2",), rev=2)
    primary_row(box, [fact("reserve1", "new-primary", push=True, ingest=["http://reserve1/ingest"]),
                      fact("reserve2", "b2", "backup", push=True, ingest=["http://reserve2/ingest"])])
    box.wall.advance(1); box.clock.advance(1)
    pusher.pass_once([{"t": box.wall(), "key": True, "n": 4}])
    assert set(pusher.assigned.channels) == {"reserve1", "reserve2"} and len(door.calls) == 2
    assert queues["main"].drain() == []


def test_reserve_writers_independently_follow_primary_state_and_absence_grace():
    boxes, recs, sinks = [], [], []
    class Sink:
        def __init__(self): self.frames, self.closed = [], 0
        def put(self, value): self.frames.append(value)
        def finish(self): self.closed += 1
    for member in ("reserve1", "reserve2"):
        box = Box(); placement(box, member); source_row(box, push=True)
        box.objects.put("domain/seen", json.dumps({"ts": box.wall()}).encode())
        rec = recorder(box)
        rec.rows = [{"id": "backup", "cam": "ref:serial", "enabled": True, "when": "offline", "revision": 1}]
        issuer = TokenIssuer("site")
        rec.ingest = Ingest(member, ["http://" + member + "/ingest"], issuer.keyset, wall=box.wall)
        actuator, sink = IngestRecordings(rec.actuator, rec), Sink()
        rec.actuator = actuator
        queue = rec.ingest.subscribe("serial", "recorder:r/backup")
        state = _Pushed("backup", "serial", "recorder:r/backup", sink, queue, box.wall(), "offline")
        actuator.pushed["backup"] = state
        boxes.append(box); recs.append(rec); sinks.append(sink)
    sample = Sample(1, 1000, 1040, True, b"payload")
    for enabled, running, writes in ((True, True, False), (True, False, True), (False, False, False)):
        before = [len(s.frames) for s in sinks]
        for box, rec in zip(boxes, recs):
            primary_row(box, [fact("main", "primary", enabled=enabled, running=running)])
            rec._look()._got.clear()
            state = rec.actuator.pushed["backup"]
            rec.actuator._write(state, [sample])
        assert [len(s.frames) - n for s, n in zip(sinks, before)] == [int(writes), int(writes)]
    for box, rec in zip(boxes, recs):
        primary_row(box, [])
        box.objects.put("domain/seen", json.dumps({"ts": box.wall()}).encode())
        rec._look()._got.clear()
        state = rec.actuator.pushed["backup"]
        before = len(state.sink.frames)
        assert rec.actuator._write(state, [sample]) == 0
        box.wall.advance(20)
        # Silence cannot revoke the explicit stop just observed above.
        assert rec.actuator._write(state, [sample]) == 0 and len(state.sink.frames) == before
        # Only a confirmed enabled primary releases that intent; its subsequent
        # disappearance then exercises the cold reserve's independent grace.
        primary_row(box, [fact("main", "primary", enabled=True, running=True)])
        box.objects.put("domain/seen", json.dumps({"ts": box.wall()}).encode())
        rec._look()._got.clear()
        assert rec.actuator._write(state, [sample]) == 0
        primary_row(box, [])
        rec._look()._got.clear()
        assert rec.actuator._write(state, [sample]) == 0
        box.wall.advance(20)
        assert rec.actuator._write(state, [sample]) == 1 and len(state.sink.frames) == before + 1


def test_corrupt_book_keeps_a_working_channel_and_covers_only_after_absence_grace():
    box, issuer = Box(), TokenIssuer("site")
    placement(box, "camera")
    primary_row(box, [fact("main", "r", push=True, ingest=["http://main/ingest"])])
    ing = Ingest("main", ["http://main/ingest"], issuer.keyset, wall=box.wall)
    ing.want("serial", "viewer")
    q = ing.subscribe("serial", "viewer")
    p = CameraPusher("serial", box.vars, lambda url: ing, clock=box.wall,
        steady=box.clock, token_requests=Door(issuer, box))
    p.pass_once([{"t": box.wall(), "key": True}])
    assert p.uncovered is False
    box.vars.put("domain/rec/primaries", {"": '{"missing": []}', "serial": '{"entries": ['})
    p.pass_once([])
    assert p.uncovered is False
    box.wall.advance(20); box.clock.advance(20)
    p.pass_once([{"t": box.wall(), "key": True}])
    assert p.uncovered is True and len(q.drain()) == 2
    primary_row(box, [fact("main", "r", enabled=False, running=False,
        ingest=["http://main/ingest"], push=True)])
    p.pass_once([])
    assert p.uncovered is False
