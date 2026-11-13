# O1 — прокси API стенда пропускает только HTTP, а кандидат шлёт кадр read-fence

**Цель:** P/01.3/group, Opus 8. **Случаев:** 18 шагов red (12 «status 503 differs», 6 «the term of @until ran out: no response (timeout)»). **Класс:** движок; вторая причина — спецификация. Кандидат по M прав.

## Случай
Все 18 красных шагов — `GET /v1/get` на ролевом сокете **последователя**. Сценарии 07, 17, 18, 27, 29, 31; строки J `Platform/01-store/acceptance/3/scenarios.tsv` 15, 119, 122, 125, 132, 135, 137, 142, 156, 157, 176, 239, 241, 263, 265, 285, 286, 293.
- Пример: `07-group-size 11 store@s2 GET /v1/get?key=testsub/counters/g7` → ожидание `200 {"items": {"n": "1"}, …}` (scenarios.tsv:15).
- Тот же `GET` на лидере и через дверь зелёный: scenarios.tsv:16, 133, 169–171, 290, 304, 315, 328. Шаги :123 (s3) и :294 (s3) зелёные; это шаги после `@sigkill store@s1`, s3 в них, по всей видимости, лидер, а s2 рядом красный (:122, :293).
- Записи на последователе тоже зелёные (scenarios.tsv:116, 117, 287): их кандидат пересылает лидеру обычным HTTP.

## Наблюдение движка
- `out/opus8/P_01_3_group/engine.json`, `steps[]`: 12 шагов `"detail": "status 503 differs"`, `body_len` 65, `body_sha256` `855d74d9…`; 6 шагов `@until` — `no response (timeout)`. Цель шла 285 с (`log/times-opus8.tsv`), у Opus 7 на том же J и движке a00af33f — 40 с, GREEN 207 (`P01.290-circle-newJ-b-20261112T2156Z/table-claude7-pin.md`).
- Тело 503 восстановлено по коду кандидата: `{"kind":"unavailable","error":"no leader within the leader wait"}` — 65 байт, SHA256 `855d74d974c5a888d953079f0230ffa92d3e9146483bf3f6181529436c93f455` совпадает (окно посчитало `sha256sum` строки). Это отказ `no_leader_wait` (`internal/refusal/refusals.tsv:20`, текст — `internal/api/read.go:132`).
- Суды не шли параллельно: group Opus 8 — 07:39:15–07:44:00, MiniMax 8 начат в 07:44:56 (`opus8/log/times-opus8.tsv`, `minimax8/log/times-minimax8.tsv`). Барьер свежего `-join` прошёл: шаги 3–5 сценариев зелёные.

## Механизм
1. **Кандидат.** Чтение на последователе идёт через забор чтения: `internal/group/backend.go:216–218` (`Read` → `fence`; ошибка → `no_leader_wait`). `leaderIndex` (`backend.go:187–212`) шлёт лидеру внутренний кадр `{"op":"read-fence"}` по его `-api` (`backend.go:201`). Кадр — не HTTP: преамбула `"\x00w2c-configstore-admin-frame 1\n"` и строка JSON (`internal/adminframe/frame.go:18`, `internal/group/peer.go:92–116`). Лидер различает кадр по первому байту NUL (`internal/httpx/conn.go:39–49`; `-api` получает обработчик кадров — `internal/daemon/startbox.go:105`, `internal/group/frames.go:84–112`). При ошибке `leaderIndex` повторяет кадр каждые 50 мс до `-leader-wait` (`backend.go:207–211`); стенд не задаёт `-leader-wait` (`engine/runner/group.go:175–178`), значит 5 с (`internal/flags/daemon-flags.tsv:38`). Отсюда 503 после 5 с на каждый шаг. Под `@until 20/30` попытки идут по 5 с; последняя, по всей видимости, не успевает до конца срока — «no response (timeout)» (вывод окна по формулировке движка).
2. **Движок.** `{api@<id>}` — адрес прокси API раннера, его кандидат и называет партнёрам (`runner/group.go:175`). Прокси разбирает поток как HTTP: `transport/tls.go:190–198` — `http.ReadRequest`; на не-HTTP он закрывает соединение (`:191–193`). Это код снимка 340fbb39; в a00af33f прокси стал подключаться к порту участника до рукопожатия (`P01.255-continue-circle3-20261112T2132Z/RESULT.md:13`), а разбор HTTP остался: в NOTES того же снимка — «mTLS HTTP-aware API proxy» (`NOTES.md:48`). Кадр read-fence до лидера не доходит.
3. **Opus 7 зелёный** потому, что ролевой `GET` на последователе он пересылает лидеру HTTP-запросом (`attempt7-review-inputs/candidate-claude/01-store/internal/daemon/voter.go:87–106`, пересылка — `:103`). Кадр забора (`CSADM/1 read-fence`, тоже не HTTP) он шлёт только для `admin.sock` последователя (`voter.go:96–102`; `internal/group/ops.go:306–324`). Таких шагов в group J нет.
4. **Свои тесты кандидата** зелёные: `internal/daemon/group_test.go:148`, `:150` читают на последователе s3, но ходят на `-api` участников напрямую, без прокси стенда.

## Норма
- Механизм линеаризуемого чтения — выбор реализации: `Platform/01-store/spec/01.1-store.norms.md:406` («The mechanism — the implementation decides»).
- Внутренние кадры между участниками разрешены и названы: «the raft wire between members and the frame of `admin.sock` (read-fence, admit, import) remain internal to the implementation: a format with a name and a version, no new HTTP routes» — `01.3-store.norms.md:789–790`. Канал кадра read-fence норма не называет. Новый HTTP-маршрут для него запрещён.
- Прокси стенда в M: «By default it passes every request and every answer unchanged; `@cut store@<id> answer` changes this» — `acceptance/3/README.md:122` (M и J побайтно одинаковы в этой строке). Что «request» — только HTTP, текст не говорит; строка :134 про `@cut … answer` говорит о `POST /v1/write`, но только для режима обрыва.
- Кандидат описал выбор в своём описании, как велит п. 1: `01-store/ARCHITECTURE.md:90–92` («frames … on `-api` between voters (read-fence, join, leave) — not HTTP routes»).

## Что видела модель
Задание контроля (`P01.289-…/CONTROL-TASK-attempt7.md:1–3`): генерация без ворот и без проверок, только M. Модель прочла норму `01.3:789–790` и выбрала кадр на `-api`; в `GUESSES.md` догадки об этом нет — выбор она считала прямо разрешённым (п. 1 «Implementation decides»). Про то, что прокси стенда понимает только HTTP, M ей не сказала.

## Исход
- **Движок:** прокси API уже описания стенда M (`README.md:122` «every request … unchanged»). Под ним легальная реализация по `01.3:789–790` не может прочесть на последователе.
- **Спецификация (вторая):** между п. 1 «Implementation decides» (кадры между участниками, без канала) и описанием прокси (`README.md:122`) — молчаливая развилка: можно ли слать не-HTTP по `-api`. Две реализации одной M разошлись по ней (Opus 7 — HTTP-пересылка, Opus 8 — кадр).
- **Кандидат:** нет. Правка кандидата не нужна.

## Что предлагается
- **Движок:** прокси API пропускает байты как есть (TLS с обеих сторон, без разбора); разбор HTTP — только под `@cut store@<id> answer`. Либо, если владелец решит, что `-api` — только HTTP, — это норма (ниже), а не выбор движка.
- **Норма (одно из двух, решение владельца):** (а) в `README.md:122` сказать, что прокси пропускает любой поток байтов, кроме режима `answer`; или (б) в `01.3:789–790` сказать, по какому каналу ходит read-fence между участниками (например, «кадры между участниками — по raft-проводу, `-api` несёт только HTTP/1.1 дверей»).
