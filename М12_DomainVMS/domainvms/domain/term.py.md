# term.py — Lesson 15: the domain held by a camera — a term, a signed backup beyond the holder, moving as an ordinary operation

**Role in the module.** On a site with no server the designated domain holder is a camera, and cameras die. Moving the domain becomes ordinary, and three things follow: a TERM (the epoch one level up — a larger term wins, a returning holder steps down on its next read), STATE BEYOND THE HOST (what only the holder holds — Lesson 9's kept edits for a member that is off above all — published as a signed backup that chosen members' agents carry, like the shared settings), and NOTHING LOST SILENTLY (an old holder's un-backed-up changes listed for a person). The signer's key is never in the backup; it comes from where Lesson 7 put it.

## Module-level names
- `HOST = "domain/host"` (a signed `{term, host, at}` in the holder and in every member), `BACKUP = "domain/backup"` (per-member pointer `domain/backup/<member>` in the holder; the member's copy and document), `EXPORTED` — the prefixes the backup carries: pending, grants, crossings, sources, the settings pointer, topology, members, roads, placement, the licence; `EXPORTED_OBJECTS` — from the holder's object store, the week of alarm history (Lesson 14), which lives on the holder's card and would otherwise die with it.

## `class Deposed`, `class Frozen`, `class TwoHolders`

## Functions
### `read_holder(vars_, keys, now)` — the verified holder record, or `None`. A key set with a root takes a record only from the root (step 9): a record the token key signed is what a stolen holder would write.
### `install(fed, name, domain_id, root, wall, objects) -> DomainHolder` — step 9's cold start: an issuing signer under `root`, key set rev 1 signed by the root, the root-signed record of term 1, claimed. The root is then the operator's recovery file.
### `carry_holder(domain_vars, member_vars, keys, now) -> str` — the agent's side: carry the record only if it verifies and its term is LARGER than the member's; never backwards.
### `find_holder(fed, member_vars, keys, now) -> str | None` — the largest verified term among the member's own record and reachable members' claims about THEMSELVES; two holders with one term raise `TwoHolders`. A holder that is off stays the holder if nobody holds a larger term.
### `move_domain(fed, new, signer_backup, domain_id, objects_of, wall) -> (DomainHolder, report)` — restore the signer on `new`; among reachable members, the largest term carried and the newest backup that verifies; restore its state; publish keys; flag `new` as the domain holder; term = largest seen + 1; claim. The report names the term, the backup and its keeper, what was ignored, and says what is not there.
### `stranded(old_vars, restored_state) -> list` — every exported item on a returning old holder that differs from what the new term was restored from.

## `class DomainHolder`
`claim()`; `export()`; `export_objects()` (the `EXPORTED_OBJECTS` keys, as text — `move_domain` puts them back on the new holder); `backup(targets, objects) -> rev` (a deposed holder may not publish; a frozen one may — that is how it hands over); `check()` — False, and `deposed_by` set, if any reachable member carries a larger term; `guard()` raises `Deposed` naming the new holder and term, or `Frozen` while `frozen_for` names the member a handover is moving the domain to.

## `class GuardedPending`
`PendingEdits` with the holder's guard in front of `add`: a kept edit is refused as `ApiError(503, reason)` while the holder is frozen or deposed. Everything else passes through.

## `handover(holder, to, signer_backup, domain_id, objects_of, carry_to, wall) -> (DomainHolder, report)`
The planned move from a live holder: freeze; last backup to `to`; `carry_to()` runs `to`'s agent; if `to`'s pointer does not name that rev at this term (or `to` is unreachable) the handover is called off — `RuntimeError`, holder unfrozen, nothing claimed. Otherwise `move_domain`, the old holder's `check()`, and `stranded` against the restored state; the report adds `planned` and `stranded` and says *nothing stranded* only when that list is empty.

## Notes
- `test_every_move_takes_a_larger_term_than_any_member_has_seen`: the second move in a month takes term 3.
- `test_a_holder_restored_without_the_signers_key_is_followed_by_nobody`: no backup verifies and no member switches.
- `test_a_planned_handover_strands_nothing`, `test_a_handover_the_target_did_not_take_is_called_off_and_changes_nothing`, `test_a_write_that_slips_past_the_freeze_is_reported_not_trusted_away`.

## Step 9 — the root off the holder
- `DomainHolder(..., record=None)`: the record the root signed for this term; `claim()` writes it instead of signing one. `check()` reads with the published key set (`ClusterTrust(self.vars)`, the root in it). Deposed, an issuing signer forgets its keys (`_forget_keys`: `domain/signer` ← `{forgotten: "deposed by term N"}`).
- `carry_holder` refuses a record not signed by the root when the member trusts one.
- `move_domain(..., stolen=False)`: from a recovery file, the new holder gets keys of its OWN (`Signer.issued`); `_trusted_keys` — the newest root-signed key set any reachable member holds, verified against the root in the file; `_next_key_set` — the new token key current, the old ones kept `OLD_KEYS_OVERLAP` (an hour) after a planned move, dropped after a theft with every issuing certificate so far revoked; `_sign_shared_again` — the shared document signed again at the new term (members check it on every read); the root signs the record of the new term; after a theft `reissue_ldevids` signs again each member's admitted key (`domain/members`, `key`) into `domain/ldevid/<member>`. The report adds `keys_rev`, `stolen`, `reissued`. From the signer's backup of Lessons 4–7, `stolen=True` is refused: it holds the stolen keys themselves.
- Tests: `tests/test_lesson15_root.py` — the recovery file is the root and the holder holds none of it; a stolen holder can neither take the domain nor hand out keys of its own; after a theft the move drops the old keys and signs every LDevID again; a planned move gives the new holder keys of its own and the old ones live an hour; a key set only goes forward; the signer's backup cannot answer a theft.
