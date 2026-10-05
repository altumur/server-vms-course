# api.py — Lesson 3: the domain's write façade, and what it refuses

**Role in the module.** An edit goes to the directory ("where is unit 7"), then to the OWNING CLUSTER's console — the only writer of its rows — and that cluster's grants decide. The domain owns nothing and never writes a unit row on its own account; a create goes to the cluster the placement service chose, and that cluster's controller places it on a worker. The domain never names a worker or a server.

## Names
- `FORBIDDEN_FIELDS` — placement (cluster, worker, server, placement), what a worker observes or takes (epoch, observed_revision, phase), and the controller's revision: refused at either level.
- `class ClusterConsole(Protocol)` — `update_unit(ref, fields, subject)`, `create_unit(fields, subject)`.
- `class ApiError(status, detail)`.
- `refuse_addresses(fields)` — an address with a credential in it, at any depth, refused in the cluster's words (`secrets.refusal_within`), the field named and never the value.
- `said(reply)` — a member's reply masked as a page masks a row before the domain hands it on or keeps it.

## `class ConsoleAPI(directory, consoles, verifier=None, pending=None, last_known=None)`
- `update_unit(ref, fields, idempotency_key, token=None, sub=None)` — the same key is the same PUT; placement and secret fields refused (a password is set in the unit's own cluster: the domain keeps, backs up and relays its edits); with `sub` (the route's subsystem) whose spec says `domain.edit`, any other field refused 400 naming the fields and the list, before the member is asked or the edit kept (ADR-0031; no `edit` — the member's console decides); found → forwarded; not found because its cluster is silent and the domain last saw it there → KEPT (`pending.PendingEdits`, Lesson 9) and 202; not found in a complete answer → 404; incomplete → 503.
- `create_unit(fields, cluster, idempotency_key, token=None)` — to the cluster the placement chose; the same refusals.
