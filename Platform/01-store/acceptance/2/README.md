# Acceptance P/01.2 — rights through the store door

This English text is the source; the Russian translation `ru/acceptance/2/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md). The norm of the chapter is
[`01.2-store.norms.md`](../../spec/01.2-store.norms.md) N5, the full bodies of the two routes are in
[OpenAPI](../../spec/01-store.api.openapi.yaml).
The file has 11 scenarios / 67 steps (mutation check 7cecaf2 № 28, 31: `never` for admin, `/v1/rights` only for admin; sc. 11–13 — the coverage audit of P/01 2026-10-30: `never` of the floor and of `domain/`, a role header on listing, the rights file — `@rights store`; sc. 14–15 — its second pass: the bounds of `never`, the domain roles, `comment`); the rights
file of the stand is a ready input [`inputs/rights.json`](inputs/rights.json) (the form of P/01.2 N1.2): the roles `console`,
`testsubcontroller`, `testsubworker`, `testsub2worker` and the patterns the steps need — a subset of the rights output of P/02.5 N1.4 for
`testsub` and `testsub2` (`Platform/common/data/testsub/testsub*.subsystem.yaml`) with the deployment name `testsub`. The runner puts it
into `{rights}` before the store starts; the chapter needs no rights generator: the chapter checks the evaluator, not the output. The scenarios were moved from the acceptance of M10/06
(stage B) with the former numbers, steps and texts; the scenarios of the rights output from a manifest are in [the acceptance of P/02.5](../../../02-installer/acceptance/5/README.md).

## Profile interface

Use the same `01-store` [profile format](../../../common/acceptance/PROFILE.md). `stand.store` starts the store with the prepared `{rights}` file and the administrative and per-role sockets assigned by the common stand. `keys.role_header` names the role-forwarding header used by the chapter's header probes. This chapter consumes the ready rights fixture below; it requires no rights-generation command from `02-installer`. The store's own command and flags must expose these existing interfaces rather than a fixed prestarted door.

## scenarios.tsv

The format is the dictionary of directives and doors of the common acceptance README: a door without a prefix is the store, `@as <role>`, `@header` before
the method, `$name`, `ASSERT`; the expectation is a subset of fields, `index` may be omitted. Specific to the chapter:

- `expect` without a body for code `403` is the full form `{kind: forbidden, error: …}`. For a refusal of an operation on a row, error names the role, the action and the key. For an identity refusal in scenario 08 — the socket role `testsubworker` and the reason why the role header is prohibited (naming the route is admissible); the key of the row is not required, and the imposed role console does not replace the socket role.

An absent expectation body for 200 does not mean an empty answer. Its form is checked by the input
contract of chapter 1.1; 403 is exactly the string fields kind/error without console fields. `$name` is bound only
after the whole step matches; a repeated variable is compared with the earlier value. The order
of keys in list stays the order of the store; the runner does not sort the actual answer.

Sc. 16 — the batch `op: batch` by roles (P/01.1 N1 `batch`, ADR-0094 B9): step 1 — the role `console` does not know the limit `BATCH_WRITES`, step 3 — the other
roles know it; steps 4–7 — a row and a guard without the right, nothing is written; steps 8–11 — `never` for admin judges each row of the batch.

The roles of the scenarios: `console`, `testsubcontroller`, `testsubworker`, `testsub2worker`, `admin`; in sc. 14 after `@rights store
inputs/rights-domain-roles.json` — the domain roles `domain`, `domainagent`, `testsubdomain`.

Reconciliation of python and go M10/6–11 (R12): sc. 05 steps 8–10 — `never` and an empty `<y>`; sc. 08 step 2 — the role header before the body.

## Isolation

Each scenario, a repeated run included, gets a separate instance with empty
application rows and an empty replay memory of id. Cleaning prefixes does not replace cleaning this
memory. The runner variables are reset, the role is set by the first `@as`; the rights file is the same
in all scenarios. Parallel runs do not share an instance.

Background consoles, controllers, workers and the resource do not write into these rows. The permission data
is prepared by the runner with the file `inputs/rights.json` and the instance setup, and each step is performed only by
the named role.

## Checks outside the scenario file

- Compare the whole JSON of `/v1/rights` with the loaded file under admin; for another role — 403, without
  a loaded file — 404. Check the role grammar, the absence of internal roles,
  the mandatory arrays, unknown fields, delete absent / [] / a separate list.
  comment is absent or is a string and is returned as loaded; a number/null/object
  instead of comment is a refusal. A change of only comment does not change the effective rights; --check
  compares by meaning (P/02.5 N3 «install»): comment and the order of patterns are not compared. Also check the installed rights file of the implementation.
- Check a denial before and after a permission, an exact key and a prefix, an asterisk in
  the middle, an unknown role, never for admin and for an ordinary role, the separate read right of the guard.
  list has no read check; trust in the identity stays mandatory.
  For admin and ordinary roles check write/delete platform/epoch_floor separately;
  an adjacent ordinary key must not fall into never. A trusted forwarding of admin without a file
  is allowed outside never; with a loaded file it is refused. An untrusted forwarding is forbidden
  in both modes, list included. These are separate probes; the TSV does not perform them.
- Now by scenarios: a non-string `comment` is a start refusal, a string one is returned by `GET /v1/rights` — sc. 15; the keys adjacent
  to the epoch (`platform/epoch/<y>`, two segments after `epoch/`, `<x>/epoch` without `/`) are outside `never` for admin — sc. 14.

These are subjects of a separate reading/structural test, not additional performed
scenarios. Socket modes, forwarding and the certificate require the corresponding stand.

In scenario 08 the name X-Configstore-Role is a designation of the header of trusted role forwarding.
Before the run substitute the name from the implementation description (N3/«Implementation decides», item 3);
do not change the value console and the socket role. This is not a normative header name. Without
such a setting the preparation of the run is not complete. Count the forbidden identity spoofing,
not the subsequent refusal of the key write.

## Coverage audit of P/01 (sc. 11–13)

The session audit-kimi (2026-10-30, commit 399e4783b, `coverage audit P01 (for people)`): properties that were formerly checked by reading.
- Sc. 11 — `never` (N1.3): for the console a 403 is indistinguishable from a refusal by rights, so the distinguishing role is admin: its rights are
  «everything except never», and without `never` these writes would pass. Reading the floor by admin — 200: the refusal concerns the action.
- Sc. 12 — the role forwarding header at `GET /v1/list` (N3 «check», R38-06): the header name is a designation, as in sc. 08.
- Sc. 13 — the rights file (N1.2, N4) by the directive `@rights store` (common README): without a file — `GET /v1/rights` 404; three inputs
  `inputs/rights-bad-field.json` (an unknown role field), `rights-internal-role.json` (the role `configstore`),
  `rights-bad-name.json` (the name `Console`) — a start refusal, code 2; the last step brings back the stand file.
- Not accepted: rows of the vector `rights-evaluator` for a role outside the file (A09): the store does not open a socket of a role that is not in the file,
  and the door does not see the evaluator's refusal; it stays by reading (P/01.2-04).

## Coverage audit of P/01, second pass (sc. 14–15)

The coverage audit session, second pass (Gemini, 2026-10-30, commit 6a5817f88, `coverage audit Gemini P01 (for people)`, G04):
- Sc. 14 — the edges of `never` (N1.3). Steps 1–6 for admin (rights «everything except `never`»): `platform/epoch/c1` (`x = platform`),
  `testsub/epoch/a/b` (two segments after `epoch/`) and `testsub/epoch` (no `/` after `epoch`) are not epoch rows, their
  deletion — 200; an implementation whose `never` is wider than the norm refuses here. Steps 7–13 — the rights file
  `inputs/rights-domain-roles.json`: the domain roles `domain`, `domainagent` and `<sub>domain` (`testsubdomain`, its own family
  `domain/testsub/`) delete under `domain/` — 200 (C01-NEVER-DOMAIN-ROLE-01); the same prohibition for admin — sc. 11 step 6.
- Sc. 15 — `comment` of the rights file (N1.2): a number instead of a string (`inputs/rights-bad-comment.json`) — a start refusal, code 2;
  the stand file again — `GET /v1/rights` by admin returns its string `comment` (N2).
