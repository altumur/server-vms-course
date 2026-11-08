// P/04 — скачок часов контроллера и физическое удаление единиц (находки Б1, С9, М1).
// Модель текста норм, не реализации. Анкеры: файл:строка на срезе 959af8d6.
//   N = Platform/04-controller/spec/04-controller.norms.md
//   RCK = Platform/common/contracts/row-check.md
//   S1 = Platform/01-store/spec/01.1-store.norms.md
//   FRM = Platform/01-store/forms/runtime-constants.tsv
// Единицы: uEnds — обычная таблица с ends (N:186, N:877, N:895); uMade — таблица с made
//   (N:896-899, RCK:100-101); uManual — ручная строка таблицы с fixed (N:896: ends снимает и не размещает, но не удаляет);
//   uDA — unplaced.delete_after (N:188, N:888: «longer than N s by the clock of the controller», счёт с первого прохода, сброс перезапуском).
// CONST (инстансы ниже): границы скачков и чтение «часы контроллера» для delete_after.
// Не моделируется: состояния единиц (8a), journal, cas+guard (по норме защищают от гонки правок, N:888-890), сеть, порядок внутри прохода.
module p04_clock_delete {
  // Граница суммарного скачка часов контроллера и лидера относительно истинного времени (секунды модели).
  const CTRL_BOUND: int         // |ctrl_offset| <= CTRL_BOUND; посылка CLOCK_SKEW=60 при значении 60 (FRM:7, S1:81)
  const LEADER_BOUND: int       // |leader_offset| <= LEADER_BOUND; 0 — часы лидера точны
  const DA_WALL: bool           // чтение М1: delete_after считается стенными часами (true) либо монотонными (false)
  const ENDS_NOT_BEFORE: bool   // предложение Б1: удаление ends только с условием хранилища not_before = ends-60
  const MUT_MADE_NO_NB: bool    // мутант: строка с made удаляется без условия not_before хранилища
  const MUT_DELETE_MANUAL: bool // мутант: ручные строки таблицы с fixed удаляются по ends

  pure val CLOCK_SKEW: int = 60     // FRM:7, S1:81
  pure val NB_MARGIN: int = 60      // not_before = max(0, keep-60), RCK:101
  pure val PASS_EVERY: int = 5      // forms/runtime-constants.tsv PASS_EVERY

  var now: int            // физическое (истинное) время
  var ctrlOffset: int     // стенные часы контроллера = now + ctrlOffset
  var leaderOffset: int   // часы лидера = now + leaderOffset
  var admit: int          // время допуска хранилища, неубывающее (S1:455, 460)
  var ends: int           // срок (поле ends) для uEnds, uManual; для uMade — поле ends того же значения
  var keep: int           // made.keep строки uMade
  var deleteAfter: int    // N секунд unplaced.delete_after, выбран при инициализации, постоянен
  var endsExpiredKept: int // счётчик expired_kept (N:896)
  var removed: str -> bool // снята с причиной (обратимо)
  var deletedAt: str -> int // -1 не удалена; иначе истинное время удаления
  var delWallAt: str -> int // показание стенных часов контроллера в момент удаления
  var daStartMono: int      // отсчёт delete_after, первое наблюдение: монотонное (== now), -1 нет отсчёта
  var daStartWall: int      // то же: показание стенных часов контроллера
  var daStartTrue: int      // истинное время первого наблюдения
  var restarts: int         // перезапуски контроллера (сброс отсчёта N:185)

  pure val UNITS = Set("uEnds", "uMade", "uManual", "uDA")
  def wallCtrl = now + ctrlOffset
  def clockLeader = now + leaderOffset

  action init = {
    // Значения полей и параметр delete_after — произвольные модельные значения, не нормативные числа.
    nondet e = oneOf(Set(100, 200, 300))
    nondet k = oneOf(Set(100, 200, 300, 400))
    nondet da = oneOf(Set(30, 120, 300))
    all {
    now' = 0,
    ctrlOffset' = 0,
    leaderOffset' = 0,
    admit' = 0,
    ends' = e,
    keep' = k,
    endsExpiredKept' = 0,
    removed' = UNITS.mapBy(u => false),
    deletedAt' = UNITS.mapBy(u => -1),
    delWallAt' = UNITS.mapBy(u => -1),
    daStartMono' = -1,
    daStartWall' = -1,
    daStartTrue' = -1,
    restarts' = 0,
    deleteAfter' = da,
    }
  }

  action unchangedDecision = all {
    removed' = removed,
    deletedAt' = deletedAt,
    delWallAt' = delWallAt,
    endsExpiredKept' = endsExpiredKept,
    daStartMono' = daStartMono,
    daStartWall' = daStartWall,
    daStartTrue' = daStartTrue,
    restarts' = restarts,
  }

  action tick = {
    nondet dt = oneOf(Set(1, 5, 60, 100, 300, 900))
    all {
      now' = now + dt,
      ctrlOffset' = ctrlOffset,
      leaderOffset' = leaderOffset,
      admit' = admit,
      ends' = ends,
      keep' = keep,
    deleteAfter' = deleteAfter,
      unchangedDecision,
    }
  }

  // Скачок часов контроллера: не ограничен сверху нормой (N:186), ниже — параметр модели.
  action ctrlJump = {
    nondet d = oneOf(Set(-900, -60, -5, 5, 60, 300, 900, 100000))
    all {
      ctrlOffset + d >= -CTRL_BOUND,
      ctrlOffset + d <= CTRL_BOUND,
      now' = now,
      ctrlOffset' = ctrlOffset + d,
      leaderOffset' = leaderOffset,
      admit' = admit,
      ends' = ends,
      keep' = keep,
    deleteAfter' = deleteAfter,
      unchangedDecision,
    }
  }

  action leaderJump = {
    nondet d = oneOf(Set(-900, -60, 60, 900, 100000))
    all {
      LEADER_BOUND > 0,
      leaderOffset + d >= -LEADER_BOUND,
      leaderOffset + d <= LEADER_BOUND,
      now' = now,
      ctrlOffset' = ctrlOffset,
      leaderOffset' = leaderOffset + d,
      admit' = admit,
      ends' = ends,
      keep' = keep,
    deleteAfter' = deleteAfter,
      unchangedDecision,
    }
  }

  // Общий скачок: контроллер и лидер на одном сервере (L:18 — контроллер на каждом сервере; восстановление снимка ВМ).
  action sharedJump = {
    nondet d = oneOf(Set(60, 900, 100000))
    all {
      LEADER_BOUND > 0,
      ctrlOffset + d <= CTRL_BOUND,
      leaderOffset + d <= LEADER_BOUND,
      now' = now,
      ctrlOffset' = ctrlOffset + d,
      leaderOffset' = leaderOffset + d,
      admit' = admit,
      ends' = ends,
      keep' = keep,
    deleteAfter' = deleteAfter,
      unchangedDecision,
    }
  }

  // Время допуска следующей записи (S1:455)
  def admitted = if (clockLeader > admit) clockLeader else admit

  def recordDelete(u: str): (str -> int, str -> int) =
    (deletedAt.set(u, now), delWallAt.set(u, wallCtrl))

  // Шаги 4 и 8 прохода для uEnds (N:877, N:895, N:900-902): field <= clock контроллера → снять и удалить.
  action passEnds = all {
    deletedAt.get("uEnds") == -1,
    ends <= wallCtrl,
    not(ENDS_NOT_BEFORE) or admitted > ends - CLOCK_SKEW,
    removed' = removed.set("uEnds", true),
    deletedAt' = deletedAt.set("uEnds", now),
    delWallAt' = delWallAt.set("uEnds", wallCtrl),
    admit' = admitted,
    now' = now,
    ctrlOffset' = ctrlOffset,
    leaderOffset' = leaderOffset,
    ends' = ends,
    keep' = keep,
    deleteAfter' = deleteAfter,
    endsExpiredKept' = endsExpiredKept,
    daStartMono' = daStartMono,
    daStartWall' = daStartWall,
    daStartTrue' = daStartTrue,
    restarts' = restarts,
  }

  // Строка с made (N:897-899, RCK:100-101): поле истекло, стенные часы контроллера > keep; условие хранилища not_before = max(0, keep-60).
  action passMade = all {
    deletedAt.get("uMade") == -1,
    ends <= wallCtrl,
    wallCtrl > keep,
    MUT_MADE_NO_NB or admitted > (if (keep - NB_MARGIN > 0) keep - NB_MARGIN else 0),
    removed' = removed.set("uMade", true),
    deletedAt' = deletedAt.set("uMade", now),
    delWallAt' = delWallAt.set("uMade", wallCtrl),
    admit' = admitted,
    now' = now,
    ctrlOffset' = ctrlOffset,
    leaderOffset' = leaderOffset,
    ends' = ends,
    keep' = keep,
    deleteAfter' = deleteAfter,
    endsExpiredKept' = endsExpiredKept,
    daStartMono' = daStartMono,
    daStartWall' = daStartWall,
    daStartTrue' = daStartTrue,
    restarts' = restarts,
  }

  // Ручная строка таблицы с fixed: снимается, не удаляется (N:896); expired_kept + 1.
  action passManual = all {
    ends <= wallCtrl,
    not(removed.get("uManual")) or endsExpiredKept < 3,
    removed' = removed.set("uManual", true),
    if (MUT_DELETE_MANUAL) deletedAt' = deletedAt.set("uManual", now) else deletedAt' = deletedAt,
    delWallAt' = delWallAt,
    endsExpiredKept' = endsExpiredKept + 1,
    admit' = admit,
    now' = now,
    ctrlOffset' = ctrlOffset,
    leaderOffset' = leaderOffset,
    ends' = ends,
    keep' = keep,
    deleteAfter' = deleteAfter,
    daStartMono' = daStartMono,
    daStartWall' = daStartWall,
    daStartTrue' = daStartTrue,
    restarts' = restarts,
  }

  // Начало отсчёта delete_after: первый проход, увидевший единицу без размещения (N:188).
  action passDaObserve = all {
    daStartMono == -1,
    deletedAt.get("uDA") == -1,
    daStartMono' = now,
    daStartWall' = wallCtrl,
    daStartTrue' = now,
    now' = now,
    ctrlOffset' = ctrlOffset,
    leaderOffset' = leaderOffset,
    admit' = admit,
    ends' = ends,
    keep' = keep,
    deleteAfter' = deleteAfter,
    removed' = removed,
    deletedAt' = deletedAt,
    delWallAt' = delWallAt,
    endsExpiredKept' = endsExpiredKept,
    restarts' = restarts,
  }

  // Удаление по delete_after: строго дольше N секунд по выбранному чтению (N:188, N:888).
  action passDaDelete = {
    val elapsed = if (DA_WALL) wallCtrl - daStartWall else now - daStartMono
    all {
      deletedAt.get("uDA") == -1,
      daStartMono >= 0,
      elapsed > deleteAfter,
      deletedAt' = deletedAt.set("uDA", now),
      delWallAt' = delWallAt.set("uDA", wallCtrl),
      removed' = removed,
      endsExpiredKept' = endsExpiredKept,
      now' = now,
      ctrlOffset' = ctrlOffset,
      leaderOffset' = leaderOffset,
      admit' = admit,
      ends' = ends,
      keep' = keep,
    deleteAfter' = deleteAfter,
      daStartMono' = daStartMono,
      daStartWall' = daStartWall,
      daStartTrue' = daStartTrue,
      restarts' = restarts,
    }
  }

  // Перезапуск контроллера: память отсчётов сброшена (N:185).
  action restart = all {
    restarts < 2,
    daStartMono' = -1,
    daStartWall' = -1,
    daStartTrue' = -1,
    restarts' = restarts + 1,
    now' = now,
    ctrlOffset' = ctrlOffset,
    leaderOffset' = leaderOffset,
    admit' = admit,
    ends' = ends,
    keep' = keep,
    deleteAfter' = deleteAfter,
    removed' = removed,
    deletedAt' = deletedAt,
    delWallAt' = delWallAt,
    endsExpiredKept' = endsExpiredKept,
  }

  action step = any {
    tick, ctrlJump, leaderJump, sharedJump, passEnds, passMade, passManual,
    passDaObserve, passDaDelete, restart,
  }

  // Инварианты: граница на выполненное действие удаления (записаны действием удаления).
  // Б1: удаление ends не раньше ends - CLOCK_SKEW (держится только при посылке CLOCK_SKEW).
  val invEndsBound = deletedAt.get("uEnds") == -1 or deletedAt.get("uEnds") >= ends - CLOCK_SKEW
  // Строка с made: не раньше keep-60 при точном лидере (RCK:101, S1:471-481); при неточном — + LEADER_BOUND.
  val invMadeBound = deletedAt.get("uMade") == -1 or deletedAt.get("uMade") + LEADER_BOUND > keep - NB_MARGIN
  // Точная граница строки с made: не раньше keep-60 (при неточном лидере — нарушается)
  val invMadeStrict = deletedAt.get("uMade") == -1 or deletedAt.get("uMade") > keep - NB_MARGIN
  val invManualNotDeleted = deletedAt.get("uManual") == -1
  // М1: удалено не раньше, чем истинно прошло delete_after от первого наблюдения.
  val invDaNotEarly = deletedAt.get("uDA") == -1 or daStartTrue == -1 or deletedAt.get("uDA") - daStartTrue > deleteAfter

  // Свидетели (ожидается нарушение: достижимо)
  val witEndsDeleted = deletedAt.get("uEnds") == -1
  val witEndsDeletedEarly = deletedAt.get("uEnds") == -1 or deletedAt.get("uEnds") >= ends - CLOCK_SKEW
  val witMadeDeleted = deletedAt.get("uMade") == -1
  val witDaDeleted = deletedAt.get("uDA") == -1
  val witManualKept = endsExpiredKept == 0
  val witDaAfterRestart = not(restarts >= 1 and deletedAt.get("uDA") >= 0)
  val witLeaderSkew = leaderOffset == 0
}

module clk_premise {
  // Посылка: контроллер в пределах CLOCK_SKEW, лидер точен.
  import p04_clock_delete(CTRL_BOUND=60, LEADER_BOUND=0, DA_WALL=false, ENDS_NOT_BEFORE=false, MUT_MADE_NO_NB=false, MUT_DELETE_MANUAL=false).*
}
module clk_jump {
  // Скачок контроллера за посылку, лидер точен, норма как есть (Б1).
  import p04_clock_delete(CTRL_BOUND=100000, LEADER_BOUND=0, DA_WALL=false, ENDS_NOT_BEFORE=false, MUT_MADE_NO_NB=false, MUT_DELETE_MANUAL=false).*
}
module clk_jump_fix {
  // Предложение Б1 при скачке только контроллера.
  import p04_clock_delete(CTRL_BOUND=100000, LEADER_BOUND=0, DA_WALL=false, ENDS_NOT_BEFORE=true, MUT_MADE_NO_NB=false, MUT_DELETE_MANUAL=false).*
}
module clk_jump_fix_leader {
  // То же, но разрешён скачок лидера (тот же сервер): предложение не спасает от скачка лидера.
  import p04_clock_delete(CTRL_BOUND=100000, LEADER_BOUND=100000, DA_WALL=false, ENDS_NOT_BEFORE=true, MUT_MADE_NO_NB=false, MUT_DELETE_MANUAL=false).*
}
module clk_jump_da_wall {
  // Чтение М1: delete_after по стенным часам.
  import p04_clock_delete(CTRL_BOUND=100000, LEADER_BOUND=0, DA_WALL=true, ENDS_NOT_BEFORE=false, MUT_MADE_NO_NB=false, MUT_DELETE_MANUAL=false).*
}
module clk_mut_no_nb {
  import p04_clock_delete(CTRL_BOUND=100000, LEADER_BOUND=0, DA_WALL=false, ENDS_NOT_BEFORE=false, MUT_MADE_NO_NB=true, MUT_DELETE_MANUAL=false).*
}
module clk_mut_manual {
  import p04_clock_delete(CTRL_BOUND=100000, LEADER_BOUND=0, DA_WALL=false, ENDS_NOT_BEFORE=false, MUT_MADE_NO_NB=false, MUT_DELETE_MANUAL=true).*
}
module clk_premise_leader {
  // Лидер в пределах посылки, контроллер в пределах посылки.
  import p04_clock_delete(CTRL_BOUND=60, LEADER_BOUND=60, DA_WALL=false, ENDS_NOT_BEFORE=false, MUT_MADE_NO_NB=false, MUT_DELETE_MANUAL=false).*
}
module clk_jump_leader {
  // Лидер скачет за посылку: not_before строки с made не защищает.
  import p04_clock_delete(CTRL_BOUND=100000, LEADER_BOUND=100000, DA_WALL=false, ENDS_NOT_BEFORE=false, MUT_MADE_NO_NB=false, MUT_DELETE_MANUAL=false).*
}
