"""CLI differential and recovery-file races; execute through CT103 only."""
import base64
import errno
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(sys.argv[1]) / "runner"))
import c_execute
import diagnostic_secrets as ds
import m11stand


def behaviour():
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        root = base / "secret root"
        root.mkdir(mode=0o700)
        folders = {name: base / name for name in ("hold", "m1")}
        for folder in folders.values():
            folder.mkdir()
        registry = ds.Secrets()
        bench = object.__new__(m11stand.Bench)
        bench.root, bench.recovery = str(root), str(root / "acme.recovery.json")
        bench.secrets, bench.a = registry, SimpleNamespace(cwd=str(base))
        bench.clusters = {name: SimpleNamespace(workdir=str(folder), env={"CLUSTER": name}, port=1234)
                          for name, folder in folders.items()}
        bench.ac = lambda name: SimpleNamespace(install_domain="install {recovery}", first_admin="admin",
                                                join="join {recovery}", move="move {console} {recovery} {args}")
        bench.fmt = lambda cluster, template, **extra: template.format(recovery=shlex.quote(extra.get("recovery", bench.recovery)))
        bench.url = lambda port: "http://localhost:1234"
        run = m11stand.Run(SimpleNamespace(cwd=str(base)), "fixture")
        run.b, run.secrets, run.bearer = bench, registry, lambda: None
        calls = []
        secret = b"fixture-private-recovery-material"

        def invoke(**kwargs):
            words = shlex.split(kwargs["args"])
            role = words[0]
            env = {key: value.replace(str(base), "ROOT") for key, value in kwargs["env"].items()}
            calls.append(dict(argv=[v.replace(str(base), "ROOT") for v in words], shell=kwargs["shell"],
                              timeout=kwargs["timeout"], cwd=kwargs["cwd"].replace(str(base), "ROOT"),
                              env_sha256=hashlib.sha256(json.dumps(env, sort_keys=True).encode()).hexdigest(),
                              input_sha256=hashlib.sha256(kwargs.get("input") or b"").hexdigest()))
            if role == "install":
                Path(words[1]).write_bytes(secret)
                os.chmod(words[1], 0o640)
            if role == "move":
                return subprocess.CompletedProcess("fixture", 7, b'200 {"id":"fixture-binding"}', b"fixture stderr")
            if role == "join":
                return subprocess.CompletedProcess("fixture", 2, b"", b"fixture join refusal")
            return subprocess.CompletedProcess("fixture", 0, b"", b"")

        with patch.object(m11stand.subprocess, "run", side_effect=invoke):
            install = run.directive("@install domain", "ok")
            move = run.move("m1", "--fixture", '200 {"id":"$id"}')
            join = run.directive("@join m1", "ok")
            implicit_code, implicit_output = bench.run("m1", "join")
        private = root / "private/acme.recovery.json"
        report = dict(green=False, passed_steps=2, total_steps=3, scenarios={"f": [dict(ok=False, why=join)]})
        return dict(calls=calls, outcomes=[not install, not move, not join], env=run.env,
                    implicit=[implicit_code, implicit_output], source_mode=Path(bench.recovery).stat().st_mode & 0o777,
                    copy_mode=private.stat().st_mode & 0o777, private_mode=private.parent.stat().st_mode & 0o777,
                    source_sha256=hashlib.sha256(Path(bench.recovery).read_bytes()).hexdigest(),
                    copy_sha256=hashlib.sha256(private.read_bytes()).hexdigest(),
                    classification=c_execute.classification(registry.clean(report), 1, False),
                    counters=c_execute.counters(report))


def races():
    import recovery_evidence as evidence
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        path = root / "recovery"
        path.write_bytes(b"fixture metadata only")
        real_open = os.open
        descriptors = []

        def swap_fifo(target, flags):
            assert flags & os.O_NOFOLLOW and flags & os.O_NONBLOCK
            path.unlink()
            os.mkfifo(path)
            fd = real_open(target, flags)
            descriptors.append(fd)
            return fd

        with patch.object(evidence.os, "open", side_effect=swap_fifo), patch.object(evidence.hashlib, "file_digest", side_effect=AssertionError("FIFO must not be read")):
            result = evidence.snapshot(path, root)
        assert result.get("changed_during_read") and result["sha256"] is None
        try:
            os.fstat(descriptors[0])
        except OSError as error:
            assert error.errno == errno.EBADF
        else:
            raise AssertionError("descriptor leaked")
        path.unlink()
        path.write_bytes(b"fixture before mutation")
        digest = hashlib.file_digest

        def mutate(stream, algorithm):
            value = digest(stream, algorithm)
            with path.open("ab") as writer:
                writer.write(b"changed")
            return value

        with patch.object(evidence.hashlib, "file_digest", side_effect=mutate):
            result = evidence.snapshot(path, root)
        assert result.get("changed_during_read") and result["sha256"] is None
        with patch.object(evidence.os, "open", side_effect=OSError(13, "fixture private exception body")):
            result = evidence.snapshot(path, root)
        assert result["read_errno"] == 13 and "fixture private exception body" not in json.dumps(result)
        before = path.stat()
        result = evidence.snapshot(path, root)
        after = path.stat()
        assert (before.st_mode, before.st_uid, before.st_gid, before.st_size) == (after.st_mode, after.st_uid, after.st_gid, after.st_size)
        assert result["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        return dict(fifo_replacement_not_read=True, descriptor_closed=True, concurrent_mutation_rejected=True,
                    error_text_not_exported=True, stat_unchanged=True)


result = {"behaviour": behaviour()}
if hasattr(m11stand.Bench, "recovery_record"):
    result["races"] = races()
Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
