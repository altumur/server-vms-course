# signer.nomad.hcl — the domain signer job: one job, two keys, in the DOMAIN HOLDER only, kept off the servers that carry workers by a constraint

**Role.** Lessons 4 and 7. The jobspec for `python3 -m domain.signer_service` (`../domain/signer_service.py.md`, `../domain/signer.py.md`); its token is `signer-policy.hcl`. The header comment: one job, two keys (the CA and the token issuer); `count = 1` is not exactly-one during a reschedule, and that is harmless here — same key, same signatures; the key lives in the Variable `domain/signer`, a software key on purpose, because a TPM would pin the job to one server and defeat the failover it just gained.

## Stanza by stanza

### `job "domain-signer"`
- `region = "north"` — the domain holder; the comment: a stated decision, recorded where the directory can report it (`Cluster.is_domain_holder`, and `verify-bench.sh` item 4 checks `domain/signer` exists in north's raft and not in south's). The only jobspec in М12 with a `region` line.
- `datacenters = ["*"]`, `type = "service"`.

### `group "signer"`
- `count = 1` — one signer; a reschedule may briefly run two, which is fine because both load the same `domain/signer`.
- `constraint { attribute = "${meta.role}"  operator = "!="  value = "worker" }` — the comment: what the operator may say is a CONSTRAINT, never a server — not on a server carrying fifty cameras. `meta.role` is set in each client's `client.hcl`.
- `network { port "https" {} }` — a dynamic port; the service registration below is how it is found.
- `service { name = "domain-signer"  port = "https"  provider = "nomad" }` — registered in Nomad's catalogue so consoles and the registrar can find `/login`, `/revoke`, `/keys`. No health check.

### `task "signer"`
- `driver = "podman"`.
- `config { image = "vms/domainvms:latest"; args = ["python3", "-m", "domain.signer_service"] }`.
- No `identity` block: the store is no Nomad Variable any more. The comment in its place names the store — the domain holder's configstore by the domain's own socket, the role `domain` of М11's rights file (`domain/*` and `identity/*` written, the holder's cluster read, and the domain's keys `domain/signer`, which no other role reads).
- `template { … destination = "local/signer.env"  env = true }`:
  - `DOMAIN_ID=acme` — the domain name: token `iss`, root CN `acme root g<n>`, the registrar id prefix, the licence's `domain`.
  - (no store line: the signer opens its default, `configstore:///run/configstore/domain.sock`. No rights file named a role `domain`, so no daemon opened that socket: the first read was `StoreUnavailable` and the job went round its restarts — the thirteenth review, major 11. М11's `cluster/rights.py` has the role now, socket group `w2c-domain`; `tests/test_lesson3_readview_api_gateway.py::test_the_signer_opens_its_store_through_its_roles_socket_under_the_clusters_rights` starts a real daemon with the committed rights file and runs the signer's first reads and writes through that socket.)
  - `OBJECT_STORE_URL=http://minio.north:9000/domain` — the `domain` bucket for `identity/rev-N` and `users/<id>/prefs`; plain HTTP is enough here because the identity store only `put`s and `get`s (no listing).
  - `TOKEN_LIFETIME=900` — 15 minutes, the number Lesson 4 defends; not read by the code (`identity.TOKEN_LIFETIME` is the constant).
  - `IDENTITY_PUBLISH_FLOOR=60` — the minimum seconds between identity publishes: the stated RPO for users.
  - `CLUSTERS=…`, `LOST_AFTER=45` — given `CLUSTERS` (the console's format), the service also runs the domain's pass over the books every 5 s (`domain/books.py`: sources, primaries, polls, upstream, asks). The books carry tokens this job mints, so the pass runs here and not in the console. `CENTRE` and `STAR` (Lesson 17) are optional. The holder's own cluster is named by `domain.sock`, not `console.sock`: the books are `domain/*` rows, which the console's role does not write.
  - `SIGNER_PORT={{ env "NOMAD_PORT_https" }}` — the port Nomad gave the group; without it the process listened on 8445 whatever the service registration said (the thirteenth review, major 11).
- `resources { cpu = 200  memory = 128 }` — signing is cheap; scrypt on login is the only real work.

## Notes
- The port is dynamic and the code binds `SIGNER_PORT` (default 8445), set from `NOMAD_PORT_https` in the template.
- The domain's console (`console.nomad.hcl`) opens the same role: both are the domain's processes on the holder, so both read the keys — the narrowing between them is the round that splits М12.
- The port is named `https` but the service speaks plain HTTP; a bench would put TLS in front (the LDevID/renewal flow the docstring defers needs mTLS).
- Same one-line `config`/`resources` style as the other jobspecs.
