// outcomes.qnt — неизвестные исходы (С14): потерянный ответ на отчёт и повтор правки своей консоли.
// Якоря: 09.1:194-198,1437,1443; acc:291-309; 09.1:443,458; 06.1:690-709,711,781-784; 06.1 DONE_ANSWER_KEEP, CLAIM_TAKEOVER_AFTER.

// --- Отчёт: дельта против подтверждённой базы, потеря ответа. ---
module report_base {
  const BASE_CHECK: bool // мутант: шаг 3 acc:296 выключен
  pure val KEYS = Set("a", "b")
  var memberDoc: Set[str]
  var baseDoc: Set[str]
  var baseRev: int       // last_rev, подтверждённая база (0 — целое)
  var hStored: Set[str]
  var hRev: int
  var confirmedMismatch: bool // подтверждённый ответ, а копия держателя отличается от посланного документа
  var lostPending: bool     // потерян ответ на последнюю дельту
  var rebasedAfterLost: bool
  var lastAction: str

  action init = all {
    lostPending' = false, rebasedAfterLost' = false,
    memberDoc' = Set("a"), baseDoc' = Set(), baseRev' = 0, hStored' = Set(), hRev' = 0,
    confirmedMismatch' = false, lastAction' = "init",
  }
  action edit = { nondet k = oneOf(KEYS) all {
    memberDoc' = if (memberDoc.contains(k)) memberDoc.exclude(Set(k)) else memberDoc.union(Set(k)),
    baseDoc' = baseDoc, baseRev' = baseRev, hStored' = hStored, hRev' = hRev,
    confirmedMismatch' = confirmedMismatch, lostPending' = lostPending, rebasedAfterLost' = rebasedAfterLost, lastAction' = "edit" } }

  pure def added(m: Set[str], b: Set[str]): Set[str] = m.exclude(b)
  pure def deleted(m: Set[str], b: Set[str]): Set[str] = b.exclude(m)

  // Посылка: сервер отвечает атомарно с записью (acc:289 шаг 0 — по одному на члена).
  action send = {
    nondet lost = oneOf(Set(true, false))
    if (BASE_CHECK and baseRev > 0 and baseRev != hRev)
      // 409 rebase -> last_rev = 0 и тут же целым (09.1:1437): откат базы отдельным шагом.
      all {
        baseRev' = 0, baseDoc' = Set(), memberDoc' = memberDoc, hStored' = hStored, hRev' = hRev,
        confirmedMismatch' = confirmedMismatch,
        rebasedAfterLost' = (rebasedAfterLost or lostPending), lostPending' = false, lastAction' = "rebase",
      }
    else
      val nextStored = if (baseRev == 0) memberDoc
                       else hStored.union(added(memberDoc, baseDoc)).exclude(deleted(memberDoc, baseDoc))
      val isGen = nextStored != hStored
      val newRev = if (isGen) hRev + 1 else hRev
      all {
        hStored' = nextStored, hRev' = newRev, memberDoc' = memberDoc,
        if (lost)
          all { baseDoc' = baseDoc, baseRev' = baseRev, confirmedMismatch' = confirmedMismatch,
                lostPending' = (baseRev > 0 or lostPending), rebasedAfterLost' = rebasedAfterLost,
                lastAction' = if (baseRev == 0) "sendWholeLost" else "sendDeltaLost" }
        else
          all { baseDoc' = memberDoc, baseRev' = newRev,
                confirmedMismatch' = (confirmedMismatch or nextStored != memberDoc),
                lostPending' = false, rebasedAfterLost' = rebasedAfterLost,
                lastAction' = if (baseRev == 0) "sendWholeOk" else "sendDeltaOk" },
      }
  }
  action step = any { edit, send }

  // Подтверждённый успех: копия держателя равна посланному документу (acc:296 + 09.1:194-198).
  val ConfirmedMatches = not(confirmedMismatch)
  val BaseNotAhead = baseRev <= hRev
  val witRebaseConverge = not(lastAction == "sendWholeOk" and rebasedAfterLost)
  val witConfirmedMismatch = not(confirmedMismatch)
}
module report_text { import report_base(BASE_CHECK = true).* }
module report_mut_nobase { import report_base(BASE_CHECK = false).* }

// --- Правка своей консоли: повтор с тем же Idempotency-Key. ---
module edit_base {
  const KEEP: int   // DONE_ANSWER_KEEP 86400 (06 const), минимум нормы; большое значение — контроль без истечения
  pure val TAKEOVER = 30 // CLAIM_TAKEOVER_AFTER (06 const)
  var now: int
  var claim: str     // none | pending | done
  var claimAt: int
  var applied: int   // сколько раз правка применена к строке
  var outcome: bool  // агент записал исход
  var sends: int
  var lostOnce: bool
  var lastAction: str

  action init = all { lostOnce' = false, now' = 0, claim' = "none", claimAt' = 0, applied' = 0, outcome' = false, sends' = 0, lastAction' = "init" }
  action tick = { nondet dt = oneOf(Set(1, TAKEOVER, 86400)) all {
    lostOnce' = lostOnce,
    now' = now + dt, claim' = claim, claimAt' = claimAt, applied' = applied, outcome' = outcome, sends' = sends, lastAction' = "tick" } }

  // Посылка правки с ключом (09.1:443); повтор до исхода (09.1:458).
  // crash: "none" — исполнение до конца; "before" — падение между claim и записью цели;
  // "after" — падение после записи цели до сохранения ответа (06.1:784: pending, исход неизвестен).
  action send = {
    nondet delivered = oneOf(Set(true, false))
    nondet crash = oneOf(Set("none", "before", "after"))
    all {
      not(outcome), sends < 12,
      sends' = sends + 1,
      now' = now,
      if (claim == "done" and now - claimAt < KEEP)
        // сохранённый ответ (06.1:704)
        all { claim' = claim, claimAt' = claimAt, applied' = applied, lostOnce' = (lostOnce or not(delivered)),
              outcome' = delivered, lastAction' = if (delivered) "savedAnswer" else "savedLost" }
      else if (claim == "pending" and now - claimAt < TAKEOVER)
        // 409 in flight (06.1:700) -> повтор следующим проходом (09.1:458)
        all { claim' = claim, claimAt' = claimAt, applied' = applied, lostOnce' = lostOnce, outcome' = false, lastAction' = "inFlight" }
      else
        // претензии нет, перехват pending после CLAIM_TAKEOVER_AFTER (06.1:711: сначала смотрят цель),
        // либо истекла память done (06.1:182 DONE_ANSWER_KEEP — новая претензия, новое исполнение).
        val inc = if (claim == "pending" and applied > 0) 0 else 1
        all {
          applied' = applied + (if (crash == "before") 0 else inc),
          claim' = if (crash == "none") "done" else "pending",
          claimAt' = now,
          outcome' = (crash == "none" and delivered),
          lostOnce' = (lostOnce or (crash == "none" and not(delivered))),
          lastAction' = if (claim == "done") "reapplied" else (if (crash == "before") "crashBefore" else (if (crash == "after") "crashAfter" else (if (delivered) "appliedOk" else "appliedLost"))),
        },
    }
  }
  action step = any { tick, send }
  val AtMostOnce = applied <= 1
  val witSaved = not(outcome and applied == 1 and lostOnce)
  val witAppliedTwice = not(applied >= 2)
}
module edit_text { import edit_base(KEEP = 86400).* }
module edit_inf { import edit_base(KEEP = 1000000000).* }
