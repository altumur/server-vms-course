"""The gateway reaches domain account operations only through its own console."""
import json
import os

from w2cplatform.domain.api import ApiError


class ConsoleAPI:
    def __init__(self, env=None, client=None):
        self.env = dict(os.environ if env is None else env)
        self.url = self.env.get("CONSOLE_URL", "").rstrip("/")
        self.client = client

    def as_person(self, auth, by):
        return _Person(self, auth)

    def request(self, method, path, auth, body):
        if not self.url:
            raise ApiError(503, "this gateway has no local CONSOLE_URL")
        if self.client is None:
            from w2cplatform.tls import RoleClient, TLS_DIR
            self.client = RoleClient(self.env.get("W2C_TLS_DIR") or TLS_DIR,
                                     self.env.get("W2C_ROLE"), required_role="liveworker")
        raw = b"" if body is None else json.dumps(body, allow_nan=False).encode()
        headers = {"Content-Type": "application/json", "X-Operator": "liveworker"}
        if auth:
            headers["Authorization"] = auth
        try:
            status, answer, _ = self.client.request(method, self.url + path, raw, headers, role="console")
            doc = json.loads(answer)
            if not isinstance(doc, dict):
                raise ValueError("console answer is not an object")
        except (OSError, ValueError, UnicodeError) as error:
            raise ApiError(503, "the local console did not answer") from error
        if not 200 <= status < 300:
            raise ApiError(status, str(doc.get("detail") or doc.get("error") or "the console refused"))
        return doc


class _Person:
    def __init__(self, console, auth):
        self.console, self.auth = console, auth

    def do(self, method, path, body=None):
        return self.console.request(method, path, self.auth, body)
