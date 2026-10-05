# console.py — the domain's door for people: the read view, the directory, the write façade, members, topology, grants, alarms, and the tables the specs serve — with no key; `python3 -m w2cplatform.domain.console`

**Role in the module.** The process that serves the domain to browsers and tools, in the standard library, bounded like every door (`ConsoleServer`, `Deadlined`, the reserve, the box's own unix socket `DOMAIN_CONSOLE_UNIX`). Every route but `/healthz` is the platform's and the specs': a subsystem's units at the route its spec's row name makes, a table its spec serves — never a route a subsystem wrote (the boundary's «no hooks»).

**No key (ADR-0032).** The domain's keys are the signer's (`signer_service.py`), and so is the holder's whole pass — the view, the kept edits closed, the week of alarms, the backup: one writer for each output. This process READS — the members and their publications from the holder's stores, and what only the signer knows (its term, its failing steps, the rows it could not read) from the view the signer publishes — and writes only what a person decides with no key: admitting a member, the topology, the grants, an edit kept again (`domain/rights.py`, `CONSOLE_WRITES`). What needs a key it hands to the signer as it came (`TO_SIGNER`, `ask_signer`), with the person's token; the signer checks it whole. While a handover freezes the holder it refuses its writes early (`refused_early`: the signer's `/api/holder`, `frozen_for`; replaced, 409), but the rule is the signer's.

## Routes
One set of paths (the console module's contract, §10a): every human route under `/domain/*`, the path a cluster console forwards unrewritten (`console.Mount.domain_forward`); `/api/*` is the processes' (the signer's) — here only `POST /api/login`, handed on.
- `GET /domain` — the view the signer's last pass left (`view_doc`: `console.domain_view`, with its age); 404 when there is none.
- `GET /domain/keys` — every `domain/` key of the holder's stores, masked; a row the role may not read (`domain/signer`) named and withheld (`keysview.keys`).
- `GET /`, `/index.html` — the holder's page, `page.html`: the console module with `sections: ["domain"]` (§10a); `/platform/console.{js,css}` — the module.
- `GET /domain/shared` — `shared_view()`: `{doc, delivery, declared}` read from the store, no key.
- `PUT /domain/shared`, `POST /domain/handover`, `/domain/users[/<name>]`, `/domain/break-glass[/<cluster>]` (`GET` too: the people's rows are opened where the ring is) — handed to the signer's `/api/shared`, `/api/handover` (a 90 s bound: it waits for the target's report), `/api/people/…`.
- `GET /domain/alarms?since=&until=` — `alarms_doc`: `DomainAlarms.list`, read; the week is the signer's pass's to keep.
- `GET /domain/backup` — `backup_doc`: for each `domain/backup/<member>` the pointer and what the member's last report says it took, and the signer's term.
- `GET /domain/grants`, `PUT /domain/grants/<cluster> {lines}` — `grants_doc`, `set_grants`: lines `{subject, cap, scope, until}`, `scope` `*`, `unit:<sub>/<id>` or `labels:a,b`; the domain's own (`domain`) never lapse and keep an admin (`set_domain_grants`), a cluster's lapse at `until` (default a grant's lifetime from now); a journal line each.
- `POST /domain/pending/<member> {ref, fields}` — `keep_again`: an edit an old holder held, kept again (202).
- `POST /domain/stranded/apply {path, key}` — `stranded_apply`: on a replaced holder, a kept edit it alone held sent to the new holder's console (`deposed_by.url` → its signer's `/api/holder` → `console`) as `POST /domain/pending/<member>`; anything else is made again by hand.
- `GET|POST|DELETE /session` — the door in by the domain's key set (`person`): the platform's shapes, `login_url: "/api/login"`, a token set as an `HttpOnly` cookie; no emergency entry (`/session/break-glass` is 404 — that is a cluster's).
- `GET /spec` — `{name: "", rows: null}`; `GET /mounts` — `{root: "", mounts: {<sub>: console.describe(spec)}}`.
- `GET /domain/<sub>/<rows>?q=&page=&size=&cluster=`, `PUT /domain/<sub>/<rows>/<ref>` (Idempotency-Key; 202 when kept), `GET /domain/<sub>/<table>`, `GET /domain/causes`, `GET /domain/where/<ref>`, `GET|POST /domain/members` (`{name, fingerprint?}`: admitted by the key its report presents, `Members.accept`), `DELETE /domain/members/<name>`, `GET|PUT /domain/topology`, `GET /healthz`.
- With `viewer`, every `GET /domain*` asks for a token (bearer or the session's cookie) and a `view` on the domain; its own writes need an `admin` on the domain; a write carried by the cookie from another site's page is refused (`access.cross_site`).

## `class Console`
Its pass, every step in a try of its own (`steps.Steps`), READS: following the members, following the topology, the read view's pass — in memory, for the routes that list units and say where they are. `health()` is `/healthz`: passes, failing steps, and what others wrote that does not parse (`GARBLED_SHOWN`).

## `main()` — `CLUSTERS`/`DOMAIN_HOLDER` (`runtime.federation_from_env`), `AUTH`, `REFRESH_INTERVAL`, `CONSOLE_HOST`/`CONSOLE_PORT`, `SIGNER_HOST`/`SIGNER_PORT`, `LOST_AFTER`; no `SECRETS_KEY`. The domain's own grants decide who may look and change (`grants.domain_may`); its journal is role `domainconsole` (`runtime.events_said`).
