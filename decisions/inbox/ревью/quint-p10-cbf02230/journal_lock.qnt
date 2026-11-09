// C15: a door that must write a journal line under flock, with a stuck lock holder and an I/O error.
// Anchors (slice cbf02230):
//   10-domain-console.norms.md:57        role journal audit/domainconsole
//   gate-and-pass.md:168                 "403 -> the journal access.denied"
//   event-journal.md:92-93               all processes of the role write audit/<role>/e1; flock LOCK_EX
//   event-journal.md:188                 append; fsync of the line
//   event-journal.md:202                 an I/O error -> "an error to the caller, without an automatic repeat"; "the caller decides"
//   event-journal.md:222                 "Common finite budgets ... are required for the applicable phases of this contract"
//   production-obligations.md:9,11       budgets for "lock acquisition and lock holding"; "A stalled dependency cannot indefinitely hold a shared lock"
// The model has three layers:
//   LOCK_BUDGET=0 — no wait term (only the text of P/10, with no link to the common budget);
//   LOCK_BUDGET>0 — the common obligation carried by event-journal.md:222 → production-obligations.md:9;
//   ON_FAIL=1 — the proposed caller outcome of C15 (a control, not in the text).
// ON_FAIL=0 (silent) admits both "403 answered anyway, line lost" and "503 to the client".
// Assumption: the order of journal line and answer is not named in the text; the model lets the door answer
// only after the attempt to write (the stronger, easier side for the door). Not modelled: alarms journal,
// other doors, fsync of directories, the unit of a line, the torn tail (event-journal.md:188-191).
module journal_core {
  const LOCK_BUDGET: int   // 0 = none
  const ENFORCED: bool     // false = mutant: the budget is not enforced
  const ON_FAIL: int       // 0 = silent, 1 = control: a failed journal -> 503
  const WAIT_H: int        // the bound H of inv_wait_bounded
  const DTS: Set[int]

  def R = Set(1, 2)
  var now: int
  var seq: int
  var holder: int          // 0 none; 9 the other process of the role; or a request id
  var holderStuck: bool
  var phase: int -> str    // none | wait | write | ready | answered
  var waitStart: int -> int
  var lineOk: int -> bool
  var failure: int -> str  // "" | io | timeout
  var ans: int -> str      // "" | 403 | 503
  var tStuck: int
  var tAcq: int -> int
  var tLost: int

  action init = all {
    now' = 0, seq' = 0, holder' = 0, holderStuck' = false,
    phase' = R.mapBy(_ => "none"), waitStart' = R.mapBy(_ => -1),
    lineOk' = R.mapBy(_ => false), failure' = R.mapBy(_ => ""), ans' = R.mapBy(_ => ""),
    tStuck' = -1, tAcq' = R.mapBy(_ => -1), tLost' = -1,
  }

  action arrive(r: int): bool = all {
    phase.get(r) == "none",
    phase' = phase.set(r, "wait"), waitStart' = waitStart.set(r, now),
    seq' = seq + 1,
    now' = now, holder' = holder, holderStuck' = holderStuck, lineOk' = lineOk, failure' = failure, ans' = ans,
    tStuck' = tStuck, tAcq' = tAcq, tLost' = tLost,
  }

  action otherTakes = all {
    holder == 0,
    holder' = 9,
    seq' = seq + 1,
    now' = now, holderStuck' = holderStuck, phase' = phase, waitStart' = waitStart, lineOk' = lineOk,
    failure' = failure, ans' = ans, tStuck' = tStuck, tAcq' = tAcq, tLost' = tLost,
  }

  action otherReleases = all {
    holder == 9, not(holderStuck),
    holder' = 0,
    seq' = seq + 1,
    now' = now, holderStuck' = holderStuck, phase' = phase, waitStart' = waitStart, lineOk' = lineOk,
    failure' = failure, ans' = ans, tStuck' = tStuck, tAcq' = tAcq, tLost' = tLost,
  }

  // The holder stalls in write or fsync (a stuck medium).
  action stuck = all {
    holder != 0, not(holderStuck),
    holderStuck' = true, tStuck' = seq,
    seq' = seq + 1,
    now' = now, holder' = holder, phase' = phase, waitStart' = waitStart, lineOk' = lineOk,
    failure' = failure, ans' = ans, tAcq' = tAcq, tLost' = tLost,
  }

  action acquire(r: int): bool = all {
    phase.get(r) == "wait", holder == 0,
    holder' = r, phase' = phase.set(r, "write"), tAcq' = tAcq.set(r, seq),
    seq' = seq + 1,
    now' = now, holderStuck' = holderStuck, waitStart' = waitStart, lineOk' = lineOk, failure' = failure, ans' = ans,
    tStuck' = tStuck, tLost' = tLost,
  }

  action writeOk(r: int): bool = all {
    phase.get(r) == "write", holder == r, not(holderStuck),
    lineOk' = lineOk.set(r, true), phase' = phase.set(r, "ready"), holder' = 0,
    seq' = seq + 1,
    now' = now, holderStuck' = holderStuck, waitStart' = waitStart, failure' = failure, ans' = ans,
    tStuck' = tStuck, tAcq' = tAcq, tLost' = tLost,
  }

  action writeErr(r: int): bool = all {
    phase.get(r) == "write", holder == r, not(holderStuck),
    failure' = failure.set(r, "io"), phase' = phase.set(r, "ready"), holder' = 0,
    seq' = seq + 1,
    now' = now, holderStuck' = holderStuck, waitStart' = waitStart, lineOk' = lineOk, ans' = ans,
    tStuck' = tStuck, tAcq' = tAcq, tLost' = tLost,
  }

  // The wait term ran out (only with the common budget).
  action expire(r: int): bool = all {
    LOCK_BUDGET > 0,
    phase.get(r) == "wait" or phase.get(r) == "write",
    now >= waitStart.get(r) + LOCK_BUDGET,
    failure' = failure.set(r, "timeout"), phase' = phase.set(r, "ready"),
    holder' = if (holder == r) 0 else holder,
    holderStuck' = if (holder == r) false else holderStuck,
    seq' = seq + 1,
    now' = now, waitStart' = waitStart, lineOk' = lineOk, ans' = ans, tStuck' = tStuck, tAcq' = tAcq, tLost' = tLost,
  }

  action answer(r: int, a: str): bool = all {
    phase.get(r) == "ready",
    if (failure.get(r) == "") a == "403" else (ON_FAIL == 0 or a == "503"),
    ans' = ans.set(r, a), phase' = phase.set(r, "answered"),
    tLost' = if (a == "403" and not(lineOk.get(r))) seq else tLost,
    seq' = seq + 1,
    now' = now, holder' = holder, holderStuck' = holderStuck, waitStart' = waitStart, lineOk' = lineOk,
    failure' = failure, tStuck' = tStuck, tAcq' = tAcq,
  }

  // The stuck holder may be `r` itself, stuck in fsync: expire above covers it.
  // Urgency only if the common budget is present and enforced.
  action tick(dt: int): bool = all {
    not(ENFORCED) or LOCK_BUDGET == 0 or R.forall(r =>
       (phase.get(r) != "wait" and phase.get(r) != "write")
       or now + dt <= waitStart.get(r) + LOCK_BUDGET),
    now' = now + dt, seq' = seq + 1,
    holder' = holder, holderStuck' = holderStuck, phase' = phase, waitStart' = waitStart, lineOk' = lineOk,
    failure' = failure, ans' = ans, tStuck' = tStuck, tAcq' = tAcq, tLost' = tLost,
  }

  action step = {
    nondet r = oneOf(R)
    nondet a = oneOf(Set("403", "503"))
    nondet dt = oneOf(DTS)
    any { arrive(r), otherTakes, otherReleases, stuck, acquire(r), writeOk(r), writeErr(r), expire(r), answer(r, a), tick(dt) }
  }

  // The budget covers acquiring and holding: production-obligations.md:9, :11 ("lock acquisition and lock holding").
  val waiting = R.filter(r => phase.get(r) == "wait" or phase.get(r) == "write")
  val inv_wait_bounded = waiting.forall(r => now - waitStart.get(r) <= WAIT_H)
  val inv_no_silent_loss = R.forall(r => ans.get(r) == "403" implies lineOk.get(r))
  val inv_answer_has_cause = R.forall(r => (ans.get(r) == "403" and failure.get(r) == "") implies lineOk.get(r))

  // witnesses: violated iff the ordered situation is reachable
  val wit_stuck_blocks_both =
    not(tStuck >= 0 and holderStuck and R.forall(r => phase.get(r) == "wait") and R.forall(r => now - waitStart.get(r) >= 50))
  val wit_timeout_then_403_lost =
    not(R.exists(r => failure.get(r) == "timeout" and ans.get(r) == "403" and tLost > tStuck) and tStuck >= 0)
  val wit_io_then_403_lost =
    not(R.exists(r => failure.get(r) == "io" and ans.get(r) == "403" and tLost >= 0))
  val wit_line_written_answered =
    not(R.exists(r => lineOk.get(r) and ans.get(r) == "403"))
  val wit_timeout_503 =
    not(R.exists(r => failure.get(r) == "timeout" and ans.get(r) == "503") and tStuck >= 0)
}

module journal_norm {
  import journal_core(LOCK_BUDGET=0, ENFORCED=true, ON_FAIL=0, WAIT_H=50, DTS=Set(1,50)).*
}
// The common obligation only: the wait is bounded, the caller's outcome is still not named.
module journal_budget {
  import journal_core(LOCK_BUDGET=30, ENFORCED=true, ON_FAIL=0, WAIT_H=30, DTS=Set(1,30,50)).*
}
// Control: common budget + a named caller outcome.
module journal_ctrl {
  import journal_core(LOCK_BUDGET=30, ENFORCED=true, ON_FAIL=1, WAIT_H=30, DTS=Set(1,30,50)).*
}
// Mutant: the budget is declared but not enforced.
module journal_mut_unenforced {
  import journal_core(LOCK_BUDGET=30, ENFORCED=false, ON_FAIL=1, WAIT_H=30, DTS=Set(1,30,50)).*
}
