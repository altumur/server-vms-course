// C13: the silence conclusion of GET /domain/alarms against a wall-clock step of the console.
// Anchors (slice cbf02230):
//   10-domain-console.norms.md:433   "now - last_report > silent_after -> silent"
//   10-domain-console.norms.md:412   last_report is received_at of the mark (the domain clock of the holder process)
//   10-domain-console/forms/runtime-constants.tsv:4   LOST_AFTER 45 s
//   accept.md:63                     REPORT_EVERY 5 s
//   02-installer/spec/02.4-installer.norms.md:370,707  the spare server of the domain; one active by the queue
//   decisions/0130: Addendum (10) item 6 "deadlines are monotonic"
// Assumption A1: `now` at the alarm door is the console's wall clock: the door has no other clock in the text;
//   the same clock is the base of `age` at 10-domain-console.norms.md:90 ("by the wall clock of the console").
// Assumption A2: COLOCATED = the console and the active domain process share a wall clock (norms.md:66 "next to the
//   process domain"); not COLOCATED = they stand on two boxes (the spare server): a step of the console's clock is
//   not a step of the domain's clock.
// Assumption A3: an alive member's report lands at the holder within EVERY.
// A dead member that the door calls silent before LOST_AFTER by a wall-clock step is not counted: the invariant is
// about members that report (a false silence).
// Not modelled: the camera's silent_after, not_reporting (a witness), the windowing of alarms, clock drift,
//   Offsets of the agent's own clock (norms.md:357 are not consulted here).
module clock_core {
  const LOST: int
  const EVERY: int
  const COLOCATED: bool
  const JUMPS: Set[int]     // the values of one wall-clock step of the console; 0 = no step
  const DTS: Set[int]

  var real: int
  var consOff: int
  var domOff: int
  var lastRepReal: int -> int
  var lastRepDom: int -> int
  var alive: int -> bool
  var jumped: bool
  var jumpAt: int
  var seq: int
  var tFalse: int
  var tJump: int

  def M = Set(1, 2)
  def conNow = real + consOff

  // N3 step 1 at the door: silence by the console's wall clock.
  def doorSilent(m: int): bool = conNow - lastRepDom.get(m) > LOST
  def realSilent(m: int): bool = real - lastRepReal.get(m) > LOST
  def falseSilent(m: int): bool = alive.get(m) and doorSilent(m) and not(realSilent(m))
  def falseOk(m: int): bool = realSilent(m) and not(doorSilent(m))

  action init = all {
    real' = 100, consOff' = 0, domOff' = 0,
    lastRepReal' = M.mapBy(_ => 100), lastRepDom' = M.mapBy(_ => 100),
    alive' = M.mapBy(_ => true), jumped' = false, jumpAt' = -1, seq' = 0, tFalse' = -1, tJump' = -1,
  }

  action report(m: int): bool = all {
    alive.get(m),
    lastRepReal' = lastRepReal.set(m, real),
    lastRepDom' = lastRepDom.set(m, real + domOff),
    seq' = seq + 1,
    real' = real, consOff' = consOff, domOff' = domOff, alive' = alive, jumped' = jumped, jumpAt' = jumpAt,
    tFalse' = tFalse, tJump' = tJump,
  }

  action die(m: int): bool = all {
    alive.get(m),
    alive' = alive.set(m, false),
    seq' = seq + 1,
    real' = real, consOff' = consOff, domOff' = domOff, lastRepReal' = lastRepReal, lastRepDom' = lastRepDom,
    jumped' = jumped, jumpAt' = jumpAt, tFalse' = tFalse, tJump' = tJump,
  }

  // One wall-clock step of the console's box. On a shared box it is a step of the domain clock too.
  action jump(d: int): bool = all {
    not(jumped), d != 0,
    jumped' = true, jumpAt' = real, tJump' = seq,
    consOff' = consOff + d,
    domOff' = if (COLOCATED) domOff + d else domOff,
    seq' = seq + 1,
    real' = real, lastRepReal' = lastRepReal, lastRepDom' = lastRepDom, alive' = alive, tFalse' = tFalse,
  }

  action tick(dt: int): bool = all {
    M.forall(m => not(alive.get(m)) or real + dt <= lastRepReal.get(m) + EVERY),
    real' = real + dt,
    seq' = seq + 1,
    consOff' = consOff, domOff' = domOff, lastRepReal' = lastRepReal, lastRepDom' = lastRepDom,
    alive' = alive, jumped' = jumped, jumpAt' = jumpAt, tFalse' = tFalse, tJump' = tJump,
  }

  action step = {
    nondet m = oneOf(M)
    nondet d = oneOf(JUMPS)
    nondet dt = oneOf(DTS)
    any { report(m), die(m), jump(d), tick(dt) }
  }

  // -- invariants: the door's conclusion vs the truth of the model --
  val inv_no_false_silent = M.forall(m => not(falseSilent(m)))
  val inv_no_false_ok = M.forall(m => not(falseOk(m)))
  // A false silence is over within one report period of the step (the next report restores the age).
  val inv_false_silent_transient =
    M.forall(m => falseSilent(m) implies (jumped and real - jumpAt <= EVERY))

  // -- witnesses --
  val wit_mass_false_silent =
    not(M.forall(m => alive.get(m) and falseSilent(m)) and tJump >= 0)
  val wit_false_silent_persists =
    not(M.exists(m => alive.get(m) and falseSilent(m) and jumped and real - jumpAt > EVERY))
  val wit_false_ok_hides_silence =
    not(M.exists(m => not(alive.get(m)) and falseOk(m)) and jumped)
  val wit_true_silent_seen =
    not(M.exists(m => not(alive.get(m)) and realSilent(m) and doorSilent(m)) and not(jumped))
}

// Separate boxes, a forward step of LOST_AFTER; no step of the domain's clock.
module clock_sep {
  import clock_core(LOST=45, EVERY=5, COLOCATED=false, JUMPS=Set(46), DTS=Set(1,5,45,50)).*
}
// Separate boxes, a forward step of 41: age up to 5 s + step 41 > 45.
module clock_sep_41 {
  import clock_core(LOST=45, EVERY=5, COLOCATED=false, JUMPS=Set(41), DTS=Set(1,5,45,50)).*
}
// Separate boxes, a forward step of 40: age <= 5 + 40 not > 45.
module clock_sep_40 {
  import clock_core(LOST=45, EVERY=5, COLOCATED=false, JUMPS=Set(40), DTS=Set(1,5,45,50)).*
}
// One box.
module clock_co {
  import clock_core(LOST=45, EVERY=5, COLOCATED=true, JUMPS=Set(46), DTS=Set(1,5,45,50)).*
}
// One box, a backward step.
module clock_co_back {
  import clock_core(LOST=45, EVERY=5, COLOCATED=true, JUMPS=Set(-46), DTS=Set(1,5,45,50)).*
}
// Separate boxes, a backward step (real silence hidden).
module clock_sep_back {
  import clock_core(LOST=45, EVERY=5, COLOCATED=false, JUMPS=Set(-46), DTS=Set(1,5,45,50)).*
}
// Control: no step at all.
module clock_nojump {
  import clock_core(LOST=45, EVERY=5, COLOCATED=false, JUMPS=Set(0), DTS=Set(1,5,45,50)).*
}
