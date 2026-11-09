// -*- mode: Bluespec; -*-
// P/08 model unit: wall-clock jumps of the holder (C16). Three small independent modules: the name hold of a deleted person;
// the window of books after a term taken; the wait of a planned key change.
// Anchors: 08.4:79 (mark until at + TOKEN_LIFETIME + TOKEN_SKEW, `at` — wall clock of the holder at the write);
// runtime-constants.tsv:14 (TOKEN_LIFETIME 900); common/contracts/domain-token.md:45 (TOKEN_SKEW 60, wall clock of the checker), :86
// (now > exp + TOKEN_SKEW -> expired); 08.2:83 (premise: the wall clocks of the holders differ by at most TOKEN_SKEW);
// 08.5:55 (books window: now − at ≤ LOST_AFTER by the wall clock of the process; LOST_AFTER 45 accept.md:92);
// 08.2:77-79 (a change waits until the clock catches up with rev; 08.2:80 emergency rev = max(known+1, floor(now)+TOKEN_SKEW+1)).
// NOT modelled: restart, several holders, real hardware clock mechanisms, PARTIAL_QUIET (monotonic, p08_age).
module p08_clock_hold {
  const LIFETIME: int
  const SKEW: int
  const J: int              // the size of a forward jump of the holder's wall clock (environment)
  const CHECKER_OFF: int    // checker wall clock − real; premise-bound for honest scenarios (absolute value ≤ SKEW)
  const Q6_DEFER: bool      // control: after a detected jump the destructive step is deferred (Q6 applied; not at the pin)
  const FREE_SKEW: int      // the hold uses this skew in its until (normally = SKEW); mutant 0
  const JUMP_AFTER_MARK_ONLY: bool // scenario restricted to a jump after the delete mark; false — a token minted during the jump is also in scope

  var real: int
  var off: int              // holder wall − real
  var issued: bool
  var exp: int              // the token's exp: holder wall at issue + LIFETIME
  var at: int               // wall at the delete mark write (0 = no mark)
  var freed: bool           // the name hold ended and the name was free
  var aliveAtFree: bool     // the token still valid on the checker at the moment of free
  var jumped: bool
  var seq: int
  var tIssue: int
  var tMark: int
  var tJump: int
  var tFree: int

  action init = all { real' = 0, off' = 0, issued' = false, exp' = 0, at' = 0, freed' = false, aliveAtFree' = false, jumped' = false, seq' = 1, tIssue' = 0, tMark' = 0, tJump' = 0, tFree' = 0 }

  action issue = all { not(issued), at == 0, issued' = true, exp' = real + off + LIFETIME, real' = real, off' = off, at' = at, freed' = freed, aliveAtFree' = aliveAtFree, jumped' = jumped, seq' = seq + 1, tIssue' = seq, tMark' = tMark, tJump' = tJump, tFree' = tFree }
  action mark = all { issued, at == 0, at' = real + off, real' = real, off' = off, issued' = issued, exp' = exp, freed' = freed, aliveAtFree' = aliveAtFree, jumped' = jumped, seq' = seq + 1, tIssue' = tIssue, tMark' = seq, tJump' = tJump, tFree' = tFree }
  action advance(d: int): bool = all { d > 0, real' = real + d, off' = off, issued' = issued, exp' = exp, at' = at, freed' = freed, aliveAtFree' = aliveAtFree, jumped' = jumped, seq' = seq + 1, tIssue' = tIssue, tMark' = tMark, tJump' = tJump, tFree' = tFree }
  action jump = all { not(jumped), J > 0, or { not(JUMP_AFTER_MARK_ONLY), at != 0 }, off' = off + J, jumped' = true, real' = real, issued' = issued, exp' = exp, at' = at, freed' = freed, aliveAtFree' = aliveAtFree, seq' = seq + 1, tIssue' = tIssue, tMark' = tMark, tJump' = seq, tFree' = tFree }
  action free = all {
    at != 0, not(freed), real + off > at + LIFETIME + FREE_SKEW, // strictly past the until (08.4:79)
    not(Q6_DEFER and jumped),
    freed' = true, aliveAtFree' = real + CHECKER_OFF <= exp + SKEW,
    real' = real, off' = off, issued' = issued, exp' = exp, at' = at, jumped' = jumped, seq' = seq + 1, tIssue' = tIssue, tMark' = tMark, tJump' = tJump, tFree' = seq,
  }
  // a jump back to true time (a correction) and the deferred end of a Q6 hold: the mark lives on (control)
  action correct = all { jumped, off != 0, off' = 0, jumped' = false, real' = real, issued' = issued, exp' = exp, at' = at, freed' = freed, aliveAtFree' = aliveAtFree, seq' = seq + 1, tIssue' = tIssue, tMark' = tMark, tJump' = tJump, tFree' = tFree }

  action step = any { issue, mark, jump, free, correct, nondet d = oneOf(Set(1, 60, 240, 300, 600, 900)) advance(d) }

  val inv_hold_covers_token = not(aliveAtFree)
  val wit_free_after_issue = not(tMark > tIssue and tFree > tMark)
  val wit_jump_free_alive = not(tMark > tIssue and tJump > tMark and tFree > tJump and aliveAtFree)
}
module hold_j0_slow { import p08_clock_hold(LIFETIME = 900, SKEW = 60, J = 0, CHECKER_OFF = 0, Q6_DEFER = false, JUMP_AFTER_MARK_ONLY = true, FREE_SKEW = 60).* }
module hold_j0_checker_behind60 { import p08_clock_hold(LIFETIME = 900, SKEW = 60, J = 0, CHECKER_OFF = -60, Q6_DEFER = false, JUMP_AFTER_MARK_ONLY = true, FREE_SKEW = 60).* }
module hold_j60_checker_true { import p08_clock_hold(LIFETIME = 900, SKEW = 60, J = 60, CHECKER_OFF = 0, Q6_DEFER = false, JUMP_AFTER_MARK_ONLY = true, FREE_SKEW = 60).* }
module hold_j600 { import p08_clock_hold(LIFETIME = 900, SKEW = 60, J = 600, CHECKER_OFF = 0, Q6_DEFER = false, JUMP_AFTER_MARK_ONLY = true, FREE_SKEW = 60).* }
module hold_j600_anytime { import p08_clock_hold(LIFETIME = 900, SKEW = 60, J = 600, CHECKER_OFF = 0, Q6_DEFER = false, JUMP_AFTER_MARK_ONLY = false, FREE_SKEW = 60).* }
module hold_m_noskew { import p08_clock_hold(LIFETIME = 900, SKEW = 60, J = 0, CHECKER_OFF = 0, Q6_DEFER = false, JUMP_AFTER_MARK_ONLY = true, FREE_SKEW = 0).* }
module hold_c_q6 { import p08_clock_hold(LIFETIME = 900, SKEW = 60, J = 600, CHECKER_OFF = 0, Q6_DEFER = true, JUMP_AFTER_MARK_ONLY = true, FREE_SKEW = 60).* }

module p08_clock_books {
  // books window after a term taken: wall-clock window; a jump closes it early / extends it.
  const LOST_AFTER: int // 45
  const J: int          // forward jump (>0) or backward (negative) of the wall clock after the take

  var real: int
  var off: int
  var at: int      // wall at the take (the term record's at)
  var assembled: bool
  var assembledAtReal: int
  var jumped: bool
  action init = all { real' = 0, off' = 0, at' = 0, assembled' = false, assembledAtReal' = 0, jumped' = false }
  action advance(d: int): bool = all { d > 0, real' = real + d, off' = off, at' = at, assembled' = assembled, assembledAtReal' = assembledAtReal, jumped' = jumped }
  action jump = all { not(jumped), J != 0, off' = off + J, jumped' = true, real' = real, at' = at, assembled' = assembled, assembledAtReal' = assembledAtReal }
  action assemble = all {
    not(assembled), (real + off) - at > LOST_AFTER,
    assembled' = true, assembledAtReal' = real, real' = real, off' = off, at' = at, jumped' = jumped,
  }
  action step = any { assemble, jump, nondet d = oneOf(Set(1, 5, 10, 30, 45, 100, 200)) advance(d) }
  // by the real time from the take, the first assembly waits the whole window
  val inv_assembly_after_real_window = not(assembled and assembledAtReal <= LOST_AFTER)
  // backward jump: the assembly delayed past a chosen yardstick (no bound named) — here against 3*LOST_AFTER
  val wit_assembly_blocked_past_3x = not(real > 3 * LOST_AFTER and (real + off) - at <= LOST_AFTER)
  val wit_assembly_early = not(assembled and assembledAtReal <= LOST_AFTER)
}
module books_nojump { import p08_clock_books(LOST_AFTER = 45, J = 0).* }
module books_forward { import p08_clock_books(LOST_AFTER = 45, J = 60).* }
module books_back { import p08_clock_books(LOST_AFTER = 45, J = -300).* }

module p08_clock_rev {
  // the wait of a planned key change until the wall clock catches up with rev (08.2:77-79); after an emergency set
  // (08.2:80-82) rev is up to TOKEN_SKEW + 1 ahead; a forward jump followed by a correction raises it by J.
  const SKEW: int
  const J: int
  var real: int
  var off: int
  var rev: int
  var waitStart: int   // real time the planned change began to wait (0 = not waiting)
  var waited: int      // measured wait at completion
  var phase: str       // init | jumped | waiting | done
  action init = all { real' = 1000, off' = 0, rev' = 1000 + SKEW + 1, waitStart' = 0, waited' = 0, phase' = "init" }
  action jump = all { phase == "init", J > 0, phase' = "jumped", off' = J, rev' = real + J, real' = real, waitStart' = waitStart, waited' = waited }
  action correct = all { phase == "jumped", off' = 0, phase' = "waiting_corrected", real' = real, rev' = rev, waitStart' = real, waited' = waited }
  action plan = all {
    phase == "init" or phase == "waiting_corrected",
    waitStart == 0, phase' = "waiting", off' = off, waitStart' = real, real' = real, rev' = rev, waited' = waited,
  }
  // time does not overshoot the moment the waiting change becomes possible (waits measured exactly)
  action advance(d: int): bool = all { d > 0, or { not(phase == "waiting" or phase == "waiting_corrected"), real + d + off <= rev + 1 }, real' = real + d, off' = off, rev' = rev, waitStart' = waitStart, waited' = waited, phase' = phase }
  action complete = all {
    (phase == "waiting" or phase == "waiting_corrected"), rev + 1 <= real + off,
    phase' = "done", waited' = real - waitStart, real' = real, off' = off, rev' = rev, waitStart' = waitStart,
  }
  action step = any { jump, correct, plan, complete, nondet d = oneOf(Set(1, 5, 30, 60, 300, 600)) advance(d) }
  // the wait of the change is bounded by the emergency's own advance TOKEN_SKEW + 2 (a yardstick from 08.2:80)
  val inv_wait_le_skew = waited <= SKEW + 2 // measured wait is 0 when not done; the comparator is exact
  val wit_waited = waited == 0
  // the yardstick is tight: the completed wait equals the emergency advance
  val wit_waited_tight = waited != SKEW + 2
}
module rev_nojump { import p08_clock_rev(SKEW = 60, J = 0).* }
module rev_jump_big { import p08_clock_rev(SKEW = 60, J = 600).* }
