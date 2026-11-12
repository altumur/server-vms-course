# Vectors: the closed lists of the platform

This English text is the source; the Russian translation `ru/vectors/platform-lists/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The owner is chapter [P/02.5](../../spec/02.5-installer.norms.md) of the installer (N1.3 `roles`, `platform_readers`; N1.4 —
the negations of the secret readers). The participants are the loader [P/02.1](../../spec/02.1-installer.norms.md)
(N1.2a: `heartbeat.strings` names no string fields of the platform heartbeat; `display.tree.columns[].field` and
`display.form[].fields[]` — a field of the unit or a name from `platform_shown`; `objects.rows[]` names no families of the platform) and
the rights generator P/02.5 N2. The bytes are written by the Specification; the conformance of the product — by its acceptance against this table.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` are explanations, empty ones are skipped. There is no header. Two fields: `list` — the name of the list,
`word` — its element. Each list is a set: the order of the rows is not compared.

| List | What is in it | Norm |
|---|---|---|
| `heartbeat_strings` | the string fields of the platform in every heartbeat: `heartbeat.strings` of a manifest names none of them | P/02.1 N1.2a `heartbeat.strings`; P/03.4 N1.1 |
| `secret_roles` | the roles that `secrets.readers` may name | P/02.5 N1.3 `roles` |
| `secret_readers` | the secret rows of the platform and their readers, `<row or prefix>=<role>`; `<row>=` — nobody except the reader named by the manifest | P/02.5 N1.3 `platform_readers` |
| `platform_shown` | the fields of a platform unit that a manifest may name where it shows a unit | P/02.1 N1.2a (reference row 71 `display.tree.columns[].field`) |
| `object_families` | the object families of the platform under `objects/<sub>/`: `objects.rows[]` of a manifest names none of them; `*` — the prefix of the whole family | P/02.1 N1.2a `objects.rows`; P/05 N1.1 `key` |

## Run

The side compares each of its closed lists with the set of words of this list in the table: equality of sets. A list
that the table does not name, or a word beyond the table, is a mismatch.
Who executes — by `list`, the installer (`02-installer`): `heartbeat_strings`, `platform_shown`, `object_families` — the loader (P/02.1 N1.2a, reference rows 73 and 84); `secret_roles`, `secret_readers` — the rights generator (P/02.5 N1.3 `roles`, `platform_readers`, N3 step 4). Only read the ready result: the worker (`03-worker`, P/03.4 N1.1 `platform_strings` — the fields it writes), the resource (`05-resource`, its own `PLATFORM_DOOR`, P/05 N2), the console (`06-console`, P/06.5 N1.2 `tree.columns`) and the process `domain` (`08-domain`, P/08.2 N1.3 `readers`) (a row is executed by the role whose norm calls its function).


## What the vector does not cover

The loader refusal on a manifest that names a word from the list — the cases of the corpus of [the acceptance of P/02.1](../../acceptance/1/) (judge-only: the corpus cases);
the derivation of the rights for the secret rows — the variants of [the acceptance of P/02.5](../../acceptance/5/) and sc. 06 of [the acceptance of chapter 6.2](../../../06-console/acceptance/2/README.md) (judge-only: the variants and the scenario).

## Vector wire

The wire of `cases.tsv` (judge-only: the table itself) is set by the `02-installer/platform-lists` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native outcome and comparison. Algorithm meaning and consumer obligations remain here.
