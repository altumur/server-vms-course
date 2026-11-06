# Vectors: the writer turn — sequences over the turn row

This English text is the source; the Russian translation `ru/vectors/turn/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The owner is [the writer turn contract](../../contracts/turn.md) (lesson P/04 N1.5, N3; C08-TURN-SELF-99, the Architect's decision
2026-10-26). The participants are the controller (`<sub>/controller/placement_turn`, P/04) and the process `domain` of the holder
(`domain/signer-turn`, [P/08.10](../../../08-domain/spec/08.10-domain.norms.md) N1.7, N3), the member agent (`domain/agent-turn`, P/09.1), and the console (`<sub>/operations-turn`, P/06.9). The bytes are written by «Specification»; the rows are
by the text of the contract and P/08.10 N3 «the turn of the domain process», the norms do not change.

## `cases.tsv`

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header `case<TAB>input<TAB>expect<TAB>note`.
A row is one sequence of events of one side; `expect` is the array of its actions, one per event, in order.

**Input** — `{kind, turn, me, steps}`: `kind` — `placement` (the turn of a subsystem) or `signer` (the turn of the process `domain`; the turn of the agent of a member `domain/agent-turn` —
by the same rule, its cases are the `signer` rows, P/09.1 N1.13), or `operations` (the console's own operations turn, P/06.9);
`turn` — the key of the turn row (the guard key); `me` — its own: the `manifest_rev` of the controller or `holder` — the instance of the process
`domain` ([the instance contract](../../contracts/instance.md)); at `operations`, `me` is exactly `{}` and the holder is generated for each attempt, not supplied as a process instance. There is no `manifest_rev` in this form. `steps` — the events:

| Event | Meaning |
|---|---|
| `{read, version?, seen}` | the turn row is read (steps 1–3): `read` — the row (`null` — there is no row, `"@unreadable"` — it does not read by the form); `version` — its version; `seen` — how many seconds this version has been unchanged on my monotonic clock (the first look — 0) |
| `{reply: ok, version}` / `{reply: conflict}` / `{reply: none}` | the answer to my write of the turn row: confirmed with a new version, a `cas` conflict, no answer |
| `{renew: true}` | the term `TURN_RENEW`: renew (step 4) |
| `{target: true, age}` | a changing write of the participant; `age` — the age of its own confirmed turn request, s |
| `{target_reply: "412"}` / `{target_reply: "none"}` | the guard refused / a changing write without an answer |
| `{end: true}` | the end of the pass (`placement`, step 6), no unfinished operations or SIGTERM (`operations`, P/06.9), or `SIGTERM` at the active one (`signer`, P/08.10 N1.7 `release`) |

**Actions**: `{write, cas}` — write the turn row `write` by `cas` (`""` — there is no row, otherwise the version); in `write` at
`placement` `holder` is `"@new"` (a new unique mark of this attempt, not equal to the former ones) or `"@same"` (the mark of its own
attempt), `manifest_rev` — mine; at `operations` the same fresh/current-attempt rule applies to `holder`, without `manifest_rev`; at `signer` — `{holder: <me>}` or `{holder: ""}`; `held` — the turn is its own, the version is remembered;
`not_held` — not obtained (including after `reread`: the row does not name this attempt) (at `signer` — a waiting one); `busy` — occupied; `refused` — a refusal of the step (the row is unreadable; at `signer` —
a waiting one); `manifest_behind` — step 1; `{guard: {key, index}}` — the write goes with the guard; `wait` — its own term has expired, do not
write until a confirmed renewal; `stop` — cease the writes; `reread` — re-read (the barrier is confirmed at `placement`:
intent and the rows; an unknown outcome of the write of its own turn row: the turn, and in `read` `holder` `"@same"` — the mark of this attempt); `done` — the release is complete, the conflict does not repeat.

49 rows: the existing33 rows are byte-identical; `placement` — take an empty one, a released one, a foreign one older than `TURN_TERM` (45; 44.999 — occupied), the first look, below and above
`manifest_rev` (10 > 9 as a number), an unreadable one, a capture conflict, a renewal and its conflict, the guard before and after `TURN_TERM`, 412,
the barrier (confirmed, without an answer, a conflict), the release `holder ""`, an unknown outcome of the taking (applied, no row, a foreign one) and
of the renewal; `signer` — take an empty one, its own row (`held`, not `busy`) and its
conflict, a foreign live one and one older than `TURN_TERM`, a released one, an unreadable one, the guard, the renewal, `SIGTERM`, an unknown outcome of the taking (its own, a foreign one),
the barrier of a write with the guard.

The first 15 `operations` rows cover taking an absent/released/stale row, live and first-look busy, unreadable form, capture conflict, renewal and conflict, guard age/412, release, and unknown capture/renewal outcomes (own, absent or foreign). These are the common turn obligation of the console, with a new attempt holder. They do not rename signer cases or copy placement's plan barrier into operations. The operations-epoch CAS barrier, generation/ticket guards, two leaders and late IO remain P/06.9's separate mandatory acceptance duties; `held` proves only the turn capture.

The release of `placement` writes `manifest_rev` with its own revision (the form `placement-turn` requires the field); an unknown outcome of the write
of its own turn row — the contract «An unknown outcome of a write of one's own turn row» (both answers — C08-TURN-SELF-99, the decision
of «Architect» 2026-10-26).


Case49, `operations-two-attempts-after-release`, is the approved12-event sequence with exactly `@new`, `@same`, empty-holder/done, `@new`, `@same`, empty-holder/done. Both end events mean idle with no unfinished work, not SIGTERM. Keep one live process/Turn; the caller schedules its next pass/capture after done, not an internal retry. Preserve all earlier fresh labels across release within this case: the second new label differs from the first, and same refers to the latest new. Reset label history only between cases. The second capture has an unknown reply, then the ordinary owned reread/CAS confirmation. Old33+15 rows stay byte-identical. This is a published source obligation, not proof that a Turn/native/operations implementation executed it.

## Run

Without a stand: a side gives the events to its turn algorithm (the store and the clock are replaced by the events) and reconciles the actions;
`"@new"` — any new mark not equal to the former marks of this side, `"@same"` — the mark of its current attempt. The lexemes `"@new"`, `"@same"` are written only in the table (`expect` and `read` of the input); in the input the side substitutes its current mark, and in the output it writes the real marks, and the judge reconciles them by this rule. A lexeme given as a string is judged as a mark: `"@same"` after `"@new"` is another mark, red (C04-TURN-LABEL-LEXEME-01, the decision of the Specification). The races of two
contenders and the late writes of an old holder — the acceptance scenarios of P/04, P/08.10 and reading.
Who performs it — by `kind`: `placement` — the controller (`04-controller`, P/04 N3 «get and hold the placement turn», the row `placement_turn`); `signer` — the process `domain` of the holder (`08-domain`, P/08.10 N1.7, N3 «the turn of the domain process») and the agent of a member (`09-agent`, P/09.1 N1.13, N3 «the agent turn» — `domain/agent-turn` by the same rule); `operations` — only the console (`06-console`, P/06.9, `<sub>/operations-turn`). Merely naming `placement_turn` does not assign its cases to the console (ACC-VECTORS-CONNECT-03). The exact owner/kind selection and `compare=turn` transport are declared in `wire.tsv`; its narrow form is [wire.md](../wire.md#turn-comparison). No holder is ignored, no alias or widened consumer selector is permitted (the Architect's decision under ADR-0127, P/06 C4).
