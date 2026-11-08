// P/04 — проход против WATCHDOG=1 / WatchdogSec и бюджета прохода (находка С1), связь с памятью наблюдений и ходом.
// Модель текста норм, не реализации.
//   N = Platform/04-controller/spec/04-controller.norms.md
//   L = Platform/04-controller/lifecycle.md
//   024 = Platform/02-installer/spec/02.4-installer.norms.md
//   T = Platform/common/contracts/turn.md
//   OB = Platform/common/contracts/observation.md
//   RC = Platform/04-controller/forms/runtime-constants.tsv
//   FRM = Platform/04-controller/forms/slot-fate.tsv
// Единица времени — секунды. opCost — стоимость одной операции (чтения, решения, снимка), выбирается недетерминированно из 1..400
// при инициализации и постоянна: норма числа не задаёт (нормативного значения здесь нет).
// Допущения: WATCHDOG=1 раз за оборот прохода — в начале прохода (L:85); ошибка стороны прохода считается одинаково;
//   один контроллер (гонка ходов — p04_turn_race); ожидание хранилища не срывается; kill сторожа — только при превышении WD.
// Не моделируется: снимки подробно, бюджеты, реальная цена записи, несколько контроллеров.
module p04_pass_watchdog {
  const BUDGET: bool              // проба предложения С1: число решений за проход конечно, так что проход укладывается в WD
  const NOTIFY_PER_DECISION: bool // вариант С1: WATCHDOG=1 между решениями, а не раз за оборот

  pure val PASS_EVERY: int = 5    // RC:4
  pure val WD: int = 360          // 024:66-67 WatchdogSec=360 (SHOULD)
  pure val TURN_TERM: int = 45    // T:32
  pure val TURN_BUSY_RETRY: int = 5 // RC:5
  pure val SLOT_TERM: int = 45    // FRM:16; Platform/common/contracts/slot.md:45
  pure val LOST_AFTER: int = 45   // FRM:17; Platform/common/contracts/observation.md Freshness

  var now: int
  var opCost: int           // frozen, 1..400
  var budget: int           // frozen; 0 — нет бюджета
  var phase: str            // Idle | Busy | Control | Snap | Down
  var lastNotify: int
  var passStart: int
  var lastPassEnd: int
  var u: int                // ждущие решения (backlog)
  var decided: int          // решений в текущем проходе
  var kills: int
  var reports: int          // опубликованные финальные отчёты (N:911-912)
  var lastPassDur: int      // устанавливается завершающим действием прохода
  var turnBusy: bool        // ход занят чужим следом
  var turnSeenAt: int       // когда этот процесс впервые увидел занятый ход (T:46: возраст по своим часам)
  var slotFirstSeen: int    // память наблюдения мёртвого слота; -1 — ещё не видел (OB:44)
  var judgedNonAlive: bool  // была неживая судьба (шаг 3)
  var runsSinceStart: int   // проходов завершено после (пере)запуска

  action init = {
    nondet c = oneOf(1.to(400))
    nondet u0 = oneOf(Set(1, 2, 3, 4, 5, 6, 7, 8))
    nondet b = oneOf(1.to(8))
    all {
      now' = 0,
      opCost' = c,
      budget' = if (BUDGET) b else 0,
      phase' = "Idle",
      lastNotify' = 0,
      passStart' = 0,
      lastPassEnd' = 0,
      u' = u0,
      decided' = 0,
      kills' = 0,
      reports' = 0,
      lastPassDur' = 0,
      turnBusy' = false,
      turnSeenAt' = -1,
      slotFirstSeen' = -1,
      judgedNonAlive' = false,
      runsSinceStart' = 0,
      // допущение варианта BUDGET: бюджет подобран так, что B*c + 2*c <= WD (т.е. проход с бюджетом укладывается в сторож)
      BUDGET implies (b * c + 2 * c <= WD),
    }
  }

  def overdue = now - lastNotify > WD
  // стоимость следующей операции не укладывается в сторож
  def wouldOverrun = now + opCost - lastNotify > WD

  // Начало прохода: шаг 0 наблюдение (OB:44), получение хода (T:46); busy → no changing pass (RC:5).
  action startPass = all {
    phase == "Idle",
    now - lastPassEnd >= PASS_EVERY or (kills > 0 and runsSinceStart == 0) or now == 0,
    not(overdue),
    val seen = if (slotFirstSeen < 0) now else slotFirstSeen
    val busyNow = turnBusy and (turnSeenAt < 0 or now - turnSeenAt < TURN_TERM)
    all {
      lastNotify' = now,
      slotFirstSeen' = seen,
      if (busyNow) all {
        // ход занят: изменяющего прохода нет, следующая попытка через TURN_BUSY_RETRY
        phase' = "Busy",
        turnSeenAt' = if (turnSeenAt < 0) now else turnSeenAt,
        now' = now,
        passStart' = passStart,
        lastPassEnd' = lastPassEnd,
        decided' = decided,
        judgedNonAlive' = judgedNonAlive,
        turnBusy' = turnBusy,
      } else all {
        phase' = "Control",
        passStart' = now,
        decided' = 0,
        turnSeenAt' = -1,
        turnBusy' = true,  // взят этим процессом, отпускается в конце
        // шаг 3: судьба мёртвого слота — возраст от первого наблюдения этого судьи (FRM:6, строка 4: age >= SLOT_TERM + LOST_AFTER)
        judgedNonAlive' = (judgedNonAlive or (now - seen >= SLOT_TERM + LOST_AFTER)),
        now' = now,
        lastPassEnd' = lastPassEnd,
      },
      opCost' = opCost, budget' = budget, u' = u, kills' = kills, reports' = reports, lastPassDur' = lastPassDur, runsSinceStart' = runsSinceStart,
    },
  }

  action busyRetry = all {
    phase == "Busy",
    not(overdue),
    phase' = "Idle",
    now' = now + TURN_BUSY_RETRY,
    lastPassEnd' = now + TURN_BUSY_RETRY - PASS_EVERY,
    lastNotify' = now + TURN_BUSY_RETRY,
    opCost' = opCost, budget' = budget, passStart' = passStart, u' = u, decided' = decided, kills' = kills,
    reports' = reports, lastPassDur' = lastPassDur, turnBusy' = turnBusy, turnSeenAt' = turnSeenAt,
    slotFirstSeen' = slotFirstSeen, judgedNonAlive' = judgedNonAlive, runsSinceStart' = runsSinceStart,
  }

  // Шаг 4: одно решение стоит opCost, решение дюрабельно (u уменьшается необратимо), N:819-828.
  action decide = all {
    phase == "Control",
    u > 0,
    not(BUDGET) or decided < budget,
    not(wouldOverrun),
    now' = now + opCost,
    u' = u - 1,
    decided' = decided + 1,
    lastNotify' = if (NOTIFY_PER_DECISION) now + opCost else lastNotify,
    phase' = phase, opCost' = opCost, budget' = budget, passStart' = passStart, lastPassEnd' = lastPassEnd,
    kills' = kills, reports' = reports, lastPassDur' = lastPassDur, turnBusy' = turnBusy, turnSeenAt' = turnSeenAt,
    slotFirstSeen' = slotFirstSeen, judgedNonAlive' = judgedNonAlive, runsSinceStart' = runsSinceStart,
  }

  // Завершение управляющей части (T:56): ход сдан; дальше снимки и отчёт вне хода (N:911-912).
  action finishControl = all {
    phase == "Control",
    u == 0 or (BUDGET and decided >= budget),
    not(wouldOverrun),
    now' = now + opCost,
    phase' = "Snap",
    turnBusy' = false,
    lastNotify' = if (NOTIFY_PER_DECISION) now + opCost else lastNotify,
    opCost' = opCost, budget' = budget, passStart' = passStart, lastPassEnd' = lastPassEnd, u' = u, decided' = decided,
    kills' = kills, reports' = reports, lastPassDur' = lastPassDur, turnSeenAt' = turnSeenAt,
    slotFirstSeen' = slotFirstSeen, judgedNonAlive' = judgedNonAlive, runsSinceStart' = runsSinceStart,
  }

  // Финальный отчёт прохода (N:912) и переход в Idle: завершающее действие, фиксирует длительность.
  action finishPass = all {
    phase == "Snap",
    not(wouldOverrun),
    now' = now + opCost,
    phase' = "Idle",
    reports' = reports + 1,
    lastPassDur' = now + opCost - passStart,
    lastPassEnd' = now + opCost,
    runsSinceStart' = runsSinceStart + 1,
    lastNotify' = if (NOTIFY_PER_DECISION) now + opCost else lastNotify,
    opCost' = opCost, budget' = budget, passStart' = passStart, u' = u, decided' = decided, kills' = kills,
    turnBusy' = turnBusy, turnSeenAt' = turnSeenAt, slotFirstSeen' = slotFirstSeen, judgedNonAlive' = judgedNonAlive,
  }

  action arrive = all {
    phase != "Down",
    u < 8,
    u' = u + 1,
    now' = now, opCost' = opCost, budget' = budget, phase' = phase, lastNotify' = lastNotify, passStart' = passStart,
    lastPassEnd' = lastPassEnd, decided' = decided, kills' = kills, reports' = reports, lastPassDur' = lastPassDur,
    turnBusy' = turnBusy, turnSeenAt' = turnSeenAt, slotFirstSeen' = slotFirstSeen, judgedNonAlive' = judgedNonAlive,
    runsSinceStart' = runsSinceStart,
  }

  // Убийство сторожем: следующая операция не укладывается в WatchdogSec (L:85, 024:66-67). Ход остаётся занятым до TURN_TERM (T:75, N:800-801).
  action kill = all {
    phase == "Control" or phase == "Snap",
    wouldOverrun,
    now' = lastNotify + WD + 1,
    phase' = "Down",
    kills' = kills + 1,
    lastNotify' = lastNotify,
    opCost' = opCost, budget' = budget, passStart' = passStart, lastPassEnd' = lastPassEnd, u' = u, decided' = decided,
    reports' = reports, lastPassDur' = lastPassDur, turnBusy' = turnBusy, turnSeenAt' = turnSeenAt,
    slotFirstSeen' = slotFirstSeen, judgedNonAlive' = judgedNonAlive, runsSinceStart' = runsSinceStart,
  }

  // Перезапуск (Restart=always, L:91): новая память наблюдений (OB:44), следующий проход первым.
  action restart = all {
    phase == "Down",
    phase' = "Idle",
    now' = now + 1,
    lastNotify' = now + 1,
    lastPassEnd' = now + 1 - PASS_EVERY,
    slotFirstSeen' = -1,
    turnSeenAt' = -1,
    runsSinceStart' = 0,
    opCost' = opCost, budget' = budget, passStart' = passStart, u' = u, decided' = decided, kills' = kills,
    reports' = reports, lastPassDur' = lastPassDur, turnBusy' = turnBusy, judgedNonAlive' = judgedNonAlive,
  }

  action idle = all {
    phase == "Idle",
    now - lastPassEnd < PASS_EVERY,
    now' = lastPassEnd + PASS_EVERY,
    lastNotify' = lastPassEnd + PASS_EVERY,
    phase' = phase, opCost' = opCost, budget' = budget, passStart' = passStart, lastPassEnd' = lastPassEnd, u' = u,
    decided' = decided, kills' = kills, reports' = reports, lastPassDur' = lastPassDur, turnBusy' = turnBusy,
    turnSeenAt' = turnSeenAt, slotFirstSeen' = slotFirstSeen, judgedNonAlive' = judgedNonAlive, runsSinceStart' = runsSinceStart,
  }

  action step = any { startPass, busyRetry, decide, finishControl, finishPass, arrive, kill, restart, idle }

  // Границы и завершение
  val invNoKill = kills == 0
  // убийство не из-за одной операции длиннее сторожа, а из-за суммы операций прохода
  val invNoKillIfOpFits = opCost > WD or kills == 0
  // проход без бюджета и с notify на решение: длительность прохода не ограничена (длиннее WD без убийства)
  // Граница завершённого прохода: при фиксации завершения длительность укладывается в сторож
  val invCompletedPassWithinWd = lastPassDur <= WD
  // Завершающее действие сдало ход
  val invIdleAfterPassReleased = not(phase == "Idle" and runsSinceStart > 0) or not(turnBusy)
  // Свидетели (ожидается нарушение)
  val witKilled = kills == 0
  val witTwoKillsNoReport = not(kills >= 2 and reports == 0)
  val witTwoKillsNoJudgement = not(kills >= 2 and not(judgedNonAlive) and now >= 2 * WD and opCost <= WD)
  val witReportPublished = reports == 0
  val witCompletion = not(reports >= 1 and lastPassDur > 0)
  val witNonAlive = not(judgedNonAlive)
  val witBusyAfterKill = not(phase == "Busy" and kills >= 1)
  val witLongPassNoKill = not(lastPassDur > WD)
}

module wd_norm { import p04_pass_watchdog(BUDGET=false, NOTIFY_PER_DECISION=false).* }
module wd_budget { import p04_pass_watchdog(BUDGET=true, NOTIFY_PER_DECISION=false).* }
module wd_notify_each { import p04_pass_watchdog(BUDGET=false, NOTIFY_PER_DECISION=true).* }
