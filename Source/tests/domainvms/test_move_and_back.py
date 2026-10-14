"""A move and a move back (ADR-0066's addition of 2026-10-11, «Сборка»'s drill on the stand): the domain moves from
srv to relay-a, the state changes on relay-a and its copy goes to relay-b; relay-a is gone, and the domain moves back
to srv. On the stand every neighbour answered srv 403 — the former holder was on no list of members — and srv was
restored from its own old copy: the domain's state rolled back, said by nobody. Two rules, as the product's: the holder
and the former holder are always on the list of members; and a move refuses when it cannot read a copy newer than the
one it would restore from, which it learns of by the public pointers (`/api/held`) — the older copy only by the
operator's explicit word — a copy named (`copy: {term, rev}` with `why`) or `stolen` — written into the journal.

Three clusters on files, each with its console (the processes' doors, `/api/held` and `/api/backup`), the holder's
signer moving the domain at its door (`Holder.move`, as `POST /domain/move` hands it on); every holder installed as a
holder is (`term.install`, with no member key handed in: its agent made one on its box)."""

from tests.reporting import sync as report_sync
import json
import os
import tempfile

from vms.config import SPEC
from w2cplatform.console import Mount, SpecConsole
from w2cplatform.domain.agent import DomainAgent, DomainPublisher
from w2cplatform.domain.federation import Cluster, Federation
from w2cplatform.domain.grants import Grant, grants_from_items
from w2cplatform.domain.members import Members
from w2cplatform.domain.signer_service import Holder
from w2cplatform.domain.term import MEMBER_LIST, install
from w2cplatform.objects import FsObjectStore
from w2cplatform.spec import SpecController
from w2cplatform.trust.memberkey import MemberKey
from w2cplatform.trust.signer import DomainRoot, Signer
from w2cplatform.variables import FileVariables
from tests.domain.conftest import Clock

DOMAIN = "acme"
NAMES = ("srv", "relay-a", "relay-b", "relay-c")
GONE = "http://127.0.0.1:9"                      # a console that does not answer: its box is off


class Site:
    def __init__(self):
        self.wall = wall = Clock(1_760_000_000.0)
        self.c = {}
        for n in NAMES:
            root = tempfile.mkdtemp(prefix=f"mb-{n}-")
            self.c[n] = Cluster(n, FileVariables(os.path.join(root, "config"), volatile=True),
                                FsObjectStore(os.path.join(root, "objects")))
        self.keys = {n: MemberKey.load_or_make(self.c[n].vars) for n in NAMES}   # each box's agent made its key
        fed = Federation()
        for n in NAMES:
            fed.add(self.c[n])
        self.c["srv"].is_domain_holder = True
        self.root = DomainRoot(DOMAIN, now=wall)
        self.recovery = self.root.recovery().decode()
        self.holder = install(fed, "srv", DOMAIN, self.root, wall=wall, objects=self.c["srv"].objects)
        for n in ("relay-a", "relay-b", "relay-c"):
            Members(self.c["srv"].vars, wall, domain="srv").add(n, "voucher", key=self.keys[n].pub,
                                                                  seal=self.keys[n].seal_pub)
        from tests.domain.books_fixture import initial_books
        initial_books(fed, self.holder.signer, wall,
                      {n: (c.vars, c.objects) for n, c in self.c.items()})
        self.grant("srv", "anna")
        self.consoles = {}

    def grant(self, holder: str, who: str) -> None:
        DomainPublisher(self.c[holder].vars).publish_grants("relay-b", [Grant(who, "view", None, self.wall() + 86400)])

    def grants(self, holder: str) -> set:
        return {g.subject for g in grants_from_items(self.c[holder].vars.get("domain/grants/relay-b")[0] or {})}

    def carry(self, holder: str, *members: str) -> None:
        """Each member's agent carries from `holder`'s store: its copy of the backup, its list of members."""
        h = self.c[holder]
        for n in members:
            assert report_sync(DomainAgent(n, h.vars, self.c[n].vars, now=self.wall, domain_objects=h.objects,
                               cluster_objects=self.c[n].objects)), n

    def console(self, n: str) -> str:
        if n not in self.consoles:
            c = self.c[n]
            srv = Mount(SpecConsole(SpecController(SPEC, c.vars, c.objects, wall=self.wall, cluster=n),
                                    wall=self.wall)).serve("127.0.0.1", 0)
            self.consoles[n] = (srv, f"http://127.0.0.1:{srv.server_address[1]}")
        return self.consoles[n][1]

    def signer(self, at: str, gone: str, journal=None) -> Holder:
        """`at`'s signer, its box's own: the domain read by `at` itself and the others by their consoles, `gone` off."""
        mine = Federation()
        me = self.c[at]
        mine.add(Cluster(at, me.vars, me.objects, is_domain_holder=True))
        consoles = {n: (GONE if n == gone else self.console(n)) for n in NAMES if n != at}
        return Holder(me.vars, me.objects, Signer(DOMAIN, me.vars, now=self.wall), fed=mine, wall=self.wall,
                      consoles=consoles, journal=journal)

    def close(self):
        for srv, _ in self.consoles.values():
            srv.shutdown()
            srv.server_close()


class Lines:
    def __init__(self):
        self.lines = []

    def say(self, kind, cls="observation", **fields):
        self.lines.append((kind, fields))


def _moved_to_relay_a_and_on(s: Site):
    """The drill (`_notes-ru/drills/2026-10-11-move-rollback.md`) on three members and a holder: srv backs up to every
    relay (term 1) and goes; the domain moves to relay-a from a neighbour's copy; relay-a decides more (boris) and backs
    it up to relay-b alone (term 2), which carries it home; relay-c keeps the copy of term 1. Then relay-a goes too."""
    first = s.holder.backup(["relay-a", "relay-b", "relay-c"], s.c["srv"].objects)
    s.carry("srv", "relay-a", "relay-b", "relay-c")
    a = s.signer("relay-a", gone="srv")
    st, report = a.move({"recovery": s.recovery})
    assert st == 200 and report["term"] == 2, report
    assert s.grants("relay-a") == {"anna"}
    s.wall.advance(60)
    s.grant("relay-a", "boris")                              # what the domain decided after the move
    newer = a.term.backup(["relay-b"], s.c["relay-a"].objects)
    s.carry("relay-a", "relay-b")
    return {"term": 1, "rev": first}, {"term": 2, "rev": newer}


def test_the_domain_moves_back_to_its_former_holder_from_the_newest_copy_and_never_rolls_back():
    """The return finds the newest copy and takes it: srv, the former holder, is on relay-b's list — relay-a listed
    itself and kept srv when it took the domain — and relay-b gives srv its copy. Before the rules every neighbour
    answered srv 403 and srv started from what it had («no backup could be reached»): the state of term 1."""
    s = Site()
    try:
        _, newer = _moved_to_relay_a_and_on(s)
        listed = Members(s.c["relay-a"].vars).read()["members"]
        assert listed["srv"].get("key") == s.keys["srv"].pub, listed.get("srv")          # the holder it replaced, kept
        assert listed["relay-a"].get("key") == s.keys["relay-a"].pub, listed.get("relay-a")   # the holder itself
        srv = s.signer("srv", gone="relay-a")
        st, report = srv.move({"recovery": s.recovery})
        assert st == 200, report
        assert report["term"] == 3 and report["restored_from"] == "relay-b" and report["rev"] == newer["rev"], report
        assert s.grants("srv") == {"boris"}, s.grants("srv")      # the newest state, not srv's own of term 1
        listed = Members(s.c["srv"].vars).read()["members"]
        assert listed["srv"].get("key") == s.keys["srv"].pub and listed["relay-a"].get("key") == s.keys["relay-a"].pub
    finally:
        s.close()


def test_a_move_that_cannot_read_a_newer_copy_a_neighbour_announces_refuses_and_a_copy_named_with_why_is_restored():
    """relay-b keeps the newest copy and will not give it to srv (its list does not know srv: 403), though its
    `/api/held` says which it keeps; relay-c gives the older one. Without a word the move is refused — 409, who keeps
    what and why it did not give it, nothing restored; `copy: {term, rev}` without `why` is 400; a copy nobody gives is
    409; the older copy named, with why, is restored exactly, and the journal says so (`domain.moved`, copy, why)."""
    s = Site()
    try:
        older, newer = _moved_to_relay_a_and_on(s)
        items, _ = s.c["relay-b"].vars.get(MEMBER_LIST)
        doc = json.loads(items["doc"])
        doc["members"].pop("srv", None)
        s.c["relay-b"].vars.put(MEMBER_LIST, {"doc": json.dumps(doc)})
        lines = Lines()
        srv = s.signer("srv", gone="relay-a", journal=lines)
        st, said = srv.move({"recovery": s.recovery})
        assert st == 409 and said["detail"].startswith("the domain was not moved: nothing was restored: the newest copy "
                                                       f"this move could read is term 1 rev {older['rev']}"), said
        assert f"relay-b keeps term 2 rev {newer['rev']} and did not give it" in said["detail"], said
        assert "would roll the domain back" in said["detail"] and "(copy: {term, rev}) and say why" in said["detail"]
        assert srv.term is None and s.grants("srv") == {"anna"}               # nothing moved, nothing rolled back
        assert srv.move({"recovery": s.recovery, "copy": older})[0] == 400        # a copy named, and no why
        st, said = srv.move({"recovery": s.recovery, "copy": {"term": 1, "rev": 99}, "why": "a typo"})
        assert st == 409 and "no neighbour gave the copy named, term 1 rev 99" in said["detail"], said
        why = "relay-b is away for the week; the decision after term 2 is taken again by hand"
        st, report = srv.move({"recovery": s.recovery, "copy": older, "why": why})
        assert st == 200 and report["term"] == 3 and report["rev"] == older["rev"], report
        kind, fields = lines.lines[-1]
        assert kind == "domain.moved" and fields["copy"] == {"term": 1, "rev": older["rev"]} and fields["why"] == why, lines.lines
        assert fields["restored_term"] == 1 and fields["restored_rev"] == older["rev"] and fields["stolen"] is False
    finally:
        s.close()
