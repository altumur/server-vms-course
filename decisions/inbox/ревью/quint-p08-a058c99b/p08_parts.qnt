// -*- mode: Bluespec; -*-
// P/08 model unit: the restore of a copy in parts by the emergency move / take, and the outcome of an incomplete read (C6, C7).
// Anchors: 08.8:202-206 (head, parts, restore: GET /api/backup + GET /api/backup-part), 08.8:393 (move deadline 90 s), 08.8:463
// (restore = the state becomes exactly the copy), 08.8:414, 08.8:445 (head outcome only), 08.8:810 (break before claim, the state
// «already the copy's»); the writes of step 7 precede the claim of step 8 (08.8:482-483). Modelled: a target that reads the
// head, then the parts one by one (each may fail: 404/sha/timeout, unmodelled which), writes the rows of the part into state,
// claims at the end. The target may be the holder in the split case (a holder that serves readers, 08.8:455, 08.8:810).
// The outcome of a failed part and of the deadline after step 5 is not named at the pin: the model makes the choices of the
// text-silent point nondeterministic (abort / continue), control variants forbid them (those controls are NOT norms at the pin).
// NOT modelled: secrets, keeper's GC (p08_partgc), head change during the fetch (behind, 08.8:206), multiple neighbours.
module p08_parts {
  const PART_S: int          // seconds per part read: an environment parameter (not a norm)
  const N_PARTS: int         // parts of the head (small scope; the norm says 4096 rows, 08.8:543)
  const FETCH_FIRST: bool    // control: all parts checked before the first write (proposed in C6, not in the norm)
  const SILENT_CONTINUE: bool // text-silent: a part that failed may be skipped and the restore continues (allowed nondeterminism)
  const DEADLINE: int        // 90, 08.8:393
  const DEADLINE_RULE: bool  // control: the deadline ends the restore with a definite refusal (not named at the pin after step 5)
  const CLAIM_EARLY: bool    // mutant: claim right after all parts are read, before the writes

  var t: int
  var phase: str         // head | fetch | writing | claimed | aborted | running (claimed/aborted terminal)
  var nextPart: int      // the part number being processed
  var written: Set[int]  // parts written to state
  var got: Set[int]      // parts read and checked (FETCH_FIRST)
  var holderServes: bool // the split case: this cluster is the holder and its state serves readers
  var answered: bool
  var answerAt: int
  var claimedIncomplete: bool
  var mixedVisible: bool // a state mix observable by readers at an abort of a move at a serving holder
  var tBad: int          // the moment a part failed
  var tMix: int
  var tAbort: int
  var seq: int

  action init = all {
    t' = 0, phase' = "head", nextPart' = 1, written' = Set(), got' = Set(), answered' = false, answerAt' = 0,
    claimedIncomplete' = false, mixedVisible' = false, tBad' = 0, tMix' = 0, tAbort' = 0, seq' = 1,
    nondet h = oneOf(Set(true, false))
    holderServes' = h,
  }
  action hold = all { nextPart' = nextPart, written' = written, got' = got, holderServes' = holderServes, answered' = answered, answerAt' = answerAt, claimedIncomplete' = claimedIncomplete, mixedVisible' = mixedVisible, tBad' = tBad, tMix' = tMix, tAbort' = tAbort }

  action tickPart(ok: bool): bool = all {
    phase == "fetch" or phase == "writing",
    val p = nextPart
    all {
      nextPart <= N_PARTS,
      or { not(DEADLINE_RULE), t + PART_S <= DEADLINE },
      t' = if (FETCH_FIRST and phase == "writing") t else t + PART_S,
      if (ok or (FETCH_FIRST and phase == "writing")) {
        if (FETCH_FIRST and phase == "fetch") all {
          got' = got.union(Set(p)), written' = written,
          nextPart' = if (p < N_PARTS) p + 1 else 1,
          phase' = if (p < N_PARTS) "fetch" else "writing",
          tBad' = tBad, tMix' = tMix,
        } else all {
          // INCREMENTAL (literal) or the write of FETCH_FIRST phase 2
          written' = written.union(Set(p)),
          got' = got,
          nextPart' = p + 1,
          phase' = if (p < N_PARTS) phase else "writing_done",
          tBad' = tBad, tMix' = if (holderServes and written.size() + 1 < N_PARTS and tMix == 0) seq else tMix,
        }
      } else all {
        // part read fails: abort with 409 or, in the silent text, skip the part
        tBad' = seq,
        written' = written, got' = got,
        nextPart' = if (SILENT_CONTINUE) p + 1 else nextPart,
        phase' = if (SILENT_CONTINUE) (if (p < N_PARTS) phase else "writing_done") else phase,
        tMix' = tMix,
      },
      holderServes' = holderServes, answered' = answered, answerAt' = answerAt, claimedIncomplete' = claimedIncomplete, mixedVisible' = mixedVisible, tAbort' = tAbort, seq' = seq + 1,
    },
  }

  action startFetch = all { phase == "head", phase' = "fetch", t' = t, hold, seq' = seq + 1 }

  // abort: terminal 409; mix observable if parts were already written at a serving holder (08.8:810 accepts only «the rest is the copy's»,
  // N.B. the text allows a break, not a named outcome)
  action abort = all {
    (phase == "fetch" or phase == "writing"), tBad > 0, not(SILENT_CONTINUE),
    phase' = "aborted", answered' = true, answerAt' = t,
    nextPart' = nextPart, written' = written, got' = got, holderServes' = holderServes, claimedIncomplete' = claimedIncomplete,
    mixedVisible' = (mixedVisible or (holderServes and written.size() > 0 and written.size() < N_PARTS)),
    tBad' = tBad, tMix' = tMix, tAbort' = seq, t' = t, seq' = seq + 1,
  }

  // deadline rule (control)
  action deadlineEnd = all {
    DEADLINE_RULE, (phase == "fetch" or phase == "writing"), t + PART_S > DEADLINE,
    phase' = "aborted", answered' = true, answerAt' = t,
    nextPart' = nextPart, written' = written, got' = got, holderServes' = holderServes, claimedIncomplete' = claimedIncomplete,
    mixedVisible' = (mixedVisible or (holderServes and written.size() > 0 and written.size() < N_PARTS)),
    tBad' = tBad, tMix' = tMix, tAbort' = seq, t' = t, seq' = seq + 1,
  }

  action claim = all {
    or { phase == "writing_done", CLAIM_EARLY and phase == "writing" },
    phase' = "claimed", answered' = true, answerAt' = t,
    claimedIncomplete' = written != 1.to(N_PARTS),
    nextPart' = nextPart, written' = written, got' = got, holderServes' = holderServes, mixedVisible' = mixedVisible,
    tBad' = tBad, tMix' = tMix, tAbort' = tAbort, t' = t, seq' = seq + 1,
  }
  action noop = all {
    phase' = phase, t' = t, hold, seq' = seq,
  }

  action step = any {
    startFetch,
    nondet ok = oneOf(Set(true, false))
    tickPart(ok),
    abort, deadlineEnd, claim, noop,
  }

  val inv_claim_complete = not(claimedIncomplete)
  val inv_no_mixed_visible = not(mixedVisible)
  // an answer exists by the deadline, or the run has not reached the deadline yet (only the state where t > DEADLINE is judged)
  val inv_answer_by_deadline = not(t > DEADLINE and not(answered))
  // every completed answer (claim or refusal) came by the deadline: judged at the completed action, not at an idle state
  val inv_answered_within = not(answered) or answerAt <= DEADLINE
  val wit_claim_past_deadline = not(phase == "claimed" and answerAt > DEADLINE)
  val wit_refusal_before_deadline = not(phase == "aborted" and answerAt <= DEADLINE and answerAt > 0)
  // witnesses (order)
  val wit_part_failed_then_mix = not(tMix > 0 and tBad > tMix and tAbort > tBad)
  val wit_claim_after_failed_part = not(claimedIncomplete and tBad > 0)
  val wit_claim_full = not(phase == "claimed" and not(claimedIncomplete))
  val wit_abort_clean = not(phase == "aborted" and written == Set())
  val wit_past_deadline_running = not(t > DEADLINE and not(answered))
}

// N_PARTS small scope (3, PART_S 20 so that the sum 60 < 90; 40 so that 120 > 90); the text
module parts_text { import p08_parts(PART_S = 20, N_PARTS = 3, FETCH_FIRST = false, SILENT_CONTINUE = true, DEADLINE = 90, DEADLINE_RULE = false, CLAIM_EARLY = false).* }
module parts_text_slow { import p08_parts(PART_S = 40, N_PARTS = 3, FETCH_FIRST = false, SILENT_CONTINUE = true, DEADLINE = 90, DEADLINE_RULE = false, CLAIM_EARLY = false).* }
// fails-stop variant: literal abort on a failed part but incremental writes
module parts_incremental_abort { import p08_parts(PART_S = 20, N_PARTS = 3, FETCH_FIRST = false, SILENT_CONTINUE = false, DEADLINE = 90, DEADLINE_RULE = false, CLAIM_EARLY = false).* }
// controls: C6 proposal - fetch all first, stop on failure, deadline ends with a definite refusal
module parts_c_fetchfirst { import p08_parts(PART_S = 20, N_PARTS = 3, FETCH_FIRST = true, SILENT_CONTINUE = false, DEADLINE = 90, DEADLINE_RULE = true, CLAIM_EARLY = false).* }
module parts_c_fetchfirst_slow { import p08_parts(PART_S = 40, N_PARTS = 3, FETCH_FIRST = true, SILENT_CONTINUE = false, DEADLINE = 90, DEADLINE_RULE = true, CLAIM_EARLY = false).* }
module parts_m_claimearly { import p08_parts(PART_S = 20, N_PARTS = 3, FETCH_FIRST = true, SILENT_CONTINUE = false, DEADLINE = 90, DEADLINE_RULE = true, CLAIM_EARLY = true).* }
