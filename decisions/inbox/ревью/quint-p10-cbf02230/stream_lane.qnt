// C5: a stalled stream reader and the stream lane of the domain console.
// Claim checked: the text of gate-and-pass closes a stream only on the listed
// causes; the lane is bounded by PASS_STREAMS_MAX; which causes bound a stalled
// reader's hold on a lane slot?
// Anchors (slice cbf02230):
//   gate-and-pass.md:596  "a stream has no limit, the end of the request closes it"
//   gate-and-pass.md:614  close: answer given in full, client connection closed or broken, wait limit
//   gate-and-pass.md:615  stream also: jti revoked, person disabled, exp has come, may refused;
//                         open streams checked at least once per PASS_TICKET_CHECK
//   gate-and-pass.md:644  a pass as a stream takes the stream lane
//   gate-and-pass.md:646  PASS_STREAMS_MAX 256; :647 PASS_TICKET_CHECK 5 s
//   forwarding.md:123     stream relayed as bytes arrive, no 5-s cap, no body cap
//   forwarding.md:278     "Streaming and pass retain their existing idle, header and completion rules"
//   08-domain/forms/runtime-constants.tsv:14  TOKEN_LIFETIME 900 s
//   domain-token.md:47    exp = iat + TOKEN_LIFETIME
// Not modelled: revoke/disable/may (they only shorten a hold), TOKEN_SKEW (gate-and-pass.md:615
// says "exp has come"; if a skew applied, the bound grows by 60 s), data flow (a stalled reader
// is a boolean), lane-full refusal word (C3; here "refused" is an event only), bytes, TCP.
// Slots are scaled from 256 to SLOTS: the claim is per-stream and per-lane, no arithmetic on 256.
module stream_core {
  const SLOTS: int
  const STREAMS: Set[int]
  const TOK: int            // TOKEN_LIFETIME; exp = open + TOK (worst case: fresh token at open)
  const CHECK: int          // PASS_TICKET_CHECK
  const WRITE_DEADLINE: int // 0 = the norm's text (no stall term); >0 = control rule "stall term"
  const EXP_RULE: bool      // true = gate-and-pass.md:615; false = mutant, no exp close
  const CAP_RULE: bool      // true = lane enforced; false = mutant
  const HOLD_BOUND: int     // the bound H of inv_stalled_hold_bounded
  const DTS: Set[int]       // time steps

  var now: int
  var st: int -> str          // idle | open | closed
  var stalled: int -> bool
  var stallAt: int -> int     // -1 while not stalled
  var expAt: int -> int
  var why: int -> str         // why closed
  var tRefused: int           // -1 or time of a refused open, when all holders are stalled
  var tLastStall: int         // time of the latest stall event
  var nRefused: int
  var seq: int                // step counter: the order of events, not time

  def openStreams = STREAMS.filter(s => st.get(s) == "open")
  def stalledOpen = openStreams.filter(s => stalled.get(s))

  action init = all {
    now' = 0,
    st' = STREAMS.mapBy(_ => "idle"),
    stalled' = STREAMS.mapBy(_ => false),
    stallAt' = STREAMS.mapBy(_ => -1),
    expAt' = STREAMS.mapBy(_ => -1),
    why' = STREAMS.mapBy(_ => ""),
    tRefused' = -1,
    tLastStall' = -1,
    nRefused' = 0,
    seq' = 0,
  }

  action unchanged_rest = all {
    tRefused' = tRefused, tLastStall' = tLastStall, nRefused' = nRefused, seq' = seq + 1,
  }

  action openStream(s: int): bool = all {
    st.get(s) == "idle",
    or { not(CAP_RULE), openStreams.size() < SLOTS },
    st' = st.set(s, "open"),
    expAt' = expAt.set(s, now + TOK),
    stalled' = stalled, stallAt' = stallAt, why' = why, now' = now,
    unchanged_rest,
  }

  action refuse(s: int): bool = all {
    CAP_RULE,
    st.get(s) == "idle",
    openStreams.size() == SLOTS,
    tRefused' = if (stalledOpen.size() == SLOTS) seq else tRefused,
    nRefused' = nRefused + 1,
    st' = st, stalled' = stalled, stallAt' = stallAt, expAt' = expAt, why' = why, now' = now,
    tLastStall' = tLastStall, seq' = seq + 1,
  }

  // The client stops reading while TCP stays alive: no close cause of gate-and-pass.md:614 applies.
  action stall(s: int): bool = all {
    st.get(s) == "open", not(stalled.get(s)),
    stalled' = stalled.set(s, true),
    stallAt' = stallAt.set(s, now),
    tLastStall' = seq,
    st' = st, expAt' = expAt, why' = why, now' = now,
    tRefused' = tRefused, nRefused' = nRefused, seq' = seq + 1,
  }

  // A reader that still reads may leave: gate-and-pass.md:614 "closed or broken".
  action clientLeaves(s: int): bool = all {
    st.get(s) == "open", not(stalled.get(s)),
    st' = st.set(s, "closed"), why' = why.set(s, "client"),
    stalled' = stalled, stallAt' = stallAt, expAt' = expAt, now' = now,
    unchanged_rest,
  }

  // gate-and-pass.md:615: exp has come, noticed by the periodic check.
  action closeExp(s: int): bool = all {
    EXP_RULE,
    st.get(s) == "open", now >= expAt.get(s),
    st' = st.set(s, "closed"), why' = why.set(s, "exp"),
    stalled' = stalled, stallAt' = stallAt, expAt' = expAt, now' = now,
    unchanged_rest,
  }

  // Control rule (the proposed norm of C5, not in the text): a finite stall term.
  action closeStall(s: int): bool = all {
    WRITE_DEADLINE > 0,
    st.get(s) == "open", stalled.get(s), now >= stallAt.get(s) + WRITE_DEADLINE,
    st' = st.set(s, "closed"), why' = why.set(s, "stall"),
    stalled' = stalled, stallAt' = stallAt, expAt' = expAt, now' = now,
    unchanged_rest,
  }

  // Urgency: time does not pass a deadline that the console must have acted on.
  def tickOk(dt: int): bool =
    STREAMS.forall(s =>
      st.get(s) != "open" or (
        (not(EXP_RULE) or now + dt <= expAt.get(s) + CHECK) and
        (not(WRITE_DEADLINE > 0 and stalled.get(s)) or now + dt <= stallAt.get(s) + WRITE_DEADLINE + CHECK)))

  action tick(dt: int): bool = all {
    tickOk(dt),
    now' = now + dt,
    st' = st, stalled' = stalled, stallAt' = stallAt, expAt' = expAt, why' = why,
    unchanged_rest,
  }

  action step = {
    nondet s = oneOf(STREAMS)
    nondet dt = oneOf(DTS)
    any { openStream(s), refuse(s), stall(s), clientLeaves(s), closeExp(s), closeStall(s), tick(dt) }
  }

  // -- properties --
  val inv_lane_cap = openStreams.size() <= SLOTS

  // The bound on a stalled reader's hold on a slot, for streams STILL holding it:
  // no stream may have been stalled for longer than HOLD_BOUND and still occupy the lane.
  val inv_stalled_hold_bounded =
    stalledOpen.forall(s => now - stallAt.get(s) <= HOLD_BOUND)

  // The same bound measured on the whole hold of the slot, from the open.
  val inv_open_hold_bounded =
    openStreams.forall(s => now - (expAt.get(s) - TOK) <= HOLD_BOUND)

  // -- witnesses: each is violated exactly when the ordered situation is reachable --
  // All slots are held by stalled readers and only AFTER the last stall a new client is refused.
  val wit_lane_full_of_stalled_refuses =
    not(tRefused >= 0 and tLastStall >= 0 and tRefused > tLastStall
        and stalledOpen.size() == SLOTS and nRefused >= 1)

  // A stream stalled at time 0..; closed only by exp, after it held the slot for TOK or more.
  val wit_stalled_closed_by_exp =
    not(STREAMS.exists(s => why.get(s) == "exp" and stallAt.get(s) >= 0
                            and now - stallAt.get(s) >= TOK - 1))

  val wit_stalled_closed_by_term =
    not(STREAMS.exists(s => why.get(s) == "stall"))
}

// The text of the norm, real constants, 2 slots (PASS_STREAMS_MAX scaled).
module stream_norm {
  import stream_core(SLOTS=2, STREAMS=Set(1,2,3), TOK=900, CHECK=5, WRITE_DEADLINE=0,
                     EXP_RULE=true, CAP_RULE=true, HOLD_BOUND=905,
                     DTS=Set(1,4,5,895,900,905)).*
}
// Below exp: the hold can exceed 450 s (half the term), so the term of a slot is not "short".
module stream_norm_h450 {
  import stream_core(SLOTS=2, STREAMS=Set(1,2,3), TOK=900, CHECK=5, WRITE_DEADLINE=0,
                     EXP_RULE=true, CAP_RULE=true, HOLD_BOUND=450,
                     DTS=Set(1,4,5,895,900,905)).*
}
// Control: a stall term of 30 ticks (a parameter of the model, not a proposed number).
module stream_ctrl_term {
  import stream_core(SLOTS=2, STREAMS=Set(1,2,3), TOK=900, CHECK=5, WRITE_DEADLINE=30,
                     EXP_RULE=true, CAP_RULE=true, HOLD_BOUND=35,
                     DTS=Set(1,4,5,30,35,895,900,905)).*
}
// Mutant: exp rule removed: then the hold is unbounded (within the bound of the run).
module stream_mut_noexp {
  import stream_core(SLOTS=2, STREAMS=Set(1,2,3), TOK=900, CHECK=5, WRITE_DEADLINE=0,
                     EXP_RULE=false, CAP_RULE=true, HOLD_BOUND=905,
                     DTS=Set(1,4,5,895,900,905)).*
}
// Mutant: no lane enforcement.
module stream_mut_nocap {
  import stream_core(SLOTS=2, STREAMS=Set(1,2,3), TOK=900, CHECK=5, WRITE_DEADLINE=0,
                     EXP_RULE=true, CAP_RULE=false, HOLD_BOUND=905,
                     DTS=Set(1,4,5,895,900,905)).*
}
