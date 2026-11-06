# Acceptance V/01.1 — the camera as a unit

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The norm of the chapter is [`01.1-cam.norms.md`](../../spec/01.1-cam.norms.md) N5. The stand and the dictionary of directives and expectations are in the common
[platform acceptance README](../../../../Platform/common/acceptance/README.md#dictionary-of-directives-and-doors) (export
`7a875c75`); the format of `scenarios.tsv` is the same (`scenario`, `step`, `request`, `expect`; an expectation is a subset).
The run — after the first stage C generation that has passed the platform acceptance (ADR-0090 addenda (8), (9)); until then the scenarios are
norm text.

## Preparation

The store and the cluster console of one implementation per the section Stand of the common README; one manifest is installed —
`VMS/01-cam/cam.subsystem.yaml` (P/02.1), the console — `CONSOLE_ROOT=cam`, the doors — `/cameras`, `/devices`, `/children`, `/child_settings`. The key
ring is set (`SECRETS_KEY`, P/06.2 N1.2): `cred_secret` is sealed. The controller, the workers, the resource and the domain are not started.
Requests — from loopback without a domain (P/06.3 N1.3 `open`): one identity with full rights. All scenarios run sequentially on
one instance with empty `cam/` data after the installation; binding `$name` is within a scenario. A repeated and a
parallel run — their own instances. For each creating `POST` the runner issues a fresh `Idempotency-Key`. The scenarios share
data: the address (`source`) of each created camera is its own across the whole acceptance, otherwise the next scenario gets 409 `unique`;
`01-create` is the first on empty data, its cameras are numbers 1 and 2 (P/06.1 N1.3: the first number is 1).

## Scenarios

| Scenario | Norm | What it observes |
|---|---|---|
| `01-create` | V/01.1-01 | the fields and defaults of N1.1, `name` without a name — `cam<id>` in full (`cam1`, the second creation — `cam2`); an edit of another field does not recompute the name; no password — the field is empty |
| `02-numeric` | V/01.1-01 | `id` in `POST` — a refusal with the field name; `live` outside `enum` — a refusal without `fault` (P/06.1 N4) |
| `03-one-channel` | V/01.1-02 | the same canonical spelling (the case of the scheme) — 409 `unique`; another channel — allowed; without the default port — a different canon (the port is not stripped, the row check contract), the door accepts — whether it is the same channel is decided by the holder (chapter 2 N1.2, `busy`) |
| `04-credentials` | V/01.1-03 | a login and a password in the address (userinfo, `secret_in`, `driverpack://` in the path) — 400 `bad_url` with the field names; in their own fields — accepted, the password is masked |
| `05-bound` | V/01.1-03 | a change of `source` without the password — 400 `bound_to`; with the password — accepted |
| `06-schemes` | V/01.1-03 | a scheme not from `schemes` — 400; `ipint` with `#` in the path — accepted |
| `07-devices` | V/01.1-04 | the operator does not write the table `devices`: `POST` — 403 «written by its worker», `PUT` — 405; `DELETE` of a nonexistent row — 404 (deleting an existing one — 200 with cas, P/06.1 N1.6; on the stand without a device there is no row) |
| `08-streams` | V/01.1-09 | a camera stream: `main` to a camera, `profile` by default `main`, an edit of `main` — 400 `fixed`, `profile` is editable; `resolution`, `fps` are editable on the stream, not per the form — 400; an unknown field — 400 |
| `09-delete-camera` | V/01.1-09 | deleting a camera does not touch the streams: a stream lives with `main` pointing to the deleted camera and is editable; a new stream to it — 201 (`ref` does not require the target); the holder does not hold such a stream (`reason` «main: missing», chapter 2) — by reading; the stream itself is deleted |
| `10-type` | V/01.1-11 | `type` outside `enum` (`thermal`) — a refusal; four kinds are accepted; an edit — 400 `fixed`; a stream on a row that is not `camera` and a stream that is not `camera` on a camera — 409 `must_match`; a `camera` stream on a camera — accepted |
| `11-order` | V/01.1-01, -02 | two errors at once in the order of P/06.1 N3: a creation with a field not per the schema and an address that the camera of scenario 03 already holds — 400 of the form (without `fault`), not 409 `unique`; an edit of a nonexistent camera with a body not per the schema — 400, not 404; the scenario creates no data |
| `12-children` | V/01.1-10 | the operator does not write `children`: `POST` — 403 «written by its worker», `PUT` — 405; a child's setting: the key from `camera`, `type`, `number` is seen by reading the row, `enabled` and `norm` without a default, an edit by `POST` on top — the name survived the edit; without `type`, `type` outside the list, `number` 0 — 400; there is no field `kind`; on the stand without a device there are no children rows — by reading (V/01.4-08); `mic`, `spk` are accepted, `norm` outside the list — 400 |
| `13-fields` | V/01.1-11 | `lat`, `lon`, `azimuth`, `short`, `mac`: accepted, `0` is a value, `null` removes the field, not a number — 400 |
| `14-eventsrc` | V/01.1-13 | the fields of an `eventsrc` row: `camera`, `words`, `overlay_*`, the label `server:*`; `words` without `msg`, `overlay_delay_ms` < 0 — 400 |
| `15-units` | V/01.1-14 | the tables `device_units`, `unit_next`: the key, `enabled` by default, the nesting `parent`, form refusals, removal |

People's rights (`rights.reach`, V/01.1-07) are not observed by this stand: the grants `view`/`edit`/`admin` are the domain stand
(P/06.3, P/08.4); they are checked by reading until the lesson has a domain stand scenario.
