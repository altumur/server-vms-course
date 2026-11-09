// -*- mode: Bluespec; -*-
// P/08 model unit: the member mutex, the freeze read-write lock with writer priority, the restore section (C3, part of C4).
// Anchors: common/contracts/accept.md:289 (mutex, no term), 08.8:299-308 (common handover deadline 90 s; the waiting for
// the exclusive side goes into it; writer priority), 08.8:385 (restore section: not released while old I/O can write),
// production-obligations.md:9,11 (prod: finite lock budgets; declaration, not a number). Modelled in discrete seconds with
// jumps; events fire as soon as enabled (the tick is enabled only when nothing else is), so waits are exact. The hang of a
// dependency is a parameter: HANG_END (time the store answers). NOT modelled: the content of the writes, the handover steps
// after the freeze, read-only doors, retries. Bound: 1 mutex waiter, 1 shared holder + 1 shared waiter behind a freeze waiter.
module p08_locks {
  const F_DEADLINE: int     // 90 s, 08.8:299-301
  const HANG_END: int       // time the hung dependency answers; beyond the horizon = "does not answer in the run"
  const WAIT_BUDGET: int    // 0 = none (P/08 text: no term named for the mutex wait); >0 = a declared budget (prod:9)
  const HOLD_BUDGET: int    // 0 = none; >0: a holder stalled by a dependency gives up at this age
  const CALLOFF: bool       // N: the freeze wait expires inside the common deadline. mutant false
  const WRITER_PRIORITY: bool // N true; mutant false (the shared waiter overtakes)
  const RESTORE_RESTART: bool // true: a process restart (bounded by a stop budget) frees the section
  const RELEASE_ON_CALLOFF: bool // mutant true: the section is released at the source's call-off while I/O can still write

  var t: int
  // mutex: R1 holds, R2 waits
  var r1: str                 // holding | done
  var r2: str                 // none | waiting | granted | refused
  var r2Since: int
  // RW lock: E1 shared holder, E2 shared waiter behind the waiting freeze F
  var e1: str                 // holding | done
  var e2: str                 // none | waiting | granted | refused
  var e2Since: int
  var f: str                  // none | waiting | frozen | calledoff
  var fSince: int
  var e2Wait: int             // measured wait at the moment of the grant/refusal (0 = not yet)
  var r2Wait: int
  // restore section
  var secHeld: bool           // section occupied, a hung old handler
  var secAge: int
  var secIoAlive: bool
  var staleAfterRelease: bool // an old handler's write after the release
  var seq: int
  var tFStart: int
  var tE2Arrive: int
  var tCalledOff: int
  var tE2Granted: int
  var tFrozenSet: int
  var tE2Refused: int

  action init = all {
    t' = 0, r1' = "holding", r2' = "none", r2Since' = 0,
    e1' = "holding", e2' = "none", e2Since' = 0, f' = "none", fSince' = 0, e2Wait' = 0, r2Wait' = 0,
    secHeld' = true, secAge' = 0, secIoAlive' = true, staleAfterRelease' = false,
    seq' = 1, tFStart' = 0, tE2Arrive' = 0, tCalledOff' = 0, tE2Granted' = 0, tFrozenSet' = 0, tE2Refused' = 0,
  }

  // helper unchanged groups
  action keep_r = all { r1' = r1, r2' = r2, r2Since' = r2Since, r2Wait' = r2Wait }
  action keep_e = all { e1' = e1, e2' = e2, e2Since' = e2Since, e2Wait' = e2Wait, f' = f, fSince' = fSince }
  action keep_sec = all { secHeld' = secHeld, secAge' = secAge, secIoAlive' = secIoAlive, staleAfterRelease' = staleAfterRelease }
  action keep_stamps = all { tFStart' = tFStart, tE2Arrive' = tE2Arrive, tCalledOff' = tCalledOff, tE2Granted' = tE2Granted, tFrozenSet' = tFrozenSet, tE2Refused' = tE2Refused }

  // what is immediately enabled (the tick waits for these): deadlines and grants
  def e1StallExpired = HOLD_BUDGET > 0 and t >= HOLD_BUDGET
  def depResponds = t >= HANG_END
  val e1CanFinish = depResponds or e1StallExpired
  val r1CanFinish = depResponds or e1StallExpired
  val fDeadlineHit = f == "waiting" and t - fSince >= F_DEADLINE
  val canFreeze = f == "waiting" and e1 == "done"
  val canGrantE2 = e2 == "waiting" and (f != "waiting") and not(f == "frozen")
  val canR2 = r2 == "waiting" and r1 == "done"
  val r2Expired = WAIT_BUDGET > 0 and r2 == "waiting" and t - r2Since >= WAIT_BUDGET
  val ready = or {
    r1 == "holding" and r1CanFinish, e1 == "holding" and e1CanFinish, CALLOFF and fDeadlineHit, canFreeze, canGrantE2, canR2,
    e2 == "waiting" and f == "frozen", r2Expired,
  }

  // time jump, not beyond the next deadline so that ages at deadline moments are exact
  action tick(d: int): bool = all {
    not(ready), d > 0,
    val limits = Set(
      if (f == "waiting" and CALLOFF) fSince + F_DEADLINE else 1000000,
      if (t < HANG_END) HANG_END else 1000000,
      if (HOLD_BUDGET > 0 and t < HOLD_BUDGET) HOLD_BUDGET else 1000000,
      if (WAIT_BUDGET > 0 and r2 == "waiting") r2Since + WAIT_BUDGET else 1000000,
    )
    t + d <= limits.fold(1000000, (a, b) => if (a < b) a else b),
    t' = t + d,
    keep_r, keep_e, keep_sec, seq' = seq + 1, keep_stamps,
  }

  action r2Arrive = all { r2 == "none", r2' = "waiting", r2Since' = t, r1' = r1, r2Wait' = r2Wait, t' = t, keep_e, keep_sec, seq' = seq + 1, keep_stamps }
  action r1Finish = all { r1 == "holding", r1CanFinish, r1' = "done", r2' = r2, r2Since' = r2Since, r2Wait' = r2Wait, t' = t, keep_e, keep_sec, seq' = seq + 1, keep_stamps }
  action r2Grant = all { canR2, r2' = "granted", r2Wait' = t - r2Since + 1, r1' = r1, r2Since' = r2Since, t' = t, keep_e, keep_sec, seq' = seq + 1, keep_stamps }
  action r2Refuse = all { r2Expired, r2' = "refused", r2Wait' = t - r2Since + 1, r1' = r1, r2Since' = r2Since, t' = t, keep_e, keep_sec, seq' = seq + 1, keep_stamps }

  action e1Finish = all { e1 == "holding", e1CanFinish, e1' = "done", e2' = e2, e2Since' = e2Since, e2Wait' = e2Wait, f' = f, fSince' = fSince, t' = t, keep_r, keep_sec, seq' = seq + 1, keep_stamps }

  // the handover starts waiting for the exclusive side
  action fStart = all { f == "none", f' = "waiting", fSince' = t, e1' = e1, e2' = e2, e2Since' = e2Since, e2Wait' = e2Wait, t' = t, keep_r, keep_sec, seq' = seq + 1,
    tFStart' = seq, tE2Arrive' = tE2Arrive, tCalledOff' = tCalledOff, tE2Granted' = tE2Granted, tFrozenSet' = tFrozenSet, tE2Refused' = tE2Refused }

  // E2 arrives after F began waiting: with writer priority it queues behind F
  action e2Arrive = all { e2 == "none", f == "waiting", e2' = "waiting", e2Since' = t, e1' = e1, e2Wait' = e2Wait, f' = f, fSince' = fSince, t' = t, keep_r, keep_sec, seq' = seq + 1,
    tFStart' = tFStart, tE2Arrive' = seq, tCalledOff' = tCalledOff, tE2Granted' = tE2Granted, tFrozenSet' = tFrozenSet, tE2Refused' = tE2Refused }

  action fCalloff = all { CALLOFF, fDeadlineHit, f' = "calledoff", fSince' = fSince, e1' = e1, e2' = e2, e2Since' = e2Since, e2Wait' = e2Wait, t' = t, keep_r, keep_sec, seq' = seq + 1,
    tFStart' = tFStart, tE2Arrive' = tE2Arrive, tCalledOff' = seq, tE2Granted' = tE2Granted, tFrozenSet' = tFrozenSet, tE2Refused' = tE2Refused }

  // the exclusive side is free: frozen is set, the exclusive side is released at once (08.8:308)
  action fFreeze = all { canFreeze, f' = "frozen", fSince' = fSince, e1' = e1, e2' = e2, e2Since' = e2Since, e2Wait' = e2Wait, t' = t, keep_r, keep_sec, seq' = seq + 1,
    tFStart' = tFStart, tE2Arrive' = tE2Arrive, tCalledOff' = tCalledOff, tE2Granted' = tE2Granted, tFrozenSet' = seq, tE2Refused' = tE2Refused }

  // E2 gets the shared side when no freeze is pending or (without writer priority) at once
  action e2Grant = all {
    e2 == "waiting", or { canGrantE2, not(WRITER_PRIORITY) },
    e2' = "granted", e2Wait' = t - e2Since + 1, e2Since' = e2Since, e1' = e1, f' = f, fSince' = fSince, t' = t, keep_r, keep_sec, seq' = seq + 1,
    tFStart' = tFStart, tE2Arrive' = tE2Arrive, tCalledOff' = tCalledOff, tE2Granted' = seq, tFrozenSet' = tFrozenSet, tE2Refused' = tE2Refused }

  // frozen: E2 re-checks the freeze and gets 503 frozen (08.8:308): a refused outcome, not a grant
  action e2Frozen = all {
    e2 == "waiting", f == "frozen",
    e2' = "refused", e2Wait' = t - e2Since + 1, e2Since' = e2Since, e1' = e1, f' = f, fSince' = fSince, t' = t, keep_r, keep_sec, seq' = seq + 1,
    tFStart' = tFStart, tE2Arrive' = tE2Arrive, tCalledOff' = tCalledOff, tE2Granted' = tE2Granted, tFrozenSet' = tFrozenSet, tE2Refused' = seq }

  // the restore section: an old handler's I/O may be hung; the norm releases only when it cannot write any more
  action secAgeTick = all { secHeld, or { not(RESTORE_RESTART), secAge < 3 }, secAge' = secAge + 1, secHeld' = secHeld, secIoAlive' = secIoAlive, staleAfterRelease' = staleAfterRelease, t' = t, keep_r, keep_e, seq' = seq + 1, keep_stamps }
  action secIoFinish = all { secHeld, secIoAlive, secIoAlive' = false, secHeld' = secHeld, secAge' = secAge, staleAfterRelease' = staleAfterRelease, t' = t, keep_r, keep_e, seq' = seq + 1, keep_stamps }
  action secRelease = all { secHeld, or { not(secIoAlive), RELEASE_ON_CALLOFF }, secHeld' = false, secIoAlive' = secIoAlive, secAge' = secAge, staleAfterRelease' = staleAfterRelease, t' = t, keep_r, keep_e, seq' = seq + 1, keep_stamps }
  action secRestart = all { secHeld, RESTORE_RESTART, secHeld' = false, secIoAlive' = false, secAge' = secAge, staleAfterRelease' = staleAfterRelease, t' = t, keep_r, keep_e, seq' = seq + 1, keep_stamps }
  // an old handler's write occurs while its I/O is alive; after a release it is the bad case
  action secLateWrite = all { secIoAlive, secHeld' = secHeld, secIoAlive' = secIoAlive, secAge' = secAge, staleAfterRelease' = (staleAfterRelease or not(secHeld)), t' = t, keep_r, keep_e, seq' = seq + 1, keep_stamps }

  action stutter = all { t' = t, keep_r, keep_e, keep_sec, seq' = seq, keep_stamps }
  action step = any {
    stutter,
    nondet d = oneOf(Set(1, 10, 30, 45, 60, 90, 100, 120))
    tick(d),
    r2Arrive, r1Finish, r2Grant, r2Refuse, e1Finish, fStart, e2Arrive, fCalloff, fFreeze, e2Grant, e2Frozen,
    secAgeTick, secIoFinish, secRelease, secRestart, secLateWrite,
  }

  // the wait of E2 that is behind a freeze: bounded by the common deadline (it exists in the text)
  val e2WaitingNow = e2 == "waiting"
  val inv_e2_wait_le_deadline = and {
    not(e2WaitingNow) or t - e2Since <= F_DEADLINE,
    e2Wait <= F_DEADLINE + 1,
  }
  // the wait on the member mutex against the same comparator (no term in the P/08 text; 90 s is only a yardstick from 08.8:299)
  val inv_r2_wait_le_deadline = and {
    not(r2 == "waiting") or t - r2Since <= F_DEADLINE,
    r2Wait <= F_DEADLINE + 1,
  }
  val inv_no_stale_after_release = not(staleAfterRelease)
  val inv_section_bounded = not(secHeld and secAge > 3)
  // witnesses of order
  val wit_freeze_blocks_then_calledoff = not(tFStart > 0 and tE2Arrive > tFStart and tCalledOff > tE2Arrive and tE2Granted > tCalledOff)
  val wit_frozen_then_e2_refused = not(tFrozenSet > 0 and tE2Refused > tFrozenSet)
  val wit_r2_waits_long = not(r2 == "waiting" and t - r2Since > F_DEADLINE)
  val wit_r2_refused_by_budget = not(r2 == "refused")
  val wit_e2_waits_nonzero = not(e2Wait > 1)
  // the bound is tight: a completed wait equal to the whole common deadline exists
  val wit_e2_wait_tight = not(e2Wait == F_DEADLINE + 1)
  val wit_r2_budget_tight = not(r2 == "refused" and r2Wait == WAIT_BUDGET + 1)
  val wit_section_io_alive_old = not(secHeld and secAge > 3 and secIoAlive)
}

// the text of P/08 (no mutex budget; freeze has its deadline; the dependency does not answer in the run)
module locks_text { import p08_locks(F_DEADLINE = 90, HANG_END = 1000000, WAIT_BUDGET = 0, HOLD_BUDGET = 0, CALLOFF = true, WRITER_PRIORITY = true, RESTORE_RESTART = false, RELEASE_ON_CALLOFF = false).* }
// a freeze waiter when the dependency answers at t=120 (> the deadline) and at t=30 (< the deadline)
module locks_dep120 { import p08_locks(F_DEADLINE = 90, HANG_END = 120, WAIT_BUDGET = 0, HOLD_BUDGET = 0, CALLOFF = true, WRITER_PRIORITY = true, RESTORE_RESTART = false, RELEASE_ON_CALLOFF = false).* }
module locks_dep30 { import p08_locks(F_DEADLINE = 90, HANG_END = 30, WAIT_BUDGET = 0, HOLD_BUDGET = 0, CALLOFF = true, WRITER_PRIORITY = true, RESTORE_RESTART = false, RELEASE_ON_CALLOFF = false).* }
// control: prod:9 budgets applied (the value of the budget is a model parameter, not a norm number)
module locks_c_budget { import p08_locks(F_DEADLINE = 90, HANG_END = 1000000, WAIT_BUDGET = 45, HOLD_BUDGET = 0, CALLOFF = true, WRITER_PRIORITY = true, RESTORE_RESTART = true, RELEASE_ON_CALLOFF = false).* }
// mutants
module locks_m_nocalloff { import p08_locks(F_DEADLINE = 90, HANG_END = 1000000, WAIT_BUDGET = 0, HOLD_BUDGET = 0, CALLOFF = false, WRITER_PRIORITY = true, RESTORE_RESTART = false, RELEASE_ON_CALLOFF = false).* }
module locks_m_release { import p08_locks(F_DEADLINE = 90, HANG_END = 1000000, WAIT_BUDGET = 0, HOLD_BUDGET = 0, CALLOFF = true, WRITER_PRIORITY = true, RESTORE_RESTART = false, RELEASE_ON_CALLOFF = true).* }
