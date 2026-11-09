# The writer turn contract: the turn row, terms, guard, barrier

This English text is the source; the Russian translation `ru/contracts/turn.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

A common contract of the module «Platform» (ADR-0083 addendum (5), addendum (13): one changing writer at each moment — at the
subsystem controller and at the `domain` process of the holder; one algorithm is a contract, not copies in chapters; layout audit A-03,
the Architect's decision of 2026-10-25). The owner is lesson [P/04](../../04-controller/spec/04-controller.norms.md) (N1.5 «Placement admission
between controllers», N3 «get and hold the placement turn»). Participants: the controller — the row
`<sub>/controller/placement_turn` (P/04); the `domain` process at the holder — the row `domain/signer-turn`
([P/08.10](../../08-domain/spec/08.10-domain.norms.md) N1.7, N3); the member agent — the row `domain/agent-turn`
([P/09.1](../../09-agent/spec/09.1-agent.norms.md) N1.13, N3 «the agent turn»; DOM-AGENT-TURN-01, the owner's consent of 2026-10-26): by the same rule as the turn
of the `domain` process (the column «Turn of the `domain` process» below, the form `{holder}`). The cluster console — the row `<sub>/operations-turn`
([P/06.9](../../06-console/spec/06.9-console.norms.md) N3 «leader»; ADR-0095): the leader of the group operations of a subsystem (the column «Operations turn» below).

Moved from P/04 N1.5 (`TURN_TERM`, `TURN_RENEW`) and N3 «get and hold the placement turn» (the steps, the barrier,
«Races») without a change of behaviour; P/04 and P/08.10 refer here. What is each participant's own — the row key, the mark
`holder`, which writes go under the guard, when the turn is given up — is the participant's (P/04 N1.5, N3; P/08.10 N1.7).

Normative keywords follow [the course canon](../NORMATIVE-TERMS.md).

## Form

The turn row of the controller is the family `placement-turn`: the form `Platform/04-controller/data/placement-turn.schema.json`, the outcomes
`Platform/04-controller/data/placement-turn.outcomes.tsv`; the turn row of the `domain` process is the family `signer-turn`:
`Platform/08-domain/data/signer-turn.schema.json`, `Platform/08-domain/data/signer-turn.outcomes.tsv`; the operations turn row is the family `operations-turn`:
`Platform/06-console/data/operations-turn.schema.json`, `Platform/06-console/data/operations-turn.outcomes.tsv`. The operations `cas` and
`guard` are [the store client contract](store-client.md).

## Terms

```yaml
TURN_TERM: 45                         # age of an unchanged version by the claimant's clock
TURN_RENEW: 10                        # renewal between operations; the term of one's own request is monotonic
```

## Get and hold the turn

The steps are as at the controller (P/04 N3); `<turn>` is the turn row of the participant, a «changing write» is the writes that the participant
makes under the guard (at the controller — P/04 N3 «get and hold the placement turn» step 5, at the `domain` process — P/08.10
N1.7 `guard`):

1. Read `<turn>`. If it is unreadable, the step is refused. If `manifest_rev` > mine, do not change anything: `manifest_behind`
   (`manifest_rev` is only in the turn of a subsystem, `placement_turn`; `domain/signer-turn` has no revision and it is not checked;
   TURN-FORM-32-01, the Architect's decision of 2026-10-25). The operations turn also has no `manifest_rev`; its own fresh-attempt holder rule is the Operations turn column, not the signer's stable instance.
2. If there is no row, use `cas ""`. If `holder` is empty, use the cas of the read version. If `holder` is foreign and this version has
   not changed for ≥ `TURN_TERM` by my clock, use the cas of the read version. Otherwise the turn is busy: this pass does not change the
   placement; the next one tries again.
3. Write `{holder: a new unique mark of this attempt, manifest_rev: mine}` with the chosen cas (`domain/signer-turn` — only
   `{holder}`, TURN-FORM-32-01, the Architect's decision of 2026-10-25; operations — only `{holder}` with a new attempt mark). On `conflict` the turn is not obtained; when confirmed,
   remember the version of turn and the time the request was sent.
4. Every `TURN_RENEW`, between operations, rewrite one's own turn row with the cas of one's own version. When confirmed — a new
   guard and the start of one's own term from the sending; on `conflict` or a foreign `holder` — stop the writes.
5. While one's own confirmed request is younger than `TURN_TERM`, every changing write has the cas of the target row AND
   `guard {key: <turn>, index: my version}`. When one's own term has expired, do not write until a confirmed renewal; on 412, stop the
   current attempt.
6. End of the pass: write `holder: ""` with the cas of one's own version; do not repeat on a conflict.

**An unknown outcome of a write of one's own turn row** (the taking of step 3 or the renewal of step 4 applied or not, the answer lost) — all
three forms (C08-TURN-SELF-99, the Architect's decision of 2026-10-26; at the `domain` process — P/08.10 N3): it is not counted as a success; re-read `<turn>`: if `holder` is the mark of this attempt
(at the turn of the `domain` process — this instance), confirm it by `cas` of the read version (confirmed — the turn is one's own, the
version is remembered); otherwise (there is no row, `holder` is foreign or empty) the turn is not obtained in this attempt. The giving up
of the subsystem turn (step 6) writes `{holder: "", manifest_rev: <mine>}` — the field is required by the form.

## Differences of the turns

The terms (`TURN_TERM`, `TURN_RENEW`), `cas`, the guard, the giving up and the barrier are common; the differences (TURN-FORM-32-01, the Architect's decision of 2026-10-25):

| | Subsystem turn | Turn of the `domain` process | Operations turn |
|---|---|---|---|
| row | `<sub>/controller/placement_turn` (P/04 N1.5) | `domain/signer-turn` (P/08.10 N1.7); at the member agent — `domain/agent-turn` (P/09.1 N1.13) | `<sub>/operations-turn` ([P/06.9](../../06-console/spec/06.9-console.norms.md) N3 «leader») |
| form | `{holder, manifest_rev}` | `{holder}` — there is no revision and it is not checked | `{holder}` — there is no revision and it is not checked |
| `holder` | a new unique mark of each attempt | the process instance ([the instance contract](instance.md)); it rewrites its own row by CAS of the read version (P/08.10 N3 step 2) | a new unique mark of each attempt |
| step 1 `manifest_rev > mine` | do not change, `manifest_behind` | does not apply | does not apply |
| under the guard | write and delete of `placement/*`, `workers/*`, `placement_intent`, delete of a unit row by `delete_after` (P/04 N3) | every write of the process to a row of the holder's store (P/08.10 N1.7 `guard`); at the agent — every write to a row `domain/*` of the member (P/09.1 N1.13 `guard`) | the writes of the leader: the row `<sub>/operations-epoch`, the write flags of an operation, the results of a failure and of `cancel`, the removal of a secret, the finish batch; a step batch goes by the ticket and guards the generation, not the turn (P/06.9 N2) |
| giving up | at the end of the pass (step 6) | on SIGTERM by the active process (P/08.10 N1.7 `release`) | when there are no unfinished operations (step 6) and on SIGTERM |
| not obtained | the pass does not change the placement | the process is standby, `standby` (P/08.10 N3) | the console does not run operations this tick, the doors work |

## Barrier

Any non-answer, unknown outcome, conflict or 412 on a change of the placement interrupts
the current plan of actions in memory. Before continuing, the controller changes the version
of its turn with cas, confirmed (if holder is already foreign, it stops), then reads intent and the rows anew.
This barrier also cuts off an old write still in flight: it is either applied before the barrier and visible to the read,
or gets 412 after it. A non-answer of the barrier itself forbids continuing. One cannot simply
substitute a newer guard version into the former command. Two changing passes of one process
also do not run at the same time under one turn; a renewal is not executed in parallel with a target write.

**Races.** Of two capture cas, one passes. The new holder reads the world anew after the capture;
late changing writes of the old holder are refused by the turn guard, even if the target row did not change. The old holder
does not renew and does not release a foreign turn by its own cas. To a new observer a foreign turn is fresh at first; the wait does not depend on
the clock of the former holder. The time of sending one's own confirmed request is the time of the first sending of this logical write;
a repeat with the same id and the answer again do not shift it (the same rule at the slot and the lease, P/03.2). A vanished holder delays
changes at most until the next successful attempt after the observation window, but the answer term of an unavailable store is not
bounded by this.

## Production obligations

ADR-0130 Addendum (10), MB4: the turn lease is NOT a fence for external side effects. Its `guard` protects only store mutations that carry it, under the declared clock qualification. A paused old holder can resume after another holder takes the turn; the store rejects its old guard with `412`, but that alone cannot prevent an external action. Each external-effect owner MUST declare and qualify its own independent fence at the effect boundary before relying on exclusivity. Without that fence no exclusive external-effect claim follows from this contract. The controller's barrier and existing `cas`/`guard` wire remain unchanged.

## Vectors

The package [`turn`](../vectors/turn/README.md) (C08-TURN-SELF-99, the Architect's decision of 2026-10-26): sequences of events
of one side over a turn row and its actions — take an empty or a given-up one, one's own row of the `domain` process (`held`, not
`busy`), a foreign live one — busy, a foreign one older than `TURN_TERM` — take, `manifest_rev` (step 1), renewal, the guard, 412, the barrier on
an unknown outcome of a write — of the target row and of one's own turn row, the giving up `holder ""`; placement, signer and operations forms. The console runs its own 16 operations cases with a fresh attempt holder, no manifest revision, not signer relabeling; the 33 previous cases and their existing participants stay byte-identical. Capturing the turn is separate from P/06.9's operations-epoch CAS barrier, generation/ticket guards, two leaders and late IO. Races of two claimants and late writes of the old holder are
acceptance scenarios of the participants (P/04, P/08.10, P/09.1, P/06.9) and reading. The exact owner/kind selector and narrow freshness comparison are [the wire form](../vectors/wire.md#turn-comparison), the Architect's decision under ADR-0127 P/06 C4.

The cell `input` of `cases.tsv` is `{kind, turn, me, steps}`: `kind` is `placement` (the turn of a subsystem), `signer` (the turn of the process `domain`; the turn of the agent of a member `domain/agent-turn` by the same rule, P/09.1 N1.13) or `operations` (the console's own operations turn, P/06.9); `turn` is the key of the turn row (the guard key); `me` is its own: the `manifest_rev` of the controller or `holder`, the instance of the process `domain`; at `operations`, `me` is exactly `{}` and the holder is generated for each attempt, not supplied as a process instance, there is no `manifest_rev` in this form. `steps` is the events of one side, in order: `{read, version?, seen}` — the turn row is read (steps 1–3): `read` is the row (`null` — there is no row, `"@unreadable"` — it does not read by the form), `version` is its version, `seen` is how many seconds this version has been unchanged on my monotonic clock (the first look — `0`); `{reply: ok, version}`, `{reply: conflict}`, `{reply: none}` — the answer to my write of the turn row: confirmed with a new version, a `cas` conflict, no answer; `{renew: true}` — the term `TURN_RENEW`: renew (step 4); `{target: true, age}` — a changing write of the participant, `age` is the age of its own confirmed turn request in seconds; `{target_reply: "412"}`, `{target_reply: "none"}` — the guard refused, a changing write without an answer; `{end: true}` — the end of the pass (`placement`, step 6), no unfinished operations or SIGTERM (`operations`, P/06.9), or `SIGTERM` at the active one (`signer`, P/08.10 N1.7 `release`).

The native output is an array of actions, one per event, in order: `{write, cas}` — write the turn row `write` by `cas` (`""` — there is no row, otherwise the version); in `write` at `placement` `holder` is a new unique mark of this attempt or the mark of its own attempt and `manifest_rev` is mine, at `operations` the same rule for `holder` without `manifest_rev`, at `signer` `{holder: <me>}` or `{holder: ""}`; `held` — the turn is its own, the version is remembered; `not_held` — not obtained (including after `reread`: the row does not name this attempt; at `signer` — a waiting one); `busy` — occupied; `refused` — a refusal of the step (the row is unreadable; at `signer` — a waiting one); `manifest_behind` — step 1; `{guard: {key, index}}` — the write goes with the guard; `wait` — its own term has expired, do not write until a confirmed renewal; `stop` — cease the writes; `reread` — re-read (the barrier is confirmed at `placement`: intent and the rows; an unknown outcome of the write of its own turn row: the turn, and in `read` `holder` `"@same"` — the mark of this attempt); `done` — the release is complete, the conflict does not repeat. The lexemes `"@new"` and `"@same"` are written only in the table (`expect` and `read` of the input): in the input the side substitutes its current mark, in the output it writes the real marks.

[Common finite budgets and acceptance limits](production-obligations.md) are required for the applicable phases of this contract.
