// C7: the fate of a forwarded edit after 502 "did not answer".
// Anchors (slice cbf02230):
//   10-domain-console.norms.md:186     the answer as it came; 502 on a break and on silence
//   forwarding.md:85-87,89             no answer within FORWARD_WAIT (default 5) -> 502 did not answer
//   forwarding.md:278                  "Existing ambiguous, unavailable and forwarding 502 outcomes remain distinct";
//                                      unknown write outcome: retry only the identical operation with the same id and cas
//   08-domain/spec/08.0-domain.norms.md:130   Idempotency-Key is optional: absent -> "a repeat is a new write"
//   08.0:142                           memory: no row -> the pass; the same print -> the former answer
//   08.0:144                           in_flight: same key already in work -> 409 in flight
//   08.0:145                           write: the target and the claim row in one batch
//   08.0:134                           "a repeat after a lost answer carries the former condition"
// Assumptions: the process is frozen at the start and may thaw at any time; the socket keeps the
// forwarded request while frozen (acceptance A:50 frames exactly this, "should it read it after @thaw");
// one user, one key, one path; the batch is atomic (08.0:145).
// Not modelled: memory retention expiry (08.10 N1.5 idem), holder move (08.0:156 memory not carried),
// 5xx not remembered, 422 key reused (another print is another request), stand restart, cluster-console hop.
// The word "applied" is an effect of the model, not a claim about any implementation.
module edit502_core {
  const FW: int
  const KEYED: bool        // the edit carries Idempotency-Key (08.0:130)
  const IFMATCH: bool      // the edit carries If-Match (08.0:134)
  const RETRY: bool        // the client repeats after 502
  const MEM_ON: bool       // false = mutant, memory row ignored
  const BATCH: bool        // false = mutant, effect before the claim row (crash between)
  const LATE: bool         // true = mutant, the late answer of the process reaches the client after 502
  const DTS: Set[int]

  var now: int
  var seq: int
  var frozen: bool
  var lost: bool           // process lost its socket before reading
  var phase: int -> str    // none | sent | inwork | done
  var sentAt: int -> int
  var procAns: int -> str  // none | ok | 409 | 412 | replay
  var clientAns: int -> str// none | 200 | 502 | 409 | 412
  var effects: int
  var row: bool
  var rowPending: bool     // mutant BATCH=false: effect made, row not yet
  var inflight: bool
  var rev: int
  var base: int -> int
  var t502: int -> int
  var tApply: int -> int
  var tBegin: int -> int
  var t409: int
  var tLate: int

  def A = Set(1, 2)

  action init = all {
    now' = 0, seq' = 0, frozen' = true, lost' = false,
    phase' = A.mapBy(_ => "none"), sentAt' = A.mapBy(_ => -1),
    procAns' = A.mapBy(_ => "none"), clientAns' = A.mapBy(_ => "none"),
    effects' = 0, row' = false, rowPending' = false, inflight' = false, rev' = 0,
    base' = A.mapBy(_ => 0), t502' = A.mapBy(_ => -1), tApply' = A.mapBy(_ => -1),
    tBegin' = A.mapBy(_ => -1), t409' = -1, tLate' = -1,
  }

  action keep_time = all { now' = now, seq' = seq + 1 }

  action send1 = all {
    phase.get(1) == "none",
    phase' = phase.set(1, "sent"), sentAt' = sentAt.set(1, now), base' = base.set(1, rev),
    keep_time, frozen' = frozen, lost' = lost,
    procAns' = procAns, clientAns' = clientAns, effects' = effects, row' = row, rowPending' = rowPending,
    inflight' = inflight, rev' = rev, t502' = t502, tApply' = tApply, tBegin' = tBegin, t409' = t409, tLate' = tLate,
  }

  // The retry of the same edit (same key, same condition) after the 502.
  action retry = all {
    RETRY, clientAns.get(1) == "502", phase.get(2) == "none",
    phase' = phase.set(2, "sent"), sentAt' = sentAt.set(2, now), base' = base.set(2, base.get(1)),
    keep_time, frozen' = frozen, lost' = lost,
    procAns' = procAns, clientAns' = clientAns, effects' = effects, row' = row, rowPending' = rowPending,
    inflight' = inflight, rev' = rev, t502' = t502, tApply' = tApply, tBegin' = tBegin, t409' = t409, tLate' = tLate,
  }

  action thaw = all {
    frozen, not(lost),
    frozen' = false,
    keep_time, lost' = lost, phase' = phase, sentAt' = sentAt, base' = base,
    procAns' = procAns, clientAns' = clientAns, effects' = effects, row' = row, rowPending' = rowPending,
    inflight' = inflight, rev' = rev, t502' = t502, tApply' = tApply, tBegin' = tBegin, t409' = t409, tLate' = tLate,
  }

  // The process is lost before it read the socket: the request never takes effect.
  action loseBeforeRead = all {
    frozen, not(lost),
    lost' = true, frozen' = frozen,
    keep_time, phase' = phase, sentAt' = sentAt, base' = base,
    procAns' = procAns, clientAns' = clientAns, effects' = effects, row' = row, rowPending' = rowPending,
    inflight' = inflight, rev' = rev, t502' = t502, tApply' = tApply, tBegin' = tBegin, t409' = t409, tLate' = tLate,
  }

  action deadline(a: int): bool = all {
    phase.get(a) == "sent" or phase.get(a) == "inwork" or phase.get(a) == "done",
    clientAns.get(a) == "none",
    procAns.get(a) == "none",
    now >= sentAt.get(a) + FW,
    clientAns' = clientAns.set(a, "502"), t502' = t502.set(a, seq),
    keep_time, frozen' = frozen, lost' = lost, phase' = phase, sentAt' = sentAt, base' = base,
    procAns' = procAns, effects' = effects, row' = row, rowPending' = rowPending,
    inflight' = inflight, rev' = rev, tApply' = tApply, tBegin' = tBegin, t409' = t409, tLate' = tLate,
  }

  // The process reads the edit from the socket: 08.0:140-144.
  action begin(a: int): bool = all {
    phase.get(a) == "sent", not(frozen), not(lost),
    if (KEYED and MEM_ON and row) all {
      phase' = phase.set(a, "done"), procAns' = procAns.set(a, "replay"),
      inflight' = inflight, t409' = t409, tBegin' = tBegin,
    } else if (KEYED and MEM_ON and inflight) all {
      phase' = phase.set(a, "done"), procAns' = procAns.set(a, "409"),
      inflight' = inflight, t409' = seq, tBegin' = tBegin,
    } else all {
      phase' = phase.set(a, "inwork"), procAns' = procAns,
      inflight' = (KEYED and MEM_ON), t409' = t409, tBegin' = tBegin.set(a, seq),
    },
    keep_time, frozen' = frozen, lost' = lost, sentAt' = sentAt, base' = base, clientAns' = clientAns,
    effects' = effects, row' = row, rowPending' = rowPending, rev' = rev, t502' = t502, tApply' = tApply, tLate' = tLate,
  }

  // The condition and the batch: 08.0:145 (target + claim row at once).
  action commit(a: int): bool = all {
    phase.get(a) == "inwork", not(rowPending),
    if (IFMATCH and base.get(a) != rev) all {
      procAns' = procAns.set(a, "412"), effects' = effects, rev' = rev, row' = (row or KEYED),
      rowPending' = rowPending, tApply' = tApply,
    } else if (BATCH) all {
      procAns' = procAns.set(a, "ok"), effects' = effects + 1, rev' = rev + 1, row' = (row or KEYED),
      rowPending' = rowPending, tApply' = tApply.set(a, seq),
    } else all {
      procAns' = procAns.set(a, "ok"), effects' = effects + 1, rev' = rev + 1, row' = row,
      rowPending' = KEYED, tApply' = tApply.set(a, seq),
    },
    phase' = phase.set(a, "done"), inflight' = false,
    keep_time, frozen' = frozen, lost' = lost, sentAt' = sentAt, base' = base, clientAns' = clientAns,
    t502' = t502, tBegin' = tBegin, t409' = t409, tLate' = tLate,
  }

  // Mutant BATCH=false only: the row lands later, or the process crashes before it (the row is lost).
  action rowLands = all {
    rowPending,
    rowPending' = false, row' = true,
    keep_time, frozen' = frozen, lost' = lost, phase' = phase, sentAt' = sentAt, base' = base,
    procAns' = procAns, clientAns' = clientAns, effects' = effects, inflight' = inflight, rev' = rev,
    t502' = t502, tApply' = tApply, tBegin' = tBegin, t409' = t409, tLate' = tLate,
  }
  action crashBeforeRow = all {
    rowPending,
    rowPending' = false, row' = false, inflight' = false,
    keep_time, frozen' = frozen, lost' = lost, phase' = phase, sentAt' = sentAt, base' = base,
    procAns' = procAns, clientAns' = clientAns, effects' = effects, rev' = rev,
    t502' = t502, tApply' = tApply, tBegin' = tBegin, t409' = t409, tLate' = tLate,
  }

  action deliver(a: int): bool = all {
    phase.get(a) == "done", clientAns.get(a) == "none", procAns.get(a) != "none",
    clientAns' = clientAns.set(a, match3(procAns.get(a))),
    keep_time, frozen' = frozen, lost' = lost, phase' = phase, sentAt' = sentAt, base' = base,
    procAns' = procAns, effects' = effects, row' = row, rowPending' = rowPending,
    inflight' = inflight, rev' = rev, t502' = t502, tApply' = tApply, tBegin' = tBegin, t409' = t409, tLate' = tLate,
  }
  def match3(p: str): str = if (p == "409") "409" else if (p == "412") "412" else "200"

  // Mutant: a late process answer after the 502 reaches the client.
  action lateDeliver(a: int): bool = all {
    LATE, clientAns.get(a) == "502", procAns.get(a) != "none", tLate < 0,
    tLate' = seq,
    keep_time, frozen' = frozen, lost' = lost, phase' = phase, sentAt' = sentAt, base' = base,
    procAns' = procAns, clientAns' = clientAns, effects' = effects, row' = row, rowPending' = rowPending,
    inflight' = inflight, rev' = rev, t502' = t502, tApply' = tApply, tBegin' = tBegin, t409' = t409,
  }

  // The console must act at the deadline (502), so time does not pass it for a waiting attempt.
  def waiting(a: int): bool =
    (phase.get(a) == "sent" or phase.get(a) == "inwork") and clientAns.get(a) == "none"

  action tick(dt: int): bool = all {
    A.forall(a => not(waiting(a)) or now + dt <= sentAt.get(a) + FW),
    now' = now + dt, seq' = seq + 1,
    frozen' = frozen, lost' = lost, phase' = phase, sentAt' = sentAt, base' = base,
    procAns' = procAns, clientAns' = clientAns, effects' = effects, row' = row, rowPending' = rowPending,
    inflight' = inflight, rev' = rev, t502' = t502, tApply' = tApply, tBegin' = tBegin, t409' = t409, tLate' = tLate,
  }

  action step = {
    nondet a = oneOf(A)
    nondet dt = oneOf(DTS)
    any { send1, retry, thaw, loseBeforeRead, deadline(a), begin(a), commit(a), rowLands, crashBeforeRow,
          deliver(a), lateDeliver(a), tick(dt) }
  }

  val inv_one_effect = effects <= 1
  val inv_no_late_answer = tLate < 0
  val inv_502_not_early = A.forall(a => clientAns.get(a) != "502" or now >= sentAt.get(a) + FW)

  // witnesses: violated iff the ordered situation is reachable
  val wit_applied_after_502 =
    not(t502.get(1) >= 0 and tApply.get(1) > t502.get(1))
  val wit_502_never_applied =
    not(t502.get(1) >= 0 and lost and effects == 0)
  val wit_double_effect_after_502 =
    not(effects >= 2 and t502.get(1) >= 0 and tApply.get(2) > t502.get(1))
  val wit_retry_409_in_flight =
    not(t409 > tBegin.get(1) and tBegin.get(1) >= 0 and clientAns.get(2) == "none" and procAns.get(2) == "409")
  val wit_retry_replay_one_effect =
    not(effects == 1 and t502.get(1) >= 0 and clientAns.get(2) == "200" and procAns.get(2) == "replay" and tApply.get(1) > t502.get(1))
  val wit_retry_412 =
    not(effects == 1 and t502.get(1) >= 0 and clientAns.get(2) == "412" and tApply.get(1) > t502.get(1))
}

module edit502_keyed {
  import edit502_core(FW=5, KEYED=true, IFMATCH=false, RETRY=true, MEM_ON=true, BATCH=true, LATE=false, DTS=Set(1,5)).*
}
module edit502_ifmatch {
  import edit502_core(FW=5, KEYED=false, IFMATCH=true, RETRY=true, MEM_ON=true, BATCH=true, LATE=false, DTS=Set(1,5)).*
}
module edit502_bare {
  import edit502_core(FW=5, KEYED=false, IFMATCH=false, RETRY=true, MEM_ON=true, BATCH=true, LATE=false, DTS=Set(1,5)).*
}
module edit502_bare_noretry {
  import edit502_core(FW=5, KEYED=false, IFMATCH=false, RETRY=false, MEM_ON=true, BATCH=true, LATE=false, DTS=Set(1,5)).*
}
module edit502_mut_nomem {
  import edit502_core(FW=5, KEYED=true, IFMATCH=false, RETRY=true, MEM_ON=false, BATCH=true, LATE=false, DTS=Set(1,5)).*
}
module edit502_mut_nobatch {
  import edit502_core(FW=5, KEYED=true, IFMATCH=false, RETRY=true, MEM_ON=true, BATCH=false, LATE=false, DTS=Set(1,5)).*
}
module edit502_mut_late {
  import edit502_core(FW=5, KEYED=true, IFMATCH=false, RETRY=true, MEM_ON=true, BATCH=true, LATE=true, DTS=Set(1,5)).*
}
