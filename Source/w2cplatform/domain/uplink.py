"""Every connection between a member and the domain is opened by the member.

A member may never be reachable from the domain — behind a NAT, in a segment nothing routes into, on a
cellular link that only dials out — while the domain is, now and then, reachable from the member. So the
domain does not go to members at all. It reads its OWN cluster's store, and what it knows of a member is
what that member's agent left there; what it wants of a member is a row the agent takes home (Lessons 4, 9,
12–15 — that half was always the agent's). The agent already opens one connection to the domain on every
pass; this module is the other half of that same pass.

    up      the member's agent sends a REPORT to the domain holder's door — `POST /api/member/<member>`, the same
            door it carries through, so the report follows the holder as the rows do (the three-site
            scenario, N5; ADR-0066) — and the door keeps it in the holder's object store under a prefix of the
            member's own — `domain/members/<member>/` — one writer per prefix, as everywhere: copies of the
            objects the domain reads (every subsystem's heartbeats and snapshot shards, and what a spec adds),
            copies of the rows the domain reads (the outcomes of kept edits, its copy of the shared
            settings' pointer, the holder record it follows, its backup pointer, its epochs), the pages it
            is asked for (its newest alarms, the ones it keeps for a neighbour) — and, LAST, `reported`:
            the time of this report, and the keys the member presents (`key`, `seal`: what its agent printed at
            its first start). Only what changed is rewritten
    read    `member_copy()` gives the domain a `Cluster` over that prefix, with the same reads a member's
            own stores have. So the directory, the read view, the books, the delivery report and the edit
            collector read a member exactly as before and do not know which way the bytes came
    silence a member's silence is the AGE OF ITS LAST REPORT — on the DOMAIN's clock. Older than
            `lost_after`, its copy answers Unreachable, as a cluster the domain could not reach always did:
            the last known rows are kept, named as such, and the answer is incomplete — Lesson 1's rule,
            unchanged in meaning
    clocks  a member's clock is not the domain's, a small box's least of all. So the domain does not believe
            the time a report carries: it notes, by its own clock, WHEN it first saw each report (each has
            a sequence number), and that is the report's age. The times inside the report — every `ts` in a
            heartbeat or a snapshot shard — are moved onto the domain's clock by the difference between
            "the member stamped it" and "the domain saw it". A member fifteen minutes slow is otherwise
            fifteen minutes stale for ever, and one fifteen minutes fast is never stale at all. The
            difference is kept (`offset`) and shown with the member

What moves: the cost. A domain pass reads one store instead of N members, and a member that cannot be
reached costs nothing to ask about. Each member's report is writes into the domain holder instead — at
three hundred members, measured in Lesson 11.

The one exception, and it is named, not hidden: moving the domain to another member (Lesson 15) needs
the new holder to find the newest backup, and it reads its PEERS for it — member to member, on the site. The
domain in steady state never opens a connection to anyone.
"""
from __future__ import annotations

import json
import time

from w2cplatform.rows import PARSE_ERRORS, finite

from . import declared
from .federation import MEMBER_OBJECTS, REACHES, Cluster, Unreachable

# What a member reported is read with the platform's one list of what a parse raises (`PARSE_ERRORS`), not a list of
# this file's own: the lists here left out `KeyError` in one place, `OverflowError` (`"seq": 1e999`) and `RecursionError`
# (a mark nested ten thousand deep) everywhere — and what they left out raised out of the member's every read (the
# review's eighth pass).

UPLINK = "domain/members"
REPORTED = "reported"
# The largest publication a door takes (the product's `maxPublication`): a member's report this large is the sign to
# publish changes instead of all.
MAX_PUBLICATION = 16 << 20
# What the domain reads of a member, and nothing more. Objects: what a cluster publishes (М10–М11) — every loaded
# subsystem's heartbeats and snapshot, and the objects a spec adds (`declared.reported_objects`) — and what the member
# says it can see.
def objects() -> tuple[str, ...]:
    return (*declared.reported_objects(), REACHES)


def _rows() -> tuple[str, ...]:
    """The rows the domain reads of a member: named where they are defined, collected here (imported late —
    those modules import the agent, and the agent imports this)."""
    from .agent import KEYS_PATH, ROOT_PATH
    from .pending import OUTCOMES_PATH
    from .shared import POINTER, REFUSED
    from .term import BACKUP_TAKEN, HOLDER
    # The root this member pinned and the key set it holds (Lesson 15): what the domain compares with its own
    # before anybody accepts the member (`Members.pinned`, feedback BX).
    return (OUTCOMES_PATH, POINTER, REFUSED, HOLDER, BACKUP_TAKEN, ROOT_PATH, KEYS_PATH, *declared.epoch_prefixes())


def base(member: str) -> str:
    return f"{UPLINK}/{member}/"


class NotPublished(Exception):
    """The member has published nothing yet — a report now would say "I hold no units", completely."""


# One report, in the product's words (`Publication`; ADR-0066's addition of 2026-10-11, night): what a member's agent
# sends its holder's door, `POST /api/member/<member>` (`carry.HolderDoor.member`), or — on the holder's own box and in
# the tests, with no door between — hands `take` itself (`report`). `member_vars` and `member_objects` are the member's
# OWN stores, read locally by its agent; `pages` is what the member is asked to show beyond its rows and objects —
# Lesson 14's alarm pages — as {name: bytes}.
#
#     sent_at    the member's clock when it sent this
#     objects    {key: JSON} — what it publishes (`objects()`), each object as the JSON it is: one that is not JSON is
#                not sent (the product's `Collect`)
#     outcomes   {edit: outcome} — what came of the kept edits it applied (`pending`, Lesson 9)
#     key        the member key it presents (hex)
#     rows       {path: {items, idx}} — the rows the domain reads of it (`_rows()`)          ┐ the course's alone: lines
#     pages      {name: text} — the pages it is asked for                                   │ of `ПАРИТЕТ-КУРС-ПРОДУКТ.md`
#     seal       its sealing key (hex), which the door seals the answer to                  ┘ `# ADR-0066 «курс»`
#
# Lesson 10's ordering rule, on the report: a member that has not published yet does not report. Its report
# would be a COMPLETE answer with no units in it, which the domain must believe; silence is the truthful
# thing until the first publish.
def publication(member: str, member_vars, member_objects, now: float, pages: dict | None = None, key=None) -> dict:
    from .pending import OUTCOMES_PATH
    objs: dict = {}
    for prefix in objects():
        for k in member_objects.list(prefix):
            raw = member_objects.get(k)
            if not raw:
                continue
            try:
                objs[k] = json.loads(raw)
            except PARSE_ERRORS:
                continue                                           # not JSON: not published (the product's `Collect`)
    if not any(k.startswith(f"{s.name}/snapshot/") for s in declared.directory() for k in objs):
        raise NotPublished(f"{member} has not published yet; it reports after its first publish")
    rows: dict = {}
    outcomes = None
    for row in _rows():
        for path in (member_vars.list(row) if row.endswith("/") else [row]):
            items, idx = member_vars.get(path)
            if items is None:
                continue
            if path == OUTCOMES_PATH:
                outcomes = {k: _json_or_text(v) for k, v in items.items()}
            else:
                rows[path] = {"items": items, "idx": idx}
    pub = {"sent_at": now, "objects": objs, "rows": rows,
           "pages": {n: raw.decode("utf-8", "surrogateescape") for n, raw in (pages or {}).items()}}
    if outcomes is not None:
        pub["outcomes"] = outcomes
    # The keys it presents ride on the mark (ADR-0032): a member nobody admitted yet is KNOCKING, and the person who
    # admits it on the domain's console admits it by this key — after comparing its fingerprint with the one the box
    # shows (`Members.accept`). The mark proves nothing by itself; the person's comparison does.
    if key is not None:
        pub["key"], pub["seal"] = key.pub, key.seal_pub
    return pub


def _json_or_text(v):
    """An outcome as the agent keeps it — a JSON text — sent as the JSON it is; one that is not JSON, as its text."""
    try:
        return json.loads(v) if isinstance(v, str) else v
    except PARSE_ERRORS:
        return v


def entries(pub: dict, prev_mark: bytes | None = None, keep_seq: bool = False) -> tuple[dict[str, bytes], bytes]:
    """A publication as the holder keeps it under `base(member)`: `({sub: bytes}, mark)` — `o/<key>`, `v/<path>`,
    `p/<name>`, and the mark `reported`, written last. The mark counts on from `prev_mark`; with `keep_seq` (a relay's
    summary, which carries a silent member's last publication again) it counts only when the member's `sent_at` moved.
    Raises ValueError for a publication that is not one."""
    from .pending import OUTCOMES_PATH
    if not isinstance(pub, dict):
        raise ValueError("a publication is an object {sent_at, objects}")
    try:
        sent_at = finite(pub.get("sent_at"))
    except PARSE_ERRORS:
        raise ValueError("a publication names when it was sent: `sent_at`, a number") from None
    want: dict[str, bytes] = {}
    # What the domain reads of a member, and nothing more: an object or a row it does not read is dropped at the door
    # (the product's `Collect`: "anything else in a member's store is nobody else's business").
    kept_objects, kept_rows = objects(), _rows()
    for part, fam in (("objects", "o/"), ("rows", "v/"), ("pages", "p/")):
        got = pub.get(part) or {}
        if not isinstance(got, dict):
            raise ValueError(f"`{part}` of a publication is an object")
        for k, v in got.items():
            if not isinstance(k, str) or ".." in k.split("/") or (
                    fam == "o/" and not k.startswith(kept_objects)) or (
                    fam == "v/" and not any(k == r or (r.endswith("/") and k.startswith(r)) for r in kept_rows)):
                continue
            if fam == "o/":
                want[fam + k] = json.dumps(v).encode()
            elif fam == "v/":
                if not isinstance(v, dict) or not isinstance(v.get("items"), dict):
                    raise ValueError(f"the row {k} of a publication is {{items, idx}}")
                want[fam + k] = json.dumps({"items": v["items"], "idx": v.get("idx", 0)}, sort_keys=True).encode()
            else:
                if not isinstance(v, str):
                    raise ValueError(f"the page {k} of a publication is a text")
                want[fam + k] = v.encode("utf-8", "surrogateescape")
    outcomes = pub.get("outcomes")
    if outcomes is not None:
        if not isinstance(outcomes, dict):
            raise ValueError("`outcomes` of a publication is an object")
        items = {k: v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, sort_keys=True) for k, v in outcomes.items()}
        want["v/" + OUTCOMES_PATH] = json.dumps({"items": items, "idx": 0}, sort_keys=True).encode()
    presented = {f: pub[f] for f in ("key", "seal") if isinstance(pub.get(f), str) and pub[f]}
    # The mark of the last report, read to count on from. A mark that does not parse — half a write — raised here
    # before the new one was written, so it was never written again: the member stopped reporting for good, by one
    # object (М10's seventh review, part 2). It starts again from the clock's milliseconds — a number the domain has
    # not seen, which is all `_Fresh` asks of a sequence — and is written whole.
    try:
        prev = json.loads(prev_mark) if prev_mark else {}
        seq = int(prev.get("seq", 0)) if isinstance(prev, dict) else 0
        same = isinstance(prev, dict) and prev.get("ts") == sent_at
    except PARSE_ERRORS:
        seq, same = int(sent_at * 1000) - 1, False
    if not (keep_seq and same and prev_mark):
        seq += 1
    mark = json.dumps({"ts": sent_at, "seq": seq, "items": len(want), **presented}).encode()
    return want, mark


def take(member: str, pub: dict, domain_objects) -> int:
    """The holder's half: one member's publication into its own object store, under `base(member)` — only what changed
    is rewritten, what the member no longer has is swept, and the mark goes last: the report is whole."""
    b = base(member)
    want, mark = entries(pub, domain_objects.get(b + REPORTED))
    written = 0
    for k, raw in want.items():
        if domain_objects.get(b + k) != raw:                       # only what changed is rewritten
            domain_objects.put(b + k, raw)
            written += 1
    # Only the report's own families are the report's to sweep (`o/`, `v/`, `p/`): beside them under the same prefix
    # lies what another writer keeps for this member — a relay's summary of its members (`relay.BUNDLE`) — and the
    # office's own report deleted its bundle on every pass, written again at once: two writes for none, and between them
    # no member behind it reported to the holder (the three-site run, O3).
    keep = {b + k for k in want}
    for full in domain_objects.list(b):
        if full[len(b):].startswith(("o/", "v/", "p/")) and full not in keep:
            domain_objects.delete(full)                            # gone from the member: gone from its report
    domain_objects.put(b + REPORTED, mark)                         # last: the report is whole
    return written + 1


def report(member: str, member_vars, member_objects, domain_objects, now: float, pages: dict | None = None,
           key=None) -> int:
    """One report with no door between: the member's publication taken into `domain_objects` itself — the holder's own
    agent on its own box, a member behind a relay into its relay's objects, the tests."""
    return take(member, publication(member, member_vars, member_objects, now, pages, key), domain_objects)


def reported_at(member: str, domain_objects) -> float | None:
    """The time the member stamped its last report with — ITS clock. For how old the report is, ask the copy."""
    raw = domain_objects.get(base(member) + REPORTED)
    try:
        return float(json.loads(raw)["ts"]) if raw else None
    except PARSE_ERRORS:
        return None                                                  # a mark nobody can read says no time (the seventh review)


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
        try:
            mark, now = json.loads(raw), self.wall()
            ts = finite(mark["ts"])                                  # `nan` would make every time of the member `nan`
        except PARSE_ERRORS as e:
            # Not a report the domain can read: as if the member had not reported (М10's seventh review) — it raised a
            # `ValueError` out of every read of the member, which nothing above takes for a silent member.
            raise Unreachable(f"{self.member}'s last report mark does not parse ({e}): the member writes it again "
                              f"with its next report") from None
        if mark.get("seq") != self.seq:                              # a new report: seen now, by our clock
            self.seq, self.seen_at = mark.get("seq"), now
            self.offset = now - ts                                   # our clock minus theirs, as of this report
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
            except PARSE_ERRORS:                          # `ts: null` too: handed on as it is, the reader decides
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
        try:
            d = json.loads(raw)
            return d["items"], d["idx"]
        except PARSE_ERRORS as e:
            # A row of the copy that does not parse is not a row that is gone: this read is as one the member did not
            # answer (М10's seventh review) — said, counted, and each reader's own "not reached" decides.
            MEMBER_OBJECTS.garbled(f"{self.f.member}/{path}", e)
            raise Unreachable(f"{self.f.member}'s copy of {path} does not parse ({e})") from None

    def list(self, prefix: str) -> list[str]:
        self.f.check()
        n = len(self.f.base) + 2
        return [k[n:] for k in self.f.store.list(self.f.base + "v/" + prefix)]

    def put(self, path, items, cas=None):
        raise PermissionError("the domain writes nothing into a member: what it wants there is a row its agent takes home")


def member_copy(member: str, domain_objects, reaches=(), lost_after: float = 45.0, wall=time.time,
                via: str | None = None) -> Cluster:
    """The domain's handle on a member it never reaches: a `Cluster` over that member's last report. Its
    `objects.f.offset` is how far the member's clock is from the domain's, as of the last report.

    `via`: Lesson 17's summary report — the member reports to that relay, and the relay carries one bundle
    for all its members. Read the same way; silent together with the relay."""
    if via is not None:
        from .relay import BundleView
        domain_objects = NewerRoad(member, domain_objects, BundleView(via, domain_objects), lost_after, wall)
    f = _Fresh(member, domain_objects, lost_after, wall)
    return Cluster(member, _CopyVars(f), _CopyObjects(f), frozenset(reaches), via=via)


class NewerRoad:
    """A member placed behind a relay is read from the relay's bundle — and from its own direct report too. The
    topology describes a road; it does not forbid another (feedback AM): a member that can reach the domain after
    all, or that has not yet been moved, is not made silent by a record that says it goes round.

    Which of the two: among the roads still ALIVE on the domain's clock — whose report changed within
    `lost_after` — the newer by the report's `ts`, the member's own clock, the same one on both roads (not by its
    number, which each store counts for itself). A road that has gone silent gives way to a live one whatever
    the member's clock says: a member whose clock stepped back would otherwise freeze on its stale road until it
    counted as silent (found by the product). The number the domain's freshness sees is the road's name with its
    own, so a switch of road is a new report."""

    def __init__(self, member: str, direct, bundled, lost_after: float = 45.0, wall=time.time):
        self.member, self.roads, self.lost_after, self.wall = member, {"direct": direct, "via": bundled}, lost_after, wall
        self.seen: dict[str, tuple] = {}                  # road -> (its report number, when the domain first saw it)
        self.unread: set[str] = set()                     # roads that could not be read on the last pick

    def _pick(self) -> str:
        now, marks, self.unread = self.wall(), {}, set()
        for name, road in self.roads.items():
            try:
                raw = road.get(base(self.member) + REPORTED)
            except Unreachable:
                self.unread.add(name)
                continue                               # a relay whose bundle cannot be read is no road this pass — the
            if not raw:                                  # member's own report still is (the review's eighth pass)
                continue
            try:
                mark = json.loads(raw)
                finite(mark.get("ts", 0))
            except PARSE_ERRORS:
                continue                                 # a road whose mark does not parse is no road this pass (the seventh review)
            if self.seen.get(name, (None,))[0] != mark.get("seq"):
                self.seen[name] = (mark.get("seq"), now)
            marks[name] = mark
        if not marks:
            return "direct" if "via" not in self.unread else "via"   # neither road reads: the bundle's own words, if it is that
        alive = [n for n in marks if now - self.seen[n][1] <= self.lost_after] or \
                [max(marks, key=lambda n: self.seen[n][1])]          # both silent: the one heard last
        return max(alive, key=lambda n: (float(marks[n].get("ts", 0)), self.seen[n][1]))

    def get(self, key: str):
        name = self._pick()
        raw = self.roads[name].get(key)
        if raw is not None and key == base(self.member) + REPORTED:
            try:
                mark = json.loads(raw)
                mark["seq"] = f"{name}:{mark.get('seq')}"
            except PARSE_ERRORS:
                return raw                               # as it is: `_Fresh` reads it as no report, with the words
            return json.dumps(mark).encode()
        return raw

    def list(self, prefix: str) -> list[str]:
        return self.roads[self._pick()].list(prefix)


def offset_of(copy: Cluster) -> float:
    """The domain's clock minus the member's, as of its last report seen — for the member's card."""
    return copy.objects.f.offset


_FRESH: dict[tuple[int, str], _Fresh] = {}


def reported_at(member: str, domain_objects, lost_after: float = 45.0, wall=time.time) -> float | None:
    """When the member's last report was made, on the domain's clock — however old; None: it never reported (or its mark
    does not read). What the domain calls a member silent by when it reports no page (the scenario «камера — офис —
    центр», N9): the same remembered sequence as its pages' (`_FRESH`)."""
    f = _FRESH.setdefault((id(domain_objects), member), _Fresh(member, domain_objects, lost_after, wall))
    f.lost_after, f.wall = lost_after, wall
    try:
        f.check()
    except Unreachable:
        if f.seq is None:
            return None
    return f.seen_at


def page(member: str, name: str, domain_objects, lost_after: float = 45.0, wall=time.time,
         stale_ok: bool = False) -> dict | None:
    """One page a member reported (Lesson 14's alarms), with its times on the domain's clock, or Unreachable
    if its report is too old — by the domain's clock, remembered per store and member across calls.
    `stale_ok`: the page of the LAST report however old — what a silent member said before it went quiet.
    A member that never reported is still Unreachable."""
    f = _FRESH.setdefault((id(domain_objects), member), _Fresh(member, domain_objects, lost_after, wall))
    f.lost_after, f.wall = lost_after, wall
    try:
        f.check()
    except Unreachable:
        if not stale_ok or f.seq is None:
            raise
    raw = domain_objects.get(base(member) + "p/" + name)
    if not raw:
        return None
    try:
        p = json.loads(raw)
        if not isinstance(p, dict):
            raise TypeError("a page is not an object")
        for k in ("from", "to", "known_until"):
            if p.get(k) is not None:
                p[k] = f.domain_time(finite(p[k]))
        events = p.get("events", [])
        if not isinstance(events, list):
            raise TypeError("its events are not a list")
    except PARSE_ERRORS as e:
        MEMBER_OBJECTS.garbled(f"{member}/p/{name}", e)
        raise Unreachable(f"{member}'s page {name} does not parse ({e})") from None
    MEMBER_OBJECTS.parsed(f"{member}/p/{name}")
    # One line of the page that is not a line — no object, a time that is a word — is that line's (the review's eighth
    # pass, minor: `{"t": "x"}` from one member raised out of the domain's whole list of alarms). Skipped, counted once.
    kept, bad = [], None
    for e in events:
        try:
            if not isinstance(e, dict):
                raise TypeError("a line is not an object")
            t = finite(e["t"])
        except PARSE_ERRORS as err:
            bad = err
            continue
        # `t_src` keeps the line's own time, on the member's clock: the shift to ours is taken afresh with every
        # report and moves with how late the domain read it, so a line compared by its shifted time is a new line
        # on every report (feedback AZ). Whatever remembers lines — the week of history — keys them on this.
        e["t_src"], e["t"] = e["t"], f.domain_time(t)
        kept.append(e)
    if bad is not None:
        MEMBER_OBJECTS.garbled(f"{member}/p/{name}#line", bad)
    else:
        MEMBER_OBJECTS.parsed(f"{member}/p/{name}#line")
    p["events"] = kept
    return p
