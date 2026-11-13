# Platform vectors (ADR-0083)

This English text is the source; the Russian translation `ru/vectors/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A package of algorithms common to the micromodules: input → expected output. Each micromodule implements the algorithm itself and passes the
vectors. The bytes are written by «Specification»; the conformance of the product is by its acceptance against these tables (ADR-0080 addendum 16, ADR-0083;
«Parity» is removed). The owner is the lesson that introduces the algorithm first (the module note, «Vectors»).

The course owns its specification data independently of the product; historical product references below do not require synchronization (ADR-0083 addendum (115)).

The parity tables of stage A lay in `Source/tests/testdata/`; at stage B they moved into the directory of the owner lesson,
`NN-<process>/vectors/<algorithm>/`, together with the lesson (lesson 6 — `fault`, `group_of`, `rid`, `requests_body`, `secret_in`,
`log_mask`, `platform_lists`; with them `canonical_json` — in P/01; the former files are removed), and the product switched the paths once. The common vectors lie here.

The machine-readable consumer registry is [`consumers.tsv`](consumers.tsv): one row per `(package, table, lesson)`, with the norm that assigns the computation. Package names are `common/<name>`, table names are file names, and lessons are the directory names of `Platform/lessons.tsv`. The registry covers every table in the common packages and adds no new consumer. The package README still selects the rows, operations, directions and output fields performed by that consumer; an assignment is not permission to execute foreign rows. The published byte module `07-console-module` performs none of these functions. The native outcome and the unified command envelope remain those of the package README and the common acceptance README; a masked log line is a JSON string, not bare stdout text.


| Vector | Where now | Owner (stage A) | Norm |
|---|---|---|---|
| JCS | [`common/vectors/jcs/`](jcs/) | P/01 | [JCS contract](../contracts/jcs.md), RFC 8785 |
| the dictionary `fault` of door refusals | [`common/vectors/fault/`](fault/) | P/06.1 | the doors of P/06 (chapters 6.1, 6.5, 6.6) |
| `cut_at: host` | [`common/vectors/group-of/`](group-of/) | P/04 | P/04 N1.3 `group_by` |
| `rid` | [`06-console/vectors/rid/`](../../06-console/vectors/rid/) | P/06.4 | P/06.4 N1.5 |
| serialization of the request body | [`06-console/vectors/requests-body/`](../../06-console/vectors/requests-body/) | P/06.4 | P/06.4 N1.5, ADR-0072 |
| digest of a request | [`06-console/vectors/request-digest/`](../../06-console/vectors/request-digest/) | P/06.4 | P/06.4 N1.5 `digest` |
| secrets in an address | [`common/vectors/secret-in/`](secret-in/) | P/06.2 | the address contract `url-credentials` (P/06.2 N1.1a) |
| log mask | [`common/vectors/log-mask/`](log-mask/) | P/06.2 | the log mask contract `log-mask` (P/06.2 N1.4; C06-LOG-MASK-33-01) |
| secret rows of the platform | [`02-installer/vectors/platform-lists/`](../../02-installer/vectors/platform-lists/) | P/02.5 | P/02.5 N1.3, P/02.5 N1.4 |
| the manifest corpus | [`02-installer/acceptance/1/`](../../02-installer/acceptance/1/) (`cases/`, `verdicts.tsv`, `classes.tsv`, `diagnostics.tsv`); the former `spec_verdicts.tsv` and `spec_verdicts/` are read by the frozen witness, not a vector | P/02.1 | P/02.1 N1, N4, N5 |
| the rights evaluator (literal patterns, prefix, negation) | [`common/vectors/rights-evaluator/`](rights-evaluator/) | P/01.2 | [rights-evaluator contract](../contracts/rights-evaluator.md) |
| a copy of the store | [`01-store/acceptance/3/inputs/`](../../01-store/acceptance/3/inputs/) | P/01.3 | P/01.3 N1.3 `copy` |
| derivation of rights from the manifest (by meaning) | [`02-installer/acceptance/5/variants/`](../../02-installer/acceptance/5/variants/) | P/02.5 | P/02.5 N1.4, N3 |
| text forms of values (`values_by_type`) | [`common/vectors/values-by-type/`](values-by-type/) | P/06.1 | the row check contract «Unit row» (P/06.1 N1.2) |
| the common row check | [`common/vectors/row-check/`](row-check/) | P/06.1 | the row check contract (W03-E07) |
| the label alphabet | [`common/vectors/labels/`](labels/) | P/06 | the label alphabet contract (L01–L03) |
| a line of the environment file | [`common/vectors/env-file/`](env-file/) | P/02.4 | the environment file contract (C04-ENV-01) |
| password hash | [`common/vectors/password-hash/`](password-hash/) | P/08.4 | the password hash contract (GP-G06) |
| event id | no vectors — a form norm; a package candidate — after lesson 5 | P/05 | [the event journal contract](../contracts/event-journal.md) `id` |
| the founding of the domain: the recovery file, the book acceptance key, term record 1 | [`domain-founding/`](domain-founding/README.md) | P/08 (chapters 8.2, 8.8) | [the domain founding contract](../contracts/domain-founding.md); finding I02-FOUND |
| the domain backup copy key: HMAC-SHA256 of root_key and backup_key_rev | [`domain-backup-key/`](domain-backup-key/README.md) | P/08 (chapter 8.8) | [the domain backup copy key contract](../contracts/domain-backup-key.md); stage C guess I02-BACKUP-HMAC |
| the journal bucket: a torn tail and a wrong line, times by the codec, the years of the bucket; the names `%h<sha256>` and `.name` | [`journal/`](journal/README.md) | common (the event journal contract) | [the event journal contract](../contracts/event-journal.md) `bucket` (`torn`, `years`), `line`, «File names in shared trees»; stage C guesses EJ-G03, EJ-G04, EJ-G06, EJ-G07 |
| address parsing | in part — the packages `secret-in`, `group-of`, `row-check`; there is no separate package | P/06.2 | the address contract, P/02.1 N1.2a `schemes` |
| the envelope `enc:v2`, the AAD path, opening, the ring file | [`sealing/`](sealing/README.md) | common | [the sealing contract](../contracts/sealing.md) |
| freshness: the age of the observed version → fresh (`≤ LOST_AFTER`) | [`fresh-age/`](fresh-age/README.md) | common (the observation contract) | [the observation contract](../contracts/observation.md) «Freshness»; P/04 N3, chapters 6.1, 6.4, 6.5, 6.6 (review analysis of stage B 6–7, № 20) |
| the state of a resource by the observation history (`resource_state`, non-answer and absence) | [`resource-state/`](resource-state/README.md) | common (the observation contract) | [the observation contract](../contracts/observation.md) «Observation of a version», «Resource state» (OBS-001) |
| the merge of the event journal (console and worker: duplicates, `cut`, epochs, `unknown`, completeness) | [`events-merge/`](events-merge/README.md) | P/06.4 (participant — the worker) | [the event journal merge contract](../contracts/events-merge.md) (ADR-0091 addendum (21)) |
| reading the heartbeat of a resource and a worker by the form and outcomes of the family | [`heartbeat-read/`](heartbeat-read/README.md) | common (the observation contract) | [the observation contract](../contracts/observation.md) «Form» (C04-DEP-OBS-HEARTBEAT-01, C08-HEARTBEAT-READER-99-VECTORS) |
| the reaper over an append request: the marks `gone` and `expired`, `settle`, no removal by `ttl` alone | [`06-console/vectors/reap/`](../../06-console/vectors/reap/README.md) | P/06.4 | the contract of the request and its mark «States…» (C06-GONE-FETCHED-33-01) |
| the key of the step batch and the expected version of the step | [`06-console/vectors/op-step/`](../../06-console/vectors/op-step/README.md) | P/06.9 | P/06.9 N1.4, N2 «Step batch» (ADR-0095) |
| the manifest series `metrics[]` on `/metrics` | [`06-console/vectors/metrics/`](../../06-console/vectors/metrics/README.md) | P/06.5 | P/06.5 N3 «Manifest series metrics[]» (C06-METRICS-DSL-33-01) |
| the record of the sent deadline `valid_until` | [`deadline/`](deadline/README.md) | P/06.4 (the request contract) | the contract of the request and its mark «Request» `valid_until` (C47-DEADLINE-VECTORS-01) |
| the pool, the place keeper, `idle_by_policy`, `placeable` | [`pool/`](pool/README.md) | P/04 (participant — the console P/06.5) | [the pool contract](../contracts/pool.md) (C06-SERVER-POLICY-33-01) |
| the slot name: the slot order, the next number, the process number of a role | [`slot-name/`](slot-name/README.md) | P/03.2 | [the slot name contract](../contracts/slot-name.md) (POOL-ORDER-51-01) |
| holding a bucket by a hold row: the declaration, the row, the bucket span → `held` \| `not_held` \| `unknown` | [`holds/`](holds/README.md) | P/06.4 (performed by the resource P/05) | [the holds contract](../contracts/holds.md) (ADR-0083 addendum (37) item 5) |
| the effective hold of a place | [`hold-state/`](hold-state/README.md) | common (the observation contract) | [the observation contract](../contracts/observation.md) «Hold of a place» (C06-WHERE-PLACE-HOLD-33-01) |
| the judgement of a slot row | [`slot/`](slot/README.md) | P/03.2 | [the slot contract](../contracts/slot.md) (C140-SLOT-TIME-01) |
| the writer turn: sequences over the turn row | [`turn/`](turn/README.md) | P/04 | [the writer turn contract](../contracts/turn.md) (C08-TURN-SELF-99) |
| the object store client: the address, the read outcome | [`object-client/`](object-client/README.md) | P/05 | [the object store client contract](../contracts/object-client.md) (C10-OBJECT-ADDRESS-32) |
| the schema check at start | [`schema/`](schema/README.md) | P/06.6 | [the schema contract](../contracts/schema.md) (C06-SCHEMA-WIDE-32-01) |
| the process instance: a given `INSTANCE_ID` | [`instance/`](instance/README.md) | P/03.2 | [the process instance contract](../contracts/instance.md) (INSTANCE54-02) |
| the trust set of a role door and the leaf check | [`trust-set/`](trust-set/README.md) | P/10 (the role certificate contract, class `role`) | [the role certificate contract](../contracts/role-certificate.md) «The server side: the class `role`» (C10-SDK-ROLE83) |
| the alarm history: equality of rows, a repeat in a page, the holder's record | [`alarm-history/`](alarm-history/README.md) | P/08.9 (participant — the domain console P/10) | [the alarm history contract](../contracts/alarm-history.md) (C10-ALARM-SAME-LINE83) |
| the outcome of a store answer for the client | [`store-client/`](store-client/README.md) | P/01.1 | [the store client contract](../contracts/store-client.md) (SC-WIRE78-G01) |
| the tombstone: neighbours, confirmations, removal | [`tombstone/`](tombstone/README.md) | P/05 (participant — the console P/06.1) | [the tombstone contract](../contracts/tombstone.md) (C06-BLOB-GC-33-01) |
| the freshness of a contender mark: age → fresh (`≤ CONTENDER_FRESH`) | [`contender-fresh/`](contender-fresh/README.md) | common (the observation contract) | [the observation contract](../contracts/observation.md) «Freshness of a contender mark» (C06-CONTENDER-FRESH-33-01) |
| SaidID: the name of a request in `fetched` and its reading | [`said-id/`](said-id/README.md) | P/03.4 (participant 6.4) | [P/03.4](../../03-worker/spec/03.4-worker.norms.md) N1.1 `said_id` |
| the door token `door1`: issue (JCS, Ed25519) and the check at the holder by `door/keys` | [`door-token/`](door-token/README.md) | P/06.5 (participant 3.4) | [the door token contract](../contracts/door-token.md); P/06.5-05, P/03.4-08 |
| «accept by a console» | no vectors — the acceptance steps of [chapter 6.7](../../06-console/acceptance/7/README.md) (sc. 01, 02) | P/06 | [the forwarding contract](../contracts/forwarding.md) «Accept by a console» |
| the domain envelopes `x25519:v1` and `m1`: opening and the round (`seal`, `seal-round`, `seal-member`, `seal-member-round` of the acceptance of M11) | [`domain-envelopes/`](domain-envelopes/README.md) | common (owner P/08, chapters 8.2, 8.3) | [the domain envelopes contract](../contracts/domain-envelopes.md); review analysis of stage A 8–10, № 12 |
| the agent signature `X-Agent-Signature`: the check `agent-sig` (windows, bytes, forms) | [`agent-sig/`](agent-sig/README.md) | common (owner P/09, chapter 9.1) | [the agent signature contract](../contracts/agent-signature.md); review analysis of stage A 8–10, № 13 |
| the domain key set: the function `keys` | [`keys/`](keys/README.md) | common (owner P/08, chapter 8.2) | [the domain key set contract](../contracts/keys.md); review analysis of stage A 8–10, № 13 |
| the term record and the issuer's signature: the function `record` | [`record/`](record/README.md) | common (owner P/08, chapter 8.8) | [the term record contract](../contracts/record.md); review analysis of stage A 8–10, № 13 |
| the request signature `X-W2C-*`: the function `ask-sig` | [`ask-sig/`](ask-sig/README.md) | common (owner P/08, chapter 8.8) | [the request signature contract](../contracts/ask-sig.md); review analysis of stage A 8–10, № 13 |
| the intake of a report: the function «accept» (`accept`), the roads | [`accept/`](accept/README.md) | common (owner P/08, chapter 8.3) | [the report intake contract](../contracts/accept.md); review analysis of stage A 8–10, № 13 |
| the revocation file `revoked`: syntax, the serial value, a wrong file | [`revoked/`](revoked/README.md) | common (the role certificate contract) | [the role certificate contract](../contracts/role-certificate.md) `revoke`; stage C guess S01, the Architect's decision 2026-10-23 |
| the revocation file `crl.pem`: a block per centre, the serial range by issuer, the signature, the dates — log and count, defects | [`crl/`](crl/README.md) | common (the role certificate contract) | [the role certificate contract](../contracts/role-certificate.md) `revoke` `crl`; stage C guesses RC-02, S03, RC-05, RC-06 |
| a right by grants: the function `may` | [`may/`](may/README.md) | common (owner P/08, chapter 8.4) | [the right contract](../contracts/may.md); the Architect's decision 2026-10-20, ADR-0083 addendum (14) item 1 |
| a client about a server of another cluster: the function `peer` | [`peer/`](peer/README.md) | common (owner P/09) | [the `peer` contract](../contracts/peer.md); the Architect's decision 2026-10-20, ADR-0083 addendum (14) item 2 |
| the loopback threshold of a client of its own cluster: `{url}` → `loopback` \| `name` \| `ip` | [`loopback/`](loopback/README.md) | common (the role certificate contract) | [the role certificate contract](../contracts/role-certificate.md) «The client of a door of its own cluster» `loopback`; ADR-0075 addendum 2026-10-26 (4) item 1, (5) item 1 |
| the domain token: the function `token` | [`domain-token/`](domain-token/README.md) | common (owner P/08, chapter 8.2) | [the domain token contract](../contracts/domain-token.md); P/08.2-05, -06, -07 |
| the domain view and the shadow report: the function `view` | [`08-domain/vectors/view/`](../../08-domain/vectors/view/README.md) | P/08.1 | [P/08.1](../../08-domain/spec/08.1-domain.norms.md) N1.3–N1.6, N3 |
| the assembly of a book: the function `assemble` | [`08-domain/vectors/assemble/`](../../08-domain/vectors/assemble/README.md) | P/08.5 | [P/08.5](../../08-domain/spec/08.5-domain.norms.md) N1.3, N3 |
| the issue of a worker token: the function `issue` | [`08-domain/vectors/issue/`](../../08-domain/vectors/issue/README.md) | P/08.7 | [P/08.7](../../08-domain/spec/08.7-domain.norms.md) N3 |
| following: the function `follow` | [`09-agent/vectors/follow/`](../../09-agent/vectors/follow/README.md) | P/09.1 | [P/09.1](../../09-agent/spec/09.1-agent.norms.md) N3 «follow» |
| the value at reading: the function `resolve` | [`06-console/vectors/resolve/`](../../06-console/vectors/resolve/README.md) (14 rows; 11 from M11/11 sc. 03) | P/06.7 | [P/06.7](../../06-console/spec/06.7-console.norms.md) N1.14, N3 `resolve` |
| the alarm list: the function `alarms` | [`10-domain-console/vectors/alarms/`](../../10-domain-console/vectors/alarms/README.md) (27 rows; 15 from M11/11 sc. 04; 17–27 — the coverage audit of Gemini P/10) | P/10 | [P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.8, N3 `alarms` |
| the shortage of a label set and the order by servers (`in_flight`, `per`, candidates, the share-out) | [`04-controller/vectors/order/`](../../04-controller/vectors/order/) | P/04 | P/04 N3 «shortage(), order()»; ADR-0084 addendum (1)–(3) |
| the shrink victim | [`04-controller/vectors/shrink-victim/`](../../04-controller/vectors/shrink-victim/) | P/04 | P/04 N3 «shrink()», R4, R22 |
| whether shrinking is allowed: the condition and the order of the refusal reasons (the victim, live ones without a place while some wait, the hold-off, in flight, hysteresis) | [`04-controller/vectors/shrink-allowed/`](../../04-controller/vectors/shrink-allowed/) | P/04 | P/04 N3 «shrink (step 9a)», the condition; R3, R13′, R16′, R16‴, R22, R28 (the Architect's decision 2026-10-20, № 12 of the review analysis of stage B 3–5) |
| the command line `exec` → argv | [`02-installer/vectors/exec/`](../../02-installer/vectors/exec/) | P/02.1 | P/02.1 `execLine`; ADR-0091 addendum (4)–(6) |
| the count `room` and `live` of the presence locks | [`presence-room/`](presence-room/README.md) | common (the presence lock contract) | [the presence lock contract](../contracts/presence-lock.md) «Count `room`»; PL-EXT-01 |
| a request to free a place: the computation `relieve` with the answer `freeing` | [`05-resource/vectors/relieve/`](../../05-resource/vectors/relieve/) | P/05 | P/05 N1.4 `free_ask`, N3 `relieve`; the VMS freeing query |
| the order of the first installation of the manifests | [`02-installer/vectors/install-order/`](../../02-installer/vectors/install-order/) | P/02.4 | P/02.4 N1.7 `order`; I02-INSTALL-ORDER |
| the workers script by the order (what to start, what to stop) | [`02-installer/vectors/workers-script/`](../../02-installer/vectors/workers-script/) | P/02.4 | P/02.4 N1.5 rules 2–4 |
| the order of label sets over a shared capacity | [`04-controller/vectors/order/`](../../04-controller/vectors/order/) — the cases `two-sets-*` (a set takes up to its own need, the remainder to the next) | P/04 | P/04 N3 «set order» |
| the removal of an order by its term, a number above want, shrinking by the hold-off, the trial process at `distinct` | by an acceptance step — [P/04](../../04-controller/acceptance/README.md) sc. 14–17 | P/04 | P/04 N3; ADR-0084 |
| `YIELD_SAME_TERM`, `SET_GUARD` (the follow set) | by an acceptance step — [P/08.8](../../08-domain/acceptance/8/README.md) sc. 09; the input of `follow` does not carry answer sets | P/08.8 | [P/08.8](../../08-domain/spec/08.8-domain.norms.md) N1.6 `yields`; [P/09.1](../../09-agent/spec/09.1-agent.norms.md) N3 «follow» 1a |
| `put_at` by index before the confirmation of the turn, the CAS of its own turn row (G6, T6) | by reading — the stand does not stop the process between steps | P/08.10 | [P/08.10](../../08-domain/spec/08.10-domain.norms.md) N1.7, N3 «the turn of the domain process» |

The M11 vectors are the former inputs of the stand commands of their lessons; all of them are packages now (lesson 8 — the packages `view`, `assemble`, `issue`
of the lesson and the common packages above, lesson 9 — the package `follow`, lesson 10 — `resolve` of chapter 6.7 and `alarms` of lesson P/10; their scenarios and
inputs in the acceptance of M11 are removed by the moves). The rows «no vectors»
are algorithms of the module note that so far have only acceptance steps (review of stage A, Gemini 4.5).

The machine-readable wire bindings are [`wire.tsv`](wire.tsv), with the closed grammar in [`wire.md`](wire.md). The first slice covers P/01 and P/02 vector tables; missing bindings remain undeclared. The form distinguishes the unified vectors command, existing stand commands and layout checks. The package README keeps algorithm meaning and consumer obligations; wire declarations move into this single form.
