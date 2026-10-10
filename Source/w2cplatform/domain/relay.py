"""Lesson 17 — the relay: a cluster as its members' road to the domain.

Members on remote sites, behind NATs, relayed by clusters that are behind NATs too, held by one domain at the centre.
One rule generalises Lessons 10 and 16: EACH LEVEL DIALS THE LEVEL ABOVE; a level must be reachable from below and never
from above. Control is flat where it can be — one domain, held by the centre, and every member that can reach the
centre reports to it directly (Lesson 10). A member that can reach ONLY ITS RELAY cannot — and then the relay is its
road to the domain both ways:

    down    the relay's agent asks the domain's door for what each member it relays carries (`carry.py`: the answer
            is that member's own rows, every secret in them sealed to THAT member's key), keeps the answers in its
            MEMORY — never in its stores, which every member of the site reaches — and gives each member only its own,
            by the member's signature (`RelayDoor`); with the time the relay last reached the domain (`say_seen`).
            What a relay can open of its members' secrets: nothing
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
    # only `Unreachable` for "did not answer". `DomainDirectory.where` scans every cluster, so `/domain/where` and every
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
RELAY_SEEN = "relay/domain/seen"


def relay_down(agent, members: list[str]) -> int:
    """One pass of relaying down, after the relay's agent reached the domain: the domain's answer for each member it
    relays, kept in the agent's memory (`agent.relayed`) — asked of the holder's door for that member when the agent
    has a door (`CarryClient.carry_for`: sealed to the member, with the member's key to check its asks by), read
    through `carry.answer` when it holds the holder's store itself (the tests). A member it no longer relays is
    forgotten. How current it all is, the relay says on every pass of its own, reached or not (`say_seen`)."""
    from .carry import answer
    from .members import Members
    changed = 0
    for m in members:
        if hasattr(agent.domain_vars, "carry_for"):
            got = agent.domain_vars.carry_for(m)
        else:
            got = answer(agent.domain_vars, agent.domain_objects, m)
            got["key"] = (Members(agent.domain_vars).read()["members"].get(m) or {}).get("key")
        if agent.relayed.get(m) != got:
            changed += 1
        agent.relayed[m] = got
    for m in [m for m in agent.relayed if m not in members]:
        del agent.relayed[m]
    return changed


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


class RelayDoor:
    """What a relay answers its members: each one's kept answer, to that member only — checked by the member's key (the
    domain's answer carried it), its clock within `carry.SKEW` of the relay's. A member admitted without a key is
    answered only in the same process (`plain`: the tests' members), never over the network."""

    def __init__(self, agent, relay_objects=None):
        self.agent = agent
        self.objects = relay_objects if relay_objects is not None else getattr(agent, "bundle_store", None)

    def _kept(self, cluster: str) -> dict:
        from .carry import Refused
        kept = self.agent.relayed.get(cluster) if self.agent is not None else None
        if kept is None:
            raise Refused(404, f"{getattr(self.agent, 'cluster', 'the relay')} relays no member {cluster}, or has not "
                               f"reached the domain for it yet")
        return {**kept, "seen": seen_mark(self.objects)}

    def carry(self, cluster: str, at: float, seal: str, signature: str, for_member: str | None = None,
              key: str | None = None) -> dict:
        """`key`: the key the ask says it is signed with — the holder's door remembers a cluster it does not know by it
        (a knock); the relay checks the member by the key the domain answered with, and no other."""
        from w2cplatform.trust.memberkey import verify
        from .carry import SKEW, Refused, request_message
        kept = self._kept(cluster)
        if for_member not in (None, cluster):
            raise Refused(403, f"a member asks a relay for its own rows only, not {for_member}'s")
        if not kept.get("key"):
            raise Refused(403, f"{cluster} was admitted without a key: it cannot be told from anybody on the site")
        if not verify(kept["key"], request_message(cluster, at, seal), signature):
            raise Refused(401, f"the ask is not signed by {cluster}'s key")
        if abs(self.agent.now() - at) > SKEW:
            raise Refused(401, f"the ask is {self.agent.now() - at:+.0f} s from the relay's clock")
        return kept

    def plain(self, cluster: str) -> dict:
        from .carry import Refused
        kept = self._kept(cluster)
        if kept.get("key"):
            raise Refused(401, f"{cluster} has a key: it asks signed")
        return kept


class RelayLink:
    """A member's `domain_vars` when it reaches only its relay: `answer_for(cluster, key)` — signed by its key when it has
    one (`carry.CarryClient`, secrets opened by its key), else the relay's plain answer; `seen()` — the relay's age mark."""

    def __init__(self, door: RelayDoor):
        self.door = door

    def answer_for(self, cluster: str, key) -> dict:
        from .carry import CarryClient
        if key is None:
            return self.door.plain(cluster)
        return CarryClient(self.door, cluster, key, wall=self.door.agent.now).carry()

    def seen(self) -> dict | None:
        return seen_mark(self.door.objects)


class Relay:
    """What a member that can reach only its relay uses in place of the domain: `vars`, the relay's door to what the
    domain answered for it (`RelayLink`), and `objects`, the relay's object store, where its reports go as they are."""

    def __init__(self, relay_agent, relay_objects=None):
        self.door = RelayDoor(relay_agent, relay_objects)
        self.vars = RelayLink(self.door)
        self.objects = self.door.objects


def seen_mark(relay_objects) -> dict | None:
    """The relay's age mark, or None when there is none or it does not parse (the relay writes it whole again on its
    next pass, `say_seen`): a member that cannot read it knows nothing of how current its books are."""
    if relay_objects is None:
        return None
    from w2cplatform.rows import finite
    from .federation import published
    return published("relay", RELAY_SEEN, relay_objects.get(RELAY_SEEN),
                     lambda m: None if m.get("age") is None else finite(m["age"]))


def door_handler(door: RelayDoor):
    """The relay's door over HTTP for its members: `GET /api/carry/<cluster>`, signed as the holder's door is asked."""
    from http.server import BaseHTTPRequestHandler

    from w2cplatform.console import Deadlined
    from .carry import Refused

    class H(Deadlined, BaseHTTPRequestHandler):
        def _send(self, status, body):
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if not path.startswith("/api/carry/"):
                return self._send(404, {"detail": "no such route"})
            try:
                at = float(self.headers.get("X-W2C-Time", "nan"))
                got = door.carry(path[len("/api/carry/"):], at, self.headers.get("X-W2C-Seal", ""),
                                 self.headers.get("X-W2C-Signature", ""))
            except ValueError:
                return self._send(400, {"detail": "an ask names its time"})
            except Refused as e:
                return self._send(e.status, {"detail": e.detail})
            self._send(200, got)

        def log_message(self, *a):
            pass
    return H
