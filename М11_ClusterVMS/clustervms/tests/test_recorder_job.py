"""The recorder's unit and the host's archive engine say the same thing, and a test says so.

Every server of the cluster runs М10's obsd unit, installed as `vms-obsd.service` (`install.sh`): the daemon as its
own user, its socket in a directory of its own, and only the members of one group let in. The recorder's unit is
written by hand beside it, and nothing compared the two once before: the obsd unit moved its socket and started
refusing peers outside its group, and the recorder's job went on naming the old place and no group — every recorder
of the cluster saw its volume `away` for ever, and the suite stayed green (the review's fourth pass, blocker 3). The
recorder could not open a network volume's secret either: no key.

So the recorder's unit is read as a file and held against М10's obsd unit and its users file: the socket the daemon
listens on, the group it lets in (by name, which a unit joins), the unit it comes after — and the key. The appendix's
Nomad job (`deploy/nomad/recworker.nomad.hcl`) is held to the same socket."""
import os
import re

import vms

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIT = os.path.join(HERE, "deploy", "systemd", "vms-recworker.service")
JOB = os.path.join(HERE, "deploy", "nomad", "recworker.nomad.hcl")
M10 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(vms.__file__))), "deploy")

# The platform's rename is merged after this module's rework: until it is, М10's unit still says the names before it.
# What it says is read through this table, so the check holds on both sides of that merge; after it the table maps
# nothing that is still there.
BEFORE_THE_RENAME = {"/run/obsd/obsd.sock": "/run/vms-obsd/obsd.sock", "vms-rec": "vms-obsd"}


def unit(path: str) -> dict:
    """A unit's keys, repeated ones as lists; `Environment=` as a dict under `env`."""
    out: dict = {"env": {}}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith(("#", "[")) and "=" in line:
            k, v = line.split("=", 1)
            if k == "Environment":
                name, _, value = v.partition("=")
                out["env"][name] = value
            out.setdefault(k, []).append(v)
    return out


def obsd_unit() -> tuple[str, dict]:
    for name in ("vms-obsd.service", "obsd.service"):
        if os.path.exists(os.path.join(M10, name)):
            return name, unit(os.path.join(M10, name))
    raise AssertionError("М10's obsd unit is not in vmsserver/deploy/")


def renamed(value: str) -> str:
    return BEFORE_THE_RENAME.get(value, value)


def test_the_recorder_unit_reaches_the_daemon_the_hosts_unit_runs():
    name, svc = obsd_unit()
    rec = unit(UNIT)
    sock = renamed(svc["ExecStart"][0].split("--socket", 1)[1].strip().split()[0])
    assert rec["env"]["OBSD_SOCKET"] == sock                                            # where the daemon listens
    group = renamed(svc["env"]["OBSD_CLIENT_GROUP"])
    assert group == renamed(svc["Group"][0])                                            # the group the daemon lets in…
    assert group in rec["SupplementaryGroups"][0].split()                               # …is one the recorder joins
    assert "vms-recworker" in rec["SupplementaryGroups"][0].split()                     # with its own store socket's
    users = next(f for f in ("vms-obsd.sysusers", "obsd.sysusers") if os.path.exists(os.path.join(M10, f)))
    groups = {renamed(f[1]) for f in (l.split() for l in open(os.path.join(M10, users), encoding="utf-8")) if f and f[0] == "g"}
    assert group in groups                                                              # a group the host has
    assert "vms-obsd.service" in rec["After"][0] and "vms-obsd.service" in rec["Wants"][0]   # the name `install.sh` gives it
    job = open(JOB, encoding="utf-8").read()
    assert re.search(r'OBSD_SOCKET\s*=\s*"([^"]+)"', job).group(1) == sock              # the appendix too


def test_the_recorder_unit_opens_a_network_volumes_secret_with_the_clusters_key():
    """A network volume's `access_secret` is sealed by the console to its row, and the daemon takes credentials only as
    the volume's parameters — so the recorder, which mounts the volume, opens it (М10's third review, blocker 3). Its
    unit loads the cluster's key as a systemd credential and says where it is."""
    rec = unit(UNIT)
    assert rec["LoadCredential"] == ["platform.key:/etc/w2c/secrets/platform.key"]
    assert rec["env"]["SECRETS_KEY"] == "%d/platform.key"
    assert rec["env"]["WORKER_NAME"] == "r-%l-1" and rec["env"]["BOX_ID"] == "%m"       # its name from the unit; which box
    assert rec["env"]["PLATFORM_STORE"] == "configstore:///run/configstore/recworker.sock"
