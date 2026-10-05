# federation.py — Lesson 1: N clusters as a `Federation` of `Cluster` handles, and a `DomainDirectory` whose every `Answer` says what it could not reach

**Role in the module.** A domain is N clusters, each with its own store and object store; nothing replicates between them. So the domain's directory is an *aggregation* — partial, stale by a bounded amount, sometimes incomplete — and the honest answer when a cluster is unreachable is "not found in the clusters I could reach". What a cluster publishes for the domain is, for every subsystem, one snapshot object per worker (`<sub>/snapshot/<w>`, `SpecController.publish_snapshot`) and the workers' heartbeats (`<sub>/heartbeats/<w>`). Which subsystems' units are in the directory, and by which field each is named across clusters, the specs say (`domain.ref`; `declared.directory()`). The domain never reads a cluster's rows.

## Names
- `REACHES = "domain/reaches"` — what a cluster says it can see, in its own object store, written by its agent.
- `class Unreachable` — the cluster did not answer; every reader marks the cluster down rather than fail.
- `MEMBER_OBJECTS`, `published(cluster, key, raw, check, default)` — the members' one reader of what they published: an object that does not parse is skipped, counted once, logged once.
- `ref_of(row)` — what the domain calls a unit: its spec's `domain.ref` field of a snapshot row or a status entry (each carries its `sub`).

## `class Cluster(name, vars, objects, reaches, is_domain_holder, via)`
- `networks()` — what it reports it can see, with any stated here.
- `snapshot(sub=None)` — `{cluster, ts, units: [{sub, id, <snapshot fields>, worker, server}]}` merged from every shard of one subsystem, or of every subsystem of the directory; the age of the whole is the OLDEST shard's; a unit in two shards for the length of a move is the newer shard's.
- `heartbeats(sub=None)` — worker → its last heartbeat, with its `sub` (keyed `<sub>/<worker>` when the read covers more than one subsystem).

## `class Answer(unit, worker, server, cluster, searched, unreachable, contested, sub)` — `complete`, `found`, `sentence()`: the four honest sentences.

## `class Federation` — `clusters`, `add`, `domain_holder` (exactly one).

## `class DomainDirectory(fed, wall)` — `scan()`, `where(ref)` (two clusters claiming one ref is contested, not a tie), `holdings()`, `ages()` (the domain's RPO, shown).
