// P/05 pass and step `mirror` (findings C1, M1). Срез d21ed721.
// Модель только сроков и порядка шага mirror; не модель реализации.
// Числа: PASS_EVERY, PEER_FAILS — forms/runtime-constants.tsv; BUDGET, NB, PEERS_N, PASS_BOUND — параметры.
module p05_pass {
  const PASS_EVERY: int        // const: 600, norms:299 (от конца прохода)
  const PEER_FAILS: int        // const: 3, norms:985
  const NB: int                // сколько закрытых ведер сосед не имеет (параметр модели)
  const PEERS_N: int           // следующие copies живых соседей norms:984
  const BUDGET: int            // 0 = срока вызова в P/05 нет (norms:371); >0 = объявленный срок (prod:9)
  const EXPIRY_FAIL: bool      // истечение считается неуспехом PEER_FAILS (норма не называет)
  const REFUSAL_FAIL: bool     // отказ по строке (400/409/422) считается неуспехом (норма не называет)
  const REFUSE_HEAD: int       // первые REFUSE_HEAD ведер получают постоянный отказ строки
  const KINDS: Set[str]        // поведения соседа: "OK" | "FAIL" | "HANG" | "SLOW"
  const PER_CALL: bool         // поведение выбирается на каждый вызов (иначе фиксировано на соседа)
  const STEP_BUDGET: int       // 0 = нет; >0 = гипотетический срок шага, проверяемый между вызовами (не норма)
  const PASS_BOUND: int        // проверяемая граница длительности прохода
  const MUT_NO_SKIP: bool      // мутант: skip после PEER_FAILS не применяется
  const MUT_KEEP_SKIP: bool    // мутант: skip переносится на следующий проход (против s67)

  type S = {
    now: int, nextPass: int, inMirror: bool, passStart: int, passCount: int,
    lastPassDur: int, lastRetain: int, kind: int -> str,
    cur: int, bucket: int, failsCur: int, skipped: Set[int],
    callDeadline: int, callKind: str, hung: bool,
    copied: Set[(int, int)], lastCopied: Set[(int, int)],
    consulted: Set[int], lastConsulted: Set[int]
  }

  var s: S

  pure val PEERS: Set[int] = 1.to(PEERS_N)
  pure val BEHIND: Set[int] = (REFUSE_HEAD + 1).to(NB)

  // Применить исход текущего вызова: успех сбрасывает серию (s67 success_resets_sequence),
  // неуспех продолжает к следующему ведру, PEER_FAILS подряд — сосед до конца прохода пропущен (norms:985).
  pure def after(st: S, out: str): S = {
    val counted = out == "FAIL" or (out == "EXPIRED" and EXPIRY_FAIL) or (out == "REFUSE" and REFUSAL_FAIL)
    val succ = out == "OK"
    val f2 = if (succ) 0 else if (counted) st.failsCur + 1 else st.failsCur
    val skipNow = counted and f2 >= PEER_FAILS and not(MUT_NO_SKIP)
    val b2 = st.bucket + 1
    val donePeer = skipNow or b2 > NB
    st.with("failsCur", if (donePeer) 0 else f2)
      .with("bucket", if (donePeer) 1 else b2)
      .with("cur", if (donePeer) st.cur + 1 else st.cur)
      .with("skipped", if (skipNow) st.skipped.union(Set(st.cur)) else st.skipped)
      .with("copied", if (succ) st.copied.union(Set((st.cur, st.bucket))) else st.copied)
      .with("consulted", st.consulted.union(Set(st.cur)))
  }

  pure def stepExceeded(st: S): bool = STEP_BUDGET > 0 and st.now - st.passStart >= STEP_BUDGET

  action init = {
    nondet k = oneOf(setOfMaps(PEERS, KINDS))
    s' = {
      now: 0, nextPass: 0, inMirror: false, passStart: -1, passCount: 0,
      lastPassDur: 0, lastRetain: -1, kind: k,
      cur: 1, bucket: 1, failsCur: 0, skipped: Set(),
      callDeadline: -1, callKind: "none", hung: false,
      copied: Set(), lastCopied: Set(), consulted: Set(), lastConsulted: Set()
    }
  }

  // Первый проход сразу после готовности, далее PASS_EVERY от конца (norms:299). retain, usage, relieve — нулевой длительности (оптимистично).
  action startPass = all {
    not(s.inMirror), s.callDeadline < 0, not(s.hung), s.now >= s.nextPass,
    s' = s.with("lastRetain", s.now).with("passStart", s.now).with("inMirror", true)
          .with("cur", 1).with("bucket", 1).with("failsCur", 0)
          .with("skipped", if (MUT_KEEP_SKIP) s.skipped else Set())
          .with("copied", Set()).with("consulted", Set())
  }

  action idleAdvance = all {
    not(s.inMirror), s.now < s.nextPass,
    s' = s.with("now", s.nextPass)
  }

  action skipAdvance = all {
    s.inMirror, s.callDeadline < 0, not(s.hung), s.cur <= PEERS_N, s.skipped.contains(s.cur), not(stepExceeded(s)),
    s' = s.with("cur", s.cur + 1).with("bucket", 1).with("failsCur", 0)
  }

  action callBegin = all {
    s.inMirror, s.callDeadline < 0, not(s.hung), s.cur <= PEERS_N, not(s.skipped.contains(s.cur)), not(stepExceeded(s)),
    nondet chosen = oneOf(KINDS)
    val k = if (s.bucket <= REFUSE_HEAD) "REFUSE" else if (PER_CALL) chosen else s.kind.get(s.cur)
    val markC = s.with("consulted", s.consulted.union(Set(s.cur)))
    s' = if (k == "OK") after(s, "OK")
         else if (k == "FAIL") after(s, "FAIL")
         else if (k == "REFUSE") after(s, "REFUSE")
         else if (k == "HANG" and BUDGET == 0) markC.with("hung", true)
         else if (k == "HANG") markC.with("callDeadline", s.now + BUDGET).with("callKind", "HANG")
         else markC.with("callDeadline", s.now + BUDGET - 1).with("callKind", "SLOW")   // успех чуть раньше срока
  }

  action callEnd = all {
    s.callDeadline >= 0,
    val t = s.with("now", s.callDeadline).with("callDeadline", -1)
    s' = if (s.callKind == "HANG") after(t, "EXPIRED") else after(t, "OK")
  }

  // Зависший вызов без срока: ничего не завершается, идёт только время.
  action hangTick = all { s.hung, s' = s.with("now", s.now + PASS_EVERY) }

  action finishMirror = all {
    s.inMirror, s.callDeadline < 0, not(s.hung), s.cur > PEERS_N or stepExceeded(s),
    s' = s.with("inMirror", false).with("passCount", s.passCount + 1)
          .with("lastPassDur", s.now - s.passStart)
          .with("nextPass", s.now + PASS_EVERY)
          .with("lastCopied", s.copied).with("lastConsulted", s.consulted)
  }

  action step = any { startPass, idleAdvance, skipAdvance, callBegin, callEnd, hangTick, finishMirror }

  // Инварианты (граница распространяется и на идущий, и на завершённый проход).
  val inv_passBounded = (s.inMirror implies (s.now - s.passStart <= PASS_BOUND)) and
                        (s.passCount > 0 implies s.lastPassDur <= PASS_BOUND)
  val inv_retainGap = s.lastRetain < 0 or s.now - s.lastRetain <= PASS_EVERY + PASS_BOUND
  // M1: у здорового соседа за завершённый проход скопированы все ведра, стоящие за постоянно отказанными.
  val inv_behindCopied = (s.passCount > 0 and s.kind.get(1) == "OK") implies
                         BEHIND.forall(b => s.lastCopied.contains((1, b)))
  // s67: следующий проход снова обращается к соседу.
  val inv_consulted = s.passCount > 0 implies PEERS.forall(p => s.lastConsulted.contains(p))
  val inv_types = s.now >= 0 and s.cur >= 1 and s.bucket >= 1 and s.failsCur >= 0

  // Свидетели достижимости (ожидается нарушение: след — доказательство).
  val wit_completedPass = not(s.passCount >= 1)
  val wit_twoPasses = not(s.passCount >= 2)
  val wit_tight = not(s.passCount >= 1 and s.lastPassDur == PASS_BOUND)
  val wit_hung = not(s.hung and s.inMirror)
  val wit_hangThenSecondCall = not(s.passCount >= 1 and s.consulted.size() > 0 and s.inMirror)
  val wit_slow = not(s.passCount >= 1 and s.kind.get(1) == "SLOW" and s.lastPassDur > 0)
}
