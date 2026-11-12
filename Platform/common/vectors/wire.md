# Vector wire form

This English text is the source; the Russian translation `ru/vectors/wire.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124).

The norm is [`wire.tsv`](wire.tsv) together with `wire.cases.tsv`, by the Architect’s decision under ADR-0125 addendum (1) item 5 and addendum (5): one form in two files with one grammar. `wire.cases.tsv` holds the rows whose cells carry values taken from the judge-side case tables, such as the case names or the input values of those tables, and it is judge-side. A reference to a field of the row by its column name, or a word of the closed vocabulary of the package, is no such value: a row with only such references stays in `wire.tsv` (the Architect's answer on the review P01.87). The triple `(package,table,surface)` is unique across both files (the Architect's answer on P01.86). The initial slice covers the vector tables of P/01 and P/02; subsequent declared rows extend the registry. A missing binding is an undeclared adapter, never a performed test. The write-checks probes in P/01 forms are judged by their own check table and probes grammar, through the envelope of [P/01 write-checks transport](#p01-write-checks-transport) below, a row of the form [`probe-tables.tsv`](probe-tables.tsv); they have no row in this form. The package README retains the algorithm, consumer obligation, meaning of the inputs and native fields, and reading or stand checks outside the function. It refers to this form for the wire, without a second wire declaration.

## Rows and sources

```text
package	table	surface	header	inputs	files	expect	compare	markers	native	norm
```

Literal TAB separates the columns, without CSV quoting. UTF-8 and LF; empty lines and lines beginning with `#` are skipped; the first other line is the header. The triple `(package,table,surface)` is unique. `package` is a path from Platform without vectors/; `table` is an existing TSV filename in that package. `norm` is an existing source `.md` path from Platform, optionally followed by `#` and an existing heading anchor.

`surface` is `vectors`, `stand:<key>` of a process profile, or `layout`. The latter is explicitly excluded from function execution: `inputs`, `expect`, `markers` are `[]`, `files` is `{}`, `compare` and `native` are `-`. It does not prove the layout check and is never a function PASS.

`header` lists column names in source order, separated by commas. Without a source header its first item is `-`, followed by positional names, for example `-,raw,masked,note`. The actual header or positional field count must agree. A quote in any source TSV cell is a byte of the cell, never CSV syntax.

`inputs`, `files`, `expect`, `markers` and non-layout `native` are strict JSON in one cell. Duplicate JSON keys, BOM, NaN and Infinity are errors. The unified command envelope and the existing stand templates remain those of [the common acceptance README](../acceptance/README.md).

## Input selection and groups

```text
{"variant":"","when":"true","case":"case","cells":{"input":{"column":"input"}}}
```

`inputs` is a nonempty array of declarations. Each has a string `variant` (empty, read, write, or another published name), optional boolean CEL `when` (default true), optional `case`, and exactly one of `cells` or `arg_file`. CEL inputs are `row: map<string,string>` and `owner: string`, with the strings extension. Source cells retain their exact strings. `owner` is a lesson directory. For common packages it must be assigned by `consumers.tsv`; a condition cannot add a foreign consumer. Native function form checks belong to the adapter, not the selector.

The consumer set is the explicit rows of consumers.tsv, united with the owner lesson of a lesson-local package. Its package column is the full `(common|NN-name)/name` path from Platform without vectors/, exactly as in wire.tsv; NN-name must be a lesson directory in lessons.tsv. Common packages have no implicit lesson. Duplicate (package, table, lesson), an unknown lesson, package or table is a form error. A when cannot add a foreign consumer. The cross-lesson rows for JCS, rid, request-digest and requests-body record their already published README duties; they introduce no new function assignment. For requests-body, only the worker request rows use the native function binding; the console keeps its separate complete HTTP stand duty.

Selection is per variant: at most one input declaration of a variant can select a row. A selected variant has exactly one expectation and native declaration. A both direction can select two variants; a foreign owner or direction selects none, and its row is absent from the inventory of the target: there is no closed outcome for an excluded row. Absence of a declaration is never PASS. Variants follow declaration order in calls and inventory; it is not algorithm priority.

`case` is a column name, `{"line":true}` for the physical `line-<number>`, or `{"literal":"name"}`. Its default is the case column, then id, otherwise the physical line. A run identity `(owner,package,table,surface,variant,case)` must be unique: duplicates are errors, without an added line suffix. This identity is not an algorithm input.

For `vectors`, `cells` maps wire cell names to exactly `{"column":"name"}` or `{"literal":"string"}`. Every result is a string: a raw source cell or literal, without decoding, re-encoding, or expectations. In particular a rotate flag is the string `"true"`.

For `stand:<key>`, `arg_file` is exactly `{"column":"name"}`, `{"literal":"text"}`, or `{"path_column":"input","base":"root"}`. The first two write exact UTF-8 bytes to a temporary file; the last resolves an existing fixture. The profile template gets its path in `{input}`. `files` must be `{}` on this surface: no sidecar transport is implied. The form contains no shell commands.

Optional `group_by` is an array of column names: absent means per row, `["list"]` groups equal list values, `[]` forms one group of the selected table. Filter by input when first, then group, then call once per group and variant. Group keys sort by UTF-8; rows retain source order. All row-based `when` evaluations in an expectation, native descriptor or file declaration must agree across every row of a group. A cell, case or substituted path from a column must be constant across the group. There is no implicit first-row rule.

The inventory of grouped calls is [P/AC-R008](../acceptance/spec/acceptance.norms.md#n14-verdict-of-a-target); target surfaces and callable interfaces are [P/AC-R006](../acceptance/spec/acceptance.norms.md#n13-target-registry) and [the target form](../acceptance/runner-targets.README.md).

## Fixtures and values

```text
{"in.yaml":{"base":"package","path":"inputs/{id}.yaml","when":"true"}}
```

`files` maps fixture basenames to objects with `base`, `path`, and optional `when`. Base `package` is the package directory, `root` is the export root. Paths allow `{column}` substitution. Only paths resolving inside the export are allowed, including a relative parent component that remains inside it. Missing or unreadable files, absolute paths, and escaping the export are preflight errors. Copy fixture bytes exactly. Expected output fixtures never enter this mapping.

`expect` is an array of declarations with `variant`, optional `when`, `code` (native integer exit code in 0..255), `value` and optional `assert`. The code is the decoded exit_code for vectors, and the command exit for stand; the outer vectors wrapper still exits 0. A ValueExpr has exactly one constructor from the following closed list.

```text
{"column":"expect","decode":"cell|json|text"}
{"literal":<JSON value>}
{"object":{"field":<ValueExpr>}}
{"array":[<ValueExpr>]}
{"file":{"base":"package|root","path":"expect/{case}.json"},"decode":"bytes|text|json"}
{"file":{"base":"package|root","path_column":"expect"},"decode":"bytes|text|json"}
{"group":{"column":"word","decode":"text|json|cell"}}
{"groups":{"by":"list","column":"word","decode":"text|json|cell"}}
{"suffix":true,"decode":"text|json|cell"}
{"omit":true}
{"at":{"value":<column or literal ValueExpr>,"pointer":"/tags"},"decode":"json"}
```

`text` preserves the cell as a string. `json` requires exactly one strict JSON value. `cell` reads strict JSON when it is JSON, otherwise the original string. Text is required for string domains such as hex keys, seeds or unquoted names that can look like JSON. Mixed JSON and raw words are allowed only by the published native form and checked against native type/schema, not guessed as a universal conversion.

A `file` is a judge-side expected fixture, with the same path safety rules; bytes means exact file bytes, text means strict UTF-8, json means strict JSON. `group` collects the values of the current group; `groups` builds an object keyed by its by column. Both require group_by. `suffix` is only the remainder of a matched prefix marker. `omit` is only an object field omission, never a root value and never null. These constructors read data and do not compute the implementation’s algorithm.

## Comparison and assertions

The closed `compare` list is `value|subset|raw|set|object-sets|lines-value|lines-subset|turn`; `-` is only layout. It can be a single string or an object from variant names to such strings. Value compares JSON by value with types preserved (numeric 1 equals 1.0, boolean is not a number). Subset compares object fields recursively; an empty object at any depth is exactly empty, never any object. Raw compares native bytes, or UTF-8 bytes of a decoded native JSON string. Set compares an array as a set of JSON values, ignoring order and repeats. Object-sets requires exactly the expected object keys and set comparison of each array value. Lines-value and lines-subset compare complete JSON Lines in order with a final LF required. Turn is restricted to the binding and whole-value comparison below; it is not an assertion comparison or a general holder alias.

```text
{"pointer":"/row","test":"prefix","value":{"literal":"enc:v2:"}}
{"pointer":"/plaintext","test":"absent"}
{"pointer":"/text","test":"no-leak","value":{"array":[{"literal":"fixture-password"}]},"min_bytes":4,"whole":true}
{"pointer":"/row","decode":"json","compare":"value","value":<ValueExpr>}
```

`assert` is an array over the native response. Pointer is JSON Pointer. The closed `test` list is `prefix|absent|no-leak`. Prefix requires a string with the exact prefix; absent requires the pointer not to exist. Without test, compare the pointer value by the given compare, defaulting to the binding comparison without lines modes. Optional decode json parses JSON inside a string field, not the wire frame. A missing pointer fails except for absent. Assertions do not enter the SUT input. The Architect’s no-leak assertion has `pointer`, `test` set to no-leak, `value` (a string or array of secret strings) and `min_bytes` (an integer at least 1). The UTF-8 text at the pointer must contain no substring of any secret whose length is at least min_bytes bytes. An optional boolean `whole` (default false) is allowed only for no-leak: false forbids any such fragment; true forbids an occurrence of the whole secret only when its full UTF-8 length is at least min_bytes (shorter secrets are not judged). Secret-in P/03 and P/06 use whole true under their README Run item 3. This is an output assertion, never a secret input to the implementation.

## Markers and native framing

```text
{"variant":"","column":"expect","match":"@exit 2","code":2,"ignore_stdout":true}
{"variant":"write","column":"row","match":"@refuse ","prefix":true,"code":0,"compare":"subset","value":{"object":{"status":{"literal":"refused"},"fault":{"suffix":true,"decode":"text"}}}}
```

`markers` is an array in match priority order. Match is against the raw column and exact variant, before decoding; default match is whole-cell, prefix true matches its exact prefix and exposes suffix. The first match may override code, ignore_stdout, value, compare and assert. A JSON-quoted marker is ordinary data. Without an explicit declaration an at-sign word is never inferred as an exit code. In particular refusal/bad/skip markers can be native JSON strings. ignore_stdout true disables stdout content, frame and schema checks, but not the native exit check.

```text
{"type":"object|array|string|number|boolean|null|value|bytes","frame":"json|json-lf|raw","schema":<optional Draft 2020-12 JSON Schema>}
```

`native` is a descriptor or an array of descriptors with variant/when; exactly one applies to a selected input. Type is one listed word or an array of JSON type words; value means any JSON value. Bytes requires raw and no schema. Json allows JSON whitespace around one value. Json-lf requires no bytes before the value and exactly LF and end after it (an object therefore starts with an opening brace); internal JSON formatting is allowed. Parsing is strict, without BOM, NaN/Infinity or duplicate keys. For vectors this is the decoded stdout_b64 payload, not the outer wrapper. Optional schema always checks the complete actual native output, also in subset and lines-subset modes. Static checking of a complete expected value may apply the schema directly; a partial expectation does not have to contain the unmentioned required output fields. Only its declared fields and assertions can be checked statically where their values are known. The schema is data, not an algorithm. An ignored stdout is not parsed.

## Examples in the first slice

The actual rows are executable declarations: log-mask preserves masked text as a decoded JSON string and compares raw bytes; family-read compares paths as a set and reader outcome arrays as sets; sealing ring adds rotate only to installer rotate cases; yaml-suite supplies in.yaml and judges only layer1; canonical resolves an existing manifest and compares expected file bytes. The exec and install-order stand bindings use json-lf and distinguish a native form refusal from their successful rule-refusal object. Platform-lists has two independent bindings: vectors groups by list and returns an array per group; stand:platform-lists groups the whole table and returns an object of sets. Journal modes is layout.

## P/06 transport constructors

These extensions are the Architect's decision under ADR-0125 addendum (5). The argument/file and ValueExpr lists above are extended only as declared here; all other keys and constructors remain closed.

For stand, `arg_file` also permits exactly `{"json": <ValueExpr>}`. Evaluate the expression as a JSON value and write one JSON document to the argument file. In this constructor, ValueExpr permits only column (text/json/raw-json), literal, object and array; file/group/groups/map/suffix/omit/at are forbidden. Inside this constructor alone, a source-input column may use `decode: "raw-json"`: validate one strict JSON document and insert its original JSON lexeme as a fragment, without normalization or decode/re-encode. This checks JSON syntax, not the native function's accepted form: a non-string rid still reaches that function. No expectation column may enter an argument file. The ordinary decode json remains a decoded value; raw-json is not allowed elsewhere, including expectations and fixtures.

```text
{"json":{"object":{"rid":{"column":"rid","decode":"raw-json"}}}}
{"json":{"object":{"sender":{"column":"sender","decode":"text"},"input":{"column":"input","decode":"text"}}}}
{"map":{"key":"word","value":{"column":"status","decode":"json"}}}
```

ValueExpr `at` has exactly value and pointer inside at, plus optional outer decode. Value is only a column or literal ValueExpr under its existing decoding rules; nested at and all other constructors are forbidden. Pointer is a nonempty RFC 6901 JSON Pointer starting with `/`; invalid escapes and a missing selected path are form-data errors. Select that value from the decoded source, then optionally apply the outer `decode: "json"`, which requires the selected value to be a string and parses exactly one strict JSON document. No other outer decode is allowed. This constructor is allowed only in expectations, assertions and markers, never in input cells or arg_file.json. When value is a column, static form checking also resolves the pointer against the actual table rows. For example, a row-check expectation can select the JSON string at `/tags` from its row column without copying a second golden array:

```text
{"at":{"value":{"column":"row","decode":"json"},"pointer":"/tags"},"decode":"json"}
```

ValueExpr `map` has exactly key (a source column) and value (a ValueExpr), and requires group_by. On each row of the current group, use the raw key cell as the object key and evaluate value on that row. A repeated key is a data error even for equal values. Object order is not significant; the constructor does not run an implementation algorithm.

An expectation and an assertion without test may declare `ignore: [<JSON Pointer>…]` (a nonempty array). Ignore applies to both expected and actual values before their chosen comparison; native schema checks the complete actual value first. An absent ignored path is allowed. Empty/root, repeated or overlapping pointers are form errors; assertions with test and a direct marker.ignore property are forbidden; an assertion without test inside a marker follows the ordinary ignore rule. Paths are resolved against each original value, so removing an array element does not shift the interpretation of another pointer. For console pool, ignore is exactly ["/fates"], compare value; all other keys remain strict.

CEL when alone also provides `json(string) -> dyn`, one strict JSON document: no BOM, duplicates, NaN or Infinity. Parse failure is a form-data error, never false or a silently omitted test. This selector chooses the consumer operation by input fields, not by an implementation result, and cells still contain the exact source strings. Group when must still agree on every row. Example: `owner == "06-console" && !("salt" in json(row["input"]))`.

The console requests-body binding remains surface layout: it is excluded from native/function generation, not discharged. The separately published and installed C target `P/06/vectors-requests-body` must run the actual store+console HTTP stand over all 77 rows and all 21 accepted-json round trips, by the package README. A worker's 52 native rows do not cover it; no pure native console command or fictional HTTP surface is introduced.

An input column may also be read by an expectation: for example json is the original write input and the expected plaintext after actually opening a sealed envelope, or the read expectation in another variant. Golden output data may not become an algorithm argument; shared references do not make an input golden output. Roles come from the package norm and selected variant, not a union of expectation columns. Neither literal nor cells {} infers grouping: absent group_by still means one call per row. For fault, explicit group_by [] gives one call per whole table. Form validation does not prove that an external HTTP target ran.

## Turn comparison

`compare=turn` is admitted only in the rows that the form [`compare-scope.tsv`](compare-scope.tsv) names for it (judge-only: the scope of the comparison words), now `(common/turn,cases.tsv,vectors)`; the judge reads the scope from that form, not from a package name. The input is the exact `input` cell; the expectation is decoded from `expect`, never passed to the native function. The native output is one JSON array of actions. Array length and order, action types, object key sets and every ordinary value are exact; nothing is ignored. There is no conversion between signer and operations identities.

Only an expected holder mark `@new` or `@same` has the package's published freshness semantics. `@new` requires a nonempty real string distinct from every holder mark previously emitted by this side in this case; it becomes this attempt's mark. `@same` requires that exact current-attempt string. A new case resets the comparison state. A native literal `@new` or `@same` is not a real holder and fails. Empty holder stays exactly empty. Missing/extra fields, wrong cas/version/guard, a stable signer holder substituted for an operations mark, reuse of a previous mark, or an unresolved placeholder fails. The owned adapter substitutes the current-attempt mark for input read placeholders before invoking the ordinary algorithm, without passing expected actions. This is the already published package rule, not a runtime alias.

The only selections are placement for04-controller; signer for08-domain and09-agent; operations for06-console. The `owner` and parsed input `kind` must both match the exact CEL in `wire.tsv`. A foreign owner/kind selects no call, and its row is absent from the inventory of the target; a malformed input is a form error, not a false selector. This form does not infer operations-epoch, two-leader, generation/ticket or late-IO execution from a turn result. Its judge is supplied by the Architect in the joint slice; a source declaration alone is not wire GREEN.

## Scope of the P/06 slice

The P/06 declarations cover every table assigned to 06-console by consumers.tsv and its own lesson tables. Journal modes and requests-body are layout, with their separate process/HTTP duties preserved. Compatible stand and vectors bindings name independent surfaces; they do not claim that a runner publishes both. Other owners receive only the projections explicitly selected in these rows; this slice does not close their whole lessons or their undeclared tables. The native.schema check is over the complete actual answer before comparison ignores. The explicit ignore_stdout true marker alone disables stdout content, frame and schema checks, while retaining the native exit check.

## P/01 write-checks transport

A probe table that lies in the forms of a lesson, not under `vectors/`, and some of whose cells come from the parameter lines of the table has no row in this form. Its envelope of the [unified vector command](../acceptance/PROFILE.md#unified-vector-command) is a row of the form [`probe-tables.tsv`](probe-tables.tsv); the header of the form defines its columns and the closed sources of its cells, and the judge reads the envelope from that row.

The form has one row, the package `01-store/write-checks`. It evaluates [`write-checks.tsv`](../../01-store/forms/write-checks.tsv) by the implementation's own function (P/01.1 N2.1, the order of command and batch checks) over the probe table `Platform/01-store/forms/write-checks.probes.tsv` (judge-only: the probes of the table; P/01.1-R255). Its row says:

- `package` is `01-store/write-checks`, `table` is `write-checks.probes.tsv` (the column `table` of the row; the column `source` is the path of the probe table, whose file name it is), `case` is `line-<physical source line>`, `variant` is `""` and `files` is `{}`;
- `cells` are exactly `sock`, `body`, `lim` and `allow`, strings as P/01.1 N2.1 describes them: `sock` and `body` are the cells of the row; `lim` is one JSON object text for every row, from the `#lim` lines of the probes; `allow` is one JSON array text for every row: each element is one JSON string, the text of one `#allow` line after the word `#allow` and one space (`#allow writer read acc/` gives `"writer read acc/"`), in the order of the lines;
- every row is executed except a row of the case `nopair`, whose body is prose;
- the native output is one JSON object, compared by value: `{"n": 0}`, or `{"n", "code", "kind"}` with the code and kind of row `n` of `write-checks.tsv`.

The profile of `01-store` declares the `vectors` entry `01-store/write-checks`; without it the target is not executed.
