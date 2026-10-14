# The domain's units (М11's servers; no orchestrator)

The cluster's form (`deploy/cluster/systemd`): each unit runs `w2c-run.sh <verb>`, names its role's socket
(`PLATFORM_STORE`), joins that role's group first, and lists no `EnvironmentFile=` — the site's lines are
`/etc/w2c/w2c.env`'s (`domain.env.example`), read under the unit's. A unit that seals or opens a secret loads the ring as
a credential (`SECRETS_KEY=%d/platform.key`); the domain's console loads none (ADR-0032).

| unit | verb | role socket | user | where |
|---|---|---|---|---|
| `w2c-domain.service` | `signer` | `domain` | w2c | the holder: the keys and the holder's pass; /api/login, /api/carry/<member>, the five operations on 8445, the tokens socket |
| `w2c-domain-console.service` | `domainconsole` | `domainconsole` | w2c | the holder: 8444, no key (the cluster's console keeps 8080) |
| `w2c-domainagent.service` | `domainagent` | `domainagent` | w2c | every server |
| `vms-domainpart.service` | `vms domainpart` | `camdomain` | vms | the holder: temporary VMS console diagnostics, 8096 |

`w2c-domain.tmpfiles` makes the tokens socket's directory (2750 w2c:vms-camdomaintokens): the tokens socket's own group
(ADR-0031, `<deployment>-<sub>domaintokens`), with no deployed readers after C6 — no `m` line in the sysusers or unit joins it. Rights: the configstore's file
(`deploy/cluster/configstore-rights.json`, the domain roles from `w2cplatform/domain/rights.py`): `domain`,
`domainconsole` (no `domain/signer*`, read or write), `domainagent` (with `!` denials), `camdomain`. Groups:
`deploy/cluster/systemd/w2c-cluster.sysusers`. The console's groups are its socket's, `w2c-store` and `w2c-events` — not
the ring's, not the tokens socket's — and the key file and the signer's sockets are `InaccessiblePaths=` for it. mTLS
names when the doors get them: `domain.<server>`, `domainconsole.<server>`, `domainagent.<server>`.


## Role token doors (ADR-0074)

The member agent binds one Unix door per role granted by the loaded token specs.
Before enabling these specs, provision the directories and the agent's groups
from that same catalogue. Run from Source with the deployment's SPEC_DIR (vms in
this course) and TOKEN_REQUESTS_DIR=/run/w2c-token-requests:

```sh
python3 -m w2cplatform.domain.tokenrequest tmpfiles
python3 -m w2cplatform.domain.tokenrequest groups
```

Append the first output to the installed domain tmpfiles configuration, apply it
with systemd-tmpfiles as root; install the second output as a domainagent service
drop-in, reload systemd and restart the agent. Run this after every grant change.
The base is root:root 0755; each role directory is root:<derived role group> 2770,
and its socket 0660. Workers join only their existing role group. The agent joins
all generated groups. The generator uses cluster.rights.group and loaded specs;
there is no list of subsystem roles in platform code. Worker and agent must see
the same directory (mount it into a container without changing uid/gid).

Unconfigured or unsafe directories disable that role's issuance and report the
failure; there is no fallback to the holder's token socket. A deployment with
User=w2c must preserve root ownership of the role directories: a directory owned
by w2c does not separate processes with the same uid. Token kind determines the
subsystem, while the socket fixes the role; the request body contains only ref.
