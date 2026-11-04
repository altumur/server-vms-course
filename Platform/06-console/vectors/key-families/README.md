# Vectors: the key families of the domain `families`

This English text is the source; the Russian translation `ru/vectors/key-families/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is chapter P/06.7 ([norms](../../spec/06.7-console.norms.md) Н1.11 `families`; stage C guess
C06-DOMAIN-KEY-FAMILIES-168-21, the Architect's decision of 2026-10-27). The participant is the cluster console (the door `GET /domain/keys`).
The declaration `domain.keys` and its load refusals are [P/02.1 Н1.2б](../../../02-installer/spec/02.1-installer.norms.md)
(the cases `m59_keys_*`). The bytes are written by the Specification; the rows follow the text of the norm, the rule is there, not here.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header
`case<TAB>decls<TAB>present<TAB>expect<TAB>note`.

**Input** — `decls`: the declarations `domain.keys` of the catalogue manifests, a JSON object `{<sub>: [{id, keys?, prefix?}]}` (the keys and
the family are under `domain/<sub>/`, as loading requires); `present`: the keys of the rows under `domain/` of this store, a JSON array, the order
does not matter.

**Output** — `families`: `{<id>: [<ключ>…]}`; the comparison is JSON by value, the order in an array matters.

12 rows: one manifest (no keys — an empty list, sc. 06 step 2; a named key and keys under `prefix`); one `id` in two
manifests — the union, the same answer with another order of the manifests, keys of only one side (each), of neither; a common
`id` next to their own ones; a named key under `prefix` — once; `prefix` — by bytes; the order is ascending by UTF-8 bytes
(ASCII and non-BMP: 😀 after ｚ, although in UTF-16 it would come earlier).

## Run

Without a stand: the side gives the input to its own computation of `families` of the door `GET /domain/keys` (the catalogue manifests and the read of the rows under
`domain/` are replaced by the input). The native outcome is code 0 and the value `families` (one expectation column — the common rule «Vectors»
of [the common acceptance README](../../../common/acceptance/README.md)); the input is `cells` `decls`, `present`.
Who executes it is the cluster console (`06-console`, P/06.7 Н1.11 `families`). The console module (`07-console-module`) takes
`families` ready-made: the subsystem page selects its own keys by prefix (ACC-VECTORS-CONNECT-03: a row is executed by the role whose
norm calls its function; the Architect's decision of 2026-10-27).
