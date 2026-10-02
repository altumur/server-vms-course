"""The domain agent: one small Nomad job per cluster whose only right is to
write domain/* in that cluster's Variables — the way a worker's only right
is to write its epochs and its slot, and the controller's is vms/*.

It carries the three things a cluster needs from the domain and nothing
else: the signer's public key set, the revocation list, and the grants for
THIS cluster. When the domain is unreachable it stops updating; the
cluster's console and gateway keep verifying with the keys they have,
issued tokens run to expiry, grants run to theirs, nobody new logs in —
the bounded outage the services table promises, with the mechanism named.
Workers are not involved: nothing about a user reaches a worker, ever.
"""
from __future__ import annotations

import threading
import time

from cluster.variables import Variables

from .federation import Unreachable
from .tokens import ROOT_KID, KeySet, RevocationList

KEYS_PATH, REVOKED_PATH, GRANTS_PATH = "domain/keys", "domain/revoked", "domain/grants"
# Lesson 15: the domain root's public key, PINNED in each member — written once, never replaced by the agent.
# In production it comes with enrollment (the trust bundle of Lesson 6); here the first root-signed key set pins it.
ROOT_PATH = "domain/root"
# …and the member's LDevID, issued again by a new holder after its issuing certificate was revoked.
LDEVID_PATH = "domain/ldevid"
# Lesson 13: where this cluster's recorders find cameras of OTHER clusters. Lesson 14: whose closed alarm
# buckets this cluster keeps a copy of.
SOURCES_PATH = "domain/sources"
# Lesson 13, the other way round: who records THIS cluster's cameras elsewhere, and whether it writes them —
# read by the backup on a camera's card. The recorder owns the names; the agent only carries.
from vms.recworker import DOMAIN_SEEN, PRIMARIES as PRIMARIES_PATH
# Lesson 17: a recording cluster's upstream — where its streams go up to the centre, or come down from (star).
UPSTREAM_PATH = "domain/upstream"
# Lesson 16: whom this camera may ask to act, at which ingest, with what token (a scenario between cameras).
ASKS_PATH = "domain/asks"
# …and, for a camera nobody records, the ingest it polls all the same — for asks, with no stream to push.
POLL_PATH = "domain/poll"
# The emergency account's password HASH for one cluster (Lesson 4, step 7): set at the domain, carried home, checked
# at the cluster's console with the domain away — which is the only time it is for.
BREAK_GLASS_PATH = "domain/break_glass"
# That this cluster IS a member — written on every pass that leaves a key set here, so the cluster's console can tell
# "the keys were lost" from "there never were any" (`w2cplatform/access.py`, `DOMAIN_MARKS`). The other marks are each
# conditional — `domain/root` only with a root-signed key set, grants and the rest only when the domain has some for
# this cluster — and a member with none of them looked, keys gone, like a cluster that never joined: open (the review's
# fourth pass). This one has no condition but the keys themselves.
MEMBER_PATH = "domain/member"
PER_CLUSTER = (SOURCES_PATH, PRIMARIES_PATH, UPSTREAM_PATH, ASKS_PATH, POLL_PATH, LDEVID_PATH, BREAK_GLASS_PATH)


class DomainPublisher:
    """The signer's side: writes the key set and the revocation list into
    the domain HOLDER's Variables, where agents read them."""

    def __init__(self, domain_vars: Variables):
        self.vars = domain_vars

    def publish_keys(self, ks: KeySet | dict) -> None:
        """A key set, or — Lesson 15 — the items `DomainRoot.key_set` signed."""
        _, idx = self.vars.get(KEYS_PATH)
        self.vars.put(KEYS_PATH, ks if isinstance(ks, dict) else ks.to_items(), cas=idx)

    def publish_revoked(self, rl: RevocationList) -> None:
        _, idx = self.vars.get(REVOKED_PATH)
        self.vars.put(REVOKED_PATH, rl.to_items(), cas=idx)

    def publish_break_glass(self, cluster: str, pwhash: str, now: float) -> None:
        """The one local account of `cluster`: its password's hash, never the password. Rotating it is
        publishing a new one — which the domain does when an emergency entry has been used."""
        path = f"{BREAK_GLASS_PATH}/{cluster}"
        _, idx = self.vars.get(path)
        self.vars.put(path, {"pwhash": pwhash, "set_at": now}, cas=idx)

    def publish_grants(self, cluster: str, grants: list) -> None:
        """The grants for one cluster, under domain/grants/<cluster> in the
        domain holder's Variables; the cluster's agent copies them home."""
        from .grants import grants_to_items
        path = f"{GRANTS_PATH}/{cluster}"
        _, idx = self.vars.get(path)
        self.vars.put(path, grants_to_items(grants), cas=idx)


class DomainAgent:
    def __init__(self, cluster: str, domain_vars: Variables, cluster_vars: Variables, now=time.time,
                 console=None, current=None, domain_objects=None, cluster_objects=None, seen_store=None,
                 published=None, pages=None, bundle_members=None, bundle_store=None, relay_members=None, alarm_waiting=None,
                 reaches=None, own_objects=None):
        """`console` and `current` are Lesson 9: this cluster's console, which writes its rows, and
        `current(ref) -> (id, row)` for a camera by the domain's name. Given them, the agent also applies
        the edits the domain kept while this cluster was off. Without them it only carries them home.

        `domain_objects` and `cluster_objects` are Lesson 12: where the domain publishes documents, and
        this cluster's DURABLE object store, where the agent keeps the copy it verified. Given them, it
        carries the shared settings home.

        `seen_store` is Lesson 13: where the agent says when it last reached the domain (`domain/seen`), so
        the books it carried can be judged by their age without the books themselves changing. On a camera
        it is RAM — this is written on every pass, and flash is not.

        `published` and `pages` are the uplink (`domain/uplink.py`): this member's own object store, where
        its workers publish, and a callable returning the pages it is asked to show (Lesson 14). Given
        them, every pass ends with a REPORT into the domain holder's object store — the domain never opens
        a connection to this member; this pass is the only one there is, and it carries both ways."""
        self.cluster, self.domain_vars, self.cluster_vars, self.now = cluster, domain_vars, cluster_vars, now
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
        # minute is long enough for the camera that saw the door forced to be broken before it reported it. The
        # card only sets this; the agent's own loop reports, so two threads never sync at once.
        self.woken = threading.Event()
        self._urgent_at: float | None = None
        self._relay_n, self._relay_seen = None, None      # through a relay: its last age mark, on OUR clock

    def _carry(self, path: str, items: dict | None, clear: bool = False) -> None:
        have, idx = self.cluster_vars.get(path)
        if items is None and not clear:
            return
        items = items or {}
        if have != items and not (have is None and not items):
            self.cluster_vars.put(path, items, cas=idx)

    # The key set, carried with one rule per lesson. Lesson 4: as it is — the channel was the trust. Lesson 15:
    # once this member has a root pinned, only a key set that root SIGNED, and never an older revision than it
    # holds. A holder carried off the wall has the token key and can sign anything with it — but not as the
    # root: a key set of its own, published to members it can still reach, is refused, and says why.
    def _carry_keys(self, items: dict | None) -> str:
        import json
        from .shared import NotTaken, verify
        if items is None:
            return "no key set"
        trust = ClusterTrust(self.cluster_vars)
        pinned = trust.root()
        if "doc" not in items:
            if pinned is not None:
                return "refused: a key set not signed by the domain's root"
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
        have = trust.keyset()
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
            from .chain import say_seen                     # a relay: how current its relay is, reached or not
            say_seen(self.bundle_store, self.last_synced, self.now())
        return ok

    def _relay_mark(self) -> float | None:
        mark = self.domain_vars.seen()
        if mark and mark.get("n") != self._relay_n:
            self._relay_n = mark.get("n")
            self._relay_seen = None if mark.get("age") is None else self.now() - float(mark["age"])
        return self._relay_seen

    def _sync(self) -> bool:
        from .pending import OUTCOMES_PATH, PENDING_PATH, apply_pending
        try:
            keys, _ = self.domain_vars.get(KEYS_PATH)
            revoked, _ = self.domain_vars.get(REVOKED_PATH)
            grants, _ = self.domain_vars.get(f"{GRANTS_PATH}/{self.cluster}")
            pending, _ = self.domain_vars.get(f"{PENDING_PATH}/{self.cluster}")
            # What the domain decided for THIS cluster in the later lessons — each one more row of the same
            # kind: written by the domain under `<path>/<cluster>`, carried home to `<path>`.
            later = [(path, self.domain_vars.get(f"{path}/{self.cluster}")[0]) for path in PER_CLUSTER]
        except Unreachable:
            return False
        self.keys = self._carry_keys(keys)
        for path, items in ((REVOKED_PATH, revoked), (GRANTS_PATH, grants), *later):
            self._carry(path, items)
        # Edits the domain kept while this cluster was off (Lesson 9) — carried home even when there are
        # none left, because an edit the domain has cleared must stop being applied here. Then applied, by
        # this cluster's console and as the operator who made each one, and what happened written where the
        # domain reads it. The agent writes `domain/*` and nothing else; the row is the console's.
        self._carry(PENDING_PATH, pending, clear=True)
        if self.console is not None and self.current is not None:
            import json
            entries = {k: json.loads(v) for k, v in (pending or {}).items()}
            outcomes = apply_pending(entries, self.current, self.console, self.now())
            self._carry(OUTCOMES_PATH, {k: json.dumps(v, ensure_ascii=False, sort_keys=True)
                                        for k, v in outcomes.items()}, clear=True)
        # The shared settings (Lesson 12), checked against the key set this pass just carried — the member's
        # own, never one that came with the document.
        # And Lesson 15: which member holds the domain — carried like the keys, but never to a smaller term —
        # and, on the members chosen to keep it, the backup of the domain's state, carried like the settings.
        from .term import BACKUP, carry_holder
        keyset = ClusterTrust(self.cluster_vars).keyset()
        if keyset is not None:
            self._carry(MEMBER_PATH, {"cluster": self.cluster})   # written when missing — after a rollback too — and only then
        try:
            self.holder = carry_holder(self.domain_vars, self.cluster_vars, keyset, self.now()) if keyset else "no keys yet"
            if self.domain_objects is not None and self.cluster_objects is not None:
                from .shared import carry
                self.shared = carry(self.domain_vars, self.domain_objects, self.cluster_vars, self.cluster_objects,
                                    keyset, self.now())
                self.backup = carry(self.domain_vars, self.domain_objects, self.cluster_vars, self.cluster_objects,
                                    keyset, self.now(), src=f"{BACKUP}/{self.cluster}", dst=BACKUP, obj=BACKUP,
                                    refused=f"{BACKUP}-refused")
        except Unreachable:
            return False
        self.last_synced = self.now()
        self.syncs += 1
        if self.seen_store is not None:
            import json
            # Through a relay (Lesson 17), "when did I last hear from the domain" is when the RELAY last did: a
            # camera that reaches its relay every pass while the relay is cut from the centre has current
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
                           self.pages() if self.pages else None)
                self._paged_at = paged_at
                self.reported = f"reported ({n} written)"
            except NotPublished as e:
                self.reported = str(e)
            except Unreachable:
                self.reported = "the domain did not take the report"
                return False
        if self.relay_members and self.bundle_store is not None:
            from .chain import relay_down
            members = self.relay_members() if callable(self.relay_members) else self.relay_members
            try:
                relay_down(members, self.domain_vars, self.domain_objects, self.cluster_vars, self.bundle_store, self.now())
            except Unreachable:
                return False
        if self.bundle_members and self.bundle_store is not None and self.domain_objects is not None:
            from .chain import bundle
            try:
                bundle(self.cluster, self.bundle_members() if callable(self.bundle_members) else self.bundle_members,
                       self.bundle_store, self.domain_objects)
            except Unreachable:
                return False
        return True


class ClusterTrust:
    """What a cluster's console and gateway read from THEIR OWN cluster's
    Variables — never from the domain — to verify tokens and decide grants
    offline."""

    def __init__(self, cluster_vars: Variables):
        self.vars = cluster_vars

    def keyset(self) -> KeySet | None:
        items, _ = self.vars.get(KEYS_PATH)
        return KeySet.from_items(items) if items else None

    def root(self) -> bytes | None:
        items, _ = self.vars.get(ROOT_PATH)
        return bytes.fromhex(items["pub"]) if items else None

    def revoked(self) -> set[str]:
        items, _ = self.vars.get(REVOKED_PATH)
        return RevocationList.from_items(items).jtis

    def grants(self) -> list:
        from .grants import grants_from_items
        items, _ = self.vars.get(GRANTS_PATH)
        return grants_from_items(items)


def local_networks() -> list[str]:
    """What this cluster can see: REACHES — the site's own names ("vlan:cctv-a"), set by the operator of the SITE,
    and the right source — else, as a fallback, the IPv4 networks of this host's interfaces as `net:<cidr>`
    (`ip -j -4 addr`), leaving out what is not a network a camera sits on: host routes (/31, /32 — a VPN's
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
    except (OSError, ValueError, subprocess.SubprocessError):
        nets = set()
    return sorted(f"net:{n}" for n in nets)


def main() -> None:
    """python3 -m domain.agent — one per cluster."""
    import os
    import signal
    import threading

    import cluster as _cluster  # noqa: F401  — registers the `nomad://` scheme
    from w2cplatform.variables import open_vars

    cluster = os.environ.get("CLUSTER", os.environ.get("NOMAD_REGION", "local"))
    # REPORT=1: this member is one the domain never reaches (`domain/uplink.py`) — every pass also leaves its
    # report in the domain holder's object store, `DOMAIN_OBJECTS_URL`, read from this cluster's own
    # `OBJECTS_URL`. The same one connection, opened from here, carrying both ways.
    report = os.environ.get("REPORT") == "1"
    from cluster.objectstore import open_store
    own_vars = open_vars(os.environ.get("CONFIG_URL") or "nomad://" + os.environ.get("NOMAD_ADDR", "127.0.0.1:4646").replace("http://", ""))
    # Lesson 17. RELAY_CONFIG_URL / RELAY_OBJECTS_URL: this member can reach only its relay — the relay is
    # its road to the domain both ways (`chain.Relay`). RELAY_MEMBERS: this is such a relay, relaying for them.
    if os.environ.get("RELAY_CONFIG_URL"):
        from .chain import Relay
        through = Relay(open_vars(os.environ["RELAY_CONFIG_URL"]), open_store(os.environ["RELAY_OBJECTS_URL"]))
        domain_vars, domain_objects = through.vars, through.objects
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
        from .topology import Topology
        topo = Topology(domain_vars)
        relayed = lambda: topo.relayed_by(cluster)                       # noqa: E731
    own_objects = open_store(os.environ["OBJECTS_URL"]) if os.environ.get("OBJECTS_URL") else None
    agent = DomainAgent(cluster, domain_vars, own_vars, domain_objects=domain_objects,
                        published=own_objects if report else None,
                        relay_members=relayed or None, bundle_members=relayed or None,
                        bundle_store=own_objects if relay else None,
                        reaches=local_networks, own_objects=own_objects)
    interval = float(os.environ.get("SYNC_INTERVAL", "30"))
    stop = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    next_pass = 0.0
    while not stop.is_set():
        try:
            if agent.due():
                ok = agent.report_now()                      # an alarm woke it: the report goes now
            elif time.monotonic() >= next_pass:
                ok = agent.sync(); next_pass = time.monotonic() + interval
            else:
                ok = True
        except Exception:                                    # noqa: BLE001 — the domain is unreachable; keep the last set
            ok = False
        if not ok:
            print(f"{cluster}: domain unreachable; keeping the key set from {agent.last_synced}", flush=True)
        agent.woken.wait(max(0.05, min(agent.URGENT_GAP, next_pass - time.monotonic())))


if __name__ == "__main__":
    main()
