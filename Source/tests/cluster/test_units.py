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

from tests.cluster.conftest import RIGHTS
from tests.cluster.test_recorder_job import unit

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # Source/
DEPLOY = os.path.join(HERE, "deploy", "cluster")
# The role each unit runs as, and what `w2c-run.sh` is told to run: the platform's verbs (`python3 -m w2cplatform.cluster`)
# and the VMS's processes (`python3 -m vms`). A subsystem's controller is an instance of the platform's template
# (`w2c-controller@<sub>`, ADR 0023); its role keeps the spec's name.
UNITS = {"w2c-resource": ("resource", "resource"), "w2c-console": ("console", "console"),
         "vms-jobs": ("console", "vms jobs"),
         "w2c-controller@vms": ("vmscontroller", "controller vms"), "w2c-controller@rec": ("reccontroller", "controller rec"),
         "vms-vmsworker": ("vmsworker", "vms worker"), "vms-recworker": ("recworker", "vms recorder")}
PLISTS = {"com.w2c.resource": "w2c-resource", "com.w2c.console": "w2c-console", "com.w2c.vms.jobs": "vms-jobs",
          "com.w2c.controller.vms": "w2c-controller@vms", "com.w2c.controller.rec": "w2c-controller@rec",
          "com.w2c.vms.vmsworker": "vms-vmsworker", "com.w2c.vms.recworker": "vms-recworker"}


def service(name: str) -> dict:
    """A systemd unit by name; an instance (`w2c-controller@vms`) is its template's file with `%i` put in, as systemd
    reads it."""
    base, _, instance = name.partition("@")
    if not instance:
        return unit(os.path.join(DEPLOY, "systemd", f"{name}.service"))
    text = open(os.path.join(DEPLOY, "systemd", f"{base}@.service"), encoding="utf-8").read().replace("%i", instance)
    with tempfile.NamedTemporaryFile("w", suffix=".service", delete=False, encoding="utf-8") as f:
        f.write(text)
    return unit(f.name)


def test_every_unit_opens_its_roles_socket_and_joins_its_group():
    groups = {r: g["group"] for r, g in json.load(open(RIGHTS, encoding="utf-8"))["roles"].items()}
    for name, (role, verb) in UNITS.items():
        u = service(name)
        assert u["env"]["PLATFORM_STORE"] == f"configstore:///run/configstore/{role}.sock", name
        assert u["SupplementaryGroups"][0].split()[0] == groups[role], name
        assert u["ExecStart"] == [f"/opt/w2c/bin/w2c-run.sh {verb}"], name
        assert "configstore.service" in u["After"][0], name                         # the store's member first
        # a platform process runs as the platform's user, never the subsystem's (ADR 0023): the resource, the console,
        # every controller; the subsystem's processes as `vms` — its housekeeping too, on the console's socket
        assert u["User"] == (["w2c"] if name.startswith("w2c-") else ["vms"]), name
        assert "EnvironmentFile" not in u, f"{name}: a file would override what the unit says"
    store = unit(os.path.join(DEPLOY, "systemd", "configstore.service"))
    assert store["ExecStart"] == ["/opt/w2c/bin/w2c-run.sh configstore"] and store["RuntimeDirectory"] == ["configstore"]


def test_a_worker_is_named_by_its_unit_one_per_server():
    """The product's P4: `Environment=WORKER_NAME=w-%l-1` — one name per server and role, `w-srv-a-1` on srv-a; a
    restarted process claims the same name, and the store's CAS decides between two that both do."""
    assert unit(os.path.join(DEPLOY, "systemd", "vms-vmsworker.service"))["env"]["WORKER_NAME"] == "w-%l-1"
    assert unit(os.path.join(DEPLOY, "systemd", "vms-recworker.service"))["env"]["WORKER_NAME"] == "r-%l-1"


def test_every_plist_is_its_units_twin():
    """launchd has no `%l` and no groups per unit: the plist names the same socket, the same verb, and the name with
    `@HOST@`, which `install.sh` replaces. Under the box (the thirteenth review, major 15): a Mac has no /data and no
    /opt/w2c of ours, so the runner, the sockets and the logs are the box's — `__BOX__`, which `install.sh --box`
    replaces — and every plist names its box (`W2C_BOX`), whose files the runner reads."""
    for label, name in PLISTS.items():
        with open(os.path.join(DEPLOY, "launchd", f"{label}.plist"), "rb") as f:
            p = plistlib.load(f)
        role, verb = UNITS[name]
        assert p["Label"] == label and p["ProgramArguments"] == ["__BOX__/bin/w2c-run.sh", *verb.split()], label
        assert p["EnvironmentVariables"]["PLATFORM_STORE"] == f"configstore://__BOX__/state/run/configstore/{role}.sock", label
        assert p["KeepAlive"] is True and p["StandardErrorPath"] == f"__BOX__/state/logs/{label}.log", label
    for f in sorted(os.listdir(os.path.join(DEPLOY, "launchd"))):
        if f.endswith(".plist"):
            with open(os.path.join(DEPLOY, "launchd", f), "rb") as fh:
                p = plistlib.load(fh)
            assert p["EnvironmentVariables"]["W2C_BOX"] == "__BOX__", f
            body = repr(p)
            assert not [w for w in ("/opt/", "/etc/w2c", "/etc/vms", "/var/", "/data", "/usr/local") if w in body], (f, body)
    with open(os.path.join(DEPLOY, "launchd", "com.w2c.configstore.plist"), "rb") as f:
        p = plistlib.load(f)
    assert p["ProgramArguments"][1] == "configstore"
    assert p["EnvironmentVariables"]["CONFIGSTORE_SOCKETS"] == "__BOX__/state/run/configstore"
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
        f.write("CAPACITY=50\nRESOURCE_ROOT=/data/archive\n")
    py = os.path.join(d, "python3")
    with open(py, "w") as f:                                          # what the runner execs: print the environment
        f.write("#!/bin/sh\necho \"$@\"\nenv\n")
    os.chmod(py, 0o755)
    env = {"PATH": os.environ["PATH"], "W2C_ENV": w2c, "VMS_ENV": vms_, "PYTHON": py, "W2C_HOME": d,
           "PLATFORM_STORE": "configstore:///run/configstore/vmsworker.sock"}
    out = subprocess.run(["sh", os.path.join(DEPLOY, "w2c-run.sh"), "console"], env=env, capture_output=True, text=True,
                         check=True).stdout.splitlines()
    got = dict(l.split("=", 1) for l in out[1:] if "=" in l)
    assert out[0] == "-m w2cplatform.cluster console"
    assert got["PLATFORM_STORE"] == "configstore:///run/configstore/vmsworker.sock"      # the unit's
    assert got["SERVER_NAME"] == "srv-b" and got["CAPACITY"] == "7" and got["RESOURCE_ROOT"] == "/data/archive"
    assert got["EVIL"] == "$(touch " + d + "/ran)" and not os.path.exists(os.path.join(d, "ran"))   # a value, never run
    assert got["PYTHONPATH"].startswith(f"{d}/Source")
    with open(w2c, "a") as f:
        f.write("CONFIGSTORE_RAFT=10.0.0.2:8301\nCONFIGSTORE_API=10.0.0.2:8300\nCONFIGSTORE_JOIN=srv-a@10.0.0.1:8300\n")
    out = subprocess.run(["sh", os.path.join(DEPLOY, "w2c-run.sh"), "configstore"], env=env, capture_output=True,
                         text=True, check=True).stdout.splitlines()
    assert out[0] == ("-m w2cplatform.configstore -id srv-b -dir /data/platform/configstore -raft 10.0.0.2:8301 -api "
                      "10.0.0.2:8300 -sockets /run/configstore -rights /etc/w2c/configstore-rights.json -tls "
                      "/etc/w2c/tls -tuning lan -join srv-a@10.0.0.1:8300")


def test_the_runner_writes_as_its_group_however_it_was_started_and_finds_a_box_by_its_directory():
    """The thirteenth review, major 13: a unit says `UMask=0007`, but Nomad's `raw_exec` hands on the agent's 0022 —
    the events archive's buckets came out 2755 `vms:w2c-events`, the resource (`w2c`) could not delete them, and its
    retention stopped. The runner sets 0007 itself: started under 0022, what it execs has 0007. And major 15: a box on
    macOS (`install.sh --box <dir>`) has no /etc/w2c and no /data — a plist says `W2C_BOX`, and the runner reads that
    box's two files, runs its code, and gives the store's member the box's journal, sockets, rights and TLS."""
    d = tempfile.mkdtemp(prefix="run-")
    py = os.path.join(d, "python3")
    with open(py, "w") as f:
        f.write("#!/bin/sh\necho \"$@\"\necho \"umask=$(umask)\"\nenv\n")
    os.chmod(py, 0o755)
    with open(os.path.join(d, "w2c.env"), "w") as f:
        f.write("SERVER_NAME=mac-a\nCONFIGSTORE_RAFT=127.0.0.1:8301\nCONFIGSTORE_API=127.0.0.1:8300\n")
    with open(os.path.join(d, "vms.env"), "w") as f:
        f.write("CAPACITY=9\n")
    env = {"PATH": os.environ["PATH"], "PYTHON": py, "W2C_BOX": d}
    out = subprocess.run(["sh", os.path.join(DEPLOY, "w2c-run.sh"), "console"], env=env, capture_output=True, text=True,
                         check=True, preexec_fn=lambda: os.umask(0o022)).stdout.splitlines()
    got = dict(l.split("=", 1) for l in out[1:] if "=" in l)
    assert got["umask"] in ("0007", "007"), got["umask"]
    assert got["SERVER_NAME"] == "mac-a" and got["CAPACITY"] == "9"                     # the box's two files
    assert got["PYTHONPATH"].startswith(f"{d}/Source")                 # …and its code
    out = subprocess.run(["sh", os.path.join(DEPLOY, "w2c-run.sh"), "configstore"], env=env, capture_output=True,
                         text=True, check=True).stdout.splitlines()
    assert out[0] == (f"-m w2cplatform.configstore -id mac-a -dir {d}/state/configstore -raft 127.0.0.1:8301 -api "
                      f"127.0.0.1:8300 -sockets {d}/state/run/configstore -rights {d}/configstore-rights.json -tls "
                      f"{d}/tls -tuning lan -bootstrap")


def test_the_controllers_reach_budget_is_named_where_an_operator_looks():
    """The thirteenth review, minor: `REACH_BUDGET` (the twelfth review's M7: how many units a pass moves to a server
    that reaches them; a group left over is `units.over_budget`) was read by the controller and named in no env file of
    the delivery and in neither entry point's list of settings. Both env examples (this module's and the box's) name
    it, and both entry points' docstrings."""
    import w2cplatform.host as h
    import vms.__main__ as vm
    assert "REACH_BUDGET" in (h.__doc__ or "") and "REACH_BUDGET" in (vm.__doc__ or "")
    for path in (os.path.join(SYSTEMD, "vms.env.example"), os.path.join(M10, "vms.env.example")):
        assert "#REACH_BUDGET=10" in open(path, encoding="utf-8").read(), path


def _run_spare(d: str, said: str | None, env: dict | None = None, w2c_env: str = "") -> subprocess.CompletedProcess:
    """`w2c-run.sh` as a spare's template runs it (the verb is the runner's last word, the set its first): `SPARE_FILE` names `said` (None: no file at all), the two
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
    return subprocess.run(["sh", os.path.join(DEPLOY, "w2c-run.sh"), "console"], env=full, capture_output=True, text=True)


def test_a_spares_runner_takes_only_its_set_from_its_file_and_refuses_one_outside_the_alphabet():
    """The product's cross-check (4 Oct): the spare's template read its file by `EnvironmentFile=`, so whoever could
    write `/run/w2c-spares/<unit>.env` — the spares' script's user — could set ANY variable in a process holding the
    role's key and groups: `LD_PRELOAD`, `PYTHONPATH`. The runner reads the line `SPARE_FOR=` of the file the unit
    names (`SPARE_FILE`) and nothing else, checked against the labels' alphabet (`spec.LABEL_WORD`, comma-joined; empty
    is the empty set): every other line is ignored, a set outside the alphabet, no such line or no file at all is a
    spare that does not start — nothing exec'd. And neither name comes from the shared files: a regular unit never
    becomes a spare by a line in `w2c.env`. The thirteenth review, minor: the set is the file's FIRST line — what the
    spares' script writes — not the first `SPARE_FOR=` anywhere in it; a file that opens with anything else is refused."""
    from w2cplatform.spec import LABEL_WORD
    d = tempfile.mkdtemp(prefix="spare-")
    hostile = (f"SPARE_FOR=vlan:dmz,zone-1.b_2\nLD_PRELOAD={d}/evil.so\nPYTHONPATH={d}/evil\nSECRETS_KEY={d}/stolen\n"
               "SPARE_FOR=second\n")
    out = _run_spare(d, hostile)
    assert out.returncode == 0, out.stderr
    got = dict(l.split("=", 1) for l in out.stdout.splitlines()[1:] if "=" in l)
    assert got["SPARE_FOR"] == "vlan:dmz,zone-1.b_2"                                   # the first line, that line only
    assert "LD_PRELOAD" not in got and "SECRETS_KEY" not in got
    out = _run_spare(d, "# a comment first\nSPARE_FOR=vlan:dmz\n")
    assert out.returncode == 2 and "is not SPARE_FOR=" in out.stderr and "-m " not in out.stdout, out.stderr
    assert got["PYTHONPATH"] == f"{d}/Source"                        # the runner's own, nothing added
    out = _run_spare(d, "SPARE_FOR=\n")
    assert out.returncode == 0 and "SPARE_FOR=" in out.stdout.splitlines(), out.stderr  # the empty set is a set
    word64 = "a" * 64
    assert LABEL_WORD.fullmatch(word64) and not LABEL_WORD.fullmatch(word64 + "a")
    assert _run_spare(d, f"SPARE_FOR={word64}\n").returncode == 0
    for bad in ("vlan dmz", "$(touch x)", ",a", "a,", "a,,b", "-a", "a;b", "склад", word64 + "a", "a\tb"):
        out = _run_spare(d, f"SPARE_FOR={bad}\n")
        assert out.returncode == 2 and "is not a label set" in out.stderr and "-m " not in out.stdout, bad
    for said in (None, "LD_PRELOAD=x\n", "# SPARE_FOR=a\n"):
        out = _run_spare(d, said)
        assert out.returncode == 2 and "is not SPARE_FOR=" in out.stderr and "-m " not in out.stdout, said
    out = _run_spare(d, "SPARE_FOR=x\n", w2c_env=f"SPARE_FOR=from-a-shared-file\nSPARE_FILE={d}/other\n")
    assert out.returncode == 0 and "SPARE_FOR=x" in out.stdout.splitlines()
    regular = subprocess.run(["sh", os.path.join(DEPLOY, "w2c-run.sh"), "console"], capture_output=True, text=True,
                             env={"PATH": os.environ["PATH"], "W2C_ENV": os.path.join(d, "w2c.env"), "PYTHON": os.path.join(d, "python3"),
                                  "VMS_ENV": os.path.join(d, "none"), "W2C_HOME": d})
    assert regular.returncode == 0 and not [l for l in regular.stdout.splitlines() if l.startswith(("SPARE_FOR=", "SPARE_FILE="))]


def test_the_runner_runs_a_subsystems_package_by_its_name_and_nothing_else():
    """The platform's verbs are its own (`controller <sub>`, `console`, `resource`, `rights`: `python3 -m
    w2cplatform.cluster`); a subsystem's process is `w2c-run.sh <package> <verb>` — a package of the installed tree that
    has an entry point (`vms worker`), and not a module path, the platform's own package or a name with no entry point."""
    d = tempfile.mkdtemp(prefix="run-")
    os.makedirs(os.path.join(d, "Source", "vms"))
    open(os.path.join(d, "Source", "vms", "__main__.py"), "w").close()
    py = os.path.join(d, "python3")
    with open(py, "w") as f:
        f.write("#!/bin/sh\necho \"$@\"\n")
    os.chmod(py, 0o755)
    env = {"PATH": os.environ["PATH"], "PYTHON": py, "W2C_HOME": d, "W2C_ENV": os.path.join(d, "none"),
           "VMS_ENV": os.path.join(d, "none")}
    run = lambda *a: subprocess.run(["sh", os.path.join(DEPLOY, "w2c-run.sh"), *a], env=env, capture_output=True, text=True)  # noqa: E731
    assert run("vms", "worker").stdout.strip() == "-m vms worker"
    assert run("controller", "rec").stdout.strip() == "-m w2cplatform.cluster controller rec"
    for bad in (("w2cplatform", "console"), ("os.path", "x"), ("nope", "x"), ("../vms", "worker")):
        out = run(*bad)
        assert out.returncode == 2 and "no such program" in out.stderr and not out.stdout, bad


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


def test_the_spares_script_runs_as_the_platforms_user_whom_polkit_lets_start_a_spare_template_and_nothing_else():
    """The product's cross-check (4 Oct): the spares' timer ran its script as root. It runs as the platform's `w2c`
    (ADR 0030: every platform process is `w2c`, in no subsystem's group; there is no user of the spares' own) and joins
    no group in its unit — no store socket, no key — and the polkit rule `install.sh --spares` installs lets that user
    do one thing through systemd: `start`, of an instance of a spare
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
    assert not [l for l in users if l[1] == "w2c-spares"]                                 # no user of its own
    for f in sorted(os.listdir(M10)):
        if f.startswith("w2c-spares") and f.endswith(".service"):
            u = unit(os.path.join(M10, f))
            assert u["User"] == ["w2c"] and u["Group"] == ["w2c"] and "SupplementaryGroups" not in u, f
            assert u["RuntimeDirectory"] == ["w2c-spares"] and u["RuntimeDirectoryMode"] == ["0755"], f
    manage = "org.freedesktop.systemd1.manage-units"
    cases = [("w2c", manage, "start", "vms-vmsworker-spare@2.service", "yes"),
             ("w2c", manage, "start", "vms-recworker-spare@1.service", "yes"),
             ("w2c", manage, "stop", "vms-vmsworker-spare@2.service", "no"),
             ("w2c", manage, "restart", "vms-vmsworker-spare@2.service", "no"),
             ("w2c", manage, "reset-failed", "vms-vmsworker-spare@2.service", "no"),
             ("w2c", manage, "start", "vms-vmsworker.service", "no"),
             ("w2c", manage, "start", "vms-liveworker-spare@1.service", "no"),
             ("w2c", manage, "start", "vms-vmsworker-spare@.service", "no"),
             ("w2c", manage, "start", "vms-vmsworker-spare@1.service.d", "no"),
             ("w2c", manage, "start", "vms-recworker-spare@99.service", "yes"),          # the number: 1 to 99
             ("w2c", manage, "start", "vms-recworker-spare@100.service", "no"),          # (the thirteenth review)
             ("w2c", manage, "start", "vms-vmsworker-spare@99999999999999999999.service", "no"),
             ("w2c", manage, "start", "vms-vmsworker-spare@01.service", "no"),
             ("w2c", manage, "start", "sshd.service", "no"),
             ("w2c", manage, None, None, "no"),
             ("w2c", "org.freedesktop.systemd1.manage-unit-files", None, None, "no"),
             ("w2c", "org.freedesktop.systemd1.reload-daemon", None, None, "no"),
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
    files = {n.split("@", 1)[0] + "@" if "@" in n else n for n in listed}                 # an instance: its template's file
    assert sorted(f[:-len(".service")] for f in os.listdir(os.path.join(DEPLOY, "systemd")) if f.endswith(".service")) == sorted(files | set(spares))
    assert "rights --check" in src and "--spares" in src and "@BOXID@" in src


def _install_on_a_mac(*args: str, box_files=None) -> tuple[subprocess.CompletedProcess, str, str, list[str]]:
    """`install.sh` RUN on the macOS path: `uname` says Darwin, there is no `systemctl`, `launchctl` and `ioreg` are
    shims (the first writes its line down), `HOME` is the test's; the rest are the real tools. `(the process, the home,
    the shims' directory, launchctl's lines)`."""
    import shutil
    import sys
    bin_ = tempfile.mkdtemp(prefix="mac-")
    home = os.path.join(bin_, "home")
    os.makedirs(home)
    log = os.path.join(bin_, "calls")
    open(log, "w").close()
    shims = {"uname": "echo Darwin", "launchctl": f'echo "launchctl $*" >> "{log}"',
             "ioreg": 'echo \'    "IOPlatformUUID" = "0A1B2C3D-0000-1111-2222-333344445555"\''}
    for name, body in shims.items():
        with open(os.path.join(bin_, name), "w") as f:
            f.write(f"#!/bin/sh\n{body}\n")
        os.chmod(os.path.join(bin_, name), 0o755)
    for tool in ("sh", "cp", "mv", "rm", "mkdir", "chmod", "chgrp", "chown", "sed", "install", "id", "hostname",
                 "dirname", "basename", "cat"):
        os.symlink(shutil.which(tool), os.path.join(bin_, tool))
    env = {"PATH": bin_, "HOME": home, "PYTHON": sys.executable}
    out = subprocess.run(["/bin/sh", os.path.join(DEPLOY, "install.sh"), *args], env=env, capture_output=True,
                         text=True, timeout=120)
    return out, home, bin_, [l.strip() for l in open(log)]


def test_on_a_mac_the_box_is_a_directory_named_to_the_installer_and_everything_goes_under_it():
    """The thirteenth review, major 15: on macOS `install.sh` failed at `mkdir /data` — the root volume is read-only,
    there is no /data, and `synthetic.conf` was named nowhere. The decision aligned with the product: macOS REQUIRES
    `--box <dir>` (no default: refused without it), and everything goes under the box — the code and `bin/w2c-run.sh`,
    `w2c.env` and `vms.env` written from the examples with the box's places in them, `configstore-rights.json`,
    `secrets/` and `tls/` (0700, a bundle there handed to the user), `state/` — and the plists, `__BOX__` replaced, go
    to the user's `~/Library/LaunchAgents` and are bootstrapped into the user's launchd domain, not `system`. Nothing
    of /data, /etc/w2c or /etc/vms is named in what it wrote: those are Linux's. A box whose sockets' paths would not
    fit a unix socket is refused before anything is written."""
    import plistlib
    import shutil
    import stat
    out, home, bin_, calls = _install_on_a_mac()
    assert out.returncode == 2 and "--box <dir>" in out.stderr and calls == [], out.stderr
    long_box = os.path.join(bin_, "b" * 80)
    out, home, bin_, calls = _install_on_a_mac("--box", long_box)
    assert out.returncode == 2 and "too long" in out.stderr and not os.path.exists(long_box), out.stderr
    box = os.path.join(tempfile.mkdtemp(prefix="box-"), "box")
    os.makedirs(os.path.join(box, "tls"))
    for f in ("ca.pem", "server.pem", "server.key", "raft.secret"):
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__import__("vms").__file__)), "..", "tests", "tls",
                                 "srv-a", f), os.path.join(box, "tls", f))
        os.chmod(os.path.join(box, "tls", f), 0o644)
    out, home, bin_, calls = _install_on_a_mac("--box", box, "--spares")
    assert out.returncode == 0, out.stdout + out.stderr
    for p in ("bin/w2c-run.sh", "bin/w2c-spares.sh", "Source/vms/config.py", "Source/w2cplatform/cluster/rights.py",
              "configstore-rights.json", "state/configstore", "state/run/configstore", "state/logs", "state/events",
              "state/objects", "state/vms/obsd/volume"):
        assert os.path.exists(os.path.join(box, p)), p
    mode = lambda p: stat.S_IMODE(os.stat(os.path.join(box, p)).st_mode)        # noqa: E731
    assert mode("secrets") == mode("state/configstore") == 0o700 and mode("tls") == 0o750
    assert mode("tls/raft.secret") == mode("tls/server.key") == 0o600              # the bundle, the user's alone
    w2c, vms_ = open(os.path.join(box, "w2c.env")).read(), open(os.path.join(box, "vms.env")).read()
    assert f"PLATFORM_DIR={box}/state\n" in w2c and f"RESOURCE_ROOT={box}/state/events\n" in w2c and f"W2C_TLS={box}/tls\n" in w2c
    assert f"OBJECTS=cluster://{box}/state/objects?" in w2c
    assert f"ARCHIVE_VOLUME=file://{box}/state/vms/obsd/volume\n" in vms_ and f"SHM_DIR={box}/state/run/vms\n" in vms_
    agents = os.path.join(home, "Library", "LaunchAgents")
    labels = sorted(f[:-len(".plist")] for f in os.listdir(agents))
    assert labels == sorted(f[:-len(".plist")] for f in os.listdir(os.path.join(DEPLOY, "launchd")) if f.endswith(".plist"))
    uid = os.getuid()
    for label in labels:
        raw = open(os.path.join(agents, f"{label}.plist")).read()
        assert "__BOX__" not in raw and "@HOST@" not in raw and "@BOXID@" not in raw, label
        p = plistlib.loads(raw.encode())
        assert p["ProgramArguments"][0] == f"{box}/bin/w2c-run.sh" and p["EnvironmentVariables"]["W2C_BOX"] == box, label
        assert f"launchctl bootstrap gui/{uid} {agents}/{label}.plist" in calls, (label, calls)
    for text in [w2c, vms_] + [open(os.path.join(agents, f)).read().split("-->", 1)[1] for f in os.listdir(agents)]:
        assert not [w for w in ("/data/", "/etc/w2c", "/etc/vms", "/var/run", "/opt/w2c") if w in text], text
    assert not [c for c in calls if " system" in c], calls


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
    named = [f[:-len(".service")] for f in sorted(os.listdir(SYSTEMD)) if f.endswith(".service") and not f.endswith("@.service")
             or f.endswith("-spare@.service")] + [n for n in UNITS if "@" in n]       # a template by its instances
    for n in named:
        u = service(n)
        joined = set(" ".join(u.get("SupplementaryGroups", [])).split()) | set(u.get("Group", []))
        assert joined <= groups, (n, joined - groups)
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
    that open a password — the console, the holder, the recorder — and no other. A platform process (`User=w2c`: the
    resource, the console, every controller) joins no subsystem's group (ADR 0023); the console writes its marks into
    the events archive as its owner, `w2c`, and joins no `w2c-events` — that group is the resource's and the
    subsystems' writers'."""
    events = {"w2c-resource", "vms-vmsworker", "vms-recworker"}
    writes_events = events | {"w2c-console"}
    secrets = {"w2c-console", "vms-vmsworker", "vms-recworker"}
    for f in sorted(os.listdir(SYSTEMD)):
        if not f.endswith(".service"):
            continue
        name = f[:-len(".service")].replace("-spare@", "")
        u = unit(os.path.join(SYSTEMD, f))
        assert u["UMask"] == (["0077"] if name == "configstore" else ["0007"]) and u["ProtectSystem"] == ["strict"], f
        assert u["ProtectHome"] == ["yes"] and u["PrivateTmp"] == ["yes"] and u["NoNewPrivileges"] == ["yes"], f
        if name == "configstore":
            assert u["ReadWritePaths"] == ["/data/platform/configstore"]
            continue
        joined = set(u["SupplementaryGroups"][0].split())
        writes = set(u["ReadWritePaths"][0].split())
        assert "w2c-store" in joined and "/data/platform/objects" in writes, f
        assert ("w2c-events" in joined) == (name in events), f
        assert ("/data/platform/events" in writes) == (name in writes_events), f
        assert ("w2c-secrets" in joined) == (name in secrets) == ("LoadCredential" in u), f
        if u["User"] == ["w2c"]:
            assert not [g for g in joined if g.startswith("vms")], f                       # no subsystem's group
            assert u["Group"] == ["w2c"], f


def test_a_spare_is_its_roles_unit_line_for_line_but_the_name():
    """The twelfth review, blocker 6 (the owner's decision: a spare has the regular unit's credentials, keys, environment,
    user and groups): `vms-<role>-spare@.service`, which `w2c-spares.sh` starts, is its role's unit with only these
    differences — no `WORKER_NAME`; a worker's set from its one-line file (`SPARE_FILE`, of which the runner reads
    `SPARE_FOR=` alone: no set, no start) and its fan-out on a port the OS gives; a recorder's door likewise. Nothing
    else may differ, so a line given to the role is given to its spares or this fails. And no `EnvironmentFile=` in a
    spare either (the product's cross-check, 4 Oct): a file read whole is every variable its writer wants."""
    # …and what a spare depends on (the thirteenth review, major 12): what its role's unit is ordered after, a spare
    # `Requisite=`s, up already or the spare does not start; and a worker spare whose set is refused (exit 2) is not
    # restarted (the same review, minor).
    allowed = {"vms-vmsworker": {("env", "WORKER_NAME"), ("env", "RTSP_PORT"), ("env", "SPARE_FILE"), ("Description",),
                                 ("WantedBy",), ("Requisite",), ("RestartPreventExitStatus",)},
               "vms-recworker": {("env", "WORKER_NAME"), ("env", "ARCHIVE_PORT"), ("Description",), ("WantedBy",),
                                 ("Requisite",)}}
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


def test_no_unit_starts_what_it_depends_on_and_a_refused_set_is_not_restarted():
    """The thirteenth review, major 12: the spare templates said `Wants=configstore.service vms-obsd.service`, so the
    spares' timer starting a spare made PID 1 start a stopped engine — the administrator stops it to hand the volumes
    over (`install-obsd.sh`, its `chown -R`) — past polkit. And the product's r28-ops2, the same in the ROLE units: the
    console, the two controllers, the worker and the resource said `Wants=configstore.service`, the recorder
    `Wants=… vms-obsd.service` — any restart of one (its own crash, `Restart=always`) started the store's member or the
    engine the administrator had stopped. Every unit is enabled on its own (`WantedBy=multi-user.target`, `install.sh`),
    so boot needs no `Wants=`: a role unit is ORDERED after what it uses (`After=`) and wants nothing but the network
    target. No role needs `Requisite=` either: each outlives its store (a worker records past its lease's end,
    its spec's `lease.unconfirmed_max`) and the recorder its engine (`away`, then `remounted`), and `Requisite=`
    would stop them with it.
    A spare `Requisite=`s the store's member — and a recorder's spare the engine —: up already, or it does not start.
    And the minor: a worker spare whose set its runner refuses ends 2 at every start — no restart."""
    for f in sorted(os.listdir(SYSTEMD)):
        if not f.endswith(".service"):
            continue
        u = unit(os.path.join(SYSTEMD, f))
        assert u.get("Wants", ["network-online.target"]) == ["network-online.target"], f
        assert "Requires" not in u and "BindsTo" not in u, f
        after = u["After"][0].split()
        if f != "configstore.service":
            assert "configstore.service" in after, f                         # ordered after the store's member…
        if f.startswith("vms-recworker"):
            assert "vms-obsd.service" in after, f                            # …and the recorder after the engine
        requisite = u.get("Requisite", [""])[0].split()
        assert requisite == ((["configstore.service", "vms-obsd.service"] if f.startswith("vms-recworker") else
                              ["configstore.service"]) if "-spare@" in f else []), f
        assert set(requisite) <= set(after), f
    assert unit(os.path.join(SYSTEMD, "vms-vmsworker-spare@.service"))["RestartPreventExitStatus"] == ["2"]


def test_the_stores_journal_is_its_members_alone_however_it_was_started():
    """The product's r28-ops2: `configstore.service` said `UMask=0007`, the box's rule for what a role writes into the
    shared archive and objects — and the store's member wrote its raft journal and snapshots 0660, the rows readable by
    whoever joins its group, past the rights file. Its journal is its own: `UMask=0077` in the unit, `Umask` 63 in the
    plist, and the runner sets 0077 itself for the store's member (it sets 0007 for every other program, the thirteenth
    review's major 13 — and would have undone the unit's). The directory is 0700 on a Mac box as on Linux."""
    assert unit(os.path.join(SYSTEMD, "configstore.service"))["UMask"] == ["0077"]
    with open(os.path.join(DEPLOY, "launchd", "com.w2c.configstore.plist"), "rb") as f:
        assert plistlib.load(f)["Umask"] == 0o077
    d = tempfile.mkdtemp(prefix="run-")
    py = os.path.join(d, "python3")
    with open(py, "w") as f:
        f.write("#!/bin/sh\necho \"umask=$(umask)\"\n")
    os.chmod(py, 0o755)
    with open(os.path.join(d, "w2c.env"), "w") as f:
        f.write("SERVER_NAME=a\nCONFIGSTORE_RAFT=127.0.0.1:8301\nCONFIGSTORE_API=127.0.0.1:8300\n")
    env = {"PATH": os.environ["PATH"], "PYTHON": py, "W2C_BOX": d}
    for program, mask in (("configstore", ("0077", "077")), ("console", ("0007", "007"))):
        out = subprocess.run(["sh", os.path.join(DEPLOY, "w2c-run.sh"), program], env=env, capture_output=True,
                             text=True, check=True, preexec_fn=lambda: os.umask(0o022)).stdout
        assert out.strip().split("=", 1)[1] in mask, (program, out)
    script = open(os.path.join(DEPLOY, "install.sh"), encoding="utf-8").read()
    assert 'chmod 0700 "$BOX/state/configstore"' in script


# The spellings that differ between the two supervisors and nothing else: on macOS everything is under the box
# (`__BOX__`, the thirteenth review, major 15) — its sockets under `state/run/`, the key read where it lies in
# `secrets/` (no credentials directory) — and there is no %l and no %m (`install.sh` puts @HOST@ and @BOXID@).
def _as_launchd(value: str) -> str:
    return (value.replace("/run/", "__BOX__/state/run/").replace("%d/platform.key", "__BOX__/secrets/platform.key")
            .replace("%l", "@HOST@").replace("%m", "@BOXID@"))


def test_every_plist_says_what_its_unit_says_name_for_name():
    """The twelfth review, major 12: the plists had drifted — no `SECRETS_KEY` for the console, the worker and the
    recorder (the console on macOS stored passwords in the clear), no `OBSD_SOCKET` or `BOX_ID` for the recorder. Each
    plist's environment is its unit's, the same names and the same values but for the supervisors' own spellings."""
    for label, name in PLISTS.items():
        with open(os.path.join(DEPLOY, "launchd", f"{label}.plist"), "rb") as f:
            p = plistlib.load(f)
        u = service(name)
        assert p["EnvironmentVariables"] == {"W2C_BOX": "__BOX__", **{k: _as_launchd(v) for k, v in u["env"].items()}}, label


def test_the_worker_and_the_recorder_tell_systemds_watchdog_that_their_loop_turns():
    """The twelfth review, major 14: lesson 8 promised a watchdog and there was none — a hung worker held its cameras
    the whole fifteen minutes. The worker's and the recorder's units say `WatchdogSec` — longer than the stand-in holds
    a hung step (`STAND_IN_FOR`), shorter than a hung worker keeps its cameras (`HUNG_MOVE_AFTER`) — and the loop says
    `WATCHDOG=1` to `$NOTIFY_SOCKET` at every turn: here a socket of the test's, two turns of a real loop, two
    datagrams. With no socket nothing is sent and nothing fails."""
    import socket
    import threading
    from w2cplatform.runtime import notify
    from w2cplatform.contract import HUNG_MOVE_AFTER
    from w2cplatform.worker import Worker
    from tests.cluster.conftest import Cluster
    for name in ("vms-vmsworker", "vms-recworker", "vms-vmsworker-spare@", "vms-recworker-spare@"):
        u = unit(os.path.join(SYSTEMD, f"{name}.service"))
        sec = float(u["WatchdogSec"][0])
        assert Worker.STAND_IN_FOR < sec < HUNG_MOVE_AFTER, name
        # the product's units (4 Oct): the main process may notify, and `simple` — under `notify` a spare waiting for
        # an offer, which says nothing until it is somebody, would hold `systemctl start` and the script behind it
        assert sec == 360 and u["Type"] == ["simple"] and u["NotifyAccess"] == ["main"], name
    d = tempfile.mkdtemp(prefix="notify-")
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
    key, and the box's events and objects. The console's task is the platform's and runs as `w2c` (ADR 0023), a
    member of its socket's group and the key ring's, and of no subsystem's group."""
    import re
    lines = _sysusers(os.path.join(DEPLOY, "nomad", "vms-nomad.sysusers"))
    member = {u: {l[2] for l in lines if l[:2] == ["m", u]} for u in ("vms", "w2c")}
    rights = json.load(open(RIGHTS, encoding="utf-8"))["roles"]
    for job, user in (("console", "w2c"), ("vmsworker", "vms"), ("recworker", "vms")):
        src = open(os.path.join(DEPLOY, "nomad", f"{job}.nomad.hcl"), encoding="utf-8").read()
        assert re.search(r'\buser\s*=\s*"' + user + '"', src), job
        role = re.search(r'configstore:///run/configstore/(\w+)\.sock', src).group(1)
        assert rights[role]["group"] in member[user], job
        if "SECRETS_KEY" in src:
            assert "w2c-secrets" in member[user], job
        if "OBSD_SOCKET" in src:
            assert "vms-obsd" in member[user], job
    assert {"w2c-events", "w2c-store"} <= member["vms"]
    assert not [g for g in member["w2c"] if g.startswith("vms")]                           # no subsystem's group
    tmp = {l.split()[1]: l.split()[2:5] for l in open(os.path.join(SYSTEMD, "w2c-cluster.tmpfiles")) if l.startswith("d ")}
    assert tmp["/data/platform/etc/secrets"] == ["2710", "root", "w2c-secrets"]
