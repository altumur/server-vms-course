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
    up      the member reports into the relay's store and the relay carries ONE object for all such members — sent to
            the holder's door, `POST /api/relay/<relay>` (`take_bundle`), read by `member_copy(..., via=relay)`

The price: a relay down makes its members silent too, and nothing can be done about it — there is no other road. What
travels on the media road between the levels is a subsystem's, not this module's.
"""
from __future__ import annotations

import json
import logging

from w2cplatform.rows import PARSE_ERRORS

from .federation import Unreachable

log = logging.getLogger("relay")


# A relay forwards original publication bodies. The holder keeps each accepted member generation
# under domain/members/<member>/reports/<rev>, independently of the route that delivered it.
MEMBER_SHARE = 256 << 10
MAX_RELAY_BATCH = 4 * (16 << 20)


def relayed(members: list[str], relay_objects) -> dict[str, bytes]:
    """Original accepted publication bodies; never reconstruct pieces or change their bytes."""
    from .reports import read
    out = {}
    for member in members:
        try:
            out[member] = read(member, relay_objects).raw
        except Unreachable:
            continue
    return out


def take_bundle(relay: str, publications: dict, domain_objects, *, received_at: float) -> tuple[bool, dict[str, str]]:
    """Each authenticated, topology-checked member enters the holder's single report sequence."""
    from .uplink import take
    changed, refused = False, {}
    for member, raw in sorted(publications.items()):
        if not isinstance(raw, bytes) or len(raw) > MEMBER_SHARE:
            refused[member] = f'report exceeds the {MEMBER_SHARE} byte member share'
            continue
        try:
            changed |= bool(take(member, raw, domain_objects, received_at=received_at, via=relay))
        except (ValueError, Unreachable) as e:
            refused[member] = str(e)
    return changed, refused


def bundle(relay: str, members: list[str], relay_objects, domain_objects, *, received_at: float) -> bool:
    return take_bundle(relay, relayed(members, relay_objects), domain_objects, received_at=received_at)[0]


# -- the relay: a cluster as its members' road to the domain ---------------------------------------------
RELAY_SEEN = "relay/domain/seen"


def relay_down(agent, members: list[str]) -> int:
    """One pass of relaying down, after the relay's agent reached the domain: the domain's answer for each member it
    relays, kept in the agent's memory (`agent.relayed`) — asked of the holder's door for that member when the agent
    has a door (`CarryClient.carry_for`: sealed to the member, with the member's key to check its asks by), read
    through `carry.answer` when it holds the holder's store itself (the tests). A member it no longer relays is
    forgotten. How current it all is, the relay says on every pass of its own, reached or not (`say_seen`)."""
    from .carry import Refused, answer
    from .members import Members
    changed = 0
    refused = agent.__dict__.setdefault("relay_refused", {})
    for m in members:
        if hasattr(agent.domain_vars, "carry_for"):
            # The door refusing one member is that member's (O9: one no longer on the list): what was kept for it is
            # dropped and the door's words kept for its asks (`RelayDoor`); the others are relayed as before.
            try:
                got = agent.domain_vars.carry_for(m)
            except Refused as e:
                changed += agent.relayed.pop(m, None) is not None
                refused[m] = e.detail
                continue
        else:
            got = answer(agent.domain_vars, agent.domain_objects, m)
            got["key"] = (Members(agent.domain_vars).read()["members"].get(m) or {}).get("key")
        if agent.relayed.get(m) != got:
            changed += 1
        agent.relayed[m] = got
        refused.pop(m, None)
    for m in [m for m in agent.relayed if m not in members]:
        del agent.relayed[m]
    for m in [m for m in refused if m not in members]:
        del refused[m]
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
    answered only in the same process (`plain`: the tests' members), never over the network.

    A CLUSTER THE RELAY DOES NOT RELAY KNOCKS THROUGH IT (the three-site scenario, N1; ADR-0066's addition of
    2026-10-11, «Архитектор»). The knock is remembered by the holder's door alone (`carry.HolderDoor`, `note_knock`), and
    a member behind an office reaches no door but the office's: it was answered 404 «relays no member», nothing was passed
    on, and no member behind an office was ever in `knocking` — none could be admitted by its fingerprint. Now an ask the
    relay has nothing for and no refusal of goes on to the holder by the relay's own road to it — the one its relaying
    down takes (`CarryClient.pass_on`) — as it came: the cluster's time, sealing key, signature and the key it names. The
    relay keeps nothing of it and vouches for nothing; the holder checks the signature as at its own door, remembers the
    knock, and refuses — and the relay answers with the holder's words and status, not with a 404 of its own."""

    def __init__(self, agent, relay_objects=None):
        self.agent = agent
        self.objects = relay_objects if relay_objects is not None else getattr(agent, "bundle_store", None)

    def _kept(self, cluster: str) -> dict:
        from .carry import Refused
        kept = self.agent.relayed.get(cluster) if self.agent is not None else None
        why = getattr(self.agent, "relay_refused", {}).get(cluster) if self.agent is not None else None
        if kept is None and why:
            raise Refused(403, f"the domain refuses {cluster} to {getattr(self.agent, 'cluster', 'the relay')}: {why}")
        if kept is None:
            raise Refused(404, f"{getattr(self.agent, 'cluster', 'the relay')} relays no member {cluster}, or has not "
                               f"reached the domain for it yet")
        return {**kept, "seen": seen_mark(self.objects)}

    def carry(self, cluster: str, at: float, seal: str, signature: str, for_member: str | None = None,
              key: str | None = None) -> dict:
        """`key`: the key the ask says it is signed with — the holder's door remembers a cluster it does not know by it
        (a knock: passed on, `_pass_on`); the relay checks the member by the key the domain answered with, and no other."""
        from w2cplatform.trust.memberkey import verify
        from .carry import SKEW, Refused, request_message
        if for_member not in (None, cluster):
            raise Refused(403, f"a member asks a relay for its own rows only, not {for_member}'s")
        if self._stranger(cluster):
            self._pass_on(cluster, at, seal, signature, key)
        kept = self._kept(cluster)
        if not kept.get("key"):
            raise Refused(403, f"{cluster} was admitted without a key: it cannot be told from anybody on the site")
        if not verify(kept["key"], request_message(cluster, at, seal), signature):
            raise Refused(401, f"the ask is not signed by {cluster}'s key")
        if abs(self.agent.now() - at) > SKEW:
            raise Refused(401, f"the ask is {self.agent.now() - at:+.0f} s from the relay's clock")
        return kept

    def member(self, cluster: str, body: bytes, signature: str) -> dict:
        from .carry import SKEW, Refused
        from .uplink import MAX_PUBLICATION
        from .uplink import take
        from .reports import StaleReport
        from w2cplatform.trust.memberkey import verify_request
        if len(body) > MAX_PUBLICATION:
            raise Refused(413, 'publication exceeds body limit')
        kept = self._kept(cluster)
        if self.objects is None:
            raise Refused(503, 'the relay has no report store')
        why = verify_request(kept.get('key', ''), signature, 'POST', f'/api/member/{cluster}',
                             body, self.agent.now(), SKEW)
        if why:
            raise Refused(401, why)
        try:
            take(cluster, body, self.objects, received_at=self.agent.now(), signature=signature)
        except StaleReport as e:
            raise Refused(409, str(e)) from None
        except ValueError as e:
            raise Refused(400, str(e)) from None
        return kept

    def _stranger(self, cluster: str) -> bool:
        """Nothing kept for `cluster`, no refusal of it, and not a member this relay relays (its topology as carried, or
        `RELAY_MEMBERS`): a cluster the domain did not name behind this relay — one asking to join, as far as the relay
        can tell. A member it relays and has not reached the domain for yet is not one: it waits for the relay's pass."""
        a = self.agent
        if a is None or cluster in a.relayed or cluster in getattr(a, "relay_refused", {}):
            return False
        relays = getattr(a, "relay_members", None)
        return cluster not in (relays() if callable(relays) else (relays or []))

    def _pass_on(self, cluster: str, at: float, seal: str, signature: str, key: str | None) -> None:
        """The ask of a cluster this relay does not relay, to the holder's door by the relay's road to the domain, as it
        came; the holder's refusal is raised as it said it. An answer the holder GAVE is not handed on: the domain's
        topology does not put that member behind this relay, and the relay gives a member nothing it did not keep."""
        from .carry import HolderDoor, Refused
        a = self.agent
        road = a.domain_vars                             # a door (`CarryClient`), a relay above (`RelayLink`) — or, in
        if not hasattr(road, "pass_on"):                 # the tests, the holder's stores: its door over them
            road = _HolderRoad(HolderDoor(road, a.domain_objects, wall=a.now))
        try:
            road.pass_on(cluster, at, seal, signature, key)
        except Refused:
            raise                                        # the holder's words, and its status
        except Unreachable as e:
            raise Refused(503, f"{getattr(a, 'cluster', 'the relay')} relays no member {cluster}, and could not pass "
                               f"its ask on to the domain: {e}") from None
        raise Refused(404, f"{getattr(a, 'cluster', 'the relay')} relays no member {cluster}: the domain's topology "
                           f"does not place it here, or the relay has not reached the domain for it yet")

    def plain(self, cluster: str) -> dict:
        from .carry import Refused
        kept = self._kept(cluster)
        if kept.get("key"):
            raise Refused(401, f"{cluster} has a key: it asks signed")
        return kept


class _HolderRoad:
    """The holder's door over its stores, as a relay that holds them (the tests) passes an ask on."""

    def __init__(self, door):
        self.door = door

    def pass_on(self, cluster: str, at: float, seal: str, signature: str, key: str | None) -> dict:
        return self.door.carry(cluster, at, seal, signature, None, key=key)


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

    def pass_on(self, cluster: str, at: float, seal: str, signature: str, key: str | None) -> dict:
        """A relay behind this one passes a knock on: to this relay's door, which passes it on in turn — up to the holder."""
        return self.door.carry(cluster, at, seal, signature, key=key)


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

        def do_POST(self):
            from .uplink import MAX_PUBLICATION
            path = self.path.split('?', 1)[0]
            if not path.startswith('/api/member/'):
                return self._send(404, {'detail': 'no such route'})
            try:
                size = int(self.headers.get('Content-Length', '-1'))
                if not 0 <= size <= MAX_PUBLICATION:
                    return self._send(413, {'detail': 'publication exceeds body limit'})
                body = self.rfile.read(size)
                if len(body) != size:
                    return self._send(400, {'detail': 'incomplete publication'})
                got = door.member(path[len('/api/member/'):], body, self.headers.get('X-Agent-Signature', ''))
            except ValueError:
                return self._send(400, {'detail': 'invalid publication length'})
            except Refused as e:
                return self._send(e.status, {'detail': e.detail})
            self._send(200, got)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if not path.startswith("/api/carry/"):
                return self._send(404, {"detail": "no such route"})
            try:
                at = float(self.headers.get("X-W2C-Time", "nan"))
                got = door.carry(path[len("/api/carry/"):], at, self.headers.get("X-W2C-Seal", ""),
                                 self.headers.get("X-W2C-Signature", ""), key=self.headers.get("X-W2C-Key") or None)
            except ValueError:
                return self._send(400, {"detail": "an ask names its time"})
            except Refused as e:
                return self._send(e.status, {"detail": e.detail})
            self._send(200, got)

        def log_message(self, *a):
            pass
    return H
