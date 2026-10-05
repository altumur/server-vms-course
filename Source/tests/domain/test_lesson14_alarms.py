"""Lesson 14 — alarms from every member.

One list of alarms across cameras that are each their own cluster: merged by the domain from the alarm page
each member's agent leaves in its report (Lesson 10, step 7), newest first, with what it could not hear said
as part of the answer. The camera that goes dark is the one whose last alarm matters, so: an alarm wakes the
agent and leaves at once; a silent member is answered from its last report; its silence is itself an alarm,
and the ingest it polls says whether it is alive; and the domain keeps what it read, a week of it.
"""
import json

from w2cplatform.cluster.variables import FakeVariables

from w2cplatform.domain.agent import DomainAgent
from vms.domainpart.ingest import POLLED
from w2cplatform.domain.alarms import AlarmHistory, Card, DomainAlarms, ReportedDoor, pages
from vms.domainpart.device import DeviceCluster, serial_of
from w2cplatform.domain.federation import Federation
from w2cplatform.domain.uplink import member_copy
from tests.domain.conftest import Clock, make_cluster

NOW = 1_001_000.0                     # the open bucket is [1 000 800, 1 001 400)


def _site(wall, nets=("vlan:a", "vlan:a", "vlan:b")):
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    fed.add(north)
    devices, cards, agents = {}, {}, {}
    for i, net in enumerate(nets):
        d = DeviceCluster(f"SN{i}", FakeVariables(), wall=wall, reaches=(net,))
        d.boot()
        fed.add(member_copy(d.name, north.objects, wall=wall, reaches=(net,)))   # the domain reads its reports
        devices[d.name] = d
        agents[d.name] = DomainAgent(d.name, north.vars, d.flash, now=wall, domain_objects=north.objects,
                                     published=d.local_objects(),
                                     pages=lambda d=d: pages(cards[d.name], wall()))
        cards[d.name] = Card("vms", on_alarm=agents[d.name].wake)

    def report(skip=()):                                               # every camera that is on: one pass of its agent
        for name, a in agents.items():
            if devices[name].door_open and name not in skip:
                a.sync()

    report()
    reported = lambda name: ReportedDoor(name, north.objects, wall=wall)
    return fed, north, devices, cards, agents, report, reported


def test_one_list_newest_first_each_line_naming_its_member():
    wall = Clock(NOW)
    fed, north, devices, cards, agents, report, reported = _site(wall)
    cards["cam-SN0"].observe(1, NOW - 1500, "door_forced", alarm=True)
    cards["cam-SN1"].observe(1, NOW - 900, "stream_lost", alarm=True)
    cards["cam-SN2"].observe(1, NOW - 100, "tamper", alarm=True)
    cards["cam-SN2"].observe(1, NOW - 90, "motion")                       # an observation: not an alarm
    report()
    out = DomainAlarms(fed, reported, wall, ref_of=serial_of).list(since=NOW - 3600)
    assert [(e["member"], e["kind"]) for e in out["events"]] == [("cam-SN2", "tamper"), ("cam-SN1", "stream_lost"), ("cam-SN0", "door_forced")]
    assert out["complete"] and out["sentence"] == "every member answered"


def test_an_alarm_wakes_the_agent_and_leaves_at_once_and_a_storm_is_one_report_a_second():
    """The camera at the gate goes dark thirty seconds after it saw the door forced — about one pass of its
    agent. So the alarm does not wait for the pass: the card wakes the agent, and the report goes now. A storm
    is not a report per line: the next urgent report waits a second, and everything written meanwhile goes
    with it."""
    wall = Clock(NOW)
    fed, north, devices, cards, agents, report, reported = _site(wall)
    agent = agents["cam-SN0"]
    assert not agent.due()
    cards["cam-SN0"].observe(1, NOW, "door_forced", alarm=True)
    assert agent.due() and agent.report_now()                             # now, not in half a minute
    assert [e["kind"] for e in DomainAlarms(fed, reported, wall, ref_of=serial_of).list(since=NOW - 60, until=NOW + 60)["events"]] == ["door_forced"]
    cards["cam-SN0"].observe(1, NOW + 0.2, "tamper", alarm=True)
    assert not agent.due()                                                # inside the second: it waits
    wall.advance(1)
    assert agent.due() and agent.report_now()
    kinds = [e["kind"] for e in DomainAlarms(fed, reported, wall, ref_of=serial_of).list(since=NOW - 60, until=NOW + 60)["events"]]
    assert kinds == ["tamper", "door_forced"]
    cards["cam-SN0"].observe(1, NOW + 1.5, "motion")                     # an observation wakes nobody
    wall.advance(5)
    assert not agent.due()


def test_an_agent_the_card_cannot_wake_asks_it_once_a_second():
    """The card wakes the agent when both are one process. The product's agent is a process of its own, and so is
    the course's in production — nothing can wake it (feedback AZ). So it asks: is there an alarm on the card
    newer than the last page it reported? Asked by the loop with `due`, once a second; the report goes at once."""
    wall = Clock(NOW)
    fed, north, devices, cards, agents, report, reported = _site(wall)
    card, d = Card("vms"), devices["cam-SN0"]                                   # no `on_alarm`: another process
    agent = DomainAgent(d.name, north.vars, d.flash, now=wall, domain_objects=north.objects,
                        published=d.local_objects(), pages=lambda: pages(card, wall()), alarm_waiting=card.waiting)
    agent.sync()
    assert not agent.due()
    wall.advance(0.5)
    card.observe(1, wall(), "door_forced", alarm=True)
    assert agent.due() and agent.report_now()
    assert [e["kind"] for e in DomainAlarms(fed, reported, wall, ref_of=serial_of).list(since=NOW - 60, until=NOW + 60)["events"]] == ["door_forced"]
    assert not agent.due()                                                # reported: nothing newer on the card


def test_the_history_keeps_an_alarm_once_however_late_the_domain_reads_the_report():
    """A page's times are moved to the domain's clock by a shift taken afresh with every report — the domain's time
    when it first saw the report, less the report's stamp — and it moves with how late the domain read it. The
    product's history compared lines by the shifted time and kept every alarm again on every read: two alarms, eight
    lines on its box (feedback AZ). The key is the line's time on the member's clock (`t_src`)."""
    wall = Clock(NOW)
    fed, north, devices, cards, agents, report, reported = _site(wall)
    history = AlarmHistory(north.objects, days=7, wall=wall)
    cards["cam-SN1"].observe(1, NOW - 100, "door_forced", alarm=True)
    for late in (3.0, 0.4, 2.7):                                          # how long after the report the domain reads it
        report(); wall.advance(late)
        out = DomainAlarms(fed, reported, wall, history=history, ref_of=serial_of).list(since=NOW - 3600)
        assert [e["kind"] for e in out["events"] if e["member"] == "cam-SN1"] == ["door_forced"]
        wall.advance(30 - late)
    assert [e["kind"] for e in history.read("cam-SN1", NOW - 3600, wall())] == ["door_forced"]


def test_a_member_that_goes_dark_is_answered_from_its_last_report_and_its_silence_is_an_alarm():
    """SN0 raised an alarm twenty-five minutes ago and another ninety seconds ago, and went dark. The domain has
    its last report, one pass behind the camera: both alarms are on the list, "known up to" the report. And
    the silence is news in itself — an alarm of its own, "silent since", with the time the report went stale.
    Nobody else polls its ingest either: silent, not merely not reporting."""
    wall = Clock(NOW)
    fed, north, devices, cards, agents, report, reported = _site(wall)
    cards["cam-SN0"].observe(1, NOW - 1500, "door_forced", alarm=True)
    cards["cam-SN0"].observe(1, NOW - 90, "door_forced", alarm=True)
    report()
    DomainAlarms(fed, reported, wall, ref_of=serial_of).list(since=NOW - 3600)            # the domain's pass: it has seen these reports
    devices["cam-SN0"].power_off()
    wall.advance(60)
    report()
    out = DomainAlarms(fed, reported, wall, ref_of=serial_of).list(since=NOW - 3600)
    mine = [(e["kind"], e["t"]) for e in out["events"] if e["member"] == "cam-SN0"]
    assert mine == [("silent", NOW + 45), ("door_forced", NOW - 90), ("door_forced", NOW - 1500)]
    assert [e for e in out["events"] if e["kind"] == "silent"][0]["class"] == "alarm"
    m = out["members"]["cam-SN0"]
    assert (m["state"], m["known_until"], m["silent_since"]) == ("last_report", NOW, NOW + 45)
    assert not out["complete"] and "cam-SN0 silent since" in out["sentence"] and "none known since" in out["sentence"]


def test_a_camera_still_polling_its_ingest_is_alive_and_not_reporting():
    """Its agent stopped — a crash, an expired certificate — and the camera works. The ingest it polls says so
    (`rec/polled`): the poll is kept by the camera's pusher, not by its agent. The alarm is then "not
    reporting", with where and when it was last seen alive: the operator sends somebody to fix software, not
    to look for a broken camera."""
    wall = Clock(NOW)
    fed, north, devices, cards, agents, report, reported = _site(wall)
    DomainAlarms(fed, reported, wall, ref_of=serial_of).list(since=NOW - 60)
    wall.advance(120)
    report(skip=("cam-SN0",))                                            # its agent is gone; the camera is not
    north.objects.put(f"{POLLED}/srt___north_9000", json.dumps({"cluster": "north", "ts": wall(), "units": {"SN0": 2.0}}).encode())
    out = DomainAlarms(fed, reported, wall, ref_of=serial_of).list(since=NOW - 60)
    alarm = [e for e in out["events"] if e["member"] == "cam-SN0"][0]
    assert (alarm["kind"], alarm["alive_at"], alarm["alive_via"]) == ("not_reporting", NOW + 118, "north")
    assert "alive, and not reporting to the domain" in out["sentence"]


def test_the_domain_keeps_a_week_of_what_it_read_and_a_dead_card_takes_nothing_with_it():
    """The page a member reports is a day and a hundred lines. The domain keeps what it read, by day, in its
    own store: two days later the alarm is no longer in any page and still on the list, and it stays there
    when the camera's card dies — for a week, and then it goes."""
    wall = Clock(NOW)
    fed, north, devices, cards, agents, report, reported = _site(wall)
    history = AlarmHistory(north.objects, days=7, wall=wall)
    alarms = lambda: DomainAlarms(fed, reported, wall, history=history, ref_of=serial_of)
    cards["cam-SN1"].observe(1, NOW - 100, "door_forced", alarm=True)
    report()
    alarms().list(since=NOW - 3600)                                      # read: kept
    wall.advance(2 * 86400)
    report()
    got = [e for e in alarms().list(since=NOW - 3600, until=NOW + 1)["events"] if e["member"] == "cam-SN1"]
    assert [(e["kind"], e.get("from_history")) for e in got] == [("door_forced", True)]   # in no page any more
    devices["cam-SN1"].power_off()                                        # the card goes with the camera
    wall.advance(60)
    got = [e for e in alarms().list(since=NOW - 3600, until=NOW + 1)["events"] if e["member"] == "cam-SN1"]
    assert ("door_forced", True) in [(e["kind"], e.get("from_history")) for e in got]
    wall.advance(7 * 86400)
    got = [e for e in alarms().list(since=NOW - 3600, until=NOW + 1)["events"] if e["member"] == "cam-SN1"]
    assert "door_forced" not in [e["kind"] for e in got]                 # a week, and then it goes


def test_a_storm_pushes_its_oldest_out_of_the_history_and_the_list_says_so():
    """The history had no ceiling (feedback BA): a contact bouncing once a second for a week is fifty megabytes for
    one member, read whole by every answer and carried in every backup. Now it keeps the newest `max_lines` and says
    from when it holds the member whole. What a page still shows from before that is not taken back, and a window
    reaching past it is told the week is not complete there."""
    wall = Clock(NOW)
    fed, north, devices, cards, agents, report, reported = _site(wall)
    history = AlarmHistory(north.objects, days=7, wall=wall, max_lines=50)
    alarms = lambda: DomainAlarms(fed, reported, wall, history=history, ref_of=serial_of)
    for i in range(100):
        cards["cam-SN1"].observe(1, NOW - 1000 + i, "stream_lost", alarm=True)
    report()
    out = alarms().list(since=NOW - 3600)
    assert len(history.read("cam-SN1", NOW - 3600, wall() + 1)) == 50 and history.cut_before("cam-SN1") == NOW - 950
    assert out["members"]["cam-SN1"]["history_cut_before"] == NOW - 950
    assert "cam-SN1 had an alarm storm" in out["sentence"]
    key = "domain/alarm-history/cam-SN1"
    raw = north.objects.get(key)
    assert history.keep("cam-SN1", alarms().doors("cam-SN1").alarms(NOW - 3600, NOW + 1, 100)["events"]) == 0
    assert north.objects.get(key) == raw                                  # the fifty let go stay let go
    assert "history_cut_before" not in alarms().list(since=NOW - 900)["members"]["cam-SN1"]
    north.objects.put(key, json.dumps([{"t": NOW - 10, "kind": "tamper", "class": "alarm"}]).encode())
    assert [e["kind"] for e in history.read("cam-SN1", NOW - 60, NOW)] == ["tamper"]   # the first form still reads


def test_a_member_never_heard_from_is_named_not_read_as_quiet():
    wall = Clock(NOW)
    fed, north, devices, cards, agents, report, reported = _site(wall)
    fed.add(member_copy("cam-SN9", north.objects, wall=wall))            # admitted, and never reported
    out = DomainAlarms(fed, reported, wall, ref_of=serial_of).list(since=NOW - 3600)
    assert out["members"]["cam-SN9"]["state"] == "unreachable"
    assert "cam-SN9 has never reported to the domain" in out["sentence"]


def test_a_storm_on_one_camera_does_not_push_the_others_off_the_page():
    """One camera raising a hundred and fifty alarms in an hour is a camera with a problem, and it is one
    line of news. Each member is asked for at most a page; the one that had more says so; the alarm from
    the quiet camera next to it is still on the list."""
    wall = Clock(NOW)
    fed, north, devices, cards, agents, report, reported = _site(wall)
    for i in range(150):
        cards["cam-SN1"].observe(1, NOW - 3000 + i * 10, "stream_lost", alarm=True)
    cards["cam-SN0"].observe(1, NOW - 3500, "door_forced", alarm=True)
    report()
    out = DomainAlarms(fed, reported, wall, per_member=100).list(since=NOW - 3600)
    assert ("cam-SN0", "door_forced") in [(e["member"], e["kind"]) for e in out["events"]]
    assert out["members"]["cam-SN1"]["truncated"] and not out["members"]["cam-SN0"]["truncated"]
    assert "cam-SN1 had more alarms than one page holds" in out["sentence"]
