# Vectors of book assembly

This English text is the source; the Russian translation `ru/vectors/assemble/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The vectors of the function `assemble` of [chapter P/08.5](../../spec/08.5-domain.norms.md): the assembly of one book at the holder without
a store, a network and a stand — the input is the copies of the members of the list and their view state, the output is the book rows of each member before the ring
(secrets opened) and a view report `{conflicts, dropped, undelivered}` (N1.3, N1.5, N3 «assembly of a book»; N5 «`assemble`»).
The owner is lesson P/08, chapter 8.5; the function is performed by the process `domain` (the holder's pass once per `VIEW_EVERY`). The bytes are written by
«Specification»; the conformance of the product is by its acceptance against this table.

`case` is the name of the case, `note` is a comment on the row.
The input is JSON text in one line: only insignificant whitespace outside strings is removed; the order of keys, the lexemes of numbers and the values are kept
as they are. The expectation is written as in a stand step after `ok `; `@exit 2` is `@exit 2`. The table is the only source of these cases.

## Run

Without a stand: the command `assemble` of an implementation gets the input (the column `input`) and prints the JSON `{rows, report}`; `expect` is
a subset of the fields of the output by the dictionary of the «Stand» ([the common acceptance README](../../../common/acceptance/README.md), `<code>
<JSON>`: the named fields exist and are equal, `"@absent"` — there is no field, an array — by length, order and elements) or `@exit 2` (an input
not of the form of N5: the keys of `copies` are not exactly `members`; `grants` without `now`). Each row is a separate run.

## Inputs, keys and manifests

The input is N5 of the chapter: `book` is `testsub2/notes` (`pick: unique`, the names index `notes/` with `grant: view`) or `testsub2/rolls`
(`pick: all`), `members` is the list of members, `book_seal_seed` is the `seed_secret` of the book acceptance key (`book seal 1`,
the `domain-token` checking data «Keys»), `copies` is the state and the objects of the copy
of each member (`null` — there is no copy), `grants` and `now` are the grant rows of the receivers for the rule N1.3 `grant`. The secrets of the
inputs are envelopes `x25519:v1` to `book seal 1`, `eph 1`, `nonce` 0…11
([the domain envelopes contract](../../../common/contracts/domain-envelopes.md) «Envelope `x25519:v1`», the AAD is `[member, row key,
item]` and the JSON Pointer of the secret).

The expectations depend on the bytes of the catalog manifests: `domain.books` (`from`, `key`, `pick`, `to`) and
`domain.names` of the manifest `testsub2` from the specification data.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header.

| File | Input → expectation |
|---|---|
| the vector cases, 23 rows: 22 computed, 1 `@exit 2` | `input` is the input of `assemble` as JSON text → `expect`: the rows `rows` (delivery only to the members from `to`, the order of `entries` by (member, item), `missing` with closed words, the key of a `unique` conflict and one not delivered by the grant — `"@absent"`, an opened secret in `value`) and `report` (`conflicts`, `dropped` — `bad_contribution`, `secret_unopened`, `undelivered`); `@exit 2` — `grants` without `now` |

The vectors are checked by an oracle against the text of the norms (N1.3, N3 «assembly of a book», N5; the opening of a secret — by reference X25519, HKDF-SHA256
and AES-256-GCM by the domain envelopes contract; the acting grant row — [the right contract](../../../common/contracts/may.md)
step 5), not against the code of implementations: the output of the oracle contains the expectation of each row. On a divergence the text of the norm is right, the vector
is corrected by «Specification».
