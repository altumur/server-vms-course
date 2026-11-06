# Counting final-code origins (ADR-0127 addendum (2), item 1)

`../code_origin.py` counts physical lines in a final implementation Git snapshot. Its JSON input pins full implementation
and kit commit SHAs, an explicit directory scope, exclusions, and code/test suffixes. It uses Python stdlib and Git;
it does not execute generators, runners or implementation code. Supply local repository directories through
`--repo ALIAS=PATH`. They are excluded from the report, so moving a repository to another machine changes no results.

```sh
python tools/normgen/code_origin.py \
  --config tools/normgen/provenance/probe1.json \
  --repo probe1=/path/to/cammeta-c-go-codex-kit > /tmp/probe1-origin.json
python tools/normgen/code_origin.py \
  --config tools/normgen/provenance/probe1.json \
  --repo probe1=/path/to/cammeta-c-go-codex-kit \
  --format markdown > /tmp/probe1-origin.md
```

[probe1.json](probe1.json) pins every input to probe 1. A kit pin is its import commit in the implementation, containing
the manifest and original kit bytes, including unchanged editable scaffolds. The script verifies every counted kit file
against its manifest SHA-256. The report records the manifest's own SHA-256 and its course/export pins as metadata.
For a separate kit repository, supply another `repo` alias and full commit. `source_root` is relative to the kit Git root;
`target_root` is relative to the implementation. Append manifest `files[].path` to those roots. The manifest's own path
is always relative to its snapshot root.

Current generator output is temporary. Manifest `source` labels under `tools/normgen/out/` name generated artifacts,
not current course Git inputs. `code_origin` still reads the immutable **imported kit snapshot**, its manifest and
actual imported payload bytes. Regenerating current output cannot replace historical package bytes or their SHA.
The checked temporary-output manifest binds current source/code/runtime inputs and actual payload hashes; its
random physical directory is not part of issued payload/provenance. A changed prepared set is rejected, never healed.

For each final file:

1. Select a file under `include_dirs` matching `suffixes`. Exclude `exclude_dir_names` at every depth, necessarily
   including `vendor`, and additional `exclude_paths` subtrees. Count each file once. Overlapping included directories
   or multiple kits owning the same path are errors.
2. Find its kit entry by path. If SHA-256 matches the original bytes, retain manifest `origin`, either `generated` or
   `handwritten`, including editable files. An unchanged scaffold does not become model code.
3. Attribute an entire changed editable file to `model`, using its final lines rather than scaffold lines, diff additions
   or edit counts. Files outside kit manifests are also `model`: a residual category for implementation-owned code,
   not Git-based authorship inference. A changed closed file stops counting with an error instead of attributing its
   changed bytes to the kit.
4. Count test suffixes separately (`_test.go` in the probe). A line ends at LF, with a final nonempty unterminated part
   also counted; empty files have zero lines. Include comments and blank lines. Ignore manifest `lines` metadata.
   Deleted kit files contribute zero final lines and are listed separately.

`DO NOT EDIT`, `Code generated` and `YOURS` headers do not determine origin. Kit `handwritten` includes runtimes and
shared contracts even when closed to edits. Copies in distinct modules count separately: this measures final implementation
composition, not unique generator lines or effort. Unreadable pins, incorrect SHAs, unknown origins, duplicates, symlinks
and unexpanded submodules within the selected scope are errors.

JSON records line/file totals for all three origins separately for code and tests, per-included-directory totals and a
file inventory: path, Git blob, SHA-256, origin and reason (`unchanged_closed`, `unchanged_editable`, `changed_editable`,
`outside_package`). It emits no source text. File order is deterministic; execution time and working-tree contents are absent.

[probe1-report.md](probe1-report.md) is the pinned-input Markdown report: code **10107 / 8213 / 12481** and tests
**29312 / 0 / 39**. The difference from the initial review metric is 17 unchanged editable `open.go` lines whose SHA
matches the kit; they retain `generated`. The Architect's decision was conveyed through coord103 on 2026-11-05.

Judge: `python -m unittest discover -s tools/normgen -p test_code_origin.py -v`. It creates independent Git repositories
to test handwritten code with generated headers, generated code without headers, both unchanged editable origins,
changed editables, final-line counting, tests, vendor, exclusions, path moves and independence from dirty working trees.
Corrupt closed files, kits or manifests must refuse. Probe numbers come from a separate script run; line implementation
sources are not copied into judge fixtures.
