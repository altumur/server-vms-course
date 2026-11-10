// C7: "one name at a time" is a condition of the window, nothing enforces it.
// Anchors (slice ff32d483):
//   23:264   step 5: read the full confirmed catalogue, substitute the candidate, load_catalogue; before any write
//   23:350   "The installation profile admits a simultaneous change of only one manifest name ... This is a condition of the window"
//   21:1190  the catalogue: for any A and B the name of B does not coincide with a table of A; a refusal of one is a refusal of the catalogue
//   23:216   start: load_catalogue refused -> no start, code 2 (no restart)
//   cl:41    guard: a row version guard exists in the store protocol (the control "window row")
// Two installers of different names: a changes its manifest to a new revision a2 that adds a table named "b"; b installs subsystem b.
// The conflict is the table of a2 named as b. Other cases of 21:1190 reduce to the same two-reader shape.
// WINDOW: the operator honours the sequential window (the text's assumption); not modelled how.
// REVALIDATE: control — re-read the catalogue after the row is written and report.
// LOCK: control — a guard row held during the whole put (the "window row" of frozen C7); CRASH can leave it behind.
module cat_core {
  const WINDOW: bool
  const REVALIDATE: bool
  const LOCK: bool
  const CRASH: bool

  var cat: Set[str]
  var pc: str -> str
  var seen: str -> Set[str]
  var lock: str             // "" or a holder
  var reported: Set[str]    // who exited with a refusal
  var readerOut: str        // "" | "code2" | "ok"
  var tWrite: str -> int
  var seq: int

  val I = Set("a", "b")
  pure def other(i: str): str = if (i == "a") "b" else "a"
  pure def cand(i: str): str = if (i == "a") "a2" else "b"
  pure def bad(c: Set[str]): bool = c.contains("a2") and c.contains("b")
  pure def term(p: str): bool = p == "done" or p == "dead" or p == "refused"
  pure def withCand(c: Set[str], i: str): Set[str] =
    if (i == "a") c.exclude(Set("a")).union(Set("a2")) else c.union(Set("b"))

  action init = all {
    cat' = Set("a"),
    pc' = I.mapBy(_ => "start"),
    seen' = I.mapBy(_ => Set()),
    lock' = "",
    reported' = Set(),
    readerOut' = "",
    tWrite' = I.mapBy(_ => -1),
    seq' = 0,
  }

  action keep = all { cat' = cat, lock' = lock, reported' = reported, readerOut' = readerOut, tWrite' = tWrite, seq' = seq + 1 }

  // Steps 5-14a: the check on the catalogue read now. The window, when honoured, is a precondition.
  action checkCat(i: str): bool = all {
    pc.get(i) == "start",
    not(WINDOW) or term(pc.get(other(i))) or pc.get(other(i)) == "start",
    LOCK implies (lock == ""),
    seen' = seen.set(i, cat),
    pc' = pc.set(i, if (bad(withCand(cat, i))) "refused" else "write"),
    lock' = if (LOCK and not(bad(withCand(cat, i)))) i else lock,
    reported' = if (bad(withCand(cat, i))) reported.union(Set(i)) else reported,
    cat' = cat, readerOut' = readerOut, tWrite' = tWrite, seq' = seq + 1,
  }

  // Step 16 of this name (the row: the steps 15, 17, 18 are not observed here).
  action writeRow(i: str): bool = all {
    pc.get(i) == "write",
    cat' = withCand(cat, i),
    pc' = pc.set(i, if (REVALIDATE) "recheck" else "done"),
    lock' = if (LOCK and not(REVALIDATE)) "" else lock,
    tWrite' = tWrite.set(i, seq),
    seen' = seen, reported' = reported, readerOut' = readerOut, seq' = seq + 1,
  }

  // Control: a second reading after the write; a confirmed conflict is a refusal with a visible code.
  action recheck(i: str): bool = all {
    pc.get(i) == "recheck",
    val refuse = bad(cat)
    all {
      pc' = pc.set(i, if (refuse) "refused" else "done"),
      reported' = if (refuse) reported.union(Set(i)) else reported,
      lock' = if (LOCK) "" else lock,
      cat' = cat, seen' = seen, readerOut' = readerOut, tWrite' = tWrite, seq' = seq + 1,
    }
  }

  action crash(i: str): bool = all {
    CRASH, i == "a", not(term(pc.get(i))),
    pc' = pc.set(i, "dead"),
    // the lock row stays with the dead holder: nothing in the text releases it (a parameter of the control)
    lock' = lock, cat' = cat, seen' = seen, reported' = reported, readerOut' = readerOut, tWrite' = tWrite, seq' = seq + 1,
  }

  // A process that needs the whole catalogue (23:208, 23:216).
  action reader = all {
    readerOut == "",
    readerOut' = if (bad(cat)) "code2" else "ok",
    cat' = cat, pc' = pc, seen' = seen, lock' = lock, reported' = reported, tWrite' = tWrite, seq' = seq + 1,
  }

  def allTerm: bool = I.forall(i => term(pc.get(i)))
  action stutter = all { allTerm, readerOut != "", cat' = cat, pc' = pc, seen' = seen, lock' = lock, reported' = reported, readerOut' = readerOut, tWrite' = tWrite, seq' = seq }

  action step = {
    nondet i = oneOf(I)
    any { checkCat(i), writeRow(i), recheck(i), crash(i), reader, stutter }
  }

  val inv_catalogue_valid = not(bad(cat))
  val wit_both_checked_clean =
    not(bad(cat) and seen.get("a").contains("b") == false and seen.get("b").contains("a2") == false
        and tWrite.get("a") >= 0 and tWrite.get("b") >= 0)
  val wit_reader_code2 = not(readerOut == "code2" and bad(cat))
  val inv_bad_reported = not(allTerm and bad(cat)) or size(reported) > 0
  val wit_all_ok_no_report = not(allTerm and size(reported) == 0 and bad(cat))
  val wit_lock_stuck = not(pc.get("a") == "dead" and lock == "a" and pc.get("b") == "start")
  val inv_no_bad_writes_with_lock = not(bad(cat))
  val wit_second_refused = not(pc.get("a") == "refused" or pc.get("b") == "refused")
  val wit_both_write_clean = not(allTerm and pc.get("a") == "done" and pc.get("b") == "done")
}
