# Change 0130-p01-production-bindings

change: 0130-p01-production-bindings rev 1 · lessons P/01, Platform/common · author spec103 · state review

Publication parent `c28a89768c50093f1374d94fb60d47adbbc81235`. Task P01.136, ADR-0130 plan row 5, the condition of P01.132; the Architect's answer on P01.136 (two commits). (2) Stand data of the target `P/01/production`, judge only, in `Platform/common/acceptance/production/` next to `forms/production.tsv` (the acceptance of a lesson with chapters holds only chapter directories, check_spec): `bindings.tsv` (the activations of the D7 bindings of each entry of `production.tsv` by the payload form), `input.json` (the input of N6.2 without `source_pin`; `budgets`, `manager`, `volume` absent: P01.134, the teardown margin of ops103, a volume of the host), `README.md` EN/RU. Decisions 3 and 5 of P01.135 are applied; decision 1 is not reflected in data. The descriptors with identity, invoke, refs and pin are the stand's (P01.132). No numeric value is invented. No requirement unit changes.

| Artifact | Operation | Before blob | After blob | After SHA256 |
|---|---|---|---|---|
| `Platform/common/acceptance/judge-input-filter.json` | MODIFIED | 20b5962a32a9678675b0359863ee08a48f7e8ac1 | fb005cbef5a238f1635f0d82ef87fc0fbe6fa6f4 | 1b01c3b8592b9fe79cd78ef7c9c835b2753db91e24486b3dcd06d30eff935e7e |
| `Platform/common/acceptance/production/README.md` | ADDED | - | b17d1be69be2f8dc85e3253b0f132f32f8bc97ae | b724ed8bf3bd64c09da1e501cc6f09a0ae9582c557de245d08165b9d22366070 |
| `Platform/common/acceptance/production/bindings.tsv` | ADDED | - | 791766136390bd1c7b1da45dab51fa50024cacce | f9879d0cadd86831a03a815369ee06802bb8c630fed40ccb3a0a77a6c53bf5b8 |
| `Platform/common/acceptance/production/input.json` | ADDED | - | 00517d70de6db1e19725caa81a52566a6f9011a8 | 4ae3f0c00241cb6269312ab8e0c5a39ef219ff0c9df43821a958cb78ea5d5287 |
| `Platform/common/export-model-filter.json` | MODIFIED | 230d2756547b3f13128e723648ca6694fac39b7d | 4159ccd67853bf5d3c678dc718c0e7ef46e7739f | a33660602c7f8dd76140ec89db6f9d45d24d5feea7b7d301ddba2b9ca8a4ec56 |
| `Platform/common/ru/acceptance/production/README.md` | ADDED | - | f2657c447c51196a794ef429ffd6b5114e6b353e | 9171731adf3eeb4ef6b32cadb32221522661759fbcc19a8e18ea7dcb9be3f864 |
