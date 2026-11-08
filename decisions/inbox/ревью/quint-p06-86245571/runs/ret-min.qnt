// -*- mode: Bluespec; -*-
// Term of a done claim and pending claims: first observation, restarts, cleanup (C7, C5).
// Anchors: 06.1:181 (done kept >= DONE_ANSWER_KEEP), 06.1:183 (local monotonic age, a new observer counts it as fresh), 06.1:772 (keep pending),
//   06.1:1136 (cleanup way chosen by the implementation), const:33 DONE_ANSWER_KEEP, life:92.
// Abstraction: one done claim saved at true time `savedAt`; consoles O1, O2 each with a first-observation mark;
// the cleanup is modelled as a permitted implementation action (the norm does not require one, 06.1:1136) that fires when due (fairness).
// `advance` is capped so that a due cleanup is not skipped. Restart resets a console's first-observation mark and needs `MAX_RESTARTS`.
// NOT modelled: pending claims of unknown outcome being repeated; multiple claims; the sweep marks.
module claim_retention {
  pure val KEEP = 86400          // const:33 DONE_ANSWER_KEEP
  pure val DT = 3600             // @override advance granularity in seconds (model step, no norm)
  pure val MAX_RESTARTS = 2      // @override
  pure val WALL_JUMP = 0         // @override wall-clock jump used only by the mutant
  pure val MUT = "none"          // @override none | wall_age
  type Proc = str
  pure val CONSOLES = Set("O1", "O2")
  type St = { now: int, savedAt: int, present: bool, firstObs: Proc -> int, restarts: int, removedAge: int, wallOffset: int }
  var s: St

  action init = s' = {
    now: 0, savedAt: 0, present: true,
    firstObs: CONSOLES.mapBy(c => -1), restarts: 0, removedAge: -1, wallOffset: 0,
  }

  def age(c: Proc): int = s.now - s.firstObs.get(c)
  def due(c: Proc): bool =
    s.present and s.firstObs.get(c) >= 0 and
    (if (MUT == "wall_age") s.now + s.wallOffset - s.savedAt >= KEEP else age(c) >= KEEP)
  val anyDue = CONSOLES.exists(c => due(c))

  action observe(c: Proc): bool = all {
    s.present, s.firstObs.get(c) < 0,
    s' = {...s, firstObs: s.firstObs.set(c, s.now)},
  }

  // the implementation's cleanup, a permitted action (06.1:1136); uses the local age from the first observation
  action cleanup(c: Proc): bool = all {
    due(c),
    s' = {...s, present: false, removedAge: s.now - s.savedAt},
  }

  // a console restart loses the first observation (06.1:183)
  action restart(c: Proc): bool = all {
    s.present, s.restarts < MAX_RESTARTS, s.firstObs.get(c) >= 0,
    s' = {...s, firstObs: s.firstObs.set(c, -1), restarts: s.restarts + 1},
  }

  // adversary wall jump, only meaningful for the wall_age mutant
  action jump: bool = all {
    WALL_JUMP != 0, s.wallOffset == 0,
    s' = {...s, wallOffset: WALL_JUMP},
  }

  // time passes only after all present consoles have observed the claim (fairness of the observation)
  action advance(d: int): bool = all {
    not(anyDue), not(s.present) or CONSOLES.forall(c => s.firstObs.get(c) >= 0),
    // an advance may not jump over the due moment of any observed console by more than DT (fair cleanup)
    not(s.present) or CONSOLES.forall(c => s.now + d <= s.firstObs.get(c) + KEEP + DT),
    s' = {...s, now: s.now + d},
  }

  action idle = s' = s

  action step = any {
    idle,
    nondet c = oneOf(CONSOLES) any { observe(c), cleanup(c), restart(c) },
    jump,
    nondet d = oneOf(Set(DT, KEEP - DT)) advance(d),
  }

  // -- properties
  // A completed cleanup happened only at true age >= DONE_ANSWER_KEEP (06.1:181).
  val removedNotEarly = s.removedAge < 0 or s.removedAge >= KEEP
  // Liveness-shaped safety: a present claim is not older than KEEP + slack; violated if restarts keep resetting the observation.
  val SLACK = 2 * DT
  val removedInBound = not(s.present) or s.now - s.savedAt <= KEEP + SLACK

  // -- witnesses
  val w_removed = not(not(s.present) and s.removedAge >= KEEP)
  val w_restart_used = not(s.restarts >= 1)
  val c_false = s.now < 0
}
