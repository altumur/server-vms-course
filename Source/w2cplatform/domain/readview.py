"""Lesson 3 — the list of units, and where the console gets it.

Not a fan-out to N consoles (waits for the slowest, breaks on the first dead one). Not status in the store (raft is not
for frequent, large data). The read model reads what each cluster's WORKERS already publish — `<sub>/heartbeats/<w>`,
carrying the worker's status per unit, its server, its epochs — and, for the units no worker reports at all, each
cluster's `<sub>/snapshot/*`, for every subsystem of the directory (`declared.directory`). It holds both in memory and
serves the list, search and pagination from there. No call to any worker or controller on any request. It is a cache
that admits to being one: a restart is one pass over the objects.

The two sources answer different questions and the list keeps them apart. A heartbeat is an OBSERVATION: this unit is
running, at this revision, on this worker. The snapshot is the CONFIGURATION: this unit is supposed to exist. A unit
that is configured and observed appears once, from the observation. A unit that is configured and observed by nobody —
nothing placed it, or the worker that holds it has never reported — appears from the snapshot, marked `configured`, and
that is the whole of "set up but not working" (М10A Lesson 13 shows the same pair inside one cluster, as `rows` beside
`configured`).

Staleness is shown, never hidden: every row carries the age of the heartbeat it came from; a worker older than
`lost_after` is *stale — last known state*, its units still listed. A cluster that did not answer is reported as such,
with its rows from the last successful pass — never as an empty cluster.

Grouped by failure domain: the heartbeat carries the server the worker runs on, so when a server dies its workers go
silent together and the console shows ONE cause, not thirty greyed units.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

from w2cplatform.rows import PARSE_ERRORS

from . import declared
from .federation import MEMBER_OBJECTS, Answer, DomainDirectory, Federation, Unreachable, ref_of

log = logging.getLogger("domain.readview")


@dataclass
class Row:
    unit: str                   # the cluster's own id of the unit
    name: str
    worker: str
    cluster: str
    server: str
    phase: str
    position: str
    revision: int
    observed_revision: int
    epoch: int
    age: float                  # seconds since the heartbeat this row came from
    worker_state: str           # "live" | "stale" | "unreachable" (cluster did not answer) | "configured" (no worker reports it)
    ref: str = ""               # the name the DOMAIN knows it by; the cluster's number is the cluster's
    sub: str = ""               # the subsystem the unit is of

    def to_json(self) -> dict:
        d = self.__dict__.copy()
        if self.worker_state == "live":
            d["as_of"] = f"as of {self.age:.0f} s ago"
        elif self.worker_state == "configured":
            d["as_of"] = f"configured — no worker reports it; the cluster's copy is {self.age:.0f} s old"
        else:
            d["as_of"] = f"{self.worker_state} — last known state, {self.age:.0f} s old"
        return d


@dataclass
class Cause:
    scope: str                  # "cluster" | "server" | "worker"
    name: str
    silent_for: float
    workers: list[str]
    units: int

    def sentence(self) -> str:
        what = {"cluster": "cluster unreachable", "server": "server silent", "worker": "worker silent"}[self.scope]
        return f"{what}: {self.name} for {self.silent_for:.0f} s — {len(self.workers)} worker(s), {self.units} unit(s)"


@dataclass
class Snapshot:
    worker: str
    cluster: str
    ts: float
    server: str
    status: list[dict]
    doors: dict | None = None   # what else the worker said in its heartbeat — its doors, what it holds — as it said it
    sub: str = ""

def _text(v) -> str:
    """A field shown and searched as text: `""` for none, else what was written, as a string."""
    return "" if v is None else str(v)


def _unit_id(v, sub: str = "") -> str:
    """A unit's id as a string, as its spec says ids are (`unit.id`: numeric, or a field's value) — and a number that is
    no number is no id (`1e400`, `nan`, `"seven"` where ids are numbers)."""
    if isinstance(v, bool) or v is None:
        raise ValueError(f"not a unit's id: {v!r}")
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")) or v != int(v):
            raise ValueError(f"not a unit's id: {v!r}")
        v = int(v)
    spec = declared.spec(sub) if sub else None
    s = str(spec.parse_id(v)) if spec is not None else str(v)
    if not s:
        raise ValueError("an empty unit id")
    return s


def _order(uid: str):
    """Units sort by number when their ids are numbers, else by name — `2` before `10`."""
    return (0, int(uid), "") if uid.isdigit() else (1, 0, uid)


# What of a heartbeat is not a doors' word: the platform's own fields. Everything else a worker says beside its status
# is kept as it said it, for whoever reads the view and knows what it means (the subsystem's own passes).
_OWN = ("status", "worker", "ts", "server", "sub", "instance", "capacity", "headroom")


class ReadView:
    def __init__(self, fed: Federation, lost_after: float = 45.0, wall=time.time, lanes: int = 1,
                 backoff: float = 0.0, backoff_max: float = 60.0):
        self.fed, self.lost_after, self.wall = fed, lost_after, wall
        self.snapshots: dict[tuple[str, str], Snapshot] = {}     # (cluster, worker) -> last heartbeat seen
        self.configured: dict[str, list[dict]] = {}              # cluster -> the rows its snapshot carries
        self.configured_at: dict[str, float] = {}                # …and how old that copy is
        self.cluster_ok: dict[str, float] = {}
        self.cluster_down_since: dict[str, float] = {}
        self.passes = 0
        # Lesson 11. `lanes` members are read at once; a member that did not answer is not asked again
        # until `retry_at` — `backoff` seconds after its first silence, doubling to `backoff_max`. With the
        # defaults (one lane, no backoff) a pass is what it was in Lesson 3: every member, in order.
        self.lanes, self.backoff, self.backoff_max = max(1, lanes), backoff, backoff_max
        self.failures: dict[str, int] = {}
        self.retry_at: dict[str, float] = {}
        # Why each member that did not answer did not (the review's eighth pass): "has not reported for 60 s" and
        # "reports through relay east, which runs an older build; update it" are different things to do about it.
        self.why: dict[str, str] = {}

    # -- the one pass ----------------------------------------------------------
    # One member's part of it. The heartbeats, then the cluster's own copy of what SHOULD exist, for the
    # units no worker reports — read in the same call and from the same member, so a member that goes
    # unreachable loses both together rather than leaving one of them stale in a way nothing explains.
    # The snapshot is read ONCE: this used to call `c.snapshot()` twice, for the rows and for their age,
    # which at three clusters was invisible and at three hundred is a third of every pass (Lesson 11).
    @staticmethod
    def _read(c) -> tuple[dict, dict]:
        return c.heartbeats(), (c.snapshot() or {})

    def refresh(self) -> None:
        now = self.wall()
        due = [(n, c) for n, c in self.fed.clusters.items() if self.retry_at.get(n, 0) <= now]
        if self.lanes > 1 and len(due) > 1:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(self.lanes, len(due))) as pool:
                results = list(pool.map(lambda nc: self._try(nc[1]), due))
        else:
            results = [self._try(c) for _, c in due]
        for (name, _), got in zip(due, results):
            if got is None:
                self.cluster_down_since.setdefault(name, now)
                if self.backoff:
                    self.failures[name] = self.failures.get(name, 0) + 1
                    self.retry_at[name] = now + min(self.backoff_max, self.backoff * 2 ** (self.failures[name] - 1))
                continue
            hbs, snap = got
            # Each worker's heartbeat is that worker's (М10's seventh review, part 2): the member's reads skip what does
            # not parse (`federation.published`), and what parses and still is not numbers is skipped here, counted.
            for w, hb in hbs.items():
                try:
                    self.snapshots[(name, w)] = Snapshot(w, name, float(hb.get("ts", 0)), str(hb.get("server", "?")),
                                                         list(hb.get("status", [])),
                                                         {k: v for k, v in hb.items() if k not in _OWN and v is not None},
                                                         str(hb.get("sub", "")))
                except PARSE_ERRORS as e:
                    MEMBER_OBJECTS.garbled(f"{name}/{hb.get('sub')}/heartbeats/{w}", e)
            # What a member published is shown as a cluster's snapshot would carry it (the eleventh review, blocker 4,
            # defence in depth): a shard written by an older build, or a row stored before the rule, could carry a
            # `*_secret` field or an address with a credential in it — no secret field here, no credential in an address.
            from w2cplatform.secrets import is_secret_field, mask_secrets
            self.configured[name] = [{k: v for k, v in mask_secrets([r])[0].items() if not is_secret_field(k)}
                                     if isinstance(r, dict) else r for r in snap.get("units", [])]
            self.configured_at[name] = float(snap.get("ts", 0) or 0)
            self.cluster_ok[name] = now
            self.cluster_down_since.pop(name, None)
            self.failures.pop(name, None)
            self.retry_at.pop(name, None)
        self.passes += 1

    def _try(self, c):
        try:
            got = self._read(c)
        except Unreachable as e:
            self.why[c.name] = str(e)                      # why it did not answer, in its own words: shown with it
            return None
        except PARSE_ERRORS as e:
            # Whatever a member's read still raises of what it published (its copy's rows, a relay's bundle) is that
            # member's: this pass reads it as one that did not answer — its rows kept as last known, counted — and the
            # other members are read (М10's seventh review: one of them stopped the pass of all).
            MEMBER_OBJECTS.garbled(f"{c.name}/(read)", e)
            self.why[c.name] = f"what it published does not parse: {e}"
            return None
        self.why.pop(c.name, None)
        return got

    # -- reads, from memory ----------------------------------------------------
    # The cluster that last reported the unit the domain calls `ref`, and the row it reported — kept when that
    # cluster stops answering, which is the point: an edit for a unit that is off is measured against what the domain
    # last SAW of it (Lesson 9). `refresh` leaves a silent cluster's copy where it was.
    def last_known(self, ref) -> tuple[str, dict] | None:
        for cluster, rows in self.configured.items():
            for row in rows:
                if ref_of(row) == str(ref):
                    return cluster, row
        return None

    # Lesson 11: "where is unit X", answered from this pass's memory instead of a scan of every member.
    # `DomainDirectory.where` reads every cluster's snapshot on every call — at three clusters a detail, at
    # three hundred members two calls each, per unit, per edit. The answer is as old as the last pass, and
    # it says so the way the directory's does: found only in a member that answered, and the silent ones named.
    def where(self, ref) -> Answer:
        down = sorted(n for n in self.fed.clusters if n in self.cluster_down_since or n not in self.cluster_ok)
        searched = sorted(n for n in self.fed.clusters if n not in down)
        hits = [(cl, row) for cl in searched for row in self.configured.get(cl, []) if ref_of(row) == str(ref)]
        if len(hits) > 1:                                  # one member naming another's unit: contested, not a 500
            return Answer(str(ref), None, None, None, searched, down, contested=sorted({cl for cl, _ in hits}))
        if hits:
            cl, row = hits[0]
            return Answer(str(ref), row.get("worker"), row.get("server"), cl, searched, down, sub=row.get("sub"))
        return Answer(str(ref), None, None, None, searched, down)

    def rows(self) -> list[Row]:
        now = self.wall()
        out = []
        for s in self.snapshots.values():
            age = max(0.0, now - s.ts)
            state = "unreachable" if s.cluster in self.cluster_down_since else ("stale" if age > self.lost_after else "live")
            for st in s.status:
                try:
                    # `name` as a string, whatever the worker wrote: a number there broke the search of every operator
                    # (`r.name.lower()`, the review's eighth pass)
                    out.append(Row(_unit_id(st["id"], s.sub), _text(st.get("name")), s.worker, s.cluster, s.server,
                                   st.get("phase", "?"), st.get("position", "?"), int(st.get("revision", 0)),
                                   int(st.get("observed_revision", 0)), int(st.get("epoch", 0)), age, state,
                                   ref_of({**st, "sub": s.sub}), s.sub))
                except PARSE_ERRORS as e:                  # one entry of one worker: that entry's (the seventh review)
                    MEMBER_OBJECTS.garbled(f"{s.cluster}/{s.sub}/heartbeats/{s.worker}#{st.get('id')}", e)
        # What the workers report, and then what the cluster says exists and nobody reports. The second
        # set is small by construction — it is the units that are NOT running — and it is the set an
        # operator is looking for when something has gone wrong.
        # Keyed by what the DOMAIN calls a unit — its `ref` — and not by the cluster's own id: two
        # clusters both have a unit 7 (Lesson 1), and the same unit is identified one way in a
        # worker's status entry and another in the cluster's snapshot. Deduping by the cluster's number
        # would show a configured unit twice, once under each name.
        def ident(cluster: str, sub: str, ref, uid) -> tuple:
            return (cluster, sub, str(ref) if ref else str(uid))

        seen = {ident(r.cluster, r.sub, r.ref, r.unit) for r in out}
        for cl, rows in self.configured.items():
            if cl in self.cluster_down_since:
                continue
            age = max(0.0, now - self.configured_at.get(cl, 0))
            for row in rows:
                sub = str(row.get("sub", ""))
                try:
                    uid = _unit_id(row["id"], sub)
                except PARSE_ERRORS as e:                  # its own list here left out `OverflowError`: `{"id": 1e400}`
                    MEMBER_OBJECTS.garbled(f"{cl}/{sub}/snapshot#{row.get('id')}", e)   # froze every list (the ninth review)
                    continue
                ref = ref_of(row)
                if ident(cl, sub, ref, uid) in seen:
                    continue
                try:
                    revision = int(row.get("revision", 0))
                except PARSE_ERRORS as e:
                    MEMBER_OBJECTS.garbled(f"{cl}/{sub}/snapshot#{uid}", e)
                    revision = 0                           # the row is shown; its revision is not known
                out.append(Row(uid, _text(row.get("name")), str(row.get("worker") or ""), cl,
                               str(row.get("server") or "?"), "unobserved", "", revision,
                               0, 0, age, "configured", ref, sub))
        out.sort(key=lambda r: (r.cluster, r.worker, r.sub, _order(r.unit)))
        return out

    def list(self, q: str = "", page: int = 1, size: int = 50, cluster: str | None = None, sub: str | None = None) -> dict:
        rows = [r for r in self.rows() if (not cluster or r.cluster == cluster) and (not sub or r.sub == sub)
                and (not q or q.lower() in r.name.lower() or q == str(r.unit) or q == r.ref)]
        total = len(rows)
        page_rows = rows[(page - 1) * size: page * size]
        return {"total": total, "page": page, "size": size, "rows": [r.to_json() for r in page_rows],
                "clusters": {n: ("unreachable" if n in self.cluster_down_since else "ok") for n in self.fed.clusters},
                "why": {n: self.why[n] for n in self.cluster_down_since if n in self.why},
                "rpo": self.rpo(),
                "complete": not self.cluster_down_since}

    # How far behind each cluster's published copy is, in seconds. `DomainDirectory.ages()` has computed
    # this since Lesson 1 and nothing outside a test ever called it — so the one number that says "this
    # cluster's controller stopped publishing" was computable and never computed.
    #
    # It is a different silence from the one `causes()` reports. A silent WORKER means units are not
    # running; a stale SNAPSHOT means the cluster is running fine and the domain's picture of it is not
    # moving. Shown apart, because the operator does different things about them.
    def rpo(self) -> dict[str, float | None]:
        """{cluster: seconds behind}, `None` for a cluster that did not answer."""
        try:
            ages = DomainDirectory(self.fed, wall=self.wall).ages()
        except Exception:                                        # noqa: BLE001 — a reader never fails a list
            ages = {}
        return {n: (None if n in self.cluster_down_since else round(ages.get(n), 1) if n in ages else None)
                for n in self.fed.clusters}

    # What this pass saw, left as ONE object in the domain holder's own object store (feedback X): the members and
    # whether each answered, whether the list is complete, the units with the cluster, server and worker they are on
    # and the fields their spec shows (`domain.view`), the causes, and the tables the specs serve (`domain.tables`,
    # each as the holder keeps it — `tables`, by `<sub>/<table>`). The domain holder's own console serves it at
    # `GET /domain` (`w2cplatform.console.domain_view`), and the domain's own door the same (`console.Console`): the
    # platform's console module draws the domain as the root of its tree from it, without asking any member anything;
    # what a table means is the page's.
    #
    # ITS SHAPE IS THE PRODUCT'S (the console module is one file for both, a byte copy of the product's): `members` is a
    # LIST, the holder among them (`holder: true`), each with its `state` — `ok`, `silent` (did not answer: `why`), or
    # `never` (nothing of it read yet) — and `age`, seconds behind; `holder` names the holder, `as_of` is when; `units` by
    # subsystem. `extra` is what the domain's console adds from the records it keeps: the topology, the list of members
    # and who knocks, where its door is (`url`).
    def doc(self, tables: dict | None = None, extra: dict | None = None) -> dict:
        own = ("ref", "unit", "sub", "name", "cluster", "server", "worker", "phase", "worker_state", "as_of")
        shown = {s.name: set(s.domain.view) for s in declared.directory()}

        def unit(r: Row) -> dict:
            d = r.to_json()
            row = self._configured_row(r)
            return {**{k: v for k, v in d.items() if k in own},
                    **{f: row[f] for f in shown.get(r.sub, ()) if f in row and f not in own}}

        def member(n: str, behind) -> dict:
            c, down = self.fed.clusters[n], n in self.cluster_down_since
            return {"name": n, "holder": bool(c.is_domain_holder), "rpo": behind, "age": behind or 0,
                    "state": "silent" if down else "ok" if behind is not None else "never",
                    "reaches": sorted(c.reaches or ()), **({"why": self.why[n]} if down and n in self.why else {})}
        units: dict[str, list] = {s.name: [] for s in declared.directory()}
        for r in self.rows():
            units.setdefault(r.sub, []).append(unit(r))
        now = self.wall()
        holder = next((n for n, c in self.fed.clusters.items() if c.is_domain_holder), None)
        return {"ts": now, "as_of": now, "holder": holder, "complete": not self.cluster_down_since,
                "members": [member(n, r) for n, r in self.rpo().items()], "units": units,
                "causes": [c.sentence() for c in self.causes()], "tables": dict(tables or {}), **(extra or {})}

    def publish(self, objects, tables: dict | None = None, extra: dict | None = None) -> dict:
        from w2cplatform.console import DOMAIN_VIEW
        view = self.doc(tables, extra)
        objects.put(DOMAIN_VIEW, json.dumps(view, ensure_ascii=False, sort_keys=True).encode())
        return view

    def _configured_row(self, r: Row) -> dict:
        for row in self.configured.get(r.cluster, []):
            if str(row.get("sub", "")) == r.sub and str(row.get("id")) == r.unit:
                return row
        return {}

    def causes(self) -> list[Cause]:
        """Silence grouped by the largest failure domain that explains it."""
        now = self.wall()
        causes: list[Cause] = []
        for cl, since in self.cluster_down_since.items():
            ws = [s for s in self.snapshots.values() if s.cluster == cl]
            causes.append(Cause("cluster", cl, now - since, sorted(s.worker for s in ws), sum(len(s.status) for s in ws)))
        silent = [s for s in self.snapshots.values() if s.cluster not in self.cluster_down_since and now - s.ts > self.lost_after]
        by_server: dict[tuple[str, str], list[Snapshot]] = {}
        for s in silent:
            by_server.setdefault((s.cluster, s.server), []).append(s)
        for (cl, server), group in by_server.items():
            all_on_server = [s for s in self.snapshots.values() if s.cluster == cl and s.server == server]
            silent_for = now - max(s.ts for s in group)
            if len(group) == len(all_on_server) and len(group) > 1:
                causes.append(Cause("server", f"{cl}/{server}", silent_for, sorted(s.worker for s in group), sum(len(s.status) for s in group)))
            else:
                for s in group:
                    causes.append(Cause("worker", f"{cl}/{s.worker}", now - s.ts, [s.worker], len(s.status)))
        return sorted(causes, key=lambda c: (-c.units, c.name))
