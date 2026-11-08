// P/03: штатная остановка по SIGTERM. Гонки только во времени и порядке шагов.
// Время в тиках 1/12 с. Шаги: spec/03.4:411-417. Срок: forms и 02.1 (stop_timeout 20..50 с,
// TimeoutStopSec, 02.1:235, 03.4:508-510). SIGKILL по сроку: немой обрыв, 03.4:421.
// Условие may_write на шагах остановки: spec/03.6:76-77.
// Модель не моделирует реализацию: длительность каждого шага — выбор окружения.
module p03_stop {
  const STOP_TIMEOUT: int        // stop_timeout, тиков
  const STEP_DUR: Set[int]       // длительность шагов (выбор окружения)
  const LAST_RENEW_AGE: Set[int] // давность последнего подтверждённого обновления при SIGTERM
  const ORDER_MUT: str           // "none" | "slot_before_place" | "standin_after_release"
  const STANDIN_REREAD: bool     // заместитель перечитывает строку перед обновлением (R029)
  // Контроль (не норма): бюджет шагов с исчерпанием — переход к шагу 4
  const STEP_BUDGET: int         // 0: нет бюджета

  pure val W = 300           // окно действий
  pure val SLOT_TERM = 540   // 45 с
  pure val HOLD_SKEW = 60    // 5 с
  pure val WRITE_WINDOW = SLOT_TERM - HOLD_SKEW  // 03.2:51
  pure val RENEW_EVERY = 100 // 03.2:90

  // standin_stop -> before_all -> stop_units -> heartbeat -> place_go -> slot_go -> after_stop -> done | killed

  var now: int
  var phase: str
  var phaseEnds: int
  var killAt: int
  var lastRenew: int
  var standinOn: bool
  var slotHeld: bool
  var slotReleased: bool
  var placeHeld: bool
  var stoppedUnits: bool
  var everWriteAfterRelease: bool
  var everStandinAfterRelease: bool
  var everKilled: bool
  var everFinalWriteOutside: bool
  var everHungPastTimeout: bool
  var everBudgetPass: bool

  action init = {
    nondet age = oneOf(LAST_RENEW_AGE)
    all {
    now' = 0, phase' = "standin_stop", phaseEnds' = 0, killAt' = STOP_TIMEOUT,
    lastRenew' = 0 - age, standinOn' = true, slotHeld' = true, slotReleased' = false,
    placeHeld' = true, stoppedUnits' = false,
    everWriteAfterRelease' = false, everStandinAfterRelease' = false, everKilled' = false,
    everFinalWriteOutside' = false, everHungPastTimeout' = false, everBudgetPass' = false
    }
  }

  pure def nextPhase(p: str, mut: str): str =
    if (mut == "slot_before_place") {
      if (p == "standin_stop") "before_all" else if (p == "before_all") "stop_units"
      else if (p == "stop_units") "heartbeat" else if (p == "heartbeat") "slot_go"
      else if (p == "slot_go") "place_go" else if (p == "place_go") "after_stop"
      else "done"
    } else {
      if (p == "standin_stop") "before_all" else if (p == "before_all") "stop_units"
      else if (p == "stop_units") "heartbeat" else if (p == "heartbeat") "place_go"
      else if (p == "place_go") "slot_go" else if (p == "slot_go") "after_stop"
      else "done"
    }

  // Шаг завершён к моменту phaseEnds; при стоп-таймауте раньше — SIGKILL
  action finishPhase = all {
    now <= phaseEnds, phase != "done", phase != "killed",
    if (phaseEnds >= killAt) all {
      // SIGKILL приходит раньше конца шага: немой обрыв, ничего не пишется
      now' = killAt, phase' = "killed", phaseEnds' = killAt,
      everKilled' = true,
      everHungPastTimeout' = true,
      lastRenew' = lastRenew, standinOn' = false, slotHeld' = slotHeld, slotReleased' = slotReleased,
      placeHeld' = placeHeld, stoppedUnits' = stoppedUnits,
      everWriteAfterRelease' = everWriteAfterRelease, everStandinAfterRelease' = everStandinAfterRelease,
      killAt' = killAt, everFinalWriteOutside' = everFinalWriteOutside, everBudgetPass' = everBudgetPass,
    } else {
      val p = phase
      val t = phaseEnds
      val winEnd = lastRenew + W
      nondet d = oneOf(STEP_DUR)
      val capped = if (STEP_BUDGET > 0 and d > STEP_BUDGET) STEP_BUDGET else d
      all {
        now' = t,
        killAt' = killAt,
        phase' = nextPhase(p, ORDER_MUT),
        phaseEnds' = t + capped,
        lastRenew' = lastRenew,
        everKilled' = everKilled,
        everHungPastTimeout' = everHungPastTimeout,
        everBudgetPass' = (everBudgetPass or (STEP_BUDGET > 0 and d > STEP_BUDGET)),
        standinOn' = if (p == "standin_stop" and ORDER_MUT != "standin_after_release") false
                     else if (p == "after_stop") false else standinOn,
        stoppedUnits' = (stoppedUnits or p == "stop_units"),
        slotReleased' = (slotReleased or p == "slot_go"),
        slotHeld' = if (p == "slot_go") false else slotHeld,
        placeHeld' = if (p == "place_go") false else placeHeld,
        // Отпуск места — запись под защитой своего слота: после release писать нельзя (03.2:430)
        everWriteAfterRelease' = (everWriteAfterRelease or (p == "place_go" and slotReleased)),
        // Заместитель работает, пока не остановлен: перечитывает строку и видит released (R029)
        everStandinAfterRelease' = (everStandinAfterRelease or (standinOn and slotReleased and not(STANDIN_REREAD))),
        // Шаг остановки единиц (финальная запись состояния) идёт под may_write (03.6:76-77)
        everFinalWriteOutside' = (everFinalWriteOutside or (p == "stop_units" and t >= winEnd)),
      }
    }
  }

  action step = any {
    finishPhase,
    all {
      now' = now, phase' = phase, phaseEnds' = phaseEnds, killAt' = killAt, lastRenew' = lastRenew,
      standinOn' = standinOn, slotHeld' = slotHeld, slotReleased' = slotReleased, placeHeld' = placeHeld,
      stoppedUnits' = stoppedUnits, everWriteAfterRelease' = everWriteAfterRelease,
      everStandinAfterRelease' = everStandinAfterRelease, everKilled' = everKilled,
      everFinalWriteOutside' = everFinalWriteOutside, everHungPastTimeout' = everHungPastTimeout,
      everBudgetPass' = everBudgetPass,
      phase == "done" or phase == "killed"
    }
  }

  // Правила 03.4:412-417, 03.2:429-430
  val NoWriteAfterRelease = not(everWriteAfterRelease)
  val NoStandinWriteAfterRelease = not(everStandinAfterRelease)
  val PlaceBeforeSlot = not(slotReleased) or not(placeHeld)
  // Бюджет: остановка завершена отдачей слота, а не сроком (С4)
  val KilledImpliesReleased = not(everKilled) or slotReleased
  val DoneReleased = phase != "done" or slotReleased

  // Цена из 03.4:510: «бюджет» после SIGTERM не меньше WRITE_WINDOW - RENEW_EVERY от посылки подтверждения.
  // Проверяем арифметику при давности не больше RENEW_EVERY и при больше (шаг стоял).
  val PlaceBudgetGuaranteed = (WRITE_WINDOW + lastRenew) >= WRITE_WINDOW - RENEW_EVERY

  // Сводка окон подавления при остановке пишется под may_write (03.6:77); при off окно закрыто после last + W
  val FinalFlushInMayWrite = not(everFinalWriteOutside)

  val W_done = phase != "done"
  val W_killed = phase != "killed"
  val W_budget_used = not(everBudgetPass)
}
