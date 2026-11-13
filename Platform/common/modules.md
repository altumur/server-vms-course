# Shared code modules

This English text is the source; the Russian translation `ru/modules.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

A lesson uses the shared code module for the function that its own contract calls. The shared module is generated once from the contracts and acceptance inputs below. Other common contracts prescribe shared behaviour through their vectors; they do not require another shared code module.

## Module inventory

| Name | Go module | Contract | Acceptance inputs | Consumers in lessons 1–7 |
|---|---|---|---|---|
| `json` | `servervms.local/common/json` | [JSON parsing](contracts/json.md), [JCS](contracts/jcs.md) | `common/jcs`; the existing JSON body cases of P/01.1 N5 | `01-store`, `02-installer`, `03-worker`, `04-controller`, `05-resource`, `06-console`; JCS only where the consumer's contract calls it |
| `rights-evaluator` | `servervms.local/common/rights-evaluator` | [Rights evaluator](contracts/rights-evaluator.md) | `common/rights-evaluator` | `01-store` |
| `store-client` | `servervms.local/common/store-client` | [Store client](contracts/store-client.md), [store OpenAPI](../01-store/spec/01-store.api.openapi.yaml) | `common/store-client` | `01-store`, `02-installer`, `03-worker`, `04-controller`, `05-resource`, `06-console` |
| `log-mask` | `servervms.local/common/log-mask` | [Log mask](contracts/log-mask.md), [address rules](contracts/url-credentials.md) | `common/log-mask` | `01-store`, `02-installer`, `03-worker`, `04-controller`, `05-resource`, `06-console` |
| `row-check` | `servervms.local/common/row-check` | [Row check](contracts/row-check.md) | `common/row-check` | `03-worker`, `06-console`: row check and unit state; `04-controller`: unit state only |

A package name in Acceptance inputs selects its existing tables and wire through [consumers.tsv](vectors/consumers.tsv) and [wire.tsv](vectors/wire.tsv). The inventory does not assign new vector consumers or make every caller execute every function of a module. In particular, the installer's derivation of rights is not an action evaluator. The resource and controller are not JCS-vector consumers. The JS byte library `07-console-module` calls the console's public doors; it is not a Go consumer of these modules and has no common vector assignment.

## Pins and use

The pin location for every Go module in the inventory is a direct `require` in [versions/go.mod](versions/go.mod); its content checksums are in [versions/go.sum](versions/go.sum). The version identifies the generated module's exact commit and the checksums identify its bytes. A module without its generated, qualified pin is not ready for generation of a consuming lesson. There is no placeholder version or fallback to a local copy.

A consuming Go lesson has a `requires_module` row with the inventory's exact module path and `from` equal to `Platform/common/versions/go.mod`. The row's profile name maps to a package of the lesson that calls that shared module. The implementation imports and uses it under the existing [dependency rule](versions/README.md); a blank import, copied source, `replace`, `vendor` or `go.work` does not satisfy the rule. Behaviour, refusal selection and limits remain those of the caller's contract.

The lesson's `forbid_imports` row excludes direct `encoding/json` imports in its main module, so parsing and JSON encoding go through the shared `json` module. This check covers every non-test package, including commands and packages outside the package mapped by the row. Dependencies of a shared module are outside that main module. Other libraries remain available for functions outside these shared contracts; an exception to a forbidden import must be explicit in `allow` and justified by a norm in the same row. The code-check definitions are [the common dictionary](acceptance/forms/code-rules.tsv).

## Lesson contract input

The model input of lesson N includes every earlier lesson contract on which it relies: doors and OpenAPI, forms, schemas and client-vector interfaces. It obtains these files from the dependency table in the lesson README and the assembled export lists, as whole public files. Dependencies of those files are included too. The lesson's `forms/export.json` classifies its own files only; it does not own another lesson's files. The shared code modules supply implementations of their contracts; previous lesson implementation code is not an input. Scenario inputs and expected vectors remain outside the model input.
