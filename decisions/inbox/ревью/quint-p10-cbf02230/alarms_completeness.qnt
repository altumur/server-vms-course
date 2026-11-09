// C11: the `complete` flag of GET /domain/alarms and the incompleteness of its assembled input.
// NOT a race: the door's outcome depends on per-member read outcomes, not on their order. Kept
// minimal: it checks the consequence of the formula of N3 step 4 together with the table of P/08.9.
// Anchors (slice cbf02230):
//   10-domain-console.norms.md:407  "discards a broken witness ... with a counter before the call"
//   10-domain-console.norms.md:441  history_cut_before only for a history with cut_before > since
//   10-domain-console.norms.md:442  "complete = all ok" (member states only)
//   08-domain/spec/08.9-domain.norms.md:262  whole unreadable history at domainconsole: "the history lines of this
//       member are not taken, the output is from the page, history_cut_before is not given for the member, log"
//   08-domain/spec/08.1-domain.norms.md:219  "MUST carry its incompleteness as a field"; :222 names P/10 alarms derived observation
// Assumption: UNK = the read of the history object did not confirm (object-client.md:97: the reading is unknown).
// The text names no outcome for it: `unkPolicy`=0 admits either "not taken" or 503 of the whole door; `1` = control "503".
// Not modelled: marks/pages unreadable (the state unreadable is a named incompleteness), witnesses of a member,
// page truncation (`truncated` is a named field), the window, the set of members changing.
module alarmcomp_core {
  const M: Set[int]
  const UNK_POLICY: int     // 0 = silent (either); 1 = control: unknown history read -> 503
  const COMPLETE_ALL: bool  // control: complete also requires histories and witnesses taken

  var phase: int            // members processed
  var histOut: int -> str   // ok | unreadable | unknown | none (history outcome for member)
  var dropped: int -> bool  // a history not taken (no field in the answer says so)
  var witDropped: int       // broken witnesses discarded
  var door503: bool
  var complete: bool
  var done: bool

  action init = all {
    phase' = 0, histOut' = M.mapBy(_ => "none"), dropped' = M.mapBy(_ => false),
    witDropped' = 0, door503' = false, complete' = false, done' = false,
  }

  // One member at a time: the member state is ok (a hypothesis of this module).
  action member(m: int, h: str, u: bool): bool = all {
    not(done), not(door503), histOut.get(m) == "none",
    histOut' = histOut.set(m, h),
    if (h == "ok") all { dropped' = dropped, door503' = door503 }
    else if (h == "unreadable") all { dropped' = dropped.set(m, true), door503' = door503 }
    else if (UNK_POLICY == 1 or u) all { dropped' = dropped, door503' = true }
    else all { dropped' = dropped.set(m, true), door503' = door503 },
    phase' = phase + 1,
    witDropped' = witDropped, complete' = complete, done' = done,
  }

  action dropWitness = all {
    not(done), not(door503), witDropped < 2,
    witDropped' = witDropped + 1,
    phase' = phase, histOut' = histOut, dropped' = dropped, door503' = door503, complete' = complete, done' = done,
  }

  action finish = all {
    not(done), not(door503),
    M.forall(m => histOut.get(m) != "none"),
    done' = true,
    complete' = if (COMPLETE_ALL) (M.forall(m => not(dropped.get(m))) and witDropped == 0) else true,
    phase' = phase, histOut' = histOut, dropped' = dropped, witDropped' = witDropped, door503' = door503,
  }

  action stutter = all {
    done,
    phase' = phase, histOut' = histOut, dropped' = dropped, witDropped' = witDropped,
    door503' = door503, complete' = complete, done' = done,
  }

  action step = {
    nondet m = oneOf(M)
    nondet h = oneOf(Set("ok", "unreadable", "unknown"))
    nondet u = oneOf(Set(true, false))
    any { member(m, h, u), dropWitness, finish, stutter }
  }

  val anyDrop = M.exists(m => dropped.get(m)) or witDropped > 0
  val inv_complete_is_whole = (done and complete) implies not(anyDrop)
  val inv_no_history_drop = (done and complete) implies M.forall(m => not(dropped.get(m)))
  val inv_no_witness_drop = (done and complete) implies witDropped == 0
  val wit_complete_true_reachable = not(done and complete and not(anyDrop))
  val wit_complete_with_unknown_history =
    not(done and complete and M.exists(m => histOut.get(m) == "unknown"))
  val wit_complete_with_unreadable_history =
    not(done and complete and M.exists(m => histOut.get(m) == "unreadable"))
}

module alarmcomp_norm {
  import alarmcomp_core(M=Set(1,2), UNK_POLICY=0, COMPLETE_ALL=false).*
}
// Control: 503 on unknown history read; the named outcomes (unreadable, witness) still drop silently.
module alarmcomp_ctrl_unk503 {
  import alarmcomp_core(M=Set(1,2), UNK_POLICY=1, COMPLETE_ALL=false).*
}
// Control: complete also accounts for what the door dropped.
module alarmcomp_ctrl_field {
  import alarmcomp_core(M=Set(1,2), UNK_POLICY=0, COMPLETE_ALL=true).*
}
