// -*- mode: Bluespec; -*-
// P/08 model unit: keeping a part alive while a fetch is going on, across a restart of the holder process (C7, M3).
// Anchors: 08.8:203 (a part lives while one of BACKUP_HEADS heads refers to it or a fetch not older than BACKUP_FETCH is going
// on), forms: BACKUP_HEADS=5 (runtime-constants.tsv:49), BACKUP_EVERY_MIN=30 (:46), BACKUP_FETCH=600 (:48). Where the fetch is
// accounted is not named at the pin (M3): the switch DURABLE chooses a durable mark or process memory (restart forgets).
// NOT modelled: curHead content (a part changes every curHead, the worst case for links), the keeper's own copy GC, door checks.
// Bound: one fetch of the part of one curHead.
module p08_partgc {
  const HEADS: int
  const EVERY: int
  const FETCH: int
  const DURABLE: bool    // the fetch accounting survives a restart of the process (not named at the pin)
  const IGNORE_FETCH: bool // mutant: GC ignores the running fetch

  var t: int
  var curHead: int          // the current curHead number; a part of curHead h is removed when h < curHead - HEADS + 1 unless fetched
  var fetchRev: int      // 0 none: the curHead number of the part being fetched
  var fetchStart: int
  var accounted: bool    // the holder knows about the running fetch
  var gone: Set[int]     // part revisions removed
  var seq: int
  var tFetch: int
  var tRestart: int
  var tGc: int
  var hit: bool          // the fetcher reads a part that was removed while the fetch is younger than FETCH

  action init = all { t' = 0, curHead' = 1, fetchRev' = 0, fetchStart' = 0, accounted' = false, gone' = Set(), seq' = 1, tFetch' = 0, tRestart' = 0, tGc' = 0, hit' = false }

  action startFetch = all { fetchRev == 0, fetchRev' = curHead, fetchStart' = t, accounted' = true, curHead' = curHead, t' = t, gone' = gone, seq' = seq + 1, tFetch' = seq, tRestart' = tRestart, tGc' = tGc, hit' = hit }
  action rotate = all { curHead' = curHead + 1, t' = t + EVERY, fetchRev' = fetchRev, fetchStart' = fetchStart, accounted' = accounted, gone' = gone, seq' = seq + 1, tFetch' = tFetch, tRestart' = tRestart, tGc' = tGc, hit' = hit }
  action restart = all { accounted' = DURABLE, curHead' = curHead, t' = t, fetchRev' = fetchRev, fetchStart' = fetchStart, gone' = gone, seq' = seq + 1, tFetch' = tFetch, tRestart' = seq, tGc' = tGc, hit' = hit }

  // the GC: a part of revision r unreferenced by the retained heads
  action gc(r: int): bool = all {
    r >= 1, r <= curHead - HEADS, not(gone.contains(r)),
    or { IGNORE_FETCH, not(fetchRev == r and accounted and t - fetchStart <= FETCH) },
    gone' = gone.union(Set(r)),
    tGc' = seq, curHead' = curHead, t' = t, fetchRev' = fetchRev, fetchStart' = fetchStart, accounted' = accounted, seq' = seq + 1, tFetch' = tFetch, tRestart' = tRestart, hit' = hit,
  }
  // the fetcher reads its part
  action read = all {
    fetchRev != 0, t - fetchStart <= FETCH,
    hit' = (hit or gone.contains(fetchRev)),
    fetchRev' = 0, fetchStart' = fetchStart, accounted' = false, curHead' = curHead, t' = t, gone' = gone, seq' = seq + 1, tFetch' = tFetch, tRestart' = tRestart, tGc' = tGc,
  }

  action step = any { startFetch, rotate, restart, read, nondet r = oneOf(1.to(10)) gc(r) }

  val inv_no_gc_under_young_fetch = not(hit)
  // the fetch is still within its term when the part is removed: the witness of order
  val wit_restart_gc_read = not(tFetch > 0 and tRestart > tFetch and tGc > tRestart and hit)
  val wit_gc_happens = not(tGc > 0)
  val wit_read_ok = not(fetchRev == 0 and tGc > 0 and not(hit))
}

module gc_text_memory { import p08_partgc(HEADS = 5, EVERY = 30, FETCH = 600, DURABLE = false, IGNORE_FETCH = false).* }
module gc_c_durable { import p08_partgc(HEADS = 5, EVERY = 30, FETCH = 600, DURABLE = true, IGNORE_FETCH = false).* }
module gc_m_ignore { import p08_partgc(HEADS = 5, EVERY = 30, FETCH = 600, DURABLE = true, IGNORE_FETCH = true).* }
