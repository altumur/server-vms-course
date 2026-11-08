// P/05 retain на границе срока против Q6 (находка C15). Срез d21ed721.
// Одно закрытое ведро, настенные часы (wall) и монотонные (mono), скачки часов — действия среды.
// Модель предиката, а не реализации. TERM — из seams s50 (1 день = 86400 с).
module p05_retain {
  const TERM: int        // seconds срока: 86400 (seams:52, norms:224)
  const MODE: str        // "LETTER" — norms:224; "DEFER" — откладывание (Q6) с доказательством по mono
  const JUMPS: Set[int]  // допустимые среда-скачки wall (положительные и отрицательные)
  const ALLOWED: int     // допуск раннего удаления, если среда квалифицирована (0 иначе)
  const CAN_APPEND: bool
  const WRITTEN_WATERMARK: bool  // вариант: written = max(прежний, wall) (норма не называет)
  const MUT_STRICT: bool     // мутант: строго > вместо >=
  const MUT_EARLY: bool      // мутант: на 1 с раньше срока
  const MUT_NO_MONO: bool    // мутант: DEFER без проверки монотонного времени
  const MAX_JUMPS: int       // сколько скачков за трассу допускает среда (квалификация среды; большое число — нет предела)

  type S = { wall: int, mono: int, written: int, monoW: int, closed: bool, removed: bool,
             rmElapsed: int, rmWall: int, lastRetain: int, jumped: bool, jumps: int, net: int, rmNet: int }
  var s: S

  action init = s' = { wall: 100, mono: 0, written: 100, monoW: 0, closed: false, removed: false,
                       rmElapsed: -1, rmWall: -1, lastRetain: -1, jumped: false, jumps: 0, net: 0, rmNet: 0 }

  // Нормальный ход времени; двойной шаг до границы (nondet выбирает).
  action tick = all {
    // Шаг 1 с, либо сразу на границу − 1 или на границу (чтобы s49/s50 были достижимы при малом числе шагов).
    val toEdge = s.written + TERM - s.wall
    nondet d = oneOf(Set(1, if (toEdge > 2) toEdge - 1 else 1, if (toEdge > 1) toEdge else 1))
    s' = s.with("wall", s.wall + d).with("mono", s.mono + d)
  }

  action jump = {
    nondet j = oneOf(JUMPS)
    all { j != 0, s.jumps < MAX_JUMPS, s' = s.with("wall", s.wall + j).with("jumped", true).with("jumps", s.jumps + 1).with("net", s.net + j) }
  }

  action close = all { not(s.closed), not(s.removed), s' = s.with("closed", true) }

  action appendRow = all {
    CAN_APPEND, not(s.closed), not(s.removed),
    s' = s.with("written", if (WRITTEN_WATERMARK and s.written > s.wall) s.written else s.wall).with("monoW", s.mono)
  }

  pure def eligible(st: S): bool = {
    val boundary = st.written + TERM + (if (MUT_EARLY) -1 else 0)
    val wallOk = if (MUT_STRICT) st.wall > boundary else st.wall >= boundary
    if (MODE == "DEFER" and not(MUT_NO_MONO)) wallOk and st.mono - st.monoW >= TERM
    else wallOk
  }

  // retain: только закрытые (norms:968); рождаем запись о запуске при любом исходе.
  action retainRun = all {
    s.closed, not(s.removed),
    if (eligible(s))
      s' = s.with("removed", true).with("rmElapsed", s.mono - s.monoW).with("rmWall", s.wall).with("rmNet", s.net).with("lastRetain", s.wall)
    else
      s' = s.with("lastRetain", s.wall)
  }

  action step = any { tick, jump, close, appendRow, retainRun }

  // Q6 (ej:216): нет удаления раньше истекшего срока (по реальному прошедшему времени от последней записи).
  val inv_noEarly = s.removed implies s.rmElapsed >= TERM - ALLOWED
  // То же при нулевой сумме скачков (откат назад и возврат): раннего удаления нет только если written взят не из отката.
  val inv_noEarlyNetZero = (s.removed and s.rmNet == 0) implies s.rmElapsed >= TERM
  // R020/s50: запуск retain при wall ≥ written+TERM удаляет закрытое ведро.
  val inv_s50 = (s.lastRetain >= 0 and s.lastRetain >= s.written + TERM) implies s.removed
  // s49: удаления до срока по настенным часам нет.
  val inv_s49 = s.removed implies s.rmWall >= s.written + TERM
  val inv_types = s.mono >= 0

  // Свидетели (ожидается нарушение).
  val wit_removed = not(s.removed)
  val wit_boundaryEq = not(s.removed and s.rmWall == s.written + TERM)
  val wit_jumped = not(s.jumped)
  val wit_removedAfterTerm = not(s.removed and s.rmElapsed >= TERM)
  val wit_retainBelow = not(s.lastRetain >= 0 and s.lastRetain < s.written + TERM)
}
