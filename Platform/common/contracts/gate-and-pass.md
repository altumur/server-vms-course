# The gate-and-pass contract: who calls the console, `/session`, the pass of `door.pass` to a worker

This English text is the source; the Russian translation `ru/contracts/gate-and-pass.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (11) and addendum (13): a contract that several
processes execute lies in `Platform/common/`; analysis of review of stage A 8–10, № 14 / decision 3). The owner is lesson
[P/06](../../06-console/spec/06.3-console.norms.md) (chapters 6.3 — the gate and the session, 6.5 — `door.pass`): the cluster console
asks every door for the identity and the grant and passes the routes `door.pass` to a worker. The participant is lesson P/10, the domain console
([norms of lesson P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.5, N1.6, N1.7): the same gate before the doors `/domain/*` and the same pass of the routes `door.pass` to the worker on the domain.

| What | Cluster console (P/06) | Domain console (P/10) |
|---|---|---|
| the gate (section «The gate») | in full; the grants are the copy of `domain/grants` of this cluster (section «The gate with grants» `cluster`) | `gate`, `identity`, `x_user`, `caps`, `scope`, `csrf`, `body`, `refusal`; the grants are `domain/grants/domain`, `need` is [P/08.4](../../08-domain/spec/08.4-domain.norms.md) N1.5 `domain`, `body_unit` |
| `/session`, `/healthz` (section «The gate» `session`) | yes | yes (P/10 N1.7 `session`; `grants` — P/10 N1.5 `session`) |
| the traces of the domain, «loopback — operator» (section «Traces of the domain») | yes (the late layer) | yes (P/10 N1.5) |
| the rights by the body (section «Rights by the body») | `rights:`, `body_unit`, `session` | `body_unit`, `session`, the line `domain` |
| the break-glass entry and the attempt limit (section «Break-glass entry») | yes | the limit is at `POST /api/login`, passed to the process `domain` |
| the pass of `door.pass` (section «Pass of `door.pass`») | to a live worker of the subsystem with a door ([P/06.5](../../06-console/spec/06.5-console.norms.md) N1.8 «Live worker with a door») | to the worker on the domain of this subsystem by its heartbeat (P/10 N1.6 `route`, `address`, `absent`) |
| the pass of the second kind and the callback by ticket (section «Pass of the second kind») | yes | the pass — yes; there is no callback on the domain yet (P/10 N1.6) |
| forwarding of `/domain/*` to another process | [forwarding contract](forwarding.md) | [forwarding contract](forwarding.md) |

Moved from P/06.3 N1.3 (the block `gate`, `open_routes`, `session` in full) and P/06.5 N1.8 (the block `manifest`, `rule`, `codes`) without
a change of behaviour; the source chapters hold pointers. What the grants and the entry of the people of the domain mean is lesson P/08
([chapter 8.4](../../08-domain/spec/08.4-domain.norms.md)); the parsing of a console request and the order of checks are the section «Request parsing and the order of checks» below; the keys `rights:` of the manifest are
P/06.3 N1.5; the refusals of the gate are the section «Refusals of the gate»; the refusals of the pass are P/06.5 N4.
References «N1.x» in the moved text are to the source chapter (N1.5, N1.8 — P/06.3; N4 — P/06.5); «chapter 6.K» is a chapter of lesson P/06.

Normative keywords follow the [course canon](../NORMATIVE-TERMS.md).

## Form

The files the contract works by (layout audit, `V-23`–`V-29`; the Architect's decision of 2026-10-25):

- the forms of the answers of the contract (`Denied` — `{detail, error: denied}`, the answers of `/session`) — `Platform/common/contracts/gate-and-pass.api.openapi.yaml`;
- the doors: the cluster console — `Platform/06-console/spec/06-console.api.openapi.yaml`; the domain console (`/session`, `/domain/*`) —
  `Platform/10-domain-console/spec/10-domain-console.api.openapi.yaml`; the process `domain` (`POST /api/login`, the attempt limit) —
  `Platform/08-domain/spec/08-domain.api.openapi.yaml`;
- the key set `domain/keys` (`on`, «keys exist», `unreadable`) — the family `keys`: `Platform/08-domain/data/keys.schema.json`,
  `Platform/08-domain/data/keys.outcomes.tsv`;
- the grants: the copy of `domain/grants` at the cluster console — `Platform/09-agent/data/grants.schema.json`,
  `Platform/09-agent/data/grants.outcomes.tsv`; `domain/grants/domain` at the domain console — `Platform/08-domain/data/grants.schema.json`,
  `Platform/08-domain/data/grants.outcomes.tsv`;
- the break-glass account `domain/break-glass/<cluster>` — `Platform/08-domain/data/break-glass.schema.json`,
  `Platform/08-domain/data/break-glass.outcomes.tsv`;
- the worker heartbeat (`door.pass` — to a live worker with a door, to the worker on the domain — by the heartbeat) — `Platform/03-worker/data/heartbeats.schema.json`,
  `Platform/03-worker/data/heartbeats.outcomes.tsv`;
- the traces of the domain (only the fact that the row exists is needed): `domain/member` — `Platform/09-agent/data/member.schema.json`,
  `Platform/09-agent/data/member.outcomes.tsv`; `domain/root` — `Platform/08-domain/data/root.schema.json`,
  `Platform/08-domain/data/root.outcomes.tsv`; `domain/revoked` — `Platform/08-domain/data/revoked.schema.json`,
  `Platform/08-domain/data/revoked.outcomes.tsv`.

## The gate

From P/06.3 N1.3:

```yaml
gate:
  on:       the store has domain/keys → every door except the open ones asks for the identity and the grant
  open:     no keys and no traces of the domain → the console is open: only from loopback (otherwise 403), the name is operator
  shut:     there were keys or a trace of the domain exists, but there is nothing to check with / the store did not answer → 503, not open (a row
            domain/keys that exists but does not read is unreadable below, not shut); GET /session
            (open_routes) to the anonymous — {open: false, login_url, server_time, timezone}, as «closed to the anonymous», not 503 (guess of stage C
            GP-G04, the Architect's decision of 2026-10-23)
            # «keys exist» and «a trace of the domain» — the section «Traces of the domain» below (the late layer)
  unreadable: in order: the store did not answer, or there is no row domain/keys with a trace of the domain or with keys seen → shut
            (503 {detail: "…admits nobody", error: denied}, as before); the row domain/keys exists but does not read (an outcome of the family
            keys, Platform/08-domain/data/keys.outcomes.tsv) → there is nothing to check a token with: 503 {error: "unavailable"}, not shut
            and not open (DF-OUTCOMES-109, the Architect's answer of 2026-10-25)
  identity: # in order
    0. the header X-W2C-Pass-Ticket is present — a callback by ticket: the identity is only the record of the ticket (section «Pass of the second kind» ticket);
       the cookie, Authorization, the agent signature and the debug identity are not read: a worker does not mix a ticket with another's credential
       (ADR-0094 B1; P/06.3 N1.9)
    1. the break-glass cookie w2c_glass (a session in memory, 15 min); a cookie without a live emergency session is as without it,
       the check goes on to the next step (the cookie stays in the browser after 15 min too; GP-G03)
    2. X-Agent-Signature — the agent of the domain: only the doors of units, of tables domain.edit_tables, POST /console/batch and GET /events?class=alarm; with X-Agent-For (the form is <name> <iat>, out of form — 401; without a proven signature the header is removed) the identity of the door is this person, iat is from the header, then the usual need and may by the copy of grants: a refusal is 403, the agent's outcome is refused (ADR-0111 item 16; D-2) (the front and the alarm page — P/09.1 N1.10; the form and the window UNIT_WINDOW 60 s — the agent signature contract common/contracts/agent-signature.md; analysis of review of stage A 8–10, № 13)
    3. Authorization: Bearer <token> | the cookie w2c_token → the domain: {user, until, grants} (the token — the domain token contract «The check» with expect {kind: person, cluster: null} (the Architect's decision of 2026-10-20, ADR-0083 addendum (14) item 7; analysis of review of stage A 8–10), the owner is P/08.2 — analysis of review of stage B 3–5, V1; the grants — P/06.7 N1.9 (the cluster console), P/10 N1.5 (the domain console); may — the right contract may.md)
       the name is sub of the token, until is exp (the fields — the domain token contract «The token» person); sub out of the form of a person name — 401
       (guess of stage C GP-L01, the Architect's decision of 2026-10-23); Authorization before the cookie w2c_token: with both, the header is read (guess of stage C GP-L02, the Architect's decision of 2026-10-23)
       a presented and wrong X-Agent-Signature (item 2) or token (item 3: by the header or by the cookie w2c_token) — 401, to item 4
       they do not go on (guess of stage C GP-G03, the Architect's decision of 2026-10-23)
    4. the debug identity (ADR-0050): W2C_DEBUG_PERSON=<name> is set, a request without a token presented in any form
       (neither Authorization nor the cookie w2c_token; GP-G03), the address of the TCP connection
       127.0.0.1 or ::1 (address headers are not read) → this person with their grants from domain/grants; the criterion
       of disabling is the row domain/disabled (the form Platform/08-domain/data/disabled.schema.json (outcomes — `Platform/08-domain/data/disabled.outcomes.tsv`), outcomes disabled.outcomes.tsv;
       the same input disabled as at the function may step 2): a name in it — as without the entry; the row exists but does not read — as without
       the entry (nothing to check with); no row — nobody is disabled; the console does not read domain/users: an identity without rows in
       domain/grants — the session grants: [], every check no_grant; the row domain/grants exists but does not read —
       the rule «Unreadable row» of the section «Refusals of the gate» (503 unavailable, not an exception; the Architect's decision of 2026-10-28 by the reconciliation ddc9bee1e) (C06-DEBUG-FACTS-33-01, the Architect's decision
       of 2026-10-25); from another address — as without the variable; a trusted proxy on loopback and the variable set
       → the process does not start; visible: /session gives debug: true, at start the alarm session.debug_open,
       every edit goes to the journal with debug: true
    5. otherwise 401
  x_user:   the header X-User is always erased; the proven name is written in; with a proven agent signature with X-Agent-For — the name of the person; with a proven agent signature without it (identity item 2) —
            X-User: agent, there is no session (guess of stage C GP-L07, the Architect's decision of 2026-10-23)
  caps:     none < view < edit < admin; need names only view | edit | admin, none occurs only in a role row (the right contract)
  need:     # what a door requires; decided by the path BEFORE reading the body
    GET/HEAD                         → view (on the unit from the path or ?unit=; without a unit — any grant, sub = null)
    /marks, POST /{sub}/requests     → edit on the unit of the body: at the cluster console before the body — a grant edit on anything, after
                                       the body — exactly on the unit of the body; at the domain gate before the body — edit on "*" (body_unit)
    DELETE /{sub}/asked/*            → admin on *
    server labels, decommission, policy, drain, schema PUT → admin on *
    GET /manifest/<sub>/source       → admin on * or a ticket with the entry GET manifest/<s>/source in calls (P/06.5 N2; ADR-0116 addendum (7))
    GET /drain                       → view on * (not «any grant»): the drain is the state of the whole cluster, there is no partial visibility;
                                       a narrower grant (unit:…, labels:…) — 403 by refusal, without an answer (C06-DRAIN-VISIBILITY-33-01)
    POST /domain/move                → step 1 or step 4a of the right contract by the role table of this cluster: an emergency session or
                                       a domain administrator; a row admin of the cluster is not enough, the user manager also
                                       issues it (ADR-0100 §1; the emergency move of the domain here, P/08.8 N1.8); only at this door, only from loopback:
                                       the address of the TCP connection 127.0.0.1 or ::1, address headers are not read (`identity` item 4), a request with the header Forwarded, X-Forwarded-*, X-Real-IP or Via is as not from loopback;
                                       a signature by the root replaces the token (P/06.7 N1.8 step 3, C08-MOVE-BY-FILE-01)
    writes_via (P/06.1 N1.1a)        → before need: a write of rows of a unit or of a table with the word writes_via — only a callback by
                                       a ticket of a subsystem from the list (ticket below); to the others — 403 writes via, need is not judged
    unit rows: POST → admin on * | by rights.routes view/edit on the unit about | cluster_rows → *
                   PUT/DELETE        → admin on the unit | cluster_rows → *; rights.routes does not lower them — for unit rows
                                       only creation is lowered (the table «Rights by the body» below; finding M-2)
    GET /<rows>?deleted=1&about=<z>  → view on the unit <about.sub>/<z> (P/06.1 N2 «Tombstones by `about`»; ADR-0094 addendum (5) item 1)
    GET /changes                     → view without a unit — any grant; what is seen is decided by the filter of the door (P/06.1 N2 «Change feed»; ADR-0094 B2)
    GET /{sub}/<route>/<id>[/…]    → view on the unit <sub>/<id> (P/06.3 N1.9 «Door route»; P/06.7 N1.6 route)
    GET /{sub}/heartbeats            → view without a unit — any grant: the door gives only the fields heartbeat.door (P/06.7 N1.6 pulse; ADR-0112 addendum (12) item 3)
    GET /{sub}/next_id               → as the creation of rows <sub>: admin on * | by rights.routes — there is no body, the pre-check create_about | cluster_rows → *
                                       (P/06.1 N2 «Counter door»; ADR-0094 B4)
    tables                           → by rights.routes (view | edit | admin); a table service: true is closed to a person, 403 by refusal before
                                       the body; a ticket — the rule service of the section «Pass of the second kind» (P/06.1 N1.6 service)
    POST /console/batch              → before the body — any grant; after the body — each row of writes by its door above: creation — as POST,
                                       an edit and a removal — as PUT and DELETE, a table row — as the table, <s>/next_id — as the creation
                                       of rows <s>; a refusal of one — 403 of the whole batch, nothing is written (P/06.1 N2 «Batch door»;
                                       ADR-0094 B9); a guard without view — not 403 but the refusal of an absent row (addendum (12) item 12)
    door.pass of the second kind      → a proven identity and any grant, including one in another cluster of the domain: the input anywhere of the right contract, the row
                                       domain/anywhere (ADR-0110 D-8); the capability is not asked and rights.routes is not read: a route
                                       is not a right, what a person may do is decided by a fresh may on every callback (section «Pass of the second kind»)
    GET/HEAD /folders, /folders/<id> → view without a unit: any effective grant row (P/06.8 N3 «folder rights»)
    POST /folders, PUT and DELETE /folders/<id> → before the body — any grant; the decision — the procedure of the door, the input of may — the folder and its ancestors
                                       (P/06.8 N3 «folder rights»; ADR-0096, ADR-0097 § 6, ADR-0099 § 4)
    a row platform/folders/<id> in POST /console/batch → as PUT /folders/<id> by the difference of the members; a row platform/memberof/…
                                       has no check of its own, it is judged by the folder row (P/06.8 N3 «folder rows in a batch»)
    /{sub}/operations and the operation doors → any grant; view and edit on the operations table are decided by the door: without view — 404, not 403
                                       (P/06.9 N2; ADR-0095 § 5)
    door.pass of the first kind (section «Pass of `door.pass`») → the capability — by rights.routes if the first segment is named there, otherwise GET/HEAD — view,
                                       other methods — admin; the target — the unit from ?unit= (<sub>/<id>; a bare id — 400, as at GET),
                                       if named; without ?unit= — at the cluster console view and edit — a grant of this capability on anything, admin — on "*":
                                       admin on one unit gives no write to a door without a unit (C06-PASS-ADMIN-STAR-01, the Architect's decision of 2026-11-01)
                                       (the worker will check the credentials again, P/03.7), at the domain console — on "*" (the worker on the domain does not check
                                       people; the same difference as body_unit); the body is not read for the rights
                                       (C06-PASS-NEED-51-01, the Architect's decision of 2026-10-25)
    by the body — rights.unit_of, reach, names add units (section «Rights by the body»); before the body — the pre-check body_unit
    (at the cluster console — a grant on anything, at the domain gate — unit = "*"), the checks after the body are kept
    (added by the reconciliation of M11; C06-BODYEDIT-SCOPE-33-01)
  scope:    a grant on * | unit:<sub>/<id> | labels:<…> | folder:<id>; a grant on the unit or on its about-unit (C06-EVENTS-QUERY-UNKNOWN-138-10, the Architect's decision of 2026-10-26):
            - * and unit:<sub>/<id> of the unit itself are matched by the name given in the path or ?unit=: the unit row need not be read,
              with an unreadable row the grant covers;
            - labels:… and unit: of the about-unit (another unit that the row names in about) require the unit row: if it is
              unreadable or the read is not confirmed — this grant does not cover (not 503; the next grant is checked, none
              covered — 403 by refusal);
            - the value of the field about.field in the row is empty or the row has no such field — the unit has no about (the right contract): it is judged by itself, unresolved does not apply; a creation with such a value — as for a manifest without about, on * (C02-ABOUT-EMPTY-01);
            - folder:<id> covers the unit if it or its about-unit is a member of the folder <id> or of its subfolder: the input of may gets
              chains; the console reads the membership row platform/memberof/<sub>/<rows>/<id> and the chain parent up to the root (P/06.8 N1.1,
              N1.2) only if after the selection of step 5 and of the tiers this can decide the check (below «Cost»); into chains goes only a live
              chain; the read failed or is not confirmed — chains are unknown: the row does not cover, for a role group —
              the right contract «An unreadable group»; ADR-0097 §5, ADR-0099 §2;
            - unresolved → "*" — only for units from the body (about, unit_of, names) that have no name without a row;
            the function covers — README of the package may «covers»
  sub:      the subsystem of the check — the input sub of the function may, section «Subsystem of the check» below
  csrf:     an acting request by cookie with a foreign Origin → 403; a request without Origin is not cross-site (a browser sends Origin on
            cross-site edits), it passes (GP-L02)
  body:     the body limit (≥ 1 MiB; blob PUT /<rows>/<id>/<blob_field> — 32 MiB, the ceilings of chapter 6.1 N1.4); chunked → 400; slow → 408; larger → 413;
            the refusal body is {detail, error: denied}, detail is the implementation's text unless named (GP-L03, the Architect's decision of 2026-10-28)
            (the answer of an early refusal — «Early refusal» of the section «Request parsing and the order of checks»); slow — the body is not read through within BODY_WAIT after the headers
  BODY_WAIT: 5               # s; a default — a deployment can override it, acceptance runs on the default (guess of stage C GP-G01, the Architect's decision of 2026-10-23)
  refusal:  {detail, error: denied}; 403 → the journal access.denied
open_routes: [/, /index.html, /platform/console.js, /platform/console.css, /metrics, /healthz, /session, /session/break-glass,
              /api/held, /api/backup, /api/prepare, /api/take, /api/login]   # /api/login — the entry of people through the console (P/08.4 N1.2)
session:
  GET  /session  → open: {open: true, login_url, server_time, timezone, domain?}; closed to the anonymous: {open: false, login_url,
                   server_time, timezone}; to a proven identity: {open: false, login_url, user, until, via,
                   grants: [{cap, sub?, scope, role?}], admin?, debug?, server_time, timezone, domain?}
  POST /session {token} → {user, until} + the cookie w2c_token (HttpOnly, SameSite=Strict, Secure behind https)
  DELETE /session → {out: true}; removes both cookies (w2c_token, w2c_glass) and the emergency session in memory (GP-L02); POST /session/break-glass {who, why, password} → {user, until} + the cookie w2c_glass; 429 by the limit
  by_state:  the outcomes of the session doors by the states of the gate (gate above; P/06.3 N4 — by reference; sc. 03 of the acceptance of chapter 6.3;
             guess of stage C C06-GATE-OPEN-33-01, the Architect's decision of 2026-10-23):
             open — POST /session → 400 {detail, error: "this console is open"}, not 503; GET /session → 200 {open: true,
             login_url, server_time, timezone}; DELETE /session → 200 {out: true}, removes both cookies; POST /session/break-glass — 400 open (section
             «Break-glass entry», door step 1);
             shut — the doors that need an identity check — 503 {detail: "…admits nobody", error: denied}; GET /session to the anonymous —
             {open: false, login_url, server_time, timezone} (shut above); 503 at POST /session — only in shut, never in open
  login_url: the domain door /api/login (P/08.4 N1.2) — the console forwards it to the domain (open_routes, the forwarding contract «Domain doors»);
             the console issues no tokens of people; the value is LOGIN_URL of the environment (the environment file contract «Environment variables»), not set — "/api/login"
             (a string, not null, at an open console too)
  grants:    one element per (cap, sub, scope, source): a direct row — without role, through a role — role: <name>; the order — by (cap, sub,
             scope), no sub — the empty string, then the direct one, then roles by name in UTF-8 bytes; rows none are included; the assignment admin
             gives no element (ADR-0097 §4, ADR-0098 §4, ADR-0099 §6)
  admin:     true when step 4a of the right contract holds for this identity; a field of the answer, not a row; otherwise there is no field (ADR-0100 §1)
  via:       the step of identity by which the identity of this session is proven: break-glass — the break-glass cookie (item 1; grants — [],
             the right — by the emergency session, P/06.7 N1.9 session); token — the domain token by the header Authorization or by the cookie
             w2c_token (item 3); debug — the debug identity (item 4, together with debug: true); the agent signature (item 2) gives no
             session (analysis of review of stage A 6–7, № 6: the word and its values are here, by the reconciliation with the witnesses at the move;
             an empty `via` for a token is a divergence, a change of behaviour); ticket — a callback by ticket (item 0), only at GET /session
             (P/06.3 N1.9): until — exp of the ticket, grants — the rows of the person of the ticket
  until:     wall-clock seconds of the end of the session; for the debug identity (via: debug, debug: true) — 0: no term, as until of the rows of
             P/08.4 N1.3 — the identity is proven on every request, there is no session (guess of stage C GP-G02, the Architect's decision of 2026-10-23)
  server_time: wall-clock seconds of the console that answered, at the moment of the answer — a JSON number in the writer's notation of P/01.1 N0 «Time in a row»
             (the fraction is at most 3 digits). The clocks of the consoles of the cluster differ within CLOCK_SKEW (N0 «Cluster clocks»),
             therefore the field names the clock of this console only (ADR-0094 B6)
  domain:    {name, root} — from the row domain/root of this cluster: name — the field domain, root — pub: the permanent sign of the domain, independent of the view and of the holder; no row — no field: the cluster is outside a domain;
             exists but does not read — null: unknown, not «outside a domain». The anonymous get no field. So 404 no domain here at GET /domain with the field domain means «the view is not ready yet», not «there is no domain» (V/11 step 8)
  timezone:  the name of an IANA time zone, the value of TIMEZONE of the environment (the environment file contract «Environment variables»), not set — "UTC".
             It is a setting of the cluster, not the zone of the server OS: the OS zones of the servers of a cluster can differ, and people see time in one.
             The console gives the word as it is and computes no time by it (ADR-0094 B6)
  The fields server_time and timezone are in every answer 200 GET /session: of an open console, to the anonymous, to a proven identity;
  only GET carries them, the answers of POST /session and POST /session/break-glass are as before.
```

## Subsystem of the check

Each call of `may` gets `sub` of the row or door that it guards (ADR-0097 §2). The subsystem is determined by the console from the door
before the body, not by a data field. A batch and a compound request pass only if all their checks pass; the door journal writes `sub`
of each check: `access.denied {sub, reason?}`, for edits — the field `sub` of the line of the door journal. `reason` is the refusal word when the
refusal is not `denied` of the right check: `writes via` (P/06.1 N1.1a; ADR-0119 addendum (10)); a refusal of `may` has no such field.

| Door | `sub` of the check |
|---|---|
| doors under `/<s>/…`: unit rows, tables, requests, `DELETE /<s>/asked/*`, `door.pass` | `s` |
| writes of the console: folders and membership, server labels, decommission, `<s>/policy`, `drain`, `schema`; `GET /drain`; `POST /domain/move`; `/where`; `/marks` | `platform` |
| reading «any grant» without a unit: `/session`, the folder list and a single folder (P/06.8 N2), the other `GET` without a unit | `null` |
| `GET /events` | for each event — the item «The subsystem of an event» below |
| the feed `/changes` | `sub` of the subsystem of the row; for a folder row `sub` is empty, as at the door: the members of a folder are open to every holder of a grant (ADR-0096 §6; chapter 6.1 N2 «Change feed») |
| the other doors of the console | `platform` |

- `POST /console/batch`: each row — with its own `sub` (`<s>` of its key); the pre-check before the body (`body_unit`: «a grant on anything») —
  `sub = null`; after the body — `sub` of the unit of the body, for `/marks` — `platform`.
- The references of one check (`rights.unit_of`, `reach`, `body_unit`) — with `sub` of this check: `<s>/keeps` with `unit_of` on
  a unit of another subsystem is checked in `s` on that unit. `rights.names` is otherwise: `sub` of the check is the subsystem of the named unit, otherwise a grant on `*` in `sub` of the row would cover everything it names; the target `*` (`names` `outcomes`) — with `sub` of the check of the row (C06-NAMES-SUB-01, the Architect's decision of 2026-11-01, analysis of the VMS pass).
- A step of a group operation: the target rows — `sub` of each row; the service rows of the operation — by the right of consequences (P/06.9), without a check
  of the person.
- A write of a folder with a member: the folder row — `platform`, the member — in its subsystem (P/06.8 N3).
- The journal of the console doors names `sub` of its checks by the word `platform` with the tree `console`.
- The subsystem of an event is the journal tree of the writer of the line, not `about`; the trees `console` and `audit` — `platform`. The field `sub` of a line
  of `audit` and any application field `sub` do not go into the input of `may` (P/06.4 «Who sees a line»; ADR-0097 §3).
- The emergency session — without changes (step 1).

**Membership guards** (ADR-0097 §5, ADR-0099 §3). A decision about a write depended on membership if tier 3 allowed, or tier 4 allowed
with the membership read, or the decision was given only by a `folder:` row of a direct group. Then the console puts into the write batch (P/01.1
`guards`) guards of the membership rows of the unit and of its about by the read indexes, including a guard of an absent row with
confirmed absence (`index: ""`). It does not guard the chain of ancestors: the window «an ancestor was deleted after the read» remains, as with the revocation of
a grant (`GRANT_LIFETIME`); renaming an ancestor gives no false 412. A conflict is 412, as with any guard. A write of a unit goes under
a claim or a batch (P/06.1 N3), so the guard lies in the same operation; a single write with two guards goes as `op: batch`.

**Cost** (ADR-0097 §5, ADR-0099 §3). Membership and the liveness of a folder are read once per request, at most one membership read per
distinct unit (with about) and one per distinct folder; there is no memory between requests. Tier 1 — no reads; tier 2 needs the unit
row if about did not come in the request; tier 3 — only if the group has a `folder:` row in this `sub`, tiers 1–2 are empty and
the cut-off of the right contract did not decide. A direct group reads membership only if after the selection `folder:` rows remain and the rows `*`
and `unit:` did not cover earlier. For a person without `folder:` the cost is zero.

## Request parsing and the order of checks

From P/06.5 N2 «Console request parsing» (moved without a change), P/06.5 N3 «request → answer (console)» steps 1–8 and P/01.1
N2.1 «Early refusal» (a copy; the owner of the rule for all HTTP doors is P/01.1) (layout audit `B-09`, `B-11`, the Architect's decision of 2026-10-25). «Chapter 6.K» is a chapter of lesson P/06;
«chapter 6.3 N1.3» in the steps is the section «The gate» above. The domain console parses a request the same way (P/10 N2); the order of its own
checks is P/10 N3 (the role door before the gate, then the gate).

**Console request parsing** — by P/01.1 N2.1: the query as `application/x-www-form-urlencoded` (`+`, `%XX`, empty pairs),
the JSON of the body by RFC 8259 (a repeated field name, `NaN`/`Infinity`, BOM, not UTF-8, a lone surrogate — a refusal), the path byte for byte
without normalization, HTTP by RFC 9112, the early refusal. The deviations of the console, the same for all its doors (chapters 6.1–6.6):
a parse refusal is 400 ConsoleRefusal `{detail, error: refused}`, not `Fault {kind}` of P/01.1; no route — 404 NoRoute, the method — 405
(P/01.1 gives 404 to both); a parameter that the door reads is repeated — 400, except `v` of the module — 404 (N1.1); the body `chunked` — 400
([chapter 6.3](../../06-console/spec/06.3-console.norms.md) N1.3 `body`); the depth of the JSON of the body is 64 ([chapter 6.1](../../06-console/spec/06.1-console.norms.md) N1.4). The doors of other chapters refer here and name only their own deviations.

**Numeric query parameters** (C06-EVENTS-QUERY-LEXEME-162-01, the Architect's decision of 2026-10-27). A query parameter that a door reads as a number is first
URL-decoded (P/01.1 N2.1: `+` is a space, `%XX` is a byte), then its whole value goes by the reader grammar of its
type of the [row codec](../data/codec.tsv): time (`from`, `to` at `GET /events`; `since`, `until` at `GET /domain/alarms`
of the domain console) — `time`: `^(0|[1-9][0-9]*)(\.[0-9]+)?$`, finite in binary64; an integer (`limit`, `late`) — `integer` as an integer lexeme
`^-?(0|[1-9][0-9]*)$`, then the bounds of the door; a number — `number`, the decimal notation of the reader. Out of the grammar — 400
ConsoleRefusal, `detail` is the name of the parameter (a door with its own `detail` names it in its deviation). Consequences: `+1`
(= « 1»), `%2B1` (= `+1`), `%201`, `1e3`, `-0`, `1_0`, `.5`, `limit=01` — 400; `%31` (= `1`) — accepted. The grammar of the resource
door is its own (P/05 N1.3).

**Early refusal.** Follow P/01.1 R050: send the complete refusal with `Connection: close` first, then discard raw HTTP-stream bytes without parsing/execution, bounded by the declared length when framing supplies one, the declared raw-byte limit and the absolute monotonic drain deadline. The interval starts after the complete refusal is sent; a trickle does not extend it and chunked discard does not wait for a terminal chunk. Then close; add no second refusal or executed pipelined request. The console ([P/06.5](../../06-console/spec/06.5-console.norms.md)), its bytes door (P/06.1) and the resource (P/05) keep their own outcomes and declared limits. This reference does not copy P/01 input-timeout responses/budgets onto them: console slow-body `408` and BODY_WAIT from headers remain owned here; forwarding, pass and stream response budgets are not replaced by a common P/01 response deadline.

A body refusal at the doors of the console: chunked — 400, larger than the limit — 413, slow — 408, short — 400; the body ConsoleRefusal
`{detail, error: denied}` (P/06.5 N4 the row «body»; GP-L03, the Architect's decision of 2026-10-28).

`order` — the order of checks on a request of the cluster console:

```
1. lane: reserve / monitor / feed / callback (the callback listener and the role socket; chapter 6.5 N2) / streams (the route stream
   of the pass of the second kind) / common; busy → 503 busy
2. erase X-User; framing and the limit by the header; chunked → 400
3. determine the trust gate — by reading on every request, without a cache: the store did not answer or the trust is unknown →
   503 {error: denied} before parsing the path and the body (earlier — only steps 1–2: the lane and the frame; reconciliation of python and go M10/3–5, U19); no domain and not loopback → 403 FOR ALL paths,
   the open ones and /session* included; no such door has been executed yet
4. /session* → the procedure of chapter 6.3 N1.3: after the identity is established, if the request acts by cookie,
   a foreign Origin → 403 before a change of the session/cookies; otherwise the answer of the procedure
5. path → the door and what it requires (chapter 6.3 N1.3 need); no path → 404; the path is compared byte for byte (P/01.1 N2.1):
   `/counters/`, `/where/` are not routes; query — by P/01.1 N2.1, a parameter that the door reads is repeated → 400 {detail, error: refused}
   (except `v` of the module — 404, N1.1)
6. who calls, if the door requires an identity (chapter 6.3 N1.3 identity) → otherwise 401; `POST /domain/move` by a root signature judges the identity after reading the body, P/06.7 N1.8; `GET` of the shell of a mounted subsystem with
   console.shell → 302 to the console login (P/06.5 N2 «Login at the shell»; ADR-0094 A4), it does not become an open route
7. the identity is chosen by cookie and Origin is foreign → 403; then the units from the path and the required capability → a grant or 403 + the journal
8. read the body with the actual limit and timeout; if the unit is determined by the body, check it here;
   unit_of / reach / names add checks. Not a single change before all checks are completed
9. the door — the lesson of the door (P/06.5 N3 step 9)
```

## The gate with grants

From P/06.7 N1.9 `cluster` (the side of the cluster console; moved without a change; layout audit `B-09`, `B-11`, the Architect's decision of 2026-10-25): in the state `on` a person is admitted
only by the entry and the grants. The side of the process `domain` is [P/08.4](../../08-domain/spec/08.4-domain.norms.md) N1.5; the domain
console is P/10 N1.5 (the grants `domain/grants/domain`).

```yaml
cluster:   P/06.3 N1.3 identity step 3 (Bearer | the cookie w2c_token): the token — the function token of the domain token contract «The check»
           by the set and domain/revoked of this cluster with expect {kind: person, cluster: null} — the domain token contract «The token» (the Architect's decision
           of 2026-10-20, ADR-0083 addendum (14) item 7; analysis of review of stage A 8–10); a refusal — 401 {error: denied, detail:
           "token refused: <word>"}, the form `Denied` (`Platform/common/contracts/gate-and-pass.api.openapi.yaml`), except
           no_revocations: the rule «Unreadable row» (503 {error: "unavailable"}; the Architect's decision of 2026-10-28 by the reconciliation ddc9bee1e); then may (the right contract) with
           grants = doc of the row domain/grants (the copy of this cluster; exists but does not read — the rule «Unreadable row»), as_of — its as_of, disabled — domain/disabled of this
           store (exists only at the holder), cap and unit — need of P/06.3 N1.3, sub — section «Subsystem of the check», roles — below,
           iat — iat of the token; deny — 403 {error: denied, detail: "<name> may not <cap> <sub>/<id> | here"}; unavailable — the rule
           «Unreadable row»; stale — detail «the grants this cluster holds are older than a day: its agent has not reached the
           domain»
roles_in:  the role table: the copy of domain/roles of this cluster (P/09.1 N1.4 member_roles). No row — roles = null. The table is taken
           only if its doc_sha256 matched the hex SHA-256 of the text doc of the current copy of grants and its as_of passes step 4 of the right contract; otherwise, and
           with an unreadable row, — roles = "unreadable". An unreadable element of lines of the copy: for the subject role:<R> — unread {role: R},
           with sub if it is read; the subject is not read — unread "all"; a direct group skips such a line.
           The console expands: {<name>: [{role, until, at}…]} from assigned and groups once per version of the copy, not per check; at of the role admin — admin_at[<name>], for the other roles 0
           (ADR-0098 §4)
```

## Refusals of the gate

From P/06.3 N4 (moved without a change; layout audit `B-09`, `B-11`, the Architect's decision of 2026-10-25).

**Unreadable row** (the owner's decision of 2026-10-28). A row of the domain that the access check reads for this session
(the identity, the signature, the grant, the input of `may`) exists but does not read (an outcome of its family) — 503 `{error: "unavailable", detail?}` (the form
`Unavailable` of the [common forms of the contract](gate-and-pass.api.openapi.yaml); `detail` at the cluster console is mandatory — P/06.5 N4); not 401, not 403, not «no row»; it does not count
toward the limits; there is no journal. The exceptions are only those named here:
- the debug entry of the console (section «The gate» `identity` item 4): an unreadable `domain/disabled` — «as without the entry»;
- an unreadable element `lines` of the grants (the path `/doc/lines/*` of the families `grants`; P/08.4 N1.3 `unreadable`): in a direct group a skip with
  a diagnostic, the other lines decide; the row as a whole reads (the Architect's decision of 2026-10-28 by the reconciliation ddc9bee1e); for a role line —
  the sign `unread` of the function `may`, the outcome is decided by the right contract (ADR-0099 §2).

The output `unavailable` of the function `may` (an unreadable role table, an unreadable role group) is an application of this rule: 503, not 403.

The unit rows (the grants `labels:…` and `unit:` of the about-unit) are not rows of the domain: their unreadability is the section «The gate»
`scope` (the grant does not cover) (the Architect's decision of 2026-10-28 by the reconciliation ddc9bee1e).

The emergency session (the cookie `w2c_glass`, `may` step 1 `glass` → allow) does not read the grants and `domain/disabled` — their unreadability
does not stop it; `GET /session` of the emergency one — `grants: []` (C06-GLASS-UNREADABLE-01, the Architect's decision of 2026-10-28).

The traces of the domain (section «Traces of the domain») require only the presence of a row: an unreadable row is a trace. The lines below are
applications of the rule.

| Cause | Code | Body | What the caller does |
|---|---|---|---|
| break-glass entry: the password did not match | 401 | `{detail, error: denied}` | do not create a session; the common journal of access refusal; counts toward the limit (chapter 6.7 N1.10; P/08.4 N1.10) |
| break-glass entry: no row or no member (the conditions) | 403 | `{detail, error: denied}` | do not create a session; the common journal of access refusal |
| not an identity | 401 | `{detail: "this console asks who is calling: …", error: denied}` | log in (login_url) |
| no grant | 403 | `{detail: "<who> may not <cap> <unit \| here>", error: denied}`; journal | — |
| no domain, not loopback | 403 | `{detail: "this cluster is in no domain … loopback", error: denied}` | connect a domain |
| there were keys, nothing to check with | 503 | `{detail: "…admits nobody", error: denied}` | restore the trust |
| the row `domain/keys` exists but does not read — nothing to check a token with ([family `keys`](../../08-domain/data/keys.outcomes.tsv)) | 503 | `{error: "unavailable"}` — the rule «Unreadable row»; not «the token is valid» | wait for a readable row (DF-OUTCOMES-109, the Architect's decision of 2026-10-25) |
| the row `domain/member` exists but does not read — nothing to check the signature of its own agent (`X-Agent-Signature`) and the trace of the domain with ([family `member`](../../09-agent/data/member.outcomes.tsv)) | 503 | `{error: "unavailable"}` — the rule «Unreadable row»; not «the signature is valid», not «no domain» | wait for a readable row (C06-GATE-UNREADABLE-ROW-503-01, the Architect's decision of 2026-10-28) |
| the row `domain/disabled` exists but does not read — nothing to check the input `disabled` of the function `may` with ([family `disabled`](../../08-domain/data/disabled.outcomes.tsv)) | 503 | `{error: "unavailable"}` — the rule «Unreadable row» (C06-GATE-DISABLED-UNREADABLE-JOURNAL-01, the Architect's decision of 2026-10-28); `may` does not decide; the debug entry of the console — «as without the entry» (section «The gate») | wait for a readable row (C06-GATE-UNREADABLE-ROW-503-01, the Architect's decision of 2026-10-28) |
| callback by ticket: the header out of form, no record, the wrong transport or leaf, the session kind is not `person`, the door outside the list, the ticket token is revoked, expired or its key is withdrawn, the person is disabled (section «Pass of the second kind» `ticket`) | 401 | `{detail: "ticket refused", error: denied}`; the cause is only in the line of the console log, the worker has no need to know it | finish the translation of the request: the ticket is dead, there is no retry (ADR-0094 B1) |
| a foreign Origin on an acting request by cookie | 403 | `{detail, error: denied}` | — |
| `/session POST` at an open console (section «The gate» `session` `by_state`) | 400 | `{detail, error: "this console is open"}` | — |
| `/session GET` and `DELETE` at an open console (section «The gate», `by_state`) | 200 | GET — `{open: true, login_url, server_time, timezone}`; DELETE — `{out: true}` | — |
| break-glass entry: the limit | 429 | `Retry-After` | wait |

A refusal of the gate has no side writes of the door. The lane, the frame, no path, the method, the body, the common entry limit of the console (429) —
[chapter 6.5](../../06-console/spec/06.5-console.norms.md) N4.

## Traces of the domain

From P/06.3 N1.8 (the late layer, introduced by lesson P/08; guess of stage C GP-G05, the Architect's decision of 2026-10-23). «N1.3» is the section «The gate» above, «chapter 6.7 N1.9»
is the section «The gate with grants» above.

The states `on`, `open`, `shut` of the console gate are N1.3. «Keys exist» means the row `domain/keys` reads and is accepted
by the function `keys` ([domain key set contract](keys.md); analysis of review of stage A 8–10, № 13) with the pinned root. «A trace of the domain» is any of the rows `domain/root`, `domain/member`, `domain/revoked`,
`domain/grants/*`, `domain/break-glass/*`, or this console process has already seen keys: then without keys — `shut` (503), not `open`.

In the state `on` the identity goes by the order of N1.3 `identity`: the agent signature — [agent signature contract](agent-signature.md); the token — the function `token` of the
[domain token contract](domain-token.md) «The check» (owner P/08.2; analysis of review of stage B 3–5, V1) by the set of this cluster with `expect {kind: person, cluster: null}` (the Architect's decision of 2026-10-20, ADR-0083 addendum (14) item 7; analysis of review of stage A 8–10); the grants of a person and the entry — P/08.4. Without an identity — 401, not 503: 503 is only `shut`. In `on`
a person is admitted only by the entry and the grants (section «The gate with grants»); «loopback — operator» is only `open`; the agent of its own cluster passes by
the signature ([agent signature contract](agent-signature.md); analysis of review of stage A 8–10, № 13).

```yaml
loopback:  «loopback — operator» — only the state open (no domain, N1.3); in the state on — only «The gate with grants» above
```

## Rights by the body

From P/06.3 N1.5 (the keys `rights:` of the manifest — the boundary of the rights of people), P/06.7 N1.9 and P/10 N1.5 (`body_unit`, `session`), P/08.4 N1.5
(the line `domain`) without a change of behaviour (guess of stage C GP-G05, the Architect's decision of 2026-10-23). The form of the keys is `Platform/02-installer/spec/02.1-installer.schema.json` (`rights`; [form](../../02-installer/spec/02.1-installer.schema.json), P/02.1).

| Key | Meaning |
|---|---|
| `routes: {view: [families], edit: [families]}` | the writes of the family require less than `admin`: `view` or `edit`; for unit rows only creation is lowered |
| `cluster_rows: true` | any write of a unit row requires a grant on the cluster |
| `unit_of: {table: field}` | a row of the table belongs to the unit from the field; a write requires the right on the unit of the old and of the new row |
| `reach: {group: [fields], cluster: [fields], requests: [actions]}` | what an edit changes beyond the unit: a group field — all units of the old and of the new group; a cluster field — a grant on the cluster; a request with an action — `edit` on the whole group (the action is the field `action` of the request body, [chapter 6.4](../../06-console/spec/06.4-console.norms.md) N1.5 `action`; analysis of review of stage A 6–7, № 14); `reach.group` requires `placement.group_by` |
| `names: [{field, unit, sub \| of, action?}]` | the units that a row names inside a `json` field; their targets are added to the reach of the edit |

```yaml
names:     # the layout of rights.names: [{field, at?, walk?, quiet?, unit, sub | of | kind, kinds?, action?}] (guess of stage C GP-G07, by the witness, the Architect's decision of 2026-10-23; at, walk, kind — ADR-0105 item 4)
  field:   a json field of the row; its value is a list of objects, with at — also an object
  at:      a path from an object: from an element of the field's list, from a node of walk, from the value itself if it is an object. Keys are joined by a dot, [] — each element: target.include[]. The objects at the end of the path are what the entry is read over. No key on the path — the entry is silent; a value not of that form — "*"
  walk:    [<key>…] the keys of nested branches: the value is a list of objects of the same form, the entries of names of this field are read over them too; deeper than 32 — "*" (P/06.1 N1.4); a key that is not a list — "*"
  quiet:   [<key>…] an object with such a key in which no entry named a unit names nobody and gives no "*": a step without a target (wait, ask, alarm); a unit, if named, such an object names as usual
  kind:    the name of the key of the object whose value is the kind of the target, instead of sub and of; kinds: {<kind>: {of: <subsystem>} | {of: <subsystem>, table: <table>} | {folder: true} | {server: true}}: of — a unit of this subsystem; with table — the value of unit is the name of a table row, the unit is its field by rights.unit_of of that subsystem, as for a table edit; the row does not read or the table is not in unit_of — "*"; folder — the id of a folder: the target is the folder object of the right contract, chains by reading; server — a server has no unit: "*"; a kind outside kinds — "*"
  unit:    the name of the key of the object whose value is the id of the unit; an empty or absent id — the entry does not name
  sub:     the name of the key of the object whose value is the name of the subsystem of the unit
  of:      the name of the subsystem itself (constant) — instead of sub
  action:  the name of the key of the object whose value is the action of a request to the named unit; with at the key is read from the object the path goes from (a step, a node of walk), not from the end of the path: the target lies deeper than the action word, otherwise output through target would bypass edit on the group; the action is named in rights.reach.requests of the manifest of its subsystem —
           edit on all units of its group, as for the request itself; no field or the action outside the list — only the unit (C06-NAMES-ACTION-01, the Architect's decision of 2026-11-01, analysis of the VMS invariants)
  name:    the unit is <subsystem>/<id>; the entries of names with one field are read over each object of the list together
  outcomes: the value of the field null — nobody; a value not JSON or not a list — "*" (all: the edit reaches all units);
           an element of the list that is not an object — skipped; an object in which no entry named a unit and there is neither a key of walk with a list nor a key of quiet — "*"; a branch node is judged by its children; an empty list by at — nobody
           the exclusions of the target (exclude) do not change the reach: at does not name them, the right is judged on the whole included area
body_unit: need whose unit is in the body (section «The gate» need: /marks, POST /<sub>/requests): at the cluster console — as create_about:
           before the body — the pre-check «there is a grant edit on anything» (none — 403, the body is not read), after the body — the exact
           check of edit on the unit of the body (unit) and on the units of rights.unit_of, reach, names; a unit is not resolved — by
           unresolved ("*"); a grant on the about-unit of the row — by scope; at the domain gate before the body — unit = "*", the checks
           after the body are kept (added by the reconciliation of M11; guess of stage C C06-BODYEDIT-SCOPE-33-01, the Architect's decision of
           2026-10-25)
create_about: the creation of a unit row whose unit is about from the body (rights.routes): before the body — the pre-check «there is a grant
           of the needed capability on anything» (as body_unit, but at the cluster console — without the requirement "*"), after the body —
           the exact check by about from the body (guess of stage C GP-L06, the Architect's decision of 2026-10-23)
unresolved: a unit that cannot be resolved (no row, the row is unreadable) — by about, unit_of, names — a grant on
           "*" is needed; cluster_rows — always "*" (GP-L06); only units from the body — a unit named in the path or ?unit= is matched
           by scope above (C06-EVENTS-QUERY-UNKNOWN-138-10, the Architect's decision of 2026-10-26)
session:   GET /session of a proven identity (section «The gate» session) — grants: [{cap, sub?, scope, role?}] — the effective rows of this person and of the groups of their roles (step 5 of the right contract with sub = null)
           (step 5 of may) at this console, the order — section «The gate» session grants; for the emergency session — [] (its may — allow by glass)
domain:    the domain console and the process domain: may with grants = domain/grants/domain, as_of null, roles — the rows of roles and groups of the holder (P/08.4 N1.3b roles_at_holder), iat — of the token, sub — null; view — GET /domain*, /manifest,
           /mounts and the doors of the lesson with GET; admin — the other doors /domain/* (the table of the [forwarding contract](../forwarding.md)
           «Domain doors»; layout audit, B-10); unit = "*" at admin; except POST /domain/revoke — without an identity and a grant: the credential is the token in the body
           (P/08.4 N1.2 revoke); the doors of the view GET /domain, GET /domain/<sub>/<rows>, GET /domain/<sub>/tables/<table>, all doors
           of the kept edit P/08.6 N1.3, N1.3b, GET /domain/users, /groups, /roles, GET /domain/grants, PUT /domain/grants/<cluster> with a cluster ≠ domain,
           POST /domain/batch by row (P/08.4 N2), GET and PUT /domain/memberof — «Judgement by target» of the right contract, not this line (ADR-0110); the domain console judges them by the same norm as the process
```

## Break-glass entry

From P/06.7 N1.10 (the cluster console; the domain console has no emergency session — it has no steps 1 and 2 of `identity`, P/10 N1.5) and
P/08.4 N1.10 (the attempt limit is common to `POST /session/break-glass` of the cluster console and `POST /api/login` of the process `domain`,
to which the domain console passes it) without a change of behaviour (guess of stage C GP-G05, the Architect's decision of 2026-10-23). The holder's side (the row
`domain/break-glass/<cluster>`, `GLASS_MIN`, `carry`) — [P/08.4](../../08-domain/spec/08.4-domain.norms.md) N1.6.

```yaml
door:          POST /session/break-glass {who, why, password} at the cluster console (section «The gate» open_routes) — in order:
               1. the console is open — 400 {error: "open", detail: "this console is open: there is nothing to break into"}
               2. the body is not {who, why, password} as strings, who or why are empty — 400 bad body
               3. the limit («Attempt limit» below)                       → 429
               4. no domain/member — 403 {error: denied, detail: "no emergency account: its store names no member"};
                  domain/member exists but does not read (the family member, `Platform/09-agent/data/member.outcomes.tsv`) —
                  503 {error: "unavailable"}, as «does not open» (the rule «Unreadable row» of the section «Refusals of the gate»); it does not count toward
                  the limit (C06-BREAKGLASS-MEMBER-UNREADABLE-01, the Architect's decision of 2026-10-28);
                  no row domain/break-glass/<this cluster> — 403 {error: denied, detail: "no emergency account: …"};
                  does not open — 503 {error: "unavailable", detail: "the emergency account does not open"}
               5. the password did not match — 401 {error: denied, detail: "break-glass: wrong password"} (counts toward the limit)
               5a. there are already GLASS_SESSIONS_MAX open sessions — 429 the form RateLimited of the contract of P/06 (`Platform/06-console/spec/06-console.api.openapi.yaml`), detail «too many
                  emergency sessions», Retry-After — the seconds until the end of the earliest session; the refusal does not count toward «Attempt limit»
                  (added by the reconciliation of M11, P20)
               6. 200 {user: "break-glass(<who>)", until} + the cookie w2c_glass; the session is in the memory of the console process,
                  GLASS_SESSION, there is no token
GLASS_SESSION: 900         # s
GLASS_SESSIONS_MAX: 256    # open emergency sessions at the console; expired ones are not counted
journal:       access.break_glass.opened {who, why} | .refused {who, why, reason} | .limited; every action under the session
               stronger than view — access.break_glass {who, method, path}
```

The check of the password hash — the [password hash contract](password-hash.md) (`verify`; GP-G06).

### Attempt limit

«N1.2» is [P/08.4](../../08-domain/spec/08.4-domain.norms.md); «chapter 8.0 N1.8» is P/08.0 (layout audit, `B-08`: the circle through P/08.4 N1.10 is removed — the rule is here).

```yaml
scope:     at the process domain — POST /api/login and POST /api/verify (P/08.4 N1.2a); at the cluster console — POST /session/break-glass; each door has its own count
count:     a refusal is a wrong pair at POST /api/login (N1.2), at POST /api/verify (N1.2a, 401) and step 5 of the section «Break-glass entry» door above; a success and a form refusal are not counted; an attempt is every call that passed
           the form (the moment for ceiling)
address:   at the cluster console — the address of the TCP peer (address headers are not read); at the process domain — the address of the client that
           the domain console passes (its TCP peer; chapter 8.0 N1.8 pass): the process trusts a passed address only from the domain
           console, from other connections — the address of the TCP peer; a count by the TCP peer of the process would count all people as one address
           of the console (added by the reconciliation of M11, P16)
  header:  X-W2C-Client — the forwarding contract «Client address» (who sets it, on which connection the process trusts it, the removal
           of one that came from outside; analysis of review of stage A 8–10, № 23 / decision 3)
key:       the count key — at the process domain the pair (address, name): the name is the field user of the body of POST /api/login byte for byte, including
           a name that does not exist; at the cluster console — the address (break-glass: the door is not forwarded, its TCP peer is the client itself; who is free, the password is one per cluster)
           (the Architect's decision of 2026-10-21, ADR-0083 addendum (19) item 2; analysis of review of ADR-0090, № 26): forwarding reduces the people of the domain to the address of the console
           (P/06.7 N1.4; the address of the browser is not carried through transition 1 without a proven role), and a count by one address would lock
           the entry for everyone; the pair narrows the locking to one name. At the process domain both per_address and ceiling go by the pair (by
           the reduced address, ceiling would again brake the whole domain). The cost: trying one password over many names
           is limited per name, not in sum — the protection against such «spraying» is the password policy, not the limit
per_address: 5 refusals of this key in the last 900 s → 429; Retry-After — the seconds until the oldest leaves the window
verify:    POST /api/verify has three count keys, each — refusals 401 in the last 900 s; the author is user of the token of the person of the forwarding, the name —
           user of the body byte for byte, including a name that does not exist; the address is not judged (through backend it is the same for all):
  pair:    (author, name) — 5 refusals → 429 to the check of this name by this author
  author:  the author — VERIFY_FAIL_MAX refusals of all their pairs → 429 to this author for any name
  name:    the name — VERIFY_NAME_FAIL_MAX refusals from all authors → 429 to the check of this name by any author; the guessing budget of one name
           is held by this key, not by the number of authors (ADR-0119 addendum (14) item 1)
  answer:  the admission is before the password check, atomically under the lock of the three keys of the attempt (pair, name, author; taken in this order by all
           attempts), not under a common lock of the process: the other doors do not wait. For each key the sum is judged — refusals 401 in the last
           900 s plus the reserves of the running checks of this key; at all three the sum is below the limit — a reserve in each key, the password
           is checked; at least at one it is not below — 429, the password is not checked, there is no reserve. Otherwise two simultaneous admissions at the boundary
           would both see 4 and give 6 refusals of 5 (ADR-0119 addendum (18) item 1; the Quint model v119)
  outcome: 401 — the reserve becomes a refusal with the time of the answer; 200, 503, 409 deposed, another refusal after the admission, a break or a timeout —
           the reserve is removed; a success and 429 spend no budget. The finalization of the reserve is single and atomic, under the same lock of
           the keys: the outcome is applied to the reserve once, a repeated one (a late answer after a timeout, a break after 401) is not applied
           («M» of review (18) Codex)
  retry:   Retry-After — by the key that fired: the sum is not below the limit only because of reserves (the refusals of the window are below the limit) —
           Retry-After: 1; otherwise — the seconds until the oldest refusal leaves the window; several fired — the key with the largest such
           term (with equal ones — pair, name, author), otherwise a retry after Retry-After would get 429 again (the Specification's decision;
           addendum (14) item 2, (16), (18) item 1); limit of the line domain.verify.limited — this key
  apart:   the count of the check and the count of the entry are separate: refusals of the check do not go into ceiling of the entry, refusals of the entry do not go into the count of the check; therefore
           an author trying names does not brake the entry of the domain, and the entry of the one checked is not locked — by the key name either
           (ADR-0119 addendum (1) item 2, addendum (13) item 1, addendum (14); addendum (5) item 4 is replaced)
VERIFY_FAIL_MAX: 20
VERIFY_NAME_FAIL_MAX: 10
ceiling:   at POST /api/login and break-glass: 20 refusals of all keys of the door in the last 900 s → to each key at most one attempt per
           60 s; earlier — 429, Retry-After — the seconds until the next one; POST /api/verify has no ceiling — its place is taken by the author ceiling of verify
body:      429 {error: "too many attempts", detail} and the header Retry-After (at the console — the form RateLimited of the contract of P/06, `Platform/06-console/spec/06-console.api.openapi.yaml`);
           there is no lock by one name without the address — it would let anyone disable an administrator from any address; through
           forwarding those who enter have one address, and the pair (address, name) locks the name for all who enter through the same console — this is
           a narrowing from «all» to one name, not a protection against locking an administrator (№ 26)
```

There are no vectors for these rules — they are checked by the scenarios of the acceptances of chapters 6.3, 6.7, of lesson P/10 and of chapter 8.4.

## Pass of `door.pass`

From P/06.5 N1.8; the grammar of `door.pass` in the manifest — [P/02.1](../../02-installer/spec/02.1-installer.norms.md):

```yaml
manifest: door: {routes: […], pass: [<segment>…]}   # the segments do not repeat routes, rows and where (P/02.1)
rule:     a console route whose first segment is in pass is passed to a live worker of the subsystem with a door (the smallest name):
          the method, the path `/<segment>[/…]` — without the mount prefix at any root and mount, as at the domain console
          (CONSOLE_ROOT=<sub> — /accounts/x, mounted — /<sub>/accounts/x → to the worker /accounts/x; C06-DOOR-PASS-PATH-01,
          the Architect's decision of 2026-10-29, analysis of V/03 question 7), query — as it came, the body ≤ 1 MiB, the headers Authorization,
          Content-Type, Idempotency-Key, X-Operator and X-W2C-Supervision (set by the console, section «Supervision»); the identity is proven by the cookie w2c_token — the console puts its token into the passed Authorization: Bearer,
          it does not pass the cookie itself (C06-PASS-COOKIE-01); at the cluster console the emergency session (identity item 1) is not passed: it has no domain token, the worker has nothing to check —
          403 {detail: "the emergency session does not reach a worker's door", error: denied} (C06-PASS-GLASS-01, the Architect's decision of 2026-11-01, analysis of the VMS pass);
          the console gate checks its own earlier; the worker checks the credentials again (the cluster console; the worker on
          the domain does not check people — below); the answer as it is (the status, Content-Type, the body ≤ 4 MiB); the client to the worker — with
          the role certificate, if any; to the worker on the domain — only with the role certificate domainconsole
codes:    503 «this console passes no route on to a worker» (no client) | 503 «no worker of <sub> with a door is heard»
          | 400 the body is not read | 408 the body reads slowly (BODY_WAIT, section «The gate» body) | 413 the body is larger than
          the limit (N4) | 502 «<worker> did not answer»: the worker's answer is not received in full within PASS_WAIT, a connection refusal,
          a break or an answer body larger than 4 MiB — without a partial body and before the headers to the client
words:    the body of the refusals of codes — ConsoleRefusal {detail, error: denied}: the text in «…» is detail, 400/408/413 — as body;
          acceptance compares the code and error, not detail; what is named otherwise is kept — at the domain console no worker is heard —
          503 {error: "unavailable"} (P/10 N1.6 absent) (GP-L03, the Architect's decision of 2026-10-28)
PASS_WAIT: 5               # s; a default — a deployment can override it, acceptance runs on the default (guess of stage C GP-G01, the Architect's decision of 2026-10-23)
```

Which worker gets the route depends on the side (the table above). The domain console passes the path `/<segment>[/…]` and the query with the client of
the role `domainconsole`; no worker on the domain is heard — 503 `{detail: <text of the codes row>, error: "unavailable"}` (P/10 N1.6 `absent`;
C06-GP-L03-DOMAIN-WORKER-503-01, the Architect's decision of 2026-10-28). The worker on the domain accepts
`door.pass` only from a client with the role certificate `domainconsole` (otherwise 403 `forbidden`) and does not check the credentials of people
again: the token of the person was checked by the gate of the domain console ([P/03.7](../../03-worker/spec/03.7-worker.norms.md) N1.6
`door_client`; edit `d92df6554`; analysis of review of stage B 8–10, № 9).

### Supervision

ADR-0119 addendum (5)–(7): supervision is `supervision: {<sub>: <supervisors role>}` at a domain role (P/08.4 N1.3a); the cluster console judges it
by the copy of the role table of the member (P/09.1 N1.4 member_roles: `assigned`, `groups`, `supervision`, `unreadable`); it does not know the meaning of the subsystem.

```yaml
roles_of:  the effective roles of the person u by the copy — roles_now of P/08.4 N1.3a over assigned and groups of the copy
required:  required(u, s) — at least one role of roles_of(u) carries supervision[s]; the copy does not read or has not arrived, or unreadable has at least
           one role or group (any: of an unreadable role neither the supervision nor the members are known, of an unreadable group — the members), — true (in favour of
           supervision; ADR-0119 addendum (5) item 3)
header:    X-W2C-Supervision: <s>[,<s>…] — all s with required(u, s), in ascending order of bytes, comma-separated; none — "-"; the copy does not read, has not
           arrived or unreadable is not empty — "*" (supervision is needed for any subsystem); the cluster console sets it on every request of a person
           forwarded to a worker (door.pass of both kinds; at the second — by the person of the ticket); one that came from outside is removed (ADR-0119 addendum (7) item 1)
ok:        ok(v, u, s) — the checked v is in the role of supervisors supervision[s] of every role of roles_of(u) that carries it; the role
           of supervisors or its group in unreadable — v is not a member (ADR-0119 addendum (5) items 2, 3); the copy does not read or has not arrived, or
           unreadable is not empty, — ok = false: supervision required by an unreadable one cannot be confirmed — the roles of supervisors cannot be determined (addendum (7) item 4)
limit:     unreadable collects the unreadable roles and groups of the whole domain (P/08.4 N1.3b): one spoiled role row gives * to all people of all
           clusters and stops every action with supervision until the row is repaired; the signal to the operator — the journal and the alarm of the holder
           domain.roles.unreadable (P/08.4 N1.3b), the cause in the answer of the check — supervision.unreadable
one:       the header and the answer of the check door (P/06.7 N1.15) — one function by one copy; the copy changed between requests — the answer of
           the check judges, it is later (ADR-0119 addendum (7) item 2)
```

## Pass of the second kind

The first kind above passes the credential of the person to the worker, so a captured worker could act on their behalf after the request too. The second kind passes
the request without the credential, with a ticket for this request: the worker calls the console doors back only by the ticket, only while the request is open, only from the transport of its own
role and only to the doors of the list (ADR-0094 B1, addendum (3), (6), (12); ADR-0091 addendum (30)). The grammar of `door.pass` is [P/02.1](../../02-installer/spec/02.1-installer.norms.md) N1.4; the closed list of doors is [P/06.3](../../06-console/spec/06.3-console.norms.md) N1.9.
The accounts of the subsystems that need the first kind stay on it until their transition; `door.pass` of one manifest is of one kind.

```yaml
manifest: door: {pass: {routes: [<path>…], calls: [<door>…], stream: [<path>…], wait: {<path>: <s>}, refusals: {form: problem, codes: {<status>: <code>}}}}
match:    <path> matches the beginning of the request path by whole segments, the path is without the mount prefix: api covers /api and /api/x, not /apix.
          A request goes to the pass if an element of routes covers it. Its first segment is the first segment of an element of routes, and no element covers
          it — 404 by the form of the route (refusals below). A stream: an element of stream covers it. The limit: the longest covering key of wait;
          no key — PASS_WAIT, a stream has no limit, the end of the request closes it (close below)
rule:     as for the first kind (the method, the path without the prefix, query as it came, the body ≤ 1 MiB, a live worker with a door), except the lines below
to_worker: exactly the headers: Content-Type, Idempotency-Key, If-Match, Last-Event-ID — as they came; X-W2C-Pass-Ticket — the ticket;
          X-W2C-Supervision — by the roles of the person of the ticket (section «Supervision»);
          X-W2C-Pass-Console — at the cluster console, the callback listener of the issuing instance, https://<SERVER_NAME>:<CONSOLE_CALL_PORT>, only with a kit (without it the worker calls the role socket); at the domain console — the exception of P/10 N1.6;
          X-W2C-Loopback: 1 — only if the address of the TCP connection of the client with the console is 127.0.0.1 or ::1 (address headers are not read).
          Authorization, cookies, X-Operator, X-User and the others do not go; X-W2C-Loopback, X-W2C-Pass-Console and X-W2C-Supervision that came from outside the console always removes
to_client: from the worker — the status, the body and exactly the headers Content-Type, ETag, Cache-Control (ADR-0112 addendum (3) item 5, addendum (4) item 5); the console adds X-Content-Type-Options: nosniff and
          Content-Security-Policy: sandbox: otherwise a script of a captured worker would run under the origin of the console with its cookie
types:    Content-Type of the answer — application/json, application/problem+json, text/event-stream, with parameters or without; an answer without a body (204, 304) — without
          Content-Type; anything else — 502 «<worker> did not answer», the worker's body does not go to the client; the type is compared case-insensitively, by the part before «;»
transport: with a kit — https to the url of the heartbeat: own_client of the role certificate contract, role <sub>worker, host — the host of the url; the client leaf of the role console.
          A foreign or wrong server leaf — 502 «<worker> did not answer», neither the headers nor the body go. Without a kit — http to the url of the heartbeat on loopback (P/03.4 N1.7 door_address)
ticket_form: 128 random bits by a cryptographically strong generator, 32 characters [0-9a-f]; a new one for every pass; not written to the journal or the log
record:   a record of the instance, only in memory: {user, session kind, jti, kid, iat, exp, the open external request, the addressee instance: {sub, worker, server}, stream}; for an addressee with the doors
          of the domain or with an entry of the first kind in calls — also the token of the external request: it is needed only by the forwarding to the domain console (P/06.3 N1.9) and by the pass first_kind below, it goes neither to the addressee of the ticket nor to the journal.
          The session kind is the word via of the session: person — a domain token; break-glass, debug and open (the console is open) are recorded but give no callback.
          Only the 128 bits go to the worker. worker — the field worker of the heartbeat of the addressee, server — the host of the url of its heartbeat; a restart of the instance — there are no records
close:    the ticket is removed — the record is deleted — when the external request is over: the answer is given in full, the client connection is closed or broken, the wait limit ran out;
          for a stream also — jti is revoked, the person is disabled, exp has come, a fresh may by need of the door of the route refused: the console checks open streams at least once per PASS_TICKET_CHECK and closes the client connection;
          the row domain/disabled exists only at the holder, at a member a disabling arrives by the removal of the person's rows from the copy of grants (P/08.4 carry), therefore the stream of a member is closed by may; unavailable does not close the stream (C06-PASS-DISABLED-MEMBER-01)
first_kind: a callback by the entry <s>/<segment of door.pass> of the first kind: the worker of the door <s> checks the credential itself (section «Pass of `door.pass`»), therefore the console puts the token of the ticket record into the passed Authorization: Bearer, as the token of the cookie (C06-PASS-COOKIE-01), Authorization from the addressee of the ticket is replaced;
          X-W2C-Pass-Ticket does not go to the worker of the door. The token goes only to the worker of the door, it is not shown to the addressee of the ticket (ADR-0112 addendum (3) item 1)
ticket:   a callback is a request with the header X-W2C-Pass-Ticket. In order, the first violation — 401 {detail: "ticket refused", error: denied}:
          1. the header is one, of the form ticket_form, this instance has the record: a ticket of another instance does not do;
          2. the transport (below);
          3. the session kind person: break-glass, debug, open give no ticket for a callback;
          4. the door and the method are in the list calls of the manifest of the addressee (P/06.3 N1.9); a stream ticket — also only GET, HEAD and a door route of the subsystem;
          5. the record of the ticket passes the steps of the domain token contract that do not need the bytes of the token: kid in the set (step 3), the key term (step 5a, keep does not serve a ticket), exp with TOKEN_SKEW (step 6), jti not in revoked (step 8);
             the person is not in domain/disabled, the read condition — the right contract, the input `disabled`: a member has no row, the step passes, and the disabling is seen by a fresh may further along the order of the door, `/session` — grants: [] (C06-PASS-DISABLED-MEMBER-01). An unreadable row — the rule «Unreadable row», 503, not 401.
          Further — the usual order of the door: the identity is user of the record, Origin is not judged (there is no cookie), need and may are fresh, iat is that of the ticket record, a refusal is 403; the body, the repeat memory,
          If-Match — as for a person. The answer to the worker is the form of the door, the refusals of the manifest do not apply to it
callback_transport:
  kit:    a callback goes to a separate callback listener (the port CONSOLE_CALL_PORT), section «The callback leaf» of the role certificate contract: no leaf or a foreign authority — a handshake refusal;
          a leaf of another role, a leaf of another server — 401 (step 2): the role is <sub>worker of the addressee, the server is server of the addressee. A request with the ticket header to the main listener — 401: there is no identity there
  no_kit: a callback goes to the role socket of the worker (P/02.5 N1.5): the identity is the socket, the role <sub>worker of the addressee is matched. A request with the ticket header over TCP — 401
writes_via: a row of a unit or of a table with the word writes_via (P/06.1 N1.1a) by ticket: sub of the addressee of the ticket is in the list, the transport of step 2 is
          its role; otherwise 403 writes via. Further need and may of the person of the ticket — as for the other writes (ADR-0119 addendum (10), (11))
service:  a table service: true (P/06.1 N1.6) by ticket: it is read and written by the right of consequences, may is not asked, if <sub> of the table is sub of the addressee of the ticket and the transport of
          step 2 is its role; otherwise 403 denied, as to a person. A row of such a table in a batch — by the same rule. The feed by ticket gives its rows with the field user equal to user of the ticket (P/06.1 N2 «Change feed»). The journal — as for the other writes
journal:  every accepted callback is a line pass.called in audit/<console role>/e1 (the event journal contract): {user, via: <sub>/<worker>, door: "<method> <path without query>", status};
          a write made by ticket carries the same user and via in its journal line
counter:  <sub>_passed_calls_total — a series of /metrics (P/06.5 N3): of the accepted callbacks
refusals: the console on the path of the route answers with its own refusal (a status outside the worker: 401, 403, 404, 413, 502, 503, 504) — the manifest has refusals and the status is in codes —
          application/problem+json {code, message}: code — the value of the map, message — detail of the refusal; the headers of the refusal (Retry-After, nosniff) — as before. The status is not in the map, 400, 405, 408,
          429 or there is no key refusals — ConsoleRefusal. The platform does not know the words of the product: the manifest names them. The worker's answer is not rewritten
timeout:  the wait limit ran out before the headers of the answer — 504 {detail: "<worker> did not answer", error: denied}: for the second kind the manifest declares the limit, and it matters to the client to tell it from a refusal of the worker;
          the other outcomes 502 — as for the first kind. After the headers of a stream the limit and a break close the connection: a refusal body cannot be given any more
stream:   a route stream: the answer goes to the client as it arrives, without a buffer and the limit of 4 MiB; the rest — as above. A pass as a stream takes the stream lane (PASS_STREAMS_MAX), not the common one
PASS_WAIT_MAX: 9000           # s; the ceiling of the key wait: the longest declared route, (1 + 2) × 25 × 120 s (ADR-0094 addendum (12) item 7)
PASS_STREAMS_MAX: 256         # passes as a stream of one instance at once: each holds a feed request, therefore no more than CHANGES_SUBSCRIBERS_MAX (P/06.1 N3 «feed»)
PASS_TICKET_CHECK: 5          # s; the term within which an open stream notices a revocation, a disabling and exp
```

**Domain pass across consoles.** For the domain path, the [forwarding hop policy](forwarding.md#domain-worker-pass-hop-policy) fixes the confirmed manifest descriptor, `X-W2C-Pass-Policy`, finite complete-answer budgets at every hop, 4 MiB buffering, and unbounded stream time/body. This is a narrow exception to ordinary forwarding. The second-kind 504 before worker headers and refusal mapping above remain; after client headers only bytes and closure are possible. It creates no domain callback or credential.

**One worker per server.** A ticket is bound to the leaf of the server, and the leaf is one per role and server: a second worker with a callback on the same server would share it. Therefore the controller's order for such a subsystem does not raise `want` of the server above 1 ([P/04](../../04-controller/spec/04-controller.norms.md) N3 «shortage(), order()…»).

**Races.** Two callbacks of one ticket at once are independent, the edits are judged by `cas` and `If-Match`. The request closes in the middle of a callback — a call that has passed `ticket` runs to its end: one write is atomic, and the next call gets 401, so the worker stops the translation and writes nothing more. A disabling and a revocation are seen by the next call or by the stream check: the window is `PASS_TICKET_CHECK` and the delay of the copy at the cluster: at a member a revocation goes by the copy of `domain/revoked`, a disabling — by the copy of grants, so the ticket of a disabled person is not removed there until the end of the request, but `may` refuses it.

## Vectors

There are no vectors: the gate, `/session`, the rights by the body, the break-glass entry and the pass are checked by the scenarios of the acceptances of chapters 6.3, 6.5, 6.7, of lesson P/10 and of chapter 8.4, the pass of the second kind — by the stand [`acceptance/pass/`](../acceptance/pass/README.md); the check of the break-glass password — by the package [`password-hash`](../vectors/password-hash/README.md) of the password hash contract. (ADR-0083 addendum (32) item 2) The coverage of a grant `scope` against a unit row is the function `covers` of the package [`may`](../vectors/may/README.md) (`covers.tsv`; C06-EVENTS-QUERY-UNKNOWN-138-10).

