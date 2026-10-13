"""Inputs for the books not yet transferred in ADR-0074 (polls, asks, accounts).

C2 observations are published by ordinary workers. The only assignment source is
platform placement; this service neither places recordings nor publishes C2 books.
"""
from __future__ import annotations
import json
import time
from .keys import POLLS_PATH
from w2cplatform.domain.federation import Unreachable
from w2cplatform.trust.tokens import kid_of
from w2cplatform.domain.placement import PREFIX, decode


class BookInputs:
    def __init__(self, domain_vars, view, wall=time.time, issuer=None, token_lifetime: float | None = None, sealer=None,
                 centre: str | None = None, star=frozenset(), poll_home: str | None = None, topology=None):
        """`issuer` is Lesson 16: the domain signer's token issuer. The remaining polls book carries its token until C4."""
        self.vars, self.view, self.wall = domain_vars, view, wall
        # The tokens its books carry are of the kinds the spec declares (`domain.tokens`), issued by the domain's signer:
        # an issuer that is the signer's own (a test's, the holder's process) is asked through the declaration too.
        if issuer is not None and not hasattr(issuer, "lifetime"):
            from w2cplatform.domain.declared import token_kinds
            from w2cplatform.trust.tokens import DeclaredIssuer
            issuer = DeclaredIssuer(issuer, token_kinds())
        self.issuer = issuer
        # The holder's store as the books see it: what they read, opened; what they write, sealed (`keys.OpenedVars`).
        from .keys import OpenedVars
        if not isinstance(domain_vars, OpenedVars):
            self.vars = OpenedVars(domain_vars, sealer)
        self.token_lifetime = token_lifetime if token_lifetime is not None else (
            issuer.lifetime("stream") if issuer is not None else 86400.0)
        # Lesson 17: the monitoring centre, and the recording clusters that cannot be pushed to — their cameras
        # push to the centre instead, and the cluster pulls its streams from there.
        # Given explicitly they stand; otherwise the operator's topology says (`domain/topology.py`), read on
        # every use, so an edit there reaches the next pass without a restart.
        self._centre, self._star, self.topology = centre, (frozenset(star) if star else None), topology
        # Lesson 16, step 8: where a pushing camera that nobody records keeps its poll — a cluster every camera
        # already reaches. The centre if there is one, else the cluster that holds the domain: a camera reaches
        # it for its agent's pass anyway.
        self.poll_home = poll_home


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


    def _poll_home(self, home: str | None = None) -> str | None:
        """Where a camera of cluster `home` polls when nobody records it. A camera that reaches only its relay
        (Lesson 17, `report@relay`) polls that relay's ingest: the centre and the domain's holder are exactly
        what it cannot reach."""
        via = self.via_of(home)
        if via:
            return via
        if self.poll_home or self.centre:
            return self.poll_home or self.centre
        dc = getattr(self.view.fed, "domain_holder", None)
        return dc.name if dc is not None else None


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
        return self._poll_home(home) if home is not None else None


    def _ingest(self, ref: str, on: str, home: str, now: float, old: dict | None) -> dict | None:
        from .ingest import audience, ingest_urls
        if on in self.star and self.centre:
            on = self.centre                             # a star: the camera pushes to the centre, never to its relay
        c = self.view.fed.clusters.get(on)
        if self.issuer is None or c is None:
            return None
        try:
            urls = ingest_urls(on, c.objects, now)
        except Unreachable:
            urls = []
        # Each address through the members' one reader (`ingest_urls`; the review's ninth pass, major: a STRING read as a
        # list told the camera to push to its letters): a string, or that recorder says nothing.
        if not urls:
            return old                                   # silent, or no recorder there says an ingest: keep what the camera has
        if old and old.get("urls") == urls and _until(old) - now > self.token_lifetime / 2 \
                and kid_of(old.get("token_secret", "")) == self.issuer.kid:
            return old
        token = self.issuer.issue("stream", home, now=now, aud=[on], ref=ref)
        return {"urls": urls, "token_secret": token, "until": now + self.token_lifetime}


    def publish_polls(self) -> dict[str, dict]:
        now, books = self.wall(), {}
        for ref, home in self.unrecorded().items():
            on = self._poll_home(home)
            if on is None:
                continue
            have, _ = self.vars.get(f"{POLLS_PATH}/{home}")
            old = _entry((have or {}).get(ref), None)
            ingest = self._ingest(ref, on, home, now, old)
            if ingest:
                books.setdefault(home, {})[ref] = json.dumps({**ingest, "cluster": on}, sort_keys=True)
        for home in {h for h in self.unrecorded().values()} | set(books):
            path = f"{POLLS_PATH}/{home}"
            have, idx = self.vars.get(path)
            if (have or {}) != books.get(home, {}):
                self.vars.put(path, books.get(home, {}), cas=idx)
        return books


    def all(self):
        out = {}
        for key in self.vars.list(PREFIX + "rec/"):
            items, _ = self.vars.get(key)
            if items:
                out[key[len(PREFIX + "rec/"):]] = decode(items)["cluster"]
        return out


def _entry(raw, default):
    if raw is None:
        return default
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return default
    return value if isinstance(value, dict) else default


def _until(row):
    from w2cplatform.rows import finite
    try:
        return finite(row.get("until") or 0)
    except (ValueError, TypeError, OverflowError):
        return 0.0
