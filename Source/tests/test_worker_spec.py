"""A platform key is executed by the platform, and the platform has no path where the spec is absent (the architect's
rule after step 7). Two halves, on testsub and testsub2 — the platform's own subsystems:

    the spec, always     a `Worker` runs by its subsystem's spec: the catalogue's, by the subsystem's name (the one the
                         controller and the console run by), or the one a test hands it. Neither: it does not start. Every
                         worker key — `slot`, `lease`, `placement.places`, `events.suppress` — is then carried out by the
                         base, and a subsystem's worker writes no line of it
    `of`, the base's     what a unit is about (`about`) is the platform's to write on every line and every mark of it,
                         remembered when its epoch is taken. A subsystem that says `of` itself is refused: each passed it by
                         hand, and the line that forgot it was found by no query for what its unit is about
"""
import json
import os

from tests.conftest import Box, in_catalogue, spec_named, testsub, testsub2
from w2cplatform.events import ALARM, read_bucket
from w2cplatform.worker import NoSpec, Worker


def _refused(fn, words: str) -> None:
    try:
        fn()
    except (NoSpec, ValueError) as e:
        assert words in str(e), str(e)
        return
    raise AssertionError(f"not refused: {words}")


def _base(box, spec=None, sub=None, **kw) -> Worker:
    """The platform's `Worker` itself — no subclass, no line of a subsystem's — on the box's stores and clocks."""
    sub = sub or spec.sub
    return Worker(sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, resource_root=box.resource_root,
                  spec=spec, **kw)


def _tally(box, name: str, counter: str) -> None:
    box.vars.put(testsub2().sub.config("tallies", name), {"name": name, "of": counter})


def test_a_worker_without_a_spec_does_not_start():
    """No spec in the catalogue under its subsystem's name and none handed to it: the constructor refuses, by name —
    there is no «empty spec» to fall back on, so no key of the spec can be skipped by a worker that forgot it. A spec of
    another subsystem is refused too. In the catalogue, the worker runs by the catalogue's spec, the same object the
    controller and the console run by."""
    box = Box()
    nobody = spec_named("nobody")
    _refused(lambda: _base(box, sub=nobody.sub), "a worker of nobody runs by its spec, and this process has none for it")

    class Mine(Worker):                                            # a subsystem's class, naming nothing: the same
        def reconcile_once(self, now=None):
            return []
    _refused(lambda: Mine(nobody.sub, None, box.vars, box.objects), "a worker of nobody runs by its spec")
    _refused(lambda: _base(box, spec=testsub(), sub=nobody.sub), "a worker of nobody runs by nobody's spec, not testsub's")
    with in_catalogue(testsub2()):
        w = _base(box, sub=testsub2().sub)
        assert w.spec is testsub2()


def test_every_worker_key_is_executed_by_the_base_with_no_line_of_subsystem_code():
    """The bare `Worker` — no subclass — on testsub2, which says each worker key, and on testsub, which says none:

        slot             `slot: {prefix: t, name_env: TALLY_NAME}`: made `t-<n>`, given in `TALLY_NAME`   / `w-<n>`
        lease            `lease: {unconfirmed_max: 600}`: the worker's and every lease it opens            / none
        places           `places: {…, server_field: server, lease: strict}`: a shelf whose row names no
                         server — or another server — is held strictly, one that names its own is not     / never
        events.suppress  `tally.tick: {window: 5, by: [unit]}`: a repeat inside the window is nothing      / written
    """
    box = Box()
    with in_catalogue(testsub2()):
        two = _base(box, sub=testsub2().sub)
        assert two.claim_at_start(None, {}) == "t-1"
        named = _base(box, sub=testsub2().sub)
        assert named.claim_at_start(None, {"TALLY_NAME": "t-5"}) == "t-5"
    one = _base(box, spec=testsub())
    assert one.claim_at_start(None, {"TALLY_NAME": "t-5"}) == "w-1"         # testsub says no `slot`

    _tally(box, "t1", "c1")
    box.vars.put(testsub().sub.config("counters", "c1"), {"name": "c1"})
    assert two.unconfirmed_max == 600.0 and two.take_epoch("t1") == 1 and two.leases["t1"].unconfirmed_max == 600.0
    assert one.unconfirmed_max == 0.0 and one.take_epoch("c1") == 1 and one.leases["c1"].unconfirmed_max == 0.0

    two.server = "srv-1"
    assert two.held_strictly("s1", {"name": "s1"}) and not two.held_strictly("s2", {"name": "s2", "server": "srv-1"})
    assert two.held_strictly("s3", {"name": "s3", "server": "srv-2"})      # another server's: not this worker's
    assert not one.held_strictly("s1", {"name": "s1"})

    assert two.observe("t1", "tally.tick", n=1) is not None
    assert two.observe("t1", "tally.tick", n=2) is None                      # a repeat inside the window: nothing
    assert one.observe("c1", "tally.tick", n=1) is not None and one.observe("c1", "tally.tick", n=2) is not None


def test_the_base_stamps_of_on_every_line_of_a_unit_from_the_spec_and_the_row():
    """testsub2's tally is about a counter (`about: {sub: testsub, field: of}`). The base reads the tally's row when it
    takes the epoch and writes `of: testsub/<counter>` on every line of it: through `observe`, through `write_event`
    under the epoch it holds, and under an epoch it names for a unit it does not hold (read then). A unit of testsub,
    about nothing but itself, has no `of`."""
    box = Box()
    w = _base(box, spec=testsub2())
    w.claim_slot("t-1")
    _tally(box, "t1", "c1")
    _tally(box, "t2", "c2")
    w.take_epoch("t1")
    assert w.abouts == {"t1": "testsub/c1"} and w.of("t1") == "testsub/c1"
    seen = w.observe("t1", "tally.counted", n=1)
    alarm = w.write_event("t1", box.wall(), "tally.jammed", ALARM, depth=3)
    other = w.write_event("t2", box.wall(), "tally.kept", epoch=0)
    lines = read_bucket(seen) + read_bucket(alarm) + read_bucket(other)
    assert {(ln["kind"], ln.get("of")) for ln in lines} == {("tally.counted", "testsub/c1"), ("tally.jammed", "testsub/c1"),
                                                            ("tally.kept", "testsub/c2")}, lines
    assert w.write_event("t2", box.wall(), "tally.kept") is None             # no epoch held, none named: not written
    w.release("t1")
    assert w.abouts == {}

    plain = _base(box, spec=testsub())
    plain.claim_slot("w-1")
    box.vars.put(testsub().sub.config("counters", "c1"), {"name": "c1"})
    plain.take_epoch("c1")
    assert "of" not in read_bucket(plain.observe("c1", "counted"))[0]


def test_a_line_written_through_observe_carries_of_as_every_other_line_does():
    """The regression (the recorder's refused backfill, `archive.backfill.refused`): the lines a subsystem wrote itself
    said `of`, the ones it wrote through the platform's `observe` did not — a query for the counter found the tally's
    jam and not its refused request. On testsub2 every line of `observe` says it, the window's summary too, and a row
    that did not read when the epoch was taken is read again at the line."""
    box = Box()
    w = _base(box, spec=testsub2())
    w.claim_slot("t-1")
    real, row = w.vars, testsub2().sub.config("tallies", "t1")

    class RowAway:                                                 # the store answers; the tally's row does not, now
        def get(self, key):
            if key == row:
                raise OSError("the store is away")
            return real.get(key)

        def __getattr__(self, name):
            return getattr(real, name)
    _tally(box, "t1", "c1")
    w.vars = RowAway()
    assert w.take_epoch("t1") == 1 and w.abouts["t1"] is None               # the row did not read at the take
    w.vars = real
    first = w.observe("t1", "tally.tick", n=1)
    assert w.observe("t1", "tally.tick", n=2) is None
    box.wall.advance(6)
    assert w.flush_suppressed() == 1
    lines = read_bucket(first)
    assert [ln.get("of") for ln in lines] == ["testsub/c1", "testsub/c1"] and lines[-1].get("repeats") == 1, lines
    assert w.abouts["t1"] == "testsub/c1"                                     # read again, and remembered


def test_a_subsystem_that_still_says_of_is_refused():
    """`of` is the base's: a line that says its own — through `observe` or `write_event`, by the log itself
    (`events.refuse_own_of`) — raises before anything is written, whatever the unit, so a call site left over from when
    each subsystem passed it fails where it stands."""
    box = Box()
    w = _base(box, spec=testsub2())
    w.claim_slot("t-1")
    _tally(box, "t1", "c1")
    w.take_epoch("t1")
    _refused(lambda: w.observe("t1", "tally.tick", of="testsub/c1"), "`of` is the platform's to write")
    _refused(lambda: w.write_event("t1", box.wall(), "tally.jammed", of="testsub/c9"), "`of` is the platform's to write")
    _refused(lambda: w.observe("t9", "tally.tick", of=""), "`of` is the platform's to write")    # not held: refused all the same
    assert not os.path.exists(os.path.join(box.resource_root, "testsub2"))


def test_a_request_mark_says_what_its_unit_is_about():
    """The mark a holder writes before it performs a request, and the answer written into it after, say `of` as the
    unit's lines do — and so does the line of the command performed."""
    box = Box()

    class Tallies(Worker):                                         # what testsub2's work is: a count, added to
        def reconcile_once(self, now=None):
            return []

        def held_rows(self):
            return {"t1": {"id": "t1", "of": "c1"}}

        def perform(self, target, row, it):
            return {"added": int(it["add"])}

    w = Tallies(testsub2().sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall,
                resource_root=box.resource_root, spec=testsub2())
    w.claim_slot("t-1")
    _tally(box, "t1", "c1")
    w.assigned_now = frozenset({"t1"})
    box.vars.put(testsub2().sub.request_key("r1"), {"unit": "testsub2/t1", "add": "2", "valid_until": str(box.wall() + 30),
                                                     "at": str(box.wall())})
    done = w.requests()
    for _ in range(50):
        if done:
            break
        done = w.requests()
    assert [d.get("added") for d in done] == [2], done
    mark = json.loads(box.objects.get(testsub2().sub.command_key("r1")))
    assert mark["of"] == "testsub/c1" and mark["outcome"] == "performed", mark
    lines = [ln for p in (w.observe("t1", "tally.other"),) for ln in read_bucket(p)]
    assert {ln["kind"]: ln.get("of") for ln in lines}["command"] == "testsub/c1", lines
