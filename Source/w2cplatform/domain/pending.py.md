# pending.py — Lesson 9: an edit for a cluster that is off, kept per field and applied by the member's own console

**Role in the module.** Lesson 3 answered `503` when the owning cluster did not answer. Right for a server room in your own building; useless for a member that is one box, off for its power and edited in bulk with forty-nine others. So the domain keeps the edit — in the holder's store under `domain/pending/<cluster>`, beside the grants — and the member's agent carries it home; the member's own console applies it, as the operator who made it, grant checked then.

## `class PendingEdits(domain_vars, wall)`
One row per cluster, one item per unit by the DOMAIN's name (`ref`), each `{fields: {f: {old, new, via?, conflict?}}, rev, subject, since, refused?}`.
- `add(cluster, ref, fields, base, subject)` — merged per field by CAS: a new field `{old: base[f], new}`; a field reported as a conflict is measured against what the unit now holds; a field already waiting keeps its `old`, takes the latest `new`, remembers the values in between (`via`). `rev` counts edits; only an outcome for the current `rev` clears anything.
- `reconcile(cluster, outcomes)` — applied and already-there fields go, a conflict stays annotated, a refusal stays with its reason, a unit gone takes its edit with it; one outcome that does not fit is that unit's.
- `collect(fed)` — every cluster with something waiting, its `domain/outcomes` read through its stores.

## `apply_pending(entries, current, console, now)` — the member's side, run by its agent: per field, holds `new` → already; holds `old` or a `via` → applied (`console.update_unit`); anything else → conflict. The console's refusal is the grant check, recorded, not retried. No password is kept or reported: every address is said as a page says it (`secrets.hide_in_reply`).
