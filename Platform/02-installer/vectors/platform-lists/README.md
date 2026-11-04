# Vectors: the closed lists of the platform

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is chapter [P/02.5](../../../spec/02.5-installer.norms.md) of the installer (Н1.3 `roles`, `platform_readers`; Н1.4 —
the negations of the secret readers; review analysis of stage A 6–7, № 5). The participants are the loader [P/02.1](../../../spec/02.1-installer.norms.md)
(Н1.2а: `heartbeat.strings` names no string fields of the platform heartbeat; `display.tree.columns[].field` and
`display.form[].fields[]` — a field of the unit or a name from `platform_shown`; `objects.rows[]` names no families of the platform) and
the rights generator P/02.5 Н2. The bytes are written by the Specification; the conformance of the product — by its acceptance against this table (ADR-0080
addendum 16, ADR-0083). Moved from `Source/tests/testdata/platform_lists.tsv` byte for byte (stage B, the move of lesson 6,
the Architect's decision on В8 of the plan of lesson 6 with correction № 5).

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` are explanations, empty ones are skipped. There is no header. Two fields: `list` — the name of the list,
`word` — its element. Each list is a set: the order of the rows is not compared.

| List | What is in it | Norm |
|---|---|---|
| `heartbeat_strings` | the string fields of the platform in every heartbeat: `heartbeat.strings` of a manifest names none of them | P/02.1 Н1.2а `heartbeat.strings`; P/03.4 Н1.1 |
| `secret_roles` | the roles that `secrets.readers` may name | P/02.5 Н1.3 `roles` |
| `secret_readers` | the secret rows of the platform and their readers, `<строка или префикс>=<роль>`; `<строка>=` — nobody except the reader named by the manifest | P/02.5 Н1.3 `platform_readers` |
| `platform_shown` | the fields of a platform unit that a manifest may name where it shows a unit | P/02.1 Н1.2а (reference row 71 `display.tree.columns[].field`) |
| `object_families` | the object families of the platform under `objects/<sub>/`: `objects.rows[]` of a manifest names none of them; `*` — the prefix of the whole family | P/02.1 Н1.2а `objects.rows`; P/05 Н1.1 `key` |

## Run

The side compares each of its closed lists with the set of words of this list in the table: equality of sets. A list
that the table does not name, or a word beyond the table, is a mismatch.
Who executes — by `list`, the installer (`02-installer`): `heartbeat_strings`, `platform_shown`, `object_families` — the loader (P/02.1 Н1.2а, reference rows 73 and 84); `secret_roles`, `secret_readers` — the rights generator (P/02.5 Н1.3 `roles`, `platform_readers`, Н3 step 4). Only read the ready result: the worker (`03-worker`, P/03.4 Н1.1 `platform_strings` — the fields it writes), the resource (`05-resource`, its own `PLATFORM_DOOR`, P/05 Н2), the console (`06-console`, P/06.5 Н1.2 `tree.columns`) and the process `domain` (`08-domain`, P/08.2 Н1.3 `readers`) (ACC-VECTORS-CONNECT-03: a row is executed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## Native outcome

The expectation column is `word`, the set of words of one `list`: one call per list, the input — `cells` `{"list": <имя>}`; the outcome —
code 0 and a JSON array of strings — all words of this closed list of the side; the comparison — equality of sets with the words of the rows
of the table of this `list` (order and repeats do not matter) (the Architect's decision of 2026-10-27; the common rule «Vectors» of [the common acceptance
README](../../../../common/acceptance/README.md)).

## What the vector does not cover

The loader refusal on a manifest that names a word from the list — the cases of the corpus of [the acceptance of P/02.1](../../../acceptance/1/);
the derivation of the rights for the secret rows — the variants of [the acceptance of P/02.5](../../../acceptance/5/) and sc. 06 of [the acceptance of chapter 6.2](../../../../06-console/acceptance/2/README.md).
