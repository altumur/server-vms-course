#!/usr/bin/python3 -I
"""Build the J-input: the immutable tree of the second filter over J (ADR-0135 (2) item 1).

Reads one exact J commit and the filter blob inside it. Every path of J must be
classified exactly once. Included files keep path, mode and blob; nothing is sliced.
The forbidden classes below cannot be opted in by a filter record. Refuses rather
than repairs, and never writes to an existing output.

P02.52 (ADR-0135 addendum (14) item 3): the second filter is assembled from the common
J filter and the `judge` records of the lists `Platform/NN-<process>/forms/export.json`
of the lessons, by the rule of the common acceptance README («Target registry and export
lists assembled from the lessons», items 2-4). The bound blob is the blob of the
assembled bytes; without lesson lists they are the canonical common filter.
"""
import argparse, hashlib, json, os, re, subprocess, sys, tempfile

FILTER = "Platform/common/acceptance/judge-input-filter.json"
MARKER = "Platform/COURSE_COMMIT"
REF = "refs/heads/judge-input"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
MODES = {"100644", "100755"}
CODE = (".py", ".go", ".sh", ".c", ".cc", ".cpp", ".h", ".js", ".ts", ".rs")
FORBIDDEN_PATHS = {
    "Platform/common/acceptance/runner-targets.provenance.cases.md",
    "Platform/01-store/probes/README.cases.md",
    FILTER,
}
CORPUS = {"spec_verdicts", "legacy_spec_verdicts"}
# ADR-0135 addendum (14) item 2: the list of the files of a lesson; item 3: the forms of every lesson.
LESSON_LIST = re.compile(r"Platform/(\d\d-[a-z0-9-]+)/forms/export\.json\Z")
LESSON_FORM = re.compile(r"Platform/\d\d-[a-z0-9-]+/(forms/(?:targets\.tsv|targets\.routing\.tsv|export\.json))\Z")
LESSON_RULES = {"forms/targets.tsv": "include", "forms/targets.routing.tsv": "include",
                "forms/export.json": "exclude"}
# Names of the existing judge's code and of its inventory; none occurs in a norm.
FORBIDDEN_TEXT = re.compile(rb"c_targets|c_store|harness\.py|bcb22c07|P01\.28")
ENV = {"GIT_AUTHOR_NAME": "judge-input", "GIT_AUTHOR_EMAIL": "judge-input@invalid",
       "GIT_COMMITTER_NAME": "judge-input", "GIT_COMMITTER_EMAIL": "judge-input@invalid",
       "GIT_AUTHOR_DATE": "1970-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "1970-01-01T00:00:00Z",
       "PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"}


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class Refused(Exception):
    pass


def git(gd, *a, data=None):
    r = subprocess.run(["git", "--git-dir", gd, *a], input=data, capture_output=True, env=ENV)
    if r.returncode:
        raise Refused(f"git {a[0]}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def in_acceptance_inputs(parts):
    """P02.26 (Architect 2026-11-11T09:28:46Z): a file inside acceptance/<n>/inputs/ is a
    fixture copied as bytes (ADR-0133 addendum (4) item 8), not judge code; the
    FORBIDDEN_TEXT check still applies to it."""
    return any(parts[i] == "acceptance" and parts[i + 1].isdigit() and parts[i + 2] == "inputs"
               for i in range(len(parts) - 3))


def forbidden_class(path):
    parts = path.split("/")
    if path in FORBIDDEN_PATHS or LESSON_LIST.fullmatch(path):
        return "named exclusion"
    if "ru" in parts:
        return "translation"
    if path.endswith(CODE) and not in_acceptance_inputs(parts):
        return "code"
    # P02.26 (Architect 2026-11-11T09:23:54Z): the verdict corpus is a segment named
    # spec_verdicts or legacy_spec_verdicts (file stem included); a judge table whose
    # name merely contains "verdict" (P/02 acceptance/1/verdicts.tsv) is not the corpus.
    if any("mutant" in p.lower() or p.lower().split(".", 1)[0] in CORPUS for p in parts):
        return "verdict corpus or mutants"
    return None


def read_tree(gd, commit):
    out = {}
    for rec in git(gd, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0"):
        if not rec:
            continue
        meta, raw = rec.split(b"\t", 1)
        mode, typ, oid = meta.decode().split()
        path = raw.decode("utf8")
        if typ != "blob" or mode not in MODES:
            raise Refused(f"unsupported entry {mode} {typ} {path}")
        out[path] = (mode, oid)
    return out


def blob_id(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def load_json(raw, what):
    def unique(pairs):
        d = dict(pairs)
        if len(d) != len(pairs):
            raise Refused(f"duplicate JSON key in {what}")
        return d
    try:
        return json.loads(raw.decode("utf8"), object_pairs_hook=unique)
    except ValueError as e:
        raise Refused(f"{what} is not JSON: {e}")


def sorted_records(records, what):
    """An array of records sorted by path as UTF-8 bytes, one record per path (shape is checked later)."""
    if not isinstance(records, list):
        raise Refused(f"{what}: records are not an array")
    keys = []
    for rec in records:
        if not isinstance(rec, dict) or not isinstance(rec.get("path"), str):
            raise Refused(f"{what}: filter record {rec!r}")
        keys.append(rec["path"].encode("utf8"))
    for k in sorted({k for k in keys if keys.count(k) > 1}):
        raise Refused(f"{what}: duplicate path {k.decode()}")
    if keys != sorted(keys):
        raise Refused(f"{what}: records not sorted by path as UTF-8 bytes")
    return records


def assemble(gd, entries):
    """ADR-0135 addendum (14): common J filter + `judge` records of every lesson list → (bytes, sources).

    A list is exactly {version: 1, model, judge}; each array is sorted, names every file of its
    lesson directory once and no other file. A path has one record in one place. The assembled
    filter keeps the fields and their order of the common file; its `files` are all records sorted
    by path as UTF-8 bytes; its bytes are JSON, indent 2, non-ASCII as is, LF, final LF.
    """
    if FILTER not in entries:
        raise Refused("J has no common judge-input filter")
    doc = load_json(git(gd, "cat-file", "blob", entries[FILTER][1]), "the filter")
    if not isinstance(doc, dict) or "files" not in doc:
        raise Refused("filter top level")
    records = list(sorted_records(doc["files"], FILTER))
    sources = {FILTER: entries[FILTER][1]}
    for path in sorted(entries, key=lambda q: q.encode("utf8")):
        m = LESSON_LIST.fullmatch(path)
        if not m:
            continue
        lst = load_json(git(gd, "cat-file", "blob", entries[path][1]), path)
        if (not isinstance(lst, dict) or set(lst) != {"version", "model", "judge"}
                or type(lst["version"]) is not int or lst["version"] != 1):
            raise Refused(f"{path}: a lesson list is exactly version 1, model and judge")
        prefix = f"Platform/{m.group(1)}/"
        own = {q for q in entries if q.startswith(prefix)}
        for side in ("model", "judge"):
            named = {r["path"] for r in sorted_records(lst[side], f"{path} {side}")}
            if named != own:
                raise Refused(f"{path} {side}: names other than the files of its lesson: {sorted(named ^ own)[:5]}")
        records.extend(lst["judge"])
        sources[path] = entries[path][1]
    keys = [r["path"] for r in records]
    for k in sorted({k for k in keys if keys.count(k) > 1}):
        raise Refused(f"duplicate path {k}: a record in the common filter and in a lesson list")
    out = dict(doc)
    out["files"] = sorted(records, key=lambda r: r["path"].encode("utf8"))
    return (json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf8"), sources


def parse_filter(raw):
    def unique(pairs):
        d = dict(pairs)
        if len(d) != len(pairs):
            raise Refused("duplicate JSON key in the filter")
        return d
    try:
        doc = json.loads(raw.decode("utf8"), object_pairs_hook=unique)
    except ValueError as e:
        raise Refused(f"filter is not JSON: {e}")
    if not isinstance(doc, dict) or set(doc) != {"version", "files"} or doc["version"] != 1:
        raise Refused("filter top level")
    if not isinstance(doc["files"], list) or not doc["files"]:
        raise Refused("filter must be non-empty")
    seen, included = set(), set()
    for rec in doc["files"]:
        if not isinstance(rec, dict) or set(rec) != {"path", "disposition", "basis"}:
            raise Refused(f"filter record {rec!r}")
        p, d, b = rec["path"], rec["disposition"], rec["basis"]
        if not isinstance(p, str) or not isinstance(b, str) or not b.strip() or not b.isascii():
            raise Refused(f"filter record fields {p!r}")
        if d not in ("include", "exclude"):
            raise Refused(f"disposition {d!r}")
        if p in seen:
            raise Refused(f"duplicate path {p}")
        if p.startswith("/") or p != os.path.normpath(p) or ".." in p.split("/"):
            raise Refused(f"non-canonical path {p}")
        seen.add(p)
        if d == "include":
            included.add(p)
    return seen, included


def mktree(gd, files):
    """files: {relative path: (mode, oid)}; returns the root tree id."""
    subdirs, lines = {}, []
    for path, entry in files.items():
        head, sep, tail = path.partition("/")
        if sep:
            subdirs.setdefault(head, {})[tail] = entry
        else:
            lines.append(f"{entry[0]} blob {entry[1]}\t{head}\0".encode("utf8"))
    for name, sub in subdirs.items():
        lines.append(f"040000 tree {mktree(gd, sub)}\t{name}\0".encode("utf8"))
    return git(gd, "mktree", "-z", data=b"".join(lines)).decode().strip()


def build(j_git, j_commit, filter_blob, output):
    for v, n in ((j_commit, "J commit"), (filter_blob, "filter blob")):
        if not HEX40.match(v):
            raise Refused(f"{n} must be a full object id")
    if git(j_git, "rev-parse", "--verify", j_commit + "^{commit}").decode().strip() != j_commit:
        raise Refused("J commit is not exact")
    if git(j_git, "rev-list", "--count", j_commit).strip() != b"1":
        raise Refused("J must be a single parentless commit")
    if os.path.lexists(output):
        raise Refused("output exists")
    entries = read_tree(j_git, j_commit)
    raw, sources = assemble(j_git, entries)
    if blob_id(raw) != filter_blob:
        raise Refused("assembled filter blob of J differs from the bound one")
    if MARKER not in entries:
        raise Refused("J has no source marker")
    seen, included = parse_filter(raw)
    if seen != set(entries):
        raise Refused(f"filter and J differ: {sorted(seen ^ set(entries))[:5]}")
    if FILTER in included:
        raise Refused("the filter cannot include itself")
    for p in sorted(seen):
        form = LESSON_FORM.fullmatch(p)
        if form and (p in included) != (LESSON_RULES[form.group(1)] == "include"):
            raise Refused(f"lesson form against the common rule (gives {LESSON_RULES[form.group(1)]}): {p}")
    for p in sorted(included):
        why = forbidden_class(p)
        if why:
            raise Refused(f"forbidden class ({why}): {p}")
        if FORBIDDEN_TEXT.search(git(j_git, "cat-file", "blob", entries[p][1])):
            raise Refused(f"names the existing judge or its inventory: {p}")
    if MARKER not in included:
        raise Refused("the source marker must be included")
    course = git(j_git, "cat-file", "blob", entries[MARKER][1]).decode().strip()
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=".ji-", dir=os.path.dirname(output) or ".")
    bare = os.path.join(tmp, "JI.git")
    subprocess.run(["git", "init", "-q", "--bare", "--template=", bare], check=True, env=ENV)  # no hooks/*.sample in the output
    selected = {p: entries[p] for p in included}
    for p, (_, oid) in sorted(selected.items()):
        data = git(j_git, "cat-file", "blob", oid)
        if git(bare, "hash-object", "-w", "--stdin", data=data).decode().strip() != oid:
            raise Refused(f"blob changed in transit: {p}")
    tree = mktree(bare, selected)
    commit = git(bare, "commit-tree", tree, "-m", "J-input").decode().strip()
    git(bare, "update-ref", REF, commit)
    git(bare, "symbolic-ref", "HEAD", REF)
    if read_tree(bare, commit) != selected:
        raise Refused("output tree differs from the selection")
    passport = {"version": 1, "source_C": course, "j_commit": j_commit,
                "j_tree": git(j_git, "rev-parse", j_commit + "^{tree}").decode().strip(),
                "second_filter_path": FILTER, "second_filter_blob": filter_blob,
                "second_filter_sources": sources, "second_filter_file": "FILTER-JI.json",
                "j_input_commit": commit, "j_input_tree": tree, "ref": REF,
                "files_in_j": len(entries), "files_in_j_input": len(selected),
                "operator_sha256": sha256_file(__file__)}
    with open(os.path.join(tmp, "FILTER-JI.json"), "xb") as f:
        f.write(raw)
    with open(os.path.join(tmp, "PASSPORT-JI.json"), "x") as f:
        json.dump(passport, f, indent=2, sort_keys=True)
        f.write("\n")
    os.rename(tmp, output)
    return passport


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--j-git-dir", required=True)
    ap.add_argument("--j-commit", required=True)
    ap.add_argument("--filter-blob", required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args(argv)
    try:
        print(json.dumps(build(a.j_git_dir, a.j_commit, a.filter_blob, a.output), sort_keys=True))
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
