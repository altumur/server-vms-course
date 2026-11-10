// C9 (end-to-end term, ceiling of Retry-After), M5 (the replay horizon is shorter than the takeover of the claim).
// Anchors: nr:111-114 replay rule; the delay Retry-After, without it 2, 3, 5 s, after the third replay throw; 06.1:740 takeover, 409 in flight;
//   rc:32 CLAIM_TAKEOVER_AFTER 30; fwd:278 Q4 end-to-end budget (not bound to P/07).
// One POST whose executor died: the claim is pending, every attempt before TAKEOVER gets the kinds in KINDS. A later attempt takes over and resolves.
// LATS: the seconds an attempt takes (0 for an immediate 409; up to 20 for a network timeout).
// RAS: Retry-After values the answer may carry ({} = no header). CAP: ceiling of the delay (-1 none, the text has none).
// POLICY409: refuse = a 409 after the third replay is thrown as a refusal (text); unknown = reported as unknown outcome (proposal M5).
// BUDGET: a declared end-to-end budget (-1 none, the text has none); at its expiry the action ends unknown.
module budget_core {
  const KINDS: Set[str]
  const LATS: Set[int]
  const RAS: Set[int]
  const CAP: int
  const POLICY409: str
  const BUDGET: int
  const TAKEOVER: int
  const LIM: int

  type S = {t: int, a: int, phase: str, nextAt: int, report: str, lastDelay: int, manual: bool}
  var s: S
  action init = s' = {t: 0, a: 0, phase: "wait", nextAt: -1, report: "none", lastDelay: 0, manual: false}

  def dflt(a: int): int = if (a == 0) 2 else if (a == 1) 3 else 5
  def clip(x: int): int = if (CAP >= 0 and x > CAP) CAP else x
  def delays: Set[int] = if (RAS == Set()) Set(dflt(s.a)) else RAS.map(x => clip(x))

  action respond = all {
    s.phase == "wait",
    nondet lat = LATS.oneOf()
    nondet kind = KINDS.oneOf()
    nondet dly = delays.oneOf()
    val nt = s.t + lat
    if (nt >= TAKEOVER)
      s' = s.with("t", nt).with("phase", "done").with("report", "ok")
    else if (s.a == 3)
      s' = s.with("t", nt).with("phase", "done").with("report", if (kind == "409" and POLICY409 == "refuse") "refused409" else "unknown")
    else if (BUDGET >= 0 and nt + dly > BUDGET)
      s' = s.with("t", nt).with("phase", "done").with("report", "unknown")
    else
      s' = s.with("t", nt).with("phase", "delay").with("nextAt", nt + dly).with("lastDelay", dly)
  }

  action resend = all {
    s.phase == "delay",
    s' = s.with("t", s.nextAt).with("a", s.a + 1).with("phase", "wait")
  }

  action manualRetry = all {
    s.phase == "done", s.report != "ok", not(s.manual),
    nondet dt = Set(1, 40).oneOf()
    val nt = s.t + dt
    s' = s.with("t", nt).with("manual", true).with("report", if (nt >= TAKEOVER) "ok" else s.report)
  }

  action stutter = s' = s
  action step = any { respond, resend, manualRetry, stutter }

  val inv_no_refused409 = s.report != "refused409"
  val inv_total_le_lim = s.t <= LIM
  val inv_never_auto_ok = not(s.report == "ok" and not(s.manual))
  val wit_exhaust_before_takeover = not(s.report == "refused409" and s.t < TAKEOVER)
  val wit_auto_ok = not(s.report == "ok" and not(s.manual))
  val wit_manual_ok = not(s.report == "ok" and s.manual)
  val wit_faster_than_default = not(s.phase == "done" and s.t > 0 and s.t <= 3)
  val wit_huge = not(s.t >= LIM)
  val wit_budget_ends_unknown = not(s.phase == "done" and s.report == "unknown" and s.t < TAKEOVER and not(s.manual))
}
