# Answers files of the model stub — acceptance 2

This English text is the source; the Russian translation `ru/vectors/model-stub/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The owner is lesson V/10 ([the norms of chapter 2](../../spec/10.2-assist.norms.md) Н5 «Заглушка модели»). They are read by the runner program
`model-stub`: the stand of acceptance 2 names the scenario file in `MODEL_COMMAND` (`{model_stub} {spec}/VMS/10-assist/vectors/model-stub/<сценарий>.tsv` — the file by the scenario name,
[the README of acceptance 2](../../acceptance/2/README.md)). The file is not an expectation: it sets what the «model» will answer; the expectations are in
`scenarios.tsv` of the acceptance.

The file form — UTF-8, LF, the fields separated by TAB, lines with `#` are explanations:
- the first line is `load <секунды>` or `load hang`: for that many seconds from the start `GET /health` answers 503 (with `load hang`
  — always: the model does not load), then 200 — also during a step;
- an optional second line `busy`: during a step `GET /health` answers 503, like a server with one busy slot;
- then a line for each request `POST /v1/chat/completions` in order: `<после>` (seconds or `hang`), `<статус>`,
  `<тело ответа JSON>`; `hang` — there is no answer until the holder breaks the connection; not enough lines — 500.

| File | Scenario | What it answers |
|---|---|---|
| `01-loading.tsv` | `01-loading` | never loads |
| `02-step.tsv` | `02-step` | loaded at once; the first step — `готово`; the second — `hang`; the third — 500; the fourth (a step with history) — `дальше` |
| `03-limits.tsv` | `03-limits` | two steps — `hang`; during a step `/health` — 503 (`busy`) |
| `04-owner.tsv` | `04-owner` | one step — `для ann` |
