# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/2/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

### Original passage 1

The file has 11 scenarios / 67 steps (mutation check 7cecaf2 № 28, 31: `never` for admin, `/v1/rights` only for admin; sc. 11–13 — the coverage audit of P/01 2026-10-30: `never` of the floor and of `domain/`, a role header on listing, the rights file — `@rights store`; sc. 14–15 — its second pass: the bounds of `never`, the domain roles, `comment`); the rights
file of the stand is a ready input [`inputs/rights.json`](inputs/rights.json) (the form of P/01.2 N1.2): the roles `console`,
`testsubcontroller`, `testsubworker`, `testsub2worker` and the patterns the steps need — a subset of the rights output of P/02.5 N1.4 for
`testsub` and `testsub2` (`Platform/common/data/testsub/testsub*.subsystem.yaml`) with the deployment name `testsub`. The runner puts it
into `{rights}` before the store starts; the chapter needs no rights generator: the chapter checks the evaluator, not the output. The scenarios were moved from the acceptance of M10/06
(stage B) with the former numbers, steps and texts; the scenarios of the rights output from a manifest are in [the acceptance of P/02.5](../../../02-installer/acceptance/5/README.md).

### Original passage 2

- `expect` without a body for code `403` is the full form `{kind: forbidden, error: …}`. For a refusal of an operation on a row, error names the role, the action and the key. For an identity refusal in scenario 08 — the socket role `testsubworker` and the reason why the role header is prohibited (naming the route is admissible); the key of the row is not required, and the imposed role console does not replace the socket role.
