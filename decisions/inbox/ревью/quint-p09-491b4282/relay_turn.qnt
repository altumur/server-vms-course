// relay_turn.qnt — очередь агента на кластере реле: дверь реле при потере очереди (С7),
// штатная остановка и судьба работы (С6), верхняя граница перехвата очереди.
// Якоря: 09.1:725-743,1396-1402; 09.2:57,60,92,133; turn.md:32-33,45-46,51-56,58-61,88-94; 09.1:1502.
module relay_turn_base {
  // DOOR_RULE: "text" — 09.2:57, 09.1:739 говорят «не открывает», закрытие открытой двери не названо;
  //            "close" — контроль-гипотеза: дверь закрывается, когда агент сам увидел потерю очереди.
  const DOOR_RULE: str
  // STOP_RULE: "text" — 09.1:1402: CAS holder "", затем выход, судьба работы не названа;
  //            "drain" — контроль-гипотеза: SIGTERM выходит только без принятой работы.
  const STOP_RULE: str
  const TURN_TERM: int   // turn.md:32
  const TURN_RENEW: int  // turn.md:33
  const GUARD_ON: bool   // мутант: охрана записей выключена
  const WAIT_X: int      // мутант: ожидающий ждёт WAIT_X * TURN_TERM

  pure val AGENTS = Set(1, 2)
  var now: int
  var ver: int
  var holder: int          // 0 — пусто (holder "" или нет строки)
  var lastChange: int      // время последнего изменения версии строки
  var role: int -> str     // standby | active | dead
  var paused: int -> bool
  var doorOpen: int -> bool
  var knownVer: int -> int
  var inFlightVer: int -> int
  var renewInFlight: int -> bool
  var seenVer: int -> int
  var seenAt: int -> int
  var nextCheck: int -> int
  var observedLoss: int -> bool
  var pendingWrite: int -> int   // -1 нет; иначе версия охраны записи
  var acceptedByNonHolder: bool
  var acceptedWrites: int
  var inflight: int -> int       // принятая работа (удержанный POST, запрос токена)
  var dropped: int               // работа, брошенная при выходе по SIGTERM
  var staleObserved: int         // 200 у двери после того, как агент сам увидел потерю
  var staleUnobserved: int       // 200 у двери, когда очередь уже чужая, агент ещё не знает
  var served: int                // 200 у истинно активной двери
  var releaseLost: bool          // SIGTERM попал на незавершённое продление, CAS неверной версии
  var lastAction: str

  action init = all {
    now' = 0, ver' = 0, holder' = 0, lastChange' = 0,
    role' = AGENTS.mapBy(_ => "standby"), paused' = AGENTS.mapBy(_ => false),
    doorOpen' = AGENTS.mapBy(_ => false), knownVer' = AGENTS.mapBy(_ => -1),
    inFlightVer' = AGENTS.mapBy(_ => -1), renewInFlight' = AGENTS.mapBy(_ => false),
    seenVer' = AGENTS.mapBy(_ => -1), seenAt' = AGENTS.mapBy(_ => 0),
    nextCheck' = AGENTS.mapBy(_ => 0), observedLoss' = AGENTS.mapBy(_ => false),
    pendingWrite' = AGENTS.mapBy(_ => -1), acceptedByNonHolder' = false, acceptedWrites' = 0,
    inflight' = AGENTS.mapBy(_ => 0), dropped' = 0, staleObserved' = 0, staleUnobserved' = 0,
    served' = 0, releaseLost' = false, lastAction' = "init",
  }

  // Ход времени: нельзя перешагнуть срок проверки живого не на паузе агента (допущение о планировании).
  action tick = {
    nondet dt = oneOf(Set(TURN_RENEW))
    all {
      AGENTS.forall(a => role.get(a) == "dead" or paused.get(a) or now + dt <= nextCheck.get(a)),
      now' = now + dt,
      ver' = ver, holder' = holder, lastChange' = lastChange, role' = role, paused' = paused,
      doorOpen' = doorOpen, knownVer' = knownVer, inFlightVer' = inFlightVer, renewInFlight' = renewInFlight,
      seenVer' = seenVer, seenAt' = seenAt, nextCheck' = nextCheck, observedLoss' = observedLoss,
      pendingWrite' = pendingWrite, acceptedByNonHolder' = acceptedByNonHolder, acceptedWrites' = acceptedWrites,
      inflight' = inflight, dropped' = dropped, staleObserved' = staleObserved, staleUnobserved' = staleUnobserved,
      served' = served, releaseLost' = releaseLost, lastAction' = "tick",
    }
  }

  // Один проход агента: продление, наблюдение потери или попытка взять очередь.
  action agentPass(a: int): bool = all {
    role.get(a) != "dead", not(paused.get(a)), now >= nextCheck.get(a), not(renewInFlight.get(a)),
    if (role.get(a) == "active")
      if (holder == a and ver == knownVer.get(a))
        // шаг продления: CAS прошёл, ответ ещё не дошёл (turn.md:51)
        all {
          ver' = ver + 1, lastChange' = now, holder' = holder,
          renewInFlight' = renewInFlight.set(a, true), inFlightVer' = inFlightVer.set(a, ver + 1),
          role' = role, doorOpen' = doorOpen, seenVer' = seenVer, seenAt' = seenAt,
          observedLoss' = observedLoss, knownVer' = knownVer,
          nextCheck' = nextCheck.set(a, now + TURN_RENEW), lastAction' = "renew",
        }
      else
        // потеря очереди замечена (09.1:1397, конфликт -> standby)
        all {
          ver' = ver, lastChange' = lastChange, holder' = holder,
          renewInFlight' = renewInFlight, inFlightVer' = inFlightVer,
          role' = role.set(a, "standby"),
          doorOpen' = if (DOOR_RULE == "close") doorOpen.set(a, false) else doorOpen,
          seenVer' = seenVer.set(a, ver), seenAt' = seenAt.set(a, now),
          observedLoss' = observedLoss.set(a, true), knownVer' = knownVer,
          nextCheck' = nextCheck.set(a, now + TURN_RENEW), lastAction' = "lossObserved",
        }
    else // standby
      if (holder == 0 or (holder != a and ver == seenVer.get(a) and now - seenAt.get(a) >= WAIT_X * TURN_TERM))
        // взять: пусто или чужая неизменная >= TURN_TERM (09.1:1398-1399, turn.md:45)
        all {
          ver' = ver + 1, lastChange' = now, holder' = a,
          renewInFlight' = renewInFlight, inFlightVer' = inFlightVer,
          role' = role.set(a, "active"), doorOpen' = doorOpen.set(a, true),
          seenVer' = seenVer, seenAt' = seenAt,
          observedLoss' = observedLoss.set(a, false), knownVer' = knownVer.set(a, ver + 1),
          nextCheck' = nextCheck.set(a, now + TURN_RENEW), lastAction' = "takeTurn",
        }
      else if (holder != a and ver != seenVer.get(a))
        all {
          ver' = ver, lastChange' = lastChange, holder' = holder,
          renewInFlight' = renewInFlight, inFlightVer' = inFlightVer,
          role' = role, doorOpen' = doorOpen,
          seenVer' = seenVer.set(a, ver), seenAt' = seenAt.set(a, now),
          observedLoss' = observedLoss, knownVer' = knownVer,
          nextCheck' = nextCheck.set(a, now + TURN_RENEW), lastAction' = "observeVer",
        }
      else
        all {
          ver' = ver, lastChange' = lastChange, holder' = holder,
          renewInFlight' = renewInFlight, inFlightVer' = inFlightVer,
          role' = role, doorOpen' = doorOpen, seenVer' = seenVer, seenAt' = seenAt,
          observedLoss' = observedLoss, knownVer' = knownVer,
          nextCheck' = nextCheck.set(a, now + TURN_RENEW), lastAction' = "waitPass",
        },
    paused' = paused, now' = now, pendingWrite' = pendingWrite,
    acceptedByNonHolder' = acceptedByNonHolder, acceptedWrites' = acceptedWrites,
    inflight' = inflight, dropped' = dropped, staleObserved' = staleObserved, staleUnobserved' = staleUnobserved,
    served' = served, releaseLost' = releaseLost,
  }

  // Ответ на продление: версия запомнена (turn.md:51).
  action renewAck(a: int): bool = all {
    renewInFlight.get(a), role.get(a) != "dead",
    knownVer' = knownVer.set(a, inFlightVer.get(a)),
    renewInFlight' = renewInFlight.set(a, false),
    inFlightVer' = inFlightVer, now' = now, ver' = ver, holder' = holder, lastChange' = lastChange,
    role' = role, paused' = paused, doorOpen' = doorOpen, seenVer' = seenVer, seenAt' = seenAt,
    nextCheck' = nextCheck, observedLoss' = observedLoss, pendingWrite' = pendingWrite,
    acceptedByNonHolder' = acceptedByNonHolder, acceptedWrites' = acceptedWrites,
    inflight' = inflight, dropped' = dropped, staleObserved' = staleObserved, staleUnobserved' = staleUnobserved,
    served' = served, releaseLost' = releaseLost, lastAction' = "renewAck",
  }

  // SIGTERM у активного: CAS своей версии, затем выход (09.1:729,1402; turn.md:56 без повтора при конфликте).
  action sigterm(a: int): bool = all {
    role.get(a) == "active", not(paused.get(a)),
    STOP_RULE == "text" or inflight.get(a) == 0,
    if (holder == a and ver == knownVer.get(a))
      all { holder' = 0, ver' = ver + 1, lastChange' = now, releaseLost' = releaseLost, lastAction' = "sigterm" }
    else
      all { holder' = holder, ver' = ver, lastChange' = lastChange, releaseLost' = true, lastAction' = "sigtermConflict" },
    role' = role.set(a, "dead"), doorOpen' = doorOpen.set(a, false),
    renewInFlight' = renewInFlight.set(a, false),
    inFlightVer' = inFlightVer, knownVer' = knownVer, seenVer' = seenVer, seenAt' = seenAt,
    nextCheck' = nextCheck, observedLoss' = observedLoss, paused' = paused, now' = now,
    pendingWrite' = pendingWrite, acceptedByNonHolder' = acceptedByNonHolder, acceptedWrites' = acceptedWrites,
    inflight' = inflight.set(a, 0), dropped' = dropped + inflight.get(a),
    staleObserved' = staleObserved, staleUnobserved' = staleUnobserved, served' = served,
  }

  action kill(a: int): bool = all {
    role.get(a) != "dead",
    role' = role.set(a, "dead"), doorOpen' = doorOpen.set(a, false),
    renewInFlight' = renewInFlight.set(a, false),
    inFlightVer' = inFlightVer, knownVer' = knownVer, seenVer' = seenVer, seenAt' = seenAt,
    nextCheck' = nextCheck, observedLoss' = observedLoss, paused' = paused, now' = now,
    ver' = ver, holder' = holder, lastChange' = lastChange,
    pendingWrite' = pendingWrite, acceptedByNonHolder' = acceptedByNonHolder, acceptedWrites' = acceptedWrites,
    inflight' = inflight.set(a, 0), dropped' = dropped,
    staleObserved' = staleObserved, staleUnobserved' = staleUnobserved, served' = served,
    releaseLost' = releaseLost, lastAction' = "kill",
  }

  action pause(a: int): bool = all {
    role.get(a) != "dead", not(paused.get(a)),
    paused' = paused.set(a, true),
    now' = now, ver' = ver, holder' = holder, lastChange' = lastChange, role' = role,
    doorOpen' = doorOpen, knownVer' = knownVer, inFlightVer' = inFlightVer, renewInFlight' = renewInFlight,
    seenVer' = seenVer, seenAt' = seenAt, nextCheck' = nextCheck, observedLoss' = observedLoss,
    pendingWrite' = pendingWrite, acceptedByNonHolder' = acceptedByNonHolder, acceptedWrites' = acceptedWrites,
    inflight' = inflight, dropped' = dropped, staleObserved' = staleObserved, staleUnobserved' = staleUnobserved,
    served' = served, releaseLost' = releaseLost, lastAction' = "pause",
  }
  // Пауза снимается, проверка становится сразу должной (now >= nextCheck) — следующий agentPass.
  action resume(a: int): bool = all {
    paused.get(a),
    paused' = paused.set(a, false),
    nextCheck' = nextCheck.set(a, now),
    now' = now, ver' = ver, holder' = holder, lastChange' = lastChange, role' = role,
    doorOpen' = doorOpen, knownVer' = knownVer, inFlightVer' = inFlightVer, renewInFlight' = renewInFlight,
    seenVer' = seenVer, seenAt' = seenAt, observedLoss' = observedLoss,
    pendingWrite' = pendingWrite, acceptedByNonHolder' = acceptedByNonHolder, acceptedWrites' = acceptedWrites,
    inflight' = inflight, dropped' = dropped, staleObserved' = staleObserved, staleUnobserved' = staleUnobserved,
    served' = served, releaseLost' = releaseLost, lastAction' = "resume",
  }

  // Запрос члена: первая открытая дверь в порядке адресов (09.2:60), ответ 200 из памяти (09.2:92,133).
  // Пауза двери: соединение есть, ответа нет — здесь не моделируется (С2, не задача модели).
  pure val firstDoorOrder = List(1, 2)
  def firstOpen = if (doorOpen.get(1)) 1 else if (doorOpen.get(2)) 2 else 0
  action memberPost = all {
    firstOpen != 0, not(paused.get(firstOpen)),
    val a = firstOpen
    all {
      if (role.get(a) == "active" and holder == a) all { served' = served + 1, staleObserved' = staleObserved, staleUnobserved' = staleUnobserved }
      else if (observedLoss.get(a)) all { served' = served, staleObserved' = staleObserved + 1, staleUnobserved' = staleUnobserved }
      else all { served' = served, staleObserved' = staleObserved, staleUnobserved' = staleUnobserved + 1 },
    },
    now' = now, ver' = ver, holder' = holder, lastChange' = lastChange, role' = role, paused' = paused,
    doorOpen' = doorOpen, knownVer' = knownVer, inFlightVer' = inFlightVer, renewInFlight' = renewInFlight,
    seenVer' = seenVer, seenAt' = seenAt, nextCheck' = nextCheck, observedLoss' = observedLoss,
    pendingWrite' = pendingWrite, acceptedByNonHolder' = acceptedByNonHolder, acceptedWrites' = acceptedWrites,
    inflight' = inflight, dropped' = dropped, releaseLost' = releaseLost, lastAction' = "memberPost",
  }

  // Запись под охраной: выдана с версией, применяется позже (turn.md:53,83,88-89).
  action issueWrite(a: int): bool = all {
    role.get(a) == "active", not(paused.get(a)), pendingWrite.get(a) == -1, knownVer.get(a) >= 0,
    pendingWrite' = pendingWrite.set(a, knownVer.get(a)),
    now' = now, ver' = ver, holder' = holder, lastChange' = lastChange, role' = role, paused' = paused,
    doorOpen' = doorOpen, knownVer' = knownVer, inFlightVer' = inFlightVer, renewInFlight' = renewInFlight,
    seenVer' = seenVer, seenAt' = seenAt, nextCheck' = nextCheck, observedLoss' = observedLoss,
    acceptedByNonHolder' = acceptedByNonHolder, acceptedWrites' = acceptedWrites,
    inflight' = inflight, dropped' = dropped, staleObserved' = staleObserved, staleUnobserved' = staleUnobserved,
    served' = served, releaseLost' = releaseLost, lastAction' = "issueWrite",
  }
  action applyWrite(a: int): bool = all {
    pendingWrite.get(a) != -1,
    val ok = pendingWrite.get(a) == ver or not(GUARD_ON)
    all {
      acceptedWrites' = if (ok) acceptedWrites + 1 else acceptedWrites,
      acceptedByNonHolder' = (acceptedByNonHolder or (ok and holder != a)),
    },
    pendingWrite' = pendingWrite.set(a, -1),
    now' = now, ver' = ver, holder' = holder, lastChange' = lastChange, role' = role, paused' = paused,
    doorOpen' = doorOpen, knownVer' = knownVer, inFlightVer' = inFlightVer, renewInFlight' = renewInFlight,
    seenVer' = seenVer, seenAt' = seenAt, nextCheck' = nextCheck, observedLoss' = observedLoss,
    inflight' = inflight, dropped' = dropped, staleObserved' = staleObserved, staleUnobserved' = staleUnobserved,
    served' = served, releaseLost' = releaseLost, lastAction' = "applyWrite",
  }

  action acceptWork(a: int): bool = all {
    role.get(a) == "active", doorOpen.get(a), not(paused.get(a)), inflight.get(a) < 2,
    inflight' = inflight.set(a, inflight.get(a) + 1),
    now' = now, ver' = ver, holder' = holder, lastChange' = lastChange, role' = role, paused' = paused,
    doorOpen' = doorOpen, knownVer' = knownVer, inFlightVer' = inFlightVer, renewInFlight' = renewInFlight,
    seenVer' = seenVer, seenAt' = seenAt, nextCheck' = nextCheck, observedLoss' = observedLoss,
    pendingWrite' = pendingWrite, acceptedByNonHolder' = acceptedByNonHolder, acceptedWrites' = acceptedWrites,
    dropped' = dropped, staleObserved' = staleObserved, staleUnobserved' = staleUnobserved,
    served' = served, releaseLost' = releaseLost, lastAction' = "acceptWork",
  }
  action finishWork(a: int): bool = all {
    inflight.get(a) > 0, role.get(a) != "dead",
    inflight' = inflight.set(a, inflight.get(a) - 1),
    now' = now, ver' = ver, holder' = holder, lastChange' = lastChange, role' = role, paused' = paused,
    doorOpen' = doorOpen, knownVer' = knownVer, inFlightVer' = inFlightVer, renewInFlight' = renewInFlight,
    seenVer' = seenVer, seenAt' = seenAt, nextCheck' = nextCheck, observedLoss' = observedLoss,
    pendingWrite' = pendingWrite, acceptedByNonHolder' = acceptedByNonHolder, acceptedWrites' = acceptedWrites,
    dropped' = dropped, staleObserved' = staleObserved, staleUnobserved' = staleUnobserved,
    served' = served, releaseLost' = releaseLost, lastAction' = "finishWork",
  }

  action step = any {
    tick,
    nondet a = oneOf(AGENTS) any {
      agentPass(a), renewAck(a), sigterm(a), kill(a), pause(a), resume(a),
      issueWrite(a), applyWrite(a), acceptWork(a), finishWork(a),
    },
    memberPost,
  }
  // Шаг для границы перехвата: пауза только держателя (ожидающий обязан быть живым и не на паузе).
  action stepBound = any {
    tick,
    nondet a = oneOf(AGENTS) any {
      agentPass(a), renewAck(a), sigterm(a), kill(a),
      all { holder == a, pause(a) },
      resume(a),
    },
  }

  // Сфокусированные шаги: без них случайный обход не проходит длинные цепочки ожидания.
  action stepDoor = any {
    tick,
    nondet a = oneOf(AGENTS) any { agentPass(a), renewAck(a), pause(a), resume(a) },
    memberPost,
  }
  action stepKill = any {
    tick,
    nondet a = oneOf(AGENTS) any { agentPass(a), renewAck(a), kill(a) },
  }

  def waiterLive = AGENTS.exists(a => role.get(a) == "standby" and not(paused.get(a)))
  def holderInactive = holder == 0 or role.get(holder) != "active" or paused.get(holder)

  // --- Инварианты ---
  // С7: 09.2:57 как инвариант состояния: дверь открыта только у активного.
  val DoorOnlyActive = AGENTS.forall(a => not(doorOpen.get(a)) or role.get(a) == "active")
  // С7: ни одного 200 после того, как агент сам увидел потерю очереди.
  val NoStaleObserved = staleObserved == 0
  // С7, окно: 200 от двери, чья очередь уже чужая, но агент ещё не знает.
  val NoStaleUnobserved = staleUnobserved == 0
  // Охрана: записи со старой версией стором отвергаются (turn.md:88-89).
  val GuardNoLateWrite = not(acceptedByNonHolder)
  // Граница перехвата: при живом ожидающем и неактивном держателе время от последнего изменения строки
  // не превышает TURN_TERM + 2*TURN_RENEW. Граница для шага stepBound.
  val HandoverBound = not(waiterLive and holderInactive) or now - lastChange <= TURN_TERM + 2 * TURN_RENEW
  // С6: при SIGTERM не бросается принятая работа.
  val NoDroppedOnSigterm = dropped == 0
  // Не более одного активного по строке.
  val OneActiveByRow = AGENTS.filter(a => role.get(a) == "active" and holder == a).size() <= 1

  // --- Свидетели ---
  val witStaleObserved = not(staleObserved > 0)
  val witServed = not(served > 0)
  val witReleaseLost = not(releaseLost and holder != 0 and AGENTS.exists(a => role.get(a) == "standby"))
  val witDropped = not(dropped > 0)
  val witWaiterTook = not(lastAction == "takeTurn" and holder == 2 and role.get(1) == "dead" and ver >= 2)
}

module relay_text { import relay_turn_base(DOOR_RULE = "text", STOP_RULE = "text", TURN_TERM = 45, TURN_RENEW = 10, GUARD_ON = true, WAIT_X = 1).* }
module relay_close { import relay_turn_base(DOOR_RULE = "close", STOP_RULE = "text", TURN_TERM = 45, TURN_RENEW = 10, GUARD_ON = true, WAIT_X = 1).* }
module relay_drain { import relay_turn_base(DOOR_RULE = "close", STOP_RULE = "drain", TURN_TERM = 45, TURN_RENEW = 10, GUARD_ON = true, WAIT_X = 1).* }
module relay_mut_noguard { import relay_turn_base(DOOR_RULE = "text", STOP_RULE = "text", TURN_TERM = 45, TURN_RENEW = 10, GUARD_ON = false, WAIT_X = 1).* }
module relay_mut_slowwait { import relay_turn_base(DOOR_RULE = "text", STOP_RULE = "text", TURN_TERM = 45, TURN_RENEW = 10, GUARD_ON = true, WAIT_X = 2).* }
