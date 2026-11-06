# Vectors of accepting a report

This English text is the source; the Russian translation `ru/vectors/accept/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The vectors of [the report acceptance contract](../../contracts/accept.md): the function «accept» (`accept`) — the generation, the mark, `same`,
`heard`, `ignored`, the refusals, the roads. The owner is lesson P/08, chapter 8.3 (the holder); the participant is the relay (9.2), which
accepts a member by the same function over its own memory (the review analysis of stage A 8–10, № 13 / decision 2; ADR-0083 addendum (13)). The bytes
are written by «Specification» (ADR-0083); the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The rows were transferred from the inputs of the command `accept` of the acceptance of
M11/3 (`inputs/accept-*.json`, sc. 13) and
M11/4 (`inputs/accept-*.json`, sc. 06 — the roads) without
a change of bytes; `case` is the name of the input file (the numbers of lesson 4 start anew, the names differ), `note` is the lesson, the scenario and
the step. The scenarios M11/03 sc. 13 and M11/04 sc. 06 and their inputs were removed by the move of lesson 8 (ADR-0083 addendum (14) item 17; the log is
the acceptance of chapter P/08.3 (`corrections-3.tsv` (historical correction record), a log, not in the export)): the table is the only source of these cases.

## Run

Without a stand: the function of an implementation gets the input (the column `input`) and gives the output; `expect` is a subset of the fields of the output by
the dictionary of the «Stand» ([the common acceptance README](../../acceptance/README.md)): `"@absent"` — there is no field, `"@any"` — the field exists with any
value. The form of the input and the output, the meaning of the fields (`catalog`, `refreshed_ago`, `refresh`, `whole`, `status`) and the exit code 2 are
[the contract](../../contracts/accept.md) «The form of the function»; the mark `mark` is by the form of the contract «Generation, mark, limits», its
`sha256` is of the JCS of `stored`, except `accept-05-rebase-stored-not-mark` and `accept-20-whole-over-broken-stored` of lesson 3: there
`stored` is deliberately not with `mark.sha256` (the review analysis of stage B 8–10, № 22, Claude `M-18`).

The inputs depend on the bytes of the catalogue manifest (P/08.3 N5; the review analysis of stage A 8–10, № 37; the review analysis of stage B 8–10, № 22,
Kimi SB810-06): at the rows of lessons 3 and 4 `catalog` is `["testsub"]`, the keys of the objects are `testsub/*`; at the rows of the families `reports`,
witnesses and contributions (`accept-36`…`accept-39`) — `["testsub", "testsub2"]` (`domain.reports`, `domain.witness`,
`domain.books` with `from` exist only at `testsub2`); the `domain.ref` of the manifest decides steps 4 (`member_objects`) and 5 (`not_ready`):

| Manifest | File | sha256 |
|---|---|---|
| `testsub` | [`Platform/common/data/testsub/testsub.subsystem.yaml`](../../data/testsub/testsub.subsystem.yaml) | `fc3bf70585646b078a8812edd0c92cd5c7d0c2e364b689273c5fd229aed7355b` |
| `testsub2` | [`Platform/common/data/testsub/testsub2.subsystem.yaml`](../../data/testsub/testsub2.subsystem.yaml) | `e4bfd9e0035dba5839018625bba20f7214176004fc2d0cb4f8d640015d915dbb` |

The bytes of `testsub2` changed on 2026-11-04 (the roadmap 4.5): the token kind `vault` with `keep: true` was added to `domain.tokens`, then the comments of the header were rewritten without the names of test files; the fields on which the expectations of this table depend were not touched — a recheck by the oracle is not needed.

A change of these bytes is a reason to recheck the table.
Who performs is the holder (`08-domain`, the process `domain`: P/08.3 N3 «accept» on `POST /api/member/<member>` and the relay batch with `via`) and the relay (`09-agent`, the door over its own memory, P/09.2 N2) — all rows. They only read the result: the member's agent (the side of P/09.1 — the answer `carry` and 409 of the holder, N3 «the agent pass») and the domain console (`10-domain-console` — the mark `reported`, P/10 N3 `alarms`) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 66 rows (3 ADR-0113 — `accept-camera-*`, `accept-heard-every-changed`; 26 of lesson 3, 9 of lesson 4, 2 of the relay door — `same_sent_at` after `heard`, the witnesses' note and the Architect's decision of 2026-10-23; 25 of stage C — below; 1 — the coverage audit of P/08, the second pass of Gemini) | `input` is the input of the command `accept` as JSON text (`catalog`, `mark`, `stored`, `body`, `refreshed_ago`; for lesson 4 — `via`, `heard_ago`) → `expect`: `generation` (`rev`, `base`, parts of `whole`), `heard` (`refresh`), `same`, `ignored` or `refused` (`status`, `reason`: `rebase`, `same_sent_at`, `not_ready`, `not_a_publication`, `rev_exhausted`; `whole_too_large` — there are no rows, «Candidates») |

## Rows of stage C

The Architect's decision of 2026-10-23 (ADR-0083 addendum (33) item 8: an error of `common` without a vector is a gap of the contract):

- `accept-31`…`accept-38` (ACC-OBJECTS-31-01) — a row for each other family of `member_objects` (`domain/shared`,
  `domain/shared-refused`, `domain/reaches`, `domain/alarms`, `domain/backup-taken`, `reports`, a witness, a book contribution):
  the object is kept in `whole` as it is; `accept-39` — keys outside the list, including those with the same beginning (`domain/sharedx`,
  `domain/shared/x`) and a witness without a name, are dropped silently, the report is accepted;
- `accept-40`…`accept-47` (ACC-FORM-31-01) — the names are compared exactly: an extra field of the input envelope, of the mark, of `stored` —
  `@exit 2`; an extra field of the publication body — `not_a_publication`; `sign_failures` not of the form (a compound or an unknown
  name, `0`, a fraction) — the field is not taken (`out_of_delta`), the report is accepted;
- `accept-48`…`accept-50` (ACC-G01-COUNTER-31-01) — `n` is an integer of the platform: `9007199254740991` — of the form;
  `9007199254740992`, `1e20` — not of the form, the report is accepted;
- `accept-52`…`accept-55` (ACC-FORM172, ACC-TIME172; a coverage gap, the norms are the former ones) — the form of the mark at the input: `sign_failures`
  {} — not of the form (`member-reported.schema.json` and OpenAPI: at least one name), `@exit 2`; `received_at` as a string of the canon of
  P/01.1 N0 (`"1700000000.5"`) — is read, the output is as for `accept-09`; negative and with an exponent — not of the form, `@exit 2`.

`accept-56-mark-no-stale` (the coverage audit of P/08, the second pass of Gemini): the input of `accept-03` without the field `stale` of the mark — `@exit 2` (the contract «The form of the function»:
`stale` is always present). The expectation is the output of both witnesses `cammeta-python` and `cammeta-go`: for them `accept-03` is `rebase`, without
`stale` — code 2 with a refusal of the mark.

Whether the field `sign_failures` was taken into the mark is shown by the field `sign_failures` of the output `generation` and `heard` with `refresh: true`
(the contract «The form of the function»; the Architect's decision of 2026-10-23): `accept-48` — `{"domain": 9007199254740991}`, the other
rows 44–50 — `"@absent"`; `accept-51` — `heard` with `refresh: true` and the field taken.

## Candidates

The review analysis of stage B 8–10, № 6 (Claude `P-2`):

- **step 4a, `whole_too_large`** (`{"result":"refused","status":413,"reason":"whole_too_large"}`) — there is no row: the input would have to
  give a JCS of the whole `whole'` larger than `BODY_LIMIT` (16 MiB). A body larger than the limit is cut off by the door before the function (413 of the body), and
  the objects outside `member_objects` are dropped, so the input is megabytes: a large `stored` at `base > 0` (`mark` with its
  `sha256`) and a small delta; a cell `input` of such a size is unfit in a table. A form of the package input is needed that does not exist: an input
  from a file next to the table or a rule for generating the input (repeating an object up to the size) — a decision of «Specification» on the form of the
  package; then `mark.sha256` is the sha256 of the JCS of this `stored`. The Architect's decision of 2026-10-20: the row stays a candidate
  of the package, the reason is an input larger than 16 MiB (question 1 on the review analysis of stage B 8–10).

The vectors of lessons 3 and 4 are inputs of an acceptance that passed at two witness implementations; the rows of stage C were composed by the contract;
they were not checked by a reference rebuild (the generation and the mark
rest on the sections of the contract «Generation, mark, limits» and «The member's publication»; the owners of the text are P/08.3 N1.3,
[P/09.1](../../../09-agent/spec/09.1-agent.norms.md) N1.2). On a divergence the contract is right, the vector is corrected by «Specification».
