# Vectors of the alarm list

This English text is the source; the Russian translation `ru/vectors/alarms/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand.

The vectors of the function `alarms(input)` of the domain console — the alarm list of the members at the holder: the state of each member (`ok`,
`silent`, `not_reporting`, `never`, `unreadable`), the silence row, the witnesses, the domain clock at the lines of the page, the history without
repeats, the window and the phrase `sentence`. The owner is lesson P/10 ([norms](../../spec/10-domain-console.norms.md) N1.8, N3 `alarms`,
N5 `alarms`).
The history that the function reads is written by the process `domain` ([P/08.9](../../../08-domain/spec/08.9-domain.norms.md) N1.9);
the alarm page of a member — by the agent ([P/09.1](../../../09-agent/spec/09.1-agent.norms.md) N1.10). The bytes are written by «Specification»; the conformance of the product is by its acceptance against this table.

`case` identifies a vector case. JSON text in `input` and `expect` has no whitespace outside strings; `@exit 2` is a string. The table is the source of these cases.

## Run

Without a stand: the function of an implementation (the command `alarms`, the norms «Implementation decides» item 1) gets the input (the column `input`) and
gives the output; `expect` is a subset of the fields of the output (`@absent` — no such field) or `@exit 2` (the input is out of form: the norms N5
`exit`). A page out of the form of P/09.1 N1.10 — the outcome 0 `unreadable`, not code 2.
Who performs it — the domain console (`10-domain-console`, P/10 N3 `alarms`, N1.8, N5 `alarms`). The process `domain` (`08-domain`) does not perform it: it writes the history that the function reads (P/08.9 N1.9 `writer`; its writing without repeats — the package `alarm-history`); the agent (`09-agent`) writes the alarm page of a member (P/09.1 N1.10).

## Input

- `now` = 1760000000, the window — a day (`since` = `now` − 86400, `until` = `now`; except rows 08, 27), `lost_after` 45 (except row 15);
- the members: `last_report` and `received_at` — the domain clock, `sent_at` — the member clock of the same report (at the vectors — `page.to`; with
  `page` not an object — a number, as `received_at`: `null` at a member with a report — code 2, row 19), `page` — the page of P/09.1 N1.10 (`"garbled"` — does not read; `null` — none), `history` —
  the history object of P/08.9 N1.9; `reported: "garbled"` instead of `last_report`, `received_at`, `sent_at` — the mark is read, out of form;
- `silent_after` is required in each member form and is a finite positive number. The collector supplies the server/camera value from N1.8; the function infers no class and uses no `lost_after` fallback.
- `witnesses` — the witness objects `{sub, name, ts, cluster, units}` (the norms N1.8 `witness`). Here `ts` is already normalized to the domain clock by the originating report, not the clock of the target member. The real collector's two offset directions are checked by CALL seams, not simulated by changing these native inputs.

The names of the subsystems and the units in the input (`testsub`, `testsub/c1`) are data of the input: the vector does not depend on the bytes of the manifests of the catalogue.

## Files

UTF-8, LF, fields separated by TAB; lines with `#` and empty lines are skipped, the first line not skipped is the header. The `note` column explains each case.

| File | Input → expectation |
|---|---|
| The alarm corpus, 37 rows: 22 computed, 15 `@exit 2` | `input` — the input of the command `alarms` as JSON text → `expect`: `{events, members, complete, sentence}` or a part of it |

On a discrepancy the norm is right, «Specification» corrects the vector.

## P/10 neighbours

Each member form requires `silent_after`, a finite positive number; there is no `lost_after` fallback. The collector always supplies the server/camera threshold of N1.8; the function infers no class. A witness input `ts` is already normalized to domain time using its originating report, never the target member's mark. Both offset directions of the actual collector are checked by CALL seams.
