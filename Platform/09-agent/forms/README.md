# P/09 forms and ordinary implementation seams

This English text is the source; ru/forms/README.md is its Russian translation for people, not in the export. The forms express existing norms.

## Forwarded owner forms

The six GETs already listed in P/09.2 N2 use the responses and body schemas of the [P/08 OpenAPI](../../08-domain/spec/08-domain.api.openapi.yaml). A reference retains the P/08 document base, including its relative JSON/data and nested schema references. No copied or decoded body form is introduced.

| Forwarded GET | P/08 response | P/08 body schema |
|---|---|---|
| `GET /api/members/{member}/{part}` | `HolderMembersResponse` | `HolderMembersBody` |
| `GET /api/anywhere/{member}` | `HolderAnywhereResponse` | `HolderAnywhereBody` |
| `GET /api/topology/{member}` | `HolderTopologyResponse` | `HolderTopologyBody` |
| `GET /api/backup-part/{member}/{part}` | `HolderBackupPartResponse` | `HolderBackupPartBody` |
| `GET /api/book/{member}/{sub}/{book}` | `HolderBookHeadResponse` | `HolderBookHeadBody` |
| `GET /api/book/{member}/{sub}/{book}/{part}` | `HolderBookPartResponse` | `HolderBookPartBody` |

The parameters `Member`, `Part`, `BookSub`, `Book` and `AgentSignature` retain the owner PathItem level. `BackupPartRevision` remains on GET `/api/backup-part/{member}/{part}`: required query `rev`, integer, minimum 1. The agent does not guess a value or default. Success schemas remain reached through the owner responses; no second local schema is kept.

The relay origin is its existing listener, not the holder's example server. Own relay refusals and forwarded holder answers keep their different sources and headers. The forwarding 502 uses the existing `DomainRefusal` owner in the [P/06 OpenAPI](../../06-console/spec/06-console.api.openapi.yaml) and the already normative word `did not answer`; no new refusal word or transport is introduced.

## Inputs and constants

[daemon-flags.tsv](daemon-flags.tsv) projects 34 existing process environment inputs with the common header. $NAME remains environment, commands=domainagent denotes the process. No public command-line flags or join argv are introduced: the command join keeps its implementation-chosen spelling under P/09.1 Implementation decides. The launcher still applies environment-file precedence, role, instance/box/server, aliases, paths and kit rules. The inherited LISTEN_PID/FDS/FDNAMES values keep the complete activation preconditions and descriptor/path checks of the local-token-door contract. Raw string declarations never waive those contracts.

Neither DOMAIN_URL nor RELAY_URL set and nonempty is the existing configuration refusal before the turn or key birth. A https relay address requires RELAY_MEMBER. RELAY accepts absent/empty or exactly 1. Contextual TLS/listener validation remains in P/02.4: an operation-time unknown row or key is not a new startup refusal. DOMAIN_FOLDERS=chains selects chains; every other/absent value selects all, so its type is string, not a new closed enum.

[runtime-constants.tsv](runtime-constants.tsv) declares 14 positive integer literals with the common header name,value,unit,norm,meaning. Units are s, count and bytes. These are not environment settings. BODY_LIMIT is the exact limit imported from the report reception contract; formulas such as camera scheduling, relay age, kept_at rounding, and imported turn/token deadlines keep their own contracts.

## Refusal catalogue

[refusals.tsv](refusals.tsv) has the 22 N4 rows (chapter 9.1 rows 1–12, chapter 9.2 rows 1–10) as 24 projections; their cells cause, outcome, diagnostic and caller are the normative cells of N4. The two compound relay rows each have two code projections with the same source row number. Ten imported local-door/start conditions and two explicit relay-start conditions give 36 projections; the two explicit outcomes `member_key_binding_unconfirmed` and `relay_member_cache_missing` and the early chunked 400 of the relay door make 39 in total. A row is addressed by its chapter and row.

HTTP response_schema names an existing OpenAPI component. Fields name direct properties, including all directly required ones; the complete source cells and OpenAPI retain contextual requirements and exact error/reason words. The local door passes holder refusals as received except its explicitly normed mappings. A peer reply, a stored edit outcome, a journal or alarm is not a new HTTP failure of the agent. A code not fixed by its source is -, including the implementation-chosen join refusal and socket-start refusal; no new exit value is inferred. Relay refusals retain the N2 order and absence of Retry-After.

## Seams and stages

[stages.tsv](stages.tsv) declares 11 stages. Every stage is kit=-: no whole stage or ordinary process algorithm is claimed generated. Existing flags/refusals/families, vectors (with the common contracts supplied by the kit), door and stagetests parts assist only their declared material. No new KIT_PARTS or core part is introduced. The 54 CALL steps (44 in chapter 9.1 and 10 in 9.2) are kit assistance. All 27 ordinary scenarios / 314 steps, assigned vectors, real neighbouring processes, reading and any separate obligations remain mandatory. Build or these seams alone never give P/09 GREEN.

CALL/JSON uses [P/02 Non-HTTP seams](../../02-installer/forms/README.md): one strict JSON input and one result, recursive object subset, exact arrays and exact empty objects. The port table below is the machine-readable port declaration. The JSON fixture word selects the intervention described here and its matching seam, never a prepared expected answer. No public native command or application HTTP route is introduced.

Each case has its own temporary root, valid neutral catalogue and paths, a pinned root, real keys/signatures/envelopes and confirmed rows unless its intervention changes them. Neutral is not unknown. Clocks, I/O failures and races are controlled at the actual boundary; ordinary core decisions are not reimplemented by the adapter. The actual implementation paths produce the result. An unknown port, panic, unrelated failure, malformed JSON or unexecuted call fails. Returned data exposes observations and counters, not secret bytes. Counters refer to the named target effects and exclude incidental diagnostics.

| CALL port | Intervention and observation |
|---|---|
| `agent-startup` | Invoke ordinary process-start admission with a valid neutral catalogue, paths and settings except the named road. Count actual turn and member-key writes before refusal. |
| `agent-join` | Invoke the actual implementation-chosen join command or entry point. The same fixture first pins one real root, repeats it, then attempts a different domain/root; observe the stored value and exact row index. No argv spelling is prescribed. |
| `agent-key-read` | Run the ordinary key read/sign path with a real seed and another public key, under a valid ring. Observe skipped signatures, create-once effects and the in-memory domain failure counter. |
| `agent-turn` | Run ordinary turn/guard/object/release paths with real versions and controlled I/O. For standby a real local token ask uses an actual valid upstream m1. Inject unknown write outcome at the real batch; a new owner races after object confirmation or before release. Count only effective named writes. |
| `agent-publication` | Build the report through the ordinary member_objects and confirmed-base path. Invalid JSON bytes are actual bytes; a former value exists only in the confirmed base. A confirmed deletion removes that prior value. |
| `agent-book` | Run actual slot/read/slot filtering and book secret processing. Reuse compares genuine generated ciphertext across passes; rotate a real book_seal key and open the new envelope. A failed ring envelope remains its original bytes; absent book_seal omits only the affected contribution. |
| `agent-carry` | Use a real signed trusted or rejected set and actual m1. Home write failure is injected after holder confirmation. Count sealed-copy writes/deletes separately from keys and diagnostics. The relay-age fixture gives the prior as_of, the receipt time and domain_age, with unchanged content. The placed-at fixture puts `at_lexeme` as the exact bytes of `at` of one record of `carry.placement.records` in a real holder answer and runs the actual copier and CAS: `item_at_bytes` are the bytes of item `at` of the written `domain/placed/<sub>/<ref>`, `copy_writes` the writes of that copy, `marker_confirmed` whether the revision is confirmed by the `domain/placed` marker. The anywhere-hash fixture passes the JSON input of the anywhere copy hash vectors of the acceptance of chapter 9.1 to the same actual copier: `initial` is the exact stored copy (`items`, `index`, `taken_sha256`); each element of `attempts` starts independently from it, using its trusted `advertised` mark, real UTF-8 HTTP `body`, `received_at` and `domain_age`. Build the valid signed carry for server m1 and its active agent guard. Observe `computed_sha256` on the normal path that judges the body, actual `copy_writes` and `marker_confirmed`; for a refusal also observe `copy_items`, `copy_index`, `taken_sha256` and `related_edits`. Return arrays in attempt order. Expected observations are not adapter input. A hash-only fixture does not exercise the actual copy write or preservation on refusal. For the raw inner-text neighbor, observe the existing copy_items field after each successful write as well: its stored doc and as_of strings must match that attempt literally, not a decoded or normalized value. |
| `agent-edits` | Run ordinary pending/outcomes reading and edit execution through the console path. Unreadable outcomes are confirmed invalid bytes. For same-path order the first edit receives real 409 in flight; the second shares its row and the independent edit does not. |
| `agent-local-token` | Run the real local-door handler/call with role identity, valid body, member key and genuine upstream envelope. Change request_id inside a real m1 or return an actual relay 502 did not answer. Observe the agent response and absence of token-state rows. |
| `agent-follow` | Run ordinary following with real signed sets and records. Freeze the own-term guard boundary once at pass start; a newer set must not erase that evidence. The road fixture gives a dead configured door and a different valid own/best record URL; observe actual request order across two passes. |
| `agent-backup` | Run ordinary keeper validation with a real signed backup and a deliberately different pointer checksum. Count backup object, taken row and refusal row writes; do not bypass record or hash validation. |
| `agent-shared` | Run ordinary deferred refusal cleanup without a new document. A readable current shared pointer outranks the refusal; an unconfirmed/unreadable own pointer cannot justify deletion. Use actual CAS and preserve the object/pointer. |
| `agent-alarms` | Run actual page/front assembly and publication. Return a real console 503. With a readable former page retain its exact value; without it a whole still proceeds without the page. A failed assembly sends no urgent report and creates no deletion in a delta. |
| `relay-door` | Run the real relay door before/after a genuine first empty-batch response. Use real signed stranger input, or Content-Length BODY_LIMIT+1 with an instrumented unread body. Observe actual status, signature checks, body reads and knock writes. |
| `relay-reception` | Run the ordinary shared accept function through the relay memory. After a real heard write compare an exact repeat and a different body with the same sent_at; the hash is from the latest mark write, not only a new generation. |
| `relay-batch` | Run the actual relay batch queue. A newer member publication arrives while an old batch is in flight. Inject no answer at that I/O; busy carries an actual retry_in and preserves the confirmed up revision. Observe retained bytes and real retry timing. |
| `relay-token` | Forward a real raw JSON token ask with deliberate insignificant whitespace and a valid member signature. Compare exact upstream/downstream bytes and signature header; the relay never opens the returned m1. |
| `relay-restart` | Restart the actual relay instance with the same durable member identity. Its copies/answers/knocks are process memory and start empty; the first pre-batch request receives 503. No durable relay cache is invented. |

## Effect fixtures

The effect fixtures use the existing ports and ordinary implementation paths. Retry fixtures first obtain a real response with retry_in and observe every holder/relay request against the monotonic deadline; local reads, turn renewal and neighbouring-console held reads remain available. The backup fixture supplies genuinely signed documents and matching checksums; each attempt independently starts from the same own pair. Compare actual object/taken bytes.

The key replacement fixture operates on real ring-protected seeds and the actual two store rows; interventions on the conditional batch and the binding happen at their real boundaries. Run the actual signing gate, operator-authorized maintenance execution by domainagent under its current turn guard, confirmation, normal holder re-admission and own-console signature check; no fabricated public-key decision or new operator command is introduced. Never return key/seed/signature bytes.

The member-want fixture drives ordinary part requests through passes of the same process with real persistent failures. Count actual requests and observe stored at values, cleanup and a real restart. The relay-age fixture executes real batches, forwards the real cached carry into the ordinary member copier/may age path, then receives a new carry and restarts. The missing-cache fixture uses a genuine first empty-batch response admitting the member, then actual signed GET handlers; no invented cached response is produced.
