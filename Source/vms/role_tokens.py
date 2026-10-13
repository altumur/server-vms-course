"""An ordinary worker's ephemeral credentials, obtained only from its role door."""
import base64
import json
import math
import time

from w2cplatform.domain.tokenrequest import Refused, WorkerTokenDoor
from .recording_books import Unconfirmed


class RoleTokens:
    def __init__(self, role, door=None, env=None, clock=None):
        self.door = door or WorkerTokenDoor.from_env(role, env)
        self.clock = clock or time.monotonic
        self.cached = {}

    def get(self, kind, ref, scope):
        key, now = (kind, ref), self.clock()
        previous = self.cached.get(key)
        if previous and previous[0] != scope:
            previous = None
            self.cached.pop(key, None)
        if previous and previous[2] - now > 20:
            return previous[1]
        try:
            if self.door is None:
                raise OSError("role door unavailable")
            reply = self.door.request(kind, ref)
            raw = reply["token"].split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
            lifetime = float(reply["exp"]) - float(claims["iat"])
            if not math.isfinite(lifetime) or lifetime <= 10:
                raise ValueError()
        except (Refused, OSError, ValueError, KeyError, IndexError, TypeError):
            if previous and previous[2] > now:
                return previous[1]
            raise Unconfirmed("a current role token could not be obtained") from None
        self.cached[key] = scope, reply["token"], now + lifetime - 10
        return reply["token"]

    def forget(self, kind, ref):
        self.cached.pop((kind, ref), None)
