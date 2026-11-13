# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/2/README.cases.md` is derived from it.

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

The file `probe` (the manifest row
265 bytes, the mark 74, the view row `87 + 890` = 977):

| Ceiling `{row_ceiling}` | Installation | Expectation |
|---|---|---|
| 976 | `probe` | code 2, nothing is written: there is no row, no view and no mark; stderr names the file and the key of the view |
| 977 | `probe` | code 0, rev 1, the view is the vector `example-sections` |
| 977 | `probe`, then 9 times `@view-delete` and `probe` | code 2 at the last installation, nothing is written: the row and the mark are rev 9, there is no view (the directive removed it); stderr names the file and the key of the view |

All three lines are in `puts-ceiling.tsv`. The third one, `ceiling_rev_10`, is the boundary rev 9 → 10 of the view weight:
each `@view-delete` and `probe` is a new revision (case 03 `view_deleted`), so the view of rev 9 weighs exactly 977 and is written, and the
view of rev 10 weighs 978 (one more digit of `rev`). The installer checks the weight with the final new rev before any write (chapter 2.3 N3
step 14a), so the last installation refuses before the parts, the row and the mark. The same boundary reached through a `cas` conflict of two
installers (the full catalogue read with rev 8, another installer writes rev 9 first) is not judged in this lesson: it needs the store of another lesson (the stage of the system); the table installs sequentially.

### Original passage 2

| № | Case | What it checks | Norm |
|---|---|---|---|
| 01 | `first` | the first installation of `testsub`: the row, the view and the mark rev 1; `manifest` — the vector `course-testsub` | P/02.2-04, P/02.3-01 |
| 02 | `same_twice` | the same file again — «unchanged»: rev 1, the view is the former one | P/02.3 N3 «Manifest change» |
| 03 | `view_deleted` | there is no view, the file is the same — not «unchanged»: the row rev 2, the view and the mark rev 2 | P/02.3 N3 («same row, missing view») |
| 04 | `view_spoiled` | the view is not equal to the projection, the file is the same — the view is rewritten, rev 2 | ibid. |
| 05 | `view_over_ceiling` | the weight of the view row is 524289 — one byte above the ceiling, the manifest row (523609) fits: a refusal as a whole, code 2; the row, the view and the mark are the former rev 1 from `probe` | P/02.2 N3, N4; P/02.3 N4 |
| 06 | `view_at_ceiling` | the weight of the view row is exactly 524288 — the view is written, the row and the mark rev 2; the boundary of the domain of accepted manifests | P/02.2 N1.2 `ceiling` |
| 07 | `sugared` | the sugar `tables`, `bound_to`, without `snapshot` and `display` — the installer's view equals the vector | P/02.2-02, P/02.2-03 |
| 08 | `rev_deleted` | there is no mark, the file is the same — «unchanged»: the row and the view are the former rev 1, the mark is brought up to date — rev 1, the `sha256` of the row | P/02.3 N3 «Manifest change» («missing mark … → bring up to date»), P/02.3-03 |
| 09 | `rev_spoiled` | the mark is not by the form (`rev` — `"x"`), the file is the same — a refusal, code 2, nothing is written: the row and the view are the former rev 1, the mark is the spoiled one | P/02.3 N1.5 `rules`, [`manifest-rev.outcomes.tsv`](../../data/manifest-rev.outcomes.tsv) (the reader `admin`), P/02.3-01 |
| 10 | `row_without_view` | `@view-delete` and `@rev-delete` leave the row rev 1 without the view and without the mark, as a first installation broken after the write of the row; the same file again — not «unchanged»: the row, the view and the mark rev 2, the mark with the `sha256` of the row; `manifest` — the vector `course-testsub` | P/02.3-R078, P/02.3-R080, P/02.3-R104, P/02.3-R123 |


### Original passage 3

`manifest` — `87 +` the length of the view. The files 05 and 06 differ by one byte of the field `display.unit` (the view of 06 is 524201 bytes); their manifest rows are under the ceiling.
