"""Negative and positive controls of the operator, on synthetic J repositories.

P02.52: a fixture filter is written in the bytes of an assembled filter (sorted by path as
UTF-8 bytes, JSON indent 2, final LF), because the bound blob is the blob of those bytes
(ADR-0135 addendum (14), common acceptance README «assembled from the lessons» item 4).
The controls of the lists of the lessons are in the class Lists below."""
import json, os, pathlib, subprocess, tempfile, unittest
import judge_input_export as op

ENV = dict(op.ENV)
GOOD = {op.MARKER: "c" * 40 + "\n", "Platform/common/acceptance/README.md": "norm\n",
        "Platform/01-store/acceptance/1/scenarios.tsv": "a\tb\n", "Platform/02-installer/x.md": "other\n"}
INC = {op.MARKER, "Platform/common/acceptance/README.md", "Platform/01-store/acceptance/1/scenarios.tsv"}


def canonical(doc):
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf8")


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
    doc["files"].sort(key=lambda r: r["path"].encode("utf8"))
    f = wt / op.FILTER
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(canonical(doc))
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


LESSON = "Platform/01-store/"
LIST = LESSON + "forms/export.json"
TARGETS = LESSON + "forms/targets.tsv"
ROUTING = LESSON + "forms/targets.routing.tsv"
FILES = {**GOOD, TARGETS: "id\towner\n", ROUTING: "id\troute\n"}
INCL = INC | {TARGETS, ROUTING}


def by_path(records):
    return sorted(records, key=lambda r: r["path"].encode("utf8"))


def make_lists(tmp, files=FILES, include=INCL, mutate=None):
    """The records of the files of LESSON in LIST; the common filter keeps the others."""
    wt = pathlib.Path(tmp, "src")
    wt.mkdir()
    subprocess.run(["git", "init", "-q", str(wt)], check=True, env=ENV)
    for p, t in files.items():
        q = wt / p
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text(t, encoding="utf8")
    listed = set(files) | {op.FILTER, LIST}
    own = {p for p in listed if p.startswith(LESSON)}
    judge = lambda ps: by_path(rec(p, "include" if p in include else "exclude") for p in ps)
    common = {"version": 1, "files": judge(listed - own)}
    lst = {"version": 1, "model": by_path({"path": p, "disposition": "judge_only", "basis": "because"} for p in own),
           "judge": judge(own)}
    if mutate:
        mutate(common, lst)
    for path, doc in ((op.FILTER, common), (LIST, lst)):
        (wt / path).parent.mkdir(parents=True, exist_ok=True)
        (wt / path).write_bytes(canonical(doc))
    subprocess.run(["git", "-C", str(wt), "add", "-f", "Platform"], check=True, env=ENV)
    subprocess.run(["git", "-C", str(wt), "commit", "-q", "-m", "j"], check=True, env=ENV)
    gd = str(wt / ".git")
    c = op.git(gd, "rev-parse", "HEAD").decode().strip()
    assembled = dict(common, files=by_path(common["files"] + list(lst["judge"])))
    return gd, c, op.blob_id(canonical(assembled))


class Lists(unittest.TestCase):
    """ADR-0135 addendum (14): the second filter is the common J filter and the judge records of the lists."""

    def refused(self, needle, blob=None, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            gd, c, b = make_lists(tmp, **kw)
            with self.assertRaises(op.Refused) as e:
                op.build(gd, c, blob or b, os.path.join(tmp, "out"))
            self.assertFalse(os.path.exists(os.path.join(tmp, "out")))
        self.assertIn(needle, str(e.exception))

    def test_lists_select_as_the_equivalent_common_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            for d in ("a", "b"):
                os.mkdir(os.path.join(tmp, d))
            gd, c, b = make(os.path.join(tmp, "a"), FILES, INCL)
            old = op.build(gd, c, b, os.path.join(tmp, "a", "out"))
            gd2, c2, b2 = make_lists(os.path.join(tmp, "b"))
            out = os.path.join(tmp, "b", "out")
            new = op.build(gd2, c2, b2, out)
            self.assertEqual((old["j_input_commit"], old["j_input_tree"]), (new["j_input_commit"], new["j_input_tree"]))
            self.assertNotIn(LIST, op.read_tree(out + "/JI.git", new["j_input_commit"]))
            raw = pathlib.Path(out, "FILTER-JI.json").read_bytes()
            self.assertEqual((op.blob_id(raw), new["second_filter_blob"]), (b2, b2))
            self.assertEqual(set(new["second_filter_sources"]), {op.FILTER, LIST})
            self.assertEqual(new["second_filter_sources"][LIST], op.git(gd2, "rev-parse", f"HEAD:{LIST}").decode().strip())

    def test_common_file_blob_is_not_the_bound_blob_when_lists_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            gd, c, _ = make_lists(tmp)
            common = op.git(gd, "rev-parse", f"HEAD:{op.FILTER}").decode().strip()
        self.refused("differs from the bound", blob=common)

    def test_routing_and_targets_are_included(self):
        self.refused("lesson form against the common rule", include=INCL - {ROUTING})
        self.refused("lesson form against the common rule", include=INCL - {TARGETS})

    def test_list_is_excluded(self):
        self.refused("lesson form against the common rule", include=INCL | {LIST})

    def test_list_names_a_file_outside_its_lesson(self):
        def m(common, lst):
            moved = [r for r in common["files"] if r["path"] == "Platform/02-installer/x.md"][0]
            common["files"].remove(moved)
            lst["judge"] = by_path(lst["judge"] + [moved])
            lst["model"] = by_path(lst["model"] + [dict(moved, disposition="judge_only")])
        self.refused("names other than the files of its lesson", mutate=m)

    def test_list_misses_a_file_of_its_lesson(self):
        def m(common, lst):
            for side in ("model", "judge"):
                lst[side] = [r for r in lst[side] if r["path"] != ROUTING]
        self.refused("names other than the files of its lesson", mutate=m)

    def test_list_not_sorted(self):
        self.refused("not sorted", mutate=lambda common, lst: lst["judge"].reverse())

    def test_common_filter_not_sorted(self):
        self.refused("not sorted", mutate=lambda common, lst: common["files"].reverse())

    def test_record_in_the_common_filter_and_in_a_list(self):
        def m(common, lst):
            common["files"] = by_path(common["files"] + [r for r in lst["judge"] if r["path"] == TARGETS])
        self.refused("duplicate path", mutate=m)

    def test_list_extra_field(self):
        self.refused("exactly version 1, model and judge", mutate=lambda common, lst: lst.update(extra=[]))

    def test_list_version(self):
        self.refused("exactly version 1, model and judge", mutate=lambda common, lst: lst.update(version=2))


if __name__ == "__main__":
    unittest.main()
