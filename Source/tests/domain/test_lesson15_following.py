"""Lesson 15 — the members follow the holder by themselves («Архитектор», 2026-10-06; ADR 0001 §1.12).

A move writes the new holder's own store and nobody else's: its term record, signed, the state it restored, its keys.
No member is told. Each member's agent asks every cluster of the domain for the holder's record that cluster holds —
`GET /api/held` at its console (`term.held`); here a cluster's store read through its door, which is what its console
reads — and follows the greatest term that verifies against the key set the member carries (`agent.HolderFollower`).
A planned handover is the same rule from the other side: the target takes the domain onto its own store, and the
outgoing holder writes none but its own.
"""

from tests.member_console import device_console, admit_fixtures
from tests.reporting import sync as report_sync
import json

from w2cplatform.domain.agent import DomainAgent, HolderFollower
from w2cplatform.domain.term import HOLDER, handover, held, move_domain, read_holder
from w2cplatform.trust.documents import sign
from w2cplatform.trust.tokens import TokenIssuer
from tests.domain import test_lesson15_domain_of_one as one
from tests.domain import test_lesson15_root as rooted
from tests.domain.conftest import Clock

POLLS = 2                                                # a member is on the new holder within this many passes


def _follower(fed, devices, name, wall, holder="cam-SN0"):
    """A member's agent that follows the holder: it asks every cluster's console what it holds (`held`, through that
    cluster's door — a cluster that is off does not answer) and, on a new holder, carries through that holder's door."""
    d = devices[name]
    ask = {n: (lambda n=n: held(n, fed.clusters[n].vars)) for n in devices}

    def open_door(rec):
        return fed.clusters[rec["holder"]].vars, devices[rec["holder"]].disk_door()
    return DomainAgent(name, fed.clusters[holder].vars, d.flash, now=wall, console=device_console(d),
                       domain_objects=devices[holder].disk_door(), cluster_objects=d.disk, published=d.local_objects(),
                       follow=HolderFollower(ask), open_door=open_door)


def _by_url(fed, devices, name, wall, holder="cam-SN0"):
    """A follower whose door is the record's `url` and nothing else, as the agent's process opens it (`agent.main`:
    no `url`, no door): `http://<cluster>:8445` is that cluster's door here."""
    a = _follower(fed, devices, name, wall, holder)

    def open_door(rec):
        n = (rec.get("url") or "").removeprefix("http://").removesuffix(":8445")
        return (fed.clusters[n].vars, devices[n].disk_door()) if n in fed.clusters else None
    a.open_door = open_door
    return a


def _writes(devices):
    """What has been written into each camera's stores so far: `{name: (flash puts, card puts)}`."""
    counts = {n: 0 for n in devices}
    for n, d in devices.items():
        put = d.disk.put

        def counted(key, data, n=n, put=put):
            counts[n] += 1
            return put(key, data)
        d.disk.put = counted
    return lambda: {n: (devices[n].flash.writes, counts[n]) for n in devices}


def _follows(agents, name, holder):
    a = agents[name]
    for _ in range(POLLS):
        report_sync(a)
        if a.holder_at == holder:
            return True
    return False


def test_after_a_move_no_member_store_is_written_and_every_agent_follows_the_new_holder():
    """SN0 dies; the domain is moved onto SN1 from the signer's backup. The move writes SN1's stores and not one byte of
    SN2's or SN3's — or of SN0's, off. Nobody tells the members: each agent, polling the clusters, finds term 2 on SN1,
    keeps the record and carries through SN1's door from then on — SN3's kept edit lands from there."""
    wall = Clock()
    fed, devices, signer, offline, holder, _ = one._site(wall)
    agents = {n: _follower(fed, devices, n, wall) for n in devices if n != "cam-SN0"}
    for a in agents.values():
        report_sync(a)
    assert one._keep_an_edit_for(fed, devices, "SN3", holder.vars, wall)["kept"]
    holder.backup(["cam-SN1", "cam-SN2"], devices["cam-SN0"].disk_door())
    for a in agents.values():
        report_sync(a)
    devices["cam-SN0"].power_off()
    devices["cam-SN3"].boot()
    writes = _writes(devices)
    before = writes()

    new, report = move_domain(fed, "cam-SN1", offline, one.DOMAIN, one._objects(devices), wall)
    after = writes()
    assert report["term"] == 2 and report["record"]["holder"] == "cam-SN1"
    assert {n: after[n] for n in devices if n != "cam-SN1"} == {n: before[n] for n in devices if n != "cam-SN1"}
    assert after["cam-SN1"] != before["cam-SN1"]                         # its own: the record, the state, the keys

    keys = signer.tokens.keyset()
    for name in agents:
        assert _follows(agents, name, "cam-SN1"), (name, agents[name].followed)
        assert read_holder(devices[name].flash, keys, wall())["term"] == 2
    assert devices["cam-SN3"].row()["enabled"] is False            # carried from the new holder's door


def test_after_a_theft_the_move_writes_only_the_new_holder_and_the_members_follow_the_roots_term():
    """Step 9: SN0 is stolen and the domain is moved onto SN1 by the root's recovery file. The move signs a new key set
    and every LDevID again — all of it in SN1's store; the members' stores get nothing from it. Each member follows the
    record the ROOT signed for term 2 and carries the new key set home from SN1's door."""
    wall = Clock()
    fed, devices, root, holder, _, _ = rooted._site(wall)
    agents = {n: _follower(fed, devices, n, wall) for n in devices if n != "cam-SN0"}
    for a in agents.values():
        report_sync(a)
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door())
    for a in agents.values():
        report_sync(a)
    devices["cam-SN0"].power_off()
    writes = _writes(devices)
    before = writes()

    new, report = move_domain(fed, "cam-SN1", root.recovery(), rooted.DOMAIN, rooted._objects(devices), wall, stolen=True)
    after = writes()
    assert report["stolen"] and report["record"]["kid"] == "root"
    assert {n: after[n] for n in devices if n != "cam-SN1"} == {n: before[n] for n in devices if n != "cam-SN1"}

    from w2cplatform.domain.agent import ClusterTrust
    for name in agents:
        assert _follows(agents, name, "cam-SN1"), (name, agents[name].followed)
        keys = ClusterTrust(devices[name].flash).keyset()
        assert keys.rev == report["keys_rev"] and read_holder(devices[name].flash, keys, wall())["term"] == 2


def test_the_roots_record_of_a_move_by_the_file_names_the_new_holders_door_and_the_agents_go_there():
    """The scenario «камера — офис — центр», N4: a move by the recovery file wrote the record of term 2, signed by the
    root, with no `url` — the signer adds one only to a record it signs itself — so the agents took term 2 by
    `/api/held` and found no door in it: «the record names no door», and they carried on through the dead holder's.
    The root's record names the new holder's door now (the product's record always does, `HolderRecord.URL`); an agent
    whose only door is the record's `url` follows. Without a `url` given, the record names none, as before."""
    wall = Clock()
    fed, devices, root, holder, _, _ = rooted._site(wall)
    agents = {n: _by_url(fed, devices, n, wall) for n in devices if n != "cam-SN0"}
    for a in agents.values():
        report_sync(a)
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door())
    report_sync(rooted._agent(fed, devices, "cam-SN1", "cam-SN0", wall))
    devices["cam-SN0"].power_off()
    new, report = move_domain(fed, "cam-SN1", root.recovery(), rooted.DOMAIN, rooted._objects(devices), wall,
                              url="http://cam-SN1:8445")
    assert report["record"]["kid"] == "root" and report["record"]["url"] == "http://cam-SN1:8445", report["record"]
    for name in agents:
        assert _follows(agents, name, "cam-SN1"), (name, agents[name].followed)
        assert "following cam-SN1" in agents[name].followed, agents[name].followed

    wall = Clock()
    fed, devices, root, holder, _, _ = rooted._site(wall)
    lost = _by_url(fed, devices, "cam-SN2", wall)
    report_sync(lost)
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door())
    report_sync(rooted._agent(fed, devices, "cam-SN1", "cam-SN0", wall))
    devices["cam-SN0"].power_off()
    _, report = move_domain(fed, "cam-SN1", root.recovery(), rooted.DOMAIN, rooted._objects(devices), wall)
    assert "url" not in report["record"]
    assert not _follows({"cam-SN2": lost}, "cam-SN2", "cam-SN1") and "names no door" in lost.followed, lost.followed


def _door_site(wall):
    """`test_lesson15_root._site`, its members admitted with the keys their agents make (`MemberKey`: the signing key and
    the sealing key) — a member's agent asks the holder's DOOR (`carry.HolderDoor`), never its stores."""
    from w2cplatform.cluster.variables import FakeVariables
    from w2cplatform.domain.federation import Federation
    from w2cplatform.domain.members import Members
    from w2cplatform.domain.term import install
    from w2cplatform.trust.memberkey import MemberKey
    from w2cplatform.trust.signer import DomainRoot
    from tests.domain.conftest import EmbeddedMember
    fed, devices, keys = Federation(), {}, {}
    for i in range(4):
        d = EmbeddedMember(f"SN{i}", FakeVariables(), wall=wall)
        d.boot()
        devices[d.name] = d
        fed.add(d.cluster(domain=i == 0))
    root = DomainRoot(rooted.DOMAIN, now=wall)
    holder = install(fed, "cam-SN0", rooted.DOMAIN, root, wall=wall, objects=devices["cam-SN0"].disk)
    members = Members(holder.vars, wall)
    for name in devices:
        keys[name] = MemberKey.new()
        if name != "cam-SN0":
            members.add(name, "voucher", serial=name[4:], key=keys[name].pub, seal=keys[name].seal_pub)
        holder.signer.issue(name[4:], "ldevid", keys[name].signing.public_key())
    return fed, devices, root, holder, keys


def _through_doors(fed, devices, keys, name, wall):
    """A member's agent as `agent.main` builds it with `DOMAIN_URL`: it carries through the holder's door, follows the
    record's `url` (`http://<cluster>:8445` — that cluster's door here), and is given no holder objects to report into:
    its report goes through the door it carries through (`POST /api/member/<name>`)."""
    from w2cplatform.domain.carry import CarryClient, HolderDoor
    d = devices[name]
    ask = {n: (lambda n=n: held(n, fed.clusters[n].vars)) for n in devices}

    def door(n):
        return CarryClient(HolderDoor(fed.clusters[n].vars, devices[n].disk_door(), wall=wall), name, keys[name], wall)

    def open_door(rec):
        n = (rec.get("url") or "").removeprefix("http://").removesuffix(":8445")
        return (door(n), None) if n in fed.clusters else None
    return DomainAgent(name, door("cam-SN0"), d.flash, now=wall, console=device_console(d),
                       cluster_objects=d.disk, published=d.local_objects(), key=keys[name],
                       follow=HolderFollower(ask), open_door=open_door)


def test_after_a_move_by_the_file_a_members_report_goes_to_the_new_holders_door_and_none_to_the_old():
    """The scenario «камера — офис — центр», N5: after the domain moved, a member's agent carried its rows through the new
    holder's door and kept writing its report into the OLD holder's objects — set once when it started
    (`DOMAIN_OBJECTS_URL`) — so the new holder heard no member at all. The report goes through the door now, as the
    product's does (`POST /api/member/<m>`, signed `X-Agent-Signature`; ADR-0066), and follows the holder with the rows:
    after a move by the recovery file each member's report reaches the new holder, and not one more reaches the old."""
    from w2cplatform.domain.uplink import REPORTED, base
    from w2cplatform.domain.reports import read
    wall = Clock()
    fed, devices, root, holder, keys = _door_site(wall)
    agents = {n: _through_doors(fed, devices, keys, n, wall) for n in devices if n != "cam-SN0"}
    for a in agents.values():
        assert report_sync(a) and a.reported == "reported through the door", (a.cluster, a.reported, a.keys)
    old, new = devices["cam-SN0"].disk, devices["cam-SN1"].disk
    for name in agents:
        assert read(name, old).document()["key"] == keys[name].pub        # the door keeps it
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door())
    for a in agents.values():
        report_sync(a)
    before = {k: old.get(k) for k in old.list(base(""))}
    devices["cam-SN0"].power_off()
    _, moved = move_domain(fed, "cam-SN1", root.recovery(), rooted.DOMAIN, rooted._objects(devices), wall,
                           url="http://cam-SN1:8445")
    assert moved["term"] == 2 and moved["record"]["url"] == "http://cam-SN1:8445"
    for name in agents:
        assert _follows(agents, name, "cam-SN1"), (name, agents[name].followed)
    wall.advance(1)
    for name in ("cam-SN2", "cam-SN3"):
        a = agents[name]
        assert report_sync(a) and a.reported == "reported through the door", (name, a.reported)
        mark = json.loads(new.get(base(name) + REPORTED))
        assert read(name, new).document()["key"] == keys[name].pub and abs(mark["sent_at"] - wall()) < 1e-6, mark            # this pass's, at the new holder
    assert {k: old.get(k) for k in old.list(base(""))} == before                        # and nothing more at the old


def test_a_planned_handover_is_taken_by_the_target_and_the_outgoing_holder_writes_no_store_but_its_own():
    """SN0 hands the domain to SN1. SN0 freezes and seals its last backup in its own store; SN1's agent carries it; SN1
    takes the domain onto its own store (`take`). Every write into SN1's stores is SN1's own — its agent's or its move's —
    and SN2 and SN3 get none at all. SN0 reads the term SN1 claimed and steps down; the members follow SN1."""
    wall = Clock()
    fed, devices, signer, offline, holder, _ = one._site(wall)
    agents = {n: _follower(fed, devices, n, wall) for n in devices if n != "cam-SN0"}
    for a in agents.values():
        report_sync(a)
    writes = _writes(devices)
    by_target = []

    def as_target(fn):
        b = writes()
        out = fn()
        a = writes()
        by_target.append(tuple(x - y for x, y in zip(a["cam-SN1"], b["cam-SN1"])))
        return out

    before = writes()
    new, report = handover(holder, "cam-SN1", one._objects(devices),
                           lambda: as_target(lambda: report_sync(agents["cam-SN1"])),
                           lambda: as_target(lambda: move_domain(fed, "cam-SN1", offline, one.DOMAIN,
                                                                  one._objects(devices), wall)), wall)
    after = writes()
    assert report["planned"] and report["term"] == 2 and report["stranded"] == []
    assert holder.deposed_by["holder"] == "cam-SN1"
    for name in ("cam-SN2", "cam-SN3"):
        assert after[name] == before[name], name
    grew = tuple(x - y for x, y in zip(after["cam-SN1"], before["cam-SN1"]))
    assert grew == tuple(sum(c) for c in zip(*by_target)) and any(grew)    # all of it by SN1 itself
    for name in ("cam-SN2", "cam-SN3"):
        assert _follows(agents, name, "cam-SN1"), (name, agents[name].followed)


def test_a_forged_or_unsigned_larger_term_is_followed_by_nobody():
    """A cluster's console may say anything: SN2's store holds a record of term 9 signed by a key the domain never
    trusted, SN3's an unsigned one of term 10. Neither verifies against the key set SN1 carries, so SN1's agent keeps
    term 1 on SN0 and its door, and says which clusters it refused."""
    wall = Clock()
    fed, devices, signer, offline, holder, _ = one._site(wall)
    agents = {n: _follower(fed, devices, n, wall) for n in devices if n != "cam-SN0"}
    for a in agents.values():
        report_sync(a)
    forged = sign({"term": 9, "holder": "cam-SN2", "at": wall(), "url": "http://elsewhere:8445"}, TokenIssuer(one.DOMAIN))
    devices["cam-SN2"].flash.put(HOLDER, {"doc": json.dumps(forged, sort_keys=True)})
    devices["cam-SN3"].flash.put(HOLDER, {"doc": json.dumps({"term": 10, "holder": "cam-SN3", "at": wall()})})
    a = agents["cam-SN1"]
    for _ in range(POLLS + 1):
        assert report_sync(a)
    assert a.holder_at == "cam-SN0" and read_holder(devices["cam-SN1"].flash, signer.tokens.keyset(), wall())["term"] == 1
    assert "refused from cam-SN2, cam-SN3" in a.followed, a.followed


def test_held_says_the_record_the_key_set_and_which_backup_by_term_and_rev_and_nothing_of_its_content():
    """What a cluster's console answers at `/api/held`, for anybody: `{cluster, holder, term, keys, backup: {term, rev}}`
    — the record it holds and the key set it carries, both as signed, and which backup copy it keeps, by the pair its
    pointer is ordered by (a rev says nothing against another term's: ADR-0032); never the copy's content, which is the
    domain's state (`/api/backup`, a member's). No `{rev}` alone beside it (ADR-0003)."""
    wall = Clock()
    fed, devices, signer, offline, holder, agents = one._site(wall)
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door())
    report_sync(agents["cam-SN1"])
    said = held("cam-SN1", devices["cam-SN1"].flash)
    assert sorted(said) == ["backup", "cluster", "holder", "keys", "term"], said
    assert said["holder"]["term"] == said["term"] == 1 and said["holder"]["sig"] and said["backup"] == {"term": 1, "rev": 1}
    assert said["keys"]["current"] == signer.tokens.kid
    assert held("cam-SN2", devices["cam-SN2"].flash)["backup"] is None                 # keeps none
