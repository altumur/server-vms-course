# The domain's units (М11's servers; no orchestrator)

The cluster's form (`deploy/cluster/systemd`): each unit runs `w2c-run.sh <verb>`, names its role's socket
(`PLATFORM_STORE`), joins that role's group first, loads the ring as a credential (`SECRETS_KEY=%d/platform.key`), and
lists no `EnvironmentFile=` — the site's lines are `/etc/w2c/w2c.env`'s (`domain.env.example`), read under the unit's.

| unit | verb | role socket | user | where |
|---|---|---|---|---|
| `w2c-domain.service` | `signer` | `domain` | w2c | the holder: /login, /api/carry/<member> on 8445, the tokens socket |
| `w2c-domain-console.service` | `domainconsole` | `domain` | w2c | the holder: 8444 (the cluster's console keeps 8080) |
| `w2c-domainagent.service` | `domainagent` | `domainagent` | w2c | every server |
| `vms-domainpart.service` | `vms domainpart` | `vmsdomain` | vms | the holder: the VMS's books, 8096 |

`w2c-domain.tmpfiles` makes the tokens socket's directory (2750 w2c:vms-vmsdomain). Rights: the configstore's file
(`deploy/cluster/configstore-rights.json`, the domain roles from `w2cplatform/domain/rights.py`): `domain`,
`domainagent` (with `!` denials), `vmsdomain`. Groups: `deploy/cluster/systemd/w2c-cluster.sysusers`. mTLS names when
the doors get them: `domain.<server>`, `domainagent.<server>`.
