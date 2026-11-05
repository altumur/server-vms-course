# Acceptance P/06.7 — the cluster console in a domain (stand)

This English text is the source; the Russian translation `ru/acceptance/7/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/README.md#domain-stand) (a stand of several clusters). The norm of the chapter is
[`06.7-console.norms.md`](../../spec/06.7-console.norms.md) N5. The scenarios were moved from the acceptances of М11/08 (01, 02, 03),
М11/09 (06; 03 → 14), М11/05 (02 → 13) and М11/10 (01 → 15) (stage B, ADR-0083 addendum (1): without a change of behaviour); the numbers,
the names and the steps are the former ones, except `13-notes-unique` (in М11/05 — `02-notes-unique`), `14-break-glass` (in М11/09 —
`03-break-glass`) and `15-held-and-copies` (in М11/10 — `01-held-and-copies`): their numbers are taken by the scenarios of М11/08 (it has more scenarios in
the chapter); the new numbers are the next ones after the largest number of the sources of the chapter (М11/10 sc. 12), in the order of
the lesson М11, then of the scenario (the Architect's decision on the plans of the move 8–10, ADR-0083 addendum (14) item 14; the row of
`journal/corrections-7.tsv`). In total 10 scenarios / 106 steps: 41 from М11/08, 18 from М11/09, 5 from М11/05, 9 from М11/10, 11 — sc. 16 (the second pass of the coverage audit of P/06, Gemini), 7 — sc. 17 (ADR-0094 B6), 9 — sc. 18 (ADR-0094 B7), 4 steps of sc. 03 (ADR-0112 addendum (12) item 3), 1 step of sc. 03 (ADR-0112 addendum (13) item 10), 1 step of sc. 03 (the ADR reconciliation S23).

The function `resolve` without a stand is checked by the vector [`resolve`](../../vectors/resolve/README.md) (12 rows: 11 — the former sc. 03 of the acceptance of
М11/11); `families` of the door `/domain/keys` (N1.11) — by the vector [`key-families`](../../vectors/key-families/README.md) (12 rows:
one `id` in several manifests, the order; on the stand there is one manifest with `domain.keys`). The other scenarios of the sources are at the neighbours: М11/08 sc. 04 — [chapter 8.3](../../../08-domain/acceptance/3/README.md),
05 (the holder's page) — the lesson P/10, 06 — the vectors [`peer`](../../../common/vectors/peer/README.md); М11/09 — [chapter
8.4](../../../08-domain/acceptance/4/README.md), [8.5](../../../08-domain/acceptance/5/README.md) (11) and the vectors
[`may`](../../../common/vectors/may/README.md); М11/05 — [chapter 8.5](../../../08-domain/acceptance/5/README.md), [9.1](../../../09-agent/acceptance/1/README.md)
(13) and the vector [`assemble`](../../../08-domain/vectors/assemble/README.md); М11/10 — [chapter 8.8](../../../08-domain/acceptance/8/README.md),
[9.1](../../../09-agent/acceptance/1/README.md) (11), the vectors [`record`](../../../common/vectors/record/README.md),
[`ask-sig`](../../../common/vectors/ask-sig/README.md), [`follow`](../../../09-agent/vectors/follow/README.md).

## Stand

**Scenarios 01–03, 15** (from the READMEs of the acceptances of М11/08 and М11/10). The preparation is as in the acceptance of [chapter 8.3](../../../08-domain/acceptance/3/README.md)
(«Stand», «Preparation of each scenario»): the clusters `hold`, `m1`, `m2`, the catalogue `testsub`. The doors `holder`,
`holder@<cluster>`, `member <cluster> console`, `signer` and the directives `@domain`, `@person`, `@env`, `@start domain on`,
`@stop domain`, `@move` — the section «Domain stand» of the common acceptance README; the forwarding environment is there too (`CLUSTERS` of the consoles,
`DOMAIN_CONSOLE_URL` of the process `domain`, `SIGNER_URL` only at `hold`). The runner goes as the person `root` (chapter 8.4).

- `member hold console` is the console of the holder's cluster: `GET /domain` at it is also a forwarding (into the domain console of its own
  box by `view.url`).
- Scenario 02 sets up the domain only with `m1` (`@domain m1`): `m2` is not a member, it has no list.
- Scenario 03 creates the unit `c2` on `m2`; the controller of `m2` places it, step 3 waits for the answer 200 and binds `$w`, `$s`,
  `$r` (`worker`, `server`, `reason`), steps 4 and 5 wait for the same values through `/domain/at/m2/…` and with the subsystem prefix:
  the forwarded answer equals the local one (N1.6, the answer as it came). The 404 of a member «как пришёл» — step 13 (`hold` has no unit `c2`).
  `m9` is the name of a non-member.
- Scenario 15. Keepers: with two members `ok` (`m1`, `m2`) both. `@sleep 35` — `BACKUP_EVERY` and the pass of the agent after
  `@domain`: the admission of members changes the state, and the first backup copy is not the last one. `$r` is its revision from the first answer
  after the silence; a quiet domain makes no new revisions ([chapter 8.8](../../../08-domain/spec/08.8-domain.norms.md) N1.5 `rev`). The
  holder has no backup copy: `backup` of its `/api/held` is `null`. Step 7 — the holder's view (chapter 8.8 N1.3 `term`, the door
  of the domain console — the lesson P/10) — a neighbour on the stand.

**Scenario 16** (the second pass of the coverage audit of P/06, Gemini, `audit-coverage-gemini` 0a5ae79f9) — the stand of sc. 01–03, 15
(`testsub` declares `domain.shared`, as in the acceptance of [chapter 8.9](../../../08-domain/acceptance/9/README.md)).
- Steps 2–6 — `GET /domain/shared/testsub` at the console of the holder's cluster (`member hold console`): the document named by
  the pointer (`domain/shared-docs/rev-<rev>`, N1.14 `term, rev`), — `term` 1, `rev` 1 after an edit by the holder (step 2; at a member
  this is sc. 01 of the acceptance of chapter 8.9); `?unit=` empty and repeated — 400 `refused` «a unit id is required», `..` — 404 `no such
  unit` (N1.14 `refusals`).
- Steps 7–11 — without a person (`@person -`): the segment `.` and `..` in percent form under `/domain/` — 404 `not a domain route` (N3
  «forward» step 1, before the guard; D4), the same route without the segment — 401 (step 3, the guard); `/api/held` is an open
  row: the door does not read an invalid `Authorization: Bearer` — 200 (N1.12 `open`, X13).

**Scenario 17** (ADR-0094 B6; the norm — [chapter 6.3](../../spec/06.3-console.norms.md) N2) — the stand of sc. 01–03, 15. A value not by default:
`@env m1 TIMEZONE=Asia/Tokyo` restarts the console and the agent only of the cluster `m1`, so the console `hold` at the same step gives
the former `UTC`: the zone is taken from the environment of the console, not from the shared place and not from the OS. Step 6 removes the variable, step 7 checks the return
to the default. `/session` is an open door, the answer 200 does not depend on the domain; the fields are compared by subset.

**Scenario 18** (ADR-0094 B7) — the stand of sc. 06, 13, 14 (the catalogue `testsub`, `testsub2`; the files of `testsub2` — common README, «Манифесты»).
The runner does not follow `302`: it judges the code, `Location` by equality and the empty body. Without a person (`@person -`) `GET` of the shell — `302` to the page `/` with `return`, also with
an invalid token: the identity is not proved (step 5); `HEAD` and a file — `401`; with a person — the shell byte for byte (P/06.5 N2 «Вход на оболочке»).
A logged-in person without a grant (`403`) — by reading.

**Scenarios 06, 13, 14** (from the READMEs of the acceptances of М11/05 and М11/09). The preparation is as in the acceptance of [chapter 8.5](../../../08-domain/acceptance/5/README.md)
(«Preparation»): the catalogue of each cluster is `testsub` and `testsub2`; on each cluster the controllers of both work, the worker
`w-1` of the manifest `testsub`, the worker `t-1` of the manifest `testsub2` (with the training writer of contributions — [chapter 8.5](../../../08-domain/spec/08.5-domain.norms.md) N5) and
the resource of its own server `srv-<cluster>`; before the steps the store of each cluster has the counter `testsub` `c1-<cluster>` and the shelf
`testsub2` `sh1` `{zone: z1, server: srv-<cluster>}`. `console2` at `member` is the prefix `/testsub2`.

- The person `root` with the password `w2c test root password` is created at `@install domain` (`domain first-admin`, the directive
  `@admin`). The runner goes as this person by default: `admin` `*` at the domain door and in the grants row of each cluster of the stand.
- Scenario 13 — the book `notes` of `testsub2` (`pick: unique`): one ref `t5` on two members — `view.books.conflicts` at
  the holder (chapter 8.5 N1.3, N1.5 — a neighbour on the stand); the book row at `m2` without grants carries only `""` (the book door and
  the copy at a member — N1.1).
- Scenario 14 counts the failures of the emergency login from one address of the runner. A successful attempt does not count: the fifth failure is
  step 13, the sixth attempt — 429, for a correct pair too. The row `domain/break-glass/m1` is written by the process `domain` (steps 2–4 —
  chapter 8.4 N1.6, a neighbour on the stand), the agent carries it to `m1` (step 5 — chapter 9.1 N1.4 `break_glass`).
- Scenario 06 — the key families door at `m1`. The stand has no training worker on the domain, so the families of `testsub` are empty.

An equal answer time to an unknown and to a wrong one, the journal and the limit band by the peer address (not by a header) — by reading.

`answer too large`, `answer broke off`, the recognition of `X-Operator: console` by the role and the journal `domain.forwarded` the stand does not
cause: they are checked by reading (N5 of the chapter). How the runner passes the environment and restarts the console and the agent of a cluster with
a variable (`@env`) — «Implementation decides» item 2 of the chapter.

## scenarios.tsv

The format is the dictionary of the «Stand» of the common acceptance README and the section «Domain stand»; the expectation is a subset of fields. In total 10
scenarios / 106 steps.

## `journal/corrections-7.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`. The rows of the logs of the acceptances of М11/05, М11/08,
М11/09 and М11/10 from before the move are at the beginning of the log, with the former paths and numbers (they are resolved by
[`id-map.tsv`](../../../common/id-map.tsv)): by `sample` — the rows about the scenarios of this chapter; the rows without a scenario (the whole
`scenarios.tsv`, `inputs`, `@sleep`, the preparation, the move) — into all successor chapters (analysis of the review of stage B 6–7, № 18).
Then — the rows of the move of this chapter and of the history of the sources.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

| Sc./step | Sleep | Reason |
|---|---|---|
| 15/2 | 35 s | time before an action: the domain has gone quiet — after the admission of members the next backup copy is not earlier than `BACKUP_EVERY` 30 s, it is brought by the pass of the agent 5 s; `$r` is the last copy (the silence is not to be observed: «копий больше не будет» is an absence) |

The scenarios of the chapter have no other sleeps.
