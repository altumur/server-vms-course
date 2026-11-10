// C5 (walk over domain pages).
// Anchors: nr:195 both loaders follow the opaque cursor; nr:183, nr:249 failed continuation -> domain: null; 10:98-100 pagination, on unchanged data following all pages
//   returns every member once; 10rc:3 DOMAIN_PAGE_MEMBERS; fwd:89 default forwarding wait 5 s.
// A walk over cursors 0..PAGES-1. FAULT: none = a proper server; repeat = at cursor 1 returns cursor 1; cycle = 1 -> 2 -> 1 (two faulty modes of a server or an intermediate).
// The text promises the end on unchanged readable data; a faulty server is outside the promise. The model asks what the client does if it happens.
// DETECT: none (text), last (proposal read as "same as the previous"), set (seen before). BUDGET: page budget (-1 none, the text has none).
module walk_core {
  const PAGES: int
  const FAULT: str
  const DETECT: str
  const BUDGET: int
  const LIM: int
  const POLL: int

  type S = {cur: int, seen: Set[int], pages: int, status: str, t: int}
  var s: S
  action init = s' = {cur: 0, seen: Set(0), pages: 0, status: "walk", t: 0}

  def nxt(i: int): int =
    if (FAULT == "repeat" and i == 1) 1
    else if (FAULT == "cycle" and i == 2) 1
    else if (i < PAGES - 1) i + 1
    else -1

  action read = all {
    s.status == "walk",
    val n = nxt(s.cur)
    val np = s.pages + 1
    val detected = (DETECT == "last" and n == s.cur) or (DETECT == "set" and n != -1 and s.seen.contains(n))
    val st =
      if (n == -1) "done"
      else if (detected) "failed"
      else if (BUDGET >= 0 and np >= BUDGET) "failed"
      else "walk"
    s' = s.with("pages", np).with("t", s.t + 5).with("status", st).with("cur", if (n == -1) s.cur else n)
          .with("seen", if (n == -1) s.seen else s.seen.union(Set(n)))
  }

  action stutter = s' = s
  action step = any { read, stutter }

  val inv_pages_le_lim = s.pages <= LIM
  val inv_no_false_fail = (s.status == "failed") implies FAULT != "none"
  val inv_done_all = (s.status == "done") implies s.pages == PAGES
  val wit_over_poll = not(s.t > POLL and s.status == "walk")
  val wit_done = not(s.status == "done")
}
