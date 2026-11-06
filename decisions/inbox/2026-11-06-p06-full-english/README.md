# P/06 full English after the closed semantic baseline

Language basis: `01c2ef53920042ff4313807b3d2ef48ed05baf27`, the accepted
`coord103/p06-semantic-joint`. This delivery retains its P06 review decisions,
P01 `max_body`, P02 finite profile and numeric-loader supplement, and C4 case49.
Historical semantic maps remain separate and unchanged. This directory records
the language delta only; it does not claim implementation acceptance.

The remaining Russian section names, descriptions, norm references, comments
and field-template labels in P06 source are English. Actual protocol words,
selectors, flags/defaults, validation trees and typed outcome columns retain
their values. Three `forms/refusals.tsv` word-column changes are references to
chapter 6.5 N4, not wire refusal words. The 61 field-column label changes use
`<field>` and `<number>` in `data/refusal-words.tsv`; concrete request paths and
JSON values are unchanged. Existing English protocol words are not renamed.

`source-map.json` records file SHA/blob/size pairs, 402 changed metadata TSV
cells with path/physical line/column and full old/new values, 175 JSON/YAML
metadata fields, raw text/comment changes and all 80 TSV table rosters.
JSON validation structures are unchanged after removing description metadata;
the OpenAPI parsed delta is only description/summary. The two probe manifests
change comments only. Built family sections are rendered from these sources in
both English and Russian. Other mirror changes are Latin historical M-labels
and the same URI-encoded historical document citations; the original names
still resolve after URI decoding.

The 519 localization rows, including parameters and intentional trailing
caption spaces, all 14 raw acceptance assets, the three published console
assets, common turn sources/49 cases and FR06 remain frozen. Browser fallback
is still the explicit P07 owner debt. P01/P02/P03/P04/P05/P07/P08/P09/P10,
Source, VMS, tools, skills, root console module and reserved common paths are
unchanged from the semantic joint. The sole related common delta appends the
new byte proofs to `Platform/common/data/cell-json-sha256.tsv`.

The existing source encoding is applied to complete columns:

| Table under P06 | Declared columns | Rows | Marked cells |
|---|---|---|---|
| acceptance/1/scenarios.tsv | request | 514 | 514 |
| acceptance/8/scenarios.tsv | request,expect | 189 | 378 |
| acceptance/8/seams.tsv | request | 4 | 4 |
| vectors/request-digest/digest.tsv | input,canonical | 12 | 24 |
| vectors/requests-body/requests_body.tsv | body,stored | 77 | 154 |
| vectors/rid/rid.tsv | rid | 30 | 30 |
| vectors/rid/template.tsv | body | 20 | 20 |

Total: **1124 added cells / 7 tables**, **1855 total cells / 16 tables**.
The prior 731-cell/9-table proof is an exact byte prefix. `cell-map.json`
separates original/raw source SHA and physical lines from each restored UTF-8
cell hash. Within these seven tables every marked and unmarked data cell is byte-identical after one
existing reader decode. Each marker adds exactly one LF row; no header is
inserted in a positional table. Invalid inner JSON remains an input to its
previous semantic parser. Unicode fixtures, JCS, AAD, signatures, rid and
expected outputs are not translated or repaired. No decoder, grammar or alias
is introduced.

`semantic-preview-inventory.tsv` is the actual generator preview before the
source encoding: 57 translated / 0 excluded. `port-gate-map.json` matches each
selected source input/output and its existing CALL port against the language
slice. In particular s06, s07 and s08 remain selected and byte-identical.
This is generator/source evidence, not 57 executed calls. The actual preview
after encoding exits 1 at acceptance/8 s01: `gen_cmdtests.read_seams` consumes
the outer JSON string as a raw request. It needs the assigned Gen2 common-reader
adoption; this preview is **not GREEN**, and no excluded case is counted PASS.

The shared source-cell test also has a pre-activation assertion that the real
seams8 table is unmarked. The combined author run is 255 tests, 1 failure,
1 existing skip, 217.282 s: its sole failure is
`SeamsBinding.test_real_seams_unchanged`. Thus forms76 and spec168 pass (spec
has the existing skip), sourcecells10 pass/1 fail. The Architect assigned the
exact four-cell activation regression to review-claude, with no skip or decoder
change. These two follow-ups belong to the final joint and are not hidden by
the successful structural source check.

`completion-proposed.patch` is a separate skills-review proposal for the one
`FULL_ENGLISH_DONE` entry. It has not been applied. The explicit P06 English
scan and all 31 mirror comparisons pass independently of that entry. Exact
source check/log hashes and limits are in `checks.json`.

Read-only reproduction on this exact source checkout (with the frozen before
Git object present):

```sh
python3.12 -B decisions/inbox/2026-11-06-p06-full-english/audit.py
python3.12 -B skills/lesson-spec/scripts/check_spec.py --strict-coverage
```

Use the pinned lesson-spec requirements environment. No normgen full/KIT,
native/Go/controller/console/model/SUT execution, private export, official pin,
queue or runtime switch is claimed. Full joint GATE and release remain with
coord103 after its assigned code and checker slices.
