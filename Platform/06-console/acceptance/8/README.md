# Acceptance P/06.8 — cluster folders (stand)

This English text is the source; the Russian translation `ru/acceptance/8/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`06.8-console.norms.md`](../../spec/06.8-console.norms.md) N5. The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors).
In total 12 scenarios / 189 steps.

**There is no dry run by an implementation.** The scenarios are composed by reading the norms and the contract; `index` and other values of the store the scenario binds from the answer and does not compute in advance. The chapter is part of the rights increment and waits for the credit of increment B.

## Preparation

A console with the manifests `testsub` (declares `display.tree.folders: true`) and `testsub2` (does not declare it: it stands in sc. 03 as a subsystem without folders), there is no domain, the requests come from one caller with the needed rights. Each scenario begins with
an empty store on its own instance: `GET /folders` reconciles the whole list, so a foreign folder changes the expectation. A door without a prefix is the console. The role of the door `store` is `console`: it reads `platform/*` and the rows of the subsystems ([P/02.5](../../../02-installer/spec/02.5-installer.norms.md) N1.4).

The folder reaper on the stand works with the period of the norm `FOLDERS_REAP_EVERY` 60 s: scenarios 06 and 10 wait for it with `@until 90`. This deadline is an upper bound: the step ends as soon as the sign is there. There are no sleeps (`@sleep`).

## scenarios.tsv

The format is [the dictionary of directives and doors](../../../common/acceptance/README.md#dictionary-of-directives-and-doors). A subset of fields, `$name`, `@any`, `@big(N)`, `@header`, `@key`, `@as`, `@until`, `ASSERT` — as there. The record `{"items": null}` means: there is no row.

- `$f`, `$g` and the like bind the folder id from the answer `201`. The scenario does not set the value of the id: the console chooses 128 random bits.
- `$i`, `$j` bind `index`: they are compared only for equality. The `index` of the answer of `PUT` equals the index of the row in the store — sc. 02 steps 4–5.

## What is checked by reading

| Subject | Why not a scenario |
|---|---|
| the strict race «read — write»: the guards of the unit and of the chain, the guard of the absence of the membership row, `412 parent moved` | the HTTP stand does not open the window between the read and the batch; the sequential orders — sc. 07, 08, 11 |
| the rights of the table of N3 «folder rights», the rights of a folder row in a batch | a domain stand with grants is needed: the filter by the row `folder:` — the acceptance of chapter 8.4 sc. 33, the rights of the folder door — by reading |
| `FOLDERS_MEMBERS_MAX`, `FOLDER_ROW_MAX`, the numbers of N1.3 | the boundary requires thousands of units; the numbers are computed |
| an unconfirmed read: 503, the reaper removes nothing | a refusal of the store on the read of a particular key is needed |
| a member from a second subsystem | `testsub2` holds `display.tree.group_by`, and `display.tree.folders` next to it is forbidden; the code is one, only the prefix of the reference differs |

## Static deletion profile and exact entity bytes (ADR-0127 C2)

Before a folder-enabled profile is installed, use the existing P02.3 manifest put entry and effective Status.max_body/max_value, then its finite-profile validator before every installation write, including unchanged. The owned 13 form/arithmetic witnesses are Platform/02-installer/forms/finite-profile.cases.json; missing/H/multiplicity/provenance negatives need the Architect's separate judge and do not become passing from JSON Schema alone. The actual implementation's complete descriptors and mixed-packet coverage must be proved separately. Declare a sufficient existing body_limit/row_ceiling for the actual stand; no acceptance.yaml key is invented and AssemblyError is not an installer refusal.

The 6 codec witnesses in ../../forms/deletion-body-witnesses.json count whole compact UTF-8 entities: 1048575/1048576/1048577, extra LF, alternative escaping and the own 1380972-byte counterexample. The padded cases use V=1048576 rather than default 524288; the sufficient whole-profile test is distinct from one favorable packet's size. Check actual emitted target/done/auxiliary requests and Content-Length or decoded chunk data when proving IO; HTTP framing is excluded. This source addition performs no such store/console run, changes no existing scenario/seam or native command, and does not introduce a mutation-time DELETE refusal.


ADR-0129(17): a unit deletion and explicit folder/memberof rows in the same batch must agree on the deletion consequences. A retained deleted unit or restoring membership gives existing 400 no membership with field at the conflicting writes row before any target mutation. Consistent explicit rows are used once; missing automatic consequences, their full size and guards remain ordinary. No silent body rewrite or full-folder traversal is permitted. The separate Z10 over-limit unreadable branches remain unchanged.


The separately declared added seam rows are s05-delete-explicit-folder-conflict, s06-delete-explicit-membership-conflict, s07-delete-explicit-consistent, s08-delete-explicit-folder-only. Their exact interventions and real observations use the existing ports described by the forms README. All earlier seam cells and process scenario bytes are preserved; source selection/translation does not execute an adapter or IO.
