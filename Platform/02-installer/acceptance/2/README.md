# Acceptance P/02.2 — the canonical view on the installation `manifest put`

This English text is the source; the Russian translation `ru/acceptance/2/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The norm of the chapter is
[`02.2-installer.norms.md`](../../spec/02.2-installer.norms.md) N5; the write of the view is [chapter 2.3](../../spec/02.3-installer.norms.md)
N3 «Manifest change» (the installer). `puts.tsv` has 9 installations (judge-only: the installation table of the chapter; it checks P/02.2-R027, P/02.2-R032, P/02.2-R047, P/02.2-R051, P/02.2-R054, P/02.2-R055 and P/02.2-R060); the installation files are in `puts/`. The view is built before
any write, a view above the ceiling is a refusal of the installation as a whole, the write order is row, view, mark last. The bytes of the view are
the vectors [`canonical`](../../vectors/canonical/README.md); here — the wrapper, `rev`, «unchanged» and the boundary of the view ceiling.

## Profile interface

Use the `02-installer` [profile format](../../../common/acceptance/PROFILE.md). The canonical-function package uses `stand.canonical` with `{input}`: the file path names the manifest input assigned by the package, and stdout contains exactly the canonical bytes of its [wire form](../../../common/vectors/wire.tsv). The installation checks below use `stand.manifest-put` with `{socket}` and `{file}`; the own command performs the normal installation rather than only printing a canonical view. Store launch parameters belong to the selected `01-store` profile. No complete positive-profile provider, sufficient B/V or recovery execution follows from declaring these commands.

## puts.tsv and puts-ceiling.tsv

Both tables are run by the engine word `puts` in the form «[Installation sequences](../../../common/acceptance/command-tables.md#installation-sequences)» of the common acceptance README: the four or five columns, the directives `@view-delete`, `@view-spoil`, `@rev-delete`, `@rev-spoil`, the execution in a fresh store per line and the comparison of the code, stderr, `rev`, the mark and the view are defined there. The declaration `# canonical:` of both tables names the vector package [`canonical`](../../vectors/canonical/README.md): the bytes `expect/<canonical>.json` are the expected field `manifest` of the view row (judge-only: the expected views of the package; they check P/02.2-R027 and P/02.2-R043). The installation is `stand.manifest-put` above. `puts.tsv` runs with the default row ceiling of 524288 bytes; `puts-ceiling.tsv` sets the ceiling of each line in its column `ceiling`, and the judge confirms it before the line (the same form; judge-only: the installation tables of the chapter; they check P/02.2-R009, P/02.2-R015, P/02.2-R017, P/02.2-R027, P/02.2-R032, P/02.2-R044, P/02.2-R051, P/02.2-R054, P/02.2-R055, P/02.3-R016, P/02.3-R031, P/02.3-R103 and P/02.3-R123).

The view ceiling is `max_value` of the answer of `GET /v1/status` of the store, not the number 524288. The installer checks the weight with the final new rev before any write (chapter 2.3 N3 step 14a), so a refusal above the ceiling comes before the parts, the row and the mark.

The cases of a non-default ceiling and their expected outcomes are in [judge-only case data](README.cases.md) (judge-only: it checks P/02.2-R032, P/02.2-R044, P/02.2-R051).

## Cases

The cases and their expected outcomes are in [judge-only case data](README.cases.md) (judge-only: they check P/02.2-R009, P/02.2-R015, P/02.2-R017, P/02.2-R027, P/02.2-R032, P/02.2-R051, P/02.2-R054, P/02.3-R031 and P/02.3-R103). They cover these rules:

| What it checks | Norm |
|---|---|
| the first installation writes the row, the view and the mark with one revision; `manifest` is the assigned vector | P/02.2-R027, P/02.3-R016 |
| the same file again — «unchanged»: the revision and the view stay | P/02.3 N3 «Manifest change» |
| there is no view, the file is the same — not «unchanged»: a new revision of the row, the view and the mark | P/02.3 N3 («same row, missing view») |
| the view is not equal to the projection, the file is the same — the view is rewritten with a new revision | ibid. |
| the weight of the view row is above the ceiling, the manifest row fits — a refusal as a whole, code 2; the row, the view and the mark stay | P/02.2 N3, N4; P/02.3 N4 |
| the weight of the view row is exactly the ceiling — the view is written; the boundary of the domain of accepted manifests | P/02.2 N1.2 `ceiling` |
| the sugar `tables`, `bound_to`, the absence of `snapshot` and `display` — the installer's view equals the assigned vector | P/02.2-R009, P/02.2-R015, P/02.2-R017 |
| there is no mark, the file is the same — «unchanged»: the row and the view stay, the mark is brought up to date with the revision and the `sha256` of the row | P/02.3 N3 «Manifest change» («missing mark … → bring up to date»), P/02.3-R103 |
| the mark is not by the form, the file is the same — a refusal, code 2, nothing is written: the row, the view and the mark stay | P/02.3 N1.5 `rules`, [`manifest-rev.outcomes.tsv`](../../data/manifest-rev.outcomes.tsv) (the reader `admin`), P/02.3-R031 |
The weight of the view row is the sum of the bytes of the names and values of `items` (P/01.1 N1): `form` `"1"`, `rev` of one digit, `sha256` 64 characters,
`manifest` — `87 +` the length of the view.

## Not judged in this lesson

- The order of the writes in time (row — view — mark) and the repeat of the view after a `cas` conflict: the tables compare the state after the installation; the order is checked by reading per N5 of the chapter.
- The ceiling reached through a `cas` conflict of two installers, and any conflict of two installers: they need the store of another lesson and belong to the stage of the system; the tables install sequentially.
- A cluster of one process (P/02.4 N1.10) and the reader of the view (P/02.2-R062, P/02.2-R064, P/02.2-R067, P/02.2-R068, P/02.2-R069, P/02.2-R070, P/02.2-R072 — by the readers' edits): by reading per N5 of the chapter.
- An unreadable row `platform/manifest/<name>`: by [`manifest-row.outcomes.tsv`](../../data/manifest-row.outcomes.tsv) the reader `admin` refuses `manifest put` and writes nothing; its rows are `row_spoiled_yaml` and `row_spoiled_sha256` of [`../3/puts.tsv`](../3/puts.tsv) (judge-only: the installation table of chapter 2.3; they check P/02.3-R031; three columns: a spoiled `sha256` makes the view of item 5 differ from the row by itself).

## The mark `/rev`

The mark is checked by the directives `@rev-delete`,
`@rev-spoil` and the cases 08 `rev_deleted` and 09 `rev_spoiled`.
The refusal code on an unreadable mark is `2`: N1.5 of chapter 2.3 says «code ≠ 0», the table `expect` knows `0` and `2`, the refusals of
`manifest put` of N4 of chapter 2.3 are code 2.
