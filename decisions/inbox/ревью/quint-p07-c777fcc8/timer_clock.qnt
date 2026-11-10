// M4 (clocks are not named).
// Anchors: nr:27, nr:189 time of the doors; 06.3:152 server_time; gp:199 server_time form; nr:111 20 s; 06.5:99 poll_s; 10:90; adr Addendum (10) item 6 monotonic clocks.
// CLOCK: mono or wall = the clock of the timer (the text does not choose). JUMP: a jump of the wall clock during the wait.
// SKEW: browser wall clock minus console clock. AGE: browser = age shown by the browser clock, server_time = by the console's server_time.
// SLEEP: the tab sleeps and the timer does not run while asleep; on wake both the answer and the timer are due; the text gives no order; WAKE_ANSWER_FIRST is a control.
module clock_core {
  const CLOCK: str
  const JUMP: int
  const T: int
  const D: int
  const SKEW: int
  const AGE: str
  const SLEEP: int
  const WAKE_ANSWER_FIRST: bool
  type S = {t: int, wallOff: int, jumped: bool, st: str, started: int, startWall: int, asleep: bool, slept: bool, shownAge: int, ageErr: int, falseT: bool}
  var s: S
  action init = s' = {t: 0, wallOff: 0, jumped: false, st: "wait", started: 0, startWall: 0, asleep: false, slept: false, shownAge: -9999, ageErr: 0, falseT: false}

  def elapsed: int = if (CLOCK == "mono") s.t - s.started else (s.t + s.wallOff) - s.startWall
  def answerDue: bool = s.t >= D

  action tick = all {
    not(s.asleep), s.t < T + D + 25,
    nondet dt = Set(1, 5).oneOf()
    all {
      s.st != "wait" or elapsed < T,   // a due timer fires before time moves on (both clocks)
      s.st != "wait" or s.t + dt <= D or s.t >= D,
      s' = s.with("t", s.t + dt),
    }
  }
  action jump = all { JUMP != 0, not(s.jumped), s' = s.with("wallOff", s.wallOff + JUMP).with("jumped", true) }
  action sleep = all { SLEEP > 0, not(s.slept), s.st == "wait", s' = s.with("asleep", true).with("slept", true) }
  action wake = all { s.asleep, s' = s.with("t", s.t + SLEEP).with("asleep", false) }
  action answer = all {
    not(s.asleep), s.st == "wait", answerDue,
    s' = s.with("st", "answered")
  }
  action timeout = all {
    not(s.asleep), s.st == "wait", elapsed >= T,
    not(WAKE_ANSWER_FIRST and answerDue),
    s' = s.with("st", "timeout").with("falseT", answerDue)
  }
  action showAge = all {
    s.shownAge == -9999,
    s' = s.with("shownAge", s.t).with("ageErr", if (AGE == "browser") SKEW else 0)
  }
  action stutter = s' = s
  action step = any { tick, jump, sleep, wake, answer, timeout, showAge, stutter }

  val inv_no_premature = (s.st == "timeout") implies s.t - s.started >= T
  val inv_no_false_timeout = not(s.falseT)
  val inv_wait_bounded = (s.st == "wait" and not(s.asleep)) implies s.t - s.started <= T + 5
  val inv_age_exact = s.ageErr == 0
  val wit_timeout = not(s.st == "timeout")
}
