"""The holder's door for a browser: a token the console signs, and the holder checks.

THE BYTES DO NOT GO THROUGH THE CONSOLE (the boundary's step 6, the owner's decision 1; ГРАНИЦА-ПЛАТФОРМЫ-И-ПОДСИСТЕМЫ.md
§6.1). What a unit's holder serves to a page — its pieces, its stream — goes from the holder to the browser, and the
console only says where and lets in: `GET /where/<id>` answers `door: {url, token, expires, routes}`, for the routes
the subsystem's spec declares (`door: {routes: [...]}`), and only to whoever may `view` that unit. The page goes to
`url` itself, with the token.

    token       `v1.<kid>.<payload>.<signature>` — base64url; the payload `{sub, unit, holder, routes, exp}`: who it was
                given to, which unit (`<sub>/<id>`), which holder, which routes, until when. Ed25519: the console
                SIGNS and the holder only CHECKS — no holder holds what issues a token (§1.8: delegate an authority,
                never hand out a secret)
    lifetime    `TTL`, 120 s; the page asks `/where` again before `expires`. Needed to OPEN: each GET, each offer; a
                stream already open lives by its own id. A unit moved is another holder, and the old token is not
                its: `/where` gives a new one
    keys        a FILE, as the sealing key is (`sealing.py`): `DOOR_KEY=<path>` for the consoles — lines `<kid> <64 hex
                digits of an Ed25519 seed>`, the first the current one — and `DOOR_RING=<path>` for the holders —
                lines `<kid> <64 hex digits of the public key>`. Rotating is a line on top of both
    transport   `Authorization: Bearer <token>` wherever a header can be set; `?t=<token>` where it cannot (a media element's
                `src`). A query's token is masked wherever a path is logged (`masked`)
    CORS        `Access-Control-Allow-Origin` only for the consoles' origins (`DOOR_ORIGINS`, the deployment's — not a
                spec's); `Expose-Headers: Location` for an offer's session; no `Allow-Credentials`: a cookie never
                goes to a holder. Nothing is written through the door: it is read-only, but for opening a stream

NO KEY IS A MODE, AND IT SAYS SO — as the console without a key set is open (`access.py`). A console without
`DOOR_KEY` hands out the door with no token; a holder without `DOOR_RING` opens to anybody who reaches it, and says so
once in its log. A holder WITH a ring and a request without a token, or with one it does not take: 401 or 403, in
words, and nothing served.

The platform's part is all of that — the issue, the keys, the check, the headers. What a route SERVES is the
subsystem's: its holder calls `DoorKeeper.admit(handler, route, unit)` and then answers as it answers.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import threading
from urllib.parse import parse_qs, urlsplit

log = logging.getLogger("w2cplatform.door")

TTL = 120.0                     # seconds a token opens a door for: the page asks again before it ends
VERSION = "v1"
_ROUTE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")   # a route of a door is one path segment, a word


class DoorRefused(Exception):
    """A token a holder does not take: `status` (401 none, 403 not this door's) and `why`, in words."""

    def __init__(self, status: int, why: str):
        super().__init__(why)
        self.status, self.why = status, why


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _lines(path: str) -> list[tuple[str, bytes]]:
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            kid, hexkey = line.split()
            raw = bytes.fromhex(hexkey)
            if len(raw) != 32 or not _ROUTE.match(kid.lower()):
                raise ValueError(f"{path}: a line is `<kid> <64 hex digits>`, not {line[:20]!r}…")
            out.append((kid, raw))
    if not out:
        raise ValueError(f"{path} holds no key")
    return out


def parse_routes(where: str, raw) -> tuple:
    """The spec's `door: {routes: [<route>]}` — each a word, one path segment."""
    if raw is None:
        return ()
    routes = raw.get("routes") if isinstance(raw, dict) and not set(raw) - {"routes"} else None
    if not isinstance(routes, list) or not routes or not all(isinstance(r, str) and _ROUTE.match(r) for r in routes):
        raise ValueError(f"{where}: `door:` is {{routes: [<a word, one path segment>]}}, not {raw!r}")
    return tuple(routes)


class Signer:
    """The console's half: signs a token. From `DOOR_KEY`; None without it (the open mode)."""

    def __init__(self, keys: list[tuple[str, bytes]]):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        self.kid, seed = keys[0]
        self._key = Ed25519PrivateKey.from_private_bytes(seed)

    @classmethod
    def from_env(cls, env=None) -> "Signer | None":
        path = (os.environ if env is None else env).get("DOOR_KEY", "")
        return cls(_lines(path)) if path else None

    def public_line(self) -> str:
        """`<kid> <hex>` — the line of `DOOR_RING` this key is checked by."""
        from cryptography.hazmat.primitives import serialization
        raw = self._key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return f"{self.kid} {raw.hex()}"

    def issue(self, user: str, unit: str, holder: str, routes, now: float, ttl: float = TTL) -> tuple[str, float]:
        exp = now + ttl
        body = json.dumps({"sub": user, "unit": unit, "holder": holder, "routes": list(routes), "exp": exp},
                          separators=(",", ":"), sort_keys=True).encode()
        head = f"{VERSION}.{self.kid}.{_b64(body)}"
        return f"{head}.{_b64(self._key.sign(head.encode()))}", exp


class Ring:
    """The holder's half: the public keys it checks a token by. From `DOOR_RING`; None without it (the open mode)."""

    def __init__(self, keys: list[tuple[str, bytes]]):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        self._keys = {kid: Ed25519PublicKey.from_public_bytes(raw) for kid, raw in keys}

    @classmethod
    def from_env(cls, env=None) -> "Ring | None":
        path = (os.environ if env is None else env).get("DOOR_RING", "")
        return cls(_lines(path)) if path else None

    def check(self, token: str | None, *, unit: str, holder: str, route: str, now: float) -> dict:
        """The payload of a token that opens THIS door — this holder, this unit, this route, not past its time — or
        `DoorRefused`."""
        from cryptography.exceptions import InvalidSignature
        if not token:
            raise DoorRefused(401, "this door opens with a token the console gives with the unit's place "
                                   "(`GET /where/<id>`): `Authorization: Bearer <token>`, or `?t=` where no header goes")
        parts = token.split(".")
        if len(parts) != 4 or parts[0] != VERSION:
            raise DoorRefused(401, "not a door token")
        key = self._keys.get(parts[1])
        if key is None:
            raise DoorRefused(401, f"a token signed by key {parts[1][:16]!r}, which this holder does not know (DOOR_RING)")
        try:
            key.verify(_unb64(parts[3]), f"{parts[0]}.{parts[1]}.{parts[2]}".encode())
            payload = json.loads(_unb64(parts[2]))
        except (InvalidSignature, ValueError, TypeError):
            raise DoorRefused(401, "a door token whose signature does not hold") from None
        if not isinstance(payload, dict):
            raise DoorRefused(401, "not a door token")
        try:
            exp = float(payload.get("exp"))
        except (TypeError, ValueError):
            raise DoorRefused(401, "a door token with no time it ends") from None
        if not exp > now:                                # `nan` ends never: refused as ended
            raise DoorRefused(401, "the door token has ended: ask `/where` for another")
        if payload.get("holder") != holder:
            raise DoorRefused(403, f"the token opens the door of {payload.get('holder')!r}, not of {holder!r}: the unit "
                                   f"moved — ask `/where` again")
        if payload.get("unit") != unit:
            raise DoorRefused(403, f"the token opens {payload.get('unit')!r}, not {unit!r}")
        if route not in (payload.get("routes") or []):
            raise DoorRefused(403, f"the token does not open {route!r}")
        return payload


def token_in(headers, path: str) -> str | None:
    """The token a request carries: `Authorization: Bearer`, or `?t=`."""
    auth = str((headers or {}).get("Authorization", "") or "")
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip() or None
    got = parse_qs(urlsplit(path).query).get("t")
    return got[0] if got else None


_T = re.compile(r"([?&]t=)[^&#]*")


def masked(path: str) -> str:
    """A path as a log may say it: a token in the query is `***`, as a secret in an address is."""
    return _T.sub(r"\1***", path)


def origins(env=None) -> tuple:
    """The consoles' origins a page may come from (`DOOR_ORIGINS`, comma-separated): the deployment's word."""
    raw = (os.environ if env is None else env).get("DOOR_ORIGINS", "")
    return tuple(o.strip().rstrip("/") for o in raw.split(",") if o.strip())


def cors(origin: str | None, allowed: tuple) -> list[tuple[str, str]]:
    """The headers a door answers a page from `origin` with — none for an origin that is not a console's."""
    if not origin or origin.rstrip("/") not in allowed:
        return []
    return [("Access-Control-Allow-Origin", origin), ("Vary", "Origin"),
            ("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS"),
            ("Access-Control-Allow-Headers", "Authorization, Content-Type, Range"),
            ("Access-Control-Expose-Headers", "Location, Content-Range, Content-Length"),
            ("Access-Control-Max-Age", "600")]


class DoorKeeper:
    """What a holder's door asks of every request on a route the spec declares: `admit(handler, route, unit)` — the
    token's payload (or `{}` in the open mode), or None with the refusal already answered. `preflight(handler)`
    answers a browser's `OPTIONS`. `headers(handler)` — the CORS headers to add to the answer."""

    def __init__(self, holder: str, wall, ring: "Ring | None" = None, allowed: tuple | None = None, env=None):
        self.holder, self.wall = holder, wall
        self.ring = ring if ring is not None else Ring.from_env(env)
        self.allowed = allowed if allowed is not None else origins(env)
        self._said = False
        self._lock = threading.Lock()

    def headers(self, handler) -> list[tuple[str, str]]:
        return cors((getattr(handler, "headers", None) or {}).get("Origin"), self.allowed)

    def preflight(self, handler) -> None:
        handler.send_response(204)
        for k, v in self.headers(handler):
            handler.send_header(k, v)
        handler.send_header("Content-Length", "0")
        handler.end_headers()

    def admit(self, handler, route: str, unit: str) -> dict | None:
        if self.ring is None:
            with self._lock:
                if not self._said:
                    self._said = True
                    log.warning("%s: this door is OPEN — no DOOR_RING, so whoever reaches it is let in", self.holder)
            return {}
        try:
            return self.ring.check(token_in(handler.headers, handler.path), unit=unit, holder=self.holder,
                                   route=route, now=self.wall())
        except DoorRefused as e:
            log.info("%s: door refused %s: %s", self.holder, masked(handler.path), e.why)
            data = json.dumps({"error": "denied", "detail": e.why}).encode()
            handler.send_response(e.status)
            for k, v in self.headers(handler):
                handler.send_header(k, v)
            if e.status == 401:
                handler.send_header("WWW-Authenticate", 'Bearer realm="door"')
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(data)))
            handler.end_headers()
            handler.wfile.write(data)
            return None


# `python3 -m w2cplatform.door new <dir>` — a key pair as the deployment gives it: `<dir>/door.key` (0600, the consoles'
# `DOOR_KEY`) and `<dir>/door.ring` (0644, the holders' `DOOR_RING`). Rotating is a line on top of both.
def _new(directory: str) -> None:
    import secrets as _secrets
    kid = "k" + _secrets.token_hex(4)
    seed = _secrets.token_bytes(32)
    line = Signer([(kid, seed)]).public_line()
    key, ring = os.path.join(directory, "door.key"), os.path.join(directory, "door.ring")
    fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"{kid} {seed.hex()}\n")
    with open(ring, "w") as f:
        f.write(line + "\n")
    os.chmod(ring, 0o644)
    print(f"{key} (DOOR_KEY, the consoles')\n{ring} (DOOR_RING, the holders')")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3 or sys.argv[1] != "new":
        sys.exit("usage: python3 -m w2cplatform.door new <dir>")
    _new(sys.argv[2])
