// Model of Platform/common/contracts/tombstone.md (pin f8ce0f52) with mirror copies (P/05 N1.1).
// ANY_SOURCE: whether a neighbour that holds a copy may mirror it onward («every local body»; the text is read both ways).
module tombstone {
  const ANY_SOURCE: bool
  const MUT_ACK_WITHOUT_404: bool
  pure val PEERS: Set[str] = Set("P1", "P2")
  type T = { on: bool, written: int, acked: Set[str], old: bool }
  type S = { d: int, stamp: int, copy: str -> int, tomb: T, silent: Set[str], removedAt: int, removals: int }
  var s: S
  action init = s' = { d: 0, stamp: 0, copy: PEERS.mapBy(p => 0), tomb: { on: false, written: 0, acked: Set(), old: false }, silent: Set(), removedAt: 0, removals: 0 }

  action writeBody = all {
    s.stamp < 5,
    s' = s.with("d", s.stamp + 1).with("stamp", s.stamp + 1).with("tomb", { on: false, written: 0, acked: Set(), old: false }).with("removedAt", 0)
  }
  action mirror(p: str): bool = all { s.d > s.copy.get(p), not(s.silent.contains(p)), s' = s.with("copy", s.copy.set(p, s.d)) }
  action mirrorOn(p: str, q: str): bool = all {
    ANY_SOURCE, p != q, s.copy.get(p) > s.copy.get(q), not(s.silent.contains(p)), not(s.silent.contains(q)),
    s' = s.with("copy", s.copy.set(q, s.copy.get(p)))
  }
  action del = all {
    s.d > 0, not(s.tomb.on), s.stamp < 5,
    s' = s.with("d", 0).with("stamp", s.stamp + 1).with("tomb", { on: true, written: s.stamp + 1, acked: Set(), old: false })
  }
  action drop(p: str): bool = all {
    s.tomb.on, not(s.silent.contains(p)), s.copy.get(p) > 0, s.copy.get(p) < s.tomb.written,
    s' = s.with("copy", s.copy.set(p, 0))
  }
  action ack(p: str): bool = all {
    s.tomb.on, not(s.tomb.acked.contains(p)), not(s.silent.contains(p)), or { MUT_ACK_WITHOUT_404, s.copy.get(p) == 0 },
    s' = s.with("tomb", s.tomb.with("acked", s.tomb.acked.union(Set(p))))
  }
  action age = all { s.tomb.on, not(s.tomb.old), s' = s.with("tomb", s.tomb.with("old", true)) }
  action remove = all {
    s.tomb.on, s.tomb.old, PEERS.subseteq(s.tomb.acked),
    s' = s.with("removedAt", s.tomb.written).with("removals", s.removals + 1).with("tomb", { on: false, written: 0, acked: Set(), old: false })
  }
  action goSilent(p: str): bool = all { not(s.silent.contains(p)), s' = s.with("silent", s.silent.union(Set(p))) }
  action back(p: str): bool = all { s.silent.contains(p), s' = s.with("silent", s.silent.exclude(Set(p))) }
  action step = any {
    writeBody, del, age, remove,
    nondet p = oneOf(PEERS) any { mirror(p), drop(p), ack(p), goSilent(p), back(p), nondet q = oneOf(PEERS) mirrorOn(p, q) },
  }

  // After a tombstone is removed and no newer write exists, no peer keeps a copy older than the deletion.
  val noResurrection: bool = s.removedAt == 0 or PEERS.forall(p => s.copy.get(p) == 0 or s.copy.get(p) > s.removedAt)
  // An acknowledged peer holds no copy older than the tombstone.
  val ackMeansGone: bool = not(s.tomb.on) or s.tomb.acked.forall(p => s.copy.get(p) == 0 or s.copy.get(p) >= s.tomb.written)
  val noRemoval: bool = s.removals == 0
  val notStuckWithSilent: bool = not(s.tomb.on and s.tomb.old and s.silent != Set() and s.tomb.acked != PEERS)
}
module ts_owner { import tombstone(ANY_SOURCE = false, MUT_ACK_WITHOUT_404 = false).* }
module ts_any { import tombstone(ANY_SOURCE = true, MUT_ACK_WITHOUT_404 = false).* }
module ts_mut_ack { import tombstone(ANY_SOURCE = false, MUT_ACK_WITHOUT_404 = true).* }
