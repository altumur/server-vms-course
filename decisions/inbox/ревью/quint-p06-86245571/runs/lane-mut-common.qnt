// -*- mode: Bluespec; -*-
// Lanes of a console instance: common, callback; passes wait for their callback (06.5:255, 06.5:824, gate:283, gate:596, gate:644-646).
// Anchors: 06.5:255 (a pass takes the common lane; callback lane own and bounded; stream lane separate), 06.5:824 (callback lane not smaller than the common one),
//   gate:283 (lane first), gate:596 (no response time limit for a stream), gate:614 (closing conditions), gate:645 (PASS_WAIT_MAX).
// Abstraction: counters. A pass holds a common slot until its callback finishes; a callback holds a slot of the callback lane while it runs.
// A stalled reader (gate:596: no idle limit in the text) holds a common slot with no release action in the model.
// L_COMMON has no number in the norms (implementation decides, "the lanes and their sizes" 06.5:824): the model takes small values, the claim is structural.
// NOT modelled: reserve/monitor/feed/stream lanes, wait timers, 503 Retry-After loops, the order of the gate.
module lanes {
  pure val L_COMMON = 2      // @override implementation-chosen
  pure val L_CB = 2          // @override
  pure val MUT = "callback_on_common"  // @override none | callback_on_common
  pure val STALLED_MAX = 2   // @override
  type St = { common: int, cb: int, passesWaiting: int, stalled: int, callbackRefused: bool, opRefused: bool }
  var s: St

  action init = s' = { common: 0, cb: 0, passesWaiting: 0, stalled: 0, callbackRefused: false, opRefused: false }

  val commonFree = s.common < L_COMMON
  val cbFree = if (MUT == "callback_on_common") s.common < L_COMMON else s.cb < L_CB

  // a pass of the common lane admitted (holds the slot and waits for its callback)
  action passAdmitted = all {
    commonFree,
    s' = {...s, common: s.common + 1, passesWaiting: s.passesWaiting + 1},
  }

  // the waiting pass' callback arrives at the callback lane (one concurrent callback per pass, 06.5:824)
  action callbackAdmitted = all {
    s.passesWaiting > 0, cbFree,
    if (MUT == "callback_on_common")
      s' = {...s, common: s.common + 1, cb: s.cb + 1, passesWaiting: s.passesWaiting - 1, callbackRefused: false}
    else
      s' = {...s, cb: s.cb + 1, passesWaiting: s.passesWaiting - 1, callbackRefused: false},
  }

  // a callback is refused 503 busy because its lane is full
  action callbackRefused = all {
    s.passesWaiting > 0, not(cbFree),
    s' = {...s, callbackRefused: true},
  }

  // the callback finishes, the pass ends, slots are released
  action callbackDone = all {
    s.cb > 0,
    if (MUT == "callback_on_common")
      s' = {...s, cb: s.cb - 1, common: s.common - 2}
    else
      s' = {...s, cb: s.cb - 1, common: s.common - 1},
  }

  // a reader that stops reading the response holds a common slot; the norm names no idle limit (gate:596), so no release action exists
  action stall = all {
    commonFree, s.stalled < STALLED_MAX,
    s' = {...s, common: s.common + 1, stalled: s.stalled + 1},
  }

  // a new operator request is refused 503 busy when the common lane is full
  action operatorRefused = all {
    not(commonFree),
    s' = {...s, opRefused: true},
  }

  action idle = s' = s

  action step = any { idle, passAdmitted, callbackAdmitted, callbackRefused, callbackDone, stall, operatorRefused }

  // -- properties
  // A pass waiting for its callback can always have the callback admitted when the callback lane >= common lane (06.5:824).
  val callbackEverAdmissible = not(s.passesWaiting > 0 and s.callbackRefused and s.cb < L_COMMON and s.stalled == 0)
  // the deadlock shape of 06.5:255: all common slots are passes that wait for a callback which cannot be admitted
  val noDeadlock = not(s.passesWaiting == L_COMMON and not(cbFree))

  // -- witnesses
  val w_common_full_stalled = not(s.common == L_COMMON and s.stalled == L_COMMON and s.opRefused)
  val w_pass_ok = not(s.cb > 0)
  val c_false = s.common < 0
}
