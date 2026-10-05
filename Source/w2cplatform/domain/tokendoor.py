"""The signer's door for a subsystem's worker: tokens of the kinds the specs declare, over the signer's own socket.

A subsystem's books carry tokens for its members (`domain.tokens` of its spec: a kind, its claims, its lifetime). The
worker that writes the books runs at the holder, and the key that signs them stays in the signer's process: the worker
asks, the signer issues — of a declared kind, with declared claims only (`trust.tokens.DeclaredIssuer`), never a
person's token. The door is a unix socket on the holder (`SIGNER_TOKENS_UNIX`, mode 0660, its group the workers'),
not the signer's network door: who may ask for a token is who may open that file.

    GET  /kid               {"kid"} — the key that signs now (a book re-issues a token another key signed)
    GET  /kinds             {kind: {lifetime, claims[, grant]}} — what the loaded specs declare
    POST /tokens/<kind>     {"sub", "claims": {...}} -> {"token"}; 400 for an undeclared kind or claim, or a `grant`
                            above the kind's (`domain.tokens.<kind>.grant`, ADR-0031)

`TokenDoor` is the worker's handle on it, with the same face as `DeclaredIssuer`: `kid`, `lifetime(kind)`,
`issue(kind, subject, **claims)`.
"""
from __future__ import annotations

import json

from w2cplatform.trust.tokens import TokenError


class DoorRefused(TokenError):
    """The signer's door said no, or could not be asked."""


class TokenDoor:
    def __init__(self, path: str, timeout: float = 5.0, transport=None):
        from w2cplatform.configstorevars import unix_transport
        self.path, self.timeout = path, timeout
        self.call = transport or unix_transport(path)
        self._kinds: dict | None = None

    def _ask(self, method: str, target: str, body: dict | None = None) -> dict:
        raw = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json", **({"Content-Length": str(len(raw))} if raw else {})}
        try:
            code, out = self.call(method, target, raw, headers, self.timeout)
        except Exception as e:                                  # noqa: BLE001 — no socket, no signer: said as a refusal
            raise DoorRefused(f"the signer's door {self.path} did not answer: {e}") from None
        try:
            doc = json.loads(out or b"{}")
        except ValueError:
            doc = {}
        if code != 200:
            raise DoorRefused(f"the signer's door said {code}: {doc.get('detail', '')}")
        return doc

    @property
    def kid(self) -> str:
        return str(self._ask("GET", "/kid").get("kid", ""))

    def lifetime(self, kind: str) -> float:
        if self._kinds is None:
            self._kinds = self._ask("GET", "/kinds")
        if kind not in self._kinds:
            raise DoorRefused(f"no spec the signer loaded declares a token of kind {kind!r}")
        return float(self._kinds[kind]["lifetime"])

    def issue(self, kind: str, subject: str, now: float | None = None, **claims) -> str:
        return str(self._ask("POST", f"/tokens/{kind}", {"sub": subject, "claims": claims})["token"])


def handler(issuer):
    """The door's handler over `issuer` (a `DeclaredIssuer`): for the signer's unix socket."""
    from http.server import BaseHTTPRequestHandler

    from w2cplatform.console import Deadlined, read_body
    from w2cplatform.rows import PARSE_ERRORS

    class H(Deadlined, BaseHTTPRequestHandler):
        MAX_BODY = 16 << 10

        def _send(self, status, body):
            raw = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == "/kid":
                return self._send(200, {"kid": issuer.kid})
            if self.path == "/kinds":
                return self._send(200, {k: {"lifetime": v["lifetime"], "claims": list(v.get("claims") or ()),
                                            **({"grant": v["grant"]} if v.get("grant") else {})}
                                        for k, v in issuer.kinds.items()})
            self._send(404, {"detail": "no such route"})

        def do_POST(self):
            if not self.path.startswith("/tokens/"):
                return self._send(404, {"detail": "no such route"})
            if not read_body(self, self.MAX_BODY):
                return
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if not isinstance(body, dict) or not isinstance(body.get("sub"), str) or \
                        not isinstance(body.get("claims", {}), dict):
                    raise TypeError("{sub: <string>, claims: {...}}")
            except PARSE_ERRORS as e:
                return self._send(400, {"detail": f"the body is {{sub, claims}}: {e}"})
            try:
                token = issuer.issue(self.path[len("/tokens/"):], body["sub"], **body.get("claims", {}))
            except (TokenError, TypeError) as e:
                return self._send(400, {"detail": str(e)})
            self._send(200, {"token": token})

        def log_message(self, *a):
            pass
    return H
