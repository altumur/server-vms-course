// -*- mode: Bluespec; -*-
// P/08 model unit: the gathering «from nothing» and a second change of holder during it (C7).
// Anchors: 08.8:515-541 (N1.8a: domain/partial/<part>, removed, the term of the source, merge rules), 08.8:517 («removed of the first
// gathering does not survive the second move: a limit»), 08.8:923 («a second change of holder during the gathering is not modelled
// yet»). Modelled: a section, one name in the old rows of a member, DELETE during the gathering writing `removed`, a late row
// merged (merge step 3/4: not in removed and not already held), a second move that drops `removed`. NOT modelled: signatures, the
// (term, rev) comparison of the source (the row here is always the old row, newest at that member), keys, the count, close.
module p08_gather {
  const KEEP_REMOVED_ON_SECOND: bool // mutant/control: the second move keeps removed (contrary to the stated limit, 08.8:517)
  const IGNORE_REMOVED: bool         // mutant: merge does not read removed
  const ALLOW_SECOND: bool           // the second move is enabled

  var list: Set[str]
  var removed: Set[str]
  var deletedEver: Set[str]
  var movesDone: int
  var returned: bool    // a name deleted during this gathering returned to the list
  var seq: int
  var tDel: int
  var tMove2: int
  var tBack: int

  pure val NAME = "n"
  action init = all { list' = Set(), removed' = Set(), deletedEver' = Set(), movesDone' = 1, returned' = false, seq' = 1, tDel' = 0, tMove2' = 0, tBack' = 0 }
  action merge = all {
    not(list.contains(NAME)),
    or { IGNORE_REMOVED, not(removed.contains(NAME)) },
    list' = list.union(Set(NAME)),
    returned' = (returned or deletedEver.contains(NAME)),
    tBack' = if (deletedEver.contains(NAME)) seq else tBack,
    removed' = removed, deletedEver' = deletedEver, movesDone' = movesDone, seq' = seq + 1, tDel' = tDel, tMove2' = tMove2,
  }
  action del = all {
    list.contains(NAME),
    list' = list.exclude(Set(NAME)), removed' = removed.union(Set(NAME)), deletedEver' = deletedEver.union(Set(NAME)),
    tDel' = seq, returned' = returned, movesDone' = movesDone, seq' = seq + 1, tMove2' = tMove2, tBack' = tBack,
  }
  action move2 = all {
    ALLOW_SECOND, movesDone == 1,
    movesDone' = 2,
    removed' = if (KEEP_REMOVED_ON_SECOND) removed else Set(),
    list' = list, deletedEver' = deletedEver, returned' = returned, seq' = seq + 1, tDel' = tDel, tMove2' = seq, tBack' = tBack,
  }
  action stutter = all { list' = list, removed' = removed, deletedEver' = deletedEver, movesDone' = movesDone, returned' = returned, seq' = seq, tDel' = tDel, tMove2' = tMove2, tBack' = tBack }
  action step = any { merge, del, move2, stutter }

  val inv_deleted_not_returned = not(returned)
  val wit_del_move_back = not(tDel > 0 and tMove2 > tDel and tBack > tMove2)
  val wit_merge_reachable = not(list.contains(NAME))
}

module gather_text { import p08_gather(KEEP_REMOVED_ON_SECOND = false, IGNORE_REMOVED = false, ALLOW_SECOND = true).* }
module gather_one_move { import p08_gather(KEEP_REMOVED_ON_SECOND = false, IGNORE_REMOVED = false, ALLOW_SECOND = false).* }
module gather_c_keep { import p08_gather(KEEP_REMOVED_ON_SECOND = true, IGNORE_REMOVED = false, ALLOW_SECOND = true).* }
module gather_m_ignore { import p08_gather(KEEP_REMOVED_ON_SECOND = false, IGNORE_REMOVED = true, ALLOW_SECOND = false).* }
