# Production obligations for common contracts

This English text is the source; the Russian translation `ru/contracts/production-obligations.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

ADR-0130 Addendum (10) selects Q1–Q6 and MB1–MB4. Spec103 owns this common carrier; the process and data owners remain those named in each contract. These obligations supplement existing correctness, security, clock and outcome rules.

## Finite budgets and observable completion

Each implementation MUST declare finite positive budgets for applicable input and output phases, dependency waits, lock acquisition and lock holding, cancellation, shutdown and accepted-work completion. This includes slow or stalled readers/writers, backups, exports, dependency outages and interrupted cleanup. It MUST declare finite memory, disk, descriptor, queue and admission budgets and the workload units to which they apply: bytes, records, identifiers, marks, tombstones, generations, buckets and queued operations. Queue saturation MUST produce the owner's existing visible refusal/backpressure; unbounded buffering is not completion. Resource accounting includes background work and retained correctness state.

These are required declarations, not new fixed constants or environment flags. Exact positive values, workload sizes, capacity, clock bounds, instrumentation and fault hooks are implementation/environment qualification inputs. Existing limits remain in force; an implementation budget does not narrow a valid protocol value or forget required state. A bounded cache MUST preserve mandatory replay identity in durable state. Cleanup eligibility is proved before bounded reclamation; protected state is never sacrificed to meet capacity. A stalled dependency cannot indefinitely hold a shared lock or prevent cancellation/stop beyond the respective declared budgets. Partial output, a lost write answer and an interrupted barrier retain their existing owner outcomes and cannot become a successful complete result.

The existing P/01 budgets do not qualify common GC, output, cancellation or other processes. Existing qualification groups remain NOTEXEC, numeric budgets NULL and provider UNKNOWN until their separate factual inputs and execution are supplied.

## Public acceptance and missing bindings

The public sequences are [production vectors](../vectors/production-obligations/README.md). Runner owns executable probes and negative controls; these declarations are neither Runner code nor a new public test language. A measurement records the exact Source revision, owner, input, environment, fault phase, declared budget and measured observable. Missing executable/context/fault/budget/capacity is MissingBinding/NOTEXEC, never PASS. A timeout of the probe itself is not evidence of bounded implementation completion. Negative controls must violate the stated observable while a faithful positive control meets it. No model result or bounded abstract safety check qualifies real barriers, disk capacity, clocks or native effects.

Existing-norm probe obligations include `whole_too_large` at reconstructed JCS whole size, `keys_sealed` and `sealed` at their existing security boundaries, and the owner-native probe roster: actual filesystem barriers, startup contention, clock discontinuities, slow output, cancellation/stop, capacity and dependency failures. Preserve the existing acceptance/function forms and outcome words; a missing native binding stays explicit.
