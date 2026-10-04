"""One name, two processes: who is left without it, and how anybody finds out (the owner's decision of 4 Oct, the
product's r24-names).

A unit names its process (`WORKER_NAME=w-%l-1`, `RECORDER_NAME`, `SLOT_INDEX`), and that name is the process: two ways
to be left without it.

- On its own box, the unit started again while the old process still lived (it hung past its stop, or somebody started
  a second copy by hand): the new one takes the name at its START — the restart after kill -9 — and the old one is
  fenced at its next renewal. It used to rejoin under whatever was free (`w-2`): a second worker on the server that its
  unit knew nothing about. Now it is NOBODY: it holds nothing, says `worker.name_taken` once an episode, leaves its mark
  (`<sub>/contenders/<name>/<box>`), and takes its own name back only when that is free or lapsed — never from a live
  holder (two live processes of one name on one box would take it from each other for ever), never another number.
- On ANOTHER box a live process holds it (two machines installed with one hostname compute one `w-%l-1`): it is not
  taken. The process refuses with words and exits (`NameOnAnotherBox`), its unit restarts it, and each refusal leaves
  the mark: `/servers` shows `name_conflict` on the holder's row, the controller says `worker.name_conflict` once an
  episode, and `<p>_name_conflicts` counts the names.

A process that took whatever was free (no name given) rejoins as before.
"""
import json
import urllib.request

from w2cplatform.contract import SLOT_LOST_AFTER, NameOnAnotherBox, Slot
from w2cplatform.events import ALARM
from vms.config import SPEC
from vms.controller import VmsController
from vms.worker import FakeActuator, VmsWorker
from tests.conftest import Box
from tests.test_slot_fate import _Said

NAME = "w-srv-1-1"                                         # `w-%l-1` on a server whose short hostname is srv-1


def _unit(box, machine="machine-a", name=NAME, server="srv-1"):
    """`vms-vmsworker` started by its unit on `machine` (systemd's `%m` → `BOX_ID`): the name from the unit."""
    env = {"BOX_ID": machine, **({"WORKER_NAME": name} if name else {})}
    w = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server=server, env=env)
    w.journal = _Said()
    return w


def _tick(box, seconds, *live):
    box.clock.advance(seconds); box.wall.advance(seconds)
    for w in live:
        assert w.renew_slot()
        w.heartbeat_once()


def _holder(box, name=NAME) -> str:
    return Slot.from_items(name, box.vars.get(SPEC.sub.slot_key(name))[0]).holder


def _mark(box, machine, name=NAME):
    raw = box.objects.get(SPEC.sub.contender_key(name, machine))
    return json.loads(raw) if raw else None


def _ctl(box):
    ctl = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, wall=box.wall)
    ctl.journal = _Said()
    return ctl


def test_a_process_named_by_its_unit_whose_name_was_taken_is_nobody_and_takes_no_other_number():
    """The old process wakes to find its name taken by the process its unit started after it, on its box. Before: its
    next pass rejoined as `w-2` — a second worker on srv-1 nobody started, given units by the controller, under no
    unit. Now it is nobody — no slot made, no heartbeat, nothing assigned — says `worker.name_taken` once (who holds the
    name, on which box), and leaves its mark; it takes its name back when the holder lets it go, and says so."""
    box = Box()
    a = _unit(box)
    a.heartbeat_once()
    b = _unit(box)                                                       # the unit's restart, the old one alive: taken at start
    assert a.name == b.name == NAME and _holder(box) == b.instance
    a.lease_pass()
    assert not a.recording_allowed and "held by another instance" in a.fenced_reason
    for _ in range(4):                                                   # pass after pass: nobody, and said once
        assert a.rejoin() is None, "it rejoined under another number"
        _tick(box, 5, b)
    assert a.seeking == NAME and a.slot is None and not a.recording_allowed
    assert sorted(_ctl(box).slots()) == [NAME]                           # no w-2
    [(kind, cls, said)] = a.journal.lines
    assert (kind, cls) == ("worker.name_taken", ALARM)
    assert said["worker"] == NAME and said["holder"] == b.instance and said["holder_box"] == "machine-a", said
    mark = _mark(box, "machine-a")
    assert mark["state"] == "nameless" and mark["holder"] == b.instance and mark["instance"] == a.instance
    b.heartbeat_once()
    a.heartbeat_once()                                                   # nothing under the name: the heartbeat is b's
    assert json.loads(box.objects.get(SPEC.sub.heartbeat_key(NAME)))["instance"] == b.instance

    b.release_slot()                                                     # b stops in order: the name is free
    assert a.rejoin() == NAME and a.recording_allowed and _holder(box) == a.instance
    assert [k for k, _, _ in a.journal.lines] == ["worker.name_taken", "worker.name_back"]
    assert _mark(box, "machine-a") is None                               # it asks for nothing any more


def test_a_nobody_takes_its_name_once_the_holder_lapses_and_never_from_a_live_holder():
    """No ping-pong: the old process does not take its name back from the live new one, however long it asks — the
    take of a live holder's name is a START's (the unit says which process is the current one). Once the holder stops
    renewing — it hangs, or dies without a word — the name lapses, and its own nobody takes it once the margin past the
    lapse is out (`SLOT_LOST_AFTER`: the units would move then, and the name goes with them)."""
    box = Box()
    a = _unit(box)
    b = _unit(box)
    a.lease_pass()
    for _ in range(20):
        assert a.rejoin() is None
        _tick(box, 5, b)
        assert b.lease_pass() == [] and b.recording_allowed                # b is never fenced by a
    assert _holder(box) == b.instance
    _tick(box, b.slot_ttl + 1)                                           # b silent past its slot…
    assert a.rejoin() is None                                            # …within the margin: what it started may still write
    _tick(box, SLOT_LOST_AFTER)                                          # …and past it (the twelfth pass, blocker 2)
    assert a.rejoin() == NAME and _holder(box) == a.instance
    b.lease_pass()
    assert not b.recording_allowed and b.rejoin() is None                # now b is the nobody, and takes nothing else
    assert sorted(_ctl(box).slots()) == [NAME]


def test_a_process_that_took_whatever_was_free_still_rejoins_under_a_free_number():
    """No name given (no `WORKER_NAME`, no index): the process is any worker, and fenced it takes whatever is free, as
    before — a lapsed slot first, then a new number."""
    box = Box()
    a = _unit(box, name=None)
    assert a.name == "w-1"
    _unit(box, name="w-1")                                               # somebody started one under that name
    a.lease_pass()
    assert not a.recording_allowed
    assert a.rejoin() == "w-2" and a.recording_allowed and a.journal.lines == []


def test_a_live_holder_on_another_box_keeps_its_name_and_the_refused_process_is_seen():
    """Two machines with one hostname compute one `w-%l-1`. Before: the second box's process took the name, the first
    box's was fenced and rejoined as `w-2`, and its restart took the name back — a ping-pong only the boxes' own logs
    saw. Now the live holder of another box keeps it: the claimant refuses in words and exits (its unit restarts it),
    leaving its mark; `/servers` shows `name_conflict` on the holder's row, the controller says `worker.name_conflict`
    once an episode, `vms_name_conflicts` is 1. A restart on the holder's own box still takes it at once (kill -9), and
    once nobody live holds it the other box's next restart takes it as a lapsed name and asks no more."""
    from tests.test_console_gate import _call, _console
    box = Box()
    a = _unit(box, "machine-a")
    a.heartbeat_once()
    for attempt in range(2):                                             # the unit restarts it, and it refuses again
        try:
            _unit(box, "machine-b")
            raise AssertionError("a live holder on another box was taken")
        except NameOnAnotherBox as e:
            assert e.box == "machine-a" and "WORKER_NAME" in str(e) and "hostname" in str(e), str(e)
        assert _holder(box) == a.instance
        _tick(box, 2, a)
    mark = _mark(box, "machine-b")
    assert mark["state"] == "refused" and mark["holder"] == a.instance and mark["holder_box"] == "machine-a"
    assert mark["server"] == "srv-1" and mark["since"] < mark["at"], mark   # the episode began at the first refusal
    ctl = _ctl(box)
    for _ in range(3):
        rep = ctl.pass_once()
        assert rep["name_conflicts"] == 1, rep
    [(kind, cls, said)] = [line for line in ctl.journal.lines if line[0] == "worker.name_conflict"]
    assert cls == ALARM and said["worker"] == NAME and said["holder_box"] == "machine-a" and said["contender_box"] == "machine-b"

    _, _, _, srv, base = _console(box)
    try:
        servers = _call(base, "GET", "/servers")[1]["servers"]
        row = next(w for w in servers["srv-1"]["workers"] if w["worker"] == NAME)
        conflict = row["name_conflict"]
        assert conflict["holder"] == a.instance and conflict["holder_box"] == "machine-a", conflict
        [who] = conflict["contenders"]
        assert who["box"] == "machine-b" and who["state"] == "refused" and who["server"] == "srv-1", who
        with urllib.request.urlopen(base + "/metrics") as r:
            text = r.read().decode()
    finally:
        srv.shutdown()
    assert "vms_name_conflicts 1\n" in text

    c = _unit(box, "machine-a")                                          # its own box's restart: taken at once
    assert _holder(box) == c.instance
    _tick(box, c.slot_ttl + 1)                                           # and then nobody renews it
    d = _unit(box, "machine-b")
    assert d.name == NAME and _holder(box) == d.instance                 # a lapsed name is anybody's of that name
    assert _mark(box, "machine-b") is None
    assert ctl.pass_once()["name_conflicts"] == 0
