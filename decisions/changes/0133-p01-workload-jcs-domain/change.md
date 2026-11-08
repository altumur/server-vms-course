# Change 0133-p01-workload-jcs-domain

change: 0133-p01-workload-jcs-domain rev 1 · lesson P/01 · author spec103 · state review

Actual parent `20e2dc51df63cf49e0e75e53197ddce579368ffd`. Direct Architect task `SPEC103-P01-WORKLOAD-COUNTING-DOMAIN-TASK.json`; Source EN/RU pair only.

Clarify only the WORKLOAD_ORDINARY/WORKLOAD_WORST counting domain: sum of canonical JCS byte lengths of each row items value. Raw JSONL/request/storage bytes are recorded separately and are outside only those workload-volume thresholds. All numerical values, other budgets and measurement definitions, including store_write_bytes, remain unchanged.

Two unanchored production-acceptance artifacts; no new or modified requirement IDs. No runtime, native, model, export or GATE assertion.

| Source | Before blob | After blob | After SHA256 |
|---|---|---|---|
| `Platform/01-store/spec/production-acceptance.md` | 99e80d96f3fe0d558776383aa4dd47be77b43253 | 31410786475a41390e0b772fbfab09e0035fc617 | ec1ddfbcfb634c6591e99fa8d5b887a63eeefce7a3beb429eead36a0538484d0 |
| `Platform/01-store/ru/spec/production-acceptance.md` | bf2af22d87efedbe2eea78e3075fd2763890c541 | 08ee3b6ec7e73477cfb27ef488b114fc7f02b3a7 | f45e3b06b79485d4eebd728b415bad82614ced4996f488a632026c9850b795cc |
