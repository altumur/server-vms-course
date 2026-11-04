# Vectors of the rule words reconciliation — V/11.13

This English text is the source; the Russian translation `ru/vectors/rules-words/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The reconciliation with the words of the request (chapter 13 Н1.6) and the prohibitions (Н1.5) on the measurement cases. There is no model: the plan row is given ready-made. The expectations are derived by a write-up of the chapter's rules over `harness/rules/words.json`, independent of the pilot's code; they are not checked by an implementation. Cases with `known_gap` fix a limit: the plan is wrong, and the reconciliation accepts it.

## Files

| File | What |
|---|---|
| `cases.json` | `world` — cameras (an `eventsrc` row also has `words`, V/01.1 Н1.1г), children (a relay without `name` — without a name), the units `units` (rows of `cam/device_units`: `key`, `camera`, `n`, `type`, `title?`), folders, schedules, modes, rules, servers, roles; `cases` — `{id, note, request, row \| edits, errors, known_gap?}`: `row` — the row of a new rule, `edits` — the whole plan |

`errors` — the error words: the prohibitions of Н1.5 come before the reconciliation, the reconciliation goes in the order of the rows of the table of Н1.6, a plan error has the prefix `edits[i]`; empty — the layers are passed.

A plan row is the translation of the neutral plan (Н1.4): the layers judge the row, so the cases are given as a row. `ask`, `escalate` are composed with ADR-0093 addendum (9): the cases `ask-*`, `escalate-*`; the level path is `<путь шага>.levels[k]` (step path).

The words of ADR-0093 addenda (19)–(38): the cases `step-*` (a named step), `same-cam-*` (the same camera), `runrule-kick-off`, `segment-stops-recording`, `silent-drops-off`, `lost-*`, `arm-put-on-guard`, `role-other-language`, `segment-loses`, `*-off-guard*`, `ask-default-*` (`default yes` and the negation), `recording-*`, `wait-still*` (item 1 of addendum (19)), `pass-*`, `open-*`, `on-numbered`, `ru-*` (the pass relay and the number, «открой» ("open"), the number sign, Russian stems with a boundary; `pass-lock-name` — the name is cut out before the state words, `pass-steps-order` — the order of the ending «на N секунд» ("for N seconds")), `runrule-*` (running a rule), `disarm-*`, `arm-*`, `armed-false-ru` (disarming only with «охран»), `relay-off-ru`, `record-ru-pisat`, `disable-*` (disabling a camera, «switch … off» with words in between), `vanish-*` («пропад»), `unit-*` (the trigger `unit`, an event word with boundaries), `text-*` (the trigger `text`). The text is reconciled in lower case, word boundaries are by `tokens` (V/11.13 Н1.6).
