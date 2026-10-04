"""The units of a cluster server say what the rights file and the code say.

A process's identity in the store is the socket it can open: its unit joins its role's group
(`SupplementaryGroups=`) and names its role's socket (`PLATFORM_STORE=configstore:///run/configstore/<role>.sock`);
the daemon owns each socket by the rights file's `group`. Three files written by hand beside each other — the
systemd unit, the launchd plist, the rights file — and a fourth that runs them all (`w2c-run.sh`). These checks are
what keep them one thing: every role a process runs as has a unit and a plist, each naming the role's socket and,
for systemd, joining its group; the names come from the unit (`w-%l-1`, product P4); the runner reads the two env
files under what the unit said, never over it; `install.sh` installs the units there are."""
import json
import os
import plistlib
import subprocess
import tempfile

from tests.conftest import RIGHTS
from tests.test_recorder_job import unit

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY = os.path.join(HERE, "deploy")
# The role each unit runs as, and the verb `w2c-run.sh` runs (`cluster/__main__.py`).
UNITS = {"w2c-resource": ("resource", "resource"), "vms-console": ("console", "console"),
         "vms-vmscontroller": ("vmscontroller", "controller"), "vms-reccontroller": ("reccontroller", "reccontroller"),
         "vms-vmsworker": ("vmsworker", "worker"), "vms-recworker": ("recworker", "recorder")}
PLISTS = {"com.w2c.resource": "w2c-resource", "com.w2c.vms.console": "vms-console",
          "com.w2c.vms.vmscontroller": "vms-vmscontroller", "com.w2c.vms.reccontroller": "vms-reccontroller",
          "com.w2c.vms.vmsworker": "vms-vmsworker", "com.w2c.vms.recworker": "vms-recworker"}


def test_every_unit_opens_its_roles_socket_and_joins_its_group():
    import cluster.__main__ as m
    groups = {r: g["group"] for r, g in json.load(open(RIGHTS, encoding="utf-8"))["roles"].items()}
    assert set(m.ROLES.values()) == {role for role, _ in UNITS.values()}            # a unit for each verb's role
    for name, (role, verb) in UNITS.items():
        u = unit(os.path.join(DEPLOY, "systemd", f"{name}.service"))
        assert u["env"]["PLATFORM_STORE"] == f"configstore:///run/configstore/{role}.sock", name
        assert u["SupplementaryGroups"][0].split()[0] == groups[role], name
        assert u["ExecStart"] == [f"/opt/w2c/bin/w2c-run.sh {verb}"] and m.ROLES[verb] == role, name
        assert "configstore.service" in u["After"][0], name                         # the store's member first
        assert u["User"] == (["w2c"] if role == "resource" else ["vms"]), name       # the platform's user, the subsystem's
        assert "EnvironmentFile" not in u, f"{name}: a file would override what the unit says"
    store = unit(os.path.join(DEPLOY, "systemd", "configstore.service"))
    assert store["ExecStart"] == ["/opt/w2c/bin/w2c-run.sh configstore"] and store["RuntimeDirectory"] == ["configstore"]


def test_a_worker_is_named_by_its_unit_one_per_server():
    """The product's P4: `Environment=WORKER_NAME=w-%l-1` — one name per server and role, `w-srv-a-1` on srv-a; a
    restarted process claims the same name, and the store's CAS decides between two that both do."""
    assert unit(os.path.join(DEPLOY, "systemd", "vms-vmsworker.service"))["env"]["WORKER_NAME"] == "w-%l-1"
    assert unit(os.path.join(DEPLOY, "systemd", "vms-recworker.service"))["env"]["WORKER_NAME"] == "r-%l-1"


def test_every_plist_is_its_units_twin():
    """launchd has no `%l` and no groups per unit: the plist names the same socket (under /var/run, macOS has no
    /run), the same verb, and the name with `@HOST@`, which `install.sh` replaces."""
    for label, name in PLISTS.items():
        with open(os.path.join(DEPLOY, "launchd", f"{label}.plist"), "rb") as f:
            p = plistlib.load(f)
        role, verb = UNITS[name]
        assert p["Label"] == label and p["ProgramArguments"] == ["/opt/w2c/bin/w2c-run.sh", verb], label
        assert p["EnvironmentVariables"]["PLATFORM_STORE"] == f"configstore:///var/run/configstore/{role}.sock", label
        assert p["KeepAlive"] is True, label
    with open(os.path.join(DEPLOY, "launchd", "com.w2c.configstore.plist"), "rb") as f:
        p = plistlib.load(f)
    assert p["ProgramArguments"][1] == "configstore" and p["EnvironmentVariables"]["CONFIGSTORE_SOCKETS"] == "/var/run/configstore"
    with open(os.path.join(DEPLOY, "launchd", "com.w2c.vms.vmsworker.plist"), "rb") as f:
        assert plistlib.load(f)["EnvironmentVariables"]["WORKER_NAME"] == "w-@HOST@-1"


def test_the_runner_reads_the_two_files_under_what_the_unit_said():
    """`w2c-run.sh` loads /etc/w2c/w2c.env, then /etc/vms/vms.env, setting a name only when it is not set already: the
    unit's socket and name win over any file, the platform's file over the subsystem's; a line that is not
    `NAME=value` is skipped, and nothing in a file is run."""
    d = tempfile.mkdtemp(prefix="run-")
    w2c, vms_ = os.path.join(d, "w2c.env"), os.path.join(d, "vms.env")
    with open(w2c, "w") as f:
        f.write("# the platform's\nSERVER_NAME=srv-b\nPLATFORM_STORE=file:///nowhere\nCAPACITY=7\nnot a line\n"
                "EVIL=$(touch " + d + "/ran)\n")
    with open(vms_, "w") as f:
        f.write("CAPACITY=50\nARCHIVE=/data/archive\n")
    py = os.path.join(d, "python3")
    with open(py, "w") as f:                                          # what the runner execs: print the environment
        f.write("#!/bin/sh\necho \"$@\"\nenv\n")
    os.chmod(py, 0o755)
    env = {"PATH": os.environ["PATH"], "W2C_ENV": w2c, "VMS_ENV": vms_, "PYTHON": py, "W2C_HOME": d,
           "PLATFORM_STORE": "configstore:///run/configstore/vmsworker.sock"}
    out = subprocess.run(["sh", os.path.join(DEPLOY, "w2c-run.sh"), "worker"], env=env, capture_output=True, text=True,
                         check=True).stdout.splitlines()
    got = dict(l.split("=", 1) for l in out[1:] if "=" in l)
    assert out[0] == "-m cluster worker"
    assert got["PLATFORM_STORE"] == "configstore:///run/configstore/vmsworker.sock"      # the unit's
    assert got["SERVER_NAME"] == "srv-b" and got["CAPACITY"] == "7" and got["ARCHIVE"] == "/data/archive"
    assert got["EVIL"] == "$(touch " + d + "/ran)" and not os.path.exists(os.path.join(d, "ran"))   # a value, never run
    assert got["PYTHONPATH"].startswith(f"{d}/clustervms:{d}/vmsserver")
    with open(w2c, "a") as f:
        f.write("CONFIGSTORE_RAFT=10.0.0.2:8301\nCONFIGSTORE_API=10.0.0.2:8300\nCONFIGSTORE_JOIN=srv-a@10.0.0.1:8300\n")
    out = subprocess.run(["sh", os.path.join(DEPLOY, "w2c-run.sh"), "configstore"], env=env, capture_output=True,
                         text=True, check=True).stdout.splitlines()
    assert out[0] == ("-m w2cplatform.configstore -id srv-b -dir /data/platform/configstore -raft 10.0.0.2:8301 -api "
                      "10.0.0.2:8300 -sockets /run/configstore -rights /etc/w2c/configstore-rights.json -tls "
                      "/etc/w2c/tls -tuning lan -join srv-a@10.0.0.1:8300")


def test_install_installs_the_units_there_are():
    src = open(os.path.join(DEPLOY, "install.sh"), encoding="utf-8").read()
    listed = src.split('UNITS="', 1)[1].split('"', 1)[0].split()
    assert sorted(listed) == sorted(["configstore", *UNITS])
    assert sorted(f[:-len(".service")] for f in os.listdir(os.path.join(DEPLOY, "systemd")) if f.endswith(".service")) == sorted(listed)
    assert "rights --check" in src and "--spares" in src
