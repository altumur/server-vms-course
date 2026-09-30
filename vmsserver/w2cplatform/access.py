"""Who is calling a cluster's console, and may they: the gate, and nothing of the cryptography behind it."""
# ================================================================================================
# # access.py — the console's gate
#
# Until now whoever reached a console was an administrator, under whatever name they put in `X-User` (the
# platform review, blocker 1; the order agreed with the product, feedback BP — this is its step 3).
#
# THE PLATFORM DOES NOT KNOW HOW A PERSON IS PROVED. That is the domain's (М12, Lesson 4): users live with the
# domain's holder, a short token names a subject and nothing else, and what the subject may do is a table in
# THIS cluster's own store, carried there by the domain's agent. The platform knows three things:
#
#   when to ask     when this cluster's store holds a key set (`domain/keys`). A cluster nobody has joined to
#                   a domain has none, and its console is as open as it always was — and says so in its log.
#                   М10A and М10B are read and run without М12; one box is not made to carry a signer
#   what to ask     `Access`: `who(token)` — the token's payload, or a refusal — and `may(payload, capability,
#                   unit, labels)`. Whoever can verify a token implements it; `ACCESS_IMPL` names it
#                   (`domain.access:cluster_access`), and it is imported only when there are keys to check by
#   what a route    `view` to read, `edit` to act (a command, a mark, a keep), `admin` to change what the
#   needs           cluster is (units, volumes, policy)
#
# AND IT FAILS SHUT. A key set in the store and no way to verify a token — the implementation is not
# installed, the store does not answer — is 503 for every request, not an open console: "I cannot check" is
# not "there is nothing to check".
#
# With the gate on, `X-User` from outside is thrown away and replaced by the name the token proved. Every line
# a console writes about who did what — `unit.deleted`, `archive.read`, a keep — then names somebody who was
# checked, not somebody who introduced themselves.
#
# What this does NOT close, and it is said in `М10B_ServerVMS/module-design.md`: the doors BEHIND the console —
# the resource, a recorder's archive door — still ask nobody. That is mutual TLS between processes, the next
# step, and until it a cluster of several machines stands behind its network.
# ================================================================================================
from __future__ import annotations

import importlib
import logging
import os
from typing import Protocol

TRUST_KEYS = "domain/keys"            # where a domain's agent puts the key set in a cluster's store (М12)
RANK = {"view": 0, "edit": 1, "admin": 2}
OPEN_ROUTES = ("/", "/index.html", "/metrics", "/healthz", "/session")   # the page, what monitoring reads, and the door in
COOKIE = "w2c_token"
GLASS_COOKIE = "w2c_glass"            # an emergency session: this console's own, in its memory, never a token
log = logging.getLogger("w2cplatform.access")


class Denied(Exception):
    """401: nobody proved who they are. 403: they did, and may not. 503: this console cannot check."""

    def __init__(self, status: int, why: str):
        super().__init__(why)
        self.status, self.why = status, why


class Access(Protocol):
    def who(self, token: str) -> dict: ...                       # the token's payload (`sub`, …), or `Denied(401)`
    def may(self, payload: dict, capability: str, unit: str | None, labels: list) -> bool: ...


# `Authorization: Bearer …`, or the cookie a browser carries (`w2c_token`, set `HttpOnly` by whoever logged
# the person in — a page's script never sees it).
def token_of(headers) -> str | None:
    auth = headers.get("Authorization", "") or ""
    if auth.startswith("Bearer "):
        return auth[7:].strip() or None
    for part in (headers.get("Cookie", "") or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE and v:
            return v
    return None


def from_cookie(headers) -> bool:
    return not (headers.get("Authorization", "") or "").startswith("Bearer ") and token_of(headers) is not None


# A browser sends the cookie with every request to this console — including one a page on ANOTHER site made
# it send. `SameSite=Strict` is what stops that; this is the second lock, for the browser that does not honour
# it: a request that ACTS, carries its proof in the cookie and names an `Origin` that is not this console is
# refused. A caller with a bearer token is not a browser being steered and is not asked.
def cross_site(headers) -> bool:
    from urllib.parse import urlsplit
    origin = headers.get("Origin", "") or ""
    return bool(origin) and urlsplit(origin).netloc != (headers.get("Host", "") or "")


# The cookie a console sets when somebody hands it a token it has checked (`POST /session`). `HttpOnly`: a
# page's script never reads it back — a script injected into the page cannot carry the token away. It lives
# exactly as long as the token does.
def session_cookie(token: str, seconds: float, secure: bool = False) -> str:
    return (f"{COOKIE}={token}; Path=/; Max-Age={max(0, int(seconds))}; HttpOnly; SameSite=Strict"
            + ("; Secure" if secure else ""))


def cookie(headers, name: str) -> str | None:
    for part in (headers.get("Cookie", "") or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == name and v:
            return v
    return None


class Gate:
    """One console's gate. `impl` pins an `Access` (tests, or a process that builds its own); without it the
    gate looks in the cluster's store on every request — a cluster may join a domain while a console runs."""

    # EMERGENCY SESSIONS (М12 Lesson 4, step 7; the product's question 7). The holder is away, the agent cannot
    # renew, the operator's token ran out an hour ago, and somebody has to get in. The one local account: its
    # password's HASH is carried into this cluster's store by the agent, the check is local, and what it opens is
    # a session held in THIS process's memory — no token, so nothing to steal from the store and nothing that
    # outlives the console. Shared by every console of the process (a mount's gate is another object).
    _glass: dict = {}

    def __init__(self, vars_, wall, journal=None, impl: Access | None = None):
        self.vars, self.wall, self.journal, self.impl = vars_, wall, journal, impl
        self._said_open = False
        self._loaded: Access | None = None

    def access(self) -> Access | None:
        if self.impl is not None:
            return self.impl
        try:
            items, _ = self.vars.get(TRUST_KEYS)
        except OSError as e:
            raise Denied(503, f"this console cannot read the cluster's trust ({e}): it admits nobody until it can") from None
        if not items:
            if not self._said_open:
                self._said_open = True
                log.warning("this console is OPEN: the cluster's store holds no key set (%s), so nobody is asked who "
                            "they are and whoever reaches it is an administrator under any name", TRUST_KEYS)
            return None
        if self._loaded is None:
            name = os.environ.get("ACCESS_IMPL", "domain.access:cluster_access")
            try:
                module, _, fn = name.partition(":")
                self._loaded = getattr(importlib.import_module(module), fn)(self.vars, self.wall)
            except Exception as e:                       # noqa: BLE001 — not installed, or broken: shut either way
                raise Denied(503, f"this cluster is in a domain (its store holds a key set) and this console cannot "
                                  f"verify a token ({name}: {e}): it admits nobody") from None
        return self._loaded

    # The caller's payload: from a token, or from an emergency session of this process. `Denied` if neither.
    def payload(self, headers, access: Access) -> dict:
        sid = cookie(headers, GLASS_COOKIE)
        if sid:
            held = self._glass.get(sid)
            if held is not None and float(held.get("exp", 0)) > self.wall():
                return held
            self._glass.pop(sid, None)
        token = token_of(headers)
        if not token:
            raise Denied(401, "this console asks who is calling: send the domain's token (Authorization: Bearer …)")
        return access.who(token)

    # Open an emergency session: `(session id, payload)`. Every attempt is an alarm, the refused ones too — the
    # account exists to be used rarely and seen always.
    def open_glass(self, who: str, why: str, password: str) -> tuple[str, dict]:
        import secrets
        from .events import ALARM
        access = self.access()
        if access is None:
            raise Denied(400, "this console is open: there is nothing to break into")
        if not who.strip() or not why.strip():
            raise Denied(400, "an emergency entry says who is entering and why")
        if not hasattr(access, "glass"):
            raise Denied(501, "this cluster's access has no emergency account")
        try:
            payload = access.glass(who, why, password)
        except Denied:
            if self.journal is not None:
                self.journal().say("access.break_glass.refused", cls=ALARM, user=f"break-glass({who})", why=why)
            raise
        sid = secrets.token_urlsafe(24)
        self._glass[sid] = payload
        if self.journal is not None:
            self.journal().say("access.break_glass.opened", cls=ALARM, user=f"break-glass({who})", why=why, until=payload.get("exp"))
        return sid, payload

    def close_glass(self, headers) -> None:
        self._glass.pop(cookie(headers, GLASS_COOKIE) or "", None)

    # The name to act under — or `Denied`. With no key set: whatever `X-User` says, as before.
    def admit(self, headers, capability: str, unit: str | None = None, labels: list | None = None) -> str:
        access = self.access()
        if access is None:
            return headers.get("X-User", "operator")
        if capability != "view" and (from_cookie(headers) or cookie(headers, GLASS_COOKIE)) and cross_site(headers):
            raise Denied(403, "a request that acts came from another site's page: refused")
        payload = self.payload(headers, access)
        name = str(payload.get("sub", ""))
        if payload.get("via") == "break-glass":          # the one local account (М12 Lesson 4): every use is an alarm
            name = f"break-glass({payload.get('who', '?')})"
            if self.journal is not None:
                from .events import ALARM
                self.journal().say("access.break_glass", cls=ALARM, user=name, capability=capability, **({"target": unit} if unit else {}))
        if not access.may(payload, capability, unit, list(labels or [])):
            if self.journal is not None:
                self.journal().say("access.denied", user=name, capability=capability, **({"target": unit} if unit else {}))
            raise Denied(403, f"{name} may not {capability}" + (f" {unit}" if unit else " here"))
        del headers["X-User"]                            # whatever the caller called themselves
        headers["X-User"] = name                         # …is replaced by what the token proved
        return name
