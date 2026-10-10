"""The domain agent: one small process per cluster whose only right is to
write domain/* in that cluster's store — the way a worker's only right is to
write its epochs and its slot, and the controller's is its subsystem's rows.

It carries what a cluster needs from the domain and nothing else: the signer's
public key set, the revocation list, the grants for THIS cluster, and the rows
each subsystem's spec says a member carries (`domain.books`), moved as they are,
without reading them. When the domain is unreachable it stops updating; the
cluster's console and doors keep verifying with the keys they have, issued
tokens run to expiry, grants run to theirs, nobody new logs in — the bounded
outage the services table promises, with the mechanism named. Workers are not
involved: nothing about a user reaches a worker, ever.
"""
from __future__ import annotations

import logging
import threading
import time

from w2cplatform.rows import PARSE_ERRORS
from w2cplatform.trust.tokens import ROOT_KID, TRUST_ROWS, KeySet, RevocationList
from w2cplatform.variables import Variables

from . import declared
from .federation import Unreachable

log = logging.getLogger("domain.agent")

KEYS_PATH, REVOKED_PATH, GRANTS_PATH = "domain/keys", "domain/revoked", "domain/grants"
# Lesson 15: the domain root's public key, PINNED in each member — written once, never replaced by the agent.
# In production it comes with enrollment (the trust bundle of Lesson 6); here the first root-signed key set pins it.
ROOT_PATH = "domain/root"
# …and the member's LDevID, issued again by a new holder after its issuing certificate was revoked.
LDEVID_PATH = "domain/ldevid"
# When this member last reached the domain — through a relay, when that relay last did (Lesson 17) — in its own object
# store, written every pass (`seen_store`: RAM on a small box, whose flash is not written every pass). What a
# subsystem's process reads to judge the age of the books its agent carried, without the books themselves changing.
DOMAIN_SEEN = "domain/seen"
# The emergency account's password HASH for one cluster (Lesson 4, step 7): set at the domain, carried home, checked
# at the cluster's console with the domain away — which is the only time it is for.
BREAK_GLASS_PATH = "domain/break_glass"
# That this cluster IS a member — written on every pass that leaves a key set here, so the cluster's console can tell
# "the keys were lost" from "there never were any" (`w2cplatform/access.py`, `DOMAIN_MARKS`). The other marks are each
# conditional — `domain/root` only with a root-signed key set, grants and the rest only when the domain has some for
# this cluster — and a member with none of them looked, keys gone, like a cluster that never joined: open (the review's
# fourth pass). This one has no condition but the keys themselves.
MEMBER_PATH = "domain/member"
# What the domain decided for ONE cluster, each a row of the same kind: written by the domain under `<path>/<cluster>`,
# carried home to `<path>`. The platform's own, and every book a subsystem's spec declares (`declared.books`).
PLATFORM_PER_CLUSTER = (LDEVID_PATH, BREAK_GLASS_PATH)


def per_cluster() -> tuple[str, ...]:
    return (*PLATFORM_PER_CLUSTER, *declared.books())


class DomainPublisher:
    """The signer's side: writes the key set and the revocation list into
    the domain HOLDER's Variables, where agents read them."""

    def __init__(self, domain_vars: Variables):
        from .declared import guarded
        self.vars = guarded(domain_vars)     # a grant wider than a subject family's `grant` is refused (ADR-0031)

    def publish_keys(self, ks: KeySet | dict) -> None:
        """A key set, or — Lesson 15 — the items `DomainRoot.key_set` signed."""
        _, idx = self.vars.get(KEYS_PATH)
        self.vars.put(KEYS_PATH, ks if isinstance(ks, dict) else ks.to_items(), cas=idx)

    def publish_revoked(self, rl: RevocationList) -> None:
        _, idx = self.vars.get(REVOKED_PATH)
        self.vars.put(REVOKED_PATH, rl.to_items(), cas=idx)

    def publish_break_glass(self, cluster: str, pwhash: str, now: float, sealer=None) -> None:
        """The one local account of `cluster`: its password's hash, never the password, sealed under the holder's ring
        (`pwhash_secret`). Rotating it is publishing a new one (`breakglass.set_password`)."""
        from .carry import seal_row
        path = f"{BREAK_GLASS_PATH}/{cluster}"
        _, idx = self.vars.get(path)
        self.vars.put(path, seal_row(sealer, {"pwhash_secret": pwhash, "set_at": now}, path), cas=idx)

    def publish_grants(self, cluster: str, grants: list) -> None:
        """The grants for one cluster, under domain/grants/<cluster> in the
        domain holder's Variables; the cluster's agent copies them home."""
        from .grants import grants_to_items
        path = f"{GRANTS_PATH}/{cluster}"
        have, idx = self.vars.get(path)
        self.vars.put(path, grants_to_items(grants, was=have, where=path), cas=idx)   # an old name there blocks nothing (the ninth review)


class HolderFollower:
    """WHICH MEMBER HOLDS THE DOMAIN, AS A MEMBER'S AGENT WORKS IT OUT BY ITSELF (Lesson 15; «Архитектор» 2026-10-06).
    A move writes the new holder's own store and nobody else's (ADR 0001 §1.12): no member is told. So the agent asks
    every cluster of the domain — `CLUSTERS`, the one declaration; the domain recruits nobody and there is no list of
    candidates — for the holder's record that cluster holds (`GET /api/held` at its console, `term.held`), and follows
    the record with the GREATEST term that verifies against the key set this member carries (`term.verified_record`:
    signed by a key it trusts, by the root once a root is pinned). A record proves itself, so it does not matter which
    cluster says it — the new holder's own claim, or a member that carried it already. A forged or unsigned record of
    any term is not counted; a cluster that does not answer is skipped; two holders claiming one term are followed by
    nobody, said. Never backwards: a record smaller than the one this member holds changes nothing (`take_record`).

    `ask`: `{cluster: callable() -> the /api/held answer}` — over HTTP in production (`ask_held`), a cluster's store
    read through its door in the lessons; `Unreachable` (or anything that is not an answer) skips that cluster."""

    def __init__(self, ask: dict):
        self.ask = dict(ask)

    def best(self, keys, now: float) -> tuple[dict | None, str]:
        """The verified record of the greatest term any cluster holds, and what was found — or None and why."""
        import json
        from .term import verified_record
        best, heard, forged = None, [], []
        for name, ask in sorted(self.ask.items()):
            try:
                said = ask()
                doc = said.get("holder") if isinstance(said, dict) else None
            except Unreachable:
                continue
            except PARSE_ERRORS:
                continue
            heard.append(name)
            if not doc:
                continue
            rec = verified_record(doc, keys, now)
            if rec is None:
                forged.append(name)
                continue
            if best is None or int(rec["term"]) > int(best["term"]):
                best = rec
            elif int(rec["term"]) == int(best["term"]) and rec["holder"] != best["holder"]:
                return None, f"{rec['holder']} and {best['holder']} both claim term {rec['term']}: followed by nobody"
        if best is None:
            return None, ("no cluster answered" if not heard else "no cluster holds a record this member can verify"
                          + (f" (refused from {', '.join(forged)})" if forged else ""))
        return json.loads(json.dumps(best)), (f"term {best['term']} on {best['holder']}"
                                              + (f"; a record that does not verify refused from {', '.join(forged)}"
                                                 if forged else ""))


def ask_held(console: str, timeout: float = 3.0):
    """`GET <console>/api/held` — a cluster console's process door: the holder's record that cluster holds. A console that
    does not answer, or answers no object, is `Unreachable` to the follower."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(console.rstrip("/") + "/api/held", timeout=timeout) as r:
            raw = r.read(1 << 20)
        said = json.loads(raw)
    except (OSError, *PARSE_ERRORS) as e:
        raise Unreachable(f"{console}: {e}") from None
    if not isinstance(said, dict):
        raise Unreachable(f"{console}: /api/held answered no object")
    return said


class DomainAgent:
    def __init__(self, cluster: str, domain_vars: Variables, cluster_vars: Variables, now=time.time,
                 console=None, current=None, domain_objects=None, cluster_objects=None, seen_store=None,
                 published=None, pages=None, bundle_members=None, bundle_store=None, relay_members=None, alarm_waiting=None,
                 reaches=None, own_objects=None, sealer=None, key=None, follow: HolderFollower | None = None,
                 open_door=None):
        """`console` and `current` are Lesson 9: this cluster's console, which writes its rows, and
        `current(ref) -> (id, row)` for a unit by the domain's name. Given them, the agent also applies
        the edits the domain kept while this cluster was off. Without them it only carries them home.

        `domain_objects` and `cluster_objects` are Lesson 12: where the domain publishes documents, and
        this cluster's DURABLE object store, where the agent keeps the copy it verified. Given them, it
        carries the shared settings home.

        `seen_store` is Lesson 13: where the agent says when it last reached the domain (`domain/seen`), so
        the books it carried can be judged by their age without the books themselves changing. On a small
        box it is RAM — this is written on every pass, and flash is not.

        `published` and `pages` are the uplink (`domain/uplink.py`): this member's own object store, where
        its workers publish, and a callable returning the pages it is asked to show (Lesson 14). Given
        them, every pass ends with a REPORT into the domain holder's object store — the domain never opens
        a connection to this member; this pass is the only one there is, and it carries both ways.

        `domain_vars` is where the pass reads what this member carries (`carry.py`): a door — `carry.CarryClient`, a
        relay's `relay.Relay(...).vars` — whose answer is this member's own rows, its secrets sealed to `key` (this
        member's `trust.memberkey.MemberKey`); or the holder's store itself, on the holder's own box and in the tests,
        read through the same `carry.answer`: its own rows and nothing else. `sealer`: this member's key ring — every
        secret the agent writes into its own store is sealed with it (`carry.seal_row`).

        `follow` and `open_door` are Lesson 15: the agent follows the holder by itself (`HolderFollower`) — every pass
        it asks the domain's clusters for the record of the greatest term, carries it home, and when it names another
        holder, `open_door(record)` gives the door to carry through from now on: `(domain_vars, domain_objects)`, or None
        where the record names no door (the agent keeps the one it has)."""
        self.cluster, self.domain_vars, self.cluster_vars, self.now = cluster, domain_vars, cluster_vars, now
        self.follow, self.open_door = follow, open_door
        self.holder_at: str | None = None                  # the holder whose door this agent carries through, once known
        self.followed = ""                                 # what the last pass found of the holder
        self.sealer, self.key = sealer, key
        self.relayed: dict[str, dict] = {}                 # a relay: what the domain answered for each member it relays
        self.console, self.current = console, current
        self.domain_objects, self.cluster_objects = domain_objects, cluster_objects
        self.seen_store = seen_store
        self.published, self.pages = published, pages
        # An agent in another process than the card cannot be woken by it (feedback AZ: the product's agent is its own
        # process). `alarm_waiting(since)` — is there an alarm newer than the last page reported? — is asked instead,
        # once a second by the loop (`due`). In one process the card's `on_alarm` still wakes it at once.
        self.alarm_waiting, self._paged_at = alarm_waiting, None
        # Lesson 17's summary report: a relay's agent folds the reports its members left in `bundle_store`
        # (this cluster's object store) into one object in the domain holder.
        self.bundle_members, self.bundle_store = bundle_members, bundle_store
        # …and it RELAYS down what the domain leaves for those members (`chain.relay`): the relay is their only
        # road to the domain. `bundle_store` is the relay's object store, where both halves live.
        self.relay_members = relay_members
        # What this cluster can see — `reaches()`, from its interfaces or its site — said in its own object store
        # (`own_objects`, or the one it reports from), where the domain reads it. Written only when it changes.
        self.reaches, self.own_objects = reaches, own_objects if own_objects is not None else published
        self.reported = ""                                  # what the last pass did with the report
        self.shared = self.backup = self.holder = self.keys = ""   # what the last pass did with each document
        self.last_synced: float | None = None
        self.syncs = 0
        # An alarm on the card wakes the agent (Lesson 14): the report goes now, not at the next pass — half a
        # minute is long enough for the box that saw the door forced to be broken before it reported it. The
        # card only sets this; the agent's own loop reports, so two threads never sync at once.
        self.woken = threading.Event()
        self._urgent_at: float | None = None
        self._relay_n, self._relay_seen = None, None      # through a relay: its last age mark, on OUR clock

    # One row home, by CAS, only when what it SAYS changed: a secret in it is sealed afresh every time (a new nonce), so
    # the row as stored is compared opened — or the member's flash would be written every pass for nothing.
    def _carry(self, path: str, items: dict | None, clear: bool = False) -> None:
        from .carry import open_row, seal_row
        have, idx = self.cluster_vars.get(path)
        if items is None and not clear:
            return
        items = items or {}
        try:
            said = open_row(self.sealer, have, path) if have else have
        except Exception:                                   # noqa: BLE001 — what is there does not open: written anew
            said = None
        if said != items and not (have is None and not items):
            self.cluster_vars.put(path, seal_row(self.sealer, items, path), cas=idx)

    # The key set, carried with one rule per lesson. Lesson 4: as it is — the channel was the trust. Lesson 15:
    # once this member has a root pinned, only a key set that root SIGNED, and never an older revision than it
    # holds. A holder carried off the wall has the token key and can sign anything with it — but not as the
    # root: a key set of its own, published to members it can still reach, is refused, and says why.
    #
    # A key set from the domain that does not parse is REFUSED like one that does not verify, and the one carried
    # before is held (the review's eighth pass: `json.loads(items["doc"])` raised out of the pass — nothing after the
    # keys was carried, and the report that is this member's sign of life was not written). A pinned root this member
    # cannot read trusts nothing: refused too, said — the member is enrolled again.
    def _carry_keys(self, items: dict | None) -> str:
        try:
            return self._carry_keys_parsed(items)
        except Untrusted as e:
            return f"refused: {e}"
        except PARSE_ERRORS as e:
            return f"refused: the domain's key set does not parse ({e}); holding the one carried before"

    def _carry_keys_parsed(self, items: dict | None) -> str:
        import json
        from w2cplatform.trust.documents import NotTaken, verify
        if items is None:
            return "no key set"
        trust = ClusterTrust(self.cluster_vars)
        pinned = trust.root()
        if "doc" not in items:
            if pinned is not None:
                return "refused: a key set not signed by the domain's root"
            KeySet.from_items(items)                        # carried as it is — but only one that reads
            self._carry(KEYS_PATH, items)
            return "carried"
        doc = json.loads(items["doc"])
        if pinned is not None and doc.get("root") != pinned.hex():
            return "refused: signed by a root this member did not pin"   # said first: it is the reason a person can act on
        root = pinned if pinned is not None else bytes.fromhex(doc.get("root", ""))
        try:
            verify(doc, KeySet(current="", keys={ROOT_KID: root}), self.now())
        except NotTaken as e:
            return f"refused: {e}"
        if doc.get("root") != root.hex() or doc.get("kid") != ROOT_KID:
            return "refused: signed by a root this member did not pin"
        KeySet.from_items(items)                            # signed, and readable as a key set
        try:
            have = trust.keyset()
        except Untrusted:
            have = None                                     # the copy here does not read: the root's signed set replaces it
        if have is not None and have.root is not None and int(doc["rev"]) < have.rev:
            return f"holding rev {have.rev}"
        if pinned is None:
            self.cluster_vars.put(ROOT_PATH, {"pub": root.hex()})
        self._carry(KEYS_PATH, items)
        return f"rev {doc['rev']}"

    def say_reaches(self) -> bool:
        if self.reaches is None or self.own_objects is None:
            return False
        import json
        from .federation import REACHES
        raw = json.dumps({"networks": sorted(set(self.reaches()))}).encode()
        if self.own_objects.get(REACHES) == raw:
            return False
        self.own_objects.put(REACHES, raw)
        return True

    URGENT_GAP = 1.0                                        # a storm is one report a second, not one per line

    def wake(self) -> None:
        """An alarm was written: report as soon as the loop can."""
        self.woken.set()

    def due(self) -> bool:
        """Woken — or an alarm newer than the last page reported — and the last urgent report was at least
        `URGENT_GAP` ago: report now."""
        if not self.woken.is_set() and self.alarm_waiting is not None and self._paged_at is not None \
                and self.alarm_waiting(self._paged_at):
            self.woken.set()
        if not self.woken.is_set():
            return False
        return self._urgent_at is None or self.now() - self._urgent_at >= self.URGENT_GAP

    def report_now(self) -> bool:
        """The loop's answer to `wake`: one pass, marked as urgent."""
        self.woken.clear()
        self._urgent_at = self.now()
        return self.sync()

    def sync(self) -> bool:
        """One pass. False (and nothing written) if the domain did not answer."""
        self.say_reaches()                                  # local: said even when the domain is away
        ok = self._sync()
        if self.relay_members and self.bundle_store is not None:
            from .relay import say_seen                     # a relay: how current its relay is, reached or not
            say_seen(self.bundle_store, self.last_synced, self.now())
        return ok

    def _relay_mark(self) -> float | None:
        mark = self.domain_vars.seen()                     # None when it does not parse (`relay.RelayLink.seen`)
        if mark and mark.get("n") != self._relay_n:
            self._relay_n = mark.get("n")
            self._relay_seen = None if mark.get("age") is None else self.now() - float(mark["age"])
        return self._relay_seen

    # What this member carries, as the door answered (`carry.py`): its own rows, the public ones, the documents they
    # point at — its secrets opened by its own key. The holder's store itself (the holder's own agent, the tests) is read
    # through the same `answer`, so no member's pass ever reads another member's rows.
    def _answer(self) -> dict:
        from .carry import answer
        if hasattr(self.domain_vars, "answer_for"):
            return self.domain_vars.answer_for(self.cluster, self.key)
        return answer(self.domain_vars, self.domain_objects, self.cluster)

    def _sync(self) -> bool:
        from .carry import CarriedObjects, CarriedVars, Refused
        from .pending import OUTCOMES_PATH, PENDING_PATH, apply_pending
        if self.follow is not None:                        # Lesson 15: where the domain is held now — asked first
            self.followed = self._step("following the holder", self._follow)
        try:
            got = self._answer()
        except Unreachable:
            return False
        except Refused as e:                               # the door said no: said once, the last carried rows stand
            self.keys = f"refused by the domain's door: {e.detail}"
            self._say_refused("the door", self.keys)
            return False
        self._say_refused("the door", "")
        dv, do = CarriedVars(got.get("rows", {})), CarriedObjects(got.get("objects", {}), report_to=self.domain_objects)
        self._carried_seen = got.get("seen")
        keys, _ = dv.get(KEYS_PATH)
        revoked, _ = dv.get(REVOKED_PATH)
        grants, _ = dv.get(f"{GRANTS_PATH}/{self.cluster}")
        pending, _ = dv.get(f"{PENDING_PATH}/{self.cluster}")
        # What the domain decided for THIS cluster in the later lessons — each one more row of the same
        # kind: written by the domain under `<path>/<cluster>`, carried home to `<path>`.
        later = [(path, dv.get(f"{path}/{self.cluster}")[0]) for path in per_cluster()]
        self.keys = self._carry_keys(keys)
        self._say_refused("the key set", self.keys)
        from .members import MEMBERS
        from .term import MEMBER_LIST
        from .topology import TOPOLOGY
        # …and the list of members, under a name of this cluster's (`term.MEMBER_LIST`): its console knows a member by it
        # when one asks for the backup copy kept here (`GET /api/backup`)
        for path, items in ((REVOKED_PATH, revoked), (GRANTS_PATH, grants), (TOPOLOGY, dv.get(TOPOLOGY)[0]),
                            (MEMBER_LIST, dv.get(MEMBERS)[0]), *later):
            self._carry(path, items)
        # Edits the domain kept while this cluster was off (Lesson 9) — carried home even when there are
        # none left, because an edit the domain has cleared must stop being applied here. Then applied, by
        # this cluster's console and as the operator who made each one, and what happened written where the
        # domain reads it. The agent writes `domain/*` and nothing else; the row is the console's.
        self._carry(PENDING_PATH, pending, clear=True)
        if self.console is not None and self.current is not None:
            import json
            from .pending import _load
            entries = _load(pending if isinstance(pending, dict) else None, PENDING_PATH)   # one entry that does not parse: that unit's
            outcomes = apply_pending(entries, self.current, self.console, self.now())
            self._carry(OUTCOMES_PATH, {k: json.dumps(v, ensure_ascii=False, sort_keys=True)
                                        for k, v in outcomes.items()}, clear=True)
        # The shared settings (Lesson 12), checked against the key set this pass just carried — the member's
        # own, never one that came with the document.
        # And Lesson 15: which member holds the domain — carried like the keys, but never to a smaller term —
        # and, on the members chosen to keep it, the backup of the domain's state, carried like the settings.
        #
        # Each of these three is its own step (the review's eighth pass): a pointer or a record from the domain that does
        # not parse raised out of the pass, and the report below — the member's sign of life — was not written; the
        # domain then called a member silent whose only trouble was one row the domain itself wrote. Now it is refused,
        # said in what the pass did (`holder`, `shared`, `backup`) and in the log once, and the pass goes on.
        from .term import BACKUP, BACKUP_TAKEN, carry_holder
        try:
            keyset = ClusterTrust(self.cluster_vars).keyset()
        except Untrusted:
            keyset = None
        if keyset is not None:
            self._carry(MEMBER_PATH, {"cluster": self.cluster})   # written when missing — after a rollback too — and only then
        try:
            self.holder = self._step("the holder record", lambda: carry_holder(
                dv, self.cluster_vars, keyset, self.now()) if keyset else "no keys yet")
            if self.cluster_objects is not None:
                from .shared import carry
                self.shared = self._step("the shared settings", lambda: carry(
                    dv, do, self.cluster_vars, self.cluster_objects, keyset, self.now()))
                self.backup = self._step("the backup", lambda: carry(
                    dv, do, self.cluster_vars, self.cluster_objects, keyset, self.now(),
                    src=f"{BACKUP}/{self.cluster}", dst=BACKUP_TAKEN, obj=BACKUP_TAKEN, refused=f"{BACKUP}-refused"))
        except Unreachable:
            return False
        self.last_synced = self.now()
        self.syncs += 1
        if self.seen_store is not None:
            import json
            # Through a relay (Lesson 17), "when did I last hear from the domain" is when the RELAY last did: a
            # member that reaches its relay every pass while the relay is cut from the centre has current
            # nothing, and must not believe its books are.
            seen = self._relay_mark() if hasattr(self.domain_vars, "seen") else self.last_synced
            self.seen_store.put(DOMAIN_SEEN, json.dumps({"ts": seen or 0.0, "cluster": self.cluster}).encode())
        # Up, on the same connection: what the domain reads of this member, left where it reads it. Last,
        # so the outcomes of the edits applied above go up in this same pass.
        if self.published is not None and self.domain_objects is not None:
            from .uplink import NotPublished, report
            try:
                paged_at = self.now()
                n = report(self.cluster, self.cluster_vars, self.published, self.domain_objects, paged_at,
                           self.pages() if self.pages else None, key=self.key)
                self._paged_at = paged_at
                self.reported = f"reported ({n} written)"
            except NotPublished as e:
                self.reported = str(e)
            except Unreachable:
                self.reported = "the domain did not take the report"
                return False
        if self.relay_members and self.bundle_store is not None:
            from .relay import relay_down
            try:
                self._step("relaying down", lambda: relay_down(
                    self, self.relay_members() if callable(self.relay_members) else self.relay_members))
            except Unreachable:
                return False
        if self.bundle_members and self.bundle_store is not None and self.domain_objects is not None:
            from .relay import bundle
            try:
                self._step("the bundle", lambda: bundle(
                    self.cluster, self.bundle_members() if callable(self.bundle_members) else self.bundle_members,
                    self.bundle_store, self.domain_objects))
            except Unreachable:
                return False
        return True

    # The holder, followed (`HolderFollower`): the record of the greatest term the domain's clusters hold, checked against
    # the key set THIS member carries, kept in its own store (never backwards), and — when it names a holder other than
    # the one this agent carries through — the door moved there. A record of a smaller term than the one kept here moves
    # nothing: the holder that is off stays the holder until somebody holds more.
    def _follow(self) -> str:
        from .term import read_holder, take_record
        try:
            keys = ClusterTrust(self.cluster_vars).keyset()
        except Untrusted:
            keys = None
        if keys is None:
            return "no keys yet: nothing to check a holder's record against"
        now = self.now()
        if self.holder_at is None:
            kept = read_holder(self.cluster_vars, keys, now)
            self.holder_at = kept["holder"] if kept else None
        rec, said = self.follow.best(keys, now)
        if rec is None:
            return said
        took = take_record(self.cluster_vars, rec, keys, now)
        if took.startswith("refused"):
            return took
        kept = read_holder(self.cluster_vars, keys, now)
        if kept is None or kept["holder"] == self.holder_at:
            return f"{said} ({took})"
        door = self.open_door(kept) if self.open_door is not None else None
        if door is None:
            return f"{said} ({took}); the record names no door — carrying through the one this agent has"
        self.domain_vars, objects = door
        if objects is not None:
            self.domain_objects = objects
        log.warning("%s: the domain is held by %s at term %s; carrying through its door from now on", self.cluster,
                    kept["holder"], kept["term"])
        self.holder_at = kept["holder"]
        return f"{said} ({took}); following {kept['holder']}"

    def relays(self) -> list[str]:
        """The members this cluster relays, by the domain's topology as it last carried it."""
        import json
        from .topology import TOPOLOGY
        items, _ = self.cluster_vars.get(TOPOLOGY)
        try:
            via = json.loads(items["doc"]).get("via", {}) if items and items.get("doc") else {}
        except PARSE_ERRORS:
            via = {}
        return sorted(m for m, r in via.items() if r == self.cluster)

    # One step of the pass that reads what the domain wrote: what does not parse is that step's — refused, said once
    # in the log until it works again — and `Unreachable` is still the domain not answering, which ends the pass.
    def _step(self, what: str, fn):
        try:
            done = fn()
        except PARSE_ERRORS as e:
            done = f"refused: what the domain wrote does not parse ({e})"
        self._say_refused(what, done)
        return done

    def _say_refused(self, what: str, done) -> None:
        said = self.__dict__.setdefault("_refused", {})
        refused = isinstance(done, str) and done.startswith("refused")
        if refused and said.get(what) != done:
            log.error("%s: %s %s", self.cluster, what, done)     # a refusal is a person's to act on: said, once
        if refused:
            said[what] = done
        elif said.pop(what, None) is not None:
            log.warning("%s: %s taken again", self.cluster, what)


class Untrusted(Exception):
    """A row of trust is in this cluster's store and does not parse: nobody can be checked by it."""


class ClusterTrust:
    """What a cluster's console and gateway read from THEIR OWN cluster's
    Variables — never from the domain — to verify tokens and decide grants
    offline.

    A row that does not parse (the review's seventh pass left these readers open: each request raised) is not a row
    that is absent. `keyset`, `root` and `revoked` raise `Untrusted` with what to do — the door answers 503, "I cannot
    check", which is what an absent key set in a member already meant — counted once (`TRUST_ROWS`). The revocation
    list is read entry by entry (`RevocationList.from_items`), and the grants item by item (`grants_from_items`): one
    entry or one item is its own trouble, not the row's."""

    def __init__(self, cluster_vars: Variables):
        self.vars = cluster_vars

    def _read(self, path: str, parse):
        items, _ = self.vars.get(path)
        if not items:
            return None
        try:
            v = parse(items)
        except PARSE_ERRORS as e:
            TRUST_ROWS.garbled(path, e)
            raise Untrusted(f"{path} in this cluster's store does not parse ({e}); the domain's agent writes it again "
                            f"on its next pass") from None
        TRUST_ROWS.parsed(path)
        return v

    def keyset(self) -> KeySet | None:
        return self._read(KEYS_PATH, KeySet.from_items)

    def root(self) -> bytes | None:
        return self._read(ROOT_PATH, lambda items: bytes.fromhex(items["pub"]))

    def revoked(self) -> set[str]:
        got = self._read(REVOKED_PATH, lambda items: RevocationList.from_items(items, REVOKED_PATH).jtis)
        return got or set()

    def grants(self) -> list:
        from .grants import grants_from_items
        items, _ = self.vars.get(GRANTS_PATH)
        return grants_from_items(items, GRANTS_PATH)


def local_networks() -> list[str]:
    """What this cluster can see: REACHES — the site's own names ("vlan:cctv-a"), set by the operator of the SITE,
    and the right source — else, as a fallback, the IPv4 networks of this host's interfaces as `net:<cidr>`
    (`ip -j -4 addr`), leaving out what is not a network a member sits on: host routes (/31, /32 — a VPN's
    tunnel end) and tunnel, bridge and container interfaces. The product found them on its box: every cluster
    "saw" the same VPN (feedback AM)."""
    import ipaddress
    import json
    import os
    import subprocess
    if os.environ.get("REACHES"):
        return [n for n in os.environ["REACHES"].split(",") if n]
    try:
        out = subprocess.run(["ip", "-j", "-4", "addr"], capture_output=True, text=True, timeout=5).stdout
        skip = ("lo", "tun", "utun", "tap", "wg", "ppp", "docker", "br-", "veth", "virbr", "cni", "flannel")
        nets = {str(ipaddress.ip_interface(f"{a['local']}/{a['prefixlen']}").network)
                for i in json.loads(out or "[]") if not str(i.get("ifname", "")).startswith(skip)
                for a in i.get("addr_info", []) if int(a.get("prefixlen", 32)) < 31}
    except (OSError, subprocess.SubprocessError, *PARSE_ERRORS):
        nets = set()
    return sorted(f"net:{n}" for n in nets)


def main() -> None:
    """python3 -m w2cplatform.domain.agent — one per cluster."""
    import os
    import signal
    import threading

    from w2cplatform.variables import open_vars, store_url

    cluster = os.environ.get("CLUSTER", "local")
    # REPORT=1: this member is one the domain never reaches (`uplink.py`) — every pass also leaves its report in the
    # domain holder's object store, `DOMAIN_OBJECTS_URL`, read from this cluster's own `OBJECTS` (`w2c.env`).
    report = os.environ.get("REPORT") == "1"
    from w2cplatform.sealing import Sealer
    from w2cplatform.trust.memberkey import MemberKey
    from .carry import CarryClient
    from .runtime import open_objects as open_store
    own_vars = open_vars(store_url(os.environ, "configstore:///run/configstore/domainagent.sock"))   # its cluster's store, by its role's socket
    sealer = Sealer.from_env(os.environ)                     # this member's ring: what it keeps of the domain's secrets
    key = MemberKey.load_or_make(own_vars, sealer)           # who it is to the door; admitted by this public key
    from .members import fingerprint
    log.info("%s: member key %s (fingerprint %s), sealing key %s — the domain admits this member by them; the person "
             "who admits it compares the fingerprint", cluster, key.pub, fingerprint(key.pub), key.seal_pub)
    # What it carries comes through a DOOR, never from the holder's store (`carry.py`): DOMAIN_URL — the holder's door —
    # or, Lesson 17, RELAY_URL — this member reaches only its relay, which keeps what the domain answered for it in
    # memory (`relay.RelayDoor`). DOMAIN_CONFIG_URL: the holder's own agent, on the holder's own box, reading its store.
    if os.environ.get("RELAY_URL"):
        domain_vars = CarryClient(os.environ["RELAY_URL"], cluster, key)
        domain_objects = open_store(os.environ["RELAY_OBJECTS_URL"])
    elif os.environ.get("DOMAIN_URL"):
        domain_vars = CarryClient(os.environ["DOMAIN_URL"], cluster, key)
        domain_objects = open_store(os.environ["DOMAIN_OBJECTS_URL"]) if report or os.environ.get("RELAY_MEMBERS") \
            or os.environ.get("RELAY") == "1" else None
    else:
        domain_vars = open_vars(os.environ["DOMAIN_CONFIG_URL"])
        domain_objects = open_store(os.environ["DOMAIN_OBJECTS_URL"]) if report or os.environ.get("RELAY_MEMBERS") else None
    # Which members this relay cluster works for: the domain's topology (`domain/topology`, the operator's one record),
    # read on every pass — RELAY_MEMBERS only where there is no topology yet. RELAY=1 says this cluster is an
    # relay at all: it keeps the relay and the bundle in its own stores.
    relayed = [m for m in os.environ.get("RELAY_MEMBERS", "").split(",") if m]
    relay = os.environ.get("RELAY") == "1" or bool(relayed)
    if relay and domain_objects is None:
        domain_objects = open_store(os.environ["DOMAIN_OBJECTS_URL"])
    if relay and not relayed:
        relayed = lambda: agent.relays()                                  # noqa: E731  the topology, as carried
    own_objects = open_store(os.environ["OBJECTS"]) if os.environ.get("OBJECTS") else None
    # Lesson 15: a member that carries through the domain's door FOLLOWS the holder by itself — it asks the consoles of
    # the domain's clusters `CLUSTERS` names (`runtime.consoles_from_env`) for the holder's record (`/api/held`), and
    # carries through the door the record of the greatest term names (its `url`, the signer's). Behind a relay, the
    # relay is its road, whoever holds the domain.
    from .runtime import consoles_from_env
    consoles = consoles_from_env() if os.environ.get("DOMAIN_URL") and not os.environ.get("RELAY_URL") else {}
    follow = HolderFollower({n: (lambda u=u: ask_held(u)) for n, u in consoles.items()}) if consoles else None
    # Its cluster's object store is also where it keeps the copies it verified (`cluster_objects`): the shared settings
    # the domain signed (Lesson 12, ADR-0032) and the backup the holder chose it to keep (Lesson 15). Built without it,
    # the agent of a unit carried neither home — only the tests gave it one (the scenario «камера — офис — центр», O5).
    agent = DomainAgent(cluster, domain_vars, own_vars, domain_objects=domain_objects, cluster_objects=own_objects,
                        published=own_objects if report else None,
                        relay_members=relayed or None, bundle_members=relayed or None,
                        bundle_store=own_objects if relay else None,
                        reaches=local_networks, own_objects=own_objects, sealer=sealer, key=key, follow=follow,
                        open_door=lambda rec: (CarryClient(rec["url"], cluster, key), None) if rec.get("url") else None)
    if relay:                                                # its members ask it for what the domain answered for them
        from w2cplatform.console import open_doors
        from .relay import RelayDoor, door_handler
        open_doors(os.environ.get("RELAY_HOST", "0.0.0.0"), int(os.environ.get("RELAY_PORT", "8446")),
                   door_handler(RelayDoor(agent)), unix_env="RELAY_UNIX", say=False)
    interval = float(os.environ.get("SYNC_INTERVAL", "30"))
    stop = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    run(agent, interval, stop)


# The agent's loop. The next pass is set BEFORE the pass (the review's eighth pass, major): a pass that raised left
# `next_pass` where it was, and the loop ran it again at once — twenty passes a second, ten reads of the domain's store
# each, from every member behind a relay whose age mark did not parse. A pass that raises is said with its trace once
# until one goes through — not printed as "the domain is unreachable", which it may not be.
def run(agent: "DomainAgent", interval: float, stop: threading.Event) -> None:
    next_pass, failing = 0.0, None
    while not stop.is_set():
        try:
            if agent.due():
                ok = agent.report_now()                      # an alarm woke it: the report goes now
            elif time.monotonic() >= next_pass:
                next_pass = time.monotonic() + interval
                ok = agent.sync()
            else:
                ok = True
            failing = None
        except Exception as e:                               # noqa: BLE001 — a bad pass: the last books are kept
            ok = False
            if failing != repr(e):
                failing = repr(e)
                log.exception("%s: the agent's pass failed; trying again in %.0f s", agent.cluster, interval)
        if not ok and failing is None:
            print(f"{agent.cluster}: domain unreachable; keeping the key set from {agent.last_synced}", flush=True)
        agent.woken.wait(max(0.05, min(agent.URGENT_GAP, next_pass - time.monotonic())))


if __name__ == "__main__":
    main()
