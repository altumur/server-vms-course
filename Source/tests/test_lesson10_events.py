"""Lesson 10 — events, and the tree that is their index. An event is an
observation, written by the worker holding a unit's epoch into that unit's
bucket on the resource (Lesson 3); the resource PROCESS reads its own tree
where it lies and serves it; the console holds nothing and asks. Three
subsystems' events land on one camera's timeline, fenced by their own
epochs; a fresh index over the same tree gives the same answer; retention on
the resource takes the events with the file."""
import json
import os
import urllib.error
import urllib.request

from w2cplatform.eventdatabase import EventIndex, MergedIndex
from w2cplatform.resource import resources_seen, serve as serve_resource
from w2cplatform.spec import SpecController
from vms.config import DET_SPEC, LIVE_SPEC, SPEC
from vms.console import serve
from vms.controller import VmsController
from vms.detworker import DetWorker
from w2cplatform.resource import platform_resource
from vms.worker import FakeActuator, VmsWorker
from tests.conftest import as_kept
from tests.vmsconftest import Box


def call(base, method, path, body=None, headers=None):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def _console_over(box, db, per_minute: float = 0.0):
    """A console whose index is this one database — enough to ask it what an
    operator would be shown, without a second process."""
    from w2cplatform.console import SpecConsole
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    return SpecConsole(ctl, index=db, wall=box.wall, per_minute=per_minute)


def _resource_process(box):
    """What `python3 -m w2cplatform resource` does: the platform's Resource with what the specs hold,
    served over HTTP, heartbeating so the console can find it, its index over the tree."""
    res = platform_resource(box.resource_root, "srv-1", "", box.vars, box.objects, wall=box.wall)
    rsrv = serve_resource(res, "127.0.0.1", 0)
    res.url = f"http://127.0.0.1:{rsrv.server_address[1]}"
    res.heartbeat()
    return res, rsrv


def test_three_subsystems_events_reach_one_timeline_through_the_resource_process_and_the_console():
    box = Box()
    ctl = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    con_vars = box.vars.as_writer("console", SPEC.acl_console() + LIVE_SPEC.acl_console() + DET_SPEC.acl_console())
    con = VmsController(con_vars, box.objects, wall=box.wall)
    det_ctl = SpecController(DET_SPEC, box.vars.as_writer("detcontroller", DET_SPEC.acl_controller()), box.objects, wall=box.wall)
    w = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1", resource_root=box.resource_root)
    w.heartbeat_once(); con.create_camera({"name": "gate", "source": "driverpack://file/gate.mp4"}); ctl.ensure_placed(); w.reconcile_once(); w.heartbeat_once()
    res, rsrv = _resource_process(box)
    assert list(resources_seen(box.objects)) == ["srv-1"]                                  # the console finds the resource by its heartbeat
    srv = serve(con, box.resource_root, port=0, wall=box.wall,
                mounts={"det": SpecController(DET_SPEC, con_vars, box.objects, wall=box.wall)})   # no database here: the default MergedIndex asks srv-1
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        gpu = DetWorker("d-1", box.vars.as_writer("detworker", ["det/epoch/*", "det/slots/*"]), box.objects, capacity=8,
                        clock=box.clock, wall=box.wall, server="srv-1", resource_root=box.resource_root, env={"LABELS": "gpu"})
        gpu.heartbeat_once()
        call(base, "POST", "/det/units", {"name": "1-linecross", "cam": "1", "kind": "linecross"}, {"Idempotency-Key": "k1"})
        det_ctl.ensure_placed(); gpu.reconcile_once()
        for _ in range(3):
            box.wall.advance(2); gpu.reconcile_once()                                    # one event, on the third pass
        # the operator marks a moment, and the camera goes silent: three subsystems' events on one resource
        call(base, "POST", "/marks", {"unit": "vms/1", "note": "check this"}, {"Idempotency-Key": "m1", "X-User": "murat"})
        w.actuator.dead.append(1); w.pump_once()
        st, out = call(base, "GET", "/events?unit=vms/1"); ev = out["events"]             # nobody tailed, nobody told: the files, as they are
        assert st == 200 and out["state"] == "live"
        assert [(e["subsystem"], e["kind"], e["server"], e["fenced"]) for e in ev] == [
            ("det", "linecross", "srv-1", False), ("console", "mark", "srv-1", False), ("vms", "silent", "srv-1", False)]
        assert ev[0]["unit"] == "det/1-linecross" and ev[0]["of"] == "vms/1" and ev[0]["pass"] == 3 and ev[0]["epoch"] == 1 and ev[1]["user"] == "murat"
        # the page shows all of it: the events under the timeline, the live feed beside the picture, the Mark button —
        # the VMS's page over the platform's console module, which draws the servers and the journal
        page = urllib.request.urlopen(base + "/").read().decode()
        assert 'id="events"' in page and 'id="livefeed"' in page and "/marks" in page and "/platform/console.js" in page
        # the same answer under the mount: /det/events fences by det's epochs too
        assert call(base, "GET", "/det/events?unit=vms/1&subsystem=det")[1]["events"][0]["kind"] == "linecross"
        # an open bucket keeps growing: the next event is in the next answer — the file is looked at, not remembered
        for _ in range(3):
            box.wall.advance(2); gpu.reconcile_once()
        assert len(call(base, "GET", "/events?unit=vms/1&subsystem=det")[1]["events"]) == 2
        # another detector instance takes the unit's epoch: the first one's events are fenced, nobody else's
        box.vars.put("det/epoch/1-linecross", {"epoch": "2"})
        assert [(e["subsystem"], e["fenced"]) for e in call(base, "GET", "/events?unit=vms/1")[1]["events"]] == [
            ("det", True), ("console", False), ("vms", False), ("det", True)]
        # the resource process stops: the console says so by name, and answers with what it has — nothing
        rsrv.shutdown(); rsrv.server_close()
        st, out = call(base, "GET", "/events?unit=vms/1")
        assert st == 200 and out["events"] == [] and out["state"] == "live; srv-1 unreachable"
    finally:
        srv.shutdown(); srv.server_close()


def test_the_index_is_the_tree_and_retention_takes_the_events_with_the_file():
    """No store between the buckets and the answer: a fresh index over the same
    tree gives the same rows, with nothing rebuilt; the resource's retention pass
    removes a bucket file and its events go with it — the console just asks."""
    from vms.archive import event_log
    box = Box(); t = box.wall() - 3 * 86400
    event_log(box.resource_root, 7, 1).append(t + 10, "motion", zone="gate")                  # three days old: past a 1-day policy
    event_log(box.resource_root, 7, 1).append(box.wall() - 100, "motion")                      # fresh
    res = platform_resource(box.resource_root, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    res.heartbeat()
    assert res.index.listing() == {"units": 1, "buckets": 2, "mirrored": [], "cached": 0} and res.index.state == "live"
    again = EventIndex(box.resource_root, "srv-1", wall=box.wall)
    assert again.query(0, 1e12)["events"] == res.index.query(0, 1e12)["events"]          # nothing of its own: two indexes, one tree
    m = MergedIndex(box.objects, fetch=lambda url, p: res.index.query(float(p["from"]), float(p["to"]), unit=p.get("unit")), wall=box.wall)
    assert [e["t"] for e in m.query(0, 1e12, unit="vms/7")["events"]] == [t + 10, box.wall() - 100]
    box.vars.put("vms/retention/7", {"days": "1"})                                        # the VMS's policy for its unit, as a row the platform reads
    assert res.retain() == 1                                                              # the file went — and its events with it
    assert [e["t"] for e in m.query(0, 1e12, unit="vms/7")["events"]] == [box.wall() - 100]
    assert box.vars.list("vms/events") == [] and box.objects.list("vms/events") == []     # nothing about events in any store


def test_a_torn_last_line_loses_the_line_not_the_bucket():
    """`append` writes and flushes without `fsync`, so a crash can leave the last line
    half-written. That is the accepted loss — and it must be the same SHAPE as the one
    for footage: the open thing, not the day. A bucket of ten minutes' observations is
    not thrown away because one record was damaged; the torn line is skipped and
    counted, and the index over it answers everything that did land."""
    import w2cplatform.events as ev
    from w2cplatform.events import EventLog, read_bucket
    from tests.vmsconftest import Box

    box = Box()
    log = EventLog(box.resource_root, "vms", "8123", 7, 600)
    for i in range(5):
        p = log.append(1000.0 + i, "motion", score=i)
    with open(p, "a") as f:                                   # the writer died mid-append
        f.write('{"t": 1005.0, "kind": "mot')

    before = ev.torn
    rows = read_bucket(p)
    assert [r["score"] for r in rows] == [0, 1, 2, 3, 4]      # every whole line survives
    assert ev.torn == before + 1                              # and the damage is counted, not silent

    db = EventIndex(box.resource_root, "srv-1", lambda: 2000.0, 600)
    assert len(db.query(0, 1e12, kind=None, subsystem="vms", unit="vms/8123",
                        current_epochs={("vms", "8123"): 7})["events"]) == 5


def _events(box, n, cam=7):
    """`n` observations a second apart in one bucket, numbered so a test can say WHICH ones came back."""
    from vms.archive import event_log
    log = event_log(box.resource_root, cam, 1)
    for i in range(n):
        log.append(1000.0 + i, "motion", n=i)
    db = EventIndex(box.resource_root, "srv-1", wall=box.wall)
    return db


def test_an_overflowing_window_keeps_the_newest_end_and_says_it_was_cut():
    """`LIMIT` with no direction is a question nobody asked: "a thousand of the five
    thousand" means nothing until somebody says WHICH thousand. The database answered
    `ORDER BY t LIMIT ?`, so the rows it dropped were the NEWEST — the end a timeline
    and a scenario are both looking at, and it dropped them without a word.

    Both halves are the fix. The default end is the newest, because nearly everything
    asked of an event log is a form of "what just happened"; and the answer says
    `truncated`, because a decision taken on part of a window must not look like one
    taken on all of it."""
    box = Box()
    db = _events(box, 10)

    rep = db.query(0, 1e12, limit=4)
    assert [e["n"] for e in rep["events"]] == [6, 7, 8, 9]        # the newest four…
    assert [e["t"] for e in rep["events"]] == sorted(e["t"] for e in rep["events"])   # …still ascending by time
    assert rep["truncated"] is True

    whole = db.query(0, 1e12, limit=10)                            # exactly `limit` rows is a WHOLE window:
    assert [e["n"] for e in whole["events"]] == list(range(10))    # the fact is read one row past the limit,
    assert whole["truncated"] is False                             # so "cut" is never a guess from a count


def test_which_end_survives_is_the_callers_and_an_unknown_end_is_refused():
    """The reader that wants the other end — paging forward through an archive from a
    cursor — knows that about itself and says so. It is a choice, so it is refused at the
    door like any other field: an unknown `keep` must not quietly mean the opposite end,
    because that failure is invisible and permanent."""
    box = Box()
    db = _events(box, 10)

    assert [e["n"] for e in db.query(0, 1e12, limit=4, keep="oldest")["events"]] == [0, 1, 2, 3]

    try:
        db.query(0, 1e12, keep="middle"); assert False, "an unknown end was accepted"
    except ValueError as e:
        assert "'newest' or 'oldest'" in str(e) and "middle" in str(e)


def test_the_merge_does_not_cut_the_newest_end_twice():
    """The console's index asks every resource for a window and then cuts the union to
    `limit` again. A limit with no direction therefore dropped the newest end TWICE —
    once per resource, once over the merge — and the second cut is the one no single
    resource could have warned about.

    `truncated` is the union's too: any resource that cut its answer makes the merged
    window partial, and the reader is told that, not which server did it."""
    from w2cplatform.resource import RESOURCES
    box = Box()
    rows = [{"subsystem": "vms", "unit": "7", "cam": 7, "epoch": 1, "t": 1000.0 + i, "kind": "motion",
             "server": f"srv-{i % 2 + 1}", "bucket": f"b-{i % 2 + 1}", "n": i} for i in range(8)]
    for s in ("srv-1", "srv-2"):
        box.objects.put(f"{RESOURCES}/{s}/heartbeat",
                        json.dumps({"server": s, "ts": box.wall(), "url": f"http://{s}"}).encode())

    def fetch(url, p):
        mine = sorted([e for e in rows if e["server"] == url.rsplit("/", 1)[1]], key=lambda e: e["t"])
        lim, keep = int(p["limit"]), p.get("keep", "newest")
        cut = len(mine) > lim
        return {"events": (mine[-lim:] if keep == "newest" else mine[:lim]) if cut else mine,
                "state": "live", "truncated": cut}

    m = MergedIndex(box.objects, fetch=fetch, wall=box.wall)
    rep = m.query(0, 1e12, limit=4)                                # four each, eight merged, four kept
    assert [e["n"] for e in rep["events"]] == [4, 5, 6, 7]         # the newest of the UNION, not of one server
    assert rep["truncated"] is True                                # cut by the merge, though neither resource cut

    assert [e["n"] for e in m.query(0, 1e12, limit=4, keep="oldest")["events"]] == [0, 1, 2, 3]
    assert m.query(0, 1e12, limit=8)["truncated"] is False         # room for both servers' windows


def test_the_operators_timeline_can_ask_for_its_own_window():
    """The sharpest form of the defect was the operator's: `/events` on the console took
    no `limit` at all, so a busy hour came back as its first thousand rows with nothing
    saying so. The timeline now sets its own window, gets the newest end of it, and is
    told when the hour did not fit."""
    box = Box()
    _events(box, 10)
    res, rsrv = _resource_process(box)
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    srv = serve(con, box.resource_root, port=0, wall=box.wall)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        st, rep = call(base, "GET", "/events?from=0&to=1e12&limit=3")
        assert st == 200 and [e["n"] for e in rep["events"]] == [7, 8, 9] and rep["truncated"] is True
        st, rep = call(base, "GET", "/events?from=0&to=1e12&limit=3&keep=oldest")
        assert st == 200 and [e["n"] for e in rep["events"]] == [0, 1, 2]
        st, rep = call(base, "GET", "/events?from=0&to=1e12&keep=middle")   # refused at the door, not read as an end
        assert st == 400 and "middle" in rep["error"]
        st, rep = call(f"{res.url}", "GET", "/events?from=0&to=1e12&keep=middle")
        assert st == 400 and "middle" in rep["error"]               # the resource's door says the same thing
    finally:
        srv.shutdown(); rsrv.shutdown()


def test_a_suppression_rule_is_refused_at_load_when_it_would_drop_more_than_it_says():
    """Suppression drops observations, so its declaration is read strictly rather
    than leniently. Every refusal here is a typo that would otherwise leave a
    subsystem believing it had suppression, or having far more than it asked for —
    and both failures are invisible, because what they produce is a log that looks
    calm."""
    from w2cplatform.spec import SubsystemSpec
    base = {"name": "panel", "unit": {"rows": "panels", "fields": {"host": {"type": "string"}}}, "placement": {"capacity": {"from": "capacity", "default": 4}}}

    spec = SubsystemSpec.from_dict({**base, "events": {"suppress": {"io.input": {"window": 30}}}})
    assert spec.suppress["io.input"].window == 30 and spec.suppress["io.input"].by is None   # every field: the safe default
    assert SubsystemSpec.from_dict(base).suppress == {}                                      # and nothing at all by default

    def refused(rule):
        try:
            SubsystemSpec.from_dict({**base, "events": {"suppress": {"io.input": rule}}})
            raise AssertionError(f"accepted {rule}")
        except ValueError as e:
            return str(e)

    assert "must be positive" in refused({"window": 0})          # the shape a typo takes, read as "no suppression"
    assert "must be positive" in refused({})                     # a rule with no window is a kind not listed here
    assert "would then be the same thing" in refused({"window": 30, "by": []})   # empty `by`: every line collapses into one
    assert "the summary line writes itself" in refused({"window": 30, "by": ["repeats"]})


def test_an_overflowing_window_drops_observations_before_alarms():
    """The class earns its existence here, and nowhere else it could be checked.

    A limit is a budget for a screenful. Spending it on the thousand statistics
    lines that crowded out the one contact that opened is exactly the failure the
    class exists to prevent — and it is the failure the previous fix could not
    reach: keeping the NEWEST end is right when every line is worth the same, and
    the whole point of a class is that they are not.

    Without this ordering `class` would be a word in a file: written, indexed,
    filterable, and changing nothing about what anybody is shown."""
    from w2cplatform.events import ALARM
    from vms.archive import event_log
    box = Box()
    log = event_log(box.resource_root, 7, 1)
    for i in range(20):
        log.append(1000.0 + i, "stats", n=i)                      # the noise, filling the window
    log.append(1001.5, "io.input", ALARM, port="1", value="open")  # one alarm, and an OLD one at that
    db = EventIndex(box.resource_root, "srv-1", wall=box.wall)

    rep = db.query(0, 1e12, limit=5)
    assert rep["truncated"] is True
    kinds = [e["kind"] for e in rep["events"]]
    assert "io.input" in kinds, "the newest five buried the alarm the window existed for"
    assert kinds.count("stats") == 4 and len(kinds) == 5           # the alarm took one seat, the newest noise the rest
    assert [e["t"] for e in rep["events"]] == sorted(e["t"] for e in rep["events"])   # still a timeline
    assert rep["events"][0]["class"] == ALARM                      # …and it is the oldest of the five

    assert all(e["class"] == "observation" for e in db.query(0, 1e12, kind="stats")["events"])
    only = db.query(0, 1e12, cls=ALARM)
    assert [e["kind"] for e in only["events"]] == ["io.input"] and only["truncated"] is False


def test_the_merge_keeps_an_alarm_a_busier_neighbour_would_have_crowded_out():
    """The merge cuts the union a second time, so the policy has to be carried both
    ways: an alarm that survived its own server's window is dropped when it meets a
    louder neighbour's, and no single resource could have warned about that."""
    from w2cplatform.events import ALARM
    from w2cplatform.resource import RESOURCES
    box = Box()
    rows = [{"subsystem": "vms", "unit": "7", "cam": 7, "epoch": 1, "t": 1000.0 + i, "kind": "stats",
             "server": "srv-1", "bucket": "b-1", "class": "observation", "n": i} for i in range(6)]
    rows += [{"subsystem": "vms", "unit": "8", "cam": 8, "epoch": 1, "t": 1000.5, "kind": "io.input",
              "server": "srv-2", "bucket": "b-2", "class": ALARM, "port": "1"}]
    for s in ("srv-1", "srv-2"):
        box.objects.put(f"{RESOURCES}/{s}/heartbeat",
                        json.dumps({"server": s, "ts": box.wall(), "url": f"http://{s}"}).encode())

    def fetch(url, p):
        mine = sorted([e for e in rows if e["server"] == url.rsplit("/", 1)[1]], key=lambda e: e["t"])
        lim = int(p["limit"])
        return {"events": mine[-lim:] if len(mine) > lim else mine, "state": "live", "truncated": len(mine) > lim}

    m = MergedIndex(box.objects, fetch=fetch, wall=box.wall)
    rep = m.query(0, 1e12, limit=3)
    assert rep["truncated"] is True
    assert [e["kind"] for e in rep["events"]].count("io.input") == 1, "the alarm was crowded out by a neighbour"
    assert len(rep["events"]) == 3


def test_a_traffic_class_is_a_declared_value_and_not_a_convention_on_kind():
    """The whole argument for making this a field: a convention refuses nothing.
    "Kinds beginning with io. are alarms" reads whatever is written, so the first
    `IO.input` typed where `io.input` was meant leaves the class in silence and
    stays out of it until somebody reads the file by hand.

    An unknown class is refused where the line is written, and there is exactly one
    spelling of it — a `class` field beside a `cls` argument would be two names for
    one thing, and they drift."""
    from w2cplatform.events import EventLog
    box = Box()
    log = EventLog(box.resource_root, "vms", "7", 1)

    try:
        log.append(1000.0, "io.input", "Alarm")
        raise AssertionError("an unknown class was written")
    except ValueError as e:
        assert "'Alarm'" in str(e) and "alarm, observation" in str(e)

    try:
        log.append(1000.0, "io.input", **{"class": "alarm"})
        raise AssertionError("a second spelling was accepted")
    except ValueError as e:
        assert "two spellings" in str(e)

    from w2cplatform.events import read_bucket
    p = log.append(1000.0, "silent")
    assert "class" not in read_bucket(p)[0], "an observation says nothing: it is nearly every line"


def test_past_the_norm_the_timeline_counts_instead_of_listing():
    """A norm nobody acts on is a comment. Written down and never consulted, it
    prevents nothing: the storm still turns every alarm into wallpaper until the
    operator stops reading, which is the failure the whole event path exists to
    avoid, arriving through the front door instead of through a lost write.

    So the number does something. Past it the screen stops showing lines and
    starts showing counts — `(subsystem, unit, kind, class)` with how many and
    between when and when, the same three numbers a suppressed window reports one
    layer down, and alarms in their own groups so they still come first."""
    from w2cplatform.events import ALARM
    from vms.archive import event_log
    box = Box(); t = box.wall() - 60
    log = event_log(box.resource_root, 7, 1)
    for i in range(90):
        log.append(t + i * 0.5, "stats", n=i)
    for i in range(3):
        log.append(t + 10 + i, "io.input", ALARM, port="1", value="open")
    db = EventIndex(box.resource_root, "srv-1", wall=box.wall)
    con = _console_over(box, db)

    quiet = con.timeline(db.query(0, t + 5), 0, t + 5)             # a handful over a long window
    assert quiet["aggregated"] is False and quiet["events"] and "groups" not in quiet

    busy = con.timeline(db.query(t, t + 60), t, t + 60)            # ninety-three in a minute, norm sixty
    assert busy["aggregated"] is True and busy["events"] == []
    assert busy["rate_per_minute"] > busy["per_minute"]
    assert [g["kind"] for g in busy["groups"]] == ["io.input", "stats"], "the alarm group is not first"
    assert busy["groups"][0]["count"] == 3 and busy["groups"][1]["count"] == 90
    assert busy["groups"][0]["until"] - busy["groups"][0]["since"] == 2.0


def test_the_norm_is_the_operators_and_a_process_still_gets_every_line():
    """The line worth naming: the index answers processes, and a process reads a
    thousand lines as easily as ten. The evaluator asks the same merge and must
    keep getting every one of them — a scenario that missed its event is the
    failure this path exists to prevent, and it would be a strange way to fail, by
    protecting a machine's attention.

    Only the reader who tires gets counts. So the aggregation lives on the console
    and not in the index, and the norm is a number rather than a constant: a
    control room with four screens and a guard with a phone are not one reader."""
    from vms.archive import event_log
    box = Box(); t = box.wall() - 60
    log = event_log(box.resource_root, 7, 1)
    for i in range(90):
        log.append(t + i * 0.5, "stats", n=i)
    db = EventIndex(box.resource_root, "srv-1", wall=box.wall)

    assert len(db.query(t, t + 60)["events"]) == 90                # the index never aggregates
    assert "aggregated" not in db.query(t, t + 60)

    patient = _console_over(box, db, per_minute=1000)
    assert patient.timeline(db.query(t, t + 60), t, t + 60)["aggregated"] is False


def test_an_alarm_is_written_down_and_an_observation_is_only_flushed():
    """The trade the course made for observations — flushed, not synced: survives
    the process dying, not the power going — was made on purpose, and it is the
    same shape as the accepted loss for footage. It is not the right trade for an
    alarm: a line that only reached the page cache is not written down, and losing
    it is losing the thing the system is for.

    Two things this test pins that "just add fsync" misses. `os.fsync` on macOS
    returns without the drive flushing its own cache, so the durable path has to
    ask for `F_FULLFSYNC` and fall back rather than assume. And a file is not
    durable until the DIRECTORY ENTRY naming it is — otherwise a power cut leaves
    the bytes with nothing pointing at them, which is the torn line one level up."""
    import w2cplatform.events as ev
    from w2cplatform.events import ALARM, EventLog
    box = Box()
    log = EventLog(box.resource_root, "vms", "7", 1)
    synced, dirs = [], []
    real_durably, real_dir = ev.durably, ev.durable_dir
    ev.durably = lambda f: synced.append(f.name)
    ev.durable_dir = lambda d: dirs.append(d)
    try:
        p = log.append(1000.0, "stats", n=1)                       # an observation pays nothing…
        assert synced == [] and dirs == []                         # …including for the file it just created
        pa = log.append(1001.0, "io.input", ALARM, port="1")
        epoch_dir = os.path.dirname(pa)
        unit_dir_ = os.path.dirname(epoch_dir)
        assert synced == [pa] and dirs == [epoch_dir, unit_dir_, os.path.dirname(unit_dir_), box.resource_root]   # the alarm pays for
        log.append(1002.0, "io.input", ALARM, port="1")             # both, the entries included: the file's, and every new
        assert synced == [pa, pa] and len(dirs) == 4                # directory's up to the root — and once per bucket is enough
        # ten minutes on, the NEXT bucket in the same `e1` (the review's third pass): its entry is synced too — once
        # per directory synced the first bucket's and none after it
        pb = log.append(1001.0 + 600, "io.input", ALARM, port="1")
        assert pb != pa and os.path.dirname(pb) == epoch_dir and dirs[4:] == [epoch_dir]
    finally:
        ev.durably, ev.durable_dir = real_durably, real_dir

    # …and the alarm lies in a tree of its own (feedback BO): the same shape, another first directory
    from w2cplatform.events import read_bucket
    assert os.path.relpath(p, box.resource_root).startswith("vms/7/e1/") and os.path.relpath(pa, box.resource_root).startswith("vms.alarms/7/e1/")
    assert [r["kind"] for r in read_bucket(p)] == ["stats"] and [r["kind"] for r in read_bucket(pa)] == ["io.input", "io.input"]


def test_every_directory_above_a_durable_line_is_synced_up_to_the_root_once():
    """The review's fourth pass (Т-m3's remainder). The first durable line of a unit creates `<sub>/<unit>/e<epoch>/`
    in one go, and only `e<epoch>`'s entry (in `<unit>`) was synced: `<unit>`'s entry in `<sub>` and `<sub>`'s in the
    root stayed in the cache, and after a power cut the bytes were on the medium with no path to them. Every directory
    from the bucket's up to the tree's root is synced the first time a writer makes a durable line there — also when
    an observation created them a moment before and paid for nothing — and never again by that writer."""
    import w2cplatform.events as ev
    from w2cplatform.events import EventLog
    box = Box()
    real_durably, real_dir = ev.durably, ev.durable_dir
    dirs = []
    ev.durably, ev.durable_dir = (lambda f: None), (lambda d: dirs.append(os.path.abspath(d)))
    try:
        log = EventLog(box.resource_root, "journal", "srv-1", 3)
        p = log.append(1000.0, "stats", n=1)                       # an observation makes the directories, and pays nothing
        assert dirs == []
        log.append(1001.0, "unit.deleted", durable=True, target="7")   # the journal's line: durable
        e = os.path.dirname(os.path.abspath(p))
        assert dirs == [e, os.path.dirname(e), os.path.dirname(os.path.dirname(e)), os.path.abspath(box.resource_root)]
        log.append(1002.0, "unit.deleted", durable=True, target="8")
        assert len(dirs) == 4                                       # once per writer: the chain is not walked again
    finally:
        ev.durably, ev.durable_dir = real_durably, real_dir


def test_the_durable_write_reaches_the_medium_or_says_it_could_not():
    """`durably` is one line only if you do not look at it. Plain `fsync` is the
    call everybody reaches for and the one that, on this platform, returns before
    the drive has flushed anything — so the strongest available barrier is asked
    for first and the fallback is what makes the code portable, not what makes it
    correct."""
    import w2cplatform.events as ev
    box = Box()
    p = os.path.join(box.resource_root, "sync-probe")
    os.makedirs(box.resource_root, exist_ok=True)
    with open(p, "w") as f:
        f.write("x"); f.flush()
        ev.durably(f)                                              # whichever path, it must not raise
    assert open(p).read() == "x"

    class _NoFcntl:
        def fileno(self): raise ValueError("closed")
    try:
        ev.durably(_NoFcntl())                                     # a fallback that cannot work is not silent
        raise AssertionError("a file that cannot be synced was reported as synced")
    except ValueError:
        pass


def test_the_timeline_endpoint_hands_the_page_counts_and_says_why():
    """The shape the page depends on, checked through HTTP rather than on the
    method, because the bug this guards against was in the WIRING: a console that
    starts returning `events: []` to a page reading `d.events` blanks the operator's
    timeline exactly when it is busiest, which is worse than the flood it replaced.

    So the reply says three things at once — the counts, the rate, and the norm —
    and the page has something to draw and a sentence to show for why it changed
    shape."""
    from vms.archive import event_log
    box = Box(); t = box.wall() - 60
    log = event_log(box.resource_root, 7, 1)
    for i in range(90):
        log.append(t + i * 0.5, "stats", n=i)
    res, rsrv = _resource_process(box)
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    srv = serve(con, box.resource_root, port=0, wall=box.wall)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        st, rep = call(base, "GET", f"/events?from={t}&to={t + 60}")
        assert st == 200 and rep["aggregated"] is True
        assert rep["events"] == [] and [g["count"] for g in rep["groups"]] == [90]
        assert rep["rate_per_minute"] > rep["per_minute"] == 60.0
        st, quiet = call(base, "GET", f"/events?from=0&to={t + 60}")     # the same rows over a long window
        assert st == 200 and quiet["aggregated"] is False and len(quiet["events"]) == 90
    finally:
        srv.shutdown(); rsrv.shutdown()


def test_the_timeline_reads_every_epoch_once_in_a_while_and_a_cameras_timeline_only_its_own():
    """The review's second pass, major: every `GET /events` listed the WHOLE store and read every epoch row —
    a thousand cameras, a page polling every three seconds, ten operators: thousands of reads a second to the
    store, the leases' CAS queueing behind them. The map is cached for `EPOCH_CACHE` seconds of the console's
    monotonic clock; a camera's or one unit's timeline makes no scan at all — it reads, by name and now, the
    epochs of the units in its answer, so a fence that fell a moment ago still shows."""
    from vms.archive import event_log
    box = Box(); t = box.wall() - 60
    event_log(box.resource_root, 7, 1).append(t + 1, "motion"); box.vars.put("vms/epoch/7", {"epoch": "1"})
    event_log(box.resource_root, 9, 1).append(t + 2, "motion"); box.vars.put("vms/epoch/9", {"epoch": "2"})   # a zombie's line: epoch 1 < 2
    con = _console_over(box, EventIndex(box.resource_root, "srv-1", wall=box.wall))
    con.clock = box.clock

    class Counting:
        """The console's store, counting what the review counted: scans of the whole store, and epoch rows read."""
        def __init__(self, inner): self.inner, self.scans, self.epochs = inner, 0, 0
        def list(self, prefix): self.scans += prefix == ""; return self.inner.list(prefix)
        def get(self, path): self.epochs += "/epoch/" in path; return self.inner.get(path)
        def __getattr__(self, name): return getattr(self.inner, name)

    vars_ = con.ctl.vars = Counting(con.ctl.vars)

    class H:
        headers: dict = {}
        def _send(self, status, body, raw=False): self.reply = (status, body)

    def ask(**q):
        h = H(); con.dispatch(h, "GET", "/events", {"from": str(t), "to": str(t + 60), **q}); return h.reply

    fenced = lambda rep: [(e["unit"].split("/")[1], e["fenced"]) for e in rep[1]["events"]]
    assert fenced(ask()) == [("7", False), ("9", True)] and (vars_.scans, vars_.epochs) == (1, 2)
    assert fenced(ask()) == [("7", False), ("9", True)] and (vars_.scans, vars_.epochs) == (1, 2)   # a second request: the cache
    box.clock.advance(con.EPOCH_CACHE + 1)
    assert fenced(ask()) == [("7", False), ("9", True)] and vars_.scans == 2                   # past the window: read again
    # one camera: no scan, one row — its own — and read now, not from the cache
    vars_.scans = vars_.epochs = 0
    assert fenced(ask(unit="vms/9")) == [("9", True)] and (vars_.scans, vars_.epochs) == (0, 1)
    box.vars.put("vms/epoch/7", {"epoch": "3"})                                                 # the camera's holder changed this instant
    assert fenced(ask(unit="vms/7")) == [("7", True)] and vars_.scans == 0                      # the camera's timeline knows at once…
    assert fenced(ask()) == [("7", False), ("9", True)]                                         # …the whole one, inside its three seconds, not yet
    # the review's third pass, minor: one epoch row that does not parse was no reply at all; now that unit is unfenced
    box.vars.put("vms/epoch/9", {"epoch": "torn"})
    box.clock.advance(con.EPOCH_CACHE + 1)
    rep = ask()
    assert rep[0] == 200 and fenced(rep) == [("7", True), ("9", False)] and "epochs" not in rep[1]
    # …and a store that does not answer the scan: the last map, and the reply says it is the last map
    vars_.list = lambda prefix: (_ for _ in ()).throw(PermissionError(13, "the store does not answer"))
    box.clock.advance(con.EPOCH_CACHE + 1)
    rep = ask()
    assert rep[0] == 200 and fenced(rep) == [("7", True), ("9", False)] and rep[1]["epochs"] == "cached"


def test_a_burst_of_timeline_requests_lists_the_resources_once_in_two_seconds():
    """The product's DD (the course's answer to the fourth review left it open): every `GET /events` learned which
    resources exist by listing `resources/` in the object store and reading every heartbeat there — on every poll
    of every open page. The list is read at most once every `SEEN_FOR` seconds of the merge's monotonic clock; a
    heartbeat comes every few seconds anyway. The resources themselves are asked on every request, as before."""
    from w2cplatform.resource import RESOURCES
    box = Box()
    for server in ("srv-1", "srv-2"):
        res = platform_resource(box.resource_root, server, "", box.vars, box.objects, wall=box.wall)
        res.url = f"http://{server}"
        res.heartbeat()

    class Counting:
        """The console's object store, counting what the review counted: listings of the resources, heartbeats read."""
        def __init__(self, inner): self.inner, self.lists, self.reads = inner, 0, 0
        def list(self, prefix): self.lists += prefix.startswith(RESOURCES); return self.inner.list(prefix)
        def get(self, key): self.reads += key.startswith(RESOURCES); return self.inner.get(key)
        def __getattr__(self, name): return getattr(self.inner, name)

    objects, asked = Counting(box.objects), []
    m = MergedIndex(objects, fetch=lambda url, p: asked.append(url) or {"events": []}, wall=box.wall, clock=box.clock)
    con = _console_over(box, m)
    con.clock = box.clock

    class H:
        headers: dict = {}
        def _send(self, status, body, raw=False): self.reply = (status, body)

    def ask():
        h = H(); con.dispatch(h, "GET", "/events", {"from": str(box.wall() - 60), "to": str(box.wall())}); return h.reply

    assert ask()[0] == 200 and ask()[0] == 200
    assert (objects.lists, objects.reads) == (1, 2)                             # two requests, one listing
    assert sorted(asked) == ["http://srv-1", "http://srv-1", "http://srv-2", "http://srv-2"]   # each resource, each time
    box.clock.advance(m.SEEN_FOR)
    assert ask()[0] == 200 and (objects.lists, objects.reads) == (2, 4)        # past the window: listed again
    # a resource that appears inside the window is seen once the window is over
    late = platform_resource(box.resource_root, "srv-3", "", box.vars, box.objects, wall=box.wall)
    late.url = "http://srv-3"; late.heartbeat()
    ask()
    assert "http://srv-3" not in asked
    box.clock.advance(m.SEEN_FOR)
    ask()
    assert asked[-3:].count("http://srv-3") == 1 and objects.lists == 3


def test_the_consoles_records_outlive_what_they_refer_to():
    """The one rule that has to exist BEFORE the records it protects.

    An operator's record refers to events — a mark names a unit, and an
    acknowledgement, when there is one, names the alarm it answers. The
    reference is one-way, and the asymmetry decides everything: a record that
    outlives what it refers to is harmless clutter, while an event that outlives
    the record ABOUT it goes quietly back to looking unanswered.

    Swept on its own clock, the console's bucket would do exactly that — a year
    later, to the one class of line somebody is going to be asked about. So its
    days are a floor and not a setting: whatever anybody keeps longest, the
    records keep too. It costs almost nothing, because an operator writes a
    handful of lines a day against a worker's thousands."""
    from w2cplatform.events import EventLog
    from w2cplatform.resource import console_floor
    box = Box(); old = box.wall() - 400 * 86400
    event_log = __import__("vms.archive", fromlist=["event_log"]).event_log
    event_log(box.resource_root, 7, 1).append(old, "motion")             # a camera that keeps two years…
    marks = EventLog(box.resource_root, "console", "c-1", 1)
    mark = marks.append(old, "mark", user="anna", note="checked")  # …and the record written the same day
    box.vars.put("vms/retention/7", {"days": "730"})

    res = platform_resource(box.resource_root, "srv-1", "", box.vars, box.objects, wall=box.wall)
    assert res.retain() == 0                                       # neither is old enough yet
    assert os.path.exists(mark)

    box.vars.put("vms/retention/7", {"days": "500"})               # still longer than the console's year
    assert res.retain() == 0 and os.path.exists(mark), "the record was swept while the events it names stayed"

    assert console_floor({("vms", "7"): 500.0, ("console", "c-1"): 365.0}) == 500.0
    assert console_floor({("console", "c-1"): 365.0}) == 0.0       # nothing to outlive: its own days stand


# -- the tree is the index (the notes on the event log's concurrency and load, 28 September) ------------------
def test_an_event_written_into_a_past_bucket_is_in_the_next_answer():
    """A bucket is named by the time of its EVENTS, not of their writing: a scan of an archive (Lesson 21) and a
    survey of somebody else's (Lesson 23) write lines stamped hours ago into buckets whose time is long past. An
    index leaning on "a closed bucket never changes" would never see them. This one asks the file — its size —
    at every query that touches it, and reads only what it had not read."""
    from w2cplatform.events import EventLog
    box = Box()
    now = box.wall()
    scan = EventLog(box.resource_root, "detjob", "7-scan", 1, 600)
    scan.append(now - 7200, "person", n=1)                                       # two hours ago, into a closed bucket
    db = EventIndex(box.resource_root, "srv-1", wall=box.wall)
    window = (now - 7300, now - 7100)
    assert [e["n"] for e in db.query(*window)["events"]] == [1]
    scan.append(now - 7150, "person", n=2)                                       # the scan goes on: the same past bucket grows
    assert [e["n"] for e in db.query(*window)["events"]] == [1, 2]


def test_a_bucket_removed_and_written_again_is_read_as_a_new_file():
    """Retention removed a bucket, and a late scan of the archive wrote the same hour again under the same name —
    as long as the old file, or longer. "Not shorter" is not "the same file grown" (feedback AX): read on from
    the old offset, the index kept the old line and began the new ones mid-line. The file's identity and its
    first bytes are compared as well, and a different file is read from its start."""
    import glob
    from w2cplatform.events import EventLog
    box = Box()
    now = box.wall()
    EventLog(box.resource_root, "detjob", "7-scan", 1, 600).append(now - 7200, "person", n=1)
    db = EventIndex(box.resource_root, "srv-1", wall=box.wall)
    window = (now - 7300, now - 7100)
    assert [e["n"] for e in db.query(*window)["events"]] == [1]
    [path] = glob.glob(os.path.join(box.resource_root, "**", "*.events.jsonl"), recursive=True)
    os.remove(path)                                                              # retention
    again = EventLog(box.resource_root, "detjob", "7-scan", 1, 600)                   # the late scan
    again.append(now - 7190, "person", n=2)
    again.append(now - 7180, "person", n=3)
    assert [e["n"] for e in db.query(*window)["events"]] == [2, 3]
    assert db.torn == 0
    # Written again IN PLACE — the same inode, as a freed one handed straight back would be: only the first
    # bytes tell it from the file the index read.
    with open(path, "r+b") as f:
        body = f.read()
        f.seek(0)
        f.write(body.replace(b'"n": 2', b'"n": 7'))
    again.append(now - 7170, "person", n=4)
    assert [e["n"] for e in db.query(*window)["events"]] == [7, 3, 4]


def test_the_operators_timeline_says_which_servers_a_window_is_missing():
    """The product's console built its `/events` answer itself and dropped the merge's word on completeness
    (feedback AX): a window a server did not answer for looked empty to the operator. Here it is passed on as
    it came — in the plain answer and in the one folded into groups for a busy hour."""
    box = Box()

    class Merge:
        def query(self, t0, t1, *a, **kw):
            evs = [{"t": t0 + i, "subsystem": "vms", "unit": "7", "kind": "motion", "class": "observation"} for i in range(50)]
            return {"events": evs, "state": "live", "complete": False, "incomplete": {"srv-2": "did not answer"}}

    now = box.wall()
    for per_minute in (0.0, 1000.0):                                   # folded, and plain
        con = _console_over(box, Merge(), per_minute=per_minute)
        out = con.timeline(con.index.query(now - 60, now), now - 60, now)
        assert out["complete"] is False and out["incomplete"] == {"srv-2": "did not answer"}


def test_a_query_holds_what_the_answer_can_carry_and_answers_as_before():
    """The cache's ceiling bounds the files held, not the answer: a window with no `from` gathered every matching
    line of the tree and cut it to `limit` at the very end (the platform review; the product's index, feedback
    BD). Now only `limit + 1` rows of each class are held while the window is read. Same answer as the old
    rule — alarms first, then the end `keep` names, then by time — checked on twenty thousand lines; and a door
    clamps a `limit` of a billion to ten thousand."""
    from w2cplatform.doors import MAX_LIMIT
    from w2cplatform.events import ALARM, EventLog
    box = Box()
    now = box.wall()
    log = EventLog(box.resource_root, "vms", "7", 1, 600)
    for i in range(20_000):
        log.append(now - 20_000 + i + 0.5, "motion", n=i)
    for i in range(30):
        log.append(now - 19_000 + i * 600, "door_forced", cls=ALARM, n=i)
    db = EventIndex(box.resource_root, "srv-1", wall=box.wall)
    everything = db.query(0, now + 1, limit=10 ** 9)["events"]
    assert len(everything) == 20_030
    for keep in ("newest", "oldest"):
        for limit in (1000, 20):                                       # 20: fewer than the alarms alone
            ranked = sorted(everything, key=lambda e: (e["class"] != ALARM, -e["t"] if keep == "newest" else e["t"]))
            want = sorted(ranked[:limit], key=lambda e: e["t"])
            got = db.query(0, now + 1, limit=limit, keep=keep)
            assert got["events"] == want and got["truncated"] is True, (keep, limit)
    assert db.query(now - 10, now + 1, limit=1000)["truncated"] is False

    res, rsrv = _resource_process(box)
    try:
        with urllib.request.urlopen(f"{res.url}/events?limit=999999999", timeout=30) as r:
            rep = json.loads(r.read())
        assert len(rep["events"]) == MAX_LIMIT and rep["truncated"] is True
    finally:
        rsrv.shutdown()


def test_a_pass_longer_than_the_pulse_keeps_the_resources_heartbeat_fresh():
    """The pass and the heartbeat share a thread, and the pass reads every bucket it keeps. On a year of archive it
    outlasts `lost_after`: the resource is called silent and the controller moves the recordings off a healthy
    server (the platform review; feedback BE). While the pass runs, the last heartbeat goes out again with the
    time moved on — what was already published, and nothing the pass is changing."""
    import time
    box = Box()
    res, rsrv = _resource_process(box)
    res.clock = box.clock                                             # the pulse's clock is monotonic: the test's own
    try:
        res.PULSE_SECONDS = 0.02
        first = res.heartbeat()

        class Slow:                                                   # a subsystem's own pass, over a long archive
            def pass_(self, now):
                box.wall.advance(100); box.clock.advance(100)
                time.sleep(0.2)
                return {}

        res.kept = as_kept(Slow())                                    # a long step of the pass (the hooks are gone: step 6)
        seen = {}
        mirror = res.mirror
        res.mirror = lambda: seen.update(resources_seen(box.objects)) or mirror()     # the last step of the pass
        res.pass_()
        assert seen["srv-1"]["ts"] == box.wall() and "srv-1" in res.live_resources()   # fresh, while the pass ran
        assert {k: v for k, v in seen["srv-1"].items() if k not in ("ts", "pass_seconds")} == {k: v for k, v in first.items() if k != "ts"}
        assert seen["srv-1"]["pass_seconds"] >= 100                                     # …and says how long the pass has run
        # …and a pass stuck past PULSE_LIMIT × lost_after is SAID, not silent (the review's thirteenth pass, blocker 5):
        # it stopped the pulse, the resource went silent, and a hung worker it ran was moved at 250 s. The beat goes
        # on, the presence looked at anew, and `pass_stuck` says how long the pass has not moved.

        class Stuck(Slow):
            def pass_(self, now):
                box.wall.advance(res.PULSE_LIMIT * res.lost_after + 1); box.clock.advance(res.PULSE_LIMIT * res.lost_after + 1)
                time.sleep(0.2)
                return {}

        res.kept = as_kept(Stuck())
        res.pass_()
        assert seen["srv-1"]["ts"] == box.wall() and "srv-1" in res.live_resources()
        assert seen["srv-1"]["pass_stuck"] > res.PULSE_LIMIT * res.lost_after
        res.heartbeat()
        assert "srv-1" in res.live_resources() and "pass_stuck" not in resources_seen(box.objects)["srv-1"]
    finally:
        rsrv.shutdown()


def test_the_pulse_survives_a_failed_beat_and_stops_on_no_progress_not_on_a_long_pass():
    """The review's third pass. The pulse thread died on its first error — one store write that failed during a
    five-minute pass, and the resource was silent, its recordings moved off a sound server. It counted by the wall
    clock, and stopped at four `lost_after` of TOTAL time, which a big archive legitimately takes. Now a failed beat
    is one beat; the limit is four `lost_after` WITHOUT PROGRESS, by a monotonic clock."""
    import time
    box = Box()
    res, rsrv = _resource_process(box)
    res.clock = box.clock
    try:
        res.PULSE_SECONDS = 0.02
        res.heartbeat()
        real, failed = box.objects.put, []

        def put(key, data, **kw):
            if key.endswith("/heartbeat") and not failed:
                failed.append(key)
                raise OSError("the store blinked")
            return real(key, data, **kw)
        box.objects.put = put

        class Long:                                                   # long in total, and moving all the time
            def pass_(self, now):
                for _ in range(6):
                    box.wall.advance(res.lost_after); box.clock.advance(res.lost_after)
                    res._progressed()                                 # what the walk and the retention say as they go
                    time.sleep(0.1)
                return {}

        res.kept = as_kept(Long())
        seen = {}
        mirror = res.mirror
        res.mirror = lambda: seen.update(resources_seen(box.objects)) or mirror()
        res.pass_()
        assert failed and seen["srv-1"]["ts"] == box.wall() and "srv-1" in res.live_resources()   # beat on after the failure
        assert seen["srv-1"]["pass_seconds"] > res.PULSE_LIMIT * res.lost_after                  # past the old limit, still beating
    finally:
        rsrv.shutdown()


def test_a_mirror_a_hook_and_relieve_that_keep_moving_keep_the_pulse_and_one_that_hangs_stops_it():
    """The review's fourth pass (Т-M13's remainder). Only the walk and the retention said they moved: the mirror, a
    subsystem's own hook and `relieve` did not, so a part that worked the whole time — the FIRST mirroring of a
    server, a year of buckets to its peer — was "stuck" to the pulse after four `lost_after`, and the resource went
    silent with its recordings moved off it. Now each bucket a peer took is progress, `kept` is handed `progressed`,
    and `relieve` marks each volume and each answer. A peer that hangs on one bucket is said (`pass_stuck`), and the
    beat goes on (the review's thirteenth pass, blocker 5: it stopped the pulse, and a hung worker was moved)."""
    import time
    from w2cplatform.events import EventLog
    box = Box()
    res, rsrv = _resource_process(box)
    res.clock = box.clock
    limit = res.PULSE_LIMIT * res.lost_after
    try:
        res.PULSE_SECONDS = 0.02
        for i in range(8):                                            # eight closed buckets for the mirror to send
            EventLog(box.resource_root, "vms", "7", 1).append(box.wall() - 86400 + i * 600, "stats", n=i)
        box.vars.put("platform/mirror", {"enabled": "true", "copies": "1"})
        res.heartbeat()
        seen = {}

        def beat_caught_up(more=lambda b: True, within=10.0):
            """Wait by the condition, not by a sleep: the pulse's thread has written a beat as of the box's clock now
            (and `more` of it holds) — under a loaded machine 0.1 s was sometimes not enough for one beat."""
            end = time.monotonic() + within
            while time.monotonic() < end:
                b = resources_seen(box.objects).get("srv-1") or {}
                if b.get("ts") == box.wall() and more(b):
                    return
                time.sleep(0.005)

        class Peer:                                                   # each copy takes a third of the limit
            took, hang = [], False

            def mirrored(self, url, server):
                return []

            def put(self, url, server, path, data):
                peer_hb()
                box.wall.advance(limit + 1 if self.hang else limit / 3); box.clock.advance(limit + 1 if self.hang else limit / 3)
                beat_caught_up((lambda b: b.get("pass_stuck", 0) > limit) if self.hang else (lambda b: True))
                self.took.append(path)
                seen.update(resources_seen(box.objects))

        def peer_hb():                                                # the peer is live, by its own word, now
            box.objects.put("platform/resources/srv-2/heartbeat",
                            json.dumps({"server": "srv-2", "ts": box.wall(), "url": "http://srv-2"}).encode())
        peer_hb()
        res.peers = peer = Peer()
        res.pass_()
        assert len(peer.took) == 8 and seen["srv-1"]["ts"] == box.wall() and "srv-1" in res.live_resources()

        # what is kept read long, and said as it goes (`kept`, handed `progressed`: the one step of the pass a spec's
        # declaration leaves long — the hooks, a subsystem's pass and its `free`, are gone since the boundary's step 6)
        class Long:
            def pass_(self, now, progressed):
                for _ in range(6):
                    box.wall.advance(limit / 3); box.clock.advance(limit / 3)
                    progressed(); beat_caught_up()
                seen["hook"] = (resources_seen(box.objects)["srv-1"]["ts"], box.wall())
                return {}

        box.vars.put("platform/mirror", {"enabled": "false"})
        res.kept = as_kept(Long())
        res.pass_()
        assert seen["hook"][0] == seen["hook"][1]                     # fresh at its end
        assert "srv-1" in res.live_resources()
        res.kept = lambda progressed=None: (lambda *a: False)

        # …and a peer that hangs on its first bucket is a stuck pass, said — the beat goes on
        box.vars.put("platform/mirror", {"enabled": "true", "copies": "1"})
        box.vars.put("platform/space", {"enabled": "false"})
        for i in range(2):
            EventLog(box.resource_root, "vms", "8", 1).append(box.wall() - 86400 + i * 600, "stats", n=i)
        peer.hang, peer.took = True, []
        peer_hb(); res.heartbeat()
        res.pass_()
        assert peer.took                                              # the peer was asked, and hung
        assert seen["srv-1"]["ts"] == box.wall() and seen["srv-1"]["pass_stuck"] > limit
    finally:
        rsrv.shutdown()


def test_a_walk_over_many_buckets_keeps_the_pulse_with_a_mark_per_bucket_and_opens_none_of_them():
    """The review's fifth pass (Т-M13's remainder). The mirror's walk (`closed_buckets`) opened every bucket to count
    its lines and marked progress once per UNIT: 5000 buckets of 300 lines took 3.2 s against a pulse limit of 2 s,
    and a resource walking a year of one camera looked silent. Now the walk goes by names, and every bucket named is
    progress — in the mirror's walk and in the retention's.

    The disk is made slow by the box's clock: every name the walk parses costs a tenth of the pulse's limit. What is
    measured is the pulse's own question — how long since the pass last got somewhere — at every name."""
    from w2cplatform import events as ev_mod
    from w2cplatform.events import bucket_path
    from w2cplatform.resource import Resource
    box = Box()
    res = Resource(box.resource_root, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, clock=box.clock,
                   lost_after=0.5)
    limit = res.PULSE_LIMIT * res.lost_after                        # two seconds, as the review measured against
    n = 2000
    for i in range(n):                                              # closed buckets of one camera, a few lines each
        p = bucket_path(box.resource_root, "vms", "7", 1, box.wall() - (n - i + 1) * 600)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write("".join(json.dumps({"t": 0, "kind": "stats", "n": k}) + "\n" for k in range(5)))
    box.vars.put("platform/mirror", {"enabled": "true", "copies": "1"})
    box.objects.put("platform/resources/srv-2/heartbeat",
                    json.dumps({"server": "srv-2", "ts": box.wall(), "url": "http://srv-2"}).encode())
    res.heartbeat()
    held = sorted(b.path for b in ev_mod.bucket_names_under(box.resource_root, "vms", "7", 600))

    class Peer:                                                     # holds every one already: the pass is the walk
        def mirrored(self, url, server):
            return [type("B", (), {"path": p})() for p in held]

        def put(self, url, server, path, data):
            raise AssertionError("nothing to send")

    res.peers = Peer()
    worst, opened = [0.0], [0]
    real_parse, real_read = ev_mod.parse_bucket, ev_mod.read_bucket

    def slow_parse(path, root):
        worst[0] = max(worst[0], box.clock() - res._progress_at)     # the pulse's `still`, at this name
        box.clock.advance(limit / 10)
        return real_parse(path, root)

    def counted_read(path):
        opened[0] += 1
        return real_read(path)

    ev_mod.parse_bucket, ev_mod.read_bucket = slow_parse, counted_read
    try:
        res._progressed()
        assert res.mirror()["mirrored"] == 0
        assert worst[0] < limit, f"the mirror's walk went {worst[0]:.1f} s without a mark (limit {limit:g} s)"
        assert opened[0] == 0, f"the mirror's walk opened {opened[0]} buckets to count lines nobody reads"
        worst[0] = 0.0
        res._progressed()
        assert res.retain() == 0                                     # nothing is old enough: the walk is the work
        assert worst[0] < limit, f"the retention's walk went {worst[0]:.1f} s without a mark (limit {limit:g} s)"
    finally:
        ev_mod.parse_bucket, ev_mod.read_bucket = real_parse, real_read


class _slow_disk:
    """The disk made slow by the box's clock, as the test above makes the names slow: every `stat` of a file and every
    removal costs a tenth of the pulse's limit. `worst` is the pulse's own question — how long since the pass last
    got somewhere — asked at each of them."""
    def __init__(self, box, res, limit):
        self.box, self.res, self.cost, self.worst, self.stats, self.removed = box, res, limit / 10, 0.0, 0, 0

    def _op(self):
        self.worst = max(self.worst, self.box.clock() - self.res._progress_at)
        self.box.clock.advance(self.cost)

    def __enter__(self):
        self.getsize, self.remove = os.path.getsize, os.remove

        def getsize(path):
            self._op(); self.stats += 1
            return self.getsize(path)

        def remove(path):
            self._op(); self.removed += 1
            return self.remove(path)

        os.path.getsize, os.remove = getsize, remove
        return self

    def __exit__(self, *exc):
        os.path.getsize, os.remove = self.getsize, self.remove


def _year_of_buckets(box, n, root=None, t0=None):
    from w2cplatform.events import bucket_path
    t0 = box.wall() - 60 * 86400 if t0 is None else t0
    for i in range(n):
        p = bucket_path(root or box.resource_root, "vms", "7", 1, t0 + i * 600)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(json.dumps({"t": 0, "kind": "stats"}) + "\n")


def test_measuring_the_tree_and_removing_what_is_old_keep_the_pulse_with_a_mark_per_file():
    """The review's sixth pass (П-M10's remainder). The fifth pass gave the walks by NAME a mark per bucket; the two
    parts beside them kept the old grain. `usage()` marked once per directory — and every bucket of an epoch is in ONE
    directory — and the removals in `retain` marked nothing: the names were all marked first, while the list was
    built, and then the files went one after another. By the model of the test above, 2000 buckets were 399.8 s
    without a mark in `usage` and 371 s in `retain` against a limit of 2 s: the pulse stopped, and a resource
    measuring or sweeping a year of one camera was reported silent. A mark per file measured and per file removed —
    this server's buckets, and the copies it keeps of another's."""
    from w2cplatform.resource import MIRROR_DIR, MIRROR_GRACE, Resource
    box = Box()
    res = Resource(box.resource_root, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall, clock=box.clock,
                   lost_after=0.5)
    limit = res.PULSE_LIMIT * res.lost_after
    n = 2000
    box.vars.put("vms/retention", {"days": "30"})
    _year_of_buckets(box, n)                                                        # two weeks of them, the newest 46 days old: past the 30 kept
    _year_of_buckets(box, n, root=os.path.join(box.resource_root, MIRROR_DIR, "srv-2"))   # …and as many copies of a peer's
    with _slow_disk(box, res, limit) as disk:
        res._progressed()
        assert res.usage() > 0 and disk.stats >= 2 * n
        assert disk.worst < limit, f"measuring the tree went {disk.worst:.1f} s without a mark (limit {limit:g} s)"
        disk.worst = 0.0
        res._progressed()
        assert res.retain() == n and disk.removed == 2 * n and res.mirror_removed == n
        assert disk.worst < limit, f"the removals went {disk.worst:.1f} s without a mark (limit {limit:g} s)"
    assert res.usage() < 4096 and MIRROR_GRACE > 0                                  # what is left is the journal's line


def test_reading_what_is_kept_marks_every_row_it_reads():
    """The sibling in what is kept (the specs' `holds:`, `w2cplatform/holds.py`; it was the VMS's own hook). Before
    anything is swept the retention asks what somebody said to keep, and the answer is read from the store row by row —
    the holds, and the rows of every unit about one — with no mark between them: on a store that takes its time, a
    part of the pass that moved the whole while and looked stuck. `kept` is handed `progressed`."""
    from vms import keeps
    from w2cplatform.resource import platform_resource
    box = Box()
    res = platform_resource(box.resource_root, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    res.clock, res.lost_after = box.clock, 0.5
    limit = res.PULSE_LIMIT * res.lost_after
    t = box.wall()
    keeps.write(box.vars, {"cam": "7", "from": t - 600, "to": t}, ["7"], "anna", t)
    for i in range(300):
        box.vars.put(f"det/units/{i}-motion", {"id": f"{i}-motion", "cam": str(i), "kind": "motion"})
        box.vars.put(f"rec/recordings/{i}", {"id": str(i), "cam": str(i)})
    worst = [0.0]
    real = type(box.vars).get

    def slow_get(path, *a, **kw):
        worst[0] = max(worst[0], box.clock() - res._progress_at)
        box.clock.advance(limit / 10)
        return real(box.vars, path, *a, **kw)

    box.vars.get = slow_get
    try:
        res._progressed()
        assert res.retain() == 0
    finally:
        del box.vars.get
    assert worst[0] < limit, f"reading what is kept went {worst[0]:.1f} s without a mark (limit {limit:g} s)"


def test_a_file_that_vanishes_under_the_walk_and_a_part_that_raises_end_only_themselves():
    """The review's third pass (minor; Н-M9's remainder). `usage()` ran outside any part and `part` caught only
    `OSError`: one `.tmp` renamed between the listing and the `stat` took the whole pass — watermark and mirror with
    it. The walk skips what is gone, it is a part of its own, and a part that raises anything is named in `errors`."""
    import os as _os
    box = Box()
    res, rsrv = _resource_process(box)
    try:
        _os.makedirs(_os.path.join(box.resource_root, "vms", "7"), exist_ok=True)
        open(_os.path.join(box.resource_root, "vms", "7", "keep.bin"), "wb").write(b"x" * 1000)
        real_getsize = _os.path.getsize

        def getsize(path):
            if path.endswith("keep.bin"):
                raise FileNotFoundError(path)                         # gone between the listing and the stat
            return real_getsize(path)
        _os.path.getsize = getsize
        try:
            assert res.usage() >= 0
        finally:
            _os.path.getsize = real_getsize

        class Buggy:
            def pass_(self, now):
                raise KeyError("a bug in reading what is kept")
        res.kept = as_kept(Buggy())
        ran = []
        res.mirror = lambda: ran.append("mirror") or {"enabled": False, "mirrored": 0, "peers": []}
        out = res.pass_()
        assert ran == ["mirror"] and "usage" in out and any(e.startswith("retain:") for e in out["errors"])
    finally:
        rsrv.shutdown()


def test_a_narrow_window_computes_its_files_and_a_wide_one_lists_them_with_the_same_answer():
    """Up to a day, the candidate files are computed from the window — a name from a time, a stat for whether it
    is there; wider, the epoch's directory is listed. Two ways to find the same files: one answer."""
    from w2cplatform.eventdatabase import NARROW
    from w2cplatform.events import EventLog
    box = Box()
    now = box.wall()
    log = EventLog(box.resource_root, "vms", "7", 1, 600)
    for i in range(6):
        log.append(now - 3 * 86400 + i * 3600, "motion", n=i)                   # six hours, three days ago
    db = EventIndex(box.resource_root, "srv-1", wall=box.wall)
    narrow = db.query(now - 3 * 86400 - 1, now - 3 * 86400 + 6 * 3600)
    wide = EventIndex(box.resource_root, "srv-1", wall=box.wall).query(0, now + 1)
    assert (now - (now - 3 * 86400 - 1)) / 600 > NARROW                          # the second one took the listing road
    assert [e["n"] for e in narrow["events"]] == [e["n"] for e in wide["events"]] == list(range(6))


def test_a_query_reads_the_files_of_its_window_and_nothing_else_and_nothing_twice():
    """What a query costs is what its window touches, not what the tree holds: three days of buckets, and a
    ten-minute question opens one file. Asked again over files that did not change, it opens none."""
    from w2cplatform.events import EventLog
    box = Box()
    now = box.wall()
    log = EventLog(box.resource_root, "vms", "7", 1, 600)
    for i in range(3 * 144):
        log.append(now - 3 * 86400 + i * 600 + 5, "motion", n=i)                 # a line in every bucket of three days
    db = EventIndex(box.resource_root, "srv-1", wall=box.wall)
    opened = []
    real_open = open

    def counting(path, *a, **kw):
        if str(path).endswith(".events.jsonl"):
            opened.append(path)
        return real_open(path, *a, **kw)

    import builtins
    builtins.open = counting
    try:
        assert len(db.query(now - 600, now)["events"]) == 1
        assert len(opened) == 1 and db.listing()["cached"] == 1
        db.query(now - 600, now)
        assert len(opened) == 1                                                  # unchanged size and time: the cached lines
    finally:
        builtins.open = real_open


def test_the_cache_keeps_to_its_ceiling():
    """In memory lives the working set, not the retention: read buckets go least recently used first once the
    cache passes its ceiling in bytes, and come back from the file when asked for again."""
    from w2cplatform.events import EventLog
    box = Box()
    now = box.wall()
    log = EventLog(box.resource_root, "vms", "7", 1, 600)
    for i in range(20):
        log.append(now - 20 * 600 + i * 600 + 5, "motion", pad="x" * 200)
    db = EventIndex(box.resource_root, "srv-1", wall=box.wall, cache_bytes=5 * 300)
    assert len(db.query(now - 20 * 600, now)["events"]) == 20
    assert db.listing()["cached"] <= 6 and db._bytes <= 5 * 300 + 300
    assert len(db.query(now - 20 * 600, now)["events"]) == 20                   # evicted is not lost: read again


def test_a_detector_is_skipped_for_another_camera_once_its_lines_have_named_its_own():
    """A detector `7-motion` is about camera 7 (det.subsystem.yaml, `about`) and says so in every line (`of: vms/7`):
    its name is not its camera. Once its lines have said camera 7, a timeline for camera 9 does not read its buckets."""
    from vms.config import DET_SPEC
    from w2cplatform.events import EventLog
    from tests.conftest import stamped
    box = Box()
    now = box.wall()
    stamped(EventLog(box.resource_root, "det", "7-motion", 1, 600), DET_SPEC.of_row({"cam": "7"})).append(now - 60, "motion", cam=7)
    db = EventIndex(box.resource_root, "srv-1", wall=box.wall)
    assert [(e["unit"], e["of"]) for e in db.query(now - 600, now, unit="vms/7")["events"]] == [("det/7-motion", "vms/7")]
    assert db._may_be_about("srv-1", "det", "7-motion", "vms/9") is False and db.query(now - 600, now, unit="vms/9")["events"] == []


def test_a_resource_says_busy_rather_than_queueing_without_end():
    """The server starts a thread per request and never says no; without a limit a burst of readers is a queue
    with no end, and a reader that times out cannot tell slow from gone. Past `EVENTS_INFLIGHT` queries at once,
    `/events` answers 503 with `Retry-After` — which the merge reads as "did not answer", holding automation's
    cursor instead of losing what this resource holds."""
    from w2cplatform.resource import EVENTS_INFLIGHT
    box = Box()
    res, rsrv = _resource_process(box)
    try:
        for _ in range(EVENTS_INFLIGHT):
            assert res.events_slots.acquire(blocking=False)             # as many queries as it takes, in flight
        try:
            urllib.request.urlopen(res.url + "/events?from=0&to=1")
            raise AssertionError("a ninth query was queued")
        except urllib.error.HTTPError as e:
            assert e.code == 503 and e.headers["Retry-After"] == "1" and b"busy" in e.read()
        res.events_slots.release()
        assert urllib.request.urlopen(res.url + "/events?from=0&to=1").status == 200   # a slot free: answered
    finally:
        rsrv.shutdown(); rsrv.server_close()


def test_the_timeline_fences_a_subsystem_its_scan_did_not_list_and_says_one_it_may_not_read():
    """The twelfth round's «Вопросы» 6 (found by runs): the whole timeline is fenced by a scan of the empty prefix, and a
    store that answers only what the console may read (М11's rights) leaves out `live/`, `det/` — their zombies' lines
    stood "current". Now the units of a subsystem the scan did not see are read by name for the answer; one whose rows
    the console may not read at all is said in the reply (`epochs_unread`), its lines as their resource marked them."""
    from vms.archive import event_log
    from w2cplatform.events import EventLog
    box = Box(); t = box.wall() - 60
    event_log(box.resource_root, 7, 1).append(t + 1, "motion"); box.vars.put("vms/epoch/7", {"epoch": "1"})
    EventLog(box.resource_root, "det", "7-motion", 1, 600).append(t + 2, "motion")
    box.vars.put("det/epoch/7-motion", {"epoch": "2"})                        # det's holder changed: epoch 1 is a zombie's
    con = _console_over(box, EventIndex(box.resource_root, "srv-1", wall=box.wall))

    class Rights:
        """The console's store under rights that leave `det/` out of a listing — and, `deny`, out of reads too."""
        def __init__(self, inner, deny=False): self.inner, self.deny = inner, deny
        def list(self, prefix): return [k for k in self.inner.list(prefix) if not k.startswith("det/")]
        def get(self, path):
            if self.deny and path.startswith("det/"):
                raise LookupError("refused by the store's rights")
            return self.inner.get(path)
        def __getattr__(self, name): return getattr(self.inner, name)

    class H:
        headers: dict = {}
        def _send(self, status, body, raw=False): self.reply = (status, body)

    def ask():
        h = H(); con.dispatch(h, "GET", "/events", {"from": str(t), "to": str(t + 60)}); return h.reply

    lines = lambda rep: {(e["subsystem"], e["unit"].split("/")[1]): e["fenced"] for e in rep[1]["events"]}
    real = con.ctl.vars
    con.ctl.vars = Rights(real)
    rep = ask()
    assert lines(rep) == {("vms", "7"): False, ("det", "7-motion"): True} and "epochs_unread" not in rep[1], rep
    con.ctl.vars = Rights(real, deny=True)
    con._epochs = (-1e18, {})
    rep = ask()
    assert lines(rep)[("det", "7-motion")] is False and rep[1]["epochs_unread"] == ["det"], rep
