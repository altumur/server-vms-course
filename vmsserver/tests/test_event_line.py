"""The event line, as agreed with the product (the platform review; feedback BL).

    t          when the line was WRITTEN. It files the line: the bucket is chosen by it, and its meaning is unchanged
    occurred   when the event HAPPENED, where the writer knows better than `t`
    id         the line's name, given by the writer: what tells a copy from a twin
    v          the version — not written; a line without it is version 1

A reader says which time it asks in (`by`); the merge knows a copy by its name; a scenario fires on when things
happened and is named after the event that completed it; and only what one of OUR elements said on the bus is
an observation of the camera.
"""
import json

from w2cplatform.eventdatabase import EventIndex, MergedIndex
from w2cplatform.events import MAX_EVENT_LATENESS, EventLog, read_bucket
from tests.conftest import Box
from tests.test_autoworker import DOOR, _assigned, _Log, _scenario, _worker, ev


def test_every_line_has_a_name_and_two_events_in_one_instant_are_two():
    box = Box()
    t = box.wall() - 100
    log = EventLog(box.archive, "vms", "7", 3)
    p = log.append(t, "io.input", port="1")
    log.append(t, "io.input", port="1")                                # the same kind, the same instant, the same fields
    log.append(t + 1, "motion", id="cam-7-evt-0042")                   # a name the writer was handed is kept
    a, b, c = read_bucket(p)
    assert a["id"] != b["id"] and c["id"] == "cam-7-evt-0042"
    unit, epoch, proc, n = a["id"].rsplit("-", 3)
    assert (unit, epoch) == ("7", "e3") and len(proc) == 10 and int(b["id"].rsplit("-", 1)[1]) == int(n) + 1
    assert "v" not in a and "occurred" not in a                        # no version written; no second time nobody knows
    rows = EventIndex(box.archive, "srv-1", wall=box.wall).query(t - 1, t + 2)["events"]
    assert [r["id"] for r in rows] == [a["id"], b["id"], c["id"]]      # …and the reader hands the names on

    for bad in ({"occurred": "yesterday"}, {"occurred": True}, {"v": 2}):
        try:
            log.append(t, "motion", **bad)
            raise AssertionError(f"{bad} was written")
        except ValueError:
            pass


def test_a_reader_says_which_time_it_asks_in():
    """A contact closed at 10:00 and the device told us at 10:50. The line lies in the 10:50 bucket — a closed
    bucket is never written again — and says `occurred`. Asked by `t`, the 10:00 window does not have it; asked
    by `occurred`, it does, because the index reads `MAX_EVENT_LATENESS` further on."""
    box = Box()
    t = box.wall() - 7200
    log = EventLog(box.archive, "vms", "7", 1)
    log.append(t + 10, "motion")                                                   # written as it happened
    log.append(t + 3000, "io.input", occurred=t + 5)                               # fifty minutes late
    log.append(t + 3010, "motion")
    db = EventIndex(box.archive, "srv-1", wall=box.wall)
    window = (t, t + 600)
    assert [e["kind"] for e in db.query(*window)["events"]] == ["motion"]
    late = db.query(*window, by="occurred")["events"]
    assert [(e["kind"], e["t"]) for e in late] == [("io.input", t + 3000), ("motion", t + 10)]   # in event order; `t` still says when written
    assert late[0]["occurred"] == t + 5
    assert [e["kind"] for e in db.query(t + 2700, t + 3300, by="occurred")["events"]] == ["motion"]   # …and not where it was written

    EventLog(box.archive, "vms", "7", 1).append(t + 5000, "io.input", occurred=t + 20)   # later than the index looks
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
    when it was written."""
    box = Box()
    now = box.wall()
    for server, age in (("srv-a", 600), ("srv-b", 0), ("srv-c", 0)):
        box.objects.put(f"platform/resources/{server}/heartbeat",
                        json.dumps({"server": server, "ts": now - age, "url": f"http://{server}"}).encode())
    row = {"subsystem": "vms", "unit": "7", "cam": 7, "epoch": 1, "t": now - 900, "kind": "io.input", "server": "srv-a",
           "bucket": "vms/7/e1/x.events.jsonl", "class": "observation"}
    twins = [{**row, "id": "7-e1-abc-1"}, {**row, "id": "7-e1-abc-2"}, {**row, "id": "7-e1-abc-3", "occurred": now - 1500}]
    asked = []

    def fetch(url, params):
        asked.append(params)
        return {"events": list(twins), "truncated": False, "state": "live"}

    m = MergedIndex(box.objects, fetch=fetch, wall=box.wall)
    assert [e["id"] for e in m.query(now - 1000, now)["events"]] == ["7-e1-abc-1", "7-e1-abc-2", "7-e1-abc-3"]
    assert "by" not in asked[0]
    got = m.query(now - 2000, now, by="occurred")["events"]
    assert [e["id"] for e in got] == ["7-e1-abc-3", "7-e1-abc-1", "7-e1-abc-2"] and asked[-1]["by"] == "occurred"
    old = [dict(row), dict(row)]                                       # lines written before lines had names: the old key
    twins[:] = old
    assert len(m.query(now - 1000, now)["events"]) == 1


def test_a_scenario_counts_in_event_time_and_is_named_after_the_event():
    box = Box()
    t = box.wall()
    # Two badges in one millisecond are two firings: the name is the event's, not its time
    same = [ev(t - 10, "vms", 12, "io.input", port="1", value="closed", id="12-e1-abc-1"),
            ev(t - 10, "vms", 12, "io.input", port="1", value="closed", id="12-e1-abc-2")]
    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")
    w = _worker(box, _Log(same))
    w.reconcile_once()
    assert sorted(box.vars.list("vms/requests/")) == ["vms/requests/one-12-e1-abc-1-0", "vms/requests/one-12-e1-abc-2-0"]
    assert box.vars.get("vms/requests/one-12-e1-abc-1-0")[0]["valid_until"] == str(t - 10 + 30.0)


def test_within_is_between_when_two_things_happened_and_a_late_event_is_too_late_to_act_on():
    box = Box()
    t = box.wall()
    # Motion at t-200; the contact closed at t-190 — ten seconds later — and the device told us only now.
    # Written 190 s apart, they HAPPENED inside the window: the scenario fires. But the action was due thirty
    # seconds after the contact closed: nothing is filed, and the firing says how late it was.
    events = [ev(t - 200, "det", "7-motion", "motion", id="m-1"),
              ev(t - 5, "vms", 12, "io.input", port="1", value="closed", id="d-1", occurred=t - 190)]
    _scenario(box); _assigned(box, "door-on-badge")
    w = _worker(box, _Log(events))
    w.reconcile_once()
    assert box.vars.list("vms/requests/") == [] and w.late == 1 and w.filed == 0

    # …and written in time, it is filed with the deadline counted from when it happened
    box2 = Box(); t = box2.wall()
    events = [ev(t - 12, "det", "7-motion", "motion", id="m-1"),
              ev(t - 1, "vms", 12, "io.input", port="1", value="closed", id="d-1", occurred=t - 4)]
    _scenario(box2); _assigned(box2, "door-on-badge")
    w = _worker(box2, _Log(events))
    w.reconcile_once()
    assert box2.vars.get("vms/requests/door-on-badge-d-1-0")[0]["valid_until"] == str(t - 4 + 30.0)


def test_only_what_our_own_element_said_is_an_observation():
    """The filter was a list of names to drop. On the product's box `rtpbin` posted `application/x-rtp-source-sdes`
    every few seconds and each became an event of the camera. The question is who posted it."""
    import os
    from gstvms.observes import observes
    assert observes("driverpacksrc", "motion")
    assert not observes("rtpbin", "application/x-rtp-source-sdes") and not observes("", "motion")
    assert not observes("splitmuxsink", "splitmuxsink-fragment-closed") and not observes("appsink", "eos")
    assert observes("acmemotion", "motion", extra=("acmemotion",))
    os.environ["EVENT_ELEMENTS"] = "acmemotion,acmeface"
    try:
        assert observes("acmeface", "face")
    finally:
        del os.environ["EVENT_ELEMENTS"]
