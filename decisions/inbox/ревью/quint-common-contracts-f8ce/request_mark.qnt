// Model of Platform/common/contracts/request-mark.md (pin f8ce0f52), section «States of an executed request and its mark»:
// one rid, two holders and the reaper. Time is abstracted to the monotonic flags termExpired and timedOut.
module request_mark {
  const MUT_CALL_WITHOUT_MARK: bool
  const MUT_REAPER_BLIND: bool
  pure val HOLDERS: Set[str] = Set("H1", "H2")
  pure val FINAL: Set[str] = Set("performed", "refused", "unknown", "expired")
  type S = { row: bool, mark: str, began: str, late: bool, called: Set[str], pending: Set[str], calls: int, termExpired: bool, timedOut: bool, sawPerformed: bool, lifes: int }
  var s: S
  action init = s' = { row: false, mark: "none", began: "", late: false, called: Set(), pending: Set(), calls: 0, termExpired: false, timedOut: false, sawPerformed: false, lifes: 0 }

  action file = all { not(s.row), s.mark == "none", s.lifes < 2, s' = s.with("row", true).with("termExpired", false).with("timedOut", false) }
  action expire = all { s.row, not(s.termExpired), s' = s.with("termExpired", true) }
  action timeout = all { s.mark == "begun", not(s.timedOut), s' = s.with("timedOut", true) }
  action begin(h: str): bool = all { s.row, s.mark == "none", not(s.termExpired), s' = s.with("mark", "begun").with("began", h) }
  action noBegun(h: str): bool = all { s.row, s.mark == "none", s.termExpired, s' = s.with("mark", "expired") }
  action call(h: str): bool = all {
    not(s.called.contains(h)),
    or { s.began == h, and { MUT_CALL_WITHOUT_MARK, s.row, s.mark == "none" } },
    s' = s.with("called", s.called.union(Set(h))).with("calls", s.calls + 1).with("pending", s.pending.union(Set(h)))
  }
  action answer(h: str): bool = all {
    s.pending.contains(h), s.began == h, or { s.mark == "begun", s.mark == "unknown" },
    s' = s.with("late", s.mark == "unknown").with("mark", "performed").with("sawPerformed", true).with("pending", s.pending.exclude(Set(h)))
  }
  action foreignUnknown(h: str): bool = all { s.mark == "begun", s.began != h, s.timedOut, s' = s.with("mark", "unknown") }
  action reaperUnknown = all { or { s.mark == "begun", and { MUT_REAPER_BLIND, s.mark == "performed" } }, s.timedOut, s' = s.with("mark", "unknown") }
  action reaperExpired = all { s.row, s.mark == "none", s.termExpired, s' = s.with("mark", "expired") }
  action clear = all { s.row, FINAL.contains(s.mark), s' = s.with("row", false) }
  action cleanup = all {
    not(s.row), FINAL.contains(s.mark),
    s' = s.with("mark", "none").with("began", "").with("late", false).with("called", Set()).with("pending", Set()).with("calls", 0).with("sawPerformed", false).with("lifes", s.lifes + 1)
  }
  action step = any {
    file, expire, timeout, reaperUnknown, reaperExpired, clear, cleanup,
    nondet h = oneOf(HOLDERS) any { begin(h), noBegun(h), call(h), answer(h), foreignUnknown(h) },
  }

  val atMostOneCall: bool = s.calls <= 1
  val performedStays: bool = not(s.sawPerformed) or s.mark == "performed"
  val expiredNoCall: bool = s.mark != "expired" or s.calls == 0
  val noLate: bool = not(s.late)
  val noUnknown: bool = s.mark != "unknown"
}
module rm_ok { import request_mark(MUT_CALL_WITHOUT_MARK = false, MUT_REAPER_BLIND = false).* }
module rm_mut_nomark { import request_mark(MUT_CALL_WITHOUT_MARK = true, MUT_REAPER_BLIND = false).* }
module rm_mut_blind { import request_mark(MUT_CALL_WITHOUT_MARK = false, MUT_REAPER_BLIND = true).* }
