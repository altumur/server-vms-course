# The store schema contract: `platform/schema`, `SCHEMA`, the check at start

This English text is the source; the Russian translation `ru/contracts/schema.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13): the schema check at start is executed by all processes
of the platform — a contract, not copies in chapters; layout audit A-02, the Architect's decision of 2026-10-25). The owner is chapter
[P/06.6](../../06-console/spec/06.6-console.norms.md) (N1.1a «Schema», N3 «raise_schema»). Participants: the console (P/06.6),
the controller ([P/04](../../04-controller/spec/04-controller.norms.md) N3 «controller start — schema check»), the worker
([P/03.2](../../03-worker/spec/03.2-worker.norms.md) N3 «schema check by the worker»), the resource
([P/05](../../05-resource/spec/05-resource.norms.md) N3 «resource start — schema check»), the domain processes — `domain`,
the agent, the domain console ([P/02.4 N1.12](../../02-installer/spec/02.4-installer.norms.md); the domain console —
[P/10](../../10-domain-console/spec/10-domain-console.norms.md) N1.1); step 0 of a process start is [P/02.3](../../02-installer/spec/02.3-installer.norms.md)
N3 «Process start».

Moved from P/06.6 N1.1a (the lines `platform/schema`, `SCHEMA`, `BUILD`, `heartbeat`, `check`) and the common block «start
of the controller, the worker, the resource or the console — schema check» (P/06.6, P/03.2, P/04, P/05 N3; formerly М10/10 N3) without
a change of behaviour; they refer here. The raise of the schema by the operator (`raise`, `PUT /schema`, the maintenance window) is with the
owner, P/06.6 N1.1a, N3 «raise_schema».

Normative keywords follow [the course canon](../../../НОРМАТИВНЫЕ-СЛОВА.md).

## Form

The row `platform/schema` is the family `schema`: the form `Platform/06-console/data/schema.schema.json`, the outcomes
`Platform/06-console/data/schema.outcomes.tsv` ([form](../../06-console/data/schema.schema.json),
[outcomes](../../06-console/data/schema.outcomes.tsv)). The field `schema` of a heartbeat is the heartbeat forms
`Platform/03-worker/data/heartbeats.schema.json` (outcomes — `Platform/03-worker/data/heartbeats.outcomes.tsv`) and `Platform/05-resource/data/resource-heartbeat.schema.json` (outcomes — `Platform/05-resource/data/resource-heartbeat.outcomes.tsv`) (and their
`.outcomes.tsv`).

## Schema

```yaml
platform/schema:  {version: <integer ≥ 1>, at: <moment>, revision?: <integer ≥ 1>}     # revision — P/06.6 N2.1 «Row version», only the console reads it; the writer is the console (admin); no row = the schema of the build (a fresh installation)
version:  an exact integer ≥ 1 without an upper bound and without machine overflow (as a slot number, the slot name contract): greater than
          SCHEMA of the build — «schema is newer» (too new: a start refusal, code 2, the exact N in the journal); out of form — only not an integer, < 1
          (C06-SCHEMA-WIDE-32-01, the Architect's decision of 2026-10-25)
SCHEMA:   the number the build understands; adding a field — without a new number; changing the meaning of a field — a new number; for the current
          specification SCHEMA = 1 and schema of the heartbeat = 1; raising SCHEMA — only by a decision with a transition (the stage C guess W03-E02, the Architect's decision of 2026-10-23)
BUILD:    the build word for a human (env BUILD, default dev); the machine reads SCHEMA
heartbeat: every heartbeat of the worker and the resource carries schema and build (P/03.4 N1.1, P/05 N1.4); schema — a JSON integer without a fraction
          part and exponent (the form int of [the row check contract](../row-check.md) «Preparation of fields»: «An `int` value at the input of the door»), ≥ 1; `1.0`, `1e0`, `-1`, a string, null — the schema of the process is unknown (null
          in `processes`, P/06.6 N2.3) (reconciliation of python and go М10/6–11, T3); build — a string; not a string — `null` (not known; reconciliation of python and go М10/6–11, T27; V7 item 3, the Architect's decision of 2026-10-28, P1; row 14 of the list)
check:    at the start of the controller, the worker, the resource and the console: version > SCHEMA → do not start; the row is not a number → do not start;
          the domain processes start the same way — domain, the agent, the domain console (P/02.4 N1.12); the worker also checks on the renewal
          of the slot (P/03.2 N3 «schema check by the worker»)
```

## Check at start

```
as the first step of the start, before reading the manifest (P/02.3), at all four processes:
read platform/schema: absent → own SCHEMA; not a number → do not start; version > SCHEMA → do not start
                                                                 («store is at schema N; this build understands M»)
  a read error → wait for availability without starting work; do not start — exit with code 2 and a log line
worker: after the renewal of the slot — P/03.2 N3 «schema check by the worker»
```

**Boundary.** The daemon of the row store does not interpret the layout of a subsystem and is not blocked by this check: otherwise the store could not be opened for reading/repairing the schema; its own format is P/01.1 and P/01.3 N1.3 (the daemon `configstore`: `member.json`, `backup`/`restore`). The check on renewal exists at the worker; it does not prove the safety of all other processes. Their race with the start is excluded by the maintenance window of P/06.6 N3 «raise_schema». A read failure — wait for availability without work; a reliably damaged/too new schema — a start refusal with code 2.

## Vectors

The package [`schema`](../vectors/schema/README.md): the function `check` — the row `platform/schema` and SCHEMA of the build → a start with the version,
«schema is newer» with the exact N, or «out of form» (C06-SCHEMA-WIDE-32-01, the Architect's decision of 2026-10-25). A read error and the slot renewal by the worker — by acceptance scenarios
of the participants (P/06.6; a read error at the resource — sc. 18 of the acceptance of P/05, a start refusal — sc. 17) and by reading.

## Correspondence to former lessons

From P/06.6 N1.1a (`platform/schema`, `SCHEMA`, `BUILD`, `heartbeat`, `check`; the norm P/06.6-04 by `note` of [id-map](../id-map.tsv))
and the common block N3 «start … — schema check» (P/06.6, P/03.2, P/04, P/05; formerly М10/10 N3, М10/10-01); they refer here
(layout audit A-02).
