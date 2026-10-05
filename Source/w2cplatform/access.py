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
# a console writes about who did what — `unit.deleted`, `door.issued`, a row of a table — then names somebody who was
# checked, not somebody who introduced themselves.
#
# What this does NOT close, and it is said in `М10B_ServerVMS/module-design.md`: the doors BEHIND the console —
# the resource, a holder's door between processes — still ask nobody. That is mutual TLS between processes, the next
# step, and until it a cluster of several machines stands behind its network.
# ================================================================================================
from __future__ import annotations

import importlib
import logging
import os
import threading
import time
from typing import Protocol

TRUST_KEYS = "domain/keys"            # where a domain's agent puts the key set in a cluster's store (М12)
# What says THIS CLUSTER IS IN A DOMAIN when the key set is not there to say it (the review's third pass, Н-M2): rows
# only the domain's agent writes, and only into a member — the root it pinned (М12 Lesson 15, written once, never
# replaced), the grants, the revocation list, the emergency account's hash. Any of them and no key set is a cluster
# that lost its keys — deleted, or the row rolled back from a backup — not one that never had any: shut, and it stays
# shut across a restart of the console, which a flag in one process's memory did not. `domain/primaries` is not one
# of them: the recorder writes it in a cluster of its own.
DOMAIN_MARKS = ("domain/member", "domain/root", "domain/grants", "domain/revoked", "domain/break_glass")   # `domain/member`: written by the agent on every pass that leaves keys (the review's fourth pass)
MEMBER_MARK = DOMAIN_MARKS[0]         # the one a door that verifies no token reads (`Gate.gated`; the review's ninth pass)
RANK = {"view": 0, "edit": 1, "admin": 2}
OPEN_ROUTES = ("/", "/index.html", "/metrics", "/healthz", "/session")   # the page, what monitoring reads, and the door in
COOKIE = "w2c_token"
GLASS_COOKIE = "w2c_glass"            # an emergency session: this console's own, in its memory, never a token
log = logging.getLogger("w2cplatform.access")


class Denied(Exception):
    """401: nobody proved who they are. 403: they did, and may not. 503: this console cannot check."""

    def __init__(self, status: int, why: str, retry_after: float | None = None):
        super().__init__(why)
        self.status, self.why, self.retry_after = status, why, retry_after


# Whether `payload` holds `capability` on `unit` or on the unit it is about (`of`) — the one question every door asks
# of a unit (the product's `MayOn`). A grant on a unit takes in the units about it because each of those says so in its
# spec (`about`); nothing here knows what either is.
def may_on(access, payload: dict, capability: str, unit: str | None, labels, of: str | None = None) -> bool:
    labels = list(labels or [])
    if access.may(payload, capability, unit, labels):
        return True
    return bool(of) and of != unit and access.may(payload, capability, of, labels)


class Access(Protocol):
    def who(self, token: str) -> dict: ...                       # the token's payload (`sub`, …), or `Denied(401)`
    # `unit`: `<sub>/<id>` (`doors.unit_ref`), `"*"` (every unit: only a grant on the whole cluster), or None (no unit
    # in particular: to look, any grant; to act, the whole cluster's). A grant's scope is a unit, labels, or the
    # cluster; that a grant on a unit takes in the units ABOUT it is asked by the gate (`Gate.admit`, `of`), not here.
    def may(self, payload: dict, capability: str, unit: str | None, labels: list) -> bool: ...
    # Optional: whether the payload's subject holds a grant given on labels at `capability` or above — what `/events`
    # asks before it names units whose labels it could not read (`SpecConsole._by_labels`). Absent: taken as no.
    def by_labels(self, payload: dict, capability: str) -> bool: ...


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


# Who is on the other end, for a limit counted by address. The peer — unless the peer is a proxy this console was
# told to trust (`TRUSTED_PROXY`: its addresses, comma-separated), and then the address that proxy says it saw: the
# rightmost entry of `X-Forwarded-For` that is not itself one of ours. Taken from anybody, the header is whatever the
# caller writes in it — one guesser would be a thousand addresses; not taken at all, behind a proxy every caller is
# the proxy (the review's third pass, major).
def caller_addr(headers, peer: str) -> str:
    trusted = trusted_proxies()
    if peer not in trusted:
        return peer
    hops = [a.strip() for a in (headers.get("X-Forwarded-For", "") or "").split(",") if a.strip()]
    return next((a for a in reversed(hops) if a not in trusted), peer)


def trusted_proxies() -> set:
    return {a.strip() for a in os.environ.get("TRUSTED_PROXY", "").split(",") if a.strip()}


# Whether the caller is ON THIS BOX: the connection came through the console's unix socket (`console.UnixConsoleServer`,
# whose peers are named `unix…`). The emergency door's local lane (`Gate.open_glass`), and the box's own connections
# (`console.Bounds`).
#
# NOT A LOOPBACK ADDRESS (the review's sixth pass, minor). It was "a TCP peer of 127.0.0.1 that is no trusted proxy" —
# true of nobody on the network, and wrong twice on the box: behind a proxy on the same machine the proxy is that
# peer, so the lane was every caller's (the proxy not named in `TRUSTED_PROXY`) or nobody's (named); and any process
# on the box could take the lane's turns. The socket is a file under a directory only root opens: who reaches it is
# decided by the file's mode, a proxy does not go through it, and nothing a caller writes in a header names it.
UNIX_PEER = "unix"


def is_local(peer: str) -> bool:
    return str(peer).startswith(UNIX_PEER)


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
    # …and its attempts, by the caller's address and for the process: the one account with rights to everything
    # is the one password worth guessing, and a wrong guess is also a fsync'd alarm line. Past the limit the
    # door says 429 and writes one alarm, not one per guess (the review's second pass, major).
    #
    # The third pass, major: the check and the count were two steps, and 500 parallel attempts all passed the
    # check before the first was counted. An attempt is now RESERVED under a lock before its password is looked
    # at, and given back only if the password was right — at most `GLASS_TRIES` checks are ever in flight from one
    # address. The address is the peer's, or what a proxy we trust says the peer was (`caller_addr`): behind a
    # proxy every caller was the proxy, and five wrong guesses from anybody shut the door to everybody.
    #
    # The limit is still asked BEFORE the password, the right one included, and that is the point of it: a door
    # that checks the password while the limit is full and lets the right one in limits nothing — the guesser keeps
    # guessing, and the right guess opens it. So while an ADDRESS's window is full it is 429 for that address until
    # the window ends.
    #
    # THE PROCESS'S LIMIT IS A PACE, NOT A BAN (the review's fourth pass, major). It was a window too: twenty wrong
    # guesses from anywhere and the door was shut to everybody, the right password included — and kept shut for as
    # long as somebody sent a wrong one now and then (the product's own check: one every 45 s from four addresses held
    # its sliding window shut for good). The emergency door exists for the hour the domain is down; one stranger
    # could keep the operator at the box out of it. Now the process checks at most `GLASS_RATE` passwords a minute,
    # `GLASS_BURST` at once: a check past the pace WAITS its turn — up to `GLASS_WAIT` seconds, held in its thread —
    # and only one that would wait longer is 429 with `Retry-After`. Guessing across addresses is as slow as it was
    # (ten a minute is fourteen thousand a day, against a password nobody chose to be short); a trickle never fills
    # the pace, so a right password from an address that has not been refused gets in at once or after one turn.
    # Only a flood keeps the turns taken — from thirty fresh addresses each quarter of an hour, each of them
    # refused five times — and then the right password still competes for every turn, and the alarm says so.
    #
    # …AND THE BOX HAS A LANE OF ITS OWN (the review's fifth pass, Ч-M3's remainder). A refusal by the pace spends
    # no try of the address — and so forty addresses, each inside its five a window, keep every network turn
    # taken for good: the right password competed with them for each one, and the reviewer's simulation left the
    # operator outside for an hour. Three ways out were named; the one taken is a separate pace for the caller on
    # the box itself (`is_local`: a connection through the console's unix socket — on the console's host, or through
    # an SSH tunnel to that socket; it was a loopback TCP peer until the review's sixth pass). Nobody on the network
    # can take its turns, and guessing from the network stays exactly as slow as it was. The other two were not: counting pace refusals against the address shuts out the operator
    # whose own attempts the flood turned into refusals — five of them, and a quarter of an hour; a queue for
    # addresses with no wrong attempt gives every FRESH address an unpaced guess, and a flood is fresh addresses.
    # What stays: an operator who can reach neither the box nor an unflooded network still competes, and the
    # alarm `access.break_glass.limited` says the door is under a flood. The per-address limit holds for the box
    # too — five wrong guesses through the socket close it to that user for the window (the "address" is the peer's
    # uid, where the kernel says it); whoever is on the box is not a stranger. A console with no unix socket
    # (`CONSOLE_UNIX` not set) has no such lane, and says so when it starts.
    GLASS_TRIES, GLASS_WINDOW = 5, 900.0
    GLASS_RATE, GLASS_BURST, GLASS_WAIT = 10.0, 10, 10.0
    _glass_tries: dict = {}
    _glass_limited: dict = {}                            # key -> when its `limited` alarm was written: once a window
    _glass_pace: dict = {"tat": 0.0, "local": 0.0}       # each lane's theoretical arrival time (GCRA), on `_glass_clock`
    _glass_lock = threading.Lock()
    _glass_clock = staticmethod(time.monotonic)          # the pace's clock and its wait: a test sets its own
    _glass_sleep = staticmethod(time.sleep)

    @classmethod
    def forget_glass(cls) -> None:
        """The counts are the process's: a test starts from none."""
        with cls._glass_lock:
            cls._glass_tries.clear(); cls._glass_limited.clear(); cls._glass_pace.update(tat=0.0, local=0.0)

    # THE EMERGENCY DOOR IS THE CONSOLE'S (the product's own finding on the review's ninth pass: its `POST /session/break-
    # glass` was served by every door that mounts the shared gate — a recorder, the live gateway). Here `/session` is
    # routed by the console alone (`SpecConsole.dispatch`), and a session lives in the memory of the process that opened
    # it — but the gate a door holds read the session cookie all the same, so a door running in the console's process
    # would have taken one. `glass=False` — a door that is not the console (the gateway, the holder's playback door):
    # no emergency session is opened through it or honoured by it; a token is.
    def __init__(self, vars_, wall, journal=None, impl: Access | None = None, glass: bool = True):
        self.vars, self.wall, self.journal, self.impl = vars_, wall, journal, impl
        self.glass = glass
        self._said_open = False
        self._seen_keys = False                          # a cluster that WAS in a domain does not become open again
        self._loaded: Access | None = None

    # Whether this cluster asks at all: a key set, or the marks of a member that lost it — without loading
    # anything that verifies a token. For a door that checks something other than a token (the device's playback
    # door checks the console's signature, `vms/playback.py`) and must ask exactly when the console asks.
    # `Denied(503)` when the store does not answer: "I cannot tell" is not "open".
    #
    # …BY THE KEY SET AND THE MEMBERSHIP ROW ALONE (the review's ninth pass, minor): it read every mark the console reads,
    # and so the holder's policy let it read `domain/break_glass` — the emergency password's hash — and the grants, of
    # which it needs nothing but that they exist. `domain/member` is written by the domain's agent on every pass that
    # leaves keys, and a cluster that lost its keys still has it; the other marks are the console's, which verifies
    # tokens and reads them anyway.
    def gated(self) -> bool:
        if self.impl is not None:
            return True
        try:
            items, _ = self.vars.get(TRUST_KEYS)
            marked = None if items else (MEMBER_MARK if self.vars.get(MEMBER_MARK)[0] else None)
        except OSError as e:
            raise Denied(503, f"this process cannot read the cluster's trust ({e}): it admits nobody until it can") from None
        if items:
            self._seen_keys = True
        return bool(items or marked or self._seen_keys)

    def access(self) -> Access | None:
        if self.impl is not None:
            return self.impl
        try:
            items, _ = self.vars.get(TRUST_KEYS)
            marked = None if items else next((p for p in DOMAIN_MARKS if self.vars.get(p)[0]), None)
        except OSError as e:
            raise Denied(503, f"this console cannot read the cluster's trust ({e}): it admits nobody until it can") from None
        if not items and (self._seen_keys or marked):
            # Deleted, or rolled back from a backup made before the cluster joined: the keys this console has
            # already checked tokens against are gone. Open would be "an administrator under any name" for
            # whoever did that (the review's second pass, major). Shut, until the agent brings them back — and
            # not only in the process that saw them: the store still says it is a member (`DOMAIN_MARKS`), and a
            # console started after the loss reads that (the review's third pass).
            raise Denied(503, f"the key set has gone from this cluster's store ({TRUST_KEYS}"
                              + (f"; {marked} says this cluster is in a domain" if marked else "") +
                              "): this console admits nobody until the domain's agent writes it again")
        if items:
            self._seen_keys = True
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

    # WHO, BEFORE WHAT (the review's fifth pass, major). The console read a request's body before the gate — `_named`
    # looked in it for the unit an action names — and read it whole, whatever `Content-Length` said: a POST with no
    # token and 400 MiB declared grew the console by 800 MiB and was then told 401. The caller is proved first, from
    # the headers alone — no token is 401 and not a byte of the body is read — and what the caller may do on the
    # unit the body names is asked after (`admit`). The payload, or None when this console is open.
    def caller(self, headers) -> dict | None:
        access = self.access()
        return None if access is None else self.payload(headers, access)

    # The caller's payload: from a token, or from an emergency session of this process. `Denied` if neither.
    def payload(self, headers, access: Access) -> dict:
        sid = cookie(headers, GLASS_COOKIE) if self.glass else None
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
    def open_glass(self, who: str, why: str, password: str, addr: str = "?", local: bool = False) -> tuple[str, dict]:
        import secrets
        from .events import ALARM
        if not self.glass:
            raise Denied(404, "the emergency entry is the console's: this door has none")
        access = self.access()
        if access is None:
            raise Denied(400, "this console is open: there is nothing to break into")
        if not who.strip() or not why.strip():
            raise Denied(400, "an emergency entry says who is entering and why")
        if not hasattr(access, "glass"):
            raise Denied(501, "this cluster's access has no emergency account")
        now = self.wall()
        limits = {addr: self.GLASS_TRIES}
        interval = 60.0 / self.GLASS_RATE
        lane = "local" if local else "tat"               # the box's own turns, or the network's
        with self._glass_lock:                           # check and reserve in one step: no attempt slips between them
            tries = self._glass_tries[addr] = [t for t in self._glass_tries.get(addr, []) if now - t < self.GLASS_WINDOW]
            if len(tries) >= self.GLASS_TRIES:
                raise Denied(429, f"too many emergency entries refused from this address ({len(tries)} in "
                                  f"{self.GLASS_WINDOW:.0f} s): it is closed to this address for a while — the right "
                                  f"password too, until the window ends")
            # The pace (GCRA): every check moves the theoretical arrival time on by one interval; a check may run
            # while that time is within the burst of now, and waits for it otherwise.
            mono = self._glass_clock()
            tat = max(self._glass_pace[lane], mono)
            wait = tat - (self.GLASS_BURST - 1) * interval - mono
            if wait > self.GLASS_WAIT:
                full = mono - self._glass_limited.get("*" + lane, -1e18) >= self.GLASS_WINDOW
                if full:
                    self._glass_limited["*" + lane] = mono
            else:
                full = None
                self._glass_pace[lane] = tat + interval
                self._glass_tries[addr].append(now)
        if full is not None:
            if full and self.journal is not None:
                self.journal().say("access.break_glass.limited", cls=ALARM, user=f"break-glass({who})", addr=addr,
                                   rate=self.GLASS_RATE, all=True, lane="box" if local else "network")
            raise Denied(429, f"the emergency door checks {self.GLASS_RATE:.0f} passwords a minute and every turn is "
                              f"taken: retry in {wait:.0f} s"
                              + ("" if local else " — on the box itself, through the console's unix socket "
                                                  "(CONSOLE_UNIX), the door has turns of its own"), retry_after=wait)
        if wait > 0:
            self._glass_sleep(wait)                      # its turn: a pace, not a refusal
        try:
            payload = access.glass(who, why, password)
        except Denied:
            with self._glass_lock:                       # the reservation stays: it was a wrong guess
                full = [(k, limit) for k, limit in limits.items() if len(self._glass_tries[k]) >= limit
                        and now - self._glass_limited.get(k, -1e18) >= self.GLASS_WINDOW]
                for k, _ in full:
                    self._glass_limited[k] = now
            for k, limit in full:
                if self.journal is not None:
                    self.journal().say("access.break_glass.limited", cls=ALARM, user=f"break-glass({who})",
                                       addr=addr, tries=limit, window=self.GLASS_WINDOW)
            if self.journal is not None:
                self.journal().say("access.break_glass.refused", cls=ALARM, user=f"break-glass({who})", why=why, addr=addr)
            raise
        except BaseException:
            self._give_back(limits, now)                 # not an answer about the password: not a guess either
            raise
        self._give_back(limits, now)                     # the right password: it was no guess
        sid = secrets.token_urlsafe(24)
        self._glass[sid] = payload
        if self.journal is not None:
            self.journal().say("access.break_glass.opened", cls=ALARM, user=f"break-glass({who})", why=why, until=payload.get("exp"))
        return sid, payload

    def _give_back(self, limits: dict, at: float) -> None:
        with self._glass_lock:
            for k in limits:
                try:
                    self._glass_tries.get(k, []).remove(at)
                except ValueError:
                    pass                                 # aged out meanwhile

    def close_glass(self, headers) -> None:
        self._glass.pop(cookie(headers, GLASS_COOKIE) or "", None)

    # The name to act under — or `Denied`. With no key set: whatever `X-User` says, as before.
    # `of`: the unit `unit` is about (its spec's `about`), when it is about one — a grant that takes in either is enough,
    # with the labels given for both (the about-unit's, when there is one: a unit's own labels say where it runs).
    def admit(self, headers, capability: str, unit: str | None = None, labels: list | None = None,
              of: str | None = None) -> str:
        access = self.access()
        if access is None:
            return headers.get("X-User", "operator")
        if capability != "view" and (from_cookie(headers) or cookie(headers, GLASS_COOKIE)) and cross_site(headers):
            raise Denied(403, "a request that acts came from another site's page: refused")
        payload = self.payload(headers, access)
        name = str(payload.get("sub", ""))
        if payload.get("via") == "break-glass":          # the one local account (М12 Lesson 4): every use is an alarm
            name = f"break-glass({payload.get('who', '?')})"
            # …every use that ACTS. The session's opening is the alarm for looking (`open_glass`); a page that
            # polls `/events` under it would write one every three seconds and bury the ones that matter.
            if self.journal is not None and capability != "view":
                from .events import ALARM
                self.journal().say("access.break_glass", cls=ALARM, user=name, capability=capability, **({"target": unit} if unit else {}))
        if not may_on(access, payload, capability, unit, labels, of):
            if self.journal is not None:
                self.journal().say("access.denied", user=name, capability=capability, **({"target": unit} if unit else {}))
            raise Denied(403, f"{name} may not {capability}" + (f" {unit}" if unit else " here"))
        del headers["X-User"]                            # whatever the caller called themselves
        headers["X-User"] = name                         # …is replaced by what the token proved
        return name
