"""The holder side of the requests family is the base worker's (ADR 0013), on testsub and testsub2 — a holder that says
only what one holder knows:

    held_rows()                   what it holds open now
    request_target(row)           the key of what a request against the row goes into: compared, never called; the
                                  unit itself unless it says otherwise; None — not open yet
    perform(target, row, it)      the call, handed that key
    moved_refusal(unit)           (its own words, if it has them) a unit moved since the request was given

and everything else is the base's, no hook: the fence, the epoch taken before a request's first act and its rules (not
for a unit off the assignment read last, nor for one the lease step let go since that read), the marks, the deadline,
the two kinds every holder writes — `command` and `command.failed`, with the unit's `of` — and what the heartbeat says.
"""
import glob
import json
import os
import threading
import time

from tests.conftest import Box, testsub, testsub2
from w2cplatform.contract import Controller, Heartbeat, NotReadThisPass
from w2cplatform.epoch import current_epoch, next_epoch
from w2cplatform.canonical import canonical_json
from w2cplatform.events import COMMAND, COMMAND_FAILED, read_bucket
from w2cplatform.spec import SubsystemSpec
from w2cplatform.worker import Worker


class Holder(Worker):
    """A subsystem's holder, all of it: the rows it holds open, the key of what each goes into, the call."""

    def __init__(self, box, spec, keys=None, gate=None):
        super().__init__(spec.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall,
                         resource_root=box.resource_root, spec=spec)
        self.open: dict[str, dict] = {}
        self.keys = keys or {}                       # unit -> the key of what it goes into (a box several units share)
        self.gate = gate                             # set: a call waits for it — the target hangs
        self.calls: list[tuple] = []

    def reconcile_once(self, now=None):
        return []

    def held_rows(self):
        return dict(self.open)

    def request_target(self, row):
        return self.keys.get(str(row["id"]), str(row["id"]))

    def perform(self, target, row, it):
        if self.gate is not None:
            self.gate.wait(10)
        if int(it["add"]) < 0:
            raise ValueError("a tally only grows")
        self.calls.append((target, str(row["id"]), int(it["add"])))
        return {"added": int(it["add"])}


def _holder(box, spec, units, held=None, cls=Holder, **kw) -> Holder:
    w = cls(box, spec, **kw)
    w.server = "srv-1"
    w.claim_slot(f"{spec.sub.name[0]}-1")
    Controller(spec.sub, box.vars, box.objects, wall=box.wall).assign(w.name, list(units))
    w.assignment()
    w.open = {u: {"id": u} for u in (held if held is not None else units)}
    return w


def _ask(box, spec, rid, unit, add, **more):
    box.vars.put(spec.sub.request_key(rid), {"unit": unit, "add": str(add), "valid_until": str(box.wall() + 30),
                                             "at": str(box.wall()), **more})


def _look(w, want: int, tries: int = 50) -> list[dict]:
    """Looks until `want` answers came (a call is on a thread of its own: a look waits `PERFORM_GRACE` for it)."""
    done = []
    for _ in range(tries):
        done += w.requests()
        if len(done) >= want:
            break
        time.sleep(0.02)                             # a call not waited for (a slow target's) comes back meanwhile
    return done


def test_the_base_performs_a_request_with_only_what_one_holder_knows():
    """Two counters on one box (`request_target` names the box for both): each request is performed once, into the key
    the holder named, each unit's epoch taken by the base before its first act — and the second call into the box waits
    until the first is back, though the two rows are two objects: the key is compared, not the object. Answered, the
    requests are said in the heartbeat (`fetched`, `command_counts`) and not performed again."""
    box = Box()
    gate = threading.Event()
    w = _holder(box, testsub(), ["c1", "c2"], keys={"c1": "box-a", "c2": "box-a"}, gate=gate)
    _ask(box, testsub(), "r1", "testsub/c1", 2)
    _ask(box, testsub(), "r2", "c2", 3)
    assert w.requests() == [] and set(w.leases) == {"c1"}         # one call begun into box-a; c2 waits its turn
    assert len(w._performing) == 1 and "box-a" in w._performing
    gate.set()
    done = {d["request"]: d for d in _look(w, 2)}
    assert done["r1"]["added"] == 2 and done["r2"]["added"] == 3, done
    assert sorted(w.calls) == [("box-a", "c1", 2), ("box-a", "c2", 3)] and set(w.leases) == {"c1", "c2"}
    for rid in ("r1", "r2"):
        assert json.loads(box.objects.get(testsub().sub.command_key(rid)))["outcome"] == "performed"
    assert w.requests() == [] and len(w.calls) == 2                  # at most once: answered, not performed again
    w.heartbeat_once()
    hb = Heartbeat.from_bytes(box.objects.get(testsub().sub.heartbeat_key(w.name)))
    assert sorted(hb.extra["fetched"].split(",")) == ["r1", "r2"] and hb.extra["command_counts"]["performed"] == 2


def test_a_unit_the_holder_names_no_target_for_is_asked_again_and_the_default_target_is_the_unit():
    """None from `request_target` is "not open yet": the request waits for the next look, unanswered. A holder that
    names no target at all calls each unit on its own — one call at a time into each unit, not one for the whole worker."""
    box = Box()
    w = _holder(box, testsub(), ["c1"], keys={"c1": None})
    _ask(box, testsub(), "r1", "c1", 1)
    assert w.requests() == [] and w.calls == [] and not w.fetched
    w.keys = {}
    assert [d.get("added") for d in _look(w, 1)] == [1] and w.calls == [("c1", "c1", 1)]


def test_a_fenced_holder_performs_nothing_and_leaves_the_request_standing():
    """The fence is the base's: a holder that is nobody (`fence`) reads no row as its own to act on — no mark, no epoch,
    no answer — and whoever holds the unit now performs it."""
    box = Box()
    w = _holder(box, testsub(), ["c1"])
    w.fence("another instance holds w's name")
    _ask(box, testsub(), "r1", "c1", 1)
    assert w.requests() == [] and w.calls == [] and not w.fetched and w.epochs == {}
    assert box.objects.get(testsub().sub.command_key("r1")) is None


def test_no_epoch_is_taken_for_a_request_on_a_unit_off_the_assignment_read_last():
    """A row the holder still has open, of a unit the assignment read last does not name — or after a read that did not
    answer — is not this holder's to take an epoch for (`take_epoch`: `NotReadThisPass`): the request is left, not
    answered, and the unit's epoch row is untouched."""
    box = Box()
    w = _holder(box, testsub(), ["c1"], held=["c1", "c2"])
    _ask(box, testsub(), "r2", "c2", 1)
    assert w.requests() == [] and "c2" not in w.epochs and current_epoch(box.vars, testsub().sub.epoch_key("c2")) == 0
    w.assigned_now = None                                            # the read did not answer
    _ask(box, testsub(), "r1", "c1", 1)
    assert w.requests() == [] and w.epochs == {} and w.calls == []


def test_a_unit_the_lease_step_let_go_is_not_taken_back_by_a_request_before_the_assignment_is_read_again():
    """The lease step found a newer epoch on c1 and let it go (`lost_to_epoch`); the holder still has the row open and the
    list read before still names c1. A request is NOT a reason to take c1 back: `take_epoch` refuses (the epoch's rule,
    whoever asks — the base's requests, a subsystem's gate), the newer holder's epoch stands. The next assignment read
    says c1 is still this holder's, and the request is performed under a new epoch."""
    box = Box()
    w = _holder(box, testsub(), ["c1"])
    _ask(box, testsub(), "r1", "c1", 1)
    assert [d.get("added") for d in _look(w, 1)] == [1] and w.epochs["c1"] == 1
    next_epoch(box.vars, testsub().sub.epoch_key("c1"))              # another holder took epoch 2
    w.lease_pass()
    assert "c1" in w.lost_to_epoch and "c1" not in w.leases
    try:
        w.take_epoch("c1")
        raise AssertionError("an epoch was taken for a unit let go since the assignment was read")
    except NotReadThisPass as e:
        assert "let go to a newer epoch" in str(e), str(e)
    _ask(box, testsub(), "r2", "c1", 5)
    assert w.requests() == [] and "c1" not in w.epochs and len(w.calls) == 1
    assert current_epoch(box.vars, testsub().sub.epoch_key("c1")) == 2      # nothing taken from the other holder
    w.assignment()                                                   # the read answered: still mine
    assert [d.get("added") for d in _look(w, 1)] == [5] and w.epochs["c1"] == 3


def test_the_base_writes_command_and_command_failed_with_the_units_of():
    """The two kinds are the platform's (`events.COMMAND`), written by the base for every holder: what was performed
    (`command`, with what the call answered), what was refused by the target (`command.failed`, its error) and what was
    refused before the call — here a tally moved to another group since the request was given, in the holder's own
    words (`moved_refusal`). Each line carries the unit's `of` (testsub2's `about`: the counter the tally is about)."""
    box = Box()
    box.vars.put(testsub2().sub.config("tallies", "t1"), {"name": "t1", "of": "c1"})

    class Tallies(Holder):
        def moved_refusal(self, unit):
            return f"tally {unit} went to another feed after this was asked"

    w = Tallies(box, testsub2())
    w.server = "srv-1"
    w.claim_slot("t-1")
    Controller(testsub2().sub, box.vars, box.objects, wall=box.wall).assign("t-1", ["t1"])
    w.assignment()
    w.open = {"t1": {"id": "t1", "of": "c1", "feed": "https://feeds.example/a"}}
    _ask(box, testsub2(), "r1", "testsub2/t1", 2, by="ann")
    _ask(box, testsub2(), "r2", "t1", -1)
    _ask(box, testsub2(), "r3", "t1", 4, group="https://feeds.example/b")
    done = {d["request"]: d for d in _look(w, 3)}
    assert done["r1"]["added"] == 2 and "only grows" in done["r2"]["error"], done
    assert done["r3"]["error"] == "tally t1 went to another feed after this was asked"
    path = w.observe("t1", "tally.other")
    lines = [ln for ln in read_bucket(path) if ln.get("kind") in (COMMAND, COMMAND_FAILED)]
    assert sorted(ln["kind"] for ln in lines) == [COMMAND, COMMAND_FAILED, COMMAND_FAILED], lines
    assert {ln.get("of") for ln in lines} == {"testsub/c1"}, lines
    performed = next(ln for ln in lines if ln["kind"] == COMMAND)
    # the platform's fields at the top, the target's answer whole under `reply` (what the console module reads)
    assert performed["outcome"] == "performed" and performed["by"] == "ann" and performed["reply"] == {"added": 2}, performed
    assert "added" not in performed and "late" not in performed
    failed = [ln for ln in lines if ln["kind"] == COMMAND_FAILED]
    assert {ln["outcome"] for ln in failed} == {"refused"} and all("reply" not in ln for ln in failed), failed
    assert {ln.get("error") for ln in failed} == {"a tally only grows", "tally t1 went to another feed after this was asked"}


def test_no_spec_names_the_request_familys_kinds_among_its_own():
    """`command` and `command.failed` are the platform's words: the console module has them, as it has `server.*` and
    `worker.*`. A subsystem's `display.kinds` names only what its own units raise."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = glob.glob(os.path.join(root, "vms", "*.subsystem.yaml")) + glob.glob(
        os.path.join(root, "tests", "testdata", "*.subsystem.yaml"))
    assert paths
    for p in paths:
        kinds = (SubsystemSpec.load(p).display or {}).get("kinds") or {}
        assert not {COMMAND, COMMAND_FAILED} & set(kinds), (p, sorted(kinds))


def test_a_target_that_hangs_holds_its_own_key_and_no_other():
    """A call into one key that does not come back holds that key — its next request waits — and the other keys are
    called on the same look: the hung key is named slow and not waited for again."""
    box = Box()
    hang = threading.Event()

    class Two(Holder):
        def perform(self, target, row, it):
            if target == "box-a":
                hang.wait(10)
            return super().perform(target, row, it)

    w = _holder(box, testsub(), ["c1", "c2"], cls=Two, keys={"c1": "box-a", "c2": "box-b"})
    _ask(box, testsub(), "r1", "c1", 1)
    _ask(box, testsub(), "r2", "c2", 2)
    t0 = time.monotonic()
    done = _look(w, 1, tries=5)
    assert [d.get("added") for d in done] == [2] and time.monotonic() - t0 < 2.0, done
    assert "box-a" in w._performing and w._slow == {"box-a"}
    hang.set()
    assert [d.get("added") for d in _look(w, 1)] == [1]


def test_a_target_that_answers_after_the_timeout_keeps_the_request_answered_and_its_mark_says_what_was_done_late():
    """A call not back after `PERFORM_TIMEOUT` is answered "did not answer" (the request's answer: refused, cleared by
    the console). When the target answers after all, that answer stands and the row is not touched — but the MARK says
    what was really done to it, `late: true` beside the outcome: the next instance says it again rather than `unknown`,
    and `late` tells an execution past the timeout (an incident) from an ordinary one (the architect's decision)."""
    box = Box()
    gate = threading.Event()
    w = _holder(box, testsub(), ["c1"], gate=gate)
    _ask(box, testsub(), "r1", "c1", 4)
    assert w.requests() == [] and len(w._performing) == 1
    box.clock.advance(w.PERFORM_TIMEOUT)
    done = w.requests()
    assert [d.get("error") for d in done] == ["the target did not answer"] and w.fetched == ["r1"], done
    assert "outcome" not in json.loads(box.objects.get(testsub().sub.command_key("r1")))
    gate.set()
    for _ in range(100):
        if not w._performing:
            break
        w.requests()
        time.sleep(0.02)
    mark = json.loads(box.objects.get(testsub().sub.command_key("r1")))
    assert mark["outcome"] == "performed" and mark["late"] is True and w.calls == [("c1", "c1", 4)], mark
    assert w.fetched == ["r1"] and w.commands == {"performed": 0, "refused": 1, "expired": 0, "unknown": 0}
    assert box.vars.get(testsub().sub.request_key("r1"))[0]["add"] == "4"          # the row as it was
    path = w.observe("c1", "counted")
    said = [(ln["kind"], ln.get("outcome"), ln.get("late"), ln.get("error"), ln.get("reply"))
            for ln in read_bucket(path) if ln.get("kind") in (COMMAND, COMMAND_FAILED)]
    assert said == [(COMMAND_FAILED, "refused", None, "the target did not answer", None),
                    (COMMAND, "performed", True, None, {"added": 4})], said   # the incident, on the unit's line
    # the next instance, under another name the unit moved to: the mark's answer, said again — not `unknown`
    w2 = Holder(box, testsub())
    w2.server = "srv-2"
    w2.claim_slot("w-2")
    Controller(testsub().sub, box.vars, box.objects, wall=box.wall).assign("w-2", ["c1"])
    w2.assignment()
    w2.open = {"c1": {"id": "c1"}}
    again = w2.requests()
    assert [(d.get("answered"), d.get("by")) for d in again] == [("performed", w.name)] and w2.calls == [], again
    assert w2.commands["unknown"] == 0 and w2.reanswered == 1


def test_a_family_that_declares_no_most_valid_refuses_every_request_it_is_handed():
    """`most_valid` is the spec's number and nothing else (the loader requires it wherever `valid_for` is declared): a
    family that declares none has no deadline the holder could judge near, and its requests are refused in those words
    rather than measured against a number nobody wrote."""
    box = Box()
    spec = SubsystemSpec.from_dict({"name": "bare", "unit": {"rows": "bares", "id": "name",
                                                             "fields": {"name": {"type": "string", "required": True}}},
                                    "placement": {"capacity": {"from": "capacity", "default": 4}},
                                    "requests": {"free": True, "ttl": 0}})
    assert spec.requests.get("most_valid") is None
    w = _holder(box, spec, ["b1"])
    assert w.most_valid() is None
    box.vars.put(spec.sub.request_key("r1"), {"unit": "b1", "add": "1", "valid_until": str(box.wall() + 30)})
    done = w.requests()
    assert [d.get("error") for d in done] == ["this family declares no `requests.most_valid`: no deadline can be "
                                              "judged near"] and w.calls == [], done


def test_the_familys_numbers_in_the_heartbeat_are_the_bases_and_the_vms_holder_says_none_of_them():
    """What the family counts — the outcomes, the answers said again, the calls in flight, the road to the call — the base
    says in every holder's heartbeat (`Worker.requests_fields`, in `platform_fields`), by the product's names, which the
    spec's `metrics:` reads. A holder that adds nothing to its heartbeat says them all; the VMS holder says none of them
    itself."""
    import inspect
    from vms.worker import VmsWorker
    box = Box()
    gate = threading.Event()
    gate.set()
    w = _holder(box, testsub(), ["c1", "c2"], gate=gate)
    _ask(box, testsub(), "r1", "c1", 1)
    assert [d.get("added") for d in _look(w, 1)] == [1]
    gate.clear()
    _ask(box, testsub(), "r2", "c2", 2)
    w.requests()                                                       # c2's call hangs: in flight
    w.reanswered = 1                                                   # an answer said again (its own test: the late mark)
    w.heartbeat_once()
    hb = Heartbeat.from_bytes(box.objects.get(testsub().sub.heartbeat_key(w.name)))
    for field in ("fetched", "command_counts", "commands_reanswered", "commands_in_flight", "command_road",
                  "command_request", "command_wait"):
        assert field in hb.extra, (field, sorted(hb.extra))
    assert hb.extra["commands_in_flight"] == 1 and hb.extra["command_counts"]["performed"] == 1
    gate.set()
    vms = inspect.getsource(VmsWorker.heartbeat_extra) + inspect.getsource(VmsWorker.heartbeat_fields)
    for field in ("fetched", "command_counts", "commands_reanswered", "commands_in_flight", "command_road",
                  "command_request", "command_wait"):
        assert f'"{field}"' not in vms, field


def test_a_mark_and_a_contenders_row_are_written_in_the_one_canonical_text():
    """The base writes its store rows through `canonical_json` (compact, keys sorted, numbers by `number_text` — the
    product's `CanonicalJSON`): the request's mark before the call, the answer written into it after, and the mark a
    process leaves on a name another instance holds. A Go reader and a Python one read the same bytes."""
    box = Box()
    w = _holder(box, testsub(), ["c1"])
    _ask(box, testsub(), "r1", "c1", 3)
    raw = box.objects.get(testsub().sub.command_key("r1"))
    assert raw is None
    w._mark("r1", "c1", box.wall())
    raw = box.objects.get(testsub().sub.command_key("r1")).decode()
    assert raw == canonical_json(json.loads(raw)) and ", " not in raw, raw
    box.objects.delete(testsub().sub.command_key("r1"))
    assert [d.get("added") for d in _look(w, 1)] == [3]
    raw = box.objects.get(testsub().sub.command_key("r1")).decode()
    assert raw == canonical_json(json.loads(raw)) and json.loads(raw)["outcome"] == "performed", raw
    w._contend("w-9", "somebody-else", "nameless")
    key = testsub().sub.contender_key("w-9", w._box())
    raw = box.objects.get(key).decode()
    assert raw == canonical_json(json.loads(raw)), raw
