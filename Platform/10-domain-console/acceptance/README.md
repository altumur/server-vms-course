# Acceptance P/10 — the domain console

This English text is the source; the Russian translation `ru/acceptance/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand, the dictionary of directives and doors — [the common acceptance README](../../common/acceptance/README.md#dictionary-of-directives-and-doors) and its
section [«Domain stand»](../../common/acceptance/README.md#domain-stand) (the door `holder` — the domain console on `hold`, the doors
`member`, the directives `@domain`, `@person`, `@stop agent`, `@start agent`; the plan of lesson 10 В10). The norm of the lesson is
[`10-domain-console.norms.md`](../spec/10-domain-console.norms.md) Н5. The scenarios were moved from the acceptances of М11/08 (sc. 05) and
М11/11 (sc. 02) (stage B, ADR-0083 addendum (1): without a change of behaviour); the numbers of the scenarios and the steps are the former ones; sc. 06–09 —
the coverage audit of P/10 (audit-kimi 290ae7697), the numbers — after the largest number of the sources (М11/08 sc. 05); sc. 10–16 —
the second pass (Gemini, the section below); sc. 17–19 — after it (the section «Scenarios 17–19»). Scenario 04
of the acceptance of М11/11 (the command `alarms`) — the vector [`vectors/alarms`](../vectors/alarms/README.md) (27 rows). The other scenarios
of М11/08 and М11/11 — at their chapters (the cluster console — chapter P/06.7; the shared document — [the acceptance of chapter 8.9](../../08-domain/acceptance/9/README.md);
the agent side — [the acceptance of chapter 9.1](../../09-agent/acceptance/1/README.md)). The forms of foreign doors — their owners.

## Stand

The preparation is as the acceptance README of [chapter 8.3](../../08-domain/acceptance/3/README.md) («Preparation of each scenario», from
М11/03: the clusters `hold`, `m1`, `m2`, the catalogue `testsub`); at sc. 02 — with a declaration of the shared in `testsub`, as the acceptance README of
[chapter 8.9](../../08-domain/acceptance/9/README.md):
- `domain.shared: [step, marks, {rounds}]`;
- `step` — `int` with `inherit: 1`;
- `marks` — `list` with `inherit: []`, `merge: union`.

The runner goes as the human `root` (the first administrator — chapter 8.4, the directive `@person`).

- **Scenario 02.** The agent `m2` is turned off longer than `LOST_AFTER`: in the delivery it is `silent`, in the alarm list — the member is `silent` and
  the silence row (step 05); a window not by the grammar and `since > until` — 400 (steps 06, 07). Turned on, it takes the document,
  and the list is full again (steps 09, 10).
- **Scenario 05** — the doors of the holder page (the norms Н1.7). The calls of the module in the mode `domain` are checked by the test of the module at its
  owner ([P/07](../../07-console-module/spec/07-console-module.norms.md) Н1.6), not by this acceptance.
- **Scenario 06** — there is no view (the norms Н1.2а, Н1.2б, Н1.2в, Н1.2е, Н4 `no domain here`): `@start domain` without `@install domain` —
  the process `domain` without a signer row does not lead the holder pass and does not write the view ([P/08.10](../../08-domain/spec/08.10-domain.norms.md)
  Н1.7 `no_signer`), there are no traces of the domain in the store of `hold` — the gate `open`: the runner calls from the loopback without a token, the identity —
  `operator` (`@person`: «до домена заголовка нет»; step 2 confirms it). Every door of the view — 404 `no domain here`;
  at the door of the subsystem rows — after the manifest checks (`testsub` has `domain.ref`, `counters` are its rows).
- **Scenario 07** — the view and the shadow exist but do not read (Н1.2а, Н1.2б, Н1.2е, Н4 `unavailable`): the process `domain` is stopped
  (the only writer of `domain/view` and `domain/shadow` — the data catalogue), then the object is spoiled by `@spoil object` — 503
  `unavailable`, not 404, at `GET /domain`, `/domain/members`, `/domain/testsub/counters`, `/domain/shared`; then the shadow — 503
  at `/domain/shadow`. The step does not ask for the topology: its door reads the row `domain/topology`, Н1.2в does not name an unreadable view.
- **Scenario 08** — a break of the passing (Н1.3 `pass`, Н4 «слова договора пересылки `answer`»): the process `domain` is stopped,
  the domain console is alive; an edit (`PUT /domain/topology`) and the door of people (`GET /domain/users` — `GET` is passed too, Н1.3а) — 502
  `did not answer` («сеть», [the forwarding contract](../../common/contracts/forwarding.md) «Forwarding is one function» `answer`);
  its own read door (`GET /domain`) answers. After `@restart domain` and the readiness of the process (the login `signer`, as sc. 04 of the acceptance of
  [chapter 8.10](../../08-domain/acceptance/10/README.md)) the same edit — 200 `rev: 1`: the broken one is not applied.
- **Scenario 09** — silence (Н1.3 `pass`): the process `domain` is frozen (`@on hold @freeze domain`, the pause ≈ the term «Ожидание»
  of the row `PUT /domain/topology` — 5 s, the freeze limit 120 s) — 502 `did not answer` (no answer within `FORWARD_WAIT`). The edit under
  silence is one the process would refuse (`via: {m1: m1}` — 409 «through itself», P/08.3 Н1.2): should it read it after `@thaw`,
  there is no write; the control — the edit `base_rev: 0` gives `rev: 1`. That the 502 does not come earlier than the term — by reading (the acceptance does not measure
  the answer time).

The refusal `not in the directory` (a manifest without `domain.ref`, Н1.2а) — by reading: the manifests of the stand (`testsub`, `testsub2`)
have `domain.ref`.

The neighbours on the stand: the edit of the shared document (sc. 02 step 03) is passed by the domain console to the process `domain` (the norms Н1.3;
the execution — [chapter 8.9](../../08-domain/spec/08.9-domain.norms.md) Н1.3); the content of `delivery` (steps 04, 09) —
`view.shared` of chapter 8.9 (Н1.6), the door `GET /domain/shared` — this lesson (P/10-14); the document is taken by the agent of the member
([chapter 9.1](../../09-agent/spec/09.1-agent.norms.md)); step 11 — the agent signature at `/events` of the cluster console of the member
([the agent signature contract](../../common/contracts/agent-signature.md), the gate P/06.3; the plan of lesson 10 В6: the step is not split).

The stand does not call the alarm page (the front once a second, the urgent report, `truncated`): the stand has no training subsystem that
raises alarms. This is checked by the vector `alarms` and by reading.

## Coverage audit of P/10, the second pass (Gemini)

Sc. 10–16 — the second pass of the coverage audit of P/10 (audit-coverage-gemini 798e11a44), the numbers — after sc. 09. The rows of the store of
`hold` are written by the runner through the door `member hold store` (`admin.sock`); it cannot delete a row under `domain/` (P/01.2 Н1.3
`never`: delete under `domain/` — only by the domain role), therefore the stand does not create «no row» — an unreadable row is written by a `put`
not by the form of its family, and the former one — by a `put` of a value by the form. The writer of these rows is the process `domain` (the data catalogue); before
the spoiling it is stopped (`@on hold @sigterm domain`, as sc. 07), the domain console is alive and answers itself.

- **Scenario 10** — the door of the subsystem rows and `HEAD` (Н1.2, Н1.2а): `HEAD` of a read door — the same code without a body (steps 2, 3);
  `?cluster=` empty or twice — 400 (steps 4, 5; twice — with one value too); no manifest, `rows` not its own — 404 (steps 6, 7;
  `testsub` has no `door.pass`); `?part=` empty, not by the grammar of a section (`4096`), together with `?cluster=` — 400 (steps 8–10);
  the section `0000` is empty — 200 `[]` (step 11). `?cluster=` not a member — sc. 06 step 6 of the acceptance of [chapter 8.1](../../08-domain/acceptance/1/README.md).
- **Scenario 11** — the topology and the placements do not read (Н1.2в, Н1.2г, Н4 `unavailable`): `domain/topology` out of form — 503,
  not `rev 0` (steps 4, 5); the counter `domain/placement` (after `@domain` — `rev 1`: the raise at start, P/08.6 Н3, as sc. 01 step 2
  of the acceptance of [chapter 8.6](../../08-domain/acceptance/6/README.md)) out of form — 503, the former one — 200 again (steps 6–9); no record or
  no manifest — 404 (steps 10, 11); a record out of form (`cluster` empty, no fields) — 503, not 404 (steps 12, 13). No row
  `domain/topology` — sc. 15 step 2 of the acceptance of [chapter 8.3](../../08-domain/acceptance/3/README.md) (C10-TOPOLOGY-ABSENT-01);
  no counter (C10-PLACEMENT-ABSENT-01) — by reading: after `@domain` it exists, the stand cannot delete it.
- **Scenario 12** — the shared document and the member list do not read (Н1.2б, Н1.2е, Н3 `alarms`, Н4 `unavailable`): the pointer
  `domain/shared` out of form — 503, not `doc: null` (steps 3, 4); the row `domain/member-rows/3723` (the part of the member `hold`, Н1.2) out of form with a readable view — 503 at
  `GET /domain/members` and at the whole door `GET /domain/alarms`, not an empty list (steps 6–8; step 5 — the control before the spoiling).
- **Scenario 13** — the grammar of the alarm window (Н1.8 `door`, the gate-and-pass contract «Numeric query parameters»,
  C06-EVENTS-QUERY-LEXEME-162-01, A12): `1e3`, `-1`, `%2B1` (= `+1`), `%201` (= « 1»), `1_000` at `since` and `1e10` at `until` — 400
  `refused` with its own `detail`; each value without the grammar check would give a window `since ≤ until` (200), the refusal is only
  the grammar; `since` twice — 400; `%31` and `%32` (= `1`, `2`) — accepted: the window `[1, 2]`, no rows (step 9).
- **Scenario 14** — the mark `reported` does not read (Н3 `alarms`, C10-REPORTED-OUTCOME-1D6): the process `domain` (the writer of the mark) is
  stopped, the mark of `m1` is spoiled by `@spoil object` — the door 200, `m1` — `unreadable` without `known_until` and `silent_since`, the other
  member — not `unreadable`. A generation `reports/<rev>` not by the `sha256` of the mark (C10-ALARMS-INPUT-01) — by reading: the key of the generation carries
  the `rev` of the mark, and the directive `@on … @spoil object` takes the key as it is.
- **Scenario 15** — before the gate (Н2, Н1.4 «принять консолью», Н1.5 `session`): without a token (`@person -`) a path with a segment
  `.` or `.%2E` — 404 `not a domain route`, not 401 (steps 3, 4); an incoming `X-User: root` is stripped — without a token 401, `/session`
  is anonymous, without `user` (steps 5, 6); with the token of `root` an incoming `X-User: forged` does not change the identity, `/session` carries the grants
  `domain/grants/domain` (`[{cap, scope}]`, the first administrator, step 8). `X-Operator: console` — by reading (until the TLS stand).
- **Scenario 16** — the rule «Unreadable row» of the gate (Н1.5, Н4 `unavailable`): `domain/disabled`, `domain/revoked`
  (`no_revocations`), `domain/grants/domain`, `domain/keys` out of form — 503 `unavailable`, not 401/403; after each (except
  the last) the former value by the form — `GET /domain` 200 again: each 503 is from its own row. The former values: `names` —
  `"[]"` (none is disabled), `jtis` — `""` (an empty string by the form of the contract `keys`; the row `domain/revoked` without revocations may also be absent), the grants of the domain door — the row of the first administrator. No row
  `domain/keys` with a trace of the domain (`shut`) — by reading: the stand cannot delete it.

## Scenarios 17–19

Sc. 17 — ADR-0094 B4 (the version of the row at the read doors); sc. 18, 19 — the doors `GET /domain/<sub>/kept/<имя>` and
`GET /domain/relays/<ретранслятор>` (the journal `journal/corrections.tsv`, 2026-11-02); the numbers — after sc. 16.

- **Scenario 17** — the version of the row at the read doors (Н1.2; [P/08.0](../../08-domain/spec/08.0-domain.norms.md) Н1.9): the index of `versions` and of the record equals the index of the store row (steps 10–13); steps 14–18 go through the door `member m1 console`: `If-Match`, `Idempotency-Key` and `ETag` pass the cluster console and the domain console ([the forwarding contract](../../common/contracts/forwarding.md) `pass`, `answer`). Step 14 waits (`@until 30`) until `GET /domain/topology` through the door `member m1 console` gives 200 `rev: 1`. The stand does not bind the value of `ETag`: it judges the quotes of the header.
- **Scenario 18** — the door of a `kept` row (Н1.2а; [P/06.2](../../06-console/spec/06.2-console.norms.md) Н1.4): the row
  `domain/testsub/ledger` is written by the runner through the door `member hold store` (step 2), `ledger` is an element of `domain.kept_read` of the manifest
  `testsub`. The mask in depth: `plain_secret`, the envelope `enc:` (`sealed`) and the field `token_secret` in a JSON value (`inner`) —
  `"***"`, `note` — as is (step 6); the family `badges/` and an undeclared name — 404 (steps 7, 8); through the door `member m1 console` —
  the same mask through forwarding (step 9). Without an identity (`@person -`) — 401 (step 11); `ann` (`view` only at the cluster `m1`,
  step 4) — 403 also on an undeclared name: the right before 404 (steps 12, 13).
- **Scenario 19** — the door «who is behind the relay» (Н1.2а; [P/08.3](../../08-domain/spec/08.3-domain.norms.md) Н1.2): a domain
  with the members `m1`, `relay`, the topology `via: {m1: relay}` — `rev: 1` (steps 1, 2); `GET /domain/relays/relay` — `members: ["m1"]`
  (step 3), nobody behind `m1` — `rev: 0`, `members: []` (step 4), not a member — 404 (step 5). `ann` without grants — 403 also
  on a non-member: the right before 404 (steps 8, 9); through the door `member m1 console` — the same `relay`, `members` through forwarding (step 10); without an identity
  (`@person -`) — 401 (step 12).

## scenarios.tsv

The format — [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../common/acceptance/README.md#dictionary-of-directives-and-doors)
and the section «Domain stand»: a subset of the fields, `~` — a substring, `@file` — the bytes of a file. In total 16 scenarios / 163 steps.

The subset of expect does not replace the check of the full HTTP form of the OpenAPI of the lesson: check the required fields, the types, the Content-Type.

## `journal/corrections.tsv`

The journal of the AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`. The rows of the journals of the acceptances of М11/08 and М11/11 about
the scenarios and the inputs of the lesson — as they are (the plan of the move of lesson 10, § 3 «corrections.tsv»: from М11/08 — the row 2026-10-18 about
sc. 05; from М11/11 — R41-16, № 52–54, «класс record и сумм», `04-alarms 11–14`, `03-resolve 11, 04-alarms 15`,
`04-alarms 6`; the paths of the old rows — `11/…`, `NN-<имя> <шаг>` — are resolved by [id-map](../../common/id-map.tsv)); the rows about
sc. 04 — also in «Журнал источника» of the vector `alarms`; the last row — the move.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

There are no sleeps: the waits for events — `@until` by a sign (sc. 02 steps 04, 05, 09, 10; sc. 07 step 3; the readiness of the process `domain` —
sc. 08 step 7, sc. 09 step 5; the raise of the placement counter at start — sc. 11 step 2; the topology at the console of `m1` — sc. 17 step 14).
