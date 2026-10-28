# Сценарии хода — V/10.3

Цикл хода панели «Ассистент» без модели и без DOM: ядро страницы (`VMS/01-cam/cam.shell.html`, между метками
`assist:core`) ведёт ход по записанным ответам двери модели над консолью
[`../plan-check/stand3.console.json`](../plan-check/README.md). Исполняет свой прогон jsdom VMS у раннера (ADR-0093
доп. (1) п. 11).

```yaml
id, rule:       имя и правило V/10.3
console:        консоль — ../plan-check/<имя>.console.json
text:           просьба админа
answers:        ответы админа на ask_admin по порядку (тексты хода)
answer_secrets: номера секретов, введённых вместе с ответом
context:        окно строки модели (умолчание 16384); prompt_tokens — usage каждого ответа модели
model:          ответы шагов по порядку — {ok: true, message, usage} (состояние done двери: message как есть),
                {ok: false, lost: true} (410/404), {ok: false, why, reason} (failed и прочие исходы шага, V/10.3 Н1.3)
expect:         outcome (plan | refusal | unfinished | cancelled), why и reason у unfinished и refusal, plan_rows у плана,
                texts — тексты хода, steps — число шагов, step_messages — сообщения каждого шага: role, tool_call_id,
                имена tool_calls, content — первые 160 знаков
```

Случайные байты `turn` — заглушкой (сравнивается длина, не значение). Сценарии панели в DOM (раздел, ввод, блок отбора над
diff, «Применить», «Повторить», отмена с `DELETE`, уход со страницы) — прогон раннера над той же страницей с этими
ответами модели.
