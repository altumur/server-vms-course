// C4 and C5: weight checks by max_value only, and parts left behind.
// Anchors (slice ff32d483):
//   23:266      step 6 reads max_value and max_body
//   23:271      step 8: part row against max_value
//   23:282      step 14a: view row against max_value; "nothing"
//   23:293-299  step 16: toolarge stops the call, code 2 (only the row)
//   23:300-304  step 17: no toolarge branch
//   22:773      "nothing is written" for the view above the ceiling
//   p011:290    body above the limit: 413 toolarge before the store operation
//   cl:47       weight of items vs the body read limit are different limits
//   23:295-296  parts named by no row stay until the next call that moves the mark
//   23:307-309  step 19 removal
//   daemon-flags.tsv:38-39 defaults -max-value 524288, -max-body 1048576
// One installer; each attempt carries a file of a new digest (C5) or the same one.
// BODY(w, e) = w + e + ENV: the body bytes of a write whose items weigh w, e = extra bytes of JSON escaping, ENV = the envelope
// (key, op, cas, id). ENV and the escape values are parameters of the model, not limits proposed anywhere.
// PRECHECK: control, row and view are compared with max_body too, and the row with max_value, before step 15.
// CRASH: a break between step 15 and 16 (C5, 23:291).
module wgt_core {
  const MV: int
  const MB: int
  const ENV: int
  const PRECHECK: bool
  const NEWDIG: bool       // each attempt has a different digest
  const CRASH: bool
  const VW: int            // weight of the view row
  const RW: int            // weight of the manifest row
  const VE: int            // escape bytes of the view
  const RE: int            // escape bytes of the row

  var pc: str             // start | row | view | mark | clean | done | rf2 (refused, code 2) | crashed
  var attempt: int
  var rowRev: int
  var viewRev: int
  var markRev: int
  var rowAttempt: int     // last attempt whose row was written
  var orphans: Set[int]   // attempts whose parts are named by no row and no mark
  var partsOf: Set[int]   // parts present (by attempt digest)
  var failed: str         // "" | "row413" | "view413"
  var writesThisAttempt: int

  def body(w: int, e: int): int = w + e + ENV

  action init = all {
    pc' = "start", attempt' = 1, rowRev' = 1, viewRev' = 1, markRev' = 1, rowAttempt' = 0,
    orphans' = Set(), partsOf' = Set(0), failed' = "", writesThisAttempt' = 0,
  }

  // Steps 5-15 in one step. 14a checks only the weight; steps 8 passed by assumption.
  action prepare = all {
    pc == "start",
    if (VW > MV or (PRECHECK and (RW > MV or body(RW, RE) > MB or body(VW, VE) > MB))) all {
      pc' = "rf2", failed' = "", orphans' = orphans, partsOf' = partsOf, writesThisAttempt' = 0,
      rowRev' = rowRev, viewRev' = viewRev, markRev' = markRev, rowAttempt' = rowAttempt, attempt' = attempt,
    } else all {
      pc' = "row",
      // step 15 writes the parts of this attempt's digest
      partsOf' = partsOf.union(Set(attempt)),
      orphans' = orphans,
      writesThisAttempt' = 1,
      failed' = "",
      rowRev' = rowRev, viewRev' = viewRev, markRev' = markRev, rowAttempt' = rowAttempt, attempt' = attempt,
    }
  }

  // Step 16. Row weight above max_value or body above max_body: 413 toolarge (p011:290), the call stops, the parts remain.
  action writeRow = all {
    pc == "row",
    if (RW > MV or body(RW, RE) > MB) all {
      pc' = "rf2", failed' = "row413",
      orphans' = orphans.union(if (attempt != rowAttempt) Set(attempt) else Set()),
      rowRev' = rowRev, rowAttempt' = rowAttempt,
      viewRev' = viewRev, markRev' = markRev, partsOf' = partsOf, attempt' = attempt, writesThisAttempt' = writesThisAttempt,
    } else all {
      pc' = "view",
      rowRev' = rowRev + 1, rowAttempt' = attempt,
      orphans' = orphans, failed' = failed,
      viewRev' = viewRev, markRev' = markRev, partsOf' = partsOf, attempt' = attempt, writesThisAttempt' = writesThisAttempt + 1,
    },
  }

  // Step 17. The text has no branch for 413 here: the only thing the model does is to stop; the row stays written.
  action writeView = all {
    pc == "view",
    if (body(VW, VE) > MB) all {
      pc' = "rf2", failed' = "view413", viewRev' = viewRev,
      rowRev' = rowRev, markRev' = markRev, rowAttempt' = rowAttempt, orphans' = orphans, partsOf' = partsOf, attempt' = attempt,
      writesThisAttempt' = writesThisAttempt,
    } else all {
      pc' = "mark", viewRev' = rowRev, failed' = failed,
      rowRev' = rowRev, markRev' = markRev, rowAttempt' = rowAttempt, orphans' = orphans, partsOf' = partsOf, attempt' = attempt,
      writesThisAttempt' = writesThisAttempt + 1,
    },
  }

  // Step 18 and 19: the mark moves, step 19 removes all digests except this attempt's.
  action writeMark = all {
    pc == "mark",
    markRev' = rowRev, pc' = "done",
    orphans' = Set(), partsOf' = Set(attempt),
    rowRev' = rowRev, viewRev' = viewRev, rowAttempt' = rowAttempt, failed' = failed, attempt' = attempt, writesThisAttempt' = writesThisAttempt + 1,
  }

  action crashBeforeRow = all {
    CRASH, pc == "row",
    pc' = "crashed",
    orphans' = orphans.union(Set(attempt)),
    rowRev' = rowRev, viewRev' = viewRev, markRev' = markRev, rowAttempt' = rowAttempt, partsOf' = partsOf, failed' = failed, attempt' = attempt, writesThisAttempt' = writesThisAttempt,
  }

  // The operator repeats the command (same file: same digest, or a new one).
  action again = all {
    pc == "rf2" or pc == "crashed",
    pc' = "start",
    attempt' = attempt + 1,
    orphans' = orphans, partsOf' = partsOf, rowRev' = rowRev, viewRev' = viewRev, markRev' = markRev, rowAttempt' = rowAttempt,
    failed' = "", writesThisAttempt' = 0,
  }

  action stutter = all { pc == "done", pc' = pc, attempt' = attempt, rowRev' = rowRev, viewRev' = viewRev, markRev' = markRev,
    rowAttempt' = rowAttempt, orphans' = orphans, partsOf' = partsOf, failed' = failed, writesThisAttempt' = writesThisAttempt }

  action step = any { prepare, writeRow, writeView, writeMark, crashBeforeRow, again, stutter }

  // Properties.
  val inv_nothing_on_toolarge = not(failed == "row413" or failed == "view413") or writesThisAttempt == 0
  val inv_no_row_without_view = rowRev == viewRev or pc != "rf2"
  val wit_view413_after_row = not(failed == "view413" and rowRev > viewRev and markRev < rowRev)
  val wit_row413_after_parts = not(failed == "row413" and orphans.contains(attempt))
  val wit_rev_climbs = not(rowRev >= 3 and viewRev == 1 and markRev == 1 and failed == "view413")
  def orphansOver(K: int): bool = orphans.size() <= K
  val inv_orphans_le_1 = orphansOver(1)
  val inv_orphans_le_2 = orphansOver(2)
  val inv_no_orphan_at_all = orphans.size() == 0
  val wit_orphans_cleared = not(pc == "done" and orphans.size() == 0 and attempt >= 3)
  val wit_crash_orphan = not(pc == "crashed" and orphans.contains(attempt))
  val wit_published = not(pc == "done" and markRev == rowRev and viewRev == rowRev)
  val wit_refused_precheck = not(pc == "rf2" and failed == "" and writesThisAttempt == 0)
}
