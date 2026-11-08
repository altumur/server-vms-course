// -*- mode: Bluespec; -*-
// Claim of POST (create) under an idempotency key: intent, target write, continuation.
// Anchors: 06.1:713, 06.1:717, 06.1:719, 06.1:760-763, 06.1:767, 06.1:770-772, 06.1:775-778 (ownership), const:32.
// Abstraction: one key K (processes A,B), one named row, one foreign creator C with another key.
// NOT modelled: numeric ids and next_id, tombstones (intended rev is 1), references, refusals of form, the 409/422 answers to the repeat.
module claim_post {
  pure val T_TAKEOVER = 30   // const:32 CLAIM_TAKEOVER_AFTER
  pure val FOREIGN_MAX = 1   // @override
  pure val MUT = "rev_only"  // @override none | no_intent | fresh_born | rev_only | no_guard | no_proof
  type Proc = str
  pure val PROCS = Set("A", "B")

  var rowOn: bool
  var rowBorn: int           // born of the row (random, unique per attempt); 0 = none
  var rowBy: str             // base | K | C
  var clSt: str              // none | pending | done
  var clVer: int
  var clBorn: int            // saved intended born; 0 = none
  var clAns: str             // none | 201 | 409
  var nextBorn: int          // generator of fresh random `born` values
  var phase: Proc -> str
  var myVer: Proc -> int
  var sawVer: Proc -> int
  var sawAt: Proc -> int
  var plan: Proc -> int      // born of this attempt
  var now: int
  // ghosts
  var landCount: int
  var keyLanded: bool
  var foreignCount: int
  var false409: bool
  var falseSuccess: bool
  var contDone: bool
  var crashed: bool

  action init = all {
    rowOn' = false, rowBorn' = 0, rowBy' = "",
    clSt' = "none", clVer' = 0, clBorn' = 0, clAns' = "none", nextBorn' = 1,
    phase' = PROCS.mapBy(p => "Idle"), myVer' = PROCS.mapBy(p => 0),
    sawVer' = PROCS.mapBy(p => -1), sawAt' = PROCS.mapBy(p => 0),
    plan' = PROCS.mapBy(p => 0), now' = 0,
    landCount' = 0, keyLanded' = false, foreignCount' = 0, false409' = false, falseSuccess' = false, contDone' = false, crashed' = false,
  }

  action uRow = all { rowOn' = rowOn, rowBorn' = rowBorn, rowBy' = rowBy }
  action uClaim = all { clSt' = clSt, clVer' = clVer, clBorn' = clBorn, clAns' = clAns }
  action uG = all { landCount' = landCount, keyLanded' = keyLanded, foreignCount' = foreignCount, false409' = false409, falseSuccess' = falseSuccess, contDone' = contDone, crashed' = crashed }
  action uProc = all { phase' = phase, myVer' = myVer, sawVer' = sawVer, sawAt' = sawAt, plan' = plan }

  // create step 2: claim `cas ""`
  action startClaim(p: Proc): bool = all {
    phase.get(p) == "Idle", clSt == "none",
    clSt' = "pending", clVer' = clVer + 1, clBorn' = 0, clAns' = clAns,
    phase' = phase.set(p, "Claimed"), myVer' = myVer.set(p, clVer + 1),
    sawVer' = sawVer, sawAt' = sawAt, plan' = plan, nextBorn' = nextBorn, now' = now, uRow, uG,
  }

  // ordinary step 5: row live → 409 exists (a live row with no continuation proof) (06.1:754)
  action checkExists(p: Proc): bool = all {
    phase.get(p) == "Claimed",
    if (rowOn) all {
      phase' = phase.set(p, "Conflict"), myVer' = myVer, uRow, uClaim,
      sawVer' = sawVer, sawAt' = sawAt, plan' = plan, nextBorn' = nextBorn, now' = now, uG,
    } else all {
      phase' = phase.set(p, "Ready"), myVer' = myVer, uRow, uClaim,
      sawVer' = sawVer, sawAt' = sawAt, plan' = plan, nextBorn' = nextBorn, now' = now, uG,
    }
  }

  // step 8: the plan of this attempt saved into pending before the target write (06.1:760-763)
  // A plan already in the claim is reused (06.1:763), a fresh born only if there is none.
  action saveIntent(p: Proc): bool = all {
    phase.get(p) == "Ready",
    val born = if (clBorn != 0 and MUT != "fresh_born") clBorn else nextBorn
    if (MUT == "no_intent") all {
      phase' = phase.set(p, "Intended"), myVer' = myVer, plan' = plan.set(p, born), nextBorn' = nextBorn + 1, uClaim,
      sawVer' = sawVer, sawAt' = sawAt, now' = now, uRow, uG,
    } else if (clVer == myVer.get(p) and clSt == "pending") all {
      clVer' = clVer + 1, clSt' = clSt, clBorn' = born, clAns' = clAns,
      phase' = phase.set(p, "Intended"), myVer' = myVer.set(p, clVer + 1), plan' = plan.set(p, born),
      nextBorn' = nextBorn + 1,
      sawVer' = sawVer, sawAt' = sawAt, now' = now, uRow, uG,
    } else all {
      phase' = phase.set(p, "Stop"), myVer' = myVer, plan' = plan, nextBorn' = nextBorn, uClaim,
      sawVer' = sawVer, sawAt' = sawAt, now' = now, uRow, uG,
    }
  }

  // step 8: write the row `cas ""` with the guard of my claim version (06.1:764-765)
  action targetWrite(p: Proc, outcome: str): bool = all {
    phase.get(p) == "Intended",
    val guardOk = MUT == "no_guard" or (clVer == myVer.get(p) and clSt == "pending")
    val land = guardOk and not(rowOn) and outcome != "unknown_not"
    all {
      if (land) all {
        rowOn' = true, rowBorn' = plan.get(p), rowBy' = "K", landCount' = landCount + 1, keyLanded' = true,
      } else all { uRow, landCount' = landCount, keyLanded' = keyLanded },
      phase' = phase.set(p,
        if (outcome == "unknown_landed" or outcome == "unknown_not") "Unknown"
        else if (land) "Landed"
        else if (not(guardOk)) "Stop"
        else "Conflict"),
      myVer' = myVer, plan' = plan, sawVer' = sawVer, sawAt' = sawAt, nextBorn' = nextBorn, now' = now,
      uClaim,
      foreignCount' = foreignCount, false409' = false409, falseSuccess' = falseSuccess, contDone' = contDone, crashed' = crashed,
    }
  }

  // 06.1:766-768: conflict of the target write: re-read; intent matches → 201 else 409 exists
  action afterConflict(p: Proc): bool = all {
    phase.get(p) == "Conflict",
    val proof = MUT != "no_proof" and rowOn and clBorn != 0 and rowBorn == clBorn
    all {
      phase' = phase.set(p, if (proof) "Confirmed" else "Exists409"),
      myVer' = myVer, plan' = plan, sawVer' = sawVer, sawAt' = sawAt, nextBorn' = nextBorn, now' = now,
      uRow, uClaim, uG,
    }
  }

  action rememberDone(p: Proc): bool = all {
    phase.get(p) == "Landed" or phase.get(p) == "Confirmed" or phase.get(p) == "Exists409",
    if (clVer == myVer.get(p) and clSt == "pending") all {
      clSt' = "done", clVer' = clVer + 1, clBorn' = clBorn,
      clAns' = if (phase.get(p) == "Exists409") "409" else "201",
      phase' = phase.set(p, "Answered"), myVer' = myVer,
      falseSuccess' = (falseSuccess or (phase.get(p) != "Exists409" and not(keyLanded))),
      false409' = (false409 or (phase.get(p) == "Exists409" and keyLanded)),
      contDone' = (contDone or phase.get(p) == "Confirmed"),
      landCount' = landCount, keyLanded' = keyLanded, foreignCount' = foreignCount, crashed' = crashed,
      plan' = plan, sawVer' = sawVer, sawAt' = sawAt, nextBorn' = nextBorn, now' = now, uRow,
    } else all {
      phase' = phase.set(p, "Stop"), myVer' = myVer, plan' = plan, sawVer' = sawVer, sawAt' = sawAt, nextBorn' = nextBorn, now' = now,
      uRow, uClaim, uG,
    }
  }

  action observe(p: Proc): bool = all {
    phase.get(p) == "Idle", clSt == "pending", sawVer.get(p) != clVer, myVer.get(p) != clVer,
    sawVer' = sawVer.set(p, clVer), sawAt' = sawAt.set(p, now),
    phase' = phase, myVer' = myVer, plan' = plan, nextBorn' = nextBorn, now' = now, uRow, uClaim, uG,
  }

  action takeover(p: Proc): bool = all {
    phase.get(p) == "Idle", clSt == "pending", sawVer.get(p) == clVer, myVer.get(p) != clVer,
    now - sawAt.get(p) >= T_TAKEOVER,
    clVer' = clVer + 1, clSt' = clSt, clAns' = clAns,
    clBorn' = if (MUT == "fresh_born") 0 else clBorn,
    phase' = phase.set(p, "TookOver"), myVer' = myVer.set(p, clVer + 1),
    plan' = plan, sawVer' = sawVer, sawAt' = sawAt, nextBorn' = nextBorn, now' = now, uRow, uG,
  }

  // continuation: 06.1:713, 06.1:717, 06.1:719 — look first; a complete saved intent must match both values
  action lookTarget(p: Proc): bool = all {
    phase.get(p) == "TookOver",
    val proof = rowOn and clBorn != 0 and
      (if (MUT == "rev_only") true else rowBorn == clBorn)
    val first = MUT != "no_proof"
    all {
      phase' = phase.set(p, if (first and proof) "Confirmed" else "Claimed"),
      myVer' = myVer, plan' = plan, sawVer' = sawVer, sawAt' = sawAt, nextBorn' = nextBorn, now' = now,
      uRow, uClaim, uG,
    }
  }

  action crash(p: Proc): bool = all {
    phase.get(p) != "Idle", phase.get(p) != "Answered",
    phase' = phase.set(p, "Idle"), myVer' = myVer.set(p, 0), sawVer' = sawVer.set(p, -1),
    sawAt' = sawAt, plan' = plan, nextBorn' = nextBorn, now' = now, uRow, uClaim,
    landCount' = landCount, keyLanded' = keyLanded, foreignCount' = foreignCount, false409' = false409, falseSuccess' = falseSuccess, contDone' = contDone,
    crashed' = (crashed or clSt == "pending"),
  }

  // a create by another key: `cas ""` lets one pass (06.1:792)
  action foreignCreate: bool = all {
    foreignCount < FOREIGN_MAX, not(rowOn),
    rowOn' = true, rowBorn' = 100 + nextBorn, rowBy' = "C",
    foreignCount' = foreignCount + 1, nextBorn' = nextBorn + 1,
    landCount' = landCount, keyLanded' = keyLanded, false409' = false409, falseSuccess' = falseSuccess, contDone' = contDone, crashed' = crashed,
    uClaim, phase' = phase, myVer' = myVer, sawVer' = sawVer, sawAt' = sawAt, plan' = plan, now' = now,
  }

  action advance: bool = all {
    now' = now + T_TAKEOVER, nextBorn' = nextBorn,
    phase' = phase, myVer' = myVer, sawVer' = sawVer, sawAt' = sawAt, plan' = plan,
    uRow, uClaim, uG,
  }

  action step = any {
    nondet p = oneOf(PROCS) any {
      startClaim(p), checkExists(p), saveIntent(p),
      nondet o = oneOf(Set("ok", "unknown_landed", "unknown_not")) targetWrite(p, o),
      afterConflict(p), rememberDone(p), observe(p), takeover(p), lookTarget(p), crash(p),
    },
    foreignCreate,
    advance,
  }

  // -- properties on completed actions (ghosts set at the action)
  val atMostOneLand = landCount <= 1
  val noFalseSuccess = not(falseSuccess)
  val noFalse409 = not(false409)
  // done 201 answers only if the row of this key landed
  val doneMatches = clSt != "done" or clAns != "201" or keyLanded

  val w_done_cont = not(clSt == "done" and contDone)
  val w_409_foreign = not(clSt == "done" and clAns == "409")
  val w_done_ok = not(clSt == "done" and clAns == "201" and keyLanded)
  val w_foreign_row = not(rowBy == "C")
  val w_takeover = not(PROCS.exists(p => phase.get(p) == "TookOver"))
  val w_done_after_crash = not(clSt == "done" and clAns == "201" and crashed)
  val c_false = now < 0
}
