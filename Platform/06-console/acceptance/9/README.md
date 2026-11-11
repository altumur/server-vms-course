# Acceptance P/06.9 — group operations (stand)

This English text is the source; the Russian translation `ru/acceptance/9/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The norm of the chapter is [`06.9-console.norms.md`](../../spec/06.9-console.norms.md) N5. The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
In total 2 scenarios / 8 steps.

**There is no dry run by an implementation.**

## Preparation

A console with the manifest `testsub`, it declares no operations. A door without a prefix is the console; the role of the door `store` is `console`. There are no sleeps.

## scenarios.tsv

The format is [the dictionary of directives and doors](../../../common/acceptance/README.md#dictionary-of-directives-and-doors). The scenarios check only what is executable without a declaration: the subsystem has no operation doors, rows do not appear, there is no rollback as a path.

## What is checked by reading

Scenarios of the plan table that the TSV does not run — by reading. The algorithms without a stand are checked by the vectors [`op-step`](../../vectors/op-step/README.md): `step_key` and the expected version along the chain of the root.



`retry-failed` uses the ordinary acceptance procedure. Conflicting memory CAS is existing 412 row moved with key/index and field /memory/cas, distinct from per-step expectedVersion; matching CAS permits 202. Unknown acceptance outcomes and cleanup retain the ordinary rules. There is no retry-admission CALL port among the current ports: this HTTP/IO binding must be proved by the actual ordinary operation setup, and is not counted as executed by a source or schema preview.
