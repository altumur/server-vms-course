// C1, the cost of `manifest put`: counting the store calls the text requires, per phase.
// Anchors (slice ff32d483):
//   23:264      step 5: the full confirmed catalogue, all rows `platform/manifest/*` (21:1190)
//   21:1190     the catalogue is checked pairwise; "any subsystems A and B"
//   21:1174     "the catalogue is checked whole at every installation"
//   23:266      step 6: one status read
//   23:273      step 9: row, view, mark
//   23:274-275  step 10 unchanged: parts brought up (step 15), mark brought up
//   23:289-290  step 15: read each part, write absent/different
//   23:293,300,305 steps 16-18: one write each (cas); the read of the mark is step 9
//   23:307      step 19: re-read the row, list, delete old digests
//   23:46       FILE_PART 262144, FILES_TOTAL_MAX 33554432: at most 128 parts per put
// The counters follow the phases; the phases are the machine, the counting inside each phase is a formula, stated by the text.
// S: subsystems in the catalogue (the candidate replaced by name; a new name adds one row)
// P: parts of the candidate; W: of them absent or different; D: rows to delete at step 19; C: conflicts of the row (each repeats from step 9)
// Not modelled: the size of a read (S rows carry yaml + view, parts carry up to 349 KiB each), retries of steps 15, 17, 18,
// the view conflicts, the time of an operation. Time is expressed nowhere here.
module cost_core {
  const S: int
  const P: int
  const W: int
  const D: int
  const C: int
  const UNCHANGED: bool

  var pc: str
  var reads: int
  var writes: int
  var deletes: int
  var cmp: int           // comparisons of load_catalogue (pairs of subsystems)
  var left: int          // conflicts still to come

  action init = all { pc' = "cat", reads' = 0, writes' = 0, deletes' = 0, cmp' = 0, left' = C }

  // Step 5: list + one get per manifest row.
  action phaseCat = all { pc == "cat", pc' = "status", reads' = reads + 1 + S, writes' = writes, deletes' = deletes, cmp' = cmp + S * S, left' = left }
  action phaseStatus = all { pc == "status", pc' = "s9", reads' = reads + 1, writes' = writes, deletes' = deletes, cmp' = cmp, left' = left }
  // Steps 9-14a.
  action phaseS9 = all { pc == "s9", pc' = "parts", reads' = reads + 3, writes' = writes, deletes' = deletes, cmp' = cmp, left' = left }
  // Step 15 (and step 10): every part is read each pass; only the first pass finds the W absent ones.
  action phaseParts = all { pc == "parts", pc' = if (UNCHANGED) "mark" else "row", reads' = reads + P, writes' = writes + (if (left == C) W else 0), deletes' = deletes, cmp' = cmp, left' = left }
  // Step 16: with a conflict: repeat from step 9.
  action phaseRow = all {
    pc == "row",
    pc' = if (left > 0) "s9" else "view",
    reads' = reads, writes' = writes + 1, deletes' = deletes, cmp' = cmp, left' = if (left > 0) left - 1 else left,
  }
  action phaseView = all { pc == "view", pc' = "mark", reads' = reads, writes' = writes + 1, deletes' = deletes, cmp' = cmp, left' = left }
  // Step 18 (the mark was read at step 9; "unchanged" with an up-to-date mark writes nothing).
  action phaseMark = all { pc == "mark", pc' = if (UNCHANGED) "done" else "clean", reads' = reads, writes' = writes + (if (UNCHANGED) 0 else 1), deletes' = deletes, cmp' = cmp, left' = left }
  // Step 19.
  action phaseClean = all { pc == "clean", pc' = "done", reads' = reads + 2, writes' = writes, deletes' = deletes + D, cmp' = cmp, left' = left }
  action stutter = all { pc == "done", pc' = pc, reads' = reads, writes' = writes, deletes' = deletes, cmp' = cmp, left' = left }

  action step = any { phaseCat, phaseStatus, phaseS9, phaseParts, phaseRow, phaseView, phaseMark, phaseClean, stutter }

  val totalOps = reads + writes + deletes
  // Expected values by the formula of the report, for the runs of a chosen grid.
  val inv_reads_expected = pc != "done" or reads == (1 + S) + 1 + (3 + P) * (C + 1) + (if (UNCHANGED) 0 else 2)
  val inv_writes_expected = pc != "done" or writes == (if (UNCHANGED) W else W + (C + 1) + 2)
  val inv_cmp_expected = pc != "done" or cmp == S * S
  val wit_done = not(pc == "done")
}
