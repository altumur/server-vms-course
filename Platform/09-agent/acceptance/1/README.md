# Acceptance P/09.1 — the agent of a member (stand)

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand, the dictionary of directives and doors — [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/README.md#domain-stand) (the stand of several clusters; formerly — the M11 dictionary of the acceptance README
of M11/01; the plan of the move of lesson 8, V5). The norm of the chapter is [`09.1-agent.norms.md`](../../spec/09.1-agent.norms.md) N5;
[the contract](../../spec/09-agent.api.openapi.yaml), the lecture (`ru/09-agent.md`, for people, not in the export). The scenarios were moved (stage B, ADR-0083
addendum (1): without a change of behaviour) from the acceptances of M11/05 (04 → 13), M11/06 (04, 07, 08), M11/10 (11), M11/11 (05, 06 → 14) and
M11/12 (01, 03, 06); the numbers, names and steps are the former ones, except `13-slot-liveness` (in M11/05 — `04-slot-liveness`) and
`14-pointer-checksum` (in M11/11 — `06-pointer-checksum`): the number 04 is taken by the scenario of M11/06, the number 06 — by the scenario of M11/12;
the next numbers after the largest number of the sources of the chapter (M11/10 sc. 12) — in the order of the lesson M11, then of the scenario
(the Architect's decision on the move plans 8–10, item 14; a row of `corrections-1.tsv` (historical correction record)). In total 22 scenarios / 252 steps: 5 from
M11/05, 26 from M11/06, 20 from M11/10, 11 from M11/11, 40 from M11/12, 2 — sc. 06 steps 9–10 (`as_of` to the medium no more often than once an hour; VMS request № 19); 20 — sc. 15 `one-agent` (DOM-AGENT-TURN-01);
35 — sc. 16–19 of the coverage audit of P/09 (audit-kimi aee4369fb, drafts J01–J04); 72 — sc. 20–25 of its second pass (Gemini,
cc36de538, drafts G03, G04; below); 21 — sc. 27 `roles-copy` (ADR-0098 §4).

The other scenarios of the sources are at the chapters of their outcome (ADR-0083 addendum (13); the appendix of the plan of the move of lesson 8): M11/05
sc. 01, 03, 05 — [chapter 8.5](../../../08-domain/acceptance/5/README.md), 02 — [the acceptance of chapter 6.7](../../../06-console/acceptance/7/README.md) (13); M11/06 sc. 01, 02,
03, 05, 09 — [chapter 8.6](../../../08-domain/acceptance/6/README.md), 06 — [chapter 8.1](../../../08-domain/acceptance/1/README.md)
(sc. 15); M11/10 sc. 01 — the acceptance of chapter 6.7 (15), 02–04, 08–10, 12 — [chapter 8.8](../../../08-domain/acceptance/8/README.md),
06 — the vector package [`follow`](../../vectors/follow/README.md); M11/11 sc. 01 — [chapter 8.9](../../../08-domain/acceptance/9/README.md),
02 — [the acceptance of lesson P/10](../../../10-domain-console/acceptance/README.md), 04 — the vector [`alarms`](../../../10-domain-console/vectors/alarms/README.md), 03 — the vectors [`resolve`](../../../06-console/vectors/resolve/README.md); M11/12 sc. 02 — [chapter 8.3](../../../08-domain/acceptance/3/README.md) (sc. 17), 04,
05 — [chapter 8.10](../../../08-domain/acceptance/10/README.md). The agent side in the scenarios of other chapters — the list
«Neighbours on the stand» of the norm of the chapter, N5.

## Stand

**Preparation of each scenario** — as the acceptance README of [chapter 8.3](../../../08-domain/acceptance/3/README.md)
(«Preparation of each scenario»; from the acceptance README of M11/03): the runner brings up on one machine three clusters — `hold`, `m1`, `m2`; each has
its own empty store, its own `{data}`, its own role sockets and ports of the console and the resource, its own ring (P/06.2 N1.2), the manifest catalogue
— only `testsub`; the console, the controller and the worker `w-1` of `testsub`, the resource of its own server (`srv-hold`, `srv-m1`, `srv-m2`).
There are no units. There is no domain: it is set up by the directive `@domain` of the first step of each scenario. The domain name is `acme`.

- `store` at `member <cluster>` is the store door of the cluster through `admin.sock` (the preparation and the observation of the domain rows at a member:
  `domain/agent`, `domain/member-key`, `domain/member-list/<part>`, `domain/keys`, `domain/member-topology`, `domain/grants`,
  `domain/backup-taken`, `domain/shared`, `domain/shared-refused`, `domain/root`, `domain/placed`, `domain/outcomes`,
  `domain/agent-turn`); `store` without `member` is the store of `hold`.
- `resource` without a prefix is the resource door of `hold`: through it the holder's objects `domain/members/<member>/…` are read.
- Do not speed up the clocks: `LOST_AFTER` 45 s, `REPORT_EVERY`, `MARK_REFRESH` 22.5 s, `VIEW_EVERY` 3 s; the `@until` terms are taken with
  a margin.
- The runner goes as the human `root` (the first administrator — chapter 8.4).

The differences by scenario (from the READMEs of the source acceptances):

- **Scenarios 01, 03, 06** (from the acceptance README of M11/12). The doors `holder`, `member`, `resource` and the directives `@domain`,
  `@start`/`@stop agent` — the dictionary of the «Domain stand».
- **Scenarios 04, 07, 08** (from the acceptance README of M11/06). The catalogue `testsub` — `domain.edit: [start, labels]`, `domain.ref:
  name`. The doors `holder`, `member` and the directives `@domain`, `@cut`, `@mend`, `@clock` — the dictionary of the «Domain stand»; at the door
  `holder` the runner sets `Idempotency-Key` also for `PUT`/`DELETE`. `$id` is the id of the stored edit from the answer 202. The holder stores
  the edit (chapter 8.6), the agent of `m1` applies it (N1.5) after `@mend`; the condition `If-Match` of the units door — sc. 14 of the acceptance of
  [P/06.1](../../../06-console/acceptance/1/README.md). Sc. 08: `@clock m1 +90` — the agent clock outside the window of the units door
  `UNIT_WINDOW` 60 s ([the agent signature contract](../../../common/contracts/agent-signature.md)); step 10 returns the clock.
- **Scenarios 05, 14** (from the acceptance README of M11/11). The catalogue `testsub` with a declaration of the shared document:
  - `domain.shared: [step, marks, {rounds}]`;
  - `step` — `int` with `inherit: 1`;
  - `marks` — `list` with `inherit: []`, `merge: union`.

- **Scenarios 16–19** (the coverage audit of P/09, audit-kimi aee4369fb). The doors `holder`, `member`, `store`, `token` and the directives
  `@domain`, `@stop`/`@start agent`, `@on` (`@freeze`, `@thaw`, `@put object`) — the dictionary of the «Domain stand» and the common dictionary
  of directives; the freeze limit is 120 s.

### Coverage audit of P/09, the second pass (Gemini)

Sc. 20–25 (`audit-coverage-gemini` cc36de538, drafts G03, G04) — the same stand; the doors `holder`, `member`, `store`,
`token` and the directives `@domain`, `@join`, `@stop`/`@start agent`, `@on` (`@put object`) — the dictionary of the «Domain stand». The rows
bypassing the writer are put by the store door of the member through `admin.sock`, as in sc. 03 and 18.

## Inputs `inputs/`

| File | Scenario | What is in it |
|---|---|---|
| `shared-doc-unknown-issuer.json` | 05, 14, 22 | a shared document of the form ([P/08.9 N1.2](../../../08-domain/spec/08.9-domain.norms.md) `document`) with an unknown issuer: `kid` `0000000000000000`, `issuer` — 32 bytes `0x11`, `sig` — 64 zero bytes base64url |
| `backup-foreign-term.json` | 19 | a backup copy document of the form `backup.schema.json` (`common.domain_backup_doc`) of term and revision 99, `holder` `hold`, `members` `[hold, m1]`, empty `state` and `objects`, `issuer` — 32 bytes `0x33`, `kid` — the first 16 characters, `sig` — the bytes 0…63 base64url (does not verify: the agent reads its own copy by form); JCS without a line break, sha256 `eec6d36c2e9636846f2d335daf072c791c8022e1e714091f05fe56e4b2380434` — in the row `domain/backup-taken` of step 5 |

`shared-doc-unknown-issuer.json` is copied byte for byte from `inputs/` of the acceptance of M11/11 (the plan of the move of lesson 9, § 3
«Inputs and form»); `backup-foreign-term.json` — the coverage audit of P/09 (draft J04), the bytes of the draft.

## scenarios.tsv

The format is the dictionary of the «Stand» of the common acceptance README and the section «Domain stand»; the expectation is a subset of the fields, `~` — a substring,
`@time` — a time in a string (P/01.1 N0), `@not(…)` — not equal. In total 22 scenarios / 252 steps. Sc. 27 — ADR-0098 §4, there is no dry run by an implementation; steps 14–15 give the emergency row so that `sealed` opens without the grant fields too; step 19 `@sleep 7` is a check of absence: the agent pass 5 s and a margin, the copies are not erased, the indices are the same; a break between two writes of the agent, an old agent and a rollback — by reading: the stand does not interrupt a write and does not substitute the agent version.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

Waiting for an event — `@until`: sc. 01 step 9 waits for the next report of the same generation (`received_at` changed, `rev` the
same). The remaining sleeps (from the READMEs of the acceptances of M11/12 and M11/10):

| Sc./step | Sleep | Reason |
|---|---|---|
| 01/2 | 35 s | time before an action: the first backup copy and its keepers after `@domain` — `BACKUP_EVERY` 30 s and the agent pass 5 s |
| 01/5 | 10 s | time before an action: the member went quiet after the write of `domain/backup-taken` — two agent passes |
| 06/6 | 10 s | absence: fresh copies with the same content are not rewritten — a rewrite would be in the nearest agent pass (5 s), two passes; `as_of` is freshened no more often than `FRESH_EVERY` 60 s |
| 06/9 | 65 s | absence: longer than `FRESH_EVERY` — the freshening of `as_of` in memory has already happened, but it is not in the row: to the medium no more often than `AS_OF_STORE_EVERY` 3600 s (VMS request № 19; the whole hour — by reading) |
| 11/6 | 65 s | time before an action: two windows of `BACKUP_EVERY` after the revocation — the copy with `bob` (step 9) is made at once, not after a window |
| 11/10 | 6 s | time before an action: the copy with `bob` — in the nearest pass of the holder (3 s) with a margin |
| 15/4 | 25 s | absence: for two `TURN_RENEW` (10 s) the waiting one does not take a fresh queue — the holder is the former one (step 5) |
| 15/16 | 30 s | absence: the killed active one has not given up the queue, and it is not taken earlier than `TURN_TERM` 45 s from the last renewal (the renewal — no later than 10 s before SIGKILL: 30 < 35) |
| 18/6 | 10 s | absence: the agent of the holder does not write and does not delete its own row `domain/break-glass/hold` — a write or a deletion would be in the nearest agent pass (5 s) after the holder's answer; two passes |
| 18/9 | 10 s | absence: the copy of `m1` is not touched with an unreadable holder row (`held`) — a deletion would be in the nearest agent pass (5 s); two passes |
| 24/6 | 15 s | absence: with an unreadable `domain/outcomes` the agent does not perform the edit — the performance would be in the nearest agent pass (5 s) after the issue by the holder; three passes, and the holder view (`VIEW_EVERY` 3 s) manages to show the pending edit |
| 27/19 | 7 s | absence: the copies `domain/grants` and `domain/roles` are not touched with an unreadable holder row — an erasure would be in the nearest agent pass (5 s) with a margin |

## Evidence outside the TSV

Checked by reading (the norm of the chapter, N5 «By reading»): the agent does not send a new generation by time, an unreadable edits row
of the holder at itself, the alarm page and the urgent report (the stand does not raise alarms), the agent in the process (the stand has no process without
a kit), the field `sign_failures` of the publication and the count `sign_failures_console` (an edit has no way to be delivered to an agent without a key: it does not ask
for the holder's answer, and an edit received before the key was spoiled is a race of one pass), `no_seal` and `domain.reports`, key changes at a member without a connection, the book secrets at
a member, the refusals of the keeper's agent by the sum and by `record` (the holder does not send such a document), a break of the road of the local token door,
an answer from the relay memory and `as_of` of the grants copy (on the stand `as_of` is visible only as a store row, and its freshening is
no more often than `AS_OF_STORE_EVERY`), the agent body limit; the HTTPS client and the first contact (the stand without TLS). The bytes of the agent signature
— the package [`agent-sig`](../../../common/vectors/agent-sig/README.md), the function `peer` — the package
[`peer`](../../../common/vectors/peer/README.md), the function `follow` — the package [`follow`](../../vectors/follow/README.md).

## Kit assistance seams

[seams.tsv](seams.tsv) provides 44 CALL steps over ordinary implementation paths. The fixture/port contract is [forms/README.md](../../forms/README.md); [stages.tsv](../../forms/stages.tsv) selects them. They assist the kit and do not replace the ordinary process scenarios or their required neighbours.

## Anywhere copy hash (G09-ANYWHERE-HASH-01)

The five fixture vectors in [`inputs/anywhere-hash/cases.tsv`](inputs/anywhere-hash/cases.tsv) specify the complete-body
digest of P/08.4 N1.3 carry and the check before the copy of N1.4 member_anywhere. The input column names a JSON file
next to the table; expect is a JSON subset of the observations, not an input to the implementation.

Each input has an initial stored copy with its exact index and last confirmed taken_sha256 marker, and a list of attempts.
Every attempt starts independently from that initial state: its trusted carry advertisement is advertised, its real
200 body from `GET /api/anywhere/{member}` is the UTF-8 text body. The fixture calls the ordinary agent copy code with
the body and mark, and records the store operations and marker changes. received_at is the receipt time and domain_age is the answer age; each case prepares a valid trusted carry for server m1 and its active agent guard. It reports arrays in attempt order:
computed_sha256, copy_writes, marker_confirmed; for a refusal also related_edits (the writes belonging to this copy),
copy_items, copy_index and taken_sha256. The digest observation comes from the normal code path that judges the body;
it is not computed by the fixture instead of that path. The three positive vectors must reach the actual copy write.

The existing agent-carry IO seam can carry these inputs: these files do not declare a new native command. A fixture
that only calculates the expected digest does not check the negative cases: they require the former copy, exact index
and marker to stay unchanged and zero copy writes and related edits. The five cases cover as_of in the digest, JCS
instead of wire formatting, a refused digest of doc alone and a refused mismatching whole-body digest.

The owner wire body contains raw KV strings doc and as_of. Only the outer JSON is canonicalized for the digest; the internal doc text is not normalized first. The inner-text neighbor has equal decoded inner objects but different strings and digests, and observes the exact successful copy_items. The trusted advertised as_of, received_at and domain_age retain their existing numeric types. Existing refusal cases preserve the complete initial raw copy, index and the rebaselined current-wire marker. No case reports actual IO success before its adapter is run.
