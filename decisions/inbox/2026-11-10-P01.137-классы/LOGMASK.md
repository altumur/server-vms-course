# LOGMASK — 11 строк log-mask `cases.tsv`, красных у обоих судей (М6 ревью P01.112)

**Случаев:** 11 «не GREEN у обоих» на dcdc0bfe — строки 20, 29, 31, 32, 33, 43, 53, 54, 55, 56, 57 `Platform/common/vectors/log-mask/cases.tsv` (на c36e6ac в P01.80 их было 9). Не расхождение судей: оба красят те же строки по той же причине.

## Суть
Раннер по каждой строке: `classification: implementation`, `why: ["native stdout differs from published expect"]`. Движок: `red`, class `implementation`, reason `native`, `response: valid`. Строки — пограничные случаи маски: URL-кодированный секрет в адресе (20), адрес RTSP с `user=` и `password=` (29), JSON без кавычек у секрета (31), учётные данные в адресе внутри JSON (32), имя «&pwd» в URL-кодировке (33), конец значения на U+00A0 / U+000B / U+3000 (43, 53–57).

## Норма
Шапка таблицы `cases.tsv:1–6`: «The norm — M10/7 N1.4 `log` with N1.1a (pairs, addresses)»; владелец — контракт `Platform/common/contracts/log-mask.md` (P/06.2 N1.4 `never.log`); README пакета `Platform/common/vectors/log-mask/README.md:5`. Пояснения строк — третья колонка таблицы (например, строка 53: «a no-break space (U+00A0) ends the credential»).

## Образцы (вывод кандидата — `…-court/acc/P_01_vectors-log-mask/P-01-vectors-log-mask-processes/case-NNNN/stdout.bin`, base64 декодирован)
| Строка | Ожидание | Кандидат | Движок (`out/P_01_vectors-log-mask/engine.json`) |
|---|---|---|---|
| 29 | `DESCRIBE rtsp://10.0.0.9:554/user=admin&password=***&channel=1&stream=0.sdp RTSP/1.0` | `…/user=***&password=***&channel=1…` — маскирует `user` и выводит `&` как `&` | `red implementation native` |
| 32 | `{"source":"driverpack://acme/u:***@10.0.0.5/ch/1"}` | `{\"source\":\"driverpack://acme/u:hunter2xyz@10.0.0.5/ch/1\"}` — секрет не замаскирован | `red implementation native` |
| 53 | `Authorization: Bearer *** x` (U+00A0 перед `x`) | `Authorization: Bearer ***` — хвост после U+00A0 потерян | `red implementation native` |

## Мнение представителя
Исход — **кандидат** (продукт попытки 4): оба судьи сравнивают верно и согласны; норма и пояснения строк однозначны. По схеме для продукта — модель (без обратной связи по поведению, ADR-0133 доп. (42)). Для судей правила не нужно.

## Вопросы ревьюеру
1. Подтверди, что ожидания строк 29 (только `password` маскируется, `user` — нет; `&` остаётся байтом) и 53 следуют из N1.4/N1.1a однозначно.
2. Есть ли среди 11 строк такие, где ожидание спорно (пробел нормы)?
