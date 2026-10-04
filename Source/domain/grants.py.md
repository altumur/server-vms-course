# grants.py — Lesson 4: cluster-local grants with an expiry (`ClusterGrants`), their Variable shape, the stated revocation window, and `ClusterAuthoriser` — signature, then its own table, never a network call

**Role in the module.** Lesson 4, "grants are cluster-local, carry an expiry, and expiry IS the revocation mechanism". Each cluster holds `subject X may do Y on camera Z until T` in its own Variables under `domain/grants`, written by the domain agent (the only writer of `domain/*` in that cluster — `deploy/domain/agent-policy.hcl`) and read by the cluster's console and live gateway. Enforcement is a local read — no lookup, no token exchange — which is the only way authorisation survives the domain being down. A cluster whose agent cannot reach the domain lets its grants lapse; that converts an unbounded revocation window into a number the product states. Workers never see a user, a grant or a token: the console and the gateway are the cluster's clients of them, and those two enforce. Two lifetimes, not independent: the revocation window is the SHORTER of the token lifetime and the grant lifetime. Depends on `tokens.verify`/`KeySet`; `agent.DomainPublisher.publish_grants` and `ClusterTrust.grants()` use the two item converters; `gateway.WorkerLiveEndpoint.authorise` is the slot `ClusterAuthoriser.authorise` fills.

## Module-level names
- `GRANT_LIFETIME = 24 * 3600.0` — one day: "Lesson 4 makes students pick and defend it; the product states it". The tests grant `now + GRANT_LIFETIME`.

## `class Grant` (frozen dataclass)
- `subject: str`; `capability: str` (`view` | `edit` | `admin`); `camera: int | None` (`None` = every camera in this cluster); `valid_until: float`; `labels: tuple = ()` — or the cameras that carry ALL of these labels (then `camera` is `None` and means nothing).

## `class ClusterGrants`
"One cluster's grants, as its console and gateway hold them in memory from `domain/grants/*` (М9's `grants` table, with `valid_until`, one level up)."
### `__init__(self, cluster, now=time.time)` — `grants: {(subject, capability, camera, labels): valid_until}`, labels sorted.
### `grant(self, subject, capability, camera, valid_until, labels=())` — add or replace one entry.
### `revoke(self, subject)` — drop every entry for a subject (the local, immediate revoke — only useful when the cluster can be reached).
### `may(self, subject, capability, camera, now=None, labels=()) -> bool`
True if any entry matches the subject, has the capability or `admin`, is still valid at `now`, and covers the camera: a grant without labels names the camera or `None`; a labelled grant covers a camera whose `labels` include all of its own — and never "every camera" (asked about `camera=None` with no labels, it does not match).
### `renew_from_domain(self, renewals)`
"The agent carried the domain's current grants for this cluster: replace, so a grant the domain dropped is not renewed." Wholesale replacement, never a merge — the test's last lines: renewing with only `view` leaves `edit` on camera 7 gone.
### `access_ends(self, subject, token_exp) -> float`
State in advance: if a revoke cannot reach this cluster, when does the subject lose access? `min(token_exp, max(valid_until over the subject's grants))`, or `token_exp` if it has no grants. The test states the number, then advances the clock and measures it in both directions (token outlives grant, grant outlives token).

## Functions
### `grants_to_items(grants, was=None, where="domain/grants") -> dict`
The Variable `domain/grants/<cluster>`: one item per grant, key `subject|capability|camera` (empty camera for `None`; `labels:a,b` for a labelled grant, `_item`), value the expiry as a string. A subject or a label the reader could not take back apart (`name_refused`) is refused with `BadName` before anything is written — unless the grant's item is already in `was`, the row this write replaces (the review's ninth pass, minor): a grant to `say"hi` stored before `"` was refused is then left out of the new row, counted once in `GRANTS` (`<where>#<item>`) and logged with why and what to do ("create the user under an allowed name and grant again"), and the rest is written. A NEW grant under such a name still raises: the rule is for what is made. `publish_grants` passes the cluster's row (`was=have, where=path`), `set_domain_grants` the domain's.

```python
    for g in grants:
        ...
        if why is None:
            out[_item(g)] = str(g.valid_until)
        elif isinstance(was, dict) and _item(g) in was:
            GRANTS.garbled(f"{where}#{_item(g)}", BadName(f"{why} — stored before the rule; left out of the row as it "
                                                          f"is written again: create the user under an allowed name "
                                                          f"and grant again"))
        else:
            raise BadName(why)
```

Test: `test_foreign_data.py::test_an_old_name_with_a_quote_blocks_no_write_of_grants_and_a_new_one_is_still_refused` — deleting `mallory` goes through with `say"hi` in the row, the mending command writes, `new"one` raises `BadName`, an admin only under an old name is `LastAdmin`, and `publish_grants` drops the old grant from `domain/grants/south`.
### `grants_from_items(items, where) -> list[Grant]` — the inverse; tolerates `None`. Item by item (the review's eighth pass): an item that does not split into three, whose camera is not a number or whose expiry is not finite is not a grant — counted once in the table `grant` (`<where>#<item>`), logged once; the others are read. A row that is not an object is no grants, counted.
### `revocation_window(token_lifetime, grant_lifetime) -> float`
`min` of the two. The docstring: "Most people answer the token." With the module's numbers, 900 s.

## `class ClusterAuthoriser`
"What a cluster's console and live gateway run: signature against the key set the cluster holds (in its Variables, via the domain agent), the revocation list it holds, then its grants. Never a network call, never a worker."
### `__init__(self, grants, keyset, revoked=frozenset(), now=time.time)`.
### `update_trust(self, keyset, revoked)` — swap in what the agent last synced.
### `subject(self, token) -> str` — `verify(...)["sub"]` at `self.now()`.
### `authorise(self, token, capability, camera) -> str`
A `TokenError` becomes `PermissionError("token refused: …")`; no matching grant → `PermissionError("alice has no edit grant on camera 12 in south")`; otherwise the subject. `test_grants_are_cluster_local…`: `view` on any camera and `edit` on 7 pass, `edit` on 12 fails; after `TOKEN_LIFETIME + 61` the token is refused as expired; after a further `GRANT_LIFETIME` a fresh token is refused for lack of a live grant.

## Notes
- The item key splits on `|`, so `|` is not allowed in a subject (nor `"` and control characters; in a label not `,` either): `grants_to_items` refuses a new one (`BadName`, `name_refused`), and so does `IdentityStore.create_local`/`create_federated` (`refuse_name`). A stored one with `|` is an item that is not a grant (`grants_from_items`, above); a stored one that still reads — `"`, say — is left out, counted, when its row is written again (`grants_to_items`, above).
- `gateway.py` defines its own `Forbidden` for the same refusal; the two are not related classes.
- In production the grants a cluster reads live at `domain/grants` (the agent copies `domain/grants/<cluster>` from the domain holder to that exact path in its own cluster — see `agent.py.md`).
- **The domain's own grants** (feedback CA): `DOMAIN_GRANTS = "domain/grants/domain"` in the holder's store — who may look at the domain's door (`view`) and change what it decided (`admin`). Not the carried grants of the cluster that holds the domain: a move (Lesson 15) would change the domain's administrators to whoever administers the new holder. Exported in the backup (`term.EXPORTED` has `domain/grants/`), carried by no agent (`Members` refuses a cluster named `domain`). `domain_may(vars, subject, capability, now)`: whole-domain grants only (no camera, no labels), `valid_until` 0 never lapses, rank as `w2cplatform.access.RANK`. `set_domain_grants` refuses (`LastAdmin`) a write that leaves no live `admin` in the row it writes — an admin left out under an old name is no admin. The first admin: `CONFIG_URL=… python3 -m domain.grants domain <subject> [view|edit|admin]` on the holder. Tests: `test_domain_door.py`.
