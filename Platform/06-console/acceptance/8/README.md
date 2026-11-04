# Acceptance P/06.8 — cluster folders (stand)

This English text is the source; the Russian translation `ru/acceptance/8/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`06.8-console.norms.md`](../../spec/06.8-console.norms.md) Н5. The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
In total 12 scenarios / 189 steps.

**There is no dry run by an implementation.** The scenarios are composed by reading the norms and the contract; `index` and other values of the store the scenario binds from the answer and does not compute in advance. The chapter is part of the rights increment and waits for the credit of increment B.

## Preparation

A console with the manifests `testsub` (declares `display.tree.folders: true`) and `testsub2` (does not declare it: it stands in sc. 03 as a subsystem without folders), there is no domain, the requests come from one caller with the needed rights. Each scenario begins with
an empty store on its own instance: `GET /folders` reconciles the whole list, so a foreign folder changes the expectation. A door without a prefix is the console. The role of the door `store` is `console`: it reads `platform/*` and the rows of the subsystems ([P/02.5](../../../02-installer/spec/02.5-installer.norms.md) Н1.4).

The folder reaper on the stand works with the period of the norm `FOLDERS_REAP_EVERY` 60 s: scenarios 06 and 10 wait for it with `@until 90`. This deadline is an upper bound: the step ends as soon as the sign is there. There are no sleeps (`@sleep`).

## scenarios.tsv

The format is [the dictionary of directives and doors](../../../common/acceptance/README.md#dictionary-of-directives-and-doors). A subset of fields, `$имя`, `@any`, `@big(N)`, `@header`, `@key`, `@as`, `@until`, `ASSERT` — as there. The record `{"items": null}` means: there is no row.

- `$f`, `$g` and the like bind the folder id from the answer `201`. The scenario does not set the value of the id: the console chooses 128 random bits.
- `$i`, `$j` bind `index`: they are compared only for equality. The `index` of the answer of `PUT` equals the index of the row in the store — sc. 02 steps 4–5.
- Sc. 03 steps 11–14: the key `testsub/counters/<1007 байт>` is exactly 1024 bytes: the unit row is representable, the membership key is longer than the limit — `400 bad member`. The neighbour at 989 bytes gives a membership key of exactly 1024 bytes and passes.
- Sc. 04: a chain of eight folders — `FOLDERS_DEPTH_MAX`; the ninth — `too deep`. Steps 13–16: a tombstone of an ancestor in the middle of the chain.
- Sc. 05 step 8: a write over a tombstone goes through the batch door, because `PUT` and `DELETE` of such a folder answer 404.
- Sc. 09: the boundary `FOLDERS_PER_UNIT_MAX`: the eighth folder passes, the ninth — 400, the deletion of a unit at the boundary removes all eight.
- Sc. 10 step 5: the store door removes the unit row bypassing the console door, as the controller does by `placement.ends`: `testsub` has no such deadline, so the scenario itself does the write, by the role `console`, as in sc. 19 of chapter 6.1. Until the pass of the reaper the member hangs; the scenario waits only for the end of the window, because the moment of the pass is not subject to the stand.
- Sc. 11: a batch of a unit with a folder. Steps 6–7 and 12 — a refusal by `no chain`, `no membership`, `parent gone`; `$ip` is the index of the parent, `$t` is the index of its tombstone.
- Sc. 12 steps 12–14: a row with an empty `name` is written by the store door by the role `console`, bypassing the folder door. A folder with this id is neither live nor dead: `garbled` in the list, 503 for a single one.

## What is checked by reading

| Subject | Why not a scenario |
|---|---|
| the strict race «чтение — запись»: the guards of the unit and of the chain, the guard of the absence of the membership row, `412 parent moved` | the HTTP stand does not open the window between the read and the batch; the sequential orders — sc. 07, 08, 11 |
| the rights of the table of Н3 «folder rights», the rights of a folder row in a batch | a domain stand with grants is needed: the filter by the row `folder:` — the acceptance of chapter 8.4 sc. 33, the rights of the folder door — by reading |
| `FOLDERS_MEMBERS_MAX`, `FOLDER_ROW_MAX`, the numbers of Н1.3 | the boundary requires thousands of units; the numbers are computed |
| an unconfirmed read: 503, the reaper removes nothing | a refusal of the store on the read of a particular key is needed |
| a member from a second subsystem | `testsub2` holds `display.tree.group_by`, and `display.tree.folders` next to it is forbidden; the code is one, only the prefix of the reference differs |

The plan of the rights scenarios, when the norm `may` is entered (a domain stand, `@person`, grants rows — as in [the acceptance of chapter 8.4](../../../08-domain/acceptance/4/README.md)):

1. a person with `edit` on a unit without `admin`, the unit is in a folder: `DELETE` of the unit — 200, the folder is without it;
2. the creation of a unit with a folder row without `admin` over the folder — 403, nothing is written;
3. a write of a folder without `admin` over it — 403; with `admin` on `folder:<предок>` — 200;
4. adding and removing a unit with `admin` over the folder, without `admin` on the unit — 403;
5. deleting a folder with a role row `folder:` on a descendant without `admin` on `*` in `sub` of this row — 403.

## corrections.tsv

The log of corrections of the scenarios of the chapter, the format is as in the neighbouring chapters.
