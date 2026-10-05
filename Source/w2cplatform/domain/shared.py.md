# shared.py — Lesson 12: settings of the system as one signed object behind a pointer, carried by every member's agent, resolved as defaults when read

**Role in the module.** Defaults, the tree a console offers, what one member's event asks of another belong to no unit, and with small boxes as members there is no cluster to keep them in; the domain has no database. The identity set's publish-then-point (Lesson 4) plus the offline key set (Lessons 4, 7): the document is an object (it outgrows a 64 KiB Variable), the pointer is the CAS, the signature makes any copy as good as the original, `(term, rev)` keeps a member from going backwards, and the member keeps the verified copy in its own durable store. Also used by Lesson 15 (`term.py`) to carry the domain's backup, through `carry`'s path arguments.

## Module-level names
- `POINTER = OBJECT = "domain/shared"` (the pointer in Variables, the document in a member's objects), `REFUSED = "domain/shared-refused"`.

## Functions
### `sign(doc, issuer) -> dict`, `verify(doc, keys, now) -> dict`
Ed25519 over canonical JSON without `kid`/`sig`, by the signer's token key. `verify` raises `NotTaken` for no key set, an untrusted or retired `kid`, or a bad signature.
### `carry(domain_vars, domain_objects, member_vars, member_objects, keys, now, src=POINTER, dst=POINTER, obj=OBJECT, refused=REFUSED) -> str`
The agent's side. Nothing published → nothing. Member already at or past `(term, rev)` → nothing ("up to date" / "holding newer"). Otherwise fetch, check checksum, signature (against the MEMBER's keys) and that the object's `(term, rev)` matches the pointer; failure writes `refused` with the reason and keeps the old copy; success writes the object, then the member's pointer.

### `refusals(settings) -> [reasons]`
Why the document would be wrong by the specs: a key beside `shared`, a subsystem not on the domain, a field outside its `domain.shared`, a value its schema refuses — a document's (`{name, type: json, schema}`, `spec.domain.documents`) or a unit field's that has one. One rule over whatever the specs declare; no field is known by what it means.
### `resolve(spec, settings, label, row=None) -> {field: (value, from)}`
The chain for a unit: its own value; for a field the spec shares and that inherits, the domain's `settings.shared.<sub>.<field>` (`merge: union` — the unit's and the domain's); else the spec's `inherit`. The shared field the page groups by never becomes a unit's value.
### `door(spec, doc, row=None) -> {sub, rev, fields}`
`GET /domain/shared/<sub>` on the cluster console (`SpecConsole.shared_route`): the declared fields only — an inheriting one as `{value, from, inherit, merge?}`, the grouping one as `{groups, from}`, a document as `{value, from}`.

## `class SharedSettings`
The domain's side. `current()` → the document and the pointer's index. `edit(mutate, base_rev, by=None)` → a `Conflict` (409) if the editor's `base_rev` is stale; a 400 (`ApiError`) for anything `refusals` names — wrong by the specs on its own; else signs rev+1 with the current `term()`, puts `shared/rev-<n>`, then the pointer by CAS. No subsystem's check is asked: what a value means is the subsystem's pass's to say (ADR-0032). A person's edit reaches it through the signer's `edit_shared` alone. `delivery(fed)` → per member `holding` / `behind` / `refused` / `silent`, from each member's copy of the pointer, and a sentence naming the silent and the refusing.

## `class SharedView`
A member's console side. `document()` re-verifies the stored copy against the member's own keys; `settings()`; `effective(row, spec)` → `resolve` over the verified copy: `{field: (value, "unit" | "domain rev N" | "unit + domain rev N" | "spec")}` — resolved at read time, never written into rows.

## Notes
- The document: `{shared: {<sub>: {<field or document>: value}}}` and nothing beside — a subsystem's fields and documents only as its spec's `domain.shared` declares them (`tests/test_domain_platform.py`: inherit, union, only declared fields, a document by its schema).
- `test_a_document_not_signed_by_the_domain_is_refused_and_the_old_one_kept` forges a document with a matching checksum; `test_a_default_is_resolved_when_read_and_never_written_into_a_row` checks no row revision moves.
