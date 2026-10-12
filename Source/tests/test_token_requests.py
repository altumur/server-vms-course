"""ADR-0074 scoped tokens and ephemeral transport, testsub/testsub2 only."""
import copy
import json
import threading
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import yaml

from w2cplatform import catalog
from w2cplatform.spec import SubsystemSpec
from w2cplatform.console import Bounds, ConsoleServer, UnixConsoleServer
from w2cplatform.configstorevars import unix_transport
from w2cplatform.domain import declared, placement, tokenrequest
from w2cplatform.domain.agent import DomainAgent
from w2cplatform.domain.carry import CarryClient, HolderDoor, Refused, publication_bytes
from w2cplatform.domain.relay import RelayDoor, door_handler
from w2cplatform.trust.memberkey import NotMine, sign_request
from w2cplatform.trust.tokens import DeclaredIssuer, verify
from tests.test_book_runtime import site
from tests.test_book_names import raises


def raw_spec(sub="testsub"):
    raw = yaml.safe_load((Path(__file__).parent / "testdata" / f"{sub}.subsystem.yaml").read_text())
    raw["domain"]["tokens"] = {"tally": {"lifetime": 60, "claims": ["ref", "aud"],
        "grant": [f"{sub}worker"], "placement": {"sub": sub, "caller": "origin", "ref_claim": "ref",
            "target_fields": ["cluster", "copies"], "audience_claim": "aud"}}}
    return raw


@contextmanager
def issuing(two=False):
    with site(two=two) as e:
        specs = [SubsystemSpec.from_dict(raw_spec(s.name)) for s in e.specs]
        if two:
            specs[1].domain.tokens["tally2"] = specs[1].domain.tokens.pop("tally")
        with patch.object(catalog, "_loaded", {s.name: s for s in specs}), patch.object(catalog, "_derived", {}):
            e.door = HolderDoor(e.north.vars, e.north.objects, wall=e.wall,
                                token_issuer=DeclaredIssuer(e.signer.tokens, declared.token_kinds()))
            yield e


@contextmanager
def serving(server):
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        yield server
    finally:
        server.shutdown(); server.server_close(); t.join()


def client(e, member="south", door=None):
    return CarryClient(door or e.door, member, e.memberkeys[member], e.wall)


def signed(e, body, member="south", sub="testsub", kind="tally"):
    raw = publication_bytes(body)
    sig = sign_request(e.memberkeys[member], "POST", tokenrequest.route(member, sub, kind), raw, e.wall())
    return raw, sig


def test_token_spec_rejects_unknown_unsafe_and_partial_bindings():
    for sub in ("testsub", "testsub2"):
        raw = raw_spec(sub)
        assert SubsystemSpec.from_dict(raw).domain.tokens["tally"]["grant"] == (f"{sub}worker",)
        for change in (dict(grant=[]), dict(grant=["x", "x"]), dict(grant="worker"), dict(placement=None), dict(audience_prefix="prefix")):
            broken = copy.deepcopy(raw); broken["domain"]["tokens"]["tally"].update(change)
            raises(ValueError, lambda: SubsystemSpec.from_dict(broken))
        for change in ({"caller": "unit"}, {"target_fields": []}, {"target_fields": ["origin", "origin"]},
                       {"target_fields": ["when"]}, {"ref_claim": "undeclared"}, {"audience_claim": "ref"}, {"extra": "unsafe"}):
            broken = copy.deepcopy(raw); broken["domain"]["tokens"]["tally"]["placement"].update(change)
            raises(ValueError, lambda: SubsystemSpec.from_dict(broken))
        for key in ("grant", "placement"):
            broken = copy.deepcopy(raw); del broken["domain"]["tokens"]["tally"][key]
            raises(ValueError, lambda: SubsystemSpec.from_dict(broken))


def test_scope_comes_from_assignment_in_two_subsystems_and_changes_with_reassignment():
    with issuing(two=True) as e:
        for sub, kind in (("testsub", "tally"), ("testsub2", "tally2")):
            placement.assign(e.north.vars, sub, "badge", {"cluster": "north", "origin": "south", "copies": ["south"]}, e.wall)
            got = client(e).request_token(sub, kind, "badge", f"{sub}worker")
            claims = verify(got["token"], e.signer.tokens.keyset(), now=e.wall(), kind=kind)
            assert claims["sub"] == claims["ref"] == "badge" and claims["aud"] == ["north", "south"]
            assert got["exp"] == claims["exp"] == e.wall() + 60
            placement.assign(e.north.vars, sub, "badge", {"cluster": "south", "origin": "north"}, e.wall)
            assert raises(Refused, lambda: client(e).request_token(sub, kind, "badge", f"{sub}worker")).status == 403
            new = client(e, "north").request_token(sub, kind, "badge", f"{sub}worker")
            assert verify(new["token"], e.signer.tokens.keyset(), now=e.wall())["aud"] == ["south"]


def test_no_grant_foreign_role_ref_member_or_broken_assignment_cannot_issue():
    with issuing() as e:
        placement.assign(e.north.vars, "testsub", "badge", {"cluster": "north", "origin": "south"}, e.wall)
        for member, role, ref in (("south", "domainagent", "badge"), ("north", "testsubworker", "badge"), ("south", "testsubworker", "absent")):
            assert raises(Refused, lambda: client(e, member).request_token("testsub", "tally", ref, role)).status == 403
        rule = catalog.spec("testsub").domain.tokens["tally"]
        grant = rule.pop("grant")
        assert raises(Refused, lambda: client(e).request_token("testsub", "tally", "badge", "testsubworker")).status == 403
        rule["grant"] = grant
        key = placement.path("testsub", "badge"); row = e.north.vars.get(key)[0]
        for broken in ({**row, "copies": '["stranger"]'}, {**row, "unit": "invented"}):
            e.north.vars.put(key, broken)
            assert raises(Refused, lambda: client(e).request_token("testsub", "tally", "badge", "testsubworker")).status == 403
        e.north.vars.put(key, row)
        e.north.vars.put("domain/members", {"doc": json.dumps({"rev": 2, "members": {"north": {"key": e.memberkeys["north"].pub}}})})
        assert raises(Refused, lambda: client(e).request_token("testsub", "tally", "badge", "testsubworker")).status == 404


def test_signature_covers_bytes_route_time_and_reply_is_bound_to_original_member_and_request():
    with issuing() as e:
        placement.assign(e.north.vars, "testsub", "badge", {"cluster": "north", "origin": "south"}, e.wall)
        raw, sig = signed(e, {"request_id": "once", "role": "testsubworker", "ref": "badge"})
        assert raises(Refused, lambda: e.door.token("south", "testsub", "tally", raw + b" ", sig)).status == 401
        assert raises(Refused, lambda: e.door.token("south", "testsub2", "tally", raw, sig)).status == 401
        got = e.door.token("south", "testsub", "tally", raw, sig)
        ctx = tokenrequest.context(tokenrequest.route("south", "testsub", "tally"), "once", got["exp"])
        token = e.memberkeys["south"].open("token", got["token"], ctx)
        raises(NotMine, lambda: e.memberkeys["north"].open("token", got["token"], ctx))
        raises(NotMine, lambda: e.memberkeys["south"].open("token", got["token"], ctx + "other"))
        assert token not in json.dumps(got)
        for c in e.fed.clusters.values():
            assert all(token not in json.dumps(c.vars.get(p)[0]) for p in c.vars.list("domain/"))
        e.wall.advance(301)
        assert raises(Refused, lambda: e.door.token("south", "testsub", "tally", raw, sig)).status == 401


def test_real_holder_and_relay_http_preserve_the_member_signature_and_encrypted_reply():
    with issuing() as e:
        placement.assign(e.north.vars, "testsub", "badge", {"cluster": "north", "origin": "south"}, e.wall)
        e.holder.carry_door = e.door
        with serving(ConsoleServer(("127.0.0.1", 0), e.holder.handler())) as server:
            road = client(e, "north", f"http://127.0.0.1:{server.server_port}")
            relay_agent = SimpleNamespace(domain_vars=road, now=e.wall, relayed={"south": {"key": e.memberkeys["south"].pub}})
            relay = RelayDoor(relay_agent)
            with serving(ConsoleServer(("127.0.0.1", 0), door_handler(relay))) as hop:
                got = client(e, door=f"http://127.0.0.1:{hop.server_port}").request_token("testsub", "tally", "badge", "testsubworker")
                assert verify(got["token"], e.signer.tokens.keyset(), now=e.wall())["aud"] == ["north"]
                raw, sig = signed(e, {"request_id": "relay", "role": "testsubworker", "ref": "badge"})
                sealed = relay.token("south", "testsub", "tally", raw, sig)
                ctx = tokenrequest.context(tokenrequest.route("south", "testsub", "tally"), "relay", sealed["exp"])
                raises(NotMine, lambda: e.memberkeys["north"].open("token", sealed["token"], ctx))
                assert raises(Refused, lambda: relay.token("south", "testsub", "tally", raw + b" ", sig)).status == 401


def test_local_socket_role_is_fixed_and_failed_request_leaves_no_cached_reply():
    with issuing() as e, tempfile.TemporaryDirectory(prefix="token-role-") as temp:
        placement.assign(e.north.vars, "testsub", "badge", {"cluster": "north", "origin": "south"}, e.wall)
        agent = DomainAgent("south", client(e), e.fed.clusters["south"].vars, now=e.wall, key=e.memberkeys["south"])
        path = str(Path(temp) / "role.sock")
        with serving(UnixConsoleServer(path, tokenrequest.local_handler(agent, "testsub", "testsubworker"), Bounds())):
            caller = tokenrequest.WorkerTokenDoor(path)
            first = caller.request("tally", "badge")
            assert verify(first["token"], e.signer.tokens.keyset(), now=e.wall())["ref"] == "badge"
            code, _ = unix_transport(path)("POST", "/tokens/tally", b'{"ref":"badge","role":"domainagent"}', {}, 1)
            assert code == 400
            old = agent.domain_vars
            agent.domain_vars = SimpleNamespace(request_token=lambda *a: (_ for _ in ()).throw(TimeoutError()))
            assert raises(Refused, lambda: caller.request("tally", "badge")).status == 503
            agent.domain_vars = old
            second = caller.request("tally", "badge")
            assert second["request_id"] != first["request_id"] and "token" not in agent.__dict__



def test_remote_body_cannot_supply_target_claims_or_replay_reply_to_another_request():
    with issuing() as e:
        placement.assign(e.north.vars, "testsub", "badge", {"cluster": "north", "origin": "south"}, e.wall)
        good = {"request_id": "once", "role": "testsubworker", "ref": "badge"}
        for extra in ({"target": "north"}, {"claims": {"aud": ["stranger"]}}, {"sub": "somebody"}):
            raw, sig = signed(e, {**good, **extra})
            assert raises(Refused, lambda: e.door.token("south", "testsub", "tally", raw, sig)).status == 400
        real = e.door.token
        raw, sig = signed(e, good)
        kept = real("south", "testsub", "tally", raw, sig)
        e.door.token = lambda *a: kept
        assert raises(Refused, lambda: client(e).request_token("testsub", "tally", "badge", "testsubworker")).status == 502
        e.door.token = lambda *a: {**kept, "request_id": json.loads(a[3])["request_id"]}
        # Even with a matching outer id, ciphertext belongs to the first request's context.
        assert raises(Refused, lambda: client(e).request_token("testsub", "tally", "badge", "testsubworker")).status == 502


def test_local_handler_refuses_network_connections_even_with_an_allowed_role():
    with issuing() as e:
        with serving(ConsoleServer(("127.0.0.1", 0), tokenrequest.local_handler(None, "testsub", "testsubworker"))) as srv:
            import urllib.request, urllib.error
            req = urllib.request.Request(f"http://127.0.0.1:{srv.server_port}/tokens/tally", data=b'{"ref":"badge"}')
            assert raises(urllib.error.HTTPError, lambda: urllib.request.urlopen(req)).code == 403



def test_reply_expiry_is_authenticated_with_the_ciphertext():
    with issuing() as e:
        placement.assign(e.north.vars, "testsub", "badge", {"cluster": "north", "origin": "south"}, e.wall)
        actual = e.door.token
        def changed(*args):
            result = actual(*args)
            return {**result, "exp": result["exp"] + 60}
        e.door.token = changed
        assert raises(Refused, lambda: client(e).request_token("testsub", "tally", "badge", "testsubworker")).status == 502


def test_local_client_timeout_drops_late_reply_and_retry_asks_again():
    with issuing() as e, tempfile.TemporaryDirectory(prefix="token-timeout-") as temp:
        placement.assign(e.north.vars, "testsub", "badge", {"cluster": "north", "origin": "south"}, e.wall)
        agent = DomainAgent("south", client(e), e.fed.clusters["south"].vars, now=e.wall, key=e.memberkeys["south"])
        actual = agent.request_token
        entered, release, done = threading.Event(), threading.Event(), threading.Event()
        replies = []
        def slow(*args):
            entered.set()
            assert release.wait(2)
            result = actual(*args)
            replies.append(result["request_id"])
            done.set()
            return result
        agent.request_token = slow
        path = str(Path(temp) / "role.sock")
        with serving(UnixConsoleServer(path, tokenrequest.local_handler(agent, "testsub", "testsubworker"), Bounds())):
            short = tokenrequest.WorkerTokenDoor(path, timeout=0.03)
            try:
                raises(TimeoutError, lambda: short.request("tally", "badge"))
                assert entered.wait(1)
            finally:
                release.set()
            assert done.wait(2)
            agent.request_token = actual
            retried = tokenrequest.WorkerTokenDoor(path, timeout=1).request("tally", "badge")
            assert retried["request_id"] not in replies
            assert "token" not in agent.__dict__


def test_revoked_member_and_frozen_holder_do_not_issue_tokens():
    with issuing() as e:
        placement.assign(e.north.vars, "testsub", "badge", {"cluster": "north", "origin": "south"}, e.wall)
        e.north.vars.put("domain/keys", e.root.key_set(e.signer.tokens.keyset(), 2,
            revoked_members=[e.memberkeys["south"].pub]))
        assert raises(Refused, lambda: client(e).request_token("testsub", "tally", "badge", "testsubworker")).status == 403
        e.north.vars.put("domain/keys", e.root.key_set(e.signer.tokens.keyset(), 3))
        from w2cplatform.domain.term import Frozen
        e.holder.term = SimpleNamespace(guard=lambda: (_ for _ in ()).throw(Frozen("moving")), frozen_for="south")
        e.holder.carry_door = e.door
        with serving(ConsoleServer(("127.0.0.1", 0), e.holder.handler())) as srv:
            remote = client(e, door=f"http://127.0.0.1:{srv.server_port}")
            assert raises(Refused, lambda: remote.request_token("testsub", "tally", "badge", "testsubworker")).status == 503
