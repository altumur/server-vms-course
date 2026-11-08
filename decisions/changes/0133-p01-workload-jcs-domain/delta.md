# Delta 0133-p01-workload-jcs-domain

change: 0133-p01-workload-jcs-domain rev 1 · state review · author spec103

Two MODIFIED artifacts, unanchored contract prose. Exact UTF8/codepoint/LF and inverse records are in the external BEFOREWRITE-SOURCE2-MAP; old evidence is unchanged.

## MODIFIED artifact `Platform/01-store/spec/production-acceptance.md`

old-sha256: 62d3b2cf77ef6518fa4bf2ac389b36da143813ac9ee8e6309ab97b37caa93d3f

new-sha256: ec1ddfbcfb634c6591e99fa8d5b887a63eeefce7a3beb429eead36a0538484d0

For `WORKLOAD_ORDINARY` and `WORKLOAD_WORST`, volume is the sum of the canonical JCS byte lengths of each row's `items` value. Record raw JSONL, request and storage bytes separately; those raw bytes are outside these two workload-volume thresholds. Other budgets and the measurement definitions below are unchanged.

## MODIFIED artifact `Platform/01-store/ru/spec/production-acceptance.md`

old-sha256: 78f30c3e70191b64593cfdbf2f867fc9bd329324cce096fa391a1c7af09fa58e

new-sha256: f45e3b06b79485d4eebd728b415bad82614ced4996f488a632026c9850b795cc

Для `WORKLOAD_ORDINARY` и `WORKLOAD_WORST` объём — сумма длин канонических JCS-байтов значения `items` каждой строки. Сырые байты JSONL, запроса и хранилища записываются отдельно и не входят в эти два порога объёма нагрузки. Остальные бюджеты и определения измерений ниже не меняются.
