# Vectors: the grammar of the request `rid`

This English text is the source; the Russian translation `ru/vectors/rid/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is chapter P/06.4 ([norms](../../spec/06.4-console.norms.md) Н1.5 `rid`: the name of the row `<sub>/requests/<rid>` and of the mark
`objects/<sub>/commands/<rid>`; Н4 «просьба: неверный … rid»; ADR-0060). The participants are the console requests door
(`POST /<sub>/requests`: the rid by the template `requests.key` or `r-<sha16(Idempotency-Key)>`; a refusal — 400 RequestError, Н4) and
the worker that writes a request itself ([chapter 3.6](../../../03-worker/spec/03.6-worker.norms.md) Н1.5, `worker.requests`: a refusal —
`RequestRefused`, the count `filings.refused`); the form of the element `rids` of the record `asked` ([the family `asked`](../../data/asked.schema.json)).
The bytes are written by the Specification (ADR-0083, stage B; the rule — the Architect, 2026-10-06, after the fourteenth review; the ban on
`free-` — the Architect's decision of 2026-10-18); the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The package was moved from `Source/tests/testdata/rid.tsv` (stage A) together with lesson 6 (stage B, ADR-0083 addendum (1)); the bytes
of the table are the same, including the header comment (its «М10/8 Н1.5» is the former address of the norm, now [the contract of the request and its mark](../../../common/contracts/request-mark.md) `rid` (review analysis of stage B 6–7, № 24); the product copy
is checked against these bytes).

## `rid.tsv`

UTF-8, LF, fields separated by TAB. Rows with `#` and empty ones are skipped; there is no header row. Two fields:

| Field | Value |
|---|---|
| `rid` | the request name — a JSON string; a character of Cc, Zl, Zp is written escaped (`\u0085`, ` `), other characters — as they are |
| `verdict` | `ok` — the name is accepted; `refused` — a refusal |

## Rule

No more than 200 UTF-8 **bytes**, not empty, not `.` and not `..`; without `/ \ " '` and the Unicode characters Cc, Zl, Zp (control characters, U+0085,
U+2028, U+2029); does not begin with `free-` — that is the family of the resource requests `<sub>/requests/free-<server>-<volume>`
([P/05](../../../05-resource/spec/05-resource.norms.md) Н1.4 `free_ask`). Case matters: `Free-a` is not `free-`.

The last row of the table is the form of `rid` by the filer's key `<filer's subsystem>.<key>` (the request contract `rid`; ADR-0091
addendum (23) item 2): a dot in the name is allowed, the grammar is the same.

## `template.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header
`case<TAB>key<TAB>body<TAB>expect<TAB>note`.

| Field | Value |
|---|---|
| `key` | the template `requests.key` as a JSON string (`{поле}` — a string, `{поле:int}` — a number; the form — P/02.1, the request contract `manifest.key`) |
| `body` | the request body — a JSON object with the fields of the template |
| `expect` | `{"rid": <rid>}` — the substitution gave a rid by the grammar; `{"detail": <field>}` — a refusal 400 RequestError, `detail` names this field of the template |

The rule of the refusal field is the contract of the request and its mark `rid` and P/06.4 Н4: a beginning `free-` — the field with which the rid begins;
the limit of 200 bytes — the field on whose substitution the rid, assembled from left to right, exceeded the limit (in a literal after a field — that
field); a forbidden character or the grammar (`.`, `..`, empty) — the first field in the order of the template with a violation; with several
violations — the field of the earliest byte offset in the rid (`free-`, `.`, `..`, empty — 0; a character — its offset; the length —
the offset of byte 201; a literal byte — to the field before it) (the Architect's decisions of 2026-10-27). 20 rows: 3 `rid`, 17
`detail`, of them 3 mixed (`mixed-*`). The native outcome is code 0 and the object `expect` (one expectation
column — the common rule «Vectors» of [the common acceptance README](../../../common/acceptance/README.md)); the input is `cells` `key`,
`body`. Who executes it are the same ones that build a rid by the template: the console requests door (`06-console`, P/06.4 Н3 «file a request» step 1)
and the filing worker at a target with `requests.key` (`03-worker`, P/03.6 Н1.5: both have one rid name) — both
compare `rid`; the field `detail` — only the door (for the worker the refusal is `RequestRefused`, the field in the log). On the 17 `detail` rows
the worker answers with code 0 and `{"detail": <non-empty string>}` — a refusal without a rid; the value is not compared (for the door — as
in `expect`) (ACC-RID-TEMPLATE-WORKER-01, the Architect's decision of 2026-10-27).

## The stand command `rid`

The key `stand` of the profile `06-console` (the section «Layout by processes» of [the common acceptance README](../../../common/acceptance/README.md));
a template with `{input}` — the path of a file with one JSON object `{"rid": <rid cell as is>}` (the cell is a JSON string, the runner inserts
its lexeme without a second layer of quotes and without decoding it again); there are no fields other than `rid`. The answer is `{"status": "ok"}` or
`{"status": "refused"}`, checked against the column `verdict`; a refusal of the name is code 0 with `refused`, not code 2. An input not in form: not an object,
no `rid` or a repeated one, an unknown field, `rid` not a string. stdout is exactly one JSON object and LF: the first byte is `{`, after the object — LF and the end; extra fields, bytes, CRLF, spaces
around it — FAIL of the row; formatting inside the object is allowed; service output goes to stderr. Code 0 — computed; an input not in
form — code 2, stdout empty (stage C guess C06-F2-IO-01, the Architect's decision of 2026-10-23).

## Run

The side decodes the cell `rid` as a JSON string and checks the verdict with its own name check — one function at the door and at the
worker. `rid.tsv` checks the grammar; the substitution of the template `requests.key` and the field of its refusal are checked by `template.tsv`; the computation of
`r-<sha16(Idempotency-Key)>` is not checked by the tables.
Who executes it are the console requests door (`06-console`: the rid by the template and `r-<sha16>`, the form of `rids` of the record `asked`; P/06.4 Н3 «file a request» step 1, Н4) and the filing worker (`03-worker`, P/03.6 Н1.5 `worker.requests`) — all the rows with one name check (the contract of the request and its mark `rid`) (ACC-VECTORS-CONNECT-03: a row is executed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Vector wire

The wire of `rid.tsv`, `template.tsv` is set by the `06-console/rid` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.
