// -*- mode: Bluespec; -*-
// P/02 службы и запуск, срез 244355d161139bd6fe65fd68c7e5134598c21ba3.
// Шаги install и rollout вне машины опроса (находка С6) и прерывание/повтор.
//
// Нормы: ROLLOUT_WAIT = 300, опрос раз в 1 с (02.4:558); барьер читает GET /v1/rights, /manifest/<sub>/source
// (02.4:543-549) — срока одного чтения нет; failure «любой шаг — ненулевой код с именем шага, без отката,
// повтор той же командой безвреден» (02.4:561); install W2C_HOLD — имена без включённых юнитов, в том числе
// на повторе (02.4:533-534); rollout не включает юниты подсистем (02.4:563); install ждёт GET /v1/status
// (02.4:395, 02.4:396) без срока.
//
// Что НЕ моделируется: содержание шагов, состав файлов, порядок серверов, сами barriers кроме формы;
// барьер считается по событию «прошло», без различения частей; machine poll — отдельный модуль.
// Сроки шагов и чтений — параметры (STEP_MAX, BARRIER_READ), нормой не заданы.
module rolloutsteps {
  pure val ROLLOUT_WAIT = 300  // 02.4:560
  const BARRIER_READ: int      // срок одного чтения барьера; нормы нет
  const BARRIER_BOUND_READ: bool // вариант: чтение обрезается остатком ROLLOUT_WAIT (не норма)
  const STEP_MAX: int          // срок шага; нормы нет
  const MUT: int
  const MAX_ATTEMPTS: int

  // Попытка: 0 — не шла; Get | Hold | Rights | Console | Barrier | Done
  var stage: str
  var now: int
  var barrierStart: int
  var attempt: int
  var newSubInstalled: bool
  var newSubEnabled: bool
  var repeated: bool
  var rolloutDone: bool
  var barrierOvershoot: int
  // Контроль: барьер пройден именно в этой попытке.
  var barrierThisAttempt: bool

  action init = all {
    stage' = "Get", now' = 0, barrierStart' = 0, attempt' = 1, newSubInstalled' = false,
    newSubEnabled' = false, repeated' = false, rolloutDone' = false, barrierOvershoot' = 0,
    barrierThisAttempt' = false,
  }

  pure def stepNext(s: str): str =
    if (s == "Get") "Hold" else if (s == "Hold") "Rights" else if (s == "Rights") "Console" else "Barrier"

  // Шаг: ok — следующий; fail — прерывание с кодом, повтор той же командой возможен.
  action doStep = all {
    Set("Get", "Hold", "Rights", "Console").contains(stage),
    nondet d = Set(0, STEP_MAX).oneOf()
    nondet ok = Bool.oneOf()
    all {
      now' = now + d,
      stage' = if (ok) stepNext(stage) else "Failed",
      barrierStart' = if (ok and stepNext(stage) == "Barrier") now + d else barrierStart,
      // Hold-шаг: install с W2C_HOLD — имена новых подсистем, чьи юниты не включены (02.4:533-534).
      newSubInstalled' = if (ok and stage == "Hold") true else newSubInstalled,
      // MUT 1: на повторе не держать те, что уже установлены (ошибочная логика первой установки): включит.
      newSubEnabled' = (newSubEnabled or (MUT == 1 and ok and stage == "Hold" and repeated and newSubInstalled)),
      attempt' = attempt, repeated' = repeated, rolloutDone' = rolloutDone,
      barrierOvershoot' = barrierOvershoot, barrierThisAttempt' = barrierThisAttempt,
    },
  }

  // Опрос барьера: одно чтение (BARRIER_READ) — затем проверка срока.
  action pollBarrier = all {
    stage == "Barrier",
    nondet dIdx = Set(0, 1).oneOf()
    val remain = barrierStart + ROLLOUT_WAIT - now
    val d = if (BARRIER_BOUND_READ and BARRIER_READ > remain and remain >= 0) (if (dIdx == 0) 0 else remain) else (if (dIdx == 0) 0 else BARRIER_READ)
    nondet passed = Bool.oneOf()
    all {
      now' = now + d,
      // Срок проверяется после чтения (02.4:558 — «polling once per 1 s»); вне нормы — превышение.
      if (passed and now + d <= barrierStart + ROLLOUT_WAIT) all {
        stage' = "Done", rolloutDone' = true, barrierThisAttempt' = true, barrierOvershoot' = barrierOvershoot,
      } else if (now + d >= barrierStart + ROLLOUT_WAIT) all {
        stage' = "Failed", rolloutDone' = rolloutDone, barrierThisAttempt' = barrierThisAttempt,
        barrierOvershoot' = if (now + d > barrierStart + ROLLOUT_WAIT) now + d - (barrierStart + ROLLOUT_WAIT) else barrierOvershoot,
      } else all {
        stage' = "Barrier", rolloutDone' = rolloutDone, barrierThisAttempt' = barrierThisAttempt, barrierOvershoot' = barrierOvershoot,
      },
      barrierStart' = barrierStart, attempt' = attempt, newSubInstalled' = newSubInstalled,
      newSubEnabled' = newSubEnabled, repeated' = repeated,
    },
  }

  // Повтор той же командой после неуспеха шага; MUT 2 — повтор не сбрасывает «барьер пройден».
  action repeatCmd = all {
    stage == "Failed", attempt < MAX_ATTEMPTS,
    stage' = "Get", attempt' = attempt + 1, repeated' = true,
    now' = now, barrierStart' = barrierStart, newSubInstalled' = newSubInstalled, newSubEnabled' = newSubEnabled,
    rolloutDone' = rolloutDone, barrierOvershoot' = barrierOvershoot,
    barrierThisAttempt' = if (MUT == 2) barrierThisAttempt else false,
  }

  // Мутант 2: Done без барьера при повторе (неверный «уже проходили»).
  action finishByOld = all {
    MUT == 2, stage == "Get", repeated,
    stage' = "Done", rolloutDone' = true, now' = now, barrierStart' = barrierStart,
    attempt' = attempt, repeated' = repeated, newSubInstalled' = newSubInstalled, newSubEnabled' = newSubEnabled,
    barrierOvershoot' = barrierOvershoot, barrierThisAttempt' = barrierThisAttempt,
  }

  action stutter = all {
    stage == "Done" or (stage == "Failed" and attempt >= MAX_ATTEMPTS),
    stage' = stage, now' = now, barrierStart' = barrierStart, attempt' = attempt,
    newSubInstalled' = newSubInstalled, newSubEnabled' = newSubEnabled, repeated' = repeated,
    rolloutDone' = rolloutDone, barrierOvershoot' = barrierOvershoot, barrierThisAttempt' = barrierThisAttempt,
  }

  action step = any { doStep, pollBarrier, repeatCmd, finishByOld, stutter }

  // Барьер не ждёт дольше ROLLOUT_WAIT (02.4:558).
  val inv_barrierWithinWait = barrierOvershoot == 0
  // Запрет: rollout не включает юниты подсистем (02.4:563) и на повторе (02.4:533-534).
  val inv_noEnableBeforeEnd = not(newSubEnabled) or stage == "Done"
  // Завершение только при пройденном барьере текущей попытки (02.4:561).
  val inv_doneAfterBarrier = stage != "Done" or barrierThisAttempt
  // Свидетели
  val notDone = stage != "Done"
  val notRepeated = not(repeated)
  val notBarrierPhase = stage != "Barrier"
  val notFailed = stage != "Failed"
}

module rs_a   { import rolloutsteps(BARRIER_READ=1,BARRIER_BOUND_READ=false,STEP_MAX=0,MUT=0,MAX_ATTEMPTS=3).* }
module rs_read { import rolloutsteps(BARRIER_READ=100000,BARRIER_BOUND_READ=false,STEP_MAX=0,MUT=0,MAX_ATTEMPTS=2).* }
module rs_bound { import rolloutsteps(BARRIER_READ=100000,BARRIER_BOUND_READ=true,STEP_MAX=0,MUT=0,MAX_ATTEMPTS=2).* }
module rs_m1  { import rolloutsteps(BARRIER_READ=1,BARRIER_BOUND_READ=false,STEP_MAX=0,MUT=1,MAX_ATTEMPTS=3).* }
module rs_m2  { import rolloutsteps(BARRIER_READ=1,BARRIER_BOUND_READ=false,STEP_MAX=0,MUT=2,MAX_ATTEMPTS=3).* }
