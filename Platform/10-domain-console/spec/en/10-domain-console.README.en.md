# P/10 — instructions for an implementation

This English text is the source; the Russian [`10-domain-console.README.md`](../10-domain-console.README.md) is derived from it by translation and is not edited by hand (ADR-0121).

This file is for the agent (or the human) who writes code by the lesson. The explanation of «why» is [`../10-domain-console.md`](../../10-domain-console.md).

## Task

Implement the process `domainconsole` on the holder's box in the language `<LANG>`; pass the acceptance of Н5 and close the readiness
checklist. There are 17 norms in all: P/10-01…17; the map to former ids is [`id-map.tsv`](../../../common/id-map.tsv). The lesson is assembled from
the lessons М11/1, 3, 4, 6, 8, 9, 11, 12 (the domain console side) (stage B, ADR-0083 addendum (1), (14)). The process `domain` is
lesson [P/08](../../../08-domain/spec/08-domain.README.md), the agent is lesson [P/09](../../../09-agent/spec/09-agent.README.md), the forwarding
of the cluster console is chapter P/06.7.

- The read doors `GET /domain`, `/domain/<sub>/<rows>`, `/domain/<sub>/tables/<таблица>`, `/domain/shadow`, `/domain/members`, `/domain/topology`,
  `/domain/placement*`, `/domain/grants`, `/domain/shared`, `/domain/alarms`.
- Passing the edits, the people doors and the login on to the process `domain`.
- The role door of TLS and «принять консолью»; the gate by `domain/grants/domain`.
- The holder's page and `door.pass` on the domain.

## Inputs and their priority

- The canon is the [norms](../10-domain-console.norms.md), including Н0, the paragraph «Data», the order of Н3 and the refusals of Н4. The input and the output of the
  acceptance command are Н5.
- The [HTTP contract](../10-domain-console.api.openapi.yaml) expresses the forms of its own doors and the codes of transition 2; the answers of the process
  `domain` are the [OpenAPI of lesson P/08](../../../08-domain/spec/08-domain.api.openapi.yaml) (by reference).
- Contracts: [forwarding](../../../common/contracts/forwarding.md), [gate and pass](../../../common/contracts/gate-and-pass.md),
  [domain token](../../../common/contracts/domain-token.md), [right](../../../common/contracts/may.md), [role
  certificate](../../../common/contracts/role-certificate.md), [`peer`](../../../common/contracts/peer.md), [event
  journal](../../../common/contracts/event-journal.md).
- [Acceptance](../../acceptance/README.md) — the stand of several clusters ([the common README of
  acceptance](../../../common/acceptance/README.md#стенд-домена), the section «Domain stand») and the vector
  [`alarms`](../../vectors/alarms/README.md). Flags, environment, exit codes — [`../lifecycle.md`](../../lifecycle.md).
- The [lecture](../../10-domain-console.md) explains the reasons.

Internal interfaces, types and structure are the implementation's choice. The name and the call template of the command `alarms` are the item of «Implementation
decides» of the norms.

**On a divergence.** Name the norm id, the input, the initial state, the expected and the obtained outcome. An implementation defect is
an output that does not match the expectation on an acceptance input. An acceptance defect is an expectation that diverges from the norm. A norm gap is an input
for which the norm gives no unambiguous outcome: record the place and a counterexample and hand it to «Спецификации» with a proposal.
The instructions introduce no new refusal. Record a change of acceptance in `corrections.tsv` of its catalogue.

## What to create

- The read doors of Н1.2 and the alarm list of Н1.8 with the function `alarms` (the command `alarms`).
- The passing of Н1.3: each row of the list of domain doors, except its own reads and `door.pass`, — to the process `domain`
  (`SIGNER_URL`), the answer as it came; the people doors of Н1.3а.
- The role door of Н1.4 (`server.role`) and «принять консолью»; the gate of Н1.5 (the steps of `identity` 3, 4; `may` by
  `domain/grants/domain`; `/session` with the grants).
- `door.pass` on the domain of Н1.6; the holder's page of Н1.7.
- The start of Н1.1: the reader's side of the manifest row, the schema check, readiness — the port.

## Order of work

This is a suggested order, not a mandatory structure of the code.

1. `alarms` by the vector [`alarms`](../../vectors/alarms/README.md).
2. The read doors of Н2 and their refusals of Н4.
3. The gate of the domain console; `/session` with the grants.
4. The passing to the process; «принять консолью»; the role door.
5. The holder's page and `door.pass` on the domain.
6. The stand: scenarios 02, 05–19 of the [acceptance of the lesson](../../acceptance/README.md) and the domain console side in the scenarios of the chapters of lesson P/08
   (the table of neighbours on the stand of Н5).

## Pitfalls of the language and the library

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| Н1.8 | Throw away the alarms of a silent member | The alarms of the last report stay, plus the silence row. |
| Н1.3 | Recompute `deposed`, `frozen`, `standby` of the process | The answer of the process is as it came (P/08.0 Н1.8 `answers`). |
| Н1.2в | Serve the topology from the view | From the row `domain/topology`: the new `rev` right after a PUT (T1). |
| Н1.4 | Resume TLS sessions at the role door | Tickets and PSK are turned off: each connection is a full handshake by the current union. |
| Н1.4 | Pass on an arrived `X-W2C-Client` | One that arrived from outside is stripped, like `X-User`; the console sets it itself. |

## Boundary checks

The domain console writes no rows of the holder: it passes the edits on to the process `domain` (Н1.3; the rights of `domainconsole` are reading
`domain/*`). The alarm history is written by the process `domain` (chapter 8.9); the list only reads it. The execution of edits and the check
of the identity at the process are lesson P/08; the forwarding of the cluster console is chapter P/06.7.

## Done when

- Scenarios 02, 05–19 of the acceptance of the lesson pass; the vector `alarms` — 27 rows, rows 15, 17–23 — code 2.
- The description of the implementation names the command `alarms`.
- The normative checklist P/10-01…17 is closed; the items «checked by reading» (P/10-03, -10, -11, -15, -16 and parts of the others by Н5)
  are named separately.

A TSV success confirms only the branches it observes: it does not prove TLS between clusters, `door.pass` on the domain and the deadline of the passing.
