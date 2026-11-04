# Vectors: reading the heartbeat of a resource and a worker by the form of the family

This English text is the source; the Russian translation `ru/vectors/heartbeat-read/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the observation contract](../../contracts/observation.md) «Form», «Resource state» (stage C guess
C04-DEP-OBS-HEARTBEAT-01, the Architect's decision 2026-10-25). The form is `Platform/05-resource/data/resource-heartbeat.schema.json`,
the outcomes are `Platform/05-resource/data/resource-heartbeat.outcomes.tsv` (the family `platform/resources/<server>/heartbeat` of lesson
P/05). The participants are the observers of `resource_state`: the controller and the console. The bytes are written by «Спецификация»; the expectations are obtained by the judge
of the family schemas of the skill (the reader mode, LAYERS.md §§ 6–7), not by the code of implementations.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header
`case<TAB>object<TAB>expect<TAB>note`.

| Field | Meaning |
|---|---|
| `object` | the heartbeat of a resource — a JSON object under the key `platform/resources/srv-a/heartbeat` |
| `expect` | `{"readable": false}` — the whole object is unreadable (the outcome «объект целиком»: it does not confirm life); `{"readable": true, "fields": [<поле>…]}` — the heartbeat is readable, for the listed fields (in the order of the rows of `outcomes.tsv`) their field outcome from `outcomes.tsv` applies (`build` — reads as `""`, `retention_garbled`, `retention_withheld` — as absent), an empty list — there are no field outcomes |

18 rows: 11 readable (7 of them with a field outcome), 7 unreadable. The lexemes of time and of integers (OBS154-RAW-TIME-EXACT-01, the Architect's decision
2026-10-26): the time `ts`, `usage_at` with `1e0`, `1e-400`, `-0` — not of the form (`codec.tsv` `time`, the reader); `usage` `100.0` is
the integer 100, `100.00000000000000001` is not an integer by the exact decimal value of the lexeme, not after binary64; `schema` `1.0`
(`x-whole`) — a field outcome.

## `worker.tsv`

Reading the heartbeat of a worker `<sub>/heartbeats/<имя>` by the form `Platform/03-worker/data/heartbeats.schema.json` and the outcomes
`Platform/03-worker/data/heartbeats.outcomes.tsv` (lesson P/03.4 Н1.1; C08-HEARTBEAT-READER-99-VECTORS, the Architect's decision 2026-10-26). The readers are the console (`GET /{rows}`, `/servers`,
`/metrics`, `/where`, door.pass, `/schema`), the controller, the drain, the shadow report of the domain. The same file rules; the fields `case`,
`key` (the key of the object), `object`, `expect`, `note`.

| `expect` | Meaning |
|---|---|
| `rows` | the reader `GET /{rows}` (P/06.1 Н2 «rows»): `"unreadable"` — the heartbeat as a whole is unreadable, the elements do not read; `{"skip": [<индекс>…]}` — the elements of `status[]` not of the form are skipped, the rest go into rows |
| `others` | the other readers (`/servers`, `/metrics`, `/where`, the controller, the drain): `"unreadable"` — there is no heartbeat (the worker is not shown, the heartbeat is in `<sub>_heartbeats_garbled`); at an element of `status[]` not of the form — also `"unreadable"` (the outcome `/status`); `"readable"` — readable |
| `fields` | at `others: "readable"` — the fields with a field outcome in the order of the rows of `outcomes.tsv` (`build` — `""`, `schema` — `null` in processes, `pending_writes` — not stated); otherwise `[]` |

19 rows: of the form; not an object, no `instance`, `status` not a list, `worker` ≠ the name in the key (the prose rule of P/03.4 Н1.1, the outcome
«объект целиком») — unreadable; an element without `phase`, with a non-integer `epoch`, `sealed` with `epoch`, `id` not by the grammar — a skip at
`GET /{rows}`, unreadable to the others; `unreadable` with `why` — of the form; the field outcomes `build`, `schema`, `pending_writes`; the path `""`
before `/status` — unreadable to all. The expectations — by the judge of the family schemas of the skill (the reader mode), the rule `worker` — by the prose.
The lexemes (OBS154-RAW-TIME-EXACT-01): `ts`, `started`, `previous_hb` with `1e0`, `1e-400`, `-0` — unreadable to all; `freeing` `100.0` —
readable, `100.00000000000000001` — unreadable to all (`freeing` has no field outcome); `pending_writes` `1.0` (`x-whole`) — a field outcome.

## Run

Without a stand: a side reads the object by its heartbeat reader (for a resource — the one that gives `resource_state`; for a worker — each
reader from `expect` by its own part) and compares: whether the heartbeat is readable, which elements are skipped and to which fields a field outcome is applied. The state by the observation history is the package [`resource-state`](../resource-state/README.md).
Who performs it: `cases.tsv` — the observers of `resource_state`: the controller (`04-controller`) and the console (`06-console`);
`worker.tsv` — the console (`06-console`) the whole `expect`; the controller (`04-controller`) and the shadow report of the domain (`08-domain`) —
the parts `others` and `fields` (ACC-VECTORS-CONNECT-03: a row is performed by the role whose norm calls its function; the Architect's decision 2026-10-26).
