# Vectors: the order of the initial installation of manifests

This English text is the source; the Russian translation `ru/vectors/install-order/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The owner is chapter [P/02.4](../../spec/02.4-installer.norms.md) of the installer (N1.7 `install` `steps`, `order`). The participant is the installer (`install.sh`, the step `manifest put`). The bytes are written by
the Specification.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — `{manifests, installed}`: `manifests` — the manifests of this installation, each with `name` and what sets or does not set
the order: `requests` (`worker.requests`), `near` (`placement.near.sub`), `creates` (the subsystems of `worker.creates`), `uses`
(`worker.uses`); `installed` — the names of the subsystems whose manifests are already in the store. `manifests`, `installed` and `name` of an element are mandatory;
`requests`, `near`, `creates`, `uses` are optional (absent — no link); empty arrays are allowed; `null` instead of a string or
an array — not by form: code 2, stdout empty.

**Output** — a JSON array of names in the order of `manifest put`, or `@exit 2` — a refusal of the installation with code 2 at the preliminary check,
before changes. Comparison — JSON by value.

The command’s native form and rule-refusal mapping are in the wire form below. An input outside the form exits with code 2 and empty stdout; a rule refusal on a well-formed input is a computed outcome, not a transport error. This does not change the installation or loader refusal named above.

## Run

The side computes the order with its own code of the installer without a store and compares it with `expect`. The edge of the domain token kind
(the declarer of `domain.tokens` before the subsystem whose `door.routes[].domain` names it; P/02.4 N1.7 `order`) is not expressed by the input — the form of the input is not extended: rows without kinds do not set it, the rule — by reading and
`puts.tsv` of chapter 2.3 (`door_domain_kind_other`, `door_domain_kind_missing`; judge-only: the installation sequences of chapter 2.3; they check P/02.4-R233, P/02.4-R241, P/02.4-R253, P/02.4-R259, P/02.4-R496, P/02.4-R506, P/02.4-R511).

The order is set only by `requests` (and by the kind, not expressed by the input); `near`, `creates`, `uses` are in the input but do not set the order: `cycle` — a cycle by `requests`; `requests-near-pair` — `requests` and `near`
towards each other — the order by `requests`, not a cycle; `near-only` — only `near`, no order (by name). Nine rows: eight
orders, one `@exit 2`.
Who executes — the installer (`02-installer`: the order of `manifest put` and the refusal on a cycle, P/02.4 N1.7 `order`, `refuse`); there are no other executors (a row is executed by the role whose norm calls its function).

## Vector wire

The wire of `cases.tsv` (judge-only: the table itself; it checks P/02.4-R233, P/02.4-R241, P/02.4-R253, P/02.4-R259, P/02.4-R496, P/02.4-R506, P/02.4-R511) is set by the `02-installer/install-order` rows of [the single form](../../../common/vectors/wire.tsv); [grammar](../../../common/vectors/wire.md). The form is the source of the header, selected inputs, fixtures, native outcome and comparison. Algorithm meaning and consumer obligations remain here.
