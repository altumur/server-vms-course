# Judge-only case data

This English text is the source; the Russian translation `ru/acceptance/1/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing named case associations as judge-only provenance.

[the contract](../../spec/09-agent.api.openapi.yaml), the lecture (`ru/09-agent.md`, for people, not in the export). The scenarios were moved (stage B, ADR-0083
addendum (1): without a change of behaviour) from the acceptances of M11/05 (04 → 13), M11/06 (04, 07, 08), M11/10 (11), M11/11 (05, 06 → 14) and
M11/12 (01, 03, 06); the numbers, names and steps are the former ones, except `13-slot-liveness` (in M11/05 — `04-slot-liveness`) and
`14-pointer-checksum` (in M11/11 — `06-pointer-checksum`): the number 04 is taken by the scenario of M11/06, the number 06 — by the scenario of M11/12;
the next numbers after the largest number of the sources of the chapter (M11/10 sc. 12) — in the order of the lesson M11, then of the scenario
(the Architect's decision on the move plans 8–10, item 14; a row of `corrections-1.tsv` (historical correction record)). In total 22 scenarios / 252 steps: 5 from
M11/05, 26 from M11/06, 20 from M11/10, 11 from M11/11, 40 from M11/12, 2 — sc. 06 steps 9–10 (`as_of` to the medium no more often than once an hour; VMS request № 19); 20 — sc. 15 `one-agent` (DOM-AGENT-TURN-01);
35 — sc. 16–19 of the coverage audit of P/09 (audit-kimi aee4369fb, drafts J01–J04); 72 — sc. 20–25 of its second pass (Gemini,
cc36de538, drafts G03, G04; below); 21 — sc. 27 `roles-copy` (ADR-0098 §4).

The other scenarios of the sources are at the chapters of their outcome (ADR-0083 addendum (13); the appendix of the plan of the move of lesson 8): M11/05
sc. 01, 03, 05 — [chapter 8.5](../../../08-domain/acceptance/5/README.md), 02 — [the acceptance of chapter 6.7](../../../06-console/acceptance/7/README.md) (13); M11/06 sc. 01, 02,
03, 05, 09 — [chapter 8.6](../../../08-domain/acceptance/6/README.md), 06 — [chapter 8.1](../../../08-domain/acceptance/1/README.md)
(sc. 15); M11/10 sc. 01 — the acceptance of chapter 6.7 (15), 02–04, 08–10, 12 — [chapter 8.8](../../../08-domain/acceptance/8/README.md),
06 — the vector package [`follow`](../../vectors/follow/README.md); M11/11 sc. 01 — [chapter 8.9](../../../08-domain/acceptance/9/README.md),
02 — [the acceptance of lesson P/10](../../../10-domain-console/acceptance/README.md), 04 — the vector [`alarms`](../../../10-domain-console/vectors/alarms/README.md), 03 — the vectors [`resolve`](../../../06-console/vectors/resolve/README.md); M11/12 sc. 02 — [chapter 8.3](../../../08-domain/acceptance/3/README.md) (sc. 17), 04,
05 — [chapter 8.10](../../../08-domain/acceptance/10/README.md). The agent side in the scenarios of other chapters — the list
«Neighbours on the stand» of the norm of the chapter, N5.

The differences by scenario (from the READMEs of the source acceptances):

- **Scenarios 01, 03, 06** (from the acceptance README of M11/12). The doors `holder`, `member`, `resource` and the directives `@domain`,
  `@start`/`@stop agent` — the dictionary of the «Domain stand».
- **Scenarios 04, 07, 08** (from the acceptance README of M11/06). The catalogue `testsub` — `domain.edit: [start, labels]`, `domain.ref:
  name`. The doors `holder`, `member` and the directives `@domain`, `@cut`, `@mend`, `@clock` — the dictionary of the «Domain stand»; at the door
  `holder` the runner sets `Idempotency-Key` also for `PUT`/`DELETE`. `$id` is the id of the stored edit from the answer 202. The holder stores
  the edit (chapter 8.6), the agent of `m1` applies it (N1.5) after `@mend`; the condition `If-Match` of the units door — sc. 14 of the acceptance of
  [P/06.1](../../../06-console/acceptance/1/README.md). Sc. 08: `@clock m1 +90` — the agent clock outside the window of the units door
  `UNIT_WINDOW` 60 s ([the agent signature contract](../../../common/contracts/agent-signature.md)); step 10 returns the clock.
- **Scenarios 05, 14** (from the acceptance README of M11/11). The catalogue `testsub` with a declaration of the shared document:
  - `domain.shared: [step, marks, {rounds}]`;
  - `step` — `int` with `inherit: 1`;
  - `marks` — `list` with `inherit: []`, `merge: union`.

- **Scenarios 16–19** (the coverage audit of P/09, audit-kimi aee4369fb). The doors `holder`, `member`, `store`, `token` and the directives
  `@domain`, `@stop`/`@start agent`, `@on` (`@freeze`, `@thaw`, `@put object`) — the dictionary of the «Domain stand» and the common dictionary
  of directives; the freeze limit is 120 s.

### Coverage audit of P/09, the second pass (Gemini)

Sc. 20–25 (`audit-coverage-gemini` cc36de538, drafts G03, G04) — the same stand; the doors `holder`, `member`, `store`,
`token` and the directives `@domain`, `@join`, `@stop`/`@start agent`, `@on` (`@put object`) — the dictionary of the «Domain stand». The rows
bypassing the writer are put by the store door of the member through `admin.sock`, as in sc. 03 and 18.

## Inputs `inputs/`

| File | Scenario | What is in it |
|---|---|---|
| `shared-doc-unknown-issuer.json` | 05, 14, 22 | a shared document of the form ([P/08.9 N1.2](../../../08-domain/spec/08.9-domain.norms.md) `document`) with an unknown issuer: `kid` `0000000000000000`, `issuer` — 32 bytes `0x11`, `sig` — 64 zero bytes base64url |
| `backup-foreign-term.json` | 19 | a backup copy document of the form `backup.schema.json` (`common.domain_backup_doc`) of term and revision 99, `holder` `hold`, `members` `[hold, m1]`, empty `state` and `objects`, `issuer` — 32 bytes `0x33`, `kid` — the first 16 characters, `sig` — the bytes 0…63 base64url (does not verify: the agent reads its own copy by form); JCS without a line break, sha256 `eec6d36c2e9636846f2d335daf072c791c8022e1e714091f05fe56e4b2380434` — in the row `domain/backup-taken` of step 5 |

`shared-doc-unknown-issuer.json` is copied byte for byte from `inputs/` of the acceptance of M11/11 (the plan of the move of lesson 9, § 3
«Inputs and form»); `backup-foreign-term.json` — the coverage audit of P/09 (draft J04), the bytes of the draft.


The three positive vectors must reach the actual copy write.

and marker to stay unchanged and zero copy writes and related edits. The five cases cover as_of in the digest, JCS
instead of wire formatting, a refused digest of doc alone and a refused mismatching whole-body digest.

The owner wire body contains raw KV strings doc and as_of. Only the outer JSON is canonicalized for the digest; the internal doc text is not normalized first. The inner-text neighbor has equal decoded inner objects but different strings and digests, and observes the exact successful copy_items. The trusted advertised as_of, received_at and domain_age retain their existing numeric types. Existing refusal cases preserve the complete initial raw copy, index and the rebaselined current-wire marker. No case reports actual IO success before its adapter is run.
