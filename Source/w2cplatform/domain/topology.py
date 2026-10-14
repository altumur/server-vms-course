"""The domain's topology — who reaches the domain through whom — as ONE record the operator edits.

Lesson 17 needed three facts that no cluster can observe about itself, because they are the network's POLICY,
not its state: which member reaches the domain only through a relay (`via`), which relays cannot be pushed
to and take their members' data from the centre (`star`), and which cluster is the centre. They lived in the
environment of three different jobs (`name=report@relay`, RELAY_MEMBERS, CENTRE/STAR). Now they live here,
in the domain holder, edited by CAS and checked when written — and every pass reads them from here: the
books, the relay's copying down and its bundle (its agent), the domain's copy of each member (`apply`).

What a cluster CAN observe — the networks it sees — is not here: it says that itself (`federation.REACHES`).

    domain/topology   in the domain holder's Variables: {"doc": {rev, centre, star: [...], via: {member: relay}}}
"""
from __future__ import annotations

import json

from w2cplatform.variables import Conflict

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

    def relayed_by(self, relay: str) -> list[str]:
        return sorted(m for m, o in self.read()["via"].items() if o == relay)

    def edit(self, mutate, base_rev: int, known=None, by: str | None = None, domain: str | None = None) -> int:
        """`mutate(doc)` changes {centre, star, via}. `known`: the clusters of the domain — a name that is not
        one is refused (409, with the reason), as is a topology that contradicts itself. Nothing is written
        then. `base_rev` is the revision the editor was looking at: two editors are told, not overwritten."""
        items, idx = self.vars.get(TOPOLOGY)
        doc = self.read()
        if doc["rev"] != base_rev:
            raise Conflict(f"the topology is at rev {doc['rev']}; the edit was made against rev {base_rev}")
        new = {"centre": doc["centre"], "star": list(doc["star"]), "via": dict(doc["via"])}
        mutate(new)
        reasons = refusals(new, known, domain)
        if reasons:
            from .api import ApiError
            raise ApiError(409, "; ".join(reasons))
        new.update(rev=doc["rev"] + 1, by=by, star=sorted(set(new["star"])))
        self.vars.put(TOPOLOGY, {"doc": json.dumps(new, sort_keys=True)}, cas=idx)
        return new["rev"]


def refusals(doc: dict, known=None, domain: str | None = None) -> list[str]:
    """`domain`: the domain holder. Nobody reaches the domain THROUGH it — whoever reaches the domain holder
    reaches the domain — and it goes through nobody (feedback AM)."""
    out, known = [], set(known) if known is not None else None
    centre, star, via = doc.get("centre"), set(doc.get("star", [])), doc.get("via", {})
    names = ([("centre", centre)] if centre else []) + [("star", s) for s in sorted(star)] + \
            [(f"via of {m}", o) for m, o in sorted(via.items())] + [("member", m) for m in sorted(via)]
    if known is not None:
        out += [f"{what}: {n} is not a cluster of this domain" for what, n in names if n not in known]
    if star and not centre:
        out.append("a star relay takes its members' data from the centre, and there is no centre")
    if centre and centre in star:
        out.append(f"{centre} is the centre and cannot be a star relay")
    for m, o in sorted(via.items()):
        if domain and o == domain:
            out.append(f"{m} through {domain}, the domain's holder: whoever reaches it reaches the domain")
            continue
        if domain and m == domain:
            out.append(f"{domain} is the domain's holder and goes through nobody")
            continue
        if m == o:
            out.append(f"{m} cannot reach the domain through itself")
        elif o in via:
            out.append(f"{m} goes through {o}, which itself goes through {via[o]}: one relay between a member and "
                       f"the domain (Lesson 17)")
    return out


def apply(fed, topology: Topology, domain_objects, lost_after: float = 45.0, wall=None) -> list[str]:
    """Make the domain's copy of each REPORTING member read where the topology says it reports: its own
    report, or its relay's bundle. A member moved behind a relay, or out from behind one, is read the new
    way on the next pass — no restart. Returns the members whose road changed."""
    import time
    from .uplink import _CopyObjects, member_copy
    moved = []
    if topology.read()["rev"] == 0:
        return moved                                     # never written: the configuration's `report@relay` stands
    for name, c in list(fed.clusters.items()):
        if not isinstance(c.objects, _CopyObjects):
            continue                                     # a cluster the domain reads directly: not a reporting member
        want = topology.via(name)
        if want != c.via:
            fed.clusters[name] = member_copy(name, domain_objects, reaches=c.reaches, lost_after=lost_after,
                                             wall=wall or time.time, via=want)
            moved.append(name)
    return moved


def member_topology(vars_, member):
    """The topology at the current holder or its carried member copy (ADR-0074)."""
    from .memberbook import holds
    key = TOPOLOGY if holds(vars_, member) else "domain/member-topology"
    items, _ = vars_.get(key)
    doc = json.loads(items["doc"]) if items and items.get("doc") else {}
    if not isinstance(doc, dict):
        raise ValueError("invalid topology")
    result = {"rev": doc.get("rev", 0), "centre": doc.get("centre"),
              "star": doc.get("star", []), "via": doc.get("via", {})}
    if type(result["rev"]) is not int or result["rev"] < 0 or not isinstance(result["star"], list) or not isinstance(result["via"], dict) \
            or refusals(result):
        raise ValueError("invalid topology")
    return result


def poll_home(vars_, member, *, authoritative=False):
    """The member's poll home: its relay, the centre, or the confirmed holder.

    A worker selects the topology by its local identity, independently of the
    member whose home is asked. Holder services explicitly read authoritative
    topology; a stale member copy never overrides it. Unknown policy is an error.
    """
    from w2cplatform.canonical import parse_json
    from w2cplatform.rows import PARSE_ERRORS
    def name(value):
        return isinstance(value, str) and bool(value) and not any(ord(ch) < 33 for ch in value)
    try:
        if not name(member):
            raise ValueError()
        record, _ = vars_.get("domain/holder")
        holder = parse_json(record["doc"]) if record else None
        if not isinstance(holder, dict) or not name(holder.get("holder")) \
                or type(holder.get("term")) is not int or holder["term"] <= 0:
            raise ValueError()
        here = holder["holder"]
        if not authoritative:
            local, _ = vars_.get("domain/member")
            if not isinstance(local, dict) or not name(local.get("cluster")):
                raise ValueError()
            here = local["cluster"]
        key = TOPOLOGY if authoritative or here == holder["holder"] else "domain/member-topology"
        items, _ = vars_.get(key)
        doc = parse_json(items["doc"]) if items is not None else {}
        if not isinstance(doc, dict):
            raise ValueError()
        rev, centre, star, via = doc.get("rev", 0), doc.get("centre"), doc.get("star", []), doc.get("via", {})
        if type(rev) is not int or rev < 0 or centre is not None and not name(centre) \
                or not isinstance(star, list) or any(not name(n) for n in star) or len(set(star)) != len(star) \
                or not isinstance(via, dict) or any(not name(m) or not name(r) for m, r in via.items()) \
                or rev == 0 and (centre is not None or star or via) \
                or refusals({"centre": centre, "star": star, "via": via}, domain=holder["holder"]):
            raise ValueError()
        return via.get(member) or centre or holder["holder"]
    except PARSE_ERRORS:
        raise ValueError("poll home needs a confirmed holder and valid topology") from None
