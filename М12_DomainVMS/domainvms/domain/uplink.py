"""Every connection between a member and the domain is opened by the member.

A camera may never be reachable from the domain — behind a NAT, in a segment nothing routes into, on a
cellular link that only dials out — while the domain is, now and then, reachable from the camera. So the
domain does not go to members at all. It reads its OWN cluster's store, and what it knows of a member is
what that member's agent left there; what it wants of a member is a row the agent takes home (Lessons 4, 9,
12–15 — that half was always the agent's). The agent already opens one connection to the domain on every
pass; this module is the other half of that same pass.

    up      the member's agent writes a REPORT into the domain cluster's object store, under a prefix of
            its own — `domain/members/<member>/` — one writer per prefix, as everywhere: copies of the
            objects the domain reads (its workers' heartbeats and snapshot shards, its recorders' too),
            copies of the rows the domain reads (the outcomes of kept edits, its copy of the shared
            settings' pointer, the host record it follows, its backup pointer, its epochs), the pages it
            is asked for (its newest alarms, the ones it keeps for a neighbour) — and, LAST, `reported`:
            the time of this report. Only what changed is rewritten
    read    `member_copy()` gives the domain a `Cluster` over that prefix, with the same reads a member's
            own stores have. So the directory, the read view, the books, the delivery report and the edit
            collector read a member exactly as before and do not know which way the bytes came
    silence a member's silence is the AGE OF ITS LAST REPORT — on the DOMAIN's clock. Older than
            `lost_after`, its copy answers Unreachable, as a cluster the domain could not reach always did:
            the last known rows are kept, named as such, and the answer is incomplete — Lesson 1's rule,
            unchanged in meaning
    clocks  a member's clock is not the domain's, a camera's least of all. So the domain does not believe
            the time a report carries: it notes, by its own clock, WHEN it first saw each report (each has
            a sequence number), and that is the report's age. The times inside the report — every `ts` in a
            heartbeat or a snapshot shard — are moved onto the domain's clock by the difference between
            "the member stamped it" and "the domain saw it". A camera fifteen minutes slow is otherwise
            fifteen minutes stale for ever, and one fifteen minutes fast is never stale at all. The
            difference is kept (`offset`) and shown with the member

What moves: the cost. A domain pass reads one store instead of N members, and a member that cannot be
reached costs nothing to ask about. Each member's report is writes into the domain cluster instead — at
three hundred members, measured in Lesson 11.

The one exception, and it is named, not hidden: re-hosting the domain on another camera (Lesson 15) needs
the new host to find the newest backup, and it reads its PEERS for it — member to member, on the site. The
domain in steady state never opens a connection to anyone.
"""
from __future__ import annotations

import json
import time

from .federation import Cluster, Unreachable

UPLINK = "domain/members"
REPORTED = "reported"
# What the domain reads of a member, and nothing more. Objects: what a cluster publishes (М10–М11).
OBJECTS = ("vms/heartbeats/", "vms/snapshot/", "rec/heartbeats/", "rec/snapshot/")


def _rows() -> tuple[str, ...]:
    """The rows the domain reads of a member: named where they are defined, collected here (imported late —
    those modules import the agent, and the agent imports this)."""
    from .pending import OUTCOMES_PATH
    from .shared import POINTER, REFUSED
    from .term import BACKUP, HOST
    return (OUTCOMES_PATH, POINTER, REFUSED, HOST, BACKUP, "vms/epoch/")


def base(member: str) -> str:
    return f"{UPLINK}/{member}/"


class NotPublished(Exception):
    """The member has published nothing yet — a report now would say "I have no cameras", completely."""


# One report. `member_vars` and `member_objects` are the member's OWN stores, read locally by its agent;
# `domain_objects` is the domain cluster's object store, the one connection. `pages` is what the member is
# asked to show beyond its rows and objects — Lesson 14's alarm pages — as {name: bytes}.
#
# Lesson 10's ordering rule, on the report: a member that has not published yet does not report. Its report
# would be a COMPLETE answer with no cameras in it, which the domain must believe; silence is the truthful
# thing until the first publish.
def report(member: str, member_vars, member_objects, domain_objects, now: float, pages: dict | None = None) -> int:
    want: dict[str, bytes] = {}
    for prefix in OBJECTS:
        for key in member_objects.list(prefix):
            raw = member_objects.get(key)
            if raw:
                want["o/" + key] = raw
    if not any(k.startswith("o/vms/snapshot/") for k in want):
        raise NotPublished(f"{member} has not published yet; it reports after its first publish")
    for row in _rows():
        for key in (member_vars.list(row) if row.endswith("/") else [row]):
            items, idx = member_vars.get(key)
            if items is not None:
                want["v/" + key] = json.dumps({"items": items, "idx": idx}, sort_keys=True).encode()
    for name, raw in (pages or {}).items():
        want["p/" + name] = raw
    b = base(member)
    written = 0
    for k, raw in want.items():
        if domain_objects.get(b + k) != raw:                       # only what changed is rewritten
            domain_objects.put(b + k, raw)
            written += 1
    keep = {b + k for k in want} | {b + REPORTED}
    for full in domain_objects.list(b):
        if full not in keep:
            domain_objects.delete(full)                            # gone from the member: gone from its report
    prev = domain_objects.get(b + REPORTED)
    seq = (json.loads(prev).get("seq", 0) if prev else 0) + 1
    domain_objects.put(b + REPORTED, json.dumps({"ts": now, "seq": seq, "items": len(want)}).encode())   # last: the report is whole
    return written + 1


def reported_at(member: str, domain_objects) -> float | None:
    """The time the member stamped its last report with — ITS clock. For how old the report is, ask the copy."""
    raw = domain_objects.get(base(member) + REPORTED)
    return float(json.loads(raw)["ts"]) if raw else None


class _Fresh:
    """How old a member's report is, by the domain's clock: when the domain first saw its sequence number."""

    def __init__(self, member: str, store, lost_after: float, wall):
        self.member, self.store, self.lost_after, self.wall = member, store, lost_after, wall
        self.base = base(member)
        self.seq, self.seen_at, self.offset = None, None, 0.0

    def check(self) -> None:
        raw = self.store.get(self.base + REPORTED)
        if not raw:
            raise Unreachable(f"{self.member} has never reported to the domain")
        mark, now = json.loads(raw), self.wall()
        if mark.get("seq") != self.seq:                              # a new report: seen now, by our clock
            self.seq, self.seen_at = mark.get("seq"), now
            self.offset = now - float(mark["ts"])                    # our clock minus theirs, as of this report
        age = now - self.seen_at
        if age > self.lost_after:
            raise Unreachable(f"{self.member} has not reported for {age:.0f} s")

    def domain_time(self, ts) -> float:
        return float(ts) + self.offset


class _CopyObjects:
    """A member's objects, as its last report left them. Read only."""

    def __init__(self, fresh: _Fresh):
        self.f = fresh

    def get(self, key: str) -> bytes | None:
        self.f.check()
        raw = self.f.store.get(self.f.base + "o/" + key)
        if raw and self.f.offset:
            try:                                                     # the member's `ts`, on the domain's clock
                d = json.loads(raw)
                if isinstance(d, dict) and "ts" in d:
                    d["ts"] = self.f.domain_time(d["ts"])
                    raw = json.dumps(d).encode()
            except ValueError:
                pass
        return raw

    def list(self, prefix: str) -> list[str]:
        self.f.check()
        n = len(self.f.base) + 2
        return [k[n:] for k in self.f.store.list(self.f.base + "o/" + prefix)]

    def put(self, key, data):
        raise PermissionError("the domain writes nothing into a member's report: its agent does")

    def delete(self, key):
        raise PermissionError("the domain writes nothing into a member's report: its agent does")


class _CopyVars:
    """A member's rows, as its last report left them: `(items, index)` as the member's own store answered."""

    def __init__(self, fresh: _Fresh):
        self.f = fresh

    def get(self, path: str):
        self.f.check()
        raw = self.f.store.get(self.f.base + "v/" + path)
        if not raw:
            return None, 0
        d = json.loads(raw)
        return d["items"], d["idx"]

    def list(self, prefix: str) -> list[str]:
        self.f.check()
        n = len(self.f.base) + 2
        return [k[n:] for k in self.f.store.list(self.f.base + "v/" + prefix)]

    def put(self, path, items, cas=None):
        raise PermissionError("the domain writes nothing into a member: what it wants there is a row its agent takes home")


def member_copy(member: str, domain_objects, reaches=(), lost_after: float = 45.0, wall=time.time) -> Cluster:
    """The domain's handle on a member it never reaches: a `Cluster` over that member's last report. Its
    `objects.f.offset` is how far the member's clock is from the domain's, as of the last report."""
    f = _Fresh(member, domain_objects, lost_after, wall)
    return Cluster(member, _CopyVars(f), _CopyObjects(f), frozenset(reaches))


def offset_of(copy: Cluster) -> float:
    """The domain's clock minus the member's, as of its last report seen — for the member's card."""
    return copy.objects.f.offset


_FRESH: dict[tuple[int, str], _Fresh] = {}


def page(member: str, name: str, domain_objects, lost_after: float = 45.0, wall=time.time) -> dict | None:
    """One page a member reported (Lesson 14's alarms), with its times on the domain's clock, or Unreachable
    if its report is too old — by the domain's clock, remembered per store and member across calls."""
    f = _FRESH.setdefault((id(domain_objects), member), _Fresh(member, domain_objects, lost_after, wall))
    f.lost_after, f.wall = lost_after, wall
    f.check()
    raw = domain_objects.get(base(member) + "p/" + name)
    if not raw:
        return None
    p = json.loads(raw)
    for k in ("from", "to", "known_until"):
        if p.get(k) is not None:
            p[k] = f.domain_time(p[k])
    for e in p.get("events", []):
        e["t"] = f.domain_time(e["t"])
    return p
