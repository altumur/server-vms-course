# The observation contract: freshness, resource state, reading the decision

This English text is the source; the Russian translation `ru/contracts/observation.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5): a contract that several processes read lies in
`Platform/common/`; the Architect's decision on the review of stage A 6–7, № 1, № 2). The owner is lesson
[P/04](../../04-controller/spec/04-controller.norms.md) (N1.4: the constant `LOST_AFTER` and the judge; the blocks are moved from there; review of stage B 6–7, № 35). Readers: the controller — the pool, the judge
of a slot, the decommissioning of a server ([P/04](../../04-controller/spec/04-controller.norms.md) N1.4, N3), the console — the outputs of observations
(chapter [P/06.5](../../06-console/spec/06.5-console.norms.md): `/servers`, `/resources`, `/where`, `/unplaceable`,
`/metrics`), the control doors (chapter [P/06.6](../../06-console/spec/06.6-console.norms.md): server decommissioning, `/schema`,
the schema raise, the drain, label forecasts), the live resources of the merge `/events` (chapter
[P/06.4](../../06-console/spec/06.4-console.norms.md)) and contender marks (`name_conflict` P/06.5; section «Freshness of a contender mark»). Moved from P/04 N1.4 (`resource_state`) and N1.5 (the reader
side of the decision) without a change of behaviour, except one: the freshness bound is one relation `≤` for all observers
(«Freshness» below; review of stage A 6–7, № 1). What an observer does with the state (the fate of a slot, the pool, a refusal of decommissioning,
`live` of a process in `/schema`, `state` of a worker in an output) is in the norms of the reading lessons; the form of the observed rows and objects is at
their owners ([catalogue](../data/catalog.tsv)).

Normative keywords follow the [course canon](../../../NORMATIVE-TERMS.md).

## Form

The observer reads the resource heartbeat `platform/resources/<s>/heartbeat` by the form and the outcomes of the family of its writer — the files
`Platform/05-resource/data/resource-heartbeat.schema.json` and `Platform/05-resource/data/resource-heartbeat.outcomes.tsv`
([form](../../05-resource/data/resource-heartbeat.schema.json), [outcomes](../../05-resource/data/resource-heartbeat.outcomes.tsv));
the door row `platform/doors/<s>` — by the change of its version, its form is `Platform/05-resource/data/doors.schema.json`, the outcomes are
`Platform/05-resource/data/doors.outcomes.tsv` ([form](../../05-resource/data/doors.schema.json)). The named data files are part of the reading of `common`
(ADR-0083 addendum (32) item 1; C04-DEP-OBS-HEARTBEAT-01). The outcomes are by `outcomes.tsv`: for a field not of its form that has
an outcome row of the field (`build`, `schema`, `retention_garbled`, `retention_withheld`) its outcome applies, the heartbeat stays
readable; only the outcome «the whole object» makes the heartbeat unreadable (a field outside the closed form included).

The other forms by which observers read (layout audit, V-38–V-40, B-16; the Architect's decision of 2026-10-25): the place hold row `<sub>/holds/<place>` —
`Platform/03-worker/data/holds.schema.json`, `Platform/03-worker/data/holds.outcomes.tsv`; the worker heartbeat `<sub>/heartbeats/<name>`
— `Platform/03-worker/data/heartbeats.schema.json`, `Platform/03-worker/data/heartbeats.outcomes.tsv`; the contender mark
`<sub>/contenders/<name>/<box>` — `Platform/03-worker/data/contenders.schema.json`,
`Platform/03-worker/data/contenders.outcomes.tsv`; the decision rows `<sub>/controller/placement_intent` and `<sub>/placement/<id>`
— `Platform/04-controller/data/placement-intent.schema.json`, `Platform/04-controller/data/placement-intent.outcomes.tsv`,
`Platform/04-controller/data/placement.schema.json`, `Platform/04-controller/data/placement.outcomes.tsv`. The version of an object
(section «Observation of a version» changed: the headers `X-Server`, `X-Written`, in the listing `server`, `written`) is the contract of the
resource door `Platform/05-resource/spec/05-resource.api.openapi.yaml` ([OpenAPI of lesson P/05](../../05-resource/spec/05-resource.api.openapi.yaml)).

## Observation of a version

```yaml
observer:  a reader process with its own observation memory and its own monotonic clock; the memory is not shared between
           observers and begins anew after a restart (ADR-0049)
changed:   «changed» — a change of the version of a row or object before the eyes of the observer (the index of a row P/01.1 N1, the version of an object
           P/05 N1.1), not the value of a time field in it (`ts`, `at`, `until`): the clock of the writer does not prove freshness;
           the version of an object is the pair (server, written) as the resource door gives it (the headers X-Server, X-Written; in the listing
           — server, written): written is a stamp of the resource at the write, strictly growing per key (P/05 N1.1 written), not
           a field of the body; the same pair — the same version, another — a new one, even with the same bytes (the stage C guess
           C06-OBJECT-VERSION-33-01, the decision of the Architect of 2026-10-23)
age:       the age of the observed version — the time by the clock of the observer since the moment it first successfully read the current
           version ([P/03.2 N1.4](../../../03-worker/spec/03.2-worker.norms.md) «age of the observed version»); a first
           look, a new version or changed bytes — age 0; a repeated read of the same state and no answer of the store
           do not reset the age
first:     the first observation is fresh: what is seen for the first time «has just changed» (age 0); therefore a new observer
           counts nobody as silent during the first LOST_AFTER (P/04 N1.4a `fresh_controller`)
lapse:     no answer of the store or a confirmed absence of a row (object) that was read before is not a new version: the age
           of the last read version and the fact of the former observation are neither erased nor reset; the same version came back —
           the age runs from its first read (the stage C guess OBS-001 (Go), the decision of the Architect of 2026-10-23);
           the judgement is by the last read version, also by one whose body does not read by its family (garbled): no answer after
           it keeps garbled and does not revive the rows of the former readable version; age and life — only by readable versions:
           an unreadable one does not reset the age and does not confirm life (`live`, `unknown` below), the age runs from the first read
           of the last readable version (C06-PULSE-LAPSE-GARBLED-01, the decision of the Specification, refined by c-go 2026-10-29);
           a confirmed absence is the answer «there is no row (object) now»: the outputs and judgements that need the row itself
           see the absence (the hold is not `active`, the heartbeat is not `live`, the body of the former version is not in the output; an output from memory —
           only at no answer); lapse keeps only the age and the fact of the former observation (`unknown`, the return of the same version);
           the former version stays a ground after an absence only where the contract says so directly (the door row in
           `unreachable`) (C06-LAPSE-ABSENT-01, the decision of the Specification)
```

## Freshness: `LOST_AFTER`

```yaml
LOST_AFTER:  45             # s; one freshness bound for all observers; the literal is here, the lessons refer to it (P/04 N1.4 —
                            # also the margin after SLOT_TERM at the judge; review of stage B 6–7, № 46; layout audit, the Architect's decision of 2026-10-25, A-01, B-01)
fresh:       a source is fresh (heard) — its version changed within the last LOST_AFTER: the age of the observed version ≤ LOST_AFTER;
             age > LOST_AFTER — not fresh (silent, stale). One relation for all observers and outputs
             (review of stage A 6–7, № 1)
```

The relation is one for all the places where a norm says «changed within the last LOST_AFTER», «heard», «live» by the heartbeat, a «fresh»
or a «stale» heartbeat: `resource_state` below; a live worker in an output of the console (`worker_state` of a row of `GET /{rows}`,
`WorkerRow.state` `/servers`); the live processes of `/schema` and of the schema raise, «heard» of the server decommissioning, the freshness of the heartbeat
of the drain (chapter 6.6); the series `w2c_resources_live` (chapter 6.5); the live resources of the merge `/events` (chapter 6.4); the neighbours of a mirror (P/05 N1.4 mirror, the same door row). The former notations
«`< 45 s`», «`< LOST_AFTER`» at the doors of the console are read by this contract; where an output gave `<`, this is a change of behaviour at
one step — an age of exactly LOST_AFTER: fresh. The bound is checked by the vector [`fresh-age`](../vectors/fresh-age/README.md):
the pure function «age → fresh» with the rows `LOST_AFTER − 1`, `= LOST_AFTER`, `+ 1` and fractional ones near the bound (review
of stage B 6–7, № 20: a vector instead of an acceptance step at the bound, which a stand without controlled clocks does not do).

## Hold of a place

Moved from P/03.2 N1.4 `places` (`HOLD_SKEW`) and P/03.7 (`domain_worker`) — they have references here; the judgement for a reader of a place
(the console, `/where/<table>/<place>` P/06.5 N3) is the same relation to the bound as for the one who takes the place (P/03.2 N3 «take_place»:
«stood unchanged for 45 + HOLD_SKEW») (the stage C guess C06-WHERE-PLACE-HOLD-33-01, the Architect's decision of 2026-10-25).

```yaml
HOLD_SKEW: 5          # s; the margin to LOST_AFTER of a place hold and of the slot of a worker on the domain (P/03.7)
active:    an effective hold of a place — the row <sub>/holds/<place> by the form (holds.schema.json, section «Form»), released ≠ true, holder non-empty,
           the age of its observed version on the monotonic clock of the observer < LOST_AFTER + HOLD_SKEW (at 50 — already free),
           and the heartbeat of the worker by is fresh (≤ LOST_AFTER, section «Freshness») and names the instance holder (the field instance); the first
           observation — age 0 (section «Observation of a version» first); otherwise the hold is not effective
unknown:   the hold row exists but does not read (an outcome of the family holds), or the heartbeat of the worker by does not read — the hold is not known:
           it is counted neither effective nor released; the console — /where/<table>/<place> 503 unavailable, held_by null, the series unheld
           does not count the place free (V7 item 3, the decision of the Architect of 2026-10-28, P1; row 27; the class of row 23 of the list);
           the heartbeat decides only when the row itself is effective: the row is readable and already not active by itself (released, holder empty,
           age ≥ 50 s) — the hold is not effective, the heartbeat is not read and its unreadability does not make the hold unknown
           (C06-UNHELD-PULSE-UNREAD-01)
```

## Resource state (`resource_state`)

The resource of a server has one definition for all observers (the controller, the console), by their monotonic clocks; «changed» is a change
of the version before the eyes of the observer (section «Observation of a version»), the first look is fresh; the rules go in order, the first
that matches applies (reconciliation of python and go 2026-10-18).

```yaml
resource_state:
  live:         the resource heartbeat platform/resources/<s>/heartbeat reads and changed within the last LOST_AFTER; an unreadable
                heartbeat does not confirm life, nor does its change; the last read of the heartbeat being no answer or a confirmed
                absence does not give live (lapse; OBS-001)
  unreachable:  the heartbeat is not live (an unreadable one included), the door row platform/doors/<s> changed within the last LOST_AFTER —
                the resource exists, there are no heartbeats; a door row read before stays, at no answer or a confirmed absence,
                a ground up to the same bound — the age of its last version ≤ LOST_AFTER, there is no new count
                (lapse; OBS-001)
  unknown:      the observer has never seen either a readable heartbeat or the door row: an unreadable heartbeat does not count
                as seen (reconciliation of python and go M10/6–11, C13); what was read before and disappeared is seen (lapse)
  silent:       otherwise; only silent excludes and moves
ALIVE_EVERY:    15           # s; the resource rewrites at of its door row platform/doors/<s> (P/05 N1.4 door_row) — so
                             # the door row changes even with a silent heartbeat (moved from P/04 N1.4; layout audit, the Architect's decision of 2026-10-25, A-10)
```

An unreadable heartbeat is judged by the form of its writer (section «Form» above; [P/05 N1.4](../../05-resource/spec/05-resource.norms.md)); the door row
the observer judges by the change of its version, not by its fields (the family `doors` P/05). What each state means for the fate of a slot and
for the pool — [P/04 N3](../../04-controller/spec/04-controller.norms.md) «fate», «choose»; for the output `ServerRow.resource` —
chapter 6.5; for a refusal of server decommissioning — chapter 6.6. The state by the history of observation — the vectors
[`resource-state`](../vectors/resource-state/README.md).

## Server decommissioned

Moved from [P/03.2](../../03-worker/spec/03.2-worker.norms.md) N3 «start()» step 3 and P/04 N3 «decommission_server» «Races»
(layout audit, the Architect's decision of 2026-10-25, A-18); the rows of the request and of the mark — [P/06.6](../../06-console/spec/06.6-console.norms.md) N1.1 and P/04 N3 «decommission_server».

```yaml
decommissioned: the server <s> is decommissioned — there is the request row platform/decommission/<s> (written by the console; the form —
                Platform/06-console/data/decommission.schema.json) (the outcomes — `Platform/06-console/data/decommission.outcomes.tsv`) or the mark of the controller <sub>/decommissioned/<s> (the form —
                Platform/04-controller/data/decommissioned.schema.json) (the outcomes — `Platform/04-controller/data/decommissioned.outcomes.tsv`) — either of them is readable and exists; so the worker judges at start
                (P/03.2 N3 «start()» step 3) and the pool (the pool contract); an unreadable row — by the reader: the pool — not a fact, do not subtract;
                a tombstone — the listing is not confirmed, there is no deletion (the answer of the Architect of 2026-10-25)
narrower:      readers whose norm takes only the request row judge by it: the resource does not write its door row while there stands
                platform/decommission/<own server> (P/05 N1.4 door_row); the neighbours of a tombstone — by the confirmed listing
                platform/decommission/ (the tombstone contract «Neighbours»)
```

## Freshness of a domain member

Moved from [P/08.1](../../08-domain/spec/08.1-domain.norms.md) N1.3 `member_state` without a change (layout audit, the Architect's decision of 2026-10-25, A-15); readers —
the process `domain` (the view, P/08.1) and the domain console (P/10 N3 `alarms`: `silent` by the last report and `silent_after`).

```yaml
silent_after:   LOST_AFTER; for class camera — 3 × max(every of the mark, the stated retry_in) (P/08.3 N1.1a): an input of the command view; the domain console does not know retry_in, it has 3 × every of the mark
member_state:                                    # by the monotonic clock of the holder, «change» — a change of the bytes of the mark `reported`
                                                 # (P/08.3 N1.3): a new rev or a refresh of the same rev (received_at)
  ok:        this holder process has seen a change of the mark, the last one within silent_after
  unseen:    the mark exists, but this holder process has not yet seen a change and no more than silent_after has passed since the first look;
             a live member moves to ok no later than LOST_AFTER/2 (the mark is refreshed no less often, P/08.3 N1.3)
  silent:    there was a change and it did not repeat for longer than silent_after, or there is no change for longer than silent_after since the first look; or a mark
             that this process saw disappeared — at once silent with the former copy (its units — silent), the age — since
             the last seen change; a mark that came back — as any: bytes different from the last seen ones — a change
  never:     the member is accepted, this process has never seen a mark (one that disappeared after being seen — silent, not never)
  leave:     the member left the list (P/08.3 N2 DELETE) — the process forgets its memory (the mark, the copy, the first look, the heartbeats);
             one that came back — a first look anew (unseen)
  # disappearance, never and leaving — added by the reconciliation of M11 (V1–V3)
```

## Reading the decision: intent → placement → intent

The effective placement of a unit is read by the controller rows `<sub>/controller/placement_intent` and `<sub>/placement/<id>`
(the form — the families `placement-intent`, `placement`: `Platform/04-controller/data/placement-intent.schema.json`,
`Platform/04-controller/data/placement.schema.json` and their `.outcomes.tsv`, section «Form»; the writer side — [P/04](../../04-controller/spec/04-controller.norms.md) N1.5).
The rule is one for all readers: the controller, `/where`, `/unplaceable`, label forecasts, the drain.

```
read intent → the needed placement → intent again; the version of intent changed → repeat the read;
only equal versions of intent give a result
the needed placement at active — all placement rows that the reader requested for the answer are read between the two
  reads of intent; a confirmed absence of a row is admissible; an unconfirmed read or an unreadable row —
  the outcome unavailable (the stage C guess OBS-002, the decision of the Architect of 2026-10-23)
active intent and id in members → target/reason/at/manifest_rev of intent decide; an absence of placement does not cancel the target of an active
  intent; otherwise — worker/reason of the placement row
a mandatory read is not confirmed → there is no result (at the doors of the console — 503 unavailable); an unconfirmed read does not
  mean idle
an intent row not by the form (state not active/idle; an active one has no members, target, reason, at or they are not by the form) —
  unreadable: readers — 503 unavailable, not idle; the controller — a refusal with failures (P/04 N1.5, N4)
```

One HTTP read does not promise an atomic snapshot of the whole subsystem: the effective placement and the heartbeat of the holder are read
separately, the answer names the observed holder. Idle is kept by the writer so that the version of intent does not return to the version
of absence between two reads (the writer side — P/04 N1.5).

## Freshness of a contender mark: `CONTENDER_FRESH`

Moved from P/03.2 N1.2, N1.4a (they have a reference here); `CONTEND_EVERY` — how often the writer rewrites its mark —
stays at the writer (P/03.2 N1.2). The reader is the console: `WorkerRow.name_conflict` `/servers`, the series `name_conflicts`
([P/06.5](../../06-console/spec/06.5-console.norms.md) N2, N3) (C06-CONTENDER-FRESH-33-01, the Architect's decision of 2026-10-25).

```yaml
CONTENDER_FRESH: 300   # s; the freshness bound of a contender mark
contender: a contender mark <sub>/contenders/<name>/<box> (contenders.schema.json, section «Form») is fresh — the age of its observed version
           (section «Observation of a version» age) on the monotonic clock of the reader ≤ CONTENDER_FRESH; the first look — age 0
           (first); the field at is a display, not an input of the judgement (changed: the clock of the writer does not prove freshness); older than
           CONTENDER_FRESH — do not count it, as if there were no mark; an unreadable one (not by the form contenders.schema.json) —
           the freshness is the same, by the age of its observed version, whether it reads or not (for contender marks — unlike heartbeats,
           `lapse` above: unreadability does not hide a conflict); a fresh unreadable one — a conflict with a flag at the console reader; the worker does not count an unreadable one — the outcomes by reader in contenders.outcomes.tsv (C03-CONTENDER-UNREADABLE-01) (P/06.5 N3
           «Contenders», `name_conflict_unreadable`; V7 item 3, the decision of the Architect of 2026-10-28; C06-CONTENDER-UNREADABLE-01)
```

## Vectors

The packages [`fresh-age`](../vectors/fresh-age/README.md) (the freshness bound: age → fresh), [`hold-state`](../vectors/hold-state/README.md) (an effective hold of a place; C06-WHERE-PLACE-HOLD-33-01), [`resource-state`](../vectors/resource-state/README.md) (the resource state by the history of observation) and [`heartbeat-read`](../vectors/heartbeat-read/README.md) (reading a heartbeat by the form and the outcomes: for a resource — correct and incorrect `retention_*`, the outcome of a field and of the whole object, C04-DEP-OBS-HEARTBEAT-01; for a worker — `worker.tsv`: the whole object, an element of `status[]` by readers, `worker` ≠ the name of the key, the outcomes of fields, C08-HEARTBEAT-READER-99-VECTORS), [`contender-fresh`](../vectors/contender-fresh/README.md) (the freshness bound of a contender mark: age → fresh; C06-CONTENDER-FRESH-33-01). (ADR-0083 addendum (32) item 2)

