# ADR-0129 p5: clarify P/01.1, no store-core form or algorithm

Exact base `62751995ba14646dac48d482d5dc394ecd9a87c2`; read-only report `517c1d2cd8273eb8ca04f92f4fe5a12bb405b3d9`, SHA256 `f474b2db2fa6cd5ba2ceca90df692995d236c3778b62352143028b7313dde966`. The report's typed store_core profile was rejected by ADR-0129; none is introduced. The observed gaps predate this change and are present on the assigned base. The report is analysis, not an implementation failure or test run.

R088 and R132 now distinguish admitted-record metadata from zero business effects explicitly. R090 names binary64 for both time-bound comparisons/fingerprints and preserves exact string version comparison. All other req units, N2/max-body, OpenAPI, write-checks and libraries are unchanged. The separate P06-related source588/Englishfb is neither read as a source nor copied here. No current implementation, model, runtime, export or official pin is touched.

| Item | Old coverage preserved | Addition |
|---|---|---|
| Admission on refusal | R070/R088/R132; fractional boundaries s2 and successful monotone/reopen s3/s5 | s7 single put/delete and s8 batch cover expired/early/guard/conflict; immediate clock rollback precedes all observations so reads cannot mask a missing refused-record timestamp; changed-condition reuse proves no id occupation. s9 covers an expired single write and guarded batch through graceful reopen. |
| Guard order versus fingerprint set | R125/R131, 35 steps 8–11; R134, 36 step 3 | none; source-list order and set semantics already have distinct witnesses |
| Binary64 time bounds | R019 already defines binary64; ordinary 28/30 and s2 cover equal spellings and fractional edges | s10 separates binary64 from exact decimal comparison; s11 tests equal rounding and adjacent distinct binary64 for both bounds on put/delete/batch replays |
| Exact versions, zero versus absence | R019 says opaque equality and nonempty versions; normal bound/CAS-order cases do not reach zero CAS on absence | s12 sends string 0 to absent single/batch CAS and guards, then uses empty-string conditions; no numeric version ordering or allocator seed assumed |
| Absent delete | R116, 31 steps 1–4; batch 34 steps 7–8 | none; visible absence and later create-once already covered |

Old ordinary source table: 345 steps, byte-exact including all outer cell-json request bytes/proofs. Old seams: 6 scenarios / 73 steps, exact whole-file prefix. Additions: 6 scenarios / 128 steps, total 12 / 201. Only named case selectors are appended to existing store_core/durable gates; all other columns, including the final empty when field, are unchanged. Two changed TSV lines intentionally still end with a TAB for that existing empty column; it is not an added space or a changed applicability condition. No new form/port/directive/KIT part is introduced.

These witnesses are not executed algorithm/SUT acceptance. Graceful Close/Open does not prove power-loss/barrier correctness or consensus. Opaque wire versions do not expose allocator counts: zero version issuance remains the existing R089/R132 reading obligation, not a fabricated counter observation. No reference store/snapshot/effects interpreter is supplied. Source arithmetic checks only explain the number pairs. Full normgen/KIT runs follow an exact joint source root under coord103.
