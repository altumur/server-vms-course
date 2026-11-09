# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/8/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

<!-- original-mixed-case-paragraph -->

A console with the manifests `testsub` (declares `display.tree.folders: true`) and `testsub2` (does not declare it: it stands in sc. 03 as a subsystem without folders), there is no domain, the requests come from one caller with the needed rights. Each scenario begins with

<!-- original-mixed-case-paragraph -->

- `$i`, `$j` bind `index`: they are compared only for equality. The `index` of the answer of `PUT` equals the index of the row in the store — sc. 02 steps 4–5.

<!-- original-mixed-case-paragraph -->

| the strict race «read — write»: the guards of the unit and of the chain, the guard of the absence of the membership row, `412 parent moved` | the HTTP stand does not open the window between the read and the batch; the sequential orders — sc. 07, 08, 11 |
| the rights of the table of N3 «folder rights», the rights of a folder row in a batch | a domain stand with grants is needed: the filter by the row `folder:` — the acceptance of chapter 8.4 sc. 33, the rights of the folder door — by reading |

<!-- original-mixed-case-paragraph -->

The separately declared added seam rows are s05-delete-explicit-folder-conflict, s06-delete-explicit-membership-conflict, s07-delete-explicit-consistent, s08-delete-explicit-folder-only. Their exact interventions and real observations use the existing ports described by the forms README. All earlier seam cells and process scenario bytes are preserved; source selection/translation does not execute an adapter or IO.
