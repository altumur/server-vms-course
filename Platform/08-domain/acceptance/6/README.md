# Acceptance P/08.6 — placement and kept edits (stand)

This English text is the source; the Russian translation `ru/acceptance/6/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/domain-stand.md#domain-stand) (a stand of several clusters). The norm of the chapter is
[`08.6-domain.norms.md`](../../spec/08.6-domain.norms.md) N5; [the contract](../../spec/08-domain.api.openapi.yaml),
the lecture (`ru/08-domain.md`, for people, not in the export). In total 12 scenarios / 261 steps.

The `If-Match` condition of the units door, by which the agent applies an edit, is in the acceptance of
[P/06.1](../../../06-console/acceptance/1/README.md). The doors `GET /domain/placement`, `/domain`, `/domain/<sub>/<rows>`,
through which the stand reads placements, the view and the units, are doors of the domain console (lesson P/10, [the forwarding contract](../../../common/contracts/forwarding.md) «Domain doors»; [N1.2a, N1.2d](../../../10-domain-console/spec/10-domain-console.norms.md)); the chapter normates their content.

## Preparation

As the acceptance README of [chapter 8.3](../3/README.md) («Stand», «Preparation of each scenario»): the runner brings up three clusters on one machine — `hold`, `m1`, `m2`; each has its own
empty store, its own `{data}`, its own role sockets and console and resource ports, its own ring (P/06.2 N1.2), a manifest catalog of
only `testsub` (`domain.edit: [start, labels]`, `domain.ref: name`); the console, the controller and the worker `w-1` of `testsub`, the resource
of its own server (`srv-hold`, `srv-m1`, `srv-m2`). There are no units. There is no domain: it is set by the directive `@domain` of the first step of each
scenario. The domain name is `acme`; the recovery file is `{recovery}` in the instance directory.

- `store` of `member <cluster>` is the store door of the cluster through `admin.sock` (observation of the domain rows:
  `domain/placed*` of the members, `domain/pending/m1` of the holder).
- The clock is not accelerated: LOST_AFTER 45 s, REPORT_EVERY 5 s, MARK_REFRESH 22.5 s, VIEW_EVERY 3 s; the deadlines of `@until` are taken with a margin.
- At the door `holder` the runner sets `Idempotency-Key` for `PUT`/`DELETE` too; `@key(N)` repeats the key of step `N`.

## scenarios.tsv

The format is the dictionary of the «Stand» and the dictionary of the domain; an expectation is a subset of fields. `$id` is the id of the kept edit from the 202 answer.

Selected steps also observe the side of the member's agent (the copies `domain/placed*`, the application of an edit
through the units door) — items of [chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md) (P/09.1-07, -08) refer to them; the outcome of the scenario is the placement and the holder's edit.

## Placement counter after the start

The process `domain`, at its start and at each new taking of the queue `domain/signer-turn` — before the first answer to an agent — raises
the counter `domain/placement` by 1 (P/08.6 N3).

## Kit seams

[3 CALL seams](seams.tsv) (judge-only: `acceptance/6/seams.tsv`; they check P/08.6-R066, P/08.6-R073, P/08.6-R079, P/08.6-R081, P/08.6-R082, P/08.6-R203 and P/08.6-R228) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.
