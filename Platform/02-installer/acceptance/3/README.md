# Acceptance P/02.3 — the manifest installation `manifest put`

This English text is the source; the Russian translation `ru/acceptance/3/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The norm of the chapter is
[`02.3-installer.norms.md`](../../spec/02.3-installer.norms.md) N5. `puts.tsv` has 87 installations (9 after `near_*` — the coverage audit P/02 of 2026-10-30, the next 16 — its second pass, below; the 11 next ones — ADR-0094 B7; 3 `calls_*` — the callback list at a subsystem of the catalogue, ADR-0094 B1; 3 `calls_requests_*` — the entry `<s>/requests` of another subsystem (it is in the catalogue without `requests` — accepted; it is absent — a deferral) and of the own one, P/06.3 N1.9 (review of lesson P/02, С5); 3 `calls_first_*`, `calls_second_kind` — ADR-0112 addendum (3) item 2; the last two `calls_pulse_ok`, `calls_pulse_bad` — the declared heartbeat callback); the installation files are in `puts/`.
The table and the files were moved from the acceptance of М10/2 (stage B) without changes; the loader corpus is [the acceptance of chapter 2.1](../1/README.md).

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
`testsub2` has on the stand (common README, «Манифесты»); P/02.3 N3 reads them next to the manifest file. There is no directive for them: the files do not change between
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
   `on…=` in the shell — the shell file `<name>.shell.html` (P/02.3 N4: «stderr называет файл и атрибут»; the attribute name — by reading);
3. `rev` of the row `platform/manifest/<name>` — with `<rev>`: the row is read by the store door (`GET /v1/get?key=platform/manifest/<name>`,
   the field `rev` in `items`) or by the command `manifest show` of the implementation; `-` — `items: null` / there is no row.

Nothing else is compared: neither the mark `/rev` nor the refusal text beyond the file name. The cases `self_*`, `other_*`,
`prefix_clash` are catalogue checks (chapter 2.1 N3 `load_catalogue`: «A=B», a coincidence of `metrics.prefix`): a single load of these
files gives `ok`, the refusal is only at an installation into the catalogue. `same_twice` — the same file twice: «unchanged», rev 1;
`changed` — a changed one with the same name: rev 2. The cases `creates_*`, `uses_*`, `os_name_clash` (ADR-0091) are catalogue checks
of chapter 2.1 N3 for `worker.creates`, `worker.uses` and OS names: each refusing case differs from `creates_ok` or `uses_ok`
by one reason; `creates_nested_prefix` installs two customers, the refusal is at the second one (`cust-x`). If the target or the owner of a share is not yet in the catalogue, the check waits for its installation (`creates_no_target`, `uses_no_owner` — 0);
`target_after_customer_mismatch` — a refusal at the installation of the target after an incompatible customer. The cases `kind_dup`,
`door_domain_*` (ADR-0091 addendum (14), (17), (18) item 6) are the kinds of the domain token: the same kind at a second subsystem — a refusal; the kind
of the route `door.routes[].domain` is declared by another subsystem of the catalogue or by its own — accepted; there is no kind — a refusal (there is no deferral).
The cases `files_*`, `shell_declared_*` (ADR-0094 B7): `filed` names the accepted names — all extensions, nested segments, `api.js` and
`apis/…` next to the prohibition of `api/`, an empty file, a file in two parts; `filed-missing` names a file that does not exist — code 2, stderr names the manifest file and the path;
`filed-none` — the same `name` without a list; `pagedecl` — `console.shell: true`, there is no shell — code 2; `pagedecl-bare` — the same `name` without
the word, after `@shell-put` there is a shell — a new revision with the declaration. `filed-big` names `big.js`, `filed-sum` — `sum1.js`…`sum5.js`:
a file one byte above `FILE_MAX` and a sum one byte above `FILES_TOTAL_MAX` (four files of 8 MiB and a byte) — code 2 before the write, the revision is the former 1;
exactly `FILE_MAX` — accepted, rev 2.
The cases `near_*` (ADR-0091 addendum (26) item 2) — the deferral of `near`: there is no subsystem `near.sub` — the client is accepted, the field check
waits; the target after an incompatible client — a refusal at the installation of the target.

## `journal/corrections-3.tsv`

The log of AI corrections (ADR-0080 addendum 1; ADR-0124: a log, not an input, not in the export): `date`, `sample` (a sample of a generation error), `fix` (which line of the chapter was clarified),
`languages`. The former corrections of `puts.tsv` are in the log of chapter 2.1 (`journal/corrections-1.tsv`, a log, not in the export) (the line 2026-10-17 `02/m49_*, puts.tsv`).

## Checks by reading

The row and the mark of the manifest in the store, all the reasons for a start refusal, an admissible lagging mark, the stop on a change of the mark and the branch
`toolarge` of the installer — by reading per N5 of the chapter: `puts.tsv` compares only the code of the last installation, the file name in stderr and
the `rev` of the row.

## The coverage audit P/02 (2026-10-30)

The session audit-kimi, commit 82f4da9fc, `АУДИТ-ПОКРЫТИЯ-P02.md`: properties that were formerly checked by reading.
- `toolarge_row` (B01): the same manifest with a comment after which the weight of the main row is above the ceiling 524288 — code 2
  before bringing the mark up to date, the row is the former rev 1 (N3 branch `toolarge`, N4; a counterexample of N5).
- `self_table_list`, `other_table_list`, `list_tables_ok` (B04): catalogue checks with the list form of `tables`, paired with
  `self_table`, `other_table` (chapter 2.1 N3, P/02.1-20).
- `rev_max_same`, `rev_max_changed` (B02): the boundary `rev` = 2^53 − 1 by the directive `@rev-max`: the same file — «unchanged»,
  code 0; a changed one — a refusal before any write, code 2, rev is the former one (N3, N4). The row key and `rev` in stderr — by reading per N4.
- `shell_script_text` (C02-SHELL-TAG-01): `onclick=` in the text of a script, `onload=` in a style, `onclick=` in a comment and `data-on=` are not an attribute `on…=`, the shell is accepted, rev 2; not yet run by an implementation.
- `shell_onclick`, `shell_same_twice`, `shell_changed` (B03): after an installation without a shell (rev 1), the shell `paged.shell.html`
  with `onmouseover=` — code 2 before reading the catalogue, rev is the former 1; a shell appeared — a new revision (absence equals empty),
  the same yaml and shell again — «unchanged» (rev 2); a shell different by bytes (`@shell-put pagedok-alt`) — rev 3 (N1.5, N3). The attribute name in stderr — by reading per N4. The form of the check — check_spec 0021baa83 (the Architect).

## The coverage audit P/02, second pass (Gemini)

The report `АУДИТ-ПОКРЫТИЯ-GEMINI-P02.md` (branch gemini/audit-coverage, c698f3291): catalogue checks that were formerly done by reading.
- `requests_ok`, `requests_missing_target`, `requests_target_no_requests`, `requests_target_drops_requests` —
  `worker.requests` (chapter 2.1 N3 «load_catalogue»): a target with the section `requests` — accepted; there is no target — code 2
  (requests have no deferral as `near`, `creates`, `uses` have: the target is installed earlier, P/02.4 N1.7 `order`); a target without
  `requests` — code 2; a target that removed `requests` on an update — code 2, its row is the former rev 1 (the catalogue is checked
  as a whole with the candidate).
- `creates_target_secret_default`, `creates_target_after_secret_default` — rule 4 of `worker.creates`: an optional field
  `*_secret` of the target with `default` (the file `target-secret-default` differs from `target` by one `default`) — code 2 with the target
  earlier and at the installation of the target after the customer.
- `near_bad_of`, `near_target_after_bad_of` — a field `near.of` that `near.sub` does not have, with a correct `near.prefer`
  (paired with `near_bad_field`, `near_target_after_mismatch`).
- `uses_owner_after`, `uses_owner_after_mismatch` — the owner of a share after the consumer: the share is declared — accepted, it is not — code 2
  at the installation of the owner (paired with `target_after_customer`, `target_after_customer_mismatch`).
- `os_name_*` — the OS names of the catalogue (P/02.4 N1.1 `users_groups` names): the group `w2c-<sub>controller` with a name of 18 characters —
  exactly 32, accepted; of 19 — 33, code 2; the user of a part `<dep>-pbox-<24-character part>` — 33, code 2; the subsystem
  `store` — the user `<dep>-store` coincided with the platform group `w2c-store`, code 2; the part `belt` and the share `belt` without
  `part` — the user of the part and the group of the share `<dep>-psub-belt` coincided, code 2; a share with `part: belt` has no group of its own —
  accepted. The deployment of the installer is the default `w2c` (P/02.4 N1.2; the command `manifest-put` of the «Stand» does not receive a deployment
  name): `os_name_platform_clash` and the lengths of the users are computed with it; the controller group is `w2c-…` with any.

Bringing up to date a removed mark `/rev` in the branch «unchanged» and the refusal on a mark not by the form — the acceptance of chapter 2.2 (`rev_deleted`,
`rev_spoiled`; the directives `@rev-delete`, `@rev-spoil` — the Architect's decision, only with the four columns of chapter 2.2).
