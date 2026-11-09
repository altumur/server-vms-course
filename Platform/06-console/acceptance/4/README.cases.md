# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/4/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

The norm of the chapter is [`06.4-console.norms.md`](../../spec/06.4-console.norms.md) N5. The scenarios were moved from the acceptance of
M10/08 (stage B, ADR-0083 addendum (1): without a change of
behaviour); the numbers of scenarios and steps are the former ones. Scenarios 05 (a request with a holder) and 07 (the append) of M10/08 are in
[the acceptance of chapter 3.6](../../../03-worker/acceptance/6/README.md); 01, 02, 08 of M10/08 (the objects door, the events query, the paths
of the resource) are in [the acceptance of P/05](../../../05-resource/acceptance/README.md). The preparation, the comparison and the evidence below are the parts
of the former README needed by these scenarios; the forms of foreign doors belong to their owners ([P/05](../../../05-resource/spec/05-resource.norms.md) —
the doors of the resource, [P/01.1](../../../01-store/spec/01.1-store.norms.md) — the store).

There is no controller and no workers: the scenarios do not start them. There are no third-party daemons and timers able to start a holder in scenario 04.

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors): the doors `console`, `console2` (sc. 07, 08, 11, 12), `resource`, `store` (with `@as` — sc. 08, 09), `admin` (sc. 11, 12), the directives `@until`, `@sleep`, the request form `@header`. In total 9 scenarios / 120 steps; all HTTP (with @until and @key).

`Idempotency-Key` and `@key(N)` — per the dictionary. The body of the repeat
04/3 is the same as the original one. The presence of the header at /marks does not create a promise

In scenario 03 the event queries filter kind=mark: the audit of the creation of a unit does not become
an extra element of the expected array. An expectation of a single code does not require an empty body.

$rid from queued in 04 is a string substituted without change into the store path.
