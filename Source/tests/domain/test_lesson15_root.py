"""Lesson 15, step 9 — the domain's root, off the holder.

A camera holder can be carried off the wall, and with the keys of Lessons 4 and 7 in its flash, whoever has it
has the domain: tokens with any role, certificates for any device, and — back on the site's network — the
domain itself, by a holder record with a larger term. So the key that decides who the domain is leaves the
holder: the root is in the recovery file, and signs the key set, the holder record and the holder's issuing
certificate. The holder keeps what signs every minute; a theft is answered by a move that drops those keys.
"""
import json

from w2cplatform.cluster.variables import FakeVariables

from w2cplatform.domain.agent import LDEVID_PATH, ROOT_PATH, ClusterTrust, DomainAgent, DomainPublisher
from vms.domainpart.device import DeviceCluster
from w2cplatform.domain.federation import Federation
from w2cplatform.domain.members import Members
from w2cplatform.domain.shared import SharedSettings, SharedView, sign
from w2cplatform.trust.signer import DomainRoot, Signer, TrustBundle, VerifyError, _key_bytes
from w2cplatform.domain.term import BACKUP, carry_holder, find_holder, install, move_domain, read_holder
from w2cplatform.trust.tokens import KeySet, TokenError, verify
from tests.domain.conftest import Clock

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

DOMAIN = "acme"


def _pub_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def _site(wall, n=4):
    """Four cameras, the domain on SN0 from the first day with its root off the holder. Each camera was
    admitted with a key (Lesson 6) — the registrar wrote it on the list — and holds an LDevID for it."""
    fed, devices, device_keys = Federation(), {}, {}
    for i in range(n):
        d = DeviceCluster(f"SN{i}", FakeVariables(), wall=wall)
        d.boot()
        devices[d.name] = d
        fed.add(d.cluster(domain=i == 0))
    root = DomainRoot(DOMAIN, now=wall)
    holder = install(fed, "cam-SN0", DOMAIN, root, wall=wall, objects=devices["cam-SN0"].disk)
    members = Members(holder.vars, wall)
    ldevids = {}
    for name in devices:
        device_keys[name] = Ed25519PrivateKey.generate()
        if name != "cam-SN0":
            members.add(name, "voucher", serial=name[4:], key=_pub_hex(device_keys[name]))
        ldevids[name] = holder.signer.issue(name[4:], "ldevid", device_keys[name].public_key())
    agents = {name: _agent(fed, devices, name, "cam-SN0", wall) for name in devices if name != "cam-SN0"}
    for a in agents.values():
        a.sync()
    return fed, devices, root, holder, agents, ldevids


def _agent(fed, devices, name, holder, wall):
    d = devices[name]
    return DomainAgent(name, fed.clusters[holder].vars, d.flash, now=wall, console=d.local_console(), current=d.current,
                       domain_objects=devices[holder].disk_door(), cluster_objects=d.disk, published=d.local_objects())


def _objects(devices):
    return lambda name: devices[name].disk_door()


def test_the_recovery_file_is_the_root_and_the_holder_holds_none_of_it():
    """The root signs three rare things and is written nowhere online: not in the holder's Variables, not in
    its backups. Members pin it with the first key set it signed, and verify people's tokens as before."""
    wall = Clock()
    fed, devices, root, holder, agents, _ = _site(wall)
    stored, _ = holder.vars.get("domain/signer")
    assert _key_bytes(root.key).hex() not in stored.values()             # the flash has the holder's keys, not the root
    try:
        holder.signer.backup(); raise AssertionError("an issuing signer's keys must not leave the holder")
    except RuntimeError:
        pass
    assert b"root_key" in root.recovery()
    trust = ClusterTrust(devices["cam-SN2"].flash)
    assert trust.root() == root.public_bytes and trust.keyset().rev == 1
    assert agents["cam-SN2"].keys == "rev 1"
    tok = holder.signer.tokens.issue("anna", 900, now=wall(), kind="person")
    assert verify(tok, trust.keyset(), now=wall())["sub"] == "anna"
    assert read_holder(devices["cam-SN2"].flash, trust.keyset(), wall())["kid"] == "root"


def test_a_stolen_holder_can_neither_take_the_domain_nor_hand_out_keys_of_its_own():
    """The thief has SN0 and everything on its flash. He writes a holder record at term 9 with the token key,
    and a key set of his own, and puts SN0 back on the site's network. The members take neither: a term is
    the root's to sign, and a key set is taken only from the root they pinned."""
    wall = Clock()
    fed, devices, root, holder, agents, _ = _site(wall)
    thief = Signer(DOMAIN, holder.vars, now=wall)                        # read off the flash
    forged = sign({"term": 9, "holder": "cam-SN0", "at": wall()}, thief.tokens)
    import json
    holder.vars.put("domain/holder", {"doc": json.dumps(forged, sort_keys=True)})
    mine = KeySet(current="evil", keys={"evil": Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)})
    DomainPublisher(holder.vars).publish_keys(mine)
    agents["cam-SN2"].sync()
    member = devices["cam-SN2"].flash
    keys = ClusterTrust(member).keyset()
    assert agents["cam-SN2"].keys == "refused: a key set not signed by the domain's root"
    assert "evil" not in keys.keys
    assert carry_holder(holder.vars, member, keys, wall()).startswith("refused")
    assert read_holder(member, keys, wall())["term"] == 1
    assert find_holder(fed, devices["cam-SN3"].flash, ClusterTrust(devices["cam-SN3"].flash).keyset(), wall()) == "cam-SN0"
    assert read_holder(holder.vars, keys, wall()) is None                # its own claim, by a key that is not the root


def test_after_a_theft_the_move_drops_the_old_keys_and_signs_every_ldevid_again():
    """SN0 is taken off the wall. The operator moves the domain to SN1 from the recovery file, saying it was
    stolen: SN1 gets keys of its own, the root signs key set rev 2 without SN0's token key and with SN0's
    issuing certificate revoked, and signs again each member's LDevID for the key it was admitted with. A
    token the thief signs is refused wherever rev 2 has arrived; the shared settings still read."""
    wall = Clock()
    fed, devices, root, holder, agents, ldevids = _site(wall)
    shared = SharedSettings(holder.vars, devices["cam-SN0"].disk_door(), holder.signer.tokens, wall, term=lambda: 1)
    shared.edit(lambda s: s.update(shared={"vms": {"events_retention_days": 30}}), base_rev=0, by="anna")
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door())
    for a in agents.values():
        a.sync()
    stolen_token = holder.signer.tokens.issue("mallory", 900, now=wall(), role="admin", kind="person")
    old_ca = holder.signer.root.cert
    devices["cam-SN0"].power_off()

    new, report = move_domain(fed, "cam-SN1", root.recovery(), DOMAIN, _objects(devices), wall, stolen=True)
    assert report["keys_rev"] > 1 and new.signer.tokens.kid != holder.signer.tokens.kid
    assert sorted(report["reissued"]) == ["cam-SN1", "cam-SN2", "cam-SN3"]
    a2 = _agent(fed, devices, "cam-SN2", "cam-SN1", wall)
    a2.sync()
    trust = ClusterTrust(devices["cam-SN2"].flash)
    keys = trust.keyset()
    assert keys.rev == report["keys_rev"]
    try:
        verify(stolen_token, keys, now=wall()); raise AssertionError("the stolen key must be refused")
    except TokenError:
        pass
    assert verify(new.signer.tokens.issue("anna", 900, now=wall(), kind="person"), keys, now=wall())["sub"] == "anna"
    assert read_holder(devices["cam-SN2"].flash, keys, wall())["holder"] == "cam-SN1"
    assert SharedView(devices["cam-SN2"].flash, devices["cam-SN2"].disk, wall).settings() == \
        {"shared": {"vms": {"events_retention_days": 30}}}

    bundle = TrustBundle([root.cert])
    try:
        bundle.verify(ldevids["cam-SN2"], now=wall(), chain=[old_ca], revoked=keys.revoked_ca)
        raise AssertionError("an LDevID of the revoked issuing certificate must not verify")
    except VerifyError:
        pass
    row, _ = devices["cam-SN2"].flash.get(LDEVID_PATH)
    again = x509.load_pem_x509_certificate(row["cert"].encode())
    chain = [x509.load_pem_x509_certificate(row["chain"].encode())]
    assert bundle.verify(again, now=wall(), chain=chain, revoked=keys.revoked_ca) == f"{DOMAIN} root"


def test_a_planned_move_gives_the_new_holder_keys_of_its_own_and_the_old_ones_live_an_hour():
    """A camera being replaced, not stolen. The new holder still gets keys of its own — the old ones are not in
    the recovery file — but the old token key stays trusted for an hour, so nobody is logged out by a move.
    And the old holder, told it was replaced, forgets its keys: a camera on the wall with them is the stolen
    holder of step 9, waiting."""
    wall = Clock()
    fed, devices, root, holder, agents, _ = _site(wall)
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door())
    agents["cam-SN1"].sync()
    old_token = holder.signer.tokens.issue("anna", 900, now=wall(), kind="person")
    new, report = move_domain(fed, "cam-SN1", root.recovery(), DOMAIN, _objects(devices), wall)
    assert not report["reissued"] and new.signer.tokens.kid != holder.signer.tokens.kid
    a2 = _agent(fed, devices, "cam-SN2", "cam-SN1", wall)
    a2.sync()
    assert verify(old_token, ClusterTrust(devices["cam-SN2"].flash).keyset(), now=wall())["sub"] == "anna"
    assert holder.check() is False
    stored, _ = holder.vars.get("domain/signer")
    assert "token_key" not in stored and "deposed by term 2" in stored["forgotten"]
    wall.advance(3601)
    try:
        verify(holder.signer.tokens.issue("anna", 900, now=wall(), kind="person"), ClusterTrust(devices["cam-SN2"].flash).keyset(),
               now=wall())
        raise AssertionError("an hour on, the old holder's key is retired")
    except TokenError:
        pass


def test_a_key_set_only_goes_forward():
    """A thief who kept the key set rev 1 — signed by the root, and genuine — replays it after the move. A
    member holding rev 2 keeps rev 2: a key set, like the holder record, never goes backwards."""
    wall = Clock()
    fed, devices, root, holder, agents, _ = _site(wall)
    old_items, _ = holder.vars.get("domain/keys")
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door()); agents["cam-SN1"].sync()
    devices["cam-SN0"].power_off()
    _, report = move_domain(fed, "cam-SN1", root.recovery(), DOMAIN, _objects(devices), wall, stolen=True)
    rev = report["keys_rev"]
    a2 = _agent(fed, devices, "cam-SN2", "cam-SN1", wall)
    a2.sync()
    assert ClusterTrust(devices["cam-SN2"].flash).keyset().rev == rev > 1
    devices["cam-SN0"].boot()
    holder.vars.put("domain/keys", old_items)
    agents["cam-SN2"].sync()                                            # still pointed at the old holder
    assert agents["cam-SN2"].keys == f"holding rev {rev}"
    assert ClusterTrust(devices["cam-SN2"].flash).keyset().rev == rev


def test_the_signers_backup_of_lessons_4_and_7_cannot_answer_a_theft():
    """It holds both keys — the stolen ones. A move from it gives the new holder the thief's keys, and saying
    `stolen` there is refused with the reason, rather than moving and pretending."""
    wall = Clock()
    fed = Federation()
    for i in range(2):
        d = DeviceCluster(f"SN{i}", FakeVariables(), wall=wall); d.boot()
        fed.add(d.cluster(domain=i == 0))
    signer = Signer(DOMAIN, fed.clusters["cam-SN0"].vars, now=wall)
    try:
        move_domain(fed, "cam-SN1", signer.backup(), DOMAIN, lambda n: None, wall, stolen=True)
        raise AssertionError("the signer's backup must not claim to answer a theft")
    except ValueError as e:
        assert "root off the holder" in str(e)


def test_a_member_that_pinned_another_root_is_named_and_not_accepted():
    """Feedback BX. A member pins the root of the first key set it is given, so whoever answers its agent first
    becomes its root. SN9's first pass reached an impostor with a root of its own; afterwards its agent reaches
    the real domain, refuses every key set the real root signed — and still reports. The domain shows which root
    each member pinned, and an admin cannot accept SN9: it would be listed and take nothing this domain signs."""
    from w2cplatform.domain.api import ApiError
    wall = Clock()
    fed, devices, root, holder, agents, _ = _site(wall)
    impostor_fed, x0 = Federation(), DeviceCluster("X0", FakeVariables(), wall=wall)
    x0.boot()
    impostor_fed.add(x0.cluster(domain=True))
    install(impostor_fed, "cam-X0", DOMAIN, DomainRoot(DOMAIN, now=wall), wall=wall, objects=x0.disk)
    sn9 = DeviceCluster("SN9", FakeVariables(), wall=wall)
    sn9.boot()
    DomainAgent(sn9.name, impostor_fed.clusters["cam-X0"].vars, sn9.flash, now=wall, domain_objects=x0.disk_door(),
                published=sn9.local_objects()).sync()                    # the first answer: the impostor's
    real = DomainAgent(sn9.name, holder.vars, sn9.flash, now=wall, domain_objects=devices["cam-SN0"].disk_door(),
                       published=sn9.local_objects())
    real.sync()
    assert real.keys == "refused: signed by a root this member did not pin"
    members = Members(holder.vars, wall)
    knock = {k["name"]: k for k in members.knocking(devices["cam-SN0"].disk_door())}
    assert knock["cam-SN9"]["root"] == "another"
    assert members.pinned("cam-SN1", devices["cam-SN0"].disk_door()) == {"root": "this", "keys_rev": 1}
    try:
        members.accept("cam-SN9", by="anna", domain_objects=devices["cam-SN0"].disk_door())
        raise AssertionError("a member that pinned another root must not be accepted")
    except ApiError as e:
        assert e.status == 409 and "another root" in e.detail
    assert "cam-SN9" not in members.names()


def test_the_holder_becomes_a_member_with_the_key_it_was_admitted_with():
    """Feedback CC. A holder is on no list while it holds; after a move it was written in without a key, and the
    next theft did not sign its LDevID again — enrolled from the start. Its key travels in its backups, and the
    move writes it into its row."""
    wall = Clock()
    fed, devices, root, holder, agents, ldevids = _site(wall)
    pub = lambda c: c.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()   # noqa: E731
    holder.member_key = pub(ldevids["cam-SN0"])
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door()); agents["cam-SN1"].sync()
    new, _ = move_domain(fed, "cam-SN1", root.recovery(), DOMAIN, _objects(devices), wall)
    members = Members(new.vars, wall).read()["members"]
    assert members["cam-SN0"]["key"] == pub(ldevids["cam-SN0"])
    assert new.member_key == pub(ldevids["cam-SN1"])                    # its own, for its own backups
    a2 = _agent(fed, devices, "cam-SN2", "cam-SN1", wall); a2.sync()
    new.backup(["cam-SN2"], devices["cam-SN1"].disk_door()); a2.sync()
    devices["cam-SN1"].power_off()                                      # now SN1 is stolen
    third, report = move_domain(fed, "cam-SN2", root.recovery(), DOMAIN, _objects(devices), wall, stolen=True)
    assert "cam-SN0" in report["reissued"]                              # the former holder, by the key it was admitted with
    assert "cam-SN1" not in report["reissued"]                          # never the stolen one: the thief has its key
    row = Members(third.vars, wall).read()["members"]["cam-SN1"]
    assert "key" not in row and pub(ldevids["cam-SN1"]) in row["revoked_keys"]   # revoked, not merely skipped (CH)
    a3 = _agent(fed, devices, "cam-SN3", "cam-SN2", wall); a3.sync()
    third.backup(["cam-SN3"], devices["cam-SN2"].disk_door()); a3.sync()
    devices["cam-SN2"].power_off()                                      # a second theft, of somebody else
    _, report = move_domain(fed, "cam-SN3", root.recovery(), DOMAIN, _objects(devices), wall, stolen=True)
    assert "cam-SN1" not in report["reissued"] and "cam-SN0" in report["reissued"]   # the first thief's key stays dead



def test_a_revoked_member_key_survives_a_backup_from_before_the_theft():
    """Feedback CK. The revocation lived in the list of members, and the list travels in backups: a move restored
    from a copy made BEFORE the theft brought the thief's key back. Now it is also in the key set the root signs,
    which every member holds and which only goes forward — and the move reads that, not the copy, to decide."""
    wall = Clock()
    fed, devices, root, holder, agents, ldevids = _site(wall)
    pub = lambda c: c.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()   # noqa: E731
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door()); agents["cam-SN1"].sync()
    second, _ = move_domain(fed, "cam-SN1", root.recovery(), DOMAIN, _objects(devices), wall)
    a3 = _agent(fed, devices, "cam-SN3", "cam-SN1", wall); a3.sync()
    second.backup(["cam-SN3"], devices["cam-SN1"].disk_door()); a3.sync()   # a copy from BEFORE the theft, on SN3
    devices["cam-SN1"].power_off()                                      # SN1 is stolen
    third, report = move_domain(fed, "cam-SN2", root.recovery(), DOMAIN, _objects(devices), wall, stolen=True)
    assert pub(ldevids["cam-SN1"]) in ClusterTrust(third.vars).keyset().revoked_members
    for name in ("cam-SN0", "cam-SN3"):
        _agent(fed, devices, name, "cam-SN2", wall).sync()              # the members carry the new key set home
    devices["cam-SN2"].power_off()                                      # SN2 stolen too, and it backed up nowhere
    fourth, report = move_domain(fed, "cam-SN3", root.recovery(), DOMAIN, _objects(devices), wall, stolen=True)
    assert "cam-SN1" not in report["reissued"]                          # the old copy's list had its key: the key set says no
    assert pub(ldevids["cam-SN1"]) in ClusterTrust(fourth.vars).keyset().revoked_members
    try:
        Members(fourth.vars, wall).add("cam-SN1b", "approved by anna", key=pub(ldevids["cam-SN1"]))
        raise AssertionError("a revoked key admitted under another name")
    except Exception as e:
        assert getattr(e, "status", None) == 409


def test_a_move_signs_a_revision_larger_than_any_a_member_out_of_reach_may_hold():
    """Feedback CK, the question. The next revision was the reachable members' plus one; a member that took a
    later set and is off now would hold a larger number and refuse the new set for good. The revision is also at
    least the root's clock: a move made later always signs more."""
    wall = Clock()
    fed, devices, root, holder, agents, _ = _site(wall)
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door()); agents["cam-SN1"].sync()
    _, first = move_domain(fed, "cam-SN1", root.recovery(), DOMAIN, _objects(devices), wall)
    wall.advance(10)
    _, later = move_domain(fed, "cam-SN2", root.recovery(), DOMAIN, _objects(devices), wall)
    assert later["keys_rev"] > first["keys_rev"] >= 1000


def test_the_signers_start_with_the_recovery_file_founds_the_domain_at_term_one_and_a_later_start_leaves_it():
    """The three-site run, F4: the signer's first start with `RECOVERY_FILE` — the course's installer — signed the
    keys with the root and wrote no record of the holder, so `term_of` found the domain not installed with a term and
    the stand called `term.install` itself. As the product's `domain install` (`Install`, then `Found`): the record of
    the holder at term 1, signed by the root, written once into a store that names none; a later start leaves it; a start
    that names no holder writes nothing."""
    import os
    import tempfile
    from w2cplatform.domain.federation import Cluster
    from w2cplatform.domain.signer_service import first_signer, term_of
    from w2cplatform.domain.term import HOLDER
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.variables import FileVariables
    root_dir = tempfile.mkdtemp()
    vars_, objects = FileVariables(f"{root_dir}/vars"), FsObjectStore(f"{root_dir}/objects")
    recovery = os.path.join(root_dir, "recovery.bin")
    with open(recovery, "wb") as f:
        f.write(DomainRoot(DOMAIN).recovery())
    try:
        first_signer(vars_, DOMAIN, None, DomainPublisher(vars_), {"RECOVERY_FILE": recovery})
        raise AssertionError("a domain was founded with no holder named")
    except SystemExit as e:
        assert "DOMAIN_HOLDER" in str(e)
    assert vars_.list("domain/") == []                                    # nothing written
    env = {"RECOVERY_FILE": recovery, "CLUSTERS": "srv,relay-a=report"}
    signer = first_signer(vars_, DOMAIN, None, DomainPublisher(vars_), env)
    keys = ClusterTrust(vars_).keyset()
    rec = read_holder(vars_, keys, signer.now())
    assert rec["holder"] == "srv" and int(rec["term"]) == 1, rec
    was = vars_.get(HOLDER)
    fed = Federation()
    fed.add(Cluster("srv", vars_, objects, is_domain_holder=True))
    term = term_of(fed, signer, objects)
    assert term is not None and term.term == 1 and term.record is not None    # the root's record, not the signer's
    again = first_signer(vars_, DOMAIN, None, DomainPublisher(vars_), env)
    assert again.chain and vars_.get(HOLDER)[0] == was[0]                   # a later start: the record as it was


def test_install_seals_the_holders_keys_with_the_installers_ring():
    """The three-site run, F5: `term.install` made the signer with no ring, and `domain/signer` lay in the store in
    the clear until the signer's first start sealed it. The installer's ring seals it at once — the one it is given, or
    the one `SECRETS_KEY` names, as the product's install seals with its process's key."""
    import os
    import tempfile
    from w2cplatform.sealing import Sealer, is_sealed, new_key_file
    from w2cplatform.secrets import is_secret_field
    wall = Clock()
    path = os.path.join(tempfile.mkdtemp(prefix="ring-"), "platform.key")
    new_key_file(path)
    for given, env in ((Sealer.from_file(path), None), (None, path)):
        fed = Federation()
        d = DeviceCluster("SN0", FakeVariables(), wall=wall)
        d.boot()
        fed.add(d.cluster(domain=True))
        saved = os.environ.get("SECRETS_KEY")
        try:
            if env:
                os.environ["SECRETS_KEY"] = env
            install(fed, "cam-SN0", DOMAIN, DomainRoot(DOMAIN, now=wall), wall=wall, sealer=given)
        finally:
            if saved is None:
                os.environ.pop("SECRETS_KEY", None)
            else:
                os.environ["SECRETS_KEY"] = saved
        items, _ = fed.clusters["cam-SN0"].vars.get("domain/signer")
        secrets = {k: v for k, v in items.items() if is_secret_field(k) and v}
        assert secrets and all(is_sealed(v) for v in secrets.values()), sorted(secrets)
