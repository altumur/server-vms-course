"""Судья части `launch` (ADR-0083 доп. (95) п. 3): пакет как есть (каркас и его пустое ядро) под раннером P/01.1.

  python3 tools/normgen/launch_judge.py stand <dst> --spec-version <SHA выгрузки>   # каталог реализации для раннера
  python3 tools/normgen/launch_judge.py job <in> --spec-version <SHA> [--acceptance <клон раннера>] [--specs <клон выгрузки>]
  python3 tools/normgen/launch_judge.py judge <out/report> [--json итог]

stand — пакет Б с частями door, flags, stagetests, launch (build_kit.build) как есть, ничего не правится:
cmd/configstore/main.go — сгенерированный каркас, internal/coreadapter/open.go — заглушка пакета (ErrNotImplemented),
на ней каркас отвечает своим пустым ядром launch.Empty (Get — всегда отсутствующая строка, прочее — 503); профиль 01-store/acceptance.yaml по справке KIT.md части launch (build
`go build -o bin/configstore ./cmd/configstore`, store — `-id store1 -dir {data} -sockets {rundir} -rights {rights} -max-body
{body_limit} -max-value {row_ceiling}`), assembly.yaml, SPEC_VERSION; <dst> — репозиторий Git (коммит делает stand).
job — вход очереди CT 103: RUN.py (раннер all.py --only P/01.1 --build), acceptance, specs на --spec-version, impl.
judge — мера этапа launch: gate accept:1.1:01-absent — сценарий 01-absent отчёта P-01.1-door.json целиком зелёный.
Нет отчёта, нет сценария, шаг без исхода — провал (отсутствие исполнения — отрицательный исход). Прочие сценарии —
сводкой, в меру не идут (их держит ядро модели).
Итог: `launch: 01-absent PASS|FAIL (…)`; код 0 — PASS.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "kit"))
import build_kit  # noqa: E402

MODULE = "p01store/01-store"
GATE = ("01-absent",)                      # forms/stages.tsv: launch — accept:1.1:01-absent
PARTS = ("door", "flags", "stagetests", "launch")

PROFILE = """# Судья части launch (tools/normgen/launch_judge.py, ADR-0083 доп. (95) п. 3): пакет как есть, пустое ядро каркаса.
format: 2
implementation: normgen-launch-frame
module: 01-store
spec_version: '{spec}'
build: 'go build -o bin/configstore ./cmd/configstore'
stand:
  store1: './bin/configstore -id store1 -dir {{data}} -sockets {{rundir}} -rights {{rights}} -max-body {{body_limit}} -max-value {{row_ceiling}}'
  store: './bin/configstore -id store1 -dir {{data}} -sockets {{rundir}} -rights {{rights}} -max-body {{body_limit}} -max-value {{row_ceiling}}'
keys:
  role: acc
  role_header: X-Configstore-Role
  request_line_limit: 8192
artifacts:
  configstore: bin/configstore
"""
ASSEMBLY = "format: 1\nmodules:\n  01-store: 01-store/acceptance.yaml\n"

RUN = """# Судья части launch (ADR-0083 доп. (95) п. 3): раннер P/01.1 --build на каркасе пакета с пустым ядром.
import os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
tmp = os.environ.get('TMPDIR', '/tmp')
env = dict(os.environ, CAMMETA_SPECS=os.path.join(here, 'specs'), GOCACHE=os.path.join(tmp, 'gocache'),
           GOFLAGS='-mod=mod', GOPROXY='off', GOWORK='off', GOTOOLCHAIN='local')
out = os.path.join(os.environ.get('CHECK_OUT', here), 'report')
code = subprocess.call([sys.executable, '-I', '-B', os.path.join(here, 'acceptance/runner/all.py'),
                        '--assembly', os.path.join(here, 'impl/assembly.yaml'), '--only', 'P/01.1',
                        '--build', '--out', out], env=env, cwd=here)
for name in sorted(os.listdir(out)) if os.path.isdir(out) else []:
    if name.endswith(('.json', '.txt')) and name not in ('inventory.json', 'commands.json'):
        sys.stdout.write('\\n=== ' + name + '\\n' + open(os.path.join(out, name), encoding='utf-8').read() + '\\n')
raise SystemExit(code)
"""


def git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def stand(dst, spec):
    if len(spec) != 40:
        raise build_kit.KitError(f"--spec-version {spec!r}: a full 40-hex commit of cammeta-specs")
    dst = Path(dst)
    manifest = build_kit.build(dst, MODULE, PARTS)
    store = dst / "01-store"
    (store / "go.mod").write_text(f"module {MODULE}\n\ngo 1.22\n", encoding="utf-8")
    (store / "acceptance.yaml").write_text(PROFILE.format(spec=spec), encoding="utf-8")
    (dst / "assembly.yaml").write_text(ASSEMBLY, encoding="utf-8")
    (dst / "SPEC_VERSION").write_text(spec + "\n", encoding="utf-8")
    (dst / ".gitignore").write_text("01-store/bin/\n", encoding="utf-8")
    git(["init", "-q"], dst)
    git(["add", "-A"], dst)
    git(["-c", "user.name=normgen", "-c", "user.email=normgen@localhost", "commit", "-q", "-m", "launch frame stand"], dst)
    return manifest


def job(dst, spec, acceptance, specs):
    dst = Path(dst)
    dst.mkdir(parents=True)
    (dst / "RUN.py").write_text(RUN, encoding="utf-8")
    git(["clone", "-q", str(acceptance), str(dst / "acceptance")], dst)
    git(["clone", "-q", str(specs), str(dst / "specs")], dst)
    git(["checkout", "-q", spec], dst / "specs")
    stand(dst / "impl", spec)                 # specs — с .git: предпроверка раннера читает его метаданные
    return dst


def judge(report, json_out=None):
    path = Path(report) / "P-01.1-door.json"
    errors, steps, summary = [], {}, {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        scenarios = doc["scenarios"]
        summary = {n: f"{sum(bool(s.get('ok')) for s in sc.get('steps', []))}/{len(sc.get('steps', []))}"
                   for n, sc in scenarios.items()}
    except FileNotFoundError:
        errors.append(f"no runner report {path}")
        scenarios = {}
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        errors.append(f"runner report {path} unreadable: {e!r}")
        scenarios = {}
    table = HERE.parent.parent / "Platform/01-store/acceptance/1/scenarios.tsv"
    want = {}
    for line in table.read_text(encoding="utf-8").splitlines():
        cells = line.split("\t")
        if line and not line.startswith("#") and cells[0] in GATE:
            want.setdefault(cells[0], []).append(cells[1])
    for name in GATE:
        sc = scenarios.get(name)
        if sc is None:
            errors.append(f"scenario {name}: no outcome in the report")
            continue
        got = {str(s["step"]): s for s in sc.get("steps", [])}
        for step in want.get(name, []):
            s = got.get(step)
            if s is None:
                errors.append(f"{name} step {step}: no outcome")
            elif s.get("ok") is not True:
                errors.append(f"{name} step {step}: {'; '.join(map(str, s.get('why') or []))[:300]}")
            steps[f"{name}/{step}"] = bool(s and s.get("ok") is True)
        if sc.get("error"):
            errors.append(f"{name}: {sc['error'][:300]}")
    if not want:
        errors.append(f"no steps of {GATE} in {table}")
    verdict = "PASS" if not errors and steps and all(steps.values()) else "FAIL"
    for e in errors:
        print("FAIL", e)
    green = sorted(n for n, s in summary.items() if s.split("/")[0] == s.split("/")[1] and s != "0/0")
    print(f"launch: {', '.join(GATE)} {verdict} ({sum(steps.values())}/{len(steps)} steps); other scenarios green with "
          f"the empty core, not counted: {len(green)}/{len(summary)}")
    if json_out:
        Path(json_out).write_text(json.dumps({"verdict": verdict, "steps": steps, "errors": errors,
                                              "scenarios": summary}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if verdict == "PASS" else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stand")
    s.add_argument("dst")
    s.add_argument("--spec-version", required=True)
    j = sub.add_parser("job")
    j.add_argument("dst")
    j.add_argument("--spec-version", required=True)
    j.add_argument("--acceptance", default="/home/pilot/cammeta-acceptance")
    j.add_argument("--specs", default="/home/pilot/cammeta-specs")
    d = sub.add_parser("judge")
    d.add_argument("report")
    d.add_argument("--json")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "stand":
            stand(a.dst, a.spec_version)
        elif a.cmd == "job":
            print(job(a.dst, a.spec_version, a.acceptance, a.specs))
        else:
            return judge(a.report, a.json)
    except (build_kit.KitError, subprocess.CalledProcessError) as exc:
        print(f"launch_judge: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
