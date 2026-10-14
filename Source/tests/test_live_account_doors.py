"""Approved C5 account HTTP responses, through the actual durable account service."""
import json

from tests.test_live_accounts import Console, fixture, ring, seed
from vms.live_account_doors import AccountDoors
from vms.live_accounts import ACCOUNTS, LiveAccounts
from w2cplatform.sealing import seal_items


def setup():
    box, worker = fixture()
    console = Console()
    service = LiveAccounts(box.vars.as_writer("liveworker", [ACCOUNTS+"*"]),
                           sealer=worker.sealer, console=console, wall=box.wall)
    return box, worker, console, AccountDoors(service)


def test_account_doors_return_approved_names_and_password_only_on_create_or_reset():
    box, worker, console, door = setup()
    status, created = door.handle("POST", "/live/accounts", {"name": "wall"}, "Bearer human", "anna")
    assert status == 200 and set(created) == {"account", "password"}
    assert created["account"] == "wall" and created["password"]
    assert created["password"] not in json.dumps(box.vars.get(ACCOUNTS+"wall")[0])
    status, listed = door.handle("GET", "/live/accounts", None, "Bearer human", "anna")
    assert status == 200 and listed == {"accounts": [{"name": "wall", "at": box.wall(), "by": "anna"}]}
    status, changed = door.handle("PUT", "/live/accounts/wall", {"disabled": True}, "Bearer human", "bob")
    assert (status, changed) == (200, {"account": "wall", "disabled": True})
    assert door.handle("GET", "/live/accounts", None, "Bearer human", "bob")[1] == {
        "accounts": [{"name": "wall", "disabled": True, "at": box.wall(), "by": "bob"}]}
    status, reset = door.handle("POST", "/live/accounts/wall/password", None, "Bearer human", "bob")
    assert status == 200 and set(reset) == {"account", "password"}
    assert reset["account"] == "wall" and reset["password"] != created["password"]
    assert "password" not in json.dumps(door.handle("GET", "/live/accounts", None, "", "")[1])


def test_list_omits_only_zero_metadata_and_never_alters_durable_doc_or_opens_password():
    box, worker, _, door = setup()
    path = ACCOUNTS+"zero"
    doc = {"name": "zero", "disabled": False, "at": 0, "by": ""}
    box.vars.put(path, seal_items(worker.sealer, {"doc": json.dumps(doc), "password_secret": "secret"}, path))
    door.accounts.sealer = ring("not-the-sealing-key")
    assert door.handle("GET", "/live/accounts", None, "", "") == (200, {"accounts": [{"name": "zero"}]})
    assert json.loads(box.vars.get(path)[0]["doc"]) == doc


def test_delete_response_reports_only_revoked_clusters_and_forwards_original_person():
    box, worker, console, door = setup()
    seed(box, worker.sealer)
    console.grants = {"b": [{"subject": "wall", "cap": "view", "scope": "*"}],
                      "a": [{"subject": "other", "cap": "view", "scope": "*"}]}
    assert door.handle("DELETE", "/live/accounts/wall", None, "Bearer original", "anna") == (
        200, {"account": "wall", "deleted": True, "grants_changed": ["b"]})
    assert box.vars.get(ACCOUNTS+"wall")[0] is None
    assert all(call[0:2] == ("Bearer original", "anna") for call in console.calls)
    assert console.grants["a"][0]["subject"] == "other" and console.grants["b"] == []


def test_bad_bodies_methods_routes_and_old_aliases_cannot_mutate_accounts():
    box, _, _, door = setup()
    for body in (None, [], "name", {}, {"name": 1}):
        assert door.handle("POST", "/live/accounts", body, "", "anna")[0] == 400
    for body in (None, [], {}, {"disabled": 0}, {"disabled": "false"}):
        assert door.handle("PUT", "/live/accounts/wall", body, "", "anna")[0] == 400
    for path in ("/stream-clients", "/live/accounts-old", "/live/accounts/wall/password/extra"):
        assert door.handle("POST", path, {}, "", "anna")[0] == 404
    for method, path in (("DELETE", "/live/accounts"), ("GET", "/live/accounts/wall"),
                         ("GET", "/live/accounts/wall/password")):
        assert door.handle(method, path, {}, "", "anna")[0] == 405
    assert list(box.vars.list(ACCOUNTS)) == []


def test_expected_core_refusals_keep_status_and_do_not_leak_passwords():
    box, worker, _, door = setup()
    assert door.handle("POST", "/live/accounts", {"name": "wall"}, "token", "anna")[0] == 200
    status, reply = door.handle("POST", "/live/accounts", {"name": "wall"}, "token", "anna")
    assert status == 409 and set(reply) == {"error", "detail"} and reply["error"] == "refused"
    assert door.handle("POST", "/live/accounts/missing/password", None, "", "anna")[0] == 404
    door.accounts.sealer = None
    assert door.handle("POST", "/live/accounts", {"name": "new"}, "", "anna")[0] == 503
    assert set(box.vars.list(ACCOUNTS)) == {ACCOUNTS+"wall"}


def test_real_holder_claim_lists_itself_before_gateway_derives_the_exact_account_audience():
    from vms.live_accounts import INPUT, accounts
    from w2cplatform.domain.carry import open_row
    from w2cplatform.domain.federation import Cluster, Federation
    from w2cplatform.domain.memberbook import members
    from w2cplatform.domain.members import Members
    from w2cplatform.domain.term import DomainHolder
    from w2cplatform.trust.signer import Signer

    box, worker = fixture("holder")
    authority = box.vars.as_writer("domain", ["domain/*"])
    authority.delete("domain/members")
    roster = Members(authority, box.wall, configured=lambda: ["holder", "a"], domain="holder")
    assert roster.settle()
    assert sorted(roster.read()["members"]) == ["a"]  # settle alone is not a claimed holder
    seed(box, worker.sealer)
    assert accounts(worker, []) == {}
    fed = Federation()
    fed.add(Cluster("holder", authority, box.objects, is_domain_holder=True))
    holder = DomainHolder(fed, "holder", Signer("c5-test", authority, now=box.wall), 1,
                          box.wall, objects=box.objects)
    holder.claim()
    assert members(box.vars, "holder") == ("a", "holder")
    contribution = open_row(worker.sealer, accounts(worker, []), INPUT+worker.name)
    assert json.loads(contribution["wall"])["to"] == ["a", "holder"]
    copied, _ = box.vars.get("domain/members")
    box.vars.put("domain/member-list", copied)
    assert members(box.vars, "a") == ("a", "holder")
    # No invention of membership by the publisher when the record is absent or broken.
    for row in (None, {"doc": "{"}):
        if row is None:
            authority.delete("domain/holder")
        else:
            box.vars.put("domain/holder", row)
        assert accounts(worker, []) == {}
