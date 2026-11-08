# Optional SMT checks of ordered forms

ADR-0133 addendum (8), item 2 permits Z3 for a disputed question about an ordered
form: influence on a verdict, an unreachable row, or conflicting outcomes. This
tool runs a manually supplied SMT encoding through the Python Z3 API. It does not
translate CEL. It is not imported or run by `check_spec`, and it does not gate a
trial.

The dependency is separate from the course checker's requirements. Create an
external environment and install this directory's exact pin:

```sh
python3.12 -m venv /absolute/external/form-smt-env
/absolute/external/form-smt-env/bin/python -m pip install -r tools/form-smt/requirements.txt
```

The selected release is [z3-solver 4.16.0.0](https://pypi.org/project/z3-solver/4.16.0.0/).
The runner checks both the installed distribution version and the native Z3
version before solving. It uses the official Python
[Solver API](https://z3prover.github.io/api/html/classz3py_1_1_solver.html).
The regular checker's environment needs no Z3 installation. Importing this runner
and requesting `--help` also do not load Z3.

## A hash-bound question

Keep a binding JSON outside the model input. Select a full immutable source
commit, the form's normalized repository path and SHA256, and the encoding's
path and SHA256. Relative encoding/review paths are relative to the binding file.
An encoding path may be absolute. All hashes below are placeholders:

```json
{
  "version": 1,
  "source_commit": "<full 40-character lowercase Git commit>",
  "question": "<the disputed question>",
  "form": {"path": "Platform/01-store/forms/write-checks.tsv", "sha256": "<64 hex characters>"},
  "encoding": {"path": "question.smt2", "sha256": "<64 hex characters>"},
  "translator_provider": "openai",
  "abstraction": "<what the encoding abstracts and does not establish>"
}
```

Run it with an explicit source worktree and a fresh external report path:

```sh
/absolute/external/form-smt-env/bin/python -I -B tools/form-smt/solver_run.py bound \
  --source-root /absolute/course-worktree \
  --binding /absolute/artifacts/binding.json \
  --output /absolute/artifacts/new-result.json
```

The form comes from the selected Git blob, not a dirty working file. Wrong/missing
commits, nonregular blobs and stale form or encoding hashes refuse before a
solver result can be reported. If the form changes, the old binding is stale.
Rebinding to a new form is a new translation/review decision, not an automatic
update of the expected hash.

## Translation review

A different provider must review whether the encoding faithfully represents the
selected form and question. In particular, treating CEL predicates as independent
Boolean flags does not establish their real meaning or relationships. A solver
answer alone does not establish the claim about the form.

After the coordinator has received the actual other-provider review, add
`"review": {"path": "review.json", "sha256": "<64 hex characters>"}` to the
binding. The referenced review record contains:

```json
{
  "form_sha256": "<the bound form hash>",
  "encoding_sha256": "<the bound encoding hash>",
  "translator_provider": "openai",
  "reviewer_provider": "anthropic",
  "status": "approved",
  "notes": "<review scope and limits>"
}
```

`status` is `approved` or `rejected`. Provider names are canonical provider IDs,
not model or session names. The runner verifies hash consistency and rejects an
identical provider name, comparing names without case or surrounding whitespace.
It reports these declarations as `reported_approved` or `reported_rejected`.
It does not authenticate provider identity, obtain a review, or replace the
coordinator's acceptance. Without a review record the status is `pending`; even
with a record the runner's scope remains `hash_bound_encoding_only`.

## Unbound encodings and results

When the source commit/hash/translation provenance is unknown, use the explicitly
unbound mode rather than inventing a binding:

```sh
/absolute/external/form-smt-env/bin/python -I -B tools/form-smt/solver_run.py encoding-only \
  --encoding /absolute/artifacts/question.smt2 \
  --output /absolute/artifacts/new-encoding-result.json
```

This reports `unbound_encoding_only` and no form identity. The owner's two flat
write-checks samples can be reproduced this way; their Boolean abstraction still
needs a reviewed source binding before it is a statement about the form.

The SMT input is one declarative query: declarations/definitions/assertions, an
optional logic declaration, and at most one final `check-sat`. File commands,
options, push/pop/reset and additional queries are rejected. The runner itself
performs `check()`, extracts a model for `sat`, a named core for `unsat`, or
`reason_unknown()` for `unknown`. Unknown is never success or unsatisfiability.
Optional `--timeout-ms` and `--resource-limit` are caller-supplied Z3 limits, not
new course budgets; no numeric limit is imposed by default.

For core extraction, outer `:named` assertion labels must be unique fresh symbols
that the encoding does not otherwise reference. The runner parses the formulas
with Z3 and uses `assert_and_track`; it does not assume the SMT parser retains
labels. Unnamed assertions remain background constraints, so a core can be empty
when their contradiction alone suffices. A core is not promised minimal.

Exit 0 means an encoding result was recorded, including `unknown`; exit 2 is an
input/dependency/report failure. Reports are new immutable files, outside source
worktrees. They include exact form/encoding/review hashes, pinned solver version,
actual start/end times and the raw model/core/reason. Treat reports, bindings and
encodings as judge-side artifacts; do not put their answers or hashes in model
input. No trial, generator, SDK or mandatory checker is invoked by this tool.

Focused controls, using the optional environment:

```sh
/absolute/external/form-smt-env/bin/python -I -B tools/form-smt/test_solver_run.py -v
```
