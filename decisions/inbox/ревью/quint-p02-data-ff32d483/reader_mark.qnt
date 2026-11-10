// M5 and M1 (part 2): the mark of a running process after a restore; the period of the check by a clock.
// Anchors (slice ff32d483):
//   23:311      the check on every pass and at least every 30 s
//   23:314-315  a mark with rev not equal to the remembered one and not lower: a change, code 0; a mark below: not a change, wait
//   23:34       the mark never decreases (the writer's rule)
//   23:218      a mark below the row at start is not a refusal
//   p013:136-139 restore: rows return with the versions of the copy
// A process remembers (rev, content). The store mark is (rev, content). Content is the digest named by the mark;
// the process compares the rev only (23:314). The restore returns the mark to a lower rev, nothing else changes.
// PUTS: after the restore the operator puts new manifests; each put raises the mark by one with a new content.
// CMP_DIG: control — a change is also an equal rev with another digest.
module mark_core {
  const CMP_DIG: bool
  const CLOCK: str        // "mono" | "wall" for the period of the check
  const PERIOD: int
  const JUMP: int         // backward step of the wall clock (negative)
  const DTS: Set[int]

  var markRev: int
  var markDig: int
  var memRev: int         // remembered rev of the running process
  var memDig: int         // content the process serves
  var status: str         // "serve" | "stopped0"
  var restored: bool
  var putsAfter: int
  var nextPoll: int
  var clk: int
  var real: int
  var pollsSinceChange: int
  var realAtPublish: int
  var jumped: bool
  var newProcDig: int     // content of a process started now (0 = none yet)

  action init = all {
    markRev' = 5, markDig' = 50, memRev' = 5, memDig' = 50, status' = "serve", restored' = false, putsAfter' = 0,
    nextPoll' = PERIOD, clk' = 0, real' = 0, pollsSinceChange' = 0, realAtPublish' = 0, jumped' = false, newProcDig' = 0,
  }

  def changed: bool =
    (markRev != memRev and markRev >= memRev) or (CMP_DIG and markRev == memRev and markDig != memDig)

  action poll = all {
    status == "serve", clk >= nextPoll,
    nextPoll' = clk + PERIOD, pollsSinceChange' = pollsSinceChange + 1,
    if (changed) status' = "stopped0" else status' = "serve",
    markRev' = markRev, markDig' = markDig, memRev' = memRev, memDig' = memDig, restored' = restored, putsAfter' = putsAfter,
    clk' = clk, real' = real, realAtPublish' = realAtPublish, jumped' = jumped, newProcDig' = newProcDig,
  }

  // The operator restores the store from a copy of rev 3 (once).
  action restore = all {
    not(restored), status == "serve",
    restored' = true, markRev' = 3, markDig' = 30, pollsSinceChange' = 0,
    memRev' = memRev, memDig' = memDig, status' = status, putsAfter' = putsAfter, nextPoll' = nextPoll, clk' = clk, real' = real,
    realAtPublish' = real, jumped' = jumped, newProcDig' = newProcDig,
  }

  // The next put after the restore: rev + 1 with a new content.
  action putAfter = all {
    restored, putsAfter < 3,
    markRev' = markRev + 1, markDig' = markDig + 7, putsAfter' = putsAfter + 1, pollsSinceChange' = 0,
    memRev' = memRev, memDig' = memDig, status' = status, restored' = restored, nextPoll' = nextPoll, clk' = clk, real' = real,
    realAtPublish' = real, jumped' = jumped, newProcDig' = newProcDig,
  }

  // A process started now reads the row of the current mark and serves it.
  action startNew = all {
    status == "serve", newProcDig == 0,
    newProcDig' = markDig,
    markRev' = markRev, markDig' = markDig, memRev' = memRev, memDig' = memDig, status' = status, restored' = restored,
    putsAfter' = putsAfter, nextPoll' = nextPoll, clk' = clk, real' = real, pollsSinceChange' = pollsSinceChange, realAtPublish' = realAtPublish, jumped' = jumped,
  }

  // The process keeps its schedule by its own clock: time cannot pass a due poll.
  action tick(dt: int): bool = all {
    status != "serve" or clk + dt <= nextPoll,
    real' = real + dt, clk' = clk + dt,
    markRev' = markRev, markDig' = markDig, memRev' = memRev, memDig' = memDig, status' = status, restored' = restored, putsAfter' = putsAfter,
    nextPoll' = nextPoll, pollsSinceChange' = pollsSinceChange, realAtPublish' = realAtPublish, jumped' = jumped, newProcDig' = newProcDig,
  }

  action jump = all {
    CLOCK == "wall", not(jumped),
    jumped' = true, clk' = clk + JUMP,
    markRev' = markRev, markDig' = markDig, memRev' = memRev, memDig' = memDig, status' = status, restored' = restored, putsAfter' = putsAfter,
    nextPoll' = nextPoll, pollsSinceChange' = pollsSinceChange, real' = real, realAtPublish' = realAtPublish, newProcDig' = newProcDig,
  }

  action stutter = all {
    status != "serve",
    markRev' = markRev, markDig' = markDig, memRev' = memRev, memDig' = memDig, status' = status, restored' = restored, putsAfter' = putsAfter,
    nextPoll' = nextPoll, clk' = clk, real' = real, pollsSinceChange' = pollsSinceChange, realAtPublish' = realAtPublish, jumped' = jumped, newProcDig' = newProcDig,
  }

  action step = {
    nondet dt = oneOf(DTS)
    any { poll, restore, putAfter, startNew, tick(dt), jump, stutter }
  }

  // The process keeps serving content the mark no longer names, after polling the current mark (23:314 is by rev only).
  val wit_stale_after_restore_lower = not(status == "serve" and restored and markRev < memRev and pollsSinceChange >= 1)
  val wit_new_differs = not(status == "serve" and newProcDig != 0 and newProcDig != memDig and pollsSinceChange >= 1 and markRev < memRev)
  val wit_equal_rev_other_content = not(status == "serve" and restored and markRev == memRev and markDig != memDig and pollsSinceChange >= 1)
  val inv_no_stale_at_equal_rev = status != "serve" or pollsSinceChange == 0 or not(markRev == memRev and markDig != memDig)
  val inv_stop_within_period = status != "serve" or not(restored) or markRev < memRev or real - realAtPublish <= PERIOD + 1 or not(changed)
  // property on the mark rising normally (no restore): a change is detected on the next poll
  val wit_stop_on_rise = not(status == "stopped0" and restored and markRev > memRev)
  val wit_stops_on_equal_rev_ctrl = not(status == "stopped0" and markRev == memRev and markDig != memDig)
  val wit_poll_delayed_by_backward_jump = not(status == "serve" and jumped and real > PERIOD + 1 and pollsSinceChange == 0 and clk < nextPoll)
  val inv_period_real = jumped or pollsSinceChange >= 1 or real - realAtPublish <= PERIOD + 1 or restored
}
