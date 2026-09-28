"""Lesson 14 — alarms from every member.

One list of alarms across cameras that are each their own cluster: merged by the domain from the alarm page
each member's agent leaves in its report (Lesson 10, step 7), newest first, with what it could not hear said
as part of the answer. And a second copy, because the camera that is off is the camera whose last alarms
matter: a neighbour keeps its closed alarm buckets, pulled through the camera's door — member to member, on
the site — never pushed, reports it as a page of its own, and the list says up to when the copy knows.
"""
from cluster.variables import FakeVariables

from domain.agent import DomainAgent
from domain.alarms import Card, DomainAlarms, EventDoor, MirrorPlan, ReportedDoor, mirror_once, pages
from domain.device import DeviceCluster
from domain.federation import Federation
from domain.uplink import member_copy
from tests.conftest import Clock, make_cluster

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
        devices[d.name], cards[d.name] = d, Card()
        agents[d.name] = DomainAgent(d.name, north.vars, d.flash, now=wall, domain_objects=north.objects,
                                     published=d.local_objects(),
                                     pages=lambda d=d: pages(cards[d.name], d.flash.get("domain/mirrors")[0], wall()))
    site = lambda name: EventDoor(devices[name], cards[name])          # a camera's door: for its neighbours
    plan = MirrorPlan(north.vars, copies=1)
    plan.publish(fed)

    def report(skip=()):                                               # every camera that is on: one pass of its agent
        for name, a in agents.items():
            if devices[name].door_open and name not in skip:
                a.sync()

    report()                                                           # carries `domain/mirrors` home
    reported = lambda name: ReportedDoor(name, north.objects, wall=wall)
    return fed, north, devices, cards, site, plan, report, reported


def test_one_list_newest_first_each_line_naming_its_member():
    wall = Clock(NOW)
    fed, north, devices, cards, site, plan, report, reported = _site(wall)
    cards["cam-SN0"].observe(1, NOW - 1500, "door_forced", alarm=True)
    cards["cam-SN1"].observe(1, NOW - 900, "stream_lost", alarm=True)
    cards["cam-SN2"].observe(1, NOW - 100, "tamper", alarm=True)
    cards["cam-SN2"].observe(1, NOW - 90, "motion")                       # an observation: not an alarm
    report()
    out = DomainAlarms(fed, reported, plan, wall).list(since=NOW - 3600)
    assert [(e["member"], e["kind"]) for e in out["events"]] == [("cam-SN2", "tamper"), ("cam-SN1", "stream_lost"), ("cam-SN0", "door_forced")]
    assert out["complete"] and out["sentence"] == "every member answered"


def test_a_member_that_is_off_is_answered_from_its_last_report_and_its_neighbours_copy():
    """SN0 raised an alarm twenty-five minutes ago and another a minute and a half ago, and then went off. Its
    neighbour on the same network had pulled its closed buckets — the second alarm was in the open bucket, in no
    copy. But the domain still has SN0's LAST report, one agent pass behind the camera, and the second alarm is
    in its page (feedback AR). The list takes both sources, says so, and says up to when: the later of the two,
    here the report."""
    wall = Clock(NOW)
    fed, north, devices, cards, site, plan, report, reported = _site(wall)
    cards["cam-SN0"].observe(1, NOW - 1500, "door_forced", alarm=True)
    cards["cam-SN0"].observe(1, NOW - 90, "door_forced", alarm=True)
    holder = plan.holders("cam-SN0")[0]
    assert holder == "cam-SN1"                                             # the neighbour on vlan:a
    assert mirror_once(cards[holder], devices[holder].flash, site, NOW) == 1
    report()
    DomainAlarms(fed, reported, plan, wall).list(since=NOW - 3600)     # the domain's pass: it has seen these reports
    devices["cam-SN0"].power_off()
    wall.advance(60)                                                   # silent: its last report is too old
    report()                                                           # the others go on reporting, the copy included

    out = DomainAlarms(fed, reported, plan, wall).list(since=NOW - 3600)
    mine = [(e["t"], e.get("from_mirror_on")) for e in out["events"] if e["member"] == "cam-SN0"]
    assert mine == [(NOW - 90, None), (NOW - 1500, None)]              # both: its own word, in its last report
    m = out["members"]["cam-SN0"]
    assert (m["state"], m["via"], m["last_report_until"], m["known_until"]) == ("mirror", "cam-SN1", NOW, NOW)
    assert not out["complete"]
    assert "cam-SN0 silent — its alarms from its last report and the copy on cam-SN1, known up to" in out["sentence"]
    assert "none known since" in out["sentence"]


def test_a_camera_that_lost_its_road_to_the_domain_is_known_from_the_copy_and_so_is_a_quiet_one():
    """What the copy is for once the last report exists: the camera works, the site works, and only its road to
    the domain is gone — its agent stopped. The neighbour goes on pulling through the camera's door. An alarm
    after the last report reaches the list from the copy, and "known up to" moves with the copy: the keeper keeps
    the boundary the source named at every pull (feedback AR), so it moves on for a quiet camera too, one with
    no bucket at all in the interval."""
    wall = Clock(NOW)
    fed, north, devices, cards, site, plan, report, reported = _site(wall)
    holder = plan.holders("cam-SN0")[0]
    report()
    DomainAlarms(fed, reported, plan, wall).list(since=NOW - 3600)
    wall.advance(500)
    cards["cam-SN0"].observe(1, wall(), "door_forced", alarm=True)       # after its last report
    wall.advance(600)                                                    # …and its bucket has closed
    mirror_once(cards[holder], devices[holder].flash, site, wall())
    report(skip=("cam-SN0",))                                            # its agent is gone; the camera is not
    out = DomainAlarms(fed, reported, plan, wall).list(since=NOW - 3600)
    assert [(e["t"], e["from_mirror_on"]) for e in out["events"] if e["member"] == "cam-SN0"] == [(NOW + 500, "cam-SN1")]
    m = out["members"]["cam-SN0"]
    assert (m["last_report_until"], m["known_until"]) == (NOW, 1_002_000.0)    # the copy knows more than the report

    wall.advance(1200)                                                   # twenty quiet minutes: nothing raised
    mirror_once(cards[holder], devices[holder].flash, site, wall())
    report(skip=("cam-SN0",))
    out = DomainAlarms(fed, reported, plan, wall).list(since=NOW - 3600)
    assert out["members"]["cam-SN0"]["known_until"] == 1_003_200.0       # looked at, not stuck at its last alarm


def test_a_member_with_no_reachable_copy_is_answered_from_its_last_report_and_one_never_heard_is_missing():
    """SN2 and its keeper are both off. Its alarms are still on the list — from its last report, and said to be
    so. What is truly missing is a member the domain has never heard from and nobody keeps a copy of: named,
    never read as quiet."""
    from domain.uplink import member_copy as copy_of
    wall = Clock(NOW)
    fed, north, devices, cards, site, plan, report, reported = _site(wall)
    cards["cam-SN2"].observe(1, NOW - 1500, "tamper", alarm=True)
    holder = plan.holders("cam-SN2")[0]
    report()
    DomainAlarms(fed, reported, plan, wall).list(since=NOW - 3600)     # the domain's pass: it has seen these reports
    devices["cam-SN2"].power_off(); devices[holder].power_off()
    fed.add(copy_of("cam-SN9", north.objects, wall=wall))              # admitted, and never reported
    wall.advance(60)
    report()
    out = DomainAlarms(fed, reported, plan, wall).list(since=NOW - 3600)
    assert out["members"]["cam-SN2"]["state"] == "last_report"
    assert ("cam-SN2", "tamper") in [(e["member"], e["kind"]) for e in out["events"]]
    assert "cam-SN2 silent — its alarms from its last report, known up to" in out["sentence"]
    assert out["members"]["cam-SN9"]["state"] == "unreachable"
    assert "cam-SN9 off, and no copy of its alarms could be reached" in out["sentence"]


def test_the_copy_is_closed_alarm_buckets_only_and_taking_it_twice_takes_nothing():
    """Closed: an open bucket is still being written, and a copy of it would be a copy of half of it. Alarm
    lines only: a neighbour's flash is not a second card. And because a closed bucket never changes, the
    second pass finds everything already there and copies nothing."""
    wall = Clock(NOW)
    fed, north, devices, cards, site, plan, report, reported = _site(wall)
    src, holder = cards["cam-SN0"], plan.holders("cam-SN0")[0]
    src.observe(1, NOW - 2500, "door_forced", alarm=True)
    src.observe(1, NOW - 2400, "motion")
    src.observe(1, NOW - 1800, "motion")                                  # a closed bucket with no alarm in it
    src.observe(1, NOW - 50, "door_forced", alarm=True)                   # the open bucket
    assert mirror_once(cards[holder], devices[holder].flash, site, NOW) == 1
    assert mirror_once(cards[holder], devices[holder].flash, site, NOW) == 0
    copy = cards[holder].mirrored("cam-SN0", 0, NOW + 1, 100)["events"]
    assert [(e["t"], e["kind"]) for e in copy] == [(NOW - 2500, "door_forced")]


def test_who_keeps_whose_copy_is_stable_as_the_site_grows():
    """Three hundred cameras on three networks, one copy each, kept by a camera on the same network. Add
    one camera and the plan changes where the newcomer outranks an existing holder — a handful of pairs,
    not a reshuffle of three hundred copies across the site's uplinks."""
    plan = MirrorPlan(FakeVariables(), copies=1)
    members = {f"cam-SN{i:03d}": frozenset({f"vlan:{i % 3}"}) for i in range(300)}
    before = plan.choose(members)
    assert all(a not in bs and members[a] & members[bs[0]] for a, bs in before.items())
    members["cam-SN999"] = frozenset({"vlan:0"})
    after = plan.choose(members)
    moved = [a for a in before if before[a] != after[a]]
    assert len(moved) <= 5


def test_a_storm_on_one_camera_does_not_push_the_others_off_the_page():
    """One camera raising a hundred and fifty alarms in an hour is a camera with a problem, and it is one
    line of news. Each member is asked for at most a page; the one that had more says so; the alarm from
    the quiet camera next to it is still on the list."""
    wall = Clock(NOW)
    fed, north, devices, cards, site, plan, report, reported = _site(wall)
    for i in range(150):
        cards["cam-SN1"].observe(1, NOW - 3000 + i * 10, "stream_lost", alarm=True)
    cards["cam-SN0"].observe(1, NOW - 3500, "door_forced", alarm=True)
    report()
    out = DomainAlarms(fed, reported, plan, wall, per_member=100).list(since=NOW - 3600)
    assert ("cam-SN0", "door_forced") in [(e["member"], e["kind"]) for e in out["events"]]
    assert out["members"]["cam-SN1"]["truncated"] and not out["members"]["cam-SN0"]["truncated"]
    assert "cam-SN1 had more alarms than one page holds" in out["sentence"]
