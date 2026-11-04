# Vectors of book assembly

This English text is the source; the Russian translation `ru/vectors/assemble/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The vectors of the function `assemble` of [chapter P/08.5](../../spec/08.5-domain.norms.md): the assembly of one book at the holder without
a store, a network and a stand — the input is the copies of the members of the list and their view state, the output is the book rows of each member before the ring
(secrets opened) and a view report `{conflicts, dropped, undelivered}` (Н1.3, Н1.5, Н3 «сборка книги»; Н5 «`assemble`»).
The owner is lesson P/08, chapter 8.5; the function is performed by the process `domain` (the holder's pass once per `VIEW_EVERY`). The bytes are written by
«Спецификация» (ADR-0083); the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16).

The rows were transferred from the steps of the acceptance of М11/05
(sc. 06, 17 steps; the command `assemble` on `inputs/assemble-*.json`) at the move of lesson 8 (the plan of the move of lesson 8, § 3 and В1;
the decision of «Архитектор» 2026-10-20, ADR-0083 addendum (14)). `case` is the name of the input file, `note` is the scenario and the step of the acceptance of М11/05.
The input is the JSON of the file in one line: only insignificant whitespace outside strings is removed; the order of keys, the lexemes of numbers and the values are as
in the file. The expectation is a subset of the acceptance step as it is (after `ok `); the step `@exit 2` is `@exit 2`. The scenario М11/05 sc. 06 and
its inputs were removed by the move of lesson 8 (the row of `corrections.tsv` of the acceptance of М11/05): the table is the only source of these cases.

## Run

Without a stand: the command `assemble` of an implementation gets the input (the column `input`) and prints the JSON `{rows, report}`; `expect` is
a subset of the fields of the output by the dictionary of the «Stand» ([the common acceptance README](../../../common/acceptance/README.md), `<код>
<JSON>`: the named fields exist and are equal, `"@absent"` — there is no field, an array — by length, order and elements) or `@exit 2` (an input
not of the form of Н5: the keys of `copies` are not exactly `members`; `grants` without `now`). Each row is a separate run.

## Inputs, keys and manifests

The input is Н5 of the chapter: `book` is `testsub2/notes` (`pick: unique`, the names index `notes/` with `grant: view`) or `testsub2/rolls`
(`pick: all`), `members` is the list of members, `book_seal_seed` is the `seed_secret` of the book acceptance key (`book seal 1`,
[the README of the package `domain-token`](../../../common/vectors/domain-token/README.md#ключи) «Keys»), `copies` is the state and the objects of the copy
of each member (`null` — there is no copy), `grants` and `now` are the grant rows of the receivers for the rule Н1.3 `grant`. The secrets of the
inputs are envelopes `x25519:v1` to `book seal 1` (in case 07 — to `book seal 2`: it does not open), `eph 1`, `nonce` 0…11
([the domain envelopes contract](../../../common/contracts/domain-envelopes.md) «Конверт `x25519:v1`», the AAD is `[член, ключ строки,
item]` and the JSON Pointer of the secret). Case 12 is a secret in the member's ring envelope `enc:v2:`: the member did not open it, and the agent carried it as
it is ([chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md) Н1.2) — the assembly gives `secret_unopened`.

The expectations depend on the bytes of the catalog manifests (the review analysis of stage A 8–10, № 37): `domain.books` (`from`, `key`, `pick`, `to`) and
`domain.names` of the manifest `testsub2` from the specification data:

| Manifest | File | sha256 |
|---|---|---|
| `testsub` | [`Source/tests/testdata/testsub.subsystem.yaml`](../../../../Source/tests/testdata/testsub.subsystem.yaml) | `7e6118cea2d639e11e894208d5f5be1d82cd1ec385cac0231fe7449305e5430a` |
| `testsub2` | [`Source/tests/testdata/testsub2.subsystem.yaml`](../../../../Source/tests/testdata/testsub2.subsystem.yaml) | `813a807f3472bdc64e279c94c12bfe3b00ebaaa8ebda0c996d2a50161043e6eb` |

The bytes of `testsub2` changed on 2026-11-04 (roadmap 4.5): the token kind `vault` with `keep: true` was added to `domain.tokens`, then the comments of the header were rewritten without the names of test files; the fields on which the expectations of this table depend are not touched — a recheck by the oracle is not needed.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header.

| File | Input → expectation |
|---|---|
| [`cases.tsv`](cases.tsv), 23 rows: 22 computed, 1 `@exit 2` | `input` is the input of `assemble` as JSON text → `expect`: the rows `rows` (delivery only to the members from `to`, the order of `entries` by (member, item), `missing` with closed words, the key of a `unique` conflict and one not delivered by the grant — `"@absent"`, an opened secret in `value`) and `report` (`conflicts`, `dropped` — `bad_contribution`, `secret_unopened`, `undelivered`); `@exit 2` — `grants` without `now` |

| Cases | What it checks |
|---|---|
| 01, 09 | delivery by `to`, the holder is a receiver too; a receiver outside the list — `undelivered`, it gets nothing |
| 02, 03 | a `unique` conflict — the key is absent at everyone; `all` — all contributions, the order by (member, item) |
| 04, 05, 11, 13 | a spoiled input (no `key`, an empty `key`, unequal elements of one `key` at one member, including in two slots) — the whole contribution is removed; the form before the secrets |
| 18, 19 | equal elements of one `key` at a member in two slots — one entry, the smallest `item`; equality after the opening of the secrets, the envelopes differ |
| 06, 07, 12 | a secret is opened (`value` with the opened value); a foreign `book_seal`, a ring envelope not opened by the member — `secret_unopened` |
| 08 | `unseen` contributes into `missing` too; `silent`, `never`, `no_copy` |
| 10 | objects outside the `from` of the book are not read |
| 14–16 | the names index `notes/` with `grant: view`: a grant row of the receiver — the key is delivered; no rows — only `""`; `grants: null` — the rule is not applied |
| 17 | `grants` without `now` — `@exit 2` |
| `to-all`, `star-in-plain-book`, `to-servers` (ADR-0113 addendum (8) item 4, (11) item 1) | a book with `to: "*"` — the head and the row of the key's section, the field `to` of the input is not read; `"*"` in the input of an ordinary book — the cost of a row per member is not returned; `to` `servers` — a camera receives nothing |
| `13-missing-shown` (the analysis of stage 8) | `missing_count` — all, `missing` — the first 500, the class `server` first |

The vectors are checked by an oracle against the text of the norms (Н1.3, Н3 «сборка книги», Н5; the opening of a secret — by reference X25519, HKDF-SHA256
and AES-256-GCM by the domain envelopes contract; the acting grant row — [the right contract](../../../common/contracts/may.md)
step 5), not against the code of implementations: the output of the oracle contains the expectation of each row. On a divergence the text of the norm is right, the vector
is corrected by «Спецификация».
