# Worker operational qualification procedures

This English text is the canonical `qualification/stand-procedures.md`; the Russian text is a derived translation for people, not in the export.

Apply the binding, controls and evidence rules of the [inventory](README.md). Use actual operational effects and independently controlled dependencies. All times below are stand interventions or existing normative boundaries, not new candidate deadlines. Record any unbound slice as NotExecuted.

## RUN-G01 Restart admission after stop

Use P/03.2-R192/R215/R226/R227 and P/03.3-R033. Run a confirmed assigned unit; change only revision under the same born. Keep its lease confirmation send at t=0, admit restart at t=23 and hold the actual stop callback for 8 s while preventing later lease confirmation. Observe actual start entry and external recipient effects. At t=31 there is no restart call with that expired action window, even when silence allows data writes. The constants are the existing 25 s action window; repeat just before and at its boundary. Normal fast stop with a still-open lease restarts under the same epoch without a fresh issue or resetting last.

Also deliver fencing, name loss and cancellation during stop, then return late after rejoin. The cancelled attempt never revives; a later fresh eligible attempt is distinct. Qualify a control that checks admission only before stop: it must be caught by the post-stop call observation. A prepared may_act boolean or a pure gate vector does not bind this operational race.

## RUN-G02 Worker-table ownership independently of target CAS

Use P/03.4-R022/R023 and P/03.2-R030/R174/R175. Prepare a permitted worker table and a row whose CAS remains current. Let A read it; then give its slot to B with a different holder or gen. Invoke A's ordinary table write and deletion through the SDK. Neither commits under the old ownership; preserve the target bytes/version, and inspect the actual guard and ownership reread. Repeat for a closed slot-write window, including a silent unit lease whose data writes remain permitted: the lost/closed slot still prohibits control publication. As a separate positive control, unit-lease silence with a live own slot does not by itself prohibit the permitted control write.

An own slot renewal between read and write is the positive race: a guard refusal triggers an ownership reread and may retry under the new own slot version without losing the name. Cover whole-row revision/CAS publication, deletes, contributions and books that use the same ownership rule, without assuming one shared function. Qualify an unguarded target-CAS-only control and a guard-refusal-as-name-loss control. Target equality alone cannot prove a guard when the attempted write was never activated.

## RUN-L01 Loaded-catalogue process log mask

Use [log-mask](../../common/contracts/log-mask.md) and [URL credentials](../../common/contracts/url-credentials.md). Load two individually admissible owned teaching manifests. Their secret_in declarations give different synthetic secret parameter names outside common_words, including one nested/URL-valued context; use the published declaration grammar. Trigger ordinary subsystem start/action errors and process diagnostics containing canaries under each declared name, common secret names and a nonsecret neighbor. Observe stderr, journal and other configured process log sinks. Declared/common secret values are masked; the neighbor demonstrates that the diagnostic occurred. No raw canary leaves a log sink.

Exercise diagnostics after load and after catalogue replacement through the prescribed manifest-change/restart procedure, including names contributed by the other manifest; no live reload is required. Prove that the process loaded the catalogue used by the oracle. Controls using only the common vocabulary or only the active subsystem's declaration must fail. Pure Mask vectors remain useful but do not prove the process supplied the catalogue. Store no clear canaries in public evidence; retain only matches and sanitized excerpts.

## RUN-M01 Startup manifest row and mark

Use P/02.3-R040/R042/R043/R046 and worker lifecycle. Start through the ordinary admission path with independently valid schema, environment and manifest SHA. Observe reads of both `platform/manifest/<sub>` and its /rev mark before name capture or ready. Separately remove the row, remove the mark, corrupt mark form and corrupt SHA. Confirmed absence/form failure refuses with the existing code 2 before capture, not an eventual stand timeout.

Separately make a required read temporarily unanswered and then recover within START_WAIT. The process retries with the prescribed 1 s pause and can start when all required reads succeed. Keep it unanswered through START_WAIT=60 s from process start: temporary outcome is code 1, not NoManifest/code 2; doors remain closed and no capture occurs. Record process-start/budget origin and attempts for row and mark separately. Positive controls include both valid reads and lagging-but-admissible publication state from RUN-M02. A control treating any non-row reply as absence must fail.

## RUN-M02 Manifest watch distinguishes lagging, changed and malformed marks

Use P/02.3-R054/R072/R075 and its mark form. Start from a valid installation publication window: the loaded manifest row has rev=2 while the readable mark still has rev=1, as permitted by the contract. Let ordinary watch passes observe 1, then 2. The worker keeps serving while awaiting the mark and does not restart merely for the lag. Later publish a valid new mark that requires restart: observe orderly stop and code 0.

In independent running-process slices supply malformed mark values, including 0 and 01: the process diagnoses the form failure and stops with code 2. A confirmed missing mark is a change and causes orderly stop with code 0. An unanswered read is not a change: the worker keeps serving until a later confirmed observation supplies its own outcome. Keep these cases distinct by the running-process rules P/02.3-R128/R130/R131/R132/R134, not the startup missing-mark rule. Controls are a same-mark no-stop run, a lag-as-change control and a digits-only parser. Record loaded revision, observed marks and exit causes, not just process disappearance.

## RUN-N01 Supervisor notifications from the ordinary loop

Use worker lifecycle Signals and readiness and P/03.3 N1.2 watchdog. Launch the ordinary worker with a stand-owned NOTIFY_SOCKET receiver and otherwise healthy dependencies. Record received messages and correlate name capture with READY=1: it follows capture, never precedes it. During ordinary turns, observe WATCHDOG=1 on each loop turn. The notification receiver must be reached by the deployed process path; an injected SDK notifier alone is insufficient.

Delay an ordinary step through STALL so the stand-in takes over. It may maintain permitted slot/heartbeat effects but emits no watchdog; after the ordinary loop returns its own notifications resume if still admitted. Capture-refusal and no-name controls produce no false ready. Qualify a nil/disconnected notifier control and a stand-in-watchdog control. Missing supervisor transport leaves that slice NotExecuted, not a successful SDK-only readiness result.

## RUN-T01 TLS process door and domain peer admission

Use P/03.4 N1.7, P/03.7-R081/R082/R083/R086 and [role-certificate](../../common/contracts/role-certificate.md). Prepare an owned readable kit, current trust/revocation data and an ordinary worker door. Observe its advertised address, TLS handshake and an authorized request reaching its handler. A present kit selects the contract's TLS path; plain HTTP or unconditional kit_absent behavior does not pass. Independently exercise the no-kit loopback HTTP mode and its closed role routes, without requiring TLS in that permitted mode.

For the domain door, a valid domainconsole client reaches door.pass. No client certificate, a trusted wrong role, a forbidden signature or a revoked serial yields 403 forbidden without handler execution. Bad chain, expired leaf and missing clientAuth are handshake failures without HTTP. The client verifies the worker server as its own-cluster `<sub>domain` peer. Keep other conditions valid in each mutation, including optional client-certificate request semantics. Qualify controls that ignore the kit, search for a role without admission, or execute the handler before refusing. Missing domain consumer/TLS binding is NotExecuted for its dependent slices.

## RUN-I01 One retry budget and Retry-After

Use [store-client](../../common/contracts/store-client.md) Production obligations/unavailable and [production obligations](../../common/contracts/production-obligations.md). Record the worker's declared finite logical-operation budget, cancellation and retry ownership. Trigger an ordinary worker write through a controlled store boundary. Make consecutive attempts silent; observe send/return times from the first attempt. Retries preserve operation id, CAS and guard where required and share the one original budget; a new hop does not restart it. Budget/cancellation yields the existing unknown/unavailable handling, never fabricated success.

Separately return 503 unavailable with Retry-After: 5 in the contract's valid form, recover afterwards and observe that no retry is sent before the permitted retry time. Test response loss before/after commit and an expired remaining budget; do not require a particular retry count. Qualify controls that reset the deadline per attempt or discard Retry-After. Keep network scheduling uncertainty separate from the measured monotonic origin. Pure reply classification does not establish the worker's operational retry policy.

## RUN-S01 Envelope retention belongs to worker state

Use P/03.5-R026/R035 and [sealing](../../common/contracts/sealing.md). Supply an owned envelope in an otherwise valid unit, including a nested secret. Bind a qualified observer to abstract state ownership and lifetime: distinguish long-lived SDK/worker unit state from temporary opening arguments and recipient-owned buffers. Prove the observer can identify a deliberately retained clear unit row and a permitted recipient-held value. Do not require a named field, map, language, object address, garbage-collector behavior or erasure of every heap byte.

Run ordinary start, callback completion, revision restart and stop. The recipient obtains the correct opened value; retained worker unit state holds only the envelope. Heartbeats/logs contain no opened value. Fresh restart obtains its value through the permitted opening/recipient path, not a retained clear row. A whole-process string scan is not an oracle: the recipient may lawfully retain clear data and dead transient bytes need not be erased. Without a qualified ownership/lifetime binding, report that retention assertion NotExecuted even if log canary checks pass. A retention control must fail independently of sink leakage controls.

## RUN-R01 Operational stable-work retry reset

Use P/03.3-R024/R025/R028 and runtime constants. Cause real start/work failures until the exponential base reaches RETRY_MAX; observe stalled=true in heartbeat and through the subsystem word. Then permit successful continuous work. Before RETRY_MAX elapses from stable start the old count remains; at/after the reset boundary the next failure has count 1 and stalled=false, with the first-failure backoff range. Use qualified retry-state observation if no public count is exposed; do not invent a status field.

Independently test subsystem stable, confirmed assignment absence, unanswered assignment, move, fence and name change. Only the three normative reset causes clear the count; moves/fences/name changes are not additional failures. Exercise formula support at low n and at cap, default jitter and admitted configured jitter through the declared configuration if exposed; do not require an unprovided jitter option or exact random samples. Controls include a pure Stable function never called by the running worker and a reset-on-nonanswer control. Preserve monotonic stability evidence; wall-clock steps cannot substitute for stable duration.

## RUN-G03 Effective place and unreadable former heartbeat

Use P/03.2-R051. Prepare a hold with a nonempty holder, not released, version age below LOST_AFTER+HOLD_SKEW and otherwise valid shape. Arrange that it follows the name just captured on the same server. Make the former worker heartbeat unreadable while all name/hold reads succeed. Ordinary acquisition waits and does not write the hold; unreadability is not staleness. Cover absent/unanswered/damaged heartbeat by their own contract classifications rather than making them all empty.

With the same bad heartbeat, change only the hold to an ineffective/free state: it can be taken according to the hold row without needing that heartbeat. Then restore an effective hold and a readable former heartbeat to test the applicable following-name/age branch. Observe actual reads and writes and the age origin. Qualify an unconditional follows-name takeover control and an always-wait-for-heartbeat control; the latter must fail the free-hold positive slice. No new public heartbeat override is required.

## RUN-F01 Filing stamps and later group move

Use P/03.6-R079/R151. Prepare an admissible target manifest declaring requests.stamp with by, at, group and about, plus placement.group_by and an about field. File through the ordinary worker SDK on behalf of an assigned unit. Independently compute the addressee's group from its row and the declared group-of contract. Observe the stored request: all requested stamps have the specified values, not merely by/at. Include a target without these optional stamps as a separate positive case.

Before holder execution move only the addressee to another group. The stamped request is refused before perform with the existing moved-group error. Empty/absent group does not trigger comparison; an unchanged group permits the ordinary action. Qualify controls omitting group/about or calculating them from the filer rather than addressee. Request bytes and handler calls must both be observed; refusal alone could hide an invalid preparation. Use owned teaching descriptors without modifying the common canonical manifests.

## RUN-O01 Extension applies changed-field validation

Use P/03.6-R182/R183 and [row-check](../../common/contracts/row-check.md) edit R1–R3. Prepare an existing otherwise valid owned row and an admissible target descriptor restricting ends. Order an extension whose new ends exceeds that restriction while all ownership, CAS and time checks permit reaching the validation branch. Observe refused and no target write/version change. The old row remains whole. A legal increased ends passes validation, preserves unchanged fields and writes revision+1 with its CAS, guard and not_after.

Cover changed fields' type/bounds and any declared reference checks independently; equality/lower ends exercises unchanged, not refusal. Qualify a control that validates Create but writes extensions directly. Observe the actual SDK/order path; passing the pure Edit vectors or detecting a matching import is insufficient. Use descriptor-conforming synthetic values and retain the independent validation result so an earlier failure cannot masquerade as this refusal.

## RUN-C01 First confirmed publication and cumulative late counters

Use P/03.4-R069/R071. Give a live holder one otherwise eligible request. Commit its outcome at the store, drop the response, then replay the same operation id to receive the first successful confirmation with again. On the next confirmed heartbeat, its outcome count increases exactly once. Repeating that confirmation does not increment it again. Exercise performed, refused, expired and unknown through their ordinary branches; a failed/unconfirmed publication alone does not count.

For unknown followed by late performed/refused, lose the late publication response after commit and confirm its replay. Unknown stays incremented; the new outcome and commands_reanswered each increase once. Repeat with ordinary first replies and CAS/transport retry races. Qualify controls skipping every again reply, incrementing every retry, or decrementing unknown after late. Correlate counts with the first confirmation to this instance, not only server application; keep other heartbeat traffic healthy and compare deltas per process incarnation.

## RUN-E01 Suppression starts with the written line

Use P/03.6-R058/R062/R064/R070. Feed repeated events of one declared suppress class through the ordinary event sink. Independently fail its first non-summary write before publication; recover and offer the next event. It is written as the first line, not swallowed behind a nonexistent line. In another slice delay the first successful publication; the monotonic window starts at that actual write, not Offer/admission. A pass before its window age expires emits no summary; at expiry it closes with the normative repeats/since/until/t and ordering before a new first line.

Control a wall-clock jump while monotonic time advances normally; event stamps retain their own meaning. On stop, open windows with repeats close under may_write before the last heartbeat; windows without repeats produce no summary. Unknown write outcome needs its own qualified activation/history and cannot be called a proven pre-publication failure. Qualify an offer-time-window control and a state-advance-on-failed-write control. Read actual journal lines independently; a pure suppression state or sink return code is insufficient.

## RUN-D01 Sequential retained-token publication

Use P/03.7-R053/R058/R113 and [secret-files](../../common/contracts/secret-files.md). Prepare a kind with keep:true and owned valid tokens. Through the ordinary agent/receiver path accept h1; delay its persist publication. Revoke/replace it and accept h2, then release the delay. A correct writer may serialize later work behind the first publication. Require proved overlapping accepted intents or proved serialization, not two concurrently executed filesystem writes. After intents drain, ordinary reopen/decrypt reads the latest sequentially accepted persisted token, never h1 overwriting completed h2.

Fail persist before publication and at the contract's uncertainty/barrier points. Immediately after accepted h2 the current in memory is h2 regardless of persist success; retries use the declared finite budget. Before first acceptance the old retained file remains; pre-publication failure preserves it, unknown publication does not claim preservation. A persistence success requires file/directory barriers and mode 0600. Verify the single AAD with full file path and /token on ordinary reopen, with wrong-path/wrong-pointer controls. Do not require new-file recovery after exhausted IO budget. Qualify stale-late-rename, delayed-promotion and false-success controls; no token material enters logs/evidence.

## RUN-G04 Slot deadline throughout SIGTERM

Use P/03.4-R034/R200 and runtime constants. Execute ordinary SIGTERM with independent monotonic send times for the slot's confirmed capture/renewal, each lease and each place. Delay stop callbacks and, separately, post-unit-stop place close/summary/last-heartbeat work. Observe actual renewal and hand-over sends. Every slot release is within WRITE_WINDOW of the slot's own last confirmed send; an epoch/place confirmation does not extend it. A confirmed slot renewal during stop does extend that slot origin. Each place retains its own window.

Exercise near/beyond boundaries with no units still stopping, and with one/two slow units. The implementation may renew while delayed; score the resulting history rather than requiring a timer or renewal location. Preserve the prescribed place-before-slot stop order and the declared worker.stop_timeout bounds; never require the system to free a slot using an expired permission. Qualify a control renewing only during stop_unit and one using the newest arbitrary confirmation as the slot clock. A common confirmed_age seam cannot prove distinct-clock slices. A manager timeout is distinct from orderly hand-over.

## RUN-C02 Unknown from actual perform entry

Use P/03.6-R155/R159/R162/R163/R164/R165/R167/R168/R169/R170/R171/R172 and runtime constants. Schedule the ordinary holder so a request has passed admission/begun but actual perform entry is delayed; record that entry independently at the recipient boundary. Let B=PERFORM_TIMEOUT+PERFORM_GRACE from that actual monotonic point. A result just before B is ordinary, and no-result unknown is not published before B. Observe a result after published unknown following late/CAS rules, including a lost publication response. The scheduler delay before perform is not part of this result wait.

Hold the callback unfinished across timeout and observe another eligible same-group request: it is not dispatched until the first returns. Repeat with delays on both sides of timer scheduling and qualified tolerance bounds; if entry cannot be ordered at the needed precision, mark that boundary slice NotExecuted. Do not claim cross-holder exclusion from this wait. Qualify a timer-from-dispatch/admission control and a callback-completed-by-timeout control. Require actual entry/return/store events, not a helper's computed duration.

## RUN-D02 Operational domain worker effects

Use P/03.7-R011/R033/R074/R077/R080/R101. Prepare isolated admissible testsub/testsub2 descriptors with kept and a carried book, an owned holder and members. Bind a teaching subsystem consumer that produces declared kept/book content through the ordinary domain SDK. Run the actual domain-worker route, observe its single domain slot/heartbeat, declared exact/family kept paths `domain/<sub>/<name>` and carried-book rows `domain/<sub>/<book>/<member>` under the existing ownership rule. Include several kept names and a family so a single literal kept row cannot pass. Kept is not delivered as a member copy. Use two contenders to ensure only the admitted slot owner publishes; readiness or token cache alone is insufficient.

Send an ordinary domain-console door.pass request to the domain handler; observe dispatch and its lawful result, with the TLS controls of RUN-T01. Include kept-only and carried-book-only manifests, restart/reacquisition and absence of these features by their existing eligibility rules. The subsystem chooses book content: the oracle verifies its declared teaching output, not a new platform book algorithm. No new canonical teaching manifest bytes or public ABI are required. Missing qualified consumer, domain route or door binding is NotExecuted for that subject; qualify a heartbeat-only/no-handler control.

## RUN-D03 UTC-day cooldown reaches the operational requester

Use P/03.7-R107 and token-cache day. In a keep:true consumer, let the receiver refuse current with revoked, then let the actual local agent return the same jti; verify all ordinary token validation. Observe one replacement request and no further request before the end of the worker's current UTC calendar day. Use a non-UTC TIMEZONE whose displayed local midnight differs from UTC. Advance local displayed midnight without crossing UTC: it does not end cooldown. Cross UTC midnight while local date remains unchanged: cooldown no longer forbids the next eligible request; do not impose an exact new scheduling cadence.

Also test a different jti and a clock near UTC midnight with ordinary positive receiver outcomes. Keep worker wall clock distinct from receiver verification time and monotonic IO budgets. An injected day ordinal in the pure machine cannot prove the process supplier's UTC calculation. Qualify local-midnight and monotonic-24-hour cooldown controls; retain sanitized request times, jti fingerprints and UTC-day derivation without tokens. An unbound worker clock leaves this slice NotExecuted.

## RUN-I02 Failed store attempts on every operational path

Use P/03.4-R059, P/03.2 N4 and [store-client](../../common/contracts/store-client.md). Independently record actual worker store attempts and their contract classifications at a controlled store/transport boundary. Drive startup/schema/manifest reads that recover and allow a later heartbeat, ordinary SDK get/list/write retries, manifest watch and process-door reads. In isolated slices fail exactly one or several actual attempts with an error or no answer, then recover. Compare heartbeat.store_errors deltas with independently correlated failed attempts since that incarnation launched; include successful, conflict/guard and other classified responses by their actual N4 rule.

Do not substitute a count of logical SDK invocations for transport attempts, double-count one attempt at several layers or assume a common module supplies an observer. The binding may use qualified external interception and the implementation's declared transport; no new common-module callback/API is prescribed. If hidden internal retries cannot be independently distinguished, their slices remain NotExecuted. Qualify logical-call-only, skipped-startup/watch/door and double-observer controls. A process that exits before a heartbeat does not establish a zero counter; preserve that limitation rather than inventing a new public metric endpoint.

## RUN-C03 Histograms and ordered-row listing

Use P/03.4-R072/R073/R074/R077/R078 and runtime constants. Run eligible operator and subsystem-filed requests with known at stamps, independently observed first local receipt and outcome publication. Observe heartbeat deltas of command_road/request by the correct by class and monotonic command_wait; they have the specified cumulative buckets/count/sum and approximate decomposition, not timing derived from filed. Choose event times around published bucket boundaries, account for qualified observation uncertainty and repeat the same local observation so it is not counted as a new first receipt.

For made_rows prepare the orderer's permitted prefix with ordinary, tombstone and taken rows and unrelated neighboring rows. Observe actual ordinary listings and the reported last-listing count. Consecutive listings are at least MADE_ROWS_MIN_INTERVAL apart; while no new listing occurs the last count may remain, since no upper listing deadline exists. Change rows between listings and verify the next completed listing updates it. Qualify empty-histogram, filed-time, exclude-tombstone/taken and too-frequent-listing controls. No observed completed listing leaves its update slice NotExecuted, not a reason to invent a maximum wait or forced public listing method.

## RUN-S02 Startup resealing of list-form worker tables

Use P/03.4-R100 and [sealing](../../common/contracts/sealing.md) Reseal a value. Prepare an admissible list-form worker.writes table with declared readers and owned nested secrets. Ordinary table writes seal with current kid. Before a fresh worker startup place clear, older-key and current-key values plus one unreadable row, with a later readable row. Under its own live slot, startup reseals each eligible readable row with the read CAS; revision is unchanged and AAD remains the row key/full pointer. The unreadable row stays unchanged, is diagnosed without values, and startup continues to the later row.

Cause a CAS conflict by an independently admitted writer; the worker rereads and avoids rewriting a value already at the new kid. Separately lose the slot before publication: the old owner cannot commit reseal. Verify plaintext equivalence by the independent envelope reader and unchanged versions where no write is needed. A declared-field worker table with *_secret is a manifest refusal, not this exception. Qualify skipped-startup-reseal, revision-increment and unguarded-reseal controls. Passing a pure reseal vector does not prove table enumeration, CAS retry or startup continuation.
