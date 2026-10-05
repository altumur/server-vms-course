"""What an older epoch MEANS. Same comparison, two answers: a writer that lost
the race, or a finished earlier run of work that ends."""
from w2cplatform.epoch import current_epoch, next_epoch
from w2cplatform.eventdatabase import EventIndex
from w2cplatform.events import EventLog
from w2cplatform.spec import SubsystemSpec
from tests.conftest import Box, testsub, testsub2


def _runs():
    """A subsystem whose unit is a run of work that ends, and says so: `events.older_epochs: earlier-run`."""
    return SubsystemSpec.from_dict({"name": "testruns", "unit": {"rows": "runs", "id": "name",
                                                                 "fields": {"name": {"type": "string"}}},
                                    "placement": {"capacity": {"from": "capacity", "default": 4}},
                                    "events": {"older_epochs": "earlier-run"}})


def _run(box, sub, unit, t, epoch):
    EventLog(box.tree, sub, unit, epoch).append(t, "tick", n=7)
    next_epoch(box.vars, f"{sub}/epoch/{unit}")


def _events(box, sub, unit, policy):
    db = EventIndex(box.tree, "srv-1")
    cur = {(sub, unit): current_epoch(box.vars, f"{sub}/epoch/{unit}")}
    out = db.query(0, 1e12, current_epochs=cur, epoch_policy=policy)["events"]
    return sorted(((e["epoch"], e["epoch_is"], e["fenced"]) for e in out))


def test_one_finished_run_is_not_older_than_anything():
    """The thing I expected to be broken and is not: a job that ran once keeps the
    epoch it took, so its events are under the current one."""
    box = Box(); _run(box, "testruns", "c7-run-1", 1000.0, 1)
    assert _events(box, "testruns", "c7-run-1", {"testruns": "earlier-run"}) == [(1, "current", False)]


def test_a_second_run_does_not_strike_the_first_one_through():
    """The operator runs the same search again — a new model, a wider interval.
    Both results exist, both are real, and the page can offer to compare them."""
    box = Box()
    _run(box, "testruns", "c7-run-1", 1000.0, 1)
    _run(box, "testruns", "c7-run-1", 1100.0, 2)
    assert _events(box, "testruns", "c7-run-1", {"testruns": "earlier-run"}) == \
        [(1, "earlier-run", False), (2, "current", False)]


def test_a_live_unit_still_strikes_its_zombie_through():
    """The same shape, under the default. Here an older epoch really is a writer
    that lost the race and kept writing, and nothing about this changed."""
    box = Box()
    _run(box, "testsub2", "t7", 1000.0, 1)
    _run(box, "testsub2", "t7", 1000.5, 2)
    assert _events(box, "testsub2", "t7", {"testsub2": "fenced"}) == \
        [(1, "fenced", True), (2, "current", False)]


def test_a_subsystem_nobody_declared_keeps_the_old_answer():
    """An empty policy is the behaviour this code had before it could be asked."""
    box = Box()
    _run(box, "testsub2", "t7", 1000.0, 1)
    _run(box, "testsub2", "t7", 1000.5, 2)
    assert _events(box, "testsub2", "t7", {}) == [(1, "fenced", True), (2, "current", False)]


def test_the_default_is_fenced_and_earlier_run_only_where_a_spec_says_it():
    """A spec that says nothing (testsub) means what one that says `fenced` (testsub2) means; only a spec that
    says `earlier-run` gets it."""
    assert testsub().older_epochs == "fenced" and testsub2().older_epochs == "fenced"
    assert _runs().older_epochs == "earlier-run"


def test_a_meaning_the_page_cannot_draw_is_refused_at_load():
    unit = {"rows": "u", "id": "name", "fields": {"name": {"type": "string"}}}
    try:
        SubsystemSpec.from_dict({"name": "x", "unit": unit, "events": {"older_epochs": "superseded"}})
        raise AssertionError("accepted an unknown meaning")
    except ValueError as e:
        assert "fenced or earlier-run" in str(e)


def test_the_console_hands_its_mounts_meanings_to_the_query():
    """`/events` merges across subsystems, so the console answering the request
    has to know what an older epoch means in a subsystem it does not own."""
    from w2cplatform.console import Mount, SpecConsole
    from w2cplatform.spec import SpecController
    box = Box()
    root = SpecConsole(SpecController(testsub(), box.vars, box.objects, wall=box.wall))
    jobs = SpecConsole(SpecController(_runs(), box.vars, box.objects, wall=box.wall))
    m = Mount(root, {"testruns": jobs})
    assert m.epoch_policy == {"testsub": "fenced", "testruns": "earlier-run"}
    assert root.epoch_policy is m.epoch_policy and jobs.epoch_policy is m.epoch_policy   # one dict, shared

    later = SpecConsole(SpecController(testsub2(), box.vars, box.objects, wall=box.wall))
    m.mount("testsub2", later)
    assert root.epoch_policy["testsub2"] == "fenced"     # a console mounted later is known to the ones before it
