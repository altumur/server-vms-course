"""What the platform's worker does for every subsystem, so that no subsystem's worker has to remember it — on testsub and
testsub2, with workers that set nothing but their work (the code-fix batch after the boundary program).

    the resource tree     set by the base from the runtime (`RESOURCE_ROOT`): `observe` and the journal write there
    the loop's pass       `reconcile_once(now=None)` — the abstract and the loop that calls it agree
    capacity              the spec's `placement.capacity.default` when the subsystem sets none — never a said 0
    a unit let go         forgotten by the assignment read that answers (`lost_to_epoch`), in the base
    events.suppress       applied by the platform's `observe`, `occurred` kept out of a repeat's identity
    an early pass         the platform's loop (`early_pass(touched)`), not one subsystem's copy
    failover              every worker's heartbeat says the instance before it under its name (`previous_*`)
    a request look        that raises something else is that look's trouble: counted, the pump goes on
    the request marks     `<sub>/commands/*` are rows for every spec with `requests:`, granted to its worker
"""
import json
import threading

from tests.conftest import Box, Served, controller, counter_worker, in_catalogue, testsub, testsub2
from w2cplatform.contract import Controller, Heartbeat
from w2cplatform.worker import Worker


class _Bare(Worker):
    """A subsystem's worker that sets nothing — no tree, no capacity, no suppressor — and passes."""
    def reconcile_once(self, now=None):
        return []


def _bare(box, spec, name, **kw):
    cls = type("Bare", (_Bare,), {"spec": spec})
    w = cls(spec.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, **kw)
    w.server = "srv-1"
    w.claim_slot(name)
    return w


def test_a_worker_that_names_no_resource_tree_writes_its_events_where_the_runtime_says():
    """The base never set `resource_root`: every subsystem's worker repeated `runtime.events_root(env, root)`, and one that
    forgot had `observe` write nothing, silently — and its journal opened on no tree. The base sets it from the runtime
    (the caller's, else `RESOURCE_ROOT`, else the platform's events root)."""
    box = Box()
    w = _bare(box, testsub(), "w-1", env={"RESOURCE_ROOT": box.resource_root})
    assert w.resource_root == box.resource_root
    w.take_epoch("c1")
    path = w.observe("c1", "counted", n=1)
    assert path is not None and path.startswith(box.resource_root), path


def test_the_loop_calls_the_pass_the_way_the_abstract_declares_it():
    """`Worker.run` calls `reconcile_once()` with no argument, and the abstract declared `now` required: a subsystem
    written to the abstract raised `TypeError` on every pass of the platform's loop. `now` is optional in both."""
    import inspect
    assert inspect.signature(Worker.reconcile_once).parameters["now"].default is None


def test_a_worker_whose_subsystem_sets_no_capacity_says_the_specs_default_and_is_placed_by_it():
    """`platform_fields` said `capacity: 0` for a worker whose subsystem set none, and the controller reads a said number
    as the worker's word (`capacity_of`): nothing was ever placed on it, whatever `placement.capacity.default` said. It
    says the spec's default now; a worker with no spec and no capacity says none, and the controller's fallback holds."""
    box = Box()
    w = _bare(box, testsub(), "w-1", resource_root=box.resource_root)
    w.heartbeat_once()
    hb = Heartbeat.from_bytes(box.objects.get(w.sub.heartbeat_key("w-1")))
    assert hb.extra["capacity"] == testsub().capacity_default == 4 and hb.extra["headroom"] == 4
    assert controller(box, capacity=1).capacity_of("w-1") == 4                 # the worker's word, not the fallback
    plain = _Bare(testsub().sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, resource_root=box.resource_root)
    plain.server = "srv-1"
    plain.claim_slot("w-2")                                                     # no spec, no capacity
    plain.heartbeat_once()
    said = Heartbeat.from_bytes(box.objects.get(plain.sub.heartbeat_key("w-2"))).extra
    assert "capacity" not in said and "headroom" not in said
    assert controller(box, capacity=1).capacity_of("w-2") == 1                 # not said: the fallback


def test_a_unit_the_lease_step_let_go_is_forgotten_by_the_assignment_read_that_answers():
    """`lost_to_epoch` is the platform's — set by its lease step, read by its requests — and only one subsystem's refresh
    cleared it: any other worker that serves requests never forgot a unit let go, and its requests were skipped until a
    pass took the epoch again. The base's `assignment()` forgets it, at the read that answered, and only then."""
    from w2cplatform.epoch import next_epoch
    box = Box()
    ctl = controller(box)
    ctl.create({"name": "c1"})
    w = counter_worker(box, "w-1", resource_root=box.resource_root)
    Controller(testsub().sub, box.vars, box.objects, wall=box.wall).assign("w-1", ["c1"])
    w.reconcile_once()
    assert "c1" in w.epochs
    next_epoch(box.vars, w.sub.epoch_key("c1"))                              # another holder's epoch
    w.lease_pass()
    assert "c1" in w.lost_to_epoch and "c1" not in w.leases
    real = box.vars.get
    box.vars.get = lambda *a, **k: (_ for _ in ()).throw(OSError("the store blinked"))
    try:
        try:
            w.assignment()
            raise AssertionError("the read answered")
        except OSError:
            pass
        assert "c1" in w.lost_to_epoch                                         # a read that did not answer forgets nothing
    finally:
        box.vars.get = real
    w.assignment()
    assert "c1" not in w.lost_to_epoch                                         # the read answered: the pass judges it again


def test_the_specs_suppressed_repeats_are_the_platforms_observe():
    """`events.suppress` was loaded and checked for every spec and applied by one subsystem's worker: testsub2's
    `tally.tick: {window: 5, by: [unit]}` swallowed nothing in the platform's `observe`. A repeat inside the window is
    written as nothing now, the window's summary once it closed (`flush_suppressed`, the loop's pump), and `occurred` —
    the source's clock — rides on the line written and is no part of a repeat's identity."""
    from w2cplatform.events import read_bucket
    box = Box()
    w = _bare(box, testsub2(), "t-1", resource_root=box.resource_root)
    w.take_epoch("t1")
    first = w.observe("t1", "tally.tick", n=1, occurred=box.wall() - 2)
    assert first is not None
    assert w.observe("t1", "tally.tick", n=2, occurred=box.wall() - 1) is None   # a repeat, whatever its clock said
    assert w.flush_suppressed() == 0                                             # the window is open
    box.wall.advance(6)
    assert w.flush_suppressed() == 1 and w.flush_suppressed() == 0               # its summary, once
    lines = [ln for ln in read_bucket(first) if ln.get("kind") == "tally.tick"]
    assert lines[0]["occurred"] == box.wall() - 8 and lines[-1]["repeats"] == 1, lines
    assert w.observe("t1", "tally.other", n=3) is not None                       # a kind with no rule: written


def test_an_early_pass_is_the_platforms_loop_and_a_worker_may_look_at_what_was_touched():
    """One subsystem's evaluator ran a copy of the platform's loop for the long poll's early passes. The loop is the
    platform's now: a wait cut short by a resource's answer is followed by `early_pass(touched)` — what the answers said
    changed — and the ordinary pass (`reconcile_once`) comes otherwise, and at least every `poll`."""
    box = Box()
    seen = []

    class Early(_Bare):
        spec = testsub()

        def reconcile_once(self, now=None):
            seen.append("full")
            return []

        def early_pass(self, touched):
            seen.append(("early", frozenset(touched)))

    w = Early(testsub().sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, resource_root=box.resource_root)
    w.claim_slot("w-1")
    w.start_stand_in = lambda: threading.Event()

    class Poll:
        def take_touched(self): return {("testsub", "counted", "c1")}
        def close(self): pass

    class Turns:
        def __init__(self, n): self.n = n
        def is_set(self): self.n -= 1; return self.n < 0
        def wait(self, s): return None

    w.long_poll = Poll()
    woken = iter([True, False])
    w.between = lambda poll, stop, beat: next(woken, False)
    w.run(poll=10.0, stop=Turns(3))
    assert seen == ["full", ("early", frozenset({("testsub", "counted", "c1")})), "full"], seen


def test_every_workers_failover_is_measured_from_the_heartbeat_its_name_left():
    """The previous instance's heartbeat — what `failover_seconds` measures from — was read in one subsystem's
    constructor, and every other subsystem's failover went unmeasured. The platform reads it, before an instance's first
    heartbeat under its name, and says it in every heartbeat (`previous_hb`, `previous_instance`, `previous_server`)."""
    box = Box()
    old = counter_worker(box, "w-1", instance="srv-1:101", resource_root=box.resource_root)
    old.heartbeat_once()
    was = Heartbeat.from_bytes(box.objects.get(old.sub.heartbeat_key("w-1")))
    assert was.extra["previous_hb"] == 0.0 and was.extra["started"] == old.started_wall   # nobody before it
    old.release_slot()
    box.wall.advance(20)
    new = counter_worker(box, "w-1", instance="srv-1:102", resource_root=box.resource_root)
    new.heartbeat_once()
    hb = Heartbeat.from_bytes(box.objects.get(new.sub.heartbeat_key("w-1")))
    assert (hb.extra["previous_hb"], hb.extra["previous_instance"], hb.extra["previous_server"]) == (was.ts, "srv-1:101", "srv-1")
    assert controller(box).failover_seconds() == {"w-1": 20.0}


def test_a_request_look_that_raises_something_else_is_that_looks_trouble():
    """A store that refuses a write it does not take raised `ValueError` past the pump's `OSError`, out of `pump_once`;
    in the loop every turn counted a failed pump and logged a trace. It is counted, said once a spell, and the pump goes
    on — the next look tries again."""
    box = Box()
    w = counter_worker(box, "w-1", resource_root=box.resource_root)
    w.serve_requests = lambda: (_ for _ in ()).throw(ValueError("not a row of the store"))
    w.pump_once()
    w.pump_once()
    assert w.pass_failures == 2


def test_the_request_marks_are_rows_for_every_spec_whose_units_take_requests():
    """The marks a worker writes before it performs a request (`<sub>/commands/<id>`) are the platform's family, and they
    must be create-only ACROSS servers — a row. That held only where a spec repeated `commands/*` under `objects.rows`:
    testsub takes requests and names no rows, so on a cluster its marks were files on each server (two holders could both
    perform), and every look that reached one raised. Derived now for every spec with `requests:`, and granted to its
    worker; a spec's own rows stay beside it."""
    from w2cplatform import catalog
    from w2cplatform.cluster import rights
    from w2cplatform.cluster.objectstore import is_row
    with in_catalogue(testsub(), testsub2()):
        assert "testsub/commands/*" in catalog.object_rows() and is_row("testsub/commands/r-1")
        assert set(catalog.rows_of(testsub2())) == {"marks/*", "commands/*"}
        assert "testsub/commands/*" in testsub().sub.acl_objects_worker()
        roles = rights.roles([testsub(), testsub2()], "tests")
        assert "objects/testsub/commands/*" in roles["testsubworker"]["write"], roles["testsubworker"]
        assert "objects/testsub2/commands/*" in roles["testsub2worker"]["write"]
        assert not is_row("testsub/heartbeats/w-1")


def test_a_create_under_a_name_a_unit_has_is_409_exists():
    """The product answers a create under a taken id `409 {error: "exists"}`; the course's console said 400 with the
    sentence for an error. The page's watch (`startLive`) reads it as "there already"."""
    from w2cplatform.console import SpecConsole
    box = Box()
    with Served(SpecConsole(controller(box), wall=box.wall)) as call:
        assert call("POST", "/counters", {"name": "c1"})[0] == 201
        code, body = call("POST", "/counters", {"name": "c1"})
        assert code == 409 and body["error"] == "exists" and "exists" in body["detail"], (code, body)
        assert call("POST", "/counters", {"name": "a/b"})[0] == 400                    # a refusal is still a refusal


def test_a_persons_request_ledger_that_does_not_read_stops_that_person_and_says_so_once():
    """A person's open requests are one row (`<sub>/requests/asks-<sha>`, `per_person`). One that did not parse was read
    as an empty list and written over: the limit silently reset, nothing counted. Now that person is refused — 429,
    «учёт не читается» — the row is not written over, `<sub>_requests_ledger_garbled` says it on `/metrics`, the journal
    says it once for the row (not per request); another person files as before; an administrator deletes the row
    (`DELETE /requests/asks-…`) and the ledger starts anew."""
    from w2cplatform.console import SpecConsole
    box = Box()
    spec = testsub2()
    ctl = controller(box, spec=spec)
    ctl.create({"name": "t1", "of": "c1"})
    con = SpecConsole(ctl, marks_root=box.resource_root, wall=box.wall)
    said, real = [], con.journal.say
    con.journal.say = lambda kind, *a, **k: (said.append(kind), real(kind, *a, **k))[1]
    as_ = lambda who: {"X-User": who}                                            # noqa: E731
    with Served(con) as call:
        assert call("POST", "/requests", {"unit": "testsub2/t1", "add": 1}, headers=as_("anna"))[0] == 202
        [ledger] = [k for k in box.vars.list(spec.sub.requests_prefix()) if k.rsplit("/", 1)[1].startswith("asks-")]
        box.vars.put(ledger, {"asks": "[[\"t1-1\"", "by": "anna"})                # torn
        for add in (2, 3):
            code, body = call("POST", "/requests", {"unit": "testsub2/t1", "add": add}, headers=as_("anna"))
            assert code == 429 and body["error"] == "учёт не читается", (code, body)
        assert box.vars.get(ledger)[0]["asks"] == "[[\"t1-1\"" and said.count("request.ledger_garbled") == 1
        assert "testsub2_requests_ledger_garbled 1" in con.metrics_text().splitlines()
        assert call("POST", "/requests", {"unit": "testsub2/t1", "add": 5}, headers=as_("boris"))[0] == 202
        assert call("DELETE", "/requests/" + ledger.rsplit("/", 1)[1], headers=as_("admin"))[0] == 200
        assert call("POST", "/requests", {"unit": "testsub2/t1", "add": 4}, headers=as_("anna"))[0] == 202
        assert "testsub2_requests_ledger_garbled 0" in con.metrics_text().splitlines()
        assert json.loads(box.vars.get(ledger)[0]["asks"])[0][0] == "t1-4"        # anew
    assert con.needs("DELETE", "/requests/" + ledger.rsplit("/", 1)[1])[0] == "admin"


def test_workers_needed_is_one_series_when_a_spec_has_both_spares_and_places():
    """A spec with `offers` and `places` (testsub2) said `<p>_workers_needed{labels=""}` twice whenever the pass report was
    fresh — two TYPE lines and a duplicate series, and Prometheus refuses the whole scrape. One series: the free places
    are added to the empty set's row; alone, they are said by themselves."""
    from w2cplatform.console import SpecConsole
    box = Box()
    spec = testsub2()
    box.vars.put(spec.sub.config("shelves", "s1"), {"name": "s1", "enabled": "true"})
    con = SpecConsole(controller(box, spec=spec), wall=box.wall)
    series = lambda text: [ln for ln in text.splitlines() if ln.startswith(f"{spec.name}_workers_needed")]   # noqa: E731
    text = con.metrics_text()
    assert series(text) == [f'{spec.name}_workers_needed{{labels=""}} 1'], series(text)     # no pass report: places alone
    box.objects.put(f"{spec.name}/controller/pass", json.dumps({"ts": box.wall(), "workers_needed": {"": 2, "gpu": 1}}).encode())
    text = con.metrics_text()
    assert text.count(f"# TYPE {spec.name}_workers_needed gauge") == 1
    assert series(text) == [f'{spec.name}_workers_needed{{labels=""}} 3', f'{spec.name}_workers_needed{{labels="gpu"}} 1'], series(text)
