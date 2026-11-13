# P/06 forms and console seams

This English text is the source; `ru/forms/README.md` is its Russian translation for people, not in the export. Forms express the existing norms.

## Catalogue-bound HTTP contract

The [OpenAPI](../spec/06-console.api.openapi.yaml) declares the catalogue-dependent PathItems as the standard `components.pathItems` below. Their bindings use only the loaded catalogue already accepted by the [P/02 loader](../../02-installer/spec/02.1-installer.norms.md) and served at [process start](../../02-installer/spec/02.3-installer.norms.md). Component names, proof maps and example values of `servers` do not admit a route or a subsystem.

| Standard PathItem | Existing catalogue source |
|---|---|
| `UnitsCollection`, `UnitItem` | `unit.rows` of the chosen subsystem |
| `TableCollection`, `TableItem` | each declared entry of `tables` of that subsystem, with its existing field and service rules |
| `PassRoot` | the existing `door.pass` list or its `routes`; retain its kind and the declared `wait`, `stream`, `calls` and `refusals` |
| `ConsoleFile` | each complete literal name in `console.files`, including every path segment |

Specialize each applicable component for those actual catalogue entries: short routes only for the selected `CONSOLE_ROOT`, and explicitly named subsystem routes for the root and mounted subsystems. A file has only its existing explicitly named subsystem route. A component alone is not a reachable door. Use the existing catalogue, not an additional binding file, proof map or new input grammar.

A specialization removes only `in: path` parameters already replaced with catalogue literals, at both PathItem and operation levels. Keep every remaining parameter and its decoding, headers, query, body, requiredness, response, security condition and reference base. A literal subsystem is present in the path once: use the existing origin context without adding the same subsystem again through `servers`. Neither a server-variable example nor a parameter name chooses a catalogue class. The logical operation keeps its source provenance and adapter identity; a changed traversal order does not rename it.

`ConsoleFile` matches the whole declared finite filename. `PassRoot` keeps the existing admitted prefix and unbounded raw remainder and query, for both kinds of pass; this remainder is not a one-segment OpenAPI parameter. The existing `door.routes` route/id remainder and the domain-at operations remain owned by their current procedures, even when a parameter is called `rows`. Path priority, method selection, ambiguity, no fallback, refusal order, rights and all existing limits remain unchanged. This representation does not add an operation, URI, alias, permission or runtime option.

## Inputs and constants

[daemon-flags.tsv](daemon-flags.tsv) is the P/01 header `flag type default default_text required commands bad norm`. `$NAME` is environment, not a CLI flag. The process is console. `cleanup-window` is only the logical invocation name of the implementation-chosen sweep command; its actual executable/name remains P/06.1 Implementation decides. The sole CLI flag here is its existing `--writers-stopped`. Parsed fields do not waive catalogue, kit, role, server/box, alias, ring-placement, timezone or active-listener checks from the cited contracts. Inactive callback configuration and an unreadable configured ring are judged at their normative activation/operation, not relabelled as new startup failures. Malformed CLUSTERS is operation-unreadable, not an empty list or a new startup refusal.

`$INSTANCE_ID` is the existing common instance override: absent or empty selects the ordinary box/pid/random resolver; a supplied nonempty value is accepted or refused by the instance contract and preserved byte for byte. It is environment, with no new CLI flag or new configuration rule.

[runtime-constants.tsv](runtime-constants.tsv) is the numeric source of its 34 declared constants. Header is `name value unit norm meaning`, literal TAB. Name is unique `[A-Z][A-Z0-9_]*`; value is a positive JSON integer, no quotes; unit is `count|s|bytes`; norm is an existing req anchor of its owning chapter; meaning is text. No expression language or new environment knob is introduced. The cited procedure owns dependent formulas and conditional use: in particular OPS_KEEP cannot undercut the subsystem acceptance-memory term. These literals may be emitted with core; they do not declare a wholly generated stage.

The numeric source of each folder bound is its row of `runtime-constants.tsv`. JSON Schema is a second machine carrier with the same value, not an independent default. The equality is a `check_spec` obligation; prose and dependent formulas refer to the row name.

| Source row | Second carrier JSON pointer |
|---|---|
| `FOLDERS_MEMBERS_MAX` | `data/folders.schema.json#/$defs/writer/properties/members/maxItems` |
| `FOLDERS_PER_UNIT_MAX` | `data/memberof.schema.json#/$defs/writer/properties/folders/maxItems` |

`AT_ROUTE_WAIT` and the local `FORWARD_WAIT` apply only to P/06.7 N1.6. Other forwarding waits and `FORWARD_MAX` remain declared by the [forwarding contract](../../common/contracts/forwarding.md); `PASS_WAIT`, `GLASS_SESSION` and `GLASS_SESSIONS_MAX` remain declared by the [gate-and-pass contract](../../common/contracts/gate-and-pass.md). These references do not copy foreign constants into this form.


The same existing subject check must compare FOLDER_NAME_MAX with `data/folders.schema.json#/properties/name/x-max-bytes` as UTF-8 bytes, CHANGES_HISTORY with `spec/06-console.api.openapi.yaml#/components/schemas/Changes/properties/changes/maxItems`, CHANGES_WAIT with the GET and HEAD `/changes` wait maximum, VERIFY_UNITS_MAX with `VerifyInput.need.units.maxItems`, and SWEEP_LIMIT with `data/sweep.schema.json#/$defs/writer/properties/digests/maxItems` and the effective root reader reference. Folder/memberof root reader references retain the two existing equalities above.

CLAIM_TAKEOVER_AFTER, DONE_ANSWER_KEEP, SWEEP_GRACE, SWEEP_MARK_EVERY, DOOR_TOKEN_TTL and OPS_CONTROL_RETRIES have distinct meanings even when another clock/size has the same value. OPS_CONTROL_RETRIES counts retries after the original pass. The four defining TTL/formula lines of the common door-token contract cite the same DOOR_TOKEN_TTL.

## Numeric loader supplement

`numeric-loader.cases.tsv` (judge-only: checking material outside M) is the separate P06 C3 loader set, not part of the947 P02 corpus or220 canonical cases. Header is `case input expect relation norm`, literal TAB; input is an exact existing YAML file relative to this forms directory. For each of the9 rows call the existing P02.1 N2 `load(bytes,file)` with the input's unchanged UTF-8 bytes and actual source path. This is the same loader entry as the corpus, no new native command/class/role. The input contains no expected result; the roster supplies only the judge. `ok` requires a manifest; `refused:relations` requires the existing relations refusal, with the listed relation as sole cause. The set is4 refused/5 ok; worker.deletes numeric is refused even with fixed protection, whereas protected numeric retire/ends and named neighbors load. The separate strict supplemental binding applies to rows160–162. Source-loader execution does not prove installer, worker, physical deletion, native or SUT execution.

## Console localization

[`localization.tsv`](../../07-console-module/data/localization.tsv) has the header `key en ru`, literal TAB,519 unique existing W leaf names and equal substitution parameters in each locale. A nested W path uses its qualified caption key (`n.late`, `kinds.server.decommission_requested`); event-name dots in kinds remain literal, not protocol renaming. The ru column alone may contain Cyrillic; en is the default, ru requires explicit opts.lang. Subject captions and every protocol/data value are unchanged by that choice. The frozen W object repeats `glass` in each locale; this table preserves the actual last-value semantics without changing a key or the published bytes. This table does not execute UI behavior.

## Refusals

[refusals.tsv](refusals.tsv) uses `chapter row name surface code kind fields headers log norm word response_schema cause outcome diagnostic caller`. It holds the 204 refusal rows of N4 of the chapters and the 14 imported gate rows (6.3), as 279 projections. A row carries the cells cause/outcome/diagnostic/caller of its refusal; a row of chapter 6.7 carries the cells word/outcome/cause, with diagnostic/caller `-`. Row is unique within a source chapter condition, projections repeat it; source alternatives apply under their N4 conditions. A response schema alternative is not an arbitrary choice at an operation. Success rows and abstract load/procedure outcomes stay in the catalogue and do not become new errors.

HTTP bodies name their actual lesson components; no Fault.kind is invented. `fields` names required properties declared directly by that component; inherited/composed requirements, optional/conditional fields, error words, dynamic headers and logging stay in the complete OpenAPI schema and the N4 source cells. `response_schema=-` denotes no own JSON body; a peer row retains the imported owner’s form. The closed error words are also in [data/refusal-words.tsv](../data/refusal-words.tsv). RevisionMoved in components/schemas also defines the response schema of components/responses/RevisionMoved; the public response is components/responses/RevisionMoved.

## Seams and stages

Chapter acceptance directories keep all their scenarios and README obligations. Their seams use the CALL/JSON grammar of [P/03](../../03-worker/forms/README.md) and [P/02](../../02-installer/forms/README.md). Each CALL takes one JSON input and returns one native JSON value; recursive object subset, exact arrays and empty objects. Ports normalize observations of real console code, not a private API that implementations must adopt. Never return a case’s expected object. A panic, unrelated error or unexecuted call fails.

Each scenario has a new temporary root and valid catalogue, rows, identity, permissions and limits before its named intervention. Unspecified input means a valid neutral background, not an unconfirmed read. Fixture words select setup and controlled dependency outcomes, not precomputed function results. Existing version/cas values are real schema-valid versions. Use regular crypto for readable keys/tickets/cookies/envelopes and real transaction guards. Counters measure actual calls, writes, bytes and deletion effects. A controlled store/transport may inject the named I/O result/race, while the console decision code is the ordinary implementation. No fake run or canned success substitutes for it.

| CALL port | Intervention and observation |
|---|---|
| `console-repeat` | Run the regular keyed write path over real pending/done claim rows; compare target writes after the retry, excluding claim/diagnostic writes. Bodies differ only at one valid customer field. For the POST continuation cases, perform the first real target write over the declared tombstone or absent row, lose its reply and stop before done; observe the unchanged pending version for 30 s and take it with another console. Read intended revision/born through the implementation's real claim codec, not a newly required public claim schema. A late old executor uses its former guard. For unknown planning-save outcome, no target call occurs before a confirmed owned reread; compare actual target bytes to the saved intent. |
| `console-next-id` | Invoke real numeric recovery with an unreadable counter and controlled list outcomes; issue no id until the full history is confirmed. |
| `console-body-window` | Invoke the implementation-chosen maintenance command/entry point with its actual acknowledgement flag. Use real objects, list versions and controlled monotonic time. Inject list CAS rejection before the first deletion; count actual unlinks. |
| `console-secret-edit` | Use a valid manifest with address credentials and password_secret; valid old envelopes are made/opened by the regular crypto code on a temporary ring. Count actual target/done-claim writes. The fixture password is test data; scan the actual refusal for it. |
| `console-gate` | Read domain facts through a controlled store and run the ordinary gate for a valid harmless GET. Readable keys and glass cookies are created/verified by regular code. Keys absent and keys unreadable are different facts. Count actual handler calls and business writes. |
| `console-request` | Submit a complete valid ordinary request with fresh valid rid/digest and a readable existing unit; only the accounting read is unconfirmed. |
| `console-request-reaper` | Run the regular append reaper. The unit, TTL and append shape are valid unless explicitly made unknown. Controlled clocks establish the published age of this unchanged request. No mark/fetched exists initially; settle has not elapsed at first publication. |
| `console-where-memory` | Use a valid unit/place/holder. A prior confirmed fixture really feeds the ordinary observer once before I/O becomes unconfirmed; a fresh observer has no such memory. No unconfirmed read becomes an absent row. |
| `console-shell` | Request the actual mounted shell route in on mode. The shell bytes and manifest are valid; only proof of identity is absent. Inspect status, Location and actual body length. |
| `console-pass` | Call the regular second-kind pass to a valid live worker route. A controlled transport times out before headers; successful_headers_sent records the actual write of success headers. |
| `console-schema-raise` | Use the actual schema-raise procedure under a valid administrative identity and confirmed listings. Unknown live build and an unconfirmed schema read are distinct interventions. |
| `console-decommission` | A known server and confirmed facts, but its resource has never been heard. Run the real decommission path without gone confirmation; count writes of its decommission marker. |
| `console-labels` | Run PUT labels with a valid server, key, revision and identity; the only invalid input is the repeated label. |
| `console-forward` | Run regular routing with a valid request and proof of identity. section_absent denotes an incomplete member copy, so the published CLUSTERS fallback is needed. Count real outgoing calls; the listed refusals happen before them. |
| `console-forward-credentials` | Execute the first cluster-console forwarding hop, transition 1 or 2, after the ordinary gate. The fixture/observations are [the forwarding seam protocol](../../10-domain-console/acceptance/README.md#forwarding-credential-seams). |
| `console-callback` | Create a real valid person ticket with the declared calls entry. Match the actual requested method/path through the ordinary callback admission code; a suffix is not the exact book door. |
| `console-folder-create` | POST a root folder through the ordinary path with the given UTF-8 name, no members and a valid new key. Count actual folder rows. |
| `console-folder-batch` | Use a valid folder tree and member row. For the ancestor race change a confirmed ancestor after read and before the real atomic batch. For key length choose a valid member whose composed membership key exceeds the configured store limit by exactly one byte. |
| `console-op-round` | Use an unfinished nonexpired operation with an accepted key and live author token. Only revocation/disabled reads are unconfirmed. Run the actual round and observe cancellation writes. |
| `console-op-step` | Feed the real leader a malformed next-step row under a current turn. Its predecessor is confirmed ok; backend_calls counts actual attempts to call the subsystem. |
| `console-op-step-batch` | Use a complete valid step batch and ticket. Change the turn after preparation before atomic commit, or expire only the ticket. Read all target, outcome and counter rows after the actual refusal. |

[stages.tsv](stages.tsv) has 11 stages, all kit `-`, with 67 CALL scenario rows across nine chapters. The gates are aids, not full acceptance. Every own/common vector assignment and additional probe/reading remains required. The 77 requests-body HTTP rows and 21 accepted-json round trips require the real store+console judge; native worker 52 does not replace console 77. The runner target P/06/vectors-requests-body is this HTTP obligation; no pure native console command or kit function PASS is invented. Late domain process tests need the actual neighbours 08–10 and cannot be closed by unit fixtures.

The cases use only these same ports. Build the state a case names as real rows: the pending claim, any saved reservation or intended revision/born, and a valid target row. Observe the unchanged pending for the declared eligibility interval and take it by the normal CAS path. No input bypasses the normal claim codec, gate or ownership.

For the unit-delete cases, run a real unit-delete batch with a readable valid one-folder membership and valid current rights/CAS/guards. `writes[0]` deletes U, `writes[1]` is the explicit folder when supplied, and `writes[2]` is the explicit membership when supplied. Counters observe actual target unit/folder/memberof mutations after setup, excluding setup/claim/journal from those named counters only. unique_target_keys inspects the real emitted target batch. Current auxiliary/gone effects, admission, full size accounting and atomicity still apply. The adapter is never passed expected results.

## Computed TLS default

For W2C_TLS_DIR unset, execute the common environment resolver under a Linux profile and a macOS profile: /etc/w2c/tls versus <W2C_BOX>/tls. A supplied path is used verbatim and Given remains true; omission remains Given=false even after resolution. daemon-flags default=- means computed, never the literal string "-" or an unconditional Linux path. These are resolver/start checks, not new flags or an edit of the common env-file contract. VerifyUnavailable is the own verify503 form only; all other ConsoleRefusal properties remain unchanged.
