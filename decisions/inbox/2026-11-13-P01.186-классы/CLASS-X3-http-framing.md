# X3 — MiniMax 8: три ошибки разбора тела HTTP (CL+TE, HTTP/1.0+TE, огромный Content-Length)

**Случаев:** P/01.1/extra — 4 строки и 3 входа (`engine.json`: `rows` red 4, `entries` red 3). Каждый вход — свой сценарий. У Opus 8 все три GREEN.

| Сценарий (J `extra.scenarios.tsv`) | Ждёт | Наблюдение движка |
|---|---|---|
| `extra-cl-and-te`, строка 35: `Content-Length: 70` и `Transfer-Encoding: chunked` | `200 @close {"index":"$a"}` | `the connection was not closed after the response` |
| `extra-http10-te`, строка 37: `HTTP/1.0` и `Transfer-Encoding: chunked` | `400 @close {"kind":"badrequest"}` | `status 200 differs` |
| `extra-http10-te`, строка 38: чтение того же ключа | `200 {"items":null,"index":""}` | `body /items: value differs` (запись прошла — следствие строки 37) |
| `extra-framing`, строка 59: `Content-Length: 99999999999999999999999` | `413 @close {"kind":"toolarge","limit":1048576}` | `body /limit: value differs` |

Источник наблюдений: `minimax8/out/minimax8/P_01_1_extra/engine.json`, `rows` и `entries`. Сценарии J модели не видны (в M нет `extra.scenarios.tsv`).

## Норма (M)
- `spec/01.1-store.norms.md:356`: «**Body framing** follows RFC 9112 §6–7 … A length number larger than the implementation can represent — `413 toolarge`: it is certainly larger than the body limit, no `size`». Поле `limit` у `toolarge` — предел тела.
- `spec/01.1-store.norms.md:359`: «With `Content-Length` and `Transfer-Encoding: chunked` together the body is read as chunked (§6.3)». «After any framing error the door MUST close the connection».
- RFC 9112 §6.1 (по ссылке из `:356`): при CL и TE вместе сервер «MUST close the connection after responding»; сообщение HTTP/1.0 с `Transfer-Encoding` — «as if the framing is faulty … and close the connection».

## Код кандидата (`internal/daemon/http_server.go`)
1. **CL+TE без закрытия.** `parseFraming` `:307–343` выбирает chunked и ничего не говорит о закрытии. `readRequest` `:142–146` берёт `closeAfter` только из `connectionMustClose` `:487–492`: заголовок `Connection: close` или HTTP/1.0 без keep-alive. Соединение остаётся открытым.
2. **HTTP/1.0 + TE принят.** `parseFraming` не смотрит на версию; `readRequest` читает chunked-тело для HTTP/1.0 и исполняет запись.
3. **`limit: 0` у огромного CL.** `parseFraming` `:328–329` и `:338–339` возвращает `requestFailureTooLarge` без поля `limit` (функции не передан `maxBody`). `serveConnection` `:73–74` строит ответ `bodyLimitResponse(failure.limit, …)` — в теле `"limit":0`. Для chunked (`:397`) и обычного тела (`:358`) предел передаётся, ошибка только здесь.

Собственные тесты (`internal/daemon/handler_test.go:306–308`) проверяют `Content-Length: +5` и `0x5` — оба примера есть в тексте M `:356`. Случаев CL+TE, HTTP/1.0+TE и CL больше uint64 нет.

## Код движка
`runner/scenario.go:536` (снимок 340fbb39) — проверка `@close`. Движок прав: Opus 8 на тех же строках GREEN.

## Что видела модель
- N2.1 главы 1.1 — в голове этапа `http` (`stages.tsv:28`, `norms: P/01.1 N2`). Этап закрыт в раунде 6 по воротам `mech` 44/44 (`passport.json`, `stages.http.gates`); сценарии `accept:1.1:*` не исполнялись (`log.jsonl`, раунды 4–6, `judge.total = 0`).
- Догадки нет.

## Мнение окна
Исход — **кандидат** по всем трём. Причина по доп. (44): **модель (без обратной связи)**. Для пункта 3 норма прямо в тексте M. Для пунктов 1 и 2 вторая причина — **спека**: обязанность закрыть соединение при CL+TE и отказ HTTP/1.0+TE стоят только в RFC по ссылке; строка `:359` пересказывает §6.3 «read as chunked» и молчит о закрытии. Это не молчаливая развилка (R7): RFC однозначен, догадки нет. Предложение спеке: дописать в `:359` «… and the door closes the connection after the response; a `Transfer-Encoding` in an HTTP/1.0 request is a framing error (RFC 9112 §6.1)».
