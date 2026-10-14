"""Lesson 1 — placement at the level above the one М11 built.

    Servers   pick the SERVER    on resources        because each knows its own — and how many workers, and where
    Cluster   picks the WORKER   on capacity         because only its controller sees its workers' headroom (М11 Lesson 10)
    Domain    picks the CLUSTER  on REACHABILITY     because only it knows which clusters exist and what each can see

Reachability, not capacity: a unit on the warehouse VLAN can be reached
from the warehouse cluster and from nowhere else. Capacity only breaks ties
among clusters that can see the unit at all.

Only place when you must: the unit is new, or an operator asked. A dead
server is not a trigger (its worker moves; its units follow its name). A
dead cluster is not a trigger either — its units cannot be reached from
anywhere else.

The placement is STORED, with a reason and a time, in the domain holder's
store under domain/placement/<sub>/<ref> — by check-and-set, which is why two
placers racing is harmless: the second gets a conflict and re-reads.
"""
from __future__ import annotations

import time
import json
import math
import re
from dataclasses import dataclass

from w2cplatform.variables import Conflict, Variables

from .federation import Cluster, Federation


@dataclass(frozen=True)
class UnitSite:
    unit: str
    network: str                      # "vlan:b" — where the unit's traffic can be seen from
    load: float = 1.0


@dataclass
class ClusterPlacement:
    cluster: str
    reason: str
    at: float
    rev: int
    origin: str = ""
    copies: tuple[str, ...] = ()


class Refused(Exception):
    """No cluster can reach that network — 'the domain cannot place it',
    never 'cluster X is full'."""


class ClusterPlacer:
    def __init__(self, fed: Federation, vars_: Variables | None = None, headroom=None, clock=time.time, *, sub: str):
        """`headroom(cluster) -> float` is the cluster's spare capacity, from its own
        placement service; the domain does not measure it."""
        path(sub, "check")
        self.sub = sub
        self.fed = fed
        self.vars = vars_ or fed.domain_holder.vars
        self.headroom = headroom or (lambda c: 1.0)
        self.clock = clock

    def path(self, unit) -> str:
        return path(self.sub, unit)

    def current(self, unit) -> ClusterPlacement | None:
        items, _ = self.vars.get(self.path(unit))
        if not items or not items.get("cluster"):
            return None
        d = decode(items)
        return ClusterPlacement(d["cluster"], d["reason"], d["at"], d["rev"], d["origin"], tuple(d["copies"]))

    def candidates(self, site: UnitSite, unreachable: set[str] = frozenset()) -> list[Cluster]:
        from .members import Members
        admitted = set(Members(self.vars).names())
        return [c for c in self.fed.clusters.values()
                if c.name in admitted and site.network in c.networks() and c.name not in unreachable]

    def place(self, site: UnitSite, unreachable: set[str] = frozenset()) -> ClusterPlacement:
        """Place ONE new unit. An existing placement is returned untouched."""
        have = self.current(site.unit)
        if have is not None:
            return have
        cands = self.candidates(site, unreachable)
        if not cands:
            seen = sorted(c.name for c in self.fed.clusters.values() if site.network in c.networks())
            if seen:
                raise Refused(f"unit {site.unit}: the only cluster(s) reaching {site.network} "
                              f"({', '.join(seen)}) are unreachable; not placing elsewhere — nothing else can see it")
            raise Refused(f"unit {site.unit}: no cluster in the domain reaches {site.network}")
        best = max(sorted(cands, key=lambda c: c.name), key=lambda c: self.headroom(c.name))
        why = (f"only cluster reaching {site.network}" if len(cands) == 1
               else f"most headroom ({self.headroom(best.name):.1f}) among {len(cands)} reaching {site.network}")
        return self._store(site.unit, best.name, why)

    def _store(self, unit, cluster: str, reason: str, retries: int = 5) -> ClusterPlacement:
        for _ in range(retries):
            have = self.current(unit)
            if have is not None:
                return have
            _, idx = self.vars.get(self.path(unit))
            try:
                assign(self.vars, self.sub, unit, {"cluster": cluster, "reason": reason}, self.clock, cas=idx)
                return self.current(unit)
            except Conflict:
                continue
        raise RuntimeError("could not store placement after conflicts")

    def rebalance_across_clusters(self, *a, **k):
        raise NotImplementedError("a worker never crosses a cluster (М11); the domain moves a unit between "
                                  "clusters only when an operator asks, and then as delete-here/create-there")


PREFIX = "domain/placement/"
COPIES_PREFIX = "domain/placed/"


def path(sub, ref):
    ref = str(ref)
    if not isinstance(sub, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", sub) \
            or not ref or ref in (".", "..") or "/" in ref or any(ord(c) < 32 for c in ref):
        raise ValueError("invalid placement identity")
    return PREFIX + sub + "/" + ref


def decode(items):
    """Strict assignment row, with lists stored as JSON in Variables' string values."""
    if not isinstance(items, dict) or set(items) - {"cluster", "origin", "copies", "reason", "at", "rev"}:
        raise ValueError("invalid placement row")
    try:
        copies = json.loads(items.get("copies", "[]"))
        out = {"cluster": items["cluster"], "origin": items.get("origin", ""), "copies": copies,
               "reason": items.get("reason", ""), "at": float(items["at"]), "rev": int(items["rev"])}
        if not isinstance(out["cluster"], str) or not out["cluster"] or not isinstance(out["origin"], str) \
                or not isinstance(out["reason"], str) or not isinstance(copies, list) \
                or any(not isinstance(n, str) or not n for n in copies) or len(set(copies)) != len(copies) \
                or out["cluster"] in copies or not math.isfinite(out["at"]) or out["rev"] <= 0:
            raise ValueError()
        return out
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ValueError("invalid placement row") from None


def read(vars_, sub, ref):
    items, _ = vars_.get(path(sub, ref))
    return decode(items) if items else None


def placed(vars_, sub, ref):
    """Member copy or holder record, newest revision (ADR-0074, holder correction)."""
    record = path(sub, ref)
    copy = COPIES_PREFIX + record[len(PREFIX):]
    candidates = []
    for key in (copy, record):
        items, _ = vars_.get(key)
        if items:
            candidates.append(decode(items))
    if not candidates:
        return None
    latest = max(candidates, key=lambda value: value["rev"])
    if any(value["rev"] == latest["rev"] and value != latest for value in candidates):
        raise ValueError("conflicting placement locations")
    return latest


def overview(vars_):
    """The operator's typed assignment view, never raw store rows."""
    from .booknames import MUTATIONS
    with MUTATIONS:
        counter, _ = vars_.get(PREFIX.rstrip("/"))
        rev = int((counter or {}).get("rev", 0))
        if rev < 0:
            raise ValueError("invalid placement revision")
        records = {}
        for key in vars_.list(PREFIX):
            parts = key[len(PREFIX):].split("/")
            if len(parts) != 2 or path(*parts) != key:
                raise ValueError("invalid placement identity")
            items, _ = vars_.get(key)
            if items:
                records["/".join(parts)] = decode(items)
        return {"rev": rev, "records": records}


def remove(vars_, sub, ref):
    from .booknames import MUTATIONS
    from .api import ApiError
    key = path(sub, ref)
    with MUTATIONS:
        items, index = vars_.get(key)
        if items is None:
            raise ApiError(404, "no assignment")
        decode(items)
        while True:
            counter, ci = vars_.get(PREFIX.rstrip("/"))
            rev = int((counter or {}).get("rev", 0)) + 1
            if rev <= 0:
                raise ValueError("invalid placement revision")
            try:
                vars_.put(PREFIX.rstrip("/"), {"rev": str(rev)}, cas=ci)
                break
            except Conflict:
                continue
        vars_.delete(key, cas=index)
        return overview(vars_)


def assign(vars_, sub, ref, body, wall=time.time, *, cas=None):
    """Holder/operator write: member links checked against admission, no payload in errors."""
    from .members import Members
    from .api import ApiError
    from .booknames import MUTATIONS
    key = path(sub, ref)
    if not isinstance(body, dict) or set(body) - {"cluster", "origin", "copies", "reason"}:
        raise ApiError(400, "placement takes cluster, origin, copies and reason")
    candidate = {**body, "copies": json.dumps(body.get("copies", [])), "at": str(wall()), "rev": "1"}
    try:
        decoded = decode(candidate)
    except ValueError:
        raise ApiError(400, "invalid placement fields") from None
    candidate = {"cluster": decoded["cluster"], "origin": decoded["origin"],
                 "copies": json.dumps(sorted(decoded["copies"])), "reason": decoded["reason"],
                 "at": str(decoded["at"]), "rev": "1"}
    decoded["copies"] = sorted(decoded["copies"])
    with MUTATIONS:
        members = Members(vars_).read()["members"]
        links = [decoded["cluster"], *decoded["copies"], *([decoded["origin"]] if decoded["origin"] else [])]
        if any(n not in members for n in links):
            raise ApiError(400, "placement names an unadmitted member")
        old, index = vars_.get(key)
        if old:
            try:
                before = decode(old)
            except ValueError:
                before = None
            if before and all(before[k] == decoded[k] for k in ("cluster", "origin", "copies", "reason")):
                if cas is not None and cas != index:
                    raise Conflict(key)
                return before
        while True:
            counter, ci = vars_.get("domain/placement")
            try:
                rev = int((counter or {}).get("rev", 0)) + 1
                if rev <= 0:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ApiError(503, "placement revision is unreadable") from None
            try:
                vars_.put("domain/placement", {"rev": str(rev)}, cas=ci)
                break
            except Conflict:
                continue
        candidate["rev"] = str(rev)
        vars_.put(key, candidate, cas=index if cas is None else cas)
        return decode(candidate)
