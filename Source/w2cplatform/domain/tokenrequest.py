"""ADR-0074: ephemeral token requests scoped by assignments or accepted unit reports."""
from __future__ import annotations

import json
import uuid

from w2cplatform.canonical import parse_json
from w2cplatform.rows import PARSE_ERRORS
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
        if not isinstance(request, dict) or (set(request) - {"request_id", "role", "ref", "by"} or {"request_id", "role", "ref"} - set(request)) \
                or any(not isinstance(request[k], str) or not request[k] for k in request):
            raise ValueError()
        # The ref is a row identity; malformed identities never reach storage.
        placement.path(sub, request["ref"])
    except (ValueError, TypeError, UnicodeError):
        raise Refused(400, "token request takes request_id, role and ref") from None
    spec = declared.spec(sub)
    rule = spec.domain.tokens.get(kind) if spec and spec.domain else None
    if not rule or request["role"] not in rule.get("grant", ()) or not (rule.get("placement") or rule.get("unit") or rule.get("scenario")):
        raise Refused(403, "role has no token request grant")
    if issuer is None or not me.get("seal"):
        raise Refused(503, "token issuer or member sealing key is unavailable")
    if ("by" in request) != bool(rule.get("scenario")):
        raise Refused(400, "by is required only for scenario scope")
    with MUTATIONS:
        if rule.get("scenario"):
            from .scenarioscope import claims as scenario_claims
            binding = rule["scenario"]
            extra = scenario_claims(door, spec, member, request["ref"], request["by"], binding)
            targets = extra.pop(binding["audience_claim"])
        elif rule.get("unit"):
            binding = rule["unit"]
            targets = _unit_targets(door, spec, member, request["ref"])
        else:
            binding = rule["placement"]
            try:
                row = placement.read(door.vars, binding["sub"], request["ref"])
            except ValueError:
                raise Refused(403, "assignment is unreadable") from None
            if not row:
                raise Refused(403, "token request has no assignment")
            def values(field):
                if field in ("centre", "star_centre"):
                    from .topology import TOPOLOGY, refusals
                    try:
                        items, _ = door.vars.get(TOPOLOGY)
                        topology = parse_json(items["doc"]) if items and items.get("doc") else {}
                        if field == "star_centre" and not items:
                            return []                         # no configured topology grants no additional audience
                        if not isinstance(topology, dict) or type(topology.get("rev")) is not int \
                                or topology["rev"] <= 0 or not isinstance(topology.get("star", []), list) \
                                or not isinstance(topology.get("via", {}), dict) or refusals(topology):
                            raise ValueError("invalid confirmed topology")
                    except PARSE_ERRORS:
                        raise Refused(409, "topology has no confirmed centre") from None
                    if field == "star_centre" and row["cluster"] not in topology.get("star", []):
                        return []
                    if not isinstance(topology.get("centre"), str) or not topology["centre"]:
                        raise Refused(409, "topology has no confirmed centre")
                    return [topology["centre"]]
                v = row[field]
                return v if isinstance(v, list) else ([v] if v else [])
            links = values("cluster") + values("origin") + values("copies")
            admitted = Members(door.vars).read()["members"]
            if any(n not in admitted for n in links) or member not in values(binding["caller"]):
                raise Refused(403, "token request is outside assignment scope")
            targets = sorted({n for f in binding["target_fields"] for n in values(f)})
            if not targets or any(n not in admitted for n in targets):
                raise Refused(403, "assignment has no admitted token audience")
        now = door.wall()
        claims = {binding["ref_claim"]: request["ref"], binding["audience_claim"]: targets}
        if rule.get("scenario"):
            claims.update(extra)
        token = issuer.issue(kind, member, now=now, **claims)
        exp = now + issuer.lifetime(kind)
        return {"request_id": request["request_id"],
                "token": seal_to(me["seal"], "token", token, context(path, request["request_id"], exp)), "exp": exp}


def _unit_targets(door, spec, member, ref):
    from .federation import Unreachable, _a_shard
    from .reports import pinned
    from .members import Members
    from .topology import poll_home
    if not spec.domain.ref or door.objects is None:
        raise Refused(403, "unit scope has no accepted unit report")
    try:
        objects = pinned(member, door.objects).document()["objects"]
        found = False
        for key, shard in objects.items():
            if not key.startswith(spec.name + "/snapshot/"):
                continue
            if not isinstance(shard, dict) or not isinstance(shard.get(spec.rows), list):
                raise ValueError()
            _a_shard(shard, spec.rows)
            for row in shard[spec.rows]:
                value = row.get(spec.domain.ref)
                if type(value) in (str, int) and str(value) == ref:
                    found = True
        if not found:
            raise Refused(403, "the member does not report this unit")
    except (Unreachable, *PARSE_ERRORS):
        raise Refused(403, "unit scope has no complete accepted unit report") from None
    try:
        target = poll_home(door.vars, member, authoritative=True)
    except ValueError:
        raise Refused(409, "unit scope has no confirmed poll home") from None
    if target not in Members(door.vars).read()["members"]:
        raise Refused(403, "unit scope has no admitted token audience")
    return [target]


def pass_on(client, member, sub, kind, body, signature):
    """Forward bytes and signature unchanged; never unwrap another member's reply."""
    path = route(member, sub, kind)
    if isinstance(client.door, str):
        return _http_post(client.door, path, body, signature, client.timeout)
    return client.door.token(member, sub, kind, body, signature)


def request(client, sub, kind, ref, role, by=None, request_id=None):
    from w2cplatform.trust.memberkey import sign_request
    path = route(client.cluster, sub, kind)
    request_id = request_id or uuid.uuid4().hex
    body = publication_bytes({"request_id": request_id, "role": role, "ref": ref, **({"by": by} if by is not None else {})})
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



def grants():
    """One role socket for all of its kinds; duplicate kind owners are refused."""
    from . import declared
    declared.token_kinds()
    return {kind: (spec.name, tuple(rule.get("grant", ())))
            for spec in declared.specs() for kind, rule in spec.domain.tokens.items()
            if rule.get("grant") and (rule.get("placement") or rule.get("unit") or rule.get("scenario"))}


def owner(kind, role):
    binding = grants().get(kind)
    if not binding or role not in binding[1]:
        raise Refused(403, "role has no token request grant")
    return binding[0]


def socket_path(directory, role):
    import os
    route("local", role, "local")
    return os.path.join(directory, role, "tokens.sock")


def _protected_directory(path, gid, mode):
    import os
    import stat
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_gid != gid \
            or stat.S_IMODE(info.st_mode) != mode:
        raise PermissionError("token request directory is not protected")


def open_role_doors(agent, env=None):
    """Only pre-provisioned root-owned directories; failure disables that role."""
    import grp
    import logging
    import os
    import stat
    import threading
    from w2cplatform.console import Bounds, UnixConsoleServer
    env = os.environ if env is None else env
    directory = env.get("TOKEN_REQUESTS_DIR")
    if not directory:
        return []
    deployment = env.get("ROLE_GROUP") or os.path.basename(os.path.normpath(env.get("SPEC_DIR", "")))
    servers = []
    roles = sorted({r for _, granted in grants().values() for r in granted})
    for role in roles:
        server = None
        try:
            # The parent cannot be renamed/replaced by a worker with the same uid.
            _protected_directory(directory, 0, 0o755)
            parent = os.path.dirname(os.path.realpath(directory))
            while True:
                info = os.stat(parent)
                if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
                    raise PermissionError("token request ancestor can be replaced")
                if parent == os.path.dirname(parent):
                    break
                parent = os.path.dirname(parent)
            gid = grp.getgrnam(role_groups(deployment)[role]).gr_gid
            path = socket_path(directory, role)
            _protected_directory(os.path.dirname(path), gid, 0o2770)
            if os.path.lexists(path):
                info = os.lstat(path)
                if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid() or info.st_gid != gid:
                    raise PermissionError("token request path is not this agent's socket")
            server = UnixConsoleServer(path, local_handler(agent, role), Bounds())
            info = os.lstat(path)
            if info.st_gid != gid or stat.S_IMODE(info.st_mode) != 0o660:
                raise PermissionError("token request socket has unsafe permissions")
            threading.Thread(target=server.serve_forever, daemon=True).start()
            servers.append(server)
        except (OSError, KeyError, ValueError):
            if server is not None:
                server.server_close()
            logging.getLogger(__name__).error("token request door unavailable for role %s", role)
    return servers



def role_groups(deployment):
    from w2cplatform import catalog
    from w2cplatform.cluster.rights import roles
    # Preserve platform controllers' groups and the ROLE_GROUP override too.
    return {role: rule["group"] for role, rule in roles(catalog.specs(), deployment).items()}

def installation(directory, deployment):
    """Deployment files derive their groups and directories from loaded grants."""
    import os
    import re
    if not os.path.isabs(directory) or any(c.isspace() for c in directory) or "%" in directory:
        raise ValueError("token request installation directory must be an absolute literal path")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", deployment):
        raise ValueError("token request installation requires a deployment name")
    roles = sorted({r for _, granted in grants().values() for r in granted})
    derived = role_groups(deployment)
    groups = [derived[role] for role in roles]
    rows = [f"d {directory} 0755 root root -"]
    rows += [f"d {os.path.dirname(socket_path(directory, role))} 2770 root {g} -"
             for role, g in zip(roles, groups)]
    dropin = "[Service]\n" + ("SupplementaryGroups=" + " ".join(groups) + "\n" if groups else "")
    return "\n".join(rows) + "\n", dropin

def local_handler(agent, role):
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
                if not isinstance(body, dict) or set(body) - {"request_id", "ref", "by"} \
                        or {"request_id", "ref"} - set(body) \
                        or any(not isinstance(v, str) or not v for v in body.values()):
                    raise Refused(400, "local token request takes request_id, ref and optional by")
                sub = owner(parts[2], role)
                result = agent.request_token(sub, parts[2], body["ref"], role, body.get("by"), body["request_id"])
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

    @classmethod
    def from_env(cls, role, env=None):
        import os
        env = os.environ if env is None else env
        directory = env.get("TOKEN_REQUESTS_DIR")
        return cls(socket_path(directory, role)) if directory else None

    def request(self, kind, ref, by=None):
        route("local", "local", kind)
        request_id = uuid.uuid4().hex
        raw = publication_bytes({"request_id": request_id, "ref": ref, **({"by": by} if by is not None else {})})
        code, body = self.call("POST", f"/tokens/{kind}", raw,
                              {"Content-Type": "application/json"}, self.timeout)
        if code != 200:
            raise Refused(code, "local token request was refused")
        try:
            result = parse_json(body)
            if not isinstance(result, dict) or set(result) != {"request_id", "token", "exp"} \
                    or result["request_id"] != request_id:
                raise ValueError()
            return result
        except (ValueError, TypeError):
            raise Refused(502, "invalid local token reply") from None


if __name__ == "__main__":
    import argparse
    import os
    parser = argparse.ArgumentParser(description="Role token doors: deployment derived from loaded specs")
    parser.add_argument("output", choices=("tmpfiles", "groups"))
    args = parser.parse_args()
    directory = os.environ.get("TOKEN_REQUESTS_DIR")
    if not directory:
        parser.error("TOKEN_REQUESTS_DIR is required for provisioning")
    files, groups = installation(directory, os.environ.get("ROLE_GROUP") or os.path.basename(os.path.normpath(os.environ.get("SPEC_DIR", ""))))
    print(files if args.output == "tmpfiles" else groups, end="")
