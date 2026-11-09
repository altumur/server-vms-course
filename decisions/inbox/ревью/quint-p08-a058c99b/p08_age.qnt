// -*- mode: Bluespec; -*-
// P/08 model unit: the local monotonic age of a row and frequent restarts (M5, the PARTIAL_QUIET count of C7).
// Anchors: 08.10:64-71 (IDEM_KEEP: removed by the pass by the local monotonic age from the first observation of the row version; a new
// process counts anew: the term is only longer; the ceiling IDEM_MAX: at the ceiling a new key — 503), runtime-constants.tsv:30-31
// (IDEM_KEEP 86400, IDEM_MAX 4096); 08.8:541 (PARTIAL_QUIET = 3×3600, after a start the count begins anew; closed by the operator or by
// silence), runtime-constants.tsv:50. KEEP is the age constant under check. The restart gap is an environment parameter, chosen relative
// to KEEP (below/above) — it is not a new norm number. Ceiling is a small-scope count (2 rows) instead of 4096. NOT modelled: the
// pass frequency (a pass is taken as an action), writes of new rows other than the ceiling witness, the operator's close word.
module p08_age {
  const KEEP: int
  const RESTART_GAP: int  // time between restarts (environment)
  const CEILING: int      // small scope
  const SURVIVE_AGE: bool // control/mutant: the age survives a restart (not the text)
  const CLEAN_AT: int     // the age at which the pass removes; normally = KEEP; mutant KEEP/2

  var t: int              // real seconds
  var age: int            // the observed monotonic age in this process of the row (0 = not observed)
  var born: int           // real time when the row was first written
  var sinceRestart: int
  var alive: bool
  var removedEarly: bool  // removed before KEEP real seconds passed
  var removedAt: int
  var count: int          // rows counted against the ceiling (small scope: the one row plus older ones)
  var ceilingHit: bool
  var seq: int
  var tRestart: int
  var nRestarts: int

  action init = all { t' = 0, age' = 0, born' = 0, sinceRestart' = 0, alive' = true, removedEarly' = false, removedAt' = 0, count' = CEILING, ceilingHit' = false, seq' = 1, tRestart' = 0, nRestarts' = 0 }

  // time passes in chosen quanta, not beyond a restart boundary
  action tick(d: int): bool = all {
    d > 0, sinceRestart + d <= RESTART_GAP, not(alive and age >= KEEP), t' = t + d, age' = if (alive) age + d else age, sinceRestart' = sinceRestart + d,
    born' = born, alive' = alive, removedEarly' = removedEarly, removedAt' = removedAt, count' = count, ceilingHit' = ceilingHit, seq' = seq + 1, tRestart' = tRestart, nRestarts' = nRestarts,
  }
  action restart = all {
    sinceRestart == RESTART_GAP, not(alive and age >= KEEP), age' = if (SURVIVE_AGE) age else 0, sinceRestart' = 0,
    t' = t, born' = born, alive' = alive, removedEarly' = removedEarly, removedAt' = removedAt, count' = count, ceilingHit' = ceilingHit, seq' = seq + 1, tRestart' = seq, nRestarts' = nRestarts + 1,
  }
  action clean = all {
    alive, age >= CLEAN_AT,
    alive' = false,
    removedEarly' = (t - born < KEEP),
    removedAt' = t,
    count' = count - 1,
    t' = t, age' = age, born' = born, sinceRestart' = sinceRestart, ceilingHit' = ceilingHit, seq' = seq + 1, tRestart' = tRestart, nRestarts' = nRestarts,
  }
  // a new key meets the ceiling while the rows are not cleaned: 503 (08.10:69-71)
  action newKeyAtCeiling = all {
    alive, count >= CEILING, ceilingHit' = (ceilingHit or t - born >= KEEP),
    t' = t, age' = age, born' = born, sinceRestart' = sinceRestart, alive' = alive, removedEarly' = removedEarly, removedAt' = removedAt, count' = count, seq' = seq + 1, tRestart' = tRestart, nRestarts' = nRestarts,
  }

  action stutter = all { t' = t, age' = age, born' = born, sinceRestart' = sinceRestart, alive' = alive, removedEarly' = removedEarly, removedAt' = removedAt, count' = count, ceilingHit' = ceilingHit, seq' = seq, tRestart' = tRestart, nRestarts' = nRestarts }
  action step = any {
    nondet d = oneOf(Set(RESTART_GAP, RESTART_GAP / 2, RESTART_GAP - RESTART_GAP / 2))
    tick(d), restart, clean, newKeyAtCeiling, stutter,
  }

  val inv_not_early = not(removedEarly)
  // the ceiling is hit (new keys refused) after the row has really outlived KEEP and still is not cleaned
  val wit_full_stale_past_keep = not(alive and t - born >= 2 * KEEP and ceilingHit and tRestart > 0)
  val wit_cleaned = alive
  // the bounded liveness that fails under frequent restarts: by real age 2*KEEP the row is gone
  val inv_cleaned_by_2keep = not(alive and t - born >= 2 * KEEP)
}

// IDEM_KEEP = 86400 (runtime-constants.tsv:30): restarts every KEEP-1 s (below) and KEEP+1 s (above)
module idem_restart_frequent { import p08_age(KEEP = 86400, RESTART_GAP = 86399, CEILING = 2, SURVIVE_AGE = false, CLEAN_AT = 86400).* }
module idem_restart_rare { import p08_age(KEEP = 86400, RESTART_GAP = 86401, CEILING = 2, SURVIVE_AGE = false, CLEAN_AT = 86400).* }
// PARTIAL_QUIET = 10800 (runtime-constants.tsv:50): the count of silence begins anew at a start (08.8:541)
module quiet_restart_frequent { import p08_age(KEEP = 10800, RESTART_GAP = 10799, CEILING = 2, SURVIVE_AGE = false, CLEAN_AT = 10800).* }
module quiet_restart_rare { import p08_age(KEEP = 10800, RESTART_GAP = 10801, CEILING = 2, SURVIVE_AGE = false, CLEAN_AT = 10800).* }
module idem_c_survive { import p08_age(KEEP = 86400, RESTART_GAP = 86399, CEILING = 2, SURVIVE_AGE = true, CLEAN_AT = 86400).* }
module idem_m_early { import p08_age(KEEP = 86400, RESTART_GAP = 86401, CEILING = 2, SURVIVE_AGE = false, CLEAN_AT = 43200).* }
