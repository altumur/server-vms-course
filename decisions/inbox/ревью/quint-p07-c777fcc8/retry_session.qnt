// C8 (the replay crosses the session and page boundary); the C8 proposal.
// Anchors: nr:111 snapshot and same key; nr:115 401 the login window; nr:138 another user - the page resets its own; nr:306; cm:190 Retry at a toast;
//   06.1:690 key (user, method, path, key); rc:33 DONE_ANSWER_KEEP; 06.3:191 cookies; 06.5:292 busy.
// One logical action of user A: a POST /<rows> with the snapshot body of A, already sent once, the answer lost; the first attempt may or may not have applied.
// cookie = the real session in the browser (shared between tabs when SHARED); seen = the user this tab learned from its last read of /session.
// The request goes with the cookie of the moment; the module does not name a user on the wire.
// POLICY: norm = what the text says (no rule for the module's replays); cancel_seen = proposal "cancel at a change of user" as known to the tab;
//   recheck = read /session just before the send (not atomic with the send); bound = hypothetical server condition: the replay carries the expected
//   user and is refused otherwise (no such door form in the text; a control only).
// CANCEL_TOAST: cancel_seen also removes the toast Retry. AGE_LIMIT: no Retry after the done-answer memory expired. IDKIND: named (409 exists) or numeric (a new number).
// KEEP_EXP: the done-answer memory may expire (DONE_ANSWER_KEEP is a minimum). Reload loses the tab's snapshot and key.
module session_core {
  const POLICY: str
  const SHARED: bool
  const CANCEL_TOAST: bool
  const AGE_LIMIT: bool
  const IDKIND: str
  const KEEP_EXP: bool
  const RELOAD: bool

  type S = {cookie: str, seen: str, st: str, replays: int, rows: int, rowBy: str, mem: str -> bool, memExpired: bool, cross: bool, checked: str, sends: int}
  var s: S

  action init = {
    nondet applied = Set(true, false).oneOf()
    s' = {cookie: "A", seen: "A", st: "delay", replays: 3, rows: if (applied) 1 else 0, rowBy: if (applied) "A" else "",
          mem: Map("A" -> applied, "B" -> false), memExpired: false, cross: false, checked: "", sends: 0}
  }

  def sendable: bool = (s.st == "delay" or s.st == "toast") and (POLICY != "recheck" or s.checked == "A")

  action recheck = all { POLICY == "recheck", s.st == "delay" or s.st == "toast", s' = s.with("checked", s.cookie) }

  // one send, by the cookie of this moment
  action send = all {
    sendable,
    not(AGE_LIMIT and s.memExpired and s.st == "toast"),
    val u = s.cookie
    val s1 = s.with("sends", s.sends + 1).with("checked", "")
    if (u == "none")
      s' = s1  // 401 -> the login window; the action stays: the text gives no fate
    else if (POLICY == "bound" and u != "A")
      s' = s1.with("st", "closed")
    else if (s.mem.get(u))
      s' = s1.with("st", "closed")
    else if (IDKIND == "named" and s.rows > 0)
      s' = s1.with("st", "closed").with("mem", s.mem.set(u, true))
    else {
      nondet lost = Set(true, false).oneOf()
      val nr = s.replays - 1
      s' = s1.with("rows", s.rows + 1).with("rowBy", u).with("cross", s.cross or u != "A")
        .with("mem", s.mem.set(u, true))
        .with("st", if (not(lost)) "closed" else if (nr > 0) "delay" else "toast")
        .with("replays", if (nr > 0) nr else 0)
    }
  }

  action failedSend = all {
    sendable, s.st == "delay",
    val nr = s.replays - 1
    s' = s.with("replays", if (nr > 0) nr else 0).with("st", if (nr > 0) "delay" else "toast").with("checked", "")
  }

  action expire = all { s.cookie != "none", s' = s.with("cookie", "none") }
  action otherLogin = all { SHARED, s.cookie != "B", s' = s.with("cookie", "B") }

  def cancelled(nu: str): str =
    if (POLICY != "cancel_seen" or nu == "A") s.st
    else if (s.st == "delay") "closed"
    else if (s.st == "toast" and CANCEL_TOAST) "closed"
    else s.st

  action moduleLogin = all {
    s.cookie == "none",
    s' = s.with("cookie", "B").with("seen", "B").with("st", cancelled("B"))
  }

  action readSession = s' = s.with("seen", s.cookie).with("st", cancelled(s.cookie))

  // DONE_ANSWER_KEEP (rc:33) is a minimum of a day; the automatic replays end within seconds (nr:114): expiry is possible only while the toast waits
  action memExpire = all { KEEP_EXP, s.mem.get("A"), s.st == "toast", s' = s.with("mem", s.mem.set("A", false)).with("memExpired", true) }

  action reload = all { RELOAD, s.st == "delay" or s.st == "toast", s' = s.with("st", "lost") }

  // after a reload the human repeats: a new call, a new key (nr:111)
  action humanNew = all {
    s.st == "lost", s.cookie == "A",
    if (IDKIND == "named" and s.rows > 0) s' = s.with("st", "closed")
    else s' = s.with("rows", s.rows + 1).with("rowBy", "A").with("st", "closed")
  }

  action stutter = s' = s
  action step = any { send, failedSend, recheck, expire, otherLogin, moduleLogin, readSession, memExpire, reload, humanNew, stutter }

  val inv_no_cross = not(s.cross)
  val inv_one_row = s.rows <= 1
  val wit_cross_before_seen = not(s.cross and s.seen == "A")
  val wit_cross_toast = not(s.cross and s.st == "closed" and s.seen == "B" and s.replays == 3)
  val wit_double_after_expiry = not(s.rows == 2 and s.memExpired)
  val wit_completed = not(s.st == "closed" and s.rows == 1 and s.rowBy == "A" and s.sends >= 1)
  val wit_double_after_reload = not(s.rows == 2 and s.st == "closed" and not(s.memExpired))
}
