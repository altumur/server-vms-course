# Сценарии хода — V/11.9

Цикл хода без модели: `backend` ведёт ход по записанным ответам двери модели над консолью
[`../plan-check/stand3.console.json`](../plan-check/README.md). Исполняет драйвер `backend` (V/11.7 Н5).

Тип реплики (V/11.7 Н1.6) векторы не судят: драйвер ставит тип `config` и шаг `route` пропускает, ответы `model` — шаги цикла. Векторов шага `route`, `explain`, `found` нет: предел, судятся чтением.

```yaml
id, rule:       имя и правило V/11.9
console:        консоль — ../plan-check/<имя>.console.json
text:           просьба админа
answers:        ответы админа на ask_admin по порядку (тексты хода)
answer_secrets: номера секретов, введённых вместе с ответом
text_secrets:   номера секретов, введённых вместе с просьбой
refine:         тексты новых запросов с context исхода, по порядку (V/11.9 Н1.5); model идёт дальше
cancel_on_tool: имя инструмента — закрытый поток, пока он исполняется (cancelled() — да с этого вызова; V/11.9 Н1.6)
context:        окно строки модели (умолчание 16384); prompt_tokens — usage каждого ответа модели
model:          ответы шагов по порядку — {ok: true, message, usage} (состояние done двери: message как есть),
                {ok: false, lost: true} (410/404), {ok: false, why, reason} (failed и прочие исходы шага, V/11.9 Н1.3)
expect:         outcome (plan | refusal | unfinished | cancelled), why и reason у unfinished и refusal, rule — вид правила у
                предела после отвергнутых версий (V/11.9 Н1.5), plan_rows у плана
                (unit, revision, changes {field, from, to}, because — свидетели отбора по условиям: [{field, witnesses,
                values}] или null у named; V/11.11 Н1.7),
                texts — тексты хода, steps — число шагов, step_messages — сообщения каждого шага: role,
                reasoning_content (ключ есть, только если сообщение его несёт: `backend` его снимает — V/11.9 Н1.2,
                поэтому в ожиданиях его нет), tool_call_id, имена tool_calls, content — первые 160 знаков; нет поля — шаги не судятся
```

Случайные байты `turn` — заглушкой (сравнивается длина, не значение).
