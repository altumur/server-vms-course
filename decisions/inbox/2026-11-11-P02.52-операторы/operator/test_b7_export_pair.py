"""Four NEW operator controls, retained synthetic evidence; no historical suite.

P02.52: the fixture filter is written in the bytes of an assembled filter (JSON indent 2,
final LF), because the authorization binds the blob of those bytes (ADR-0135 addendum (14),
common acceptance README «assembled from the lessons» item 4). The controls of the lists of
the lessons are in the class LessonListControls below."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid

import b7_export_pair as op

HERE = Path(__file__).resolve().parent
ENV = dict(op.ENV, GIT_AUTHOR_NAME="Synthetic fixture", GIT_AUTHOR_EMAIL="fixture@invalid",
           GIT_COMMITTER_NAME="Synthetic fixture", GIT_COMMITTER_EMAIL="fixture@invalid",
           GIT_AUTHOR_DATE="2026-11-08T00:00:00Z", GIT_COMMITTER_DATE="2026-11-08T00:00:00Z")


def canonical(doc):
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()


def by_path(records):
    return sorted(records, key=lambda r: r["path"].encode())


def git(repo, *args, data=None):
    return subprocess.check_output(["git", "--git-dir=" + str(repo), *args], input=data, env=ENV, stderr=subprocess.PIPE)


def tree(repo, entries):
    nodes = {}
    for p, (mode, raw) in sorted(entries.items()):
        cursor = nodes
        for part in p.split("/")[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[p.split("/")[-1]] = (mode, git(repo, "hash-object", "-w", "--stdin", data=raw).strip().decode())
    def emit(node):
        rows = []
        for name, value in sorted(node.items()):
            if isinstance(value, dict):
                mode, kind, oid = "040000", "tree", emit(value)
            else:
                mode, oid = value; kind = "blob"
            rows.append(f"{mode} {kind} {oid}\t{name}".encode() + b"\0")
        return git(repo, "mktree", "-z", data=b"".join(rows)).strip().decode()
    return emit(nodes)


def files(repo, commit):
    out = {}
    for row in git(repo, "ls-tree", "-rz", commit).split(b"\0"):
        if row:
            h, p = row.split(b"\t", 1);out[p.decode()] = h.decode().split()
    return out


class OperatorControls(unittest.TestCase):
    def setUp(self):
        self.root = HERE / "operator-fixtures" / (self._testMethodName + "-" + uuid.uuid4().hex[:8])
        self.root.mkdir(parents=True, mode=0o700)
        self.products = self.root / "products"; self.products.mkdir(mode=0o700)
        self.source = self.root / "source.git"
        subprocess.check_output(["git", "init", "--bare", "--template=", str(self.source)], env=ENV, stderr=subprocess.PIPE)
        self.case = "Platform/01-store/vectors/synthetic/cases.tsv"
        self.norm = "Platform/01-store/ru/spec/public.norms.md"
        self.fixture = {
            self.norm: ("100644", "Синтетическая публичная норма.\n".encode()),
            "Platform/01-store/spec/public.norms.md": ("100644", b"Synthetic public norm.\n"),
            "Platform/01-store/probes/public_probe.py": ("100755", b"# synthetic public protocol only\n"),
            "Platform/common/vectors/wire.md": ("100644", b"Synthetic public input protocol only.\n"),
            "Platform/common/contracts/generic.norms.md": ("100644", b"Synthetic generic public rule.\n"),
            "Platform/common/contracts/s18-accept-no-kit.md": ("100644", b"Synthetic public no-kit acceptance rule.\n"),
            op.DERIVED: ("100644", b'{"synthetic_public_protocol":true}\n'),
            op.WIRE: ("100644", ("\t".join(op.WIRE_HEADER) + "\n01-store/synthetic\tcases.tsv\tpure\tx\tx\t-\tout\tjson\t-\tjson\tnorm\n").encode()),
            self.case: ("100644", b"PRIVATE_SYNTHETIC_CASE_ANSWER\n"),
            "Platform/01-store/ru/acceptance/1/synthetic.cases.md": ("100644", b"PRIVATE_SYNTHETIC_RU_CASE\n"),
            "OutsidePlatform/not-exported": ("100644", b"not part of Platform\n"),
        }
        self.public = {self.norm, "Platform/01-store/spec/public.norms.md", "Platform/01-store/probes/public_probe.py", "Platform/common/vectors/wire.md", "Platform/common/contracts/generic.norms.md", "Platform/common/contracts/s18-accept-no-kit.md", op.DERIVED, op.MARKER}
        self.commit = self.build()

    def build(self, *, keep_wire=False):
        roster = {p for p in self.fixture if p.startswith("Platform/")} | {op.FILTER, op.MARKER}
        roles = {p: "model_and_judge" if p in self.public or (keep_wire and p in {op.WIRE, self.case}) else "judge_only" for p in roster}
        f = {"version": 1, "files": [{"path": p, "disposition": roles[p], "basis": "synthetic role"} for p in sorted(roster)], "own_export_markers": []}
        self.fixture[op.FILTER] = ("100644", canonical(f))
        self.roles = roles
        root_tree = tree(self.source, self.fixture)
        c = git(self.source, "commit-tree", root_tree, data=b"Synthetic input fixture only\n").strip().decode()
        self.authorization = {"version": 1, "authorization": "ROOT_AFTER_STEP6_GREEN_AND_FILTER_REVIEW", "source_C": c,
            "filter_blob": files(self.source, c)[op.FILTER][2], "wire_blob": files(self.source, c)[op.WIRE][2],
            "derived_sha256": hashlib.sha256(self.fixture[op.DERIVED][1]).hexdigest(),
            "source_acceptance_sha256": "1" * 64, "green_check_sha256": "2" * 64,
            "different_provider_filter_review_sha256": "3" * 64,
            "filter_author_provider": "synthetic-author", "filter_reviewer_provider": "synthetic-other-provider"}
        return c

    def auth(self):
        return (json.dumps(self.authorization) + "\n").encode()

    def test_cli_full_J_exact_filter_M_independent_objects_and_canonical_metadata(self):
        auth = self.root / "synthetic-authorization.json"; auth.write_bytes(self.auth())
        output = self.products / "new-pair"
        p = subprocess.run([sys.executable, "-B", str(HERE / "b7_export_pair.py"),
            "--source-git-dir", str(self.source), "--course-commit", self.commit,
            "--output", str(output), "--authorization-json", str(auth)], env=ENV, capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        r = json.loads(p.stdout);m,j=r["M"],r["J"]
        mt,jt,ct=files(output/'M.git',m),files(output/'J.git',j),files(self.source,self.commit)
        self.assertEqual({p:v for p,v in jt.items() if p!=op.MARKER},{p:v for p,v in ct.items() if p.startswith('Platform/')})
        self.assertEqual(mt,{p:jt[p] for p,role in self.roles.items() if role=='model_and_judge'})
        self.assertIn("Platform/common/contracts/generic.norms.md",mt);self.assertIn("Platform/common/contracts/s18-accept-no-kit.md",mt)
        self.assertIn(self.norm,mt);self.assertNotIn(self.case,mt);self.assertEqual(mt['Platform/01-store/probes/public_probe.py'][0],'100755')
        for name,commit in [('M.git',m),('J.git',j)]:
            repo=output/name
            self.assertEqual(git(repo,'show',commit+':'+op.MARKER),(self.commit+'\n').encode())
            self.assertEqual((repo/'config').read_bytes(),op.CONFIG)
            self.assertFalse((repo/'index').exists());self.assertFalse(list(repo.glob('sharedindex.*')))
            self.assertFalse((repo/'objects/info/alternates').exists());self.assertFalse(list((repo/'objects/pack').iterdir()))
            self.assertEqual(git(repo,'rev-list','--count',commit).strip(),b'1')
        objects=git(output/'M.git','cat-file','--batch-all-objects','--batch-check=%(objectname)').splitlines()
        self.assertNotIn(ct[self.case][2].encode(),objects);self.assertNotIn(self.commit.encode(),objects);self.assertNotIn(j.encode(),objects)
        case_blob = ct[self.case][2]
        self.assertEqual(subprocess.run(['git','--git-dir='+str(output/'M.git'),'cat-file','-e',case_blob],env=ENV,capture_output=True).returncode,1)
        passport=json.loads((output/'PASSPORT-TRUSTED-ONLY.json').read_text())
        self.assertFalse(passport['receipt_authenticity_verified']);self.assertFalse(passport['namespace_or_runtime_qualified'])

    def test_invalid_authorization_and_case_filter_refuse_before_any_output_mutation(self):
        self.authorization['filter_blob']='0'*40
        with self.assertRaises(op.Refused):op.compose_pair(self.source,self.commit,self.products/'wrong-auth',authorization_json=self.auth())
        self.assertEqual(list(self.products.iterdir()),[])
        self.commit=self.build()
        with self.assertRaises(op.Refused):op.compose_pair(self.source,self.commit,self.products/'utf16-auth',authorization_json=self.auth().decode().encode('utf-16'))
        self.assertEqual(list(self.products.iterdir()),[])
        self.commit=self.build(keep_wire=True)
        with self.assertRaises(op.Refused):op.compose_pair(self.source,self.commit,self.products/'bad-filter',authorization_json=self.auth())
        self.assertEqual(list(self.products.iterdir()),[])
        self.fixture[self.norm]=('100644', b'Synthetic private path /private/tmp/not-a-model-input\n')
        self.commit=self.build()
        with self.assertRaises(op.Refused):op.compose_pair(self.source,self.commit,self.products/'leaking-content',authorization_json=self.auth())
        self.assertEqual(list(self.products.iterdir()),[])

    def test_existing_output_alias_and_unsafe_parent_are_preserved_not_overwritten(self):
        existing=self.products/'existing';existing.mkdir();(existing/'held').write_bytes(b'preserve')
        with self.assertRaises(op.Refused):op.compose_pair(self.source,self.commit,existing,authorization_json=self.auth())
        self.assertEqual((existing/'held').read_bytes(),b'preserve')
        alias=self.root/'alias';alias.symlink_to(self.products,target_is_directory=True)
        with self.assertRaises(op.Refused):op.compose_pair(self.source,self.commit,alias/'would-be-output',authorization_json=self.auth())
        self.assertEqual(set(p.name for p in self.products.iterdir()),{'existing'})
        with self.assertRaises(op.Refused):op.compose_pair('//'+str(self.source).lstrip('/'),self.commit,self.products/'double-root',authorization_json=self.auth())
        self.products.chmod(0o777)
        with self.assertRaises(op.Refused):op.compose_pair(self.source,self.commit,self.products/'unsafe',authorization_json=self.auth())
        self.products.chmod(0o700)

    def test_failed_staging_and_concurrent_destination_are_retained_without_publication_overwrite(self):
        # A failed mkdir has created no staging: do not report a nonexistent retained path.
        with patch.object(op.os,'mkdir',side_effect=PermissionError('synthetic precreation failure')):
            with self.assertRaises(PermissionError):op.compose_pair(self.source,self.commit,self.products/'not-created',authorization_json=self.auth())
        self.assertEqual(list(self.products.iterdir()),[])
        original=op._emit
        def fail_on_model(stage,*args):
            if args[0]=='M.git':raise OSError('synthetic injected own I/O failure')
            return original(stage,*args)
        with patch.object(op,'_emit',side_effect=fail_on_model):
            with self.assertRaises(op.RetainedFailure) as caught:op.compose_pair(self.source,self.commit,self.products/'not-final',authorization_json=self.auth())
        retained=Path(caught.exception.path)
        self.assertTrue((retained/'J.git').is_dir());self.assertTrue((retained/'FAILED-RETAINED.json').is_file());self.assertFalse((self.products/'not-final').exists())
        real_publish=op._publish
        def collision(parent_fd,stage,final):
            os.mkdir(final,0o700,dir_fd=parent_fd)
            return real_publish(parent_fd,stage,final)
        with patch.object(op,'_publish',side_effect=collision):
            with self.assertRaises(op.RetainedFailure) as collided:op.compose_pair(self.source,self.commit,self.products/'collision',authorization_json=self.auth())
        self.assertTrue((self.products/'collision').is_dir());self.assertEqual(list((self.products/'collision').iterdir()),[])
        self.assertTrue((Path(collided.exception.path)/'FAILED-RETAINED.json').is_file())


LESSON = "Platform/01-store/"
LIST = LESSON + "forms/export.json"
TARGETS = LESSON + "forms/targets.tsv"
ROUTING = LESSON + "forms/targets.routing.tsv"


class LessonListControls(OperatorControls):
    """ADR-0135 addendum (14): the model filter is the common filter and the model records of the lists."""

    def setUp(self):
        super().setUp()
        self.fixture[TARGETS] = ("100644", b"id\towner\n")
        self.fixture[ROUTING] = ("100644", b"id\troute\n")
        self.public = self.public | {TARGETS}

    def build_lists(self, mutate=None, roles=None):
        roster = {p for p in self.fixture if p.startswith("Platform/")} | {op.FILTER, op.MARKER, LIST}
        role = {p: "model_and_judge" if p in self.public else "judge_only" for p in roster}
        role.update(roles or {})
        recs = lambda ps: by_path({"path": p, "disposition": role[p], "basis": "synthetic role"} for p in ps)
        own = {p for p in roster if p.startswith(LESSON)}
        common = {"version": 1, "files": recs(roster - own), "own_export_markers": []}
        lst = {"version": 1, "model": recs(own),
               "judge": by_path({"path": p, "disposition": "include", "basis": "synthetic role"} for p in own)}
        if mutate:
            mutate(common, lst)
        self.fixture[op.FILTER] = ("100644", canonical(common))
        self.fixture[LIST] = ("100644", canonical(lst))
        self.roles = role
        c = git(self.source, "commit-tree", tree(self.source, self.fixture), data=b"Synthetic input fixture only\n").strip().decode()
        assembled = dict(common, files=by_path(common["files"] + list(lst["model"])))
        self.assembled = canonical(assembled)
        self.authorization.update(source_C=c, filter_blob=op._blob_id(self.assembled),
                                  wire_blob=files(self.source, c)[op.WIRE][2])
        return c

    def refused(self, needle=None, **kw):
        self.commit = self.build_lists(**kw)
        with self.assertRaises(op.Refused) as e:
            op.compose_pair(self.source, self.commit, self.products / "refused", authorization_json=self.auth())
        self.assertEqual(list(self.products.iterdir()), [])
        if needle:
            self.assertIn(needle, str(e.exception))

    def test_lists_give_the_M_of_the_equivalent_common_filter(self):
        self.commit = self.build()          # the same files, every record in the common filter, no list
        old = op.compose_pair(self.source, self.commit, self.products / "old", authorization_json=self.auth())
        self.commit = self.build_lists()
        out = self.products / "new"
        new = op.compose_pair(self.source, self.commit, out, authorization_json=self.auth())
        # The M of each is its files and the marker of its own C: the files are the same.
        mo = files(self.products / "old" / "M.git", old["passport"]["M"]["commit"])
        mt = files(out / "M.git", new["passport"]["M"]["commit"])
        self.assertEqual({p: v for p, v in mo.items() if p != op.MARKER}, {p: v for p, v in mt.items() if p != op.MARKER})
        self.assertIn(LIST, files(out / "J.git", new["passport"]["J"]["commit"]))
        self.assertIn(TARGETS, mt); self.assertNotIn(ROUTING, mt); self.assertNotIn(LIST, mt)
        passport = new["passport"]
        self.assertEqual((out / "FILTER-M.json").read_bytes(), self.assembled)
        self.assertEqual(passport["filter_blob"], op._blob_id(self.assembled))
        self.assertEqual(passport["filter_sources"], {op.FILTER: files(self.source, self.commit)[op.FILTER][2],
                                                      LIST: files(self.source, self.commit)[LIST][2]})

    def test_old_layout_binds_the_canonical_bytes(self):
        self.commit = self.build()
        raw = self.fixture[op.FILTER][1]
        self.fixture[op.FILTER] = ("100644", raw.replace(b"\n  ", b"\n    "))   # same JSON, other bytes
        c = git(self.source, "commit-tree", tree(self.source, self.fixture), data=b"x\n").strip().decode()
        self.authorization.update(source_C=c, filter_blob=files(self.source, c)[op.FILTER][2])
        with self.assertRaises(op.Refused):
            op.compose_pair(self.source, c, self.products / "raw-blob", authorization_json=self.auth())
        self.authorization["filter_blob"] = op._blob_id(raw)
        r = op.compose_pair(self.source, c, self.products / "canonical", authorization_json=self.auth())
        self.assertEqual((self.products / "canonical" / "FILTER-M.json").read_bytes(), raw)
        self.assertEqual(r["passport"]["filter_sources"], {op.FILTER: files(self.source, c)[op.FILTER][2]})

    def test_common_file_blob_is_not_the_bound_blob_when_lists_exist(self):
        self.commit = self.build_lists()
        self.authorization["filter_blob"] = files(self.source, self.commit)[op.FILTER][2]
        with self.assertRaises(op.Refused) as e:
            op.compose_pair(self.source, self.commit, self.products / "common-blob", authorization_json=self.auth())
        self.assertIn("authorization C/filter/wire mismatch", str(e.exception))
        self.assertEqual(list(self.products.iterdir()), [])

    def test_routing_of_the_judge_never_in_M(self):
        self.refused("lesson form", roles={ROUTING: "model_and_judge"})

    def test_list_never_in_M(self):
        self.refused("lesson form", roles={LIST: "model_and_judge"})

    def test_targets_in_M(self):
        self.refused("lesson form", roles={TARGETS: "judge_only"})

    def test_list_names_a_file_outside_its_lesson(self):
        def m(common, lst):
            moved = [r for r in common["files"] if r["path"] == "Platform/common/vectors/wire.md"][0]
            common["files"].remove(moved)
            lst["model"] = by_path(lst["model"] + [moved])
            lst["judge"] = by_path(lst["judge"] + [dict(moved, disposition="include")])
        self.refused("exactly the files of its lesson", mutate=m)

    def test_list_misses_a_file_of_its_lesson(self):
        def m(common, lst):
            for side in ("model", "judge"):
                lst[side] = [r for r in lst[side] if r["path"] != ROUTING]
        self.refused("exactly the files of its lesson", mutate=m)

    def test_list_not_sorted(self):
        self.refused("not sorted", mutate=lambda common, lst: lst["model"].reverse())

    def test_record_in_the_common_filter_and_in_a_list(self):
        def m(common, lst):
            common["files"] = by_path(common["files"] + [r for r in lst["model"] if r["path"] == TARGETS])
        self.refused("duplicate filter path", mutate=m)

    def test_list_extra_field(self):
        self.refused("exactly version 1, model and judge", mutate=lambda common, lst: lst.update(extra=[]))


if __name__=='__main__':unittest.main(verbosity=2)
