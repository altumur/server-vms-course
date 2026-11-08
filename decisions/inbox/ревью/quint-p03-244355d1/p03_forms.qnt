// P/03: формы-машины contender-writer и token-cache, перенесённые как есть
// (forms/contender-writer.machine.yaml, forms/token-cache.machine.yaml, срез 244355d1).
// Семантика строки transitions: forms/README.md:114,125-127 — строки по порядку;
// строка с `to` завершает событие, строка без `to` выполняется и разбор продолжается
// (так читается choose-refused-first; подтверждается трассами: строки io трасс).
// Числа времени — входы: wall (секунды) и day; форма сама часы не читает (README:119-120).
// MUT_FORM != "none" — мутанты для проверки того, что трассы их ловят.
module p03_forms {
  const MUT_FORM: str

  type Io = { name: str, strs: List[str], nums: List[int] }

  pure def ioS(name: str, s: str): Io = { name: name, strs: [s], nums: [] }
  pure def ioN(name: str, n: int): Io = { name: name, strs: [], nums: [n] }
  pure val ioW: Io = { name: "wait", strs: [], nums: [] }

  // ---- contender-writer ----
  type Cw = { st: str, ever: bool, lostEp: bool, phase: str, since: int }
  type CwR = { s: Cw, io: List[Io] }

  pure val cw0: Cw = { st: "seeking", ever: false, lostEp: false, phase: "", since: 0 }

  pure def cwChoose(s: Cw, foreign: bool, wall: int): Cw =
    val sel = if (foreign) "refused" else if (s.ever) "nameless" else "waiting"
    val newSince = if (MUT_FORM == "since_reset") wall else if (s.phase == sel) s.since else wall
    { ...s, since: newSince, phase: sel }

  pure def cwObserve(s: Cw, withdrawn: bool, foreign: bool, due: bool, wall: int): CwR =
    if (s.st != "seeking" and s.st != "quiet") { s: s, io: [] }
    else if (withdrawn) { s: { ...s, phase: "", st: "quiet" }, io: [] }
    else {
      val s1 = cwChoose(s, foreign, wall)
      if (due)
        { s: { ...s1, st: "seeking" },
          io: [{ name: "publish", strs: [s1.phase], nums: [s1.since, wall] }] }
      else { s: { ...s1, st: "seeking" }, io: [] }
    }

  pure def cwAcquired(s: Cw): CwR =
    if (s.st != "seeking") { s: s, io: [] }
    else if (s.lostEp and MUT_FORM != "no_back_after_loss")
      { s: { ...s, ever: true, lostEp: false, phase: "", st: "holding" },
        io: [{ name: "name_back", strs: [], nums: [] }] }
    else { s: { ...s, ever: true, lostEp: false, phase: "", st: "holding" }, io: [] }

  pure def cwLost(s: Cw): CwR =
    if (s.st != "holding") { s: s, io: [] }
    else { s: { ...s, lostEp: true, phase: "", st: "seeking" },
           io: [{ name: "name_taken", strs: [], nums: [] }] }

  // ---- token-cache ----
  type Tc = { st: str, curH: str, curJ: str, candH: str, candJ: str, revoked: str, usable: bool, blocked: int }
  type TcR = { s: Tc, io: List[Io] }

  pure val tc0: Tc = { st: "loading", curH: "", curJ: "", candH: "", candJ: "", revoked: "", usable: false, blocked: -1 }

  pure def tcReject(s: Tc, word: str): Tc =
    { ...s, usable: false, revoked: word, candH: "", candJ: "" }

  pure def tcEvent(s: Tc, kind: str, opened: bool, h: str, j: str, day: int): TcR =
    if (kind == "loaded" and s.st == "loading")
      { s: { ...s, curH: if (opened) h else "", curJ: if (opened) j else "", usable: opened, st: "ready" }, io: [] }
    else if (kind == "demand" and s.st == "ready" and s.usable)
      { s: s, io: [ioS("offer", s.curH)] }
    else if (kind == "demand" and s.st == "ready")
      { s: { ...s, st: "asking" }, io: [ioS("request", s.revoked)] }
    else if (kind == "demand" and s.st == "asking")
      { s: s, io: [ioW] }
    else if (kind == "demand" and s.st == "candidate")
      { s: s, io: [ioS("offer", s.candH)] }
    else if (kind == "demand" and s.st == "cooldown" and day <= s.blocked)
      { s: s, io: [ioW] }
    else if (kind == "demand" and s.st == "cooldown")
      { s: { ...s, st: "asking" }, io: [ioS("request", s.revoked)] }
    else if (kind == "issue_failed" and s.st == "asking")
      { s: { ...s, st: "ready" }, io: [] }
    else if (kind == "issued" and s.st == "asking" and s.revoked != "" and j == s.revoked)
      { s: { ...s, blocked: day, candH: "", candJ: "", st: "cooldown" }, io: [ioN("same_jti_log", day)] }
    else if (kind == "issued" and s.st == "asking")
      { s: { ...s, candH: h, candJ: j, st: "candidate" }, io: [ioS("offer", h)] }
    else if (kind == "accepted" and s.st == "candidate" and h == s.candH)
      { s: { ...s, curH: s.candH, curJ: s.candJ, candH: "", candJ: "", usable: true, revoked: "", st: "ready" },
        io: [ioS("persist", s.candH)] }
    else if (kind == "accepted" and MUT_FORM == "persist_early" and s.st == "ready")
      { s: s, io: [ioS("persist", h)] }
    else if (kind == "unknown_key" and s.st == "ready" and s.usable and h == s.curH)
      { s: s, io: [ioW] }
    else if (kind == "unknown_key" and s.st == "candidate" and h == s.candH)
      { s: s, io: [ioW] }
    else if (kind == "expired" and s.st == "ready" and s.usable and h == s.curH) {
      val r = tcReject(s, "")
      { s: { ...r, st: "asking" }, io: [ioS("request", r.revoked)] }
    }
    else if (kind == "revoked" and s.st == "ready" and s.usable and h == s.curH) {
      val r = tcReject(s, s.curJ)
      { s: { ...r, st: "asking" }, io: [ioS("request", r.revoked)] }
    }
    else if (kind == "expired" and s.st == "candidate" and h == s.candH) {
      val r = tcReject(s, "")
      { s: { ...r, st: "asking" }, io: [ioS("request", r.revoked)] }
    }
    else if (kind == "revoked" and s.st == "candidate" and h == s.candH) {
      val r = tcReject(s, s.candJ)
      { s: { ...r, st: "asking" }, io: [ioS("request", r.revoked)] }
    }
    else { s: s, io: [] }

  // ---- Состояние для трасс и для свойств ----
  var cw: Cw
  var tc: Tc
  var io: List[Io]

  action init = all { cw' = cw0, tc' = tc0, io' = [] }

  action cwObserveA(wd: bool, fr: bool, du: bool, wa: int): bool = {
    val r = cwObserve(cw, wd, fr, du, wa)
    all { cw' = r.s, tc' = tc, io' = r.io }
  }
  action cwAcq: bool = { val r = cwAcquired(cw)  all { cw' = r.s, tc' = tc, io' = r.io } }
  action cwLo: bool = { val r = cwLost(cw)  all { cw' = r.s, tc' = tc, io' = r.io } }
  action tcE(k: str, op: bool, h: str, j: str, d: int): bool = {
    val r = tcEvent(tc, k, op, h, j, d)
    all { tc' = r.s, cw' = cw, io' = r.io }
  }
  action tick: bool = all { cw' = cw, tc' = tc, io' = [] }

  // Свободные шаги для свойств: walls, дни и имена — малые множества
  pure val Walls = Set(90, 100, 110, 120)
  pure val Days = Set(9, 10, 11)
  pure val Hs = Set("a", "b")
  pure val Js = Set("ja", "jb")

  action step = {
    nondet wa = oneOf(Walls)
    nondet d = oneOf(Days)
    nondet h = oneOf(Hs)
    nondet j = oneOf(Js)
    nondet wd = oneOf(Set(true, false))
    nondet fr = oneOf(Set(true, false))
    nondet du = oneOf(Set(true, false))
    nondet op = oneOf(Set(true, false))
    nondet k = oneOf(Set("loaded", "demand", "issued", "issue_failed", "accepted", "unknown_key", "expired", "revoked"))
    any {
      cwObserveA(wd, fr, du, wa),
      cwAcq,
      cwLo,
      tcE(k, op, h, j, d),
    }
  }

  // Инварианты форм (contender-writer.machine.yaml:76-78, token-cache.machine.yaml, блок invariants)
  val ClosedPhase = Set("", "refused", "nameless", "waiting").contains(cw.phase)
  val LossRequiresCapture = not(cw.lostEp) or cw.ever
  val UsableHasIdentity = not(tc.usable) or (tc.curH != "" and tc.curJ != "")
  val CandidateHasIdentity = tc.st != "candidate" or (tc.candH != "" and tc.candJ != "")
  val BlockedDay = tc.blocked >= -1
  val FormsInv = ClosedPhase and LossRequiresCapture and UsableHasIdentity and CandidateHasIdentity and BlockedDay

  // Свидетели
  val W_cooldown = tc.st != "cooldown"
  val W_namelessPublished = not(io.length() > 0 and io[0].name == "publish" and io[0].strs[0] == "nameless")
  val W_refusedAfterLoss = not(cw.lostEp and cw.phase == "refused")
}
