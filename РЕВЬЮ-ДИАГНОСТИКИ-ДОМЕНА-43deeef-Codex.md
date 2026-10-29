# Третье ревью диагностики домена — Codex

Серия `domain-admission-diagnostics`: база `bf7f97a`, вершина `43deeef656278d3b067b6a1f9499fe00baf451c0`, прочитана новая ревизия от `fbc7c8f`. Пины — `7c72f79` и jsdom `6df3427`. Прочитаны все 31 изменённый файл; прежние чтения исходной серии сохраняются.

Вердикт: оба P2 прошлого чтения закрыты. Одна находка P2 в очистке кодированных логов; CLEAN не выдан.

## P2 — кодированный payload после метки в логе остаётся обратимым

Место: [diagnostic_secrets.py:99](/Users/murat/w2c/cammeta-diff/acceptance-server/review-domain-diagnostics-43deeef/check-input/runner/runner/diagnostic_secrets.py:99), файловый путь — [diagnostic_secrets.py:188](/Users/murat/w2c/cammeta-diff/acceptance-server/review-domain-diagnostics-43deeef/check-input/runner/runner/diagnostic_secrets.py:188).

`Secrets.encoded()` пробует целую строку, целую строку без пробелов и отдельные непрерывные слова длиной от восьми знаков. Это распознаёт отдельно цельный кодированный payload и отдельно кодированное слово в логе. Но сочетание текстовой метки с payload, разбитым переносами или пробелами, не распознаётся.

Для base64 с переносами строка целиком содержит `payload:`, поэтому не проходит проверку алфавита. Каждая отдельная строка base64 декодируется лишь в часть длинного секрета, а поиск требует целое известное значение. Для hex с пробелами отдельные двухзначные байты вообще не попадают в список слов. Финальный проход оставляет обе обратимые записи, хотя секрет зарегистрирован **до** очистки.

Контроль с двумя обычными представлениями одного синтетического credential:

```python
secret = "fixture-wrapped-credential-" + "s" * 180
secrets = diagnostic_secrets.Secrets()
secrets.remember(secret)
(folder / "wrapped.log").write_bytes(
    b"payload:\n" + base64.encodebytes(secret.encode()))
(folder / "spaced-hex.log").write_text(
    "payload: " + secret.encode().hex(" ") + "\n")
secrets.finalize([folder])

decoded_b64 = base64.b64decode(
    (folder / "wrapped.log").read_bytes().partition(b"payload:\n")[2])
decoded_hex = bytes.fromhex(
    (folder / "spaced-hex.log").read_text().partition("payload: ")[2])
assert secret.encode() not in decoded_b64  # FAIL
assert secret.encode() not in decoded_hex  # FAIL
```

Оба декодирования восстанавливают весь credential — 207 байт. Base64-лог после `finalize()` побайтно равен исходному. Такие логи проходят через общий файловый очиститель, используемый для копий улик и `--keep`.

Дополнительно настоящий `scan_evidence()` из новой фикстуры был вызван на **обоих** сохранённых файлах с этим известным значением: проверка прошла. Сканер повторяет тот же способ выделения отдельных слов и не замечает утечку. Следовательно, GREEN его декодирующего обхода здесь не подтверждает отсутствие обратимой копии. Нужен контроль, который собирает payload с переносами/пробелами после текстовой метки и декодирует его целиком; очистка должна исключить восстановление значения из такого лога.

## Проверка

CT 103 `20261029T223354Z-rv-p3-43deeef`: 11,1 с, без таймаута, SUT=0. SHA256 MANIFEST `ccaa4e745ffb979f1c6de382d1f757b07dcc53ebd7451fb069877e2e55cf6c06` и все 6632 файла подтверждены. Все 100 целевых тестов автора прошли без ошибок и отказов.

Повторены прежние контроли: префикса токена в `polls.view` больше нет; транспорт с пустым реестром не создаёт `response_b64` и `response.bin`; исходный объект ответа для судьи сохраняется. Exit 1 получен только от новых проверок обратимости логов. Это одна находка с двумя воспроизведениями.

Свидетельства рядом с отчётом: `РЕВЬЮ-ДИАГНОСТИКИ-ДОМЕНА-43deeef-Codex-evidence.json` — сводка; файлы с суффиксами `-base64.txt` и `-hex.txt` — копии очищенных `wrapped.log` и `spaced-hex.log` из результата CT, только синтетические данные. Вход и результат под KEEP: `/Users/murat/w2c/cammeta-diff/acceptance-server/checks/20261029T223354Z-rv-p3-43deeef/`; input SHA256 `98647a207aacd896d2e4427638aca1f1808da89231932bfedf8f43adbc9aca44`.

Авторский полный V7 `20261029T222526Z-privacy-binary-final`: 80 модулей / 945 тестов, 9 штатных пропусков, GREEN, входы неизменны. Полный V7 повторно не запускал. Других находок по прочитанной дельте нет. Код курса, раннера и реализаций не изменялся.
