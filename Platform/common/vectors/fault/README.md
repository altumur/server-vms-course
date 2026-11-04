# Vectors: the dictionary `fault` of door refusals

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is chapter P/06.1 ([the norms](../../../../06-console/spec/06.1-console.norms.md) Н2: the refusal answer `{detail, error, fault?}`; Н4: the reasons
with `fault` — `not_json`, `not_number`, `too_long`, `bad_url`, `unique`, `must_match`, `garbled`). The participants are the doors that
speak these words: the tables door (P/06.1 Н4 «Bodies, tables…»), the requests door ([chapter 6.4](../../../../06-console/spec/06.4-console.norms.md);
the vector [`requests-body`](../../../../06-console/vectors/requests-body/README.md)), sealing by the console ([chapter 6.2](../../../../06-console/spec/06.2-console.norms.md): `bad_url` at an address with
a password), the units door of the console and the customer's library (`06-console`, `03-worker`: the word `bad_url` of the vector
[`group-of`](../../group-of/) is from here; the controller, [P/04](../../../../04-controller/spec/04-controller.norms.md) `group_by`, only computes
the group and does not speak refusal words — C04-VECTOR-FAULT-167, the Architect's decision of 2026-10-27), the doors of the domain (lessons 8–10). The bytes are written by
«Спецификация» (ADR-0083, stage B; the Architect's decision of 2026-10-06 on the closed dictionary); the conformance of the product is by its
acceptance against this table (ADR-0080 addendum 16).

The package was moved from `Source/tests/testdata/fault.tsv` (stage A) together with lesson 6 (stage B, ADR-0083 addendum (1)); the bytes
of the table are the same, including the header comment (its «lesson 03 Н4» is the former address of the norm, now P/06.1 Н4; the copy of the product
is reconciled with these bytes).

## `fault.tsv`

UTF-8, LF, fields separated by TAB. Lines with `#` and empty lines are skipped; there is no header line. Two fields:

| Field | Meaning |
|---|---|
| `word` | the word `fault` — what a door refusal says to a machine and a test beside `detail` for a human |
| `status` | the HTTP code with which the word comes: 400 — the body itself is wrong; 409 — the refusal depends on the standing rows (ADR-0031): `garbled` — the row that `ref` points at is not read; a non-answer of the store is a store error, not this word |

## Rules

- The dictionary is closed: a new word appears **first** here, then in the code of both sides. The word `error` of the door is not compared.
- The tables that name `fault` (`requests_body.tsv` — column 4, the vector `group-of` — column 3) take words only
  from here.
- `fault` exists only at the reasons of Н4 of chapter 6.1; `409 conflict` always carries it; `exists`, `in flight`, `key reused`
  do not add it (P/06.1 Н2).

## Run

A side reads the table and checks: (1) every word `fault` that its doors speak is in the table and comes with the code
of the column `status`; (2) the participant tables name only words of this table.
Who performs: the console (`06-console`) — the whole table (the command `fault` below); the other participants — the rows of the words that
their doors and functions speak: the doors of the domain
(`08-domain`, `09-agent`, `10-domain-console`) — the words of their refusals (Н4 of lessons 8–10); the controller (`04-controller`) does not speak
`fault` words — it has no door with refusals, `group_by` only computes the group (C04-VECTOR-FAULT-167, the Architect's decision of
2026-10-27) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-26).

## Stand command `fault`

The key `stand` of the profile `06-console` (the section «Layout by processes» of [the common acceptance README](../../../acceptance/README.md));
a template with `{input}` — the path of a file with an object of exactly `{}`. One call per table: the answer is the full map of its own dictionary
of refusals `{<слово>: <код HTTP>}`, the code is a JSON integer (not a string, not a bool); the set of words and every code equal `fault.tsv`,
the order of fields does not matter; a word beyond the table or a missing one — FAIL. An input not of the form: not an object or a non-empty object.
stdout is exactly one JSON object and LF: the first byte is `{`, after the object — LF and the end; extra fields, bytes, CRLF, whitespace around — FAIL of the row; formatting inside the object is allowed; service output goes to stderr. Code 0 — computed; an input not of the form — code 2, stdout empty. There is no envelope `result` (the guess of stage C C06-F2-IO-02, the Architect's decision of 2026-10-23).
Through the record `vectors` `common/fault` of the profile (the single command of the common acceptance README; it or `stand.fault` is enough — ACC-VECTORS-COVERS-STAND-01) — the same one call per table: the frame `table` `fault.tsv`, `case` `fault.tsv`, `variant` `""`, `cells` `{}`, `files` `{}`; the native outcome is by this section (ACC-VECTORS-FAULT-FRAME-01, the decision of «Спецификация»).
