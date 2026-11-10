# Change 0135-p01-second-point

change: 0135-p01-second-point rev 1 · lessons P/01, Platform/common · author spec103 · state review

Publication parent `933b8bac1605005e51d6e9c8c9703ac47b0342ca`. Task P01.141, ADR-0135 addenda (8) item 3 and (11) item 3; review P01.138 (Kimi, `7ba607573`) and the Architect's note on its outcomes «norm». (1) New P/AC-R051: the judge reads a response that the implementation gives before the whole request is written (RFC 9112 §9.6) and judges the step by it; the failed write of the rest is no mismatch and no transport failure. (3) B1: the closed reason `no_machine_form` in P/AC-R030 for a probe of `forms/extra.tsv` written only as prose, until the probe has a machine form; the header of `extra.tsv` says so. (4) C1: P/AC-R011 makes the length, the SHA-256 digest and the content type of a response body mandatory in the report for every judged step with a response. (5) C2 is already closed by P/AC-R030 (P01.115 item 2): every name of every `ASSERT` step of the tables occurs in an earlier step of its scenario; not changed. Changes J, not M; it enters the next J input, not the continuation of P01.140 on `f11bf34d`. No numeric value of a norm.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/common/acceptance/forms/extra.tsv` | MODIFIED | c124c5db2a8b3347295711fe5028b13fdd7157ef | b7c7fc584563132c726731526ab71a05d1c90c1d | 62cae431caf6be4a88b8cf9988a1824c3664510912bebfc71ae8bc7f1005201f |
| `Platform/common/acceptance/spec/acceptance.norms.md` | MODIFIED | a39d764265ac1dce8e78fabe08567aa50688f9d7 | cfe76549872fa3fa7e5d2679a795b5ebb92b8587 | 192f72be8ea33d9f6f92d5472be5c9f1d3756596ce73704bf3be0ff032ba92d2 |
| `Platform/common/ru/acceptance/spec/acceptance.norms.md` | MODIFIED | 7933483a5aa9c39194189de9d0b4b162d16de9dc | 75b19306968533131b40acd150500f6b0ec9d023 | 7e3ed5a54aad8568f7f832a01564e175501e1940ac9901d3b383c9cfb7e9ed96 |
