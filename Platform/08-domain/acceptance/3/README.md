# Acceptance P/08.3 — admission of reports

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../../common/acceptance/README.md), the section [«Domain stand»](../../../../common/acceptance/README.md#стенд-домена)
(the dictionary of directives and doors of the stand of several clusters; before its move — the «Словарь директив и дверей М11» of the README
of the acceptance of М11/01). The norm of the chapter is
[`08.3-domain.norms.md`](../../../spec/08.3-domain.norms.md) Н5. The scenarios were moved (stage B, ADR-0083 addendum (1): without
a change of behaviour) from the acceptances of М11/03 (01, 02, 03, 05, 14), М11/04 (01 → 15, 05 → 16), М11/08 (04) and М11/12 (02 → 17);
the numbers, the names and the steps are the former ones, except `15-topology` (in М11/04 — `01-topology`), `16-second-road` (in М11/04 —
`05-second-road`) and `17-members-only-to-the-lagging` (in М11/12 — `02-members-only-to-the-lagging`): their numbers are taken by
scenarios of М11/03 (the rule — the plan of the move of lesson 8, § 3; the Architect's decision 2026-10-20, item 14). In total 21 scenarios /
218 steps: 14 — sc. 29 `29-batch-admission` (the admission batch, ADR-0113; the roadmap 4.5), 63 from М11/03, 21 from М11/04, 18 from М11/08, 10 from М11/12, 8 — sc. 28, 3 — sc. 18 `18-relay-not-member` (C08-G06),
5 — sc. 19 `19-members-source` (a door of lesson P/10, C10-MEMBERS-SCENARIO-01), 20 — sc. 20–22 (the coverage audit of P/08,
the view fields of chapter 8.1 and a mark beyond the limit of `rev`), 25 — sc. 23–26 (the coverage audit of P/08, the second pass of Gemini), 31 — sc. 27 (ADR-0094 B3, B4).

The command scenarios of М11/03 sc. 10–13 (`agent-sig`, `seal-member`, `seal-member-round`, `accept`) and М11/04 sc. 06 (`accept` with
a road) are not moved: the same cases without a change of bytes are the vectors of the common contracts
[`agent-sig`](../../../../common/vectors/agent-sig/README.md), [`domain-envelopes`](../../../../common/vectors/domain-envelopes/README.md)
(`m1-open.tsv`, `m1-round.tsv`) and [`accept`](../../../../common/vectors/accept/README.md); their inputs are removed together with the steps (the row of
`corrections.tsv`). The other scenarios of М11/03 are the acceptance of [chapter 8.1](../../1/README.md) (04, 06–09); М11/04 sc. 02–04 —
[chapter 9.2](../../../../09-agent/acceptance/2/README.md), М11/08 — [chapter 6.7](../../../../06-console/acceptance/7/README.md) (01–03), [lesson P/10](../../../../10-domain-console/acceptance/README.md) (05), the vectors `peer` (06), М11/12 — chapters 8.10 and [9.1](../../../../09-agent/acceptance/1/README.md).

## Stand

**Preparation of each scenario** (from the acceptance README of М11/03, «Подготовка каждого сценария 01–09»). The runner brings up on
one machine three clusters — `hold`, `m1`, `m2`: each has its own empty store, its own `{data}`, its own role sockets and
ports of the console and the resource, its own ring (P/06.2 Н1.2), the manifest catalogue — only `testsub`; the console, the controller and the worker `w-1`
of `testsub`, the resource of its own server (`srv-hold`, `srv-m1`, `srv-m2`). There are no units. There is no domain: it is set up by the steps of the scenario
(`@install domain`, `@start domain`, `@start agent`) or by the directive `@domain`. The domain name is `acme`; the recovery file of the
installation is `{recovery}` in the instance directory.

- `store` at `member <кластер>` is the store door of the cluster through `admin.sock` (the preparation and the observation of the domain rows).
- `resource` without a prefix is the resource door of `hold`: through it the holder's objects `domain/members/<член>/…` are read.
- Do not speed up the clocks: LOST_AFTER 45 s, REPORT_EVERY 5 s, MARK_REFRESH 22.5 s; the `@until` terms are taken with a margin.

**Scenarios 15, 16** (from the acceptance README of М11/04), **21 and 25**: there are four clusters — `hold`, `m1`, `m2`, `relay`. The agent `relay` always
opens the relay door (`RELAY=1`, `{relay_port}`); the directives `@domain <кластеры>`, `@start agent <кластер> via
relay`, `@stop agent`. The topology is empty until the step that writes it.

**Scenarios 20–22** (the coverage audit of P/08, audit-kimi 1e9929d51) — the view fields of chapter 8.1 on the stand:
- sc. 20 — `trust` and `topology` of the view ([chapter 8.1](../../../spec/08.1-domain.norms.md) Н1.2а, Н1.6а): before the topology is written —
  exactly `{rev: 0, star: [], via: {}}`; `trust.rev` is the same `rev` of the set as `reports.<член>.keys_rev` after `@domain`
  (the readiness of `@domain` — each member holds the holder's set); the written topology is seen in the view by the next pass
  (`@until`). `m2` in `via` is not a relay — there are no refusals of Н1.2; the direct report of `m1` is the second road (Н1.3а).
- sc. 21 — `relay_refused` (Н1.6а): the mark of `m1` at the holder is spoiled (`@stop domain`, then `@on hold @spoil object` — the writer of the
  mark is stopped, — `@start domain`), and each packet of `relay` with `m1` gets `refused` «unavailable» (Н3
  «держатель на POST /api/relay» step 2) — the record of the relay in the view is stable; a topology without `via` — the relay learns from the answer
  `relay_for: []`, the next packet is empty and accepted — the record is removed. The field `relay_refused` in the form of the view is optional, therefore step
  11 accepts `{}` or the absence of the field (`@oneof`); there is no key `relay` in any branch.
- sc. 22 — the mark `domain/members/m1/reported` with `rev` 2^53 (9007199254740992, one above `pos53`), put past the
  writer while the agent `m1` is stopped: the member is `silent`, the view is incomplete by the field (`complete: false`). The strict reading — the mark is not by the
  form ([the outcomes of the family](../../../data/member-reported.outcomes.tsv): there is no copy, the member is `silent`); the non-strict one — there is no generation
  `reports/9007199254740992` and the `sha256` is foreign (chapter 8.1 Н3 step 2) — the same `silent`. `@until 10`: the mark of `m1` is
  younger than `MARK_REFRESH` + `REPORT_EVERY` at the moment of the stop, and before LOST_AFTER (45 s) the silence by the term does not come —
  `silent` is given only by the substitution.

**Scenario 04** (from the acceptance README of М11/08): the agent `m1` is given the TLS directory `inputs/kit-m1-one/` (only `ca.pem`
of the centre A), then `inputs/kit-m1-two/` (`ca.pem` A and `ca.next.pem` B), then the variable is removed (`@env m1
W2C_TLS_DIR=…`, `@env m1 W2C_TLS_DIR`; the value `inputs/…` is a path from this directory). The doors of the stand do not speak TLS: the agent
only publishes the fingerprints and the certificates of the centres (Н1.6 `tls_ca`, `tls_ca_certs`). The fingerprints in the expectations are sha256 of the DER of these
files: A — `d72f9e5e…68a6`, B — `6fefd57b…e217`. Step 4 — the row `domain/members/m1/ca-certs` is written before `Entry.ca` (step
3 already sees the fingerprint), step 18 — the removal by the administrator deleted it. Steps 10–11 check that an edit by the administrator without
a change of the centres at the member is rewritten by its next report. Steps 14–16 — two agent passes (`REPORT_EVERY` 5 s) without
`tls_ca`: the fingerprints are not removed. How the runner passes the environment and restarts the console and the agent of the cluster with the variable
(`@env`) — the dictionary of the «Domain stand» of [the common acceptance README](../../../../common/acceptance/README.md), `@env` and
«Forwarding environment» (the review analysis of stage B 8–10, № 22: `М-16`).

**Scenario 19** — a neighbour on the stand: the door `GET /domain/members` of the domain console ([lesson P/10](../../../../10-domain-console/spec/10-domain-console.norms.md)
Н1.2б, P/10-07; C10-MEMBERS-SOURCE-01, C10-MEMBERS-KNOCKING-ABSENT-01). The process `domain` is stopped (step 2), so that the pass of
the holder does not rewrite the view; in its place the view `inputs/view-member-list-ghost.json` is put: only `hold`, there is no field `knocking` (step 3). Step 4 shows that the domain console reads this view. Step 5: `members` is the
doc of the rows `domain/member-rows/<раздел>` (`hold`, `m1`, `m2`), not the view; there is no field `knocking` in the read view —
`knocking: []`.

**Scenario 17** (from the acceptance README of М11/12): the agent `m1` holds the row of its own section — the holder's answer is without `members`. An edit of `ca` changes this row — the copy
at `m1` is with it (the row came once), then the answer is again without `members`. The runner goes as the person `root`
(lesson P/08, chapter 8.4); the expectation of `@carry` is `ok <JSON>`, a subset of fields.

## Inputs `inputs/`

| File | Scenario | What is in it |
|---|---|---|
| `other-root.json` | 02 | the recovery file of a foreign root (`root 2` of the vectors [`keys`](../../../../common/vectors/keys/README.md); formerly — lesson М11/2 Н5) for `@join m2 inputs/other-root.json` |
| `kit-m1-one/ca.pem` | 04 | the centre A (`w2c test ca north`), EC P-256 |
| `kit-m1-two/ca.pem`, `kit-m1-two/ca.next.pem` | 04 | the centres A and B (`w2c test ca south`) |
| `view-member-list-ghost.json` | 19 | the object `domain/view` (the form [`view`](../../../data/view.schema.json)): `member_list` — `hold` and `ghost`, without `knocking` |
| `member-reported-rev-2pow53.json` | 22 | the mark object `domain/members/m1/reported` (the form [`member-reported`](../../../data/member-reported.schema.json)), JCS; all fields by the form, except `rev` = 9007199254740992 (2^53, the limit of `pos53` — 2^53 − 1) |

The inputs were moved byte for byte from `inputs/` of the acceptances of М11/03 and М11/08, `view-member-list-ghost.json` is added for sc. 19
(the exception `acceptance-entry inputs`; the description of the exception — the Architect's decision 2026-10-29; the analysis of the plan of the move of lesson 8, § 3 «Исключения»),
`member-reported-rev-2pow53.json` — for sc. 22 (the coverage audit of P/08; the description of the exception does not name it yet — the edit of
the description is up to the Architect, the skill `lesson-spec`).

## scenarios.tsv

The format is the dictionary of the «Stand» of the common acceptance README and the section «Domain stand». `$fp1`, `$fp2` are fingerprints that the runner
binds from `knocking` and substitutes into the admission: so the stand repeats what a person does, comparing the fingerprint with the log of
the agent; `$kr` (sc. 20) is the `rev` of the set from `trust` of the view; `$k` (sc. 29) is the private key of the batch from the answer of `POST /domain/batches`, the runner gives it to the command `join` by the directive `@join m2 batch=b1 $k`. In total 21 scenarios / 218 steps.

**Sc. 29 — the admission batch** (ADR-0113 addendum (2)–(4); P/08.3 Н1.1б; the contract of the admission of a report «The batch knock»; P/09.1 Н1.1 `join` `batch`). `@domain m1` admits `hold` and `m1`, the agent `m2` is not started. Step 3 — a live batch with the same name — 409. Step 4 — `join` on `m2` with the batch: the row `domain/join` `{class: camera, batch}`. Step 6 — the box is admitted without a person: `Entry` with `class: camera` and `batch`, there is no knock. Step 7 — the exclusion: the fingerprint goes into `refused` of the batch. Steps 8–10 — the same token does not bring the box back: the knock with `batch` lies and waits for a person for two agent passes. Steps 11–12 — the revocation of the batch, the row with `revoked: true` and `used: 1`. Step 13 — a person admits the knock by the fingerprint: the revocation and `refused` close only the admission by the batch. By reading: the exhaustion of `n` and the revocation against a new box (on the stand there is one free box `m2`, `join` is create-once), the term `until`, the overflow of `refused`, the relay `via`, the `state` of the copy.

Sc. 18 (C08-G06): the door `signer` sends to the process `domain` the packet `POST /api/relay/m9` with `{"relayed": {}}` without a signature — `m9`
is not a member: 404 before the check of the signature and without a knock (P/08.3 Н2, the order of the row `POST /api/relay`).

The stand does not cause the loss of the holder's memory (409 `rebase`): it is checked by the vectors `accept` and by reading the contract of the admission of a report.

The mutation check 2026-10-18 (the analysis of run 41, «Мутации»): scenario 14 — a knock of a stranger without a valid signature (the clock of the
agent 400 s ahead, outside `MEMBER_WINDOW`) does not get into `knocking`, with a valid one it does (Н2: the signature by the key from the body,
401 — without a knock).

Sc. 03 does not depend on the moment of the backup copy (chapter 8.8: `first`, `BACKUP_EVERY`): the member `m1` is a keeper, and
`domain/backup-taken` in its report gives its own generation at any moment of the run. Therefore step 5 waits at `m1` for the object itself
`testsub/snapshot/w-1` (the placement `c3`), steps 6–9 — two changes of the mark of the report round `sent_at`, bound after the snapshot
(two agent passes: one change may belong to a round that was in flight), and only step 10 takes the last generation: in
it the snapshot is there for any number of generations between them (a generation carries all objects of the member, Н1.3).

**Scenarios 23–28** (23–26 — the coverage audit of P/08, the second pass of Gemini, the draft G03 `e32df6f8b`, rewritten; 27 — ADR-0094 B3, B4; 28 — C08-STOLEN-KEY-ENTRY-01):
- sc. 23 — a repeat of the admission (Н3 «принять члена» step 1, D20): the stand is brought up by hand, as sc. 01; step 5 also waits for the `key`
  of the holder in the list — further the list does not rewrite itself, and the `rev` after the admission (`$r1`) does not change. The same fingerprint —
  200 without a write (the same `rev`, step 9 reads it again); another one — 409 «… was admitted with another key: have it leave first»;
  `m2` without an agent does not knock — 404.
- sc. 24 — `POST /domain/members/<член>/ca` (Н1.6 `admin`): a list not in ascending order is written in ascending order; the same
  list again — a new write (`rev` grows). The agent `m1` has no TLS kit — `on_accept` does not rewrite the edit.
- sc. 25 — the removal of the centre and of a route by an edit of the topology (Н1.2 `centre`, `put_order`): `centre: ""` and `via: {"m1": ""}`
  remove the centre and the route; `centre: null` — too.
- sc. 26 — the row `domain/topology` is spoiled past the door (`doc` is not JSON): `PUT` — 503 `unavailable`, the row is the former one (the edit is
  partial and against `base_rev`, it cannot be executed without reading; C08-TOPOLOGY-PUT-UNREADABLE-01), `GET` — 503 too (P/10 Н1.2в).
- sc. 27 — the versions and the replay memory of the edit doors ([chapter 8.0](../../../spec/08.0-domain.norms.md) Н1.9). The clusters `hold`, `m1`, `m2`.
  There is no row `domain/topology` yet: the condition — 412 with `revision: 0`, and the first write carries `base_rev: 0` (steps 3–5). The condition is judged before the content (step 7), the form — before reading (step 9),
  `If-Match` with `base_rev`: different ones and the index next to it — 400, equal ones — a write (steps 10–12). The index of the former version no longer fits (step 13), the current one fits (steps 14, 15).
  Step 17 repeats step 16 with the former `If-Match`: without the memory this would be a 412 of one's own write; step 22 gives the saved 412 with `revision: 4`, although the row is already at 5.
  Step 24: `<key>` — `sha256("root" ‖ 0x00 ‖ "PUT" ‖ 0x00 ‖ "/domain/topology" ‖ 0x00 ‖ "t-r1")`; `body` is judged by a substring: the order of the fields of the body is the implementation's.
  Steps 27–31 — `If-Match` by the row `domain/member-rows/<раздел>`: `$m` is the `rev` of the list, the number depends on the course of `@domain`. Step 30: a non-member — 404 before the condition; step 31: the admission judges the condition first.
  The stand does not bind the value of `ETag`: it judges the quotes of the header, and the index — through `If-Match` from the store row.
- sc. 28 — a machine came back after a theft (Н3 «принять члена» steps 1, 4, 6; the contract of the admission of a report `forget`; C08-STOLEN-KEY-ENTRY-01): `stolen` is not caused on the stand, the record of `m1` without `key` is seeded by `admin.sock`. Step 3: the key of the agent is in `revoked_keys` — the knock is kept, the admission 409. Step 6: `revoked_keys` holds a foreign key, therefore the key of the agent plays the new key of the machine — the admission 200, `revoked_keys` remained, the knock is removed. Not run by an implementation.

Not taken from the draft G03: 503 of step 0 of «принять члена» with an unreadable `domain/view` — the view object is rewritten by the pass of
the holder once in `VIEW_EVERY` (3 s), the stand will not hold the spoiling window (a race, by reading; with `domain` stopped there is no door);
the refusal of the agent door with an unreadable `domain/revoked` (C08-CARRY-UNREADABLE-01) —
`@carry` sees only the answer 200, and `silent` after LOST_AFTER does not tell the cause (by reading). The expectation of the draft `star: []`
after `centre: ""` without `star` in the body is wrong: a field not given is the former one, a star without a centre — 409.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

A wait for an event is `@until`: sc. 03 steps 6–9 wait for two report rounds after the snapshot (`sent_at` changed twice; by `rev`
the generation cannot be told — the review of stage B 1–2, item 1); sc. 17 steps 2 and 8 — for the list of members at `m1`; sc. 20 step 5, sc. 21
steps 5, 9, 11, sc. 22 step 4 — for the next pass of the view (`VIEW_EVERY` 3 s). The remaining sleeps:

| Sc./step | Sleep | Reason |
|---|---|---|
| 03/2 | 20 s | time before an action: the reports after `@domain` have calmed down — `$r1` and step 3 read one generation (silence is not observed) |
| 03/14 | 20 s | time before an action: the silence of the reports before binding `$r3` — step 16 waits for a repeated sending of the same generation; the counter `c3` is created with `step: 0` (step 4): the training handler writes `n` into `status` of the pulse (P/03.4 Н1.1), and the comparison of a contribution excludes only `ts` (P/09.1 Н1.2 `change`) — a ticking counter would lawfully give a new generation every round (C08-REPORT-STEADY-COUNTER-01) |
| 04/15 | 12 s | absence: without the directory `W2C_TLS_DIR` the field `ca` of the member is not removed — two agent passes (`REPORT_EVERY` 5 s) |
| 05/3 | 60 s | the domain is complete and absence: the clock of `m1` 100 s behind does not make it silent within the term (not one event — `@until` would pass before the first report with this clock) |
| 14/5 | 10 s | absence: a knock without a valid signature is not admitted — the agent knocks once in `REPORT_EVERY` 5 s, two passes |
| 17/3, 17/9 | 10 s | time before an action, the round is not observable: `@carry` reads the answer of the same round — the holder learns from the next report of `m1` that its list is fresh (`REPORT_EVERY` 5 s and a pass); steps 2 and 8 wait for the list at `m1` (`@until`) |

## Evidence outside the TSV

Checked by reading (the norm of the chapter, Н5): the CAS of the admission of a member, a failure between the writes of a generation, of `delta` and of the mark, `sign_failures`
in the mark and the view, non-matching certificates `tls_ca_certs`, the union of the handshake at the role door (lesson P/10 Н1.4). The knock and the checks
of the holder on a relay packet — sc. 02, 03 of [the acceptance of chapter 9.2](../../../../09-agent/acceptance/2/README.md).

## corrections.tsv

The log of AI corrections (ADR-0080 addendum 1): `date`, `sample`, `fix`, `languages`. The logs of the acceptances of М11/03, М11/04, М11/08 and
М11/12 as a whole, at the beginning of this log, with the former paths and numbers (they are resolved by `Platform/common/id-map.tsv`); then
the rows of the move, the renaming and the removed command scenarios.
