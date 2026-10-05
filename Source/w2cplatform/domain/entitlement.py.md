# entitlement.py — Lesson 5: the licence cached in the domain holder's store, verified against the product's vendor key, graceful for a stated period; work never stops

**Role in the module.** Entitlement from the domain's side. The vendor issues it (М14 Lesson 3); the domain CACHES it and degrades on a grace period, like placement and identity. What degrades is adding units; nothing that already works stops because a licence server is unreachable — not for a month, not ever.

## Names
- `GRACE = 30 days` — the number the datasheet states.
- `class Licence(domain, units, features, valid_until, issued)` — `verify(blob, vendor_public)`: `<json>.<hex signature>`, Ed25519 under the vendor's key; anything else is `LicenceError`.
- `class EntitlementCache(domain, vars, vendor_public, now)` — `install(blob)` (verified, this domain's, kept at `domain/licence`, exported in the backup); `current()`; `status()` → `none | valid | grace | degraded`; `may_add_unit(current_count)` → `(bool, why)`; `work_allowed()` → `True`, by construction.
