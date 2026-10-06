"""The request family's console side: `<sub>/requests/<id>`, bounded work somebody asked a unit's holder for (§3 row 3 of
the boundary note — the family whole in the platform, driven by the spec's `requests:`; it was one subsystem's code).

    filed       by the console (`POST /<sub>/requests`, the spec's schema, `SpecConsole._request_route`) or by another
                subsystem's worker (`Worker.file_request`: only to a subsystem its spec's `worker: {requests: […]}` names,
                refused otherwise on every store, ADR-0013) — a row, named by its idempotency key, written create-only
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

from .canonical import canonical_json, field_text
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


# THE SAME REQUEST, ONE DEFINITION FOR EVERY FILER (ADR-0013: filing is idempotent, PERFORMING is not more than once; the
# fourteenth review, major 1). When a request's id is taken, the row standing under it is read and compared with the one
# being filed — the same text, byte for byte, on one form (`canonical_json` over the items as the store holds them),
# leaving out only the filer's own moments, `moment`: what a retry of the same request cannot say the same — a worker's
# `filed` (`Worker.file_request`); at the console's door `at` when it stamps it and a deadline it gave itself
# (`SpecConsole._file_request`). Who filed it (`by`), for which unit, in which group, with what values — all compared:
# under one id, another person's request is ANOTHER request. The door answered it 202 with the stranger's row, and the
# person's own command was not filed; a worker's filing was refused. Now both are refused, by this one function.
#
# `(kind, why)`: `same` — the same request, filed before; `gone` — no row stands now (answered or ended meanwhile);
# `other` — a different request; `garbled` — a row that does not parse, never overwritten; `store` — not read.
def filed_already(vars_, key: str, out: dict, moment=("filed",)) -> tuple[str, str]:
    try:
        standing, _ = vars_.get(key)
    except PARSE_ERRORS as e:                               # a torn row (`Garbled`)
        return "garbled", f"the row standing under this rid does not parse ({e}); it is left as it is"
    except Exception as e:                                  # noqa: BLE001 — a store that did not answer
        return "store", f"the row standing under this rid cannot be read ({type(e).__name__}: {e}); it is left as it is"
    if standing is None:
        return "gone", "the row that stood under this rid is gone (performed or expired meanwhile); file under a new rid"
    same = (canonical_json({k: v for k, v in standing.items() if k not in moment}) ==
            canonical_json({k: v for k, v in out.items() if k not in moment}))
    return ("same", "") if same else ("other", "under this rid stands a different request")


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
# went — `performed`, `refused`, `unknown` or `expired`; beside a refusal and `unknown` its reason, `error`, at most
# `MARK_ERROR` characters, `…` the last of them where it was cut (a mark is read by every holder of the unit and by whoever
# asked: a reason is a sentence, not a payload — cut, never refused); `late: true` on an answer that came after the request was answered "did not answer";
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
    """A reason as a mark keeps it: at most `MARK_ERROR` characters, `…` among them where it was cut (ADR-0054: «not
    longer than 200» — it was 200 and `…`, 201; the fourteenth review, minor 15: 199 and `…`)."""
    why = str(why)
    return why if len(why) <= MARK_ERROR else why[:MARK_ERROR - 1] + "…"


# A FOREIGN MARK'S WORDS ARE CLIPPED WHERE THEY ARE SAID («Сборка», window 3; ADR-0054): a mark is written by another
# instance or by the reaper, so each of its words is another writer's data. Wherever a reader SAYS one — `instance` in
# `unknown: an earlier instance (…) began it`, `slot` and `outcome` in an answer said again, `outcome` in the reaper's
# line — it says `mark_text`: the word as a field says it (`field_text`: a string as it is, the rest its JSON), ONE LINE
# (every character that is not printable — a newline, a tab, a control character, U+2028 — a space) and at most
# `MARK_TEXT` characters, `…` where it was cut. A mark of 400 KB, or one with a newline in its `instance`, made every
# refusal, log line and event that quoted it as long and broke the journal's line (the product's eleventh review: its
# `markText`, 80 and `…`). What is said is clipped, never what is stored: the mark stays as its writer wrote it.
MARK_TEXT = 80


def mark_text(mark, key: str) -> str:
    """A word of a mark another wrote, as a reader says it: one line, `MARK_TEXT` characters at most and `…` where it
    was cut; "" when the mark has none."""
    v = mark.get(key) if isinstance(mark, dict) else None
    if v is None:
        return ""
    try:
        text = field_text(v)
    except PARSE_ERRORS:
        text = str(v)                                   # `NaN` from a mark that read: said, not refused
    text = "".join(c if c.isprintable() else " " for c in text[:MARK_TEXT + 1])   # one character for one: cut first
    return text if len(text) <= MARK_TEXT else text[:MARK_TEXT] + "…"


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
        said = None
    begun = mark is not None and not (isinstance(said, dict) and said.get("outcome"))
    # A MARK THAT DOES NOT READ IS NOBODY'S (the fourteenth review, minor 12; ADR-0054, 0012): not JSON, not an object, or
    # one that names no instance — whose it is cannot be read, so no holder is there to wait for. It was read as `{}`,
    # whose holder `_holder_still_there` takes for "still there", and the row stood for good (five hours on, a probe).
    # Past the deadline it ends NOT KNOWN like any begun request whose holder went: the row deleted by CAS, counted
    # `unknown`, and `complete_mark` writes `unknown` over the garbled mark by the index it read (a mark that does not
    # parse is `instance: ?` to it) — whoever asked reads an outcome; the beginner's answer, if one comes, still wins.
    nobodys = begun and not (isinstance(said, dict) and said.get("instance"))
    if begun and not nobodys and _holder_still_there(ctl, said):
        return False
    try:
        ctl.vars.delete(key, cas=idx)                       # by CAS: a row filed again under the same id is a new one
    except Exception:                                       # noqa: BLE001 — changed meanwhile, or the store: the next pass
        return False
    if isinstance(said, dict) and said.get("outcome"):
        log.info("%s: request %s was answered (%s) and its answer never reached a heartbeat: its row is cleared",
                 ctl.spec.name, rid, mark_text(said, "outcome"))
        return True
    if begun:
        unknown[ctl.spec.name] = unknown.get(ctl.spec.name, 0) + 1
        why = ("its mark does not read: whoever began it is not known, nor how it went" if nobodys
               else "its holder began it and is gone without saying how it went")
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
# (the resource's `free-…`) has no mark to read, and goes uncounted. Rows whose `action` the spec says another process
# serves (`requests.elsewhere`) are that process's to end. A person's ledger is no row of this family (ADR 0060): it is
# `<sub>/asked/…`, and on the same slower turn one nobody has written for `ttl` goes (`clear_asked`).
def clear_requests(ctl, sweep: bool = True) -> int:
    from .console import heartbeats
    if sweep:
        clear_asked(ctl)
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
            ctl.vars.delete(key, cas=idx)                   # a row naming no unit (`free-…`) has no mark to read
        except Exception:                                   # noqa: BLE001 — changed meanwhile, or the store: the next pass
            continue
    return gone


# THE PEOPLE'S LEDGERS, `<sub>/asked/<sha256 of the person, 16 hex>` (`per_person`, the console's; ADR 0060): one nobody
# has written for the spec's `ttl` names no request that still counts — every entry is older — and goes, by CAS (a
# ledger written meanwhile is a new one). `ttl: 0`: none goes by age, as no request does. A ledger that does not read
# is the administrator's to delete (`DELETE /asked/<name>`): it stops its person, said on `/metrics`; it is not swept.
def clear_asked(ctl) -> int:
    declared = ctl.spec.requests or {}
    ttl = declared.get("ttl")
    if "per_person" not in declared or not ttl:
        return 0
    gone, now = 0, ctl.wall()
    for key in ctl.vars.list(ctl.sub.asked_prefix()):
        try:
            it, idx = ctl.vars.get(key)
            old = bool(it) and now - finite(it.get("at")) > ttl
        except (*PARSE_ERRORS, OSError):
            continue                                        # not read, or not known when it was written: it stays
        if not old:
            continue
        try:
            ctl.vars.delete(key, cas=idx)
            gone += 1
        except Exception:                                   # noqa: BLE001 — written meanwhile, or the store: the next turn
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
