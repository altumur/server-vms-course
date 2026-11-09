# Acceptance P/02.2 — the canonical view on the installation `manifest put`

This English text is the source; the Russian translation `ru/acceptance/2/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The norm of the chapter is
[`02.2-installer.norms.md`](../../spec/02.2-installer.norms.md) N5; the write of the view is [chapter 2.3](../../spec/02.3-installer.norms.md)
N3 «Manifest change» (the installer). `puts.tsv` has 9 installations; the installation files are in `puts/`. The window of chapter 2.2 is
the chapter 2.2 canonical-view window of 2026-10-20, section 4 and the Architect's decision (item 8): the view is built before
any write, a view above the ceiling is a refusal of the installation as a whole, the write order is row, view, mark last. The bytes of the view are
the vectors [`canonical`](../../vectors/canonical/README.md); here — the wrapper, `rev`, «unchanged» and the boundary of the view ceiling.

## Profile interface

Use the `02-installer` [profile format](../../../common/acceptance/PROFILE.md). The canonical-function package uses `stand.canonical` with `{input}`: the file path names the manifest input assigned by the package, and stdout contains exactly the canonical bytes of its [wire form](../../../common/vectors/wire.tsv). The installation checks below use `stand.manifest-put` with `{socket}` and `{file}`; the own command performs the normal installation rather than only printing a canonical view. Store launch parameters belong to the selected `01-store` profile. No complete positive-profile provider, sufficient B/V or recovery execution follows from declaring these commands.

## puts.tsv

The format of `puts.tsv` of [chapter 2.3](../3/README.md) with a fourth column `canonical` and with directives between files. The installation is
the command `manifest-put {socket} {file}` of the section «Stand» of the common acceptance README; the store is an instance of the «Stand» with a row ceiling of
524288 bytes (common README, «Parameters of each instance»).

**The form of the file.** UTF-8, lines separated by LF, fields by TAB. Lines starting with `#` and empty lines are skipped. The first
line not skipped is the header `case<TAB>puts<TAB>expect<TAB>canonical`, then one line per case; exactly four fields.

- `case` — the case name: `[a-z0-9_]+`, unique in the file;
- `puts` — separated by one space, in order: the file names `puts/<name>.subsystem.yaml` and the directives `@view-delete`,
  `@view-spoil`, `@rev-delete`, `@rev-spoil`; a file comes first and last;
- `expect` — `<code> <rev>`: `<code>` is the return code of the **last** installation (`0` or `2`), `<rev>` is the decimal `rev` of the row
  `platform/manifest/<name>` after it, where `<name>` is the `name` of the last file; `-` — there is no row;
- `canonical` — the case name of [`vectors/canonical/cases.tsv`](../../vectors/canonical/cases.tsv), whose bytes `expect/<case>.json`
  are the expected field `manifest` of the view row; `-` — there is no view row.

**Directives** (between installations, through `admin.sock` of the instance — `{socket}` of the «Stand», the operations of P/01.1; `<name>` is the `name`
of the file before the directive):
- `@view-delete` — `delete` of the row `platform/manifest/<name>/canonical/1`;
- `@view-spoil` — read the row `platform/manifest/<name>/canonical/1` and write it back with `cas` by the version read, but with
  the field `manifest` equal to `{}` (a different view: not a projection of the manifest); the other fields — as they were;
- `@rev-delete` — `delete` of the mark `platform/manifest/<name>/rev`;
- `@rev-spoil` — read the mark `platform/manifest/<name>/rev` and write it back with `cas` by the version read, but with the field
  `rev` equal to the string `"x"` (a mark not by the form of N1.5 of chapter 2.3: `rev` is not a decimal integer); the other fields — as they were.

**Execution.** The cases are independent, the order of lines does not matter. For **each line** the runner takes a new empty store
(P/01.1; not a single manifest) and executes `puts` in order: a file — by a separate call of the installation, a directive — by a write to the store.
All installations except the last MUST return `0`, each directive MUST pass: otherwise — a mismatch of the case (the preparation
failed). After the last installation the runner compares:

1. the return code — with `<code>`;
2. with code `2` — stderr names the file of the last installation and the key of the refused row: if the last directive before the installation is `@rev-spoil` — the key of the mark `platform/manifest/<name>/rev`, otherwise — the key of the view `platform/manifest/<name>/canonical/1` (both are part of the
   text; the weight and the ceiling in the text are not compared);
3. `rev` of the row `platform/manifest/<name>` — with `<rev>`, as in chapter 2.3 (the store door `GET /v1/get?key=…`, the field `rev` in
   `items`; `-` — `items: null`);
4. the mark `platform/manifest/<name>/rev`: its `rev` is the same `<rev>`, `sha256` is the `sha256` of the row; `-` — there is no mark; with code `2`
   after `@rev-spoil` — the mark is the one the directive wrote (`rev` — `"x"`): the refused installation does not touch it;
5. the view row `platform/manifest/<name>/canonical/1` (`items` by the codec of [the family `canonical-row`](../../data/canonical-row.schema.json)):
   `form` — `"1"`, `rev` — `<rev>`, `sha256` — the `sha256` of the row, `manifest` — the bytes `expect/<canonical>.json` of the vector byte for
   byte; extra fields are not compared; `canonical` = `-` — there is no view row.

Items 4–5 compare the state after the installation, not the order of the writes in time: the order row — view — mark and the repeat
of the view after a `cas` conflict — by reading per N5 of the chapter.

## Cases

The cases and their expected outcomes are in [judge-only case data](README.cases.md). They cover these rules:

| What it checks | Norm |
|---|---|
| the first installation writes the row, the view and the mark with one revision; `manifest` is the assigned vector | P/02.2-04, P/02.3-01 |
| the same file again — «unchanged»: the revision and the view stay | P/02.3 N3 «Manifest change» |
| there is no view, the file is the same — not «unchanged»: a new revision of the row, the view and the mark | P/02.3 N3 («same row, missing view»); window 2.2, R12 |
| the view is not equal to the projection, the file is the same — the view is rewritten with a new revision | ibid. |
| the weight of the view row is above the ceiling, the manifest row fits — a refusal as a whole, code 2; the row, the view and the mark stay | P/02.2 N3, N4; P/02.3 N4 (window 2.2, item 8) |
| the weight of the view row is exactly the ceiling — the view is written; the boundary of the domain of accepted manifests | P/02.2 N1.2 `ceiling` (ADR-0089 addendum (1) R11) |
| the sugar `tables`, `bound_to`, the absence of `snapshot` and `display` — the installer's view equals the assigned vector | P/02.2-02, P/02.2-03 |
| there is no mark, the file is the same — «unchanged»: the row and the view stay, the mark is brought up to date with the revision and the `sha256` of the row (the Gemini audit P/02, property 13) | P/02.3 N3 «Manifest change» («missing mark … → bring up to date»), P/02.3-03 |
| the mark is not by the form, the file is the same — a refusal, code 2, nothing is written: the row, the view and the mark stay (property 14) | P/02.3 N1.5 `rules`, [`manifest-rev.outcomes.tsv`](../../data/manifest-rev.outcomes.tsv) (the reader `admin`), P/02.3-01 |
The weight of the view row is the sum of the bytes of the names and values of `items` (P/01.1 N1): `form` `"1"`, `rev` of one digit, `sha256` 64 characters,
`manifest` — `87 +` the length of the view.

## puts-ceiling.tsv: a non-default store ceiling

The view ceiling is `max_value` of the answer of `GET /v1/status` of the store, not the number 524288 (the Architect's decision on the Go question P/02 № 4).
The cases are a separate file `puts-ceiling.tsv` (the coverage audit P/02, B00; `puts.tsv` does not change its form; the form
of the check — check_spec 0021baa83): the form is
`case<TAB>puts<TAB>expect<TAB>canonical<TAB>ceiling`, the first four fields and the comparison are as in `puts.tsv`; `ceiling` is the row
ceiling of the new instance of this line (`{row_ceiling}` of the start command of the «Stand»). Before the case the runner verifies the parameter:
`GET /v1/status` → `max_value` = `ceiling`, and by behaviour — `items` of weight exactly `ceiling` is written, one byte more — 413
`toolarge` with `limit` = `ceiling`; if it does not match, the run is not performed.

Cases of a non-default ceiling and their expected outcomes are in [judge-only case data](README.cases.md). The installer checks the weight with the final new rev before any write (chapter 2.3 N3 step 14a), so a refusal comes before the parts, the row and the mark. A boundary reached through a `cas` conflict of two installers is checked by reading: the table installs sequentially.

## Checks by reading

The order of the writes in time (row — view — mark), the `cas` repeat of the view, a cluster of one process (P/02.4 N1.10, R15) and
the reader of the view (P/02.2-06 — by the readers' edits) — by reading per N5 of the chapter.

## The Gemini coverage audit P/02: the mark `/rev` (the Architect's forms)

Properties 13 and 14 of the report the coverage audit Gemini P02 (for people) (branch gemini/audit-coverage, c698f3291) — the directives `@rev-delete`,
`@rev-spoil` (the Architect's decision on the question of the form; check_spec dad80a80b), the cases 08 `rev_deleted` and 09 `rev_spoiled`.
The refusal code on an unreadable mark is `2`: N1.5 of chapter 2.3 says «code ≠ 0», the table `expect` knows `0` and `2`, the refusals of
`manifest put` of N4 of chapter 2.3 are code 2. An unreadable row `platform/manifest/<name>` (the outcomes of `manifest-row.outcomes.tsv`) —
still by reading: there is no directive for spoiling the row.
