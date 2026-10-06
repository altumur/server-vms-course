"""Lesson 15 — the members follow the holder by themselves («Архитектор», 2026-10-06; ADR 0001 §1.12).

A move writes the new holder's own store and nobody else's: its term record, signed, the state it restored, its keys.
No member is told. Each member's agent asks every cluster of the domain for the holder's record that cluster holds —
`GET /api/held` at its console (`term.held`); here a cluster's store read through its door, which is what its console
reads — and follows the greatest term that verifies against the key set the member carries (`agent.HolderFollower`).
A planned handover is the same rule from the other side: the target takes the domain onto its own store, and the
outgoing holder writes none but its own.
"""
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
    return DomainAgent(name, fed.clusters[holder].vars, d.flash, now=wall, console=d.local_console(), current=d.current,
                       domain_objects=devices[holder].disk_door(), cluster_objects=d.disk, published=d.local_objects(),
                       follow=HolderFollower(ask), open_door=open_door)


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
        a.sync()
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
        a.sync()
    assert one._keep_an_edit_for(fed, devices, "SN3", holder.vars, wall)["pending"]
    holder.backup(["cam-SN1", "cam-SN2"], devices["cam-SN0"].disk_door())
    for a in agents.values():
        a.sync()
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
    assert devices["cam-SN3"].row()["name"] == "SN3-renamed"            # carried from the new holder's door


def test_after_a_theft_the_move_writes_only_the_new_holder_and_the_members_follow_the_roots_term():
    """Step 9: SN0 is stolen and the domain is moved onto SN1 by the root's recovery file. The move signs a new key set
    and every LDevID again — all of it in SN1's store; the members' stores get nothing from it. Each member follows the
    record the ROOT signed for term 2 and carries the new key set home from SN1's door."""
    wall = Clock()
    fed, devices, root, holder, _, _ = rooted._site(wall)
    agents = {n: _follower(fed, devices, n, wall) for n in devices if n != "cam-SN0"}
    for a in agents.values():
        a.sync()
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door())
    for a in agents.values():
        a.sync()
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


def test_a_planned_handover_is_taken_by_the_target_and_the_outgoing_holder_writes_no_store_but_its_own():
    """SN0 hands the domain to SN1. SN0 freezes and seals its last backup in its own store; SN1's agent carries it; SN1
    takes the domain onto its own store (`take`). Every write into SN1's stores is SN1's own — its agent's or its move's —
    and SN2 and SN3 get none at all. SN0 reads the term SN1 claimed and steps down; the members follow SN1."""
    wall = Clock()
    fed, devices, signer, offline, holder, _ = one._site(wall)
    agents = {n: _follower(fed, devices, n, wall) for n in devices if n != "cam-SN0"}
    for a in agents.values():
        a.sync()
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
                           lambda: as_target(agents["cam-SN1"].sync),
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
        a.sync()
    forged = sign({"term": 9, "holder": "cam-SN2", "at": wall(), "url": "http://elsewhere:8445"}, TokenIssuer(one.DOMAIN))
    devices["cam-SN2"].flash.put(HOLDER, {"doc": json.dumps(forged, sort_keys=True)})
    devices["cam-SN3"].flash.put(HOLDER, {"doc": json.dumps({"term": 10, "holder": "cam-SN3", "at": wall()})})
    a = agents["cam-SN1"]
    for _ in range(POLLS + 1):
        assert a.sync()
    assert a.holder_at == "cam-SN0" and read_holder(devices["cam-SN1"].flash, signer.tokens.keyset(), wall())["term"] == 1
    assert "refused from cam-SN2, cam-SN3" in a.followed, a.followed


def test_held_says_the_record_the_key_set_and_the_number_of_the_backup_and_nothing_of_its_content():
    """What a cluster's console answers at `/api/held`, for anybody: `{cluster, holder, term, keys, backup: {rev}}` —
    the record it holds and the key set it carries, both as signed, and the number of the backup copy it keeps; never
    the copy's content, which is the domain's state (`/api/backup`, a member's)."""
    wall = Clock()
    fed, devices, signer, offline, holder, agents = one._site(wall)
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door())
    agents["cam-SN1"].sync()
    said = held("cam-SN1", devices["cam-SN1"].flash)
    assert sorted(said) == ["backup", "cluster", "holder", "keys", "term"], said
    assert said["holder"]["term"] == said["term"] == 1 and said["holder"]["sig"] and said["backup"] == {"rev": 1}
    assert said["keys"]["current"] == signer.tokens.kid
    assert held("cam-SN2", devices["cam-SN2"].flash)["backup"] is None                 # keeps none
