"""ADR-0074 C2: explicit member CRUD, kept before applying through its console."""
from __future__ import annotations
import hashlib
import json
import math
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from w2cplatform.variables import Conflict
from w2cplatform.secrets import hide_in_reply
from w2cplatform.rows import PARSE_ERRORS
from .api import ApiError, said
from .federation import MEMBER_OBJECTS, Unreachable

PENDING_PATH, OUTCOMES_PATH = "domain/pending", "domain/outcomes"
OUTCOMES_LIMIT = 50


def _outcome_order(item):
    from w2cplatform.rows import finite
    identity, raw = item
    try:
        at = json.loads(raw)["at"]
        if type(at) not in (int, float):
            raise ValueError("invalid outcome time")
        at = finite(at)
    except PARSE_ERRORS:
        at = -math.inf
    return at, identity


def _transient(status, result):
    return status == 409 and isinstance(result, dict) and result.get("error") in ("in flight", "taken over")


def _load(items, path):
    out = {}
    for key, raw in (items or {}).items():
        try:
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError("not an object")
            out[key] = value
            MEMBER_OBJECTS.parsed(path + "#" + key)
        except PARSE_ERRORS as err:
            MEMBER_OBJECTS.garbled(path + "#" + key, err)
    return out


def edit_id(member, key):
    return "e-" + hashlib.sha256((member + "\0" + key).encode()).hexdigest()[:12]


def validate_edit(entry):
    if set(entry) != {"id", "what", "method", "path", "body", "key", "at"}:
        raise ValueError("invalid Edit fields")
    if entry["method"] not in ("POST", "PUT", "DELETE") or not isinstance(entry["body"], dict):
        raise ValueError("invalid CRUD operation")
    if not isinstance(entry["key"], str) or not entry["key"] or not isinstance(entry["path"], str):
        raise ValueError("invalid edit key or path")
    parts = entry["path"].split("/")
    if len(parts) not in (3, 4) or parts[0] or any(not p or p in (".", "..") or any(c in p for c in "?#%\\") for p in parts[1:]):
        raise ValueError("invalid member path")
    if (entry["method"] == "POST") != (len(parts) == 3):
        raise ValueError("method does not match unit path")
    if not isinstance(entry["what"], str) or entry["what"] != ",".join(sorted(entry["body"])):
        raise ValueError("invalid field names")
    from w2cplatform.rows import finite
    if type(entry["at"]) not in (int, float):
        raise ValueError("invalid edit time")
    finite(entry["at"])
    if not isinstance(entry["id"], str) or not entry["id"]:
        raise ValueError("invalid edit identity")
    return entry


class PendingEdits:
    def __init__(self, domain_vars, wall=time.time):
        self.vars, self.wall = domain_vars, wall

    def of(self, member):
        return _load(self.vars.get(PENDING_PATH + "/" + member)[0], PENDING_PATH + "/" + member)

    def add(self, member, method, path, body, key, retries=20):
        if not isinstance(member, str) or not member or "/" in member or not isinstance(key, str) or not key:
            raise ApiError(400, "member and Idempotency-Key are required")
        identity = edit_id(member, key)
        entry = {"id": identity, "what": ",".join(sorted(body)), "method": method,
                 "path": path, "body": body, "key": key}
        target = PENDING_PATH + "/" + member
        for _ in range(retries):
            items, idx = self.vars.get(target)
            entries = _load(items, target)
            old = entries.get(identity)
            if old is not None:
                if any(old.get(k) != entry[k] for k in ("method", "path", "body", "key")):
                    raise ApiError(422, "Idempotency-Key was used for another operation")
                return old
            if identity in (items or {}):
                raise ApiError(422, "the original edit is unreadable; this key cannot be reused")
            entry["at"] = self.wall()
            validate_edit(entry)
            outcome_path = OUTCOMES_PATH + "/" + member
            outcome = _load(self.vars.get(outcome_path)[0], outcome_path).get(identity)
            if outcome is not None:
                try:
                    from w2cplatform.rows import finite
                    if set(outcome) != {"id", "status", "result", "error", "at", "what", "kept_at"} \
                            or outcome["id"] != identity or type(outcome["status"]) is not int \
                            or not (outcome["status"] == 0 or 100 <= outcome["status"] < 500) \
                            or not isinstance(outcome["what"], str) or not isinstance(outcome["error"], str) \
                            or type(outcome["at"]) not in (int, float) or type(outcome["kept_at"]) not in (int, float):
                        raise ValueError("invalid Outcome")
                    finite(outcome["at"])
                    kept_at = finite(outcome["kept_at"])
                except PARSE_ERRORS as err:
                    MEMBER_OBJECTS.garbled(outcome_path + "#" + identity, err)
                else:
                    entry["at"] = max(entry["at"], math.nextafter(kept_at, math.inf))
            validate_edit(entry)
            try:
                self.vars.put(target, {**(items or {}), identity: json.dumps(entry, ensure_ascii=False, sort_keys=True)}, cas=idx)
                return entry
            except Conflict:
                continue
        raise ApiError(409, "the edit changed concurrently; retry")

    def reconcile(self, member, outcomes):
        """Store terminal Outcomes before removing exactly the Edits they settled.

        A restart between writes repeats settlement safely. The pending CAS
        preserves concurrent additions.
        """
        pending_path, target = PENDING_PATH + "/" + member, OUTCOMES_PATH + "/" + member
        waiting, _ = self.vars.get(pending_path)
        edits, accepted = _load(waiting, pending_path), {}
        for identity, outcome in outcomes.items():
            try:
                if identity not in edits:
                    continue
                validate_edit(edits[identity])
                if set(outcome) != {"id", "status", "result", "error", "at", "what", "kept_at"} or outcome["id"] != identity \
                        or type(outcome["status"]) is not int or not (outcome["status"] == 0 or 100 <= outcome["status"] < 500) \
                        or not isinstance(outcome["error"], str) or outcome["what"] != edits[identity]["what"] \
                        or type(outcome["at"]) not in (int, float) or type(outcome["kept_at"]) not in (int, float):
                    raise ValueError("invalid Outcome")
                from w2cplatform.rows import finite
                finite(outcome["at"])
                finite(outcome["kept_at"])
                if outcome["kept_at"] != edits[identity]["at"]:
                    continue
                if _transient(outcome["status"], outcome["result"]):
                    continue
                accepted[identity] = json.dumps(hide_in_reply({**outcome, "result": said(outcome["result"])}),
                                                ensure_ascii=False, sort_keys=True)
            except PARSE_ERRORS as err:
                MEMBER_OBJECTS.garbled(member + "/" + OUTCOMES_PATH + "#" + identity, err)
        if not accepted:
            return
        for _ in range(20):
            items, idx = self.vars.get(target)
            fresh = dict(sorted({**(items or {}), **accepted}.items(),
                                key=_outcome_order, reverse=True)[:OUTCOMES_LIMIT])
            try:
                if fresh != (items or {}):
                    self.vars.put(target, fresh, cas=idx)
                break
            except Conflict:
                continue
        else:
            raise ApiError(409, "outcomes changed concurrently; retry")
        for _ in range(20):
            items, idx = self.vars.get(pending_path)
            fresh = {k: v for k, v in (items or {}).items() if k not in accepted or v != waiting[k]}
            try:
                if fresh != (items or {}):
                    self.vars.put(pending_path, fresh, cas=idx)
                return
            except Conflict:
                continue
        raise ApiError(409, "pending edits changed concurrently; retry")

    def collect(self, fed):
        for member, cluster in fed.clusters.items():
            try:
                # The agent writes only its Outcome; the holder's role owns settlement.
                # Its own agent needs no report or carry connection back to itself.
                path = OUTCOMES_PATH
                source = self.vars if cluster.is_domain_holder else cluster.vars
                self.reconcile(member, _load(source.get(path)[0], member + "/" + path))
            except Unreachable:
                continue


def apply_pending(entries, console, now, previous=None):
    # The member console remembers idempotency. A completed key can be queued
    # again; a previous Outcome must not suppress the new request.
    # Absence from this confirmed pending snapshot acknowledges the outcome.
    outcomes = {}
    for identity, entry in entries.items():
        try:
            validate_edit(entry)
            if entry["id"] != identity:
                raise ValueError("edit key differs from identity")
        except PARSE_ERRORS as err:
            MEMBER_OBJECTS.garbled(PENDING_PATH + "#" + identity, err)
            continue
        prior = (previous or {}).get(identity)
        if isinstance(prior, dict) and set(prior) == {"id", "status", "result", "error", "at", "what", "kept_at"} \
                and prior["id"] == identity and type(prior["status"]) is int and 100 <= prior["status"] < 500 \
                and type(prior["kept_at"]) in (int, float) and prior["kept_at"] == entry["at"] \
                and prior["what"] == entry["what"] and not _transient(prior["status"], prior["result"]):
            outcomes[identity] = prior
            continue
        try:
            status, result = console.apply(entry)
        except Unreachable:
            continue
        except ApiError as err:
            status, result = err.status, {"detail": err.detail}
        if type(status) is not int or not 100 <= status < 500 or _transient(status, result):
            continue
        outcomes[identity] = {"id": identity, "status": status, "result": said(result),
                              "error": str(result.get("detail", "")) if status >= 400 and isinstance(result, dict) else "",
                              "at": now, "what": entry["what"], "kept_at": entry["at"]}
    return hide_in_reply(outcomes)


class AgentConsole:
    """The member's one local console; its private key stays in the agent."""
    def __init__(self, url, key, wall=time.time):
        self.url, self.key, self.wall = url.rstrip("/"), key, wall

    def apply(self, entry):
        from w2cplatform.trust.memberkey import sign_request
        body = json.dumps(entry["body"], ensure_ascii=False, sort_keys=True).encode()
        headers = {"Content-Type": "application/json", "Idempotency-Key": entry["key"],
                   "X-Agent-Signature": sign_request(self.key, entry["method"], entry["path"], body, self.wall())}
        request = Request(self.url + entry["path"], data=body, headers=headers, method=entry["method"])
        try:
            with urlopen(request, timeout=5) as reply:
                return reply.status, self._reply(reply)
        except HTTPError as err:
            with err:
                return err.code, self._reply(err)
        except (URLError, OSError) as err:
            raise Unreachable("the member console did not answer") from err

    @staticmethod
    def _reply(reply):
        from w2cplatform.canonical import parse_json
        raw = reply.read((1 << 20) + 1)
        if len(raw) > 1 << 20:
            raise Unreachable("the member console reply exceeds its limit")
        try:
            return parse_json(raw)
        except PARSE_ERRORS:
            raise Unreachable("the member console reply is incomplete or invalid") from None
