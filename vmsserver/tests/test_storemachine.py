"""The replicated store's state machine, its rights and its API — with no raft library and no socket
(`w2cplatform/storemachine.py`). What the daemon applies on every member and what a stand applies in one process is
this code, so what is proved here holds for both; `test_configstore.py` proves the raft half where `pysyncobj` is
installed, `test_configstorevars.py` the handle and the daemon's doors without it."""
from __future__ import annotations

import json
import os
import pickle
import sys
import tempfile

import pytest

from w2cplatform.storemachine import ADMIN, Ambiguous, Rights, StoreMachine, Unavailable, answer, local_transport
from w2cplatform.configstorevars import ConfigstoreVariables, StoreAmbiguous, StoreUnavailable
from w2cplatform.variables import Conflict, Forbidden

# A small rights file, in the format `python3 -m cluster rights` generates from the spec (М11).
RIGHTS = {"roles": {
    "vmsworker": {"read": ["vms/*"], "write": ["vms/epoch/*", "vms/slots/*"], "delete": ["vms/slots/*"]},
    "console": {"read": ["vms/*", "rec/*"], "write": ["vms/cameras/*"], "delete": ["vms/cameras/*"]},
    "domainagent": {"read": ["domain/*"], "write": ["domain/*"], "delete": ["domain/*"]},
}}


def _put(m, key, items, cas=None, op_id=None):
    cmd = {"op": "put", "key": key, "items": items, "cas": cas}
    if op_id:
        cmd["id"] = op_id
    return m.apply(cmd)


def test_an_absent_key_reads_as_nothing_and_create_only_takes_it_once():
    """`(None, 0)` for a key never written — the API says `index: ""` — and `cas=0` (on the wire `""`) lets exactly
    one creator through: `next_epoch`, `claim_slot` and `Controller.write` start from there."""
    m = StoreMachine()
    assert m.apply({"op": "get", "key": "vms/epoch/7"}) == {"items": None, "index": 0}
    first = _put(m, "vms/epoch/7", {"epoch": 1}, cas="")
    assert "index" in first and not first.get("conflict")
    assert _put(m, "vms/epoch/7", {"epoch": 9}, cas="") == {"conflict": True, "index": first["index"]}
    assert _put(m, "vms/epoch/7", {"epoch": 9}, cas=0)["conflict"]
    assert m.apply({"op": "get", "key": "vms/epoch/7"}) == {"items": {"epoch": "1"}, "index": first["index"]}


def test_a_version_is_the_log_index_above_the_base_and_is_never_handed_out_twice():
    """A version is `base + log index`: every command takes an index — a read, a delete, a conflict too — so no two
    writes ever share a version, a deleted key that comes back has a new one, and a version remembered from before
    conflicts forever."""
    m = StoreMachine(index_base=7000)
    a = _put(m, "k", {"n": 1})["index"]
    assert a == 7001
    m.apply({"op": "get", "key": "k"})
    b = m.apply({"op": "delete", "key": "k", "cas": a})["index"]
    c = _put(m, "k", {"n": 2}, cas=0)["index"]
    assert len({a, b, c}) == 3 and a < b < c
    assert _put(m, "k", {"n": 3}, cas=a)["conflict"], "a version from before the delete matched the new row"
    assert m.apply({"op": "delete", "key": "k", "cas": a}) == {"conflict": True, "index": c}


def test_a_version_this_store_never_handed_out_conflicts():
    """The platform writes `cas=TORN` to replace a row that does not read; a version a file store handed out, a
    boolean, a string that is no number — none of them name a version here, and none of them write."""
    m = StoreMachine()
    i = _put(m, "k", {"n": 1})["index"]
    for cas in ("torn", True, "rv-7", str(i) + "x"):
        assert _put(m, "k", {"n": 2}, cas=cas)["conflict"], cas
    assert _put(m, "k", {"n": 2}, cas=str(i))["index"] > i          # the version's own digits do


def test_a_write_repeated_with_its_id_is_answered_with_its_first_answer():
    """The prototype's finding (the notes on the raft prototype): during an election a write may be retried after
    its first copy landed. With its id the repeat gets the first answer — the same version, nothing applied twice,
    even after another write moved the row — and a conflict is remembered as a conflict. Without the id the same
    write would conflict with itself, and a slot renewal that conflicts fences the worker."""
    m = StoreMachine()
    i = _put(m, "vms/slots/w-2", {"holder": "a"}, cas=0)["index"]
    first = _put(m, "vms/slots/w-2", {"holder": "a", "until": "1"}, cas=i, op_id="op-1")
    j = _put(m, "vms/slots/w-2", {"holder": "b"}, cas=first["index"])["index"]
    assert _put(m, "vms/slots/w-2", {"holder": "a", "until": "1"}, cas=i, op_id="op-1") == first
    assert m.apply({"op": "get", "key": "vms/slots/w-2"}) == {"items": {"holder": "b"}, "index": j}
    lost = _put(m, "vms/slots/w-2", {"holder": "c"}, cas=i, op_id="op-2")
    assert lost["conflict"]
    assert _put(m, "vms/slots/w-2", {"holder": "c"}, cas=j, op_id="op-2") == lost, "a remembered conflict wrote"
    assert _put(m, "vms/slots/w-2", {"holder": "c"}, cas=i)["conflict"], "a NEW write against an old version passed"


def test_the_operation_memory_forgets_the_oldest_first(monkeypatch):
    """Bounded, and forgotten in log order — the same on every member, because every member applies the same log."""
    # The module the machine itself runs in: `test_portability` re-imports the package, and the package attribute
    # may be a second copy of the module by now.
    monkeypatch.setattr(sys.modules[StoreMachine.__module__], "OP_MEMORY", 3)
    m = StoreMachine()
    for n in range(5):
        _put(m, f"k{n}", {"n": n}, op_id=f"op-{n}")
    assert list(m.done) == ["op-2", "op-3", "op-4"]


def test_the_base_is_fixed_once_a_row_is_written():
    """`-index-base` is the group's first command (`configstore -bootstrap`); a base that moved under rows that exist
    would hand out versions some row already had."""
    m = StoreMachine()
    assert m.apply({"op": "base", "base": 1500}) == {"base": 1500}
    assert _put(m, "k", {"n": 1})["index"] == 1502
    got = m.apply({"op": "base", "base": 10})
    assert "refused" in got and m.base == 1500


def test_two_machines_fed_the_same_log_hold_the_same_rows_and_a_dump_carries_everything():
    """The machine decides from the command and its state only: two members applying one log agree, and a member
    restored from a dump (pysyncobj pickles the consumer) goes on exactly where the other is — ids remembered too."""
    log = [{"op": "base", "base": 100}, {"op": "put", "key": "a", "items": {"x": 1}, "cas": "", "id": "1"},
           {"op": "put", "key": "b", "items": {"y": 2}, "cas": None, "id": "2"},
           {"op": "member", "id": "srv-a", "raft": "10.0.0.1:8301", "api": "srv-a@10.0.0.1:8300"},
           {"op": "delete", "key": "a", "cas": 102, "id": "3"}, {"op": "get", "key": "b"}]
    one, two = StoreMachine(), StoreMachine()
    answers = [(one.apply(c, i + 1), two.apply(c, i + 1)) for i, c in enumerate(log)]
    assert all(x == y for x, y in answers)
    assert one.rows == two.rows and list(one.done) == list(two.done) and one.members == two.members
    three = pickle.loads(pickle.dumps(one))
    nxt = {"op": "put", "key": "b", "items": {"y": 3}, "cas": 103, "id": "4"}
    assert three.apply(nxt, 7) == one.apply(nxt, 7)
    assert three.apply(log[2], 8) == {"index": 103}, "a dump forgot the ids it had answered"


def test_what_the_machine_hands_out_is_a_copy():
    m = StoreMachine()
    items = {"n": "1"}
    _put(m, "k", items)
    items["n"] = "2"
    got = m.apply({"op": "get", "key": "k"})
    got["items"]["n"] = "3"
    assert m.apply({"op": "get", "key": "k"})["items"] == {"n": "1"}


# -- rights -------------------------------------------------------------------------------------------
def test_rights_grant_by_role_action_and_prefix():
    r = Rights.parse(RIGHTS)
    assert r.allows("vmsworker", "write", "vms/slots/w-1") and r.allows("vmsworker", "read", "vms/cameras/7")
    assert not r.allows("vmsworker", "write", "vms/cameras/7")
    assert not r.allows("vmsworker", "read", "rec/recordings/1")
    assert not r.allows("vmsworker", "delete", "vms/epoch/7")
    assert not r.allows("nobody", "read", "vms/cameras/7"), "a role the file does not name was granted something"
    assert r.allows(ADMIN, "write", "anything/at/all")


def test_nobody_deletes_an_epoch_and_only_the_domains_roles_delete_domain_rows():
    """The two deletes `variables.refuse_delete` refuses on every backend, refused by the daemon too — for the
    root-only socket as well: an epoch deleted starts again from 1, a name somebody's footage already has."""
    r = Rights.parse({"roles": {**RIGHTS["roles"], "vmsworker": {"delete": ["vms/*"]}}})
    for role in (ADMIN, "vmsworker"):
        assert not r.allows(role, "delete", "vms/epoch/7"), role
    assert not r.allows(ADMIN, "delete", "domain/keys/1")
    assert r.allows("domainagent", "delete", "domain/keys/1") and not r.allows("console", "delete", "domain/keys/1")


def test_a_denial_wins_over_every_grant_wherever_it_stands():
    """The product's format (its configstore round 2): a pattern with a leading `!` DENIES, asked before the grants —
    a role may read the domain's rows but not the emergency password's hash, whichever order the file lists them in."""
    for read in (["domain/*", "!domain/break_glass"], ["!domain/break_glass", "domain/*"]):
        r = Rights.parse({"roles": {"console": {"read": read, "write": ["vms/*", "!vms/epoch/*"]}}})
        assert r.allows("console", "read", "domain/keys") and not r.allows("console", "read", "domain/break_glass")
        assert r.allows("console", "write", "vms/cameras/1") and not r.allows("console", "write", "vms/epoch/1")
    r = Rights.parse({"roles": {"console": {"read": ["!vms/secret*"]}}})
    assert not r.allows("console", "read", "vms/cameras/1"), "a denial alone grants nothing"
    assert Rights.parse({"roles": {"console": {"read": ["!vms/*"]}}}).allows(ADMIN, "read", "vms/cameras/1")


def test_each_role_says_its_sockets_group_and_the_daemon_takes_it():
    """The product's format: each role carries its socket's `group` — `vms-<role>` for a subsystem's, `w2c-<role>` for
    the platform's. The daemon owns the socket by it (`configstore.socket_group`), and a role without one falls back
    to the same rule; what `/v1/rights` shows is the file's own form, the group with it."""
    from w2cplatform.configstore import socket_group
    doc = {"roles": {"vmsworker": {"group": "vms-vmsworker", "read": ["vms/*"], "write": [], "delete": []},
                     "resource": {"group": "w2c-resource", "read": ["platform/*"]},
                     "console": {"read": ["vms/*"]},
                     "domainagent": {"group": "w2c-domainagent", "read": ["domain/*"]}}}
    r = Rights.parse(doc)
    assert r.groups == {"vmsworker": "vms-vmsworker", "resource": "w2c-resource", "domainagent": "w2c-domainagent"}
    assert socket_group("vmsworker", r) == "vms-vmsworker" and socket_group("domainagent", r) == "w2c-domainagent"
    assert socket_group("console", r) == "vms-console" and socket_group("resource") == "w2c-resource"
    assert r.doc()["roles"]["vmsworker"] == {"group": "vms-vmsworker", "read": ["vms/*"], "write": [], "delete": []}
    assert "group" not in r.doc()["roles"]["console"]
    assert Rights.parse(r.doc()).groups == r.groups                       # the form shown is a file the daemon takes
    for bad in ({"roles": {"vmsworker": {"group": "VMS Worker"}}}, {"roles": {"vmsworker": {"group": 2101}}},
                {"roles": {"vmsworker": {"read": ["!"]}}}, {"roles": {"vmsworker": {"read": ["vms/!epoch"]}}},
                {"roles": {"vmsworker": {"read": ["!!vms/*"]}}}):
        with pytest.raises(ValueError):
            Rights.parse(bad)


def test_a_rights_file_that_is_not_the_format_is_refused_whole():
    """Half a rights file grants what nobody wrote: a file the daemon cannot read whole stops it from starting."""
    for bad in ({}, {"roles": []}, {"roles": {"Vms Worker": {}}}, {"roles": {"admin": {}}},
                {"roles": {"vmsworker": {"writes": ["vms/*"]}}}, {"roles": {"vmsworker": {"read": "vms/*"}}},
                {"roles": {"vmsworker": {"read": ["vms/*/slots"]}}}, {"roles": {"vmsworker": {"read": [""]}}},
                {"roles": {}, "extra": 1}):
        with pytest.raises(ValueError):
            Rights.parse(bad)
    path = os.path.join(tempfile.mkdtemp(), "configstore-rights.json")
    with open(path, "w") as f:
        json.dump(RIGHTS, f)
    assert Rights.load(path).allows("console", "write", "vms/cameras/1")


# -- the API ------------------------------------------------------------------------------------------
class _Submit:
    def __init__(self, machine=None, raises=None):
        self.machine, self.raises, self.calls = machine or StoreMachine(), raises, []

    def __call__(self, cmd):
        self.calls.append(cmd)
        if self.raises:
            raise self.raises
        return self.machine.apply(cmd)


def _write(body):
    return json.dumps(body).encode()


def test_a_role_without_the_grant_is_refused_before_anything_is_submitted():
    """403 at the door: the command never reaches the log — on a daemon it is never forwarded to the leader."""
    sub, r = _Submit(), Rights.parse(RIGHTS)
    code, body = answer("POST", "/v1/write", _write({"op": "put", "key": "vms/cameras/7", "items": {}, "cas": ""}),
                        "vmsworker", r, sub)
    assert (code, body["kind"]) == (403, "forbidden") and sub.calls == []
    code, body = answer("POST", "/v1/write", _write({"op": "delete", "key": "vms/epoch/7", "cas": None}), ADMIN, r, sub)
    assert (code, body["kind"]) == (403, "forbidden") and sub.calls == []
    code, _ = answer("GET", "/v1/get?key=rec/recordings/1", b"", "vmsworker", r, sub)
    assert code == 403 and sub.calls == []


def test_a_list_answers_only_what_the_role_may_read():
    m = StoreMachine()
    for k in ("vms/cameras/1", "rec/recordings/1", "secrets/vms/token"):
        _put(m, k, {"x": 1})
    r = Rights.parse(RIGHTS)
    code, body = answer("GET", "/v1/list?prefix=", b"", "vmsworker", r, _Submit(m))
    assert code == 200 and list(body["keys"]) == ["vms/cameras/1"]
    code, body = answer("GET", "/v1/list?prefix=", b"", "console", r, _Submit(m))
    assert sorted(body["keys"]) == ["rec/recordings/1", "vms/cameras/1"]


def test_the_api_says_absent_conflict_and_not_a_key_in_the_products_words():
    sub, r = _Submit(), Rights.parse(RIGHTS)
    assert answer("GET", "/v1/get?key=vms/x", b"", ADMIN, r, sub) == (200, {"items": None, "index": ""})
    code, body = answer("POST", "/v1/write", _write({"op": "put", "key": "vms/x", "items": {"a": 1}, "cas": ""}),
                        ADMIN, r, sub)
    assert code == 200 and isinstance(body["index"], int)
    code, again = answer("POST", "/v1/write", _write({"op": "put", "key": "vms/x", "items": {"a": 2}, "cas": ""}),
                         ADMIN, r, sub)
    assert (code, again["kind"], again["index"]) == (409, "conflict", body["index"])
    n = len(sub.calls)
    for bad in ("vms/a/../b", "/vms/a", ""):
        code, said = answer("GET", "/v1/get?key=" + bad, b"", ADMIN, r, sub)
        assert (code, said["kind"]) == (400, "badkey"), bad
    code, said = answer("POST", "/v1/write", b"{not json", ADMIN, r, sub)
    assert (code, said["kind"]) == (400, "badrequest")
    assert len(sub.calls) == n, "a request refused at the door reached the log"


def test_not_done_and_outcome_unknown_are_two_answers():
    """503 `unavailable` — no leader took it, NOT done; 503 `ambiguous` — a leader took it and went, it may yet be
    applied. The handle raises `StoreUnavailable` and `StoreAmbiguous` for them, both `OSError`s."""
    r = Rights.parse(RIGHTS)
    body = _write({"op": "put", "key": "vms/x", "items": {}, "cas": None, "id": "op-1"})
    code, said = answer("POST", "/v1/write", body, ADMIN, r, _Submit(raises=Unavailable("no leader")))
    assert (code, said["kind"]) == (503, "unavailable")
    code, said = answer("POST", "/v1/write", body, ADMIN, r, _Submit(raises=Ambiguous("leader went")))
    assert (code, said["kind"]) == (503, "ambiguous")
    for raises, kind in ((Unavailable("x"), StoreUnavailable), (Ambiguous("x"), StoreAmbiguous)):
        h = ConfigstoreVariables("/nowhere", transport=local_transport(_Submit(raises=raises), r, ADMIN))
        with pytest.raises(kind):
            h.put("vms/x", {"a": 1})
    assert issubclass(StoreAmbiguous, StoreUnavailable) and issubclass(StoreUnavailable, OSError)


def test_the_variables_contract_holds_on_the_machine_through_the_handle_and_the_api():
    """Every clause of the contract suite, against `ConfigstoreVariables` over the API over a bare machine — the handle's
    mapping, the API and the machine are the daemon's own code with only the socket and the raft taken out. A stand
    built on this (М11) is held to the same file as `file://`."""
    from tests import test_variables_contract as contract
    clauses = [(n, fn) for n, fn in vars(contract).items() if n.startswith("test_") and callable(fn)]
    assert len(clauses) >= 13, "the contract suite shrank"
    real = contract._store

    def on_machine(writer=None, acl=None, url=None):
        if url:
            return real(writer=writer, acl=acl, url=url)
        h = ConfigstoreVariables("/stand", transport=local_transport(_Submit(StoreMachine(1000)), Rights(), ADMIN))
        return h.as_writer(writer, (acl or {}).get(writer, [])) if writer else h

    failed = []
    contract._store = on_machine
    try:
        for name, fn in clauses:
            try:
                fn()
            except Exception as e:                     # noqa: BLE001 — collected and reported by clause
                failed.append(f"{name}: {type(e).__name__}: {e}")
    finally:
        contract._store = real
    assert not failed, "\n".join(failed)


def test_the_handle_maps_the_wire_back_to_the_contract():
    """`""` is 0 both ways, `Conflict` / `Forbidden` / `ValueError` from 409 / 403 / 400 — what `file://` raises."""
    r = Rights.parse(RIGHTS)
    m = StoreMachine(1000)
    admin = ConfigstoreVariables("/stand", transport=local_transport(_Submit(m), r, ADMIN))
    worker = ConfigstoreVariables("/stand", transport=local_transport(_Submit(m), r, "vmsworker"))
    assert admin.get("vms/slots/w-1") == (None, 0)
    i = worker.put("vms/slots/w-1", {"holder": "a"}, cas=0)
    with pytest.raises(Conflict):
        worker.put("vms/slots/w-1", {"holder": "b"}, cas=0)
    with pytest.raises(Forbidden):
        worker.put("vms/cameras/1", {"x": 1})
    with pytest.raises(ValueError):
        admin.get("vms/../x")
    worker.delete("vms/slots/w-1", cas=i)
    assert admin.get("vms/slots/w-1") == (None, 0)
