// Модель 3 из 6 (срез 244355d1): прерванный локальный recover (С2 отчёта).
// Нормы (по тексту): 01.3-store.norms.md:331-332 (шаги дамп/журнал/строки/floor), :123 (floor только растёт),
//   :112-114 (генерация из upper, включая сохранённое состояние), :40 (отказ старта называет только import/restore),
//   :353 (фазы при отказе — для import/restore), :346 (одна попытка — правило лицензии, не проверяется).
// Модель: порядок шагов recover нормой не задан — порядок свободен (nondet), прерывание возможно между шагами.
// Что НЕ определено нормой: атомарность перезаписи дампа/журнала, порядок шагов, отказ старта на незавершённом recover,
//   правило повтора (кроме роста floor). Поэтому свидетели ниже показывают: «текст не исключает», а не «дефект реализации».
// ДОПУЩЕНИЯ (флаги): ATOMIC_PUBLISH и REFUSE_ON_PARTIAL — контрольный вариант, нормой не заданы.
// Граница: один узел, один повтор, HOUR модельный.
module recover {
  pure val ATOMIC_PUBLISH = false
  pure val REFUSE_ON_PARTIAL = false
  pure val MAX_RUNS = 3
  pure val HOUR = 5
  // Мутанты
  pure val MUT_FLOOR_DOWN = false
  pure val MUT_COMPLETE_EARLY = false

  var dump: str        // old | partial | new
  var wal: str         // old | partial | new
  var rowsRemoved: bool
  var floorGen: int
  var running: bool
  var runs: int
  var floorDoneThisRun: bool
  var complete: bool   // завершён успешно (последний запуск дошёл до конца)
  var started: bool
  var startedOnPartial: bool
  var genHistoryOk: bool  // floor не убывал

  action init = all {
    dump' = "old", wal' = "old", rowsRemoved' = false, floorGen' = 1,
    running' = false, runs' = 0, floorDoneThisRun' = false, complete' = false,
    started' = false, startedOnPartial' = false, genHistoryOk' = true,
  }

  def consistent: bool = dump != "partial" and wal != "partial" and ((dump == "new" and wal == "new") or (dump == "old" and wal == "old")) and rowsRemoved == (dump == "new")

  action begin = all {
    not(running), not(started), runs < MAX_RUNS,
    running' = true, runs' = runs + 1, floorDoneThisRun' = false, complete' = false,
    dump' = dump, wal' = wal, rowsRemoved' = rowsRemoved, floorGen' = floorGen, started' = started, startedOnPartial' = startedOnPartial, genHistoryOk' = genHistoryOk,
  }

  // Шаги в свободном порядке; без атомарной публикации виден "partial".
  action stepDump = all {
    running, dump != "new",
    dump' = if (ATOMIC_PUBLISH) "new" else if (dump == "old") "partial" else "new",
    rowsRemoved' = if (ATOMIC_PUBLISH or dump == "partial") true else rowsRemoved,
    wal' = wal, floorGen' = floorGen, running' = running, runs' = runs, floorDoneThisRun' = floorDoneThisRun, complete' = complete, started' = started, startedOnPartial' = startedOnPartial, genHistoryOk' = genHistoryOk,
  }
  action stepWal = all {
    running, wal != "new",
    wal' = if (ATOMIC_PUBLISH) "new" else if (wal == "old") "partial" else "new",
    dump' = dump, rowsRemoved' = rowsRemoved, floorGen' = floorGen, running' = running, runs' = runs, floorDoneThisRun' = floorDoneThisRun, complete' = complete, started' = started, startedOnPartial' = startedOnPartial, genHistoryOk' = genHistoryOk,
  }
  action stepFloor = {
    val newG = if (MUT_FLOOR_DOWN and runs > 1) floorGen - 1 else (if (floorGen + 1 > HOUR) floorGen + 1 else HOUR)
    all {
      running, not(floorDoneThisRun),
      floorGen' = newG,
      floorDoneThisRun' = true,
      genHistoryOk' = (genHistoryOk and (newG >= floorGen)),
      dump' = dump, wal' = wal, rowsRemoved' = rowsRemoved, running' = running, runs' = runs, complete' = complete, started' = started, startedOnPartial' = startedOnPartial,
    }
  }
  action finish = all {
    running,
    MUT_COMPLETE_EARLY or (dump == "new" and wal == "new" and floorDoneThisRun),
    running' = false, complete' = true,
    dump' = dump, wal' = wal, rowsRemoved' = rowsRemoved, floorGen' = floorGen, runs' = runs, floorDoneThisRun' = floorDoneThisRun, started' = started, startedOnPartial' = startedOnPartial, genHistoryOk' = genHistoryOk,
  }
  // Прерывание: не отменяет уже сделанные шаги (нормой не задано иное).
  action interrupt = all {
    running,
    running' = false, complete' = false,
    dump' = dump, wal' = wal, rowsRemoved' = rowsRemoved, floorGen' = floorGen, runs' = runs, floorDoneThisRun' = floorDoneThisRun, started' = started, startedOnPartial' = startedOnPartial, genHistoryOk' = genHistoryOk,
  }
  // Старт демона: текст не запрещает на незавершённом recover, FORMAT цел. С REFUSE_ON_PARTIAL (допущение) отказ.
  action startDaemon = all {
    not(running), not(started),
    if (REFUSE_ON_PARTIAL) (complete or consistent) else true,
    started' = true,
    startedOnPartial' = (startedOnPartial or not(consistent)),
    dump' = dump, wal' = wal, rowsRemoved' = rowsRemoved, floorGen' = floorGen, running' = running, runs' = runs, floorDoneThisRun' = floorDoneThisRun, complete' = complete, genHistoryOk' = genHistoryOk,
  }
  action stutter = all {
    dump' = dump, wal' = wal, rowsRemoved' = rowsRemoved, floorGen' = floorGen, running' = running, runs' = runs, floorDoneThisRun' = floorDoneThisRun, complete' = complete, started' = started, startedOnPartial' = startedOnPartial, genHistoryOk' = genHistoryOk,
  }
  action step = any { begin, stepDump, stepWal, stepFloor, finish, interrupt, startDaemon, stutter }

  // По тексту: floor только растёт (:123), завершённый запуск даёт новый дамп/журнал/floor (:331-332).
  val inv_floorGrows = genHistoryOk
  val inv_completeConsistent = complete implies (dump == "new" and wal == "new" and rowsRemoved and floorDoneThisRun)
  // Контроль (не из текста): при атомарной публикации и отказе старта на незавершённом — старт только на согласованном.
  val inv_noStartOnPartial_control = not(startedOnPartial)

  // Свидетели (не исключено текстом):
  val not_w_startOnPartialDump = not(started and startedOnPartial and dump == "partial")
  val not_w_dumpNewWalOld = not(not(running) and dump == "new" and wal == "old" and not(complete))
  val not_w_floorOnlyRaised = not(not(running) and floorGen > 1 and dump == "old" and wal == "old")
  val not_w_startOnOldWithFloor = not(started and floorGen > 1 and dump == "old" and wal == "old" and not(complete))
  // повтор после прерывания на шаге floor — новая генерация (первый запуск 5, повтор 6).
  val not_w_retryNewGen = not(runs >= 2 and floorGen >= 6)
}
