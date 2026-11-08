# Сценарии хода — V/11.9

Цикл хода без модели: `backend` ведёт ход по записанным ответам двери модели над консолью
[`../plan-check/stand3.console.json`](../plan-check/README.md). Исполняет драйвер `backend` (V/11.7 N5).

Текст производный от `vectors/turn/README.md`, руками не правится: источник — английский [`vectors/turn/README.md`](../../../vectors/turn/README.md), правка идёт в него, русский пересобирается переводом (ADR-0121).

Тип реплики (V/11.7 N1.6) векторы не судят: драйвер ставит тип `config` и шаг `route` пропускает, ответы `model` — шаги цикла. Векторов шага `route`, `explain`, `found` нет: предел, судятся чтением.

```yaml
id, rule:       the name and the rule of V/11.9
console:        the console — ../plan-check/<name>.console.json
text:           the admin's request
answers:        the admin's answers to ask_admin in order (texts of the turn)
answer_secrets: numbers of the secrets entered together with an answer
text_secrets:   numbers of the secrets entered together with the request
refine:         texts of new requests with the context of the outcome, in order (V/11.9 N1.5); model continues
cancel_on_tool: a tool name — the stream is closed while it is executing (cancelled() is true from this call on; V/11.9 N1.6)
context:        the model row window (default 16384); prompt_tokens — usage of each model answer
model:          the answers of the steps in order — {ok: true, message, usage} (the door state done: message as is),
                {ok: false, lost: true} (410/404), {ok: false, why, reason} (failed and other step outcomes, V/11.9 N1.3)
expect:         outcome (plan | refusal | unfinished | cancelled), why and reason for unfinished and refusal, rule — the rule kind at the
                limit after rejected versions (V/11.9 N1.5), plan_rows for a plan
                (unit, revision, changes {field, from, to}, because — the witnesses of the selection by conditions: [{field, witnesses,
                values}] or null for named; V/11.11 N1.7),
                texts — the texts of the turn, steps — the number of steps, step_messages — the messages of each step: role,
                reasoning_content (the key is present only if the message carries it: `backend` strips it — V/11.9 N1.2,
                so it is not in the expectations), tool_call_id, the names of tool_calls, content — the first 160 characters; no field — the steps are not judged
```

Случайные байты `turn` — заглушкой (сравнивается длина, не значение).
