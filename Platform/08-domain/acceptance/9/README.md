# Acceptance P/08.9 — the shared document of the domain

This English text is the source; the Russian translation `ru/acceptance/9/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors) and its
section [«Domain stand»](../../../common/acceptance/domain-stand.md#domain-stand) (the doors `holder`, `member`, the directives `@domain`, `@person`). The norm of the chapter is
[`08.9-domain.norms.md`](../../spec/08.9-domain.norms.md) N5. The forms of foreign doors are for their owners.

## Stand

The preparation is as the acceptance README of [chapter 8.3](../3/README.md) («Preparation of each scenario»: the clusters `hold`, `m1`,
`m2`, the catalog `testsub`), with a declaration of the shared in `testsub`:
- `domain.shared: [step, marks, {rounds}]`;
- `step` is an `int` with `inherit: 1`;
- `marks` is a `list` with `inherit: []`, `merge: union`.

The runner goes as the human `root` (the first administrator — chapter 8.4, the directive `@person`).

Neighbours on the stand: the edit is passed to the process by the domain console (`holder PUT`, lesson P/10, chapter 8.0); `GET /domain/shared`
is a door of the domain console (lesson P/10, P/10-14), the content of `delivery` is `view.shared` of this chapter (N1.6); the document
is taken by the member's agent ([chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md), P/09.1-12); the value at the read `GET /domain/shared/testsub` is the cluster console
(the OpenAPI of lesson 6 `GET /domain/shared/{sub}`); the units are the units door P/06.1.

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors)
and the section «Domain stand»: a subset of fields, `~` is a substring. In total 4 scenarios / 46 steps.

A subset of expect does not replace the check of the full HTTP form of the OpenAPI of the lesson: check the mandatory fields, types, Content-Type.

## Kit seams

[3 CALL seams](seams.tsv) (judge-only: the seams of chapter 8.9; they check P/08.0-R058, P/08.9-R043, P/08.9-R067, P/08.9-R074 and P/08.9-R078) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.
