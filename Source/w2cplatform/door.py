"""The holder's door for a browser: a token the console signs, and the holder checks.

THE BYTES DO NOT GO THROUGH THE CONSOLE (the boundary's step 6, the owner's decision 1; ГРАНИЦА-ПЛАТФОРМЫ-И-ПОДСИСТЕМЫ.md
§6.1). What a unit's holder serves to a page — its pieces, its stream — goes from the holder to the browser, and the
console only says where and lets in: `GET /where/<id>` answers `door: {url, token, expires, routes}`, for the routes
the subsystem's spec declares (`door: {routes: [...]}`), and only to whoever may `view` that unit. `url` is what the
holder says in its heartbeat (`url`); the page goes to `<url>/<route>/<id>` itself, with the token.

    token       `door1.<kid>.<payload>.<signature>` — base64url; the payload `{sub, unit, holder, routes, exp}`: who it was
                given to, which unit (`<sub>/<id>`), which holder, which routes, until when. Ed25519: the console
                SIGNS and the holder only CHECKS — no holder holds what issues a token (§1.8: delegate an authority,
                never hand out a secret)
    lifetime    `TTL`, 120 s, and `SKEW` for two clocks; the page asks `/where` again before `expires`. Needed to OPEN:
                each GET, each offer; a stream already open lives by its own id. A unit moved is another holder, and
                the old token is not its: `/where` gives a new one
    keys        in the STORE, as the product keeps them: `door/signer` — the console's seed `{kid, seed}`, the seed sealed
                with the cluster's key ring (`SECRETS_KEY`) and read by the console alone — and `door/keys`, the public
                halves by key id, which every holder reads. The console makes a key the first time it is asked for a
                door (`Signer.current`), the public half first; `python3 -m w2cplatform.door new` rotates (a new key
                signs; the old half stays in the ring for the tokens it signed)
    transport   `Authorization: Bearer <token>` wherever a header can be set; `?t=<token>` where it cannot (a media element's
                `src`). A query's token is masked wherever a path is logged (`masked`)
    refusal     401 `{error, reason}` with `WWW-Authenticate`: `reason` one word a page acts on — `token` (none), `signature`,
                `expired`, `holder`, `unit`, `route` — and the page asks `/where` again and retries once
    CORS        `Access-Control-Allow-Origin` only for the consoles' origins (`DOOR_ORIGINS`, the deployment's — not a
                spec's); `Expose-Headers: Location` for an offer's session; no `Allow-Credentials`: a cookie never
                goes to a holder. Nothing is written through the door: it is read-only, but for opening a stream

NO KEY IS A MODE, AND IT SAYS SO — as the console without a key set is open (`access.py`). A console with no key ring to
seal a door key with keeps none and hands out the door with no token; a holder whose ring row is empty opens to anybody
who reaches it, and says so once in its log.

The platform's part is all of that — the issue, the keys, the check, the headers. What a route SERVES is the
subsystem's: its holder calls `DoorKeeper.admit(handler, route, unit)` and then answers as it answers.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import secrets as _secrets
import threading
import time
from urllib.parse import parse_qs, urlsplit

log = logging.getLogger("w2cplatform.door")

TTL = 120.0                     # seconds a token opens a door for: the page asks again before it ends
SKEW = 5.0                      # how far apart the console's clock and the holder's may be
VERSION = "door1"               # the token's kind and its version (the product's `door1.`): another kind of token never reads as one
SIGNER_KEY = "door/signer"      # the console's seed, sealed: `{kid, seed}` (the product's `DoorSignerKey`)
KEYS_KEY = "door/keys"          # the public halves by kid: `{<kid>: <hex>}` (the product's `DoorKeysKey`)
SIGNER_REREAD = 30.0            # seconds a console signs with the key it read before it reads the store again
RING_KEEP, RING_AGAIN = 30.0, 1.0   # a door keeps the ring it read; an unknown kid reads it again, at most once a second
_ROUTE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")   # a route of a door is one path segment, a word


class DoorRefused(Exception):
    """A token a holder does not take: `reason` (one word a page acts on) and `why`, in words. Always a 401."""

    def __init__(self, reason: str, why: str):
        super().__init__(why)
        self.reason, self.why, self.status = reason, why, 401


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def parse_routes(where: str, raw) -> tuple:
    """The spec's `door: {routes: [<route>]}` — each a word, one path segment."""
    if raw is None:
        return ()
    routes = raw.get("routes") if isinstance(raw, dict) and not set(raw) - {"routes"} else None
    if not isinstance(routes, list) or not routes or not all(isinstance(r, str) and _ROUTE.match(r) for r in routes):
        raise ValueError(f"{where}: `door:` is {{routes: [<a word, one path segment>]}}, not {raw!r}")
    # …each once (ADR-0012; the fifteenth review, minor 16: `[read, read]` loaded — the product refuses it)
    twice = next((r for i, r in enumerate(routes) if r in routes[:i]), None)
    if twice is not None:
        raise ValueError(f"{where}: door.routes: {twice!r} is said twice — a route is named once")
    return tuple(routes)


def _kid_of(pub: bytes) -> str:
    return "k" + hashlib.sha256(pub).hexdigest()[:12]   # from the public half: two consoles at once never name two alike


def _public(seed: bytes) -> bytes:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(serialization.Encoding.Raw,
                                                                               serialization.PublicFormat.Raw)


# The public half into the ring, by CAS: two consoles adding at once both end up in it.
def _publish(vars_, kid: str, pub: bytes) -> None:
    from .variables import Conflict
    for _ in range(8):
        items, idx = vars_.get(KEYS_KEY)
        items = dict(items or {})
        if items.get(kid) == pub.hex():
            return
        items[kid] = pub.hex()
        try:
            vars_.put(KEYS_KEY, items, cas=idx)
            return
        except Conflict:
            continue
    raise RuntimeError(f"{KEYS_KEY}: the ring kept changing under this write")


# A key pair put in place: the public half into the ring FIRST — a token is never signed by a key no door can know —
# then the seed, sealed, over the signer row as it was read (`cas`). Raises `Conflict` when another console made one.
def _new_key(vars_, sealer, cas) -> tuple[str, bytes]:
    seed = _secrets.token_bytes(32)
    pub = _public(seed)
    kid = _kid_of(pub)
    _publish(vars_, kid, pub)
    vars_.put(SIGNER_KEY, {"kid": kid, "seed": sealer.seal("seed", seed.hex(), SIGNER_KEY)}, cas=cas)
    return kid, seed


class Signer:
    """The console's half: signs a token with the key in `door/signer` — read from the store, made there when there is
    none, read again every `SIGNER_REREAD` (another console may have rotated it). `for_console` is None without a key
    ring to seal with: the open mode."""

    def __init__(self, vars_, sealer, clock=time.monotonic):
        self.vars, self.sealer, self.clock = vars_, sealer, clock
        self._kid, self._seed, self._read_at = None, None, -1e18
        self._lock = threading.Lock()

    @classmethod
    def for_console(cls, vars_, sealer) -> "Signer | None":
        return cls(vars_, sealer) if sealer is not None and vars_ is not None else None

    def current(self) -> tuple[str, bytes]:
        from .variables import Conflict
        with self._lock:
            if self._seed is not None and self.clock() - self._read_at < SIGNER_REREAD:
                return self._kid, self._seed
            try:
                for _ in range(3):
                    items, idx = self.vars.get(SIGNER_KEY)
                    if not items or not items.get("seed"):
                        try:
                            kid, seed = _new_key(self.vars, self.sealer, idx)
                        except Conflict:
                            continue                     # another console made one at the same moment: take theirs
                    else:
                        seed = bytes.fromhex(self.sealer.open("seed", str(items["seed"]), SIGNER_KEY))
                        kid = str(items.get("kid") or "")
                        if len(seed) != 32 or not kid:
                            raise ValueError(f"the door key in {SIGNER_KEY} is not one")
                        _publish(self.vars, kid, _public(seed))   # a ring that lost it gets it back
                    self._kid, self._seed, self._read_at = kid, seed, self.clock()
                    return kid, seed
                raise RuntimeError(f"{SIGNER_KEY}: the key kept changing under this read")
            except OSError:
                if self._seed is not None:               # the store did not answer: the key read last stays good
                    return self._kid, self._seed
                raise

    def issue(self, user: str, unit: str, holder: str, routes, now: float, ttl: float = TTL) -> tuple[str, float]:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        kid, seed = self.current()
        exp = now + ttl
        body = json.dumps({"sub": user, "unit": unit, "holder": holder, "routes": list(routes), "exp": exp},
                          separators=(",", ":"), sort_keys=True).encode()
        head = f"{VERSION}.{kid}.{_b64(body)}"
        return f"{head}.{_b64(Ed25519PrivateKey.from_private_bytes(seed).sign(head.encode()))}", exp


# A new key signs from now on (every console within `SIGNER_REREAD`); the old public half stays in the ring for the
# tokens it signed. `python3 -m w2cplatform.door new`.
def rotate(vars_, sealer) -> str:
    _, idx = vars_.get(SIGNER_KEY)
    return _new_key(vars_, sealer, idx)[0]


class Ring:
    """The holder's half: the public keys in `door/keys`, kept `RING_KEEP` and read again — at most once a second — when
    a token names a kid it does not know (a rotation it has not seen). Empty: the open mode."""

    def __init__(self, vars_, clock=time.monotonic):
        self.vars, self.clock = vars_, clock
        self._keys: dict | None = None
        self._read_at, self._forced_at = -1e18, -1e18
        self._lock = threading.Lock()

    def keys(self, fresh: bool = False) -> dict:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        with self._lock:
            now = self.clock()
            if self._keys is not None and (not fresh and now - self._read_at < RING_KEEP
                                           or fresh and now - self._forced_at < RING_AGAIN):
                return self._keys
            if fresh:
                self._forced_at = now
            try:
                items, _ = self.vars.get(KEYS_KEY)
            except OSError:
                if self._keys is not None:
                    return self._keys
                raise
            keys = {}
            for kid, h in (items or {}).items():
                try:
                    raw = bytes.fromhex(str(h))
                    if len(raw) == 32:
                        keys[str(kid)] = Ed25519PublicKey.from_public_bytes(raw)
                except ValueError:
                    continue
            self._keys, self._read_at = keys, now
            return keys

    def check(self, token: str | None, *, unit: str, holder: str, route: str, now: float) -> dict:
        """The payload of a token that opens THIS door — this holder, this unit, this route, not past its time — or
        `DoorRefused`."""
        from cryptography.exceptions import InvalidSignature
        if not token:
            raise DoorRefused("token", "this door opens with a token the console gives with the unit's place "
                                       "(`GET /where/<id>`): `Authorization: Bearer <token>`, or `?t=` where no header goes")
        parts = token.split(".")
        if len(parts) != 4 or parts[0] != VERSION:
            raise DoorRefused("signature", "not a door token")
        key = self.keys().get(parts[1]) or self.keys(fresh=True).get(parts[1])
        if key is None:
            raise DoorRefused("signature", "the token is signed by a key this cluster does not know: ask /where again")
        try:
            key.verify(_unb64(parts[3]), f"{parts[0]}.{parts[1]}.{parts[2]}".encode())
            payload = json.loads(_unb64(parts[2]))
        except (InvalidSignature, ValueError, TypeError):
            raise DoorRefused("signature", "bad signature: this is not a token this cluster's console made") from None
        if not isinstance(payload, dict):
            raise DoorRefused("signature", "not a door token")
        try:
            exp = float(payload.get("exp"))
        except (TypeError, ValueError):
            raise DoorRefused("expired", "a door token with no time it ends") from None
        if not exp + SKEW > now:                         # `nan` ends never: refused as ended
            raise DoorRefused("expired", f"the token expired {now - exp:.0f} s ago: ask /where again")
        if payload.get("holder") != holder:
            raise DoorRefused("holder", f"the token is for holder {payload.get('holder')!r} and this door is {holder!r}'s: "
                                        f"the unit is elsewhere — ask /where again")
        if route not in (payload.get("routes") or []):
            raise DoorRefused("route", f"the token does not open {route!r}")
        if payload.get("unit") != unit:
            raise DoorRefused("unit", f"the token is for {payload.get('unit')}, not {unit}")
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
            ("Access-Control-Expose-Headers", "Location, Content-Range, Content-Length, X-Unreachable"),
            ("Access-Control-Max-Age", "600")]


class DoorKeeper:
    """What a holder's door asks of every request on a route the spec declares: `admit(handler, route, unit)` — the
    token's payload (or `{}` in the open mode), or None with the refusal already answered. `preflight(handler)`
    answers a browser's `OPTIONS`. `headers(handler)` — the CORS headers to add to the answer. The ring is the store's
    `door/keys`, read through the holder's own store handle."""

    def __init__(self, holder: str, wall, vars_=None, ring: "Ring | None" = None, allowed: tuple | None = None, env=None):
        self.holder, self.wall = holder, wall
        self.ring = ring if ring is not None else (Ring(vars_) if vars_ is not None else None)
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

    def _open(self) -> bool:
        try:
            return self.ring is None or not self.ring.keys()
        except OSError:
            return False                                 # not known: shut, and the check below says why

    def admit(self, handler, route: str, unit: str) -> dict | None:
        if self._open():
            with self._lock:
                if not self._said:
                    self._said = True
                    log.warning("%s: this door is OPEN — no door key in the store (%s), so whoever reaches it is let in",
                                self.holder, KEYS_KEY)
            return {}
        try:
            return self.ring.check(token_in(handler.headers, handler.path), unit=unit, holder=self.holder,
                                   route=route, now=self.wall())
        except (DoorRefused, OSError) as e:
            refusal = e if isinstance(e, DoorRefused) else DoorRefused("signature", f"the door keys could not be read: {e}")
            log.info("%s: door refused %s: %s", self.holder, masked(handler.path), refusal.why)
            data = json.dumps({"error": "door token: " + refusal.why, "reason": refusal.reason}).encode()
            handler.send_response(401)
            for k, v in self.headers(handler):
                handler.send_header(k, v)
            # A header is Latin-1 on the wire: the reason in plain ASCII there, whole in the JSON body.
            desc = refusal.why.replace("—", "-").replace('"', "'").replace("\\", "/").encode("ascii", "replace").decode()
            handler.send_header("WWW-Authenticate", f'Bearer error="invalid_token", error_description="{desc}"')
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(data)))
            handler.end_headers()
            handler.wfile.write(data)
            return None


# `python3 -m w2cplatform.door new` — a new door key in this cluster's store (`PLATFORM_STORE`, `SECRETS_KEY`): it signs
# from now on, the old public half stays in the ring for the tokens it signed. A console makes the first one itself.
def _new(env=None) -> int:
    from . import host
    from .sealing import Sealer
    env = dict(os.environ if env is None else env)
    sealer = Sealer.from_env(env)
    if sealer is None:
        print("a door key is sealed with the cluster's key ring: SECRETS_KEY is not set", flush=True)
        return 2
    vars_, _ = host.stores(env)
    print(f"{rotate(vars_, sealer)} signs from now on ({SIGNER_KEY}; its public half in {KEYS_KEY})")
    return 0


if __name__ == "__main__":
    import sys
    if sys.argv[1:] != ["new"]:
        sys.exit("usage: python3 -m w2cplatform.door new")
    sys.exit(_new())
