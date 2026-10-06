"""probe_yaml_alike.py — BOTH trees (ADR-0019 «one YAML», ADR-0012): every real spec of the course (Source/vms,
Source/tests/testdata/testsub*) and of the product (vmsworker/vms, vmsworker/w2cplatform/testdata) is read by PyYAML
(the course's `SubsystemSpec.load`) and by the product's `ParseYAML` (probes/go/yamldump), and the two trees of data
compared. Expected: identical for every file; a difference is a spec the two loaders read as different specs.
Usage: python probe_yaml_alike.py <course root> <product root> <yamldump binary>"""
import glob, json, math, os, subprocess, sys
import yaml

course, product, dump = sys.argv[1], sys.argv[2], sys.argv[3]
files = sorted(glob.glob(f"{course}/Source/vms/*.subsystem.yaml") + glob.glob(f"{course}/Source/tests/testdata/testsub*.yaml")
               + glob.glob(f"{product}/vmsworker/vms/*.subsystem.yaml") + glob.glob(f"{product}/vmsworker/w2cplatform/testdata/*.yaml"))

def norm(v):
    if isinstance(v, dict):
        return {str(k): norm(x) for k, x in v.items()}
    if isinstance(v, list):
        return [norm(x) for x in v]
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return f"<float {v}>"
    if isinstance(v, float) and v.is_integer():
        return v                                    # 1.0 vs 1: compared as numbers below
    return v

def diff(a, b, at=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a: yield f"{at}.{k}: only Go reads it"
            elif k not in b: yield f"{at}.{k}: only PyYAML reads it (Go dropped it)"
            else: yield from diff(a[k], b[k], f"{at}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b): yield f"{at}: list of {len(a)} (PyYAML) vs {len(b)} (Go)"
        for i, (x, y) in enumerate(zip(a, b)): yield from diff(x, y, f"{at}[{i}]")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        if a != b: yield f"{at}: {a!r} vs {b!r}"
    elif a != b or type(a) is not type(b):
        yield f"{at}: PyYAML {a!r} vs Go {b!r}"

out = subprocess.run([dump, *files], capture_output=True, text=True, timeout=120).stdout.splitlines()
go = {}
for ln in out:
    f, rest = ln.split("\t", 1)
    go[f] = rest
bad = 0
for f in files:
    with open(f, encoding="utf-8") as fh:
        py = norm(yaml.safe_load(fh))
    g = go.get(f, "ERROR\tno output")
    if g.startswith("ERROR"):
        print(f"DIFF {os.path.relpath(f, os.path.dirname(course))}: Go refuses: {g}"); bad += 1; continue
    ds = list(diff(py, json.loads(g)))
    print(("SAME " if not ds else "DIFF ") + os.path.relpath(f, os.path.dirname(course)) + "".join(f"\n    {d}" for d in ds[:12]))
    bad += bool(ds)
print(f"{len(files)} files, {bad} read differently")
