"""The event line, as agreed with the product (the platform review; feedback BL).

    t          when the line was WRITTEN. It files the line: the bucket is chosen by it, and its meaning is unchanged
    occurred   when the event HAPPENED, where the writer knows better than `t`
    id         the line's name, given by the writer: what tells a copy from a twin
    v          the version — not written; a line without it is version 1

A reader says which time it asks in (`by`), and the merge knows a copy by its name. What a subsystem does with the
line — acts on when things happened, fills `occurred` from its source's clock — is proved with that subsystem.
"""
import json

from w2cplatform.eventdatabase import EventIndex, MergedIndex
from w2cplatform.events import MAX_EVENT_LATENESS, EventLog, read_bucket
from tests.conftest import Box


def test_every_line_has_a_name_and_two_events_in_one_instant_are_two():
    box = Box()
    t = box.wall() - 100
    log = EventLog(box.tree, "testsub", "c7", 3)
    p = log.append(t, "lane.jam", lane="1")
    log.append(t, "lane.jam", lane="1")                                # the same kind, the same instant, the same fields
    log.append(t + 1, "tick", id="c7-evt-0042")                        # a name the writer was handed is kept
    a, b, c = read_bucket(p)
    assert a["id"] != b["id"] and c["id"] == "c7-evt-0042"
    unit, epoch, proc, n = a["id"].rsplit("-", 3)
    assert (unit, epoch) == ("c7", "e3") and len(proc) == 10 and int(b["id"].rsplit("-", 1)[1]) == int(n) + 1
    assert "v" not in a and "occurred" not in a                        # no version written; no second time nobody knows
    rows = EventIndex(box.tree, "srv-1", wall=box.wall).query(t - 1, t + 2)["events"]
    assert [r["id"] for r in rows] == [a["id"], b["id"], c["id"]]      # …and the reader hands the names on

    for bad in ({"occurred": "yesterday"}, {"occurred": True}, {"v": 2}):
        try:
            log.append(t, "tick", **bad)
            raise AssertionError(f"{bad} was written")
        except ValueError:
            pass


def test_a_reader_says_which_time_it_asks_in():
    """A lane jammed at 10:00 and its source told us at 10:50. The line lies in the 10:50 bucket — a closed
    bucket is never written again — and says `occurred`. Asked by `t`, the 10:00 window does not have it; asked
    by `occurred`, it does, because the index reads `MAX_EVENT_LATENESS` further on."""
    box = Box()
    t = box.wall() - 7200
    log = EventLog(box.tree, "testsub", "c7", 1)
    log.append(t + 10, "tick")                                                     # written as it happened
    log.append(t + 3000, "lane.jam", occurred=t + 5)                               # fifty minutes late
    log.append(t + 3010, "tick")
    db = EventIndex(box.tree, "srv-1", wall=box.wall)
    window = (t, t + 600)
    assert [e["kind"] for e in db.query(*window)["events"]] == ["tick"]
    late = db.query(*window, by="occurred")["events"]
    assert [(e["kind"], e["t"]) for e in late] == [("lane.jam", t + 3000), ("tick", t + 10)]     # in event order; `t` still says when written
    assert late[0]["occurred"] == t + 5
    assert [e["kind"] for e in db.query(t + 2700, t + 3300, by="occurred")["events"]] == ["tick"]     # …and not where it was written

    EventLog(box.tree, "testsub", "c7", 1).append(t + 5000, "lane.jam", occurred=t + 20)   # later than the index looks
    assert MAX_EVENT_LATENESS == 3600 and len(db.query(*window, by="occurred")["events"]) == 2
    assert len(db.query(t + 4900, t + 5100)["events"]) == 1                        # by `t` it is always found

    for index in (db, MergedIndex(box.objects, fetch=lambda url, params: {"events": []}, wall=box.wall)):
        try:
            index.query(*window, by="whenever")
            raise AssertionError("an unknown time was answered")
        except ValueError as e:
            assert "by is 't'" in str(e)


def test_the_merge_knows_a_copy_by_its_name():
    """srv-a is silent; srv-b and srv-c both hold copies of its buckets. The same line from both is one event;
    two events of one kind in one instant are two — they used to be one, because a copy was known by where and
    when it was written. Silent by what the merge saw (r29-writers2): srv-a's heartbeat stood still for a minute."""
    box = Box()

    def beat(servers, age=0):
        for server in servers:
            box.objects.put(f"platform/resources/{server}/heartbeat",
                            json.dumps({"server": server, "ts": box.wall() - age, "url": f"http://{server}"}).encode())
    now = box.wall()
    beat(("srv-a",), age=600)
    beat(("srv-b", "srv-c"))
    row = {"subsystem": "testsub", "unit": "c7", "epoch": 1, "t": now - 900, "kind": "lane.jam", "server": "srv-a",
           "bucket": "testsub/c7/e1/x.events.jsonl", "class": "observation"}
    twins = [{**row, "id": "c7-e1-abc-1"}, {**row, "id": "c7-e1-abc-2"}, {**row, "id": "c7-e1-abc-3", "occurred": now - 1500}]
    asked = []

    def fetch(url, params):
        asked.append(params)
        return {"events": list(twins), "truncated": False, "state": "live"}

    m = MergedIndex(box.objects, fetch=fetch, wall=box.wall, clock=box.clock)
    m.live(m.seen())                                                   # the merge's first look
    box.wall.advance(60); box.clock.advance(60)
    beat(("srv-b", "srv-c"))
    asked.clear()
    assert [e["id"] for e in m.query(now - 1000, now)["events"]] == ["c7-e1-abc-1", "c7-e1-abc-2", "c7-e1-abc-3"]
    assert "by" not in asked[0]
    got = m.query(now - 2000, now, by="occurred")["events"]
    assert [e["id"] for e in got] == ["c7-e1-abc-3", "c7-e1-abc-1", "c7-e1-abc-2"] and asked[-1]["by"] == "occurred"
    old = [dict(row), dict(row)]                                       # lines written before lines had names: the old key
    twins[:] = old
    assert len(m.query(now - 1000, now)["events"]) == 1
