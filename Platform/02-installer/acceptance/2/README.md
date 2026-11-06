# Acceptance P/02.2 — the canonical view on the installation `manifest put`

This English text is the source; the Russian translation `ru/acceptance/2/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The norm of the chapter is
[`02.2-installer.norms.md`](../../spec/02.2-installer.norms.md) N5; the write of the view is [chapter 2.3](../../spec/02.3-installer.norms.md)
N3 «Manifest change» (the installer). `puts.tsv` has 9 installations; the installation files are in `puts/`. The window of chapter 2.2 is
`decisions/inbox/2026-10-20-окно-главы-2.2-канонический-вид.md`, section 4 and the Architect's decision (item 8): the view is built before
any write, a view above the ceiling is a refusal of the installation as a whole, the write order is row, view, mark last. The bytes of the view are
the vectors [`canonical`](../../vectors/canonical/README.md); here — the wrapper, `rev`, «unchanged» and the boundary of the view ceiling.

## puts.tsv

The format of `puts.tsv` of [chapter 2.3](../3/README.md) with a fourth column `canonical` and with directives between files. The installation is
the command `manifest-put {socket} {file}` of the section «Stand» of the common acceptance README; the store is an instance of the «Stand» with a row ceiling of
524288 bytes (common README, «Параметры каждого экземпляра»).

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
2. with code `2` — stderr names the file of the last installation and the key of the refused row: for the case `rev_spoiled` (the last directive before the installation is `@rev-spoil`) — the key of the mark `platform/manifest/<name>/rev`, otherwise — the key of the view `platform/manifest/<name>/canonical/1` (both are part of the
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

| № | Case | What it checks | Norm |
|---|---|---|---|
| 01 | `first` | the first installation of `testsub`: the row, the view and the mark rev 1; `manifest` — the vector `course-testsub` | P/02.2-04, P/02.3-01 |
| 02 | `same_twice` | the same file again — «unchanged»: rev 1, the view is the former one | P/02.3 N3 «Manifest change» |
| 03 | `view_deleted` | there is no view, the file is the same — not «unchanged»: the row rev 2, the view and the mark rev 2 | P/02.3 N3 («строка та же, а вида нет»); window 2.2, R12 |
| 04 | `view_spoiled` | the view is not equal to the projection, the file is the same — the view is rewritten, rev 2 | ibid. |
| 05 | `view_over_ceiling` | the weight of the view row is 524289 — one byte above the ceiling, the manifest row (523609) fits: a refusal as a whole, code 2; the row, the view and the mark are the former rev 1 from `probe` | P/02.2 N3, N4; P/02.3 N4 (window 2.2, item 8) |
| 06 | `view_at_ceiling` | the weight of the view row is exactly 524288 — the view is written, the row and the mark rev 2; the boundary of the domain of accepted manifests | P/02.2 N1.2 `ceiling` (ADR-0089 addendum (1) R11) |
| 07 | `sugared` | the sugar `tables`, `bound_to`, without `snapshot` and `display` — the installer's view equals the vector | P/02.2-02, P/02.2-03 |
| 08 | `rev_deleted` | there is no mark, the file is the same — «unchanged»: the row and the view are the former rev 1, the mark is brought up to date — rev 1, the `sha256` of the row (the Gemini audit P/02, property 13) | P/02.3 N3 «Manifest change» («метки нет … → довести»), P/02.3-03 |
| 09 | `rev_spoiled` | the mark is not by the form (`rev` — `"x"`), the file is the same — a refusal, code 2, nothing is written: the row and the view are the former rev 1, the mark is the spoiled one (property 14) | P/02.3 N1.5 `rules`, [`manifest-rev.outcomes.tsv`](../../data/manifest-rev.outcomes.tsv) (the reader `admin`), P/02.3-01 |

The weight of the view row is the sum of the bytes of the names and values of `items` (P/01.1 N1): `form` `"1"`, `rev` of one digit, `sha256` 64 characters,
`manifest` — `87 +` the length of the view. The files 05 and 06 differ by one byte of the field `display.unit` (after `worker.exec` the field is shortened by 49 bytes: the view of 06 is again 524201); their manifest rows are under the ceiling.

## puts-ceiling.tsv: a non-default store ceiling

The view ceiling is `max_value` of the answer of `GET /v1/status` of the store, not the number 524288 (the Architect's decision on the Go question P/02 № 4).
A pair of cases is a separate file `puts-ceiling.tsv` (the coverage audit P/02, B00; `puts.tsv` does not change its form; the form
of the check — check_spec 0021baa83): the form is
`case<TAB>puts<TAB>expect<TAB>canonical<TAB>ceiling`, the first four fields and the comparison are as in `puts.tsv`; `ceiling` is the row
ceiling of the new instance of this line (`{row_ceiling}` of the start command of the «Stand»). Before the case the runner verifies the parameter:
`GET /v1/status` → `max_value` = `ceiling`, and by behaviour — `items` of weight exactly `ceiling` is written, one byte more — 413
`toolarge` with `limit` = `ceiling`; if it does not match, the run is not performed. The file `probe` (the manifest row
265 bytes, the mark 74, the view row `87 + 890` = 977; the numbers are after `worker.exec`, ADR-0091 addendum (5), finding of cammeta-c-go I02-G01):

| Ceiling `{row_ceiling}` | Installation | Expectation |
|---|---|---|
| 976 | `probe` | code 2, nothing is written: there is no row, no view and no mark; stderr names the file and the key of the view |
| 977 | `probe` | code 0, rev 1, the view is the vector `example-sections` |

Both lines are in `puts-ceiling.tsv`.

## `journal/corrections-2.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample` (a sample of a generation error), `fix` (which line of the chapter was clarified),
`languages`. The line 2026-10-23 is the shift of the weight boundaries after `worker.exec` (finding of cammeta-c-go I02-G01).

## Checks by reading

The order of the writes in time (row — view — mark), the `cas` repeat of the view, a cluster of one process (P/02.4 N1.10, R15) and
the reader of the view (P/02.2-06 — by the readers' edits) — by reading per N5 of the chapter.

## The Gemini coverage audit P/02: the mark `/rev` (the Architect's forms)

Properties 13 and 14 of the report `АУДИТ-ПОКРЫТИЯ-GEMINI-P02.md` (branch gemini/audit-coverage, c698f3291) — the directives `@rev-delete`,
`@rev-spoil` (the Architect's decision on the question of the form; check_spec dad80a80b), the cases 08 `rev_deleted` and 09 `rev_spoiled`.
The refusal code on an unreadable mark is `2`: N1.5 of chapter 2.3 says «код ≠ 0», the table `expect` knows `0` and `2`, the refusals of
`manifest put` of N4 of chapter 2.3 are code 2. An unreadable row `platform/manifest/<name>` (the outcomes of `manifest-row.outcomes.tsv`) —
still by reading: there is no directive for spoiling the row.
