# Acceptance P/09.1 — the agent of a member (stand)

This English text is the source; the Russian translation `ru/acceptance/1/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The stand, the dictionary of directives and doors — [the common acceptance README](../../../common/acceptance/README.md#dictionary-of-directives-and-doors),
the section [«Domain stand»](../../../common/acceptance/domain-stand.md#domain-stand) (the stand of several clusters). The norm of the chapter is [`09.1-agent.norms.md`](../../spec/09.1-agent.norms.md) N5;
[the contract](../../spec/09-agent.api.openapi.yaml), the lecture (`ru/09-agent.md`, for people, not in the export). In total 22 scenarios / 252 steps.

The agent side in the scenarios of other chapters — the list «Neighbours on the stand» of the norm of the chapter, N5.

## Stand

**Preparation of each scenario**: the runner brings up on one machine three clusters — `hold`, `m1`, `m2`; each has
its own empty store, its own `{data}`, its own role sockets and ports of the console and the resource, its own ring (P/06.2 N1.2), the manifest catalogue
— only `testsub`; the console, the controller and the worker `w-1` of `testsub`, the resource of its own server (`srv-hold`, `srv-m1`, `srv-m2`).
There are no units. There is no domain: it is set up by the directive `@domain` of the first step of each scenario. The domain name is `acme`.

- `store` at `member <cluster>` is the store door of the cluster through `admin.sock` (the preparation and the observation of the domain rows at a member:
  `domain/agent`, `domain/member-key`, `domain/member-list/<part>`, `domain/keys`, `domain/member-topology`, `domain/grants`,
  `domain/backup-taken`, `domain/shared`, `domain/shared-refused`, `domain/root`, `domain/placed`, `domain/outcomes`,
  `domain/agent-turn`); `store` without `member` is the store of `hold`.
- `resource` without a prefix is the resource door of `hold`: through it the holder's objects `domain/members/<member>/…` are read.
- Do not speed up the clocks: `LOST_AFTER` 45 s, `REPORT_EVERY`, `MARK_REFRESH` 22.5 s, `VIEW_EVERY` 3 s; the `@until` terms are taken with
  a margin.
- The runner goes as the human `root` (the first administrator — chapter 8.4).

Common notes for selected scenarios:

- The doors `holder`, `member`, `resource`, `store`, `token` and the directives `@domain`, `@start`/`@stop agent`, `@cut`, `@mend`, `@clock`, `@join`, `@on` (`@freeze`, `@thaw`, `@put object`) — the dictionary of the «Domain stand» and the common dictionary of directives; the freeze limit is 120 s.
- At the door `holder` the runner sets `Idempotency-Key` also for `PUT`/`DELETE`. `$id` is the id of the stored edit from the answer 202. The holder stores an edit (chapter 8.6), the agent applies it (N1.5); the condition `If-Match` of the units door — the norms of [P/06.1](../../../06-console/spec/06.1-console.norms.md).
- Some scenarios use the catalogue `testsub` with a declaration of the shared document:
  - `domain.shared: [step, marks, {rounds}]`;
  - `step` — `int` with `inherit: 1`;
  - `marks` — `list` with `inherit: []`, `merge: union`.

The rows bypassing the writer are put by the store door of the member through `admin.sock`.

## scenarios.tsv

The format of the table is the dictionary of the «Stand» of the common acceptance README and the section «Domain stand»; the expectation is a subset of the fields, `~` — a substring,
`@time` — a time in a string (P/01.1 N0), `@not(…)` — not equal; in total 22 scenarios / 252 steps.

## Evidence outside the TSV

Checked by reading (the norm of the chapter, N5 «By reading»): the agent does not send a new generation by time, an unreadable edits row
of the holder at itself, the alarm page and the urgent report (the stand does not raise alarms), the agent in the process (the stand has no process without
a kit), the field `sign_failures` of the publication and the count `sign_failures_console` (an edit has no way to be delivered to an agent without a key: it does not ask
for the holder's answer, and an edit received before the key was spoiled is a race of one pass), `no_seal` and `domain.reports`, key changes at a member without a connection, the book secrets at
a member, the refusals of the keeper's agent by the sum and by `record` (the holder does not send such a document), a break of the road of the local token door,
an answer from the relay memory and `as_of` of the grants copy (on the stand `as_of` is visible only as a store row, and its freshening is
no more often than `AS_OF_STORE_EVERY`), the agent body limit; the HTTPS client and the first contact (the stand without TLS). The bytes of the agent signature
— the package `agent-sig`, the function `peer` — the package
`peer`, the function `follow` — the package [`follow`](../../vectors/follow/README.md).

## Kit assistance seams

CALL seams provides 44 CALL steps over ordinary implementation paths. The fixture/port contract is [forms/README.md](../../forms/README.md); [stages.tsv](../../forms/stages.tsv) selects them. They assist the kit and do not replace the ordinary process scenarios or their required neighbours.

## Anywhere copy hash

The five fixture vectors in Vector cases specify the complete-body
digest of P/08.4 N1.3 carry and the check before the copy of N1.4 member_anywhere. The input column names a JSON file
next to the table; expect is a JSON subset of the observations, not an input to the implementation.

Each input has an initial stored copy with its exact index and last confirmed taken_sha256 marker, and a list of attempts.
Every attempt starts independently from that initial state: its trusted carry advertisement is advertised, its real
200 body from `GET /api/anywhere/{member}` is the UTF-8 text body. The fixture calls the ordinary agent copy code with
the body and mark, and records the store operations and marker changes. received_at is the receipt time and domain_age is the answer age; each case prepares a valid trusted carry for server m1 and its active agent guard. It reports arrays in attempt order:
computed_sha256, copy_writes, marker_confirmed; for a refusal also related_edits (the writes belonging to this copy),
copy_items, copy_index and taken_sha256. The digest observation comes from the normal code path that judges the body;
it is not computed by the fixture instead of that path. Positive vectors must reach the actual copy write.

The existing agent-carry IO seam can carry these inputs: these files do not declare a new native command. A fixture
that only calculates the expected digest does not check the negative cases: they require the former copy, exact index
and marker to stay unchanged and zero copy writes and related edits.

The owner wire body contains raw KV strings doc and as_of. Only the outer JSON is canonicalized for the digest; the internal doc text is not normalized first. The trusted advertised as_of, received_at and domain_age retain their existing numeric types. The refusal cases preserve the complete initial raw copy, index and the current-wire marker. No case reports actual IO success before its adapter is run.
