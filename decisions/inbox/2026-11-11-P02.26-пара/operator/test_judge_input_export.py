"""Negative and positive controls of the operator, on synthetic J repositories."""
import json, os, pathlib, subprocess, tempfile, unittest
import judge_input_export as op

ENV = dict(op.ENV)
GOOD = {op.MARKER: "c" * 40 + "\n", "Platform/common/acceptance/README.md": "norm\n",
        "Platform/01-store/acceptance/1/scenarios.tsv": "a\tb\n", "Platform/02-installer/x.md": "other\n"}
INC = {op.MARKER, "Platform/common/acceptance/README.md", "Platform/01-store/acceptance/1/scenarios.tsv"}


def rec(p, d):
    return {"path": p, "disposition": d, "basis": "because"}


def make(tmp, files, include, mutate=None, link=None):
    wt = pathlib.Path(tmp, "src")
    wt.mkdir()
    subprocess.run(["git", "init", "-q", str(wt)], check=True, env=ENV)
    for p, t in files.items():
        q = wt / p
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text(t, encoding="utf8")
    if link:
        (wt / link).parent.mkdir(parents=True, exist_ok=True)
        os.symlink("README.md", wt / link)
    listed = sorted(set(files) | {op.FILTER} | ({link} if link else set()))
    doc = {"version": 1, "files": [rec(p, "include" if p in include else "exclude") for p in listed]}
    if mutate:
        mutate(doc)
    f = wt / op.FILTER
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(doc), encoding="utf8")
    subprocess.run(["git", "-C", str(wt), "add", "-f", "Platform"], check=True, env=ENV)
    subprocess.run(["git", "-C", str(wt), "commit", "-q", "-m", "j"], check=True, env=ENV)
    gd = str(wt / ".git")
    c = op.git(gd, "rev-parse", "HEAD").decode().strip()
    return gd, c, op.git(gd, "rev-parse", f"HEAD:{op.FILTER}").decode().strip()


class Controls(unittest.TestCase):
    def run_op(self, files=GOOD, include=INC, mutate=None, link=None, blob=None):
        with tempfile.TemporaryDirectory() as tmp:
            gd, c, b = make(tmp, files, include, mutate, link)
            return op.build(gd, c, blob or b, os.path.join(tmp, "out"))

    def refused(self, needle, **kw):
        with self.assertRaises(op.Refused) as e:
            self.run_op(**kw)
        self.assertIn(needle, str(e.exception))

    def test_ok_keeps_blobs_and_selects_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            gd, c, b = make(tmp, GOOD, INC)
            out = os.path.join(tmp, "out")
            p = op.build(gd, c, b, out)
            bare = out + "/JI.git"
            self.assertEqual(set(op.read_tree(bare, p["j_input_commit"])), INC)
            for path in INC:
                self.assertEqual(op.git(bare, "rev-parse", f"{op.REF}:{path}"), op.git(gd, "rev-parse", f"HEAD:{path}"))
            self.assertEqual((p["source_C"], p["second_filter_blob"], p["files_in_j_input"]), ("c" * 40, b, 3))
            subprocess.run(["git", "--git-dir", bare, "fsck", "--full", "--strict"], check=True, capture_output=True, env=ENV)
            self.assertFalse(os.path.exists(bare + "/hooks"), "the output carries no hook samples")

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            gd, c, b = make(tmp, GOOD, INC)
            a = op.build(gd, c, b, tmp + "/o1")
            z = op.build(gd, c, b, tmp + "/o2")
            self.assertEqual((a["j_input_commit"], a["j_input_tree"]), (z["j_input_commit"], z["j_input_tree"]))

    def test_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            gd, c, b = make(tmp, GOOD, INC)
            os.mkdir(tmp + "/out")
            with self.assertRaises(op.Refused):
                op.build(gd, c, b, tmp + "/out")

    def test_wrong_blob(self):
        self.refused("differs from the bound", blob="0" * 40)

    def test_short_ids(self):
        self.refused("full object id", blob="abc")

    def test_path_not_classified(self):
        self.refused("filter and J differ", mutate=lambda d: d["files"].pop())

    def test_phantom_path(self):
        self.refused("filter and J differ", mutate=lambda d: d["files"].append(rec("Platform/zz.md", "exclude")))

    def test_duplicate_path(self):
        self.refused("duplicate path", mutate=lambda d: d["files"].append(dict(d["files"][0])))

    def test_noncanonical(self):
        self.refused("non-canonical", mutate=lambda d: d["files"].append(rec("Platform/a/../b", "exclude")))

    def test_unknown_disposition(self):
        self.refused("disposition", mutate=lambda d: d["files"][0].update(disposition="maybe"))

    def test_extra_record_key(self):
        self.refused("filter record", mutate=lambda d: d["files"][0].update(extra=1))

    def test_non_english_basis(self):
        self.refused("filter record fields", mutate=lambda d: d["files"][0].update(basis="основание"))

    def test_empty(self):
        self.refused("non-empty", mutate=lambda d: d.update(files=[]))

    def test_forbidden_classes_cannot_be_opted_in(self):
        for path, needle in (("Platform/01-store/probes/store_probes.py", "code"),
                             ("Platform/common/ru/acceptance/README.md", "translation"),
                             ("Platform/02-installer/acceptance/1/spec_verdicts/a.txt", "verdict"),
                             ("Platform/x/mutants/a.txt", "verdict"),
                             ("Platform/x/acceptance/1/legacy_spec_verdicts/a.txt", "verdict"),
                             ("Platform/x/acceptance/1/spec_verdicts.tsv", "verdict"),
                             ("Platform/x/acceptance/1/Spec_Verdicts/a.txt", "verdict"),
                             ("Platform/common/acceptance/runner-targets.provenance.cases.md", "named"),
                             ("Platform/01-store/probes/README.cases.md", "named")):
            with self.subTest(path):
                self.refused(needle, files={**GOOD, path: "x\n"}, include=INC | {path})

    def test_judge_table_named_verdicts_is_not_the_corpus(self):
        # P02.26: P/02 acceptance/1/verdicts.tsv (engine word verdicts) is judge input;
        # its sibling spec_verdicts/ (the verdict corpus) stays refused.
        p = "Platform/02-installer/acceptance/1/verdicts.tsv"
        with tempfile.TemporaryDirectory() as tmp:
            gd, c, b = make(tmp, {**GOOD, p: "case\tverdict\n"}, INC | {p})
            op.build(gd, c, b, os.path.join(tmp, "out"))
            out = op.git(os.path.join(tmp, "out", "JI.git"), "ls-tree", "-r", "--name-only", "HEAD").decode().split()
            self.assertIn(p, out)
        q = "Platform/02-installer/acceptance/1/spec_verdicts/a.txt"
        self.refused("verdict", files={**GOOD, p: "x\n", q: "x\n"}, include=INC | {p, q})

    def test_code_class_not_applied_to_acceptance_inputs(self):
        # P02.26: fixtures inside acceptance/<n>/inputs/ pass the code class;
        # code elsewhere is refused, and the judge-name text check still applies there.
        p = "Platform/06-console/acceptance/5/inputs/testsub2/app.js"
        with tempfile.TemporaryDirectory() as tmp:
            gd, c, b = make(tmp, {**GOOD, p: "// fixture\n"}, INC | {p})
            op.build(gd, c, b, os.path.join(tmp, "out"))
            out = op.git(os.path.join(tmp, "out", "JI.git"), "ls-tree", "-r", "--name-only", "HEAD").decode().split()
            self.assertIn(p, out)
        for q in ("Platform/01-store/acceptance/1/probe.js", "Platform/01-store/probes/x.py",
                  "Platform/01-store/acceptance/inputs/x.py", "Platform/01-store/acceptance/1/x/inputs/y.js"):
            with self.subTest(q):
                self.refused("code", files={**GOOD, q: "x\n"}, include=INC | {q})
        self.refused("names the existing judge", files={**GOOD, p: "harness.py\n"}, include=INC | {p})

    def test_filter_cannot_include_itself(self):
        def m(d):
            [r for r in d["files"] if r["path"] == op.FILTER][0]["disposition"] = "include"
        self.refused("include itself", mutate=m)

    def test_forbidden_text(self):
        for token in ("c_targets", "bcb22c07", "P01.28", "harness.py"):
            with self.subTest(token):
                p = "Platform/common/acceptance/README.md"
                self.refused("names the existing judge", files={**GOOD, p: token + "\n"})

    def test_symlink(self):
        self.refused("unsupported entry", link="Platform/common/acceptance/l.md")

    def test_marker_required(self):
        self.refused("source marker", include=INC - {op.MARKER})

    def test_two_commits_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            gd, c, b = make(tmp, GOOD, INC)
            wt = pathlib.Path(tmp, "src")
            (wt / "extra").write_text("x")
            subprocess.run(["git", "-C", str(wt), "add", "extra"], check=True, env=ENV)
            subprocess.run(["git", "-C", str(wt), "commit", "-q", "-m", "2"], check=True, env=ENV)
            c2 = op.git(gd, "rev-parse", "HEAD").decode().strip()
            with self.assertRaises(op.Refused):
                op.build(gd, c2, b, tmp + "/o")


if __name__ == "__main__":
    unittest.main()
