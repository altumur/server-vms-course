# Acceptance P/08.9 — the shared document of the domain

This English text is the source; the Russian translation `ru/acceptance/9/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors) and its
section [«Domain stand»](../../../common/acceptance/README.md#domain-stand) (the doors `holder`, `member`, the directives `@domain`, `@person`; the plan of lesson 8 V5). The norm of the chapter is
[`08.9-domain.norms.md`](../../spec/08.9-domain.norms.md) Н5. Scenario 01 was moved from the acceptance of М11/11 (stage B, ADR-0083
addendum (1): without a change of behaviour); the numbers of the scenario and of the steps are the former ones; scenario 07 is the coverage audit of P/08 (the numbers 02–06 belong to the scenarios of М11/11 in neighbouring acceptances). The other scenarios of М11/11 are lesson P/10 (02 — the list of
alarms; the vectors `alarms` — 04), [the acceptance of chapter 9.1](../../../09-agent/acceptance/1/README.md) (05; 06 → 14) and the cluster console (the vectors [`resolve`](../../../06-console/vectors/resolve/README.md) — 03, chapter P/06.7); lesson P/10 is [the acceptance](../../../10-domain-console/acceptance/README.md)
and the vector [`alarms`](../../../10-domain-console/vectors/alarms/README.md). The forms of foreign doors are for their
owners.

## Stand

The preparation is as the acceptance README of [chapter 8.3](../3/README.md) («Подготовка каждого сценария», from М11/03: the clusters `hold`, `m1`,
`m2`, the catalog `testsub`), with a declaration of the shared in `testsub`:
- `domain.shared: [step, marks, {rounds}]`;
- `step` is an `int` with `inherit: 1`;
- `marks` is a `list` with `inherit: []`, `merge: union`.

The runner goes as the human `root` (the first administrator — chapter 8.4, the directive `@person`).

- **Scenario 09** — versions and the replay memory ([chapter 8.0](../../spec/08.0-domain.norms.md) Н1.9; Н1.3 steps 1a–3). The first write carries `base_rev: 0` (step 2). `If-Match` with `base_rev`: different, an index next to it, neither one nor the other — 400 `field: /base_rev` (steps 6–8), equal — a write (step 9). Step 5: `row` is a pointer. Step 14: the condition before the content.
- **Scenario 01.**
  - Step 05 — an edit with an outdated `base_rev` and an unknown subsystem: the revision 409 before the content 400 (Н1.3 steps 3, 4).
  - Steps 06–08 — content refusals: there is no subsystem and the name is not shared, the type of a field, the schema of the document `rounds` (`every` ≥ 1). Step 06
    names two reasons in one refusal; the expectation checks both substrings.
  - `c5` is a counter with its own `step` and `marks`, `c6` is without them.
  - Step 15 removes the domain value (`null`), and `c6` again takes the `inherit` of the manifest (step 16).
- **Scenario 07** (the coverage audit of P/08, audit-kimi 1e9929d51) — the refusals of an edit in the order of Н1.3:
  - steps 2–3 — the body form (step 2, before `base_rev`): `shared.testsub` as a string (A9) and a body that is not JSON (`@raw`) — 400 `refused`,
    `detail` begins with the words «the edit is {base_rev:»;
  - step 4 — `rounds` with the name `token_key_secret` inside an element (A6): the seal refusal among the content refusals in one 400
    (the schema `rounds` rejects the extra field too — the expectation judges the seal substring; the name at the beginning of the reason is not compared);
  - steps 5–8 — the first edit 200, then the pointer `domain/shared` is rewritten past the writer by the form of Н1.2 `pointer`
    (`object` — `domain/shared-docs/rev-1`, `rev` 1, `term` 1, JCS), but with a `sha256` of zeros: the object exists, the bytes are wrong —
    an edit with `base_rev` 1 — 503 «the shared document at rev 1 does not read: nothing is written» (step 5, A7), the pointer
    is as before (nothing is written).

Neighbours on the stand: the edit is passed to the process by the domain console (`holder PUT`, lesson P/10, chapter 8.0); `GET /domain/shared`
(steps 02, 14) is a door of the domain console (lesson P/10, P/10-14), the content of `delivery` is `view.shared` of this chapter (Н1.6); the document
is taken by the member's agent ([chapter 9.1](../../../09-agent/spec/09.1-agent.norms.md), P/09.1-12); the value at the read `GET /domain/shared/testsub` (steps 11–13, 16) is the cluster console
(the OpenAPI of lesson 6 `GET /domain/shared/{sub}`); the units `c5`, `c6` (steps 09, 10) are the units door P/06.1.

## scenarios.tsv

The format is [the dictionary of directives and doors of the «Stand» of the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors)
and the section «Domain stand»: a subset of fields, `~` is a substring. In total 4 scenarios / 46 steps.

Sc. 08 (the coverage audit of P/08, the second pass of Gemini, the draft G10 `e32df6f8b`, rewritten): the removal of the last field of a subsystem (`null`) removes the
subsystem itself too — `doc.shared` is exactly `{}` (Н1.3 `order` step 5: «пустая подсистема — снять»); the pointer `domain/shared` is spoiled
past the door (`doc` is not JSON) — the edit 503 `unavailable`, the row is as before (the outcomes of `domain/shared`, G-38). Not taken from the draft:
a replay of `null` of an absent field «без новой `rev`»: step 5 gives a new document with `rev + 1` for each edit, the shared document has no rule
«то же содержимое — без записи» (a question of the norm, if it is needed).

A subset of expect does not replace the check of the full HTTP form of the OpenAPI of the lesson: check the mandatory fields, types, Content-Type.

## `journal/corrections-9.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample`, `fix`, `languages`. The log of the acceptance of М11/11 is moved here
as a whole, the rows as they are (the plan of lesson 8 § 3 «Журналы»: the log of the source goes into each directory that takes its scenarios;
the paths of the old rows — `11/…`, `NN-<имя> <шаг>` — are resolved by [id-map](../../../common/id-map.tsv)); the last row is the move.

## Kit seams

[3 CALL seams](seams.tsv) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.
