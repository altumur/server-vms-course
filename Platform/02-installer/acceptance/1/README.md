# Acceptance P/02.1 — the verdicts of the manifest loader

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The scenarios of [the norms of chapter 2.1](../../spec/02.1-installer.norms.md) N5 (ADR-0080); the stand — [the common acceptance README](../../../common/acceptance/README.md). The door of the chapter is the loader itself: a file is given alone, as the manifest of a subsystem, and the answer is one of two.

## verdicts.tsv

Tab-separated: `case`, `verdict`. Lines with `#` and empty lines are not scenarios.

- `case` — the file `cases/<case>.subsystem.yaml`, loaded **alone** (without a catalogue of other manifests).
- `verdict` — `ok`: the manifest loads; `refused`: a loading refusal.

The acceptance runner:

- loads each file by the regular loading path of the implementation (the one by which a manifest is read from the store or from a file, N3 of the chapter), not by a bypass function; the way of calling is the command for loading one file that the implementation named in its description (the norms of the chapter, «Implementation decides» item 3): exit code 0 — a manifest, another one — a refusal;
- counts `refused` only as **a refusal in words that names the file** (the file name is part of the text); a crash, an exception of another kind, a partially loaded manifest — a mismatch;
- counts `ok` when the loading returned a manifest;
- checks that the set of files in `cases/` equals the set of rows of the table: an extra file or an extra row — a mismatch;
- the verdict and the exit code are strict (ADR-0092 item 5); for the cases of `classes.tsv` it checks the refusal class; the information of `diagnostics.tsv` is a hint: the runner writes it into the report without a failure;
- SHOULD run a sample through the manifest installation path (`manifest put` of the implementation, chapter 2.3 N3): all cases with the verdict `ok`, one refusal per each class `refused:<class>` from `classes.tsv` (the first by case name) and all installations of `puts.tsv` (chapter 2.3); the verdicts of the other cases are checked by the loading mode (the decision ADR-0080 addendum (17) item 2). An accepted file lands as the row `platform/manifest/<name>`; a refused one is not put into the store, the return code is non-zero. The installation checks the candidate in the full catalogue, and six accepted files name `testsub` in the catalogue checks: `bound_to_string`, `blob_required_false`, `secrets_reader_domainconsole` (`worker.requests: [testsub]`), `m49_table_shelf_log_ok`, `c6_secrets_reads_with_slash_ok`, `c3_near_by_ok`; therefore the run through `manifest put` is done in a store where `testsub` is already installed (`Source/tests/testdata/testsub.subsystem.yaml`). In an empty store these six files correctly get `refused:catalogue` (review of stage B 1–2, item 13).

The rules by which the verdicts are set are the norms of the chapter N1 (text, document, field, references) and N4; they are not here, so that there are not two versions of one norm (ADR-0003). Origin: the common table `spec_verdicts.tsv` (reviews 14 and 15, the Architect's verdicts of 2026-10-06), moved here on 2026-10-14 with eight new cases; both sides remove the former place in their own windows.

## puts.tsv

The manifest installation `manifest put` (`puts.tsv`, `puts/`) — [the acceptance of chapter 2.3](../3/README.md).

## classes.tsv

The N4 refusal class of selected cases: tab-separated `case`, `class` — the layer where the refusal is (ADR-0092 item 6): `text`, `form`,
`relations`, `catalogue`. Each `case` is in `verdicts.tsv` with `refused`; the class is compared with the class of the regular refusal
of the loader (the word `refused:<class>`). A correct verdict with another class is a mismatch. The corpus checks the verdict and the class;
the path and the line are a hint (`diagnostics.tsv`). The transition to V7: the former classes `name`, `key`, `value` became `form`,
`reference` became `relations` (the deltas — the delta table of set «B» of the skill `lesson-spec`).

## diagnostics.tsv

Hints for selected refusals (ADR-0092 item 5: the paths and lines of a loader refusal are a hint, not a norm; the runner writes
a divergence into the report without a failure): tab-separated `case`, `paths`, `lines`. A header with `#` and empty
lines are not cases. Each `case` occurs once and has `refused` in `verdicts.tsv`.

- `paths` — a JSON array of paths; each path is an array of key names from the root; a list index is a JSON integer (`0`), a key name is a string
  (`"0"`): these are different segments (N4 «Diagnostics»). The paths are a set: in the table they are written in the canonical order —
  by the bytes of the JSON Pointer path (RFC 6901), line numbers ascending (ADR-0087 addendum (3) R2); the set of paths
  named in the refusal is compared, a missing or an extra path is a divergence of the hint. In `unknown_multiple` all three
  paths are needed in one refusal, not only the first typo found.
- `lines` — a JSON array of the mandatory line numbers of the source file, starting from 1. An empty array means
  that this case does not check line numbers; it does not forbid them in the refusal. For `dup_top_key_name` the number
  of the second declaration of `name` — 36 — is needed; a reference only to the first declaration is not enough.
- The runner extracts this information from **the regular refusal of the loader**: from the error information already provided by it
  or from the text in the format adopted by the implementation. It describes the way of extraction; the case name and the input
  file do not serve as a source of invented paths or numbers for the comparison. The path separators, the labels of the line number
  and the rest of the message text remain the choice of the implementation. This table sets the values for the check,
  not a mandatory internal error type or an additional door of the loader.
- The requirement to name the source from `verdicts.tsv` stays — it is a norm. For example, `unknown_depth4.subsystem.yaml: error`
  passes the verdict, and the hint of the report will note that there is no path `unit.fields.name.requried`; a refusal for `dup_top_key_name`
  without line 36 — likewise.

For the other cases the verdict table checks acceptance/refusal and the source name; the implementation SHOULD give the path and the line
per N4 of the norms — as a hint.

## `journal/corrections-1.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample` (a sample of a generation error), `fix` (which line of the lesson was clarified), `languages`. Empty — no error has repeated so far.

## Additional check of string field names (R36-01)

In a minimal correct manifest, separately for `unit.fields` and `tables.<t>.fields`, the keys 1, true, null and 1.5 (without quotes) give `refused:text` per N1.1 `refused`: a plain key that the table `scalars` reads not as a string is a refusal of the text layer everywhere, including in the value keys of `json` and `display.options` (`display_options_bool_plain_key`); the path and the line are a hint per N4. The same names in quotes are strings and pass. The pair 1/"1" is refused as a whole (`text`), it is not converted into one string with the loss of a field. These inputs are added as profile_unit_key_*/profile_table_key_* to verdicts.tsv and are checked by the same regular loader as the other cases; reading the types of the YAML nodes does not by itself prove its conformance.

The cases profile_* cover the positive neighbouring values and the restrictions P/02.1-13…17,
and also the types of field keys and the membership of worker.writes (P/02.1-06/07, P/02.5-01).
The prepared verdicts are not a result of running an implementation: the author checked the data and the stated
canon, the regular execution loader was not run here.


## Additional inputs of run 37

In all 48 profile_* the common lease background is fixed: the string off is written in quotes.
The target mutations and 9/39 verdicts are kept, but the former refusal on an extraneous false
does not count as a check of the target restriction. The new r37_* cover P/02.1-18…21.
The current corpus: 947 files, 203 ok/744 refused (10 cases `a119_writes_via_*` — the word `writes_via` of the unit and of a table: a list of subsystem names without repeats, its own name is admissible, for a table with `service: true` — a refusal, ADR-0119 addendum (10), (11); 2 cases `a119_calls_verify_*` — the entry `domain/verify` in `calls` ok, `GET domain/verify` — a refusal, ADR-0119; 3 cases `a116_calls_manifest_source_*` — the entry `GET manifest/<s>/source` in `calls`, ADR-0116 addendum (6); 46 cases `a115_*` — the keys of ADR-0115: `rank` at `door.routes` (with `role`, `domain` — a refusal, addendum (19)), `display.langs`, `display.tables` (relation № 159), labels `{key, text}`, `hidden`, `items.ref`, `ref_label`, `events.kinds`, a dot in the name of a unit field (`a115_unit_field_quoted_dot` — the former key `'1.5'` of the case `profile_unit_key_quoted_ok`, there it is replaced with `'1e5'`), relations № 67–70 on `<t>.<field>` and № 158; 16 cases `a95_*` — `door.pass.operations`, `calls` with folders, operations and domain doors; 7 cases of ADR-0098 §9 — `a98_sub_*`: reserved subsystem names; 25 cases of ADR-0095, ADR-0096 — `a96_*`: forbidden names, `display.tree.folders`; 40 cases `a94_pass_*`, `c8_ref127_*`…`c8_ref131_*` — the kind of the second `door.pass`, ADR-0094 B1; 3 cases `k38_sub_changes`, `m49_table_changes`, `rows_changes` — the first segment of the feed, ADR-0094 B2; 2 cases `c8_ref125_*`, `c8_ref126_*` — a term at the table of holds and places; 3 cases of ADR-0094 B4 — `a94_unit_field_index`, `a94_table_field_*`: platform field names; 9 cases of ADR-0094 step `3b` — `a94_table_delete_after_*`: the term of table rows; 18 cases of ADR-0094 B7 — `a94_*`: `console.shell`, `console.files`; 6 cases of the coverage audit P/02 of 2026-10-30 — `secrets_readers_*`, `worker_writes_*`; 43 of set «B» of ADR-0092 at the transition to V7 — `t*`, `f*`, `r*` under the comment «Set B ADR-0092» in `verdicts.tsv`: the rules of the fine check of layer 1, scalars by node style, the integer place, a full match of an expression, other forms and relations; the deltas of the former cases (12 deviations of N1.1 from YAML 1.2.2 — the 12th is a trailing comma in a flow, `t33`, `t33b`; TAB and `{k:}`, the integer `4.0`, classes by layer) — the delta table of set «B» of the skill `lesson-spec`; it is appended to all files without `worker:` (ADR-0092 item 7); 9 c2_metrics_* per C06-METRICS-DSL-33-01: count and from together, neither, from not heartbeat./status., agg outside the list, count at heartbeat, histogram without buckets, values not at label and with count, name starting with _ — value; c2_metrics_name_repeat — elements by the form from: status.phase, the subject is the former one; 2 name_free_* per ADR-0091 addendum (24) item 5: the name `free-cam` — name, `free` — ok; 6 door_routes_domain_* per ADR-0091 addendum (14) item 1: `{name}` — admission token, `{name, domain}` and `{name, role, domain}` — ok, `domain` empty, with a repeat, `person`, not by the kind grammar, not a list — value; 3 a91_affinity_exclusive_* per ADR-0091 addendum (10) item 1; 6 door_routes_role_* per ADR-0091 addendum (7), (8): an element of `door.routes` is a name or `{name, role}`; 11 per ADR-0091 addendum (4), (5): `worker.exec` is mandatory and the grammar of `exec` — a91_exec_*, a91_worker_missing, a91_parts_exec_shell_char; the key is appended mechanically to all other manifests of the corpus, the verdicts and classes are the former ones, the line numbers of the diagnostics are shifted at blob_default and status_worker; 12 per ADR-0091 addendum (2), (3) and VMS request № 1: 7 a91_* — `stop_timeout` of the worker and of a part at the boundaries, `shares.<share>.part`, an own share with `part` and without, 5 id_default_* — `{id}` in the default of a field; 28 a91_*, profile_unit_born, profile_unit_made, m49_table_state — ADR-0091 without replay protection: the state of a unit, ends, worker.creates, worker.uses, shares, parts, the name state, the fields born and made; three former refusals of delete_after with fixed and about — now ok, rules 46–47 removed; 3 a86/k38/m49 — the reserved name manifest, ADR-0086 addendum (1) R3: k38_sub_manifest and m49_table_manifest — refusals, a86_sub_manifest2 — an admissible neighbour; 3 door_routes_* — the segments of door.routes by the grammar name, the Architect's decision of 2026-10-20; 7 c9_* — the decisions of the log digest at the transition to the form source: «- -» (T15), a single «-» in a flow (T16; and with spaces around it — review of stage B 1–2, item 7), «#» inside a word (T28), a number class out of bounds under x-class (F1), is/is_not with null (F12), the one_of path by the rule list (F15); 59 c8_ref* — strict coverage of the rows of `references.tsv` of the form source, ADR-0087 addendum (1) R10: row N is the only reason for the refusal of the case `c8_ref<N>_*`, the former row numbering of the pair ADR-0085; rows 58, 61 hold with the condition «the table is declared» at references to a table field, row 84 is removed — findings of the corpus F1; 10 c8_* — cases of the log digest, addendum (3): the node rule on a form refusal below, the canonical order of paths, a number outside float in a json field, a field without type, a nested `{` in requests.key, enum under display.options, an integer of 4301 digits, «word# c»; 10 c7_* — the experience of the text layer of 2026-10-19: a comment deeper than the key after a word, U+FEFF in the middle, folding, `]` of a continuation, a block list of scalars, the float boundary; refusals — a comment in a continuation line, a scalar below a bare `-` (text), underflow (value); 3 c6_* — the pilot of variant C of 2026-10-19: `secrets.reads` with `/`, a flow key without a value `{unconfirmed_max:}` — value; 27 c5_* — the JSON Schema pilot of 2026-10-19: findings on N1.1 and N1.2a; 29 c4_* — the reconciliation of python and go of 2026-10-18) (16 m51_books_* — the form domain.books P/02.1 N1.2b (from M11/5); 3 of them — the grammar of key and to, review analysis of stage A 8–10, № 42; 22 m57_tokens_* — the form domain.tokens P/02.1 N1.2b (from M11/7); 13 m59_names_*/m59_keys_* — the forms domain.names and domain.keys M11/9 N1.7, N1.8; 10 m61_* — the form domain.shared, merge and domain.witness P/02.1 N1.2b (from M11/11)); diagnostics — 51 rows of hints (the transition to V7 removed the row of a case that became ok; 14 former ones, 22 of the reconciliation of python and go, 4 of the JSON Schema pilot — the path of rules on two keys, 8 c8_* and 4 c9_* of the log digest); classes.tsv — the class of the same 36 cases `c4_display_fields_quoted_numeric_key` and `display_options_bool_plain_key` (38) (since 2026-10-17 — four requests_outcome_*, ADR-0054 addendum; 39 m49_* of the mutation check: each forbidden table name, the boundary 2^53; the JSON Schema pilot of 2026-10-19 — 26 more: 20 refusals c5_*, `requests_key_stray_brace` — `value`, `c4_flow_empty_item` — `text` and four diagnostics cases of rules on two keys; c8 of 2026-10-19 — 65 more; review of stage A 2 — 10 profile_*_key_* with the class `text` per N1.1 keys — c9 — 4 more; the class `name` — `name_reserved_platform`, for the sample of `manifest put` by classes; ADR-0091 — 21 more, `c8_ref47` removed from the classes; ADR-0091 addendum (2), (3) and VMS request № 1 — 9 more; ADR-0091 addendum (4), (5) — 10 more; addendum (7), (8) — 5 more; addendum (10) — 2 more; 201 rows in all; the transition to V7 — classes by the layer `text`, `form`, `relations` and the cases of set «B»: 236 rows); puts.tsv — 23 installations — the acceptance of chapter 2.3.
Two additional refusals K37-03 — r37_rows_cluster/r37_rows_worker; together
with profile_rows_ts the whole list cluster/worker/ts is covered, and profile_rows_records_ok
remains the positive control. The new files differ from profile_rows_ts only in rows.
The count of the corpus is also reconciled in N5 and in the implementation instructions; readiness requires the whole normative checklist.
The pairwise intersection of the catalogue is checked separately: two correct single documents
with the name b at the second manifest and the table b at the first give refused:catalogue before the write.
The same with unit.rows=b; when the family is renamed to b_rows, the catalogue passes exactly this
check. Single verdicts do not prove the check of a pair. The regular loader was not run here.

## Check of the error class R37 (Codex)

Check not only the changed field of the generated input, but also the whole common background: lease off remains a string, true/false do not replace off/on when read by another YAML library. Single verdicts and the catalogue check are separate pieces of evidence. During an installation, different manifest names are changed by one operator sequentially; two writes of one manifest are resolved by CAS. Before the first write the candidate is checked in the full confirmed catalogue.

This is a subject of a check of the norms/data and of a future stand, not a performed test of an implementation.

The boundaries of :int per P/02.1: binary64, modulus not greater than 2^53−1; bool/null/string/non-numeric/non-finite/out of bounds — 400, not a language conversion. Check ±0.5, ±7.9, ±(2^53−1), 1e16, 1e21 and a canonical decimal result without an exponent.

The catalogue check includes the intersection of the name with its own rows/tables: even a catalogue of one such manifest is refused. This is a separate catalogue refusal; a single parse of a file is not declared a check of non-intersection.


## The full list of names and the catalogue check (K38)

19 k38_sub_* — refusals of the remaining reserved names (k38_sub_manifest — per ADR-0086 addendum (1) R3). Together with
name_reserved_platform and r37_sub_where/r37_sub_metrics/r37_sub_healthz all 23 words
are checked; a96_sub_folders adds the twenty-fourth, `folders` (ADR-0096); a98_sub_* — the seven names of ADR-0098; r37_sub_where2, a86_sub_manifest2 and a96_sub_folders2 remain admissible neighbours. The background of the 19 files is kept
byte for byte, including lease off; only the top-level name changes.

Non-intersection is checked by reading the implementation of `load_catalogue`, including a catalogue
of ONE manifest. The verdicts runner calls `load`, not `load_catalogue`;
one file is not automatically a catalogue of one file. Therefore adding
refused for a correct single parse of name=own rows/table here is not allowed.
The implementation description states the branch of the catalogue check and the checked cases:

| Catalogue composition | Conflicting family | Expectation of the catalogue check |
|---|---|---|
| A=B: one manifest name=b | unit.rows=b | refused:catalogue |
| A=B: name=b, unit.rows=b_rows | map tables contains b | refused:catalogue |
| A=B: name=b, unit.rows=b_rows | list tables=[b] | refused:catalogue |
| A≠B: name=a and name=b | rows of manifest a equals b | refused:catalogue |
| A≠B: name=a and name=b | map tables of manifest a contains b | refused:catalogue |
| A≠B: name=a and name=b | list tables of manifest a contains b | refused:catalogue |

The other parts are the correct background base; the second manifest has rows=b_rows, the first a_rows,
except the explicitly changed rows. The positive control of each row: change
the conflicting family name b to ledger (and the references to it), keeping the manifest names a/b;
this non-intersection check passes. For map a correct table declaration remains,
for list — only the family name, without ascribing HTTP doors to it. The result is the same
for any choice of root and a swap of the two manifests. On a refusal the catalogue is not given out
partially and the installer does not perform the first write.

This is an assigned check by reading with a subject and a reason per P/02.1-20, not a performed
run of the loader/catalogue/installer. The author checked the norm and the finite examples.

R38-02: three r38_unit_* without unit/rows/id must be refused by mandatoriness with the path of the missing value; r38_unit_minimal has rows=things/id=numeric without fields and must load with an empty set of fields. A common catalogue is not required; all the former 251 inputs are unchanged. The verdict check is the regular loader; the author's check of the YAML structure does not replace it.

## Separate check of the form and of the reference group_by (R39-03)

`group_by_unknown_field` contains the mapping `{field: nosuch}`: the form is correct, but the field is not declared. `r39_group_by_known_field` differs from it only by the name `name` and has the verdict ok. The former scalar is kept as `r39_group_by_scalar` with refused by form; its refusal does not prove the reference check. The common background and the line lease off are kept byte for byte. These are prepared inputs and expectations; the regular loader was not run by the author.

The author's check of the class A39-01: `fields_derived_items_unknown` is assigned in N5 to the unknown keys of N1.2. `unit.derived` is not part of the grammar of the lessons; the refusal of this file does not confirm the check of the reference items. The two display_tree_*_unknown check references, and display_tree_word_erase checks the unknown key erase; in N5 they are also assigned to the corresponding groups. The inputs and verdicts are kept, no new form of derived is introduced.

## Supplementary core seams for the kit

[`seams.tsv`](seams.tsv) contains 14 steps in 4 scenarios over pure loading: isolation after a refusal, a whole catalogue after a refusal, parallel loading, and layer order. The source is P/02.1 N3, including its race/purity rules. CALL normalization and projection are defined by [`forms/README.md`](../../forms/README.md). These are generated adapter tests, not additional rows of `verdicts.tsv` and not an executed acceptance of the implementation. The shared regular loading path (P/02.1-12) remains checked by reading; these tests do not prove which path another process calls.
