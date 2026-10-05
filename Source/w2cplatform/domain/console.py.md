# console.py — the domain's door: the read view, the directory, the write façade, members and topology, and the tables the specs serve; `python3 -m w2cplatform.domain.console`

**Role in the module.** The process that serves the domain to browsers and tools, in the standard library, bounded like every door (`ConsoleServer`, `Deadlined`, the reserve, the box's own unix socket `DOMAIN_CONSOLE_UNIX`). Every route but `/healthz` is the platform's and the specs': a subsystem's units at the route its spec's row name makes, a table its spec serves — never a route a subsystem wrote (the boundary's «no hooks»: `/api/catalog` and `/metrics` of one subsystem were routes here; they are that subsystem's worker's door now).

## Routes
One set of paths (the console module's contract, §10a): every human route under `/domain/*`, the path a cluster console forwards unrewritten (`console.Mount.domain_forward`); `/api/*` is the processes' (`signer_service.py`).
- `GET /domain` — the view (`view_doc`: the one the last pass left, with its age, else composed now): `ReadView.doc` in the product's shape — `members` a list with the holder among them, `holder`, `complete`, `units` by subsystem, `causes`, `tables` — and `extra()`: `topology`, `member_list`, `knocking`, `url` (this door: `CONSOLE_URL`, else `http://CONSOLE_HOST:CONSOLE_PORT`).
- `GET /domain/keys` — every `domain/` key of the holder's stores, masked (`keysview.keys`).
- `GET /`, `/index.html` — the holder's page, `page.html`: the console module with `sections: ["domain"]` (§10a); `/platform/console.{js,css}` — the module.
- `GET /domain/shared` — `shared_view()`: `{doc, delivery, declared}` read from the store, no key; `PUT /domain/shared` — handed to the signer as it came (`_to_signer`, `signer_url` from `SIGNER_HOST`/`SIGNER_PORT`; ADR-0032), which checks and signs.
- `GET /spec` — `{name: "", rows: null}`: no root, no key of its own (the page mounts the module with `sections: ["domain"]`); `GET /mounts` — `{root: "", mounts: {<sub>: console.describe(spec)}}`, every loaded spec.
- `GET /domain/<sub>/<rows>?q=&page=&size=&cluster=` — the read view of a subsystem of the directory (`route` → `("rows", sub, rows)`).
- `PUT /domain/<sub>/<rows>/<ref>` — `api.update_unit(…, sub=<sub>)`, held to `<sub>`'s `domain.edit`; `Idempotency-Key` required; 202 when the edit was kept for a cluster that is off.
- `GET /domain/<sub>/<table>` — a row a spec keeps at the holder and serves (`domain.tables`), as kept.
- `GET /domain/causes`, `GET /domain/where/<ref>`, `GET|POST /domain/members`, `DELETE /domain/members/<name>`, `GET|PUT /domain/topology`, `GET /healthz`.
- With `viewer`, every `GET /domain*` asks for a token and a `view` on the domain; members and topology need an `admin` on the domain.

## `class Console`
Each pass, every step in a try of its own (`steps.Steps`): following the members, following the topology, the read view's pass, publishing the view (`domain/view`, with the tables the specs serve — `tables()`), collecting kept edits. `health()` is `/healthz`: passes, failing steps, and what others wrote that does not parse (`GARBLED_SHOWN`).

## `main()` — `CLUSTERS`/`DOMAIN_HOLDER` (`runtime.federation_from_env`), `AUTH`, `REFRESH_INTERVAL`, `CONSOLE_HOST`/`CONSOLE_PORT`; the domain's own grants decide who may look and change (`grants.domain_may`).
