# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/3/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

[`02.3-installer.norms.md`](../../spec/02.3-installer.norms.md) N5. `puts.tsv` has 87 installations (9 after `near_*` — the coverage audit P/02 of 2026-10-30, the next 16 — its second pass, below; the 11 next ones — ADR-0094 B7; 3 `calls_*` — the callback list at a subsystem of the catalogue, ADR-0094 B1; 3 `calls_requests_*` — the entry `<s>/requests` of another subsystem (it is in the catalogue without `requests` — accepted; it is absent — a deferral) and of the own one, P/06.3 N1.9 (review of lesson P/02, S5); 3 `calls_first_*`, `calls_second_kind` — ADR-0112 addendum (3) item 2; the last two `calls_pulse_ok`, `calls_pulse_bad` — the declared heartbeat callback); the installation files are in `puts/`.

### Original passage 2

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

### Original passage 3

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

### Original passage 4

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
