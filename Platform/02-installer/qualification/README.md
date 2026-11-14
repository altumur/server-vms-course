# P/02 qualification records

This English text is the canonical `qualification/README.md`; the Russian text is a derived translation for people, not in the export.

These records check the existing obligations of [P/02.3](../spec/02.3-installer.norms.md) and [P/02.4](../spec/02.4-installer.norms.md). They introduce no command, refusal, candidate interface, timeout or storage layout. Their [procedures](stand-procedures.md) are Q input, outside the implementation input M. They complement J rather than confer a passed stage, system acceptance or permission to generate.

## Inventory

| Id | Norm | Observable subject | Required stand binding |
|---|---|---|---|
| RUN-K01 | P/02.4-R373/R399/R401/R404; secret-files, Production obligations | Concurrent rotations retain every previously acknowledged key and openable value. | External command, publication scheduler and independent ring/envelope reader |
| RUN-K02 | P/02.4-R377/R379/R380 | A damaged current envelope or wrong AAD is left untouched, the walk completes, `seal` exits 1. | Real command/store walk and independent cryptographic oracle |
| RUN-K03 | P/02.4-R373/R399/R401; sealing, Ring file; production-obligations, Finite budgets | A successful writer produces a ring readable by its own ordinary reader. | Command, declared effective file budget and boundary builder |
| RUN-K04 | P/02.4-R374/R402; sealing, no_key | Set-empty and unreadable rings refuse with code 2 before writes; unset is a different state. | Isolated command environment, ring access and write observer |
| RUN-K05 | P/02.4-R389/R396; the walked families' schemas and outcomes | Invalid known rows stay byte for byte with their versions, are unreadable and yield code 1. | Family codec/schema oracle and actual command/store walk |
| RUN-C01 | P/02.4-R170/R173/R360; role-certificate, own_client/own_url | Rollout uses the authenticated TLS console path when a kit exists. | Console TLS peer, request observer and actual rollout command |
| RUN-C02 | P/02.4-R360 | Rollout takes the console address from `w2c.env`. | Isolated environment/file preparation and console request observer |
| RUN-C03 | P/02.4-R113/R157/R173; role-certificate, own_url | Workers address wildcard-bound own consoles by the specified loopback/verification-name pair. | Actual workers command, TLS console and connection/SNI observer |
| RUN-C04 | P/02.4-R157/R176; peer, step 6 | A server leaf with two roles is rejected as `no_role`. | Controlled trusted TLS peer and peer-result observer |
| RUN-W01 | P/02.4-R126/R127 | An unconfirmed stop continues to occupy capacity until reconciliation. | Actual worker passes and service-manager outcome/process observer |
| RUN-T01 | P/02.4-R406/R407/R411 | `tls status` cannot report success when store/heartbeat reading is unconfirmed. | Actual command, admin/heartbeat service and read-only observer |
| RUN-P01 | P/02.4-R137/R475; P/02.1 subName | Mandatory roles keep the underscore of an admissible subsystem name. | Owned catalogue, centre commands and independent leaf/own reader |
| RUN-D01 | P/02.3-R094/R141/R146/R153/R157/R164 | Deletion-profile acceptance covers all procedures and packets of the confirmed catalogue. | Independent catalogue/packet-proof inventory and installation write observer |

## Qualification and evidence

Every record needs a qualified binding to the implementation's ordinary command or process, its dependencies and independent observers. Merely replaying a course model, testing a local helper, parsing a profile or copying an expected result does not qualify the binding. Prepare fresh isolated current-format data and replay memory per slice; use only owned synthetic credentials and values. Keep the normal OS identity and declared layout. Privileged preparation belongs to the operations channel; lack of it does not authorize a fallback that bypasses file modes, groups or TLS.

Before scoring, execute the positive and negative controls of the procedure and prove their activation. Record the exact implementation/input commits, commands, environment with secret values omitted, effective budgets, stand/provider versions, preparation, timed external events, observations and outcome. Retain value hashes, row versions, public certificates and allow/deny results rather than private keys or token material. No record acquires a new numeric deadline: applicable normative deadlines and declared finite I/O budgets govern it. A stand deadline must be distinguished from a candidate response or exit.

A missing command, supplier, observer, declared budget or unqualified control leaves the affected slice **NotExecuted** with the missing binding named; an attempted control that fails to discriminate is a stand failure. It is neither PASS nor a candidate refusal. A proven observed violation is a candidate failure against the cited norm. Other independently qualified slices may report their own outcomes; do not promote a partial result to the whole record. These are published procedures, not evidence that a candidate or any control has run. Their executors and observers remain qualification debt until supplied and qualified.

## Relation to J

The rights variants remain J: `v1-base` observes effective domainagent exclusions, `v17-secret-own-book` the holder row of `secrets.reads`, and `v18-refused-secret-readers-nested` the catalogue-wide nested declaration refusal. They use the existing `variants` engine and no new directive. This Q inventory adds no row to a closed production-probe form and no D7 payload.
