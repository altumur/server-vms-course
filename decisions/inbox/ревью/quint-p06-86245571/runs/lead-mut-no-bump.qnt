// -*- mode: Bluespec; -*-
// Operations leader handover, late step batches, unknown outcome of a step batch, SIGTERM (06.9:390-399, 06.9:313-327, 06.9:415-424, 06.9:440-451, life:92, turn:42-59).
// Anchors: 06.9:393 (epoch write under the turn), 06.9:399 (generation = epoch index), 06.9:318,320 (step batch: cas "" + generation guard),
//   06.9:321 (step_key memory), 06.9:423-424 (retry, OPS_STEP_TRIES, fail not_run), 06.9:440-451 (finish, late batch runs into cancel),
//   06.9:541 (ticket only in console memory), life:92 (SIGTERM gives up the turn), turn:98 (turn is no fence for external effects).
// Abstraction: one operation with one step, leaders L1, L2. The turn lease time is abstracted: `steal` is enabled at any time,
// an over-approximation of TURN_TERM expiry (safety here rests on cas/guard, not on lease timing; a paused leader is `steal`+late batch).
// SIGTERM is two-phase (give up the turn, then exit); the batch of a still-open call can land until exit. Batch delivered only while the
// issuing process is alive (06.9:541: the ticket is only in its memory; the worker calls back to it).
// NOT modelled: multiple steps/roots, the subsystem target rows, the worker's own external effect (turn.md production obligations),
// lease timing and take-over delay, exp/token paths.
module ops_leader {
  pure val OPS_STEP_TRIES = 3   // const:21
  pure val MAX_EVENTS = 8       // @override bound on adversarial events
  pure val MUT = "no_bump"  // @override none | no_gen_guard | no_outcome_cas | no_bump | finish_no_cancel_cas
  type Proc = str
  pure val PROCS = Set("L1", "L2")
  type St = {
    holder: str, turnVer: int, epoch: int,
    alive: Proc -> bool, draining: Proc -> bool,
    myTurn: Proc -> int, gen: Proc -> int, tries: Proc -> int, callGen: Proc -> int, ended: Proc -> bool,
    outcome: str, outcomeWrites: int, opSt: str, cancelFlag: bool,
    events: int, okLands: int, callsTotal: int,
    bumps: int, ticketBump: Proc -> int, staleLanded: bool, giveUps: int, pendingGiveUpBy: str, handedOver: bool,
  }
  var s: St

  action init = s' = {
    holder: "", turnVer: 0, epoch: 1,
    alive: PROCS.mapBy(p => true), draining: PROCS.mapBy(p => false),
    myTurn: PROCS.mapBy(p => 0), gen: PROCS.mapBy(p => 0), tries: PROCS.mapBy(p => 0), callGen: PROCS.mapBy(p => 0),
    ended: PROCS.mapBy(p => false),
    outcome: "none", outcomeWrites: 0, opSt: "running", cancelFlag: false,
    events: 0, okLands: 0, callsTotal: 0,
    bumps: 0, ticketBump: PROCS.mapBy(p => 0), staleLanded: false, giveUps: 0, pendingGiveUpBy: "", handedOver: false,
  }

  def live(p: Proc): bool = s.alive.get(p) and not(s.draining.get(p))

  // take a free turn by cas (turn:45): the attempt writes a new mark
  action take(p: Proc): bool = all {
    live(p), s.myTurn.get(p) == 0, s.holder == "",
    s' = {...s, holder: p, turnVer: s.turnVer + 1, myTurn: s.myTurn.set(p, s.turnVer + 1), gen: s.gen.set(p, 0), tries: s.tries.set(p, 0)},
  }

  // a new attempt takes a foreign turn after expiry; expiry is abstracted (over-approximation)
  action steal(p: Proc): bool = all {
    live(p), s.holder != "", s.holder != p, s.events < MAX_EVENTS,
    s' = {...s, holder: p, turnVer: s.turnVer + 1, myTurn: s.myTurn.set(p, s.turnVer + 1), gen: s.gen.set(p, 0), tries: s.tries.set(p, 0), events: s.events + 1},
  }

  // epoch write under the turn right after taking it (06.9:393)
  action bumpEpoch(p: Proc): bool = all {
    live(p), s.holder == p, s.myTurn.get(p) == s.turnVer, s.gen.get(p) == 0, s.opSt == "running",
    if (MUT == "no_bump") s' = {...s, gen: s.gen.set(p, s.epoch), bumps: s.bumps + 1}
    else s' = {...s, epoch: s.epoch + 1, gen: s.gen.set(p, s.epoch + 1), bumps: s.bumps + 1},
  }

  // step(operation) 06.9:415-424: read the outcome after the epoch write; none → a call with the same step_key
  action startCall(p: Proc): bool = all {
    live(p), s.holder == p, s.gen.get(p) != 0, s.callGen.get(p) == 0, s.opSt == "running", not(s.cancelFlag), s.outcome == "none",
    s' = {...s, callGen: s.callGen.set(p, s.gen.get(p)), callsTotal: s.callsTotal + 1, ticketBump: s.ticketBump.set(p, s.bumps)},
  }

  // the worker's batch reaches the live issuing console: generation guard + cas "" of the outcome; `lost` = landed, answer lost
  action workerBatch(p: Proc, lost: bool): bool = all {
    s.alive.get(p), s.callGen.get(p) != 0,
    val genOk = MUT == "no_gen_guard" or s.callGen.get(p) == s.epoch
    val casOk = MUT == "no_outcome_cas" or s.outcome == "none"
    if (genOk and casOk)
      s' = {...s, outcome: "ok", outcomeWrites: s.outcomeWrites + 1, okLands: s.okLands + 1,
                  callGen: s.callGen.set(p, 0), ended: s.ended.set(p, lost),
                  staleLanded: s.staleLanded or s.ticketBump.get(p) < s.bumps}
    else
      s' = {...s, callGen: s.callGen.set(p, 0), ended: s.ended.set(p, true)},
  }

  // the worker never answers: the ticket dies at OPS_STEP_WAIT, the call ends without a batch
  action workerSilent(p: Proc): bool = all {
    s.alive.get(p), s.callGen.get(p) != 0,
    s' = {...s, callGen: s.callGen.set(p, 0), ended: s.ended.set(p, true)},
  }

  // 06.9:422-424: the call ended without an outcome: failures in a row + 1 (leader memory)
  action countFailure(p: Proc): bool = all {
    live(p), s.holder == p, s.ended.get(p), s.callGen.get(p) == 0, s.opSt == "running", s.outcome == "none", s.tries.get(p) < OPS_STEP_TRIES,
    s' = {...s, tries: s.tries.set(p, s.tries.get(p) + 1), ended: s.ended.set(p, false)},
  }

  // fail not_run under the turn guard, cas "" (06.9:424)
  action failNotRun(p: Proc): bool = all {
    live(p), s.holder == p, s.myTurn.get(p) == s.turnVer, s.callGen.get(p) == 0, s.tries.get(p) >= OPS_STEP_TRIES, s.opSt == "running",
    if (s.outcome == "none" or MUT == "no_outcome_cas")
      s' = {...s, outcome: "fail", outcomeWrites: s.outcomeWrites + 1}
    else s' = s,
  }

  action setCancel: bool = all {
    not(s.cancelFlag), s.opSt == "running", s.events < MAX_EVENTS,
    s' = {...s, cancelFlag: true, events: s.events + 1},
  }

  // finish (06.9:440): no open call of this console; `cancel` outcome cas "" on the step without an outcome
  action finish(p: Proc): bool = all {
    live(p), s.holder == p, s.myTurn.get(p) == s.turnVer, s.callGen.get(p) == 0, s.opSt == "running",
    s.cancelFlag or s.outcome != "none",
    val over = s.pendingGiveUpBy != "" and p != s.pendingGiveUpBy
    if (s.outcome == "none" or MUT == "finish_no_cancel_cas")
      s' = {...s, outcome: "cancel", outcomeWrites: s.outcomeWrites + 1, opSt: "done", handedOver: s.handedOver or over}
    else
      s' = {...s, opSt: "done", handedOver: s.handedOver or over},
  }

  // SIGTERM phase 1: give up the turn by cas of my version (life:92, turn step 6, 06.9:397); the process may still drain open calls
  action sigtermGiveUp(p: Proc): bool = all {
    s.alive.get(p), not(s.draining.get(p)), s.events < MAX_EVENTS,
    s' = {...s,
      holder: if (s.holder == p and s.myTurn.get(p) == s.turnVer) "" else s.holder,
      turnVer: if (s.holder == p and s.myTurn.get(p) == s.turnVer) s.turnVer + 1 else s.turnVer,
      draining: s.draining.set(p, true), myTurn: s.myTurn.set(p, 0), gen: s.gen.set(p, 0),
      giveUps: if (s.holder == p and s.myTurn.get(p) == s.turnVer) s.giveUps + 1 else s.giveUps,
      pendingGiveUpBy: if (s.holder == p and s.myTurn.get(p) == s.turnVer and s.opSt == "running" and s.outcome == "none") p else s.pendingGiveUpBy,
      events: s.events + 1},
  }

  // the process exits: tickets die with it (06.9:541)
  action exitProc(p: Proc): bool = all {
    s.alive.get(p), s.draining.get(p),
    s' = {...s, alive: s.alive.set(p, false), draining: s.draining.set(p, false), callGen: s.callGen.set(p, 0), ended: s.ended.set(p, false)},
  }

  // a crash: no give-up, the row stays until a steal
  action crash(p: Proc): bool = all {
    s.alive.get(p), s.events < MAX_EVENTS,
    s' = {...s, alive: s.alive.set(p, false), draining: s.draining.set(p, false), callGen: s.callGen.set(p, 0), myTurn: s.myTurn.set(p, 0), gen: s.gen.set(p, 0), ended: s.ended.set(p, false), events: s.events + 1},
  }

  // a fresh process with no memory (06.9:509)
  action restart(p: Proc): bool = all {
    not(s.alive.get(p)), s.events < MAX_EVENTS,
    s' = {...s, alive: s.alive.set(p, true), tries: s.tries.set(p, 0), events: s.events + 1},
  }

  action idle = s' = s

  action step = any {
    idle,
    nondet p = oneOf(PROCS) any {
      take(p), steal(p), bumpEpoch(p), startCall(p), countFailure(p), failNotRun(p), finish(p),
      nondet l = oneOf(Set(true, false)) workerBatch(p, l),
      workerSilent(p), sigtermGiveUp(p), exitProc(p), crash(p), restart(p),
    },
    setCancel,
  }

  // -- properties (on the store row)
  val outcomeOnce = s.outcomeWrites <= 1
  val okOnce = s.okLands <= 1
  val doneHasOutcome = s.opSt != "done" or s.outcome != "none"
  // an ok outcome never appears unless a batch landed exactly once
  val outcomeOkIsBatch = s.outcome != "ok" or s.okLands == 1
  val allSafe = and { outcomeOnce, okOnce, doneHasOutcome, outcomeOkIsBatch }
  // 06.9:320,399,508: a batch of a ticket issued before the latest epoch rewrite does not land (a completed landing, by the ghost)
  val noStaleLanding = not(s.staleLanded)

  // -- witnesses
  val w_done_ok = not(s.outcome == "ok" and s.opSt == "done")
  // a leader that held the turn got SIGTERM (give-up happened), another leader then finished the same step with a second call
  // handedOver: the turn holder got SIGTERM while the step had no outcome (give-up), and a different leader finished the operation
  val w_after_sigterm_handover = not(s.handedOver and s.outcome == "ok" and s.callsTotal >= 2)
  val w_sigterm_then_done = not(s.handedOver)
  val w_two_calls = not(s.callsTotal >= 2 and s.outcome == "ok")
  val w_cancel = not(s.outcome == "cancel" and s.cancelFlag)
  val w_fail = not(s.outcome == "fail")
  val w_handover_gen = not(s.epoch >= 3 and s.opSt == "done")
  val c_false = s.turnVer < 0
}
