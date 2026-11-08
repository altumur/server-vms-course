// Model of Platform/common/contracts/turn.md (pin f8ce0f52): take, renew, guard, term anchored at sending.
// Abstraction: one turn row, one guarded target, two claimants; integer per-process monotonic clocks.
module turn {
  const TERM: int
  const MAXT: int
  const DRIFT: bool
  const MUT_NO_GUARD: bool
  const MUT_NO_WAIT: bool
  const MUT_ANCHOR_REPLY: bool

  pure val HOLDERS: Set[str] = Set("A", "B")
  type Belief = { has: bool, ver: int, sentAt: int }
  type Seen = { ver: int, holder: str, at: int }
  type Req = { who: str, cas: int, sentAt: int, rel: bool }
  type Reply = { who: str, ver: int, sentAt: int }
  type Write = { who: str, guard: int }
  type Applied = { who: str, guard: int, atVer: int, holderAt: str }
  type S = {
    clock: str -> int, turnVer: int, turnHolder: str, belief: str -> Belief, seen: str -> Seen,
    reqs: Set[Req], replies: Set[Reply], writes: Set[Write], applied: Set[Applied], takeovers: int, refused: int
  }
  var s: S

  action init = s' = {
    clock: HOLDERS.mapBy(h => 0), turnVer: 0, turnHolder: "",
    belief: HOLDERS.mapBy(h => { has: false, ver: 0, sentAt: 0 }),
    seen: HOLDERS.mapBy(h => { ver: 0, holder: "", at: 0 }),
    reqs: Set(), replies: Set(), writes: Set(), applied: Set(), takeovers: 0, refused: 0
  }

  def valid(h: str): bool = s.belief.get(h).has and s.clock.get(h) - s.belief.get(h).sentAt < TERM

  action tick = all {
    s.clock.get("A") < MAXT,
    s' = s.with("clock", Map("A" -> (s.clock.get("A") + 1), "B" -> (s.clock.get("B") + (if (DRIFT) 2 else 1))))
  }
  action observe(h: str): bool = all {
    s.seen.get(h).ver != s.turnVer,
    s' = s.with("seen", s.seen.set(h, { ver: s.turnVer, holder: s.turnHolder, at: s.clock.get(h) }))
  }
  action claim(h: str): bool = {
    val q = s.seen.get(h)
    all {
      not(s.belief.get(h).has), s.reqs.size() < 3,
      or { q.holder == "", and { q.holder != h, or { MUT_NO_WAIT, s.clock.get(h) - q.at >= TERM } } },
      s' = s.with("reqs", s.reqs.union(Set({ who: h, cas: q.ver, sentAt: s.clock.get(h), rel: false })))
    }
  }
  action applyReq(r: Req): bool = all {
    s.reqs.contains(r),
    if (r.cas == s.turnVer)
      s' = s.with("reqs", s.reqs.exclude(Set(r))).with("turnVer", s.turnVer + 1)
            .with("turnHolder", if (r.rel) "" else r.who)
            .with("takeovers", if (not(r.rel) and s.turnHolder != "" and s.turnHolder != r.who) s.takeovers + 1 else s.takeovers)
            .with("replies", if (r.rel) s.replies else s.replies.union(Set({ who: r.who, ver: s.turnVer + 1, sentAt: r.sentAt })))
    else s' = s.with("reqs", s.reqs.exclude(Set(r)))
  }
  action confirm(p: Reply): bool = all {
    s.replies.contains(p),
    s' = s.with("replies", s.replies.exclude(Set(p)))
          .with("belief", if (p.ver > s.belief.get(p.who).ver)
                 s.belief.set(p.who, { has: true, ver: p.ver, sentAt: if (MUT_ANCHOR_REPLY) s.clock.get(p.who) else p.sentAt })
               else s.belief)
  }
  action loseReply(p: Reply): bool = all { s.replies.contains(p), s' = s.with("replies", s.replies.exclude(Set(p))) }
  action renew(h: str): bool = all {
    valid(h), s.reqs.size() < 3,
    s' = s.with("reqs", s.reqs.union(Set({ who: h, cas: s.belief.get(h).ver, sentAt: s.clock.get(h), rel: false })))
  }
  action release(h: str): bool = all {
    valid(h), s.reqs.size() < 3,
    s' = s.with("reqs", s.reqs.union(Set({ who: h, cas: s.belief.get(h).ver, sentAt: s.clock.get(h), rel: true })))
          .with("belief", s.belief.set(h, { has: false, ver: s.belief.get(h).ver, sentAt: 0 }))
  }
  action crash(h: str): bool = all {
    s.belief.get(h).has,
    s' = s.with("belief", s.belief.set(h, { has: false, ver: s.belief.get(h).ver, sentAt: 0 }))
          .with("seen", s.seen.set(h, { ver: -1, holder: "?", at: s.clock.get(h) }))
  }
  action write(h: str): bool = all {
    valid(h), s.writes.size() < 3,
    s' = s.with("writes", s.writes.union(Set({ who: h, guard: s.belief.get(h).ver })))
  }
  action deliver(w: Write): bool = all {
    s.writes.contains(w),
    if (MUT_NO_GUARD or w.guard == s.turnVer)
      s' = s.with("writes", s.writes.exclude(Set(w)))
            .with("applied", s.applied.union(Set({ who: w.who, guard: w.guard, atVer: s.turnVer, holderAt: s.turnHolder })))
    else s' = s.with("writes", s.writes.exclude(Set(w))).with("refused", s.refused + 1)
  }
  action step = any {
    tick,
    nondet h = oneOf(HOLDERS) any { observe(h), claim(h), renew(h), release(h), crash(h), write(h) },
    all { s.reqs != Set(), nondet r = oneOf(s.reqs) applyReq(r) },
    all { s.replies != Set(), nondet p = oneOf(s.replies) any { confirm(p), loseReply(p) } },
    all { s.writes != Set(), nondet w = oneOf(s.writes) deliver(w) },
  }

  // A write is applied only under the current version of the turn row.
  val fenced: bool = s.applied.forall(a => a.guard == a.atVer)
  // A write is applied only while the row names its writer.
  val onlyHolderWrites: bool = s.applied.forall(a => a.holderAt == a.who)
  // Two claimants do not both hold an unexpired confirmed term.
  val singleConfident: bool = not(valid("A") and valid("B"))

  // Reachability witnesses: a violation of the negation means the behaviour exists.
  val noTakeover: bool = s.takeovers == 0
  val noLateRefused: bool = s.refused == 0
  val noApplied: bool = s.applied == Set()
}

module turn_ok { import turn(TERM = 2, MAXT = 7, DRIFT = false, MUT_NO_GUARD = false, MUT_NO_WAIT = false, MUT_ANCHOR_REPLY = false).* }
module turn_drift { import turn(TERM = 2, MAXT = 7, DRIFT = true, MUT_NO_GUARD = false, MUT_NO_WAIT = false, MUT_ANCHOR_REPLY = false).* }
module turn_mut_noguard { import turn(TERM = 2, MAXT = 7, DRIFT = false, MUT_NO_GUARD = true, MUT_NO_WAIT = false, MUT_ANCHOR_REPLY = false).* }
module turn_mut_nowait { import turn(TERM = 2, MAXT = 7, DRIFT = false, MUT_NO_GUARD = false, MUT_NO_WAIT = true, MUT_ANCHOR_REPLY = false).* }
module turn_mut_anchor { import turn(TERM = 2, MAXT = 7, DRIFT = false, MUT_NO_GUARD = false, MUT_NO_WAIT = false, MUT_ANCHOR_REPLY = true).* }
