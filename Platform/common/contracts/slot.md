# The slot contract: states of the slot row and terms

This English text is the source; the Russian translation `ru/contracts/slot.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13): the state of a slot row is judged by the worker, the controller, the console and
the agent — a contract, not copies in chapters; layout audit A-04, the Architect's decision of 2026-10-25). The owner is chapter
[P/03.2](../../03-worker/spec/03.2-worker.norms.md) N1.4 (the row `<sub>/slots/<name>`). Participants: the worker — capture and
renewal (P/03.2 N3); the controller — the slot judge, the leaving of units, the order ([P/04](../../04-controller/spec/04-controller.norms.md)
N1.4, N3); the console — `WorkerRow.released`, `slot_taking`, `slot_until`, `slot_garbled` ([P/06.5](../../06-console/spec/06.5-console.norms.md)
N2, N3 «/servers»), the drain ([P/06.6](../../06-console/spec/06.6-console.norms.md)); the agent — the liveness of a worker in the domain
([P/09.1](../../09-agent/spec/09.1-agent.norms.md) N1.4); the pool — [the pool contract](pool.md) «Live worker».

Moved from P/03.2 N1.4 (`states`, `SLOT_TERM`, `TORN_STILL`) without a change of behaviour; P/03.2 and the readers refer
here. The form of the row, the name and the order of names are with the owner and in [the slot name contract](slot-name.md); the age of the observed version is
[the observation contract](observation.md) «Observation of a version».

Normative keywords follow [the course canon](../NORMATIVE-TERMS.md).

## Form

The row `<sub>/slots/<name>` is the family `slots`: the form `Platform/03-worker/data/slots.schema.json`, the outcomes
`Platform/03-worker/data/slots.outcomes.tsv` ([form](../../03-worker/data/slots.schema.json),
[outcomes](../../03-worker/data/slots.outcomes.tsv)); the fields `holder`, `until`, `released`, `gen`, `server` are there and in P/03.2
N1.4.

## States

```yaml
states:
  held:      a readable slot, holder ≠ "", released = false, gen ≥ 1, the age of the observed version < SLOT_TERM
  lapsed:    the same fields, the age of the observed version ≥ SLOT_TERM; by itself it does not permit a capture
  released:  released = true
  taking:    released = taking — a capture in progress: for all readers not live (as released), for the capture — free
             (as released: the capturer could have died between the writes); the controller moves its units away only after SLOT_TERM
             of an unchanged version (P/04 N3 «leaving»); every «released» below without a value means released ≠ false;
             a readable row without the field released — as released ≠ false (not held; for the capture — as released), without
             the field holder — as holder = "" (analysis of the review of stage B 3–5, № 6)
  torn:      the row does not read: until is not a number or not finite, gen is not an exact decimal integer in 1..9007199254740991;
             a finite until in the past/future relative to the judge does not make the row torn
```

## Terms

```yaml
SLOT_TERM: 45          # the slot term, s
TORN_MARGIN: 5         # s; independent extra observation margin for a torn row, not HOLD_SKEW
TORN_STILL: SLOT_TERM + TORN_MARGIN  # unchanged observation required before rewriting a torn row with readable gen at a capture, where there is no gone evidence; a release on gone does not require it
```

## Vectors

The package [`slot`](../vectors/slot/README.md): the judgement judge(row, age) → `held`, `lapsed`, `released`, `taking`, `torn` (with
`takeable`) — a row per state, the boundaries `SLOT_TERM` and `TORN_STILL`, `until` beyond binary64 (C140-SLOT-TIME-01). The boundary
of heartbeat freshness is the package [`fresh-age`](../vectors/fresh-age/README.md) of the observation contract; the transitions are acceptance scenarios of P/03.2,
P/04 and reading.

