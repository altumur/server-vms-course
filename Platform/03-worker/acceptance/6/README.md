# Acceptance P/03.6 — requests and events of the worker

This English text is the source; the Russian translation `ru/acceptance/6/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`03.6-worker.norms.md`](../../spec/03.6-worker.norms.md) N5. The scenarios were moved from the acceptance of
M10/08 (stage B, ADR-0083 addendum (1): without a change of
behaviour); the numbers of scenarios and steps are the former ones. The preparation, the comparison and the evidence below are the parts of the former README needed by
these scenarios; the forms of foreign doors belong to their owners ([P/05](../../../05-resource/spec/05-resource.norms.md) — the doors of the resource,
[chapter P/06.4](../../../06-console/spec/06.4-console.norms.md) — the doors of the console).

## Preparation of each scenario

The two scenarios are independent. Before each one stop all the processes of the previous
scenario and wait for them, create isolated directories/ports and an empty store: rows, objects,
the id memory of the store, the POST claims of the console, the asked accounting and the commands marks are absent.
Clear the event tree, the mirrors and the index cache, the variables and the replay keys of the runner.
Install the current testsub from the common testdata with its service mark using administrative
rights. There are no units and no user rows yet. The preparation is not a transfer of the state of
the previous scenario and not a check of the installer.

Start the store, a new console testsub and the resource srv-a per the section «Stand» of the common acceptance README. Their doors must be ready;
the resource is registered and available to the console before the first step (in sc. 38–43 the resource is not started before the first step: step 1 `@start resource` starts it, as in the acceptance of P/05). All the processes of this box
use one BOX_ID and server=srv-a; each new process gets a new instance.
Initially there is no controller and no workers: the scenarios start them by the directives @start.
platform/mirror and platform/space are not set; requests for release and for a copy are not prepared.

console — the door of the console testsub from the loopback, access to operations and units is allowed;
resource — the door of the resource srv-a with an admissible identity; store — the door of the store with reading of
testsub/ and objects/testsub/. If the deployment uses TLS, issue the corresponding
certificates and roles per P/02.4 N1.6 (`w2c-ca.sh issue <server> <role>`, the kit `kit`) and the address rule of P/02.4 N1.6;
these scenarios do not replace the check of TLS refusals.
Do not accelerate the deadlines and parameters of testsub: valid_for=30, most_valid=600; the ordinary
ticks of the holder and the reaper are expected, settle=60 by default.

**Scenario 07** (the append) installs the catalogue `testsub` and `testsub2` (the order — «Stand» of the common acceptance README) and starts the controllers and
the workers of both by directives; `store` also reads `testsub2/` and `objects/testsub2/`. The shelves `sh1`
(step 6) and `sh2` (step 19) are put as a store row by the role `console` (`@as console store`), not through the tables door of P/06.1 (N1.6):
the acceptance of the chapter does not depend on the tables door (the log of cammeta-go, lesson 8 № 1). `@as` acts on the step and the following
`store` steps (the dictionary of the common acceptance README), so the nearest following `store` steps 8 and 21 return the role of the scenario —
`testsub2worker`: it reads `testsub2/`, `objects/testsub2/commands/*` and the row-objects `objects/testsub2/marks/*`
(the log of cammeta-python, lesson 8 № 34). Do not accelerate the deadlines of `testsub2`:
settle=30. The worker `testsub2` carries the training handler of the append (the norms of the chapter, N5): the count is the row-object
`objects/testsub2/marks/<unit>` `{count, ranges}`. The scenario sees `fetched` of the heartbeat (chapter 3.4 N1.1, the names `SaidID`) through
the removal of the row by the reaper — the only ground for the removal of an append; steps 19–24 — the own shelf `sh2` in the zone `z2` (`spread_by: zone` does not put two units of one zone on one server) and a unit with a name longer than 40 characters: its rid
the heartbeat names by the hash `#<20 hex>`, the row is removed all the same (a unit name with a comma is not admitted by the grammar of the row check contract). The limits of the body/memory must not hinder the small requests given.

## scenarios.tsv

The format is the dictionary of directives and doors of the «Stand» of the common acceptance README: the doors `console`, `console2`, `resource`, `store`,
`admin` (sc. 10, 38–43), the directives `@start`, `@until`, `@as`, `@key`, `@sleep`, `@sigterm` (in sc. 38 — also of the console), `ASSERT` (sc. 40). Sc. 05 and 07 — 52 steps: 44 HTTP (with @until, @as and @key), six
@start, @sleep and @sigterm; sc. 08 and 09 (ADR-0091) — 23 steps; sc. 10 (coverage audit of P/03) — 16 steps; sc. 38–43 (the second pass of the coverage audit) — 58 steps; in total 11 scenarios / 149 steps (step 05/16 — the event `command` of the base, the VMS request «commands and the device row»; step 39/9 — `command.failed` of a refusal before the call, C03-REFUSED-BEFORE-CALL-EVENT-01) (steps 07/34–36 — (the Architect's decision of 2026-10-20, analysis of the review of stage B 6–7)). Steps 05/7–8 — the row stands 20 s after `performed`
(the lower bound of settle with a margin); 05/11–13 — the heartbeat through the objects door: the mandatory fields and the last heartbeat on SIGTERM
with an empty `status` (mutation check 7cecaf2 № 24, 26, 37).

Steps of the reconciliation of python and go M10/6–11 (2026-10-18):
- **05/11** — the heartbeat of the holder after `performed` carries `command_counts.performed` 1: one call of the action since its start, a repeat
  with the same rid (step 10) does not call the action (chapter 3.4 N1.1; chapter 3.6 N3 «holder's look»; coverage audit of P/03, 2026-10-30).
- **05/12–13** — the heartbeat of the resource carries `units` (`c5` on `w-1`), `waits`, `restore`, `mirror`; `W-1` with `w-1` — 404; the former
  steps 12–13 became 14–15 (E2, E39).
- **07/25–30** — the stamp `about` (`of: c1`) and `by` in the request row; the journal `tally.asked` with `sub`, `target`, `addr`;
  `from: -0` — rid `t1-0-0`, the count `0-3,7-7`; `valid_until` with a manifest without `most_valid` — 400 (E53, E54, E56, E57). The quota
  `per_person: 3` does not hinder: the former rids are removed by step 25.

`Idempotency-Key` and `@key(N)` — per the dictionary. The body of the repeat 05/10 is the same as the original one.

Scenario 05 after performed admits 90 s (settle 60 plus a tick/margin);
the runner must not end the whole scenario earlier than the total budget of its steps. After
the last step wait for the stop of all the created processes, then delete the state.

## Comparison

The forms of expectation — per the dictionary. An expectation of a single code does not require an empty body.

A repeat of a variable inside expect compares its temporary value.
In 05, before sending step 5, the runner binds $rid = r- + the first 16 lowercase hex of SHA-256 of
the exact UTF-8 bytes of the Idempotency-Key issued to this step (testsub has no requests.key).
Step 05/5 accepts only 200 Answered or 202 Queued by the full contract: with 202
queued equals the precomputed $rid; with 200 answered relates to c5 and the digest of the submitted
body. Another 2xx is not permitted by the contract. So a fast answer does not change the variables of the following steps. The directives are not sent
to the server as HTTP. The full answer is additionally checked by the contract of its owner:
the store — P/01.1, the units — P/06.1, the doors of the resource — P/05 N2, the other doors — [chapter P/06.4](../../../06-console/spec/06.4-console.norms.md) N2. In particular, answered
with @any in the TSV is still bound to be a full mark of one of the three forms of AnsweredMark.

## Evidence outside TSV

These are tasks for the implementation/stand, not checks already performed:

| Area | Counterexample and the required observation |
|---|---|
| Suppression | suppress gives out the first one and the total (from the row «Events» of the former README) |
| Requests | Two contenders for begun: no more than one call; a lost answer of put_new: zero calls by assumption. A foreign unit/digest is not overwritten; unknown does not start a repeat |
| Outcome and cleanup | An old CAS of the reaper does not overwrite performed. A late answer replaces unknown with late. An error of publishing the mark leaves the row; the console does not delete the mark |

Additional probes of Kimi 33: The outcome refused after a call always has error, never performed; check both the pass and the form of the mark. These are tasks of a check of the norms/stand, not a statement about the execution of an implementation.

Additional check of the class of errors of run 36 (Kimi), by reading: suppress is always divided by tree/unit/epoch/kind/class; by is a non-empty list of strings, t/id/repeats/since/until are forbidden. unit is taken from the path, an absent selected field differs from null; without by only the five service fields are excluded. Reconcile structured JSON values, two different units and epochs. The deadline of kept is max(60, ttl) from the moment when the holder saw that the request row is no longer there, and not earlier than valid_until ([the request and its mark contract](../../../common/contracts/request-mark.md) `kept`; C03-KEPT-FROM-ABSENT-01).

Additional case R38-03/04/05:

- The append, P/03.6-04 (the holder) and P/06.4-07 (the console) (scenario 07 — the path request → data → removal → repeat; the rest below — by reading; the loading of the key
  is checked by the cases of P/02.1 `requests_outcome_*`, the debt of the product — in the specification progress note (for people)): an admissible unit testsub2/tallies/t1, the request {unit:"t1",from:1,to:2}, rid=t1-1-2, the reserve asked. The holder reconciles the data and reports fetched; objects/testsub2/commands/t1-1-2 is absent before/after. After the local settle the console removes the read version of the row by CAS and releases the rid in asked by CAS, keeping a concurrently added rid. A CAS conflict/an unknown fetched does not permit counting the removal as done. A repeat after the removal again reconciles the data without begun and does not repeat the range already present. Without fetched the mark expired/unknown is not created and age alone does not release the reserve. free_ask does not get into this branch; a body with `action` from `elsewhere` in the append profile — the same branch: the holder reconciles the data and reports fetched (steps 07/34–36; (the Architect's decision of 2026-10-20, analysis of the review of stage B 6–7)). This is a separate case of the boundary of ADR-0054, not a performed run rec and not a promise of a single call for the append.

The form of the consumer of the append in `testsub2` (in the bytes of the manifest since 2026-10-17, ADR-0054 addendum 2026-10-17; the field `action` —
analysis of the review of stage A 6–7, № 14):

```yaml
requests:                     # the append profile of ADR-0054: the key from the data, the result — fetched of the holder, no mark
  free: true
  schema: {type: object, required: [unit, from, to], additionalProperties: false,
           properties: {unit: {type: string}, from: {type: integer}, to: {type: integer}, action: {type: string}}}
  key: "{unit}-{from:int}-{to:int}"
  outcome: fetched
  per_person: 3
  settle: 30
  ttl: 3600
  stamp: [by, at, about]
  journal: tally.asked
  elsewhere: [recount]
# the holder of the unit tallies adds to its count the number of integers of [from, to] that the count has not yet covered
# (the covered ranges — in the row-object objects/testsub2/marks/<unit>, the norms of the chapter, N5), and names the rid in fetched of the heartbeat; a repeat by the data
# adds nothing
```

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

The generic meanings of `@sleep` and `@until` are defined in the [common stand protocol](../../../common/acceptance/README.md#dictionary-of-directives-and-doors). Scenario-specific wait steps, durations and reasons are kept in the [judge-only case instructions](sleeps.cases.md).

## Scenarios 08 and 09 (ADR-0091)

The preparation is as for sc. 07: the catalogue `testsub` and `testsub2`, the doors `console` and `console2`, the resource `srv-a`; the workers `testsub`
carry the training orderer, the workers `testsub2` — the training state holder (the norms of the chapter, N5 `tally_order`,
`tally_result`).

- **08-orders** — the counter `c8` with `start: 1000` at its start orders the row `testsub2/tallies/testsub-c8` (`made.by` —
  `testsub`, `born` is present); the row `testsub-c9`, put before the start bypassing the writer without `made`, the orderer does not write (the outcome
  `taken`); `c7` with `start: 1` does not order. Step 9 — the counts of the heartbeat since its start: `creates.created` 1, `taken` 1. After
  `@sigterm` and a new start — a new start event: the row of its own `made` is extended (`revision` 2), the heartbeat of the new
  instance — `extended` 1, `taken` 1. The controller `testsub2` is not started: the order row is not placed.
- **09-state** — step 4: the worker `t-1` takes the place `sh1` before the assignment — the heartbeat carries `shelf: sh1` before `t1` is created (P/03.2 N3
  «lease_step()» step 6; the Architect's decision of 2026-10-27); the holder of the count `t1` writes under epoch 1 the state `result` `{state: "open"}` with `born` and `revision` of the row;
  the console shows it in `configured[].state` (P/06.1 N2 «State in the answer»).

Checked by reading: the epoch guard and `not_after` of the order write, a repeat after a physical cleanup and the move of the clock (P/01.1 sc. 28 —
only the edges), the fencing of the holder in the middle of a write (after the loss of the name — sc. 10), the cursor not more often than `STATE_EVERY`.

## Scenario 10 (coverage audit of P/03, 2026-10-30)

**10-slot-swap** — the preparation of sc. 09 (the shelf — through the door `admin`); the holder `t1` under epoch 1
has written `result`; the runner rewrites the slot row `testsub2/slots/t-1` to the `holder` of the box `otherbox` through the door `admin` without
`cas` (on top of the renewal, P/01.1 N1 `cas`). The lease step of the worker sees a foreign `holder` — `release_name()`, the fencing (P/03.2
N3 «lease_step()» step 1): exactly one row `worker.name_taken` in `audit/testsub2worker` (once per episode; the repeated
search — NameOnAnotherBox, does not write it), the version of the slot does not change, there is no heartbeat any more (`ts` as before, P/03.2 N3
«nobody and getting the name back»), the state row `result` is of the same version — the fenced holder does not write it (N3 «write state»).

## Scenarios 38–43 (coverage audit of P/03, the second pass of Gemini, 2026-10-30)

The report `gemini/audit-coverage` `fad5fa2ba`, the drafts G07, G08; analysis by the Specification. The request rows `testsub/requests/<rid>`,
the order rows `testsub2/tallies/*` and the state row are put by the runner through the door `admin` bypassing the writers (as in sc. 10). The request row is
the form of the family `requests` (P/06.4 N1.5): `unit`, the body field `add` as a string, `digest` — SHA-256 of the JCS of the client body without the deadline
(`{"add":5,"unit":"c38"}` → `46367a34…`, computed by python), the stamps `by`, `at`; rid — the form `r-` + 16 hex, as at the door (sc. 05).
- **38-request-expired-holder** — the deadline of the request (`valid_until: 100`) has long passed: the holder writes before the call the mark `expired`
  create-once with `ended_by: holder` (the request and its mark contract `no_begun`), the heartbeat — `command_counts.expired` 1 (chapter
  3.4 N1.1). The console is stopped (`@sigterm console`) before the row is written: the reaper marks an abandoned request with the same outcome
  (`ended_by: reaper`, P/06.4 N3 `sweep`), and without the stop the outcome of the race «holder or reaper» is not determined.
- **39-request-beyond-most-valid** — the deadline is beyond `most_valid` (600 s at `testsub`; `valid_until` — the year 2100): the mark `refused`
  with `error` and `ended_by: holder`, `command_counts.refused` 1; the reaper does not mark such a row — the deadline has not passed. Step 9 — the event
  `command.failed` of a refusal before the call in the bucket of the unit under the epoch of the holder (`outcome: refused`, `error`, without `reply`; N3
  «holder's look», as the witness — the Architect's decision of 2026-10-30, questions of norms of the Gemini audit, P/03 item 3,
  C03-REFUSED-BEFORE-CALL-EVENT-01); the epoch of the unit is taken before the row (step 5).
- **40-request-row-unreadable** — the request row of its own unit is not readable by its form (`valid_until: "x"`, the outcome of the family
  `requests` at `<s>worker`, RM-G01): there is no mark, the row is not removed (the reaper neither marks nor removes an unreadable one), `garbled_rows`
  of the heartbeat ≥ 1 (`ASSERT`; before the row — 0).
- **41-order-tombstones** — two order rows before the start are tombstones of its own `made` (`deleted: true`, `made.by: testsub`):
  at `testsub-c41` `made.gone` is the year 2100 (the start event is not later than `gone + 60`) — the outcome `gone`, no write, the version is the same; at
  `testsub-c42` `made.gone` 1000 (the event is later than `1000 + 60`) — a creation over the tombstone: `revision` 2, a new `born`, `made`
  of the orderer, no `deleted`; the heartbeat — `created` 1, `gone` 1 (N3 «order» step 4; the row check contract
  «Customer row: made» `tombstone`).
- **42-order-unchanged-never** — its own order row with `until: "0"` (without a deadline, `placement.ends` `testsub2`) and `made.at` in
  the year 2100, `made.keep = made.at + 720` = 4102445520 (computed by python): the former `until` = never is not touched, `made.at` =
  max(former, t_E) and `made.keep` = max(former, `made.at` + 720) are as before — the outcome `unchanged`, no write (`revision` 1).
- **43-state-unreadable** — the preparation of sc. 09 (the shelf — through the door `admin`): the holder has written `result` under epoch 1; the runner
  rewrites the state row not by the form (without `cas`); the worker `t-1` is restarted — the new holder under epoch 2 reads
  the unreadable state as absent and writes `result` anew (`state.outcomes.tsv` `<s>worker`; the norms of the chapter, N5
  `tally_result`: «if there is no current result»). Without spoiling, the state in effect survives the move and would not
  be rewritten (the row check contract «Unit state» `acts`).

Not taken from the second pass: the closing by the holder of a foreign `begun` without an outcome (the deadline of the request row relative to the clock of
the stand cannot be set: a far deadline runs into `most_valid`, a passed one — into the reaper; the order of the checks is now set by the norm —
`most_valid` before the closing of a foreign `begun`, then the deadline, as the witness: N3 «holder's look», C03-REQUEST-CHECK-ORDER-01,
the Architect's decision of 2026-10-30, P/03 item 2); a refusal of an order by a `fixed` field of its own row (the norm: its own row is extended
only by the fields `until`, `made.at`, `made.keep` — `of` from F is not written, the outcome would be `extended`, not `refused`).

SDK tests at the seams are in [seams.tsv](seams.tsv); their adapter contract is [forms/README.md](../../forms/README.md). They supplement the process scenarios and do not change the counts above or replace a reading witness they do not execute.

s5-state-start-born retains the current born from the accepted start and exact opaque epoch_index="9007199254740993" after another life is reread. That index is not gen/epoch and is not narrowed. The seam input and expectation remain unchanged.
