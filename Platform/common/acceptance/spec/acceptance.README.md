# P/AC — instructions for a judge engine

This English text is the source; the Russian translation `ru/acceptance/spec/acceptance.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

This file is for the agent (or person) who writes the shared judge engine from this lesson.

## Task

Write one engine that executes the targets of the registry from the data of the specification: tables, inputs and stand protocols. The engine contains no literal lesson, target or package name, and it does not know the internal API of any implementation.

## Inputs and their priority

- The canon is the [norms](acceptance.norms.md).
- The [common stand](../README.md) gives the stand, the dictionary of directives and doors, the seam protocol and the expectation forms.
- The [profile contract](../PROFILE.md) gives the shape of `acceptance.yaml`, `assembly.yaml`, the command ownership, the substitutions, the adapters and the vector envelope.
- The [vector wire form](../../vectors/wire.md) and `wire.tsv` give the vector rows; `consumers.tsv` gives their owners.
- The [target registry](../forms/targets.README.md) gives the targets and their requirements; `forms/targets.routing.tsv` gives the engine family, the acceptance directories, the scenario selection, the body mode, the initial role, the admitted unnamed fields and the rights file of the stand store of each target.
- The README of a chapter's acceptance gives its preparation and special comparison rules.
- [The production qualification of the store](../../../01-store/qualification/README.md) gives the groups, budgets and measurements of N6 of the norms.

The generation input of the engine contains no code of products or of an existing judge, no inventory of its behaviour, no corpus of verdicts and no mutants.

## What to create

One engine with these parts: the readers of the tables; the plan with the dry listing; the runner of the stand by the dictionary; the callers of the adapters and the vector command; the probes of the production qualification (N6 of the norms); the classification of results; the report.

## Order of work

1. Read the tables first: the scenario tables, the vector forms and the registry. Reject a table outside its form before any stand starts.
2. Build the plan and the dry listing from the registry; the inventory it prints is what a result is compared with.
3. Start the stand by the dictionary and the profiles. Apply the readiness rule of the common stand; stop the whole process group; leave no process after a target.
4. Execute each step by its dictionary row and judge it by the expectation forms; the outcome of a step is a mismatch, or a class of N4, never a guess.
5. Keep what is secret out of the report.

## Results and mechanical checks

The engine produces a result per target and a report (N1.4, N1.5 of the norms). N5 of the norms names the mechanical checks that the generation loop applies; passing them does not prove correctness: code review and the comparison of verdicts do.
