# Vectors: SaidID — the name of a request in `fetched`

This English text is the source; the Russian translation `ru/vectors/said-id/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the request mark contract](../../contracts/request-mark.md) «fetched» `said_id` (moved from chapter
[P/03.4](../../../03-worker/spec/03.4-worker.norms.md) Н1.1; the layout audit `А-24`, `Б-02`); the field `fetched` of the heartbeat is P/03.4 Н1.1: the worker
writes into the heartbeat the SaidIDs of the requests whose outcome it reported ([chapter 3.6](../../../03-worker/spec/03.6-worker.norms.md) Н3
«holder's look»). The participant is [chapter 6.4](../../../06-console/spec/06.4-console.norms.md): the reaper of the console reads
`fetched` and removes the append row when its rid is reported (Н3 «reaper» `clear`;
before the move — М10/8). The package is common: the algorithm is read by two processes (the Architect's decision on the review analysis of stage A 6–7, № 2).
The bytes are written by «Спецификация» (ADR-0083); the conformance of the product is by its acceptance against these tables (ADR-0080 addendum 16).

## Rule (P/03.4 Н1.1 `said_id`)

- **plain** — the rid as it is, if it has no more than 40 Unicode characters (code points), it does not start with «#», it has no
  «,», «"», «\» and every character is printable — a letter, a mark, a digit, punctuation, a symbol (the general categories L, M, N, P, S) or
  the space U+0020;
- **hashed** — otherwise «#» and the first 20 hex characters of sha256(UTF-8 rid), in lowercase;
- **read** — split `fetched` by «,»; the rid is reported if among the names there is the rid or SaidID(rid).

The input of the vectors is a rid by its grammar ([P/06.4](../../../06-console/spec/06.4-console.norms.md) Н1.5 `rid`, the vector [`rid`](../../../06-console/vectors/rid/README.md): ≤ 200 bytes of UTF-8, not empty, not `.`/`..`, without
`/ \ " '` and Cc, Zl, Zp, does not start with `free-`). The categories are by Unicode 15.0.0 (as `common.schema.json`); the characters of the vectors
are chosen so that their category did not change in the versions 15.x.

## `said.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header. Four fields:

| Field | Meaning |
|---|---|
| `case` | the name of the row; `plain-…` — the SaidID equals the rid, `hashed-…` — a hash |
| `rid` | the rid — a JSON string; a character that is not printable by the rule above, and a mark (M) are written by the escape `\uXXXX` (outside the BMP — by a surrogate pair), the others — as they are |
| `said` | the expected SaidID — a JSON string |
| `note` | what the row is for |

The boundaries: 40 and 41 code points for ASCII, Cyrillic (2 bytes), characters outside the BMP (4 bytes, two UTF-16 units), 40 and 42 for letters with
a combining mark (points, not graphemes); «#» first and inside; a comma; the space U+0020 and NBSP; Cf, Co, Cn; a digit outside
ASCII; ASCII punctuation and symbols; the largest rid of 200 bytes.

## `read.tsv`

Five fields: `case`; `fetched` — the value of the heartbeat field, a JSON string; `rid` — a JSON string; `reported` — `true` or
`false`: whether the rid is reported; `note`. The comparison of a name is whole, byte for byte, without trimming spaces; an empty element is not a name.

## Stand commands

The key `stand` of the profiles `03-worker` and `06-console` (the section «Layout by processes» of [the common acceptance
README](../../acceptance/README.md)); a template with `{input}` — the path of the input file of the row;
code 0 — computed, 2 — an input not of the form; stdout is compared with the expectation as JSON by value; there is no envelope `result`
(the guess of stage C W03-G03, the Architect's decision of 2026-10-23):

- `said-id` — the cell `rid` is written into the file byte for byte (a JSON string); stdout — the SaidID as a JSON string and LF; the expectation is
  the cell `said`;
- `said-read` — `{"fetched": <ячейка fetched>, "rid": <ячейка rid>}` is written into the file (the cells — byte for byte); stdout —
  `true` or `false` and LF; the expectation is the cell `reported`.

## Run

A side implements SaidID and the reading of `fetched` by its own function (the worker — the write, the console — the reading) and checks each row: `said.tsv` — SaidID(`rid`) equals `said` byte for byte; `read.tsv` — the outcome of the reading
equals `reported`. The vectors are derived from the norm; on a divergence the norm is right, the vector is corrected by «Спецификация».
Who performs is by the table: `said.tsv` — the worker (`03-worker`, writes SaidID into `fetched`, P/03.4 Н1.1, P/03.6 Н3) and the console (`06-console`, the reaper computes SaidID(rid) when reading, P/06.4 Н3 «reaper» `clear`); `read.tsv` — the console (`06-console`); the worker does not read `fetched` (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Vector wire

The wire of `read.tsv`, `said.tsv` is set by the `common/said-id` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.
