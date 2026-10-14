# C6 runtime cutover checklist

The component checkpoint is not the runtime cutover. The old issuer and readers
remain active until all callers below can switch together in this branch.

1. Ordinary AutoWorker: verified shared settings, local trigger ownership,
   one active evaluator, local merged events, refused map under heartbeat.asks,
   contribution publication after its heartbeat through the slot guard.
2. Camera cluster: same executor in process; direct agent call as autoworker,
   no auto unit and no road publisher. Its worker pulse carries executor stats.
3. Relay Forwarder: read auto/asks observations and request an ephemeral ask
   token as recworker for the original target/by pair. Preserve lift, carried
   answers, request deadlines and bounded unknown outcomes.
4. Ingest: signed ask audience is the approved cluster list; authorize the
   complete raw then object. Remove the former audience/action interpretation.
5. Spec/runtime switch: auto books.asks and mandatory scenario.name; cam token
   scenario placement:rec, grant autoworker/recworker; remove cam books.asks and
   old asks/worker keys per 0239252b. Remove domainpart ask issuance and its
   SIGNER_TOKENS_UNIX dependency. No aliases or dual readers.
6. C6b remains separate: the upstream publisher's unassigned-source fallback.
   Other domainpart code and the eventual page switch belong to C7.

## Existing acceptance assertions to preserve and transfer

These existing DomainVMS tests must exercise the real new runtime path. Passing
them before cutover only proves that the old path still works; it does not prove
C6 acceptance. Do not replace these tests with component doubles.

| Existing coverage | Transfer to new path |
|---|---|
| lesson16: scenario between two unreachable cameras | verified named shared scenario; embedded trigger executor; role token |
| lesson16: one recorded and one unrecorded target | auto input at each path node; source/poll home for unassigned target |
| lesson16: removed scenario and stable books | no published row after removal; no tokens in collected books |
| lesson16: allowed actions, rate and live ask deduplication | raw then equality; same deadline/MaxLiveAsks behavior |
| lesson16: event summary and event-relative deadline | shared Executor ignores summaries and never restarts an expired deadline |
| lesson16: rebooted ingest and absent outcome | existing bounded unknown answer after grace |
| lesson16: server cluster camera as trigger | ordinary autoworker owns local merged-event execution |
| lesson17: cross-relay and intra-relay asks | target/by token per role; relay/centre/home audience cases |
| lesson17: upward ask expires and is not kept | lift and carried outcome unchanged; no persistent token |
| lesson17: by-event whole road | worker and embedded host invoke the same executor |
| lesson17: torn ask books | refuse unconfirmed generation before requesting authority or dialing |
| camera_office_centre stand.scenarios | use host executor and agent role door; remove direct old Asker/Scenarios construction |

Final C6 review includes a per-test outcome, common testsub2 diff, full frozen
Python/JS unit, Cluster, Domain and DomainVMS evidence, and the remaining debts.
