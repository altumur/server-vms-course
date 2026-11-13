# P/10 — instructions for an implementation

This English text is the source; the Russian translation `ru/spec/10-domain-console.README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

This file is for the agent (or the human) who writes code by the lesson. The explanation of «why» is `ru/10-domain-console.md` (for people, not in the export).

Acceptance scenarios, fixtures and reference results are not supplied to the implementation model. Scenario names and «sc. NN» in N5 and the readiness checklist name the judge's case data; the visible norms and forms contain the implementation obligations.

## Task

Implement the process `domainconsole` on the holder's box in the language `<LANG>`; pass the acceptance of N5 and close the readiness
checklist. There are 17 norms in all: P/10-01…17; The process `domain` is
lesson [P/08](../../08-domain/spec/08-domain.README.md), the agent is lesson [P/09](../../09-agent/spec/09-agent.README.md), the forwarding
of the cluster console is chapter P/06.7.

- The read doors `GET /domain`, `/domain/<sub>/<rows>`, `/domain/<sub>/tables/<table>`, `/domain/shadow`, `/domain/members`, `/domain/topology`,
  `/domain/placement*`, `/domain/grants`, `/domain/shared`, `/domain/alarms`.
- Passing the edits, the people doors and the login on to the process `domain`.
- The role door of TLS and «accept by a console»; the gate by `domain/grants/domain`.
- The holder's page and `door.pass` on the domain.

## Inputs and their priority

- The canon is the [norms](10-domain-console.norms.md), including N0, the paragraph «Data», the order of N3 and the refusals of N4. The input and the output of the
  acceptance command are N5.
- The [HTTP contract](10-domain-console.api.openapi.yaml) expresses the forms of its own doors and the codes of transition 2; the answers of the process
  `domain` are the [OpenAPI of lesson P/08](../../08-domain/spec/08-domain.api.openapi.yaml) (by reference).
- Contracts: [forwarding](../../common/contracts/forwarding.md), [gate and pass](../../common/contracts/gate-and-pass.md),
  [domain token](../../common/contracts/domain-token.md), [right](../../common/contracts/may.md), [role
  certificate](../../common/contracts/role-certificate.md), [`peer`](../../common/contracts/peer.md), [event
  journal](../../common/contracts/event-journal.md).
- [Acceptance](../acceptance/README.md) — the stand of several clusters ([the common README of
  acceptance](../../common/acceptance/domain-stand.md#domain-stand), the section «Domain stand») and the vector
  [`alarms`](../vectors/alarms/README.md). Flags, environment, exit codes — [`../lifecycle.md`](../lifecycle.md).
- The lecture (`ru/10-domain-console.md`, for people, not in the export) explains the reasons.

Internal interfaces, types and structure are the implementation's choice. The name and the call template of the command `alarms` are the item of «Implementation
decides» of the norms.

**On a divergence.** Name the norm id, the input, the initial state, the expected and the obtained outcome. An implementation defect is
an output that does not match the expectation on an acceptance input. An acceptance defect is an expectation that diverges from the norm. A norm gap is an input
for which the norm gives no unambiguous outcome: record the place and a counterexample and hand it to «Specification» with a proposal.
The instructions introduce no new refusal. The source owner records acceptance changes in the lesson change record.

## Glossary

These names disambiguate existing rules; the glossary adds no behaviour.

| Word | Meaning here | Norm |
|---|---|---|
| process / role / kit | `domainconsole` is the executable process; the same role name selects its TLS kit. | P/10-R003; N1.1, N1.4 |
| holder / member | The holder cluster runs the domain console; it is also a member with its own agent and report. | P/10-R003, P/10-R036; N1 |
| forward / pass | The cluster console forwards to this console; this console passes edits to `domain` or `door.pass` to the domain worker. | P/10-R005, P/10-R007, P/10-R009 |
| row / part / page | A row is read from the store; a part groups stored records; an HTTP page obeys the member budget and can end inside a part. | P/10-R004; N1.2a, N1.2b |
| version / revision / index | The store row index is the exact string used for ETag; document `rev` or `revision` is a separate field. | N1.2; P/10-17 |
| view / grant view / visibility | `domain/view` is the stored aggregate; `view` is a grant action; visibility filters the returned records. | P/10-R004, P/10-R008; N1.2, N1.5 |
| reported / report / alarm page | The confirmed mark identifies a report generation; that report can have no alarm page or have an unreadable page. | P/10-R011, P/10-R014; N1.8, N3 |
| witness / clock / silent | The originating report offsets the witness clock; `silent_after` is per member; `silent` and `not_reporting` keep the last known alarms. | P/10-R011, P/10-R014; N1.8, N3 |
| token / ticket / callback | The person token proves identity; second-kind pass uses a request-bound ticket; this console has no ticket callback door. | P/10-R008, P/10-R009; N1.5, N1.6 |
| refusal / unreadable / unconfirmed | A refusal is the published outcome; a malformed confirmed report mark differs from a store read that was not confirmed. | P/10-R014, P/10-R015; N3, N4 |

## What to create

- The read doors of N1.2 and the alarm list of N1.8 with the function `alarms` (the command `alarms`).
- The passing of N1.3: each row of the list of domain doors, except its own reads and `door.pass`, — to the process `domain`
  (`SIGNER_URL`), the answer as it came; the people doors of N1.3a.
- The role door of N1.4 (`server.role`) and «accept by a console»; the gate of N1.5 (the steps of `identity` 3, 4; `may` by
  `domain/grants/domain`; `/session` with the grants).
- `door.pass` on the domain of N1.6; the holder's page of N1.7.
- The start of N1.1: the reader's side of the manifest row, the schema check, readiness — the port.

## Order of work

This is a suggested order, not a mandatory structure of the code.

1. `alarms` by the vector [`alarms`](../vectors/alarms/README.md).
2. The read doors of N2 and their refusals of N4.
3. The gate of the domain console; `/session` with the grants.
4. The passing to the process; «accept by a console»; the role door.
5. The holder's page and `door.pass` on the domain.
6. The stand: scenarios 02, 05–19 of the [acceptance of the lesson](../acceptance/README.md) and the domain console side in the scenarios of the chapters of lesson P/08
   (the table of neighbours on the stand of N5).

The machine-readable plan of this order is [forms/stages.tsv](../forms/stages.tsv), with the CALL ports in [forms/README.md](../forms/README.md); its kit seams supplement the scenarios of step 6 and the reading, they do not replace them.

## Pitfalls of the language and the library

| Norm | Possible mistake | How to keep the behaviour |
|---|---|---|
| N1.8 | Throw away the alarms of a silent member | The alarms of the last report stay, plus the silence row. |
| N1.3 | Recompute `deposed`, `frozen`, `standby` of the process | The answer of the process is as it came (P/08.0 N1.8 `answers`). |
| N1.2c | Serve the topology from the view | From the row `domain/topology`: the new `rev` right after a PUT. |
| N1.4 | Resume TLS sessions at the role door | Tickets and PSK are turned off: each connection is a full handshake by the current union. |
| N1.4 | Pass on an arrived `X-W2C-Client` | One that arrived from outside is stripped, like `X-User`; the console sets it itself. |

## Boundary checks

The domain console writes no rows of the holder: it passes the edits on to the process `domain` (N1.3; the rights of `domainconsole` are reading
`domain/*`). The alarm history is written by the process `domain` (chapter 8.9); the list only reads it. The execution of edits and the check
of the identity at the process are lesson P/08; the forwarding of the cluster console is chapter P/06.7.

## Done when

- The scenarios of the acceptance of the lesson selected for completion pass; the vector `alarms` passes.
- The description of the implementation names the command `alarms`.
- The normative checklist P/10-01…17 is closed; the items «checked by reading» (P/10-03, -10, -11, -15, -16 and parts of the others by N5)
  are named separately.

A TSV success confirms only the branches it observes: it does not prove TLS between clusters, `door.pass` on the domain and the deadline of the passing.
