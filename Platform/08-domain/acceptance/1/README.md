# Acceptance P/08.1 — the domain view and the shadow report (stand)

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/domain-stand.md#domain-stand) (a stand of several clusters). The norm of the chapter is
[`08.1-domain.norms.md`](../../spec/08.1-domain.norms.md) N5. In total 6 scenarios / 39 steps.

The same views without a stand are the vectors [`view`](../../vectors/view/README.md) (the canonical package README lists the cases).
The doors `GET /domain`, `/domain/<sub>/<rows>`, `/domain/shadow`, through which the stand reads the view and the report, are doors of the domain
console (lesson P/10, [N1.2a](../../../10-domain-console/spec/10-domain-console.norms.md)); the chapter sets the norm for their content.

## Preparation

As the acceptance README of [chapter 8.3](../3/README.md) («Stand», «Preparation of each scenario»):
the runner brings up three clusters on one machine — `hold`, `m1`, `m2`; each has its own empty store,
its own `{data}`, its own role sockets and ports of the console and the resource, its own ring (P/06.2 N1.2), the manifest catalogue — only `testsub`
(`domain.ref: name`); the console, the controller and the worker `w-1` of `testsub`, the resource of its own server (`srv-hold`, `srv-m1`, `srv-m2`).
There are no units. There is no domain: the directive `@domain` of the first step of each scenario sets it up. The domain name is `acme`; the recovery
file is `{recovery}` in the instance directory.

Do not speed up the clocks: LOST_AFTER 45 s, REPORT_EVERY 5 s, MARK_REFRESH 22.5 s, SHADOW_STALL 60 s; the `@until` terms are taken with
a margin. At the door `holder` the runner sets `Idempotency-Key` on `PUT` too (assignments — chapter 8.6).

## scenarios.tsv

The format is the dictionary of the «Stand» and the domain dictionary; the expectation is a subset of fields.

Selected scenarios use real reports of agents in `domain/members/<member>/reports/<rev>` and the holder's view (the vectors `view`).

## Kit seams

[3 CALL seams](seams.tsv) (judge-only: the seam table; it checks P/08.1-R070, P/08.1-R165, P/08.1-R169, P/08.1-R236 and P/08.1-R243) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.
