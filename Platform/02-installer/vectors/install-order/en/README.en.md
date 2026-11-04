# Vectors: the order of the initial installation of manifests

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is chapter [P/02.4](../../../spec/02.4-installer.norms.md) of the installer (Н1.7 `install` `steps`, `order`; guess of stage C
I02-INSTALL-ORDER, the Architect's decision of 2026-10-23). The participant is the installer (`install.sh`, the step `manifest put`). The bytes are written by
the Specification.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header `case<TAB>input<TAB>expect<TAB>note`.

**Input** — `{manifests, installed}`: `manifests` — the manifests of this installation, each with `name` and what sets or does not set
the order: `requests` (`worker.requests`), `near` (`placement.near.sub`), `creates` (the subsystems of `worker.creates`), `uses`
(`worker.uses`); `installed` — the names of the subsystems whose manifests are already in the store. `manifests`, `installed` and `name` of an element are mandatory;
`requests`, `near`, `creates`, `uses` are optional (absent — no link); empty arrays are allowed; `null` instead of a string or
an array — not by form: code 2, stdout empty (guess of stage C I02-G05, the Architect's decision of 2026-10-23).

**Output** — a JSON array of names in the order of `manifest put`, or `@exit 2` — a refusal of the installation with code 2 at the preliminary check,
before changes. Comparison — JSON by value.

## Stand command `install-order`

The key `stand` of the profile `02-installer` (the section «Layout by processes» of [the common acceptance README](../../../../common/acceptance/README.md)),
following the pattern of `door-token-verify` ([the door-token vectors](../../../../common/vectors/door-token/README.md)): a template with `{input}` —
the path of the file into which the runner writes the bytes of the cell `input` of the row as they are. stdout — exactly one JSON object in UTF-8 and LF,
code 0: `{"result":"ok","order":[…]}` — compared with `expect` by JSON value, — or `{"result":"refused"}` (`expect` — `@exit 2`). An input not by
form (a wrong type, an unknown or repeated field, a repeated name in `manifests`) — code 2, stdout empty; a refusal by a rule on an input that is by form — code 0, `{"result":"refused"}` (guess of stage C I02-STAND-FORM, the Architect's decision of 2026-10-23). A different code, a different `result`, extra fields or bytes — FAIL of the row (guess of stage C I02-STAND, the Architect's decision of 2026-10-23).

## Run

The side computes the order with its own code of the installer without a store and compares it with `expect`. The edge of the domain token kind
(the declarer of `domain.tokens` before the subsystem whose `door.routes[].domain` names it; P/02.4 Н1.7 `order`,
C02-KIND-ORDER-33) is not expressed by the input — the form of the input is not extended: rows without kinds do not set it, the rule — by reading and
`puts.tsv` of chapter 2.3 (`door_domain_kind_other`, `door_domain_kind_missing`).

The order is set only by `requests` (and by the kind, not expressed by the input); `near`, `creates`, `uses` are in the input but do not set the order
(ADR-0091 addendum (26) item 1, addendum (27) item 4): `cycle` — a cycle by `requests`; `requests-near-pair` — `requests` and `near`
towards each other — the order by `requests`, not a cycle; `near-only` — only `near`, no order (by name). Nine rows: eight
orders, one `@exit 2`.
Who executes — the installer (`02-installer`: the order of `manifest put` and the refusal on a cycle, P/02.4 Н1.7 `order`, `refuse`); there are no other executors (ACC-VECTORS-CONNECT-03: a row is executed by the role whose norm calls its function; the Architect's decision of 2026-10-27).
