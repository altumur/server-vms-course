# K3 — адаптер `door` выходит с кодом 2, когда дверь отвечает 413 раньше, чем он дописал тело

**Случаев:** цель P/01.1/inproc, 239 шагов с `22-body-edge:111` до конца цели (19 сценариев, строки 111–350): 236 `red stand transport` и 3 `not_executed assertion` (строки 202, 236, 245 — сравнения с переменными, которые не связались). До строки 111 шаги MiniMax и Opus совпадают. После неё у Opus 235 GREEN, 3 GREEN и шаг 111 — общий `red implementation expectation` (P01.189). Все 239 различий двух кандидатов в inproc начинаются здесь.

Класс исхода у движка (`stand`) и судьба шагов после смерти адаптера — отдельный класс E1.

## Норма
- `PROFILE.md:105` («Store door»): «An operation refusal is a normal response, not an adapter exit or an outer error frame.»
- `PROFILE.md:107`: «Premature EOF, I/O failure or invalid outer JSON is a transport failure rather than an API refusal. … Normal shutdown is EOF on stdin after the last response; the adapter exits normally with code zero».
- `PROFILE.md:99`: один процесс получает несколько запросов подряд.
- RFC 9112 §9.6: сервер может ответить до конца тела и закрыть соединение. Сторона судьи это уже учитывает (R051, `acceptance.norms.md:147`): «A write of the rest of the request that fails because the implementation closed the connection after its response is neither a mismatch of the step nor a failure of the transport». R051 лежит только в J (`acceptance.norms.md` в M нет), модель его не видела. Адаптер — клиент двери кандидата и стоит на месте судьи; R051 к нему прямо не обращён. Поэтому класс держится на `PROFILE.md:105`, который модель видела.

## Наблюдение
Шаг `22-body-edge:111`: `POST /v1/write` с телом 4 МБ (`@big(4194304)`), лимит тела адаптера 1 МБ. Дверь кандидата отказывает рано (`NOTES.md:186`: «early 413») и закрывает соединение. Адаптер ещё пишет тело, получает EPIPE и выходит.

Повтор окна (песочница окна, `bin/door-adapter` собран из `77b90bef`, кадры по `run_adapters.go:231–245`):
1. `POST /v1/write` с малым телом → `(200, {"index":"1"})`;
2. тот же запрос с телом 4 МБ → ответа нет, EOF;
3. следующий кадр → stdin закрыт.
Код выхода 2, stderr: `door-adapter: write unix @->…/instance/ordinary.sock: write: broken pipe`.

## Код кандидата
`01-store/cmd/door-adapter/main.go`:
- `performHTTP` `:206–210`: `connection.Write(body)` с ошибкой → `return 0, nil, err`, ответ двери не читается;
- `serve` `:97–100`: любая ошибка `performHTTP` → `return err`;
- `main` `:40–43`: ошибка `serve` → `os.Exit(2)`.
Отказ двери превращается в смерть адаптера, а не в кадр `{status: 413, body: …}`. Тестов с телом больше лимита в `cmd/door-adapter/main_test.go` нет (два теста: статус и тело, запись через обычную роль).

## Что видела модель
- Раунд 3, сообщение 11: `nl -ba "$SPECS/…/PROFILE.md" | sed -n '1,115p'` — строки 105 и 107 в выводе целы, без `<path>`. PROFILE.md лежит в голове модели (`state.json`, `head_files`).
- Ворота адаптер не вызывали: `profile_probe.py` (цикл `561ea2c`) проверяет только `vectors` и `stand` (старт с файлом прав). Сигнала по K3 модель не получала.
- Догадки на этом месте нет.

## Мнение окна
Исход — **кандидат**. Норма `PROFILE.md:105` однозначна: отказ — обычный ответ, не выход адаптера. Причина по доп. (44): **модель (без обратной связи)**. Вторая причина — **цикл**: ворота не вызывали адаптер на теле больше лимита и не проверяли, что после отказа он отвечает дальше.

## Вопросы ревьюеру
1. Нужна ли в «Store door» фраза из R051 для адаптера: «запись тела после ответа двери может не пройти; адаптер читает ответ и возвращает его»? Без неё правило выводится из `:105` и RFC 9112 §9.6, но не названо.
