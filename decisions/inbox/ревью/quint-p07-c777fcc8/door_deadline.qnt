// C6 (one attempt deadline of 20 s against domain doors of 90 s and 100 s), and the C6 proposal (reread of /domain).
// Anchors: nr:47 writes /domain/*; nr:100 own writes; nr:111 "timeout 20 s for each attempt"; nr:221; cm:292 limit 90 s;
//   fwd:90 forwarding 90 s /domain/move, fwd:232 /domain/handover 100 s; 08.8:302 forwarding longer than the common deadline; loc:438 notHanded.
// One door call. The door ends at second D (a process deadline), the answer reaches the client unless LOST.
// T: the client's attempt deadline; -1 = no deadline. ONTIMEOUT: "refused" = reports notHanded; "unknown_reread" = reports unknown, rereads the holder.
// RULE of the reread (the old holder is seen while the door runs and after a call off; the client cannot tell which):
//   naive: old holder -> not handed; afterdl: old holder counts as not handed only when t >= GW (the door's forwarding deadline).
module deadline_core {
  const T: int
  const ONTIMEOUT: str
  const RULE: str
  const DS: Set[int]
  const GW: int
  const LOST: bool
  const MAXT: int
  const BOUND: int

  type S = {t: int, d: int, door: str, phase: str, report: str, rereadAt: int}
  var s: S

  action init = { nondet d0 = DS.oneOf() s' = {t: 0, d: d0, door: "run", phase: "wait", report: "none", rereadAt: -1} }

  action tick = all {
    nondet nt = Set(s.t + 1, s.t + 5, s.t + 20, s.t + 45, s.t + 89, GW, MAXT).filter(x => x > s.t).oneOf()
    all {
      nt <= MAXT,
      s.door != "run" or nt <= s.d,
      s.phase != "wait" or T < 0 or nt <= T,
      LOST or s.phase != "wait" or s.door == "run",
      s' = s.with("t", nt)
    }
  }

  action doorDone = all {
    s.door == "run", s.t == s.d,
    nondet r = Set("applied", "calledoff").oneOf()
    s' = s.with("door", r)
  }

  action answer = all {
    not(LOST), s.phase == "wait", s.door != "run",
    s' = s.with("phase", "reported").with("report", if (s.door == "applied") "handed" else "not_handed")
  }

  action timeout = all {
    T >= 0, s.phase == "wait", s.t >= T,
    if (ONTIMEOUT == "refused") s' = s.with("phase", "reported").with("report", "not_handed")
    else s' = s.with("phase", "timedout").with("report", "unknown")
  }

  action reread = all {
    s.phase == "timedout",
    val seenNew = s.door == "applied"
    s' = s.with("phase", "reported").with("rereadAt", s.t).with("report",
      if (seenNew) "handed"
      else if (RULE == "naive") "not_handed"
      else if (s.t >= GW) "not_handed"
      else "unknown")
  }

  action stutter = s' = s
  action step = any { tick, doorDone, answer, timeout, reread, stutter }

  val inv_no_false_not_handed = s.report == "not_handed" implies s.door == "calledoff"
  val inv_wait_bounded = s.phase == "wait" implies s.t <= BOUND
  val wit_not_handed_while_running = not(s.report == "not_handed" and s.door == "run" and s.t < s.d)
  val wit_reread_old_during_run = not(s.rereadAt >= 0 and s.door == "run" and s.report == "not_handed")
  val wit_handed = not(s.phase == "reported" and s.report == "handed")
  val wit_unknown_end = not(s.phase == "reported" and s.report == "unknown" and s.t >= T and s.door == "applied")
}
