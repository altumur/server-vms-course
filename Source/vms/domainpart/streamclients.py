"""The RTSP accounts — stream clients (`vms/streamclients.py`) — the holder's half, the VMS worker's on the domain (the
product's `vms/domainpart/streamclients.go` and `publishAccounts`; ADR-0031, the addendum of 2026-10-07): kept beside
the people, in the grants' one name space, granted like a person (a grant names the client at a cluster: it plays what
such a grant lets it view), and carried to each cluster that grants one as that cluster's book `stream-accounts`.

    GET  /stream-clients                   name, disabled — never a password
    POST /stream-clients                   {name} — a new one, not a person's name; the answer carries its password,
                                           the one time it is shown
    POST /stream-clients/<name>/password   a new password, shown once
    PUT  /stream-clients/<name>            {disabled}
    DELETE /stream-clients/<name>          and every grant that names it, through the domain console's door

A refusal is `{error: "refused", detail}` with the product's status: 400 a request wrong by itself (a name that is no
name, a body without `disabled`), 404 no such client, 409 a name a person or a client holds already, 503 a password this
process cannot open, or no domain console to ask. With the family not declared (`domain.kept: [stream-clients/]`) the
doors are not there: 404, as any route this worker does not serve.

NAMES MEET IN TWO DIRECTIONS (ADR-0031). A person under a client's name, a grant to a client above `view`: the platform
refuses those by the spec (`domain.names`), on every write of the holder's store as its processes open it
(`w2cplatform.domain.declared.guarded`) — this worker writes through it too, so a client written under a person's name is
refused there as well. The one direction that is this worker's is the door's question: a client is made HERE, and the
person's side of the name space is the domain's, so the door asks the domain console, as the person who asked it
(`GET /domain/users`), before it writes. Deleting a client takes its grants away the same way: the grants are the
domain's to write, `PUT /domain/grants/<cluster>` as that person.
"""
from __future__ import annotations

import json
import logging
import time

from w2cplatform.domain.api import ApiError

from vms import streamclients as sc

log = logging.getLogger("vms.domainpart")


def refused(status: int, detail: str) -> ApiError:
    return ApiError(status, detail)


def valid_name(name) -> bool:
    """A client's name is a person's kind of name (the grants' subjects are one space): a path segment, none of
    `:|() "`, no control character, not `break-glass` — the product's `trust.ValidName`."""
    from w2cplatform.domain.grants import name_refused
    return isinstance(name, str) and name_refused(name, "client's name", also='/:() \\') is None \
        and name not in ("break-glass", ".", "..")


# -- the domain console's door -----------------------------------------------------------------------------------------
class ConsoleDoor:
    """The domain console's door (`DOMAIN_CONSOLE_URL`; ADR-0032): the people's routes and the grants are there. Asked
    with the token of the person who asked this worker (`as_person`), so the domain checks that person, not this process.
    `do` answers the door's JSON on a 2xx and raises `ApiError` with its status and words on anything else."""

    def __init__(self, url: str = "", auth: str = "", operator: str = "", timeout: float = 10.0):
        self.url, self.auth, self.operator, self.timeout = url, auth, operator, timeout

    def as_person(self, auth: str, operator: str) -> "ConsoleDoor":
        return ConsoleDoor(self.url, auth, operator, self.timeout)

    def do(self, method: str, path: str, body=None):
        import urllib.error
        import urllib.request
        if not self.url:
            raise refused(503, "this worker knows no domain console (DOMAIN_CONSOLE_URL)")
        headers = {"Content-Type": "application/json"}
        if self.auth:
            headers["Authorization"] = self.auth
        if self.operator:
            headers["X-Operator"] = self.operator
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url.rstrip("/") + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read(4 << 20)
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read(4 << 20)
            try:
                out = json.loads(raw)
            except ValueError:
                out = None
            msg = raw.decode("utf-8", "replace").strip()
            if isinstance(out, dict):
                msg = str(out.get("detail") or out.get("error") or msg)
            raise refused(e.code, msg) from None
        except (OSError, ValueError) as e:
            raise refused(502, f"the domain console did not answer: {e}") from None


def users_at(door: ConsoleDoor):
    """`users(name)`: refuses 409 when a person holds `name` — asked of the domain console (`GET /domain/users`)."""
    def users(name: str) -> None:
        out = door.do("GET", "/domain/users")
        for u in (out or {}).get("users") or []:
            if isinstance(u, dict) and u.get("name") == name:
                raise refused(409, f"there is a user {name} already")
    return users


def _line(g) -> dict:
    """A grant as the domain's door takes it back (`PUT /domain/grants/<cluster> {lines}`): {subject, cap, scope, until}."""
    from w2cplatform.domain.grants import UNIT_SCOPE
    scope = "labels:" + ",".join(sorted(g.labels)) if g.labels else "*" if g.unit is None else UNIT_SCOPE + g.unit
    return {"subject": g.subject, "cap": g.capability, "scope": scope, "until": g.valid_until}


def grants_at(vars_, door: ConsoleDoor):
    """`drop(name) -> [cluster…]`: every line naming `name` out of every grants row, written through the domain console's
    door as whoever asked (the grants are the domain's to write; this worker reads them only)."""
    from w2cplatform.domain.agent import GRANTS_PATH
    from w2cplatform.domain.grants import grants_from_items

    def drop(name: str) -> list[str]:
        changed = []
        for path in vars_.list(GRANTS_PATH + "/"):
            cluster = path[len(GRANTS_PATH) + 1:]
            lines = grants_from_items(vars_.get(path)[0], path)
            kept = [g for g in lines if g.subject != name]
            if len(kept) == len(lines):
                continue
            door.do("PUT", f"/domain/grants/{cluster}", {"lines": [_line(g) for g in kept]})
            changed.append(cluster)
        return changed
    return drop


# -- the records ---------------------------------------------------------------------------------------------------------
def _put(vars_, c: sc.StreamClient, password: str, sealer) -> None:
    """A client and its password, sealed with the ring. A write the platform refuses by the spec's `domain.names` is the
    door's 409 (a name a person holds) or 400 (a grant wider than declared)."""
    from w2cplatform.domain.declared import GrantTooWide, Refused
    from w2cplatform.sealing import seal_items
    row = sc.STREAM_CLIENTS_PREFIX + c.name
    items = seal_items(sealer, {"doc": json.dumps(c.to_doc(), sort_keys=True), sc.PASSWORD: password}, row)
    _, idx = vars_.get(row)
    try:
        vars_.put(row, items, cas=idx)
    except GrantTooWide as e:
        raise refused(400, str(e)) from None
    except Refused as e:
        raise refused(409, str(e)) from None


def new_stream_client(vars_, users, name, by: str, now: float, sealer=None) -> str:
    """Makes an RTSP account and returns its password — the one time it is shown. It plays nothing until a grant names
    it. `users(name)` refuses a person's name; None: nobody is asked (a tool on the holder's box; the store's guard still
    refuses it)."""
    if not valid_name(name):
        raise refused(400, f"{json.dumps(name if isinstance(name, str) else '')} is not a client's name")
    if users is not None:
        users(name)
    if sc.read_stream_client(vars_, name, sealer)[0] is not None:
        raise refused(409, f"there is a stream client {name} already")
    password = sc.new_stream_password()
    _put(vars_, sc.StreamClient(name, at=now, by=by), password, sealer)
    return password


def new_stream_client_password(vars_, name: str, by: str, now: float, sealer=None) -> str:
    """A client's new password: the old one stops at each cluster with its agent's next pass."""
    c, _ = sc.read_stream_client(vars_, name, sealer)
    if c is None:
        raise refused(404, f"no stream client {name}")
    password = sc.new_stream_password()
    c.at, c.by = now, by
    _put(vars_, c, password, sealer)
    return password


def set_stream_client_disabled(vars_, name: str, disabled: bool, by: str, now: float, sealer=None) -> None:
    """Turns a client off or on: off, no cluster is carried its password."""
    c, password = sc.read_stream_client(vars_, name, sealer)
    if c is None:
        raise refused(404, f"no stream client {name}")
    if not password:                 # sealed and not opened here: written back as "" it would be the password gone
        raise refused(503, f"the password of {name} does not open in this process (SECRETS_KEY): nothing was changed")
    c.disabled, c.at, c.by = disabled, now, by
    _put(vars_, c, password, sealer)


# A CLIENT DELETED IS A MARK, NOT A ROW REMOVED. The product deletes the row. The course's store lets nobody but the
# domain's own roles remove a row under `domain/` (`variables.refuse_delete`, the review's third pass, Н-M2) — this
# worker's role writes `domain/vms/*` and removes nothing — so the row is written over with the platform's mark of a
# subject gone, `{kind: deleted}` (as `identity.py` marks a person): no doc, no password, nobody reads it as a client, and
# the name is free again for a person or a client (`declared._holds` reads the mark as nobody).
DELETED = {"kind": "deleted"}


def delete_stream_client(vars_, drop, name: str, sealer=None) -> list[str]:
    """Removes a client, and its grants everywhere (`drop`), as deleting a person does a person's."""
    if sc.read_stream_client(vars_, name, sealer)[0] is None:
        raise refused(404, f"no stream client {name}")
    clusters = drop(name)
    _, idx = vars_.get(sc.STREAM_CLIENTS_PREFIX + name)
    vars_.put(sc.STREAM_CLIENTS_PREFIX + name, dict(DELETED), cas=idx)
    return clusters


class StreamClientDoors:
    """The doors for the RTSP accounts, over the holder's store (`vars_`, as the worker opened it: guarded), its ring
    (`sealer`) and the domain console's door (`console`)."""

    def __init__(self, vars_, sealer=None, console: ConsoleDoor | None = None, wall=time.time):
        self.vars, self.sealer, self.console, self.wall = vars_, sealer, console or ConsoleDoor(), wall

    def serves(self, path: str) -> bool:
        return sc.clients_declared() and (path == "/stream-clients" or path.startswith("/stream-clients/"))

    def handle(self, method: str, path: str, body: dict | None, auth: str, by: str) -> tuple[int, dict]:
        """`(status, answer)` of one request; `body` None: it did not parse (400 already said by the caller)."""
        try:
            return 200, self._handle(method, path, body or {}, auth, by)
        except ApiError as e:
            if e.status == 405:                          # a method the route does not take: what it takes, as the product
                return 405, {"error": e.detail}
            return e.status, {"error": "refused", "detail": e.detail}

    def _handle(self, method: str, path: str, body: dict, auth: str, by: str) -> dict:
        v, now, door = self.vars, self.wall(), self.console.as_person(auth, by)
        if path == "/stream-clients":
            if method == "GET":
                return {"clients": [c.to_doc() for c in sc.stream_clients(v, self.sealer)]}
            if method == "POST":
                name = body.get("name") if isinstance(body.get("name"), str) else ""
                password = new_stream_client(v, users_at(door), name, by, now, self.sealer)
                log.info("vms domainpart: stream client %s made by %s", name, by)
                return {"client": name, "password": password}
            raise refused(405, "GET or POST {name}")
        name, _, rest = path[len("/stream-clients/"):].partition("/")
        if method == "POST" and rest == "password":
            password = new_stream_client_password(v, name, by, now, self.sealer)
            log.info("vms domainpart: stream client %s given a new password by %s", name, by)
            return {"client": name, "password": password}
        if method == "PUT" and rest == "":
            d = body.get("disabled")
            if not isinstance(d, bool):
                raise refused(400, "{disabled: true|false}")
            set_stream_client_disabled(v, name, d, by, now, self.sealer)
            log.info("vms domainpart: stream client %s disabled=%s by %s", name, d, by)
            return {"client": name, "disabled": d}
        if method == "DELETE" and rest == "":
            clusters = delete_stream_client(v, grants_at(v, door), name, self.sealer)
            log.info("vms domainpart: stream client %s deleted by %s, and its grants at %s", name, by, clusters)
            return {"client": name, "deleted": True, "grants_changed": clusters}
        raise refused(405, "POST …/password, PUT {disabled}, DELETE")


# -- the book ----------------------------------------------------------------------------------------------------------
def publish_accounts(crossings) -> int | None:
    """For every cluster the domain reads, the RTSP accounts granted there (`streamclients.accounts_for`) as its book
    `stream-accounts/<cluster>` at the holder: `{accounts_secret: {name: password}}`, written through the books' store
    (`keys.OpenedVars`: sealed with the holder's ring; the platform opens it for the carry it seals to the member, and the
    member's agent seals it again with the member's), and only when what it SAYS changed. Only in a domain installed (a
    key set at the holder): before, nobody plays (`streamclients.stream_accounts`), and the books are left as they are.
    None: the spec declares no such book — nothing is written. Returns how many books were written."""
    if not sc.book_declared():
        return None
    from w2cplatform.domain.agent import KEYS_PATH
    v = crossings.vars
    if v.get(KEYS_PATH)[0] is None:
        return None
    written = 0
    for member in sorted(crossings.view.fed.clusters):
        raw = json.dumps(sc.accounts_for(v, member), sort_keys=True, separators=(",", ":"))
        path = f"{sc.STREAM_ACCOUNTS_KEY}/{member}"
        have, idx = v.get(path)
        if (have or {}).get(sc.ACCOUNTS) == raw:
            continue
        v.put(path, {sc.ACCOUNTS: raw}, cas=idx)
        written += 1
    return written
