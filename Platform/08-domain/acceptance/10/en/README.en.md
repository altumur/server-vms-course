# Acceptance P/08.10 — the queue and the price

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are [the common acceptance README](../../../../common/acceptance/README.md), the section [«Domain stand»](../../../../common/acceptance/README.md#стенд-домена)
(a stand of several clusters; formerly the dictionary of the М11 README of the acceptance М11/01). The norm of the chapter is
[`08.10-domain.norms.md`](../../../spec/08.10-domain.norms.md) Н5. The scenarios were moved from the acceptance of М11/12 (04, 05) (stage B,
ADR-0083 addendum (1): without a change of behaviour); the numbers, the names of the scenarios and the steps are the former ones. The other scenarios of М11/12: 01, 03,
06 — [the acceptance of chapter 9.1](../../../../09-agent/acceptance/1/README.md), 02 — [chapter 8.3](../../3/README.md) (17) (the plan of the move of lesson 8, the appendix). Scenarios 07, 08 are
the coverage audit of P/08; 09, 10 — the coverage audit of P/08, the second pass of Gemini. There are no vectors: the chapter introduces no new functions.

## Stand

The preparation is as the «Подготовка каждого сценария» of the acceptance of [chapter 8.3](../../3/README.md) (formerly the acceptance README of М11/03,
«Подготовка каждого сценария 01–09»), the catalog `testsub`. The doors `holder`, `member`, `resource`, `signer`, `signer2` and
the directives `@domain`, `@start domain`, `@start agent`, `@install domain`, `@start domain second`, `@on`, `@freeze`, `@thaw` are the dictionary of the
«Domain stand» and the common dictionary of directives of the common acceptance README. The runner goes as the human `root` (chapter 8.4). The clock is not accelerated: `LOST_AFTER` 45 s,
`REPORT_EVERY` 5 s, `MARK_REFRESH` 22.5 s, `TURN_TERM` 45 s.

- **Scenario 04.** The second copy of the process `domain` on `hold` is a standby one: the login answers 503 `standby`. The first is stopped by
  SIGTERM and gives up the queue — the second takes it at the next `TURN_RENEW` (one killed by SIGKILL would give it up only by `TURN_TERM`);
  its login is 200, the reports of `m1` are accepted again, the view is full. `@until` repeats the login: it does not change rows (the token is not
  stored). The path `TURN_TERM` is sc. 08, the refusal of the guard — by reading.
- **Scenario 05.** `SERVERS_MAX`: the runner puts `domain/member-count` with `servers` 499 as a row
  through `admin.sock`; the acceptance of `m1` gives member 500 — 200, the acceptance of `m2` — 409 `too many servers`. Both sides of the ceiling.

- **Scenario 07** (the coverage audit of P/08, audit-kimi 1e9929d51). `ENTRY_MAX` over all Entries (Н1.5 `every_entry`): the stand
  is brought up by hand, like sc. 05 (`@domain` would accept `m1` itself); `domain/member-rows/<раздел>` is rewritten as a row through `admin.sock` —
  the record `f01991` of the section of `m1` (3232) with a `by` of 1300 characters `x` (Entry 1336 bytes JCS > 1240; the field `by` is not limited by the form, the limit is a check of the
  writer). The acceptance of `m1` — 409 «… would exceed 1240 bytes» (the name in the text is not compared: step 6 «принять члена» names
  the accepted one, Н1.5 — the member with the large Entry), `m1` is not written; the leaving of `f01991` (the record without it passes the check) — 200; the acceptance of
  `m1` — 200.
- **Scenario 08** (the coverage audit of P/08). The freshness of the queue (Н1.7 `fresh_turn`): without agents, two copies of `domain`; the first
  is frozen by `@on hold @freeze domain#1` (SIGSTOP; the freeze limit of 120 s is the dictionary of the «Stand»). After 20 s the second is still
  standby: the last renewal of the first is no earlier than `TURN_RENEW` (10 s) before the freeze, and an unchanged version is no more than 30 s, with
  a margin against `TURN_TERM` 45 s. Then the second takes the queue (`@until 60`: no later than 45 s from the first look at the version plus
  the `TURN_RENEW` of its polling — about 65 s from the freeze in the worst case). After `@thaw` the door `signer` leads to the first copy
  (alive, number 1) — 503 `standby` (`@until`: the norm does not limit the answer window of the door); the second answers 200. During the
  freeze the door `signer` is not touched — a request to the frozen copy would hang.
- **Scenario 09** (the coverage audit of P/08, the second pass of Gemini, the draft G11 `e32df6f8b`, rewritten). `ENTRY_MAX` over all Entries at the administrator's edit
  `Entry.ca` (Н1.5 `every_entry`): the stand is brought up by hand without the agent of `m1`; `domain/member-rows/<раздел>` is rewritten through `admin.sock`
  — `hold` as before, `f01991` of 1336 bytes JCS (like sc. 07) and `m1` without a key (Entry `{by, how, since}` — of the form). `POST
  /domain/members/m1/ca` — 409 «… would exceed 1240 bytes», `m1` has no `Entry.ca`. Then `f01991` with five `revoked_keys`
  (`11…11`…`55…55`, 64 hex; Entry 392 bytes) — the same edit of `m1` passes and trims the `revoked_keys` of the foreign Entry to the four
  last ones (Н1.5 `revoked_keys`, `every_entry`).
- **Scenario 10** (the coverage audit of P/08, the second pass of Gemini). An unreadable queue at the start (Н3 «очередь процесса domain» step 1): `@stop domain`, the row
  `domain/signer-turn` is rewritten through `admin.sock` not of the form (`{turn: "1"}` — no `holder`), `@start domain` —
  the process is standby: the login 503 `standby` (`@until`: the process is coming up), the row is as before — it does not rewrite it.

Not taken from the draft G11: `on_accept` with a large foreign Entry — not 409 (C08-CA-ENTRY-MAX-01) — the agent needs a TLS kit
(`W2C_TLS_DIR`, the inputs of the acceptance of chapter 8.3), and the stand does not read the log `domain.member.ca.refused` (by reading); 503 `standby`
at the other doors of the process without `domain/signer` (C08-TURN-WITHOUT-SIGNER-01) — the dictionary has no door of the process `domain` not on
`hold` (`signer` is only `hold`); its answer on the merits is `POST /api/take`, sc. 16 of [the acceptance of chapter 8.8](../../8/README.md).

By reading: `whole too large` (Н1.5), a holder `url` of several nodes and an unknown outcome of a write with the guard (Н1.7),
the price (Н1.9).

## scenarios.tsv

The format is the dictionary of the «Stand» of the common acceptance README and its section «Domain stand»; the expectation of `@carry` is `ok <JSON>`.

In total 6 scenarios / 56 steps.

## corrections.tsv

The log of AI corrections (ADR-0080 addendum 1): `date`, `sample`, `fix`, `languages`. The rows from before the move are from `corrections.tsv`
of the acceptance of М11/12: about the scenarios of the chapter (04, 05) and without a scenario — at the beginning of the log, as a whole, with the former paths and numbers (they
are resolved by `Platform/common/id-map.tsv`). Implementations and their runners check their own result; this directory does not
run them itself.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

Waiting for an event is `@until`: sc. 04 steps 3 (the second copy is standby), 7 (the second took the queue after the SIGTERM
of the first), 8 (a new report of `m1` is accepted), 9 (the view is full); sc. 05 step 6 (both members knock); sc. 07 step 5 (`m1` knocks);
sc. 08 steps 4, 9, 11 (standby, the taking of the queue, standby after the thaw). Sleeps:

| Sc./step | Sleep | Reason |
|---|---|---|
| 08/7 | 20 s | absence: the frozen copy holds the queue while its version is younger than `TURN_TERM` by the clock of the second — the second does not take the queue earlier (step 8 — 503 `standby`); 20 s is less than `TURN_TERM` − `TURN_RENEW` (35 s) with a margin for the steps |
