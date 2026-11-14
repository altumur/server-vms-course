# P/02 external qualification procedures

This English text is the canonical `qualification/stand-procedures.md`; the Russian text is a derived translation for people, not in the export.

The [inventory and scoring rules](README.md) apply to every slice. The norm is the cited M text; this file supplies preparation and observations. All data is stand-owned and current-format. Record actual public outcomes and before/after state; a candidate's own success text or a prepared expected object is not an independent oracle.

## RUN-K01 Concurrent rotation preserves published keys

Use P/02.4-R373/R399/R401/R404 and the [secret-file obligations](../../common/contracts/secret-files.md#production-obligations). Prepare one permitted, readable ring and a value sealed by its current key; independently verify opening in its original AAD context. Save key identities privately in the stand and publish only opaque fingerprints.

Start two ordinary `w2cctl secrets rotate` commands on that same path. With an external scheduler, explore overlapping admission, reading and publication. Observe the actual external file-read/publication events; do not require a named lock, function, temporary filename or fixed `k2`. A correct serialization may prevent the second read until the first completes. Require evidence of competing live invocations; absence of overlap coverage is NotExecuted, not a passed race. Include both publication orders, repeats and a sequential positive control.

After each acknowledged successful rotation, use the then-published ring to create an owned envelope, record its context, and let the competing invocation continue. After all invocations finish and after ordinary reopen, every key acknowledged so far, including the initial key, remains in the ring and every such envelope opens to the original owned value. Key identity includes key bytes: equal kid labels with different keys do not match. Serialization or refusal of a competing command is admissible; two successes, a particular lock and a particular refusal code beyond zero/nonzero are not required. Keep normal command exit, reason without key material and the actual publication history. A refusal of ring validation preserves the file; do not apply that premise to an uncertain post-publication medium failure.

Qualify the scheduler and oracle with a lost-update control in which both writers use the same old snapshot and the later publication erases the first new key; it must fail retained-key and envelope-open checks. A control that only checks the initial key or kid names is insufficient. Atomic replacement alone is no proof of retention. This is a concurrency record; physical fault durability requires its own qualified medium and is not inferred from this run.

## RUN-K02 Damaged current envelopes fail the whole command

Use P/02.4-R377/R379/R380 and the [sealing contract](../../common/contracts/sealing.md). Prepare a readable ring and a schema-valid manifest unit/table row containing a synthetic current-key envelope. In separate copies, corrupt only its authentication tag while preserving the envelope grammar, and move an intact envelope to a different row key or full JSON Pointer. The independent cryptographic reader must prove that the original opens and each mutated context does not.

Add a later selected readable row with a clear secret, and a row with secrets nested in a JSON field. Invoke ordinary `secrets status` and, on a fresh copy, `secrets seal` over all selected rows. Each bad value is counted as `?`; `seal` leaves its exact bytes unchanged, finishes the walk and exits 1. `status` exits 1 and writes nothing. The later clear value is sealed by `seal`, opens with its own AAD and current key, and proves that the walk continued. When only the bad envelope exists, its row bytes and version stay unchanged. Diagnostics contain no secret values. At multiple fields in one otherwise readable row, inspect each independent field so an unchanged bad value cannot hide skipped valid work.

Controls: intact current envelope, valid older envelope, wrong tag, wrong row key, wrong nested path and an unknown kid. Qualify a control that prints `?` but exits 0, and a control that aborts before the later row; both must fail. Do not decide this command-level result solely from the pure reseal vector's `same` label.

## RUN-K03 Successful ring writes stay readable

Use P/02.4-R373/R399/R401, [Ring file](../../common/contracts/sealing.md#ring-file) and [finite budgets](../../common/contracts/production-obligations.md). Record the implementation's effective finite ring-file budget, unit and definition from its declared environment. Do not substitute a fixed size borrowed from another candidate. Prepare valid rings just below and at that budget, using permitted blank/comment lines and valid distinct `kN` entries; independently validate their form and prove that the ordinary reader accepts them before rotation. Include a case in which a further entry would cross the effective read boundary, and repeated ordinary rotations approaching it.

For every exit 0, re-read with the same ordinary reader used by the command's consumers, without altering budget or environment: the published ring is readable, the new current key exists, all former keys remain and their envelopes open. A refusal must be a normal nonzero outcome without key material; a ring-check refusal leaves the prior file intact. No exact new refusal kind, code or output sentence is introduced for a resource limit. The writer cannot confirm an unreadable result. Record before/after bytes, length and mode privately and publish only nonsecret hashes and observations.

Controls: a small valid ring, a declared-limit reader, and a writer that successfully publishes beyond its own reader's boundary. The latter must fail even if an unconstrained independent parser accepts the format. Missing effective limit evidence is NotExecuted. This procedure tests the current writer/reader pair, not old-format compatibility or permission to reject a protocol value solely for convenience.

## RUN-K04 Empty or unreadable ring is distinct from unset

Use P/02.4-R374/R402 and sealing `no_key`. Prepare selected readable rows with owned clear secrets and record exact bytes/versions. Run `status` and `seal` in separately fresh command environments for: unset `SECRETS_KEY`; set-empty `SECRETS_KEY`; an empty file at a permitted path; a malformed readable file; and a path that cannot be read by the ordinary command identity. Keep store and all selected rows available; missing store access is not this case.

Every set-empty/unreadable slice returns normally with code 2 before any write. Observe the absence of writes at the store boundary, not only equality of final values. Its diagnostic names the reason ring unreadable and the supplied path, including an empty path, without secret values. All clear rows retain bytes and versions. The unset control has the distinct reason key not set and follows the mode without a key; it is not classified as unreadable. A readable-ring control permits the normal status/seal behavior, so broken layout preparation cannot cause all slices to refuse. The diagnostic layout/language is not fixed beyond the required meaning, supplied path and absence of secret values.

Controls must detect set-empty falling through to unset, a nil-ring crash and any write before the refusal. A panic, signal or stand timeout is never code 2. Preserve set/unset presence separately from the value in the sanitized environment evidence; do not silently erase the set-empty case.

## RUN-K05 Known-row form failures are not rewritten

Use P/02.4-R389/R396, the [data catalogue](../../common/data/catalog.tsv), codec, and each selected family's schema/outcomes. Prepare `domain/users/alice` from a valid current writer-shaped row, with an owned valid clear password hash and all other fields valid. Derive separate copies with only `revision` above 9007199254740991, or only `at` outside its published time codec (for example `garbage`). Independently prove each target failure in reader mode. A valid row at the revision bound and a valid time are controls; do not use a second malformed field to reach the desired result.

For each copy run ordinary `status` and `seal`, followed in the selection by a valid sealable row. The invalid known row is byte for byte unchanged, its version unchanged, its diagnostic names its key and unreadable without values, and command code is 1 after the full walk. It is not unknown-row-form. The later row demonstrates continuation. In `status` all rows stay unchanged. Include the other selected known families, manifest unit/table rows, nested JSON syntax/shape, and the positive neighboring codec values, using their own published bounds and outcomes rather than treating presence of a field as its validation.

Qualify the oracle with a whole-decimal but out-of-range revision control and a merely-present invalid timestamp control; an implementation that seals either must fail. Record per-family coverage and keep unbound families NotExecuted; passing the two example mutations is not evidence for every walked family.

## RUN-C01 Rollout uses the console TLS path

Use P/02.4-R170/R173/R360 and [role-certificate own_client/own_url](../../common/contracts/role-certificate.md). Prepare the ordinary rollout prerequisites with a stand-owned trusted centre, valid console-role kit, valid revocation data, an owned nonloopback server address and a unique synthetic administrative token. The console-side observer recognizes the canary privately and records only its presence, never its value. Supply the ordinary configuration file and environment; bind the command to the actual console barrier path, not a pure poll adapter.

Run rollout to that barrier and observe the connection and request at the controlled console. With `ca.pem`/the kit present, the request uses HTTPS, the server chain/name/role/revocation is checked by the contract, and Authorization crosses only the authenticated TLS channel. Correlate successful control access with the matching barrier request; a command failing before any attempt does not prove transport. At a plain-HTTP sink, an untrusted/incorrect-name peer, wrong-role peer and invalid revocation input, require the existing refusal/no authorized request outcome. Observe any plaintext canary transmission on attempted connections and on redirects; refusal after sending the bearer is too late. Do not add a new rollout exit code.

Controls: valid TLS completes the barrier; a client that always prepends `http://` is detected even if the TLS-only console later refuses it; a client that disables verification is detected by an invalid peer. The no-kit loopback development slice follows its existing contract separately, not an HTTPS requirement for every environment. Capture only sanitized request metadata and public certificates.

## RUN-C02 Rollout reads its console address from the file

Use P/02.4-R360. On fresh rollout prerequisites, write valid nondefault `CONSOLE_HOST`/`CONSOLE_PORT` to `w2c.env` and leave both variables unexported in the command's inherited environment. Use an owned reachable address/port, record it, and make the usual default endpoint an observed decoy. Serve the correct barrier response only at the configured endpoint, using the transport required by RUN-C01.

Run the ordinary rollout shell and observe which console is contacted and whether its real barrier is reached. It must use the address from the file; silence at every endpoint or a refusal before address use is NotExecuted for this slice. Test host-only, port-only and both changed, plus the ordinary defaults as a positive control. This record does not invent precedence for a contradictory exported value: that is outside this input. A control that uses only process environment must be detected by the configured-endpoint and decoy observations. Retain sanitized environment presence, file fields, endpoint events and the barrier result; passing TLS alone cannot close this record.

## RUN-C03 Workers use the own-console address mapping

Use P/02.4-R113/R157/R173 and role-certificate `own_url`. Set `SERVER_NAME=s1` and give the console its ordinary trusted leaf for DNS `s1`. In independent IPv4 and IPv6 slices bind `CONSOLE_HOST=0.0.0.0` and `::`; prepare a valid metric and an admissible worker increase. Observe the actual workers command's connection destination and TLS SNI/verification name. The mappings are respectively `127.0.0.1` and `::1`, with bracketed IPv6 URL authority, and verification name `s1` in both cases. Use the whole own_url table for ordinary loopback, explicit DNS and explicit nonloopback addresses as controls, without substituting SERVER_NAME where that table does not.

The valid peer is accepted and the metric-driven lawful action occurs. A wrong-name peer is rejected without a start; merely observing an attempted TCP connection is insufficient. Controls that use the original wildcard as destination or as TLS verification name must fail. Record destination, public SAN/SNI, peer outcome and manager actions. An unavailable IPv6 stack leaves only that slice NotExecuted and does not establish the IPv6 rule by the IPv4 result.

## RUN-C04 Workers reject multiple peer roles

Use P/02.4-R157/R176 and [peer step 6](../../common/contracts/peer.md). Keep chain, time, DNS, revocation and metric input valid. Serve an owned console leaf with exactly one role URI `urn:w2c:role:console`, then a separately signed leaf that differs in role cardinality by carrying both console and resource role URIs. Call the actual workers client. The one-role control succeeds; the two-role leaf gives peer outcome `no_role`, no authorized metric use and no worker start. Retain the public leaf and the discriminating peer observation; a generic connection failure with no established cause is insufficient.

Also control no role, one wrong role and a duplicate role URI by the same published peer rule. An implementation that tests only whether console appears among the URIs must fail the two-role slice. Standard x509 success alone is not the peer contract. Missing peer-result observation is NotExecuted for the exact `no_role` assertion, even if no workers happened to start.

## RUN-W01 An uncertain stop still occupies capacity

Use P/02.4-R126/R127. With a valid metric, limit 2 and actual live instances 1 and 5, request a stop of 5. The controlled manager returns an unconfirmed result while independent process/manager observation proves that 5 is still live or deactivating. Keep that stop unresolved through the next ordinary pass with want 2. Observe reservations only through the declared stand supplier if present; the decisive public facts are the live processes, confirmation history and emitted start/stop actions.

While the stop outcome is unconfirmed, it continues to occupy capacity; there is no additional start that would make three live processes. Reconciliation that proves absence releases that occupancy and permits the lawful replacement; confirmed presence retains it. Exercise response loss both before and after an actual stop and then reconciliation. Confirmed-absent start reconciliation is a separate positive control, not an error merely because its reservation is cleared.

Controls: a manager reporting active, activating and deactivating states; a stop whose response is lost but process lives; a completed confirmed stop. A control that counts only active/activating or only start reservations must be detected. The manager observer and delays must be qualified independently; do not require any candidate-internal reservation map, operation string or library.

## RUN-T01 Unconfirmed TLS status reading exits 2

Use P/02.4-R406/R407/R411. Prepare readable absent/nonexpired local kits, no substitute local resource-cache directory, and a store with a known resource heartbeat set. First make ordinary admin.sock inaccessible; separately keep the store available but make a required heartbeat read unconfirmed. Ordinary `w2cctl tls status` exits 2, writes nothing and cannot treat unobserved heartbeats as an empty cluster. Observe actual admin/heartbeat read attempts and write absence, including the case when local kits look healthy.

Positive controls: a confirmed empty resource set, a confirmed healthy heartbeat set, an expired kit without a live door, and an off-loopback loopback-mode door. They follow the existing codes 0/1/2 and per-door fields; no new output layout is required. A control that reads only local files and returns 0 without cluster observation must fail. Missing read-attempt observation leaves the source-of-data assertion NotExecuted; a command that never accesses the actual admin interface is not qualified by a local helper test.

## RUN-P01 Role names preserve admissible underscores

Use P/02.4-R137/R475 and P/02.1 `subName`. Prepare a separately valid owned manifest named `test_sub`, whose derived worker/controller groups fit the existing OS limit. The centre issues ordinary kits for server `s1` and roles `test_subworker` and `test_subcontroller`; run the ordinary own-client preparation for these roles. This is an isolated grammar fixture, not another application subsystem. Verify with an independent public-certificate reader that the exact required role URI and permitted identity reach the resulting kit and that the standard peer accepts it under otherwise valid conditions.

Compare with the same fixture named `testsub` and test the published longest admissible installation name boundary. Reject only role/name cases that the existing grammar actually disallows; do not infer a broader centre-role grammar from these two suffixes. A control using a hyphen-only role regexp must fail the underscore slice. Retain normal command outcomes and public SANs, without private material. No valid kit or no ordinary own path leaves that dependent slice NotExecuted.

## RUN-D01 The deletion proof covers the complete catalogue

Use P/02.3-R094/R141/R146/R153/R157/R164 and the [finite-profile contract](../forms/README.md#internal-finite-deletion-profile). Independently enumerate every confirmed catalogue family participating in deletion and the procedures actually assigned by the included contracts. Derive their acquisition, intent, target, done, cleanup and mixed-batch packet shapes, guards, metadata skeleton bounds H and multiplicities. Record the exact sources for each assignment and effective B/V from the actual store Status. Do not accept the candidate's own descriptor list as the universe of completeness.

For a complete provable profile, observe ordinary installation and process startup admitting it only under the normative bound checks. For each required packet/proof entry, use a fresh independent slice that removes it, duplicates it, shortens H/multiplicity, substitutes unknown provenance or changes the effective limits; the existing refusal is `refused:form` before any installation write or process door. Bind mutations through the implementation's declared internal transfer of P/02.3-R141 and a qualified stand supplier; this requires no new public profile ABI, flag or door. If a mutation cannot be bound there, its dependent slice is NotExecuted. If a confirmed catalogue's required procedure lacks a contract proof, installation refuses without writes; its apparent small local packet cannot replace that proof. An unchanged installation must still pass the check. A conservative profile may lawfully refuse the ordinary B/V: do not demand success merely because a previous stand used those values.

Controls include a catalogue with unit/claim deletion and mixed batches whose profiles cannot be satisfied by a single parts-delete descriptor, and a truly complete positive profile if the qualified contracts supply one. Observe source-specific missing proof, refusal and write/door absence. If the stand cannot independently bind the actual catalogue to all emitted packet/proof requirements, that completeness assertion is NotExecuted. Shape-valid arbitrary strings, a schema pass and self-comparison against the same short descriptor table are not evidence.
