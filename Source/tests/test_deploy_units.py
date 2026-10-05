"""Lesson 10 — what runs on М9's box: the three processes and the policy pass as
Quadlet units over one image, on the data partition. No podman here (the
generator's dry-run is deploy/check-quadlet.sh, for the bench); this checks
that the units and the Containerfile agree with the package they run."""
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY = os.path.join(HERE, "deploy")


def unit(name):
    """A unit file as {section: {key: value or [values]}} — systemd keys repeat (Volume=, Environment=), configparser's do not."""
    out, sec = {}, None
    for line in open(os.path.join(DEPLOY, name)):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            sec = line.strip("[]"); out[sec] = {}
        else:
            k, v = line.split("=", 1)
            out[sec].setdefault(k, []).append(v)
    return {sec: {k: (v[0] if len(v) == 1 else v) for k, v in kv.items()} for sec, kv in out.items()}


# The box's layout (the owner's decisions, 4 October): the platform's state under /data/platform — its two stores and
# its events archive — and its key ring under /etc/w2c, a link into /data/platform/etc.
CONFIG, OBJECTS, EVENTS = "/data/platform/config", "/data/platform/objects", "/data/platform/events"
KEY = "/etc/w2c/secrets/platform.key"
# The numbers the containers run as and join by (`w2c.sysusers`, `obsd.sysusers`).
W2C, W2C_EVENTS, W2C_STORE, W2C_SECRETS, VMS_OBSD = "2100", "2102", "2103", "2104", "2101"


def _list(v):
    return v if isinstance(v, list) else [] if v is None else [v]


def test_the_units_run_the_entrypoints_the_package_has():
    """The VMS's verbs (`python3 -m vms`: its workers, and its housekeeping, `jobs`) and the platform's (`python3 -m
    w2cplatform controller <sub>`: every subsystem's controller, the VMS's included since the boundary's step 6, from
    the spec the image carries in `SPEC_DIR`; `resource`; `console`, the VMS's at `/` by the unit's `CONSOLE_ROOT`).
    Each unit runs one, and each verb is a unit's."""
    from vms import __main__ as m  # noqa: F401  (imports the module without running it: no __name__ == "__main__")
    from w2cplatform import host
    entrypoints = set(re.findall(r'"(\w+)": \w+', open(os.path.join(HERE, "vms", "__main__.py")).read().split("__main__")[-1]))
    assert entrypoints == {"worker", "recorder", "gateway", "detworker", "detjobworker", "surveyworker", "autoworker",
                           "jobs", "domainpart"}
    # `domainpart` is the domain holder's, not a box's: its unit is `deploy/domain/systemd/vms-domainpart.service`
    assert "w2c-run.sh vms domainpart" in open(os.path.join(HERE, "deploy", "domain", "systemd", "vms-domainpart.service")).read()
    platform = {"vmscontroller.container": "vms", "reccontroller.container": "rec", "livecontroller.container": "live", "detcontroller.container": "det",
                "detjobcontroller.container": "detjob", "surveycontroller.container": "survey",
                "autocontroller.container": "auto"}
    image = open(os.path.join(DEPLOY, "Containerfile")).read()
    assert "ENV SPEC_DIR=/app/vms" in image and "COPY vms vms" in image                # the specs the image carries
    assert "controller <sub>" in host.USAGE and "console" in host.USAGE
    for name, entry in [("vmsworker@.container", "worker"), ("w2c-resource.container", "resource"),
                        ("console.container", "console"), ("vmsjobs.container", "jobs"),
                        ("recworker@.container", "recorder"), ("liveworker@.container", "gateway"),
                        ("detworker@.container", "detworker"), ("detjobworker@.container", "detjobworker"),
                        ("surveyworker@.container", "surveyworker"), ("autoworker@.container", "autoworker"),
                        *platform.items()]:
        u = unit(name)
        assert u["Container"]["Image"] == "localhost/vmsserver:latest"                 # one image, one thing to publish
        if name == "w2c-resource.container":
            assert u["Container"]["Exec"] == "python3 -m w2cplatform resource"         # the platform's own (step 6)
        elif name == "console.container":
            assert u["Container"]["Exec"] == "python3 -m w2cplatform console"          # the platform's own (step 6)
            assert "CONSOLE_ROOT=vms" in u["Container"]["Environment"]                 # the deployment says what is at `/`
        elif name in platform:
            assert u["Container"]["Exec"] == f"python3 -m w2cplatform controller {entry}"
            assert os.path.exists(os.path.join(HERE, "vms", f"{entry}.subsystem.yaml"))   # what `SPEC_DIR` gives it
        else:
            assert u["Container"]["Exec"] == f"python3 -m vms {entry}"
        # /etc/w2c and /etc/vms, links into the data partition; the platform's half first, the VMS's after it
        assert u["Container"]["EnvironmentFile"] == ["/etc/w2c/w2c.env", "/etc/vms/vms.env"]
        for vol in (u["Container"]["Volume"] if isinstance(u["Container"]["Volume"], list) else [u["Container"]["Volume"]]):
            assert vol.startswith(("/data/", "/run/vms:", "/run/vms-obsd:", "/run/vms-console:",   # sockets on a tmpfs, not state
                                   f"{KEY}:")), vol                                              # the key ring: one file


def test_who_may_write_where_is_in_the_mounts_too():
    """The ACL says which rows each token writes; the mounts say which bytes.
    The controller has no archive at all; footage is mounted nowhere — it is behind the host's obsd."""
    vols = lambda n: dict(v.split(":", 1) for v in (lambda x: x if isinstance(x, list) else [x])(unit(n)["Container"]["Volume"]))
    assert EVENTS not in vols("vmscontroller.container")
    for n in os.listdir(DEPLOY):
        if n.endswith(".container"):
            assert "/data/spool" not in vols(n), n                                       # there is no spool: footage goes through obsd
            # the two stores, never /data/platform whole: its etc/secrets holds the key ring
            assert "/data/platform" not in vols(n) and not any(v.startswith("/data/platform/etc") for v in vols(n)), n
    assert vols("vmsworker@.container")[EVENTS] == f"{EVENTS}:z"                       # its events, vms/<cam>/, on this box's resource
    assert vols("vmsworker@.container")["/data/media"].endswith(":ro,z")
    assert vols("recworker@.container")[EVENTS] == f"{EVENTS}:z"                      # its events; its volume is the daemon's
    assert "/data/media" not in vols("recworker@.container")                          # it never reads a camera: it subscribes to the fan-out
    assert vols("vmsworker@.container")["/run/vms"] == "/run/vms:z" == vols("recworker@.container")["/run/vms"]   # the tee's shared memory
    # the daemon's socket: the recorder's alone, never the holder's — the process with a vendor's DriverPack in it
    for n in os.listdir(DEPLOY):
        if n.endswith(".container"):
            assert ("/run/vms-obsd" in vols(n)) == (n == "recworker@.container"), n
    rec_env = dict(e.split("=", 1) for e in unit("recworker@.container")["Container"]["Environment"])
    assert rec_env["OBSD_SOCKET"] == "/run/vms-obsd/obsd.sock" and rec_env["SECRETS_KEY"] == "/run/secrets/platform.key"   # it opens a volume's secret
    assert EVENTS not in vols("reccontroller.container")
    assert vols("w2c-resource.container")[OBJECTS] == f"{OBJECTS}:z"                  # the heartbeat is written, and its door's row
    assert unit("recworker@.container")["Container"]["StopTimeout"] == "40"          # the writer's close waits for its flush (30 s)
    assert "obsd.service" in unit("recworker@.container")["Unit"]["After"]
    # …ordered after the host's engine, never starting it (the product's r28-ops2): a restart of a recorder — its crash,
    # `Restart=always` — started the obsd the administrator had stopped to hand the volumes over. No unit wants another.
    for n in os.listdir(DEPLOY):
        if n.endswith((".container", ".service")):
            assert "Wants" not in unit(n).get("Unit", {}) or unit(n)["Unit"]["Wants"] in ("network-online.target",), n
    assert unit("w2c-resource.container")["Service"]["Restart"] == "always"         # a process, not a timer: the database lives in it


def test_the_image_carries_the_three_packages_and_nothing_else():
    cf = "\n".join(l for l in open(os.path.join(DEPLOY, "Containerfile")) if not l.startswith("#"))   # the instructions, not the notes
    copied = re.findall(r"^COPY (\S+) ", cf, re.M)
    assert copied == ["w2cplatform", "vms", "gstvms"]
    assert "postgres" not in cf.lower()                                                # the per-box database is gone (М10 Lesson 1)
    assert 'CMD ["python3", "-m", "vms", "worker"]' in cf
    env = open(os.path.join(DEPLOY, "vms.env.example")).read()
    platform = open(os.path.join(DEPLOY, "w2c.env.example")).read()
    assert "PLATFORM_DIR=/data/platform" in platform and f"RESOURCE_ROOT={EVENTS}" in platform   # the events archive is the platform's
    assert "CAPACITY=" in env
    assert "SPOOL=" not in env and "SEGMENT_SECONDS=" not in env


def _env_names(name: str) -> set:
    """The variables an env example sets or offers (`NAME=` at the start of a line, commented out or not)."""
    return set(re.findall(r"^#? ?([A-Z][A-Z0-9_]*)=", open(os.path.join(DEPLOY, name)).read(), re.M))


def test_the_platforms_settings_and_the_vmss_are_two_files_every_unit_reads():
    """The product's rule on the platform's names (3 October): the platform is w2c, the VMS one of its subsystems, and
    `/etc/vms/vms.env` split into the platform's `w2c.env` — its directory, its events archive, its store, the
    server's name, labels, box id — and the VMS's `vms.env`. Since the owner's decision of 4 October the course's
    box has the product's paths too, `/etc/w2c` and `/etc/vms` being links into its data partition. Every unit reads
    both, the platform's first (checked per unit above); the spares' units read them too; and each name is in its own
    half and only there — `RESOURCE_ROOT` the platform's."""
    platform, vms = _env_names("w2c.env.example"), _env_names("vms.env.example")
    assert {"PLATFORM_DIR", "RESOURCE_ROOT", "PLATFORM_STORE", "SERVER_NAME", "LABELS", "BOX_ID"} <= platform
    assert {"CAPACITY", "MEDIA_DIR", "SHM_DIR", "OBSD_SOCKET", "ARCHIVE_VOLUME"} <= vms
    assert not platform & vms, platform & vms
    for n in os.listdir(DEPLOY):
        if n.startswith("w2c-spares") and n.endswith(".service"):
            assert unit(n)["Service"]["EnvironmentFile"] == ["-/etc/w2c/w2c.env", "-/etc/vms/vms.env"], n
    # the cluster's key ring: one file of the platform's, in the three units that open sealed fields and no other
    keyed = {n for n in os.listdir(DEPLOY) if n.endswith(".container")
             and "SECRETS_KEY=/run/secrets/platform.key" in unit(n)["Container"].get("Environment", [])}
    assert keyed == {"console.container", "vmsworker@.container", "recworker@.container"}, keyed
    for n in keyed:
        assert f"{KEY}:/run/secrets/platform.key:ro,z" in unit(n)["Container"]["Volume"], n
        assert W2C_SECRETS in _list(unit(n)["Container"]["GroupAdd"]), n                 # 0640, its group: the clients of the key
    assert unit("w2c-resource.container")["Unit"]["Description"].startswith("w2c ")   # the platform's process


def test_the_archives_engine_is_the_hosts_own_daemon():
    """One obsd per host, not a container of the image: it keeps one writer per volume, and that means something
    only if every recorder on the box asks the same one. Its socket is where the recorder already looks."""
    from vms.obsd import default_socket
    u = unit("obsd.service")
    assert u["Service"]["ExecStart"] == "/usr/local/bin/obsd --socket /run/vms-obsd/obsd.sock"
    assert u["Service"]["RuntimeDirectory"] == "vms-obsd" and u["Service"]["RuntimeDirectoryPreserve"] == "yes"
    assert u["Service"]["RuntimeDirectoryMode"] == "0750"                              # its group gets in; the daemon's own 0700 would not let it
    env = dict(e.split("=", 1) for e in u["Service"]["Environment"])
    assert int(env["OBSD_WRITER_GRACE_S"]) > 45                                         # the writer outlasts a hold that lapses
    assert u["Service"]["User"] == "vms-obsd" and env["OBSD_CLIENT_GROUP"] == u["Service"]["Group"]   # its own user; the recorders' group
    import sys
    from unittest import mock
    with mock.patch.dict(os.environ, {"OBSD_SOCKET": ""}), mock.patch.object(sys, "platform", "linux"):
        assert default_socket() == "/run/vms-obsd/obsd.sock"                            # where the unit puts it: the product's path
    with mock.patch.dict(os.environ, {"OBSD_SOCKET": ""}), mock.patch.object(sys, "platform", "darwin"):
        assert default_socket() == f"/tmp/vms-obsd-{os.getuid()}.sock"                 # the daemon's own default on macOS


def test_a_session_named_by_nobody_says_its_process_name_and_not_a_subsystems():
    """The client is the platform's library, and a session its caller did not name said `vms` in HELLO and in its
    token, whatever the process (the course's decision on the platform's names). Now it is the process's name:
    `python3 -m vms recorder` is `vms`, `tests/run.py` is `run`; a caller that names itself is said as it named."""
    import sys
    from unittest import mock
    from vms.obsd import Session, process_name
    with mock.patch.object(sys, "argv", ["/usr/lib/python3/site-packages/vms/__main__.py", "recorder"]):
        assert process_name() == "vms"
    with mock.patch.object(sys, "argv", ["/srv/w2c/tests/run.py"]):
        assert process_name() == "run" and Session("/nonexistent/obsd.sock").client == "run"
        assert Session("/nonexistent/obsd.sock").token.startswith("run-")
    with mock.patch.object(sys, "argv", [""]):
        assert process_name() == "python"
    assert Session("/nonexistent/obsd.sock", client="rec-r-1").client == "rec-r-1"


def _sysusers() -> tuple[dict, dict, set]:
    """`obsd.sysusers` and `w2c.sysusers` as ({user: uid}, {group: gid}, {(user, group)}) — a user's primary group
    counted as one it is in: `u <name> -:<group>`, or `u <name> <n>`, which makes the group of its name with the same
    number."""
    users, groups, members = {}, {}, set()
    for name in ("obsd.sysusers", "w2c.sysusers"):
        for line in open(os.path.join(DEPLOY, name)):
            f = line.split()
            if not f or f[0].startswith("#"):
                continue
            if f[0] == "u":
                users[f[1]] = f[2].split(":", 1)[0]
                if ":" in f[2]:
                    members.add((f[1], f[2].split(":", 1)[1]))
                elif f[2].isdigit():
                    groups[f[1]] = f[2]; members.add((f[1], f[1]))
            elif f[0] == "g":
                groups[f[1]] = f[2]
            elif f[0] == "m":
                members.add((f[1], f[2]))
    return users, groups, members


def _tmpfiles(*names: str) -> dict:
    """`w2c.tmpfiles` and `vms.tmpfiles` (or the ones named) as {path: (type, mode, user, group)}."""
    out = {}
    for name in names or ("w2c.tmpfiles", "vms.tmpfiles"):
        for line in open(os.path.join(DEPLOY, name)):
            f = line.split()
            if f and not f[0].startswith("#"):
                out[f[1]] = (f[0], f[2], f[3], f[4])
    return out


def test_every_user_group_and_directory_a_unit_names_is_made_by_the_install_files():
    """The review's fourth pass, blocker 2. `obsd.service` ran as a user nobody created and owned a volume nobody
    handed it; /run/vms was made only by that unit, so without the daemon neither the holder nor the recorder started.
    Every user and group a unit names is in `obsd.sysusers` — the clients' group with the number the recorders join it
    by — every host directory under /run a container mounts is in `vms.tmpfiles`, the box's own volume is the daemon's,
    and `install-obsd.sh` installs both files, checks the number and hands an old ring over. Since the platform's names
    (3 October): the platform's directories — its stores, its secrets — are `w2c.tmpfiles`, installed beside it, and
    the daemon's user and group are the product's `vms-obsd`. Since the owner's decisions of 4 October: the platform's
    state is under /data/platform, its configuration in its etc/ (/etc/w2c, a link), its key ring 0640 to the group
    `w2c-secrets` in a directory the group may pass and not list; the VMS's under /data/vms, the box's own volume in
    /data/vms/obsd; the platform's user and its clients' groups in `w2c.sysusers`, each with the number the units
    run as and join by."""
    w2c = _tmpfiles("w2c.tmpfiles")
    assert w2c == {"/data/platform": ("d", "0755", "root", "root"), "/data/platform/etc": ("d", "0755", "root", "root"),
                   "/data/platform/etc/secrets": ("d", "2710", "root", "w2c-secrets"),
                   CONFIG: ("d", "2770", "w2c", "w2c-store"), OBJECTS: ("d", "2770", "w2c", "w2c-store"),
                   EVENTS: ("d", "2770", "w2c", "w2c-events")}, w2c
    assert os.path.dirname(KEY) == "/etc/w2c/secrets"                                     # = /data/platform/etc/secrets
    assert not any(p.startswith("/data/platform") for p in _tmpfiles("vms.tmpfiles"))
    users, groups, members = _sysusers()
    assert (users["w2c"], groups["w2c"], groups["w2c-events"], groups["w2c-store"], groups["w2c-secrets"]) == \
        (W2C, W2C, W2C_EVENTS, W2C_STORE, W2C_SECRETS)
    assert {("w2c", "w2c-events"), ("w2c", "w2c-store")} <= members                       # its archive's clients, its stores
    dirs = _tmpfiles()
    svc = unit("obsd.service")["Service"]
    assert svc["User"] in users and svc["Group"] in groups and (svc["User"], svc["Group"]) in members
    rec = unit("recworker@.container")["Container"]
    assert groups[svc["Group"]] == VMS_OBSD and VMS_OBSD in _list(rec["GroupAdd"])       # the number the container joins by
    for n in os.listdir(DEPLOY):
        if not n.endswith(".container"):
            continue
        vols = unit(n)["Container"].get("Volume", [])
        for v in vols if isinstance(vols, list) else [vols]:
            host = v.split(":", 1)[0]
            if host.startswith("/run/"):
                assert host in dirs, f"{n} mounts {host}, which nothing makes before it starts"
    sock_dir = os.path.dirname(svc["ExecStart"].split("--socket", 1)[1].strip())
    assert dirs[sock_dir] == ("d", svc["RuntimeDirectoryMode"], svc["User"], svc["Group"])   # the same as the unit makes it
    from vms.config import OWN_VOLUME
    own = OWN_VOLUME[len("file://"):]                                                     # the box's own volume: the VMS's
    assert own.startswith("/data/vms/obsd/") and dirs[own][2:] == (svc["User"], svc["Group"])   # the daemon opens it, as itself
    assert dirs[os.path.dirname(own)][2:] == (svc["User"], svc["Group"])
    script = open(os.path.join(DEPLOY, "install-obsd.sh")).read()
    for needed in ("obsd.sysusers", "w2c.sysusers", "systemd-sysusers", "w2c.tmpfiles", "vms.tmpfiles",
                   "systemd-tmpfiles --create", f'"$GID" != {VMS_OBSD}', f"passwd w2c {W2C}", f"group w2c-events {W2C_EVENTS}",
                   f"group w2c-store {W2C_STORE}", f"group w2c-secrets {W2C_SECRETS}",
                   f"chown -R {svc['User']}:{svc['Group']}", own.replace("/data/", '$R/data/', 1),
                   'link_etc "$R/etc/w2c" "$R/data/platform/etc"', 'link_etc "$R/etc/vms" "$R/data/vms/etc"',
                   "obsd.service", "systemctl enable obsd.service", "systemctl restart obsd.service"):
        assert needed in script, needed
    assert os.access(os.path.join(DEPLOY, "install-obsd.sh"), os.X_OK)


def _may(path: str, uid: int, gids: set, need: int) -> bool:
    """What the kernel answers a process of `uid` in `gids` (not root) asking `need` (r=4, w=2, x=1) of `path`: the
    owner's bits if it is the owner, else the group's if it is in the group, else the others'."""
    import stat
    st = os.stat(path)
    bits = st.st_mode >> 6 if st.st_uid == uid else st.st_mode >> 3 if st.st_gid in gids else st.st_mode
    return bits & need == need and not (need & 2 and st.st_mode & stat.S_ISVTX and st.st_uid != uid)


def _may_unlink(path: str, uid: int, gids: set) -> bool:
    """An entry goes if its directory lets the caller write and search it (the file's own mode does not matter)."""
    return _may(os.path.dirname(path), uid, gids, 3)


def test_the_resource_as_w2c_deletes_a_bucket_a_client_of_w2c_events_wrote():
    """The owner's decision (4 October): the events archive is the platform's, the resource runs as `w2c`, and a
    subsystem writes its buckets as a CLIENT — a member of `w2c-events`, with the umask 0007 its unit sets, into a tree
    setgid to that group (`w2c.tmpfiles`: 2770 `w2c:w2c-events`). There is no second uid here without root, so the
    claim is the modes, checked as the kernel would for a process of ANOTHER uid whose only tie to the tree is that
    group: a client writes a camera's events and a recorder's under the umask 0007 into such a tree, and every
    directory it made is the tree's group with rwx for it (and setgid, where the kernel passes it on), every file the
    group's with rw — so that process may unlink every bucket and read every line; and the resource's retention
    removes the old one. Under the old umask, 0022, the same check says it could not: the umask is half the rule."""
    import stat
    import sys
    import tempfile
    from vms.archive import event_log
    from w2cplatform.resource import platform_resource
    from w2cplatform import runtime
    from w2cplatform.events import EventLog
    from tests.vmsconftest import Box
    group = (set(os.getgroups()) - {os.getgid()} or {os.getgid()}).pop()   # a group this process is in, not its own if it can
    resource = (os.getuid() + 1, {group})                                    # another uid; the group its only tie

    def tree(umask: int):
        events = os.path.join(tempfile.mkdtemp(prefix="platform-"), "events")
        os.mkdir(events)
        os.chown(events, -1, group)
        os.chmod(events, 0o2770)
        assert runtime.events_root({"PLATFORM_DIR": os.path.dirname(events)}) == events   # the default, said once
        was = os.umask(umask)                                                # the client's unit: `--umask=…`
        try:
            event_log(events, 7, 1).append(box.wall() - 3 * 86400, "motion")  # past a day's retention
            event_log(events, 7, 1).append(box.wall() - 100, "motion")
            EventLog(events, "rec", "1", 1, 600).append(box.wall() - 100, "archive.shallow")
        finally:
            os.umask(was)
        dirs, files = [], []
        for d, ds, fs in os.walk(events):
            dirs += [os.path.join(d, x) for x in ds]
            files += [os.path.join(d, x) for x in fs]
        return events, dirs, files

    box = Box()
    events, dirs, files = tree(0o007)
    assert len(files) == 3 and dirs
    for d in dirs:
        st = os.stat(d)
        assert st.st_gid == group and st.st_mode & 0o070 == 0o070, (d, oct(st.st_mode))
        if sys.platform.startswith("linux"):
            assert st.st_mode & stat.S_ISGID, d                              # Linux passes setgid on to a new directory
        assert _may(d, *resource, 7), d
    for f in files:
        st = os.stat(f)
        assert st.st_gid == group and st.st_mode & 0o060 == 0o060, (f, oct(st.st_mode))
        assert _may_unlink(f, *resource) and _may(f, *resource, 4), f
    res = platform_resource(events, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall)
    box.vars.put("vms/retention/7", {"days": "1"})
    assert res.retain() == 1                                                 # the resource deletes the client's old bucket
    assert sum(1 for f in files if os.path.exists(f)) == 2
    _, _, old = tree(0o022)                                                  # the box's units before: every process root
    assert not all(_may_unlink(f, *resource) for f in old)                   # …and a resource of another uid could not


def test_a_platform_stores_files_are_its_groups_under_the_units_umask():
    """`w2c-store` (the owner's decision, 4 October): the platform's file stores are shared by group, and the resource —
    `w2c`, not root — reads the heartbeats and rows other processes write, takes the rows' lock and writes its own.
    An object was written through `tempfile.mkstemp`, which makes every file 0600 whatever the umask: a heartbeat
    another uid of the group could not read. Now a file in flight is made under the process's umask (`new_temp`), as
    the rows always were: under the units' 0007 an object, a create-only mark, a row, the lock and the counter are
    all 0660 — and nothing is left in flight."""
    import tempfile
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.variables import FileVariables
    root = tempfile.mkdtemp(prefix="platform-")
    was = os.umask(0o007)
    try:
        objects, vars_ = FsObjectStore(os.path.join(root, "objects")), FileVariables(os.path.join(root, "config"))
        objects.put("platform/resources/srv-1/heartbeat", b"{}")
        assert objects.put_new("vms/commands/1/a", b"1")
        vars_.put("platform/doors/srv-1", {"url": "http://srv-1:8090"})
    finally:
        os.umask(was)
    made = [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs]
    assert not any(f.endswith(".tmp") for f in made), made
    assert {os.path.relpath(f, root): oct(os.stat(f).st_mode & 0o777) for f in made} == {
        "objects/platform/resources/srv-1/heartbeat": "0o660", "objects/vms/commands/1/a": "0o660",
        "config/vars/platform%2Fdoors%2Fsrv-1.json": "0o660", "config/lock": "0o660", "config/index": "0o660"}


def test_the_platforms_processes_run_as_w2c_and_every_writer_is_a_client_of_its_group():
    """The owner's decisions (4 October), in the unit lines. The resource runs as `w2c` (`User=2100`, `Group=2100`)
    and is the one unit of the box that names a user: the VMS's processes are still root in their containers. Every
    unit opens the platform's two file stores as a member of `w2c-store` (`GroupAdd=2103`); every unit that mounts the
    events archive joins `w2c-events` (2102) — the resource, which deletes there, and the clients that write
    buckets; every unit writes with the umask 0007 (`PodmanArgs=--umask=0007`: Quadlet has no key for it, and
    systemd's `UMask=` would be podman's, not the container's) — so what each makes is its group's."""
    writers = set()
    for n in sorted(os.listdir(DEPLOY)):
        if not n.endswith(".container"):
            continue
        c = unit(n)["Container"]
        vols = dict(v.split(":", 1) for v in _list(c["Volume"]))
        groups = _list(c.get("GroupAdd"))
        assert vols.get(CONFIG) == f"{CONFIG}:z" and vols.get(OBJECTS) == f"{OBJECTS}:z" and W2C_STORE in groups, n
        assert "--umask=0007" in _list(c.get("PodmanArgs")), n
        assert (EVENTS in vols) == (W2C_EVENTS in groups), n
        if EVENTS in vols:
            writers.add(n)
        assert ("User" in c) == (n == "w2c-resource.container"), n
    assert writers == {"w2c-resource.container", "console.container", "vmsworker@.container", "recworker@.container",
                       "detworker@.container", "detjobworker@.container", "surveyworker@.container",
                       "autoworker@.container", "liveworker@.container"}, writers
    r = unit("w2c-resource.container")["Container"]
    assert (r["User"], r["Group"]) == (W2C, W2C) and W2C_SECRETS not in _list(r.get("GroupAdd"))   # it opens no secret


def test_every_process_that_registers_with_the_resource_mounts_the_events_archive():
    """The twelfth review, major 5: a process that holds a slot registers with its server's resource
    (`vms/__main__._present`, `make_worker`, `make_recorder`: a lock and its name in `<events archive>/.workers`), and the live gateway's container
    did not mount the events archive — its registration went into the container's own layer, the resource never saw it,
    and a hung gateway was "not listed", its slot released: two gateways. Every entry point that calls `_present`, read
    from `vms/__main__.py`, against the container that runs it: the archive mounted, its group joined."""
    import ast
    src = ast.parse(open(os.path.join(HERE, "vms", "__main__.py"), encoding="utf-8").read())
    registers = {f.name for f in src.body if isinstance(f, ast.FunctionDef)
                 and any(isinstance(n, ast.Call) and getattr(n.func, "id", "") in ("_present", "make_worker", "make_recorder")
                         for n in ast.walk(f))}
    assert {"worker", "recorder", "gateway", "detworker", "detjobworker", "surveyworker", "autoworker"} <= registers, registers
    ran = set()
    for n in sorted(os.listdir(DEPLOY)):
        if n.endswith(".container"):
            c = unit(n)["Container"]
            verb = c["Exec"].split()[-1]
            if verb in registers:
                vols = dict(v.split(":", 1) for v in _list(c["Volume"]))
                assert vols.get(EVENTS) == f"{EVENTS}:z" and W2C_EVENTS in _list(c.get("GroupAdd")), n
                ran.add(verb)
    assert ran == registers, registers - ran                        # every one of them has its container


def test_a_recorder_told_nothing_keeps_its_events_in_the_platforms_archive_and_its_volume_where_the_vms_keeps_volumes():
    """WP-E's layout in the recorder's own defaults (the twelfth review's alignment): with no `RESOURCE_ROOT`, no
    `resource_root` and no `ARCHIVE_VOLUME`, its events go to the platform's archive (`runtime.events_root`:
    `/data/platform/events`) and its own volume is the VMS's (`config.OWN_VOLUME`, `/data/vms/obsd/volume`) — it was
    `/data/archive` and `/data/volume` beside it, the layout before. A tree named by its caller keeps its volume beside."""
    import types
    from tests.vmsconftest import Box
    from vms.config import OWN_VOLUME
    from vms.recworker import RecWorker
    from vms.worker import FakeActuator
    box = Box()
    r = RecWorker("r-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                  obsd=types.SimpleNamespace(), env={})
    assert r.resource_root == EVENTS and r.default_url == OWN_VOLUME == "file:///data/vms/obsd/volume"
    named = RecWorker("r-2", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1",
                      obsd=types.SimpleNamespace(), env={}, resource_root=box.resource_root)
    assert named.default_url == "file://" + os.path.join(os.path.dirname(os.path.abspath(box.resource_root)), "volume")


def test_install_obsd_moves_the_old_layout_into_data_and_links_etc_deleting_nothing():
    """The owner's decision (4 October): configuration in /data, /etc as links — `/etc/w2c → /data/platform/etc`,
    `/etc/vms → /data/vms/etc` — and the course's box moved off its old places by the install script, deleting
    nothing. RUN in a sandbox (`INSTALL_ROOT`) holding a box of the old layout: `/data/config/{w2c,vms}.env`,
    `/data/secrets/platform.key`, `/data/archive` with a bucket, a ring at `/data/volume`, a real `/etc/w2c` with a
    file. After: the links, every file where the layout says, `w2c.env` given the platform's events root, the ring kept where it is
    with `ARCHIVE_VOLUME` saying so, the key 0640 to `w2c-secrets`. Run again: nothing moves, nothing is said twice.
    And a group made with another number than the units join by stops the script before it changes anything."""
    import tempfile
    box = tempfile.mkdtemp(prefix="install-box-")
    old = {"data/config/w2c.env": "PLATFORM_DIR=/data/platform\n", "data/config/vms.env": "CAPACITY=7\n",
           "data/secrets/platform.key": "k1 00\n", "data/archive/vms/7/e1/20261004T100000Z.events.jsonl": '{"t": 1}\n',
           "data/volume/ring.0": "ring", "etc/w2c/configstore-rights.json": "{}\n"}
    for path, text in old.items():
        os.makedirs(os.path.dirname(os.path.join(box, path)), exist_ok=True)
        with open(os.path.join(box, path), "w") as f:
            f.write(text)
    at = lambda *p: os.path.join(box, *p)                                    # noqa: E731
    out, calls = _install_obsd(owned=True, same_unit=True, box=box)
    assert out.returncode == 0, out.stdout + out.stderr
    assert os.readlink(at("etc/w2c")) == at("data/platform/etc") and os.readlink(at("etc/vms")) == at("data/vms/etc")
    w2c, vms = open(at("etc/w2c/w2c.env")).read(), open(at("etc/vms/vms.env")).read()
    assert w2c.startswith("PLATFORM_DIR=/data/platform\n") and "\nRESOURCE_ROOT=/data/platform/events\n" in w2c
    assert "CAPACITY=7" in vms and not any(l.startswith("RESOURCE_ROOT=") for l in vms.splitlines())   # the platform's, not the VMS's
    assert vms.count("\nARCHIVE_VOLUME=file:///data/volume\n") == 1 and open(at("data/volume/ring.0")).read() == "ring"
    assert open(at("data/platform/etc/secrets/platform.key")).read() == "k1 00\n"
    key = at("data/platform/etc/secrets/platform.key")
    assert f"chgrp w2c-secrets {key}" in calls and f"chmod 0640 {key}" in calls
    assert os.path.exists(at("data/platform/events/vms/7/e1/20261004T100000Z.events.jsonl")) and not os.path.exists(at("data/archive"))
    assert os.path.exists(at("etc/w2c/configstore-rights.json"))             # the real /etc/w2c's file, moved under the link
    assert not os.path.exists(at("data/config")) and not os.path.exists(at("data/secrets"))   # emptied, so gone
    out, calls = _install_obsd(owned=True, same_unit=True, box=box)          # again: a box in order
    assert out.returncode == 0 and "moved" not in out.stdout and "RESOURCE_ROOT" not in out.stdout, out.stdout
    assert open(at("etc/vms/vms.env")).read() == vms and open(at("etc/w2c/w2c.env")).read() == w2c
    out, calls = _install_obsd(owned=True, numbers={**NUMBERS, "group w2c-events": "999"})
    assert out.returncode == 1 and "w2c-events has the number 999" in out.stderr, out.stderr
    assert not any(c.startswith(("systemd-tmpfiles", "chgrp", "chown", "systemctl")) for c in calls), calls
    assert not os.path.exists(os.path.join(out.box, "etc"))                  # nothing laid before the numbers agree


def test_install_obsd_stops_a_running_daemon_before_the_volumes_change_hands_and_restarts_it_after():
    """The review's fifth pass, major: on a box upgraded from a daemon that ran as root, `install-obsd.sh` ran `chown -R`
    while that daemon still wrote — making new blocks of root's behind it — and `enable --now` left the running daemon
    as it was, its socket where the recorders no longer look. The script is RUN here, every command it calls a shim
    that writes its line down, and the ORDER is the claim: the daemon stopped, then the volumes handed over, then the
    unit installed, enabled and restarted — never `enable --now`."""
    out, calls = _install_obsd("/data/disk-2")
    assert out.returncode == 0, out.stderr

    def at(line):
        assert line in calls, f"{line!r} not called: {calls}"
        return calls.index(line)
    stop = at("systemctl stop obsd.service")
    handed = [i for i, line in enumerate(calls) if line.startswith("chown -R vms-obsd:vms-obsd")]
    assert len(handed) == 2 and stop < min(handed)                                     # both volumes, after the stop
    unit_in = at("install -m 0644 " + os.path.join(DEPLOY, "obsd.service") + " /etc/systemd/system/obsd.service")
    assert max(handed) < unit_in < at("systemctl daemon-reload") < at("systemctl enable obsd.service") \
        < at("systemctl restart obsd.service")
    assert not any("--now" in line for line in calls)                                  # a running unit is not left as it was


# What `getent` answers on a box where `obsd.sysusers` and `w2c.sysusers` were applied: the numbers the units say.
NUMBERS = {"passwd w2c": W2C, "group w2c": W2C, "group w2c-events": W2C_EVENTS, "group w2c-store": W2C_STORE,
           "group w2c-secrets": W2C_SECRETS, "group vms-obsd": VMS_OBSD}


def _install_obsd(*args, active=True, stops=True, owned=False, same_unit=False, store=None, server="srv-1", box=None,
                  numbers=None):
    """`install-obsd.sh` RUN, every command it calls a shim that writes its line down: `(the finished process, the
    lines)`. `active`: a daemon runs; `stops`: `systemctl stop` stops it; `owned`: every volume is obsd's already;
    `same_unit`: the unit installed is the one in the tree; `store`: the box's file store, for the declared volumes;
    `box`: the directory the layout is made under (`INSTALL_ROOT`; a fresh one when not given — `out.box`), where
    `mkdir` and `install` really make what they are asked; `numbers`: what `getent` answers (`NUMBERS`)."""
    import subprocess
    import tempfile
    bin_ = tempfile.mkdtemp(prefix="install-obsd-")
    box = box or tempfile.mkdtemp(prefix="install-box-")
    log, state = os.path.join(bin_, "calls"), os.path.join(bin_, "active")
    if active:
        open(state, "w").close()
    answers = "".join(f'"{k}") echo "{k.split()[1]}:x:{v}:" ;; ' for k, v in (numbers or NUMBERS).items())
    says = {"id": "echo 0", "getent": f'case "$1 $2" in {answers}*) exit 2 ;; esac',
            "find": "true" if owned else 'echo "$2/block-0"',
            "pgrep": f'[ -f "{state}" ]', "cmp": "true" if same_unit else "false",
            "mkdir": f'case "$*" in *"{box}"*) exec /bin/mkdir "$@" ;; esac',
            "install": f'case "$*" in *"{box}"*) exec /usr/bin/install "$@" ;; esac',
            "systemctl": (f'case "$1" in is-active) [ -f "{state}" ] ;; '
                          + (f'stop) rm -f "{state}" ;; ' if stops else "stop) false ;; ")
                          + f'restart|start) : > "{state}" ;; esac')}
    for name in ("id", "install", "systemd-sysusers", "getent", "systemd-tmpfiles", "systemctl", "mkdir", "find",
                 "chown", "chgrp", "chmod", "pgrep", "cmp"):
        with open(os.path.join(bin_, name), "w") as f:
            f.write(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n{says.get(name, "true")}\n')
        os.chmod(os.path.join(bin_, name), 0o755)
    env = {**os.environ, "PATH": bin_ + os.pathsep + os.environ.get("PATH", ""), "SERVER_NAME": server,
           "PLATFORM_DIR": store or os.path.join(bin_, "no-store"), "INSTALL_ROOT": box}
    out = subprocess.run(["/bin/sh", os.path.join(DEPLOY, "install-obsd.sh"), *args], env=env,
                         capture_output=True, text=True, timeout=30)
    out.box = box
    return out, [line.strip() for line in open(log)]


def test_install_obsd_stops_the_daemon_only_to_hand_a_volume_over_and_does_not_go_on_if_it_did_not_stop():
    """The review's sixth pass, minor. Three things the script did: it threw the failure of `stop` away
    (`2>/dev/null || true`) and chowned under a daemon that had not stopped; run again on a box in order it stopped
    and restarted the daemon all the same — every recording interrupted for nothing; and it knew only the volumes
    it was told. Now: nothing to hand over and the unit unchanged — nothing is stopped and nothing restarted; a
    daemon that will not stop ends the script with 3, and no `chown` ran; and a volume declared for THIS box in
    the box's own store is found, named and handed over — another box's, and a bucket, are not."""
    import tempfile
    from w2cplatform.variables import FileVariables
    out, calls = _install_obsd(owned=True, same_unit=True)                     # the box is in order
    assert out.returncode == 0 and "left as it is" in out.stdout, out.stdout + out.stderr
    assert not any(c.startswith(("systemctl stop", "systemctl restart", "systemctl start", "chown")) for c in calls), calls

    out, calls = _install_obsd(owned=True, same_unit=True, active=False)       # in order, and the daemon down: started
    assert out.returncode == 0 and "systemctl start obsd.service" in calls and "systemctl restart obsd.service" not in calls

    out, calls = _install_obsd(owned=True)                                     # a new unit: restarted, and nothing stopped first
    assert out.returncode == 0 and "systemctl restart obsd.service" in calls and "systemctl stop obsd.service" not in calls

    out, calls = _install_obsd(stops=False)                                    # a ring to hand over, a daemon that will not stop
    assert out.returncode == 3 and "NOTHING was handed over" in out.stderr
    assert "systemctl stop obsd.service" in calls and not any(c.startswith("chown") for c in calls), calls

    root = tempfile.mkdtemp(prefix="platform-")
    vars_ = FileVariables(os.path.join(root, "config"))
    vars_.put("rec/volumes/disk-2", {"kind": "local", "server": "srv-1", "url": "/data/disk-2", "quota_bytes": "1"})
    vars_.put("rec/volumes/second", {"kind": "backup", "server": "srv-1", "url": "file:///data/second", "quota_bytes": "1"})
    vars_.put("rec/volumes/theirs", {"kind": "local", "server": "srv-2", "url": "/data/theirs", "quota_bytes": "1"})
    vars_.put("rec/volumes/cloud", {"kind": "network", "server": "", "url": "s3://bucket/x", "quota_bytes": "1"})
    out, calls = _install_obsd(store=root)
    assert out.returncode == 0, out.stderr
    handed = sorted(c.split()[-1] for c in calls if c.startswith("chown -R vms-obsd:vms-obsd"))
    own = out.box + "/data/vms/obsd/volume"                                     # the box's own, under its layout
    assert handed == sorted(["/data/disk-2", "/data/second", own]), handed     # this box's, declared: found without being told
    assert "declared for srv-1: /data/disk-2 (disk-2)" in out.stdout and "/data/theirs" not in out.stdout
    out, calls = _install_obsd()                                               # no store to read: said, not passed over
    assert "no volume declared for srv-1" in out.stdout


ROLES_WITH_TEMPLATES = ("vmsworker", "recworker", "liveworker", "autoworker")


def _spares(*args, pages=None, env=None, active=(), linux=True, templates=ROLES_WITH_TEMPLATES, refused=()):
    """`w2c-spares.sh` RUN, every command it talks to a shim: `curl` answers from `pages` (`{path: text}`, a missing
    path is a console that does not answer); on Linux `systemctl cat` finds the spare templates of `templates`,
    `systemctl start` writes its line down and the unit is active from then on — but a unit of `refused` is refused,
    as polkit or systemd's start limit refuses one — `systemctl is-active` says so for `active` and what was started;
    any other verb is written down too (polkit gives the spares' user `start` alone). `linux` False: no `systemctl` anywhere on PATH, `uname` says Darwin — the macOS path:
    the roles' plists of `templates` in `$LAUNCHD_DIR` (as `install.sh` lays them), the real `plutil`, a `launchctl`
    that writes its line down and has the label loaded from then on. Every shim writes before it returns: nothing runs
    in the background, so the lines are there when the script ends. `(the finished process — its `dir` the shims' —,
    the lines)`."""
    import plistlib
    import shutil
    import subprocess
    import tempfile
    bin_ = tempfile.mkdtemp(prefix="w2c-spares-")
    log = os.path.join(bin_, "calls")
    open(log, "w").close()
    for path, text in (pages or {}).items():
        with open(os.path.join(bin_, "page" + path.replace("/", "_")), "w") as f:
            f.write(text)
    for unit in active:
        open(os.path.join(bin_, "active-" + unit), "w").close()
    for unit in refused:
        open(os.path.join(bin_, "refused-" + unit), "w").close()
    launchd = os.path.join(bin_, "launchd")
    os.makedirs(launchd)
    for role in templates:
        open(os.path.join(bin_, f"template-vms-{role}-spare@.service"), "w").close()
        with open(os.path.join(launchd, f"com.w2c.vms.{role}.plist"), "wb") as f:     # the role's own, as installed
            plistlib.dump({"Label": f"com.w2c.vms.{role}", "ProgramArguments": ["/opt/w2c/bin/w2c-run.sh", role],
                           "EnvironmentVariables": {"PLATFORM_STORE": f"configstore:///var/run/configstore/{role}.sock",
                                                    "WORKER_NAME": f"x-srv-a-1", "SECRETS_KEY": "/etc/w2c/secrets/platform.key",
                                                    "RTSP_HOST": "0.0.0.0", "ARCHIVE_PORT": "8084"},
                           "KeepAlive": True, "StandardErrorPath": f"/var/log/w2c/com.w2c.vms.{role}.log",
                           "StandardOutPath": f"/var/log/w2c/com.w2c.vms.{role}.log"}, f)
    says = {"curl": f'for a; do url=$a; done; f="{bin_}/page$(printf %s "${{url#http://console}}" | tr / _)"; '
                    f'[ -f "$f" ] && cat "$f" || exit 22',
            "systemctl": f'case "$1" in is-active) [ -f "{bin_}/active-$3" ] ;; cat) [ -f "{bin_}/template-$2" ] ;; '
                         f'start) [ -f "{bin_}/refused-$2" ] && {{ echo "systemctl start $2 (refused)" >> "{log}"; exit 1; }}; '
                         f'echo "systemctl start $2" >> "{log}"; : > "{bin_}/active-$2" ;; '
                         f'*) echo "systemctl $*" >> "{log}" ;; esac',
            "uname": "echo Darwin",
            "launchctl": f'case "$1" in print) [ -f "{bin_}/active-${{2##*/}}" ] ;; bootout) ;; '
                         f'bootstrap) echo "launchctl bootstrap $2 $3" >> "{log}"; : > "{bin_}/active-$(basename "$3" .plist)" ;; '
                         f'*) echo "launchctl $*" >> "{log}" ;; esac'}
    names = ("curl", "systemctl") if linux else ("curl", "uname", "launchctl")
    for name in names:
        with open(os.path.join(bin_, name), "w") as f:
            f.write(f"#!/bin/sh\n{says[name]}\n")
        os.chmod(os.path.join(bin_, name), 0o755)
    path = bin_ + os.pathsep + os.environ.get("PATH", "")
    if not linux:                                    # only the shims and the plain tools: no systemctl to be found
        for tool in ("sed", "grep", "tr", "cat", "mkdir", "cp", "chmod", "basename", "hostname", "plutil", "id"):
            found = shutil.which(tool)
            if found:
                os.symlink(found, os.path.join(bin_, tool))
        path = bin_
    full = {"PATH": path, "CONSOLE": "http://console", "SERVER_NAME": "srv-a", "SPARES_DIR": os.path.join(bin_, "spares"),
            "SPARES_ENV": os.path.join(bin_, "env"), "LAUNCHD_DIR": launchd, **(env or {})}
    out = subprocess.run(["/bin/sh", os.path.join(DEPLOY, "w2c-spares.sh"), *args], env=full, capture_output=True,
                         text=True, timeout=30)
    out.dir = bin_
    return out, [line.strip() for line in open(log)]


def _said_to(out, unit: str) -> str | None:
    """What the script wrote for a spare's template to read (`$SPARES_ENV/<unit>.service.env`), or None."""
    p = os.path.join(out.dir, "env", unit + ".service.env")
    return open(p).read() if os.path.exists(p) else None


NEEDED = """# TYPE vms_workers_needed gauge
vms_workers_needed{labels=""} 1
vms_workers_needed{labels="vlan:dmz"} 2
vms_workers_needed{labels="vlan:x"} 1
# TYPE vms_server_labels gauge
vms_server_labels{server="srv-a",labels="vlan:dmz",source="console"} 1
vms_server_labels{server="srv-b",labels="vlan:x",source="console"} 1
"""


def test_the_spares_script_starts_spares_for_the_sets_its_server_covers_up_to_its_ceiling_and_stops_nothing():
    """The product's P5, the course's `w2c-spares.sh vmsworker`, run with its commands shimmed. The console wants one
    camera worker on no label, two on `vlan:dmz`, one on `vlan:x`; srv-a reaches `vlan:dmz` by the console's row
    (`vms_server_labels … source="console"`). Under `MAX_WORKERS=2`: a spare for the empty set and one for `vlan:dmz`,
    each `systemctl start vms-vmsworker-spare@<n>` with its set in the one-line file its template reads; none for
    `vlan:x`, which srv-a does not reach; the second `vlan:dmz` not, the ceiling. Run again: the two run, the ceiling is
    reached, nothing more. Never a stop, never a kill."""
    out, calls = _spares("vmsworker", pages={"/metrics": NEEDED}, env={"MAX_WORKERS": "2"})
    assert out.returncode == 0, out.stderr
    started = [c for c in calls if c.startswith("systemctl start")]
    assert started == ["systemctl start vms-vmsworker-spare@1", "systemctl start vms-vmsworker-spare@2"], calls
    assert _said_to(out, "vms-vmsworker-spare@1") == "SPARE_FOR=\n" and _said_to(out, "vms-vmsworker-spare@2") == "SPARE_FOR=vlan:dmz\n"
    assert "which srv-a does not reach" in out.stdout and "the ceiling here is 2" in out.stderr, out.stdout + out.stderr
    assert not any(" stop " in c or c.startswith(("systemctl stop", "kill")) for c in calls), calls
    assert all(c.startswith("systemctl start ") for c in calls), calls      # the one verb polkit gives its user
    out, calls = _spares("vmsworker", pages={"/metrics": NEEDED}, env={"MAX_WORKERS": "2"},
                         active=("vms-vmsworker-spare@1", "vms-vmsworker-spare@2"))
    assert out.returncode == 0 and not [c for c in calls if c.startswith("systemctl start")], calls


def test_a_spare_systemd_refuses_to_start_is_said_and_the_next_number_is_tried():
    """The script runs as `w2c-spares` now, whom polkit lets `start` a spare template's instance and nothing else (the
    product's cross-check, 4 Oct) — so no `reset-failed` before a start either: an instance past systemd's start limit,
    or one polkit refuses, fails its `start`. That is said, and the next number is tried, within the ceiling."""
    out, calls = _spares("vmsworker", pages={"/metrics": 'vms_workers_needed{labels=""} 1\n'}, env={"MAX_WORKERS": "2"},
                         refused=("vms-vmsworker-spare@1",))
    assert out.returncode == 0, out.stderr
    assert calls == ["systemctl start vms-vmsworker-spare@1 (refused)", "systemctl start vms-vmsworker-spare@2"], calls
    assert "vms-vmsworker-spare@1 did not start — the next number is tried" in out.stderr, out.stderr
    assert "started vms-vmsworker-spare@2" in out.stdout


def test_the_spares_script_takes_the_hosts_labels_without_a_console_row_and_starts_nothing_on_a_silent_or_stale_console():
    """No `vms_server_labels` row with `source="console"` for this server: the host's `$LABELS`. A console that does
    not answer, and one whose controller's pass is stale (the page carries no `vms_workers_needed`): nothing started,
    and the script ends 0 — the console being away is not a reason to start anything. Roles from `SPARES_ROLES`; a
    recorder by `rec_workers_needed{labels=""}` on `/rec/metrics`, with no `SPARE_FOR` (it takes a free volume, no offer)."""
    no_row = NEEDED.replace('server="srv-a"', 'server="srv-c"')
    out, calls = _spares("vmsworker", pages={"/metrics": no_row}, env={"LABELS": "vlan:x"})
    assert [c for c in calls if c.startswith("systemctl start")] == \
        ["systemctl start vms-vmsworker-spare@1", "systemctl start vms-vmsworker-spare@2"], calls
    assert _said_to(out, "vms-vmsworker-spare@1") == "SPARE_FOR=\n" and _said_to(out, "vms-vmsworker-spare@2") == "SPARE_FOR=vlan:x\n"
    out, calls = _spares("vmsworker", pages={})
    assert out.returncode == 0 and calls == [] and "no answer" in out.stderr, out.stderr
    out, calls = _spares("vmsworker", pages={"/metrics": "vms_units_unplaced 3\n"})
    assert out.returncode == 0 and calls == [] and "nothing started" in out.stdout, out.stdout
    out, calls = _spares(pages={"/rec/metrics": 'rec_workers_needed{labels=""} 1\n', "/live/metrics": 'live_workers_needed{labels=""} 1\n'},
                         env={"SPARES_ROLES": "recworker,liveworker"})
    assert [c for c in calls if c.startswith("systemctl start")] == [
        "systemctl start vms-recworker-spare@1", "systemctl start vms-liveworker-spare@1"], calls
    assert _said_to(out, "vms-recworker-spare@1") is None and _said_to(out, "vms-liveworker-spare@1") == "SPARE_FOR=\n"


def test_a_spare_is_started_only_as_its_roles_unit_and_never_as_root_without_one():
    """The twelfth review, blocker 6: a spare was `systemd-run … w2c-run.sh worker` — root, no key, the fan-out on
    loopback; a camera of the dead server with a sealed password did not start on the spare started for it. Now a
    spare is its role's TEMPLATE (`vms-<role>-spare@.service`, the regular unit's twin) or nothing: a server without
    the template starts nothing for that role and says why, and the script calls no `systemd-run` at all."""
    out, calls = _spares("vmsworker", "recworker", pages={"/metrics": NEEDED, "/rec/metrics": 'rec_workers_needed{labels=""} 1\n'},
                         templates=("recworker",))
    assert out.returncode == 0, out.stderr
    assert [c for c in calls if c.startswith("systemctl start")] == ["systemctl start vms-recworker-spare@1"], calls
    assert "no spare template for vmsworker" in out.stderr and "runs as its role's unit or not at all" in out.stderr
    assert "systemd-run" not in open(os.path.join(DEPLOY, "w2c-spares.sh")).read().split("set -eu", 1)[1]


def test_the_spares_script_on_macos_starts_its_roles_plist_without_the_name_and_counts_it_by_its_label():
    """No `systemctl`, and `uname` says Darwin: the role's own plist (`$LAUNCHD_DIR/com.w2c.vms.<role>.plist`, what
    launchd runs the role from) copied as `com.w2c.vms.<role>.spare-<n>` — the same program and environment, its key
    included, but no `WORKER_NAME`, `SPARE_FOR=<set>`, its fan-out on a port the OS gives and its own log — and
    `launchctl bootstrap`ped; a loaded label is what the next run counts against the ceiling. Every call is made before
    the script ends (the coordinator's flaky test: the `nohup` child wrote its line after the script had). Into the
    box's user's launchd domain (`gui/<uid>`), not `system` (the thirteenth review, major 15: a box on macOS is a
    directory, its plists the user's `~/Library/LaunchAgents`, every process that user's), its log beside its role's."""
    import plistlib
    import shutil
    if not shutil.which("plutil"):
        import pytest
        pytest.skip("no plutil: the macOS path is checked on macOS")
    out, calls = _spares("vmsworker", pages={"/metrics": 'vms_workers_needed{labels=""} 1\n'}, linux=False)
    assert out.returncode == 0, out.stderr
    plist = os.path.join(out.dir, "spares", "com.w2c.vms.vmsworker.spare-1.plist")
    assert calls == [f"launchctl bootstrap gui/{os.getuid()} {plist}"], calls + [out.stdout, out.stderr]
    assert "started vms-vmsworker-spare@1" in out.stdout
    with open(plist, "rb") as f:
        p = plistlib.load(f)
    assert p["Label"] == "com.w2c.vms.vmsworker.spare-1" and p["ProgramArguments"] == ["/opt/w2c/bin/w2c-run.sh", "vmsworker"]
    assert p["EnvironmentVariables"] == {"PLATFORM_STORE": "configstore:///var/run/configstore/vmsworker.sock",
                                         "SECRETS_KEY": "/etc/w2c/secrets/platform.key", "RTSP_HOST": "0.0.0.0",
                                         "ARCHIVE_PORT": "8084", "SPARE_FOR": "", "RTSP_PORT": "auto"}, p
    assert p["StandardErrorPath"] == "/var/log/w2c/com.w2c.vms.vmsworker.spare-1.log" and p["KeepAlive"] is True
    out, calls = _spares("vmsworker", pages={"/metrics": 'vms_workers_needed{labels=""} 1\n'}, linux=False,
                         env={"MAX_WORKERS": "1"}, active=("com.w2c.vms.vmsworker.spare-1",))
    assert out.returncode == 0 and calls == [], calls


def test_every_spares_unit_runs_the_script_for_its_role():
    """`w2c-spares.{service,timer}` for recorders, `w2c-spares-<role>.{service,timer}` for the camera workers, the
    gateways and the evaluators (the product's §6): each service a one-shot running `w2c-spares.sh <role>` on the host,
    each timer every minute — and the one directory it writes, where each spare's set is for its runner to read;
    each as the spares' own user, never root."""
    for role in ("recworker", "vmsworker", "liveworker", "autoworker"):
        name = "w2c-spares" if role == "recworker" else f"w2c-spares-{role}"
        svc = unit(name + ".service")["Service"]
        assert svc["Type"] == "oneshot" and svc["ExecStart"] == f"/usr/local/bin/w2c-spares.sh {role}", svc
        assert svc["RuntimeDirectory"] == "w2c-spares" and svc["RuntimeDirectoryPreserve"] == "yes", svc
        # not root (the product's cross-check, 4 Oct): its own user in no group but its own; its directory readable by
        # the spares, who take one line of their file (М11's `w2c-run.sh`, `w2c-spares.rules`, `w2c-cluster.sysusers`)
        assert svc["User"] == svc["Group"] == "w2c-spares" and "SupplementaryGroups" not in svc, svc
        assert svc["RuntimeDirectoryMode"] == "0755", svc
        assert unit(name + ".timer")["Timer"]["OnUnitActiveSec"] == "1min"
    assert os.access(os.path.join(DEPLOY, "w2c-spares.sh"), os.X_OK)


def test_a_bundle_copied_to_a_server_is_given_to_the_daemons_user_who_can_then_read_it():
    """The thirteenth review, major 14: the store's member runs as `configstore` (`User=configstore`), its TLS directory
    is 0750 root:configstore — and `w2c-ca.sh` said to copy the bundle in as root with keys 0600, so the daemon could
    not read its own key or the raft secret: `PermissionError`, and the store came up on no server. Group read would not
    do for the secret (`tls.raft_secret` refuses one anybody but its owner may read). `w2c-ca.sh own <dir> <user>`
    hands the bundle to the daemon's user — the files its, the keys and the secret 0600, the certificates 0644, the
    directory 0750 to its group — and М11's `install.sh` runs it on /etc/w2c/tls for `configstore`, after the user is
    made. Here as the test's own user: a bundle as a checkout leaves it (the secret readable by others) is refused by
    `tls`, and after `own` the secret, the server's and the client's contexts all load."""
    import pwd
    import shutil
    import stat
    import subprocess
    import tempfile
    import pytest
    from w2cplatform import tls
    d = os.path.join(tempfile.mkdtemp(prefix="tls-"), "tls")
    shutil.copytree(os.path.join(HERE, "tests", "tls", "srv-a"), d)
    os.chmod(os.path.join(d, "raft.secret"), 0o644)
    with pytest.raises(ValueError):
        tls.raft_secret(d)                                              # readable by others: refused
    me = pwd.getpwuid(os.getuid()).pw_name
    out = subprocess.run(["sh", os.path.join(DEPLOY, "w2c-ca.sh"), "own", d, me], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    mode = lambda p: stat.S_IMODE(os.stat(os.path.join(d, p)).st_mode)          # noqa: E731
    assert mode("") == 0o750 and os.stat(d).st_gid == pwd.getpwnam(me).pw_gid
    for f in os.listdir(d):
        assert os.stat(os.path.join(d, f)).st_uid == os.getuid(), f
        assert mode(f) == (0o600 if f.endswith(".key") or f == "raft.secret" else 0o644), (f, oct(mode(f)))
    assert tls.raft_secret(d) and tls.server_context(d) and tls.client_context(d)
    assert subprocess.run(["sh", os.path.join(DEPLOY, "w2c-ca.sh"), "own", d, "no-such-user-here"],
                          capture_output=True, text=True).returncode != 0
    m11 = open(os.path.join(DEPLOY, "cluster", "install.sh"), encoding="utf-8").read()
    linux = m11.split("systemd-sysusers /etc/sysusers.d/w2c-cluster.conf", 1)[1]           # after the user is made
    assert 'w2c-ca.sh" own /etc/w2c/tls configstore' in linux


def test_the_console_unit_builds_the_vms_at_its_root_and_every_other_spec_under_its_name():
    """`console.container` runs the platform's console (`python3 -m w2cplatform console`; the boundary's step 6: it was
    `python3 -m vms console`, with the VMS's own routes and its own list of what it fronts): over the specs the image
    carries (`SPEC_DIR=/app/vms`, here the package's directory), the VMS at `/` by the unit's `CONSOLE_ROOT`, and the
    recorder, the live gateways, the detectors, the scans, the survey and automation under their names — one token."""
    import tempfile
    from w2cplatform import host
    env = {"SPEC_DIR": os.path.join(HERE, "vms"), "PLATFORM_DIR": tempfile.mkdtemp(prefix="platform-"), "CONSOLE_ROOT": "vms"}
    m, ctls = host.build_console(env)
    assert m.root.spec.name == "vms" and set(m.mounts) == {"rec", "live", "det", "detjob", "survey", "auto"}
    assert "door" not in m.root.describe()                               # no door at a camera's holder
    assert m.mounts["rec"].describe()["door"] == {"routes": ["timeline", "segment"]}
    assert m.mounts["live"].describe()["door"] == {"routes": ["whep"]}


def test_the_vms_processes_open_their_stores_through_the_platforms_one_function():
    """What the VMS's entry point does with the platform's rule (`test_configstorevars.py`,
    `test_a_process_reads_platform_store_and_no_other_name`: `PLATFORM_STORE`, never `CONFIG_URL`): its processes open
    their stores through the platform's `host.stores`, and the older name is nowhere in it."""
    entry = open(os.path.join(HERE, "vms", "__main__.py"), encoding="utf-8").read()
    assert "host.stores(os.environ" in entry and "CONFIG_URL" not in entry

