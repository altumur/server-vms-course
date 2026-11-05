#!/usr/bin/env python3
"""Run snapshot `keys` from a saved storage journal and run passport (ADR-0123).

Determinism belongs to the extraction, not to the live stand (ADR-0123
доп. (2) п. 1): repeated extraction from one unchanged set of inputs — the
implementation at its SHA, the saved journal, the passport — gives the same
bytes, and the header carries the hashes of those inputs. Two independent
runs of the stand are not compared byte for byte: a transient refusal, another
admissible outcome of an operation, another set of refusals met are facts of
the snapshot and normalisation does not erase them. `diff` compares two run
snapshots by meaning: it lists the differing observations and the coverage.

Inputs (the collector of the runner writes them; the form is provisional
until the runner gives the collector, plan step 5):

  journal   JSON lines, one storage call each: op, key or prefix, outcome,
            and role or port of the calling socket; ts, pid and other fields
            are dropped;
  passport  JSON object: implementation, lesson, commit (implementation SHA),
            spec (export pin), runner (runner pin), profile (stand profile),
            targets and steps executed, ports {port: socket role}.

Normalisation (доп. (1) п. 2): ports are replaced by roles, time and PID are
dropped, keys are cut to their prefix (up to the last `/`), sets are sorted,
host paths are masked.

Usage:
  runsnap.py extract --journal J --passport P [--root IMPL] [--out tools/asbuilt/out]
  runsnap.py diff A/keys.yaml B/keys.yaml
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import yamlio  # noqa: E402
from asbuilt import VERSION, check_leaks, mask  # noqa: E402

RUN_VERSION = VERSION + "+runsnap/1"
PASSPORT_FIELDS = ("implementation", "lesson", "commit", "spec", "runner", "profile", "targets", "steps", "ports")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prefix_of(rec):
    if rec.get("prefix") is not None:
        return mask(str(rec["prefix"]))
    key = str(rec.get("key", ""))
    cut = key.rfind("/")
    return mask(key[: cut + 1] if cut >= 0 else key)


def role_of(rec, ports):
    if rec.get("role"):
        return str(rec["role"]), None
    port = rec.get("port")
    if port is not None and str(port) in ports:
        return ports[str(port)], None
    return "<unmapped>", "no role for port %s" % port if port is not None else "no role or port"


def header(passport, journal_path, passport_path):
    return {
        "commit": passport["commit"],
        "extractor": RUN_VERSION,
        "implementation": passport["implementation"],
        "inputs": {"journal": sha256(journal_path), "passport": sha256(passport_path)},
        "lesson": passport["lesson"],
        "profile": passport["profile"],
        "runner": passport["runner"],
        "source": "run",
        "spec": passport["spec"],
        "steps": sorted(set(passport["steps"])),
        "targets": sorted(set(passport["targets"])),
    }


def keys_snapshot(journal_path, passport_path):
    passport = json.loads(Path(passport_path).read_text(encoding="utf-8"))
    missing = [f for f in PASSPORT_FIELDS if f not in passport]
    if missing:
        raise ValueError("runsnap: passport lacks %s" % ", ".join(missing))
    ports = {str(k): str(v) for k, v in passport["ports"].items()}
    calls, unresolved = {}, {}
    for n, line in enumerate(Path(journal_path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        rec = json.loads(line)
        role, why = role_of(rec, ports)
        unit = (role, str(rec["op"]), prefix_of(rec))
        outcomes = calls.setdefault(unit, {})
        outcome = str(rec["outcome"])
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        if why:
            unresolved.setdefault((why, unit), 0)
            unresolved[(why, unit)] += 1
    keys = [{"op": op, "outcomes": [{"count": c, "outcome": o} for o, c in sorted(outs.items())],
             "prefix": prefix, "role": role}
            for (role, op, prefix), outs in sorted(calls.items())]
    return {
        "header": header(passport, journal_path, passport_path),
        "keys": keys,
        "unresolved": [{"calls": c, "op": u[1], "prefix": u[2], "reason": why, "role": u[0]}
                       for (why, u), c in sorted(unresolved.items())],
    }


def git_head(root):
    p = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ""


def extract(journal, passport, out, root=None):
    """Write <out>/<impl>/<lesson>/keys.yaml; return its path."""
    snap = keys_snapshot(journal, passport)
    hdr = snap["header"]
    if root is not None:
        head = git_head(root)
        if head != hdr["commit"]:
            raise ValueError("runsnap: passport commit %s is not the implementation HEAD %s" % (hdr["commit"][:12], head[:12]))
    text = yamlio.dump(snap)
    check_leaks("keys.yaml", text)
    dest = Path(out) / hdr["implementation"] / hdr["lesson"]
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "keys.yaml").write_text(text, encoding="utf-8")
    return dest / "keys.yaml"


def diff(a, b):
    """Compare two run snapshots by meaning; return a list of differences.

    Kinds: header (an identity field differs: commit, spec, implementation,
    lesson — the runs are not of one build), coverage (targets or steps
    executed by one run only), only_a / only_b (a call met in one run only),
    outcomes (one call, other outcomes). Counts of one outcome and input
    hashes are not differences of meaning.
    """
    out = []
    ha, hb = a["header"], b["header"]
    for f in ("implementation", "lesson", "commit", "spec"):
        if ha[f] != hb[f]:
            out.append({"kind": "header", "unit": f, "a": ha[f], "b": hb[f]})
    for f in ("targets", "steps"):
        sa, sb = set(ha[f]), set(hb[f])
        if sa != sb:
            out.append({"kind": "coverage", "unit": f, "a": sorted(sa - sb), "b": sorted(sb - sa)})
    ka = {(k["role"], k["op"], k["prefix"]): sorted(o["outcome"] for o in k["outcomes"]) for k in a["keys"]}
    kb = {(k["role"], k["op"], k["prefix"]): sorted(o["outcome"] for o in k["outcomes"]) for k in b["keys"]}
    for unit in sorted(set(ka) | set(kb)):
        name = " ".join(unit)
        if unit not in kb:
            out.append({"kind": "only_a", "unit": name, "a": ka[unit], "b": []})
        elif unit not in ka:
            out.append({"kind": "only_b", "unit": name, "a": [], "b": kb[unit]})
        elif ka[unit] != kb[unit]:
            out.append({"kind": "outcomes", "unit": name, "a": ka[unit], "b": kb[unit]})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="build keys.yaml from a saved journal and passport")
    e.add_argument("--journal", required=True)
    e.add_argument("--passport", required=True)
    e.add_argument("--root", help="implementation root: its HEAD must equal the passport commit")
    e.add_argument("--out", default=str(HERE / "out"))
    d = sub.add_parser("diff", help="compare two run snapshots by meaning")
    d.add_argument("a")
    d.add_argument("b")
    args = ap.parse_args(argv)
    if args.cmd == "extract":
        path = extract(args.journal, args.passport, args.out, args.root)
        print("runsnap: -> %s" % path, file=sys.stderr)
        return 0
    a = yamlio.load(Path(args.a).read_text(encoding="utf-8"))
    b = yamlio.load(Path(args.b).read_text(encoding="utf-8"))
    for row in diff(a, b):
        print("\t".join([row["kind"], row["unit"], json.dumps(row["a"], ensure_ascii=False),
                         json.dumps(row["b"], ensure_ascii=False)]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
