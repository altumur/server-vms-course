"""Lesson 13 — a stream from another cluster.

A camera that is its own cluster still wants a server to record it: the card in it holds days, the server's
volume holds months, and the card is in the camera a thief takes with him. The server's recorder does what
it always does — pulls RTSP, writes its volume, closes gaps from the device's own archive (М10B Lessons
15–16). What changes is only where it FINDS the camera. In one cluster it found the holder's `live_url`,
`playback_url` and `coverage` in its own cluster's heartbeats. This camera's heartbeat is in the camera's
cluster, which the recorder cannot read and must not depend on.

So the domain — which reads every member — publishes a SOURCE BOOK per recording cluster: for each camera
of another cluster that this one records, where it was last seen, and when. The cluster's agent carries it
home, as it carries grants. The recorder resolves `ref:<serial>` against its own cluster's copy, so a
recording goes on with the domain switched off, from the address last carried.

    data crosses    footage and coverage go from the camera's cluster to the server's
    work does not   the recorder stays in the server cluster; the camera learns of no server; no row, no
                    epoch and no request is written into the camera's cluster by anyone but itself
    one consumer    a camera serves one live session and one backfill (М10B Lesson 15). Which cluster
                    records it is therefore a DOMAIN decision, stored, one per camera — the same shape as
                    Lesson 1's placement, and refused the same way when a second cluster asks
    a hint          what the book says about the card is as old as the book. The device is asked again
                    before a range is fetched, and a range the card no longer holds is dropped, not retried

    domain/crossings            in the domain cluster: {ref: the cluster that records it}
    domain/sources/<cluster>    in the domain cluster: that cluster's source book
    domain/sources              in the recording cluster: its agent's copy
    domain/primaries/<cluster>  in the domain cluster: the camera cluster's book of primaries
    domain/primaries            in the camera's cluster: its agent's copy, read by the backup on its card
    domain/poll/<cluster>       in the domain cluster: for a camera that pushes and that NOBODY records, the
                                ingest it polls anyway — so an ask reaches it (Lesson 16, step 8)
    domain/poll                 in the camera's cluster: its agent's copy

The book of primaries is the source book the other way round. A backup on the camera's card with
`when: offline` records while its primary should be written and is not (М10B Lesson 26) — and its primary
is here, in the recording cluster, where the camera's cluster cannot look. So the domain says, per camera,
who records it, whether that recording SHOULD be written (enabled, its `until` not passed) and whether it IS
(a recorder's fresh heartbeat reports it running). No time in it: a book that changed on every pass would
be rewritten on the camera's flash every few seconds. How current it is, the camera learns from its agent's
last contact with the domain, which lives in RAM.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from cluster.variables import Conflict
from vms.archive import subtract

from .agent import POLL_PATH, PRIMARIES_PATH, SOURCES_PATH
from .federation import Unreachable
from .api import ApiError

CROSSINGS = "domain/crossings"


class Crossings:
    """The domain's side: which cluster records which camera of another cluster, and the books."""

    def __init__(self, domain_vars, view, wall=time.time, issuer=None, token_lifetime: float = 86400.0,
                 centre: str | None = None, star=frozenset(), poll_home: str | None = None, topology=None):
        """`issuer` is Lesson 16: the domain signer's token issuer. Given it, the book of primaries also tells
        a camera where to PUSH — the recording cluster's ingest — with a stream token for it."""
        self.vars, self.view, self.wall = domain_vars, view, wall
        self.issuer, self.token_lifetime = issuer, token_lifetime
        # Lesson 17: the monitoring centre, and the recording clusters that cannot be pushed to — their cameras
        # push to the centre instead, and the cluster pulls its streams from there.
        # Given explicitly they stand; otherwise the operator's topology says (`domain/topology.py`), read on
        # every use, so an edit there reaches the next pass without a restart.
        self._centre, self._star, self.topology = centre, (frozenset(star) if star else None), topology
        # Lesson 16, step 8: where a pushing camera that nobody records keeps its poll — a cluster every camera
        # already reaches. The centre if there is one, else the cluster that hosts the domain: a camera reaches
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
        (Lesson 17, `report@relay`) polls that relay's ingest: the centre and the domain's cluster are exactly
        what it cannot reach."""
        via = self.via_of(home)
        if via:
            return via
        if self.poll_home or self.centre:
            return self.poll_home or self.centre
        dc = getattr(self.view.fed, "domain_cluster", None)
        return dc.name if dc is not None else None

    # Who holds a poll — one rule (feedback AL): EVERY member camera, its door open or not. A camera of ours
    # says so in its heartbeat (`polls`); one that pushes polls by definition. A camera of a server cluster that
    # does not run the platform holds none, and cannot be asked: a scenario on it is refused when written.
    def members(self) -> dict[str, str]:
        """{ref: its own cluster} for every member camera — every camera that holds a poll to an ingest."""
        out = {}
        for (cluster, _worker), s in self.view.snapshots.items():
            if (s.doors or {}).get("polls") or (s.doors or {}).get("push"):
                for st in s.status:
                    if st.get("ref"):
                        out[str(st["ref"])] = cluster
        return out

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

    def all(self) -> dict[str, str]:
        items, _ = self.vars.get(CROSSINGS)
        return dict(items or {})

    def record(self, ref: str, on: str) -> dict:
        ref = str(ref)
        known = self.view.last_known(ref)
        if known is None:
            raise ApiError(404, f"camera {ref} has never been seen by the domain; nothing to record")
        if known[0] == on:
            raise ApiError(400, f"camera {ref} is in {on} already: a cluster records its own cameras as it always did")
        for _ in range(10):
            items, idx = self.vars.get(CROSSINGS)
            items = dict(items or {})
            if items.get(ref) == on:
                return {"camera": ref, "recorded_by": on, "from": known[0]}
            if ref in items:
                raise ApiError(409, f"camera {ref} is recorded by {items[ref]} already: a device serves one live "
                                    f"session and one backfill, and a second recorder would take them from the first")
            items[ref] = on
            try:
                self.vars.put(CROSSINGS, items, cas=idx)
                return {"camera": ref, "recorded_by": on, "from": known[0]}
            except Conflict:
                continue
        raise ApiError(409, f"could not record {ref} on {on}: the crossings kept changing")

    # Each recording cluster's book, from the read view's memory: the doors the camera's worker last
    # published, with the time they were published. A camera whose cluster is silent keeps its last entry
    # and says so — the address it had is the best there is, and it is usually still right.
    def publish(self) -> dict[str, dict]:
        books: dict[str, dict] = {}
        for ref, on in self.all().items():
            books.setdefault(on, {})
            found = self._doors(ref)
            if found is not None:
                books[on][ref] = json.dumps(found, sort_keys=True)
        for on, book in books.items():
            path = f"{SOURCES_PATH}/{on}"
            have, idx = self.vars.get(path)
            if have != book:
                self.vars.put(path, book, cas=idx)
        return books

    # Each camera cluster's book of primaries: for every camera of it that another cluster records, what the
    # recording cluster's own objects say — its rec snapshot (desired: enabled, until) and its recorders'
    # heartbeats (actual: running). Read, like the source book, from what the recording cluster publishes and
    # nothing else. A recording cluster that does not answer is a primary nobody can vouch for: `written` is
    # false, and the card covers after its grace — which is right when the room is down, and only costs a
    # card's worth of writing when merely the domain cannot see it.
    def publish_primaries(self, lost_after: float = 45.0) -> dict[str, dict]:
        now, books = self.wall(), {}
        for ref, on in self.all().items():
            known = self.view.last_known(ref)
            if known is None:
                continue
            entry = self._primary(ref, on, now, lost_after)
            have, _ = self.vars.get(f"{PRIMARIES_PATH}/{known[0]}")
            old = json.loads((have or {}).get(ref, "{}")).get("ingest")
            ingest = self._ingest(ref, on, known[0], now, old)
            if ingest:
                entry["ingest"] = ingest
            books.setdefault(known[0], {})[ref] = json.dumps(entry, sort_keys=True)
        for home, book in books.items():
            path = f"{PRIMARIES_PATH}/{home}"
            have, idx = self.vars.get(path)
            if have != book:
                self.vars.put(path, book, cas=idx)
        return books

    def _primary(self, ref: str, on: str, now: float, lost_after: float) -> dict:
        # `starting` (feedback AB): the recording should be written and no recorder of its cluster has NAMED it
        # yet — a start, which gets the card's grace. Named and not written, or the cluster silent — a stop,
        # covered at once. It changes when a recording starts and when a recorder first reports it: rarely.
        entry = {"cluster": on, "recording": "", "should": True, "written": False, "starting": False}
        c = self.view.fed.clusters.get(on)
        try:
            if c is None:
                raise Unreachable(on)
            rows = []
            for key in c.objects.list("rec/snapshot/"):
                raw = c.objects.get(key)
                rows += [r for r in (json.loads(raw).get("recordings", []) if raw else []) if str(r.get("cam")) == f"ref:{ref}"]
            names = sorted(str(r.get("name") or r.get("id")) for r in rows)
            running, named = set(), set()
            for key in c.objects.list("rec/heartbeats/"):
                raw = c.objects.get(key)
                hb = json.loads(raw) if raw else None
                if not hb:
                    continue
                named |= {str(st.get("id")) for st in hb.get("status", [])}          # fresh or not: it knew of it
                if now - float(hb.get("ts", 0)) <= lost_after:
                    running |= {str(st.get("id")) for st in hb.get("status", []) if st.get("phase") == "running"}
        except Unreachable:
            return entry
        until_ok = lambda r: float(r.get("until") or 0) == 0 or float(r.get("until") or 0) > now
        should = any(bool(r.get("enabled", True)) and until_ok(r) for r in rows)
        return {**entry, "recording": ",".join(names), "should": should,
                "written": any(n in running for n in names),
                "starting": should and not any(n in named for n in names)}

    # Lesson 16: where the camera pushes, and the token that lets it. The addresses are what the recording
    # cluster's ingest announced (`rec/ingest`). The token is re-issued only when the one the book already
    # holds is past half its life — the book is flash on the camera, and a token minted every pass would
    # rewrite it every pass.
    def _ingest(self, ref: str, on: str, home: str, now: float, old: dict | None) -> dict | None:
        from .ingest import INGEST, audience
        if on in self.star and self.centre:
            on = self.centre                             # a star: the camera pushes to the centre, never to its relay
        c = self.view.fed.clusters.get(on)
        if self.issuer is None or c is None:
            return None
        try:
            raw = c.objects.get(INGEST)
        except Unreachable:
            raw = None
        if raw is None:
            return old                                   # the recording cluster is silent: keep what the camera has
        urls = json.loads(raw)["urls"]
        if old and old.get("urls") == urls and float(old["until"]) - now > self.token_lifetime / 2:
            return old
        token = self.issuer.issue(home, self.token_lifetime, now=now, aud=audience(on), ref=ref)
        return {"urls": urls, "token": token, "until": now + self.token_lifetime}

    # Lesson 16, step 8: the book of polls. A camera that pushes and that nobody records polls nothing, and an
    # ask for it — "turn to preset 3" is the usual one for a PTZ camera kept for live view only — would have
    # nowhere to wait. So it gets the poll home's ingest and a stream token for it, in a book of its own: the
    # book of primaries says who RECORDS a camera, and a backup on its card reads it (М10B Lesson 26); a poll
    # that records nothing must not look like a primary there. The camera polls, is never told to push, and
    # takes its asks. Kept by the same half-life rule, so the book on its flash does not churn.
    def publish_polls(self) -> dict[str, dict]:
        now, books = self.wall(), {}
        for ref, home in self.unrecorded().items():
            on = self._poll_home(home)
            if on is None:
                continue
            have, _ = self.vars.get(f"{POLL_PATH}/{home}")
            old = json.loads((have or {}).get(ref, "null"))
            ingest = self._ingest(ref, on, home, now, old)
            if ingest:
                books.setdefault(home, {})[ref] = json.dumps({**ingest, "cluster": on}, sort_keys=True)
        for home in {h for h in self.unrecorded().values()} | set(books):
            path = f"{POLL_PATH}/{home}"
            have, idx = self.vars.get(path)
            if (have or {}) != books.get(home, {}):
                self.vars.put(path, books.get(home, {}), cas=idx)
        return books

    def _doors(self, ref: str) -> dict | None:
        for (cluster, worker), s in self.view.snapshots.items():
            if any(str(st.get("ref", "")) == ref for st in s.status) and s.doors:
                doors = dict(s.doors)
                if doors.get("push"):                    # Lesson 16: nobody dials it; it pushes to the recording cluster's ingest
                    doors["live_url"] = f"ingest://{self.all().get(ref, '?')}/{ref}"
                    doors.pop("playback_url", None)      # the card is read by asking the camera to upload a range
                return {"cluster": cluster, "worker": worker, **doors, "as_of": s.ts,
                        "reachable": cluster not in self.view.cluster_down_since}
        return None


class NotResolvable(Exception):
    pass


@dataclass
class Source:
    ref: str
    cluster: str
    live_url: str
    playback_url: str | None          # None: a camera that pushes (Lesson 16) — its card is read by asking for an upload
    coverage: dict | None
    age: float
    reachable: bool


# The recorder's side, in the recording cluster: `ref:<serial>` against this cluster's own copy of the book.
# Any other source is this cluster's own and is found as it always was — in its own heartbeats.
def resolve(cluster_vars, source: str, now: float) -> Source | None:
    if not str(source).startswith("ref:"):
        return None
    ref = source[4:]
    items, _ = cluster_vars.get(SOURCES_PATH)
    if not items or ref not in items:
        raise NotResolvable(f"{ref} is not in this cluster's source book: the domain has not asked this cluster "
                            f"to record it, or has never seen it publish a door")
    e = json.loads(items[ref])
    return Source(ref, e["cluster"], e["live_url"], e.get("playback_url"), e.get("coverage"),
                  max(0.0, now - float(e["as_of"])), bool(e.get("reachable", True)))


# What to fetch from the card: what the book says it holds, minus what we hold, bounded as М10B's recorder
# bounds it (not older than our own volume keeps, not fresher than `settle`) — and then checked against
# what the device says NOW. The book is as old as its last carry; a card is a ring, and the oldest hour it
# listed may have been overwritten since. A range the card no longer has is dropped with its reason — a
# retry would ask the same card the same question.
def plan_backfill(src: Source, ours: list[tuple[float, float]], now: float, keep_days: float, settle: float,
                  ask_device) -> tuple[list[tuple[float, float]], list[tuple[tuple[float, float], str]]]:
    if not src.coverage:
        return [], []
    want = (max(float(src.coverage["from"]), now - keep_days * 86400), min(float(src.coverage["to"]), now - settle))
    if want[1] <= want[0]:
        return [], []
    holes = subtract(want, ours)
    if not holes:
        return [], []
    card = ask_device()                                  # {"from", "to"} — the card, now
    fetch, dropped = [], []
    for h in holes:
        lo, hi = max(h[0], float(card["from"])), min(h[1], float(card["to"]))
        if hi > lo:
            fetch.append((lo, hi))
        for gone in subtract(h, [(lo, hi)] if hi > lo else []):
            dropped.append((gone, "no longer on the card"))
    return fetch, dropped
