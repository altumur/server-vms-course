# family-read vectors (ADR-0087 addendum (9) item 2; ADR-0092 Confirmation, sets «A» and «B»)

This English text is the source; the Russian translation `ru/vectors/family-read/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

Reading a data family of the catalog (`Platform/common/data/catalog.tsv`) by the common library of an implementation: the input is the family (`key`,
`kind`), the mode `writer` or `reader`, the text of the instance; the outcome is the verdict, the refusal paths (JSON Pointer), the outcome of
`<family>.outcomes.tsv` (only at the reader). The schema of the family is the column `schema` of the catalog (JSON Schema 2020-12), the layers are the words
`x-*` of the schema and `codec.tsv`.

The table `NN.tsv` holds the families of the owner lesson NN (the column `owner` of the catalog). A row:
`case<TAB>family<TAB>key<TAB>kind<TAB>mode<TAB>who<TAB>text<TAB>verdict<TAB>paths<TAB>outcome<TAB>note`:
- `family` — the template of the column `key` of the catalog; `key` — the concrete key of the row: the literals of the template — exactly, a placeholder — by
  the grammar of the placeholder table `Platform/common/data/README.md`; a key not by the template — `refused`, the path `""` (the row
  as a whole, the value is not judged; not `/key` — that is the path of the field `key` of the families of P/08), the outcome — the rows of the empty path;
- `who` — who performs it, a JSON array of roles: at `writer` — the roles of the operations of the catalog (`ops`), at `reader` — the readers of the family
  (the rows of the empty path of `<family>.outcomes.tsv`: the `readers` of the catalog ∪ the participants of `cas` and `guard`), in the order of the file;
- `text` — at `row` — a JSON object of the fields of `items` (the values are strings, as written in the store); at `object` and `file` —
  the text of the value as is;
- `verdict` — `ok` or `refused`; `paths` — a JSON array of the refusal paths (the order does not matter); `outcome` — at the writer `[]`,
  at the reader — a JSON object «role → array of paths of the `<family>.outcomes.tsv` rows whose outcome applies to that role»
  (the empty path — the row as a whole);
- `note` — a mutation of set «A» (`base` — the instance without a mutation; `<path>: <mutation>`, including the fields `key` of the families of P/08),
  the case id of set «B», `catalog key: <placeholder> "<substitution>"` or `catalog key: literal` — a key not by the template, `add: …` —
  a row added outside set «A» (a place of refusal, a defect of the library).

The answer of an implementation to a row is the JSON `{"verdict", "paths", "outcome"}`: strictly compared are the verdict, the set of paths and
the outcome (at the reader — by each role of `who`); `note` and `case` are the names of the row.

The expectations are the dialect reference (the tag `dialect-reference-dc94d0fd1`) with the deltas of set «B» of ADR-0092 (`1e400` — a number outside
binary64: a refusal of the place, the writer does not crash). The runner compares the verdict, the set of paths and the outcomes.

The iteration order of mappings (D18): in Go the iteration of a `map` is random — the expression and the check must not depend on the order
of keys (uniqueness and `prefix_free` — without element numbers); the set is run on Go more than once.

## Vector wire

The wire of `01.tsv`, `02.tsv`, `03.tsv`, `04.tsv`, `06.tsv` is set by the `common/family-read` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.
