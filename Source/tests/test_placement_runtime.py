"""ADR-0074 assignment storage, carry and admin door on testsub/testsub2."""
import json
import urllib.request
import urllib.error

from w2cplatform.domain import placement
from w2cplatform.domain.agent import DomainAgent
from w2cplatform.domain.api import ApiError, ConsoleAPI
from w2cplatform.domain.console import Console
from w2cplatform.domain.federation import DomainDirectory
from w2cplatform.domain.rights import roles
from w2cplatform.variables import Conflict
from tests.test_book_runtime import site
from tests.test_book_names import raises


def test_assignments_are_scoped_by_subsystem_and_validate_the_admitted_roster():
    with site(two=True) as e:
        first = placement.assign(e.north.vars, "testsub", "badge", {"cluster": "north", "origin": "south"}, e.wall)
        second = placement.assign(e.north.vars, "testsub2", "badge", {"cluster": "south", "copies": ["north"]}, e.wall)
        assert first["rev"] < second["rev"] and first["origin"] == "south"
        assert placement.read(e.north.vars, "testsub", "badge") == first
        assert not e.north.vars.list("domain/placement/badge")
        for body in ({"cluster": "knocking"}, {"cluster": "north", "origin": "knocking"},
                     {"cluster": "north", "copies": ["knocking"]}, {"cluster": "north", "copies": ["north"]},
                     {"cluster": "north", "copies": "south"}, {"cluster": "north", "unit": "forbidden"},
                     {"cluster": "north", "copies": ["south", "south"]}):
            assert raises(ApiError, lambda: placement.assign(e.north.vars, "testsub", "badge", body, e.wall)).status == 400
        assert placement.read(e.north.vars, "testsub", "badge") == first
        assert raises(ValueError, lambda: placement.path("testsub", "../badge"))


def test_reachability_placer_requires_a_subsystem_and_does_not_replace_operator_links():
    with site() as e:
        p = placement.ClusterPlacer(e.fed, sub="testsub", clock=e.wall)
        operator = placement.assign(e.north.vars, "testsub", "badge", {"cluster": "south", "origin": "north"}, e.wall)
        assert p.place(placement.UnitSite("badge", "unreachable-network")).cluster == "south"
        assert placement.read(e.north.vars, "testsub", "badge") == operator
        assert p.path("badge") == "domain/placement/testsub/badge"


def test_assignment_retry_has_no_write_and_stale_cas_does_not_replace_an_operator_choice():
    with site() as e:
        body = {"cluster": "north", "origin": "south"}
        placement.assign(e.north.vars, "testsub", "badge", body, e.wall)
        key = placement.path("testsub", "badge")
        first, index = e.north.vars.get(key)
        e.wall.advance(1)
        placement.assign(e.north.vars, "testsub", "badge", body, e.wall)
        assert e.north.vars.get(key) == (first, index)
        placement.assign(e.north.vars, "testsub", "badge", {**body, "cluster": "south", "origin": "north"}, e.wall)
        raises(Conflict, lambda: placement.assign(e.north.vars, "testsub", "badge", body, e.wall, cas=index))
        assert placement.read(e.north.vars, "testsub", "badge")["cluster"] == "south"


def test_agent_carries_all_assignment_rows_and_rejects_older_or_unverified_carry():
    with site(two=True) as e:
        for sub in ("testsub", "testsub2"):
            placement.assign(e.north.vars, sub, "badge", {"cluster": "north", "origin": "south"}, e.wall)
        south = e.fed.clusters["south"]
        agent = DomainAgent("south", e.north.vars, south.vars, now=e.wall)
        assert agent._sync()
        for sub in ("testsub", "testsub2"):
            assert placement.read(south.vars, sub, "badge") == placement.read(e.north.vars, sub, "badge")
        key = placement.path("testsub", "badge")
        old = e.north.vars.get(key)[0]
        placement.assign(e.north.vars, "testsub", "badge", {"cluster": "south"}, e.wall)
        assert agent._sync() and placement.read(south.vars, "testsub", "badge")["cluster"] == "south"
        e.north.vars.put(key, old)
        assert agent._sync() and placement.read(south.vars, "testsub", "badge")["cluster"] == "south"
        e.north.vars.put(key, {**old, "rev": "999", "cluster": "north"})
        e.north.vars.put("domain/keys", e.signer.tokens.keyset().to_items())
        assert agent._sync() and placement.read(south.vars, "testsub", "badge")["cluster"] == "south"


def test_placement_door_requires_admin_and_refuses_unknown_members_without_changing_state():
    with site() as e:
        directory = DomainDirectory(e.fed)
        api = ConsoleAPI(directory, lambda n: None, verifier=lambda token: token)
        con = Console(directory, e.holder.view, api, holder_vars=e.north.vars, admin=lambda s: s == "admin")
        door = con.serve(port=0)
        def put(token, body, path="/domain/placement/testsub/badge"):
            req = urllib.request.Request(f"http://127.0.0.1:{door.server_address[1]}" + path,
                                         data=json.dumps(body).encode(), method="PUT",
                                         headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as ex:
                return ex.code, json.loads(ex.read())
        try:
            assert put("viewer", {"cluster": "north"})[0] == 403
            assert put("admin", {"cluster": "knocking"})[0] == 400
            assert put("admin", {"cluster": "north"}, "/domain/placement/unknown/badge")[0] == 400
            assert put("admin", {"cluster": "north", "origin": "south"})[0] == 200
            assert placement.read(e.north.vars, "testsub", "badge")["origin"] == "south"
            con.admin = None
            assert put("admin", {"cluster": "south"})[0] == 403
        finally:
            con.stop(door)


def test_actual_agent_and_console_rights_allow_assignment_writes_only_where_required():
    from w2cplatform.rights import allowed
    with site() as e:
        for name in ("domainagent", "domainconsole"):
            assert allowed(roles(specs=e.specs)[name]["write"], placement.path("testsub", "badge"))
        assert "domain/placement" in roles(specs=e.specs)["domainconsole"]["write"] or \
               "domain/placement*" in roles(specs=e.specs)["domainconsole"]["write"]


def test_planned_move_and_theft_restore_assignments_under_the_same_platform_paths():
    from w2cplatform.domain.term import DomainHolder, move_domain
    from w2cplatform.trust.documents import sign
    for stolen in (False, True):
        with site() as e:
            expected = placement.assign(e.north.vars, "testsub", "badge", {"cluster": "north", "origin": "south"}, e.wall)
            record = sign({"term": 1, "holder": "north", "at": e.wall()}, e.root)
            term = DomainHolder(e.fed, "north", e.signer, 1, e.wall, objects=e.north.objects, record=record)
            term.claim()
            term.backup(["south"], e.north.objects)
            south = e.fed.clusters["south"]
            agent = DomainAgent("south", e.north.vars, south.vars, now=e.wall, domain_objects=e.north.objects,
                                cluster_objects=south.objects, sealer=e.rings["south"], key=e.memberkeys["south"])
            assert agent.sync()
            moved, _ = move_domain(e.fed, "south", e.root.recovery(), "acme", lambda n: e.fed.clusters[n].objects,
                                   e.wall, stolen=stolen, sealer=e.rings["south"])
            assert placement.read(moved.vars, "testsub", "badge") == expected


def test_unadmitted_configured_candidate_cannot_win_reachability_placement():
    with site() as e:
        e.north.vars.put("domain/members", {"doc": json.dumps({"rev": 2, "members": {"north": {}}})})
        p = placement.ClusterPlacer(e.fed, sub="testsub", clock=e.wall, headroom=lambda c: 100 if c == "south" else 1)
        for c in e.fed.clusters.values():
            c.networks = lambda: {"net"}
        assert p.place(placement.UnitSite("badge", "net")).cluster == "north"
