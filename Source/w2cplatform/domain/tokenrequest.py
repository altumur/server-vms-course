"""ADR-0074: ephemeral token requests; scope comes only from holder assignments."""
from __future__ import annotations

import json
import uuid

from w2cplatform.canonical import parse_json
from w2cplatform.trust.memberkey import NotMine, seal_to
from .carry import Refused, _http_post, publication_bytes

MAX_REQUEST = 16 << 10
PREFIX = "/api/tokens/"


def route(member, sub, kind):
    import re
    parts = (member, sub, kind)
    if any(not isinstance(p, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", p) for p in parts):
        raise Refused(400, "invalid token request identity")
    return PREFIX + "/".join(parts)


def context(path, request_id, exp):
    return publication_bytes([path, request_id, exp]).decode()


def issue(door, issuer, member, sub, kind, body, signature):
    """Check the original member's signature, then derive claims; no write or queue."""
    from . import declared, placement
    from .booknames import MUTATIONS
    from .members import Members
    path = route(member, sub, kind)
    if not isinstance(body, bytes) or len(body) > MAX_REQUEST:
        raise Refused(413, "token request exceeds body limit")
    me = door._member_key(member, path, body, signature)
    try:
        request = parse_json(body)
        if not isinstance(request, dict) or set(request) != {"request_id", "role", "ref"} \
                or any(not isinstance(request[k], str) or not request[k] for k in request):
            raise ValueError()
        # The ref is a row identity; malformed identities never reach storage.
        placement.path(sub, request["ref"])
    except (ValueError, TypeError, UnicodeError):
        raise Refused(400, "token request takes request_id, role and ref") from None
    spec = declared.spec(sub)
    rule = spec.domain.tokens.get(kind) if spec and spec.domain else None
    if not rule or request["role"] not in rule.get("grant", ()) or not rule.get("placement"):
        raise Refused(403, "role has no token request grant")
    if issuer is None or not me.get("seal"):
        raise Refused(503, "token issuer or member sealing key is unavailable")
    binding = rule["placement"]
    with MUTATIONS:
        try:
            row = placement.read(door.vars, binding["sub"], request["ref"])
        except ValueError:
            raise Refused(403, "assignment is unreadable") from None
        if not row:
            raise Refused(403, "token request has no assignment")
        def values(field):
            v = row[field]
            return v if isinstance(v, list) else ([v] if v else [])
        links = values("cluster") + values("origin") + values("copies")
        admitted = Members(door.vars).read()["members"]
        if any(n not in admitted for n in links) or member not in values(binding["caller"]):
            raise Refused(403, "token request is outside assignment scope")
        targets = sorted({n for f in binding["target_fields"] for n in values(f)})
        if not targets:
            raise Refused(403, "assignment has no token audience")
        now = door.wall()
        claims = {binding["ref_claim"]: request["ref"], binding["audience_claim"]: targets}
        token = issuer.issue(kind, request["ref"], now=now, **claims)
        exp = now + issuer.lifetime(kind)
        return {"request_id": request["request_id"],
                "token": seal_to(me["seal"], "token", token, context(path, request["request_id"], exp)), "exp": exp}


def pass_on(client, member, sub, kind, body, signature):
    """Forward bytes and signature unchanged; never unwrap another member's reply."""
    path = route(member, sub, kind)
    if isinstance(client.door, str):
        return _http_post(client.door, path, body, signature, client.timeout)
    return client.door.token(member, sub, kind, body, signature)


def request(client, sub, kind, ref, role):
    from w2cplatform.trust.memberkey import sign_request
    path = route(client.cluster, sub, kind)
    request_id = uuid.uuid4().hex
    body = publication_bytes({"request_id": request_id, "role": role, "ref": ref})
    signature = sign_request(client.key, "POST", path, body, client.wall())
    got = pass_on(client, client.cluster, sub, kind, body, signature)
    try:
        if not isinstance(got, dict) or set(got) != {"request_id", "token", "exp"} \
                or got["request_id"] != request_id or type(got["exp"]) not in (int, float):
            raise ValueError()
        import math
        if not math.isfinite(got["exp"]) or got["exp"] <= client.wall():
            raise ValueError()
        token = client.key.open("token", got["token"], context(path, request_id, got["exp"]))
        return {"request_id": request_id, "token": token, "exp": got["exp"]}
    except (ValueError, TypeError, KeyError, NotMine):
        raise Refused(502, "invalid token request reply") from None


def local_handler(agent, sub, role):
    """One role's private Unix socket. No network listener and no role from the body."""
    from http.server import BaseHTTPRequestHandler
    from w2cplatform.console import Deadlined, read_body
    from w2cplatform.rows import PARSE_ERRORS
    from .federation import Unreachable

    class H(Deadlined, BaseHTTPRequestHandler):
        def _send(self, code, value):
            raw = json.dumps(value).encode()
            self.send_response(code)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            import socket
            if getattr(self.connection, "family", None) != socket.AF_UNIX:
                return self._send(403, {"detail": "token requests require a role socket"})
            parts = self.path.split("/")
            if len(parts) != 3 or parts[:2] != ["", "tokens"]:
                return self._send(404, {"detail": "no such route"})
            if not read_body(self, MAX_REQUEST):
                return
            try:
                body = parse_json(self.rfile.read(int(self.headers["Content-Length"])))
                if not isinstance(body, dict) or set(body) != {"ref"} or not isinstance(body["ref"], str) or not body["ref"]:
                    raise Refused(400, "local token request takes ref only")
                result = agent.request_token(sub, parts[2], body["ref"], role)
                self._send(200, result)
            except Refused as e:
                self._send(e.status, {"detail": e.detail})
            except PARSE_ERRORS:
                self._send(400, {"detail": "invalid token request"})
            except (OSError, Unreachable):
                self._send(503, {"detail": "token request transport is unavailable"})

        def log_message(self, *args):
            pass
    return H


class WorkerTokenDoor:
    """A worker's connection to its role's local socket, without a member key."""
    def __init__(self, path, timeout=5.0):
        from w2cplatform.configstorevars import unix_transport
        self.call, self.timeout = unix_transport(path), timeout

    def request(self, kind, ref):
        route("local", "local", kind)
        raw = publication_bytes({"ref": ref})
        code, body = self.call("POST", f"/tokens/{kind}", raw,
                              {"Content-Type": "application/json"}, self.timeout)
        if code != 200:
            raise Refused(code, "local token request was refused")
        try:
            result = parse_json(body)
            if not isinstance(result, dict) or set(result) != {"request_id", "token", "exp"}:
                raise ValueError()
            return result
        except (ValueError, TypeError):
            raise Refused(502, "invalid local token reply") from None
