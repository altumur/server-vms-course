// Модель 5 из 6 (срез 244355d1): штатная остановка R034.
// Нормы: 01.3-store.norms.md:366 (копия: один снимок, вывод вне замка; любое завершение освобождает снимок и транспорт),
//   :368 (перестать принимать; отменить/ограничить внешний ввод-вывод; разрешить/классифицировать принятую работу; снять снимки, соединения, слушатели),
//   production-acceptance.md:50 (BUDGET_STOP), :69 (RUN-L03), 01.1:751,:764 (закрытый список причин: остановка не названа; М1).
// Граница: до 2 единиц работы, 1 копия; шаги - абстрактные, не секунды.
// ДОПУЩЕНИЕ T1: шаг остановки уменьшает меру (работа+снимки+соединения+слушатели) на столько единиц, сколько снимает — так описана конечность;
//   реальные секунды BUDGET_STOP не моделируются. Не моделируется сеть, ядро, менеджер служб, перезапуск.
module stop {
  pure val MAX_WORK = 2
  pure val MAX_CONNS = 3
  // Мутанты
  pure val MUT_ADMIT_AFTER_STOP = false
  pure val MUT_COPY_HOLDS_LOCK = false
  pure val MUT_EXIT_WITH_INFLIGHT = false
  pure val MUT_LEAK_PIN_ON_CANCEL = false
  pure val MUT_DROP_ADMITTED = false

  var phase: str         // Run | Stopping | Stopped
  var inflight: int
  var definite: int
  var ambiguous: int
  var admittedTotal: int
  var copyState: str     // none | streaming | stalled
  var copyEver: bool
  var pins: int
  var conns: int
  var listeners: int
  var lockByCopy: bool
  var stopSteps: int
  var measure0: int
  var admitAfterStop: bool
  var refusedDuringStop: str   // "" | "503" | "reset": исход неприёма при остановке (М1)
  var everCopyCancelled: bool

  def measure: int = inflight + pins + conns + listeners

  action init = all {
    phase' = "Run", inflight' = 0, definite' = 0, ambiguous' = 0, admittedTotal' = 0, copyState' = "none", copyEver' = false,
    pins' = 0, conns' = 0, listeners' = 1, lockByCopy' = false, stopSteps' = 0, measure0' = 0, admitAfterStop' = false, refusedDuringStop' = "", everCopyCancelled' = false,
  }

  action acceptConn = all {
    phase == "Run", conns < MAX_CONNS,
    conns' = conns + 1,
    phase' = phase, inflight' = inflight, definite' = definite, ambiguous' = ambiguous, admittedTotal' = admittedTotal, copyState' = copyState, copyEver' = copyEver, pins' = pins, listeners' = listeners, lockByCopy' = lockByCopy, stopSteps' = stopSteps, measure0' = measure0, admitAfterStop' = admitAfterStop, refusedDuringStop' = refusedDuringStop, everCopyCancelled' = everCopyCancelled,
  }
  action admitWork = all {
    admittedTotal < MAX_WORK,
    if (phase == "Run") true else (MUT_ADMIT_AFTER_STOP and phase == "Stopping"),
    conns > 0 or MUT_ADMIT_AFTER_STOP,
    inflight' = inflight + 1, admittedTotal' = admittedTotal + 1,
    admitAfterStop' = (admitAfterStop or phase != "Run"),
    phase' = phase, definite' = definite, ambiguous' = ambiguous, copyState' = copyState, copyEver' = copyEver, pins' = pins, conns' = conns, listeners' = listeners, lockByCopy' = lockByCopy, stopSteps' = stopSteps, measure0' = measure0, refusedDuringStop' = refusedDuringStop, everCopyCancelled' = everCopyCancelled,
  }
  // Запрос, не принятый при остановке: норма не называет единственный исход (М1).
  action requestDuringStop = {
    nondet o = Set("503", "reset").oneOf()
    all {
      phase == "Stopping",
      refusedDuringStop' = o,
      phase' = phase, inflight' = inflight, definite' = definite, ambiguous' = ambiguous, admittedTotal' = admittedTotal, copyState' = copyState, copyEver' = copyEver, pins' = pins, conns' = conns, listeners' = listeners, lockByCopy' = lockByCopy, stopSteps' = stopSteps, measure0' = measure0, admitAfterStop' = admitAfterStop, everCopyCancelled' = everCopyCancelled,
    }
  }
  action beginCopy = all {
    phase == "Run", copyState == "none", conns > 0,
    copyState' = "streaming", copyEver' = true, pins' = pins + 1,
    lockByCopy' = MUT_COPY_HOLDS_LOCK,
    phase' = phase, inflight' = inflight, definite' = definite, ambiguous' = ambiguous, admittedTotal' = admittedTotal, conns' = conns, listeners' = listeners, stopSteps' = stopSteps, measure0' = measure0, admitAfterStop' = admitAfterStop, refusedDuringStop' = refusedDuringStop, everCopyCancelled' = everCopyCancelled,
  }
  action stallCopy = all {
    phase == "Run", copyState == "streaming",
    copyState' = "stalled",
    phase' = phase, inflight' = inflight, definite' = definite, ambiguous' = ambiguous, admittedTotal' = admittedTotal, copyEver' = copyEver, pins' = pins, conns' = conns, listeners' = listeners, lockByCopy' = lockByCopy, stopSteps' = stopSteps, measure0' = measure0, admitAfterStop' = admitAfterStop, refusedDuringStop' = refusedDuringStop, everCopyCancelled' = everCopyCancelled,
  }
  action copyDone = all {
    phase == "Run", copyState != "none",
    copyState' = "none", pins' = pins - 1, lockByCopy' = false,
    conns' = conns - 1,
    phase' = phase, inflight' = inflight, definite' = definite, ambiguous' = ambiguous, admittedTotal' = admittedTotal, copyEver' = copyEver, listeners' = listeners, stopSteps' = stopSteps, measure0' = measure0, admitAfterStop' = admitAfterStop, refusedDuringStop' = refusedDuringStop, everCopyCancelled' = everCopyCancelled,
  }
  action finishWork = {
    nondet definiteOutcome = Set(true, false).oneOf()
    all {
      phase == "Run", inflight > 0,
      inflight' = inflight - 1,
      definite' = definite + 1,
      phase' = phase, ambiguous' = ambiguous, admittedTotal' = admittedTotal, copyState' = copyState, copyEver' = copyEver, pins' = pins, conns' = conns, listeners' = listeners, lockByCopy' = lockByCopy, stopSteps' = stopSteps, measure0' = measure0, admitAfterStop' = admitAfterStop, refusedDuringStop' = refusedDuringStop, everCopyCancelled' = everCopyCancelled,
    }
  }
  action sigterm = all {
    phase == "Run",
    phase' = "Stopping", measure0' = measure, stopSteps' = 0,
    inflight' = inflight, definite' = definite, ambiguous' = ambiguous, admittedTotal' = admittedTotal, copyState' = copyState, copyEver' = copyEver, pins' = pins, conns' = conns, listeners' = listeners, lockByCopy' = lockByCopy, admitAfterStop' = admitAfterStop, refusedDuringStop' = refusedDuringStop, everCopyCancelled' = everCopyCancelled,
  }
  action cancelCopy = all {
    phase == "Stopping", copyState != "none",
    copyState' = "none", pins' = if (MUT_LEAK_PIN_ON_CANCEL) pins else pins - 1, lockByCopy' = false,
    conns' = conns - 1, stopSteps' = stopSteps + 2, everCopyCancelled' = true,  // снимок и соединение копии — две единицы меры
    phase' = phase, inflight' = inflight, definite' = definite, ambiguous' = ambiguous, admittedTotal' = admittedTotal, copyEver' = copyEver, listeners' = listeners, measure0' = measure0, admitAfterStop' = admitAfterStop, refusedDuringStop' = refusedDuringStop,
  }
  action resolveWork = {
    nondet definiteOutcome = Set(true, false).oneOf()
    all {
      phase == "Stopping", inflight > 0,
      inflight' = inflight - 1,
      definite' = if (MUT_DROP_ADMITTED) definite else if (definiteOutcome) definite + 1 else definite,
      ambiguous' = if (MUT_DROP_ADMITTED) ambiguous else if (definiteOutcome) ambiguous else ambiguous + 1,
      stopSteps' = stopSteps + 1,
      phase' = phase, admittedTotal' = admittedTotal, copyState' = copyState, copyEver' = copyEver, pins' = pins, conns' = conns, listeners' = listeners, lockByCopy' = lockByCopy, measure0' = measure0, admitAfterStop' = admitAfterStop, refusedDuringStop' = refusedDuringStop, everCopyCancelled' = everCopyCancelled,
    }
  }
  action closeConn = all {
    phase == "Stopping", conns > 0, copyState == "none",
    conns' = conns - 1, stopSteps' = stopSteps + 1,
    phase' = phase, inflight' = inflight, definite' = definite, ambiguous' = ambiguous, admittedTotal' = admittedTotal, copyState' = copyState, copyEver' = copyEver, pins' = pins, listeners' = listeners, lockByCopy' = lockByCopy, measure0' = measure0, admitAfterStop' = admitAfterStop, refusedDuringStop' = refusedDuringStop, everCopyCancelled' = everCopyCancelled,
  }
  action closeListeners = all {
    phase == "Stopping", listeners > 0,
    listeners' = 0, stopSteps' = stopSteps + 1,
    phase' = phase, inflight' = inflight, definite' = definite, ambiguous' = ambiguous, admittedTotal' = admittedTotal, copyState' = copyState, copyEver' = copyEver, pins' = pins, conns' = conns, lockByCopy' = lockByCopy, measure0' = measure0, admitAfterStop' = admitAfterStop, refusedDuringStop' = refusedDuringStop, everCopyCancelled' = everCopyCancelled,
  }
  action exitStop = all {
    phase == "Stopping",
    MUT_EXIT_WITH_INFLIGHT or (inflight == 0 and pins == 0 and conns == 0 and listeners == 0),
    phase' = "Stopped",
    stopSteps' = stopSteps,
    inflight' = inflight, definite' = definite, ambiguous' = ambiguous, admittedTotal' = admittedTotal, copyState' = copyState, copyEver' = copyEver, pins' = pins, conns' = conns, listeners' = listeners, lockByCopy' = lockByCopy, measure0' = measure0, admitAfterStop' = admitAfterStop, refusedDuringStop' = refusedDuringStop, everCopyCancelled' = everCopyCancelled,
  }
  action stutter = all {
    phase' = phase, inflight' = inflight, definite' = definite, ambiguous' = ambiguous, admittedTotal' = admittedTotal, copyState' = copyState, copyEver' = copyEver, pins' = pins, conns' = conns, listeners' = listeners, lockByCopy' = lockByCopy, stopSteps' = stopSteps, measure0' = measure0, admitAfterStop' = admitAfterStop, refusedDuringStop' = refusedDuringStop, everCopyCancelled' = everCopyCancelled,
  }
  action step = any { acceptConn, admitWork, requestDuringStop, beginCopy, stallCopy, copyDone, finishWork, sigterm, cancelCopy, resolveWork, closeConn, closeListeners, exitStop, stutter }

  // === ИНВАРИАНТЫ ===
  val inv_noAdmitAfterStop = not(admitAfterStop)
  val inv_copyNoLock = not(copyState != "none" and lockByCopy)
  val inv_exitClean = phase == "Stopped" implies (inflight == 0 and pins == 0 and conns == 0 and listeners == 0)
  val inv_workClassified = admittedTotal == inflight + definite + ambiguous
  val inv_pinsMatchCopy = pins == (if (copyState != "none") 1 else 0)
  // Конечность: в Stopping каждый шаг снижает меру на 1; шагов не больше исходной меры.
  val inv_rank = phase == "Stopping" implies (stopSteps <= measure0 and measure == measure0 - stopSteps)

  // === СВИДЕТЕЛИ ===
  val not_w_stopNoCopy = not(phase == "Stopped" and admittedTotal > 0 and not(copyEver))
  val not_w_stop503 = not(refusedDuringStop == "503")
  val not_w_stopReset = not(refusedDuringStop == "reset")
  val not_w_stalledCancel = not(phase == "Stopped" and everCopyCancelled)
  val not_w_ambiguousAtStop = not(ambiguous > 0)
}
