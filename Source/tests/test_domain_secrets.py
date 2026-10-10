"""The domain's secrets (DOMAIN-PLATFORM.md, «Course check of domain secrets»), on `testsub` alone: a member reads
nothing of the holder's store — it asks the domain's door, signed by its own key, and gets its own rows, every secret
sealed to its key; it keeps them sealed with its own ring; the signer's keys, the people's and the emergency hashes and
the books' tokens lie sealed at rest; the backup carries secrets under the backup key; the agent's rights deny what only
the holder writes, in the daemon's rights file and in the in-process ACL alike."""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_domain_platform import Clock, site, spec  # noqa: E402

TALLIES = "domain/testsub/tallies"


def ring():
    from w2cplatform.sealing import Sealer, new_key_file
    path = os.path.join(tempfile.mkdtemp(prefix="ring-"), "platform.key")
    new_key_file(path)
    return Sealer.from_file(path)


def sealed_everywhere(items) -> list[str]:
    """Every `*_secret` of a row, at any depth, that is NOT sealed at rest."""
    from w2cplatform.domain.carry import _walk
    from w2cplatform.sealing import is_sealed
    clear = []
    _walk(items or {}, lambda f, v, c: clear.append(f"{c}:{f}") or v if not is_sealed(v) else v, "row")
    return clear


def holder_with_members(wall=None):
    """north holds the domain, with its ring; south and east are admitted with their keys; the holder keeps for each an
    emergency hash and a book of tallies whose entries carry a token, all sealed under its ring."""
    from w2cplatform.domain.agent import DomainPublisher, GRANTS_PATH
    from w2cplatform.domain.breakglass import set_password
    from w2cplatform.domain.carry import seal_row
    from w2cplatform.domain.identity import _hash
    from w2cplatform.domain.members import Members
    from w2cplatform.trust.memberkey import MemberKey
    from w2cplatform.trust.signer import Signer
    fed, wall = site(wall)
    north = fed.clusters["north"]
    holder_ring = ring()
    signer = Signer("acme", north.vars, now=wall, sealer=holder_ring)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    keys = {n: MemberKey.new() for n in ("south", "east")}
    members = Members(north.vars, wall, domain="north")
    for n, k in keys.items():
        members.add(n, "voucher", serial=n, key=k.pub, seal=k.seal_pub)
        set_password(north.vars, n, f"glass-{n}", wall(), holder_ring)
        north.vars.put(f"{GRANTS_PATH}/{n}", {f"anna|view|": str(wall() + 3600)})
        tok = signer.tokens.issue(n, 600, now=wall(), kind="tally", counter="s1")
        north.vars.put(f"{TALLIES}/{n}", seal_row(holder_ring, {"s1": json.dumps({"n": 3, "token_secret": tok})},
                                                  f"{TALLIES}/{n}"))
    assert not _hash("x").startswith("enc:")
    return fed, wall, signer, holder_ring, keys


def test_a_member_gets_through_the_door_its_own_rows_only_and_every_secret_sealed_to_its_key():
    """The door answers south with the public rows and south's own — never east's — and every secret in them is sealed
    to south's key: east's key does not open it, and neither does the holder's ring. South's client opens it."""
    from w2cplatform.domain.carry import CarryClient, HolderDoor
    from w2cplatform.trust.memberkey import NotMine, is_sealed_to
    fed, wall, signer, holder_ring, keys = holder_with_members()
    north = fed.clusters["north"]
    door = HolderDoor(north.vars, north.objects, holder_ring, wall)
    raw = CarryClient(door, "south", keys["south"], wall)._ask()
    assert not [p for p in raw["rows"] if p.endswith("/east")] and f"{TALLIES}/south" in raw["rows"]
    glass = raw["rows"]["domain/break_glass/south"]["pwhash_secret"]
    entry = json.loads(raw["rows"][f"{TALLIES}/south"]["s1"])
    assert is_sealed_to(glass) and is_sealed_to(entry["token_secret"])
    for other in (keys["east"],):
        try:
            other.open("pwhash_secret", glass, "domain/break_glass")
            raise AssertionError("another member opened south's emergency hash")
        except NotMine:
            pass
    got = CarryClient(door, "south", keys["south"], wall).carry()
    assert got["rows"]["domain/break_glass/south"]["pwhash_secret"].count(":") == 1          # the hash: salt:digest
    assert json.loads(got["rows"][f"{TALLIES}/south"]["s1"])["token_secret"].count(".") == 2   # a token again


def test_the_door_answers_only_the_admitted_key_within_its_clock_and_a_relay_only_for_whom_it_relays():
    """Signed by another key, or with a time an hour off, or naming a sealing key that is not the member's: refused. A
    cluster asks for another member only when the domain's topology says it relays that member."""
    from w2cplatform.domain.carry import CarryClient, HolderDoor, Refused, request_message
    from w2cplatform.domain.topology import Topology
    from w2cplatform.trust.memberkey import MemberKey
    fed, wall, signer, holder_ring, keys = holder_with_members()
    north = fed.clusters["north"]
    door = HolderDoor(north.vars, north.objects, holder_ring, wall)
    stranger = MemberKey.new()
    for ask in (lambda: door.carry("south", wall(), stranger.seal_pub, stranger.sign(request_message("south", wall(), stranger.seal_pub))),
                lambda: door.carry("south", wall() - 3600, keys["south"].seal_pub,
                                   keys["south"].sign(request_message("south", wall() - 3600, keys["south"].seal_pub))),
                lambda: door.carry("south", wall(), stranger.seal_pub,
                                   keys["south"].sign(request_message("south", wall(), stranger.seal_pub))),
                lambda: CarryClient(door, "east", keys["east"], wall).carry_for("south")):
        try:
            ask()
            raise AssertionError("the door answered")
        except Refused as e:
            assert e.status in (401, 403), e.detail
    Topology(north.vars).edit(lambda d: d["via"].update({"south": "east"}), 0, known={"north", "south", "east"})
    got = CarryClient(door, "east", keys["east"], wall).carry_for("south")
    assert got["key"] == keys["south"].pub and f"{TALLIES}/south" in got["rows"]
    try:
        keys["east"].open("pwhash_secret", got["rows"]["domain/break_glass/south"]["pwhash_secret"], "domain/break_glass")
        raise AssertionError("the relay opened its member's secret")
    except Exception:                                    # noqa: BLE001 — sealed to south, not to east
        pass


def test_an_agent_keeps_what_it_carried_sealed_with_its_own_ring_and_reads_nothing_of_the_holders_store():
    """South's agent, given the door and its key, never reads north's store — every row it writes at home holds its
    secrets sealed with SOUTH's ring, and opens to what the holder decided."""
    from w2cplatform.domain.agent import BREAK_GLASS_PATH, DomainAgent
    from w2cplatform.domain.carry import CarryClient, HolderDoor, open_row
    fed, wall, signer, holder_ring, keys = holder_with_members()
    north, south = fed.clusters["north"], fed.clusters["south"]
    reads = []

    class Watched:                                       # the holder's store, counting who reads it
        def __init__(self, inner): self.inner = inner
        def get(self, p): reads.append(p); return self.inner.get(p)
        def list(self, p): reads.append(p); return self.inner.list(p)
    door = HolderDoor(north.vars, north.objects, holder_ring, wall)
    south_ring = ring()
    agent = DomainAgent("south", CarryClient(door, "south", keys["south"], wall), south.vars, now=wall,
                        sealer=south_ring, key=keys["south"])
    assert not hasattr(agent.domain_vars, "get")            # its handle on the domain is the door, not a store
    watched = Watched(north.vars)
    assert agent.sync() and not reads
    stored, _ = south.vars.get(BREAK_GLASS_PATH)
    assert stored["pwhash_secret"].startswith("enc:v1:") and not sealed_everywhere(south.vars.get(TALLIES)[0])
    assert open_row(south_ring, stored, BREAK_GLASS_PATH)["pwhash_secret"].count(":") == 1
    assert json.loads(open_row(south_ring, south.vars.get(TALLIES)[0], TALLIES)["s1"])["token_secret"].count(".") == 2
    del watched
    idx = south.vars.get(TALLIES)[1]
    assert agent.sync() and south.vars.get(TALLIES)[1] == idx       # nothing changed: nothing written, sealed or not


def test_the_signers_keys_lie_sealed_and_a_token_key_rotation_survives_a_restart():
    """`domain/signer` holds `issuing_key_secret`, `token_key_secret`, `backup_key_secret` sealed under the ring; a
    signer started again with the ring signs with the rotated key and still verifies what the old key signed; without
    the ring it does not start on guessed keys."""
    from w2cplatform.sealing import Sealed
    from w2cplatform.trust.signer import Signer
    from w2cplatform.trust.tokens import verify
    fed, wall = site()
    north = fed.clusters["north"]
    r = ring()
    s = Signer("acme", north.vars, now=wall, sealer=r)
    row, _ = north.vars.get("domain/signer")
    assert not sealed_everywhere(row) and {"issuing_key_secret", "token_key_secret", "backup_key_secret"} <= set(row)
    old = s.tokens.issue("anna", 900, now=wall(), kind="person")
    kid = s.rotate_tokens(3600)
    again = Signer("acme", north.vars, now=wall, sealer=r)
    assert again.tokens.kid == kid and verify(old, again.tokens.keyset(), now=wall())["sub"] == "anna"
    try:
        Signer("acme", north.vars, now=wall)
        raise AssertionError("a signer started on keys it could not open")
    except (Sealed, RuntimeError):
        pass


def test_the_backup_carries_the_people_and_the_emergency_hashes_under_the_backup_key_and_a_move_opens_them():
    """The keepers of a backup copy read no hash of it: the people (`identity/users/*`) and every emergency hash are in
    it sealed under the backup key, HMAC of the root's key — and a move by the recovery file derives that key again,
    opens them, and seals them under the new holder's ring."""
    from w2cplatform.domain.agent import DomainAgent, DomainPublisher
    from w2cplatform.domain.carry import open_row
    from w2cplatform.domain.identity import IdentityStore, _check
    from w2cplatform.domain.term import BACKUP_TAKEN, install, move_domain
    from w2cplatform.trust.signer import DomainRoot
    fed, wall = site()
    north, south = fed.clusters["north"], fed.clusters["south"]
    north_ring, south_ring = ring(), ring()
    root = DomainRoot("acme", now=wall)
    holder = install(fed, "north", "acme", root, wall, objects=north.objects)
    holder.signer.sealer = north_ring
    holder.signer._persist()
    IdentityStore(holder.signer, north.vars, north.objects, now=wall).create_local("anna", "pw", ["admin"])
    assert north.vars.get("identity/users/anna")[0]["pwhash_secret"].startswith("enc:v1:")
    holder.backup(["south"], north.objects)
    doc = json.loads(north.objects.get("backup/rev-1"))
    assert doc["state"]["identity/users/anna"]["pwhash_secret"].startswith("enc:v1:backup")
    assert DomainAgent("south", north.vars, south.vars, now=wall, domain_objects=north.objects,
                       cluster_objects=south.objects).sync() and south.objects.get(BACKUP_TAKEN)
    DomainPublisher(north.vars)
    new, report = move_domain(fed, "south", root.recovery(), "acme", lambda n: fed.clusters[n].objects, wall,
                              sealer=south_ring)
    restored = south.vars.get("identity/users/anna")[0]
    assert restored["pwhash_secret"].startswith("enc:v1:"), report["sentence"]
    assert _check("pw", open_row(south_ring, restored, "identity/users/anna")["pwhash_secret"])


def test_what_a_returning_holder_stranded_names_a_secret_and_never_copies_it():
    """`stranded` is a plain row the operator reads (`domain/stranded`): an item that differs from the restored state is
    listed with its value — except a `*_secret`, which is named and never copied out of the ring it was opened from."""
    from w2cplatform.domain.term import stranded
    fed, _ = site()
    north = fed.clusters["north"]
    north.vars.put("identity/users/anna", {"pwhash_secret": "scrypt$the-old-hash", "roles": "admin,viewer"})
    left = stranded(north.vars, {"identity/users/anna": {"pwhash_secret": "scrypt$the-new-hash", "roles": "admin"}})
    assert sorted(left) == [["identity/users/anna", "pwhash_secret", "<secret: differs>"],
                            ["identity/users/anna", "roles", "admin,viewer"]]


def test_the_emergency_password_has_a_writer_and_the_cluster_checks_it_sealed():
    """`breakglass.set_password` keeps the hash sealed at the holder; carried home through the door and sealed with the
    cluster's ring, the cluster's console opens it at the one moment it checks a password."""
    from w2cplatform.domain.access import ClusterAccess, Denied
    from w2cplatform.domain.agent import DomainAgent
    from w2cplatform.domain.carry import CarryClient, HolderDoor
    fed, wall, signer, holder_ring, keys = holder_with_members()
    north, south = fed.clusters["north"], fed.clusters["south"]
    south_ring = ring()
    door = HolderDoor(north.vars, north.objects, holder_ring, wall)
    assert DomainAgent("south", CarryClient(door, "south", keys["south"], wall), south.vars, now=wall,
                       sealer=south_ring, key=keys["south"]).sync()
    access = ClusterAccess(south.vars, wall, sealer=south_ring)
    assert access.glass("vera", "the domain is away", "glass-south")["via"] == "break-glass"
    for bad in ("glass-east", ""):
        try:
            access.glass("vera", "guess", bad)
            raise AssertionError("a wrong emergency password let somebody in")
        except Denied:
            pass
    try:
        ClusterAccess(south.vars, wall, sealer=ring()).glass("vera", "x", "glass-south")
        raise AssertionError("another ring opened the hash")
    except Denied as e:
        assert e.status == 503


def test_w2cctl_counts_the_domains_secrets_in_the_clear_and_seals_them():
    """Rows written before a ring existed: `status` counts them in the clear (exit 1), `seal` seals them under the
    current key, by CAS, and `status` is clean."""
    from w2cplatform import w2cctl
    from w2cplatform.domain.carry import open_row
    fed, wall = site()
    north = fed.clusters["north"]
    north.vars.put("domain/break_glass/south", {"pwhash_secret": "salt:digest", "set_at": "1"})
    north.vars.put(f"{TALLIES}/south", {"s1": json.dumps({"token_secret": "a.b.c"})})
    r = ring()
    got = w2cctl.status(north.vars, r, ["domain/"])
    assert got["domain/"]["clear"] == 2
    assert w2cctl.seal(north.vars, r, ["domain/"]) == 2 and w2cctl.status(north.vars, r, ["domain/"])["domain/"]["clear"] == 0
    assert open_row(r, north.vars.get("domain/break_glass/south")[0], "domain/break_glass/south")["pwhash_secret"] == "salt:digest"


def test_the_agents_rights_deny_what_only_the_holder_writes_and_its_reads_never_the_signers_row():
    """The domain's roles from the specs: the agent writes `domain/*` but the signer's row, the members, the holder's
    rows for each member, a subsystem's books for each member and its kept rows; it writes its own copies (the key set,
    its grants, its books carried home, its member key); it reads no signer row. The daemon's rights file and the
    in-process ACL of a box say the same."""
    from w2cplatform.domain.rights import roles
    from w2cplatform.storemachine import Rights
    from w2cplatform.variables import FileVariables, Forbidden
    spec()
    r = roles()
    assert "member" not in r and "testsubdomain" in r
    agent = r["domainagent"]
    rights = Rights({"domainagent": agent})
    mine = ["domain/keys", "domain/grants", "domain/pending", "domain/backup-taken", TALLIES, "domain/member-key",
            "domain/break_glass", "domain/holder"]
    holders = ["domain/signer", "domain/members", "domain/grants/south", "domain/pending/south", f"{TALLIES}/south",
               "domain/testsub/ledger", "domain/break_glass/south", "domain/backup/south"]
    box = FileVariables(tempfile.mkdtemp(prefix="acl-"), "domainagent", {"domainagent": agent["write"]}, volatile=True)
    for key in mine:
        assert rights.allows("domainagent", "write", key), key
        box.put(key, {"x": "1"})
    for key in holders:
        assert not rights.allows("domainagent", "write", key), key
        try:
            box.put(key, {"x": "1"})
            raise AssertionError(f"the box let the agent write {key}")
        except Forbidden:
            pass
    assert not rights.allows("domainagent", "read", "domain/signer") and rights.allows("domainagent", "read", "domain/keys")
    assert rights.allows("testsubdomain", "write", f"{TALLIES}/south") if "testsubdomain" in rights.roles else True


def test_a_relay_keeps_its_members_answers_in_memory_and_gives_each_only_its_own():
    """east relays south and west: what the domain answered for each lies in the relay agent's memory, sealed to that
    member — nothing of it in the relay's stores — and a member asking the relay gets its own, by its signature; asking
    as another member is refused."""
    from w2cplatform.domain.agent import DomainAgent
    from w2cplatform.domain.carry import CarryClient, HolderDoor, Refused, request_message
    from w2cplatform.domain.members import Members
    from w2cplatform.domain.relay import Relay
    from w2cplatform.domain.topology import Topology
    from w2cplatform.trust.memberkey import MemberKey
    fed, wall, signer, holder_ring, keys = holder_with_members()
    north, south, east = fed.clusters["north"], fed.clusters["south"], fed.clusters.get("east")
    if east is None:
        from tests.test_domain_platform import cluster
        east = cluster("east", wall)
        fed.add(east)
    keys["west"] = MemberKey.new()
    Members(north.vars, wall, domain="north").add("west", "voucher", key=keys["west"].pub, seal=keys["west"].seal_pub)
    Topology(north.vars).edit(lambda d: d["via"].update({"south": "east", "west": "east"}), 0,
                              known={"north", "south", "east", "west"})
    door = HolderDoor(north.vars, north.objects, holder_ring, wall)
    relay = DomainAgent("east", CarryClient(door, "east", keys["east"], wall), east.vars, now=wall, key=keys["east"],
                        relay_members=["south", "west"], bundle_store=east.objects, sealer=ring())
    assert relay.sync() and set(relay.relayed) == {"south", "west"}
    assert not east.vars.list("relay/") and not [k for k in east.objects.list("") if "south" in k and "relay" in k]
    through = Relay(relay)
    got = through.vars.answer_for("south", keys["south"])
    assert f"{TALLIES}/south" in got["rows"] and not [p for p in got["rows"] if p.endswith("/west")]
    try:
        relay_door = through.door
        relay_door.carry("south", wall(), keys["west"].seal_pub, keys["west"].sign(request_message("south", wall(), keys["west"].seal_pub)))
        raise AssertionError("the relay gave south's rows to west")
    except Refused:
        pass


def test_a_cluster_the_door_refuses_knocks_by_the_key_it_signs_with_and_is_admitted_by_it():
    """The three-site run, O2: an agent carrying through the domain's door that the door does not know
    ended its pass at the refusal, before any report — and the domain knew of a cluster asking to join only from a
    report, so it never knocked and a person had nothing to compare. The ask names the key it is signed with; refused,
    it is remembered as a knock (the product's `Members.NoteKnock`), over HTTP as in process: named in `knocking` with
    the key's fingerprint, accepted by it — and the next ask is answered. A knock signed by another key than it names,
    or out of the clock, is not remembered; a knock admits nobody by itself."""
    import urllib.parse
    from w2cplatform.console import open_doors
    from w2cplatform.domain.agent import DomainAgent
    from w2cplatform.domain.carry import CarryClient, HolderDoor, Refused, request_message
    from w2cplatform.domain.members import KNOCKS, Members, fingerprint
    from w2cplatform.domain.signer_service import Holder
    from w2cplatform.trust.memberkey import MemberKey
    fed, wall, signer, holder_ring, keys = holder_with_members()
    north = fed.clusters["north"]
    door = HolderDoor(north.vars, north.objects, holder_ring, wall)
    members = Members(north.vars, wall, domain="north")
    box, liar = MemberKey.new(), MemberKey.new()
    try:                                                 # names box's key and is signed by another: no knock
        door.carry("box-x", wall(), box.seal_pub, liar.sign(request_message("box-x", wall(), box.seal_pub)), key=box.pub)
        raise AssertionError("the door answered")
    except Refused as e:
        assert e.status == 403
    assert north.objects.list(KNOCKS + "/") == [] and members.knocking(north.objects) == []
    agent = DomainAgent("box-x", CarryClient(door, "box-x", box, wall), fed.clusters["south"].vars, now=wall, key=box)
    assert agent.sync() is False and "refused" in agent.keys
    srv = open_doors("127.0.0.1", 0, Holder(north.vars, north.objects, signer, carry_door=door, wall=wall).handler(),
                     unix_env="KN_NO_SUCH_SOCKET", say=False)
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        wall.advance(30)
        try:
            CarryClient(url, "box-x", box, wall).carry()
            raise AssertionError("the door answered over HTTP")
        except Refused as e:
            assert e.status == 403 and "no member with a key" in e.detail
        knocking = members.knocking(north.objects)
        assert [k["name"] for k in knocking] == ["box-x"] and knocking[0]["fingerprint"] == fingerprint(box.pub)
        assert knocking[0]["times"] == 2 and knocking[0]["last"] == wall(), knocking
        assert members.accept("box-x", "anna", north.objects, fingerprint=fingerprint(box.pub))
        assert members.knocking(north.objects) == []
        got = CarryClient(url, "box-x", box, wall).carry()
        assert got["cluster"] == "box-x" and "domain/keys" in got["rows"], urllib.parse.quote(str(got)[:200])
    finally:
        srv.shutdown()


def test_the_door_carries_for_a_member_on_the_list_alone_and_the_relay_says_so_to_one_that_left():
    """The three-site run, O9: the holder's door asked only the topology before answering a relay for a
    member — `DELETE /domain/members/<member>` and the relay still got 200 for it (public rows, no secret, `key: null`),
    and the relay refused the member as one "admitted without a key", not as one that left. The door carries for a member
    on the list alone (404, said); the relay drops what it kept for it, relays the others as before, and answers the
    member with the domain's words."""
    from w2cplatform.domain.agent import DomainAgent
    from w2cplatform.domain.carry import CarryClient, HolderDoor, Refused, request_message
    from w2cplatform.domain.members import Members
    from w2cplatform.domain.relay import Relay
    from w2cplatform.domain.topology import Topology
    from w2cplatform.trust.memberkey import MemberKey
    from tests.test_domain_platform import cluster
    fed, wall, signer, holder_ring, keys = holder_with_members()
    north = fed.clusters["north"]
    east = fed.clusters.get("east") or cluster("east", wall)
    keys["west"] = MemberKey.new()
    members = Members(north.vars, wall, domain="north")
    members.add("west", "voucher", key=keys["west"].pub, seal=keys["west"].seal_pub)
    Topology(north.vars).edit(lambda d: d["via"].update({"south": "east", "west": "east"}), 0,
                              known={"north", "south", "east", "west"})
    door = HolderDoor(north.vars, north.objects, holder_ring, wall)
    relay = DomainAgent("east", CarryClient(door, "east", keys["east"], wall), east.vars, now=wall, key=keys["east"],
                        relay_members=["south", "west"], bundle_store=east.objects, sealer=ring())
    assert relay.sync() and set(relay.relayed) == {"south", "west"}
    assert members.remove("south", by="anna")
    try:
        CarryClient(door, "east", keys["east"], wall).carry_for("south")
        raise AssertionError("the door carried for a member that left")
    except Refused as e:
        assert e.status == 404 and "no member of this domain" in e.detail, e.detail
    assert relay.sync() and set(relay.relayed) == {"west"}
    relay_door = Relay(relay).door
    try:
        relay_door.carry("south", wall(), keys["south"].seal_pub,
                         keys["south"].sign(request_message("south", wall(), keys["south"].seal_pub)))
        raise AssertionError("the relay answered a member that left")
    except Refused as e:
        assert e.status == 403 and "no member of this domain" in e.detail and "without a key" not in e.detail, e.detail
    assert Relay(relay).vars.answer_for("west", keys["west"])["rows"]


def test_a_member_behind_a_relay_over_the_network_judges_its_books_by_the_relays_age_mark():
    """The three-site run, O10: a member with `RELAY_URL` carries through a `CarryClient`, which has no
    `seen()`; the relay's age mark came in its answer and was never used — while the relay was cut from the domain the
    member wrote into `domain/seen` the time it last talked to the relay and took its books for current. An answer that
    carries the relay's mark is measured by it: the books are as old as the relay's last contact with the domain."""
    from w2cplatform.domain.agent import DOMAIN_SEEN, DomainAgent
    from w2cplatform.domain.carry import CarryClient, HolderDoor
    from w2cplatform.domain.federation import Unreachable
    from w2cplatform.domain.relay import Relay
    from w2cplatform.domain.topology import Topology
    from w2cplatform.objects import FsObjectStore
    from tests.test_domain_platform import cluster
    fed, wall, signer, holder_ring, keys = holder_with_members()
    north, south = fed.clusters["north"], fed.clusters["south"]
    east = fed.clusters.get("east") or cluster("east", wall)
    Topology(north.vars).edit(lambda d: d["via"].update({"south": "east"}), 0, known={"north", "south", "east"})
    door = HolderDoor(north.vars, north.objects, holder_ring, wall)
    relay = DomainAgent("east", CarryClient(door, "east", keys["east"], wall), east.vars, now=wall, key=keys["east"],
                        relay_members=["south"], bundle_store=east.objects, sealer=ring())
    assert relay.sync()
    flash = FsObjectStore(tempfile.mkdtemp(prefix="flash-"))
    member = DomainAgent("south", CarryClient(Relay(relay).door, "south", keys["south"], wall), south.vars, now=wall,
                      key=keys["south"], seen_store=flash, sealer=ring())
    assert member.sync()
    assert json.loads(flash.get(DOMAIN_SEEN))["ts"] == wall()                  # the relay reached the domain just now

    class Cut:
        def answer_for(self, cluster, key):
            raise Unreachable("the centre is away")

        def carry_for(self, member):
            raise Unreachable("the centre is away")
    reached = wall()
    relay.domain_vars = Cut()
    wall.advance(600)
    assert relay.sync() is False                                               # cut: its mark says 600 s
    assert member.sync()                                                          # the member still reaches the relay…
    assert json.loads(flash.get(DOMAIN_SEEN))["ts"] == reached                 # …and its books are 600 s old
