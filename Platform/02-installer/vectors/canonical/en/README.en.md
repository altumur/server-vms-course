# Vectors: the canonical view of a manifest

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is chapter [P/02.2](../../../spec/02.2-installer.norms.md) of the installer (Н1.1 projection, P/02.2-07). The participants are
the loader [P/02.1](../../../spec/02.1-installer.norms.md) (the view is built only from an accepted manifest, verdict `ok`) and the installer
`manifest put` [P/02.3](../../../spec/02.3-installer.norms.md) Н3 (writes the view next to the row). A vector is the bytes of a manifest → the bytes of the field
`manifest` of the view row `platform/manifest/<sub>/canonical/1`; the wrapper `{form, rev, sha256, manifest}` and `rev` are not vectors but
[the acceptance of chapter 2.2](../../../acceptance/2/README.md) (ADR-0089 addendum (1) Р13). Both implementations — byte for byte. The window of chapter 2.2 is
`decisions/inbox/2026-10-20-окно-главы-2.2-канонический-вид.md` (section 5, the Architect's decision — item 8).

## Composition

| What | Where | Who writes |
|---|---|---|
| table of cases | `cases.tsv` | rows `corpus-*`, `course-*` — the builder; rows `example-*` — the Specification |
| expected bytes | `expect/<case>.json` — one file per row | the builder of the skill `lesson-spec`, not edited by hand |
| inputs of the example rows | `inputs/<имя>.subsystem.yaml` | the Specification |

Inputs of the rows:
- `corpus-<случай>` — each accepted case of the corpus of chapter 2.1 (`acceptance/1/verdicts.tsv`, verdict `ok`);
- `course-<имя>` — each manifest of the course `Source/tests/testdata/*.subsystem.yaml`;
- `example-<правило>` — one row per rule of Н1.1 (the defaults note `decisions/inbox/2026-10-19-умолчания-канонического-вида.md`,
  section 5): a section without a default and with a default, a nested key, sugar ×3, П1 (and a stated `snapshot: []`), П2–П5,
  `ordered`. The input of an example row is a small manifest that changes one rule against the minimal one; what it shows is
  the field `note`.

The mutation probe of `check_spec` (ADR-0089 Confirmation): removing each annotation `default` and each mark `x-ordered` in the schema
of chapter 2.1 and skipping each step of lesson 2 change the bytes of at least one vector.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` are explanations, empty ones are skipped. The first non-skipped row is the header
`case<TAB>input<TAB>expect<TAB>note`, then one row per case; exactly four fields.

- `case` — the name of the case: `[A-Za-z0-9][A-Za-z0-9_.-]*`, unique in the file;
- `input` — the path of the manifest file from the root of the layout (the course or the export `cammeta-specs`): with `/`, without `..`, ending in
  `.subsystem.yaml`; the loader of chapter 2.1 accepts it;
- `expect` — exactly `expect/<case>.json`: the bytes of the view — JCS ([ADR-0072](../../../../../decisions/0072-канонический-json-подписанных-документов-rfc-8785.md)),
  UTF-8, without a line feed at the end;
- `note` — what the row shows (not compared).

## Run

For each row the side reads the bytes of the file `input`, builds the canonical view by Н1.1 of chapter 2.2 (by its own pass over the tree
of the loader or by shared code — «Implementation decides» item 1) and compares the bytes with the file `expect` as a whole. A different byte, an extra
line feed or a load refusal is a mismatch of the row.
Who executes — the installer (`02-installer`: «build view» P/02.2 Н3 — for `manifest put`, P/02.3 Н3, and for a cluster of one with a built-in manifest, P/02.4 Н1.10). Only read the ready result: the worker runner (`worker.exec` from the view, P/02.3 Н3 «Программа воркера из строки») and the readers of the view (P/02.2 Н3 «Reader»: the mark, `rev`, `sha256`, the schema) (ACC-VECTORS-CONNECT-03: a row is executed by the role whose norm calls its function; the Architect's decision of 2026-10-27).

## What the vector does not cover

The wrapper of the view row, the write order row — view — mark, «без изменений» with the view, the refusal `toolarge` of the view — the acceptance of chapter
[`acceptance/2/`](../../../acceptance/2/README.md). The schema of the view — the section «Форма канонического вида» of the norms of chapter 2.2 (P/02.2-05;
`check_spec` checks that the view of each input passes it). The reader of the view — by the edits of the readers (P/02.2-06).
