# Change 0125-forms-standard-schemas

change: 0125-forms-standard-schemas rev 1 · lessons P/01, Platform/common · author spec103 · state review

Publication parent `edf82b0bfa78762937791d77e332ba2b3e6124e2`. Task OBSH.39.1 (parent OBSH.39), ADR-0125 addendum (12) item 2; interface agreed with coord103-tools and confirmed by the Architect. First group of the standard form checks: JSON Schema (Draft 2020-12) sidecars `stages.tsv.schema.json`, `stages.kit.tsv.schema.json` (structure only), `code-rules.tsv.schema.json` next to the forms of P/01 and `code-rules.tsv.schema.json` next to the dictionary `Platform/common/acceptance/forms/code-rules.tsv`, validating the table as `{"columns": [header], "rows": [[raw cells]]}`; and `Platform/common/forms.keys.sql`, DDL only, with the six tables `stage`, `code_kind`, `code_rule`, `norm_item`, `stage_norm`, `required_norm_item` (names and projections as proposed to coord103-tools and confirmed). Both filters list the five files outside the model and judge input. The old checks stay until coord103-tools proves each replacement by mutants; the map below says which rule each constraint states and which rules stay. No requirement unit changes; no form, grammar or meaning changes.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/01-store/forms/code-rules.tsv.schema.json` | ADDED | - | e5f4fbddcf155b6c2a3846427f702667c58f3a4a | 68f4d6ebf88cef2dda503f262f670b520ba29d427217b117639c2b542b07f986 |
| `Platform/01-store/forms/stages.kit.tsv.schema.json` | ADDED | - | d3ab7d2a80ea6c277d590c7163c04a19c0e79c2e | 2f3c94318d231b7e1307e532472d1371701e9cc7e6215f9db27cac71662c6723 |
| `Platform/01-store/forms/stages.tsv.schema.json` | ADDED | - | e64fae330cef09ba164c565815b68a2c54d0a2d7 | 7cbc1352b10627988ca004f8784d527b4248afca10f08b514b547012d167d9d8 |
| `Platform/common/acceptance/forms/code-rules.tsv.schema.json` | ADDED | - | 0c87e2ea8a77ad4b3b71049f23d53b37c654d7d1 | e489e46e4ffae5b5c08edac01446c7530a1199db909ecb5970b0d485429600bb |
| `Platform/common/acceptance/judge-input-filter.json` | MODIFIED | fb005cbef5a238f1635f0d82ef87fc0fbe6fa6f4 | f231cec960ff054d98c0bd3e78d3567d88b77e4f | 8181cdeddf51e125f9b0d719c11a71cc735680c160ac0c527cd3090dc2d966d4 |
| `Platform/common/export-model-filter.json` | MODIFIED | 4159ccd67853bf5d3c678dc718c0e7ef46e7739f | 0675151fec34f79549aa0cc06ff9c7185205ba58 | 38232f4c13d7fe6eaf1d9005883ae7792ad9b5a829aba8754a129cf4614471b2 |
| `Platform/common/forms.keys.sql` | ADDED | - | 432bdc3a4a2ea1e1170ac4e9fba644bf81026077 | f961bff221fb0539a3299a439497496b375b0443d6419126d5129045ce709045 |

## Raw map: rule → standard constraint

| Form | Rule (source) | Constraint | Old check |
|---|---|---|---|
| `stages.tsv` P/01 | columns n, stage, goal, norms, gate, weight, depends, when in this order; no kit/parts (header; `check_stage_parts`) | schema `columns` const; row `prefixItems`, `items: false`, `minItems` 8 | `check_stage_parts` columns/width |
| `stages.tsv` | n is a positive integer (`check_stage_parts`) | schema pattern `^[1-9][0-9]*$`; SQL `stage.n` CHECK `n >= 1`, UNIQUE (`lesson`, `n`) | physical order 1, 2, … stays |
| `stages.tsv` | weight 1–5 (header) | schema enum `1`…`5` | none before |
| `stages.tsv` | depends: `-` or n of former stages, comma-separated (header) | schema pattern of the list | «former» stays in `check_stage_parts` |
| `stages.tsv` | gate: checks separated by `;` of accept:, seams:, vectors:, build, code:*; no tests: in the public form (header; `GATE`, `check_stage_parts`) | schema pattern of the public grammar | duplicates, chapter owner, scenario names stay in `gate_errors` |
| `stages.tsv` | when: CEL (header) | `contentMediaType` annotation only | existing CEL guard |
| `stages.tsv` | stage names a stage once (FK target of code rows and norms) | SQL PK (`lesson`, `stage`) | — |
| `stages.tsv` norms | each checklist item at exactly one stage; an element that is no item of the lesson is an error (header; `stage_norms`) | SQL `stage_norm` PK (two stages), FK → `norm_item` (foreign), `required_norm_item` → `stage_norm` deferred FK (no stage, required lessons) | `stage_norms` stays until mutant cover; owner and non-empty roster guards stay |
| `stages.kit.tsv` P/01 | columns with kit, parts; kit grammar of gates (tests:…[:seams], accept:, vectors:, build); kit/parts `-` or parts of kit B (header) | schema only; not loaded into SQL | part named twice stays in `check_stage_parts` |
| `code-rules.tsv` P/01 | columns id, kind, name, args, stage, norm (dictionary header; `code_stage_errors`) | schema `columns` const and width | — |
| `code-rules.tsv` P/01 | id identifies the row; kind of the dictionary; stage of stages.tsv (dictionary header) | SQL `code_rule` PK (`lesson`, `id`), FK `kind` → `code_kind`, FK (`lesson`, `stage`) → `stage` | `code_stage_errors` (stage) stays until mutant cover |
| `code-rules.tsv` P/01 | the stage or a later one holds code:* (stages header) | — (cross-row) | `code_stage_errors` stays |
| `code-rules.tsv` P/01 | args: one JSON object with the fields of the kind; one name type per name (dictionary header) | `contentMediaType` annotation only | the cycle interpreter and existing guards |
| dictionary `code-rules.tsv` | columns kind, name, args, check; kind once; name is a name type (header) | schema `columns` const, `name` enum; SQL `code_kind` PK, CHECK `name_type` | — |

Verified on the publication tree: the four sidecars hold on the current forms (0 errors) and reject 25 named structural mutants; the DDL loads the current P/01 projections (11 stages, 7 kinds, 24 code rows, 55 items, 55 placements) and rejects 15 named key mutants.
