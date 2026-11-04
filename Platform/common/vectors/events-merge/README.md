# Vectors: the merge of the event journal

This English text is the source; the Russian translation `ru/vectors/events-merge/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the event journal merge contract](../../contracts/events-merge.md) (lesson P/06, chapter 6.4; ADR-0091 addendum (21) item 3).
The participants are the cluster console (`GET /events`, [P/06.4](../../../06-console/spec/06.4-console.norms.md)) and a subsystem worker
that merges the journal itself. The bytes are written by «Спецификация»; the rows were composed by the text of the contract and checked by its oracle, not by the code of
implementations.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — a JSON object:

| Field | Meaning |
|---|---|
| `participant` | `"console"` or `{"worker": [<sub>…]}` — the subsystems whose epoch rows are declared in `worker.reads` |
| `query` | `{limit?, keep?}` — as at the request of P/05 Н1.3 (the defaults 1000, `newest`); none — the defaults |
| `policies` | `{<sub>: fenced \| earlier-run}` — `older_epochs` of the manifest; none — `fenced` |
| `epochs` | `{<sub>: {<id единицы>: <эпоха>} \| "did not answer"}` — what the participant read in `<sub>/epoch/*`; at the worker — only the declared ones |
| `grant` | the `view` scopes of the caller of the console — `*`, `unit:<sub>/<id>`, `labels:<метка>[,…]` (the contract `may` step 7); none — `["*"]` |
| `units` | `{<sub>/<id>: [<метка>…] \| "@unreadable"}` — the labels of the unit rows as read (the field `labels` declared in `unit.fields`; `"@unreadable"` — the row is unreadable or the read is not confirmed); there is no unit — there are no labels (`[]`) |
| `resources` | `{<сервер>: <ответ ресурса> \| "did not answer" \| "silent" \| {"said": <state>}}` — the live resources and their outcomes; the answer is `{events, state, truncated, partial?, lines_garbled?}` of P/05 Н1.3 |

**Output** — the answer of the contract `{events, state, truncated, partial?, lines_garbled?, complete, incomplete, withheld?}`. `expect` is a subset:
`events` — an array of rows in the order of output, at each the listed fields are compared (`id`, `epoch_is`, `fenced`; `"@absent"` —
there is no field); the other keys — by JSON value (`"@absent"` — there is no key).

23 rows: 13 of the console (5 — the visibility filter: a grant by labels and an unreadable unit — the row is hidden, `withheld` with it; a grant on
a unit and on `*` — visible, no `withheld`; labels by `of`; labels `[]` — hidden without `withheld`; C06-EVENTS-LABEL-SOURCE-138-07), 4
of the worker, 3 common ones (`limit`/`keep`, an equal time, `partial`/`lines_garbled`) at the console and 3 of their twins at the worker (`*-worker`:
the merge of the worker — steps 1–6 of the contract without the filter 5а; ACC-VECTORS-CONNECT-03).

## Run

Without a stand: a side gives the input to its merge function (the requests to the resources and the reads of the epochs are replaced by the input) and compares the output
with `expect`. The order of the segments of `state` at several unavailable resources the rows do not fix (a row has no more than one).
Who performs a row is by the field `participant` of the input: `"console"` — the cluster console (the profile `06-console`),
`{"worker": […]}` — a worker that merges the journal itself (the profile `03-worker`); a side does not perform foreign rows
(ACC-VECTORS-CONNECT-02, the Architect's decision of 2026-10-26).

## What the vector does not cover

The visibility filter of the console (the contract, step 5а) — the rows with `grant` above; without `grant` the caller is with `view` on `*`. The cut by `limit`
after the filter with the limit 10000 to the resources and the reading of the unit rows themselves — the acceptance and reading (C06-EVENTS-VIEW-33-01). The freshness of the door row (the package [`fresh-age`](../fresh-age/README.md)), `from mirror`, the lanes and the timeout, a late answer, the reconciliation
of the evidence row with a fresh read of the epoch — by reading the contract; the rights of the worker to `<sub>/epoch/` — P/02.5 and the scenarios.
