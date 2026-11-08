// Модель 6 из 6 (срез 244355d1): дверь/ожидание лидера (С12 отчёта).
// Нормы: 01.3-store.norms.md:51 (leader_wait: интервал от потери лидера → 503 unavailable; без ответа лидера → ambiguous),
//   :59, :70 (попытка DOOR_REQUEST_TIMEOUT+MARGIN; все голосующие недоступны → 503), :158-161 (исходы answered/unavailable/ambiguous),
//   forms/runtime-constants.tsv (2 и 1 с), forms/daemon-flags.tsv (-leader-wait 5s) — здесь параметры T_ATTEMPT и LEADER_WAIT,
//   01.1:766 (ambiguous: повтор только с тем же id), :738 (R142).
// ДОПУЩЕНИЯ: D1 — без задержек: лидер принимает пересланное мгновенно, голосующий отвечает 503 точно на истечении интервала
//   (реальные задержки только расширят окно ambiguous); D2 — один клиентский запрос и повторы; D3 — порядок: «лидер потерян»
//   достижим до отправки или после. Число попыток двери и общий срок нормой не заданы — не моделируются числа, см. отчёт.
// Граница: одна запись, повторы до MAX_RETRIES; время модельное.
module door {
  pure val T_ATTEMPT = 3      // DOOR_REQUEST_TIMEOUT + DOOR_REQUEST_MARGIN
  pure val LEADER_WAIT = 5    // эффективный -leader-wait
  pure val MAX_TIME = 10
  pure val MAX_RETRIES = 2
  pure val ALLOW_NO_ID = true  // запись без id (проверка: повтор без id небезопасен)
  // Мутанты
  pure val MUT_DOUBLE_APPLY_WITH_ID = false  // повтор с id применяется заново
  pure val MUT_VOTER_NEVER_ANSWERS = false   // голосующий не отвечает 503 (нет ожидания)

  var t: int
  var leaderUp: bool
  var lostAt: int
  var sent: bool
  var sentAt: int
  var reachedLeader: bool      // запись доставлена лидеру (к моменту ответа неизвестна судьба)
  var applied: int             // сколько раз применена
  var hasId: bool
  var doorAnswer: str          // "" | ambiguous | unavailable | answered
  var voterAnswered503: bool
  var allVotersDown: bool
  var retries: int

  action init = all {
    t' = 0, leaderUp' = true, lostAt' = -1, sent' = false, sentAt' = -1, reachedLeader' = false, applied' = 0,
    hasId' = true, doorAnswer' = "", voterAnswered503' = false, allVotersDown' = false, retries' = 0,
  }

  action tick = all {
    t < MAX_TIME,
    t' = t + 1,
    leaderUp' = leaderUp, lostAt' = lostAt, sent' = sent, sentAt' = sentAt, reachedLeader' = reachedLeader, applied' = applied, hasId' = hasId, doorAnswer' = doorAnswer, voterAnswered503' = voterAnswered503, allVotersDown' = allVotersDown, retries' = retries,
  }
  action loseLeader = all {
    leaderUp,
    leaderUp' = false, lostAt' = t,
    t' = t, sent' = sent, sentAt' = sentAt, reachedLeader' = reachedLeader, applied' = applied, hasId' = hasId, doorAnswer' = doorAnswer, voterAnswered503' = voterAnswered503, allVotersDown' = allVotersDown, retries' = retries,
  }
  action cutAllVoters = all {
    not(sent),
    allVotersDown' = true,
    t' = t, leaderUp' = leaderUp, lostAt' = lostAt, sent' = sent, sentAt' = sentAt, reachedLeader' = reachedLeader, applied' = applied, hasId' = hasId, doorAnswer' = doorAnswer, voterAnswered503' = voterAnswered503, retries' = retries,
  }
  action clientSend = {
    nondet withId = Set(true, false).oneOf()
    all {
      not(sent),
      withId or ALLOW_NO_ID,
      sent' = true, sentAt' = t, hasId' = withId,
      // :59 — голосующий пересылает лидеру. Если лидер жив — мгновенно (D1). Иначе — ждёт.
      reachedLeader' = (not(allVotersDown) and leaderUp),
      applied' = if (not(allVotersDown) and leaderUp) applied + 1 else applied,
      t' = t, leaderUp' = leaderUp, lostAt' = lostAt, doorAnswer' = doorAnswer, voterAnswered503' = voterAnswered503, allVotersDown' = allVotersDown, retries' = retries,
    }
  }
  // Ответ лидера о применении: дверь получает ответ.
  action leaderAnswer = all {
    sent, reachedLeader, leaderUp, doorAnswer == "",
    doorAnswer' = "answered",
    t' = t, leaderUp' = leaderUp, lostAt' = lostAt, sent' = sent, sentAt' = sentAt, reachedLeader' = reachedLeader, applied' = applied, hasId' = hasId, voterAnswered503' = voterAnswered503, allVotersDown' = allVotersDown, retries' = retries,
  }
  // Голосующий отвечает 503 unavailable, если лидер потерян и истёк интервал (01.3:51). Дверь передаёт это как answered.
  action voterAnswer503 = all {
    not(MUT_VOTER_NEVER_ANSWERS),
    sent, not(reachedLeader), not(leaderUp), not(allVotersDown), doorAnswer == "",
    t >= lostAt + LEADER_WAIT,
    voterAnswered503' = true, doorAnswer' = "answered",
    t' = t, leaderUp' = leaderUp, lostAt' = lostAt, sent' = sent, sentAt' = sentAt, reachedLeader' = reachedLeader, applied' = applied, hasId' = hasId, allVotersDown' = allVotersDown, retries' = retries,
  }
  // Дверь не достигла голосующих: 503 unavailable (:70, :159-160).
  action doorUnavailable = all {
    sent, allVotersDown, doorAnswer == "",
    doorAnswer' = "unavailable",
    t' = t, leaderUp' = leaderUp, lostAt' = lostAt, sent' = sent, sentAt' = sentAt, reachedLeader' = reachedLeader, applied' = applied, hasId' = hasId, voterAnswered503' = voterAnswered503, allVotersDown' = allVotersDown, retries' = retries,
  }
  // Попытка двери истекла: запись отправлена голосующему, ответа нет → ambiguous (:160). Голосующий ещё не должен отвечать:
  // D1 — при истёкшем интервале голосующий ответил бы первым.
  action doorTimeout = all {
    sent, not(allVotersDown), doorAnswer == "",
    t >= sentAt + T_ATTEMPT,
    leaderUp or t < lostAt + LEADER_WAIT or MUT_VOTER_NEVER_ANSWERS,
    doorAnswer' = "ambiguous",
    t' = t, leaderUp' = leaderUp, lostAt' = lostAt, sent' = sent, sentAt' = sentAt, reachedLeader' = reachedLeader, applied' = applied, hasId' = hasId, voterAnswered503' = voterAnswered503, allVotersDown' = allVotersDown, retries' = retries,
  }
  // Лидер вернулся (выборы) — разрешает повтор.
  // Если запрос ждал лидера и ещё не получил ответа - D1: голосующий пересылает его сразу при возврате лидера.
  action leaderBack = all {
    not(leaderUp),
    leaderUp' = true,
    val pending = sent and not(reachedLeader) and doorAnswer == "" and not(allVotersDown)
    all {
      reachedLeader' = (reachedLeader or pending),
      applied' = if (pending) applied + 1 else applied,
      t' = t, lostAt' = lostAt, sent' = sent, sentAt' = sentAt, hasId' = hasId, doorAnswer' = doorAnswer, voterAnswered503' = voterAnswered503, allVotersDown' = allVotersDown, retries' = retries,
    }
  }
  // Повтор клиента после ambiguous с тем же id: применённая запись дедуплицируется (R088); без id — новая запись.
  action clientRetry = all {
    doorAnswer == "ambiguous", leaderUp, retries < MAX_RETRIES,
    retries' = retries + 1,
    doorAnswer' = "answered",
    reachedLeader' = true,
    applied' = if (hasId and applied >= 1 and not(MUT_DOUBLE_APPLY_WITH_ID)) applied else applied + 1,
    t' = t, leaderUp' = leaderUp, lostAt' = lostAt, sent' = sent, sentAt' = sentAt, hasId' = hasId, voterAnswered503' = voterAnswered503, allVotersDown' = allVotersDown,
  }
  action stutter = all {
    t' = t, leaderUp' = leaderUp, lostAt' = lostAt, sent' = sent, sentAt' = sentAt, reachedLeader' = reachedLeader, applied' = applied, hasId' = hasId, doorAnswer' = doorAnswer, voterAnswered503' = voterAnswered503, allVotersDown' = allVotersDown, retries' = retries,
  }
  action step = any { tick, loseLeader, cutAllVoters, clientSend, leaderAnswer, voterAnswer503, doorUnavailable, doorTimeout, leaderBack, clientRetry, stutter }

  // === ИНВАРИАНТЫ ===
  // Повтор с тем же id не создаёт второго применения.
  val inv_idAtMostOne = hasId implies applied <= 1
  // Нет голосующих: 503 unavailable — определённый исход, запись не применена.
  val inv_unavailableNotApplied = doorAnswer == "unavailable" implies applied == 0
  // Отказ 503 unavailable от голосующего: запись не применена (лидеру не доставлена).
  val inv_voter503NotApplied = voterAnswered503 implies applied == 0

  // Уточнение С12: интервал leader_wait считается от потери лидера, не от запроса (01.3:51), поэтому
  // лишний ambiguous возможен только у запроса, отправленного не позже LEADER_WAIT - T_ATTEMPT после потери лидера.
  val inv_ambigWindow = (doorAnswer == "ambiguous" and not(reachedLeader)) implies (sentAt - lostAt < LEADER_WAIT - T_ATTEMPT)

  // === СВИДЕТЕЛИ ===
  // Ключевая находка С12: ambiguous на записи, которая не доставлена лидеру и не применена.
  val not_w_ambigNotForwarded = not(doorAnswer == "ambiguous" and not(reachedLeader) and applied == 0)
  val not_w_noIdDouble = not(applied >= 2)
  val not_w_allVotersDown503 = not(doorAnswer == "unavailable")
  val not_w_voter503 = not(voterAnswered503)
  val not_w_reachedAmbig = not(doorAnswer == "ambiguous" and reachedLeader)
}
