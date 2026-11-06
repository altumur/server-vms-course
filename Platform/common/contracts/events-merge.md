# The event journal merge contract: live resources, the merge, epochs, completeness

This English text is the source; the Russian translation `ru/contracts/events-merge.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13): a common algorithm of several processes is a contract, not copies in
chapters). The owner is lesson P/06, [chapter 6.4](../../06-console/spec/06.4-console.norms.md) N1.3, N3 «merge» (moved here without
a change of the console's behaviour, ADR-0091 addendum (21) item 1). The participants are the cluster console (the door `GET /events`, P/06.4 N2) and a subsystem
worker that merges the journal itself: it reads `GET /events` of the resources ([P/05](../../05-resource/spec/05-resource.norms.md) N1.3,
admission — the section «The participant» `admission`) and the epoch rows of the subsystems declared in `worker.reads` (`<sub>/epoch/`;
[P/02.5](../../02-installer/spec/02.5-installer.norms.md) N1.4); the console door is not opened to the worker, its TLS, `open`/`shut` and
limits do not change (ADR-0091 addendum (21) item 1, addendum (23) items 3–5, addendum (24) item 4, addendum (25) item 4, addendum (27) item 2). The index is
P/05 N1.3; the form of the row and of the answer — the section «Form», the query and the cut `cut` — «The resource query and answer» below; the hint `/events/wait` is at the resources (P/05 N1.6), the console has none.

Normative keywords follow the [course canon](../../../NORMATIVE-TERMS.md).

## Form

The event row and the answer of a resource to `GET /events` — the schemas `EventRow`, `ResourceEventRow`, `ResourceEvents` of the contract
`Platform/05-resource/spec/05-resource.api.openapi.yaml` ([OpenAPI of lesson P/05](../../05-resource/spec/05-resource.api.openapi.yaml));
the console's answer — `ConsoleEvents` and `ConsoleEventRow` of the contract `Platform/06-console/spec/06-console.api.openapi.yaml`
([OpenAPI of lesson P/06](../../06-console/spec/06-console.api.openapi.yaml)). Both files are in the reading of `common` (ADR-0083
addendum (33) item 1; EM-READ-33-01). The epoch rows `<sub>/epoch/<id>` — the family `epoch`: `Platform/03-worker/data/epoch.schema.json`,
`Platform/03-worker/data/epoch.outcomes.tsv`; the door rows `platform/doors/<s>` (the section «Live resources») — the family `doors`:
`Platform/05-resource/data/doors.schema.json`, `Platform/05-resource/data/doors.outcomes.tsv` (layout audit, V-18, V-19, B-18;
the Architect's decision of 2026-10-25).

## The resource query and answer

Moved from P/05 N1.3 (`query`, `cut`, `answer` and the paragraphs about `by`, copies, `truncated`, `partial`) without a change of behaviour: the resource
executes them at itself, the merger — over the answers (EM-READ-33-01). The grammar of the query parameters and their refusals — the resource door,
P/05 N1.3 (below this block) and N2; at the console door `from`, `to`, `limit` — the reader grammar of
[the gate-and-pass contract](gate-and-pass.md) «Numeric query parameters» (C06-EVENTS-QUERY-LEXEME-162-01, the Architect's decision of 2026-10-27).

```yaml
query:       from, to (seconds; default 0..1e12; the window from ≤ t < to, C05-QUERY-TO-OPEN-01), kind, subsystem, unit (<sub>/<id>; a bare id — a refusal), limit (1000; ceiling
             10000), keep (newest | oldest; default newest), class (none — both classes), by (t | occurred; default t), late (only with by=occurred; an integer ≥ 0; default 3600);
             limit bounds both each resource and the merger's result; the merger asks the resources with the same
             query
by:          by=occurred — a row without occurred uses t both in the filter and in the sort; buckets are read by t up to to + late: t is the writer's clock, a row about the past lies in the bucket of its write, late — how far the write could lag behind occurred; a row written later than to + late is not visible to the query (C05-QUERY-LATE-01, the Architect's decision of 2026-11-01, analysis of the VMS pass, question 8)
cut:         before the cut remove duplicates by id; first alarm, then observation; within a class by by (newest — descending, oldest —
             ascending), at an equal time id lexicographically by UTF-8 bytes; the first limit rows
from_mirror: the resource reads the copies .mirror/<server>/ together with its own tree: the same bucket — a duplicate, it answers under the owner's name
             (the field server of the row is the owner, except a line with its own field server — P/05 N1.3 `row`); at the merger the bucket copies of a silent resource in the answers of others give state «; <s> from
             mirror» (the section «The merge» step 2)
truncated:   at a resource — matching whole rows unique by id that did not fit into its local limit (the number of candidates after
             deduplication minus the number given out); at the merger — the sum of truncated of those who answered plus the candidates that did not fit into the common
             limit after deduplication; copies skipped by different sources can be counted several times — this is a counter
             of skips at the stages, not the number of different lost events and not the number of skips at silent sources;
             there is no additional reading of hidden rows for an exact count
partial:     partial: true — at least one bucket was read with a torn last line (it is not given out and is not counted
             in truncated); the merger carries partial over from a resource that answered, if true
answer:      the resource — {events, state, truncated, partial?, lines_garbled?}, state at a resource is always live; the merger — the section «The answer»
```

## The participant

```yaml
participant:  the console — reads the epoch rows <sub>/epoch/* of all subsystems of the catalogue (the rights of the console, P/02.5 N1.4);
              the worker <s>worker — the epoch rows of the subsystems declared in its worker.reads (<sub>/epoch/), and only them
epochs_age:   the participant MAY keep the epoch rows read with an age by the observation contract and not reread them on every
              poll — for selection; a row that it gives out as a proof of fencing (epoch_is: fenced) it checks against a
              fresh read of the epoch (ADR-0091 addendum (23) item 4, addendum (24) item 4)
policy:       older_epochs of the subsystem manifest (P/06.4 N1.2): fenced | earlier-run, default fenced
admission:    the resource door /events* admits the roles console, resource and <sub>worker of the manifests of the catalogue; a resource with TLS checks
              the client: the chain up to the authority, the serial is not in revoked (the role certificate contract revoke), exactly one role from the row
              of the route, CN = <role>.<SAN DNS>; otherwise a handshake refusal or 403 ResourceDenied with the role and the route; the client
              checks the role resource and the SAN DNS of the server against the host of the address; an IP with TLS — a refusal by the client (moved from P/05 N2
              «Admission to the resource doors» for the participant; layout audit, the Architect's decision of 2026-10-25, B-18)
```

## Live resources

Live resources are the door rows `platform/doors/<s>` whose version changed within the last `LOST_AFTER` by the participant's clock
([the observation contract](observation.md) `fresh`; the first look — as fresh); the merge does not read the resource heartbeat: the liveness of a resource
here is only by the door row (analysis of review of stage B 6–7, № 35). The boundary is one, `≤ LOST_AFTER` — the vector
[`fresh-age`](../vectors/fresh-age/README.md). A resource with a stale door row (`silent`) is not asked. By the same row a resource judges the liveness
of its mirror neighbours ([P/05](../../05-resource/spec/05-resource.norms.md) N1.4 `mirror`).

## The merge

```
1. ask the live resources in parallel (8 lanes, 3 s) with the same query (`query` above); at the console with a visibility filter (the grant
   of the caller is narrower than view on *, step 5a) — with limit = the ceiling 10000, the common limit — after the filter (C06-EVENTS-VIEW-33-01)
2. did not answer → incomplete[<server>] = did not answer; said not live → said <state>; a stale door row → silent;
   for each of them state gets «; <s> unreachable»; bucket copies of a silent resource in the answers of other resources
   are given out, and then state also gets «; <s> from mirror» (reconciliation of python and go M10/6–11, E23)
3. a row of a resource answer not in the form EventRow → skip it, count it in lines_garbled of the merger (P/05 N1.3; E24);
   lines_garbled of the answer — the sum of lines_garbled of those who answered plus the skips of step 3; partial: true if true at one who answered
4. duplicates by id → one
5. epochs (the section «Epochs» below): epoch_is and fenced at each row
5a. the visibility filter — only the console (the worker merges its own without a filter): a row is seen by a caller whose grant view covers its
   unit or the unit of (scope of the gate contract: unit:<sub>/<id>; labels: — by the labels of the unit of, if there is of, otherwise unit);
   the labels of a unit — the field labels of its row <sub>/<unit.rows of the manifest>/<id> ([the row check contract](../row-check.md) «the unit row»), declared in unit.fields as a list (the same field as
   the input unit.labels of the function may and the placement labels); the field is not declared or the row does not have it — no labels ([]); the unit row
   is unreadable or its read is not confirmed — the labels are unknown: the rows of this unit are seen by a grant on the unit itself (or on of) and
   on *, a grant by labels — not; this is not a 503 of the door — one unit does not bring down the output; to a caller with a grant view by labels such
   units whose rows among the candidates are therefore hidden — in withheld of the answer (without repeats, ascending by bytes; none — no
   field); with a grant on the unit and on * there is no withheld (C06-EVENTS-LABEL-SOURCE-138-07, the Architect's decision of 2026-10-26);
   a row without a subsystem unit and without of (the journal audit, a console label without of) — only view on *; an invisible row drops out
   before the cut; the filter changes neither complete nor incomplete; «the first visible» — within the window of the resource ceiling: fewer visible than limit and
   truncated > 0 — there can be more (the counter, as below), complete does not change by this; with view on * there is no filter, the query is the same
   (C06-EVENTS-VIEW-33-01, the Architect's decision of 2026-10-25)
6. order by `cut` above; keep the first limit (at the console — of the visible ones);
   truncated = the sum of truncated of the resources that answered + the number of candidates (at the console — visible) that did not fit into the common limit;
   deduplication, epoch marking and the visibility filter do not enter this counter
7. with unit: a query without fencing, then marking by epochs — a row of a former epoch is given out with fenced: true, not thrown away
   (reconciliation of python and go M10/6–11, E21)
```

**Races.** Sources and epochs can change between reads: there is no common snapshot. The count refers to the observed answers:
a local cut can hide copies and rows that are later cut off by epoch; the result does not promise a global top-k of all
files. A resource that answered after the timeout is marked in `incomplete` of this answer and can answer the next one; a late answer is not
appended to what was already given out.

## Epochs

```yaml
epoch_is:     current | fenced | earlier-run | unknown       # set by the merger — the console or the worker; a resource has no rows with it
read:         the epoch of the row's subsystem is read: the epoch of the row < current_epochs[unit] → the policy (fenced | earlier-run),
              otherwise current; no epoch row of the unit — current; fenced: true if and only if epoch_is: fenced
unknown:      only at the worker and only for a subsystem whose epoch rows it did not declare in worker.reads: epoch_is: unknown,
              fenced: false — not a proof; complete does not change by this (ADR-0091 addendum (24) item 4, addendum (27) item 2)
failed:       a needed epoch (of a subsystem whose rows came in the answers) is not read — the store did not answer or the row does not
              read: incomplete[<sub>/epoch] = did not answer, the rows of this subsystem — without the field epoch_is, fenced: false
              (not a proof); the rule is one at the console and at the worker; the console never has unknown — it reads all epochs
              (ADR-0091 addendum (25) item 4, addendum (27) item 2)
```

## The answer

`{events, state, truncated, partial?, lines_garbled?, complete, incomplete, withheld?}`: `withheld` — only at the console (step 5a); `events` — the rows of P/05 N1.3 with `epoch_is` (except
`failed`) and `fenced`; `state` — `live[; <s> unreachable][; <s> from mirror]`; `incomplete` — `{<server> | <sub>/epoch: did not
answer | silent | said <state>}`; `complete` — `incomplete` is empty: this is the completeness of the sources that answered and of the epochs read, not
the absence of a cut by `limit`. At the console this is the body of `GET /events` (the schema `ConsoleEvents` of the OpenAPI of lesson 6); at the worker — its
own result of the same form, the worker's `complete` coincides with the console's at the same answers and epochs.

## Vectors

The package [`events-merge`](../vectors/events-merge/README.md): the merge function without a stand — duplicates, the order `cut`, `truncated`,
`fenced`/`earlier-run`/`current`, no answer, `silent`, `said`, an epoch not read, a worker with a declared, an undeclared and an unread
epoch, `partial`, `lines_garbled` (ADR-0091 addendum (21) item 3); the visibility filter of the console — a grant by labels and
an unreadable unit (`withheld`), a grant on the unit and on `*`, labels by `of`, labels `[]` (C06-EVENTS-LABEL-SOURCE-138-07). The liveness of a door row — the package [`fresh-age`](../vectors/fresh-age/README.md) (the boundary `LOST_AFTER`, the section «Live resources»);
`from mirror`, races and late answers — by reading.

## Correspondence to former lessons

From P/06.4 N1.3 `merge` and N3 «merge (the console)» (formerly M10/8): the algorithm and the paragraph about the freshness of the door row — whole; P/06.4 has
a reference here. New: the worker participant, `unknown`, a failure of reading an epoch (ADR-0091 addendum (20)–(27)).
