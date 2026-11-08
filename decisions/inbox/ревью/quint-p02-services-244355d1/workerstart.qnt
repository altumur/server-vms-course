// -*- mode: Bluespec; -*-
// P/02 службы и запуск, срез 244355d161139bd6fe65fd68c7e5134598c21ba3.
// Цепочка старта Type=notify воркера против срока старта службы (находки С1, С2, часть С3).
//
// Время — целые секунды; один шаг модели — одно ожидание целиком (нормы задают лишь
// сумму паузы и попыток, а не их число), поэтому шагов мало, а срок считается точно.
//
// Нормы (якоря сверяет anchors.py): START_WAIT 60 (02.3:213); пауза повтора 1 с (02.3:212,
// не моделируется отдельно — входит в длительность ожидания); раннер читает строку
// в пределах START_WAIT (02.3:228-229); первое действие программы — проверка схемы,
// тоже в пределах START_WAIT «после старта процесса» (02.3:207, 02.3:213); flock без срока
// (03.2:536-537, pres:32-33); READY=1 только после захвата имени (02.4:116); ветка nobody
// без готовности (03.2:555); Restart=always, RestartPreventExitStatus=2, RestartSec=2
// (02.4:48-49); Type=notify, NotifyAccess=main (02.4:87).
//
// Допущения о systemd — не нормы курса, сверены только по man systemd 252 на CT 103:
//  - TimeoutStartSec не задан ни одной строкой N1.1, у Type=notify берётся
//    DefaultTimeoutStartSec manager'а (systemd-system.conf(5)); здесь это параметр TS;
//  - срок старта истёк — служба завершается и перезапускается (Restart=always покрывает
//    таймауты, systemd.service(5) Restart=);
//  - READY=1 не приходит вне NotifyAccess=main — модель всегда от главного процесса.
// Что НЕ моделируется: watchdog (активен только после старта), нормы P/03 о capture по
// содержанию, Exit-ветки кода 0 (метка/rev), MEMORY, работа после READY; StartLimit
// (снят в разборе); launchd/macOS; журналирование.
module workerstart {
  // ----- константы -----
  // START_WAIT = 60; 02.3:213
  const START_WAIT: int
  // RestartSec = 2; 02.4:49
  const RESTART_SEC: int
  // Срок старта службы (TimeoutStartSec manager'а). TS_INF — без срока.
  const TS: int
  const TS_INF: int
  // Чей START_WAIT: "exec" — у программы свой отсчёт от exec; "unit" — общий от старта юнита.
  // Норма: «START_WAIT … after the start of the process» (02.3:213), чей старт не сказано (С1/С3).
  const PROG_BASE: str
  // Насколько последнее чтение может уйти за START_WAIT: срок одного чтения — решение клиента
  // (sc:89); 0 — реализация ограничивает чтение остатком START_WAIT.
  const READ_OVER: int
  // Предел ожидания flock в секундах; нормой не задан (pres:32).
  const FLOCK_MAX: int
  // Ветка nobody достижима (03.2:555).
  const ALLOW_NOBODY: bool
  // Вариант лечения: READY=1 при входе в цикл nobody (не норма).
  const READY_AT_NOBODY: bool
  // Граница модели: число запусков юнита.
  const MAXSTARTS: int
  // Мутанты: 0 — нет.
  const MUT: int

  // Порог-зонд времени в activating (не норма; проверяет лишь, что activating ограничен).
  const ACT_BOUND: int

  // ----- состояние -----
  // Runner | Prog | Flock | Capture | Nobody | Ready | NobodyActive | Exit1 | Exit2 | Killed
  var phase: str
  var now: int
  var unitStart: int
  var progStart: int
  var starts: int
  var kills: int
  var killsInNobody: int
  var nameObtained: bool
  // Запуски после Exit2 — для мутанта.
  var startsAfterExit2: int

  // ----- вспомогательные -----
  pure def imax(a: int, b: int): int = if (a > b) a else b
  pure def isActivating(p: str): bool =
    Set("Runner", "Prog", "Flock", "Capture", "Nobody").contains(p)

  // При READY_AT_NOBODY цикл nobody не считается активацией.
  def killBase: bool = TS < TS_INF

  // Совершить переход со временем d: если срок старта успевает истечь — Killed.
  // При истечении время ставится ровно на дедлайн (исполнение прерывается), ничьи — в пользу Killed.
  action go(d: int, np: str, newProg: int, nameNew: bool): bool = {
    val nextT = now + d
    if (isActivating(phase) and killBase and nextT >= unitStart + TS)
      all {
        now' = unitStart + TS,
        phase' = "Killed",
        kills' = kills + 1,
        killsInNobody' = if (phase == "Nobody") killsInNobody + 1 else killsInNobody,
        progStart' = progStart,
        nameObtained' = nameObtained,
        unitStart' = unitStart,
        starts' = starts,
        startsAfterExit2' = startsAfterExit2,
      }
    else
      all {
        now' = nextT,
        phase' = np,
        progStart' = newProg,
        nameObtained' = nameNew,
        unitStart' = unitStart,
        kills' = kills,
        killsInNobody' = killsInNobody,
        starts' = starts,
        startsAfterExit2' = startsAfterExit2,
      }
  }

  // Длительность сверх остатка окна: только последнее чтение; мутант 2 снимает предел.
  // Раннер: строка и метка в пределах START_WAIT от старта процесса-раннера (02.3:228-229).
  action runnerStep = all {
    phase == "Runner",
    nondet outcome = Set("ok", "refused", "unconfirmed").oneOf()
    val deadline = unitStart + START_WAIT
    nondet d = 0.to(imax(0, deadline - now) + READ_OVER).oneOf()
    if (outcome == "ok")
      // Подтверждённое чтение: не позднее срока.
      all { now + d <= deadline, go(d, "Prog", if (PROG_BASE == "exec") now + d else unitStart, nameObtained) }
    else if (outcome == "refused")
      all { now + d <= deadline, go(d, "Exit2", progStart, nameObtained) }
    else
      // Не подтверждено к сроку: код 1 (02.3:213).
      all { now + d >= deadline, go(d, "Exit1", progStart, nameObtained) },
  }

  // Программа: схема и строка в пределах START_WAIT от своего старта (02.3:207, 02.3:213).
  action progStep = all {
    phase == "Prog",
    nondet outcome = Set("ok", "refused", "unconfirmed").oneOf()
    val deadline = progStart + START_WAIT
    val over = if (MUT == 2) 300 else READ_OVER
    nondet d = 0.to(imax(0, deadline - now) + over).oneOf()
    if (outcome == "ok")
      all { now + d <= deadline, go(d, "Flock", progStart, nameObtained) }
    else if (outcome == "refused")
      all { now + d <= deadline, go(d, "Exit2", progStart, nameObtained) }
    else
      all { now + d >= deadline, go(d, "Exit1", progStart, nameObtained) },
  }

  // Блокирующий flock без срока (pres:32-33), затем захват имени.
  action flockStep = all {
    phase == "Flock",
    nondet d = Set(0, FLOCK_MAX).oneOf()
    go(d, "Capture", progStart, nameObtained),
  }

  action captureStep = all {
    phase == "Capture",
    nondet got = Bool.oneOf()
    all {
      got or ALLOW_NOBODY,
      if (got) go(0, "Ready", progStart, true)
      else if (READY_AT_NOBODY) go(0, "NobodyActive", progStart, nameObtained)
      else go(0, "Nobody", progStart, nameObtained),
    }
  }

  // Мутант 1: READY приходит раньше захвата, сразу после exec.
  action earlyReady = all {
    MUT == 1,
    phase == "Flock",
    go(0, "Ready", progStart, false),
  }

  // Цикл nobody ждёт имя (seek_name, 03.2:668-678): имя может и не прийти.
  action nobodyStep = all {
    phase == "Nobody" or phase == "NobodyActive",
    nondet d = 0.to(300).oneOf()
    nondet got = Bool.oneOf()
    if (phase == "Nobody")
      (if (got) go(d, "Ready", progStart, true) else go(d, "Nobody", progStart, nameObtained))
    else
      (if (got) go(d, "Ready", progStart, true) else go(d, "NobodyActive", progStart, nameObtained)),
  }

  // Перезапуск: exit 1 и таймаут — да (Restart=always), exit 2 — нет (02.4:48-49).
  action restartStep = all {
    Set("Exit1", "Killed").contains(phase) or (MUT == 3 and phase == "Exit2"),
    starts < MAXSTARTS,
    now' = now + RESTART_SEC,
    phase' = "Runner",
    unitStart' = now + RESTART_SEC,
    progStart' = now + RESTART_SEC,
    starts' = starts + 1,
    kills' = kills,
    killsInNobody' = killsInNobody,
    nameObtained' = false,
    startsAfterExit2' = if (phase == "Exit2") startsAfterExit2 + 1 else startsAfterExit2,
  }

  action stutter = all {
    Set("Ready", "Exit2", "NobodyActive", "Killed", "Exit1").contains(phase),
    now' = now, phase' = phase, unitStart' = unitStart, progStart' = progStart,
    starts' = starts, kills' = kills, killsInNobody' = killsInNobody,
    nameObtained' = nameObtained, startsAfterExit2' = startsAfterExit2,
  }

  action init = all {
    phase' = "Runner", now' = 0, unitStart' = 0, progStart' = 0,
    starts' = 1, kills' = 0, killsInNobody' = 0, nameObtained' = false,
    startsAfterExit2' = 0,
  }

  action step = any { runnerStep, progStep, flockStep, captureStep, earlyReady, nobodyStep, restartStep, stutter }

  // ----- инварианты -----
  // С1: норма обещает исход кода 1/2 — служба не должна быть убита сроком старта раньше него.
  val inv_noKill = kills == 0
  // С2: законный nobody не убивается сроком старта.
  val inv_nobodyNotKilled = killsInNobody == 0
  // Исход Exit1 по окну не позже START_WAIT+READ_OVER от своей базы (база раннера/программы).
  val inv_exit1Deadline = phase != "Exit1" or now <= imax(unitStart, progStart) + START_WAIT + READ_OVER
  // READY только после захвата имени (02.4:116), кроме варианта-лечения (своё состояние NobodyActive).
  val inv_readyAfterCapture = phase != "Ready" or nameObtained
  // После exit 2 нет перезапуска (02.4:48-49, 02.3:233-234).
  val inv_noRestartAfter2 = startsAfterExit2 == 0
  // Без срока старта (TS=∞) конечность чтений всё равно не следует: «висит в activating».
  val inv_activatingBound = not(isActivating(phase)) or (now - unitStart) <= ACT_BOUND

  // Свидетели (ожидаются нарушенными на родной модели).
  val notReady = phase != "Ready"
  val notNobody = phase != "Nobody"
  val notExit1 = phase != "Exit1"
  val notExit2 = phase != "Exit2"
  val killsLT2 = kills < 2
  val inv_sanity = now >= 0
}

// Именованные конфигурации. Значения времени только из норм; значения вроде READ_OVER — не норма,
// а зонды вокруг START_WAIT и срока службы.
module ws_a  { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=90,TS_INF=100000,PROG_BASE="exec",READ_OVER=0,FLOCK_MAX=0,ALLOW_NOBODY=false,READY_AT_NOBODY=false,MAXSTARTS=1,MUT=0,ACT_BOUND=500).* }
module ws_b  { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=90,TS_INF=100000,PROG_BASE="unit",READ_OVER=0,FLOCK_MAX=0,ALLOW_NOBODY=false,READY_AT_NOBODY=false,MAXSTARTS=1,MUT=0,ACT_BOUND=500).* }
module ws_c  { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=90,TS_INF=100000,PROG_BASE="unit",READ_OVER=30,FLOCK_MAX=0,ALLOW_NOBODY=false,READY_AT_NOBODY=false,MAXSTARTS=1,MUT=0,ACT_BOUND=500).* }
module ws_c0 { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=90,TS_INF=100000,PROG_BASE="unit",READ_OVER=29,FLOCK_MAX=0,ALLOW_NOBODY=false,READY_AT_NOBODY=false,MAXSTARTS=1,MUT=0,ACT_BOUND=500).* }
module ws_d  { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=90,TS_INF=100000,PROG_BASE="unit",READ_OVER=0,FLOCK_MAX=100000,ALLOW_NOBODY=false,READY_AT_NOBODY=false,MAXSTARTS=1,MUT=0,ACT_BOUND=500).* }
module ws_e  { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=120,TS_INF=100000,PROG_BASE="exec",READ_OVER=0,FLOCK_MAX=0,ALLOW_NOBODY=false,READY_AT_NOBODY=false,MAXSTARTS=1,MUT=0,ACT_BOUND=500).* }
module ws_f  { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=121,TS_INF=100000,PROG_BASE="exec",READ_OVER=0,FLOCK_MAX=0,ALLOW_NOBODY=false,READY_AT_NOBODY=false,MAXSTARTS=1,MUT=0,ACT_BOUND=500).* }
module ws_g  { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=100000,TS_INF=100000,PROG_BASE="unit",READ_OVER=0,FLOCK_MAX=0,ALLOW_NOBODY=false,READY_AT_NOBODY=false,MAXSTARTS=1,MUT=0,ACT_BOUND=500).* }
module ws_n  { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=90,TS_INF=100000,PROG_BASE="unit",READ_OVER=0,FLOCK_MAX=0,ALLOW_NOBODY=true,READY_AT_NOBODY=false,MAXSTARTS=2,MUT=0,ACT_BOUND=500).* }
module ws_nr { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=90,TS_INF=100000,PROG_BASE="unit",READ_OVER=0,FLOCK_MAX=0,ALLOW_NOBODY=true,READY_AT_NOBODY=true,MAXSTARTS=2,MUT=0,ACT_BOUND=500).* }
module ws_ni { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=100000,TS_INF=100000,PROG_BASE="unit",READ_OVER=0,FLOCK_MAX=0,ALLOW_NOBODY=true,READY_AT_NOBODY=false,MAXSTARTS=2,MUT=0,ACT_BOUND=500).* }
module ws_h  { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=100000,TS_INF=100000,PROG_BASE="unit",READ_OVER=0,FLOCK_MAX=100000,ALLOW_NOBODY=false,READY_AT_NOBODY=false,MAXSTARTS=1,MUT=0,ACT_BOUND=500).* }
module ws_hb { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=100000,TS_INF=100000,PROG_BASE="unit",READ_OVER=0,FLOCK_MAX=60,ALLOW_NOBODY=false,READY_AT_NOBODY=false,MAXSTARTS=1,MUT=0,ACT_BOUND=500).* }
module ws_m1 { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=90,TS_INF=100000,PROG_BASE="unit",READ_OVER=0,FLOCK_MAX=0,ALLOW_NOBODY=true,READY_AT_NOBODY=false,MAXSTARTS=1,MUT=1,ACT_BOUND=500).* }
module ws_m2 { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=90,TS_INF=100000,PROG_BASE="unit",READ_OVER=0,FLOCK_MAX=0,ALLOW_NOBODY=false,READY_AT_NOBODY=false,MAXSTARTS=1,MUT=2,ACT_BOUND=500).* }
module ws_m3 { import workerstart(START_WAIT=60,RESTART_SEC=2,TS=90,TS_INF=100000,PROG_BASE="unit",READ_OVER=0,FLOCK_MAX=0,ALLOW_NOBODY=false,READY_AT_NOBODY=false,MAXSTARTS=2,MUT=3,ACT_BOUND=500).* }
