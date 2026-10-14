"""A member's verified roster and a holder's original are one generic read contract."""
import copy
import json
from tests.conftest import Box
from w2cplatform.domain.memberbook import members
from w2cplatform.spec import SubsystemSpec


def fixture(own="north", holder="north"):
    box = Box()
    box.vars.put("domain/holder", {"doc": json.dumps({"holder": holder, "term": 1})})
    return box, own


def write(vars_, key, names):
    vars_.put(key, {"doc": json.dumps({"rev": 1, "members": {n: {} for n in names}})})


def refused(call):
    try:
        call()
    except ValueError:
        return
    raise AssertionError("unknown roster was accepted as an audience")


def test_holder_uses_original_even_when_a_stale_copy_has_different_members():
    box, own = fixture()
    write(box.vars, "domain/members", ("south", "north"))
    write(box.vars, "domain/member-list", ("removed",))
    assert members(box.vars, own) == ("north", "south")
    box.vars.as_writer("domain", ["domain/*"]).delete("domain/members")
    refused(lambda: members(box.vars, own))


def test_member_uses_only_copy_and_holder_move_switches_location_without_restart():
    box, own = fixture("south")
    write(box.vars, "domain/members", ("old-original",))
    write(box.vars, "domain/member-list", ("north", "south"))
    assert members(box.vars, own) == ("north", "south")
    box.vars.put("domain/holder", {"doc": json.dumps({"holder": "south", "term": 2})})
    write(box.vars, "domain/members", ("south", "new"))
    assert members(box.vars, own) == ("new", "south")


def test_malformed_missing_duplicate_and_unconfirmed_rosters_never_guess_recipients():
    box, own = fixture()
    for doc in (None, {}, {"rev": True, "members": {}}, {"rev": 0, "members": {"north": {}}},
                {"rev": 1, "members": []}, {"rev": 1, "members": {"bad/name": {}}},
                {"rev": 1, "members": {"north": None}}):
        box.vars.put("domain/members", {"doc": json.dumps(doc)})
        refused(lambda: members(box.vars, own))
    box.vars.put("domain/members", {"doc": '{"rev":1,"members":{"north":{},"north":{}}}'})
    refused(lambda: members(box.vars, own))
    box.vars.put("domain/holder", {"doc": "{"})
    refused(lambda: members(box.vars, own))


def test_declared_roster_read_gives_only_read_of_the_holders_counterpart_in_two_subsystems():
    from tests.test_token_requests import raw_spec
    from w2cplatform.cluster.rights import roles
    from w2cplatform.rights import allowed
    for name in ("testsub", "testsub2"):
        raw = raw_spec(name)
        raw["worker"] = {"reads": ["domain/member-list"]}
        rule = roles([SubsystemSpec.from_dict(raw)], "test")[name + "worker"]
        assert allowed(rule["read"], "domain/members")
        assert not allowed(rule["write"], "domain/members")
        assert not allowed(rule["read"], "domain/signer")
        raw = copy.deepcopy(raw)
        raw["worker"]["reads"] = []
        rule = roles([SubsystemSpec.from_dict(raw)], "test")[name + "worker"]
        assert not allowed(rule["read"], "domain/members")


def test_missing_holder_never_turns_a_leftover_copy_into_a_confirmed_audience():
    box, own = fixture("south")
    write(box.vars, "domain/member-list", ("north", "south"))
    assert members(box.vars, own) == ("north", "south")
    box.vars.as_writer("domain", ["domain/*"]).delete("domain/holder")
    refused(lambda: members(box.vars, own))
    from w2cplatform.domain.memberbook import holds
    assert not holds(box.vars, None)
