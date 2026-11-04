# Vectors of the tools and of the plan check — V/11.10, V/11.11

This English text is the source; the Russian translation `ru/vectors/plan-check/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The vectors of chapter 10 (the read tools, the answer to the admin) and of chapter 11 (the plan, the words reconciliation, the question and the refusal) of lesson V/11. They
are executed by the `backend` driver (V/11.7 Н5) with the harness data [`harness/`](../../harness/) and a console stub built from the
console file below. There is no model in the vectors: the tool calls are given ready-made.

## Files

| File | What |
|---|---|
| `stand3.console.json` | the console of the pilot's stand 3: the seed and the overview manifests of the handover package in the form of the lesson's console doors (V/11.10 Н1.2) |
| `vms.console.json` | the VMS console: the canon manifests of `cam` and `rec` as the projection `ManifestView`, several cameras, a stream, recordings; the admin has `admin` on `*` |
| `text.json` | the words reconciliation of V/11.11 Н1.2 — the function, the arguments, the expectation; `said` — the expressions `rights`, `not_found`, `all` over `norm`, with Russian words at the boundaries (ADR-0093 addenda (28), (29)) |
| `cases.json` | turns: the texts of the turn, the secrets, the tool calls in order and the expected result of each |

## The console (`<имя>.console.json`)

`backend` takes the scope, the root and the manifests by V/11.10 Н0, Н1.2: the scope is the subsystems of the console
(or `subs` of the case), the root is `mounts.root`, the manifest is `manifests[<sub>]`; «в охвате ли» ("whether in scope") is whether the subsystem is in the
console.

```yaml
mounts:     {root, mounts: {<sub>: ManifestView}} — the root and the subsystems of the console
manifests:  {<sub>: ManifestView} — copies of the module
rows:       {<sub>: [element configured]} — GET /<rows> at the root, GET /<sub>/<rows> at another one: {rows: [], configured: …}
tables:     {<sub>: {<table>: [row]}} — GET /<table> at the root, GET /<sub>/<table>: {<table>: […]}
session:    the module session — for may() of the stub (the page does not read it)
schema:     the answer of GET /schema
```

Any other path — 404 `{error: "no_route"}`. `may(cap, ref, sub)` of the stub is the module rule (P/07 Н1.5): an emergency session
(`via: break-glass`) and the open mode — yes; otherwise a grant of a rank not lower than `cap` with the scope `*`, `unit:<sub>/<id>` of the unit or
of its `about` unit, `labels:<…>` — all labels are on the `about` unit if there is one, otherwise on the unit itself (the module rule
`covers`). The write right is `may("admin", …)`
(V/11.10 Н1.2).

Differences from the pilot's stand: the `edit` grants are raised to `admin` (the write door of a unit row requires `admin`, ADR-0093 addendum (4)
item 4); the field captions and the operator words of the pilot lie in the `display` of the manifests (`fields`, `field_help`), not as an overlay;
a field not set and without a default is `null`.

## The turn (`cases.json`)

```yaml
id:        the case name
console:   the console name — the file <name>.console.json
rule:      the norm rule the case holds (or «replay of the pilot base: <набор> <просьба> (<вид>)» — <набор> is the set, <просьба> the request, <вид> the kind)
violates:  present — the case is «violated but passes»: the check lets it through, the reason in words (a measurement gap, the lesson README)
source:    lesson — a lesson case; pilot <set> <request> — calls of the pilot's base run
texts:     the texts of the turn (V/11.9 Н0): the request, then the admin's answers
secrets:   numbers of the secrets entered in the turn (V/11.12 Н1.3); absent — there are no secrets
session:   the fields that replace the session of the console (grants, an emergency session)
fail:      {<path>: <status>} — these console reads answer with the status with {error: "unavailable", detail: "test"}
subs:      the scope — the subsystems of the page, if not all subsystems of the console
bulk:      {<sub>: N} — the rows of the subsystem are padded to N with copies of the first row: id bulk-1, bulk-2, …, the name field (if the id
           of the manifest is not numeric) — the same id, revision 1 (the boundary LIST_MAX, V/11.10 Н1.2)
calls:     [{name, args, content}] — the calls in order in one turn; content — the expected content of the result (V/11.10 Н1.3)
```

One turn per case: the account of what was found during the turn (`find_units` → the `refuse` check) and «раз за ход» ("once per turn") (the «не найдено» ("not found") check)
go by the calls of the case. `content` is compared byte for byte. The turn loop (prompts, «сначала данные» ("data first"), `not executed`,
the limit) is not here: the vectors `turn` (V/11.9 Н5).

## Where the expectations come from

- **Replay of the pilot's base** (`source: pilot …`): all tool calls of the six sets of stand 3 of the base run
  (v4.0 + `tool_choice: required`), except the loop prompt «сначала данные» ("data first"). The translation to the lesson's form: the pilot's secret slot is
  the label `{"secret": 1}`, the password is removed from the request text (it is in a form field). The verdict matches the pilot's verdict
  in 174 calls out of 175; L07 differs — `named: ["Spruce"]` for the request «Remove the label floor2 from all counters»:
  the rule `named` (ADR-0093 addendum (4) item 5) rejects a plan that the pilot accepted (the lesson README, «Правки после замера»).
- **Lesson cases** (`source: lesson`): each rule of V/11.10 Н1.5 and V/11.11 Н1.3–Н1.5 — at least once «violated» and «not
  violated»; the forms of «нет прав» ("no rights") one each; the classes «violated but passes» — with `violates`. The cases `vms-*` are Russian requests
  over the VMS manifests with the `display` captions and the operator words of `words.json`: «Выключи» ("Switch off") names «Включена» ("Enabled"), a field substitution
  is rejected; `vms-passes-days` — «дней» ("days") names both `retention_days` and `min_depth_days` (`violates`).
- Each `op` of V/11.10 Н1.5 is called in the arguments of the corpus (the vector generator checks this); `gte` and `lt` — on
  a smaller, an equal and a greater value.
- `content` is built by the removed core of the page and reconciled with the norm line by line; an edit of the norm or of the harness changes the vectors in the same
  commit.
