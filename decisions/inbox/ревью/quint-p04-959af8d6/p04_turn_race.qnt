// P/04 — гонка двух контроллеров, ход и защита записи (находки С10, С4): модель текста норм, не реализации.
//   N = Platform/04-controller/spec/04-controller.norms.md
//   T = Platform/common/contracts/turn.md
// Границы: 2 контроллера, 2 единицы (вес 1), 2 рабочих (вместимость 1), решения по одной единице
//   (группы не моделируются). Чтение строк атомарно на шаге; в полёте не более одной записи контроллера.
// Допущения (с якорем):
//   T:46 — захват чужой строки только при возрасте версии >= TURN_TERM по своим часам;
//   T:51-55 — продление cas своей версией, guard своей версией, запись только при живом своём сроке;
//   T:80-85 — барьер; после него всё читается заново (активный intent завершается первым; N:842, N:868);
//   N:869 — решение после свежего чтения; N:819-828 — шаги intent: active → снять со всех → placement → добавить → idle;
//   T:75 — сдача хода подсистемы: только в конце прохода; SIGTERM не сдаёт (вариант `SIGTERM_RELEASE` — проба предложения С4).
// Не моделируется: манифест/manifest_rev, группы/spread_by, очереди запросов, журналы, настоящие длительности кроме TURN_TERM/TURN_RENEW.
module p04_turn_race {
  const MUT: str               // none | noguard | nofresh | skipintent | addfirst | nobarrierbump | noagecheck
  const SIGTERM_RELEASE: bool  // false по норме T:75; true — предложение: сдать ход при SIGTERM
  const NOISE: bool            // false — ограничивает шум симуляции (без SIGTERM/таймаута/потери ответа/продления/времени); подмножество поведений, годно только для поиска контрпримеров мутантов

  pure val TURN_TERM: int = 45   // T:32
  pure val TURN_RENEW: int = 10  // T:33
  pure val CAP: int = 1
  pure val CTRLS = Set("c1", "c2")
  pure val UNITS = Set("u1", "u2")
  pure val WORKERS = Set("w1", "w2")

  type Intent = { ver: int, active: bool, unit: str, target: str }
  type Place = { ver: int, worker: str }
  type Assign = { ver: int, units: Set[str] }
  type Turn = { ver: int, holder: int }
  type Store = { turn: Turn, intent: Intent, place: str -> Place, assign: str -> Assign, log: int }
  // Запись: key ∈ intent|place|assign|turn; sub — единица/рабочий; поля значения — для соответствующего ключа
  type Write = { key: str, sub: str, cas: int, guard: int, holder: int, iActive: bool, iUnit: str, iTarget: str, pWorker: str, aUnits: Set[str], valid: bool }

  var store: Store
  var now: int
  var turnWrittenAt: int
  var pc: str -> str            // Idle Decide Barrier S2 S3 S4 S5 S6 Gone
  var myVer: str -> int         // своя версия хода (последняя подтверждённая); -1 нет
  var myMark: str -> int
  var attempt: str -> int
  var sentAt: str -> int        // время отправки последнего подтверждённого запроса своего хода (T:50, T:53)
  var seenVer: str -> int       // наблюдаемая версия хода
  var seenAt: str -> int        // первое наблюдение этой версии (T:46)
  var plan: str -> {u: str, t: str}
  var snapIntent: str -> Intent // снимок решения этого контроллера
  var snapAssign: str -> (str -> Assign)
  var snapPlace: str -> (str -> Place)
  var snapCount: str -> int     // сколько раз обновлялось (для MUT=nofresh)
  var inflight: str -> Write     // запись, ответа которой ждём
  var abandoned: str -> Write    // запись, чей ответ не пришёл (таймаут): продолжает идти к хранилищу (T:83)
  var ghostStaleApplied: bool
  var ghostAcceptedActive: bool
  var ghostEarlyCapture: bool
  var ghostTookActive: bool     // захват и завершение чужого активного intent
  var ghostStaleRefused: bool   // опоздавшая запись получила отказ 412
  var ghostDoubleTakeLog: int   // журнал для наблюдения: число захватов
  var ghostSigtermReleased: bool // SIGTERM со сдачей хода был
  var abandonedPassed: str -> bool // в момент этого барьера запись контроллера ещё была в пути
  var ghostLateApplied: bool    // опоздавшая запись применена после барьера (T:83)
  var ghostFastAfterSigterm: bool // захват после сдачи хода при SIGTERM

  pure val EMPTY_US: Set[str] = Set()
  pure val NONE_WRITE: Write = { key: "", sub: "", cas: -1, guard: -1, holder: 0, iActive: false, iUnit: "", iTarget: "", pWorker: "", aUnits: EMPTY_US, valid: false }
  pure val INTENT0: Intent = { ver: 0, active: false, unit: "", target: "" }
  pure val PLACE0 = UNITS.mapBy(u => { ver: 0, worker: "" })
  pure val ASSIGN0 = WORKERS.mapBy(w => { ver: 0, units: EMPTY_US })
  pure val STORE0: Store = { turn: { ver: 0, holder: 0 }, intent: INTENT0, place: PLACE0, assign: ASSIGN0, log: 0 }

  action init = all {
    store' = STORE0,
    now' = 0,
    turnWrittenAt' = 0,
    pc' = CTRLS.mapBy(c => "Idle"),
    myVer' = CTRLS.mapBy(c => -1),
    myMark' = CTRLS.mapBy(c => 0),
    attempt' = CTRLS.mapBy(c => 0),
    sentAt' = CTRLS.mapBy(c => -1000),
    seenVer' = CTRLS.mapBy(c => -1),
    seenAt' = CTRLS.mapBy(c => 0),
    plan' = CTRLS.mapBy(c => {u: "", t: ""}),
    snapIntent' = CTRLS.mapBy(c => INTENT0),
    snapAssign' = CTRLS.mapBy(c => ASSIGN0),
    snapPlace' = CTRLS.mapBy(c => PLACE0),
    snapCount' = CTRLS.mapBy(c => 0),
    inflight' = CTRLS.mapBy(c => NONE_WRITE),
    abandoned' = CTRLS.mapBy(c => NONE_WRITE),
    ghostStaleApplied' = false,
    ghostAcceptedActive' = false,
    ghostEarlyCapture' = false,
    ghostTookActive' = false,
    ghostStaleRefused' = false,
    ghostDoubleTakeLog' = 0,
    ghostSigtermReleased' = false,
    ghostFastAfterSigterm' = false,
    abandonedPassed' = CTRLS.mapBy(c => false),
    ghostLateApplied' = false,
  }

  // Применение записи к хранилищу: guard (кроме своей строки хода) и cas.
  pure def applyWrite(s: Store, w: Write, guardOn: bool): (Store, bool) = {
    val guardOk = (w.key == "turn") or not(guardOn) or (w.guard == s.turn.ver)
    val curVer = if (w.key == "turn") s.turn.ver
                 else if (w.key == "intent") s.intent.ver
                 else if (w.key == "place") s.place.get(w.sub).ver
                 else if (w.key == "assign") s.assign.get(w.sub).ver
                 else -2
    val casOk = (curVer == w.cas)
    if (not(guardOk and casOk)) (s, false)
    else {
      val nv = s.log + 1
      val s1 = s.with("log", nv)
      if (w.key == "turn") (s1.with("turn", { ver: nv, holder: w.holder }), true)
      else if (w.key == "intent") (s1.with("intent", { ver: nv, active: w.iActive, unit: w.iUnit, target: w.iTarget }), true)
      else if (w.key == "place") (s1.with("place", s.place.set(w.sub, { ver: nv, worker: w.pWorker })), true)
      else (s1.with("assign", s.assign.set(w.sub, { ver: nv, units: w.aUnits })), true)
    }
  }

  def guardOn = MUT != "noguard"
  def ownLive(c: str): bool = now - sentAt.get(c) < TURN_TERM

  // Ход: чтение и cas. Чужая строка берётся только при возрасте версии >= TURN_TERM по своим часам (T:46).
  action observeTurn(c: str): bool = all {
    pc.get(c) == "Idle",
    seenVer' = seenVer.set(c, store.turn.ver),
    seenAt' = if (seenVer.get(c) == store.turn.ver) seenAt else seenAt.set(c, now),
    store' = store, now' = now, turnWrittenAt' = turnWrittenAt, pc' = pc, myVer' = myVer, myMark' = myMark,
    attempt' = attempt, sentAt' = sentAt, plan' = plan, snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace,
    snapCount' = snapCount, inflight' = inflight, abandoned' = abandoned, ghostStaleApplied' = ghostStaleApplied, ghostAcceptedActive' = ghostAcceptedActive,
    ghostEarlyCapture' = ghostEarlyCapture, ghostTookActive' = ghostTookActive, ghostStaleRefused' = ghostStaleRefused, ghostDoubleTakeLog' = ghostDoubleTakeLog, ghostSigtermReleased' = ghostSigtermReleased, ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed, ghostLateApplied' = ghostLateApplied,
  }

  def captureAllowed(c: str): bool = {
    val v = store.turn.ver
    val h = store.turn.holder
    val ok = (seenVer.get(c) == v) and (h == 0 or MUT == "noagecheck" or now - seenAt.get(c) >= TURN_TERM)
    ok
  }

  action capture(c: str): bool = {
    val a = attempt.get(c) + 1
    val mark = (if (c == "c1") 100 else 200) + a
    nondet w = oneOf(Set({ key: "turn", sub: "", cas: store.turn.ver, guard: 0, holder: mark, iActive: false, iUnit: "", iTarget: "", pWorker: "", aUnits: EMPTY_US, valid: true }))
    nondet r = oneOf(Set(applyWrite(store, w, guardOn)))
    all {
      pc.get(c) == "Idle",
      attempt.get(c) < 3,
      captureAllowed(c),
      r._2,
      store' = r._1,
      turnWrittenAt' = now,
      pc' = pc.set(c, "Decide"),
      myVer' = myVer.set(c, r._1.turn.ver),
      myMark' = myMark.set(c, mark),
      attempt' = attempt.set(c, a),
      sentAt' = sentAt.set(c, now),
      ghostEarlyCapture' = (ghostEarlyCapture or (store.turn.holder != 0 and now - turnWrittenAt < TURN_TERM)),
      ghostDoubleTakeLog' = ghostDoubleTakeLog + 1,
      ghostSigtermReleased' = false,
      ghostFastAfterSigterm' = (ghostFastAfterSigterm or (ghostSigtermReleased and store.turn.holder == 0)), abandonedPassed' = abandonedPassed, ghostLateApplied' = ghostLateApplied,
      seenVer' = seenVer, seenAt' = seenAt, now' = now, plan' = plan, snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace,
      snapCount' = snapCount, inflight' = inflight, abandoned' = abandoned, ghostStaleApplied' = ghostStaleApplied, ghostAcceptedActive' = ghostAcceptedActive,
      ghostTookActive' = ghostTookActive, ghostStaleRefused' = ghostStaleRefused,
    }
  }

  // Продление между операциями (T:51-52): cas своей версии, holder прежний.
  action renew(c: str): bool = {
    nondet w = oneOf(Set({ key: "turn", sub: "", cas: myVer.get(c), guard: 0, holder: myMark.get(c), iActive: false, iUnit: "", iTarget: "", pWorker: "", aUnits: EMPTY_US, valid: true }))
    nondet r = oneOf(Set(applyWrite(store, w, guardOn)))
    all {
      pc.get(c) == "Decide" or pc.get(c) == "S3" or pc.get(c) == "S4" or pc.get(c) == "S5" or pc.get(c) == "S6",
      inflight.get(c).valid == false,
      store.turn.holder == myMark.get(c),
      r._2,
      store' = r._1,
      turnWrittenAt' = now,
      myVer' = myVer.set(c, r._1.turn.ver),
      sentAt' = sentAt.set(c, now),
      now' = now, pc' = pc, myMark' = myMark, attempt' = attempt, seenVer' = seenVer, seenAt' = seenAt, plan' = plan,
      snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace, snapCount' = snapCount, inflight' = inflight, abandoned' = abandoned,
      ghostStaleApplied' = ghostStaleApplied, ghostAcceptedActive' = ghostAcceptedActive, ghostEarlyCapture' = ghostEarlyCapture,
      ghostTookActive' = ghostTookActive, ghostStaleRefused' = ghostStaleRefused, ghostDoubleTakeLog' = ghostDoubleTakeLog, ghostSigtermReleased' = ghostSigtermReleased, ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed, ghostLateApplied' = ghostLateApplied,
    }
  }

  // Сдача хода в конце прохода (T:56, T:75): cas своей версии, holder "".
  action giveUp(c: str): bool = {
    nondet w = oneOf(Set({ key: "turn", sub: "", cas: myVer.get(c), guard: 0, holder: 0, iActive: false, iUnit: "", iTarget: "", pWorker: "", aUnits: EMPTY_US, valid: true }))
    nondet r = oneOf(Set(applyWrite(store, w, guardOn)))
    all {
      pc.get(c) == "Decide",
      not(store.intent.active),
      inflight.get(c).valid == false,
      r._2,
      store' = r._1,
      turnWrittenAt' = now,
      pc' = pc.set(c, "Idle"),
      myVer' = myVer.set(c, -1),
      myMark' = myMark, now' = now, attempt' = attempt, sentAt' = sentAt, seenVer' = seenVer, seenAt' = seenAt, plan' = plan,
      snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace, snapCount' = snapCount, inflight' = inflight, abandoned' = abandoned,
      ghostStaleApplied' = ghostStaleApplied, ghostAcceptedActive' = ghostAcceptedActive, ghostEarlyCapture' = ghostEarlyCapture,
      ghostTookActive' = ghostTookActive, ghostStaleRefused' = ghostStaleRefused, ghostDoubleTakeLog' = ghostDoubleTakeLog, ghostSigtermReleased' = ghostSigtermReleased, ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed, ghostLateApplied' = ghostLateApplied,
    }
  }

  // Завершение попытки без сдачи: потеря хода (свою строку уже нельзя тронуть).
  action loseTurn(c: str): bool = all {
    pc.get(c) == "Decide",
    inflight.get(c).valid == false,
    store.turn.holder != myMark.get(c),
    pc' = pc.set(c, "Idle"),
    myVer' = myVer.set(c, -1),
    store' = store, now' = now, turnWrittenAt' = turnWrittenAt, myMark' = myMark, attempt' = attempt, sentAt' = sentAt, seenVer' = seenVer, seenAt' = seenAt,
    plan' = plan, snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace, snapCount' = snapCount, inflight' = inflight, abandoned' = abandoned,
    ghostStaleApplied' = ghostStaleApplied, ghostAcceptedActive' = ghostAcceptedActive, ghostEarlyCapture' = ghostEarlyCapture,
    ghostTookActive' = ghostTookActive, ghostStaleRefused' = ghostStaleRefused, ghostDoubleTakeLog' = ghostDoubleTakeLog, ghostSigtermReleased' = ghostSigtermReleased, ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed, ghostLateApplied' = ghostLateApplied,
  }

  // Шаг 1 решения: свежее чтение и либо восстановление активного intent, либо новое решение (N:868-869, N:842; T:82).
  def needRefresh(c: str): bool = MUT != "nofresh" or snapCount.get(c) == 0

  action decideNext(c: str): bool = {
    nondet u = oneOf(UNITS)
    nondet t = oneOf(WORKERS)
    nondet newSnapI = oneOf(Set(if (needRefresh(c)) store.intent else snapIntent.get(c)))
    nondet newSnapA = oneOf(Set(if (needRefresh(c)) store.assign else snapAssign.get(c)))
    nondet newSnapP = oneOf(Set(if (needRefresh(c)) store.place else snapPlace.get(c)))
    val iActive = store.intent.active
    // MUT=skipintent: не завершает чужой активный intent (нарушение N:842)
    val recover = iActive and MUT != "skipintent"
    val freeOnT = newSnapA.get(t).units.size() < CAP
    // вместимость с резервом активного intent этого снимка (N:812)
    val reserved = (newSnapI.active and newSnapI.target == t)
    all {
      pc.get(c) == "Decide",
      inflight.get(c).valid == false,
      store.turn.holder == myMark.get(c),
      ownLive(c),
      if (recover) all {
        pc' = pc.set(c, "S3"),
        plan' = plan.set(c, {u: store.intent.unit, t: store.intent.target}),
        ghostAcceptedActive' = ghostAcceptedActive,
        ghostTookActive' = (ghostTookActive or (store.intent.active and myVer.get(c) > 0)),
      } else all {
        // новое решение
        freeOnT and not(reserved),
        newSnapP.get(u).worker != t,
        plan' = plan.set(c, {u: u, t: t}),
        pc' = pc.set(c, "S2"),
        ghostAcceptedActive' = (ghostAcceptedActive or iActive),
        ghostTookActive' = ghostTookActive,
      },
      snapIntent' = snapIntent.set(c, newSnapI),
      snapAssign' = snapAssign.set(c, newSnapA),
      snapPlace' = snapPlace.set(c, newSnapP),
      snapCount' = snapCount.set(c, snapCount.get(c) + 1),
      store' = store, now' = now, turnWrittenAt' = turnWrittenAt, myVer' = myVer, myMark' = myMark, attempt' = attempt, sentAt' = sentAt,
      seenVer' = seenVer, seenAt' = seenAt, inflight' = inflight, abandoned' = abandoned, ghostStaleApplied' = ghostStaleApplied, ghostEarlyCapture' = ghostEarlyCapture,
      ghostStaleRefused' = ghostStaleRefused, ghostDoubleTakeLog' = ghostDoubleTakeLog, ghostSigtermReleased' = ghostSigtermReleased, ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed, ghostLateApplied' = ghostLateApplied,
    }
  }

  // Выбор записи шага; для S3 — первое назначение с этой единицей по свежему чтению (N:821-823).
  def nextWrite(c: str): Write = {
    val p = plan.get(c)
    val g = myVer.get(c)
    val st = pc.get(c)
    if (st == "S2") { key: "intent", sub: "", cas: store.intent.ver, guard: g, holder: 0, iActive: true, iUnit: p.u, iTarget: p.t, pWorker: "", aUnits: EMPTY_US, valid: true }
    else if (st == "S3") {
      val withU = WORKERS.filter(w => store.assign.get(w).units.contains(p.u))
      // S3: одна запись на шаг; порядок выбора недетерминирован на уровне действия (фильтр даёт тот же результат ниже)
      val w = if (store.assign.get("w1").units.contains(p.u)) "w1" else "w2"
      { key: "assign", sub: w, cas: store.assign.get(w).ver, guard: g, holder: 0, iActive: false, iUnit: "", iTarget: "", pWorker: "", aUnits: store.assign.get(w).units.exclude(Set(p.u)), valid: withU.size() > 0 }
    }
    else if (st == "S4") { key: "place", sub: p.u, cas: store.place.get(p.u).ver, guard: g, holder: 0, iActive: false, iUnit: "", iTarget: "", pWorker: p.t, aUnits: EMPTY_US, valid: true }
    else if (st == "S5") { key: "assign", sub: p.t, cas: store.assign.get(p.t).ver, guard: g, holder: 0, iActive: false, iUnit: "", iTarget: "", pWorker: "", aUnits: store.assign.get(p.t).units.union(Set(p.u)), valid: true }
    else if (st == "S6") { key: "intent", sub: "", cas: store.intent.ver, guard: g, holder: 0, iActive: false, iUnit: "", iTarget: "", pWorker: "", aUnits: EMPTY_US, valid: true }
    else NONE_WRITE
  }

  // Переход pc после подтверждённой записи шага.
  def nextPc(c: str): str = {
    val st = pc.get(c)
    if (st == "S2") "S3"
    else if (st == "S3") (
      if (WORKERS.filter(w => store.assign.get(w).units.contains(plan.get(c).u)).size() > 1) "S3" else "S4"
    )
    else if (st == "S4") "S5"
    else if (st == "S5") "S6"
    else if (st == "S6") "Decide"
    else st
  }

  // Шаг S3 завершён: нет ни одного назначения с единицей → дальше к placement.
  action s3Done(c: str): bool = all {
    pc.get(c) == "S3",
    inflight.get(c).valid == false,
    not(WORKERS.exists(w => store.assign.get(w).units.contains(plan.get(c).u))),
    pc' = pc.set(c, "S4"),
    store' = store, now' = now, turnWrittenAt' = turnWrittenAt, myVer' = myVer, myMark' = myMark, attempt' = attempt, sentAt' = sentAt, seenVer' = seenVer, seenAt' = seenAt,
    plan' = plan, snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace, snapCount' = snapCount, inflight' = inflight, abandoned' = abandoned,
    ghostStaleApplied' = ghostStaleApplied, ghostAcceptedActive' = ghostAcceptedActive, ghostEarlyCapture' = ghostEarlyCapture,
    ghostTookActive' = ghostTookActive, ghostStaleRefused' = ghostStaleRefused, ghostDoubleTakeLog' = ghostDoubleTakeLog, ghostSigtermReleased' = ghostSigtermReleased, ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed, ghostLateApplied' = ghostLateApplied,
  }

  // Отправка записи: запись уходит с защитой своей версией (T:53); при истёкшем своём сроке писать нельзя (T:54).
  // Мутант addfirst: S3 пропускается целиком (сразу к S4 → S5 без снятия).
  action sendWrite(c: str): bool = {
    nondet w = oneOf(Set(nextWrite(c)))
    val mutSkipRemoval = (MUT == "addfirst" and pc.get(c) == "S3")
    val nextPcVal = if (mutSkipRemoval) "S4" else nextPc(c)
    all {
      Set("S2", "S3", "S4", "S5", "S6").contains(pc.get(c)),
      inflight.get(c).valid == false,
      ownLive(c),
      w.valid,
      not(mutSkipRemoval),
      any {
        // сразу доставлено, ответ получен: обычный путь
        nondet r = oneOf(Set(applyWrite(store, w, guardOn)))
        all {
          r._2,
          store' = r._1,
          pc' = pc.set(c, nextPcVal),
          inflight' = inflight, abandoned' = abandoned,
          ghostStaleApplied' = (ghostStaleApplied or (w.guard != store.turn.ver and w.key != "turn")),
          ghostStaleRefused' = ghostStaleRefused,
        },
        // запись ушла и задержана в пути (опоздает): ждём доставки
        all {
          store' = store,
          pc' = pc,
          inflight' = inflight.set(c, w), abandoned' = abandoned,
          ghostStaleApplied' = ghostStaleApplied,
          ghostStaleRefused' = ghostStaleRefused,
        },
      },
      now' = now, turnWrittenAt' = turnWrittenAt, myVer' = myVer, myMark' = myMark, attempt' = attempt, sentAt' = sentAt, seenVer' = seenVer, seenAt' = seenAt,
      plan' = plan, snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace, snapCount' = snapCount,
      ghostAcceptedActive' = ghostAcceptedActive, ghostEarlyCapture' = ghostEarlyCapture,
      ghostTookActive' = ghostTookActive, ghostDoubleTakeLog' = ghostDoubleTakeLog, ghostSigtermReleased' = ghostSigtermReleased, ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed, ghostLateApplied' = ghostLateApplied,
    }
  }

  // Доставка опоздавшей записи: применяется по guard/cas. Ответ: подтверждён либо потерян.
  action deliver(c: str, lost: bool): bool = {
    val w = inflight.get(c)
    nondet r = oneOf(Set(applyWrite(store, w, guardOn)))
    val applied = r._2
    all {
      w.valid,
      store' = r._1,
      inflight' = inflight.set(c, NONE_WRITE), abandoned' = abandoned,
      if (pc.get(c) == "Gone") pc' = pc
      else if (applied and not(lost)) pc' = pc.set(c, nextPc(c))
      else pc' = pc.set(c, "Barrier"),
      ghostStaleApplied' = (ghostStaleApplied or (applied and w.guard != store.turn.ver and w.key != "turn")),
      ghostStaleRefused' = (ghostStaleRefused or (not(applied) and w.guard != store.turn.ver)),
      now' = now, turnWrittenAt' = turnWrittenAt, myVer' = myVer, myMark' = myMark, attempt' = attempt, sentAt' = sentAt, seenVer' = seenVer, seenAt' = seenAt,
      plan' = plan, snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace, snapCount' = snapCount,
      ghostAcceptedActive' = ghostAcceptedActive, ghostEarlyCapture' = ghostEarlyCapture, ghostTookActive' = ghostTookActive, ghostDoubleTakeLog' = ghostDoubleTakeLog, ghostSigtermReleased' = ghostSigtermReleased, ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed, ghostLateApplied' = ghostLateApplied,
    }
  }

  // Барьер (T:80-84): сменить версию своего хода cas, затем читать заново (pc := Decide). Чужой holder — остановиться.
  action barrier(c: str): bool = {
    nondet w = oneOf(Set({ key: "turn", sub: "", cas: myVer.get(c), guard: 0, holder: myMark.get(c), iActive: false, iUnit: "", iTarget: "", pWorker: "", aUnits: EMPTY_US, valid: true }))
    nondet r = oneOf(Set(applyWrite(store, w, guardOn)))
    val bump = MUT != "nobarrierbump"
    all {
      pc.get(c) == "Barrier",
      inflight.get(c).valid == false,
      if (store.turn.holder == myMark.get(c) and store.turn.ver == myVer.get(c)) all {
        if (bump) all { store' = r._1, turnWrittenAt' = now, myVer' = myVer.set(c, r._1.turn.ver), sentAt' = sentAt.set(c, now) }
        else all { store' = store, turnWrittenAt' = turnWrittenAt, myVer' = myVer, sentAt' = sentAt },
        pc' = pc.set(c, "Decide"),
      } else all {
        // чужой holder или версия ушла: стоп этой попытки
        store' = store, turnWrittenAt' = turnWrittenAt, myVer' = myVer.set(c, -1), sentAt' = sentAt,
        pc' = pc.set(c, "Idle"),
      },
      now' = now, myMark' = myMark, attempt' = attempt, seenVer' = seenVer, seenAt' = seenAt, plan' = plan,
      snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace, snapCount' = snapCount, inflight' = inflight, abandoned' = abandoned,
      ghostStaleApplied' = ghostStaleApplied, ghostAcceptedActive' = ghostAcceptedActive, ghostEarlyCapture' = ghostEarlyCapture,
      ghostTookActive' = ghostTookActive, ghostStaleRefused' = ghostStaleRefused, ghostDoubleTakeLog' = ghostDoubleTakeLog, ghostSigtermReleased' = ghostSigtermReleased, ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed.set(c, abandoned.get(c).valid), ghostLateApplied' = ghostLateApplied,
    }
  }


  // Мутант addfirst: S3 пропускается целиком, снятие не выполняется (нарушение N:821-827).
  action skipRemoval(c: str): bool = all {
    MUT == "addfirst",
    pc.get(c) == "S3",
    inflight.get(c).valid == false,
    pc' = pc.set(c, "S4"),
    store' = store, now' = now, turnWrittenAt' = turnWrittenAt, myVer' = myVer, myMark' = myMark, attempt' = attempt, sentAt' = sentAt, seenVer' = seenVer, seenAt' = seenAt,
    plan' = plan, snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace, snapCount' = snapCount, inflight' = inflight, abandoned' = abandoned,
    ghostStaleApplied' = ghostStaleApplied, ghostAcceptedActive' = ghostAcceptedActive, ghostEarlyCapture' = ghostEarlyCapture,
    ghostTookActive' = ghostTookActive, ghostStaleRefused' = ghostStaleRefused, ghostDoubleTakeLog' = ghostDoubleTakeLog, ghostSigtermReleased' = ghostSigtermReleased, ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed, ghostLateApplied' = ghostLateApplied,
  }

  // Таймаут ответа: запись осталась в пути и применится или будет отвергнута позже; контроллер идёт на барьер (T:80, T:83).
  action timeoutWait(c: str): bool = all {
    inflight.get(c).valid,
    abandoned.get(c).valid == false,
    Set("S2", "S3", "S4", "S5", "S6").contains(pc.get(c)),
    abandoned' = abandoned.set(c, inflight.get(c)),
    inflight' = inflight.set(c, NONE_WRITE),
    pc' = pc.set(c, "Barrier"),
    store' = store, now' = now, turnWrittenAt' = turnWrittenAt, myVer' = myVer, myMark' = myMark, attempt' = attempt, sentAt' = sentAt, seenVer' = seenVer, seenAt' = seenAt,
    plan' = plan, snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace, snapCount' = snapCount,
    ghostStaleApplied' = ghostStaleApplied, ghostAcceptedActive' = ghostAcceptedActive, ghostEarlyCapture' = ghostEarlyCapture,
    ghostTookActive' = ghostTookActive, ghostStaleRefused' = ghostStaleRefused, ghostDoubleTakeLog' = ghostDoubleTakeLog, ghostSigtermReleased' = ghostSigtermReleased, ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed, ghostLateApplied' = ghostLateApplied,
  }

  // Опоздавшая запись достигает хранилища: применение только при совпадении guard и cas; pc не меняет.
  action deliverAbandoned(c: str): bool = {
    val w = abandoned.get(c)
    nondet r = oneOf(Set(applyWrite(store, w, guardOn)))
    val applied = r._2
    all {
      w.valid,
      store' = r._1,
      abandoned' = abandoned.set(c, NONE_WRITE),
      ghostStaleApplied' = (ghostStaleApplied or (applied and w.guard != store.turn.ver and w.key != "turn")),
      ghostStaleRefused' = (ghostStaleRefused or (not(applied) and w.guard != store.turn.ver)),
      inflight' = inflight, pc' = pc, now' = now, turnWrittenAt' = turnWrittenAt, myVer' = myVer, myMark' = myMark, attempt' = attempt, sentAt' = sentAt, seenVer' = seenVer, seenAt' = seenAt,
      plan' = plan, snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace, snapCount' = snapCount,
      ghostAcceptedActive' = ghostAcceptedActive, ghostEarlyCapture' = ghostEarlyCapture, ghostTookActive' = ghostTookActive, ghostDoubleTakeLog' = ghostDoubleTakeLog, ghostSigtermReleased' = ghostSigtermReleased, ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed.set(c, false), ghostLateApplied' = (ghostLateApplied or (applied and abandonedPassed.get(c))),
    }
  }

  // Шаг времени: фиксированные приращения с TURN_RENEW и TURN_TERM (T:32-33).
  action tick: bool = {
    nondet dt = oneOf(Set(1, 10, 45))
    all {
      now < 150,
      now' = now + dt,
      store' = store, turnWrittenAt' = turnWrittenAt, pc' = pc, myVer' = myVer, myMark' = myMark, attempt' = attempt, sentAt' = sentAt,
      seenVer' = seenVer, seenAt' = seenAt, plan' = plan, snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace, snapCount' = snapCount,
      inflight' = inflight, abandoned' = abandoned, ghostStaleApplied' = ghostStaleApplied, ghostAcceptedActive' = ghostAcceptedActive, ghostEarlyCapture' = ghostEarlyCapture,
      ghostTookActive' = ghostTookActive, ghostStaleRefused' = ghostStaleRefused, ghostDoubleTakeLog' = ghostDoubleTakeLog, ghostSigtermReleased' = ghostSigtermReleased, ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed, ghostLateApplied' = ghostLateApplied,
    }
  }

  // SIGTERM (L:89): прекращение; без сдачи хода (норма T:75) либо с cas-сдачей (SIGTERM_RELEASE, С4). Запись в полёте может опоздать.
  action sigterm(c: str): bool = {
    nondet w = oneOf(Set({ key: "turn", sub: "", cas: myVer.get(c), guard: 0, holder: 0, iActive: false, iUnit: "", iTarget: "", pWorker: "", aUnits: EMPTY_US, valid: true }))
    nondet r = oneOf(Set(applyWrite(store, w, guardOn)))
    val releaseNow = SIGTERM_RELEASE and myVer.get(c) >= 0 and store.turn.holder == myMark.get(c) and store.turn.ver == myVer.get(c)
    all {
      Set("Decide", "S2", "S3", "S4", "S5", "S6", "Barrier").contains(pc.get(c)),
      if (releaseNow) all { store' = r._1, turnWrittenAt' = now } else all { store' = store, turnWrittenAt' = turnWrittenAt },
      pc' = pc.set(c, "Gone"),
      myVer' = myVer.set(c, -1),
      ghostSigtermReleased' = (ghostSigtermReleased or releaseNow),
      ghostFastAfterSigterm' = ghostFastAfterSigterm, abandonedPassed' = abandonedPassed, ghostLateApplied' = ghostLateApplied,
      now' = now, myMark' = myMark, attempt' = attempt, sentAt' = sentAt, seenVer' = seenVer, seenAt' = seenAt, plan' = plan,
      snapIntent' = snapIntent, snapAssign' = snapAssign, snapPlace' = snapPlace, snapCount' = snapCount, inflight' = inflight, abandoned' = abandoned,
      ghostStaleApplied' = ghostStaleApplied, ghostAcceptedActive' = ghostAcceptedActive, ghostEarlyCapture' = ghostEarlyCapture,
      ghostTookActive' = ghostTookActive, ghostStaleRefused' = ghostStaleRefused, ghostDoubleTakeLog' = ghostDoubleTakeLog,
    }
  }

  action ctrlStep: bool = {
    nondet c = oneOf(CTRLS)
    any {
      observeTurn(c), capture(c), giveUp(c), loseTurn(c), decideNext(c), s3Done(c), sendWrite(c),
      deliver(c, false), barrier(c), skipRemoval(c), deliverAbandoned(c),
      all { NOISE, any { renew(c), deliver(c, true), sigterm(c), timeoutWait(c) } },
    }
  }

  action step: bool = any { ctrlStep, all { NOISE, tick } }

  // Инварианты
  val invCapacity = WORKERS.forall(w => store.assign.get(w).units.size() <= CAP)
  val invOneAssign = UNITS.forall(u => WORKERS.filter(w => store.assign.get(w).units.contains(u)).size() <= 1)
  val invIdleConsistent = store.intent.active or UNITS.forall(u =>
    (store.place.get(u).worker == "" or store.assign.get(store.place.get(u).worker).units.contains(u)) and
    WORKERS.forall(w => not(store.assign.get(w).units.contains(u)) or store.place.get(u).worker == w))
  val invNoStaleApplied = not(ghostStaleApplied)
  val invNoNewWhileActive = not(ghostAcceptedActive)
  val invNoEarlyCapture = not(ghostEarlyCapture)
  // T:83: запись, бывшая в пути на момент барьера, после него не применяется
  val invNoLateApplied = not(ghostLateApplied)
  // Свидетели (ожидается нарушение)
  val witBothPlaced = UNITS.filter(u => store.place.get(u).worker != "").size() < 2
  val witTakeoverActive = not(ghostTookActive and ghostDoubleTakeLog >= 2)
  val witStaleRefused = not(ghostStaleRefused)
  val witCapture = ghostDoubleTakeLog == 0
  val witTwoCaptures = ghostDoubleTakeLog < 2
  val witGone = CTRLS.forall(c => pc.get(c) != "Gone")
  val witMove = not(WORKERS.exists(w => WORKERS.exists(v => w != v and store.place.get("u1").worker == w and ghostDoubleTakeLog >= 2 and store.assign.get(w).units.contains("u1"))) and ghostTookActive)
  val witFastAfterSigterm = not(ghostFastAfterSigterm)
  val witLatePending = not(CTRLS.exists(c => abandonedPassed.get(c)))
  val witCommitWithRecover = not(ghostTookActive and not(store.intent.active))
}

module turn_base { import p04_turn_race(MUT="none", SIGTERM_RELEASE=false, NOISE=true).* }
module turn_sigterm_release { import p04_turn_race(MUT="none", SIGTERM_RELEASE=true, NOISE=true).* }
module turn_noguard { import p04_turn_race(MUT="noguard", SIGTERM_RELEASE=false, NOISE=true).* }
module turn_nofresh { import p04_turn_race(MUT="nofresh", SIGTERM_RELEASE=false, NOISE=true).* }
module turn_skipintent { import p04_turn_race(MUT="skipintent", SIGTERM_RELEASE=false, NOISE=true).* }
module turn_addfirst { import p04_turn_race(MUT="addfirst", SIGTERM_RELEASE=false, NOISE=true).* }
module turn_nobump { import p04_turn_race(MUT="nobarrierbump", SIGTERM_RELEASE=false, NOISE=true).* }
module turn_noage { import p04_turn_race(MUT="noagecheck", SIGTERM_RELEASE=false, NOISE=true).* }
module turn_nofresh_focus { import p04_turn_race(MUT="nofresh", SIGTERM_RELEASE=false, NOISE=false).* }
module turn_addfirst_focus { import p04_turn_race(MUT="addfirst", SIGTERM_RELEASE=false, NOISE=false).* }
module turn_nobump_focus { import p04_turn_race(MUT="nobarrierbump", SIGTERM_RELEASE=false, NOISE=false).* }
module turn_noguard_focus { import p04_turn_race(MUT="noguard", SIGTERM_RELEASE=false, NOISE=false).* }
module turn_skipintent_focus { import p04_turn_race(MUT="skipintent", SIGTERM_RELEASE=false, NOISE=false).* }
module turn_base_focus { import p04_turn_race(MUT="none", SIGTERM_RELEASE=false, NOISE=false).* }
