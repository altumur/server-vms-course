"""P03.26: the registry, the assembled filters M and J and the wire form of a tree against a base commit change only as intended.

Usage: python3 -I verify.py <repo> <base-commit>   (the tree checked is the working tree of <repo>; the base is the main
commit the task branch was last merged with)

Registry (target_registry.assemble): the rows of P/01 and P/02 are byte-equal to the base; the new rows are the 38 of P/03 in
Platform/03-worker/forms/; the public cells of the 26 vector targets taken over from runner-targets.tsv are byte-equal to their rows
there (P/03/vectors-creates-key differs: stand command creates-key); the 11 seam and stand targets are not vector rows.
Filters (export_lists.assemble, P02.54): the assembled M and J of the tree and of the base; every path of the base keeps its M
record; the new paths are exactly the four forms of P/03 (forms/targets.tsv, forms/targets.routing.tsv, forms/export.json,
forms/code-rules.tsv, the last one unlisted at the base); a J record changes only to include, only for a file of
P/03 acceptance/, data/, forms/, vectors/ or of a package directory named in the acceptance column of a P/03 routing row.
Wire: wire.tsv and wire.cases.tsv of the base are kept; the new triples are printed; consumers.tsv is unchanged.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

repo, base = Path(sys.argv[1]).resolve(), sys.argv[2]
sys.path.insert(0, str(repo / "skills/lesson-spec/scripts"))
import export_lists  # noqa: E402
import target_registry  # noqa: E402

L = "Platform/03-worker/"
failed = False


def check(ok, text):
    global failed
    failed |= not ok
    print(("ok   " if ok else "FAIL ") + text)


def show(path):
    return subprocess.run(["git", "-C", str(repo), "show", f"{base}:{path}"], capture_output=True).stdout


with tempfile.TemporaryDirectory() as tmp:
    old = Path(tmp) / "base"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", "-q", str(old), base], check=True)
    try:
        t_new, r_new, e_new, _ = target_registry.assemble(repo)
        t_old, r_old, e_old, _ = target_registry.assemble(old)
        check(not e_new and not e_old, f"registry assembles without errors (tree {len(t_new)}, base {len(t_old)} targets)")
        for name, new, prev in (("targets.tsv", t_new, t_old), ("targets.routing.tsv", r_new, r_old)):
            keep = [(p.relative_to(repo).as_posix(), r) for p, _, r in new if not p.as_posix().startswith(str(repo / L))]
            was = [(p.relative_to(old).as_posix(), r) for p, _, r in prev]
            check(keep == was, f"{name}: the {len(was)} rows of the base are unchanged")
            mine = [r for p, _, r in new if p.as_posix().startswith(str(repo / L))]
            check(len(mine) == 38, f"{name}: {len(mine)} rows of P/03")
        rt = {}
        for line in (repo / "Platform/common/acceptance/runner-targets.tsv").read_text(encoding="utf-8").split("\n")[1:]:
            if line:
                cells = line.split("\t")
                rt[cells[0]] = cells
        cols = ["owner", "stand_commands", "stand_addresses", "keys", "requirements", "norm_anchors"]
        mine = {r["id"]: r for p, _, r in t_new if p.as_posix().startswith(str(repo / L))}
        vec = [i for i in mine if i.startswith("P/03/vectors-")]
        same = [i for i in vec if i in rt and [mine[i][c] for c in cols] == rt[i][1:7]]
        check(len(vec) == 27 and set(vec) - set(same) == {"P/03/vectors-creates-key"},
              f"vector targets: {len(vec)}, public cells equal to runner-targets.tsv: {len(same)}; differs: "
              f"{sorted(set(vec) - set(same))}")
        print("     other P/03 targets:", sorted(set(mine) - set(vec)))
        routing = {r["id"]: r for p, _, r in r_new if p.as_posix().startswith(str(repo / L))}
        print("     engines:", {i: routing[i]["engine"] for i in sorted(routing) if not i.startswith("P/03/vectors-")})

        a_new, err_new, s_new = export_lists.assemble(repo)
        a_old, err_old, s_old = export_lists.assemble(old)
        check(not err_new, f"filters assemble without errors: {s_new}")
        print(f"     base: errors {len(err_old)}, {s_old}")
        routed = sorted({d + "/" for r in routing.values() for d in json.loads(r["acceptance"]) if not d.startswith(L)})
        for side in ("model", "judge"):
            new = {r["path"]: r for r in a_new[side]}
            prev = {r["path"]: r for r in a_old[side]}
            added = sorted(set(new) - set(prev))
            check(not set(prev) - set(new), f"{side}: no path of the base is lost ({len(prev)} → {len(new)})")
            check(added == sorted(L + f for f in ("forms/code-rules.tsv", "forms/export.json", "forms/targets.routing.tsv",
                                                    "forms/targets.tsv")),
                  f"{side}: new paths {[(p, new[p]['disposition']) for p in added]}")
            changed = [p for p in prev if (new[p]["disposition"], new[p]["basis"]) != (prev[p]["disposition"], prev[p]["basis"])]
            moved = [p for p in changed if new[p]["disposition"] == prev[p]["disposition"]]
            flipped = [p for p in changed if p not in moved]
            if side == "model":
                check(not flipped, f"model: no disposition changes ({len(changed)} records changed in basis only: {changed[:3]})")
            else:
                lesson = [p for p in flipped if p.startswith(L)]
                common = [p for p in flipped if not p.startswith(L)]
                ok = all(new[p]["disposition"] == "include" for p in flipped) and \
                    all(p[len(L):].startswith(("acceptance/", "data/", "forms/", "vectors/")) for p in lesson) and \
                    all(any(p.startswith(d) for d in routed) for p in common)
                check(ok, f"judge: {len(lesson)} files of P/03 and {len(common)} files of routed packages exclude → include")
                print("     packages:", sorted({p.rsplit('/', 1)[0] for p in common}))
                print("     basis-only changes:", len(moved))

        def triples(text):
            return [tuple(line.split("\t")[:3]) for line in text.decode().split("\n")
                    if line and not line.startswith("#") and not line.startswith("package\t")]
        for name in ("wire.tsv", "wire.cases.tsv"):
            new = triples((repo / "Platform/common/vectors" / name).read_bytes())
            prev = triples(show("Platform/common/vectors/" + name))
            rows_new = {tuple(l.split("\t")[:3]): l for l in (repo / "Platform/common/vectors" / name).read_text().split("\n")}
            rows_old = {tuple(l.split("\t")[:3]): l for l in show("Platform/common/vectors/" + name).decode().split("\n")}
            kept = all(rows_new.get(k) == v for k, v in rows_old.items())
            check(kept and set(prev) <= set(new), f"{name}: rows of the base kept; new triples {sorted(set(new) - set(prev))}")
        check((repo / "Platform/common/vectors/consumers.tsv").read_bytes() == show("Platform/common/vectors/consumers.tsv"),
              "consumers.tsv unchanged")
    finally:
        subprocess.run(["git", "-C", str(repo), "worktree", "remove", "--force", str(old)], check=True)
sys.exit(1 if failed else 0)
