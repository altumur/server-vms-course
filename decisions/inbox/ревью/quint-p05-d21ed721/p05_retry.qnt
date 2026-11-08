// P/05 restore: повторы с удвоением без разброса при одновременном старте (находка C18). Срез d21ed721.
// Две машины начинают restore; каждая повторяет обращение через RETRY, удваивая до RETRY_MAX.
module p05_retry {
  const RETRY: int       // const:RESTORE_RETRY = 10
  const RETRY_MAX: int   // const:RESTORE_RETRY_MAX = 600
  const STARTS: Set[int] // возможные моменты старта второго сервера (первый стартует в 0)
  const JITTER: Set[int] // случайная добавка к задержке (норма не задаёт; {0} = нет разброса)
  const MAX_ATTEMPTS: int

  type S = { next: int -> int, delay: int -> int, attempts: int -> int, now: int, sameCount: int, startGap: int }
  var s: S

  pure def d(x: int): int = if (x * 2 > RETRY_MAX) RETRY_MAX else x * 2

  action init = {
    nondet st = oneOf(STARTS)
    s' = { next: Map(1 -> RETRY, 2 -> st + RETRY), delay: Map(1 -> RETRY, 2 -> RETRY),
           attempts: Map(1 -> 0, 2 -> 0), now: 0, sameCount: 0, startGap: st }
  }

  // Сервер, чья очередь раньше, делает попытку; совпавшие по времени — обе разом.
  action fire = {
    val t = if (s.next.get(1) <= s.next.get(2)) s.next.get(1) else s.next.get(2)
    val fires1 = s.next.get(1) == t
    val fires2 = s.next.get(2) == t
    val both = fires1 and fires2
    val d1 = d(s.delay.get(1))
    val d2 = d(s.delay.get(2))
    all {
      s.attempts.get(1) < MAX_ATTEMPTS and s.attempts.get(2) < MAX_ATTEMPTS,
      {
        nondet j1 = oneOf(JITTER)
        nondet j2 = oneOf(JITTER)
        val n1 = if (fires1) t + d1 + j1 else s.next.get(1)
        val n2 = if (fires2) t + d2 + j2 else s.next.get(2)
        s' = s.with("now", t)
              .with("next", Map(1 -> n1, 2 -> n2))
              .with("delay", Map(1 -> (if (fires1) d1 else s.delay.get(1)), 2 -> (if (fires2) d2 else s.delay.get(2))))
              .with("attempts", Map(1 -> s.attempts.get(1) + (if (fires1) 1 else 0), 2 -> s.attempts.get(2) + (if (fires2) 1 else 0)))
              .with("sameCount", s.sameCount + (if (both) 1 else 0))
      }
    }
  }

  action step = any { fire, all { s.attempts.get(1) >= MAX_ATTEMPTS or s.attempts.get(2) >= MAX_ATTEMPTS, s' = s } }

  // Без разброса и при равном старте все попытки совпадают (свойство нормы при допущениях).
  val inv_alwaysTogether = s.startGap == 0 implies s.next.get(1) == s.next.get(2)
  // При ненулевом сдвиге старта без разброса сдвиг сохраняется.
  val inv_gapPreserved = s.attempts.get(1) == s.attempts.get(2) implies s.next.get(2) - s.next.get(1) == s.startGap
  val inv_types = s.now >= 0

  // Свидетели.
  val wit_coincide = not(s.sameCount >= 3)
  val wit_nonzeroGap = not(s.startGap != 0 and s.attempts.get(1) >= 2)
}
