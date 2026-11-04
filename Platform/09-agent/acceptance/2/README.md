# Acceptance P/09.2 — the relay mode (stand)

This English text is the source; the Russian translation `ru/acceptance/2/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand, the dictionary of directives and doors — [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Стенд домена»](../../../common/acceptance/README.md#domain-stand) (the stand of several clusters; formerly — the М11 dictionary of the acceptance README
of М11/01; the plan of the move of lesson 8, В5). The norm of the chapter is [`09.2-agent.norms.md`](../../spec/09.2-agent.norms.md) Н5. Scenarios
02–04 were moved from the acceptance of М11/04 (stage B, ADR-0083 addendum (1): without a change of behaviour); the numbers, names and steps are
the former ones, the number 01 is empty (sc. 01 of М11/04 — the acceptance of [chapter 8.3](../../../08-domain/acceptance/3/README.md) sc. 15). In total 5
scenarios / 62 steps (sc. 06 — the coverage audit of P/09, the second pass, below). There are no inputs: the inputs `accept-*` were removed from sc. 06 of М11/04 — the same cases are in the package
[`accept`](../../../common/vectors/accept/README.md).

The division (the appendix of the plan of the move of lesson 8): the outcome of all three scenarios is the door, the package and the relay pass. The neighbours on
the stand: the holder on the relay package and the knock ([P/08.3](../../../08-domain/spec/08.3-domain.norms.md) Н3 «the holder on `POST /api/relay/<ретранслятор>`»;
P/08.3-07, P/08.3-13), the acceptance and the topology (chapter 8.3), `join` and `domain/reached` of the agent of a member behind a
relay (chapter 9.1: P/09.1-05, P/09.1-21, P/09.1-24), the silence of a member in the view (chapter 8.1).

## Stand

The preparation is as the acceptance README of [chapter 8.3](../../../08-domain/acceptance/3/README.md) («Stand», «Подготовка каждого сценария»;
formerly — the acceptance README of М11/03), there are four clusters: `hold`, `m1`, `m2`, `relay`. The agent `relay` always opens
the relay door (`RELAY=1`, `{relay_port}`); the doors and the directives — the section «Domain stand» of the common acceptance README
(`@domain <кластеры>`, `@start agent <кластер> via relay`, `@stop agent`, `@cut relay`, `@mend relay`, `@clock`).
The topology is empty until the step that writes it.

## scenarios.tsv

The format is the dictionary of the «Стенда» and the section «Domain stand» of the common acceptance README; the expectation is a subset of the fields. `$fp2` is the fingerprint
of the stranger whom the holder learned of from a knock that came in a relay package.

- Sc. 02 steps 11–14 (the mutation check 2026-10-18): the relay checks the member signature — with the agent clock 400 s
  ahead the member behind the relay is `silent`, although the relay is alive; with the right clock — `ok` again.
- Sc. 02 steps 15–21: under `@cut relay` `domain/reached` does not grow. Step 16 binds `$c` — `as_of` of the holder view right
  after the cut; `ts` of the mark is the moment of the last answer of the holder (`domain_age` — Н1.4 of the chapter; `fresh` — chapter 9.1), not
  later than the cut, so step 21 compares `$t2` with `$c`, not with `$t1`: the former comparison of two reads caught the write, delayed by
  FRESH_EVERY, of the last value before the cut (the reconciliation of М11 01–04, sc. 04/02 step 20 of the mix).

- Sc. 05 `relay-moves` (DOM-AGENT-TURN-01, -02, the owner's consent 2026-10-26; chapter 9.2 Н1.1 `door`, P/09.1 Н1.13): two relay agents (`@start agent relay
  second`), `RELAY_URL` of the member `m2` — their doors in order; SIGTERM of the active relay agent — the waiting one takes the queue and
  opens the door, the member goes by the next address, the reports through the relay continue.

## Coverage audit of P/09, the second pass (Gemini)

- Sc. 06 `token-through-relay` (`audit-coverage-gemini` cc36de538, draft G05; Н1.1 `not_author`, Н2 `POST
  /api/tokens/<член>/…`; [the local token door contract](../../../common/contracts/local-token-door.md) `no_queue`).
  The preparation is as in sc. 02, steps 1–7. The placement `c1` (`cluster: m1`, `origin: m2`) — as in sc. 01
  of [the acceptance of chapter 8.7](../../../08-domain/acceptance/7/README.md). The request of the worker `m2` through the local door of its agent goes
  through the relay door to the holder and gets 200. Under `@cut relay` the holder does not answer the relay: the relay
  answers the member 502 `did not answer` or stays silent, and the local door of `m2` gives the worker 503 `unavailable`, not the 502
  of the relay. After `@mend relay` — again 200. The bytes of the request at the relay door and the 502 itself — by reading: the runner does not call the relay
  door.

## `journal/corrections-2.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`. The rows from before the move are from `corrections.tsv`
of the acceptance of М11/04 by `sample` (scenarios 02–04) and the rows without a scenario, at the beginning of the log, with the former paths and numbers (they are
resolved by [`id-map.tsv`](../../../common/id-map.tsv)); the rows of the inputs `accept-*`, sc. 01 and 06 are the history of the acceptance of chapter 8.3
(the plan of the move of lesson 8, § 3 «Журналы»; review analysis of stage B 6–7, № 18). Implementations and their runners check their own
result; this directory does not run them itself.

## Sleeps (`@sleep`, ADR-0080 addendum (17) item 4)

| Sc./step | Sleep | Reason |
|---|---|---|
| 02/17 + 02/19 | 70 + 15 s | absence: under `@cut relay` `domain/reached` does not grow; a new value would be written no later than `FRESH_EVERY` 60 s (chapter 9.1, `fresh`) after an answer by another road, and another road would open after `ROAD_QUIET` 15 s ([P/08.3](../../../08-domain/spec/08.3-domain.norms.md) Н1.3а) and the agent pass 5 s — no less than 80 s in all |
