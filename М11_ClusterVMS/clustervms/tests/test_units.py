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


def _run_spare(d: str, said: str | None, env: dict | None = None, w2c_env: str = "") -> subprocess.CompletedProcess:
    """`w2c-run.sh worker` as a spare's template runs it: `SPARE_FILE` names `said` (None: no file at all), the two
    shared files empty but for `w2c_env`, and a `python3` that prints its environment."""
    spare, w2c = os.path.join(d, "spare.env"), os.path.join(d, "w2c.env")
    if os.path.exists(spare):
        os.remove(spare)
    if said is not None:
        with open(spare, "w") as f:
            f.write(said)
    with open(w2c, "w") as f:
        f.write(w2c_env)
    py = os.path.join(d, "python3")
    with open(py, "w") as f:
        f.write("#!/bin/sh\necho \"$@\"\nenv\n")
    os.chmod(py, 0o755)
    full = {"PATH": os.environ["PATH"], "W2C_ENV": w2c, "VMS_ENV": os.path.join(d, "none"), "PYTHON": py,
            "W2C_HOME": d, "SPARE_FILE": spare, **(env or {})}
    return subprocess.run(["sh", os.path.join(DEPLOY, "w2c-run.sh"), "worker"], env=full, capture_output=True, text=True)


def test_a_spares_runner_takes_only_its_set_from_its_file_and_refuses_one_outside_the_alphabet():
    """The product's cross-check (4 Oct): the spare's template read its file by `EnvironmentFile=`, so whoever could
    write `/run/w2c-spares/<unit>.env` — the spares' script's user — could set ANY variable in a process holding the
    role's key and groups: `LD_PRELOAD`, `PYTHONPATH`. The runner reads the line `SPARE_FOR=` of the file the unit
    names (`SPARE_FILE`) and nothing else, checked against the labels' alphabet (`spec.LABEL_WORD`, comma-joined; empty
    is the empty set): every other line is ignored, a set outside the alphabet, no such line or no file at all is a
    spare that does not start — nothing exec'd. And neither name comes from the shared files: a regular unit never
    becomes a spare by a line in `w2c.env`."""
    from w2cplatform.spec import LABEL_WORD
    d = tempfile.mkdtemp(prefix="spare-")
    hostile = (f"LD_PRELOAD={d}/evil.so\nPYTHONPATH={d}/evil\nSECRETS_KEY={d}/stolen\n"
               "SPARE_FOR=vlan:dmz,zone-1.b_2\nSPARE_FOR=second\n")
    out = _run_spare(d, hostile)
    assert out.returncode == 0, out.stderr
    got = dict(l.split("=", 1) for l in out.stdout.splitlines()[1:] if "=" in l)
    assert got["SPARE_FOR"] == "vlan:dmz,zone-1.b_2"                                   # the first such line, that line only
    assert "LD_PRELOAD" not in got and "SECRETS_KEY" not in got
    assert got["PYTHONPATH"] == f"{d}/clustervms:{d}/vmsserver"                        # the runner's own, nothing added
    out = _run_spare(d, "SPARE_FOR=\n")
    assert out.returncode == 0 and "SPARE_FOR=" in out.stdout.splitlines(), out.stderr  # the empty set is a set
    word64 = "a" * 64
    assert LABEL_WORD.fullmatch(word64) and not LABEL_WORD.fullmatch(word64 + "a")
    assert _run_spare(d, f"SPARE_FOR={word64}\n").returncode == 0
    for bad in ("vlan dmz", "$(touch x)", ",a", "a,", "a,,b", "-a", "a;b", "склад", word64 + "a", "a\tb"):
        out = _run_spare(d, f"SPARE_FOR={bad}\n")
        assert out.returncode == 2 and "is not a label set" in out.stderr and "-m cluster" not in out.stdout, bad
    for said in (None, "LD_PRELOAD=x\n", "# SPARE_FOR=a\n"):
        out = _run_spare(d, said)
        assert out.returncode == 2 and "no SPARE_FOR= line" in out.stderr and "-m cluster" not in out.stdout, said
    out = _run_spare(d, "SPARE_FOR=x\n", w2c_env=f"SPARE_FOR=from-a-shared-file\nSPARE_FILE={d}/other\n")
    assert out.returncode == 0 and "SPARE_FOR=x" in out.stdout.splitlines()
    regular = subprocess.run(["sh", os.path.join(DEPLOY, "w2c-run.sh"), "worker"], capture_output=True, text=True,
                             env={"PATH": os.environ["PATH"], "W2C_ENV": os.path.join(d, "w2c.env"), "PYTHON": os.path.join(d, "python3"),
                                  "VMS_ENV": os.path.join(d, "none"), "W2C_HOME": d})
    assert regular.returncode == 0 and not [l for l in regular.stdout.splitlines() if l.startswith(("SPARE_FOR=", "SPARE_FILE="))]


def _polkit(rule: str, user: str, action: str, verb: str | None, unit_: str | None) -> str | None:
    """What the rule file answers, run by node against a stub `polkit`: "yes", "no", "not_handled" — or None when
    there is no node to run it."""
    import shutil
    node = shutil.which("node")
    if node is None:
        return None
    js = ("const R={YES:'yes',NO:'no',NOT_HANDLED:'not_handled'};let f;const polkit={Result:R,addRule:g=>{f=g}};"
          + open(rule, encoding="utf-8").read()
          + f"\nconst d={json.dumps({'verb': verb, 'unit': unit_})};"
          + f"process.stdout.write(String(f({{id:{json.dumps(action)},lookup:k=>d[k]===null?undefined:d[k]}},"
          + f"{{user:{json.dumps(user)}}})));")
    return subprocess.run([node, "-e", js], capture_output=True, text=True, check=True).stdout


def test_the_spares_script_runs_as_its_own_user_whom_polkit_lets_start_a_spare_template_and_nothing_else():
    """The product's cross-check (4 Oct): the spares' timer ran its script as root. It runs as `w2c-spares` — a user
    in no group but its own (`w2c-cluster.sysusers`), so no store socket, no key, no archive — and the polkit rule
    `install.sh --spares` installs lets that user do one thing through systemd: `start`, of an instance of a spare
    template, the templates being exactly `install.sh`'s SPARE_UNITS. Run by node where there is one: start of
    `vms-vmsworker-spare@2.service` yes; stop, restart, reset-failed of it no; start of the regular worker, of a
    template that is not a spare's, of a spare with no number, or a unit file written: no; another user: not this
    rule's business."""
    import re
    src = open(os.path.join(DEPLOY, "install.sh"), encoding="utf-8").read()
    spares = src.split('SPARE_UNITS="', 1)[1].split('"', 1)[0].split()
    rule = os.path.join(SYSTEMD, "w2c-spares.rules")
    text = open(rule, encoding="utf-8").read()
    named = re.search(r"/\^vms-\(([a-z|]+)\)-spare@", text).group(1).split("|")
    assert sorted(f"vms-{r}-spare@" for r in named) == sorted(spares)
    assert 'install -D -m 0644 "$HERE/systemd/w2c-spares.rules" /etc/polkit-1/rules.d/' in src
    users = _sysusers(os.path.join(SYSTEMD, "w2c-cluster.sysusers"))
    assert ["u", "w2c-spares", "-"] == next(l for l in users if l[:2] == ["u", "w2c-spares"])[:3]
    assert not [l for l in users if l[0] == "m" and l[1] == "w2c-spares"]                 # in no group but its own
    for f in sorted(os.listdir(M10)):
        if f.startswith("w2c-spares") and f.endswith(".service"):
            u = unit(os.path.join(M10, f))
            assert u["User"] == ["w2c-spares"] and u["Group"] == ["w2c-spares"] and "SupplementaryGroups" not in u, f
            assert u["RuntimeDirectory"] == ["w2c-spares"] and u["RuntimeDirectoryMode"] == ["0755"], f
    manage = "org.freedesktop.systemd1.manage-units"
    cases = [("w2c-spares", manage, "start", "vms-vmsworker-spare@2.service", "yes"),
             ("w2c-spares", manage, "start", "vms-recworker-spare@1.service", "yes"),
             ("w2c-spares", manage, "stop", "vms-vmsworker-spare@2.service", "no"),
             ("w2c-spares", manage, "restart", "vms-vmsworker-spare@2.service", "no"),
             ("w2c-spares", manage, "reset-failed", "vms-vmsworker-spare@2.service", "no"),
             ("w2c-spares", manage, "start", "vms-vmsworker.service", "no"),
             ("w2c-spares", manage, "start", "vms-liveworker-spare@1.service", "no"),
             ("w2c-spares", manage, "start", "vms-vmsworker-spare@.service", "no"),
             ("w2c-spares", manage, "start", "vms-vmsworker-spare@1.service.d", "no"),
             ("w2c-spares", manage, "start", "sshd.service", "no"),
             ("w2c-spares", manage, None, None, "no"),
             ("w2c-spares", "org.freedesktop.systemd1.manage-unit-files", None, None, "no"),
             ("w2c-spares", "org.freedesktop.systemd1.reload-daemon", None, None, "no"),
             ("vms", manage, "start", "vms-vmsworker-spare@2.service", "not_handled")]
    for user, action, verb, unit_, want in cases:
        got = _polkit(rule, user, action, verb, unit_)
        if got is None:
            import pytest
            pytest.skip("no node here to run the polkit rule; its names were checked above")
        assert got == want, (user, action, verb, unit_, got)


def test_install_installs_the_units_there_are():
    """The units, enabled; the spares' templates with `--spares` (never enabled: `w2c-spares.sh` starts their
    instances); and every unit file there is is one of the two."""
    src = open(os.path.join(DEPLOY, "install.sh"), encoding="utf-8").read()
    listed = src.split('\nUNITS="', 1)[1].split('"', 1)[0].split()
    spares = src.split('SPARE_UNITS="', 1)[1].split('"', 1)[0].split()
    assert sorted(listed) == sorted(["configstore", *UNITS])
    assert spares == ["vms-vmsworker-spare@", "vms-recworker-spare@"]
    assert sorted(f[:-len(".service")] for f in os.listdir(os.path.join(DEPLOY, "systemd")) if f.endswith(".service")) == sorted(listed + spares)
    assert "rights --check" in src and "--spares" in src and "@BOXID@" in src


# -- the box's layout (WP-E), the spares' templates, launchd's twins, the watchdog, Nomad's groups ----------------------
M10 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__import__("vms").__file__))), "deploy")
SYSTEMD = os.path.join(DEPLOY, "systemd")


def _sysusers(path: str) -> list[list[str]]:
    import shlex
    return [shlex.split(l) for l in open(path, encoding="utf-8") if l.strip() and not l.startswith("#")]


def test_the_users_and_groups_are_the_boxs_by_number_and_configstore_owns_every_socket():
    """WP-E: `install.sh` runs the box's `install-obsd.sh`, which applies the box's `w2c.sysusers` after this module's
    and refuses a `w2c` numbered otherwise — so the platform's user and its clients' groups are the box's, by number:
    `w2c` 2100, `w2c-events` 2102, `w2c-store` 2103, `w2c-secrets` 2104. The store's member runs as its own
    `configstore`, a member of every group the rights file gives a socket. Every group a unit joins is made by one of
    the files `install.sh` applies."""
    ours = _sysusers(os.path.join(SYSTEMD, "w2c-cluster.sysusers"))
    box = _sysusers(os.path.join(M10, "w2c.sysusers")) + _sysusers(os.path.join(M10, "obsd.sysusers"))
    for line in box:
        if line[0] in "ug" and line[1].startswith("w2c"):
            assert line[:3] == next(l[:3] for l in ours if l[1] == line[1]), line           # the same name, the same number
        if line[0] == "m":
            assert line in ours, line
    groups = {l[1] for l in ours + box if l[0] in "ug"}
    rights = json.load(open(RIGHTS, encoding="utf-8"))["roles"]
    assert {r["group"] for r in rights.values()} <= {l[2] for l in ours if l[:2] == ["m", "configstore"]}
    for f in sorted(os.listdir(SYSTEMD)):
        if f.endswith(".service"):
            u = unit(os.path.join(SYSTEMD, f))
            joined = set(" ".join(u.get("SupplementaryGroups", [])).split()) | set(u.get("Group", []))
            assert joined <= groups, (f, joined - groups)
    assert unit(os.path.join(SYSTEMD, "configstore.service"))["User"] == ["configstore"]


def test_the_directories_are_the_boxs_layout():
    """WP-E: the key ring 2710 root:w2c-secrets, the objects 2770 w2c:w2c-store, the events archive at
    `/data/platform/events` 2770 w2c:w2c-events (not `/data/archive`), the store's journal configstore's alone —
    and where both this file and the box's `w2c.tmpfiles` name a directory, they say the same."""
    def lines(path):
        return {l.split()[1]: l.split()[2:5] for l in open(path, encoding="utf-8") if l.startswith("d ")}
    ours, box = lines(os.path.join(SYSTEMD, "w2c-cluster.tmpfiles")), lines(os.path.join(M10, "w2c.tmpfiles"))
    assert ours["/data/platform/etc/secrets"] == ["2710", "root", "w2c-secrets"]
    assert ours["/data/platform/objects"] == ["2770", "w2c", "w2c-store"]
    assert ours["/data/platform/events"] == ["2770", "w2c", "w2c-events"]
    assert ours["/data/platform/configstore"] == ["0700", "configstore", "configstore"]
    assert "/data/archive" not in ours
    for path in set(ours) & set(box):
        assert ours[path] == box[path], path


def test_every_unit_writes_as_its_groups_and_sees_the_rest_of_the_system_read_only():
    """WP-E and the twelfth review's minor (the protection was configstore's alone): every unit `UMask=0007`,
    `ProtectSystem=strict` with what it writes said, `ProtectHome`, `PrivateTmp`. The objects' group for every
    process that opens them, the events archive's for the resource and its writers, the key ring's for the three
    that open a password — the console, the holder, the recorder — and no other."""
    events = {"w2c-resource", "vms-console", "vms-vmsworker", "vms-recworker"}
    secrets = {"vms-console", "vms-vmsworker", "vms-recworker"}
    for f in sorted(os.listdir(SYSTEMD)):
        if not f.endswith(".service"):
            continue
        name = f[:-len(".service")].replace("-spare@", "")
        u = unit(os.path.join(SYSTEMD, f))
        assert u["UMask"] == ["0007"] and u["ProtectSystem"] == ["strict"], f
        assert u["ProtectHome"] == ["yes"] and u["PrivateTmp"] == ["yes"] and u["NoNewPrivileges"] == ["yes"], f
        if name == "configstore":
            assert u["ReadWritePaths"] == ["/data/platform/configstore"]
            continue
        joined = set(u["SupplementaryGroups"][0].split())
        writes = set(u["ReadWritePaths"][0].split())
        assert "w2c-store" in joined and "/data/platform/objects" in writes, f
        assert ("w2c-events" in joined) == (name in events) == ("/data/platform/events" in writes), f
        assert ("w2c-secrets" in joined) == (name in secrets) == ("LoadCredential" in u), f


def test_a_spare_is_its_roles_unit_line_for_line_but_the_name():
    """The twelfth review, blocker 6 (the owner's decision: a spare has the regular unit's credentials, keys, environment,
    user and groups): `vms-<role>-spare@.service`, which `w2c-spares.sh` starts, is its role's unit with only these
    differences — no `WORKER_NAME`; a worker's set from its one-line file (`SPARE_FILE`, of which the runner reads
    `SPARE_FOR=` alone: no set, no start) and its fan-out on a port the OS gives; a recorder's door likewise. Nothing
    else may differ, so a line given to the role is given to its spares or this fails. And no `EnvironmentFile=` in a
    spare either (the product's cross-check, 4 Oct): a file read whole is every variable its writer wants."""
    allowed = {"vms-vmsworker": {("env", "WORKER_NAME"), ("env", "RTSP_PORT"), ("env", "SPARE_FILE"), ("Description",),
                                 ("WantedBy",)},
               "vms-recworker": {("env", "WORKER_NAME"), ("env", "ARCHIVE_PORT"), ("Description",), ("WantedBy",)}}
    for role, ok in allowed.items():
        a, b = unit(os.path.join(SYSTEMD, f"{role}.service")), unit(os.path.join(SYSTEMD, f"{role}-spare@.service"))
        diff = {(k,) for k in set(a) | set(b) if k not in ("env", "Environment") and a.get(k) != b.get(k)}
        diff |= {("env", k) for k in set(a["env"]) | set(b["env"]) if a["env"].get(k) != b["env"].get(k)}
        assert diff <= ok, (role, diff - ok)
    w = unit(os.path.join(SYSTEMD, "vms-vmsworker-spare@.service"))
    assert w["env"]["SPARE_FILE"] == "/run/w2c-spares/%n.env" and w["env"]["RTSP_PORT"] == "auto"
    assert "WORKER_NAME" not in w["env"]
    for name in ("vms-vmsworker-spare@", "vms-recworker-spare@"):
        assert "EnvironmentFile" not in unit(os.path.join(SYSTEMD, f"{name}.service")), name
    assert unit(os.path.join(SYSTEMD, "vms-recworker-spare@.service"))["env"]["ARCHIVE_PORT"] == "0"


# The spellings that differ between the two supervisors and nothing else: macOS has no /run (it is /var/run), no
# credentials directory (the key is read where it lies), no %l and no %m (`install.sh` puts @HOST@ and @BOXID@).
def _as_launchd(value: str) -> str:
    return (value.replace("/run/", "/var/run/").replace("%d/platform.key", "/etc/w2c/secrets/platform.key")
            .replace("%l", "@HOST@").replace("%m", "@BOXID@"))


def test_every_plist_says_what_its_unit_says_name_for_name():
    """The twelfth review, major 12: the plists had drifted — no `SECRETS_KEY` for the console, the worker and the
    recorder (the console on macOS stored passwords in the clear), no `OBSD_SOCKET` or `BOX_ID` for the recorder. Each
    plist's environment is its unit's, the same names and the same values but for the supervisors' own spellings."""
    for label, name in PLISTS.items():
        with open(os.path.join(DEPLOY, "launchd", f"{label}.plist"), "rb") as f:
            p = plistlib.load(f)
        u = unit(os.path.join(SYSTEMD, f"{name}.service"))
        assert p["EnvironmentVariables"] == {k: _as_launchd(v) for k, v in u["env"].items()}, label


def test_the_worker_and_the_recorder_tell_systemds_watchdog_that_their_loop_turns():
    """The twelfth review, major 14: lesson 8 promised a watchdog and there was none — a hung worker held its cameras
    the whole fifteen minutes. The worker's and the recorder's units say `WatchdogSec` — longer than the stand-in holds
    a hung step (`STAND_IN_FOR`), shorter than a hung worker keeps its cameras (`HUNG_MOVE_AFTER`) — and the loop says
    `WATCHDOG=1` to `$NOTIFY_SOCKET` at every turn: here a socket of the test's, two turns of a real loop, two
    datagrams. With no socket nothing is sent and nothing fails."""
    import socket
    import threading
    from cluster.worker import notify
    from w2cplatform.contract import HUNG_MOVE_AFTER, Worker
    from tests.conftest import Cluster
    for name in ("vms-vmsworker", "vms-recworker", "vms-vmsworker-spare@", "vms-recworker-spare@"):
        u = unit(os.path.join(SYSTEMD, f"{name}.service"))
        sec = float(u["WatchdogSec"][0])
        assert Worker.STAND_IN_FOR < sec < HUNG_MOVE_AFTER, name
        # the product's units (4 Oct): the main process may notify, and `simple` — under `notify` a spare waiting for
        # an offer, which says nothing until it is somebody, would hold `systemctl start` and the script behind it
        assert sec == 360 and u["Type"] == ["simple"] and u["NotifyAccess"] == ["main"], name
    d = tempfile.mkdtemp(prefix="notify-", dir="/tmp")
    path = os.path.join(d, "n.sock")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    s.bind(path)
    s.settimeout(5)
    try:
        assert notify(env={}) is False and notify(env={"NOTIFY_SOCKET": path + ".nobody"}) is False
        c = Cluster(); c.resources_up()
        w = c.worker("srv-a")
        stop, said = threading.Event(), []
        saved = os.environ.get("NOTIFY_SOCKET")
        os.environ["NOTIFY_SOCKET"] = path
        try:
            t = threading.Thread(target=w.run, kwargs={"poll": 0.05, "stop": stop})
            t.start()
            said = [s.recv(64), s.recv(64)]
            stop.set(); t.join(10)
        finally:
            os.environ.pop("NOTIFY_SOCKET") if saved is None else os.environ.__setitem__("NOTIFY_SOCKET", saved)
        assert said == [b"WATCHDOG=1", b"WATCHDOG=1"]
    finally:
        s.close()


def test_a_nomad_task_can_read_the_key_and_open_its_socket():
    """The twelfth review, major 13: under Nomad every task runs as `vms` with that user's groups, and the key ring was
    0750 root:w2c — `Sealer.from_file` raised and the tasks went round their restarts. The ring is 2710
    root:w2c-secrets now, the key 0640 to the same group, and `vms-nomad.sysusers` makes `vms` a member of what its
    tasks open: each task's store socket, the engine's group for the recorder, the key ring for every task given a
    key, and the box's events and objects."""
    import re
    member = {l[2] for l in _sysusers(os.path.join(DEPLOY, "nomad", "vms-nomad.sysusers")) if l[:2] == ["m", "vms"]}
    rights = json.load(open(RIGHTS, encoding="utf-8"))["roles"]
    for job in ("console", "vmsworker", "recworker"):
        src = open(os.path.join(DEPLOY, "nomad", f"{job}.nomad.hcl"), encoding="utf-8").read()
        assert re.search(r'\buser\s*=\s*"vms"', src), job
        role = re.search(r'configstore:///run/configstore/(\w+)\.sock', src).group(1)
        assert rights[role]["group"] in member, job
        if "SECRETS_KEY" in src:
            assert "w2c-secrets" in member, job
        if "OBSD_SOCKET" in src:
            assert "vms-obsd" in member, job
    assert {"w2c-events", "w2c-store"} <= member
    tmp = {l.split()[1]: l.split()[2:5] for l in open(os.path.join(SYSTEMD, "w2c-cluster.tmpfiles")) if l.startswith("d ")}
    assert tmp["/data/platform/etc/secrets"] == ["2710", "root", "w2c-secrets"]
