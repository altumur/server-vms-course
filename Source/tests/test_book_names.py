"""ADR-0074 collected names and last-moment grant checks, testsub/testsub2 only."""

from tests.frozen_data import frozen_testdata
import contextlib
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import yaml

from w2cplatform import catalog
from w2cplatform.domain import booknames, declared
from w2cplatform.domain.bookmerge import collect
from w2cplatform.spec import SubsystemSpec
from w2cplatform.variables import FileVariables


def spec(sub="testsub", *, show=()):
    raw = yaml.safe_load((frozen_testdata() / f"{sub}.subsystem.yaml").read_text())
    raw["domain"]["books"] = {"counts": {"from": f"{sub}/counts/", "key": "name", "pick": "unique", "to": "to"}}
    if show:
        raw["domain"]["books"]["counts"]["show"] = list(show)
    raw["domain"]["names"] = {"counts/": {"exclusive_with": "domain/users", "grant": "view"}}
    return SubsystemSpec.from_dict(raw)


@contextlib.contextmanager
def site(sub="testsub"):
    s = spec(sub)
    with patch.object(catalog, "_loaded", {sub: s}), patch.object(catalog, "_derived", {}):
        with tempfile.TemporaryDirectory(prefix="book-names-") as root:
            yield s, FileVariables(root, volatile=True)


def report(s, name="badge", to="b"):
    return {f"{s.name}/counts/w1": {"i": json.dumps({"name": name, "to": to, "n": 3})}}


def result(s, reports=None, members=("a", "b"), lost=()):
    return collect(s.domain.merged["counts"], reports if reports is not None else {"a": report(s), "b": {}},
                   members, lost=lost)


def raises(cls, fn):
    try:
        fn()
    except cls as e:
        return e
    raise AssertionError(f"expected {cls.__name__}")


def test_names_accept_collected_books_without_kept_and_refuse_carried_books():
    for sub in ("testsub", "testsub2"):
        assert "counts/" in spec(sub).domain.names and "counts/" not in spec(sub).domain.kept
        raw = yaml.safe_load((frozen_testdata() / f"{sub}.subsystem.yaml").read_text())
        raw["domain"]["books"] = {"counts": {}}
        raw["domain"]["names"] = {"counts/": {"exclusive_with": "domain/users", "grant": "view"}}
        raises(ValueError, lambda: SubsystemSpec.from_dict(raw))


def test_index_keeps_conflicts_and_accounts_without_recipients_but_no_values():
    s = spec()
    got = result(s, {"a": report(s, to=[]), "b": report(s, to="a")})
    assert all(set(row) == {""} for row in got.rows.values())
    assert booknames.index(got) == {"": '{"missing":[]}', "badge": '{"members":["a","b"]}'}
    assert "to" not in json.dumps(booknames.index(got)) and "value" not in json.dumps(booknames.index(got))
    unknown = result(s, {"a": report(s, to="outsider"), "b": {}})
    assert unknown.subjects == {"badge": ("a",)}
    assert unknown.rows["b"] == {"": '{"missing":[]}'}


def test_missing_retains_names_but_lost_removed_and_withdrawn_members_release_them():
    s = spec()
    old = booknames.index(result(s))
    missing = result(s, {"a": None, "b": {}})
    assert booknames.index(missing, old) == {"": '{"missing":["a"]}', "badge": '{"members":["a"]}'}
    for got in (result(s, {"a": None, "b": {}}, lost=["a"]), result(s, {"b": {}}, members=["b"]),
                result(s, {"a": {}, "b": {}})):
        assert booknames.index(got, old) == {"": '{"missing":[]}'}


def test_corrupt_index_is_unknown_and_fresh_collection_repairs_it_even_with_missing():
    s = spec()
    for bad in (None, {}, {"": "{}"}, {"": '{"missing":["a","a"]}'},
                {"": '{"missing":[]}', "badge": '{"members":[]}'},
                {"": '{"missing":[],"missing":[]}'}, {"": '{"missing":["\\ud800"]}'},
                {"": '{"missing":[]}', "badge": 'not JSON'}):
        raises(declared.NamesUnavailable, lambda: booknames.decode(bad, "index"))
        assert booknames.index(result(s, {"a": None, "b": {}}), bad) == {"": '{"missing":["a"]}'}
        assert booknames.index(result(s), bad)["badge"] == '{"members":["a"]}'


def test_corrupt_previous_index_does_not_stop_delivery_and_incomplete_creation_is_503():
    with site() as (s, v):
        v.put(booknames.path(s.name, "counts"), {"": "broken"})
        v.put("domain/grants/b", {"badge|view|": "200"})
        got = result(s, {"a": None, "b": report(s)})
        booknames.publish(v, s, "counts", got, 100)
        row = v.get("domain/testsub/counts/b")[0]
        assert json.loads(row["badge"])["entries"][0]["member"] == "b"
        assert json.loads(row[""])["missing"] == ["a"]
        assert booknames.decode(v.get(booknames.path(s.name, "counts"))[0], "index") == ({"badge": ("b",)}, ("a",))
        err = raises(declared.NamesUnavailable, lambda: declared.guarded(v).put("domain/users/new", {"kind": "local"}))
        assert err.missing == ("a",)


def test_guard_uses_subjects_not_recipient_names_and_checks_grant_ceiling():
    for sub in ("testsub", "testsub2"):
        with site(sub) as (s, v):
            v.put(booknames.path(sub, "counts"), booknames.index(result(s)))
            g = declared.guarded(v)
            raises(declared.NameTaken, lambda: g.put("domain/users/badge", {"kind": "local"}))
            g.put("domain/users/b", {"kind": "local"})  # recipient is not a subject
            raises(declared.GrantTooWide, lambda: g.put("domain/grants/b", {"badge|admin|": "200"}))
            g.put("domain/grants/b", {"badge|view|unit:testsub/c1": "200"})


def test_missing_blocks_creation_and_expansion_but_not_revoke_shorten_or_downgrade():
    with site() as (s, v):
        v.put(booknames.path(s.name, "counts"), {"": '{"missing":["a"]}'})
        v.put("domain/grants/b", {"person|admin|": "200", "badge|view|": "200"})
        g = declared.guarded(v)
        e = raises(declared.NamesUnavailable, lambda: g.put("domain/users/new", {"kind": "local"}))
        assert e.missing == ("a",) and "a" in str(e)
        raises(declared.NamesUnavailable, lambda: g.put("domain/grants/b", {"badge|view|": "201"}))
        g.put("domain/grants/b", {"person|view|": "150", "badge|view|": "100"})
        g.put("domain/grants/b", {"person|view|": "150"})
        g.put("domain/grants/b", {})
        g.put("domain/users/old", {"kind": "deleted"})


def test_subject_creation_checks_people_and_preexisting_grants_before_publication():
    with site() as (s, v):
        v.put(booknames.path(s.name, "counts"), {"": '{"missing":[]}'})
        v.put("domain/users/person", {"kind": "local"})
        raises(declared.NameTaken, lambda: booknames.available(v, s, "counts", "person"))
        v.put("domain/grants/b", {"wide|edit|": "200"})
        raises(declared.GrantTooWide, lambda: booknames.available(v, s, "counts", "wide"))
        booknames.available(v, s, "counts", "free")
        v.put(booknames.path(s.name, "counts"), {"": '{"missing":["a"]}'})
        raises(declared.NamesUnavailable, lambda: booknames.available(v, s, "counts", "free"))


def test_http_operations_distinguish_unknown_index_from_conflict_and_invalid_grant():
    from types import SimpleNamespace
    from w2cplatform.domain.console import Console
    from w2cplatform.domain.api import ApiError
    from w2cplatform.domain.identity import IdentityStore
    from w2cplatform.domain.signer_service import Holder
    with site() as (s, v):
        holder = Holder(v, None, None, ids=IdentityStore(None, v, None))
        body = {"name": "badge", "password": "synthetic-test-password", "roles": []}
        status, payload = holder._users("POST", "", "operator", body)
        assert status == 503 and "missing members" in payload["detail"]
        con = Console(None, SimpleNamespace(wall=lambda: 100), None, holder_vars=v)
        edit = {"lines": [{"subject": "badge", "cap": "view", "scope": "*", "until": 200}]}
        assert raises(ApiError, lambda: con.set_grants("b", edit, "operator")).status == 503
        v.put(booknames.path(s.name, "counts"), booknames.index(result(s)))
        assert holder._users("POST", "", "operator", body)[0] == 409
        edit["lines"][0]["cap"] = "admin"
        assert raises(ApiError, lambda: con.set_grants("b", edit, "operator")).status == 400


def test_publish_writes_results_before_index_and_does_not_bump_unchanged_rows():
    with site() as (s, v):
        v.put("domain/grants/b", {"badge|view|": "200"})
        writes, original = [], v.put
        def put(path, items, **kw):
            writes.append(path)
            return original(path, items, **kw)
        with patch.object(v, "put", put):
            booknames.publish(v, s, "counts", result(s), 100)
            assert writes[-1] == booknames.path(s.name, "counts")
            assert "badge" in v.get("domain/testsub/counts/b")[0]
            writes.clear()
            booknames.publish(v, s, "counts", result(s), 100)
            assert writes == []
            v.put("domain/grants/b", {})
            booknames.publish(v, s, "counts", result(s), 100)
            assert set(v.get("domain/testsub/counts/b")[0]) == {""}


def test_failed_output_write_does_not_publish_the_new_index():
    with site() as (s, v):
        booknames.publish(v, s, "counts", result(s), 100)
        before = v.get(booknames.path(s.name, "counts"))
        original = v.put
        def put(path, items, **kw):
            if path.endswith("/b"):
                raise OSError("unavailable")
            return original(path, items, **kw)
        changed = result(s, {"a": None, "b": {}})
        with patch.object(v, "put", put):
            raises(OSError, lambda: booknames.publish(v, s, "counts", changed, 100))
        assert v.get(booknames.path(s.name, "counts")) == before


def test_carry_rechecks_scoped_grants_expiry_revoke_and_recipient_without_recollection():
    from w2cplatform.domain.carry import answer
    with site() as (s, v):
        target = "domain/testsub/counts/b"
        row = result(s).rows["b"]
        v.put(target, row)
        for scope in ("", "unit:testsub/c1", "labels:floor1"):
            v.put("domain/grants/b", {f"badge|view|{scope}": "101"})
            assert "badge" in answer(v, None, "b", now=100)["rows"][target]
            assert "badge" not in answer(v, None, "b", now=101)["rows"][target]
        for grants in ({}, {"badge|admin|": "200"}, {"badge|view|": "nan"}, {"badge|view|bad": "200"}):
            v.put("domain/grants/b", grants)
            assert set(answer(v, None, "b", now=100)["rows"][target]) == {""}
        v.put("domain/grants/b", {"badge|view|": "200"})
        wrong = copy.deepcopy(row)
        doc = json.loads(wrong["badge"])
        doc["entries"][0]["value"]["to"] = "a"
        wrong["badge"] = json.dumps(doc)
        v.put(target, wrong)
        assert "badge" not in answer(v, None, "b", now=100)["rows"][target]


def test_index_writer_is_domain_only_and_collected_outputs_are_no_longer_subdomain_writes():
    from w2cplatform.domain.rights import roles
    from w2cplatform.rights import allowed
    s = spec()
    rs = roles(specs=[s])
    for role in ("domainconsole", "domainagent", "testsubdomain"):
        assert not allowed(rs[role]["write"], "domain/names/testsub/counts")
        assert allowed(rs[role]["read"], "domain/names/testsub/counts")
    assert allowed(rs["domain"]["write"], "domain/names/testsub/counts")
    assert not allowed(rs["testsubdomain"]["write"], "domain/testsub/counts/b")


def test_grant_filter_precedes_secret_opening_and_keeps_the_recipient_binding():
    from w2cplatform.domain.carry import answer, seal_row
    from w2cplatform.sealing import Sealer
    from w2cplatform.trust.memberkey import MemberKey, NotMine
    with site() as (s, v):
        holder_ring = Sealer({"test": bytes(range(32))}, "test")
        recipient, other = MemberKey.new(), MemberKey.new()
        target = "domain/testsub/counts/b"
        row = result(s).rows["b"]
        doc = json.loads(row["badge"])
        doc["entries"][0]["value"]["token_secret"] = "synthetic-test-secret"
        row["badge"] = json.dumps(doc)
        v.put(target, seal_row(holder_ring, row, target))
        # No grant: the holder need not even open the secret.
        assert set(answer(v, None, "b", seal_to=recipient.seal_pub, now=100)["rows"][target]) == {""}
        v.put("domain/grants/b", {"badge|view|": "200"})
        carried = answer(v, None, "b", seal_to=recipient.seal_pub, sealer=holder_ring, now=100)
        cipher = json.loads(carried["rows"][target]["badge"])["entries"][0]["value"]["token_secret"]
        ctx = "domain/testsub/counts#badge"
        assert recipient.open("token_secret", cipher, ctx) == "synthetic-test-secret"
        raises(NotMine, lambda: other.open("token_secret", cipher, ctx))


def test_actual_backup_and_move_preserve_last_known_names_for_missing_members():
    from tests.test_domain_platform import site as platform_site
    from w2cplatform.domain.agent import DomainAgent, DomainPublisher
    from w2cplatform.domain.term import DomainHolder, move_domain
    from w2cplatform.trust.signer import Signer
    fed, wall = platform_site()
    north, south = fed.clusters["north"], fed.clusters["south"]
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    s = spec()
    with patch.object(catalog, "_loaded", {s.name: s}), patch.object(catalog, "_derived", {}):
        names_path = booknames.path(s.name, "counts")
        names = {"": '{"missing":["north"]}', "badge": '{"members":["north"]}'}
        north.vars.put(names_path, names)
        holder = DomainHolder(fed, "north", signer, 1, wall, objects=north.objects)
        holder.claim()
        holder.backup(["south"], north.objects)
        assert DomainAgent("south", north.vars, south.vars, now=wall, domain_objects=north.objects,
                           cluster_objects=south.objects).sync()
        new, _ = move_domain(fed, "south", signer.backup(), "acme", lambda n: fed.clusters[n].objects, wall)
        assert new.term == 2 and south.vars.get(names_path)[0] == names
        raises(declared.NamesUnavailable,
               lambda: declared.guarded(south.vars).put("domain/users/new", {"kind": "local"}))
