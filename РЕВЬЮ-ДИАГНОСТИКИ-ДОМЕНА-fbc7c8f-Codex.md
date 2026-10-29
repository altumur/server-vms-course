# Повторное ревью диагностики домена — Codex

Серия: `domain-admission-diagnostics`, база `bf7f97a`, вершина `fbc7c8f4157f57905f9b820460c6c10d310dd08a`. Повторно прочитана дельта от `727210b`; прежнее чтение всей исходной серии сохраняется. Пины — `7c72f79` и jsdom `6df3427`.

Вердикт: исходный P2 закрыт; две находки P2 в расширенной очистке. CLEAN не выдан.

## P2 — усечение polls.view сохраняет префикс известного секрета

Место: [m11stand.py:1136](/Users/murat/w2c/cammeta-diff/acceptance-server/review-domain-diagnostics-fbc7c8f/check-input/runner/runner/m11stand.py:1136), [until_trace.py:72](/Users/murat/w2c/cammeta-diff/acceptance-server/review-domain-diagnostics-fbc7c8f/check-input/runner/runner/until_trace.py:72), [diagnostic_secrets.py:53](/Users/murat/w2c/cammeta-diff/acceptance-server/review-domain-diagnostics-fbc7c8f/check-input/runner/runner/diagnostic_secrets.py:53).

`Run._step()` передаёт исходный ответ в `Trace.record()`. Тот сначала обрезает JSON-проекцию до 299 символов и добавляет `…`. Последующий `Secrets.clean()` экспортёра заменяет только полные значения секретов. Защита границы в `Secrets.text(limit=...)` здесь не применяется: очистка строки вызывает `text()` без `limit`, а усечённый префикс уже заканчивается многоточием.

Контроль использует настоящий `Run.step()` и синтетическую дверь:

```python
secret = "fixture-private-credential-" + "s" * 180
run = m11stand.Run(SimpleNamespace(), "privacy-poll-fixture")
run.secrets.remember(secret)
body = {"detail": "x" * 150 + secret}
run.b = SimpleNamespace(door=lambda *args: (200, body, {}))
run.bearer = lambda: None
why, got = run.step("1", "@until 1 holder GET /x", '200 {"detail":"@any"}')
polls = run.secrets.clean(run.last_polls)
assert secret[:50] not in json.dumps(polls)  # FAIL
```

Шаг успешен, исходный `got` не изменён, но очищенный `polls.view` содержит более 50 начальных символов credential. Это поле попадает в отчёты Platform, VMS и TLS. Требование замены до усечения не выполнено. Очистка диагностической проекции должна предшествовать её ограничению длины, при сохранении исходных данных для судьи.

## P2 — поздно зарегистрированный секрет остаётся обратимым в response_b64

Место: [transport_diagnostics.py:60](/Users/murat/w2c/cammeta-diff/acceptance-server/review-domain-diagnostics-fbc7c8f/check-input/runner/runner/transport_diagnostics.py:60), [diagnostic_secrets.py:102](/Users/murat/w2c/cammeta-diff/acceptance-server/review-domain-diagnostics-fbc7c8f/check-input/runner/runner/diagnostic_secrets.py:102).

При существующем, но пока пустом реестре `save()` сохраняет исходный ответ и `response_b64`. Если значение становится известным позднее, финальные проходы `Secrets.files()` заменяют его в `response.bin`, но не декодируют и не удаляют `response_b64` в уже записанном JSON. Даже два прохода оставляют восстановимую копию целого credential.

Контроль:

```python
secrets = diagnostic_secrets.Secrets()
secret = "fixture-later-issued-credential"
wire = (b"HTTP/1.1 503 Error\r\nContent-Type: application/json\r\n\r\n"
        + json.dumps({"token": secret}).encode())
saved = transport_diagnostics.save(None,
    {"_response": wire, "response_size": len(wire)}, folder, secrets=secrets)
(folder / "report.json").write_text(json.dumps(saved))
secrets.remember(secret)
secrets.files(folder)
secrets.files(folder)
saved = json.loads((folder / "report.json").read_text())
assert secret.encode() not in base64.b64decode(saved["response_b64"])  # FAIL
```

Предусловие — запись транспортной улики до появления первого значения в реестре. После регистрации значения итоговая улика всё ещё восстанавливает его целиком. Поэтому заявленный финальный проход для значений, узнанных после ранней записи, неполон. Нужна очистка или исключение обратимых копий при позднем обновлении реестра; условие только на непустой реестр в момент `save()` этого не обеспечивает.

## Проверка и свидетельства

CT 103: `20261029T215815Z-rv-p2-fbc7c8f`, SUT=0, 11,0 с, без таймаута. SHA256 MANIFEST `1c33ead6711c75c45b01adab9a1f28f03ef8a3787b266948686a9c48611ad8d9` и все 5930 файлов пакета подтверждены.

Все 54 целевых теста автора прошли, без ошибок и отказов. Исходный контроль повреждённого JSON теперь проходит. Новый контроль с настоящим `Run.step()` подтверждает неизменность исходного объекта для судьи. Exit 1 получен от двух дополнительных проверок отсутствия утечки, а не от авторских тестов.

Свидетельства рядом с отчётом: `РЕВЬЮ-ДИАГНОСТИКИ-ДОМЕНА-fbc7c8f-Codex-evidence.json` — сводка и очищенный `polls`; `РЕВЬЮ-ДИАГНОСТИКИ-ДОМЕНА-fbc7c8f-Codex-base64.json` — сохранённая транспортная улика с синтетическим credential. Это копии файлов результата CT 103. Вход и результат сохранены под KEEP в `/Users/murat/w2c/cammeta-diff/acceptance-server/checks/20261029T215815Z-rv-p2-fbc7c8f/`; input SHA256 — `dc0872d01601881a7cafcf951612257e63f1dc018bbd443e2dde97055abab72a`.

Авторский полный прогон `20261029T214824Z-privacy-step-adapter`: 80 модулей / 938 тестов, 9 штатных пропусков, GREEN, входы неизменны. Повторно его не запускал. Дополнительных находок по дельте учёта процессов и teardown нет. Код курса, раннера и реализаций не изменялся.
