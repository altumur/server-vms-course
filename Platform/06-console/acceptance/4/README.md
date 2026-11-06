# Acceptance P/06.4 — requests and events of the console

This English text is the source; the Russian translation `ru/acceptance/4/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`06.4-console.norms.md`](../../spec/06.4-console.norms.md) N5. The scenarios were moved from the acceptance of
M10/08 (stage B, ADR-0083 addendum (1): without a change of
behaviour); the numbers of scenarios and steps are the former ones. Scenarios 05 (a request with a holder) and 07 (the append) of M10/08 are in
[the acceptance of chapter 3.6](../../../03-worker/acceptance/6/README.md); 01, 02, 08 of M10/08 (the objects door, the events query, the paths
of the resource) are in [the acceptance of P/05](../../../05-resource/acceptance/README.md). The preparation, the comparison and the evidence below are the parts
of the former README needed by these scenarios; the forms of foreign doors belong to their owners ([P/05](../../../05-resource/spec/05-resource.norms.md) —
the doors of the resource, [P/01.1](../../../01-store/spec/01.1-store.norms.md) — the store).

## Preparation of each scenario

The scenarios are independent. Before each one stop all the processes of the previous
scenario and wait for them, create isolated directories/ports and an empty store: rows, objects,
the id memory of the store, the POST claims of the console, the asked accounting and the commands marks are absent.
Clear the event tree, the mirrors and the index cache, the variables and the replay keys of the runner.
Install the current testsub from the common testdata with its service mark using administrative
rights. There are no units and no user rows yet. The preparation is not a transfer of the state of
the previous scenario and not a check of the installer.

Start the store, a new console testsub and the resource srv-a per the section «Stand» of the common acceptance README. Their doors must be ready;
the resource is registered and available to the console before the first step. All the processes of this box
use one BOX_ID and server=srv-a; each new process gets a new instance.
There is no controller and no workers: the scenarios do not start them. There are no third-party daemons and timers able to start a holder in scenario 04.
platform/mirror and platform/space are not set; requests for release and for a copy are not prepared.

console — the door of the console testsub from the loopback, access to operations and units is allowed;
resource — the door of the resource srv-a with an admissible identity; store — the door of the store with reading of
testsub/ and objects/testsub/. If the deployment uses TLS, issue the corresponding
certificates and roles per P/02.4 N1.6 (`w2c-ca.sh issue <server> <role>`, the kit `kit`) and the address rule of P/02.4 N1.6;
these scenarios do not replace the check of TLS refusals.
Do not accelerate the deadlines and parameters of testsub: valid_for=30, most_valid=600; the ordinary
ticks of the holder and the reaper are expected, settle=60 by default.

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors): the doors `console`, `console2` (sc. 07, 08, 11, 12), `resource`, `store` (with `@as` — sc. 08, 09), `admin` (sc. 11, 12), the directives `@until`, `@sleep`, the request form `@header`. In total 9 scenarios / 120 steps (sc. 03 steps 16–20 — the segment note `to`, ADR-0117 addendum (3) item 2; sc. 04 steps 16–21 — a submitted deadline -1, 1e-12, 1000.1234: 202 and a write truncated downwards to ms, a negative one — 0, C06-DEADLINE-PRECISION-33-01; sc. 07 `07-request-gone` — 11 steps, ADR-0091 addendum (11) item 4: requests of `testsub2` with `per_person` 3, the deletion of the addressee unit — the outcome `gone` of the reaper, the row is removed, the reserve is released: the fourth request is 429 before and 202 after; sc. 11 `11-request-expired` — 15 steps, below); all HTTP (with @until and @key).

Steps of the reconciliation of python and go M10/6–11 (2026-10-18):
- **03/9** — `user: operator` of the note (E60).
- **04/8–15** — the journal `request.asked` at a manifest without `requests.journal` (`$b` — the path of its bucket); `GET /buckets/audit/console` —
  JSON Lines `application/x-ndjson`; `Range: bytes=-5` — 206, `bytes=5-2` — 416; `Idempotency-Key` `.` and `a,b` — 202;
  `valid_until: 0` is written as `"0"` (E28, E33, E48, E52, E58).
- **06/5–7** — a body that is not JSON — 400 without `fault`; `valid_until: null` — 400; a deadline beyond `most_valid` to an absent unit —
  400 earlier than 404 (E49–E51).

`Idempotency-Key` and `@key(N)` — per the dictionary. The body of the repeat
04/3 is the same as the original one. The presence of the header at /marks does not create a promise
of replay memory for a note.

Scenario 04 admits 150 s until the mark of the reaper, then 90 s until the removal of the row;
the runner must not end the whole scenario earlier than the total budget of its steps. After
the last step wait for the stop of all the created processes, then delete the state.

## Coverage audit of P/06, second pass (Gemini)

Sc. 08–10 (`audit-coverage-gemini` 0a5ae79f9) — likewise, each on its own empty stand.
- Sc. 08 — `testsub2` (the append, `requests.key` `{unit}-{from:int}-{to:int}`, `per_person` 3): a body with the same rid `t1-0-1`
  and a different digest (the field `action` is part of the digest of the kind worker) — 409 `exists`, the row is the earlier one (without `action`), the rid is in the accounting
  (N3 «file a request» steps 3–4); the accounting of the person `operator` is `testsub2/asked/06e55b633481f7bb` (`sha256("operator")[:16]`),
  the role `console` reads and writes it; `DELETE` of the accounting — 200 `{cleared: true}` (OpenAPI `Cleared`), there is no row, a repeat — 404 (N4);
  an accounting read not by the form (`at: "x"`) — 429 without a change of the accounting and without a request row (N3 step 3, the outcome of the family `asked`).
- Sc. 09 — `testsub` (the ordinary profile, rid `r-<sha16(Idempotency-Key)>`; the key is set by `@header`, so the rid is known before
  the filing): the marks `objects/testsub/commands/<rid>` are put by the role `testsubworker` bypassing the holder before the filing (N3 step 2: the mark
  is already there). Another `unit` — 409 `spent`; a mark not by the form (`digest` is not 64 hex) — 409 `spent`, the mark is the earlier one; the same `unit`
  and digest with the outcome `expired` (the form `no_begun`) — 200 `answered` with this mark; there is no request row in any case.
  The keys and the rids (`sha256(key)[:16]`, computed by python): `acc-spent-other` — `r-7f0cd6bacd621c87`, `acc-spent-garbled` —
  `r-7c4c0556d5a0c07c`, `acc-answered` — `r-bebf2f46796986bd`; the digest of the body `{"unit": "c4", "add": 1}` of the kind client is
  sha256 JCS `{"add":1,"unit":"c4"}` = `e83c1a0bfffbff5eb0a0de9119b1ab36a9591b374b4a655621da34e02f85a969` (the rule — the vectors
  `request-digest`).
- Sc. 10 — the numeric query parameters of `GET /events` of the console (the guard and transfer contract «Numeric query parameters»,
  C06-EVENTS-QUERY-LEXEME-162-01): after URL decoding `limit` is an integer lexeme `^-?(0|[1-9][0-9]*)$`, then 1…10000 (the OpenAPI
  of the lesson); `from`, `to` — time `^(0|[1-9][0-9]*)(\.[0-9]+)?$`; otherwise 400 with `detail` — the name of the parameter; `limit=%31` and
  `to=1.5` — 200. The lexemes of `from` (`+1`, `%2B1`, `%201`, `1e3`, `%31`) — sc. 02 of [the acceptance of P/05](../../../05-resource/acceptance/README.md).

## Append without a holder (sc. 11)

The VMS request «request term», the Architect's decision of 2026-10-29; after the pattern of sc. 04 and sc. 07 `07-request-gone`. There are no workers on the stand, the unit `t1`
exists — nobody serves the request, `gone` does not come. `testsub2`: `per_person` 3, `settle` 30, `ttl` 3600, so
the boundary is the age of 3660 s. The deadline is not waited for: the age of a row is counted from its `at` (the request contract, the key `ttl`), and step 9 through the door
`admin` replaces by `cas` the row `$r1` with the same row with the old `at` `1700000000` (the same technique as in sc. 38 of [the acceptance of chapter
3.6](../../../03-worker/acceptance/6/README.md)); the accounting of the person remains real, from steps 4–6. The row `$r2` remains young:
it has no mark (step 12) and it stands (step 14) when `$r1` is already removed. Step 11 — the row stands right after the mark: `settle` runs from
the first read of the mark. Step 15 repeats the refusal of step 7 while the reserve is not released: the moment when the rid leaves the accounting is from
the confirmation of the mark to the removal of the row (the rule «States…»: `settle` bounds the row, not the hold of `per_person`), so
the occupancy of the reserve between steps 10 and 13 is not judged. The boundary ε, `fetched`, the mark `gone` earlier, `ttl` 0 and a late `fetched` are
the vectors [`reap`](../../vectors/reap/README.md): there is no holder on the stand, and the boundary cannot be observed through a door to within ε.

## Deadline of table rows (sc. 12)

ADR-0094 step 3b. The table `scraps` of the manifest `testsub2`: `delete_after` 35, the fields `name`, `note`; `shelves` has no deadline key. The deadline is not
waited for shorter and is not forged: the age judges the observed version, not the stamp (P/06.4 N3 `tables`), so the technique with the old
`at` of sc. 11 is not here. The tick of the reaper is 30 s, the first pass after the write (the moment `t1`) comes not later than 30 s.
- Step 4 — `@sleep 31`: the first pass has surely happened. A reaper that removes the row at the first look gives 404 at step 5.
- Step 6 writes `s2` anew: a new version. Step 7 waits for the removal of `s1` — the pass `t1 + 60`: at `t1 + 30` the age 30 is less than the deadline.
- Step 9: `s2` stands in the same minute. The reaper first saw its new version at `t1 + 30` or `t1 + 60`, the age is not more than 30.
- Step 10: a table row without a deadline stands. Step 11: a rewritten row is removed too.

## Comparison

The forms of expectation — per the dictionary.
In scenario 03 the event queries filter kind=mark: the audit of the creation of a unit does not become
an extra element of the expected array. An expectation of a single code does not require an empty body.

A repeat of a variable inside expect compares its temporary value.
$rid from queued in 04 is a string substituted without change into the store path.
The directives are not sent to the server as HTTP. The full answer is additionally checked by the contract of its owner:
the store — P/01.1, the units — chapter 6.1, the doors of the resource — P/05 N2, the other doors — N2 of the chapter. In particular, answered
with @any in the TSV is still bound to be a full mark of one of the three forms of AnsweredMark.

## Evidence outside TSV

These are tasks for the implementation/stand, not checks already performed. Objects, events, the index, wait, streams, retention/holds and
free space are in [the acceptance of P/05](../../../05-resource/acceptance/README.md); the holder and the mark are in
[the acceptance of chapter 3.6](../../../03-worker/acceptance/6/README.md).

| Area | Counterexample and the required observation |
|---|---|
| Merge | Two resources, a duplicate id, silence and an answer after 3 s: one duplicate, incomplete, late bytes do not change the answer. complete does not promise the absence of truncation |
| Requests | Two contenders for begun: no more than one call; a lost answer of put_new: zero calls by assumption. A foreign unit/digest is not overwritten; unknown does not start a repeat |
| Outcome and cleanup | An old CAS of the reaper does not overwrite performed. A late answer replaces unknown with late. An error of publishing the mark leaves the row; the console does not delete the mark |
| Accounting and repeat | Competing filings, per_person; a break after the reserve before the row: a repeat creates the row through steps 4–5, one asked does not give 202; an unavailable read → 503, a damaged read form → 429. A reserves the rid, B accepts the repeat, A gets a definite refusal: the reserve remains, a new C at limit 1 is refused. The same at 409/an unknown outcome; age alone does not release a non-empty accounting; after kept the old rid is not reused |
| Request action | A body with a field `action` from `requests.elsewhere` the reaper neither marks nor removes; `reach.requests` requires `edit` on the group only for a request with this `action` (the norms of the chapter N1.5 `action`; analysis of the review of stage A 6–7, № 14) — in the ordinary profile by reading (the stand has no manifest of the ordinary profile with `elsewhere`); at `testsub2` (the append profile) a body with `action: recount` is an append: fetched of the holder, the console removes the row after settle — sc. 07 steps 34–36 of the acceptance of chapter 3.6 (the Architect's decision of 2026-10-20, analysis of the review of stage B 6–7); `reach.requests` requires a domain — analysis of the review of stage B 6–7, № 20 |

Reading of the branches and the schema confirm only the corresponding order/form. Timers,
processes, file barriers, network breaks and the cryptographic identity require separate
observations.

Additional probes of Kimi 33: The outcome refused after a call always has error, never performed; check both the pass and the form of the mark. These are tasks of a check of the norms/stand, not a statement about the execution of an implementation.

Merge: two sources with one different row each at limit=1 give one row and truncated=1. Two mirror copies with the same visible e3 and a local truncated=1 give the total truncated=2; this is a counter of stages, not of unique events. Check both keep, the priority of alarm and the same time with different ids. Additional probes outside TSV.

The freshness boundary of a door row at the merge is `≤ LOST_AFTER` ([the observation contract](../../../common/contracts/observation.md);
analysis of the review of stage A 6–7, № 1): a resource whose door row changed exactly 45 s ago is alive — the boundary is checked by the vector
[`fresh-age`](../../../common/vectors/fresh-age/README.md), not by a step (a controlled clock is needed; analysis of the review of stage B 6–7, № 20).

## Additional check of the class of errors of run 36 (Kimi)

By reading: POST marks checks the form of the reference, the presence of a live row is not required. The deadline of `kept` is by [the mark contract](../../../common/contracts/request-mark.md) «Mark»: from the moment when the holder saw
that the request row is no longer there (its monotonic clock), not earlier than `valid_until` if there is one; `ended_at` of the mark does not
start the deadline, without a confirmed final outcome the mark is not deleted. The points at the boundary with `kept` 60 (`testsub` has no key
`ttl`; `ttl` 0 — also 60): the mark stands at the local moment 0, 59.999 after the holder has not seen the row, the deletion
is admissible from 60; with `valid_until` later — not earlier than `valid_until` (analysis of the review of stage B 6–7, № 4, № 5). DELETE asked without a row — 404.

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

## Check of the class of errors R37 (Codex)

For the ordinary substitution of requests.key strings are needed; :int accepts a finite number, bool is excluded, truncation towards zero and the decimal notation are common.

This is a subject of a check of the norms/data and of a future stand, not a performed test of an implementation.

The bounds of :int per P/02.1: binary64, the modulus is not more than 2^53−1; bool/null/string/non-numeric/non-finite/out of bounds — 400, not a language cast. Check ±0.5, ±7.9, ±(2^53−1), 1e16, 1e21 and the canonical decimal result without an exponent.

## Additional cases R38-03/04/05

- The event instance: node,a is outside the profile and is refused before the start; node-a, box:pid:abcdef and admissible Unicode letters with a declared file profile give a representable `console/<instance>` in UnitRef/EventRow. Emptiness, a dot/two dots, slashes, |, a quote and Cc/Zl/Zp are rejected before publication. The start tasks in more detail are in the acceptance of M10/11 (history; its scenarios — by id-map).
- Settle: with the first confirmed outcome at the local moment 0 the row stands at 0/2/59.999, CAS is admitted at 60; this is not a guarantee that the tick runs exactly at 60. A repeated observation and unknown→performed do not extend the count, after a restart it starts anew. Check clear and sweep, including expired without fetched and an answer found by a late filing: it returns answered and leaves the row to the reaper. An unreadable mark or another unit/digest give no ground to remove the row. A shift of ended_at of the writer does not change the age. The TSV checks only the eventual removal within 90 s, not the lower bound 60; the bound requires a controlled clock/reading of the implementation.
- The append (P/03.6-04, P/06.4-07; formerly M10/8-19) and the form of the consumer of the append in `testsub2` — with scenario 07 in [the acceptance of chapter 3.6](../../../03-worker/acceptance/6/README.md).

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

The scenarios have no sleeps.
