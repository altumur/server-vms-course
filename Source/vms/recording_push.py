"""C2 push channels: assigned observations, a local role door, one cursor per receiver."""
from __future__ import annotations

import base64
import json
import math
import time

from w2cplatform.domain.placement import placed
from w2cplatform.domain.memberbook import read as member_book
from w2cplatform.domain.tokenrequest import Refused, WorkerTokenDoor
from .recording_books import Unconfirmed, primary, read, recording_value
from .recording_publication import member


class AssignedPush:
    def __init__(self, pusher, token_requests=None, *, role="camworker", env=None, clock=None):
        self.pusher = pusher
        self.door = token_requests or WorkerTokenDoor.from_env(role, env)
        self.clock = clock or time.monotonic
        self.scope, self.channels, self.token, self.deadline = None, {}, None, 0.0
        self.absent_since = None
        self.replies = {}

    def observe_absence(self):
        if self.absent_since is None:
            self.absent_since = self.clock()
        self.pusher.uncovered = self.clock() - self.absent_since >= 20.0

    def entry(self):
        p = self.pusher
        assignment = placed(p.flash, "rec", p.serial)
        if assignment is None:
            self.scope, self.channels, self.token = None, {}, None
            return None
        scope = (assignment["rev"], assignment["cluster"], tuple(assignment["copies"]), assignment["origin"], member(p.flash))
        if self.scope != scope:
            self.scope, self.channels, self.token = scope, {}, None
            self.replies = {}
            self.absent_since = None
        if member(p.flash) != assignment["origin"]:
            raise Unconfirmed("this pusher is not the assigned origin")
        items = member_book(p.flash, "domain/rec/primaries", member(p.flash))
        facts = read(items, p.serial)
        main = primary(items, p.serial, assignment["cluster"])
        if main is None:
            self.observe_absence()
        else:
            self.absent_since = None
            p.uncovered = main.value["enabled"] and not main.value["running"]
        routes, observed = {}, set()
        for fact in facts.entries:
            expected = "primary" if fact.member == assignment["cluster"] else \
                "backup" if fact.member in assignment["copies"] else None
            if expected is None or fact.member in facts.missing:
                continue
            value = recording_value(fact.value)
            if value["role"] != expected:
                continue
            observed.add(fact.member)
            if not value.get("ingest"):
                continue
            if fact.member in routes:
                raise Unconfirmed("conflicting push receiver observations")
            routes[fact.member] = {"cluster": value.get("ingest_cluster", fact.member), "urls": value["ingest"],
                                  "role": expected, "push": value.get("push", False)}
        # Missing reports cannot open a channel; a channel already carrying data stays until an explicit change.
        for name, channel in self.channels.items():
            if (name in facts.missing or name not in observed) and channel.pushing is not None:
                routes[name] = channel._route
        return {"channels": routes, "primary": assignment["cluster"]}

    def stream_token(self):
        now = self.clock()
        if self.token is not None and self.deadline - now > 20:
            return self.token
        if self.door is None:
            raise Unconfirmed("the role token door is not configured")
        try:
            reply = self.door.request("stream", self.pusher.serial)
            raw = reply["token"].split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
            lifetime = float(reply["exp"]) - float(claims["iat"])
            if not math.isfinite(lifetime) or lifetime <= 10:
                raise ValueError()
        except (Refused, OSError, ValueError, KeyError, IndexError, TypeError):
            if self.token is not None and self.deadline > now:
                return self.token
            raise Unconfirmed("a current stream token could not be obtained") from None
        # The camera's wall clock may be unset; a relative deadline uses the steady clock.
        self.token, self.deadline = reply["token"], now + lifetime - 10
        return self.token

    def pass_once(self, entry, loose, wait):
        from .ingest import CameraPusher, Refused as StreamRefused
        p = self.pusher
        try:
            token = self.stream_token() if entry["channels"] else None
        except Unconfirmed:
            for channel in self.channels.values():
                if channel.pushing is not None and channel.broken_at is None:
                    channel.broken_at = channel.sent
                channel.pushing = None
            p.pushing = None
            p.state = "waiting for the role token door"
            return {"state": p.state}
        for name in set(self.channels) - entry["channels"].keys():
            self.channels.pop(name)
        result = {"pushed": 0, "uploaded": [], "asks": []}
        states = []
        for name, route in sorted(entry["channels"].items()):
            channel = self.channels.get(name)
            if channel is None:
                channel = CameraPusher(p.serial, p.flash, p.dial, clock=p.clock,
                                       perform=p.perform, hold_seconds=p.hold_seconds, recording=p.recording)
                # The camera owns its card. A held poll must not keep a reader
                # that was removed or replaced while this channel was waiting.
                channel._card_owner = p
                channel.frames, channel.clock = p.frames, p.clock
                channel._moved = len(p.frames.moves())
                if name == entry["primary"]:
                    # The card may have restored a delivery note before the first route appeared.
                    channel.since, channel.delivered = p.since, [list(span) for span in p.delivered]
                    channel.have, channel.foreign_before = p.have, p.foreign_before
                self.channels[name] = channel
            channel.perform, channel.lag_limit = p.perform, p.lag_limit
            channel.ring_seconds = p.ring_seconds
            if "uplink_free" in p.__dict__:
                channel.uplink_free = p.uplink_free
            channel._follow()
            channel._route = route
            channel._channel_entry = {"cluster": route["cluster"], "push": route["push"],
                                      "ingest": {"urls": route["urls"], "token_secret": token}}
            try:
                reply = channel._channel_pass(loose, 0.0 if len(entry["channels"]) > 1 else wait)
            except StreamRefused:
                self.token, self.deadline = None, 0.0
                channel.pushing, channel._card = None, None
                channel.state = "the receiver refused this token; requesting a current token"
                reply = {}
            except OSError:
                if channel.broken_at is None:
                    channel.broken_at = channel.sent
                channel.pushing, channel._card = None, None
                channel.state = "the receiver did not authorize or answer this channel"
                reply = {}
            finally:
                channel.seen = p.frames.newest()
            result["pushed"] += reply.get("pushed", 0)
            result["uploaded"] += reply.get("uploaded", [])
            result["asks"] += reply.get("asks", [])
            self.replies[name] = reply
            states.append(name + ": " + channel.state)
        main = self.channels.get(entry["primary"])
        if main is not None:
            for field in ("sent", "cursor", "since", "delivered", "have", "foreign_before", "continued",
                          "live_from", "broken_at", "resuming", "catching", "_sent_end", "_moved", "resumed",
                          "rtt", "ranges_failed", "failed_ranges", "unplaced_left", "uploading", "_outcomes") :
                setattr(p, field, getattr(main, field))
        p.pushing = next((c.pushing for c in self.channels.values() if c.pushing is not None), None)
        p.lag = any(c.lag for c in self.channels.values())
        # The card also protects frames that this camera's own uplink cannot carry.
        p.uncovered = p.uncovered or bool(main is not None and main.lag)
        p.road = "primary" if main is not None and main.pushing is not None else "backup" if p.pushing else None
        p.state = (next(iter(self.channels.values())).state if len(self.channels) == 1 else
                   "; ".join(states) if states else "waiting for assigned receiver observations")
        return {**self.replies.get(entry["primary"], {}), "state": p.state, **result, "road": p.road,
                "behind": max((c.behind() for c in self.channels.values()), default=0.0), "lagging": p.lag}
