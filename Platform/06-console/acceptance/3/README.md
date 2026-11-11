# Acceptance P/06.3 — the guard and the console session

This English text is the source; the Russian translation `ru/acceptance/3/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`06.3-console.norms.md`](../../spec/06.3-console.norms.md) N5. The forms of foreign
doors belong to their owners; the common codes and the parsing of a console request are [chapter 6.5](../../spec/06.5-console.norms.md) N2.

## Preparation

The session door of the console `testsub` (root) with `testsub2` mounted, without workers, without a domain (the console is open, the runner
calls from the loopback). Before the scenario, stop the processes of the previous one, create separate empty row/object stores and
clear the variables/the replay memory. Load the unchanged testsub and testsub2 by the section «Stand» of the common acceptance README;
root is testsub, the second is available under /testsub2. There is no domain, the calls come from the loopback. The background controller/resource/worker do not
run. The third manifest of the stand of chapter 6.5 (`probe-x`) is not needed by this scenario.

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors):
a door without a prefix is the console; a subset of fields, `@header` in the expectation. In all, 1 scenario / 5 steps.

A subset expect does not replace the check of the full HTTP form of the OpenAPI of the lesson: check the mandatory fields, the types, Content-Type,
the special headers. A successful open `/session` contains `login_url`, even when the TSV checks only `open`.

## Evidence outside TSV

The domain login, closed `grants`, `via` of a proven identity, the order of `identity`, `need` before the body, Origin by the cookie, the log
`access.denied`, the emergency login and the debug identity are checked by a separate stand (the domain stand: the acceptance P/08.4 and of chapter 6.7) and by a module test, not by this TSV
(the norms of the chapter, N5, «Checked by reading»).

Additional checks, by reading: without a domain every path, including the open one and /session,
is closed outside the loopback; after an identity the cookie checks Origin before the grant. Check the emergency login.

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models
of the author are not a performed stand test.



A current GET /session response with via=ticket has until equal to the proven ticket exp and grants of its person by gate-and-pass. It does not add a POST /session admission or rights. A source/schema control is separate from executing a real ticket/session exchange.
