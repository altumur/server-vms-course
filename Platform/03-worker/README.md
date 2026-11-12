# Worker (SDK) — lesson P/03

This English text is the source; the Russian translation `ru/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

A micromodule: a library in each language, the role `<sub>worker`. Its contracts are listed below.

The layout of the catalogue (the English source on the canonical path, the Russian text for people in `ru/`):

```text
README.md                        this file
spec/03.K-worker.norms.md        norms (chapters 3.1–3.7 — .K)
spec/03-worker.README.md         implementation instructions
lifecycle.md                     flags, environment, exit codes, units
data/<family>.schema.json        data families the lesson owns (JSON Schema 2020-12)
vectors/<algorithm>/             vectors of the algorithms the lesson introduces
acceptance/<K>/                  acceptance of chapter K (2, 3, 4, 6: README.md, scenarios.tsv)
ru/                              for people, not in the export — the lecture ru/03-worker.md, translations of the English text by the same path
```

The kit forms are [forms/README.md](forms/README.md): process inputs, the refusal catalogue, the slot capture machine and a stage plan. SDK seams in `acceptance/K/seams.tsv` (judge-only: the SDK seam tests) supplement the process scenarios; their normalized CALL ports are not an implementation API.

## What this lesson takes from common

These common files supply definitions used by the chapters, the implementation instructions, lifecycle and forms. The chapter norms remain the canon; this index adds no requirements. Vector data and SDK seam cases do not replace the requirements in M.

| File | Sections and use |
|---|---|
| [Normative terms](../common/NORMATIVE-TERMS.md) | N0: the force of MUST, SHOULD and MAY |
| [Store client](../common/contracts/store-client.md) | Address; Request; Answer; Outcomes and what the client does — SDK reads, CAS, guards and an ambiguous write |
| [Object client](../common/contracts/object-client.md) | Address; Operations; Outcomes and what the client does — read unit and place objects without turning a non-answer into absence |
| [Observation](../common/contracts/observation.md) | Observation of a version; Freshness; Hold of a place; Server decommissioned; Freshness of a contender mark — the reader clock, version age and server withdrawal |
| [Slot](../common/contracts/slot.md) | Form; States; Terms — the shared meaning of a slot and its release states |
| [Slot name](../common/contracts/slot-name.md) | Grammar and «by name»; Slot order; Next number — candidate names and their ordering |
| [Instance](../common/contracts/instance.md) | Instance — process identity and the box part of the holder |
| [Presence lock](../common/contracts/presence-lock.md) | Lock; Production obligations — ownership of the process name, inode retries, finite cancellation |
| [Labels](../common/contracts/labels.md) | Label; Label list — the input alphabet and list grammar |
| [Environment file](../common/contracts/env-file.md) | Grammar; Files and reading order; Environment variables; Constants and units — launcher inputs and timings consumed by the SDK |
| [Schema](../common/contracts/schema.md) | Schema; Check at start — worker startup and the check after renewal |
| [Sealing](../common/contracts/sealing.md) | Envelope; AAD path; Ring file — the recipient opening secrets before taking an epoch |
| [Request and mark](../common/contracts/request-mark.md) | Request; Mark; States of an executed request and its mark; fetched — admission, the single call and an unknown outcome |
| [Event journal](../common/contracts/event-journal.md) | The line and the bucket; The event id and the writer instance; Writing a line — event writing and suppression |
| [Request group](../common/contracts/group-of.md) | Group — serialization of requests by the holder |
| [Door token](../common/contracts/door-token.md) | Token; Keys `door/keys` — the holder checks a request from the console |
| [Domain token](../common/contracts/domain-token.md) | The token; The check; Refusal words — token caching and recipient kind/audience checks |
| [Domain keys](../common/contracts/keys.md) | The set `domain/keys`; Revocations `domain/revoked`; The function `keys` — accepted keys and revocations |
| [Local token door](../common/contracts/local-token-door.md) | The role socket; The door; Refusals; The call in the process — domain-worker token access |
| [Role certificate](../common/contracts/role-certificate.md) | The server side: the class `role`; The server side: the class `mixed` — process-door admission |
| [Production obligations](../common/contracts/production-obligations.md) | Finite budgets and observable completion; Public acceptance and missing bindings — operation budgets and completion evidence |
| [Data catalog](../common/data/catalog.tsv) | Owned files, keys and readers — the data-families sections of the chapters |
| [Data codec](../common/data/codec.tsv) | Storage of family values — string row fields and object JSON values |
| [Common acceptance](../common/acceptance/README.md) | Stand; Dictionary of directives and doors — the common process stand and scenario grammar |
| [Acceptance profile](../common/acceptance/PROFILE.md) | Commands, keys, substitutions, vector commands and code-check names — the implementation supplies its own profile |
| [SDK seams](../common/acceptance/seams.md) | Procedure and peer ownership; CALL input and observation; Explicit test-side seam bridge — normalized test ports over the real SDK |
| [Teaching subsystem stand](../common/acceptance/testsub-stand.md) | testsub process stand — process acceptance with the teaching subsystem |
| [Pass acceptance](../common/acceptance/pass/README.md) | Stand-in worker of the pass of the second kind — the boundary between the stand-in and a real worker door |
| [TLS acceptance](../common/acceptance/tls/README.md) | Doors and clients of the probe; Outcome of a probe; Expectations — certificate and chain checks |
| [System acceptance](../common/acceptance/system/README.md) | Stand; Scenarios; Scenario boundaries — recovery, host loss and the domain dependencies |
| [Dependency versions](../common/versions/README.md) | Pinned versions: the version table and module-cache rules before «Raft library and implementation boundary» — the data-family validator and SDK dependencies |
| [Vector protocol](../common/vectors/wire.md) | Rows and sources; Input selection and groups; Comparison and assertions — assigned shared packages |
| [Shared schema definitions](../common/data/common.schema.json) | `$defs` used by the owned families — common scalar and object shapes |
| [Vector consumers](../common/vectors/consumers.tsv), [wire table](../common/vectors/wire.tsv) | Assigned shared packages of consumer `03-worker` and their input/output bindings |
| [Row check](../common/contracts/row-check.md) | Unit row; The customer’s row: `made`; Unit state; Preparation of fields; Identifier and field constraints — row types, life ids, ordered rows and state guards |
| [Pool](../common/contracts/pool.md) | Live worker; Pool; Keeper of a place with `distinct`; Server eligibility: `placeable`, `why` — capacity, weight, headroom and admission of places |
| [Forwarding](../common/contracts/forwarding.md) | Client address; Domain worker pass hop policy — `X-W2C-Client` and the domain-worker forwarding boundary |
| [Domain envelopes](../common/contracts/domain-envelopes.md) | Contribution; Content of `sealed` — the `entry` input and contribution envelope |
| [Event merge](../common/contracts/events-merge.md) | The participant; The merge; Epochs; The answer — `worker.reads`, epoch failures and incomplete event output |
| [Code-check dictionary](../common/acceptance/forms/code-rules.tsv) | Header and kind rows — the closed kinds, arguments and name types used by the lesson code rules |
| [Common target registry](../common/acceptance/forms/targets.tsv) | Column header — the common target-row form used by the lesson target inventory |
| [Pinned Go modules](../common/versions/go.mod) | Required modules — the module and version source of the `json_schema` code-check row |

### Other external files and exact sections

The public external files and sections used by this lesson's M.

| File | Sections and boundary |
|---|---|
| `Platform/01-store/spec/01-store.api.openapi.yaml` | [file](../01-store/spec/01-store.api.openapi.yaml) |
| `Platform/01-store/spec/01.1-store.norms.md` | [file](../01-store/spec/01.1-store.norms.md), [`#n0-vocabulary`](../01-store/spec/01.1-store.norms.md#n0-vocabulary), [`#time-in-a-row`](../01-store/spec/01.1-store.norms.md#time-in-a-row) |
| `Platform/01-store/spec/01.3-store.norms.md` | [file](../01-store/spec/01.3-store.norms.md) |
| `Platform/02-installer/lifecycle.md` | [file](../02-installer/lifecycle.md) |
| `Platform/02-installer/spec/02.1-installer.norms.md` | [file](../02-installer/spec/02.1-installer.norms.md) |
| `Platform/02-installer/spec/02.3-installer.norms.md` | [file](../02-installer/spec/02.3-installer.norms.md) |
| `Platform/02-installer/spec/02.4-installer.norms.md` | [file](../02-installer/spec/02.4-installer.norms.md) |
| `Platform/02-installer/spec/02.5-installer.norms.md` | [file](../02-installer/spec/02.5-installer.norms.md) |
| `Platform/04-controller/spec/04-controller.norms.md` | [file](../04-controller/spec/04-controller.norms.md) |
| `Platform/05-resource/spec/05-resource.norms.md` | [file](../05-resource/spec/05-resource.norms.md), [`#n2-doors`](../05-resource/spec/05-resource.norms.md#n2-doors) |
| `Platform/05-resource/vectors/relieve/README.md` | [file](../05-resource/vectors/relieve/README.md) |
| `Platform/06-console/acceptance/1/README.md` | [file](../06-console/acceptance/1/README.md) — scenarios 20 and 21: unit state in the answer and worker tables; the witness of checklist P/03.6-06 |
| `Platform/06-console/spec/06-console.api.openapi.yaml` | [file](../06-console/spec/06-console.api.openapi.yaml) |
| `Platform/06-console/spec/06.1-console.norms.md` | [file](../06-console/spec/06.1-console.norms.md) |
| `Platform/06-console/spec/06.2-console.norms.md` | [file](../06-console/spec/06.2-console.norms.md) |
| `Platform/06-console/spec/06.4-console.norms.md` | [file](../06-console/spec/06.4-console.norms.md) |
| `Platform/06-console/spec/06.5-console.norms.md` | [file](../06-console/spec/06.5-console.norms.md) |
| `Platform/06-console/spec/06.6-console.norms.md` | [file](../06-console/spec/06.6-console.norms.md) |
| `Platform/06-console/spec/06.7-console.norms.md` | [file](../06-console/spec/06.7-console.norms.md) |
| `Platform/06-console/vectors/requests-body/README.md` | [file](../06-console/vectors/requests-body/README.md) |
| `Platform/08-domain/README.md` | [file](../08-domain/README.md) |
| `Platform/08-domain/acceptance/5/README.md` | [file](../08-domain/acceptance/5/README.md) |
| `Platform/08-domain/acceptance/7/README.md` | [file](../08-domain/acceptance/7/README.md) — scenario 01: the token check at the recipient; the witness of checklist P/03.7-06 |
| `Platform/08-domain/data/holder.outcomes.tsv` | [file](../08-domain/data/holder.outcomes.tsv) |
| `Platform/08-domain/data/keys.outcomes.tsv` | [file](../08-domain/data/keys.outcomes.tsv) |
| `Platform/08-domain/spec/08.2-domain.norms.md` | [file](../08-domain/spec/08.2-domain.norms.md) |
| `Platform/08-domain/spec/08.3-domain.norms.md` | [file](../08-domain/spec/08.3-domain.norms.md) |
| `Platform/08-domain/spec/08.5-domain.norms.md` | [file](../08-domain/spec/08.5-domain.norms.md) |
| `Platform/08-domain/spec/08.7-domain.norms.md` | [file](../08-domain/spec/08.7-domain.norms.md) |
| `Platform/09-agent/README.md` | [file](../09-agent/README.md) |
| `Platform/09-agent/acceptance/1/README.md` | [file](../09-agent/acceptance/1/README.md) |
| `Platform/09-agent/spec/09.1-agent.norms.md` | [file](../09-agent/spec/09.1-agent.norms.md) |
| `Platform/10-domain-console/spec/10-domain-console.norms.md` | [file](../10-domain-console/spec/10-domain-console.norms.md) |
| `Platform/common/acceptance/seams.md` | [`#seam-adapter-protocol`](../common/acceptance/seams.md#seam-adapter-protocol) |
| `Platform/common/contracts/sealing.md` | [file](../common/contracts/sealing.md), [`#aad-path`](../common/contracts/sealing.md#aad-path), [`#envelope`](../common/contracts/sealing.md#envelope), [`#ring-file`](../common/contracts/sealing.md#ring-file) |
| `Platform/common/vectors/values-by-type/README.md` | [file](../common/vectors/values-by-type/README.md) |
| `Platform/01-store/spec/01.2-store.norms.md` | [file](../01-store/spec/01.2-store.norms.md) — Rights and roles used by the domain worker |
| `Platform/04-controller/lifecycle.md` | [file](../04-controller/lifecycle.md) — Controller neighbour process contract |
| `Platform/06-console/spec/06.3-console.norms.md` | [file](../06-console/spec/06.3-console.norms.md) — Console and pass-door owner |
| `Platform/08-domain/spec/08.1-domain.norms.md` | [file](../08-domain/spec/08.1-domain.norms.md) — Claims, member reports and unreadable heartbeat readers |
