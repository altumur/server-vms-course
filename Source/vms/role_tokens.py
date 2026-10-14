"""An ordinary worker's ephemeral credentials, obtained only from its role door."""
import base64
import json
import math
import threading
import time

from w2cplatform.domain.tokenrequest import Refused, WorkerTokenDoor
from .recording_books import Unconfirmed


class RoleTokens:
    def __init__(self, role, door=None, env=None, clock=None):
        self.door = door or WorkerTokenDoor.from_env(role, env)
        self.clock = clock or time.monotonic
        self.cached = {}
        self._scopes = {}
        self._lock = threading.Lock()

    def get(self, kind, ref, scope, by=None):
        key, now = ((kind, ref, by) if by is not None else (kind, ref)), self.clock()
        with self._lock:
            current = self._scopes.get(key)
            if current is None or current[0] != scope:
                self.cached.pop(key, None)
                current = self._scopes[key] = (scope, object())
            previous = self.cached.get(key)
            if previous and previous[2] - now > 20:
                return previous[1]
        try:
            if self.door is None:
                raise OSError("role door unavailable")
            reply = self.door.request(kind, ref, by) if by is not None else self.door.request(kind, ref)
            token = reply["token"]
            if not isinstance(token, str):
                raise ValueError()
            raw = token.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
            lifetime = float(reply["exp"]) - float(claims["iat"])
            if not math.isfinite(lifetime) or lifetime <= 10:
                raise ValueError()
        except (Refused, OSError, ValueError, KeyError, IndexError, TypeError, OverflowError):
            with self._lock:
                if self._scopes.get(key) is current and previous and previous[2] > self.clock():
                    return previous[1]
            raise Unconfirmed("a current role token could not be obtained") from None
        with self._lock:
            if self._scopes.get(key) is not current or now + lifetime - 10 <= self.clock():
                raise Unconfirmed("the role token request outlived its scope or lifetime")
            # A camera's wall clock may be unset. Only the steady clock advances this deadline.
            self.cached[key] = scope, token, now + lifetime - 10
        return token

    def forget(self, kind, ref, scope=None, by=None):
        with self._lock:
            key = (kind, ref, by) if by is not None else (kind, ref)
            current = self._scopes.get(key)
            if scope is not None and current is not None and current[0] != scope:
                return
            self.cached.pop(key, None)
            self._scopes.pop(key, None)
