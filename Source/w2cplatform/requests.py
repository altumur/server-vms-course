"""The request family's console side: `<sub>/requests/<id>`, bounded work somebody asked a unit's holder for (§3 row 3 of
the boundary note — the family whole in the platform, driven by the spec's `requests:`; it was one subsystem's code).

    filed       by the console (`POST /<sub>/requests`, the spec's schema, `SpecConsole._request_route`) or by another
                subsystem's worker (its spec's `worker: {requests: […]}`) — a row, named by its idempotency key
    performed   by the worker holding the unit, at most once, its answer in the heartbeat's `fetched` and in its mark
                `<sub>/commands/<id>` (`Worker.requests`)
    cleared     here: a row a holder answered goes (`clear_requests`, every `CLEAR_EVERY`, no row read); and on the reaper's
                slower turn (`sweep`) a row with a deadline nobody performed is ended `REAP_AFTER` past it — counted as
                expired, or as not known when a holder began it and went — and a row with none ends after the spec's `ttl`

A worker writes no configuration, so it cannot delete what it has done, only say that it did it; the console, which
reads the heartbeats already, removes the row — one writer per row.
"""
from __future__ import annotations

import hashlib
import json
import logging

from .rows import PARSE_ERRORS, finite

log = logging.getLogger(__name__)

CLEAR_EVERY = 2.0            # the answered rows: a holder may answer sixteen a second (the review's seventh pass, M6)
SWEEP_EVERY = 30.0           # the reaper's turn, which reads the rows
REAP_AFTER = 60.0            # past a deadline: a holder ends its own rows at it and says so within a heartbeat
MOST_VALID = 600.0           # the longest a request may wait, when the spec says no `most_valid`

# Requests ended unanswered, per subsystem — `expired` (nobody performed it) and `unknown` (a holder began it and went
# without saying how): counted here, said on `/metrics` (`metrics_lines`). One tally per process.
expired: dict[str, int] = {}
unknown: dict[str, int] = {}


def count_expired(sub: str) -> None:
    expired[sub] = expired.get(sub, 0) + 1


# How a holder says a request it answered, in its heartbeat's `fetched` (`Worker.fetched_said`), and how the console
# matches it: the id itself when it is short and plain; else `#` and a digest of it — an id of 200 characters, or one with
# a comma (the list's separator), a quote or a control character in it, costs 21 bytes like any other (the review's
# eighth pass).
def said_id(rid: str) -> str:
    rid = str(rid)
    if len(rid) <= 40 and not rid.startswith("#") and rid.isprintable() and not any(c in rid for c in ',"\\'):
        return rid
    return "#" + hashlib.sha256(rid.encode()).hexdigest()[:20]


def metrics_lines() -> list[str]:
    from .console import label
    return (["# TYPE w2c_requests_expired_total counter"]
            + [f'w2c_requests_expired_total{{sub="{label(s)}"}} {n}' for s, n in sorted(expired.items())]
            + ["# TYPE w2c_requests_unknown_total counter"]
            + [f'w2c_requests_unknown_total{{sub="{label(s)}"}} {n}' for s, n in sorted(unknown.items())])


# Whether the instance that marked a request still holds the name it marked under — its slot row, read now. A mark or a
# row that does not say, a store that does not answer: "still there" — nothing is ended on what cannot be read.
def _holder_still_there(ctl, said) -> bool:
    if not isinstance(said, dict) or not said.get("slot") or not said.get("instance"):
        return True
    try:
        items, _ = ctl.vars.get(ctl.sub.slot_key(str(said["slot"])))
    except Exception:                                       # noqa: BLE001 — not readable here (a cluster's console rights)
        return True
    if not isinstance(items, dict):
        return False                                        # no row at all: the name is nobody's
    return items.get("holder") == said["instance"] and items.get("released") != "true"


# One standing request with a deadline, looked at by the reaper: True when it was ended here. A deadline that is not a
# time is the holder's refusal when there is one; with none, the row ends once its filing is older than the longest a
# request may wait. BEGUN AND NOT ANSWERED (the review's thirteenth pass, minor): a mark with no outcome whose holder
# still holds the name it marked under is that holder's to answer; once the holder is gone, the row ends as NOT KNOWN.
def _end(ctl, key: str, it: dict, idx, now: float, most_valid: float) -> bool:
    try:
        until = finite(it.get("valid_until") or 0)
    except (TypeError, ValueError):
        until = 0.0
    if not until:
        try:
            until = finite(it.get("at")) + most_valid
        except (TypeError, ValueError):
            return False                                    # not known when it was filed either: not known to be over
    if now - until < REAP_AFTER:
        return False                                        # its holder's to end, if it has one
    rid = key.rsplit("/", 1)[1]
    try:
        mark = ctl.objects.get(f"{ctl.sub.name}/commands/{rid}")
    except Exception as e:                                  # noqa: BLE001 — one mark unread does not end the walk
        log.warning("%s: whether request %s was begun cannot be read (%s): left for the next turn", ctl.spec.name, rid, e)
        return False
    try:
        said = json.loads(mark) if mark else None
    except PARSE_ERRORS:
        said = {}
    begun = mark is not None and not (isinstance(said, dict) and said.get("outcome"))
    if begun and _holder_still_there(ctl, said):
        return False
    try:
        ctl.vars.delete(key, cas=idx)                       # by CAS: a row filed again under the same id is a new one
    except Exception:                                       # noqa: BLE001 — changed meanwhile, or the store: the next pass
        return False
    if isinstance(said, dict) and said.get("outcome"):
        log.info("%s: request %s was answered (%s) and its answer never reached a heartbeat: its row is cleared",
                 ctl.spec.name, rid, said.get("outcome"))
        return True
    if begun:
        unknown[ctl.spec.name] = unknown.get(ctl.spec.name, 0) + 1
        log.warning("%s: request %s for %s ended %.0f s past its deadline NOT KNOWN: its holder began it and is gone "
                    "without saying how it went", ctl.spec.name, rid, it.get("unit", "?"), now - until)
        return True
    count_expired(ctl.spec.name)
    log.warning("%s: request %s for %s ended unperformed %.0f s past its deadline — no worker held its unit to perform it",
                ctl.spec.name, rid, it.get("unit", "?"), now - until)
    return True


# The rows the holders answered, cleared — and with `sweep`, the reaper's look at every standing row: a row with a
# deadline (`valid_until`; in a family with no `ttl`, any action) nobody performed (`_end`), and a row with none older
# than the spec's `ttl` (an ask nobody
# could answer holds one of its person's places for good otherwise — the review's sixth pass); a row that names no unit
# is a list, not a request, and goes uncounted. Rows whose `action` the spec says another process serves
# (`requests.elsewhere`) are that process's to end.
def clear_requests(ctl, sweep: bool = True) -> int:
    from .console import heartbeats
    keys = ctl.vars.list(ctl.sub.requests_prefix())
    if not keys:
        return 0
    fetched: set[str] = set()
    for _, hb in heartbeats(ctl.objects, ctl.spec.name + "/").items():
        fetched |= {r for r in str(hb.extra.get("fetched", "")).split(",") if r}
    gone, now = 0, ctl.wall()
    declared = ctl.spec.requests or {}
    elsewhere = set(declared.get("elsewhere") or ())
    most_valid = float(declared.get("most_valid") or MOST_VALID)
    ttl = float(declared.get("ttl") or 0)
    for key in keys:
        rid = key.rsplit("/", 1)[1]
        if rid in fetched or said_id(rid) in fetched:       # a long id is said by its digest (the eighth pass)
            ctl.vars.delete(key)
            gone += 1
            continue
        if not sweep:
            continue                                        # the short cycle: answered rows only, nothing read
        it, idx = ctl.vars.get(key)
        if not it or str(it.get("action") or "") in elsewhere:
            continue
        if it.get("valid_until") not in (None, "") or (not ttl and it.get("action")):
            _end(ctl, key, it, idx, now, most_valid)        # a deadline: its holder ends it — or, with none, this
            continue
        if not ttl:
            continue
        try:
            old = now - finite(it.get("at", now) or now) > ttl
        except (TypeError, ValueError):
            old = False                                     # `nan` too: not known to be old (the seventh pass)
        if not old:
            continue
        try:
            ctl.vars.delete(key, cas=idx)                   # by CAS: asked again this instant, it is a new ask
        except Exception:                                   # noqa: BLE001 — changed meanwhile, or the store: the next pass
            continue
        if it.get("unit"):
            count_expired(ctl.spec.name)
            log.warning("%s: request %s stood for %.0f s unanswered and was ended", ctl.spec.name, rid, ttl)
    return gone


# One turn over the subsystems whose specs declare requests: what the console's housekeeping runs (`host.console`).
def turn(ctls, sweep: bool) -> None:
    for c in ctls:
        if not (c.spec.requests or c.spec.requests_free):
            continue
        try:
            n = clear_requests(c, sweep=sweep)
            if n:
                log.debug("%s: %d answered request(s) cleared", c.spec.name, n)
        except Exception:                                   # noqa: BLE001
            log.exception("clearing requests failed in %s — they stand until the next turn", c.spec.name)
