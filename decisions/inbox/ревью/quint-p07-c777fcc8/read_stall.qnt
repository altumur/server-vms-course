// C2 (own reads without a deadline, a truncated body), M3 (ready, busy).
// Anchors: nr:49 order; nr:99-100 the deadline of api is written only for api; nr:111; nr:328 complete-attempt timeout is a debt for api; nr:95 ready waits; nr:146, nr:148 busy, repaintTree;
//   nr:74 profile unknown; cm:248 busy; loc:186 noConsole.
// One cycle of K reads in order. A step answers, hangs, or returns a damaged body (truncated, or HTML with 200).
// DEADLINE: a term on each read (-1 = the text). PARSE: empty_ok = a damaged body is taken as an empty list (a permitted reading: the text has no rule for own reads);
// refuse = a refusal of the read, the previous data stay (proposal C2). MARK: a visible "stale" mark (proposal C2 and M3; the text has none for own reads).
module stall_core {
  const K: int
  const DEADLINE: int
  const PARSE: str
  const MARK: bool
  const MANIFEST_UP: bool
  const MAXT: int
  const LIM: int

  type S = {step: int, t: int, waitSince: int, hung: bool, cycles: int, data: str, mark: str, failedCycle: bool, ready: bool, busy: bool, dataVer: int, cardVer: int}
  var s: S
  action init = s' = {step: 0, t: 0, waitSince: 0, hung: false, cycles: 0, data: "rows", mark: "ok", failedCycle: false, ready: false, busy: false, dataVer: 0, cardVer: 0}

  action ansOk = all {
    not(s.hung), s.step < K, s.cycles < 3,
    s' = s.with("step", s.step + 1).with("ready", s.ready or MANIFEST_UP).with("t", s.t + 1)
         .with("dataVer", s.dataVer + 1).with("cardVer", if (s.busy) s.cardVer else s.dataVer + 1)
  }
  action damaged = all {
    not(s.hung), s.step < K, s.cycles < 3,
    if (PARSE == "empty_ok")
      s' = s.with("step", s.step + 1).with("data", "empty").with("t", s.t + 1)
    else
      s' = s.with("step", s.step + 1).with("failedCycle", true).with("mark", if (MARK) "stale" else s.mark).with("t", s.t + 1)
  }
  action hang = all { not(s.hung), s.step < K, s.cycles < 3, s' = s.with("hung", true).with("waitSince", s.t) }
  action wait1 = all { s.hung, DEADLINE < 0 or s.t - s.waitSince < DEADLINE, s.t < MAXT, s' = s.with("t", s.t + 1) }
  action timeout = all {
    s.hung, DEADLINE >= 0, s.t - s.waitSince >= DEADLINE,
    s' = s.with("hung", false).with("step", s.step + 1).with("failedCycle", true).with("mark", if (MARK) "stale" else s.mark)
  }
  action cycleEnd = all {
    not(s.hung), s.step == K, s.cycles < 3,
    s' = s.with("step", 0).with("cycles", s.cycles + 1).with("failedCycle", false)
  }
  action setBusy = all { not(s.busy), s' = s.with("busy", true) }
  action stutter = s' = s
  action step = any { ansOk, damaged, hang, wait1, timeout, cycleEnd, setBusy, stutter }

  val inv_no_empty_on_damage = s.data != "empty"
  val inv_wait_bounded = s.hung implies (s.t - s.waitSince <= LIM)
  val inv_mark_honest = (s.failedCycle and s.step == K) implies s.mark == "stale"
  val wit_ready_pending = not(s.cycles >= 2 and not(s.ready))
  val wit_busy_card_behind = not(s.busy and s.cardVer + 2 <= s.dataVer)
}
