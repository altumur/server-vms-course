# Vectors: the outcome of a store answer for the client

This English text is the source; the Russian translation `ru/vectors/store-client/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the store client contract](../../contracts/store-client.md) (chapter P/01.1; the guess of stage C SC-WIRE78-G01 /
C08-SDK-06, the Architect's decision of 2026-10-25). The participants are all processes that talk with the store through the door of P/01.1. The bytes
are written by «Спецификация»; the rows are by the text of the contract and P/01.1 Н2, Н4.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — `{op, reply}`: `op` — `get` | `list` | `write` (a write, a deletion and a batch — `write`; the `conflict` of a batch has `key`, P/01.1 Н4); `reply` — `{status, body}` (the HTTP code
and the JSON body) or `"@none"` (the answer did not come), `"@truncated"` (cut off), `"@refused"` (the connection was refused).

**Output** — a JSON string: `row`, `absent`, `unreadable`, `listing`, `written` or the `kind` of a refusal (`conflict`, `guard`,
`unavailable`, `ambiguous`, …) — the contract, the section «Outcomes and what the client does» (`outcome`, `no_reply`). The comparison is JSON by
value.

21 rows: the forms of a read answer (a row, an absent one, a damaged one, one not of the form), a listing, a write and the repeat `again`,
a version not of the wire form at a write and a listing, no answer, a cut-off at a listing and a write, a refused connection at a write, the refusals
`conflict`, `guard`, `ambiguous`, `unavailable`, `toolarge`, `forbidden` (the rows `list-bad-version`, `write-truncated`,
`write-toolarge`, `get-forbidden` — the coverage audit of P/01, the second pass, G07; `write-conflict-batch` — ADR-0094 B9).

## Run

Without a stand: a side gives the input to its function that parses the answer of the store client (the wire is replaced by the input). The wire is the acceptance
of lesson 01.
Who performs is every process whose norm calls the door of P/01.1 as a client (ACC-VECTORS-CONNECT-04, the Architect's decision of 2026-10-26; the principle ACC-VECTORS-CONNECT-03): the CLI of the store daemon
(`01-store`: `admin_ops` through `admin.sock`, P/01.3 Н1.3 — `status`, `backup`, `join`, `leave`), the installer (`02-installer`:
`w2cctl manifest put`, `rights`, `secrets`, the installation), the worker and the worker at the domain (`03-worker`), the controller (`04-controller`),
the resource (`05-resource`), the cluster console (`06-console`), the process `domain` (`08-domain`), the agent (`09-agent`), the domain console
(`10-domain-console`) — the writers and the readers of rows by the catalogue (`Platform/common/data/catalog.tsv`).
