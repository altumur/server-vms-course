# Vectors: freshness — the age of the observed version → fresh

This English text is the source; the Russian translation `ru/vectors/fresh-age/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the observation contract](../../contracts/observation.md) «Freshness: `LOST_AFTER`» (a common contract of the module
«Платформа»). The participants are all observers that judge «changed within the last LOST_AFTER»: the controller — a live worker of the pool,
the fate of a slot, `resource_state` ([P/04](../../../04-controller/spec/04-controller.norms.md) Н3); the console — `worker_state`
and `WorkerRow.state` ([chapter 6.1](../../../06-console/spec/06.1-console.norms.md) Н2,
[chapter 6.5](../../../06-console/spec/06.5-console.norms.md)), `w2c_resources_live` (chapter 6.5), the live resources of the merge of
`/events` ([chapter 6.4](../../../06-console/spec/06.4-console.norms.md) Н3 «merge»), `live` of `/schema`, «live» of the schema
raise and «heard» of the server output ([chapter 6.6](../../../06-console/spec/06.6-console.norms.md)); the resource — the neighbours of the mirror ([P/05](../../../05-resource/spec/05-resource.norms.md) Н1.4 `mirror`). The package replaces «a step
of the acceptance at the boundary», which a stand without a controlled clock does not do (the Architect's decision on the review analysis of stage B 6–7,
№ 20; the boundary `≤` — the review analysis of stage A 6–7, № 1). The bytes are written by «Спецификация» (ADR-0083); the conformance of the product is by its
acceptance against this table (ADR-0080 addendum 16).

## Rule (the observation contract «Свежесть»)

- `LOST_AFTER` = 45 s (the value is the observation contract «Свежесть»; the role in the terms of the judge is [P/04](../../../04-controller/spec/04-controller.norms.md) Н1.4);
- **fresh** — the age of the observed version ≤ `LOST_AFTER`; **not fresh** — the age > `LOST_AFTER`. The relation is one for all
  observers and outputs.

The function is pure: the input is the age in seconds (a number, a fraction is allowed), the output is fresh or not. How the age is obtained
(the monotonic clock of the observer, the first look — 0, a repeated read of the same state and a non-answer of the store do not reset
the age) is the contract, the section «Observation of a version»; the vectors do not check it — this is the history of observation, it is checked
by reading and by the acceptance steps of the reading lessons. There is no negative age by definition (the clock is monotonic, the count is from the moment
of the read), there are no rows with it in the table.

## `fresh.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header. Four fields:

| Field | Meaning |
|---|---|
| `case` | the name of the row; `zero`, `below-…` — less than the boundary, `equal-…` — exactly the boundary, `above-…` — greater |
| `age` | the age of the observed version in seconds — a JSON number (`45` and `45.0` are one number) |
| `fresh` | `true` — fresh, `false` — not fresh |
| `note` | what the row is for |

The boundaries: 0; `LOST_AFTER − 1` (44), `= LOST_AFTER` (45, 45.0), `LOST_AFTER + 1` (46); fractions near the boundary — 44.9, 45.1 and
an excess of a microsecond (45.000001): the precision of the observer's clock is not coarsened to whole seconds.

## Stand command `fresh-age`

The key `stand` of the profiles `04-controller` and `06-console` (the section «Layout by processes» of [the common acceptance
README](../../acceptance/README.md)), by the general rule of the vector commands: a template with `{input}` — the path of a file into which the runner
writes the cell `age` byte for byte (a JSON number); stdout — `true` or `false` and LF; the comparison is JSON by value with the column
`fresh`; code 0 — computed, 2 — an input not of the form (not a JSON number), stdout empty (the guess of stage C C04-VECTOR-01, the Architect's decision of 2026-10-23).

## Run

A side implements the judgement of freshness by its own function (the one that stands behind all the places above) and checks each row:
fresh(`age`) equals `fresh`. The comparison is over the number of the age as it is, without rounding: the output of `age` with one digit after
the point (chapter 6.1 Н2) is a display, not an input of the judgement. The vectors are derived from the contract; on a divergence the contract is right, the vector
is corrected by «Спецификация».
Who performs is every observer whose norm judges «changed within the last LOST_AFTER» by its own code: the controller (`04-controller`, P/04 Н3 «fate», «choose», `resource_state`), the resource (`05-resource`, P/05-R026 mirror neighbours by their door row), the console (`06-console`, P/06.1 Н2 `worker_state`, P/06.4 Н3 «merge», P/06.5 Н1.8, Н2 `WorkerRow.state`, `w2c_resources_live`, P/06.6 `/schema`, «heard»), the agent (`09-agent`, P/09.1 Н1.2 `fresh` — the heartbeats in `stale`) and the domain console (`10-domain-console`, the worker heartbeat at the domain: P/03.7 Н1.6, P/10 Н1.6 `absent`). They only read the result: the process `domain` (`08-domain`, `stale` of the member mark, P/08.1 Н1.3 `unit_state`) and the console module (`07-console-module`, `WorkerRow.state` from `/servers`); The worker only declares the term as a writer; the resource also reads and judges the door versions of its mirror neighbours. The freshness of a domain member (`member_state`, P/08.1, P/10) is its own section of the observation contract and its own vectors of chapter 8.1, not this package (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Vector wire

The `vectors` binding of `fresh.tsv` is the [single wire form](../wire.tsv), with [grammar](../wire.md). The existing stand command above remains available to its named profiles; this binding adds no stand key. All appointed observers call their own freshness function.
