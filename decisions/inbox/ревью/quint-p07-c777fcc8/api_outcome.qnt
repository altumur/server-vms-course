// C7 (form of the unknown outcome, feasibility of "a read first"), M6 (key at PUT, description against norm).
// Anchors: nr:98 throw {status, body, retry}; nr:107 no other headers; nr:116 "on an unknown outcome — a read first"; nr:282; nr:306;
//   cm:96 "POST and PUT carry a new Idempotency-Key"; 06.1:690 optional key at PUT; 06.1:700 key; 06.4:282 POST /marks.
// The door: DOOR = "put" (a row value with revision) or "marks" (append, no identity). LATE: the server may apply the request after the client
// gave up (the browser cannot withdraw a delivered request; the text gives no bound: a parameter, both values are run).
// RULE: what the client concludes from the read. The text does not say what is read and what is returned, so each is a reading:
//   rev_moved: revision moved -> applied, else not_applied;
//   value_eq: the row holds my value (marks: my note found) -> applied, else not_applied;
//   positive_only: value_eq -> applied, else unknown;
//   unknown: never concludes anything.
// FOREIGN: another writer may write once; FOREIGN_SAME: it may write the same value as mine (marks: the same note).
module api_core {
  const DOOR: str
  const IFMATCH: bool
  const KEY: bool
  const LATE: bool
  const RULE: str
  const FOREIGN: bool
  const FOREIGN_SAME: bool

  type S = {phase: str, reqLive: bool, ans: str, rowVal: int, rev: int, callRev: int, marks: int, effects: int, report: str,
            foreignDone: bool, repeats: int, readDone: bool}
  var s: S

  action init = s' = {phase: "idle", reqLive: false, ans: "", rowVal: 0, rev: 1, callRev: 1, marks: 0, effects: 0, report: "none",
    foreignDone: false, repeats: 0, readDone: false}

  action send = all { s.phase == "idle", s' = s.with("phase", "sent").with("reqLive", true) }

  def casOk: bool = not(IFMATCH) or s.rev == s.callRev

  action apply = all {
    s.reqLive,
    if (DOOR == "marks")
      s' = s.with("reqLive", false).with("marks", s.marks + 1).with("effects", s.effects + 1).with("ans", "ok")
    else if (casOk)
      s' = s.with("reqLive", false).with("rowVal", 1).with("rev", s.rev + 1).with("effects", s.effects + 1).with("ans", "ok")
    else
      s' = s.with("reqLive", false).with("ans", "412")
  }

  action deliverAns = all {
    s.phase == "sent", s.ans != "",
    s' = s.with("phase", "reported").with("report", if (s.ans == "ok") "applied" else "refused412")
  }

  action lose = all {
    s.phase == "sent", s.ans == "" or s.ans == "ok",
    s' = s.with("phase", "unknown").with("reqLive", if (LATE) s.reqLive else false)
  }

  action foreignWrite = all {
    FOREIGN, not(s.foreignDone),
    nondet v = (if (FOREIGN_SAME) Set(1, 2) else Set(2)).oneOf()
    s' = if (DOOR == "marks") s.with("foreignDone", true).with("marks", s.marks + 1)
         else s.with("foreignDone", true).with("rowVal", v).with("rev", s.rev + 1)
  }

  def sawMine: bool = if (DOOR == "marks") s.marks > 0 else s.rowVal == 1

  action readFirst = all {
    s.phase == "unknown",
    val r =
      if (RULE == "rev_moved") (if (s.rev != s.callRev) "applied" else "not_applied")
      else if (RULE == "value_eq") (if (sawMine) "applied" else "not_applied")
      else if (RULE == "positive_only") (if (sawMine) "applied" else "unknown")
      else "unknown"
    s' = s.with("phase", "reported").with("report", r).with("readDone", true)
  }

  action humanRepeat = all {
    s.phase == "reported", s.report != "applied", s.report != "refused412", s.repeats < 1,
    if (DOOR == "marks")
      s' = s.with("repeats", s.repeats + 1).with("marks", s.marks + 1).with("effects", s.effects + 1).with("report", "applied")
    else if (KEY)
      // the same key: the memory of the door answers (06.1); an unfinished request of this key -> 409 in flight, still unknown
      s' = if (s.effects >= 1) s.with("repeats", s.repeats + 1).with("report", "applied")
           else if (s.reqLive) s.with("repeats", s.repeats + 1).with("report", "unknown")
           else s.with("repeats", s.repeats + 1).with("rowVal", 1).with("rev", s.rev + 1).with("effects", s.effects + 1).with("report", "applied")
    else if (casOk)
      s' = s.with("repeats", s.repeats + 1).with("rowVal", 1).with("rev", s.rev + 1).with("effects", s.effects + 1).with("report", "applied")
    else
      s' = s.with("repeats", s.repeats + 1).with("report", "conflict")
  }

  action stutter = s' = s
  action step = any { send, apply, deliverAns, lose, foreignWrite, readFirst, humanRepeat, stutter }

  val inv_no_false_applied = s.report == "applied" implies s.effects >= 1
  val inv_no_false_not_applied = s.report == "not_applied" implies s.effects == 0
  val inv_one_effect = s.effects <= 1
  val wit_late_after_read = not(s.report == "not_applied" and s.effects == 1 and s.readDone)
  val wit_own_412 = not(s.report == "conflict" and s.effects >= 1 and not(s.foreignDone))
  val wit_unknown_while_applied = not(s.readDone and s.report == "unknown" and s.effects == 1)
  val wit_conflict_is_foreign = not(s.report == "conflict" and s.foreignDone)
}
