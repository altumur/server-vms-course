# Vectors: whether a hold row holds a bucket

This English text is the source; the Russian translation `ru/vectors/holds/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the holds contract](../../contracts/holds.md) (the owner of the contract is lesson P/06, [chapter 6.4](../../../06-console/spec/06.4-console.norms.md)
N1.5 `holds`): the sections «Declaration», «Hold row», «What a row holds». The function of the package is «whether a row holds a bucket»
of the section «Vectors» of the contract (ADR-0083 addendum (37) item 5). The bytes are written by «Specification»; the rows are by the text of the contract.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header
`case<TAB>holds<TAB>types<TAB>row<TAB>bucket<TAB>expect<TAB>note`.

| Field | Meaning |
|---|---|
| `holds` | the section `holds` of the manifest — a JSON object with keys from `{table, unit, since, until, released, longest}` (P/02.1 N1.2); `null` — there is no section |
| `types` | the field types of the hold table `tables.<table>.fields` — a JSON object `{field: type}`, the type words are as in [`values-by-type`](../values-by-type/README.md) |
| `row` | the row `<M>/<table>/<id>` — a JSON object `{field: element text}` (no element — no key); `@garbled` — the row did not decode as a table row |
| `bucket` | the beginning of the bucket, wall seconds (a multiple of 600: the event journal contract `bucket` `span`); the span is `[start, start + 600]` |
| `expect` | `{"hold": "held"}` — it holds; `{"hold": "not_held"}` — it does not hold (released, an empty window, the bucket outside the window, there is no section); `{"hold": "unknown"}` — the addressee or the window are not read, the declaration is incomplete or the row did not decode: it holds by the rule «unread — held» («What a row holds» rows 2–3, «Declaration» `partial`), the row — in `garbled_rows.<table>` of the resource heartbeat |
| `note` | the rule of the contract |

38 rows: 11 `held`, 12 `not_held`, 15 `unknown`. The window — the ends inclusive (touching `since` by the end of the bucket and `until`
by the beginning), `float` with a fractional second at both ends, `int` with the notation `.0` and with a fraction; `longest` shorter and longer than the window;
`until = since` and `until < since`; `released` non-empty, `0` at an `int` field, empty, without an element, not declared, over unreadable
fields; `unit` without an element, empty, with spaces (as is); `since`/`until` without an element, not reading as their type, with the sign
`-` or `+` and with an exponent (not of the form of the reader `time` of the codec), a field of a non-numeric type; an incomplete declaration; an undecoded row; a manifest without `holds`.

## Run

Without a stand: a side gives the declaration, the field types, the row and the bucket span to its function «whether a row holds a bucket» and
compares `hold`. The belonging of the bucket to the addressee (the trees `<A>`, `<A>.alarms`, the hold «about» by `about.field` and
the tombstone) is outside the function: the input is a bucket already attributed to the unit that the row names. Who performs it — the resource
(`05-resource`: the term pass, [P/05](../../../05-resource/spec/05-resource.norms.md) N3 «resource pass» `retain`). The console
(`06-console`) writes the hold rows by the table door (P/06.1 N1.6) and does not perform the function; the loader (`02-installer`) checks
only the references of the section (P/02.1 N1.2, references 50–54) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function).

In the input of the single command `vectors` ([the common acceptance README](../../acceptance/README.md)) `cells` are `holds`, `types`, `row`,
`bucket` (the text of the cells as written); `files` is empty. The result is one JSON object `{"hold": …}`.

## What the vector does not cover

The listing of the rows of the table and its break (the contract «Reading the table»: the holds are not read — `holds_unread`), the choice of the trees
of the addressee and the hold «about» by `about` (the section «Declaration» `addressee`, «What a row holds» row 1), the count of `garbled_rows`
and the heartbeat reasons (P/05 N1.4, N4), the cleanup by term itself (the stand does not wait out the term of buckets: P/05-06, P/06.4-08 — by reading).
