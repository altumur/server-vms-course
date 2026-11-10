// C8: the wave of restarts after one change of the mark; the fixed pause of 1 s at the start.
// Anchors (slice ff32d483):
//   23:311      "not less often than once in 30 s"
//   23:314      any process stops with code 0 on a change
//   23:212      the start repeats with a pause of 1 s
//   22:794      the view reader: the same 1 s within START_WAIT
//   23:240      code 1 -> supervisor restart
//   cl:102      Q4: retries with jitter, one level; chapter 2.3 has no jitter
// N processes. Every process polls at its own instant within the 30 s after the mark; any such moment is admissible
// (the text bounds it from above only). The worst admissible case is all at once: that is a witness of the text, not a claim about
// a real cluster. After the stop every process reads the store each second while the store is down.
// STAGGER: control, process p delays by p*STEP seconds at its start (a given spread, not randomness: a probabilistic
// spread cannot be expressed by a reachability check). STEP = 0 is the mutant.
module herd_core {
  const NP: int
  const PERIOD: int
  const STAGGER: int     // the extra delay per process at start; 0 = no spread
  const DOWN: int        // for how many seconds after the change the store is not answering
  const OFFSETS: Set[int] // admissible moments of the poll within the period (a sample of 0..PERIOD-1)

  var t: int
  var polled: int -> int         // the moment the process notices the mark, -1 = not yet
  var restartAt: int -> int      // the moment the process re-enters step 0, -1 = not yet
  var lastRead: int -> int       // the last second of a read attempt
  var reads: int                 // reads at this second, recomputed by tick
  var burst: int                 // reads at the last second where the store was down
  var maxBurst: int

  val P: Set[int] = 0.to(NP - 1)

  action init = {
    nondet pts = P.setOfMaps(OFFSETS).oneOf()
    all {
      t' = 0, polled' = pts, restartAt' = P.mapBy(_ => -1), lastRead' = P.mapBy(_ => -1), reads' = 0, burst' = 0, maxBurst' = 0,
    }
  }

  // One second passes. A process whose poll moment has come stops and is restarted at once with its stagger;
  // a restarted process reads every second until the store answers (DOWN seconds).
  def readsAt(tt: int): int = P.filter(p => restartAt.get(p) >= 0 and restartAt.get(p) <= tt and tt - restartAt.get(p) <= DOWN).size()

  action tick = all {
    t < PERIOD + DOWN + NP * STAGGER + 2,
    val nt = t + 1
    val ra = P.mapBy(p => if (restartAt.get(p) < 0 and polled.get(p) == t) nt + p * STAGGER else restartAt.get(p))
    val rd = P.filter(p => ra.get(p) >= 0 and ra.get(p) <= nt and nt - ra.get(p) <= DOWN).size()
    all {
      t' = nt, restartAt' = ra, polled' = polled, lastRead' = lastRead,
      reads' = rd, burst' = rd, maxBurst' = if (rd > maxBurst) rd else maxBurst,
    }
  }

  action stutter = all {
    t >= PERIOD + DOWN + NP * STAGGER + 2,
    t' = t, restartAt' = restartAt, polled' = polled, lastRead' = lastRead, reads' = reads, burst' = burst, maxBurst' = maxBurst,
  }

  action step = any { tick, stutter }

  def burstOver(B: int): bool = maxBurst <= B
  val inv_burst_le_1 = maxBurst <= 1
  val inv_burst_le_2 = maxBurst <= 2
  val wit_all_at_once = not(maxBurst == NP)
  val wit_spread_max_one = not(maxBurst == 1 and t >= PERIOD + DOWN)
  val inv_no_burst_gt_np = maxBurst <= NP
}
