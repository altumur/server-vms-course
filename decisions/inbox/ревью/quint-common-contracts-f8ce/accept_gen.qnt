// Model of Platform/common/contracts/accept.md (pin f8ce0f52) generations: step 7 writes, the mark as the boundary, crash between writes.
// LITERAL: step 7 removes only rev-2 and objects above rev; otherwise «keep» (:62) removes everything older than the last two.
module accept_gen {
  const LITERAL: bool
  const MUT_MARK_FIRST: bool
  type S = { objs: Set[int], mark: int, phase: int, rev: int, rpc: int, rrev: int, falseSilent: int, n: int, cleaned: bool }
  var s: S
  action init = s' = { objs: Set(), mark: 0, phase: 0, rev: 0, rpc: 0, rrev: 0, falseSilent: 0, n: 0, cleaned: false }

  action start = all {
    s.phase == 0, s.n < 5,
    if (MUT_MARK_FIRST) s' = s.with("mark", s.mark + 1).with("rev", s.mark + 1).with("phase", 1).with("n", s.n + 1).with("cleaned", false)
    else s' = s.with("objs", s.objs.union(Set(s.mark + 1))).with("rev", s.mark + 1).with("phase", 1).with("n", s.n + 1).with("cleaned", false)
  }
  action writeRest = all {
    s.phase == 1,
    if (MUT_MARK_FIRST) s' = s.with("objs", s.objs.union(Set(s.rev))).with("phase", 2)
    else s' = s.with("mark", s.rev).with("phase", 2)
  }
  action clean = all {
    s.phase == 2,
    s' = s.with("phase", 0).with("cleaned", true).with("objs",
      if (LITERAL) s.objs.filter(r => r != s.rev - 2 and r <= s.rev)
      else s.objs.filter(r => r >= s.rev - 1 and r <= s.rev))
  }
  action crash = all { s.phase != 0, s' = s.with("phase", 0).with("cleaned", false) }
  action readMark = all { s.rpc == 0, s.mark > 0, s' = s.with("rpc", 1).with("rrev", s.mark) }
  action readObj = all {
    s.rpc == 1,
    s' = s.with("rpc", 0).with("falseSilent", if (s.objs.contains(s.rrev)) s.falseSilent else s.falseSilent + 1)
  }
  action step = any { start, writeRest, clean, crash, readMark, readObj }

  // The generation named by the mark exists whole.
  val markHasObject: bool = s.mark == 0 or s.objs.contains(s.mark)
  // After a completed cleanup no generation older than the last two survives.
  val noOldLeak: bool = not(s.cleaned) or s.objs.forall(r => r >= s.mark - 1)
  val noFalseSilent: bool = s.falseSilent == 0
}
module acc_keep { import accept_gen(LITERAL = false, MUT_MARK_FIRST = false).* }
module acc_literal { import accept_gen(LITERAL = true, MUT_MARK_FIRST = false).* }
module acc_mut_markfirst { import accept_gen(LITERAL = false, MUT_MARK_FIRST = true).* }
