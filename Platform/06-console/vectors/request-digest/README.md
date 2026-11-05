# Vectors: the request digest

This English text is the source; the Russian translation `ru/vectors/request-digest/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is chapter P/06.4 ([norms](../../spec/06.4-console.norms.md) Н1.5 `digest`, Н3 «file a request» step 1). The participants:
- `console` — a request filed through the door;
- `<s>worker` — a request that the worker writes itself (`worker.requests`).

The bytes of the table are written by the Specification (ADR-0083, stage A). The conformance of the product is by its acceptance against this table
(ADR-0080 addendum 16).

The bytes of the table did not change in the move of lesson 6 (stage B, ADR-0083 addendum (1)), including
the header comment (its «М10/8 Н1.5», «lesson-owner М10/8» are the former address of the norm, now [the contract of the request and its mark](../../../common/contracts/request-mark.md) (review analysis of stage B 6–7, № 24); the product copy
is checked against these bytes).

## `digest.tsv`

UTF-8, LF, fields separated by TAB. Rows with `#` and empty ones are skipped, the first non-skipped one is the header. Five fields:

| Field | Value |
|---|---|
| `sender` | `client` — the client body at the console door; `worker` — the row that the worker writes |
| `input` | `client` — the body as sent, JSON text; `worker` — the elements of the row as written, a JSON object of strings |
| `canonical` | the JCS text that is hashed (the normalized input) |
| `sha256` | hex SHA-256 of the UTF-8 bytes of the field `canonical` |
| `note` | what the row is for |

## Rules

**Client.** What is hashed is the JCS (RFC 8785, ADR-0072) of the body after the schema. Only `valid_until` is removed from the body — the only
server field that the client is entitled to send. `unit` stays.

**Worker.** What is hashed is the JCS of the object assembled from the fields of the row body as written (as text). Not included:
- `unit`;
- `valid_until`;
- the stamps `by`, `at`, `group` and the field `about` (for `testsub2` — `of`);
- `filed` — not a body field: the filer's instance, a row field that the worker writes (the contract of the request and its mark «Request» `filed`); the «поля тела строки»
  of the norm do not include it (review of stage A: SA1-27, Gemini 4.4).

**The two kinds of digest are not compared with each other.** A repeat is recognized by the digest of its own kind (the contract of the request and its mark «Request» `digest`).

**A target with `requests.key` — the kind `worker` for both writers** (the third rule; ADR-0091 addendum (24) item 3, addendum (25) item 3): one name
`rid` is given by the door and by the worker, therefore the door computes the digest of the kind `worker` from the fields of the row body as it will write them (as text:
a string — as is, anything else — JCS; the vectors [`requests-body`](../requests-body/README.md)), without `unit`, `valid_until` and the stamps;
a repeat checks `unit` and this digest, the mark copies it. The `worker` rows of the table apply to both writers; the kind `client` is
only for repeats of one client by `Idempotency-Key` at a target without `requests.key`.

## The stand command `request-digest`

The key `stand` of the profile `06-console` (the section «Layout by processes» of [the common acceptance README](../../../common/acceptance/README.md));
a template with `{input}` — the path of a file with one JSON object `{"sender": "client" | "worker", "input": <исходный текст ячейки input
строкой JSON>}`: the text of the cell is escaped only for the outer string — the number lexemes, the order of fields and the characters are preserved,
the runner does not parse the cell and does not re-serialize it. The answer is `{"canonical": <текст JCS>, "sha256": <64 строчных hex>}`: `canonical`
is compared with the column `canonical` by UTF-8 bytes, `sha256` — with the column `sha256`. An input not in form: not an object, a repeated or
unknown field, `sender` not one of the two words, `input` not a string, its text not a JSON object, for `worker` a value of the object not a string.
stdout is exactly one JSON object and LF: the first byte is `{`, after the object — LF and the end; extra fields, bytes, CRLF, spaces
around it — FAIL of the row; formatting inside the object is allowed; service output goes to stderr. Code 0 — computed; an input not in
form — code 2, stdout empty (stage C guess C06-F2-IO-01, the Architect's decision of 2026-10-23).

## Run

The side reads each row and checks two steps:
1. from `input`, by its kind, it obtains `canonical`, byte for byte;
2. SHA-256 of `canonical` equals `sha256`.
Who executes it is by `sender`: `client` — the console requests door (`06-console`, P/06.4 Н3 «file a request» step 1); `worker` — the same door at a target with `requests.key` (same place, the third rule) and the filing worker (`03-worker`, P/03.6 Н1.5 `worker.requests`). The holder and the reaper only read the ready result: they copy `digest` of the row into the mark (the contract of the request and its mark, `begun`, `no_begun`) (ACC-VECTORS-CONNECT-03: a row is executed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Vector wire

The wire of `digest.tsv` is set by the `06-console/request-digest` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.
