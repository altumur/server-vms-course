// -*- mode: Bluespec; -*-
// P/02 службы и запуск, срез 244355d161139bd6fe65fd68c7e5134598c21ba3.
// Сокет-активация против RestartPreventExitStatus=2 и остановки оператора (находка С5).
//
// Нормы: Restart=always, RestartPreventExitStatus=2, RestartSec=2 (02.4:48-49); отказ старта кодом 2
// «until an action of the operator» (02.4:48-49, 02.3:233-234); сокетные юниты configstore-*.socket с
// Service=configstore.service (02.4:55-58); After без Wants у служб (02.4:49); пауза 1 с у клиентов при
// неответе (02.3:212).
//
// Допущения (ЯВНО; связка «сокет + код 2» выведена рассуждением, см. С5 и задание):
//  A1. Новое соединение на сокете Accept=no при неактивной службе запускает службу (man systemd.socket
//      «activate on incoming traffic», Service=). Срабатывание не отличает exit 2 от остальных причин.
//  A2. Сокет остаётся слушать после exit 2 и после systemctl stop службы (не прямая норма; man
//      systemd.socket, systemd.service — «still be activated by»).
//  A3. TriggerLimit по умолчанию 20 срабатываний за 2 с для Accept=no, затем сокет в failure и не
//      принимает до перезапуска (man systemd.socket TriggerLimit*); норма TriggerLimit не упоминает.
//  A4. Срабатывания сокета происходят при новых соединениях, когда служба не работает (пока работает —
//      соединения обслуживаются, активации нет).
// Что НЕ моделируется: socket Accept=yes, порядок проверки TriggerLimit относительно enqueued job,
// семантика заполнения backlog, детальная работа демона; сокет при неработающей службе после Restart=.
module socketact {
  const BURST: int          // TriggerLimitBurst, 20 по man (Accept=no); 0 — отключён
  const WINDOW: int         // TriggerLimitIntervalSec = 2 (сотни мс не вводим; в единицах 1 с)
  const SOCK_ACT: bool      // сокет запускает службу (допущение A1)
  const OP_STOPS_SOCKET: bool // оператор останавливает и .socket (вариант лечения)
  const EXIT2_STOPS_SOCKET: bool // код 2 останавливает сокеты (вариант лечения)
  const MAX_ACTIONS: int    // граница
  const MUT: int

  // svc: Inactive | Running | Failed2
  var svc: str
  var sock: str             // Listening | Failed | Stopped
  var now: int
  var windowStart: int
  var trigCount: int
  var opStopped: bool       // оператор «стоп» выставлен до его следующего действия
  var restartsAfter2: int   // запуск через Restart= после exit 2
  var socketStartsAfter2: int // запуск сокетом после exit 2
  var startsInOpWindow: int // запуск сокетом при opStopped
  var actions: int
  var last2: bool           // последний исход — код 2

  action unch = all {
    svc' = svc, sock' = sock, now' = now, windowStart' = windowStart, trigCount' = trigCount,
    opStopped' = opStopped, restartsAfter2' = restartsAfter2, socketStartsAfter2' = socketStartsAfter2,
    startsInOpWindow' = startsInOpWindow, actions' = actions, last2' = last2,
  }

  action init = all {
    svc' = "Running", sock' = "Listening", now' = 0, windowStart' = 0, trigCount' = 0,
    opStopped' = false, restartsAfter2' = 0, socketStartsAfter2' = 0, startsInOpWindow' = 0,
    actions' = 0, last2' = false,
  }

  // Отказ старта или работы с кодом: 2 — без Restart; 1 — Restart=always.
  action exitCode = all {
    svc == "Running", actions < MAX_ACTIONS,
    nondet code = Set(1, 2).oneOf()
    all {
      svc' = if (code == 2) "Failed2" else "Inactive",
      last2' = code == 2,
      sock' = if (code == 2 and EXIT2_STOPS_SOCKET) "Stopped" else sock,
      actions' = actions + 1,
      now' = now, windowStart' = windowStart, trigCount' = trigCount, opStopped' = opStopped,
      restartsAfter2' = restartsAfter2, socketStartsAfter2' = socketStartsAfter2,
      startsInOpWindow' = startsInOpWindow,
    },
  }

  // Restart= systemd: только для кода 1 (RestartPreventExitStatus=2); мутант 1 — и на 2.
  action restartSvc = all {
    svc == "Inactive" or (MUT == 1 and svc == "Failed2"),
    not(opStopped), actions < MAX_ACTIONS,
    svc' = "Running", last2' = false, actions' = actions + 1,
    restartsAfter2' = if (svc == "Failed2") restartsAfter2 + 1 else restartsAfter2,
    now' = now, sock' = sock, windowStart' = windowStart, trigCount' = trigCount, opStopped' = opStopped,
    socketStartsAfter2' = socketStartsAfter2, startsInOpWindow' = startsInOpWindow,
  }

  // Подключение клиента: при неработающей службе сокет её запускает (A1, A4).
  // k — число срабатываний за шаг (без отдельных шагов на каждую попытку), time — приращение.
  action connect = all {
    SOCK_ACT, sock == "Listening", svc != "Running", actions < MAX_ACTIONS,
    nondet k = 1.to(21).oneOf()
    nondet dt = 0.to(3).oneOf()
    val nw = now + dt
    val reset = nw - windowStart >= WINDOW
    val cnt = (if (reset) 0 else trigCount) + k
    all {
      now' = nw, windowStart' = if (reset) nw else windowStart, trigCount' = cnt,
      if (BURST > 0 and cnt > BURST) all {
        sock' = "Failed", svc' = svc, last2' = last2, opStopped' = opStopped,
        restartsAfter2' = restartsAfter2, socketStartsAfter2' = socketStartsAfter2,
        startsInOpWindow' = startsInOpWindow,
      } else all {
        sock' = sock, svc' = "Running", last2' = false, opStopped' = opStopped,
        restartsAfter2' = restartsAfter2,
        socketStartsAfter2' = if (svc == "Failed2") socketStartsAfter2 + 1 else socketStartsAfter2,
        startsInOpWindow' = if (opStopped) startsInOpWindow + 1 else startsInOpWindow,
      },
      actions' = actions + 1,
    },
  }

  // Оператор: systemctl stop службы (окно обслуживания, restore); вариант — и .socket.
  action operatorStop = all {
    svc == "Running", actions < MAX_ACTIONS,
    svc' = "Inactive", opStopped' = true, last2' = false,
    sock' = if (OP_STOPS_SOCKET) "Stopped" else sock,
    now' = now, windowStart' = windowStart, trigCount' = trigCount,
    restartsAfter2' = restartsAfter2, socketStartsAfter2' = socketStartsAfter2,
    startsInOpWindow' = startsInOpWindow, actions' = actions + 1,
  }

  // Оператор снимает отказ (код 2) / завершает окно обслуживания: перезапуск оператором.
  action operatorStart = all {
    svc != "Running", actions < MAX_ACTIONS,
    svc' = "Running", opStopped' = false, last2' = false,
    sock' = if (OP_STOPS_SOCKET or EXIT2_STOPS_SOCKET) "Listening" else sock,
    now' = now, windowStart' = windowStart, trigCount' = trigCount,
    restartsAfter2' = restartsAfter2, socketStartsAfter2' = socketStartsAfter2,
    startsInOpWindow' = startsInOpWindow, actions' = actions + 1,
  }

  action stutter = all { actions >= MAX_ACTIONS, unch }

  action step = any { exitCode, restartSvc, connect, operatorStop, operatorStart, stutter }

  // Код 2: без перезапуска и подъёма до действия оператора (02.4:48-49, 02.3:233).
  val inv_code2NoRestart = restartsAfter2 == 0 and socketStartsAfter2 == 0
  // Только путь Restart= (RestartPreventExitStatus=2 сам по себе работает).
  val inv_restartPrevent2 = restartsAfter2 == 0
  // Окно обслуживания: стоп оператора держится до его следующего действия.
  val inv_opStopHolds = startsInOpWindow == 0
  // Сокет не попадает в failure.
  val inv_sockNotFailed = sock != "Failed"
  // Свидетели
  val notRunning = svc != "Running"
  val notFailed2 = svc != "Failed2"
  val inv_sanity = now >= 0
}

module sa_a  { import socketact(BURST=20,WINDOW=2,SOCK_ACT=true,OP_STOPS_SOCKET=false,EXIT2_STOPS_SOCKET=false,MAX_ACTIONS=8,MUT=0).* }
module sa_nosock { import socketact(BURST=20,WINDOW=2,SOCK_ACT=false,OP_STOPS_SOCKET=false,EXIT2_STOPS_SOCKET=false,MAX_ACTIONS=8,MUT=0).* }
module sa_fix2 { import socketact(BURST=20,WINDOW=2,SOCK_ACT=true,OP_STOPS_SOCKET=false,EXIT2_STOPS_SOCKET=true,MAX_ACTIONS=8,MUT=0).* }
module sa_fixop { import socketact(BURST=20,WINDOW=2,SOCK_ACT=true,OP_STOPS_SOCKET=true,EXIT2_STOPS_SOCKET=false,MAX_ACTIONS=8,MUT=0).* }
module sa_notrig { import socketact(BURST=0,WINDOW=2,SOCK_ACT=true,OP_STOPS_SOCKET=false,EXIT2_STOPS_SOCKET=false,MAX_ACTIONS=8,MUT=0).* }
module sa_m1 { import socketact(BURST=20,WINDOW=2,SOCK_ACT=false,OP_STOPS_SOCKET=false,EXIT2_STOPS_SOCKET=false,MAX_ACTIONS=8,MUT=1).* }
