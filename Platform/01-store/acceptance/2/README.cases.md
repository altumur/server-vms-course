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

### Original passage 3

The roles of the scenarios: `console`, `testsubcontroller`, `testsubworker`, `testsub2worker`, `admin`; in sc. 14 after `@rights store
inputs/rights-domain-roles.json` — the domain roles `domain`, `domainagent`, `testsubdomain`.

### Original passage 4

Reconciliation of python and go M10/6–11 (R12): sc. 05 steps 8–10 — `never` and an empty `<y>`; sc. 08 step 2 — the role header before the body.

### Original passage 5

- Now by scenarios: a non-string `comment` is a start refusal, a string one is returned by `GET /v1/rights` — sc. 15; the keys adjacent
  to the epoch (`platform/epoch/<y>`, two segments after `epoch/`, `<x>/epoch` without `/`) are outside `never` for admin — sc. 14.

### Original passage 6

In scenario 08 the name X-Configstore-Role is a designation of the header of trusted role forwarding.

### Original passage 7

do not change the value console and the socket role. This is not a normative header name. Without

### Original passage 8

- Sc. 11 — `never` (N1.3): for the console a 403 is indistinguishable from a refusal by rights, so the distinguishing role is admin: its rights are

### Original passage 9

- Sc. 12 — the role forwarding header at `GET /v1/list` (N3 «check», R38-06): the header name is a designation, as in sc. 08.
- Sc. 13 — the rights file (N1.2, N4) by the directive `@rights store` (common README): without a file — `GET /v1/rights` 404; three inputs
  `inputs/rights-bad-field.json` (an unknown role field), `rights-internal-role.json` (the role `configstore`),
  `rights-bad-name.json` (the name `Console`) — a start refusal, code 2; the last step brings back the stand file.

### Original passage 10

- Sc. 14 — the edges of `never` (N1.3). Steps 1–6 for admin (rights «everything except `never`»): `platform/epoch/c1` (`x = platform`),
  `testsub/epoch/a/b` (two segments after `epoch/`) and `testsub/epoch` (no `/` after `epoch`) are not epoch rows, their
  deletion — 200; an implementation whose `never` is wider than the norm refuses here. Steps 7–13 — the rights file
  `inputs/rights-domain-roles.json`: the domain roles `domain`, `domainagent` and `<sub>domain` (`testsubdomain`, its own family
  `domain/testsub/`) delete under `domain/` — 200 (C01-NEVER-DOMAIN-ROLE-01); the same prohibition for admin — sc. 11 step 6.
- Sc. 15 — `comment` of the rights file (N1.2): a number instead of a string (`inputs/rights-bad-comment.json`) — a start refusal, code 2;
  the stand file again — `GET /v1/rights` by admin returns its string `comment` (N2).

### Original passage 11

Sc. 16 — the batch `op: batch` by roles (P/01.1 N1 `batch`, ADR-0094 B9): step 1 — the role `console` does not know the limit `BATCH_WRITES`, step 3 — the other
roles know it; steps 4–7 — a row and a guard without the right, nothing is written; steps 8–11 — `never` for admin judges each row of the batch.
