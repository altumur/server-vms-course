// M1 (no unmount; a repeat mount of one root).
// Anchors: nr:85 mount returns the page object; nr:187 instances do not share a language: several instances are admitted; nr:139 leaving the page; nr:334.
// The text says nothing about a repeated mount or about removing the root.
// Each mount starts one polling instance and one held feed. POLICY: norm (no rule), refuse (the second mount on a root is refused), replace (the old instance is stopped).
module mount_core {
  const POLICY: str
  const NM: int
  var mounts: int
  var alive: int
  var feeds: int
  var rootGone: bool
  var maxAlive: int
  action init = all { mounts' = 0, alive' = 0, feeds' = 0, rootGone' = false, maxAlive' = 0 }
  action mountRoot = all {
    mounts < NM, not(rootGone),
    val blocked = POLICY == "refuse" and alive >= 1
    val na = if (blocked) alive else if (POLICY == "replace" and alive >= 1) alive else alive + 1
    all { mounts' = mounts + 1, alive' = na, feeds' = na, rootGone' = rootGone, maxAlive' = if (na > maxAlive) na else maxAlive }
  }
  action removeRoot = all { not(rootGone), mounts' = mounts, alive' = if (POLICY == "replace") 0 else alive, feeds' = if (POLICY == "replace") 0 else feeds, rootGone' = true, maxAlive' = maxAlive }
  action stutter = all { mounts' = mounts, alive' = alive, feeds' = feeds, rootGone' = rootGone, maxAlive' = maxAlive }
  action step = any { mountRoot, removeRoot, stutter }
  val inv_one_instance = maxAlive <= 1
  val inv_no_leak_after_remove = rootGone implies feeds == 0
  val wit_two_feeds = not(feeds == 2)
}
