"""Lesson 4 — who may call it: tokens verified offline; users never reach a
worker; the agent carries keys, revocations and the cluster's grants and
nothing else; grants are cluster-local with expiry; the revocation window
is stated then measured; break-glass is one account, audited."""
import json

from w2cplatform.cluster.variables import Forbidden
from w2cplatform.domain.agent import KEYS_PATH, DomainAgent, DomainPublisher, ClusterTrust
from w2cplatform.domain.grants import GRANT_LIFETIME, ClusterAuthoriser, ClusterGrants, Grant, revocation_window
from w2cplatform.domain.identity import TOKEN_LIFETIME, AuthError, BreakGlass, IdentityStore
from w2cplatform.trust.signer import Signer
from w2cplatform.trust.tokens import Expired, Revoked, RevocationList, UnknownKey, verify
from tests.domain.conftest import Clock, make_domain


def _domain(clk):
    fed, links = make_domain({"north": (), "south": ()}, "north")
    dc = fed.domain_holder
    signer = Signer("acme", dc.vars, now=clk)
    return fed, links, dc, signer


def test_login_ends_in_a_token_naming_the_subject_and_nothing_else():
    clk = Clock(1000.0)
    fed, _, dc, signer = _domain(clk)
    ids = IdentityStore(signer, dc.vars, dc.objects, now=clk)
    ids.create_local("alice", "correct horse", roles=["operator"])
    tok = ids.login("alice", "correct horse")
    payload = verify(tok, signer.tokens.keyset(), now=clk())
    assert payload["sub"] == "alice" and payload["exp"] == 1000.0 + TOKEN_LIFETIME
    assert "roles" not in payload and "grants" not in payload            # rights are the cluster's grants, not the token's
    try:
        ids.login("alice", "wrong"); raise AssertionError()
    except AuthError:
        pass
    ids.create_federated("bob", idp_subject="bob@corp.example", roles=["admin"])
    assert ids.get("bob").pwhash == ""                                     # an IdP user has no secret here
    assert verify(ids.login_federated({"sub": "bob@corp.example"}), signer.tokens.keyset(), now=clk())["sub"] == "bob"
    clk.advance(TOKEN_LIFETIME + 61)
    try:
        verify(tok, signer.tokens.keyset(), now=clk()); raise AssertionError()
    except Expired:
        pass


def test_nothing_about_a_user_reaches_a_worker_only_trust_does():
    clk = Clock(1000.0)
    fed, links, dc, signer = _domain(clk)
    south = fed.clusters["south"]
    ids = IdentityStore(signer, dc.vars, dc.objects, now=clk)
    ids.create_local("alice", "pw", ["operator"])
    DomainPublisher(dc.vars).publish_keys(signer.tokens.keyset())
    agent = DomainAgent("south", dc.vars, south.vars.as_writer("agent"), now=clk)
    south.vars.acl = {"agent": ["domain/*"]}
    assert agent.sync()
    assert south.vars.list("identity/") == [] and sorted(south.vars.list("domain/")) == ["domain/keys", "domain/member"]   # keys, no people
    for path in ("vms/cameras/7", "vms/epoch/7", "vms/slots/w-0"):
        try:
            south.vars.as_writer("agent").put(path, {"x": 1}); raise AssertionError()
        except Forbidden:
            pass                                                           # the agent's only right is domain/*: not the controller's, not a worker's
    trust = ClusterTrust(south.vars)
    tok = ids.login("alice", "pw")
    assert verify(tok, trust.keyset(), trust.revoked(), now=clk())["sub"] == "alice"   # verified by south's console from south's OWN Variables


def test_a_member_always_carries_a_mark_that_it_is_one_and_its_console_shuts_when_the_keys_go():
    """The review's fourth pass. The cluster's console tells "the keys were lost" from "there never were any" by the
    rows only the agent writes (`DOMAIN_MARKS`), and each of those was conditional: `domain/root` only with a
    root-signed key set, the grants and the rest only when the domain has some for this cluster. A member with an
    unsigned key set and no grants had none of them — its keys deleted, the console was open to anybody as `admin`.
    The agent writes `domain/member` on every pass that leaves a key set, again after it was lost."""
    import tempfile
    import urllib.error
    import urllib.request
    from w2cplatform.cluster.objectstore import FsObjectStore
    from w2cplatform.domain.agent import MEMBER_PATH
    from vms.console import make_console
    from vms.controller import VmsController
    from w2cplatform.access import DOMAIN_MARKS
    clk = Clock(1000.0)
    fed, links, dc, signer = _domain(clk)
    south = fed.clusters["south"]
    DomainPublisher(dc.vars).publish_keys(signer.tokens.keyset())     # a key set, no grants for south, no root pinned
    agent = DomainAgent("south", dc.vars, south.vars, now=clk)
    assert agent.sync()
    assert MEMBER_PATH in DOMAIN_MARKS and south.vars.get(MEMBER_PATH)[0] == {"cluster": "south"}
    assert [p for p in DOMAIN_MARKS if south.vars.get(p)[0]] == [MEMBER_PATH]     # the only mark there is
    idx = south.vars.get(MEMBER_PATH)[1]
    agent.sync()
    assert south.vars.get(MEMBER_PATH)[1] == idx                                   # not rewritten every pass

    south.vars._items.pop(KEYS_PATH)                                               # the key set is lost: a rollback, past the store
    srv = make_console(VmsController(south.vars, FsObjectStore(tempfile.mkdtemp(prefix="m12-")), wall=clk), None, clk) \
        .serve("127.0.0.1", 0)
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/cameras")
            raise AssertionError("a member's console without its keys let a stranger in")
        except urllib.error.HTTPError as e:
            assert e.code == 503 and MEMBER_PATH in json.loads(e.read())["detail"]
    finally:
        srv.shutdown()
    south.vars._items.pop(MEMBER_PATH)
    assert agent.sync() and south.vars.get(MEMBER_PATH)[0] and south.vars.get(KEYS_PATH)[0]   # both back on the next pass


def test_domain_down_clusters_keep_verifying_nobody_new_logs_in():
    clk = Clock(1000.0)
    fed, links, dc, signer = _domain(clk)
    south = fed.clusters["south"]
    ids = IdentityStore(signer, dc.vars, dc.objects, now=clk)
    ids.create_local("alice", "pw", ["operator"])
    DomainPublisher(dc.vars).publish_keys(signer.tokens.keyset())
    agent = DomainAgent("south", dc.vars, south.vars, now=clk)
    agent.sync()
    tok = ids.login("alice", "pw")
    links["north"].up = False                                              # the domain holder is gone
    assert agent.sync() is False and agent.last_synced == 1000.0           # the agent stops updating, writes nothing
    trust = ClusterTrust(south.vars)
    assert verify(tok, trust.keyset(), now=clk())["sub"] == "alice"        # existing tokens: fine, offline
    try:
        ids.login("alice", "pw"); raise AssertionError()
    except Exception:
        pass                                                               # nobody NEW logs in


def test_revocation_travels_by_the_agent_and_rotation_overlaps():
    clk = Clock(1000.0)
    fed, links, dc, signer = _domain(clk)
    south = fed.clusters["south"]
    pub = DomainPublisher(dc.vars)
    pub.publish_keys(signer.tokens.keyset())
    agent = DomainAgent("south", dc.vars, south.vars, now=clk); agent.sync()
    tok = signer.tokens.issue("mallory", 900, now=clk(), kind="person")
    rl = RevocationList(); rl.revoke(verify(tok, signer.tokens.keyset(), now=clk()))
    pub.publish_revoked(rl); agent.sync()
    trust = ClusterTrust(south.vars)
    try:
        verify(tok, trust.keyset(), trust.revoked(), now=clk()); raise AssertionError()
    except Revoked:
        pass
    old_tok = signer.tokens.issue("alice", 900, now=clk(), kind="person")
    signer.tokens.rotate(overlap=600, now=clk()); pub.publish_keys(signer.tokens.keyset()); agent.sync()
    trust = ClusterTrust(south.vars)
    assert verify(old_tok, trust.keyset(), now=clk())["sub"] == "alice"    # the previous key is still in the set
    new_tok = signer.tokens.issue("alice", 900, now=clk(), kind="person")
    assert verify(new_tok, trust.keyset(), now=clk())["sub"] == "alice"
    clk.advance(700)
    try:
        verify(old_tok, trust.keyset(), now=clk()); raise AssertionError()
    except UnknownKey:
        pass                                                               # overlap over: the old key is retired


def test_grants_are_cluster_local_carried_by_the_agent_and_expiry_is_the_revocation_mechanism():
    clk = Clock(1000.0)
    fed, links, dc, signer = _domain(clk)
    south = fed.clusters["south"]
    pub = DomainPublisher(dc.vars); pub.publish_keys(signer.tokens.keyset())
    pub.publish_grants("south", [Grant("alice", "view", None, clk() + GRANT_LIFETIME), Grant("alice", "edit", "vms/7", clk() + GRANT_LIFETIME)])
    agent = DomainAgent("south", dc.vars, south.vars, now=clk); agent.sync()
    assert sorted(south.vars.list("domain/")) == ["domain/grants", "domain/keys", "domain/member"]   # trust and grants, no user
    g = ClusterGrants("south", now=clk)
    g.renew_from_domain(ClusterTrust(south.vars).grants())                            # the console loads them from ITS cluster
    auth = ClusterAuthoriser(g, signer.tokens.keyset(), now=clk)
    tok = signer.tokens.issue("alice", TOKEN_LIFETIME, now=clk(), kind="person")
    assert auth.authorise(tok, "view", "vms/12") == "alice" and auth.authorise(tok, "edit", "vms/7") == "alice"
    try:
        auth.authorise(tok, "edit", "vms/12"); raise AssertionError()
    except PermissionError as e:
        assert "no edit grant on vms/12 in south" in str(e)
    # The revoke cannot reach south (unreachable). State in advance when access ends:
    stated = g.access_ends("alice", token_exp=clk() + TOKEN_LIFETIME)
    assert stated == clk() + TOKEN_LIFETIME                                  # the token is the shorter lifetime here
    assert revocation_window(TOKEN_LIFETIME, GRANT_LIFETIME) == TOKEN_LIFETIME
    # ...then measure it: the token expires, the grant is still there, access is gone anyway.
    clk.advance(TOKEN_LIFETIME + 61)
    try:
        auth.authorise(tok, "view", "vms/12"); raise AssertionError()
    except PermissionError as e:
        assert "expired" in str(e)
    # And the other direction: a fresh token, but south's agent could not renew its grants past their expiry.
    clk.advance(GRANT_LIFETIME)
    tok2 = signer.tokens.issue("alice", TOKEN_LIFETIME, now=clk(), kind="person")         # the domain is back and issues a fresh token...
    try:
        auth.authorise(tok2, "view", "vms/12"); raise AssertionError()
    except PermissionError as e:
        assert "no view grant" in str(e)
    # The agent renews what the domain still grants — and drops what it does not.
    g.renew_from_domain([Grant("alice", "view", None, clk() + GRANT_LIFETIME)])
    assert g.may("alice", "view", 12) and not g.may("alice", "edit", 7)


def test_identity_publishes_object_first_then_pointer_and_restores_elsewhere():
    clk = Clock(1000.0)
    fed, links, dc, signer = _domain(clk)
    ids = IdentityStore(signer, dc.vars, dc.objects, publish_floor=0, now=clk)
    ids.create_local("alice", "pw", ["operator"]); ids.create_federated("bob", "bob@corp", ["admin"])
    assert ids.publish() and ids.publishes == 1 and not ids.publish()
    ptr, _ = dc.vars.get("identity/pointer")
    assert ptr["object"] == "identity/rev-1" and dc.objects.get("identity/rev-1") is not None
    ids.set_roles("alice", ["admin"]); assert ids.publish() and dc.vars.get("identity/pointer")[0]["revision"] == "2"
    # The domain holder dies. Move the domain to south: the backed-up key, then the identity object.
    backup = signer.backup()
    south = fed.clusters["south"]
    objs_backup = south.objects; objs_backup.put("identity/rev-2", dc.objects.get("identity/rev-2"))
    links["north"].up = False
    signer2 = Signer.restore("acme", south.vars, backup, now=clk)
    ids2 = IdentityStore.restore(signer2, south.vars, objs_backup, ptr | {"object": "identity/rev-2", "revision": "2"}, now=clk)
    assert {u.id: u.roles for u in ids2.users()} == {"alice": ["admin"], "bob": ["admin"]}
    assert verify(ids2.login("alice", "pw"), signer2.tokens.keyset(), now=clk())["sub"] == "alice"   # same key: old tokens too
    assert signer2.root.cert.subject == signer.root.cert.subject


def test_prefs_are_objects_and_a_stale_tab_is_told():
    from w2cplatform.cluster.variables import Conflict
    clk = Clock(1000.0)
    fed, _, dc, signer = _domain(clk)
    ids = IdentityStore(signer, dc.vars, dc.objects, now=clk)
    assert ids.get_prefs("alice") == ({}, 0)
    assert ids.put_prefs("alice", {"wall": [1, 2, 3]}, base_revision=0) == 1
    assert ids.put_prefs("alice", {"wall": [1, 2]}, base_revision=1) == 2
    try:
        ids.put_prefs("alice", {"wall": []}, base_revision=1); raise AssertionError()
    except Conflict:
        pass
    assert ids.get_prefs("alice") == ({"wall": [1, 2]}, 2)
    assert dc.vars.list("users/") == []                                    # nothing of this in raft


def test_break_glass_is_one_account_audited_and_alarmed():
    clk = Clock(1000.0)
    fed, _, dc, signer = _domain(clk)
    bg = BreakGlass.create(signer, "emergency-pw")
    try:
        bg.use("nope", who="carol", why="uplink down", now=clk()); raise AssertionError()
    except AuthError:
        pass
    tok = bg.use("emergency-pw", who="carol", why="uplink down, token expired", now=clk())
    p = verify(tok, signer.tokens.keyset(), now=clk())
    assert p["sub"] == "break-glass" and p["via"] == "break-glass" and p["who"] == "carol"
    assert len(bg.audit) == 2 and bg.alarm[-1].startswith("BREAK-GLASS used by carol") and bg.used_since_rotation == 1
    bg.rotate("new-pw"); assert bg.used_since_rotation == 0


def test_who_changed_the_people_the_grants_and_the_members_is_a_line_in_the_holders_journal():
    """Feedback CL. A record held who edited it last, and the history was lost. Every change to a person, to the
    domain's grants and to the list of members is a line of the `audit` family on the holder's resource, as the
    role `domain`: the actor the door verified, the record, what changed — and never a password."""
    import os
    import tempfile
    from w2cplatform.eventdatabase import EventIndex
    from w2cplatform.journal import Journal
    from w2cplatform.domain.grants import DOMAIN_GRANTS, Grant, grants_from_items, set_domain_grants
    from w2cplatform.domain.members import Members
    clk = Clock(1_757_500_000.0)
    fed, _, dc, signer = _domain(clk)
    root = tempfile.mkdtemp(prefix="holder-")
    journal = Journal(root, "domain", clk)
    users = IdentityStore(signer, dc.vars, dc.objects, now=clk, journal=journal)
    set_domain_grants(dc.vars, [Grant("alice", "admin", None, 0)], clk(), journal=journal, by="setup")
    users.create_local("bob", "s3cret-pw", ["operator"], by="alice")
    users.set_password("bob", "0ther-pw", by="alice")
    users.set_roles("bob", ["operator", "viewer"], by="alice")
    have = grants_from_items(dc.vars.get(DOMAIN_GRANTS)[0])
    set_domain_grants(dc.vars, have + [Grant("bob", "view", None, 0)], clk(), journal=journal, by="alice")
    users.delete("bob", by="alice")
    members = Members(dc.vars, wall=clk, journal=journal)
    members.add("cam-SN9001", how="accepted by alice", by="alice", key="ab" * 32)
    members.remove("cam-SN9001", by="alice")
    bg = BreakGlass.create(signer, "emergency-pw")
    bg.rotate("new-pw", by="alice", journal=journal)

    lines = EventIndex(root, "holder", wall=clk).query(0, clk() + 1, subsystem="audit", unit="audit/domain")["events"]
    assert [(e["kind"], e["user"], e.get("target")) for e in lines] == [
        ("domain.grants.changed", "setup", "domain"),
        ("domain.user.created", "alice", "bob"), ("domain.user.password", "alice", "bob"), ("domain.user.roles", "alice", "bob"),
        ("domain.grants.changed", "alice", "domain"),
        ("domain.grants.changed", "alice", "domain"), ("domain.user.deleted", "alice", "bob"),   # deleting bob takes his grant with him
        ("domain.member.admitted", "alice", "cam-SN9001"), ("domain.member.left", "alice", "cam-SN9001"),
        ("domain.break_glass.set", "alice", None)]
    assert lines[4]["added"] == "bob|view|" and lines[5]["removed"] == "bob|view|"
    assert lines[7]["key"] == "ab" * 32                                 # the key the person saw (CJ)
    text = json.dumps(lines)
    assert "s3cret" not in text and "0ther" not in text and "new-pw" not in text and "emergency" not in text
