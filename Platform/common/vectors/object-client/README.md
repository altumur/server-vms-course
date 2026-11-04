# Vectors: the object store client — the address and the outcome of a read

This English text is the source; the Russian translation `ru/vectors/object-client/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the object store client contract](../../contracts/object-client.md) (lesson P/05; C10-OBJECT-ADDRESS-32, the Architect's decision
of 2026-10-25). The participants are the platform processes that write and read objects. The bytes are written by «Спецификация».

## `address.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first non-skipped one is the header `case<TAB>input<TAB>expect<TAB>note`.
**Input** — `{OBJECTS, PLATFORM_DIR, SERVER_NAME?, door?}`; `door` is the door row `platform/doors/<SERVER_NAME>` as
read at an access to the objects of the cluster: the object of the row, `null` — there is no row, `"@unreadable"` — not readable by the form,
`"@none"` — the store did not answer. **Output** — `{kind: file | cluster, dir, door?, resource?}`: the directory of the write; at
`cluster` — the read door of the cluster `resource` (an explicit address or the `url` of the door row; `"@unknown"` — the read of the objects of the cluster is
«не известно» (not known)) and `door` — the key of the read door row, when the address is by it; or `@exit 2` — a refusal of start. 15 rows: a bare
`file://`, an absolute and a non-absolute path, `cluster://` with `resource` (empty and a name before «?»), another scheme; `resource` empty,
repeated, with percent-encoding (OBJECT135-URL-01); a bare `cluster://` and `cluster://<имя>` — the door by the door row of its own
server; no row, not readable, the store did not answer — `"@unknown"`, not a refusal of start; an explicit `resource` overrides the door
row (P03-OBJECTS-DEFAULT-1FD, the Architect's decision of 2026-10-26). The vectors check the parsing of the address, not the connection: an IP in
`resource` (`https://10.0.0.1:8446`) stays — a client of its own cluster will refuse such a door over `https://` with `ip_address` (the contract `tls`;
ADR-0075 addendum 2026-10-26 (4) item 6).

## `read.tsv`

The same file rules. **Input** — `{reply}`: `{status, X-Missing}` of the answer of `GET /v1/objects/{key}` (`X-Missing` — a string or
`null`) or `"@none"` — the door did not answer. **Output** — `"object"`, `"absent"`, `"unknown"` or `"refused"` (the contract
«Outcomes and what the client does»). 8 rows.

## Run

Without a stand: a side gives the input to its parsing of the address and its parsing of the answer (the environment and the wire are replaced by the input). The wire
of the door is the acceptance of lesson P/05.
Who performs both files is every process whose norm writes or reads the objects of P/05 (the writers and the readers of the families of the kind `object`
of the catalogue; ACC-VECTORS-CONNECT-04, the Architect's decision of 2026-10-26; the principle ACC-VECTORS-CONNECT-03): the worker and the worker at the domain (`03-worker`), the controller (`04-controller`), the resource (`05-resource`:
its own objects, the heartbeats, the bodies and the tombstones of the neighbours), the cluster console (`06-console`), the process `domain` (`08-domain`), the agent
(`09-agent`), the domain console (`10-domain-console`). The installer writes only the value of the address and does not perform the functions.
