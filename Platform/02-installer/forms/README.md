# P/02 forms and seams for the generated kit

This English text is the source; `ru/forms/README.md` is its Russian translation for people, not in the export.
The forms express the existing norms of P/02; they introduce no HTTP door for the installer.

## Command options

`daemon-flags.tsv` keeps the eight columns of P/01: `flag`, `type`, `default`, `default_text`, `required`, `commands`, `bad`, `norm`.
Here `commands` names ids from [`operator-commands.tsv`](operator-commands.tsv), comma-separated. An option belongs only to those commands.
The value types are `string`, `number` (finite), `file`, `bool`; `required` and `bad` are CEL over the supplied options `f` and command id `cmd`.
No default is `-`. A missing bool is false; a supplied bool is true. These are command arguments, not daemon flags or environment variables.

`operator-commands.tsv` columns are `command`, `process`, `prefix`, `positionals`, `norm`. `prefix` is a JSON array of fixed argv words;
`positionals` is JSON Schema 2020-12 over the remaining positional words after option parsing. The form does not choose a shell lexer,
an output format, an exit code on unspecified input, or a new interface for commands delegated to another lesson.

## Refusal catalogue

[`refusals.tsv`](refusals.tsv) has these columns, in order:

```text
chapter row name surface code kind fields headers log norm word cause outcome diagnostic caller
```

The separator is a literal TAB. Lines starting with `#` are comments; the first other line is the header. Every row has 15 cells.
`name` is unique snake_case; `chapter` is `2.K`; `row` is the 1-based number of the row within its chapter (the address «N4 row N» of the column `norm`), not a normative id.
`surface` is one of `call` (a pure procedure), `cli`, `start`, `process` (a running process), `peer` (a check whose owner is another lesson).
`code` is a three-digit HTTP status for a `peer` outcome, `exit N` with a decimal integer N >= 0, `exit !0` (any nonzero code, including 2), or `-` (no numeric code prescribed here).
`kind`, `fields`, `headers` are `-`: P/02 has no HTTP response body schema. In particular, a `peer` row does not invent a P/02 HTTP door.
`word` is a fixed refusal/diagnostic token delimited by backticks, or the unquoted `-`; delimiters are not part of the token. `log` is a comma-separated list of required diagnostic subjects or fixed fragments in
`«…»`; `-` means no requirement here. Neither `word` nor `log` defines an otherwise unspecified stdout/stderr representation.

The four last cells carry the normative prose of the refusal, whole: condition, outcome, diagnostic rule, caller action. Generators use the
closed columns; they MUST NOT infer branches, fields or additional validation from these four prose cells. The N4 text links to this form
and does not keep a second catalogue. No OpenAPI lookup is required for a lesson without HTTP. Validation checks that every chapter links
this catalogue, `(chapter,row)` addresses are consecutive in their chapter, names are unique, and the closed cells agree with their
preserved source cells. A specified code/word cannot be broadened merely because the source cell uses prose.

Examples (TABs in the actual TSV): ``2.1 / 1 / load_text / call / - / word `refused:text` ``; `2.3 / 2 / manifest_changed / process / exit 0`;
``2.4 / 14 / secrets_unknown_family / cli / exit 1 / word `unknown-row-form` ``. The exit-0 control outcome is not a failed installation.

## Internal finite deletion profile

`finite-profile.schema.json` is the exact internal typed record, not manifest keys, flags or acceptance.yaml. P/02.3 N3 checks it after installation step6 before step7/all writes (including unchanged), and at Process start before doors. Missing/unreadable limits retain the existing refusal; an insufficient profile is `refused:form`.

`finite-profile.cases.json` (judge-only: the profile witnesses; they check P/02.3 N3 «Internal finite deletion profile», «Process start» step 3a and «Manifest change» step 6a — P/02.3-R048, P/02.3-R053, P/02.3-R094, P/02.3-R141, P/02.3-R145, P/02.3-R146, P/02.3-R149, P/02.3-R151, P/02.3-R153, P/02.3-R157, P/02.3-R159, P/02.3-R163, P/02.3-R164) binds witnesses to those existing entries. Its owned_context is an independent finite synthetic universe of packet shapes and metadata skeleton proofs; it does not attest completeness of production procedures. The source judge must reject missing/duplicate packets, short H/multiplicities, unknown provenance and wrong effective limits. Schema acceptance and free strings do not prove this. Actual descriptors must additionally cover every emitted packet, mixed batches and other auxiliary families. Expected answers/bounds never enter the implementation input. Source/form/codec checks are not installer/native/SUT execution or a pin update. The witness count, the bound of the universe and the codec boundaries are in [judge-only case data](README.cases.md) (judge-only: the case data of the profile witnesses; they check P/02.3 N3 «Internal finite deletion profile» — P/02.3-R141, P/02.3-R145, P/02.3-R146, P/02.3-R149, P/02.3-R151, P/02.3-R153, P/02.3-R157, P/02.3-R159, P/02.3-R163, P/02.3-R164).

The metadata encoding, the byte proofs and the skeleton sizes of the judge's owned context are in [judge-only case data](README.cases.md) (judge-only: the case data of the profile witnesses; they check P/02.3 N3 «Internal finite deletion profile» — P/02.3-R141, P/02.3-R145, P/02.3-R146, P/02.3-R149, P/02.3-R151, P/02.3-R153, P/02.3-R157, P/02.3-R159, P/02.3-R163, P/02.3-R164).

## Stage gates

[`stages.tsv`](stages.tsv) is a plan, not a behavior norm. `verdicts:2.1:*` selects the first column of `verdicts.tsv`;
`puts:2.2:*` and `puts:2.3:*` select `puts.tsv`; `accept` selects only `scenarios.tsv` (judge-only: the corpus and acceptance tables of the chapters; `verdicts.tsv` of chapter 2.1 checks P/02.1-R008, P/02.1-R013, P/02.1-R018, P/02.1-R020, P/02.1-R024, P/02.1-R026, P/02.1-R027, P/02.1-R028, P/02.1-R030, P/02.1-R033, P/02.1-R034, P/02.1-R036, P/02.1-R038, P/02.1-R041, P/02.1-R043, P/02.1-R047, P/02.1-R048, P/02.1-R049, P/02.1-R054, P/02.1-R055, P/02.1-R056, P/02.1-R058, P/02.1-R059, P/02.1-R062, P/02.1-R064 to P/02.1-R068, P/02.1-R070, P/02.1-R072, P/02.1-R074, P/02.1-R076, P/02.1-R078, P/02.1-R083, P/02.1-R086, P/02.1-R088, P/02.1-R092, P/02.1-R094, P/02.1-R099, P/02.1-R104, P/02.1-R108, P/02.1-R113, P/02.1-R115, P/02.1-R126, P/02.1-R127, P/02.1-R128, P/02.1-R131, P/02.1-R134, P/02.1-R136, P/02.1-R139, P/02.1-R141, P/02.1-R153, P/02.1-R155, P/02.1-R182, P/02.1-R198, P/02.1-R201, P/02.1-R206, P/02.1-R213, P/02.1-R215, P/02.1-R236; `puts.tsv` of chapter 2.2 checks P/02.2-R026, P/02.2-R027, P/02.2-R032, P/02.2-R034, P/02.2-R041, P/02.2-R044, P/02.2-R047, P/02.2-R048, P/02.2-R050, P/02.2-R051, P/02.2-R054, P/02.2-R055, P/02.2-R060, P/02.2-R061, P/02.2-R073 to P/02.2-R075; `puts.tsv` of chapter 2.3 checks P/02.1-R049, P/02.1-R061, P/02.1-R095, P/02.1-R099, P/02.1-R105, P/02.1-R106, P/02.1-R107, P/02.1-R108, P/02.1-R109, P/02.1-R110, P/02.1-R112, P/02.1-R113, P/02.1-R115, P/02.1-R116, P/02.1-R119, P/02.1-R122, P/02.1-R123, P/02.1-R124, P/02.1-R133, P/02.1-R147, P/02.1-R158, P/02.1-R159, P/02.1-R161, P/02.1-R164, P/02.1-R165, P/02.1-R166, P/02.1-R167, P/02.1-R168, P/02.1-R169, P/02.1-R172, P/02.1-R174, P/02.1-R178, P/02.1-R179, P/02.1-R182, P/02.1-R193, P/02.3-R081, P/02.3-R082, P/02.3-R085, P/02.3-R087, P/02.3-R090, P/02.3-R102, P/02.3-R103, P/02.3-R105 to P/02.3-R107, P/02.3-R114, P/02.3-R171; `scenarios.tsv` of chapter 2.5 checks P/02.5-R005, P/02.5-R007, P/02.5-R008, P/02.5-R011, P/02.5-R013, P/02.5-R015, P/02.5-R018, P/02.5-R020, P/02.5-R023, P/02.5-R025, P/02.5-R026, P/02.5-R029, P/02.5-R031, P/02.5-R036, P/02.5-R038, P/02.5-R042, P/02.5-R044, P/02.5-R046, P/02.5-R049, P/02.5-R051, P/02.5-R053, P/02.5-R054, P/02.5-R058, P/02.5-R061, P/02.5-R062, P/02.5-R063, P/02.5-R064, P/02.5-R065, P/02.5-R066, P/02.5-R067, P/02.5-R068, P/02.5-R069, P/02.5-R070, P/02.5-R075, P/02.5-R076, P/02.5-R078, P/02.5-R081, P/02.5-R082, P/02.5-R087, P/02.5-R091, P/02.5-R092, P/02.5-R093, P/02.5-R094, P/02.5-R095, P/02.5-R097, P/02.5-R102, P/02.5-R108, P/02.5-R133). Comma-separated names select exact rows;
`*` selects the full target, including its other published variants. A generated projection does not claim execution of excluded steps.
`seams:2.K:<scenario,...>` selects the seams below ([`stages.kit.tsv`](stages.kit.tsv) writes the same selection
`tests:2.K:<scenario,...>:seams`; judge-only: the kit projection of the stage plan, not a norm). The `norms` column places each item of the readiness checklists of `spec/*.norms.md` at exactly one
stage; the items of the system checklists stand at no stage. A `build` gate confirms a build; the checklist still judges installation,
units, TLS, external clients and operator windows by their named methods. It does not convert those checks to passed execution.

## Non-HTTP seams: exact request and expectation grammar

The file is `acceptance/K/seams.tsv`. Its last comment header is `# scenario<TAB>step<TAB>request<TAB>expect`; each scenario has consecutive
steps starting at 1 and a fresh adapter and temporary roots. Runner execution uses the [common seam adapter protocol](../../common/acceptance/seams.md#seam-adapter-protocol); kit stagetests remain auxiliary, not process acceptance. A stand path starts with
`$data/`, `$run/` or `$manifest/` and is below that scenario’s data, run or manifest root, without `..`. `inputs/…` is a fixture path relative
to the acceptance directory. No shell is evaluated.

* `RUN <process> <word>… [<<inputs/<file> | <<$<name>]`: words are separated by one ASCII space. A word is either an unquoted word without
  whitespace or a double quote, or a JSON string decoded to one argv element. A final stdin suffix supplies exactly those fixture bytes or
  the previously bound string and is removed from argv. Kit tests call the command function in process, without spawning an OS process.
  Example: `RUN w2cctl manifest put $manifest/bad.subsystem.yaml`.
* Its expectation is `exit N`, optionally followed by `; stdout <JSON>`, `; stdout-text <JSON string>`, `; stderr ~<JSON string>` in that order.
  N is a decimal nonnegative integer. Only named streams are checked: stdout JSON by the common subset/empty-object rules, stdout-text
  by exact decoded UTF-8 bytes, stderr by substring. Example: `exit 2; stderr ~"bad.subsystem.yaml"`. A command must return normally;
  a crash is not a valid refusal. Where the norm fixes only nonzero, CALL `command` below observes success without inventing an exact code.
* `CALL <name> <JSON>`: the name is `[a-z][a-z0-9-]*`; the JSON consumes the rest. Its expectation is JSON by the common acceptance rules
  (objects by subset, `{}` exactly empty, string bindings and markers), or a published `@absent` / `@exit 2`. This is test normalization,
  not a mandatory implementation API. A function with no published marker does not acquire one from this grammar.
* `@file <stand path> inputs/<file>` or `@file <stand path> <JSON string>` writes those exact fixture/decoded UTF-8 bytes; it first creates the
  missing directories of the stand path. Expect `ok`.
* `@read <stand path>`: expect JSON for a parsed JSON file, `text <JSON string>` for exact UTF-8 bytes, or `@absent` for a missing file.
  An unreadable file fails. `text "$name"` binds the bytes first, then compares that same value on reuse. JSON strings in JSON mode are
  parsed JSON values; text mode never parses the file contents as JSON. There is no implicit empty value for absence or an IO error.
* `@parallel K` (K >= 2) applies to the next RUN or CALL; expect `ok`. That next expectation is `each <expect>` or
  `one <expect>; rest <expect>`. All K calls share the scenario’s adapter and roots and finish before the following step. Only the single
  `one` result may bind new variables; `each` and `rest` may refer to existing ones. Each nested expectation uses the underlying RUN/CALL
  grammar. Prefix projection stops at an unsupported step; the inventory names all exclusions, and an empty selected projection is an error.

Fixtures are owned synthetic data. A native command’s implementation-specific output is not constrained when its norm leaves it open.

### Scenario layout

A command called by RUN or CALL gets the layout of P/02.4 N1.2 with `PLATFORM_DIR` = `$data`: the stand layout of the
[common acceptance](../../common/acceptance/README.md) with `{data}` = `$data`. For the placement check of the
[secret files contract](../../common/contracts/secret-files.md) (`forbidden`, `layout`) the forbidden directories are exactly two:
the store directory `$data/configstore` and the object root `$data/objects`; no copy directory is set. The adapter makes these two
directories exist before it invokes a command (it creates them empty, an existing one is kept) and names them to the command by
this layout; it looks for no other forbidden directory. A seam never requires a command to create a directory: every directory of a
target path exists before the call — a root, one of these two directories, or a directory made by an earlier `@file` step of the
same scenario. An absent directory of the path is a refusal of the command (`refuse` of the contract), not a fixture to repair.

### CALL normalization

* `command`: input `{argv:[<process>,<argument>,…]}`. Invoke that command function with the scenario roots, resolving stand paths in argv. Return `{success:<exit code == 0>}` and optionally `exit_code`. The function must return normally; do not convert a panic, exception or signal into a refusal. This is used only for outcomes whose norm sets zero versus nonzero without an exact refusal code.
* `load`: input `{source: string, text: string}`. Call the regular loader on exactly these bytes. Success returns
  `{verdict:"ok", name:<loaded name>}`; refusal returns `{verdict:"refused", class:<text|form|relations>}`. No partial manifest is returned.
* `load-catalogue`: input `{manifests:[{source:string,text:string},…]}`. Load those manifests by the same loader and check their complete
  set with `load_catalogue`. Success returns `{verdict:"ok", names:[…]}` with names sorted only by the test adapter; a refusal returns
  `{verdict:"refused", class:<text|form|relations|catalogue>}`, without names or a partial catalogue. No implicit stand manifest is added.
* `rollout-poll`: input `{input:<machine input>, events:[{t:<seconds>,event:<trace event string>},…]}`. The names, event syntax, timer
  ordering and optional `input.const` overrides are those of [`rollout-poll.machine.yaml`](rollout-poll.machine.yaml) and its
  [`rollout-poll.traces.tsv`](rollout-poll.traces.tsv) (judge-only: the source traces of the poll machine; they check P/02.4-R321). A fresh poll starts at t=0. Advance the virtual clock through each event (timers
  first at equality), then deliver that event; `advance` only advances timers. Observe the final state and refusal:
  `{state:<polling|passed|refused>, result:null|{code:<integer>,word:<string>}}`. Extra observations may be returned. The adapter calls the
  implementation’s poll, not the course interpreter as a substitute. Events contain no expected state, verdict, assertion or output.

The source traces judge the complete state machine. The seam samples do not prove the OS rollout, membership availability or all barriers.
