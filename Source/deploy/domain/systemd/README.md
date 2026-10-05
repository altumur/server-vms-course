# The domain's units (М11's servers; no orchestrator)

The cluster's form (`deploy/cluster/systemd`): each unit runs `w2c-run.sh <verb>`, names its role's socket
(`PLATFORM_STORE`), joins that role's group first, and lists no `EnvironmentFile=` — the site's lines are
`/etc/w2c/w2c.env`'s (`domain.env.example`), read under the unit's. A unit that seals or opens a secret loads the ring as
a credential (`SECRETS_KEY=%d/platform.key`); the domain's console loads none (ADR-0032).

| unit | verb | role socket | user | where |
|---|---|---|---|---|
| `w2c-domain.service` | `signer` | `domain` | w2c | the holder: the keys and the holder's pass; /api/login, /api/carry/<member>, the four operations on 8445, the tokens socket |
| `w2c-domain-console.service` | `domainconsole` | `domainconsole` | w2c | the holder: 8444, no key (the cluster's console keeps 8080) |
| `w2c-domainagent.service` | `domainagent` | `domainagent` | w2c | every server |
| `vms-domainpart.service` | `vms domainpart` | `vmsdomain` | vms | the holder: the VMS's books, 8096 |

`w2c-domain.tmpfiles` makes the tokens socket's directory (2750 w2c:vms-vmsdomain). Rights: the configstore's file
(`deploy/cluster/configstore-rights.json`, the domain roles from `w2cplatform/domain/rights.py`): `domain`,
`domainconsole` (no `domain/signer*`, read or write), `domainagent` (with `!` denials), `vmsdomain`. Groups:
`deploy/cluster/systemd/w2c-cluster.sysusers`. The console's groups are its socket's, `w2c-store` and `w2c-events` — not
the ring's, not the tokens socket's — and the key file and the signer's sockets are `InaccessiblePaths=` for it. mTLS
names when the doors get them: `domain.<server>`, `domainconsole.<server>`, `domainagent.<server>`.
