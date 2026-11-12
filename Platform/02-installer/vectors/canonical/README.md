# Vectors: the canonical view of a manifest

This English text is the source; the Russian translation `ru/vectors/canonical/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The owner is chapter [P/02.2](../../spec/02.2-installer.norms.md) of the installer (N1.1 projection, P/02.2-R041, P/02.2-R047, P/02.2-R048, P/02.2-R051, P/02.2-R054, P/02.2-R055, P/02.2-R060, P/02.2-R061, P/02.2-R073 to P/02.2-R075). The participants are
the loader [P/02.1](../../spec/02.1-installer.norms.md) (the view is built only from an accepted manifest, verdict `ok`) and the installer
`manifest put` [P/02.3](../../spec/02.3-installer.norms.md) N3 (writes the view next to the row). A vector is the bytes of a manifest → the bytes of the field
`manifest` of the view row `platform/manifest/<sub>/canonical/1`; the wrapper `{form, rev, sha256, manifest}` and `rev` are not vectors but
[the acceptance of chapter 2.2](../../acceptance/2/README.md). Both implementations — byte for byte.

## Composition

| What | Where | Who writes |
|---|---|---|
| table of cases | `cases.tsv` (judge-only: the table itself; it checks P/02.2-R005, P/02.2-R007, P/02.2-R009, P/02.2-R012, P/02.2-R014, P/02.2-R015, P/02.2-R016, P/02.2-R017, P/02.2-R018, P/02.2-R019, P/02.2-R020, P/02.2-R021, P/02.2-R024, P/02.2-R025, P/02.2-R043) | rows `corpus-*`, `course-*` — the builder; rows `example-*` — the Specification |
| expected bytes | `expect/<case>.json` — one file per row | the builder of the skill `lesson-spec`, not edited by hand |
| inputs of the example rows | `inputs/<name>.subsystem.yaml` | the Specification |

Inputs of the rows:
- `corpus-<case>` — each accepted case of the corpus of chapter 2.1 (`acceptance/1/verdicts.tsv`, verdict `ok`; judge-only: the corpus table; the rows `corpus-*` check P/02.2-R005, P/02.2-R007, P/02.2-R012, P/02.2-R021, P/02.2-R024, P/02.2-R025, P/02.2-R043);
- `course-<name>` — each manifest of the course `Platform/common/data/testsub/*.subsystem.yaml`;
- `example-<rule>` — one row per rule of N1.1: a section without a default and with a default, a nested key, sugar ×3, P1 (and a stated `snapshot: []`), P2–P5,
  `ordered`. The input of an example row is a small manifest that changes one rule against the minimal one; what it shows is
  the field `note`.

The mutation probe of `check_spec`: removing each annotation `default` and each mark `x-ordered` in the schema
of chapter 2.1 and skipping each step of lesson 2 change the bytes of at least one vector.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` are explanations, empty ones are skipped. The first non-skipped row is the header
`case<TAB>input<TAB>expect<TAB>note`, then one row per case; exactly four fields.

- `case` — the name of the case: `[A-Za-z0-9][A-Za-z0-9_.-]*`, unique in the file;
- `input` — the path of the manifest file from the root of the layout (the course or the export `cammeta-specs`): with `/`, without `..`, ending in
  `.subsystem.yaml`; the loader of chapter 2.1 accepts it;
- `expect` — exactly `expect/<case>.json`: the bytes of the view — JCS,
  UTF-8, without a line feed at the end;
- `note` — what the row shows (not compared).

## Run

For each row the side reads the bytes of the file `input`, builds the canonical view by N1.1 of chapter 2.2 (by its own pass over the tree
of the loader or by shared code — «Implementation decides» item 1) and compares the bytes with the file `expect` as a whole. A different byte, an extra
line feed or a load refusal is a mismatch of the row.
Who executes — the installer (`02-installer`: «build view» P/02.2 N3 — for `manifest put`, P/02.3 N3, and for a cluster of one with a built-in manifest, P/02.4 N1.10). Only read the ready result: the worker runner (`worker.exec` from the view, P/02.3 N3 «Worker program from the row») and the readers of the view (P/02.2 N3 «Reader»: the mark, `rev`, `sha256`, the schema) (a row is executed by the role whose norm calls its function).

## What the vector does not cover

The wrapper of the view row, the write order row — view — mark, «unchanged» with the view, the refusal `toolarge` of the view — the acceptance of chapter
[`acceptance/2/`](../../acceptance/2/README.md). The schema of the view — the section «Form of the canonical view» of the norms of chapter 2.2 (P/02.2-R036, P/02.2-R039;
`check_spec` checks that the view of each input passes it). The reader of the view — by the edits of the readers (P/02.2-R062, P/02.2-R064, P/02.2-R067, P/02.2-R068, P/02.2-R069, P/02.2-R070, P/02.2-R072).

## Vector wire

The wire of `cases.tsv` (judge-only: the table itself; it checks P/02.2-R005, P/02.2-R007, P/02.2-R009, P/02.2-R012, P/02.2-R014, P/02.2-R015, P/02.2-R016, P/02.2-R017, P/02.2-R018, P/02.2-R019, P/02.2-R020, P/02.2-R021, P/02.2-R024, P/02.2-R025, P/02.2-R043) is set by the `02-installer/canonical` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native outcome and comparison. Algorithm meaning and consumer obligations remain here.
