"""Inputs for the book not yet transferred in ADR-0074 (asks).

C2 observations are published by ordinary workers. The only assignment source is
platform placement; this service neither places recordings nor publishes C2 books.
"""
from __future__ import annotations
import json
import time
from w2cplatform.domain.placement import PREFIX, decode


class BookInputs:
    def __init__(self, domain_vars, view, wall=time.time, sealer=None,
                 centre: str | None = None, star=frozenset(), topology=None):
        self.vars, self.view, self.wall, self.sealer = domain_vars, view, wall, sealer
        # The holder's store as the books see it: what they read, opened; what they write, sealed (`keys.OpenedVars`).
        from .keys import OpenedVars
        if not isinstance(domain_vars, OpenedVars):
            self.vars = OpenedVars(domain_vars, sealer)
        # Lesson 17: the monitoring centre, and the recording clusters that cannot be pushed to — their cameras
        # push to the centre instead, and the cluster pulls its streams from there.
        # Given explicitly they stand; otherwise the operator's topology says (`domain/topology.py`), read on
        # every use, so an edit there reaches the next pass without a restart.
        self._centre, self._star, self.topology = centre, (frozenset(star) if star else None), topology


    def _topo(self) -> dict | None:
        doc = self.topology.read() if self.topology is not None else None
        return doc if doc and doc["rev"] else None      # written by the operator: it wins over what was configured


    @property
    def centre(self) -> str | None:
        doc = self._topo()
        return doc["centre"] if doc else self._centre


    @property
    def star(self) -> frozenset:
        doc = self._topo()
        return frozenset(doc["star"]) if doc else (self._star or frozenset())


    def via_of(self, member: str | None) -> str | None:
        """The relay this member reaches the domain through: the topology, else how its copy was configured."""
        if member is None:
            return None
        doc = self._topo()
        if doc:
            return doc["via"].get(member)
        c = self.view.fed.clusters.get(member)
        return c.via if c is not None else None


    def members(self) -> dict[str, str]:
        """{ref: its own cluster} for every member camera — every camera that holds a poll to an ingest."""
        out = {}
        for (cluster, _worker), s in self.view.snapshots.items():
            if (s.doors or {}).get("polls") or (s.doors or {}).get("push"):
                for st in s.status:
                    if st.get("ref"):
                        out[str(st["ref"])] = cluster
        return out


    def can_of(self, ref: str) -> dict | None:
        from w2cplatform.domain.federation import MEMBER_OBJECTS
        best = None
        for (cluster, worker), s in self.view.snapshots.items():
            for st in s.status:
                if str(st.get("ref", "")) == str(ref) and st.get("can") is not None and (best is None or s.ts > best[0]):
                    can = st["can"]
                    if not isinstance(can, dict) or not isinstance(can.get("events", []), list) \
                            or not all(isinstance(k, str) for k in can.get("events", [])):
                        MEMBER_OBJECTS.garbled(f"{cluster}/cam/heartbeats/{worker}#{ref}/can", TypeError("not a description"))
                        continue
                    best = (s.ts, can)
        return best[1] if best else None


    def unrecorded(self) -> dict[str, str]:
        """{ref: its own cluster} for every member camera that no cluster records: it polls the poll home."""
        rec = self.all()
        return {ref: c for ref, c in self.members().items() if ref not in rec}


    def polled_at(self, ref: str) -> str | None:
        """The cluster whose ingest this camera polls: the one that records it (the centre for a star), or the
        poll home for a pushing camera nobody records; None for a camera that polls nothing."""
        if str(ref) not in self.members():
            return None                                  # not a member camera: it polls nothing, nobody can ask it
        on = self.all().get(str(ref))
        if on is not None:
            return self.centre if on in self.star and self.centre else on
        home = self.unrecorded().get(str(ref))
        if home is None:
            return None
        from w2cplatform.domain.topology import poll_home
        return poll_home(self.vars, home, authoritative=True)


    def all(self):
        out = {}
        for key in self.vars.list(PREFIX + "rec/"):
            items, _ = self.vars.get(key)
            if items:
                out[key[len(PREFIX + "rec/"):]] = decode(items)["cluster"]
        return out
