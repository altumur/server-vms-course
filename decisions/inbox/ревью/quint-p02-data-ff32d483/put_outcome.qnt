// C3 and the non-conflict half of C10: `unavailable` / `ambiguous` outcome of a write of steps 15-18.
// Anchors (slice ff32d483):
//   23:289-306  steps 15-18 name only a conflict and, at 16, toolarge
//   ref:32      the row toolarge row; no row for unavailable/ambiguous of a write at steps 15-18
//   23:356      "A closed list"
//   cl:80-81    503 unavailable: not done, repeat at the next step; 503 ambiguous: outcome unknown, repeat only with the same id
//   cl:94-97    retry after ambiguous with the same id; memory at least 2 min / 50000 writes; a forgotten repeat is a new write
//   cl:102      Q4 budget and no blind retry
//   23:274-276  step 10 unchanged; step 11 row same, view differs
// One installer, one name, one part digest. State: row rev (1 = previous, 2 = this call), view rev, mark rev.
// The reactions (REACT) are the point: "silent" encodes that the text does not name an outcome, by nondeterminism among
//   stop code 0, stop code !=0, retry with the same id; "ctrl" is a proposed rule; "continue" is a mutant.
// RERUN lets the operator run `manifest put` once more after a non-zero exit, with a new id.
// MEM=false: a repeat of an applied write is a new write and fails cas -> conflict -> step 9; there the row is "the same" but the
// view differs, so step 11 writes rev + 1 (23:276). That is a consequence of the text; it is a witness, not a bug of the model.
module out_core {
  const REACT: str     // "silent" | "ctrl" | "continue"
  const MEM: bool      // the store still remembers the id at the retry (cl:96)
  const RERUN: bool

  var rowRev: int      // 1 = previous, n = rev written by this name
  var viewRev: int
  var markRev: int
  var partsOK: bool
  var rowVer: int      // version of the row
  var readVer: int     // version read at step 9
  var nRev: int        // new rev chosen at step 14 (0 = unchanged branch)
  var pc: str          // start | parts | row | view | mark | exit0 | exit1
  var attempts: int    // retries of the current write
  var rowApplied: bool // the row write of this attempt was applied; its id is known to the store while MEM
  var runs: int
  var exitCode: int    // -1 = running

  val OK = "ok"
  val AMB_APPLIED = "amb_applied"
  val AMB_NOT = "amb_not"
  val UNAV = "unavail"

  action init = all {
    rowRev' = 1, viewRev' = 1, markRev' = 1, partsOK' = false, rowVer' = 1, readVer' = 1, nRev' = 0,
    pc' = "start", attempts' = 0, rowApplied' = false, runs' = 1, exitCode' = -1,
  }

  def published: bool = rowRev >= 2 and viewRev == rowRev and markRev == rowRev and partsOK

  pure def nxt(p: str): str =
    if (p == "parts") "row" else if (p == "row") "view" else if (p == "view") "mark" else "exit0"

  // Reaction to a failure of a write of stage p that is not a conflict. "silent": the text names none.
  action react(p: str): bool =
    if (REACT == "ctrl") {
      if (attempts < 2) all { pc' = p, attempts' = attempts + 1, exitCode' = exitCode }
      else all { pc' = "exit1", attempts' = 0, exitCode' = 1 }
    } else if (REACT == "continue") {
      all { pc' = nxt(p), attempts' = 0, exitCode' = if (nxt(p) == "exit0") 0 else exitCode }
    } else {
      nondet c = oneOf(Set("exit0", "exit1", "retry"))
      if (c == "exit0") all { pc' = "exit0", attempts' = 0, exitCode' = 0 }
      else if (c == "exit1") all { pc' = "exit1", attempts' = 0, exitCode' = 1 }
      else all { pc' = p, attempts' = attempts + 1, exitCode' = exitCode }
    }

  // Step 9, branches 10/11/14. The same file throughout: "row same" means rowRev >= 2 (written by this name earlier).
  action read9 = all {
    pc == "start",
    readVer' = rowVer,
    if (rowRev >= 2 and viewRev == rowRev) all { pc' = "mark", nRev' = 0 }
    else all { pc' = "parts", nRev' = rowRev + 1 },
    attempts' = 0, rowRev' = rowRev, viewRev' = viewRev, markRev' = markRev, partsOK' = partsOK, rowVer' = rowVer,
    rowApplied' = false, runs' = runs, exitCode' = exitCode,
  }

  action writeParts(o: str): bool = all {
    pc == "parts",
    partsOK' = (partsOK or o == OK or o == AMB_APPLIED),
    if (o == OK) all { pc' = "row", attempts' = 0, exitCode' = exitCode } else react("parts"),
    rowRev' = rowRev, viewRev' = viewRev, markRev' = markRev, rowVer' = rowVer, readVer' = readVer, nRev' = nRev,
    rowApplied' = rowApplied, runs' = runs,
  }

  action writeRow(o: str): bool = all {
    pc == "row",
    val again = rowApplied and MEM               // the store recognises the id: the answer of the first write
    val casOK = rowVer == readVer
    val applies = (o == OK or o == AMB_APPLIED) and not(again) and casOK
    val conflict = o == OK and not(again) and not(casOK)
    all {
      rowRev' = if (applies) nRev else rowRev,
      rowVer' = if (applies) rowVer + 1 else rowVer,
      rowApplied' = if (applies) true else rowApplied,
      if (o == OK and not(conflict)) all { pc' = "view", attempts' = 0, exitCode' = exitCode }
      else if (conflict) all { pc' = "start", attempts' = 0, exitCode' = exitCode }    // a repeat refused by cas: step 9
      else react("row"),
      viewRev' = viewRev, markRev' = markRev, partsOK' = partsOK, readVer' = readVer, nRev' = nRev, runs' = runs,
    }
  }

  action writeView(o: str): bool = all {
    pc == "view",
    viewRev' = if (o == OK or o == AMB_APPLIED) nRev else viewRev,
    if (o == OK) all { pc' = "mark", attempts' = 0, exitCode' = exitCode } else react("view"),
    rowRev' = rowRev, markRev' = markRev, partsOK' = partsOK, rowVer' = rowVer, readVer' = readVer, nRev' = nRev, rowApplied' = rowApplied, runs' = runs,
  }

  // Step 18: the value written is nRev (the branch unchanged: the mark is brought to the row).
  action writeMark(o: str): bool = all {
    pc == "mark",
    val target = if (nRev == 0) rowRev else nRev
    markRev' = if ((o == OK or o == AMB_APPLIED) and markRev < target) target else markRev,
    if (o == OK) all { pc' = "exit0", attempts' = 0, exitCode' = 0 } else react("mark"),
    rowRev' = rowRev, viewRev' = viewRev, partsOK' = partsOK, rowVer' = rowVer, readVer' = readVer, nRev' = nRev, rowApplied' = rowApplied, runs' = runs,
  }

  // The operator repeats manifest put after a non-zero exit (a new id, the same file).
  action rerun = all {
    RERUN, pc == "exit1", runs == 1,
    pc' = "start", runs' = 2, attempts' = 0, exitCode' = -1,
    rowRev' = rowRev, viewRev' = viewRev, markRev' = markRev, partsOK' = partsOK, rowVer' = rowVer, readVer' = readVer, nRev' = nRev, rowApplied' = rowApplied,
  }

  action stutter = all { (pc == "exit0" or pc == "exit1"),
    rowRev' = rowRev, viewRev' = viewRev, markRev' = markRev, partsOK' = partsOK, rowVer' = rowVer, readVer' = readVer, nRev' = nRev,
    pc' = pc, attempts' = attempts, rowApplied' = rowApplied, runs' = runs, exitCode' = exitCode }

  action step = {
    nondet o = oneOf(Set(OK, AMB_APPLIED, AMB_NOT, UNAV))
    any { read9, writeParts(o), writeRow(o), writeView(o), writeMark(o), rerun, stutter }
  }

  val inv_no_false_success = exitCode != 0 or published
  val inv_mark_le_row = markRev <= rowRev
  val inv_view_le_row = viewRev <= rowRev
  val inv_rev_one_step = rowRev <= 2
  val inv_parts_before_row = rowRev < 2 or partsOK
  val inv_rerun_converges = not(pc == "exit0" and runs == 2) or published
  val wit_code0_row_applied_mark_missing = not(exitCode == 0 and rowRev == 2 and markRev == 1)
  val wit_code0_parts_only = not(exitCode == 0 and rowRev == 1 and partsOK)
  val wit_ambiguous_applied_retry = not(rowRev == 2 and attempts == 0 and pc == "view" and runs == 1 and rowApplied and rowVer == 2)
  val wit_rerun_after_exit1 = not(pc == "exit0" and exitCode == 0 and runs == 2 and published)
  val wit_lost_memory_double_rev = not(rowRev == 3 and pc == "exit0" and published)
  val wit_mark_above_row = not(markRev > rowRev)
}
