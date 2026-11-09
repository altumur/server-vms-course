# The layers of V7: the standard and our own remainder

This English text is the source; the Russian translation `ru/LAYERS.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The form of the manifest (P/02.1), the canonical view (P/02.2) and the forms of the data families (the catalogue `Platform/common/data/`) the course
writes in standard files: JSON Schema 2020-12 — the form, CEL — the relations of the manifest. What the standard does not express is held by
seven layers of our own; each implementation executes them, the places are the layer tables next to the schemas (ADR-0092 «Our own remainder»). This
file replaces `DIALECT.md` (ADR-0087; removed by the transition to V7, behind the tag `dialect-reference-dc94d0fd1`). A new word `x-*`
and a new rule of a layer are decided by the Architect (ADR-0087 addendum (5), ADR-0092 «What is replaced»); the description is written by «Specification».

## 1. Files

| File | What | Where |
|---|---|---|
| `*.schema.json` | the form: JSON Schema 2020-12 in the words of the standard and the marks `x-*` (§ 3) | the manifest — `02-installer/spec/02.1-installer.schema.json`; the view — `02.2-installer.view.schema.json`; a family — `NN-<process>/data/<family>.schema.json` |
| `*.relations.json` | the relations of the manifest: CEL rows with a number `no` (§ 5) | `02-installer/spec/02.1-installer.relations.json` |
| `*.layers.tsv` | the places of the marks `x-*` of a schema: `place<TAB>layer<TAB>word<TAB>value` (a place is a JSON Pointer in the schema; the root is the empty pointer `""`); the rows are all and only the places of the words with a layer of § 3; the table does not carry `x-owner`, `x-default-text`, `x-class`; the view schema has no table (`x-step`, `x-default`, `x-unique-by` — in the schema itself), `x-implied-by` — at the relation row (V7-LAYERS-ROOT-HASH-01) | next to the schema |
| `02.1-installer.scalars.tsv` | the table of the plain scalars of the manifest (P/02.1 N1.1) | next to the form of the manifest |
| `common/data/codec.tsv` | the codec of the store rows: a logical type → the notation in `items` and in JSON (layer 3) | `Platform/common/data/` |
| `<family>.outcomes.tsv` | the outcomes of an unreadable row or object by readers (§ 7) | next to the schema of the family |
| `common/versions/` | the pinned versions of the standard libraries and the YAML parsers: [README](versions/README.md), `go.mod`, `go.sum`, `requirements.txt` (ADR-0092 item 9) | `Platform/common/versions/` |
| `common/data/common.schema.json` | the common definitions of the family schemas — for reference, not a norm: each family schema is self-contained | `Platform/common/data/` |

The files `*.tsv` are tables: UTF-8 without BOM, the line feed LF, TAB is the column separator, a line with `#` is a comment, the first
line without `#` is the header, the set of columns is closed. The sections of the norms «Form», «Form of the canonical view», «Data families»
are built from these files and stand in the norms byte for byte (ADR-0087 item 3; the builder is the skill `lesson-spec`).

## 2. Seven layers

| Layer | What | Where the norm is |
|---|---|---|
| 1 | the text of the manifest: the YAML 1.2.2 parser of the pinned version and the fine check (§ 4) | P/02.1 N1.1 |
| 2 | the integers of the manifest: the bounds ±(2^53 − 1), a value with an integer value is an integer, in the tree it is cast to an integer (`4.0` → `4`) | P/02.1 N1.2, N3 step 2 |
| 3 | the codec of the family rows: `items`, time, `max_bytes`, names beyond the limit, the whole sign of the writer and the reader by the exact decimal value of the notation | `codec.tsv`, § 6 |
| 4 | the place of a refusal where the library does not give it — by the full table of § 6 «Place of refusal» (`required`, `additionalProperties: false` — the path of the key, not of the parent; `propertyNames` — the place of the parent object and the name; `uniqueItems` — the place of each element equal to an earlier one: `[a, a, a]` → `/1`, `/2`); the path of the families is normative (PY-JS-02) | § 6 |
| 5 | the full match of `pattern` and `patternProperties` (§ 3 «Expression») | § 3 |
| 6 | the projection of the canonical view — the full algorithm of P/02.2 N1.1: sugar, defaults (static — the annotation `default`, computed — the rules of P/02.2), P1–P5, `x-ordered`, scalars by the node type | P/02.2 N1.1 |
| 7 | relations: three CEL functions — `depth`, `template`, `text`; the other rows are pure CEL | § 5 |

## 3. Schema words

The standard — by the words of JSON Schema 2020-12 in their meaning (`type`, `enum`, `pattern`, `properties`, `additionalProperties`,
`patternProperties`, `propertyNames`, `required`, `items`, `minItems`, `maxItems`, `uniqueItems`, `maxProperties`,
`minimum`, `maximum`, `exclusiveMinimum`, `allOf`, `anyOf`, `if`/`then`, `not`, `$ref`, `$defs`, `default` — the annotation
of a static default, `description`; the place of refusal of each — § 6). The marks of our own layers:

| Word | Layer | What the implementation executes |
|---|---|---|
| `x-integer-place` | 2 | an integer place of the manifest: an integer by value, the bounds ±(2^53 − 1), the cast to an integer |
| `x-time` | 3 | time per the canon of P/01.1 N0: the notation of the writer is strict, of the reader tolerant |
| `x-whole` | 3 | the whole sign — both for the writer and for the reader: an integer by the exact decimal value of the notation |
| `x-integer` | 3 | an integer by the exact decimal value of the notation |
| `x-max-bytes` | 3 | the limit of the bytes of a value in the notation |
| `x-max-names` | 3 | the limit of the number of names outside `properties` |
| `x-encoding` | 3 | `json` or `jcs`: the value of the place is the parse of a JSON text (for the writer `jcs` is the canonical notation of RFC 8785) |
| `x-codec` | 3 | the types of the row fields in order — the codec of `items` |
| `x-file` | 3 | an instance of the family is a file: the root is the parse of the text of a UTF-8 file |
| `x-opaque` | 2, 6 | an opaque place: the set of keys is not checked, the projection and the tree walk do not go inside; numbers — by the common rules |
| `x-ordered` | 6 | the projection: the order of the author for a list or names |
| `x-step` | 6 | in the view schema: the projection step that gave the key |
| `x-default` | 6 | in the view schema: the key is mandatory by a default of the manifest form |
| `x-unique-by` | 6 | in the view schema: for an `ordered` list — the key by which the elements do not repeat |
| `x-complement-of` | 5 | the expression is the complement of the named one (translated by hand, ADR-0092 item 12) |
| `x-implied-by` | 7 | the relation row follows from the named rows (`[16, 17]`): it is executed like the others; in the coverage a group mutation instead of a single mutant (V7-IMPLIED-ROW-EXEC-01) |
| `x-owner`, `x-default-text` | — | reference marks of a norm section (the owner lesson, the default in words); they give no checks |
| `x-class` | — | the refusal class of the former dialect — only for the reconciliation of the set «A»; the refusal class by the norm is a layer (P/02.1 N4) |

**Expression** (`pattern`, `patternProperties`) — a portable subset: ECMA-262 in the mode `u` intersected with RE2 — without
lookahead and lookbehind, without backreferences; a character is written as the character itself in the JSON string (not `\x{HHHH}`). The match is
full: the expression is read as `^(?:…)$`, `$` does not match before the last `\n` (`"w\n"` does not pass `^(?:w)$`); the dot is
any character (`[\s\S]`). The compilation in both engines is held by `check_spec` (ADR-0092 item 14).

**The writer and the reader of families** — one schema file: the constraints of the writer are in `$defs.writer`; the writer checks
`allOf: [schema, $defs.writer]`, the reader — the schema (ADR-0092 item 15). The writer writes strictly, the reader reads tolerantly.

Tolerant reading means the declared reader schema, including its explicit permitted forms. It does not authorize old-format compatibility, a wider write/read size bound or an unknown-value fallback; current-format rules and each family's existing outcomes remain authoritative (ADR-0129 addendum (12)).

## 4. Layer 1: the fine check of the text

The rules — P/02.1 N1.1 `text` (ADR-0092 addendum (2): the list is closed, each rule has a corpus case): `bytes`, `tab`,
`document`, `refused`, `rare`, `flow`, `escape`, `comment`, `block`, `parser`. One document is counted by bytes, not by
the answer of the parser.

The workarounds of the defects of the pinned parsers are not rules (the outcome is as by the norm of YAML 1.2.2, they give no refusal of their own):
- **D13** (`go.yaml.in/yaml/v3`): the parser refuses `\/` in double quotes, YAML 1.2.2 and N1.1 admit it — layer 1 on Go
  replaces `\/` with `/` in double quotes before parsing;
- **D16** (both parsers): a last line of spaces without a line feed after a block scalar gives a value without
  the final `\n` — layer 1 appends LF to the end of a text without LF before parsing.

The other known defects of the pinned versions and their workarounds — [the list of library defects](versions/DEFECTS.md) (ADR-0092 item 9):
each has a vector row on which the answer is different without the workaround, or «guard».

**The package `yaml-suite`** ([`vectors/yaml-suite/`](vectors/yaml-suite/README.md)) — the outcome of layer 1 on each test of
yaml-test-suite `data-2022-01-17` (the inputs are in the package, acceptance without a network); `layer1` is checked strictly, the rule is a summary.

The native call of `yaml-suite` receives the cell `id` (the test identifier) and the fixture `in.yaml` (the bytes of the test input). The native output is one JSON object `{"layer1": "ok"|"refused"}`, optionally with `"rule"`. Only `layer1` is compared strictly: anything else is red (ADR-0092 item 2). `rule` is a hint into the report, without a failure: the rule names of an implementation are its own.

## 5. Relations (CEL)

A row of `relations.json` is a CEL expression over the tree of the loader: an absent value and `has` take the static
default `default` of the form; the computed defaults, P1–P5 and `x-ordered` are not applied to the relation tree (ADR-0092 layer 6).
The relations are checked only with a clean form; the refusal is `refused:relations` (P/02.1 N3, N4). A row is one expression over
the variable `doc` (the tree of the loader), the result is a list of violations `{p: path}`, nested by the number of iterated
segments of the path of the row. The CEL extensions are the standard `strings` and `two-var-comprehensions`; our own functions are
`depth(dyn) → int` (the depth of a value), `template(dyn, list, list, bool) → bool` (the substitutions of a template),
`text(list) → list` (values as text). A CEL execution error is not «the relation holds»: the implementation refuses with words rather than
skipping the row (the defect D5 of the pinned version).

**Map iteration order** (D18): CEL does not set the iteration order of a map — an expression does not rely on the order or the numbers
of the elements of the iteration of `keys()`; sets are compared by counting and by value (`filter(…).size() == 1`).

## 6. Data families

For a catalogue entry whose `schema` cell names a JSON Schema file, that file is the form of one row, object or file of `Platform/common/data/catalog.tsv`.
An instance is `{key, row}` for a row, `{key, object}` for an object, `{key, file}` for a file; the form of `row` is the object `items` after
the codec (`codec.tsv`). The signed is before tolerance: the codec and the schema
of the reader work on a parsed copy, the signature, `sha256` and forwarding — on the original bytes.

The `schema` cells `-` and `manifest` are sentinels, not JSON Schema file names. Both are outside common `family-read`: an invocation for such an entry has no family-schema verdict and is a concrete `MissingBinding`, not `ok`. This assigns no serialized form to `MissingBinding`; do not substitute an open or empty schema.

`-` means that there is no schema file in `data/`, not that any bytes are admitted. The key template, kind, owner, readers and all other catalogue requirements still apply; the value form follows the owning norm in the `norm` cell. `manifest` points to the owning manifest-dependent rule: sometimes it supplies value fields, sometimes only the family name. Where the subsystem owns the body, the platform judges the key, owner and readers, not that body's value. The [sentinel and owner-form table](data/README.md) gives the exact distinctions (Architect decision 2026-11-08, ADR-0088 R2, R3, C16). Norms and forms carry these rules without requiring vectors or scenarios as a source of meaning (ADR-0133 addendum (1)).

**Unreadable** — a row was not decoded or did not pass the schema in the reader mode; the answer is a set of refusal paths (JSON
Pointer). The path of the families is normative: it chooses the outcome (§ 7); where the library gives no place — layer 4.

**The key** of an instance is checked by the template of the column `key` of the catalogue: the literals of the template — exactly, a placeholder `<…>` — by
the [table of placeholders](data/README.md) (the grammar, the number of path components, an example). A key not by the template — the instance is not
of this family: a refusal on the empty path `""` (the instance whole), the value is not judged — like a row that is not an object; the outcome is the rows
of the empty path of `<family>.outcomes.tsv` (V7-FAMILY-KEY-PLACEHOLDER-01). The path `/key` does not fit for this: it is the path of the field
`key` of the value (P/08 `member-report`, `member-report-delta`, `member-reported`; for an open root — any name).

**Place of refusal** is normative and does not depend on the library; the rule is set by the stack of V7 — the set «A» and the vectors
`family-read` stand on it (V7-APPLICATOR-PATH-01):

| Word or layer | Place of refusal |
|---|---|
| `type`, `enum`, `pattern`, `minimum`, `maximum`, `exclusiveMinimum`, `minItems`, `maxItems`, `maxProperties` | the value on which the word stands |
| `anyOf`, `not` | the value on which the word stands (the node); the places inside the branches are not named |
| `allOf`, `$ref`, `if`/`then` | no place of its own — the places of the words of the subschemas on the same value (`then: {required: [x]}` — the path `x`) |
| `properties`, `patternProperties`, `additionalProperties` with a schema, `items` | no place of its own — the places of the words of the subschema on the value of the key or the element |
| `required` | the path of each missing key |
| `additionalProperties: false` | the path of each extra key |
| `propertyNames` | the path of a name not in form (the place of the object and the name); there are no refusals deeper than it |
| `uniqueItems` | the path of each element equal to an earlier one (`[a, a, a]` → `/1`, `/2`) |
| layer 3: the codec of `items`, `x-encoding`, `x-time`, `x-integer`, `x-whole`, `x-max-bytes`, `x-max-names`, a number outside binary64 | the place of the value; a row field not read by the codec — the path of the field, nothing deeper is judged |
| a row that is not an object, an object that is not JSON, a file that is not UTF-8, a key not by the template | the empty path `""` |

The answer is a set of paths: repeats merge, the order does not matter.

## 7. Outcomes of the unreadable (`<family>.outcomes.tsv`)

A row: `path<TAB>reader<TAB>outcome<TAB>priority<TAB>unit<TAB>norm`.
- `path` — a prefix of the refusal path as a JSON Pointer, empty — the row whole; the segment `*` — any name outside the keys of `properties`
  of the same place or any element of a list;
- `reader` — the role whose outcome is in the row (the process name per `lessons.tsv`: `console`, `<s>worker`, `domain`, …); for the empty
  path — a row for each reader of the family (the `readers` of the catalogue and the participants of `cas`, `guard`), `*` is not allowed; for the path of a field `*` —
  all readers; the pair `(path, reader)` does not repeat;
- `outcome` — what this reader does when it meets the unreadable (in the words of the norm of the owner lesson);
- `priority` — an integer, smaller earlier (the choice — below);
- `unit` — the unit of unreadability (the closed vocabulary [outcome-units.tsv](data/outcome-units.tsv): `row`, `field`, `element`): a refusal below it does not make the containing node unreadable;
- `norm` — the address of the norm.

**Choice of the outcome** of a reader R by the set of refusal paths (V7-OUTCOME-SELECT-01; a rule of the stack of V7):
1. the rows of R — with `reader` = R or `*`;
2. for each refusal path q — the covering rows: their `path` is a prefix of q (the empty one covers everything; the segment `*` — any name
   outside the keys of `properties` of that place or any element);
3. of them — the rows of the greatest depth; if among them there is a row with `unit` `field` or `element`, only these
   deepest ones act; otherwise (all the deepest are `row`) — all the rows covering q, the less deep ones too;
4. the rows of all paths are united; the rows with the smallest `priority` act, equal ones — all, in the order of the file; there is no refusal
   path or not a single row — there is no outcome.

A schema with a word (`<schema>.schema.json#<word>` in the column `schema` of the catalogue) is one schema for several families; the outcomes of a family
with a word — `<schema>.<word>.outcomes.tsv` next to the schema (V7-DOMAIN-SLOT-PULSE-SCHEMA-01).

The unreadable is not replaced by absence (the rule DF-OUTCOMES-109); for the console gate — the rule «Unreadable row»
of the [gate-and-pass contract](contracts/gate-and-pass.md).

## 8. The table of the manifest scalars (`scalars.tsv`)

A row: `kind<TAB>pattern<TAB>norm`; the first one that matches from the top, only for a plain scalar (a quoted one and a block one are a string).
`kind`: `null`, `true`, `false`, `int`, `float`, `nonfinite`, `string`. The rows `limit<TAB>int_max=N` and
`limit<TAB>float_max=X` are the limits: outside them and `nonfinite` — `refused:form` on the path of the value (P/02.1 N1.1).
