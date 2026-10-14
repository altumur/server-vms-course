"""C2 Outcomes: bounded holder history, acknowledged member results, and safe settlement."""
import json
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_member_edits import site, console
from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.domain.agent import DomainAgent
from w2cplatform.domain.federation import Unreachable
from w2cplatform.domain.pending import AgentConsole, PendingEdits, apply_pending


def records(vars_, path):
    return {key: json.loads(value) for key, value in (vars_.get(path)[0] or {}).items()}


def waiting(pending, member, count, prefix="edit"):
    return [pending.add(member, "PUT", "/testsub/counters/unit", {"start": n}, prefix + str(n))
            for n in range(count)]


def result(edit, at, status=200):
    return {"id": edit["id"], "status": status, "result": {"revision": 2}, "error": "",
            "at": at, "what": edit["what"], "kept_at": edit["at"]}


class CountingConsole:
    def __init__(self, inner):
        self.inner, self.calls = inner, []

    def apply(self, entry):
        self.calls.append(entry["id"])
        return self.inner.apply(entry)


def test_holder_keeps_only_fifty_newest_outcomes_not_the_last_fifty_arrivals():
    vars_ = FakeVariables()
    pending = PendingEdits(vars_, lambda: 1757500000.0)
    edits = waiting(pending, "north", 70)
    outcomes = {edit["id"]: result(edit, 1000 + n) for n, edit in reversed(list(enumerate(edits)))}
    pending.reconcile("north", outcomes)
    saved = records(vars_, "domain/outcomes/north")
    assert len(saved) == 50 and set(saved) == {edit["id"] for edit in edits[20:]}
    assert pending.of("north") == {}
    # Receiving an older completion later cannot evict a newer result.
    late = pending.add("north", "PUT", "/testsub/counters/unit", {"start": 99}, "late-old")
    pending.reconcile("north", {late["id"]: result(late, 10)})
    assert records(vars_, "domain/outcomes/north") == saved and pending.of("north") == {}


def test_equal_outcome_times_choose_the_same_fifty_ids_in_either_insertion_order():
    retained = []
    for reverse in (False, True):
        vars_ = FakeVariables()
        pending = PendingEdits(vars_, lambda: 1757500000.0)
        edits = waiting(pending, "north", 60)
        ordered = list(reversed(edits)) if reverse else edits
        pending.reconcile("north", {edit["id"]: result(edit, 1000) for edit in ordered})
        saved = records(vars_, "domain/outcomes/north")
        assert len(saved) == 50 and all(identity == item["id"] for identity, item in saved.items())
        retained.append(set(saved))
        assert pending.of("north") == {}
    assert retained[0] == retained[1]


def test_members_have_independent_history_and_a_reused_id_replaces_its_own_result():
    vars_ = FakeVariables()
    pending = PendingEdits(vars_, lambda: 1757500000.0)
    by_member = {member: waiting(pending, member, 65) for member in ("north", "south")}
    for member, edits in by_member.items():
        pending.reconcile(member, {edit["id"]: result(edit, 1000 + n) for n, edit in enumerate(edits)})
    north = records(vars_, "domain/outcomes/north")
    south = records(vars_, "domain/outcomes/south")
    assert len(north) == len(south) == 50 and set(north).isdisjoint(south)
    first = by_member["north"][-1]
    again = pending.add("north", "PUT", first["path"], {"start": 100}, first["key"])
    assert again["id"] == first["id"] and again["at"] != first["at"]
    pending.reconcile("north", {again["id"]: result(again, 2000, 422)})
    updated = records(vars_, "domain/outcomes/north")
    assert len(updated) == 50 and updated[again["id"]]["status"] == 422
    assert updated[again["id"]]["kept_at"] == again["at"]
    assert records(vars_, "domain/outcomes/south") == south


def test_more_than_fifty_settle_after_a_crash_and_cas_retry_without_losing_a_new_waiter():
    vars_ = FakeVariables()
    pending = PendingEdits(vars_, lambda: 1757500000.0)
    edits = waiting(pending, "north", 70)
    entries = {edit["id"]: edit for edit in edits}
    counted = CountingConsole(SimpleNamespace(apply=lambda edit: (200, {"revision": 2})))
    outcomes = apply_pending(entries, counted, 1000)
    assert len(outcomes) == len(counted.calls) == 70
    put, conflicted = vars_.put, []
    def crash_after_history(path, items, cas=None, **kwargs):
        if path == "domain/outcomes/north" and not conflicted:
            conflicted.append(True)
            previous, index = vars_.get(path)
            put(path, previous or {}, cas=index)       # another writer wins before this history CAS
        if path == "domain/pending/north":
            raise Unreachable("crash before removing the completed waiters")
        return put(path, items, cas=cas, **kwargs)
    with patch.object(vars_, "put", crash_after_history):
        try:
            pending.reconcile("north", outcomes)
        except Unreachable:
            pass
        else:
            raise AssertionError("the crash was not exercised")
    assert conflicted and len(records(vars_, "domain/outcomes/north")) == 50
    assert len(pending.of("north")) == 70
    replayed = apply_pending(entries, counted, 1001, previous=outcomes)
    assert replayed == outcomes and len(counted.calls) == 70
    raced = []
    def add_during_removal(path, items, cas=None, **kwargs):
        if path == "domain/pending/north" and not raced:
            raced.append(None)
            raced[0] = pending.add("north", "PUT", "/testsub/counters/unit", {"start": 999}, "new-waiter")
        return put(path, items, cas=cas, **kwargs)
    with patch.object(vars_, "put", add_during_removal):
        PendingEdits(vars_, lambda: 1757500000.0).reconcile("north", replayed)
    assert pending.of("north") == {raced[0]["id"]: raced[0]}
    assert len(records(vars_, "domain/outcomes/north")) == 50


def test_member_agent_forgets_only_acknowledged_outcomes_and_does_not_apply_waiters_twice():
    with site() as e, console(e) as url:
        first = e.pending.add("north", "POST", "/testsub/counters", {"name": "one"}, "ack-first")
        second = e.pending.add("north", "POST", first["path"], {"name": "two"}, "unack-second")
        counted = CountingConsole(AgentConsole(url, e.key, e.wall))
        agent = DomainAgent("north", e.vars, e.vars, now=e.wall, console=counted, key=e.key)
        assert agent.sync()
        local = records(e.vars, "domain/outcomes")
        assert set(local) == {first["id"], second["id"]} and len(counted.calls) == 2
        assert agent.sync() and records(e.vars, "domain/outcomes") == local and len(counted.calls) == 2
        e.pending.reconcile("north", {first["id"]: local[first["id"]]})
        assert agent.sync()
        assert records(e.vars, "domain/outcomes") == {second["id"]: local[second["id"]]}
        assert len(counted.calls) == 2
        e.pending.reconcile("north", {second["id"]: local[second["id"]]})
        assert agent.sync() and records(e.vars, "domain/outcomes") == {} and len(counted.calls) == 2
        assert len(records(e.vars, "domain/outcomes/north")) == 2


def test_holder_agent_purges_its_bare_acknowledgement_without_erasing_named_history():
    from w2cplatform.domain.rights import agent_denials
    from w2cplatform.variables import FileVariables, Forbidden
    class NoCarry:
        def answer_for(self, *args):
            raise Unreachable("the holder needs no carry connection to settle its own edit")
    with tempfile.TemporaryDirectory() as folder, site(FileVariables(folder)) as e, console(e) as url:
        e.vars.put("domain/holder", {"doc": json.dumps({"holder": "north", "term": 1})})
        edit = e.pending.add("north", "POST", "/testsub/counters", {"name": "own"}, "holder-own")
        agent_vars = e.vars.as_writer("domainagent", ["domain/*", *agent_denials(e.specs)])
        counted = CountingConsole(AgentConsole(url, e.key, e.wall))
        agent = DomainAgent("north", NoCarry(), agent_vars, now=e.wall, console=counted, key=e.key)
        assert agent.sync() is False
        assert edit["id"] in records(e.vars, "domain/outcomes")
        assert records(e.vars, "domain/outcomes/north") == {}
        fed = SimpleNamespace(clusters={"north": SimpleNamespace(is_domain_holder=True, vars=NoCarry())})
        PendingEdits(e.vars.as_writer("domain", ["domain/*"]), e.wall).collect(fed)
        history = records(e.vars, "domain/outcomes/north")
        assert edit["id"] in history and e.pending.of("north") == {}
        assert agent.sync() is False
        assert records(e.vars, "domain/outcomes") == {} and records(e.vars, "domain/outcomes/north") == history
        assert len(counted.calls) == 1
        try:
            agent_vars.put("domain/outcomes/north", {})
        except Forbidden:
            pass
        else:
            raise AssertionError("an agent may not erase the holder's history")
