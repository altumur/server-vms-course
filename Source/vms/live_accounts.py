"""C5 cluster-owned RTSP accounts and ordinary gateway book publication."""
from __future__ import annotations

import base64
import json
import math
import os
import time

from w2cplatform.contract import parse_heartbeat
from w2cplatform.domain.api import ApiError
from w2cplatform.domain.carry import open_row, seal_row
from w2cplatform.domain.grants import name_refused
from w2cplatform.domain.memberbook import holds, read as member_book
from w2cplatform.sealing import Sealed, is_sealed, seal_items
from w2cplatform.variables import Conflict

ACCOUNTS = "live/accounts/"
BOOK = "domain/live/stream-accounts"
INPUT = "live/stream-accounts/"


def valid_name(name):
    return isinstance(name, str) and name_refused(name, "account name", also='/:() \\') is None \
        and name not in ("break-glass", ".", "..")


def _object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate account field")
        out[key] = value
    return out


def _parse(raw):
    value = json.loads(raw, object_pairs_hook=_object)
    json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    return value


def _names(value):
    if not isinstance(value, list) or any(not isinstance(name, str) or not name for name in value) \
            or len(set(value)) != len(value):
        raise ValueError("invalid account member names")
    return value


def _record(vars_, name):
    path = ACCOUNTS+name
    items, index = vars_.get(path)
    if items is None:
        return None, None, index
    try:
        if not isinstance(items, dict) or set(items) != {"doc", "password_secret"}:
            raise ValueError()
        doc = _parse(items["doc"])
        if not isinstance(doc, dict) or set(doc) != {"name", "disabled", "at", "by"} or doc["name"] != name \
                or not valid_name(name) or type(doc["disabled"]) is not bool or not isinstance(doc["by"], str) \
                or type(doc["at"]) not in (int, float) or not math.isfinite(doc["at"]):
            raise ValueError()
        return doc, items, index
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError, UnicodeError):
        raise ApiError(503, "the account record cannot be read") from None


def _local(vars_, name, sealer):
    doc, items, index = _record(vars_, name)
    if doc is None:
        return None, "", index
    try:
        password = open_row(sealer, items, ACCOUNTS+name)["password_secret"]
        if not isinstance(password, str) or not password or is_sealed(password):
            raise ValueError()
        return doc, password, index
    except (ValueError, TypeError, KeyError, Sealed):
        raise ApiError(503, "the account password cannot be opened") from None


def _book(vars_, own, sealer):
    path = BOOK+"/"+own if holds(vars_, own) else BOOK
    items = member_book(vars_, BOOK, own)
    if not isinstance(items, dict):
        raise ValueError("missing account book")
    return open_row(sealer, items, path)


def _facts(items, name, *, complete=True):
    marker = _parse(items[""])
    if not isinstance(marker, dict) or set(marker) != {"missing"}:
        raise ValueError("invalid account completeness")
    missing = _names(marker["missing"])
    if complete and missing:
        raise ValueError("incomplete account book")
    if not name or name not in items:
        return []
    row = _parse(items[name])
    if not isinstance(row, dict) or set(row) != {"entries", "missing"} or row["missing"] != missing \
            or not isinstance(row["entries"], list):
        raise ValueError("invalid account envelope")
    seen = set()
    for entry in row["entries"]:
        if not isinstance(entry, dict) or set(entry) != {"member", "item", "value"} \
                or any(not isinstance(entry[k], str) or not entry[k] for k in ("member", "item")) \
                or (entry["member"], entry["item"]) in seen or not isinstance(entry["value"], dict) \
                or entry["value"].get("name") != name:
            raise ValueError("invalid account origin")
        seen.add((entry["member"], entry["item"]))
    return row["entries"]


def stream_accounts(vars_, cluster, sealer=None):
    """Only unique complete delivered observations authorize RTSP; never local table fallback."""
    try:
        items = _book(vars_, cluster, sealer)
        # Even an empty book must carry an intact completeness marker.
        _facts(items, "")
        out = {}
        for name in sorted(set(items)-{""}):
            entries = _facts(items, name)
            if len(entries) != 1:
                continue
            value = entries[0]["value"]
            if not valid_name(name) or set(value) != {"name", "to", "disabled", "password_secret"} \
                    or cluster not in _names(value["to"]) or type(value["disabled"]) is not bool \
                    or not isinstance(value["password_secret"], str) or not value["password_secret"] \
                    or is_sealed(value["password_secret"]):
                raise ValueError("invalid account observation")
            if not value["disabled"]:
                out[name] = value["password_secret"]
        return out
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError, UnicodeError, Sealed):
        return {}


def accounts(worker, status):
    """The smallest fresh gateway derives its slot contribution from persistent cluster rows."""
    from .recording_publication import member
    own = member(worker.vars)
    sealer = getattr(worker, "sealer", None)
    if not own or sealer is None:
        return {}
    live = []
    for key in worker.objects.list("live/heartbeats/"):
        hb = parse_heartbeat(key, worker.objects.get(key))
        if hb is not None and worker.eyes.fresh(key, hb.token, 45):
            live.append(hb.worker)
    if not live or worker.name != min(live):
        return {}
    from w2cplatform.domain.memberbook import members
    try:
        to = list(members(worker.vars, own))
        if not to or own not in to:
            return {}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError, UnicodeError):
        return {}
    out = {}
    for path in worker.vars.list(ACCOUNTS):
        name = path[len(ACCOUNTS):]
        if not valid_name(name):
            continue
        try:
            doc, password, _ = _local(worker.vars, name, sealer)
        except ApiError:
            continue
        if doc is not None:
            out[name] = json.dumps({"name": name, "to": to, "disabled": doc["disabled"],
                                    "password_secret": password}, sort_keys=True)
    return seal_row(sealer, out, INPUT+worker.name)


class LiveAccounts:
    """Gateway-owned records; domain operations go through its local console as the original person."""
    def __init__(self, vars_, objects_=None, *, sealer=None, console=None, wall=time.time):
        self.vars, self.objects, self.sealer, self.console, self.wall = vars_, objects_, sealer, console, wall

    def _door(self, auth, by):
        if self.console is None:
            raise ApiError(503, "this gateway has no local console client")
        return self.console.as_person(auth, by)

    def _put(self, name, doc, password, index):
        if self.sealer is None:
            raise ApiError(503, "this gateway has no account sealing ring")
        if type(doc.get("at")) not in (int, float) or not math.isfinite(doc["at"]) or not isinstance(doc.get("by"), str):
            raise ApiError(503, "the account author or clock is unavailable")
        path = ACCOUNTS+name
        items = seal_items(self.sealer, {"doc": json.dumps(doc, sort_keys=True), "password_secret": password}, path)
        try:
            self.vars.put(path, items, cas=index)
        except Conflict:
            raise ApiError(409, "the account changed; read it again") from None

    def _required(self, name, *, with_password=True):
        if not valid_name(name):
            raise ApiError(400, "invalid account name")
        doc, password, index = _local(self.vars, name, self.sealer) if with_password else _record(self.vars, name)
        if doc is None:
            raise ApiError(404, "no such account")
        return doc, password, index

    def listing(self):
        out = []
        for path in sorted(self.vars.list(ACCOUNTS)):
            name = path[len(ACCOUNTS):]
            if valid_name(name):
                doc, _, _ = _record(self.vars, name)
                if doc is not None:
                    out.append(doc)
        return out

    def create(self, name, auth, by):
        if not valid_name(name):
            raise ApiError(400, "invalid account name")
        if self.sealer is None:
            raise ApiError(503, "this gateway has no account sealing ring")
        path = ACCOUNTS+name
        have, index = self.vars.get(path)
        if have is not None:
            raise ApiError(409, "there is a local account with this name")
        users = self._door(auth, by).do("GET", "/domain/users")
        if not isinstance(users, dict) or not isinstance(users.get("users"), list) \
                or any(not isinstance(user, dict) or not isinstance(user.get("name"), str) for user in users["users"]):
            raise ApiError(503, "the local console did not provide the people list")
        if any(user["name"] == name for user in users["users"]):
            raise ApiError(409, "there is a person with this name")
        from .recording_publication import member
        own = member(self.vars)
        if own:
            try:
                items = member_book(self.vars, BOOK, own)
                known = _facts(items, name, complete=False) if isinstance(items, dict) else []
            except (ValueError, TypeError, KeyError, OverflowError, RecursionError, UnicodeError):
                known = []                              # this deliberately partial check cannot reserve a global name
            if known:
                raise ApiError(409, "there is an account with this name in the delivered book")
        password = base64.urlsafe_b64encode(os.urandom(24)).decode().rstrip("=")
        now = self.wall()
        if type(now) not in (int, float) or not math.isfinite(now) or not isinstance(by, str):
            raise ApiError(503, "the account author or clock is unavailable")
        self._put(name, {"name": name, "disabled": False, "at": now, "by": by}, password, index)
        return password

    def reset_password(self, name, by):
        doc, _, index = self._required(name, with_password=False)
        password = base64.urlsafe_b64encode(os.urandom(24)).decode().rstrip("=")
        self._put(name, {**doc, "at": self.wall(), "by": by}, password, index)
        return password

    def set_disabled(self, name, disabled, by):
        if type(disabled) is not bool:
            raise ApiError(400, "disabled must be a boolean")
        doc, password, index = self._required(name)
        self._put(name, {**doc, "disabled": disabled, "at": self.wall(), "by": by}, password, index)

    def delete(self, name, auth, by):
        _, _, index = self._required(name, with_password=False)
        door = self._door(auth, by)
        reply = door.do("GET", "/domain/grants")
        if not isinstance(reply, dict) or not isinstance(reply.get("grants"), dict):
            raise ApiError(503, "the local console did not provide the grants")
        updates = []
        for cluster, lines in sorted(reply["grants"].items()):
            if not isinstance(cluster, str) or not cluster or "/" in cluster or not isinstance(lines, list) \
                    or any(not isinstance(line, dict) or not isinstance(line.get("subject"), str) for line in lines):
                raise ApiError(503, "the local console did not provide valid grants")
            kept = [line for line in lines if line["subject"] != name]
            if len(kept) != len(lines):
                updates.append((cluster, kept))
        changed = []
        for cluster, lines in updates:
            door.do("PUT", "/domain/grants/"+cluster, {"lines": lines})
            changed.append(cluster)
        try:
            self.vars.delete(ACCOUNTS+name, cas=index)
        except Conflict:
            raise ApiError(409, "the account changed while revoking grants; retry deletion") from None
        return changed
