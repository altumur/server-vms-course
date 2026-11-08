// -*- mode: Bluespec; -*-
// Перенос формы Platform/02-installer/forms/rollout-poll.machine.yaml (N1.9 poll) на срезе
// 244355d161139bd6fe65fd68c7e5134598c21ba3 как есть: переходы tick/self_status/status/commit/
// read_expired/wait_expired и действия в порядке машины (см. id переходов tick-1… в комментариях).
// Время — сотые секунды (трассы содержат 1.28 с); BATCH=READ=100, ROLLOUT_WAIT=30000 или
// переопределение трассы. Часовые значения только из const машины (machine:38-40).
//
// Упрощения представления (без изменения семантики):
//  - списки «без повторов» — множества (сама форма: «Sets are lists without repeats»);
//  - held — множество {v, r}; target — множество {v, c};
//  - answer: r.voters и r.members заменены одним признаком memOK (машина их использует только
//    в сравнении same_set(r.voters, input.voters) && r.members == input.members — переходы -3, -4);
//  - r.commit и адрес лидера не меняют состояние машины (только io read_commit): не храним;
//  - io send_status/read_commit исполняет окружение; адрес лидера/голосующего не моделируется.
// Что НЕ моделируется: реальные чтения (кроме очереди событий), CEL как язык (пересказ руками),
// барьер P/02.4 N1.9 вне машины, порядок чтений внутри одной пачки на сервере. Времени внутри
// одного момента — только порядок env: «read_expired; tick; wait_expired; потом внешние».
module rolloutpoll {
  // ----- параметры -----
  const SELF: str
  const VOTERS: Set[str]
  const LAST: bool
  const ALLOW_DOWN: bool
  const WAIT: int        // ROLLOUT_WAIT, сотые (machine:40)
  const MAX_K: int       // граница модели по батчам
  const MUT: int         // 0 — нет
  pure val BATCH = 100   // machine:38
  pure val READ = 100    // machine:39
  pure val NULLS = "@null"
  const TRACK_DID: bool  // трассировка did (для трасс); в проверках — false

  type Reply = {
    some: bool,    // false — null (соединение отказано)
    st: str,       // Leader|Follower|Candidate|Shutdown|Door
    lid: str,      // leader_id
    applied: int,
    memOK: bool,   // r.voters ≈ input.voters и r.members == input.members
  }
  type Held = { v: str, r: Reply }
  type Tgt  = { v: str, c: int }
  type Rd   = { n: int, who: Set[str] }
  type Did  = { name: str, k: int, n: int, who: Set[str], word: str }
  type St = {
    mst: str,
    k: int,
    leaderId: str,
    selfReplied: bool,
    leaderless: bool,
    replied: Set[str],
    held: Set[Held],
    alive: Set[str],
    need: Set[str],
    target: Set[Tgt],
    reads: Set[Rd],
    nextRead: int,
    readDone: bool,
    resultCode: int,
    resultWord: str,
    // Таймеры и время (машина: timers:)
    now: int,
    nextTickAt: int,
    readDl: Set[{n: int, at: int}],
    waitAt: int,
    // Контроль (не часть машины)
    did: List[Did],
    lastReplyK: str -> int,     // батч последнего ответа по голосующему
    lastLive: str -> bool,      // живой ли последний учтённый ответ
    readsInBatch: int,          // чтений целей в батче
    lateCommitApplied: bool,    // поздний commit изменил цели (контроль)
  }
  var st: St

  pure def isLive(rr: Reply, ll: bool, lid: str): bool =
    not(ll) and rr.some and Set("Leader", "Follower").contains(rr.st) and rr.lid == lid

  pure def didT(rec: Did, flag: bool, ds: List[Did]): List[Did] = if (flag) ds.append(rec) else ds

  pure def recD(name: str, k: int, n: int, who: Set[str], word: str): Did =
    { name: name, k: k, n: n, who: who, word: word }

  // Действия машины ------------------------------------------------------------
  pure def closeBatch(s: St): St = s.with("leaderless", s.leaderless or not(s.selfReplied))
    .with("target", s.target.filter(t => s.selfReplied and s.replied.contains(t.v)))
    .with("need", s.need.filter(u => s.selfReplied and s.replied.contains(u)))
    .with("alive", s.alive.filter(u => s.selfReplied and s.replied.contains(u)))
    .with("reads", s.reads.map(x => { n: x.n, who: x.who.filter(u => s.selfReplied and s.replied.contains(u)) }))
    .with("held", Set())

  pure def breakAll(s: St, self: str): St = s.with("leaderless", true).with("selfReplied", true)
    .with("target", Set()).with("need", Set()).with("alive", Set())
    .with("reads", s.reads.map(x => { n: x.n, who: Set() }))
    .with("replied", s.replied.union(Set(self)).union(s.held.map(h => h.v)))
    .with("held", Set())

  pure def setLeader(s: St, r: Reply): St = s.with("leaderId", r.lid).with("selfReplied", true)

  pure def hold(s: St, v: str, r: Reply, ek: int): St =
    s.with("held", s.held.union(Set({ v: v, r: r }))).with("lastReplyK", s.lastReplyK.put(v, ek))

  // answer(v, r): live — цель или учёт, иначе обрыв своего ответа; значения от состояния входа.
  pure def answer(s: St, v: str, r: Reply, mut: int): St =
    val live = (mut == 1 and r.some) or isLive(r, s.leaderless, s.leaderId)
    val hasT = s.target.exists(t => t.v == v)
    val hasR = s.reads.exists(x => x.who.contains(v))
    val inNeed = s.need.contains(v)
    val aliveByTarget = s.target.exists(t => t.v == v and r.applied >= t.c)
    s.with("target", if (live) s.target else s.target.filter(t => t.v != v))
     .with("need", if (live) (if (not(hasT) and not(hasR) and not(inNeed)) s.need.union(Set(v)) else s.need) else s.need.exclude(Set(v)))
     .with("alive", if (live) (if (aliveByTarget and not(s.alive.contains(v))) s.alive.union(Set(v)) else s.alive) else s.alive.exclude(Set(v)))
     .with("reads", if (live) s.reads else s.reads.map(x => { n: x.n, who: x.who.exclude(Set(v)) }))
     .with("replied", s.replied.union(Set(v)))

  pure def liveH(h: Held, lid: str, mut: int): bool =
    (mut == 1 and h.r.some) or (h.r.some and Set("Leader", "Follower").contains(h.r.st) and h.r.lid == lid)

  pure def answerHeld(s: St, mut: int): St =
    val lv = s.held.filter(h => liveH(h, s.leaderId, mut))
    s.with("target", s.target.filter(t => not(s.held.exists(h => h.v == t.v and not(liveH(h, s.leaderId, mut))))))
     .with("need", s.need.union(lv.filter(h => not(s.target.exists(t => t.v == h.v)) and not(s.reads.exists(x => x.who.contains(h.v))) and not(s.need.contains(h.v))).map(h => h.v)))
     .with("alive", s.alive.union(lv.filter(h => s.target.exists(t => t.v == h.v and h.r.applied >= t.c) and not(s.alive.contains(h.v))).map(h => h.v)))
     .with("reads", s.reads.map(x => { n: x.n, who: x.who.filter(u => not(s.held.exists(h => h.v == u and not(liveH(h, s.leaderId, mut))))) }))
     .with("replied", s.replied.union(s.held.map(h => h.v)))
     .with("lastLive", s.held.fold(s.lastLive, (acc, h) => acc.put(h.v, h.r.some and Set("Leader", "Follower").contains(h.r.st) and h.r.lid == s.leaderId)))
     .with("held", Set())

  // read_commit: цели запрашивает окружение; читается при «нужно ещё и чтения этого батча не было» (-9/-5).
  pure def readCommit(s: St, td: bool): St =
    val who = s.need
    val nn = s.nextRead
    s.with("reads", s.reads.union(Set({ n: nn, who: who })))
     .with("nextRead", s.nextRead + 1)
     .with("need", Set())
     .with("readDone", true)
     .with("readDl", s.readDl.union(Set({ n: nn, at: s.now + READ })))
     .with("readsInBatch", s.readsInBatch + 1)
     .with("did", didT(recD("read_commit", -1, nn, who, ""), td, s.did))

  pure def setTargets(s: St, n: int, c: int): St =
    val who = s.reads.filter(x => x.n == n).fold(Set(), (acc, x) => acc.union(x.who))
    s.with("target", s.target.union(who.map(v => { v: v, c: c })))
     .with("reads", s.reads.filter(x => x.n != n))

  pure def dropRead(s: St, n: int): St = s.with("reads", s.reads.filter(x => x.n != n))

  pure def refuse(s: St, code: int, word: str, td: bool): St =
    s.with("mst", "refused").with("resultCode", code).with("resultWord", word)
     .with("did", didT(recD("refuse", -1, code, Set(), word), td, s.did))

  pure def passE(s: St, td: bool): St =
    s.with("mst", "passed").with("did", didT(recD("pass", -1, -1, Set(), ""), td, s.did))

  pure def newBatch(s: St, k: int): St =
    s.with("k", k).with("leaderId", NULLS).with("selfReplied", false)
     .with("leaderless", false).with("readDone", false).with("replied", Set())
     .with("held", Set()).with("alive", Set()).with("need", Set()).with("readsInBatch", 0)

  // Судья tick-2 (machine:152; ≤2 голосующих — quorum+1, 2/2+2=3 > 2 — два без -allow-downtime не проходят).
  pure def judge(s: St, voters: Set[str], self: str, last: bool, mut: int): bool =
    if (last and voters.size() > 2)
      voters.forall(v => v == self or s.alive.contains(v))
    else
      s.alive.size() >= voters.size() / 2 + (if (mut == 5) 1 else 2)

  // tick(k)
  pure def onTick(s0: St, k: int, voters: Set[str], self: str, last: bool, allow: bool, td: bool, mut: int): St =
    val s = s0.with("did", didT(recD("tick", k, -1, Set(), ""), td, s0.did)).with("nextTickAt", s0.nextTickAt + BATCH)
    // tick-5
    if (allow and voters.size() <= 2) passE(s, td)
    else {
      // tick-1: k > 0 — close_batch
      val s1 = if (k > 0) closeBatch(s) else s
      // tick-2
      if (k > 0 and judge(s1, voters, self, last, mut)) passE(s1, td)
      else {
        // tick-3
        val s2 = if (k > 0 and s1.need.size() > 0 and not(s1.readDone)) readCommit(s1, td) else s1
        // tick-4
        val s3 = newBatch(s2, k).with("did", didT(recD("send_status", k, -1, Set(), ""), td, s2.did))
        s3
      }
    }

  // read_expired(n)
  pure def onReadExpired(s0: St, n: int, td: bool, mut: int): St =
    val s = s0.with("readDl", s0.readDl.filter(x => x.n != n))
             .with("did", didT(recD("read_expired", -1, n, Set(), ""), td, s0.did))
    if (mut == 3) s
    else if (s.reads.exists(x => x.n == n)) dropRead(s, n) else s

  // wait_expired
  pure def onWaitExpired(s0: St, voters: Set[str], last: bool, td: bool): St =
    val s = s0.with("did", didT(recD("wait_expired", -1, -1, Set(), ""), td, s0.did)).with("waitAt", -1)
    if (not(last) or voters.size() <= 2) refuse(s, 2, "not enough live voters", td)
    else refuse(s, 2, "-last: voters not live", td)

  // self_status
  pure def onSelf(s00: St, ek: int, r: Reply, voters: Set[str], self: str, last: bool, td: bool, mut: int): St =
    val s0 = s00.with("did", didT(recD("self", ek, -1, Set(), ""), td, s00.did))
    // -1
    if (mut != 2 and ek != s0.k) s0
    // -2
    else if (not(r.some)) breakAll(s0, self)
    // -3
    else if (not(r.memOK)) refuse(s0, 2, "voters changed", td)
    // -4
    else if (r.lid != "" and s0.held.exists(h => h.v == r.lid and h.r.some and not(h.r.memOK))) refuse(s0, 2, "voters changed", td)
    // -5
    else if (last and (r.st != "Leader" or r.lid != self)) refuse(s0, 2, "-last: not the leader", td)
    // -6
    else if (not(last) and r.st == "Leader" and voters.size() > 1) refuse(s0, 2, "leader goes last", td)
    // -7
    else if (r.lid == "") breakAll(s0, self)
    else {
      // -8
      val s1 = setLeader(s0, r).with("lastReplyK", s0.lastReplyK.put(self, ek)).with("lastLive", s0.lastLive.put(self, isLive(r, false, r.lid)))
      val s2 = answer(s1, self, r, mut)
      val s3 = answerHeld(s2, mut)
      // -9
      if (s3.replied.size() == voters.size() and s3.need.size() > 0 and not(s3.readDone)) readCommit(s3, td) else s3
    }

  // status
  pure def onStatus(s00: St, ek: int, v: str, r: Reply, voters: Set[str], td: bool, mut: int): St =
    val s0 = s00.with("did", didT(recD("status", ek, -1, Set(v), ""), td, s00.did))
    // -1 (устаревший батч)
    if (mut != 2 and ek != s0.k) s0
    // -2
    else if (not(s0.selfReplied)) hold(s0, v, r, ek)
    // -3
    else if (not(s0.leaderless) and v == s0.leaderId and r.some and not(r.memOK)) refuse(s0, 2, "voters changed", td)
    else {
      // -4
      val s1 = answer(s0, v, r, mut).with("lastReplyK", s0.lastReplyK.put(v, ek)).with("lastLive", s0.lastLive.put(v, isLive(r, s0.leaderless, s0.leaderId)))
      // -5
      if (s1.replied.size() == voters.size() and s1.need.size() > 0 and not(s1.readDone)) readCommit(s1, td) else s1
    }

  // commit(n, c); c = -1 — null
  pure def onCommit(s00: St, n: int, c: int, td: bool, mut: int, now: int): St =
    val s = s00.with("did", didT(recD("commit", -1, n, Set(), ""), td, s00.did))
    val late = n < s00.nextRead and not(s00.readDl.exists(x => x.n == n))
    // -1
    if (not(s.reads.exists(x => x.n == n))) s
    // -2
    else if (c < 0) dropRead(s, n)
    else {
      // -3
      val s1 = setTargets(s, n, c)
      if (late) s1.with("lateCommitApplied", true) else s1
    }

  // Планировщик таймеров: один шаг (machine:env порядок одного момента) -------------
  pure def dueReadExpiry(s: St): Set[int] = s.readDl.filter(x => x.at <= s.now).map(x => x.n)

  pure def nextDue(s: St, mut: int): int =
    val waits = if (s.waitAt >= 0 and mut != 4) Set(s.waitAt) else Set()
    s.readDl.map(x => x.at).union(Set(s.nextTickAt)).union(waits).fold(2147483647, (a, b) => if (b < a) b else a)

  // Один таймерный шаг: время идёт в момент ближайшего срока, порядок одного момента — machine:env.
  pure def fireOne(s0: St, t: int, voters: Set[str], self: str, last: bool, allow: bool, td: bool, mut: int): St =
    if (s0.mst != "polling") s0
    else if (nextDue(s0, mut) > t) s0
    else {
      val s = s0.with("now", nextDue(s0, mut))
      val due = dueReadExpiry(s)
      if (due.size() > 0) {
        val n = due.fold(1000000, (a, b) => if (b < a) b else a)
        onReadExpired(s, n, td, mut)
      }
      else if (s.now >= s.nextTickAt) {
        val k = s.nextTickAt / BATCH
        onTick(s, k, voters, self, last, allow, td, mut)
      }
      else if (s.waitAt >= 0 and s.now >= s.waitAt and mut != 4) onWaitExpired(s, voters, last, td)
      else s
    }

  pure def timersDue(s: St, mut: int): bool = s.mst == "polling" and nextDue(s, mut) <= s.now

  pure def fireAll(s: St, t: int, voters: Set[str], self: str, last: bool, allow: bool, td: bool, mut: int): St =
    1.to(40).fold(s, (acc, i) => fireOne(acc, t, voters, self, last, allow, td, mut)).with("now", t)

  // ----- инициализация -----
  pure def mkInit(voters: Set[str], wait: int): St = {
    mst: "polling", k: -1, leaderId: NULLS, selfReplied: false, leaderless: false,
    replied: Set(), held: Set(), alive: Set(), need: Set(), target: Set(), reads: Set(),
    nextRead: 1, readDone: false, resultCode: 0, resultWord: "",
    now: 0, nextTickAt: 0, readDl: Set(), waitAt: wait,
    did: List(), lastReplyK: voters.mapBy(v => -9), lastLive: voters.mapBy(v => false),
    readsInBatch: 0, lateCommitApplied: false,
  }

  action init = st' = mkInit(VOTERS, WAIT)

  // Конечные множества окружения для model checking.
  pure val Commits = Set(0, 1, 2)
  pure val Applied = Set(0, 1, 2)
  pure def repliesFor(v: str): Set[Reply] =
    Applied.map(a => { some: true, st: if (v == "b") "Leader" else "Follower", lid: "b", applied: a, memOK: true })
      .union(Set({ some: false, st: "Follower", lid: "b", applied: 0, memOK: true },
                 { some: true, st: "Candidate", lid: "", applied: 0, memOK: true },
                 { some: true, st: "Follower", lid: "", applied: 0, memOK: true },
                 { some: true, st: "Follower", lid: "b", applied: 1, memOK: false }))

  // Ответы приходят не более раза (machine env). answered — по ключам (батч, голосующий).
  var answered: Set[(int, str)]
  var commited: Set[int]

  action advance = all {
    st.mst == "polling",
    not(timersDue(st, MUT)),
    st.now <= MAX_K * BATCH,
    nondet d = Set(1, 10, 50, BATCH, 2 * BATCH).oneOf()
    val nd = st.now + d
    val maxT = nextDue(st, MUT)
    st' = st.with("now", if (nd <= maxT) nd else maxT),
    answered' = answered, commited' = commited,
  }

  action fireTimer = all {
    timersDue(st, MUT),
    st' = fireOne(st, st.now, VOTERS, SELF, LAST, ALLOW_DOWN, TRACK_DID, MUT),
    answered' = answered, commited' = commited,
  }

  action selfEv = {
    val ks = Set(st.k, st.k - 1).filter(x => x >= 0)
    all {
      st.mst == "polling",
      not(timersDue(st, MUT)),
      ks.size() > 0,
      nondet k = ks.oneOf()
      nondet r = repliesFor(SELF).oneOf()
      all {
        not(answered.contains((k, SELF))),
        answered' = answered.union(Set((k, SELF))),
        st' = onSelf(st, k, r, VOTERS, SELF, LAST, TRACK_DID, MUT),
        commited' = commited,
      },
    }
  }

  action statusEv = {
    val ks = Set(st.k, st.k - 1).filter(x => x >= 0)
    all {
      st.mst == "polling",
      not(timersDue(st, MUT)),
      ks.size() > 0,
      nondet k = ks.oneOf()
      nondet v = VOTERS.exclude(Set(SELF)).oneOf()
      nondet r = repliesFor(v).oneOf()
      all {
        not(answered.contains((k, v))),
        answered' = answered.union(Set((k, v))),
        st' = onStatus(st, k, v, r, VOTERS, TRACK_DID, MUT),
        commited' = commited,
      },
    }
  }

  action commitEv = all {
    st.mst == "polling",
    not(timersDue(st, MUT)),
    st.nextRead > 1,
    nondet n = 1.to(st.nextRead - 1).oneOf()
    nondet c = Commits.union(Set(-1)).oneOf()
    all {
      not(commited.contains(n)),
      commited' = commited.union(Set(n)),
      st' = onCommit(st, n, c, TRACK_DID, MUT, st.now),
      answered' = answered,
    },
  }

  action stutter = all { st' = st, answered' = answered, commited' = commited }

  // В проверках момента инициализации answered/commited
  action initAll = all { init, answered' = Set(), commited' = Set() }

  action stepAll = any { advance, fireTimer, selfEv, statusEv, commitEv, all { st.mst != "polling", stutter } }

  // ----- инварианты машины (machine: invariants) -----
  val live_has_target = st.alive.forall(v => st.target.exists(t => t.v == v))
  val live_replied = st.alive.forall(v => st.replied.contains(v))
  val leaderless_none_live = not(st.leaderless) or st.alive.size() == 0
  val need_has_no_target = st.need.forall(v => not(st.target.exists(t => t.v == v)))
  val read_has_no_target = st.reads.forall(x => x.who.forall(v => not(st.target.exists(t => t.v == v))))
  val one_target = st.target.forall(t => st.target.filter(u => u.v == t.v).size() == 1)
  val voters_only = st.replied.forall(v => VOTERS.contains(v)) and st.target.forall(t => VOTERS.contains(t.v))
  val held_only_before_self = if (st.selfReplied) st.held.size() == 0 else (st.alive.size() == 0 and st.replied.size() == 0)
  val inv_machine = and {
    live_has_target, live_replied, leaderless_none_live, need_has_no_target,
    read_has_no_target, one_target, voters_only, held_only_before_self,
  }

  // Сроки: опрос закрывается не позже ROLLOUT_WAIT.
  val inv_pollBounded = st.mst != "polling" or st.waitAt < 0 or st.now <= st.waitAt
  // Живой — только по ответу этого батча.
  val inv_lastAnswerThisBatch = st.alive.forall(v => st.lastReplyK.get(v) == st.k)
  // Живой — только живой ответ.
  val inv_aliveReplyLive = st.alive.forall(v => st.lastLive.get(v))
  // Не более одного чтения целей на батч (machine:read_done).
  val inv_oneReadPerBatch = st.readsInBatch <= 1
  // Поздний commit игнорируется (commit-1 после read_expired).
  val inv_lateCommitIgnored = not(st.lateCommitApplied)

  // Судья tick-2: pass только при живых ≥ quorum+1 (LAST=false, >2 голосующих).
  val inv_passQuorum = st.mst != "passed" or st.alive.size() >= VOTERS.size() / 2 + 2

  // Свидетели достижимости.
  val notPassed = st.mst != "passed"
  val notRefused = st.mst != "refused"
  val notBreakAll = not(st.leaderless)
  val notAlive3 = st.alive.size() < VOTERS.size()
  val notExpired = st.waitAt >= 0
}

module rp_3f { import rolloutpoll(SELF="a", VOTERS=Set("a","b","c"), LAST=false, ALLOW_DOWN=false, WAIT=400, MAX_K=6, MUT=0, TRACK_DID=false).* }
module rp_m1 { import rolloutpoll(SELF="a", VOTERS=Set("a","b","c"), LAST=false, ALLOW_DOWN=false, WAIT=400, MAX_K=6, MUT=1, TRACK_DID=false).* }
module rp_m2 { import rolloutpoll(SELF="a", VOTERS=Set("a","b","c"), LAST=false, ALLOW_DOWN=false, WAIT=400, MAX_K=6, MUT=2, TRACK_DID=false).* }
module rp_m3 { import rolloutpoll(SELF="a", VOTERS=Set("a","b","c"), LAST=false, ALLOW_DOWN=false, WAIT=400, MAX_K=6, MUT=3, TRACK_DID=false).* }
module rp_m4 { import rolloutpoll(SELF="a", VOTERS=Set("a","b","c"), LAST=false, ALLOW_DOWN=false, WAIT=300, MAX_K=6, MUT=4, TRACK_DID=false).* }
module rp_m5 { import rolloutpoll(SELF="a", VOTERS=Set("a","b","c"), LAST=false, ALLOW_DOWN=false, WAIT=400, MAX_K=6, MUT=5, TRACK_DID=false).* }
