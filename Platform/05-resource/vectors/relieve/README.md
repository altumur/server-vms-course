# Vectors: the request to free space (`relieve`)

This English text is the source; the Russian translation `ru/vectors/relieve/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The owner is lesson [P/05](../../spec/05-resource.norms.md) (N1.4 `free_ask`, N3 «resource pass» `relieve`; the VMS freeing request). The participants are the resource (writes and removes `<sub>/requests/free-<server>-<volume>`) and the workers
of a subsystem with `requests.free` (answer with the heartbeat field `freeing`, [P/03.4](../../../03-worker/spec/03.4-worker.norms.md) N1.1).
The bytes are written by the Specification.

## Request vectors

UTF-8, LF, fields separated by TAB; rows with `#` and empty ones are skipped, the first non-skipped one is the header `case<TAB>input<TAB>expect<TAB>note`.
`input` — `{space, volume, sub, server, heartbeats}`: the row `platform/space` (`enabled`, `high`, `low`), the volume of the resource (`name`,
`used`, `total` in bytes), the subsystem and the server of the request, the heartbeats of the workers (`sub`, `server`, `live` — the heartbeat is alive, `freeing` —
the heartbeat field, or it is absent); `expect` — `{action: write, free}` (write or rewrite the row with `free`), `{action: delete}`
(remove one's own row) or `{action: none}` (there is no request).

## Shortfall vectors

The heartbeat field of the resource `short` (P/05 N1.4). The same rules of the file; the header is `case<TAB>input<TAB>expect<TAB>note`.
`input` — `{space, server, volumes, subs, heartbeats}`: the row `platform/space`, the server of the resource, the volumes (`name`, `used`, `total`),
the subsystems with `requests.free`, the heartbeats of the workers (in the same form as the request vectors above); `expect` — `{short: <integer>}`: Σ over the volumes of the largest `need`
(> 0) among the subsystems — each subsystem has the `need` of a volume per N3 `relieve` (`used − total·low − Σ freeing`, rounded up to a byte), only
for a volume above `high`. 6 cases: two volumes and two subsystems, a volume below `high`, everything is being freed, `space` is disabled, no subsystems,
rounding up.

## Run

A side computes the step `relieve` with its own resource code from the input, without a store, and compares the action with `expect` (JSON by value).
Who executes it is the resource (`05-resource`: the step `relieve` and the field `short`, P/05 N3 «resource pass», N1.4 `free_ask`) — both tables. Only read the ready result: the workers of a subsystem (`03-worker`, answer `freeing` to a row `free-*`, P/03.4 N1.1) and the console (`06-console`, the series `w2c_resource_short_bytes` as it is, P/06.5 N3 «/metrics — text») (a row is executed by the role whose norm calls its function).
