"""Lesson 15 — the domain holder on one node.

A site of small boxes and no server. The domain still has to run somewhere — the signer, the console, the
kept edits, the shared settings — and this module decided long ago where: in ONE designated cluster, with
nothing to fail over to, its key backed up beyond it (Lessons 4 and 7). On a server room that was a drill
done once a year. On a small box it is a Tuesday: boxes are unplugged, their flash wears out, they are
stolen. So moving the domain has to become an ordinary operation, and three things follow.

    a term          the holder has a number, and every move takes a larger one. A holder that comes back
                    after being replaced sees a larger term on any member and steps down: its writes are
                    refused, and it says to whom they go. The epoch of Lesson 1 of М10A, one level up —
                    and, as there, the loser finds out on its next read, not from a message
    beyond itself   what the domain holds that nobody else does is published to other members, signed, as
                    the shared settings are (Lesson 12). Much of its state already lives on members — each
                    cluster's grants in that cluster — but not all of it: the edit kept for a member that is
                    OFF (Lesson 9) is, by definition, on no member that could carry it home. A domain whose
                    holder dies takes those with it unless it published them
    stranded        an old holder that returns may have made changes after its last backup. They are not
                    silently lost and not silently applied: they are listed, for a person, as "not in term
                    N+1 — apply again?"

    domain/holder                 in the holder's Variables, and carried to every member: {term, holder, from}, signed —
                                `from`: the backup {term, rev} this term was restored from
    domain/backup/<member>      in the holder's Variables: a pointer, for each member chosen to keep a copy
    backup/rev-<n>              in the holder's durable objects: the signed state
    domain/backup               in a chosen member: its agent's copy of the pointer, and of the document
    domain/stranded             in a DEPOSED holder's Variables: what it alone held, decided once, when it stepped down

Who opens which connection (Lesson 10, step 7). The holder reads the other members only by their REPORTS, left
in its own store by their agents (`reported`) — a planned handover sees that the target took the last backup
in the target's report, never by calling it. The site's doors are used only by a member acting as a member:
one that boots and looks for the holder (`find_holder`), an old holder that comes back and looks whether it still is
one (`check`), and the operator moving the domain to a member, which reads its neighbours for the newest backup and
the largest term (`move_domain`) — the one exception the lesson names, because the holder that would have held the
reports is the one that is gone. That move is the new holder's signer's operation (`signer_service.Holder.move`,
`POST /api/move`, which `w2cctl domain move` calls), checked by the recovery file.

ONE WRITER PER STORE, A MOVE INCLUDED (ADR 0001 §1.12; «Архитектор» 2026-10-06). A move writes the new holder's own
store and nothing else — its term record, signed, the state it restored, its keys. Nobody tells the members: each
member's agent FOLLOWS the holder by itself (`agent.HolderFollower`). It asks the console of every cluster `CLUSTERS`
names for the holder's record that cluster holds (`GET /api/held`, `held`), and follows the greatest term that verifies
against the key set it carries — a record is signed, so whichever cluster says it, nobody can forge a larger one. A
planned handover is the same rule from the other side: the outgoing holder freezes and seals its last backup in its
own store; the TARGET takes the domain onto its own store (`POST /api/prepare`, `POST /api/take` at its signer,
`signer_service.Holder.take`) — the outgoing holder never writes the target's store.

What is NOT in the backup: the signer's key. It is the one thing that must never sit beside the rest, and it
is restored from where Lesson 7 put it — offline, or in the recovery file the installer handed over. Without
it no backup verifies and no member follows the new holder, which is the point.
"""
from __future__ import annotations

import json
import time

from .agent import DomainPublisher
from .alarms import HISTORY
from w2cplatform.rows import PARSE_ERRORS
from w2cplatform.secrets import is_secret_field

from w2cplatform.trust.documents import NotTaken, sign, verify
from w2cplatform.trust.signer import DomainRoot, Signer, is_recovery_file
from w2cplatform.trust.tokens import ROOT_KID, KeySet

from . import declared
from .federation import Unreachable
# A record, a backup or a key set that a member, a peer or the domain wrote and that does not parse is refused like
# one that does not verify (`except (NotTaken, *PARSE_ERRORS)`) — the lists here left out `TypeError` and
# `AttributeError` (a doc that is a list), and one such peer stopped the search for the holder and the move (the
# review's eighth pass, sibling of the relay's bundle).

HOLDER, BACKUP, STRANDED = "domain/holder", "domain/backup", "domain/stranded"
# Everything the domain DECIDED and nobody else holds (feedback AS: the first list stopped at Lesson 14, and a
# move lost the topology of Lesson 17 — every chain through a relay —, the list of members, and every road a
# subsystem had decided, which was decided again differently). The platform's own rows, and what each subsystem
# keeps at the holder for the whole domain (`domain.kept`, `declared.kept`). What is not here is not lost: the books
# are recomputed by the next pass, and the keys, the revocation list and each cluster's grants are already on every
# member, the new holder first among them. The licence is a cache of the vendor's file (Lesson 5): kept, so that
# a move does not start the grace period for nothing.
#
# The people move with the domain (the product's answer, Q7): the users and every cluster's emergency hash are in the
# backup — their secrets SEALED UNDER THE BACKUP KEY (`Signer.backup_key`, HMAC of the root's key and a revision; the
# product's r23-seal), not under the holder's ring, which no other holder has, and never in the clear: a member chosen to
# keep a copy reads no hash of it. The signer's own keys are not in the backup, ever.
PLATFORM_EXPORTED = ("domain/pending/", "domain/grants/", "domain/shared", "domain/topology", "domain/members",
                     "domain/placement", "domain/licence", "domain/break_glass/", "identity/users/")


def exported() -> tuple[str, ...]:
    return (*PLATFORM_EXPORTED, *declared.kept())


# And from the holder's OBJECT store: the week of alarms the domain read (Lesson 14). It lives on the holder's
# card, next to the reports — and a card is what dies with a small box. Promised to outlive any card, it has to
# leave the holder with the rest; restored, it is as old as the backup, and the reports fill in the rest.
EXPORTED_OBJECTS = (f"{HISTORY}/",)


class Deposed(Exception):
    pass


class Frozen(Exception):
    pass


class TwoHolders(Exception):
    pass


def read_holder(vars_, keys, now: float) -> dict | None:
    items, _ = vars_.get(HOLDER)
    if not items:
        return None
    try:
        return verified_record(json.loads(items["doc"]), keys, now)
    except PARSE_ERRORS:
        return None


def verified_record(doc, keys, now: float) -> dict | None:
    """A holder record as signed (`{term, holder, at[, from][, url], kid, sig}`), verified against `keys` — or None:
    unsigned, signed by a key this member does not trust, not a record at all. A member that trusts a root takes a
    holder record only from the ROOT (step 9). The token key signs every minute and sits on the holder; a record it
    signed is what a stolen holder would write to take the domain."""
    try:
        rec = verify(doc, keys, now)
        int(rec["term"])
        if not isinstance(rec.get("holder"), str) or not rec["holder"]:
            return None
    except (NotTaken, *PARSE_ERRORS):
        return None
    if keys is not None and keys.root is not None and rec.get("kid") != ROOT_KID:
        return None
    return rec


# THE PROCESS DOORS OF EVERY CLUSTER'S CONSOLE THAT A MOVE AND A FOLLOWING AGENT USE (contract §10a; «Архитектор»
# 2026-10-06). Each cluster answers for what IT holds; nobody reads another cluster's store.
#
#     GET  /api/held      no token: `{cluster, holder, term, keys, backup: {term, rev}}` — the holder's record this
#                         cluster holds (the holder's own claim on the holder's cluster, the record its agent carried home
#                         on a member) as it was signed, its term, the key set it carries as it was signed, and WHICH
#                         backup copy is kept here: its pointer's term and revision, a pair (null — none). A revision
#                         says nothing against another term's — rev 7 of a new term is newer than rev 255 of the old
#                         one — so a copy is never said by its `rev` alone (ADR-0032, «Архитектор» 2026-10-06). Public,
#                         and proving itself: read
#                         by an agent following the holder (`agent.HolderFollower`), by a move for the largest term and
#                         the keys, and by the console module on a person's page (contract §2: the one process door it
#                         reads). Never the backup's content — even its plain part is the domain's state
#     GET  /api/backup    the backup copy this cluster keeps (`domain/backup`, the object it names) and the shared
#                         document, only to a process that signs the ask with the key of a member on THIS cluster's
#                         copy of the list of members (`MEMBER_LIST`, carried home by its agent) — the way the
#                         domain's door knows a member (`carry.HolderDoor`). The new holder of an emergency move is a
#                         member, and signs with its member key (`AskedCluster`)
#     POST /api/prepare, POST /api/take   a planned handover's, handed on to this cluster's own signer
#                         (`signer_service.Holder.prepare`, `.take`), which checks them itself
#
# `MEMBER_LIST`: the list of members as the domain last gave it to this cluster's agent — `domain/members` is the
# holder's record, written by the holder alone, and an agent writes no row of that name anywhere (`rights`).
MEMBER_LIST = "domain/member-list"


def held(cluster: str, vars_) -> dict:
    from .agent import KEYS_PATH

    def doc_of(path):
        items, _ = vars_.get(path)
        try:
            doc = json.loads(items["doc"]) if items and items.get("doc") else None
        except PARSE_ERRORS:
            doc = None
        return doc if isinstance(doc, dict) else None
    keys, _ = vars_.get(KEYS_PATH)
    rec = doc_of(HOLDER)
    try:
        term = int(rec["term"]) if rec else None
    except PARSE_ERRORS:
        term = None
    ptr, _ = vars_.get(BACKUP)
    try:
        backup = copy_of(ptr)
    except PARSE_ERRORS:
        backup = None
    return {"cluster": cluster, "holder": rec, "term": term, "keys": dict(keys) if keys else None, "backup": backup}


def copy_of(ptr) -> dict | None:
    """Which copy a backup pointer names, `{term, rev}` — the pair it is ordered by, and nothing of what it holds; None
    for no pointer. Raises one of `PARSE_ERRORS` for a pointer that does not read."""
    return {"term": int(ptr["term"]), "rev": int(ptr["rev"])} if ptr else None


# THE COPIES ON THE HOLDER'S CARD (ADR-0032, «Архитектор» 2026-10-06). A member's console knows its own copy (`held`)
# and neither the holder's nor anybody else's; the holder knows what it wrote and, from the members' REPORTS, what each
# says it keeps. So the comparison lives on the holder's card (`signer_service.Holder.term_view`), and only there:
#
#     backup    the last copy the holder wrote — the newest by (term, rev) of the pointers it keeps for its backup
#               holders (`domain/backup/<member>`); a pointer that does not read is left out of the newest
#     copies    {<member>: {term, rev}} — the copy each member says it keeps: the `domain/backup` row its agent writes
#               only when the copy it took matched the pointer and verified (`shared.carry`), carried up with every
#               report (`uplink`). A member that keeps none is not listed; one whose row does not read is
#               `{garbled: <why>}` — said, not left out. A former backup holder's copy too, and a former holder's:
#               nobody updates them and nobody drops them — they are a move's last way back (`move_domain` reads the
#               newest anyone keeps)
def last_written(vars_) -> dict | None:
    best = None
    for path in vars_.list(BACKUP + "/"):
        try:
            c = copy_of(vars_.get(path)[0])
        except PARSE_ERRORS:
            continue
        if c and (best is None or (c["term"], c["rev"]) > (best["term"], best["rev"])):
            best = c
    return best


def copies(holder: "DomainHolder", members) -> dict:
    out = {}
    for name in members if holder.objects is not None else ():   # no store for reports: nobody's copy is known here
        mine = holder.reported(name)
        try:
            mine.vars.list(BACKUP)                       # never reported, or its mark does not read: nothing to say
        except Unreachable:
            continue
        try:
            c = copy_of(mine.vars.get(BACKUP)[0])
        except Unreachable as e:                         # the report's copy of the row does not parse
            out[name] = {"garbled": str(e)}
            continue
        except PARSE_ERRORS as e:                        # it parses, and is no pointer
            out[name] = {"garbled": f"{name}'s copy of {BACKUP} is no pointer ({type(e).__name__}: {e})"}
            continue
        if c is not None:
            out[name] = c
    return out


def backup_message(cluster: str, member: str, at: float) -> bytes:
    """What a member signs to read the backup copy `cluster` keeps (`GET /api/backup`)."""
    return f"backup|{cluster}|{member}|{at:.3f}".encode()


def prepare_message(cluster: str, at: float) -> bytes:
    """What the holder of the current term signs to ask `cluster` to prepare for a handover (`POST /api/prepare`)."""
    return f"prepare|{cluster}|{at:.3f}".encode()


def backup_answer(cluster: str, vars_, objects, member: str | None, at, signature: str | None,
                  now: float) -> tuple[int, dict]:
    """`GET /api/backup` on `cluster`'s console: 401 for an ask nobody signed, or out of time; 403 for a name that is no
    member on this cluster's list, or whose key the root revoked; 200 — `{cluster, pointer, backup, shared}`: the
    pointer, the backup object it names and the shared document, as this cluster's agent verified and kept them."""
    from w2cplatform.trust.memberkey import verify as verify_sig
    from .carry import SKEW
    from .shared import OBJECT as SHARED_OBJECT
    if not member or not signature:
        return 401, {"detail": "the backup a cluster keeps is the domain's state: a member signs its ask (X-W2C-Member, "
                               "X-W2C-Time, X-W2C-Signature)"}
    try:
        at = float(at)
        items, _ = vars_.get(MEMBER_LIST)
        doc = json.loads(items["doc"]) if items and items.get("doc") else {}
        row = dict(doc.get("members", {})).get(member) or {}
    except PARSE_ERRORS:
        return 401, {"detail": "an ask names its time, and this cluster's list of members must read"}
    if not row.get("key"):
        return 403, {"detail": f"{member} is no member with a key on {cluster}'s list of members"}
    if row["key"] in row.get("revoked_keys", []):
        return 403, {"detail": f"{member}'s key was revoked by the domain's root"}
    if not verify_sig(row["key"], backup_message(cluster, member, at), signature):
        return 401, {"detail": f"the ask is not signed by {member}'s key"}
    if not (abs(now - at) <= SKEW):
        return 401, {"detail": f"the ask is {now - at:+.0f} s from {cluster}'s clock: more than {SKEW:.0f} s"}
    ptr, _ = vars_.get(BACKUP)
    raw = objects.get(BACKUP) if ptr and objects is not None else None
    shared = objects.get(SHARED_OBJECT) if objects is not None else None
    return 200, {"cluster": cluster, "pointer": dict(ptr) if ptr else None,
                 "backup": raw.decode() if raw is not None else None,
                 "shared": shared.decode() if shared is not None else None}


class AskedCluster:
    """A cluster as a move reads it over its console's process doors, never its store: `/api/held` for the holder's
    record and the key set it carries, `/api/backup` — signed by `key`, this member's own — for the backup copy it keeps
    and the shared document. Shaped as the `Cluster` a move reads (`vars.get`, `objects.get`); every answer is asked
    once; a console that does not answer is `Unreachable`, as a store that does not. It writes nothing anywhere."""

    def __init__(self, name: str, console: str, member: str, key, wall=time.time, timeout: float = 5.0):
        self.name, self.console, self.member, self.key, self.wall, self.timeout = name, console, member, key, wall, timeout
        self.is_domain_holder = False
        self._held = self._backup = None
        outer = self

        class Vars:
            def get(self, path):
                from .agent import KEYS_PATH
                if path == HOLDER:
                    doc = outer.held().get("holder")
                    return ({"doc": json.dumps(doc, sort_keys=True)} if doc else None), 0
                if path == KEYS_PATH:
                    keys = outer.held().get("keys")
                    return (dict(keys) if isinstance(keys, dict) else None), 0
                if path == BACKUP:
                    ptr = outer.backup().get("pointer")
                    return (dict(ptr) if isinstance(ptr, dict) else None), 0
                return None, 0

            def put(self, *a, **kw):
                raise PermissionError("a move writes no other cluster's store")

        class Objects:
            def get(self, key):
                from .shared import OBJECT as SHARED_OBJECT
                said = outer.backup().get({BACKUP: "backup", SHARED_OBJECT: "shared"}.get(key, ""))
                return said.encode() if isinstance(said, str) else None

            def put(self, *a, **kw):
                raise PermissionError("a move writes no other cluster's store")

        self.vars, self.objects = Vars(), Objects()

    def _get(self, path: str, headers: dict | None = None) -> dict:
        import urllib.error
        import urllib.request
        req = urllib.request.Request(self.console.rstrip("/") + path, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                said = json.loads(r.read(16 << 20))
        except urllib.error.HTTPError as e:
            raise Unreachable(f"{self.name} refused {path}: {e.code}") from None
        except (OSError, *PARSE_ERRORS) as e:
            raise Unreachable(f"{self.name} did not answer {path}: {e}") from None
        if not isinstance(said, dict):
            raise Unreachable(f"{self.name} answered {path} with no object")
        return said

    def held(self) -> dict:
        if self._held is None:
            self._held = self._get("/api/held")
        return self._held

    def backup(self) -> dict:
        if self._backup is None:
            if self.key is None:
                raise Unreachable(f"{self.member} holds no member key: it cannot ask {self.name} for its backup")
            at = self.wall()
            self._backup = self._get("/api/backup", {
                "X-W2C-Member": self.member, "X-W2C-Time": f"{at:.3f}",
                "X-W2C-Signature": self.key.sign(backup_message(self.name, self.member, at))})
        return self._backup


# Step 9's cold start: a domain whose root is off the holder from the first day. The installer holds the root
# for the minutes this takes — the holder's issuing certificate, the first key set, the record of term 1 — and
# then hands it to the operator as the recovery file. Nothing of it is written on the holder.
def install(fed, name: str, domain_id: str, root: DomainRoot, wall=time.time, objects=None,
            member_key: str | None = None) -> "DomainHolder":
    vars_ = fed.clusters[name].vars
    signer = Signer(domain_id, vars_, now=wall, root=root)
    DomainPublisher(vars_).publish_keys(root.key_set(signer.tokens.keyset(), rev=1,
                                                     issuing=[signer.root.cert.serial_number]))
    record = sign({"term": 1, "holder": name, "at": wall()}, root)
    holder = DomainHolder(fed, name, signer, 1, wall, objects=objects, record=record)
    holder.member_key = member_key
    holder.claim()
    return holder


class DomainHolder:
    """The domain's services on one member, holding a term."""

    def __init__(self, fed, name: str, signer: Signer, term: int, wall=time.time, objects=None, record: dict | None = None):
        """`fed`: the site, each member through its door — what this member, AS a member, can reach. `objects`:
        this holder's durable store, where the other members' agents leave their reports. `record`: the holder
        record the root signed for this term (step 9) — a holder that has one cannot write another."""
        self.fed, self.name, self.signer, self.term, self.wall = fed, name, signer, term, wall
        self.objects, self.record = objects, record
        self.backup_rev = 0
        self.backups = objects                           # where its own backups are written — read again on deposition
        self.restored_from: dict | None = None           # {term, rev} of the backup this term started from
        self.deposed_by: dict | None = None
        self.frozen_for: str | None = None               # the member a planned handover is moving the domain to
        # Where this holder's signer answers (ADR-0032): said in the record it claims, so that whoever reads the record —
        # an old holder that was replaced, applying again what it alone held — knows which door holds the domain now.
        # The view's `url` is the domain console's; the signer's address is the record's.
        self.url: str | None = None
        # The key this cluster was admitted with as a MEMBER (hex) — the holder is on nobody's list while it holds
        # (`Members` refuses it), so its key travels in its backups instead (`holder_key`), and the next holder
        # writes it into the list when this one becomes a member like the others (the product, feedback CC).
        self.member_key: str | None = None

    @property
    def vars(self):
        return self.fed.clusters[self.name].vars

    def reported(self, member: str):
        """What the holder knows of another member: its last report, in the holder's own store."""
        from .uplink import member_copy
        return member_copy(member, self.objects, wall=self.wall)

    def claim(self) -> None:
        doc = self.record or sign({"term": self.term, "holder": self.name, "at": self.wall(),
                                   **({"from": self.restored_from} if self.restored_from else {}),
                                   **({"url": self.url} if self.url else {})}, self.signer.tokens)
        _, idx = self.vars.get(HOLDER)
        self.vars.put(HOLDER, {"doc": json.dumps(doc, sort_keys=True)}, cas=idx)

    # A holder process starting — after a reboot, a crash, a power cut. It LOOKS before it claims (feedback AS): its
    # own agent may have carried a larger term into this cluster before this process came up, and then there is
    # nothing to claim. Claiming blindly would write term 1 over the carried term 2 in its own store — the one
    # record that says who the holder is now. Deposed from the start, it still opens its door, for the list.
    def start(self) -> bool:
        if not self.check():
            return False
        self.claim()
        return True

    def export(self) -> dict[str, dict]:
        """What the domain decided, each row's secrets moved from the holder's ring to the backup key."""
        from .carry import open_row, seal_row
        self._settle_members()
        box, out = self.signer.backup_sealer(), {}
        for prefix in exported():
            for path in self.vars.list(prefix):
                items, _ = self.vars.get(path)
                if items is not None:
                    out[path] = seal_row(box, open_row(self.signer.sealer, items, path), path)
        return out

    # Publish the state beyond the holder: one signed document in the holder's durable store, and a pointer for
    # each member chosen to keep it, which that member's agent carries home as it carries the settings.
    # The list of members, if nobody ever wrote it, was the configuration of THIS holder's processes (`Members`); a
    # new holder restored without it would not know who its members are. So the first backup writes it — every
    # cluster of the site, this holder included: after a move it is a member like the others, and the domain's
    # own cluster on the list is left alone by `members.apply`. From then on it is a record, exported with the rest.
    def _settle_members(self) -> None:
        from .members import MEMBERS, Members
        if self.vars.get(MEMBERS)[0] is None:
            Members(self.vars, self.wall, configured=lambda: sorted(self.fed.clusters)).settle()

    def export_objects(self) -> dict[str, str]:
        out = {}
        for prefix in EXPORTED_OBJECTS if self.objects is not None else ():
            for key in self.objects.list(prefix):
                raw = self.objects.get(key)
                if raw is not None:
                    out[key] = raw.decode()
        return out

    def backup(self, targets: list[str], objects) -> int:
        self._not_deposed()                              # a FROZEN holder still backs up: that is how it hands over
        self.backups = objects
        self.backup_rev += 1
        doc = sign({"term": self.term, "rev": self.backup_rev, "holder": self.name, "at": self.wall(),
                    "state": self.export(), "objects": self.export_objects(), "backup_key_rev": self.signer.backup_rev,
                    **({"holder_key": self.member_key} if self.member_key else {})}, self.signer.tokens)
        raw = json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()
        key = f"backup/rev-{self.backup_rev}"
        objects.put(key, raw)
        import hashlib
        for t in targets:
            path = f"{BACKUP}/{t}"
            _, idx = self.vars.get(path)
            self.vars.put(path, {"object": key, "rev": self.backup_rev, "term": self.term,
                                 "sha256": hashlib.sha256(raw).hexdigest()}, cas=idx)
        return self.backup_rev

    # Is this holder still the holder? Any member that carries a larger term says no. Read, not told: the
    # loser finds out on its next look, exactly as a fenced worker does. It looks as any member looks for the
    # holder at boot — opening the connections itself: the members that follow the new term report to the NEW
    # holder, so nothing about it would ever land in this one's store.
    #
    # Its OWN store first: this cluster is a member too, and its agent carries the holder record home like any
    # agent — a holder whose neighbours' doors are closed learns it was replaced from its own agent, or not at all.
    def check(self) -> bool:
        from .agent import ClusterTrust
        keys = ClusterTrust(self.vars).keyset() or self.signer.tokens.keyset()   # the published set: the root in it
        for name, c in [(self.name, self.fed.clusters[self.name]),
                        *[(n, c) for n, c in self.fed.clusters.items() if n != self.name]]:
            try:
                rec = read_holder(c.vars, keys, self.wall())
            except Unreachable:
                continue
            if rec and int(rec["term"]) > self.term:
                self.depose(rec)
                return False
        return True

    # Replaced, by the record given — verified by whoever read it: `check`, or a planned handover whose target answered
    # with the record it claimed (`handover`).
    def depose(self, rec: dict) -> None:
        self.deposed_by = rec
        self._strand()
        self._forget_keys()

    # A holder that was replaced has no use for its keys, and a box that stays on the wall with them in its
    # flash is the stolen holder of step 9, waiting. An issuing signer's keys are nowhere else — the new holder
    # has keys of its own — so they go. (A signer of Lessons 4–7 holds what the recovery file holds; forgetting
    # it here would protect nothing.)
    def _forget_keys(self) -> None:
        if not self.signer.chain:
            return
        _, idx = self.vars.get("domain/signer")
        self.vars.put("domain/signer", {"forgotten": f"deposed by term {self.deposed_by['term']}"}, cas=idx)

    # What this holder alone held, decided ONCE — the moment it learns it was replaced — and kept (feedback AS).
    # Later there is nothing to decide it against: after a second move the record names a term restored from
    # somebody else's backup. Measured against the backup the new term was restored from, when that was one of
    # this holder's own (`from` in the record); otherwise against this holder's own last backup — "changed after my
    # last copy", which is the most it can know — and the list says which.
    def _strand(self) -> None:
        if self.vars.get(STRANDED)[0] is not None:
            return
        base, state = "no backup of its own: everything it holds", {}
        mine = self._own_backups()
        src = self.deposed_by.get("from") or {}
        if int(src.get("term", -1)) == self.term and int(src.get("rev", -1)) in mine:
            rev = int(src["rev"])
            base, state = f"backup rev {rev}, which term {self.deposed_by['term']} was restored from", mine[rev]
        elif mine:
            rev = max(mine)
            base, state = f"its own last backup, rev {rev}", mine[rev]
        left = stranded(self.vars, state, self.signer)
        self.vars.put(STRANDED, {"doc": json.dumps({"term": self.deposed_by["term"], "holder": self.deposed_by["holder"],
                                                     "base": base, "items": left}, sort_keys=True, ensure_ascii=False)})

    def _own_backups(self) -> dict[int, dict]:
        """{rev: state} of the backups this holder wrote at its own term, from its own store."""
        out = {}
        if self.backups is None:
            return out
        for key in self.backups.list("backup/rev-"):
            raw = self.backups.get(key)
            try:                                         # its own, in its own store: read, not verified — and one
                doc = json.loads(raw)                    # that does not parse is that backup's, numbers included (the
                if int(doc.get("term", -1)) == self.term and doc.get("holder") == self.name:   # ninth review's sweep)
                    out[int(doc["rev"])] = doc.get("state", {})
            except PARSE_ERRORS:
                continue
        return out

    def stranded_items(self) -> dict | None:
        items, _ = self.vars.get(STRANDED)
        return json.loads(items["doc"]) if items else None

    # What every write to the domain's state asks first. Frozen: a planned handover is under way, and a write
    # accepted now would be made after the last backup — exactly what `stranded` exists to catch, created on
    # purpose. Refused for the seconds the handover takes, with the reason.
    def guard(self) -> None:
        self._not_deposed()
        if self.frozen_for:
            raise Frozen(f"{self.name} is handing the domain over to {self.frozen_for}; edits are refused until it "
                         f"has — seconds, not minutes — and then go there")

    def _not_deposed(self) -> None:
        if self.deposed_by:
            raise Deposed(f"{self.name} held the domain at term {self.term}; {self.deposed_by['holder']} holds it "
                          f"at term {self.deposed_by['term']} — edits go there")


# The agent's side: the holder record is carried like the keys, with one rule the keys never needed — it
# never goes BACKWARDS. An agent still pointed at an old holder that came back would otherwise carry that
# holder's smaller term over the larger one, and undo the move on every member it reached.
def carry_holder(domain_vars, member_vars, keys, now: float) -> str:
    items, _ = domain_vars.get(HOLDER)
    if not items:
        return "no holder record"
    try:
        doc = json.loads(items["doc"])
    except PARSE_ERRORS as e:
        return f"refused: {e}"
    return take_record(member_vars, doc, keys, now)


def take_record(member_vars, doc, keys, now: float) -> str:
    """The holder record `doc`, as signed, into this member's own store — written by its own agent — when it verifies
    and holds a larger term than the record kept here: never backwards."""
    try:
        incoming = verify(doc, keys, now)
        int(incoming["term"])
    except (NotTaken, *PARSE_ERRORS) as e:
        return f"refused: {e}"
    if keys is not None and keys.root is not None and incoming.get("kid") != ROOT_KID:
        return "refused: a holder record not signed by the domain's root"   # what a stolen holder would write
    have = read_holder(member_vars, keys, now)
    if have and int(have["term"]) >= int(incoming["term"]):
        return "holding" if int(have["term"]) == int(incoming["term"]) else "holding a larger term"
    _, idx = member_vars.get(HOLDER)
    member_vars.put(HOLDER, {"doc": json.dumps(doc, sort_keys=True)}, cas=idx)
    return f"took term {incoming['term']}"


# Which member holds the domain, as a member works it out: the largest term it can verify — its own carried
# record, or a claim a reachable member makes about ITSELF. A holder that is off is still the holder if nobody
# holds a larger term; the agent then waits, it does not wander to a smaller one.
def find_holder(fed, member_vars, keys, now: float) -> str | None:
    best = read_holder(member_vars, keys, now)
    for name, c in fed.clusters.items():
        try:
            rec = read_holder(c.vars, keys, now)
        except Unreachable:
            continue
        if not rec or rec["holder"] != name:
            continue                                     # a member's CARRIED record is hearsay; only the holder's own claim counts here
        if best is None or int(rec["term"]) > int(best["term"]):
            best = rec
        elif int(rec["term"]) == int(best["term"]) and rec["holder"] != best["holder"]:
            raise TwoHolders(f"{rec['holder']} and {best['holder']} both claim term {rec['term']}: the domain was moved twice")
    return best["holder"] if best else None


# How long the old holder's token keys stay trusted after a PLANNED move (step 9): the people's tokens it issued
# live fifteen minutes, and the books issue their stream tokens again on the new holder's first pass (a token
# the current key did not sign is not kept, `kid_of`). After a theft: not a second.
OLD_KEYS_OVERLAP = 3600.0


def move_domain(fed, new: str, signer_backup: bytes, domain_id: str, objects_of, wall=time.time,
                stolen: bool = False, sealer=None) -> tuple[DomainHolder, dict]:
    """Move the domain on `new` from the signer's backup and the newest verified state any reachable
    member holds. `objects_of(member)` is that member's durable store.

    `signer_backup` is either the signer's backup of Lessons 4–7 (both keys; the new holder holds the same
    keys the old one did) or — step 9 — the root's recovery file: then the new holder gets keys of its OWN,
    the root signs the next key set and the record of the new term, and `stolen` says what happens to the
    old holder's keys — kept an hour for the tokens they signed, or dropped at once, with its issuing
    certificates revoked and every member's LDevID signed again."""
    now = wall()
    new_vars = fed.clusters[new].vars
    root = DomainRoot.restore(domain_id, signer_backup, now=wall) if is_recovery_file(signer_backup) else None
    if root is None:
        if stolen:
            raise ValueError("a stolen holder cannot be revoked from the signer's backup: it holds the stolen keys "
                             "themselves; that takes a root off the holder (step 9)")
        signer = Signer.restore(domain_id, new_vars, signer_backup, now=wall, sealer=sealer)
        keys = signer.tokens.keyset()
    else:
        keys = _trusted_keys(fed, new, root, now)        # what members trust NOW — the old holder's keys, under the root
        signer = Signer.issued(domain_id, new_vars, root, now=wall, sealer=sealer)
    top_term, top_holder, best, ignored = 0, None, None, []
    for name, c in fed.clusters.items():
        try:
            rec = read_holder(c.vars, keys, now)
        except Unreachable:
            continue
        if rec and int(rec["term"]) > top_term:
            top_term, top_holder = int(rec["term"]), rec["holder"]   # the holder being replaced: after a theft, the thief's
        try:                                             # a backup refused or not answered is not a term unseen
            ptr, _ = c.vars.get(BACKUP)
            raw = objects_of(name).get(BACKUP) if ptr else None
        except Unreachable as e:
            if isinstance(c, AskedCluster):              # its console answered the record and refused the backup: said
                ignored.append((name, str(e)))
            continue
        if raw is None:
            continue
        try:
            doc = verify(json.loads(raw), keys, now)
        except (NotTaken, *PARSE_ERRORS) as e:
            ignored.append((name, str(e)))
            continue
        if best is None or (int(doc["term"]), int(doc["rev"])) > (int(best[1]["term"]), int(best[1]["rev"])):
            best = (name, doc)
    if best:
        # Each secret opened with the backup key this holder derives — from the recovery file's root, or the signer's
        # backup — and sealed again with this holder's own ring. A backup this holder cannot open is not a backup of
        # this domain (a forged one was refused above, by its signature).
        from .carry import open_row, seal_row
        box = signer.backup_sealer()
        for path, items in best[1]["state"].items():
            _, idx = new_vars.get(path)
            new_vars.put(path, seal_row(sealer, open_row(box, items, path), path), cas=idx)
        for key, text in best[1].get("objects", {}).items():
            objects_of(new).put(key, text.encode())      # the alarm history, as of the backup
        _keep_member_key(new_vars, best[1], new, wall, revoked=keys.revoked_members)
    keys_rev = None
    if root is None:
        DomainPublisher(new_vars).publish_keys(keys)
    else:
        items, keys_rev = _next_key_set(root, keys, signer, now, stolen,
                                        stolen_key=_member_key_of(new_vars, top_holder, best) if stolen else None)
        DomainPublisher(new_vars).publish_keys(items)
    # The shared document (Lesson 12): its pointer came back with the state, but the object it names was in the
    # old holder's store. Every member holds that document, verified by the same key — the new holder first among
    # them — so it is put back from the first member copy whose checksum matches the pointer. Without it the new
    # holder would publish a pointer to nothing, and every pass that reads the document — the book of asks built
    # from its scenarios (Lesson 16) — would read an empty one.
    from .shared import OBJECT as SHARED_OBJECT, POINTER as SHARED_POINTER
    import hashlib
    shared_from = None
    ptr, _ = new_vars.get(SHARED_POINTER)
    if ptr and ptr.get("object") and objects_of(new).get(ptr["object"]) is None:
        for name in [new, *[n for n in fed.clusters if n != new]]:
            try:
                raw = objects_of(name).get(SHARED_OBJECT)
            except Unreachable:
                continue
            if raw is not None and hashlib.sha256(raw).hexdigest() == ptr["sha256"]:
                objects_of(new).put(ptr["object"], raw)
                shared_from = name
                break
    term = top_term + 1
    if root is not None:
        _sign_shared_again(new_vars, objects_of(new), signer, term)
    for name, c in fed.clusters.items():
        c.is_domain_holder = name == new
    restored_from = {"term": int(best[1]["term"]), "rev": int(best[1]["rev"])} if best else None
    record = None if root is None else sign({"term": term, "holder": new, "at": now,
                                              **({"from": restored_from} if restored_from else {})}, root)
    holder = DomainHolder(fed, new, signer, term, wall, objects=objects_of(new), record=record)
    from .members import Members
    holder.member_key = (Members(new_vars, wall).read()["members"].get(new) or {}).get("key")   # its own, for its backups
    holder.backup_rev = int(best[1]["rev"]) if best else 0
    holder.restored_from = restored_from
    holder.claim()
    # Never the stolen holder itself: whoever has it has its member key too, and a new LDevID for that key would hand the
    # thief a fresh identity in the domain that is moving away from him. Not skipped once but REVOKED (the product,
    # feedback CH): skipped, the key stayed in its row, and the next theft — of somebody else — signed it again.
    if stolen and top_holder:
        _revoke_member_key(new_vars, top_holder, wall)
    from .agent import KEYS_PATH
    revoked_now = KeySet.from_items(new_vars.get(KEYS_PATH)[0] or {"current": ""}).revoked_members
    reissued = reissue_ldevids(signer, new_vars, skip={top_holder} if top_holder else set(),
                               revoked=revoked_now) if stolen else []
    rev = holder.backup_rev
    report = {"term": holder.term, "record": json.loads(new_vars.get(HOLDER)[0]["doc"]),
              "restored_from": best[0] if best else None, "rev": rev, "ignored": ignored,
              "shared_from": shared_from, "keys_rev": keys_rev, "stolen": stolen, "reissued": reissued,
              "state": best[1]["state"] if best else {},
              "sentence": (f"term {holder.term} on {new}: the domain's state from backup rev {rev}, held by {best[0]}; "
                           f"anything the old holder changed after rev {rev} is not here" if best else
                           f"term {holder.term} on {new}: no backup could be reached — the domain starts empty but for its keys")
                          + (f"; the old holder's keys are no longer trusted (key set rev {keys_rev}) and "
                             f"{len(reissued)} member(s) have a new LDevID" if stolen else "")}
    return holder, report


# THE HOLDER THAT BECOMES A MEMBER (the product, feedback CC). A holder is on no list while it holds, so after a move
# the old one was written into the list without a key — and every rule that names a member by the key it was
# admitted with skipped it: after the NEXT theft its LDevID is not signed again (`reissue_ldevids`), and it has to
# be enrolled from the start. The backup carries the holder's member key, under its signature; the move writes it
# into the old holder's row when that row has none. A row with a key keeps it: a key presented later is never
# taken over the one a member was admitted with.
def _revoke_member_key(domain_vars, name: str, wall) -> None:
    """The member key of a stolen holder goes to `revoked_keys` in its row: no LDevID is signed for it again, and a
    backup that still carries it (`holder_key`) does not put it back. A machine that comes home makes a new key and
    is admitted again."""
    from .members import Members

    def mutate(members):
        row = members.get(name)
        if row is None or not row.get("key"):
            return False
        members[name] = {**{k: v for k, v in row.items() if k != "key"},
                         "revoked_keys": sorted(set(row.get("revoked_keys", [])) | {row["key"]})}
        return True
    Members(domain_vars, wall)._change(mutate)


def _member_key_of(domain_vars, name: str | None, best) -> str | None:
    """The member key of the holder being replaced: from its row, else from the backup it wrote itself."""
    from .members import Members
    if not name:
        return None
    key = (Members(domain_vars).read()["members"].get(name) or {}).get("key")
    if not key and best and best[1].get("holder") == name:
        key = best[1].get("holder_key")
    return key


def _keep_member_key(domain_vars, backup: dict, new: str, wall, revoked=frozenset()) -> None:
    from .members import Members
    old, key = backup.get("holder"), backup.get("holder_key")
    if not old or not key or old == new or key in revoked:
        return                                           # a key the root revoked never comes back from a backup (CK)
    m = Members(domain_vars, wall)

    def mutate(members):
        row = members.get(old)
        if row is not None and (row.get("key") or key in row.get("revoked_keys", [])):
            return False                                 # a key it has, or one revoked after a theft, stays as it is
        members[old] = {**(row or {"how": "former holder", "serial": None, "since": wall(), "by": None}), "key": key}
        return True
    m._change(mutate)


# The newest key set the ROOT signed that any reachable member holds — verified against the root in the
# recovery file, never taken on a member's word. It names the old holder's token keys (to read the records and
# backups they signed) and its issuing certificates (to revoke, if it was stolen).
def _trusted_keys(fed, new: str, root: DomainRoot, now: float) -> KeySet:
    from .agent import KEYS_PATH
    only_root = KeySet(current="", keys={ROOT_KID: root.public_bytes})
    best = only_root
    for name in [new, *[n for n in fed.clusters if n != new]]:
        try:
            items, _ = fed.clusters[name].vars.get(KEYS_PATH)
        except Unreachable:
            continue
        if not items or "doc" not in items:
            continue
        try:
            doc = verify(json.loads(items["doc"]), only_root, now)
        except (NotTaken, *PARSE_ERRORS):
            continue
        if doc.get("kid") == ROOT_KID and int(doc["rev"]) > best.rev:
            best = KeySet.from_items(items)
    return best


# The next key set: the new holder's token key, current. The old holder's keys stay an hour after a planned
# move and not at all after a theft — and then every issuing certificate the domain had so far is revoked with
# them: the thief holds one of them, and nobody can say which others he copied.
def _next_key_set(root: DomainRoot, old: KeySet, signer: Signer, now: float, stolen: bool,
                  stolen_key: str | None = None) -> tuple[dict, int]:
    ks = signer.tokens.keyset()
    mine = str(signer.root.cert.serial_number)
    if stolen:
        issuing, revoked = {mine}, old.revoked_ca | old.issuing
    else:
        for kid, pub in old.keys.items():
            if kid != ROOT_KID and old.usable(kid, now):
                ks.keys[kid] = pub
                ks.retire_at[kid] = min(old.retire_at.get(kid) or now + OLD_KEYS_OVERLAP, now + OLD_KEYS_OVERLAP)
        issuing, revoked = old.issuing | {mine}, set(old.revoked_ca)
    # The revision only grows, and the move cannot see every member: one that took a later set may be off now.
    # Built from what the reachable members hold, `old.rev + 1` could be no larger than what that one holds, and
    # it would refuse the new set for good (the product's question, feedback CK). So the revision is also at
    # least the root's clock, in seconds: a move made later signs a larger number than any move made before it.
    rev = max(old.rev + 1, int(now))
    revoked_members = set(old.revoked_members) | ({stolen_key} if stolen and stolen_key else set())
    return root.key_set(ks, rev, revoked, issuing, revoked_members), rev


# The shared document (Lesson 12) was signed by the old holder's token key, and members check it again every time
# they read it (`SharedView`): once that key retires, a member would read no settings at all. So the new holder
# signs the same settings again, at its own term — a newer (term, rev) than any member holds, carried like an edit.
def _sign_shared_again(domain_vars, domain_objects, signer: Signer, term: int) -> None:
    import hashlib
    from .shared import POINTER as SHARED_POINTER
    ptr, idx = domain_vars.get(SHARED_POINTER)
    raw = domain_objects.get(ptr["object"]) if ptr and ptr.get("object") else None
    if raw is None:
        return
    body = {k: v for k, v in json.loads(raw).items() if k not in ("kid", "sig")}
    doc = sign({**body, "term": term}, signer.tokens)
    raw = json.dumps(doc, ensure_ascii=False, sort_keys=True).encode()
    key = f"shared/rev-{doc['rev']}-term-{term}"
    domain_objects.put(key, raw)
    domain_vars.put(SHARED_POINTER, {"object": key, "rev": doc["rev"], "term": term,
                                     "sha256": hashlib.sha256(raw).hexdigest()}, cas=idx)


# After a theft: every member's LDevID was signed by an issuing certificate the root has just revoked. The new
# holder signs again the key each member was admitted with (`domain/members`, written by the registrar) — never
# a key a member merely presents now, which a thief could present too. Carried home by each member's agent.
def reissue_ldevids(signer: Signer, domain_vars, skip=frozenset(), revoked=frozenset()) -> list[str]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from w2cplatform.trust.signer import _pem
    from .agent import LDEVID_PATH
    from .members import Members
    out = []
    for name, m in sorted(Members(domain_vars).read()["members"].items()):
        if not m.get("key") or name in skip or m["key"] in revoked:
            continue                                     # revoked by the root (CK): a list restored from an old backup cannot bring it back
        cert = signer.issue(m.get("serial") or name, "ldevid", Ed25519PublicKey.from_public_bytes(bytes.fromhex(m["key"])))
        _, idx = domain_vars.get(f"{LDEVID_PATH}/{name}")
        domain_vars.put(f"{LDEVID_PATH}/{name}", {"cert": _pem(cert).decode(), "chain": _pem(signer.root.cert).decode()},
                        cas=idx)
        out.append(name)
    return out


# The domain's writes, behind the holder's guard: a kept edit (Lesson 9) is refused while the holder is frozen or
# deposed, as a 503 with the reason — the API's word for "not now, and here is why".
#
# Only ADDING is guarded. The other write to the same row — a member's report closing an edit (`reconcile`) —
# goes on during a handover, and that is not a hole (feedback AS): an edit the new term still holds as waiting
# is carried again, found already on the member, and closed there by the member's own report ("already").
# A closure is the member's news, not the operator's decision; losing it costs one repeat, never an edit.
class GuardedPending:
    def __init__(self, pending, holder: DomainHolder):
        self.pending, self.holder = pending, holder

    def add(self, *a, **kw):
        from .api import ApiError
        try:
            self.holder.guard()
        except (Deposed, Frozen) as e:
            raise ApiError(503, str(e))
        return self.pending.add(*a, **kw)

    def __getattr__(self, name):
        return getattr(self.pending, name)


# A PLANNED handover: the holder is alive and the operator moves the domain to `to` — a box being replaced,
# a server room arriving. It is the emergency move with the loss taken out, in four steps:
#
#     freeze        the old holder refuses writes, so nothing can be made after the backup that follows
#     last backup   to `to` itself, so the new holder restores from a copy that has EVERYTHING
#     carried       `to`'s agent takes it — verified, as any backup; if it does not, the handover is called
#                   off and the old holder unfreezes: nothing was claimed, nothing moved
#     taken         `to` takes the domain onto ITS OWN store — the same `move_domain`, run by `to`'s signer
#                   (`take`), never by the old holder, which writes no store but its own (ADR 0001 §1.12); the old
#                   holder reads the larger term `to` claims and steps down
#
# The difference from the emergency path is the last line of the report: nothing stranded, because the
# freeze made sure there was nothing to strand.
def handover(holder: DomainHolder, to: str, objects_of, carry_to, take,
             wall=time.time) -> tuple[DomainHolder | None, dict]:
    """`carry_to()` runs `to`'s agent once — in production, a nudge to the agent it would run anyway. `take()` is `to`'s
    own move: `(new, report)` — `new` the `DomainHolder` where the target runs in this process (the lessons), None where
    it answered over its door (`signer_service.move_by_handover`); `report["record"]`, the record it claimed, when it
    says one. `Unreachable` or `RuntimeError` from it: nothing moved."""
    holder.frozen_for = to
    try:
        rev = holder.backup([to], objects_of(holder.name))
        carry_to()
        try:                                             # read in `to`'s REPORT, which its agent left in the holder's store
            ptr, _ = (holder.reported(to).vars if holder.objects is not None else holder.fed.clusters[to].vars).get(BACKUP)
        except Unreachable:
            ptr = None                                   # silent: it cannot be the new holder now
        if not ptr or int(ptr["rev"]) != rev or int(ptr["term"]) != holder.term:
            raise RuntimeError(f"{to} did not take backup rev {rev}; the handover is called off and {holder.name} "
                               f"is still the holder")
    except Exception:
        holder.frozen_for = None
        raise
    try:
        new, report = take()
    except Unreachable:                                  # it reported the backup, then went silent: not the new holder
        holder.frozen_for = None
        raise RuntimeError(f"{to} took backup rev {rev} and then stopped answering; the handover is called off and "
                           f"{holder.name} is still the holder")
    except RuntimeError:
        holder.frozen_for = None
        raise
    # The record the target claimed, as it answered: verified here like any record a member reads — and, where the
    # target is reachable as a store of the site (the lessons), read there by `check` as well.
    from .agent import ClusterTrust, Untrusted
    try:
        keys = ClusterTrust(holder.vars).keyset() or holder.signer.tokens.keyset()
    except Untrusted:
        keys = holder.signer.tokens.keyset()
    claimed = verified_record(report.get("record"), keys, wall()) if report.get("record") else None
    if claimed and claimed["holder"] == to and int(claimed["term"]) > holder.term:
        holder.depose(claimed)
    if not holder.deposed_by:
        holder.check()
    if not holder.deposed_by:
        holder.frozen_for = None
        raise RuntimeError(f"{to} answered the handover with no record of a larger term; {holder.name} is still the holder")
    left = (holder.stranded_items() or {}).get("items", [])
    term = int(holder.deposed_by["term"])
    report.update(planned=True, stranded=left, term=term,
                  sentence=f"planned handover: term {term} on {to}, the domain's state at rev {rev} from "
                           f"{holder.name}; " + ("nothing stranded" if not left else f"{len(left)} item(s) stranded — a write got past the freeze"))
    return new, report


# What an old holder that came back holds and the new term does not: every exported item that differs from
# the state the new holder was restored from. For a person to look at — never applied by anyone on its own.
#
# A kept edit counts only as an EDIT: its `rev` moved, or the new term has none for that unit. An entry that
# differs only because a report closed fields of it, or annotated a conflict or a refusal, is not stranded —
# the new term will carry the same edit and the member will say "already" (see `GuardedPending`).
def stranded(old_vars, restored_state: dict, signer=None) -> list:
    """Compared by what the rows SAY: the old holder's under its ring, the restored state's under the backup key."""
    from .carry import open_row
    from .pending import PENDING_PATH
    out = []
    for prefix in exported():
        for path in old_vars.list(prefix):
            items, _ = old_vars.get(path)
            theirs = restored_state.get(path, {})
            if signer is not None:
                items = open_row(signer.sealer, items, path) if items else items
                theirs = open_row(signer.backup_sealer(), theirs, path) if theirs else theirs
            for k, v in (items or {}).items():
                if theirs.get(k) == v:
                    continue
                if path.startswith(PENDING_PATH + "/") and k in theirs:
                    try:
                        if json.loads(v).get("rev") == json.loads(theirs[k]).get("rev"):
                            continue                     # the same edit, closed further here: not the operator's
                    except PARSE_ERRORS:
                        pass
                # The list is a plain row the operator reads: a secret that differs is NAMED, its value never copied
                # out of the ring it was opened from.
                out.append([path, k, "<secret: differs>" if is_secret_field(k) else v])
    return out
