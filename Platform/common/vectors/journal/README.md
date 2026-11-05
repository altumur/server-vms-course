# Vectors: the event journal bucket and the names `%h<sha256>`

This English text is the source; the Russian translation `ru/vectors/journal/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the event journal contract](../../contracts/event-journal.md): `bucket` `torn`, the form `line` and «File names in shared trees»
(the guesses of stage C EJ-G03, EJ-G04, EJ-G06, EJ-G07, EJ-L03, EJ-L06, the Architect's decision of 2026-10-23); the form of the row is the family events
of P/05 (`05-resource/data/events-*.schema.json`: `events-unit`, `events-unit-alarms`, `events-audit`,
`events-audit-alarms`, `events-console`, `events-console-alarms`, `events-mirror`). The participants are the writers and the readers
of the trees of events and objects: the worker, the console, the controller, the resource ([P/05](../../../05-resource/spec/05-resource.norms.md)
Н1.1, Н1.2, Н1.4). The bytes are written by «Спецификация».

## `bucket.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped; the first non-skipped one is the header `case<TAB>file<TAB>expect<TAB>note`.

| Field | Meaning |
|---|---|
| `case` | the name of the row |
| `file` | the content of the bucket file — a JSON string (`\n` — LF) |
| `expect` | a JSON object: `ids` — the field `id` of the read lines in the order of the file, `torn` — 1 if the last fragment is without LF (otherwise 0), `garbled` — the number of full lines not parsed by the form `line` (the times `t`, `occurred` — by the reader's codec: a number or a string; the rows `t-*`), `duplicate` — the number of dropped repeats of `id` (the first line wins; EJ-L06) |
| `note` | the rule |

## `names.tsv`

The same file rules; the header `case<TAB>input<TAB>expect<TAB>note`. The rows `read-*` are reading: `input` is
`{entry, suffix, name_file}`: the name of the directory entry, the suffix of the norm of the compound component (`""`, `.lock`, `.alarms`) and
the content of the file `<entry без суффикса>.name` as a string or `null` — there is no file; `expect` is the original component as a JSON string
or `@skip` — the entry is skipped with a count, as an unreadable one. The rows `write-*` are writing: `input` is `{component,
name_file}`: the original component and the current content of `.name` (`null` — none); `expect` is `write` (the writer writes
`.name`), `keep` (it matches — leave it), `refuse` (it does not match — a refusal without overwriting).

## `years.tsv`

The same file rules; the header `case<TAB>t<TAB>expect<TAB>note`. `t` is the time of the write as a JSON number; `expect` is the name of the bucket
`<YYYYMMDDTHHMMSSZ>.events.jsonl` or `@refuse` — a refusal of the write before an id is allocated.

## `append.tsv`

The same file rules; the header `case<TAB>file<TAB>line<TAB>expect<TAB>note`: `file` is the content of the bucket before the write,
`line` is the new line without LF, `expect` is the content after the write (JSON strings) or `@refuse` — a refusal of the write, the file does not
change (deeper than `JSON_DEPTH`, `depth-129`; EJ-DEPTH-BASELINE33). A tail without LF is completed with LF, there is no truncation
(EJ-L03); the bucket `no-final-lf` read after the write gives `garbled` 1, and `json-tail` — three ordinary lines (`tail-json-appended` in `bucket.tsv`; EJ-L06).

## `modes.tsv`

The same file rules; the header `case<TAB>path<TAB>kind<TAB>mode<TAB>owner<TAB>group<TAB>note`: the path (with substitutions in
`<…>`), the kind (`dir`/`file`), the octal mode, the owner (`-` — not named) and the group by the contracts of the event journal
`bucket` `modes` and of the presence lock `modes` (EJ-L02, PL-G02, PL-G03). The group `w2c-events` is the installation's; at the acceptance stand
it is replaced by the primary group of the stand process (the event journal contract `modes`; ACC-EJ-STAND-GROUP-01, the Architect's decision of 2026-10-28). The check is a layout test
of an implementation (create and compare `stat`) or reading.

## Run

A side reads `file` by its own bucket reading code and compares `ids`, `torn`, `garbled` with `expect`; for `names.tsv` — by its own
name layout code, without a file system or in a temporary directory; for `years.tsv` — by its own bucket choice code.
Who performs: `bucket.tsv` — the reader of buckets, the resource (`05-resource`: the index, the copies, the sweep); `names.tsv` the rows
`read-*` — the readers of directories: the resource (`05-resource`) and every process that reads the objects root itself (`file://`,
the objects client contract: `03-worker`, `04-controller`, `06-console`, `08-domain`, `09-agent`, `10-domain-console`);
`years.tsv`, `append.tsv` and `names.tsv` the rows `write-*` — the writers of the roots of events and objects: the worker (`03-worker`,
`observe`), the console (`06-console`, the journal and the marks) and every role with its own journal `audit` (`04-controller`,
`05-resource`, `08-domain`, `09-agent`, `10-domain-console`); `modes.tsv` — the creator of the path of the row: the roots
(`events-root`, `resource-root`) — the installer (`02-installer`, P/02.4 Н1.2), `.workers`, the lock and the tree `testsub`
(`workers-dir`, `workers-sub`, `lock-file`, `tree-dir`, `unit-dir`, `bucket-one-writer`) — the worker (`03-worker`),
`audit-bucket` — the console (`06-console`) (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision of 2026-10-26).

## Native outcome

The package has no separate command contract — the general rule «Vectors» of [the common acceptance README](../../acceptance/README.md)
(ACC-VECTORS-CONNECT-04, the Architect's decision of 2026-10-26): the function answers with code 0 and one JSON value. `bucket.tsv` — an object `{ids, torn, garbled, …}`; `names.tsv` — for `read-*` the component as a JSON string or the JSON string
`"@skip"`, for `write-*` — the JSON string `"write"`, `"keep"` or `"refuse"`; `years.tsv` — the name of the bucket as a JSON string or the
JSON string `"@refuse"`; `append.tsv` — the content after the write as a JSON string or `"@refuse"`. `modes.tsv` is a layout test, not
a function: the rule does not apply to it.

## Vector wire

The wire of `modes.tsv` is set by the `common/journal` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native outcome and comparison. Algorithm meaning and consumer obligations remain here.
