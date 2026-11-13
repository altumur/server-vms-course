# Vectors of following the holder

This English text is the source; the Russian translation `ru/vectors/follow/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The vectors of the function `follow(keys, held, answers)` of the agent of a member — the choice of whose term record to follow: its own row
`domain/holder` and the records from the answers of the consoles (`/api/held`, 409 `deposed`) are checked by the function `record`
of [the term record contract](../../../common/contracts/record.md) and compared by term. The owner is lesson P/09, chapter 9.1
([P/09.1](../../spec/09.1-agent.norms.md) N3 «follow», N5 `follow`); only the agent performs it.
The bytes are written by «Specification»; the conformance of the product is by its acceptance against this table.

`case` is the name of a case; the table is the only source of these cases.

## Run

Without a stand: the function of an implementation gets the input (the column `input`) and gives the output; `expect` is a subset of the fields of the output or
`@exit 2` (an input not of the form of P/09.1 N5 `exit`: `follow` has no `held` or `answers`, `answers` is not an object, an extra field, the trusted
set `keys` is not of the form). The function does not check the signature of the set itself: the set is trusted.
The absence of a field (`term` at `stay` without its own record that passed `record`) is not compared by the subset — N5 `follow`, by reading.

## Keys

The keys of the issuer and the set are bytes in the inputs (`keys.issuing`, `doc.issuer`). The seeds are `sha256("w2c test <word>")`, as
in the package `record`  «Keys» (the root `root 1`, the token key `token key 1`, the issuers
`issuing key 1`, `issuing key 0` — in `revoked_issuing`, `issuing key 9` — a foreign one, the members `member m1`, `member m2`). The set `keys`
of rows 01–12 is one: `domain: acme`, `rev: 2`, the root signature; rows 13–21 change in it only what their `note` names
(`keys` null, no `revoked_issuing`, `issuing` not a list, `sig` — 64 zero bytes).

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header; `note` is a comment;
in rows 13–21 it names the case of P/09.1 N5 `exit`.

| File | Input → expectation |
|---|---|
| Vector cases, 21 rows: 7 `follow`, 8 `stay`, 6 `@exit 2` | `input` — the input of the command `follow` as JSON text (`keys` — the set document, `held` — `{doc}` of its own row `domain/holder` or `null`, `answers` — `{<cluster>: {doc} \| null}`) → `expect`: `{"result":"follow","term":…,"holder":…,"url":…}` (a larger term; the same holder with a new `url` and a larger `at`; the same term at another holder; its own `held` is a backup copy document or a grant, it does not count as its own record) or `{"result":"stay","reason":<word>}` — `larger` (its own is larger), `holding` (the same; a forged or tampered larger answer — in `refused`), `two_holders` (two holders on one term), `none` (no answers; only a forged one); `refused` — `{<cluster>: <record word>}` |

On a discrepancy between a vector and the norms
the norm is right, «Specification» corrects the vector.
