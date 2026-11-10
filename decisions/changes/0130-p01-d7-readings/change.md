# Change 0130-p01-d7-readings

change: 0130-p01-d7-readings rev 1 · lessons P/01, Platform/common · author spec103 · state review

Publication parent `8d7d48aefa1fbc70a0ea649c797b2df6036690f8`. Task P01.143, ADR-0130 plan row 5. P01.143: README «D7 test-side evidence bindings» EN/RU, after «Payloads»: the meanings of the words of the payload for `P/01/production`, by the open points of ops103 (P01.132, `d7/README.md`): `admission_time` is the wall clock of the daemon process, the stored time is judged by public outcomes; `heap` is `RssAnon`, `memory` is `VmRSS`; with the latch `sink`, `cancel` is the deactivation and no observation carries it; `recover_mark` names no file, the point is the first change of `-dir` after the first completed top-level entry of `recover` (P/01.3 R021), so no mark name in argv or payload (a correction of the reading of ops103); `copy_after_headers` is the client-side end of the stream for the CLI half of `RUN-H03`, the daemon half is judged under the cancellation, the stalled sink and the stop of the judge. No requirement unit changes; no form or numeric value changes.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/common/acceptance/README.md` | MODIFIED | 059292e55b28a096a131a78935b1569f9f362363 | c4b675a884e22db1f8725ff29009060ef7f45c3f | 4db9c073cf29f5e92aeaef726c7807d3528724bbe44e4e090086c02345aa19d5 |
| `Platform/common/ru/acceptance/README.md` | MODIFIED | f868b4547c28db21b8d728d949d8bd1da5f36eae | 04f89e48333193d2d700efef9689322d68e18ca7 | 1d23109b9230babf3185f079a36af23bfe270eec7393065d67a4ae7fc0fd2ed9 |
