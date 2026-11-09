# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

[`10-domain-console.norms.md`](../spec/10-domain-console.norms.md) N5. The scenarios were moved from the acceptances of M11/08 (sc. 05) and
M11/11 (sc. 02) (stage B, ADR-0083 addendum (1): without a change of behaviour); the numbers of the scenarios and the steps are the former ones; sc. 06–09 —
the coverage audit of P/10 (audit-kimi 290ae7697), the numbers — after the largest number of the sources (M11/08 sc. 05); sc. 10–16 —
the second pass (Gemini, the section below); sc. 17–19 — after it (the section «Scenarios 17–19»). Scenario 04
of the acceptance of M11/11 (the command `alarms`) — the vector [`vectors/alarms`](../vectors/alarms/README.md) (the current corpus). The other scenarios
of M11/08 and M11/11 — at their chapters (the cluster console — chapter P/06.7; the shared document — [the acceptance of chapter 8.9](../../08-domain/acceptance/9/README.md);
the agent side — [the acceptance of chapter 9.1](../../09-agent/acceptance/1/README.md)). The forms of foreign doors — their owners.

M11/03: the clusters `hold`, `m1`, `m2`, the catalogue `testsub`); at sc. 02 — with a declaration of the shared in `testsub`, as the acceptance README of

- **Scenario 05** — the doors of the holder page (the norms N1.7). The calls of the module in the mode `domain` are checked by the test of the module at its

Scenario 05 compares the JavaScript response bytes with the same [P/07 console.js](../../07-console-module/module/console.js) as the cluster console, at the existing synchronous `/platform/console.js?v=1`. The unchanged requests, statuses and headers remain mandatory. This byte-publication check does not replace the module-owner tests of UI language and date rendering; no locale fetch, new route or version is introduced.

The neighbours on the stand: the edit of the shared document (sc. 02 step 03) is passed by the domain console to the process `domain` (the norms N1.3;
the execution — [chapter 8.9](../../08-domain/spec/08.9-domain.norms.md) N1.3); the content of `delivery` (steps 04, 09) —
`view.shared` of chapter 8.9 (N1.6), the door `GET /domain/shared` — this lesson (P/10-14); the document is taken by the agent of the member
([chapter 9.1](../../09-agent/spec/09.1-agent.norms.md)); step 11 — the agent signature at `/events` of the cluster console of the member
([the agent signature contract](../../common/contracts/agent-signature.md), the gate P/06.3; the plan of lesson 10 V6: the step is not split).

Sc. 10–16 — the second pass of the coverage audit of P/10 (audit-coverage-gemini 798e11a44), the numbers — after sc. 09. The rows of the store of

the spoiling it is stopped (`@on hold @sigterm domain`, as sc. 07), the domain console is alive and answers itself.

## Scenarios 17–19

Sc. 17 — ADR-0094 B4 (the version of the row at the read doors); sc. 18, 19 — the doors `GET /domain/<sub>/kept/<name>` and
`GET /domain/relays/<relay>` (the journal `corrections.tsv` (historical correction record), 2026-11-02); the numbers — after sc. 16.


For debug its local guards are valid and the writer is in the ordinary serving state, so the independent writer refusal is 401.
