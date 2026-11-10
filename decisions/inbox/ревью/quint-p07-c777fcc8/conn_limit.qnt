// C10 (held /changes occupy the browser's connections to the origin).
// Anchors: nr:56 one held /changes wait=15 per instance; nr:187 several instances; nr:111 "20 s for each attempt"; nr:334; rc:8 CHANGES_SUBSCRIBERS_MAX (a server limit);
//   06.5:255 feed lane. fwd:67 refuses chunked framing by the HTTP/1.x form; the HTTP version of the browser's connection is not named by the norms.
// NT tabs/instances each hold a feed request up to WAIT seconds and re-issue it after GAP seconds. L: connections of the browser to one origin; a browser parameter, not a norm.
// With HTTP/2 the limit does not bind: L > NT models it. PICK: fifo or any: the order in which the browser hands out free connections is not normed.
// TIMER: call = the 20 s run from the call; start = from the moment the connection is obtained (proposal C10, not observable through fetch; an assumption).
// MAX_HELD: at most so many tabs hold (proposal C10; -1 = the text). DUR: the answer time of the write once started.
module conn_core {
  const NT: int
  const L: int
  const PICK: str
  const TIMER: str
  const MAX_HELD: int
  const DUR: int
  const CALLS: Set[int]
  const OFFSETS: Set[int]
  const WAIT: int
  const GAP: int
  const DEADLINE: int

  type S = {t: int, heldEnd: int -> int, reissueAt: int -> int, w: str, callAt: int, startAt: int, endAt: int, timedOutReal: bool}
  var s: S

  val TABS = 0.to(NT - 1)
  val HOLDERS = if (MAX_HELD >= 0) TABS.filter(x => x < MAX_HELD) else TABS

  action init = {
    nondet off = TABS.setOfMaps(OFFSETS).oneOf()
    nondet call = CALLS.oneOf()
    s' = {t: 0, heldEnd: TABS.mapBy(p => if (p.in(HOLDERS)) off.get(p) else -1), reissueAt: TABS.mapBy(_ => -1),
          w: "queued", callAt: call, startAt: -1, endAt: -1, timedOutReal: false}
  }

  def slotsUsed: int = TABS.filter(p => s.heldEnd.get(p) >= s.t).size() + (if (s.w == "run") 1 else 0)
  def free: bool = slotsUsed < L

  action holdReturn(p: int): bool = all {
    s.heldEnd.get(p) == s.t,
    s' = s.with("heldEnd", s.heldEnd.set(p, -1)).with("reissueAt", s.reissueAt.set(p, s.t + GAP))
  }

  action reissue(p: int): bool = all {
    s.reissueAt.get(p) >= 0, s.reissueAt.get(p) <= s.t, free,
    PICK == "any" or s.w != "queued" or s.reissueAt.get(p) < s.callAt,
    s' = s.with("reissueAt", s.reissueAt.set(p, -1)).with("heldEnd", s.heldEnd.set(p, s.t + WAIT))
  }

  action startWrite = all {
    s.w == "queued", s.t >= s.callAt, free,
    s' = s.with("w", "run").with("startAt", s.t).with("endAt", s.t + DUR)
  }

  action finishWrite = all { s.w == "run", s.t == s.endAt, s' = s.with("w", "done") }

  def timerFrom: int = if (TIMER == "call") s.callAt else s.startAt

  action timeoutWrite = all {
    if (TIMER == "call") (s.w == "queued" or s.w == "run") else s.w == "run",
    s.t >= s.callAt,
    s.t - timerFrom >= DEADLINE,
    s' = s.with("w", "timeout").with("timedOutReal", DUR >= DEADLINE)
  }

  def nextEvent: Set[int] =
    TABS.map(p => s.heldEnd.get(p)).union(TABS.map(p => s.reissueAt.get(p))).union(Set(s.callAt, s.endAt, s.callAt + DEADLINE, if (s.startAt >= 0) s.startAt + DEADLINE else -1, 40)).filter(x => x > s.t)

  action tick = all {
    s.t < 40,
    TABS.forall(p => s.heldEnd.get(p) != s.t),
    s.w != "run" or s.t != s.endAt,
    not(free and s.w == "queued" and s.t >= s.callAt),
    val nt = nextEvent.fold(1000, (a, b) => if (b < a) b else a)
    s' = s.with("t", nt)
  }

  action stutter = s' = s
  action step = any {
    { nondet p = TABS.oneOf() holdReturn(p) },
    { nondet p = TABS.oneOf() reissue(p) },
    startWrite, finishWrite, timeoutWrite, tick, stutter,
  }

  val inv_no_false_timeout = (s.w == "timeout") implies s.timedOutReal
  val inv_queue_le_wait = (s.w == "queued") implies (s.t - s.callAt <= WAIT)
  val inv_start_at_once = (s.w == "run" or s.w == "done") implies s.startAt == s.callAt
  val wit_waited_full = not(s.w == "run" and s.startAt - s.callAt >= 14)
  val wit_starved = not(s.w == "queued" and s.t - s.callAt >= DEADLINE)
  val wit_write_done = not(s.w == "done")
  val wit_done_after_queue = not(s.w == "done" and s.startAt - s.callAt >= 14)
}
