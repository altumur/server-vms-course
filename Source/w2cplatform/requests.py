"""The request family's console side: `<sub>/requests/<id>`, bounded work somebody asked a unit's holder for (§3 row 3 of
the boundary note — the family whole in the platform, driven by the spec's `requests:`; it was one subsystem's code).

    filed       through the family's door, `file` here — the console's `POST /<sub>/requests` and a subsystem's own
                housekeeping process: the spec's schema, key, deadline, stamps, count and journal, the fifteenth
                review's major 4 — or by another subsystem's worker (`Worker.file_request`: only to a subsystem its
                spec's `worker: {requests: […]}` names, refused otherwise on every store, ADR-0013) — a row, named by
                its idempotency key, written create-only; an id whose mark stands is answered by the mark (major 2)
    performed   by the worker holding the unit, at most once, its answer in the heartbeat's `fetched` and in its mark
                `<sub>/commands/<id>` (`Worker.requests`); an action another process performs (`elsewhere`) by that
                process, its outcome in the same mark
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
from .rows import PARSE_ERRORS, Table, finite

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
# (`requests.file`, the family's door). Who filed it (`by`), for which unit, in which group, with what values — all compared:
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
# A target that did not answer within `PERFORM_TIMEOUT` is `unknown` too, in the holder's own begun mark, by the index
# read (`Worker._timed_out`, the review's fourteenth pass, major 6): whether it acted is not known; its late answer is
# written over it, `late: true`.
#
# EVERY MARK SAYS WHAT REQUEST IT IS ABOUT (`mark_request`; the review's fourteenth pass, major 2, «Архитектор»
# 2026-10-06): its deadline `valid_until` and its `digest`. The mark is what holds "not more than once" after the row is
# gone — a request filed again under the same id, after the evaluator moved, finds it — so it is kept at least until the
# request could no longer be performed (`mark_kept_until`), and a refiling reads it (`Worker.file_request`).
#
# BEGUN IS NOT EXPIRED: a mark with no outcome past the deadline is `unknown` — whoever began it may have acted on the
# unit; `expired` is a request nobody began. The product's `MarkError`, `CompleteMark`, `endedMark`, byte for byte.
MARK_ERROR = 200


def mark_error(why: str) -> str:
    """A reason as a mark keeps it: at most `MARK_ERROR` characters, `…` among them where it was cut (ADR-0054: «not
    longer than 200» — it was 200 and `…`, 201; the fourteenth review, minor 15: 199 and `…`)."""
    why = str(why)
    return why if len(why) <= MARK_ERROR else why[:MARK_ERROR - 1] + "…"


# WHAT A REQUEST IS, as its mark keeps it: the sha256 of the row's one text without the filer's own `filed` stamp — the
# very text `Worker._filed_already` compares two filings by — so that a filing under an id whose row is gone is told the
# same request (`again`) from a different one under a spent id (refused), from the mark alone. The product's
# `RequestDigest`, byte for byte.
def request_digest(row: dict) -> str:
    return hashlib.sha256(canonical_json({k: v for k, v in row.items() if k != "filed"}).encode()).hexdigest()


def mark_request(row: dict) -> dict:
    """The request's words every mark of it carries, whoever writes it: `digest`, and `valid_until` when the row's
    deadline is a finite time (a row without one, or with a word there, is refused, never performed: nothing to keep)."""
    out = {"digest": request_digest(row)}
    try:
        until = finite(row.get("valid_until") or 0)
    except (TypeError, ValueError):
        until = 0.0
    if until:
        out["valid_until"] = until
    return out


# HOW LONG A MARK OUTLIVES ITS ROW («Архитектор», 2026-10-06, after the review's fourteenth pass, major 2): the row is
# cleared seconds after the answer, and an evaluator that moved files the same id again — its cursor and `fired` stayed
# behind. "Not more than once" is the mark's to hold, so it stands at least until the request could no longer be
# performed: its deadline plus the reaper's margin — `REAP_AFTER`, or the family's `ttl` when that is longer (the holder
# judges the deadline by its own clock, and whoever sweeps by another).
#
# A MARK WITHOUT A DEADLINE STANDS TOO (the review's fifteenth pass, major 2; ADR-0054): a request of a family that ends
# its rows by `ttl` names none, and its mark went with its row — the same id filed again a minute later was a fresh
# filing, and the process that performs it did it twice. Its bound is the later of its moments (`ended_at`, `at`: when it was
# answered, when it was begun) plus the same margin — a row of that family could have stood no longer. None: a mark
# that does not parse, or says no moment at all — swept with its row, as before.
def mark_kept_until(raw, ttl=None) -> float | None:
    try:
        mark = json.loads(raw) if raw else None
        if not isinstance(mark, dict):
            return None
        until = finite(mark.get("valid_until") or 0)
        if not until:
            until = max(finite(mark.get("ended_at") or 0), finite(mark.get("at") or 0))
    except (*PARSE_ERRORS, TypeError, ValueError, AttributeError):
        return None
    try:
        margin = max(REAP_AFTER, finite(ttl or 0))
    except (TypeError, ValueError):
        margin = REAP_AFTER
    return until + margin if until else None


# THE RESOURCE'S ASK TO FREE BYTES, ONE FORM (ADR-0059: «the row's form is the platform's»): `<sub>/requests/free-<server>-
# <volume> {free, volume, server, at}`, written by the resource (`Resource._free_key`) and read by the worker of that
# subsystem on that server — no holder performs it, none marks it, and no answer of it goes into `fetched`: the row is
# the resource's to write and to take away (the fifteenth review, minor 5). The product's `FreeRequestPrefix`,
# `IsFreeRequest`.
FREE_PREFIX = "free-"


def free_request_key(sub, server: str, volume: str) -> str:
    """The resource's ask for `volume` of `server`, in subsystem `sub` (a `Subsystem`)."""
    return sub.request_key(f"{FREE_PREFIX}{server}-{volume}")


def is_free_request(rid: str, it) -> bool:
    """Whether a row is the resource's ask to free bytes: its id says so and it says how many."""
    return str(rid).startswith(FREE_PREFIX) and isinstance(it, dict) and "free" in it


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
    mark = {"unit": str(it.get("unit", "")), "outcome": outcome, "at": now, "ended_by": "reaper", "ended_at": now,
            **mark_request(it)}
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
def holder_still_there(ctl, said) -> bool:
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
    # whose holder `holder_still_there` takes for "still there", and the row stood for good (five hours on, a probe).
    # Past the deadline it ends NOT KNOWN like any begun request whose holder went: its mark completed `unknown` by the
    # index it read (a mark that does not parse is `instance: ?` to `complete_mark`), then the row deleted by CAS —
    # whoever asked reads an outcome; the beginner's answer, if one comes, still wins.
    nobodys = begun and not (isinstance(said, dict) and said.get("instance"))
    if begun and not nobodys and holder_still_there(ctl, said):
        return False
    # THE MARK FIRST, THEN THE ROW (the review's fourteenth pass, major 6): the row deleted and the mark not completed —
    # the store did not answer — left a request no turn would look at again, and its mark was swept with no outcome ever.
    # Completed first, a mark the store did not take leaves the row standing, and the next turn writes it again.
    wrote = False
    if begun:
        why = ("its mark does not read: whoever began it is not known, nor how it went" if nobodys
               else "its holder began it and is gone without saying how it went")
        try:
            wrote = complete_mark(ctl.objects, ctl.sub.command_key(rid), "unknown", why, now)   # by the index it reads
        except Exception as e:                              # noqa: BLE001 — not written: the row stands, the next turn
            log.warning("%s: request %s: its holder is gone, and its mark could not be completed (%s): left for the "
                        "next turn", ctl.spec.name, rid, e)
            return False
    try:
        ctl.vars.delete(key, cas=idx)                       # by CAS: a row filed again under the same id is a new one
    except Exception:                                       # noqa: BLE001 — changed meanwhile, or the store: the next pass
        return False                                        # (a mark completed above is an outcome the next turn reads)
    if isinstance(said, dict) and said.get("outcome"):
        log.info("%s: request %s was answered (%s) and its answer never reached a heartbeat: its row is cleared",
                 ctl.spec.name, rid, mark_text(said, "outcome"))
        return True
    if begun:
        if wrote:                                           # not written: answered meanwhile — its beginner's word stands
            unknown[ctl.spec.name] = unknown.get(ctl.spec.name, 0) + 1
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


# THE FAMILY'S RULES, ONE FOR EVERY FILER THAT IS NOT A WORKER (the review's fifteenth pass, major 4; ГРАНИЦА §3 row 3,
# ADR-0013, ADR-0012). They were the console's `_file_request`, and a subsystem's housekeeping process filed past them
# with a raw `vars.put`: a row the family's schema refuses (a key it does not take), stamps of its own (`[at, by]` where
# the spec says `[by, at, about]`), no line in the journal. Now, as the product has them (`requests.go`: `PrepareRequest`,
# `FileAs`, `sayFiled` — one name on both sides):
#
#   prepare_request   the request's row as the platform files it, from a body — whoever files it: the spec's `schema`;
#                     its `unit` `<sub>/<id>` of a unit that is; its id (the spec's `key` filled from the body, the
#                     body's `id`, or `idem`, by the one table of names `doors.rid_fault`); its values in their one text
#                     (`field_text`), `maxLength` over that text, NaN and the infinities refused; its deadline only with
#                     `valid_for` (the body's, or now + `valid_for`, at most `most_valid` away; a family without it ends
#                     its rows by `ttl` and takes none from anybody); the spec's `stamp`: `by`, `at`, `group`, the unit's
#                     `about`. A refusal is the door's reply, in its words
#   answered_by_mark  A SPENT ID IS ANSWERED BY ITS MARK (the fifteenth review, major 2; ADR-0054): a mark with an outcome
#                     under the id — the request was answered, its row cleared or about to be — is the answer, nothing
#                     written, no place counted: the same request (the same unit and action, or the same `digest`) 200
#                     `{answered}` with the mark's words; another under the spent id 409 `spent`. A mark not read raises
#   say_filed         the spec's `requests.journal`, one line per request filed, whoever filed it
#   file              the console's door (`POST /<sub>/requests`): the above, a place in the person's ledger
#                     (`per_person`, `<sub>/asked/…`, ADR 0060) by CAS, the row create-only; a taken id compared as every
#                     filer compares (`filed_already`) — the same request → its row, 202; another → 409 `exists`, the
#                     place given back. `(status, reply)`, as it is sent; `garbled(name, by, error)` says a ledger that does
#                     not read and answers for it (the console's: 429, `/metrics`, an alarm), `read(name)` one read again
#   file_as           a process's filing (`by`: what the process files as): the same rules, the row create-only, the
#                     journal line — WITHOUT a person's ledger: a process files what a worker's report told it to, not on
#                     a whim (the product's `FileAs`). `(rid, row, filed)`: `filed` False — the same request stands, or
#                     was answered under its id (its mark); a refusal raises `spec.Refused`, a different request under
#                     the id `Conflict`, a store that does not answer its own error


# A request row a person's ledger names, read to tell whether it still stands (`per_person`): one that does not parse
# stands — it keeps its place in that person's ledger until it is mended or `ttl` passes (the fourteenth review, minor
# 2: it was a 500 to every request that person filed; the product's `requests.go` keeps the entry too).
LEDGER_ROWS = Table("request_row", "it keeps its place in its person's ledger until it is mended or its ttl passes",
                    "request row a ledger names")


def _stands(ctl, key: str) -> bool:
    try:
        it = ctl.vars.get(key)[0]
    except PARSE_ERRORS as e:                               # `Garbled` too: held by the store, and not read
        LEDGER_ROWS.garbled(key, e)
        return True
    LEDGER_ROWS.parsed(key)
    return bool(it)


# The place a refused request took in its person's ledger, given back by CAS (the fourteenth review, major 1): the id
# under which another request stands would otherwise count against this person until `ttl` — that row stands.
def _ledger_release(ctl, ledger: str, rid: str, at: float) -> None:
    from .canonical import parse_json
    from .variables import Conflict
    for _ in range(50):
        try:
            it, idx = ctl.vars.get(ledger)
            held = [(str(r), finite(t)) for r, t in parse_json((it or {}).get("asks", "[]"))]
        except PARSE_ERRORS:
            return                                          # torn meanwhile: the next request says so
        kept = [(r, t) for r, t in held if not (r == rid and t == at)]
        if len(kept) == len(held):
            return
        try:
            ctl.vars.put(ledger, {**it, "asks": canonical_json(kept)}, cas=idx)
            return
        except Conflict:
            continue
    log.warning("%s: the place request %s took in %s would not be given back: it counts until the ledger's ttl",
                ctl.spec.name, rid, ledger)


def _garbled_ledger(name: str, by: str, e: Exception, sub: str) -> tuple:
    log.error("%s: the request ledger %s of %s does not read (%s): nothing is filed for it until an administrator "
              "deletes it (DELETE /%s/asked/%s)", sub, name, by, e, sub, name)
    return 429, {"detail": f"учёт не читается: the list of {by}'s open requests ({sub}/asked/{name}) does not read, "
                           f"and nothing is filed for {by} until an administrator deletes it", "error": "учёт не читается"}


# Whether a mark with an outcome stands under `rid` and says THIS request (`file`): `(None, "")` — no mark, or one with
# no outcome yet (begun: the row stands, and the filing goes on to meet it); `(mark, "same")`; `(mark, "other")`. A mark
# that does not parse names no request: another. Raises if the store does not answer.
def _spent(ctl, rid: str, out: dict) -> tuple[dict | None, str]:
    raw = ctl.objects.get(ctl.sub.command_key(rid))
    if raw is None:
        return None, ""
    try:
        mark = json.loads(raw)
    except PARSE_ERRORS:
        mark = None
    if not isinstance(mark, dict):
        return {"outcome": "?"}, "other"
    if not mark.get("outcome"):
        return None, ""
    bare = lambda u: str(u or "").split("/", 1)[1] if str(u or "").startswith(ctl.spec.name + "/") else str(u or "")  # noqa: E731
    if mark.get("digest") == request_digest(out):
        return mark, "same"
    same = bare(mark.get("unit")) == bare(out.get("unit")) and str(mark.get("action") or "") == str(out.get("action") or "")
    return mark, "same" if same else "other"


def prepare_request(ctl, body: dict, by: str, idem: str | None = None, now: float | None = None):
    """`(rid, row, ref, None)` — or `("", None, "", (status, reply))`, the door's refusal."""
    from .canonical import number_text
    from .doors import parse_ref, rid_fault
    spec, req = ctl.spec, ctl.spec.requests or {}
    now = ctl.wall() if now is None else now
    if not req:
        return "", None, "", (404, {"detail": f"{spec.name} takes no requests (its spec declares no `requests:`)", "error": "no requests"})
    if not isinstance(body, dict):
        return "", None, "", (400, {"detail": "a request is a JSON object", "error": "bad body"})
    if "schema" in req:
        from .schema import Invalid, check
        try:
            check(req["schema"], body, "the request")
        except Invalid as e:                                # past `maxLength`: the shared table's `too_long`
            return "", None, "", (400, {"detail": str(e), "error": "refused", **({"fault": "too_long"} if e.keyword == "maxLength" else {})})
        except RecursionError:
            return "", None, "", (400, {"detail": "the request is nested past what is read", "error": "refused"})
    ref = str(body.get("unit", ""))
    got = parse_ref(ref)
    if got is None or got[0] != spec.name:
        return "", None, "", (400, {"detail": f"a request names its unit as {spec.name}/<id>, not {ref[:80]!r}", "error": "bad unit"})
    try:
        row = ctl.unit(spec.parse_id(got[1]))
    except (ValueError, *PARSE_ERRORS):
        row = None
    if row is None:
        return "", None, "", (404, {"detail": f"no unit {ref}", "error": "no such unit"})
    uid = str(row["id"])
    if "key" in req:
        from .tables import KEY_TEMPLATE

        def filled(m) -> str:                              # a field's text in the name is its text in the row
            v = {**body, "unit": uid}[m.group(1)]
            if v is None:
                raise KeyError(m.group(1))                 # `null` is no value: the name is not filled in
            if not m.group(2):
                return field_text(v)
            # `:int` — an integer in exactly its digits (through a float, 12345678901234567890 was …7168)
            return str(v) if isinstance(v, int) and not isinstance(v, bool) else str(int(float(v)))
        try:
            rid = KEY_TEMPLATE.sub(filled, req["key"])
        except (KeyError, *PARSE_ERRORS, OverflowError):
            return "", None, "", (400, {"detail": f"a request is named {req['key']}, and the body does not fill it in", "error": "bad id"})
    else:
        rid = str(body.get("id") or idem or "")
    why = rid_fault(rid)                                    # ONE TABLE OF NAMES, the worker's too (ADR 0060; `rid.tsv`)
    if why:
        return "", None, "", (400, {"detail": why, "error": "bad id"})
    # A ROW'S VALUE IS ITS JSON TEXT, ONE FORM FOR THE COURSE AND THE PRODUCT (the architect, 2026-10-05, ADR 0012;
    # «Паритет»'s `testdata/requests_body.tsv`): a string as it is, `true`/`false`, a whole number as its digits, any
    # other the shortest decimal. `null` is no value: the field is absent. The text is what the schema's `maxLength`
    # bounds — a number's too, as the holder reads it (`port: 1e40` is 41 characters).
    try:
        out = {k: t for k, v in body.items() if k not in ("unit", "id", "valid_until")
               and (t := field_text(v)) is not None}
    except PARSE_ERRORS:                                    # `NaN`, `Infinity`: Python reads them, JSON has none
        return "", None, "", (400, {"detail": "a request's values are JSON, and NaN and the infinities are not", "error": "bad body",
                     "fault": "not_json"})
    props = (req["schema"].get("properties") or {}) if isinstance(req.get("schema"), dict) else {}
    for k, t in out.items():
        most = props[k].get("maxLength") if isinstance(props.get(k), dict) else None
        if isinstance(most, int) and len(t) > most:
            return "", None, "", (400, {"detail": f"the request's {k} is at most {most} characters as written, not {len(t)}",
                         "error": "refused", "fault": "too_long"})
    out.update(unit=uid)
    if "valid_for" in req:
        # A deadline is a finite number of seconds (the review's seventh pass, M3); how far one may be is declared
        # (`most_valid`, required with `valid_for`): no bound is assumed (ADR 0012).
        try:
            until = finite(body.get("valid_until") or now + req["valid_for"])
        except (TypeError, ValueError):
            return "", None, "", (400, {"detail": f"`valid_until` is a time in seconds, not {body.get('valid_until')!r}", "error": "bad deadline"})
        if until - now > req["most_valid"]:
            return "", None, "", (400, {"detail": f"a request's `valid_until` is at most {req['most_valid']:.0f} s away", "error": "too far"})
        out["valid_until"] = number_text(until)
    stamp = set(req.get("stamp") or ())
    if "by" in stamp:
        out["by"] = str(by)
    if "at" in stamp:
        out["at"] = number_text(now)
    if "group" in stamp and spec.group_by:                  # what the rights were asked on: the holder performs it there only
        out["group"] = ctl.group_value(row)
    if "about" in stamp and spec.about_field and row.get(spec.about_field) not in (None, ""):
        out[spec.about_field] = str(row[spec.about_field])
    return rid, out, ref, None


def answered_by_mark(ctl, rid: str, out: dict) -> tuple | None:
    """The reply a spent id gets from its mark — 200 `answered`, or 409 `spent` — or None: no mark with an outcome."""
    mark, kind = _spent(ctl, rid, out)
    if kind == "same":
        return 200, {"answered": {"id": rid, "outcome": mark_text(mark, "outcome"),
                                  **{k: mark_text(mark, k) for k in ("error", "ended_at", "late") if mark.get(k) not in (None, "")}},
                     "detail": f"request {rid} was answered ({mark_text(mark, 'outcome')}): the same request is not "
                               f"performed again — its answer is in its mark"}
    if kind == "other":
        return 409, {"detail": f"request {rid}: this id is spent — a request answered under it "
                               f"({mark_text(mark, 'outcome')}) is not this one; name yours otherwise", "error": "spent"}
    return None


def say_filed(journal, spec, by: str, ref: str, rid: str, out: dict) -> None:
    """The family's journal line of a request filed (`requests.journal`): who, of which unit, which request, its range
    or action — one line for a person's at the door and a process's (`file_as`). No journal, or none declared: none."""
    req = spec.requests or {}
    if not req.get("journal") or journal is None:
        return
    journal.say(str(req["journal"]), user=str(by), target=ref, request=rid, sub=spec.name,
                **{k: v for k, v in out.items() if k in ("from", "to", "action")})


def file(ctl, body: dict, by: str, *, idem: str | None = None, journal=None, now: float | None = None,
         garbled=None, read=None) -> tuple[int, dict]:
    from .canonical import number_text, parse_json
    from .variables import Conflict
    spec, req = ctl.spec, ctl.spec.requests or {}
    now = ctl.wall() if now is None else now
    rid, out, ref, refused = prepare_request(ctl, body, by, idem, now)
    if refused is not None:
        return refused
    stamp = set(req.get("stamp") or ())
    # A SPENT ID: its mark answers (the fifteenth review, major 2). Read before any place is counted or row written.
    spent = answered_by_mark(ctl, rid, out)
    if spent is not None:
        return spent
    added, ledger = False, ""
    if "per_person" in req:
        # ONE PERSON'S OPEN REQUESTS, COUNTED BY CAS, NOT BY LOOKING (the review's sixth pass, minor): `<sub>/asked/<sha256
        # of the asker, 16 hex>` (ADR 0060), the list of their ids, changed by CAS; an id stays in it while its row stands,
        # and for `settle` seconds after it was added, row or no row, and never past the spec's `ttl` (`0`: no limit).
        # A LEDGER THAT DOES NOT READ STOPS THAT ASKER, AND SAYS SO (`garbled`); a request row it names that does not read
        # stands (`LEDGER_ROWS`).
        ledger = spec.sub.asked_key(by)
        name = ledger.rsplit("/", 1)[1]
        settle, ttl = req.get("settle", 60.0), req["ttl"]   # the loader requires it with `per_person`; 0: no limit
        for _ in range(50):
            try:
                it, idx = ctl.vars.get(ledger)
                held = [(str(r), finite(at)) for r, at in parse_json((it or {}).get("asks", "[]"))]
            except PARSE_ERRORS as e:                       # `Garbled` too: a row the store holds and cannot read
                return garbled(name, by, e) if garbled else _garbled_ledger(name, by, e, spec.name)
            if read:
                read(name)
            held = [(r, at) for r, at in held if (not ttl or now - at <= ttl)
                    and (now - at < settle or _stands(ctl, spec.sub.request_key(r)))]
            added = rid not in [r for r, _ in held]
            if added:
                if len(held) >= req["per_person"]:
                    return 429, {"detail": f"{by} has {len(held)} requests nobody has answered yet, as many as one "
                                           f"person files at once — wait for some to be answered", "error": "too many"}
                held.append((rid, now))
            try:
                ctl.vars.put(ledger, {"asks": canonical_json(held), "by": str(by), "at": number_text(now)}, cas=idx)
                break
            except Conflict:
                continue                                    # another request of this asker's got there first
        else:
            return 503, {"detail": "this person's list of requests would not settle — retry", "error": "busy"}
    try:
        ctl.vars.put(spec.sub.request_key(rid), out, cas=0)
    except Conflict:
        # THE ID IS TAKEN: THE SAME REQUEST, OR ANOTHER (the fourteenth review, major 1; ADR 0013, 0031), compared as a
        # worker's filing compares it (`filed_already`) without the door's own stamps — `by` and `at` when it stamps them,
        # a deadline it gave itself: WHAT is asked decides. The same → its row, 202; another or one that does not parse →
        # 409 `exists`, the place given back; not read → 503.
        moment = ("filed", *(k for k in ("by", "at") if k in stamp),
                  *(("valid_until",) if "valid_for" in req and body.get("valid_until") in (None, "", 0) else ()))
        kind, why = filed_already(ctl.vars, spec.sub.request_key(rid), out, moment)
        if kind in ("other", "garbled", "store"):
            if added:
                _ledger_release(ctl, ledger, rid, now)
            if kind == "store":
                return 503, {"detail": f"request {rid}: {why}", "error": "store unavailable"}
            return 409, {"detail": f"request {rid}: {why} — name yours otherwise", "error": "exists"}
        if kind == "same":
            out = ctl.vars.get(spec.sub.request_key(rid))[0] or out   # the same request, filed already: its row is the answer
    say_filed(journal, spec, by, ref, rid, out)
    return 202, {"queued": {"id": rid, **out},
                 "detail": "whoever holds the unit answers it on its next look at the requests, in its heartbeat"
                           + ("; after valid_until it expires unperformed" if "valid_for" in req else "")}




def file_as(ctl, body: dict, by: str, *, journal=None, now: float | None = None) -> tuple[str, dict | None, bool]:
    from .spec import Refused
    from .variables import Conflict
    spec = ctl.spec
    now = ctl.wall() if now is None else now
    rid, out, ref, refused = prepare_request(ctl, body, by, None, now)
    if refused is not None:
        raise Refused(str(refused[1].get("detail") or refused[1].get("error")))
    spent = answered_by_mark(ctl, rid, out)              # raises if the store does not answer
    if spent is not None:
        if spent[0] == 200:
            return rid, None, False                      # answered under its id: the mark says how
        raise Conflict(f"request {rid}: {spent[1]['detail']}")
    key = spec.sub.request_key(rid)
    try:
        ctl.vars.put(key, out, cas=0)
    except Conflict:
        stamp = set((spec.requests or {}).get("stamp") or ())
        kind, why = filed_already(ctl.vars, key, out, ("filed", *(k for k in ("by", "at") if k in stamp)))
        if kind == "same":
            return rid, None, False                      # the same request stands
        if kind == "store":
            raise OSError(f"request {rid}: {why}") from None
        raise Conflict(f"request {rid}: {why}") from None
    say_filed(journal, spec, by, ref, rid, out)
    return rid, out, True


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
