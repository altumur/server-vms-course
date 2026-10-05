# console.py — the domain's door: the read view, the directory, the write façade, members and topology, and the tables the specs serve; `python3 -m w2cplatform.domain.console`

**Role in the module.** The process that serves the domain to browsers and tools, in the standard library, bounded like every door (`ConsoleServer`, `Deadlined`, the reserve, the box's own unix socket `DOMAIN_CONSOLE_UNIX`). Every route but `/healthz` is the platform's and the specs': a subsystem's units at the route its spec's row name makes, a table its spec serves — never a route a subsystem wrote (the boundary's «no hooks»: `/api/catalog` and `/metrics` of one subsystem were routes here; they are that subsystem's worker's door now).

## Routes
- `GET /api/<sub>/<rows>?q=&page=&size=&cluster=` — the read view of a subsystem of the directory (`route` → `("rows", sub, rows)`).
- `PUT /api/<sub>/<rows>/<ref>` — `api.update_unit(…, sub=<sub>)`, held to `<sub>`'s `domain.edit`; `Idempotency-Key` required; 202 when the edit was kept for a cluster that is off.
- `GET /api/<sub>/<table>` — a row a spec keeps at the holder and serves (`domain.tables`), as kept.
- `GET /api/causes`, `GET /api/where/<ref>`, `GET|POST /api/members`, `DELETE /api/members/<name>`, `GET|PUT /api/topology`, `GET /healthz`.
- With `viewer`, every `GET /api/*` asks for a token and a `view` on the domain; members and topology need an `admin` on the domain.

## `class Console`
Each pass, every step in a try of its own (`steps.Steps`): following the members, following the topology, the read view's pass, publishing the view (`domain/view`, with the tables the specs serve — `tables()`), collecting kept edits. `health()` is `/healthz`: passes, failing steps, and what others wrote that does not parse (`GARBLED_SHOWN`).

## `main()` — `CLUSTERS`/`DOMAIN_HOLDER` (`runtime.federation_from_env`), `AUTH`, `REFRESH_INTERVAL`, `CONSOLE_HOST`/`CONSOLE_PORT`; the domain's own grants decide who may look and change (`grants.domain_may`).
