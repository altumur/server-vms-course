# Turn scenarios — V/11.9

This English text is the source; the Russian translation `ru/vectors/turn/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121).

The turn loop without a model: `backend` runs the turn by recorded answers of the model door over the console
[`../plan-check/stand3.console.json`](../plan-check/README.md). The `backend` driver executes it (V/11.7 Н5).

The vectors do not judge the utterance type (V/11.7 Н1.6): the driver sets the type `config` and skips the step `route`; the `model` answers are steps of the loop. There are no vectors for the steps `route`, `explain`, `found`: a limit, they are judged by reading.

```yaml
id, rule:       the name and the rule of V/11.9
console:        the console — ../plan-check/<name>.console.json
text:           the admin's request
answers:        the admin's answers to ask_admin in order (texts of the turn)
answer_secrets: numbers of the secrets entered together with an answer
text_secrets:   numbers of the secrets entered together with the request
refine:         texts of new requests with the context of the outcome, in order (V/11.9 Н1.5); model continues
cancel_on_tool: a tool name — the stream is closed while it is executing (cancelled() is true from this call on; V/11.9 Н1.6)
context:        the model row window (default 16384); prompt_tokens — usage of each model answer
model:          the answers of the steps in order — {ok: true, message, usage} (the door state done: message as is),
                {ok: false, lost: true} (410/404), {ok: false, why, reason} (failed and other step outcomes, V/11.9 Н1.3)
expect:         outcome (plan | refusal | unfinished | cancelled), why and reason for unfinished and refusal, rule — the rule kind at the
                limit after rejected versions (V/11.9 Н1.5), plan_rows for a plan
                (unit, revision, changes {field, from, to}, because — the witnesses of the selection by conditions: [{field, witnesses,
                values}] or null for named; V/11.11 Н1.7),
                texts — the texts of the turn, steps — the number of steps, step_messages — the messages of each step: role,
                reasoning_content (the key is present only if the message carries it: `backend` strips it — V/11.9 Н1.2,
                so it is not in the expectations), tool_call_id, the names of tool_calls, content — the first 160 characters; no field — the steps are not judged
```

The random bytes of `turn` — by a stub (the length is compared, not the value).
