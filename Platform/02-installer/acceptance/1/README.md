# Acceptance P/02.1 — the verdicts of the manifest loader

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The scenarios of [the norms of chapter 2.1](../../spec/02.1-installer.norms.md) N5; the stand — [the common acceptance README](../../../common/acceptance/README.md). The door of the chapter is the loader itself: a file is given alone, as the manifest of a subsystem, and the answer is one of two.

## Profile interface

Use the `02-installer` [profile format](../../../common/acceptance/PROFILE.md). `stand.load` loads the single file `{file}` through the normal loader: success exits zero; a refusal names the source file and follows this chapter's outcome rules. The optional `adapters.load` exposes that same loader as the persistent path/JSON-line transport defined by the common contract, without template substitutions. `keys.path_style` declares `json` or `dotted` for transporting the loader's own diagnostic paths; diagnostic authority remains the hint rules below. Neither adapter supplies a case-based answer or an alternate loader.

## verdicts.tsv, classes.tsv, diagnostics.tsv

The three tables are run by the engine word `verdicts` in the form «[Loader verdicts](../../../common/acceptance/command-tables.md#loader-verdicts)» of the common acceptance README: the call, what counts as a manifest and as a refusal that names the file, the strict verdict, the class `refused:<class>` and the hint of the diagnostics are defined there. The interface of the call is `stand.load` or `adapters.load` above. This README keeps only the data of the chapter.

The rules by which the verdicts are set are the norms of the chapter N1 (text, document, field, references) and N4; they are not here, so that there are not two versions of one norm.

**`classes.tsv`** (judge-only: the class of each case; it checks P/02.1-R213 and P/02.1-R155).** The class is the layer of the N4 refusal: `text`, `form`, `relations`, `catalogue`.

**`diagnostics.tsv`** (judge-only: the hints of each case; they illustrate P/02.1-R047, P/02.1-R201, P/02.1-R205, P/02.1-R206).** The paths and lines of a loader refusal are a hint, not a norm. A list index in a path is a JSON integer (`0`), a key name is a string (`"0"`): these are different segments (N4 «Diagnostics»). The paths of a row are written in the canonical order — by the bytes of the JSON Pointer path (RFC 6901), the line numbers ascending. An empty `lines` means that the case does not look for line numbers; it does not forbid them in the refusal. In `unknown_multiple` the hint names all three paths, not only the first typo found; in `dup_top_key_name` it names line 36, the second declaration of `name`. The requirement to name the source file stays — it is a norm: `unknown_depth4.subsystem.yaml: error` passes the verdict, and the report notes the missing path `unit.fields.name.requried`. For the other cases the implementation SHOULD give the path and the line per N4 of the norms — as a hint.

## No installation sample

The corpus is not run through `manifest put`. The form «Installation sequences» installs only the files `puts/` of its own directory, and loading and installation are judged separately: the verdicts of this directory judge the loader; the installation, the catalogue checks and a refused installation are the rows of [`../3/puts.tsv`](../3/puts.tsv) and the seam `s1-put-invalid-source` of [`../4/seams.tsv`](../4/seams.tsv) (judge-only: the installation rows and the seam; they check P/02.1-R061, P/02.1-R158, P/02.1-R159, P/02.1-R161, P/02.1-R178, P/02.3-R004, P/02.3-R005, P/02.3-R007, P/02.3-R009, P/02.3-R012, P/02.3-R014, P/02.3-R016, P/02.3-R081, P/02.3-R102 to P/02.3-R105, P/02.3-R107, P/02.3-R110, P/02.3-R114, P/02.3-R119, P/02.3-R123, P/02.3-R171, P/02.3-R173). The SHOULD sample (all `ok` cases, one refusal per class) is therefore not part of the judgement. Six accepted files of the corpus name `testsub` in catalogue relations (`bound_to_string`, `blob_required_false`, `secrets_reader_domainconsole`, `m49_table_shelf_log_ok`, `c6_secrets_reads_with_slash_ok`, `c3_near_by_ok`); loaded alone they are `ok`, in a catalogue without `testsub` they are `refused:catalogue`.

## puts.tsv

The manifest installation `manifest put` (`puts.tsv`, `puts/`; judge-only: the installation rows of chapter 2.3, they check P/02.1-R061, P/02.1-R158, P/02.1-R159, P/02.1-R161 and P/02.1-R178) — [the acceptance of chapter 2.3](../3/README.md).

## Additional check of string field names

In a minimal correct manifest, separately for `unit.fields` and `tables.<t>.fields`, the keys 1, true, null and 1.5 (without quotes) give `refused:text` per N1.1 `refused`: a plain key that the table `scalars` reads not as a string is a refusal of the text layer everywhere, including in the value keys of `json` and `display.options` (`display_options_bool_plain_key`); the path and the line are a hint per N4. The same names in quotes are strings and pass. The pair 1/"1" is refused as a whole (`text`), it is not converted into one string with the loss of a field. These inputs are the cases profile_unit_key_*/profile_table_key_* of verdicts.tsv and are checked by the same regular loader as the other cases; reading the types of the YAML nodes does not by itself prove its conformance.

The cases profile_* cover the positive neighbouring values and the restrictions P/02.1-R049, P/02.1-R070, P/02.1-R072, P/02.1-R083, P/02.1-R074,
and also the types of field keys and the membership of worker.writes (P/02.1-R024, P/02.1-R076, P/02.1-R086, P/02.5-R051).
The prepared verdicts are not a result of running an implementation: the author checked the data and the stated
canon, the regular execution loader was not run here.

## Additional inputs

In all 48 profile_* the common lease background writes the string off in quotes.
A refusal on an extraneous false
does not count as a check of the target restriction. The r37_* cover P/02.1-R136, P/02.1-R083, P/02.1-R049, P/02.1-R088.
The current corpus: 951 files, 203 ok/748 refused (4 cases `r32_secrets_readers_*` — the keys `probe/vault*`, `probe/va*ult/`, `!probe/vault`, `delete:probe/vault` of `secrets.readers`: a refusal by the form of P/02.1 N1.2, the class `form`; 10 cases `a119_writes_via_*` — the word `writes_via` of the unit and of a table: a list of subsystem names without repeats, its own name is admissible, for a table with `service: true` — a refusal; 2 cases `a119_calls_verify_*` — the entry `domain/verify` in `calls` ok, `GET domain/verify` — a refusal; 3 cases `a116_calls_manifest_source_*` — the entry `GET manifest/<s>/source` in `calls`; 46 cases `a115_*` — the keys: `rank` at `door.routes` (with `role`, `domain` — a refusal), `display.langs`, `display.tables` (relation № 159), labels `{key, text}`, `hidden`, `items.ref`, `ref_label`, `events.kinds`, a dot in the name of a unit field (`a115_unit_field_quoted_dot`, the key `'1.5'`), relations № 67–70 on `<t>.<field>` and № 158; 16 cases `a95_*` — `door.pass.operations`, `calls` with folders, operations and domain doors; 7 cases `a98_sub_*`: reserved subsystem names; 25 cases `a96_*`: forbidden names, `display.tree.folders`; 40 cases `a94_pass_*`, `c8_ref127_*`…`c8_ref131_*` — the kind of the second `door.pass`; 3 cases `k38_sub_changes`, `m49_table_changes`, `rows_changes` — the first segment of the feed; 2 cases `c8_ref125_*`, `c8_ref126_*` — a term at the table of holds and places; 3 cases `a94_unit_field_index`, `a94_table_field_*`: platform field names; 9 cases `a94_table_delete_after_*`: the term of table rows; 18 cases `a94_*`: `console.shell`, `console.files`; 6 cases `secrets_readers_*`, `worker_writes_*`; 43 of set «B» — `t*`, `f*`, `r*` under the comment of set B in `verdicts.tsv` (judge-only: the verdict table of the chapter; set B checks P/02.1-R008, P/02.1-R012, P/02.1-R013, P/02.1-R018, P/02.1-R020, P/02.1-R024, P/02.1-R026, P/02.1-R027, P/02.1-R028, P/02.1-R030, P/02.1-R033, P/02.1-R034, P/02.1-R036, P/02.1-R038, P/02.1-R041, P/02.1-R043, P/02.1-R047, P/02.1-R048 and P/02.1-R056): the rules of the fine check of layer 1, scalars by node style, the integer place, a full match of an expression, other forms and relations; it is appended to all files without `worker:`; 9 c2_metrics_*: count and from together, neither, from not heartbeat./status., agg outside the list, count at heartbeat, histogram without buckets, values not at label and with count, name starting with _ — value; c2_metrics_name_repeat — elements by the form from: status.phase, the subject is the former one; 2 name_free_*: the name `free-cam` — name, `free` — ok; 6 door_routes_domain_*: `{name}` — admission token, `{name, domain}` and `{name, role, domain}` — ok, `domain` empty, with a repeat, `person`, not by the kind grammar, not a list — value; 3 a91_affinity_exclusive_*; 6 door_routes_role_*: an element of `door.routes` is a name or `{name, role}`; 11 cases: `worker.exec` is mandatory and the grammar of `exec` — a91_exec_*, a91_worker_missing, a91_parts_exec_shell_char; the key is present in all other manifests of the corpus; 12 cases: 7 a91_* — `stop_timeout` of the worker and of a part at the boundaries, `shares.<share>.part`, an own share with `part` and without, 5 id_default_* — `{id}` in the default of a field; 28 a91_*, profile_unit_born, profile_unit_made, m49_table_state — the state of a unit, ends, worker.creates, worker.uses, shares, parts, the name state, the fields born and made; three cases of delete_after with fixed and about — ok; 3 a86/k38/m49 — the reserved name manifest: k38_sub_manifest and m49_table_manifest — refusals, a86_sub_manifest2 — an admissible neighbour; 3 door_routes_* — the segments of door.routes by the grammar name; 7 c9_*: «- -», a single «-» in a flow (and with spaces around it), «#» inside a word, a number class out of bounds under x-class, is/is_not with null, the one_of path by the rule list; 59 c8_ref* — strict coverage of the rows of `references.tsv` of the form source: row N is the only reason for the refusal of the case `c8_ref<N>_*`; rows 58, 61 hold with the condition «the table is declared» at references to a table field, row 84 is removed; 10 c8_*: the node rule on a form refusal below, the canonical order of paths, a number outside float in a json field, a field without type, a nested `{` in requests.key, enum under display.options, an integer of 4301 digits, «word# c»; 10 c7_*: a comment deeper than the key after a word, U+FEFF in the middle, folding, `]` of a continuation, a block list of scalars, the float boundary; refusals — a comment in a continuation line, a scalar below a bare `-` (text), underflow (value); 3 c6_*: `secrets.reads` with `/`, a flow key without a value `{unconfirmed_max:}` — value; 27 c5_*: on N1.1 and N1.2a; 29 c4_*) (16 m51_books_* — the form domain.books P/02.1 N1.2b; 3 of them — the grammar of key and to; 22 m57_tokens_* — the form domain.tokens P/02.1 N1.2b; 13 m59_names_*/m59_keys_* — the forms domain.names and domain.keys P/02.1 N1.2b; 10 m61_* — the form domain.shared, merge and domain.witness P/02.1 N1.2b); diagnostics — 51 rows of hints; classes.tsv — 236 rows: the class by the layer `text`, `form`, `relations`, the cases of set «B» included; puts.tsv — 23 installations — the acceptance of chapter 2.3.
Two additional refusals — r37_rows_cluster/r37_rows_worker; together
with profile_rows_ts the whole list cluster/worker/ts is covered, and profile_rows_records_ok
remains the positive control. These two files differ from profile_rows_ts only in rows.
The count of the corpus is also reconciled in N5 and in the implementation instructions; readiness requires the whole normative checklist.
The pairwise intersection of the catalogue is judged by installation into one store: see «Catalogue intersection» below.

## The error class

The common background is part of the data: `lease` is the quoted string `off` in every file of the background, and `true`/`false` do not stand for `off`/`on`; the verdicts of these files judge it with the regular loader. Single verdicts and the catalogue check are separate pieces of evidence: the catalogue check is «Catalogue intersection» below, including a catalogue of one manifest.

The value of `{name:int}` (P/02.1 N1.4, P/02.1-R088) is converted when a door builds a key from the body of a request, not when the manifest loads. The loader judges only the template: the cases `r37_requests_plain_*`, `r37_requests_int_*`, `r37_table_key_bool`, `r37_table_template_bool`, `r37_table_int_template`. The bounds of the conversion (binary64, modulus not greater than 2^53−1, a canonical decimal without an exponent; bool, null, a string or a non-finite number — 400) are not judged in this lesson: they are an outcome of the door that applies the template.

Two writes of one manifest by two installers are resolved by `cas` (P/02.3 N3); a conflict of two installers needs the store of another lesson and is not judged in this lesson.

## The full list of names and the catalogue check

19 k38_sub_* — refusals of the remaining reserved names. Together with
name_reserved_platform and r37_sub_where/r37_sub_metrics/r37_sub_healthz all 23 words
are checked; a96_sub_folders adds the twenty-fourth, `folders`; a98_sub_* — the seven names; r37_sub_where2, a86_sub_manifest2 and a96_sub_folders2 remain admissible neighbours. The background of the 19 files is kept
byte for byte, including lease off; only the top-level name changes.

The verdicts call `load`, not `load_catalogue`: one file is not a catalogue of one file. So a correct single parse of a manifest whose name equals its own rows or table is `ok` here; the refusal is the catalogue check of the installation.

Three r38_unit_* without unit/rows/id must be refused by mandatoriness with the path of the missing value; r38_unit_minimal has rows=things/id=numeric without fields and must load with an empty set of fields. A common catalogue is not required. The verdict check is the regular loader; the author's check of the YAML structure does not replace it.

## Catalogue intersection

The non-intersection of a manifest name with the families of the catalogue (P/02.1 N3 «load_catalogue», P/02.1-R178) is judged by the rows of [`../3/puts.tsv`](../3/puts.tsv) (judge-only: the installation rows of chapter 2.3): each installation loads the candidate in the full confirmed catalogue, and a refusal comes before the first write.

| Catalogue | Conflicting family | Refusal (`refused:catalogue`, code 2) | Positive control | Swapped order |
|---|---|---|---|---|
| A=B: one manifest `name=b` | `unit.rows=b` | `self_rows` | `self_rows_renamed` | — |
| A=B: `name=b` | map `tables` contains `b` | `self_table` | `self_table_renamed` | — |
| A=B: `name=b` | list `tables=[b]` | `self_table_list` | `list_tables_ok` | — |
| A≠B: `name=a` and `name=b` | `rows` of `a` equals `b` | `other_rows` | `other_rows_renamed` | `other_rows_swap` |
| A≠B: `name=a` and `name=b` | map `tables` of `a` contains `b` | `other_table` | `other_table_renamed` | `other_table_swap` |
| A≠B: `name=a` and `name=b` | list `tables` of `a` contains `b` | `other_table_list` | `other_table_list_renamed` | `other_table_list_swap` |

A positive control differs from its refusal only by the conflicting family name; the manifest names stay.

## Separate check of the form and of the reference group_by

`group_by_unknown_field` contains the mapping `{field: nosuch}`: the form is correct, but the field is not declared. `r39_group_by_known_field` differs from it only by the name `name` and has the verdict ok. The scalar is `r39_group_by_scalar` with refused by form; its refusal does not prove the reference check. The common background and the line lease off are kept byte for byte. These are prepared inputs and expectations; the regular loader was not run by the author.

The author's check: `fields_derived_items_unknown` is assigned in N5 to the unknown keys of N1.2. `unit.derived` is not part of the grammar of the lessons; the refusal of this file does not confirm the check of the reference items. The two display_tree_*_unknown check references, and display_tree_word_erase checks the unknown key erase; in N5 they are also assigned to the corresponding groups.

## Supplementary core seams

[`seams.tsv`](seams.tsv) (judge-only: the seams of the chapter; they check P/02.1-R157, P/02.1-R215, P/02.1-R176, P/02.1-R196, P/02.1-R155, P/02.1-R178, P/02.1-R193 and P/02.1-R213) contains 14 steps in 4 scenarios over pure loading: isolation after a refusal, a whole catalogue after a refusal, parallel loading, and layer order. The source is P/02.1 N3, including its race/purity rules. The engine word `run` executes the table through the seam adapter protocol of the common acceptance README; CALL normalization and projection are defined by [`forms/README.md`](../../forms/README.md). These are not additional rows of `verdicts.tsv` (judge-only: the verdict table of the chapter; it checks P/02.1-R008, P/02.1-R013, P/02.1-R018, P/02.1-R020, P/02.1-R024, P/02.1-R026, P/02.1-R027, P/02.1-R028, P/02.1-R030, P/02.1-R033, P/02.1-R034, P/02.1-R036, P/02.1-R038, P/02.1-R041, P/02.1-R043, P/02.1-R047, P/02.1-R048, P/02.1-R049, P/02.1-R054, P/02.1-R055, P/02.1-R056, P/02.1-R058, P/02.1-R059, P/02.1-R062, P/02.1-R064 to P/02.1-R068, P/02.1-R070, P/02.1-R072, P/02.1-R074, P/02.1-R076, P/02.1-R078, P/02.1-R083, P/02.1-R086, P/02.1-R088, P/02.1-R092, P/02.1-R094, P/02.1-R099, P/02.1-R104, P/02.1-R108, P/02.1-R113, P/02.1-R115, P/02.1-R126, P/02.1-R127, P/02.1-R128, P/02.1-R131, P/02.1-R134, P/02.1-R136, P/02.1-R139, P/02.1-R141, P/02.1-R153, P/02.1-R155, P/02.1-R182, P/02.1-R198, P/02.1-R201, P/02.1-R206, P/02.1-R213, P/02.1-R215, P/02.1-R236).

The single regular loading path (P/02.1-R147: every process loads a manifest by the same loader) is not judged in this lesson: these seams call the loader through the adapter and do not show which path another process calls. It is checked by reading the code in review.
