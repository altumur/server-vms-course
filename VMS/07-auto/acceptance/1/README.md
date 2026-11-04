# Acceptance V/07.1 — the scenario: the unit and the language

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`07.1-auto.norms.md`](../../spec/07.1-auto.norms.md) Н5. The stand and the vocabulary are [the common VMS acceptance
README](../../../common/acceptance/README.md) over the common platform README (export `7a875c75`).

## Preparation

The store and the cluster console; the VMS manifests `cam`, `rec`, `det`, `detjob`, `auto` are installed (the orderers and the addressees of the
orders of `auto`); the console — `CONSOLE_ROOT=auto` (the door `/scenarios`). The controller, the workers, the resource and the domain are not started.
Requests — from loopback without a domain (one identity with full rights). A scenario — on a clean instance.

| Scenario | Norm | What it observes |
|---|---|---|
| `01-create` steps 1–6 | V/07.1-01, V/07.1-02, V/07.1-03 | a scenario with the defaults and the number 1 (`match` and `port` are integers, V/01.2 Н1.5, V/01.4 Н1.1); an empty `when` is set up; an extra trigger key, an action not from the forms, `within` greater than an hour, `valid_for` 3 — 400 |
| `01-create` steps 7–10 | V/07.1-03 | each of the other four forms of an action is set up (201) |
| `01-create` steps 11–20 | V/07.1-03 | for each form — without a required key and with an extra key — 400 |
| `01-create` steps 21–28 | V/07.1-01, V/07.1-02, V/07.1-03 | five triggers, five actions — 400; `rate_per_minute` 601 — 400, `0` is stored; `valid_for` `0` is stored, `9` — 400; `minutes` as a string, `port` as a string — 400 |
| `02-key` | V/07.1-06 | `id` in the body — 400; Cyrillic and spaces in the name; an edit of the name, the number stays the same |
| `03-fields` | V/07.1-07 | `run_at`, an unfinished row, the new fields are stored; the enumerations and the forms — 400 |
| `04-target` | V/07.1-08 | a target that is an area, `null`, `from_event`; `unit` together with `target`, a foreign `kind` of an area — 400 |
| `05-conditions` | V/07.1-09 | five conditions are set up; a foreign `kind`, an extra key — 400 |
| `06-steps` | V/07.1-10 | four flow steps, two depths of branches, the third — 400; arming, switching off, an alarm, a run of another one; a step without a subject is stored as data; the form of a step inside a branch is not judged at the door |
| `07-requests` | V/07.4-11, V/07.4-13 | the requests `run`, `retry` are accepted (202: there is no holder on the stand, there is no execution); another action, an extra key — 400; a row `rule_marks` is set up, the scenario's `revision` stays the same; `POST /chains` — 403: a worker table |
| `08-run` | V/07.2-06, V/07.4-07, V/07.4-08, V/07.4-10, V/07.4-11, V/07.4-12, V/07.4-13 | `@manual`: a run on the evaluator — the run row, the waiting, `repeat`, the checks, the targets, `retry`, the door `test`, the chain; on the chapter's stand the workers are not brought up |

Step 1 of `01-create` is the first creation on a clean instance, hence the number 1; the scenario remembers the other numbers (`$k`). The rights (`rights`), the meaning of the scenario (chapter 3) and the firing (chapter 4) —
by reading and by a scenario of the implementation's stand.
