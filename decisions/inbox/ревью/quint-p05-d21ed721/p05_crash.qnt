// P/05 сбой при записи (находки C17 и M6). Срез d21ed721.
// Часть 1: приём копии (PUT /mirror) — публикация и ответ 204 против потери питания.
// Часть 2: rewrite — снятие надгробия и публикация тела против потери питания.
module p05_crash {
  const BARRIER: bool        // C17: барьер до 204 (норма не требует — вариант)
  const ORDER: str           // M6: "ANY" | "BODY_FIRST" | "TOMB_FIRST"

  type S = {
    // Часть 1
    pub: bool, durable: bool, reply: bool, crashedA: bool,
    copyAfterCrash: bool,
    // Часть 2: надгробие есть, тела нет, у соседа старая копия; новая запись
    tomb: bool, body: bool, oldCopyAtPeer: bool,
    tombDone: bool, bodyDone: bool, crashedB: bool, ordBody: bool, ordChosen: bool
  }
  var s: S

  action init = s' = {
    pub: false, durable: false, reply: false, crashedA: false, copyAfterCrash: false,
    tomb: true, body: false, oldCopyAtPeer: true,
    tombDone: false, bodyDone: false, crashedB: false, ordBody: true, ordChosen: false
  }

  // Часть 1.
  action publishA = all { not(s.pub), not(s.crashedA), s' = s.with("pub", true) }
  action flushA = all { s.pub, not(s.durable), not(s.crashedA), s' = s.with("durable", true) }
  action replyA = all { s.pub, not(s.reply), not(s.crashedA),
    if (BARRIER) s.durable else true,
    s' = s.with("reply", true) }
  action crashA = all { not(s.crashedA),
    s' = s.with("crashedA", true).with("pub", s.durable).with("copyAfterCrash", s.durable) }
  action stutterA = all { s.crashedA, s' = s }

  // Часть 2: действия снятия надгробия и публикации тела разделены, порядок — выбор реализации.
  action chooseOrder = all { not(s.ordChosen),
    nondet firstBody = oneOf(if (ORDER == "ANY") Set(true, false) else Set(ORDER == "BODY_FIRST"))
    s' = s.with("ordBody", firstBody).with("ordChosen", true) }
  action rmTomb = all { s.ordChosen, s.tomb, not(s.crashedB),
    if (s.ordBody) s.bodyDone else true,
    s' = s.with("tomb", false).with("tombDone", true) }
  action pubBody = all { s.ordChosen, not(s.body), not(s.crashedB),
    if (s.ordBody) true else s.tombDone,
    s' = s.with("body", true).with("bodyDone", true) }
  action crashB = all { not(s.crashedB), s.ordChosen, s' = s.with("crashedB", true) }

  action step = any { publishA, flushA, replyA, crashA, stutterA, chooseOrder, rmTomb, pubBody, crashB }

  // C17: ответ 204 означает, что копия переживает потерю питания.
  val inv_ackDurable = (s.reply and s.crashedA) implies s.copyAfterCrash
  // M6: после сбоя при незавершённой rewrite нет случая «надгробия нет, нового тела нет, у соседа старая копия»
  // (иначе сосед считает копию живой — факт удаления утрачен).
  val inv_noResurrect = not(s.crashedB and not(s.tomb) and not(s.body) and s.oldCopyAtPeer)
  val inv_types = true

  // Свидетели.
  val wit_ack = not(s.reply and not(s.crashedA))
  val wit_ackThenCrash = not(s.reply and s.crashedA)
  val wit_rewriteDone = not(s.bodyDone and s.tombDone)
  val wit_crashMid = not(s.crashedB and (s.bodyDone or s.tombDone) and not(s.bodyDone and s.tombDone))
}
