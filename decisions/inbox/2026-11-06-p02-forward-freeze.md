# P02 source-only forward merge on published English common/P01

Published course basis: `5a355d41ba49239726e89997609b135db5268d73`.
Author source: `828e2583fe90d8f959bdf7d4088132f5ecb96699`.
Exact two-parent source merge: `294825d2490765884f6a1186410ccc7dafd74f33`.
Branch: `spec/0121-p02-forward-main5a`. The later evidence commit adds only this record, the audit, its forward-basis map and proof; it does not change the merged source.

The only conflict was the append-only end of `decisions/adr-norms.tsv`. All published rows remain byte-identical, followed by all 21 exact P02 author rows. Every other source delta has exactly the author's bytes. All P02 lesson files, including human mirrors, are identical to `828`; its accepted review ancestors `dc76e8f33`, `29f619228` and `c58743b5` remain ancestors. There is no P03 source `8f` ancestry. P01, P03, P04, P09, VMS and the entire `tools/` tree equal published `5a`, including generated outputs. P04 work remains in its separate worktree and branch.

The forward map `2026-11-06-p02-forward-basis.tsv` is separate from the frozen language map. Its SHA256 is `b09247a255f1a67b8ccde6a0b864a7c71ccef2fea439e7367206e0d4a1fda13b`. It covers 3,604 paths whose identity differs between the two inputs: 2,848 inherit published `5a`, 755 inherit author `828`, and one is the combined ledger. Each row records mode, Git blob and SHA256 for both inputs and the source merge. Inherited output entries document identity only. The actual source delta against `5a` is 756 files.

The original language map remains unchanged, SHA256 `4ce59e1cc659fbf30f94931c629ed63fc320006e366651f6764bea411520f91d`; the original preservation JSON also remains unchanged. The composed corpus has 947 cases (203 accepted, 744 refused), 220 canonical vectors, 205 acceptance views, 87 put cases and wire counts 12,141 calls / 616 exclusions. All lesson source bytes and closed forms equal `828`. The N/English completion flag, translated default expectation and two canonical fallback strings are retained. Published common helpers, provenance, root/export paths and registry579 are retained. The old unrelated `family_read_key` baseline was not altered or hidden.

The forward audit independently decodes every declared cell against its actual before-source: 351 common cells against `2ebffcaa`, 345 P01 cells against `cac14097`, and 19 P02 exec cells against `fa9fa46a`. All 715/8 before/decoded UTF-8 byte pairs match, including the entire inner lexical JSON string in each exec cell. Its one physical-line shift remains explicit. Source-cell proof validation, all 19 P02 mirror pairs and full P02 English scan have zero errors. The shared 31 canonical outer-form fixtures are unchanged and pass in the focused tests.

New composition checks, performed on this merged tree:

- `check_spec.py --strict-coverage`: PASS with exactly 62 exceptions, including 832 VMS family-read rows; form_cases/verdicts=947, canonical_vectors=220, canonical_mutants=67/67. No exception or baseline adjustment.
- `python -B -m unittest -v test_source_cells v7.test_spec.TestTree.test_manifest_clean v7.test_spec.TestTree.test_canonical_chapter v7.test_spec.TestStack.test_defaults_only_inside_present_parent`: 11 tests PASS, 32.304 seconds, no skips. This checks the published reader against the new 715-cell source proof and the actual composed 947/220/default inputs.
- `python -B decisions/inbox/2026-11-06-p02-forward-audit.py`: source identities, ancestry, forward map, ledger append union, all 715 byte pairs, mirror and English checks PASS. The script is read-only for normative source and outputs; it writes only its two evidence files.

Local logs are `.spec-check/p02-forward-check-spec.log` (SHA256 `a40265af7fc3e069d8de3e22c410f3d8eb09b084b6cb5d59800267f02801f50f`) and `.spec-check/p02-forward-focused.log` (SHA256 `ae3770e8e698e76a9c0c956a96ef4cb6846fab8b6436385adfa9bdc2cf1b36b5`). The original complete source Gate for `828` was not repeated. No normgen regeneration, kit run, runtime/SUT run, queue operation, image/service change, export publication or pin switch was performed. Generator/runner scoped code work and the future joint normgen+kit Gate remain with coord103.
