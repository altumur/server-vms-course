# Vectors: the group of a unit by the host of the address (`cut_at: host`)

This English text is the source; the Russian translation `ru/vectors/group-of/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is lesson P/04 through [the group by host contract](../../contracts/group-of.md) ([the norms](../../../04-controller/spec/04-controller.norms.md) Н1.3 `group_by`, `cut_at: host`; ADR-0053; the parsing of the address is
`schemes` of P/02.1 Н1.2а). The participants are `<s>controller` (the group of a unit at placement) and `<s>worker` (the stamp `group` of a request and the call per group, P/03.6); moved from `04-controller/vectors/group-of` byte for byte (W03-GROUP-01). The bytes are written by «Спецификация»; moved
from `Source/tests/testdata/group_of.tsv` (stage B, the move of lesson 6, the Architect's decision on В8 of the plan of lesson 6). The header
of `cases.tsv` was moved byte for byte and names the former addresses: М10/3 Н4 — now P/06.1 Н4, М10/7 Н1.1а — P/06.2 Н1.1а,
`fault.tsv` — the package [`fault`](../fault/README.md).

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` are explanations (the declaration of the field `source` with the schemes and the parsing rules are in the header of the file,
they are part of the package), empty lines are skipped. There is no header; three fields: `raw` — the address (as in the unit row), `group` — the group (the host in
one notation) and `fault` — the refusal (`bad_url` or empty); the input of the single command `vectors` is `cells: {raw}`, the name is one for
all tables without a header with a cell «как записана» (as written) (the common acceptance README «Единая команда пакета векторов»; the inventory C04/C06-NEXT-167, the Architect's decision of 2026-10-27). An empty group without a refusal — the unit is not in a group. The comparison is by bytes. A row with an empty first cell (it starts with TAB) is
the empty value of the field: `<none>`, no refusal (GO-EMPTY-01).

## Stand command `group-of`

The key `stand` of the profiles `03-worker` and `04-controller` (the section «Layout by processes» of [the common acceptance
README](../../acceptance/README.md)), by the general rule of the vector commands: a template with `{input}` — the path of a file into which the runner
writes the bytes of the cell `raw` (the first field of the row) as they are; stdout — `{"group": <ключ группы или "">, "fault": <"bad_url" или
"">}` and LF, the `<none>` of the table — `""`; the comparison is JSON by value; code 0 — computed, 2 — an input not of the form, stdout empty.
An empty address is of the form; an unreadable address — code 0 with `fault: "bad_url"`; not of the form — only invalid UTF-8 (code 2,
stdout empty; the guess of stage C W03-G06, the Architect's decision of 2026-10-23) (the guess of stage C C04-VECTOR-01, the Architect's decision of 2026-10-23).

## Who performs

Who performs is by the field of the output: `group` — the controller (`04-controller`, P/04 Н1.3 `group_by`: the group of a unit at placement), the worker (`03-worker`, P/03.6 Н1.5 the stamp `group` of a request, Н3 — one call per group) and the requests door of the console (`06-console`, the stamp `group` of a request row, P/06.4); `fault` — the url step of the row check: the units door of the console (`06-console`, P/06.1 Н4) and the customer's library (`03-worker`, P/03.6 Н1.6). The controller does not perform the refusal — the rows have already passed the url step before it: at it only `group` is compared, at the worker and the console — both fields (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Vector wire

The wire of `cases.tsv` is set by the `common/group-of` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.
