// C9 (storm after a restart of the console).
// Anchors: nr:57 "at most once a second after ... a disconnect"; reset -> the same load at once; nr:59 a dropped connection -> the next attempt after poll_s;
//   06.1:554 reset on restart; 06.5:255 a lane busy -> 503 busy, Retry-After: 1.
// NT tabs. The console restarts at second 0: every held /changes is cut at the same moment. The console is down for DOWN seconds.
// RECONN: the delay of the next feed attempt after a disconnect (poll_s by nr:59; 1 by the nr:57 reading; both run). An attempt that finds the console up gets a reset and loads at once.
// OFFSETS: the poll phases of the tabs (any; they do not influence the feed attempts, see inv_feed_burst_eq_nt).
// LANE: an implementation-chosen size of the common lane (06.5 Implementation decides), a parameter. STAGGER: a given spread of tab p (p*STAGGER), a deterministic stand-in for jitter.
// The burst counts loads started in one second, one load counted as one (its requests are in sequence).
module storm_core {
  const NT: int
  const RECONN: int
  const DOWN: int
  const STAGGER: int
  const PERIOD: int
  const LANE: int
  const OFFSETS: Set[int]

  var t: int
  var attemptAt: int -> int
  var pollAt: int -> int
  var loadedAt: int -> int
  var burst: int
  var maxBurst: int
  var feedBurst: int
  var maxBusy: int
  var firstUpTick: int

  val P = 0.to(NT - 1)

  action init = {
    nondet po = P.setOfMaps(OFFSETS).oneOf()
    all {
      t' = 0, pollAt' = po, attemptAt' = P.mapBy(p => RECONN + p * STAGGER), loadedAt' = P.mapBy(_ => -1),
      burst' = 0, maxBurst' = 0, feedBurst' = 0, maxBusy' = 0, firstUpTick' = -1,
    }
  }

  action tick = all {
    t < RECONN + DOWN + NT * STAGGER + PERIOD,
    val nt = t + 1
    val up = nt >= DOWN
    val fired = P.filter(p => attemptAt.get(p) == nt)
    val ok = if (up) fired else Set()
    val polls = P.filter(p => pollAt.get(p) == nt)
    val b = ok.union(polls).size()
    val busy = if (b > LANE) b - LANE else 0
    all {
      t' = nt,
      attemptAt' = P.mapBy(p => if (attemptAt.get(p) == nt and not(up)) nt + RECONN else attemptAt.get(p)),
      pollAt' = P.mapBy(p => if (pollAt.get(p) == nt) nt + PERIOD else pollAt.get(p)),
      loadedAt' = P.mapBy(p => if (p.in(ok) and loadedAt.get(p) < 0) nt else loadedAt.get(p)),
      burst' = b,
      maxBurst' = if (b > maxBurst) b else maxBurst,
      feedBurst' = if (ok.size() > feedBurst) ok.size() else feedBurst,
      maxBusy' = if (busy > maxBusy) busy else maxBusy,
      firstUpTick' = if (firstUpTick < 0 and ok.size() > 0) nt else firstUpTick,
    }
  }

  action stutter = all {
    t >= RECONN + DOWN + NT * STAGGER + PERIOD,
    t' = t, attemptAt' = attemptAt, pollAt' = pollAt, loadedAt' = loadedAt, burst' = burst, maxBurst' = maxBurst,
    feedBurst' = feedBurst, maxBusy' = maxBusy, firstUpTick' = firstUpTick,
  }

  action step = any { tick, stutter }

  val inv_feed_burst_le_1 = feedBurst <= 1
  val inv_feed_burst_eq_nt = (firstUpTick >= 0) implies (STAGGER > 0 or feedBurst == NT)
  val inv_no_busy = maxBusy == 0
  val wit_all_at_once = not(feedBurst == NT)
  val wit_all_loaded_spread = not(P.forall(p => loadedAt.get(p) >= 0) and feedBurst == 1)
}
