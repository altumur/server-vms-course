"""Optional, hash-bound SMT diagnostics for manually translated course forms.

The solver checks an encoding. It does not translate CEL or establish that the
encoding represents its form. Cross-provider translation review is an external
record, bound to both raw hashes; this program does not authenticate reviewers.
"""

import argparse
import datetime
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import time


PIN_FILE = Path(__file__).with_name("requirements.txt")
HEX256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
DECLARATIONS = {"set-logic", "declare-const", "declare-fun", "declare-sort",
                "declare-datatype", "declare-datatypes", "define-fun",
                "define-fun-rec", "define-funs-rec", "define-sort", "assert"}


class InputError(ValueError):
    pass


class DependencyError(InputError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def object_json(data, where):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise InputError(f"{where}: duplicate JSON member {key!r}")
            result[key] = value
        return result
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(
                               InputError(f"{where}: non-finite JSON number")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InputError(f"{where}: invalid UTF-8 JSON") from exc
    if type(value) is not dict:
        raise InputError(f"{where}: expected an object")
    return value


def exact_keys(value, required, optional, where):
    if type(value) is not dict or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise InputError(f"{where}: wrong fields")


def text(value, where):
    if type(value) is not str or not value.strip():
        raise InputError(f"{where}: expected nonempty text")
    return value


def digest(value, where):
    if type(value) is not str or not HEX256.fullmatch(value):
        raise InputError(f"{where}: expected a lowercase SHA256")
    return value


def expected_file(record, base, where):
    exact_keys(record, ("path", "sha256"), (), where)
    name = text(record["path"], f"{where}.path")
    if "\x00" in name:
        raise InputError(f"{where}.path: NUL is not allowed")
    expected = digest(record["sha256"], f"{where}.sha256")
    path = (base / name).resolve()
    if not path.is_file():
        raise InputError(f"{where}: not a file")
    data = path.read_bytes()
    if sha256(data) != expected:
        raise InputError(f"STALE {where}: SHA256 differs")
    return path, data


def git_form(root, commit, relative):
    root = Path(root).resolve(strict=True)
    if type(commit) is not str or not COMMIT.fullmatch(commit):
        raise InputError("source_commit must be a full lowercase 40-character Git commit")
    if type(relative) is not str or not relative or "\\" in relative or "\x00" in relative:
        raise InputError("form.path must be a normalized relative Git path")
    path = PurePosixPath(relative)
    if path.is_absolute() or path.as_posix() != relative or any(p in (".", "..") for p in path.parts):
        raise InputError("form.path must be a normalized relative Git path")

    def git(*args):
        actual = subprocess.check_output(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                                         text=True, stderr=subprocess.PIPE).strip()
        if Path(actual).resolve() != root:
            raise InputError("source-root must be the exact Git worktree root")
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)

    try:
        actual_commit = git("rev-parse", "--verify", commit + "^{commit}").decode().strip()
        if actual_commit != commit:
            raise InputError("source commit identity differs")
        entry = git("ls-tree", "-z", commit, "--", relative).split(b"\0")
        if len(entry) != 2 or entry[-1]:
            raise InputError("form must name exactly one Git blob")
        metadata, actual_path = entry[0].split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        if mode != "100644" or kind != "blob" or actual_path.decode() != relative:
            raise InputError("form must be a regular 100644 Git blob")
        data = git("show", commit + ":" + relative)
    except (subprocess.CalledProcessError, UnicodeError, ValueError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError("cannot read the pinned Git form") from exc
    return data, {"source_commit": commit, "path": relative, "blob": oid,
                  "sha256": sha256(data), "bytes": len(data), "mode": mode}


def review_record(record, base, form_hash, encoding_hash, translator):
    if record is None:
        return {"status": "pending", "different_provider_reported": False}
    path, data = expected_file(record, base, "review")
    review = object_json(data, "review")
    exact_keys(review, ("form_sha256", "encoding_sha256", "translator_provider",
                        "reviewer_provider", "status"), ("notes",), "review")
    if digest(review["form_sha256"], "review.form_sha256") != form_hash or \
            digest(review["encoding_sha256"], "review.encoding_sha256") != encoding_hash:
        raise InputError("STALE review: form or encoding hash differs")
    original = text(review["translator_provider"], "review.translator_provider").strip().casefold()
    other = text(review["reviewer_provider"], "review.reviewer_provider").strip().casefold()
    if original != translator.strip().casefold():
        raise InputError("review translator does not match the binding")
    if other == original:
        raise InputError("translation reviewer must be a different provider")
    if review["status"] not in ("approved", "rejected"):
        raise InputError("review.status must be approved or rejected")
    if "notes" in review:
        text(review["notes"], "review.notes")
    return {"status": "reported_" + review["status"], "path": str(path),
            "sha256": sha256(data), "translator_provider": translator,
            "reviewer_provider": review["reviewer_provider"], "different_provider_reported": True,
            "identity_authentication": "not performed; coordinator must accept the external review"}


def read_binding(binding_path, source_root):
    binding_path = Path(binding_path).resolve(strict=True)
    data = binding_path.read_bytes()
    binding = object_json(data, "binding")
    exact_keys(binding, ("version", "question", "source_commit", "form", "encoding", "translator_provider"),
               ("review", "abstraction"), "binding")
    if type(binding["version"]) is not int or binding["version"] != 1:
        raise InputError("binding.version must be 1")
    question = text(binding["question"], "binding.question")
    translator = text(binding["translator_provider"], "binding.translator_provider")
    if "abstraction" in binding:
        text(binding["abstraction"], "binding.abstraction")
    exact_keys(binding["form"], ("path", "sha256"), (), "form")
    expected = digest(binding["form"]["sha256"], "form.sha256")
    form, form_identity = git_form(source_root, binding["source_commit"], binding["form"]["path"])
    if sha256(form) != expected:
        raise InputError("STALE form: SHA256 differs")
    encoding_path, encoding = expected_file(binding["encoding"], binding_path.parent, "encoding")
    encoding_hash = sha256(encoding)
    review = review_record(binding.get("review"), binding_path.parent, expected, encoding_hash, translator)
    return encoding, {"scope": "hash_bound_encoding_only", "question": question,
                      "binding": {"path": str(binding_path), "sha256": sha256(data)},
                      "form": form_identity,
                      "encoding": {"path": str(encoding_path), "sha256": encoding_hash, "bytes": len(encoding)},
                      "translator_provider": translator, "translation_review": review,
                      "abstraction": binding.get("abstraction"),
                      "form_semantic_claim": "not established by the runner"}


def smt_commands(data):
    """Admit one declarative SMT query, without state changes or file commands."""
    try:
        source = data.decode("utf-8")
    except UnicodeError as exc:
        raise InputError("encoding must be UTF-8") from exc
    commands = []
    i = 0
    while i < len(source):
        if source[i].isspace():
            i += 1
            continue
        if source[i] == ";":
            i = source.find("\n", i)
            if i == -1:
                break
            continue
        if source[i] != "(":
            raise InputError("SMT encoding must contain top-level commands")
        start = i
        depth, quoted, symbol = 0, False, False
        while i < len(source):
            char = source[i]
            if quoted:
                if char == '"':
                    if i + 1 < len(source) and source[i + 1] == '"':
                        i += 2
                        continue
                    quoted = False
            elif symbol:
                if char == "|":
                    symbol = False
            elif char == ";":
                end = source.find("\n", i)
                i = len(source) if end == -1 else end
                continue
            elif char == '"':
                quoted = True
            elif char == "|":
                symbol = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
        if depth or quoted or symbol:
            raise InputError("unclosed SMT command")
        command = source[start:i]
        match = re.match(r"\(\s*([a-zA-Z0-9_-]+)(?:\s|\))", command)
        if not match:
            raise InputError("unsupported SMT command head")
        commands.append((match[1], command))
    queries = [i for i, (name, _) in enumerate(commands) if name == "check-sat"]
    if len(queries) > 1 or queries and queries[0] != len(commands) - 1:
        raise InputError("only one final check-sat is permitted")
    for name, command in commands:
        if name == "check-sat" and symbol_tokens(command) != [
                ("parenthesis", "("), ("symbol", "check-sat"), ("parenthesis", ")")]:
            raise InputError("check-sat takes no arguments")
    if any(name not in DECLARATIONS | {"check-sat"} for name, _ in commands):
        raise InputError("only declarative SMT commands and one final check-sat are supported")
    if not any(name == "assert" for name, _ in commands):
        raise InputError("encoding must contain an assertion")
    return commands


def symbol_tokens(source):
    """Lexical tokens only, to retain top-level assertion labels without guessing formulas."""
    tokens, i = [], 0
    while i < len(source):
        char = source[i]
        if char.isspace():
            i += 1
        elif char == ";":
            end = source.find("\n", i)
            i = len(source) if end == -1 else end
        elif char in "()":
            tokens.append(("parenthesis", char))
            i += 1
        elif char == '"':
            start = i
            i += 1
            while i < len(source):
                if source[i] == '"':
                    i += 1
                    if i < len(source) and source[i] == '"':
                        i += 1
                    else:
                        break
                else:
                    i += 1
            else:
                raise InputError("unclosed SMT string")
            tokens.append(("string", source[start:i]))
        elif char == "|":
            end = source.find("|", i + 1)
            if end == -1:
                raise InputError("unclosed SMT quoted symbol")
            tokens.append(("symbol", source[i + 1:end]))
            i = end + 1
        else:
            end = i + 1
            while end < len(source) and not source[end].isspace() and source[end] not in '();"|':
                end += 1
            tokens.append(("symbol", source[i:end]))
            i = end
    return tokens


def assertion_labels(commands):
    labels = []
    all_tokens = []
    for name, command in commands:
        tokens = symbol_tokens(command)
        all_tokens.extend(tokens)
        if name != "assert":
            continue
        label = None
        if tokens[:4] == [("parenthesis", "("), ("symbol", "assert"),
                           ("parenthesis", "("), ("symbol", "!")]:
            depth = 0
            for index, token in enumerate(tokens):
                if token == ("parenthesis", "("):
                    depth += 1
                elif token == ("parenthesis", ")"):
                    depth -= 1
                elif token == ("symbol", ":named") and depth == 2:
                    if label is not None or index + 1 >= len(tokens) or tokens[index + 1][0] != "symbol":
                        raise InputError("assertion must have one symbolic tracking label")
                    label = tokens[index + 1][1]
        labels.append(label)
    named = [value for value in labels if value is not None]
    if len(named) != len(set(named)):
        raise InputError("assertion tracking labels must be unique")
    for name in named:
        if all_tokens.count(("symbol", name)) != 1:
            raise InputError("tracking labels must be fresh and not referenced by the encoding")
    return labels


def load_z3():
    pin = PIN_FILE.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"z3-solver==[0-9]+(?:\.[0-9]+){3}", pin):
        raise DependencyError("optional Z3 pin is malformed")
    expected = pin.split("==")[1]
    try:
        actual = importlib.metadata.version("z3-solver")
    except importlib.metadata.PackageNotFoundError as exc:
        raise DependencyError("optional z3-solver is absent; install the separate pinned requirements") from exc
    if actual != expected:
        raise DependencyError(f"optional z3-solver version differs: expected {expected}, found {actual}")
    try:
        z3 = importlib.import_module("z3")
    except (ImportError, OSError) as exc:
        raise DependencyError("the pinned optional Z3 module cannot be loaded") from exc
    if tuple(z3.get_version()) != tuple(map(int, expected.split("."))):
        raise DependencyError("native Z3 version differs from the package pin")
    return z3, {"distribution": "z3-solver", "package_version": actual,
                "native_version": z3.get_full_version(), "module": str(Path(z3.__file__).resolve())}


def solve_encoding(data, *, timeout_ms=None, resource_limit=None):
    commands = smt_commands(data)
    source = "\n".join(command for name, command in commands if name != "check-sat")
    labels = assertion_labels(commands)
    for name, value in (("timeout_ms", timeout_ms), ("resource_limit", resource_limit)):
        if value is not None and (type(value) is not int or value < 0):
            raise InputError(f"{name} must be a nonnegative caller-supplied integer")
    z3, version = load_z3()
    context = z3.Context()
    parsed = z3.Solver(ctx=context)
    try:
        parsed.from_string(source)
        formulas = list(parsed.assertions())
        assertions = len(formulas)
        if not assertions:
            raise InputError("Z3 received no assertions")
        if assertions != len(labels):
            raise InputError("Z3 assertion inventory differs from the declarative encoding")
        solver = z3.Solver(ctx=context)
        solver.set(unsat_core=True)
        if timeout_ms is not None:
            solver.set(timeout=timeout_ms)
        if resource_limit is not None:
            solver.set(rlimit=resource_limit)
        for formula, label in zip(formulas, labels):
            if label is None:
                solver.add(formula)
            else:
                solver.assert_and_track(formula, z3.Bool(label, ctx=context))
        answer = solver.check()
        result = {"result": str(answer), "assertions": assertions, "version": version,
                  "limits": {"timeout_ms": timeout_ms, "resource_limit": resource_limit},
                  "tracked_assertions": sum(value is not None for value in labels),
                  "core_scope": "tracked labels; unlabelled assertions are background constraints"}
        if answer == z3.sat:
            result["model_smt2"] = solver.model().sexpr()
        elif answer == z3.unsat:
            result["unsat_core"] = sorted(str(item) for item in solver.unsat_core())
        elif answer == z3.unknown:
            result["reason_unknown"] = solver.reason_unknown()
        else:
            raise InputError("unsupported Z3 result")
    except z3.Z3Exception as exc:
        raise InputError(f"Z3 rejected the encoding: {exc}") from exc
    return result


def report_target(path, forbidden_roots):
    path = Path(path)
    if path.is_symlink():
        raise InputError("report must be a new regular file, not a symlink")
    path = path.resolve()
    for root in forbidden_roots:
        root = Path(root).resolve()
        if path == root or root in path.parents:
            raise InputError("report must be outside the source worktree")
    if path.exists():
        raise InputError("report already exists; choose a new artifact path")
    return path


def write_report(path, report, forbidden_roots):
    path = report_target(path, forbidden_roots)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    bound = sub.add_parser("bound", help="check an encoding bound to a pinned Git form hash")
    bound.add_argument("--binding", required=True, type=Path)
    bound.add_argument("--source-root", required=True, type=Path)
    raw = sub.add_parser("encoding-only", help="solve unbound SMT without a claim about a form")
    raw.add_argument("--encoding", required=True, type=Path)
    for command in (bound, raw):
        command.add_argument("--output", required=True, type=Path)
        command.add_argument("--timeout-ms", type=int)
        command.add_argument("--resource-limit", type=int)
    args = parser.parse_args(argv)
    try:
        start = datetime.datetime.now(datetime.timezone.utc).isoformat()
        clock = time.monotonic()
        forbidden = [Path(__file__).resolve().parents[2]]
        if args.mode == "bound":
            forbidden.append(args.source_root)
        report_target(args.output, forbidden)
        if args.mode == "bound":
            encoding, report = read_binding(args.binding, args.source_root)
        else:
            path = args.encoding.resolve(strict=True)
            encoding = path.read_bytes()
            report = {"scope": "unbound_encoding_only", "form": None,
                      "encoding": {"path": str(path), "sha256": sha256(encoding), "bytes": len(encoding)},
                      "translation_review": {"status": "not_bound_to_a_form"},
                      "form_semantic_claim": "not established by the runner"}
        report.update({"schema_version": 1, "optional_check": True,
                       "start_utc": start,
                       "solver": solve_encoding(encoding, timeout_ms=args.timeout_ms,
                                                resource_limit=args.resource_limit)})
        report["end_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report["elapsed_seconds"] = time.monotonic() - clock
        write_report(args.output, report, forbidden)
        print(json.dumps({"report": str(args.output.resolve()), "result": report["solver"]["result"],
                          "scope": report["scope"]}, sort_keys=True))
    except (InputError, OSError) as exc:
        parser.exit(2, f"form-smt: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
