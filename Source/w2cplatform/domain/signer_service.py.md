# signer_service.py — the domain's signer as a process: the one process with the domain's keys, its four operations, and the holder's whole pass; `python3 -m w2cplatform.domain.signer_service`

**Role in the module.** Wiring for `deploy/domain/systemd/w2c-domain.service` (`w2c-run.sh signer`). Holds the keys (`signer.Signer` over the holder's store, by the `domain` role's socket; the private halves sealed under the ring), publishes the key set and the revocation list where agents read them (`agent.DomainPublisher`), publishes the identity set object-first on a floor (`identity.IdentityStore.publish`), and answers logins with tokens. ADR-0032: it is the ONLY process with the keys, it performs whole every operation that needs them — checking each itself, the freeze of a handover included — and it runs the holder's whole pass, so that every output of the pass has one writer. The domain's console (`console.py`) has no key, reads, and hands a person's request here as it came. The CA half (issue, renew, rotate) is driven by the registrar and by renewal requests over mTLS, which need the bench.

## `class Holder`
The pass and the operations, over the holder's stores (`vars_`, `objects`) and the `Signer`. Optional parts: `ids`, `revoked`, `pub`, `carry_door` (the door); `fed`, `view`, `members`, `topology`, `pending`, `alarms` (the pass, given `CLUSTERS`); `term` (`term.DomainHolder`, Lesson 15 — None for a domain that never moves) and `move(to)` (how a handover is made); `journal`; `console_url` (the view's `url`).

- `steps()` / `run_pass()` — the identity set and the revocation list (`signer_steps`); then, given the domain: whether it still holds the domain (`DomainHolder.check`), following the members and the topology, the read view's pass, the kept edits closed by what the members report (`PendingEdits.collect`), the week of alarms kept (`DomainAlarms.keep`), the backup sealed (`backup`), the view published (`publish_view`: `ReadView.publish` with `tables()` and `extra()` — the topology, the list of members and who knocks, the kept edits and outcomes, the term, `pass_failures`, `garbled_rows`, `url`). Each a step of `steps.Steps`.
- `holder_says()` — `GET /api/holder`: `{record, term, deposed[, deposed_by, stranded: [{path, key, value}]][, frozen_for][, console]}`; None without a term. `term_view()` adds `backup_holders` and `can_hand_to` (`hand_targets`: the members whose stores this process writes).
- `refusal()` — the freeze, checked here: 503 while `frozen_for`, 409 once replaced (`DomainHolder.guard`).
- The four operations, each `(status, body)`, the person checked here (`_person`: a token of the domain, `admin` to change, `view` to read the people) and then the freeze:
  - `shared(token, body)` — `PUT /api/shared {base_rev, shared}`: `edit_shared`;
  - `handover(token, body)` — `POST /api/handover {to}`: `move(to)` (`term.handover`), one at a time; called off → 409 and unfrozen;
  - `people(method, rest, token, body)` — `/api/people/users` (GET; POST `{name, password ≥ 10, roles?}`), `/api/people/users/<name>` (PUT `{password?, roles?}` — `disabled` is refused: no such state in the course; DELETE takes their grants, the last admin stays), `/api/people/break-glass` (GET `{clusters: {<c>: {set_at}}}`), `/api/people/break-glass/<cluster>` (PUT `{password}`, `breakglass.set_password`);
  - `backup()` — the pass's: at most every `backup_every` (30 s), to `backup_holders` (2) live members chosen stably; nothing while frozen or replaced.
- `handler()` — the door: `GET /healthz`, `/keys`, `/api/holder`, `/api/carry/<c>`, `/api/people/…`; `POST /api/login`, `/revoke`, `/api/handover`, `/api/people/…`; `PUT /api/shared`, `/api/people/…`; `DELETE /api/people/…`. No route signs what it is given.

## `main()`
Environment: `DOMAIN_ID`, `PLATFORM_STORE` (default the `domain` role's socket), `SECRETS_KEY`, `OBJECTS`, `SIGNER_UNIX`, `SIGNER_TOKENS_UNIX`, `RECOVERY_FILE` (the first start only), `IDENTITY_PUBLISH_FLOOR`, `SIGNER_HOST`/`SIGNER_PORT`, `REFRESH_INTERVAL`; given `CLUSTERS` the pass (`holder_pass`: `CLUSTERS`, `DOMAIN_HOLDER`, `LOST_AFTER`), `CONSOLE_URL` (the domain console's address, the view's `url`), `SIGNER_URL` (its own, in the holder record it claims), `HANDOVER_WAIT` (how long a handover waits for the target's report). Its journal is role `domain` (`runtime.events_said`).
- `holder_pass(holder, domain, signer)` — the pass's parts over the federation; the term from the holder record in the store (`term_of`, started as `DomainHolder.start`); `move_by_handover` with the signer's own backup — none for an issuing signer, whose root is off the holder.

## `edit_shared(vars_, objects, issuer, keyset, revoked, token, body, now)`
The shared settings edited whole where the key is: the person (401/403), the shape (400), `base_rev` and the specs' `domain.shared` (409, nothing signed), then built, signed and pointed to — `200 {rev, by}`.

## `signer_steps(ids, revoked)`, `revocations(vars_)`
The identity set and the pruning, step by step; the revocation list read entry by entry, an unreadable row said and started empty.

## Lesson 15, step 9
`RECOVERY_FILE`, on the first start only (no `domain/signer` yet): an issuing signer under that root and key set rev 1 signed by it; the installer takes the file back. Afterwards the service never publishes a key set of its own over the root's; `GET /keys` answers what `domain/keys` holds.
