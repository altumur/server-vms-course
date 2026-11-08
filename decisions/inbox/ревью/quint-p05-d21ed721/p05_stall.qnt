// P/05 pass_stalled: порог PULSE_LIMIT и пульс (норма R028 и поле pass_stalled; уточнение M9). Срез d21ed721.
module p05_stall {
  const HB: int           // HEARTBEAT_EVERY = 10 (const:5)
  const L: int            // PULSE_LIMIT, объявляет реализация (norms:368-369); значение — параметр
  const DURS: Set[int]    // возможные длительности шага (параметр)
  const BLOCK_HB: bool    // мутант: пульс не публикуется, пока идёт шаг

  type S = { now: int, nextHb: int, dur: int, running: bool, phase: int,
             reportedA: bool, reportedB: bool, conflict: bool, conflictStrict: bool, hbCount: int, ended: bool }
  var s: S

  action init = {
    nondet dur = oneOf(DURS)
    nondet ph = oneOf(1.to(HB))
    s' = { now: 0, nextHb: ph, dur: dur, running: true, phase: ph,
           reportedA: false, reportedB: false, conflict: false, conflictStrict: false, hbCount: 0, ended: false }
  }

  pure def nextEvent(st: S): int = if (st.running and st.dur < st.nextHb) st.dur else st.nextHb

  action advance = all {
    s.now < nextEvent(s),
    s' = s.with("now", nextEvent(s))
  }

  action stepEnds = all {
    s.running, s.now == s.dur,
    s' = s.with("running", false).with("ended", true)
  }

  action heartbeat = all {
    s.now == s.nextHb, not(BLOCK_HB and s.running),
    val exceeded = s.dur > L
    // R028 (norms:370): превышение порога — поле в следующем пульсе после превышения; единожды.
    val a = exceeded and s.now >= L and not(s.reportedA)
    // Поле pass_stalled «только пока проход висит» (norms:288, norms:524).
    val b = s.running and s.now >= L
    s' = s.with("nextHb", s.now + HB).with("hbCount", s.hbCount + 1)
          .with("reportedA", s.reportedA or a).with("reportedB", s.reportedB or b)
          .with("conflict", s.conflict or (a and not(b)))
          .with("conflictStrict", s.conflictStrict or (a and not(b) and s.now > s.dur))
  }

  action done = all { not(s.running), s.hbCount >= 3, s' = s }

  action step = any { advance, stepEnds, heartbeat, done }

  val inv_rulesAgree = not(s.conflict)
  // Шаг завершился строго раньше ближайшего пульса: правила расходятся и без совпадения времени.
  val inv_rulesAgreeStrict = not(s.conflictStrict)
  // Шаг, идущий дольше L+HB, виден в пульсе.
  val inv_visible = (s.running and s.now > L + HB) implies s.reportedB
  val inv_types = s.now >= 0 and s.hbCount >= 0

  val wit_shown = not(s.reportedB)
  val wit_conflict = not(s.conflict)
  val wit_endedAfterLimit = not(s.ended and s.dur > L and s.reportedB)
  val wit_noExceed = not(s.dur <= L and s.ended)
  val wit_runningPastEdge = not(s.running and s.now > L + HB)
}
