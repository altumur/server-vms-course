# resource-policy.hcl — the ACL policy bound to job `resource`'s workload identity: its own heartbeat, the mirror knob, every subsystem's retention rows

**Role.** Lesson 2/3. Applied with `nomad acl policy apply -namespace default -job resource resource deploy/resource-policy.hcl` (though `verify-bench.sh` only applies it unbound in item 4 — see Notes). The platform's resource (`w2cplatform.resource.Resource`, run by `python3 -m cluster resource`) writes exactly one Variable — its heartbeat object — and reads three kinds of rows: the mirror setting, each subsystem's retention rows, and (for the VMS hook) the camera rows. The header comment fixes two lines: it never writes any subsystem's configuration, and mirrors go resource to resource over HTTP (`PUT /mirror/...`), not through any store.

## Stanza by stanza

### `namespace "default"` → `variables`
- `path "objects/platform/resources/*" { capabilities = ["write", "read", "list"] }` — `Resource.heartbeat()` puts `platform/resources/<server>/heartbeat` through `VariablesObjectStore`, which becomes the Variable `objects/platform/resources/<server>/heartbeat`; `read`/`list` so `resources_seen(objects)` (peers for mirroring, `restore()`'s source list) works with the same token.
- `path "platform/mirror" { capabilities = ["read"] }` — `mirror_settings(vars_)`: whether mirroring is on and how many copies; written by an operator, never by a resource.
- `path "*/retention" { capabilities = ["read"] }` — each subsystem's default retention (`<sub>/retention {days}`), read by `retention_days()` in the platform's bucket-retention pass.
- `path "*/retention/*" { capabilities = ["read"] }` — the per-unit override (`vms/retention/<id>`, written by the console as a derived row).
- `path "rec/recordings/*" { capabilities = ["read", "list"] }` — which camera a recording records, for the event buckets a keep holds (`vms/resource.kept_buckets`). There is no media retention on the resource any more: footage is in volumes of ObjectStorage, and a recording's `retention_days` is a ceiling its recorder's door applies.

## Notes
- The resource needs `list` on `objects/platform/resources/` for `resources_seen`; the `*` grant covers it.
- `*/retention` and `*/retention/*` use a leading wildcard. Nomad's variables ACL documentation describes `*` globbing in paths; whether a wildcard in a *leading* segment is honoured the same way as a trailing one is worth confirming on the bench, since a refused read here silently falls back to the 365-day default in `retention_days()`.
- `verify-bench.sh` item 5 binds `vmsworker`, `vmscontroller` and `console` to their jobs with `-job`, but never `resource` — item 4 only creates the policy. Until it is bound, the `resource` job's identity token has no rights and its heartbeat `put` is a 403.
- `path "rec/keeps/*" { capabilities = ["read", "list"] }` — the keeps (М10B Lesson 18). `ArchivePolicy` and the bucket retention read them before deleting anything; a pass that cannot read them raises and deletes nothing, so without the grant retention stops on every box and the log says why.
- `path "platform/space" { capabilities = ["read"] }` — the watermark's settings (`space_settings`, М10A Lesson 14), read by every pass. The grant was missing from this file; with the watermark on by default the read is no longer optional.
- `path "*/alarms_retention"` and `"*/alarms_retention/*"` — read: the days the alarms' trees (`<sub>.alarms/…`) are swept by; three years where no row says otherwise.
- `path "platform/schema" { capabilities = ["read"] }` — the store's schema, checked first (`check_schema`; М10's eighth review): the resource job reads it at its start like every other.
