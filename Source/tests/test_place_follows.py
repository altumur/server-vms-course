"""Whether a place follows its worker's NAME (`Worker.hold_follows_name`; the architect's rule after step 7: a platform
default that weakens a fence or the single writer is off until the spec turns it on). An instance that takes a worker's
name takes its place back at once only where the spec says where the place is (`placement.places.server_field`) and the
place's row says it; anywhere else it waits like anybody — the row standing still `slot_ttl + HOLD_SKEW` by its own
clock — or until the place is let go. On testsub2, whose units are kept on shelves."""
import os

from w2cplatform.spec import SubsystemSpec
from w2cplatform.worker import Worker
from tests.conftest import Box

TESTSUB2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata", "testsub2.subsystem.yaml")


def _spec(server_field: str):
    spec = SubsystemSpec.load(TESTSUB2)
    spec.places = {**spec.places, "server_field": server_field}
    return spec


def _shelf(box, spec, name, server):
    box.vars.put(spec.sub.config("shelves", name), {"name": name, "server": server, "enabled": True})


def _worker(box, spec, instance, server="srv-1"):
    w = Worker(spec.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance=instance, spec=spec)
    w.server = server
    w.claim_slot(prefer="t-1")
    return w


def _tick(box, s):
    box.clock.advance(s); box.wall.advance(s)


def test_a_place_of_a_spec_that_names_no_server_field_waits_and_follows_the_name_from_no_box():
    """No `server_field`: where the place is is not known, so it does not follow the name — not on the same box, not
    from another; the instance that took the name waits out the hold like anybody, and a hold let go is free at once."""
    box = Box()
    spec = _spec("")
    _shelf(box, spec, "s1", "srv-1")
    first = _worker(box, spec, "box-a:1:first")
    assert first.claim_hold(["s1"]) == "s1"
    again = _worker(box, spec, "box-a:2:again")                       # the same name, another instance, the same box
    assert not again.hold_follows_name("s1", first.instance)
    assert not again.hold_follows_name("s1", "box-b:9:other")         # …nor from another box
    assert again.claim_hold(["s1"]) is None                           # waits: the old one may be writing
    _tick(box, again.slot_ttl + again.HOLD_SKEW - 1)
    assert again.claim_hold(["s1"]) is None
    _tick(box, 1)
    assert again.claim_hold(["s1"]) == "s1"                           # the row stood still a term and the skew
    again.release_hold()
    third = _worker(box, spec, "box-a:3:third")
    assert third.claim_hold(["s1"]) == "s1"                           # let go on purpose: at once


def test_a_place_follows_the_name_only_from_where_its_row_says_it_is():
    """With `server_field`: a shelf whose row names a server follows the name on that server, and only there; a shelf
    whose row names none (any box may write it) follows it only on the holder's own box."""
    box = Box()
    spec = _spec("server")
    _shelf(box, spec, "s1", "srv-1")
    _shelf(box, spec, "net", "")
    first = _worker(box, spec, "box-a:1:first")
    assert first.claim_hold(["s1"]) == "s1"
    again = _worker(box, spec, "box-a:2:again")
    assert again.claim_hold(["s1"]) == "s1"                           # its server's place: at once
    elsewhere = Worker(spec.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, instance="box-b:3:x",
                       spec=spec)
    elsewhere.server = "srv-2"
    assert not elsewhere.hold_follows_name("s1", again.instance)      # the name on another server: no
    assert again.hold_follows_name("net", first.instance)             # any box's place, from the holder's own box
    assert not elsewhere.hold_follows_name("net", first.instance)     # …and from another box, no


def test_a_place_whose_row_does_not_read_waits_and_the_claim_raises_nothing():
    """The place's row read raising — the store away (`OSError`), a row that does not parse — while the instance that
    took the name claims the hold back: where the place is is not known, so it waits (the safe side), and the claim
    answers None instead of raising (it raised `NameError`: `PARSE_ERRORS` was not imported where it was used)."""
    box = Box()
    spec = _spec("server")
    _shelf(box, spec, "s1", "srv-1")
    first = _worker(box, spec, "box-a:1:first")
    assert first.claim_hold(["s1"]) == "s1"
    again = _worker(box, spec, "box-a:2:again")
    real, row = box.vars, spec.sub.config("shelves", "s1")
    for err in (OSError("the store is away"), ValueError("a row that does not parse")):
        class Flaky:
            def __getattr__(self, name):
                return getattr(real, name)

            def get(self, key, *a, **kw):
                if key == row:
                    raise err
                return real.get(key, *a, **kw)
        again.vars = Flaky()
        assert not again.hold_follows_name("s1", first.instance)
        assert again.claim_hold(["s1"]) is None, err                  # waits, and says nothing worse
    again.vars = real
    assert again.claim_hold(["s1"]) == "s1"                           # the row reads again: its server's place, at once
