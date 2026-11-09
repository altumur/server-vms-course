// -*- mode: Bluespec; -*-
// P/08 model unit: the report acceptance of one member under one active process (C15, C18).
// Anchors: common/contracts/accept.md:289-310 (steps 0-7); 08.3:685-690 (partial read, write failed before the mark,
// cleanup failed), 08.3:701-705 (unknown outcome: barrier, 503, a repeat with the same sent_at — same or heard).
// Modelled: the steps of the write sequence (report, delta, mark), failures of each write (refused / unknown applied / unknown
// not applied), an unreadable mark/generation (store or objects not answering), repeats with the same sent_at.
// NOT modelled: the turn (p08_turn), the mutex queue (p08_locks), the cleanup of old generations, base/rebase deltas (base = 0 only),
// road_quiet (step 2a abstracted: a repeat via another road with an older sent_at is not generated), signature checks, carry.
// Bound: 1 member, sent_at in {1,2}, roads d|r, one request at a time (the mutex of step 0 is a modelling assumption here).
module p08_accept {
  const REPEAT_SEEN: bool    // N: step 2 same/heard exists; mutant false — repeats always generate
  const READ_STRICT: bool    // N: unreadable -> 503, nothing written (08.3:685-687). mutant false — substitute absence
  const MARK_LAST: bool      // N: mark written after report and delta (step 7). mutant false — mark first

  type Mark = { rev: int, sent: int, via: str } // rev 0 = no mark
  var mark: Mark
  var repObjs: Set[int]          // written report objects (rev)
  var deltas: Set[int]
  var gens: Set[(int, int)]    // (rev, sent) that were ever written as a generation
  var storeUp: bool
  var cur: { sent: int, via: str, stage: str, rev: int } // stage: idle | rep | delta | mark
  var seq: int
  // history
  var dupGen: bool
  var falseOverRead: bool       // a generation made though the read was unreadable
  var ans503AfterMark: bool     // a 503 given although the mark write of this request was applied
  var tMarkApplied: int
  var t503: int
  var tRepeatSameHeard: int     // same/heard for sent equal to a mark that came with a 503
  var lastLost503Sent: int      // sent of the request that got 503 with mark applied

  action init = all {
    mark' = { rev: 0, sent: 0, via: "" }, repObjs' = Set(), deltas' = Set(), gens' = Set(), storeUp' = true,
    cur' = { sent: 0, via: "", stage: "idle", rev: 0 }, seq' = 1, dupGen' = false, falseOverRead' = false, ans503AfterMark' = false,
    tMarkApplied' = 0, t503' = 0, tRepeatSameHeard' = 0, lastLost503Sent' = 0,
  }
  action hold_hist = all {
    dupGen' = dupGen, falseOverRead' = falseOverRead, ans503AfterMark' = ans503AfterMark,
    tMarkApplied' = tMarkApplied, t503' = t503, tRepeatSameHeard' = tRepeatSameHeard, lastLost503Sent' = lastLost503Sent,
  }

  action toggleStore = all {
    storeUp' = not(storeUp), mark' = mark, repObjs' = repObjs, deltas' = deltas, gens' = gens, cur' = cur, seq' = seq + 1, hold_hist,
  }

  // a request arrives and is judged (steps 2, 2a are simplified; step 3 base>0 absent)
  action start(s: int, v: str): bool = all {
    cur.stage == "idle",
    if (not(storeUp)) {
      // unreadable: 08.3:685 -> 503 nothing written. In the mutant the absence is substituted: a generation starts over the mark.
      if (READ_STRICT) all {
        cur' = cur, dupGen' = dupGen, falseOverRead' = falseOverRead, ans503AfterMark' = ans503AfterMark,
        tMarkApplied' = tMarkApplied, t503' = t503, tRepeatSameHeard' = tRepeatSameHeard, lastLost503Sent' = lastLost503Sent,
      } else all {
        cur' = { sent: s, via: v, stage: "rep", rev: mark.rev + 1 },
        falseOverRead' = (falseOverRead or mark.rev > 0),
        dupGen' = dupGen, ans503AfterMark' = ans503AfterMark,
        tMarkApplied' = tMarkApplied, t503' = t503, tRepeatSameHeard' = tRepeatSameHeard, lastLost503Sent' = lastLost503Sent,
      }
    } else if (REPEAT_SEEN and mark.rev > 0 and s == mark.sent) all {
      // step 2: same/heard — no generation
      cur' = cur, dupGen' = dupGen, falseOverRead' = falseOverRead, ans503AfterMark' = ans503AfterMark,
      tMarkApplied' = tMarkApplied, t503' = t503,
      tRepeatSameHeard' = if (s == lastLost503Sent and t503 >= tMarkApplied and tMarkApplied > 0) seq else tRepeatSameHeard,
      lastLost503Sent' = lastLost503Sent,
    } else if (mark.rev > 0 and s < mark.sent) all {
      // an older body: the mark is ahead; do nothing (ignored by 2a or refused, the road timing is abstracted)
      cur' = cur, dupGen' = dupGen, falseOverRead' = falseOverRead, ans503AfterMark' = ans503AfterMark,
      tMarkApplied' = tMarkApplied, t503' = t503, tRepeatSameHeard' = tRepeatSameHeard, lastLost503Sent' = lastLost503Sent,
    } else all {
      cur' = { sent: s, via: v, stage: "rep", rev: mark.rev + 1 },
      dupGen' = (dupGen or gens.exists(g => g._2 == s and g._1 != mark.rev + 1)),
      falseOverRead' = falseOverRead, ans503AfterMark' = ans503AfterMark,
      tMarkApplied' = tMarkApplied, t503' = t503, tRepeatSameHeard' = tRepeatSameHeard, lastLost503Sent' = lastLost503Sent,
    },
    mark' = mark, repObjs' = repObjs, deltas' = deltas, gens' = gens, storeUp' = storeUp, seq' = seq + 1,
  }

  // stage transitions, each with an outcome of the object write
  // kind: ok | refuse | unk_applied | unk_lost
  action writeStep(kind: str): bool = all {
    cur.stage != "idle",
    val wrote = kind == "ok" or kind == "unk_applied"
    val markFirst = not(MARK_LAST)
    val st = cur.stage
    all {
      // refuse: the write of this stage is not applied, the request ends with 503 (08.3:687)
      // unk: the write unknown -> barrier -> 503; the process does not know whether it applied (08.3:701); here we decide
      repObjs' = if (st == "rep" and wrote) repObjs.union(Set(cur.rev)) else repObjs,
      deltas' = if (st == "delta" and wrote) deltas.union(Set(cur.rev)) else deltas,
      mark' = if (st == "mark" and wrote) { rev: cur.rev, sent: cur.sent, via: cur.via } else mark,
      gens' = if (st == "mark" and wrote) gens.union(Set((cur.rev, cur.sent))) else gens,
      cur' = if (kind == "ok" and st == "rep") { ...cur, stage: if (markFirst) "mark" else "delta" }
             else if (kind == "ok" and st == "delta") { ...cur, stage: if (markFirst) "idle" else "mark" }
             else if (kind == "ok" and st == "mark") { ...cur, stage: if (markFirst) "delta" else "idle" }
             else { ...cur, stage: "idle" },
      ans503AfterMark' = (ans503AfterMark or (st == "mark" and kind == "unk_applied")),
      tMarkApplied' = if (st == "mark" and wrote) seq else tMarkApplied,
      t503' = if (kind != "ok" and st == "mark") seq else t503,
      lastLost503Sent' = if (st == "mark" and kind == "unk_applied") cur.sent else lastLost503Sent,
    },
    dupGen' = dupGen, falseOverRead' = falseOverRead, tRepeatSameHeard' = tRepeatSameHeard, storeUp' = storeUp, seq' = seq + 1,
  }
  // note: the markFirst branch skeleton: when not MARK_LAST the stage order is rep -> mark -> delta

  action step = any {
    nondet s = oneOf(Set(1, 2))
    nondet v = oneOf(Set("d", "r"))
    start(s, v),
    nondet k = oneOf(Set("ok", "refuse", "unk_applied", "unk_lost"))
    writeStep(k),
    toggleStore,
  }

  // invariants
  val inv_mark_points = mark.rev == 0 or (repObjs.contains(mark.rev) and deltas.contains(mark.rev))
  val inv_no_dup_gen = not(dupGen)
  val inv_no_write_over_unreadable = not(falseOverRead)
  // witnesses
  val wit_503_with_mark_then_same = not(tMarkApplied > 0 and t503 >= tMarkApplied and tRepeatSameHeard > t503)
  val wit_store_down_reached = storeUp
  val wit_mark_set = mark.rev == 0
  // statement that 503 is not proof of absence (it IS reachable; the norm allows it, 08.3:703)
  val inv_503_means_nothing_accepted = not(ans503AfterMark)
}

module accept_norm { import p08_accept(REPEAT_SEEN = true, READ_STRICT = true, MARK_LAST = true).* }
module accept_m_norepeat { import p08_accept(REPEAT_SEEN = false, READ_STRICT = true, MARK_LAST = true).* }
module accept_m_absent { import p08_accept(REPEAT_SEEN = true, READ_STRICT = false, MARK_LAST = true).* }
module accept_m_markfirst { import p08_accept(REPEAT_SEEN = true, READ_STRICT = true, MARK_LAST = false).* }
