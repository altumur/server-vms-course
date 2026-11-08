// -*- mode: Bluespec; -*-
// Reseal at start (06.2:202-215) against a concurrent operator edit and a second console.
// Anchors: 06.2:202-213 (the walk, cas by the one read, do not change revision), 06.2:215 (races: two consoles, an operator edit), life:27 (start order), life:91 (readiness).
// Abstraction: one row with a secret field; consoles C1,C2; operator edit raises the row's index and content; kid old/new.
// NOT modelled: the listing and its failure (the norm does not describe it, finding S12), the time of a pass, the link of the pass end to readiness (the norm names none; life:91).
module reseal {
  pure val MUT = "no_cas"  // @override none | no_cas
  pure val EDITS_MAX = 1    // @override
  type Proc = str
  pure val CONSOLES = Set("C1", "C2")
  type St = { rowIdx: int, kid: str, editValue: int, editsDone: int, read: Proc -> int, phase: Proc -> str, editLost: bool }
  var s: St

  action init = s' = {
    rowIdx: 1, kid: "old", editValue: 0, editsDone: 0,
    read: CONSOLES.mapBy(c => 0), phase: CONSOLES.mapBy(c => "Start"), editLost: false,
  }

  action readRow(c: Proc): bool = all {
    s.phase.get(c) == "Start",
    s' = {...s, read: s.read.set(c, s.rowIdx), phase: s.phase.set(c, "Read")},
  }

  action writeSeal(c: Proc): bool = all {
    s.phase.get(c) == "Read",
    if (s.kid == "new" and s.rowIdx == s.read.get(c)) // a row already under the current kid: nothing to write
      s' = {...s, phase: s.phase.set(c, "Done")}
    else if (s.rowIdx == s.read.get(c) or MUT == "no_cas")
      s' = {...s,
        rowIdx: s.rowIdx + 1, kid: "new",
        editLost: s.editLost or (MUT == "no_cas" and s.rowIdx != s.read.get(c) and s.editValue != 0),
        phase: s.phase.set(c, "Done")}
    else
      // conflict: the loser re-reads
      s' = {...s, phase: s.phase.set(c, "Start")},
  }

  // an operator edit writes the secret under the current kid by cas of the read row
  action edit = all {
    s.editsDone < EDITS_MAX,
    s' = {...s, rowIdx: s.rowIdx + 1, editValue: 1, kid: "new", editsDone: s.editsDone + 1},
  }

  action idle = s' = s

  action step = any {
    idle,
    nondet c = oneOf(CONSOLES) any { readRow(c), writeSeal(c) },
    edit,
  }

  val noEditLost = not(s.editLost)
  val w_done = not(CONSOLES.forall(c => s.phase.get(c) == "Done") and s.kid == "new")
  val w_edit_and_seal = not(s.editsDone == 1 and CONSOLES.exists(c => s.phase.get(c) == "Done") and s.editValue == 1)
  val c_false = s.rowIdx < 0
}
