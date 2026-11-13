# Vectors: reading the heartbeat of a resource and a worker by the form of the family

This English text is the source; the Russian translation `ru/vectors/heartbeat-read/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the observation contract](../../contracts/observation.md) «Form», «Resource state» (stage C guess
C04-DEP-OBS-HEARTBEAT-01, the Architect's decision 2026-10-25). The form is `Platform/05-resource/data/resource-heartbeat.schema.json`,
the outcomes are `Platform/05-resource/data/resource-heartbeat.outcomes.tsv` (the family `platform/resources/<server>/heartbeat` of lesson
P/05). The participants are the observers of `resource_state`: the controller and the console. The bytes are written by «Specification».

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header
`case<TAB>object<TAB>expect<TAB>note`.

Each case starts from a heartbeat with all required fields, including `door`, `waits`, `restore` and `mirror`.
The base uses a `loopback` door, zero wait and mirror counters, `waits.max: 16` and an empty `restore` map.
Each case changes only its stated subject; numeric lexemes in `object` are part of the input and must be preserved.

| Field | Meaning |
|---|---|
| `object` | the heartbeat of a resource — a JSON object under the key `platform/resources/srv-a/heartbeat` |
| `expect` | `{"readable": false}` — the whole object is unreadable (the outcome «the whole object»: it does not confirm life); `{"readable": true, "fields": [<field>…]}` — the heartbeat is readable, for the listed fields (in the order of the rows of `outcomes.tsv`) their field outcome from `outcomes.tsv` applies (`build` — reads as `""`, `retention_garbled`, `retention_withheld` — as absent), an empty list — there are no field outcomes |

## `worker.tsv`

Reading the heartbeat of a worker `<sub>/heartbeats/<name>` by the form `Platform/03-worker/data/heartbeats.schema.json` and the outcomes
`Platform/03-worker/data/heartbeats.outcomes.tsv` (lesson P/03.4 N1.1; C08-HEARTBEAT-READER-99-VECTORS, the Architect's decision 2026-10-26). The readers are the console (`GET /{rows}`, `/servers`,
`/metrics`, `/where`, door.pass, `/schema`), the controller, the drain, the shadow report of the domain. The same file rules; the fields `case`,
`key` (the key of the object), `object`, `expect`, `note`.

| `expect` | Meaning |
|---|---|
| `rows` | the reader `GET /{rows}` (P/06.1 N2 «rows»): `"unreadable"` — the heartbeat as a whole is unreadable, the elements do not read; `{"skip": [<index>…]}` — the elements of `status[]` not of the form are skipped, the rest go into rows |
| `others` | the other readers (`/servers`, `/metrics`, `/where`, the controller, the drain): `"unreadable"` — there is no heartbeat (the worker is not shown, the heartbeat is in `<sub>_heartbeats_garbled`); at an element of `status[]` not of the form — also `"unreadable"` (the outcome `/status`); `"readable"` — readable |
| `fields` | at `others: "readable"` — the fields with a field outcome in the order of the rows of `outcomes.tsv` (`build` — `""`, `schema` — `null` in processes, `pending_writes` — not stated); otherwise `[]` |

## Run

Without a stand: a side reads the object by its heartbeat reader (for a resource — the one that gives `resource_state`; for a worker — each
reader from `expect` by its own part) and compares: whether the heartbeat is readable, which elements are skipped and to which fields a field outcome is applied. The state by the observation history is the package [`resource-state`](../resource-state/README.md).
Who performs it: `cases.tsv` — the observers of `resource_state`: the controller (`04-controller`) and the console (`06-console`);
`worker.tsv` — the console (`06-console`) the whole `expect`; the controller (`04-controller`) and the shadow report of the domain (`08-domain`) —
the parts `others` and `fields` (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-26).

## Vector wire

The wire of `cases.tsv`, `worker.tsv` is set by the `common/heartbeat-read` rows of [the single form](../wire.tsv); [grammar](../wire.md). The form is the source of the header, selected inputs, fixtures, native framing and comparison. The input and output meanings, consumer duties, native form validation and checks outside the function remain here. Layout is an excluded function declaration, never proof that its separate acceptance ran.
