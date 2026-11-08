# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/2/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

The file `probe` (the manifest row
265 bytes, the mark 74, the view row `87 + 890` = 977; the numbers are after `worker.exec`, ADR-0091 addendum (5), finding of cammeta-c-go I02-G01):

| Ceiling `{row_ceiling}` | Installation | Expectation |
|---|---|---|
| 976 | `probe` | code 2, nothing is written: there is no row, no view and no mark; stderr names the file and the key of the view |
| 977 | `probe` | code 0, rev 1, the view is the vector `example-sections` |
| 977 | `probe`, then 9 times `@view-delete` and `probe` | code 2 at the last installation, nothing is written: the row and the mark are rev 9, there is no view (the directive removed it); stderr names the file and the key of the view |

All three lines are in `puts-ceiling.tsv`. The third one, `ceiling_rev_10`, is the boundary rev 9 → 10 of the view weight (the P/02 lesson review, S4):
each `@view-delete` and `probe` is a new revision (case 03 `view_deleted`), so the view of rev 9 weighs exactly 977 and is written, and the
view of rev 10 weighs 978 (one more digit of `rev`). The installer checks the weight with the final new rev before any write (chapter 2.3 N3
step 14a), so the last installation refuses before the parts, the row and the mark. The same boundary reached through a `cas` conflict of two
installers (the full catalogue read with rev 8, another installer writes rev 9 first) is checked by reading: the table installs sequentially.
