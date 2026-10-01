# resource.py — the resource job is М10's resource process: `cluster_resource = vms.resource.vms_resource`, re-exported

**Role in the module.** Lesson 3. On a cluster the resource is the platform's `w2cplatform.resource.Resource` (see `../../../vmsserver/w2cplatform/resource.py.md`) with the VMS registered on it — exactly what М10 builds as `python3 -m vms resource` (`vms/resource.py`): an `EventIndex` attached, and the VMS's keeps for bucket retention (`kept_buckets`). Footage is not on its tree: it is in volumes of ObjectStorage, written through the host's `obsd` by the recorder that holds each one and read through that recorder's archive door — the resource has nothing of it to repair, retain, serve or evacuate. This module has no code of its own: it re-exports `vms_resource` under the name М11's lessons use, `cluster_resource`, together with the platform's resource vocabulary, so `__main__` and the tests import everything from `cluster.resource`. A `system` job on every server with `meta.archive` (`deploy/resource.nomad.hcl`), serving buckets, taking mirrors from peers, retaining every subsystem's buckets by that subsystem's row, keeping the event index over its own tree, heartbeating under `platform/resources/<server>`.

## Module-level names
- `cluster_resource` — `vms.resource.vms_resource(root, server, url, vars_, objects, wall=None, peers=None, bucket_seconds=600) -> Resource`.
- `PeerClient`, `Resource`, `mirror_settings`, `mirrored_buckets`, `peers_of`, `resources_seen`, `serve` — the platform's resource API, re-exported.

## Notes
- `__main__.resource` builds `cluster_resource(archive, server, url, NomadVariables(), objects)`, serves it with the platform's routes only, heartbeats and restores; its event index (`res.index`) needs no start.
- The tests (`test_lesson3_events.py`, `test_lesson3_resources.py`, `test_lesson5_controller.py`) build the same object over directories and query `res.index` directly — there is no rebuild or tail to call.
