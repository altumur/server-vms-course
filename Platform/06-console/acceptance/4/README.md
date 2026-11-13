# Acceptance P/06.4 — requests and events of the console

This English text is the source; the Russian translation `ru/acceptance/4/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
The norm of the chapter is [`06.4-console.norms.md`](../../spec/06.4-console.norms.md) N5. The forms of foreign doors belong to their owners ([P/05](../../../05-resource/spec/05-resource.norms.md) —
the doors of the resource, [P/01.1](../../../01-store/spec/01.1-store.norms.md) — the store).

## Preparation of each scenario

The scenarios are independent. Before each one stop all the processes of the previous
scenario and wait for them, create isolated directories/ports and an empty store: rows, objects,
the id memory of the store, the POST claims of the console, the asked accounting and the commands marks are absent.
Clear the event tree, the mirrors and the index cache, the variables and the replay keys of the runner.
Install the current testsub from the common testdata with its service mark using administrative
rights. There are no units and no user rows yet. The preparation is not a transfer of the state of
the previous scenario and not a check of the installer.

Start the store, a new console testsub and the resource srv-a per the section «Stand» of the common acceptance README. Their doors must be ready;
the resource is registered and available to the console before the first step. All the processes of this box
use one BOX_ID and server=srv-a; each new process gets a new instance.
There is no controller and no workers: the scenarios do not start them. There are no third-party daemons and timers able to start a holder in a selected scenario.
platform/mirror and platform/space are not set; requests for release and for a copy are not prepared.

console — the door of the console testsub from the loopback, access to operations and units is allowed;
resource — the door of the resource srv-a with an admissible identity; store — the door of the store with reading of
testsub/ and objects/testsub/. If the deployment uses TLS, issue the corresponding
certificates and roles per P/02.4 N1.6 (`w2c-ca.sh issue <server> <role>`, the kit `kit`) and the address rule of P/02.4 N1.6;
these scenarios do not replace the check of TLS refusals.
Do not accelerate the deadlines and parameters of testsub: valid_for=30, most_valid=600; the ordinary
ticks of the holder and the reaper are expected, settle=60 by default.

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors): the doors `console`, `console2`, `resource`, `store` (with `@as`), `admin`, the directives `@until`, `@sleep`, the request form `@header`. In total 9 scenarios / 120 steps; all HTTP (with @until and @key).

`Idempotency-Key` and `@key(N)` — per the dictionary. The body of the repeat
is the same as the original one. The presence of the header at /marks does not create a promise
of replay memory for a note.

The runner must not end a whole scenario earlier than the total budget of its steps. After
the last step wait for the stop of all the created processes, then delete the state.

## Comparison

The forms of expectation — per the dictionary.
An expectation of a single code does not require an empty body.

A repeat of a variable inside expect compares its temporary value.
The directives are not sent to the server as HTTP. The full answer is additionally checked by the contract of its owner:
the store — P/01.1, the units — chapter 6.1, the doors of the resource — P/05 N2, the other doors — N2 of the chapter. In particular, answered
with @any in the TSV is still bound to be a full mark of one of the three forms of AnsweredMark.

## Evidence outside TSV

These are tasks for the implementation/stand, not checks already performed. Objects, events, the index, wait, streams, retention/holds and
free space are in the acceptance of P/05; the holder and the mark are in
the acceptance of chapter 3.6.

Reading of the branches and the schema confirm only the corresponding order/form. Timers,
processes, file barriers, network breaks and the cryptographic identity require separate
observations.

The freshness boundary of a door row at the merge is `≤ LOST_AFTER` ([the observation contract](../../../common/contracts/observation.md)): a resource whose door row changed exactly 45 s ago is alive — the boundary is checked by the vector
[`fresh-age`](../../../common/vectors/fresh-age/README.md), not by a step (a controlled clock is needed).

## Additional checks

This is a subject of a manual check of the specification and of a future check of an implementation. The prepared requests, the reading and the finite models of the author are not a performed stand test.

## Additional source checks

For the ordinary substitution of requests.key strings are needed; :int accepts a finite number, bool is excluded, truncation towards zero and the decimal notation are common.

This is a subject of a check of the norms/data and of a future stand, not a performed test of an implementation.

The bounds of :int per P/02.1: binary64, the modulus is not more than 2^53−1; bool/null/string/non-numeric/non-finite/out of bounds — 400, not a language cast. Check ±0.5, ±7.9, ±(2^53−1), 1e16, 1e21 and the canonical decimal result without an exponent.
