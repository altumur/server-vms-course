#!/usr/bin/env python3
"""Static as-built snapshots of one lesson of a Go implementation (ADR-0123).

Writes <out>/<implementation>/<lesson>/{params,refusals,deps}.yaml:

  params    flags (flag.*), environment variable names (os.Getenv,
            os.LookupEnv), top-level constants, and the parsed `-h` output of
            each main package when it builds offline;
  refusals  refusal literals: HTTP code + kind + word, error words, process
            exits; what could not be bound goes to `unresolved`;
  deps      package import graph: internal, stdlib, external modules.

Go syntax is read by goextract (go/ast, stdlib only). The subject tree is
only read; the `-h` build runs on a copy in a temporary directory with
GOPROXY=off. Environment values are never read; host paths are masked.

Usage:
  asbuilt.py --impl cammeta-c-go --root /path/to/cammeta-c-go --lesson 01-store \
             [--spec-repo /path/to/cammeta-specs] [--out tools/asbuilt/out] [--no-help]
"""

import argparse
import hashlib
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import yamlio  # noqa: E402

VERSION = "asbuilt/1"
GO_ENV = {
    "GOFLAGS": "-mod=mod",
    "GOPROXY": "off",
    "GOWORK": "off",
    "GOTOOLCHAIN": "local",
    "GOMEMLIMIT": "768MiB",
    "GOMAXPROCS": "2",
    "GONOSUMDB": "*",
}
HELP_TIMEOUT = 10
BUILD_TIMEOUT = 300

# Host filesystem paths: masked in every snapshot (ADR-0123 доп. (1) п. 4).
HOST_PATH = re.compile(
    r"(?<![\w.:/])(?:~|/(?:etc|run|var|usr|opt|home|Users|tmp|private|root|srv|proc|dev|sys|Library|Volumes|mnt|nix))(?:/[^\s\"'{}()\[\],;]*)?"
)
LEAK = re.compile(r"/Users/|/home/|/private/|/var/folders/|/tmp/")


def mask(text):
    """Replace host paths with <path:sha256-prefix>; the digest keeps equality checkable."""
    if not isinstance(text, str):
        return text

    def sub(m):
        return "<path:%s>" % hashlib.sha256(m.group(0).encode()).hexdigest()[:12]

    return HOST_PATH.sub(sub, text)


def go_env():
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "GOPATH", "GOCACHE", "GOMODCACHE", "GOROOT", "TMPDIR")}
    env.update({k: v for k, v in GO_ENV.items() if v})
    return env


def run(cmd, cwd=None, env=None, timeout=BUILD_TIMEOUT, check=True):
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError("%s failed (%d): %s" % (" ".join(map(str, cmd[:3])), p.returncode, p.stderr.strip()[-2000:]))
    return p


def build_extractor(work):
    exe = Path(work) / "goextract"
    run(["go", "build", "-trimpath", "-o", str(exe), "."], cwd=HERE / "goextract", env=go_env())
    return exe


def extract(exe, root, lesson):
    p = run([str(exe), "-root", str(root), "-start", lesson], timeout=BUILD_TIMEOUT)
    return json.loads(p.stdout)


def git(repo, *args):
    p = run(["git", "-C", str(repo), *args], check=False, timeout=60)
    return p.stdout.strip() if p.returncode == 0 else ""


def at(r):
    return "%s:%d" % (r["file"], r["line"]) if r.get("line") else r["file"]


def lesson_scope(pkg_dir, lesson):
    return "lesson" if pkg_dir == lesson or pkg_dir.startswith(lesson + "/") else "shared"


# ---------------- -h output ----------------

HELP_FLAG = re.compile(r"^  -(\S+)(?: (\S+))?$")
HELP_DEFAULT = re.compile(r"\(default (.*)\)\s*$")


HELP_USAGE = re.compile(r"^Usage of (\S+?):?$")


def parse_help(text):
    """Return (flag set name or None, flags) from Go flag usage output."""
    flags, cur, set_name = [], None, None
    for line in text.splitlines():
        u = HELP_USAGE.match(line.strip())
        if u and set_name is None:
            set_name = u.group(1)
            continue
        m = HELP_FLAG.match(line)
        if m:
            cur = {"name": m.group(1), "type": m.group(2) or "bool", "usage": "", "default": None}
            flags.append(cur)
            continue
        if cur is not None and line.startswith("    \t"):
            u = line.strip()
            d = HELP_DEFAULT.search(u)
            if d:
                val = d.group(1)
                if val.startswith('"') and val.endswith('"'):
                    try:
                        val = json.loads(val)
                    except ValueError:
                        pass
                cur["default"] = mask(val)
                u = u[: d.start()].rstrip()
            cur["usage"] = (cur["usage"] + " " + u).strip()
    return set_name, sorted(flags, key=lambda f: f["name"])


def help_outputs(raw, root, lesson, work):
    """Build each main package of the lesson on a copy and parse `-h`."""
    mains = [p for p in raw["packages"] if p["name"] == "main" and lesson_scope(p["dir"], lesson) == "lesson"]
    results = []
    if not mains:
        return results
    tree = Path(work) / "tree"
    for name in ("go.mod", "go.sum"):
        if (Path(root) / name).exists():
            tree.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(root) / name, tree / name)
    for p in raw["packages"]:
        for f in p["files"]:
            dst = tree / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(root) / f, dst)
    home = Path(work) / "home"
    home.mkdir(exist_ok=True)
    for m in sorted(mains, key=lambda p: p["dir"]):
        exe = Path(work) / "bin" / Path(m["dir"]).name
        entry = {"package": m["dir"], "status": "ok", "exit": None, "flags": [], "set": None}
        built = False
        for extra in ([], ["-ldflags=-linkmode=external"]):
            b = run(["go", "build", *extra, "-o", str(exe), "./" + m["dir"]], cwd=tree, env=go_env(), check=False)
            if b.returncode != 0:
                entry["status"] = "build-failed"
                continue
            try:
                h = subprocess.run([str(exe), "-h"], cwd=str(home), env={"PATH": "/usr/bin:/bin", "HOME": str(home)},
                                   capture_output=True, text=True, timeout=HELP_TIMEOUT, stdin=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                entry["status"] = "help-timeout"
                built = True
                break
            if h.returncode < 0:
                entry["status"] = "help-crashed"
                continue
            entry["status"] = "ok"
            entry["exit"] = h.returncode
            entry["set"], entry["flags"] = parse_help(h.stdout + "\n" + h.stderr)
            if entry["set"] and Path(entry["set"]).is_absolute():
                entry["set"] = Path(entry["set"]).name
            built = True
            break
        if not built and entry["status"] == "ok":
            entry["status"] = "build-failed"
        results.append(entry)
    return results


# ---------------- snapshots ----------------


def header(args, raw, commit, dirty, pin):
    return {
        "commit": commit,
        "dirty": dirty,
        "extractor": "%s+%s" % (VERSION, raw["extractor"]),
        "implementation": args.impl,
        "lesson": args.lesson,
        "module": raw["module"],
        "source": "static",
        "spec": pin,
    }


def unresolved(raw, what):
    return sorted(
        ({"at": at(u), "expr": mask(u["expr"]), "func": u["func"], "reason": u["reason"], "what": u["what"]}
         for u in raw["unresolved"] if u["what"] in what),
        key=lambda u: (u["at"], u["what"], u["expr"]),
    )


def params_snapshot(hdr, raw, helps, lesson):
    flags = []
    for f in raw["flags"]:
        flags.append({
            "at": at(f), "bound": f["bound"], "default": mask(f["value"]) if f["value"] != "" or f["default"] == '""' else None,
            "expr": mask(f["default"]), "func": f["func"], "method": f["method"], "name": f["name"],
            "set": f["set"], "type": f["type"], "usage": mask(f["usage"]),
        })
    flags.sort(key=lambda f: (f["name"], f["set"], f["at"]))
    env = sorted(({"at": at(e), "call": e["call"], "func": e["func"], "name": e["name"]} for e in raw["env"]),
                 key=lambda e: (e["name"], e["at"]))
    consts = []
    for c in raw["consts"]:
        pkgdir = c["file"].rsplit("/", 1)[0]
        consts.append({
            "at": at(c), "exported": c["exported"], "expr": mask(c["expr"]), "name": c["name"],
            "pkg": c["pkg"], "scope": lesson_scope(pkgdir, lesson), "type": c["type"], "value": mask(c["value"]),
        })
    consts.sort(key=lambda c: (c["pkg"], c["name"], c["at"]))
    return {
        "header": hdr,
        "consts": consts,
        "env": env,
        "flags": flags,
        "help": sorted(helps, key=lambda h: h["package"]),
        "unresolved": unresolved(raw, {"flag", "env", "const", "file"}),
    }


def refusal_record(r, lesson):
    pkgdir = r["file"].rsplit("/", 1)[0]
    rec = {
        "at": at(r), "func": r["func"], "pkg": r["pkg"], "scope": lesson_scope(pkgdir, lesson),
        "via": r["via"], "words": [mask(w) for w in (r["words"] or [])],
    }
    if r["channel"] in ("http", "wrapper"):
        rec.update({"code": r["code"], "kind": r["kind"], "fields": sorted(r["fields"] or []),
                    "resolved": r["resolved"], "word_source": r["word_source"] or "none"})
    return rec


def refusals_snapshot(hdr, raw, lesson):
    http = [refusal_record(r, lesson) for r in raw["refusals"] if r["channel"] == "http"]
    errs = [refusal_record(r, lesson) for r in raw["refusals"] if r["channel"] == "error"]
    wraps = [refusal_record(r, lesson) for r in raw["wrappers"]]
    http.sort(key=lambda r: (r["code"], r["kind"], r["at"], r["words"]))
    wraps.sort(key=lambda r: (r["code"], r["kind"], r["at"]))
    errs.sort(key=lambda r: (r["scope"], r["at"], r["words"]))
    pairs = {}
    for r in http:
        pairs.setdefault("%d %s" % (r["code"], r["kind"]), 0)
        pairs["%d %s" % (r["code"], r["kind"])] += 1
    exits = sorted(({"at": at(x), "call": x["call"], "code": x["code"], "func": x["func"], "pkg": x["pkg"]} for x in raw["exits"]),
                   key=lambda x: x["at"])
    return {
        "header": hdr,
        "errors": errs,
        "exits": exits,
        "http": http,
        "pairs": [{"pair": k, "sites": v} for k, v in sorted(pairs.items(), key=lambda kv: (int(kv[0].split()[0]), kv[0]))],
        "unresolved": unresolved(raw, {"refusal", "error", "exit", "file"}),
        "wrappers": wraps,
    }


def is_stdlib(path):
    return "." not in path.split("/", 1)[0]


def module_of(path, requires):
    best = None
    for r in requires:
        if path == r or path.startswith(r + "/"):
            if best is None or len(r) > len(best):
                best = r
    return best


def deps_snapshot(hdr, raw, lesson):
    mod = raw["module"]
    pkgs, used = [], set()
    lesson_dirs = re.compile(r"^\d\d-[^/]+")
    cross = []
    for p in raw["packages"]:
        internal, stdlib, external = [], [], []
        for imp in p["imports"]:
            if imp == mod or imp.startswith(mod + "/"):
                internal.append(imp)
                target = imp[len(mod) + 1:]
                m = lesson_dirs.match(target)
                if m and lesson_scope(p["dir"], lesson) == "lesson" and m.group(0) != lesson:
                    cross.append({"from": p["path"], "to": imp})
            elif is_stdlib(imp):
                stdlib.append(imp)
            else:
                m = module_of(imp, raw["requires"] or [])
                external.append({"module": m, "path": imp})
                if m:
                    used.add(m)
        pkgs.append({
            "dir": p["dir"], "external": sorted(external, key=lambda e: e["path"]), "files": len(p["files"]),
            "internal": sorted(internal), "name": p["name"], "path": p["path"],
            "scope": lesson_scope(p["dir"], lesson), "stdlib": sorted(stdlib),
        })
    pkgs.sort(key=lambda p: p["path"])
    return {
        "header": hdr,
        "cross_lesson": sorted(cross, key=lambda c: (c["from"], c["to"])),
        "modules": {"required": sorted(raw["requires"] or []), "used": sorted(used)},
        "packages": pkgs,
        "summary": {
            "external": len({e["path"] for p in pkgs for e in p["external"]}),
            "internal_edges": sum(len(p["internal"]) for p in pkgs),
            "packages": len(pkgs),
            "stdlib": len({s for p in pkgs for s in p["stdlib"]}),
        },
    }


def check_leaks(name, text):
    m = LEAK.search(text)
    if m:
        raise RuntimeError("host path leak in %s: %r" % (name, text[max(0, m.start() - 40): m.end() + 40]))


def write_snapshots(dest, snaps):
    dest.mkdir(parents=True, exist_ok=True)
    for name, doc in snaps.items():
        text = yamlio.dump(doc)
        check_leaks(name, text)
        (dest / (name + ".yaml")).write_text(text, encoding="utf-8")


def resolve_pin(root, spec_repo):
    f = Path(root) / "SPEC_VERSION"
    if not f.exists():
        return ""
    pin = f.read_text().strip()
    if spec_repo:
        full = git(spec_repo, "rev-parse", "--verify", "--quiet", pin + "^{commit}")
        if full:
            return full
    return pin


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--impl", required=True, help="implementation name, e.g. cammeta-c-go")
    ap.add_argument("--root", required=True, help="module root of the implementation (read only)")
    ap.add_argument("--lesson", required=True, help="lesson directory under the root, e.g. 01-store")
    ap.add_argument("--spec-repo", help="export repository holding the implementation's spec pin")
    ap.add_argument("--out", default=str(HERE / "out"), help="output root")
    ap.add_argument("--no-help", action="store_true", help="skip building main packages for -h")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    with tempfile.TemporaryDirectory(prefix="asbuilt-") as work:
        exe = build_extractor(work)
        raw = extract(exe, root, args.lesson)
        helps = [] if args.no_help else help_outputs(raw, root, args.lesson, work)
    commit = git(root, "rev-parse", "HEAD")
    dirty = bool(git(root, "status", "--porcelain", "--", args.lesson))
    hdr = header(args, raw, commit, dirty, resolve_pin(root, args.spec_repo))
    snaps = {
        "params": params_snapshot(hdr, raw, helps, args.lesson),
        "refusals": refusals_snapshot(hdr, raw, args.lesson),
        "deps": deps_snapshot(hdr, raw, args.lesson),
    }
    dest = Path(args.out) / args.impl / args.lesson
    write_snapshots(dest, snaps)
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    peak_mib = peak / (1 << 20) if sys.platform == "darwin" else peak / 1024
    print("asbuilt: %s/%s -> %s (child peak %.0f MiB)" % (args.impl, args.lesson, dest, peak_mib), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
