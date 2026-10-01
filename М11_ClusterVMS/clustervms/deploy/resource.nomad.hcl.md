# resource.nomad.hcl — the resource: a PLATFORM system job, one allocation on every server that declares `meta.archive`

**Role.** Lesson 2/3. The jobspec for `python3 -m cluster resource` (see `../cluster/__main__.py.md`, `../cluster/resource.py.md`). A `system` job pinned to servers with disks for as long as the server exists: it serves every subsystem's buckets, takes mirrors from its peers, retains buckets by each subsystem's own policy, and runs the passes subsystems register on it (the VMS registers none: its footage is in volumes, written and read through the host's `obsd`). The header's "No controller" — nothing places a resource; the disk is where it is. Its heartbeat is `platform/resources/<server>`; its token is `resource-policy.hcl`.

## Stanza by stanza

### `job "resource"`
- `datacenters = ["room-a"]` — from `client.hcl`.
- `type = "system"` — one allocation per eligible node.
- `constraint { attribute = "${meta.archive}"  operator = "is_set" }` — at job level (the console job puts the same constraint in the group; both scope every group). Only nodes whose `client.hcl` declares `meta.archive`.

### `group "resource"`
- `network { mode = "host"  port "resource" { static = 8090 } }` — host network, fixed port 8090: the port `RESOURCE_URL` below advertises and `__main__` defaults `RESOURCE_PORT` to.

### `task "resource"`
- `driver = "podman"` — the Podman driver.
- `identity { env = true }` — `NOMAD_TOKEN` scoped by the policy bound to job `resource`.
- `config.image = "localhost/clustervms:latest"` — the local image.
- `config.network_mode = "host"` — shares the host network.
- `config.args = ["python3", "-m", "cluster", "resource"]` — the `resource` verb.
- `config.volumes = ["/data/archive:/data/archive"]` — the tree the workers on this server write their events into: buckets, and mirrors under `.mirror/<server>/`, read-write. The box's own volume lives under it too (`volume/`); no walk here opens it — it is not a bucket.
- `env.OBJECTS = "variables://objects"` — the comment: its heartbeat as a Variable; no MinIO on this cluster.
- `env.RESOURCE_URL = "http://${attr.unique.network.ip-address}:8090"` — the node's IP interpolated by Nomad: the URL in the heartbeat, where peers PUT mirrors and the console fetches `/events`. An IP rather than a name so no DNS is needed between servers.
- `env.NOMAD_NODE_NAME = "${node.unique.name}"` — the server's name for the heartbeat and the mirror directory; Nomad already exports `NOMAD_NODE_NAME` to every task, so this makes it explicit and lets a bench override it in the jobspec.
- `service { name = "resource"  port = "resource" }` — the comment: peers find each other here, and `verify-bench.sh` item 5a uses `nomad service info -json resource` to pick a resource to PUT a mirror probe against. (In the code, peers actually find each other through `resources_seen(objects)` — the heartbeats — not the service catalog.)
- `resources { cpu = 200  memory = 256 }` — 200 MHz, 256 MB: an HTTP file server plus a ten-minute policy pass.

- No `EVENTDB` any more: the job's `EventIndex` reads this tree where it lies at each query, with nothing to rebuild after `restore()` and a bounded cache of what it read.
- `resources { cpu = 200  memory = 384 }` — the tree, the passes, and the event index's cache over this server's buckets (64 MiB by default; the index left the console job and came here).

## Notes
- No `ARCHIVE` env: `__main__` defaults it to `/data/archive`, which the volume binds.
- The `service` block has no `provider = "nomad"`; see `console.nomad.hcl.md`.
- Because this job is `system` and the worker job carries the same `meta.archive` constraint, a worker's `ARCHIVE` is always served by a resource on the same server — "a worker records into the resource on its own server".
