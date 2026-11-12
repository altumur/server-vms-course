# Acceptance P/02.3 — the manifest installation `manifest put`

This English text is the source; the Russian translation `ru/acceptance/3/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The norm of the chapter is
[`02.3-installer.norms.md`](../../spec/02.3-installer.norms.md) N5. `puts.tsv` (judge-only: the installation table) has 97 installations (2 `row_spoiled_*` after `toolarge_row` — an unreadable manifest row by `@row-spoil`, P/02.3 N1.5 rules and `manifest-row.outcomes.tsv`, the reader `admin`; 8 `*_swap` and `*_renamed` after `list_tables_ok` — the catalogue intersection of chapter 2.1 with the order swapped and its positive controls, P/02.1-R049, P/02.1-R061, P/02.1-R178; 9 after `near_*` — the installer properties below, the next 16 — the catalogue properties below; the 11 next ones — static files and the declared shell (N1.5, N3); 3 `calls_*` — the callback list at a subsystem of the catalogue; 3 `calls_requests_*` — the entry `<s>/requests` of another subsystem and of the own one, P/06.3 N1.9; 3 `calls_first_*`, `calls_second_kind` — a `calls` entry of a segment named by the first kind in `door.pass` of the target is accepted, a segment that is not named or is of the second kind is a catalogue refusal; the last two `calls_pulse_ok`, `calls_pulse_bad` — the declared heartbeat callback); the installation files are in `puts/`.
The loader corpus is [the acceptance of chapter 2.1](../1/README.md).

## Profile interface

Use the `02-installer` [profile format](../../../common/acceptance/PROFILE.md). `stand.manifest-put` takes the prepared administrative `{socket}` and the candidate manifest `{file}` and runs the normal manifest installation, including the existing catalogue, file, write-order and unchanged-state rules. It returns the native installation outcome described below; it does not receive a deployment substitution or an expected table row. Store creation belongs to the selected `01-store` profile. The implementation chooses the executable wrapper and flags that expose this existing command contract. The explicitly unbound recovery obligation below stays unexecuted.

## puts.tsv

The table is run by the engine word `puts` in the form «[Installation sequences](../../../common/acceptance/command-tables.md#installation-sequences)» of the common acceptance README with three columns: the directives `@rev-max`, `@shell-put <source>`, `@file-fill <path> <bytes>`, the execution in a fresh store per line and the comparison of the code, the file name in stderr and `rev` of the row are defined there; the mark `/rev` and the view are not compared. The installation is `stand.manifest-put` above (the command name and argv of `manifest put` — [`operator-commands.tsv`](../../forms/operator-commands.tsv), N3 «Manifest change»).

The declaration `# beside:` of the table puts the whole content of [`06-console/acceptance/5/inputs/testsub2/`](../../../06-console/acceptance/5/inputs/testsub2) (judge-only: the files of the subsystem `testsub2` beside its manifest) next to the working copy of every installation, the same files as `testsub2` has on the stand (common README, «Manifests»); P/02.3 N3 reads them next to the manifest file. Until `@shell-put` a line has no shell next to the manifest (N1.5 `shell`: no file — the field is not written). The sizes of `@file-fill` are the ceilings of N1.5, so the files of 8 MiB are not acceptance data.

The subjects of the rows (the rules are the norms of the chapter and of chapter 2.1 N3):

Catalogue checks (chapter 2.1 N3 `load_catalogue`: «A=B», a coincidence of `metrics.prefix`) give `ok` at a single load of such a file: the refusal is only at an installation into the catalogue. The same file again is «unchanged»; a changed file with the same name takes a new revision.
The catalogue checks of chapter 2.1 N3 apply to `worker.creates`, `worker.uses` and OS names. If the target or the owner of a share is not yet in the catalogue, the check waits for its installation; a target after an incompatible customer is a refusal at the installation of the target.
The kinds of the domain token: the same kind at a second subsystem — a refusal; the kind of the route `door.routes[].domain` is declared by another subsystem of the catalogue or by its own — accepted; there is no kind — a refusal (there is no deferral).
Static files and the declared shell: all extensions, nested segments, `api.js` and `apis/…` next to the prohibition of `api/`, an empty file and a file in two parts are accepted names; a listed file that does not exist — code 2, stderr names the manifest file and the path; `console.shell: true` without a shell — code 2; the same manifest without the word with a shell present — a new revision with the declaration; a file above `FILE_MAX` or a sum above `FILES_TOTAL_MAX` — code 2 before the write, the revision stays; exactly `FILE_MAX` — accepted.
The deferral of `near`: there is no subsystem `near.sub` — the client is accepted, the field check waits; the target after an incompatible client — a refusal at the installation of the target.

## Not judged in this lesson

- The start of a process by the row: the mark, all reasons for a start refusal and the two start codes, an admissible lagging mark, the stop on a change of the mark (N3 «Process start», N4 rows 1–3). They need the processes of later lessons: the system checklist of the lesson and the stage of the system.
- The place of the branch `toolarge` in the code of the installer (N5): by reading. Its outcome is the row `toolarge_row`.
- The value of `rev` in stderr after `@rev-max` (N4 row 5): by reading per N4. The row key, the attribute `on…=`, the paths of `console.files` and the key of `toolarge` are judged by `@stderr` of their rows.

## Installer properties

Installer properties judged by rows of the table:
- The weight of the main row is above the ceiling — code 2 before bringing the mark up to date, the row stays (N3 branch `toolarge`, N4; a counterexample of N5).
- Catalogue checks with the list form of `tables` (chapter 2.1 N3, P/02.1-R049, P/02.1-R061, P/02.1-R178).
- The boundary `rev` = 2^53 − 1 by the directive `@rev-max`: the same file — «unchanged», code 0; a changed one — a refusal before any write, code 2, the revision stays (N3, N4). The row key in stderr — `@stderr` of the row, the value of `rev` — by reading per N4.
- The attribute `on…=` of a shell: `onclick=` in the text of a script, `onload=` in a style, `onclick=` in a comment and `data-on=` are not an attribute `on…=`, the shell is accepted.
- The shell and the revision: a shell with an attribute `on…=` — code 2 before reading the catalogue, the revision stays; a shell appeared — a new revision (absence equals empty); the same yaml and shell again — «unchanged»; a shell different by bytes — a new revision (N1.5, N3). The attribute name in stderr — `@stderr` of the row.

## Catalogue properties

Catalogue checks judged by rows of the table:
- `worker.requests` (chapter 2.1 N3 «load_catalogue»): a target with the section `requests` — accepted; there is no target — code 2 (requests have no deferral as `near`, `creates`, `uses` have: the target is installed earlier, P/02.4 N1.7 `order`); a target without `requests` — code 2; a target that removed `requests` on an update — code 2, its row stays (the catalogue is checked as a whole with the candidate).
- Rule 4 of `worker.creates`: an optional field `*_secret` of the target with `default` — code 2 with the target earlier and at the installation of the target after the customer.
- The checks of `near` also cover a field `near.of` that `near.sub` does not have, with a correct `near.prefer`.
- The owner of a share after the consumer: the share is declared — accepted, it is not — code 2 at the installation of the owner.
- The OS names of the catalogue (P/02.4 N1.1 `users_groups` names): a name of exactly 32 characters is accepted, of 33 — code 2, for the group of a controller and for the user of a part alike; a user that coincides with a platform group or with the group of a share — code 2; a share with `part` has no group of its own and is accepted. The deployment of the installer is the default `w2c` (P/02.4 N1.2; the command `manifest-put` of the «Stand» does not receive a deployment name): the clash with platform groups and the lengths of the users are computed with it; the controller group is `w2c-…` with any.

Bringing up to date a removed mark `/rev` in the branch «unchanged» and the refusal on a mark not by the form — the acceptance of chapter 2.2 (`rev_deleted`,
`rev_spoiled`; the directives `@rev-delete`, `@rev-spoil` — only with the four columns of chapter 2.2).
