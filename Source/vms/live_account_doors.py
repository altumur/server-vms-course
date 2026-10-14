"""C5 HTTP shapes over cluster-owned accounts; the gateway authenticates first."""
from w2cplatform.domain.api import ApiError

from .live_accounts import valid_name


class AccountDoors:
    """Adapt an authenticated gateway request to LiveAccounts, without a second server."""

    def __init__(self, accounts):
        self.accounts = accounts

    def serves(self, path):
        return path == "/live/accounts" or path.startswith("/live/accounts/")

    def handle(self, method, path, body, auth, by):
        try:
            return 200, self._handle(method, path, body, auth, by)
        except ApiError as error:
            if error.status == 405:
                return 405, {"error": error.detail}
            return error.status, {"error": "refused", "detail": error.detail}

    def _handle(self, method, path, body, auth, by):
        if not self.serves(path):
            raise ApiError(404, "no such account route")
        if path == "/live/accounts":
            if method == "GET":
                # C5 omitempty applies only to this list response, never to the durable doc.
                return {"accounts": [{key: value for key, value in doc.items()
                                      if key == "name" or value}
                                     for doc in self.accounts.listing()]}
            if method == "POST":
                if not isinstance(body, dict):
                    raise ApiError(400, "{name} must be an object")
                name = body.get("name")
                password = self.accounts.create(name, auth, by)
                return {"account": name, "password": password}
            raise ApiError(405, "GET or POST {name}")
        name, _, rest = path[len("/live/accounts/"):].partition("/")
        if not valid_name(name) or rest not in ("", "password"):
            raise ApiError(404, "no such account route")
        if rest == "password":
            if method != "POST":
                raise ApiError(405, "POST")
            return {"account": name, "password": self.accounts.reset_password(name, by)}
        if method == "PUT":
            if not isinstance(body, dict) or type(body.get("disabled")) is not bool:
                raise ApiError(400, "{disabled: true|false}")
            disabled = body["disabled"]
            self.accounts.set_disabled(name, disabled, by)
            return {"account": name, "disabled": disabled}
        if method == "DELETE":
            return {"account": name, "deleted": True,
                    "grants_changed": self.accounts.delete(name, auth, by)}
        raise ApiError(405, "POST …/password, PUT {disabled}, DELETE")
