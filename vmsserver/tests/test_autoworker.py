"""The evaluator: the first worker in the course whose work is reading.

What it must get right is not the matching — that is `fires()`, tested beside
the language — but everything around a decision taken from a log that is
at-least-once, replayed after a restart and shared with five other subsystems.
"""
import json
import logging

from w2cplatform.contract import requests_acl
from w2cplatform.variables import Forbidden
from vms.auto import AutoController
from vms.autoworker import AutoWorker
from vms.config import AUTO_SPEC, REC_SPEC, SPEC as VMS_SPEC
from tests.conftest import Box, door_site


class _Log:
    """The merged event index, as a list — and as unkind as the real one.

    Two properties matter and both were missing from the first version of this
    fake, which is why two defects lived through seven green tests: a window
    that overflows comes back CUT, and an event becomes visible some seconds
    AFTER its own timestamp, because a resource tails its files on a timer.

    Which end a cut window keeps is `keep`, and the fake obeys it the way the
    index does — newest by default — and says `truncated` when it had to cut.
    A fake that answered whole windows only is what let the evaluator infer
    fullness from a row count for as long as it did."""
    def __init__(self, events=(), lag=0.0, wall=None):
        self.events = list(events)
        self.lag, self.wall = lag, wall
        self.asked: list[dict] = []

    def query(self, t0, t1, subsystem=None, kind=None, limit=1000, keep="newest", unit=None, **kw):
        self.asked.append({"t0": t0, "t1": t1, "subsystem": subsystem, "kind": kind, "unit": unit, "limit": limit, "keep": keep})
        now = self.wall() if self.wall else t1
        rows = [e for e in self.events
                if t0 <= e["t"] <= t1
                and e["t"] + self.lag <= now                      # not in the merge yet
                and (subsystem is None or e["subsystem"] == subsystem)
                and (kind is None or e["kind"] == kind)
                and (unit is None or e["unit"] == str(unit))]
        rows.sort(key=lambda e: e["t"])
        cut = len(rows) > limit
        rows = (rows[-limit:] if keep == "newest" else rows[:limit]) if cut else rows
        return {"events": rows, "state": "live", "truncated": cut}


def ev(t, sub, unit, kind, **fields):
    """Exactly the row `MergedIndex.query` returns — `subsystem`, not `sub`, and
    no second spelling to hide behind. The fake that carried both keys is how a
    scenario that could never fire passed seven tests."""
    return {"t": float(t), "subsystem": sub, "unit": str(unit), "cam": None, "kind": kind, "epoch": 1,
            "server": "srv-a", "bucket": "b", "fenced": False, "epoch_is": "current", **fields}


DOOR = {"name": "door-on-badge",
        "when": [{"sub": "vms", "kind": "io.input", "unit": "12", "match": {"port": "1", "value": "closed"}},
                 {"sub": "det", "kind": "motion", "unit": "7-motion"}],
        "within": 30,
        "then": [{"sub": "vms", "action": "output", "unit": "12", "port": 2, "pulse_ms": 500},
                 {"sub": "rec", "action": "record", "cam": "7", "minutes": 10}]}


def _worker(box, log, name="a-1"):
    """With the token a scenario evaluator actually gets: its own prefix, plus
    the one family of somebody else's it may write."""
    vars_ = box.vars.as_writer("autoworker", AUTO_SPEC.sub.acl_worker() + requests_acl("vms", "rec"))
    return AutoWorker(name, vars_, box.objects, index=log, clock=box.clock, wall=box.wall,
                      server="srv-a", archive_root=box.archive, env={})


def _assigned(box, scenario, worker="a-1"):
    ctl = AutoController(box.vars.as_writer("autocontroller", AUTO_SPEC.acl_controller()), box.objects, wall=box.wall)
    ctl.assign(worker, [scenario])
    return ctl


def _scenario(box, **patch):
    door_site(box)                                   # the door, the lobby and its detector exist
    con = AutoController(box.vars.as_writer("console", AUTO_SPEC.acl_console()), box.objects, wall=box.wall)
    return con.create({**DOOR, **patch})


def test_two_triggers_inside_the_window_fire_once_and_file_what_was_asked():
    box = Box()
    t = box.wall()
    log = _Log([ev(t - 20, "det", "7-motion", "motion"),
                ev(t - 5, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box); _assigned(box, "door-on-badge")
    w = _worker(box, log)

    assert w.reconcile_once() == ["door-on-badge"]

    rows = sorted(box.vars.list("vms/requests/") + box.vars.list("rec/requests/"))
    assert len(rows) == 2, "one firing, two actions, two rows"
    out, _ = box.vars.get([k for k in rows if k.startswith("vms/")][0])
    assert out["action"] == "output" and out["unit"] == "12" and out["port"] == "2"
    assert out["by"] == "auto/door-on-badge"
    assert float(out["valid_until"]) == (t - 5) + 30            # the scenario's own window, not a guess
    rec, _ = box.vars.get([k for k in rows if k.startswith("rec/")][0])
    assert rec["action"] == "record" and rec["cam"] == "7" and rec["minutes"] == "10"

    # …and the scenario says so in its own bucket: the answer to "why did the door open at 14:02"
    assert w.epochs["door-on-badge"] >= 1


def test_the_same_log_read_again_files_nothing_new():
    """At-least-once by construction: the window is re-read every pass, and the
    events that fired are still in it. The cursor says they were considered; the
    deterministic id says that even if it were wrong, the row would be the same
    row rather than a second door."""
    box = Box()
    t = box.wall()
    log = _Log([ev(t - 20, "det", "7-motion", "motion"), ev(t - 5, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box); _assigned(box, "door-on-badge")
    w = _worker(box, log)

    w.reconcile_once()
    before = sorted(box.vars.list("vms/requests/") + box.vars.list("rec/requests/"))
    w.reconcile_once(); w.reconcile_once()
    assert sorted(box.vars.list("vms/requests/") + box.vars.list("rec/requests/")) == before

    # a FRESH process — the memory gone, the cursor kept — does not fire them again either
    w2 = _worker(box, log, name="a-1")
    w2.reconcile_once()
    assert sorted(box.vars.list("vms/requests/") + box.vars.list("rec/requests/")) == before


def test_outside_the_window_is_not_a_firing():
    """The window is the whole question. Two things that happened are not two
    things that happened together."""
    box = Box()
    t = box.wall()
    log = _Log([ev(t - 400, "det", "7-motion", "motion"),                      # four hundred seconds earlier
                ev(t - 5, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box); _assigned(box, "door-on-badge")
    w = _worker(box, log)

    assert w.reconcile_once() == []
    assert box.vars.list("vms/requests/") == []


def test_a_bouncing_sensor_does_not_ring_the_door():
    """The ceiling, and why it is per scenario and per minute. A contact that
    chatters is not two hundred people at the door."""
    box = Box()
    t = box.wall()
    bounce = [ev(t - 30 + i * 0.2, "vms", 12, "io.input", port="1", value="closed") for i in range(50)]
    _scenario(box, name="buzz", when=[DOOR["when"][0]], within=0, rate_per_minute=3,
              then=[DOOR["then"][0]])
    _assigned(box, "buzz")
    w = _worker(box, _Log(bounce))

    for _ in range(5):
        w.reconcile_once()
    assert len(box.vars.list("vms/requests/")) == 3, "the ceiling holds across passes, not inside one"


def test_a_scenario_that_is_off_decides_nothing():
    box = Box()
    t = box.wall()
    log = _Log([ev(t - 5, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box, name="off", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]], enabled=False)
    _assigned(box, "off")
    w = _worker(box, log)

    assert w.reconcile_once() == [] and box.vars.list("vms/requests/") == []
    assert w.status_by_unit["off"]["why"] == "disabled"


def test_the_token_reaches_requests_and_nothing_else():
    """The one grant that crosses a subsystem's name, and the reason it is safe
    to give: `requests` cannot change configuration, cannot place anything and
    cannot outlive the row it writes."""
    box = Box()
    vars_ = box.vars.as_writer("autoworker", AUTO_SPEC.sub.acl_worker() + requests_acl("vms", "rec"))
    vars_.put("vms/requests/x", {"unit": "12", "action": "output"})           # allowed
    vars_.put("rec/requests/y", {"unit": "7", "action": "record"})            # allowed
    for forbidden in ("vms/cameras/12", "rec/recordings/7", "vms/placement/12", "auto/scenarios/x"):
        try:
            vars_.put(forbidden, {"a": "b"})
            raise AssertionError(f"the evaluator wrote {forbidden}")
        except Forbidden:
            pass

    # and the grant is exactly two prefixes, named out loud
    assert requests_acl("vms", "rec") == ["rec/requests/*", "vms/requests/*"]


def test_a_fenced_event_is_not_evidence():
    """The merge marks events written under an epoch that is not current. A
    scenario must not fire on the word of a zombie: those minutes are already
    disputed, and acting on them is acting twice."""
    box = Box()
    t = box.wall()
    stale = ev(t - 5, "vms", 12, "io.input", port="1", value="closed"); stale["fenced"] = True
    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")
    w = _worker(box, _Log([stale]))

    assert w.reconcile_once() == [] and box.vars.list("vms/requests/") == []


def test_a_scenarios_minutes_become_a_recording_and_then_stop_being_one():
    """The other side of `rec.record`, and the division that decides where it
    lives. "Record for ten minutes" is a write to CONFIGURATION — a row with an
    id, a retention, a home and a placement — and of the three processes only
    the console holds the token for one. A worker writes none; the controller
    writes placement.

    So the evaluator files a request and the console's loop turns it into a
    recording, the way it would if the operator had pressed Record and set an
    alarm clock."""
    from vms.jobs import expire_recordings, record_on_request
    from w2cplatform.spec import SpecController

    box = Box()
    t = box.wall()
    rec = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    log = _Log([ev(t - 20, "det", "7-motion", "motion"), ev(t - 5, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box); _assigned(box, "door-on-badge")
    w = _worker(box, log)
    w.reconcile_once()

    assert record_on_request(rec, t) == 1
    row = rec.unit("7-auto")                                  # the page's own naming rule, one field over
    assert row["cam"] == "7" and row["until"] == t + 600      # ten minutes, as an END and not a timer
    assert box.vars.list("rec/requests/") == []               # performed, so it has nothing left to say

    # a second firing while it runs EXTENDS it: the scenario meant "keep recording", not "record twice"
    box.wall.advance(60)
    box.vars.put("rec/requests/again", {"action": "record", "cam": "7", "minutes": "10",
                                        "valid_until": str(box.wall() + 30)})
    assert record_on_request(rec, box.wall()) == 1
    assert rec.unit("7-auto")["until"] == box.wall() + 600
    assert len([u for u in rec.units() if u["cam"] == "7"]) == 1

    # …and when the clock gets there the row goes: the controller unplaces it, the recorder stops. The
    # ordinary path for a recording somebody removed, reached by a clock instead of by a click.
    assert expire_recordings(rec, box.wall()) == 0            # not yet
    box.wall.advance(601)
    assert expire_recordings(rec, box.wall()) == 1
    assert rec.unit("7-auto") is None

    # a recording an operator made by hand has `until: 0`, and no clock ever touches it
    rec.create({"name": "7", "cam": "7"})
    assert expire_recordings(rec, box.wall() + 10 ** 6) == 0


def test_a_record_request_the_recorder_sees_is_not_its_to_serve():
    """One family, two kinds of asking. A backfill names a RANGE and the worker
    fetches it; `record` names a DURATION and is nobody's to fetch. Before the
    skip, the recorder tripped over `it["from"]` every pass."""
    from vms.archive import ArchiveResource
    from vms.recworker import RecWorker

    box = Box()
    r = RecWorker("r-1", box.vars, box.objects, archive=ArchiveResource(box.spool, box.archive, wall=box.wall),
                  clock=box.clock, wall=box.wall, server="srv-a", env={})
    box.vars.put("rec/requests/x", {"action": "record", "cam": "7", "minutes": "10", "unit": "7"})
    assert r.requests() == [] and r.fetched == []             # not served, and not tripped over either


def test_an_event_that_reaches_the_merge_late_is_still_considered():
    """The defect this cursor rule exists for, and it is invisible with a fake
    that answers instantly.

    The merge is not a stream: a resource tails its files on a timer, so an
    event written at T is visible some seconds later. A cursor set to `now`
    is already past it, and `t <= since` then skips it FOR EVER — no refusal,
    no log line, just a scenario that does not fire."""
    box = Box()
    t = box.wall()
    late = ev(t - 1, "vms", 12, "io.input", port="1", value="closed")
    log = _Log([late], lag=3.0, wall=box.wall)                    # visible only three seconds after it happened
    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")
    w = _worker(box, log)

    assert w.reconcile_once() == []                               # nothing to see yet — and that is fine
    assert box.vars.list("vms/requests/") == []

    box.wall.advance(4)                                           # now the merge has it
    assert w.reconcile_once() == ["one"]
    assert len(box.vars.list("vms/requests/")) == 1


def test_a_noisy_log_does_not_hide_the_event_the_scenario_watches():
    """`ORDER BY t LIMIT n` drops the NEWEST rows, which is the end a scenario
    exists for. Three cameras writing a statistics line every few seconds fill a
    thousand rows in a five-minute window; from that moment the evaluator sees
    the beginning of the window and never the end.

    The trigger already names the subsystem and the kind — so the query names
    them too, and the window holds only what this scenario is looking at."""
    box = Box()
    t = box.wall()
    noise = [ev(t - 300 + i * 0.1, "rec", 7, "stats", n=str(i)) for i in range(2000)]
    wanted = ev(t - 2, "vms", 12, "io.input", port="1", value="closed")
    log = _Log(noise + [wanted], wall=box.wall)
    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")
    w = _worker(box, log)

    assert w.reconcile_once() == ["one"], "the event was there and the noise buried it"
    assert len(box.vars.list("vms/requests/")) == 1
    # one query per kind the scenario watches, each naming what it wants
    assert [(q["subsystem"], q["kind"]) for q in log.asked] == [("vms", "io.input")]


def test_a_cut_window_is_reported_even_when_fencing_hides_the_count():
    """The evaluator warns when a window came back cut, because a decision taken on
    part of one must not look like a decision taken on all of it. It used to work
    that out by comparing the row count to its own limit — but it counts AFTER
    dropping fenced events, so a cut window whose dropped rows included fenced ones
    comes back SHORT of the limit and the warning never fires. Silence then means
    both "nothing happened" and "I did not see what happened".

    The index is the one that cut; it says so, and the evaluator reads the fact
    instead of re-deriving it from a number that no longer means what it did."""
    box = Box()
    t = box.wall()
    watched = "io.input"
    rows = [ev(t - 300 + i * 0.1, "vms", 12, watched, port="1", value="open", fenced=(i % 2 == 0))
            for i in range(AutoWorker.PER_KIND * 2)]
    log = _Log(rows, wall=box.wall)
    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")
    w = _worker(box, log)

    seen = []
    handler = logging.Handler(); handler.emit = lambda r: seen.append(r.getMessage())
    logging.getLogger("autoworker").addHandler(handler)
    try:
        w.reconcile_once()
    finally:
        logging.getLogger("autoworker").removeHandler(handler)

    cut = log.asked[-1]
    assert cut["limit"] == AutoWorker.PER_KIND and cut["keep"] == "newest"   # it asks for the newest end…
    assert any("came back full" in m and "vms.io.input" in m for m in seen), \
        "the window was cut and the evaluator said nothing: fencing put the count below the limit"


def test_the_summary_of_a_suppressed_storm_does_not_fire_a_scenario():
    """The writer collapses repeats and says what it swallowed: one line with
    `repeats`, `since` and `until` (М10A, урок 12). That line is for the operator
    reading the timeline and for whoever reconstructs the incident — it is not a
    new observation, and the first line of that window already fired this scenario.

    Acting on it too would open the door a second time for one continuous event,
    and would do it worse the louder the sensor: the longer the storm, the more
    summaries. So a line carrying `repeats` never fires, and that is one condition
    in `fires`, next to the matching it belongs with — not a filter each consumer
    re-invents."""
    box = Box()
    t = box.wall()
    summary = ev(t - 2, "vms", 12, "io.input", port="1", value="closed",
                 repeats=200, since=t - 10, until=t - 2)

    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")

    w = _worker(box, _Log([summary], wall=box.wall))
    assert w.reconcile_once() == [], "the summary of a storm fired a scenario on its own"
    assert box.vars.list("vms/requests/") == []

    box2 = Box()
    _scenario(box2, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box2, "one")
    t2 = box2.wall()
    w2 = _worker(box2, _Log([ev(t2 - 10, "vms", 12, "io.input", port="1", value="closed"),
                             ev(t2 - 2, "vms", 12, "io.input", port="1", value="closed",
                                repeats=200, since=t2 - 10, until=t2 - 2)], wall=box2.wall))
    assert w2.reconcile_once() == ["one"]                       # the observation fires it…
    assert len(box2.vars.list("vms/requests/")) == 1, "one continuous event, one request"   # …and only it


# -- feedback on the event log's load: three defects ---------------------------------------------------------
def test_the_evaluator_runs_as_a_process_and_lets_its_slot_go_when_stopped():
    """`python -m vms autoworker` calls `run`, and this worker had none: the process fell over at start, and no
    test noticed, because every test drives `reconcile_once` by hand. This one drives the loop."""
    box = Box()
    t = box.wall()
    log = _Log([ev(t - 3, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")
    w = _worker(box, log)

    class OnePass:
        def __init__(self): self.asked = 0
        def is_set(self): self.asked += 1; return self.asked > 1
        def wait(self, s): return None

    w.run(poll=0, stop=OnePass())
    assert len(box.vars.list("vms/requests/")) == 1                   # a pass ran, and filed
    assert w.slot is None                                              # an orderly stop: the slot let go, said so
    assert box.vars.get(w.sub.slot_key("a-1"))[0]["released"] == "true"


class _Holey(_Log):
    """The merge, as it answers when a server did not: what the others hold, and the window called incomplete."""
    def __init__(self, events=(), wall=None):
        super().__init__(events, wall=wall)
        self.missing = {}

    def query(self, *a, **kw):
        rep = super().query(*a, **kw)
        if self.missing:
            rep = {**rep, "events": [e for e in rep["events"] if e["server"] not in self.missing]}
        return {**rep, "complete": not self.missing, "incomplete": dict(self.missing)}


def test_a_window_a_server_did_not_answer_for_does_not_move_the_cursor():
    """The event is on srv-b, and srv-b does not answer on the first pass — it is restarting, or loaded past
    the merge's timeout. The merge says the window is incomplete. The cursor used to move past it anyway, and
    when srv-b answered a pass later its event was older than the cursor: never considered, no refusal, no log
    line. Now the cursor holds, the scenario says what it is waiting for, and the event fires when srv-b is back."""
    box = Box()
    t = box.wall()
    door = {**ev(t - 5, "vms", 12, "io.input", port="1", value="closed"), "server": "srv-b"}
    log = _Holey([door], wall=box.wall)
    log.missing = {"srv-b": "did not answer"}
    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")
    w = _worker(box, log)

    assert w.reconcile_once() == []
    assert w.status()[0]["holding"] == {"srv-b": "did not answer"}
    box.wall.advance(10)
    log.missing = {}                                                   # srv-b answers again
    assert w.reconcile_once() == ["one"]
    assert len(box.vars.list("vms/requests/")) == 1 and "holding" not in w.status()[0]


def test_a_server_that_never_comes_back_holds_a_scenario_five_minutes_and_then_it_says_so():
    """Holding the cursor must not become holding it for ever: `since` never trails `now` by more than
    `COLD_START`. Past it the scenario decides without the silent server, and its status says whom it
    stopped waiting for — once, not on every pass after.

    Five minutes from when the wait BEGAN (feedback AV). This scenario has no cursor yet, so its window already
    starts `COLD_START` back; counted from there, it said `decided_without` ten seconds into the wait. The pass
    in between is what catches that."""
    box = Box()
    log = _Holey([], wall=box.wall)
    log.missing = {"srv-b": "silent"}
    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")
    w = _worker(box, log)
    w.reconcile_once()
    box.wall.advance(10)
    w.reconcile_once()
    assert w.status()[0]["holding"] == {"srv-b": "silent"} and "decided_without" not in w.status()[0]
    box.wall.advance(w.COLD_START)
    w.reconcile_once()
    assert w.status()[0]["decided_without"] == {"srv-b": "silent"}
    box.wall.advance(2)
    w.reconcile_once()
    assert "decided_without" not in w.status()[0] and w.status()[0]["holding"] == {"srv-b": "silent"}


def test_a_scenario_whose_lease_went_elsewhere_does_not_keep_saying_what_it_last_said():
    """The lease moved to another instance: this one stops deciding, and used to leave its last status up —
    `holding` a server for a window it no longer asks for (feedback AV). It says whose the scenario is not."""
    box = Box()
    log = _Holey([], wall=box.wall)
    log.missing = {"srv-b": "did not answer"}
    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")
    w = _worker(box, log)
    w.reconcile_once()
    assert w.status()[0]["holding"] == {"srv-b": "did not answer"}
    w.may_write = lambda unit: False
    w.reconcile_once()
    st = w.status()[0]
    assert "holding" not in st and st["phase"] == "waiting" and "lease" in st["why"]


def test_a_short_window_between_triggers_is_not_a_short_life_for_the_request():
    """`within` is how far apart two triggers may be. It was also the life of the request, so a scenario with
    `within: 5` filed requests that expired on an idle box: the road from the event to the holder takes up to
    seven seconds. The life is `valid_for`, thirty seconds unless the scenario says otherwise."""
    box = Box()
    t = box.wall()
    log = _Log([ev(t - 20, "det", "7-motion", "motion"), ev(t - 18, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box, within=5); _assigned(box, "door-on-badge")
    _worker(box, log).reconcile_once()
    out, _ = box.vars.get(sorted(box.vars.list("vms/requests/"))[0])
    assert float(out["valid_until"]) == (t - 18) + 30

    box2 = Box()
    t2 = box2.wall()
    _scenario(box2, within=5, valid_for=10); _assigned(box2, "door-on-badge")
    _worker(box2, _Log([ev(t2 - 8, "det", "7-motion", "motion"), ev(t2 - 6, "vms", 12, "io.input", port="1",
                                                                     value="closed")])).reconcile_once()
    out, _ = box2.vars.get(sorted(box2.vars.list("vms/requests/"))[0])
    assert float(out["valid_until"]) == (t2 - 6) + 10
    try:
        _scenario(Box(), name="x", valid_for=2)
        raise AssertionError("a request that expires on its way")
    except Exception as e:
        assert "valid_for" in str(e)


def test_the_merge_says_which_servers_a_window_is_missing():
    """A reader that decides on a window needs to know it is whole. The merge now says so, server by server:
    one live by heartbeat that did not answer; one that answered but is rebuilding after a restart (its own
    `catching up`); one silent inside the window. A server silent since before the window cannot have
    written in it, and does not make it incomplete."""
    import json as _json
    from w2cplatform.eventdatabase import MergedIndex
    box = Box()
    now = box.wall()
    for server, age in (("srv-a", 0), ("srv-b", 0), ("srv-c", 0), ("srv-d", 60), ("srv-e", 7200)):
        box.objects.put(f"platform/resources/{server}/heartbeat",
                        _json.dumps({"server": server, "ts": now - age, "url": f"http://{server}"}).encode())

    def fetch(url, params):
        if url == "http://srv-b":
            raise OSError("timed out")
        return {"events": [], "truncated": False, "state": "catching up" if url == "http://srv-c" else "live"}

    rep = MergedIndex(box.objects, fetch=fetch, wall=box.wall).query(now - 300, now)
    assert rep["complete"] is False
    assert rep["incomplete"] == {"srv-b": "did not answer", "srv-c": "said catching up", "srv-d": "silent"}


# -- the notes on the event log's load: one query per kind a pass, and what a pass costs ----------------------
def test_scenarios_watching_one_kind_share_one_query_a_pass():
    """Every scenario used to ask its own window of every kind it watches — fifty scenarios on three kinds
    were a hundred and fifty queries a pass, each to every resource. A pass now asks each (subsystem, kind)
    once, over the longest window any scenario on it needs, and each scenario reads its own part."""
    box = Box()
    t = box.wall()
    log = _Log([ev(t - 20, "vms", 12, "io.input", port="1", value="closed")])
    for name in ("a", "b", "c"):
        _scenario(box, name=name, when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    ctl = AutoController(box.vars.as_writer("autocontroller", AUTO_SPEC.acl_controller()), box.objects, wall=box.wall)
    ctl.assign("a-1", ["a", "b", "c"])
    w = _worker(box, log)
    assert sorted(w.reconcile_once()) == ["a", "b", "c"]
    assert len(log.asked) == 1 and w.pass_stats["queries"] == 1       # three scenarios, one kind: one question


def test_a_cut_in_the_shared_answer_counts_only_against_the_scenario_it_reached():
    """The shared answer spans the longest window and keeps its newest end. A scenario reaching an hour back
    lost the hour's first minutes to the cut and says so (`cut`); one looking at the last five minutes lost
    nothing, and says nothing."""
    box = Box()
    t = box.wall()
    rows = [ev(t - 3000 + i * 5, "vms", 12, "io.input", port="1", value="open") for i in range(600)]
    log = _Log(rows, wall=box.wall)
    _scenario(box, name="long", within=3600,
              when=[DOOR["when"][0], {"sub": "vms", "kind": "io.input", "unit": "12", "match": {"value": "open"}}],
              then=[DOOR["then"][0]])
    _scenario(box, name="short", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    ctl = AutoController(box.vars.as_writer("autocontroller", AUTO_SPEC.acl_controller()), box.objects, wall=box.wall)
    ctl.assign("a-1", ["long", "short"])
    w = _worker(box, log)
    w.reconcile_once()
    st = {s["id"]: s for s in w.status()}
    assert st["long"]["cut"] == ["vms.io.input@12"] and "cut" not in st["short"]
    assert len(log.asked) == 1


def test_a_pass_says_what_it_cost_in_its_heartbeat_and_the_console_exports_it():
    """A slow pass and a held cursor were visible nowhere. The evaluator's heartbeat now carries its last
    pass — seconds, queries, how far the furthest cursor trails `now`, the longest road from an event to the
    request it filed — and the console's `/metrics` exports them per evaluator."""
    from vms.console import auto_metrics
    from w2cplatform.contract import Heartbeat
    box = Box()
    t = box.wall()
    log = _Log([ev(t - 4, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")
    w = _worker(box, log)
    w.reconcile_once(); w.heartbeat_once()
    hb = Heartbeat.from_bytes(box.objects.get(AUTO_SPEC.sub.heartbeat_key("a-1")))
    assert hb.extra["queries"] == 1 and hb.extra["latency_seconds"] == 4.0 and hb.extra["lag_seconds"] == w.COLD_START
    con = AutoController(box.vars.as_writer("console", AUTO_SPEC.acl_console()), box.objects, wall=box.wall)
    text = "\n".join(auto_metrics(con)())
    assert 'auto_firing_latency_seconds{worker="a-1"} 4.0' in text and 'auto_queries_per_pass{worker="a-1"} 1' in text
    # …and the road as a histogram since the process started: the pass after this one files nothing and its
    # gauge says 0, but a scrape between the two still sees the four-second road (feedback AY).
    box.wall.advance(2); w.reconcile_once(); w.heartbeat_once()
    text = "\n".join(auto_metrics(con)())
    assert 'auto_firing_latency_seconds{worker="a-1"} 0.0' in text
    assert 'auto_event_to_request_seconds_bucket{worker="a-1",le="2"} 0' in text
    assert 'auto_event_to_request_seconds_bucket{worker="a-1",le="5"} 1' in text
    assert 'auto_event_to_request_seconds_count{worker="a-1"} 1' in text


def test_a_firing_whose_request_would_leave_expired_is_not_filed_and_is_counted_apart():
    """A cold start looks five minutes back; `valid_for` is thirty seconds. On the product's box four requests
    of five reached the holder 47 to 229 seconds late and were counted `expired` — and `expired` is the number
    that says the road from event to device grew longer, so every start of the evaluator said so, falsely
    (feedback AY). A request that would be expired before it leaves is not filed. The firing is still a
    firing: the scenario's event says it fired, and how late; the status and the heartbeat count it apart."""
    from vms.console import auto_metrics
    from w2cplatform.eventdatabase import EventIndex
    box = Box()
    t = box.wall()
    log = _Log([ev(t - 120, "vms", 12, "io.input", port="1", value="closed"),
                ev(t - 4, "vms", 12, "io.input", port="1", value="open"),
                ev(t - 3, "vms", 12, "io.input", port="1", value="closed")])
    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")
    w = _worker(box, log)
    w.reconcile_once(); w.heartbeat_once()
    reqs = [box.vars.get(p)[0] for p in box.vars.list("vms/requests/")]
    assert len(reqs) == 1 and float(reqs[0]["at"]) == t - 3              # the fresh one; the old one is not filed
    assert w.status()[0]["late"] == 1 and w.late == 1
    fired = [e for e in EventIndex(box.archive, "srv-1", wall=box.wall).query(t - 400, t + 1, subsystem="auto")["events"]
             if e["kind"] == "fired"]
    assert sorted((e["t"], e.get("late")) for e in fired) == [(t - 120, 120.0), (t - 3, None)]
    con = AutoController(box.vars.as_writer("console", AUTO_SPEC.acl_console()), box.objects, wall=box.wall)
    assert 'auto_fired_late_total{worker="a-1"} 1' in "\n".join(auto_metrics(con)())
    w.reconcile_once()
    assert len(box.vars.list("vms/requests/")) == 1 and w.late == 1      # remembered: not late twice


def test_the_merge_asks_its_resources_at_once_and_does_not_wait_twice_for_one_that_hung():
    """Asked one after another, three resources that take a second each took three; asked at once, one. And a
    resource that did not answer is not asked again for a few seconds: it is named at once as not answering,
    instead of costing every query of the pass its full timeout."""
    import json as _json
    import time as _time
    from w2cplatform.eventdatabase import MergedIndex
    box = Box()
    now = box.wall()
    for server in ("srv-a", "srv-b", "srv-c"):
        box.objects.put(f"platform/resources/{server}/heartbeat",
                        _json.dumps({"server": server, "ts": now, "url": f"http://{server}"}).encode())
    calls = []

    def fetch(url, params):
        calls.append(url)
        if url == "http://srv-c":
            raise OSError("timed out")
        _time.sleep(0.3)
        return {"events": [], "truncated": False, "state": "live"}

    m = MergedIndex(box.objects, fetch=fetch, wall=box.wall, cooldown=10.0)
    t0 = _time.monotonic()
    rep = m.query(now - 60, now)
    assert _time.monotonic() - t0 < 0.55                              # at once: not 0.6 for two sleeping resources
    assert rep["incomplete"] == {"srv-c": "did not answer"}
    calls.clear()
    rep = m.query(now - 60, now)
    assert "http://srv-c" not in calls and rep["incomplete"] == {"srv-c": "did not answer a moment ago"}
    box.wall.advance(11)
    for server in ("srv-a", "srv-b", "srv-c"):
        box.objects.put(f"platform/resources/{server}/heartbeat",
                        _json.dumps({"server": server, "ts": box.wall(), "url": f"http://{server}"}).encode())
    calls.clear(); m.query(now - 60, now)
    assert "http://srv-c" in calls                                    # the pause is over: asked again


def test_a_loud_camera_does_not_cut_the_quiet_one_a_scenario_watches():
    """Measured before it was fixed (`tests/load_events.py`): asked across all units, one kind on twenty busy
    cameras filled the 500-row window, and the loud ones cut the quiet camera a scenario was watching. A trigger
    that names its unit gets a query for that unit, which no other camera can crowd."""
    box = Box()
    t = box.wall()
    noise = [ev(t - 250 + i * 0.4, "vms", 13, "io.input", port="1", value="open") for i in range(600)]
    log = _Log(noise + [ev(t - 200, "vms", 12, "io.input", port="1", value="closed")], wall=box.wall)
    _scenario(box, name="one", when=[DOOR["when"][0]], within=0, then=[DOOR["then"][0]])
    _assigned(box, "one")
    w = _worker(box, log)
    assert w.reconcile_once() == ["one"] and "cut" not in w.status()[0]
    assert log.asked[0]["unit"] == "12"
