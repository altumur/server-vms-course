"""The domain's topology — who reaches the domain through whom — as ONE record the operator edits.

Lesson 17 needed three facts that no cluster can observe about itself, because they are the network's POLICY,
not its state: which member reaches the domain only through an office (`via`), which offices cannot be pushed
to and take their streams from the centre (`star`), and which cluster is the centre. They lived in the
environment of three different jobs (`name=report@office`, RELAY_MEMBERS, CENTRE/STAR). Now they live here,
in the domain cluster, edited by CAS and checked when written — and every pass reads them from here: the
books (`Crossings`), the office's relay and bundle (its agent), the domain's copy of each member (`apply`).

What a cluster CAN observe — the networks it sees — is not here: it says that itself (`federation.REACHES`).

    domain/topology   in the domain cluster's Variables: {"doc": {rev, centre, star: [...], via: {member: office}}}
"""
from __future__ import annotations

import json

from cluster.variables import Conflict

TOPOLOGY = "domain/topology"


class Topology:
    def __init__(self, domain_vars):
        self.vars = domain_vars

    def read(self) -> dict:
        items, _ = self.vars.get(TOPOLOGY)
        doc = json.loads(items["doc"]) if items and items.get("doc") else {}
        return {"rev": int(doc.get("rev", 0)), "centre": doc.get("centre"), "star": list(doc.get("star", [])),
                "via": dict(doc.get("via", {}))}

    def centre(self) -> str | None:
        return self.read()["centre"]

    def star(self) -> frozenset:
        return frozenset(self.read()["star"])

    def via(self, member: str) -> str | None:
        return self.read()["via"].get(member)

    def relayed_by(self, office: str) -> list[str]:
        return sorted(m for m, o in self.read()["via"].items() if o == office)

    def edit(self, mutate, base_rev: int, known=None, by: str | None = None) -> int:
        """`mutate(doc)` changes {centre, star, via}. `known`: the clusters of the domain — a name that is not
        one is refused (409, with the reason), as is a topology that contradicts itself. Nothing is written
        then. `base_rev` is the revision the editor was looking at: two editors are told, not overwritten."""
        items, idx = self.vars.get(TOPOLOGY)
        doc = self.read()
        if doc["rev"] != base_rev:
            raise Conflict(f"the topology is at rev {doc['rev']}; the edit was made against rev {base_rev}")
        new = {"centre": doc["centre"], "star": list(doc["star"]), "via": dict(doc["via"])}
        mutate(new)
        reasons = refusals(new, known)
        if reasons:
            from .api import ApiError
            raise ApiError(409, "; ".join(reasons))
        new.update(rev=doc["rev"] + 1, by=by, star=sorted(set(new["star"])))
        self.vars.put(TOPOLOGY, {"doc": json.dumps(new, sort_keys=True)}, cas=idx)
        return new["rev"]


def refusals(doc: dict, known=None) -> list[str]:
    out, known = [], set(known) if known is not None else None
    centre, star, via = doc.get("centre"), set(doc.get("star", [])), doc.get("via", {})
    names = ([("centre", centre)] if centre else []) + [("star", s) for s in sorted(star)] + \
            [(f"via of {m}", o) for m, o in sorted(via.items())] + [("member", m) for m in sorted(via)]
    if known is not None:
        out += [f"{what}: {n} is not a cluster of this domain" for what, n in names if n not in known]
    if star and not centre:
        out.append("a star office takes its streams from the centre, and there is no centre")
    if centre and centre in star:
        out.append(f"{centre} is the centre and cannot be a star office")
    for m, o in sorted(via.items()):
        if m == o:
            out.append(f"{m} cannot reach the domain through itself")
        elif o in via:
            out.append(f"{m} goes through {o}, which itself goes through {via[o]}: one office between a member and "
                       f"the domain (Lesson 17)")
    return out


def apply(fed, topology: Topology, domain_objects, lost_after: float = 45.0, wall=None) -> list[str]:
    """Make the domain's copy of each REPORTING member read where the topology says it reports: its own
    report, or its office's bundle. A member moved behind an office, or out from behind one, is read the new
    way on the next pass — no restart. Returns the members whose road changed."""
    import time
    from .uplink import _CopyObjects, member_copy
    moved = []
    if topology.read()["rev"] == 0:
        return moved                                     # never written: the configuration's `report@office` stands
    for name, c in list(fed.clusters.items()):
        if not isinstance(c.objects, _CopyObjects):
            continue                                     # a cluster the domain reads directly: not a reporting member
        want = topology.via(name)
        if want != c.via:
            fed.clusters[name] = member_copy(name, domain_objects, reaches=c.reaches, lost_after=lost_after,
                                             wall=wall or time.time, via=want)
            moved.append(name)
    return moved
