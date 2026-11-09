// timing.qnt — сквозной срок прохода (С3), стенные часы (С8), шторм повторов (С12).
// Якоря: 09.1:572,1468; const:REPORT_EVERY; A1:40 LOST_AFTER, MARK_REFRESH; acc:302 (step 6);
//        09.1:361,396,517-521,639-643; ev:216; 08.4:233,898; 09.1:270,1437; acc:218.

// --- С3. Единица времени — полсекунды: MARK_REFRESH 22.5 с кратна (A1:40). ---
module pass_base {
  const N_SILENT: int    // консолей CLUSTERS, не отвечающих весь срок (параметр; предела числа консолей норма не даёт)
  const READ: str        // "seq" | "par": параллельность следования норма не задаёт (09.1:1468)
  const PERIOD: str      // "from_start" | "from_end": начало отсчёта every норма не называет (09.1:270)
  pure val DEADLINE = 6    // 3 с на консоль, 09.1:1468
  pure val EVERY = 10      // REPORT_EVERY 5 с, const
  pure val LOST_AFTER = 90 // 45 с, A1:40
  pure val MARK = 45       // 22.5 с, A1:40

  var now: int
  var phase: str         // wait | follow | send
  var left: int
  var passStart: int
  var nextPassAt: int
  var markAt: int
  var lastReportAt: int
  var lastGap: int
  var reports: int
  var lastAction: str

  action init = all {
    now' = 0, phase' = "wait", left' = N_SILENT, passStart' = 0, nextPassAt' = 0,
    markAt' = 0, lastReportAt' = 0, lastGap' = 0, reports' = 0, lastAction' = "init",
  }
  action waitNext = all {
    phase == "wait",
    now' = nextPassAt, phase' = "follow", passStart' = nextPassAt, left' = N_SILENT,
    nextPassAt' = nextPassAt, markAt' = markAt, lastReportAt' = lastReportAt, lastGap' = lastGap, reports' = reports,
    lastAction' = "waitNext",
  }
  action followOne = all {
    phase == "follow", left > 0,
    now' = now + DEADLINE,
    left' = if (READ == "seq") left - 1 else 0,
    phase' = "follow", passStart' = passStart, nextPassAt' = nextPassAt, markAt' = markAt,
    lastReportAt' = lastReportAt, lastGap' = lastGap, reports' = reports, lastAction' = "followOne",
  }
  // Отчёт дошёл, правило знака acc:302 (шаг 6).
  action sendReport = all {
    phase == "follow", left == 0,
    val gap = now - lastReportAt
    all { lastGap' = gap, lastReportAt' = now },
    reports' = reports + 1,
    markAt' = if (now - markAt >= MARK) now else markAt,
    nextPassAt' = if (PERIOD == "from_end") now + EVERY else (if (passStart + EVERY > now) passStart + EVERY else now),
    phase' = "wait", passStart' = passStart, left' = left, now' = now, lastAction' = "sendReport",
  }
  action step = any { waitNext, followOne, sendReport }

  // Граница на завершённом действии: интервал между отчётами меньше LOST_AFTER.
  val GapBelowLost = reports == 0 or lastGap < LOST_AFTER
  // В любое время знак моложе LOST_AFTER (на границе N_SILENT это нарушится раньше отправки).
  val MarkFresh = now - markAt < LOST_AFTER
  val witGapOver = not(reports > 0 and lastGap >= LOST_AFTER)
  val witSent = not(reports > 0)
}
module pass_seq_0 { import pass_base(N_SILENT = 0, READ = "seq", PERIOD = "from_start").* }
module pass_seq_14 { import pass_base(N_SILENT = 14, READ = "seq", PERIOD = "from_start").* }
module pass_seq_15 { import pass_base(N_SILENT = 15, READ = "seq", PERIOD = "from_start").* }
module pass_seq_16 { import pass_base(N_SILENT = 16, READ = "seq", PERIOD = "from_start").* }
module pass_end_14 { import pass_base(N_SILENT = 14, READ = "seq", PERIOD = "from_end").* }
module pass_par_60 { import pass_base(N_SILENT = 60, READ = "par", PERIOD = "from_start").* }

// --- С8 часть 1: as_of, reached, GRANT_LIFETIME. ---
module clock_asof_base {
  const RULE: str   // "text": max (не идёт назад) 09.1:361,396 | "clamp": контроль-гипотеза: при возврате min(asOf,w) | "mono": контроль-гипотеза: as_of по монотонному времени
  const J: int      // величина скачка — параметр модели, не норма
  pure val FRESH_EVERY = 60     // const
  pure val GRANT_LIFETIME = 86400 // 08-domain const
  var t: int
  var w: int
  var j: int   // 0 — не было, 1 — вперёд, 2 — вернулись
  var asOf: int
  var reachedTs: int
  var tLastReach: int   // истинное время записи reached
  var tLastCarry: int
  var staleSkip: bool   // ответ пришёл, reached по норме не записан, хотя истинно прошло >= FRESH_EVERY
  var lastAction: str

  action init = all {
    t' = 1, w' = 1, j' = 0, asOf' = 0, reachedTs' = 0, tLastReach' = 0, tLastCarry' = 0,
    staleSkip' = false, lastAction' = "init",
  }
  action tick = { nondet dt = oneOf(Set(1, FRESH_EVERY, GRANT_LIFETIME)) all {
    t' = t + dt, w' = w + dt, j' = j, asOf' = asOf, reachedTs' = reachedTs, tLastReach' = tLastReach,
    tLastCarry' = tLastCarry, staleSkip' = staleSkip, lastAction' = "tick" } }
  action jumpForward = all { j == 0, w' = w + J, j' = 1, t' = t, asOf' = asOf, reachedTs' = reachedTs,
    tLastReach' = tLastReach, tLastCarry' = tLastCarry, staleSkip' = staleSkip, lastAction' = "jumpForward" }
  action jumpBack = all { j == 1, w' = w - J, j' = 2, t' = t,
    asOf' = if (RULE == "clamp" and asOf > w - J) w - J else asOf,
    reachedTs' = reachedTs, tLastReach' = tLastReach, tLastCarry' = tLastCarry,
    staleSkip' = staleSkip, lastAction' = "jumpBack" }
  // Прямой ответ держателя: domain_age = 0 (09.1:361).
  action carry = all {
    val newAsOf = if (RULE == "mono") t else (if (w > asOf) w else asOf)
    all {
      asOf' = newAsOf,
      val writeReach = reachedTs == 0 or w >= reachedTs + FRESH_EVERY
      all {
        reachedTs' = if (writeReach) w else reachedTs,
        tLastReach' = if (writeReach) t else tLastReach,
        staleSkip' = (staleSkip or (tLastReach > 0 and t - tLastReach >= FRESH_EVERY and not(writeReach))),
      },
    },
    tLastCarry' = t, t' = t, w' = w, j' = j, lastAction' = "carry",
  }
  action step = any { tick, jumpForward, jumpBack, carry }

  // as_of — момент сборки ответа держателем (09.1:360); после возврата не впереди истинного времени.
  val AsOfNotFuture = j != 2 or asOf <= t
  // Доставленный ответ освежает reached не реже FRESH_EVERY по истинному времени (09.1:517-521, завершённое действие).
  val ReachedFresh = not(staleSkip)
  // Обещание 08.4:898: права отключённого члена сгорают к tLastCarry + GRANT_LIFETIME
  // (копия старше as_of + GRANT_LIFETIME не даёт прав, 08.4:233; as_of — момент сборки, 09.1:360).
  val RevokeBound = tLastCarry == 0 or t <= tLastCarry + GRANT_LIFETIME or w >= asOf + GRANT_LIFETIME
  val witFutureAsOf = not(j == 2 and asOf > t)
  val witStaleSkip = not(staleSkip)
  val witCarry = not(tLastCarry > 0)
}
module clock_asof_nojump { import clock_asof_base(RULE = "text", J = 0).* }
module clock_asof_text { import clock_asof_base(RULE = "text", J = 7200).* }
module clock_asof_clamp { import clock_asof_base(RULE = "clamp", J = 7200).* }
module clock_asof_mono { import clock_asof_base(RULE = "mono", J = 7200).* }

// --- С8 часть 2: фронт тревог, rebuild. Время — секунды, проверка фронта раз в секунду 09.1:639. ---
module clock_alarm_base {
  const RULE: str   // "wall": t > to 09.1:640,643 | "mono": контроль-гипотеза: новая строка по изменению фронта
  const J: int
  const CHECK_ENFORCED: bool  // мутант: тик не требует проверки фронта
  pure val URGENT_GAP = 1 // const
  pure val BOUND = 1 + URGENT_GAP

  var t: int
  var w: int
  var j: int
  var watermark: int   // последний опубликованный штамп журнала (ev:216)
  var front: int       // t последней строки тревоги (-1 нет)
  var pageTo: int      // to страницы
  var frontSeen: int   // для rule mono: номер строки фронта (монотонный счётчик), не штамп
  var seq: int         // счётчик строк тревог
  var lastUrgent: int
  var pendingAt: int   // истинное время самой старой неопубликованной тревоги (-1 нет)
  var lastPageTrue: int
  var checked: bool    // проверка фронта этой секунды сделана
  var lastAction: str

  action init = all {
    t' = 1, w' = 1, j' = 0, watermark' = 0, front' = -1, pageTo' = 0, frontSeen' = 0, seq' = 0, lastUrgent' = 0,
    pendingAt' = -1, lastPageTrue' = 0, checked' = false, lastAction' = "init",
  }
  action tick = all {
    (not(CHECK_ENFORCED) or checked),
    t' = t + 1, w' = w + 1, checked' = false,
    j' = j, watermark' = watermark, front' = front, pageTo' = pageTo, frontSeen' = frontSeen,
    lastUrgent' = lastUrgent, pendingAt' = pendingAt, lastPageTrue' = lastPageTrue, seq' = seq, lastAction' = "tick",
  }
  action jumpForward = all { j == 0, J > 0, w' = w + J, j' = 1, t' = t, checked' = checked,
    watermark' = watermark, front' = front, pageTo' = pageTo, frontSeen' = frontSeen, lastUrgent' = lastUrgent,
    pendingAt' = pendingAt, lastPageTrue' = lastPageTrue, seq' = seq, lastAction' = "jumpForward" }
  action jumpBack = all { j == 1, w' = w - J, j' = 2, t' = t, checked' = checked,
    watermark' = watermark, front' = front, pageTo' = pageTo, frontSeen' = frontSeen, lastUrgent' = lastUrgent,
    pendingAt' = pendingAt, lastPageTrue' = lastPageTrue, seq' = seq, lastAction' = "jumpBack" }
  // Новая тревога: штамп не идёт назад (ev:216). Коллизия в той же секунде, что и сборка страницы, исключена:
  // целая секунда — артефакт модели, у нормы t — число с дробью.
  action alarmEvent = all {
    pendingAt == -1, lastPageTrue < t,
    val stamp = if (w > watermark) w else watermark
    all { watermark' = stamp, front' = stamp },
    pendingAt' = t, seq' = seq + 1, t' = t, w' = w, j' = j, pageTo' = pageTo, frontSeen' = frontSeen, lastUrgent' = lastUrgent,
    lastPageTrue' = lastPageTrue, checked' = checked, lastAction' = "alarmEvent",
  }
  // Проверка фронта раз в секунду, сборка страницы при новом фронте (09.1:639-643).
  action urgentCheck = all {
    not(checked),
    val fire = (if (RULE == "wall") front > pageTo else seq != frontSeen) and t - lastUrgent >= URGENT_GAP
    all {
      pageTo' = if (fire) w else pageTo,
      lastUrgent' = if (fire) t else lastUrgent,
      frontSeen' = if (fire) seq else frontSeen,
      pendingAt' = if (fire) -1 else pendingAt,
      lastPageTrue' = if (fire) t else lastPageTrue,
      lastAction' = if (fire) "pageBuilt" else "frontRead",
    },
    checked' = true, t' = t, w' = w, j' = j, watermark' = watermark, front' = front, seq' = seq,
  }
  action step = any { tick, jumpForward, jumpBack, alarmEvent, urgentCheck }

  val AlarmBound = pendingAt == -1 or t - pendingAt <= BOUND
  val ToNotFuture = j != 2 or pageTo <= w
  val witAlarmStuck = not(pendingAt != -1 and t - pendingAt > BOUND)
  val witPageBuilt = not(lastAction == "pageBuilt" and pendingAt == -1)
}
module alarm_nojump { import clock_alarm_base(RULE = "wall", J = 0, CHECK_ENFORCED = true).* }
module alarm_text { import clock_alarm_base(RULE = "wall", J = 20, CHECK_ENFORCED = true).* }
module alarm_mono { import clock_alarm_base(RULE = "mono", J = 20, CHECK_ENFORCED = true).* }
module alarm_mut_nocheck { import clock_alarm_base(RULE = "wall", J = 0, CHECK_ENFORCED = false).* }

// --- С12. Перезапись пометки всех серверов; когорта повторов за секунду. Числа: REPORT_RATE 200 (08-domain const), every 5. ---
module storm_base {
  const N: int
  const SPREAD: str    // "sync": все в одной секунде (одновременный старт) | "uniform": равномерно по every
  pure val EVERY = 5
  pure val REPORT_RATE = 200
  var sec: int
  var marksLost: bool
  var wholesThisSec: int
  var maxBurst: int
  var postsPerMemberMax: int
  var firedCohorts: int
  var lastAction: str

  pure def cohort(n: int, s: str, sec2: int): int =
    if (s == "sync") (if (sec2 % EVERY == 0) n else 0)
    else ((n + EVERY - 1) / EVERY)

  action init = all { sec' = 0, marksLost' = false, wholesThisSec' = 0, maxBurst' = 0, postsPerMemberMax' = 0, firedCohorts' = 0, lastAction' = "init" }
  action loseMarks = all { not(marksLost), marksLost' = true, sec' = sec, wholesThisSec' = 0, maxBurst' = maxBurst, postsPerMemberMax' = postsPerMemberMax, firedCohorts' = firedCohorts, lastAction' = "loseMarks" }
  // Секунда: когорта шлёт дельту (409 rebase) и тут же целое (09.1:1437): по 2 POST на члена.
  action second = all {
    marksLost, firedCohorts < EVERY,
    val c = cohort(N, SPREAD, sec)
    all {
      wholesThisSec' = c,
      maxBurst' = if (c > maxBurst) c else maxBurst,
      postsPerMemberMax' = if (c > 0) 2 else postsPerMemberMax,
      firedCohorts' = firedCohorts + (if (c > 0) 1 else 0),
    },
    sec' = sec + 1, marksLost' = marksLost, lastAction' = "second",
  }
  action step = any { loseMarks, second }
  val BurstWithinRate = maxBurst <= REPORT_RATE
  val PerMemberBounded = postsPerMemberMax <= 2
  val witBurst = not(maxBurst > REPORT_RATE)
  val witFired = not(firedCohorts > 0)
}
module storm_sync_200 { import storm_base(N = 200, SPREAD = "sync").* }
module storm_sync_201 { import storm_base(N = 201, SPREAD = "sync").* }
module storm_uni_1000 { import storm_base(N = 1000, SPREAD = "uniform").* }
module storm_uni_1001 { import storm_base(N = 1001, SPREAD = "uniform").* }
