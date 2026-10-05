# grants.py — Lesson 4: grants are cluster-local, carry an expiry, and expiry IS the revocation mechanism

**Role in the module.** Each cluster holds `subject X may do Y on unit Z until T` in its own store under `domain/grants`, written by the domain's agent and read by the cluster's console and doors for people. Enforcement is a local read — no lookup, no token exchange — the only way authorization survives the domain being down. A cluster whose agent cannot reach the domain lets its grants lapse: an unbounded revocation window becomes a number the product states (`revocation_window` — the shorter of the token's and the grant's lifetime). Workers never see a user, a grant or a token.

## `class Grant(subject, capability, unit, valid_until, labels=())`
`capability`: `view` | `edit` | `admin`. `unit`: one unit as the platform names it, `<sub>/<id>`, or None — every unit in the cluster; a grant on a unit takes in the units ABOUT it (`about:` in their spec). `labels`: the units carrying ALL of them (`unit` is then None).

## `class ClusterGrants(cluster, now)` — `grant`, `revoke`, `may(subject, capability, unit, now, labels)` (`admin` implies the rest; a labelled grant never covers "every unit"), `renew_from_domain(renewals)` (replace: a grant the domain dropped is not renewed), `access_ends(subject, token_exp)`.

## The row
`domain/grants/<cluster>`: one item per grant, `subject|capability|<unit:<sub>/<id> | labels:a,b | nothing>` → its expiry. `grants_to_items(grants, was, where)` refuses a name the reader could not take apart (`BadName`: `|`, `"`, control characters; a label also `,`), unless the grant is already in `was` — then it is left out, counted (`GRANTS`). `grants_from_items(items, where)` reads item by item: one that does not parse is not a grant, the others are read.

## The domain's own grants (feedback CA)
`DOMAIN_GRANTS = "domain/grants/domain"` in the holder's store — who may look at the domain's door and change what it decided; exported in the backup, carried by no agent (no cluster is called `domain`). `domain_may(vars, subject, capability, now)`; `set_domain_grants(...)` refuses a write that leaves no admin (`LastAdmin`) and says the change in the journal. The first admin: `python3 -m w2cplatform.domain.grants domain <subject> [view|edit|admin]` on the holder.

## `class ClusterAuthoriser(grants, keyset, revoked, now)` — signature against the key set the cluster holds, its revocation list, then its grants; a person's token only (`kind=person`), never a member's.
