# Векторы токена двери

Векторы [договора токена двери](../../contracts/door-token.md): выпуск `door1.<kid>.<claims>.<sig>` (claims в JCS, подпись
Ed25519) и проверка у держателя по строке `door/keys`. Владелец договора — урок P/06, глава
[6.5](../../../06-console/spec/06.5-console.norms.md) (Н3 «`/where/<id>`»: консоль выдаёт токен); проверяющий — держатель
двери, глава [3.4](../../../03-worker/spec/03.4-worker.norms.md) Н3 «токен двери у держателя» (P/03.4-08). Пакет — общий:
алгоритм пишет один процесс, читают другие (решение «Архитектора» 2026-10-20, разбор ревью стадии B 3–5: подпись Ed25519
без векторов — молчаливое расхождение реализаций). Байты пишет «Спецификация» (ADR-0083); соответствие продукта — его
приёмкой по этим таблицам (ADR-0080 доп. 16).

## Прогон

Без стенда: консоль проходит `issue.tsv` своей функцией выпуска, держатель — `verify.tsv` своей функцией проверки; каждая
сторона может пройти обе таблицы. Время — входом `now` (стенные секунды), не часами процесса.

- `issue.tsv` — выпуск(`seed_hex`, `kid`, `claims`) даёт `claims_jcs` и `token` байт в байт. Ed25519 (RFC 8032)
  детерминирован: тот же seed и та же строка дают ту же подпись.
- `verify.tsv` — проверка(`keys`, `authorization`, `now`, `unit`, `holder`, `path`) даёт `ok` и прочитанные claims, равные
  колонке `claims` по значению JSON (не по тексту), или `forbidden` (чтение коммитов «cammeta-acceptance» 2026-10-20).

## Команда стенда `door-token-verify`

Ключ `stand` профиля `03-worker` (раздел «Раскладка по процессам» [общего README приёмки](../../../common/acceptance/README.md);
P/03.4 Н5): шаблон с `{input}` — путь файла, в который раннер пишет один JSON-объект входа строки: у `verify.tsv` —
`{keys, authorization, now, unit, holder, path}` (`keys` — значение колонки как JSON, `authorization` и `path` — строки
байт в байт, пустая строка `authorization` — заголовка нет, `now` — число), у `place.tsv` — ячейка `input` как есть
(`place_units` вместо `unit`; колонка `claims` — как у `verify.tsv`). stdout — ровно один JSON-объект в UTF-8 и LF: `{"result":"ok","claims":{…}}` — claims
прочитанного токена, сравниваются с колонкой `claims` по значению JSON, — или `{"result":"forbidden"}`; код 0. Вход не по
этой форме — код 2. Иной код, иной `result`, лишние поля или байты — FAIL строки (догадка стадии C W03-E04, решение
«Архитектора» 2026-10-23).

## Ключи

Зерно Ed25519 — 32 байта `sha256("w2c test <слово>")` (как ключи [векторов запечатывания](../sealing/README.md)); слова
порождения таблицы не называют — зерно и открытый ключ зафиксированы байтами, реализация берёт их отсюда и заново не
порождает (SA67-Б3). Зерно — то, что строка `door/signer` держит в `seed_secret` (64 строчных hex); открытый ключ — значение
строки `door/keys` под тем же `kid`.

| kid в векторах | seed_hex | открытый ключ (door/keys) |
|---|---|---|
| `c1` | `72207cdee579aae6185325025d5d4f82594247e8301c16b85909b5c363c2b8a9` | `865e70360600cb7dd29abc35426a83480f2d4039240f75d4d1ba2bcf894ea0db` |
| `c2-0123456789-abcdefghijklmnopqr` | `8e94e9035d25f0d2247b327ad5337ada38f934acd24c03e1aad23b4742f7f21a` | `3a42558c6b12b6e1dbcfc146e59401bffa3bd524e151493b65e2817e248d2428` |
| — (подделка) | `cc7b7d5d5b400b7efbf2053fae514d14d8daf638546d30bee836e95d671159ea` | `b3bfa2c840017b6309526eed5e4c0285630ab9b9db612d503afd1961cd3ae146` |

Третье зерно подписывает строку `forged_signer`; в `door/keys` векторов его ключа нет.

## Файлы

UTF-8, LF, поля через TAB; строки с `#` и пустые пропускаются, первая непропущенная — заголовок; `case` — имя строки,
`note` — зачем строка.

| Файл | Вход → ожидание |
|---|---|
| [`issue.tsv`](issue.tsv), 7 строк | `seed_hex`, `kid`, `now`, `claims` — объект `{user, unit, holder, routes, expires}` текстом JSON, как передан выпускающему (`expires` = `now` + 120) → `claims_jcs` — его форма RFC 8785 (UTF-8), `token` — `door1.<kid>.<base64url без «=» claims_jcs>.<base64url без «=» подписи над ASCII «door1.<kid>.<claims>»>`. Случаи: обычный, порядок полей (тот же токен), порядок `routes` (массив не сортируется), кириллица и символ вне BMP, экранирование, число с порядком, `kid` в 32 знака |
| [`verify.tsv`](verify.tsv), 89 строк: 17 `ok`, 72 `forbidden` (5 — DT-G01, 6 — DT-G02; разделитель HTAB и несколько заголовков `Authorization` строкой TSV не выразить — чтением) | `keys` — значение строки `door/keys` текстом JSON; `authorization` — заголовок `Authorization` целиком, пусто — заголовка нет (прежде колонка `token`; у большинства строк — `Bearer <token>`; (решение «Архитектора» 2026-10-20, разбор ревью стадии B 6–7)); `now`; `unit`, `holder` — свои у держателя (`unit` — `<sub>/<id>`, `holder` — `instance` его пульса); `path` — цель запроса к двери держателя: путь URL, у части строк с query (`?t=<token>`); первый сегмент пути URL без query сравнивается с элементами `routes` (разбор ревью стадии B 6–7, № 9) → `ok` и `claims` (текст части claims) или `forbidden` (колонка `claims` пуста) |
| [`place.tsv`](place.tsv), 3 строки: 1 `ok`, 2 `forbidden` | `input` — `{keys, authorization, now, holder, path, place_units}`: `place_units` — единицы, чьи данные лежат в месте держателя; токен места — договор «Токен места» (ADR-0091 доп. (7), (8)) → `expect` и `claims` — прочитанные claims у `ok` текстом JSON, сравниваются по значению; у `forbidden` пусто (чтение «cammeta-acceptance» 2026-10-23) |

## Отказы

Отказ проверки — одно слово `forbidden`, ответ двери держателя 403 с телом `{"error": "forbidden"}` без причины ([P/03.4](../../../03-worker/spec/03.4-worker.norms.md)
Н4, [договор](../../contracts/door-token.md) «Ключи `door/keys`») (решение «Архитектора» 2026-10-20, векторы door-token). Порядок проверок
вектор не фиксирует: причина в ответе не видна. Строки отказа — по списку проверки договора:

| Проверка договора | Строки |
|---|---|
| четыре части | `three_parts`, `five_parts`, `token_empty` |
| `door1` | `prefix_door2`, `prefix_upper` |
| `kid` в `door/keys` (нечитаемая строка — `kid` не найден, [исход семьи](../../../06-console/data/door-keys.outcomes.tsv)) | `unknown_kid`, `empty_keys`, `keys_upper_hex`, `keys_short_hex`, `keys_not_object`, `keys_bad_other_entry` (чужая запись не по форме — нечитаема вся строка; разбор ревью стадии B 6–7, № 8) |
| подпись — строго по RFC 8032 §5.1.7, в том числе `0 ≤ S < L` (разбор ревью стадии B 6–7, № 12) | `foreign_key`, `forged_signer`, `sig_bit`, `sig_last_bit`, `sig_short`, `sig_s_not_reduced`, `claims_swapped`; без кофактора, A или R малого порядка — отказ (решение «Архитектора» 2026-10-20, разбор ревью стадии B 6–7): `key_small_order`, `sig_r_small_order` |
| части — строгий base64url без «=», хвостовые биты последнего знака — нули | `sig_padded`, `claims_padded`, `claims_std_base64`, `sig_trailing_bits`, `claims_trailing_bits` |
| claims ровно `{user, unit, holder, routes, expires}` | `extra_field`, `missing_user`, `missing_expires`, `missing_unit`, `missing_holder`, `missing_routes`, `claims_not_json` |
| типы claims: `user`, `unit`, `holder` — строки; `routes` — массив строк без повторов; `expires` — целое ≤ 2^53−1 (решение «Архитектора» 2026-10-20, Kimi SB67-01) | `user_number`, `unit_number`, `holder_null`, `routes_not_array`, `routes_item_number`, `routes_dup`, `expires_string`, `expires_float`, `expires_over_2_53` |
| текст claims по I-JSON: строгий UTF-8, имя поля не повторяется, имена байт в байт (разбор ревью стадии B 6–7, № 8); без суррогатов и некодов (решение «Архитектора» 2026-10-20, разбор ревью стадии B 6–7) | `claims_bad_utf8`, `claims_dup_key`, `claims_name_case`, `claims_lone_surrogate`, `claims_noncharacter` |
| место токена: `Authorization: Bearer`, иначе единственный `?t=`; иная схема — как нет заголовка (решение «Архитектора» 2026-10-20, разбор ревью стадии B 6–7) | `no_token`, `query_t_repeated`, `auth_not_bearer_no_query` |
| элемент `routes` — сегмент по грамматике `name` `[a-z][a-z0-9_-]{0,31}`; целое JSON — только запись без точки и порядка (решение «Архитектора» 2026-10-20) | `routes_item_slash`, `routes_item_upper`, `expires_point_zero`, `expires_exponent` |
| `now < expires` (граница `now = expires` — отказ) | `expired_boundary`, `expired_after` |
| `unit` и `holder` свои | `other_unit`, `other_sub`, `other_holder` |
| первый сегмент пути запроса, сырым без раскодирования `%XX`, — элемент `routes` байт в байт; путь — без query (разбор ревью стадии B 6–7, № 9) | `route_not_in_routes`, `route_segment_prefix`, `route_second_segment`, `route_root`, `route_case`, `route_percent`, `route_query_only`, `route_in_query` |

Строки `ok_query_token` и `ok_query_one_segment` — контроль пути без query: токен в `?t=`, сегмент — до «?» (№ 9);
`ok_auth_not_bearer_query` — схема не Bearer, токен из `?t=`; `ok_bearer_over_query` — при Bearer query не читается (решение «Архитектора» 2026-10-20, разбор ревью стадии B 6–7). Строка `ok_expires_max` — контроль границы типа: `expires` = 2^53−1 даёт `ok`. Строка `claims_not_jcs` ждёт `ok`: выпускающий обязан писать claims в JCS, а проверяющий канон не проверяет, потому что
подпись покрывает байты части claims (решение «Архитектора» 2026-10-20, векторы door-token).

Строки `key_small_order` и `sig_r_small_order` удовлетворяют уравнению [S]B = R + [k]A; проверка OpenSSL (pyca cryptography) их принимает,
отказ даёт только условие договора «A или R малого порядка — отказ» (решение «Архитектора» 2026-10-20, разбор ревью стадии B 6–7).

Векторы получены эталонными Ed25519 (RFC 8032) и JCS (RFC 8785, проверен на [`jcs`](../../../01-store/vectors/jcs/README.md))
по договору, не по коду реализаций; при расхождении прав договор, вектор правит «Спецификация».
