// P/03: действия устройства и закрытие чужого begun. Одна группа, два держателя
// последовательно (передача эпохи), два запроса группы, зависший вызов, расхождение часов.
// Время: 1 тик = 100 мс. Якоря (срез 244355d1):
//   PERFORM_TIMEOUT 10 с, PERFORM_GRACE 200 мс: forms/runtime-constants.tsv:20,21
//   порядок в группе: spec/03.6:259; закрытие чужого begun: spec/03.6:275-277;
//   срок заявки: spec/03.6:278,288; один вызов на группу, ожидание нового держателя: spec/03.6:315-318
//   ответ, unknown, late: spec/03.6:292-306
// Модель не описывает реализацию: длительность вызова и смещение часов — входы окружения.
module p03_perform {
  const SKEW: int          // смещение часов держателя 1 относительно держателя 0, тиков
  const FSKEW: int         // смещение часов подающего относительно истинных
  const HANG: bool         // вызов может зависнуть
  const TTL: int           // валидность запроса в истинном времени
  const STEPS: Set[int]    // шаги времени
  const FIRST_EPOCH: bool  // эпоха нового держателя первая (тогда ожидания нет)
  // Мутанты
  const NO_BUSY_CHECK: bool
  const NO_TAKEOVER_WAIT: bool
  const NO_ORDER: bool
  const CLOSE_OWN_BEGUN: bool

  pure val T = 100         // PERFORM_TIMEOUT 10 с
  pure val G = 2           // PERFORM_GRACE 0,2 с
  pure val Holders = Set(0, 1)
  pure val Rids = Set(0, 1)
  pure val VU = TTL + FSKEW   // valid_until на часах подающего

  type Mark = { state: str, inst: int, at: int, start: int, late: bool, endedBy: str }
  type S = {
    now: int,
    taken: bool, takeAt: int,
    busy: int -> bool, callRid: int -> int, callStart: int -> int, callEnd: int -> int, callHung: int -> bool,
    marks: int -> Mark,
    active: int -> bool,
    ghostDouble: bool, ghostOverlap: bool, ghostFirstCall1: int,
    ghostEarlyClose: bool, ghostEarlyExpire: bool, ghostSelfClose: bool, ghostHungBlocked: bool,
    ghostLate: bool, ghostSecondExpiredDuringHang: bool, ghostOutOfOrder: bool,
    ghostForeignClose: bool, ghostExpired: bool
  }

  var st: S

  pure val noMark: Mark = { state: "none", inst: -1, at: 0, start: 0, late: false, endedBy: "" }
  pure def clk(h: int, now: int): int = if (h == 1) now + SKEW else now

  pure def outcome(m: Mark): bool = m.state != "none" and m.state != "begun"

  action init = {
    nondet firstCallHung = oneOf(if (HANG) Set(true, false) else Set(false))
    st' = {
      now: 0, taken: false, takeAt: -1,
      busy: Holders.mapBy(h => false), callRid: Holders.mapBy(h => -1), callStart: Holders.mapBy(h => 0),
      callEnd: Holders.mapBy(h => 0), callHung: Holders.mapBy(h => if (h == 0) firstCallHung else false),
      marks: Rids.mapBy(r => noMark),
      active: Holders.mapBy(h => h == 0),
      ghostDouble: false, ghostOverlap: false, ghostFirstCall1: -1,
      ghostEarlyClose: false, ghostEarlyExpire: false, ghostSelfClose: false, ghostHungBlocked: false,
      ghostLate: false, ghostSecondExpiredDuringHang: false, ghostOutOfOrder: false,
      ghostForeignClose: false, ghostExpired: false
    }
  }

  // 03.6:272-291: разбор одного запроса одним держателем
  pure def lookStep(s: S, h: int, r: int, dur: int): S =
    val m = s.marks.get(r)
    val cl = clk(h, s.now)
    val orderOk = if (r == 1) outcome(s.marks.get(0)) else true
    val waitOk = NO_TAKEOVER_WAIT or (h == 0) or FIRST_EPOCH or (s.takeAt >= 0 and s.now >= s.takeAt + T + G)
    val canCall = (not(s.busy.get(h)) or NO_BUSY_CHECK) and s.active.get(h)
    if (outcome(m)) s
    else if (m.state == "begun" and m.inst == h and not(CLOSE_OWN_BEGUN)) s  // шаг 3: свой, ждём
    else if (m.state == "begun") {
      // шаг 5: чужой begun (или свой при мутанте). Старый at против своих часов (at писателя).
      if (m.at + T + G < cl) {
        val early = s.now - m.start < T + G
        { ...s, marks: s.marks.set(r, { ...m, state: "unknown", endedBy: "holder" }),
          ghostEarlyClose: s.ghostEarlyClose or early,
          ghostForeignClose: s.ghostForeignClose or m.inst != h,
          ghostSelfClose: s.ghostSelfClose or (m.inst == h) }
      } else s
    }
    else if (cl > VU) {
      // шаг 6: срок истёк
      val early = s.now < TTL
      { ...s, marks: s.marks.set(r, { ...m, state: "expired", endedBy: "holder" }),
        ghostEarlyExpire: s.ghostEarlyExpire or early,
        ghostExpired: true,
        ghostSecondExpiredDuringHang: s.ghostSecondExpiredDuringHang or
          (r == 1 and s.busy.get(0) and s.callHung.get(0)) }
    }
    else if (canCall and waitOk and (orderOk or NO_ORDER)) {
      val hung = s.callHung.get(h)
      val newBusy = s.busy.set(h, true)
      val overlap = newBusy.get(0) and newBusy.get(1)
      { ...s,
        marks: s.marks.set(r, { state: "begun", inst: h, at: cl, start: s.now, late: false, endedBy: "" }),
        busy: newBusy,
        callRid: s.callRid.set(h, r),
        callStart: s.callStart.set(h, s.now),
        callEnd: s.callEnd.set(h, s.now + dur),
        ghostDouble: s.ghostDouble or s.busy.get(h),
        ghostOverlap: s.ghostOverlap or overlap,
        ghostFirstCall1: if (h == 1 and s.ghostFirstCall1 < 0) s.now else s.ghostFirstCall1,
        ghostOutOfOrder: s.ghostOutOfOrder or (r == 1 and not(outcome(s.marks.get(0)))) }
    }
    else s

  action look = {
    nondet h = oneOf(Holders)
    nondet r = oneOf(Rids)
    nondet dur = oneOf(Set(1, 50, T + G, T + G + 50))
    all { st.active.get(h), st' = lookStep(st, h, r, dur) }
  }

  action advance = {
    nondet d = oneOf(STEPS)
    val now2 = st.now + d
    st' = { ...st, now: now2,
      ghostHungBlocked: st.ghostHungBlocked or (st.busy.get(0) and st.callHung.get(0) and now2 >= st.callStart.get(0) + 3 * (T + G)) }
  }

  // Ответ вызова: только если не завис; 03.6:292-300 (поздний — late)
  action callReturn = {
    nondet h = oneOf(Holders)
    val r = st.callRid.get(h)
    val m = st.marks.get(if (r < 0) 0 else r)
    all {
      r >= 0, st.busy.get(h), not(st.callHung.get(h)), st.now >= st.callEnd.get(h),
      st' = { ...st,
        busy: st.busy.set(h, false),
        callRid: st.callRid.set(h, -1),
        marks: if (m.state == "begun") st.marks.set(r, { ...m, state: "performed", endedBy: "" })
               else if (m.state == "unknown") st.marks.set(r, { ...m, state: "performed", late: true, endedBy: "" })
               else st.marks,
        ghostLate: st.ghostLate or m.state == "unknown"
      }
    }
  }

  // Без ответа за T+G: unknown своего вызова, группа остаётся занятой, 03.6:305-306,315
  action timeout = {
    nondet h = oneOf(Holders)
    val r = st.callRid.get(h)
    val m = st.marks.get(if (r < 0) 0 else r)
    all {
      r >= 0, st.busy.get(h), m.state == "begun", m.inst == h,
      st.now >= st.callStart.get(h) + T + G,
      st' = { ...st, marks: st.marks.set(r, { ...m, state: "unknown", endedBy: "holder" }) }
    }
  }

  // Передача эпохи: прежний держатель теряет допуск, но уже посланный вызов продолжается (03.6:318)
  action takeover = all {
    not(st.taken),
    st' = { ...st, taken: true, takeAt: st.now, active: st.active.set(0, false).set(1, true) }
  }

  action step = any { look, advance, callReturn, timeout, takeover }

  // ---- Свойства ----
  val OnePerGroupOfHolder = not(st.ghostDouble)
  val TakeoverWaitHonored = st.ghostFirstCall1 < 0 or FIRST_EPOCH or st.ghostFirstCall1 >= st.takeAt + T + G
  val NoEarlyForeignClose = not(st.ghostEarlyClose)
  val NoEarlyExpire = not(st.ghostEarlyExpire)
  val NoSelfForeignClose = not(st.ghostSelfClose)
  val OrderInGroup = not(st.ghostOutOfOrder)
  val HungDoesNotBlockForever = not(st.ghostHungBlocked)

  // Свидетели
  val W_overlap = not(st.ghostOverlap)
  val W_late = not(st.ghostLate)
  val W_secondExpiredDuringHang = not(st.ghostSecondExpiredDuringHang)
  val W_begun = Rids.forall(r => st.marks.get(r).state != "begun")
  val W_unknown = Rids.forall(r => st.marks.get(r).state != "unknown")
  val W_performed = Rids.forall(r => st.marks.get(r).state != "performed")
  val W_taken = not(st.taken)
  val W_foreignClose = not(st.ghostForeignClose)
  val W_expired = not(st.ghostExpired)
}
