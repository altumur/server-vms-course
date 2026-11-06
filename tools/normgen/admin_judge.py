"""Judge for the admin part (Architect, 2026-11-05): run the kit daemon as shipped, with admin_ops unimplemented.

  python3 tools/normgen/admin_judge.py [--kit <kit-directory>]

Without --kit, build_kit.build creates the required parts in a temporary directory. Build cmd/configstore and execute every non-daemon subcommand declared by daemon-flags.tsv with its required flags. Expect exit 1 and exactly `configstore <command>: not in this stage` on stderr (admin.Run -> NotInStage, rather than the old launch's `not implemented` or exit 2). With -no-such-flag or a different command's -max-body, expect exit 2 before admin.Run. Own commands from own.go (spoil-row) return exit 1 before flag parsing, since their arguments are outside this form.

The roster comes from gen_admin.commands, not this file. A declared subcommand missing from INVOKE fails the judge. Non-execution fails. Result: `admin: N/N PASS|FAIL`; exit 0 means PASS."""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "kit"))
import build_kit  # noqa: E402
import gen_admin  # noqa: E402

MODULE = build_kit.L.module
PARTS = ("door", "flags", "refusals", "stagetests", "launch", "core", "admin")
# Subcommand -> argv from the form ({d}: data directory, {f}: file), including required flags.
INVOKE = {
    "recover": ["-id", "s1", "-dir", "{d}", "-isolated", "-peers", "s2@127.0.0.1:7001/127.0.0.1:7002"],
    "restore": ["-dir", "{d}", "--from", "{f}"],
    "import": ["-dir", "{d}", "--from", "{f}"],
    "status": [],
    "join": [],
    "leave": [],
    "admit": ["s2"],
    "backup": ["{f}"],
    "rights": [],
}
OWN = {"spoil-row": ["-dir", "{d}", "-key", "acc/k", "-what", "body"]}


def build_binary(kit, work):
    store = Path(kit) / build_kit.L.kit_dir
    (store / "go.mod").write_text(f"module {MODULE}\n\ngo 1.22\n", encoding="utf-8")
    env = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
    exe = Path(work) / "configstore"
    done = subprocess.run(["go", "build", "-o", str(exe), "./cmd/configstore"], cwd=store, capture_output=True,
                          text=True, env=env)
    if done.returncode:
        raise RuntimeError(f"go build ./cmd/configstore: {done.stderr[-2000:]}")
    return exe


def judge(kit=None):
    errors, cases = [], []
    with tempfile.TemporaryDirectory(prefix="admin-judge-") as t:
        t = Path(t)
        if kit is None:
            kit = t / "kit"
            build_kit.build(kit, MODULE, PARTS)
        else:
            shutil.copytree(kit, t / "kit")
            kit = t / "kit"
        try:
            exe = build_binary(kit, t)
        except RuntimeError as exc:
            print(f"FAIL {exc}")
            print("admin: 0/0 FAIL (no binary)")
            return 1
        data, file = t / "data", t / "copy.jsonl"
        data.mkdir()
        file.write_text("", encoding="utf-8")
        cmds, _ = gen_admin.commands()
        for cmd in cmds:
            if cmd not in INVOKE:
                errors.append(f"{cmd}: no invocation in admin_judge.INVOKE (the form names it)")
                continue
            words = [w.replace("{d}", str(data)).replace("{f}", str(file)) for w in INVOKE[cmd]]
            cases.append((cmd, [cmd, *words], 1, f"configstore {cmd}: not in this stage\n"))
            cases.append((f"{cmd} -no-such-flag", [cmd, "-no-such-flag", *words], 2, None))
            cases.append((f"{cmd} -max-body", [cmd, "-max-body", "1", *words], 2, None))
        for cmd, words in OWN.items():
            words = [w.replace("{d}", str(data)) for w in words]
            cases.append((cmd, [cmd, *words], 1, f"configstore {cmd}: not in this stage\n"))
        ok = 0
        for name, argv, code, stderr in cases:
            try:
                done = subprocess.run([str(exe), *argv], capture_output=True, text=True, timeout=20,
                                      env={"PATH": os.environ.get("PATH", "")})
            except subprocess.TimeoutExpired:
                errors.append(f"{name}: no exit in 20 s")
                continue
            why = []
            if done.returncode != code:
                why.append(f"exit {done.returncode}, want {code}")
            if stderr is not None and done.stderr != stderr:
                why.append(f"stderr {done.stderr[:200]!r}, want {stderr!r}")
            if why:
                errors.append(f"{name}: {'; '.join(why)}")
            else:
                ok += 1
    for e in errors:
        print("FAIL", e)
    verdict = "PASS" if not errors and cases and ok == len(cases) else "FAIL"
    print(f"admin: {ok}/{len(cases)} {verdict}")
    return 0 if verdict == "PASS" else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kit", help="a built kit directory (default: build_kit.build of the parts)")
    a = ap.parse_args(argv)
    try:
        return judge(a.kit)
    except build_kit.KitError as exc:
        print(f"admin_judge: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
