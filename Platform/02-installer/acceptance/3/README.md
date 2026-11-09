# Acceptance P/02.3 — the manifest installation `manifest put`

This English text is the source; the Russian translation `ru/acceptance/3/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The norm of the chapter is
[`02.3-installer.norms.md`](../../spec/02.3-installer.norms.md) N5. `puts.tsv` has 87 installations (9 after `near_*` — the coverage audit P/02 of 2026-10-30, the next 16 — its second pass, below; the 11 next ones — ADR-0094 B7; 3 `calls_*` — the callback list at a subsystem of the catalogue, ADR-0094 B1; 3 `calls_requests_*` — the entry `<s>/requests` of another subsystem and of the own one, P/06.3 N1.9 (review of lesson P/02, S5); 3 `calls_first_*`, `calls_second_kind` — ADR-0112 addendum (3) item 2; the last two `calls_pulse_ok`, `calls_pulse_bad` — the declared heartbeat callback); the installation files are in `puts/`.
The table and the files were moved from the acceptance of M10/2 (stage B) without changes; the loader corpus is [the acceptance of chapter 2.1](../1/README.md).

## Profile interface

Use the `02-installer` [profile format](../../../common/acceptance/PROFILE.md). `stand.manifest-put` takes the prepared administrative `{socket}` and the candidate manifest `{file}` and runs the normal manifest installation, including the existing catalogue, file, write-order and unchanged-state rules. It returns the native installation outcome described below; it does not receive a deployment substitution or an expected table row. Store creation belongs to the selected `01-store` profile. The implementation chooses the executable wrapper and flags that expose this existing command contract. The explicitly unbound recovery obligation below stays unexecuted.

## puts.tsv

The manifest installation `manifest put` of the implementation (N3 «Manifest change», the command name and argv — [`operator-commands.tsv`](../../forms/operator-commands.tsv)); the runner calls it
by the command `manifest-put {socket} {file}` of the section «Stand» of the common acceptance README (the store pilot, A6).

**The form of the file.** UTF-8, lines separated by LF, fields by TAB. Lines starting with `#` and empty lines are skipped. The first
line not skipped is the header `case<TAB>puts<TAB>expect`, then one line per case; exactly three fields.

- `case` — the case name: `[a-z0-9_]+`, unique in the file;
- `puts` — the file names `puts/<name>.subsystem.yaml` separated by one space, in the order of installation, and the directives `@rev-max`,
  `@shell-put <name>`, `@file-fill <path> <bytes>` between them; a file comes first and last; there is no subsystem shell next to the manifest until
  `@shell-put` puts it (N1.5 `shell`: no file — the field is not written);
- `expect` — `<code> <rev>`: `<code>` is the return code of the **last** installation (`0` or `2`), `<rev>` is the decimal value of the field
  `rev` of the row `platform/manifest/<name>` after it, where `<name>` is the `name` of the last file; `-` — there is no row.

**Directives** (this chapter only; through `admin.sock` of the instance — `{socket}` of the «Stand»; `<name>` is the `name` of the file before the directive):
- `@rev-max` — read the row `platform/manifest/<name>`, the mark `platform/manifest/<name>/rev` and the view
  `platform/manifest/<name>/canonical/1` and write each with `cas` by the version read, where `rev` = `9007199254740991`
  (2^53 − 1), the other fields byte for byte the former ones: the state as after an honest installation with such a revision (N1.5 `rev`);
- `@shell-put <name>` — put next to the manifest `<name>` the shell `<name>.shell.html` with the bytes of `puts/<name>.shell.html`
  (replace the former one); it applies to the following installations of the line; the working copy is its own for each line.

**The files of the list.** Next to the working copy of the manifest of each installation the runner puts the whole content of
[`06-console/acceptance/5/inputs/testsub2/`](../../../06-console/acceptance/5/inputs/testsub2) under the same paths — the same files as
`testsub2` has on the stand (common README, «Manifests»); P/02.3 N3 reads them next to the manifest file. There is no directive for them: the files do not change between
installations. The shell next to the manifest appears only by `@shell-put`.

- `@file-fill <path> <bytes>` — put next to the manifest the file `<path>` (relative, without `..`) of exactly `<bytes>` bytes; it
  applies to the following installations of the line; the bytes are arbitrary: the subject is the size (the ceilings of P/02.3 N1.5). The runner creates the file, it is not in `puts/`,
  therefore the ceilings of 8 MiB do not add weight to the acceptance data.

**Execution.** The cases are independent, the order of lines does not matter. For **each line** the runner takes a new empty store
(P/01.1; not a single manifest, including `testsub`) and installs the files of this line in order into one and the same store by the installation
command, each by a separate call. All installations except the last MUST return `0`: otherwise — a mismatch of the case
(the preparation failed). After the last one the runner compares:

1. the return code — with `<code>`;
2. with code `2` — stderr names the file of the last installation (the file name is part of the text), as with `verdicts.tsv`; a refusal on the attribute
   `on…=` in the shell — the shell file `<name>.shell.html` (P/02.3 N4: «stderr names the file and attribute»; the attribute name — by reading);
3. `rev` of the row `platform/manifest/<name>` — with `<rev>`: the row is read by the store door (`GET /v1/get?key=platform/manifest/<name>`,
   the field `rev` in `items`) or by the command `manifest show` of the implementation; `-` — `items: null` / there is no row.

Nothing else is compared: neither the mark `/rev` nor the refusal text beyond the file name. Catalogue checks (chapter 2.1 N3 `load_catalogue`: «A=B», a coincidence of `metrics.prefix`) give `ok` at a single load of such a file: the refusal is only at an installation into the catalogue. The same file again is «unchanged»; a changed file with the same name takes a new revision.
The catalogue checks of chapter 2.1 N3 apply to `worker.creates`, `worker.uses` and OS names (ADR-0091). If the target or the owner of a share is not yet in the catalogue, the check waits for its installation; a target after an incompatible customer is a refusal at the installation of the target.
The kinds of the domain token (ADR-0091 addendum (14), (17), (18) item 6): the same kind at a second subsystem — a refusal; the kind of the route `door.routes[].domain` is declared by another subsystem of the catalogue or by its own — accepted; there is no kind — a refusal (there is no deferral).
Static files and the declared shell (ADR-0094 B7): all extensions, nested segments, `api.js` and `apis/…` next to the prohibition of `api/`, an empty file and a file in two parts are accepted names; a listed file that does not exist — code 2, stderr names the manifest file and the path; `console.shell: true` without a shell — code 2; the same manifest without the word with a shell present — a new revision with the declaration; a file above `FILE_MAX` or a sum above `FILES_TOTAL_MAX` — code 2 before the write, the revision stays; exactly `FILE_MAX` — accepted.
The deferral of `near` (ADR-0091 addendum (26) item 2): there is no subsystem `near.sub` — the client is accepted, the field check waits; the target after an incompatible client — a refusal at the installation of the target.

## Checks by reading

The row and the mark of the manifest in the store, all the reasons for a start refusal, an admissible lagging mark, the stop on a change of the mark and the branch
`toolarge` of the installer — by reading per N5 of the chapter: `puts.tsv` compares only the code of the last installation, the file name in stderr and
the `rev` of the row.

## The coverage audit P/02 (2026-10-30)

The session audit-kimi, commit 82f4da9fc, the coverage audit P02 (for people): properties that were formerly checked by reading.
- The weight of the main row is above the ceiling (B01) — code 2 before bringing the mark up to date, the row stays (N3 branch `toolarge`, N4; a counterexample of N5).
- Catalogue checks with the list form of `tables` (B04; chapter 2.1 N3, P/02.1-20).
- The boundary `rev` = 2^53 − 1 by the directive `@rev-max` (B02): the same file — «unchanged», code 0; a changed one — a refusal before any write, code 2, the revision stays (N3, N4). The row key and `rev` in stderr — by reading per N4.
- The attribute `on…=` of a shell (C02-SHELL-TAG-01): `onclick=` in the text of a script, `onload=` in a style, `onclick=` in a comment and `data-on=` are not an attribute `on…=`, the shell is accepted; not yet run by an implementation.
- The shell and the revision (B03): a shell with an attribute `on…=` — code 2 before reading the catalogue, the revision stays; a shell appeared — a new revision (absence equals empty); the same yaml and shell again — «unchanged»; a shell different by bytes — a new revision (N1.5, N3). The attribute name in stderr — by reading per N4. The form of the check — check_spec 0021baa83 (the Architect).

## The coverage audit P/02, second pass (Gemini)

The report the coverage audit Gemini P02 (for people) (branch gemini/audit-coverage, c698f3291): catalogue checks that were formerly done by reading.
- `worker.requests` (chapter 2.1 N3 «load_catalogue»): a target with the section `requests` — accepted; there is no target — code 2 (requests have no deferral as `near`, `creates`, `uses` have: the target is installed earlier, P/02.4 N1.7 `order`); a target without `requests` — code 2; a target that removed `requests` on an update — code 2, its row stays (the catalogue is checked as a whole with the candidate).
- Rule 4 of `worker.creates`: an optional field `*_secret` of the target with `default` — code 2 with the target earlier and at the installation of the target after the customer.
- The checks of `near` also cover a field `near.of` that `near.sub` does not have, with a correct `near.prefer`.
- The owner of a share after the consumer: the share is declared — accepted, it is not — code 2 at the installation of the owner.
- The OS names of the catalogue (P/02.4 N1.1 `users_groups` names): a name of exactly 32 characters is accepted, of 33 — code 2, for the group of a controller and for the user of a part alike; a user that coincides with a platform group or with the group of a share — code 2; a share with `part` has no group of its own and is accepted. The deployment of the installer is the default `w2c` (P/02.4 N1.2; the command `manifest-put` of the «Stand» does not receive a deployment name): the clash with platform groups and the lengths of the users are computed with it; the controller group is `w2c-…` with any.

Bringing up to date a removed mark `/rev` in the branch «unchanged» and the refusal on a mark not by the form — the acceptance of chapter 2.2 (`rev_deleted`,
`rev_spoiled`; the directives `@rev-delete`, `@rev-spoil` — the Architect's decision, only with the four columns of chapter 2.2).
