// C6, C2, C10 and the view re-read order: installers of ONE name, the writes of steps 9-19.
// Anchors (slice ff32d483):
//   23:289-292  step 15: parts, cas, a conflict re-reads the part; a break leaves the previous revision whole
//   23:293-296  step 16: row by cas of the version read; conflict -> step 9
//   23:300-304  step 17: view by cas; conflict -> re-read row and view, mine -> repeat cas, other -> step 9
//   23:305-306  step 18: mark, cas by version, below the row; conflict -> re-read while below
//   23:307-309  step 19: mark moved by this call and re-read row rev is mine -> list, delete digests outside its files
//   23:326-330  file races; a part removed by the race is brought up by the next put
//   23:350      races of one name; mark only rises; lagging installer cannot lower it
//   22:778-782  the same re-read rule for the view
// The store is one linearizable register for each key (P/01.1). One digest stands for the whole set of parts of one revision;
// the parts are not modelled one by one, except where 23:289 matters for C6 (a digest either is whole or is deleted).
// A step of this machine is one store call. The text does not say whether steps 17a/17b read the row or the view first: VIEW_FIRST.
// Parameters that encode a reading of a silent text or a proposed rule are consts below; none is a budget to adopt.
module race_core {
  const N: int              // number of installers (1..3)
  const D2: int             // digest of installer 2 (installer 1 has digest 2; the initial row has digest 1)
  const D3: int
  const VIEW_FIRST: bool    // re-read order of step 17 (the text does not fix it); true = view, then row
  const ATOMIC19: bool      // true: re-read of the row and the delete in one store call
  const CLEAN: str          // "norm" delete digests outside its files; "known" only the digest of the row this call read at step 9
                            // ("guard" = "norm" digests, the delete conditioned on the row version: a guard, cl:41)
  const POSTPARTS: bool     // control: after step 16 write the parts again (step 15) before the view
  const SEQ: bool           // installer i starts only after i-1 finished (the sequential window)
  const CRASH: bool         // installer 1 may die before any step
  const FOREIGN: bool       // an external writer bumps the row version (a frequent foreign write, C2)
  const BUDGET: int         // conflicts on the row allowed before a refusal; -1 = no budget (the text)
  const MARK_CAS: bool      // false = mutant: the mark is written without cas and without "below the row"
  const ENFORCE: bool       // false = mutant: BUDGET exists but is not applied
  const COARSE: bool        // true: step 9 + step 15 are one store interaction, and on a passed cas the view and the mark are one step
                            // (for the C6 runs: the race there is between step 19 and the row of the other installer only)
  const MID: bool           // start from the mid-state of three installers (see init); reachable, wit_mid_state

  type S = {
    rowRev: int, rowDig: int, rowVer: int,
    viewRev: int, viewDig: int, viewVer: int,
    markRev: int, markDig: int, markVer: int,
    parts: Set[int],
    pc: int -> str,
    rR: int -> int, rV: int -> int, rD: int -> int, vV: int -> int, mV: int -> int, nRev: int -> int,
    mine: int -> bool, brought: int -> bool, conflicts: int -> int,
    listed: int -> Set[int],
    tParts: int -> int, tRow: int -> int, tDel: int -> int,
    tBreak: int -> int,
    viewFell: bool, markFell: bool, viewFellAt: int,
    seq: int,
  }

  var s: S

  val I: Set[int] = if (N == 1) Set(1) else if (N == 2) Set(1, 2) else Set(1, 2, 3)
  pure def term(p: str): bool = p == "done" or p == "dead" or p == "refused"

  pure def dig(i: int): int = if (i == 1) 2 else if (i == 2) D2 else D3
  def allTerm: bool = I.forall(i => term(s.pc.get(i)))

  // MID (run with N=2): installer 1 wrote row 3 (digest 2) and is about to write the view with the version it read at step 9
  // (view version 1); meanwhile another installer (not modelled) wrote view rev 2 of its row 2 (digest 4), so the cas of
  // installer 1 will conflict; installer 2 has not started (digest 3). wit_mid_state reaches this state with three installers.
  action init = all {
    s' = {
      rowRev: if (MID) 3 else 1, rowDig: if (MID) 2 else 1, rowVer: if (MID) 3 else 1,
      viewRev: if (MID) 2 else 1, viewDig: if (MID) 4 else 1, viewVer: if (MID) 2 else 1,
      markRev: 1, markDig: 1, markVer: 1,
      parts: if (MID) Set(1, 2, 4) else Set(1),
      pc: if (MID) I.mapBy(i => if (i == 1) "s17" else "s9") else I.mapBy(_ => "s9"),
      rR: I.mapBy(_ => 0), rV: I.mapBy(_ => 0), rD: I.mapBy(_ => 0),
      vV: if (MID) I.mapBy(i => if (i == 1) 1 else 0) else I.mapBy(_ => 0),
      mV: I.mapBy(_ => 0), nRev: if (MID) I.mapBy(i => if (i == 1) 3 else 0) else I.mapBy(_ => 0),
      mine: I.mapBy(_ => false), brought: I.mapBy(_ => false), conflicts: I.mapBy(_ => 0),
      listed: I.mapBy(_ => Set()),
      tParts: I.mapBy(_ => -1), tRow: I.mapBy(_ => -1), tDel: I.mapBy(_ => -1), tBreak: I.mapBy(_ => -1),
      viewFell: false, markFell: false, viewFellAt: -1,
      seq: 0,
    }
  }

  def may(i: int): bool = I.contains(i) and (not(SEQ) or i == 1 or term(s.pc.get(i - 1)))
  def at(i: int, p: str): bool = s.pc.get(i) == p and may(i)
  def adv(st: S): S = st.with("seq", st.seq + 1)

  // Step 9, branches 10/11/14.
  action read9(i: int): bool = all {
    at(i, "s9"),
    val same = s.rowDig == dig(i) and s.viewDig == dig(i)
    val r = adv(s).with("rR", s.rR.set(i, s.rowRev)).with("rV", s.rV.set(i, s.rowVer)).with("rD", s.rD.set(i, s.rowDig))
              .with("vV", s.vV.set(i, s.viewVer))
    val coarseParts = r.with("parts", s.parts.union(Set(dig(i)))).with("tParts", s.tParts.set(i, s.seq))
    if (same) s' = if (COARSE) coarseParts.with("pc", s.pc.set(i, "u18")) else r.with("pc", s.pc.set(i, "u15"))
    else if (COARSE) s' = coarseParts.with("nRev", s.nRev.set(i, s.rowRev + 1)).with("pc", s.pc.set(i, "s16"))
    else s' = r.with("nRev", s.nRev.set(i, s.rowRev + 1)).with("pc", s.pc.set(i, "s15"))
  }

  // Step 15 (one digest at once) and the unchanged branch of step 10.
  action writeParts(i: int): bool = all {
    at(i, "s15") or at(i, "u15"),
    val st = adv(s).with("parts", s.parts.union(Set(dig(i)))).with("tParts", s.tParts.set(i, s.seq))
    s' = st.with("pc", s.pc.set(i, if (s.pc.get(i) == "s15") "s16" else "u18"))
  }

  // Step 16.
  action writeRow(i: int): bool = all {
    at(i, "s16"),
    if (s.rowVer == s.rV.get(i))
      s' = adv(s).with("rowRev", s.nRev.get(i)).with("rowDig", dig(i)).with("rowVer", s.rowVer + 1)
             .with("tRow", s.tRow.set(i, s.seq))
             .with("pc", s.pc.set(i, if (POSTPARTS) "s16p" else "s17"))
    else
      val c = s.conflicts.get(i) + 1
      s' = adv(s).with("conflicts", s.conflicts.set(i, c))
             .with("pc", s.pc.set(i, if (ENFORCE and BUDGET > 0 and c >= BUDGET) "refused" else "s9"))
  }

  // Control POSTPARTS only: the parts once more, after the row.
  action postParts(i: int): bool = all {
    at(i, "s16p"),
    s' = adv(s).with("parts", s.parts.union(Set(dig(i)))).with("pc", s.pc.set(i, "s17"))
  }

  // Step 17: the view by cas.
  action writeView(i: int): bool = all {
    at(i, "s17"),
    if (s.viewVer == s.vV.get(i))
      val low = s.nRev.get(i) < s.viewRev
      val st = adv(s).with("viewRev", s.nRev.get(i)).with("viewDig", dig(i)).with("viewVer", s.viewVer + 1)
             .with("viewFell", s.viewFell or low)
             .with("viewFellAt", if (low and not(s.viewFell)) s.seq else s.viewFellAt)
      if (not(COARSE))
        s' = st.with("pc", s.pc.set(i, "s18"))
      else if (s.markRev < s.nRev.get(i))
        s' = st.with("markRev", s.nRev.get(i)).with("markDig", s.rowDig).with("markVer", s.markVer + 1)
               .with("brought", s.brought.set(i, true)).with("pc", s.pc.set(i, "s19a"))
      else
        s' = st.with("pc", s.pc.set(i, "s19a"))
    else
      s' = adv(s).with("pc", s.pc.set(i, "s17a"))
  }

  // The re-read after a conflict of the view: two store calls, the order is the parameter VIEW_FIRST.
  action reread1(i: int): bool = all {
    at(i, "s17a"),
    if (VIEW_FIRST) s' = adv(s).with("vV", s.vV.set(i, s.viewVer)).with("pc", s.pc.set(i, "s17b"))
    else s' = adv(s).with("mine", s.mine.set(i, s.rowRev == s.nRev.get(i))).with("pc", s.pc.set(i, "s17b"))
  }
  action reread2(i: int): bool = all {
    at(i, "s17b"),
    if (VIEW_FIRST)
      s' = adv(s).with("pc", s.pc.set(i, if (s.rowRev == s.nRev.get(i)) "s17" else "s9"))
    else
      s' = adv(s).with("vV", s.vV.set(i, s.viewVer)).with("pc", s.pc.set(i, if (s.mine.get(i)) "s17" else "s9"))
  }

  // Step 18 and the unchanged branch.
  action readMark(i: int): bool = all {
    at(i, "s18") or at(i, "u18"),
    val u = s.pc.get(i) == "u18"
    val target = if (u) s.rR.get(i) else s.nRev.get(i)
    if (s.markRev < target)
      s' = adv(s).with("mV", s.mV.set(i, s.markVer)).with("pc", s.pc.set(i, if (u) "u18w" else "s18w"))
    else
      s' = adv(s).with("pc", s.pc.set(i, if (u) "done" else "s19a"))
  }

  action writeMark(i: int): bool = all {
    at(i, "s18w") or at(i, "u18w"),
    val u = s.pc.get(i) == "u18w"
    val target = if (u) s.rR.get(i) else s.nRev.get(i)
    if (not(MARK_CAS) or s.markVer == s.mV.get(i))
      s' = adv(s).with("markRev", target).with("markDig", s.rowDig).with("markVer", s.markVer + 1)
             .with("markFell", s.markFell or target < s.markRev)
             .with("brought", if (u) s.brought else s.brought.set(i, true))
             .with("pc", s.pc.set(i, if (u) "done" else "s19a"))
    else
      s' = adv(s).with("pc", s.pc.set(i, if (u) "u18" else "s18"))
  }

  def toDelete(i: int, l: Set[int]): Set[int] =
    if (CLEAN == "known") l.filter(d => d == s.rD.get(i) and d != dig(i))
    else l.filter(d => d != dig(i))

  // Step 19: re-read the row, list; the delete.
  action clean1(i: int): bool = all {
    at(i, "s19a"),
    val go = s.brought.get(i) and s.rowRev == s.nRev.get(i)
    if (not(go))
      s' = adv(s).with("pc", s.pc.set(i, "done"))
    else if (ATOMIC19)
      s' = adv(s).with("parts", s.parts.exclude(toDelete(i, s.parts)))
             .with("tDel", s.tDel.set(i, s.seq)).with("pc", s.pc.set(i, "done"))
    else
      s' = adv(s).with("listed", s.listed.set(i, s.parts)).with("pc", s.pc.set(i, "s19b"))
  }

  action clean2(i: int): bool = all {
    at(i, "s19b"),
    val allowed = CLEAN != "guard" or s.rowRev == s.nRev.get(i)
    if (allowed)
      s' = adv(s).with("parts", s.parts.exclude(toDelete(i, s.listed.get(i))))
             .with("tDel", s.tDel.set(i, s.seq)).with("pc", s.pc.set(i, "done"))
    else
      s' = adv(s).with("pc", s.pc.set(i, "done"))
  }

  action crash(i: int): bool = all {
    CRASH, i == 1, not(term(s.pc.get(i))),
    s' = adv(s).with("pc", s.pc.set(i, "dead"))
  }

  action foreign = all {
    FOREIGN,
    s' = adv(s).with("rowVer", s.rowVer + 1)
  }

  action stutter = all { allTerm, s' = s }

  action step = {
    nondet i = oneOf(I)
    any { read9(i), writeParts(i), writeRow(i), postParts(i), writeView(i), reread1(i), reread2(i),
          readMark(i), writeMark(i), clean1(i), clean2(i), crash(i), foreign, stutter }
  }

  // Properties and witnesses.
  val inv_row_names_parts = s.parts.contains(s.rowDig)
  val inv_published_whole = s.markRev < s.rowRev or s.parts.contains(s.markDig)
  val inv_mark_le_row = s.markRev <= s.rowRev
  val inv_mark_never_fell = not(s.markFell)
  val inv_view_never_fell = not(s.viewFell)
  val inv_quiescent_published = not(allTerm) or (s.viewRev == s.rowRev and s.markRev == s.rowRev and s.viewDig == s.rowDig)
  val inv_quiescent_parts = not(allTerm) or s.parts.contains(s.rowDig)
  // the previous revision stays whole until the row of this call is written (23:291-292)
  val inv_prev_whole = (s.tRow.get(1) >= 0) or s.pc.get(2) != "s9" or (s.rowRev == 1 and s.parts.contains(1) and s.markRev == 1 and s.viewRev == 1)

  // C6: A deleted B's parts; B had written them before and writes its row after the delete.
  val wit_foreign_parts_deleted =
    not(s.tDel.get(1) >= 0 and s.tParts.get(2) >= 0 and s.tParts.get(2) < s.tDel.get(1)
        and s.tRow.get(2) > s.tDel.get(1) and s.rowDig == dig(2) and not(s.parts.contains(s.rowDig)))
  // the same on the published row
  val wit_published_row_no_parts =
    not(s.markRev == s.rowRev and s.rowDig == dig(2) and s.tDel.get(1) >= 0 and not(s.parts.contains(s.rowDig)))
  // C2: the row was conflicted K times
  def wit_conflicts(K: int): bool = not(s.conflicts.get(1) >= K)
  val wit_conflicts_3 = wit_conflicts(3)
  val wit_conflicts_5 = wit_conflicts(5)
  val inv_conflicts_bounded = s.conflicts.get(1) <= BUDGET or BUDGET < 0
  val wit_refused_by_budget = not(s.pc.get(1) == "refused")
  val wit_refused_nothing_of_mine = not(s.pc.get(1) == "refused" and s.tRow.get(1) < 0)

  // C10: recovery after a break
  val inv_recovered = not(allTerm and s.pc.get(1) == "dead" and N == 2) or
      (s.rowRev == s.viewRev and s.viewRev == s.markRev and s.parts.contains(s.rowDig))
  val wit_row_without_mark_after_break =
    not(s.pc.get(1) == "dead" and s.tRow.get(1) >= 0 and s.markRev < s.rowRev and s.viewRev < s.rowRev)
  val wit_view_without_mark_after_break =
    not(s.pc.get(1) == "dead" and s.tRow.get(1) >= 0 and s.viewRev == s.rowRev and s.markRev < s.rowRev)
  val wit_recovery_rev_jumps =
    not(s.pc.get(1) == "dead" and allTerm and s.rowRev == 3 and s.markRev == 3)
  val wit_recovery_unchanged =
    not(s.pc.get(1) == "dead" and allTerm and s.pc.get(2) == "done" and s.rowRev == 2 and s.markRev == 2)
  val wit_old_parts_left_unchanged =
    not(s.pc.get(1) == "dead" and allTerm and s.pc.get(2) == "done" and s.rowRev == 2 and s.parts.contains(1))

  // the row-first re-read: a view regressed under a published mark
  val wit_view_regressed = not(allTerm and s.viewFell and s.viewRev < s.markRev and s.rowRev == s.markRev)
  val wit_three_install_order =
    not(s.viewFell and s.tRow.get(2) >= 0 and s.tRow.get(2) < s.viewFellAt)
  // the mid-state of the module MID, reached from the initial state by the full protocol
  val wit_mid_state = not(s.rowRev == 3 and s.rowDig == 2 and s.pc.get(1) == "s17" and s.nRev.get(1) == 3 and s.viewRev == 2 and s.vV.get(1) == 1 and s.viewVer == 2)
  val wit_view_fell_mark_row =
    not(s.viewFell and s.viewRev < s.rowRev and s.viewRev < s.markRev and s.markRev == s.rowRev)

  // a run of the sequence that exercises the protocol end to end: non-vacuity of the property runs
  val wit_two_installers_finish =
    not(allTerm and s.pc.get(1) == "done" and s.pc.get(2) == "done" and s.rowRev == 3 and s.markRev == 3)
  val wit_lagging_mark_not_lowered =
    not(s.pc.get(1) == "done" and s.tRow.get(1) >= 0 and s.markRev > s.nRev.get(1) and s.rowRev > s.nRev.get(1))
  val wit_step19_race = not(s.tDel.get(1) >= 0 and s.tParts.get(2) >= 0 and s.tParts.get(2) < s.tDel.get(1))
}
