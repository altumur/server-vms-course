# Vectors: the record of the sent deadline `valid_until`

This English text is the source; the Russian translation `ru/vectors/deadline/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the contract of the request and its mark](../../contracts/request-mark.md) «Request» `valid_until` (the owner of the contract is chapter P/06.4;
[norms](../../../06-console/spec/06.4-console.norms.md) Н3 «file a request» step 1; stage C guesses C06-DEADLINE-PRECISION-33-01,
C47-DEADLINE-VECTORS-01, the Architect's decisions 2026-10-25). The participant is the request door of the console. The bytes are written by «Спецификация»;
the rows are by the text of the norm.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header `case<TAB>input<TAB>expect<TAB>note`.

| Field | Meaning |
|---|---|
| `input` | the text of the value `valid_until` from the request body — one JSON value, as sent |
| `expect` | `{"written": <текст>}` — the element of the request row by the time writer of P/01.1 Н0: truncation down to milliseconds (towards −∞), a negative one — `0`, an integer — without a fractional part; or `{"status": 400, "error": "bad deadline"}` — the value is not a finite JSON number (the refusal of step 1, P/06.4 Н4 RequestError) |

13 rows: 8 records (`0`, negative ones, `1e-12`, the truncation of `1000.1234` and `1.2349`, the integer `1000` and `1e3`), 5 refusals (`null`, a string,
bool, a list, the overflow `1e400`).

## Run

Without a stand: a side gives the value to its deadline translation of the door and compares the result — JSON by value as a whole
(`written` — a string byte for byte). The check `too far` (by the value as
sent, against `now` and `most_valid`) is not here: the acceptance of chapter 6.4, sc. 04 and 06.
Who performs it — the console (`06-console`: the request door translates the sent deadline, P/06.4 Н3 «file a request» step 1). The worker (`03-worker`) does no translation: it reads a ready `valid_until` from the request row (P/03.6 Н3), its own filing is without a deadline sent by a client (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-27).

## Vector wire

The wire of `cases.tsv` is set by the `common/deadline` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.
