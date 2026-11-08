// P/04 — суд слота (перенос форм slot-fate/slot-release) против продления, двух судей и скачка часов пишущего (находки С9, С10 частично).
// Модель текста норм, не реализации.
//   N = Platform/04-controller/spec/04-controller.norms.md; OB = Platform/common/contracts/observation.md
//   SF = Platform/04-controller/forms/slot-fate.tsv; SR = Platform/04-controller/forms/slot-release.tsv
//   SL = Platform/common/contracts/slot.md
// Допущения: чтение одной строки слота атомарно; разрешение (names_given) и release привязаны к версии (N:1053, SF:14, SR:7);
//   age считается от первого наблюдения этим судьёй неизменной версии (N:998, OB:44, OB:52, SF:6);
//   вход судьи (ресурс/присутствие/assigned) — произвольное наблюдение (SF:5), в том числе несогласованное с действиями рабочего.
// Не моделируется: кворум чтения, запись torn как отдельная операция с telling P/03.2, abandoned capture, тело снимков, cas журнала.
module p04_slot_fate {
  import p04_forms.* from "./p04_forms"
  const ALLOW_TORN: bool
  const MUT: str     // none | nocas | noreset | agefromuntil

  pure val HUNG_MOVE_AFTER: int = 900 // env-file.md:121, daemon-flags.tsv:28
  pure val CTRL = Set("c1", "c2")
  pure val RES = Set("live", "unreachable", "silent", "unknown")
  pure val PRES = Set("runs", "gone", "unlisted", "unknown")

  var now: int
  var writerOffset: int
  var slotVer: int
  var slotReadable: bool
  var slotReleased: bool
  var untilW: int           // writer until = writer wall + SLOT_TERM (не вход судьи по форме; SF:6)
  var workerAlive: bool
  var seenVer: str -> int   // -1 нет наблюдения (перезапуск судьи)
  var firstSeen: str -> int
  var lastFate: str -> str
  var lastRow: str -> int
  var lastAge: str -> int
  var lastTrueAge: str -> int
  var lastReadable: str -> bool
  var relState: str -> str      // consider writing released refused ...
  var relCas: str -> int
  var relRow: str -> int
  var conflicted: str -> int    // версия, на которой получен conflict (ждём следующего суждения); -1 нет
  var ghostOverwrote: bool
  var ghostBadAfterConflict: bool
  var grantedAfterRelease: str -> int
  var trueAgeJudged: bool

  action init = all {
    now' = 0, writerOffset' = 0, slotVer' = 1, slotReadable' = true, slotReleased' = false, untilW' = SLOT_TERM,
    workerAlive' = true,
    seenVer' = CTRL.mapBy(c => -1), firstSeen' = CTRL.mapBy(c => 0),
    lastFate' = CTRL.mapBy(c => ""), lastRow' = CTRL.mapBy(c => 0), lastAge' = CTRL.mapBy(c => 0),
    lastTrueAge' = CTRL.mapBy(c => 0), lastReadable' = CTRL.mapBy(c => true),
    relState' = CTRL.mapBy(c => "idle"), relCas' = CTRL.mapBy(c => -1), relRow' = CTRL.mapBy(c => 0),
    conflicted' = CTRL.mapBy(c => -1), ghostOverwrote' = false, ghostBadAfterConflict' = false,
    grantedAfterRelease' = CTRL.mapBy(c => NOVER), trueAgeJudged' = false,
  }

  action unchangedWorld = all {
    writerOffset' = writerOffset, slotVer' = slotVer, slotReadable' = slotReadable, slotReleased' = slotReleased,
    untilW' = untilW, workerAlive' = workerAlive,
  }
  action unchangedJudge = all {
    seenVer' = seenVer, firstSeen' = firstSeen, lastFate' = lastFate, lastRow' = lastRow, lastAge' = lastAge,
    lastTrueAge' = lastTrueAge, lastReadable' = lastReadable, relState' = relState, relCas' = relCas, relRow' = relRow,
    conflicted' = conflicted, ghostOverwrote' = ghostOverwrote, ghostBadAfterConflict' = ghostBadAfterConflict,
    grantedAfterRelease' = grantedAfterRelease, trueAgeJudged' = trueAgeJudged,
  }

  action tick = {
    nondet dt = oneOf(Set(1, 5, 45, 50, 90, 900))
    all { now < 2000, now' = now + dt, unchangedWorld, unchangedJudge }
  }

  action writerJump = {
    nondet d = oneOf(Set(-900, -30, 300, 900))
    all { writerOffset' = writerOffset + d, now' = now,
          slotVer' = slotVer, slotReadable' = slotReadable, slotReleased' = slotReleased, untilW' = untilW, workerAlive' = workerAlive, unchangedJudge }
  }

  // Продление (слот записан заново живым рабочим): новая версия; writer until по стенным часам пишущего.
  action renew = all {
    workerAlive, not(slotReleased),
    slotVer' = slotVer + 1,
    untilW' = now + writerOffset + SLOT_TERM,
    now' = now, writerOffset' = writerOffset, slotReadable' = slotReadable, slotReleased' = slotReleased, workerAlive' = workerAlive,
    unchangedJudge,
  }

  action workerDie = all {
    workerAlive,
    workerAlive' = false,
    now' = now, writerOffset' = writerOffset, slotVer' = slotVer, slotReadable' = slotReadable, slotReleased' = slotReleased, untilW' = untilW,
    unchangedJudge,
  }

  // Запись torn (строка не читается), новая версия (SL:38). Только в конфигурации ALLOW_TORN (строку может оставить сторонний писатель).
  action tear = all {
    ALLOW_TORN, not(slotReleased), slotReadable,
    slotVer' = slotVer + 1,
    slotReadable' = false,
    now' = now, writerOffset' = writerOffset, slotReleased' = slotReleased, untilW' = untilW, workerAlive' = workerAlive,
    unchangedJudge,
  }

  action restartJudge(c: str): bool = all {
    seenVer' = seenVer.set(c, -1),
    now' = now, firstSeen' = firstSeen, lastFate' = lastFate, lastRow' = lastRow, lastAge' = lastAge, lastTrueAge' = lastTrueAge, lastReadable' = lastReadable,
    relState' = relState, relCas' = relCas, relRow' = relRow, conflicted' = conflicted, ghostOverwrote' = ghostOverwrote, ghostBadAfterConflict' = ghostBadAfterConflict,
    grantedAfterRelease' = grantedAfterRelease, trueAgeJudged' = trueAgeJudged, unchangedWorld,
  }

  // Суд: age — от первого наблюдения этой версии этим судьёй; новая версия — age 0 (OB:52, N:998).
  action judge(c: str): bool = {
    nondet res = oneOf(RES)
    nondet pres = oneOf(PRES)
    nondet assigned = oneOf(Set(true, false))
    nondet workerFresh = oneOf(Set(true, false))
    nondet serverKnown = oneOf(Set(true, false))
    val same = (seenVer.get(c) == slotVer)
    val first = if (same) firstSeen.get(c) else now
    val trueAge = now - first
    // MUT=noreset: age не сбрасывается новой версией (нарушение OB:52)
    val age0 = if (MUT == "noreset" and seenVer.get(c) >= 0) now - firstSeen.get(c) else trueAge
    // MUT=agefromuntil: возраст по until пишущего, а не по наблюдению (нарушение SF:6, N:998, N:1053)
    val age = if (MUT == "agefromuntil") (if (untilW - SLOT_TERM >= now) 0 else now - (untilW - SLOT_TERM)) else age0
    val r = slotFate(age, slotReadable, workerFresh, res, pres, assigned, serverKnown, true, slotVer, HUNG_MOVE_AFTER)
    val fate = r._1
    all {
      not(slotReleased),
      relState.get(c) == "idle" or relState.get(c) == "released" or relState.get(c) == "refused",
      seenVer' = seenVer.set(c, slotVer),
      firstSeen' = if (same) firstSeen else firstSeen.set(c, now),
      lastFate' = lastFate.set(c, fate),
      lastRow' = lastRow.set(c, r._3),
      lastAge' = lastAge.set(c, age),
      lastTrueAge' = lastTrueAge.set(c, trueAge),
      lastReadable' = lastReadable.set(c, slotReadable),
      relState' = if (fate == "release") relState.set(c, "writing") else relState,
      relCas' = if (fate == "release") relCas.set(c, slotVer) else relCas,
      relRow' = if (fate == "release") relRow.set(c, 1) else relRow,
      // Что должно быть видно после конфликта по продлению: следующая судьба читаемого слота — alive.
      ghostBadAfterConflict' = (ghostBadAfterConflict or (conflicted.get(c) >= 0 and conflicted.get(c) != slotVer and slotReadable and not(same) and fate != "alive")),
      conflicted' = if (fate != "release") conflicted.set(c, -1) else conflicted,
      trueAgeJudged' = (trueAgeJudged or (slotReadable and trueAge < SLOT_TERM and fate != "alive")),
      now' = now, ghostOverwrote' = ghostOverwrote, grantedAfterRelease' = grantedAfterRelease, unchangedWorld,
    }
  }

  // Доставка CAS release: по форме slot-release, её строки 2-5.
  action deliverRelease(c: str): bool = {
    val v = relCas.get(c)
    val casOk = (MUT == "nocas") or (v == slotVer)
    val reply = if (casOk) "ok" else "conflict"
    val r = slotReleaseStep("writing", "release", true, 0, HUNG_MOVE_AFTER, v, slotVer + 1, reply)
    all {
      relState.get(c) == "writing",
      relCas.get(c) >= 0,
      relState' = relState.set(c, r._1),
      relCas' = relCas.set(c, -1),
      relRow' = relRow.set(c, r._4),
      conflicted' = if (reply == "conflict") conflicted.set(c, v) else conflicted,
      grantedAfterRelease' = if (r._2 == "release") grantedAfterRelease.set(c, r._3) else grantedAfterRelease,
      if (r._1 == "released") all {
        slotReleased' = true, slotVer' = slotVer + 1,
        ghostOverwrote' = (ghostOverwrote or (v != slotVer)),
      } else all {
        slotReleased' = slotReleased, slotVer' = slotVer, ghostOverwrote' = ghostOverwrote,
      },
      now' = now, writerOffset' = writerOffset, slotReadable' = slotReadable, untilW' = untilW, workerAlive' = workerAlive,
      seenVer' = seenVer, firstSeen' = firstSeen, lastFate' = lastFate, lastRow' = lastRow, lastAge' = lastAge, lastTrueAge' = lastTrueAge, lastReadable' = lastReadable,
      ghostBadAfterConflict' = ghostBadAfterConflict, trueAgeJudged' = trueAgeJudged,
    }
  }

  action step = any {
    tick, writerJump, renew, workerDie, tear,
    { nondet c = oneOf(CTRL) any { restartJudge(c), judge(c), deliverRelease(c) } },
  }

  // Инварианты
  val invNoReleaseOverwrite = not(ghostOverwrote)
  val invConflictThenAlive = not(ghostBadAfterConflict)
  val invTrueAgeBelowTermAlive = not(trueAgeJudged)
  // Свежий судья не двигает в первый LOST_AFTER (N:323, L:87) — ограничено строкой ниже, читаемые и torn
  val invFreshMovesNothing = CTRL.forall(c => lastRow.get(c) == 0 or lastTrueAge.get(c) >= LOST_AFTER or
    not(Set("release", "move", "hung_moved", "unsure_moved").contains(lastFate.get(c))))
  val invRow1NonVacuous = true

  // Свидетели: строки формы (ожидается нарушение: строка достижима)
  val witR1 = lastRow.get("c1") != 1
  val witR2 = lastRow.get("c1") != 2
  val witR3 = lastRow.get("c1") != 3
  val witR4 = lastRow.get("c1") != 4
  val witR5 = lastRow.get("c1") != 5
  val witR6 = lastRow.get("c1") != 6
  val witR7 = lastRow.get("c1") != 7
  val witR8 = lastRow.get("c1") != 8
  val witR9 = lastRow.get("c1") != 9
  val witR10 = lastRow.get("c1") != 10
  val witR11 = lastRow.get("c1") != 11
  val witR12 = lastRow.get("c1") != 12
  val witR13 = lastRow.get("c1") != 13
  val witR14 = lastRow.get("c1") != 14
  val witR15 = lastRow.get("c1") != 15
  val witR16 = lastRow.get("c1") != 16
  val witRel2 = relRow.get("c1") != 2
  val witRel5 = relRow.get("c1") != 5
  val witConflict = conflicted.get("c1") < 0
  val witReleased = not(slotReleased)
  val witGrantAfterRelease = grantedAfterRelease.get("c1") == NOVER and grantedAfterRelease.get("c2") == NOVER
  val witTornMoveAtZero = not(lastRow.get("c1") > 0 and lastTrueAge.get("c1") == 0 and not(lastReadable.get("c1")) and Set("release", "move").contains(lastFate.get("c1")))
}

module fate_base { import p04_slot_fate(ALLOW_TORN=true, MUT="none").* }
module fate_notorn { import p04_slot_fate(ALLOW_TORN=false, MUT="none").* }
module fate_nocas { import p04_slot_fate(ALLOW_TORN=false, MUT="nocas").* }
module fate_noreset { import p04_slot_fate(ALLOW_TORN=false, MUT="noreset").* }
module fate_until { import p04_slot_fate(ALLOW_TORN=false, MUT="agefromuntil").* }
