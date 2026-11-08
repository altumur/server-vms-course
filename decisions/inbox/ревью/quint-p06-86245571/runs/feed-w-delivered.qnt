// -*- mode: Bluespec; -*-
// The change feed: history eviction, reset, full re-read, and the client's re-read/reset cycle.
// Anchors: 06.1:549 (start of a subscription: position first, reads, then after), 06.1:553,555 (reset, item 2 evicted), 06.1:994-1002 (give), const:5,6.
// Abstraction: a counter model. Numbers are integers; the history holds the last CHANGES_HISTORY message numbers.
// One tick produces RATE messages (sustained) or a one-off burst; the client re-read duration D is measured in ticks (environment parameter, no norm).
// Assumption A: the client takes its position before reading (06.1:553) and asks after= that position after the read; a re-read holds for D ticks.
// NOT modelled: rights filters, labels/folders resets (3,4,5), wait/long-poll semantics, Retry-After, the cost of the read itself.
module feed {
  pure val CHANGES_HISTORY = 256      // const:6
  pure val MODE = "sustained"         // @override sustained | burst
  pure val RATE = 1  // @override messages per tick (sustained): model/environment input
  pure val BURST = 257                // @override one-off burst size
  pure val D = 1                      // @override client re-read duration in ticks (environment input)
  pure val N = 2                      // @override number of subscribers
  pure val MAX_TICKS = 8              // @override
  pure val MUT = "none"               // @override none | no_reset
  pure val RESTARTS_MAX = 1           // @override console restarts (reset 1 of 06.1:554); 0 removes the action
  pure val CLIENTS: Set[int] = 0.to(N-1)

  var last: int                       // last issued message number; 0 = none
  var ticks: int
  var burstDone: bool
  // per-client
  var pos: int -> int                 // position (after) the client asks for
  var phase: int -> str               // Read | Poll
  var readUntil: int -> int           // tick at which the re-read ends
  var known: int -> int               // the client has every message <= known applied
  // ghosts
  var resets: int -> int              // consecutive resets since last delivered message
  var maxResets: int
  var silentSkip: bool                // a delivery that skipped evicted numbers
  var simulReads: int                 // clients in Read state at the same time when a reset was issued in this tick
  var storm: bool
  var restarts: int

  val firstKept = last - CHANGES_HISTORY + 1   // numbers firstKept..last are in history
  def evicted(p: int): bool = p + 1 < firstKept and p < last  // after=p needs messages p+1.. that are evicted

  action init = all {
    last' = 0, ticks' = 0, burstDone' = false,
    pos' = CLIENTS.mapBy(i => 0), phase' = CLIENTS.mapBy(i => "Read"), readUntil' = CLIENTS.mapBy(i => D),
    known' = CLIENTS.mapBy(i => 0), resets' = CLIENTS.mapBy(i => 0), maxResets' = 0, silentSkip' = false,
    simulReads' = 0, storm' = false, restarts' = 0,
  }

  // client ends its re-read at the deadline and polls after=position
  action endRead(i: int): bool = all {
    phase.get(i) == "Read", ticks >= readUntil.get(i),
    phase' = phase.set(i, "Poll"), known' = known.set(i, pos.get(i)),
    pos' = pos, readUntil' = readUntil, last' = last, ticks' = ticks, burstDone' = burstDone,
    resets' = resets, maxResets' = maxResets, silentSkip' = silentSkip, simulReads' = simulReads, storm' = storm, restarts' = restarts,
  }

  // give(after): reset if evicted; else deliver all up to last and advance position
  action poll(i: int): bool = all {
    phase.get(i) == "Poll",
    val p = pos.get(i)
    if (evicted(p) and MUT != "no_reset") all {
      // reset: re-read all rows from the current position (06.1:555); the client starts a full re-read
      pos' = pos.set(i, last), phase' = phase.set(i, "Read"), readUntil' = readUntil.set(i, ticks + D),
      resets' = resets.set(i, resets.get(i) + 1), maxResets' = if (resets.get(i) + 1 > maxResets) resets.get(i) + 1 else maxResets,
      known' = known, silentSkip' = silentSkip, last' = last, ticks' = ticks, burstDone' = burstDone,
      simulReads' = simulReads + 1, storm' = (storm or simulReads + 1 >= N), restarts' = restarts,
    } else if (evicted(p)) all {
      // mutant: silently delivers from firstKept (skipping evicted numbers)
      pos' = pos.set(i, last), known' = known.set(i, last), silentSkip' = true,
      phase' = phase, readUntil' = readUntil, resets' = resets, maxResets' = maxResets, last' = last, ticks' = ticks, burstDone' = burstDone,
      simulReads' = simulReads, storm' = storm, restarts' = restarts,
    } else all {
      pos' = pos.set(i, last), known' = known.set(i, last),
      resets' = resets.set(i, 0),
      phase' = phase, readUntil' = readUntil, maxResets' = maxResets, silentSkip' = silentSkip, last' = last, ticks' = ticks, burstDone' = burstDone,
      simulReads' = simulReads, storm' = storm, restarts' = restarts,
    }
  }

  // the feed tick: RATE messages sustained, or a single burst.
  // Assumption B (attentive client, the favourable case): a tick is taken only when every client is either mid-read before its deadline
  // or has polled up to the end of the history, so a reset below is not due to client laziness.
  action tick = all {
    ticks < MAX_TICKS,
    CLIENTS.forall(i => (phase.get(i) == "Read" and ticks < readUntil.get(i)) or (phase.get(i) == "Poll" and pos.get(i) == last)),
    val produced = if (MODE == "sustained") RATE else if (not(burstDone)) BURST else 0
    all {
      last' = last + produced, ticks' = ticks + 1, burstDone' = (burstDone or MODE == "burst"),
      pos' = pos, phase' = phase, readUntil' = readUntil, known' = known,
      resets' = resets, maxResets' = maxResets, silentSkip' = silentSkip, simulReads' = 0, storm' = storm, restarts' = restarts,
    }
  }

  // a console restart: the client's position is of another instance → reset 1; modelled as an eviction of everything
  action restart = all {
    ticks > 0, ticks < MAX_TICKS, MODE == "burst", restarts < RESTARTS_MAX,
    restarts' = restarts + 1,
    last' = last + CHANGES_HISTORY + 1, ticks' = ticks + 1, burstDone' = burstDone,
    pos' = pos, phase' = phase, readUntil' = readUntil, known' = known,
    resets' = resets, maxResets' = maxResets, silentSkip' = silentSkip, simulReads' = 0, storm' = storm,
  }

  action idle = all {
    last' = last, ticks' = ticks, burstDone' = burstDone, pos' = pos, phase' = phase, readUntil' = readUntil, known' = known,
    resets' = resets, maxResets' = maxResets, silentSkip' = silentSkip, simulReads' = simulReads, storm' = storm, restarts' = restarts,
  }

  action step = any {
    idle,
    nondet i = oneOf(CLIENTS) any { endRead(i), poll(i) },
    tick,
    restart,
  }

  // -- properties
  // no silent gap: the client never advances over evicted numbers without a reset
  val noSilentSkip = not(silentSkip)
  // the client state never claims knowledge of numbers it did not get or re-read
  val knownSound = CLIENTS.forall(i => known.get(i) <= last)
  // bound on the consecutive reset loop: 1 reset per episode (a client that re-reads then keeps up)
  val noResetLoop = CLIENTS.forall(i => resets.get(i) <= 1)
  // all clients reset within one tick (storm)
  val noStorm = not(storm)

  // -- witnesses
  val w_delivered = CLIENTS.exists(i => known.get(i) > 0) == false
  val w_reset = not(maxResets >= 1)
  val w_all_read = not(simulReads == N and N >= 2)
  val c_false = last < 0
}
