"""Стенд внешнего судьи двери (ADR-0125 доп. (1) п. 1): пакет Б с частями writecheck и door + заглушка демона
tools/normgen/kit/stub (хранилище в памяти без смысла Н3) — каталог реализации для раннера приёмки P/01.1.

Запуск: python tools/normgen/kit/build_stub.py <dst> [--spec-version <полный SHA выгрузки cammeta-specs>] [--go-build]

Кладёт в <dst>: 01-store/ (пакет: build_kit.build(parts writecheck, door), go.mod модуля stubstore, cmd/stubstore,
acceptance.yaml формата 2) и assembly.yaml (format 1, один модуль 01-store). --go-build собирает 01-store/bin/stubstore
(иначе сборка — фаза build раннера: `go build -o bin/stubstore ./cmd/stubstore`). Прогон — только на сервере через
очередь, не здесь.
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_kit  # noqa: E402

MODULE = "stubstore"
SPECS = Path("/Users/murat/w2c/cammeta-specs")
GOENV_FLAGS = {"GOPROXY": "off", "GOFLAGS": "-mod=mod", "GOWORK": "off", "GOTOOLCHAIN": "local"}

PROFILE = """# Заглушка двери P/01 (tools/normgen/kit/build_stub.py, ADR-0125 доп. (1) п. 1): пакет Б writecheck + door и хранилище
# в памяти без смысла Н3. Не реализация урока: мера — шаги P/01.1, не зависящие от ядра.
format: 2
implementation: normgen-door-stub
module: 01-store
spec_version: '{spec}'
build: 'go build -o bin/stubstore ./cmd/stubstore'
stand:
  store1: './bin/stubstore -dir {{data}} -admin {{socket}} -rights {{rights}} -max-body {{body_limit}} -max-value {{row_ceiling}}'
  store: './bin/stubstore -dir {{data}} -admin {{socket}} -rights {{rights}} -max-body {{body_limit}} -max-value {{row_ceiling}}'
keys:
  role: acc
artifacts:
  stubstore: bin/stubstore
"""

ASSEMBLY = "format: 1\nmodules:\n  01-store: 01-store/acceptance.yaml\n"


def spec_version(given):
    if given:
        return given
    try:
        return subprocess.run(["git", "-C", str(SPECS), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise build_kit.KitError("no --spec-version and no git HEAD of /Users/murat/w2c/cammeta-specs")


def build(dst, spec=None, go_build=False):
    dst = Path(dst)
    manifest = build_kit.build(dst, MODULE, ("writecheck", "door"))
    store = dst / "01-store"
    (store / "go.mod").write_text(f"module {MODULE}\n\ngo 1.22\n", encoding="utf-8")
    cmd = store / "cmd/stubstore"
    cmd.mkdir(parents=True, exist_ok=True)
    src = (HERE / "stub/main.go").read_text(encoding="utf-8")
    if '"kitmodule/internal/' not in src:
        raise build_kit.KitError("stub/main.go: no import kitmodule/internal/… to rewrite")
    (cmd / "main.go").write_text(src.replace('"kitmodule/internal/', f'"{MODULE}/internal/'), encoding="utf-8")
    sha = spec_version(spec)
    if len(sha) != 40:
        raise build_kit.KitError(f"spec_version {sha!r}: a full 40-hex commit of cammeta-specs")
    (store / "acceptance.yaml").write_text(PROFILE.format(spec=sha), encoding="utf-8")
    (dst / "assembly.yaml").write_text(ASSEMBLY, encoding="utf-8")
    if go_build:
        import os
        env = dict(os.environ, **GOENV_FLAGS)
        # macOS 26 dyld требует LC_UUID, внутренний компоновщик Go 1.22 его не пишет для бинаря с net: локально —
        # внешний компоновщик; на сервере (Linux) сборка — командой build профиля как есть.
        link = ["-ldflags=-linkmode=external"] if sys.platform == "darwin" else []
        for args in (["build", *link, "-o", "bin/stubstore", "./cmd/stubstore"], ["vet", "./..."]):
            done = subprocess.run(["go", *args], cwd=store, env=env, capture_output=True, text=True)
            if done.returncode:
                raise build_kit.KitError(f"go {' '.join(args)}: {done.stdout}{done.stderr}")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dst")
    ap.add_argument("--spec-version", default=None)
    ap.add_argument("--go-build", action="store_true")
    args = ap.parse_args(argv)
    try:
        m = build(args.dst, args.spec_version, args.go_build)
    except build_kit.KitError as exc:
        print(f"build_stub: {exc}", file=sys.stderr)
        return 1
    print(f"build_stub: {args.dst}: kit {m['lines']}, profile 01-store/acceptance.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
