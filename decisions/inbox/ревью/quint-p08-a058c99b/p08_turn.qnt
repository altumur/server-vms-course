// -*- mode: Bluespec; -*-
// P/08 model unit: the process turn domain/signer-turn, guarded writes, unknown outcome and barrier,
// object writes without guard, SIGTERM and accepted work, the local restore section (C4, C15, C18).
// Anchors (norm text at pin a058c99b): 08.10:83-120 (turn, release, guard, objects, window), 08.10:205-215 (steps,
// barrier), common/contracts/turn.md:80-86 (barrier), 08.8:385 (target restore exclusion), 08.8:481-484 (objects of the copy
// «by value»). NOT modelled: real time (TURN_TERM/TURN_RENEW are abstracted: a takeover of a foreign live-looking row is
// always allowed, turn.md:98 — a paused old holder can resume), store outage as a whole (see p08_accept), multiple rows,
// journal, cryptography, HTTP. Bound: 2 processes A,B; one row; one object.
module p08_turn {
  // switches (mutants/controls), defaults set in the instance modules at the bottom
  const BARRIER_BUMPS: bool     // N: the barrier CAS changes the version (turn.md:81). mutant: false
  const BLIND_RESUME: bool      // mutant true: after an unknown outcome the process goes on without the barrier
  const GET_AFTER_CONFIRM: bool // mutant true: get_at after the confirming CAS (the order forbidden by 08.10:101)
  const DRAIN: bool             // control true: accepted work finished before release (not in P/08; prod:9 only)
  const RESTORE_PUT_AT: bool    // control true: restore object write conditional on the turn (not in the text)
  const GUARD_OFF: bool         // mutant true: guarded write not checked against the turn row

  pure val PROCS = Set("A", "B")
  type Msg = { id: int, p: str, guard: int, st: str } // st: sent | applied | refused
  var turnHolder: str
  var turnVer: int
  var role: str -> str        // active | standby | gone
  var myVer: str -> int
  var net: Set[Msg]           // the store's input: guarded writes
  var waiting: str -> int     // id of the awaited write, 0 none
  var needBarrier: str -> bool
  var seq: int                // the event counter, the only clock (order, not time)
  // object without pointer row: get_at/CAS/put_at
  var objIdx: int
  var objWriterVer: int
  var phase: str -> str       // none | got | confirmed
  var gotIdx: str -> int
  var confVer: str -> int
  // accepted work
  var accepted: str -> bool
  // restore section (local to a process) and the restored object written «by value»
  var restore: str -> bool
  var restObjVer: int   // ver of the last restore object write
  // history for the properties
  var badGuard: bool
  var lateApply: bool       // old write applied after the sender's barrier
  var reordered: bool       // write applied after a later write of the same process
  var overwrite: bool       // a put_at of a deposed process went over a write of a new active one
  var droppedAccepted: bool // accepted work without an outcome at exit
  var staleRestoreObj: bool // a late restore object write over a newer restore's write
  var maxApplied: str -> int
  // order stamps for the witnesses (0 = not yet)
  var tUnknown: int
  var tBarrier: int
  var tLateRefused: int
  var gotAt: str -> int
  var confAt: str -> int
  var takeAt: str -> int
  var putAt: str -> int
  var conflictAt: str -> int
  var confFailAt: str -> int
  var tSigterm: int
  var tRefusedAfterStop: int
  var tOverlap: int

  action init = all {
    turnHolder' = "", turnVer' = 0,
    role' = Map("A" -> "standby", "B" -> "standby"),
    myVer' = Map("A" -> 0, "B" -> 0),
    net' = Set(),
    waiting' = Map("A" -> 0, "B" -> 0),
    needBarrier' = Map("A" -> false, "B" -> false),
    seq' = 1,
    objIdx' = 0, objWriterVer' = 0,
    phase' = Map("A" -> "none", "B" -> "none"),
    gotIdx' = Map("A" -> 0, "B" -> 0),
    confVer' = Map("A" -> 0, "B" -> 0),
    accepted' = Map("A" -> false, "B" -> false),
    restore' = Map("A" -> false, "B" -> false),
    restObjVer' = 0,
    badGuard' = false, lateApply' = false, reordered' = false, overwrite' = false,
    droppedAccepted' = false, staleRestoreObj' = false,
    maxApplied' = Map("A" -> 0, "B" -> 0),
    tUnknown' = 0, tBarrier' = 0, tLateRefused' = 0, gotAt' = Map("A" -> 0, "B" -> 0), confAt' = Map("A" -> 0, "B" -> 0), takeAt' = Map("A" -> 0, "B" -> 0), putAt' = Map("A" -> 0, "B" -> 0), conflictAt' = Map("A" -> 0, "B" -> 0), confFailAt' = Map("A" -> 0, "B" -> 0),
    tSigterm' = 0, tRefusedAfterStop' = 0, tOverlap' = 0,
  }

  action unchanged_hist = all {
    badGuard' = badGuard, lateApply' = lateApply, reordered' = reordered, overwrite' = overwrite,
    droppedAccepted' = droppedAccepted, staleRestoreObj' = staleRestoreObj,
    maxApplied' = maxApplied,
  }
  action unchanged_stamps = all {
    tUnknown' = tUnknown, tBarrier' = tBarrier, tLateRefused' = tLateRefused, gotAt' = gotAt, confAt' = confAt, takeAt' = takeAt, putAt' = putAt, conflictAt' = conflictAt, confFailAt' = confFailAt, tSigterm' = tSigterm, tRefusedAfterStop' = tRefusedAfterStop,
    tOverlap' = tOverlap,
  }
  action hold_obj = all { objIdx' = objIdx, objWriterVer' = objWriterVer, phase' = phase, gotIdx' = gotIdx, confVer' = confVer }

  // take: free row or a foreign row whose holder looks stale (time abstracted away)
  action take(p: str): bool = all {
    role.get(p) == "standby", turnHolder != p,
    turnHolder' = p, turnVer' = turnVer + 1,
    role' = role.set(p, "active"),
    myVer' = myVer.set(p, turnVer + 1),
    needBarrier' = needBarrier.set(p, false),
    net' = net, waiting' = waiting.set(p, 0), accepted' = accepted, restore' = restore, restObjVer' = restObjVer,
    seq' = seq + 1,
    objIdx' = objIdx, objWriterVer' = objWriterVer, phase' = phase.set(p, "none"), gotIdx' = gotIdx, confVer' = confVer,
    unchanged_hist,
    tUnknown' = tUnknown, tBarrier' = tBarrier, tLateRefused' = tLateRefused,
    takeAt' = takeAt.set(p, seq), gotAt' = gotAt, confAt' = confAt, putAt' = putAt, conflictAt' = conflictAt, confFailAt' = confFailAt, tSigterm' = tSigterm, tRefusedAfterStop' = tRefusedAfterStop, tOverlap' = tOverlap,
  }

  // CAS of one's own row, including the barrier when needBarrier (08.10:202, 08.10:210-213)
  action confirm(p: str): bool = all {
    role.get(p) == "active",
    if (turnHolder == p and myVer.get(p) == turnVer) {
      val nv = if (needBarrier.get(p) and not(BARRIER_BUMPS)) turnVer else turnVer + 1
      all {
        turnVer' = nv, myVer' = myVer.set(p, nv), role' = role,
        needBarrier' = needBarrier.set(p, false),
        turnHolder' = turnHolder,
        tBarrier' = if (needBarrier.get(p)) seq else tBarrier,
      }
    } else all {
      // lost: a foreign holder or a version we did not write -> standby (08.10:203)
      turnVer' = turnVer, myVer' = myVer, turnHolder' = turnHolder,
      role' = role.set(p, "standby"),
      needBarrier' = needBarrier.set(p, false),
      tBarrier' = tBarrier,
    },
    net' = net, waiting' = waiting, accepted' = accepted, restore' = restore, restObjVer' = restObjVer,
    seq' = seq + 1, hold_obj, unchanged_hist,
    tUnknown' = tUnknown, tLateRefused' = tLateRefused, gotAt' = gotAt, confAt' = confAt, takeAt' = takeAt, putAt' = putAt, conflictAt' = conflictAt, confFailAt' = confFailAt,
    tSigterm' = tSigterm, tRefusedAfterStop' = tRefusedAfterStop, tOverlap' = tOverlap,
  }

  action startWrite(p: str): bool = all {
    role.get(p) == "active", waiting.get(p) == 0,
    or { BLIND_RESUME, not(needBarrier.get(p)) },
    size(net) < 4,
    net' = net.union(Set({ id: seq, p: p, guard: myVer.get(p), st: "sent" })),
    waiting' = waiting.set(p, seq),
    accepted' = accepted.set(p, true),
    turnHolder' = turnHolder, turnVer' = turnVer, role' = role, myVer' = myVer, needBarrier' = needBarrier,
    restore' = restore, restObjVer' = restObjVer,
    seq' = seq + 1, hold_obj, unchanged_hist, unchanged_stamps,
  }

  // the store processes a message (the guard is checked by the store, independently of the sender's knowledge)
  action apply(m: Msg): bool = all {
    m.st == "sent",
    val ok = or { GUARD_OFF, m.guard == turnVer }
    val staleBarrier = tBarrier > 0 and m.id < tBarrier
    val laterApplied = maxApplied.get(m.p) > m.id
    all {
      net' = net.exclude(Set(m)).union(Set({ ...m, st: if (ok) "applied" else "refused" })),
      badGuard' = (badGuard or (ok and m.guard != turnVer)),
      lateApply' = (lateApply or (ok and staleBarrier and tBarrier > 0)),
      reordered' = (reordered or (ok and laterApplied)),
      maxApplied' = if (ok and m.id > maxApplied.get(m.p)) maxApplied.set(m.p, m.id) else maxApplied,
      overwrite' = overwrite, droppedAccepted' = droppedAccepted, staleRestoreObj' = staleRestoreObj,
      tRefusedAfterStop' = if (not(ok) and tSigterm > 0 and m.id < tSigterm and role.get(m.p) == "gone") seq else tRefusedAfterStop,
      tLateRefused' = if (not(ok) and tBarrier > 0 and m.id < tBarrier) seq else tLateRefused,
    },
    turnHolder' = turnHolder, turnVer' = turnVer, role' = role, myVer' = myVer, needBarrier' = needBarrier,
    waiting' = waiting, accepted' = accepted, restore' = restore, restObjVer' = restObjVer, seq' = seq + 1, hold_obj,
    tUnknown' = tUnknown, tBarrier' = tBarrier, gotAt' = gotAt, confAt' = confAt, takeAt' = takeAt, putAt' = putAt, conflictAt' = conflictAt, confFailAt' = confFailAt,
    tSigterm' = tSigterm, tOverlap' = tOverlap,
  }

  // the process learns the outcome of its awaited write
  action answer(p: str, m: Msg): bool = all {
    waiting.get(p) == m.id, m.p == p, m.st != "sent", role.get(p) != "gone",
    waiting' = waiting.set(p, 0),
    accepted' = accepted.set(p, false),
    role' = if (m.st == "refused") role.set(p, "standby") else role,
    needBarrier' = needBarrier,
    net' = net.exclude(Set(m)),
    turnHolder' = turnHolder, turnVer' = turnVer, myVer' = myVer, restore' = restore, restObjVer' = restObjVer,
    seq' = seq + 1, hold_obj, unchanged_hist, unchanged_stamps,
  }

  // the answer is lost; the message may stay in flight (unknown outcome, 08.10:210)
  action lose(p: str): bool = all {
    waiting.get(p) != 0, role.get(p) == "active",
    waiting' = waiting.set(p, 0),
    accepted' = accepted.set(p, false),
    needBarrier' = needBarrier.set(p, true),
    net' = net,
    turnHolder' = turnHolder, turnVer' = turnVer, role' = role, myVer' = myVer, restore' = restore, restObjVer' = restObjVer,
    seq' = seq + 1, hold_obj, unchanged_hist,
    tUnknown' = seq, tBarrier' = tBarrier, tLateRefused' = tLateRefused, gotAt' = gotAt, confAt' = confAt, takeAt' = takeAt, putAt' = putAt, conflictAt' = conflictAt, confFailAt' = confFailAt,
    tSigterm' = tSigterm, tRefusedAfterStop' = tRefusedAfterStop, tOverlap' = tOverlap,
  }

  // an in-memory object write: get_at -> own confirming CAS -> put_at by the index read before the CAS (08.10:98-102)
  action objGet(p: str): bool = all {
    role.get(p) == "active", phase.get(p) == "none", not(needBarrier.get(p)),
    or { not(GET_AFTER_CONFIRM), confVer.get(p) == myVer.get(p) and confVer.get(p) > 0 },
    gotIdx' = gotIdx.set(p, objIdx),
    phase' = phase.set(p, if (GET_AFTER_CONFIRM) "confirmed" else "got"),
    objIdx' = objIdx, objWriterVer' = objWriterVer, confVer' = confVer,
    turnHolder' = turnHolder, turnVer' = turnVer, role' = role, myVer' = myVer, needBarrier' = needBarrier, net' = net,
    waiting' = waiting, accepted' = accepted, restore' = restore, restObjVer' = restObjVer, seq' = seq + 1, unchanged_hist,
    tUnknown' = tUnknown, tBarrier' = tBarrier, tLateRefused' = tLateRefused, gotAt' = gotAt.set(p, seq), confAt' = confAt, takeAt' = takeAt, putAt' = putAt, conflictAt' = conflictAt, confFailAt' = confFailAt,
    tSigterm' = tSigterm, tRefusedAfterStop' = tRefusedAfterStop, tOverlap' = tOverlap,
  }

  action objConfirm(p: str): bool = all {
    role.get(p) == "active", 
    if (GET_AFTER_CONFIRM) phase.get(p) == "none" else phase.get(p) == "got",
    if (turnHolder == p and myVer.get(p) == turnVer) all {
      turnVer' = turnVer + 1, myVer' = myVer.set(p, turnVer + 1), role' = role,
      confVer' = confVer.set(p, turnVer + 1),
      phase' = if (GET_AFTER_CONFIRM) phase.set(p, "none") else phase.set(p, "confirmed"),
      confAt' = confAt.set(p, seq), confFailAt' = confFailAt,
    } else all {
      turnVer' = turnVer, myVer' = myVer, role' = role.set(p, "standby"), confVer' = confVer, phase' = phase.set(p, "none"),
      confAt' = confAt, confFailAt' = confFailAt.set(p, seq),
    },
    gotIdx' = gotIdx, objIdx' = objIdx, objWriterVer' = objWriterVer,
    turnHolder' = turnHolder, needBarrier' = needBarrier, net' = net, waiting' = waiting, accepted' = accepted,
    restore' = restore, restObjVer' = restObjVer, seq' = seq + 1, unchanged_hist,
    tUnknown' = tUnknown, tBarrier' = tBarrier, tLateRefused' = tLateRefused, gotAt' = gotAt, takeAt' = takeAt, putAt' = putAt, conflictAt' = conflictAt,
    tSigterm' = tSigterm, tRefusedAfterStop' = tRefusedAfterStop, tOverlap' = tOverlap,
  }

  // put_at: conditional on the index read before the confirmation; a deposed process may still reach this step
  action objPut(p: str): bool = all {
    phase.get(p) == "confirmed",
    if (gotIdx.get(p) == objIdx) all {
      objIdx' = objIdx + 1, objWriterVer' = confVer.get(p),
      overwrite' = (overwrite or objWriterVer > confVer.get(p)),
      phase' = phase.set(p, "none"),
      putAt' = putAt.set(p, seq), conflictAt' = conflictAt,
    } else all {
      objIdx' = objIdx, objWriterVer' = objWriterVer, overwrite' = overwrite,
      phase' = phase.set(p, "none"),
      putAt' = putAt, conflictAt' = conflictAt.set(p, seq),
    },
    gotIdx' = gotIdx, confVer' = confVer,
    turnHolder' = turnHolder, turnVer' = turnVer, role' = role, myVer' = myVer, needBarrier' = needBarrier, net' = net,
    waiting' = waiting, accepted' = accepted, restore' = restore, restObjVer' = restObjVer, seq' = seq + 1,
    badGuard' = badGuard, lateApply' = lateApply, reordered' = reordered, droppedAccepted' = droppedAccepted,
    staleRestoreObj' = staleRestoreObj, maxApplied' = maxApplied,
    tUnknown' = tUnknown, tBarrier' = tBarrier, tLateRefused' = tLateRefused, gotAt' = gotAt, confAt' = confAt, takeAt' = takeAt, confFailAt' = confFailAt,
    tSigterm' = tSigterm, tRefusedAfterStop' = tRefusedAfterStop, tOverlap' = tOverlap,
  }

  // SIGTERM at the active process: holder "" by CAS of its own version, then exit (08.10:208). In-flight messages stay.
  action sigterm(p: str): bool = all {
    role.get(p) == "active", turnHolder == p, myVer.get(p) == turnVer,
    or { not(DRAIN), not(accepted.get(p)) },
    turnHolder' = "", turnVer' = turnVer + 1,
    role' = role.set(p, "gone"),
    droppedAccepted' = (droppedAccepted or accepted.get(p)),
    myVer' = myVer, needBarrier' = needBarrier, net' = net, waiting' = waiting.set(p, 0), accepted' = accepted.set(p, false),
    restore' = restore.set(p, false), restObjVer' = restObjVer, seq' = seq + 1, hold_obj,
    badGuard' = badGuard, lateApply' = lateApply, reordered' = reordered, overwrite' = overwrite,
    staleRestoreObj' = staleRestoreObj, maxApplied' = maxApplied,
    tUnknown' = tUnknown, tBarrier' = tBarrier, tLateRefused' = tLateRefused, gotAt' = gotAt, confAt' = confAt, takeAt' = takeAt, putAt' = putAt, conflictAt' = conflictAt, confFailAt' = confFailAt,
    tSigterm' = seq, tRefusedAfterStop' = tRefusedAfterStop, tOverlap' = tOverlap,
  }

  // restore: local section entered by an active process; two processes may be inside at once (the section is per process)
  action restoreStart(p: str): bool = all {
    role.get(p) == "active", not(restore.get(p)),
    restore' = restore.set(p, true),
    tOverlap' = if (restore.get(if (p == "A") "B" else "A")) seq else tOverlap,
    turnHolder' = turnHolder, turnVer' = turnVer, role' = role, myVer' = myVer, needBarrier' = needBarrier, net' = net,
    waiting' = waiting, accepted' = accepted, restObjVer' = restObjVer, seq' = seq + 1, hold_obj, unchanged_hist,
    tUnknown' = tUnknown, tBarrier' = tBarrier, tLateRefused' = tLateRefused, gotAt' = gotAt, confAt' = confAt, takeAt' = takeAt, putAt' = putAt, conflictAt' = conflictAt, confFailAt' = confFailAt,
    tSigterm' = tSigterm, tRefusedAfterStop' = tRefusedAfterStop,
  }

  // a restore object write «by value» (08.8:484): not conditional on the turn; the handler lives on after the turn is lost
  // RESTORE_PUT_AT control: allowed only by the current holder
  action restoreObj(p: str): bool = all {
    restore.get(p), role.get(p) != "gone",
    or { not(RESTORE_PUT_AT), turnHolder == p },
    restObjVer' = myVer.get(p),
    staleRestoreObj' = (staleRestoreObj or restObjVer > myVer.get(p)),
    badGuard' = badGuard, lateApply' = lateApply, reordered' = reordered, overwrite' = overwrite,
    droppedAccepted' = droppedAccepted, maxApplied' = maxApplied,
    turnHolder' = turnHolder, turnVer' = turnVer, role' = role, myVer' = myVer, needBarrier' = needBarrier, net' = net,
    waiting' = waiting, accepted' = accepted, restore' = restore, seq' = seq + 1, hold_obj, unchanged_stamps,
  }

  action step = any {
    nondet p = oneOf(PROCS)
    any {
      take(p), confirm(p), startWrite(p), lose(p), objGet(p), objConfirm(p), objPut(p), sigterm(p),
      restoreStart(p), restoreObj(p),
      nondet m = oneOf(if (net == Set()) Set({ id: 0, p: "A", guard: 0, st: "x" }) else net)
      any { apply(m), answer(p, m) },
    },
    // stutter so that bounded traces exist with idle tails
    all {
      turnHolder' = turnHolder, turnVer' = turnVer, role' = role, myVer' = myVer, net' = net, waiting' = waiting,
      needBarrier' = needBarrier, seq' = seq, accepted' = accepted, restore' = restore, restObjVer' = restObjVer,
      hold_obj, unchanged_hist, unchanged_stamps,
    },
  }

  // properties (safety, invariants)
  val inv_guard = not(badGuard)                     // the guard protects guarded rows
  val inv_no_late_apply = not(lateApply)            // after the barrier an old write cannot land (turn.md:83)
  val inv_no_reorder = not(reordered)               // writes of one process do not land out of order
  val inv_no_overwrite = not(overwrite)             // a deposed put_at does not overwrite the new active one (08.10:99-102)
  val inv_no_drop = not(droppedAccepted)            // no accepted work without an outcome at SIGTERM
  val inv_no_stale_restore_obj = not(staleRestoreObj)

  // witnesses: order of events, not just a flag (each is a NEGATED invariant -> a counterexample = the witness trace)
  val wit_unknown_barrier_refuse = not(tUnknown > 0 and tBarrier > tUnknown and tLateRefused > tBarrier)
  val wit_barrier_only = not(tUnknown > 0 and tBarrier > tUnknown)
  // G6, the branch «after our confirmation»: p got the index and confirmed, q took the turn and wrote the object, p's put_at conflicts
  val wit_takeover_conflict = not(tuples(PROCS, PROCS).exists(pq => pq._1 != pq._2 and
    gotAt.get(pq._1) > 0 and confAt.get(pq._1) > gotAt.get(pq._1) and
    takeAt.get(pq._2) > confAt.get(pq._1) and putAt.get(pq._2) > takeAt.get(pq._2) and conflictAt.get(pq._1) > putAt.get(pq._2)))
  // G6, the branch «before our confirmation»: p got the index, q took the turn, p's confirmation does not pass
  val wit_takeover_confirm_fails = not(tuples(PROCS, PROCS).exists(pq => pq._1 != pq._2 and
    gotAt.get(pq._1) > 0 and takeAt.get(pq._2) > gotAt.get(pq._1) and confFailAt.get(pq._1) > takeAt.get(pq._2)))
  val wit_sigterm_inflight_refused = not(tSigterm > 0 and tRefusedAfterStop > tSigterm)
  val wit_restore_overlap = not(tOverlap > 0)
  val wit_applied_write = not(net.exists(m => m.st == "applied"))
}

// instances: norm text and variants
module turn_norm {
  import p08_turn(BARRIER_BUMPS = true, BLIND_RESUME = false, GET_AFTER_CONFIRM = false, DRAIN = false, RESTORE_PUT_AT = false, GUARD_OFF = false).*
}
// mutants
module turn_m_nobump { import p08_turn(BARRIER_BUMPS = false, BLIND_RESUME = false, GET_AFTER_CONFIRM = false, DRAIN = false, RESTORE_PUT_AT = false, GUARD_OFF = false).* }
module turn_m_blind { import p08_turn(BARRIER_BUMPS = true, BLIND_RESUME = true, GET_AFTER_CONFIRM = false, DRAIN = false, RESTORE_PUT_AT = false, GUARD_OFF = false).* }
module turn_m_get_after { import p08_turn(BARRIER_BUMPS = true, BLIND_RESUME = false, GET_AFTER_CONFIRM = true, DRAIN = false, RESTORE_PUT_AT = false, GUARD_OFF = false).* }
module turn_m_noguard { import p08_turn(BARRIER_BUMPS = true, BLIND_RESUME = false, GET_AFTER_CONFIRM = false, DRAIN = false, RESTORE_PUT_AT = false, GUARD_OFF = true).* }
// controls: what would close the gap (not norms of P/08 at the pin)
module turn_c_drain { import p08_turn(BARRIER_BUMPS = true, BLIND_RESUME = false, GET_AFTER_CONFIRM = false, DRAIN = true, RESTORE_PUT_AT = false, GUARD_OFF = false).* }
module turn_c_restore { import p08_turn(BARRIER_BUMPS = true, BLIND_RESUME = false, GET_AFTER_CONFIRM = false, DRAIN = false, RESTORE_PUT_AT = true, GUARD_OFF = false).* }
