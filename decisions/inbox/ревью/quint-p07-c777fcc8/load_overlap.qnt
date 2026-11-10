// C3 (overlapping loads, an old answer over a new one), link to C2 (a hung read) and the C3 proposal.
// Anchors (slice c777fcc8): nr:50 polling every poll_s; nr:57 "the same load `order` at once"; nr:58 no compare of revision;
//   nr:303, nr:304 the proofs named by N5: order and load on a message, nothing about overlap.
// One row (or a list of rows) with a serial of server changes. A load cycle reads at some moment and its answer comes later;
// nothing in the text orders the cycles or the application of answers.
// POLICY: free = what the text says (no prohibition, applies on arrival); latest = apply only the last started (third clause
// of the proposal alone); revguard = apply only if row revision is not lower (an alternative; an absent row has no revision);
// single = at most one load, a request during a load merges into one later (first two clauses); single_nomerge = mutant, drops it.
// HANG: the answer of a started load never comes (the text gives no deadline to own reads, C2). DEADLINE ends it (cancelled
// answers are never applied: an assumption). REARM: a cancelled load asks for a reload.
// NC cycles and NW writes are bounds of the model, not limits of the module.
module load_core {
  const POLICY: str
  const NC: int
  const NW: int
  const HANG: bool
  const DEADLINE: bool
  const REARM: bool
  const DEL: bool

  type S = {sv: int, live: bool, n: int, st: int -> str, snapSeq: int -> int, snapLive: int -> bool, inflight: int,
            hungN: int, doneN: int, droppedN: int, shownSeq: int, shownLive: bool, dirty: bool, pendingMerge: bool,
            rolledBack: bool, maxInflight: int, startsAfterHang: int, hungEver: bool}
  var s: S
  val C = 0.to(NC - 1)
  val merging = POLICY == "single" or POLICY == "single_nomerge"

  action init = s' = {sv: 0, live: true, n: 0, st: C.mapBy(_ => "idle"), snapSeq: C.mapBy(_ => 0), snapLive: C.mapBy(_ => true),
    inflight: 0, hungN: 0, doneN: 0, droppedN: 0, shownSeq: 0, shownLive: true, dirty: false, pendingMerge: false,
    rolledBack: false, maxInflight: 0, startsAfterHang: 0, hungEver: false}

  action write = all {
    s.sv < NW,
    val ns = s.sv + 1
    s' = s.with("sv", ns).with("live", not(DEL and ns == NW)).with("dirty", true)
  }

  action startNew(clear: bool): bool = all {
    s.n < NC,
    not(merging) or s.inflight == 0,
    val c = s.n
    val ni = s.inflight + 1
    s' = s.with("n", c + 1).with("st", s.st.set(c, "started")).with("inflight", ni)
      .with("maxInflight", if (ni > s.maxInflight) ni else s.maxInflight)
      .with("pendingMerge", false).with("dirty", if (clear) false else s.dirty)
      .with("startsAfterHang", if (s.hungEver) s.startsAfterHang + 1 else s.startsAfterHang)
  }

  action merge(clear: bool): bool = all {
    merging, s.inflight >= 1,
    s' = s.with("pendingMerge", POLICY == "single" or s.pendingMerge).with("dirty", if (clear) false else s.dirty)
  }

  action poll = any { startNew(false), merge(false) }
  action deliver = all { s.dirty, any { startNew(true), merge(true) } }

  action read(c: int): bool = all {
    s.st.get(c) == "started",
    s' = s.with("st", s.st.set(c, "read")).with("snapSeq", s.snapSeq.set(c, s.sv)).with("snapLive", s.snapLive.set(c, s.live))
  }

  def applies(c: int): bool =
    if (POLICY == "latest") c == s.n - 1
    else if (POLICY == "revguard") (not(s.snapLive.get(c)) or not(s.shownLive) or s.snapSeq.get(c) >= s.shownSeq)
    else true

  action answer(c: int): bool = all {
    s.st.get(c) == "read",
    val ok = applies(c)
    val q = s.snapSeq.get(c)
    s' = s.with("st", s.st.set(c, "done")).with("inflight", s.inflight - 1).with("doneN", s.doneN + 1)
      .with("droppedN", if (ok) s.droppedN else s.droppedN + 1)
      .with("shownSeq", if (ok) q else s.shownSeq)
      .with("shownLive", if (ok) s.snapLive.get(c) else s.shownLive)
      .with("rolledBack", s.rolledBack or (ok and q < s.shownSeq))
  }

  action hang(c: int): bool = all {
    HANG, s.st.get(c) == "started",
    s' = s.with("st", s.st.set(c, "hung")).with("hungN", s.hungN + 1).with("hungEver", true)
  }

  action cancel(c: int): bool = all {
    DEADLINE, s.st.get(c) == "hung",
    s' = s.with("st", s.st.set(c, "cancelled")).with("hungN", s.hungN - 1).with("inflight", s.inflight - 1)
      .with("dirty", if (REARM) true else s.dirty)
  }

  action stutter = s' = s

  action step = any {
    write, poll, deliver,
    { nondet c = C.oneOf() read(c) },
    { nondet c = C.oneOf() answer(c) },
    { nondet c = C.oneOf() hang(c) },
    { nondet c = C.oneOf() cancel(c) },
    stutter,
  }

  val quiescent = not(s.dirty) and s.inflight == 0 and not(s.pendingMerge) and s.hungN == 0
  val inv_no_rollback = not(s.rolledBack)
  val inv_inflight_le1 = s.maxInflight <= 1
  val inv_quiescent_fresh = quiescent implies (s.shownSeq == s.sv and s.shownLive == s.live)
  val inv_no_start_after_hang = s.startsAfterHang == 0
  val wit_rollback_quiescent = not(s.rolledBack and quiescent and s.shownSeq < s.sv)
  val wit_heal = not(s.rolledBack and quiescent and s.shownSeq == s.sv and s.shownLive == s.live)
  val wit_inflight_all = not(s.inflight == NC)
  val wit_latest_starves = not(s.droppedN >= NC - 1 and s.shownSeq == 0 and s.sv >= 1)
  val wit_stuck_after_hang = not(s.hungN >= 1 and s.inflight == s.hungN and s.pendingMerge and s.sv > s.shownSeq)
  val wit_free_continues_after_hang = not(s.startsAfterHang >= 1 and s.hungN >= 1)
  val wit_hung_grow = not(s.hungN >= 2)
  val wit_fresh_after_write = not(quiescent and s.sv >= 1 and s.shownSeq == s.sv)
  val wit_deletion_rollback = not(s.rolledBack and not(s.live) and s.shownLive)
}
