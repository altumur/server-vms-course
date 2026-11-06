# Vectors: the state of a resource by the observation history

This English text is the source; the Russian translation `ru/vectors/resource-state/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the observation contract](../../contracts/observation.md) («Observation of a version» with `lapse`, «Freshness», «Resource state»;
the guess of stage C OBS-001 (Go), the Architect's decision of 2026-10-23). The participants are the observers of `resource_state`:
the controller ([P/04](../../../04-controller/spec/04-controller.norms.md) N3) and the console (`ServerRow.resource`
of [chapter 6.5](../../../06-console/spec/06.5-console.norms.md), the server output of chapter 6.6). The bytes are written by «Specification».
The freshness boundary is one — the vectors [`fresh-age`](../fresh-age/README.md); here — how the age and the state follow from
the observation history: the first look, a repeat of the same version, a new version, an unreadable one, a non-answer and a confirmed absence.

`LOST_AFTER` = 45 s (P/04 N1.4).

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped; the first line without `#` is the header. Five fields:

| Field | Meaning |
|---|---|
| `case` | the name of the case, unique |
| `history` | a JSON array of observations in order `[t, source, outcome]`: `t` — the seconds of the observer's monotonic clock from the start of its memory; the source — `pulse` (the heartbeat `platform/resources/<s>/heartbeat`) or `door` (the row `platform/doors/<s>`); the outcome — a version label (`v1`, `v2` — equal labels are one version), `garbled` (read, not of the writer's form), `noanswer` (the store did not answer), `absent` (a confirmed absence) |
| `at` | the moment of the judgement — seconds of the same clock, not earlier than the last observation |
| `state` | `live`, `unreachable`, `unknown` or `silent` |
| `note` | a rule of the contract |

24 cases: 5 `live`, 7 `unreachable`, 4 `unknown`, 8 `silent`.

## Run

A side gives the history to its observer (the observation memory and the monotonic clock are replaceable) and compares the state at
the moment `at`. What the state means for the fate of a slot, the pool and the outputs is with the reading lessons, the vectors do not check it.
The version labels `v1`, `v2` are abstract: what a version is made of (at an object — the pair `(server, written)` of the resource door,
a strictly growing `written` by key, P/05 N1.1 `written`; the contract «changed») — by reading, the table does not express it
(C06-OBJECT-VERSION-33-01).
Who performs are the observers of `resource_state`: the controller (`04-controller`, P/04 N1.4, N3 «fate», «choose») and the console (`06-console`, P/06.5 N2 `ServerRow.resource`, P/06.6 N3 «decommission_server»). The resource (`05-resource`) does not perform the state: it writes the heartbeat and the door row (P/05 N1.4); the console module (`07-console-module`) only reads the result from `/servers` (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Native outcome

Code 0 and the value of the column `state` as a JSON string — `"live"`, `"unreachable"`, `"unknown"` or `"silent"` (one expectation
column — the general rule «Vectors» of [the common acceptance README](../../acceptance/README.md)); the input is the cells `history`, `at`; the Architect's decision of 2026-10-27.

## Vector wire

The wire of `cases.tsv` is set by the `common/resource-state` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.
