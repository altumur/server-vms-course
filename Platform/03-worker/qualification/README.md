# P/03 qualification records

This English text is the canonical `qualification/README.md`; the Russian text is a derived translation for people, not in the export.

These records check the existing worker obligations in [chapters 3.2–3.7](../spec/03.2-worker.norms.md), [lifecycle](../lifecycle.md) and the imported contracts. They add no command, refusal, clock source, public observer interface or candidate storage layout. The [procedures](stand-procedures.md) are Q input, outside the implementation input M. Publication is not execution, a passed stage or permission to generate.

## Inventory

| Id | Norm | Observable subject | Required qualified binding |
|---|---|---|---|
| RUN-G01 | P/03.2-R192/R215/R226/R227; P/03.3-R033 | Restart rechecks admission after stopping the old revision. | Ordinary reconciliation, delayed subsystem stop and actual start observer |
| RUN-G02 | P/03.4-R022/R023; P/03.2-R030/R174/R175 | Worker-table writes/deletes require the live own slot, independently of target CAS. | SDK table operations, store request/commit history and ownership intervention |
| RUN-L01 | common log-mask, Function/rule and Where it applies; url-credentials, field rule | The process log masks the union of loaded manifest secret names. | Actual loaded catalogue, subsystem diagnostics and all process log sinks |
| RUN-M01 | P/02.3-R040/R042/R043/R046; worker lifecycle | Startup reads the manifest row and mark and distinguishes silence from confirmed absence. | Ordinary startup, controlled store reads and admission/exit observer |
| RUN-M02 | P/02.3-R054/R072/R075 | A lagging manifest mark is awaited; a changed or malformed mark has its own outcome. | Running process, controlled mark reads and stop/exit history |
| RUN-N01 | worker lifecycle, Signals and readiness; P/03.3 N1.2 watchdog | READY and WATCHDOG reach the supervisor on the prescribed path. | Ordinary process launch, notification receiver and loop/stand-in observation |
| RUN-T01 | P/03.4 N1.7; P/03.7-R081/R082/R083/R086; role-certificate | Installed kits select the TLS door and enforce peer admission. | Actual process door, owned kits, trusted/invalid peers and request execution observer |
| RUN-I01 | store-client, Production obligations and unavailable; production-obligations | Retries share one logical budget and respect Retry-After. | Actual worker/store transport, external attempt timestamps and declared retry budget |
| RUN-S01 | P/03.5-R026/R035 | Long-lived worker unit state retains envelopes; clear values belong only to recipients. | Qualified state ownership/lifetime observer and ordinary open/restart path |
| RUN-R01 | P/03.3-R024/R025/R028 | Stable work resets the operational retry count and stalled state. | Subsystem failure/stable controls, monotonic clock and retry/heartbeat observations |
| RUN-G03 | P/03.2-R051 | An effective place with unreadable former heartbeat is not taken by following its name. | Ordinary place acquisition, controlled rows and write observer |
| RUN-F01 | P/03.6-R079/R151 | Filing supplies group/about and a later move refuses before perform. | Actual SDK filing, target manifest/unit and request/perform observer |
| RUN-O01 | P/03.6-R182/R183; row-check edit R1–R3 | Extension validates changed fields before a write. | Ordinary row order, admissible target descriptor and store history |
| RUN-C01 | P/03.4-R069/R071 | The first confirmed replay counts once; late counts are cumulative. | Ordinary holder, response loss after commit and heartbeat/outcome history |
| RUN-E01 | P/03.6-R058/R062/R064/R070 | A suppression window starts with its first written line. | Ordinary journal sink, qualified write failure/delay, monotonic clock and journal reader |
| RUN-D01 | P/03.7-R053/R058/R113; secret-files | Immediate in-memory promotion and sequential retained-file publication. | Ordinary token consumer, publication scheduler and independent reopen/decrypt observer |
| RUN-G04 | P/03.4-R034/R200 | The slot hand-over uses its own confirmation clock through all stop stages. | Ordinary SIGTERM path, independently timed slot/place/epoch sends and delayed post-stop I/O |
| RUN-C02 | P/03.6-R155/R159/R162/R163/R164/R165/R167/R168/R169/R170/R171/R172 | Unknown is timed from actual perform; timeout does not complete the callback. | Actual perform entry/return, dispatch scheduler and outcome/store observer |
| RUN-D02 | P/03.7-R011/R033/R074/R077/R080/R101 | Domain worker publishes kept/carried-book results and serves door.pass. | Owned teaching manifest/consumer, holder store and actual domain process/door |
| RUN-D03 | P/03.7-R107; token-cache day | Same-jti revoked cooldown follows the worker's UTC day. | Ordinary token requester, local wall clock, agent and receiver request observer |
| RUN-I02 | P/03.4-R059; P/03.2 N4; store-client | Store errors include actual failed attempts on startup, watch and door paths. | Controlled store boundary, independently correlated attempts and heartbeat deltas |
| RUN-C03 | P/03.4-R072/R073/R074/R077/R078 | Request histograms and made_rows reflect actual observations/listings. | Request event clock/history, heartbeat reader and controlled listing boundary |
| RUN-S02 | P/03.4-R100; sealing, Reseal a value | List-form worker tables seal on write and reseal at startup under the slot. | Ordinary table/startup path, controlled CAS/ownership and independent envelope reader |

## Qualification and evidence

Each slice needs a qualified binding to the implementation's ordinary worker/SDK path and its dependencies, plus independent observations. A standalone policy machine, pure vector, helper or prepared expected result does not establish that connection. Native call shape and internal instrumentation may vary; use the implementation's declared binding and prove that it reaches the same operational path. This does not require a new public flag, door, callback, module observer or state layout. State lifetime observations in RUN-S01 require an ownership proof, not a whole-process plaintext scan.

Use fresh isolated current-format data and replay memory, ordinary OS identity and declared layout. Use only stand-owned synthetic values, credentials and cryptographic material. Privileged preparation belongs to operations. Preserve exact implementation/input and provider commits, commands, sanitized environment, effective finite budgets, preparation, timed external events, before/after row versions and per-slice results. Keep secret-free fingerprints and boolean canary matches; do not publish tokens, opened values or keys. Distinguish candidate exits and normative outcomes from the stand's deadline.

Qualify the positive and discriminating negative controls before scoring and retain activation evidence. Missing suppliers, clocks, budgets, ownership observations or qualified bindings leave only the dependent slice **NotExecuted**, with the missing item named. An attempted nondiscriminating control is a stand failure. Neither outcome is PASS or a candidate refusal. An observed violation is a candidate failure against the cited existing norm. Partial coverage does not close a whole record. Executors and observers remain qualification debt until supplied and qualified.

## Relation to J

The existing [seam contracts](../forms/README.md), [reconcile/retry seams](../acceptance/3/seams.tsv), [slot seams](../acceptance/2/seams.tsv), [stop seams](../acceptance/1/seams.tsv), [holder seams](../acceptance/6/seams.tsv), policy machines and common vectors remain J. They check their declared scope. They do not supply delayed restart admission, independent confirmation clocks, operational journal/file publication, systemd/TLS wiring or a qualified domain consumer. These Q records add no CALL fields, event words, J directives or functional gates; they do not turn a pure policy result into process evidence.
