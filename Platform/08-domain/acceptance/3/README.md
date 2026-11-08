# Acceptance P/08.3 — admission of reports

This English text is the source; the Russian translation `ru/acceptance/3/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The stand and the dictionary of directives and doors are in [the common acceptance README](../../../common/acceptance/README.md), the section [«Domain stand»](../../../common/acceptance/README.md#domain-stand)
(the dictionary of directives and doors of the stand of several clusters; before its move — the «Dictionary of directives and doors M11» of the README
of the acceptance of M11/01). The norm of the chapter is
[`08.3-domain.norms.md`](../../spec/08.3-domain.norms.md) N5. The scenarios were moved (stage B, ADR-0083 addendum (1): without
a change of behaviour) from the acceptances of M11/03 (01, 02, 03, 05, 14), M11/04 (01 → 15, 05 → 16), M11/08 (04) and M11/12 (02 → 17);
the numbers, the names and the steps are the former ones, except `15-topology` (in M11/04 — `01-topology`), `16-second-road` (in M11/04 —
`05-second-road`) and `17-members-only-to-the-lagging` (in M11/12 — `02-members-only-to-the-lagging`): their numbers are taken by
scenarios of M11/03 (the rule — the plan of the move of lesson 8, § 3; the Architect's decision 2026-10-20, item 14). In total 21 scenarios /
218 steps: 14 — sc. 29 `29-batch-admission` (the admission batch, ADR-0113; the roadmap 4.5), 63 from M11/03, 21 from M11/04, 18 from M11/08, 10 from M11/12, 8 — sc. 28, 3 — sc. 18 `18-relay-not-member` (C08-G06),
5 — sc. 19 `19-members-source` (a door of lesson P/10, C10-MEMBERS-SCENARIO-01), 20 — sc. 20–22 (the coverage audit of P/08,
the view fields of chapter 8.1 and a mark beyond the limit of `rev`), 25 — sc. 23–26 (the coverage audit of P/08, the second pass of Gemini), 31 — sc. 27 (ADR-0094 B3, B4).

The command scenarios of M11/03 sc. 10–13 (`agent-sig`, `seal-member`, `seal-member-round`, `accept`) and M11/04 sc. 06 (`accept` with
a road) are not moved: the same cases without a change of bytes are the vectors of the common contracts
[`agent-sig`](../../../common/vectors/agent-sig/README.md), [`domain-envelopes`](../../../common/vectors/domain-envelopes/README.md)
(`m1-open.tsv`, `m1-round.tsv`) and [`accept`](../../../common/vectors/accept/README.md); their inputs are removed together with the steps (the row of
`corrections-3.tsv` (historical correction record)). The other scenarios of M11/03 are the acceptance of [chapter 8.1](../1/README.md) (04, 06–09); M11/04 sc. 02–04 —
[chapter 9.2](../../../09-agent/acceptance/2/README.md), M11/08 — [chapter 6.7](../../../06-console/acceptance/7/README.md) (01–03), [lesson P/10](../../../10-domain-console/acceptance/README.md) (05), the vectors `peer` (06), M11/12 — chapters 8.10 and [9.1](../../../09-agent/acceptance/1/README.md).

## Stand

**Preparation of each scenario** (from the acceptance README of M11/03, «Setup of each scenario 01–09»). The runner brings up on
one machine three clusters — `hold`, `m1`, `m2`: each has its own empty store, its own `{data}`, its own role sockets and
ports of the console and the resource, its own ring (P/06.2 N1.2), the manifest catalogue — only `testsub`; the console, the controller and the worker `w-1`
of `testsub`, the resource of its own server (`srv-hold`, `srv-m1`, `srv-m2`). There are no units. There is no domain: it is set up by the steps of the scenario
(`@install domain`, `@start domain`, `@start agent`) or by the directive `@domain`. The domain name is `acme`; the recovery file of the
installation is `{recovery}` in the instance directory.

- `store` at `member <cluster>` is the store door of the cluster through `admin.sock` (the preparation and the observation of the domain rows).
- `resource` without a prefix is the resource door of `hold`: through it the holder's objects `domain/members/<member>/…` are read.
- Do not speed up the clocks: LOST_AFTER 45 s, REPORT_EVERY 5 s, MARK_REFRESH 22.5 s; the `@until` terms are taken with a margin.

**Scenarios 15, 16** (from the acceptance README of M11/04), **21 and 25**: there are four clusters — `hold`, `m1`, `m2`, `relay`. The agent `relay` always
opens the relay door (`RELAY=1`, `{relay_port}`); the directives `@domain <clusters>`, `@start agent <cluster> via
relay`, `@stop agent`. The topology is empty until the step that writes it.

**Scenario 04** (from the acceptance README of M11/08): the agent `m1` is given the TLS directory `inputs/kit-m1-one/` (only `ca.pem`
of the centre A), then `inputs/kit-m1-two/` (`ca.pem` A and `ca.next.pem` B), then the variable is removed (`@env m1
W2C_TLS_DIR=…`, `@env m1 W2C_TLS_DIR`; the value `inputs/…` is a path from this directory). The doors of the stand do not speak TLS: the agent
only publishes the fingerprints and the certificates of the centres (N1.6 `tls_ca`, `tls_ca_certs`). The fingerprints in the expectations are sha256 of the DER of these
files: A — `d72f9e5e…68a6`, B — `6fefd57b…e217`. Step 4 — the row `domain/members/m1/ca-certs` is written before `Entry.ca` (step
3 already sees the fingerprint), step 18 — the removal by the administrator deleted it. Steps 10–11 check that an edit by the administrator without
a change of the centres at the member is rewritten by its next report. Steps 14–16 — two agent passes (`REPORT_EVERY` 5 s) without
`tls_ca`: the fingerprints are not removed. How the runner passes the environment and restarts the console and the agent of the cluster with the variable
(`@env`) — the dictionary of the «Domain stand» of [the common acceptance README](../../../common/acceptance/README.md), `@env` and
«Forwarding environment» (the review analysis of stage B 8–10, № 22: `M-16`).

## Inputs `inputs/`

| File | Scenario | What is in it |
|---|---|---|
| `other-root.json` | 02 | the recovery file of a foreign root (`root 2` of the vectors [`keys`](../../../common/vectors/keys/README.md); formerly — lesson M11/2 N5) for `@join m2 inputs/other-root.json` |
| `kit-m1-one/ca.pem` | 04 | the centre A (`w2c test ca north`), EC P-256 |
| `kit-m1-two/ca.pem`, `kit-m1-two/ca.next.pem` | 04 | the centres A and B (`w2c test ca south`) |
| `view-member-list-ghost.json` | 19 | the object `domain/view` (the form [`view`](../../data/view.schema.json)): `members` — only `hold`, without `knocking`; a substituted (ghost) view |
| `member-reported-rev-2pow53.json` | 22 | the mark object `domain/members/m1/reported` (the form [`member-reported`](../../data/member-reported.schema.json)), JCS; all fields by the form, except `rev` = 9007199254740992 (2^53, the limit of `pos53` — 2^53 − 1) |

The inputs were moved byte for byte from `inputs/` of the acceptances of M11/03 and M11/08, `view-member-list-ghost.json` is added for sc. 19
(the exception `acceptance-entry inputs`; the description of the exception — the Architect's decision 2026-10-29; the analysis of the plan of the move of lesson 8, § 3 «Exceptions»),
`member-reported-rev-2pow53.json` — for sc. 22 (the coverage audit of P/08; the description of the exception does not name it yet — the edit of
the description is up to the Architect, the skill `lesson-spec`).

## scenarios.tsv

The format is the dictionary of the «Stand» of the common acceptance README and the section «Domain stand». `$fp1`, `$fp2` are fingerprints that the runner
binds from `knocking` and substitutes into the admission: so the stand repeats what a person does, comparing the fingerprint with the log of
the agent; `$kr` (sc. 20) is the `rev` of the set from `trust` of the view; `$k` (sc. 29) is the private key of the batch from the answer of `POST /domain/batches`, the runner gives it to the command `join` by the directive `@join m2 batch=b1 $k`. In total 21 scenarios / 218 steps.

The stand does not cause the loss of the holder's memory (409 `rebase`): it is checked by the vectors `accept` and by reading the contract of the admission of a report.

Sc. 03 does not depend on the moment of the backup copy (chapter 8.8: `first`, `BACKUP_EVERY`): the member `m1` is a keeper, and
`domain/backup-taken` in its report gives its own generation at any moment of the run. Therefore step 5 waits at `m1` for the object itself
`testsub/snapshot/w-1` (the placement `c3`), steps 6–9 — two changes of the mark of the report round `sent_at`, bound after the snapshot
(two agent passes: one change may belong to a round that was in flight), and only step 10 takes the last generation: in
it the snapshot is there for any number of generations between them (a generation carries all objects of the member, N1.3).

## Evidence outside the TSV

Checked by reading (the norm of the chapter, N5): the CAS of the admission of a member, a failure between the writes of a generation, of `delta` and of the mark, `sign_failures`
in the mark and the view, non-matching certificates `tls_ca_certs`, the union of the handshake at the role door (lesson P/10 N1.4). The knock and the checks
of the holder on a relay packet — sc. 02, 03 of [the acceptance of chapter 9.2](../../../09-agent/acceptance/2/README.md).

## Kit seams

[CALL seams](seams.tsv) execute ordinary code with controlled inputs and I/O under [the forms protocol](../../forms/README.md#seams-and-stages). They do not replace ordinary scenarios, assigned vectors, the process stand or reading of the chapter.
