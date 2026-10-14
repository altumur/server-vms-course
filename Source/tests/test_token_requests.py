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
        centre = copy.deepcopy(raw)
        centre["domain"]["tokens"]["tally"]["placement"]["target_fields"] = ["centre"]
        assert SubsystemSpec.from_dict(centre).domain.tokens["tally"]["placement"]["target_fields"] == ("centre",)
        centre["domain"]["tokens"]["tally"]["placement"]["target_fields"] = ["star_centre"]
        assert SubsystemSpec.from_dict(centre).domain.tokens["tally"]["placement"]["target_fields"] == ("star_centre",)
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
            assert claims["sub"] == "south" and claims["ref"] == "badge" and claims["aud"] == ["north", "south"]
            assert got["exp"] == claims["exp"] == e.wall() + 60
            placement.assign(e.north.vars, sub, "badge", {"cluster": "south", "origin": "north"}, e.wall)
            assert raises(Refused, lambda: client(e).request_token(sub, kind, "badge", f"{sub}worker")).status == 403
            new = client(e, "north").request_token(sub, kind, "badge", f"{sub}worker")
            assert verify(new["token"], e.signer.tokens.keyset(), now=e.wall())["aud"] == ["south"]




def test_star_centre_scope_depends_on_primary_not_a_copy_in_two_subsystems():
    with issuing(two=True) as e:
        for sub, kind in (("testsub", "tally"), ("testsub2", "tally2")):
            rule = catalog.spec(sub).domain.tokens[kind]
            rule["placement"] = {**rule["placement"], "target_fields": ("cluster", "copies", "star_centre")}
            e.north.vars.put("domain/topology", {"doc": json.dumps({"rev": 1, "centre": "north", "star": ["south"], "via": {}})})
            placement.assign(e.north.vars, sub, "badge", {"cluster": "south", "origin": "south", "copies": []}, e.wall)
            got = client(e).request_token(sub, kind, "badge", f"{sub}worker")
            assert verify(got["token"], e.signer.tokens.keyset(), now=e.wall())["aud"] == ["north", "south"]
            placement.assign(e.north.vars, sub, "badge", {"cluster": "north", "origin": "south", "copies": ["south"]}, e.wall)
            e.north.vars.put("domain/topology", {"doc": json.dumps({"rev": 2, "centre": "elsewhere", "star": ["south"], "via": {}})})
            got = client(e).request_token(sub, kind, "badge", f"{sub}worker")
            assert verify(got["token"], e.signer.tokens.keyset(), now=e.wall())["aud"] == ["north", "south"]
            placement.assign(e.north.vars, sub, "badge", {"cluster": "south", "origin": "south", "copies": []}, e.wall)
            e.north.vars.put("domain/topology", {"doc": json.dumps({"rev": 3, "centre": None, "star": ["south"], "via": {}})})
            assert raises(Refused, lambda: client(e).request_token(sub, kind, "badge", f"{sub}worker")).status == 409


def test_declared_centre_target_comes_only_from_confirmed_holder_topology():
    with issuing(two=True) as e:
        for sub, kind in (("testsub", "tally"), ("testsub2", "tally2")):
            rule = catalog.spec(sub).domain.tokens[kind]
            rule["placement"] = {**rule["placement"], "caller": "cluster", "target_fields": ("centre",)}
            placement.assign(e.north.vars, sub, "badge", {"cluster": "south", "origin": "north"}, e.wall)
            e.north.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 9, "centre": "south"})})
            for topology in (None, [], {"rev": 0, "centre": "north"}, {"rev": True, "centre": "north"},
                             {"rev": "1", "centre": "north"}, {"rev": 1, "centre": "north", "star": ["north"]}):
                e.north.vars.put("domain/topology", {"doc": json.dumps(topology)})
                assert raises(Refused, lambda: client(e).request_token(sub, kind, "badge", f"{sub}worker")).status == 409
            e.north.vars.put("domain/topology", {"doc": json.dumps({"rev": 1, "centre": "north", "star": [], "via": {}})})
            reply = client(e).request_token(sub, kind, "badge", f"{sub}worker")
            assert verify(reply["token"], e.signer.tokens.keyset(), now=e.wall(), kind=kind)["aud"] == ["north"]
            assert raises(Refused, lambda: client(e, "north").request_token(sub, kind, "badge", f"{sub}worker")).status == 403
            e.north.vars.put("domain/topology", {"doc": json.dumps({"rev": 2, "centre": "south", "star": [], "via": {}})})
            reply = client(e).request_token(sub, kind, "badge", f"{sub}worker")
            assert verify(reply["token"], e.signer.tokens.keyset(), now=e.wall(), kind=kind)["aud"] == ["south"]
            e.north.vars.put("domain/topology", {"doc": json.dumps({"rev": 2, "centre": "not-admitted"})})
            assert raises(Refused, lambda: client(e).request_token(sub, kind, "badge", f"{sub}worker")).status == 403


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
        with serving(UnixConsoleServer(path, tokenrequest.local_handler(agent, "testsubworker"), Bounds())):
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
        with serving(ConsoleServer(("127.0.0.1", 0), tokenrequest.local_handler(None, "testsubworker"))) as srv:
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
        with serving(UnixConsoleServer(path, tokenrequest.local_handler(agent, "testsubworker"), Bounds())):
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


def test_one_role_socket_resolves_kinds_of_two_subsystems_and_refuses_foreign_role():
    with issuing(two=True) as e, tempfile.TemporaryDirectory(prefix="token-kind-") as temp:
        specs = list(catalog._loaded.values())
        specs[1].domain.tokens["tally2"]["grant"] = ("testsubworker",)
        placement.assign(e.north.vars, "testsub", "badge", {"cluster": "north", "origin": "south"}, e.wall)
        placement.assign(e.north.vars, "testsub2", "badge2", {"cluster": "north", "origin": "south"}, e.wall)
        agent = DomainAgent("south", client(e), e.fed.clusters["south"].vars, now=e.wall, key=e.memberkeys["south"])
        path = str(Path(temp) / "role.sock")
        with serving(UnixConsoleServer(path, tokenrequest.local_handler(agent, "testsubworker"), Bounds())):
            caller = tokenrequest.WorkerTokenDoor(path)
            assert verify(caller.request("tally", "badge")["token"], e.signer.tokens.keyset(), now=e.wall())["ref"] == "badge"
            assert verify(caller.request("tally2", "badge2")["token"], e.signer.tokens.keyset(), now=e.wall())["ref"] == "badge2"
            assert raises(Refused, lambda: caller.request("unknown", "badge")).status == 403
        with serving(UnixConsoleServer(path, tokenrequest.local_handler(agent, "strangerworker"), Bounds())):
            assert raises(Refused, lambda: tokenrequest.WorkerTokenDoor(path).request("tally", "badge")).status == 403
        specs[1].domain.tokens["tally"] = specs[1].domain.tokens["tally2"]
        raises(ValueError, tokenrequest.grants)


def test_role_socket_startup_is_disabled_by_default_and_refuses_unsafe_real_directories():
    import os
    with issuing() as e, tempfile.TemporaryDirectory(prefix="token-mode-") as temp:
        assert tokenrequest.open_role_doors(None, {}) == []
        assert tokenrequest.WorkerTokenDoor.from_env("testsubworker", {}) is None
        assert tokenrequest.WorkerTokenDoor.from_env("testsubworker", {"TOKEN_REQUESTS_DIR": temp}).call is not None
        role = Path(temp) / "testsubworker"
        role.mkdir(); os.chown(role, -1, os.getegid()); role.chmod(0o2770)
        gid = role.stat().st_gid
        assert tokenrequest.open_role_doors(None, {"TOKEN_REQUESTS_DIR": temp, "SPEC_DIR": "testsub"}) == []
        raises(PermissionError, lambda: tokenrequest._protected_directory(str(role), gid, 0o2770))
        alias = Path(temp) / "alias"; alias.symlink_to(role)
        raises(PermissionError, lambda: tokenrequest._protected_directory(str(alias), gid, 0o2770))
        actual = os.lstat
        def root_owned(path):
            info = actual(path)
            vals = list(info); vals[4] = 0
            return os.stat_result(vals)
        # Deployment owner injected; modes and filesystem objects remain real.
        with patch("os.lstat", side_effect=root_owned):
            tokenrequest._protected_directory(str(role), gid, 0o2770)
            role.chmod(0o2775)
            raises(PermissionError, lambda: tokenrequest._protected_directory(str(role), gid, 0o2770))
            role.chmod(0o2770)
            raises(PermissionError, lambda: tokenrequest._protected_directory(str(role), gid+1, 0o2770))


def test_role_socket_bootstrap_and_installation_follow_loaded_grants():
    import os
    import stat
    from types import SimpleNamespace
    with issuing(two=True) as e, tempfile.TemporaryDirectory(prefix="token-bootstrap-") as temp:
        specs = list(catalog._loaded.values())
        specs[1].domain.tokens["tally2"]["grant"] = ("testsubworker",)
        files, groups = tokenrequest.installation("/run/w2c-token-requests", "example")
        assert files.count("2770") == 1
        assert "example-testsubworker" in files and "example-testsubworker" in groups
        raises(ValueError, lambda: tokenrequest.installation("/run/unsafe path", "example"))
        for s in specs:
            for rule in s.domain.tokens.values():
                rule.pop("grant", None)
        assert tokenrequest.installation("/run/w2c-token-requests", "example")[1] == "[Service]\n"
        specs[0].domain.tokens["tally"]["grant"] = ("testsubworker",)
        placement.assign(e.north.vars, "testsub", "badge", {"cluster": "north", "origin": "south"}, e.wall)
        agent = DomainAgent("south", client(e), e.fed.clusters["south"].vars, now=e.wall, key=e.memberkeys["south"])
        directory = Path(temp); directory.chmod(0o755)
        role = directory / "testsubworker"
        role.mkdir(); os.chown(role, -1, os.getegid()); role.chmod(0o2770)
        actual_lstat, actual_stat = os.lstat, os.stat
        def deployment_info(info, path):
            vals = list(info)
            if stat.S_ISDIR(info.st_mode):
                vals[4] = 0
                # Simulate privileged provisioning only; socket uid/gid/mode are real.
                if str(path) == str(directory): vals[5] = 0
                else: vals[0] &= ~0o022 if str(path) != str(role) else -1
            return os.stat_result(vals)
        def lstat(path): return deployment_info(actual_lstat(path), path)
        def stored(path): return deployment_info(actual_stat(path), path)
        with patch("os.lstat", side_effect=lstat), patch("os.stat", side_effect=stored), \
                patch("grp.getgrnam", return_value=SimpleNamespace(gr_gid=os.getegid())):
            servers = tokenrequest.open_role_doors(agent, {"TOKEN_REQUESTS_DIR": temp, "SPEC_DIR": "example"})
            assert len(servers) == 1
            try:
                door = tokenrequest.WorkerTokenDoor.from_env("testsubworker", {"TOKEN_REQUESTS_DIR": temp})
                assert verify(door.request("tally", "badge")["token"], e.signer.tokens.keyset(), now=e.wall())["ref"] == "badge"
                socket_info = actual_lstat(role / "tokens.sock")
                assert stat.S_IMODE(socket_info.st_mode) == 0o660 and socket_info.st_gid == os.getegid()
            finally:
                for server in servers:
                    server.shutdown(); server.server_close()
        assert not (role / "tokens.sock").exists()


def test_role_groups_match_controller_and_worker_configstore_groups():
    with issuing() as e:
        loaded = catalog._loaded["testsub"].domain.tokens["tally"]
        loaded["grant"] = ("testsubcontroller", "testsubworker")
        files, groups = tokenrequest.installation("/run/w2c-token-requests", "tenant")
        assert "root w2c-testsubcontroller -" in files
        assert "root tenant-testsubworker -" in files
        assert "w2c-testsubcontroller" in groups and "tenant-testsubworker" in groups
        loaded["grant"] = ("unknownworker",)
        raises(KeyError, lambda: tokenrequest.installation("/run/w2c-token-requests", "tenant"))


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


def test_embedded_agent_uses_authenticated_relay_link_for_role_requests():
    from w2cplatform.domain.relay import RelayLink
    with issuing() as e:
        placement.assign(e.north.vars, "testsub", "badge", {"cluster": "north", "origin": "south"}, e.wall)
        relay_agent = SimpleNamespace(domain_vars=client(e, "north"), now=e.wall,
            relayed={"south": {"key": e.memberkeys["south"].pub}})
        relay = RelayDoor(relay_agent)
        agent = DomainAgent("south", RelayLink(relay), e.fed.clusters["south"].vars,
                            now=e.wall, key=e.memberkeys["south"])
        got = agent.request_token("testsub", "tally", "badge", "testsubworker", request_id="embedded")
        assert got["request_id"] == "embedded"
        assert verify(got["token"], e.signer.tokens.keyset(), now=e.wall())["aud"] == ["north"]
        # The relay still verifies the original member signature, not its own identity.
        relay_agent.relayed["south"]["key"] = e.memberkeys["north"].pub
        assert raises(Refused, lambda: agent.request_token("testsub", "tally", "badge", "testsubworker")).status == 401
