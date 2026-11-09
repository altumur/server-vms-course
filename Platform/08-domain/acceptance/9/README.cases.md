# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/9/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

[`08.9-domain.norms.md`](../../spec/08.9-domain.norms.md) N5. Scenario 01 was moved from the acceptance of M11/11 (stage B, ADR-0083
addendum (1): without a change of behaviour); the numbers of the scenario and of the steps are the former ones; scenario 07 is the coverage audit of P/08 (the numbers 02–06 belong to the scenarios of M11/11 in neighbouring acceptances). The other scenarios of M11/11 are lesson P/10 (02 — the list of
alarms; the vectors `alarms` — 04), [the acceptance of chapter 9.1](../../../09-agent/acceptance/1/README.md) (05; 06 → 14) and the cluster console (the vectors [`resolve`](../../../06-console/vectors/resolve/README.md) — 03, chapter P/06.7); lesson P/10 is [the acceptance](../../../10-domain-console/acceptance/README.md)
and the vector [`alarms`](../../../10-domain-console/vectors/alarms/README.md). The forms of foreign doors are for their
owners.

(steps 02, 14) is a door of the domain console (lesson P/10, P/10-14), the content of `delivery` is `view.shared` of this chapter (N1.6); the document
is taken by the member's agent ([chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md), P/09.1-12); the value at the read `GET /domain/shared/testsub` (steps 11–13, 16) is the cluster console
(the OpenAPI of lesson 6 `GET /domain/shared/{sub}`); the units `c5`, `c6` (steps 09, 10) are the units door P/06.1.
