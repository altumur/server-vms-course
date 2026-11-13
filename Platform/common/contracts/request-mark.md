# The request and its mark contract: the request row, the keys `requests`, the mark, the states, `kept`

This English text is the source; the Russian translation `ru/contracts/request-mark.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5) and addendum (11): a contract that several processes read
and write lies in `Platform/common/`; review of stage B 3–5, V1). The owner is chapter [P/06.4](../../06-console/spec/06.4-console.norms.md)
(the console): it creates the request row by the door and removes it by the reaper, keeps the accounting `asked` itself, and in
the mark it is a participant (the reaper writes `no_begun` `expired` and `unknown` by the index; P/06.4 N3 «file a request»,
«reaper»). Read and written by: the holder worker — the mark `begun` and the outcome, the cleanup of the mark after `kept`, the
filing of a row by `worker.requests` (chapter [P/03.6](../../03-worker/spec/03.6-worker.norms.md) N1.5, N3 «holder's look»,
«Execution and cleanup of the mark»); the heartbeat of the holder with `fetched` — chapter [P/03.4](../../03-worker/spec/03.4-worker.norms.md)
N1.1. Moved from P/06.4 (formerly M10/8) N1.5 (the blocks `<sub>/requests/<rid>`, `action`, `rid`, `manifest`, `mark` and the
paragraph on the vectors), N1.6 (the paragraph on the forms of the mark), N3 «States of an executed request and its mark»
(whole) and «Races» of the procedure «reaper» without a change of behaviour. The accounting of a person (`ledger`), `holds`,
the constants of the reaper, the doors of the console, the filing `POST /<sub>/requests` and the procedure of the reaper are in
the norms of the owner (P/06.4 N1.5, N2, N3); the constants of the holder — P/03.6 N1.5; the form of the keys `requests` in the
manifest and the refusals of their loading — [P/02.1](../../02-installer/spec/02.1-installer.norms.md) N1.4, N4. The form
of the rows — the families of the owner [`requests`](../../06-console/data/requests.schema.json) (`<sub>/requests/<rid>`) and
[`commands`](../../06-console/data/commands.schema.json) (`objects/<sub>/commands/<rid>`) with the tables of outcomes next to
them ([catalogue](../data/catalog.tsv)). A reference «P/0N[.K] NM» is a norm of a lesson or of a chapter of the module.

Normative keywords follow the [course canon](../NORMATIVE-TERMS.md).

## Form

The files the contract works by (layout audit, V-50–V-54, B-17; the Architect's decision of 2026-10-25):

- the request row `<sub>/requests/<rid>` — the family `requests`: `Platform/06-console/data/requests.schema.json`,
  `Platform/06-console/data/requests.outcomes.tsv`; the mark `objects/<sub>/commands/<rid>` — the family `commands`:
  `Platform/06-console/data/commands.schema.json`, `Platform/06-console/data/commands.outcomes.tsv`;
- a resource request `<sub>/requests/free-<server>-<volume>` — the family `free-ask`: `Platform/05-resource/data/free-ask.schema.json`,
  `Platform/05-resource/data/free-ask.outcomes.tsv`;
- the accounting of a person `<sub>/asked/<sha16(name)>` — the family `asked`: `Platform/06-console/data/asked.schema.json`, `Platform/06-console/data/asked.outcomes.tsv`;
- `fetched` of the holder's heartbeat — the family `heartbeats`: `Platform/03-worker/data/heartbeats.schema.json`,
  `Platform/03-worker/data/heartbeats.outcomes.tsv`;
- the keys `requests` of the manifest — `Platform/02-installer/spec/02.1-installer.schema.json` (the key `requests`);
- the door `POST /{sub}/requests` (the answer `queued`, `AnsweredMark`, 400 `RequestError`, 409) — `Platform/06-console/spec/06-console.api.openapi.yaml`.

## Request

```yaml
<sub>/requests/<rid>:                        # a row; create-once; the writer — the console (the door) or the worker (worker.requests);
                                             # free-<server>-<volume> is not this form: it is written and rewritten by the resource (free_ask, P/05 N1.4; ADR-0059),
                                             # without unit, digest and requests.schema
  unit:        <id>                          # MUST; absent in a resource request (ADR-0059, free_ask); a resource request is told apart by the family of the key
                                             # requests/free-<server>-<volume> (the catalogue, P/05 N1.4), not by the absence of unit (review of stage B 6–7, № 37)
  <body fields>: by requests.schema, as text: a string — as is, another value — canonical JSON (JCS, ADR-0072)
  valid_until: <seconds>                     # the time of the writer (`Platform/common/data/codec.tsv` row time; P/01.1 N0) (a sent one — truncated down to ms, a negative one — 0, P/06.4 N3 step 1);
                                             # when the manifest has valid_for or the client sent its own term; 0 and a past one are a term
                                             # that has already expired (expired), not «no term» (reconciliation of python and go M10/6–11, E52)
  digest:      <sha256 hex>                  # MUST in every executed request (not in a resource request): in one filed by the door — JCS of the client body after the schema without
                                             # the server fields (kind client); in one filed by the worker — JCS of the object of the body fields of the row as written (as text), without unit,
                                             # valid_until and stamps (kind worker); the worker computes it itself at the write (P/03.6 N1.5); repeats are compared by it;
                                             # for a target with requests.key — kind worker at both writers: the door and the worker give one rid name, a repeat is checked
                                             # by one formula — digest of kind worker plus an explicit check of unit; kind client — repeats of one client by
                                             # Idempotency-Key at a target without requests.key (vectors request-digest, the third rule; ADR-0091 addendum (23) item 1,
                                             # addendum (24) item 3, addendum (25) item 3)
  by, at, group, <about-field>:              # by requests.stamp; by — the person in one filed by the door, `<sub>/<unit>` of the filer in one filed
                                             # by the worker (P/03.6 N1.5; ADR-0091 item 7); the about field — the value of the addressee unit in both
  filed:       <worker instance>             # MUST in one filed by the worker (worker.requests) — who filed it; absent in one filed by the door
action:     the action of the request — the value of the string field action of the body (by requests.schema of the manifest); requests.elsewhere and
            rights.reach.requests ([the gate-and-pass contract](../gate-and-pass.md) «Rights by the body») name actions by these values; a body without the field action has no action
            (review of stage A 6–7, № 14: the current behaviour of the witnesses; a change of behaviour is a separate item of the commit of lesson 6);
            the field action of the mark (section «Mark») is the same value; for a body without action the mark has no field action (review
            of stage B 6–7, № 16)
rid:        non-empty, ≤ 200 bytes of UTF-8; without / \ " ' and the characters Cc, Zl, Zp (vector rid; review of stage B 6–7, № 35); not `.` and not `..` (a segment of the key of the mark, P/01.1 N1); does not begin with `free-`
            (this is the family of resource requests P/05 N1.4; the decision of the Architect of 2026-10-18, the data catalogue); by requests.key — the template {field}; otherwise at the door of the console —
            r-<sha16(Idempotency-Key)> (the header is mandatory, P/06.4 N2); at the worker (worker.requests, P/03.6 N1.5) without requests.key of the target — by the key
            of the filer <filer subsystem>.<key> in this grammar (the key — deterministically from the data of the filer; there is no dot in the names
            of subsystems and they do not begin with free- — the parsing is unambiguous, the door form r-<16 hex> does not arise) or a random one, without a dot, — only for a
            request whose repeat the filer does not need (ADR-0091 addendum (20) item 2, addendum (21) item 2, addendum (23) item 2, addendum (24) item 5)
            # a substitution of the template that gave a rid not by this grammar (the start free-, the length or a forbidden character in the value of a field)
            # is a definite 400 RequestError; detail names the field of the template whose substitution broke the rule: the start free- —
            # the field with which the rid begins; the length limit — the field at whose substitution the rid (left to right) exceeded
            # 200 bytes, in a literal after the field — this field; a character or the grammar — the first field in the order of the template with a violation;
            # a literal of the template cannot break it — the loader rejects such a template; at several violations — the field of the
            # earliest by byte offset in the rid (free-, «.», «..», empty — 0; a character — its offset; the length — the offset of byte
            # 201; a byte of a literal — to the field before it): free- in unit takes precedence over the length in to (vectors rid template.tsv; the
            # decision of the Architect of 2026-10-27); a repeat of the same input gives the same refusal: this is a declared narrowing of the domain of the unit id
            # for requests by a template
manifest:                                    # requests: (the form — `Platform/02-installer/spec/02.1-installer.schema.json`, the key requests)
  schema:      JSON Schema of the body
  valid_for:   seconds to the deadline; mandatory without free
  most_valid:  the ceiling of valid_for; mandatory with valid_for; ≥ valid_for
  per_person:  the limit of reserved/unanswered rid of one person (without a domain the person is operator, the gate-and-pass contract «The gate» open); requires ttl; a reservation after a refusal can
               conservatively take a place until a repeat or maintenance completes, but is not lost for an accepted request
  settle:      a finite number of seconds ≥0 before an answered row is removed; default 60; the local monotonic age of the first confirmation of the outcome by the rule below
  ttl:         the term of an ordinary row without valid_until, of an append without a holder (+ REAP_AFTER, section «States…») and of a resource row without an owner; mandatory with free and per_person; 0 — no limit.
               The age of a row is now − its at (stamp, wall clock), if at exists and reads; otherwise the local monotonic age of the first
               observation of this version of the row by the console; a restart begins it anew: an unknown age does not count as
               expired (journal of cammeta-go, lesson 8 № 6). For an append without fetched the ttl alone does not permit removing the row/a non-empty accounting: at an age ≥ ttl + REAP_AFTER it is closed by
               the reaper with the mark expired (section «States…»); ttl 0 or no key — the append has no term
  key:         the rid template (the form — `Platform/02-installer/spec/02.1-installer.schema.json` requests.key; P/02.1 N1.4): {field} only a string, {field:int} only a finite binary64 number |x|≤2^53−1 truncated toward zero; *_secret is forbidden as a source
  outcome:     mark (default) | fetched — how the holder reports the result (ADR-0054 addendum 2026-10-17); mark — the mark begun/of the outcome (the ordinary profile);
               fetched — an append: only the word fetched in the heartbeat, there is no mark, except the mark of the reaper: gone to an absent unit or expired by the term (section «States…»);
               fetched without key — a load refusal of P/02.1 N1.4
  stamp:       [by, at, group, about]       # about — the field about.field of the manifest (in testsub2 — of) with the value of the addressee unit (E56)
  journal:     the kind of the journal line; no key — request.asked (reconciliation of python and go M10/6–11, E58)
  elsewhere:   the actions (action) that another process executes (the reaper does not touch them)
  free:        accepts requests of a resource to free a place
```

The accounting of a person `ledger` (`<sub>/asked/<sha16(name)>`), the manifest section `holds` and the constants of the reaper (`CLEAR_EVERY`, `SWEEP_EVERY`,
`REAP_AFTER`) — [P/06.4 N1.5](../../06-console/spec/06.4-console.norms.md); the constants of the holder (`PERFORM_TIMEOUT`,
`PERFORM_GRACE`, `REQUESTS_HOLD`, `COMMANDS_PER_LOOK`) — [P/03.6 N1.5](../../03-worker/spec/03.6-worker.norms.md).

## Mark

```yaml
mark:       objects/<sub>/commands/<rid>      # the ordinary profile; an ADR-0054 append has no mark, except the mark of the reaper: gone (the unit is absent) or expired (the term ttl + REAP_AFTER). A row object, create-once
  begun:     {instance, slot, unit, of?, at, digest, valid_until?}        # before the call; digest — a copy of the element `digest` of the request row
             # (section «Request» above: kind client or worker — by the rule of digest), the same unit; repeats are compared by it, and after settle — by the same formula
             # (ADR-0091 addendum (24) item 3)
  answer:    + {outcome, action?, ended_at, error (≤ 200 — MUST in refused and unknown, absent in performed), reply?, late?: true}   # action — the value of the field action of the body
             # of the request (section «Request» `action`), not the name of a handler: for a body with action MUST at performed/refused after the call, at unknown
             # optional; for a body without action the mark has no such field (review of stage B 6–7, № 16)
             # the write of the holder that began — by the index of the mark read, conflict → reread and repeat only the write,
             # without repeating the action; late — by the mark whose index accepted the write (ADR-0054; W03-E06); closing a foreign begun — by the index, with ended_by
  no_begun:  {unit, digest, outcome: expired | refused | gone, ended_by: reaper | holder, ended_at, error (≤ 200 — MUST in refused)}   # a mark without begun (the term expired, a refusal before the call,
             # the addressee unit is absent — gone, only ended_by: reaper; ADR-0091 addendum (11) item 4; for an append expired — also only ended_by: reaper):
             # digest and unit are carried over from the request row — a repeat after the deletion of the row compares digest here too
  outcome:   performed | refused | unknown | expired | gone                # closed (ADR-0054; gone — ADR-0091 addendum (11) item 4)
  ended_by:  reaper | holder                                               # who closed a foreign or beginless request: reaper — expired/unknown from the reaper; holder — expired/refused before the call
             # (no_begun) and unknown with which another holder closed a foreign begun past its term; an answer from the one who began has no such field
  kept:      max(60, ttl) from the moment the holder saw that the request row no longer exists (its monotonic clock), and not
             earlier than valid_until, if there is one: the repeat guarantee outlives the request row (removed by settle) by no less than this
             term; without a confirmed final outcome the mark is not deleted. ttl 0 («no limit» for the row) or no key ttl
             — kept 60: max(60, ttl) is computed by the number, 0 here is not «no limit» (the decision of the Architect, review
             of stage B 6–7, № 5)
```

`unit` and `digest` of the mark `begun` are the same as in the request row (section «Request»): the comment of the block above speaks of
one filed by the door; in one filed by the worker `digest` is JCS of the body fields of the row without `unit`, `valid_until` and stamps (review of stage B 6–7, № 35).

`reply` is the answer of `perform` of the holder that began: in the row the text of a JSON object, the values are strings of up to 200 code points, truncated as `error` is, there are no values of secrets; for a refusal before the call (`no_begun`), `expired`, `gone` there is no field: there was no call. Without it the client of the mark sees only the constant word of the device (C06-MARK-REPLY-01).

The limit of `error` of the mark (`answer` and `no_begun`) is 200 Unicode code points, not bytes and not UTF-16 units (as `maxLength`
of OpenAPI). A longer text the writer truncates to 199 code points and appends «…» (U+2026) — 200 in all; a text within the limit
is written as is (review of stage B 6–7, № 31).

### Three forms of the mark

From P/06.4 N1.6 (the form `answered` of the console door is the content of the mark):

`answered` is the content of the mark row (section «Mark» above): string values, times included, error and
late="true"; the description `{queued:rid}` does not admit replacing rid with an object. A mark without a beginning
does not contain instance/slot/at/action/late; closing a foreign begun keeps its fields and adds
unknown/ended_by/ended_at/error. The answer of the one who began does not contain ended_by. These three forms
are distinguished in AnsweredMark; begun without an outcome is returned as queued, not answered.

## States of an executed request and its mark

The table applies to an ordinary request with unit that the holder executes through the mark.
Excluded from it are resource rows (the family of the key `free-*`), elsewhere actions and the ADR-0054 append (for the append — only the rows
«reaper, append, …»)
(a family of requests of a manifest with `requests.outcome: fetched`: the key from data, for example `<unit>-<from>-<to>`, the execution is idempotent by data).
A resource row — by the family of the key `requests/free-<server>-<volume>` (the catalogue; a row of this family without `unit` is its form, while a row
of the family `requests/<rid>` without `unit` is unreadable by the family `requests`, the reaper neither marks nor removes it); the class of the other rows is given by
the declared form/action of the manifest (`outcome`, `free`, `elsewhere`; the action — section «Request» `action`), not by the text of
rid alone (review of stage B 6–7, № 37).
A resource row without a live owner: the owner is the resource `<server>` from the key `requests/free-<server>-<volume>`; «without a live owner» is
only `resource_state` of this server = `silent` ([observation contract](observation.md) «Resource state»); `live`,
`unreachable`, `unknown` — do not remove; no answer of the store — leave it; at `silent` and an age of the row ≥ `ttl` (by the rule of
`ttl` of an ordinary row without a term, the manifest section above) — `delete` by `cas` of the version read, there is no mark (P/05 N1.4 `free_ask`;
the stage C guess C06-FREE-OWNER-33-01, the Architect's decision of 2026-10-25; vectors [`reap`](../../06-console/vectors/reap/README.md)
profile `resource`).
Append: the console removes the row by CAS after fetched and settle and frees its rid in asked
by CAS. The addressee unit of the append is confirmed absent (there is no row `<sub>/<rows>/<unit>` or it is a tombstone) —
the reaper writes the mark `gone` create-once (`no_begun`: `{unit, digest, outcome: gone, ended_by: reaper, ended_at}`).
The unit exists (a confirmed read), there is no mark, `fetched` is not confirmed, `ttl` is declared and not 0, the age of the row (the rule of
`ttl`, the manifest section above) ≥ `ttl` + `REAP_AFTER` — nobody serves such a request (the holder closes earlier):
the reaper writes the mark `expired` create-once (`no_begun`: `{unit, digest, outcome: expired, ended_by: reaper, ended_at}`).
An append has one mark of the reaper: `expired` is not written over `gone`, nor `gone` over `expired`. The start of `settle` is the first
confirmed read of this mark with the same `unit`/`digest` (local monotonic clock); an age ≥ `settle` — remove the row by
CAS and the rid from `asked` by CAS; an unknown read — leave it. A late `fetched` of the holder after the mark is harmless: the mark does not
change, the start of `settle` does not move — the request has one outcome, the first confirmed one; `fetched` confirmed earlier
excludes the mark `expired`. ADR-0130 Addendum (10), Q5 supersedes the Architect's 2026-10-31 decision that append marks accumulate forever. A still-needed `expired` mark MUST NOT be deleted: the rid of an append is data-derived, the door does not read the mark, and a repeat with the same rid is accepted (202); the old mark with the same `unit`/`digest` closes it through `settle`, not `ttl`. Thus elapsed time alone does not prove cleanup eligibility. Only a proof that mandatory replay and side-effect memory is no longer needed permits cleanup. Eligible records MUST be reclaimed resumably within a finite positive implementation-declared cleanup budget under qualified workload. Until eligibility is proved, retain them and apply finite admission/resource budgets with visible existing refusal/backpressure; never forget them to admit work. Without a mark of the reaper an append has no marks, and it is not removed by `ttl` alone (P/06.4 N3 reaper `gone`,
`expired`; ADR-0091 addendum (11) item 4; the stage C guess C06-GONE-FETCHED-33-01, the Architect's decision of 2026-10-25; the VMS request
«request lifetime», the Architect's decision of 2026-10-29; vectors [`reap`](../../06-console/vectors/reap/README.md)). The holder's side of the append is [chapter P/03.6](../../03-worker/spec/03.6-worker.norms.md) N3 «The ADR-0054 append».
The sign of an append is `requests.outcome: fetched` (ADR-0054 addendum 2026-10-17); the training consumer is the requests of `testsub2`
(the form and the handler — [P/03.6](../../03-worker/spec/03.6-worker.norms.md) N5). Except for these two marks the reaper neither marks such a row nor removes it by `ttl` alone; scenario 07 of the acceptance of chapter 3.6.
Resource rows and elsewhere stay with their owners; the reaper neither marks them nor
moves them into the protocol of an ordinary request. Elsewhere is closed/removed by its owner — in the ordinary profile; in the append profile a body with
`action` from `elsewhere` is an append: the holder reports fetched, the console removes the row after settle (P/03.6 N3; (the Architect's decision of 2026-10-20, review of stage B 6–7)).

For an ordinary request the confirmation of the outcome is a successful read of the terminal mark
with the same unit/digest. For an append — a confirmed fetched of the holder for its row: rid or SaidID(rid) in the field `fetched`
of the heartbeat `<sub>/heartbeats/*` of any worker of its manifest (section «fetched» below; a worker does not name foreign rid) or
a successful read of the mark of the reaper with the same unit/digest, whichever happens first.
From this first observation the console counts settle by the local monotonic clock;
at an age <settle the row is removed neither by clear nor by sweep. Equality permits
a CAS attempt, it does not promise an immediate deletion. A repeated observation and a late
replacement of unknown by performed do not move the start for the same row/unit/digest;
a new version of the row begins a new observation. After a restart or
a loss of the observation memory the age begins anew, ended_at/fetched do not serve
as foreign clocks. An unknown read does not allow deleting the row; before CAS
its current version and the ground for removal are confirmed. The accounting of an answered request can be freed
earlier than the deletion of the row: settle limits the row, not the per_person hold.
For the ordinary profile the existing mark is checked first, then the term/admission; the name rid does not determine the class of the row.
Each read gives a state only at the moment of the read: a conflict returns to the table.

| Participant / state | Condition | Action | Outcome |
|---|---|---|---|
| filing, a mark with an outcome | the same unit and digest | return the mark, do not create the row/accounting | 200 answered |
| filing, begun without an outcome | the same unit and digest | do not create a new request | 202 queued |
| filing, a reservation of the rid already exists, there is no mark | the accounting was read successfully | do not duplicate the reservation; continue without fail to the write/check of the row and the mark (steps 4–5) | the reservation alone does not give 202 |
| filing, foreign content | another unit or digest in the row/mark | change nothing foreign | 409 exists/spent |
| holder, a mark with an outcome | any outcome | do not call the action | skip |
| holder, its own begun | the action is already called by this instance | do not call again | wait for the result |
| another holder, begun | at + timeout + grace is not yet past | do not change | skip |
| another holder, begun | the waiting term is past | unknown by the index read | conflict → reread, do not overwrite the result |
| holder, there is no mark | the term expired / no admission | put_new expired/refused, without a call | conflict → reread |
| holder, there is no mark | there is admission, the term has not expired | put_new begun; only a confirmed success permits the call | begun → one call |
| the holder that began, begun/unknown | answer/timeout | write the full outcome by the index of the mark read (conflict — reread, repeat the write), keeping the begun fields | performed/refused/unknown; a late answer — late |
| reaper, there is no mark | the row is overdue by P/06.4 N3 | put_new expired | conflict → reread the mark |
| reaper, begun without an outcome | an abandoned request | unknown by the index | conflict → reread; do not overwrite the result |
| reaper, a mark with an outcome | any outcome, the age of the confirmation ≥settle | do not change the mark; the row can be removed by its CAS | the outcome is kept |
| clear of an ordinary request | the row and the mark with an outcome for the same unit/digest are confirmed; age ≥settle | delete this version of the row; the accounting — CAS | conflict → do not delete a new version |
| reaper, append, the unit is absent | a confirmed read: there is no unit row or it is a tombstone; there is no mark | put_new gone {unit, digest, ended_by: reaper} | conflict → reread the mark; an unknown read — leave it |
| reaper, append, the term expired | a confirmed read: the unit exists, there is no mark; fetched is not confirmed; ttl is declared and not 0; the age of the row ≥ ttl + REAP_AFTER | put_new expired {unit, digest, ended_by: reaper} | conflict → reread the mark; an unknown read — leave it |
| reaper, append, the mark gone or expired | a mark of the same unit/digest; the age of its confirmation ≥settle | remove the row by CAS, the rid from asked by CAS | conflict → do not delete a new version; < settle — do not remove |
| holder, cleanup of the mark | the request row no longer exists and kept has elapsed | delete by the index of the checked mark | conflict/unknown read → leave it |

The rows «holder …», «another holder …», «the holder that began …» and «holder, cleanup of the mark» are the side of [chapter P/03.6](../../03-worker/spec/03.6-worker.norms.md)
(N3 «holder's look», «Execution and cleanup of the mark»); they stand here because the table is one per request. The rows
«filing …» are the console door (P/06.4 N3 «file a request», the steps are there), «reaper …» and «clear …» are the procedure of the reaper (P/06.4 N3 «reaper»).

## fetched

Moved from [P/03.4](../../03-worker/spec/03.4-worker.norms.md) N1.1 `said_id` and P/03.6 «Implementation decides» item 1 (the limits)
without a change of behaviour: the name of a request in `fetched` of the heartbeat is written by the holder worker (P/03.6 N3 «holder's look»), read by the reaper
of the console (P/06.4 N3 «reaper» `clear`) (layout audit A-24, B-02, the Architect's decision of 2026-10-25). The field `fetched` of the heartbeat has the form of P/03.4 N1.1
(`Platform/03-worker/data/heartbeats.schema.json`, the outcomes `Platform/03-worker/data/heartbeats.outcomes.tsv`).

```yaml
fetched:     <SaidID(rid) separated by commas, without spaces> — the requests whose outcome the holder reported; no field or empty —
             nothing is reported
said_id:     # the name of a request in fetched (vectors common/vectors/said-id/README.md)
  plain:     rid as is, if it has no more than 40 Unicode characters (code points), it does not begin with «#», it has no «,», «"»,
             «\» and each character is printable — a letter, a mark, a digit, punctuation, a symbol (general categories L, M, N, P, S) or the space U+0020
  hashed:    otherwise «#» and the first 20 hex characters of sha256(UTF-8 rid), in lower case (review of stage B 6–7, № 46)
  read:      fetched — split by «,»; rid is reported if among the names there is rid or SaidID(rid)
limits:      FETCHED_COUNT, FETCHED_BYTES — the limit of the length of fetched in the heartbeat, MARK_SWEEP — the cleanup of marks: the values are named by
             the implementation of the worker in its description (P/03.6 «Implementation decides» item 1)
```

## Races of marks

From the «Races» of the procedure «reaper» of P/06.4 N3: two holders of one unit: `put_new` of the mark lets one through; the second holder closes a foreign `begun` past its term with the word `unknown` by the index — the one who began, having got a late answer, rereads the mark and writes the outcome by its index over it, `late: true`, as after the reaper too. The reaper against a holder that began in the last second: the mark `begun` already exists — the reaper writes `unknown` by the index, the holder, having got the answer, writes the outcome by the index of the mark read; conflict — reread and repeat only the write: the reaper and the second holder write once, so the repeat of the holder ends with its word over `unknown` — the holder wins (ADR-0054), `late: true` in the outcome after `unknown` (the stage C guess W03-E06, the Architect's decision of 2026-10-23); the reaper writes only by the index read and does not overwrite the word of the holder. A repeat of filing with the same rid: `cas ""` — the second one gets «exists»; unit/digest matched — queued without an outcome, answered with an outcome; foreign content — exists/spent.

## Production obligations

Destructive cleanup MUST obey the clock qualification and monotonic deadline rules of [the event journal](event-journal.md), Q6 of ADR-0130 Addendum (10). An uncertain wall-clock jump defers deletion; required security/replay state is retained under finite resource/admission budgets.

## Vectors

The grammar of `rid` — the vectors [`rid`](../../06-console/vectors/rid/README.md); the write of a body field into the row (`<body fields>`; `<body fields>` in the Russian text) — the vectors
[`requests-body`](../../06-console/vectors/requests-body/README.md); `digest` — the vectors [`request-digest`](../../06-console/vectors/request-digest/README.md);
the name `SaidID(rid)` in `fetched` of the heartbeat — section «fetched» `said_id` (the vectors
[`said-id`](../vectors/said-id/README.md), the owner is this contract); the reaper over an append request — the marks `gone` and `expired`, `settle`, without removal by `ttl` alone (the rows
«reaper, append, …» of the section «States…») and a resource row without a live owner (C06-FREE-OWNER-33-01) — the vectors [`reap`](../../06-console/vectors/reap/README.md) (C06-GONE-FETCHED-33-01);
the write of a sent term `valid_until` — the vectors [`deadline`](../vectors/deadline/README.md) (C47-DEADLINE-VECTORS-01).
The packages are at the owner (P/06.4); the other states and `kept` have no vectors — the acceptance steps of chapters 6.4 and 3.6 and reading.

The vectors `deadline`: the cell `input` of `cases.tsv` is the text of the value `valid_until` from the request body — one JSON value, as sent. The native output is one JSON object: `{"written": <text>}` — the element of the request row by the time writer of P/01.1 N0 (an integer — without a fractional part), `written` is a string; or `{"status": 400, "error": "bad deadline"}` — the value is not a finite JSON number (the refusal of step 1, P/06.4 N4 RequestError).

The canonical JSON (RFC 8785, ADR-0072) that the contract relies on — the package [`jcs`](../vectors/jcs/README.md)
of the common JCS contract (`canonical_json.tsv`: input → the RFC 8785 form → sha256; ADR-0083 addendum (33) item 2).

[Common finite budgets and acceptance limits](production-obligations.md) are required for the applicable phases of this contract.
