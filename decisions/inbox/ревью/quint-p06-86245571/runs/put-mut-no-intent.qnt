// -*- mode: Bluespec; -*-
// Claim of PUT (and table write) with an idempotency key: continuation after a takeover.
// Source anchors (slice 86245571, verified by check_anchors.py):
//   06.1:707  target write under the guard; 06.1:714 PUT continuation test; 06.1:715 table continuation test;
//   06.1:830  step 5a intent; 06.1:831 step 6 cas + guard; 06.1:783 unknown outcome keeps pending; const:32 CLAIM_TAKEOVER_AFTER.
// Abstraction: one row, one key K, processes A and B (consoles), one foreign writer C with its own key.
// Time: `now` in seconds, advanced only in steps of CLAIM_TAKEOVER_AFTER (the only deadline of this model).
// NOT modelled: If-Match, references (steps 4,5), the done answer body bytes, the 409/422 answers to the repeat, multiple rows.
module claim_put {
  pure val T_TAKEOVER = 30       // const:32 CLAIM_TAKEOVER_AFTER
  pure val FOREIGN_MAX = 0  // @override bound on foreign edits by C
  pure val MUT = "no_intent"  // @override none | no_intent | no_guard | takeover_blind
  pure val REPAIR = false        // @override continuation also proves own content (not in the norm; control only)
  type Proc = str
  pure val PROCS = Set("A", "B")

  // store: the unit row
  var rowIdx: int                // store index of the row (cas)
  var rowRev: int                // field revision of the row
  var rowBy: str                 // whose body lies in the row: base | K | C
  // store: the claim row <sub>/idem/<key>
  var clSt: str                  // none | pending | done
  var clVer: int
  var clIntent: int              // intended revision saved at step 5a; 0 = no intent
  // per-process
  var phase: Proc -> str
  var myVer: Proc -> int
  var readIdx: Proc -> int
  var readRev: Proc -> int
  var sawVer: Proc -> int
  var sawAt: Proc -> int
  var now: int
  // ghosts: what really happened
  var landCount: int
  var keyLanded: bool
  var foreignCount: int
  var falseSuccess: bool
  var contDone: bool
  var crashed: bool              // an executor was lost (crash or SIGTERM) while the claim was pending

  action init = all {
    rowIdx' = 1, rowRev' = 1, rowBy' = "base",
    clSt' = "none", clVer' = 0, clIntent' = 0,
    phase' = PROCS.mapBy(p => "Idle"),
    myVer' = PROCS.mapBy(p => 0),
    readIdx' = PROCS.mapBy(p => 0),
    readRev' = PROCS.mapBy(p => 0),
    sawVer' = PROCS.mapBy(p => -1),
    sawAt' = PROCS.mapBy(p => 0),
    now' = 0,
    landCount' = 0, keyLanded' = false, foreignCount' = 0, falseSuccess' = false, contDone' = false, crashed' = false,
  }

  action unchangedAux = all {
    readIdx' = readIdx, readRev' = readRev, sawVer' = sawVer, sawAt' = sawAt, now' = now,
  }
  action unchangedRow = all { rowIdx' = rowIdx, rowRev' = rowRev, rowBy' = rowBy }
  action unchangedClaim = all { clSt' = clSt, clVer' = clVer, clIntent' = clIntent }
  action unchangedGhost = all { landCount' = landCount, keyLanded' = keyLanded, foreignCount' = foreignCount, falseSuccess' = falseSuccess, contDone' = contDone, crashed' = crashed }

  // 1a: claim `cas ""` (create step 2)
  action startClaim(p: Proc): bool = all {
    phase.get(p) == "Idle", clSt == "none",
    clSt' = "pending", clVer' = clVer + 1, clIntent' = 0,
    phase' = phase.set(p, "Claimed"), myVer' = myVer.set(p, clVer + 1),
    unchangedRow, unchangedAux, unchangedGhost,
  }

  // a repeat at p sees a foreign pending: first observation of this version (06.1:183 style local observation)
  action observe(p: Proc): bool = all {
    phase.get(p) == "Idle", clSt == "pending", sawVer.get(p) != clVer, myVer.get(p) != clVer,
    sawVer' = sawVer.set(p, clVer), sawAt' = sawAt.set(p, now),
    phase' = phase, myVer' = myVer, readIdx' = readIdx, readRev' = readRev, now' = now,
    unchangedRow, unchangedClaim, unchangedGhost,
  }

  // takeover after CLAIM_TAKEOVER_AFTER of an unchanged version; keeps the intent (06.1:714, 06.1:763)
  action takeover(p: Proc): bool = all {
    phase.get(p) == "Idle", clSt == "pending", sawVer.get(p) == clVer, myVer.get(p) != clVer,
    now - sawAt.get(p) >= T_TAKEOVER,
    clVer' = clVer + 1, clSt' = clSt,
    clIntent' = clIntent,
    phase' = phase.set(p, "TookOver"), myVer' = myVer.set(p, clVer + 1),
    unchangedRow, unchangedAux, unchangedGhost,
  }

  // continuation: look at the target first (06.1:713-715)
  action lookTarget(p: Proc): bool = all {
    phase.get(p) == "TookOver",
    val written = clIntent != 0 and rowRev == clIntent and (not(REPAIR) or rowBy == "K") and MUT != "takeover_blind"
    all {
      phase' = phase.set(p, if (written) "Confirmed" else "Claimed"),
      myVer' = myVer, unchangedRow, unchangedClaim, unchangedAux, unchangedGhost,
    }
  }

  // step 3: read the row
  action read(p: Proc): bool = all {
    phase.get(p) == "Claimed",
    readIdx' = readIdx.set(p, rowIdx), readRev' = readRev.set(p, rowRev),
    phase' = phase.set(p, "Read"), myVer' = myVer,
    sawVer' = sawVer, sawAt' = sawAt, now' = now,
    unchangedRow, unchangedClaim, unchangedGhost,
  }

  // step 5a: intent by cas of my version
  action saveIntent(p: Proc): bool = all {
    phase.get(p) == "Read",
    if (MUT == "no_intent") all {
      phase' = phase.set(p, "Intended"), myVer' = myVer,
      unchangedClaim, unchangedRow, unchangedAux, unchangedGhost,
    } else if (clVer == myVer.get(p) and clSt == "pending") all {
      clVer' = clVer + 1, clSt' = clSt, clIntent' = readRev.get(p) + 1,
      myVer' = myVer.set(p, clVer + 1), phase' = phase.set(p, "Intended"),
      unchangedRow, unchangedAux, unchangedGhost,
    } else all {
      phase' = phase.set(p, "Stop"), myVer' = myVer,
      unchangedRow, unchangedClaim, unchangedAux, unchangedGhost,
    }
  }

  // step 6: write with cas of the read version and the guard of my claim version
  action targetWrite(p: Proc, outcome: str): bool = all {
    phase.get(p) == "Intended",
    val guardOk = MUT == "no_guard" or (clVer == myVer.get(p) and clSt == "pending")
    val casOk = rowIdx == readIdx.get(p)
    val land = guardOk and casOk and outcome != "unknown_not"
    all {
      if (land) all {
        rowIdx' = rowIdx + 1, rowRev' = readRev.get(p) + 1, rowBy' = "K",
        landCount' = landCount + 1, keyLanded' = true,
      } else all {
        unchangedRow, landCount' = landCount, keyLanded' = keyLanded,
      },
      phase' = phase.set(p,
        if (outcome == "unknown_landed" or outcome == "unknown_not") "Unknown"
        else if (land) "Landed"
        else if (not(guardOk)) "Stop"
        else "Claimed"),
      myVer' = myVer,
      unchangedClaim, unchangedAux,
      foreignCount' = foreignCount, falseSuccess' = falseSuccess, contDone' = contDone, crashed' = crashed,
    }
  }

  // step 9: remember the answer by cas of my version
  action rememberDone(p: Proc): bool = all {
    phase.get(p) == "Landed" or phase.get(p) == "Confirmed",
    if (clVer == myVer.get(p) and clSt == "pending") all {
      clSt' = "done", clVer' = clVer + 1, clIntent' = clIntent,
      phase' = phase.set(p, "Answered"), myVer' = myVer,
      falseSuccess' = (falseSuccess or not(keyLanded)),
      contDone' = (contDone or phase.get(p) == "Confirmed"),
      landCount' = landCount, keyLanded' = keyLanded, foreignCount' = foreignCount, crashed' = crashed,
      unchangedRow, unchangedAux,
    } else all {
      phase' = phase.set(p, "Stop"), myVer' = myVer,
      unchangedRow, unchangedClaim, unchangedAux, unchangedGhost,
    }
  }

  // crash / orderly SIGTERM: the process leaves, the claim stays in the row (life:92)
  action crash(p: Proc): bool = all {
    phase.get(p) != "Idle", phase.get(p) != "Answered",
    phase' = phase.set(p, "Idle"), myVer' = myVer.set(p, 0),
    sawVer' = sawVer.set(p, -1), sawAt' = sawAt, readIdx' = readIdx, readRev' = readRev, now' = now,
    unchangedRow, unchangedClaim,
    landCount' = landCount, keyLanded' = keyLanded, foreignCount' = foreignCount, falseSuccess' = falseSuccess, contDone' = contDone,
    crashed' = (crashed or clSt == "pending"),
  }

  // foreign edit with its own key (cas of the current row version)
  action foreignEdit: bool = all {
    foreignCount < FOREIGN_MAX,
    rowIdx' = rowIdx + 1, rowRev' = rowRev + 1, rowBy' = "C",
    foreignCount' = foreignCount + 1,
    phase' = phase, myVer' = myVer, unchangedClaim, unchangedAux,
    landCount' = landCount, keyLanded' = keyLanded, falseSuccess' = falseSuccess, contDone' = contDone, crashed' = crashed,
  }

  action advance: bool = all {
    now' = now + T_TAKEOVER,
    phase' = phase, myVer' = myVer, readIdx' = readIdx, readRev' = readRev, sawVer' = sawVer, sawAt' = sawAt,
    unchangedRow, unchangedClaim, unchangedGhost,
  }

  action step = any {
    nondet p = oneOf(PROCS) any {
      startClaim(p), observe(p), takeover(p), lookTarget(p), read(p), saveIntent(p),
      nondet o = oneOf(Set("ok", "unknown_landed", "unknown_not")) targetWrite(p, o),
      rememberDone(p), crash(p),
    },
    foreignEdit,
    advance,
  }

  // -- properties (each constrains a completed action via a ghost set at the action)
  // A done answer for key K while K's body never landed: the client is told "written" for a foreign edit.
  val noFalseSuccess = not(falseSuccess)
  // The same key lands its target write at most once.
  val atMostOneLand = landCount <= 1

  // -- witnesses (expect: violated = reachable)
  val w_done_after_unknown = not(clSt == "done" and keyLanded and contDone)
  val w_takeover_reached = not(PROCS.exists(p => phase.get(p) == "TookOver"))
  val w_foreign_seen = not(foreignCount > 0 and clSt == "done")
  val w_land = not(keyLanded)
  val w_done_after_crash = not(clSt == "done" and crashed)

  // -- control: a deliberately false invariant to show the tool reports violations at this shape
  val c_false = now < 0
}
