// Модель 4 из 6 (срез 244355d1): память id, R141.
// Нормы: 01.1-store.norms.md:733 (оба условия; MAY forget только при обоих), :735 (не забывать неподходящий id; бюджет — отдельно),
//   :501-502/:537 (повтор: answer, again, новых версий нет), :766 (ambiguous: повтор с тем же id),
//   production-acceptance.md:15, :62 (равенство возраста — неподходящий, два края независимы, считаются только применённые id-записи),
//   runtime-constants.tsv:ID_REPLAY_MIN_AGE/ID_REPLAY_MIN_RECORDS (значения 120 с, 50000 — здесь параметры модели).
// ДОПУЩЕНИЕ M3: основание «времени с первого применения» нормой не названо (01.1:733; М3 отчёта):
//   AGE_BASE = "wall" (стенные часы узла, подвержены скачку) или "mono" (монотонное время). Отчёт М3 — именно этот выбор.
// Граница: id 1..3; часы, счётчик — параметры. Модель не про ёмкость кэша и GC (в норме :735 — другое свойство).
module id_memory {
  pure val AGE_BASE = "wall"       // "wall" | "mono"  - допущение, см. выше
  pure val MIN_AGE = 2
  pure val MIN_RECORDS = 2
  pure val IDS = Set(1, 2, 3)
  pure val MAX_TIME = 6
  pure val MAX_RECORDS = 4
  // Мутанты
  pure val MUT_AGE_ONLY = false        // забыть при выполнении только условия возраста
  pure val MUT_RECORDS_ONLY = false    // забыть при выполнении только условия числа записей
  pure val MUT_EQ_AGE = false          // возраст >= вместо строгого >
  pure val MUT_REPLAY_NEW_VER = false  // повтор создаёт новую версию
  pure val MUT_FORGET_ANY = false      // забыть неподходящий (GC без условий)

  var wall: int
  var mono: int
  var appliedRecords: int   // применённых записей с id всего
  var mem: int -> { applied: bool, forgotten: bool, firstWall: int, firstMono: int, countAt: int, ver: int }
  var issued: int
  var verCount: int -> int      // версий, выданных за текущую «жизнь» id (сброс при забывании)
  var lifetimeVer: int -> int   // версий за всё время
  var lastAgain: int -> int     // ответ последнего повтора (версия), -1 — нет
  // Запись последнего забывания: условия, какими оно было разрешено (в момент забывания).
  var forgetEvent: { happened: bool, ageOk: bool, recOk: bool, ageEqualsMin: bool, wallAge: int, monoAge: int }
  var ambiguousAwaiting: int -> bool

  action init = all {
    wall' = 0, mono' = 0, appliedRecords' = 0,
    mem' = IDS.mapBy(i => { applied: false, forgotten: false, firstWall: 0, firstMono: 0, countAt: 0, ver: -1 }),
    issued' = 0, verCount' = IDS.mapBy(i => 0), lifetimeVer' = IDS.mapBy(i => 0), lastAgain' = IDS.mapBy(i => -1),
    forgetEvent' = { happened: false, ageOk: false, recOk: false, ageEqualsMin: false, wallAge: 0, monoAge: 0 },
    ambiguousAwaiting' = IDS.mapBy(i => false),
  }

  action tick = all {
    mono < MAX_TIME, wall < MAX_TIME,
    mono' = mono + 1, wall' = wall + 1,
    appliedRecords' = appliedRecords, mem' = mem, issued' = issued, verCount' = verCount, lifetimeVer' = lifetimeVer, lastAgain' = lastAgain, forgetEvent' = forgetEvent, ambiguousAwaiting' = ambiguousAwaiting,
  }
  // Скачок стенных часов вперёд (М3). mono не меняется.
  action jumpForward = {
    nondet j = Set(1, 2, 3).oneOf()
    all {
      wall + j <= MAX_TIME,
      wall' = wall + j,
      mono' = mono, appliedRecords' = appliedRecords, mem' = mem, issued' = issued, verCount' = verCount, lifetimeVer' = lifetimeVer, lastAgain' = lastAgain, forgetEvent' = forgetEvent, ambiguousAwaiting' = ambiguousAwaiting,
    }
  }
  // Новое применение id: первое или повторное после законного забывания ("новая запись", :733).
  action applyNew = {
    nondet i = IDS.oneOf()
    nondet ambiguous = Set(true, false).oneOf()
    all {
      appliedRecords < MAX_RECORDS,
      not(mem.get(i).applied) or mem.get(i).forgotten,
      mem' = mem.set(i, { applied: true, forgotten: false, firstWall: wall, firstMono: mono, countAt: appliedRecords + 1, ver: issued }),
      appliedRecords' = appliedRecords + 1,
      issued' = issued + 1,
      verCount' = verCount.set(i, verCount.get(i) + 1),
      lifetimeVer' = lifetimeVer.set(i, lifetimeVer.get(i) + 1),
      ambiguousAwaiting' = ambiguousAwaiting.set(i, ambiguous),
      wall' = wall, mono' = mono,
      lastAgain' = lastAgain.set(i, -1),  // новая «жизнь» id: прежний ответ повтора не относится к ней
      forgetEvent' = forgetEvent,
    }
  }
  // Повтор с тем же id (в том числе после ambiguous).
  action replay = {
    nondet i = IDS.oneOf()
    all {
      mem.get(i).applied, not(mem.get(i).forgotten),
      val newV = MUT_REPLAY_NEW_VER
      all {
        lastAgain' = lastAgain.set(i, if (newV) issued else mem.get(i).ver),
        issued' = if (newV) issued + 1 else issued,
        verCount' = if (newV) verCount.set(i, verCount.get(i) + 1) else verCount,
        lifetimeVer' = if (newV) lifetimeVer.set(i, lifetimeVer.get(i) + 1) else lifetimeVer,
        ambiguousAwaiting' = ambiguousAwaiting.set(i, false),
        wall' = wall, mono' = mono, appliedRecords' = appliedRecords, mem' = mem, forgetEvent' = forgetEvent,
      }
    }
  }
  def ageOf(i: int): int = if (AGE_BASE == "wall") wall - mem.get(i).firstWall else mono - mem.get(i).firstMono
  def strictAgeOk(i: int): bool = if (MUT_EQ_AGE) ageOf(i) >= MIN_AGE else ageOf(i) > MIN_AGE
  def recordsOk(i: int): bool = appliedRecords - mem.get(i).countAt >= MIN_RECORDS
  // Забывание: MAY при обоих; норма не требует забывать.
  action forget = {
    nondet i = IDS.oneOf()
    all {
      mem.get(i).applied, not(mem.get(i).forgotten),
      if (MUT_FORGET_ANY) true else if (MUT_AGE_ONLY) strictAgeOk(i) else if (MUT_RECORDS_ONLY) recordsOk(i) else (strictAgeOk(i) and recordsOk(i)),
      mem' = mem.set(i, { applied: mem.get(i).applied, forgotten: true, firstWall: mem.get(i).firstWall, firstMono: mem.get(i).firstMono, countAt: mem.get(i).countAt, ver: mem.get(i).ver }),
      forgetEvent' = { happened: true, ageOk: strictAgeOk(i), recOk: recordsOk(i),
                       ageEqualsMin: ageOf(i) == MIN_AGE, wallAge: wall - mem.get(i).firstWall, monoAge: mono - mem.get(i).firstMono },
      verCount' = verCount.set(i, 0),
      wall' = wall, mono' = mono, appliedRecords' = appliedRecords, issued' = issued, lifetimeVer' = lifetimeVer, lastAgain' = lastAgain, ambiguousAwaiting' = ambiguousAwaiting,
    }
  }
  action stutter = all {
    wall' = wall, mono' = mono, appliedRecords' = appliedRecords, mem' = mem, issued' = issued, verCount' = verCount, lifetimeVer' = lifetimeVer, lastAgain' = lastAgain, forgetEvent' = forgetEvent, ambiguousAwaiting' = ambiguousAwaiting,
  }
  action step = any { tick, jumpForward, applyNew, replay, forget, stutter }

  // === ИНВАРИАНТЫ ===
  // Забыт только при обоих условиях, строго (равенство возраста — неподходящий).
  val inv_forgetBoth = forgetEvent.happened implies (forgetEvent.ageOk and forgetEvent.recOk)
  val inv_strictAge = forgetEvent.happened implies not(forgetEvent.ageEqualsMin)
  // Повтор не создаёт новую версию: за «жизнь» id — не более одной.
  val inv_oneVersionPerLife = IDS.forall(i => verCount.get(i) <= 1)
  // Ответ повтора — первая версия.
  val inv_againSameAnswer = IDS.forall(i => (lastAgain.get(i) != -1 and not(mem.get(i).forgotten)) implies lastAgain.get(i) == mem.get(i).ver)

  // === СВИДЕТЕЛИ ===
  // Законно забытый id применён как новая запись (:733).
  val not_w_forgottenNewWrite = not(IDS.exists(i => lifetimeVer.get(i) >= 2))
  // Скачок часов выполнил условие возраста раньше фактического времени (М3).
  val not_w_ageMetByJump = not(forgetEvent.happened and forgetEvent.wallAge > MIN_AGE and forgetEvent.monoAge <= MIN_AGE)
  // Следствие М3: после раннего забывания из-за скачка повтор становится новой записью раньше фактического возраста.
  val not_w_earlyReforget = not(forgetEvent.happened and forgetEvent.monoAge <= MIN_AGE and IDS.exists(i => lifetimeVer.get(i) >= 2))
  // ambiguous → повтор с тем же id даёт again и не создаёт версии.
  val not_w_ambiguousRetry = not(IDS.exists(i => lastAgain.get(i) != -1 and lifetimeVer.get(i) == 1 and mem.get(i).applied and not(mem.get(i).forgotten) and issued == 1))
}
