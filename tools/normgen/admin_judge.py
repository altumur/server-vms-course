"""Судья части `admin` (Архитектор 2026-11-05): демон пакета как есть, подкоманды admin_ops без реализации.

  python3 tools/normgen/admin_judge.py [--kit <каталог пакета>]   (без --kit — build_kit.build частей пакета во временный)

Собирает cmd/configstore пакета и исполняет:
- каждую подкоманду формы daemon-flags.tsv (кроме daemon) с флагами по форме (обязательные даны) — ожидание: код 1,
  stderr ровно «configstore <подкоманда>: not in this stage» (admin.Run → NotInStage; не «not implemented» прежнего
  launch, не 2);
- каждую подкоманду с флагом вне формы (-no-such-flag) и с флагом чужой команды (-max-body — только daemon) — код 2
  (отказ формы флагов до admin.Run);
- свои команды own.go (spoil-row) — код 1, «not in this stage», до разбора флагов (их аргументы — не форма таблицы).
Набор подкоманд — из формы (gen_admin.commands), не из этого файла: подкоманда без вызова в INVOKE — провал судьи.
Отсутствие исполнения — отрицательный исход. Итог: `admin: N/N PASS|FAIL`; код 0 — PASS.
"""
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

MODULE = "p01store/01-store"
PARTS = ("door", "flags", "refusals", "stagetests", "launch", "core", "admin")
# Подкоманда → слова командной строки по форме ({d} — каталог данных, {f} — файл): обязательные флаги даны.
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
    store = Path(kit) / "01-store"
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
