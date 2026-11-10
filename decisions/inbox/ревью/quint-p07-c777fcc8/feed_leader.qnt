// C10 proposal: "not more than one held feed per origin between the tabs". This introduces a leader between tabs: a browser analogue of the daemon leadership
// (nr:255: the lesson has no process; the module has no leadership rule). Coordination is outside the text; localStorage is named only by cm:178 for favourites.
// A tab claims by read-then-write of a shared record (read and write are separate events: localStorage has no compare-and-set) or, ATOMIC, by one step (a Web Locks style
// primitive; a browser parameter). LEASE: an expired claim of a closed tab can be taken over by another tab; no lease = the claim stays with a closed tab.
// Tabs are 0..NT-1; the shared record: claim tab id (-1 = free).
module leader_core {
  const NT: int
  const ATOMIC: bool
  const LEASE: bool
  type S = {claim: int, read: int -> int, holder: int -> bool, alive: int -> bool, closedHolder: bool}
  var s: S
  val T = 0.to(NT - 1)
  action init = s' = {claim: -1, read: T.mapBy(_ => -2), holder: T.mapBy(_ => false), alive: T.mapBy(_ => true), closedHolder: false}
  action readClaim(p: int): bool = all { not(ATOMIC), s.alive.get(p), not(s.holder.get(p)), s' = s.with("read", s.read.set(p, s.claim)) }
  action writeClaim(p: int): bool = all {
    not(ATOMIC), s.alive.get(p), s.read.get(p) == -1, not(s.holder.get(p)),
    s' = s.with("claim", p).with("holder", s.holder.set(p, true)).with("read", s.read.set(p, -2))
  }
  action atomicClaim(p: int): bool = all {
    ATOMIC, s.alive.get(p), s.claim == -1, not(s.holder.get(p)),
    s' = s.with("claim", p).with("holder", s.holder.set(p, true))
  }
  action closeTab(p: int): bool = all {
    s.alive.get(p), s.holder.get(p),
    s' = s.with("alive", s.alive.set(p, false)).with("holder", s.holder.set(p, false)).with("closedHolder", true)
  }
  action leaseExpire = all { LEASE, s.claim != -1, s.alive.get(s.claim) == false, s' = s.with("claim", -1) }
  action stutter = s' = s
  action step = any {
    { nondet p = T.oneOf() readClaim(p) },
    { nondet p = T.oneOf() writeClaim(p) },
    { nondet p = T.oneOf() atomicClaim(p) },
    { nondet p = T.oneOf() closeTab(p) },
    leaseExpire, stutter,
  }
  val holders = T.filter(p => s.holder.get(p)).size()
  val inv_one_holder = holders <= 1
  val wit_two_holders = not(holders == 2)
  val wit_no_holder_after_close = not(s.closedHolder and holders == 0 and T.exists(p => s.alive.get(p)))
  val wit_takeover = not(s.closedHolder and holders == 1)
  val inv_takeover_impossible = not(s.closedHolder and holders == 1)
}
