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
            the time a report carries: it persists, by its own clock, WHEN it accepted each report (each has
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
import logging
import time

from w2cplatform.rows import PARSE_ERRORS, finite

from . import declared
from .federation import MEMBER_OBJECTS, REACHES, Cluster, Unreachable

# What a member reported is read with the platform's one list of what a parse raises (`PARSE_ERRORS`), not a list of
# this file's own: the lists here left out `KeyError` in one place, `OverflowError` (`"rev": 1e999`) and `RecursionError`
# (a mark nested ten thousand deep) everywhere — and what they left out raised out of the member's every read (the
# review's eighth pass).

UPLINK = "domain/members"
REPORTED = "reported"
# The largest publication a door takes (the product's `maxPublication`): a member's report this large is the sign to
# publish changes instead of all.
MAX_PUBLICATION = 16 << 20
log = logging.getLogger(__name__)
_inactive_inputs = set()


def _input_slot(vars_, path, now):
    """Confirm the local owner; slot rows themselves never cross the domain door."""
    from w2cplatform.contract import read_slot
    sub, name = path.split("/", 1)[0], path.rsplit("/", 1)[-1]
    key = f"{sub}/slots/{name}"
    items, index = vars_.get(key)
    slot = read_slot(key, name, items)
    if slot is None or not slot.holder or slot.released or slot.until <= now:
        if path not in _inactive_inputs:
            log.warning("book input %s omitted: no live local slot", path)
            _inactive_inputs.add(path)
        return None
    return key, index
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
    inputs = (rule.source for s in declared.specs() for rule in s.domain.merged.values())
    return tuple(dict.fromkeys((OUTCOMES_PATH, POINTER, REFUSED, HOLDER, BACKUP_TAKEN, ROOT_PATH, KEYS_PATH,
                               *declared.epoch_prefixes(), *inputs)))


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
def publication(member: str, member_vars, member_objects, now: float, pages: dict | None = None, key=None,
                *, sealer=None) -> dict:
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
    inputs = {rule.source for s in declared.specs() for rule in s.domain.merged.values()}
    for row in _rows():
        for path in (member_vars.list(row) if row.endswith("/") else [row]):
            is_input = any(path == source or source.endswith("/") and path.startswith(source) for source in inputs)
            slot = _input_slot(member_vars, path, now) if is_input else None
            if is_input and slot is None:
                continue
            items, idx = member_vars.get(path)
            if items is None:
                continue
            if is_input:
                # A release, takeover or renewal during the read gives no new control fact.
                after = _input_slot(member_vars, path, now)
                if after != slot:
                    continue
                _inactive_inputs.discard(path)
            if path == OUTCOMES_PATH:
                outcomes = {k: _json_or_text(v) for k, v in items.items()}
            else:
                if is_input:
                    from .booksecrets import outgoing
                    items = outgoing(member, path, items, member_vars, sealer, now)
                rows[path] = {"items": items, "idx": idx}
    pub = {"sent_at": now, "objects": objs, "rows": rows,
           "pages": {n: raw.decode("utf-8", "surrogateescape") for n, raw in (pages or {}).items()}}
    if outcomes is not None:
        pub["outcomes"] = outcomes
    # The keys it presents ride in the report body (ADR-0074): a member nobody admitted yet is KNOCKING, and the person who
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


def projection(pub: dict) -> dict[str, bytes]:
    """Read-only projections of one pinned report, restricted to declared inputs."""
    from .pending import OUTCOMES_PATH
    if not isinstance(pub, dict):
        raise ValueError("a publication is an object {sent_at, objects}")
    try:
        sent_at = finite(pub.get("sent_at"))
    except PARSE_ERRORS:
        raise ValueError("a publication names when it was sent: `sent_at`, a number") from None
    want: dict[str, bytes] = {}
    # What the domain reads of a member: undeclared objects and rows stay outside the projection.
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
    return want


def take(member: str, body: bytes, domain_objects, *, received_at: float, signature: str = '', via: str = '') -> int:
    """Store one authenticated report, then prune. Never write mutable per-part projections."""
    from .reports import accept, prune
    previous = domain_objects.get(base(member)+REPORTED)
    accept(member, body, domain_objects, received_at=received_at, signature=signature, via=via)
    prune(member, domain_objects)
    return 0 if previous == domain_objects.get(base(member)+REPORTED) else 2


def report(member: str, member_vars, member_objects, domain_objects, now: float, pages: dict | None = None,
           key=None, *, sealer=None) -> int:
    """Local reports use exactly the serialization and signature of the HTTP client."""
    from w2cplatform.trust.memberkey import MemberKey, sign_request, verify_request
    from .carry import SKEW, publication_bytes
    if key is None:
        key = MemberKey.load_or_make(member_vars, sealer)
    body = publication_bytes(publication(member, member_vars, member_objects, now, pages, key, sealer=sealer))
    signature = sign_request(key, 'POST', f'/api/member/{member}', body, now)
    why = verify_request(key.pub, signature, 'POST', f'/api/member/{member}', body, now, SKEW)
    if why:
        raise ValueError(why)
    return take(member, body, domain_objects, received_at=now, signature=signature)


def reported_at(member: str, domain_objects) -> float | None:
    from .reports import read
    try:
        return read(member, domain_objects).mark['sent_at']
    except Unreachable:
        return None


class _Fresh:
    """A complete generation, pinned once per logical read pass; freshness survives restart."""
    def __init__(self, member, store, lost_after, wall):
        self.member, self.store, self.lost_after, self.wall = member, store, lost_after, wall
        self.base = base(member)
        self.rev, self.seen_at, self.offset = None, None, 0.0
        self.parts = {}

    def check(self, stale_ok=False):
        from .reports import pinned
        try:
            snap = pinned(self.member, self.store)
        except Unreachable:
            self.rev, self.seen_at, self.parts = None, None, {}
            raise
        self.rev = snap.mark['rev']
        self.seen_at = snap.mark['received_at']
        self.offset = self.seen_at - snap.mark['sent_at']
        self.parts = projection(snap.document())
        if not stale_ok and self.wall() - self.seen_at > self.lost_after:
            raise Unreachable(f'{self.member} has not reported for {self.wall()-self.seen_at:.0f} s')

    def domain_time(self, ts):
        return float(ts) + self.offset


class _CopyObjects:
    def __init__(self, fresh):
        self.f = fresh

    def get(self, key):
        self.f.check()
        raw = self.f.parts.get('o/'+key)
        if raw and self.f.offset:
            try:
                doc = json.loads(raw)
                if isinstance(doc, dict) and 'ts' in doc:
                    doc['ts'] = self.f.domain_time(doc['ts'])
                    raw = json.dumps(doc).encode()
            except PARSE_ERRORS:
                pass
        return raw

    def list(self, prefix):
        self.f.check()
        return [k[2:] for k in self.f.parts if k.startswith('o/'+prefix)]

    def put(self, key, data):
        raise PermissionError('a report projection is read only')

    def delete(self, key):
        raise PermissionError('a report projection is read only')


class _CopyVars:
    def __init__(self, fresh):
        self.f = fresh

    def get(self, path):
        self.f.check()
        raw = self.f.parts.get('v/'+path)
        if raw is None:
            return None, 0
        doc = json.loads(raw)
        return doc['items'], doc['idx']

    def list(self, prefix):
        self.f.check()
        return [k[2:] for k in self.f.parts if k.startswith('v/'+prefix)]

    def put(self, path, items, cas=None):
        raise PermissionError('a report projection is read only')


def member_copy(member, domain_objects, reaches=(), lost_after=45.0, wall=time.time, via=None):
    # Both roads are accepted into the same member sequence by the holder's receiver.
    f = _Fresh(member, domain_objects, lost_after, wall)
    return Cluster(member, _CopyVars(f), _CopyObjects(f), frozenset(reaches), via=via)


def offset_of(copy: Cluster) -> float:
    """The domain's clock minus the member's, as of its last report seen — for the member's card."""
    return copy.objects.f.offset


_FRESH: dict[tuple[int, str], _Fresh] = {}


def last_report_at(member: str, domain_objects, lost_after: float = 45.0, wall=time.time) -> float | None:
    """Persisted receipt time, even for a stale report; None for a missing or corrupt generation."""
    f = _FRESH.setdefault((id(domain_objects), member), _Fresh(member, domain_objects, lost_after, wall))
    f.lost_after, f.wall = lost_after, wall
    try:
        f.check()
    except Unreachable:
        if f.rev is None:
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
    f.check(stale_ok=stale_ok)
    raw = f.parts.get("p/" + name)
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
