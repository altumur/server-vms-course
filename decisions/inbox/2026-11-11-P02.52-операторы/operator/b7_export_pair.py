#!/usr/bin/env python3
"""Privileged B7 pair creation mechanism, pending Root release (stdlib + Git).

This operator reads committed Source only. It does not select C, approve a filter,
prove receipt authenticity, run GREEN, materialize model views or launch a trial.
No invocation on an actual course/export is authorized by this preparation.

P02.52 (ADR-0135 addendum (14) item 3): the model filter is assembled from the common
filter and the `model` records of the lists `Platform/NN-<process>/forms/export.json` of
the lessons, by the rule of the common acceptance README («Target registry and export
lists assembled from the lessons», items 2-4). The blob bound by the authorization is the
blob of the assembled bytes; without lesson lists they are the canonical common filter.
"""
from __future__ import annotations

import argparse
import csv
import ctypes
import errno
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import uuid
from datetime import datetime, timezone

FILTER = "Platform/common/export-model-filter.json"
MARKER = "Platform/COURSE_COMMIT"
WIRE = "Platform/common/vectors/wire.tsv"
# P01.88 (ADR-0133 #22, Architect 2026-11-10): the public line protocol wire.tsv may be in M;
# the judge-side rows live in wire.cases.tsv, which is J-only, as is every case table either file names.
WIRE_CASES = "Platform/common/vectors/wire.cases.tsv"
DERIVED = "Platform/common/contracts/vector-adapter.protocol.json"
# ADR-0135 addendum (14) item 2: the list of the files of a lesson; item 3: the forms of every lesson.
LESSON_LIST = re.compile(r"Platform/(\d\d-[a-z0-9-]+)/forms/export\.json\Z")
LESSON_FORM = re.compile(r"Platform/\d\d-[a-z0-9-]+/(forms/(?:targets\.tsv|targets\.routing\.tsv|export\.json))\Z")
LESSON_RULES = {"forms/targets.tsv": "model_and_judge",          # the public target table
                "forms/targets.routing.tsv": "judge_only",       # the routing of the judge never reaches the model
                "forms/export.json": "judge_only"}               # as the common filters
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
ENV = {"PATH": os.defpath, "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
       "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_NO_REPLACE_OBJECTS": "1",
       "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0"}
ACTOR = "B7 export operator <b7-export@invalid>"
CONFIG = b"[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = true\n"
WIRE_HEADER = ["package", "table", "surface", "header", "inputs", "files",
               "expect", "compare", "markers", "native", "norm"]
# Literal maintenance sidecars from Root QC-B7-01 authority, not a kit substring policy.
STAGE_KIT_J_ONLY = frozenset({
    "Platform/01-store/forms/stages.kit.tsv",
    "Platform/02-installer/forms/stages.kit.tsv",
    "Platform/03-worker/forms/stages.kit.tsv",
    "Platform/04-controller/forms/stages.kit.tsv",
    "Platform/05-resource/forms/stages.kit.tsv",
    "Platform/06-console/forms/stages.kit.tsv",
    "Platform/08-domain/forms/stages.kit.tsv",
    "Platform/09-agent/forms/stages.kit.tsv",
    "Platform/10-domain-console/forms/stages.kit.tsv",
})
DELETION_WITNESS_J_ONLY = "Platform/06-console/forms/deletion-body-witnesses.json"
AUTH_KEYS = {"version", "authorization", "source_C", "filter_blob", "wire_blob",
             "derived_sha256", "source_acceptance_sha256", "green_check_sha256",
             "different_provider_filter_review_sha256", "filter_author_provider",
             "filter_reviewer_provider"}


class Refused(ValueError):
    """Invalid input. No Source payload is included in diagnostics."""


class RetainedFailure(RuntimeError):
    """Own failed output is retained. It is not a successfully published pair."""
    def __init__(self, path, publication_state):
        super().__init__("pair creation failed; owned evidence retained")
        self.path, self.publication_state = str(path), publication_state


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Refused("duplicate JSON key")
            result[key] = value
        return result
    try:
        text = raw.decode("utf-8", errors="strict") if isinstance(raw, bytes) else raw
        return json.loads(text, object_pairs_hook=unique)
    except Refused:
        raise
    except (ValueError, UnicodeError, TypeError) as exc:
        raise Refused("invalid UTF-8 JSON metadata") from exc


def _canonical(path):
    path = os.fspath(path)
    if not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or str(Path(path)) != path:
        raise Refused("explicit canonical absolute path required")
    if any(x in {".", ".."} for x in path.split("/")) or any(c in path for c in "\x00\n\r\t"):
        raise Refused("path alias or control character")
    return Path(path)


def _open_dir(path):
    """Open every directory component without following symlinks; caller closes FD."""
    path = _canonical(path)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except OSError as exc:
        os.close(fd)
        raise Refused("directory inaccessible or aliased") from exc


def _read_regular(path, limit):
    """Refuse known special files before open, and races without a blocking FIFO open."""
    path = _canonical(path)
    fd = _open_dir(path.parent)
    leaf = None
    try:
        before = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise Refused("bounded regular metadata file required")
        # O_NONBLOCK also protects the stat/open interval if a regular leaf is
        # replaced by a FIFO. O_NOFOLLOW rejects a substituted symlink.
        leaf = os.open(path.name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        opened = os.fstat(leaf)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_size > limit
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            raise Refused("metadata type or identity changed before read")
        chunks, size = [], 0
        while True:
            b = os.read(leaf, min(65536, limit + 1 - size))
            if not b:
                break
            size += len(b)
            if size > limit:
                raise Refused("metadata size limit")
            chunks.append(b)
        after = os.fstat(leaf)
        stable = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        if stable(after) != stable(opened) or size != opened.st_size:
            raise Refused("metadata changed during read")
        return b"".join(chunks)
    except OSError as exc:
        raise Refused("metadata inaccessible or aliased") from exc
    finally:
        if leaf is not None:
            os.close(leaf)
        os.close(fd)


def _git(fd, *args, data=None, environment=None):
    try:
        return subprocess.check_output(
            ["git", "--git-dir=/proc/self/fd/" + str(fd), *args], input=data,
            env=environment or ENV, pass_fds=(fd,), stderr=subprocess.PIPE, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise Refused("Git operation failed") from exc


def _path(value):
    if not isinstance(value, str) or not value.startswith("Platform/"):
        raise Refused("exact Platform file path required")
    parts = PurePosixPath(value).parts
    if (str(PurePosixPath(value)) != value or ".." in parts
            or any(x.casefold() == ".git" for x in parts)
            or any(c in value for c in "\\*?[]\x00\n\r\t")):
        raise Refused("noncanonical Platform path")
    return value


def _source(fd, commit):
    if not isinstance(commit, str) or not SHA1.fullmatch(commit):
        raise Refused("full immutable SHA-1 Source C required")
    if _git(fd, "rev-parse", "--show-object-format").strip() != b"sha1":
        raise Refused("Source object format unsupported")
    if _git(fd, "rev-parse", "--verify", commit + "^{commit}").strip().decode() != commit:
        raise Refused("Source C is not the explicit commit")
    entries = {}
    for raw in _git(fd, "ls-tree", "-rz", commit, "--", "Platform").split(b"\0"):
        if not raw:
            continue
        try:
            header, name = raw.split(b"\t", 1)
            mode, kind, oid = header.decode("ascii").split()
            name = _path(name.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise Refused("Source tree entry unsupported") from exc
        if kind != "blob" or mode not in {"100644", "100755"} or not SHA1.fullmatch(oid):
            raise Refused("nonregular Source entry unsupported")
        body = _git(fd, "cat-file", "blob", oid)
        if hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest() != oid:
            raise Refused("Source blob identity mismatch")
        entries[name] = (mode, oid, body)
    if not entries or MARKER in entries:
        raise Refused("missing Platform or reserved Course marker already on C")
    return entries


def _blob_id(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _sorted_records(records):
    """An array of records sorted by path as UTF-8 bytes, one record per path (shape is checked later)."""
    if not isinstance(records, list):
        raise Refused("filter records are not an array")
    keys = []
    for item in records:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise Refused("filter record shape")
        keys.append(item["path"].encode("utf-8"))
    if len(set(keys)) != len(keys):
        raise Refused("duplicate filter path")
    if keys != sorted(keys):
        raise Refused("filter records not sorted by path as UTF-8 bytes")
    return records


def _assemble(entries, side="model"):
    """ADR-0135 addendum (14): common filter + `side` records of every lesson list → (bytes, value, sources).

    A list is exactly {version: 1, model, judge}; each array is sorted, names every file of its
    lesson directory once and no other file. A path has one record in one place. The assembled
    value keeps the fields and their order of the common file; its `files` are all records sorted
    by path as UTF-8 bytes; its bytes are JSON, indent 2, non-ASCII as is, LF, final LF.
    """
    if FILTER not in entries:
        raise Refused("one committed course filter missing")
    value = _json(entries[FILTER][2])
    if not isinstance(value, dict) or "files" not in value:
        raise Refused("unsupported schema1 filter; self-marker exceptions not implemented")
    records = list(_sorted_records(value["files"]))
    sources = {FILTER: entries[FILTER][1]}
    for path in sorted(entries, key=lambda p: p.encode("utf-8")):
        match = LESSON_LIST.fullmatch(path)
        if not match:
            continue
        lesson = _json(entries[path][2])
        if (not isinstance(lesson, dict) or set(lesson) != {"version", "model", "judge"}
                or type(lesson["version"]) is not int or lesson["version"] != 1):
            raise Refused("lesson list must be exactly version 1, model and judge")
        prefix = "Platform/" + match.group(1) + "/"
        own = {p for p in entries if p.startswith(prefix)}
        for name in ("model", "judge"):
            named = [item["path"] for item in _sorted_records(lesson[name])]
            if set(named) != own:
                raise Refused("lesson list must name exactly the files of its lesson directory")
        records.extend(lesson[side])
        sources[path] = entries[path][1]
    keys = [item["path"].encode("utf-8") for item in records]
    if len(set(keys)) != len(keys):
        raise Refused("duplicate filter path")
    assembled = dict(value)
    assembled["files"] = sorted(records, key=lambda item: item["path"].encode("utf-8"))
    raw = (json.dumps(assembled, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return raw, assembled, sources


def _classification(entries):
    value = _assemble(entries)[1]
    if (not isinstance(value, dict) or set(value) != {"version", "files", "own_export_markers"}
            or type(value["version"]) is not int or value["version"] != 1
            or not isinstance(value["files"], list) or value["own_export_markers"] != []):
        raise Refused("unsupported schema1 filter; self-marker exceptions not implemented")
    selected = {}
    for item in value["files"]:
        if (not isinstance(item, dict) or set(item) != {"path", "disposition", "basis"}
                or not isinstance(item.get("disposition"), str)
                or item["disposition"] not in {"model_and_judge", "judge_only"}
                or not isinstance(item["basis"], str) or not item["basis"].strip()):
            raise Refused("filter record shape")
        p = _path(item["path"])
        if p in selected:
            raise Refused("duplicate filter path")
        selected[p] = item["disposition"]
    if set(selected) != set(entries):
        raise Refused("filter does not cover exact full J roster")
    if selected[FILTER] != "judge_only" or selected[MARKER] != "model_and_judge":
        raise Refused("filter must be J-only; Course marker must be in both")
    for p, role in selected.items():
        form = LESSON_FORM.fullmatch(p)
        if form and role != LESSON_RULES[form.group(1)]:
            raise Refused("lesson form classified against the common rule (routing or list must be J-only)")
    return selected


def _wire_case_tables(entries, path, leading_comments):
    """Case tables named by one wire file → set of paths. Header and row shape are strict."""
    text = entries[path][2].decode("utf-8")
    if leading_comments:                     # wire.cases.tsv opens with '#' lines before its header
        lines = text.split("\n")
        k = 0
        while k < len(lines) and lines[k].startswith("#"):
            k += 1
        text = "\n".join(lines[k:])
    reader = csv.DictReader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE)
    if reader.fieldnames != WIRE_HEADER:
        raise Refused("canonical wire header mismatch")
    cases = set()
    for row in reader:
        if not row or (row.get("package") or "").startswith("#"):
            continue
        package, table = row.get("package"), row.get("table")
        if (set(row) != set(WIRE_HEADER) or not isinstance(package, str)
                or not isinstance(table, str) or any(v is None for v in row.values())):
            raise Refused("wire row shape")
        lesson, sep, part = package.partition("/")
        if not sep or not part or not table:
            raise Refused("wire row interface")
        p = _path(f"Platform/{lesson}/vectors/{part}/{table}")
        if p not in entries:
            raise Refused("registered case table unavailable")
        cases.add(p)
    return cases


def _case_boundary(entries, selected):
    if WIRE not in entries:
        raise Refused("canonical committed wire missing")
    try:
        cases = _wire_case_tables(entries, WIRE, False)
        if WIRE_CASES in entries:
            cases |= _wire_case_tables(entries, WIRE_CASES, True)
        cases |= {p for p in entries if "/acceptance/" in p and p.endswith(("/scenarios.tsv", "/seams.tsv"))}
    except (UnicodeError, csv.Error, TypeError, KeyError) as exc:
        raise Refused("wire metadata unreadable") from exc
    # These are unconditional J-only classes, not semantic filter discretion.
    # Filename classification here NEVER changes the exact committed filter.
    mandatory = {p for p in entries if ".cases." in PurePosixPath(p).name
                 or p == DELETION_WITNESS_J_ONLY or p in STAGE_KIT_J_ONLY}
    if WIRE_CASES in entries:
        mandatory.add(WIRE_CASES)
    if any(selected[p] != "judge_only" for p in mandatory):
        raise Refused("unconditional judge-only file classified into model view")
    removed = {p for p, role in selected.items() if role == "judge_only"}
    # P01.88: wire.tsv itself is no longer required in J; every case table named by
    # wire.tsv or wire.cases.tsv, every scenario and seam table, stays J-only.
    if not cases or not removed or cases - removed:
        raise Refused("zero removal or registered case/wire retained in M")
    return cases


def _legacy_model_content_guard(entries):
    """Retain existing operator lexical guard; never alter filter membership.

    This does not prove semantic absence of cases or detect arbitrary encodings.
    Actual filter/provider review and Runner content guards remain external.
    """
    rx = re.compile(rb"/Users/|/home/[a-z]|/private/(tmp|var)|[A-Za-z_/]+\.py\b|[a-z_]+\.go\b|w2cplatform/")
    for path, (_, _, raw) in entries.items():
        if path in {"Platform/07-console-module/module/console.js", "Platform/07-console-module/module/console.css", "Platform/07-console-module/module/console.html"}:
            continue
        if path.startswith("Platform/common/vectors/yaml-suite/inputs/"):
            continue
        if path == "Platform/common/versions/README.md":
            raw = raw.replace(b"https://raw.githubusercontent.com/hashicorp/raft/v1.7.3/fsm.go", b"")
        if (path == "Platform/common/vectors/production-obligations/README.md"
                and hashlib.sha256(raw).hexdigest() == "7118252cc4757f7ca8dabdd8fed3325797c87c277cf0b2ac3400169248e2949d"):
            # ADR-0133(4) p6 permits this reviewed informational reference.
            raw = raw.replace(b"runner/common_contract_probes.py", b"", 1)
        if rx.search(raw):
            raise Refused("model content violates existing lexical leak guard")


def _authorization(raw, commit, entries):
    """Bind trusted authorization metadata. Authenticity/meaning is external to this operator."""
    a = _json(raw)
    if (not isinstance(a, dict) or set(a) != AUTH_KEYS or type(a["version"]) is not int
            or a["version"] != 1 or a["authorization"] != "ROOT_AFTER_STEP6_GREEN_AND_FILTER_REVIEW"):
        raise Refused("Root release authorization metadata required")
    if a["source_C"] != commit or a["filter_blob"] != _blob_id(_assemble(entries)[0]) or a["wire_blob"] != entries[WIRE][1]:
        raise Refused("authorization C/filter/wire mismatch")
    for k in ("derived_sha256", "source_acceptance_sha256", "green_check_sha256", "different_provider_filter_review_sha256"):
        if not isinstance(a[k], str) or not SHA256.fullmatch(a[k]):
            raise Refused("exact authorization digest required")
    for k in ("filter_author_provider", "filter_reviewer_provider"):
        if not isinstance(a[k], str) or not a[k].strip() or len(a[k]) > 80:
            raise Refused("filter provider identity required")
    if a["filter_author_provider"] == a["filter_reviewer_provider"]:
        raise Refused("different-provider filter review required")
    if DERIVED not in entries or hashlib.sha256(entries[DERIVED][2]).hexdigest() != a["derived_sha256"]:
        raise Refused("approved derived artifact must already exist on C")
    return a


def _write(fd, name, raw, mode=0o600):
    child = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode, dir_fd=fd)
    try:
        view = memoryview(raw)
        while view:
            n = os.write(child, view)
            if n <= 0:
                raise OSError(errno.EIO, "metadata write made no progress")
            view = view[n:]
        os.fsync(child)
    finally:
        os.close(child)


def _emit(stage_fd, name, entries, branch):
    # Each output has its own object store. Never clone/fetch/hardlink C or J.
    subprocess.check_output(["git", "init", "--bare", "--template=", "--object-format=sha1",
                             "/proc/self/fd/" + str(stage_fd) + "/" + name],
                            env=ENV, pass_fds=(stage_fd,), stderr=subprocess.PIPE, timeout=60)
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=stage_fd)
    try:
        # Git init is allowed to create only the structure; overwrite its version-specific
        # config to a fixed course-independent policy before this repository is used.
        conf = os.open("config", os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW, dir_fd=fd)
        try:
            view = memoryview(CONFIG)
            while view:
                n = os.write(conf, view)
                if n <= 0:
                    raise OSError(errno.EIO, "config write made no progress")
                view = view[n:]
            os.fsync(conf)
        finally:
            os.close(conf)
        nodes, expected = {}, set()
        for p, (mode, expected_oid, body) in sorted(entries.items()):
            oid = _git(fd, "hash-object", "-w", "--stdin", data=body).strip().decode()
            if expected_oid is not None and oid != expected_oid:
                raise Refused("whole retained blob changed")
            expected.add(oid)
            cursor = nodes
            parts = p.split("/")
            for part in parts[:-1]:
                cursor = cursor.setdefault(part, {})
            cursor[parts[-1]] = (mode, oid)
        def build(node):
            rows = []
            for key, val in sorted(node.items()):
                if isinstance(val, dict):
                    mode, kind, oid = "040000", "tree", build(val)
                else:
                    mode, oid = val; kind = "blob"
                rows.append(f"{mode} {kind} {oid}\t{key}".encode() + b"\0")
            oid = _git(fd, "mktree", "-z", data=b"".join(rows)).strip().decode()
            expected.add(oid)
            return oid
        tree = build(nodes)
        message = ("Model export\n" if branch == "model" else "Judge export\n").encode()
        # Epoch 0 is a declared canonical metadata value, never an execution timestamp.
        commit_raw = f"tree {tree}\nauthor {ACTOR} 0 +0000\ncommitter {ACTOR} 0 +0000\n\n".encode() + message
        commit = _git(fd, "hash-object", "-w", "-t", "commit", "--stdin", data=commit_raw).strip().decode()
        expected.add(commit)
        _git(fd, "update-ref", "refs/heads/" + branch, commit)
        _git(fd, "symbolic-ref", "HEAD", "refs/heads/" + branch)
        all_objects = {r.split()[0].decode() for r in _git(fd, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)").splitlines()}
        reachable = {r.split()[0].decode() for r in _git(fd, "rev-list", "--objects", commit).splitlines()}
        if all_objects != expected or reachable != expected:
            raise Refused("fresh repository object closure mismatch")
        refs = _git(fd, "for-each-ref", "--format=%(refname) %(objectname)").decode().splitlines()
        if refs != ["refs/heads/" + branch + " " + commit]:
            raise Refused("unexpected reference in fresh export")
        return {"commit": commit, "tree": tree, "objects": len(expected), "files": len(entries),
                "branch": branch, "commit_sha256": hashlib.sha256(commit_raw).hexdigest()}
    finally:
        os.close(fd)


def _seal_tree(fd, repo):
    """Fsync and inspect newly owned output. Not a general attacker-writable FS scanner."""
    allowed_top = {"HEAD", "config", "objects", "refs"}
    allowed_dirs = {"objects", "objects/info", "objects/pack", "refs", "refs/heads", "refs/tags"}
    def walk(dfd, prefix=""):
        for name in os.listdir(dfd):
            rel = prefix + name
            st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
            if stat.S_ISDIR(st.st_mode):
                if rel not in allowed_dirs and not re.fullmatch(r"objects/[0-9a-f]{2}", rel):
                    raise Refused("unexpected export directory metadata")
                nxt = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dfd)
                try: walk(nxt, rel + "/")
                finally: os.close(nxt)
            elif stat.S_ISREG(st.st_mode):
                if not (rel in {"HEAD", "config", "refs/heads/" + repo["branch"]}
                        or re.fullmatch(r"objects/[0-9a-f]{2}/[0-9a-f]{38}", rel)):
                    raise Refused("unexpected export file metadata")
                leaf = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dfd)
                try: os.fsync(leaf)
                finally: os.close(leaf)
            else:
                raise Refused("export alias/nonregular metadata")
        os.fsync(dfd)
    if set(os.listdir(fd)) != allowed_top:
        raise Refused("unexpected fresh bare repository layout")
    walk(fd)
    if _git(fd, "config", "--local", "--list").decode().splitlines() != ["core.repositoryformatversion=0", "core.filemode=true", "core.bare=true"]:
        raise Refused("export config policy mismatch")


def _publish(parent_fd, stage, final):
    # Unlike rename(), NOREPLACE never replaces an existing empty destination.
    libc = ctypes.CDLL(None, use_errno=True)
    call = getattr(libc, "renameat2", None)
    if call is None:
        raise Refused("atomic no-replace publication unavailable; no fallback")
    call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    call.restype = ctypes.c_int
    if call(parent_fd, os.fsencode(stage), parent_fd, os.fsencode(final), 1) != 0:
        e = ctypes.get_errno()
        raise OSError(e, "atomic no-replace publication failed")
    os.fsync(parent_fd)


def compose_pair(source_git_dir, source_C, output_dir, *, authorization_json):
    """Create a fresh private pair after external Root authorization.

    All Source/filter/authorization validation precedes output staging. Failed own
    staging is retained under hold; this function NEVER deletes or overwrites paths.
    Authorization strings are trusted inputs, NOT cryptographically authenticated.
    """
    source_git_dir, output_dir = _canonical(source_git_dir), _canonical(output_dir)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", output_dir.name):
        raise Refused("fresh output basename required")
    if source_git_dir == output_dir or source_git_dir in output_dir.parents:
        raise Refused("output must not be inside Source Git storage")
    parent_fd = source_fd = stage_fd = None
    stage, state = None, "not_created"
    try:
        parent_fd = _open_dir(output_dir.parent)
        parent_st = os.fstat(parent_fd)
        if parent_st.st_uid != os.geteuid() or parent_st.st_mode & 0o022:
            raise Refused("output parent must be owned and not group/world writable")
        try:
            os.stat(output_dir.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise Refused("output already exists; never overwrite")
        source_fd = _open_dir(source_git_dir)
        # Linked worktree metadata is not a complete Git-dir. Caller supplies the
        # canonical common object-store Git directory explicitly, never a .git file.
        if _git(source_fd, "rev-parse", "--git-common-dir").decode().strip() != "/proc/self/fd/" + str(source_fd):
            raise Refused("explicit common Git directory required")
        entries = _source(source_fd, source_C)
        entries[MARKER] = ("100644", None, (source_C + "\n").encode())
        selected = _classification(entries)
        cases = _case_boundary(entries, selected)
        authorization = _authorization(authorization_json, source_C, entries)
        if selected[DERIVED] != "model_and_judge":
            raise Refused("approved public derived contract must be in both views")
        model = {p: e for p, e in entries.items() if selected[p] == "model_and_judge"}
        _legacy_model_content_guard(model)
        filter_raw, _value, filter_sources = _assemble(entries)
        # Creation is possible only after all preflight checks. No mutation of C.
        new_stage = ".b7-stage-" + uuid.uuid4().hex
        os.mkdir(new_stage, 0o700, dir_fd=parent_fd)
        stage = new_stage
        stage_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        state = "staging_retained"
        judge_meta = _emit(stage_fd, "J.git", entries, "judge")
        model_meta = _emit(stage_fd, "M.git", model, "model")
        for name, meta in (("J.git", judge_meta), ("M.git", model_meta)):
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=stage_fd)
            try: _seal_tree(fd, meta)
            finally: os.close(fd)
        passport = {"format": "b7-pair-private-v1", "created_utc": _utc(), "C": source_C,
                    "M": model_meta, "J": judge_meta, "filter_path": FILTER,
                    "filter_blob": _blob_id(filter_raw),
                    "filter_sha256": hashlib.sha256(filter_raw).hexdigest(),
                    "filter_sources": filter_sources, "filter_file": "FILTER-M.json",
                    "authorization_sha256": hashlib.sha256(authorization_json).hexdigest(),
                    "trusted_authorization": authorization, "registered_cases_removed": len(cases),
                    "operator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "projection": "full_committed_Platform_J_one_assembled_filter_M",
                    "canonical_git_metadata": {"actor": ACTOR, "epoch": 0,
                        "epoch_is_execution_time": False, "config_sha256": hashlib.sha256(CONFIG).hexdigest()},
                    "mechanical_pair_only": True, "receipt_authenticity_verified": False,
                    "namespace_or_runtime_qualified": False, "Owner_pin_or_launch_selected": False}
        _write(stage_fd, "FILTER-M.json", filter_raw)
        _write(stage_fd, "PASSPORT-TRUSTED-ONLY.json", (json.dumps(passport, ensure_ascii=False, indent=2) + "\n").encode())
        os.fsync(stage_fd)
        _publish(parent_fd, stage, output_dir.name)
        state = "published_pair_needs_Root_acceptance"
        # A separate return value gives actual final path, never written into M.
        return {"status": state, "output_dir": str(output_dir), "passport": passport}
    except BaseException as exc:
        if stage is not None:
            # No cleanup: the ancestor is held. Even a failure is owned evidence.
            # Publication could have succeeded before a parent-fsync failure.
            location = output_dir.parent / stage
            try:
                os.stat(stage, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                location = output_dir
                state = "final_path_exists_durability_or_return_unqualified"
            if stage_fd is not None:
                try:
                    _write(stage_fd, "FAILED-RETAINED.json", (json.dumps({"utc": _utc(),
                        "status": state, "error_class": type(exc).__name__,
                        "no_cleanup": True, "not_accepted_pair": True}) + "\n").encode())
                except OSError:
                    pass
            raise RetainedFailure(location, state) from exc
        raise
    finally:
        for fd in (stage_fd, source_fd, parent_fd):
            if fd is not None:
                os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-git-dir", required=True)
    parser.add_argument("--course-commit", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--authorization-json", required=True)
    args = parser.parse_args(argv)
    try:
        authorization = _read_regular(args.authorization_json, 65536)
        result = compose_pair(args.source_git_dir, args.course_commit, args.output, authorization_json=authorization)
    except (Refused, OSError, RetainedFailure) as exc:
        diagnostic = {"status": "REFUSED_OR_RETAINED_NOT_ACCEPTED", "error_class": type(exc).__name__}
        if isinstance(exc, RetainedFailure):
            diagnostic.update(retained_path=exc.path, publication_state=exc.publication_state)
        print(json.dumps(diagnostic), file=sys.stderr)
        return 2
    print(json.dumps({"status": result["status"], "output_dir": result["output_dir"],
                      "C": result["passport"]["C"], "M": result["passport"]["M"]["commit"],
                      "J": result["passport"]["J"]["commit"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
