"""Lesson 14 — alarms from every member.

The operator of a site of cameras wants ONE list of alarms: the door forced at gate 3, the stream gone at
the loading bay, newest first, whichever camera saw it. Inside a cluster the platform has that list already
— every resource's buckets, merged by `MergedIndex`, with `state` and `truncated` said per source (М10A,
М11). Across members there is no cluster to merge in: each camera's events are on its own card.

So the domain merges, the way the directory merges snapshots — from each member, with what it could not
reach said as part of the answer — and adds the one thing a card does not have: a second copy. A camera
that is off, or whose card has died, is exactly the camera whose last alarms matter most.

    one list        each member's alarms, fetched from its door, merged newest first, each line naming its
                    member. A member asked for at most `per_member` lines, and one that had more says so —
                    a storm on one camera must not push every other camera off the page
    a mirror        a neighbouring member keeps a copy of another's CLOSED alarm buckets. Closed, because a
                    closed bucket never changes: copying it needs no coordination, and a copy is either all
                    there or not there. Alarm lines only: a neighbour's flash is not a second card
    pulled          the copy is made by the one who keeps it, reading the other's door — the platform's rule
                    that the one who lacks takes the initiative. Nothing is written into the source
    chosen          which neighbour keeps whose copy is the domain's decision, by reachability, stored per
                    member and carried by its agent (`domain/mirrors`) — stable, so that one camera added to
                    a site of three hundred moves a handful of copies, not all of them
    honest          a member answered from its mirror says so, and says up to WHEN: the alarms of its open
                    bucket were in no copy, and "none since 14:20" must never read as "none"
    two sources     a silent member is answered from BOTH what the domain already has — the page of its last
                    report, one agent pass behind — and its neighbour's copy, which goes on while the camera
                    works and only its road to the domain is gone. The union, and the later of the two "up to"s
                    (feedback AR)
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time

from w2cplatform.events import ALARM, EventLog, buckets_under, read_bucket, subsystems_under

from .agent import MIRRORS_PATH
from .federation import Unreachable

BUCKET = 600


class Card:
    """A member's events, on its card: М10's buckets, `vms/<unit>/e<epoch>/<start>Z.events.jsonl`, and a
    `mirror/<member>/…` tree beside them for the copies this member keeps of others."""

    def __init__(self, root: str | None = None, unit: str = "1", bucket: int = BUCKET):
        self.root, self.unit, self.bucket = root or tempfile.mkdtemp(prefix="card-"), unit, bucket

    def observe(self, epoch: int, t: float, kind: str, alarm: bool = False, unit: str | None = None, **fields) -> None:
        EventLog(self.root, "vms", unit or self.unit, epoch, self.bucket).append(t, kind, cls=ALARM if alarm else "observation", **fields)

    # Which units have buckets here — read from the card itself, never from a list published earlier (feedback
    # AR). A door published at the first report, often before the first event, would name no unit; and the
    # camera that lost its road to the domain, the very one being copied, could not correct it.
    def _buckets(self, root: str):
        for unit in subsystems_under(root).get("vms", []):
            yield from buckets_under(root, "vms", unit, self.bucket)

    def _alarms_in(self, root: str, since: float, until: float) -> list[dict]:
        out = []
        for b in self._buckets(root):
            if b.end <= since or b.start >= until:
                continue
            out += [e for e in read_bucket(os.path.join(root, b.path))
                    if e.get("class") == ALARM and since <= float(e["t"]) < until]
        return out

    def alarms(self, since: float, until: float, limit: int) -> dict:
        evs = sorted(self._alarms_in(self.root, since, until), key=lambda e: -float(e["t"]))
        return {"events": evs[:limit], "truncated": len(evs) > limit}

    def closed_alarm_buckets(self, now: float) -> dict[str, list[dict]]:
        """{relative path: its alarm lines} for every bucket that has closed and holds an alarm."""
        out = {}
        for b in self._buckets(self.root):
            if b.end > now:
                continue                                 # still being written: in no copy, by design
            lines = [e for e in read_bucket(os.path.join(self.root, b.path)) if e.get("class") == ALARM]
            if lines:
                out[b.path] = lines
        return out

    def closed_until(self, now: float) -> float:
        """Where this card's closed buckets end: everything before it is in `closed_alarm_buckets(now)`, alarms
        or none. A copy taken at `now` therefore knows the source up to here — even a quiet source, and even
        one with no bucket at all in the interval, which is what copying empty buckets could not say."""
        return (now // self.bucket) * self.bucket

    # -- the copies this member keeps of others --------------------------------------------------------
    def _mirror_root(self, of: str) -> str:
        return os.path.join(self.root, "mirror", of)

    def keep_copy(self, of: str, path: str, lines: list[dict]) -> bool:
        dst = os.path.join(self._mirror_root(of), path)
        if os.path.exists(dst):
            return False                                 # closed means immutable: what is here is all of it
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".part"
        with open(tmp, "w") as f:
            f.write("".join(json.dumps(e) + "\n" for e in lines))
        os.replace(tmp, dst)                             # all there or not there
        return True

    # How far the copy knows the source: the boundary the source named at the last pull that succeeded, kept
    # beside the copy (`.known_until`). Only ever forward. Without it a quiet camera's copy would stop "knowing"
    # at its last alarm, and the list would say "none since 03:10" of a camera looked at a minute ago.
    def _known_path(self, of: str) -> str:
        return os.path.join(self._mirror_root(of), ".known_until")

    def looked(self, of: str, until: float) -> None:
        path = self._known_path(of)
        if until <= (self._known(of) or 0):
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".part", "w") as f:
            f.write(str(until))
        os.replace(path + ".part", path)

    def _known(self, of: str) -> float | None:
        try:
            with open(self._known_path(of)) as f:
                return float(f.read())
        except (OSError, ValueError):
            return None

    def mirrored(self, of: str, since: float, until: float, limit: int) -> dict:
        root = self._mirror_root(of)
        evs = sorted(self._alarms_in(root, since, until), key=lambda e: -float(e["t"])) if os.path.isdir(root) else []
        ends = [b.end for b in self._buckets(root)] if os.path.isdir(root) else []
        known = [k for k in (max(ends) if ends else None, self._known(of)) if k is not None]
        return {"events": evs[:limit], "truncated": len(evs) > limit, "known_until": max(known) if known else None}


class EventDoor:
    """A member's events as the domain and its neighbours reach them: through its door, closed when it is
    off."""

    def __init__(self, member, card: Card):
        self.member, self.card = member, card

    def _open(self) -> Card:
        if not self.member.door_open:
            raise Unreachable(f"{self.member.name} did not answer")
        return self.card

    def alarms(self, since, until, limit):
        return self._open().alarms(since, until, limit)

    def closed_alarm_buckets(self, now):
        return self._open().closed_alarm_buckets(now)

    def closed_until(self, now):
        return self._open().closed_until(now)

    def mirrored(self, of, since, until, limit):
        return self._open().mirrored(of, since, until, limit)


# The alarm pages a member reports (`domain/uplink.py`): its newest alarms of the last `window` seconds, and
# the same for every neighbour it keeps a copy of. The domain answers from these and never opens the member's
# door. What is older than the page is not in it, and the answer says so (`truncated`); an operator asking
# about last week asks the member's own console, on the site.
WINDOW = 86400.0


def pages(card: Card, keeps, now: float, per_member: int = 100, window: float = WINDOW) -> dict[str, bytes]:
    since = now - window
    out = {"alarms": json.dumps({"from": since, "to": now, **card.alarms(since, now + 1, per_member)}).encode()}
    for of in sorted(keeps or {}):
        out[f"mirror/{of}"] = json.dumps({"from": since, "to": now, **card.mirrored(of, since, now + 1, per_member)}).encode()
    return out


class ReportedDoor:
    """A member's alarms as the domain sees them: from the pages in its last report. Unreachable when the
    report is too old — and then the domain turns to the pages its neighbours report, as it did to their doors,
    and to `last`: the page of the silent member's last report, which it still has."""

    def __init__(self, member: str, domain_objects, lost_after: float = 45.0, wall=time.time):
        self.member, self.store, self.lost_after, self.wall = member, domain_objects, lost_after, wall

    def _page(self, name: str) -> dict:
        from .uplink import page
        return page(self.member, name, self.store, self.lost_after, self.wall) or {"from": self.wall(), "events": [], "truncated": False}

    @staticmethod
    def _cut(p: dict, since: float, until: float, limit: int) -> dict:
        evs = [e for e in p.get("events", []) if since <= float(e["t"]) < until]
        return {"events": evs[:limit], "truncated": bool(p.get("truncated")) or len(evs) > limit or since < float(p.get("from", since))}

    def alarms(self, since, until, limit):
        return self._cut(self._page("alarms"), since, until, limit)

    def mirrored(self, of, since, until, limit):
        p = self._page(f"mirror/{of}")
        return {**self._cut(p, since, until, limit), "known_until": p.get("known_until")}

    # The last report of a member that has gone silent — one agent pass behind the camera, where a copy is up to
    # a bucket behind. The door forced ninety seconds before the camera went dark is in this page and in no
    # copy. `known_until` is when the report was made, on the domain's clock. None: it never reported.
    def last(self, since, until, limit) -> dict | None:
        from .uplink import page
        try:
            p = page(self.member, "alarms", self.store, self.lost_after, self.wall, stale_ok=True)
        except Unreachable:
            return None                                  # never reported: there is no last page
        return None if p is None else {**self._cut(p, since, until, limit), "known_until": p.get("to")}


def _same(e: dict) -> str:
    """One alarm, whichever source carried it: the line itself, without what the list adds."""
    return json.dumps({k: v for k, v in e.items() if k not in ("member", "from_mirror_on")}, sort_keys=True)


def _score(a: str, b: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{a}|{b}".encode()).digest()[:8], "big")


class MirrorPlan:
    """Who keeps a copy of whom. Rendezvous hashing: each member ranks the others by a hash of the pair and
    takes the top `copies`, among the members that share a network with it when there are enough of them.
    Adding a member changes a pair only where the newcomer outranks it — about `copies` in N of them."""

    def __init__(self, domain_vars, copies: int = 1):
        self.vars, self.copies = domain_vars, copies

    def choose(self, members: dict[str, frozenset]) -> dict[str, list[str]]:
        """{member: [the members that keep its copies]}"""
        out = {}
        for a, nets in members.items():
            others = [b for b in members if b != a]
            near = [b for b in others if nets & members[b]]
            pool = near if len(near) >= self.copies else others
            out[a] = sorted(pool, key=lambda b: -_score(a, b))[: self.copies]
        return out

    def publish(self, fed) -> dict[str, list[str]]:
        members = {n: c.networks() for n, c in fed.clusters.items() if not c.is_domain_cluster}
        holders = self.choose(members)
        keeps: dict[str, dict] = {b: {} for b in members}
        for a, bs in holders.items():
            for b in bs:
                keeps[b][a] = "1"
        for b, items in keeps.items():
            path = f"{MIRRORS_PATH}/{b}"
            have, idx = self.vars.get(path)
            if have != items:
                self.vars.put(path, items, cas=idx)
        return holders

    def holders(self, of: str) -> list[str]:
        out = []
        for path in self.vars.list(f"{MIRRORS_PATH}/"):
            items, _ = self.vars.get(path)
            if items and of in items:
                out.append(path.rsplit("/", 1)[1])
        return sorted(out)


# One pass of a member's mirror job: for each member its agent says it keeps a copy of, pull the closed
# alarm buckets it does not have yet. A source that does not answer is simply not copied this pass.
def mirror_once(me: Card, my_vars, doors, now: float) -> int:
    keeps, _ = my_vars.get(MIRRORS_PATH)
    copied = 0
    for of in sorted(keeps or {}):
        try:
            door = doors(of)
            closed, until = door.closed_alarm_buckets(now), door.closed_until(now)
        except Unreachable:
            continue
        for path, lines in closed.items():
            copied += me.keep_copy(of, path, lines)
        me.looked(of, until)                             # all of it is here: the copy knows the source up to `until`
    return copied


class DomainAlarms:
    """The one list. `doors(member)` is that member's `EventDoor`."""

    def __init__(self, fed, doors, plan: MirrorPlan, wall=time.time, per_member: int = 100):
        self.fed, self.doors, self.plan, self.wall, self.per_member = fed, doors, plan, wall, per_member

    def list(self, since: float, until: float | None = None) -> dict:
        until = self.wall() if until is None else until
        events, members = [], {}
        for name, c in self.fed.clusters.items():
            if c.is_domain_cluster:
                continue
            door = self.doors(name)
            try:
                got = door.alarms(since, until, self.per_member)
                members[name] = {"state": "ok", "truncated": got["truncated"]}
                events += [{**e, "member": name} for e in got["events"]]
                continue
            except Unreachable:
                pass
            # Silent. Two sources, and neither is enough alone (feedback AR): its last report is one pass behind
            # the camera and stops when the camera's road to the domain does; the copy is up to a bucket behind
            # and goes on while the camera works. The union, and the later of the two "up to"s.
            last = door.last(since, until, self.per_member) if hasattr(door, "last") else None
            copy, via = None, None
            for b in self.plan.holders(name):
                try:
                    copy, via = self.doors(b).mirrored(name, since, until, self.per_member), b
                    break
                except Unreachable:
                    continue
            if last is None and copy is None:
                members[name] = {"state": "unreachable", "truncated": False}
                continue
            seen = set()
            for e in (last or {}).get("events", []):
                seen.add(_same(e))
                events.append({**e, "member": name})
            for e in (copy or {}).get("events", []):
                if _same(e) not in seen:
                    events.append({**e, "member": name, "from_mirror_on": via})
            knowns = [k for k in ((last or {}).get("known_until"), (copy or {}).get("known_until")) if k is not None]
            members[name] = {"state": "mirror" if copy is not None else "last_report",
                             **({"via": via} if copy is not None else {}),
                             "last_report_until": (last or {}).get("known_until"),
                             "known_until": max(knowns) if knowns else None,
                             "truncated": bool((last or {}).get("truncated")) or bool((copy or {}).get("truncated"))}
        events.sort(key=lambda e: -float(e["t"]))
        return {"events": events, "members": members, "complete": all(m["state"] == "ok" for m in members.values()),
                "sentence": self._sentence(members)}

    @staticmethod
    def _sentence(members: dict) -> str:
        parts = []
        for name, m in sorted(members.items()):
            if m["state"] in ("mirror", "last_report"):
                when = time.strftime("%H:%M", time.gmtime(m["known_until"])) if m["known_until"] else "never"
                src = " and ".join(x for x in ("its last report" if m.get("last_report_until") is not None else "",
                                               f"the copy on {m['via']}" if m.get("via") else "") if x)
                parts.append(f"{name} silent — its alarms from {src}, known up to {when} UTC; none known since")
            elif m["state"] == "unreachable":
                parts.append(f"{name} off, and no copy of its alarms could be reached")   # nor any report of its own
            if m.get("truncated"):
                parts.append(f"{name} had more alarms than one page holds; showing its newest")
        return "; ".join(parts) if parts else "every member answered"
