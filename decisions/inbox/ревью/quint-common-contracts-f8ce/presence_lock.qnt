// Model of Platform/common/contracts/presence-lock.md (pin f8ce0f52): open/flock/compare at the worker,
// non-blocking flock/compare/delete at the resource. Inodes are integers; 0 means no directory entry.
module presence_lock {
  const MUT_NO_STAT: bool
  const MUT_DELETE_AFTER_RELEASE: bool
  pure val MAXI: int = 4
  type S = { path: int, next: int, lockBy: int -> str, wpc: str, wfd: int, rpc: str, rfd: int, retries: int, deleted: int }
  var s: S
  action init = s' = { path: 0, next: 1, lockBy: 1.to(MAXI).mapBy(i => ""), wpc: "idle", wfd: 0, rpc: "idle", rfd: 0, retries: 0, deleted: 0 }

  action wOpen = all {
    s.wpc == "idle", or { s.path != 0, s.next <= MAXI },
    if (s.path != 0) s' = s.with("wpc", "opened").with("wfd", s.path)
    else s' = s.with("wpc", "opened").with("wfd", s.next).with("path", s.next).with("next", s.next + 1)
  }
  action wFlock = all { s.wpc == "opened", s.lockBy.get(s.wfd) == "", s' = s.with("wpc", "locked").with("lockBy", s.lockBy.set(s.wfd, "W")) }
  action wCompare = all {
    s.wpc == "locked",
    if (MUT_NO_STAT or s.path == s.wfd) s' = s.with("wpc", "holding")
    else s' = s.with("wpc", "idle").with("lockBy", s.lockBy.set(s.wfd, "")).with("wfd", 0).with("retries", s.retries + 1)
  }
  action wExit = all {
    s.wpc != "idle",
    s' = s.with("wpc", "idle").with("wfd", 0)
          .with("lockBy", if (s.wpc == "locked" or s.wpc == "holding") s.lockBy.set(s.wfd, "") else s.lockBy)
  }
  action rFlock = all {
    s.rpc == "idle", s.path != 0, s.lockBy.get(s.path) == "",
    s' = s.with("rpc", "locked").with("rfd", s.path).with("lockBy", s.lockBy.set(s.path, "R"))
  }
  action rCompare = all {
    s.rpc == "locked",
    if (s.path != s.rfd) s' = s.with("rpc", "idle").with("lockBy", s.lockBy.set(s.rfd, "")).with("rfd", 0)
    else if (MUT_DELETE_AFTER_RELEASE) s' = s.with("rpc", "todelete").with("lockBy", s.lockBy.set(s.rfd, ""))
    else s' = s.with("rpc", "idle").with("path", 0).with("deleted", s.deleted + 1).with("lockBy", s.lockBy.set(s.rfd, "")).with("rfd", 0)
  }
  action rDeleteLate = all { s.rpc == "todelete", s' = s.with("rpc", "idle").with("path", if (s.path == s.rfd) 0 else s.path).with("deleted", s.deleted + 1).with("rfd", 0) }
  action step = any { wOpen, wFlock, wCompare, wExit, rFlock, rCompare, rDeleteLate }

  // A worker that believes it holds the lock is visible through the path of its file.
  val holderVisible: bool = s.wpc != "holding" or s.path == s.wfd
  val noRetry: bool = s.retries == 0
  val noDelete: bool = s.deleted == 0
  val neverHolding: bool = s.wpc != "holding"
}
module presence_ok { import presence_lock(MUT_NO_STAT = false, MUT_DELETE_AFTER_RELEASE = false).* }
module presence_mut_nostat { import presence_lock(MUT_NO_STAT = true, MUT_DELETE_AFTER_RELEASE = false).* }
module presence_mut_lateunlink { import presence_lock(MUT_NO_STAT = false, MUT_DELETE_AFTER_RELEASE = true).* }
