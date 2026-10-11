"""The fencing token and the lease — generic to any writer that can have
two instances. The subsystem decides what key the epoch goes in; the
platform only promises that it comes from one issuer and increases.

    next_epoch(vars, key)   issue the next epoch for `key` by check-and-set: two callers
                            racing get two different numbers, in order — above the group's
                            floor (`platform/epoch_floor`, raised by `configstore recover`)
    Lease                   may_act while now − last_renewal < TTL − margin, on a
                            monotonic clock (may_write: also through a silent store, up to
                            its ceiling); renew = read the key and find it still mine
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # epoch.py — the fencing-token issuer and the lease, generic to any writer that can have two instances
#
# **Role in the module.** Lesson 1. A unit (a stream, a fan-out, a model) may at any moment have two processes
# believing they run it — a zombie after a reschedule, or a reassignment window. The platform's answer is a
# fencing token, the *epoch*: a per-unit integer that comes from one issuer (the CAS on a Variables key) and
# only increases. Whoever holds the newest epoch is the writer; an older holder discovers it on its next
# renewal and stops. This file has the issuer (`next_epoch`), the reader (`current_epoch`) and the lease
# that a holder keeps on its epoch (`Lease`). The subsystem decides the key (`Subsystem.epoch_key(unit)`
# gives `<name>/epoch/<unit>`); the platform promises only that numbers come from one issuer, in order.
# `worker.Worker.take_epoch` and `renew_leases` are the callers; a subsystem's bulk writer puts the epoch in every
# segment and bucket path so a stale writer's output is identifiable afterwards.
#
# ## Module-level names
# - `EPOCH_FLOOR_KEY = "platform/epoch_floor"`, `EPOCH_FLOOR_FIELD = "floor"` — the floor under every epoch of the group
#   (ADR-0070, the blocker of step 1's drill), `EPOCH_FLOOR_AT = "generation_at"` — the hour its generation was set; and
#   `next_epoch_floor(floor, hours)` — the next generation, `max((floor >> 32) + 1, hours) << 32`, `hours` the clock's
#   (`generation_hours`: whole hours of UTC since 2026-01-01; ADR-0070's addition of 2026-10-11).
#
# ## The floor (ADR-0070)
# A group given back to a member that was BEHIND (`configstore recover`, the majority gone for good) has lost the epochs the
# others issued since — and nobody left knows how many. A count cannot mend that; a floor can. `recover` writes
# `platform/epoch_floor` into the state it gives the member, before its daemon starts (so nothing is issued between the
# start and the floor): the generation `max(by the content + 1, the clock)` in the upper 32 bits — the content the highest
# of the old floor and every epoch the member holds, the clock below. `restore` and `import` raise it by the same rule.
# `next_epoch` issues `max(current, floor) + 1` for ANY unit — one never seen too — so every epoch issued after a recover is
# above every one issued before it, of any unit. The price is names like `e4294967297` after a recover; Python's `int` reads
# them as it reads `e7`, and they stay below 2^53, what JSON carries exactly. The floor is written by `recover` alone: no door
# writes or deletes it (`storemachine.Rights.allows`; `restore` and `import` raise it with the machine's `floor` command,
# the operator's alone), and a worker's role reads it (`cluster/rights.py`).
#
# ## Notes
# - `test_lease_on_a_monotonic_clock`: at 24.9 s the lease may write; at 25.1 s it may not and
#   `seconds_left() == 0`; a successful `renew()` restores it; after someone else calls `next_epoch` on the
#   same key, `renew()` returns False, `fenced` is set and `conflicts == 1`.
# - The fence is discovered at renewal, never pushed: a zombie keeps writing for at most `ttl − margin`
#   after the new holder took the epoch. That bounded window is the RPO a subsystem's storage lesson accepts, and the
#   epoch in the name — of a bucket, of a stream in a volume — is what lets a reader mark that window as
#   fenced afterwards.
# - Two threads renew a lease (feedback DD): the loop, and `Worker`'s stand-in while a step of the loop hangs.
#   The fields are under `_lock`, the store is asked outside it; a stamp never moves backwards, and a lease
#   fenced or released (`release`) while a renewal was in flight stays so (`tests/test_stand_in.py`).
# ================================================================================================
from __future__ import annotations

import threading
import time

from .variables import Conflict, Variables, cas_pause
from .rows import PARSE_ERRORS

# The floor under every epoch of the group — raised by a state put in (`configstore recover`, `restore`, `import`) alone
# (the notes above; ADR-0070); `generation_at`, the hour its generation was set, for diagnosis and the clock's check.
EPOCH_FLOOR_KEY = "platform/epoch_floor"
EPOCH_FLOOR_FIELD = "floor"
EPOCH_FLOOR_AT = "generation_at"

# THE GENERATION FROM THE CLOCK, NOT ONLY FROM THE CONTENT (ADR-0070's addition of 2026-10-11, the model's blocker): a
# state put in knows only the generations it holds — a backup restored after the group it was taken of went through a
# recover or a restore of its own repeated a generation (backup → recover 2^32 → epoch 2^32+1 → restore of that backup →
# floor 2^32 → 2^32+1 again). So the generation of any input is `max(by the content + 1, the clock)`, the clock being
# whole HOURS of UTC since 2026-01-01: 2^21 hours are 239 years, and an epoch stays below 2^53 — it travels in JSON as a
# number (seconds, proposed first, would have passed that in three weeks). A repeat stays possible only for an older copy
# put in within the same hour as another input — the operator's condition (lesson 2 of М11). An input whose machine's
# clock is before the hour of the generation in the state put in (the clock went back) is refused without `-force`.
GENERATION_FROM = 1767225600                      # 2026-01-01T00:00:00Z, unix seconds
GENERATION_LIMIT = 1 << 21                        # hours: a generation above it would carry an epoch past 2^53


def generation_hours(now: float | None = None) -> int:
    """The clock's generation: whole hours of UTC since 2026-01-01 (`now`: unix seconds; None — this machine's)."""
    return max(0, int(((time.time() if now is None else now) - GENERATION_FROM) // 3600))


def hour_stamp(hours: int) -> str:
    """`hours` since 2026-01-01 as the hour it is, `2026-10-11T15:00:00Z` — what `generation_at` says."""
    return time.strftime("%Y-%m-%dT%H:00:00Z", time.gmtime(GENERATION_FROM + int(hours) * 3600))


def hours_of(stamp) -> int | None:
    """The hours since 2026-01-01 a `generation_at` says, or None when it says none that reads."""
    import calendar
    try:
        return (calendar.timegm(time.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ")) - GENERATION_FROM) // 3600
    except (ValueError, OverflowError):
        return None


class EpochUnreadable(ValueError):
    """An epoch's row that is no epoch — a word, nothing, a sign: an error, never 0 (the product's `ErrEpochUnreadable`)."""


# The epoch an epoch's row says, or `EpochUnreadable` (the external review of 2026-10-11, its finding 3; ADR-0070): read as
# 0, a garbled row handed out epochs already issued; read as silence, a lease under it wrote on for as long as its spec
# allows. ASCII digits only — `-5` and `٣` are no epoch either.
def _epoch_of(items: dict, key: str) -> int:
    raw = items.get("epoch") if isinstance(items, dict) else None
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
        return raw                                   # a store that keeps what it was given (`memory://`)
    if not (isinstance(raw, str) and raw.isascii() and raw.isdigit()):
        raise EpochUnreadable(f"{key} says {raw!r}: an epoch is a whole number")
    return int(raw)


# The floor a state put in raises `floor` to (the generation in the upper 32 bits): `max(by the content + 1, the clock's
# hours)` — the addition above. Past `GENERATION_LIMIT` it refuses: the epoch would no longer be a JSON number exactly.
def next_epoch_floor(floor: int, hours: int) -> int:
    generation = max((int(floor) >> 32) + 1, int(hours))
    if generation >= GENERATION_LIMIT:
        raise ValueError(f"the generation {generation} is past {GENERATION_LIMIT}: an epoch above it is past 2^53 (ADR-0070)")
    return generation << 32


# The group's floor under every epoch: 0 where no recover ever raised one. A floor row that does not read is said, not
# counted as 0 — under it, epochs already issued would be issued again.
def epoch_floor(vars_: Variables) -> int:
    items, _ = vars_.get(EPOCH_FLOOR_KEY)
    if not items:
        return 0
    raw = str(items.get(EPOCH_FLOOR_FIELD, ""))
    if not (raw.isascii() and raw.isdigit()):
        raise ValueError(f"{EPOCH_FLOOR_KEY} says {raw!r}: the floor under every epoch is a whole number (ADR-0070)")
    return int(raw)


# Issues the next epoch for `key` by check-and-set: read `{epoch}` and its ModifyIndex (missing key means
# epoch 0), try to `put` `epoch + 1` with `cas=idx`; on `Conflict` re-read and try again, up to `retries`
# times, then raise `RuntimeError`. Because the CAS is on the row's index, two callers racing get two
# different numbers in order and no number is ever reused — `test_epoch_issuer_never_reuses_a_number` runs
# four threads issuing 25 each and asserts the set is exactly 1..100. The returned index is the row's
# ModifyIndex after the write (unused by `Worker.take_epoch`, which keeps only the epoch).
# ABOVE THE GROUP'S FLOOR (ADR-0070): `max(current, floor) + 1`, for a unit never seen as well — a group recovered from
# a member that was behind issues no epoch it issued before (the notes: The floor). The floor is read once a call: it
# moves only with a recover, and a recover starts its daemon with it already there.
def next_epoch(vars_: Variables, key: str, retries: int = 200) -> tuple[int, int]:
    floor = epoch_floor(vars_)
    for attempt in range(retries):
        items, idx = vars_.get(key)
        current = max(_epoch_of(items, key) if items else 0, floor)
        try:
            new_idx = vars_.put(key, {"epoch": current + 1}, cas=idx)
            return current + 1, new_idx
        except Conflict:
            cas_pause(attempt)                       # not at once: whoever won is one of several still trying
            continue
    raise RuntimeError(f"could not issue an epoch for {key} after {retries} conflicts")


# Reads the epoch stored under `key`, 0 if the key does not exist. Used by `Lease.renew` and by the
# console's `/events` route to compute the current epoch per unit for fencing in the index's reply.
def current_epoch(vars_: Variables, key: str) -> int:
    items, _ = vars_.get(key)
    return _epoch_of(items, key) if items else 0


# What a worker holds per unit once it has taken the epoch. It answers two questions from a monotonic clock, not
# from the store — `may_act()`, what an action asks: the store confirmed this epoch less than `ttl − margin` ago and
# the lease has not been fenced; and `may_write()`, what data asks: also for `unconfirmed_max` past that while the
# store is silent (below). Renewal is "read the key and find it still mine". The store being unreachable
# does not by itself stop writing; the TTL does. Created by `Worker.take_epoch`; `Worker.renew_leases`
# renews all of them and reports the ones lost.
class Lease:
    # `key` is the epoch row, `epoch` the number this holder took, `ttl` and `margin` the window (writes
    # stop `margin` seconds before the TTL to leave room for the fence to propagate), `clock` a monotonic
    # clock (tests inject a fake). Sets `last_renewal = clock()` now, `fenced = False`, `conflicts = 0`.
    def __init__(self, vars_: Variables, key: str, epoch: int, ttl: float = 30.0, margin: float = 5.0,
                 clock=time.monotonic, unconfirmed_max: float | None = 0.0):
        self.vars, self.key, self.epoch = vars_, key, epoch
        self.ttl, self.margin, self.clock = ttl, margin, clock
        self.last_renewal = clock()
        self.fenced = False
        self.conflicts = 0
        self.store_errors = 0                  # renewals the store did not answer: not a loss, and not nothing
        # TWO QUESTIONS, NOT ONE (feedback BK). `may_act` is the strict one and it has not changed: the store
        # confirmed this epoch less than `ttl − margin` ago. It is what an ACTION asks — a relay, a scenario's
        # firing — because an action done twice is done twice.
        #
        # `may_write` is what DATA asks, and it is wider by exactly one case: a lease that ran out while the
        # store was SILENT is not a lease somebody took. Nobody said this epoch is over; nobody could have. A
        # frame written under it harms nothing — the epoch is in the path, a reader marks what an old epoch
        # wrote, and if there really was a second writer the cost is a duplicate. Stopping costs a hole.
        #
        #   silent_since       when the store first failed to answer a renewal WHILE THE LEASE WAS STILL GOOD.
        #                      A holder that slept past its lease and then found the store away has not
        #                      established silence: its lease ran out while nobody was asking, and it is lost
        #   unconfirmed_max    how long past the lease's end the writing may go on unconfirmed. `None`: no
        #                      ceiling. `0`: none at all — the strict behaviour, which is this class's default;
        #                      a subsystem that writes data says otherwise
        self.silent_since: float | None = None
        self.unconfirmed_max = unconfirmed_max
        # TWO THREADS RENEW IT (feedback DD): the worker's loop, and its stand-in while a step of that loop hangs
        # (`Worker.stand_in_once`). The fields are read and written under this lock; the store is asked outside it,
        # so a renewal hung on the store does not hang the other one too.
        self._lock = threading.RLock()
        self.released = False                  # the worker let go of the unit (`Worker.release`): renewed by nobody

    # Once fenced, always `False`. Otherwise read `current_epoch(key)`: if the store raises (unreachable),
    # do not fence — return `may_act()` and keep going until `ttl − margin` runs out; if the live epoch
    # differs from mine, set `fenced = True`, count a conflict and return `False`; else stamp `last_renewal`
    # and return `True`. `conflicts` is what the worker sums into its heartbeat (`conflicts=`) and the
    # console exports as `<sub>_epoch_conflicts`.
    #
    # The lease runs from BEFORE the read, not from after it (the platform review): a holder paused for a minute
    # between reading the row and stamping the renewal — a GC, a stalled disk — woke up with twenty-five more
    # seconds of a lease it had in fact lost while it slept. And a renewal the store did not answer is counted
    # (`store_errors`): "the store is away" and "the row is garbled" used to look alike and be seen by nobody
    # until the leases ran out.
    def renew(self) -> bool:
        with self._lock:
            if self.fenced or self.released:
                return False
        t0 = self.clock()
        try:
            live = current_epoch(self.vars, self.key)
        except OSError:                        # the store is unreachable: not a loss, and not a confirmation
            with self._lock:
                self.store_errors += 1
                if self.silent_since is None and self.may_act():
                    self.silent_since = t0     # silence, established while the lease was still good
                return self.may_write()
        except PARSE_ERRORS:                   # `epoch: Infinity` too — it raised out of `renew_leases`, every lease (the tenth round)
            # The store ANSWERED, with a row that is not an epoch. That is not silence to record through
            # (the review's second pass): somebody wrote over the counter, and whoever did may have given the
            # unit away too. Fenced, as a counter that moved; the instance takes a fresh slot and starts again.
            with self._lock:
                self.fenced, self.conflicts = True, self.conflicts + 1
            return False
        with self._lock:
            if self.fenced or self.released:
                return False                   # fenced or let go while we asked: an answer does not undo either
            self.silent_since = None           # it answered: whatever it says now is an answer
            if live != self.epoch:
                self.fenced, self.conflicts = True, self.conflicts + 1
                return False
            # Never backwards: of two renewals in flight, the one that asked earlier may answer later, and its
            # stamp is the older one (the loop and the stand-in, feedback DD).
            self.last_renewal = max(self.last_renewal, t0)
            return True

    # The worker stopped the unit. A renewal already in flight — the stand-in's — finds it let go and stamps nothing.
    def release(self) -> None:
        with self._lock:
            self.released = True

    # Data may go on: the strict answer, or a lease that ran out in silence and is under its ceiling.
    def may_write(self) -> bool:
        with self._lock:
            if self.fenced:
                return False
            if self.may_act():
                return True
            if self.silent_since is None:
                return False                   # it ran out and nobody was silent about it: lost
            return self.unconfirmed_max is None or self.unconfirmed() < self.unconfirmed_max

    # Seconds this lease has been past its end with the store silent; 0 while it is confirmed.
    def unconfirmed(self) -> float:
        with self._lock:
            if self.silent_since is None:
                return 0.0
            return max(0.0, (self.clock() - self.last_renewal) - (self.ttl - self.margin))

    # `not fenced and (clock() − last_renewal) < ttl − margin`. What an ACTION asks before it is done — a request's
    # call into its target; data asks `may_write`.
    def may_act(self) -> bool:
        with self._lock:
            return not self.fenced and (self.clock() - self.last_renewal) < (self.ttl - self.margin)

    # Time until `may_act` would become false, floored at 0.
    def seconds_left(self) -> float:
        with self._lock:
            return max(0.0, (self.ttl - self.margin) - (self.clock() - self.last_renewal))
