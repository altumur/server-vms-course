"""Build the external door judge's stand (ADR-0125 addendum 1, item 1): writecheck+door and kit/stub, an in-memory store without N3 semantics, for the P/01.1 runner.

  python tools/normgen/kit/build_stub.py <dst> [--spec-version <full-export-SHA>] [--go-build]
Create01-store with build_kit output, stubstore go.mod/cmd and format2 acceptance.yaml, plus format1 assembly.yaml and SPEC_VERSION. The caller initializes/commits the destination Git repository required by the runner. The stub uses X-Configstore-Role. request_line_limit8192 is declared but net/http does not enforce strict framing, so manual-frame extra probes are excluded from the door metric. --go-build builds bin/stubstore; otherwise the runner's build phase does so. Run only through the server queue, not here."""
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

PROFILE = r'''# P/01 door stub: writecheck+door with an in-memory store, without N3 semantics.
# Not a lesson implementation: measure only core-independent P/01.1 steps.
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
  role_header: X-Configstore-Role
  request_line_limit: 8192
artifacts:
  stubstore: bin/stubstore
'''

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
    manifest = build_kit.build(dst, MODULE, ("door",))
    store = dst / "01-store"
    (store / "go.mod").write_text(f"module {MODULE}\n\ngo 1.22\n", encoding="utf-8")
    cmd = store / "cmd/stubstore"
    cmd.mkdir(parents=True, exist_ok=True)
    src = (HERE / "stub/main.go").read_text(encoding="utf-8")
    active = (build_kit.ROOT / build_kit.gen_flags.P01_CONSTANTS).is_file()
    src = build_kit.gen_flags.bind_p01(src, "stub", active, error=build_kit.KitError)
    if '"kitmodule/internal/' not in src:
        raise build_kit.KitError("stub/main.go: no import kitmodule/internal/… to rewrite")
    (cmd / "main.go").write_text(src.replace('"kitmodule/internal/', f'"{MODULE}/internal/'), encoding="utf-8")
    sha = spec_version(spec)
    if len(sha) != 40:
        raise build_kit.KitError(f"spec_version {sha!r}: a full 40-hex commit of cammeta-specs")
    (store / "acceptance.yaml").write_text(PROFILE.format(spec=sha), encoding="utf-8")
    (dst / "assembly.yaml").write_text(ASSEMBLY, encoding="utf-8")
    (dst / "SPEC_VERSION").write_text(sha + "\n", encoding="utf-8")   # Runner requires SPEC_VERSION at the implementation Git root.
    if go_build:
        import os
        env = dict(os.environ, **GOENV_FLAGS)
        # macOS26 dyld requires LC_UUID, absent from Go 1.22's internal linker for net binaries; use the external
        # linker locally. Linux uses the profile's build command unchanged.
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
