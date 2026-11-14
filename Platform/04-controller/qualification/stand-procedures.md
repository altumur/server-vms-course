# P/04 external qualification procedures

This English text is the canonical `qualification/stand-procedures.md`; the Russian text is a derived translation for people, not in the export.

These procedures check the existing obligations of [the controller norms](../spec/04-controller.norms.md). They introduce no command, refusal, field, timeout or candidate interface. They complement J with externally scheduled races, ordinary process integration and dependency observations; they do not narrow the applicability of an unmarked norm to production.

## Binding, controls and evidence

Use isolated current-format data owned by the stand, the ordinary controller and launcher, and dependencies through their published doors. Fixture manifests use only the training subsystem names testsub and testsub2 and pass the ordinary loader, except for a specifically invalid loader slice. A fixture value or process count is preparation, not a new normative limit. Do not change canonical training data. Keep private material out of evidence; credentials, certificates and canaries are synthetic and stand-owned.

Before scoring a slice, bind its ordinary command/process, real store/object requests, clock or scheduler, and independent observers. Record the exact implementation and M/J/Q commits, the validated fixture, effective settings and store limits, provider versions, sanitized environment presence, initial bytes/versions and timed external request/response events. Use the controller's own monotonic observation history for ages, not a console's history or a writer's wall clock. Exact time-boundary slices need a qualified clock binding; ordinary event observations alone do not establish equality at a boundary. No procedure acquires a new numeric deadline: use the cited normative periods and the implementation's declared finite I/O budgets. Distinguish a stand timeout from a candidate response.

Qualify each observer and fault/scheduling supplier with the stated positive and discriminating negative controls before judging the candidate. Controls are stand tests, not a requirement to patch a candidate. A missing or unqualified supplier, command, observer, budget or independently established branch leaves the affected slice **NotExecuted**, with **MissingBinding** and the missing item recorded. An attempted control that does not discriminate is a stand failure. A proven observable violation is a candidate failure against the cited norm. Do not promote partial coverage to a passed record. Publishing these procedures is not execution or qualification of their suppliers.

For every race, prove the actual external interleaving and admission/confirmation order. Do not require a particular function, package, lock, temporary filename or internal map. A request trace must come from the dependency boundary, not a candidate-produced expected result. Preserve before/after store versions, object identities and report cycles. An unchanged final object alone does not prove that no forbidden intermediate write occurred.

## RUN-M01 Field rules reach snapshot and diagnostic masks

Use P/04-R548/R556 and the [URL credential](../../common/contracts/url-credentials.md) and [log mask](../../common/contracts/log-mask.md) contracts. In an isolated valid fixture, expose a table URL field through domain.view_tables and a unit URL through snapshot. Declare a permitted path regex with named login/secret groups and a synthetic address such as https://h/~alice:DEMO/x. Independently verify the field rule and ordinary load before publication. Include field-specific rules, rules from the combined catalogue, nested URL rules and the common userinfo vocabulary.

Run ordinary passes and a normal diagnostic path that includes the owned URL. Read the actual unit/table objects and sanitized diagnostic output: every credential location selected by its applicable field/catalogue rule is masked as specified, including the password replacement ***; nonsecret URL structure remains. In JSON table values, *_secret keys are absent at every depth. No clear canary appears in a public output. Check both field-level and catalogue-based callers where the masking contract assigns them; a pure mask vector alone does not prove the process supplied its rules.

Controls: a public URL without credentials is preserved; a common-userinfo-only mask that loses the path canary must fail; a shallow JSON filter must fail a nested *_secret value. Retain only synthetic inputs and masked output.

## RUN-D01 Orphan sweeping preserves a recreated unit's state

Use P/04-R275/R276 and the [unit-state row check](../../common/contracts/row-check.md). Prepare an ordinary named unit with born A and a readable state belonging to A; make its row deletion eligible and confirm that deletion at the store. Run the following separately isolated schedules on both the post-delete cleanup route and the ordinary orphan sweep.

First recreate the same id with born B and write its valid acting state before the sweep reads state. The fresh unit born matches that state, which remains byte for byte with its version. Next let the sweep read the old state and its CAS, then confirm absence of the unit; before the pending state delete is admitted, create B and confirm B's state write. The delete by the earlier CAS is refused and B's confirmed state survives. In the existing-unit/tombstone branch, change that row after its fresh read; the exact-version guard cancels the delete. The stand must observe the state read before the fresh unit read, not merely supply an already orphaned expected object. No guard-of-absence capability is presumed.

Positive controls remove an unchanged proven orphan and advance state_swept_total only for the confirmed delete. Born-matched state and non-orphaned revision-mismatched state are kept. Negative controls delete the newly read B state without a born check, or refresh the state CAS after checking unit absence; both must fail. Record old/new born identities, state versions, admission order, refusal and counter deltas without private state values.

## RUN-D02 Deletion age belongs to the current continuous unit life

Use P/04-R165/R269/R479. Choose a valid fixture with a positive delete_after and a normal named row outside the manual-row and made exceptions. Observe retirement/unplacement long enough to start its timer. Remove the row, let a pass actually observe its tombstone or absence, then recreate its id with a different born and retire/unplace it again. At a time when the former life would already expire but the new life has not completed its delay, the new row remains. Only a complete eligible interval of the new life may lead to deletion, with the fresh checks and guards of R269.

Test retire_when and unplaced.delete_after separately, then both when applicable. Also clear retirement without removing the row, re-enter it, and restart the controller during a running interval. Each restarts the applicable observation count as specified; repeating an unchanged eligible pass does not reset it. Keep clock/event evidence showing the intervening noneligible observation, not only a changed id value. Controls that keep a timer by id across absence/new born, or reset it on every ordinary pass, must respectively fail early-deletion and eventual-deletion checks. Independently exercise the existing manual/made protections; they must not accidentally make every early-deletion slice pass.

## RUN-A01 Ordinary startup enforces the loader and finite profile

Use P/04-R009/R549 and P/02.3-R040/R047/R048/R053. Keep a healthy role socket and ordinary startup environment. Supply a structurally valid manifest whose spread_by names an undeclared field; independent ordinary-load validation establishes the relation failure. The controller refuses startup by the existing load/start outcome before acting on that manifest. A corrected field declaration is the positive control; refusing every manifest is insufficient.

Independently bind the actual catalogue, store Status and declared finite deletion profile used at startup. Remove a required proof or make effective limits unavailable, without altering the ordinary transfer into the process. The existing refusal precedes readiness and control writes; guessed/default body limits cannot stand in for confirmation. A complete provable profile under compatible confirmed limits admits startup. Record exact proof sources and actual Status calls, not just the process's assertion that its own short descriptor list is complete. An unavailable declared transfer/provider leaves that slice NotExecuted; no new profile ABI is required. Controls are a schema-only loader and startup that never asks Status.

## RUN-P01 Recovery finishes the accepted intent before a new decision

Use P/04-R232/R254/R259/R490. Prepare an accepted active intent with fixed members and target, stopped partway through its ordinary removals or additions. Make one required recovery read unavailable or one recovery placement write definitely refused, while unrelated removed/unplaced units could otherwise trigger another decision. Continue the ordinary pass under a confirmed own turn.

Until recovery completes, no new intent replaces the accepted composition, target or rule, and no member is redirected by another decision. Independent steps may continue according to their contracts; their continuation cannot overwrite active intent. Restore the dependency: the same accepted decision completes, old assignments are removed before additions, then a new decision uses a fresh view. Repeat with a new turn holder. A control that overwrites active intent using its current CAS must fail even if its eventual target looks reasonable; a stand that prevents all later triggers does not activate the test.

## RUN-P02 Composition repair admits the whole final group

Use P/04-R023/R237/R243/R517. Prepare a partially placed group whose former target admits its original member but cannot admit all current members. Use separate cases for capacity, spread_by within the group, spread_by across workers of one target server and another declared constraint. Keep manifest revisions, turn and all source reads confirmed, and independently prove each limiting condition.

The ordinary repair first removes the whole group by an intent with target ""; no over-capacity or otherwise forbidden final assignment is published. A later decision may choose a fitting common target or leave the group waiting. No partial capacity admission substitutes for the whole group. A fully fitting group is repaired successfully and a fully placed group without a leaving reason remains placed. Controls that check only assignment byte size or only the first member must fail at the recorded assignment/intent boundary; merely testing a pure group selector does not close this process path.

## RUN-P03 Every new decision sees refreshed candidate facts

Use P/04-R243/R524. Arrange at least two potential decisions in one pass. In one schedule, an earlier confirmed step releases a slot while its old worker heartbeat remains fresh; in another, change capacity, labels, policy or an assignment while intent recovery or turn admission is in progress. Record each dependency confirmation and the subsequent source reads.

The next decision uses the refreshed candidate properties and effects of its predecessor: a released slot is not reused and a changed limiting fact is not bypassed by a pre-turn snapshot. Include a permitted fresh target as a positive control so the stand distinguishes blocked admission from a dead process. If the implementation serializes requests differently, schedule at its observed public boundary; do not require a named snapshot cache. A control that keeps one candidate picture through all decisions must fail a schedule whose old and new eligibility yield different decisions.

## RUN-P04 Failed auxiliary reads are not empty facts

Use P/04-R159/R253/R504/R559 and the [pool contract](../../common/contracts/pool.md). In independent ordinary-pass slices, leave a binding row present but make its required read unconfirmed; fail a required want listing while a retiring/above-want row really exists; and after listing a hold make its required get unreadable or unavailable during decommission-plan preparation. All unrelated sources are healthy.

The missing binding observation cannot permit admission as if affinity did not apply. The unconfirmed want source cannot authorize a plan based on an invented empty set. Decommission pending is not accepted with an incomplete frozen hold/unit list; keep the request standing until the required sources are confirmed. Once restored, the real binding, want and complete metadata affect the plan. Confirmed absence is a separate permissible-input control, not a substitute for failure. Controls that turn list/get failures into empty maps must fail, including the case in which a successful list precedes a failed get. Preserve exact source outcomes and emitted decisions/plans.

## RUN-P05 Ordinary near preference follows declared references

Use P/04-R157 and [near-of](../vectors/near-of/README.md). Supply two valid neighbours with equal of values. Their ids put one first by UTF-8 bytes, but only the other matches a prefer path through a declared reference, such as home.kind. Place them on distinguishable eligible servers and give the new unit otherwise tied choices; independently validate the reference target and field types.

The ordinary pass prefers the holder/server implied by the matching neighbour, rather than losing the nested preference and falling back to the first id. Test a path with more than one reference step and equality/list values within the published grammar. When both match, the ordinary id tie-break applies; no matching holder yields no preference and does not invent a constraint. A control whose pure near function works but whose process supplies no referenced rows must fail. Record actual source accesses and final effective placement.

## RUN-P06 Neighbour preference reads its effective decision

Use P/04-R021/R157 and [observation](../../common/contracts/observation.md). Keep a neighbour's old individual placement on server a while its accepted active intent names a worker on server b. Both targets and heartbeats are valid; the new unit has otherwise tied admissible choices. Observe the ordinary controller's reads and chosen effective placement.

It uses the confirmed active decision, so the preference is b rather than the unfinished old placement at a. Complete the intent to idle and verify the same preference from the completed rows. Change the intent between its first and second reads: an inconsistent snapshot must be retried or withheld by the existing decision-read contract, not taken as an accepted old/new mixture. Also cover no holder and unreadable required decision data. A placement-only reader is the discriminating negative control; merely testing this controller's own current intent is insufficient for a neighbour in the other catalogue subsystem.

## RUN-G01 Label sets share capacity once

Use P/04-R333/R527. Prepare two canonical label sets in known UTF-8 order with pending demand and an eligible worker/server capacity source shared by both. Make ordinary placement remain pending through a separate valid spread constraint so the growth calculation is exercised. Independently compute the report and orders from the declared weights, per, remaining free capacity, free server slots and in-flight processes.

Use separate slices for free worker capacity, free(s) and in flight. Each unit of each resource is credited once, in set order and only up to that set's need; unused remainder reaches the next set. Include demand for which copying the one available unit to both sets would change the second set's workers/ordered/withheld result. Observe real short reports and want writes, not internal allocation structures. Controls with independent per-set copies must fail. Reverse fixture labels and include the empty set first to prove canonical order rather than input order.

## RUN-G02 Growth candidates are specific to the set and place rule

Use P/04-R337/R527. For one pending label set, prepare a server with free slots and a live base whose labels do not satisfy that set, and separately a server already holding a live role worker with servers: distinct and place_by: server. Neither is a candidate for an additional order in the corresponding slice; neither contributes unsuitable in-flight capacity to hide that shortage.

Provide an otherwise eligible alternative and check that orders use it with the published candidate order and bounds; without one the unmet need remains withheld with the existing report/alarm meaning. Change only the failing label/place condition to form a positive control. With place_by from a heartbeat field, do not invent a prohibition based on an as-yet-unknown new process place. Controls that compute one global suitability bit for every label set, or omit distinct/server, must fail by their actual want writes and shortage report.

## RUN-G03 Wanted and exclusive places trigger their own order

Use P/04-R529/R531. Prepare a valid wanted declaration, a matching places row with an inactive hold and a readable wanted row, and no unit rows at all. The ordinary pass includes the weight-1 waiting piece and orders its qualified server out of order with share 1, or uses the empty label set when server_field is empty. Do not manufacture a unit to make the trigger work. A nonmatching place and a confirmed absent wanted row are no-trigger controls; an unreadable wanted row gives no order and a value-free journal line.

Separately bind a waiting unit to an exclusive unheld place. A suitable named server gets the specified share; an empty server_field waits without an order. With `place_error.<place> = sealed` from a live worker on that server, no order is sent and withheld has the normative `"<place_by> <place> is sealed"` meaning. With no live worker there, the ordinary one-order rule applies. Controls driven only by unit rows or ignoring sealed must fail. Keep each slice's other candidate conditions independently true.

## RUN-G04 Retiring does not manufacture shortage

Use P/04-R327/R348/R349/R351/R356 and the shrink forms. Under a complete no-shortage interval, let the ordinary controller select a victim that holds movable units and confirm retiring in its order row. Keep the genuine placeable/waiting inputs stable and all needed destination capacity available through subsequent passes.

Retiring alone does not add those units to waiting, cancel its own shrink or reset the no-shortage timer. The controller continues bounded moves and completes the existing shrink protocol. Change the turn holder after retiring: it continues the same victim. In a separate slice introduce genuine waiting demand before completion: retiring is cancelled by the existing rule and the victim returns to the pool. A control that treats every unit on retiring as waiting must fail the stable-input completion slice. Observe intent/assignment/order transitions; one initial retiring write alone is insufficient.

## RUN-G05 An unconfirmed want write does not become an accepted plan

Use P/04-R052/R113/R339/R340 and [turn barrier](../../common/contracts/turn.md). Prepare either an order increase or a withdrawal after WANT_GRACE. Refuse the target want write with a definite version conflict while confirming the subsequent own-turn barrier; separately lose the write reply and reconcile each possible actual store result. Keep the real want row and its version independently observable.

The barrier confirms the turn, not the want write. Any continued calculation uses a fresh confirmed row/plan; it cannot report ordered/withdrawn capacity, change raise_failed, or spend room solely as if the old proposed write succeeded. A later freshly planned and confirmed operation is allowed. Once the dependency permits a real successful write, the report and subsequent plan reflect that confirmation. Controls that convert the barrier result to want success without a fresh read must fail. Retain request ids/versions, actual admission outcomes and report cycles, including the "reply lost after commit" branch.

## RUN-T01 Resource access uses the ordinary role kit and peer rules

Use P/04-R460 and [object-client](../../common/contracts/object-client.md), [role-certificate](../../common/contracts/role-certificate.md) and [peer](../../common/contracts/peer.md). Prepare the published kit layout only, with the controller's own role leaf/key, trust centres and permitted revocation input. Connect the ordinary controller to an owned HTTPS resource, including loopback where SERVER_NAME supplies the verification name. The valid mTLS path reads real worker/resource objects and permits a lawful decision; successful startup without any resource request is insufficient.

Independently vary wrong trust/name, wrong role, multiple roles, revoked leaf and invalid revocation input while keeping other fields valid. The existing peer/connection refusal occurs without authorized object use; no fallback to system trust or an unauthenticated client makes a bad kit succeed. Verify revocation rereading on a new connection after content change. Off-loopback plain HTTP is refused by the published address rule. Controls accepting any system-trusted peer, checking only x509 without role/revocation, or requiring unpublished kit filenames must fail. Evidence contains public certificates and peer outcomes, never private files or key bytes.

## RUN-E01 Object defaults preserve the configured transport

Use forms/daemon-flags.tsv OBJECTS/PLATFORM_OBJECTS, [env-file](../../common/contracts/env-file.md) and [object-client](../../common/contracts/object-client.md). With an ordinary configstore role socket and neither object variable set, publish valid worker/resource objects at the own resource and observe actual reads through its door: the default is cluster://, and an eligible placement works. Leave a local-file decoy so defaulting silently to file mode is detected.

In independent slices, use explicit valid file:// with owned local objects and require actual get/list results through that mode; a bare file:// uses its specified root. A nonabsolute file address such as file://relative refuses startup with code 2. Exercise both variable names, matching values, and their existing differing-values refusal. Change the own door row after startup and observe the next access using it; an explicit resource address overrides the row. Controls with a permanently empty Door or a once-cached own URL must fail. Missing declared file-mode binding is NotExecuted for that slice, not permission to call unknown a successful read.

## RUN-S01 Unreadable assignments do not erase checked snapshots

Use P/04-R064/R169/R421. First publish a nonempty worker shard from confirmed assignments and units, and save its bytes/version/time. Make that worker's assignment unreadable or its required read unavailable while a later ordinary publication cycle runs. The unchecked source does not become an empty replacement shard, and its units do not become confirmed unplaced merely because that assignment failed to read. Observe attempted writes as well as final objects.

Keep an unrelated checked shard active to prove publication still runs. Restore valid assignment data and verify subsequent lawful publication. A confirmed truly empty assignment is a separate empty-shard control. A control that skips unreadable assignments and then clears every formerly published but unvisited worker shard must fail. Distinguish prewrite failure, where the former shard/time is retained, from an unknown admitted-write result, which does not establish that the old bytes survived.

## RUN-S02 Places-table snapshots publish held_by with its own meaning

Use P/04-R013/R555 and P/06.1-R174. In a valid places table exposed through domain.view_tables, establish an acting hold for a live worker and matching instance. The ordinary table snapshot includes held_by equal to that worker. With a confirmed inactive/absent hold it includes held_by: null. Check both the snapshot row schema and the conditional requirement from the manifest; accepting the field in a generic schema alone does not enforce its presence for places.

Exercise released hold, wrong heartbeat instance, freshness limits, and an unreadable hold or heartbeat using observation's hold outcomes: unknown held_by is null and cannot be treated as confirmed free for decisions requiring that distinction. A non-places table follows its own row requirements rather than acquiring an invented universal held_by obligation. Controls that omit held_by, always write null, or infer a holder from heartbeat place alone must fail. Keep exact observed hold versions/ages and snapshot rows, without replacing unknown by an invented worker.

## RUN-E02 The ordinary launcher parses the published environment language

Use [env-file](../../common/contracts/env-file.md) Grammar/Files and reading order and P/04 lifecycle Environment/Exit codes. Run the ordinary launcher with fresh files and sanitized inherited environment. Cover export KEY=value, a lowercase-legal key, an unquoted value with a trailing space and #, paired quotes without substitution, and duplicate KEY entries whose first value wins. Choose declared observable settings or the implementation's ordinary declared launch boundary to prove effective bytes/precedence; if that boundary cannot expose a key, that slice remains NotExecuted.

Separately introduce CR, BOM, bad UTF-8, NUL, spaces around =, an unpaired quote and an unreadable existing file. Each has the existing startup code 2 with the required file/line diagnostic (file only for unreadability), before the controller acts. Test missing/wrong inherited W2C_ROLE without letting the launcher replace it with the expected role. Confirm the published file-reading order and absent-file skip with valid controls. A shell source, last-duplicate-wins parser, trimming parser or unconditional role overwrite must fail its corresponding slice; do not require a new diagnostic sentence or dump environment values.

## RUN-P07 Capacity is a JSON numeric value, not an integer spelling

Use P/04-R486 and the [pool contract](../../common/contracts/pool.md). Keep the source heartbeat otherwise valid and independently accepted by its family. Encode the same allowed positive integer capacity as 1000, 1000.0 and 1e3 in separate ordinary-pass slices, with all remaining eligibility and reservations equal. A unit whose weight fits that capacity is admitted identically; exponent spelling must not silently become zero.

Include zero, a nonintegral numeric value and other bounds/types according to the existing pool rule, not an invented x-whole restriction on capacity. Test derived unit_mb/base_mb capacity if the fixture declares it. A control that truncates the spelling at a decimal point and feeds it to an integer parser must fail the exponent slice. Record actual heartbeat bytes, the independent numeric interpretation and resulting effective assignment/report; a schema-only check does not establish process consumption.

## RUN-R01 A refused release is a failed control step

Use P/04-R030/R113/R264 and slot-release. Prepare exactly one ordinary release branch with readable gen and no competing renewal, and make its write definitely refused, for example forbidden. Other control reads/writes are healthy and an earlier successful pass establishes last_success.

The slot is not reported as released, no permission version is published, and the current report has ok=false, a failure for that failed step and the existing error meaning; last_success remains the preceding successful time. Other independent steps still run. Restore permission and verify successful release/counters by confirmed store state. A refused-write control that returns only a human outcome while publishing ok=true must fail. A version conflict caused by concurrent renewal is a separate normal rejudgement control and is not relabelled as a new protocol refusal.

## RUN-P08 Distinct-by-server placements remain stable without leaving

Use P/04-R033/R047/R152 and pool place. Prepare two healthy live workers on distinct servers with place_by: server, valid slots/resources and an already placed unit. Keep capacity, policy, drain, decommission and every leaving source stable and eligible. Observe multiple completed ordinary passes and every assignment/intent write: the existing placement stays, no fictitious "no place" leaving reason or alternating move is emitted.

Repeat with no alternative target to detect a spurious alarm instead of a move. Then introduce an actual declared leaving cause and verify its ordinary move, proving the controller is active. With place_by from a heartbeat field, a genuinely empty place follows its existing leaving rule. A control that computes server place for choose but leaves it empty for leaving must fail. Use observable cycle completion, not elapsed wall time alone, to establish that reconsideration opportunities occurred.

## RUN-P09 Rebalance requests use the declared channel and budget

Use P/04-R164. Read the implementation's required declaration of request channel, caller and rebalance budget. A missing mandatory declaration is an observed omission of R164; an unavailable stand binding to an otherwise declared channel is NotExecuted. Bind the ordinary process through that channel and permitted caller without assigning a new public API, algorithm or budget.

With stable healthy placements and no leaving or recovery work, submit a real request while load spread is below dead_band: rebalance emits no moves. In a separate valid fixture with larger spread and independently demonstrated lawful improving moves, submit the request and observe ordinary intents, assignments and the resulting balance under the published obligations. Measure against the declared budget in its own unit and scope; do not turn an operation budget into an invented time limit or demand one specific target. Include no-request and otherwise identical below-band controls, and prove actual delivery of each request. Controls that ignore the request, always rebalance below the band, or merely print success without the ordinary placement effects must fail.

## RUN-R02 Fate since records knowledge, transitions and restart

Use P/04-R119 and [observation](../../common/contracts/observation.md). On a fresh controller, present an occupied unreleased slot with a stable initial fate. Its first pass.fates entry has since=0, the unknown time, rather than its discovery time or a writer timestamp. Record the actual controller-clock interval of its first observed fate transition. For example keep an old unchanged slot below HUNG_MOVE_AFTER, with a live resource, let stale worker observation select hung, then change presence evidence so unsure applies while the slot remains occupied/unreleased.

At each observed change, since is the controller's transition time; repeated passes in the same fate retain it. Changing wall-clock fields without the corresponding fate transition does not fabricate a new start. Restart the controller with the same occupied slot: initial knowledge is again unknown, and age is freshly observed under the ordinary contract. A later real transition starts a new known since. Controls using first sight as since, resetting every pass or carrying since across restart must fail. Do not use since to drive HUNG_MOVE_AFTER; separately confirm that limit is based on unchanged slot-version age. A missing clock binding leaves exact-time assertions NotExecuted.

## RUN-R03 Name conflicts count distinct fresh contender names

Use P/04-R128 and observation's CONTENDER_FRESH. Through the own resource, present multiple contender marks for one valid name, another name with a fresh unreadable mark, a name whose observed mark is stale, and marks under "-". The controller's current pass counts distinct names with any fresh contender mark: duplicate boxes of one name count once, the fresh unreadable mark counts, stale-only names and "-" do not. Establish ages in this controller's memory; a pre-aged console is not the observer.

Check first sight, a changed version with the same body, the same version with misleading at, and ages just below, at and above CONTENDER_FRESH. At equality the mark is fresh. Confirmed removal updates the current count; old cumulative conflicts do not persist as the current value. Restart starts observation afresh. Controls that count marks instead of names, ignore unreadable marks, trust at, hardcode zero or accumulate earlier passes must fail. Save key/version histories and report cycles; exact-boundary slices require the qualified clock binding.

## RUN-R04 Imported resource forms and unknown control reads stay distinct

Use P/04-R113/R491, observation and the P/05 resource-heartbeat/doors schemas and outcomes. Start with complete valid heartbeat/door sources and independently check their family-reader outcomes. In a stale-worker, old-slot slice below HUNG_MOVE_AFTER, a valid live resource reporting runs permits hung; changing only a schema/build field with a field-level unknown outcome leaves the heartbeat readable. A whole-heartbeat error, such as server not matching its key, confirms no resource life or process presence; with a fresh door version its state is unreachable and the corresponding unsure fate is observed. Verify door-family failure separately: an unreadable door source does not make its server an order candidate by substituting absent fields.

With ordinary cluster://, make this controller's own resource unavailable while a control operation requires its object inputs. The reads are unknown, not confirmed absent, and pass.ok=false; they cannot authorize dependent admission or cleanup by an invented empty observation. Keep error handling in the existing vocabulary. Restore the resource and observe confirmed input consumption and a successful later pass. Test readable, unreadable, unavailable and confirmed-absent sources separately, including return of the same version; invalid input must not refresh life merely because it was fetched again. Controls accepting every JSON object as a heartbeat, collapsing field-unknown to whole-row failure, or treating unknown as an empty successful read must fail.

## Existing J vector coverage

The common vector obligations remain in J: forms/targets.routing.tsv names P/04/vectors-* routes with scenarios=all, and Platform/common/vectors/consumers.tsv names every table assigned to consumer 04-controller. Independently enumerate those consumer rows and compare their package/table identities with the declared profile and actual invocations through Platform/common/vectors/wire.tsv. A missing command, skipped table or nonzero vector invocation cannot be hidden by a short self-authored package list or by local property tests. The existing routes include crl, family-read, instance, journal, log-mask, loopback, object-client, pool, revoked, secret-in, store-client, turn and values-by-type. No new Q invocation ABI is added; these are existing J obligations. A completeness control that removes one assigned binding must be detected before a whole-stage PASS.
