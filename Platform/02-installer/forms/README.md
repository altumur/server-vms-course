# P/02 forms and seams for the generated kit

This English text is the source; `ru/forms/README.md` is its Russian translation for people, not in the export (ADR-0121).
The forms express the existing norms of P/02 (ADR-0125 addendum (5)); they introduce no HTTP door for the installer.

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

The separator is a literal TAB. Lines starting with `#` are comments; the first other line is the header. Every row has fifteen cells.
`name` is unique snake_case; `chapter` is `2.K`; `row` is the original 1-based row of that chapter’s Н4 catalogue, not a new normative id.
`surface` is one of `call` (a pure procedure), `cli`, `start`, `process` (a running process), `peer` (a check whose owner is another lesson).
`code` is `exit N` with a decimal integer N >= 0, `exit !0` (any nonzero code, including 2), or `-` (no numeric code prescribed here).
`kind`, `fields`, `headers` are `-`: P/02 has no HTTP response body schema. In particular, a `peer` row does not invent a P/02 HTTP door.
`word` is a fixed refusal/diagnostic token, or `-`. `log` is a comma-separated list of required diagnostic subjects or fixed fragments in
`«…»`; `-` means no requirement here. Neither `word` nor `log` defines an otherwise unspecified stdout/stderr representation.

The four last cells retain the former normative prose table, whole: condition, outcome, diagnostic rule, caller action. Generators use the
closed columns; they MUST NOT infer branches, fields or additional validation from these four prose cells. The Н4 text links to this form
and does not keep a second catalogue. No OpenAPI lookup is required for a lesson without HTTP. Validation checks that every chapter links
this catalogue, `(chapter,row)` addresses are consecutive in their chapter, names are unique, and the closed cells agree with their
preserved source cells. A specified code/word cannot be broadened merely because the source cell uses prose.

Examples (TABs in the actual TSV): `2.1 / 1 / load_text / call / - / word refused:text`; `2.3 / 2 / manifest_changed / process / exit 0`;
`2.4 / 14 / secrets_unknown_family / cli / exit 1 / word unknown-row-form`. The exit-0 control outcome is not a failed installation.

## Stage gates

[`stages.tsv`](stages.tsv) is a plan, not a behavior norm (ADR-0126). `verdicts:2.1:*` selects the first column of `verdicts.tsv`;
`puts:2.2:*` and `puts:2.3:*` select `puts.tsv`; `accept` selects only `scenarios.tsv`. Comma-separated names select exact rows;
`*` selects the full target, including its other published variants. A generated projection does not claim execution of excluded steps.
`tests:2.K:<scenario,...>:seams` selects the seams below. A `build` gate confirms a build; the checklist still judges installation,
units, TLS, external clients and operator windows by their named methods. It does not convert those checks to passed execution.

## Non-HTTP seams: exact request and expectation grammar

The file is `acceptance/K/seams.tsv`. Its non-comment header is `scenario<TAB>step<TAB>request<TAB>expect`; each scenario has consecutive
steps starting at 1 and a fresh adapter instance and temporary root. The runner does not read seams. They are input to kit stagetests.
A word is a nonempty sequence without ASCII whitespace. Paths are relative to the scenario root, without `..`; `inputs/…` names a fixture
relative to this chapter’s acceptance directory. There is no shell evaluation, interpolation or execution of a command string.

* `RUN <process> <word>… [<<inputs/<file> | <<$<name>]` calls the command function in process with this argv. An optional final stdin
  suffix supplies exactly the fixture bytes or the string previously bound to `$<name>`. The suffix is not part of argv. RUN does not
  spawn an OS process in generated tests. Examples: `RUN w2cctl secrets new keys/ring.json`; `RUN w2cctl rights -deployment dep`.
* Its expectation is `exit <N|!0>` followed optionally by ` stdout <JSON>` and then optionally by ` stderr ~<fragment>` in this order.
  `N` is decimal without a sign; `!0` means nonzero. Only a stated stream is checked. `stdout` is parsed as one JSON value and compared by
  the common acceptance rules (objects by subset; `{}` exactly empty; markers and bindings as below). `stderr ~` means substring.
  If `stdout` is present, its JSON value ends by the JSON decoder, not by splitting on spaces; a trailing `stderr ~` is then recognized.
  Example: `exit 2 stderr ~ring.json`. A nonzero code does not by itself make a crash a valid refusal: the command must return normally.
* `CALL <name> <JSON>` invokes a lesson adapter function; the JSON value consumes the rest of the request. Its expectation is one JSON
  value, compared by the same subset/empty-object rules. It is a normalization for tests, not a required public implementation API.
  Supported names and shapes in this lesson are listed below. Examples: `CALL load {"source":"a.yaml","text":"name: a\n"}`;
  `CALL rollout-poll {"input":{"last":false,"self":"a","voters":["a","b"],"members":{"a":"h-a","b":"h-b"}},"events":[]}`.
* `@file <path> inputs/<file>` writes those fixture bytes below the scenario root; expectation `ok`. Directories are created there.
* `@read <path>` returns the UTF-8 file bytes as a JSON string, even for a file whose contents are JSON. Expectation is a JSON string,
  a string binding `"$name"`, or the unquoted marker `@absent` for no file. Missing/unreadable is not an arbitrary empty string.
  Reusing `"$name"` compares the exact bytes captured by its first occurrence. Non-UTF-8 file tests need a separate explicit codec.
* `@parallel K` (K >= 2) applies only to the next RUN or CALL. The directive expects `ok`; the following expectation is
  `each <expect>` or `one <expect>; rest <expect>`. All K calls share that scenario’s adapter/root; calls finish before the next step.
  Variables are bound only by the single `one` result; `each` and `rest` may refer to existing bindings. Prefix projection stops at an
  unsupported request; it never skips a step and resumes. The inventory names exclusions, and an empty selected projection is an error.

A marker such as `@absent` is outside JSON; a JSON string with those characters is a file value. Fixtures are owned synthetic test data.
A native command’s implementation-specific output is not constrained when its norm leaves that output open.

### CALL normalization

* `load`: input `{source: string, text: string}`. Call the regular loader on exactly these bytes. Success returns
  `{verdict:"ok", name:<loaded name>}`; refusal returns `{verdict:"refused", class:<text|form|relations>}`. No partial manifest is returned.
* `load-catalogue`: input `{manifests:[{source:string,text:string},…]}`. Load those manifests by the same loader and check their complete
  set with `load_catalogue`. Success returns `{verdict:"ok", names:[…]}` with names sorted only by the test adapter; a refusal returns
  `{verdict:"refused", class:<text|form|relations|catalogue>}`, without names or a partial catalogue. No implicit stand manifest is added.
* `rollout-poll`: input `{input:<machine input>, events:[{t:<seconds>,event:<trace event string>},…]}`. The names, event syntax, timer
  ordering and optional `input.const` overrides are those of [`rollout-poll.machine.yaml`](rollout-poll.machine.yaml) and its
  [`rollout-poll.traces.tsv`](rollout-poll.traces.tsv). A fresh poll starts at t=0. Advance the virtual clock through each event (timers
  first at equality), then deliver that event; `advance` only advances timers. Observe the final state and refusal:
  `{state:<polling|passed|refused>, result:null|{code:<integer>,word:<string>}}`. Extra observations may be returned. The adapter calls the
  implementation’s poll, not the course interpreter as a substitute. Events contain no expected state, verdict, assertion or output.

The source traces judge the complete state machine. The seam samples do not prove the OS rollout, membership availability or all barriers.
