// C9 and M1 (part 1): the start of a process that loads the row, code 1 and code 2, START_WAIT by a clock.
// Anchors (slice ff32d483):
//   23:207      step 0: schema check; its wait is the same START_WAIT
//   23:212-213  read not confirmed: repeat with a pause of 1 s; after START_WAIT = 60 s from the start, code 1
//   23:211      no row/mark or out of form: code 2
//   23:236-240  code 2 confirmed unfitness, no restart; code 1 temporary, restart after RestartSec
//   23:242      the decision between the two codes is made before the doors open
//   23:373-374  the test of the implementation, not a seam
// The text does not say which clock START_WAIT is measured by (23:213, M1): CLOCK = "wall" or "mono" is a parameter.
// "wall" can jump (JUMP seconds, signed), "mono" cannot. The real time elapsed is tracked separately. The attempts are every
// second of the process clock in fact; the coarse dt only shortens the trace and cannot skip the deadline (guard of tick).
module start_core {
  const START_WAIT: int
  const CLOCK: str          // "wall" | "mono"
  const JUMP: int           // size of a step of the wall clock; forward positive, backward negative
  const DTS: Set[int]

  var real: int             // real seconds since the process started
  var clk: int              // the value the process reads for the wait: real + offset for wall, real for mono
  var offset: int
  var store: str            // "down" | "row" | "absent" | "spoiled"
  var status: str           // "wait" | "serve" | "code1" | "code2"
  var nextTry: int          // clk value of the next read attempt (pause of 1 s)
  var tries: int
  var jumped: bool
  var servedAtUnconfirmed: bool
  var seq: int

  action init = {
    nondet st = oneOf(Set("down", "row", "absent", "spoiled"))
    all {
      real' = 0, clk' = 0, offset' = 0, store' = st, status' = "wait", nextTry' = 0, tries' = 0, jumped' = false,
      servedAtUnconfirmed' = false, seq' = 0,
    }
  }

  action keepStore = store' = store

  // A read attempt: a pause of 1 s between attempts; the outcome by the store state at that moment.
  action read = all {
    status == "wait", clk >= nextTry,
    tries' = tries + 1, nextTry' = clk + 1,
    if (store == "row") all { status' = "serve", servedAtUnconfirmed' = false }
    else if (store == "absent" or store == "spoiled") all { status' = "code2", servedAtUnconfirmed' = servedAtUnconfirmed }
    else if (clk - 0 >= START_WAIT) all { status' = "code1", servedAtUnconfirmed' = servedAtUnconfirmed }
    else all { status' = status, servedAtUnconfirmed' = servedAtUnconfirmed },
    real' = real, clk' = clk, offset' = offset, store' = store, jumped' = jumped, seq' = seq + 1,
  }

  // Time passes. The attempts are not lost when several seconds pass in one step.
  // The waiting process cannot sleep past its own reckoning of the deadline (a coarse clock: the steps are not one per second).
  action tick(dt: int): bool = all {
    status == "wait", clk + dt <= START_WAIT + 1,
    real' = real + dt, clk' = clk + dt, offset' = offset,
    store' = store, status' = status, nextTry' = nextTry, tries' = tries, jumped' = jumped,
    servedAtUnconfirmed' = servedAtUnconfirmed, seq' = seq + 1,
  }

  // The store changes under the waiting process.
  action storeUp(st: str): bool = all {
    status == "wait", store == "down", st != "down",
    store' = st,
    real' = real, clk' = clk, offset' = offset, status' = status, nextTry' = nextTry, tries' = tries, jumped' = jumped,
    servedAtUnconfirmed' = servedAtUnconfirmed, seq' = seq + 1,
  }

  action storeDown = all {
    status == "wait", store == "row" or store == "absent" or store == "spoiled",
    store' = "down",
    real' = real, clk' = clk, offset' = offset, status' = status, nextTry' = nextTry, tries' = tries, jumped' = jumped,
    servedAtUnconfirmed' = servedAtUnconfirmed, seq' = seq + 1,
  }

  action jump = all {
    CLOCK == "wall", status == "wait", not(jumped),
    clk' = clk + JUMP, offset' = offset + JUMP, jumped' = true,
    real' = real, store' = store, status' = status, nextTry' = nextTry, tries' = tries, servedAtUnconfirmed' = servedAtUnconfirmed, seq' = seq + 1,
  }

  action stutter = all {
    status != "wait", real' = real, clk' = clk, offset' = offset, store' = store, status' = status, nextTry' = nextTry, tries' = tries,
    jumped' = jumped, servedAtUnconfirmed' = servedAtUnconfirmed, seq' = seq,
  }

  action step = {
    nondet dt = oneOf(DTS)
    nondet st = oneOf(Set("row", "absent", "spoiled"))
    any { read, tick(dt), storeUp(st), storeDown, jump, stutter }
  }

  // Serving without a confirmed read: guaranteed by the model's own guard; see the report.
  val inv_no_serve_unconfirmed = not(status == "serve") or store == "row"
  val inv_code1_only_after_wait = status != "code1" or real >= START_WAIT
  val inv_wait_real_bounded = status != "wait" or real <= START_WAIT + 2
  val inv_code2_confirmed = status != "code2" or store != "down"
  val inv_one_decision = not(status == "serve" and tries == 0)
  val wit_serve_after_outage = not(status == "serve" and real > 0 and tries >= 2)
  val wit_code1 = not(status == "code1" and real >= START_WAIT)
  val wit_code2 = not(status == "code2" and tries >= 1)
  val wit_wall_jump_premature_code1 = not(status == "code1" and real < START_WAIT)
  val wit_wall_jump_long_wait = not(status == "wait" and real > START_WAIT + 2)
}
