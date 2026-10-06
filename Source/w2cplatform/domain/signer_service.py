"""python3 -m w2cplatform.domain.signer_service — the domain's signer: the one process with the domain's keys, and the
holder's whole pass (ADR-0032).

Holds the keys (from domain/signer in the domain holder's store), publishes the key set and the revocation list for
the agents, publishes the identity set object-first on a floor, and answers logins with tokens. The CA half (issue,
renew, rotate) is driven by the registrar and by renewal requests over mTLS, which need the bench.

AND EVERYTHING OF THE HOLDER THAT WRITES (ADR-0032: every output of the holder's pass has one writer). Each pass, given
the domain's clusters (`CLUSTERS`): it looks whether it still holds the domain (`term.DomainHolder.check`), follows the
members and the topology, reads every member's report, closes kept edits by what the members say became of them, keeps
the week of alarms, seals the backup for the members chosen to keep it, and leaves the view (`domain/view`) — with what
this process alone knows: the term, whether a handover freezes it, the steps that fail, the rows it could not read.
The domain's console reads all of it and writes none of it.

Its door is the processes' (`/api/*`, `/revoke`, `/keys`) and the five operations that need the keys — each checked
HERE, the person's token and grant (or, for a move, the recovery file), the freeze of a handover, the operation's own
rules — whoever hands it on (the domain's console, which has no key, forwards a person's request as it came):

    POST /api/login           {"user","password"}         -> {"token"}
    POST /revoke              {"token"}                    -> revokes that token's jti
    GET  /keys                the key set (what agents copy)
    GET  /api/carry/<c>       what member <c> carries home, to the member alone, its secrets sealed to its key (`carry.py`)
    GET  /api/holder          the holder's claim about itself: {record, term, deposed[, deposed_by, stranded][,
                              frozen_for][, console]}; 404 for a domain that holds no term
    PUT  /api/shared          {base_rev, shared} — the shared settings, checked and signed (`Holder.shared`)
    POST /api/handover        {to} — a planned handover (`Holder.handover`: `term.handover`)
    POST /api/move            {recovery, stolen?} — the domain moved HERE, on the NEW holder, from the newest backup any
                              member holds (`Holder.move`: `term.move_domain`), checked by the recovery file; the
                              neighbours read over their consoles' doors (`/api/held`, `/api/backup`, `term.AskedCluster`)
    POST /api/prepare         the TARGET's half of a planned handover, asked by the holder of the current term (its
                              token key signs `prepare|<this cluster>|<time>`): a key of this signer's own for the
                              domain, kept aside here (`domain/signer-prepared`); the answer is its public halves
    POST /api/take            {grant, recovery_secret} — …and the taking: the outgoing holder's grant (signed by its
                              token key, naming this cluster and the backup rev it carried), its signer's keys sealed to
                              the prepared key; this signer moves the domain onto ITS OWN store (`Holder.take`:
                              `term.move_domain`) — the outgoing holder writes no store but its own (ADR 0001 §1.12)
    GET|POST /api/people/users, PUT|DELETE /api/people/users/<name>, GET /api/people/break-glass,
    PUT  /api/people/break-glass/<cluster> — the people with their passwords and the clusters' emergency passwords,
                              sealed with the ring (`Holder.people`)
    GET  /healthz             alive — what a monitor asks

The backup has no route: it is sealed by the pass (`Holder.backup`), with the backup key, and a pass that finds the
holder frozen or replaced seals nothing. No route signs what it is given.

Its keys, the people's hashes and the emergency hashes lie sealed under the platform's ring (`SECRETS_KEY`); at its
start it seals what it finds of the domain's and the people's rows in the clear, or under an older key (`w2cctl`).

The books a subsystem writes at the holder for its members are its own worker's pass (a spec's `domain.books`); the
tokens those books carry are of the kinds its spec declares, and the signer issues them on the worker's ask — the key
never leaves this process (`trust.tokens.DeclaredIssuer`).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler

from w2cplatform.canonical import parse_json
from w2cplatform.console import Deadlined, open_doors, read_body
from w2cplatform.rows import PARSE_ERRORS
from w2cplatform.trust.signer import DomainRoot, Signer
from w2cplatform.trust.tokens import RevocationList, TokenError, verify
from w2cplatform.variables import open_vars, store_url

from .agent import KEYS_PATH, DomainPublisher
from .identity import AuthError, IdentityStore

log = logging.getLogger("domain.signer")

# How often the pass seals a backup, at most (the product's `BackupEvery`): every pass would be a new revision every
# few seconds, carried home by every member chosen to keep it.
BACKUP_EVERY = 30.0
# How many members keep the domain's backup (the product's `BackupHolders`): chosen stably among the live ones.
BACKUP_HOLDERS = 2
# A person's password: ten characters at least (the product's rule, the page's words).
MIN_PASSWORD = 10
# The tables of what others wrote that the view counts (`w2cplatform.rows`): members' objects, grants, user records,
# and the trust rows a cluster holds — what this process could not read, shown on the domain's page.
GARBLED_SHOWN = ("member_object", "grant", "user", "trust_row")


class Holder:
    """The holder's pass and the five operations that need the domain's keys — the signer's, and nobody else's.

    `vars_`, `objects`: the holder's stores. `fed`: the domain as this process reads it (its own cluster, the members by
    their reports) — without it the pass is the identity set and the revocation list alone, a signer of the earlier
    lessons. `term`: the `term.DomainHolder` this signer holds the domain as (Lesson 15), or None for a domain that
    never moves or that this cluster does not hold. `hand_to(to)`: how a handover is made (`term.handover` with this
    process's means), None where it cannot be. `console_url`: where the domain's console answers — the view's `url`,
    where a cluster console hands `/domain/*`; `signer_url`: where this signer answers, said in the holder record a
    move here claims. `consoles`: the consoles of the domain's clusters, by name (`runtime.consoles_from_env`) — where a
    move reads its neighbours and a handover asks its target; None — the clusters of `fed` are read as they are (the
    lessons' site, one process).
    """

    def __init__(self, vars_, objects, signer: Signer, *, sealer=None, ids=None, revoked=None, pub=None, carry_door=None,
                 fed=None, view=None, members=None, topology=None, pending=None, alarms=None, term=None, hand_to=None,
                 journal=None, console_url: str | None = None, signer_url: str | None = None, wall=time.time,
                 backup_every: float = BACKUP_EVERY, backup_holders: int = BACKUP_HOLDERS, consoles: dict | None = None):
        from .steps import Steps
        self.vars, self.objects, self.signer = vars_, objects, signer
        self.sealer = sealer if sealer is not None else getattr(signer, "sealer", None)
        self.ids, self.revoked, self.pub, self.carry_door = ids, revoked, pub, carry_door
        self.fed, self.view, self.members, self.topology = fed, view, members, topology
        self.pending, self.alarms, self.term, self.hand_to = pending, alarms, term, hand_to
        self.journal, self.console_url, self.signer_url, self.wall = journal, console_url, signer_url, wall
        self.backup_every, self.backup_holders = backup_every, backup_holders
        self.consoles = consoles
        self.loop = Steps("domain signer", 5.0, log)
        self._backed_up: float | None = None             # when the pass last sealed a backup
        self._moving = threading.Lock()                  # one handover at a time

    # -- the pass ---------------------------------------------------------------------------------------------------
    def steps(self) -> list:
        """The holder's pass, step by step (`steps.Steps`): what one raises is said, counted, and stops only itself."""
        out = signer_steps(self.ids, self.revoked) if self.ids is not None else []
        if self.fed is None:
            return out
        if self.term is not None:
            out.append(("looking whether it still holds the domain", self.term.check))
        if self.members is not None:
            out.append(("following the members", self._follow_members))
        if self.topology is not None:
            out.append(("following the topology", self._follow_topology))
        if self.view is not None:
            out.append(("the read view's pass", self.view.refresh))
        if self.pending is not None:
            out.append(("collecting kept edits", lambda: self.pending.collect(self.fed)))   # what the members' reports say
        if self.alarms is not None:
            out.append(("keeping the week of alarms", self.alarms.keep))
        if self.term is not None:
            out.append(("sealing the backup", self.backup))
        if self.view is not None:
            out.append(("publishing the view", self.publish_view))
        return out

    def run_pass(self) -> dict:
        return self.loop.run(*self.steps())

    def _follow_members(self) -> None:
        from .members import apply
        apply(self.fed, self.members, self.objects, self.topology, wall=self.wall)

    def _follow_topology(self) -> None:
        from .topology import apply
        apply(self.fed, self.topology, self.objects, wall=self.wall)

    def tables(self) -> dict:
        """Every table a spec serves, as the holder keeps it: {`<sub>/<table>`: items}."""
        from . import declared
        out = {}
        for s in declared.specs():
            for t in s.domain.tables:
                items, _ = self.vars.get(f"{s.domain_prefix}{t}")
                out[f"{s.name}/{t}"] = dict(items or {})
        return out

    def extra(self) -> dict:
        """What the view carries beside the members' units: the records the domain keeps (the topology, the list of
        members and who knocks, the edits kept for members that are off and what became of them), where the domain's
        console is, the term — and what only this process knows: its steps that fail, the rows it could not read."""
        from w2cplatform.rows import counts
        out = {"url": self.console_url} if self.console_url else {}
        if self.topology is not None:
            out["topology"] = self.topology.read()
        if self.members is not None:
            out["member_list"] = self.members.read()
            out["knocking"] = self.members.knocking(self.objects)
        if self.pending is not None:
            # the edits kept for a cluster that is off (Lesson 9): waiting, or refused by the member — the course keeps
            # a member's outcome on the entry it answers, so `outcomes` are the refused ones
            out["pending"], out["outcomes"] = {}, {}
            for name, c in self.fed.clusters.items():
                if c.is_domain_holder:
                    continue
                entries = self.pending.of(name)
                waiting = [{"what": ref, "id": ref, "rev": e.get("rev"), "fields": sorted(e.get("fields") or {})}
                           for ref, e in entries.items() if not e.get("refused")]
                refused = [{"what": ref, "id": ref, "status": 409, "error": e["refused"]}
                           for ref, e in entries.items() if e.get("refused")]
                if waiting:
                    out["pending"][name] = waiting
                if refused:
                    out["outcomes"][name] = refused
        if self.term is not None:
            out["term"] = self.term_view()
        out["pass_failures"] = {**self.loop.said(), "by_step": dict(self.loop.by_step)}
        out["garbled_rows"] = {n: sum(c.values()) for n, c in counts().items() if n in GARBLED_SHOWN and c}
        return out

    def publish_view(self) -> dict:
        return self.view.publish(self.objects, self.tables(), self.extra())

    # -- the term ---------------------------------------------------------------------------------------------------
    def holder_says(self) -> dict | None:
        """`GET /api/holder`: the holder's claim about itself — its record, whether it was replaced and by whom and what
        it alone held, whether a handover freezes it now, and where its domain console is. None: no term here."""
        if self.term is None:
            return None
        from .agent import ClusterTrust, Untrusted
        from .term import read_holder
        try:
            keys = ClusterTrust(self.term.vars).keyset() or self.signer.tokens.keyset()
        except Untrusted:
            keys = self.signer.tokens.keyset()
        rec = read_holder(self.term.vars, keys, self.wall()) or {}
        out = {"record": {k: v for k, v in rec.items() if k not in ("sig", "kid")}, "term": self.term.term,
               "deposed": bool(self.term.deposed_by)}
        if self.term.deposed_by:
            out["deposed_by"] = {k: v for k, v in self.term.deposed_by.items() if k not in ("sig", "kid")}
            out["stranded"] = [{"path": p, "key": k, "value": v}
                               for p, k, v in (self.term.stranded_items() or {}).get("items", [])]
        if self.term.frozen_for:
            out["frozen_for"] = self.term.frozen_for
        if self.console_url:
            out["console"] = self.console_url
        return out

    def term_view(self) -> dict:
        """The term as the domain's page shows it (`view.term`): the claim, who keeps the backup, the last copy written
        (`backup: {term, rev}`) and the copy each member says it keeps (`copies`, `term.copies`) — the one place they
        are compared (ADR-0032) —, whom it can be handed to."""
        from .term import BACKUP, copies, last_written
        t = self.holder_says()
        t["backup_holders"] = sorted(p[len(BACKUP) + 1:] for p in self.vars.list(BACKUP + "/"))
        t["backup"] = last_written(self.vars)
        # every member on the list — a former backup holder, a former holder — and, where no list is kept (the
        # lessons' site), every cluster of it but this holder
        names = self.members.names() if self.members is not None else \
            [n for n in (self.fed.clusters if self.fed is not None else ()) if n != self.term.name]
        t["copies"] = copies(self.term, names)
        t["can_hand_to"] = self.hand_targets()
        return t

    def hand_targets(self) -> list[str]:
        """The members a planned handover can go to: the ones that can be ASKED to take the domain — the target moves it
        onto its own store, this holder writes none but its own (`term.handover`). A member with a console in
        `CLUSTERS` (`consoles`); every other member of `fed` where there are no consoles (the lessons' site)."""
        if self.term is None or self.hand_to is None or self.fed is None:
            return []
        return sorted(n for n in self.fed.clusters if n != self.term.name and (self.consoles is None or n in self.consoles))

    # THE FREEZE IS THE SIGNER'S TO CHECK (ADR-0032). Every operation that changes what the domain decided asks it
    # here, in this process, whoever handed the request on: frozen, a handover is under way and a write accepted now
    # would be made after its last backup — 503, seconds, not minutes; replaced, edits go to the new holder — 409. The
    # domain's console asks `/api/holder` too, but only to refuse early: the rule does not depend on it.
    def refusal(self) -> tuple[int, dict] | None:
        if self.term is None:
            return None
        from .term import Deposed, Frozen
        try:
            self.term.guard()
        except Deposed as e:
            return 409, {"detail": str(e), "holder": self.term.deposed_by.get("holder")}
        except Frozen as e:
            return 503, {"detail": str(e), "frozen_for": self.term.frozen_for}
        return None

    def _person(self, token: str | None, capability: str) -> tuple[str | None, tuple[int, dict] | None]:
        """Who is asking, checked here: a person's token of the domain, and `capability` on the domain."""
        from w2cplatform.trust.tokens import PERSON
        from .grants import domain_may
        if not token:
            return None, (401, {"detail": "an operation of the domain names its person: a token of the domain"})
        revoked = set(self.revoked.entries) if self.revoked is not None else set()
        try:
            who = verify(token, self.signer.tokens.keyset(), revoked, now=self.wall(), kind=PERSON)["sub"]
        except TokenError as e:
            return None, (401, {"detail": f"token refused: {e}"})
        if not domain_may(self.vars, who, capability, self.wall()):
            return None, (403, {"detail": f"{who} has no {capability} on the domain"})
        return who, None

    def _say(self, kind: str, **fields) -> None:
        if self.journal is not None:
            self.journal.say(kind, **fields)

    # -- the five operations ----------------------------------------------------------------------------------------
    def shared(self, token: str | None, body: dict) -> tuple[int, dict]:
        """`PUT /api/shared`: a person's edit of the shared settings, checked and signed (`edit_shared`)."""
        who, no = self._person(token, "admin")
        if no:
            return no
        refused = self.refusal()
        if refused:
            return refused
        revoked = set(self.revoked.entries) if self.revoked is not None else set()
        st, out = edit_shared(self.vars, self.objects, self.signer.tokens, self.signer.tokens.keyset(), revoked, token,
                              body, self.wall())
        if st == 200:
            self._say("domain.shared.edited", user=who, target="shared", rev=out["rev"])
        return st, out

    def handover(self, token: str | None, body: dict) -> tuple[int, dict]:
        """`POST /api/handover {to}`: a planned handover — freeze, the last backup to `to`, `to`'s agent takes it, the
        move, this holder steps down (`term.handover`). Made by the process that holds the keys; called off, it
        unfreezes and nothing moved."""
        who, no = self._person(token, "admin")
        if no:
            return no
        if self.term is None or self.hand_to is None:
            return 404, {"detail": "this domain holds no term here: there is nothing to hand over"}
        refused = self.refusal()
        if refused:
            return refused
        to = body.get("to")
        if not isinstance(to, str) or to not in self.hand_targets():
            return 400, {"detail": f"the domain is handed to a member whose store this holder writes: "
                                   f"{', '.join(self.hand_targets()) or 'none'}"}
        if not self._moving.acquire(blocking=False):
            return 503, {"detail": f"a handover is under way already ({self.term.frozen_for}): seconds, not minutes"}
        try:
            refused = self.refusal()
            if refused:
                return refused
            try:
                new, report = self.hand_to(to)
            except RuntimeError as e:
                self._say("domain.handover.called_off", user=who, target=to, why=str(e))
                return 409, {"detail": str(e)}
        finally:
            self._moving.release()
        self._say("domain.handover", user=who, target=to, term=report["term"], stranded=len(report.get("stranded", [])))
        return 200, {"term": report["term"], "rev": report.get("rev"), "to": to, "sentence": report["sentence"],
                     "stranded": [{"path": p, "key": k, "value": v} for p, k, v in report.get("stranded", [])]}

    # THE MOVE IS THE NEW HOLDER'S, AND THE RECOVERY FILE IS ITS AUTHORITY (ADR-0032's addition). A handover is asked of
    # the holder that leaves, by a person with a grant on the domain it holds. When that holder is gone — dead, stolen —
    # there is nobody to ask and no grant to read: the holder kept them. So the move is made on the member that is to
    # hold the domain, by its own signer, and what it checks is the file the operator kept beyond the holder (Lesson 7,
    # Lesson 15, step 9): the domain's root, or — for a domain whose root is the holder's own — the signer's backup.
    # It wraps `term.move_domain` whole; nothing else moves a domain (`handover` ends in the same function).
    def move(self, body: dict) -> tuple[int, dict]:
        """`POST /api/move {recovery, stolen?}`: the domain moved onto this signer's cluster, from the newest verified
        backup any reachable member holds and the largest term any carries. `recovery`: the file, as its text. `stolen`:
        the old holder's keys dropped at once, its issuing certificates revoked, every member's LDevID signed again —
        a root's recovery file only. Refused: 404 with no domain to read; 503 while a handover from this holder is
        under way (the freeze, as for the other operations); 409 while this cluster holds the domain; 400 for a body
        that is not the move's; 403 for a file that is not this domain's. Returns the move's report."""
        from w2cplatform.trust.signer import is_recovery_file
        if self.fed is None:
            return 404, {"detail": "this signer reads no domain (CLUSTERS): there is nowhere to move it from"}
        refused = self.refusal()
        if refused and refused[0] == 503:
            return refused
        me = self.fed.domain_holder.name
        if self.term is not None and not self.term.deposed_by:
            return 409, {"detail": f"{me} holds the domain at term {self.term.term}: there is nothing to move here"}
        raw, stolen = body.get("recovery"), body.get("stolen", False)
        if not isinstance(raw, str) or not raw or not isinstance(stolen, bool):
            return 400, {"detail": "a move is {recovery: <the recovery file, as its text>, stolen?: true | false}"}
        blob = raw.encode()
        if stolen and not is_recovery_file(blob):
            return 400, {"detail": "a stolen holder is answered by the root's recovery file: the signer's backup holds "
                                   "the stolen keys themselves"}
        fed = self.neighbours()
        why = self._not_the_domains(blob, me, fed)
        if why:
            return 403, {"detail": why}
        if not self._moving.acquire(blocking=False):
            return 503, {"detail": "a move is under way already: seconds, not minutes"}
        try:
            from .federation import Unreachable
            from .term import move_domain
            try:
                new, report = move_domain(fed, me, blob, self.signer.domain, lambda n: fed.clusters[n].objects,
                                          self.wall, stolen=stolen, sealer=self.sealer)
            except (ValueError, RuntimeError, Unreachable) as e:
                return 409, {"detail": f"the domain was not moved: {e}"}
            self._took(new)
        finally:
            self._moving.release()
        self._say("domain.moved", user="recovery file", target=me, term=report["term"], stolen=stolen,
                  reissued=len(report.get("reissued") or []))
        return 200, {k: report.get(k) for k in ("term", "rev", "restored_from", "keys_rev", "stolen", "reissued",
                                                "shared_from", "sentence")}

    # THE NEIGHBOURS, AS A MOVE HERE READS THEM: this cluster's own stores, and every other cluster over its console's
    # doors (`term.AskedCluster`: `/api/held`, and `/api/backup` signed by this cluster's member key) — never a store of
    # theirs. A cluster `CLUSTERS` gives no console is read as `fed` reaches it (a cluster read directly; the lessons).
    def neighbours(self):
        if not self.consoles:
            return self.fed
        from w2cplatform.trust.memberkey import MemberKey
        from .federation import Federation
        from .term import AskedCluster
        me = self.fed.domain_holder
        try:
            key = MemberKey.load(me.vars, self.sealer)
        except Exception:                                # noqa: BLE001 — a key that does not open: no backup is asked
            key = None
        fed = Federation()
        fed.add(me)
        for name, c in self.fed.clusters.items():
            if name == me.name:
                continue
            fed.add(AskedCluster(name, self.consoles[name], me.name, key, wall=self.wall) if name in self.consoles else c)
        for name, console in self.consoles.items():
            if name not in fed.clusters:
                fed.add(AskedCluster(name, console, me.name, key, wall=self.wall))
        return fed

    def _not_the_domains(self, blob: bytes, me: str, fed=None) -> str | None:
        """Why `blob` is not this domain's recovery file — None when it is. A root's: some member holds a key set that
        root signed (`term._trusted_keys`). The signer's backup: the key set this cluster holds names its token key, by
        the same public half."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from w2cplatform.trust.signer import DomainRoot, is_recovery_file
        from .agent import ClusterTrust, Untrusted
        from .term import _trusted_keys
        try:
            if is_recovery_file(blob):
                root = DomainRoot.restore(self.signer.domain, blob, now=self.wall)
                if _trusted_keys(fed or self.fed, me, root, self.wall()).rev == 0:
                    return "no member holds a key set this root signed: it is not this domain's recovery file"
                return None
            d = json.loads(blob)
            pub = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(d["token_key_secret"])).public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            kid = d["kid"]
        except (*PARSE_ERRORS, ValueError):
            return "the file is neither the domain's recovery file nor the signer's backup"
        try:
            keys = ClusterTrust(self.fed.clusters[me].vars).keyset()
        except Untrusted as e:
            return f"{me} cannot read the key set it holds ({e}): nothing to check the file against"
        if keys is None or keys.keys.get(kid) != pub:
            return f"the key set {me} holds does not name this backup's key: it is not this domain's signer"
        return None

    # THE TARGET'S HALF OF A PLANNED HANDOVER (ADR-0032: `handover` is checked by the outgoing holder's grant; contract
    # §10a: `/api/prepare`, `/api/take` are processes' doors, handed here by this cluster's console). The outgoing holder
    # writes no store but its own (ADR 0001 §1.12): it asks THIS signer to prepare, then to take — and the move onto
    # this cluster's store is made here, by `term.move_domain`, as an emergency move is.
    PREPARED = "domain/signer-prepared"                 # `domain/signer*`: the signer's alone, never an agent's or a console's

    def _current_holder_signed(self, message: bytes, signature: str | None) -> str | None:
        """Why `signature` is not by the holder of the current term — None when it is: its token key, the current key
        of the key set this cluster carries (the key only that holder holds)."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from .agent import ClusterTrust, Untrusted
        try:
            keys = ClusterTrust(self.vars).keyset()
        except Untrusted as e:
            return f"the key set this cluster carries does not read ({e})"
        if keys is None or not keys.current or keys.current not in keys.keys:
            return "this cluster carries no key set: it knows no holder to take the domain from"
        try:
            Ed25519PublicKey.from_public_bytes(keys.keys[keys.current]).verify(bytes.fromhex(signature or ""), message)
        except Exception:                                # noqa: BLE001 — anything that does not verify is not the holder
            return "not signed by the holder of the current term"
        return None

    def prepare(self, at, signature: str | None) -> tuple[int, dict]:
        """`POST /api/prepare`, signed by the holder of the current term (`prepare|<this cluster>|<time>`): a key of this
        signer's own for the domain, made now and kept aside here, sealed with the ring; the answer is its public
        halves — the outgoing holder seals its keys to `seal`. Anybody else: 403, and nothing is made or replaced."""
        from w2cplatform.sealing import seal_items
        from w2cplatform.trust.memberkey import MemberKey
        from .carry import SKEW
        from .term import prepare_message
        if self.fed is None:
            return 404, {"detail": "this signer reads no domain (CLUSTERS): there is nothing to prepare for"}
        me = self.fed.domain_holder.name
        if self.term is not None and not self.term.deposed_by:
            return 409, {"detail": f"{me} holds the domain at term {self.term.term}: it is handed from here, not to here"}
        try:
            at = float(at)
        except (TypeError, ValueError):
            return 403, {"detail": "a prepare names its time (X-W2C-Time) and is signed by the holder (X-W2C-Signature)"}
        why = self._current_holder_signed(prepare_message(me, at), signature)
        if why:
            return 403, {"detail": why}
        if not (abs(self.wall() - at) <= SKEW):
            return 403, {"detail": f"the ask is {self.wall() - at:+.0f} s from this cluster's clock: more than {SKEW:.0f} s"}
        key = MemberKey.new()
        _, idx = self.vars.get(self.PREPARED)
        self.vars.put(self.PREPARED, seal_items(self.sealer, {"seed_secret": key.seed.hex(), "seal_pub": key.seal_pub,
                                                              "at": str(at)}, self.PREPARED), cas=idx)
        return 200, {"cluster": me, "seal": key.seal_pub, "pub": key.pub}

    def _prepared(self):
        from w2cplatform.sealing import open_row
        from w2cplatform.trust.memberkey import MemberKey
        items, _ = self.vars.get(self.PREPARED)
        if not items or not items.get("seed_secret"):
            return None
        try:
            return MemberKey(bytes.fromhex(open_row(self.sealer, items, self.PREPARED)["seed_secret"]))
        except Exception:                                # noqa: BLE001 — a key that does not open is none prepared
            return None

    def take(self, body: dict) -> tuple[int, dict]:
        """`POST /api/take {grant, recovery_secret}`: the domain moved onto this cluster's store, handed by the holder of
        the current term. `grant`: signed by that holder's token key — `{grant: "handover", to: <this cluster>, term,
        rev}`, the backup rev this cluster's agent carried; `recovery_secret`: that holder's signer's keys (Lessons
        4–7: the domain's own), sealed to the key `/api/prepare` made. The prepared key is used once. Returns the move's
        report and the record this cluster claimed."""
        from w2cplatform.trust.documents import NotTaken, verify as verify_doc
        from w2cplatform.trust.memberkey import NotMine
        from w2cplatform.trust.signer import is_recovery_file
        from .agent import ClusterTrust, Untrusted
        from .term import BACKUP_TAKEN, HOLDER
        if self.fed is None:
            return 404, {"detail": "this signer reads no domain (CLUSTERS): there is nothing to take"}
        refused = self.refusal()
        if refused and refused[0] == 503:
            return refused
        me = self.fed.domain_holder.name
        if self.term is not None and not self.term.deposed_by:
            return 409, {"detail": f"{me} holds the domain at term {self.term.term}: there is nothing to take"}
        grant, sealed = body.get("grant"), body.get("recovery_secret")
        if not isinstance(grant, dict) or not isinstance(sealed, str):
            return 400, {"detail": "a take is {grant: <the outgoing holder's, signed>, recovery_secret: <sealed>}"}
        key = self._prepared()
        if key is None:
            return 409, {"detail": f"nothing is prepared on {me}: the holder asks POST /api/prepare first"}
        try:
            blob = key.open("recovery_secret", sealed, f"take|{me}").encode()
            kid = json.loads(blob)["kid"]
        except (NotMine, *PARSE_ERRORS) as e:
            return 403, {"detail": f"the keys handed over do not open with the key prepared here: {e}"}
        if is_recovery_file(blob):
            return 400, {"detail": "a handover hands on the signer's own keys; a domain whose root is off the holder is "
                                   "moved by its recovery file (POST /api/move)"}
        try:
            keys = ClusterTrust(self.vars).keyset()
            g = verify_doc(grant, keys, self.wall())
        except (Untrusted, NotTaken) as e:
            return 403, {"detail": f"the grant does not verify: {e}"}
        if g.get("grant") != "handover" or g.get("to") != me or g.get("kid") != kid or kid != keys.current:
            return 403, {"detail": f"the grant is no handover to {me} by the holder whose keys it hands on"}
        why = self._not_the_domains(blob, me)
        if why:
            return 403, {"detail": why}
        ptr, _ = self.vars.get(BACKUP_TAKEN)
        if not ptr or str(ptr.get("rev")) != str(g.get("rev")) or str(ptr.get("term")) != str(g.get("term")):
            return 409, {"detail": f"{me} did not take backup rev {g.get('rev')} of term {g.get('term')}: the handover "
                                   f"restores from nothing older"}
        if not self._moving.acquire(blocking=False):
            return 503, {"detail": "a move is under way already: seconds, not minutes"}
        try:
            from .federation import Unreachable
            from .term import move_domain
            fed = self.neighbours()
            try:
                new, report = move_domain(fed, me, blob, self.signer.domain, lambda n: fed.clusters[n].objects,
                                          self.wall, sealer=self.sealer)
            except (ValueError, RuntimeError, Unreachable) as e:
                return 409, {"detail": f"the domain was not taken: {e}"}
            self._took(new)
            _, idx = self.vars.get(self.PREPARED)
            self.vars.put(self.PREPARED, {"taken": f"term {new.term}"}, cas=idx)   # used once
        finally:
            self._moving.release()
        self._say("domain.taken", user=g.get("from") or "holder", target=me, term=report["term"])
        record = json.loads(self.vars.get(HOLDER)[0]["doc"])
        return 200, {**{k: report.get(k) for k in ("term", "rev", "restored_from", "shared_from", "sentence")},
                     "record": record}

    def _took(self, new) -> None:
        """This process holds the domain now: the new term, its signer for everything it signs from here on (the
        people's tokens too), and — for a signer whose root is its own — a handover's means again."""
        new.url = self.signer_url
        if new.record is None and self.signer_url:
            new.claim()                                  # the record says where this signer answers
        self.term, self.signer = new, new.signer
        if self.ids is not None:
            self.ids.signer = new.signer
        if self.pub is not None and self.revoked is not None:
            self.pub.publish_revoked(self.revoked)
        self.hand_to = (lambda to: move_by_handover(self, to, new.signer.domain, new.signer)) if not new.signer.chain \
            else None

    def backup(self) -> int | None:
        """The pass's backup: the domain's state, its secrets sealed with the backup key, signed, and a pointer for each
        member chosen to keep it. None — nothing sealed — while a handover freezes the holder (its own backup, to its
        target, is the last), once it was replaced, before `backup_every` has passed, or with nobody to keep it."""
        if self.term is None or self.refusal() is not None:
            return None
        now = self.wall()
        if self._backed_up is not None and now - self._backed_up < self.backup_every:
            return None
        targets = self.backup_targets()
        if not targets:
            return None
        rev = self.term.backup(targets, self.objects)
        self._backed_up = now
        return rev

    def backup_targets(self) -> list[str]:
        """`backup_holders` members the view reads now, chosen stably (by a hash of the holder's name and theirs), so
        the same members keep the copy pass after pass."""
        if self.view is None:
            return []
        down, behind = self.view.cluster_down_since, self.view.rpo()
        live = [n for n, c in self.fed.clusters.items()
                if not c.is_domain_holder and n not in down and behind.get(n) is not None]
        live.sort(key=lambda n: hashlib.sha256(f"{self.term.name}/{n}".encode()).hexdigest(), reverse=True)
        return live[:self.backup_holders]

    def people(self, method: str, rest: str, token: str | None, body: dict) -> tuple[int, dict]:
        """`/api/people/<rest>`: the people with their passwords and the clusters' emergency passwords — rows sealed
        with the ring, so written here. `view` on the domain to read them, `admin` to change them."""
        who, no = self._person(token, "view" if method == "GET" else "admin")
        if no:
            return no
        if method != "GET":
            refused = self.refusal()
            if refused:
                return refused
        if self.ids is None:
            return 503, {"detail": "this signer keeps no people"}
        kind, _, name = rest.partition("/")
        if kind == "users":
            return self._users(method, name, who, body)
        if kind == "break-glass":
            return self._break_glass(method, name, who, body)
        return 404, {"detail": "no such route"}

    # The codes by the architect's rule: 409 when the refusal depends on rows that exist (a person under a subject's
    # name, one that exists, the last admin), 400 when the request is wrong by the spec alone (a grant wider than a
    # family's declared `grant` — no write of the people's makes one, every grant a person loses is narrower; said all
    # the same).
    def _users(self, method: str, name: str, who: str, body: dict) -> tuple[int, dict]:
        from .declared import GrantTooWide, NameTaken
        from .grants import BadName, LastAdmin
        if method == "GET" and not name:
            return 200, {"users": [{"name": u.id, "how": "oidc" if u.kind == "idp" else "password", "roles": u.roles,
                                    "at": u.created} for u in self.ids.users()]}
        if method == "POST" and not name:
            uid, password, roles = body.get("name"), body.get("password"), body.get("roles", [])
            if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
                return 400, {"detail": "roles are a list of names"}
            if not isinstance(password, str) or len(password) < MIN_PASSWORD:
                return 400, {"detail": f"a password is {MIN_PASSWORD} characters at least"}
            try:
                self.ids.create_local(uid, password, roles, by=who)
            except (BadName, TypeError, GrantTooWide) as e:
                return 400, {"detail": str(e)}
            except NameTaken as e:
                return 409, {"detail": str(e)}
            except ValueError as e:                      # it exists
                return 409, {"detail": str(e)}
            return 200, {"user": uid}
        u = self.ids.get(name) if name else None
        if u is None or u.kind == "deleted":
            return 404, {"detail": f"no user {name}"}
        if method == "DELETE":
            try:
                self.ids.delete(name, by=who)
            except LastAdmin as e:
                return 409, {"detail": str(e)}
            except GrantTooWide as e:
                return 400, {"detail": str(e)}
            return 200, {"user": name, "deleted": True}
        if method != "PUT":
            return 405, {"detail": "PUT {password?, roles?} or DELETE /domain/users/<name>"}
        if "disabled" in body:
            return 400, {"detail": "a person of this domain is not disabled: delete them, or take their grants away"}
        password, roles = body.get("password"), body.get("roles")
        if password is None and roles is None:
            return 400, {"detail": "PUT {password?, roles?}"}
        if password is not None:
            if not isinstance(password, str) or len(password) < MIN_PASSWORD:
                return 400, {"detail": f"a password is {MIN_PASSWORD} characters at least"}
            try:
                self.ids.set_password(name, password, by=who)
            except KeyError:
                return 400, {"detail": f"{name} logs in through the identity provider: no password here"}
        if roles is not None:
            if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
                return 400, {"detail": "roles are a list of names"}
            self.ids.set_roles(name, roles, by=who)
        return 200, {"user": name}

    def _break_glass(self, method: str, cluster: str, who: str, body: dict) -> tuple[int, dict]:
        from .agent import BREAK_GLASS_PATH
        from .breakglass import set_password
        from .grants import name_refused
        if method == "GET" and not cluster:
            out = {}
            for path in self.vars.list(BREAK_GLASS_PATH + "/"):
                items, _ = self.vars.get(path)
                try:
                    out[path[len(BREAK_GLASS_PATH) + 1:]] = {"set_at": float((items or {}).get("set_at"))}
                except PARSE_ERRORS:
                    out[path[len(BREAK_GLASS_PATH) + 1:]] = {"set_at": None}
            return 200, {"clusters": out}
        if method != "PUT" or not cluster:
            return 405, {"detail": "PUT /domain/break-glass/<cluster> {password}"}
        why = name_refused(cluster, "cluster's name", also="/")
        if why:
            return 400, {"detail": why}
        password = body.get("password")
        if not isinstance(password, str) or not password:
            return 400, {"detail": "name the new emergency password"}
        set_password(self.vars, cluster, password, self.wall(), self.sealer, journal=self.journal, by=who)
        return 200, {"cluster": cluster, "set": True}

    # -- the door ---------------------------------------------------------------------------------------------------
    def handler(self):
        holder = self
        vars_, ids, revoked, pub = self.vars, self.ids, self.revoked, self.pub

        # THE LOGIN DOOR IS ANYBODY'S, SO IT IS BOUNDED (М10's sixth review: "every HTTP door in the code base"). Whoever
        # reaches it has proved nothing yet — that is what it is for — and it was a thread for every connection, no
        # deadline on a request, and a body read to whatever `Content-Length` said. The platform's server and reading
        # (`ConsoleServer`, `Deadlined`, `read_body`): so many connections at once and so many to one address, the
        # request line and headers under a deadline, a body of a name and a password — `MAX_BODY`, no more.
        #
        # …AND WITH THE CONSOLE'S RESERVE AND THE BOX'S LANE (М10's seventh review, major). Four addresses took every
        # connection of it; its bounds are the console's now (`Bounds`), with the box's own door a unix socket when
        # `SIGNER_UNIX` names one (`open_doors`). The reserve is for the door in — `/api/login`, and its preflight — and
        # a listed monitor (`CONSOLE_MONITORS`) is answered on `/healthz`.
        class H(Deadlined, BaseHTTPRequestHandler):
            MAX_BODY = 16 << 10
            RESERVE = ("/api/login",)

            def parse_request(self):
                return super().parse_request() and not self.busy_unless(self.RESERVE, self.path.split("?", 1)[0])

            def _send(self, status, body):
                raw = json.dumps(body).encode()
                self.send_response(status); self.send_header("Content-Type", "application/json")
                self._cors()
                self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

            # A cluster console's page logs a person in HERE, from its own origin (`w2cplatform/console.html`): the
            # password goes to the signer and only the token goes back to the console. So the login door answers a
            # page on another origin. Any origin: what the door gives is a token for credentials the person typed,
            # and it gives the same to `curl`; it sets no cookie and reads none, so there is nothing of this origin
            # for another site's page to ride on.
            def _cors(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

            def _token(self):
                auth = self.headers.get("Authorization", "")
                return auth[7:] if auth.startswith("Bearer ") else None

            # The body, an object — or None, the 400 already sent. The door in is anybody's, and so is its body (the
            # ninth review's sweep of "a garbage token is 500, not 401").
            def _body(self):
                if self.command in ("GET", "DELETE") and not int(self.headers.get("Content-Length") or 0):
                    return {}
                if not read_body(self, self.MAX_BODY):
                    return None
                try:
                    # the platform's one reading (`canonical.parse_json`): a body not UTF-8, a lone surrogate, `1e400`
                    # are 400 with the shared table's `fault` (the architect, 2026-10-06)
                    body = parse_json(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                except PARSE_ERRORS as e:
                    self._send(400, {"detail": "the body is a JSON object", "fault": getattr(e, "fault", "") or "not_json"})
                    return None
                if not isinstance(body, dict):
                    self._send(400, {"detail": "the body is a JSON object"})
                    return None
                return body

            def do_OPTIONS(self):
                self.send_response(204); self._cors(); self.send_header("Content-Length", "0"); self.end_headers()

            def do_GET(self):
                if self.path == "/healthz":
                    return self._send(200, {"ok": True, **holder.loop.said()})   # what is failing in its loop, said (the eighth pass)
                if self.path == "/keys":
                    return self._send(200, vars_.get(KEYS_PATH)[0] or holder.signer.tokens.keyset().to_items())
                if self.path == "/api/holder":
                    said = holder.holder_says()
                    return self._send(200, said) if said is not None else self._send(404, {"detail": "this domain holds no term"})
                if self.path.startswith("/api/people/"):
                    return self._send(*holder.people("GET", self.path[len("/api/people/"):], self._token(), {}))
                if self.path.startswith("/api/carry/") and holder.carry_door is not None:
                    from urllib.parse import parse_qs, urlsplit
                    from .carry import Refused
                    u = urlsplit(self.path)
                    try:
                        got = holder.carry_door.carry(u.path[len("/api/carry/"):], float(self.headers.get("X-W2C-Time", "nan")),
                                                      self.headers.get("X-W2C-Seal", ""), self.headers.get("X-W2C-Signature", ""),
                                                      (parse_qs(u.query).get("for") or [None])[0])
                    except ValueError:
                        return self._send(400, {"detail": "an ask names its time"})
                    except Refused as e:
                        return self._send(e.status, {"detail": e.detail})
                    return self._send(200, got)
                self._send(404, {"detail": "no such route"})

            def do_POST(self):
                body = self._body()
                if body is None:
                    return
                try:
                    if self.path == "/api/login" and ids is not None:
                        user, password = body.get("user"), body.get("password")
                        if not isinstance(user, str) or not isinstance(password, str):
                            return self._send(400, {"detail": "a login names a user and a password, both strings"})
                        return self._send(200, {"token": ids.login(user, password)})
                    if self.path == "/revoke" and revoked is not None:
                        revoked.revoke(verify(body.get("token"), holder.signer.tokens.keyset()))
                        if pub is not None:
                            pub.publish_revoked(revoked)
                        return self._send(200, {"revoked": True})
                except AuthError:
                    return self._send(401, {"detail": "bad credentials"})
                except TokenError as e:
                    return self._send(401, {"detail": f"token refused: {e}"})
                if self.path == "/api/handover":
                    return self._send(*holder.handover(self._token(), body))
                if self.path == "/api/move":
                    return self._send(*holder.move(body))         # checked by the file it carries, not by a token
                if self.path == "/api/prepare":                   # …by the current holder's signature
                    return self._send(*holder.prepare(self.headers.get("X-W2C-Time"), self.headers.get("X-W2C-Signature")))
                if self.path == "/api/take":                      # …by its grant and the key prepared here
                    return self._send(*holder.take(body))
                if self.path.startswith("/api/people/"):
                    return self._send(*holder.people("POST", self.path[len("/api/people/"):], self._token(), body))
                self._send(404, {"detail": "no such route"})

            def do_PUT(self):
                body = self._body()
                if body is None:
                    return
                if self.path == "/api/shared":
                    return self._send(*holder.shared(self._token(), body))
                if self.path.startswith("/api/people/"):
                    return self._send(*holder.people("PUT", self.path[len("/api/people/"):], self._token(), body))
                self._send(404, {"detail": "no such route"})

            def do_DELETE(self):
                body = self._body()
                if body is None:
                    return
                if self.path.startswith("/api/people/"):
                    return self._send(*holder.people("DELETE", self.path[len("/api/people/"):], self._token(), body))
                self._send(404, {"detail": "no such route"})

            def log_message(self, *a):
                pass

        return H


def main() -> None:
    from w2cplatform import runtime
    from w2cplatform.journal import Journal
    from .runtime import open_objects
    domain = os.environ.get("DOMAIN_ID", "domain")
    # The domain holder's store: its configstore by the domain's own socket, unless `PLATFORM_STORE` says otherwise;
    # the role `domain` is one of the two that may delete `domain/*` rows (`storemachine.DOMAIN_ROLES`).
    vars_ = open_vars(store_url(os.environ, "configstore:///run/configstore/domain.sock"))
    from w2cplatform.sealing import Sealer
    from w2cplatform.w2cctl import DOMAIN_PREFIXES, seal as seal_stored
    sealer = Sealer.from_env(os.environ)
    seal_stored(vars_, sealer, DOMAIN_PREFIXES)
    objects = open_objects(os.environ.get("OBJECTS", "file:///data/platform/objects"))   # the platform's, `w2c.env`
    pub = DomainPublisher(vars_)
    # Lesson 15, step 9: a domain whose root stays off the holder. The installer points RECOVERY_FILE at the root
    # for the FIRST start only: the holder's issuing certificate and the first key set are signed, and the file
    # goes back to the operator. From then on the signer holds its own keys, and the key set is the root's —
    # never overwritten here by one of its own, which members that pinned the root would refuse.
    recovery = os.environ.get("RECOVERY_FILE")
    if vars_.get("domain/signer")[0] is None and recovery:
        with open(recovery, "rb") as f:
            root = DomainRoot.restore(domain, f.read())
        signer = Signer(domain, vars_, root=root, sealer=sealer)
        pub.publish_keys(root.key_set(signer.tokens.keyset(), rev=1, issuing=[signer.root.cert.serial_number]))
    else:
        signer = Signer(domain, vars_, sealer=sealer)
        # A first start publishes its own key set. A start on a MEMBER — a signer waiting for a move here
        # (`Holder.move`) — finds the domain's key set its agent carried, and leaves it: over it, a key set of its own
        # would make the cluster trust nobody but itself, and the move could not check the file against what it holds.
        if not signer.chain and vars_.get(KEYS_PATH)[0] is None:
            pub.publish_keys(signer.tokens.keyset())
    # Its own lines of the journal, as role `domain` — who changed the people, the shared settings, who handed the domain
    # on; the domain's console writes its own (`domainconsole`). Where it was told to (`runtime.events_said`).
    journal = Journal(runtime.events_said(os.environ), "domain", time.time)
    ids = IdentityStore(signer, vars_, objects, publish_floor=float(os.environ.get("IDENTITY_PUBLISH_FLOOR", "60")),
                        sealer=sealer, journal=journal)
    from .carry import HolderDoor
    holder = Holder(vars_, objects, signer, sealer=sealer, ids=ids, revoked=revocations(vars_), pub=pub,
                    carry_door=HolderDoor(vars_, objects, sealer), journal=journal,
                    console_url=os.environ.get("CONSOLE_URL") or
                    f"http://127.0.0.1:{os.environ.get('CONSOLE_PORT', '8443')}",
                    signer_url=os.environ.get("SIGNER_URL") or None)
    if os.environ.get("CLUSTERS"):
        holder_pass(holder, domain, signer)
    srv = open_doors(os.environ.get("SIGNER_HOST", "0.0.0.0"), int(os.environ.get("SIGNER_PORT", "8445")),
                     holder.handler(), unix_env="SIGNER_UNIX", say=False)
    # The tokens a subsystem's books carry, on the holder's own socket only (`tokendoor.py`): of the kinds the loaded
    # specs declare, asked by the subsystem's worker that writes the books — the key stays here.
    if os.environ.get("SIGNER_TOKENS_UNIX"):
        from w2cplatform.console import UnixConsoleServer
        from w2cplatform.trust.tokens import DeclaredIssuer
        from . import declared, tokendoor
        class Current:                                   # the key the holder signs with NOW: a move here changes it
            def __getattr__(self, name):
                return getattr(holder.signer.tokens, name)
        tokens_door = UnixConsoleServer(os.environ["SIGNER_TOKENS_UNIX"],
                                        tokendoor.handler(DeclaredIssuer(Current(), declared.token_kinds())), srv.bounds)
        threading.Thread(target=tokens_door.serve_forever, daemon=True).start()
    stop = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    while not stop.is_set():
        holder.run_pass()
        stop.wait(float(os.environ.get("REFRESH_INTERVAL", "5")))
    srv.shutdown()


# THE HOLDER'S PASS, WIRED (ADR-0032): what the domain's console ran before — the members, the topology, the read view,
# the kept edits — and what nobody ran outside the lessons: the week of alarms kept, the term looked at and the backup
# sealed. The domain as `CLUSTERS` names it (`runtime.federation_from_env`); the term from the holder record in the
# store, when a domain was installed with one (Lesson 15) — a domain that never moves holds none.
def holder_pass(holder: Holder, domain: str, signer: Signer) -> None:
    from .alarms import AlarmHistory, DomainAlarms, ReportedDoor
    from .members import Members
    from .pending import PendingEdits
    from .readview import ReadView
    from .runtime import consoles_from_env, federation_from_env
    from .topology import Topology
    from .uplink import _CopyObjects
    fed = federation_from_env()
    holder.consoles = consoles_from_env() or None        # where a move reads its neighbours and a handover asks
    lost_after = float(os.environ.get("LOST_AFTER", "45"))
    configured = [n for n, c in fed.clusters.items() if isinstance(c.objects, _CopyObjects)]
    hv, ho = fed.domain_holder.vars, fed.domain_holder.objects
    holder.fed, holder.view = fed, ReadView(fed, lost_after=lost_after)
    holder.members = Members(hv, configured=lambda: configured, domain=fed.domain_holder.name)
    holder.topology, holder.pending = Topology(hv), PendingEdits(hv)
    holder.alarms = DomainAlarms(fed, lambda m: ReportedDoor(m, ho, lost_after), lost_after=lost_after,
                                 history=AlarmHistory(ho))
    holder.term = term_of(fed, signer, ho, holder.signer_url)
    if holder.term is not None and not signer.chain:
        holder.hand_to = lambda to: move_by_handover(holder, to, domain, signer)


def term_of(fed, signer: Signer, objects, url: str | None = None):
    """The term this signer holds the domain at: the holder record in its store, verified — or None, a domain that was
    never installed with one. Started as a holder process starts (`DomainHolder.start`): it looks before it claims."""
    from .agent import ClusterTrust, Untrusted
    from .term import HOLDER, DomainHolder, read_holder
    hv = fed.domain_holder.vars
    if hv.get(HOLDER)[0] is None:
        return None
    try:
        keys = ClusterTrust(hv).keyset() or signer.tokens.keyset()
    except Untrusted:
        keys = signer.tokens.keyset()
    rec = read_holder(hv, keys, time.time())
    if rec is None or rec.get("holder") != fed.domain_holder.name:
        return None
    from w2cplatform.trust.tokens import ROOT_KID
    root_signed = rec.get("kid") == ROOT_KID                 # a record the root signed is not this signer's to sign again
    items, _ = hv.get(HOLDER)
    term = DomainHolder(fed, fed.domain_holder.name, signer, int(rec["term"]), objects=objects,
                        record=json.loads(items["doc"]) if root_signed else None)
    term.restored_from = rec.get("from")
    term.url = url
    term.start()
    return term


def _post(url: str, body: dict, headers: dict | None = None, timeout: float = 10.0) -> tuple[int, dict]:
    import urllib.error
    import urllib.request
    from .federation import Unreachable
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    except OSError as e:
        raise Unreachable(f"{url} did not answer: {e}") from None
    try:
        said = json.loads(raw or b"{}")
    except PARSE_ERRORS:
        said = {}
    return status, said if isinstance(said, dict) else {}


def move_by_handover(holder: Holder, to: str, domain: str, signer: Signer):
    """`term.handover` with this process's means: for `to`'s agent to take the last backup, a wait for its report to
    say so; then `to` is ASKED to take the domain at its console (`CLUSTERS`), which hands it to its signer — prepare
    (signed by this holder's token key), then take (the grant, and this signer's own keys sealed to the key `to`
    prepared; a domain whose root is off the holder has no such keys here — no handover then). This process writes
    no store of `to`'s."""
    from .term import BACKUP_TAKEN, handover
    wait = float(os.environ.get("HANDOVER_WAIT", "80"))
    t = holder.term

    def carry_to():
        until = time.monotonic() + wait
        while time.monotonic() < until:
            try:
                ptr, _ = t.reported(to).vars.get(BACKUP_TAKEN)
            except Exception:                            # noqa: BLE001 — not reported yet: wait on
                ptr = None
            if ptr and int(ptr.get("rev", -1)) == t.backup_rev and int(ptr.get("term", -1)) == t.term:
                return
            time.sleep(0.5)

    return handover(t, to, lambda n: holder.fed.clusters[n].objects, carry_to,
                    asked_to_take((holder.consoles or {}).get(to), to, t, signer))


def asked_to_take(console: str | None, to: str, t, signer: Signer):
    """The `take` of `term.handover` over doors: `to`'s console (`CLUSTERS`) hands both asks to `to`'s signer — prepare,
    signed by this holder's token key; then take, with the grant and this signer's own keys sealed to the key `to`
    prepared. `(None, report)`: the report `to` answered, the record it claimed in it. `RuntimeError`: not taken."""
    from w2cplatform.trust.documents import sign
    from w2cplatform.trust.memberkey import seal_to
    from .term import prepare_message

    def take():
        if not console:
            raise RuntimeError(f"CLUSTERS gives {to} no console: there is nobody to ask to take the domain; the handover "
                               f"is called off and {t.name} is still the holder")
        at = time.time()
        st, pubs = _post(console.rstrip("/") + "/api/prepare", {}, {
            "X-W2C-Time": f"{at:.3f}", "X-W2C-Signature": signer.tokens.key.sign(prepare_message(to, at)).hex()})
        if st != 200 or not isinstance(pubs.get("seal"), str):
            raise RuntimeError(f"{to} did not prepare ({st}: {pubs.get('detail', '')}); the handover is called off and "
                               f"{t.name} is still the holder")
        grant = sign({"grant": "handover", "to": to, "from": t.name, "term": t.term, "rev": t.backup_rev,
                      "at": time.time()}, signer.tokens)
        sealed = seal_to(pubs["seal"], "recovery_secret", signer.backup().decode(), f"take|{to}")
        st, rep = _post(console.rstrip("/") + "/api/take", {"grant": grant, "recovery_secret": sealed}, timeout=90.0)
        if st != 200:
            raise RuntimeError(f"{to} did not take the domain ({st}: {rep.get('detail', '')}); the handover is called "
                               f"off and {t.name} is still the holder")
        return None, rep
    return take


# THE SHARED SETTINGS ARE SIGNED WHERE THE KEY IS, AND CHECKED THERE (ADR-0032: the key's process performs the operation
# whole; a «sign me this» door would sign anything for whoever reaches it). `PUT /api/shared {base_rev, shared: {<sub>:
# {<field>: value | null}}}` is a person's edit with its intent: the signer checks the person (a token of the domain, an
# `admin` on it), the revision the edit was made against and the specs' declarations (`SharedSettings.edit`:
# `domain.shared`, each field and document by its schema), builds the document itself and signs it. The domain's
# console, which has no key, hands the person's edit on here as it came (`console.Console`, `PUT /domain/shared`).
# Returns `(status, body)`. The freeze of a handover is `Holder.shared`'s to check, before this.
#
# ONE OPERATION OVER WHAT THE SPECS DECLARE (ADR-0032's addition): no field is known here by what it means — a document
# a spec declares (`{name, type: json, schema}`) is taken as JSON, an object or the text of one, and checked by its
# schema like any field with one; the words of a refusal are the schema's.
def edit_shared(vars_, objects, issuer, keyset, revoked, token: str | None, body: dict, now: float) -> tuple[int, dict]:
    from w2cplatform.trust.tokens import PERSON
    from w2cplatform.variables import Conflict

    from .api import ApiError
    from .grants import domain_may
    from .shared import SharedSettings
    from .term import HOLDER
    if not token:
        return 401, {"detail": "an edit of the shared settings names its person: a token of the domain"}
    try:
        who = verify(token, keyset, revoked, now=now, kind=PERSON)["sub"]
    except TokenError as e:
        return 401, {"detail": f"token refused: {e}"}
    if not domain_may(vars_, who, "admin", now):
        return 403, {"detail": f"{who} is not an admin of the domain: the shared settings are the domain's"}
    shared, base = body.get("shared"), body.get("base_rev")
    if not isinstance(shared, dict) or not all(isinstance(v, dict) for v in shared.values()) or \
            isinstance(base, bool) or not isinstance(base, int):
        return 400, {"detail": "the edit is {base_rev: <the revision it was made against>, shared: {<sub>: {<field>: "
                               "value or null}}}"}

    # a document a spec declares is taken AS IT IS: reading a form's text box is the page's work before it sends (the
    # architect with «Паритет», 2026-10-06, (б)) — a string is a document that is a string

    def mutate(settings: dict) -> None:
        held = settings.setdefault("shared", {})
        for sub, values in shared.items():
            mine = held.setdefault(sub, {})
            for f, v in values.items():
                if v is None:
                    mine.pop(f, None)                        # null takes the domain's value away
                else:
                    mine[f] = v
            if not mine:
                held.pop(sub)

    def term() -> int:
        try:
            return int(json.loads((vars_.get(HOLDER)[0] or {})["doc"]).get("term", 1))
        except (KeyError, *PARSE_ERRORS):
            return 1
    try:
        rev = SharedSettings(vars_, objects, issuer, wall=lambda: now, term=term).edit(mutate, base, by=who)
    except Conflict as e:
        return 409, {"detail": str(e)}
    except ApiError as e:
        return e.status, {"detail": e.detail}
    return 200, {"rev": rev, "by": who}


# THE SIGNER'S LOOP, STEP BY STEP (the review's eighth pass, major). It was two `try` blocks with `except Exception: pass`
# — the same silence the domain console's loop had and lost in the seventh pass: one torn relay bundle stopped the pass
# over the books, and nobody saw it; and a failed publication of the identity set skipped the pruning of the
# revocation list behind it. Now each is a step of its own (`Steps`): what raises is logged with its trace once until
# it works again, counted, named on `/healthz`, and the steps after it run. The rest of the holder's pass follows them
# (`Holder.steps`).
def signer_steps(ids, revoked) -> list:
    return [("publishing the identity set", ids.publish),         # object first, then the pointer, on a floor
            ("pruning the revocation list", lambda: revoked.prune(time.time()))]


# The revocation list the signer starts from (the review's seventh pass left the signer's start open: one torn entry
# and it did not start — nobody logged in anywhere). Entry by entry: an entry whose expiry is not a number stays
# revoked, with no end (`RevocationList.from_items`). A row of another shape altogether is said, and the signer starts
# with an empty list — revocations last as long as the tokens they name, and a signer that does not start lets nobody in.
def revocations(vars_) -> RevocationList:
    try:
        return RevocationList.from_items(vars_.get("domain/revoked")[0])
    except PARSE_ERRORS as e:
        log.error("domain/revoked does not parse (%s): the signer starts with no revocations; tokens revoked before now "
                  "are honoured again until they expire — revoke them again", e)
        return RevocationList()


if __name__ == "__main__":
    main()
