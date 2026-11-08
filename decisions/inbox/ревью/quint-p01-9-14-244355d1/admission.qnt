// Модель 1 из 6 (P/01 пп. 9-14, срез 244355d1): время допуска.
// Нормы: 01.1-store.norms.md:451 (формула max), :456-458 (проверка по сохранённому времени, не убывает),
//   :463-465 (скачок вперёд → expired), :501-502/:537/:541 (мета растёт, бизнес-эффектов нет),
//   :689-694 (R132, пакет), :473-477 (R071, гонки), 01.3-store.norms.md:91-97 (admission в журнале и снимке).
// Граница: 3 узла, до MAXLOG записей, часы 0..CLOCK_MAX; числа - параметры модели, не значения норм.
// Допущение A1 (абстракция Raft): лидером становится только узел с полным журналом (известное условие Raft),
//   фиксация и потери журнала не моделируются; журнал один на группу (префикс known на узел).
// Допущение A2: команды id-памяти и порядок проверок - как R088 (01.1:534-537), без полей строк.
// Не моделируется: бинарное представление binary64 (:466), реальная сеть, пакеты как отдельная форма
//   (пакет = запись, R132 по исходу тот же; см. mut_batch ниже нет, различие в счёт не идёт), box.
module admission {
  // === КОНФИГУРАЦИЯ (run.py заменяет pure val по имени) ===
  pure val NODES = Set("a", "b", "c")
  pure val MAXLOG = 5
  pure val CLOCK_MAX = 9
  pure val ALLOW_JUMP = true      // скачки часов вперёд и назад (физический случай, не норма)
  pure val ALLOW_SKEW = true      // свои часы у узлов; false — общие часы группы
  pure val ALLOW_LEADER_CHANGE = true
  // Мутанты: все false в базовой модели.
  pure val MUT_NO_MAX = false              // убрать max по журналу
  pure val MUT_REFUSE_ROLLBACK = false     // отказ не обновляет последнее время допуска
  pure val MUT_SNAP_NO_ADM = false         // снимок не несёт время допуска
  pure val MUT_APPLY_OWN_CLOCK = false     // применение сверяет своим часом, не сохранённым временем
  pure val MUT_EXPIRED_TAKES_ID = false    // expired занимает id
  pure val MUT_AGAIN_NEW_VERSION = false   // повтор выдаёт новую версию
  pure val MUT_CAS_BEFORE_TIME = false     // CAS раньше проверок времени

  // === ТИПЫ ===
  type AdmRec = { adm: int, clk: int, outcome: str, notAfter: int, notBefore: int, id: int, fp: int, ver: int,
               byLeader: str, fromSnap: bool, guardOk: bool, casOk: bool }
  pure val NONE = -1
  pure val IDS = Set(1, 2)
  pure val BOUNDS = Set(NONE, 2, 4, 6)
  pure val IDXS = 0.to(MAXLOG - 1)
  pure val CLOCKS = 0.to(CLOCK_MAX)
  pure val DUMMY: AdmRec = { adm: NONE, clk: NONE, outcome: "", notAfter: NONE, notBefore: NONE, id: NONE, fp: 0, ver: NONE,
                           byLeader: "", fromSnap: false, guardOk: true, casOk: true }
  pure def maxI(a: int, b: int): int = if (a > b) a else b

  // Время допуска; R069 формула (01.1:451). Мутант MUT_NO_MAX - только часы.
  pure def admissionOf(clk: int, prev: int): int = if (MUT_NO_MAX) clk else maxI(clk, prev)

  // Порядок проверок R088 (01.1:534-537): id-память, not_after, not_before, guard, cas.
  // Замечание к inv_order: при guardOk=false исход guard, проверяем порядок только по conflict.
  pure def outcomeOf(admitted: int, nA: int, nB: int, idApplied: bool, fpSame: bool, guardOk: bool, casOk: bool): str =
    if (idApplied) (if (fpSame) "again" else "badrequest")
    else if (MUT_CAS_BEFORE_TIME and not(casOk)) "conflict"
    else if (nA != NONE and admitted > nA) "expired"
    else if (nB != NONE and admitted <= nB) "early"
    else if (not(guardOk)) "guard"
    else if (not(casOk)) "conflict"
    else "ok"

  // R088: порядок: expired/early раньше guard/conflict; при неверном cas и нарушенном времени - исход по времени (хотя MUT_CAS_BEFORE_TIME даёт conflict).
  // Исход только по времени - для проверки «исход один на всех серверах» (01.1:456-458).
  pure def timeOutcome(t: int, nA: int, nB: int): str =
    if (nA != NONE and t > nA) "expired"
    else if (nB != NONE and t <= nB) "early"
    else "pass"

  // === СОСТОЯНИЕ ===
  var log: int -> AdmRec
  var logLen: int
  var clock: str -> int
  var lastAdm: str -> int     // «последнее время допуска», с которого продолжает узел
  var known: str -> int       // длина префикса журнала на узле
  var snapIdx: str -> int     // записи вошли в снимок
  var snapAdm: str -> int     // время допуска, вошедшее в снимок (R070, 01.3:91-92)
  var restartedSnap: str -> bool
  var leader: str             // "" - лидера нет
  var ids: int -> { ver: int, fp: int }
  var issued: int
  var diverged: bool          // применение на узле дало другой исход по времени

  // === ПЕРЕХОДЫ ===
  action init = all {
    log' = IDXS.mapBy(i => DUMMY),
    logLen' = 0,
    clock' = NODES.mapBy(n => 0),
    lastAdm' = NODES.mapBy(n => 0),
    known' = NODES.mapBy(n => 0),
    snapIdx' = NODES.mapBy(n => 0),
    snapAdm' = NODES.mapBy(n => 0),
    restartedSnap' = NODES.mapBy(n => false),
    leader' = "a",
    ids' = IDS.mapBy(i => { ver: NONE, fp: 0 }),
    issued' = 0,
    diverged' = false,
  }

  // Время допуска, с которого продолжает узел после рестарта/получения лидерства.
  def restoreAdm(n: str): int =
    if (known.get(n) == 0) 0
    else if (known.get(n) > snapIdx.get(n)) log.get(known.get(n) - 1).adm
    else snapAdm.get(n)

  // Часы: скачки вперёд/назад (скачок как явление среды). С ALLOW_SKEW = false - общие часы группы.
  action setClock = {
    nondet n = NODES.oneOf()
    nondet v = CLOCKS.oneOf()
    nondet step_ = Set(1, 2).oneOf()
    all {
      v <= CLOCK_MAX,
      if (ALLOW_SKEW and ALLOW_JUMP) clock' = clock.set(n, v)
      else if (ALLOW_SKEW) clock' = clock.setBy(n, c => if (c + step_ <= CLOCK_MAX) c + step_ else CLOCK_MAX)
      else clock' = NODES.mapBy(m => if (clock.get(m) + step_ <= CLOCK_MAX) clock.get(m) + step_ else CLOCK_MAX),
      log' = log, logLen' = logLen, lastAdm' = lastAdm, known' = known, snapIdx' = snapIdx,
      snapAdm' = snapAdm, restartedSnap' = restartedSnap, leader' = leader, ids' = ids, issued' = issued,
      diverged' = diverged,
    }
  }

  action admit = {
    nondet nA = BOUNDS.oneOf()
    nondet nB = BOUNDS.oneOf()
    nondet idIn = Set(NONE, 1, 2).oneOf()
    nondet fp = Set(0, 1).oneOf()
    nondet guardOk = Set(true, false).oneOf()
    nondet casOk = Set(true, false).oneOf()
    all {
      leader != "",
      logLen < MAXLOG,
      val L = leader
      val prev = lastAdm.get(L)
      val a = admissionOf(clock.get(L), prev)
      val idApplied = idIn != NONE and ids.get(idIn).ver != NONE
      val fpSame = idApplied and ids.get(idIn).fp == fp
      val outcome = outcomeOf(a, nA, nB, idApplied, fpSame, guardOk, casOk)
      val isOk = outcome == "ok"
      val newVer = isOk or (MUT_AGAIN_NEW_VERSION and outcome == "again")
      val takes = (isOk and idIn != NONE) or (MUT_EXPIRED_TAKES_ID and outcome == "expired" and idIn != NONE)
      val refused = outcome.in(Set("expired", "early", "guard", "conflict", "badrequest"))
      val r: AdmRec = { adm: a, clk: clock.get(L), outcome: outcome, notAfter: nA, notBefore: nB, id: idIn, fp: fp,
                     ver: if (newVer) issued else NONE, byLeader: L, fromSnap: restartedSnap.get(L), guardOk: guardOk, casOk: casOk }
      all {
        log' = log.set(logLen, r),
        logLen' = logLen + 1,
        lastAdm' = if (MUT_REFUSE_ROLLBACK and refused) lastAdm else lastAdm.set(L, a),
        known' = known.set(L, known.get(L) + 1),
        snapIdx' = snapIdx, snapAdm' = snapAdm, leader' = leader, restartedSnap' = restartedSnap,
        clock' = clock,
        ids' = if (takes) ids.set(idIn, { ver: if (newVer) issued else -2, fp: fp }) else ids,
        issued' = if (newVer) issued + 1 else issued,
        diverged' = diverged,
      }
    }
  }

  action replicate = {
    nondet n = NODES.oneOf()
    all {
      known.get(n) < logLen,
      n != leader,
      val idx = known.get(n)
      val r = log.get(idx)
      val t = if (MUT_APPLY_OWN_CLOCK) clock.get(n) else r.adm
      all {
        known' = known.set(n, idx + 1),
        lastAdm' = lastAdm.set(n, r.adm),
        diverged' = (diverged or (timeOutcome(t, r.notAfter, r.notBefore) != timeOutcome(r.adm, r.notAfter, r.notBefore))),
        log' = log, logLen' = logLen, clock' = clock, snapIdx' = snapIdx, snapAdm' = snapAdm,
        restartedSnap' = restartedSnap, leader' = leader, ids' = ids, issued' = issued,
      }
    }
  }

  // Снимок несёт время допуска последней вошедшей записи (01.3:91-92). Мутант: не несёт.
  action snapshot = {
    nondet n = NODES.oneOf()
    all {
      known.get(n) > snapIdx.get(n),
      val k = known.get(n)
      all {
        snapIdx' = snapIdx.set(n, k),
        snapAdm' = snapAdm.set(n, if (MUT_SNAP_NO_ADM) 0 else log.get(k - 1).adm),
        log' = log, logLen' = logLen, clock' = clock, lastAdm' = lastAdm, known' = known,
        leader' = leader, ids' = ids, issued' = issued, diverged' = diverged, restartedSnap' = restartedSnap,
      }
    }
  }

  // Рестарт узла: продолжает с времени последней записи своего журнала (включая снимок). 01.1:458.
  action restart = {
    nondet n = NODES.oneOf()
    all {
      val a = restoreAdm(n)
      all {
        lastAdm' = lastAdm.set(n, a),
        restartedSnap' = restartedSnap.set(n, known.get(n) > 0 and known.get(n) == snapIdx.get(n)),
        leader' = if (leader == n) "" else leader,
        log' = log, logLen' = logLen, clock' = clock, known' = known, snapIdx' = snapIdx, snapAdm' = snapAdm,
        ids' = ids, issued' = issued, diverged' = diverged,
      }
    }
  }

  // Смена лидера: допущение A1 — кандидат имеет полный журнал.
  action leaderChange = {
    nondet n = NODES.oneOf()
    all {
      ALLOW_LEADER_CHANGE,
      n != leader,
      known.get(n) == logLen,
      leader' = n,
      lastAdm' = lastAdm.set(n, restoreAdm(n)),
      restartedSnap' = restartedSnap,
      log' = log, logLen' = logLen, clock' = clock, known' = known, snapIdx' = snapIdx, snapAdm' = snapAdm,
      ids' = ids, issued' = issued, diverged' = diverged,
    }
  }

  action stutter = all {
    log' = log, logLen' = logLen, clock' = clock, lastAdm' = lastAdm, known' = known, snapIdx' = snapIdx, snapAdm' = snapAdm,
    restartedSnap' = restartedSnap, leader' = leader, ids' = ids, issued' = issued, diverged' = diverged,
  }

  action step = any { setClock, admit, replicate, snapshot, restart, leaderChange, stutter }

  // === ИНВАРИАНТЫ (что норма требует) ===
  def lastI: int = logLen - 1
  val inv_admNonDec = IDXS.forall(i => i + 1 < logLen implies log.get(i).adm <= log.get(i + 1).adm)
  // После принятой записи - и успешной, и отказа - последнее время допуска лидера равно времени записи.
  val inv_metaLast = (leader != "" and logLen > 0) implies lastAdm.get(leader) == log.get(lastI).adm
  // Отказ/повтор не создают бизнес-эффекта: выдано ровно по одной версии на запись с исходом ok.
  val inv_noBusiness = issued == IDXS.filter(i => i < logLen and log.get(i).outcome == "ok").size()
  val inv_oneOkPerId = IDXS.forall(i => IDXS.forall(j =>
    (i < j and j < logLen and log.get(i).outcome == "ok" and log.get(j).outcome == "ok" and log.get(i).id != NONE)
    implies log.get(i).id != log.get(j).id))
  // id занят только записью с исходом ok, с её же fp и версией; отказ/badrequest не меняют его.
  val inv_idMatchesOk = IDS.forall(d =>
    (ids.get(d).ver != NONE) implies
      IDXS.exists(i => i < logLen and log.get(i).id == d and log.get(i).outcome == "ok" and log.get(i).ver == ids.get(d).ver and log.get(i).fp == ids.get(d).fp))
  val inv_idOccupied = IDXS.forall(i =>
    (i < logLen and log.get(i).outcome == "ok" and log.get(i).id != NONE) implies ids.get(log.get(i).id).ver == log.get(i).ver)
  // R088: expired - тот же отказ при том же сроке и неубывающем времени; id-память идёт первой.
  val inv_expiredSticky = IDXS.forall(i => IDXS.forall(j =>
    (i < j and j < logLen and log.get(i).outcome == "expired" and log.get(j).notAfter == log.get(i).notAfter)
    implies log.get(j).outcome.in(Set("expired", "again", "badrequest"))))
  // Когда часы лидера не меньше последнего времени допуска, запись со сроком не раньше часов не expired.
  val inv_catchUp = IDXS.forall(i =>
    (i < logLen and log.get(i).clk >= (if (i > 0) log.get(i - 1).adm else 0)
     and log.get(i).notAfter != NONE and log.get(i).notAfter >= log.get(i).clk)
    implies log.get(i).outcome != "expired")
  // Исход по времени один на всех серверах (применение по сохранённому времени).
  val inv_sameOutcome = not(diverged)
  // R071: delete с not_before=T и write с not_after=T.
  val inv_r071 = IDXS.forall(i => IDXS.forall(j =>
    (i < j and j < logLen and log.get(i).notBefore != NONE and log.get(i).outcome == "ok"
     and log.get(j).notAfter == log.get(i).notBefore)
    implies log.get(j).outcome != "ok"))

  val inv_order = IDXS.forall(i =>
    (i < logLen and log.get(i).outcome == "conflict" and not(log.get(i).notAfter == NONE)) implies not(log.get(i).adm > log.get(i).notAfter))

  // === СВИДЕТЕЛИ ДОСТИЖИМОСТИ (ожидаемый итог: invariant нарушен = свидетель найден) ===
  // expired на будущей записи: срок ещё не наступил по часам лидера.
  val not_w_futureExpired = not(IDXS.exists(i => i < logLen and log.get(i).outcome == "expired" and log.get(i).notAfter >= log.get(i).clk))
  // держится: две expired подряд с будущим сроком у той же записи времени часов.
  val not_w_expiredHolds = not(IDXS.exists(i => IDXS.exists(j =>
    i < j and j < logLen and log.get(i).outcome == "expired" and log.get(j).outcome == "expired"
    and log.get(j).notAfter >= log.get(j).clk and log.get(i).clk > log.get(j).clk)))
  // новый лидер с отстающими часами продолжает с журнала.
  val not_w_leaderLower = not(IDXS.exists(i => i > 0 and i < logLen and log.get(i).byLeader != log.get(i-1).byLeader and log.get(i).clk < log.get(i).adm))
  // продолжение из снимка выше часов.
  val not_w_snapContinue = not(IDXS.exists(i => i < logLen and log.get(i).fromSnap and log.get(i).adm > log.get(i).clk))
  // отказ поднимает время допуска.
  val not_w_refusalRaises = not(IDXS.exists(i => i > 0 and i < logLen and log.get(i).adm > log.get(i-1).adm and log.get(i).outcome.in(Set("expired","early","guard","conflict","badrequest"))))
  // повтор получает ответ и после срока.
  val not_w_againLate = not(IDXS.exists(i => i < logLen and log.get(i).outcome == "again" and log.get(i).notAfter != NONE and log.get(i).adm > log.get(i).notAfter))
}
