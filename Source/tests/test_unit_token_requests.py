"""C4 generic unit scope, immutable reports and topology; testsub/testsub2 only."""
import copy
import json
from contextlib import contextmanager
from unittest.mock import patch

from tests.conftest import Box
from tests.test_book_runtime import site
from tests.test_token_requests import client, raw_spec
from tests.test_book_names import raises
from w2cplatform import catalog
from w2cplatform.spec import SubsystemSpec
from w2cplatform.domain import declared, tokenrequest
from w2cplatform.domain.carry import HolderDoor, Refused, publication_bytes
from w2cplatform.domain.reports import read
from w2cplatform.domain.topology import poll_home
from w2cplatform.domain.uplink import base, report
from w2cplatform.trust.tokens import DeclaredIssuer, verify


def unit_raw(sub="testsub"):
    raw = raw_spec(sub)
    raw["domain"]["ref"] = "name"
    token = raw["domain"]["tokens"]["tally"]
    del token["placement"]
    token["unit"] = {"ref_claim": "ref", "target_fields": ["poll_home"], "audience_claim": "aud"}
    return raw


@contextmanager
def issuing():
    with site(two=True) as e:
        specs = [SubsystemSpec.from_dict(unit_raw(s.name)) for s in e.specs]
        specs[1].domain.tokens["tally2"] = specs[1].domain.tokens.pop("tally")
        with patch.object(catalog, "_loaded", {s.name: s for s in specs}), patch.object(catalog, "_derived", {}):
            e.specs = specs
            e.north.vars.put("domain/holder", {"doc": json.dumps({"holder": "north", "term": 1})})
            e.door = HolderDoor(e.north.vars, e.north.objects, wall=e.wall,
                                token_issuer=DeclaredIssuer(e.signer.tokens, declared.token_kinds()))
            yield e


def publish(e, member="south", sub="testsub", refs=("badge",), *, accepted=True):
    spec = catalog.spec(sub)
    cluster = e.fed.clusters[member]
    cluster.objects.put(sub + "/snapshot/c4", json.dumps({"ts": e.wall(), "cluster": member,
        spec.rows: [{spec.domain.ref: ref, "id": str(i)} for i, ref in enumerate(refs)]}).encode())
    if accepted:
        e.wall.advance(1)
        report(member, cluster.vars, cluster.objects, e.north.objects, e.wall(), key=e.memberkeys[member])


def requested(e, sub="testsub", member="south", ref="badge", role=None):
    kind = "tally2" if sub == "testsub2" else "tally"
    return client(e, member).request_token(sub, kind, ref, role or sub + "worker")


def claims(e, sub="testsub", member="south", **kw):
    return verify(requested(e, sub, member, **kw)["token"], e.signer.tokens.keyset(), now=e.wall())


def test_unit_loader_is_closed_requires_claims_grant_and_reference():
    for sub in ("testsub", "testsub2"):
        raw = unit_raw(sub)
        rule = SubsystemSpec.from_dict(raw).domain.tokens["tally"]
        assert rule["unit"] == {"ref_claim": "ref", "target_fields": ("poll_home",), "audience_claim": "aud"}
        for change in ({"sub": "bad/name"}, {"sub": None}, {"caller": "origin"}, {"caller": None}, {"target_fields": []},
                       {"target_fields": ["poll_home", "poll_home"]}, {"ref_claim": "other"},
                       {"audience_claim": "ref"}, {"extra": True}):
            broken = copy.deepcopy(raw)
            broken["domain"]["tokens"]["tally"]["unit"].update(change)
            raises(ValueError, lambda: SubsystemSpec.from_dict(broken))
        for key in ("ref_claim", "audience_claim", "target_fields"):
            broken = copy.deepcopy(raw)
            del broken["domain"]["tokens"]["tally"]["unit"][key]
            raises(ValueError, lambda: SubsystemSpec.from_dict(broken))
        for key in ("unit", "grant"):
            broken = copy.deepcopy(raw)
            del broken["domain"]["tokens"]["tally"][key]
            raises(ValueError, lambda: SubsystemSpec.from_dict(broken))
        broken = copy.deepcopy(raw)
        broken["domain"]["tokens"]["tally"]["placement"] = raw_spec(sub)["domain"]["tokens"]["tally"]["placement"]
        assert set(SubsystemSpec.from_dict(broken).domain.tokens["tally"]) >= {"placement", "unit"}
        broken = copy.deepcopy(raw)
        del broken["domain"]["ref"]
        raises(ValueError, lambda: SubsystemSpec.from_dict(broken))
        for grant in ([], ["bad role"], ["worker", "worker"], "worker"):
            broken = copy.deepcopy(raw)
            broken["domain"]["tokens"]["tally"]["grant"] = grant
            raises(ValueError, lambda: SubsystemSpec.from_dict(broken))


def test_unit_token_comes_from_own_accepted_snapshot_in_two_subsystems_without_assignment():
    with issuing() as e:
        for sub in ("testsub", "testsub2"):
            publish(e, sub=sub)
            got = claims(e, sub)
            assert got["sub"] == "south" and got["ref"] == "badge" and got["aud"] == ["north"]
            assert got["exp"] == e.wall() + 60
            assert not e.north.vars.list("domain/placement/")
        grants = tokenrequest.grants()
        assert grants["tally"] == ("testsub", ("testsubworker",))
        assert grants["tally2"] == ("testsub2", ("testsub2worker",))
        token = requested(e)["token"]
        for c in e.fed.clusters.values():
            assert all(token not in str(c.vars.get(k)[0]) for k in c.vars.list(""))
        assert all(token.encode() not in (e.north.objects.get(k) or b"") for k in e.north.objects.list("domain/"))


def test_local_unaccepted_or_other_members_unit_never_authorizes_issuance():
    with issuing() as e:
        publish(e, accepted=False)
        assert raises(Refused, lambda: requested(e)).status == 403
        publish(e, member="north")
        assert raises(Refused, lambda: requested(e)).status == 403
        publish(e)
        assert claims(e)["ref"] == "badge"
        assert raises(Refused, lambda: requested(e, sub="testsub2")).status == 403
        assert raises(Refused, lambda: requested(e, ref="absent")).status == 403
        assert raises(Refused, lambda: requested(e, role="testsub2worker")).status == 403
        assert raises(Refused, lambda: requested(e, role="domain")).status == 403
        # A report body outside the accepted pointer cannot grant another reference.
        snap = read("south", e.north.objects)
        orphan = snap.document()
        orphan["sent_at"] += 1
        orphan["objects"]["testsub/snapshot/orphan"] = {"ts": e.wall(), "counters": [{"name": "orphan"}]}
        e.north.objects.put(base("south") + "reports/" + str(snap.mark["rev"] + 1), publication_bytes(orphan))
        assert raises(Refused, lambda: requested(e, ref="orphan")).status == 403


def test_new_accepted_report_withdraws_a_unit_and_malformed_report_cannot_reuse_old_data():
    with issuing() as e:
        publish(e)
        assert claims(e)["ref"] == "badge"
        publish(e, refs=())
        assert raises(Refused, lambda: requested(e)).status == 403
        publish(e)
        assert claims(e)["ref"] == "badge"
        snap = read("south", e.north.objects)
        e.north.objects.put(base("south") + "reports/" + str(snap.mark["rev"]), b"{")
        assert raises(Refused, lambda: requested(e)).status == 403


def test_malformed_snapshot_or_nonunit_heartbeat_never_proves_a_unit():
    for shard in ({"ts": 1, "counters": "badge"}, {"ts": 1, "counters": ["badge"]},
                  {"ts": 1, "counters": [{"other": "badge"}]}, {"ts": 1, "units": [{"name": "badge"}]}):
        with issuing() as e:
            c = e.fed.clusters["south"]
            c.objects.put("testsub/snapshot/c4", json.dumps(shard).encode())
            c.objects.put("testsub/heartbeats/c4", json.dumps({"worker": "c4", "ts": e.wall(),
                "status": [{"id": "badge", "name": "badge"}]}).encode())
            e.wall.advance(1)
            report("south", c.vars, c.objects, e.north.objects, e.wall(), key=e.memberkeys["south"])
            assert raises(Refused, lambda: requested(e)).status == 403


def test_unit_token_tracks_authoritative_topology_and_current_holder_without_member_copy_override():
    with issuing() as e:
        publish(e)
        # via, centre, then current holder. The member's carried policy is irrelevant to issuance.
        from w2cplatform.trust.memberkey import MemberKey
        relay = MemberKey.new()
        roster = json.loads(e.north.vars.get("domain/members")[0]["doc"])
        roster["members"]["relay"] = {"key": relay.pub, "seal": relay.seal_pub}
        roster["rev"] += 1
        e.north.vars.put("domain/members", {"doc": json.dumps(roster)})
        e.north.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 99, "centre": "stranger"})})
        for topology, holder, expected in (({"rev": 1, "centre": "south", "via": {"south": "relay"}}, "north", "relay"),
                                           ({"rev": 2, "centre": "south"}, "north", "south"),
                                           ({"rev": 3, "centre": None}, "north", "north"),
                                           ({"rev": 4, "centre": None}, "south", "south")):
            e.north.vars.put("domain/holder", {"doc": json.dumps({"holder": holder, "term": topology["rev"]})})
            e.north.vars.put("domain/topology", {"doc": json.dumps(topology)})
            assert claims(e)["aud"] == [expected]
        e.north.vars.put("domain/topology", {"doc": json.dumps({"rev": 5, "centre": "stranger"})})
        assert raises(Refused, lambda: requested(e)).status == 403
        e.north.vars.put("domain/topology", {"doc": "{"})
        assert raises(Refused, lambda: requested(e)).status == 409


def test_unadmitted_or_revoked_member_cannot_request_for_its_previous_report():
    with issuing() as e:
        publish(e)
        roster = json.loads(e.north.vars.get("domain/members")[0]["doc"])
        del roster["members"]["south"]
        roster["rev"] += 1
        e.north.vars.put("domain/members", {"doc": json.dumps(roster)})
        assert raises(Refused, lambda: requested(e)).status == 404
    with issuing() as e:
        publish(e)
        e.north.vars.put("domain/keys", e.root.key_set(e.signer.tokens.keyset(), 2,
            revoked_members=[e.memberkeys["south"].pub]))
        assert raises(Refused, lambda: requested(e)).status == 403


def test_poll_home_uses_local_location_not_target_member_and_has_no_unknown_fallback():
    box = Box()
    box.vars.put("domain/holder", {"doc": json.dumps({"holder": "north", "term": 1})})
    box.vars.put("domain/member", {"cluster": "north"})
    box.vars.put("domain/topology", {"doc": json.dumps({"rev": 1, "centre": "south"})})
    box.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 99, "centre": "stranger"})})
    assert poll_home(box.vars, "leaf") == "south"
    box.vars.put("domain/member", {"cluster": "south"})
    assert poll_home(box.vars, "leaf") == "stranger"
    assert poll_home(box.vars, "leaf", authoritative=True) == "south"
    box.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 2, "via": {"leaf": "relay"}, "centre": "south"})})
    assert poll_home(box.vars, "leaf") == "relay"
    box.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 3})})
    assert poll_home(box.vars, "leaf") == "north"
    for broken in ("{", "[]", json.dumps({"holder": "north", "term": 0}), json.dumps({"holder": "", "term": 1}),
                   json.dumps({"holder": "north", "term": True})):
        box.vars.put("domain/holder", {"doc": broken})
        raises(ValueError, lambda: poll_home(box.vars, "leaf"))


def test_poll_home_refuses_malformed_or_unconfirmed_policy_before_choosing_another_route():
    box = Box()
    box.vars.put("domain/holder", {"doc": json.dumps({"holder": "north", "term": 1})})
    box.vars.put("domain/member", {"cluster": "south"})
    for doc in ("{", "[]", {"rev": True}, {"rev": 0, "centre": "south"}, {"rev": 1, "centre": []},
                {"rev": 1, "via": {"leaf": None}}, {"rev": 1, "via": {"leaf": ""}},
                {"rev": 1, "via": {"leaf": "relay", "relay": "next"}},
                {"rev": 1, "star": [1]}, {"rev": 1, "star": ["south", "south"], "centre": "north"},
                {"rev": 1, "via": {"leaf": "north"}}, {"rev": 1, "centre": ""}):
        box.vars.put("domain/member-topology", {"doc": doc if isinstance(doc, str) else json.dumps(doc)})
        raises(ValueError, lambda: poll_home(box.vars, "leaf"))
    box.vars.put("domain/member-topology", {"doc": "{}"})
    assert poll_home(box.vars, "leaf") == "north"
    box.vars.put("domain/member", {})
    raises(ValueError, lambda: poll_home(box.vars, "leaf"))


def test_unit_binding_reads_only_home_policy_and_does_not_grant_domain_writes():
    from w2cplatform.cluster.rights import roles
    from w2cplatform.rights import allowed
    for sub in ("testsub", "testsub2"):
        scoped = SubsystemSpec.from_dict(unit_raw(sub))
        rule = roles([scoped], "test")[sub + "worker"]
        for key in ("domain/holder", "domain/member-topology", "domain/topology"):
            assert allowed(rule["read"], key), key
            assert not allowed(rule["write"], key), key
        assert not allowed(rule["read"], "domain/signer")
        unscoped = unit_raw(sub)
        del unscoped["domain"]["tokens"]["tally"]["unit"]
        del unscoped["domain"]["tokens"]["tally"]["grant"]
        rule = roles([SubsystemSpec.from_dict(unscoped)], "test")[sub + "worker"]
        for key in ("domain/member-topology", "domain/topology"):
            assert not allowed(rule["read"], key), key


def test_unit_binding_accepts_cross_subsystem_poll_home_and_placement_fallback():
    for sub in ('testsub','testsub2'):
        raw = unit_raw(sub)
        token = raw['domain']['tokens']['tally']
        token['unit'].update(sub='testsub2' if sub=='testsub' else 'testsub',caller='poll_home',target_fields=['centre'])
        token['placement'] = raw_spec(sub)['domain']['tokens']['tally']['placement']
        del raw['domain']['ref']  # the referenced subsystem, not this token owner, provides domain.ref
        rule = SubsystemSpec.from_dict(raw).domain.tokens['tally']
        assert rule['unit']['caller']=='poll_home' and rule['unit']['target_fields']==('centre',)
        assert set(rule) >= {'placement','unit'}


def test_unit_poll_home_comes_from_another_subsystems_accepted_report_and_cannot_override_assignment():
    from w2cplatform.domain import placement
    with issuing() as e:
        rule = catalog.spec('testsub2').domain.tokens['tally2']
        rule['unit'].update(sub='testsub',caller='poll_home',target_fields=('centre',))
        rule['placement'] = {'sub':'testsub2','caller':'cluster','ref_claim':'ref',
                             'target_fields':('centre',),'audience_claim':'aud'}
        e.north.vars.put('domain/topology',{'doc':json.dumps({'rev':1,'centre':'north','star':[],'via':{}})})
        for name in e.fed.clusters:
            publish(e,member=name,refs=('badge',) if name=='south' else ())
        got = claims(e,'testsub2',member='north')
        assert got['sub']=='north' and got['aud']==['north'] and got['ref']=='badge'
        assert raises(Refused,lambda:requested(e,'testsub2',member='south')).status==403
        # A real placement takes priority even when a unit-based grant would pass.
        placement.assign(e.north.vars,'testsub2','badge',{'cluster':'south','origin':'south'},e.wall)
        assert raises(Refused,lambda:requested(e,'testsub2',member='north')).status==403
        assert claims(e,'testsub2',member='south')['aud']==['north']
        e.north.vars.put('domain/placement/testsub2/badge',{'rev':'bad'})
        assert raises(Refused,lambda:requested(e,'testsub2',member='north')).status==403


def test_unit_poll_home_rejects_withdrawn_duplicate_and_unaccepted_report():
    with issuing() as e:
        rule=catalog.spec('testsub2').domain.tokens['tally2']
        rule['unit'].update(sub='testsub',caller='poll_home',target_fields=('centre',))
        e.north.vars.put('domain/topology',{'doc':json.dumps({'rev':1,'centre':'north','star':[],'via':{}})})
        for name in e.fed.clusters:
            publish(e,member=name,refs=())
        publish(e,accepted=False)
        assert raises(Refused,lambda:requested(e,'testsub2',member='north')).status==403
        publish(e)
        assert claims(e,'testsub2',member='north')['aud']==['north']
        publish(e,member='north')
        assert raises(Refused,lambda:requested(e,'testsub2',member='north')).status==403
        publish(e,member='north',refs=());publish(e,refs=())
        assert raises(Refused,lambda:requested(e,'testsub2',member='north')).status==403
