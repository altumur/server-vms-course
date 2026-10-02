"""The recorder's job and the host's archive engine say the same thing, and a test says so.

Every node of the cluster runs М10's `obsd.service`, installed by М10's `install-obsd.sh`: the daemon as its own
user, its socket in a directory of its own, and only the members of one group let in. The recorder's job is written
by hand beside it, and nothing compared the two: the unit moved its socket from /run/vms to /run/obsd and started
refusing peers outside its group, and the job went on mounting /run/vms, naming no socket and no group — every
recorder of the cluster saw its volume `away` for ever, and the suite stayed green (the review's fourth pass, blocker
3). The job could not open a network volume's secret either: no key, and no grant to read one.

So the job is read as a file and held against the unit, the install files and the policy: the socket, the group the
daemon lets in — by the number a container joins it by — and the key."""
import os
import re

import vms

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOB = os.path.join(HERE, "deploy", "recworker.nomad.hcl")
POLICY = os.path.join(HERE, "deploy", "recworker-policy.hcl")
M10 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(vms.__file__))), "deploy")


def _code(path: str) -> str:
    """The file without its comments: what Nomad reads, not what the notes say."""
    return "\n".join(re.sub(r"\s#.*$", "", l) for l in open(path, encoding="utf-8") if not l.lstrip().startswith("#"))


def _unit(name: str) -> dict:
    """An М10 unit's `[Service]`/`[Container]` keys, repeated ones as lists."""
    out: dict = {}
    for line in open(os.path.join(M10, name), encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith(("#", "[")) and "=" in line:
            k, v = line.split("=", 1)
            out.setdefault(k, []).append(v)
    return out


def _gids() -> dict:
    """`obsd.sysusers`'s groups: {name: gid}."""
    return {f[1]: f[2] for f in (l.split() for l in open(os.path.join(M10, "obsd.sysusers"), encoding="utf-8"))
            if f and f[0] == "g"}


def test_the_recorder_job_reaches_the_daemon_the_hosts_unit_runs():
    job, svc = _code(JOB), _unit("obsd.service")
    sock = svc["ExecStart"][0].split("--socket", 1)[1].strip()
    env = dict(re.findall(r'^\s*([A-Z_]+)\s*=\s*"([^"]*)"', job, re.M))
    assert env["OBSD_SOCKET"] == sock                                                  # where the daemon listens
    volumes = re.search(r"volumes\s*=\s*\[([^\]]*)\]", job).group(1)
    sock_dir = os.path.dirname(sock)
    assert f'"{sock_dir}:{sock_dir}"' in volumes                                       # …mounted into the task
    group = dict(e.split("=", 1) for e in svc["Environment"])["OBSD_CLIENT_GROUP"]
    assert group == svc["Group"][0]
    user = re.search(r'^\s*user\s*=\s*"(\d+):(\d+)"', job, re.M)
    assert user and user.group(2) == _gids()[group]                                     # the group the daemon lets in, by number
    rec = _unit("recworker@.container")
    assert rec["GroupAdd"] == [user.group(2)]                                           # the same number as М10's own recorder
    assert dict(e.split("=", 1) for e in rec["Environment"])["OBSD_SOCKET"] == sock


def test_the_recorder_job_opens_a_network_volumes_secret_with_the_clusters_key():
    """`module-design.md` (М10B) says the key is a Nomad variable that the policies of exactly the three jobs that open
    sealed fields read: the console, the worker and the recorder. The recorder's job renders it and says where; its
    policy lets it read the variable."""
    job = _code(JOB)
    tpl = re.search(r'template\s*\{\s*\n\s*data\s*=\s*"[^\n]*nomadVar \\"secrets/vms\\"[^\n]*\n\s*destination\s*=\s*"([^"]+)"', job)
    assert tpl, "the job renders no key"
    env = dict(re.findall(r'^\s*([A-Z_]+)\s*=\s*"([^"]*)"', job, re.M))
    assert env["SECRETS_KEY"] == "/" + tpl.group(1)                                     # the task's secrets dir, at /secrets
    from tests.test_policies import rules
    assert any(p == "secrets/vms" and "read" in caps for p, caps in rules("recworker-policy.hcl"))
    readers = {n for n in os.listdir(os.path.join(HERE, "deploy")) if n.endswith("-policy.hcl")
               and any(p == "secrets/vms" for p, _ in rules(n))}
    assert readers == {"console-policy.hcl", "vmsworker-policy.hcl", "recworker-policy.hcl"}   # and nobody else
