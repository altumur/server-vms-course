"""Lesson 17 — the relay: a cluster as its members' road to the domain.

Members on remote sites, behind NATs, relayed by clusters that are behind NATs too, held by one domain at the centre.
One rule generalises Lessons 10 and 16: EACH LEVEL DIALS THE LEVEL ABOVE; a level must be reachable from below and never
from above. Control is flat where it can be — one domain, held by the centre, and every member that can reach the
centre reports to it directly (Lesson 10). A member that can reach ONLY ITS RELAY cannot — and then the relay is its
road to the domain both ways:

    down    the relay's agent RELAYS everything the domain leaves for that member (keys, revocations, its grants, kept
            edits, the rows its subsystems' specs say it carries, the holder record, shared settings and backups, with
            their objects) into `relay/` in the relay's own stores, with the time the relay last reached the domain;
            the member's agent reads that instead of the domain (`Relay`)
    up      the member reports into the relay's store and the relay carries ONE object for all such members (`bundle`,
            `member_copy(..., via=relay)`)

The price: a relay down makes its members silent too, and nothing can be done about it — there is no other road. What
travels on the media road between the levels is a subsystem's, not this module's.
"""
from __future__ import annotations

import json
import logging

from .federation import Unreachable
from .uplink import UPLINK, base

log = logging.getLogger("relay")


# -- the summary report ------------------------------------------------------------------------------------
# The relay carries its members' reports as ONE object in the domain holder. Members report to the RELAY's
# object store (the relay is reachable from its sites — that is the whole premise of this layout); the
# relay's agent folds what is there into `domain/members/<relay>/bundle`, only when it changed.
BUNDLE = "bundle"
# What one member's report may weigh in its relay's bundle (feedback from the product, checking the eighth review: a
# bundle bounded only as a whole let one large member crowd out the others behind the relay). Thirty members' reports
# are some 60 KiB together (Lesson 17's test); a member past this share is NOT carried, and the bundle says why under
# `REFUSED_KEY` — the domain names the reason with the member (`BundleView`), and the others are carried whole.
MEMBER_SHARE = 256 << 10
REFUSED_KEY = "!refused"                 # not a member's name: `!` is in no cluster's name


def bundle(relay: str, members: list[str], relay_objects, domain_objects) -> bool:
    out: dict[str, dict[str, str]] = {}
    refused: dict[str, str] = {}
    for m in members:
        b = base(m)
        keys = relay_objects.list(b)
        if keys:
            entry = {k[len(b):]: (relay_objects.get(k) or b"").decode("utf-8", "surrogateescape") for k in keys}
            size = sum(len(k) + len(v) for k, v in entry.items())
            if size > MEMBER_SHARE:
                refused[m] = (f"its report is {size} bytes, over the {MEMBER_SHARE} its relay carries for one member — "
                              f"the relay carried the others")
                continue
            out[m] = entry
    if refused:
        out[REFUSED_KEY] = refused
    raw = json.dumps(out, sort_keys=True).encode()
    key = base(relay) + BUNDLE
    if domain_objects.get(key) == raw:
        return False
    domain_objects.put(key, raw)
    return True


class BundleView:
    """The domain holder's store as a member reporting through `relay` sees it: its report, out of the
    relay's bundle. Read only; what `member_copy(..., via=relay)` reads through."""

    def __init__(self, relay: str, domain_objects):
        self.relay, self.store = relay, domain_objects

    # A BUNDLE THAT DOES NOT PARSE IS ITS RELAY'S MEMBERS NOT ANSWERING (the review's eighth pass, blocker). It was read
    # with a bare `json.loads(raw).get(member)`: a torn bundle — or a list, the shape an older build of the relay wrote —
    # raised `JSONDecodeError`/`AttributeError` out of every read of every member behind it, and the readers above take
    # only `Unreachable` for "did not answer". `DomainDirectory.where` scans every cluster, so `/api/where` and every
    # edit through the domain failed for every unit of the domain; the pass over the books raised, and the signer's
    # loop swallowed it — the stream tokens in the books stopped being re-issued. Now the bundle is read through the
    # members' one reader (`MEMBER_OBJECTS`): what does not parse is counted once under `<relay>/bundle`, logged once,
    # and is `Unreachable` for the members behind that relay — each reader's own "not reached" decides, and the rest
    # of the domain is read. A list is REFUSED by name, not parsed: an older relay is updated, not guessed at (the
    # coordinator's decision). One member's entry that is not an object is that member's alone, and one record of an
    # entry that is not a string is that record's (feedback from the product: one record rejected its relay's bundle).
    def _entries(self, member: str) -> dict[str, str]:
        from w2cplatform.rows import PARSE_ERRORS
        from .federation import MEMBER_OBJECTS
        key = base(self.relay) + BUNDLE
        raw = self.store.get(key)
        if not raw:
            return {}
        try:
            doc = json.loads(raw)
            if isinstance(doc, list):
                raise TypeError(f"relay {self.relay} runs an older build (its bundle is a list); update it")
            if not isinstance(doc, dict):
                raise TypeError(f"relay {self.relay}'s bundle is not an object: {type(doc).__name__}")
        except PARSE_ERRORS as e:
            MEMBER_OBJECTS.garbled(f"{self.relay}/{BUNDLE}", e)
            raise Unreachable(f"{member} reports through relay {self.relay}, whose bundle cannot be read: {e}") from None
        MEMBER_OBJECTS.parsed(f"{self.relay}/{BUNDLE}")
        why = doc.get(REFUSED_KEY, {}).get(member) if isinstance(doc.get(REFUSED_KEY), dict) else None
        if why is not None:
            raise Unreachable(f"relay {self.relay} did not carry {member}'s report: {why}")
        entry = doc.get(member, {})
        if not isinstance(entry, dict):
            MEMBER_OBJECTS.garbled(f"{self.relay}/{BUNDLE}#{member}", TypeError(f"not an object: {type(entry).__name__}"))
            raise Unreachable(f"{member}'s entry in relay {self.relay}'s bundle cannot be read")
        MEMBER_OBJECTS.parsed(f"{self.relay}/{BUNDLE}#{member}")
        out = {}
        for sub, v in entry.items():                     # …and one record of it, that record's: left out, counted, named
            if isinstance(v, str):
                out[sub] = v
                MEMBER_OBJECTS.parsed(f"{self.relay}/{BUNDLE}#{member}/{sub}")
            else:
                MEMBER_OBJECTS.garbled(f"{self.relay}/{BUNDLE}#{member}/{sub}", TypeError(f"not a string: {type(v).__name__}"))
        return out

    @staticmethod
    def _split(key: str) -> tuple[str, str]:
        rest = key[len(UPLINK) + 1:]
        member, _, sub = rest.partition("/")
        return member, sub

    def get(self, key: str) -> bytes | None:
        member, sub = self._split(key)
        v = self._entries(member).get(sub)
        return v.encode("utf-8", "surrogateescape") if v is not None else None

    def list(self, prefix: str) -> list[str]:
        member, sub = self._split(prefix)
        return [base(member) + k for k in self._entries(member) if k.startswith(sub)]


# -- the relay: a cluster as its members' road to the domain ---------------------------------------------
# What the domain leaves for a member, as its agent reads it (`DomainAgent.sync`): named once here, so the
# relay carries exactly that and a member's agent needs no other code.
RELAY = "relay/"
RELAY_SEEN = "relay/domain/seen"


def _relayed_rows(member: str) -> list[str]:
    from .agent import GRANTS_PATH, KEYS_PATH, REVOKED_PATH, per_cluster
    from .pending import PENDING_PATH
    from .shared import POINTER
    from .term import BACKUP, HOLDER
    return [KEYS_PATH, REVOKED_PATH, HOLDER, POINTER, f"{GRANTS_PATH}/{member}", f"{PENDING_PATH}/{member}",
            f"{BACKUP}/{member}", *[f"{p}/{member}" for p in per_cluster()]]


def relay_down(members: list[str], domain_vars, domain_objects, relay_vars, relay_objects, now: float) -> int:
    """One pass of relaying down, after the relay's agent has reached the domain. Copies each row a member's agent
    would read, and the object a pointer names (shared settings, backup), into `relay/`; only what changed.
    How current it all is, the relay says on every pass of its own, reached or not (`say_seen`)."""
    written, seen = 0, set()
    for m in members:
        for path in _relayed_rows(m):
            if path in seen:
                continue
            seen.add(path)
            items, _ = domain_vars.get(path)
            have, idx = relay_vars.get(RELAY + path)
            if items is None and have is None:
                continue
            items = dict(items or {})
            if have != items:
                relay_vars.put(RELAY + path, items, cas=idx)
                written += 1
            obj = items.get("object") if isinstance(items, dict) else None
            if obj and domain_objects is not None:
                raw = domain_objects.get(obj)
                if raw is not None and relay_objects.get(RELAY + obj) != raw:
                    relay_objects.put(RELAY + obj, raw)
                    written += 1
    return written


# How current the relayed books are — an AGE, measured on the relay's clock: how long ago the relay last
# reached the domain, said on every relay pass, the failed ones above all, with a counter. The member takes a
# new counter as "said just now" and sets its own mark to ITS clock minus the age: two clocks never compared,
# and the error is at most one member's pass (feedback AM — the product sends the same age in its exchange).
#
# A mark that does not parse — half a write — is written whole again (the review's eighth pass, major). It was read to
# count on from BEFORE the new one was written, so one torn mark raised on every pass, was never rewritten, and the
# members behind the relay never heard how current their books were; the relay's agent loop, its pass raising, ran
# again at once (`run`, now paced). It counts on from the clock's milliseconds instead — a number the members have
# not seen, which is all they ask of it — as `uplink.report` does with its own mark.
def say_seen(relay_objects, last_contact: float | None, now: float) -> dict:
    from w2cplatform.rows import PARSE_ERRORS
    raw = relay_objects.get(RELAY_SEEN)
    try:
        n = int(json.loads(raw).get("n", 0)) + 1 if raw else 1
    except PARSE_ERRORS:
        n = int(now * 1000)
    mark = {"n": n, "age": None if last_contact is None else max(0.0, now - last_contact)}
    relay_objects.put(RELAY_SEEN, json.dumps(mark).encode())
    return mark


class Relay:
    """What a member that can reach only its relay uses in place of the domain: `vars` and `objects` over the
    relay's `relay/` copy — its reports go into the relay's store as they are — and `seen()`, how long ago the
    RELAY last reached the domain (`say_seen`), which is how current the member's books are."""

    def __init__(self, relay_vars, relay_objects):
        self.vars = _RelayVars(relay_vars, relay_objects)
        self.objects = _RelayObjects(relay_objects)


class _RelayVars:
    def __init__(self, relay_vars, relay_objects):
        self.relay_vars, self.relay_objects = relay_vars, relay_objects

    def get(self, path):
        return self.relay_vars.get(RELAY + path)

    def list(self, prefix):
        return [k[len(RELAY):] for k in self.relay_vars.list(RELAY + prefix)]

    def seen(self) -> dict | None:
        """The relay's age mark, or None when there is none or it does not parse (the relay writes it whole again on
        its next pass, `say_seen`): a member that cannot read it knows nothing of how current its books are."""
        from w2cplatform.rows import finite
        from .federation import published
        mark = published("relay", RELAY_SEEN, self.relay_objects.get(RELAY_SEEN),
                         lambda m: None if m.get("age") is None else finite(m["age"]))
        return mark


class _RelayObjects:
    """Documents from the relay; the member's own report straight into the relay's store."""

    def __init__(self, relay_objects):
        self.relay = relay_objects

    def _key(self, key: str) -> str:
        return key if key.startswith(UPLINK + "/") else RELAY + key

    def get(self, key):
        return self.relay.get(self._key(key))

    def list(self, prefix):
        return self.relay.list(prefix) if prefix.startswith(UPLINK + "/") else \
            [k[len(RELAY):] for k in self.relay.list(RELAY + prefix)]

    def put(self, key, data):
        return self.relay.put(key, data)

    def delete(self, key):
        return self.relay.delete(key)
