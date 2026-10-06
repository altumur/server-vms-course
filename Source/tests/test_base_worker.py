"""The base worker carries out the keys of its spec by itself, on testsub2 — a subsystem that has nothing of the product
(the product's `baseworker_test.go`, mirrored test for test). Where a place is — and so whether its hold follows the
name, and whether it goes through a silence — is read from the place's row by `placement.places.server_field`, and
where that is not said, or the place is not this worker's server's, the safe reading holds (ADR 0012, ADR 0029). And
`of`, what a unit is about, is the platform's to write into every line of the unit: a line that says its own is refused
by the log itself, whoever opened it; a mark of the console alone names what it marks."""
import logging
import os
import tempfile

from tests.conftest import Box, testsub, testsub2
from w2cplatform import runtime
from w2cplatform.contract import Heartbeat
from w2cplatform.events import CONSOLE_MARKS, OF, OWN_OF_TREES, EventLog, read_bucket
from w2cplatform.journal import Journal
from w2cplatform.spec import RESERVED_NAMES, SubsystemSpec
from w2cplatform.worker import SERVER_UNSAID, Worker

TESTSUB2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata", "testsub2.subsystem.yaml")
SOURCE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _testsub2_without(key: str) -> SubsystemSpec:
    """testsub2 with one key of its `placement.places` taken out: the spec that does not say it. A copy of its own, put in
    no catalogue (`conftest._read`): a loaded testsub2 changes the derived rules of every test after it in the run."""
    from w2cplatform import specyaml
    with open(TESTSUB2, encoding="utf-8") as f:
        spec = SubsystemSpec.from_dict(specyaml.loads(f))
    assert key in spec.places, key
    spec.places = {k: v for k, v in spec.places.items() if k != key}
    return spec


def _tick(box, s):
    box.clock.advance(s); box.wall.advance(s)


class _Silent:
    """The store, not answering: every read and write raises `OSError`."""
    def __getattr__(self, name):
        def away(*a, **kw):
            raise OSError("the store does not answer")
        return away


def _refused(fn, words: str) -> None:
    try:
        fn()
    except ValueError as e:
        assert words in str(e), str(e)
        return
    raise AssertionError(f"not refused: {words}")


def test_a_place_follows_the_name_only_where_the_spec_says_where_it_is():
    """A place held under the worker's NAME by the instance it replaced is taken back at once only where the spec says
    where the place is and it is here: a place of one server from that server, a place any box may write from the box
    the replaced instance ran on. Where the spec does not say — no `server_field` — or the row does not, the hold waits
    to be let go or to lapse, like anybody's."""
    no_field = _testsub2_without("server_field")
    for name, spec, place, row, old, at_once in [
        ("one server's, from that server", testsub2(), "s-here", {"server": "srv-a"}, "host:100:aa", True),
        ("another server's", testsub2(), "s-there", {"server": "srv-b"}, "host:100:aa", False),
        ("any box's, from the box the old instance ran on", testsub2(), "s-any", {"enabled": True}, "host:100:aa", True),
        ("any box's, from an instance that names no box", testsub2(), "s-any", {"enabled": True}, "A", False),
        ("no row", testsub2(), "s-gone", None, "host:100:aa", False),
        ("no server_field in the spec", no_field, "s-here", {"server": "srv-a"}, "host:100:aa", False),
    ]:
        box = Box()
        if row is not None:
            box.vars.put(spec.sub.config("shelves", place), {"name": place, **row})

        def mk(instance):
            w = Worker(spec.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance=instance, spec=spec)
            w.server = "srv-a"
            return w
        first = mk(old)
        assert first.claim_slot(prefer="t-1") == "t-1", name
        assert first.claim_hold([place]) == place, name
        if runtime.box_of(old) is None:
            first.release_slot()                 # a name held live by an instance of no box is nobody's to take (`claim_slot`)
        restarted = mk("host:200:bb")
        assert restarted.claim_slot(prefer="t-1") == "t-1", name
        got = restarted.claim_hold([place])
        assert (got == place) == at_once, (name, got)
        if not at_once:
            _tick(box, restarted.slot_ttl + restarted.HOLD_SKEW)   # the old hold stood still its term: it lapsed
            assert restarted.claim_hold([place]) == place, name


def test_through_a_silence_a_place_is_kept_or_let_go_by_where_its_row_says_it_is():
    """Through a silent store a place of this worker's own server — its row names that server — is held by the units'
    own ceiling (`lease.unconfirmed_max`, ten minutes on testsub2); every other place is let go once its hold has gone
    unconfirmed past its window (`places.lease: strict`): a place any box may write, another server's, one whose row
    the claim could not read, and every place of a worker that names no server (ADR 0029) — which says so once, in
    its log, when it takes a server's place. Without `lease: strict` every place goes by the ceiling."""
    not_strict = _testsub2_without("lease")
    for name, spec, row, server, kept in [
        ("this server's", testsub2(), {"server": "srv-a"}, "srv-a", True),
        ("another server's", testsub2(), {"server": "srv-b"}, "srv-a", False),
        ("a server's, the worker names none", testsub2(), {"server": "srv-a"}, "", False),
        ("any box's", testsub2(), {"enabled": True}, "srv-a", False),
        ("not known where", testsub2(), None, "srv-a", False),
        ("any box's, places not strict", not_strict, {"enabled": True}, "srv-a", True),
    ]:
        box = Box()
        if row is not None:
            box.vars.put(spec.sub.config("shelves", "s-1"), {"name": "s-1", **row})
        w = Worker(spec.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance="box-a:1:w", spec=spec)
        w.server = server or None
        assert w.claim_slot(prefer="t-1") == "t-1", name
        said: list[str] = []

        class Said(logging.Handler):
            def emit(self, record):
                said.append(record.getMessage())
        h = Said()
        logging.getLogger("w2cplatform.worker").addHandler(h)
        try:
            assert w.claim_hold(["s-1"]) == "s-1", name
        finally:
            logging.getLogger("w2cplatform.worker").removeHandler(h)
        unsaid = [m for m in said if "naming no server of its own" in m]
        assert len(unsaid) == (1 if name == "a server's, the worker names none" else 0), (name, said)
        w.vars = _Silent()
        _tick(box, 10 * w.slot_ttl)              # the store says nothing for ten holds' terms: inside the ten minutes
        w.lease_pass()
        assert (w.hold == "s-1") == kept and w.may_write_place("s-1") == kept, (name, w.hold)
        _tick(box, 600)                          # …and past them: nothing is held through a silence longer than the spec says
        w.lease_pass()
        assert w.hold is None, (name, w.hold)


class _Blind:
    """The store, answering everything but the read of one row (`key`) while `blind`: a renewal of the hold goes through
    and the read of where the place is fails."""
    def __init__(self, vars, key: str):
        self.vars, self.key, self.blind = vars, key, False

    def __getattr__(self, name):
        return getattr(self.vars, name)

    def get(self, key, *a, **kw):
        if self.blind and key == self.key:
            raise OSError("the store does not answer for this row")
        return self.vars.get(key, *a, **kw)


def test_where_a_place_is_is_read_again_at_every_renewal():
    """The mark «a place of this server» is read again at every renewal of the hold that succeeds, not only at the take
    (ADR 0029, More Information; the product's `TestWhereAPlaceIsIsReadAgainAtEveryRenewal`): a row read that names
    this worker's server sets it, a row read that names another server — the administrator gave the place away
    mid-hold — or none takes it away, and the next silence lets the place go by its strict lease. A read that fails
    changes nothing, either way: a place whose row the take could not read stays strict until a renewal reads it, and a
    place of this server stays its own through a renewal that could not read its row."""
    spec, box = testsub2(), Box()
    key = spec.sub.config("shelves", "s-1")
    box.vars.put(key, {"name": "s-1", "server": "srv-a"})
    blind = _Blind(box.vars, key)
    w = Worker(spec.sub, None, blind, box.objects, clock=box.clock, wall=box.wall, instance="box-a:1:w", spec=spec)
    w.server = "srv-a"
    assert w.claim_slot(prefer="t-1") == "t-1"
    blind.blind = True                           # the take cannot read where the place is: strict
    assert w.claim_hold(["s-1"]) == "s-1" and w.held_strictly("s-1")
    blind.blind = False
    assert w.renew_hold() and not w.held_strictly("s-1")          # the renewal reads it: this server's own
    box.vars.put(key, {"name": "s-1", "server": "srv-b"})          # the administrator gives it to another server
    assert not w.held_strictly("s-1")                               # (nobody has read that yet)
    assert w.renew_hold() and w.held_strictly("s-1")              # the next renewal has
    box.vars.put(key, {"name": "s-1", "server": "srv-a"})          # given back, and the renewal cannot read it: still strict
    blind.blind = True
    assert w.renew_hold() and w.held_strictly("s-1")
    blind.blind = False
    assert w.renew_hold() and not w.held_strictly("s-1")
    box.vars.put(key, {"name": "s-1", "server": "srv-b"})          # given away, and the renewal cannot read it: still ours
    blind.blind = True
    assert w.renew_hold() and not w.held_strictly("s-1")
    blind.blind = False
    assert w.renew_hold() and w.held_strictly("s-1")              # read at last: another server's
    w.vars = _Silent()
    _tick(box, 10 * w.slot_ttl)                  # a silence inside the units' ceiling: another server's place is let go
    w.lease_pass()
    assert w.hold is None and not w.may_write_place("s-1"), w.hold

    # …and this server's own place, whose last renewal could not read the row, goes through the same silence
    box2 = Box()
    box2.vars.put(key, {"name": "s-1", "server": "srv-a"})
    blind2 = _Blind(box2.vars, key)
    own = Worker(spec.sub, None, blind2, box2.objects, clock=box2.clock, wall=box2.wall, instance="box-a:1:w", spec=spec)
    own.server = "srv-a"
    assert own.claim_slot(prefer="t-1") == "t-1" and own.claim_hold(["s-1"]) == "s-1"
    blind2.blind = True
    assert own.renew_hold() and not own.held_strictly("s-1")
    own.vars = _Silent()
    _tick(box2, 10 * own.slot_ttl)
    own.lease_pass()
    assert own.hold == "s-1" and own.may_write_place("s-1"), own.hold


def test_the_base_writes_of_and_a_line_that_says_its_own_is_refused():
    """What a unit is about is the platform's to write: the worker that takes the unit's epoch reads it from the row by
    the spec's `about` and stamps it on every line of the unit, so a line the subsystem writes without a word of it
    carries it. A line that says its own — an empty one too — is refused, not written over: on the worker's log and on
    any other log of a subsystem's unit, opened past the worker. The platform's own trees alone name theirs: a mark
    what it marks, in the console's tree, and a journal line what was done to, in `audit`. `about.field` is fixed: what was read at the epoch holds while the epoch does, and a new epoch reads the row
    again."""
    box = Box()
    root, now = box.resource_root, box.wall()
    box.vars.put(testsub2().sub.config("tallies", "1"), {"name": "1", "of": "7"})
    w = Worker(testsub2().sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, resource_root=root,
               spec=testsub2())
    w.claim_slot("t-1")
    epoch = w.take_epoch("1")
    log_ = w.event_log("1", epoch)
    path = log_.append(now, "counted", n=1)
    lines = read_bucket(path)
    assert len(lines) == 1 and lines[0][OF] == "testsub/7", lines
    for said in ("testsub/7", "testsub/9", ""):
        _refused(lambda: log_.append(now, "counted", **{OF: said}), "platform's to write")
        past = EventLog(root, "testsub2", "1", epoch)                       # past the worker
        _refused(lambda: past.append(now, "counted", **{OF: said}), "platform's to write")
        _refused(lambda: w.write_event("1", now, "counted", **{OF: said}), "platform's to write")
        _refused(lambda: w.observe("1", "counted", **{OF: said}), "platform's to write")
    assert len(read_bucket(path)) == 1, "a refused line was written"
    box.vars.put(testsub2().sub.config("tallies", "1"), {"name": "1", "of": "9"})
    assert w.of("1") == "testsub/7"                                          # read again under the same epoch: no
    w.release("1")
    w.take_epoch("1")
    assert w.of("1") == "testsub/9"                                          # a new epoch reads the row again

    # a unit about nothing — a counter of testsub — gets no `of`
    c = Worker(testsub().sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, resource_root=root,
               spec=testsub())
    c.claim_slot("w-1")
    box.vars.put(testsub().sub.config("counters", "7"), {"name": "7"})
    cp = c.event_log("7", c.take_epoch("7")).append(now, "opened")
    assert OF not in read_bucket(cp)[0]

    # a mark names the unit it marks, in the console's own log; a journal line, what it was done to
    mark = EventLog(root, CONSOLE_MARKS, "c-1", 1).append(now, "mark", **{OF: "testsub2/1"})
    assert read_bucket(mark)[0][OF] == "testsub2/1"
    said = Journal(root, "testsub2worker", box.wall).say("keep.made", target="testsub2/1", **{OF: "testsub/7"})
    assert said is not None and read_bucket(said)[-1][OF] == "testsub/7"


def test_a_worker_without_its_server_says_so_in_its_heartbeat():
    """A worker that names no server of its own, of a subsystem whose places name theirs (`server_field`), holds none of
    them through a silence, and its heartbeat says so (`server_unsaid`, ADR 0029). A worker with its server, or one of a
    spec whose places say no server, says nothing of it: the field is absent."""
    no_field = _testsub2_without("server_field")
    for name, spec, server, present in [
        ("no server, and the places name one", testsub2(), None, True),
        ("its server named", testsub2(), "srv-a", False),
        ("no server, and the spec names no server_field", no_field, None, False),
    ]:
        box = Box()
        w = Worker(spec.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance="box-a:1:w", spec=spec)
        w.server = server
        w.claim_slot(prefer="t-1")
        w.heartbeat([])
        hb = Heartbeat.from_bytes(box.objects.get(spec.sub.heartbeat_key("t-1")))
        if present:
            assert hb.extra.get("server_unsaid") == SERVER_UNSAID, (name, hb.extra)
        else:
            assert "server_unsaid" not in hb.extra, (name, hb.extra)


def test_only_the_base_says_what_a_log_is_about():
    """The log's `of` (`EventLog._of`) is set in one place, the base worker's `event_log`: no module of a subsystem or of
    the platform sets it besides — the marker is the platform's, not a caller's word. And no subsystem takes a tree
    of the platform's own, whose lines say their own (`OWN_OF_TREES`: the console's marks, the journal)."""
    setters = []
    for top, dirs, files in os.walk(SOURCE):
        dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__", ".venv", "node_modules")]
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(top, f)
                with open(p, encoding="utf-8") as src:
                    for n, line in enumerate(src, 1):
                        if "._of =" in line and "self._of = " not in line:     # the log's own "" at its birth
                            setters.append(f"{os.path.relpath(p, SOURCE)}:{n}")
    assert len(setters) == 1 and setters[0].startswith(os.path.join("w2cplatform", "worker.py")), setters
    for tree in OWN_OF_TREES:
        assert tree in RESERVED_NAMES, tree
        _refused(lambda: SubsystemSpec.from_dict({"name": tree, "unit": {"rows": "marks", "id": "name",
                                                                         "fields": {"name": {"type": "string"}}}}),
                 "a name of the platform's own")


def test_a_spec_named_as_one_of_the_platforms_own_names_does_not_load():
    """The platform's trees and spaces — `console` (its marks), `audit` (its journal), `platform` (its keys) and `domain`
    (the domain's space) — are one reserved set (ADR 0029, More Information): a spec of such a name is refused at load,
    from its file as from a dict (the strict loader, ADR 0012). Any other name loads."""
    assert RESERVED_NAMES == {"console", "audit", "platform", "domain"}, RESERVED_NAMES
    with open(TESTSUB2, encoding="utf-8") as f:
        text = f.read()
    assert text.count("\nname: testsub2\n") == 1
    d = tempfile.mkdtemp(prefix="reserved-")
    for name in sorted(RESERVED_NAMES):
        path = os.path.join(d, f"{name}.subsystem.yaml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace("\nname: testsub2\n", f"\nname: {name}\n", 1))
        _refused(lambda: SubsystemSpec.load(path), f"`{name}` is a name of the platform's own")
    from w2cplatform import specyaml
    other = specyaml.loads(text.replace("\nname: testsub2\n", "\nname: testsub3\n", 1))
    assert SubsystemSpec.from_dict(other).name == "testsub3"     # (from a dict: nobody's catalogue, the run's specs stay)
