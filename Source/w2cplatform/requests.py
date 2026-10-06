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

from .canonical import canonical_json
from .rows import PARSE_ERRORS, finite

log = logging.getLogger(__name__)

CLEAR_EVERY = 2.0            # the answered rows: a holder may answer sixteen a second (the review's seventh pass, M6)
SWEEP_EVERY = 30.0           # the reaper's turn, which reads the rows
REAP_AFTER = 60.0            # past a deadline: a holder ends its own rows at it and says so within a heartbeat

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


# EVERY REQUEST ENDS WITH ITS OUTCOME IN ITS MARK (ADR-0054): `<sub>/commands/<id>`, where whoever asked reads how it
# went — `performed`, `refused`, `unknown` or `expired`; beside a refusal and `unknown` its reason, `error`, cut to
# `MARK_ERROR` characters (a mark is read by every holder of the unit and by whoever asked: a reason is a sentence, not a
# payload — cut, never refused); `late: true` on an answer that came after the request was answered "did not answer";
# `ended_by: reaper` on the console's `expired`. Who writes what, and whose word wins:
#
#   the holder   its begun mark create-only before the call, its answer over it after (`Worker._confirm`) — over another
#                instance's or the reaper's word too: the holder's answer is the truth of what was done to the unit; a
#                refusal before any call, and `expired` for a request nobody began, create-only (`Worker._end_mark`);
#                `unknown` into another instance's mark with no outcome, that instance kept (`complete_mark`, by the index
#                it read)
#   the reaper   `expired` for a request nobody began, create-only, `ended_by: reaper` and `ended_at` (`_ended_mark`);
#                `unknown` into a mark with no outcome whose holder is gone (`complete_mark`); a mark with an outcome — never
#
# BEGUN IS NOT EXPIRED: a mark with no outcome past the deadline is `unknown` — whoever began it may have acted on the
# unit; `expired` is a request nobody began. The product's `MarkError`, `CompleteMark`, `endedMark`, byte for byte.
MARK_ERROR = 200


def mark_error(why: str) -> str:
    """A reason as a mark keeps it: at most `MARK_ERROR` characters, and `…` where it was cut."""
    why = str(why)
    return why if len(why) <= MARK_ERROR else why[:MARK_ERROR] + "…"


# A CLOSER WRITES BY THE INDEX IT READ (ADR-0054, the architect's amendment): whoever completes a mark it did not begin —
# the reaper, a holder's `unknown` — reads the mark with its index (`get_at`) and writes by it (`put_at`). A conflict
# means somebody wrote the mark meanwhile: read again; an outcome there now — stop, the beginner's answer stands, it is
# the truth; none — write again by the new index, `CLOSE_ATTEMPTS` times at most. The holder's own answer is no closer's:
# `Worker._confirm` writes it unconditionally, the one writer that knows what was done to the unit.
CLOSE_ATTEMPTS = 8


def complete_mark(objects, key: str, outcome: str, why: str, at: float) -> bool:
    """Writes `outcome` (and `why`, as `mark_error`) into the mark at `key` while it stands with none — the request's end
    said by whoever saw it end, the mark's `instance` and `slot` kept, `ended_at` beside them — by the index read. True
    when written; False when an outcome stands (or appeared), when there is no mark to complete, or after
    `CLOSE_ATTEMPTS` conflicts. A mark that does not parse is a mark of nobody known (`instance: ?`)."""
    for _ in range(CLOSE_ATTEMPTS):
        raw, index = objects.get_at(key)
        if raw is None:
            return False                                    # gone (swept with its row): nothing begun to close
        try:
            mark = json.loads(raw)
        except PARSE_ERRORS:
            mark = None
        if not isinstance(mark, dict):
            mark = {"instance": "?"}
        if mark.get("outcome"):
            return False                                    # answered meanwhile: the beginner's word is the truth
        out = {**mark, "outcome": outcome, "ended_at": at}
        if why:
            out["error"] = mark_error(why)
        if objects.put_at(key, canonical_json(out).encode(), index):
            return True
    log.warning("%s: the mark was written by others %d times while it was being completed %s: left as it stands", key,
                CLOSE_ATTEMPTS, outcome)
    return False


# The reaper's end of a request nobody began, into its mark, CREATE-ONLY — never over a mark that stands: a holder's
# beginning or answer is the holder's. It says it is the reaper's word (`ended_by`). A store without create-only: none.
def _ended_mark(ctl, rid: str, it: dict, outcome: str, now: float) -> None:
    put_new = getattr(ctl.objects, "put_new", None)
    if put_new is None:
        return
    mark = {"unit": str(it.get("unit", "")), "outcome": outcome, "at": now, "ended_by": "reaper", "ended_at": now}
    if it.get("action"):
        mark["action"] = str(it["action"])
    try:
        put_new(ctl.sub.command_key(rid), canonical_json(mark).encode())
    except Exception as e:                                  # noqa: BLE001 — the row is ended; its mark is not written
        log.warning("%s: request %s ended %s, and its mark was not written (%s)", ctl.spec.name, rid, outcome, e)


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
# request may wait — the spec's `most_valid`, declared with `valid_for` (ADR 0012); a family that declares neither has
# no such bound, and the row is not known to be over. BEGUN AND NOT ANSWERED (the review's thirteenth pass, minor): a
# mark with no outcome whose holder still holds the name it marked under is that holder's to answer; once the holder is
# gone, the row ends as NOT KNOWN.
def _end(ctl, key: str, it: dict, idx, now: float, most_valid) -> bool:
    try:
        until = finite(it.get("valid_until") or 0)
    except (TypeError, ValueError):
        until = 0.0
    if not until:
        if most_valid is None:
            return False
        try:
            until = finite(it.get("at")) + most_valid
        except (TypeError, ValueError):
            return False                                    # not known when it was filed either: not known to be over
    if now - until < REAP_AFTER:
        return False                                        # its holder's to end, if it has one
    return _close(ctl, key, it, idx, now, f"{now - until:.0f} s past its deadline")


# ONE RULE FOR BOTH OF THE REAPER'S PATHS (ADR 0054; the product's 1315207 found the second going past the mark): a
# deadline passed, or a row with none older than `ttl`. The mark not read — wait; an outcome in it — the row is cleared;
# no outcome and its holder still there — wait; its holder gone — `unknown`; no mark — `expired`.
def _close(ctl, key: str, it: dict, idx, now: float, how: str) -> bool:
    rid = key.rsplit("/", 1)[1]
    try:
        mark = ctl.objects.get(ctl.sub.command_key(rid))
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
        why = "its holder began it and is gone without saying how it went"
        try:
            complete_mark(ctl.objects, ctl.sub.command_key(rid), "unknown", why, now)   # by the index it reads
        except Exception as e:                              # noqa: BLE001 — the row is ended; its mark says less
            log.warning("%s: request %s ended not known, and its mark was not completed (%s)", ctl.spec.name, rid, e)
        log.warning("%s: request %s for %s ended %s NOT KNOWN: %s", ctl.spec.name, rid, it.get("unit", "?"), how, why)
        return True
    count_expired(ctl.spec.name)
    _ended_mark(ctl, rid, it, "expired", now)
    log.warning("%s: request %s for %s ended unperformed %s — no worker held its unit to perform it",
                ctl.spec.name, rid, it.get("unit", "?"), how)
    return True


# The rows the holders answered, cleared — and with `sweep`, the reaper's look at every standing row: a row with a
# deadline (`valid_until`; in a family with no `ttl`, any action) nobody performed (`_end`), and a row with none older
# than the spec's `ttl` (an ask nobody could answer holds one of its person's places for good otherwise — the review's
# sixth pass); `ttl: 0` ends none by age — the spec said so, nothing assumed it (2026-10-05); a row that names no unit
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
    most_valid = declared.get("most_valid")                 # the declared one, no other: the loader requires it with `valid_for`
    ttl = declared.get("ttl")                               # None: a family of deadlines (`valid_for`); 0: no limit, said
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
        if it.get("valid_until") not in (None, "") or (ttl is None and it.get("action")):
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
        if it.get("unit"):
            _close(ctl, key, it, idx, now, f"standing past its ttl ({ttl} s)")   # the mark read first, as by deadline
            continue
        try:
            ctl.vars.delete(key, cas=idx)                   # a row naming no unit is a list, not a request: no mark
        except Exception:                                   # noqa: BLE001 — changed meanwhile, or the store: the next pass
            continue
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
