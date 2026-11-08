// Модель 2 из 6 (P/01 пп. 9-14, срез 244355d1): прерванный import/restore в группе (С1 отчёта).
// Нормы (по тексту): 01.3-store.norms.md:40 (отказ старта на незавершённой попытке, код 2 — без оговорки «только box»),
//   :104 (import в группе только на admin.sock лидера), :109-110 (завершённая — отказ, незавершённая — replay),
//   :120 (floor — первая запись), :133-135 (писатель ждёт «Done»), :147-152 (Transfer, replay, новая попытка — новая генерация,
//   «daemon does not start ... the log — repeat import with the same input»), 01.3:353-355 (фазы), 02.4:48 (RestartPreventExitStatus=2).
// «По тексту»: отказ старта и маршрут admin.sock. Допущения - только флаги ниже, каждый назван в отчёте как допущение.
// Абстракция Raft (допущение G1): группа хранит общую фазу; лидер выбирается только из up-узлов большинства,
//   имеющих состояние группы (полнота журнала). Один лидер, потерь журнала нет. Рестарт только из каталога узла.
// Не моделируется: сами строки и их формы, проверка входа, манифесты, сеть, таймауты.
// Граница: 3 узла (BOX: 1), R строк, 1 вход. Параметры R, HOUR, UPPER - модельные.
module import_group {
  // === КОНФИГУРАЦИЯ ===
  pure val NODES = Set("a", "b", "c")
  pure val R = 2                           // строк входа
  pure val INPUT_GEN = 1                   // генерация upper входа (абстрактно)
  pure val BOX = false                     // box: один узел; import — офлайн (01.3:104, :169-170)
  pure val READING_BOX_ONLY = false        // ЧТЕНИЕ: отказ старта :40 относится только к box (норма этого не пишет)
  pure val ALLOW_REBUILD_GROUP = false     // ДОПУЩЕНИЕ: пересборка свежей группы в новых каталогах как новая попытка (:132, :150, маршрут не назван)
  // Мутанты
  pure val MUT_NO_HOLD = false             // писатель допускается во время переноса
  pure val MUT_DONE_EARLY = false          // Done без полного переноса
  pure val MUT_REPLAY_NEW_FLOOR = false    // replay берёт новую генерацию

  pure val PHASES = Set("Idle", "Floor", "Transfer", "Done")
  pure val HOURS = Set(1, 2)
  pure def isUnfinished(p: str): bool = p == "Floor" or p == "Transfer"
  pure def maxI(a: int, b: int): int = if (a > b) a else b
  pure def genOf(savedGen: int, hour: int): int = maxI(maxI(INPUT_GEN, savedGen) + 1, hour)

  var up: str -> bool
  var leader: str
  var phase: str             // фаза группы (реплицируемая часть)
  var rowsDone: int
  var floorGen: int
  var dirPhase: str -> str   // фаза в каталоге узла
  var dirRows: str -> int
  var dirGen: str -> int
  var refused: str -> bool   // старт отказан кодом 2 и не перезапускается (02.4:48)
  var writesInAttempt: int   // писатели, допущенные во время незавершённой попытки
  var attempts: int
  var attemptGen: int        // генерация текущей попытки
  var lastAttemptGen: int    // генерация предыдущей попытки в истории (для новой попытки)
  var hour: int
  var rebuilds: int
  var outageSeen: bool      // все узлы были down при незавершённой попытке

  action init = all {
    up' = NODES.mapBy(n => true),
    leader' = if (BOX) "" else "a",
    phase' = "Idle", rowsDone' = 0, floorGen' = 0,
    dirPhase' = NODES.mapBy(n => "Idle"), dirRows' = NODES.mapBy(n => 0), dirGen' = NODES.mapBy(n => 0),
    refused' = NODES.mapBy(n => false),
    writesInAttempt' = 0, attempts' = 0, attemptGen' = 0, lastAttemptGen' = 0, hour' = 1, rebuilds' = 0, outageSeen' = false,
  }

  def majority: int = NODES.size() / 2 + 1
  def upCount: int = NODES.filter(n => up.get(n)).size()
  // :40 — незавершённая попытка в каталоге мешает старту. В чтении box-only отказ только на box.
  def startRefusedBy(n: str): bool = isUnfinished(dirPhase.get(n)) and (BOX or not(READING_BOX_ONLY))
  // Уже-допустимый маршрут импорта: только admin.sock живого лидера группы, на box — офлайн.
  def importRouteOpen: bool = if (BOX) not(up.get("a")) else (leader != "" and up.get(leader))

  // Применить состояние группы к каталогам up-узлов.
  def applyDirPhase(p: str): str -> str = NODES.mapBy(n => if (up.get(n)) p else dirPhase.get(n))
  def applyDirRows(r: int): str -> int = NODES.mapBy(n => if (up.get(n)) r else dirRows.get(n))
  def applyDirGen(g: int): str -> int = NODES.mapBy(n => if (up.get(n)) g else dirGen.get(n))

  action importStart = {
    all {
      phase == "Idle",
      importRouteOpen,
      attempts < 3,
      val savedGen = if (BOX) dirGen.get("a") else dirGen.get(leader)
      val g = genOf(savedGen, hour)
      all {
        phase' = "Floor", rowsDone' = 0, floorGen' = g,
        dirPhase' = if (BOX) NODES.mapBy(n => "Floor") else applyDirPhase("Floor"),
        dirRows' = if (BOX) NODES.mapBy(n => 0) else applyDirRows(0),
        dirGen' = if (BOX) NODES.mapBy(n => g) else applyDirGen(g),
        attempts' = attempts + 1,
        attemptGen' = g,
        lastAttemptGen' = attemptGen,
        up' = up, leader' = leader, refused' = refused, writesInAttempt' = writesInAttempt, hour' = hour, rebuilds' = rebuilds, outageSeen' = outageSeen,
      }
    }
  }

  action importStep = {
    all {
      isUnfinished(phase),
      importRouteOpen,
      rowsDone < R,
      val g2 = if (MUT_REPLAY_NEW_FLOOR) genOf(floorGen, hour) else floorGen
      all {
        phase' = "Transfer", rowsDone' = rowsDone + 1, floorGen' = g2,
        dirPhase' = if (BOX) NODES.mapBy(n => "Transfer") else applyDirPhase("Transfer"),
        dirRows' = if (BOX) NODES.mapBy(n => rowsDone + 1) else applyDirRows(rowsDone + 1),
        dirGen' = if (BOX) NODES.mapBy(n => g2) else applyDirGen(g2),
        up' = up, leader' = leader, refused' = refused, writesInAttempt' = writesInAttempt, attempts' = attempts, attemptGen' = attemptGen,
        lastAttemptGen' = lastAttemptGen, hour' = hour, rebuilds' = rebuilds, outageSeen' = outageSeen,
      }
    }
  }

  action importDone = all {
    isUnfinished(phase),
    importRouteOpen,
    (MUT_DONE_EARLY or rowsDone == R),
    phase' = "Done",
    dirPhase' = if (BOX) NODES.mapBy(n => "Done") else applyDirPhase("Done"),
    dirRows' = dirRows, dirGen' = dirGen, rowsDone' = rowsDone, floorGen' = floorGen, up' = up, leader' = leader,
    refused' = refused, writesInAttempt' = writesInAttempt, attempts' = attempts, attemptGen' = attemptGen,
    lastAttemptGen' = lastAttemptGen, hour' = hour, rebuilds' = rebuilds, outageSeen' = outageSeen,
  }

  action powerOff = {
    nondet n = NODES.oneOf()
    all {
      up.get(n),
      up' = up.set(n, false),
      leader' = if (leader == n) "" else leader,
      phase' = phase, rowsDone' = rowsDone, floorGen' = floorGen, dirPhase' = dirPhase, dirRows' = dirRows, dirGen' = dirGen,
      refused' = refused, writesInAttempt' = writesInAttempt, attempts' = attempts, attemptGen' = attemptGen,
      lastAttemptGen' = lastAttemptGen, hour' = hour, rebuilds' = rebuilds,
      outageSeen' = (outageSeen or (isUnfinished(phase) and NODES.forall(m => m == n or not(up.get(m))))),
    }
  }

  // Старт демона. Отказ по :40 (кодом 2) — узел остаётся down и не перезапускается автоматически.
  action start = {
    nondet n = NODES.oneOf()
    all {
      not(up.get(n)),
      not(refused.get(n)),
      if (startRefusedBy(n)) all { refused' = refused.set(n, true), up' = up, leader' = leader }
      else all { refused' = refused, up' = up.set(n, true), leader' = leader },
      phase' = phase, rowsDone' = rowsDone, floorGen' = floorGen, dirPhase' = dirPhase, dirRows' = dirRows, dirGen' = dirGen,
      writesInAttempt' = writesInAttempt, attempts' = attempts, attemptGen' = attemptGen, lastAttemptGen' = lastAttemptGen, hour' = hour, rebuilds' = rebuilds, outageSeen' = outageSeen,
    }
  }

  action elect = {
    nondet n = NODES.oneOf()
    all {
      not(BOX),
      up.get(n),
      leader == "",
      upCount >= majority,
      dirPhase.get(n) == phase and dirRows.get(n) == rowsDone and dirGen.get(n) == floorGen,   // полнота журнала
      leader' = n,
      up' = up, refused' = refused, phase' = phase, rowsDone' = rowsDone, floorGen' = floorGen, dirPhase' = dirPhase, dirRows' = dirRows,
      dirGen' = dirGen, writesInAttempt' = writesInAttempt, attempts' = attempts, attemptGen' = attemptGen, lastAttemptGen' = lastAttemptGen, hour' = hour, rebuilds' = rebuilds, outageSeen' = outageSeen,
    }
  }

  // Догоняющая репликация отставшего up-узла из состояния группы.
  action catchUp = {
    nondet n = NODES.oneOf()
    all {
      not(BOX),
      up.get(n),
      leader != "",
      not(dirPhase.get(n) == phase and dirRows.get(n) == rowsDone),
      dirPhase' = dirPhase.set(n, phase), dirRows' = dirRows.set(n, rowsDone), dirGen' = dirGen.set(n, floorGen),
      up' = up, leader' = leader, refused' = refused, phase' = phase, rowsDone' = rowsDone, floorGen' = floorGen,
      writesInAttempt' = writesInAttempt, attempts' = attempts, attemptGen' = attemptGen, lastAttemptGen' = lastAttemptGen, hour' = hour, rebuilds' = rebuilds, outageSeen' = outageSeen,
    }
  }

  // Обычный писатель: на лидере; во время переноса ждёт «Done» (01.3:133-135).
  action writerWrite = {
    all {
      if (BOX) up.get("a") else leader != "",
      if (isUnfinished(phase)) MUT_NO_HOLD else true,
      writesInAttempt' = if (isUnfinished(phase)) writesInAttempt + 1 else writesInAttempt,
      up' = up, leader' = leader, phase' = phase, rowsDone' = rowsDone, floorGen' = floorGen, dirPhase' = dirPhase, dirRows' = dirRows,
      dirGen' = dirGen, refused' = refused, attempts' = attempts, attemptGen' = attemptGen, lastAttemptGen' = lastAttemptGen, hour' = hour, rebuilds' = rebuilds, outageSeen' = outageSeen,
    }
  }

  action tickHour = {
    nondet h = HOURS.oneOf()
    all {
      h > hour,
      hour' = h,
      up' = up, leader' = leader, phase' = phase, rowsDone' = rowsDone, floorGen' = floorGen, dirPhase' = dirPhase, dirRows' = dirRows,
      dirGen' = dirGen, refused' = refused, writesInAttempt' = writesInAttempt, attempts' = attempts, attemptGen' = attemptGen, lastAttemptGen' = lastAttemptGen, rebuilds' = rebuilds, outageSeen' = outageSeen,
    }
  }

  // Допущение: оператор удаляет каталоги и собирает свежую группу (маршрут не назван нормой как выход из С1).
  action rebuildGroup = all {
    ALLOW_REBUILD_GROUP,
    NODES.forall(n => not(up.get(n))),
    isUnfinished(phase),
    rebuilds < 2,
    up' = NODES.mapBy(n => true),
    leader' = if (BOX) "" else "a",
    phase' = "Idle", rowsDone' = 0, floorGen' = 0,
    dirPhase' = NODES.mapBy(n => "Idle"), dirRows' = NODES.mapBy(n => 0), dirGen' = NODES.mapBy(n => 0),
    refused' = NODES.mapBy(n => false),
    writesInAttempt' = writesInAttempt, attempts' = attempts, attemptGen' = attemptGen, lastAttemptGen' = lastAttemptGen, hour' = hour,
    rebuilds' = rebuilds + 1, outageSeen' = outageSeen,
  }

  action stutter = all {
    up' = up, leader' = leader, phase' = phase, rowsDone' = rowsDone, floorGen' = floorGen, dirPhase' = dirPhase, dirRows' = dirRows,
    dirGen' = dirGen, refused' = refused, writesInAttempt' = writesInAttempt, attempts' = attempts, attemptGen' = attemptGen, lastAttemptGen' = lastAttemptGen, hour' = hour, rebuilds' = rebuilds, outageSeen' = outageSeen,
  }

  action step = any { importStart, importStep, importDone, powerOff, start, elect, catchUp, writerWrite, tickHour, rebuildGroup, stutter }

  // === ЧТО ГАРАНТИРУЕТ ТЕКСТ ===
  val inv_noWriterBeforeDone = writesInAttempt == 0
  val inv_doneComplete = phase == "Done" implies rowsDone == R
  val inv_floorFirst = (rowsDone > 0) implies floorGen > 0
  // replay продолжает ту же попытку с тем же floor (:149-150): пока фаза незавершена, floor не меняется.
  val inv_floorStableInAttempt = isUnfinished(phase) implies floorGen == attemptGen

  // === ВЫХОД: что значит «назван законный выход» ===
  def canStart(n: str): bool = not(up.get(n)) and not(startRefusedBy(n))
  def canFormMajority: bool = NODES.filter(n => up.get(n) or canStart(n)).size() >= majority
  // Законный выход по тексту: replay на лидере/офлайн на box; для группы без лидера нужен путь к лидеру.
  def namedExit: bool = isUnfinished(phase) and (importRouteOpen or (not(BOX) and canFormMajority) or (BOX and not(up.get("a"))))
  // Состояние: попытка не завершена и законного выхода нет.
  val not_w_stuck = not(isUnfinished(phase) and not(namedExit) and not(ALLOW_REBUILD_GROUP) )
  // Узел с незавершённой попыткой остаётся отказанным, хотя группа уже Done (при литеральном :40).
  val not_w_refusedAfterDone = not(phase == "Done" and NODES.exists(n => refused.get(n) and isUnfinished(dirPhase.get(n))))
  // Лидер теряется, новый лидер продолжает и завершает (достижимость законного пути при большинстве).
  val not_w_resumeAfterLeaderLoss = not(phase == "Done" and rowsDone == R and attempts >= 1 and NODES.filter(n => up.get(n)).size() >= majority and NODES.exists(n => not(up.get(n))))
  // Новая попытка со свежей группой получает ту же генерацию (при допущении пересборки и том же часе).
  val not_w_sameGen = not(rebuilds >= 1 and attempts >= 2 and isUnfinished(phase) and attemptGen == lastAttemptGen)
  // Выход по допущению пересборки: новая попытка доходит до Done.
  val not_w_resumeAfterFullOutage = not(rebuilds >= 1 and phase == "Done")
  // Главный вопрос С1: после потери всех узлов на незавершённой попытке группа доходит до Done.
  val not_w_doneAfterOutage = not(outageSeen and phase == "Done")
  // Контроль: сам случай остановки всех узлов при незавершённой попытке достижим.
  val not_w_allDownUnfinished = not(isUnfinished(phase) and NODES.forall(n => not(up.get(n))))
}
