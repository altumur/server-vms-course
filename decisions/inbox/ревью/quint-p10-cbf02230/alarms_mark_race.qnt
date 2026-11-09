// C8: the alarm door reads the mark `reported`, then the generation it names.
// Anchors (slice cbf02230):
//   10-domain-console.norms.md:415-417  "the mark is read, and the generation reports/<rev> of the mark does not exist
//                                        or it is not with its sha256 - page: garbled (the member is unreadable...)"
//   accept.md:71-74     mark is the boundary; readers take reported.rev and read only that generation;
//                       "a mark without an object ... requires the bounded marker reread below before the member is silent"
//   accept.md:376       cleanup removes generations older than the last two committed; publication order whole, delta, mark;
//                       "cleanup cannot delete the current or previous committed generation"
//   accept.md:378       MB3: reread the marker exactly once; stable + missing -> keep outcome; changed + newly named
//                       generation cannot be read -> 503 unavailable; do not publish from the race, combine, invent, or loop
//   common/vectors/production-obligations/README.md:25   MB3 lists P/10 among its owners
//   accept.md:63,271    REPORT_EVERY 5 s, every 1..3600
// REREAD=false is the text of P/10 alone (norms.md:416 is unconditional); REREAD=true is that text plus accept.md:378
// as the vector README assigns to P/10.
// "unreadable" is what the door concludes for the member; here at most one member (the race is per member).
// Assumptions: the door's reads are sequential (mark, then generation); publication is two steps (object, then mark);
// marks spaced at least EVERY seconds apart; the door's work between the mark read and the generation read
// is bounded by GAP (a model parameter: the door has no deadline of its own, C1).
// Not modelled: the sha256 mismatch path (identical in the model to "missing"; immutability is accept.md:71),
// deltas, several members, the `silent` outcome of accept.md:378 for P/08 readers, resumable-cleanup crashes,
// witness/history reads, a mark that is unreadable (norms.md:410).
module alarmrace_core {
  const MAX: int           // highest generation number
  const KEEP: int          // generations cleanup keeps: 2 = accept.md:376; 1 = mutant
  const REREAD: bool       // accept.md:378 applied
  const NOCMP: bool        // mutant of REREAD: "missing" -> unreadable without comparing markers
  const LOOP: bool         // mutant of REREAD: reread until found
  const MARK_FIRST: bool   // mutant: the mark before the object (accept.md:376 reversed)
  const EVERY: int
  const GAP: int           // the door's own gap budget between its first read and its last
  const FAULT: bool        // the object of the current generation may be genuinely lost
  const DTS: Set[int]

  var now: int
  var seq: int
  var mark: int
  var objs: Set[int]
  var pub: int             // pending publication generation (0 = none)
  var lastMarkAt: int
  var lost: Set[int]       // generations lost by the fault
  var phase: str           // idle | gen1 | reread | gen2 | done
  var m1: int
  var m2: int
  var nReread: int
  var outcome: str         // none | page | unreadable | 503
  var pageGen: int
  var doorAt: int          // time of the first read of the mark
  // ordered stamps for the witness
  var tMark1: int
  var tMiss: int
  var tDoneU: int
  var nMarkAfterRead: int  // marks published after the door's first read
  var tCleanM1: int        // the seq of the cleanup that removed generation m1

  action init = all {
    now' = 0, seq' = 0, mark' = 2, objs' = Set(1, 2), pub' = 0, lastMarkAt' = -1000,
    lost' = Set(), phase' = "idle", m1' = 0, m2' = 0, nReread' = 0, outcome' = "none",
    pageGen' = 0, doorAt' = -1, tMark1' = -1, tMiss' = -1, tDoneU' = -1, nMarkAfterRead' = 0, tCleanM1' = -1,
  }

  // publication step 1: the object (or, in the mutant, the mark)
  action pub1 = all {
    pub == 0, mark < MAX,
    now >= lastMarkAt + EVERY,
    pub' = mark + 1,
    if (MARK_FIRST) all {
      mark' = mark + 1, objs' = objs, lastMarkAt' = now,
      nMarkAfterRead' = if (phase != "idle" and phase != "done") nMarkAfterRead + 1 else nMarkAfterRead,
    } else all {
      objs' = objs.union(Set(mark + 1)), mark' = mark, lastMarkAt' = lastMarkAt, nMarkAfterRead' = nMarkAfterRead,
    },
    seq' = seq + 1,
    now' = now, lost' = lost, phase' = phase, m1' = m1, m2' = m2, nReread' = nReread, outcome' = outcome,
    pageGen' = pageGen, doorAt' = doorAt, tMark1' = tMark1, tMiss' = tMiss, tDoneU' = tDoneU, tCleanM1' = tCleanM1,
  }

  // publication step 2: the mark (or, in the mutant, the object)
  action pub2 = all {
    pub > 0,
    if (MARK_FIRST) all {
      objs' = objs.union(Set(pub)), mark' = mark, lastMarkAt' = lastMarkAt, nMarkAfterRead' = nMarkAfterRead,
    } else all {
      mark' = pub, objs' = objs, lastMarkAt' = now,
      nMarkAfterRead' = if (phase != "idle" and phase != "done") nMarkAfterRead + 1 else nMarkAfterRead,
    },
    pub' = 0,
    seq' = seq + 1,
    now' = now, lost' = lost, phase' = phase, m1' = m1, m2' = m2, nReread' = nReread, outcome' = outcome,
    pageGen' = pageGen, doorAt' = doorAt, tMark1' = tMark1, tMiss' = tMiss, tDoneU' = tDoneU, tCleanM1' = tCleanM1,
  }

  // Cleanup removes one eligible old generation at a time (accept.md:376 resumable).
  action cleanup(g: int): bool = all {
    objs.contains(g),
    g <= mark - KEEP,
    objs' = objs.exclude(Set(g)),
    tCleanM1' = if (phase != "idle" and g == m1) seq else tCleanM1,
    seq' = seq + 1,
    now' = now, mark' = mark, pub' = pub, lastMarkAt' = lastMarkAt, lost' = lost, phase' = phase, m1' = m1, m2' = m2,
    nReread' = nReread, outcome' = outcome, pageGen' = pageGen, doorAt' = doorAt, tMark1' = tMark1, tMiss' = tMiss,
    tDoneU' = tDoneU, nMarkAfterRead' = nMarkAfterRead,
  }

  // A genuine loss of the current generation's object, a negative control of the door's outcome.
  action fault = all {
    FAULT, lost.size() == 0, objs.contains(mark),
    lost' = lost.union(Set(mark)), objs' = objs.exclude(Set(mark)),
    seq' = seq + 1,
    now' = now, mark' = mark, pub' = pub, lastMarkAt' = lastMarkAt, phase' = phase, m1' = m1, m2' = m2,
    nReread' = nReread, outcome' = outcome, pageGen' = pageGen, doorAt' = doorAt, tMark1' = tMark1, tMiss' = tMiss,
    tDoneU' = tDoneU, nMarkAfterRead' = nMarkAfterRead, tCleanM1' = tCleanM1,
  }

  action readMark = all {
    phase == "idle",
    m1' = mark, phase' = "gen1", doorAt' = now, tMark1' = seq, nMarkAfterRead' = 0,
    seq' = seq + 1,
    now' = now, mark' = mark, objs' = objs, pub' = pub, lastMarkAt' = lastMarkAt, lost' = lost, m2' = m2,
    nReread' = nReread, outcome' = outcome, pageGen' = pageGen, tMiss' = tMiss, tDoneU' = tDoneU, tCleanM1' = tCleanM1,
  }

  action readGen1 = all {
    phase == "gen1",
    if (objs.contains(m1)) all {
      phase' = "done", outcome' = "page", pageGen' = m1, tMiss' = tMiss, tDoneU' = tDoneU,
    } else if (REREAD) all {
      phase' = "reread", outcome' = outcome, pageGen' = pageGen, tMiss' = seq, tDoneU' = tDoneU,
    } else all {
      phase' = "done", outcome' = "unreadable", pageGen' = pageGen, tMiss' = seq, tDoneU' = seq,
    },
    seq' = seq + 1,
    now' = now, mark' = mark, objs' = objs, pub' = pub, lastMarkAt' = lastMarkAt, lost' = lost, m1' = m1, m2' = m2,
    nReread' = nReread, doorAt' = doorAt, tMark1' = tMark1, nMarkAfterRead' = nMarkAfterRead, tCleanM1' = tCleanM1,
  }

  action rereadMark = all {
    phase == "reread",
    m2' = mark, nReread' = nReread + 1, phase' = "gen2",
    seq' = seq + 1,
    now' = now, mark' = mark, objs' = objs, pub' = pub, lastMarkAt' = lastMarkAt, lost' = lost, m1' = m1,
    outcome' = outcome, pageGen' = pageGen, doorAt' = doorAt, tMark1' = tMark1, tMiss' = tMiss, tDoneU' = tDoneU,
    nMarkAfterRead' = nMarkAfterRead, tCleanM1' = tCleanM1,
  }

  action readGen2 = all {
    phase == "gen2",
    if (objs.contains(m2)) all {
      phase' = "done", outcome' = "page", pageGen' = m2, tDoneU' = tDoneU, nReread' = nReread,
    } else if (LOOP) all {
      phase' = "reread", outcome' = outcome, pageGen' = pageGen, tDoneU' = tDoneU, nReread' = nReread,
    } else if (NOCMP or m2 == m1) all {
      phase' = "done", outcome' = "unreadable", pageGen' = pageGen, tDoneU' = seq, nReread' = nReread,
    } else all {
      phase' = "done", outcome' = "503", pageGen' = pageGen, tDoneU' = tDoneU, nReread' = nReread,
    },
    seq' = seq + 1,
    now' = now, mark' = mark, objs' = objs, pub' = pub, lastMarkAt' = lastMarkAt, lost' = lost, m1' = m1, m2' = m2,
    doorAt' = doorAt, tMark1' = tMark1, tMiss' = tMiss, nMarkAfterRead' = nMarkAfterRead, tCleanM1' = tCleanM1,
  }

  // Time; the door's gap is bounded by GAP.
  action tick(dt: int): bool = all {
    (phase == "idle" or phase == "done") or now + dt <= doorAt + GAP,
    now' = now + dt, seq' = seq + 1,
    mark' = mark, objs' = objs, pub' = pub, lastMarkAt' = lastMarkAt, lost' = lost, phase' = phase, m1' = m1, m2' = m2,
    nReread' = nReread, outcome' = outcome, pageGen' = pageGen, doorAt' = doorAt, tMark1' = tMark1, tMiss' = tMiss,
    tDoneU' = tDoneU, nMarkAfterRead' = nMarkAfterRead, tCleanM1' = tCleanM1,
  }

  action step = {
    nondet g = oneOf(1.to(MAX))
    nondet dt = oneOf(DTS)
    any { pub1, pub2, cleanup(g), fault, readMark, readGen1, rereadMark, readGen2, tick(dt) }
  }

  // -- invariants --
  val namedGen = if (nReread == 0) m1 else m2
  // The door says unreadable only for a generation that was genuinely lost.
  val inv_no_false_unreadable = outcome == "unreadable" implies lost.contains(namedGen)
  // Reread at most once (accept.md:378).
  val inv_reread_once = nReread <= 1
  // A page is the generation the door named, never a mixture, never above the mark.
  val inv_page_named = outcome == "page" implies (pageGen == namedGen and pageGen <= mark)
  // A marker that moved and whose fresh generation is gone -> never unreadable, may only be 503 or page.
  val inv_changed_never_unreadable =
    (nReread >= 1 and m2 != m1) implies outcome != "unreadable"

  // -- witnesses: violated iff the ordered situation is reachable --
  val wit_false_unreadable_ordered =
    not(outcome == "unreadable" and not(lost.contains(namedGen))
        and tMark1 >= 0 and nMarkAfterRead >= 2 and tCleanM1 > tMark1 and tMiss > tCleanM1 and tDoneU >= tMiss)
  val wit_503_changed_marker =
    not(outcome == "503" and nReread == 1 and m2 != m1)
  val wit_fresh_after_reread =
    not(outcome == "page" and nReread == 1 and pageGen == m2 and m2 != m1)
  val wit_genuine_unreadable =
    not(outcome == "unreadable" and lost.contains(namedGen))
  val wit_page_served = not(outcome == "page")
  val wit_one_mark_in_gap = not(nMarkAfterRead >= 1 and phase != "idle" and phase != "done")
  // With the door's gap below the publication period at most one mark moves inside it.
  val inv_at_most_one_mark_in_gap = nMarkAfterRead <= 1
}

// P/10 text alone, the default every 5 s, door gap GAP=10 (>= EVERY)
module alarmrace_norm {
  import alarmrace_core(MAX=6, KEEP=2, REREAD=false, NOCMP=false, LOOP=false, MARK_FIRST=false,
                        EVERY=5, GAP=10, FAULT=false, DTS=Set(1,5,10)).*
}
// P/10 text alone, the door gap is below the publication period: one mark at most moves in the gap.
module alarmrace_norm_shortgap {
  import alarmrace_core(MAX=6, KEEP=2, REREAD=false, NOCMP=false, LOOP=false, MARK_FIRST=false,
                        EVERY=5, GAP=4, FAULT=false, DTS=Set(1,2,4)).*
}
// P/10 text alone, the smallest every (1 s): the gap needed is small.
module alarmrace_norm_every1 {
  import alarmrace_core(MAX=6, KEEP=2, REREAD=false, NOCMP=false, LOOP=false, MARK_FIRST=false,
                        EVERY=1, GAP=1, FAULT=false, DTS=Set(1)).*
}
// With accept.md:378 applied (control).
module alarmrace_ctrl {
  import alarmrace_core(MAX=6, KEEP=2, REREAD=true, NOCMP=false, LOOP=false, MARK_FIRST=false,
                        EVERY=5, GAP=20, FAULT=true, DTS=Set(1,5,10)).*
}
// Mutant: the cleanup keeps only the current generation (accept.md:376 broken).
module alarmrace_mut_keep1 {
  import alarmrace_core(MAX=6, KEEP=1, REREAD=false, NOCMP=false, LOOP=false, MARK_FIRST=false,
                        EVERY=5, GAP=4, FAULT=false, DTS=Set(1,2,4)).*
}
// Mutant: the reread does not compare the markers.
module alarmrace_mut_nocmp {
  import alarmrace_core(MAX=6, KEEP=2, REREAD=true, NOCMP=true, LOOP=false, MARK_FIRST=false,
                        EVERY=5, GAP=20, FAULT=false, DTS=Set(1,5,10)).*
}
// Mutant: an indefinite reread loop.
module alarmrace_mut_loop {
  import alarmrace_core(MAX=6, KEEP=2, REREAD=true, NOCMP=false, LOOP=true, MARK_FIRST=false,
                        EVERY=5, GAP=20, FAULT=true, DTS=Set(1,5,10)).*
}
// Mutant: the mark published before the object (accept.md:376 reversed).
module alarmrace_mut_markfirst {
  import alarmrace_core(MAX=6, KEEP=2, REREAD=true, NOCMP=false, LOOP=false, MARK_FIRST=true,
                        EVERY=5, GAP=20, FAULT=false, DTS=Set(1,5,10)).*
}
