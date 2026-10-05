"""Lesson 1 — what a cluster cannot know.

A domain is N clusters, each with its own store (a raft among its servers) and its own object store. Nothing
replicates between them. The domain's directory is therefore an AGGREGATION over N cluster directories: partial, stale
by a bounded amount, sometimes incomplete — and the honest answer to "where is unit 7" when a cluster is unreachable
is "not found in the clusters I could reach", never a short list rendered as complete.

What a cluster publishes for the domain to read (М11 Lesson 10): for every subsystem, one object PER WORKER under
`<sub>/snapshot/` — the controller's copy of the unit rows placed on that worker, with the server, carrying a
timestamp — plus `<sub>/snapshot/unplaced` for the rows nobody holds, and the workers' own heartbeats under
`<sub>/heartbeats/`. Which subsystems' units are in the directory, and by which field each is named across clusters,
the specs say (`domain.ref`, `declared.directory`). The domain never reads a cluster's rows: the rows stay in raft with
one writer, and what leaves is a copy with an age.

`Cluster` is the domain's handle on one cluster; `Federation` is the list; `DomainDirectory` merges the snapshots with
the incompleteness kept as a first-class field of every answer.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from w2cplatform.objects import ObjectStore
from w2cplatform.rows import Table, finite
from w2cplatform.variables import Variables

from . import declared

# What a cluster says it can see, in its OWN object store — written by its agent from what the cluster observes
# (its interfaces, its configured site), read by the domain like any published object. The operator does not
# type it into the domain: a fact about a network belongs to the network's side, and goes stale there first.
REACHES = "domain/reaches"


class Unreachable(Exception):
    """The cluster did not answer. Raised by a cluster's stores when the link is down; the fakes raise it on demand."""


# ONE OBJECT A MEMBER PUBLISHED THAT DOES NOT PARSE IS THAT OBJECT'S TROUBLE (М10's seventh review, part 2). The domain
# read every member's heartbeats, snapshot shards and books with a bare `json.loads` and bare numbers: one torn object
# raised out of the read view's pass — every cluster's time froze, the directory failed, and the console's loop
# swallowed it without a word. Every such read goes through `published` now, the platform's one reader of rows
# (`w2cplatform.rows`): the object is skipped, counted once per `<cluster>/<key>` until it parses again
# (`MEMBER_OBJECTS`), logged once, and what reads it decides what "skipped" means — a shard nobody can read makes the
# cluster's copy the oldest there can be; a heartbeat, a worker not seen.
MEMBER_OBJECTS = Table("member_object", "skipped — the rest of what the member published is read", "published object")


def _a_dict(v) -> dict:
    if not isinstance(v, dict):
        raise TypeError(f"not an object: {type(v).__name__}")
    return v


def published(cluster: str, key: str, raw, check=None, default=None):
    """The JSON of one object `cluster` published under `key`, or `default` when there is none or it does not parse —
    or does not pass `check` (which raises a parse error for the wrong shape): counted once, logged once."""
    if not raw:
        return default

    def parse():
        v = _a_dict(json.loads(raw))
        if check is not None:
            check(v)
        return v
    return MEMBER_OBJECTS.read(f"{cluster}/{key}", parse, default)


def _names(v) -> None:
    """A list of names (strings): a string in its place is not read as a list of its letters."""
    if not isinstance(v, list) or not all(isinstance(n, str) for n in v):
        raise TypeError("not a list of names")


def a_heartbeat(hb: dict) -> None:
    """The shape every reader of a worker's heartbeat relies on: a finite `ts`, a list of status entries."""
    finite(hb.get("ts", 0))
    if not all(isinstance(st, dict) for st in hb.get("status", [])):
        raise TypeError("a status entry is not an object")


def _specs(sub):
    """The specs a read covers: the one named, or every spec of the directory."""
    if sub is None:
        return declared.directory()
    s = declared.spec(sub)
    return [s] if s is not None else []


@dataclass
class Cluster:
    name: str
    vars: Variables
    objects: ObjectStore
    reaches: frozenset = frozenset()      # networks this cluster can see: {"vlan:a", ...}
    is_domain_holder: bool = False        # the one that runs the domain services — a stated decision
    via: str | None = None                # Lesson 17: a member that reaches only this relay — and through it the domain

    def networks(self) -> frozenset:
        """The networks this cluster can see: what it reports (`REACHES`, from its agent), with any stated here."""
        try:
            raw = self.objects.get(REACHES)
        except Unreachable:
            raw = None
        said = published(self.name, REACHES, raw, lambda v: _names(v.get("networks", []))) or {}
        return self.reaches | frozenset(said.get("networks", []))       # what does not parse says no network (the seventh review)

    def snapshot(self, sub: str | None = None) -> dict | None:
        """The cluster's units and placement, merged from one object per worker, of one subsystem or of every
        subsystem of the directory: `{cluster, ts, units: [{sub, id, <snapshot fields>, worker, server}]}`.

        Read exactly the way `heartbeats()` is read — a listing and a get per object — because the cluster publishes
        it in exactly that shape. There is no single instant at which the whole cluster was in the state this
        returns: each shard carries its own `ts`, and the merge keeps the OLDEST as the age of the whole, because a
        directory is only as fresh as its stalest part.

        A unit can appear in two shards for the length of a move. The newer shard wins; reporting it twice would make
        `where()` answer `contested` — a placement failure — on what is not a fault."""
        keys_of = [(s, self.objects.list(f"{s.name}/snapshot/")) for s in _specs(sub)]
        if not any(keys for _, keys in keys_of):
            return None
        best: dict[tuple, tuple[float, dict]] = {}
        oldest = None
        for s, keys in keys_of:
            for key in keys:
                raw = self.objects.get(key)
                if not raw:
                    continue
                shard = published(self.name, key, raw, lambda sh, rows=s.rows: _a_shard(sh, rows))
                if shard is None:
                    oldest = 0.0                       # a shard nobody can read has no age: the copy is as old as can be
                    continue
                ts = float(shard.get("ts", 0))
                oldest = ts if oldest is None else min(oldest, ts)
                for row in shard.get(s.rows, []):
                    uid = (s.name, str(row.get("id")))
                    if uid not in best or ts > best[uid][0]:
                        best[uid] = (ts, {**row, "sub": s.name})
        return {"cluster": self.name, "ts": oldest or 0, "units": [r for _, r in best.values()]}

    def heartbeats(self, sub: str | None = None) -> dict[str, dict]:
        """worker -> its last heartbeat (М10's shape: status, server, epoch per unit), each with its `sub`. A worker's
        name is its subsystem's: two subsystems' workers are keyed `<sub>/<worker>` when the read covers more than one.

        `<sub>/heartbeats/` holds heartbeats and nothing else, so this is a listing and a get — the same two calls
        `snapshot()` makes, against a sibling directory."""
        specs = _specs(sub)
        out = {}
        for s in specs:
            for key in self.objects.list(f"{s.name}/heartbeats/"):
                hb = published(self.name, key, self.objects.get(key), lambda hb: (_a_name(hb["worker"]), a_heartbeat(hb)))
                if hb is not None:
                    out[hb["worker"] if len(specs) == 1 else f"{s.name}/{hb['worker']}"] = {**hb, "sub": s.name}
        return out


def _a_name(v) -> None:
    """A worker's name is a string (the review's ninth pass, minor): the check was `str(hb["worker"])`, which a list
    passes, and the key was the list itself — unhashable, raised out of `heartbeats()`, and the whole member read as
    unreachable for one heartbeat. Now that heartbeat is the one skipped, counted."""
    if not isinstance(v, str) or not v:
        raise TypeError(f"a worker's name is a non-empty string, not {type(v).__name__}")


def _a_shard(shard: dict, rows: str) -> None:
    """A snapshot shard: a finite `ts`, and its rows (objects) — what `snapshot` and its readers rely on."""
    finite(shard.get("ts", 0))
    if not all(isinstance(r, dict) for r in shard.get(rows, [])):
        raise TypeError("a row of the shard is not an object")


def ref_of(row: dict) -> str:
    """What the domain calls a unit of a snapshot or a status entry: its spec's `domain.ref` field, else `<sub>/<id>`."""
    s = declared.spec(str(row.get("sub", "")))
    v = row.get(s.domain.ref) if s is not None and s.domain.ref else None
    return str(v) if v not in (None, "") else ""


@dataclass
class Answer:
    """Where a unit is, and how much of the domain that claim covers."""
    unit: str
    worker: str | None
    server: str | None
    cluster: str | None
    searched: list[str]
    unreachable: list[str]
    # Members that each claim the unit (the review's eighth pass, minor): a member naming another's unit in its
    # snapshot made `where` raise — a 500 on `/domain/where/<ref>` and on every edit of that unit through the domain.
    # Now the answer says who claims it and is not complete: the domain cannot tell which of them is right.
    contested: list[str] = field(default_factory=list)
    sub: str | None = None

    @property
    def complete(self) -> bool:
        return not self.unreachable and not self.contested

    @property
    def found(self) -> bool:
        return self.cluster is not None

    def sentence(self) -> str:
        if self.found:
            s = f"{self.unit} is on {self.worker or 'no worker yet'} ({self.server or '?'}) in {self.cluster}"
            return s if self.complete else s + f" (and {', '.join(self.unreachable)} could not be asked)"
        if self.contested:
            return (f"{self.unit} is claimed by {', '.join(self.contested)}: a placement failure, not a tie — "
                    f"the domain cannot tell which of them holds it")
        if self.complete:
            return f"{self.unit} is in no cluster of the domain ({len(self.searched)} clusters searched)"
        return (f"{self.unit} was not found in the {len(self.searched)} cluster(s) I could reach; "
                f"{', '.join(self.unreachable)} unreachable — not 'not anywhere'")


@dataclass
class Federation:
    clusters: dict[str, Cluster] = field(default_factory=dict)

    def add(self, c: Cluster) -> None:
        self.clusters[c.name] = c

    @property
    def domain_holder(self) -> Cluster:
        holders = [c for c in self.clusters.values() if c.is_domain_holder]
        if len(holders) != 1:
            raise RuntimeError(f"exactly one domain holder must be designated; found {[c.name for c in holders]}")
        return holders[0]


class DomainDirectory:
    """A directory of directories. Reads each cluster's snapshot; never copies the rows; never claims more than it
    reached."""

    def __init__(self, fed: Federation, wall=time.time):
        self.fed, self.wall = fed, wall

    def scan(self) -> tuple[dict[str, dict], list[str]]:
        """{cluster: snapshot}, and the clusters that did not answer."""
        out, down = {}, []
        for name, c in self.fed.clusters.items():
            try:
                out[name] = c.snapshot() or {"units": [], "ts": 0}
            except Unreachable:
                down.append(name)
        return out, down

    def where(self, ref) -> Answer:
        """`ref` is the DOMAIN's name for a unit — the value of its spec's `domain.ref` field, which the domain gave
        the cluster when it forwarded the create. A cluster's own `id` is the cluster's: two clusters both have an id
        7, and the domain never asks by it."""
        scan, down = self.scan()
        hits = [(cl, row) for cl, snap in scan.items() for row in snap.get("units", []) if ref_of(row) == str(ref)]
        if len(hits) > 1:
            return Answer(str(ref), None, None, None, sorted(scan), sorted(down), contested=sorted({h[0] for h in hits}))
        if hits:
            cl, row = hits[0]
            return Answer(str(ref), row.get("worker"), row.get("server"), cl, sorted(scan), sorted(down),
                          sub=row.get("sub"))
        return Answer(str(ref), None, None, None, sorted(scan), sorted(down))

    def holdings(self) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
        """{cluster: {worker: [refs]}} from the snapshots, and the silent clusters."""
        scan, down = self.scan()
        out: dict[str, dict[str, list[str]]] = {}
        for cl, snap in scan.items():
            out[cl] = {}
            for row in snap.get("units", []):
                out[cl].setdefault(str(row.get("worker") or "(unplaced)"), []).append(
                    ref_of(row) or f"{cl}/{row.get('sub')}/{row.get('id')}")
        return out, down

    def ages(self) -> dict[str, float]:
        """How old each cluster's snapshot is — the domain's RPO, shown, never hidden."""
        scan, _ = self.scan()
        now = self.wall()
        return {cl: max(0.0, now - float(snap.get("ts", 0))) for cl, snap in scan.items()}
