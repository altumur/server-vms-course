# P/04 — Controller: norms

This English text is the source; the Russian translation `ru/spec/04-controller.norms.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The canon of the lesson. Lecture (`ru/04-controller.md`, for people, not in the export), [instructions](04-controller.README.md), [life cycle](../lifecycle.md),
vectors [`order`](../vectors/order/README.md),
[`shrink-victim`](../vectors/shrink-victim/README.md) and [`shrink-allowed`](../vectors/shrink-allowed/README.md). The lesson has no HTTP contract of its own (`P/04 no-openapi`): the doors through
which the operator talks to the controller are the doors of the console ([P/06.6](../../06-console/spec/06.6-console.norms.md) N2; `/where` — [chapter 6.5](../../06-console/spec/06.5-console.norms.md)). Current source dependencies are the [observation contract](../../common/contracts/observation.md), the current data families below, and the linked console doors. Requirement and checklist identifiers are retained; the acceptance files define the full completion boundary.

## Index

| Topic | Requirements | Files |
|---|---|---|
| `input_owners` | P/04-R003, P/04-R004, P/04-R005, P/04-R006, P/04-R024, P/04-R076, P/04-R459, P/04-R460 | `forms/README.md`, `lifecycle.md`, `Platform/common/data/catalog.tsv` |
| `time_fields` | P/04-R002, P/04-R076, P/04-R087, P/04-R089, P/04-R091, P/04-R094, P/04-R107, P/04-R113, P/04-R174, P/04-R217 | `Platform/common/contracts/env-file.md`, `Platform/common/contracts/observation.md` |
| `turn_fence` | P/04-R026, P/04-R032, P/04-R036, P/04-R038, P/04-R069, P/04-R209, P/04-R212, P/04-R222 | `Platform/common/contracts/turn.md`, `data/placement-turn.schema.json` |
| `intent_read` | P/04-R020, P/04-R021, P/04-R076, P/04-R214, P/04-R217, P/04-R500 | `Platform/common/contracts/observation.md`, `data/placement-intent.schema.json` |
| `admission_reserve` | P/04-R022, P/04-R023, P/04-R149, P/04-R155, P/04-R232, P/04-R243, P/04-R288, P/04-R517, P/04-R520, P/04-R521 | `data/placement-intent.schema.json`, `Platform/common/contracts/pool.md` |
| `intent_commit` | P/04-R027, P/04-R036, P/04-R037, P/04-R038, P/04-R243, P/04-R244, P/04-R245, P/04-R246, P/04-R247, P/04-R248, P/04-R253, P/04-R254, P/04-R259, P/04-R301, P/04-R490, P/04-R517, P/04-R520, P/04-R521 | `Platform/common/contracts/turn.md`, `data/workers.schema.json` |
| `group_atomicity` | P/04-R023, P/04-R029, P/04-R156, P/04-R235, P/04-R237, P/04-R239, P/04-R245, P/04-R246, P/04-R247, P/04-R261 | `Platform/common/contracts/group-of.md`, `data/placement-intent.schema.json` |
| `placement_key_size` | P/04-R028, P/04-R031, P/04-R250 | `data/placement-intent.schema.json`, `forms/refusals.tsv` |
| `manifest_revision` | P/04-R058, P/04-R076, P/04-R094, P/04-R116, P/04-R212, P/04-R214, P/04-R262, P/04-R405, P/04-R560 | `data/placement.schema.json`, `data/placement-turn.schema.json`, `data/placement-intent.schema.json` |
| `pool_labels` | P/04-R005, P/04-R034, P/04-R081, P/04-R083, P/04-R150, P/04-R152, P/04-R160, P/04-R287, P/04-R288, P/04-R337, P/04-R566 | `Platform/common/contracts/labels.md`, `Platform/common/contracts/pool.md` |
| `home_preference` | P/04-R158, P/04-R268, P/04-R290 | `Platform/common/contracts/pool.md` |
| `near_preference` | P/04-R034, P/04-R133, P/04-R157, P/04-R262 | `vectors/near-of/README.md`, `Platform/common/contracts/pool.md` |
| `affinity_places` | P/04-R159, P/04-R288, P/04-R334, P/04-R527, P/04-R528, P/04-R529, P/04-R531 | `Platform/common/contracts/pool.md` |
| `choice_ranks` | P/04-R033, P/04-R035, P/04-R151, P/04-R286, P/04-R287, P/04-R288, P/04-R290, P/04-R291, P/04-R292, P/04-R566 | `Platform/common/contracts/pool.md`, `data/placement.schema.json` |
| `slot_observation` | P/04-R014, P/04-R015, P/04-R039, P/04-R046, P/04-R196, P/04-R197, P/04-R208, P/04-R313 | `Platform/common/contracts/observation.md`, `forms/slot-fate.tsv` |
| `release_permission` | P/04-R040, P/04-R041, P/04-R042, P/04-R043, P/04-R044, P/04-R045, P/04-R046, P/04-R117, P/04-R119, P/04-R198, P/04-R310, P/04-R311, P/04-R318 | `forms/slot-fate.tsv`, `forms/slot-release.tsv`, `data/controller-pass.schema.json` |
| `leaving` | P/04-R035, P/04-R047, P/04-R048, P/04-R267, P/04-R287, P/04-R322 | `forms/README.md`, `Platform/common/contracts/pool.md` |
| `placeable_set` | P/04-R025, P/04-R162, P/04-R163, P/04-R165, P/04-R325, P/04-R327, P/04-R479, P/04-R481, P/04-R563, P/04-R566 | `vectors/order/README.md`, `vectors/shrink-allowed/README.md` |
| `unit_cleanup` | P/04-R025, P/04-R120, P/04-R124, P/04-R134, P/04-R269, P/04-R276 | `Platform/common/contracts/row-check.md`, `data/controller-pass.schema.json` |
| `order_absolute` | P/04-R050, P/04-R052, P/04-R107, P/04-R339, P/04-R355, P/04-R356, P/04-R494, P/04-R541 | `vectors/order/README.md`, `data/want.schema.json` |
| `growth_room` | P/04-R085, P/04-R330, P/04-R332, P/04-R333, P/04-R337, P/04-R357 | `vectors/order/README.md`, `Platform/common/contracts/presence-lock.md` |
| `shortage_estimate` | P/04-R053, P/04-R130, P/04-R139, P/04-R149, P/04-R325, P/04-R327, P/04-R334, P/04-R527, P/04-R528, P/04-R529, P/04-R531, P/04-R532 | `vectors/order/README.md`, `data/controller-pass.schema.json` |
| `want_deadline` | P/04-R107, P/04-R131, P/04-R191, P/04-R329, P/04-R330, P/04-R340, P/04-R356, P/04-R482, P/04-R562 | `forms/runtime-constants.tsv`, `data/want.schema.json` |
| `shrink` | P/04-R051, P/04-R111, P/04-R194, P/04-R327, P/04-R341, P/04-R343, P/04-R348, P/04-R349, P/04-R350, P/04-R351, P/04-R352, P/04-R353, P/04-R482, P/04-R499, P/04-R563 | `forms/README.md`, `vectors/shrink-victim/README.md`, `vectors/shrink-allowed/README.md` |
| `decommission_plan` | P/04-R054, P/04-R055, P/04-R056, P/04-R089, P/04-R091, P/04-R094, P/04-R359, P/04-R361, P/04-R363, P/04-R369, P/04-R371, P/04-R495, P/04-R504, P/04-R558, P/04-R559 | `data/decommission-pending.schema.json`, `data/decommissioned.schema.json` |
| `decommission_release` | P/04-R094, P/04-R101, P/04-R376, P/04-R378, P/04-R381 | `data/decommission-pending.schema.json`, `Platform/common/contracts/turn.md` |
| `decommission_cleanup` | P/04-R094, P/04-R103, P/04-R384, P/04-R385, P/04-R386, P/04-R387, P/04-R388, P/04-R390, P/04-R392, P/04-R393, P/04-R395, P/04-R507, P/04-R510, P/04-R511, P/04-R513 | `data/decommission-pending.schema.json`, `Platform/common/contracts/turn.md` |
| `decommission_finish` | P/04-R054, P/04-R055, P/04-R056, P/04-R091, P/04-R094, P/04-R105, P/04-R353, P/04-R395, P/04-R399, P/04-R401, P/04-R403, P/04-R404, P/04-R495, P/04-R558, P/04-R559 | `data/decommissioned.schema.json`, `data/decommission-pending.schema.json` |
| `snapshot_fields` | P/04-R011, P/04-R064, P/04-R137, P/04-R167, P/04-R168, P/04-R169, P/04-R170, P/04-R413, P/04-R415, P/04-R417, P/04-R498, P/04-R548, P/04-R549, P/04-R561, P/04-R564 | `data/snapshot.schema.json`, `data/snapshot-unplaced.schema.json` |
| `snapshot_ceiling` | P/04-R068, P/04-R171, P/04-R182, P/04-R419, P/04-R421, P/04-R560, P/04-R564 | `forms/refusals.tsv`, `data/snapshot.schema.json` |
| `table_snapshot` | P/04-R012, P/04-R013, P/04-R062, P/04-R174, P/04-R175, P/04-R177, P/04-R178, P/04-R181, P/04-R182, P/04-R183, P/04-R411, P/04-R412, P/04-R555, P/04-R556, P/04-R560, P/04-R564 | `data/snapshot-tables.schema.json`, `forms/runtime-constants.tsv` |
| `report_cycle` | P/04-R007, P/04-R008, P/04-R113, P/04-R124, P/04-R134, P/04-R137, P/04-R139, P/04-R142, P/04-R279, P/04-R560, P/04-R562, P/04-R565 | `data/controller-pass.schema.json`, `forms/README.md` |
| `startup_schema` | P/04-R059, P/04-R060 | `forms/daemon-flags.tsv`, `lifecycle.md`, `Platform/common/contracts/schema.md` |
| `power_pull` | P/04-R016, P/04-R017, P/04-R065, P/04-R066, P/04-R202, P/04-R203, P/04-R204, P/04-R205, P/04-R206, P/04-R207, P/04-R208, P/04-R430, P/04-R431 | `Platform/common/contracts/observation.md`, `lifecycle.md` |
| `refusals` | P/04-R067, P/04-R068, P/04-R564 | `forms/refusals.tsv` |

In N5 and the checklists, `sc. NN` or `scenario NN` denotes a numbered scenario, and an `s…` identifier denotes a CALL seam; these are acceptance evidence names of this lesson unless another owner is named. A paragraph starting with «**Scope: production.**» applies only to production qualification; every unmarked requirement remains mandatory for every implementation. The checklist marks `[test]`, `[reading]` and `[stand]` have the meanings of P/01.1-R151.

## N0 Vocabulary

<!-- req: P/04-R001 -->

Normative keywords (MUST, MUST NOT, SHOULD, MAY by RFC 2119 and RFC 8174) follow the [course canon](../../common/NORMATIVE-TERMS.md).

<!-- req: P/04-R070 -->

The rules of the module are [P/01.1 N0](../../01-store/spec/01.1-store.norms.md#n0-vocabulary).

<!-- req: P/04-R069 -->

The [common production obligations](../../common/contracts/production-obligations.md) apply to this owner. MB4: a turn protects guarded store mutations only; external actions require their owner-declared independent fence. Q4 retry ownership and Q5 bounded resources also apply.

## N1 Form

<!-- req: P/04-R002 -->

**Time.** The time fields of the rows and objects of the lesson are time by [the canon of N0 of P/01.1](../../01-store/spec/01.1-store.norms.md#time-in-a-row): `<sub>/placement/<id>` — `at`; `platform/doors/<host>` — `since`, `at`; `platform/drain` — `at`; `platform/decommission/<host>` — `at`; `<sub>/decommissioned/<host>` — `asked_at`, `at`; `<sub>/decommission-pending/<host>` — `asked_at`, `at`; `<sub>/controller/placement_intent` — `at`; `<sub>/want/<host>` — `at`; the object `<sub>/controller/pass` — `at`, `last_success`; the object `<sub>/snapshot/<worker>` — `ts`.

<!-- req: P/04-R003 -->

**Data** ([catalogue](../../common/data/catalog.tsv)):
- owns: `<sub>/placement/<id>`, `<sub>/workers/<name>`, `<sub>/want/<host>`, `<sub>/decommissioned/<host>`, `<sub>/decommission-pending/<host>`, `<sub>/controller/placement_turn`, `<sub>/controller/placement_intent`, `<sub>/controller/pass`, `<sub>/snapshot/<worker>`, `<sub>/snapshot/unplaced`, `<sub>/snapshot-tables/<table>`;
- writes: `<sub>/slots/<name>` (cas), `<sub>/<manifest:unit.rows>/<id>` (delete), `<sub>/<manifest:domain.books.from>/<slot>` (delete), `<sub>/state/<name>/<id>` (delete), `<events root>/audit/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` (append), `<events root>/audit.alarms/<role>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` (append), `<events or objects root>/<path>/%h<sha256>.name` (create), `<objects root>/<dir>/~lock` (create);
- reads: `platform/manifest/<sub>`, `platform/manifest/<sub>/rev`, `<sub>/heartbeats/<name>`, `<sub>/slots/<name>`, `<sub>/holds/<place>`, `<sub>/<manifest:unit.rows>/<id>`, `<sub>/state/<name>/<id>`, `platform/schema`, `platform/resources/<server>/heartbeat`, `<sub>/policy`, `platform/servers/<host>`, `platform/doors/<host>`, `platform/drain`, `platform/decommission/<host>`, `<sub>/<manifest:tables>/<name>`, `/etc/w2c/tls/<role>/server.key`.

<!-- req: P/04-R004 -->

The tables of places and links (`places.table`, `places.wanted`, `affinity.table`, N1.3) and the tables `domain.view_tables` (N1.3b) the controller reads as rows `<sub>/<manifest:tables>/<name>`.

<!-- req: P/04-R459 -->

The controller writes the journal `unit.unplaced_deleted` (N3 pass step 8) and alarms (`workers.raise_failed` in N1.4; hung/unsure in step 3) to `audit/<role>` and `audit.alarms/<role>`; it writes `%h<sha256>.name` by the [event journal contract](../../common/contracts/event-journal.md), `journal`, `writer`, «File names».

<!-- req: P/04-R460 -->

The controller uses the key of its own kit for resource doors over HTTPS ([P/02.4 N1.6](../../02-installer/spec/02.4-installer.norms.md), `roles`).

<!-- req: P/04-R005 -->

The rows `<sub>/policy`, `platform/servers/<host>`, `platform/drain`, `platform/decommission/<host>` (written by the console, P/06.6) and `platform/doors/<host>` (written by the resource, P/05) are given in N1.1 in the form that the controller reads; the owner of the row is the writer process (catalogue).

### N1.1 Controller rows

<!-- req: P/04-R006 -->

The controller and imported rows use the forms and field rules below. For unreadable-family outcomes, the smallest numeric priority applies; all equal-priority rows act in file order by the outcome-selection rule of common/LAYERS.md §7.

<!-- req: P/04-R076 -->

**`<sub>/placement/<id>`**: — a decision; the writer is the controller. **`<sub>/placement/<id> — worker`**: \<worker name\> | "" — "" — not placed; with an active intent the common decision of N1.5 applies. **`<sub>/placement/<id> — reason`**: \<a string for a human\> — non-empty; grammar — N3 «Reason». **`<sub>/placement/<id> — at`**: \<wall seconds of the controller\>. **`<sub>/placement/<id> — rev`**: \<decimal integer ≥ 1\> — +1 on every write. **`<sub>/placement/<id> — manifest_rev`**: \<revision of the manifest under which the decision was taken\> — required for the current decision; a missing value is unreadable, never stamped (P/02.3)

<!-- req: P/04-R078 -->

**`<sub>/workers/<name>`**: — an assignment; derived from the placement rows. **`<sub>/workers/<name> — units`**: \<list of ids by the list rule of P/06.1 N1.2 (comma-separated, otherwise a JSON array)\> — sorted. **`<sub>/workers/<name> — rev`**: \<decimal integer ≥ 1\> — +1 only when the list changes

<!-- req: P/04-R081 -->

**`<sub>/policy`**: — the writer is the console; the controller reads it. **`<sub>/policy — servers`**: shared | distinct — another value or key on read — the manifest default; on write — a refusal

<!-- req: P/04-R083 -->

**`platform/servers/<host>`**: — the writer is the console. **`platform/servers/<host> — labels`**: \<comma-separated labels\> — "" — none; the row beats the node labels

<!-- req: P/04-R085 -->

**`platform/doors/<host>`**: — the writer is the resource of the server; the form — P/05 N1.4 door_row (family doors). **`platform/doors/<host> — room.<sub>, live.<sub>`**: — the controller reads them — free(s) N3 «shortage()»; the element is absent, does not read or is unknown — the server is not an order candidate

<!-- req: P/04-R087 -->

**`platform/drain`**: — the writer is the console; one row per cluster. **`platform/drain — server`**: `<server>`; at: `<moment>`

<!-- req: P/04-R089 -->

**`platform/decommission/<host>`**: — the writer is the console. **`platform/decommission/<host> — by`**: `<who>`; at: `<moment>`; why: `<words>`; gone: "true"? — gone — the confirmation «there is no server» when the resource was never heard

<!-- req: P/04-R091 -->

**`<sub>/decommissioned/<host>`**: — the writer is the controller; removed when the request is withdrawn. **`<sub>/decommissioned/<host> — asked_at, at`**: \<wall seconds of the console request and of the controller mark\>. **`<sub>/decommissioned/<host> — slots, units, holds`**: names of the released slots, ids of the removed units, and places of the holds, by the list rule of P/06.1 N1.2; "" means none. Elements are slot names (P/03.2 N1.4), unit ids (P/06.1 N1.3), and hold-place names (P/03.2 N1.3), respectively. These are names, not counts; "0" is not an element.

<!-- req: P/04-R094 -->

**`<sub>/decommission-pending/<host>`**: — unfinished controller progress, never the final decommission mark. **`<sub>/decommission-pending/<host> — state`**: prepared | cleaning | finalizing. **`<sub>/decommission-pending/<host> — request_index`**: `<version>` — exact fixed platform/decommission/`<host>` index. **`<sub>/decommission-pending/<host> — asked_at, at`**: `<time>` — request at and plan acceptance time. **`<sub>/decommission-pending/<host> — manifest_rev`**: `<revision>`. **`<sub>/decommission-pending/<host> — remaining`**: [{name: \<slot name\>, index: `<version>`}, ...] — JSON; original versions, no later substitution. **`<sub>/decommission-pending/<host> — from`**: [\<owned from prefix\>, ...] — fixed full prefixes, each ending in /

<!-- req: P/04-R101 -->

**`<sub>/decommission-pending/<host> — released, skipped`**: [\<slot name\>, ...]. **`<sub>/decommission-pending/<host> — current`**: [\<slot name\>, ...] — at most BATCH_WRITES - 1, the confirmed release chunk

<!-- req: P/04-R103 -->

**`<sub>/decommission-pending/<host> — cleanup_index`**: "" | `<version>` — empty means the progress row's own index, before its first cleanup rewrite. **`<sub>/decommission-pending/<host> — slot_cursor, from_cursor`**: `<count>` — next current slot and its next from prefix

<!-- req: P/04-R105 -->

**`<sub>/decommission-pending/<host> — units, holds`**: `<lists>` — fixed final-mark metadata, same form as decommissioned

<!-- req: P/04-R107 -->

**`<sub>/want/<host>`**: — the writer is the controller, cas with the guard placement_turn (N1.5). **`<sub>/want/<host> — want`**: \<decimal 1…WANT_NUM_MAX\> — the absolute target of the number of role processes on the server, the base `<prefix>`-`<server>`-1 is included. **`<sub>/want/<host> — at`**: \<moment of the write\> — diagnostics; the terms — by the observation of the row version (N1.4 terms). **`<sub>/want/<host> — by`**: \<controller instance\> — diagnostics; the authority — cas and the guard placement_turn. **`<sub>/want/<host> — why`**: \<non-empty reason\> — grammar N3 «shortage(), order()…»

<!-- req: P/04-R111 -->

**`<sub>/want/<host> — retiring?`**: optional worker name chosen for shrinking (N3 «shrink»).

<!-- req: P/04-R499 -->

The row `<sub>/want/<host>` exists, except while pending/finally decommissioned, for an installed role on a server of a manifest with `grows: true` (N3 «order row»). Only decommission of the server or removal of the role deletes this row; shrinking writes want 1. The controller and console read the row (`workers_wanted`, P/06.5).

### N1.2 Pass report

<!-- req: P/04-R007 -->

The object `<sub>/controller/pass` is written at the end of every pass; it is read by the console (the series `<sub>_reconcile_last_pass_age_seconds`, `<sub>_reconcile_pass_seconds`, `<sub>_reconcile_failures`, `<sub>_units_unplaced`, `<sub>_units_diverged` — P/06.5 N3 «/metrics — text») and by the workers (`names_given`, `hung_move_after` — P/03.2). The pass report MUST contain the fields below; an implementation MAY add its own counters.

<!-- req: P/04-R008 -->

The pass report uses all fields and field meanings specified below.

<!-- req: P/04-R113 -->

**`pass — at`**: \<moment the control part ends, before snapshot publication\>. **`pass — ok`** is boolean: true means the control part reached its end, all control inputs were read and no control write was refused; otherwise false. **`pass — error`** is the text of the last error or "". **`pass — failures`** is the number of failures. **`pass — last_success`** is the moment of the last successful control part. **`pass — seconds`**: \<duration of the control part, excluding later snapshot/report publication\>

<!-- req: P/04-R116 -->

**`pass — manifest_rev`** is the manifest revision of this controller. **`pass — manifest_behind`** counts rows whose writes this pass postpones because the manifest lags; count each row once per pass.

<!-- req: P/04-R560 -->

For the JSON objects of this lesson, the implementation chooses whitespace and object-key order; these choices are not judged. The pass writer also chooses the schema-admissible string or integer notation of manifest_rev; the exact revision value is judged without loss of precision. The complete actual serialization still determines every byte limit; this freedom does not impose JCS or change any normative array order.

<!-- req: P/04-R117 -->

**`pass — names_given`**: {\<slot name\>: \<version of the slot row at which the name is given\>}

<!-- req: P/04-R118 -->

**`pass — hung_move_after`**: \<seconds of the hang limit in force at this controller\>

<!-- req: P/04-R119 -->

**`pass — fates`** is `{<name>: {fate, server, why, rev, since}}` for occupied, unreleased slots only: holder is nonempty and released is false, neither true nor taking (slot contract, States). In each `pass.fates` entry, `since` is the moment the slot entered this fate on this controller’s clock: fate change resets since; first sight of the slot is not this moment.

<!-- req: P/04-R120 -->

**`pass — diverged`**: \<assignments fixed by sync\>. **`pass — unplaced`**: \<units without a worker, except those taken out of service\>. **`pass — garbled`**: \<unit rows that do not read\>. **`pass — expired_kept`**: \<manual rows with a passed deadline that the deadline removed but did not delete: a target with fixed fields or about not by id (N3 «pass()» step 8)\>

<!-- req: P/04-R124 -->

**`pass — snapshot_state_garbled`**: \<unit states not included in the snapshot shard of this cycle: the state row does not read by its type (N1.3a; P/03.6 N1.7 unreadable)\>. **`pass — state_swept_total`**: \<state rows removed by the sweep of the orphaned and after the delete of the unit row (N3 step 8a)\>. **`pass — snapshot_tables_refused`**: \<tables of N1.3b that this cycle replaced with a stub: the object is larger than SNAPSHOT_TABLE_MAX\>. **`pass — snapshot_rows_garbled`**: \<unit rows not included in the snapshot shard of this cycle: a field of snapshot does not read by its type (N1.3a garbled)\> — P/01.1 N0 «Stability of output»

<!-- req: P/04-R128 -->

**`pass — reach_moves_total, slots_released_total, unplaced_deleted_total, servers_decommissioned_total, workers_hung, workers_hung_moved_total, workers_unsure_moved_total, name_conflicts`**: `<numbers>`

<!-- req: P/04-R129 -->

**`pass — unplaceable`**: {`<id>`: `<why>`} — units without a place in this pass and a non-empty reason; the console takes why from it for /unplaceable and reason 404 /where/`<id>` of an unplaced one (N2.2)

<!-- req: P/04-R130 -->

**`pass — short`**: — only with placement.grows: true; an element for each label set with waiting ones - {labels: [`<labels>`], units: \<exact nonnegative integer sum of waiting unit weights\>, workers: \<processes needed beyond the live ones and the capacity in flight\>, groups: \<waiting groups\>, ordered: \<ordered by this pass\>, withheld?: \<words why it is not ordered\>} labels — the canonical notation: unique labels ascending, a repeat collapses; groups — always, 0 too (required in the form); own counters of the element MAY be added by the existing count form; standard fields keep their forms; acceptance compares the named fields; an empty set in the words of why is any labels; a set without a computable per is the same element: workers 0, ordered 0, withheld «no positive capacity estimate»; the series `<sub>`_workers_withheld{labels} (P/06.5 /metrics) — for each set of the pass report, zero too

<!-- req: P/04-R131 -->

**`pass — wants`**: {`<server>`: {want, live, pending, retiring?, why, state}} — only with grows: true; live — the live role processes of the server, pending — in flight(s) by heartbeats (N3); state: ok | raising | raise_failed | no_base. **`pass — raise_failed`**: {`<server>`: {since, times}} — the server «failed to raise»: since — the moment the order was withdrawn, times — in a row

<!-- req: P/04-R562 -->

Select `wants.<s>.state` in this order: no_base when the base process is not live; otherwise raise_failed while the server is excluded for RAISE_QUIET after a confirmed order withdrawal; otherwise raising when heartbeat-derived pending is positive; otherwise ok. The diagnostic raise_failed.{since,times} and its reset remain P/04-R340. A missing base is never included in pending.

<!-- req: P/04-R133 -->

**`pass — near_waiting`**: [`<subsystem>`…] — only with placement.near whose near.sub is not in the manifest catalogue of this pass: the affinity waits for its installation (N1.3 near); otherwise there is no field

<!-- req: P/04-R134 -->

The current reader and writer both require expired_kept, snapshot_state_garbled and state_swept_total as nonnegative count values. If `expired_kept`, `snapshot_state_garbled` or `state_swept_total` is missing or invalid in the current pass report, use the existing unreadable outcome for those required counters. In the pass report, `expired_kept` and `snapshot_state_garbled` belong to the current cycle; `state_swept_total` accumulates confirmed deletions from zero in this process.

<!-- req: P/04-R137 -->

The current snapshot reader and writer both require exactly one admissible unit.rows array, including an empty array; missing or multiple arrays are unreadable. Absence of the snapshot object before its first publication is separate from an unreadable current snapshot object.

<!-- req: P/04-R139 -->

Weight aggregates short[].units, waiting and load are exact nonnegative integers without a common.uint53 ceiling; their JSON output has integer notation and never rounds or saturates through binary64/int64. Individual weights/capacities and other count fields keep their forms. Custom short counters keep count; widening the aggregate changes no full serialized-object write limit.

<!-- req: P/04-R142 -->

A cycle ends its control part and releases the placement turn, then attempts the unit snapshots and table snapshots, and finally writes one pass report containing the snapshot counters of that same cycle. At, seconds, last_success, ok and failures describe only the control part. Snapshot errors keep their own existing outcomes/logs/counters and do not become control failures. The three snapshot counters start at zero for each cycle; the next cycle cannot reset or absorb an unfinished prior cycle. After publication attempts return their confirmed, refused, failed or unconfirmed outcomes, write the final report once, without later patching it. state_swept_total is not reset.

### N1.3 Placement keys and their meaning

<!-- req: P/04-R009 -->

The form of the keys is P/02.1 (N1.2). Here — what each of them means for the controller, and the default. Placement keys have the meanings and defaults specified below; their input form is owned by P/02.1.

<!-- req: P/04-R486 -->

**`capacity: {from, default, unit_mb, base_mb}`.** capacity — [the pool contract](../../common/contracts/pool.md) `capacity`; the reason — the field `fates.<worker>.why` of the pass report (N1.2). Default: `from: capacity`; `default` is required.

<!-- req: P/04-R148 -->

**`headroom: {from}`.** headroom — a heartbeat field that the subsystem names; the controller does not read it (neither the choice, nor the slot fate, nor the pass report); the console shows it — the series `worker_headroom{worker,server}` and `headroom` ([P/06.5](../../06-console/spec/06.5-console.norms.md) N3 «/metrics — text»). Default: `from: headroom`.

<!-- req: P/04-R149 -->

**`weight: {field, default}`.** the weight of a unit — an `int` field of the row ≥ 1, when the field is absent — weight.default ≥ 1; a wrong present value is not replaced with default: the unit row is unreadable (`garbled` of the pass report), the unit is neither placed nor removed, the reason is in `unplaceable`; the load = Σ of the weights. Default: without the key — weight 1 for all.

<!-- req: P/04-R150 -->

**`constraint`.** `none` \| `labels-subset`: the labels of the unit ⊆ the labels of the worker. The labels of the unit — its field `labels` of type `list` (no field — an empty set, the constraint holds); a label — by [the label alphabet](../../common/contracts/labels.md); the labels of the worker — the row `platform/servers/<host>` or the node labels. Default: `none`.

<!-- req: P/04-R566 -->

Label reachability and out of reach apply only with constraint: labels-subset (P/04-R150). With constraint: none, a label mismatch alone does not move or unplace a unit and does not make it waiting or create shortage.

<!-- req: P/04-R151 -->

**`tie_break`.** `most-free-capacity` — the only word. Default: the same.

<!-- req: P/04-R152 -->

**`servers`.** `shared` \| `distinct`: with `distinct` only one worker can carry the units on one place — the one with the largest load, on equality the first in the slot order of P/03.2 N1.4; the others stay idle. Default: `shared`; the row `policy` overrides. **`place_by`.** what counts as a place with `distinct` — [the pool contract](../../common/contracts/pool.md) `place`, the keeper — `keeper`; `distinct` units are given only to the keeper of a non-empty place. Default: `server`.

<!-- req: P/04-R154 -->

**`places: {table, where, server_field, lease, wanted}`.** the table of places and the hold row `<sub>/holds/<place>` (P/03.2 N1.3); `lease: strict` — a strict place; `wanted` — a table of the subsystem: a row with the name of a place says that the place needs a holder, the reason is known to the subsystem (N3 «shortage()»). Default: —.

<!-- req: P/04-R155 -->

**`spread_by`.** a field: two units with one value are not on one server; an absent or empty value does not take part in the spreading — a unit without a value neither constrains nor is constrained (a pair to `group_by`: empty is not a group). Default: —.

<!-- req: P/04-R156 -->

**`group_by: {field, cut_at}`.** a group — one value of the field (for `url` — the host by `cut_at: host`); it is placed only whole on one worker. What a group is, the host in one spelling, `none`, an unreadable host, «not in a group» and the refusal — [the contract of the group by host](../../common/contracts/group-of.md) (vector [`group-of`](../../common/vectors/group-of/README.md)). Default: —.

<!-- req: P/04-R157 -->

**`near: {sub, by, of, prefer}`.** a preference: beside the holder of a neighbour — the units of the subsystem `sub` (the manifest catalogue). Default: `none`. **`near: {sub, by, of, prefer}`.** My value — the field `by` of my row, without `by` — my id; the value of a neighbour — its field `of`, without `of` — its id; the neighbours — the live rows of `sub` whose value equals mine. **`near: {sub, by, of, prefer}`.** Among several neighbours first those that matched `prefer` — AND over the fields, OR over a list of values; a field value is a scalar (equality) or a list (as `affinity.strict`); a field of `prefer` is a path: a segment through `.` is a step along a reference field of the neighbour to the row it names (`home.kind` — the field `kind` of the row named by the field `home` of the neighbour); among equals — by the id of the neighbour (UTF-8 bytes). **`near: {sub, by, of, prefer}`.** The worker holding the chosen neighbour is preferred; no holder — no preference (vectors [`near-of`](../vectors/near-of/README.md)). **`near: {sub, by, of, prefer}`.** The manifest `sub` is not in the catalogue — the affinity does not apply, the unit is placed without it, the controller does not need the rows of `sub`; the subsystem is in `near_waiting` of the pass report (N1.2); the affinity is switched on from the pass at which the manifest `sub` appeared in the catalogue (N3 «pass()» step 1)

<!-- req: P/04-R158 -->

**`home`.** a preference, not a filter: a field of the row naming the home (the value — of the first member in UTF-8 order; no value — no home), or `near` — the home is at the neighbour; only one side of a pair can follow. Default: —. **`home`.** The field is a reference `ref` to the table of places `places.table`: the home is the holder of the named place, the worker whose place (`place_by`, the pool contract `place`) is the name of this row; there is no holder among the eligible (N3 «choose») — the workers of the server from the field `places.server_field` of this row, if the field is non-empty; otherwise there is no home. **`home`.** An empty server field does not hinder the home when there is a holder: the home is the holder (a volume without a server). **`home`.** Another worker of the same server, when there is a holder, is not the home: a unit at it moves to the holder (N3 «pass()», step 7). **`home`.** The reason: `place_by` names where the data of the unit lie; a comparison with the server would give it to the holder of another place of this server, and step 7 would not bring it back. **`home`.** No row or it does not read — no home. **`home`.** A field without `ref` — its value is the server itself: the home is the workers whose `server` equals the value. **`home`.** A `ref` to another table (or the manifest has no `places`) — no home: the value is the id of a foreign row, not a server, and `places.server_field` is not named for it.

<!-- removed: P/04-R472 by ADR-0133 -->

<!-- req: P/04-R159 -->

**`affinity: {field, table, server_field, strict, exclusive}`.** a filter: a place from the table that admits the unit; `admits: false` takes nobody; a binding row leads the unit only to its own place. Default: —. **`affinity: {field, table, server_field, strict, exclusive}`.** The place of the unit is the row of `table` named by its `field` (no value or no row — affinity does not apply). **`affinity: {field, table, server_field, strict, exclusive}`.** `strict` is a predicate that selects the binding rows: a row is binding when each field of `strict` equals the value or is in the list of values (AND over the fields, OR over a list); no `strict` or `{}` — all rows of the table bind, there are no non-binding ones. **`affinity: {field, table, server_field, strict, exclusive}`.** A binding row leads the unit only to the holder of its place — the worker whose place (`place_by`, P/03.2 N1.3) is the name of the row; with a non-empty `server_field` of the row — also only if the server of the worker is that one (both conditions; another worker of the same server with another place does not fit); a non-binding one is a preference for the server `server_field`, not a filter. **`affinity: {field, table, server_field, strict, exclusive}`.** `admits` is checked at the actual place of the unit. **`affinity: {field, table, server_field, strict, exclusive}`.** `exclusive: true` (only with `strict`, P/02.1) — the binding place is exclusive: its holder admits only the units bound to this place, the others are not placed on it (as `admits` for strangers); a worker with such a place takes no other places (P/03.2 N3 «place: take, hold, let go»); a binding row with an empty `server_field` — strictness by the holder of the place without a check of the server

<!-- req: P/04-R160 -->

**`requires`.** `none` \| `resource`: with `resource` a worker is eligible only while the resource of its server is not silent. Default: `none`.

<!-- req: P/04-R161 -->

**`grows`.** `true` — the role grows on demand: the controller counts the shortage and orders processes of the role per server with the row `<sub>/want/<host>` (N3 «shortage(), order()…»). Default: `false`.

<!-- req: P/04-R162 -->

**`retire_when: {state?, field, in, delete_after?}`.** a unit with a value of the field from `in` is not placed and is removed with the value as the reason. Default: —. **`retire_when: {state?, field, in, delete_after?}`.** Without `state` the field is one of the unit row; with `state` — a field of the value of the acting state `unit.state.<state>` (the row-check contract «Unit state» acts; no acting one — not finished).

<!-- req: P/04-R479 -->

**`retire_when: {state?, field, in, delete_after?}`.** `delete_after` — N s after the removal by `retire_when`, by the clock of the controller, delete the row (N3 step 8): the count starts from the first pass at which the controller saw the unit removed by `retire_when`; a pass at which it is no longer removed (an operator edit removed the value or the acting state) clears the count, a new removal counts anew; after a restart of the controller the count starts anew, as for `unplaced.delete_after`

<!-- req: P/04-R163 -->

**`ends: {field, never}`.** the deadline of a unit: the field `field` of the row (Unix seconds) ≠ `never` and not later than the clock of the controller — the unit is not placed, is removed with the reason `ends`, the row is deleted (N3 step 8); `never` — no deadline. Default: without the key — no deadline; `never: 0`.

<!-- req: P/04-R164 -->

**`rebalance: {dead_band}`.** rebalancing on request: while the spread of the load is smaller — do not move. Default: `0.10`. The implementation declares the request channel, caller and rebalance budget in its description. Production qualification measures rebalance against that declared budget.

<!-- req: P/04-R165 -->

**`unplaced: {delete_after}`.** a unit row that nobody holds for longer than N s by the clock of the controller is deleted by the controller; one removed by `retire_when` too: nobody holds it. Default: without the key — never. **`unplaced: {delete_after}`.** For a table with `fixed` fields (except the field that is the source of the id) or with `about` not by id, only the rows with `made` are physically deleted (the name is held by the template `key` of the customer, P/03.6 N1.6) — likewise by `retire_when.delete_after` and `ends`; the deadline does not delete the manual rows of such a table: `ends` removes them and does not place them, `delete_after` does not delete them, the counter `expired_kept` of the pass report; the operator deletes them through a door.

<!-- req: P/04-R481 -->

**`unplaced: {delete_after}`.** The worker of the subsystem MAY also delete its own unit rows by the key `worker.deletes` — a delete with `cas` without the write right

### N1.3a Snapshot

<!-- req: P/04-R011 -->

Unit snapshot objects use the envelope, content and publication rules below. **`<sub>/snapshot/<worker> | <sub>/snapshot/unplaced`**: — objects; the writer is the controller; the worker name unplaced is a refusal {cluster, worker: `<name>` | null, ts, `<rows>`: [{id, revision, \<fields of snapshot:\>, state?, worker, server}]} worker: the worker name of the shard; null — for the shard unplaced and for the shard of a gone worker. **`<sub>/snapshot/<worker> | <sub>/snapshot/unplaced — cluster`**: the installation name — CLUSTER of the environment (the environment file contract «Environment variables»; the name of a domain member, [P/08.1](../../08-domain/spec/08.1-domain.norms.md) N1.1); not set — "local" (outside a domain)

<!-- req: P/04-R167 -->

**Unit snapshot fields.** The manifest snapshot list chooses fields: without that key include all fields except *_secret, blob and an author field server; [] includes none of those fields, while id, revision, worker and server remain. A secret, blob or server named explicitly in the snapshot list makes the manifest fail to load.

<!-- req: P/04-R548 -->

Unit snapshot addresses use the P/06.2 N1.1a output mask, the same as the console: password → ***.

<!-- req: P/04-R549 -->

Declared unit fields cannot include platform_fields of P/06.1 N1.2, including deleted/worker: the P/02.1 loader refuses such a manifest. unit.rows must differ from cluster, worker and ts; collision with the snapshot envelope is the P/02.1 load refusal refused:form.

<!-- req: P/04-R168 -->

**Unit snapshot state.** With declared unit.state, state maps names to acting state values under the row-check contract, Unit state, as P/06.1 N2 State in the answer. Use state.\<name\> from the manifest snapshot list; without snapshot include all states except cursor, [] includes none; no acting value means no name, and no names means no state field. If a state row does not read by its type, include the unit in the snapshot without that state and increment snapshot_state_garbled of the pass report.

<!-- req: P/04-R169 -->

**`<sub>/snapshot/<worker> | <sub>/snapshot/unplaced — publish`**: after the control part releases turn and before this cycle's one final report (N3 «pass()»); the shards of gone workers — empty; without units — an empty unplaced an empty shard has one form for all: {cluster, worker: null, ts, `<rows>`: []} — the field `<rows>` is present, the list is empty (as the witness)

<!-- req: P/04-R561 -->

The implementation chooses the order of unit entries in a worker or unplaced shard; that order is not judged. The required membership, fields and types are unchanged. This freedom does not change the table-snapshot key order of P/04-R175.

<!-- req: P/04-R170 -->

**`<sub>/snapshot/<worker> | <sub>/snapshot/unplaced — garbled`**: a unit row whose snapshot field does not read by its type by values_by_type P/06.1 N1.2 is not included in the shard; the shard is published with the other units, a log line once per series and the counter `snapshot_rows_garbled` of the pass report N1.2 (P/01.1 N0 «Stability of output»)

<!-- req: P/04-R171 -->

Before a unit-shard write, the controller checks the P/05 resource door limit L. It does not calculate the store max_bytes: the store enforces that limit on put; a store TooLarge has the same N4 outcome, leaving the former shard. Unit-shard size is the byte count of its complete serialized object, including the envelope, empty shards and the actual ts notation, whose length counts. Exactly L bytes is allowed; above L return TooLarge before put_durable, without replacing the former shard. For this size refusal, diagnostics are "N units on \<shard\>; snapshot is B bytes, limit is L bytes"; raising OBJECTS does not lift the resource door limit.

### N1.3b Table snapshot

<!-- req: P/04-R012 -->

The domain view shows the units with `domain.ref`; the other unit rows and the console tables of a foreign cluster are not visible to the domain without this object. A manifest without `domain.ref` and a unit without a value of `ref` are visible here.

<!-- req: P/04-R013 -->

Table snapshot objects use the envelope, content and publication rules below. **`<sub>/snapshot-tables/<table>`**: — an object; the writer is the controller; `<table>` — a key of domain.view_tables of the manifest (P/02.1, P/08.1 N1.4a): a table of tables or unit.rows {cluster, ts, refused?, rows: [{key, revision, fields, secrets?, labels?, about?, worker?, server?, phase?, status?}]}. **`<sub>/snapshot-tables/<table> — cluster`**: as for a shard, N1.3a

<!-- req: P/04-R174 -->

**`<sub>/snapshot-tables/<table> — ts`**: the moment of the object write. Compare the candidate object with the last confirmed published object without ts: cluster, refused and rows must match, including presence or absence of refused. If they match, do not write and keep the former ts; a new ts alone never causes a write. A CLUSTER change or a transition between a too_large stub and an ordinary object requires publication even when rows match. Liveness is not ts but members[].state of the view.

<!-- req: P/04-R175 -->

**`<sub>/snapshot-tables/<table> — rows`**: store rows, the order — key in UTF-8 bytes; key — the row name (P/06.1 N1.6) or the unit id, revision — the row version (P/06.1 N2 «Row revision»); a removed row and a tombstone are not in rows. **`<sub>/snapshot-tables/<table> — fields`** contains only the manifest domain.view_tables list; values use their own type by values_by_type P/06.1 N1.2. An absent source field stays absent, without a default.

<!-- req: P/04-R555 -->

In a table snapshot, held_by of a places table follows P/06.1 N1.6 held_by.

<!-- req: P/04-R556 -->

Table snapshot addresses use the mask of P/06.2 N1.1a. Cut *_secret keys from JSON field values at every depth (P/06.2 N1.4); the manifest list itself does not name *_secret fields (P/02.1).

<!-- req: P/04-R177 -->

**`<sub>/snapshot-tables/<table> — secrets`**: the names of the *_secret fields of the row with a non-empty value, ascending in UTF-8 bytes; none such — no field; no values: the domain needs to know whether a secret is set

<!-- req: P/04-R178 -->

**`<sub>/snapshot-tables/<table> — labels, about`**: only for unit rows — the field labels and the value of the field about.field of the manifest, whether the list names them or not: the right judges by them (the right contract «Judgement by target»); no value — no field. **`<sub>/snapshot-tables/<table> — worker, server`**: only for unit rows — from the assignment; no assignment — no fields. **`<sub>/snapshot-tables/<table> — phase, status`**: only for unit rows — phase and the fields domain.view_status of the manifest from the element status[] of the heartbeat of this unit (P/08.1 N1.4 status); no element — no fields

<!-- req: P/04-R181 -->

**`<sub>/snapshot-tables/<table> — garbled`**: a row whose field from the list does not read by its type is not included in rows; the counter snapshot_rows_garbled, as N1.3a garbled

<!-- req: P/04-R182 -->

**`<sub>/snapshot-tables/<table> — ceiling`**: SNAPSHOT_TABLE_MAX from forms/runtime-constants.tsv of the full serialized object; more — instead of the object a stub {cluster, ts, refused: "too_large", rows: []} and snapshot_tables_refused of the pass report (N1.2). A stub, not the former object: an old snapshot would look alive. The agent owns per-member and combined table budgets (P/09.1 N1.2 tables_budget and its linked P/08 admission bounds); this controller introduces no second member count, camera count or measured domain-wide byte ceiling.

<!-- req: P/04-R183 -->

**`<sub>/snapshot-tables/<table> — scope`**: the object exists for a manifest with domain.view_tables; domain.ref is not needed for it; the key removed from the manifest — the object is not removed, the agent no longer carries it (the report intake contract member_objects). **`<sub>/snapshot-tables/<table> — reader`**: only the domain agent (P/09.1 N1.2); the cluster console reads its own tables as rows

### N1.4 Terms and states of the judge

<!-- req: P/04-R014 -->

The deadlines and budgets below use their named source contracts or `forms/runtime-constants.tsv`. **`constants — LOST_AFTER`**: the observation contract «Freshness» (the value is there) — heartbeat freshness («within the last LOST_AFTER») and the margin after SLOT_TERM of observing an unchanged slot version. **`constants — HUNG_MOVE_AFTER`**: the environment file contract «Constants and units» (the value is there) — s; the age of the observed slot version up to the hung/unsure/wait limit; from the environment of the controller, published in the report

<!-- req: P/04-R187 -->

**`constants — ALIVE_EVERY`**: the observation contract «Resource state» (the value is there) — the resource rewrites at of its door

<!-- req: P/04-R188 -->

**`constants — REACH_BUDGET`**: the environment file contract «Constants and units» (the value is there) — units per pass for moves by reachability; from the environment

<!-- req: P/04-R189 -->

**`constants — WRITE_CONFLICT_LIMIT`**: forms/runtime-constants.tsv — consecutive conflicts of one logical change; after the limit the existing step fails, not an extra attempt; barriers remain

<!-- req: P/04-R190 -->

**`constants — HOME_BUDGET`**: forms/runtime-constants.tsv — unit per pass for moves home

<!-- req: P/04-R191 -->

**`constants — WANT_GRACE`**: forms/runtime-constants.tsv — s; an order the server has not raised is withdrawn (N3 «withdraw on deadline»). **`constants — RAISE_QUIET`**: forms/runtime-constants.tsv — s; a server that «failed to raise» gets no orders. **`constants — RAISE_FAILS_LOUD`**: forms/runtime-constants.tsv — failures in a row — the alarm workers.raise_failed of raised severity

<!-- req: P/04-R194 -->

**`constants — SHRINK_AFTER`**: the environment file contract «Constants and units» (the value is there) — s; without a shortage — shrinking (N3 «shrink»); only on the stand — W2C_SHRINK_AFTER=`<seconds>` of the environment of the controller: with the variable set, the controller writes a loud journal line at start; outside the stand the variable is not set. **`constants — SHRINK_BUDGET`**: forms/runtime-constants.tsv — unit per pass for a move from the worker being shrunk (as HOME_BUDGET)

<!-- req: P/04-R482 -->

the terms of the order and of shrinking are starting values of the policy; the count is by the local monotonic clock of the controller from the first observation of the order row version (for SHRINK_AFTER — from the first pass without a shortage), a new controller starts from 0, a repeated write of the same target does not extend the term, at is diagnostics. WANT_GRACE — from the first pass where in flight(s) > 0 (N3), reset — when in flight(s) = 0: the order is raised, then the process of the number died without a change of the row version — the count is from the pass where the number is in flight again, not from the former version

<!-- req: P/04-R196 -->

**`resource_state`**: — the resource of a server — live | unreachable | unknown | silent: one definition for all observers (the controller, the console) by their monotonic clocks, the rules in order — the observation contract (common/contracts/observation.md «Resource state»); only silent excludes and moves

<!-- req: P/04-R197 -->

**`process_presence`**: — what the resource says about the process of a worker: the output of [P/05 N1.4](../../05-resource/spec/05-resource.norms.md) `presence` by the key `<sub>`/\<slot name\> of its subsystem; only from the heartbeat of a resource in the state live: a stale heartbeat with the word runs gives no presence, and the slot is judged by resource_state; an absent one of the fields workers, running, unknown is an empty list (a partial set: running without workers — runs, workers without running — gone) runs | gone | unlisted | unknown — unknown — an unconfirmed read; silent — only the resource state above

<!-- req: P/04-R198 -->

**`fate`**: alive | wait | hung | hung_moved | unsure | unsure_moved | move | release. **`NAME_FATES`**: [move, hung_moved, unsure_moved, release] — + wait beyond the limit HUNG_MOVE_AFTER. **`MOVED_FATES`**: [move, hung_moved, unsure_moved]

<!-- req: P/04-R015 -->

The observation of a version, the freshness `LOST_AFTER` («within the last LOST_AFTER» — one relation `≤`) and `resource_state` are [the observation contract](../../common/contracts/observation.md); here — what they mean for the judge and the pool of the controller (N3 «choose», «fate»).

### N1.4a Server failure: the move

<!-- req: P/04-R016 -->

The server-failure outcomes and fresh-controller observation are specified below. **`power_pull — moves`**: units — by two silences (the heartbeat of the worker and the word of the resource), by the tolerances of N3; (SLOT_TERM + LOST_AFTER) + a pass — a guide for a sound stand with heartbeats known in advance, an available store and capacity, not a general deadline; the new holder takes the next epoch; the same with shared and distinct; it does not move back by itself, except a declared `home` (N3 «pass()», step 7, HOME_BUDGET)

<!-- req: P/04-R202 -->

**`power_pull — stays`**: the archive on the volume of the server — under the old epoch, unavailable until the return, not rebuilt, not lost; the units of a hung live worker — stay with it (one writer)

<!-- req: P/04-R203 -->

**`power_pull — lost`**: the open bucket and the closed buckets without a confirmed mirror copy; one vote of the group. An RPO of a bucket length is admissible only with a confirmed mirror of all closed ones; otherwise the loss is larger

<!-- req: P/04-R204 -->

**`power_pull — store`**: 1 of 3 — an election in seconds; 2 of 3 — 503 unavailable after the effective P/01 -leader-wait, the workers live on the last assignment by the lease and unconfirmed_max; recovery — recover by hand (P/01.3 N3 «recover the store (no majority)»)

<!-- req: P/04-R205 -->

**`power_pull — restore`**: P/05 N1.4 «Bucket restore»

<!-- req: P/04-R206 -->

**`power_pull — return`**: the resource pulls the buckets; the workers take free names; a name with an expired slot — only by the word of the controller (P/03.2)

<!-- req: P/04-R207 -->

**`power_pull — presence`**: the presence lock contract (common/contracts/presence-lock.md)

<!-- req: P/04-R208 -->

**`fresh_controller`**: what is seen for the first time has just changed; it moves nothing for the first LOST_AFTER (N3 «pass()», step 0). This limits judgements by silence and by terms; a confirmed gone from a live resource is positive evidence and takes precedence, the race is closed by CAS

<!-- req: P/04-R017 -->

`stays`, `lost`, `store` and `return` describe the server failure outcomes; the procedure «pull the power» is in N3.

### N1.5 Placement admission between controllers

<!-- req: P/04-R209 -->

A subsystem has one controller changing the placement at each moment. The right is set by a row, not by the presence of a process: late writes of the former holder are cut off by the store guard.

<!-- req: P/04-R210 -->

The two service rows `<sub>/controller/placement_turn` and `<sub>/controller/placement_intent` belong to the controller role; placement readers also read these two rows. The store doors and the vocabulary of operations remain P/01.1.

<!-- req: P/04-R212 -->

The placement turn and intent use the row forms below. **`<sub>/controller/placement_turn`**: — a row; the writer is the controller. **`<sub>/controller/placement_turn — holder`**: \<unique mark of the capture attempt\> | "" — a new attempt does not repeat the mark of the former one. **`<sub>/controller/placement_turn — manifest_rev`**: \<manifest revision\> — does not decrease; an old controller does not capture a new revision

<!-- req: P/04-R214 -->

**`<sub>/controller/placement_intent`**: — a row; it is not deleted after creation. **`<sub>/controller/placement_intent — state`**: active | idle. **`<sub>/controller/placement_intent — manifest_rev`**: \<revision of the accepted decision\>. The fields `members`, `target`, `reason` and `at` below belong to an active `placement_intent`; `manifest_rev` is required in both states.

<!-- req: P/04-R217 -->

**`<sub>/controller/placement_intent — members`**: \<JSON array of all ids of the decision; unique, sorted\>. **`<sub>/controller/placement_intent — target`**: \<worker name\> | "" — one target of the whole group; "" — remove the placement. **`<sub>/controller/placement_intent — reason`**: \<non-empty reason\>. **`<sub>/controller/placement_intent — at`**: \<wall seconds of taking the decision\>

<!-- req: P/04-R222 -->

**`constants — TURN_TERM, TURN_RENEW`**: the writer turn contract «Terms»

<!-- req: P/04-R020 -->

An unreadable turn/intent row is a refusal of the placement change with failures, not an empty row. An intent row out of form (`state` is not `active`/`idle`; an active row lacks `members`, `target`, `reason`, `at`, or their values are out of form) is unreadable: placement change is refused with failures at the controller; the readers (`/where`, `/unplaceable`, label forecasts) return 503 `unavailable`, not idle.

<!-- req: P/04-R500 -->

Initial absence of the turn and intent rows is admissible; after creation neither of these two rows is deleted. Turn keeps the lower bound of manifest_rev, idle is kept so that the version of intent does not return to the version of absence between two reads; the readers below need this.

<!-- req: P/04-R021 -->

An active intent is an accepted common decision for members while the individual placement and workers are being brought to it. For each of its ids the target/reason/at/manifest_rev of the intent decide; the other ids are decided by their own placement. A reader (/where, unplaceable, forecasts and the controller) reads the decision by [the observation contract](../../common/contracts/observation.md) «Reading the decision: intent → placement → intent». With idle, all rows of the completed decision have already been brought to it.

<!-- req: P/04-R022 -->

For admission the load of a target is counted conservatively: the sum of the weights of the unique ids already assigned to it **or** directed there by the effective decision. Double counting of one id at one worker is excluded; an old assignment not yet removed keeps the room at the former worker. The same aggregate is counted for spread_by. An active intent reserves all members at target even before workers. The indicators of the actual assignment are still counted by workers; the reserve is a condition of admission, not a statement that the unit already runs.

<!-- req: P/04-R232 -->

Before a new admission an unfinished intent is completed.

<!-- req: P/04-R023 -->

A group is admitted by one intent with all its members from a fresh look and one common target; the preferences are chosen by the first id in UTF-8 order, the constraints and the weight — by all members. The workers never get the assignments of the members of this operation at different targets at the same time: first all former assignments of all members are removed, then the members are added to one target. An intermediate absence of a part of the assignments is admissible and is repaired; a partial decision on capacity is not.

<!-- req: P/04-R235 -->

Changes of the unit fields, the group composition, the capacity, the policy and the life after the look are processed by the next pass: they are not atomic with the admission. With unchanged inputs the competition of controllers does not exceed the capacity, does not violate spread_by and does not split a group.

<!-- req: P/04-R237 -->

If after a change of composition a group is placed only partially and does not fit whole on the former target, it is first removed whole by an intent with target ""; it waits or chooses a new common target by the next decision. A fully placed group is not reconsidered without a reason to leave.

<!-- families:begin -->
### Data families (built from the standard files)

The form of the rows and objects that the chapter owns by the [catalog](../../common/data/catalog.tsv) is the JSON Schema 2020-12 of the family. An instance of a row is `{key, row}`, of an object `{key, object}`; the key is the grammar of the column `key` of the catalog. The fields of `row` are the values of `items` after the [codec](../../common/data/codec.tsv): the writer checks the schema and its `$defs.writer`, the reader the schema (layer 3 — the words `x-*` of the schema). Unreadable — the row did not decode or did not pass the schema in the reader's mode; the outcome is by the table of outcomes of the family: the path is a prefix of the path of the refusal (empty — the whole row); with several paths of refusal the outcome of the least priority applies.

#### `<sub>/placement/<id>` — row

Schema — [`placement.schema.json`](../data/placement.schema.json), outcomes — [`placement.outcomes.tsv`](../data/placement.outcomes.tsv); form version 1; norm — P/04 N1.1, N1.5.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `worker` | string; matching `([a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*)?` in full | required |  | the worker name — a slot name, P/03.2 N1.4 (`<prefix>-<suffix>`; prefix of its own manifest — a check of the lesson, not of the form); "" — not placed |
| `reason` | string | required |  | The current nonempty human reason, required for readers and writers (P/04 N3 Reason). |
| `at` | time (P/01.1 N0 «Time in a row») | required |  | the controller's wall-clock seconds at the moment of the decision |
| `rev` | string; matching `[1-9][0-9]*` in full | required |  | a decimal integer ≥ 1; +1 for each write of the row |
| `manifest_rev` | string; matching `[1-9][0-9]*` in full | required |  | Required manifest revision under which the current intent completion wrote this decision. A missing value is unreadable and is never stamped or repaired; newer-revision protection remains P/04 N3 manifest_rev. |

Reader and writer bounds (`$defs.writer`, applied by root `allOf`):

| Key | Also |
|---|---|
| `reason` | not one of: `""` |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable: the controller — an error of a pass step (failures + 1), the unreadable is not replaced by absence and is not rewritten as unplaced (N3 «pass()»: «data from such a read are not replaced by empty ones»); the cause goes to the log | 0 | row | P/04 N3 «pass()» |
| the whole row | `console` | the whole row is unreadable: the effective placement (/where, /unplaceable, label forecasts) — an unconfirmed read, not «not placed» | 0 | row | P/04 N1.5 |

#### `<sub>/workers/<name>` — row

Schema — [`workers.schema.json`](../data/workers.schema.json), outcomes — [`workers.outcomes.tsv`](../data/workers.outcomes.tsv); form version 1; norm — P/04 N1.1.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `units` | list, without repeats, element — string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | required |  | ids of the assigned units by the list rule of P/06.1 N1.2 (comma-separated, otherwise a JSON array; codec array), sorted; "" — none |
| `units[]` | string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | optional |  | the unit id (P/06.1 N1.3); a numeric id — also by this grammar |
| `rev` | string; matching `[1-9][0-9]*` in full | required |  | a decimal integer ≥ 1; +1 only when the list changes |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable: the worker is not in the pool, does not enter garbled of the pass report (N4 «heartbeat/slot/assignment is unreadable») | 0 | row | P/04 N4 |
| the whole row | `<s>worker` | the whole row is unreadable: the worker reading its own assignment does not change its set of units (takes no new ones, does not give away the ones held by this row), the log | 0 | row | P/03.3 N3 «loop()» step 2 |
| the whole row | `console` | the whole row is unreadable: drain — `GET /drain` 503 `unavailable` | 0 | row | P/06.6 N1.2 |

#### `<sub>/want/<host>` — row

Schema — [`want.schema.json`](../data/want.schema.json), outcomes — [`want.outcomes.tsv`](../data/want.outcomes.tsv); form version 1; norm — P/04 N1.1.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `want` | integer; ≥ 1; ≤ 99 | required |  | the absolute target of the number of processes of the role on the server, the base `<prefix>-<server>-1` is included; maximum WANT_NUM_MAX is defined by P/04 forms/runtime-constants.tsv; numeric minimum/maximum carriers stay unchanged. |
| `at` | time (P/01.1 N0 «Time in a row») | required |  | the moment of the write; diagnostics — the terms go by the observation of the row version (N1.4 terms) |
| `by` | string | required |  | the controller instance; diagnostics — the authority is given by cas and the guard placement_turn |
| `why` | string | required |  | a non-empty reason; the grammar of N3 «shortage(), order()…» |
| `retiring` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | optional |  | the worker chosen for shrinking (N3 «shrink»); a slot name, P/03.2 N1.4 |

Only at the writer (`$defs.writer`):

| Key | Also |
|---|---|
| `why` | not one of: `""` |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable: the unreadable is not replaced by absence and is not rewritten: an error of step 9 (failures + 1), the order rules (retiring, «number above want») are not applied to the processes of the server (the pool contract want_rule), the cause goes to the pass log | 0 | row | P/04 N3 «pass()»; pool contract want_rule |
| the whole row | `console` | the whole row is unreadable: there is no series workers_wanted{server} of this server, the server's script starts and stops nothing by it (P/02.4 N1.5) | 0 | row | P/06.5 N3 «/metrics — text» |

#### `<sub>/decommissioned/<host>` — row

Schema — [`decommissioned.schema.json`](../data/decommissioned.schema.json), outcomes — [`decommissioned.outcomes.tsv`](../data/decommissioned.outcomes.tsv); form version 1; norm — P/04 N1.1.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `asked_at` | time (P/01.1 N0 «Time in a row») | required |  | wall-clock seconds of the console request (`platform/decommission/<server>` at) |
| `at` | time (P/01.1 N0 «Time in a row») | required |  | wall-clock seconds of the controller's mark |
| `slots` | list, element — string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | names of the given-away slots by the list rule of P/06.1 N1.2; "" — none; names, not a number |
| `slots[]` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | optional |  | the name of the given-away slot, P/03.2 N1.4 |
| `units` | list, element — string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | required |  | ids of the removed units by the list rule of P/06.1 N1.2; "" — none |
| `units[]` | string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | optional |  | the id of the removed unit, P/06.1 N1.3 |
| `holds` | list, element — string | required |  | the hold places by the list rule of P/06.1 N1.2; "" — none |
| `holds[]` | string | optional |  | the name of the hold place, P/03.2 N1.3 (`<sub>/holds/<place>`) |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable: the controller does not remove or rewrite the mark at revocation, the cause goes to the pass log; the mark of the subsystem about.sub, near.sub or ref of the unit being placed is unreadable — the server is not confirmed for this placement: not a candidate, a step error (failures + 1), the cause goes to the log; it counts neither as decommissioned nor as not decommissioned | 0 | row | P/04 N3 «choose(unit)»; P/04 N1.1 |
| the whole row | `<s>domain` | the decommission row of its own server is unreadable: at the start it does not take a name until it reads, the cause goes to the log without the value | 0 | row | P/03.7 N1.6 start; P/03.2 N3 «start()» step 3 |
| the whole row | `<s>worker` | the decommission row of its own server is unreadable: at the start it does not take a name until it reads, the cause goes to the log without the value | 0 | row | P/03.2 N3 «start()» step 3 |
| the whole row | `console` | the whole row is unreadable: `/servers` — `decommissioned: null` (the general rule of output: a field with an unreadable source — null, if required) | 0 | row | P/06.6 N2.1; P/04 N3 «decommission_server» |

#### `<sub>/decommission-pending/<host>` — row

Schema — [`decommission-pending.schema.json`](../data/decommission-pending.schema.json), outcomes — [`decommission-pending.outcomes.tsv`](../data/decommission-pending.outcomes.tsv); form version 1; norm — P/04 N1.1; N3 decommission_server.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `state` | string; one of: `prepared`, `cleaning`, `finalizing` | required |  | prepared: release the next original candidates; cleaning: remove contributions for the confirmed current release chunk; finalizing: publish the final mark last |
| `request_index` | string; not one of: `""` | required |  | the immutable index of platform/decommission/\<host> for this plan |
| `asked_at` | time (P/01.1 N0 «Time in a row») | required |  | at of the fixed console request |
| `at` | time (P/01.1 N0 «Time in a row») | required |  | the controller time at plan acceptance |
| `manifest_rev` | string; matching `[1-9][0-9]*` in full | required |  | the manifest revision used to freeze the owned from prefixes |
| `remaining` | list, without repeats, element — map `{name, index}`; in `items` — a JSON text (x-encoding: json) | required |  | ordered immutable slot names and original observed versions still to release; never replace a version after conflict |
| `remaining[]` | map `{name, index}` | optional |  |  |
| `remaining[].name` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | the name of the given-away slot, P/03.2 N1.4 |
| `remaining[].index` | string; not one of: `""` | required |  | the exact opaque store version; compare only for equality |
| `from` | list, without repeats, element — string; matching `[a-z][a-z0-9_-]{0,31}/[a-z][a-z0-9_-]{0,31}/` in full | required |  | distinct ordered owned family prefixes from this manifest domain.books declarations; full prefixes including final slash; never a foreign subsystem |
| `from[]` | string; matching `[a-z][a-z0-9_-]{0,31}/[a-z][a-z0-9_-]{0,31}/` in full | optional |  |  |
| `released` | list, without repeats, element — string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | slot names confirmed released by this plan, in release order; historical names, never an authority to touch a later holder |
| `released[]` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | optional |  | the name of the given-away slot, P/03.2 N1.4 |
| `skipped` | list, without repeats, element — string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | original candidates whose version changed; never reread/adopt a newer version for release |
| `skipped[]` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | optional |  | the name of the given-away slot, P/03.2 N1.4 |
| `current` | list, at most 63 items, without repeats, element — string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | the current atomic release chunk; at most BATCH_WRITES-1 slots; exact shared release index from cleanup_index or the progress row index |
| `current[]` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | optional |  | the name of the given-away slot, P/03.2 N1.4 |
| `cleanup_index` | string | required |  | empty only before the first progress rewrite of a confirmed release chunk: then the progress row index is the exact release index; otherwise its preserved value, never a later slot reread |
| `slot_cursor` | integer; ≥ 0; ≤ 9007199254740991 | required |  | zero-based current slot being cleaned; compared with current length by the procedure |
| `from_cursor` | integer; ≥ 0; ≤ 9007199254740991 | required |  | zero-based next from prefix for the current slot; conflict discards the remainder of this slot |
| `units` | list, element — string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | required |  | final mark metadata fixed before plan acceptance: ids of the removed units by the list rule of P/06.1 N1.2; "" — none |
| `units[]` | string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | optional |  | the id of the removed unit, P/06.1 N1.3 |
| `holds` | list, element — string | required |  | final mark metadata fixed before plan acceptance: the hold places by the list rule of P/06.1 N1.2; "" — none |
| `holds[]` | string | optional |  | the name of the hold place, P/03.2 N1.3 (`<sub>/holds/<place>`) |

Rules:

- `<root>`: if `state` — `prepared`: `current` — also any value; `cleanup_index` — also one of: `""`; `slot_cursor` — also one of: `0`; `from_cursor` — also one of: `0`; `remaining` — also any value.
- `<root>`: if `state` — `finalizing`: `current` — also any value; `cleanup_index` — also one of: `""`; `slot_cursor` — also one of: `0`; `from_cursor` — also one of: `0`; `remaining` — also any value.
- `<root>`: if `state` — `cleaning`: `current` — also any value; `from` — also any value.

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the progress row is unreadable: do not infer completion, recreate the plan, release slots or delete contributions; keep progress and final mark unchanged, record a step error and retry only after a readable source is restored | 0 | row | P/04 N1.1; N3 decommission_server, progress and recovery |

#### `<sub>/controller/placement_turn` — row

Schema — [`placement-turn.schema.json`](../data/placement-turn.schema.json), outcomes — [`placement-turn.outcomes.tsv`](../data/placement-turn.outcomes.tsv); form version 1; norm — P/04 N1.5.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `holder` | string | required |  | a unique mark of the capture attempt or "" — the turn is free; a new attempt does not repeat the mark of the previous one |
| `manifest_rev` | string; matching `[1-9][0-9]*` in full | required |  | the manifest revision (P/02.3 N1.5 rev); does not decrease — an old controller does not capture a new revision |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable: a refusal of the placement change with failures and a cause, not an empty row; without a new admission; restore the service row | 0 | row | P/04 N1.5, N3 «get and hold the placement turn» step 1, N4 |

#### `<sub>/controller/placement_intent` — row

Schema — [`placement-intent.schema.json`](../data/placement-intent.schema.json), outcomes — [`placement-intent.outcomes.tsv`](../data/placement-intent.outcomes.tsv); form version 1; norm — P/04 N1.5.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `state` | string; one of: `active`, `idle` | required |  | active — the decision is still being carried through; idle — all rows of the completed decision have been carried through |
| `manifest_rev` | string; matching `[1-9][0-9]*` in full | required |  | the manifest revision of the decision made |
| `members` | list, without repeats, element — string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full; in `items` — a JSON text (x-encoding: json) | optional |  | a JSON array of all ids of the decision; unique, sorted (the order is a rule of the lesson, not of the form); only when active |
| `members[]` | string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | optional |  | the id of a unit of the decision (P/06.1 N1.3) |
| `target` | string; matching `([a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*)?` in full | optional |  | one target of the whole group — a worker name (slot, P/03.2 N1.4); "" — remove the placement; only when active |
| `reason` | string | optional |  | A nonempty human reason when state is active, for reader and writer alike. The idle form does not require reason. |
| `at` | time (P/01.1 N0 «Time in a row») | optional |  | wall-clock seconds of making the decision; only when active |

Rules:

- `<root>`: if `state` — `active`: required `members`, `target`, `reason`, `at` (the path is the missing key); `reason` — also any value; not one of: `""`.

Only at the writer (`$defs.writer`):

| Key | Also |
|---|---|
| `reason` | not one of: `""` |

Outcomes of an unreadable row (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole row | `<s>controller` | the whole row is unreadable (including state not active/idle; active without members, target, reason, at or with them out of form): the controller — a refusal of the placement change with failures, not an empty row and not idle | 0 | row | P/04 N1.5, N4 «intent row out of the form of N1.5» |
| the whole row | `console` | the whole row is unreadable (including state not active/idle; active without members, target, reason, at or with them out of form): /where, /unplaceable, label forecasts — 503 unavailable, not idle | 0 | row | P/04 N1.5 |

#### `<sub>/controller/pass` — object

Schema — [`controller-pass.schema.json`](../data/controller-pass.schema.json), outcomes — [`controller-pass.outcomes.tsv`](../data/controller-pass.outcomes.tsv); form version 1; norm — P/04 N1.2.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `at` | time (P/01.1 N0 «Time in a row») | required |  | Wall time when this cycle control part ended; frozen before snapshot publication, not the final object put time. |
| `ok` | bool | required |  | The control part completed with its confirmed inputs/writes and no control-step failure; snapshot outcomes are recorded separately. |
| `error` | string | required |  | the text of the last error or an empty string |
| `failures` | by the definition `count` | required |  | Independent control-step failures of this cycle; snapshot publication outcomes do not increment this field. |
| `last_success` | time (P/01.1 N0 «Time in a row») | required |  | Last successful control-part completion time, unchanged by a later snapshot publication failure. |
| `seconds` | number; ≥ 0 | required |  | Duration of this cycle control part only, excluding snapshot and final-report publications. |
| `manifest_rev` | string or integer | required |  | the manifest revision of the controller |
| `manifest_behind` | by the definition `count` | required |  | rows of this pass whose write was postponed because of a lagging manifest; a row — once per pass |
| `names_given` | map author names: name — by the definition `slot_name`, value — string; not one of: `""` | required |  | names given away by the fate; the worker reads them at capture (P/03.2 N3 «capture») |
| `names_given.<name>` | string; not one of: `""` | optional |  | the version of the slot row (index P/01.1 N1, an opaque string) at which the name was given away (N3 «fate» names_given) |
| `hung_move_after` | number; ≥ 0 | required |  | seconds of the hang limit in force at this controller (N1.4 HUNG_MOVE_AFTER); the worker reads it |
| `fates` | map author names: name — by the definition `slot_name`, value — map `{fate, server, why, rev, since}` | required |  | only taken slots not given away (holder non-empty, released false) |
| `fates.<name>` | map `{fate, server, why, rev, since}` | optional |  |  |
| `fates.<name>.fate` | string; one of: `alive`, `wait`, `hung`, `hung_moved`, `unsure`, `unsure_moved`, `move`, `release` | required |  |  |
| `fates.<name>.server` | string | required |  |  |
| `fates.<name>.why` | string | required |  |  |
| `fates.<name>.rev` | string or integer | required |  | the version of the judgment about the slot |
| `fates.<name>.since` | time (P/01.1 N0 «Time in a row») | required |  | the moment the slot entered this fate by the controller's clock |
| `diverged` | by the definition `count` | required |  | a counter ≥ 0 |
| `unplaced` | by the definition `count` | required |  | a counter ≥ 0 |
| `garbled` | by the definition `count` | required |  | a counter ≥ 0 |
| `snapshot_tables_refused` | by the definition `count` | required |  | Tables replaced by the too_large stub during this cycle at SNAPSHOT_TABLE_MAX; included in this same final report, outside control-step failures. |
| `snapshot_rows_garbled` | by the definition `count` | required |  | Unreadable snapshot fields omitted by unit/table publications of this same cycle; reset only for the next cycle after this final report. |
| `reach_moves_total` | by the definition `count` | required |  | a counter ≥ 0 |
| `slots_released_total` | by the definition `count` | required |  | a counter ≥ 0 |
| `unplaced_deleted_total` | by the definition `count` | required |  | a counter ≥ 0 |
| `servers_decommissioned_total` | by the definition `count` | required |  | a counter ≥ 0 |
| `workers_hung` | by the definition `count` | required |  | a counter ≥ 0 |
| `workers_hung_moved_total` | by the definition `count` | required |  | a counter ≥ 0 |
| `workers_unsure_moved_total` | by the definition `count` | required |  | a counter ≥ 0 |
| `name_conflicts` | by the definition `count` | required |  | a counter ≥ 0 |
| `unplaceable` | map author names: name — string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full, value — string; not one of: `""` | required |  |  |
| `unplaceable.<name>` | string; not one of: `""` | optional |  | a non-empty reason — why of /unplaceable and reason of 404 `/where/<id>` |
| `short` | list, element — map `{labels, units, workers, groups, ordered, withheld?}` and other author names: name — string, value — by the definition `count` | optional |  | only when placement.grows true |
| `short[]` | map `{labels, units, workers, groups, ordered, withheld?}` and other author names: name — string, value — by the definition `count` | optional |  |  |
| `short[].labels` | list, element — string | required |  | the label set — the canonical notation in ascending order (N3 «set order») |
| `short[].labels[]` | string | optional |  |  |
| `short[].units` | integer; ≥ 0; the whole sign for the reader too (x-whole) | required |  | Exact nonnegative sum of waiting unit weights, in integer JSON notation, without an upper common.uint53 bound. Preserve the whole serialized-report limit; never round or saturate through binary64/int64 (P/04-R008). |
| `short[].workers` | by the definition `count` | required |  | processes needed beyond the live ones and the capacity in flight |
| `short[].groups` | by the definition `count` | required |  | waiting groups; always, 0 too |
| `short[].ordered` | by the definition `count` | required |  | ordered by this pass |
| `short[].withheld` | string | optional |  | words for why it was not ordered |
| `short[].<name>` | by the definition `count` | optional |  | An own counter of the short element; standard properties keep their declared forms. |
| `wants` | map author names: name — by the definition `server_name`, value — map `{want, live, pending, retiring?, why, state}` | optional |  | only when placement.grows true |
| `wants.<name>` | map `{want, live, pending, retiring?, why, state}` | optional |  |  |
| `wants.<name>.want` | integer; ≥ 1; ≤ 99 | required |  |  |
| `wants.<name>.live` | by the definition `count` | required |  | live processes of the role of the server |
| `wants.<name>.pending` | by the definition `count` | required |  | capacity in flight |
| `wants.<name>.retiring` | by the definition `slot_name` | optional |  | a slot name, P/03.2 N1.4 |
| `wants.<name>.why` | string | required |  |  |
| `wants.<name>.state` | string; one of: `ok`, `raising`, `raise_failed`, `no_base` | required |  |  |
| `raise_failed` | map author names: name — by the definition `server_name`, value — map `{since, times}` | required |  |  |
| `raise_failed.<name>` | map `{since, times}` | optional |  |  |
| `raise_failed.<name>.since` | time (P/01.1 N0 «Time in a row») | required |  | the moment the order was removed |
| `raise_failed.<name>.times` | by the definition `count` | required |  | refusals in a row |
| `near_waiting` | list, at least 1 items, without repeats, element — string; matching `[a-z][a-z0-9_-]{0,31}` in full | optional |  | the subsystems of placement.near.sub that are not in the manifest catalog of this pass: the affinity waits for their installation (N1.3 near); otherwise there is no field |
| `near_waiting[]` | string; matching `[a-z][a-z0-9_-]{0,31}` in full | optional |  |  |
| `expired_kept` | by the definition `count` | required |  | Manual rows retained after ends removed them; required nonnegative count for current reader and writer, zero when none. |
| `snapshot_state_garbled` | by the definition `count` | required |  | Unreadable unit states omitted by the unit snapshot publications of this same cycle; reset only for the next cycle after this final report. |
| `state_swept_total` | by the definition `count` | required |  | Cumulative confirmed orphan-state deletions from this process start; not reset between cycles. |
| `.<name>` | any value | optional |  | the implementation's own counters (N1.2 — MAY add) |

**`count`** — a counter ≥ 0

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `<count>` | integer; ≥ 0; ≤ 9007199254740991 |  |  |  |

**`server_name`** — the server name — the grammar of SERVER_NAME (P/02.4 N1.2)

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `<server_name>` | string; matching `[a-z0-9]+(-[a-z0-9]+)*` in full |  |  |  |

**`slot_name`** — a slot name, P/03.2 N1.4

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `<slot_name>` | string; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full |  |  |  |

Outcomes of an unreadable object (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| `/names_given` | * | the worker at capture (P/03.2 N3 «capture» step 1): without a readable names_given there is no permission by it — the name is taken only when released or free, the cause goes to the log | 0 | field | P/04 N1.2; P/03.2 N3 «capture» |
| `/short` | * | short out of form (an element without a required field of N1.2, including groups): the console does not give the series units_short, workers_withheld and groups_waiting of this pass, /metrics — 200 (P/01.1 N0 «Stability of output»); the rest of the report is read | 1 | field | P/04 N1.2; P/06.5 N3 «/metrics — text» |
| `/hung_move_after` | * | the worker (P/03.2): keeps the previous hang limit (the last one read); if none was read — does not judge itself hung by the limit of the report; the cause goes to the log once per pass | 1 | field | P/04 N1.2 |
| the whole object | `<s>worker` | the whole object is unreadable: the worker at capture — as /names_given: there is no permission by it, the name is taken only when released or free, the cause goes to the log; the hang limit — as /hung_move_after: the previous one read, without one read it does not judge itself hung by the limit of the report | 2 | row | P/04 N1.2; P/03.2 N3 «capture» |
| the whole object | `console` | the whole object is unreadable: the console removes the series from the pass report rather than dropping the /metrics answer (P/01.1 N0 «Stability of output»); /where of an unplaced one — reason without why: «not placed: no worker holds it» | 2 | row | P/06.5 N3 «/metrics — text»; P/06.6 N2.2 |

#### `<sub>/snapshot/<worker>` — object

Schema — [`snapshot.schema.json`](../data/snapshot.schema.json), outcomes — [`snapshot.outcomes.tsv`](../data/snapshot.outcomes.tsv); form version 1; norm — P/04 N1.3a.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `cluster` | string | required |  | the installation name — CLUSTER of the environment (P/02.4 N1.2), not set — local |
| `worker` | string or null; matching `[a-z]{1,8}-[a-z0-9]+(-[a-z0-9]+)*` in full | required |  | the worker name of the shard (slot, P/03.2 N1.4); for the shard of a gone worker — null |
| `ts` | time (P/01.1 N0 «Time in a row») | required |  | the moment of publication |
| `.<name>` | list, element — map `{id, revision, worker, server}` and other author names: name — string, value — any value | optional |  | name: unit.rows of the manifest (P/06.1 N1.1; not cluster/worker/ts — P/02.1) |
| `.<name>[]` | map `{id, revision, worker, server}` and other author names: name — string, value — any value | optional |  |  |
| `.<name>[].id` | string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | required |  | the unit id (P/06.1 N1.3) |
| `.<name>[].revision` | string or integer | required |  | revision of the unit row |
| `.<name>[].worker` | string or null | required |  | the worker of the assignment; unplaced has none |
| `.<name>[].server` | string or null | required |  | the worker's server |
| `.<name>[].<name>` | any value | optional |  | a field from snapshot of the manifest (P/02.1), addresses — with the mask of P/06.2 N1.1a |

Reader and writer bounds (`$defs.writer`, applied by root `allOf`):

| Key | Also |
|---|---|
| `<root>` | at most 1 names (x-max-names) |
| `.<name> (name)` | string; not one of: `platform`, `spec`, `manifest`, `next_id`, `slots`, `epoch`, `idem`, `policy`, `placement`, `workers`, `controller`, `decommissioned`, `decommission-pending`, `holds`, `requests`, `asked`, `sweep`, `servers`, `where`, `unplaceable`, `drain`, `events`, `marks`, `console`, `audit`, `session`, `mounts`, `healthz`, `changes`, `metrics`, `resources`, `schema`, `domain`, `api`, `heartbeats`, `contenders`, `snapshot`, `blobs`, `commands`, `state`, `folders`, `memberof`, `operations`, `opsteps`, `opdone`, `opcount`, `opbusy`, `operations-turn`, `operations-epoch`, `cluster`, `worker`, `ts`, `tables`, `snapshot-tables`; matching `[a-z][a-z0-9_-]{0,31}` in full |

Outcomes of an unreadable object (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole object | `console` | the whole shard is unreadable (not JSON or not a shard object): on /metrics — skipped and counted in `<sub>_snapshot_garbled_shards`, /metrics — 200 with the rest, not 503; a read error does not update the age (P/01.1 N0 «Stability of output») | 0 | row | P/06.5 N1.3 age, metrics |
| the whole object | `domainagent` | the whole shard is unreadable (not JSON or not a shard object): it does not enter the publication and does not get into deleted, the previous copy at the holder stays, the log | 0 | row | P/09.1 N1.2 |

#### `<sub>/snapshot/unplaced` — object

Schema — [`snapshot-unplaced.schema.json`](../data/snapshot-unplaced.schema.json), outcomes — [`snapshot-unplaced.outcomes.tsv`](../data/snapshot-unplaced.outcomes.tsv); form version 1; norm — P/04 N1.3a.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `cluster` | string | required |  | the installation name — CLUSTER of the environment (P/02.4 N1.2), not set — local |
| `worker` | null | required |  | for the shard of the unplaced — null |
| `ts` | time (P/01.1 N0 «Time in a row») | required |  | the moment of publication |
| `.<name>` | list, element — map `{id, revision, worker, server}` and other author names: name — string, value — any value | optional |  | name: unit.rows of the manifest (P/06.1 N1.1; not cluster/worker/ts — P/02.1) |
| `.<name>[]` | map `{id, revision, worker, server}` and other author names: name — string, value — any value | optional |  |  |
| `.<name>[].id` | string; not one of: `.`, `..`; matching `[^/\\\|",\u{0000}-\u{001F}\u{007F}-\u{009F}\u{2028}\u{2029}٠-٩۰-۹߀-߉०-९০-৯੦-੯૦-૯୦-୯௦-௯౦-౯೦-೯൦-൯෦-෯๐-๙໐-໙༠-༩၀-၉႐-႙០-៩᠐-᠙᥆-᥏᧐-᧙᪀-᪉᪐-᪙᭐-᭙᮰-᮹᱀-᱉᱐-᱙꘠-꘩꣐-꣙꤀-꤉꧐-꧙꧰-꧹꩐-꩙꯰-꯹０-９𐒠-𐒩𐴰-𐴹𑁦-𑁯𑃰-𑃹𑄶-𑄿𑇐-𑇙𑋰-𑋹𑑐-𑑙𑓐-𑓙𑙐-𑙙𑛀-𑛉𑜰-𑜹𑣠-𑣩𑥐-𑥙𑱐-𑱙𑵐-𑵙𑶠-𑶩𑽐-𑽙𖩠-𖩩𖫀-𖫉𖭐-𖭙𝟎-𝟿𞅀-𞅉𞋰-𞋹𞓰-𞓹𞥐-𞥙🯰-🯹]+` in full | required |  | the unit id (P/06.1 N1.3) |
| `.<name>[].revision` | string or integer | required |  | revision of the unit row |
| `.<name>[].worker` | string or null | required |  | an unplaced one has no worker |
| `.<name>[].server` | string or null | required |  | the worker's server; an unplaced one has none |
| `.<name>[].<name>` | any value | optional |  | a field from snapshot of the manifest (P/02.1), addresses — with the mask of P/06.2 N1.1a |

Reader and writer bounds (`$defs.writer`, applied by root `allOf`):

| Key | Also |
|---|---|
| `<root>` | at most 1 names (x-max-names) |
| `.<name> (name)` | string; not one of: `platform`, `spec`, `manifest`, `next_id`, `slots`, `epoch`, `idem`, `policy`, `placement`, `workers`, `controller`, `decommissioned`, `decommission-pending`, `holds`, `requests`, `asked`, `sweep`, `servers`, `where`, `unplaceable`, `drain`, `events`, `marks`, `console`, `audit`, `session`, `mounts`, `healthz`, `changes`, `metrics`, `resources`, `schema`, `domain`, `api`, `heartbeats`, `contenders`, `snapshot`, `blobs`, `commands`, `state`, `folders`, `memberof`, `operations`, `opsteps`, `opdone`, `opcount`, `opbusy`, `operations-turn`, `operations-epoch`, `cluster`, `worker`, `ts`, `tables`, `snapshot-tables`; matching `[a-z][a-z0-9_-]{0,31}` in full |

Outcomes of an unreadable object (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole object | `console` | the whole shard is unreadable (not JSON or not a shard object): on /metrics — skipped and counted in `<sub>_snapshot_garbled_shards`, /metrics — 200 with the rest, not 503; a read error does not update the age (P/01.1 N0 «Stability of output») | 0 | row | P/06.5 N1.3 age, metrics |
| the whole object | `domainagent` | the whole shard is unreadable (not JSON or not a shard object): it does not enter the publication and does not get into deleted, the previous copy at the holder stays, the log | 0 | row | P/09.1 N1.2 |

#### `<sub>/snapshot-tables/<table>` — object

Schema — [`snapshot-tables.schema.json`](../data/snapshot-tables.schema.json), outcomes — [`snapshot-tables.outcomes.tsv`](../data/snapshot-tables.outcomes.tsv); form version 1; norm — P/04 N1.3b.

| Key | Type and bounds | Requirement | Lesson | Meaning |
|---|---|---|---|---|
| `cluster` | string | required |  | the installation name — CLUSTER of the environment (P/02.4 N1.2), not set — local |
| `ts` | time (P/01.1 N0 «Time in a row») | required |  | the moment of the object write; unchanged cluster, refused and rows retain the former ts (P/04-R174) |
| `refused` | string; one of: `too_large`, `whole_too_large` | optional |  | a stub instead of rows: the table did not fit (P/04 N1.3b ceiling, P/09.1 N1.2 tables_budget) |
| `rows` | list, element — map `{key, revision, fields, secrets?, worker?, server?, phase?, status?, labels?, about?}` | required |  | the rows of the table by key in UTF-8 bytes (the order is a rule of the lesson, not the form) |
| `rows[]` | map `{key, revision, fields, secrets?, worker?, server?, phase?, status?, labels?, about?}` | optional |  |  |
| `rows[].key` | string; not one of: `""` | required |  | the row name (P/06.1 N1.6) |
| `rows[].revision` | integer; ≥ 1; ≤ 9007199254740991 | required |  | the row version |
| `rows[].fields` | map, opaque | required |  | fields of the list domain.view_tables of the manifest; values of their own type; no secrets |
| `rows[].secrets` | list, element — string | optional |  | names of the set *_secret fields; no values |
| `rows[].secrets[]` | string | optional |  |  |
| `rows[].worker` | string | optional |  | for unit rows — from the assignment |
| `rows[].server` | string | optional |  | for unit rows — from the assignment |
| `rows[].phase` | string | optional |  | for unit rows — from the heartbeat |
| `rows[].status` | map, opaque | optional |  | fields of domain.view_status from the element of status[] of the heartbeat |
| `rows[].labels` | list, element — string | optional |  | for unit rows — the field labels |
| `rows[].labels[]` | string | optional |  |  |
| `rows[].about` | string | optional |  | for unit rows — the id of the about unit |

Outcomes of an unreadable object (the reader is a role; `*` — all readers of the family):

| Path of refusal | Reader | Outcome | Priority | Unit | Norm |
|---|---|---|---|---|---|
| the whole object | `domainagent` | the whole object is unreadable (not JSON or not an object of the family): it does not enter the publication and does not get into deleted, the previous copy at the holder stays, the log (P/09.1 N1.2) | 1 | row | P/09.1 N1.2 |
<!-- families:end -->

<!-- req: P/04-R239 -->

The writer and the reader check the schema with a ready-made JSON Schema 2020-12 validator of a pinned version ([pinned versions](../../common/versions/README.md)); the schema files themselves are a norm, not a choice.

---

## N2 Doors

<!-- req: P/04-R024 -->

The lesson has no HTTP doors of its own (`P/04 no-openapi`). The console doors through which the operator talks to the controller (`/policy`, `/drain`, `/servers/{server}/labels`, `/servers/{server}/decommission`, `/unplaceable`, `/where/{id}`), their procedures and refusals are [P/06.6](../../06-console/spec/06.6-console.norms.md) N2 (`/where` — [chapter 6.5](../../06-console/spec/06.5-console.norms.md) N2); the controller executes their writes as the rows of N1.1 on its pass (N3).

---

## N3 Procedures

<!-- req: P/04-R025 -->

delete_after applies only to a named id: numeric together with this key is rejected by the loader of P/02.1. The controller does not replace a physical delete with a tombstone and does not destroy the history of numeric issues.

### get and hold the placement turn

<!-- req: P/04-R026 -->

Steps 1–6, the barrier and «Races» are [the writer turn contract](../../common/contracts/turn.md) «Get and hold the turn», «Barrier». The turn row of the controller is `<sub>/controller/placement_turn` (N1.5), `holder` is a new unique mark of the attempt; the changing writes under the guard (step 5 of the contract) are every write/delete of placement/*, workers/* and placement_intent, and also the delete of a unit row by delete_after; the turn is given up at the end of the pass (step 6 of the contract).

### accept and complete a decision(members, target, reason)

<!-- req: P/04-R027 -->

Accepting and completing a decision follows steps 0–6 below, in order.

<!-- req: P/04-R490 -->

0. the turn is mine; an active intent → first complete it, do not accept new decisions yet; manifest_rev of the intent > mine → do not change it and the placements; the rows of its members — into manifest_behind (N1.2)

<!-- req: P/04-R243 -->

1. Before a new decision, freshly read the units, effective decisions, assignments and candidate properties. If any member placement has manifest_rev greater than this controller’s revision, accept no new intent and count members’ rows in manifest_behind (N1.2).

<!-- req: P/04-R517 -->

Check the whole group or unit against free capacity with the reserves of N1.5, spread_by and every other constraint before accepting a decision. For a move estimate, do not count the members’ own old reserves as a second copy at the target. Admission checks the final set: old ids excluding members plus ALL members, including spread_by inside the group and across every worker of the target server.

<!-- req: P/04-R520 -->

No common target means no new admission; removal uses target "".

<!-- req: P/04-R521 -->

If any full `<sub>/placement/<id>` key of the members exceeds the P/01.1 key limit, there is no decision or intent write; those members enter unplaceable with why.

<!-- req: P/04-R244 -->

2. write the active intent with cas of the read idle (or cas "" on the initial absence) and guard turn; toolarge before a confirmed active → a refusal of the step, do not change placement/workers, do not split the group

<!-- req: P/04-R245 -->

3. after a confirmed intent freshly list/read ALL workers; remove ALL members from ALL assignments, including target, each by a write cas + guard turn; only the confirmed completion of all removals allows going on

<!-- req: P/04-R246 -->

4. assign to each placement of members target/reason/at/manifest_rev of the intent with cas + guard turn, rev + 1; the row already contains these fields → do not rewrite it; an absent one starts with rev 1

<!-- req: P/04-R247 -->

5. target non-empty → add ALL members to its assignment by one write cas + guard turn; target empty → no addition; while 3–4 are not complete, step 5 is forbidden

<!-- req: P/04-R248 -->

6. only after the confirmation of 3–5 write the intent {state: idle, manifest_rev} with cas + guard turn

<!-- req: P/04-R028 -->

Each group occupies one intent write; it is not split for the sake of the ceiling of a row or of an assignment. The weight of both future rows (the intent and the full assignment of the target) is checked before step 2; an excess is a refusal of the step with a reason and failures, without a partial placement.

<!-- req: P/04-R250 -->

Before step 2 it is likewise checked that the full key `<sub>/placement/<id>` of each of the members is representable within the key limit of the store (P/01.1 N1): an id admissible by P/06.1 N1.3 for a unit row may not fit into the longer placement key. An unrepresentable key — there is no decision, the intent is not written, the group is not split; these members go into `unplaceable` with `why`, the other decisions of the pass go on. Therefore an intent that cannot be completed because of the key length never happens, and one such unit does not stop the placement of the subsystem.

<!-- req: P/04-R253 -->

An incomplete read also forbids admission.

<!-- req: P/04-R254 -->

On a change of holder an active intent is recovered **from step 3**; a new decision and another direction for its members are forbidden until completion. The composition, the target and the rule are fixed in the intent; changes of the inputs after its acceptance are processed by the next decision after the recovery. After completion all new calculations take a fresh look, so the reserve of the previous decision is already visible.

<!-- req: P/04-R029 -->

**Races.** Two admissions of different units do not use one remainder: B gets the turn after A and sees the decision/assignment of A or its active intent, which B is obliged to complete first. In two admissions by different controllers with capacity=1, the second weight 1 does not pass; with spread_by the value occupied by the first admission is already visible. Two different first members of a group do not create different decisions: one active intent fixes all of them and one target.

<!-- req: P/04-R259 -->

After a break in the middle of the removals the additions do not start; after a break in the middle of placement the new holder repeats the removals and completes the same target. Before members are added to the new target, their old worker assignments contain none of those members.

<!-- req: P/04-R261 -->

The transfer guarantee is about rows and assignments; old process actions stop through reconciliation and leases (P/03.3, P/03.2), not through the placement map change alone.

### pass() — every PASS_EVERY

<!-- req: P/04-R030 -->

Each pass follows the ordered steps below every PASS_EVERY, with the independent-step error handling specified there. Each step of the pass runs in its own attempt: an error of a step increments failures by 1, and the other steps go on.

<!-- req: P/04-R565 -->

If a pass lasts longer than PASS_EVERY, the implementation chooses whether to skip occupied ticks or schedule the next pass after completion; that scheduling choice is not judged. Without an overrun, the PASS_EVERY period remains in force. Changing passes and cycle publications must not overlap, and P/04-R142 still isolates every cycle and its counters.

<!-- req: P/04-R491 -->

0. Update the memory of observed heartbeats, slots and resources on this controller’s own clock; first sight of a version means it has just changed. Read cluster objects (worker/resource heartbeats and reports) through the resource of this server. Without its resource, `cluster://` gives unknown, not absent ([object client](../../common/contracts/object-client.md), door).

<!-- req: P/04-R523 -->

Get the placement turn before a changing pass: busy means no changing pass and retry after TURN_BUSY_RETRY; when the turn is mine, first complete an active intent.

<!-- req: P/04-R524 -->

After turn admission and intent completion, take a fresh view of units, placements, assignments and candidate properties. Refresh that view before every new decision, including effects of the preceding decision.

<!-- req: P/04-R262 -->

1. revision: read the manifest revision; a placement without its required manifest_rev is unreadable; do not stamp or repair it; read the manifest catalogue (platform/manifest/*) — on every pass: the manifest near.sub has appeared — the affinity (N1.3 near) applies from this pass; it is absent — no affinity, near_waiting

<!-- req: P/04-R263 -->

2. decommission of servers: resume pending or admit a stopped server by N3 decommission_server; release/cleanup in bounded chunks, then publish `<sub>`/decommissioned/`<s>` only at finalization. Before admission a heard server leaves the request standing.

<!-- req: P/04-R264 -->

3. slot fates (below); release → write the slot as released; names_given; alarms hung/unsure; an abandoned capture — remove the rows under it (below)

<!-- req: P/04-R265 -->

4. place: remove the deleted (reason deleted) → remove by retire_when (by the acting state with retire_when.state) → remove by ends (the field ≠ never and ≤ the clock of the controller; reason ends) → sync of the assignments with the placements (diverged) → each unplaced unit from placeable (N3 shortage; deleted, ends and retire_when excluded) — choose (below), a group whole at its first member; each in its own attempt; the order of the unplaced — by id in UTF-8 bytes (a group — by the id of the first member); the same order for the moves of steps 5–7

<!-- req: P/04-R266 -->

5. reachability: only with constraint: labels-subset by P/04-R150 and P/04-R566, the units whose server no longer reaches their labels — a move within REACH_BUDGET; a group — whole, the first group goes even beyond the budget; nowhere — remove with a reason

<!-- req: P/04-R267 -->

6. leaving: the units of the workers that are leaving (below) — a move without a budget; a group whole, or it waits

<!-- req: P/04-R268 -->

7. home: no more than HOME_BUDGET units — home, if there is room there; the home is judged as in «choose» (N1.3 home): the holder of the named place is eligible — it alone is the home, a unit at another worker, including one of the same server, moves to it; there is no holder — the home is the server of the place, and a unit on this server is already home; no home, it has no free room or is not eligible — the unit stays: a preference does not become a filter

<!-- req: P/04-R269 -->

8. unplaced for longer than delete_after: under the own turn re-read the unit and its effective placement by N1.5; there is an assignment, an active intent (with any target) or the read is not confirmed → do not delete. Still unplaced and the deadline is confirmed → delete the row with cas of its fresh version AND guard of the own version of placement_turn (turn admission P/04-R523 and step 5 of the turn contract); conflict/412/no answer → the barrier and a new plan by the turn rule, the journal unit.unplaced_deleted only on success.

<!-- req: P/04-R271 -->

Physical deletion under step 8 also applies when the unit is still removed by retire_when for longer than retire_when.delete_after, counted from the first observed removal and reset when removal ceases or the controller restarts. Recheck the fresh row and, with retire_when.state, its acting state; if no longer removed, do not delete, so an operator edit is preserved.

<!-- req: P/04-R525 -->

A unit removed by ends is physically deleted immediately after removal, under the same step-8 deletion rules and manual-row exception.

<!-- req: P/04-R272 -->

For a table with fixed fields or about not by id only a row with made is deleted; a manual row is not deleted — expired_kept + 1 (N1.3 unplaced). A row with made is deleted by the row-check contract «Customer row: made» `delete` (strictly after made.keep, not_before = max(0, made.keep − 60)): 409 early — not deleted, without a barrier and a journal, on the next pass; keep prevents only an obviously early delete attempt; a delete arriving late is still bounded by not_before at store admission. The made.keep check never authorizes deletion before keep.

<!-- req: P/04-R275 -->

The row is deleted physically, without a tombstone (P/01.1 delete): the row first, with cas of the read version and guard of the own version of placement_turn; an edit or a prolongation between the read and the delete — conflict: the delete is cancelled, the state is not touched; only after a confirmed delete of the row — its states (step 8a); the journal unit.unplaced_deleted {reason: unplaced | retired | ends}

<!-- req: P/04-R276 -->

8a. state sweep (unit.state declared): list `<sub>`/state/; for each state row read the unit row: it is absent, a tombstone or its born ≠ born of the state → orphaned: delete by one operation with cas of the version of the state and guard {key: the unit row, index: the read version — for a tombstone its version, "" — no row}; a row created or changed after the read cancels the sweep (412 — leave it until the next pass); the acting and other non-orphaned ones (born matched, revision differs) — do not touch; state_swept_total + 1 for each removed one

<!-- req: P/04-R277 -->

9. shortage and order (grows: true): order rows, capacity in flight, short, order, withdraw on deadline

<!-- req: P/04-R278 -->

9a. shrink (grows: true): the victim, retiring, a move of no more than SHRINK_BUDGET, the end or the cancel; drain — N3 below

<!-- req: P/04-R279 -->

10. Finish the control part and its ok/failures/at/seconds/last_success; release the turn; then attempt unit snapshots and table snapshots outside turn, and write this cycle’s one final `<sub>/controller/pass`.

<!-- req: P/04-R031 -->

A definite badkey of a full store key is an error of the corresponding step, not the absence of a row; the data of such a read are not replaced with empty ones. If the error does not allow completing an active intent, a new decision is not accepted: the recovery rule of N1.5/N3 applies.

<!-- req: P/04-R281 -->

The pass checks the placement and the assignments; `unique`/`ref`/`must_match` of the unit fields are checked in advance by the units door of P/06.1. This pass does not guarantee a background audit and journaling of a violation of these constraints after a race of separate writes (P/06.1 N3).

<!-- req: P/04-R032 -->

**Races.** The target of placement/assignment changes only under the turn and through an intent; one cas of a unit row does not replace the common admission. A break of the turn/store stops the whole changing pass, not just one unit; the errors of the other independent steps are counted by the usual failures. The next holder first repairs the unfinished decision, then accepts its own. A missing manifest_rev is an unreadable current row, not authority to stamp it; all existing turn/intent barriers remain.

### choose(unit) → worker | none

<!-- req: P/04-R033 -->

Worker selection follows the eligibility and rank rules below. placed (worker ≠ "") → as is; do not reconsider

<!-- req: P/04-R286 -->

retire_when (by the acting state with retire_when.state); ends ≠ never and ≤ the clock of the controller → none

<!-- req: P/04-R287 -->

live worker, pool, keeper of the place with distinct — the pool contract (common/contracts/pool.md): live − released slots − the draining, pending and decommissioned servers − (requires: resource ∧ resource silent) − retiring − number above want − unreadable assignment − (distinct: all except the keeper of the place)

<!-- req: P/04-R288 -->

eligible = pool ∩ constraint ∩ spread_by ∩ affinity ∩ (the group is already at a worker → only it) ∩ (the worker holds an exclusive place → only the units bound to it; N1.3 affinity.exclusive). a group of several waiting: eligible ∩ {admits all ∧ free ≥ Σ of the weights}; empty → wait, tell

<!-- req: P/04-R290 -->

order: home → preference → all; home — among the eligible (N1.3 home): the holder of the named place, no holder — the workers of the server of this place; the holder lacks free room — the rank is empty, the server of the home does not replace it; preference — one rank: a worker beside the neighbour (near) or on the server of a non-binding affinity row (N1.3) — either of the two, both at once do not raise the rank; inside a rank — free = capacity − load with the reserves of N1.5, free ≥ the weight of the unit ∧ strictly more than the former best; equality — the first by name (ASCII, P/03.2 N1.4)

<!-- req: P/04-R291 -->

found → accept and complete a decision for the unit or the whole group by N3 above; already placed while the turn was being got → do not accept the former choice, a fresh look

<!-- req: P/04-R292 -->

none → choose neither creates nor rewrites a placement row; the non-empty reason for a unit without a place is recorded in unplaceable by P/04-R129. This does not cancel the separately required removal of a placement by reachability, leaving, ends or retire_when.

<!-- req: P/04-R034 -->

If the decommission mark `<sub>/decommissioned/<s>` of the subsystem named by `about.sub`, `near.sub` or `ref` of the unit being placed does not read, then the server `s` is not confirmed for this placement: it is not a candidate, an error of the step (failures + 1), the reason goes into the journal; it is counted neither as decommissioned nor as not decommissioned.

<!-- req: P/04-R035 -->

**Reason** (for a human; it MUST be non-empty; it SHOULD follow the grammar): `most free capacity (<free>) among <n> worker(s)` — `<n>` is the number of the eligible (after the filters), not of all live ones + `; weight <w>` — only for a manifest with `placement.weight` + ` reaching <labels>` + `; on <server>` + `, whose resource is <state>` + a mark of the choice by the rank of the chosen worker: the home rank — `, at home on <s>`, with `home: near` — `, beside <their ids> holding it`; the neighbour rank — `, beside <their ids> holding it`, and if a home is declared but its rank is empty — also ` (home <s> has no room)`; the rank «all» with `near` whose server is not chosen — `, away from <their ids> on <neighbour's server> (no room there)`, and with a declared `home`, except `home: near`, outside the home — also `; away from home <s>`; `<s>` of the home marks is what the home is named by: the place of the holder or the server. For the human-readable reason, which MUST be non-empty and SHOULD follow this grammar, Leaving: `slot <name> released`, `slot <name> capture did not finish`, `resource on <s> silent`, `server <s> draining`, `server <s> decommissioned`, `<w> holds no <place_by> now`, `<w>'s <place_by> <place> admits no unit` (`<place_by>` is the name of the field `placement.place_by`, `<place>` is the id of the place of the worker: `w-1 holds no shard now`, `w-1's shard s3 admits no unit`). For the human-readable reason, which MUST be non-empty and SHOULD follow this grammar, Reachability: `<s> no longer reaches <label>; …` / `; nothing live reaches it`. For the human-readable reason, which MUST be non-empty and SHOULD follow this grammar, Group: `with <id>, one <group_by>: <why>; on <s>`. For the human-readable reason, which MUST be non-empty and SHOULD follow this grammar, Deleted: `deleted`.

<!-- req: P/04-R036 -->

**Materialization and sync.** They use the same intent and turn. Even if the correct decision already exists, the repair first fixes it for the unit/group, removes the former assignments and completes one target. There is no partial addition by the snapshot of the start of the pass. The only guard of the target write is the turn version; the stability of the decision is ensured by the exclusive ownership of the turn, the fresh check and the intent that is unchangeable until completion.

### move(unit, from, to) → ok | already moved

<!-- req: P/04-R037 -->

1. the turn of the current pass is mine and confirmed; outside a pass first get it; re-capturing an already held turn is not needed; complete the former active intent; freshly read the effective placement; worker != from → Moved, do not touch; for a group check all members and the common target

<!-- req: P/04-R301 -->

2. check to by all constraints and the free capacity with the reserves; accept an intent for the whole unit/group and complete it by steps 2–6 above

<!-- req: P/04-R038 -->

**Races.** A was delayed after the decision w-2, B got the turn and completed it, then moved the unit to w-3. Each late write of A has an old guard turn and is refused. The late writer A can neither add to w-2 nor remove from the already new w-3. If A managed to add before the capture by B, B sees the assignment at the fresh removal. One unit never gets two assignments; for a group all old assignments are removed before the addition of the new target. A moment without an assignment and a lag of directory remain admissible.

<!-- req: P/04-R039 -->

In all branches hung/unsure/wait, HUNG_MOVE_AFTER is counted from the first observation by this judge of an unchanged slot version (age 0), not from until, the end of SLOT_TERM or the entry into the fate. The diagnostic fates.since does not carry this term. A new judge starts the observation anew.

### fate(slot) → fate — by the clock of the controller

<!-- req: P/04-R040 -->

The ordered decision machine is [forms/slot-fate.tsv](../forms/slot-fate.tsv). Its typed inputs are the observations of this judge, not the writer's `until`. The first matching rule wins. It returns the fate and, when allowed, the exact judgement version for `names_given`. The release branch calls [forms/slot-release.tsv](../forms/slot-release.tsv): only its confirmed CAS answer can publish the post-release version. A `-` action is YOURS at its anchor; it must not be skipped. The write, abandoned-capture cleanup and permission rules remain below.

<!-- req: P/04-R041 -->

Release writes, abandoned-capture cleanup and capture permissions follow the rules below. write release: write the slot released (cas), keep holder/until/gen/server; a torn one — wholly released and nobody's, keeping a readable gen and writing until as zero Time in the existing writer notation, never now; keep server only if readable by the current slot field schema; otherwise omit the field, with no empty substitute. When preserving or omitting server during a release, use no liveness or registry check. If gen is unreadable in the existing slot, do not change the row or grant capture permission (P/03.2 N1.4).

<!-- req: P/04-R310 -->

abandoned capture: released = "taking", the version unchanged ≥ SLOT_TERM on the clock of the controller (the capturer died between the writes of P/03.2 N3 «capture» steps 3 and 4) → remove the rows under the slot: the contributions `<sub>`/`<from>`/`<slot>` of each book of the manifest with a from family (P/03.7 N1.2) by a batch with guards by `<sub>`/slots/`<slot>` with the version of this judgement, do not write the slot; no row — skip; a guard refusal (412 guard, 409 conflict) — a live capture changed the version: do not repeat; with a server decommission and without: an abandoned capture carries the server of the capturer, step 2 of «decommission_server» by server = s does not recognise it, and an orphan under taking would keep the contribution stale forever

<!-- req: P/04-R311 -->

names_given[name] = the version of the slot row at which the name is taken: for move, hung_moved, unsure_moved and wait ≥ HUNG_MOVE_AFTER — the version at the moment of the judgement (the controller does not write the row); for release — the version AFTER the write of the release (the answer of this write): the released slot is taken by it, and as a «free» one it is also a candidate (P/03.2 N3 «capture» step 2c)

<!-- req: P/04-R042 -->

An unreadable gen of an existing slot is not replaced with zero on release; such a row is kept and is not included in names_given until the generation is recovered. A reassignment of units by fate does not mean a permission to rewrite a damaged generation of the slot.

<!-- req: P/04-R043 -->

**Transitions of `release`.** The branch `release` is reachable by the row «gone without assigned units»: a live resource tells about a process with one of `runs`, `gone`, `unlisted`, `unknown` (P/05 N1.4; `silent` is a state of the resource, not a presence), and the higher-priority rules still run first.

<!-- req: P/04-R313 -->

The two closing rows are reachable when server/slot are known, the slot version has been observed unchanged for at least SLOT_TERM + LOST_AFTER, worker freshness is not confirmed, and resource_state is unknown: with assignments select move, without assignments enter the release procedure. The two closing rows of the fate selector use their existing closing-row policy, not the unreachable-resource delay of HUNG_MOVE_AFTER; resource_state unknown is evidence of neither silence nor unreachability.

<!-- req: P/04-R044 -->

The transition selector is [forms/slot-release.tsv](../forms/slot-release.tsv). The slot-release transition selector receives the selected fate; after its YOURS CAS action, deliver the confirmed reply or conflict to that machine. The five witnesses remain covered: gone without units, a competing renewal, gone with units, unlisted without units and runs without units. A competing renewal refuses the release, and the next pass judges the changed version as `alive`.

<!-- req: P/04-R045 -->

The order of the rules is normative: more definite knowledge before less definite; the margin before the judgements.

<!-- req: P/04-R318 -->

The controller does not write the slot at any outcome except `release` and the server decommission, and it removes the rows under an abandoned capture (above).

<!-- req: P/04-R046 -->

**Races.** The holder renewed the slot between the judgement and the capture of the name by a new process: `names_given` is bound to the version, a capture with `cas` by it will not pass — the name stays. Two controllers can have different observation histories and therefore different judgements; each uses its own version age by P/03.2 N1.4. The `release` writes go with `cas` of the read version, so two decisions do not overwrite a renewal or someone else's capture. A shift of the writer clock with the same observation history does not change the fate.

### leaving(worker) → reason | none

<!-- req: P/04-R047 -->

The first of: the slot is released (released = true — at once); an abandoned capture (released = taking, the version unchanged for SLOT_TERM on the clock of the controller — the capturer died between the writes; earlier — not leaving, the capture will finish); the resource of the server is silent — only with `requires: resource` and a live worker (the pool contract): it works, but its units need a resource that is absent; it does not hold a place (`distinct`); the place does not admit; the server is draining; the server is decommissioned; an outcome from MOVED_FATES — its `why`.

<!-- req: P/04-R322 -->

The units of a leaving worker — a move (step 6) by the rules of the choice; a group whole, or it stays with the alarm `units.left_on_leaving`; the placement row is not cleared until a new place is found, except for a released slot and an abandoned capture: their units that nobody can take are removed by the write `worker: ""`, the reason `slot <w> released; nothing live can take it` (`slot <w> capture did not finish; nothing live can take it`) (the worker has gone forever, a row with its name would say «placed»; acceptance P/03.4, sc. 03). A silence of the store moves nothing. Without `requires: resource` a silence of the resource does not count as leaving, and a worker silent together with the resource leaves only by fate: the units are carried by its outcome `move`, SLOT_TERM + LOST_AFTER of observation of an unchanged slot version (N3 «fate», [P/03.2-08](../../03-worker/spec/03.2-worker.norms.md)).

<!-- req: P/04-R048 -->

**Races.** Leaving and a revived worker: the decision is by the snapshot of the pass; a worker that returned after the move reads an assignment without the unit and stops it (P/03.3 N3 «loop()», step 2: the carried one is not in the assignment → `stop_unit`); the move is not rolled back.

### shortage(), order(), withdraw the order, shrink() — with grows: true

<!-- req: P/04-R050 -->

The role grows on demand: the controller orders the number of processes of the role on a specific server with the row `<sub>/want/<host>`, the server script brings the number of processes to it (P/02.4 N1.5); the controller does not start processes. Shortage, order creation, order distribution and withdrawal follow the rules below.

<!-- req: P/04-R494 -->

order row: on every server where the role is installed and neither pending nor finally decommissioned (the door row has room.`<sub>`, N1.1) — the row `<sub>`/want/`<host>`; none — create want 1 by a write with cas "" and guard of the own version of placement_turn

<!-- req: P/04-R325 -->

placeable = readable live unit rows, excluding deleted/tombstoned rows and every unit removed by ends or retire_when in step 4; a manual expired row may remain in the store, but it is outside this set. Use the placeable set of readable live units (excluding deleted/tombstoned, ends and retire_when) before either grouping or weighing.

<!-- req: P/04-R327 -->

waiting = placeable ∩ (units without a placement ∪ units of the leaving ∪ out of reach only with constraint: labels-subset by P/04-R150 and P/04-R566); a group is one piece. Only these waiting units feed shortage, growth, the no-shortage timer and shrinking; retained expired rows and garbled rows neither cause an order nor delay shrinking.

<!-- req: P/04-R563 -->

The no-shortage timer is one timer for the entire role, not one per label set. Any non-empty waiting set resets it; the first pass with no waiting units across all label sets starts it. Absence of waiting units for one label set does not permit shrinking while another label set still has waiting units.

<!-- req: P/04-R329 -->

live(s) = the live role processes of the server s (a live worker of N3 «choose»), including the base `<prefix>`-`<s>`-1 and the shrink victim (retiring): for «in flight» and «failed to raise» the victim is a live process, want includes it while it is alive; it is excluded from the placement pool (shrink); the number n of the name — as an integer (P/03.2 N1.4)

<!-- req: P/04-R330 -->

in flight(s) = the count of the numbers 2…want(s) that have no live role process of the server s (by heartbeats, live(s)) — ordered and not yet raised, until the order is withdrawn on deadline; the base `<prefix>`-`<s>`-1 is not ordered and is never in flight; by heartbeats — for needed, the order of candidates, the shrink condition, the withdrawal on deadline and wants.`<s>`.pending; the candidate and the share — by the door (free(s) below); with consecutive numbers — max(0, want(s) − live(s)). no_base: the base `<prefix>`-`<s>`-1 is dead — wants.`<s>`.state no_base, an alarm; the server is not a candidate; the base is never in flight, therefore it does not hold back the shrinking of the role on other servers

<!-- req: P/04-R332 -->

free(s) = room.`<sub>`(s) − |{2…want(s)} ∖ live.`<sub>`(s)| — by the door row platform/doors/`<s>` of one snapshot (P/05 N1.4 door_row): live.`<sub>` — the numbers n ≥ 2 of the live presence locks by which room.`<sub>` was counted; it is counted once per pass before the loop over the sets and decreases with every share (order); no live.`<sub>` or it does not read — the server is not a candidate

<!-- req: P/04-R333 -->

set order: a worker or a server that suits several label sets gives its capacity (free of the worker), free(s) of the server and in flight to the sets in turn — in the UTF-8 byte order of the canonical notation of the set (unique labels ascending, comma-separated, a repeat collapses — a label set is a set; the empty set first); each unit of capacity, of free(s) and of in flight is spent by one set once; a set takes the free, free(s) and in flight only up to its own need (min): the in flight taken by a set — min(Σ in flight, processes), the remainder — to the next set

<!-- req: P/04-R334 -->

For a label set, a worker with no named capacity uses placement.capacity.default; a named 0 is not replaced by default. per is the smallest positive capacity among suitable live workers, named or default; with none, use placement.capacity.default only if it is positive. With no positive estimate or default, order nothing for the set and use withheld "no positive capacity estimate". The order vector still returns its usual fields: per null and processes/in flight/needed/withheld zero, plus why; the pass report still shows short[] with workers 0 and withheld words, including shortage weight and groups. That zero means no computable estimate, not no shortage; it is not a step error.

<!-- req: P/04-R527 -->

Otherwise processes = ceil(max(0, sum of waiting weights − free at suitable live workers) / per) plus one per group with no room anywhere; needed = max(0, processes − sum of in flight(s) at suitable servers). In-flight capacity is subtracted for groups too, so the next pass does not order the same growth again.

<!-- req: P/04-R528 -->

A worker holding an exclusive place (N1.3 affinity.exclusive) contributes no free capacity for other units.

<!-- req: P/04-R529 -->

Waiting units bound to an exclusive place without a holder trigger an order for that place: its server_field server is considered out of order with share 1; empty server_field gives no order and the place waits for a holder. If that place’s secret did not open, give no order and withheld "\<place_by\> \<place\> is sealed". Sealed comes from place_error.\<place\> = sealed in heartbeats of live role workers on the place’s server (P/03.4 N1.1); with no live workers there, give one ordinary order.

<!-- req: P/04-R531 -->

For a manifest with places.wanted, an unheld place triggers a waiting piece of weight 1 when its place row passes places.where, its hold is inactive, and `<sub>/<wanted>/<place>` exists and reads. It need not wait for a record or unit: without a holder nobody reads its archive. For the places.wanted trigger, The server is from the row of the place, as for an exclusive place: server_field non-empty — this server is a candidate out of order, share 1, on top of the general check of the candidate; not fit — no order, the place waits; Sealed — withheld, as there. server_field empty — the place is on any server: the piece goes with the empty label set as an ordinary probe; a limit: a new process will take the first free place, not necessarily this one, a superfluous process lives until shrinking. For the places.wanted trigger, an unreadable wanted row gives no reason to order; write a journal line without the value. Another empty place does not itself cause an order.

<!-- req: P/04-R532 -->

With servers: distinct and a heartbeat-derived place_by, free at suitable live workers includes only place keepers. For that distinct heartbeat-place set, a candidate server has in flight(s) = 0 and no live suitable process without a place. For that distinct heartbeat-place set, order at most one probe process per pass, and at most one unfinished probe per server: its place is unknown before start. For that distinct heartbeat-place set, no candidate or exhausted growth leaves the rest of needed withheld with "no free \<place_by\>" (N4). A probe on one server does not prevent growth on another.

<!-- req: P/04-R337 -->

candidate s: the order row exists; the base `<prefix>`-`<s>`-1 is alive (otherwise no_base above: the server is not a candidate); free(s) > 0; want(s) < WANT_NUM_MAX (otherwise the reason «`<s>` has no instance numbers left», the alarm workers.no_server); the labels of the server suit the set (constraint), requires: resource — the resource is not silent; not draining, not decommission-pending or decommissioned; not «failed to raise» (RAISE_QUIET); servers: distinct — by the place place_by: with place_by: server a server with a live worker of the role is not a candidate, with a heartbeat field the place of a new process is unknown before its start — it does not restrict the choice of the server. candidate order: smaller live(s) + in flight(s) — by heartbeats (not by the door), then the server name in UTF-8 bytes

<!-- req: P/04-R339 -->

Distribute needed for the label set over candidates in their order; a share is at most min(free(s), WANT_NUM_MAX − want(s)). For a manifest with non-empty door.pass.calls, the want(s) ceiling is 1 instead of WANT_NUM_MAX: a ticket is bound to the server sheet, and there is one sheet per role and server (gate-and-pass, Pass of the second kind). After each order share, subtract that share from the pass’s free(s). Increase want(s) by the share through an order-row write with CAS of its read version and guard of the own placement_turn version; why uses "\<n\> more for \<labels\> on \<s\>: \<waiting\> waiting", with the canonical label set and "any labels" for the empty set. want is an absolute target: a repeat pass or new turn holder recomputes needed with in-flight capacity, without repeating growth; one logical order acts per shortage piece (label set). After all shares, any undistributed needed of the label set is withheld, as with a lack of candidates; with no candidates the entire needed remains. The withheld process count is in workers_withheld{labels} (P/06.5), words in report short.withheld (N1.2), and alarm workers.no_server {server, labels, want, why}.

<!-- req: P/04-R541 -->

Subsystem competition for the last room of a server across roles is an admissible delay; the common server memory ceiling over all roles remains a scheme limit.

<!-- req: P/04-R340 -->

withdraw on deadline: in flight(s) > 0 for longer than WANT_GRACE (N1.4 terms) → want(s) := 1 + |live numbers ∩ {2…want(s)}|; the script then renumbers: it stops a number above want, starts a missing one below; stopping a worker with an assignment is a move of the units; the server «failed to raise» for RAISE_QUIET, raise_failed.`<s>`.times + 1, the alarm workers.raise_failed {server, labels, want, why}; after RAISE_FAILS_LOUD in a row — of raised severity; it is removed when the server raised the order; the shortage is ordered on the next candidate in the same pass; the base does not count toward «failed to raise»

<!-- req: P/04-R341 -->

number above want: a live role process of the server s (the name and the number N — the slot name contract, «Role process name and its number»; not a role process — the rule does not apply) with a number greater than want(s) (raised after the withdrawal of the order, a shrink victim before its stop, a remainder of a door race) — not in the pool (as retiring) and gets no units; the server script stops it (P/02.4 N1.5 rules 3); the controller does not raise want(s)

<!-- req: P/04-R051 -->

Shrink step 9a follows the condition, victim and transition rules below. The [shrink checks](../forms/README.md#shrink-checks) select the first existing refusal reason; only `ok` permits shrinking. The victim, wanted-place protection, move and completion rules below still apply.

<!-- req: P/04-R343 -->

victim: only a live worker with n = want(s) > 1 of its server s is a candidate; select the largest eligible n (as an integer); a live number above want(s) is not a victim: the script stops it, the end of shrinking does not extinguish it; on equal numbers on different servers — the smaller name of the server in UTF-8 bytes first, as the order of candidates; each of its units (a group — whole) passes choose(unit) on the pool without the victim; otherwise do not shrink, the reason is in the report. wanted: only the top ordered number n = want(s) of a server may be a victim. If that worker holds a place with a readable row of places.wanted, skip the entire server and consider the top candidate of another server, with the same number/server ordering. Never fall back to a lower number on that server: reducing want would stop its protected top process. A removed wanted place would at once order a process.

<!-- req: P/04-R348 -->

retiring: write retiring = `<victim>` into the order row of its server (cas, guard turn); the victim is outside the pool of all steps (choose, move, home, reachability), and at a new holder of the turn — by the row; one victim per role at a time; in live(s) for «in flight» and «failed to raise» it stays while it is alive

<!-- req: P/04-R349 -->

move: no more than SHRINK_BUDGET units per pass, the reason «`<w>` is retiring: the role shrinks on `<s>`»; the first indivisible group goes even beyond the budget (as reachability, step 5)

<!-- req: P/04-R350 -->

end: the assignment of the victim is empty → want := want − 1 (not below 1) and retiring removed — by one write; the server script stops the process with the largest n (P/02.4 N1.5) — this is the victim: there is no in flight (the condition), the numbers 2…want(s) are alive, and the victim is the number want(s)

<!-- req: P/04-R351 -->

cancel: the shortage returned before the end → retiring removed, the victim is in the pool again

<!-- req: P/04-R352 -->

drain: a server in platform/drain gets no new orders; its additional processes are shrunk one by one without the hold time and hysteresis (the units leave anyway, «server `<s>` draining»), want − 1 with an empty assignment of the victim, down to 1

<!-- req: P/04-R353 -->

decommission: step 2 — accepting pending deletes the order row with cas and turn/request guards; pending/final servers get no new orders

<!-- req: P/04-R052 -->

**Races.** Two controllers write one order row: cas by the version and the guard `placement_turn` let one pass, the second re-reads and recomputes from the absolute target. The order has no separate kind of record in `placement_intent`: the absolute target under cas with the guard `placement_turn` and the capacity in flight close a repeat of the growth — a repeated pass and a new controller complete the target, they do not add to it.

<!-- req: P/04-R355 -->

The order against the script: the script reads the row once a minute (P/02.4 N1.5) and lags — a process raised after the withdrawal of the order, with a number above want, is not in the pool and is stopped by the script; a process stopped by the script with a non-empty assignment (a desync) releases the slot in the regular way (P/03.4 N3 «stop by SIGTERM») — this is a move, not a loss of units.

<!-- req: P/04-R356 -->

Shrinking and a change of the turn holder: `retiring` is in the row, the new holder continues the move and does not choose a new victim.

<!-- req: P/04-R357 -->

The door against the heartbeats: the candidate and the share are counted by `live.<sub>` of the door, the shortage — by heartbeats; the remainder of the race is a process with a number greater than want, raised after the door mark, for no longer than the mark period (ALIVE_EVERY): it is caught by the memory check of the workers script (P/02.4 N1.5, the ceiling by memory).

<!-- req: P/04-R053 -->

**The probe process with `distinct`.** A worker without a place carries no units and does not leave for another server: a place on its server is freed only by the leaving of the keeper, until then it stays idle. With servers: distinct and a heartbeat-derived place, a new probe process has place "" until its first heartbeat with a held place. In this window its server is not a candidate; it is also not a candidate while the probe is ordered but not raised. A delayed start gives that server no second probe; other servers remain candidates, with one probe process per pass.

### decommission_server(s) — a console request, executed by the controller

<!-- req: P/04-R054 -->

Controller decommission follows the acceptance, release, cleanup and finalization procedure below.

<!-- req: P/04-R495 -->

console: request, 409 server answers, platform/decommission/`<host>`, door deletion and withdrawal remain P/06.6 N3.

<!-- req: P/04-R359 -->

existing valid final mark and standing request: do not rewrite the mark, its slots or remaining contributions; no new cleanup is authorized.

<!-- removed: P/04-R360 by ADR-0133 -->

<!-- req: P/04-R361 -->

0. Resume a readable pending row before admitting a new plan. The fixed request_index of the pending row must still identify the current request.

<!-- req: P/04-R363 -->

Before mutation validate the progress invariants: remaining names are distinct and disjoint from released/skipped; released and skipped are disjoint; current is an ordered subset of released. Before mutation, validate that slot_cursor < len(current) and from_cursor <= len(from) when the pending decommission plan is in cleaning. Before mutation, validate that every from prefix of the pending plan belongs to this subsystem. The from list is frozen at plan acceptance from the declared owned books and is never rebuilt from a later manifest. A malformed pending progress plan is a step error: keep it; do not infer completion, release/delete anything or replace it with a fresh plan. Schema readability alone is insufficient.

<!-- req: P/04-R504 -->

With no pending or final row, if the server is heard by the ordinary observation rule, leave the decommission request standing without mutation; otherwise completely read the request, owned slots and required metadata. An incomplete or unreadable source while preparing the decommission plan is not an empty list.

<!-- req: P/04-R369 -->

Fix the original readable slots with server = s as ordered {name,index}, the owned from prefixes, asked_at, manifest_rev, units/holds metadata. Preflight every full key, the largest reachable serialized progress row and final mark, row weights, and real batch-body ceiling. Reserve the P/01 wire index width for cleanup_index; never parse an opaque version. An unrepresentable plan is a step error before any slot/order change, not a partial final mark.

<!-- req: P/04-R558 -->

The implementation chooses the initial order of planned slots, owned from prefixes and final-mark slots/units/holds lists; those ordering choices are not judged. Their required membership is unchanged. After plan acceptance, continuation must preserve the recorded list order and original indices; the release/cleanup procedure alone advances progress. Final-mark slots preserves the recorded confirmed released sequence, not all original candidates. There is no requirement to choose the fullest possible release chunk.

<!-- req: P/04-R559 -->

Before accepting pending, fix units as the unique union of ids in the assignments of the original slots and ids whose effective decisions name one of those slots. Fix holds as the place names of readable `<sub>/holds/<place>` rows whose `by` equals an original slot name; do not substitute heartbeat place values. Freeze both lists before acceptance. An incomplete or unreadable required source is not an empty list. These lists are final-mark metadata, not authority to delete units or contributions; the cleanup guards remain required.

<!-- removed: P/04-R370 by ADR-0133 -->

<!-- req: P/04-R371 -->

1. Accept pending with cas "" and delete an existing want row with its read cas in one conditional batch. The plan-acceptance batch uses guards of the own placement_turn version and the fixed request_index. Count both writes of the plan-acceptance batch. State prepared has remaining candidates; no candidates means finalizing. The pending server is outside the placement pool and gets no new orders/automatic want-row creation.

<!-- req: P/04-R376 -->

After acceptance continue only this frozen plan, also after a break or a later server answer; never add/adopt a new holder.

<!-- removed: P/04-R377 by ADR-0133 -->

<!-- req: P/04-R378 -->

2. Prepared: read each next candidate only to confirm its original index and obtain the unchanged readable slot items. A different index (including absence) is obsolete: move its name to skipped, never substitute the new version for release. A non-answer postpones the step; it is not obsolescence.

<!-- req: P/04-R381 -->

When releasing a planned readable slot in prepared, keep holder/gen/server/until and set released = "true"; never invent gen. Write up to BATCH_WRITES - 1 slots with their original cas plus pending with its read cas, guarded by turn and request. Atomically record their names in released/current and enter cleaning; the one returned batch index is the version of ALL those released slots AND pending.

<!-- req: P/04-R384 -->

After a lost answer, a cleaning row with empty cleanup_index carries that exact release index as its own row index: no slot reread is needed.

<!-- req: P/04-R385 -->

With no from families, the slot-release batch advances directly to prepared or finalizing with empty current/cursors.

<!-- req: P/04-R386 -->

A refused release batch changes neither slots nor progress: barrier/re-read pending; only discard candidates proved to have changed from their planned index, never retry a release against a newer slot version.

<!-- req: P/04-R387 -->

Persist skipped candidates under pending CAS and turn/request guards; when no remaining release candidates exist, advance directly to finalizing.

<!-- req: P/04-R388 -->

3. Cleaning processes one current slot at a time, with from prefixes in their fixed order, split across bounded batches. Cleanup authority for the current slot is cleanup_index when non-empty, otherwise the current pending row index. Before ANY rewrite of progress, preserve the exact release authority in cleanup_index; a later pending index must not replace it.

<!-- req: P/04-R507 -->

Delete existing contributions by their read CAS plus pending progress in one batch, guarded by the own turn, fixed request and this slot’s exact release index. For each cleanup batch, count all deletes AND progress/service writes, every guard, row weights and the full serialized body. A cleanup batch must not use any guard key as a written key.

<!-- req: P/04-R510 -->

A confirmed missing contribution advances the cleanup cursor; an unknown read does not.

<!-- req: P/04-R511 -->

A 409 conflict or 412 guard discards ALL remaining removals for this slot, without a new slot read or retry. Record cleanup cursor advancement under turn/request guards; never delete a new holder’s contribution.

<!-- req: P/04-R513 -->

Only confirmed cursor progress permits the next current slot and then the next release chunk. After finishing one current slot, advance slot_cursor and reset from_cursor. After finishing the whole current chunk, clear current, cleanup_index and both cursors; in a guarded progress write set prepared when remaining is non-empty, otherwise finalizing.

<!-- removed: P/04-R389 by ADR-0133 -->

<!-- req: P/04-R390 -->

4. Every prepared/cleanup/final batch fits BATCH_WRITES, BATCH_GUARDS and the actual body ceiling. If even one indivisible operation plus required service writes cannot fit, record a step error and keep progress, never publish completion.

<!-- req: P/04-R392 -->

Renew the turn by the ordinary rule; an unknown write or lost turn stops further mutation behind the existing barrier.

<!-- req: P/04-R393 -->

A new holder re-reads pending after taking the turn and resumes its recorded phase, never restarts releases from slot names.

<!-- removed: P/04-R394 by ADR-0133 -->

<!-- req: P/04-R395 -->

5. Only after remaining is empty and the current chunk's eligible removals are confirmed or conservatively discarded, enter finalizing. Atomically write the absent final `<sub>`/decommissioned/`<host>` mark from released/units/holds and asked_at (at = now), delete pending by cas, and delete a remaining want by cas if necessary, with turn/request guards. Count EVERY service write in the finalization batch. The final mark is the LAST atomic step, never plan acceptance or merely the first released chunk.

<!-- req: P/04-R399 -->

A failed/unknown final batch proves no completion: use the barrier and confirm the actual pending/final state before continuing.

<!-- removed: P/04-R400 by ADR-0133 -->

<!-- req: P/04-R401 -->

6. A withdrawn/replaced request cancels its old pending row with cas and guards proving the current request state and own turn; it does not roll back confirmed releases/deletes, invent a final mark, or authorize an old delayed batch for a new request. Withdrawal removes an existing final mark as before.

<!-- req: P/04-R403 -->

The resource publishes its door again; contributions return by normal start/capture cleanup, not by rollback.

<!-- req: P/04-R404 -->

A new request requires a new admission and fresh plan.

<!-- req: P/04-R055 -->

The console side (the refusal 409 `server answers` by [the observation contract](../../common/contracts/observation.md), the write of the request, the delete of the door row, the withdrawal) is [chapter P/06.6](../../06-console/spec/06.6-console.norms.md) N3 «decommission_server(s) — the console side»; here — the execution by the controller.

<!-- req: P/04-R056 -->

**Races.** The decommission of a server and the return of its workers: `decommissioned/*` is written with `cas`; a worker of this server checks the decommission at the capture (P/03.2 N3 «start()», step 3: `platform/decommission/<s>` or `<sub>/decommissioned/<s>`) and does not take the name; the console request and the pass of the controller are separated by a row — a repeat of the request is idempotent.

### manifest_rev — the rule guard

<!-- req: P/04-R405 -->

Every placement write follows the manifest revision guard below. before every write of a placement row (place, move, remove): a missing manifest_rev is unreadable, never stamped. row.manifest_rev > my revision → do not touch; the row — into manifest_behind. manifest_behind (N1.2): the number of rows of this pass whose write is postponed because of a lagging manifest; each row — once per pass, however many write attempts touched it

---

<!-- req: P/04-R058 -->

**Races.** A change of the manifest during a pass: `rev` is read once per pass, the decisions are written with this `manifest_rev`; the controller sees a change of `rev` by the mark check (P/02.3) and stops with code 0; a new instance with the new `rev` re-reads everything; a row with a former `manifest_rev` is a snapshot of a decision, not a rule.

### controller start — schema check

<!-- req: P/04-R059 -->

The environment and the launcher argument are inventoried in [forms/daemon-flags.tsv](../forms/daemon-flags.tsv). Derived defaults and imported checks remain the linked contract rules; no CLI flags are added.

<!-- req: P/04-R060 -->

The current controller start check uses the common block of [P/06.6](../../06-console/spec/06.6-console.norms.md) N3 «console start — schema check». The platform/schema row, SCHEMA and its raise remain P/06.6 N1.1a, N3 «raise_schema». start: the schema contract «Check at start» ([the schema contract](../../common/contracts/schema.md))

### table snapshot — after the unit snapshot, before the final report

<!-- req: P/04-R062 -->

Table snapshots follow the procedure below, after unit snapshots and before the final report. For each table from domain.view_tables of the manifest, build rows by N1.3b in key order. Skip a row whose field does not read by its type and increment snapshot_rows_garbled. Form the candidate ordinary object or ceiling stub, then apply the comparison without ts of P/04-R174; an unchanged cluster/refused/rows preserves the former ts and causes no write.

<!-- req: P/04-R411 -->

serialize; more than SNAPSHOT_TABLE_MAX → write the stub of N1.3b ceiling, snapshot_tables_refused + 1, a log line once per series.

<!-- req: P/04-R412 -->

an error reading a table — do not write the object, a log line once per series: an empty object is not published instead of an unread one

### snapshot — after the control part, before the final report

<!-- req: P/04-R498 -->

Unit snapshots follow the procedure below, after the control part and before the final report. per worker: the unit rows of its assignment → [{id, revision, the fields of snapshot (address mask), worker, server}].

<!-- req: P/04-R413 -->

A unit row whose snapshot field does not read by its type is skipped; log once per series and increment `snapshot_rows_garbled` of the pass report (N1.2; N1.3a garbled).

<!-- removed: P/04-R414 by ADR-0133 -->

<!-- req: P/04-R415 -->

the unplaced → unplaced; a shard that existed and is not filled → empty; without units → an empty unplaced. an empty shard — {cluster, worker: null, ts, `<rows>`: []} (N1.3a).

<!-- req: P/04-R417 -->

Each snapshot unit carries state by N1.3a (the acting states from the snapshot list); an unreadable state is omitted from that unit and increments `snapshot_state_garbled`.

<!-- removed: P/04-R418 by ADR-0133 -->

<!-- req: P/04-R419 -->

serialize each shard; check the size by N1.3a before the write; more than L → TooLarge, do not write this shard. write an admissible shard; TooLarge of the store → the same refusal; a publication error — one log line per series.

<!-- req: P/04-R421 -->

TooLarge before the write keeps the former shard and its time; an unknown outcome of a write does not prove that the shard stayed the former one. On any error do not publish an empty shard instead of unchecked data

<!-- req: P/04-R064 -->

**Races.** On one server there is one controller of a manifest; different servers can publish different local copies of one logical shard key. A choice by written does not create a common moment of reading. Rows and shards are published separately: a snapshot is an observed configuration, not a consistent backup. An error reading the rows/list does not allow publishing an empty shard; an error of one write does not roll back the ones already published. A consumer checks revision and does not infer absence from an incomplete set.

### pull the power (do nothing) — a drill

<!-- req: P/04-R065 -->

t = 0 the server is off; its daemon — minus a vote; its heartbeats and its door stop changing. In this drill, at about 45 s, controllers with already known heartbeats observe expired slots and a silent resource, with the tolerances of N3. In this drill, controllers with already known heartbeats move units after SLOT_TERM + LOST_AFTER, with all tolerances of N3 and free capacity; the new holder takes the next epoch. In this drill there is no common movement deadline with unknown/unavailability/lack of room; the archive remains on the server volume.

<!-- req: P/04-R430 -->

In this failure drill, neighbours have only confirmed mirror copies.

<!-- req: P/04-R431 -->

return the daemon restarts with the saved member.json (does not repeat join); the resource pulls the buckets (restore); the workers take free names; names with expired slots — by the word of the controller; nothing moves back, except a declared `home` (N3 «pass()», step 7, HOME_BUDGET)

<!-- req: P/04-R066 -->

**Races.** The failure coincides with a renewal, a write and mirroring; the boundaries are this lesson, [P/03.2](../../03-worker/spec/03.2-worker.norms.md), [P/05](../../05-resource/spec/05-resource.norms.md). The absence of operator actions does not turn an observation into a snapshot. The terms given are the profile of the drill, not a guarantee for an arbitrary failure.

---

## N4 Refusals

<!-- req: P/04-R067 -->

The refusals of the console doors (the policy, the drain, the labels, the server decommission, `/where`, the common codes of the console) are [P/06.6](../../06-console/spec/06.6-console.norms.md) N4 and [P/06.5](../../06-console/spec/06.5-console.norms.md) N4. The row «an intent row out of the form of N1.5» is given here whole: 503 at the reader doors of the console, failures at the controller.

<!-- req: P/04-R068 -->

The closed catalogue is [forms/refusals.tsv](../forms/refusals.tsv), `chapter = 4`. Columns `cause`, `outcome`, `diagnostic`, `caller` define the cause, outcome, diagnostics and caller action; fixed machine codes supplement these fields. `peer` refers to the console contract, not a controller HTTP API.

<!-- req: P/04-R564 -->

Whenever this lesson requires a log once per series, the implementation defines the series and its key and declares them in its description, for example by shard, error type or field. One mandatory log entry is written for each declared series; silence is forbidden. The chosen grouping and the exact log count between otherwise admissible implementations are not judged.

---

## N5 Acceptance

<!-- req: P/04-R437 -->

Acceptance uses a stand of the workers and the controller of `testsub` and `testsub2` of the implementation under the control of the runner on a catalogue of two manifests ([the common README of the acceptance](../../common/acceptance/README.md), section «Stand»); sc. 12, 14–17 — with the resource P/05 on the server of the controller; the rows are read through the store door P/01.1, the console doors (`/where`, `/unplaceable`, `/servers`, `/metrics`) and the pass report object through the resource door. The acceptance contains 40 scenarios / 575 steps. In scenario 11, steps 7–12 prepare the shelf. Scenarios 07, 11 and 13 begin with `@start resource`; scenario 25 uses `@cut role`/`@mend role`, and scenarios 26 and 27 use `@freeze`/`@thaw`.

<!-- req: P/04-R441 -->

Scenarios 03 and 08 cover the snapshot without the console `/metrics` steps; the reader side is [chapter 6.5](../../06-console/spec/06.5-console.norms.md).

<!-- req: P/04-R442 -->

Detailed case descriptions and their expected outcomes are recorded in the judge's case data. Governing rules and the public acceptance scope remain in this chapter.

<!-- req: P/04-R444 -->

The console doors without workers (a unit without a worker, `/unplaceable`, the policy, the drain, the labels, the server decommission) — sc. 01–07 [of the acceptance of P/06.6](../../06-console/acceptance/6/README.md).

<!-- req: P/04-R445 -->

The snapshot — sc. 03 and 08; the age of a shard and a spoiled shard in `/metrics` of the console — the acceptance of [P/06.5](../../06-console/acceptance/5/README.md); the shards of a gone worker — N3 «snapshot»: an empty shard — sc. 40, the size of a shard with `ts` — N1.3a `ceiling` — by reading.

<!-- req: P/04-R446 -->

A server failure (N1.4a) is covered by drill 05 of [system acceptance](../../common/acceptance/system/README.md). Server-failure witnesses also include scenario `09-resource-door` of [P/05 acceptance](../../05-resource/acceptance/README.md) (judge-only: checks P/04-R065, P/04-R066). Server-failure witnesses also include scenario `14-resource-silent` of [P/06.5 acceptance](../../06-console/acceptance/5/README.md).

<!-- req: P/04-R449 -->

The start refusal by the schema — N3 «controller start — schema check»: `version` above SCHEMA and not a number, code 2 — sc. 23; a read error — wait — sc. 25; «before the manifest is read» — by reading.

<!-- req: P/04-R450 -->

The vectors [`order`](../vectors/order/README.md) (the shortage of a label set and the order over the servers), [`shrink-victim`](../vectors/shrink-victim/README.md) (the shrink victim) and [`shrink-allowed`](../vectors/shrink-allowed/README.md) (whether shrinking is allowed and the order of the refusal reasons) — N3 «shortage(), order()…», «shrink».

<!-- req: P/04-R451 -->

Checked by reading and on the stand (workers with heartbeats are needed — sc. 02-unit of the acceptance of P/03.3, 03-sigterm — P/03.4, 05-sigkill — P/03.2; the stand of the system acceptance): the choice of a worker and the reason; the group whole (except «room for all or all wait» on one worker — sc. 22); the weight and the free capacity; `distinct` and the keeper of the place; the spread, the neighbourhood, the home, the affinity (except the spread by a non-empty zone, binding shelves, a move home and `admits: false` — sc. 36–39, the home at the holder with two places of a server — sc. 43, on a place without a server — sc. 44); the slot fate by each rule and `names_given` with the version (except the release of a slot without units and the write release by the slot row — sc. 21; the margin and `hung` of a live silent worker with a unit and without — sc. 26, 27; `wait` before HUNG_MOVE_AFTER — sc. 42); the move through intent and the repair `sync` (except the recovery of intent by one holder, `sync` of one assignment and an unreadable intent — sc. 28–30); leaving by each reason (drain — sc. 33, the place does not admit — sc. 39); drain with live workers (except the move and `safe` — sc. 33); decommission with live workers, `gone: true`; a url group without a host (without a value and with an unreadable value, and with them `spread_by: zone` without a value — sc. 11; drain «assignment ∪ `status`» — sc. 07 of the acceptance of P/06.6); `fates` and `since`; presence only from the live heartbeat of the resource; the order, the withdrawal on deadline, the number above want and shrinking, except the shrink condition by the input of the pass — with the branch «live ones without a place are not shrunk while there are waiting» with `servers: distinct`, which sc. 17 does not distinguish from the hysteresis; it is checked by the vector `shrink-allowed`; the delete by `delete_after`; `manifest_rev` and `manifest_behind` with two revisions of the manifest (the rows and the turn decided by a newer revision, without a change of the manifest — sc. 31, 32); the pass report.

<!-- req: P/04-R452 -->

**Pass obligations.** The acceptance has 63 CALL seams. Public obligations cover resource-state/fate handling, top-number and wanted-place protection composed with the P/02 script stop plan, excluded expired manual rows, complete decommission and durable recovery under exact guards, regular-loader name restrictions and progress validation before mutation. The public pass witnesses use the existing controller-pass/fate ports and actual IO observations of the forms README, not new commands or kit parts. Detailed named witness inputs and outcomes are judge-only coverage.

<!-- req: P/04-R456 -->

Current reader/writer requirements are the data-family source, including the three report counters, one snapshot array, required placement manifest_rev and active nonempty reason. Pending recovery, exact opaque guards and the named current witnesses remain required.

<!-- req: P/04-R458 -->

Source/schema projections do not prove OS stop, process recovery or runtime acceptance; related generator/runner checks and joint GATE remain separate.

### Evidence outside TSV

Scenarios 01–06 [of the acceptance of P/06.6](../../06-console/acceptance/6/README.md) observe an empty pool and several refusals; they do not prove the other branches.
«Reading» below means a check of the transitions of the implementation by the owner of the implementation with the given
interventions; in the translation window the author reads only documents and does not claim that code passes.

| Norms | Subject and intervention | What must be shown |
|---|---|---|
| P/04-01…03, 12, 16 | two controllers, a pause/break after each read and write of placement/workers; a newer manifest_rev | cas/guard by own versions, a repeated check by the mutator, the repair sync, the old rule does not write |
| P/04-04, 05 | the first look, a shift of ts, an absence/damage/empty row of labels (a row, an empty and an unreadable row with node labels — on the stand sc. 24) | life by local observation; labels are not guessed on a non-answer |
| P/04-06…09, 18 | two weights, equality, a group, distinct, incompatible constraint/home; the weight of a row `"7x"` and the capacity of a heartbeat `"2x"` | an admissible candidate and a non-empty reason; a preference does not bypass a filter; a spoiled weight — the unit in `garbled` and `unplaceable`, a spoiled capacity — a worker without new units, the reason in the report, not `default` |
| P/04-10, 11 | each fate outcome before/at/after the boundary; a renewal between the judgement and the capture; gen damaged; `gone` without assigned units and with them (without units and the write release — on the stand sc. 21) | the order of the judge, the version of names_given, an unknown generation is not reset; `release` before `move` for a slot without units (the transition table of N3) |
| P/04-13, 14, 15 | all reasons of leaving; an order by two controllers, the withdrawal on deadline, the number above want, shrinking with a change of the turn holder; the count of delete_after | budgets/group, one logical order per piece of shortage, retiring survives the change of holder, the delete by version and local time |
| P/04-17 | a successful/partly refused pass, grows on/off | the required fields of the report, failures, short and wants correspond to the steps performed |
| P/04-20 | a unit whose key `<sub>/placement/<id>` is 1 byte longer than the key limit of the store, with free capacity; the same unit in a group | the intent is not written; the unit is in `unplaceable` with `why`; the other units of the same subsystem are placed |
| P/04-19 | two controllers admit different units with capacity 1; spread_by; a group with different home; a change of holder after each step of intent | one common decision, no overload/split from competition; late writes are cut off by turn; an incomplete transfer is completed before the next admission |
| P/04-R558, P/04-R559 | readable disagreement between assignments and effective decisions before decommission admission; holds.by differs from heartbeat place | checked by reading: exact metadata membership and frozen sequences; the decommission witnesses exercise chunk/progress recovery, not these conflicting metadata sources |
| P/04-R562, P/04-R563 | missing base together with quiet/pending; waiting in one label set while another has none | checked by reading: state priority and one role-wide no-shortage timer; the shrink vector receives an already computed timer and does not prove its aggregation |
| P/04-R174, P/04-R062 | unchanged rows with a changed cluster or stub/ordinary transition; a new ts only | checked by reading: compare the complete candidate without ts; the unchanged-table witness keeps the envelope unchanged and does not distinguish those transitions |
| P/04-R292, P/04-R566 | a label mismatch under none and labels-subset; choose without a candidate | checked by reading: mismatch under none is not reachability shortage, failed choose preserves placement and reports the reason for an unplaced unit; the label stand scenario uses labels-subset |

---

Remaining fault checks are by reading the implementation transitions: controller-native journal/disk failures (P/04-R459, P/04-R069), a stop at every intermediate intent phase or with an old request in flight (P/04-R026, P/04-R254, P/04-R259, P/04-R269, P/04-R275), and restart of the long order/shrink/delete timers (P/04-R482, P/04-R479, P/04-R271). The process stand can kill a controller but cannot select such an internal phase or disk operation, and its clock is not the virtual seam clock. Existing intent/decommission/snapshot seams cover their named interventions; they do not prove the other crash points. Production fault qualification remains separate from these functional witnesses.

## Implementation decides

The implementation is to name in its description:

1. **how the cache and retries implement the fixed sources** — PASS_EVERY, TURN_BUSY_RETRY and WRITE_CONFLICT_LIMIT are norms in forms/runtime-constants.tsv, not discretionary values. The judge observes the pass results, busy-turn retry and conflict-limit outcome; the cache layout and retry implementation are not compared.
2. **the cache between passes** — what is held by the row version, and how this does not change the decisions (the rows decide, not the cache). After turn acquisition and between decisions the judge observes the fresh store decisions and assignments; after restart the former placement version/rev and epoch remain until a new decision is needed.
3. **how the resource of a server reports the presence of a process** (the form of the field `workers` of the resource heartbeat — P/05 N1.4) and the presence lock ([the presence lock contract](../../common/contracts/presence-lock.md)). The judge observes fates and names_given from the fixed presence words and only a live resource heartbeat; it does not call a private controller presence API.
4. **how the effective inputs are read** — channel and defaults are the named source of lifecycle/forms/common contracts, not another local choice. The stand observes the effective settings through the required report/snapshot fields and policy effects, and start refusals through the exit codes of lifecycle.md.
5. **how rebalancing is requested** and who calls it; the declared budget of P/04-R164. The common functional judge does not call this private channel; P/04-R164 is checked by reading.
6. **additional fields of the report** beyond N1.2 and how the metrics are made from it (the series `<sub>_reconcile_*`, `<sub>_units_unplaced`, `<sub>_units_diverged` — P/06.5 N3 «/metrics — text»). The judge reads the required fields and types of the N1.2 object and the fixed metric series of P/06.5; extra counters do not replace those fields.
7. **the exact texts** of reasons and refusals beyond the grammar of N3/N4. The observable values are placement.reason, the console answer and the refusal outcome of N4; the MUST for a non-empty reason and the SHOULD grammar of N3 remain in force.
8. **what a manifest without `grows` does** with a shortage (it counts nothing) and where the server script lives (`w2c-workers.sh`, P/02.4 N1.5 `script`). Without grows the judge observes no growth order; the script name and its target/stop behaviour remain those of P/02.4.
9. **the command printing the pass report** `<sub>/controller/pass` for the acceptance — by the section «Stand» of the common README of the acceptance. The judge observes the N1.2 JSON object through the resource object door; a chosen inspection command prints that same report and does not define another report form.
10. **how the snapshot is published** on a store refusal (a log once per series); the period — after every pass (N1.3a `publish`), there is no choice. The judge observes a kept shard/time on TooLarge before put, the actual read-back on an unknown write outcome, and the once-per-series log; unchecked data never become an empty replacement.
11. ~~**where the `cluster` of the snapshot comes from**~~ — normed: `CLUSTER` of the environment (N1.3a; P/02.4 N1.2), not set — `local`. The snapshot field cluster is the supplied CLUSTER value or local when unset.
12. **the chosen list orders** of P/04-R558 and P/04-R561; the implementation decides and these choices are not judged. List membership, frozen plan sequences and the normative table-snapshot order remain required.
13. **JSON representation** of P/04-R560; whitespace, object-key order and either admissible manifest_rev notation are not judged. Exact values, required forms and actual serialized-byte ceilings remain required.
14. **series and their keys for mandatory logs** by P/04-R564; the grouping is not judged, and silence does not satisfy a mandatory log.
15. **the pass schedule after an overrun** by P/04-R565; the scheduling choice is not judged, while the period without an overrun and non-overlapping cycles remain required.

---

## Readiness checklist

An implementation conforms to the lesson when every norm is fulfilled; a norm id `P/04-MM` is what the decision deltas,
findings and window records refer to:

- [ ] **P/04-01** [test, reading] the effective decision is the active intent for members, otherwise placement; the assignment is derived; `rev` grows; `sync` repairs a broken one — sc. 01 [of the acceptance of P/06.6](../../06-console/acceptance/6/README.md); the removals of all members before the addition and the completion by a new holder after a break in the middle — the seam `s18-intent-removals-before-add`, no new admission after an unknown outcome — the seam `s19-intent-unknown-barrier` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R006, P/04-R021, P/04-R027, P/04-R036) (`CALL controller-complete-intent`); the recovery of an active intent by a new holder — sc. 28, `sync` of one assignment and `diverged` — sc. 29, an unreadable intent at the controller — sc. 30 [of the lesson acceptance](../acceptance/README.md) (judge-only: checks P/04-R006, P/04-R021, P/04-R027, P/04-R036); a double read of intent — checked by reading
- [ ] **P/04-02** [test, reading] decisions and an unfinished intent are kept in the store; every write is with `cas`; placement changes go through the common turn with CAS/guard by N1.5/N3; the local observation history starts anew after a restart and does not replace reading the decision — a restart of the controller: the decision and the epoch are the former ones, the new instance places — sc. 20 and 47 [of the lesson acceptance](../acceptance/README.md) (judge-only: checks P/04-R209, P/04-R212, P/04-R027, P/04-R030); an unfinished intent from the store is completed by a new holder — sc. 28, in logical time — the seam `s18-intent-removals-before-add` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R209, P/04-R212, P/04-R027, P/04-R030) (`CALL controller-complete-intent`); the rest is checked by reading
- [ ] **P/04-03** [test, reading] the order of the pass of N3 — checked by reading; an attempt per step: the error of one step gives `ok: false` and `failures` 1, and the later steps still run — the seam `s33-pass-report-partial-failure` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R030) (`CALL controller-pass`)
- [ ] **P/04-04** [test, reading] the picture of the world: capacity, server, node labels — without a term; life — by a change of the heartbeat within 45 s by the clock of the controller; seen for the first time — has just changed — checked by reading (stand P/03.3, sc. 02-unit; no scenario observes the term of 45 s); the boundary `≤ LOST_AFTER` — the vector [`fresh-age`](../../common/vectors/fresh-age/README.md); the reading of a heartbeat by the form of its family — the vectors [`heartbeat-read`](../../common/vectors/heartbeat-read/README.md)
- [ ] **P/04-05** [test] server labels: the row beats the node, an empty one — «reaches nothing», an unreadable one — the last ones and without a judgement; the label alphabet — the vectors [`labels`](../../common/vectors/labels/README.md) and sc. 05 of the acceptance of P/06.6 (form refusals); the priority of the row over the node, an empty list, an unreadable row — sc. 24 [of the lesson acceptance](../acceptance/README.md) (judge-only: checks P/04-R005, P/04-R030) (the stand of the acceptance of P/06.6 (sc. 01–07) has no workers)
- [ ] **P/04-06** [test, reading] the pool, the constraints, the preferences in the order of N3; the placed is not reconsidered — checked by reading; a preference does not bypass a constraint — the seam `s21-preference-respects-filter` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R009, P/04-R030, P/04-R033) (`CALL controller-choose`); the pool and the fitness of a server — the vectors [`pool`](../../common/vectors/pool/README.md) (judge-only: checks P/04-R009, P/04-R030, P/04-R033); an unreadable assignment is outside the pool — sc. 41; `spread_by` with a non-empty value — sc. 36; a binding shelf leads to its holder — sc. 37; home (step 7) — sc. 38, the holder of the place with two places of a server — sc. 43, on a place without a server — sc. 44 [of the lesson acceptance](../acceptance/README.md) (judge-only: checks P/04-R009, P/04-R030, P/04-R033); the fallback to the server of the place with a worker of another server — by reading: there are no vectors for the choice of a worker, and sc. 43 stands on one server;
  `affinity.strict` selects the binding rows, a non-binding shelf is a preference: `tallies` on the shelf `plain` with
  `strict.kind: [reserve]` are placed — sc. 07 [of the acceptance of P/03.6](../../03-worker/acceptance/6/README.md) (judge-only: checks P/04-R009, P/04-R030, P/04-R033)
- [ ] **P/04-07** [test, reading] weight and free capacity: Σ of the weights, strictly more, the first by name — equality of capacity: sc. 07; heavier than any — `unplaceable` — checked by reading
- [ ] **P/04-08** [test] the group whole: room for all or all wait — sc. 22; no value of `group_by`, it is empty, does not read
  or has no host — not a group — the vectors [`group-of`](../../common/vectors/group-of/README.md) and sc. 11; `spread_by` without a value does not spread — sc. 11 (the stand of two manifests, `testsub2`)
- [ ] **P/04-09** [test, reading] `distinct`: one keeper per place, the largest load, on equality the slot order of P/03.2 N1.4 for all admissible names; the policy by a row, a soft read, a strict write — sc. 03 of the acceptance of P/06.6; the slot order of the names — the vectors [`slot-name`](../../common/vectors/slot-name/README.md) (`op: order`); units only at the keeper of a non-empty place — sc. 11, one shelf: one keeper, the trial process without a place carries no units — sc. 17 [of the lesson acceptance](../acceptance/README.md) (judge-only: checks P/04-R009, P/04-R033); the largest load and the order on equality between keepers — by reading by the [README of the acceptance](../acceptance/README.md) (judge-only: checks P/04-R009, P/04-R033) («Checks by reading»)
- [ ] **P/04-10** [test, reading] the slot fate of N3: the outcomes, the order of the rules, presence only from the live heartbeat of the resource, the terms SLOT_TERM/LOST_AFTER/HUNG_MOVE_AFTER, the controller does not write the slot except `release`; an unreadable gen is not reset and does not allow its capture — the outcomes and the exact boundaries of the terms: the seams `s1-fate-before-term`, `s3-fate-gone-with-units`, `s4-fate-margin`, `s5-fate-two-silences`, `s6-fate-gone-before-fresh-beat`, `s7-fate-hung-young`, `s8-fate-hung-boundary`, `s9-fate-wait-no-units`, `s10-fate-wait-boundary`, `s11-fate-runs-no-units`, `s12-fate-presence-unknown`, `s13-fate-unreachable-boundary`, `s34-fate-resource-never-seen-assigned`; the write release of a slot without units with the former items — `s2-fate-release-term`, `s35-fate-resource-never-seen-empty`; a lost CAS of release — `s15-release-cas-race`; an unreadable gen — no write and no permission — `s14-fate-no-permission-bad-gen`, `s16-release-unreadable-gen` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R039–P/04-R046) (`CALL controller-fate`); the judgement of a slot row — the vectors [`slot`](../../common/vectors/slot/README.md), the state of a resource — the vectors [`resource-state`](../../common/vectors/resource-state/README.md); on the full stand: release of a slot without units (not move), the write release of a readable slot, of a torn `until` and of an unreadable gen — sc. 21 [of the lesson acceptance](../acceptance/README.md) (judge-only: checks P/04-R039–P/04-R046); the margin SLOT_TERM + LOST_AFTER and `hung` with the presence `runs` (the name is not given, the slot is not released, the unit does not leave; without units — not release) — sc. 26, 27; `wait` with `unlisted` (the name is not given, the slot is not released) — sc. 42; the local observation starts anew after forced controller restart — sc. 42; the terms on a real server failure — P/04-22
- [ ] **P/04-11** [test] `names_given` is bound to the version of the slot row; only NAME_FATES and `wait` beyond the limit; a row with an unreadable gen is not included until the generation is recovered — the permission version `permission_version` of the seams `s2-fate-release-term`, `s3-fate-gone-with-units`, `s8-fate-hung-boundary`, `s35-fate-resource-never-seen-empty`; `wait` gives the name only beyond the limit — `s9-fate-wait-no-units`, `s10-fate-wait-boundary`; an unreadable gen and a lost release CAS — no permission — `s14-fate-no-permission-bad-gen`, `s16-release-unreadable-gen`, `s15-release-cas-race` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R040, P/04-R041, P/04-R042, P/04-R046) (`CALL controller-fate`); on the full stand: the name of a released slot in `names_given`, an unreadable gen outside it — sc. 21; `wait` does not give the name before the limit — sc. 42
- [ ] **P/04-12** [test, reading] move/first addition/sync — one intent: remove all members from all assignments, complete placement, add to one target and only then idle; each change with cas and guard turn, 412 stops the attempt; the removals before the addition — the seam `s18-intent-removals-before-add`, no write after an unknown outcome and a failed barrier — the seam `s19-intent-unknown-barrier` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R027, P/04-R036, P/04-R037) (`CALL controller-complete-intent`); the completion of an active intent (removal, row, addition, idle) — sc. 28, `sync` — sc. 29 [of the lesson acceptance](../acceptance/README.md) (judge-only: checks P/04-R027, P/04-R036, P/04-R037); `Moved` with an already different source target (N3 «move», step 1) and the rest — checked by reading
- [ ] **P/04-13** [test, reading] leaving: the reasons in order, without a budget, a group whole or it stays — checked by reading; `silent` — only with `requires: resource` and a live worker, otherwise the fate of SLOT_TERM + LOST_AFTER — P/04-30; a released slot — the units without a place are removed (`worker: ""`) — sc. 03 of [the acceptance of P/03.4](../../03-worker/acceptance/4/README.md) (judge-only: checks P/04-R047, P/04-R322); a capture in progress (`taking`) takes them away only after SLOT_TERM of an unchanged version — sc. 13; drain — sc. 33, the place does not admit (`admits: false`) — sc. 39; reachability with constraint: labels-subset by P/04-R150 and P/04-R566: the server no longer reaches the labels of the unit, the unit is removed with a reason of reachability — sc. 24 [of the lesson acceptance](../acceptance/README.md) (judge-only: checks P/04-R047, P/04-R322); the budget REACH_BUDGET — checked by reading
- [ ] **P/04-14** [test, reading] order: per — a positive observed capacity, otherwise a positive capacity.default, otherwise withheld without division; the shortage by label sets and weight minus the capacity in flight; the order row always, `want` 1…WANT_NUM_MAX as an absolute target, cas and guard turn; the candidates (the base is alive, room, numbers, distinct by place_by, drain, decommission); the withdrawal on deadline `WANT_GRACE`, «failed to raise» `RAISE_QUIET`; shrinking — `SHRINK_AFTER`, hysteresis, only the live top number n=want(s)>1 per server; a protected top skips its whole server (a number above want is not a victim), `retiring`, `SHRINK_BUDGET`, cancel; the alarms `workers.no_server`, `workers.raise_failed`; in flight — the numbers 2…want without a live process by heartbeats, the candidate and the share — by the door (`live.<sub>` by numbers, free once per pass), a number above want is outside the pool (its stop by the script on the host — P/04-31), the withdrawal on deadline — by numbers, `distinct` with the place from the heartbeat — a server without a live suitable one without a place, without a probe in flight (in flight(s) = 0), no more than one probe per pass, and `no free <place_by>`, the capacity — the smallest positive one, the forms of `short[]` — the vectors `order`, `shrink-victim`, `shrink-allowed` (the shrink condition and the order of the refusal reasons, including live ones without a place while there are waiting); the deadline `WANT_GRACE` restarts when the number falls again — the seam `s32-want-grace-restarts` (`CALL controller-want`); a protected top skips its server — `s36-shrink-wanted-top-prefix`, the victim on another server — `s37-shrink-wanted-other-server`; the end of growth with a manual row does not block shrinking — `s38-growth-ended-manual-row`; `short[]` at the bound 2^53 — `s51-short-weight-max53`, `s52-short-weight-at53`, `s53-short-weight-odd53` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R050, P/04-R051, P/04-R052, P/04-R053) (`CALL controller-pass`); on the full stand — sc. 14–17 after P/05 (`@grow`), completion of a persisted retiring by a new controller — sc. 45; the rest by reading
- [ ] **P/04-15** [test, reading] `delete_after` by the clock of the controller from the first look, a fresh check of the effective placement, `cas` of the unit and guard of the own turn, the journal: the count from the removal — the seam `s22-retire-counter-reset`; a refused delete of the unit deletes no state and writes no journal — `s23-delete-cas-then-state`; `409 early` without a barrier and a journal — `s25-made-delete-early` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R030) (`CALL controller-delete-after`); the journal bucket and the names — the vectors [`journal`](../../common/vectors/journal/README.md); the fresh check of the effective placement and the guard of the own turn — checked by reading
- [ ] **P/04-16** [test, reading] current manifest_rev is required, no missing-revision stamp; the rule guard and manifest_behind for a newer row — sc.31; a newer placement turn is not taken — sc.32 [of the lesson acceptance](../acceptance/README.md) (judge-only: checks P/04-R405, P/04-R058); manifest change/code0 remains checked by reading
- [ ] **P/04-17** [test, reading] the pass report of N1.2 with the required fields; `fates` — only occupied slots not released, `since` — the entry into
  the fate; `short[]` and `wants` with `grows`, the waiting without the removed and the unreadable — the error of one step: `ok: false`, `failures`, the later steps run — the seam `s33-pass-report-partial-failure`; the counters of the same cycle — `s57-snapshot-state-garbled-same-cycle`, `s58-snapshot-rows-garbled-same-cycle`, `s59-snapshot-tables-refused-same-cycle`; `state_swept_total` is cumulative — `s60-sweep-total-cumulative`; one report write after the publications — `s61-publication-read-failure`, `s62-publication-store-too-large`, `s63-publication-reply-lost` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R007, P/04-R008) (`CALL controller-pass`); the fields `diverged` (sc. 29), `manifest_behind` (sc. 31),
  `unplaced` without those removed by `retire_when` (sc. 34), `state_swept_total` (sc. 35), `garbled` without assignments (sc. 41)
  [of the lesson acceptance](../acceptance/README.md) (judge-only: checks P/04-R007, P/04-R008); the rest is checked by reading
- [ ] **P/04-18** [reading] the reason of a decision MUST be non-empty and SHOULD follow the grammar of N3 «choose» (`among` — the number of the eligible, `weight` —
  only with `placement.weight`) — checked by reading: the subject is the field `reason` of the placement row and of the answer `/where/<id>` for a placed unit; sc. 02-unit of the acceptance of P/03.3, step 6, reads the row `testsub/placement/c1` with `"reason": "@any"` — the presence of the field, not its non-emptiness or grammar; `/where/<id>` is not read there; the stand of the acceptance of P/06.6 (sc. 01–07) has no workers
- [ ] **P/04-19** [test, reading] the common admission of N1.5/N3: turn with cas/guard, a new look after the capture and between decisions; the reserve of the whole group by intent, the recovery before a new admission; the barrier after an unknown outcome, idle is kept for the readers; competition does not bypass capacity/spread_by/group — two controllers do not bypass the capacity — the seam `s17-admission-capacity` (`CALL controller-admit`); the removals before the addition and the recovery by a new holder — `s18-intent-removals-before-add`, the barrier after an unknown outcome — `s19-intent-unknown-barrier` (`CALL controller-complete-intent`); the limit of write conflicts — `s54-conflict-nine-then-success`, `s55-conflict-ten-stops` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R209, P/04-R027, P/04-R028, P/04-R029) (`CALL controller-pass`); the sequences over the turn row — the vectors [`turn`](../../common/vectors/turn/README.md) (judge-only: checks P/04-R209, P/04-R027, P/04-R028, P/04-R029); on the full stand: the recovery of an active intent and idle without deleting the row — sc. 28, an unreadable intent — a refusal without admission — sc. 30, an unreadable turn and progress after its repair — sc. 46; the rest is checked by reading and by the models of N5
- [ ] **P/04-20** [test] before the write of intent the full key `<sub>/placement/<id>` of each of the members is representable within the key limit of the store; otherwise there is no decision, the members are in `unplaceable` with `why`, the placement of the other units of the subsystem does not stop — the seam `s20-long-key-group-no-intent` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R028, P/04-R031) (`CALL controller-key-admission`: no write of intent or placement for the group, the group is not split, both members in `unplaceable`, an independent unit is placed); the stand of the acceptance of P/06.6 (sc. 01–07) has no workers
- [ ] **P/04-21** [test, reading] snapshot: shards per worker, the content of N1.3a, empty shards, `unplaced`, the mask, after the pass — sc. 03 [of the lesson acceptance](../acceptance/README.md) (judge-only: checks P/04-R011, P/04-R498, P/04-R064); the shard of a worker, an empty `unplaced` and an empty shard of a gone worker — sc. 40; an unreadable unit row outside the shard, the shard is published — sc. 08 (steps 1–6); a read error keeps the published data — the seam `s26-snapshot-error-keeps-data`, the byte ceiling and the store ceiling — `s27-snapshot-byte-boundary`, `s28-snapshot-over-boundary`, `s29-snapshot-store-ceiling` (`CALL controller-snapshot`); the counters of the same cycle — `s57-snapshot-state-garbled-same-cycle`, `s58-snapshot-rows-garbled-same-cycle`; the publications before the report: a read failure, `TooLarge`, a lost reply — `s61-publication-read-failure`, `s62-publication-store-too-large`, `s63-publication-reply-lost` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R011, P/04-R498, P/04-R064) (`CALL controller-pass`); the age and a spoiled shard in `/metrics` of the console — [chapter 6.5](../../06-console/spec/06.5-console.norms.md); the rest by reading
- [ ] **P/04-23** [test, reading] the schema check at the start of the controller (the schema row and the raise — [P/06.6](../../06-console/spec/06.6-console.norms.md) N1.1a): N3 «controller start — schema check» — no row — the own SCHEMA, not a number or above SCHEMA — do not start, code 2 before reading the manifest, a read error — wait — the outcomes of the check — the vectors [`schema`](../../common/vectors/schema/README.md); not a number and above SCHEMA, code 2 — sc. 23 [of the lesson acceptance](../acceptance/README.md) (judge-only: checks P/04-R060); a read error — wait — sc. 25; «before the manifest is read» — checked by reading
- [ ] **P/04-24** [test, reading] the deadline `ends`, `retire_when.state` and `retire_when.delete_after`, the delete of the row first without a tombstone and of the state after it, the sweep of the orphaned (step 8a), manual rows — `expired_kept`: `ends`, the sweep, `expired_kept` — sc. 18; `retire_when` by the acting state (a removal with the value as the reason, outside `unplaced`) — sc. 34; the count is cleared when the removal is cancelled — the seam `s22-retire-counter-reset` (`CALL controller-delete-after`); the sweep under the guard of the unit row, a refused sweep waits for the next pass — `s24-sweep-unit-guard` (`CALL controller-state-sweep`); a manual row after `ends` — `expired_kept` — `s38-growth-ended-manual-row` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R009, P/04-R025, P/04-R030) (`CALL controller-pass`); the acting state — the vectors [`row-check`](../../common/vectors/row-check/README.md) (judge-only: checks P/04-R009, P/04-R025, P/04-R030); the sweep of a state with a foreign `born` and `state_swept_total` — sc. 35; the count of `delete_after` from the removal on the full stand (600 s at `testsub2`, after a restart anew), a cancelled delete and a sweep cancelled by a row after the read — checked by reading: the stand does not hold the term and does not wedge in between the read and the delete
- [ ] **P/04-25** [test, reading] the replay protection on delete: a row with `made` — strictly after `made.keep`, with `not_before`; `409 early` — without a barrier and a journal — the seam `s25-made-delete-early` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R030) (`CALL controller-delete-after`); the delete in sc. 18 (`keep` in 2001); `keep` in the future — the row is not deleted, sc. 18 steps 15–19; the equality boundary — by reading (the stand does not move clocks)
- [ ] **P/04-26** [test, reading] the table snapshot of N1.3b: the stub `too_large` with empty rows — the seam `s30-table-too-large-stub`, an unchanged table is not rewritten, `ts` is kept — `s31-table-unchanged-no-rewrite` (`CALL controller-table-snapshot`); `snapshot_tables_refused` of the same cycle — `s59-snapshot-tables-refused-same-cycle` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R013, P/04-R062) (`CALL controller-pass`); the rest of N1.3b — by reading; the snapshot with `state` (N1.3a) — sc. 19; `snapshot_state_garbled` — sc. 18
- [ ] **P/04-27** [test, reading] `near`: `by`/`of`, `prefer` (AND, OR, path), the order by the id of the neighbour (N1.3) — the vectors [`near-of`](../vectors/near-of/README.md); the preference for the worker of the holder — by reading; the manifest `near.sub` is not in the catalogue — no affinity, `near_waiting` in the pass report, switching on from the pass at which it appeared — by reading: the stand sets the catalogue `testsub` + `testsub2` before the start, and the vocabulary of the «Stand» has no directive installing a manifest in the middle of a scenario
- [ ] **P/04-28** [reading] the exclusive place (N1.3 `affinity.exclusive`): the holder admits only the bound units, its capacity is outside the shortage count of the others; an order for the place — the server of the place, an empty `server_field` — without an order, `Sealed` by `place_error` of the live workers — `withheld`, no live ones — one ordinary order — the stand prepares neither an exclusive place nor a row of a place with a secret that does not open — by reading; scenarios of P/04 and P/03.2 — when the training subsystem gets such a place (a debt)

- [ ] **P/04-29** [test, reading] the decommission of a server by the controller (N3 «decommission_server(s)»): a resumable plan fixed at acceptance, release chunks within the store limits, the cleanup of contributions under the exact guard of the release index, the final mark `<sub>/decommissioned/<host>` as the last atomic step; a malformed progress plan — a step error without mutation; a valid final mark with a standing request — no new cleanup — chunks and limits — the seams `s39-decommission-62-slots`, `s40-decommission-63-slots`, `s41-decommission-65-contributions`; the resumption from the store and a new holder kept — `s42-decommission-restart-before-cleanup`, `s43-decommission-new-holder`; a refused or lost final batch — `s44-decommission-final-refusal`, `s45-decommission-final-reply-lost`; a malformed progress — `s48-decommission-bad-progress-duplicate-remaining-name`, `s49-decommission-bad-progress-cursor-past-chunk`, `s50-decommission-bad-progress-foreign-from-prefix`; a valid final mark — `s56-valid-final-no-cleanup` of [the lesson](../acceptance/seams.tsv) (judge-only: checks P/04-R054, P/04-R056) (`CALL controller-pass`); the family name `decommission-pending` is reserved: the ordinary loader of P/02.1 used by the controller refuses a manifest that declares it — `s46-loader-reserved-pending-rows`, `s47-loader-reserved-pending-table` (`CALL controller-pass`, `fixture=loader_reserved_name`; the refusal is that of the loader of P/02.1); the console side — [P/06.6](../../06-console/spec/06.6-console.norms.md) N3 «decommission_server(s) — the console side»

## System checklist

The items of the lesson that need the OS, a host or several lessons: they stand at no stage
of this lesson (`forms/stages.tsv`) and go to the system lesson. The ids are those of the readiness checklist; a part split off
a readiness item has a new id, and the item and its part name each other.

- [ ] **P/04-22** [stand] a server failure of N1.4a (`stays`, `lost`): the move by the tolerances of two silences without a common deadline, the archive stays, the buckets not re-mirrored are lost, nothing back, except `home` (N3 «pass()», step 7); the terms SLOT_TERM/(SLOT_TERM + LOST_AFTER) of N1.4a on a real failure (P/04-10) — the drill `05-power-pull` of [the system acceptance](../../common/acceptance/system/README.md); sc. 01 — `09-resource-door` of the acceptance of [P/05](../../05-resource/acceptance/README.md) (judge-only: checks P/04-R016, P/04-R065, P/04-R066), sc. 02 — `14-resource-silent` of the acceptance of [chapter 6.5](../../06-console/acceptance/5/README.md)
- [ ] **P/04-30** [stand] leaving `silent` (N3 «leaving»; P/04-13): only with `requires: resource` and a live worker whose server resource is silent, otherwise the fate of SLOT_TERM + LOST_AFTER — the heartbeat of a worker is read through the resource of its server, and the lesson stand does not hold a live worker with a silent resource; the term of the fate — the drill `05-power-pull` of [the system acceptance](../../common/acceptance/system/README.md)
- [ ] **P/04-31** [stand] the workers of an order on the host (P/04-14): systemd does not raise the instance of the unit by the order (code 2 of the process); a number above want that came up after the withdrawal by the deadline is stopped by the script on the host, want is not raised — the lesson stand raises a process by `@grow` at once or not at all (sc. 15 of [the lesson acceptance](../acceptance/README.md) (judge-only: checks P/04-R050, P/04-R052), a debt of the stand); the units of P/02.4 and the workers script on a host
- [ ] **P/04-32** [stand] the lifecycle of the controller process ([lifecycle.md](../lifecycle.md) «Signals and readiness»): `READY=1` after the schema check and the manifest read, `WATCHDOG=1` at the boundaries of completed decisions and of the progress of the pass, not from an independent timer; SIGTERM — an orderly exit, an unfinished intent is completed by the next holder of the turn; `Restart=always` except the code 2 by the unit of P/02.4 — systemd and the units of P/02.4 on a host; the restart after `@sigterm` on the lesson stand — P/04-02; the norms set no stop term
