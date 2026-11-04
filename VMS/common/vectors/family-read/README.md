# VMS family vectors (family-read)

This English text is the source; the Russian translation `ru/vectors/family-read/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

A table `NN.tsv` per VMS lesson that owns families of `VMS/common/data/catalog.tsv` (the Architect's decision on the VMS request
«семьи в открытых местах», option A). A row: the family (`family`, `kind`, `place` — a row of the VMS catalog), a concrete key,
the mode and the roles (`who`), the text of the platform family row (`text`, as in `Platform/common/vectors/family-read/`), the verdict and the refusal
paths (from the root of the row), the outcome for each reader (`outcome`: role → paths of the rows of `outcomes.tsv` of the VMS family, the paths are from
the value of the place). First the row is judged by the platform family, then by the VMS schema — the value in each instance of the place `place`.
Rows where the platform family itself refuses are not included here — those are platform vectors.

Built by `python -m v7.vms --root . --tables` (from `skills/lesson-spec/scripts`), judged by `check_spec`.

## Who executes and the wire

As with the platform package `common/family-read`: the table `NN.tsv` is executed by the lesson that owns its families (the column `owner`
of the VMS catalog) — `01.tsv` by the implementation of `cam`, `02.tsv` — `rec`, `03.tsv` — `live`, `04.tsv` — `det`, `05.tsv` — `detjob`,
`06.tsv` — `detedge`, `07.tsv` — `auto`; no table — the lesson has no families. The package is `VMS/common/family-read` (the path in
the export without `vectors/`), the single vector package command of the common platform acceptance README: the implementation profile declares
`vectors` → `VMS/common/family-read` with its own command with `{input}`. The input — `cells` `family`, `key`, `kind`, `place`, `mode`,
`who`, `text` as the cell string (no expectations, `case`, `note` in the input). The answer is JSON `{"verdict", "paths", "outcome"}`, the comparison
is as on the platform: strictly the verdict, the set of paths and the outcome for each role of `who`. The implementation judges the row by the platform family
and the value in each instance of the place `place` by the VMS schema (the column `schema` of the VMS catalog); the outcomes — per `outcomes.tsv`
of the VMS family. No `vectors` entry at the table owner — the target is `blocked`.
