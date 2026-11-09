// -*- mode: Bluespec; -*-
// P/08 model unit: busy and back pressure at the agent doors; the first whole reports after a change of holder (C13, C14).
// Anchors: common/contracts/accept.md:217-220 (busy after the signature, class server is not refused, the threshold counts requests
// of class camera in the last second), 08.1:101 (a new holder has no marks: every member reports whole), runtime-constants.tsv:36
// (REPORT_RATE: unmeasured). Modelled in one-second buckets; arrival sets are small and are not a load model; REPORT_RATE_SCALED
// is a small-scope stand-in for REPORT_RATE (200), SERVERS and CAMERAS stand for 3 members each: the counts are a shape, not an
// estimate. NOT modelled: retry_in, spreading of passes (P/09.1 N1.2a), bodies and whole sizes, relay batches.
module p08_storm {
  const RATE: int         // threshold per second (small scope)
  const SERVERS_BUSY: bool // control: class server is also refused (contrary to accept.md:218)
  const COUNT_ADMITTED_ONLY: bool // alternative: only admitted requests count toward the threshold (text: requests)
  const NO_THRESHOLD: bool // mutant: no busy at all

  pure val CAMS = Set("c1", "c2", "c3")
  pure val SRVS = Set("s1", "s2", "s3")
  var t: int
  var reqs: int            // camera requests in this second (literal count)
  var admittedCam: int     // cameras admitted in this second
  var sigWork: int         // signature checks spent in this second, on all classes
  var wholeSrv: int        // whole first reports of servers in this second, after the change of holder
  var seen: Set[str]       // members already sent their first whole in this run
  var refusedThisSec: int
  var maxAdmittedCam: int
  var maxWholeSrv: int
  var maxSigWork: int

  action init = all { t' = 0, reqs' = 0, admittedCam' = 0, sigWork' = 0, wholeSrv' = 0, seen' = Set(), refusedThisSec' = 0, maxAdmittedCam' = 0, maxWholeSrv' = 0, maxSigWork' = 0 }

  action nextSec = all { t' = t + 1, reqs' = 0, admittedCam' = 0, sigWork' = 0, wholeSrv' = 0, seen' = seen, refusedThisSec' = 0, maxAdmittedCam' = maxAdmittedCam, maxWholeSrv' = maxWholeSrv, maxSigWork' = maxSigWork }

  action camera(c: str): bool = all {
    CAMS.contains(c),
    val over = not(NO_THRESHOLD) and (if (COUNT_ADMITTED_ONLY) admittedCam else reqs) >= RATE
    all {
      reqs' = reqs + 1,
      sigWork' = sigWork + 1,
      admittedCam' = if (over) admittedCam else admittedCam + 1,
      refusedThisSec' = if (over) refusedThisSec + 1 else refusedThisSec,
      maxAdmittedCam' = if (not(over) and admittedCam + 1 > maxAdmittedCam) admittedCam + 1 else maxAdmittedCam,
      maxSigWork' = if (sigWork + 1 > maxSigWork) sigWork + 1 else maxSigWork,
      seen' = seen.union(Set(c)),
    },
    t' = t, wholeSrv' = wholeSrv, maxWholeSrv' = maxWholeSrv,
  }

  action serverWhole(s: str): bool = all {
    SRVS.contains(s), not(seen.contains(s)),
    val refused = SERVERS_BUSY and (wholeSrv + admittedCam) >= RATE
    all {
      wholeSrv' = if (refused) wholeSrv else wholeSrv + 1,
      maxWholeSrv' = if (not(refused) and wholeSrv + 1 > maxWholeSrv) wholeSrv + 1 else maxWholeSrv,
      sigWork' = sigWork + 1,
      maxSigWork' = if (sigWork + 1 > maxSigWork) sigWork + 1 else maxSigWork,
      seen' = seen.union(Set(s)),
    },
    t' = t, reqs' = reqs, admittedCam' = admittedCam, refusedThisSec' = refusedThisSec, maxAdmittedCam' = maxAdmittedCam,
  }

  action step = any {
    nextSec,
    nondet c = oneOf(CAMS) camera(c),
    nondet s = oneOf(SRVS) serverWhole(s),
  }

  val inv_camera_admitted = maxAdmittedCam <= RATE
  val inv_whole_srv_le_rate = maxWholeSrv <= RATE
  val inv_sigwork_le_rate = maxSigWork <= RATE
  val wit_whole_burst = maxWholeSrv < 2
  val wit_camera_refused_with_sig = not(refusedThisSec > 0 and sigWork > RATE)
}

module storm_text { import p08_storm(RATE = 2, SERVERS_BUSY = false, COUNT_ADMITTED_ONLY = false, NO_THRESHOLD = false).* }
module storm_c_servers { import p08_storm(RATE = 2, SERVERS_BUSY = true, COUNT_ADMITTED_ONLY = false, NO_THRESHOLD = false).* }
module storm_m_nothreshold { import p08_storm(RATE = 2, SERVERS_BUSY = false, COUNT_ADMITTED_ONLY = false, NO_THRESHOLD = true).* }
