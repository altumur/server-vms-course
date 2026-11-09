// C6: a regular stop of the domain console with a forwarded edit and an open stream.
// Anchors (slice cbf02230):
//   10-domain-console/lifecycle.md:63-68   "Signals and readiness" says nothing on a stop
//   10-domain-console.norms.md:186         answer: 502 on a break and on silence (forwarding)
//   forwarding.md:85-87                    no answer within FORWARD_WAIT -> 502 did not answer
//   forwarding.md:89                       FORWARD_WAIT default 5 s (Domain doors table)
//   gate-and-pass.md:596                   a stream has no limit
//   production-obligations.md:9            budgets for "shutdown and accepted-work completion" are required
//                                          of each implementation; P/10 carries no link to it (finding M1)
// The silent norm is encoded as nondeterminism: POLICY=0 admits every reaction of the process to
// SIGTERM the text does not exclude, including exit at once and waiting forever.
// POLICY=1 is the control rule (the proposal of C6, not in the text): drain, then exit at the budget.
// The model does not say what any implementation does.
// Not modelled: refusal of new requests in stopping, the port, client retries (see edit_after_502),
// the domain process crashing, more than one edit (independent per edit).
module shutdown_core {
  const FW: int            // FORWARD_WAIT
  const POLICY: int        // 0 = text of the norm (silent); 1 = control: drain + budget
  const STOP_BUDGET: int   // budget of the stop for POLICY=1
  const STOP_H: int        // the bound H of inv_stop_bounded
  const DTS: Set[int]

  var now: int
  var proc: str            // running | stopping | exited
  var termAt: int
  var edit: str            // none | forwarded
  var sentAt: int
  var applied: bool        // effect at the process `domain` (independent of the console)
  var ready: bool          // the process answer reached the console
  var clientSaw: str       // none | 200 | 502 | break
  var stream: str          // none | open | closed
  var seq: int
  var tTerm: int
  var tApplied: int
  var tBreak: int

  action init = all {
    now' = 0, proc' = "running", termAt' = -1, edit' = "none", sentAt' = -1,
    applied' = false, ready' = false, clientSaw' = "none", stream' = "none",
    seq' = 0, tTerm' = -1, tApplied' = -1, tBreak' = -1,
  }

  action forward = all {
    proc == "running", edit == "none",
    edit' = "forwarded", sentAt' = now,
    seq' = seq + 1,
    now' = now, proc' = proc, termAt' = termAt, applied' = applied, ready' = ready,
    clientSaw' = clientSaw, stream' = stream, tTerm' = tTerm, tApplied' = tApplied, tBreak' = tBreak,
  }

  action openS = all {
    proc == "running", stream == "none",
    stream' = "open",
    seq' = seq + 1,
    now' = now, proc' = proc, termAt' = termAt, edit' = edit, sentAt' = sentAt, applied' = applied,
    ready' = ready, clientSaw' = clientSaw, tTerm' = tTerm, tApplied' = tApplied, tBreak' = tBreak,
  }

  // The process `domain` is a separate process: it may apply the edit at any moment after it was
  // forwarded, even after the console left (P/10 N1.3 "the process checks ... and executes").
  action apply = all {
    edit == "forwarded", not(applied),
    applied' = true, tApplied' = seq,
    seq' = seq + 1,
    now' = now, proc' = proc, termAt' = termAt, edit' = edit, sentAt' = sentAt, ready' = ready,
    clientSaw' = clientSaw, stream' = stream, tTerm' = tTerm, tBreak' = tBreak,
  }

  action answerArrives = all {
    applied, not(ready), proc != "exited",
    ready' = true,
    seq' = seq + 1,
    now' = now, proc' = proc, termAt' = termAt, edit' = edit, sentAt' = sentAt, applied' = applied,
    clientSaw' = clientSaw, stream' = stream, tTerm' = tTerm, tApplied' = tApplied, tBreak' = tBreak,
  }

  action deliver = all {
    ready, clientSaw == "none", proc != "exited",
    clientSaw' = "200",
    seq' = seq + 1,
    now' = now, proc' = proc, termAt' = termAt, edit' = edit, sentAt' = sentAt, applied' = applied,
    ready' = ready, stream' = stream, tTerm' = tTerm, tApplied' = tApplied, tBreak' = tBreak,
  }

  action deadline502 = all {
    edit == "forwarded", clientSaw == "none", not(ready), proc != "exited",
    now >= sentAt + FW,
    clientSaw' = "502",
    seq' = seq + 1,
    now' = now, proc' = proc, termAt' = termAt, edit' = edit, sentAt' = sentAt, applied' = applied,
    ready' = ready, stream' = stream, tTerm' = tTerm, tApplied' = tApplied, tBreak' = tBreak,
  }

  action term = all {
    proc == "running",
    proc' = "stopping", termAt' = now, tTerm' = seq,
    seq' = seq + 1,
    now' = now, edit' = edit, sentAt' = sentAt, applied' = applied, ready' = ready,
    clientSaw' = clientSaw, stream' = stream, tApplied' = tApplied, tBreak' = tBreak,
  }

  // Control rule: on a stop the console closes streams (bytes and closure, forwarding.md:123).
  action closeOnStop = all {
    POLICY == 1, proc == "stopping", stream == "open",
    stream' = "closed",
    seq' = seq + 1,
    now' = now, proc' = proc, termAt' = termAt, edit' = edit, sentAt' = sentAt, applied' = applied,
    ready' = ready, clientSaw' = clientSaw, tTerm' = tTerm, tApplied' = tApplied, tBreak' = tBreak,
  }

  def drained = (edit != "forwarded" or clientSaw != "none") and stream != "open"
  def budgetOver = now >= termAt + STOP_BUDGET

  // POLICY=0: the process may exit at any time; POLICY=1: only when drained or at the budget.
  action exitProc = all {
    proc == "stopping",
    POLICY == 0 or ((drained or budgetOver) and not(ready and clientSaw == "none")),
    proc' = "exited",
    val brk = edit == "forwarded" and clientSaw == "none"
    all {
      clientSaw' = if (brk) "break" else clientSaw,
      tBreak' = if (brk) seq else tBreak,
    },
    stream' = if (stream == "open") "closed" else stream,
    seq' = seq + 1,
    now' = now, termAt' = termAt, edit' = edit, sentAt' = sentAt, applied' = applied,
    ready' = ready, tTerm' = tTerm, tApplied' = tApplied,
  }

  // Urgency: the 502 at FW; for POLICY=1 the exit at the budget.
  def tickOk(dt: int): bool = and {
    not(edit == "forwarded" and clientSaw == "none" and not(ready) and proc != "exited")
      or now + dt <= sentAt + FW,
    not(POLICY == 1 and proc == "stopping") or now + dt <= termAt + STOP_BUDGET,
    // Control: an answer that reached the console is relayed at once (not stored over time).
    not(POLICY == 1 and ready and clientSaw == "none" and proc != "exited"),
  }

  action tick(dt: int): bool = all {
    tickOk(dt),
    now' = now + dt,
    seq' = seq + 1,
    proc' = proc, termAt' = termAt, edit' = edit, sentAt' = sentAt, applied' = applied,
    ready' = ready, clientSaw' = clientSaw, stream' = stream, tTerm' = tTerm, tApplied' = tApplied, tBreak' = tBreak,
  }

  action step = {
    nondet dt = oneOf(DTS)
    any { forward, openS, apply, answerArrives, deliver, deadline502, term, closeOnStop, exitProc, tick(dt) }
  }

  val inv_stop_bounded = proc == "stopping" implies now - termAt <= STOP_H
  val inv_no_break_on_applied = clientSaw == "break" implies not(applied)
  // Not "some value": exit itself writes "break", so a break does not count as an answer.
  val inv_edit_answered_at_exit =
    (proc == "exited" and edit == "forwarded") implies (clientSaw == "200" or clientSaw == "502")
  val inv_no_early_502 = clientSaw == "502" implies now >= sentAt + FW

  // witnesses (violated iff the ordered situation is reachable)
  val wit_term_break_then_applied =
    not(tTerm >= 0 and tBreak > tTerm and tApplied > tBreak and clientSaw == "break")
  val wit_applied_then_term_break =
    not(tApplied >= 0 and tTerm > tApplied and tBreak > tTerm and clientSaw == "break")
  val wit_stop_hangs_on_stream =
    not(proc == "stopping" and stream == "open" and tTerm >= 0 and now - termAt >= 100)
  val wit_drained_exit =
    not(proc == "exited" and edit == "forwarded" and clientSaw != "none" and tBreak < 0 and tTerm >= 0)
}

module shutdown_norm {
  import shutdown_core(FW=5, POLICY=0, STOP_BUDGET=0, STOP_H=100, DTS=Set(1,5,100)).*
}
// Control: drain with a budget above FORWARD_WAIT (parameter, no number proposed): at equality
// the exit and the 502 race for the same instant, so the budget here is FW + 1.
module shutdown_ctrl {
  import shutdown_core(FW=5, POLICY=1, STOP_BUDGET=6, STOP_H=6, DTS=Set(1,5,6,100)).*
}
// Mutant of the control: the stop budget is below FORWARD_WAIT.
module shutdown_mut_short {
  import shutdown_core(FW=5, POLICY=1, STOP_BUDGET=3, STOP_H=3, DTS=Set(1,2,3,5,100)).*
}
