# Common to all VMS lessons

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

```text
lessons.tsv        the lesson map: number (address V/NN), directory, title, subsystem (manifest name or «-»), status
data/catalog.tsv   the VMS data catalog: the subsystem keys — owner, participants, readers (the form of the platform catalog)
id-map.tsv         ids of the former norms М10B, М12A, М12B → V/NN[.K]-MM (the form of the platform id-map)
acceptance/        the common stand and directives of the VMS acceptances (on top of the common platform acceptance README)
inventory.md       the inventory: chapters М10B, М12A, М12B → the lessons VMS/ and the platform, names with «vms», vmsjobs, domain:, platform gaps
```

The tables are read by `check_spec` (ADR-0090 addendum (1), «Условия старта»). At the start the catalog and the id-map are empty: they are filled by the inventory
and by the translation of the lessons by «Спецификация VMS». The inventory (`inventory.md`, ADR-0090 addendum (4)) does not read the tables and is checked by «Архитектор».
