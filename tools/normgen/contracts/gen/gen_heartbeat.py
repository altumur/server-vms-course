"""The two foreign heartbeat families used by the contracts reader (coord103, ADR-0125 addendum (5)).

Use gen_families' schema mode in an isolated process: importing it in a P/01 kit must not select its flat mode,
or change the lesson of the caller. No separate schema interpreter and no edits to gen_families.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

NORMGEN = Path(__file__).resolve().parents[2]
OUT = NORMGEN / "contracts/go/heartbeat"

SCRIPT = r'''
import json
import gen_families as g

keys = {"<sub>/heartbeats/<имя>", "platform/resources/<server>/heartbeat"}
fams = [f for nn in ("03", "05") for f in g.families(nn) if f["key"] in keys]
assert g.DOC_MODE and {f["key"] for f in fams} == keys
generated = g.gofmt(g.go_module(fams, "03+P/05"))
runtime = g.RUNTIME_DOC.read_text(encoding="utf-8")
def package(text):
    return text.replace("\npackage families\n", "\npackage heartbeat\n", 1).replace("// Package families", "// Package heartbeat")
print(json.dumps({"families.go": package(generated), "runtime.go": package(runtime)}))
'''


def render():
    done = subprocess.run([sys.executable, "-c", SCRIPT], cwd=NORMGEN,
                          env=dict(os.environ, NORMGEN_LESSON="03-worker"),
                          capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def sources():
    """All family-generator inputs, including catalog selection and the copied schema runtime."""
    done = subprocess.run([sys.executable, "-c", '''
import json
import gen_families as g
keys = {"<sub>/heartbeats/<имя>", "platform/resources/<server>/heartbeat"}
fams = [f for nn in ("03", "05") for f in g.families(nn) if f["key"] in keys]
paths = [g.CATALOG, g.KEYS_README, g.RUNTIME_DOC, g.HERE / "gen_families.py", g.HERE / "gen_checks.py"]
paths += [p for f in fams for p in f["sources"] if p is not None]
print(json.dumps([str(p) for p in dict.fromkeys(paths)]))
'''], cwd=NORMGEN, env=dict(os.environ, NORMGEN_LESSON="03-worker"),
                          capture_output=True, text=True, check=True)
    return [Path(p) for p in json.loads(done.stdout)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in render().items():
        (OUT / name).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
