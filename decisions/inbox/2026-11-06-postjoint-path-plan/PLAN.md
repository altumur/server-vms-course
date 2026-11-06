# Post-joint path and ownership plan — READONLY

This is an input plan, not an adopted source/CODE candidate. No files were moved, copied into a new canon, edited in the course, or executed. Source freeze `63811ddc9957251b9c6ac3d60777c0c9dbe94077` remains intact. Policy was read at published main `e587819a6672efe78b5e6115383076b6bba6710c`: ADR-0083 (115)–(117), ADR-0121 (10), plus the coordinator's explicit scope. The next source branch must start from the **published current joint**, including 638, its readers, completion and operator work. It must not copy the older policy-main testdata instead of 638's accepted English bytes.

## Exact inputs and counts

- `move-roster.tsv` / `.json`: 149 source-file identities, target paths, Git modes, lengths, SHA-256 and owners. These pin the input bytes; they do not claim that future target files already exist or that a future Console translation is byte-identical.
- `moved-document-all-links.json`: every relative Markdown link in the four moving documents, including targets which do not themselves move. Retargeting only links *to* moved files would leave the moved Console document's P/06–P/10 links broken. `Source-witness-144.json` pins all old Source data files, including the three retired debt files that do not become canonical input.
- `markdown-link-map.json`: 363 mapped Markdown link occurrences across the course. **Platform: 195 occurrences in 179 files**, the exact counterpart of the approximate 180-file scope. VMS: 152 occurrences in 150 files (75 English and 75 Russian normative-word links, plus a Console contract link in each language). Root/control/history links are separately classified.
- `references.json` / `.tsv`, `reference-files.json`: conservative literal/relative-name search, with history, frozen witnesses, active source, mirrors, judges, generators and runner separated. Bare `testsub2.subsystem.yaml` is not automatically a file reference.
- `python-reader-sites.json`: 167 conservative AST call candidates in matched scopes. This includes fixture builders and generic `copy()` calls; it is **not** a count of 167 independent runtime readers. Actual binding contexts and their owners are listed below.
- `console-loaders.json`: **54 file-load sites in 44 JS test/helper files**. The module implementation itself was hash-only, not inspected or executed.
- `machine-source-cells.json`: 10 conservative matching TSV rows, of which **8 require a path change** and 2 are not relocation references (details below).
- Source verdict corpus: **138 files = 138 unique TSV rows**, 19 `ok`, 119 `refused`; filename/row sets are equal. Table SHA-256 is `1b7e2a4c957c89c7df8a579c29301133bbd153281a90c089c03cb1cefdcdcd3a`. This is data/roster proof, not loader execution and not a replacement for the current 947-case corpus or canonical 220.

The verdict TSV is **headerless**, with comment lines and two positional cells `case/verdict`. A reader must not consume its first case as a header. There is no new cell-json marker or protocol grammar in this relocation.

## Source moves and copies

| Current location | Proposed canonical location | Operation / owner |
|---|---|---|
| `NORMATIVE-TERMS.md` | `Platform/common/NORMATIVE-TERMS.md` | Spec moves source with history; rewrite consumers; no root alias |
| `ru/NORMATIVE-TERMS.md` | `Platform/common/ru/NORMATIVE-TERMS.md` | Move paired human mirror, with derived-header/link check |
| `CONSOLE-MODULE.md` | `Platform/07-console-module/CONSOLE-MODULE.md` | Spec moves live public description and maps history split |
| `ru/CONSOLE-MODULE.md` | `Platform/07-console-module/ru/CONSOLE-MODULE.md` | Paired mirror; no second live root contract |
| `Source/tests/testdata/testsub.subsystem.yaml` | `Platform/common/data/testsub/testsub.subsystem.yaml` | Initial raw copy as new canon; old Source witness stays immutable |
| `Source/tests/testdata/testsub2.subsystem.yaml` | `Platform/common/data/testsub/testsub2.subsystem.yaml` | Same; only these **two** root testsub YAML files exist |
| `Source/tests/testdata/spec_verdicts/*.subsystem.yaml` | `Platform/02-installer/acceptance/1/spec_verdicts/<same-name>.subsystem.yaml` | 138 initial raw copies; old Source witnesses stay immutable |
| `Source/tests/testdata/spec_verdicts.tsv` | `Platform/02-installer/acceptance/1/spec_verdicts/spec_verdicts.tsv` | Table and cases share the one new directory; do not accidentally append a second `spec_verdicts/` in readers |
| `Source/w2cplatform/console.{js,css,html}` | `Platform/07-console-module/module/console.{js,css,html}` | **Console** authors new English canonical bytes; old Source assets never change |
| `Platform/06-console/data/localization.tsv` | `Platform/07-console-module/data/localization.tsv` | **Console** moves the one table; no duplicate canon; review103 changes path exception |

Source input manifest SHA-256: `testsub` = `fc3bf70585646b078a8812edd0c92cd5c7d0c2e364b689273c5fd229aed7355b`; `testsub2` = `e4bfd9e0035dba5839018625bba20f7214176004fc2d0cb4f8d640015d915dbb`. Localization: 519 rows, columns `key/en/ru`, SHA-256 `a5b3c4b9c1af6cfe40a72c80b58d2348a9e9517d7c36c0b6ad8a91bc807850e9`. Final hashes must be rechecked against the published joint and Console author's exact branch.

### Contract-note history proposal

Pin the full old English and Russian note bytes before splitting them. Proposed archive names: `decisions/history/platform/console-module-note.md` and `decisions/history/platform/ru/console-module-note.md`. The archive is history, not a second live contract.

The unambiguous historical sections are §11 “Order of work” and §12 “Decisions on the questions”, plus dated provenance. A split cannot simply delete §12's current language clause: English default, explicit Russian, qualified W keys and equal parameters already belong to live §3 `lang` and the P/07/P/06 norms and must remain there. Keep §1–10a's public-surface subjects, retarget relative links from the new home, and map any historical prologue removal separately. Do not rewrite accepted historical bytes. Current P/07 norms prevail over the descriptive note; no new ABI or behaviour is introduced by this split.

## Actual reader/binding groups

| Owner | Files / binding | Required post-joint adoption |
|---|---|---|
| Spec source, spec103 source | 179 Platform Markdown files and mirrors, exact URL map | Retarget resolved paths and anchors rather than blanket string substitution. A moved document's own relative links also change. Re-run mirror/link checks on the final pair |
| spec103 / coord joint | `Platform/common/contracts/{accept,password-hash}.md` and their `ru/` pairs | All four contain a normative-word link. Reserved B owns these files; Spec must not race it. Route these four narrow link changes through spec103 or root composition |
| VMS owner / Architect | 150 VMS files, 152 links | VMS remains paused. Moving the root canon without changing these links would break the source checker. Obtain a separately assigned mechanical-link slice from that owner/Architect, or compose at its permitted time; do not retain a root alias |
| review103 | `check_spec.py`: `manifest_schema`, `form_source`, `form_v7` Source/testdata globs; canonical tests; `v7/test_spec.py` source-tree fixture and manifest list | Select exactly the two new common manifests. Missing new roots/rosters must be errors, not an empty glob silently lowering checked counts. Source witness manifests are no longer canonical validation input |
| review103 | Corpus layout, source/local Markdown links, `en_mirror` roots/completion, Cyrillic scope/localization exception and marker validation | Admit/bind the new P02 subdirectory deliberately. Preserve 947/220 and supplemental numeric-nine counts; the new 138-case legacy bundle must not silently replace them. Move the one locale exception to P07; no added exception or Cyrillic reset |
| Generators | `gen_box.py` provenance; `wire_draft.py` draft file maps; `kit/build_kit.py:build_from_export`; `test_wire.py`, `test_consumer_packages.py`, `test_copy_storage.py` | Published vector file maps are the primary input. Remove Source-only stage/archive prerequisites and cover the two new canonical manifests under Platform. Do not make missing canonical data an optional skipped copy. Draft producers and test setup remain separate from published wire forms. Actual related output/provenance regeneration is by their owners |
| Runner | `specs.py:root/testdata/subsystem`, `all.py:runs`, `body_vectors.py:fixture` | Current published `root()` requires Source/testdata and will reject a Platform/VMS-only export. Make the active subsystem root explicit and require its two files. Do not route the verdict corpus or legacy acceptance through that same new root, and do not add old/new layout fallback |
| Runner | `c_targets.py` fixture lists and TESTSUB2; `c_vector_packages.py` package fixture declarations; `c_installer.py:put_case`, `c_installer_data.py:sources`, `c_store.py:_main`, `stand.py:put_specs`, and dependent fixture/capture evidence | Update file identities, stand `specdir`, seed path, allowed worker-name environment lookup and evidence source paths together. Manifest row YAML/hash/rev are still derived from the same raw bytes. Keep current 14-file P06 asset stand mapping; no duplicate asset tree under the new manifest directory |
| Runner | `runner/vms-jsdom/panel.cjs` module reads | It reads old Source assets even though the subject is a VMS page. Coordinate its module asset binding with Console's exact new three-byte input and VMS's paused witness-page scope; no product/native execution claim |
| Spec tests | 44 `Source/tests/console` files / 54 reads, including `boot.js`, platform/holder page fixtures, optional `MODULE_FILE`, and shell wrappers | Retarget module/page asset reads to the new P07 canon. Keep arbitrary-file overrides only as existing owned test plumbing; no silent fallback to Source. Preserve hostile Unicode payload values. Classify VMS shell witness tests separately rather than turning their failures into module PASS |
| Frozen Source witness | `tests/frozen_data.py` (historical ref `a0bd9e53`), `test_spec_verdicts.py`, `test_spec_parity.py`, conftest/boundary tests, Python console serving tests, Source/deploy/vms references | These explain old witness operation, not the new canonical root. Leave Source implementation/data immutable. Python `test_console_page.py` imports the frozen server's MODULE/PAGE constants: changing its comparison path alone would not prove the new module is served. Canonical publication proof belongs to the new source/runner/test slice, not a claim that the old server changed |
| coord103 | Export operator, runner preparation/passports and source pin propagation | New export contains Platform/VMS only. Exact current CT operator source is still requested; the local Mac exporter is historical and is not attested as the candidate |

### Eight machine-data rows and two non-changes

1. `Platform/02-installer/vectors/canonical/cases.tsv`, physical 223/224, column `input`: change the two root paths. Keep the 220 case roster/order/expectations and each manifest's actual bytes.
2. `Platform/common/vectors/wire.tsv`, physical 76/77, column `files`: retarget the three `base: root` manifest mappings; keep package/table/variant/CEL/input/expect/native/comparison unchanged. Stage basenames remain `testsub*.subsystem.yaml`.
3. `Platform/06-console/acceptance/5/scenarios.tsv`, physical 9/10/11, column `expect`: the three `@file` references move to the new Console canon. The supplied new JS/CSS/HTML bytes intentionally change; those are new canonical expectations, not byte-preserving relocation of the old module.
4. `Platform/10-domain-console/acceptance/scenarios.tsv`, physical 16, column `expect`: same JS binding change, coordinated with spec103.

Do **not** change P06 physical 240, `GET /testsub2/testsub2.subsystem.yaml → 404`: this is an intentionally unserved HTTP filename. Do **not** rewrite the basename in common system scenario physical 79: it describes an installed `MANIFEST_DIR` file, not a Source fixture path. All eight actual path-binding rows are unmarked columns at source638; the existing 1855-cell/16-table lexical proof is not rewritten for them. Recheck this on the eventual joint. Raw table identity changes are recorded separately from identical referenced manifest bytes or Console's intentionally new bytes.

## Markers and export contract

The operator writes **two** files: `Platform/COURSE_COMMIT` and `VMS/COURSE_COMMIT`, each the same full 40-hex course commit plus LF. No root COURSE_COMMIT, Source tree, exporter script, generated exporter README or old debt files in the new export. These are operator-generated markers, not source files Spec should prewrite.

review103 checks both markers, exact equality and full-hash form; runner/pins/passports use the new explicit layout. A marker-only migration must not keep a root alias or accept one missing marker. VMS content translation remains its owner's task; creating the same export pin marker does not declare VMS English or READY.

No executable direct `COURSE_COMMIT` reader was found in published runner94b by this inventory; its mentions are documentation/history. `prepare.py` identifies the **export Git commit**, not the course-source hash inside a marker. Do not replace SPEC_VERSION/export identity with the course marker value. Unpublished CT passports/operator code still require their exact input before code assignment.

## Separate semantic work after the joint

- C6 is approved **only** as optional Boolean `FieldView.hidden`, no default, no required-list/additionalProperties change; P06.5 N1.2 links its schema. It belongs in a **P6 branch after the joint**, with its own semantic map. No new ConsoleRefusal field/class or ABI. P07 N5 records open `v1showsHidden` debt next to P07-07/08; old frozen JS is never credited with the rule. Console authors/final tests close new canonical byte behaviour separately.
- Locale move and three module byte files are Console-owned. The language-selection norm is specified with that author: English default, explicit `lang: "ru"`, existing W keys/parameters. Do not invent a runtime TSV-fetch door or a second table.
- ADR-0129 post-P6 constants are a **later** slice after the current joint. Closed rows and schema pointers require the separate agreed mapping. No parallel edits to reserved B common contracts; no silent FOLDERS_*_MAX choice.

## Staging and acceptance of the future slice

1. Root publishes current joint; freeze its exact source, operator and Console inputs. Rebaseline every identity in the roster; old Source remains immutable after that point.
2. New isolated source branch; keep mechanical path/copy/history moves separate from C6 and later constants. Retarget all real readers through their assigned owners, including paused/shared links; no aliases.
3. For byte copies: compare every mode/length/SHA and complete case/row roster, including BOM, invalid UTF-8, NUL, tabs, line endings, depth and duplicate-key witnesses. Never decode/reserialize YAML while copying. For doc splits/link rewrites and new Console bytes, provide an explicit non-identity delta instead of claiming whole-file equality.
4. Require positive new-root-only preflight and negative missing-file/old-root-only/wrong-marker checks. Keep all consumer rosters and case order before/after. Preserve existing cell-json one-decode, physical/raw SHA and payload proof; no new decoder.
5. New judges/reviews run **only review103 on CT103**, per ADR-0127 (7). coord103 composes and runs one full source/normgen/KIT Gate and export. No Mac judge/reviewer or product synchronization dependency.

No source/CODE changes or execution were made for this plan. Published runner94b and course638 were read through Git; unpublished CT operator/private export state was not attested. These limitations must remain visible when the plan is handed off.
