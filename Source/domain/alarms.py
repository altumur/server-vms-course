"""Lesson 14 — alarms from every member.

The operator of a site of cameras wants ONE list of alarms: the door forced at gate 3, the stream gone at
the loading bay, newest first, whichever camera saw it. Inside a cluster the platform has that list already
— every resource's buckets, merged by `MergedIndex`, with `state` and `truncated` said per source (М10A,
М11). Across members there is no cluster to merge in: each camera's events are on its own card.

So the domain merges, the way the directory merges snapshots — from each member's report, with what it could
not hear said as part of the answer — and it has to be honest about the camera that went dark, because that
is exactly the camera whose last alarm matters most: the camera at the gate goes dark thirty seconds after it
reported the door forced.

    one list        each member's alarms, from the page its agent leaves in its report, merged newest first,
                    each line naming its member. A page holds at most `per_member` lines, and a member that had
                    more says so — a storm on one camera must not push every other camera off the page
    at once         an alarm does not wait for the agent's next pass: the card wakes the agent and the report goes
                    now (`Card.on_alarm`, `DomainAgent.report_now`). Half a minute is long enough for the camera
                    that saw the door forced to be broken before its report left
    the last report a silent member is answered from the page of its last report — kept by the domain, "known up
                    to" the moment it was made
    silence         a member that stopped reporting is itself an ALARM on the list, not only a state: "silent
                    since 14:21" — and the camera's poll to an ingest (Lesson 16), kept by another process than
                    its agent, tells a camera that is alive but not reporting from one that is gone
    history         the domain keeps what it read, a week of it (`AlarmHistory`): the page is a day and a hundred
                    lines, and a camera whose card died takes the rest with it

What is NOT here any more: copies of a member's alarms on its neighbours' cards (until 29 September). They
copied only closed buckets — ten minutes behind, so the last alarm before a camera went dark was in none of
them — they worked only between cameras with open doors on one network, and they cost a plan in the domain, a
book every agent carried and the neighbours' flash. What they still bought once the last report was kept
(feedback AR) — the alarms of a camera alive but unable to report, ten minutes late — the witness and the
silence alarm now say at once (the note on alarm mirrors, 28 September).
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time

from w2cplatform.events import ALARM, EventLog, alarm_tree, buckets_under, read_bucket, subsystems_under

from w2cplatform.rows import PARSE_ERRORS, finite

from .federation import Unreachable, published

BUCKET = 600
POLLED = "rec/polled"                 # an ingest's word, `rec/polled/<ingest>`: when each camera last polled it
HISTORY = "domain/alarm-history"      # in the domain's object store: <member>, a rolling week of what it read


class Card:
    """A member's events, on its card: М10's buckets, `vms/<unit>/e<epoch>/<start>Z.events.jsonl`.
    `on_alarm()` is called when an alarm is written — the camera's agent, woken to report now."""

    def __init__(self, root: str | None = None, unit: str = "1", bucket: int = BUCKET, on_alarm=None):
        self.root, self.unit, self.bucket = root or tempfile.mkdtemp(prefix="card-"), unit, bucket
        self.on_alarm = on_alarm

    def observe(self, epoch: int, t: float, kind: str, alarm: bool = False, unit: str | None = None, **fields) -> None:
        EventLog(self.root, "vms", unit or self.unit, epoch, self.bucket).append(t, kind, cls=ALARM if alarm else "observation", **fields)
        if alarm and self.on_alarm is not None:
            self.on_alarm()                          # the line is on the card: now it has to leave it

    # Alarms lie in a tree of their own (`vms.alarms/…`, М10A Lesson 12); a bucket written before they did
    # holds both classes in `vms/…`. Both are read, and the class is what picks a line.
    def _buckets(self, root: str):
        trees = subsystems_under(root)
        for tree in ("vms", alarm_tree("vms")):
            for unit in trees.get(tree, []):
                yield from buckets_under(root, tree, unit, self.bucket)

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

    def waiting(self, since: float) -> bool:
        """An alarm on the card newer than `since` — the last page the agent reported. What an agent in ANOTHER
        process asks, once a second, instead of being woken (`DomainAgent(alarm_waiting=...)`)."""
        return any(float(e["t"]) > since for e in self._alarms_in(self.root, since, float("inf")))


# The alarm page a member reports (`domain/uplink.py`): its newest alarms of the last `window` seconds. The
# domain answers from it and never opens the member's door.
WINDOW = 86400.0


def pages(card: Card, now: float, per_member: int = 100, window: float = WINDOW) -> dict[str, bytes]:
    since = now - window
    return {"alarms": json.dumps({"from": since, "to": now, **card.alarms(since, now + 1, per_member)}).encode()}


class ReportedDoor:
    """A member's alarms as the domain sees them: from the page in its last report. Unreachable when the
    report is too old — and then `last` is the page of the silent member's last report, which it still has."""

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

    # The last report of a member that has gone silent — one agent pass behind the camera, less when the alarm
    # woke the agent. `known_until` is when the report was made, on the domain's clock. None: it never reported.
    def last(self, since, until, limit) -> dict | None:
        from .uplink import page
        try:
            p = page(self.member, "alarms", self.store, self.lost_after, self.wall, stale_ok=True)
        except Unreachable:
            return None
        return None if p is None else {**self._cut(p, since, until, limit), "known_until": p.get("to")}


def _same(e: dict) -> str:
    """One alarm, whichever source carried it: the line itself, without what the list adds — and by its time on
    the SOURCE's clock when the page carries it (`t_src`): the time on ours moves from report to report."""
    d = {k: v for k, v in e.items() if k not in ("member", "from_history")}
    if "t_src" in d:
        d.pop("t")
    return json.dumps(d, sort_keys=True)


def serial_of(member: str) -> str:
    """The camera a member cluster is: `cam-<serial>` (Lesson 10) — the `ref` its poll is known by."""
    return member[4:] if member.startswith("cam-") else member


class AlarmHistory:
    """What the domain read of each member's alarms, kept in its own object store for `days`. The page a member
    reports is a day and a hundred lines; a camera whose card died, or which was stolen, takes everything older
    with it. The domain has read it all already — so it keeps it, instead of asking a neighbour to.

    One object per member, a rolling week: what is older than `days` falls off when the object is written again.
    Nothing is deleted, because the store under the domain may not delete at all (М11's has put, get and list).

    And at most `max_lines` of them, the newest (feedback BA). A contact that bounces once a second for a week is
    six hundred thousand lines — fifty megabytes for one member, read whole by every answer of the list and carried
    in every backup of the holder (Lesson 15). A storm pushes its own oldest lines out, and the object says from
    when it holds the member whole (`cut_before`): what a page still shows from before it is not taken back — it
    would push out newer lines — and the list says the week is incomplete there. A week, then, is the newest week."""

    MAX_LINES = 2000                             # twenty pages; ~160 KB a member, whatever the storm

    def __init__(self, domain_objects, days: int = 7, wall=time.time, max_lines: int = MAX_LINES):
        self.store, self.days, self.wall, self.max_lines = domain_objects, days, wall, max_lines
        self._lock = threading.Lock()

    def _key(self, member: str) -> str:
        return f"{HISTORY}/{member}"

    def _read(self, member: str) -> dict:
        raw = self.store.get(self._key(member))
        doc = json.loads(raw) if raw else []
        return {"events": doc, "cut_before": None} if isinstance(doc, list) else doc    # the first form: a list

    def _write(self, member: str, events: list[dict], cut_before: float | None) -> None:
        self.store.put(self._key(member), json.dumps({"events": sorted(events, key=lambda e: float(e["t"])),
                                                      "cut_before": cut_before}).encode())

    def keep(self, member: str, events: list[dict]) -> int:
        """Add what is not kept yet, and let go what is older than the week or past the ceiling; returns how many
        were new."""
        horizon = self.wall() - self.days * 86400
        with self._lock:
            doc = self._read(member)
            have, cut = doc["events"], doc.get("cut_before")
            seen = {_same(e) for e in have}
            add = [{k: v for k, v in e.items() if k != "member"} for e in events
                   if float(e["t"]) >= horizon and (cut is None or float(e["t"]) >= cut) and _same(e) not in seen]
            kept = sorted([e for e in have if float(e["t"]) >= horizon] + add, key=lambda e: float(e["t"]))
            if len(kept) > self.max_lines:
                kept = kept[-self.max_lines:]
                cut = max(cut or 0.0, float(kept[0]["t"]))
            if add or len(kept) != len(have) or cut != doc.get("cut_before"):
                self._write(member, kept, cut)
        return len(add)

    def read(self, member: str, since: float, until: float) -> list[dict]:
        horizon = self.wall() - self.days * 86400
        return [e for e in self._read(member)["events"] if since <= float(e["t"]) < until and float(e["t"]) >= horizon]

    def cut_before(self, member: str) -> float | None:
        """From when the history holds this member whole — None if a storm never pushed any of its lines out."""
        return self._read(member).get("cut_before")


class DomainAlarms:
    """The one list. `doors(member)` is that member's `ReportedDoor`; `history` is the domain's `AlarmHistory`."""

    def __init__(self, fed, doors, wall=time.time, per_member: int = 100, history: AlarmHistory | None = None,
                 lost_after: float = 45.0, ref_of=serial_of):
        self.fed, self.doors, self.wall, self.per_member = fed, doors, wall, per_member
        self.history, self.lost_after, self.ref_of = history, lost_after, ref_of

    # When a camera last polled an ingest, as the ingests say (`rec/polled`, in their clusters' stores — read
    # directly, or carried in a relay's or a camera's report). The poll is kept by another process than the
    # agent, so a camera whose agent died still polls — the domain's one witness that it is alive.
    def alive_at(self, ref: str) -> tuple[float, str] | None:
        best = None
        for name, c in self.fed.clusters.items():
            try:
                raws = [(k, c.objects.get(k)) for k in c.objects.list(POLLED + "/")]   # one per ingest of the cluster
            except Unreachable:
                continue
            for key, raw in raws:
                # Through the members' one reader (the review's eighth pass, minor): one ingest's object that does not
                # parse said nothing, and raised out of the domain's list of alarms for every member.
                d = published(name, key, raw, lambda d: (finite(d["ts"]), dict(d.get("cameras") or {})))
                if d is None:
                    continue
                age = (d.get("cameras") or {}).get(str(ref))
                if age is None:
                    continue
                try:
                    at = float(d["ts"]) - finite(age)            # `ts` on the domain's clock: the copy shifts it
                except PARSE_ERRORS:
                    continue
                if best is None or at > best[0]:
                    best = (at, d.get("cluster", name))
        return best

    def list(self, since: float, until: float | None = None) -> dict:
        until = self.wall() if until is None else until
        events, members = [], {}
        for name, c in self.fed.clusters.items():
            if c.is_domain_holder:
                continue
            door = self.doors(name)
            try:
                got = door.alarms(since, until, self.per_member)
                if self.history is not None:          # what it reads, it keeps: the whole page, not the window
                    self.history.keep(name, door.alarms(self.wall() - WINDOW, self.wall() + 1, self.per_member)["events"])
                # …and only then reads the history back: kept first, so this answer knows what the keeping pushed
                # out (feedback BA — the other order answered from a history about to lose its oldest lines).
                kept = self.history.read(name, since, until) if self.history is not None else []
                members[name] = {"state": "ok", "truncated": got["truncated"], **self._history_cut(name, since)}
                events += self._union(name, got["events"], kept)
                continue
            except Unreachable:
                pass
            kept = self.history.read(name, since, until) if self.history is not None else []
            last = door.last(since, until, self.per_member) if hasattr(door, "last") else None
            if last is None and not kept:
                members[name] = {"state": "unreachable", "truncated": False}
                continue
            reported = (last or {}).get("known_until")
            events += self._union(name, (last or {}).get("events", []), kept)
            m = {"state": "last_report", "known_until": reported, "truncated": bool((last or {}).get("truncated")),
                 **self._history_cut(name, since)}
            if reported is not None:
                silent_since = float(reported) + self.lost_after
                alive = self.alive_at(self.ref_of(name))
                # Silence is news, and of two kinds the operator acts on differently: a camera still polling its
                # ingest is alive and not reporting — its agent, its certificate, its road to the domain; one that
                # polls nothing either is gone — broken, stolen, unpowered.
                kind = "not_reporting" if alive is not None and alive[0] > float(reported) else "silent"
                if kind == "not_reporting":
                    m.update(alive_at=alive[0], alive_via=alive[1])
                events.append({"t": silent_since, "kind": kind, "class": ALARM, "member": name, "subsystem": "domain",
                               "last_report": reported, "ongoing": True,
                               **({"alive_at": alive[0], "alive_via": alive[1]} if kind == "not_reporting" else {})})
                m["silent_since"] = silent_since
            members[name] = m
        events.sort(key=lambda e: -float(e["t"]))
        return {"events": events, "members": members, "complete": all(m["state"] == "ok" for m in members.values()),
                "sentence": self._sentence(members)}

    def _history_cut(self, name: str, since: float) -> dict:
        cut = self.history.cut_before(name) if self.history is not None else None
        return {"history_cut_before": cut} if cut is not None and since < cut else {}

    @staticmethod
    def _union(name: str, fresh: list[dict], kept: list[dict]) -> list[dict]:
        seen, out = set(), []
        for e in fresh:
            seen.add(_same(e))
            out.append({**e, "member": name})
        for e in kept:
            if _same(e) not in seen:
                out.append({**e, "member": name, "from_history": True})
        return out

    @staticmethod
    def _sentence(members: dict) -> str:
        hm = lambda t: time.strftime("%H:%M", time.gmtime(t)) if t else "never"
        parts = []
        for name, m in sorted(members.items()):
            if m["state"] == "last_report":
                said = (f"{name} silent since {hm(m.get('silent_since'))} — its alarms from its last report, known up "
                        f"to {hm(m['known_until'])} UTC; none known since")
                if m.get("alive_at"):
                    said += f" — but it polled {m['alive_via']} at {hm(m['alive_at'])}: alive, and not reporting to the domain"
                parts.append(said)
            elif m["state"] == "unreachable":
                parts.append(f"{name} has never reported to the domain")
            if m.get("truncated"):
                parts.append(f"{name} had more alarms than one page holds; showing its newest")
            if m.get("history_cut_before"):
                parts.append(f"{name} had an alarm storm: the domain keeps only its newest alarms, and what came before "
                             f"{hm(m['history_cut_before'])} UTC is not known in full")
        return "; ".join(parts) if parts else "every member answered"
