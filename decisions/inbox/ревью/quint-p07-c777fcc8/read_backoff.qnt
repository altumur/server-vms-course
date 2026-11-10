// C9: reads do not follow Retry-After. Anchors: nr:50 polling every poll_s; 06.5:255, 06.5:292 503 busy Retry-After: 1, 429 with Retry-After; the text gives reads no rule.
// A poll every PERIOD; each answer in the model is a refusal with Retry-After RA. FOLLOW: the next poll waits max(PERIOD, RA).
module backoff_core {
  const PERIOD: int
  const RA: int
  const FOLLOW: bool
  var t: int
  var nextAllowed: int
  var polls: int
  var early: bool
  action init = all { t' = 0, nextAllowed' = 0, polls' = 0, early' = false }
  action poll = all {
    polls < 4,
    val nt = if (FOLLOW and nextAllowed > t + PERIOD) nextAllowed else t + PERIOD
    all { t' = nt, nextAllowed' = nt + RA, polls' = polls + 1, early' = (early or nt < nextAllowed) }
  }
  action stutter = all { polls >= 4, t' = t, nextAllowed' = nextAllowed, polls' = polls, early' = early }
  action step = any { poll, stutter }
  val inv_follows_ra = not(early)
}
