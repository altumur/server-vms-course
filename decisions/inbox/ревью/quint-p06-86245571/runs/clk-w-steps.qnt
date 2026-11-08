// -*- mode: Bluespec; -*-
// OPS_RUN_MAX / OPS_KEEP counted on wall clocks (06.9:28, 06.9:405, 06.9:494) under clock jumps.
// Anchors: 06.9:28 (wall clocks, "neither a step nor a right depends on it"), 06.9:405 (round: now > created_at + OPS_RUN_MAX),
//   06.9:440 (finish), 06.9:494 (reaper: now >= finished_at + OPS_KEEP), 06.9:494 ("record last"), const:23,24,16.
// Abstraction: one operation with two steps, one leader L, one reaper R (acceptor clock = L at init); true time `t` in seconds;
// `advance` moves t but is capped so that a deadline by the actor's wall clock is crossed by at most OPS_TICK (fair ticking).
// Assumption A1 (fairness): the leader ticks and the reaper passes as soon as the wall-clock condition holds (06.9:395); this model
// does not check lost/late ticks. Assumption A2: wall-clock jumps are instantaneous adversary steps of bounded size (`JUMPS`),
// the magnitude has no normative source and is a parameter of the adversary, not a claim about real systems.
// NOT modelled: tokens/exp, pause, rebinding, fail outcomes, opbusy, secrets, the step call transport.
module ops_clock {
  pure val OPS_RUN_MAX = 86400   // const:23
  pure val OPS_KEEP = 86400      // const:24
  pure val OPS_TICK = 5          // const:22
  pure val OPS_STEP_WAIT = 30    // const:20
  pure val STEPS = 2
  pure val JUMPS = Set(86405)  // @override forward jump of a wall clock (size = adversary parameter, NOT a norm number)
  pure val MAX_JUMPS = 1          // @override
  pure val MUT = "none"           // @override none | run_ge0 | reap_nokeep
  pure val MONO = false           // @override deadlines by monotonic first observation (the repair of finding S13, not in the norm; control only)
  pure val BOUND = OPS_RUN_MAX + 2 * OPS_TICK + OPS_STEP_WAIT // model-derived bound on true age of a running op under fair ticks without jumps (see report)

  var t: int                      // true (monotonic) seconds
  var wallL: int                  // leader wall offset
  var wallR: int                  // reaper wall offset
  var recSt: str                  // running | done | absent
  var createdAt: int
  var finishedAt: int
  var cancel: bool
  var nextStep: int               // index of the first step without an outcome; STEPS = none left
  var cancelledSteps: int         // steps finished with outcome cancel at finish
  var okSteps: int
  var openCall: bool
  var openSince: int
  var jumpsLeft: int
  // monotonic observations (MONO only, repair control)
  var obsCreateL: int             // true time of first observation of the op by the leader
  var obsFinishR: int             // true time of first observation of the finished op by the reaper
  // ghosts on completed actions
  var cancelAge: int              // true age at clock-based cancel, -1 = none
  var finishAge: int              // true age at finish, -1 = none
  var reapAge: int                // true age since the true finish at reap, -1 = none
  var clockCancelledSteps: int    // number of steps cancelled solely by the clock before true age OPS_RUN_MAX
  var tFinished: int

  val wallLeader = t + wallL
  val wallReaper = t + wallR

  val runDue = if (MONO) (recSt == "running" and not(cancel) and t - obsCreateL > OPS_RUN_MAX)
               else (recSt == "running" and not(cancel) and wallLeader > createdAt + OPS_RUN_MAX)
  val finishDue = recSt == "running" and cancel and not(openCall)
  val reapDue = recSt == "done" and (if (MONO) t - obsFinishR >= OPS_KEEP else wallReaper >= finishedAt + OPS_KEEP)

  action init = all {
    t' = 0, wallL' = 0, wallR' = 0, recSt' = "running", createdAt' = 0, finishedAt' = -1,
    cancel' = false, nextStep' = 0, cancelledSteps' = 0, okSteps' = 0, openCall' = false, openSince' = -1,
    jumpsLeft' = MAX_JUMPS, obsCreateL' = 0, obsFinishR' = 0,
    cancelAge' = -1, finishAge' = -1, reapAge' = -1, clockCancelledSteps' = 0, tFinished' = -1,
  }

  action uAll = all {
    t' = t, wallL' = wallL, wallR' = wallR, recSt' = recSt, createdAt' = createdAt, finishedAt' = finishedAt,
    cancel' = cancel, nextStep' = nextStep, cancelledSteps' = cancelledSteps, okSteps' = okSteps, openCall' = openCall,
    openSince' = openSince, jumpsLeft' = jumpsLeft, obsCreateL' = obsCreateL, obsFinishR' = obsFinishR,
    cancelAge' = cancelAge, finishAge' = finishAge, reapAge' = reapAge, clockCancelledSteps' = clockCancelledSteps, tFinished' = tFinished,
  }

  // 06.9 step: open a call of the first step without an outcome
  action openStep = all {
    recSt == "running", not(cancel), not(openCall), nextStep < STEPS,
    openCall' = true, openSince' = t,
    t' = t, wallL' = wallL, wallR' = wallR, recSt' = recSt, createdAt' = createdAt, finishedAt' = finishedAt,
    cancel' = cancel, nextStep' = nextStep, cancelledSteps' = cancelledSteps, okSteps' = okSteps,
    jumpsLeft' = jumpsLeft, obsCreateL' = obsCreateL, obsFinishR' = obsFinishR,
    cancelAge' = cancelAge, finishAge' = finishAge, reapAge' = reapAge, clockCancelledSteps' = clockCancelledSteps, tFinished' = tFinished,
  }

  // the step call ends with an outcome ok (the worker batch) within OPS_STEP_WAIT
  action stepOk = all {
    openCall,
    openCall' = false, openSince' = -1, nextStep' = nextStep + 1, okSteps' = okSteps + 1,
    t' = t, wallL' = wallL, wallR' = wallR, recSt' = recSt, createdAt' = createdAt, finishedAt' = finishedAt,
    cancel' = cancel, cancelledSteps' = cancelledSteps,
    jumpsLeft' = jumpsLeft, obsCreateL' = obsCreateL, obsFinishR' = obsFinishR,
    cancelAge' = cancelAge, finishAge' = finishAge, reapAge' = reapAge, clockCancelledSteps' = clockCancelledSteps, tFinished' = tFinished,
  }

  // the call ends without an outcome (dead ticket at OPS_STEP_WAIT)
  action stepTimeout = all {
    openCall, t - openSince >= OPS_STEP_WAIT,
    openCall' = false, openSince' = -1,
    t' = t, wallL' = wallL, wallR' = wallR, recSt' = recSt, createdAt' = createdAt, finishedAt' = finishedAt,
    cancel' = cancel, nextStep' = nextStep, cancelledSteps' = cancelledSteps, okSteps' = okSteps,
    jumpsLeft' = jumpsLeft, obsCreateL' = obsCreateL, obsFinishR' = obsFinishR,
    cancelAge' = cancelAge, finishAge' = finishAge, reapAge' = reapAge, clockCancelledSteps' = clockCancelledSteps, tFinished' = tFinished,
  }

  // round step 1: time-based cancel (06.9:405)
  action roundCancel = all {
    if (MUT == "run_ge0") (recSt == "running" and not(cancel) and wallLeader >= createdAt)
    else runDue,
    cancel' = true, cancelAge' = t,
    t' = t, wallL' = wallL, wallR' = wallR, recSt' = recSt, createdAt' = createdAt, finishedAt' = finishedAt,
    nextStep' = nextStep, cancelledSteps' = cancelledSteps, okSteps' = okSteps, openCall' = openCall, openSince' = openSince,
    jumpsLeft' = jumpsLeft, obsCreateL' = obsCreateL, obsFinishR' = obsFinishR,
    finishAge' = finishAge, reapAge' = reapAge, clockCancelledSteps' = clockCancelledSteps, tFinished' = tFinished,
  }

  // finish (06.9:440): remaining steps get outcome cancel
  action finish = all {
    finishDue,
    val rem = STEPS - nextStep
    all {
      recSt' = "done", finishedAt' = wallLeader, cancelledSteps' = rem, finishAge' = t, tFinished' = t,
      clockCancelledSteps' = if (cancelAge >= 0 and cancelAge < OPS_RUN_MAX) rem else 0,
      obsFinishR' = t,
      t' = t, wallL' = wallL, wallR' = wallR, createdAt' = createdAt, cancel' = cancel, nextStep' = nextStep, okSteps' = okSteps,
      openCall' = openCall, openSince' = openSince, jumpsLeft' = jumpsLeft, obsCreateL' = obsCreateL, cancelAge' = cancelAge, reapAge' = reapAge,
    }
  }

  // all steps done: normal finish
  action finishComplete = all {
    recSt == "running", not(cancel), not(openCall), nextStep == STEPS,
    recSt' = "done", finishedAt' = wallLeader, finishAge' = t, tFinished' = t, obsFinishR' = t,
    t' = t, wallL' = wallL, wallR' = wallR, createdAt' = createdAt, cancel' = cancel, nextStep' = nextStep, cancelledSteps' = cancelledSteps, okSteps' = okSteps,
    openCall' = openCall, openSince' = openSince, jumpsLeft' = jumpsLeft, obsCreateL' = obsCreateL, cancelAge' = cancelAge, reapAge' = reapAge,
    clockCancelledSteps' = clockCancelledSteps,
  }

  // reaper removes the record (06.9:494)
  action reap = all {
    if (MUT == "reap_nokeep") recSt == "done" else reapDue,
    recSt' = "absent", reapAge' = t - tFinished,
    t' = t, wallL' = wallL, wallR' = wallR, createdAt' = createdAt, finishedAt' = finishedAt,
    cancel' = cancel, nextStep' = nextStep, cancelledSteps' = cancelledSteps, okSteps' = okSteps,
    openCall' = openCall, openSince' = openSince, jumpsLeft' = jumpsLeft, obsCreateL' = obsCreateL, obsFinishR' = obsFinishR,
    cancelAge' = cancelAge, finishAge' = finishAge, clockCancelledSteps' = clockCancelledSteps, tFinished' = tFinished,
  }

  // adversary: wall-clock jump of the leader or the reaper
  action jumpL(j: int): bool = all { jumpsLeft > 0, wallL' = wallL + j, jumpsLeft' = jumpsLeft - 1,
    t' = t, wallR' = wallR, recSt' = recSt, createdAt' = createdAt, finishedAt' = finishedAt, cancel' = cancel, nextStep' = nextStep,
    cancelledSteps' = cancelledSteps, okSteps' = okSteps, openCall' = openCall, openSince' = openSince, obsCreateL' = obsCreateL, obsFinishR' = obsFinishR,
    cancelAge' = cancelAge, finishAge' = finishAge, reapAge' = reapAge, clockCancelledSteps' = clockCancelledSteps, tFinished' = tFinished }
  action jumpR(j: int): bool = all { jumpsLeft > 0, wallR' = wallR + j, jumpsLeft' = jumpsLeft - 1,
    t' = t, wallL' = wallL, recSt' = recSt, createdAt' = createdAt, finishedAt' = finishedAt, cancel' = cancel, nextStep' = nextStep,
    cancelledSteps' = cancelledSteps, okSteps' = okSteps, openCall' = openCall, openSince' = openSince, obsCreateL' = obsCreateL, obsFinishR' = obsFinishR,
    cancelAge' = cancelAge, finishAge' = finishAge, reapAge' = reapAge, clockCancelledSteps' = clockCancelledSteps, tFinished' = tFinished }

  // time passes; capped so that no due action is skipped by more than a tick
  action advance(d: int): bool = all {
    not(runDue), not(finishDue), not(reapDue),
    not(openCall) or t + d <= openSince + OPS_STEP_WAIT,
    // the next deadline by the actor's wall clock is crossed by at most OPS_TICK
    recSt != "running" or cancel or
      (if (MONO) t + d <= obsCreateL + OPS_RUN_MAX + OPS_TICK else wallLeader + d <= createdAt + OPS_RUN_MAX + OPS_TICK),
    recSt != "done" or (if (MONO) t + d <= obsFinishR + OPS_KEEP + OPS_TICK else wallReaper + d <= finishedAt + OPS_KEEP + OPS_TICK),
    t' = t + d,
    wallL' = wallL, wallR' = wallR, recSt' = recSt, createdAt' = createdAt, finishedAt' = finishedAt,
    cancel' = cancel, nextStep' = nextStep, cancelledSteps' = cancelledSteps, okSteps' = okSteps, openCall' = openCall, openSince' = openSince,
    jumpsLeft' = jumpsLeft, obsCreateL' = obsCreateL, obsFinishR' = obsFinishR,
    cancelAge' = cancelAge, finishAge' = finishAge, reapAge' = reapAge, clockCancelledSteps' = clockCancelledSteps, tFinished' = tFinished,
  }

  action step = any {
    openStep, stepOk, stepTimeout, roundCancel, finish, finishComplete, reap,
    nondet d = oneOf(Set(OPS_TICK, OPS_STEP_WAIT, 60, OPS_RUN_MAX)) advance(d),
    nondet j = oneOf(JUMPS) any { jumpL(j), jumpR(j) },
  }

  // -- properties on completed actions (ghosts assigned inside the action)
  // A time-based cancel happens only at true age >= OPS_RUN_MAX.
  val cancelNotEarly = cancelAge < 0 or cancelAge >= OPS_RUN_MAX
  // The reaper removes a finished operation at true age >= OPS_KEEP since the finish.
  val reapNotEarly = reapAge < 0 or reapAge >= OPS_KEEP
  // 06.9:28: "neither a step nor a right depends on it": no step gets outcome cancel solely by a clock shift before true age OPS_RUN_MAX.
  val stepNotClockCancelled = clockCancelledSteps == 0
  // In-progress bound: a running operation does not outlive OPS_RUN_MAX in true time by more than the fair ticks allow.
  val runBounded = recSt != "running" or cancel or t <= BOUND

  // -- witnesses
  val w_cancel_by_time = not(cancelAge >= 0 and recSt == "done")
  val w_reap = not(recSt == "absent" and reapAge >= OPS_KEEP)
  val w_ok_step = not(okSteps == 1 and openCall == false)
  val w_early_cancel = not(cancelAge >= 0 and cancelAge < OPS_RUN_MAX)
  val w_steps_cancelled = not(clockCancelledSteps > 0)
  val w_late_cancel_age = not(cancelAge > OPS_RUN_MAX + OPS_TICK)
  val c_false = t < 0
}
