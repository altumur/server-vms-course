"""Lesson 15 — the domain holder on one node.

`fed` below is the SITE — every camera through its door, what a camera on the site can reach. The domain on its
holder reads the other cameras only by their reports (`_domain`); the doors are used by cameras acting as cameras
(looking for the holder) and by the move, the one exception the lesson names.

A site of cameras and no server: the domain's services run on one camera. Moving them becomes an
ordinary operation — from the signer's key, kept beyond the holder since Lesson 7, and the newest signed copy
of the domain's state that other members keep — and it needs a term, so that a holder which comes back after
being replaced steps down instead of splitting the site in two.
"""
import json

from cluster.variables import FakeVariables

from domain.agent import DomainAgent, DomainPublisher
from domain.api import ApiError, ConsoleAPI
from domain.device import DeviceCluster
from domain.federation import DomainDirectory, Federation
from domain.grants import Grant
from domain.pending import PendingEdits
from domain.readview import ReadView
from domain.shared import sign
from domain.signer import Signer
from domain.term import (BACKUP, Deposed, DomainHolder, GuardedPending, carry_holder, find_holder, handover,
                         move_domain, read_holder, stranded)
from domain.tokens import TokenIssuer
from domain.federation import Unreachable
from domain.uplink import member_copy
from tests.conftest import Clock

DOMAIN = "acme"


def _site(wall, n=4):
    fed, devices = Federation(), {}
    for i in range(n):
        d = DeviceCluster(f"SN{i}", FakeVariables(), wall=wall)
        d.boot()
        devices[d.name] = d
        fed.add(d.cluster(domain=i == 0))
    home = fed.clusters["cam-SN0"].vars
    signer = Signer(DOMAIN, home, now=wall)
    offline = signer.backup()                            # Lesson 7: the key, kept beyond the holder
    DomainPublisher(home).publish_keys(signer.tokens.keyset())
    for name in devices:
        DomainPublisher(home).publish_grants(name, [Grant("anna", "edit", None, wall() + 30 * 86400)])
    holder = DomainHolder(fed, "cam-SN0", signer, term=1, wall=wall, objects=devices["cam-SN0"].disk)
    holder.claim()
    agents = {name: _agent(fed, devices, name, "cam-SN0", wall) for name in devices if name != "cam-SN0"}
    for a in agents.values():
        a.sync()
    return fed, devices, signer, offline, holder, agents


def _agent(fed, devices, name, holder, wall):
    d = devices[name]
    return DomainAgent(name, fed.clusters[holder].vars, d.flash, now=wall, console=d.local_console(), current=d.current,
                       domain_objects=devices[holder].disk_door(), cluster_objects=d.disk, published=d.local_objects())


def _domain(devices, holder, wall):
    """What the domain on `holder` reads: itself, and every other camera by the report its agent left here."""
    fed = Federation()
    fed.add(devices[holder].cluster(domain=True))
    for name in devices:
        if name != holder:
            fed.add(member_copy(name, devices[holder].disk, wall=wall))
    return fed


def _no_door(name):
    raise Unreachable(f"{name} is reached only by its own agent: the edit is kept")


def _keep_an_edit_for(fed, devices, camera, holder_vars, wall, holder="cam-SN0"):
    dom = _domain(devices, holder, wall)
    view = ReadView(dom, wall=wall)
    view.refresh()
    devices[f"cam-{camera}"].power_off()
    view.refresh()
    api = ConsoleAPI(DomainDirectory(dom, wall=wall), _no_door, verifier=lambda t: t,
                     pending=PendingEdits(holder_vars, wall), last_known=view.last_known)
    return api.update_camera(camera, {"name": f"{camera}-renamed"}, idempotency_key=f"k-{camera}", token="anna")


def _objects(devices):
    return lambda name: devices[name].disk_door()


def test_the_holder_dies_and_the_domain_is_moved_with_the_edit_it_was_keeping():
    """SN3 is off and the domain on SN0 is keeping an edit for it — the one piece of state that, by
    definition, is on no camera that could carry it home. SN0 published a signed backup to SN1 and SN2.
    Then SN0 dies. The operator moves the domain to SN1 from the signer's key: term 2, the newest backup any member
    holds, and the kept edit with it. SN3 boots, its agent finds the holder with the larger term, and the
    edit lands."""
    wall = Clock()
    fed, devices, signer, offline, holder, agents = _site(wall)
    assert _keep_an_edit_for(fed, devices, "SN3", holder.vars, wall)["pending"]
    assert holder.backup(["cam-SN1", "cam-SN2"], devices["cam-SN0"].disk_door()) == 1
    agents["cam-SN1"].sync(); agents["cam-SN2"].sync()
    devices["cam-SN0"].power_off()                       # for good: flash worn out

    new, report = move_domain(fed, "cam-SN1", offline, DOMAIN, _objects(devices), wall)
    assert (report["term"], report["rev"]) == (2, 1) and report["restored_from"] in ("cam-SN1", "cam-SN2")
    assert "SN3" in PendingEdits(new.vars, wall).of("cam-SN3")
    assert fed.domain_holder.name == "cam-SN1"

    d3 = devices["cam-SN3"]
    d3.boot()
    keys = signer.tokens.keyset()
    assert find_holder(fed, d3.flash, keys, wall()) == "cam-SN1"
    _agent(fed, devices, "cam-SN3", "cam-SN1", wall).sync()
    assert d3.row()["name"] == "SN3-renamed"


def test_a_holder_record_is_never_carried_backwards():
    """The old holder comes back and an agent still pointed at it carries its record. Carried blindly, term 1
    would overwrite term 2 on every member that agent reached and undo the move. The record is carried
    like the keys, with one more rule: never to a smaller term."""
    wall = Clock()
    fed, devices, signer, offline, holder, agents = _site(wall)
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door()); agents["cam-SN1"].sync()
    devices["cam-SN0"].power_off()
    move_domain(fed, "cam-SN1", offline, DOMAIN, _objects(devices), wall)
    d2 = devices["cam-SN2"]
    _agent(fed, devices, "cam-SN2", "cam-SN1", wall).sync()
    keys = signer.tokens.keyset()
    assert read_holder(d2.flash, keys, wall())["term"] == 2

    devices["cam-SN0"].boot()                            # the old holder is back, still claiming term 1
    assert carry_holder(fed.clusters["cam-SN0"].vars, d2.flash, keys, wall()) == "holding a larger term"
    assert read_holder(d2.flash, keys, wall())["term"] == 2
    assert find_holder(fed, d2.flash, keys, wall()) == "cam-SN1"


def test_an_old_holder_that_comes_back_steps_down_and_lists_what_it_alone_holds():
    """SN0 kept an edit for SN2 AFTER its last backup, then died. The new term does not have it and cannot:
    it was on no other camera. When SN0 comes back it reads a larger term on a member and steps down — its
    writes refused, saying where they go — and what it alone held is listed for a person, not dropped and
    not re-applied by itself."""
    wall = Clock()
    fed, devices, signer, offline, holder, agents = _site(wall)
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door()); agents["cam-SN1"].sync()
    _keep_an_edit_for(fed, devices, "SN2", holder.vars, wall)          # after the backup
    devices["cam-SN0"].power_off()
    new, report = move_domain(fed, "cam-SN1", offline, DOMAIN, _objects(devices), wall)
    _agent(fed, devices, "cam-SN3", "cam-SN1", wall).sync()          # a member now carries term 2

    devices["cam-SN0"].boot()
    assert holder.check() is False
    try:
        holder.backup(["cam-SN3"], devices["cam-SN0"].disk_door())
        raise AssertionError("a deposed holder must not publish")
    except Deposed as e:
        assert "cam-SN1" in str(e) and "term 2" in str(e)
    left = stranded(fed.clusters["cam-SN0"].vars, report["state"])
    assert [(p, k) for p, k, _ in left] == [("domain/pending/cam-SN2", "SN2")]
    assert json.loads(left[0][2])["fields"]["name"]["new"] == "SN2-renamed"


def test_a_backup_not_signed_by_the_domain_is_ignored_however_new_it_claims_to_be():
    wall = Clock()
    fed, devices, signer, offline, holder, agents = _site(wall)
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door()); agents["cam-SN1"].sync()
    forged = sign({"term": 9, "rev": 99, "host": "cam-SN2", "state": {"domain/grants/cam-SN3": {"mallory": "admin"}}},
                  TokenIssuer(DOMAIN))
    devices["cam-SN2"].disk.put(BACKUP, json.dumps(forged).encode())
    devices["cam-SN2"].flash.put(BACKUP, {"rev": 99, "term": 9, "sha256": "x"})
    devices["cam-SN0"].power_off()
    new, report = move_domain(fed, "cam-SN1", offline, DOMAIN, _objects(devices), wall)
    assert report["restored_from"] == "cam-SN1" and report["rev"] == 1 and report["term"] == 2
    assert [n for n, _ in report["ignored"]] == ["cam-SN2"]


def test_a_holder_restored_without_the_signers_key_is_followed_by_nobody():
    """The signer's key is the one thing never in the backup, and this is why. A holder set up from any other
    key finds no backup that verifies, and its claim verifies on no member: every agent stays where it
    was. Losing that key does not lose the site — it loses the ability to move the domain."""
    wall = Clock()
    fed, devices, signer, offline, holder, agents = _site(wall)
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door()); agents["cam-SN1"].sync()
    devices["cam-SN0"].power_off()
    wrong = Signer(DOMAIN, FakeVariables(), now=wall).backup()
    impostor, report = move_domain(fed, "cam-SN2", wrong, DOMAIN, _objects(devices), wall)
    assert report["restored_from"] is None and [n for n, _ in report["ignored"]] == ["cam-SN1"]
    keys = signer.tokens.keyset()
    assert find_holder(fed, devices["cam-SN3"].flash, keys, wall()) == "cam-SN0"      # still the old holder, off, waited for


def test_every_move_takes_a_larger_term_than_any_member_has_seen():
    """Twice in a month: SN0 dies, the domain goes to SN1 at term 2; SN1 is stolen, it goes to SN2. The new
    term is one more than the largest ANY reachable member carries — 3, not 2 again — or the holder that
    comes back from the first move would tie with the second and nothing could tell them apart."""
    wall = Clock()
    fed, devices, signer, offline, holder, agents = _site(wall)
    holder.backup(["cam-SN1", "cam-SN2"], devices["cam-SN0"].disk_door())
    agents["cam-SN1"].sync(); agents["cam-SN2"].sync()
    devices["cam-SN0"].power_off()
    second, _ = move_domain(fed, "cam-SN1", offline, DOMAIN, _objects(devices), wall)
    for name in ("cam-SN2", "cam-SN3"):
        _agent(fed, devices, name, "cam-SN1", wall).sync()
    devices["cam-SN1"].power_off()
    third, report = move_domain(fed, "cam-SN2", offline, DOMAIN, _objects(devices), wall)
    assert report["term"] == 3
    _agent(fed, devices, "cam-SN3", "cam-SN2", wall).sync()
    devices["cam-SN1"].boot()
    assert second.check() is False and find_holder(fed, devices["cam-SN3"].flash, signer.tokens.keyset(), wall()) == "cam-SN2"


def test_a_planned_handover_strands_nothing():
    """SN0 is alive and being replaced; the operator moves the domain to SN1. The emergency path would work
    and could strand whatever SN0 changed after its last backup. The planned one cannot: SN0 freezes —
    an edit arriving in those seconds is refused with the reason, not accepted into a gap — makes its last
    backup to SN1, SN1's agent takes it, and the move restores from a copy that has everything. SN0,
    still reachable, reads the larger term and steps down, and the report says nothing was stranded."""
    wall = Clock()
    fed, devices, signer, offline, holder, agents = _site(wall)
    _keep_an_edit_for(fed, devices, "SN3", holder.vars, wall)          # kept before the handover: must travel

    dom = _domain(devices, "cam-SN0", wall)
    view = ReadView(dom, wall=wall)
    view.refresh()
    devices["cam-SN2"].power_off()
    view.refresh()
    api = ConsoleAPI(DomainDirectory(dom, wall=wall), _no_door, verifier=lambda t: t,
                     pending=GuardedPending(PendingEdits(holder.vars, wall), holder), last_known=view.last_known)

    def carry_to():
        try:                                             # the moment an operator edits during the handover
            api.update_camera("SN2", {"name": "late"}, idempotency_key="k-late", token="anna")
            raise AssertionError("a frozen holder must refuse the edit")
        except ApiError as e:
            assert e.status == 503 and "handing the domain over to cam-SN1" in e.detail
        agents["cam-SN1"].sync()

    new, report = handover(holder, "cam-SN1", offline, DOMAIN, _objects(devices), carry_to, wall)
    assert report["planned"] and report["stranded"] == [] and report["term"] == 2
    assert report["sentence"].endswith("nothing stranded")
    assert "SN3" in PendingEdits(new.vars, wall).of("cam-SN3")
    assert holder.deposed_by["host"] == "cam-SN1" and fed.domain_holder.name == "cam-SN1"


def test_a_handover_the_target_did_not_take_is_called_off_and_changes_nothing():
    """SN1's agent could not take the last backup — SN1 went off in the middle. Moving now would start
    the new term from an older copy, which is the emergency path's loss taken on for no emergency. So the
    handover is called off: SN0 unfreezes and is still the holder at term 1, and no member carries anything
    new."""
    wall = Clock()
    fed, devices, signer, offline, holder, agents = _site(wall)

    def carry_to():
        devices["cam-SN1"].power_off()                   # and its agent with it: no report of the backup comes

    try:
        handover(holder, "cam-SN1", offline, DOMAIN, _objects(devices), carry_to, wall)
        raise AssertionError("the handover must be called off")
    except RuntimeError as e:
        assert "called off" in str(e)
    assert holder.frozen_for is None and holder.term == 1 and fed.domain_holder.name == "cam-SN0"
    holder.guard()                                         # writes are accepted again
    keys = signer.tokens.keyset()
    assert read_holder(devices["cam-SN3"].flash, keys, wall())["term"] == 1


def test_a_write_that_slips_past_the_freeze_is_reported_not_trusted_away():
    """"Nothing stranded" is checked, not asserted. A path that writes the domain's state without asking the
    holder's guard — a bug, a second process — is exactly what the freeze cannot stop, and the report finds it:
    the handover says how many items were stranded, and `stranded` names them."""
    wall = Clock()
    fed, devices, signer, offline, holder, agents = _site(wall)

    def carry_to():
        PendingEdits(holder.vars, wall).add("cam-SN2", "SN2", {"name": "sneaked"}, {"name": "SN2"}, "anna")   # no guard
        agents["cam-SN1"].sync()

    new, report = handover(holder, "cam-SN1", offline, DOMAIN, _objects(devices), carry_to, wall)
    assert [(p, k) for p, k, _ in report["stranded"]] == [("domain/pending/cam-SN2", "SN2")]
    assert "1 item(s) stranded" in report["sentence"]


# -- feedback AS ------------------------------------------------------------------------------------------------
def test_a_move_keeps_the_topology_the_members_and_the_roads():
    """The first backup stopped at Lesson 14. A move then lost every chain through a relay (the topology of
    Lesson 17), every road a recorder had said it could not pull (Lesson 16 — a push became a pull again), and the
    list of members — which, if nobody had ever written it, was the configuration of the old holder's processes and
    nothing else. They travel now, and the list is written by the first backup so that there is one to carry."""
    from domain.members import Members
    wall = Clock()
    fed, devices, signer, offline, holder, agents = _site(wall)
    topology = {"doc": json.dumps({"rev": 1, "centre": None, "star": [], "via": {"cam-SN3": "cam-SN2"}})}
    roads = {"SN3": json.dumps({"road": "push", "why": "the recorder could not open its stream"})}
    holder.vars.put("domain/topology", topology)
    holder.vars.put("domain/roads", roads)
    assert holder.vars.get("domain/members")[0] is None                   # never written: configuration only
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door()); agents["cam-SN1"].sync()
    assert Members(holder.vars).names() == ["cam-SN0", "cam-SN1", "cam-SN2", "cam-SN3"]   # the backup wrote it first
    devices["cam-SN0"].power_off()
    new, report = move_domain(fed, "cam-SN1", offline, DOMAIN, _objects(devices), wall)
    assert new.vars.get("domain/topology")[0] == topology and new.vars.get("domain/roads")[0] == roads
    assert Members(new.vars).names() == ["cam-SN0", "cam-SN1", "cam-SN2", "cam-SN3"]   # the old holder: a member now


def test_a_report_that_closes_an_edit_during_a_handover_is_not_stranded():
    """Only adding an edit is guarded by the freeze. A member's report goes on during the handover and closes
    part of an edit the last backup still holds as waiting — here it marks a conflict. That is the camera's news,
    not the operator's decision: the new term carries the same edit again and the camera answers the same. So
    the handover strands nothing, and the edit waits in the new term (feedback AS)."""
    wall = Clock()
    fed, devices, signer, offline, holder, agents = _site(wall)
    _keep_an_edit_for(fed, devices, "SN3", holder.vars, wall)
    rev = PendingEdits(holder.vars, wall).of("cam-SN3")["SN3"]["rev"]

    def carry_to():
        PendingEdits(holder.vars, wall).reconcile("cam-SN3", {"SN3": {"rev": rev, "conflicts": {"name": {"current": "x"}}}})
        agents["cam-SN1"].sync()

    new, report = handover(holder, "cam-SN1", offline, DOMAIN, _objects(devices), carry_to, wall)
    assert report["stranded"] == [] and report["sentence"].endswith("nothing stranded")
    assert PendingEdits(new.vars, wall).of("cam-SN3")["SN3"]["rev"] == rev


def test_an_old_holder_that_learns_of_two_moves_from_its_own_agent_starts_deposed_and_keeps_its_list():
    """SN0 kept an edit for SN2 after its last backup and died; the domain was moved twice, to term 3. SN0
    comes back behind closed neighbours' doors, and its own agent carries term 3 home before the holder process
    starts. The process looks before it claims: it starts deposed, never writes term 1 over term 3 in its own
    store, and decides what it alone held ONCE — against its own last backup, since term 3 was restored from
    somebody else's — and keeps that list (feedback AS)."""
    wall = Clock()
    fed, devices, signer, offline, holder, agents = _site(wall)
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door()); agents["cam-SN1"].sync()
    _keep_an_edit_for(fed, devices, "SN2", holder.vars, wall)             # after the last backup
    devices["cam-SN0"].power_off()
    second, _ = move_domain(fed, "cam-SN1", offline, DOMAIN, _objects(devices), wall)
    devices["cam-SN2"].boot()
    _agent(fed, devices, "cam-SN2", "cam-SN1", wall).sync()
    second.backup(["cam-SN2"], devices["cam-SN1"].disk_door())
    _agent(fed, devices, "cam-SN2", "cam-SN1", wall).sync()
    devices["cam-SN1"].power_off()
    third, report = move_domain(fed, "cam-SN2", offline, DOMAIN, _objects(devices), wall)
    assert report["term"] == 3

    devices["cam-SN0"].boot()
    _agent(fed, devices, "cam-SN0", "cam-SN2", wall).sync()             # its own agent: term 3, carried home
    for name in ("cam-SN2", "cam-SN3"):
        devices[name].door_open = False                                  # and no neighbour's door to look through
    old = DomainHolder(fed, "cam-SN0", signer, term=1, wall=wall, objects=devices["cam-SN0"].disk)   # a fresh process
    assert old.start() is False
    assert old.deposed_by["term"] == 3 and read_holder(devices["cam-SN0"].flash, signer.tokens.keyset(), wall())["term"] == 3
    kept = old.stranded_items()
    assert kept["base"] == "its own last backup, rev 1" and [(p, k) for p, k, _ in kept["items"]] == [("domain/pending/cam-SN2", "SN2")]

    PendingEdits(old.vars, wall).add("cam-SN3", "SN3", {"name": "later"}, {"name": "SN3"}, "anna")   # a write past it
    old.check()
    assert old.stranded_items() == kept                                  # decided once, not re-decided
