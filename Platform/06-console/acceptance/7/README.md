# Acceptance P/06.7 — the cluster console in a domain (stand)

This English text is the source; the Russian translation `ru/acceptance/7/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/README.md#domain-stand) (a stand of several clusters). The norm of the chapter is
[`06.7-console.norms.md`](../../spec/06.7-console.norms.md) N5. The scenarios were moved from the acceptances of M11/08 (01, 02, 03),
M11/09 (06; 03 → 14), M11/05 (02 → 13) and M11/10 (01 → 15) (stage B, ADR-0083 addendum (1): without a change of behaviour); the numbers,
the names and the steps are the former ones, except `13-notes-unique` (in M11/05 — `02-notes-unique`), `14-break-glass` (in M11/09 —
`03-break-glass`) and `15-held-and-copies` (in M11/10 — `01-held-and-copies`): their numbers are taken by the scenarios of M11/08 (it has more scenarios in
the chapter); the new numbers are the next ones after the largest number of the sources of the chapter (M11/10 sc. 12), in the order of
the lesson M11, then of the scenario (the Architect's decision on the plans of the move 8–10, ADR-0083 addendum (14) item 14; the row of
`corrections-7.tsv` (historical correction record)). In total 10 scenarios / 106 steps: 41 from M11/08, 18 from M11/09, 5 from M11/05, 9 from M11/10, 11 — sc. 16 (the second pass of the coverage audit of P/06, Gemini), 7 — sc. 17 (ADR-0094 B6), 9 — sc. 18 (ADR-0094 B7), 4 steps of sc. 03 (ADR-0112 addendum (12) item 3), 1 step of sc. 03 (ADR-0112 addendum (13) item 10), 1 step of sc. 03 (the ADR reconciliation S23).

The function `resolve` without a stand is checked by the vector [`resolve`](../../vectors/resolve/README.md) (12 rows: 11 — the former sc. 03 of the acceptance of
M11/11); `families` of the door `/domain/keys` (N1.11) — by the vector [`key-families`](../../vectors/key-families/README.md) (12 rows:
one `id` in several manifests, the order; on the stand there is one manifest with `domain.keys`). The other scenarios of the sources are at the neighbours: M11/08 sc. 04 — [chapter 8.3](../../../08-domain/acceptance/3/README.md),
05 (the holder's page) — the lesson P/10, 06 — the vectors [`peer`](../../../common/vectors/peer/README.md); M11/09 — [chapter
8.4](../../../08-domain/acceptance/4/README.md), [8.5](../../../08-domain/acceptance/5/README.md) (11) and the vectors
[`may`](../../../common/vectors/may/README.md); M11/05 — [chapter 8.5](../../../08-domain/acceptance/5/README.md), [9.1](../../../09-agent/acceptance/1/README.md)
(13) and the vector [`assemble`](../../../08-domain/vectors/assemble/README.md); M11/10 — [chapter 8.8](../../../08-domain/acceptance/8/README.md),
[9.1](../../../09-agent/acceptance/1/README.md) (11), the vectors [`record`](../../../common/vectors/record/README.md),
[`ask-sig`](../../../common/vectors/ask-sig/README.md), [`follow`](../../../09-agent/vectors/follow/README.md).

## Stand

**Scenarios 01–03, 15** (from the READMEs of the acceptances of M11/08 and M11/10). The preparation is as in the acceptance of [chapter 8.3](../../../08-domain/acceptance/3/README.md)
(«Stand», «Preparation of each scenario»): the clusters `hold`, `m1`, `m2`, the catalogue `testsub`. The doors `holder`,
`holder@<cluster>`, `member <cluster> console`, `signer` and the directives `@domain`, `@person`, `@env`, `@start domain on`,
`@stop domain`, `@move` — the section «Domain stand» of the common acceptance README; the forwarding environment is there too (`CLUSTERS` of the consoles,
`DOMAIN_CONSOLE_URL` of the process `domain`, `SIGNER_URL` only at `hold`). The runner goes as the person `root` (chapter 8.4).

- `member hold console` is the console of the holder's cluster: `GET /domain` at it is also a forwarding (into the domain console of its own
  box by `view.url`).
- Scenario 02 sets up the domain only with `m1` (`@domain m1`): `m2` is not a member, it has no list.

**Scenario 16** (the second pass of the coverage audit of P/06, Gemini, `audit-coverage-gemini` 0a5ae79f9) — the stand of sc. 01–03, 15
(`testsub` declares `domain.shared`, as in the acceptance of [chapter 8.9](../../../08-domain/acceptance/9/README.md)).

**Scenarios 06, 13, 14** (from the READMEs of the acceptances of M11/05 and M11/09). The preparation is as in the acceptance of [chapter 8.5](../../../08-domain/acceptance/5/README.md)
(«Preparation»): the catalogue of each cluster is `testsub` and `testsub2`; on each cluster the controllers of both work, the worker
`w-1` of the manifest `testsub`, the worker `t-1` of the manifest `testsub2` (with the training writer of contributions — [chapter 8.5](../../../08-domain/spec/08.5-domain.norms.md) N5) and
the resource of its own server `srv-<cluster>`; before the steps the store of each cluster has the counter `testsub` `c1-<cluster>` and the shelf
`testsub2` `sh1` `{zone: z1, server: srv-<cluster>}`. `console2` at `member` is the prefix `/testsub2`.

- The person `root` with the password `w2c test root password` is created at `@install domain` (`domain first-admin`, the directive
  `@admin`). The runner goes as this person by default: `admin` `*` at the domain door and in the grants row of each cluster of the stand.
- Scenario 06 — the key families door at `m1`. The stand has no training worker on the domain, so the families of `testsub` are empty.

An equal answer time to an unknown and to a wrong one, the journal and the limit band by the peer address (not by a header) — by reading.

`answer too large`, `answer broke off`, the recognition of `X-Operator: console` by the role and the journal `domain.forwarded` the stand does not
cause: they are checked by reading (N5 of the chapter). How the runner passes the environment and restarts the console and the agent of a cluster with
a variable (`@env`) — «Implementation decides» item 2 of the chapter.

## scenarios.tsv

The format is the dictionary of the «Stand» of the common acceptance README and the section «Domain stand»; the expectation is a subset of fields. In total 10
scenarios / 106 steps.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

| Sc./step | Sleep | Reason |
|---|---|---|
| 15/2 | 35 s | time before an action: the domain has gone quiet — after the admission of members the next backup copy is not earlier than `BACKUP_EVERY` 30 s, it is brought by the pass of the agent 5 s; `$r` is the last copy (the silence is not to be observed: «no more copies will arrive» is an absence) |

The scenarios of the chapter have no other sleeps.
