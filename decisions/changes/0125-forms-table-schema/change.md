# Change 0125-forms-table-schema

change: 0125-forms-table-schema rev 1 · lessons P/01, Platform/common · author spec103 · state review

Publication parent `ebb8e38543f6656865eed5942d41d68b5ae0c2cd`. Task OBSH.39.1 (parent OBSH.39), ADR-0125 addenda (12) item 2 and (13) (Frictionless Table Schema, no SQLite); interface agreed with coord103-tools. The owner's word of ADR-0125 addendum (13) replaces the means of `0125-forms-standard-schemas`: the four sidecars `stages.tsv.schema.json`, `stages.kit.tsv.schema.json` (structure only), `code-rules.tsv.schema.json` of P/01 and `code-rules.tsv.schema.json` of the dictionary `Platform/common/acceptance/forms/code-rules.tsv` stay on their paths and are now Frictionless Table Schema v1 (every field a raw string; constraints required, enum, pattern; primaryKey; foreignKeys). The new Data Package `Platform/forms.datapackage.json` names the resources `stages_p01`, `stages_kit_p01`, `code_rules_p01`, `code_kinds` (path from `Platform/`, format tsv, encoding utf-8, dialect commentChar `#`, TAB, headerRows = the physical line of the header), so that the foreign keys `code_rules_p01.stage` → `stages_p01.stage` and `code_rules_p01.kind` → `code_kinds.kind` resolve. `Platform/common/forms.keys.sql` (SQLite) is removed from Source and from both filters; its history stays in `0125-forms-standard-schemas`. The package and the sidecars stay outside the model and judge input. No form, grammar or meaning changes; the old checks stay. No requirement unit changes; no form, grammar or meaning changes.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/forms/code-rules.tsv.schema.json` | MODIFIED | e5f4fbddcf155b6c2a3846427f702667c58f3a4a | fbfedf1bfad2a49a5496638a49b73db61c287148 | f1f1ddcb120e0905a60aaac7893a57fdd3a39be8f778cc4d6c2003917f4eab7d |
| `Platform/01-store/forms/stages.kit.tsv.schema.json` | MODIFIED | d3ab7d2a80ea6c277d590c7163c04a19c0e79c2e | 4d78b5beea383dbc0c56257257810b6f93c5791b | a60d553ac05dfc59471e3f80e5731cb5b7baed1ef67ad8b2ab09ca8695a45bc9 |
| `Platform/01-store/forms/stages.tsv.schema.json` | MODIFIED | e64fae330cef09ba164c565815b68a2c54d0a2d7 | 5267ca408777accc88f3465ffc346947b6b264ca | 0f495f913f7f077ae1b0422e5a3b7c2d6c0ff02c7b98a029323764f31b996777 |
| `Platform/common/acceptance/forms/code-rules.tsv.schema.json` | MODIFIED | 0c87e2ea8a77ad4b3b71049f23d53b37c654d7d1 | 0aa5760d29d6ae858c9b8dd50f197ce44655b08f | f7ae03a3c9dff51a9a32c6ec9205f2c939c49b6d4190967bc374c604f6793b9f |
| `Platform/common/acceptance/judge-input-filter.json` | MODIFIED | f231cec960ff054d98c0bd3e78d3567d88b77e4f | ca7a9563ff64365e0a2c4f3e03ba846e1fc9a438 | 8093742f9dbadc007dbc45261196ccf0f6e53d230005a0bbede30badd3f4e768 |
| `Platform/common/export-model-filter.json` | MODIFIED | 0675151fec34f79549aa0cc06ff9c7185205ba58 | 27efe802ef20d3b2284bfdbb190d42b85c596e2d | 1e72cbe7bf033e4086f5937d77fde3c16b7317f223a73b91ef911518adb8ac2a |
| `Platform/common/forms.keys.sql` | DELETED | 432bdc3a4a2ea1e1170ac4e9fba644bf81026077 | - | - |
| `Platform/forms.datapackage.json` | ADDED | - | 6957da50cc96aad1094dd07a870ce92c3f7ea539 | d56f216bf04eed40d4a00bda8af9f78d9a94d2c05ef26b8ab4784bee573548e3 |

## Raw map: rule → Table Schema constraint

| Form (resource) | Rule (source) | Constraint | Old check |
|---|---|---|---|
| `stages.tsv` (`stages_p01`) | columns n, stage, goal, norms, gate, weight, depends, when in this order (header; `check_stage_parts`) | fields in order: a label or count mismatch is `incorrect-label`/`extra-label`/`missing-label`; a row of another width is `extra-cell`/`missing-cell` | `check_stage_parts` columns/width |
| `stages.tsv` | the header is the first physical line not beginning with # (transport) | dialect `headerRows` = that line; a stale number fails, no inference | Tools guard: `headerRows` equals the first non-# line |
| `stages.tsv` | n is a positive integer (`check_stage_parts`) | pattern `[1-9][0-9]*`, required | physical order 1, 2, … stays |
| `stages.tsv` | weight 1–5; depends `-` or n of former stages, comma-separated (header) | enum `1`…`5`; pattern of the list; required | «former» stays |
| `stages.tsv` | gate: checks separated by `;` of accept:, seams:, vectors:, build, code:*; no tests: (header; `GATE`) | pattern of the public grammar, required | duplicates, chapter owner, scenario names stay in `gate_errors` |
| `stages.tsv` | stage names one stage (target of code rows) | required; primaryKey `stage` | — |
| `stages.tsv` | when: CEL, empty — always applicable (header) | string, not required (empty is lawful) | existing CEL guard |
| `stages.tsv` norms | each checklist item at exactly one stage (header; `stage_norms`) | not expressed: items live in Markdown and norms is a list cell | `stage_norms` stays whole |
| `stages.kit.tsv` (`stages_kit_p01`) | kit grammar of gates (tests:…[:seams], accept:, vectors:, build); kit and parts `-` or parts of kit B (header) | structure only: fields, patterns, required; no key | a part named twice stays |
| `code-rules.tsv` (`code_rules_p01`) | columns id, kind, name, args, stage, norm (dictionary header) | fields in order | — |
| `code-rules.tsv` | id identifies the row; kind of the dictionary; stage of stages.tsv (dictionary header) | primaryKey `id`; foreignKeys `kind` → `code_kinds.kind`, `stage` → `stages_p01.stage` | `code_stage_errors` (stage) stays until mutant cover |
| `code-rules.tsv` | the stage or a later one holds code:* (stages header) | not expressed (cross-row) | `code_stage_errors` stays |
| `code-rules.tsv` | args: one JSON object with the fields of the kind; one name type per name (dictionary header) | string, required; JSON not checked by the schema | the cycle interpreter and existing guards on the raw text |
| dictionary `code-rules.tsv` (`code_kinds`) | columns kind, name, args, check; kind once; name is a name type (header) | fields in order; primaryKey `kind`; enum of `name` | — |

Default `missingValues` (`""`) only makes an empty required cell an error; the old JSON, CEL and owner guards keep reading the raw text. Verified on the publication tree with frictionless 5.18.1: the package holds on the current forms (11, 11, 24, 7 rows); 29 named mutants fail (header order and width, header line moved, row width, n, weight, depends, gate grammar, duplicate and empty stage, empty gate, kit grammar and parts, empty id, unknown stage and kind, duplicate id, dictionary name type and duplicate kind); 3 positive controls hold (empty when, empty goal, empty norm of a code row).
