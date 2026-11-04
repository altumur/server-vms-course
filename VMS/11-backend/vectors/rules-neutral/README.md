# Vectors of the neutral plan translator — V/11.13

This English text is the source; the Russian translation `ru/vectors/rules-neutral/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The translator of the neutral plan into the contract body (chapter 13 Н1.4) and its refusals. There is no model: the plan is given ready-made. The expectations are derived by a write-up of the norm independent of the pilot's code; they are not checked by an implementation.

## Files

| File | What |
|---|---|
| `cases.json` | `world` — cameras, children, folders, schedules, modes, roles, rules, as in [`rules-words`](../rules-words/README.md); `cases` — `{id, note, plan, body, errors}`: `plan` — the neutral `edits`, `body` — `AssistRuleEdit` in order, `errors` — the refusal words of the translation |

- `body` — only what the translator derives from the plan: the defaults of `Rule` and the `logOnly` of a new rule are not here, they are set by the translation and the write (Н1.4, Н1.7).
- Contract ids are signs `<вид>:<id мира>` (kind:world id): `device:<камера>`, `child:<ключ>`, `folder:`, `rule:`, `role:`, `schedule:`, `mode:`. The real id is a UUID by V/11.3 Н1.6; the vector does not judge it.
- `errors` are not empty — `body` is `null`: the plan is not translated, the layers do not judge.

The world has two cameras with identical children «Вход 1», «Реле 1», two cameras «Lift», two rules «Alarm», two folders «Floor 1» under different parents: names with the camera and the path, the refusals `several`, `is named with its camera`, `is named by its path`. The translator carries `default`, `stop`, `via` as they are: the judgements `default_yes`, `reset`, `via` are the layers over the row, the vectors [`rules-words`](../rules-words/README.md).

**Limit:** these vectors do not go round the circle row → body → neutral → body → row: the translation of the body into a V/07 row (V/11.3 Н1.3) is not judged here.
