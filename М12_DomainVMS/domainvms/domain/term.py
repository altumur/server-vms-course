"""Lesson 15 — the domain holder on one node.

A site of cameras and no server. The domain still has to run somewhere — the signer, the console, the
kept edits, the shared settings — and this module decided long ago where: in ONE designated cluster, with
nothing to fail over to, its key backed up beyond it (Lessons 4 and 7). On a server room that was a drill
done once a year. On a camera it is a Tuesday: cameras are unplugged, their flash wears out, they are
stolen. So moving the domain has to become an ordinary operation, and three things follow.

    a term          the holder has a number, and every move takes a larger one. A holder that comes back
                    after being replaced sees a larger term on any member and steps down: its writes are
                    refused, and it says to whom they go. The epoch of Lesson 1 of М10A, one level up —
                    and, as there, the loser finds out on its next read, not from a message
    beyond itself   what the domain holds that nobody else does is published to other members, signed, as
                    the shared settings are (Lesson 12). Much of its state already lives on members — each
                    cluster's grants in that cluster — but not all of it: the edit kept for a camera that is
                    OFF (Lesson 9) is, by definition, on no camera that could carry it home. A domain whose
                    holder dies takes those with it unless it published them
    stranded        an old holder that returns may have made changes after its last backup. They are not
                    silently lost and not silently applied: they are listed, for a person, as "not in term
                    N+1 — apply again?"

    domain/host                 in the holder's Variables, and carried to every member: {term, host, from}, signed —
                                `from`: the backup {term, rev} this term was restored from
    domain/backup/<member>      in the holder's Variables: a pointer, for each member chosen to keep a copy
    backup/rev-<n>              in the holder's durable objects: the signed state
    domain/backup               in a chosen member: its agent's copy of the pointer, and of the document
    domain/stranded             in a DEPOSED holder's Variables: what it alone held, decided once, when it stepped down

Who opens which connection (Lesson 10, step 7). The holder reads the other cameras only by their REPORTS, left
in its own store by their agents (`reported`) — a planned handover sees that the target took the last backup
in the target's report, never by calling it. The site's doors are used only by a camera acting as a camera:
one that boots and looks for the holder (`find_holder`), an old holder that comes back and looks whether it still is
one (`check`), and the operator moving the domain to a camera, which reads its neighbours for the newest backup and
the largest term (`move_domain`) — the one exception the lesson names, because the holder that would have held the
reports is the one that is gone.

What is NOT in the backup: the signer's key. It is the one thing that must never sit beside the rest, and it
is restored from where Lesson 7 put it — offline, or in the recovery file the installer handed over. Without
it no backup verifies and no member follows the new holder, which is the point.
"""
from __future__ import annotations

import json
import time

from .agent import DomainPublisher
from .federation import Unreachable
from .shared import NotTaken, sign, verify
from .signer import Signer

HOST, BACKUP, STRANDED = "domain/host", "domain/backup", "domain/stranded"
# Everything the domain DECIDED and nobody else holds (feedback AS: the first list stopped at Lesson 14, and a
# move lost the topology of Lesson 17 — every chain through a relay —, the list of members, and every road a
# recorder had said it could not pull, which became a pull again). What is not here is not lost: the books are
# recomputed by the next pass, and the keys, the revocation list and each cluster's grants are already on every
# member, the new holder first among them. The licence is a cache of the vendor's file (Lesson 5): kept, so that
# a move does not start the grace period for nothing.
EXPORTED = ("domain/pending/", "domain/grants/", "domain/crossings", "domain/sources/", "domain/shared",
            "domain/topology", "domain/members", "domain/roads", "domain/placement", "domain/licence")


class Deposed(Exception):
    pass


class Frozen(Exception):
    pass


class TwoHolders(Exception):
    pass


def read_holder(vars_, keys, now: float) -> dict | None:
    items, _ = vars_.get(HOST)
    if not items:
        return None
    try:
        return verify(json.loads(items["doc"]), keys, now)
    except (NotTaken, ValueError, KeyError):
        return None


class DomainHolder:
    """The domain's services on one member, holding a term."""

    def __init__(self, fed, name: str, signer: Signer, term: int, wall=time.time, objects=None):
        """`fed`: the site, each camera through its door — what this camera, AS a camera, can reach. `objects`:
        this holder's durable store, where the other cameras' agents leave their reports."""
        self.fed, self.name, self.signer, self.term, self.wall = fed, name, signer, term, wall
        self.objects = objects
        self.backup_rev = 0
        self.backups = objects                           # where its own backups are written — read again on deposition
        self.restored_from: dict | None = None           # {term, rev} of the backup this term started from
        self.deposed_by: dict | None = None
        self.frozen_for: str | None = None               # the member a planned handover is moving the domain to

    @property
    def vars(self):
        return self.fed.clusters[self.name].vars

    def reported(self, member: str):
        """What the holder knows of another camera: its last report, in the holder's own store."""
        from .uplink import member_copy
        return member_copy(member, self.objects, wall=self.wall)

    def claim(self) -> None:
        doc = sign({"term": self.term, "host": self.name, "at": self.wall(),
                    **({"from": self.restored_from} if self.restored_from else {})}, self.signer.tokens)
        _, idx = self.vars.get(HOST)
        self.vars.put(HOST, {"doc": json.dumps(doc, sort_keys=True)}, cas=idx)

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
        self._settle_members()
        out = {}
        for prefix in EXPORTED:
            for path in self.vars.list(prefix):
                items, _ = self.vars.get(path)
                if items is not None:
                    out[path] = items
        return out

    # Publish the state beyond the holder: one signed document in the holder's durable store, and a pointer for
    # each member chosen to keep it, which that member's agent carries home as it carries the settings.
    # The list of members, if nobody ever wrote it, was the configuration of THIS holder's processes (`Members`); a
    # new holder restored without it would not know who its members are. So the first backup writes it — every
    # cluster of the site, this holder included: after a move it is a camera like the others, and the domain's
    # own cluster on the list is left alone by `members.apply`. From then on it is a record, exported with the rest.
    def _settle_members(self) -> None:
        from .members import MEMBERS, Members
        if self.vars.get(MEMBERS)[0] is None:
            Members(self.vars, self.wall, configured=lambda: sorted(self.fed.clusters)).settle()

    def backup(self, targets: list[str], objects) -> int:
        self._not_deposed()                              # a FROZEN holder still backs up: that is how it hands over
        self.backups = objects
        self.backup_rev += 1
        doc = sign({"term": self.term, "rev": self.backup_rev, "host": self.name, "at": self.wall(),
                    "state": self.export()}, self.signer.tokens)
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
    # loser finds out on its next look, exactly as a fenced worker does. It looks as any camera looks for the
    # holder at boot — opening the connections itself: the members that follow the new term report to the NEW
    # holder, so nothing about it would ever land in this one's store.
    #
    # Its OWN store first: this cluster is a member too, and its agent carries the holder record home like any
    # agent — a holder whose neighbours' doors are closed learns it was replaced from its own agent, or not at all.
    def check(self) -> bool:
        keys = self.signer.tokens.keyset()
        for name, c in [(self.name, self.fed.clusters[self.name]),
                        *[(n, c) for n, c in self.fed.clusters.items() if n != self.name]]:
            try:
                rec = read_holder(c.vars, keys, self.wall())
            except Unreachable:
                continue
            if rec and int(rec["term"]) > self.term:
                self.deposed_by = rec
                self._strand()
                return False
        return True

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
        left = stranded(self.vars, state)
        self.vars.put(STRANDED, {"doc": json.dumps({"term": self.deposed_by["term"], "host": self.deposed_by["host"],
                                                     "base": base, "items": left}, sort_keys=True, ensure_ascii=False)})

    def _own_backups(self) -> dict[int, dict]:
        """{rev: state} of the backups this holder wrote at its own term, from its own store."""
        out = {}
        if self.backups is None:
            return out
        for key in self.backups.list("backup/rev-"):
            raw = self.backups.get(key)
            try:
                doc = json.loads(raw)                    # its own, in its own store: read, not verified
            except (TypeError, ValueError):
                continue
            if int(doc.get("term", -1)) == self.term and doc.get("host") == self.name:
                out[int(doc["rev"])] = doc.get("state", {})
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
            raise Deposed(f"{self.name} held the domain at term {self.term}; {self.deposed_by['host']} holds it "
                          f"at term {self.deposed_by['term']} — edits go there")


# The agent's side: the holder record is carried like the keys, with one rule the keys never needed — it
# never goes BACKWARDS. An agent still pointed at an old holder that came back would otherwise carry that
# holder's smaller term over the larger one, and undo the move on every member it reached.
def carry_holder(domain_vars, member_vars, keys, now: float) -> str:
    items, _ = domain_vars.get(HOST)
    if not items:
        return "no holder record"
    try:
        incoming = verify(json.loads(items["doc"]), keys, now)
    except (NotTaken, ValueError, KeyError) as e:
        return f"refused: {e}"
    have = read_holder(member_vars, keys, now)
    if have and int(have["term"]) >= int(incoming["term"]):
        return "holding" if int(have["term"]) == int(incoming["term"]) else "holding a larger term"
    _, idx = member_vars.get(HOST)
    member_vars.put(HOST, dict(items), cas=idx)
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
        if not rec or rec["host"] != name:
            continue                                     # a member's CARRIED record is hearsay; only the holder's own claim counts here
        if best is None or int(rec["term"]) > int(best["term"]):
            best = rec
        elif int(rec["term"]) == int(best["term"]) and rec["host"] != best["host"]:
            raise TwoHolders(f"{rec['host']} and {best['host']} both claim term {rec['term']}: the domain was moved twice")
    return best["host"] if best else None


def move_domain(fed, new: str, signer_backup: bytes, domain_id: str, objects_of, wall=time.time) -> tuple[DomainHolder, dict]:
    """Move the domain on `new` from the signer's backup and the newest verified state any reachable
    member holds. `objects_of(member)` is that member's durable store."""
    now = wall()
    new_vars = fed.clusters[new].vars
    signer = Signer.restore(domain_id, new_vars, signer_backup, now=wall)
    keys = signer.tokens.keyset()
    top_term, best, ignored = 0, None, []
    for name, c in fed.clusters.items():
        try:
            rec = read_holder(c.vars, keys, now)
            ptr, _ = c.vars.get(BACKUP)
            raw = objects_of(name).get(BACKUP) if ptr else None
        except Unreachable:
            continue
        if rec:
            top_term = max(top_term, int(rec["term"]))
        if raw is None:
            continue
        try:
            doc = verify(json.loads(raw), keys, now)
        except (NotTaken, ValueError) as e:
            ignored.append((name, str(e)))
            continue
        if best is None or (int(doc["term"]), int(doc["rev"])) > (int(best[1]["term"]), int(best[1]["rev"])):
            best = (name, doc)
    if best:
        for path, items in best[1]["state"].items():
            _, idx = new_vars.get(path)
            new_vars.put(path, items, cas=idx)
    DomainPublisher(new_vars).publish_keys(keys)
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
    for name, c in fed.clusters.items():
        c.is_domain_holder = name == new
    holder = DomainHolder(fed, new, signer, top_term + 1, wall, objects=objects_of(new))
    holder.backup_rev = int(best[1]["rev"]) if best else 0
    holder.restored_from = {"term": int(best[1]["term"]), "rev": int(best[1]["rev"])} if best else None
    holder.claim()
    rev = holder.backup_rev
    report = {"term": holder.term, "restored_from": best[0] if best else None, "rev": rev, "ignored": ignored,
              "shared_from": shared_from,
              "state": best[1]["state"] if best else {},
              "sentence": (f"term {holder.term} on {new}: the domain's state from backup rev {rev}, held by {best[0]}; "
                           f"anything the old holder changed after rev {rev} is not here" if best else
                           f"term {holder.term} on {new}: no backup could be reached — the domain starts empty but for its keys")}
    return holder, report


# The domain's writes, behind the holder's guard: a kept edit (Lesson 9) is refused while the holder is frozen or
# deposed, as a 503 with the reason — the API's word for "not now, and here is why".
#
# Only ADDING is guarded. The other write to the same row — a member's report closing an edit (`reconcile`) —
# goes on during a handover, and that is not a hole (feedback AS): an edit the new term still holds as waiting
# is carried again, found already on the camera, and closed there by the camera's own report ("already").
# A closure is the camera's news, not the operator's decision; losing it costs one repeat, never an edit.
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


# A PLANNED handover: the holder is alive and the operator moves the domain to `to` — a camera being replaced,
# a server room arriving. It is the emergency move with the loss taken out, in four steps:
#
#     freeze        the old holder refuses writes, so nothing can be made after the backup that follows
#     last backup   to `to` itself, so the new holder restores from a copy that has EVERYTHING
#     carried       `to`'s agent takes it — verified, as any backup; if it does not, the handover is called
#                   off and the old holder unfreezes: nothing was claimed, nothing moved
#     move       the same `move_domain`; the old holder is reachable and reads the larger term on `to`, steps down
#
# The difference from the emergency path is the last line of the report: nothing stranded, because the
# freeze made sure there was nothing to strand.
def handover(holder: DomainHolder, to: str, signer_backup: bytes, domain_id: str, objects_of, carry_to,
             wall=time.time) -> tuple[DomainHolder, dict]:
    """`carry_to()` runs `to`'s agent once — in production, a nudge to the agent it would run anyway."""
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
        new, report = move_domain(holder.fed, to, signer_backup, domain_id, objects_of, wall)
    except Unreachable:                                  # it reported the backup, then went silent: not the new holder
        holder.frozen_for = None
        raise RuntimeError(f"{to} took backup rev {rev} and then stopped answering; the handover is called off and "
                           f"{holder.name} is still the holder")
    holder.check()
    left = (holder.stranded_items() or {}).get("items", [])
    report.update(planned=True, stranded=left,
                  sentence=f"planned handover: term {new.term} on {to}, the domain's state at rev {rev} from "
                           f"{holder.name}; " + ("nothing stranded" if not left else f"{len(left)} item(s) stranded — a write got past the freeze"))
    return new, report


# What an old holder that came back holds and the new term does not: every exported item that differs from
# the state the new holder was restored from. For a person to look at — never applied by anyone on its own.
#
# A kept edit counts only as an EDIT: its `rev` moved, or the new term has none for that camera. An entry that
# differs only because a report closed fields of it, or annotated a conflict or a refusal, is not stranded —
# the new term will carry the same edit and the camera will say "already" (see `GuardedPending`).
def stranded(old_vars, restored_state: dict) -> list:
    from .pending import PENDING_PATH
    out = []
    for prefix in EXPORTED:
        for path in old_vars.list(prefix):
            items, _ = old_vars.get(path)
            theirs = restored_state.get(path, {})
            for k, v in (items or {}).items():
                if theirs.get(k) == v:
                    continue
                if path.startswith(PENDING_PATH + "/") and k in theirs:
                    try:
                        if json.loads(v).get("rev") == json.loads(theirs[k]).get("rev"):
                            continue                     # the same edit, closed further here: not the operator's
                    except (TypeError, ValueError, AttributeError):
                        pass
                out.append([path, k, v])
    return out
