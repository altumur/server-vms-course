# console.nomad.hcl — the console job: two stateless instances of `domain.console`, in every cluster, pointed at one cluster or at all of them

**Role.** Lesson 3. The jobspec for `python3 -m domain.console` (`../domain/console.py.md`). The header comment: UI, API façade, the read model, TLS, token verification; runs in EVERY cluster (a single-cluster customer has it with no domain), and the domain holder's instance is the same image pointed at every cluster's stores; stateless; `count = 2`; placed anywhere. Compare М11's `console.nomad.hcl` (`../../../Source/deploy/cluster/console.nomad.hcl.md`), a `system` job with the write routes; this one is the read model plus the proxied PUT.

## Stanza by stanza

### `job "console"`
- `datacenters = ["*"]` — any datacenter of the region.
- `type = "service"` — two long-running allocations.

### `group "console"`
- `count = 2` — two instances for availability; safe because, as the header says, the console is stateless (each rebuilds its read model in one pass). See Notes on idempotency keys.
- `network { port "https" { static = 8443 } }` — a fixed port 8443, matching `console.main`'s `CONSOLE_PORT` default; `static` reserves it with the scheduler, so with `count = 2` the two allocations must land on different nodes.
- `service { name = "console"  port = "https"  provider = "nomad"  check { type = "http"; path = "/healthz"; interval = "10s"; timeout = "2s" } }` — registered in Nomad's own service catalogue (no Consul — the `provider` М11's jobspecs lacked), so `nomadService "console"` can find it (the `consoles()` stub in `console.main` names exactly this); health-checked every 10 s on `GET /healthz`, which returns `{"ok": true, "passes": n}`.

### `task "console"`
- `driver = "podman"`.
- `config { image = "vms/domainvms:latest"; args = ["python3", "-m", "domain.console"] }` — the domainvms image and the `console` entry point.
- `identity { env = true }` — `NOMAD_TOKEN`; the comment: reads `vms/snapshot`, `vms/*/heartbeat` and `domain/*`; forwards writes to the owning cluster. No `console-policy.hcl` ships in М12 to bind to this identity; what it may read (`domain/keys` for the verifier) is left to the operator.
- `template { data = <<-EOT … EOT  destination = "local/console.env"  env = true }`:
  - `CLUSTERS=north=configstore:///run/configstore/domain.sock|cluster:///data/platform/objects?resource=http://127.0.0.1:8090,south=report` — the holder's own cluster by the DOMAIN's socket, the role `domain` of М11's rights file (the thirteenth review, major 11, a sibling of the signer's): this console writes the domain's pending edits, topology, crossings and members into the holder's store, `domain/*` rows the cluster console's role does not write. One entry per cluster the console aggregates (the comment: the cluster-level console lists its own cluster only; the domain's lists all). Each entry is `<name>=<store url>|<object store url>`, or `<name>=report`, parsed by `runtime.federation_from_env`; the first entry is the domain holder unless `DOMAIN_HOLDER` says otherwise (it is not set here, so north). Its own cluster by this node's configstore socket and its `cluster://` objects (both mounted into the container); another cluster's store is not opened from here — a configstore has no remote reader — so it is a member that reports. It named `nomad://` stores before, a backend that is gone, and `open_vars` refused it at start (the twelfth review, major 22; `tests/domain/test_lesson3_readview_api_gateway.py::test_the_domains_jobs_name_stores_that_open`).
  - `LOST_AFTER=45` — `ReadView.lost_after`: the same 45 s as М11's `disconnect.lost_after`.
  - `REFRESH_INTERVAL=5` — the read model's pass period; every row's `as_of` is at most this plus a heartbeat interval old.
- `resources { cpu = 500  memory = 256 }` — the in-memory read model for a few hundred cameras and an HTTP server.

## Notes
- The object-store URLs are plain `http://`, which `open_store` maps to `HttpObjectStore` — an adapter with no `list()`. `Cluster.heartbeats()` lists `vms/`, so every `ReadView.refresh()` raises `NotImplementedError`, `Console._refresher` swallows it, and `/api/cameras` stays empty while `/api/where` (which only `get`s the snapshot) works. The URLs need `s3+http://` (SigV4, with listing) for the read model to fill. See the report.
- The port is named `https` and the header says TLS, but `domain.console` serves plain HTTP (`ThreadingHTTPServer`, no TLS context); `verify-bench.sh` item 6 curls `http://console.north:8443`.
- `AUTH` is not set, so it defaults to `1`: every PUT needs a bearer token, verified against `domain/keys` in the *domain* cluster's Variables (see `console.py.md` on which cluster's Variables that is).
- `ConsoleAPI` keeps Idempotency-Keys in process memory; with `count = 2` a retried PUT that reaches the other instance is a second edit, unlike М11's console, which kept them in `vms/idem/*`.
- Same one-line `config`/`resources`/`check` blocks with `;` as in `agent.nomad.hcl.md`.
