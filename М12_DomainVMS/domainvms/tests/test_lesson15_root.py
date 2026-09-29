"""Lesson 15, step 9 — the domain's root, off the holder.

A camera holder can be carried off the wall, and with the keys of Lessons 4 and 7 in its flash, whoever has it
has the domain: tokens with any role, certificates for any device, and — back on the site's network — the
domain itself, by a holder record with a larger term. So the key that decides who the domain is leaves the
holder: the root is in the recovery file, and signs the key set, the holder record and the holder's issuing
certificate. The holder keeps what signs every minute; a theft is answered by a move that drops those keys.
"""
from cluster.variables import FakeVariables

from domain.agent import LDEVID_PATH, ROOT_PATH, ClusterTrust, DomainAgent, DomainPublisher
from domain.device import DeviceCluster
from domain.federation import Federation
from domain.members import Members
from domain.shared import SharedSettings, SharedView, sign
from domain.signer import DomainRoot, Signer, TrustBundle, VerifyError, _key_bytes
from domain.term import BACKUP, carry_holder, find_holder, install, move_domain, read_holder
from domain.tokens import KeySet, TokenError, verify
from tests.conftest import Clock

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
    tok = holder.signer.tokens.issue("anna", 900, now=wall())
    assert verify(tok, trust.keyset(), now=wall())["sub"] == "anna"
    assert read_holder(devices["cam-SN2"].flash, trust.keyset(), wall())["kid"] == "root"


def test_a_stolen_holder_can_neither_take_the_domain_nor_hand_out_keys_of_its_own():
    """The thief has SN0 and everything on its flash. He writes a holder record at term 9 with the token key,
    and a key set of his own, and puts SN0 back on the site's network. The members take neither: a term is
    the root's to sign, and a key set is taken only from the root they pinned."""
    wall = Clock()
    fed, devices, root, holder, agents, _ = _site(wall)
    thief = Signer(DOMAIN, holder.vars, now=wall)                        # read off the flash
    forged = sign({"term": 9, "host": "cam-SN0", "at": wall()}, thief.tokens)
    import json
    holder.vars.put("domain/host", {"doc": json.dumps(forged, sort_keys=True)})
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
    shared.edit(lambda s: s.update({"retention_days": 30}), base_rev=0, by="anna")
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door())
    for a in agents.values():
        a.sync()
    stolen_token = holder.signer.tokens.issue("mallory", 900, now=wall(), role="admin")
    old_ca = holder.signer.root.cert
    devices["cam-SN0"].power_off()

    new, report = move_domain(fed, "cam-SN1", root.recovery(), DOMAIN, _objects(devices), wall, stolen=True)
    assert report["keys_rev"] == 2 and new.signer.tokens.kid != holder.signer.tokens.kid
    assert sorted(report["reissued"]) == ["cam-SN1", "cam-SN2", "cam-SN3"]
    a2 = _agent(fed, devices, "cam-SN2", "cam-SN1", wall)
    a2.sync()
    trust = ClusterTrust(devices["cam-SN2"].flash)
    keys = trust.keyset()
    assert keys.rev == 2
    try:
        verify(stolen_token, keys, now=wall()); raise AssertionError("the stolen key must be refused")
    except TokenError:
        pass
    assert verify(new.signer.tokens.issue("anna", 900, now=wall()), keys, now=wall())["sub"] == "anna"
    assert read_holder(devices["cam-SN2"].flash, keys, wall())["host"] == "cam-SN1"
    assert SharedView(devices["cam-SN2"].flash, devices["cam-SN2"].disk, wall).settings() == {"retention_days": 30}

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
    old_token = holder.signer.tokens.issue("anna", 900, now=wall())
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
        verify(holder.signer.tokens.issue("anna", 900, now=wall()), ClusterTrust(devices["cam-SN2"].flash).keyset(),
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
    move_domain(fed, "cam-SN1", root.recovery(), DOMAIN, _objects(devices), wall, stolen=True)
    a2 = _agent(fed, devices, "cam-SN2", "cam-SN1", wall)
    a2.sync()
    assert ClusterTrust(devices["cam-SN2"].flash).keyset().rev == 2
    devices["cam-SN0"].boot()
    holder.vars.put("domain/keys", old_items)
    agents["cam-SN2"].sync()                                            # still pointed at the old holder
    assert agents["cam-SN2"].keys == "holding rev 2"
    assert ClusterTrust(devices["cam-SN2"].flash).keyset().rev == 2


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
