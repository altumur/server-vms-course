// -*- mode: Bluespec; -*-
// P/02 службы и запуск, срез 244355d161139bd6fe65fd68c7e5134598c21ba3.
// w2c-workers.service/.timer: сроки прохода, чтение /metrics и последовательность
// проходов (находка С4, правила 1, 3, 5 N1.5).
//
// Нормы: oneshot + timer (02.4:102-105); правило 1 — чтение /metrics (02.4:217); правило 2 —
// молчание консоли >1 мин (02.4:224) и возраст серии >60 (02.4:225); правило 3 — старт
// наименьших, стоп наибольших (02.4:227); правило 5 — сериализация проходов и «uncertain» (02.4:236);
// stop — systemctl stop (02.4:239); stop_timeout 20..50 (02.4:87-88).
//
// Допущения (man systemd 252, не нормы):
//  - один oneshot-юнит не запускается параллельно, таймер не создаёт второй запуск пока
//    активен (systemd.timer: OnUnitActiveSec от «last activated»; см. допущения в отчёте);
//  - systemctl start/stop без --no-block ждёт завершения задания (не сказано нормой, флаг BLOCK).
// Что НЕ моделируется: сам разбор /metrics (форма — векторы), polkit, потолок памяти правила 4,
// macOS/launchd, ручной запуск (кроме мутанта), зависшее чтение как отдельный вид (просто READ_MAX).
module workertimer {
  const TIMER_PERIOD: int   // OnUnitActiveSec 60 (02.4:105)
  const BOOT: int           // OnBootSec 1–2 мин (02.4:104), начальный срок = 60..120
  const FRESH: int          // 60: «older than a minute» (02.4:224)
  const READ_MAX: int       // срок чтения /metrics; нормой не задан (С4) — параметр
  const STOP_MAX: int       // stop_timeout (02.4:87-88)
  const START_MAX: int      // срок systemctl start (start ждёт READY/таймаута) — параметр
  const BLOCK: bool         // systemctl ждёт задание (default)
  const NUMS: List[int]     // номера по порядку возрастания (сужение 2..99)
  const NUMS_DESC: List[int]
  const RECHECK: bool       // вариант: перепроверка возраста перед каждым действием (не норма)
  const PASS_BOUND: int     // порог длительности прохода (период таймера)
  const MAX_PASSES: int     // граница модели
  const MUT: int

  type Op = { kind: str, n: int }
  // Idle | Read | Act
  var phase: str
  var now: int
  var nextFire: int
  var passStart: int
  var collectedAt: int
  var running: Set[int]
  var uncertain: Set[int]
  var plan: List[Op]
  var passes: int
  var runningPasses: int
  var opsStale: bool
  var startsWhileUncertain: int
  var passCompleted: int

  pure def startsPlan(want: int, nums: List[int], rr: Set[int], unc: Set[int], ignoreUnc: bool): List[Op] =
    nums.select(n => n <= want and not(rr.contains(n)) and (ignoreUnc or not(unc.contains(n))))
        .foldl(List(), (acc, n) => acc.append({ kind: "start", n: n }))
  pure def stopsPlan(want: int, numsDesc: List[int], rr: Set[int]): List[Op] =
    numsDesc.select(n => n > want and rr.contains(n))
        .foldl(List(), (acc, n) => acc.append({ kind: "stop", n: n }))

  action unchangedAll = all {
    phase' = phase, now' = now, nextFire' = nextFire, passStart' = passStart,
    collectedAt' = collectedAt, running' = running, uncertain' = uncertain, plan' = plan,
    passes' = passes, runningPasses' = runningPasses, opsStale' = opsStale,
    startsWhileUncertain' = startsWhileUncertain, passCompleted' = passCompleted,
  }

  action init = all {
    phase' = "Idle", now' = 0, nextFire' = BOOT, passStart' = 0, collectedAt' = 0,
    running' = Set(), uncertain' = Set(), plan' = List(), passes' = 0, runningPasses' = 0,
    opsStale' = false, startsWhileUncertain' = 0, passCompleted' = 0,
  }

  // Ожидание до срока таймера (время только вперёд до точки срабатывания).
  action advance = all {
    phase == "Idle", now < nextFire,
    now' = nextFire,
    phase' = phase, nextFire' = nextFire, passStart' = passStart, collectedAt' = collectedAt,
    running' = running, uncertain' = uncertain, plan' = plan, passes' = passes,
    runningPasses' = runningPasses, opsStale' = opsStale,
    startsWhileUncertain' = startsWhileUncertain, passCompleted' = passCompleted,
  }

  // Срабатывание: новая активация (OnUnitActiveSec считается от неё). Мутант 2 — параллельный проход.
  action fire = all {
    passes < MAX_PASSES,
    now >= nextFire,
    phase == "Idle" or MUT == 2,
    phase' = if (phase == "Idle") "Read" else phase,
    now' = now, nextFire' = now + TIMER_PERIOD, passStart' = now, collectedAt' = collectedAt,
    running' = running, uncertain' = uncertain, plan' = plan, passes' = passes + 1,
    runningPasses' = runningPasses + 1, opsStale' = opsStale,
    startsWhileUncertain' = startsWhileUncertain, passCompleted' = passCompleted,
  }

  // Чтение /metrics; у норм нет срока (READ_MAX — параметр); неуспех — ничего не делать (правило 2).
  action readStep = all {
    phase == "Read",
    nondet d = Set(0, READ_MAX).oneOf()
    nondet ok = Bool.oneOf()
    nondet want = 1.to(NUMS.length() + 1).oneOf()
    all {
      now' = now + d,
      if (ok) all {
        // Правило 1, 3: план на основе целевого набора.
        val pl = startsPlan(want, NUMS, running, uncertain, MUT == 1).concat(stopsPlan(want, NUMS_DESC, running))
        all {
          phase' = "Act", collectedAt' = now + d, plan' = pl,
          passCompleted' = passCompleted, runningPasses' = runningPasses,
        }
      } else all {
        phase' = "Idle", collectedAt' = collectedAt, plan' = List(),
        passCompleted' = passCompleted + 1, runningPasses' = runningPasses - 1,
      },
      nextFire' = nextFire, passStart' = passStart, running' = running, uncertain' = uncertain,
      passes' = passes, opsStale' = opsStale, startsWhileUncertain' = startsWhileUncertain,
    },
  }

  // Одно действие плана: start ждёт READY/таймаут (Type=notify), stop ждёт stop_timeout.
  action opStep = all {
    phase == "Act",
    plan.length() > 0,
    nondet outcome = Set("ok", "uncertain").oneOf()
    nondet dIdx = Set(0, 1).oneOf()
    val op = plan[0]
    val maxD = if (not(BLOCK)) 0 else if (op.kind == "start") START_MAX else STOP_MAX
    val d = dIdx * maxD
    val stale = now - collectedAt > FRESH
    all {
      if (RECHECK and stale) all {
        // Вариант: возраст истёк — отказ от остатка плана (не норма).
        phase' = "Idle", plan' = List(), now' = now, running' = running, uncertain' = uncertain,
        opsStale' = opsStale, startsWhileUncertain' = startsWhileUncertain,
        passCompleted' = passCompleted + 1, runningPasses' = runningPasses - 1,
      } else all {
        now' = now + d,
        plan' = plan.slice(1, plan.length()),
        phase' = if (plan.length() == 1) "Idle" else "Act",
        opsStale' = (opsStale or stale),
        // Мутант 1: повторный start по uncertain (с учётом reconciliation отсутствует) — счётчик.
        startsWhileUncertain' = if (op.kind == "start" and uncertain.contains(op.n)) startsWhileUncertain + 1 else startsWhileUncertain,
        if (op.kind == "start")
          (if (outcome == "ok") all { running' = running.union(Set(op.n)), uncertain' = uncertain.exclude(Set(op.n)) }
           else all { running' = running, uncertain' = uncertain.union(Set(op.n)) })
        else
          all { running' = running.exclude(Set(op.n)), uncertain' = uncertain },
        passCompleted' = if (plan.length() == 1) passCompleted + 1 else passCompleted,
        runningPasses' = if (plan.length() == 1) runningPasses - 1 else runningPasses,
      },
      nextFire' = nextFire, passStart' = passStart, collectedAt' = collectedAt, passes' = passes,
    },
  }

  // Пустой план (нечего делать): проход сразу завершается.
  action finishEmpty = all {
    phase == "Act", plan.length() == 0,
    phase' = "Idle", passCompleted' = passCompleted + 1, runningPasses' = runningPasses - 1,
    now' = now, nextFire' = nextFire, passStart' = passStart, collectedAt' = collectedAt,
    running' = running, uncertain' = uncertain, plan' = plan, passes' = passes,
    opsStale' = opsStale, startsWhileUncertain' = startsWhileUncertain,
  }

  // Сверка с systemd снимает uncertain (правило 5): выполняется в Idle между проходами.
  action reconcile = all {
    phase == "Idle", uncertain.size() > 0,
    nondet n = uncertain.oneOf()
    nondet started = Bool.oneOf()
    all {
      uncertain' = uncertain.exclude(Set(n)),
      running' = if (started) running.union(Set(n)) else running,
      phase' = phase, now' = now, nextFire' = nextFire, passStart' = passStart, collectedAt' = collectedAt,
      plan' = plan, passes' = passes, runningPasses' = runningPasses, opsStale' = opsStale,
      startsWhileUncertain' = startsWhileUncertain, passCompleted' = passCompleted,
    },
  }

  action stutterEnd = all { phase == "Idle", passes >= MAX_PASSES, unchangedAll }

  action step = any { advance, fire, readStep, opStep, finishEmpty, reconcile, stutterEnd }

  // ----- инварианты -----
  // С4: длительность прохода не превышает период таймера.
  val inv_passBounded = phase == "Idle" or (now - passStart) <= PASS_BOUND
  // Правило 2 (если понимать как «данные действия не старше минуты»).
  val inv_opsFresh = not(opsStale)
  // Правило 5: проходы не параллельны.
  val inv_serial = runningPasses <= 1
  // Правило 5: «uncertain» занят до сверки с systemd — без повторного start.
  val inv_noStartWhileUncertain = startsWhileUncertain == 0

  // Свидетели достижимости
  val notAct = phase != "Act"
  val notCompleted = passCompleted < 2
  val noStale = not(opsStale)
  val inv_sanity = now >= 0
}

module wt_a  { import workertimer(TIMER_PERIOD=60,BOOT=60,FRESH=60,READ_MAX=0,STOP_MAX=50,START_MAX=90,BLOCK=true,NUMS=[2,3,4],NUMS_DESC=[4,3,2],RECHECK=false,PASS_BOUND=60,MAX_PASSES=2,MUT=0).* }
module wt_b  { import workertimer(TIMER_PERIOD=60,BOOT=60,FRESH=60,READ_MAX=0,STOP_MAX=20,START_MAX=20,BLOCK=true,NUMS=[2,3,4],NUMS_DESC=[4,3,2],RECHECK=false,PASS_BOUND=60,MAX_PASSES=2,MUT=0).* }
module wt_c  { import workertimer(TIMER_PERIOD=60,BOOT=60,FRESH=60,READ_MAX=0,STOP_MAX=50,START_MAX=90,BLOCK=true,NUMS=[2,3,4],NUMS_DESC=[4,3,2],RECHECK=true,PASS_BOUND=60,MAX_PASSES=2,MUT=0).* }
module wt_d  { import workertimer(TIMER_PERIOD=60,BOOT=60,FRESH=60,READ_MAX=100000,STOP_MAX=50,START_MAX=90,BLOCK=true,NUMS=[2,3,4],NUMS_DESC=[4,3,2],RECHECK=false,PASS_BOUND=60,MAX_PASSES=2,MUT=0).* }
module wt_e  { import workertimer(TIMER_PERIOD=60,BOOT=60,FRESH=60,READ_MAX=0,STOP_MAX=50,START_MAX=90,BLOCK=false,NUMS=[2,3,4],NUMS_DESC=[4,3,2],RECHECK=false,PASS_BOUND=60,MAX_PASSES=2,MUT=0).* }
module wt_m1 { import workertimer(TIMER_PERIOD=60,BOOT=60,FRESH=60,READ_MAX=0,STOP_MAX=20,START_MAX=20,BLOCK=true,NUMS=[2,3],NUMS_DESC=[3,2],RECHECK=false,PASS_BOUND=60,MAX_PASSES=2,MUT=1).* }
module wt_m2 { import workertimer(TIMER_PERIOD=60,BOOT=60,FRESH=60,READ_MAX=0,STOP_MAX=50,START_MAX=90,BLOCK=true,NUMS=[2,3],NUMS_DESC=[3,2],RECHECK=false,PASS_BOUND=60,MAX_PASSES=2,MUT=2).* }
