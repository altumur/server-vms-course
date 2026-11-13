# JSON parsing and encoding

This English text is the source; the Russian translation `ru/contracts/json.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The shared `json` module supplies parsing and encoding, including [JCS](jcs.md). The caller selects the rules of its own existing contract. Parsing preserves the information required by those rules: object names before duplicate names can be lost, numeric lexemes before conversion and string escapes before a malformed scalar can be replaced. The module does not choose a platform refusal or introduce a universal size limit.

## Caller rules

The store's [JSON body rules](../../01-store/spec/01.1-store.norms.md#n21-request-parsing) define duplicate names, BOM, UTF-8, non-JSON numbers and nesting depth. Its fields keep their distinct treatment: a lone surrogate in a key is `badkey`, one in items is `badrequest`, while extra fields are not read. The length or numeric range of an ignored extra value does not become a new refusal. Depth still counts in extra fields. The [runtime constants](../../01-store/forms/runtime-constants.tsv) and [check order](../../01-store/forms/write-checks.tsv) belong to that caller.

Other callers apply their own schemas, field forms and refusal outcomes. A signed document's I-JSON constraints and the JCS canonical form remain those of the document's contract; the store's treatment of extra fields does not relax a signed document. Parsing a record that is already out of its family form uses that family's existing unreadable outcome. Encoding follows the writer's form and uses JCS only when that contract calls for it.

## Acceptance inputs

The package `common/jcs` checks canonical bytes and their digest by its existing [JCS contract](jcs.md). The existing JSON body cases of P/01.1 N5 check the store-specific parsing decisions through its door (judge-only: JSON cases of `Platform/01-store/acceptance/1/scenarios.tsv`). They are caller tests, not a new generic outcome mapping. The module's tests exercise the parser used by these callers; passing JCS vectors alone does not establish strict parsing.
