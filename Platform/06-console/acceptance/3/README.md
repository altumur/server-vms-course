# Acceptance P/06.3 — the guard and the console session

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../../common/acceptance/README.md#словарь-директив-и-дверей).
The norm of the chapter is [`06.3-console.norms.md`](../../../spec/06.3-console.norms.md) Н5. The scenario was moved from the acceptance of
М10/09 (stage B, ADR-0083 addendum (1): without a change of
behaviour); the numbers of the scenario and of the steps are the former ones. The other scenarios of М10/09 are the acceptance of [chapter 6.5](../../5/README.md). The forms of foreign
doors belong to their owners; the common codes and the parsing of a console request are [chapter 6.5](../../../spec/06.5-console.norms.md) Н2.

## Preparation

The session door of the console `testsub` (root) with `testsub2` mounted, without workers, without a domain (the console is open, the runner
calls from the loopback). Before the scenario, stop the processes of the previous one, create separate empty row/object stores and
clear the variables/the replay memory. Load the unchanged testsub and testsub2 by the section «Stand» of the common acceptance README;
root is testsub, the second is available under /testsub2. There is no domain, the calls come from the loopback. The background controller/resource/worker do not
run. The third manifest of the stand of chapter 6.5 (`probe-x`) is not needed by this scenario.

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../../common/acceptance/README.md#словарь-директив-и-дверей):
a door without a prefix is the console; a subset of fields, `@header` in the expectation. In all, 1 scenario / 5 steps.

A subset expect does not replace the check of the full HTTP form of the OpenAPI of the lesson: check the mandatory fields, the types, Content-Type,
the special headers. A successful open `/session` contains `login_url`, even when the TSV checks only `open`.

Steps of the reconciliation of python and go М10/6–11 (2026-10-18):
- **03/3–5** — the answer of `DELETE /session` carries two `Set-Cookie` headers (it removes the cookies `w2c_token` and `w2c_glass`, C34).
  The expectation `@header` looks for a substring in each value of a repeated header.

Step 03/1 — `login_url` without `LOGIN_URL` is `/api/login` (reconciliation 2 of the clean room of М10, faa988b0); `server_time` is `@time`,
`timezone` is the default `UTC`: the stand does not set `TIMEZONE` (ADR-0094 B6).

## Evidence outside TSV

The domain login, closed `grants`, `via` of a proven identity, the order of `identity`, `need` before the body, Origin by the cookie, the log
`access.denied`, the emergency login and the debug identity are checked by a separate stand (the domain stand: the acceptance P/08.4, sc. 14 of chapter 6.7) and by a module test, not by this TSV
(the norms of the chapter, Н5, «Проверяются чтением»).

Additional check of the class of errors of run 36 (Kimi), by reading: without a domain every path, including the open one and /session,
is closed outside the loopback; after an identity the cookie checks Origin before the grant. Check the emergency login.

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models
of the author are not a performed stand test.

## corrections.tsv

The log of AI corrections (ADR-0080 addendum 1): `date`, `sample`, `fix`, `languages`. The rows of the log of the acceptance of М10/09 about scenario 03
were moved here as they are; the whole log of М10/09 is at the beginning of the log of [the acceptance of chapter 6.5](../../5/corrections.tsv) (review analysis
of stage B 6–7, № 18).
