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


def test_the_units_run_the_entrypoints_the_package_has():
    from vms import __main__ as m  # noqa: F401  (imports the module without running it: no __name__ == "__main__")
    entrypoints = set(re.findall(r'"(\w+)": \w+', open(os.path.join(HERE, "vms", "__main__.py")).read().split("__main__")[-1]))
    assert entrypoints == {"worker", "controller", "recorder", "reccontroller", "console", "resource", "gateway",
                           "livecontroller", "detworker", "detcontroller", "detjobworker", "detjobcontroller",
                           "surveyworker", "surveycontroller", "autoworker", "autocontroller"}
    for name, entry in [("vmsworker@.container", "worker"), ("vmscontroller.container", "controller"),
                        ("console.container", "console"), ("resource.container", "resource"),
                        ("recworker@.container", "recorder"), ("reccontroller.container", "reccontroller"),
                        ("liveworker@.container", "gateway"), ("livecontroller.container", "livecontroller"),
                        ("detworker@.container", "detworker"), ("detcontroller.container", "detcontroller"),
                        ("detjobworker@.container", "detjobworker"), ("detjobcontroller.container", "detjobcontroller"),
                        ("surveyworker@.container", "surveyworker"), ("surveycontroller.container", "surveycontroller"),
                        ("autoworker@.container", "autoworker"), ("autocontroller.container", "autocontroller")]:
        u = unit(name)
        assert u["Container"]["Image"] == "localhost/vmsserver:latest"                 # one image, one thing to publish
        assert u["Container"]["Exec"] == f"python3 -m vms {entry}"
        assert u["Container"]["EnvironmentFile"] == "/data/config/vms.env"             # the data partition, never a rootfs slot
        for vol in (u["Container"]["Volume"] if isinstance(u["Container"]["Volume"], list) else [u["Container"]["Volume"]]):
            assert vol.startswith("/data/") or vol.startswith("/run/vms:") or vol.startswith("/run/obsd:"), vol   # sockets on a tmpfs, not state


def test_who_may_write_where_is_in_the_mounts_too():
    """The ACL says which rows each token writes; the mounts say which bytes.
    The controller has no archive at all; footage is mounted nowhere — it is behind the host's obsd."""
    vols = lambda n: dict(v.split(":", 1) for v in (lambda x: x if isinstance(x, list) else [x])(unit(n)["Container"]["Volume"]))
    assert "/data/archive" not in vols("vmscontroller.container")
    for n in os.listdir(DEPLOY):
        if n.endswith(".container"):
            assert "/data/spool" not in vols(n), n                                       # there is no spool: footage goes through obsd
    assert vols("vmsworker@.container")["/data/archive"] == "/data/archive:z"          # its events, vms/<cam>/, on this box's resource
    assert vols("vmsworker@.container")["/data/media"].endswith(":ro,z")
    assert vols("recworker@.container")["/data/archive"] == "/data/archive:z"         # its events, and its own volume's path
    assert "/data/media" not in vols("recworker@.container")                          # it never reads a camera: it subscribes to the fan-out
    assert vols("vmsworker@.container")["/run/vms"] == "/run/vms:z" == vols("recworker@.container")["/run/vms"]   # the tee's shared memory
    # the daemon's socket: the recorder's alone, never the holder's — the process with a vendor's DriverPack in it
    for n in os.listdir(DEPLOY):
        if n.endswith(".container"):
            assert ("/run/obsd" in vols(n)) == (n == "recworker@.container"), n
    rec_env = dict(e.split("=", 1) for e in unit("recworker@.container")["Container"]["Environment"])
    assert rec_env["OBSD_SOCKET"] == "/run/obsd/obsd.sock" and rec_env["SECRETS_KEY"] == "/run/secrets/vms.key"   # it opens a volume's secret
    assert "/data/archive" not in vols("reccontroller.container")
    assert vols("resource.container")["/data/platform"] == "/data/platform:z"       # the heartbeat is written; rows are only read
    assert unit("recworker@.container")["Container"]["StopTimeout"] == "40"          # the writer's close waits for its flush (30 s)
    assert "obsd.service" in unit("recworker@.container")["Unit"]["After"]
    assert unit("resource.container")["Service"]["Restart"] == "always"             # a process, not a timer: the database lives in it


def test_the_image_carries_the_three_packages_and_nothing_else():
    cf = "\n".join(l for l in open(os.path.join(DEPLOY, "Containerfile")) if not l.startswith("#"))   # the instructions, not the notes
    copied = re.findall(r"^COPY (\S+) ", cf, re.M)
    assert copied == ["w2cplatform", "vms", "gstvms"]
    assert "postgres" not in cf.lower()                                                # the per-box database is gone (М10 Lesson 1)
    assert 'CMD ["python3", "-m", "vms", "worker"]' in cf
    env = open(os.path.join(DEPLOY, "vms.env.example")).read()
    assert all(k in env for k in ("PLATFORM_DIR=/data/platform", "ARCHIVE=/data/archive", "CAPACITY="))
    assert "SPOOL=" not in env and "SEGMENT_SECONDS=" not in env


def test_the_archives_engine_is_the_hosts_own_daemon():
    """One obsd per host, not a container of the image: it keeps one writer per volume, and that means something
    only if every recorder on the box asks the same one. Its socket is where the recorder already looks."""
    from w2cplatform.obsd import default_socket
    u = unit("obsd.service")
    assert u["Service"]["ExecStart"] == "/usr/local/bin/obsd --socket /run/obsd/obsd.sock"
    assert u["Service"]["RuntimeDirectory"] == "obsd" and u["Service"]["RuntimeDirectoryPreserve"] == "yes"
    assert u["Service"]["RuntimeDirectoryMode"] == "0750"                              # its group gets in; the daemon's own 0700 would not let it
    env = dict(e.split("=", 1) for e in u["Service"]["Environment"])
    assert int(env["OBSD_WRITER_GRACE_S"]) > 45                                         # the writer outlasts a hold that lapses
    assert u["Service"]["User"] == "obsd" and env["OBSD_CLIENT_GROUP"] == u["Service"]["Group"]   # its own user; the recorders' group
    import sys
    if sys.platform != "darwin":
        assert default_socket() == "/run/obsd/obsd.sock"                                # where the unit puts it, not the daemon's own default


def _sysusers() -> tuple[set, dict, set]:
    """`obsd.sysusers` as (users, {group: gid}, {(user, group)})."""
    users, groups, members = set(), {}, set()
    for line in open(os.path.join(DEPLOY, "obsd.sysusers")):
        f = line.split()
        if not f or f[0].startswith("#"):
            continue
        if f[0] == "u":
            users.add(f[1])
        elif f[0] == "g":
            groups[f[1]] = f[2]
        elif f[0] == "m":
            members.add((f[1], f[2]))
    return users, groups, members


def _tmpfiles() -> dict:
    """`vms.tmpfiles` as {path: (type, mode, user, group)}."""
    out = {}
    for line in open(os.path.join(DEPLOY, "vms.tmpfiles")):
        f = line.split()
        if f and not f[0].startswith("#"):
            out[f[1]] = (f[0], f[2], f[3], f[4])
    return out


def test_every_user_group_and_directory_a_unit_names_is_made_by_the_install_files():
    """The review's fourth pass, blocker 2. `obsd.service` ran as a user nobody created and owned a volume nobody
    handed it; /run/vms was made only by that unit, so without the daemon neither the holder nor the recorder started.
    Every user and group a unit names is in `obsd.sysusers` — the clients' group with the number the recorders join it
    by — every host directory under /run a container mounts is in `vms.tmpfiles`, the box's own volume is the daemon's,
    and `install-obsd.sh` installs both files, checks the number and hands an old ring over."""
    users, groups, members = _sysusers()
    dirs = _tmpfiles()
    svc = unit("obsd.service")["Service"]
    assert svc["User"] in users and svc["Group"] in groups and (svc["User"], svc["Group"]) in members
    rec = unit("recworker@.container")["Container"]
    assert groups[svc["Group"]] == rec["GroupAdd"]                                       # the number the container joins by
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
    archive = dict(l.strip().split("=", 1) for l in open(os.path.join(DEPLOY, "vms.env.example"))
                   if "=" in l and not l.startswith("#"))["ARCHIVE"]
    own = os.path.join(os.path.dirname(archive), "volume")                                # the box's own volume, beside ARCHIVE
    assert dirs[own][2:] == (svc["User"], svc["Group"])                                   # the daemon opens it, as itself
    script = open(os.path.join(DEPLOY, "install-obsd.sh")).read()
    for needed in ("obsd.sysusers", "systemd-sysusers", "vms.tmpfiles", "systemd-tmpfiles --create",
                   f'"$GID" != {rec["GroupAdd"]}', f"chown -R {svc['User']}:{svc['Group']}", own,
                   "obsd.service", "systemctl enable obsd.service", "systemctl restart obsd.service"):
        assert needed in script, needed
    assert os.access(os.path.join(DEPLOY, "install-obsd.sh"), os.X_OK)


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
    handed = [i for i, line in enumerate(calls) if line.startswith("chown -R obsd:vms-rec")]
    assert len(handed) == 2 and stop < min(handed)                                     # both volumes, after the stop
    unit_in = at("install -m 0644 " + os.path.join(DEPLOY, "obsd.service") + " /etc/systemd/system/obsd.service")
    assert max(handed) < unit_in < at("systemctl daemon-reload") < at("systemctl enable obsd.service") \
        < at("systemctl restart obsd.service")
    assert not any("--now" in line for line in calls)                                  # a running unit is not left as it was


def _install_obsd(*args, active=True, stops=True, owned=False, same_unit=False, store=None, server="srv-1"):
    """`install-obsd.sh` RUN, every command it calls a shim that writes its line down: `(the finished process, the
    lines)`. `active`: a daemon runs; `stops`: `systemctl stop` stops it; `owned`: every volume is obsd's already;
    `same_unit`: the unit installed is the one in the tree; `store`: the box's file store, for the declared volumes."""
    import subprocess
    import tempfile
    bin_ = tempfile.mkdtemp(prefix="install-obsd-")
    log, state = os.path.join(bin_, "calls"), os.path.join(bin_, "active")
    if active:
        open(state, "w").close()
    says = {"id": "echo 0", "getent": "echo vms-rec:x:2101:", "find": "true" if owned else 'echo "$2/block-0"',
            "pgrep": f'[ -f "{state}" ]', "cmp": "true" if same_unit else "false",
            "systemctl": (f'case "$1" in is-active) [ -f "{state}" ] ;; '
                          + (f'stop) rm -f "{state}" ;; ' if stops else "stop) false ;; ")
                          + f'restart|start) : > "{state}" ;; esac')}
    for name in ("id", "install", "systemd-sysusers", "getent", "systemd-tmpfiles", "systemctl", "mkdir", "find",
                 "chown", "chmod", "pgrep", "cmp"):
        with open(os.path.join(bin_, name), "w") as f:
            f.write(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n{says.get(name, "true")}\n')
        os.chmod(os.path.join(bin_, name), 0o755)
    env = {**os.environ, "PATH": bin_ + os.pathsep + os.environ.get("PATH", ""), "SERVER_NAME": server,
           "PLATFORM_DIR": store or os.path.join(bin_, "no-store")}
    out = subprocess.run(["/bin/sh", os.path.join(DEPLOY, "install-obsd.sh"), *args], env=env,
                         capture_output=True, text=True, timeout=30)
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
    handed = sorted(c.split()[-1] for c in calls if c.startswith("chown -R obsd:vms-rec"))
    assert handed == ["/data/disk-2", "/data/second", "/data/volume"], handed   # this box's, declared: found without being told
    assert "declared for srv-1: /data/disk-2 (disk-2)" in out.stdout and "/data/theirs" not in out.stdout
    out, calls = _install_obsd()                                               # no store to read: said, not passed over
    assert "no volume declared for srv-1" in out.stdout
