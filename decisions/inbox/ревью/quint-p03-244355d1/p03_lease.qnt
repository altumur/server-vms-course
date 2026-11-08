// P/03: один процесс воркера. Поток цикла и поток заместителя, шаг аренды,
// окно действий, тишина, потолок, скачок стенных часов.
// Время: 1 тик = 1/12 с, чтобы LEASE_EVERY = 25/3, STALL = 25/2 и WAKE <= 25/4
// были точными целыми. Все чтения хранилища моделируются как операции с задержкой;
// t0 операции — момент посылки. Это модель текста норм, а не реализации.
//
// Якоря (срез 244355d1):
//   LEASE_TTL 30, LEASE_MARGIN 5: forms/runtime-constants.tsv:4,5
//   LEASE_EVERY, again: spec/03.2:45,46
//   STALL, WAKE: spec/03.4:168,169; FOR 300: common/contracts/env-file.md:120
//   SLOT_TERM 45: common/contracts/slot.md:45
//   may_act/may_write, unconfirmed_max: spec/03.2:162,165,166
//   confirm(id): spec/03.2:496-504
//   шаг аренды: spec/03.2:568-582; цикл: spec/03.3:80-107; заместитель: spec/03.4:374-385
module p03_lease {
  // Конфигурация экземпляра
  const N: int              // единиц под воркером
  const HORIZON: int        // граница времени, тиков
  const DURS: Set[int]      // длительность обычного шага цикла (reconcile, pump, heartbeat)
  const POLLS: Set[int]     // длительность шага 6 (пауза): POLL — выбор реализации, 03.3:42
  const LATS: Set[int]      // задержка ответа хранилища/ожидание no_reply (wait, store-client:89)
  const WAKES: Set[int]     // период заместителя, не более WAKE_MAX
  const CEIL: int           // unconfirmed_max в тиках: 0 = off, -1 = forever
  const FAULTS: int         // допустимое число переключений связи с хранилищем
  const UPFLIP_NOT_BEFORE: int // возврат связи не раньше этого момента (0: любой)
  const JUMPS: Set[int]     // скачки стенных часов (пусто: нет)
  const WALL_CADENCE: bool  // каденция шага аренды читает стенные часы (норма clock не называет)
  const WALL_AGE: bool      // возраст шага заместителя читает стенные часы
  const STANDIN: bool       // заместитель есть
  const STEAL: bool         // чужой номер эпохи возможен
  const FOREIGN: bool       // чужой захват слота возможен
  const WRITE_FAULT: bool   // записи теряются при живых чтениях (норма 03.2:163-164, F3)
  const INIT_DELAY: Set[int]// положение первого пробуждения заместителя
  const POLL_MIN: int       // нижняя граница паузы (0: нет)
  const INIT_DUE: bool      // первый шаг аренды уже назрел (нужно для начала с нулевыми длительностями)
  // Мутанты (false = норма)
  const LAST_AT_ANSWER: bool    // last по ответу, а не по посылке
  const SLOT_AT_ANSWER: bool    // срок слота по ответу, а не по посылке
  const REVIVE_FENCED: bool     // чужой номер не закрепляет fenced
  const REVIVE_OVERSLEPT: bool  // проспанное окно не даёт lost
  // Контроль (не норма): условие заместителя от последнего подтверждения
  const STANDIN_FROM_CONFIRM: bool

  pure val W = 300           // LEASE_TTL - LEASE_MARGIN = 25 с
  pure val EVERY = 100       // LEASE_EVERY = 25/3 с
  pure val STALL = 150       // 25/2 с
  pure val FOR_ = 3600       // 300 с
  pure val SLOT_TERM = 540   // 45 с
  pure val DEAD = 1000000    // момент, которого нет

  pure val Units = 0.to(N - 1)

  type Op = { k: str, u: int, t0: int, ends: int }
  type S = {
    now: int, wallOff: int, storeUp: bool, writeUp: bool, flips: int, jumps: int,
    lp: Op, sp: Op, stepBegan: int, leaseStart: int, again: bool,
    last: int -> int, status: int -> str, slotSend: int, nobody: bool,
    foreignSlot: bool, stolen: int -> bool,
    ghostSend: int -> int, ghostSlot: int,
    everSilent: bool, everRecovered: bool, everStandin: bool,
    ghostLost: int -> bool, ghostFenced: int -> bool, ghostMissed: int -> bool,
    leaseSteps: int, reqs: int
  }

  var st: S

  pure def idle(ends: int): Op = { k: "idle", u: -1, t0: 0, ends: ends }
  pure def op(k: str, u: int, t0: int, ends: int): Op = { k: k, u: u, t0: t0, ends: ends }
  pure val dead: Op = op("dead", -1, 0, DEAD)

  pure def maxI(a: int, b: int): int = if (a > b) a else b
  pure def minI(a: int, b: int): int = if (a < b) a else b

  pure def cadenceClock(s: S, t: int): int = if (WALL_CADENCE) t + s.wallOff else t
  pure def ageClock(s: S, t: int): int = if (WALL_AGE) t + s.wallOff else t

  // N1.6: unconfirmed считается от конца окна (03.2:160), предикаты 03.2:162,165
  pure def windowOpen(s: S, t: int, u: int): bool = t - s.last.get(u) < W
  pure def unconfirmed(s: S, t: int, u: int): int = maxI(0, t - (s.last.get(u) + W))
  pure def slotTermOpen(s: S, t: int): bool = t < s.slotSend + SLOT_TERM
  pure def mayAct(s: S, t: int, u: int): bool =
    s.status.get(u) != "fenced" and s.status.get(u) != "lost"
      and windowOpen(s, t, u) and slotTermOpen(s, t) and not(s.nobody)
  pure def mayWrite(s: S, t: int, u: int): bool =
    mayAct(s, t, u) or (s.status.get(u) == "silent"
      and (CEIL < 0 or unconfirmed(s, t, u) < CEIL))

  pure def setStatus(s: S, u: int, v: str): S =
    { ...s, status: s.status.set(u, v),
      ghostLost: if (v == "lost") s.ghostLost.set(u, true) else s.ghostLost,
      ghostFenced: if (v == "fenced") s.ghostFenced.set(u, true) else s.ghostFenced }

  // confirm(id), 03.2:496-504. fromLoop: only the loop's confirm counts for "became silent".
  pure def applyConfirm(s: S, u: int, t0: int, t: int, fromLoop: bool): S =
    val cur = s.status.get(u)
    val missed = t0 - s.last.get(u) >= W and cur != "silent"
    val s0 = if (missed) { ...s, ghostMissed: s.ghostMissed.set(u, true) } else s
    if (cur == "lost" and not(REVIVE_OVERSLEPT)) s0
    else if (cur == "fenced" and not(REVIVE_FENCED)) s0
    else if (s.storeUp and s.stolen.get(u) and not(REVIVE_FENCED and cur == "fenced")) setStatus(s0, u, "fenced")
    else if (s.storeUp) {
      val prev = s.last.get(u)
      if (missed and not(REVIVE_OVERSLEPT)) setStatus(s0, u, "lost")
      else
        val s1 = { ...s0,
          last: s.last.set(u, maxI(prev, if (LAST_AT_ANSWER) t else t0)),
          ghostSend: s.ghostSend.set(u, maxI(s.ghostSend.get(u), t0)),
          everRecovered: s.everRecovered or cur == "silent" }
        setStatus(s1, u, "confirmed")
    } else {
      if (cur == "silent") s0
      else if (t0 - s.last.get(u) < W) {
        val s1 = { ...s0, everSilent: true, again: s.again or fromLoop }
        setStatus(s1, u, "silent")
      } else setStatus(s0, u, "lost")
    }

  // renew, 03.2:408-411,569-573: при ответе с чужим держателем — fence всех
  pure def fenceAll(s: S): S =
    val s1 = Units.fold(s, (acc, u) => setStatus(acc, u, "fenced"))
    { ...s1, nobody: true, lp: dead, sp: dead }

  pure def applyRenew(s: S, t0: int, t: int, fromLoop: bool): S =
    if (s.storeUp and s.foreignSlot) fenceAll(s)
    else if (s.storeUp and s.writeUp) {
      ...s,
      slotSend: maxI(s.slotSend, if (SLOT_AT_ANSWER) t else t0),
      ghostSlot: maxI(s.ghostSlot, t0)
    } else { ...s, again: s.again or fromLoop }

  // Шаг 2 конца шага аренды: lost = те, у кого нет may_write (03.2:575)
  pure def endLeaseEval(s: S, t: int): S =
    Units.fold(s, (acc, u) => {
      val c = acc.status.get(u)
      if (c == "fenced" or c == "lost" or mayWrite(acc, t, u)) acc
      else setStatus(acc, u, "lost")
    })

  pure def startOp(k: str, u: int, t: int, l: int): Op = op(k, u, t, t + l)

  // Завершение операции цикла в момент t. d — длительность следующего обычного шага,
  // p — паузы, l — задержка следующей операции.
  pure def loopEvent(s: S, t: int, d: int, p: int, l: int): S =
    val op0 = s.lp
    val base = { ...s, now: t }
    if (op0.k == "rec") {
      ...base, stepBegan: ageClock(base, t), lp: op("pump", -1, t, t + d)
    } else if (op0.k == "pump") {
      val due = cadenceClock(base, t) - base.leaseStart >= EVERY or base.again
      if (due) {
        ...base, lp: startOp("renew", -1, t, l), stepBegan: ageClock(base, t),
        leaseStart: cadenceClock(base, t), again: false,
        leaseSteps: base.leaseSteps + 1, reqs: base.reqs + 1
      } else {
        ...base, stepBegan: ageClock(base, t), lp: op("hb", -1, t, t + d)
      }
    } else if (op0.k == "hb") {
      ...base, stepBegan: ageClock(base, t), lp: op("pause", -1, t, t + p)
    } else if (op0.k == "pause") {
      ...base, stepBegan: ageClock(base, t), lp: op("rec", -1, t, t + d)
    } else if (op0.k == "renew") {
      val s1 = applyRenew(base, op0.t0, t, true)
      if (s1.lp.k == "dead") s1
      else { ...s1, lp: startOp("floor", -1, t, l), reqs: s1.reqs + 1 }
    } else if (op0.k == "floor") {
      if (N > 0) { ...base, lp: startOp("confirm", 0, t, l), reqs: base.reqs + 1 }
      else { ...base, stepBegan: ageClock(base, t), lp: op("hb", -1, t, t + d) }
    } else if (op0.k == "confirm") {
      val s1 = applyConfirm(base, op0.u, op0.t0, t, true)
      if (op0.u + 1 < N) { ...s1, lp: startOp("confirm", op0.u + 1, t, l), reqs: s1.reqs + 1 }
      else {
        val s2 = endLeaseEval(s1, t)
        { ...s2, stepBegan: ageClock(s2, t), lp: op("hb", -1, t, t + d) }
      }
    } else base

  // Заместитель: 03.4:374-385. Условие возраста — по текущему шагу цикла.
  pure def standinEligible(s: S, t: int): bool =
    if (STANDIN_FROM_CONFIRM)
      not(s.nobody) and Units.exists(u => s.status.get(u) != "fenced" and s.status.get(u) != "lost"
        and t - s.last.get(u) >= W / 3)
    else {
      val age = ageClock(s, t) - s.stepBegan
      not(s.nobody) and age > STALL and age <= FOR_
    }

  pure def standEvent(s: S, t: int, l: int, w: int): S =
    val op0 = s.sp
    val base = { ...s, now: t }
    if (op0.k == "idle") {
      if (standinEligible(base, t))
        { ...base, sp: startOp("renew", -1, t, l), reqs: base.reqs + 1, everStandin: true }
      else { ...base, sp: idle(t + w) }
    } else if (op0.k == "renew") {
      val s1 = applyRenew(base, op0.t0, t, false)
      if (s1.sp.k == "dead") s1
      else if (N > 0) { ...s1, sp: startOp("confirm", 0, t, l), reqs: s1.reqs + 1 }
      else { ...s1, sp: idle(t + w) }
    } else if (op0.k == "confirm") {
      val s1 = applyConfirm(base, op0.u, op0.t0, t, false)
      if (op0.u + 1 < N) { ...s1, sp: startOp("confirm", op0.u + 1, t, l), reqs: s1.reqs + 1 }
      else { ...s1, sp: idle(t + w) }
    } else base

  action init = all {
    nondet firstWake = oneOf(INIT_DELAY)
    st' = {
      now: 0, wallOff: 0, storeUp: true, writeUp: true, flips: 0, jumps: 0,
      lp: op("rec", -1, 0, 0), sp: if (STANDIN) idle(firstWake) else dead,
      stepBegan: 0, leaseStart: if (INIT_DUE) 0 - EVERY else 0, again: false,
      last: Units.mapBy(u => 0), status: Units.mapBy(u => "confirmed"),
      slotSend: 0, nobody: false, foreignSlot: false,
      stolen: Units.mapBy(u => false),
      ghostSend: Units.mapBy(u => 0), ghostSlot: 0,
      everSilent: false, everRecovered: false, everStandin: false,
      ghostLost: Units.mapBy(u => false), ghostFenced: Units.mapBy(u => false), ghostMissed: Units.mapBy(u => false),
      leaseSteps: 0, reqs: 0
    }
  }

  pure def nextEvent(s: S): int = minI(s.lp.ends, s.sp.ends)

  action step = {
    nondet d = oneOf(DURS)
    nondet p = oneOf(POLLS)
    nondet l = oneOf(LATS)
    nondet w = oneOf(WAKES)
    val e = nextEvent(st)
    any {
      all { st.lp.ends <= st.sp.ends, e <= HORIZON, st' = loopEvent(st, e, d, p, l) },
      all { STANDIN, st.sp.ends <= st.lp.ends, e <= HORIZON, st' = standEvent(st, e, l, w) },
      all { st.flips < FAULTS, st.storeUp or st.now >= UPFLIP_NOT_BEFORE,
            st' = { ...st, storeUp: not(st.storeUp), flips: st.flips + 1 } },
      all { JUMPS != Set(), st.jumps < 1,
        nondet j = oneOf(JUMPS)
        st' = { ...st, wallOff: st.wallOff + j, jumps: st.jumps + 1 } },
      all { STEAL, Units.exists(u => not(st.stolen.get(u))),
        nondet u = oneOf(Units)
        st' = { ...st, stolen: st.stolen.set(u, true) } },
      all { FOREIGN, not(st.foreignSlot), st' = { ...st, foreignSlot: true } },
      all { WRITE_FAULT, st.writeUp, st' = { ...st, writeUp: false } },
      // Конец горизонта: иначе застрянет на шаге без успеха
      all { e > HORIZON, st' = st },
    }
  }

  // ---- Свойства ----
  // R041 (03.2:592): при тишине на шагах 1 и 2 ничего не теряется до потолка.
  // Проверяем: lost только после потолка или проспанного окна при ответившем хранилище.
  val NoLost = Units.forall(u => st.status.get(u) != "lost")
  val LostOnlyPastCeiling = Units.forall(u =>
    st.status.get(u) != "lost" or (CEIL >= 0 and st.now >= st.ghostSend.get(u) + W + CEIL))

  val ActWithinWindowFromSend = Units.forall(u =>
    not(mayAct(st, st.now, u)) or st.now < st.ghostSend.get(u) + W)
  val ActWithinSlotTerm = Units.forall(u =>
    not(mayAct(st, st.now, u)) or st.now < st.ghostSlot + SLOT_TERM)
  val FencedStays = Units.forall(u => not(st.ghostFenced.get(u)) or st.status.get(u) == "fenced")
  val LostStays = Units.forall(u => not(st.ghostLost.get(u)) or st.status.get(u) == "lost")
  // Проспанное окно: как только посылка оказалась за окном (t0 - last >= W, не silent), единица lost.
  val MissedIsLost = Units.forall(u => not(st.ghostMissed.get(u))
    or st.status.get(u) == "lost" or st.status.get(u) == "fenced")
  // Чистая алгебра норм
  val WriteOnlyInWindowOrCeiling = Units.forall(u =>
    not(mayWrite(st, st.now, u)) or mayAct(st, st.now, u)
      or (st.status.get(u) == "silent" and (CEIL < 0 or st.now < st.last.get(u) + W + CEIL)))

  // Шаги аренды в одну точку времени под again (С15): штатные паузы ноль и отказ связи мгновенно.
  val NoZenoAgain = st.leaseSteps < 3 or st.now > 0
  // Контроль С15: шагов не больше чем один на паузу POLL_MIN
  val StepsBounded = POLL_MIN <= 0 or st.leaseSteps <= 1 + st.now / POLL_MIN

  // Свидетели достижимости: инвариант отрицания
  val W_lost = Units.forall(u => st.status.get(u) != "lost")
  val W_silent = not(st.everSilent)
  val W_recovered = not(st.everRecovered)
  val W_standin = not(st.everStandin)
  val W_fenced = Units.forall(u => not(st.ghostFenced.get(u)))
  val W_nobody = not(st.nobody)
  val W_leaseStep = st.leaseSteps < 2
  // Окно действий открыто, срок слота истёк (F3: живые чтения при потерянных записях)
  val W_slot_term_over = Units.forall(u => not(windowOpen(st, st.now, u)
    and st.status.get(u) == "confirmed" and not(slotTermOpen(st, st.now))))
}
