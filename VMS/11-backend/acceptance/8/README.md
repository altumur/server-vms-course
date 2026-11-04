# Acceptance V/11.8 — translation of rights

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`11.8-backend.norms.md`](../../../spec/11.8-backend.norms.md) Н5, the boundary of the suite is [V/11.6](../../../spec/11.6-backend.norms.md) Н5. The stand and the vocabulary are the [common README
of VMS acceptance](../../../../common/acceptance/README.md) on top of the common platform README (export `7a875c75`, the VMS pin).

The basis of the `backend` acceptance is the consolem API tests in the profile ([`data/profile-tests.tsv`](../../../data/profile-tests.tsv)). Here is only what they do not see (ADR-0094 addenda (17), (18)):
the column «What the test does not see» is mandatory, the analysis of the tests is the listing of gaps by «Консоль» at `ef7175b`. The first run is with the first generation of V/11; until then the scenarios are the text of the norm.

## Preparation

The VMS domain stand (the common README of VMS acceptance, «Стенд домена VMS»): `@domain m1`, on `m1` the manifests `VMS/01-cam/cam.subsystem.yaml`, `VMS/02-rec/rec.subsystem.yaml`,
`VMS/04-det/det.subsystem.yaml`, `VMS/11-backend/backend.subsystem.yaml` are installed, with the controllers of all four. The console is `CONSOLE_ROOT=cam` (`member m1 console`), `backend` is mounted:
`member m1 console2` — the prefix `/backend`, so the contract API is `member m1 console2 … /api/…`. The worker `b-srv-a-1` is started by the scenario; there are no holders of `cam`, `rec`, `det` on the stand: the scenarios
need rows, not cameras. Without TLS kits: the callback is by the role socket on the loopback (ADR-0094 addendum (6) item 4). The subsystem file of `backend` is not set: the suites do not need `/test/*`.
The current person after `@domain` is `root`, the password `w2c test root password`; `@person -` — without a token. Each scenario runs on a clean instance.

The ids of the records are derived by V/11.4 Н1.6, so the scenarios write them as values; the cluster in the names is `m1`, the first 12 bits of `device:` are the section of `m1`, `ca0`; the domain is `$dom`: the `root` of the stand is random, the id is taken from `GET /api/domains`; the cameras `1`, `2`, `3` are `ca08e8ba-11ab-5128-97e6-d03888680c2e`, `ca07be2d-dfe2-5601-b0b3-f4eba44b12f8`, `ca0ca265-e670-5862-92f2-bfae90f7da31`, the person `root` is `6ad9a883-cad5-5ab8-802f-0889506a2358`, the role `admin` is `cd290440-e663-50ed-bef1-7b3cdbab3c03`.

The draft of `POST /api/access/apply` is given whole in the step row: the runner has no edit of the snapshot of its own. The values of `global` are those the snapshot reads by Н1.4. New roles, groups and people are named by the scenarios with client
ids; people with a password are created by `holder POST /domain/users`, their ids are v5 (Н1.2). The arrays of grant lines are compared with the order: it is canonical (P/08.4 `doc.lines`); the line `root admin *` is written by `@start domain`. Waiting for `grants` in `GET /session` — the copy of the grant has reached `m1`, as in V/03.

| Scenario | Norm | What the consolem test does not see | What it observes |
|---|---|---|---|
| `01-read` | V/11.8-01, V/11.8-05, V/11.8-07 | the 428, 412 test is out of the profile: it reads `catalogs[0]`; the reader always has the right | 428, 412; a second identical `apply` — 412 with `current`; a history row with the author; without `admin` on `*` in any cluster — 403 as a whole |
| `02-not-supported` | V/11.8-02, V/11.8-06 | there is no `NOT_SUPPORTED` in `api-access.js` | the listing of Н1.6, `unr: false` for `admin` (ADR-0094 addendum (18) item 4), the fields `enabled`, `login`, `id`, a new key `folderAccess` — `VALIDATION_FAILED`, the snapshot version has not moved |
| `03-pair` | V/11.8-06 | the test judges only the reference | `MON` and `ONLY_ARCHIVE`: two folders, two roles of a person, through a group, two points `unit:` — no refusal, `reference.access.joins` |
| `03-pair-saved` | V/11.8-06 | the test does not save the pair bypassing `backend` | a pair created bypassing `backend` does not reject an edit of another role |
| `04-levels` | V/11.8-03, V/11.8-04, V/11.8-05 | the role is only renamed, the levels do not change | grant lines by Н1.3 line for line, the copy of the root, the functions; the snapshot back — the difference is empty: there are no writes, the version and the lines are the same |
| `05-manager` | V/11.8-05, Н1.9 | there is no manager, no refusal by right, no passwords as a condition | an ordinary person 403; a manager: `403 admin only` on a person and a group with `admin`, another edit 200; the alarm `domain.rights_via_backend`; `password set by a non-admin` — 409, after the administrator's password 200 |
| `06-lockout` | V/11.8-08 | the test is out of the profile (ADR-0094 addendum (18) item 4) and knows three cases | `SELF_LOCKOUT`: no administrators, remove from oneself, through a group, disable, delete, `expiresDate`, the assignment deadline, `dryRun`; `BUILTIN` |
| `07-limits` | V/11.8-09 | there are no limits, the server always answers | a difference larger than a package — «сохраните частями» ("save in parts"), the version is the same; `too many admins` — 422; the domain is silent — 503 `UPSTREAM_UNAVAILABLE` |
| `08-clusters` | V/11.8-10, V/11.8-11, V/11.8-14 | the console server has one cluster | the role's rights are `lines`, the lines arrive by a pass, there are no `система` records; an edit of a cluster grant — `local` and a `система` record, an edit of the role removes it; a new member and `refused` — `@manual` |
| `09-cluster-admin` | V/11.8-10 | there is one administrator per system | the cluster `admin` reads the snapshot, sees the record about the folder tree, does not create a folder; a draft with a role edit and a comment — 403, rights only — 200, `local` on his cluster; a grant only in another cluster: login through `m1`, there is no own one, there is a snapshot |
| `11-changes` | V/11.8-13 | the test judges listings in pages, it is out of the profile: it needs the users of the set | a snapshot without people, `users`, `groups`, `history`, the objects of a role in pages; no `version` — 422; an old one — 412; an edit of one record does not touch the others |
| `10-password` | V/11.8-05, V/11.8-12 | the test expects the policy of the set and `passwordByAdmin` | `PASSWORD_POLICY`, the password of a new person logs in, stream accounts without a gateway — 503 `UPSTREAM_UNAVAILABLE` |

No sleep is needed: the wait is `@until` by an observable sign.

**By reading** (the state cannot be assembled on the stand): the email for a reader without the right — the norm does not set the order of `users`; `409 last admin` of the package — the check of Н1.8 answers earlier; `standby`, `frozen`, `deposed`, `names unknown` go in one line of Н4 with the step `07-limits`, `admin table too large`, `roles table too large` — there is nothing to assemble them with.

Twelve independent scenarios in all, 241 steps.
