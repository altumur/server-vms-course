# P/07 — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/07-console-module.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

This file is for the agent (or person) who writes or checks the console module from the lesson. The explanation of «why» is
`ru/07-console-module.md` (for people, not in the export).

## Task

The console module is a common module: the published files of [P/06.5 Н1.1](../../06-console/spec/06.5-console.norms.md) `module`; they
are served byte for byte, not written. The lesson norms what the module calls (Н1.4) and what it gives the shell (Н1.5); an implementation
of the console does not write it, the owner of the specification keeps its bytes by the norms, the generator checks the completeness of the contract
by rewriting (P/06.5 Н1.1 `module`: a check of the completeness of the contract, not a way to implement). The norms of the lesson are
P/07-01…08.

## Inputs and their priority

The canon is the [norms](07-console-module.norms.md). The doors the module calls are the [contract of lesson
P/06](../../06-console/spec/06-console.api.openapi.yaml); the publication of the module and the version `?v=1` are observed by sc. 01 of [the acceptance of chapter
6.5](../../06-console/acceptance/5/README.md); the lecture (`ru/07-console-module.md`, for people, not in the export) explains the reasons; the description of the surface is
[`КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md`](../../../КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md) (not a norm; where it differs from Н1.5, the lesson is right). On a
contradiction, record the place and a counterexample and pass it to the Specification; the instructions introduce no new refusal. The internal types,
functions and structure of the module remain the choice of its owner.

## What to create

- Calls of the module only from the closed list of Н1.4, in the order `order`; the doors of the holders — only to the shell through `where()`.
- The contract with the shell, Н1.5: `version`, `objects`, `api`, `may`, `events`, `where`, `words`, `adds`, `cards`, `commands`.
- The domain section — the late layer Н1.6 (lessons 8, 10; the doors — lesson P/10 and chapter 6.7).

## Order of work

1. Connect the closed may. Tell apart a replay of one request and a new action; allow an automatic replay only by
   the memory of the owner. For an unknown PUT/table — a read first (Н1.5). The three states of the session by which `may` judges —
   [chapter 6.3](../../06-console/spec/06.3-console.norms.md) Н1.3 `session`.
2. Check the module/shell separately: the jsdom test of the owner of the specification `Source/tests/console` by the subjects of Н5 (review
   analysis of stage A 6–7, № 31). An implementation neither reads nor runs the jsdom tests of Н5: they check the published bytes
   of the module at the owner of the specification; the proof of an implementation is the bytes of the module as they are and the load of `?v=1` (sc. 01 of the acceptance
   of chapter 6.5; C07-F01).
3. The library for the shell turns the absent field `door` of the HTTP answer `Where` into `null` (Н1.5 `where`). Check
   this level separately from HTTP: a `Where` without a trustworthy door has no field `door` — the check of the door is in
   [the instructions of P/06](../../06-console/spec/06-console.README.md), chapter 6.5.

## Traps of the language and the library

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| Н1.5 | A key cache by method/path/body merges two clicks | A key per logical action; a new call is independent. |

The published module keeps a key per action and replays by itself only the `POST` of units, and `may` without grants gives `true` only
with `open: true` («Implementation decides» item 1 of the norms is closed, the Architect's decision of 2026-10-21); the evidence is the jsdom tests by the table of Н5.

## Boundary checks

The module calls nothing outside Н1.4 `reads`/`writes`; the paths of `never` (`/{sub}/requests`, `/api/backup`, `/resources`, tables outside
`servers.show`, the doors of the holders) do not appear among the requests intercepted by the jsdom test, neither on mounting nor on
polling. The parts of the list that the domain introduces are checked in the mode `domain` of the late layer (Н1.6).

## Done when

For every id (`P/07-01…08`) a concrete piece of evidence is given: a jsdom test by the subjects of Н5 or a reading with a reason; for P/07-07, P/07-08 — the acceptance tests of the module of implementations, not jsdom on the witness (the limit of the witness, ADR-0112 addendum (23)).
The compatibility of the common console module is a separate comparison of bytes (sc. 01 of the acceptance of chapter 6.5) and a reading by the norms Н1.4, Н1.5.

On a discrepancy — compare the norm, the answer form and the scenario. Record the exact input and outcome; do not carry a difference of an implementation
silently into the canon. The decision is reflected in the norm, the contract, the instructions and the affected acceptance; the origin of the error and
the check of the related class — in the log of the Specification.
