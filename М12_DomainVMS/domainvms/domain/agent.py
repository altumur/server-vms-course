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

import time

from cluster.variables import Variables

from .federation import Unreachable
from .tokens import KeySet, RevocationList

KEYS_PATH, REVOKED_PATH, GRANTS_PATH = "domain/keys", "domain/revoked", "domain/grants"
# Lesson 13: where this cluster's recorders find cameras of OTHER clusters. Lesson 14: whose closed alarm
# buckets this cluster keeps a copy of.
SOURCES_PATH, MIRRORS_PATH = "domain/sources", "domain/mirrors"
# Lesson 13, the other way round: who records THIS cluster's cameras elsewhere, and whether it writes them —
# read by the backup on a camera's card. The recorder owns the names; the agent only carries.
from vms.recworker import DOMAIN_SEEN, PRIMARIES as PRIMARIES_PATH
# Lesson 17: a recording cluster's upstream — where its streams go up to the centre, or come down from (star).
UPSTREAM_PATH = "domain/upstream"
PER_CLUSTER = (SOURCES_PATH, MIRRORS_PATH, PRIMARIES_PATH, UPSTREAM_PATH)


class DomainPublisher:
    """The signer's side: writes the key set and the revocation list into
    the DOMAIN cluster's Variables, where agents read them."""

    def __init__(self, domain_vars: Variables):
        self.vars = domain_vars

    def publish_keys(self, ks: KeySet) -> None:
        _, idx = self.vars.get(KEYS_PATH)
        self.vars.put(KEYS_PATH, ks.to_items(), cas=idx)

    def publish_revoked(self, rl: RevocationList) -> None:
        _, idx = self.vars.get(REVOKED_PATH)
        self.vars.put(REVOKED_PATH, rl.to_items(), cas=idx)

    def publish_grants(self, cluster: str, grants: list) -> None:
        """The grants for one cluster, under domain/grants/<cluster> in the
        domain cluster's Variables; the cluster's agent copies them home."""
        from .grants import grants_to_items
        path = f"{GRANTS_PATH}/{cluster}"
        _, idx = self.vars.get(path)
        self.vars.put(path, grants_to_items(grants), cas=idx)


class DomainAgent:
    def __init__(self, cluster: str, domain_vars: Variables, cluster_vars: Variables, now=time.time,
                 console=None, current=None, domain_objects=None, cluster_objects=None, seen_store=None,
                 published=None, pages=None, bundle_members=None, bundle_store=None):
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
        them, every pass ends with a REPORT into the domain cluster's object store — the domain never opens
        a connection to this member; this pass is the only one there is, and it carries both ways."""
        self.cluster, self.domain_vars, self.cluster_vars, self.now = cluster, domain_vars, cluster_vars, now
        self.console, self.current = console, current
        self.domain_objects, self.cluster_objects = domain_objects, cluster_objects
        self.seen_store = seen_store
        self.published, self.pages = published, pages
        # Lesson 17's summary report: an office's agent folds the reports its members left in `bundle_store`
        # (this cluster's object store) into one object in the domain cluster.
        self.bundle_members, self.bundle_store = bundle_members, bundle_store
        self.reported = ""                                  # what the last pass did with the report
        self.shared = self.backup = self.host = ""          # what the last pass did with each document
        self.last_synced: float | None = None
        self.syncs = 0

    def _carry(self, path: str, items: dict | None, clear: bool = False) -> None:
        have, idx = self.cluster_vars.get(path)
        if items is None and not clear:
            return
        items = items or {}
        if have != items and not (have is None and not items):
            self.cluster_vars.put(path, items, cas=idx)

    def sync(self) -> bool:
        """One pass. False (and nothing written) if the domain did not answer."""
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
        for path, items in ((KEYS_PATH, keys), (REVOKED_PATH, revoked), (GRANTS_PATH, grants), *later):
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
        # And Lesson 15: which member hosts the domain — carried like the keys, but never to a smaller term —
        # and, on the members chosen to keep it, the backup of the domain's state, carried like the settings.
        from .term import BACKUP, carry_host
        keyset = ClusterTrust(self.cluster_vars).keyset()
        try:
            self.host = carry_host(self.domain_vars, self.cluster_vars, keyset, self.now()) if keyset else "no keys yet"
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
            self.seen_store.put(DOMAIN_SEEN, json.dumps({"ts": self.last_synced, "cluster": self.cluster}).encode())
        # Up, on the same connection: what the domain reads of this member, left where it reads it. Last,
        # so the outcomes of the edits applied above go up in this same pass.
        if self.published is not None and self.domain_objects is not None:
            from .uplink import NotPublished, report
            try:
                n = report(self.cluster, self.cluster_vars, self.published, self.domain_objects, self.now(),
                           self.pages() if self.pages else None)
                self.reported = f"reported ({n} written)"
            except NotPublished as e:
                self.reported = str(e)
            except Unreachable:
                self.reported = "the domain did not take the report"
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

    def revoked(self) -> set[str]:
        items, _ = self.vars.get(REVOKED_PATH)
        return RevocationList.from_items(items).jtis

    def grants(self) -> list:
        from .grants import grants_from_items
        items, _ = self.vars.get(GRANTS_PATH)
        return grants_from_items(items)


def main() -> None:
    """python3 -m domain.agent — one per cluster."""
    import os
    import signal
    import threading

    import cluster as _cluster  # noqa: F401  — registers the `nomad://` scheme
    from w2cplatform.variables import open_vars

    cluster = os.environ.get("CLUSTER", os.environ.get("NOMAD_REGION", "local"))
    # REPORT=1: this member is one the domain never reaches (`domain/uplink.py`) — every pass also leaves its
    # report in the domain cluster's object store, `DOMAIN_OBJECTS_URL`, read from this cluster's own
    # `OBJECTS_URL`. The same one connection, opened from here, carrying both ways.
    report = os.environ.get("REPORT") == "1"
    if report:
        from cluster.objectstore import open_store
    agent = DomainAgent(cluster, open_vars(os.environ["DOMAIN_CONFIG_URL"]),
                        open_vars(os.environ.get("CONFIG_URL") or "nomad://" + os.environ.get("NOMAD_ADDR", "127.0.0.1:4646").replace("http://", "")),
                        domain_objects=open_store(os.environ["DOMAIN_OBJECTS_URL"]) if report else None,
                        published=open_store(os.environ["OBJECTS_URL"]) if report else None)
    interval = float(os.environ.get("SYNC_INTERVAL", "30"))
    stop = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    while not stop.is_set():
        try:
            ok = agent.sync()
        except Exception:                                    # noqa: BLE001 — the domain is unreachable; keep the last set
            ok = False
        if not ok:
            print(f"{cluster}: domain unreachable; keeping the key set from {agent.last_synced}", flush=True)
        stop.wait(interval)


if __name__ == "__main__":
    main()
